#!/usr/bin/env python3
"""Rookgaard, jaskinia bugów z8 za pocztą (schody w dół z7 -> kieszeń 144 pól, 5 spawnów bugów), z mapy klienta i spawnów CipSoft 7.4 (20.10).
Metoda jak generuj_trasy_ph.py: składowa z8 -> spawny bugów w niej -> przystanki -> pętla (NN + 2-opt po A*).
Uruchamiane offline, niczego nie wysyła do gry:

  python3 -I generuj_trasy_rook_bugi.py [--zapisz]

Powstaje (przy --zapisz), w trasy/ i dane_tibia/mapy/:
  rook_bugi_z8_petla   pętla po jaskini z8 (start na lądowaniu pod wejściem (32077,32152,z8))
  rook_bugi_z8.png     podgląd trasy
Dojścia z miasta nie ma: Karol wchodzi ręcznie (20.10), bot startuje na miejscu jak gobliny_edron.
Dwa wejścia z7 do tej samej kieszeni: (32056,32146) i (32077,32151) — oba z flagą 2 w mapie, typ niezweryfikowany.
"""
import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import mapa as _mapa  # noqa: E402
import spot_lib  # noqa: E402
from spot_lib import petla, przystanki, skladowa, wynik  # noqa: E402

Z = 8
LAD8 = (32077, 32152, 8)
POTWORY = ("bug",)
OBSZAR = (32040, 32110, 32140, 32180)  # x1, x2, y1, y2


def spawny():
    return spot_lib.spawny(Z, POTWORY, OBSZAR)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m = _mapa.Mapa()
    comp = skladowa(m, LAD8)
    if LAD8[:2] not in comp:
        raise SystemExit(f"lądowanie {LAD8} poza składową z8")
    stops = przystanki(spawny(), comp)
    order, nodes, pelna = petla(m, Z, LAD8[:2], stops, ())
    wynik("rook_bugi_z8", Z, comp, stops, order, nodes, pelna)
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    spot_lib.zapis_spotu(m, "rook_bugi_z8", Z, pelna, order, nodes, stops, "Rook jaskinia bugów z8", ekstra={"potwory": list(POTWORY)})
    print("zapisano trasy/rook_bugi_z8_petla i dane_tibia/mapy/rook_bugi_z8.*")


if __name__ == "__main__":
    main()
