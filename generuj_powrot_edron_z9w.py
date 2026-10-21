#!/usr/bin/env python3
"""Edron, wschodnia jaskinia trolli z9 (trolle_edron_z9w): trasa powrotu do depo po wyjściu liną z z9 (21.10).

  python3 -I generuj_powrot_edron_z9w.py [--zapisz]        bez --zapisz tylko liczy i drukuje podsumowanie

Powód: 21.10 20:14 Kolanosh utknął w z9w na żądanie powrotu (`depo: brak drogi`, plan "edron" nie miał wyjścia z z9w).
Wyjście: lina na polu (33119,31740,z9) (dziura, którą dojście schodzi z z8), stanie obok (33119,31739,z9),
lądowanie (33119,31741,z8). Wpis w wyprawa.PLANY_PK["edron"]["wyjscia"].

Powstaje trasy/trolle_edron_z9w_do_depo (+ .meta), sklejona z dwóch przebytych na żywo kawałków:
  1. odcinek z8 dojścia trolle_edron_z9w_dojscie, odwrócony: od (33118,31741) do (33117,31774), BEZ pola dziury
     (33119,31740,z8) (wejście na nie = spadek z powrotem na z9) i bez pola liny (33117,31775,z8);
  2. edron_do_depo od liny (33117,31774,z8) -> z7 do depo (33173,31796,z8): powrót sprawdzony (Dawajkesh 21.10 18:24).
"""
import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import trasa_io  # noqa: E402

NAZWA = "trolle_edron_z9w_do_depo"
DZIURA_Z8 = (33119, 31740, 8)
PIERWSZY = (33118, 31741, 8)          # pierwszy punkt odwróconego dojścia za polem dziury
SKLEJENIE = (33117, 31774, 8)         # pole stania przy linie z8 -> z7, wspólne dla obu tras


def zbuduj():
    dojscie, _ = trasa_io.wczytaj("trolle_edron_z9w_dojscie")
    do, meta_do = trasa_io.wczytaj("edron_do_depo")
    rev = list(reversed(dojscie))
    i0 = rev.index(PIERWSZY)
    i1 = rev.index(SKLEJENIE, i0)
    czesc1 = rev[i0:i1 + 1]
    if any(q[2] != 8 for q in czesc1) or DZIURA_Z8 in czesc1:
        raise SystemExit(f"odcinek z8 dojścia nie jest ciągły na z8 albo zawiera dziurę: {czesc1}")
    j = do.index(SKLEJENIE)
    czesc2 = do[j + 1:]
    punkty = czesc1 + czesc2
    przes = len(czesc1) - (j + 1)
    meta = [{"idx": 0, "typ": "start", "komentarz": "lądowanie po linie z z9 (33119,31740), z8"}]
    meta += [dict(m, idx=m["idx"] + przes) for m in meta_do if m["idx"] >= j]
    return punkty, meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    punkty, meta = zbuduj()
    print(f"{NAZWA}: {len(punkty)} pkt, start {punkty[0]}, koniec {punkty[-1]}, "
          f"piętra {sorted({q[2] for q in punkty})}, meta {len(meta)}")
    if a.zapisz:
        print("zapisano", trasa_io.zapisz(NAZWA, punkty, meta))


if __name__ == "__main__":
    main()
