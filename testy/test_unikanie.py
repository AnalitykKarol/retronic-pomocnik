import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types, math
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import unikanie
from collections import deque

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

KONF = dict(UNIKANIE=1, UNIKANIE_PROMIEN=9, UNIKANIE_PROMIEN_MAX=14, UNIKANIE_DEBOUNCE=1.5, UNIKANIE_ZNIKL_S=10.0,
            UNIKANIE_MOB_PROMIEN=4, UNIKANIE_PUNKT_D=6, UNIKANIE_DROGA_MIN=4, UNIKANIE_BLOK_S=45.0,
            UNIKANIE_SPOT_S=180.0, UNIKANIE_POWIADOM_S=300.0)

def cheb(a, b): return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

class Swiat:
    """Siatka pól `wolne`, jeden bot (uproszczony cavebot: stosuje Ruch, idzie po drodze, zalicza punkty)."""
    def __init__(s, wolne, punkty, poz, gracze, konf=None, nazwa="Ja"):
        s.wolne = set(wolne); s.punkty = [tuple(p) for p in punkty]; s.poz = tuple(poz); s.idx = min(range(len(s.punkty)), key=lambda i: cheb(s.punkty[i], s.poz))
        s.gracze = {n: list(p) for n, p in gracze.items()}    # nick -> [x,y] (None = nieobecny)
        s.t = 0.0; s.zd = []; s.pow = []; s.logi = []; s.nazwa = nazwa; s.z = 7
        k = dict(KONF, **(konf or {}))
        s.u = unikanie.Unikanie(types.SimpleNamespace(**k), zegar=lambda: s.t, log=s.logi.append,
                                zdarzenie=lambda typ, **d: s.zd.append((typ, d)),
                                powiadom=lambda *a, **kw: s.pow.append((s.t, a)))
        s.trasa = []; s.min_odl = 999; s.ruchy = []; s.moby = []; s.min_mob = 999
    def lista(s):
        l = [{"id": 1, "nazwa": s.nazwa, "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.z, "hp": 100}]
        for i, (n, p) in enumerate(s.gracze.items()):
            if p is not None:
                l.append({"id": 100 + i, "nazwa": n, "gracz": True, "x": p[0], "y": p[1], "z": s.z, "hp": 100})
        for i, m in enumerate(s.moby):
            l.append({"id": 500 + i, "nazwa": "Rat", "gracz": False, "x": m[0], "y": m[1], "z": s.z, "hp": 100})
        return l
    def droga(s, start, cel, blok):
        blok = {tuple(b[:2]) for b in blok}
        start, cel = tuple(start[:2]), tuple(cel[:2])
        if start == cel: return []
        if cel in blok or cel not in s.wolne: return None
        skad = {start: None}; q = deque([start])
        while q:
            c = q.popleft()
            if c == cel: break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (c[0] + dx, c[1] + dy)
                    if n in s.wolne and n not in blok and n not in skad:
                        skad[n] = c; q.append(n)
        if cel not in skad: return None
        w = []; c = cel
        while c != start: w.append((c[0], c[1], s.z)); c = skad[c]
        return w[::-1]
    def krok(s, dt=0.4):
        n = len(s.punkty)
        s.u.obserwuj(s.lista(), s.poz + (s.z,), s.nazwa)
        if s.poz[:2] == s.punkty[s.idx][:2] and not (s.u.aktywne and s.u.gracze):
            s.idx = (s.idx + 1) % n
        r = s.u.decyduj(s.poz + (s.z,), s.punkty, s.idx, s.droga)
        path = None
        if r is not None:
            s.ruchy.append(r.tryb)
            if r.zmiana: s.idx = r.idx
            path = list(r.droga) if r.droga else None
            if r.pauza: s.t += r.pauza[0]
        if s.poz[:2] == s.punkty[s.idx][:2]:
            s.idx = (s.idx + 1) % n; path = None
        if path is None:
            path = s.droga(s.poz, s.punkty[s.idx][:2], [])
        if path:
            nxt = path[0][:2]
            if not any(p is not None and tuple(p) == nxt for p in s.gracze.values()):
                s.poz = nxt
        s.trasa.append((s.t, s.poz))
        for p in s.gracze.values():
            if p is not None: s.min_odl = min(s.min_odl, cheb(s.poz, p))
        for m in s.moby: s.min_mob = min(s.min_mob, cheb(s.poz, m))
        s.t += dt
    def bieg(s, sekundy, fn=None):
        k = s.t + sekundy
        while s.t < k:
            if fn: fn(s)
            s.krok()
    def max_postoj(s, od=0.0):
        """Najdłuższy czas bez zmiany pozycji."""
        ost, t0, mx = None, None, 0.0
        for t, p in s.trasa:
            if t < od: continue
            if p != ost: ost, t0 = p, t
            mx = max(mx, t - t0)
        return mx

def prostokat(x0, x1, y0, y1): return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
def petla(x0, x1, y0, y1):
    return [(x, y0, 7) for x in range(x0, x1)] + [(x1, y, 7) for y in range(y0, y1)] + \
           [(x, y1, 7) for x in range(x1, x0, -1)] + [(x0, y, 7) for y in range(y1, y0, -1)]
def typy(s, t): return [d for tt, d in s.zd if tt == t]

# --- 0. brak gracza: nic się nie dzieje ---
s = Swiat(prostokat(80, 140, 80, 120), petla(90, 120, 95, 105), (90, 95), {})
s.bieg(30)
sprawdz("U0 bez gracza: unikanie nieaktywne, decyzje None", not s.u.aktywne and s.ruchy == [] and s.zd == [], (s.u.aktywne, s.zd))

# --- 1. gracz na trasie (otwarte pole): omija, trzyma >= 4, nie stoi ---
s = Swiat(prostokat(80, 140, 80, 120), petla(90, 120, 95, 105), (95, 95), {"Zbyszek": [105, 95]})
s.bieg(120)
sprawdz("U1 gracz na trasie: aktywacja po debounce (1 zdarzenie start z nickiem i odległością)",
        len(typy(s, "unikanie_start")) == 1 and typy(s, "unikanie_start")[0]["gracz"] == "Zbyszek"
        and typy(s, "unikanie_start")[0]["odl"] <= 9, typy(s, "unikanie_start"))
sprawdz("U1b nigdy bliżej niż 4 pola od gracza (start 10 pól od niego, marsz w jego stronę przed debounce)",
        s.min_odl >= 4, s.min_odl)
sprawdz("U1c bot nie zamarza (postój < 6 s) i zmienia punkty (log po polsku)",
        s.max_postoj() < 6 and len(typy(s, "unikanie_punkt")) >= 1 and any("punkt" in l for l in s.logi),
        (s.max_postoj(), len(typy(s, "unikanie_punkt"))))
pola = {p for _, p in s.trasa}
sprawdz("U1d trasa nadal się toczy: odwiedza punkty poza strefą 6 pól gracza (min. 25 różnych pól)",
        len(pola) >= 25 and all(cheb(p, (105, 95)) >= 4 for p in pola), len(pola))

# --- 1e. punkt rotacji po drugiej stronie: omijamy naokoło, nie przeskakujemy ściany ---
sciana = [p for p in prostokat(80, 140, 80, 120) if not (p[0] == 110 and p[1] != 95)]   # ściana x=110 z przejściem y=95
s = Swiat(sciana, [(100, 95, 7), (120, 95, 7)], (98, 95), {"Zbyszek": [108, 95]})
s.bieg(60)
sprawdz("U1e gracz w jedynym przejściu przed ścianą: nie przechodzimy przez niego (>= 3 pola), nie stoimy",
        s.min_odl >= 3 and s.max_postoj() < 8, (s.min_odl, s.max_postoj()))

# --- 2. gracz obok moba: cel pomijany ---
s = Swiat(prostokat(80, 140, 80, 120), petla(90, 120, 95, 105), (100, 100), {"Zbyszek": [108, 100]})
s.u.obserwuj(s.lista(), (100, 100, 7), "Ja")
poz = (100, 100, 7)
mob = lambda x, y, i=5: {"id": i, "nazwa": "Rat", "gracz": False, "x": x, "y": y, "z": 7, "hp": 100}
sprawdz("U2a mob 3 pola od gracza pomijany", s.u.pomin_moba(mob(105, 100), poz) is True)
sprawdz("U2b mob 5 pól od gracza (poza promieniem 4) nie jest pomijany", s.u.pomin_moba(mob(103, 100), poz) is False)
sprawdz("U2c mob obok nas przy graczu: bijemy (nie pomijamy)", s.u.pomin_moba(mob(s.poz[0] + 1, 100), poz) is False)
sprawdz("U2d mob 2 pola od nas i 3 od gracza: pomijany, ale gdy nas gryzie - nie",
        s.u.pomin_moba(mob(105, 100), (103, 100, 7)) is True and s.u.pomin_moba(mob(105, 100), (103, 100, 7), gryzie=True) is False)
sprawdz("U2e bez gracza żaden mob nie jest pomijany",
        unikanie.Unikanie(types.SimpleNamespace(**KONF)).pomin_moba(mob(105, 100), poz) is False)
# 15.10: mob obok nas, ale też tuż przy innym graczu (1 pole) i nas nie gryzie: to jego mob, nie bierzemy
s = Swiat(prostokat(80, 140, 80, 120), petla(90, 120, 95, 105), (100, 100), {"Quben": [102, 100]})
s.u.obserwuj(s.lista(), (100, 100, 7), "Ja")
sprawdz("U2j mob obok nas i obok gracza, nas nie bije: pomijany", s.u.pomin_moba(mob(101, 100), poz) is True)
sprawdz("U2k ten sam mob, gdy nas gryzie: bijemy", s.u.pomin_moba(mob(101, 100), poz, gryzie=True) is False)
s2 = Swiat(prostokat(80, 140, 80, 120), petla(90, 120, 95, 105), (100, 100), {"Zbyszek": [108, 100]}, konf=dict(UNIKANIE=0))
s2.bieg(10)
sprawdz("U2f UNIKANIE=0: nic nie robi (stare zachowanie)", not s2.u.aktywne and not s2.u.pomin_moba(mob(107, 100), s2.poz + (7,)))
s3 = Swiat(prostokat(80, 140, 80, 120), petla(90, 120, 95, 105), (100, 100), {"Zbyszek": [108, 100]})
s3.u.obserwuj(s3.lista(), (100, 100, 7), "Ja")
sprawdz("U2g moby przy graczu pomijane od razu (bez debounce unikania trasy)",
        s3.u.pomin_moba(mob(106, 100), (100, 100, 7)) is True and not s3.u.aktywne)

# --- 2h. mob przy graczu: droga nie przechodzi obok niego (nie wciągamy się w jego walkę) ---
s = Swiat(prostokat(80, 140, 80, 120), [(100, 100, 7), (120, 100, 7)], (100, 100), {"Zbyszek": [112, 104]})
s.moby = [(110, 100)]
s.bieg(40)
sprawdz("U2h mob 4 pola od gracza stoi na trasie: nie podchodzimy bliżej niż 2 pola do moba, gracza >= 4",
        s.min_mob >= 2 and s.min_odl >= 3, (s.min_mob, s.min_odl))
sprawdz("U2i moby przy graczu zapamiętane w Unikanie.moby", s.u.moby == [(110, 100)], s.u.moby)

# --- 3. gracz w korytarzu blokuje jedyną drogę: cofamy się, czekamy w ruchu, po 45 s inna opcja ---
kor = prostokat(60, 160, 100, 100)
s = Swiat(kor, [(x, 100, 7) for x in range(70, 151, 2)], (98, 100), {"Blokujacy": [120, 100]})
s.bieg(40)
sprawdz("U3a korytarz: trzymamy >= 4 pola przez pierwsze 40 s", s.min_odl >= 4, s.min_odl)
sprawdz("U3b korytarz: nie stoi (postój < 6 s), cofa się (tryb tyl/czekaj w decyzjach)",
        s.max_postoj() < 6 and ("tyl" in s.ruchy or "czekaj" in s.ruchy), (s.max_postoj(), set(s.ruchy)))
sprawdz("U3c log po polsku o cofaniu się", any("cofam" in l or "czekam w ruchu" in l for l in s.logi), s.logi[:5])
s.bieg(80)   # razem 120 s
inny = [d for d in typy(s, "unikanie_punkt") if "inny punkt rotacji" in d["powod"]]
sprawdz("U3d po 45 s bez zmiany: inny punkt rotacji (skan całej trasy) albo luz; nadal nie przez gracza i bez zamarznięcia",
        s.min_odl >= 3 and s.max_postoj() < 8 and (inny or typy(s, "unikanie_luz")), (s.min_odl, s.max_postoj(), [t for t, _ in s.zd]))
t_inny = next((i for i, (tt, d) in enumerate(s.zd) if tt == "unikanie_punkt" and "inny punkt" in d["powod"]), None)
sprawdz("U3e wybór innego punktu dopiero po ~45 s czekania w ruchu (log: po 4x s blokady)",
        any("po 4" in l and "blokady" in l for l in s.logi), [l for l in s.logi if "blokady" in l])

# --- 4. gracz znika: po 10 s powrót do normalnego planu ---
s = Swiat(prostokat(80, 140, 80, 120), petla(90, 120, 95, 105), (95, 95), {"Zbyszek": [105, 95]})
s.bieg(30)
a0 = s.u.aktywne
s.gracze["Zbyszek"] = None
s.bieg(6)
sprawdz("U4a po 6 s bez gracza unikanie jeszcze trwa (histereza 10 s)", a0 and s.u.aktywne)
s.bieg(8)
sprawdz("U4b po > 10 s bez gracza: koniec, zdarzenie unikanie_koniec z powodem",
        not s.u.aktywne and typy(s, "unikanie_koniec") and typy(s, "unikanie_koniec")[0]["powod"] == "gracz_zniknal", typy(s, "unikanie_koniec"))
r = s.u.decyduj(s.poz + (7,), s.punkty, s.idx, s.droga)
sprawdz("U4c po końcu decyduj() = None (cavebot idzie normalnym planem)", r is None)
s.gracze["Zbyszek"] = [s.poz[0] + 8, s.poz[1]]
s.bieg(1.0)
sprawdz("U4d powrót gracza (8 pól) na 1 s (< debounce) nie włącza unikania", not s.u.aktywne)
s.bieg(2.0)
sprawdz("U4e po debounce włącza ponownie", s.u.aktywne)

# --- 5. gracz wiecznie obok (przy trasie, nie na niej): 700 s, bez zamarznięcia, powiadomienia co 5 min ---
s = Swiat(prostokat(80, 140, 80, 120), petla(90, 120, 95, 105), (90, 95), {"Wieczny": [105, 109]})
s.bieg(700)
sprawdz("U5a wieczny gracz: ruch nie ustaje (postój < 8 s przez 700 s)", s.max_postoj() < 8, s.max_postoj())
sprawdz("U5b dystans >= 3 przez cały czas", s.min_odl >= 3, s.min_odl)
sprawdz("U5c powiadomienia: dokładnie 2 w 700 s (po 180 s i 5 min później), nie co tick",
        len(s.pow) == 2 and 175 <= s.pow[0][0] <= 190 and s.pow[1][0] - s.pow[0][0] >= 300, [t for t, _ in s.pow])
sprawdz("U5d treść: 'gracz Wieczny na spocie od N min'", "Wieczny" in s.pow[0][1][1] and "na spocie od" in s.pow[0][1][1], s.pow[0])
sprawdz("U5e bot nadal chodzi po trasie (odwiedził > 30 pól)", len({p for _, p in s.trasa}) > 30, len({p for _, p in s.trasa}))

# --- 6. zakresy: gracz dalej niż R2 się nie liczy; inne piętro i własna postać ignorowane ---
s = Swiat(prostokat(80, 160, 80, 120), petla(90, 120, 95, 105), (90, 95), {"Daleko": [90 + 15, 95]})
for _ in range(10): s.u.obserwuj(s.lista(), (90, 95, 7), "Ja"); s.t += 0.5
sprawdz("U6a gracz 15 pól (> R2=14): ignorowany", not s.u.aktywne and s.u.gracze == [])
s.gracze["Daleko"] = [90 + 12, 95]
for _ in range(10): s.u.obserwuj(s.lista(), (90, 95, 7), "Ja"); s.t += 0.5
sprawdz("U6b gracz 12 pól (R < odl <= R2): widziany, ale nie włącza unikania (próg R=9)", len(s.u.gracze) == 1 and not s.u.aktywne)
s = Swiat(prostokat(80, 160, 80, 120), petla(90, 120, 95, 105), (90, 95), {})
l = s.lista() + [{"id": 9, "nazwa": "Pietro", "gracz": True, "x": 92, "y": 95, "z": 8, "hp": 100}]
for _ in range(8):
    s.u.obserwuj(l, (90, 95, 7), "Ja"); s.t += 0.5
sprawdz("U6c gracz z innego piętra i własna postać ignorowani", not s.u.aktywne and s.u.gracze == [])
s.gracze["Czaszka"] = [93, 95]
l = s.lista(); l[-1]["czaszka"] = 1
s.u.obserwuj(l, (90, 95, 7), "Ja")
sprawdz("U6d lista graczy zawiera tylko obcych (bez nas)", [g["nazwa"] for g in s.u.gracze] == ["Czaszka"])

# --- 7. powiadomienie: odstęp 5 min i tylko gdy gracz faktycznie jest ---
s = Swiat(prostokat(80, 140, 80, 120), petla(90, 120, 95, 105), (90, 95), {"A": [105, 109]})
s.bieg(179)
n0 = len(s.pow)
s.bieg(10)
sprawdz("U7 powiadomienie dopiero po 3 min obecności", n0 == 0 and len(s.pow) == 1, (n0, len(s.pow)))

# --- 8. pokrętła na żywo: zmiana stałej w konf od razu działa ---
s = Swiat(prostokat(80, 140, 80, 120), petla(90, 120, 95, 105), (100, 100), {"Zbyszek": [108, 100]})
s.u.obserwuj(s.lista(), (100, 100, 7), "Ja")
sprawdz("U8a UNIKANIE_MOB_PROMIEN=4 domyślnie: mob 3 pola od gracza pomijany", s.u.pomin_moba(mob(105, 100), (100, 100, 7)) is True)
s.u.konf.UNIKANIE_MOB_PROMIEN = 2
sprawdz("U8b pokrętło UNIKANIE_MOB_PROMIEN=2: mob 3 pola od gracza już nie jest pomijany",
        s.u.pomin_moba(mob(105, 100), (100, 100, 7)) is False)

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
