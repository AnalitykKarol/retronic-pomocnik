#!/usr/bin/env python3
"""Odwraca kolejność punktów trasy (miasto->spot staje się spot->miasto). Piętra zostają
przypisane do swoich punktów, więc zmiana piętra dalej następuje na tych samych polach.

  python3 -I odwroc_trase.py <nazwa> [--wyj nazwa2]
Bez --wyj zapisuje jako <nazwa>_odwrocona.
"""
import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import trasa_io  # noqa: E402

ODWROTNE = {"schody_w_gore": "schody_w_dol", "schody_w_dol": "schody_w_gore"}


def odwroc(punkty, meta):
    n = len(punkty)
    nowe_meta = []
    for m in sorted(meta, key=lambda m: -m["idx"]):
        typ = ODWROTNE.get(m["typ"], m["typ"])
        kom = m.get("komentarz", "")
        if typ != m["typ"]:
            kom += " (po odwróceniu kierunek przeciwny)"
        nowe_meta.append(dict(m, idx=n - 1 - m["idx"], typ=typ, komentarz=kom))
    return list(reversed(punkty)), nowe_meta


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("nazwa")
    p.add_argument("--wyj", help="nazwa wyjściowa (domyślnie <nazwa>_odwrocona)")
    a = p.parse_args(argv)
    punkty, meta = trasa_io.wczytaj(a.nazwa)
    nowe, meta2 = odwroc(punkty, meta)
    wyj = a.wyj or f"{a.nazwa}_odwrocona"
    plik = trasa_io.zapisz(wyj, nowe, meta2)
    print(f"{plik}: {trasa_io.podsumowanie(nowe)}")


if __name__ == "__main__":
    main()
