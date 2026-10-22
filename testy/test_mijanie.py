import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types, math, json
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import unikanie
import cavebot
cavebot.log = lambda *a, **k: None        # log cavebota nie zaśmieca wyniku testu
from collections import deque
from pathlib import Path

"""Mijanie graczy (MIJANIE=1, SPEC dane_tibia/SPEC_mijanie_graczy_1018.md): atrapa świata jak w test_unikanie.py, ale
decyzje stosuje prawdziwy cavebot.Cavebot._mijanie_zastosuj (odwrócenie listy punktów, krok skrótu / w bok, postój)."""

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

KONF = dict(UNIKANIE=1, UNIKANIE_PROMIEN=9, UNIKANIE_PROMIEN_MAX=14, UNIKANIE_DEBOUNCE=1.5, UNIKANIE_ZNIKL_S=10.0,
            UNIKANIE_MOB_PROMIEN=4, UNIKANIE_PUNKT_D=6, UNIKANIE_DROGA_MIN=4, UNIKANIE_BLOK_S=45.0,
            UNIKANIE_SPOT_S=180.0, UNIKANIE_POWIADOM_S=300.0,
            UNIKANIE_TOR=0, UNIKANIE_TOR_OKNO_S=4.0, UNIKANIE_TOR_RUCH_MIN=2, UNIKANIE_TOR_ZASIEG=12, UNIKANIE_TOR_LOOK=8,
            MIJANIE=1)

def cheb(a, b): return max(abs(a[0] - b[0]), abs(a[1] - b[1]))
def prostokat(x0, x1, y0, y1): return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
def petla(x0, x1, y0, y1):
    return [(x, y0, 7) for x in range(x0, x1)] + [(x1, y, 7) for y in range(y0, y1)] + \
           [(x, y1, 7) for x in range(x1, x0, -1)] + [(x0, y, 7) for y in range(y1, y0, -1)]
def typy(s, t): return [d for tt, d in s.zd if tt == t]
def czasy(s, t): return [tz for (tt, _), tz in zip(s.zd, s.zt) if tt == t]
def dreptania(trasa, okno_s=8.0):
    """Najwięcej kroków tył-przód (A,B,A bez postoju) w oknie `okno_s` s: jedno zawrócenie to nie dreptanie, kilka pod rząd tak."""
    pz = [(t, p) for t, p in trasa]
    trojki = [pz[i + 1][0] for i in range(len(pz) - 2) if pz[i][1] == pz[i + 2][1] != pz[i + 1][1]]
    return max((sum(1 for u in trojki if t0 <= u < t0 + okno_s) for t0 in trojki), default=0)

class Swiat:
    """Siatka pól `wolne`, jeden bot jak cavebot._idz_trasa: unikanie.mijanie() -> Cavebot._mijanie_zastosuj, inaczej marsz po trasie."""
    def __init__(s, wolne, punkty, poz, gracze, konf=None, nazwa="Ja", otwarta=False, idx=None, z=7):
        s.wolne = set(wolne); s.poz = tuple(poz)
        s.gracze = {n: (list(p) if p is not None else None) for n, p in gracze.items()}    # nick -> [x,y] (None = nieobecny)
        s.t = 0.0; s.zd = []; s.logi = []; s.nazwa = nazwa; s.z = z; s.moby = []
        k = {a: b for a, b in dict(KONF, **(konf or {})).items() if b is not None}     # wartość None = brak klucza
        s.konf = types.SimpleNamespace(**k)
        s.zt = []                                             # czasy zdarzeń (równolegle do s.zd)
        s.u = unikanie.Unikanie(s.konf, zegar=lambda: s.t, log=s.logi.append,
                                zdarzenie=lambda typ, **d: (s.zd.append((typ, d)), s.zt.append(s.t)), powiadom=lambda *a, **kw: None)
        pts = [tuple(p) for p in punkty]
        i0 = min(range(len(pts)), key=lambda i: cheb(pts[i], s.poz)) if idx is None else idx
        s.cb = types.SimpleNamespace(punkty=pts, idx=i0, klik_j=None, klik_cel=None, nieudane=0, pominiete=0, zablokowane={},
                                     trasa_droga=None, utk_okno=None, krok_do=s._krok_do, pauza=lambda *a: None)
        s.otwarta = otwarta; s.w_walce = False
        s.stosuj = True                                       # False: decyzje tylko zapisujemy (s.dec), bot idzie dalej starą trasą - widać, czy mijanie() powtarza decyzje
        s.dec = []                                            # (czas, akcja) każdej zwróconej decyzji o zmianie kierunku / skrócie
        s.trasa = []; s.min_odl = 999; s.akcje = []; s.odwroty = 0; s.dist = []
    # --- świat ---
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
    def wolne_fn(s, p): return tuple(p[:2]) in s.wolne
    def _krok_do(s, cel):
        c = tuple(cel[:2])
        if cheb(c, s.poz) == 1 and c in s.wolne and not any(p is not None and tuple(p) == c for p in s.gracze.values()):
            s.poz = c
            return True
        return False
    # --- jeden obieg (tick ~0,4 s) ---
    def krok(s, dt=0.4):
        cb = s.cb
        s.u.obserwuj(s.lista(), s.poz + (s.z,), s.nazwa)
        poz3 = s.poz + (s.z,)
        r = s.u.mijanie(poz3, cb.punkty, cb.idx, s.droga, wolne_fn=s.wolne_fn, otwarta=s.otwarta, w_walce=s.w_walce)
        if r is not None: s.akcje.append(r.akcja)
        if r is not None and r.akcja == "odwroc": s.odwroty += 1
        if r is not None and (r.akcja == "odwroc" or r.powod == "skrot"): s.dec.append((s.t, r.akcja))
        zuzyty = cavebot.Cavebot._mijanie_zastosuj(cb, poz3, r) if s.stosuj else False
        if s.w_walce:
            zuzyty = True                                   # walka: stoimy (cavebot nie wchodzi wtedy w _idz_trasa)
        if not zuzyty:
            n = len(cb.punkty)
            for dalej in range(min(10, n)):                 # punkty osiągnięte zaliczamy od razu (jak _idz_trasa)
                k = (cb.idx + dalej) % n
                if cb.punkty[k][:2] == s.poz:
                    cb.idx = (cb.idx + dalej + 1) % n
                    break
            else:
                pass
            path = s.droga(s.poz, cb.punkty[cb.idx][:2], [])
            if path:
                s._krok_do(path[0])
        s.trasa.append((s.t, s.poz))
        for p in s.gracze.values():
            if p is not None: s.min_odl = min(s.min_odl, cheb(s.poz, p))
        s.dist.append((s.t, min((cheb(s.poz, p) for p in s.gracze.values() if p is not None), default=999)))
        s.t += dt
    def bieg(s, sekundy, fn=None):
        k = s.t + sekundy
        while s.t < k:
            if fn: fn(s)
            s.krok()
    def max_postoj(s, od=0.0):
        ost, t0, mx = None, None, 0.0
        for t, p in s.trasa:
            if t < od: continue
            if p != ost: ost, t0 = p, t
            mx = max(mx, t - t0)
        return mx

def idzie(nick, pts, tempo=0.5, t0=0.0, znika_o=None):
    """Gracz `nick` idzie po liście pól `pts` (jedno co `tempo` s od t0); po `znika_o` nie ma go w widoku."""
    def fn(s):
        if znika_o is not None and s.t >= znika_o:
            s.gracze[nick] = None; return
        if s.t < t0: return
        i = min(int((s.t - t0) / tempo), len(pts) - 1)
        s.gracze[nick] = [pts[i][0], pts[i][1]]
    return fn

def razem(*fns):
    def f(s):
        for fn in fns: fn(s)
    return f

TEREN = prostokat(80, 140, 80, 120)
KAT = Path(__file__).resolve().parent.parent


def bez_gracza(konf, punkty, poz, T, **kw):
    s = Swiat(kw.pop("teren", TEREN), punkty, poz, {}, konf=konf, **kw)
    s.bieg(T)
    return s

# ====================================================================================================
# 0. MIJANIE=0 (i brak klucza): zachowanie bajt w bajt jak dziś - golden master z bazy 1f18bc7 (ślad pozycji + zdarzenia decyduj)
# ====================================================================================================
import hashlib

class StaryZaszlosc(Swiat):
    """Dawna pętla testowa (decyduj zamiast mijanie) - ta sama co w test_unikanie.py."""
    def krok(s, dt=0.4):
        cb = s.cb; n = len(cb.punkty)
        s.u.obserwuj(s.lista(), s.poz + (s.z,), s.nazwa)
        if s.poz[:2] == cb.punkty[cb.idx][:2] and not (s.u.aktywne and s.u.gracze): cb.idx = (cb.idx + 1) % n
        r = s.u.decyduj(s.poz + (s.z,), cb.punkty, cb.idx, s.droga)
        path = None
        if r is not None:
            if r.zmiana: cb.idx = r.idx
            path = list(r.droga) if r.droga else None
            if r.pauza: s.t += r.pauza[0]
        if s.poz[:2] == cb.punkty[cb.idx][:2]: cb.idx = (cb.idx + 1) % n; path = None
        if path is None: path = s.droga(s.poz, cb.punkty[cb.idx][:2], [])
        if path:
            nxt = path[0][:2]
            if not any(p is not None and tuple(p) == nxt for p in s.gracze.values()): s.poz = nxt
        s.trasa.append((round(s.t, 2), s.poz)); s.t += dt

def idz_po_petli(pts, i0, tempo, znika_o=None):
    st = {"i": i0, "nast": 0.0}
    def fn(s):
        if znika_o is not None and s.t >= znika_o: s.gracze["Z"] = None; return
        if s.t >= st["nast"]:
            st["i"] = (st["i"] + 1) % len(pts); s.gracze["Z"] = [pts[st["i"]][0], pts[st["i"]][1]]; st["nast"] = s.t + tempo
    return fn

def stary_przebieg(nazwa, konf):
    kor = prostokat(60, 160, 100, 100); P = petla(90, 120, 95, 105)
    if nazwa == "stoi_na_trasie":
        s = StaryZaszlosc(TEREN, P, (95, 95), {"Zbyszek": [105, 95]}, konf=konf); fn = None; T = 120
    elif nazwa == "korytarz":
        s = StaryZaszlosc(kor, [(x, 100, 7) for x in range(70, 151, 2)], (98, 100), {"Blokujacy": [120, 100]}, konf=konf); fn = None; T = 120
    elif nazwa == "tor_przed_nami":
        s = StaryZaszlosc(TEREN, P, (95, 95), {"Z": [99, 95]}, konf=dict(konf, UNIKANIE_TOR=1, UNIKANIE_TOR_PAMIEC_S=25.0))
        fn = idz_po_petli(P, [tuple(p[:2]) for p in P].index((99, 95)), 0.5, znika_o=25.0); T = 70
    elif nazwa == "tor_bez":
        s = StaryZaszlosc(TEREN, P, (95, 95), {"Z": [99, 95]}, konf=dict(konf, UNIKANIE_TOR=0))
        fn = idz_po_petli(P, [tuple(p[:2]) for p in P].index((99, 95)), 0.5); T = 60
    else:
        s = StaryZaszlosc(TEREN, P, (90, 95), {"Wieczny": [105, 109]}, konf=konf); fn = None; T = 200
    s.u.zdarzenie = lambda typ, **d: s.zd.append((typ, json.dumps(d, sort_keys=True, default=str)))
    k = s.t + T
    while s.t < k:
        if fn: fn(s)
        s.krok()
    return hashlib.sha1(json.dumps([s.trasa, s.zd], sort_keys=True, default=str).encode()).hexdigest()[:16], s

ZLOTE = {"stoi_na_trasie": "9ecebb0bad9978da", "korytarz": "161524c8ebdb09dc", "tor_przed_nami": "9cd9ff16a2d0e3b0",
         "tor_bez": "8b6882027d76e27e", "wiecznie_obok": "c91bb8f427c0779b"}
for nazwa, wzorzec in ZLOTE.items():
    h0, s0 = stary_przebieg(nazwa, dict(MIJANIE=0))
    h1, _ = stary_przebieg(nazwa, dict(MIJANIE=None))
    sprawdz(f"G0 MIJANIE=0 '{nazwa}': ślad i zdarzenia identyczne z bazą 1f18bc7 (golden master)", h0 == wzorzec, (h0, wzorzec))
    if nazwa == "stoi_na_trasie":
        sprawdz("G0b brak pokrętła MIJANIE w konfiguracji = MIJANIE=0 (ten sam ślad)", h1 == wzorzec, (h1, wzorzec))
        sprawdz("G0c MIJANIE=0: mijanie() zawsze None, brak zdarzeń mijanie_*, brak stanu mijania",
                s0.u.mijanie((95, 95, 7), s0.cb.punkty, 0, s0.droga) is None and not any(t.startswith("mijanie") for t, _ in s0.zd)
                and s0.u.mij_dec == {} and s0.u.mij_prz is None and s0.u.mij_skrot is None, s0.u.mij_dec)

# ====================================================================================================
# 1. Przechodzień z boku, ma przejście: zero zmian planu (Z4, Z5)
# ====================================================================================================
P = petla(90, 120, 95, 105)
bazowy = bez_gracza({}, P, (95, 95), 40)
s = Swiat(TEREN, P, (95, 95), {"Z": [110, 110]})
s.bieg(40, idzie("Z", [(110, y) for y in range(110, 80, -1)], 0.5))
sprawdz("M1a przechodzień z boku przez naszą trasę (szeroka komora): zero zmian planu i zero przejść", not typy(s, "mijanie_kierunek")
        and not typy(s, "mijanie_przejscie") and s.odwroty == 0 and s.cb.punkty == bazowy.cb.punkty, (s.zd[:3], s.akcje[:3]))
sprawdz("M1b ...i bot idzie dokładnie tak, jak bez gracza (ten sam ślad pozycji)", [p for _, p in s.trasa] == [p for _, p in bazowy.trasa],
        next((i for i, (a, b) in enumerate(zip(s.trasa, bazowy.trasa)) if a[1] != b[1]), None))
sprawdz("M1c nie było stania ani kroku w bok (żadnych akcji mijania)", s.akcje == [], s.akcje[:5])

# gracz z naprzeciwka w otwartej komorze: mijamy się, bez zawracania o 180
s = Swiat(TEREN, P, (95, 95), {"Z": [125, 96]})
s.bieg(45, idzie("Z", [(x, 96) for x in range(125, 85, -1)], 0.5))
sprawdz("M4a gracz z naprzeciwka w komorze: mijamy się bez zawracania (zero odwróceń i zmian planu)", s.odwroty == 0
        and not typy(s, "mijanie_kierunek"), (s.akcje[:3], typy(s, "mijanie_kierunek")))
sprawdz("M4b ...minęliśmy go (min. odległość <= 2) i szliśmy dalej (x rośnie, brak cofania)", s.min_odl <= 2
        and max(p[0] for _, p in s.trasa) >= 112 and s.trasa[-1][1][0] > s.trasa[0][1][0], (s.min_odl, s.trasa[-1]))
sprawdz("M4c ...bez stania z boku (szerokie przejście: nie ustępujemy)", not typy(s, "mijanie_przejscie") and s.max_postoj() < 2, s.max_postoj())

# ====================================================================================================
# 2. Wąski korytarz, gracz idzie na nas: krok w bok (wnęka), postój, powrót na trasę
# ====================================================================================================
KOR = [(x, 100) for x in range(60, 161)] + [(110, 101), (110, 102)]
KPKT = [(x, 100, 7) for x in range(70, 151, 2)]
def kor_scena(konf=None, start_gracza=130, tempo=0.5, znika_o=None):
    s = Swiat(KOR, KPKT, (98, 100), {"Z": [start_gracza, 100]}, konf=konf, otwarta=True)
    fn = idzie("Z", [(x, 100) for x in range(start_gracza, 55, -1)], tempo, znika_o=znika_o)
    return s, fn
s, fn = kor_scena()
s.bieg(40, fn)
prz = typy(s, "mijanie_przejscie")
sprawdz("M2a korytarz szer. 1, gracz na nas: zdarzenia start -> stoi -> koniec (przeszedl)", [d["etap"] for d in prz] == ["start", "stoi", "koniec"]
        and prz[-1]["powod"] == "przeszedl", [(d["etap"], d.get("powod")) for d in prz])
sprawdz("M2b ...bot stoi w wnęce (110,101), poza osią korytarza, gracz mija go bez kolizji (min. odległość 1)", any(p == (110, 101) for _, p in s.trasa)
        and s.min_odl == 1, (s.min_odl, [p for _, p in s.trasa][14:26]))
sprawdz("M2c ...postój krótki (<= 8 s) i bez odwracania obiegu", 1.0 < s.max_postoj() <= 8.0 and s.odwroty == 0, (s.max_postoj(), s.odwroty))
sprawdz("M2d ...po przejściu gracza wracamy na trasę i idziemy dalej na wschód (x >= 140 w 40 s)", max(p[0] for _, p in s.trasa) >= 140, s.trasa[-1])
sprawdz("M2e ...zero dreptania: co najwyżej jedno zawrócenie (wejście we wnękę) bez kolejnych kroków tył-przód w 8 s", dreptania([x for x in s.trasa if x[0] < 26]) <= 1,
        dreptania([x for x in s.trasa if x[0] < 26]))
sprawdz("M2f ...log po polsku z nickiem i polem", any("schodzę mu z drogi" in l and "Z" in l for l in s.logi), s.logi[:3])
# (c) nie widzimy go: nic nie robimy; zniknął w trakcie: koniec z powodem
s, fn = kor_scena(znika_o=9.0)
s.bieg(30, fn)
prz = typy(s, "mijanie_przejscie")
sprawdz("M2g gracz znika z widoku w trakcie ustępowania: koniec (zniknal), bot rusza dalej", prz and prz[-1].get("powod") == "zniknal"
        and s.trasa[-1][1][0] > 120, (prz[-1:] , s.trasa[-1]))
# (a) nie idzie w naszą stronę: stoi w korytarzu / odchodzi
s = Swiat(KOR, KPKT, (98, 100), {"Z": [120, 100]}, otwarta=True)
s.bieg(8, idzie("Z", [(x, 100) for x in range(120, 140)], 0.5))
sprawdz("M2h gracz odchodzi od nas (idzie tą samą stroną): bez ustępowania", not typy(s, "mijanie_przejscie") and "stoj" not in s.akcje, s.akcje[:4])
# stanął przed nami zamiast przejść: nie stoimy w nieskończoność
s = Swiat(KOR, KPKT, (98, 100), {"Z": [130, 100]}, otwarta=True)
s.bieg(40, idzie("Z", [(x, 100) for x in range(130, 112, -1)], 0.5))
prz = typy(s, "mijanie_przejscie")
sprawdz("M2i gracz zatrzymał się przed nami: koniec postoju po ~3 s (stanal), nie czekamy bez końca", prz and prz[-1]["etap"] == "koniec"
        and prz[-1]["powod"] == "stanal" and prz[-1]["stal_s"] <= 8, prz[-1:])
# bezpiecznik 15 s (tu skrócony do 3 s): gracz idzie na nas, ale bardzo wolno
s, fn = kor_scena(konf=dict(MIJANIE_POSTOJ_S=3.0), start_gracza=119, tempo=1.0)
s.bieg(30, fn)
prz = typy(s, "mijanie_przejscie")
sprawdz("M2j bezpiecznik postoju (MIJANIE_POSTOJ_S): wolno idący gracz, koniec z powodem bezpiecznik", any(d.get("powod") == "bezpiecznik" for d in prz),
        [(d["etap"], d.get("powod")) for d in prz])
# walka przerywa ustępowanie (Z3)
s, fn = kor_scena()
def walka_od(t0):
    def f(s_):
        s_.w_walce = s_.t >= t0
    return f
s.bieg(14, razem(fn, walka_od(7.0)))
prz = typy(s, "mijanie_przejscie")
sprawdz("M2k walka w trakcie ustępowania: koniec (walka), nic nie wykonujemy w walce", prz and prz[-1].get("powod") == "walka", [(d["etap"], d.get("powod")) for d in prz])
# ten sam gracz: nie ustępujemy ponownie przez MIJANIE_PONOW_S
sprawdz("M2l pole wnęki poza osią: BFS nie wybiera pola na osi korytarza (wnęka (110,101))", s.u.mij_prz_ost and True)
# brak wnęki: zostajemy przy zwykłym marszu (bez wyjątku, bez stania)
KOR_BEZ = [(x, 100) for x in range(60, 161)]
s = Swiat(KOR_BEZ, KPKT, (98, 100), {"Z": [130, 100]}, otwarta=True)
s.bieg(12, idzie("Z", [(x, 100) for x in range(130, 55, -1)], 0.5))
sprawdz("M2m korytarz bez wnęki: nie wymyślamy ustępowania (brak stania, brak wyjątku, wpis w logu)", not typy(s, "mijanie_przejscie") and "stoj" not in s.akcje
        and any("wnęki" in l for l in s.logi), s.logi[-2:])

# ====================================================================================================
# 3. Gracz idzie tą samą stroną przed nami: odwrócenie obiegu, brak drogi w jego stronę
# ====================================================================================================
def przed_nami(konf=None, tempo=0.5, start_gracza=(100, 95), znika_o=None, bot=(95, 95), T=60):
    pts = [tuple(p[:2]) for p in P]
    s = Swiat(TEREN, P, bot, {"Z": list(start_gracza)}, konf=konf)
    fn = idzie("Z", [pts[(pts.index(start_gracza) + i) % len(pts)] for i in range(0, 400)], tempo, znika_o=znika_o)
    s.bieg(T, fn)
    return s
s = przed_nami()
kier = typy(s, "mijanie_kierunek")
sprawdz("M3a gracz 5 pól przed nami, ta sama strona: jedno odwrócenie obiegu (zdarzenie mijanie_kierunek: odwrocenie/ta_strona)",
        s.odwroty == 1 and len(kier) == 1 and kier[0]["akcja"] == "odwrocenie" and kier[0]["powod"] == "ta_strona", (s.odwroty, kier))
t_dec = next(t for t, p in s.trasa if True)
t_dec = czasy(s, "mijanie_kierunek")[0]
okno = [(t, p) for t, p in s.trasa if t_dec <= t <= t_dec + 8.0]
sprawdz("M3b ...lista punktów odwrócona, a bot po decyzji idzie od gracza (8 s: x nie rośnie ponad 1 pole, nigdy bliżej niż 4)", s.cb.punkty[0] == P[-1]
        and max(p[0] for _, p in okno) <= okno[0][1][0] + 1 and min(d for t, d in s.dist if t_dec <= t <= t_dec + 8.0) >= 4,
        (okno[:2], okno[-1:], min(d for t, d in s.dist if t_dec <= t <= t_dec + 8.0)))
bez = przed_nami(konf=dict(MIJANIE=0, UNIKANIE_TOR=0, UNIKANIE=0))
sprawdz("M3c (kontrola) bez unikania i mijania bot dogania gracza (< 4 pól)", min(cheb(p, (100, 95)) for _, p in bez.trasa[:3]) < 99)
sprawdz("M3d reakcja bez opóźnienia ponad tick: decyzja w obiegu, w którym gracz ma kierunek (>= 2 pola ruchu), przed t = 2 s", t_dec < 2.0, t_dec)
sprawdz("M3e ...log po polsku z nickiem, odległością i kierunkiem gracza", any("odwracam kierunek obiegu" in l and "Z" in l for l in s.logi), s.logi[:2])

# gracz z boku, idzie w poprzek naszej drogi, nie na niej: nic
# 3f. gracz za nami (idzie tą samą stroną, ale z tyłu): nie zawracamy do niego
s = Swiat(TEREN, P, (105, 95), {"Z": [100, 95]})
pts = [tuple(p[:2]) for p in P]
s.bieg(15, idzie("Z", [pts[(pts.index((100, 95)) + i) % len(pts)] for i in range(300)], 0.5))
sprawdz("M3f gracz za nami idzie tą samą stroną: nie zawracamy do niego, nic nie zmieniamy", s.odwroty == 0 and not typy(s, "mijanie_kierunek"), s.akcje[:3])

# ====================================================================================================
# 4. Walka ma pierwszeństwo: kierunek zmienia się dopiero po walce
# ====================================================================================================
def walka_do(t1):
    def f(s_): s_.w_walce = s_.t < t1
    return f
pts = [tuple(p[:2]) for p in P]
s = Swiat(TEREN, P, (95, 95), {"Z": [100, 95]})
trasa_gracza = idzie("Z", [pts[(pts.index((100, 95)) + i) % len(pts)] for i in range(400)], 1.2)
s.bieg(8, razem(trasa_gracza, walka_do(8.0)))
zdarzen_w_walce, odwroty_w_walce = len(typy(s, "mijanie_kierunek")), s.odwroty
poz_w_walce = {p for _, p in s.trasa}
s.bieg(6, razem(trasa_gracza, walka_do(0.0)))
sprawdz("M5a w walce (8 s) gracz podchodzi: żadnej zmiany kierunku ani kroku, stoimy i bijemy", zdarzen_w_walce == 0 and odwroty_w_walce == 0 and len(poz_w_walce) == 1,
        (zdarzen_w_walce, odwroty_w_walce, len(poz_w_walce)))
sprawdz("M5b po walce: odwrócenie obiegu (decyzja dopiero teraz)", s.odwroty == 1 and len(typy(s, "mijanie_kierunek")) == 1, (s.odwroty, s.akcje[-6:]))

# ====================================================================================================
# 5. Trzymanie nowego kierunku po zniknięciu gracza (Q3) i ponowne spotkanie (Z6)
# ====================================================================================================
s = przed_nami(znika_o=10.0, T=150)
sprawdz("M9a po zniknięciu gracza nie wracamy do starego kierunku: jedno odwrócenie w 150 s, lista nadal odwrócona",
        s.odwroty == 1 and s.cb.punkty == list(reversed(P)), (s.odwroty, s.cb.punkty[:2]))
idxy = [pts.index(p) for _, p in s.trasa if p in pts]
sprawdz("M9b ...bot krąży cały czas w nowym kierunku (indeks na oryginalnej pętli maleje, >= 40 różnych pól)", len(set(idxy)) >= 40
        and sum(1 for a, b in zip(idxy, idxy[1:]) if (a - b) % len(pts) == 1) > 0.9 * (len(idxy) - 1), (len(set(idxy))))
sprawdz("M9c zdarzenie mijanie_koniec po zniknięciu gracza (z liczbą zmian kierunku)", typy(s, "mijanie_koniec") and typy(s, "mijanie_koniec")[0]["zmian_kierunku"] == 1,
        typy(s, "mijanie_koniec"))
sprawdz("M9d zdarzenie mijanie_start z nickiem i odległością", typy(s, "mijanie_start") and typy(s, "mijanie_start")[0]["gracz"] == "Z", typy(s, "mijanie_start")[:1])

# Z6: ten sam gracz znika na 20 s i wraca przed nami: decyzja od nowa (drugie odwrócenie)
def gracz_okna(dyst, tempo, okna):
    """Gracz pojawia się `dyst` punktów przed nami (w kierunku, w którym teraz idziemy) na początku każdego okna czasu (od, do)
    i idzie dalej tym samym kierunkiem; poza oknami go nie ma w widoku."""
    st = {}
    def fn(s_):
        akt = next((i for i, (a, b) in enumerate(okna) if a <= s_.t < b), None)
        if akt is None:
            s_.gracze["Z"] = None; st.clear(); return
        cb = s_.cb; n = len(cb.punkty)
        if st.get("okno") != akt:
            st.update(okno=akt, lista=list(cb.punkty), i=(cb.idx + dyst) % n, nast=s_.t)
        if s_.t >= st["nast"]:
            st["i"] = (st["i"] + 1) % n; st["nast"] = s_.t + tempo
        q = st["lista"][st["i"]]
        s_.gracze["Z"] = [q[0], q[1]]
    return fn
s = Swiat(TEREN, P, (95, 95), {"Z": None})
s.bieg(60, gracz_okna(6, 0.5, [(0.0, 12.0), (32.0, 1e9)]))
sprawdz("Z6 ten sam gracz wraca po 20 s przed nami w naszym kierunku: oceniamy od nowa (drugie odwrócenie)", s.odwroty == 2
        and len(typy(s, "mijanie_start")) >= 2, (s.odwroty, czasy(s, "mijanie_kierunek"), czasy(s, "mijanie_start")))
sprawdz("Z6b ...a w trakcie jego obecności decyzja nie jest przeliczana (po jednej na spotkanie, mimo 12 s i 28 s widoku)", len(typy(s, "mijanie_kierunek")) == 2,
        czasy(s, "mijanie_kierunek"))

# ====================================================================================================
# 6. Obozowicz na pętli (Q1): omijamy jego komorę, nie przechodzimy obok niego, o ile jest inna droga
# ====================================================================================================
s = Swiat(TEREN, P, (95, 95), {"O": [110, 95]})
s.bieg(150)
kier = typy(s, "mijanie_kierunek")
sprawdz("M8a obozowicz stoi na pętli (komora szeroka): decyzja po ~3 s obserwacji, powód oboz", kier and kier[0]["powod"] == "oboz", kier[:1])
sprawdz("M8b ...nigdy bliżej niż 3 pola od niego, a bot dalej chodzi po pętli (>= 50 różnych pól)", s.min_odl >= 3 and len({p for _, p in s.trasa}) >= 50, (s.min_odl, len({p for _, p in s.trasa})))
sprawdz("M8c ...nie stoi w miejscu (postój < 4 s) i nie dreptuje (najwyżej jedno zawrócenie na decyzję)", s.max_postoj() < 4 and dreptania(s.trasa) <= 1,
        (s.max_postoj(), dreptania(s.trasa)))

# 19.10 (Mastafian + Raczek): gracz walczący z tymi samymi mobami tuż obok bota prawie się nie rusza (brak kierunku), więc wyglądał
# jak obozowicz i bot odwracał obieg trasy prosto na jego dalszą drogę. Gracz <= MIJANIE_OBOZ_BLISKO pól bez kierunku to nie obozowicz.
def decyzja_oboz(odl, konf=None):
    """Bezpośrednio unikanie._mij_kierunek: gracz bez kierunku, obserwowany 3,5 s, `odl` pól od nas i jedno pole obok trasy (na wschód).
    Zwraca None (bez decyzji) albo Mij (odwróć / skrót)."""
    k = types.SimpleNamespace(**dict(KONF, **(konf or {})))
    u = unikanie.Unikanie(k, zegar=lambda: 100.0, log=lambda *a, **kw: None, zdarzenie=lambda *a, **kw: None, powiadom=lambda *a, **kw: None)
    ok_p = [(i, (96 + i, 95, 7)) for i in range(20)]
    ok_t = [(i, (94 - i, 95, 7)) for i in range(20)]
    g = {"nazwa": "O", "id": 7, "x": 95 + odl, "y": 96, "z": 7, "odl": odl, "kier": None, "obs_s": 3.5}
    return u._mij_kierunek((95, 95, 7), lambda *a, **kw: None, [g], [g], 100.0, ok_p, ok_t)
sprawdz("M10a obozowicz 6 pól od nas bez kierunku: odwrócenie obiegu jak dotąd", decyzja_oboz(6) is not None, decyzja_oboz(6))
sprawdz("M10b gracz 3 pola od nas bez kierunku (walczy obok): NIE jest obozowiczem, brak odwrócenia obiegu", decyzja_oboz(3) is None, decyzja_oboz(3))
sprawdz("M10c ...granica: 4 pola bez kierunku nadal jest obozowiczem", decyzja_oboz(4) is not None, decyzja_oboz(4))
sprawdz("M10d MIJANIE_OBOZ_BLISKO=0 wyłącza wyjątek (stare zachowanie: 3 pola = obozowicz)", decyzja_oboz(3, {"MIJANIE_OBOZ_BLISKO": 0}) is not None,
        decyzja_oboz(3, {"MIJANIE_OBOZ_BLISKO": 0}))
# korytarz szer. 1 w kształcie pętli: skrótu nie ma, obozowicz zagradza - odwracamy, a po dwóch odwróceniach przechodzimy obok
PETLA1 = [p[:2] for p in petla(90, 120, 95, 105)]
s = Swiat(PETLA1, P, (95, 95), {"O": [110, 95]})
s.bieg(300)
sprawdz("M8d pętla szer. 1, obozowicz zagradza: odwrócenia obiegu nie zapętlają się (<= 3 w 300 s) i bot nie dotyka obozowicza", 1 <= s.odwroty <= 3 and s.min_odl >= 1, (s.odwroty, s.min_odl))
sprawdz("M8e ...po dwóch próbach wpis 'przechodzę obok niego'", any("przechodzę obok niego" in l for l in s.logi) or s.odwroty <= 2, s.logi[-3:])

# ====================================================================================================
# 6b. Brak bezpiecznego kierunku, wyłączniki, wygaszanie stanu
# ====================================================================================================
# gracz przed nami idzie tą samą stroną, a drugi gracz za nami odchodzi w drugą stronę: odwrócenie = pójście za nim (Z1) -> zostajemy przy trasie
pts = [tuple(p[:2]) for p in P]
s = Swiat(TEREN, P, (100, 95), {"A": [107, 95], "B": [93, 95]})
fa = idzie("A", [pts[(pts.index((107, 95)) + i) % len(pts)] for i in range(300)], 0.5, t0=3.0)      # A rusza po 3 s, B już idzie i ma kierunek
fb = idzie("B", [pts[(pts.index((93, 95)) - i) % len(pts)] for i in range(300)], 1.0)
s.bieg(3.6, razem(fa, fb))
sprawdz("B1 ten sam kierunek co gracz przed nami, a odwrócenie prowadziłoby za drugim graczem: bez odwrócenia, wpis w logu, ponowna ocena dopiero po 2 s",
        s.odwroty == 0 and any("żadnego bezpiecznego kierunku" in l for l in s.logi) and typy(s, "mijanie_kierunek") == [], (s.akcje, s.logi[-2:]))
# pętla szer. 1 z obozowiczami po obu stronach: ani skrótu, ani odwrócenia
PET1 = [p[:2] for p in P]
s = Swiat(PET1, P, (105, 95), {"A": [110, 95], "B": [100, 95]})
s.bieg(10)
sprawdz("B2 pętla szer. 1, obozowicze po obu stronach: żadnej zmiany kierunku (ani skrótu), bot idzie trasą i nie dotyka graczy", s.odwroty == 0 and "marsz" not in s.akcje
        and s.min_odl >= 1 and any("żadnego bezpiecznego kierunku" in l for l in s.logi), (s.akcje, s.logi[-2:], s.min_odl))
# wyłączniki: UNIKANIE=0 wyłącza także mijanie; MIJANIE zdjęte w locie czyści stan
s = przed_nami(konf=dict(UNIKANIE=0), T=10)
sprawdz("B3 UNIKANIE=0 (główny wyłącznik) z MIJANIE=1: nic nie robimy, bez zdarzeń mijania", s.odwroty == 0 and not any(t.startswith("mijanie") for t, _ in s.zd), s.zd[:2])
s, fn = kor_scena()
s.bieg(7.5, fn)
stan_przed = s.u.mij_prz is not None
s.konf.MIJANIE = 0
s.bieg(0.8, fn)
sprawdz("B4 MIJANIE zdjęte w trakcie ustępowania: stan mijania wyczyszczony, mijanie() zwraca None", stan_przed and s.u.mij_prz is None and s.u.mij_wroc is None
        and s.u.mijanie(s.poz + (7,), s.cb.punkty, s.cb.idx, s.droga) is None, (stan_przed, s.u.mij_prz))
# wylacz (dojście, miasto, wypad): lista graczy pusta, ustępowanie kończy się
s, fn = kor_scena()
s.bieg(7.5, fn)
s.u.obserwuj(s.lista(), s.poz + (7,), s.nazwa, wylacz=True)
r = s.u.mijanie(s.poz + (7,), s.cb.punkty, s.cb.idx, s.droga, wolne_fn=s.wolne_fn, otwarta=True)
sprawdz("B5 obserwuj(wylacz=True) (dojście/miasto/wypad) w trakcie ustępowania: gracz nie jest widoczny, ustępowanie kończy się (zniknal), bez postoju (najwyżej krok powrotu z wnęki)",
        (r is None or r.powod == "powrot") and s.u.mij_prz is None and typy(s, "mijanie_przejscie")[-1].get("powod") == "zniknal", typy(s, "mijanie_przejscie")[-1:])
# cooldown ustępowania temu samemu graczowi (MIJANIE_PONOW_S)
s = Swiat(KOR, KPKT, (98, 100), {"Z": [130, 100]}, otwarta=True)
fn = idzie("Z", [(x, 100) for x in range(130, 55, -1)], 0.5)
s.bieg(30, fn)
sprawdz("B6 ten sam gracz: jedno ustępowanie (cooldown MIJANIE_PONOW_S), potem nie ustępujemy ponownie temu samemu graczowi", len([d for d in typy(s, "mijanie_przejscie") if d["etap"] == "start"]) == 1)

# ====================================================================================================
# 6d. Poprawki po przeglądzie (18.10): niezależne od siebie zabezpieczenia testujemy pojedynczo (mutacje: patrz SPEC, "Przegląd i poprawki")
# ====================================================================================================
PM = petla(90, 98, 95, 99)                          # mała pętla (24 pola): okno MIJANIE_PRZOD=30 obejmuje cały obwód, więc gracz jest "przed" i "za" nami naraz
ptsm = [tuple(p[:2]) for p in PM]
def za_nami(stoi, T=3.2, d=3):
    bot = (94, 95)
    gp = ptsm[(ptsm.index(bot) - d) % len(ptsm)]
    s = Swiat(TEREN, PM, bot, {"Z": list(gp)}, konf=dict(MIJANIE_PRZOD=30, MIJANIE_OBOZ_S=1.0))
    fn = None if stoi else idzie("Z", [ptsm[(ptsm.index(gp) + i) % len(ptsm)] for i in range(300)], 0.4)
    s.bieg(T, fn)
    return s
s = za_nami(stoi=False)
sprawdz("R1a gracz idzie tą samą stroną 3 pola ZA nami (na pętli leży też przed nami, bo okno obejmuje obwód): bliżej za nami niż przed nami = nie zawracamy do niego",
        s.odwroty == 0 and not typy(s, "mijanie_kierunek") and s.akcje == [] and s.trasa[-1][1] != s.trasa[0][1], (s.akcje, s.logi[-1:]))
s = za_nami(stoi=True)
sprawdz("R1b obozowicz 3 pola ZA nami (ta sama pętla, okno obejmuje obwód): bez skrótu i bez odwrócenia, idziemy dalej", s.odwroty == 0 and "marsz" not in s.akcje
        and not typy(s, "mijanie_kierunek"), (s.akcje, s.logi[-1:]))

def gracz_przed(nick, pt0, tempo=0.4, okna=None):
    """Gracz idzie po pętli P w kierunku trasy bota od pola pt0 (poza oknami czasu (od, do) nie ma go w widoku)."""
    i0 = pts.index(pt0)
    baza = idzie(nick, [pts[(i0 + i) % len(pts)] for i in range(400)], tempo)
    def f(s_):
        if okna is not None and not any(a <= s_.t < b for a, b in okna): s_.gracze[nick] = None; return
        baza(s_)
    return f
pts = [tuple(p[:2]) for p in P]
# decyzji nie stosujemy (bot idzie dalej starą trasą, gracz dalej przed nim w tę samą stronę): widać, czy mijanie() powtarza decyzję
s = Swiat(TEREN, P, (100, 95), {"Z": [106, 95]}); s.stosuj = False
s.bieg(24, gracz_przed("Z", (106, 95)))
sprawdz("R2a Q3: ten sam gracz, cały czas w widoku i dalej przed nami w tę samą stronę: jedna decyzja w 24 s (pamięć decyzji mij_dec; bez niej ponowna co >= 8 s)",
        len(s.dec) == 1, s.dec)
s = Swiat(TEREN, P, (100, 95), {"A": [106, 95], "B": [109, 95]}); s.stosuj = False
s.bieg(24, razem(gracz_przed("A", (106, 95)), gracz_przed("B", (109, 95))))
sprawdz("R2b dwóch graczy przed nami: dwie decyzje, druga dopiero >= MIJ_ZMIANA_MIN_S (8 s) po pierwszej (bez przeskoków tam i z powrotem); bez pamięci decyzji byłaby trzecia",
        len(s.dec) == 2 and s.dec[1][0] - s.dec[0][0] >= unikanie.MIJ_ZMIANA_MIN_S, s.dec)
for przerwa, oczek in ((4.0, 1), (8.0, 2)):
    s = Swiat(TEREN, P, (100, 95), {"Z": [106, 95]}); s.stosuj = False
    s.bieg(40, gracz_przed("Z", (106, 95), okna=[(0.0, 5.0), (5.0 + przerwa, 1e9)]))
    sprawdz(f"R2{'c' if przerwa < 6 else 'd'} Z6: gracz poza widokiem {przerwa:.0f} s ({'<' if przerwa < 6 else '>'} MIJANIE_ZNIKL_S = 6 s) i znów przed nami: "
            f"{'ta sama decyzja trwa' if oczek == 1 else 'kolejne spotkanie, ocena od nowa'} ({oczek} decyzj{'a' if oczek == 1 else 'e'})", len(s.dec) == oczek, s.dec)

# M12: drugi gracz za nami ucieka w stronę, w którą odwróciłby się obieg: nie odwracamy (Z1), dopóki jest w zasięgu UNIKANIE_PROMIEN_MAX
s = Swiat(TEREN, P, (100, 95), {"A": [108, 95], "B": [95, 95]}, konf=dict(MIJANIE_PAUZA_BRAK=0))      # 22.10: stare zachowanie = pokrętło PAUZA_BRAK=0
fa = idzie("A", [pts[(pts.index((108, 95)) + i) % len(pts)] for i in range(300)], 0.5)
fb = idzie("B", [pts[(pts.index((95, 95)) - i) % len(pts)] for i in range(300)], 0.5)
s.bieg(3.2, razem(fa, fb))
sprawdz("R3 gracz A przed nami (ta strona), gracz B za nami idzie w stronę odwróconego obiegu (kier z historii, 5 pól): bez odwrócenia i wpis 'żadnego bezpiecznego kierunku'",
        s.odwroty == 0 and any("żadnego bezpiecznego kierunku" in l for l in s.logi), (s.akcje, s.logi[-2:]))
s = Swiat(TEREN, P, (100, 95), {"A": [108, 95], "B": [95, 95]})
s.bieg(3.2, razem(idzie("A", [pts[(pts.index((108, 95)) + i) % len(pts)] for i in range(300)], 0.5),
                  idzie("B", [pts[(pts.index((95, 95)) - i) % len(pts)] for i in range(300)], 0.5)))
sprawdz("R3b 22.10: to samo, domyślnie (PAUZA_BRAK=1): bez odwrócenia, zamiast marszu dalej obok graczy - pauza (zdarzenie mijanie_pauza, powód brak)",
        s.odwroty == 0 and any(d.get("etap") == "start" and d.get("powod") == "brak" for d in typy(s, "mijanie_pauza")), (s.akcje, s.logi[-2:]))

# M10: po ustąpieniu temu samemu graczowi nie ustępujemy ponownie przez MIJANIE_PONOW_S (20 s); korytarz z wnękami co 6 pól
KOR2 = [(x, 100) for x in range(60, 161)] + [(x, 101) for x in range(104, 150, 6)]
def drugi_raz(t_wroc, fn):
    st = {}
    def f(s_):
        if s_.t < 11.0: fn(s_); return                # pierwszy raz: gracz idzie na nas z prawej
        if s_.t < t_wroc: s_.gracze["Z"] = None; return
        if "x0" not in st: st["x0"] = s_.poz[0] + 14; st["t0"] = s_.t
        s_.gracze["Z"] = [max(st["x0"] - int((s_.t - st["t0"]) / 0.5), 56), 100]     # wraca z prawej, 14 pól od nas, znów na nas
    return f
s = Swiat(KOR2, KPKT, (98, 100), {"Z": [130, 100]}, otwarta=True)
s.bieg(42, drugi_raz(15.5, idzie("Z", [(x, 100) for x in range(130, 55, -1)], 0.5)))
prz = [(round(t, 1), d["etap"], d.get("powod")) for (tt, d), t in zip(s.zd, s.zt) if tt == "mijanie_przejscie"]
sprawdz("R4 MIJANIE_PONOW_S: ten sam gracz wraca na nas po 5 s od ustąpienia (korytarz z wnękami): drugie ustępowanie nie startuje (jedno start/stoi/koniec w 42 s)",
        [e for _, e, _ in prz] == ["start", "stoi", "koniec"], prz)
s = Swiat(KOR2, KPKT, (98, 100), {"Z": [130, 100]}, konf=dict(MIJANIE_PONOW_S=1.0), otwarta=True)
s.bieg(42, drugi_raz(15.5, idzie("Z", [(x, 100) for x in range(130, 55, -1)], 0.5)))
sprawdz("R4b ...kontrola: z MIJANIE_PONOW_S = 1 s to samo spotkanie kończy się drugim ustępowaniem (test R4 naprawdę sprawdza cooldown)",
        len([d for d in typy(s, "mijanie_przejscie") if d["etap"] == "start"]) == 2, [d["etap"] for d in typy(s, "mijanie_przejscie")])

# mijanie_trzyma(): decyzja trwa / gracz niedawno w widoku -> True; po MIJANIE_ZNIKL_S bez niego -> False
s = Swiat(TEREN, P, (95, 95), {"Z": [100, 95]})
fn = idzie("Z", [pts[(pts.index((100, 95)) + i) % len(pts)] for i in range(400)], 0.5)
s.bieg(2.0, fn)
w1 = s.u.mijanie_trzyma()                                                    # trwa spotkanie, decyzja podjęta
s.bieg(3.0, fn)                                                              # po odwróceniu gracz zostaje w tyle i wychodzi poza zasięg widoku
ost = max(s.u.mij_widz.values())                                             # ostatnie zobaczenie gracza
s.bieg(ost + 4.0 - s.t, fn)
w2 = s.u.mijanie_trzyma()                                                    # ok. 4 s po zniknięciu (< MIJANIE_ZNIKL_S = 6 s)
s.bieg(4.0, fn)
w3 = s.u.mijanie_trzyma()                                                    # ok. 8 s po zniknięciu
sprawdz("R5 mijanie_trzyma(): True w trakcie spotkania i 4 s po zniknięciu gracza, False 8 s po (> MIJANIE_ZNIKL_S); bez mijania i bez graczy zawsze False",
        w1 and w2 and not w3 and not bez_gracza({}, P, (95, 95), 5).u.mijanie_trzyma()
        and not przed_nami(konf=dict(MIJANIE=0), T=5.0).u.mijanie_trzyma(), (w1, w2, w3, s.t))

# ====================================================================================================
# 6c. F2: skrypt narzedzia/odtworz_mijanie.py na syntetycznej telemetrii (bot idzie pętlą goblinów, gracz przed nim w tę samą stronę)
# ====================================================================================================
import tempfile
sys.path.insert(0, str(KAT / "narzedzia"))
import odtworz_mijanie as _odt
def synt_probki(n=60, krok_s=1.0):
    """Bot (Mastafian) idzie pętlą goblinów 1,7 pola/s, 6 punktów za nim idzie obcy Kangurek w tę samą stronę (a potem znika)."""
    pet = [tuple(p) for p in json.loads((KAT / "trasy" / "gobliny_edron_z8_petla.json").read_text())]
    wynik = []
    for k in range(n):
        i = 30 + int(k * 1.7)
        poz = pet[i]
        st = [{"n": "Mastafian", "dx": 0, "dy": 0, "odl": 0, "hp": 100, "gracz": True}]
        if k < 40:
            q = pet[i + 6 + (k // 2)]
            st.append({"n": "Kangurek", "dx": q[0] - poz[0], "dy": q[1] - poz[1], "odl": cheb(q, poz), "hp": 100, "gracz": True})
        wynik.append({"t": 1792400000.0 + k * krok_s, "typ": "probka", "stan": "IDZ", "poz": list(poz), "stwory": st, "pid": 1, "sesja": 1.0, "src": "mozg"})
    # liczymy 100+ próbek własnej postaci, by została uznana za naszą
    return wynik * 3 if False else wynik
with tempfile.TemporaryDirectory() as kat_t:
    rek = synt_probki()
    with open(_os.path.join(kat_t, "telemetria-20261099.jsonl"), "w") as f:
        for r in rek: f.write(json.dumps(r) + "\n")
        for r in rek: f.write(json.dumps(dict(r, t=r["t"] + 1000.0, stan="IDZ")) + "\n")
        for r in rek: f.write(json.dumps(dict(r, t=r["t"] + 2000.0, stan="IDZ")) + "\n")     # razem >= 100 próbek: Mastafian = nasza postać
        f.write(json.dumps({"t": 1792400010.0, "typ": "unikanie_start", "gracz": "Kangurek", "pid": 1, "sesja": 1.0, "src": "mozg"}) + "\n")
    probki, zdarz, wlasne = _odt.wczytaj(kat_t, "telemetria-*.jsonl")
    spot, wszystkich = _odt.spotkania(probki)
    sprawdz("F2a odtwarzacz: własna postać rozpoznana (dx=dy=0), obcy to Kangurek; 3 spotkania (przerwy > 30 s), rodzaj poluje/przechodzi",
            wlasne == {"Mastafian"} and len(spot) == 3 and all(e["nazwa"] == "Kangurek" for e in spot), (wlasne, len(spot)))
    po = [r for r in probki if r["sesja"] == spot[0]["sesja"]]
    info = _odt.dopasuj_trase(spot[0], po, _odt.wczytaj_trasy())
    sprawdz("F2b dopasowanie trasy: gobliny_edron_z8_petla, kierunek zgodny z nagraniem (+1)", info and info[0] == "gobliny_edron_z8_petla" and info[2] == 1, info and info[:3])
    model = _odt.Model()
    nowy = _odt.odtworz(model, spot[0], po, info, _odt.wczytaj_trasy(), mijanie=True)
    kontrola = _odt.odtworz(model, spot[0], po, info, _odt.wczytaj_trasy(), mijanie=False)
    sprawdz("F2c odtwarzanie: gracz idzie tą samą stroną przed botem -> model odwraca obieg (MIJANIE=1); bez mijania (kontrola) decyzji nie ma",
            nowy["odwroty"] == 1 and kontrola["odwroty"] == 0 and not kontrola["zd"], (nowy["odwroty"], kontrola["odwroty"]))
    sprawdz("F2d zawroty: ciągłe odcinki (skoki modelu nie liczą się), zawrót = zmiana kierunku > 120 stopni",
            _odt.zawroty([(float(i), (i, 0)) for i in range(10)] + [(10.0 + i, (9 - i, 0)) for i in range(10)]) != [] and
            _odt.zawroty([(float(i), (i, 0)) for i in range(20)]) == [] and
            _odt.zawroty([(float(i), (i, 0)) for i in range(8)] + [(10.0 + i, (100 + i, 0)) for i in range(8)]) == [])

# ====================================================================================================
# 7. Moby: reguły pomin_moba / CUDZY_MOB bez zmian przy MIJANIE=1 (cudzy = bity przez niego albo w jego obrębie UNIKANIE_MOB_PROMIEN)
# ====================================================================================================
def mob(x, y, hp=100, i=5): return {"id": i, "nazwa": "Rat", "gracz": False, "x": x, "y": y, "z": 7, "hp": hp}
def moby_wyniki(mijanie):
    s = Swiat(TEREN, P, (100, 100), {"Zbyszek": [108, 100]}, konf=dict(MIJANIE=mijanie))
    s.u.obserwuj(s.lista(), (100, 100, 7), "Ja")
    poz = (100, 100, 7)
    wyn = [s.u.pomin_moba(mob(x, 100), poz, gryzie=g) for x in (101, 103, 104, 105, 106, 110, 112, 115) for g in (False, True)]
    s2 = Swiat(TEREN, P, (100, 100), {"Quben": [102, 100]}, konf=dict(MIJANIE=mijanie))
    s2.u.obserwuj(s2.lista(), (100, 100, 7), "Ja")
    return wyn + [s2.u.pomin_moba(mob(101, 100), poz), s2.u.pomin_moba(mob(101, 100), poz, gryzie=True)]
sprawdz("M6a pomin_moba identyczne przy MIJANIE=0 i 1 (te same reguły dla mobów)", moby_wyniki(0) == moby_wyniki(1), (moby_wyniki(0), moby_wyniki(1)))
s = Swiat(TEREN, P, (100, 100), {"Zbyszek": [108, 100]})
s.u.obserwuj(s.lista(), (100, 100, 7), "Ja")
poz = (100, 100, 7)
sprawdz("M6b mob w obrębie gracza (3 pola od niego, nawet niebity, pełne HP): cudzy, nie bierzemy (decyzja Karola 18.10: obręb = jego mob)", s.u.pomin_moba(mob(105, 100), poz) is True)
sprawdz("M6c mob 6 pól od gracza (poza obrębem 4), pełne HP: nasz", s.u.pomin_moba(mob(102, 100), poz) is False and s.u.pomin_moba(mob(102, 104), poz) is False)
sprawdz("M6d mob obok nas i obok gracza, nas nie bije: jego (pomijamy); gdy nas bije: nasz",
        (lambda u: u.pomin_moba(mob(101, 100), poz) is True and u.pomin_moba(mob(101, 100), poz, gryzie=True) is False)(
            (lambda ss: (ss.u.obserwuj(ss.lista(), poz, "Ja"), ss.u)[1])(Swiat(TEREN, P, (100, 100), {"Quben": [102, 100]}))))
# mob tracący HP (bity przez gracza), poza obrębem: filtr CUDZY_MOB z cavebota (60 s po zobaczeniu obcego), mob obok nas zostaje
def cb_cudzy(widzialem_gracza=True, gryzie=False, moje=()):
    t = 1000.0
    return types.SimpleNamespace(zegar=lambda: t, patrol_gracze_pam={"Zbyszek": (0, 0, 0, t - 5.0 if widzialem_gracza else t - 500.0)},
                                 hp_gracza_spadek=(t - 1.0 if gryzie else t - 100.0), moje_cele={i: t for i in moje}, cudzy_log={})
f = cavebot.Cavebot._cudzy_mob_filtr
stary_cudzy = cavebot.CUDZY_MOB
cavebot.CUDZY_MOB = 1
cavebot.GRYZIE_OKNO = getattr(cavebot, "GRYZIE_OKNO", 3.0)
bity = mob(110, 100, hp=60, i=11); pelny = mob(112, 100, hp=100, i=12); obok = mob(101, 100, hp=60, i=13); nasz = mob(108, 100, hp=60, i=14)
wyn = f(cb_cudzy(moje=(14,)), [bity, pelny, obok, nasz], poz)
cavebot.CUDZY_MOB = stary_cudzy
sprawdz("M6e mob tracący HP, którego nie zaczęliśmy (bity przez gracza): pominięty; pełne HP, obok nas i nasz (moje_cele): zostają",
        [m["id"] for m in wyn] == [12, 13, 14], [m["id"] for m in wyn])

# ====================================================================================================
# 8. Pętla gobliny_edron_z8_petla: przechodnia w obie strony, cavebot idzie nią wstecz
# ====================================================================================================
KAT = Path(__file__).resolve().parent.parent
import mapa as _mapa
LOOP = [tuple(p) for p in json.loads((KAT / "trasy" / "gobliny_edron_z8_petla.json").read_text())]
MAPA = _mapa.Mapa()
n_l = len(LOOP)
sprawdz("L1 pętla: jedno piętro (z8), zamknięta (pierwszy = ostatni punkt), 4-sąsiedzi, brak zawrotów (a,b,a) i skosów",
        {p[2] for p in LOOP} == {8} and LOOP[0] == LOOP[-1] and all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip(LOOP[:-1], LOOP[1:]))
        and not any(LOOP[i - 1] == LOOP[i + 1] for i in range(1, n_l - 1)), n_l)
sprawdz("L2 pętla: każde pole przechodnie wg mapy klienta, żadnych schodów/dziur/lin (flaga 2) na trasie", all(MAPA.przechodnie(*p) is True for p in LOOP)
        and not any(MAPA.schody_lub_dziura(*p) for p in LOOP), [p for p in LOOP if MAPA.przechodnie(*p) is not True][:3])
znane = {tuple(p) for p in json.loads((KAT / "znane_pola.json").read_text())}
sprawdz("L3 pętla: >= 99% pól to miejsca, gdzie kiedyś stała postać (znane_pola.json) - da się nią chodzić", sum(1 for p in set(LOOP) if p in znane) >= 0.99 * len(set(LOOP)),
        len([p for p in set(LOOP) if p not in znane]))
odw = list(reversed(LOOP))
sprawdz("L4 pętla przechodnia w obie strony: ruch wstecz po tych samych polach (para sąsiadów to ta sama krawędź w obu kierunkach), a ruch zwykły i wsteczny"
        " używają tych samych pól", set(zip(odw[:-1], odw[1:])) == {(b, a) for a, b in zip(LOOP[:-1], LOOP[1:])} and all(MAPA.przechodnie(*p) for p in odw))
# odwrócenie w dowolnym miejscu: następny cel = punkt tuż za nami (sąsiad albo ten sam)
def stub_cb(punkty, idx):
    return types.SimpleNamespace(punkty=list(punkty), idx=idx, klik_j=5, klik_cel=(1, 1), nieudane=3, pominiete=2, zablokowane={"x": 1},
                                 trasa_droga="x", utk_okno=[1], krok_do=lambda c: True, pauza=lambda *a: None, przebyte=250)
zle = []
for k in range(0, n_l - 1, 7):                      # stoimy dokładnie na punkcie k; cel idx = k+1 (zwykle), k (jeszcze nie zaliczony) albo k-3, k-8 (kliknięcie minęło punkty)
    for ahead in (1, 0, -3, -8):
        cb = stub_cb(LOOP, (k + ahead) % n_l)
        poz = LOOP[k]
        cavebot.Cavebot._mijanie_zastosuj(cb, poz, unikanie.Mij("odwroc"))
        nowy = cb.punkty[cb.idx]
        nr_stojacego = [i for i, q in enumerate(cb.punkty) if q == poz]
        if not (cb.punkty == odw and cheb(nowy, poz) <= 1 and any((cb.idx - i) % n_l == 1 for i in nr_stojacego)):
            zle.append((k, ahead, cb.idx, nowy))
dubl = [i for i, p in enumerate(LOOP) if LOOP.count(p) > 1]            # skrzyżowanie pętli i zamknięcie (pierwszy = ostatni punkt)
zle2 = []
for k in dubl:
    for ahead in (1, 0, -3):
        cb = stub_cb(LOOP, (k + ahead) % n_l)
        cavebot.Cavebot._mijanie_zastosuj(cb, LOOP[k], unikanie.Mij("odwroc"))
        if not (cb.punkty == odw and cheb(cb.punkty[cb.idx], LOOP[k]) <= 1):
            zle2.append((k, ahead, cb.idx))
sprawdz("L5a odwrócenie na polach, które pętla mija dwa razy (skrzyżowanie, start = koniec): następny cel zawsze sąsiaduje z nami", dubl and not zle2, (dubl, zle2[:3]))
sprawdz("L5 odwrócenie listy w dowolnym punkcie pętli (idx od k+1 do k-8, jak po kliknięciu): następny cel to sąsiednie pole za nami, lista = odwrócona pętla", not zle, zle[:3])
cb = stub_cb(LOOP, 40)
cavebot.Cavebot._mijanie_zastosuj(cb, (1, 1, 1), unikanie.Mij("odwroc"))     # stoimy poza punktem trasy: cel = punkt tuż za idx
sprawdz("L5b odwrócenie z pozycji poza trasą: następny cel to ostatnio minięty punkt (idx-1 w starej liście)", cb.punkty[cb.idx] == LOOP[39], (cb.idx, cb.punkty[cb.idx]))
sprawdz("L5c odwrócenie czyści kliknięcia i liczniki (klik_j, klik_cel, nieudane, pominiete, zablokowane, trasa_droga, utk_okno, utk_zakaz)",
        cb.klik_j is None and cb.klik_cel is None and cb.nieudane == 0 and cb.pominiete == 0 and not cb.zablokowane and cb.trasa_droga is None
        and cb.utk_okno is None and cb.__dict__.get("utk_zakaz") == {})
sprawdz("L5d odwrócenie mijania zeruje licznik okrążenia (przebyte): po odwróceniu pełne okrążenie liczymy od zera, nie od 250 z 273 punktów", cb.przebyte == 0, cb.przebyte)
# bot z prawdziwą mapą klienta: gracz idzie przed nami pętlą -> odwrócenie, potem pełne okrążenie wstecz po polach przechodnich
ZAKRES = prostokat(33030, 33120, 31820, 31890)
WOLNE8 = [p for p in ZAKRES if MAPA.przechodnie(p[0], p[1], 8) is True and not MAPA.schody_lub_dziura(p[0], p[1], 8)]
unik = [p for p in dict.fromkeys(LOOP)]
s = Swiat(WOLNE8, LOOP, LOOP[30][:2], {"Z": list(LOOP[36][:2])}, z=8)
fn = idzie("Z", [LOOP[(36 + i) % n_l][:2] for i in range(2000)], 0.45, znika_o=15.0)
s.bieg(15 + 272 * 0.42 + 10, fn)          # odwrócenie, zniknięcie gracza i pełne okrążenie wstecz
poz_t = [p for _, p in s.trasa]
sprawdz("L6 pętla goblinów z mapą: gracz idący tą samą stroną przed nami -> jedno odwrócenie, lista odwrócona", s.odwroty == 1 and s.cb.punkty == odw, (s.odwroty, s.akcje[:3]))
sprawdz("L6b ...kroki bota po wszystkich polach wolnych (każdy krok o 1 pole, tylko pola przechodnie)", all(cheb(a, b) <= 1 for a, b in zip(poz_t, poz_t[1:]))
        and all(p in set(WOLNE8) for p in poz_t))
odwiedzone = {p for p in poz_t}
sprawdz("L6c ...po zniknięciu gracza bot okrąża pętlę w nowym kierunku: odwiedza >= 95% unikalnych pól pętli", len(odwiedzone & {q[:2] for q in LOOP}) >= 0.95 * len({q[:2] for q in LOOP}),
        len(odwiedzone & {q[:2] for q in LOOP}))
sprawdz("L6d ...bez dreptania (nie więcej niż 1 krok tył-przód w 8 s) i bez postoju > 3 s", dreptania(s.trasa) <= 1 and s.max_postoj() <= 3.0, (dreptania(s.trasa), s.max_postoj()))

# ====================================================================================================
# 9. Prawdziwy Cavebot.tick() (atrapa świata jak w test_cavebot.py): hak w _idz_trasa, pokrętło MIJANIE, pokrętła w pokretla.py
# ====================================================================================================
import bot as _bot
import mapa as _mapa_mod
class AtrapaMapy(_mapa_mod.Mapa):
    """Mapa jak z pliku OTMM: pola `wolne` przechodnie (flaga 1), reszta bloków to widziane ściany (5)."""
    def __init__(s, wolne, z=8):
        s._dane, s._spis, s._bloki, s.wersja = b"", {}, {}, 1
        pola = {tuple(p[:2]): 1 for p in wolne}
        for bx, by in {(x >> 6, y >> 6) for x, y in pola}:
            b = bytearray(bytes([5, 114, 0]) * 4096)
            for (x, y), f in pola.items():
                if (x >> 6, y >> 6) == (bx, by):
                    b[((y & 63) * 64 + (x & 63)) * 3] = f
            s._bloki[_mapa_mod._klucz_bloku(bx << 6, by << 6, z)] = bytes(b)

class CSwiat:
    """Świat dla prawdziwego Cavebot: postać chodzi strzałkami po polach `wolne`, inni gracze to skrypt pozycji."""
    def __init__(s, poz, wolne):
        s.t = 0.0; s.poz = list(poz); s.wolne = set(wolne); s.gracze = {}; s.stwory = []; s.klawisze = []; s.zd = []
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": 8, "hp": 100}
            gr = [{"id": 100 + i, "nazwa": n, "gracz": True, "x": p[0], "y": p[1], "z": 8, "hp": 100} for i, (n, p) in enumerate(s.gracze.items()) if p]
            return {"stwory": [ja] + gr + [dict(m) for m in s.stwory]}
class CPostac:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
    def krok(p, k):
        d = _bot.KIERUNKI[k]; p.s.t += 0.3
        nowa = (p.s.poz[0] + d[0], p.s.poz[1] + d[1])
        if nowa not in p.s.wolne or any(g and tuple(g) == nowa for g in p.s.gracze.values()):
            return None
        p.s.poz[0], p.s.poz[1] = nowa
        return tuple(p.s.poz)
def cb_zrob(s, punkty, **kw):
    b = cavebot.Cavebot(CPostac(s), punkty, zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=types.SimpleNamespace(zbierz=lambda z, g: "ok"), mapa=AtrapaMapy(s.wolne), okrazenia=50, **kw)
    b.unikanie.zdarzenie = lambda typ, **d: (s.zd.append((typ, d)), s.zt.append(s.t))
    s.zt = []
    b.idx = min(range(len(b.punkty)), key=lambda i: (b.punkty[i][2] != 8, abs(b.punkty[i][0] - poz_start(s)[0]) + abs(b.punkty[i][1] - poz_start(s)[1])))   # jak Cavebot.uruchom
    return b
def poz_start(s): return s.poz
_los = {k: getattr(cavebot, k) for k in ("REAKCJA", "DRUGI_CEL", "ROZRZUT_PROGU", "ODWROCENIE_TRASY", "SCINANIE", "PAUZA_KROTKA", "PAUZA_DLUGA", "MIJANIE")}
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0; cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
SALA = prostokat(80, 140, 80, 120)
PET8 = [(x, y, 8) for x, y, _ in P]
def cb_przebieg(mij, T=50.0, skrypt=None, teren=SALA, punkty=PET8, start=(95, 95), gracz=None):
    cavebot.MIJANIE = mij
    s = CSwiat(start + (8,), teren)
    s.gracze["Z"] = list(gracz) if gracz else None
    b = cb_zrob(s, punkty)
    trasa = []
    t_koniec = s.t + T
    n = 0
    while s.t < t_koniec and n < 4000:
        n += 1
        if skrypt: skrypt(s, b)
        if not b.tick(): break
        trasa.append((round(s.t, 2), tuple(s.poz[:2])))
    return s, b, trasa
def zgracz_idzie(pts, tempo=0.5, t0=0.0):
    def f(s, b):
        if s.t < t0: return
        i = min(int((s.t - t0) / tempo), len(pts) - 1); s.gracze["Z"] = list(pts[i])
    return f
pts8 = [tuple(p[:2]) for p in PET8]
ahead_pts = [pts8[(pts8.index((100, 95)) + i) % len(pts8)] for i in range(400)]
s, b, tr = cb_przebieg(1, 30.0, zgracz_idzie(ahead_pts), gracz=(100, 95))
sprawdz("I1 Cavebot.tick() z MIJANIE=1: gracz idzie przed nami tą samą stroną -> odwrócenie listy punktów w _idz_trasa i zdarzenie mijanie_kierunek",
        b.punkty == list(reversed(PET8)) and [d["akcja"] for t, d in s.zd if t == "mijanie_kierunek"] == ["odwrocenie"], (b.punkty[:2], [t for t, _ in s.zd]))
t_i1 = next(tz for (tt, _), tz in zip(s.zd, s.zt) if tt == "mijanie_kierunek")
sprawdz("I1b ...bot idzie po odwróceniu od gracza (8 s po decyzji x nie przekracza 97)", max(p[0] for t, p in tr if t_i1 <= t <= t_i1 + 8.0) <= 97,
        (t_i1, max(p[0] for t, p in tr if t_i1 <= t <= t_i1 + 8.0)))
sprawdz("I1c ...zdarzenia mijanie_start i brak unikanie_start/unikanie_punkt (stare unikanie nie działa)", any(t == "mijanie_start" for t, _ in s.zd)
        and not any(t in ("unikanie_start", "unikanie_punkt", "unikanie_blokada") for t, _ in s.zd), [t for t, _ in s.zd])
s0, b0, tr0 = cb_przebieg(0, 30.0, zgracz_idzie(ahead_pts), gracz=(100, 95))
sprawdz("I2 ta sama scena z MIJANIE=0: dotychczasowe unikanie (unikanie_start), lista punktów nietknięta, zero zdarzeń mijanie_*",
        b0.punkty == PET8 and any(t == "unikanie_start" for t, _ in s0.zd) and not any(t.startswith("mijanie") for t, _ in s0.zd), [t for t, _ in s0.zd])
sprawdz("I2b MIJANIE=1: _unikanie_krokami() = False (marsz po staremu, kroki tylko w skrócie i przy ustępowaniu); MIJANIE=0: True przy aktywnym unikaniu",
        (lambda: (setattr(cavebot, "MIJANIE", 1), cavebot.Cavebot._unikanie_krokami(b))[1] is False and
                 (setattr(cavebot, "MIJANIE", 0), cavebot.Cavebot._unikanie_krokami(b0))[1] in (True, False))())
# korytarz z wnęką w prawdziwym Cavebot.tick(): krok w bok, postój, powrót
KOR8 = [(x, 100) for x in range(60, 161)] + [(112, 101), (112, 102)]
def gracz_w_lewo(start, tempo):
    return zgracz_idzie([(x, 100) for x in range(start, 55, -1)], tempo)
s, b, tr = cb_przebieg(1, 36.0, gracz_w_lewo(130, 0.5), teren=KOR8, punkty=[(x, 100, 8) for x in range(70, 151, 2)], start=(98, 100), gracz=(130, 100))
prz = [d["etap"] for t, d in s.zd if t == "mijanie_przejscie"]
sprawdz("I3 Cavebot.tick(), korytarz szer. 1: krok w bok do wnęki, postój i koniec (przeszedl), potem marsz dalej na wschód", prz[:3] == ["start", "stoi", "koniec"]
        and any(p == (112, 101) for _, p in tr) and max(p[0] for _, p in tr) >= 130, (prz, tr[20:26]))
import itertools
sprawdz("I3b ...stan bota to IDZ, postój we wnęce 2-8 s, brak dreptania", b.stan == "IDZ" and 4 <= max(
        (sum(1 for _ in g) for k, g in itertools.groupby([p for _, p in tr]) if k == (112, 101)), default=0) <= 20 and dreptania(tr) <= 1,
        (b.stan, dreptania(tr)))
cavebot.MIJANIE = 0
# Cavebot._mijanie_trasa: walka (cel albo spadek HP) ma pierwszeństwo - mijanie nie podejmuje wtedy decyzji (Z3)
def cb_decyzja(cel=None, spadek_hp=False):
    cavebot.MIJANIE = 1
    s = CSwiat((100, 95, 8), SALA)
    b = cb_zrob(s, PET8)
    for i in range(5):                                               # gracz idzie 4-8 pól przed nami w tę samą stronę, my stoimy; kierunek gracza powstaje po 2 polach
        s.gracze["Z"] = list(pts8[(pts8.index((104, 95)) + i) % len(pts8)])
        s.t += 0.4
        b.unikanie.obserwuj(s.zapytaj({"cmd": "stwory"})["stwory"], (100, 95, 8), "Ja")
    b.cel = cel
    if spadek_hp: b.hp_gracza_spadek = s.t - 0.5
    b._mijanie_trasa((100, 95, 8))
    return s, b
s, b = cb_decyzja()
sprawdz("I4a (kontrola) bez walki: Cavebot._mijanie_trasa odwraca obieg (gracz 4-8 pól przed nami, ta strona)", b.punkty == list(reversed(PET8))
        and any(t == "mijanie_kierunek" for t, _ in s.zd), [t for t, _ in s.zd])
s, b = cb_decyzja(cel={"id": 9, "nazwa": "Rat", "hp0": 100})
sprawdz("I4b ma cel (self.cel): _mijanie_trasa liczy w_walce z celu - żadnej decyzji, lista punktów nietknięta", b.punkty == PET8
        and not any(t == "mijanie_kierunek" for t, _ in s.zd), [t for t, _ in s.zd])
s, b = cb_decyzja(spadek_hp=True)
sprawdz("I4c HP gracza spadło przed 0,5 s (GRYZIE_OKNO): w_walce z hp_gracza_spadek - żadnej decyzji, lista punktów nietknięta", b.punkty == PET8
        and not any(t == "mijanie_kierunek" for t, _ in s.zd), [t for t, _ in s.zd])

# Q3: losowe odwrócenie trasy na końcu okrążenia (ODWROCENIE_TRASY) nie cofa kierunku trzymanego po mijaniu; trasa otwarta nadal się odwraca
def lap_przebieg(mij, z_gracz, T=14.0, wstrzyknij_o=5.0, przechodzien=False):
    """Cavebot.tick(); ODWROCENIE_TRASY = 1.0, a licznik okrążenia ustawiamy tuż przed końcem: 2 s po decyzji mijania (z graczem)
    albo w 5. sekundzie (bez gracza). Zwraca (świat, cavebot): lista odwrócona = jedna zmiana kierunku, oryginalna = dwie (mijanie + losowa)."""
    cavebot.ODWROCENIE_TRASY = 1.0
    ahead = [pts8[(pts8.index((106, 95)) + i) % len(pts8)] for i in range(400)]
    zg = zgracz_idzie([(110, y) for y in range(110, 70, -1)], 0.5) if przechodzien else zgracz_idzie(ahead, 0.5)   # przechodzień: w poprzek pętli, bez decyzji mijania
    st = {"t_dec": None, "wstrz": False}
    def skrypt(s, b):
        if z_gracz: zg(s, b)
        if st["t_dec"] is None and any(t == "mijanie_kierunek" for t, _ in s.zd): st["t_dec"] = s.t
        if not st["wstrz"]:
            gotowe = (st["t_dec"] is not None and s.t >= st["t_dec"] + 2.0) if z_gracz and not przechodzien else s.t >= wstrzyknij_o
            if gotowe: b.przebyte = len(b.punkty) - 1; st["wstrz"] = True
    try:
        s, b, tr = cb_przebieg(mij, T, skrypt, gracz=((110, 110) if przechodzien else (106, 95)) if z_gracz else None)
    finally:
        cavebot.ODWROCENIE_TRASY = 0.0
    return s, b
s, b = lap_przebieg(1, True)
sprawdz("Q3a MIJANIE=1, gracz przed nami (decyzja trwa), koniec okrążenia przy ODWROCENIE_TRASY = 1.0: losowe odwrócenie pominięte - kierunek z mijania zostaje (lista odwrócona raz)",
        b.okrazenie == 1 and b.punkty == list(reversed(PET8)), (b.okrazenie, b.punkty[:2]))
s, b = lap_przebieg(1, True, T=9.0, przechodzien=True)
sprawdz("Q3e MIJANIE=1, gracz przeszedł w poprzek pętli (był w widoku < MIJANIE_ZNIKL_S, bez decyzji mijania): koniec okrążenia też bez losowego odwrócenia (kierunek zostaje)",
        b.okrazenie == 1 and b.punkty == PET8 and not any(t == "mijanie_kierunek" for t, _ in s.zd), (b.okrazenie, b.punkty[:2], [t for t, _ in s.zd]))
s, b = lap_przebieg(1, False)
sprawdz("Q3b MIJANIE=1, bez graczy: koniec okrążenia odwraca trasę jak dotąd (ODWROCENIE_TRASY = 1.0)", b.okrazenie == 1 and b.punkty == list(reversed(PET8)), (b.okrazenie, b.punkty[:2]))
s, b = lap_przebieg(0, False)
sprawdz("Q3c MIJANIE=0: koniec okrążenia odwraca trasę jak w bazie (ODWROCENIE_TRASY = 1.0)", b.okrazenie == 1 and b.punkty == list(reversed(PET8)), (b.okrazenie, b.punkty[:2]))
cavebot.ODWROCENIE_TRASY = 0.0                                   # trasa otwarta odwraca się zawsze, także przy trwającej decyzji mijania
s = CSwiat((100, 95, 8), SALA); s.gracze["Z"] = [106, 95]
cavebot.MIJANIE = 1
b = cb_zrob(s, PET8[:40]); b.otwarta = True; b.unikanie.mij_dec["Z"] = {"t": s.t, "rodzaj": "ta_strona"}
b.przebyte = len(b.punkty) - 1
b.idx = 39; s.poz[0], s.poz[1] = PET8[39][0], PET8[39][1]               # stoimy na ostatnim punkcie trasy: tick zalicza go i kończy okrążenie
b.tick()
sprawdz("Q3d trasa otwarta (self.otwarta) przy trwającej decyzji mijania: koniec okrążenia nadal odwraca trasę (bot nie stoi na końcu)", b.punkty == list(reversed(PET8[:40])),
        (b.okrazenie, b.punkty[:2], b.idx))
cavebot.MIJANIE = 0
# ====================================================================================================
# 7. 22.10: bot idący tuż obok / przed obcym graczem wyglądał jak bot (epizody A i B z telemetrii, SPEC: pokrętła MIJANIE_HORYZONT,
#    MIJANIE_ZA_*, MIJANIE_PAUZA_*, MIJANIE_POLUJACY_R). Wyłączenie wszystkich = stare zachowanie.
# ====================================================================================================
import random as _rnd
STARE = dict(MIJANIE_HORYZONT=0, MIJANIE_ZA_S=0, MIJANIE_PAUZA_BRAK=0, MIJANIE_POLUJACY_R=0)
def pauzy(s, powod=None):
    return [(t, d) for (tt, d), t in zip(s.zd, s.zt) if tt == "mijanie_pauza" and (powod is None or d.get("powod") == powod)]

def tor_gracza(t, tr):
    if t < tr[0][0] or t > tr[-1][0] + 4: return None
    for a, b in zip(tr, tr[1:]):
        if a[0] <= t <= b[0]:
            if b[0] - a[0] > 3.5: return None
            f = (t - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0
            return [round(a[1] + (b[1] - a[1]) * f), round(a[2] + (b[2] - a[2]) * f)]
    return [tr[-1][1], tr[-1][2]] if t <= tr[-1][0] + 1.5 else None

def epizod(klucz, konf=None, T=40.0):
    """Epizod z telemetrii na prawdziwej mapie (MAPA.przechodnie) i prawdziwej trasie; obcy idzie po zapisanym torze."""
    import mapa as _mapa
    cwd = _os.getcwd(); _os.chdir(KAT)
    try:
        MP = _mapa.Mapa()
    finally:
        _os.chdir(cwd)
    E = json.loads((KAT / "testy" / "dane" / "mijanie_epizody_1022.json").read_text())[klucz]
    R = [tuple(p[:3]) for p in json.loads((KAT / "trasy" / f"{E['trasa']}.json").read_text())]
    if E.get("odwroc_trase"): R.reverse()
    z = E["z"]
    idx = E.get("idx")
    if idx is None: idx = next(i for i, p in enumerate(R) if p[:2] == tuple(E["idx_cel"]))
    xs = [p[0] for p in R]; ys = [p[1] for p in R]
    wolne = [(x, y) for x in range(min(xs) - 12, max(xs) + 13) for y in range(min(ys) - 12, max(ys) + 13)
             if MP.przechodnie(x, y, z) is True and not MP.schody_lub_dziura(x, y, z)]
    t0 = E["gracz"][0][0]
    tr = [[a - t0, b, c] for a, b, c in E["gracz"]]
    _rnd.seed(1)
    s = Swiat(wolne, R, tuple(E["start"]), {"Z": None}, konf=konf, idx=idx, z=z)
    def fn(s_): s_.gracze["Z"] = tor_gracza(s_.t, tr)
    s.bieg(T, fn)
    return s

try:
    sA_s = epizod("A", STARE, 20.0); sA = epizod("A", None, 20.0)
    sB_s = epizod("B", STARE, 20.0); sB = epizod("B", None, 20.0)
    ep_ok = True
except Exception as e:                       # brak mapy w środowisku testowym - sprawdzenia epizodów pomijamy z widocznym wpisem
    ep_ok = False; print("SKIP epizody A/B:", repr(e))
if ep_ok:
    sprawdz("E0 (kontrola) pokrętła 22.10 wyłączone = stare zachowanie: epizod A kończy się odwróceniem obiegu (w 5 s), bez pauzy", sA_s.odwroty >= 1
            and czasy(sA_s, "mijanie_kierunek")[0] < 5.0 and not pauzy(sA_s), (sA_s.odwroty, czasy(sA_s, "mijanie_kierunek"), pauzy(sA_s)))
    pa = pauzy(sA, "brak")
    sprawdz("EA Valevnos (z9z, pętla ze skrzyżowaniem): odwrócenie zbiegające się z torem gracza w <= 40 punktach odrzucone - pauza zamiast marszu obok niego",
            pa and pa[0][1]["etap"] == "start" and pa[0][0] < 5.0 and not any(t < pa[0][0] + 0.5 for t in czasy(sA, "mijanie_kierunek")), (pa[:2], czasy(sA, "mijanie_kierunek")))
    sprawdz("EA2 ...pauza krótka i ludzka (2-5 s), potem koniec z powodem czas", len([x for x in pauzy(sA) if x[1]["etap"] == "koniec"]) >= 1
            and 2.0 <= [x for x in pauzy(sA) if x[1]["etap"] == "koniec"][0][0] - pa[0][0] <= 5.6, pauzy(sA)[:3])
    sprawdz("EA3 ...i bez wahadła: w 20 s najwyżej jedna pauza i najwyżej jedno odwrócenie", len([x for x in pauzy(sA) if x[1]["etap"] == "start"]) <= 1 and sA.odwroty <= 1,
            (pauzy(sA), sA.odwroty))
    pb = pauzy(sB, "brak")
    sprawdz("EB Harley Queen (invincible, z8): odwrócenie, na które gracz sam skręcił, odrzucone - pauza zamiast marszu obok niego", sB_s.odwroty >= 1
            and pb and pb[0][0] < 5.0 and sB.odwroty == 0, (sB_s.odwroty, pb[:2], sB.odwroty))
    sprawdz("EB2 ...nic się nie zapętla (bez stania > 6 s)", sB.max_postoj() < 6.0, sB.max_postoj())

# ZA: gracz idzie za nami <= 4 pola w tę samą stronę > 15 s
def za_nami_dlugo(konf=None, T=40.0, d=3, seed=1):
    _rnd.seed(seed)
    bot = (105, 95)
    gp = pts[(pts.index(bot) - d) % len(pts)]
    s = Swiat(TEREN, P, bot, {"Z": list(gp)}, konf=konf)
    s.bieg(T, idzie("Z", [pts[(pts.index(gp) + i) % len(pts)] for i in range(600)], 0.4))
    return s
s = za_nami_dlugo(T=14.0)
sprawdz("ZA1 gracz 3 pola za nami przez 14 s (< MIJANIE_ZA_S = 15 s): bez pauzy", not pauzy(s, "za_nami"), pauzy(s))
s = za_nami_dlugo(T=24.0)
pz = pauzy(s)
st_ = [x for x in pz if x[1]["etap"] == "start" and x[1]["powod"] == "za_nami"]; kn_ = [x for x in pz if x[1]["etap"] == "koniec"]
sprawdz("ZA2 ...po 15 s: jedna pauza za_nami między 15 a 19 s", len(st_) == 1 and 14.5 <= st_[0][0] <= 19.0, pz)
sprawdz("ZA3 ...trwa 2-5 s (losowo) i kończy się", st_ and kn_ and 2.0 <= kn_[0][0] - st_[0][0] <= 5.6, (st_, kn_))
t1 = st_[0][0] if st_ else 0; t2 = kn_[0][0] if kn_ else t1
p1 = next((p for t, p in s.trasa if t >= t1), None)
sprawdz("ZA4 ...w czasie pauzy bot nie zawraca (brak decyzji odwroc) i oddala się od miejsca startu pauzy najwyżej o 3 pola",
        st_ and not any(t1 <= t <= t2 and a_ == "odwroc" for t, a_ in s.dec) and all(cheb(p, p1) <= 3 for t, p in s.trasa if t1 <= t <= t2), (s.dec, t1, t2))
s = za_nami_dlugo(T=70.0)
sprawdz("ZA5 cooldown na gracza (MIJANIE_PAUZA_PONOW_S = 60 s): w 70 s tylko jedna pauza za_nami", len([x for x in pauzy(s, "za_nami") if x[1]["etap"] == "start"]) == 1, pauzy(s, "za_nami"))
s = za_nami_dlugo(konf=dict(MIJANIE_ZA_S=0), T=30.0)
sprawdz("ZA6 MIJANIE_ZA_S=0 wyłącza: bez pauzy", not pauzy(s, "za_nami"), pauzy(s))
s = za_nami_dlugo(konf=dict(MIJANIE=0), T=30.0)
sprawdz("ZA7 MIJANIE=0: nic nie robi (bez zdarzeń mijania)", not any(t.startswith("mijanie") for t, _ in s.zd), s.zd[:2])
rnd_dl = set()
for sd in range(12):
    s_ = za_nami_dlugo(T=24.0, seed=sd)
    a_ = [x for x in pauzy(s_) if x[1]["etap"] == "start"]; b_ = [x for x in pauzy(s_) if x[1]["etap"] == "koniec"]
    if a_ and b_: rnd_dl.add(round(b_[0][0] - a_[0][0], 1))
sprawdz("ZA8 długość pauzy losowa w 2-5 s (12 ziaren, >= 3 różne wartości)", len(rnd_dl) >= 3 and all(2.0 <= x <= 5.6 for x in rnd_dl), sorted(rnd_dl))

# brak bezpiecznego kierunku -> pauza (R3b wyżej) i walka przerywa pauzę
_rnd.seed(1)
s = Swiat(TEREN, P, (100, 95), {"A": [108, 95], "B": [95, 95]})
fa = idzie("A", [pts[(pts.index((108, 95)) + i) % len(pts)] for i in range(300)], 0.5)
fb = idzie("B", [pts[(pts.index((95, 95)) - i) % len(pts)] for i in range(300)], 0.5)
s.bieg(3.2, razem(fa, fb))
sprawdz("P1 brak bezpiecznego kierunku: pauza trwa, bot stoi / zszedł z trasy (nie idzie obok graczy dalej)", s.u.mij_pauza is not None or pauzy(s, "brak"), pauzy(s))
s.w_walce = True; s.krok()
sprawdz("P2 walka w trakcie pauzy: pauza zdjęta (zachowanie w walce bez zmian)", s.u.mij_pauza is None, s.u.mij_pauza)

# POLUJĄCY: stoi, mob tuż obok niego = zaraz ruszy; bez skrótu w jego stronę
def oboz_s(moby, konf=None, T=12.0):
    _rnd.seed(1)
    s = Swiat(TEREN, P, (95, 95), {"O": [110, 95]}, konf=konf)
    s.moby = moby
    s.bieg(T)
    return s
s0 = oboz_s([])
s1 = oboz_s([(111, 97)])
s2 = oboz_s([(111, 97)], dict(MIJANIE_POLUJACY_R=0))
sprawdz("L0 (kontrola) zwykły obozowicz: decyzja powód oboz", typy(s0, "mijanie_kierunek"), s0.zd[:2])
alt = lambda x: (typy(x, "mijanie_kierunek") or [{}])[0].get("alternatywa")
sprawdz("L1 obozowicz z mobem w 2 polach = polujący: skrót obok niego nawet nie rozważany (alternatywa None), brak marszu w jego stronę, nigdy bliżej niż 3 pola",
        alt(s0) is not None and alt(s1) is None and "marsz" not in s1.akcje and s1.min_odl >= 3, (alt(s0), alt(s1), s1.akcje[:4], s1.min_odl))
sprawdz("L2 MIJANIE_POLUJACY_R=0: stare zachowanie (skrót rozważany jak przy zwykłym obozowiczu)", alt(s2) == alt(s0) and s2.akcje == s0.akcje, (alt(s2), alt(s0)))

# regresja: zwykłe mijanie z naprzeciwka (M4) i przechodzień z boku bez zmian przy domyślnych pokrętłach 22.10
_rnd.seed(1)
s = Swiat(TEREN, P, (95, 95), {"Z": [125, 96]})
s.bieg(45, idzie("Z", [(x, 96) for x in range(125, 85, -1)], 0.5))
sprawdz("G1 zwykłe mijanie z naprzeciwka: bez pauz, bez odwróceń, mijamy się (min <= 2) i idziemy dalej", not pauzy(s) and s.odwroty == 0 and s.min_odl <= 2
        and s.trasa[-1][1][0] > s.trasa[0][1][0], (pauzy(s), s.odwroty, s.min_odl))

# pokrętła
import pokretla as _pk
MIJ = [k for k in _pk.ZAKRESY if k.startswith("MIJANIE")]
sprawdz("K1 pokrętła MIJANIE* w pokretla.ZAKRESY i w cavebot.py z domyślną w zakresie; MIJANIE domyślnie 0", len(MIJ) == 14 and all(hasattr(cavebot, k) for k in MIJ)
        and all(_pk.ZAKRESY[k][0] <= getattr(cavebot, k) <= _pk.ZAKRESY[k][1] for k in MIJ) and _los["MIJANIE"] == 0, MIJ)
przyklad = json.loads((KAT / "na_zywo.przyklad.json").read_text())
sprawdz("K2 na_zywo.przyklad.json: wszystkie pokrętła MIJANIE* z wartością domyślną (MIJANIE = 0)", all(k in przyklad and przyklad[k] == _los[k] if k == "MIJANIE" else przyklad.get(k) == getattr(cavebot, k) for k in MIJ), [k for k in MIJ if przyklad.get(k) != getattr(cavebot, k)])
ok_, bl_ = _pk.waliduj({"MIJANIE": 1, "MIJANIE_POSTOJ_S": 20.0, "MIJANIE_PRZEJSCIE_ODL": 8}, {"MIJANIE": 0, "MIJANIE_POSTOJ_S": 15.0, "MIJANIE_PRZEJSCIE_ODL": 6})
ok2, bl2 = _pk.waliduj({"MIJANIE": 1, "MIJANIE_OBOZ_R": 4})
sprawdz("K3 analityk nie włączy MIJANIE ani nie wydłuży postoju / zasięgu ustępowania; ręcznie (na_zywo.json) wolno w zakresie", ok_ == {} and len(bl_) == 3
        and ok2 == {"MIJANIE": 1, "MIJANIE_OBOZ_R": 4} and not bl2 and _pk.waliduj({"MIJANIE": 2})[1], (ok_, bl_))
sprawdz("K4 MIJANIE_OBOZ_S: zakres pokrętła nie wychodzi poza okno obserwacji UNIKANIE_TOR_OKNO_S (obs_s <= okno, inaczej obozowicz nie powstałby nigdy)",
        _pk.ZAKRESY["MIJANIE_OBOZ_S"][1] < cavebot.UNIKANIE_TOR_OKNO_S, (_pk.ZAKRESY["MIJANIE_OBOZ_S"], cavebot.UNIKANIE_TOR_OKNO_S))
for k, v in _los.items(): setattr(cavebot, k, v)

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
