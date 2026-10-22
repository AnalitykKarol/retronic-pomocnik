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
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generuj_trasy_rook as G  # noqa: E402
import mapa as _mapa  # noqa: E402
import trasa_io  # noqa: E402

Z = 8
LAD8 = (32077, 32152, 8)
POTWORY = ("bug",)
OBSZAR = (32040, 32110, 32140, 32180)  # x1, x2, y1, y2


def spawny():
    dane = json.loads(G.SPAWNY.read_text())["potwory"]
    x1, x2, y1, y2 = OBSZAR
    return [s for mo in dane if mo["nazwa"] in POTWORY for s in mo.get("spawny", [])
            if s["z"] == Z and x1 <= s["x"] <= x2 and y1 <= s["y"] <= y2]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m = _mapa.Mapa()
    comp = G.skladowa(m, LAD8)
    if LAD8[:2] not in comp:
        raise SystemExit(f"lądowanie {LAD8} poza składową z8")
    stops = G.przystanki(spawny(), comp)
    order, nodes, pelna = G.petla(m, Z, LAD8[:2], stops, ())
    G.wynik("rook_bugi_z8", Z, comp, stops, order, nodes, pelna)
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    trasa_io.zapisz("rook_bugi_z8_petla", [(x, y, Z) for x, y in pelna])
    G.obraz(m, Z, pelna, order, nodes, stops, G.OBRAZY / "rook_bugi_z8.png", "Rook jaskinia bugów z8")
    (G.OBRAZY / "rook_bugi_z8.json").write_text(json.dumps({
        "start": [*nodes[0], Z], "dlugosc_petli": len(pelna), "potwory": list(POTWORY),
        "przystanki": [{"kolejnosc": k, "x": nodes[o][0], "y": nodes[o][1], "z": Z,
                        **({} if o == 0 else {"potworow": stops[o - 1]["n"], "spawnow": stops[o - 1]["spawny"]})}
                       for k, o in enumerate(order)]}, ensure_ascii=False, indent=1))
    print("zapisano trasy/rook_bugi_z8_petla i dane_tibia/mapy/rook_bugi_z8.*")


if __name__ == "__main__":
    main()
