#!/usr/bin/env python3
"""Trasa na cave raty i bugi pod Port Hope (z8, 32644-32679 x 32699-32752) z mapy klienta i spawnów CipSoft 7.4 (20.10).
Metoda jak generuj_trasy_rook.py (klocki w spot_lib.py od 21.10): składowa z8 -> spawny cave rat/bug/spider w niej -> przystanki -> pętla (NN + 2-opt po A*).
Uruchamiane offline, niczego nie wysyła do gry:

  python3 -I generuj_trasy_ph.py [--zapisz]

Powstają (przy --zapisz), w trasy/ i dane_tibia/mapy/:
  ph_raty_z8_petla    pętla po jaskini z8
  ph_raty_z8_dojscie  ze środka Port Hope (32623,32772,z7) 68 pól po z7 do wejścia (32662,32741,z7) i na z8.
                      WEJŚCIE WYWNIOSKOWANE Z MAPY (kolor 210 i flaga 2 na z7, kolor 210 na z8 w tym samym polu, jak sprawdzone
                      wejście Rook z8), typ przejścia i pole lądowania NIEZWERYFIKOWANE w grze.
  ph_raty_z8.png      podgląd trasy
Zagrożenia (dane 7.4 i 7.6 jamera): w 8 polach od dojścia brak spawnów z ciosem > 25; najbliższy spawn czegokolwiek 23 pola od drogi.
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
MIASTO = (32623, 32772, 7)          # środek Port Hope (start trasy dane_tibia/mapy/port_hope_swamp_trolle.json)
WEJ7, LAD8 = (32662, 32741, 7), (32662, 32741, 8)
POTWORY = ("cave rat", "bug", "spider")
OBSZAR = (32640, 32685, 32695, 32755)  # x1, x2, y1, y2


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
    wynik("ph_raty_z8", Z, comp, stops, order, nodes, pelna)
    przed = min(((WEJ7[0] + dx, WEJ7[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy),
                key=lambda p: len(m.droga(MIASTO, p, dlugosc=0, limit=400000) or range(10 ** 6)))
    d7 = m.droga(MIASTO, przed, dlugosc=0, limit=400000)
    if d7 is None:
        raise SystemExit(f"brak drogi z7 {MIASTO} -> {przed}")
    doj = [MIASTO] + [tuple(p) for p in d7] + [WEJ7, LAD8]
    meta = [{"idx": len(doj) - 2, "typ": "przed_zmiana_pietra",
             "komentarz": "pole przejścia z7 (kolor 210, flaga 2), typ przejścia NIEZWERYFIKOWANY w grze"},
            {"idx": len(doj) - 1, "typ": "schody_w_dol",
             "komentarz": "lądowanie z8 (32662,32741) z mapy; potem pętla ph_raty_z8_petla"}]
    print(f"ph_raty_z8_dojscie: {len(doj)} pkt, z7 {len(d7)} pól do wejścia")
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    spot_lib.zapis_spotu(m, "ph_raty_z8", Z, pelna, order, nodes, stops, "Port Hope cave raty/bugi", ekstra={"potwory": list(POTWORY)},
                         doj=doj, meta=meta)
    print("zapisano trasy/ph_raty_z8_* i dane_tibia/mapy/ph_raty_z8.*")


if __name__ == "__main__":
    main()
