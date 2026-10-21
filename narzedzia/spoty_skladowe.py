#!/usr/bin/env python3
"""Ranking spotów jako SKŁADOWYCH mapy klienta (obszary oddzielone ścianami, bez schodów), ze spawnami CipSoft 7.4.
Tylko odczyt plików, nic nie wysyła do gry. Krok 1 procedury `dane_tibia/mapy/PROCEDURA_nowy_spot.md`.

  python3 -I narzedzia/spoty_skladowe.py --miasto Thais [--max-cios 50] [--min-potworow 8] [--pietra 7-12]
  python3 -I narzedzia/spoty_skladowe.py --obszar 33000,31640,33320,31960 --swiatynia 33217,31814,8

Wiersz: miasto, piętro, środek ciężkości spawnów, odległość (Chebyshev) od świątyni, pola składowej, liczba potworów,
sufit exp/h z respawnu (górna granica, NIE pomiar), cios najgroźniejszego (`potwory.json` atak_max_szac, zawyżony),
skład i trasy bota, które już przechodzą przez tę składową (`bot: -` = nikt tam nie chodzi).
Spawn trafia do składowej, w której leży jego środek albo najbliższe pole w promieniu 4.
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import mapa  # noqa: E402

MIASTA = {   # świątynia (x, y, z), obszar szukania (x0, y0, x1, y1)
    "Thais": ((32369, 32241, 7), (32180, 31990, 32600, 32420)),
    "Edron": ((33217, 31814, 8), (33000, 31640, 33320, 31960)),
    "Rookgaard": ((32097, 32219, 7), (31890, 32030, 32170, 32310)),
    "Carlin": ((32360, 31782, 7), (32230, 31650, 32490, 31910)),
    "Venore": ((32957, 32076, 7), (32830, 31950, 33090, 32210)),
    "Kazordoon": ((32649, 31925, 11), (32540, 31810, 32760, 32040)),
    "Ab'Dendriel": ((32732, 31634, 7), (32600, 31500, 32860, 31770)),
}
POMIN = {"rabbit", "deer", "chicken", "sheep", "black sheep", "butterfly", "flamingo", "pig", "parrot", "squirrel",
         "cat", "dog", "seagull", "bat"}


def wczytaj_trasy():
    trasy = {}
    for f in glob.glob(str(ROOT / "trasy" / "*.json")):
        try:
            pk = json.load(open(f))
        except (OSError, ValueError):
            continue
        if isinstance(pk, list) and pk and isinstance(pk[0], list) and len(pk[0]) == 3:
            trasy[os.path.basename(f)[:-5]] = {tuple(p) for p in pk}
    return trasy


def skladowe(m, z, obszar):
    """{(x,y): nr} i {nr: liczba pól} dla piętra z w obszarze; schody/dziury (flaga 2) przerywają składową."""
    X0, Y0, X1, Y1 = obszar

    def ok(x, y):
        f = m.flagi(x, y, z)
        return bool(f & mapa.WIDZIANE and not f & (mapa.SCIANA | mapa.BEZ_DROGI))
    komp, rozm, n = {}, {}, 0
    for x in range(X0, X1 + 1):
        for y in range(Y0, Y1 + 1):
            if (x, y) in komp or not ok(x, y):
                continue
            n += 1
            st, komp[(x, y)], c = [(x, y)], n, 0
            while st:
                a, b = st.pop()
                c += 1
                for da in (-1, 0, 1):
                    for db in (-1, 0, 1):
                        q = (a + da, b + db)
                        if q in komp or not (X0 <= q[0] <= X1 and Y0 <= q[1] <= Y1) or not ok(*q):
                            continue
                        komp[q] = n
                        st.append(q)
            rozm[n] = c
    return komp, rozm


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--miasto", choices=sorted(MIASTA))
    ap.add_argument("--obszar", help="x0,y0,x1,y1 (zamiast --miasto)")
    ap.add_argument("--swiatynia", help="x,y,z do liczenia odległości (z --obszar)")
    ap.add_argument("--pietra", default="5-15", help="zakres pięter, np. 7-12")
    ap.add_argument("--max-cios", type=int, default=50, help="pomiń spoty z groźniejszym potworem (lvl 8-15: ~45-50)")
    ap.add_argument("--min-potworow", type=int, default=8)
    a = ap.parse_args(argv)
    if a.miasto:
        sw, obszar = MIASTA[a.miasto]
        nazwa = a.miasto
    elif a.obszar and a.swiatynia:
        obszar = tuple(int(v) for v in a.obszar.split(","))
        sw = tuple(int(v) for v in a.swiatynia.split(","))
        nazwa = "obszar"
    else:
        ap.error("podaj --miasto albo --obszar z --swiatynia")
    z0, z1 = (int(v) for v in a.pietra.split("-"))
    X0, Y0, X1, Y1 = obszar
    m = mapa.Mapa()
    P = json.loads((ROOT / "dane_tibia" / "serwer74" / "potwory_pelne.json").read_text())["potwory"]
    cios = {v["nazwa"]: v.get("atak_max_szac") or 0 for v in json.loads((ROOT / "dane_tibia" / "potwory.json").read_text())["potwory"]}
    trasy = wczytaj_trasy()
    sp = [(s["x"], s["y"], s["z"], p["nazwa"], s["ilosc"], s["respawn_s"], p["exp"]) for p in P for s in p.get("spawny", [])
          if X0 <= s["x"] <= X1 and Y0 <= s["y"] <= Y1 and z0 <= s["z"] <= z1 and p["nazwa"] not in POMIN]
    wyn = []
    for z in sorted({s[2] for s in sp}):
        komp, rozm = skladowe(m, z, obszar)
        gr = {}
        for s in (s for s in sp if s[2] == z):
            k = next((komp[(s[0] + dx, s[1] + dy)] for r in range(5) for dx in range(-r, r + 1) for dy in range(-r, r + 1)
                      if (s[0] + dx, s[1] + dy) in komp), None)
            if k:
                gr.setdefault(k, []).append(s)
        for k, ss in gr.items():
            sklad = {}
            for s in ss:
                sklad[s[3]] = sklad.get(s[3], 0) + s[4]
            ile = sum(sklad.values())
            cmax = max(cios.get(nm, 0) for nm in sklad)
            if ile < a.min_potworow or cmax > a.max_cios:
                continue
            cx = sum(s[0] * s[4] for s in ss) / ile
            cy = sum(s[1] * s[4] for s in ss) / ile
            pola = {q for q, v in komp.items() if v == k}
            bot = sorted(t for t, pts in trasy.items() if any(p[2] == z and (p[0], p[1]) in pola for p in pts))[:3]
            wyn.append((z, round(cx), round(cy), rozm[k], ile, round(sum(s[4] * s[6] * 3600 / s[5] for s in ss)), cmax,
                        round(max(abs(cx - sw[0]), abs(cy - sw[1]))), sklad, bot))
    for z, x, y, pola, ile, exp, cm, odl, sklad, bot in sorted(wyn, key=lambda w: -w[5]):
        s = ", ".join(f"{k} {v}" for k, v in sorted(sklad.items(), key=lambda t: -t[1]))
        print(f"{nazwa:9} z{z:<2} ({x},{y}) odl {odl:3} | {pola:5} pól | {ile:3} potw | sufit {exp:5} | cios {cm:3} | {s} | bot: {','.join(bot) or '-'}")


if __name__ == "__main__":
    main()
