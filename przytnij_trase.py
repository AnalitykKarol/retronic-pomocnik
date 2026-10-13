#!/usr/bin/env python3
"""Przycina trasę do punktów od..do (włącznie, indeksy od 0).

  python3 -I przytnij_trase.py <nazwa> --od N --do M [--wyj nazwa2]
Bez --wyj nadpisuje trasę (stara kopia: trasy/<nazwa>.json.bak).
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import trasa_io  # noqa: E402


def przytnij(punkty, meta, od=0, do=None):
    n = len(punkty)
    do = n - 1 if do is None else do
    if not (0 <= od <= do < n):
        raise ValueError(f"zły zakres {od}..{do} dla trasy z {n} punktami")
    nowe = [dict(m, idx=m["idx"] - od) for m in meta if od <= m["idx"] <= do]
    return punkty[od:do + 1], nowe


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("nazwa")
    p.add_argument("--od", type=int, default=0)
    p.add_argument("--do", type=int)
    p.add_argument("--wyj", help="zapisz pod inną nazwą (domyślnie nadpisz)")
    a = p.parse_args(argv)
    punkty, meta = trasa_io.wczytaj(a.nazwa)
    try:
        nowe, meta2 = przytnij(punkty, meta, a.od, a.do)
    except ValueError as e:
        sys.exit(str(e))
    if not a.wyj:
        shutil.copyfile(trasa_io.sciezka(a.nazwa), str(trasa_io.sciezka(a.nazwa)) + ".bak")
    cel = a.wyj or a.nazwa
    plik = trasa_io.zapisz(cel, nowe, meta2)
    print(f"{plik}: {len(punkty)} -> {trasa_io.podsumowanie(nowe)}")


if __name__ == "__main__":
    main()
