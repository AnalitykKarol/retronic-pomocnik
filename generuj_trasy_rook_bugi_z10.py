#!/usr/bin/env python3
"""Rookgaard, jaskinia bugów z10 (165 pól, 11 bugów w 5 spawnach) pod środkiem miasta, z mapy klienta i spawnów CipSoft 7.4 (20.10).
Metoda jak generuj_trasy_rook_raty2.py (jego funkcje); nic nie wysyła do gry:

  python3 -I generuj_trasy_rook_bugi_z10.py [--zapisz]        bez --zapisz tylko liczy i drukuje podsumowanie

Powstaje (przy --zapisz), w trasy/ i dane_tibia/mapy/:
  rook_bugi_z10_petla    pętla po jaskini bugów z10
  rook_bugi_z10_dojscie  z depo w mieście (z7) przez schody (32050,32187,z7) do kieszeni z8, schody (32061,32197,z8) na z9
                         (50 pól) i schody (32056,32199,z9) na z10; bot z kieszeni z8 / z9 idzie od najbliższego punktu
  rook_bugi_z10.png/.json podgląd i opis

Przejścia z mapy (kolor 210 + flaga 2 na górnym piętrze, to samo x,y niżej), niezweryfikowane botem:
  z7 (32050,32187) -> z8 (32050,32187); z8 (32061,32197) -> z9 (32061,32197); z9 (32056,32199) -> z10 (32056,32199).
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generuj_trasy_rook as g  # noqa: E402
import generuj_trasy_rook_raty2 as r2  # noqa: E402
import mapa as _mapa  # noqa: E402
import trasa_io  # noqa: E402

S7 = r2.S7
T7 = (32050, 32187, 7)
T8 = (32061, 32197, 8)
T9 = (32056, 32199, 9)
OBSZAR = (32030, 32070, 32185, 32210)  # x1, x2, y1, y2 (piętro 10)


def spawny_bugow():
    dane = json.loads(g.SPAWNY.read_text())["potwory"]
    x1, x2, y1, y2 = OBSZAR
    return [s for mo in dane if mo["nazwa"] == "bug" for s in mo.get("spawny", [])
            if s["z"] == 10 and x1 <= s["x"] <= x2 and y1 <= s["y"] <= y2]


def zbuduj():
    m = _mapa.Mapa()
    dz = [tuple(p) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])]
    sciana = lambda z: [p for p in dz if p[2] == z]   # noqa: E731
    for T in (T7, T8, T9):
        if not m.flagi(*T) & _mapa.WIDZIANE:
            raise SystemExit(f"{T}: pole niewidziane w mapie")
    # z7 -> z8
    przed7, d7 = r2.przed_przejsciem(m, S7, T7)
    L8 = r2.ladowanie(m, T7)
    comp8 = g.skladowa(m, L8, sciana(8))
    # z8 -> z9 (schody w kieszeni z8)
    przed8, d8 = r2.przed_przejsciem(m, L8, T8, sciana(8))
    L9 = r2.ladowanie(m, T8)
    comp9 = g.skladowa(m, L9, sciana(9))
    if not any((T9[0] + dx, T9[1] + dy) in comp9 for dx in (-1, 0, 1) for dy in (-1, 0, 1)):   # pole schodów (flaga 2) nie wchodzi do składowej
        raise SystemExit(f"z9: przejście {T9} poza składową z lądowania {L9}")
    # z9 -> z10
    przed9, d9 = r2.przed_przejsciem(m, L9, T9, sciana(9))
    L10 = r2.ladowanie(m, T9)
    comp10 = g.skladowa(m, L10, sciana(10))
    st = g.przystanki(spawny_bugow(), comp10)
    if not st:
        raise SystemExit("brak przystanków bugów w składowej z10")
    order, nodes, pelna = g.petla(m, 10, L10[:2], st, sciana(10))
    bugi = sum(t["n"] for t in st)

    doj = [S7] + [(x, y, 7) for x, y in d7] + [T7, L8]
    meta = [{"idx": len(doj) - 2, "typ": "przed_zmiana_pietra", "komentarz": "schody z7 (32050,32187), kolor 210 + flaga 2 w mapie; niezweryfikowane botem"},
            {"idx": len(doj) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z8 {L8[:2]} w kieszeni z8"}]
    doj += [(x, y, 8) for x, y in d8] + [T8, L9]
    meta += [{"idx": len(doj) - 2, "typ": "przed_zmiana_pietra", "komentarz": "schody z8 (32061,32197), kolor 210 + flaga 2"},
             {"idx": len(doj) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z9 {L9[:2]} (50 pól)"}]
    doj += [(x, y, 9) for x, y in d9] + [T9, L10]
    meta += [{"idx": len(doj) - 2, "typ": "przed_zmiana_pietra", "komentarz": "schody z9 (32056,32199), kolor 210 + flaga 2"},
             {"idx": len(doj) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z10 {L10[:2]}; po zejściu wejdź w pętlę rook_bugi_z10_petla"}]
    print(f"rook_bugi_z10: składowa {len(comp10)} pól, przystanków {len(st)}, bugów {bugi}, pętla {len(pelna)} pól, "
          f"dojście {len(doj)} pkt (kieszeń z8 {len(comp8)} pól, z9 {len(comp9)} pól), kolejność {order}")
    return m, comp10, st, order, nodes, pelna, doj, meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m, comp, st, order, nodes, pelna, doj, meta = zbuduj()
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    trasa_io.zapisz("rook_bugi_z10_petla", [(x, y, 10) for x, y in pelna])
    g.obraz(m, 10, pelna, order, nodes, st, g.OBRAZY / "rook_bugi_z10.png", "Rook jaskinia bugow z10")
    (g.OBRAZY / "rook_bugi_z10.json").write_text(json.dumps({
        "start": [*nodes[0], 10], "dlugosc_petli": len(pelna), "potwory": ["bug"],
        "przystanki": [{"kolejnosc": k, "x": nodes[o][0], "y": nodes[o][1], "z": 10,
                        **({} if o == 0 else {"potworow": st[o - 1]["n"], "spawnow": st[o - 1]["spawny"]})}
                       for k, o in enumerate(order)]}, ensure_ascii=False, indent=1))
    trasa_io.zapisz("rook_bugi_z10_dojscie", doj, meta)
    print("zapisano trasy/ i dane_tibia/mapy/ (wpis mapy.json dodaj osobno)")


if __name__ == "__main__":
    main()
