"""26.10: powrót do depo z nowych pięter z10 Edronu (trolle_edron_z10w, gobliny_edron_z10_zachod/wschod/poludnie): trasy `<plik>_do_depo` z
generuj_powroty_rodziny.py i ich wpisy w wyprawa.PLANY_PK["edron"|"gobliny_edron"]["wyjscia"]. Wzór: test_powroty_edron_z9.py.
Dane rzeczywiste: pętle, trasy, prawdziwa mapa i W.droga_do_depo. Jeśli wyprawa.py nie ma jeszcze wpisów, test dokłada je TYLKO w pamięci
(PROPOZYCJA), a gdy już są, sprawdza je jako wpisane. Nic nie trafia do gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa
import generuj_powroty_rodziny as R
import generuj_rodziny_pietra as GP
import wypad
import wyprawa as W

TRASY = Path(_R) / "trasy"
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test powrotów rodziny")
    sys.exit(0)


def wczytaj(nazwa):
    return [tuple(int(v) for v in p) for p in json.loads((TRASY / nazwa).read_text())]


MAPA = _mapa.Mapa()
T = W.Trasownik(MAPA)
DEPO = (33173, 31796, 8)
OGIEN_BUF = GP.ogien_pola()
OGIEN = set()                                       # sam ogień, bez bufora (jak w test_powroty_edron_z9)
for f in ("ogien_stale.json", "ogien_epizody.json"):
    d = json.loads((TRASY / f).read_text())
    pola = d.get("pola") if isinstance(d, dict) else d
    for p in (pola if isinstance(pola, list) else pola.keys() if isinstance(pola, dict) else []):
        if isinstance(p, (list, tuple)) and len(p) >= 3:
            OGIEN.add(tuple(int(v) for v in p[:3]))
        elif isinstance(p, str) and p.count(",") == 2:
            OGIEN.add(tuple(int(a) for a in p.split(",")))


def zalew(a, cele):
    return T.zalew(a, cele, limit=W.DEPO_ZALEW_LIMIT)


def ciagla(pts):
    for a, b in zip(pts, pts[1:]):
        if a[2] == b[2] and wypad.cheb(a, b) > 5:
            return f"skok {a}->{b}"
        if a[2] != b[2] and wypad.cheb(a, b) > 3:
            return f"skok pięter {a}->{b}"
    return None


_STARE = W.PLANY_PK
try:
    for nazwa, (plan_nazwa, stoi9, lad8, kont, _a) in R.EXITY.items():
        spec = GP.SPECY[nazwa]
        w = R.zbuduj(nazwa, MAPA)
        wyj = R.wyjscie(nazwa, w)
        POLE, LAD9, plik_do, STOISKA = wyj
        petla = wczytaj(spec["plik"] + "_petla.json")
        plik = wczytaj(plik_do)
        kont = wczytaj(R.EXITY[nazwa][3] + ".json")
        PLAN = next(p for p in W.PLANY_PK if p["nazwa"] == plan_nazwa)
        DO = wczytaj(PLAN["do"])
        ISTNIEJACE = set(DO) | set(kont) | {q for x in PLAN["wyjscia"] if len(x) > 2 and x[2] for q in wczytaj(x[2])}
        wpisane = [x for x in PLAN["wyjscia"] if tuple(x[0]) == POLE]
        sprawdz(f"{nazwa}: plik trasy == generator", plik == [tuple(p) for p in w["pts"]], (len(plik), len(w["pts"])))
        if wpisane:
            sprawdz(f"{nazwa}: wpis w PLANY_PK[{plan_nazwa}] zgodny z generatorem", tuple(tuple(q) if isinstance(q, list) else q for q in wpisane[0][:3]) == wyj[:3], wpisane[0])
            wyjscia = tuple(PLAN["wyjscia"])
            print(f"   ({nazwa}: wpis jest już w wyprawa.py)")
        else:
            wyjscia = tuple(PLAN["wyjscia"]) + (wyj,)        # PROPOZYCJA, tylko w pamięci testu
            print(f"   ({nazwa}: PROPOZYCJA wpisu, w pamięci testu: {wyj})")

        # 1. bez wyjścia = brak drogi z pięter z10 (objaw, który naprawia wpis)
        stare = tuple(x for x in PLAN["wyjscia"] if tuple(x[0]) != POLE)           # plan bez wpisu tej mapy (także, gdy wpis już jest w wyprawa.py)
        sprawdz(f"{nazwa}: bez wyjścia brak drogi z {petla[0]}", W.droga_do_depo(petla[0], petla, DO, zalew, MAPA, wyjscia=stare) is None)

        # 2. z co 6. punktu pętli, z jej początku i końca
        dziura_z9 = spec["hops"][-1][0]                  # wejście na nią z9 = spadek z powrotem na z10
        for poz in [petla[0], petla[-1]] + petla[::6]:
            r = W.droga_do_depo(poz, petla, DO, zalew, MAPA, wyjscia=wyjscia)
            if r is None:
                sprawdz(f"{nazwa} z {poz}: droga", False, "brak drogi")
                continue
            pts = [tuple(q) for q in r[0]]
            zm = [(a, b) for a, b in zip(pts, pts[1:]) if a[2] != b[2]]
            sprawdz(f"{nazwa} z {poz}: koniec w depo", pts[-1] == DEPO, pts[-1])
            sprawdz(f"{nazwa} z {poz}: pierwsze przejście = lina stanie z10 -> {LAD9}", zm and zm[0][1] == LAD9 and zm[0][0] in STOISKA and zm[0][0][2] == 10, zm[:1])
            sprawdz(f"{nazwa} z {poz}: drugie przejście = lina z9 {stoi9[:2]} -> z8 {lad8[:2]}", len(zm) > 1 and zm[1] == (stoi9, lad8), zm[:2])
            sprawdz(f"{nazwa} z {poz}: lina nie z pola liny {POLE}", all(a != POLE for a, _ in zm[:1]), zm[:1])
            sprawdz(f"{nazwa} z {poz}: nie wchodzi na dziurę z9 {dziura_z9} (spadek na z10)", dziura_z9 not in pts)
            sprawdz(f"{nazwa} z {poz}: żadnego NOWEGO pola ognia (istniejące trasy {R.EXITY[nazwa][3]} i do planu mają 3 pojedyncze epizody n=1 na polach stania: poza oceną)",
                    not (OGIEN & set(pts)) - ISTNIEJACE, sorted((OGIEN & set(pts)) - ISTNIEJACE)[:3])
            sprawdz(f"{nazwa} z {poz}: trasa ciągła", ciagla(pts) is None, ciagla(pts))
        # 3. plan etapów (IDZ/LINA...) bez uwag dla jednej drogi z pętli
        r = W.droga_do_depo(petla[len(petla) // 2], petla, DO, zalew, MAPA, wyjscia=wyjscia)
        et = wypad.zbuduj_etapy([tuple(q) for q in r[0]], MAPA)
        sprawdz(f"{nazwa}: etapy zaczynają się IDZ LINA IDZ LINA (z10->z9, z9->z8)", [e["typ"] for e in et][:4] == ["IDZ", "LINA", "IDZ", "LINA"], [e["typ"] for e in et][:5])
        sprawdz(f"{nazwa}: sprawdz_plan bez uwag", not wypad.sprawdz_plan(et, MAPA, {}, rampy_ok=True), wypad.sprawdz_plan(et, MAPA, {}, rampy_ok=True)[:2])

        # 4. plik trasy: start przy lądowaniu, koniec w depo, nowy odcinek z buforem 1 od ognia, końcówka = istniejąca trasa dalej
        sprawdz(f"{nazwa} plik: start przy lądowaniu {LAD9}", wypad.cheb(plik[0], LAD9) <= 1 and plik[0][2] == 9, plik[0])
        sprawdz(f"{nazwa} plik: koniec w depo", plik[-1] == DEPO, plik[-1])
        sprawdz(f"{nazwa} plik: końcówka = {R.EXITY[nazwa][3]} (od jej 2. punktu)", plik[-len(kont[1:]):] == kont[1:])
        nowe = plik[:len(plik) - len(kont[1:])]
        przy = sorted({q for q in nowe if q in OGIEN_BUF})
        sprawdz(f"{nazwa} plik: nowy odcinek z buforem 1 od ognia", not przy, przy[:3])
        sprawdz(f"{nazwa} plik: pole liny {POLE} i dziura z9 {dziura_z9} poza trasą", POLE not in plik and dziura_z9 not in plik)
finally:
    W.PLANY_PK = _STARE

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
