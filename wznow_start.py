"""Start bota: kontynuacja tego, co postać robiła, od miejsca, w którym stoi (Karol 22.10: „po restarcie bot ma
kontynuować od momentu, w którym jest, a nie zaczynać od nowa”).

Przypadek 22.10 13:56, dawajkesh: wyprawa do depo po blanki utknęła na z11 -> z10 i zapisała STOP, stan wyprawy
miał `aktywna: false, wynik: blad`. Restart `uruchom_instancje.sh` puścił DOJŚCIE na spot (`mozg.main`) i postać
poszła z powrotem w górę zamiast dokończyć drogę do depo.

Zasada: ZANIM mozg.main puści dojście, pyta tego modułu, czy jest przerwana wyprawa (do depo/refill/WROC/serwis
= `wyprawa_stan.json`), której powód nadal zachodzi. Jeśli tak, odnawia zapis (aktywna=True) i woła
`Wyprawa._wznow`, które buduje plan wyprawy i wznawia od najbliższego punktu planu względem BIEŻĄCEJ pozycji
(<= WZNOW_ODL pól). Wznowienie się nie udało (poza planem, powód nieaktualny, zbyt wiele prób) = wszystko jak
dotąd: dojście od najbliższego punktu (`mozg.dojscie_od_pozycji`), a na spocie bez dojścia (`mozg.DOJSCIE_POMIN_ODL`).

Czysta logika, bez ruchu w grze. Wyłączniki (każdy z dwóch wystarcza, stare zachowanie): `RETRONIC_WZNOW_START=0` w środowisku
startu oraz pokrętło `WZNOW_START` (0/1, domyślnie 1) w na_zywo.json instancji (26.10, Karol, test na Odchydzie: „niech zawsze
zaczyna od tego miejsca”). Pokrętło 0 = nie wznawiamy, a stary zapis przerwanej wyprawy jest ZAMYKANY (wynik
`anulowana_pokretlo`), żeby nie wrócił przy kolejnym starcie; bot idzie zwykłą logiką startu (dojście/od bieżącej pozycji)."""
import os
import time
from pathlib import Path

WLACZONE = os.environ.get("RETRONIC_WZNOW_START", "1") != "0"
WZNOW_START_MAX_S = 4 * 3600          # s od ostatniego zapisu stanu wyprawy: starszy zapis nie jest wznawiany
WZNOW_START_RECZNY_BLAD_S = 1800      # s: ręczne „Wróć do miasta”, które skończyło się błędem, wznawiamy tylko krótko po nim
WZNOW_START_PROB = 3                  # tyle wznowień po starcie w oknie WZNOW_START_OKNO_S; potem dojście jak dotąd
WZNOW_START_OKNO_S = 2 * 3600         # (pętla restart -> to samo zacięcie -> STOP -> nadzorca restart nie może trwać w nieskończoność)


POKRETLO = "WZNOW_START"


def pokretlo(plik=None):
    """Pokrętło WZNOW_START z na_zywo.json instancji (czytane przy starcie, bo hook w mozg.main działa PRZED budową cavebota
    i jego hot-reloadem). 1 = wznawiaj (domyślnie), 0 = nie. Brak pliku/klucza, zły typ lub wartość poza ZAKRESY = 1
    (tak samo `pokretla.waliduj` odrzuca takie wartości i zostaje domyślna)."""
    import pokretla  # noqa: PLC0415
    dane = _json(pokretla.PLIK if plik is None else plik)
    if POKRETLO not in dane:
        return 1
    ok, _bledy = pokretla.waliduj({POKRETLO: dane[POKRETLO]})
    return 1 if POKRETLO not in ok else (0 if ok[POKRETLO] == 0 else 1)


def _json(plik):
    import json  # noqa: PLC0415
    try:
        d = json.loads(Path(plik).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def powody(st):
    """Powody wyprawy z zapisu stanu: 'depo:blanki+zapas' -> {'blanki','zapas'} (bez słów 'wyprawa'/'depo')."""
    import re  # noqa: PLC0415
    return {t for t in re.split(r"[:+]", str(st.get("powod") or "")) if t} - {"wyprawa", "depo"}


def kandydat(st, teraz_wall):
    """(rodzaj, opis): 'aktywna' = wyprawa w toku w chwili zatrzymania bota (kill, STOP, restart, awaria procesu),
    'blad' = wyprawa zakończona błędem/zacięciem (STOP po utknięciu), którą można dokończyć po naprawie przyczyny,
    None = nic do wznowienia (opis mówi dlaczego). Wyprawy PK i teleport/śmierć nigdy nie są wznawiane
    automatycznie przy 'blad' (zagrożenie życia: człowiek decyduje)."""
    if not st:
        return None, "brak zapisu stanu wyprawy"
    potrzeby = st.get("potrzeby") or {}
    zapis = float(st.get("zapis_wall") or st.get("t_wall") or 0)
    wiek = max(0.0, teraz_wall - zapis)
    if st.get("aktywna"):
        if wiek > WZNOW_START_MAX_S:
            return None, f"zapis wyprawy sprzed {wiek / 60:.0f} min (limit {WZNOW_START_MAX_S // 60})"
        return "aktywna", f"wyprawa w toku w chwili zatrzymania ({wiek:.0f} s temu)"
    if st.get("wynik") == "blad":
        if potrzeby.get("pk"):
            return None, "wyprawa PK zakończona błędem: bez automatu"
        if "teleport" in str(st.get("opis") or ""):
            return None, "teleport/śmierć w drodze: bez automatu"
        if not potrzeby or not st.get("baza"):
            return None, "brak planu wyprawy w zapisie"
        limit = WZNOW_START_RECZNY_BLAD_S if potrzeby.get("reczny") else WZNOW_START_MAX_S
        if wiek > limit:
            return None, f"wyprawa zakończona błędem {wiek / 60:.0f} min temu (limit {limit // 60} min)"
        return "blad", f"wyprawa zakończona błędem {wiek:.0f} s temu: {str(st.get('opis') or '')[:80]}"
    return None, f"ostatnia wyprawa: wynik {st.get('wynik')!r}, nieaktywna"


def jest_kandydat(plik_stanu, teraz_wall=None):
    """Tani test przed budową całego cavebota: czy zapis stanu wyprawy w ogóle wygląda na do wznowienia."""
    return kandydat(_json(plik_stanu), time.time() if teraz_wall is None else teraz_wall)[0] is not None


def za_wiele_prob(st, teraz_wall):
    """(True, n), gdy w oknie WZNOW_START_OKNO_S było już WZNOW_START_PROB wznowień po starcie."""
    ws = st.get("wznow_start") or {}
    n = int(ws.get("n") or 0)
    if teraz_wall - float(ws.get("t") or 0) > WZNOW_START_OKNO_S:
        n = 0
    return n >= WZNOW_START_PROB, n


def powod_aktualny(wyprawa, st):
    """(True/False, opis). Reczny (WROC): zawsze aktualny. Blanki: aktualny, gdy w plecaku nadal < WYPRAWA_BLANKI_PROG
    (nie da się odczytać plecaka = aktualny, jak w Wyprawa._powod_ustal). Zapas/głód sprawdza potem Wyprawa._wznow
    (_powod_ustal). Brak rozpoznanego powodu = aktualny."""
    p = powody(st)
    if "reczny" in p or not p:
        return True, "reczny" if p else "powód nieznany: wznawiam"
    inne = p - {"blanki"}
    if "blanki" not in p:
        return True, f"powód {sorted(p)} sprawdzi wznowienie wyprawy"
    try:
        plecak = wyprawa.ops.plecak()
        ile = wyprawa._ile(plecak, "blank") if plecak is not None else None
        prog = int(wyprawa._kw("WYPRAWA_BLANKI_PROG"))
    except Exception as e:               # noqa: BLE001  (nie umiemy sprawdzić = wznawiamy, jak walidacja jedzenia)
        return True, f"blanki: nie sprawdziłem ({e!r}), wznawiam"
    if ile is None or ile < prog:
        return True, f"blanki {ile} < próg {prog}: powód nadal zachodzi"
    if inne:
        return True, f"blanki {ile} >= próg {prog}, ale zostają powody {sorted(inne)}"
    return False, f"blanki {ile} >= próg {prog}: powód wyprawy już nie zachodzi"


def sprobuj(wyprawa, log=print, teraz_wall=None, plik_pokretel=None):
    """Próbuje wznowić przerwaną wyprawę od BIEŻĄCEJ pozycji (Wyprawa._wznow). True = wyprawa działa (stan WYPAD,
    pierwszy obieg ją poprowadzi), mozg.main pomija wtedy dojście i test „na spocie”. False = nic się nie zmienia
    (stan wyprawy cofnięty tak, by nie skracać karencji nieudanej wyprawy), main idzie starą ścieżką."""
    if not WLACZONE or wyprawa is None or not hasattr(wyprawa, "_wznow") or not hasattr(wyprawa, "plik_stanu"):
        return False
    teraz_w = float(wyprawa.czas() if teraz_wall is None else teraz_wall)
    # 26.10 (PK_RESET_PO_ZGONIE): zgon sprzed startu = wyprawa PK (ucieczka do depo / powrót na spot) jest nieaktualna: cavebot
    # rozpoznaje zgon z danych na dysku (pk_zgon.py), zeruje karencję i zamyka zapis wyprawy PK; zwykłych wypraw to nie dotyczy.
    zgon = (False, "")
    fn = getattr(getattr(wyprawa, "cb", None), "_pk_zgon_start", None)
    if callable(fn):
        try:
            zgon = fn()
        except Exception as e:             # noqa: BLE001
            import bot  # noqa: PLC0415
            if isinstance(e, bot.Zatrzymano):
                raise
            log(f"Start: rozpoznanie zgonu nie powiodło się ({e!r}), bez resetu PK.")
    st = wyprawa._stan_czytaj()
    if zgon[0] and (st.get("potrzeby") or {}).get("pk") and (st.get("aktywna") or st.get("wynik") == "blad"):
        log(f"Start: wyprawa PK z zapisu odrzucona po zgonie postaci ({zgon[1]}): nie wznawiam, dojście od bieżącej pozycji.")
        return False
    rodzaj, opis = kandydat(st, teraz_w)
    if pokretlo(plik_pokretel) == 0:
        # 26.10 WZNOW_START=0: bez wznowienia; zapis przerwanej wyprawy zamykamy (nie wróci przy kolejnym starcie).
        # Karencji (nast_wall) i reszty zapisu nie ruszamy; zamykamy tylko wyprawę w toku/przerwaną/kandydata.
        if rodzaj is not None or st.get("aktywna") or st.get("przerwana"):
            wyprawa._stan_zapisz(aktywna=False, przerwana=False, faza=None, wynik="anulowana_pokretlo", zapis_wall=teraz_w,
                                 opis="pokrętło WZNOW_START=0: start od bieżącej pozycji, zapis przerwanej wyprawy zamknięty")
            log(f"Start: pokrętło WZNOW_START=0: NIE wznawiam przerwanej wyprawy ({opis}), zapis zamknięty; "
                "zwykła logika startu (dojście/od bieżącej pozycji).")
        else:
            log(f"Start: pokrętło WZNOW_START=0, wyprawy do wznowienia i tak brak ({opis}).")
        return False
    if rodzaj is None:
        log(f"Start: wyprawy do wznowienia brak ({opis}).")
        return False
    stop, n = za_wiele_prob(st, teraz_w)
    if stop:
        log(f"Start: wyprawa przerwana ({opis}), ale to już {n}. wznowienie w ciągu "
            f"{WZNOW_START_OKNO_S // 60} min (zacięcie się powtarza): NIE wznawiam, dojście jak dotąd.")
        return False
    aktualny, ptxt = powod_aktualny(wyprawa, st)
    if not aktualny:
        log(f"Start: wyprawa przerwana ({opis}), ale {ptxt}: nie wznawiam.")
        return False
    log(f"Start: wyprawa przerwana ({opis}), {ptxt}. Wznawiam od bieżącej pozycji, bez dojścia na spot.")
    przed = {k: st.get(k) for k in ("aktywna", "przerwana", "nast_wall", "t_wall", "wznow_start")}
    wyprawa._stan_zapisz(aktywna=True, przerwana=False, nast_wall=0, t_wall=teraz_w, zapis_wall=teraz_w,
                         wznow_start={"n": n + 1, "t": teraz_w, "rodzaj": rodzaj})
    wyprawa._wznowiono = True              # pierwszy obieg nie powtarza wznowienia
    try:
        ok = bool(wyprawa._wznow(wyprawa.cb.zegar()))
    except Exception as e:                 # noqa: BLE001  (wyjątek zostaje w Zatrzymano, reszta = stara ścieżka)
        import bot  # noqa: PLC0415
        if isinstance(e, bot.Zatrzymano):
            raise
        log(f"Start: wznowienie wyprawy nie powiodło się ({e!r}), dojście jak dotąd.")
        ok = False
    if not ok:
        # _wznow zapisał własny wynik (poza_planem / nie_wznowiona / powod_ustal); karencja z błędu wraca
        wyprawa._stan_zapisz(nast_wall=przed["nast_wall"] or 0)
        log("Start: wyprawy nie da się wznowić z bieżącej pozycji, dojście i spot jak dotąd.")
    return ok
