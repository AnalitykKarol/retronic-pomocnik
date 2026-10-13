import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""Testy offline pomocnik/mapa.py na prawdziwym pliku map74.otmm (+ pomiary)."""
import json, random, sys, time, tracemalloc
from pathlib import Path
sys.dont_write_bytecode = True
P = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(P))
import mapa as M

ok = bledy = 0
def sprawdz(warunek, opis):
    global ok, bledy
    if warunek: ok += 1
    else: bledy += 1; print("BŁĄD:", opis)

PAM = "--pamiec" in sys.argv
if PAM: tracemalloc.start()
t = time.perf_counter(); m = M.Mapa(); t_start = time.perf_counter() - t
pam_start = tracemalloc.get_traced_memory()[0] if PAM else 0
trasa = [tuple(p) for p in json.loads((P / "trasy/kanaly2.json").read_text())]

sprawdz(m.bloki == 3267, f"bloków {m.bloki}")
sprawdz(m.pole(32032, 32150, 11) == (1, 121, 12), "pole trasy")
sprawdz(m.pole(32033, 32150, 11) == (5, 114, 0), "ściana")
sprawdz(m.przechodnie(32032, 32150, 11) is True, "trasa przechodnia")
sprawdz(m.przechodnie(32033, 32150, 11) is False, "ściana nieprzechodnia")
sprawdz(m.przechodnie(100, 100, 7) is None, "brak bloku -> None")
sprawdz(m.przechodnie(0, 0, 3) is None, "brak bloku z=3 -> None")
sprawdz(all(m.przechodnie(*p) for p in trasa), "wszystkie pola trasy przechodnie")
sprawdz(all(m.flagi(*p) == 1 for p in trasa), "flagi pól trasy == 1")
sprawdz(not any(m.schody_lub_dziura(*p) for p in trasa), "trasa bez schodów")
sprawdz(m.schody_lub_dziura(32034, 32124, 11) is True, "znane schody (3,210)")
sprawdz(m.przechodnie(32034, 32124, 11) is True, "schody są przechodnie")
# pole widziane w bloku, ale niewidziane
nw = next((x, y) for x in range(32000, 32064) for y in range(32128, 32192) if m.flagi(x, y, 11) == 0) if any(
    m.flagi(x, y, 11) == 0 for x in range(32000, 32064) for y in range(32128, 32192)) else None
if nw: sprawdz(m.przechodnie(nw[0], nw[1], 11) is None, "niewidziane -> None")

# droga omija ścianę
d = m.droga((32032, 32150, 11), (32034, 32151), dlugosc=0)
sprawdz(d is not None and d[-1][:2] == (32034, 32151), f"droga do celu {d}")
sprawdz(d and all(p[:2] != (32033, 32150) for p in d), "droga omija ścianę")
sprawdz(d and all(m.przechodnie(*p) for p in d), "droga po przechodnich")
d1 = m.droga((32032, 32150, 11), (32034, 32151), dlugosc=1)
sprawdz(d1 is not None and max(abs(d1[-1][0] - 32034), abs(d1[-1][1] - 32151)) <= 1, f"dlugosc=1 {d1}")
sprawdz(m.droga((32032, 32150, 11), (32033, 32151), dlugosc=1) == [], "już przy celu -> []")
# zajęte pole blokujące: korytarz
dz = m.droga((32032, 32150, 11), (32034, 32151), zajete=[(32033, 32151)], dlugosc=0)
sprawdz(dz is None or all(p[:2] != (32033, 32151) for p in dz), f"omija zajęte {dz}")
dz3 = m.droga((32032, 32150, 11), (32034, 32151), zajete=[(32033, 32151, 11)], dlugosc=0)
sprawdz(dz == dz3, "zajęte jako (x,y,z)")
# bez skosów: kolejne pola sąsiadują prosto
ds = m.droga(trasa[0], trasa[25][:2], skosy=False)
sprawdz(ds and all(abs(a[0]-b[0]) + abs(a[1]-b[1]) == 1 for a, b in zip([trasa[0]] + ds, ds)), "bez skosów")
# cel w ścianie / poza mapą -> None w limicie
sprawdz(m.droga((32032, 32150, 11), (32033, 32150), dlugosc=0, limit=2000) is None, "cel w ścianie -> None")
sprawdz(m.droga((32032, 32150, 11), (10, 10), limit=500) is None, "nieosiągalny -> None (limit)")
# droga nie wchodzi na schody (gdy schody=False)
sch = [(32034, 32124)]
dd = m.droga((32034, 32128, 11), (32034, 32118), limit=20000)
sprawdz(dd is None or all(p[:2] not in sch for p in dd), "omija schody")
# długości drogi optymalne wzgl. Dijkstry bez heurystyki (porównanie z cavebot-podobnym BFS)
def dijkstra(start, cel, dl):
    import heapq
    z = start[2]; pq = [(0, start[:2])]; best = {start[:2]: 0}
    while pq:
        c, (x, y) = heapq.heappop(pq)
        if c != best[(x, y)]: continue
        if max(abs(x-cel[0]), abs(y-cel[1])) <= dl and (x, y) != start[:2]: return c
        for dx, dy, k in ((1,0,1),(-1,0,1),(0,1,1),(0,-1,1),(1,1,3),(1,-1,3),(-1,1,3),(-1,-1,3)):
            n = (x+dx, y+dy)
            if m.flagi(n[0], n[1], z) & 7 == 1 and c + k < best.get(n, 1 << 30):
                best[n] = c + k; heapq.heappush(pq, (c + k, n))
def koszt(start, d):
    return sum(1 if abs(a[0]-b[0]) + abs(a[1]-b[1]) == 1 else 3 for a, b in zip([start] + d, d))

random.seed(7)
pary = []
while len(pary) < 200:
    a, b = random.sample(trasa, 2)
    if 5 <= max(abs(a[0]-b[0]), abs(a[1]-b[1])) <= 30: pary.append((a, b))
zgodne = 0; czasy = []; dl = []
for a, b in pary:
    t = time.perf_counter(); d = m.droga(a, b[:2]); czasy.append(time.perf_counter() - t)
    dl.append(len(d) if d else -1)
    if d is not None and koszt(a, d) == dijkstra(a, b, 1): zgodne += 1
sprawdz(zgodne == len(pary), f"A* optymalny jak Dijkstra: {zgodne}/{len(pary)}")
czasy.sort()

# pomiar zapytania o pole (bloki już w cache)
pola = [(random.randint(31950, 32100), random.randint(32100, 32200), 11) for _ in range(100000)]
for p in pola: m.flagi(*p)
t = time.perf_counter()
for x, y, z in pola: m.flagi(x, y, z)
t_flagi = (time.perf_counter() - t) / len(pola)
t = time.perf_counter()
for x, y, z in pola: m.przechodnie(x, y, z)
t_przech = (time.perf_counter() - t) / len(pola)
pam = tracemalloc.get_traced_memory() if PAM else (0, 0)
# zimny start: wszystkie bloki
t = time.perf_counter(); m2 = M.Mapa()
for kb in list(m2._spis): m2._blok(kb)
t_wszystko = time.perf_counter() - t
pam_wszystko = tracemalloc.get_traced_memory()[0] if PAM else 0
if PAM: tracemalloc.stop()

print(f"start (spis bloków): {t_start*1000:.1f} ms, pamięć {pam_start/1e6:.2f} MB")
print(f"flagi(): {t_flagi*1e6:.2f} µs, przechodnie(): {t_przech*1e6:.2f} µs")
print(f"droga 200 par z kanaly2 (5-30 pól): mediana {czasy[100]*1000:.2f} ms, p95 {czasy[190]*1000:.2f} ms, "
      f"max {czasy[-1]*1000:.2f} ms; długości {min(dl)}-{max(dl)}")
print(f"pamięć po testach: {pam[0]/1e6:.2f} MB (szczyt {pam[1]/1e6:.2f}); bloki w cache {len(m._bloki)}")
print(f"rozpakowanie całej mapy: {t_wszystko:.2f} s, {pam_wszystko/1e6:.1f} MB (obie mapy)")
print(f"{ok}/{ok + bledy} OK")
sys.exit(1 if bledy else 0)
