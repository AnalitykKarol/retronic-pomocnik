#!/usr/bin/env python3
"""Edron, jaskinie trolli z9 (trolle_edron_z9w, trolle_edron_z9z): trasy powrotu do depo po wyjściu liną z z9 (21.10).

  python3 -I generuj_powroty_edron_z9.py [--zapisz]        bez --zapisz tylko liczy i drukuje podsumowanie

Powód: 21.10 20:14 Kolanosh utknął w z9w na żądanie powrotu (`depo: brak drogi`, plan "edron" nie miał wyjścia z z9);
z9z miał tę samą lukę (offline: brak drogi z 14/14 punktów pętli). Dojścia schodzą na z9 dziurą z z8; powrót = lina
w tym samym polu na z9, stanie obok (pole liny wolne), lądowanie (x, y+1, z8). Wpisy w wyprawa.PLANY_PK["edron"]["wyjscia"].

Każda trasa trasy/<spot>_do_depo (+ .meta) jest sklejona z dwóch kawałków:
  1. odcinek z8 dojścia <spot>_dojscie, odwrócony: od pola za dziurą do (33117,31774), BEZ pola dziury (wejście na nie =
     spadek z powrotem na z9) i bez pola liny (33117,31775,z8);
  2. edron_do_depo od liny (33117,31774,z8) -> z7 do depo (33173,31796,z8): powrót sprawdzony (Dawajkesh 21.10 18:24).
z9w: odcinek 1 przebyty na żywo (Kolanosh 21.10 2x). z9z: odcinek 1 z generatora, na żywo jeszcze nie.
"""
import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import trasa_io  # noqa: E402

SKLEJENIE = (33117, 31774, 8)         # pole stania przy linie z8 -> z7, wspólne dla dojść i edron_do_depo
# spot: (dziura na z8 = pole liny na z9 (x, y), stanie obok na z9)
SPOTY = {
    "trolle_edron_z9w": ((33119, 31740), (33119, 31739, 9)),
    "trolle_edron_z9z": ((33081, 31742), (33081, 31741, 9)),
}


def wyjscie(spot):
    """Wpis do wyprawa.PLANY_PK["edron"]["wyjscia"]: (pole liny z9, lądowanie z8, plik trasy dalej, (stanie,))."""
    (x, y), stoi = SPOTY[spot]
    return ((x, y, 9), (x, y + 1, 8), f"{spot}_do_depo.json", (stoi,))


def zbuduj(spot):
    (x, y), _ = SPOTY[spot]
    dziura = (x, y, 8)
    dojscie, _ = trasa_io.wczytaj(f"{spot}_dojscie")
    do, meta_do = trasa_io.wczytaj("edron_do_depo")
    rev = list(reversed(dojscie))
    i0 = rev.index(dziura) + 1
    i1 = rev.index(SKLEJENIE, i0)
    czesc1 = rev[i0:i1 + 1]
    if any(q[2] != 8 for q in czesc1) or dziura in czesc1:
        raise SystemExit(f"{spot}: odcinek z8 dojścia nie jest ciągły na z8 albo zawiera dziurę: {czesc1}")
    j = do.index(SKLEJENIE)
    punkty = czesc1 + do[j + 1:]
    przes = len(czesc1) - (j + 1)
    meta = [{"idx": 0, "typ": "start", "komentarz": f"lądowanie po linie z z9 ({x},{y}), z8"}]
    meta += [dict(m, idx=m["idx"] + przes) for m in meta_do if m["idx"] >= j]
    return punkty, meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    for spot in SPOTY:
        punkty, meta = zbuduj(spot)
        print(f"{spot}_do_depo: {len(punkty)} pkt, start {punkty[0]}, koniec {punkty[-1]}, "
              f"piętra {sorted({q[2] for q in punkty})}, meta {len(meta)}")
        if a.zapisz:
            print("zapisano", trasa_io.zapisz(f"{spot}_do_depo", punkty, meta))


if __name__ == "__main__":
    main()
