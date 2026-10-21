#!/usr/bin/env python3
"""Przejścia pięter w obszarze z mapy klienta: które pola flagi 2 łączą które składowe i w którą stronę (W GÓRĘ / W DÓŁ).
Tylko odczyt. Krok 2 procedury `dane_tibia/mapy/PROCEDURA_nowy_spot.md`.

  python3 -I narzedzia/przejscia_pieter.py --obszar 32270,32090,32380,32180 --pietra 7-9 [--min-pola 40]

Kierunek (reguły sprawdzone na żywo 21.10, Thais północ):
  - pole przejścia na z, a w 3x3 na z-1 jest coś chodliwego  -> prowadzi W GÓRĘ (żółte 210 nad jaskinią to były schody na z6),
  - nic chodliwego wyżej, a obok na z+1 jest chodliwe          -> prowadzi W DÓŁ (dziura/schody; może być ZASYPANA = łopata),
  - pole, na którym postać stoi i nie spada, a use nic nie daje -> zasypana dziura: wpis do pietra.ZASYPANE + shovel,
  - flaga 2 w kolorze podłogi wokół (nie 210) POZA z7 -> PRZESZKODA (ogień, przedmiot), NIE przejście: 21.10 invincible stał
    w ogniu na (33115,31744,z8), które generator wziął za zejście (HP 91% -> 58% w 30 s).
Powierzchnia (z7) bywa bez flagi 2 nad zejściem (Edron (33117,31776) ma tylko zwykłe pole), więc brak wyniku na z7 nie
znaczy, że wejścia nie ma: wtedy patrz pola flagi 2 na z8 z „nad: z7” i nagranie przejścia.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import mapa  # noqa: E402
import spot_lib  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--obszar", required=True, help="x0,y0,x1,y1")
    ap.add_argument("--pietra", required=True, help="np. 7-10")
    ap.add_argument("--min-pola", type=int, default=40, help="pomiń przejścia z małych składowych")
    a = ap.parse_args(argv)
    X0, Y0, X1, Y1 = (int(v) for v in a.obszar.split(","))
    z0, z1 = (int(v) for v in a.pietra.split("-"))
    m = mapa.Mapa()

    def chodliwe(x, y, z):
        f = m.flagi(x, y, z)
        return bool(f & mapa.WIDZIANE and not f & mapa.SCIANA)

    K, R = {}, {}
    for z in range(z0 - 1, z1 + 2):
        komp, rozm, n = {}, {}, 0
        for x in range(X0, X1 + 1):
            for y in range(Y0, Y1 + 1):
                if (x, y) in komp or not chodliwe(x, y, z):
                    continue
                n += 1
                st, komp[(x, y)], c = [(x, y)], n, 0
                while st:
                    p, q = st.pop()
                    c += 1
                    for d in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)):
                        r = (p + d[0], q + d[1])
                        if r in komp or not (X0 <= r[0] <= X1 and Y0 <= r[1] <= Y1) or not chodliwe(*r, z):
                            continue
                        komp[r] = n
                        st.append(r)
                rozm[n] = c
        K[z], R[z] = komp, rozm

    def opis(z, x, y):
        k = K.get(z, {}).get((x, y))
        return f"z{z}#{k}({R[z][k]} pól)" if k else None

    for z in range(z0, z1 + 1):
        for (x, y), k in sorted(K[z].items()):
            if not m.flagi(x, y, z) & mapa.BEZ_DROGI or R[z][k] < a.min_pola:
                continue
            obok = [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
            gora = sorted({opis(z - 1, *c) for c in obok} - {None})
            dol = sorted({opis(z + 1, *c) for c in obok} - {None})
            kier = "W GÓRĘ" if gora else ("W DÓŁ" if dol else "?")
            if spot_lib.przeszkoda_na_podlodze(m, x, y, z):
                kier = "PRZESZKODA"      # 21.10: flaga 2 w kolorze podłogi poza z7 = ogień/przedmiot, nie przejście
            print(f"z{z} ({x},{y}) kolor {m.pole(x, y, z)[1]:3} w {opis(z, x, y)}: {kier:6} | wyżej: {gora} | niżej: {dol}")


if __name__ == "__main__":
    main()
