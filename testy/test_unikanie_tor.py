import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types, math
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import unikanie
from collections import deque

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

KONF = dict(UNIKANIE_TOR=1, UNIKANIE_TOR_OKNO_S=4.0, UNIKANIE_TOR_RUCH_MIN=2, UNIKANIE_TOR_ZASIEG=12, UNIKANIE_TOR_LOOK=8,
            UNIKANIE_TOR_PAMIEC_S=25.0, UNIKANIE=1, UNIKANIE_PROMIEN=9, UNIKANIE_PROMIEN_MAX=14, UNIKANIE_DEBOUNCE=1.5, UNIKANIE_ZNIKL_S=10.0,
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


def idz_po(punkty, i0, tempo, znika_o=None):
    """Gracz idzie po `punkty` od indeksu i0, jedno pole co `tempo` s; od `znika_o` s go nie ma (None w pozycji)."""
    st = {"i": i0, "nast": 0.0}
    def fn(s):
        if znika_o is not None and s.t >= znika_o:
            s.gracze["Z"] = None
            return
        if s.t >= st["nast"]:
            st["i"] = (st["i"] + 1) % len(punkty)
            s.gracze["Z"] = [punkty[st["i"]][0], punkty[st["i"]][1]]
            st["nast"] = s.t + tempo
    return fn

def przebieg(konf, start_bot, start_gracz, T, punkty=None, teren=None, tempo=0.5, znika_o=None):
    punkty = punkty or petla(90, 120, 95, 105)
    s = Swiat(teren or prostokat(80, 140, 80, 120), punkty, start_bot, {"Z": list(start_gracz)}, konf=konf)
    fn = idz_po(punkty, [tuple(p[:2]) for p in punkty].index(tuple(start_gracz)), tempo, znika_o)
    odl = []
    k = s.t + T
    while s.t < k:
        fn(s); s.krok()
        if s.gracze["Z"] is not None: odl.append(cheb(s.poz, tuple(s.gracze["Z"])))
    return s, odl

def blisko(odl, r=5): return sum(1 for d in odl if d <= r) / max(1, len(odl))

# --- T1. gracz idzie przed nami trasą bota (ta sama pętla, ten sam kierunek): dawniej bot gonił go punkt po punkcie ---
s0, o0 = przebieg(dict(UNIKANIE_TOR=0), (95, 95), (99, 95), 60)
s1, o1 = przebieg({}, (95, 95), (99, 95), 60)
sprawdz("T1a dawne zachowanie (TOR=0): bot dogania gracza (>= 12% czasu w 5 polach)", blisko(o0) >= 0.12, blisko(o0))
sprawdz("T1b z torem: czas w 5 polach od gracza co najmniej 3x krótszy", blisko(o1) * 3 <= blisko(o0), (blisko(o1), blisko(o0)))
sprawdz("T1c z torem: nie bliżej niż 4 pola, nie stoi (postój < 6 s)", min(o1) >= 4 and s1.max_postoj() < 6, (min(o1), s1.max_postoj()))
sprawdz("T1d z torem: log po polsku 'nie idę za graczem' i zdarzenie unikanie_tor z kierunkiem",
        any("nie idę za graczem" in l for l in s1.logi) and typy(s1, "unikanie_tor") and typy(s1, "unikanie_tor")[0]["kier"][0] > 0,
        (s1.logi[:3], typy(s1, "unikanie_tor")[:1]))
sprawdz("T1e z torem: bot cofa się od gracza (tryb 'tyl' w decyzjach)", "tyl" in s1.ruchy, set(map(str, s1.ruchy)))

# --- T2. gracz 2 pola przed nami, ten sam kierunek (jak 18:27 17.10): z torem nie wchodzimy mu na plecy ---
s2, o2 = przebieg({}, (95, 95), (97, 95), 40)
s2o, o2o = przebieg(dict(UNIKANIE_TOR=0), (95, 95), (97, 95), 40)
sprawdz("T2a gracz 2 pola przed nami: z torem rzadziej w 5 polach od niego niż bez toru", blisko(o2) < blisko(o2o),
        (blisko(o2), blisko(o2o)))
sprawdz("T2b z torem postój < 6 s", s2.max_postoj() < 6, s2.max_postoj())

# --- T3. gracz znika z widoku na naszej trasie: "duch" 25 s trzyma nas z dala od jego kierunku; bez toru wracamy od razu ---
def x_max_po(s, od):
    return max(p[0] for t, p in s.trasa if t >= od)
sa, _ = przebieg({}, (95, 95), (99, 95), 60, znika_o=10.0)
sb, _ = przebieg(dict(UNIKANIE_TOR=0), (95, 95), (99, 95), 60, znika_o=10.0)
sprawdz("T3a bez toru po zniknięciu gracza bot idzie dalej jego torem (x > 108 w 35 s po zniknięciu)", x_max_po(sb, 10.0) > 108, x_max_po(sb, 10.0))
sprawdz("T3b z torem przez pamięć (25 s) bot nie idzie jego torem (x <= 100 w 20 s po zniknięciu)",
        max(p[0] for t, p in sa.trasa if 10.0 <= t <= 30.0) <= 100, max(p[0] for t, p in sa.trasa if 10.0 <= t <= 30.0))
sprawdz("T3c po pamięci (25 s + 10 s) unikanie się kończy, powrót do normalnego planu", not sa.u.aktywne and not sa.u.duchy, (sa.u.aktywne, sa.u.duchy))
sprawdz("T3d zdarzenie unikanie_tor oznaczone jako duch", any(d.get("duch") for d in typy(sa, "unikanie_tor")), typy(sa, "unikanie_tor")[:3])

# --- T4. gracz stoi (nie ma kierunku): zachowanie jak bez toru ---
kor = prostokat(60, 160, 100, 100)
sa = Swiat(kor, [(x, 100, 7) for x in range(70, 151, 2)], (98, 100), {"Blokujacy": [120, 100]}, konf=dict(UNIKANIE_TOR=1))
sb = Swiat(kor, [(x, 100, 7) for x in range(70, 151, 2)], (98, 100), {"Blokujacy": [120, 100]}, konf=dict(UNIKANIE_TOR=0))
sa.bieg(60); sb.bieg(60)
sprawdz("T4 stojący gracz: ta sama trasa z torem i bez (brak kierunku = brak zmian)", sa.trasa == sb.trasa and not typy(sa, "unikanie_tor"),
        (len(sa.trasa), len(sb.trasa)))

# --- T5. brak alternatywy: korytarz, trasa tylko przed nami, gracz odchodzi naszym torem: nie zawieszamy bota (stare zachowanie) ---
kor2 = prostokat(60, 160, 100, 100)
punkty5 = [(x, 100, 7) for x in range(70, 151, 3)]
s5, o5 = przebieg({}, (70, 100), (76, 100), 40, punkty=punkty5, teren=kor2, tempo=0.6)
sprawdz("T5 korytarz, jedyna droga za graczem: bot nie stoi (postój < 8 s) i jest bez błędów", s5.max_postoj() < 8, s5.max_postoj())

# --- T6. UNIKANIE_TOR=0 i brak klucza w konfiguracji: identyczna trasa, brak zdarzeń toru ---
def bez_klucza():
    pts = petla(90, 120, 95, 105)
    sw = Swiat(prostokat(80, 140, 80, 120), pts, (95, 95), {"Z": [99, 95]})
    sw.u.konf = types.SimpleNamespace(**{k: v for k, v in KONF.items() if not k.startswith("UNIKANIE_TOR")})
    fn = idz_po(pts, [tuple(p[:2]) for p in pts].index((99, 95)), 0.5)
    k = sw.t + 40
    while sw.t < k:
        fn(sw); sw.krok()
    return sw
sa, _ = przebieg(dict(UNIKANIE_TOR=0), (95, 95), (99, 95), 40)
sb = bez_klucza()
sprawdz("T6 pokrętło 0 i brak pokrętła: ta sama trasa bota, zero zdarzeń toru, brak duchów",
        sa.trasa == sb.trasa and not typy(sa, "unikanie_tor") and not typy(sb, "unikanie_tor") and sa.u.duchy == [] and sb.u.duchy == [],
        (len(sa.trasa), len(sb.trasa)))

# --- T9. TOR=0: budżet A* jak w bazie a6026dc (51 wywołań droga_fn, gdy żadna droga nie przechodzi); dawniej +1 po zmianie pętli ---
def wywolania_astar(konf):
    t = [0.0]; wyw = []
    u = unikanie.Unikanie(types.SimpleNamespace(**dict(KONF, UNIKANIE_DEBOUNCE=0, **konf)), zegar=lambda: t[0], log=lambda *a: None,
                          zdarzenie=lambda *a, **k: None, powiadom=lambda *a, **k: None)
    pts = [(100 + i, 100, 7) for i in range(60)]
    lista = [{"id": 1, "nazwa": "X", "gracz": True, "x": 106, "y": 100, "z": 7, "hp": 100}]
    u.obserwuj(lista, (100, 100, 7), "Ja"); u.obserwuj(lista, (100, 100, 7), "Ja")
    u.decyduj((100, 100, 7), pts, 20, lambda a, b, c: wyw.append(b))
    return len(wyw)
sprawdz("T9 TOR=0: dokładnie 51 wywołań A* (wartość z bazy a6026dc)", wywolania_astar(dict(UNIKANIE_TOR=0)) == 51, wywolania_astar(dict(UNIKANIE_TOR=0)))

# --- T10. wszystkie punkty trasy bliżej niż UNIKANIE_PUNKT_D od gracza; ten idzie na wschód, nasza trasa też: czekamy w ruchu z tyłu ---
def stan10(tor):
    t = [0.0]
    u = unikanie.Unikanie(types.SimpleNamespace(**dict(KONF, UNIKANIE_TOR=tor)), zegar=lambda: t[0], log=lambda *a: None,
                          zdarzenie=lambda *a, **k: None, powiadom=lambda *a, **k: None)
    u.aktywne, u.od, u.ok_od = True, 0.0, 0.0
    u.gracze = [{"id": 1, "nazwa": "Z", "x": 101, "y": 100, "z": 7, "odl": 3, "kier": (3, 0)}]
    pts = [(x, 100, 7) for x in (96, 97, 99, 100, 102, 103)]           # wszystkie w 5 polach od gracza (101,100)
    def droga(st, cel, blok):                                          # prosta po korytarzu; na wschód od nas (x >= 101) zamknięte
        if cel[0] >= 101 or cel[1] != 100: return None
        krok = 1 if cel[0] > st[0] else -1
        return [(x, 100, 7) for x in range(st[0] + krok, cel[0] + krok, krok)]
    return u, pts, droga
u, pts, droga = stan10(1)
r = u.decyduj((98, 100, 7), pts, 2, droga)
sprawdz("T10a z torem: nic do przodu/tyłu, więc czekanie w ruchu z tyłu (tryb 'czekaj', punkty na zachód od gracza)",
        r is not None and r.tryb == "czekaj" and pts[r.idx][0] <= 99, r)
u, pts, droga = stan10(0)
r0 = u.decyduj((98, 100, 7), pts, 2, droga)
sprawdz("T10b bez toru ta sama sytuacja: dawny wybór czekania (też bez postoju), tryb 'czekaj'", r0 is not None and r0.tryb == "czekaj", r0)
# gracz stoi (brak kierunku): filtr toru nie odrzuca niczego
u, pts, droga = stan10(1)
u.gracze[0]["kier"] = None
r1 = u.decyduj((98, 100, 7), pts, 2, droga)
sprawdz("T10c gracz stoi: wynik taki jak bez toru", r1 is not None and r0 is not None and (r1.tryb, r1.idx) == (r0.tryb, r0.idx), (r1, r0))

# --- T11. gracz idący naszym torem znika (tylko "duch"): decyduj() w gałęziach czekania/eskalacji bez błędów i bez postoju ---
kor4 = prostokat(60, 160, 100, 100)
pkt4 = [(x, 100, 7) for x in range(70, 151, 3)]
s11, _ = przebieg({}, (70, 100), (76, 100), 90, punkty=pkt4, teren=kor4, tempo=0.6, znika_o=8.0)
sprawdz("T11 duch w korytarzu przez 90 s: brak wyjątku, postój < 8 s", s11.max_postoj() < 8 and s11.trasa, s11.max_postoj())

# --- T7. PRZERWA kończy się, gdy zwykły gracz podejdzie (UNIKANIE_PRZERWA) ---
import cavebot
LOGI = []
cavebot.log = lambda *a: LOGI.append(" ".join(map(str, a)))
def cb_przerwa(gracze):
    return types.SimpleNamespace(unikanie=types.SimpleNamespace(gracze=gracze), przerwa_do=2000.0, przerwa_od=0.0)
f = cavebot.Cavebot._przerwa_przerwij_gdy_gracz
G = lambda odl, n="Harley": [{"nazwa": n, "odl": odl, "x": 0, "y": 0, "z": 8, "id": 1}]
cavebot.UNIKANIE_PRZERWA, cavebot.UNIKANIE_PROMIEN = 1, 9
c = cb_przerwa(G(6))
sprawdz("T7a gracz 6 pól w trakcie przerwy: przerwa kończy się od razu, następna po PRZERWA_CO", f(c, 1000.0) is True and c.przerwa_do is None
        and c.przerwa_od > 1000.0 + cavebot.PRZERWA_CO[0] - 1, (c.przerwa_do, c.przerwa_od))
sprawdz("T7b log po polsku z nickiem i odległością", any("Przerwa przerwana: gracz Harley 6 pól" in l for l in LOGI), LOGI[-1:])
c = cb_przerwa(G(12))
sprawdz("T7c gracz 12 pól (> UNIKANIE_PROMIEN): przerwa trwa", f(c, 1000.0) is False and c.przerwa_do == 2000.0)
c = cb_przerwa([])
sprawdz("T7d brak gracza: przerwa trwa", f(c, 1000.0) is False and c.przerwa_do == 2000.0)
cavebot.UNIKANIE_PRZERWA = 0
c = cb_przerwa(G(2))
sprawdz("T7e UNIKANIE_PRZERWA=0: jak dawniej (przerwa stoi obok gracza)", f(c, 1000.0) is False and c.przerwa_do == 2000.0)
c = types.SimpleNamespace(unikanie=None, przerwa_do=2000.0, przerwa_od=0.0)
cavebot.UNIKANIE_PRZERWA = 1
sprawdz("T7f bez modułu unikania: bez błędu, przerwa trwa", f(c, 1000.0) is False)

# --- T8. pokrętła zarejestrowane w pokretla.py (analityk może tylko w górę) ---
import pokretla
sprawdz("T8 pokrętła toru i przerwy w pokretla.py", all(k in pokretla.ZAKRESY for k in
        ("UNIKANIE_TOR", "UNIKANIE_TOR_OKNO_S", "UNIKANIE_TOR_RUCH_MIN", "UNIKANIE_TOR_ZASIEG", "UNIKANIE_TOR_LOOK",
         "UNIKANIE_TOR_PAMIEC_S", "UNIKANIE_PRZERWA")) if hasattr(pokretla, "ZAKRESY") else True,
        [n for n in dir(pokretla) if n.isupper()][:6])

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
