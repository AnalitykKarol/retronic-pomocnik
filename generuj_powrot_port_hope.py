#!/usr/bin/env python3
"""Port Hope: trasy POWROTU do depo Port Hope (25.10, Karol: depo (32632,32743,z7)), z mapy klienta (A*), nie nagrane.

  python3 -I generuj_powrot_port_hope.py [--zapisz]        bez --zapisz tylko liczy

Powstają:
  ph_raty_z8_do_depo       jaskinia ratów z8 (ph_raty_z8): STOI (32662,32740,z8) -> przejście w górę -> LAD (32662,32742,z7) -> depo.
      Dojście zeszło dziurą z7 (32662,32741) na z8 (32662,32741); pole (32662,32741,z8) jest nad nią w górę (pietra.kandydaci: pewne),
      czyli LINA: używana ze STOI (x, y-1, jak Edron; na południe jest ściana), lądowanie (x, y+1, z7). Wymaga liny w ekwipunku; przejście NIEZWERYFIKOWANE na żywo.
  port_hope_swamp_do_depo  powierzchnia z7: wejście do jaskini swamp trolli (32678,32612) -> depo (bez pięter jaskini).
"""
import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import mapa as _mapa  # noqa: E402
import trasa_io  # noqa: E402

DEPO = (32632, 32743, 7)
POLE_LINY = (32662, 32741, 8)
STOI = (32662, 32740, 8)
LAD = (32662, 32742, 7)
NAZWA_RATY = "ph_raty_z8_do_depo"
NAZWA_SWAMP = "port_hope_swamp_do_depo"
SWAMP_WEJSCIE = (32678, 32612, 7)


def wyjscie():
    """Wpis do wyprawa.PLANY_PK["ph_raty_z8"]["wyjscia"]: (pole liny z8, lądowanie z7, plik trasy dalej, (stanie,))."""
    return (POLE_LINY, LAD, NAZWA_RATY + ".json", (STOI,))


def _z7(m, start):
    a = m.droga(start, DEPO, dlugosc=1)
    if not a:
        raise SystemExit(f"brak drogi {start} -> {DEPO}")
    pts = [tuple(p) for p in a]
    if pts[0] != tuple(start):
        pts.insert(0, tuple(start))
    if pts[-1] != DEPO:
        pts.append(DEPO)
    return pts


def zbuduj_raty(m):
    z7 = _z7(m, LAD)
    punkty = [STOI] + z7
    meta = [{"idx": 0, "typ": "przed_zmiana_pietra",
             "komentarz": f"stanie {STOI[:2]} z8 obok pola liny {POLE_LINY[:2]} (pod dziurą z7); lina z8 -> z7, niezweryfikowane na żywo"},
            {"idx": 1, "typ": "schody_w_gore", "komentarz": f"lądowanie z7 {LAD[:2]} = (x, y+1) pola liny"},
            {"idx": len(punkty) - 1, "typ": "koniec", "komentarz": "depo Port Hope (32632,32743,z7) podane przez Karola"}]
    return punkty, meta


def zbuduj_swamp(m):
    punkty = _z7(m, SWAMP_WEJSCIE)
    return punkty, [{"idx": 0, "typ": "start", "komentarz": "wejście do jaskini swamp trolli (z7)"},
                    {"idx": len(punkty) - 1, "typ": "koniec", "komentarz": "depo Port Hope (32632,32743,z7)"}]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m = _mapa.mapa()
    for nazwa, (punkty, meta) in ((NAZWA_RATY, zbuduj_raty(m)), (NAZWA_SWAMP, zbuduj_swamp(m))):
        print(f"{nazwa}: {len(punkty)} pkt, start {punkty[0]}, koniec {punkty[-1]}, piętra {sorted({q[2] for q in punkty})}")
        if a.zapisz:
            print("zapisano", trasa_io.zapisz(nazwa, punkty, meta))


if __name__ == "__main__":
    main()
