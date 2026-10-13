#!/usr/bin/env python3
"""Generator tras wypadu do miasta (do_miasta / z_miasta) z pełnej mapy (mapa.py) i nagranych tras łowiska.

  generuj_trase_miasta.py troll    [--zapisz]   troll_cave (z8/z9) -> Thais, sklep Gorna (z7) i z powrotem
  generuj_trase_miasta.py kanaly   [--zapisz]   kanały Thais (z8, lądowanie dziury (32360,32242)) -> Gorn i z powrotem

Bez --zapisz tylko raport (długości, przejścia). Zapisuje trasy/<prefiks>_do_miasta.json, <prefiks>_z_miasta.json
(listy punktów x,y,z jak każda trasa) i .meta z przejściami pięter.

Model przejść (potwierdzony na nagraniach do_miasta/z_miasta/troll_cave i w pietra.py):
  w dół:  krok na pole T (flaga mapy 2 = "bez drogi") na piętrze z, lądowanie (T.x, T.y, z+1);
  w górę: z pola obok R (albo z samego R) na piętrze z, gdzie nad R (piętro z-1) jest dziura (flaga 2):
          drabina/lina na R, lądowanie (R.x, R.y+1, z-1).
Trasa troll_do_miasta zaczyna się od ODWRÓCONEJ trasy troll_cave (z poprawionymi przejściami), więc działa z każdego
pola jaskini (z8 i z9), a kończy się przy Gornie (sprzedaje torch). UWAGA: pozycja Gorna (Home z danych Tibiantis)
i przejścia po minimapie są niezweryfikowane na żywo; pierwszy wypad obserwować.
"""
import heapq
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
KATALOG = Path(__file__).resolve().parent
sys.path.insert(0, str(KATALOG))
import mapa as _mapa  # noqa: E402

TRASY = KATALOG / "trasy"
GORN_HOME = (32377, 32200, 7)          # NPC Gorn (Tibiantis: Home, promień 3); sprzedaje torch
KOSZT_W_DOL, KOSZT_W_GORE = 6, 8
RUCHY = ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 3), (1, -1, 3), (-1, 1, 3), (-1, -1, 3))


class Graf:
    def __init__(self, m):
        self.m = m

    def idzie(self, x, y, z):
        f = self.m.flagi(x, y, z)
        return bool(f & 1) and not f & 4 and not f & 2

    def sasiedzi(self, p):
        """(q, koszt, typ) z pola p: chodzenie, w dół (krok na dziurę), w górę (R obok albo własne)."""
        x, y, z = p
        for dx, dy, c in RUCHY:
            q = (x + dx, y + dy, z)
            if self.idzie(*q):
                yield q, c, "idz"
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            t = (x + dx, y + dy, z)
            f = self.m.flagi(*t)
            if f & 1 and f & 2 and not f & 4:
                l = (t[0], t[1], z + 1)
                if self.idzie(*l):
                    yield l, KOSZT_W_DOL, "dol"
        if z > 0:
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                r = (x + dx, y + dy, z)
                if not self.idzie(*r):
                    continue
                g = self.m.flagi(r[0], r[1], z - 1)
                if g & 1 and g & 2:
                    l = (r[0], r[1] + 1, z - 1)
                    if self.idzie(*l):
                        yield l, KOSZT_W_GORE, "gora"

    def astar(self, start, cel, limit=400000):
        """Najkrótsza droga start -> cel (dokładnie to pole); [(pole, typ_wejscia)] z pierwszym (start, None)."""
        start, cel = tuple(start), tuple(cel)
        d = {start: 0}
        skad = {start: None}
        pq = [(0, 0, start)]
        n = 0
        while pq:
            _, c, p = heapq.heappop(pq)
            if c > d[p]:
                continue
            if p == cel:
                wyn = []
                while p is not None:
                    prev = skad[p]
                    wyn.append((p, prev[1] if prev else None))
                    p = prev[0] if prev else None
                return wyn[::-1]
            n += 1
            if n > limit:
                return None
            for q, cc, t in self.sasiedzi(p):
                nc = c + cc
                if nc < d.get(q, 1 << 60):
                    d[q] = nc
                    skad[q] = (p, t)
                    h = max(abs(q[0] - cel[0]), abs(q[1] - cel[1])) + (0 if q[2] == cel[2] else 0)
                    heapq.heappush(pq, (nc + h, nc, q))
        return None


def rzadko(sciezka, co=3):
    """Przerzedza drogę z A* (co `co`-te pole + zakręty + końce piętra); [(x,y,z)]. Pola przy przejściach zostają."""
    pts = [p for p, _ in sciezka]
    typy = [t for _, t in sciezka]
    n = len(pts)
    zostaw = {0, n - 1}
    for i in range(1, n):
        if typy[i] in ("dol", "gora"):
            zostaw.update({i - 1, i, min(n - 1, i + 1)})
    ost = 0
    for i in range(1, n - 1):
        kier = (pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) != (pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
        if pts[i][2] != pts[i - 1][2] or pts[i][2] != pts[i + 1][2]:
            zostaw.add(i)
        elif i - ost >= co or (kier and i - ost >= 2):
            zostaw.add(i)
        if i in zostaw:
            ost = i
    return [pts[i] for i in sorted(zostaw)]


def scal(*listy):
    wyn = []
    for l in listy:
        for p in l:
            p = (int(p[0]), int(p[1]), int(p[2]))
            if not wyn or wyn[-1] != p:
                wyn.append(p)
    return wyn


def napraw_przejscia(g, punkty):
    """Między sąsiednimi punktami na różnych piętrach wstawia drogę z grafu (poprawne pole przejścia).
    -> (lista, ostrzezenia)."""
    wyn, ost = [], []
    for p in punkty:
        p = tuple(p)
        if wyn and wyn[-1][2] != p[2]:
            a = wyn[-1]
            s = g.astar(a, p, limit=60000)
            if s is None:
                ost.append(f"brak przejścia {a} -> {p} w grafie, zostaje bezpośrednie")
            else:
                for q, _ in s[1:-1]:
                    wyn.append(q)
        wyn.append(p)
    return wyn, ost


def opisz_przejscia(punkty):
    spec = [{"idx": 0, "typ": "start", "komentarz": "początek trasy"}]
    for i in range(len(punkty) - 1):
        a, b = punkty[i], punkty[i + 1]
        if a[2] != b[2]:
            spec.append({"idx": i, "typ": "przed_zmiana_pietra", "komentarz": f"ostatnie pole na piętrze {a[2]}, potem piętro {b[2]}"})
            spec.append({"idx": i + 1, "typ": "schody_w_dol" if b[2] > a[2] else "schody_w_gore",
                         "komentarz": f"zmiana piętra {a[2]} -> {b[2]}, z ({a[0]},{a[1]})"})
    return {"specjalne": spec}


def stoisko(g, home, od):
    """Pole przy NPC: osiągalne z `od`, Chebyshev 1 od Home (potem 2), najtańsze. -> (pole, droga)."""
    kand = []
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            q = (home[0] + dx, home[1] + dy, home[2])
            c = max(abs(dx), abs(dy))
            if c >= 1 and g.idzie(*q):
                kand.append((c, abs(q[0] - od[0]) + abs(q[1] - od[1]), q))
    kand.sort()
    for _, _, q in kand:
        s = g.astar(od, q)
        if s is not None:
            return q, s
    return None, None


def zbuduj(nazwa, m):
    g = Graf(m)
    ostrz = []
    if nazwa == "troll":
        troll = [tuple(p) for p in json.loads((TRASY / "troll_cave.json").read_text())]
        wejscie = troll[0]
        rev, ow = napraw_przejscia(g, list(reversed(troll)))
        ostrz += ow
        cel, droga = stoisko(g, GORN_HOME, wejscie)
        if droga is None:
            raise SystemExit("brak drogi z troll_cave do Gorna")
        do = scal(rev, rzadko(droga))
        powrot = g.astar(cel, wejscie)
        if powrot is None:
            raise SystemExit("brak drogi powrotnej z Gorna do troll_cave")
        z = scal(rzadko(powrot))
        prefiks = "troll"
    elif nazwa == "kanaly":
        wejscie = (32360, 32242, 8)
        cel, droga = stoisko(g, GORN_HOME, wejscie)
        if droga is None:
            raise SystemExit("brak drogi z kanałów do Gorna")
        do = scal(rzadko(droga))
        powrot = g.astar(cel, wejscie)
        if powrot is None:
            raise SystemExit("brak drogi powrotnej z Gorna do kanałów")
        z = scal(rzadko(powrot))
        prefiks = "thais_kanaly"
    else:
        raise SystemExit(f"nieznana trasa {nazwa}")
    return prefiks, do, z, cel, ostrz


def main(argv):
    if not argv or argv[0] not in ("troll", "kanaly"):
        print(__doc__)
        return 1
    m = _mapa.Mapa()
    prefiks, do, z, cel, ostrz = zbuduj(argv[0], m)
    print(f"{prefiks}: do_miasta {len(do)} pkt (z{do[0][2]} -> z{do[-1][2]}), z_miasta {len(z)} pkt, stoisko {cel}")
    for o in ostrz:
        print("UWAGA:", o)
    for nazwa, pts in (("do_miasta", do), ("z_miasta", z)):
        zm = [(i, pts[i], pts[i + 1]) for i in range(len(pts) - 1) if pts[i][2] != pts[i + 1][2]]
        print(f"  {nazwa}: przejścia pięter {[(i, a, b) for i, a, b in zm]}")
    if "--zapisz" in argv:
        for sufiks, pts in (("do_miasta", do), ("z_miasta", z)):
            plik = TRASY / f"{prefiks}_{sufiks}.json"
            plik.write_text(json.dumps([list(p) for p in pts]))
            (TRASY / f"{prefiks}_{sufiks}.meta").write_text(json.dumps(opisz_przejscia(pts), ensure_ascii=False, indent=1))
            print("zapisano", plik)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
