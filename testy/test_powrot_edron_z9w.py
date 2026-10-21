"""21.10: powrót do depo z wschodniej jaskini trolli z9 (trolle_edron_z9w). Regresja zacięcia Kolanosha 20:14:
plan "edron" nie miał wyjścia z z9w, wyprawa dawała "depo: brak drogi" i stała w (33121,31756,9) do alarmu.
Dane rzeczywiste: pętla z9w, trolle_edron_z9w_do_depo, edron_do_depo, prawdziwa mapa. Nic nie trafia do gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa
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
PETLA = wczytaj("trolle_edron_z9w_petla.json")
PLAN = next(p for p in W.PLANY_PK if p["nazwa"] == "edron")
DO = wczytaj(PLAN["do"])
DEPO = (33173, 31796, 8)
STOI, LAD = (33119, 31739, 9), (33119, 31741, 8)
DZIURA_Z8 = (33119, 31740, 8)      # wejście na nią = spadek z powrotem na z9
POLE_LINY = (33119, 31740, 9)      # leży na pętli (wolno po nim chodzić), ale liny nie używamy, stojąc na nim
OGIEN = {(33115, 31744, 8)}
for f in ("ogien_stale.json", "ogien_epizody.json"):
    d = json.loads((TRASY / f).read_text())
    for p in (d.get("pola") if isinstance(d, dict) else d) or []:
        if isinstance(p, (list, tuple)) and len(p) >= 3:
            OGIEN.add(tuple(int(v) for v in p[:3]))


def zalew(a, cele):
    return T.zalew(a, cele, limit=W.DEPO_ZALEW_LIMIT)


def droga(poz, wyjscia):
    wyn = W.droga_do_depo(poz, PETLA, DO, zalew, MAPA, wyjscia=wyjscia)
    return None if wyn is None else [tuple(q) for q in wyn[0]]


def ciagla(pts):
    for a, b in zip(pts, pts[1:]):
        if a[2] == b[2] and wypad.cheb(a, b) > 5:
            return f"skok {a}->{b}"
        if a[2] != b[2] and wypad.cheb(a, b) > 3:
            return f"skok pięter {a}->{b}"
    return None


# 1. przed poprawką: same stare wyjścia = brak drogi (dokładnie objaw z logu 20:13:38)
stare = tuple(w for w in PLAN["wyjscia"] if tuple(w[0]) != (33119, 31740, 9))
sprawdz("bez wyjścia z9w: brak drogi z (33123,31749,9)", droga((33123, 31749, 9), stare) is None)

# 2. po poprawce: z miejsc zacięcia i z co 10. punktu pętli
starty = [(33121, 31756, 9), (33123, 31749, 9), (33122, 31752, 9)] + PETLA[::10]
for poz in starty:
    pts = droga(poz, PLAN["wyjscia"])
    if pts is None:
        sprawdz(f"droga z {poz}", False, "brak drogi")
        continue
    zm = [(a, b) for a, b in zip(pts, pts[1:]) if a[2] != b[2]]
    sprawdz(f"z {poz}: koniec w depo", pts[-1] == DEPO, pts[-1])
    sprawdz(f"z {poz}: pierwsze przejście = lina {STOI}->{LAD}", zm and zm[0] == (STOI, LAD), zm[:1])
    sprawdz(f"z {poz}: nie wchodzi na dziurę z8", DZIURA_Z8 not in pts)
    sprawdz(f"z {poz}: lina nie z pola liny", all(a != POLE_LINY for a, _ in zm), zm[:1])
    sprawdz(f"z {poz}: żadnego pola ognia", not OGIEN & set(pts), sorted(OGIEN & set(pts))[:3])
    blad = ciagla(pts)
    sprawdz(f"z {poz}: trasa ciągła", blad is None, blad)

# 3. plik trasy: start obok lądowania, koniec w depo, odcinek z8 do liny z8->z7 wspólny z edron_do_depo
plik = wczytaj("trolle_edron_z9w_do_depo.json")
sprawdz("plik: start przy lądowaniu", wypad.cheb(plik[0], LAD) <= 1 and plik[0][2] == 8, plik[0])
sprawdz("plik: koniec w depo", plik[-1] == DEPO, plik[-1])
sprawdz("plik: końcówka = edron_do_depo od liny z8->z7", plik[-len(DO[7:]):] == DO[7:])

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
