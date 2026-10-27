#!/usr/bin/env python3
"""Blanki do pojemnika na runy zaraz po starcie bota (27.10, Karol: „dopiszmy to, żebym nie musiał tego robić”; spec N9a w
`dane_tibia/SPEC_naprawy_1014.md`).

PROBLEM: blanki z zakupów poza pełną wyprawą albo po relogu zostają w GŁÓWNYM plecaku łupu i zajmują miejsce na łup.
Do pojemnika na runy (drugi bag tylko z runami) przenosi je krok wyprawy `przenies_runy`, okresowy `Wyprawa._blanki_auto`
(pokrętło `BLANKI_AUTO_BAG`, start + co 10 min w spokoju; u marianni, gerbora i odchyda wyłączone w szablonie „nowa postać”)
albo ręcznie `przenies_runy.py`. Ten moduł dodaje JEDNĄ próbę na start procesu bota, PRZED wznowieniem wyprawy i dojściem
(hook w `mozg.main` zaraz po `okna_start.przy_starcie`), niezależnie od `BLANKI_AUTO_BAG` i od wyprawy.

CO ROBI: decyzje WYŁĄCZNIE z pamięci klienta (kontenery: pojemność, sloty, ID, rola z położenia okna; zero zrzutów, zero klików) -> jeśli wszystkie warunki naraz, woła ISTNIEJĄCE `loot.przenies_do_runow`
(jedyny mechanizm przeciągania; limit 30 przeciągnięć, weryfikacja w pamięci po każdym). Warunki (inaczej jedna linia logu z powodem
i zero klików):
  (a) robimy runy: `UH_AKTYWNY` = 1 w na_zywo.json instancji (czytane przy starcie, jak `wznow_start.pokretlo`: hook działa przed
      budową cavebota; postać bez run nie ma pojemnika na runy);
  (b) pamięć klienta pokazuje OBA okna: główny plecak i pojemnik na runy (z kontenerem, nie samo rozpoznanie obrazu);
  (c) w głównym plecaku jest co najmniej 1 widoczna runa/blank (ID z `loot.ID_RUN_W_POJEMNIKU`: blank, HMM, UH, SD, GFB, explosion, IH);
  (d) w pojemniku na runy jest wolne pole (pojemność minus zajęte sloty z pamięci; pełny, np. 20/20 = jedna linia „brak wolnego
      pola (N/M), zostawiam”, bez zrzutu i prób przeciągania). Czy wolny slot jest WIDOCZNY (okno nie ucięte oknem zwłok/panelem) sprawdza
      dopiero `loot.przenies_do_runow` na zrzucie: ekran służy tylko do współrzędnych slotów i tej kontroli;
  (e) brak STOP i STOP_RECZNY, w widoku (to samo piętro, +-8 x +-6 pól) nie ma żywego potwora ani cudzego gracza; przy zagrożeniu
      czeka do `CZEKAJ_S` (5 s) i rezygnuje z logiem. Moduł niczego nie robi, gdy bot jest w trybie --bez-ruchu.
Najwyżej raz na proces (flaga `_URUCHOMIONO`); wyjątek w środku nigdy nie przerywa startu (STOP/`bot.Zatrzymano` przechodzi).

WYŁĄCZNIKI (domyślnie WŁĄCZONE; spójnie z `okna_start.py`, nadzorca z timera nie dziedziczy env, więc plik):
  RETRONIC_BLANKI_START=0           środowisko startu bota
  instancje/<id>/BLANKI_START_OFF   tylko ta instancja (plik pusty wystarcza)
  instancje/_wspolne/BLANKI_START_OFF  wszystkie instancje
Dowód w logu bota: `Blanki na starcie: przeniesiono N` albo `Blanki na starcie: pominięto (powód)`.

UKŁAD „DWA OKNA RUN” (odchyd 27.10): po ręcznym refillu plecak łupu (Blue backpack) jest w ~80% z blankami i `loot.czy_runy` (reguła
15.10: runy >= 3 i >= 75% zawartości) uznaje OBA okna za pojemniki na runy -> `loot.plan`: plecak None, `okna_start`: plecaki 0 / runy 2
(brak_plecaka), UH i loot kończą się `brak_plecaka`. `rozstrzygnij_dwa_runy` wskazuje plecak łupu TYLKO wtedy, gdy dokładnie jedno
z dwóch okien ma przedmioty inne niż runy/tarcze/monety (i nie jest Purple backpack z nazwy/ID); inaczej nic nie robi i podaje powód.
Klasyfikator ogólny (`loot.czy_runy`/`_plan_z_pamieci`) NIE jest zmieniany: rozstrzygnięcie dotyczy tylko przenoszenia blanków
(`loot.przenies_do_runow(plan_fn=...)`, jedyna zmiana w loot.py: opcjonalny argument).

DRUGI WYZWALACZ (w trakcie pracy, 27.10): `zglos(powod)` wołane z cavebota, gdy UH kończy `brak_plecaka (zero lub kilka okien plecaka)`
albo loot zwraca `brak_plecaka`; `naprawa_w_trakcie` (cavebot._blanki_naprawa_tick, w spokoju, bez walki/lootu/wyprawy/obcych) robi
TĘ SAMĄ naprawę. Limity: najwyżej raz na 10 min (po chwilowej rezygnacji: 30 s), najwyżej 3 prawdziwe próby na proces, potem jedna linia
`naprawa układu nieudana: <powód>` i jedno powiadomienie; bez pętli. Ten sam wyłącznik wyłącza oba wyzwalacze.
Test: `python3 testy/test_blanki_start.py`. Cofnięcie: `*.bak-20261027-blanki-start` albo wyłącznik."""
import json
import os
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import instancja  # noqa: E402

POKRETLO_RUNY = "UH_AKTYWNY"
PLIK_WYLACZNIKA = "BLANKI_START_OFF"
CZEKAJ_S = 5.0                      # tyle czekamy na ustąpienie potwora/gracza w widoku, potem rezygnacja
KROK_CZEKANIA_S = 1.0
ZASIEG_X, ZASIEG_Y = 8, 6           # „w widoku”: ekran gry 15x11 pól (+-7 x +-5) z zapasem 1
MAKS_PRZECIAGNIEC = 30              # jak `loot.przenies_do_runow` dziś

_URUCHOMIONO = False                # najwyżej raz na proces


def _przepusc_stop(e):
    """Plik STOP (bot.Zatrzymano) przerywa także ten moduł: nie połykamy go jak zwykłego błędu."""
    if type(e).__name__ == "Zatrzymano":
        raise e


# --- wyłączniki i pokrętło -------------------------------------------------------------------------------

def wylaczony(env=None, stan=None, wspolne=None):
    """Powód wyłączenia (tekst) albo None: env RETRONIC_BLANKI_START=0, plik BLANKI_START_OFF instancji albo wspólny."""
    env = os.environ if env is None else env
    if (env.get("RETRONIC_BLANKI_START", "1") or "1").strip() == "0":
        return "RETRONIC_BLANKI_START=0"
    stan = Path(stan) if stan else Path(instancja.S.stan)
    wspolne = Path(wspolne) if wspolne else Path(instancja.S.wspolne)
    for katalog in (stan, wspolne):
        if (katalog / PLIK_WYLACZNIKA).exists():
            return f"plik {katalog / PLIK_WYLACZNIKA}"
    return None


def robi_runy(plik=None):
    """True, gdy UH_AKTYWNY = 1 w na_zywo.json instancji (brak pliku/klucza, zły typ lub wartość poza zakresem = 0)."""
    import pokretla  # noqa: PLC0415
    try:
        dane = json.loads(Path(pokretla.PLIK if plik is None else plik).read_text())
    except (OSError, ValueError):
        return False
    if not isinstance(dane, dict) or POKRETLO_RUNY not in dane:
        return False
    ok, _ = pokretla.waliduj({POKRETLO_RUNY: dane[POKRETLO_RUNY]})
    return ok.get(POKRETLO_RUNY) == 1


# --- czyste: rozstrzygnięcie „dwa okna run” i ocena odczytu --------------------------------------------------

def _inne_przedmioty(kontener):
    """Przedmioty INNE niż runy/blanki, tarcze odłożone na czas runy i monety (to one czynią z okna plecak łupu)."""
    import loot  # noqa: PLC0415
    obce = loot.ID_RUN_W_POJEMNIKU | loot.ID_TARCZ_W_POJEMNIKU | loot.ID_MONET_W_POJEMNIKU
    return [q for q in kontener.get("przedmioty", []) if q.get("id") not in obce]


def _runy_z_nazwy(kontener):
    """True, gdy okno jest pojemnikiem na runy z ID/nazwy (Purple backpack), nie z zawartości: nigdy nie jest plecakiem łupu."""
    import loot  # noqa: PLC0415
    return bool(kontener.get("id") in loot.ID_POJEMNIKOW_RUN
                or (kontener.get("nazwa") or "").casefold().startswith(loot.NAZWY_POJEMNIKOW_RUN))


def rozstrzygnij_dwa_runy(plan):
    """Układ z odchyd 27.10: `loot.plan` uznał OBA okna za runy (plecak łupu w >= 75% z blankami) i nie ma plecaka. Zwraca KOPIĘ planu
    z `plecak`/`runy` ustawionymi na podstawie przedmiotów innych niż runy/tarcze/monety, albo (gdy się nie da jednoznacznie)
    plan z kluczem `niejednoznaczne` (dokładny powód). Plan z plecakiem, z 0/1 oknem runy: bez zmian. Klucz `rozstrzygniecie` = opis wyboru."""
    plan = dict(plan or {})
    if plan.get("plecak") is not None:
        return plan
    okna = [o for o in plan.get("okna") or [] if getattr(o, "rola", None) == "runy" and getattr(o, "kontener", None) is not None]
    if len(okna) < 2:
        return plan
    if len(okna) > 2:
        plan["niejednoznaczne"] = f"{len(okna)} okna uznane za pojemniki na runy i brak plecaka: nie rozstrzygam"
        return plan
    inne = [len(_inne_przedmioty(o.kontener)) for o in okna]
    kandydaci = [i for i, o in enumerate(okna) if inne[i] > 0 and not _runy_z_nazwy(o.kontener)]
    if len(kandydaci) != 1:
        if not kandydaci:
            powod = "oba okna mają tylko runy/blanki/tarcze/monety albo są pojemnikami na runy z nazwy: nie wiem, które jest plecakiem łupu"
        else:
            powod = f"oba okna mają przedmioty inne niż runy (inne: {inne[0]} i {inne[1]}): nie wiem, które jest plecakiem łupu"
        plan["niejednoznaczne"] = f"dwa okna uznane za runy, brak plecaka; {powod}"
        return plan
    i = kandydaci[0]
    lup, runy = okna[i], okna[1 - i]
    plan["plecak"], plan["runy"] = lup, runy
    plan["rozstrzygniecie"] = (f"dwa okna uznane za runy: plecak łupu = kontener {lup.kontener.get('numer')} "
                               f"(przedmiotów innych niż runy: {inne[i]}), pojemnik na runy = kontener {runy.kontener.get('numer')}")
    return plan


def ocena(plan, ids):
    """Ocena planu `loot.plan` (po `rozstrzygnij_dwa_runy`). -> (kod, opis, dane). kod "ruszaj" albo powód pominięcia:
    "brak_plecaka", "brak_pojemnika", "brak_blankow", "brak_pola"; `dane` = {widoczne_blanki, zajete, pojemnosc, wolne}."""
    plecak, runy = (plan or {}).get("plecak"), (plan or {}).get("runy")
    if plecak is None or getattr(plecak, "kontener", None) is None:
        opis = "pamięć klienta nie pokazuje głównego plecaka (otwarte oba okna: plecak i pojemnik na runy)"
        if (plan or {}).get("niejednoznaczne"):
            opis = plan["niejednoznaczne"]
        return "brak_plecaka", opis, {}
    if runy is None or getattr(runy, "kontener", None) is None:
        return "brak_pojemnika", "pamięć klienta nie pokazuje pojemnika na runy (drugi bag z runami musi być otwarty)", {}
    widoczne = len(plecak.sloty)
    wszystkie = [q for q in plecak.kontener.get("przedmioty", []) if q.get("id") in ids]
    w_widoku = [q for q in wszystkie if q.get("slot", 10 ** 9) < widoczne]
    k = runy.kontener
    poj = int(k.get("pojemnosc", 0) or 0)
    zajete = {q.get("slot") for q in k.get("przedmioty", [])}
    wolne = [i for i in range(min(len(runy.sloty), poj)) if i not in zajete]
    dane = {"widoczne_blanki": len(w_widoku), "wszystkie_blanki": len(wszystkie), "zajete": len(k.get("przedmioty", [])),
            "pojemnosc": poj, "wolne": len(wolne)}
    if not w_widoku:
        if wszystkie:
            return "brak_blankow", f"blanki są w plecaku, ale poza widocznymi polami okna ({len(wszystkie)} poza widokiem)", dane
        return "brak_blankow", "w głównym plecaku nie ma blanków ani run", dane
    if not wolne:
        return "brak_pola", (f"brak wolnego pola w pojemniku na runy ({dane['zajete']}/{poj}), zostawiam"), dane
    return "ruszaj", f"{len(w_widoku)} blanków/run w plecaku, wolnych widocznych pól w pojemniku: {len(wolne)}", dane


def zagrozenia(lista, poz, nick, zasieg_x=ZASIEG_X, zasieg_y=ZASIEG_Y):
    """Opisy żywych potworów i cudzych graczy w widoku (to samo piętro, +-zasieg). Pusta lista = spokój.
    `lista`: wpisy rdzenia ("stwory": nazwa, x, y, z, hp, gracz); `poz`: (x, y, z); `nick`: własna nazwa (pomijana)."""
    wynik = []
    for s in lista or []:
        try:
            if s.get("hp", 100) <= 0:
                continue
            if s.get("gracz") and s.get("nazwa") == nick:
                continue
            if s.get("z") != poz[2] or abs(s["x"] - poz[0]) > zasieg_x or abs(s["y"] - poz[1]) > zasieg_y:
                continue
            wynik.append(f"{'gracz' if s.get('gracz') else 'potwór'} {s.get('nazwa', '?')}")
        except (KeyError, TypeError, AttributeError):
            continue
    return wynik


# --- odczyt i wykonanie (wstrzykiwane w testach) -----------------------------------------------------------

class _OknoPamieci:
    """Okno widziane TYLKO z pamięci klienta: kontener + założenie, że wszystkie sloty są widoczne (widoczność sprawdza dopiero
    `loot.przenies_do_runow` na zrzucie; tu nie robimy zrzutu)."""
    def __init__(self, kontener):
        import loot  # noqa: PLC0415
        self.kontener = kontener
        self.rola = loot.rola_kontenera(kontener)
        self.sloty = [None] * int(kontener.get("pojemnosc", 0) or 0)


def plan_z_kontenerow(kontenery):
    """Plan w kształcie `loot.plan` (plecak, runy, okna), ale wyłącznie z listy kontenerów z pamięci klienta: decyzja bez zrzutu ekranu.
    Role z `loot.rola_kontenera` (najpierw położenie okna, potem nazwa/ID/zawartość); plecak = ten z największą liczbą rzeczy
    (jak `loot._plan_z_pamieci`), runy = pierwszy pojemnik na runy."""
    import loot  # noqa: PLC0415
    okna = [_OknoPamieci(k) for k in kontenery or []]
    plecaki = sorted([o for o in okna if o.rola == "plecak"],
                     key=lambda o: (loot._wyglada_na_runy(o.kontener), -len(o.kontener.get("przedmioty", []))))
    runy = [o for o in okna if o.rola == "runy"]
    return {"plecak": plecaki[0] if plecaki else None, "runy": runy[0] if runy else None, "okna": okna}


def _plan_z_pamieci():
    """Odczyt TYLKO z pamięci klienta (bez zrzutu i bez myszy): `loot.kontenery_z_pamieci` -> plan_z_kontenerow."""
    import loot  # noqa: PLC0415
    kontenery, powod = loot.kontenery_z_pamieci()
    if kontenery is None:
        raise RuntimeError(f"pamięć klienta: {powod}")
    return plan_z_kontenerow(kontenery)


def _plan_rozstrzygniety(obraz, lista):
    """Podmiana `loot.plan` dla `loot.przenies_do_runow(plan_fn=...)`: ten sam plan + rozstrzygnięcie „dwa okna run”."""
    import loot  # noqa: PLC0415
    return rozstrzygnij_dwa_runy(loot.plan(obraz, lista))


def _przenies_domyslnie(ids, maks, log):
    import loot  # noqa: PLC0415
    return loot.przenies_do_runow(ids=ids, maks=maks, log=log, plan_fn=_plan_rozstrzygniety)


def _stwory_z_rdzenia(postac):
    import bot  # noqa: PLC0415
    lista = bot.zapytaj({"cmd": "stwory"})["stwory"]
    return lista, tuple(postac.pozycja()), getattr(postac, "nazwa", None)


def _stop_reczny():
    return Path(instancja.S.stop_reczny).exists()


def _stop_sprawdz():
    """True, gdy istnieje plik STOP (poza testami: jak `bot.sprawdz_stop`, tylko bez wyjątku, powód idzie do logu)."""
    import bot  # noqa: PLC0415
    return bool(bot.STOP.exists() and not os.environ.get("RETRONIC_TESTY"))


class Wynik(tuple):
    """(stan, opis, przeniesione) + `.przejsciowe`: pominięcie z powodu chwilowego (STOP, STOP_RECZNY, obcy/potwór w widoku, nieznany
    widok) nie liczy się jako próba naprawy w trakcie pracy."""
    def __new__(cls, stan, opis, n, przejsciowe=False):
        w = super().__new__(cls, (stan, opis, n))
        w.przejsciowe = przejsciowe
        return w

    stan = property(lambda s: s[0])
    opis = property(lambda s: s[1])
    n = property(lambda s: s[2])


def uruchom(postac=None, log=print, plan_fn=None, stwory_fn=None, przenies_fn=None, pauza=time.sleep, zegar=time.monotonic,
            stop_fn=None, stop_reczny_fn=None, uh_fn=None, ids=None, bez_ruchu=False, kiedy="na starcie", czekaj_s=None):
    """Jedna próba. -> Wynik(stan, opis, przeniesione): stan "przeniesiono" | "pominieto" | "blad". Wyjątek (poza STOP) -> "blad".
    Logi: `Blanki <kiedy>: przeniesiono N` albo `Blanki <kiedy>: pominięto (powód)`. `czekaj_s`: ile czekać na ustąpienie
    zagrożenia w widoku (domyślnie CZEKAJ_S; w trakcie pracy 0)."""
    import loot  # noqa: PLC0415
    ids = tuple(sorted(loot.ID_RUN_W_POJEMNIKU)) if ids is None else ids
    czekaj_s = CZEKAJ_S if czekaj_s is None else czekaj_s
    et = f"Blanki {kiedy}"

    def pomin(powod, przejsciowe=False):
        log(f"{et}: pominięto ({powod})")
        return Wynik("pominieto", powod, 0, przejsciowe)

    if bez_ruchu:
        return pomin("tryb --bez-ruchu")
    if (stop_fn or _stop_sprawdz)():
        return pomin("STOP", True)
    if (stop_reczny_fn or _stop_reczny)():
        return pomin("STOP_RECZNY: Karol gra sam", True)
    if not (uh_fn or robi_runy)():
        return pomin(f"postać nie robi run ({POKRETLO_RUNY} != 1): nie ma pojemnika na runy")
    try:
        plan = rozstrzygnij_dwa_runy((plan_fn or _plan_z_pamieci)())
    except Exception as e:      # noqa: BLE001
        _przepusc_stop(e)
        return pomin(f"odczyt nieudany ({type(e).__name__}: {e})")
    if plan.get("rozstrzygniecie"):
        log(f"{et}: {plan['rozstrzygniecie']}")
    kod, opis, dane = ocena(plan, set(ids))
    if kod == "brak_pola":
        log(f"przenoszenie blanków {kiedy}: {opis}")
        return Wynik("pominieto", opis, 0)
    if kod != "ruszaj":
        return pomin(opis)
    # (e) spokój w widoku: potwór albo cudzy gracz = czekamy chwilę (na starcie), potem rezygnacja (nie ruszamy myszą przy zagrożeniu)
    koniec = zegar() + czekaj_s
    while True:
        try:
            lista, poz, nick = (stwory_fn or (lambda: _stwory_z_rdzenia(postac)))()
        except Exception as e:      # noqa: BLE001
            _przepusc_stop(e)
            return pomin(f"nie znam widoku/pozycji ({type(e).__name__}: {e}), nie ruszam myszą", True)
        zagr = zagrozenia(lista, poz, nick)
        if not zagr:
            break
        if zegar() >= koniec:
            return pomin(f"w widoku: {', '.join(zagr[:3])}; po {czekaj_s:.0f} s nie ruszam myszą", True)
        pauza(KROK_CZEKANIA_S)
    try:
        if (stop_fn or _stop_sprawdz)():
            return pomin("STOP", True)
        n = przenies_fn(ids=ids, maks=MAKS_PRZECIAGNIEC, log=log) if przenies_fn else _przenies_domyslnie(ids, MAKS_PRZECIAGNIEC, log)
    except Exception as e:      # noqa: BLE001
        _przepusc_stop(e)
        log(f"{et}: przenoszenie nie wyszło ({type(e).__name__}: {e})")
        return Wynik("blad", str(e), 0)
    log(f"{et}: przeniesiono {n}" + (f" (w plecaku było {dane['widoczne_blanki']}, wolnych pól {dane['wolne']})" if n else ""))
    return Wynik("przeniesiono", f"przeniesiono {n}", n)


def przy_starcie(postac=None, log=print, bez_ruchu=False, **wstrzykniete):
    """Hook startu bota (mozg.main, zaraz po okna_start.przy_starcie, przed wznowieniem wyprawy i dojściem). Najwyżej raz na proces,
    nigdy nie rzuca (poza STOP). -> wynik uruchom() albo None (wyłączone / już było / testy)."""
    global _URUCHOMIONO
    wymus = wstrzykniete.pop("_wymus", False)       # tylko testy: hook mimo RETRONIC_TESTY
    if os.environ.get("RETRONIC_TESTY") and not wymus:
        return None
    if _URUCHOMIONO:
        return None
    _URUCHOMIONO = True
    try:
        powod = wylaczony()
        if powod:
            log(f"Blanki na starcie: wyłączone ({powod})")
            return None
        return uruchom(postac, log, bez_ruchu=bez_ruchu, **wstrzykniete)
    except Exception as e:      # noqa: BLE001  (start bota nie może się wywrócić na tej funkcji; STOP i Ctrl+C przechodzą)
        _przepusc_stop(e)
        log(f"Blanki na starcie: pominięto (wyjątek {type(e).__name__}: {e})")
        return None


# --- drugi wyzwalacz: naprawa układu W TRAKCIE pracy (UH/loot zgłaszają brak_plecaka) -------------------------------

ODSTEP_NAPRAWY_S = 600.0            # najwyżej raz na 10 min (prawdziwa próba)
ODSTEP_PO_PRZEJSCIOWYM_S = 30.0     # po chwilowej rezygnacji (obcy/potwór w widoku, STOP_RECZNY) ponowna próba najwcześniej za tyle
MAKS_PROB_NAPRAWY = 3               # prawdziwych prób na proces, potem tylko jedna linia + powiadomienie

_NAPRAWA = {"zgloszenie": None, "proby": 0, "blok_do": float("-inf"), "powiadomiono": False}


def _reset_naprawy():
    """Tylko testy: stan wyzwalacza z powrotem na zero."""
    global _URUCHOMIONO
    _URUCHOMIONO = False
    _NAPRAWA.update(zgloszenie=None, proby=0, blok_do=float("-inf"), powiadomiono=False)


def oczekuje():
    """True, gdy UH/loot zgłosiły brak_plecaka i naprawa czeka na spokój (tani test na każdy tick)."""
    return _NAPRAWA["zgloszenie"] is not None


def zglos(powod, teraz, uh_fn=None, wylaczony_fn=None, _wymus=False):
    """Zgłoszenie z cavebota (UH `brak_plecaka (zero lub kilka okien plecaka)` albo loot `brak_plecaka`). -> True, gdy zapisane do wykonania
    w spokoju. Odrzuca: wyłącznik (env/plik), postać bez run, limit (3 próby, odstęp 10 min / 30 s), zgłoszenie już czeka. Nigdy nie rzuca."""
    try:
        if os.environ.get("RETRONIC_TESTY") and not _wymus:       # testy cavebota nie uruchamiają naprawy układu okien
            return False
        if _NAPRAWA["zgloszenie"] is not None or _NAPRAWA["proby"] >= MAKS_PROB_NAPRAWY or teraz < _NAPRAWA["blok_do"]:
            return False
        if (wylaczony_fn or wylaczony)():
            return False
        if not (uh_fn or robi_runy)():
            return False
        _NAPRAWA["zgloszenie"] = (teraz, str(powod))
        return True
    except Exception:       # noqa: BLE001
        return False


def naprawa_w_trakcie(postac, log=print, teraz=None, powiadom_fn=None, **wstrzykniete):
    """Wykonuje zgłoszoną naprawę (wołać TYLKO w spokoju: cavebot._blanki_naprawa_tick). Ta sama funkcja co na starcie
    (`uruchom`, bez czekania na ustąpienie zagrożenia: obcy/potwór w widoku = rezygnacja i ponowna próba najwcześniej za 30 s).
    -> Wynik albo None (nic nie zgłoszono). Nigdy nie rzuca (poza STOP). Po 3 nieudanych próbach: jedna linia
    `naprawa układu nieudana: <powód>` i jedno powiadomienie."""
    zgl = _NAPRAWA["zgloszenie"]
    if zgl is None:
        return None
    _NAPRAWA["zgloszenie"] = None
    teraz = time.monotonic() if teraz is None else teraz
    try:
        w = uruchom(postac, log, kiedy="w trakcie pracy", czekaj_s=0.0, **wstrzykniete)
    except Exception as e:      # noqa: BLE001
        _przepusc_stop(e)
        log(f"Blanki w trakcie pracy: pominięto (wyjątek {type(e).__name__}: {e})")
        w = Wynik("blad", str(e), 0)
    if w.przejsciowe:
        _NAPRAWA["blok_do"] = teraz + ODSTEP_PO_PRZEJSCIOWYM_S
        return w
    _NAPRAWA["blok_do"] = teraz + ODSTEP_NAPRAWY_S
    if w.stan == "przeniesiono" and w.n > 0:
        _NAPRAWA["proby"] = 0
        log(f"Blanki w trakcie pracy: układ naprawiony (zgłoszenie: {zgl[1]}), następna naprawa najwcześniej za {ODSTEP_NAPRAWY_S / 60:.0f} min")
        return w
    _NAPRAWA["proby"] += 1
    if _NAPRAWA["proby"] >= MAKS_PROB_NAPRAWY:
        log(f"naprawa układu nieudana: {w.opis} (próby {_NAPRAWA['proby']}/{MAKS_PROB_NAPRAWY}, zgłoszenie: {zgl[1]}); nie ponawiam")
        if not _NAPRAWA["powiadomiono"]:
            _NAPRAWA["powiadomiono"] = True
            try:
                if powiadom_fn is None:
                    import powiadom as _p  # noqa: PLC0415
                    powiadom_fn = _p.powiadom
                kto = instancja.ID or "domyślna"
                powiadom_fn(f"Retronic [{kto}]: popraw okna", f"[{kto}] naprawa układu okien nieudana: {w.opis}. "
                            "Ustaw w głównym plecaku okno łupu, a drugie jako Purple backpack na runy.", "critical",
                            klucz=f"blanki-naprawa-{kto}")
            except Exception:       # noqa: BLE001
                pass
    return w


if __name__ == "__main__":
    print(__doc__)
