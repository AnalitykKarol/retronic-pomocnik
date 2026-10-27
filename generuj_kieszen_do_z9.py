#!/usr/bin/env python3
"""Dojście z kieszeni z8 (Rook) w dół do jaskini szczurów z9 (25.10; Karol: „połączyć razem”). Offline, nic nie wysyła do gry.

W kieszeni jest jedno pole przejścia z mapy: (32021,32166,z8) (flaga 2, kolor 210); pod nim, w tym samym polu na z9, leży pole przechodnie
(kolor 210) z tej samej składowej co pętla rook_raty_z9_petla (432 pola). Trasa: start pętli kieszeni (32035,32170,z8) po polach, na których
postać faktycznie stała -> pole przejścia -> lądowanie (32021,32166,z9) -> A* po z9 do startu pętli z9 (32029,32195,z9).
TYP PRZEJŚCIA NIEZWERYFIKOWANY W GRZE (dziura czy schody): oznaczone jak wejście z7 rook_raty_z8_dojscie (przed_zmiana_pietra + schody_w_dol).
Powrót z z9 do kieszeni NIE istnieje w danych (w składowej z9 nie ma pól flagi 2).

  python3 -I generuj_kieszen_do_z9.py [--zapisz]

Zapis: trasy/rook_raty_z8_kieszen_do_z9.{json,meta}, wpis `rook_raty_z9_z_kieszeni` w mapy.json (kopia mapy.json.bak-20261025-kieszen-z9)."""
import argparse, json, shutil, sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import mapa as _mapa  # noqa: E402
import spot_lib  # noqa: E402
import trasa_io  # noqa: E402
import generuj_kieszen_rook as g  # noqa: E402

DZIURA = (32021, 32166)
START8 = (32035, 32170)
START9 = (32029, 32195)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m = _mapa.Mapa()
    assert m.schody_lub_dziura(DZIURA[0], DZIURA[1], 8), "pole przejścia nie ma flagi 2"
    dz = {(p[0], p[1]) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", []) if p[2] == g.Z}
    vis = g.wizyty()
    dozw = set()
    for (x, y) in vis:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                q = (x + dx, y + dy)
                if q not in dz and (q in vis or spot_lib.chodliwe(m, (q[0], q[1], g.Z))):
                    dozw.add(q)
    xs = [p[0] for p in dozw]; ys = [p[1] for p in dozw]
    zajete = [(x, y, g.Z) for x in range(min(xs) - 2, max(xs) + 3) for y in range(min(ys) - 2, max(ys) + 3) if (x, y) not in dozw]
    d8 = m.droga((START8[0], START8[1], 8), DZIURA, zajete=zajete, dlugosc=1, limit=400000)
    if d8 is None:
        raise SystemExit("brak drogi po odwiedzonych polach kieszeni do pola przejścia")
    p8 = [(START8[0], START8[1], 8)] + [(p[0], p[1], 8) for p in d8]
    if (p8[-1][0], p8[-1][1]) != DZIURA:
        p8.append((DZIURA[0], DZIURA[1], 8))
    land = (DZIURA[0], DZIURA[1], 9)
    d9 = m.droga(land, START9, dlugosc=0, limit=400000)
    if d9 is None:
        raise SystemExit("brak drogi po z9 od lądowania do startu pętli z9")
    p9 = [land] + [(p[0], p[1], 9) for p in d9]
    punkty = p8 + p9
    # bez dubli sąsiadujących
    out = [punkty[0]]
    for p in punkty[1:]:
        if p != out[-1]:
            out.append(p)
    i_przejscia = out.index((DZIURA[0], DZIURA[1], 8))
    meta = [{"idx": i_przejscia, "typ": "przed_zmiana_pietra", "komentarz": "pole przejścia z8 w kieszeni (32021,32166; flaga 2, kolor 210), typ (dziura/schody) NIEZWERYFIKOWANY w grze"},
            {"idx": i_przejscia + 1, "typ": "schody_w_dol", "komentarz": "lądowanie z9 (32021,32166) dokładnie pod polem przejścia; potem A* po z9 do startu pętli rook_raty_z9_petla"}]
    print(f"z8: {len(p8)} pól (po odwiedzonych), przejście idx {i_przejscia}, z9: {len(p9)} pól do {START9}; razem {len(out)} pkt")
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    trasa_io.zapisz("rook_raty_z8_kieszen_do_z9", out, meta)
    mp = ROOT / "mapy.json"
    shutil.copy2(mp, ROOT / "mapy.json.bak-20261025-kieszen-z9")
    d = json.loads(mp.read_text())
    z9 = d["rook_raty_z9"]
    d["rook_raty_z9_z_kieszeni"] = {
        "opis": ("Rookgaard, jaskinia szczurów z9 (jak rook_raty_z9) z dojściem Z KIESZENI z8: kieszeń -> pole przejścia (32021,32166,z8) -> z9 -> pętla. "
                 "25.10, Karol: połączyć kieszeń z z9. Typ przejścia NIEZWERYFIKOWANY, powrotu z z9 do kieszeni brak. Start bota tylko gdy postać stoi w kieszeni."),
        "trasa": z9["trasa"], "potwory": z9["potwory"], "prog_hp": z9["prog_hp"], "dojscie": "rook_raty_z8_kieszen_do_z9"}
    tmp = mp.with_name("mapy.json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    tmp.replace(mp)
    print("zapisano trasy/ i mapy.json")


if __name__ == "__main__":
    main()
