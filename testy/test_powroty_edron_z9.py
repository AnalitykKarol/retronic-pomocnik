"""21.10: powrót do depo z jaskiń trolli z9 Edron (trolle_edron_z9w, trolle_edron_z9z). Regresja zacięcia Kolanosha 20:14:
plan "edron" nie miał wyjścia z z9w, wyprawa dawała "depo: brak drogi" i stała w (33121,31756,9) do alarmu; z9z to samo.
Dane rzeczywiste: pętle, trasy <spot>_do_depo, edron_do_depo, prawdziwa mapa. Nic nie trafia do gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa
import generuj_powroty_edron_z9 as G
import wypad
import wyprawa as W

TRASY = Path(_R) / "trasy"
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test powrotu z z9w")
    sys.exit(0)


def wczytaj(nazwa):
    return [tuple(int(v) for v in p) for p in json.loads((TRASY / nazwa).read_text())]


MAPA = _mapa.Mapa()
T = W.Trasownik(MAPA)
PLAN = next(p for p in W.PLANY_PK if p["nazwa"] == "edron")
DO = wczytaj(PLAN["do"])
DEPO = (33173, 31796, 8)
OGIEN = {(33115, 31744, 8)}
for f in ("ogien_stale.json", "ogien_epizody.json"):
    d = json.loads((TRASY / f).read_text())
    for p in (d.get("pola") if isinstance(d, dict) else d) or []:
        if isinstance(p, (list, tuple)) and len(p) >= 3:
            OGIEN.add(tuple(int(v) for v in p[:3]))


def zalew(a, cele):
    return T.zalew(a, cele, limit=W.DEPO_ZALEW_LIMIT)


def droga(poz, petla, wyjscia):
    wyn = W.droga_do_depo(poz, petla, DO, zalew, MAPA, wyjscia=wyjscia)
    return None if wyn is None else [tuple(q) for q in wyn[0]]


def ciagla(pts):
    for a, b in zip(pts, pts[1:]):
        if a[2] == b[2] and wypad.cheb(a, b) > 5:
            return f"skok {a}->{b}"
        if a[2] != b[2] and wypad.cheb(a, b) > 3:
            return f"skok pięter {a}->{b}"
    return None


ZACIECIA = {"trolle_edron_z9w": [(33121, 31756, 9), (33123, 31749, 9), (33122, 31752, 9)], "trolle_edron_z9z": []}

for spot in G.SPOTY:
    POLE_LINY, LAD, plik_do, (STOI,) = G.wyjscie(spot)
    DZIURA_Z8 = (POLE_LINY[0], POLE_LINY[1], 8)      # wejście na nią = spadek z powrotem na z9
    PETLA = wczytaj(f"{spot}_petla.json")          # pole liny leży na pętli: chodzić wolno, liny z niego nie używamy
    sprawdz(f"{spot}: wyjście w PLANY_PK", any(tuple(w[0]) == POLE_LINY and w[2] == plik_do for w in PLAN["wyjscia"]))

    # 1. przed poprawką: bez tego wyjścia = brak drogi (objaw z logu 20:13:38)
    stare = tuple(w for w in PLAN["wyjscia"] if tuple(w[0]) != POLE_LINY)
    sprawdz(f"{spot}: bez wyjścia brak drogi z {PETLA[0]}", droga(PETLA[0], PETLA, stare) is None)

    # 2. po poprawce: z miejsc zacięcia i z co 10. punktu pętli
    for poz in ZACIECIA[spot] + PETLA[::10]:
        pts = droga(poz, PETLA, PLAN["wyjscia"])
        if pts is None:
            sprawdz(f"{spot} z {poz}: droga", False, "brak drogi")
            continue
        zm = [(a, b) for a, b in zip(pts, pts[1:]) if a[2] != b[2]]
        sprawdz(f"{spot} z {poz}: koniec w depo", pts[-1] == DEPO, pts[-1])
        sprawdz(f"{spot} z {poz}: pierwsze przejście = lina {STOI}->{LAD}", zm and zm[0] == (STOI, LAD), zm[:1])
        sprawdz(f"{spot} z {poz}: nie wchodzi na dziurę z8", DZIURA_Z8 not in pts)
        sprawdz(f"{spot} z {poz}: lina nie z pola liny", all(a != POLE_LINY for a, _ in zm), zm[:1])
        sprawdz(f"{spot} z {poz}: żadnego pola ognia", not OGIEN & set(pts), sorted(OGIEN & set(pts))[:3])
        blad = ciagla(pts)
        sprawdz(f"{spot} z {poz}: trasa ciągła", blad is None, blad)

    # 3. plik trasy: start obok lądowania, koniec w depo, końcówka = edron_do_depo od liny z8->z7,
    #    nowy odcinek z8 (sprzed sklejenia) z buforem 1 od znanego ognia
    plik = wczytaj(plik_do)
    sprawdz(f"{spot} plik: start przy lądowaniu", wypad.cheb(plik[0], LAD) <= 1 and plik[0][2] == 8, plik[0])
    sprawdz(f"{spot} plik: koniec w depo", plik[-1] == DEPO, plik[-1])
    sprawdz(f"{spot} plik: końcówka = edron_do_depo od liny z8->z7", plik[-len(DO[7:]):] == DO[7:])
    nowe = plik[:len(plik) - len(DO[7:])]
    przy = sorted({q for q in nowe for o in OGIEN if q[2] == o[2] and wypad.cheb(q, o) <= 1})
    sprawdz(f"{spot} plik: odcinek z8 z buforem 1 od ognia", not przy, przy[:3])

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
