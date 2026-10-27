#!/usr/bin/env python3
"""Raport spotkań z obcymi graczami na spocie, liczony Z TELEMETRII (tylko ODCZYT; nic nie zapisuje, nie dotyka gry ani botów). 26.10, Karol.

  python3 -I narzedzia/spotkania_graczy_raport.py                    # od ostatniego startu bota (ostatnia `sesja` w telemetrii), wszystkie instancje
  python3 -I narzedzia/spotkania_graczy_raport.py --dzien 20261025   # cały dzień RRRRMMDD
  python3 -I narzedzia/spotkania_graczy_raport.py --instancja gerbor --json

DWA liczniki spotkań (zmiana Karola 26.10, tylko wyświetlanie; bot i `spot_gracz.Licznik` bez zmian):
  * `spotkan` / `nicki` / `spotkan_na_h` = spotkanie BEZ minimalnego czasu widoku: obcy nick (`gracz:true` w `stwory`) w >= 1 próbce „na spocie” otwiera epizod; następny epizod tego
    samego nicku po >= PRZERWA_S (300 s) bez niego. Krótkie mijanie (3-8 s) to spotkanie. To pokazuje okno jako „spotkań”.
  * `spotkan_prog15` / `nicki_prog15` = reguły bota (spot_gracz.Licznik; `SPOT_ZMIANA_PRZY_GRACZU`): nick widoczny łącznie >= MIN_WIDOK_S (od 27.10: 3 s, Karol; do 27.10 15 s) w jednym epizodzie, następne po
    >= PRZERWA_S (300 s). To licznik decyzyjny (n/PRÓG), zostaje do porównania. `--min-widok` zmienia tylko ten drugi.
    UWAGA: nazwa `*_prog15` jest historyczna (pierwotny próg 15 s) i zostaje, bo czytają ją okno (spotkania_okno.py) i testy; wartość progu to zawsze SG.MIN_WIDOK_S.
Oba liczą tylko, gdy postać jest „na spocie”, w zakresie raportu (domyślnie ostatnia sesja bota), z tymi samymi filtrami.
Nie liczą się: nasze postacie (instancje/*/profil.json `postac` + lista znanych), własny nick, HP <= 0, GM, wpisy z czaszką/PK (jeśli telemetria je niesie).
Nie filtruję NPC (na spocie ich nie ma) ani wrogów z wrogowie.json (telemetria nie niesie listy wrogów; bot ich pomija, więc raport może ich liczyć więcej).

„Na spocie / w trakcie expienia” (jedno kryterium dla pętli i patrolu, bez geometrii trasy) — próbka telemetrii liczy się, gdy:
  * `stan` bota to nie WYPAD (marsz do depo/serwis), WPADNIECIE (odzyskiwanie po spadku), PAUZA_STOJ/STOJ_POWROT (stanowisko), WYLOGUJ_OBCY ani brak stanu;
  * próbka nie leży w DOJŚCIU na spot: sesja bota (`logi/mozg-stdout-MMDD-GGMM.log`) ma wpis „Dojście: trasa …”, a „Dojście zakończone” jeszcze nie padło
    (brak zakończenia = cała reszta sesji to dojście; sesja bez „Dojście:” = bot od razu na spocie);
  * próbki starsze niż początek pierwszego logu w oknie nie mają sesji: liczą się bez sprawdzania dojścia (granica danych, opisana w wyniku).
Dlaczego nie geometria (odległość od punktów pętli): Pomszta 26.10 miała w tryb.log i `Mózg:` trasę `rook_raty_z8_petla` (491 pkt, z8 x 32022..32116, y 32190..32234),
ale cały dzień expiła w kieszeni obok (x 32011..32035, y 161..171; 7794 z 9517 próbek <= 8 pól od `rook_raty_z8_kieszen_petla`, tylko 4 próbki <= 8 pól od jej własnej
pętli): trasa z logu nie opisuje miejsca expienia, a patrol (`patrol:troll`) nie ma pętli wcale. Granica: czas „na spocie” zawiera też marsz między celami po zakończonym dojściu
i okresy po spadku na inne piętro, o ile bot nie zgłosił WPADNIECIE.

„Widziani” (26.10, Karol: NOWY licznik obok „spotkań”): liczba RÓŻNYCH obcych graczy, którzy byli w zasięgu wzroku przynajmniej w JEDNEJ próbce telemetrii (bez progu
widoku i bez przerwy 5 min), liczona OD WEJŚCIA NA OBECNY SPOT, czyli od `instancje/<id>/ostatnie.json` `na_spocie_od` (zapisuje je ostatnie.py: czas pierwszej próbki po zmianie
`mapa`; restart bota na tej samej mapie w < 180 s bez przerwy w grze go nie zeruje, dłuższa przerwa albo koniec sesji tak). Te same filtry co „graczy”/„spotkań”
(`_widoczni_obcy`: bez własnego nicku, naszych postaci, GM, czaszek/pk, hp <= 0) i to samo kryterium „na spocie” (`_na_spocie`: STANY_POZA_SPOTEM + okna dojścia), ale okres
obejmuje WSZYSTKIE sesje bota od `na_spocie_od` (nie tylko ostatnią), więc może być większy niż „graczy”. Brak/nieprawidłowe `na_spocie_od` = `widziani: None` + `widziani_powod`.
Pola: `widziani`, `widziani_od`, `widziani_lista` [{nick, probek, pierwszy_t, ostatnio_t}] (najczęściej widziani pierwsi), `widziani_uwaga`. Z `--dzien` nie liczone (None).

Wyjście: tabela (instancja, postać, czas na spocie, graczy, widziani, spotkań, spotkań/h, spotk. >= MIN_WIDOK_S s, najczęstsi) albo `--json`."""
import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent.parent
if str(KAT) not in sys.path:
    sys.path.insert(0, str(KAT))
import spot_gracz as SG  # noqa: E402

STANY_POZA_SPOTEM = {"WYPAD", "WPADNIECIE", "PAUZA_STOJ", "STOJ_POWROT", "WYLOGUJ_OBCY", None}
RE_LOG = re.compile(r"mozg-stdout-(\d{2})(\d{2})-(\d{2})(\d{2})\.log$")
RE_GODZ = re.compile(r"^(\d\d):(\d\d):(\d\d) (.*)$")
GM = re.compile(r"^(gm|cm|god|tutor)\s|\[gm\]|\[cm\]", re.IGNORECASE)


def probki(plik):
    """Generator próbek telemetrii (typ == "probka") z pliku jsonl; uszkodzone linie pomijane."""
    try:
        f = open(plik, encoding="utf-8", errors="replace")
    except OSError:
        return
    with f:
        for l in f:
            if '"probka"' not in l:
                continue
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if r.get("typ") == "probka" and isinstance(r.get("t"), (int, float)) and isinstance(r.get("poz"), list):
                yield r


def okna_dojscia(kat_logi, rok):
    """[(start_logu, koniec_dojscia | None, koniec_logu_przyblizony)] dla każdej sesji bota z `logi/mozg-stdout-*.log`. `koniec_dojscia` None = sesja bez
    dojścia (bot od razu na spocie) -> okno dojścia puste; (start, inf) przez konwencję poniżej: dojście bez zakończenia trwa do końca sesji."""
    wynik = []
    for p in sorted(Path(kat_logi).glob("mozg-stdout-*.log")):
        m = RE_LOG.search(p.name)
        if not m:
            continue
        mies, dzien, g, mi = (int(x) for x in m.groups())
        try:
            start = datetime(rok, mies, dzien, g, mi).timestamp()
        except ValueError:
            continue
        dojscie, koniec_doj, ost = False, None, None
        try:
            tekst = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        dzien_log = datetime(rok, mies, dzien)
        poprz = -1
        for l in tekst:
            mm = RE_GODZ.match(l)
            if not mm:
                continue
            h, mn, sc, reszta = int(mm.group(1)), int(mm.group(2)), int(mm.group(3)), mm.group(4)
            sek = h * 3600 + mn * 60 + sc
            if sek < poprz - 3600:                  # północ: kolejny dzień
                dzien_log += timedelta(days=1)
            poprz = max(poprz, sek) if sek >= poprz - 3600 else sek
            t = (dzien_log + timedelta(seconds=sek)).timestamp()
            ost = t
            if reszta.startswith("Dojście: trasa"):
                dojscie = True
            elif dojscie and koniec_doj is None and reszta.startswith("Dojście zakończone"):
                koniec_doj = t
        wynik.append({"start": start, "dojscie": dojscie, "koniec_dojscia": koniec_doj, "koniec_logu": ost})
    return wynik


def w_dojsciu(t, okna):
    """Czy czas t leży w dojściu na spot: ostatni log, który wystartował przed t, miał dojście i jeszcze go nie zakończył. Brak logu przed t = nie wiadomo (False)."""
    ost = None
    for o in okna:
        if o["start"] <= t + 60:                    # nazwa logu ma dokładność do minuty
            ost = o
        else:
            break
    if ost is None or not ost["dojscie"]:
        return False
    return ost["koniec_dojscia"] is None or t < ost["koniec_dojscia"]


def nasze_nicki_instancji(korzen):
    return SG.nasze_nicki(Path(korzen) / "instancje")


def _na_spocie(r, okna):
    """Czy próbka liczy się jako „na spocie” (jedno kryterium dla `licz` i `licz_widzianych`): stan nie poza spotem i czas nie w dojściu."""
    return r.get("stan") not in STANY_POZA_SPOTEM and not w_dojsciu(float(r["t"]), okna)


def _widoczni_obcy(r, nasze, wlasny_k):
    """Nicki obcych graczy w próbce po wszystkich filtrach (własny nick, nasze postacie, GM, czaszka/PK, hp <= 0). Jedyne miejsce tych reguł."""
    widoczni = []
    for s in r.get("stwory") or ():
        if not isinstance(s, dict) or not s.get("gracz"):
            continue
        n = str(s.get("n") or "")
        k = SG.klucz(n)
        hp = s.get("hp")
        if not k or k == wlasny_k or k in nasze or GM.search(n) or s.get("czaszka") or s.get("skull") or s.get("pk"):
            continue
        if isinstance(hp, (int, float)) and not isinstance(hp, bool) and hp <= 0:
            continue
        widoczni.append(n)
    return widoczni


def licz(probki_lista, okna, nasze, wlasny, ostatnia_sesja_tylko=False):
    """Przepuszcza próbki przez TEN SAM licznik co bot. -> słownik z wynikiem. `probki_lista` posortowane po t."""
    lic = SG.Licznik(None, 0.0)
    wlasny_k = SG.klucz(wlasny)
    spotkania = Counter()           # reguły bota (próg widoku MIN_WIDOK_S): `spotkan_prog15`
    epizody = Counter()             # bez progu widoku (1 próbka wystarczy): `spotkan`
    ost_epizod, nazwa_epizod = {}, {}
    gracze = set()
    czas_spot = 0.0
    n_spot = n_razem = 0
    poprz_t = None
    od = do = None
    for r in probki_lista:
        n_razem += 1
        t = float(r["t"])
        od = t if od is None else od
        do = t
        aktywny = _na_spocie(r, okna)
        widoczni = _widoczni_obcy(r, nasze, wlasny_k) if aktywny else []
        if aktywny:
            n_spot += 1
            if poprz_t is not None and 0 < t - poprz_t <= SG.MAX_KROK_S:
                czas_spot += t - poprz_t
            gracze.update(SG.klucz(x) for x in widoczni)
            for x in widoczni:                      # epizod bez progu: pierwszy widok albo przerwa >= PRZERWA_S (jak w Licznik: też cofnięty zegar o > 60 s)
                k = SG.klucz(x)
                ost = ost_epizod.get(k)
                if ost is None or t - ost >= SG.PRZERWA_S or t < ost - 60:
                    epizody[k] += 1
                    nazwa_epizod[k] = str(x).strip()
                ost_epizod[k] = t
        for nick in lic.obserwuj(t, widoczni, aktywny):
            spotkania[nick] += 1
        poprz_t = t if aktywny else None
    h = czas_spot / 3600.0
    razem15 = sum(spotkania.values())
    razem = sum(epizody.values())
    ost = max(lic.gracze.values(), key=lambda e: e["ostatnio_t"], default=None)     # 26.10 (okno): ostatnio widziany gracz (tylko dodatkowe pole wyniku)
    return {"od": od, "do": do, "probek": n_razem, "probek_na_spocie": n_spot, "czas_na_spocie_h": round(h, 3), "graczy": len(gracze),
            "spotkan": razem, "spotkan_na_h": round(razem / h, 2) if h > 0 else None,
            "nicki": sorted(((nazwa_epizod[k], c) for k, c in epizody.items()), key=lambda kv: (-kv[1], kv[0])),
            "spotkan_prog15": razem15, "spotkan_prog15_na_h": round(razem15 / h, 2) if h > 0 else None,
            "nicki_prog15": sorted(spotkania.items(), key=lambda kv: (-kv[1], kv[0])),
            "ostatni": {"nick": ost["nick"], "t": ost["ostatnio_t"]} if ost else None}


def licz_widzianych(probki_lista, okna, nasze, wlasny, od_t):
    """„Widziani” (26.10): różni obcy gracze widoczni w >= 1 próbce `na spocie` od czasu `od_t` (epoch; próbki wcześniejsze pomijane). Bez progów licznika bota,
    te same filtry i kryterium „na spocie” co `licz`. -> {"widziani": int, "lista": [{nick, probek, pierwszy_t, ostatnio_t}], "probek_na_spocie": int}."""
    wlasny_k = SG.klucz(wlasny)
    wpisy = {}
    n_spot = 0
    for r in probki_lista:
        t = float(r["t"])
        if t < od_t or not _na_spocie(r, okna):
            continue
        n_spot += 1
        for nick in _widoczni_obcy(r, nasze, wlasny_k):
            k = SG.klucz(nick)
            e = wpisy.get(k)
            if e is None:
                wpisy[k] = {"nick": nick.strip(), "probek": 1, "pierwszy_t": t, "ostatnio_t": t}
            else:
                e["probek"] += 1
                e["ostatnio_t"] = t
    lista = sorted(wpisy.values(), key=lambda e: (-e["probek"], e["nick"].lower()))
    return {"widziani": len(lista), "lista": lista, "probek_na_spocie": n_spot}


def na_spocie_od(kat_instancji):
    """`na_spocie_od` z ostatnie.json instancji (epoch) albo None (brak pliku/pola/zła wartość)."""
    try:
        j = json.loads((Path(kat_instancji) / "ostatnie.json").read_text(encoding="utf-8"))
        v = j.get("na_spocie_od")
        ses = (j.get("sesja") or {}).get("start")
    except (OSError, ValueError, AttributeError):
        return None
    if not (isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0):
        return None
    if isinstance(ses, (int, float)) and not isinstance(ses, bool) and v < ses:
        return float(ses)                           # 27.10: spot nie zaczął się przed wejściem do gry (stare `na_spocie_od` z wczoraj)
    return float(v)


def pliki_telemetrii(kat_logi, dzien=None, od_t=None):
    kat_logi = Path(kat_logi)
    if dzien:
        p = kat_logi / f"telemetria-{dzien}.jsonl"
        return [p] if p.is_file() else []
    wsz = sorted(kat_logi.glob("telemetria-*.jsonl"))
    if od_t is not None:                            # 26.10: „widziani” od wejścia na spot: także pliki od dnia `od_t`, jeśli starsze niż dwa ostatnie
        pocz = f"telemetria-{datetime.fromtimestamp(od_t):%Y%m%d}.jsonl"
        return sorted(set(wsz[-2:]) | {p for p in wsz if p.name >= pocz})
    return wsz[-2:]                                 # ostatni dzień i poprzedni (sesja może trwać przez północ)


def widziani_pola(wszystkie, okna, nasze, postac, od_spotu, dzien):
    """Pola „widziani” wyniku `raport_instancji` (zawsze obecne: `widziani` None + `widziani_powod`, gdy nie da się policzyć)."""
    puste = {"widziani": None, "widziani_od": od_spotu, "widziani_lista": [], "widziani_uwaga": None}
    if dzien:
        return {**puste, "widziani_powod": "tryb --dzien: widziani liczymy od wejścia na obecny spot"}
    if od_spotu is None:
        return {**puste, "widziani_powod": "brak początku huntu (ostatnie.json bez na_spocie_od)"}
    if od_spotu > wszystkie[-1]["t"] + 60:
        return {**puste, "widziani_powod": "początek huntu w przyszłości względem telemetrii"}
    w = licz_widzianych(wszystkie, okna, nasze, postac, od_spotu)
    uwaga = None
    if wszystkie[0]["t"] > od_spotu + 60:
        uwaga = f"telemetria zaczyna się {datetime.fromtimestamp(wszystkie[0]['t']):%d.%m %H:%M}, po wejściu na spot ({datetime.fromtimestamp(od_spotu):%d.%m %H:%M})"
    elif not okna or okna[0]["start"] > od_spotu + 60:
        uwaga = "wejście na spot przed najstarszym logiem sesji: dojście niesprawdzone"
    return {"widziani": w["widziani"], "widziani_od": od_spotu, "widziani_lista": w["lista"], "widziani_uwaga": uwaga, "widziani_powod": None,
            "widziani_probek_na_spocie": w["probek_na_spocie"]}


def raport_instancji(korzen, id_, dzien=None):
    kat = Path(korzen) / "instancje" / id_
    try:
        postac = (json.loads((kat / "profil.json").read_text(encoding="utf-8")).get("postac") or "").strip()
    except (OSError, ValueError, AttributeError):
        postac = ""
    od_spotu = None if dzien else na_spocie_od(kat)            # 26.10: początek huntu dla „widziani” (None = niedostępne)
    pliki = pliki_telemetrii(kat / "logi", dzien, od_spotu)
    if not pliki:
        return {"instancja": id_, "postac": postac, "blad": "brak telemetrii"}
    lista = [r for p in pliki for r in probki(p) if r.get("src", "mozg") == "mozg"]
    lista.sort(key=lambda r: r["t"])
    if not lista:
        return {"instancja": id_, "postac": postac, "blad": "brak próbek"}
    tryb = "dzień " + dzien if dzien else "od ostatniego startu"
    wszystkie = lista                                           # wszystkie sesje z wczytanych plików (dla „widziani”)
    if not dzien:
        ses = lista[-1].get("sesja")
        lista = [r for r in lista if r.get("sesja") == ses]
        # sesja ciągnie się od pierwszej próbki z tą wartością; przy braku klucza `sesja` cały zakres
    rok = datetime.fromtimestamp(wszystkie[0]["t"]).year
    okna = okna_dojscia(kat / "logi", rok)
    nasze = nasze_nicki_instancji(korzen)
    wyn = licz(lista, okna, nasze, postac)
    wyn.update(widziani_pola(wszystkie, okna, nasze, postac, od_spotu, dzien))
    wyn.update({"instancja": id_, "postac": postac, "zakres": tryb})
    if not dzien:                                   # 26.10 (okno): która sesja bota i który proces (do sprawdzenia „to bieżąca sesja”)
        wyn["sesja"], wyn["pid"] = lista[-1].get("sesja"), lista[-1].get("pid")
    if lista and (not okna or okna[0]["start"] > lista[0]["t"] + 60):
        wyn["uwaga"] = "początek zakresu przed najstarszym logiem sesji: dojście niesprawdzone"
    return wyn


def instancje(korzen, tylko=None):
    kat = Path(korzen) / "instancje"
    wynik = []
    for p in sorted(kat.iterdir()) if kat.is_dir() else []:
        if p.name.startswith("_") or not (p / "logi").is_dir():
            continue
        if tylko and p.name != tylko:
            continue
        wynik.append(p.name)
    return wynik


def tabela(wiersze):
    nagl = ("instancja", "postać", "okres", "na spocie", "graczy", "widziani", "spotkań", "spotk./h", f"≥{SG.MIN_WIDOK_S:g} s", "najczęstsi")
    out = [nagl]
    for w in wiersze:
        if w.get("blad"):
            out.append((w["instancja"], w.get("postac", ""), "-", "-", "-", "-", "-", "-", "-", w["blad"]))
            continue
        top = ", ".join(f"{n} {c}" for n, c in w["nicki"][:5]) or "-"
        okres = f"{datetime.fromtimestamp(w['od']):%d.%m %H:%M}-{datetime.fromtimestamp(w['do']):%H:%M}" if w.get("od") and w.get("do") else "-"
        out.append((w["instancja"], w.get("postac", ""), okres, f"{w['czas_na_spocie_h']:.2f} h", str(w["graczy"]),
                    "-" if w.get("widziani") is None else str(w["widziani"]), str(w["spotkan"]),
                    "-" if w["spotkan_na_h"] is None else f"{w['spotkan_na_h']:.2f}", str(w["spotkan_prog15"]), top + (f"  [{w['uwaga']}]" if w.get("uwaga") else "")))
    szer = [max(len(r[i]) for r in out) for i in range(len(nagl) - 1)]
    return "\n".join("  ".join(c.ljust(szer[i]) if i < len(szer) else c for i, c in enumerate(r)) for r in out)


def main(argv=None):
    a = argparse.ArgumentParser(description="Raport spotkań z graczami z telemetrii (tylko odczyt)")
    a.add_argument("--dzien", help="RRRRMMDD: cały dzień (domyślnie: od ostatniego startu bota)")
    a.add_argument("--od-startu", action="store_true", help="od ostatniego startu bota (ostatnia `sesja` w telemetrii; domyślne)")
    a.add_argument("--instancja", help="tylko ta instancja")
    a.add_argument("--json", action="store_true")
    a.add_argument("--min-widok", type=float, help=f"próg widoku w epizodzie w s (domyślnie {SG.MIN_WIDOK_S:g} jak w bocie; do analiz czułości)")
    a.add_argument("--przerwa", type=float, help=f"przerwa kończąca epizod w s (domyślnie {SG.PRZERWA_S:g} jak w bocie)")
    a.add_argument("--korzen", default=str(KAT), help="katalog bota (testy: katalog z fixture)")
    o = a.parse_args(argv)
    if o.dzien and not re.fullmatch(r"\d{8}", o.dzien):
        a.error("--dzien: RRRRMMDD")
    if o.min_widok is not None:
        SG.MIN_WIDOK_S = o.min_widok
    if o.przerwa is not None:
        SG.PRZERWA_S = o.przerwa
    wiersze = [raport_instancji(o.korzen, i, o.dzien) for i in instancje(o.korzen, o.instancja)]
    if o.json:
        print(json.dumps(wiersze, ensure_ascii=False, indent=1))
    else:
        print(tabela(wiersze))
    return 0


if __name__ == "__main__":
    sys.exit(main())
