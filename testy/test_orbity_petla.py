"""Strażnik orbit, PĘTLA (24.10, Wydra 12:43-12:49): bot nie powtarza w kółko tych samych czynności i nie tkwi w kieszeni.

Przypadek: Wydra 24.10, Troll zabity 12:43:03, potem 6 min 26 s w kieszeni 4x4 pola (32501..32503, 32273) na z8, 0 zabić, stan IDZ,
okno orbit (STRAZNIK_ORBITY=1/2 bez pętli) nic nie widzi (40 zmian pozycji w 330 s, stanie > połowy okna).
Testy (offline, `python3 -I testy/test_orbity_petla.py`):
 (a) detektor na prawdziwych próbkach telemetrii (testy/dane/wydra_petla_20261024.json): zdarzenie `petla` w <= 63 s od wejścia w kieszeń;
 (b) sygnały: cykl > 3 powtórzeń, ramka 45 s; postęp (exp, piętro) zeruje; progi z pokręteł;
 (c) brak fałszywych alarmów: spawn z zabiciami, walka, stany zamierzone, patrol po długiej trasie, WYPAD, pokrętło 0 = zero zmian;
 (d) integracja z Cavebot (atrapy + prawdziwa mapa, kieszeń Wydry): cień (ORBITY=1), działanie (ORBITY=2: klik poza kieszeń, potem
     inny plan), brak STOP/alarmu/powiadomienia, stanowisko `stoj` nie reaguje, drugi epizod zaczyna od innego sposobu naprawy."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, random, sys, tempfile, types
sys.dont_write_bytecode = True
_R = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _R)
import stoj, cavebot, bot, mapa as _mapa, wpadniecie, powiadom, straznik_orbity
from pathlib import Path

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

def konf(**k):
    return types.SimpleNamespace(**{**straznik_orbity.DOMYSLNE, "STRAZNIK_ORBITY": 1, "STRAZNIK_PETLA": 1, **k})

def przebieg(det, pozy, stan="IDZ", dt=1.0, t0=0.0, exp=None):
    """pozy: lista poz albo (poz, stan); exp: stały albo funkcja (i) -> exp; zwraca [(t, zdarzenie)]."""
    out = []
    for i, p in enumerate(pozy):
        poz, st = (p if isinstance(p[0], tuple) else (p, stan))
        e = exp(i) if callable(exp) else exp
        for zd in det.tick(t0 + i * dt, poz, st, False, e):
            out.append((t0 + i * dt, zd))
    return out

def sygn(zdarzenia):
    return [(round(t), z["rodzaj"], z.get("sygnal")) for t, z in zdarzenia if z["rodzaj"] == "petla"]

A, B, C = (100, 50, 8), (101, 50, 8), (102, 50, 8)

print("--- (a) Wydra 24.10 12:43 na prawdziwych próbkach ---")
dane = json.loads((Path(_R) / "testy" / "dane" / "wydra_petla_20261024.json").read_text())["wiersze"]
def t_hms(h, m, s):
    import datetime
    d0 = datetime.datetime.fromtimestamp(dane[0][0])
    return d0.replace(hour=h, minute=m, second=s, microsecond=0).timestamp()
def replay(det):
    out = []
    for t, stan, x, y, z, exp in dane:
        for zd in det.tick(t, (x, y, z), stan, False, exp):
            out.append((t, zd))
    return out
wyn = replay(straznik_orbity.Detektor(konf()))
pet = [(t, z) for t, z in wyn if z["rodzaj"] == "petla"]
t_wejscia = t_hms(12, 43, 12)
sprawdz("a1 Wydra: jest zdarzenie petla (ramka)", pet and pet[0][1]["sygnal"] == "ramka", [(t, z["rodzaj"]) for t, z in wyn])
sprawdz("a2 Wydra: wykrycie w <= 63 s od wejścia w kieszeń (12:43:12)", pet and pet[0][0] - t_wejscia <= 63.0, pet[0][0] - t_wejscia if pet else None)
sprawdz("a3 Wydra: nie przed 45 s (okno)", pet and pet[0][0] - t_wejscia >= 45.0, pet[0][0] - t_wejscia if pet else None)
sprawdz("a4 Wydra: pola zdarzenia leżą w kieszeni, 0 przyrostu exp, ramka <= 4x4",
        pet and all(32497 <= p[0] <= 32503 and 32270 <= p[1] <= 32273 for p in pet[0][1]["pola"]) and pet[0][1]["exp_przyrost"] == 0
        and max(pet[0][1]["ramka"]) <= 4, pet[0][1] if pet else None)
sprawdz("a5 Wydra: przed 12:43:12 (walka, loot, zabicia) brak zdarzeń petla", all(t >= t_wejscia for t, _ in pet))
sprawdz("a6 Wydra: stara orbita (bez pętli) tu nic nie widzi (powód, że pętla jest potrzebna)",
        not [1 for t, z in wyn if z["rodzaj"] == "orbita" and t_hms(12, 43, 0) <= t <= t_hms(12, 49, 30)], [z["rodzaj"] for t, z in wyn])
wyn0 = replay(straznik_orbity.Detektor(konf(STRAZNIK_PETLA=0)))
sprawdz("a7 STRAZNIK_PETLA=0: zero zdarzeń petla, a pozostałe (orbita/pietro) te same co z pętlą",
        not [1 for t, z in wyn0 if z["rodzaj"] == "petla"]
        and [(t, z["rodzaj"]) for t, z in wyn0] == [(t, z["rodzaj"]) for t, z in wyn if z["rodzaj"] != "petla"])
d0 = straznik_orbity.Detektor(konf(STRAZNIK_PETLA=0)); replay(d0)
sprawdz("a8 STRAZNIK_PETLA=0: okna pętli puste (zero kosztu)", not d0.pw and not d0.cykl)
sprawdz("a9 wartości domyślne: STRAZNIK_PETLA=0 (ORBITY=1 bez pętli nic nie zmienia)", straznik_orbity.DOMYSLNE["STRAZNIK_PETLA"] == 0
        and cavebot.STRAZNIK_PETLA == 0)

print("--- (b) sygnał cykl: ta sama sekwencja > 3 razy ---")
AB = [A, B]
d = straznik_orbity.Detektor(konf())
sprawdz("b1 A-B x4 co 3 s (24 s): petla cykl", sygn(przebieg(d, AB * 4, dt=3.0)) == [(21, "petla", "cykl")], sygn(przebieg(straznik_orbity.Detektor(konf()), AB * 4, dt=3.0)))
d = straznik_orbity.Detektor(konf())
sprawdz("b2 A-B x3 (tylko 3 powtórzenia, wolno): brak", sygn(przebieg(d, AB * 3, dt=3.0)) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("b3 A-B x4 w 4 s (mrugnięcie, < CYKL_S): brak", sygn(przebieg(d, AB * 4, dt=0.5)) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("b4 A-B-C-B x4 (okres 4): petla cykl", [s for s in sygn(przebieg(d, [A, B, C, B] * 4, dt=3.0)) if s[2] == "cykl"] != [])
d = straznik_orbity.Detektor(konf())
sprawdz("b5 cykl przerwany zabiciem (exp rośnie w środku): brak", sygn(przebieg(d, AB * 6, dt=3.0, exp=lambda i: 1000 + (20 if i >= 7 else 0))) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("b6 cykl przerwany zmianą piętra w środku: brak",
        sygn(przebieg(d, AB * 2 + [((100, 50, 9), "IDZ"), ((101, 50, 9), "IDZ")] + [((100, 50, 9), "IDZ"), ((101, 50, 9), "IDZ")], dt=3.0)) == [])
d = straznik_orbity.Detektor(konf(STRAZNIK_PETLA_POWTORZ=5))
sprawdz("b7 próg powtórzeń z pokrętła (POWTORZ=5): 4 powtórzenia brak, 6 jest",
        sygn(przebieg(d, AB * 4, dt=3.0)) == [] and bool(sygn(przebieg(straznik_orbity.Detektor(konf(STRAZNIK_PETLA_POWTORZ=5)), AB * 6, dt=3.0))))
d = straznik_orbity.Detektor(konf())
sprawdz("b8 debounce: jedno zdarzenie na 5 min w tym samym miejscu", len(sygn(przebieg(d, AB * 40, dt=3.0))) == 1)
d = straznik_orbity.Detektor(konf())
sprawdz("b9 pole obce w cyklu (A-B-A-C-A-B-A-C... okres 4 z różnymi): jest", bool(sygn(przebieg(d, [A, B, A, C] * 5, dt=3.0))))

print("--- (b) sygnał ramka: 45 s w ramce 4x4 bez postępu ---")
d = straznik_orbity.Detektor(konf())
z = sygn(przebieg(d, [A] * 60))
sprawdz("b10 stanie w IDZ: zdarzenie dopiero po 45 s", z and 45 <= z[0][0] <= 47 and z[0][2] == "ramka", z)
d = straznik_orbity.Detektor(konf())
sprawdz("b11 stanie 44 s: brak", sygn(przebieg(d, [A] * 45)) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("b12 ramka 4x4 (16 pól, losowo po 3 s): jest", bool(sygn(przebieg(d, [(100 + (i * 7) % 4, 50 + (i * 5) % 4, 8) for i in range(40)], dt=3.0))))
_r5 = random.Random(5)
_los5 = [(100 + _r5.randrange(5), 50 + _r5.randrange(5), 8) for _ in range(60)]
d = straznik_orbity.Detektor(konf())
sprawdz("b13 ramka 5x5 (za duża): brak", sygn(przebieg(d, _los5, dt=2.0)) == [])
d = straznik_orbity.Detektor(konf(STRAZNIK_PETLA_RAMKA=5))
sprawdz("b14 ramka 5x5 z pokrętła RAMKA=5: jest", bool(sygn(przebieg(d, _los5, dt=2.0))))
d = straznik_orbity.Detektor(konf())
sprawdz("b15 zabicie (exp +20) po 40 s zeruje okno: 40 s + 10 s po zabiciu = brak; dopiero 45 s po zabiciu jest",
        sygn(przebieg(d, [A] * 50, exp=lambda i: 1000 + (20 if i >= 40 else 0))) == []
        and bool(sygn(przebieg(straznik_orbity.Detektor(konf()), [A] * 90, exp=lambda i: 1000 + (20 if i >= 40 else 0)))))
d = straznik_orbity.Detektor(konf())
sprawdz("b16 zmiana piętra zeruje okno (30 s z8, 30 s z9 w tych samych x,y): brak",
        sygn(przebieg(d, [((100, 50, 8), "IDZ")] * 30 + [((100, 50, 9), "IDZ")] * 30)) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("b17 wyjście z ramki w trakcie okna (40 s w kieszeni, potem marsz): brak",
        sygn(przebieg(d, [A] * 40 + [(100 + i, 50, 8) for i in range(1, 20)])) == [])
d = straznik_orbity.Detektor(konf(STRAZNIK_PETLA_S=20.0))
z = sygn(przebieg(d, [A] * 30))
sprawdz("b18 okno z pokrętła (PETLA_S=20): wykrycie po 20 s", z and 20 <= z[0][0] <= 22, z)
d = straznik_orbity.Detektor(konf())
zd = przebieg(d, [A] * 60)
sprawdz("b19 pola zdarzenia i opis czytelne dla Reakcji", zd and zd[0][1]["pola"] == [list(A)] and "ramce" in straznik_orbity.Reakcja._opis(zd[0][1]), zd[0][1] if zd else None)

print("--- (c) brak fałszywych alarmów ---")
d = straznik_orbity.Detektor(konf())
sprawdz("c1 spawn: stoi w ramce 3x3, zabicie co 20 s (exp rośnie) 5 min: brak",
        sygn(przebieg(d, [(100 + (i // 3) % 3, 50 + (i // 5) % 3, 8) for i in range(300)], exp=lambda i: 1000 + 20 * (i // 20))) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c2 walka w miejscu 300 s (WALKA, exp stoi): brak", sygn(przebieg(d, [(A, "WALKA")] * 300)) == [])
d = straznik_orbity.Detektor(konf())
mix = ([(A, "IDZ")] * 6 + [(A, "WALKA")] * 4) * 20          # 40% walki: za dużo na pętlę (pościg/dobijanie bez exp)
sprawdz("c3 40% walki w ramce (udział > 30%): brak", sygn(przebieg(d, mix)) == [])
d = straznik_orbity.Detektor(konf())
mix = ([(A, "IDZ")] * 9 + [(A, "LOOT")]) * 8               # 10% lootu, brak exp: to już jest pętla
sprawdz("c4 10% lootu bez zabicia (udział < 30%): jest (zwłoki bez exp nie zasłaniają pętli)", bool(sygn(przebieg(d, mix))))
for stan in ("PAUZA", "PRZERWA", "PAUZA_PK", "GRACZ", "JEDZENIE", "ML", "WYPAD", "PET", "STOJ_POWROT", "POCHODNIA", "WPADNIECIE", "ORBITA"):
    d = straznik_orbity.Detektor(konf())
    sprawdz(f"c5 {stan} 300 s w miejscu: brak", sygn(przebieg(d, [(A, stan)] * 300)) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c6 stan zamierzony w środku zeruje okno (40 s IDZ, 5 s PAUZA, 40 s IDZ): brak",
        sygn(przebieg(d, [(A, "IDZ")] * 40 + [(A, "PAUZA")] * 5 + [(A, "IDZ")] * 40)) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c7 inny stan w środku (WYPAD 3 s) zeruje okno pętli: brak", sygn(przebieg(d, [(A, "IDZ")] * 40 + [(A, "WYPAD")] * 3 + [(A, "IDZ")] * 40)) == [])
d = straznik_orbity.Detektor(konf())
patrol = []
for _ in range(8):                                          # patrol 20 pól tam i z powrotem (okres 38, ramka 20)
    patrol += [(100 + i, 50, 8) for i in range(20)] + [(119 - i, 50, 8) for i in range(20)]
sprawdz("c8 patrol 20 pól tam i z powrotem 8x (320 s): brak", sygn(przebieg(d, patrol, dt=0.5)) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c9 marsz prosty 200 pól: brak", sygn(przebieg(d, [(100 + i, 50, 8) for i in range(200)], dt=0.4)) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c10 luka > 30 s w obserwacji zeruje okno", sygn(przebieg(d, [A] * 30)) == [] and sygn(przebieg(d, [A] * 30, t0=200.0)) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c11 inne piętra w oknie (A na z8, potem to samo xy na z9 po 30 s): brak", sygn(przebieg(d, [((100, 50, 8 + (i // 30)), "IDZ") for i in range(90)])) == [])
d = straznik_orbity.Detektor(konf(STRAZNIK_PETLA=0))
sprawdz("c12 STRAZNIK_PETLA=0: stanie 300 s i A-B x20 nie dają nic", sygn(przebieg(d, [A] * 300)) == [] and sygn(przebieg(d, AB * 20, dt=3.0, t0=1000.0)) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c13 orbita (stary sygnał) nadal działa obok pętli: oscylacja co 3,9 s daje orbitę (i/lub cykl)",
        [z["rodzaj"] for t, z in przebieg(d, [(100 + i % 2, 50, 8) for i in range(40)], dt=3.9)][:1] in (["orbita"], ["petla"]))

print("--- (d) integracja z Cavebot (atrapy + prawdziwa mapa, kieszeń Wydry) ---")
M = _mapa.Mapa()
LOG = []
cavebot.log = lambda *a: LOG.append(" ".join(map(str, a)))
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
TRASA = [(32478, 32290, 8), (32491, 32294, 8), (32500, 32270, 8), (32493, 32259, 8)]
KIESZEN = (32501, 32273, 8)
KIESZEN_POLA = {(32501, 32273, 8), (32502, 32273, 8), (32503, 32273, 8)}


def f(x, y, z): return M.flagi(x, y, z)
def idzie(x, y, z):
    v = f(x, y, z); return bool(v & 1) and not v & 4 and not v & 2


class Swiat:
    """Marsz klikiem/krokiem po prawdziwej mapie (jak w test_straznik_orbity.py)."""
    def __init__(s, poz):
        s.t = 0.0; s.poz = list(poz); s.cel = None; s.stoi = False
        s.klawisze = []; s.klikniecia = []; s.stwory = []; s.nielegalne = 0
    def zegar(s): return s.t
    def klik(s, dx, dy): s.cel = (s.poz[0] + dx, s.poz[1] + dy, s.poz[2]); s.klikniecia.append((dx, dy))
    def spij(s, d):
        s.t += d
        c = s.cel
        if s.stoi or c is None or d < 0.08 or tuple(s.poz) == c:
            return
        start = tuple(s.poz); skad = {start: None}; q = [start]
        for a in q:
            if a == c or len(skad) > 4000: break
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (a[0] + dx, a[1] + dy, a[2])
                    if (dx or dy) and n not in skad and idzie(*n):
                        skad[n] = a; q.append(n)
        if c not in skad:
            s.cel = None; return
        sciezka = []; a = c
        while a != start: sciezka.append(a); a = skad[a]
        for n in sciezka[::-1][:max(1, int(d / 0.2))]:
            z0 = s.poz[2]
            s.ruch(n[0] - s.poz[0], n[1] - s.poz[1])
            if s.poz[2] != z0:
                s.cel = None
                break
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0, "exp": 1000}}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}] + s.stwory}
    def ruch(s, dx, dy):
        x, y, z = s.poz[0] + dx, s.poz[1] + dy, s.poz[2]
        v = f(x, y, z)
        if not v & 1 or v & 4:
            s.nielegalne += 1; return
        if v & 2:
            s.nielegalne += 1; return                       # w tych testach nigdy nie wchodzimy w dziury/schody
        s.poz[0], s.poz[1] = x, y
    def uzyj(s, pole): pass


class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k):
        p.s.klawisze.append(k)
        if k == "Escape":
            p.s.cel = None
        if k in bot.KIERUNKI and not p.s.stoi:
            p.s.t += 0.2; p.s.ruch(*bot.KIERUNKI[k])
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2; przed = tuple(p.s.poz)
        if not p.s.stoi: p.s.ruch(*d)
        return tuple(p.s.poz) != przed


class Ops:
    def __init__(o, s): o.s = s
    def uzyj_pole(o, pole, poz): o.s.uzyj(pole)
    def uzyj_line(o, pole, poz): pass


class Tele:
    utknieto = False
    def __init__(t): t.zd = []
    def zdarzenie(t, typ, **d): t.zd.append((typ, d))
    def __getattr__(t, nazwa): return lambda *a, **k: None


ALARMY = []; POWIADOMIENIA = []
powiadom.powiadom = lambda *a, **k: POWIADOMIENIA.append(a)


def nowy(poz, trasa=TRASA, tryb=2, petla=1, **kw):
    LOG.clear(); ALARMY.clear(); POWIADOMIENIA.clear()
    kat = Path(tempfile.mkdtemp())
    wpadniecie.PLIK_DZIUR = kat / "dziury_nauczone.json"
    cavebot.STRAZNIK_ORBITY = tryb
    cavebot.STRAZNIK_PETLA = petla
    s = Swiat(poz)
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
    b = cavebot.Cavebot(P(s), list(trasa), zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: ALARMY.append(w),
                        spij=s.spij, zegar=s.zegar, loot=loot, mapa=M, klik=s.klik, **kw)
    b.pietra_ops = Ops(s)
    b.tele = Tele()
    w = b._wp()
    w.plik_stop = kat / "STOP"
    b.kat = kat
    b.stoj_katalog = str(kat)                       # nigdy katalog prawdziwej instancji
    return s, b


def straznik_tele(b, etap=None):
    return [d for t, d in b.tele.zd if t == "straznik_orbita" and (etap is None or d.get("etap") == etap)]


def ticki(b, n, az=None):
    for i in range(n):
        if az and az():
            return i
        b.tick()
    return n


sprawdz("d0 mapa: kieszeń Wydry chodliwa, wyjście po skosie (32500,32272) i przez (32503,32272)", idzie(*KIESZEN) and idzie(32500, 32272, 8)
        and idzie(32503, 32272, 8))

# d1: ORBITY=1 (cień): wykrycie w logu i telemetrii, ZERO akcji strażnika
random.seed(11)
s, b = nowy(KIESZEN, tryb=1)
s.stoi = True
n = ticki(b, 4000, az=lambda: any("[ORBITA] cień" in l for l in LOG))
sprawdz("d1 cień: log [ORBITA] cień: petla po ~45-60 s", any("[ORBITA] cień: petla" in l for l in LOG) and 44.0 <= s.t <= 75.0, (s.t, [l for l in LOG if "ORBITA" in l]))
sprawdz("d1 cień: telemetria straznik_orbita etap cien z rodzajem petla", [d.get("rodzaj") for d in straznik_tele(b, "cien")] == ["petla"], straznik_tele(b))
s.stoi = False
ticki(b, 400)
sprawdz("d1 cień: strażnik niczego nie robi (bez [ORBITA] wykryto, bez stanu ORBITA, bez alarmu)",
        not any("[ORBITA] wykryto" in l for l in LOG) and str(b.stan) != "ORBITA" and not ALARMY and not POWIADOMIENIA)

# d2: ORBITY=2: wykrycie, stop chodzenia, naprawa wyprowadza z kieszeni, powrót do pracy
random.seed(11)
s, b = nowy(KIESZEN, tryb=2)
s.stoi = True
rea = None
ticki(b, 4000, az=lambda: b._straznik is not None and b._straznik[1].faza is not None)
rea = b._straznik[1]
t_wykr = s.t
sprawdz("d2 działa: [ORBITA] wykryto petla po 45-70 s stania", any("[ORBITA] wykryto petla" in l for l in LOG) and 44.0 <= t_wykr <= 75.0, (t_wykr, [l for l in LOG if "ORBITA" in l]))
sprawdz("d2 działa: faza start/pauza, stan ORBITA, telemetria start z rodzajem petla",
        rea.faza in ("start", "pauza") and [d.get("rodzaj") for d in straznik_tele(b, "start")] == ["petla"], (rea.faza, straznik_tele(b)))
sprawdz("d2 działa: wykrycie nie jest orbitą (zdarzenie petla, ramka)", rea.ep["zd"]["rodzaj"] == "petla" and rea.ep["petla"] and rea.ep["zd"]["sygnal"] == "ramka")
s.stoi = False
ticki(b, 6000, az=lambda: rea.faza is None)
sprawdz("d2 działa: wyszedł z kieszeni (>= 3 pola od pól pętli), faza zakończona", rea.faza is None
        and all(max(abs(s.poz[0] - q[0]), abs(s.poz[1] - q[1])) >= 3 for q in KIESZEN_POLA), (s.poz, rea.faza))
sprawdz("d2 działa: log [ORBITA] postęp", any("[ORBITA] postęp" in l for l in LOG), [l for l in LOG if "ORBITA" in l][-4:])
sprawdz("d2 działa: BEZ alarmu, powiadomienia i pliku STOP (naprawa, nigdy stop)", not ALARMY and not POWIADOMIENIA and not (b.kat / "STOP").exists(), (ALARMY, POWIADOMIENIA))
sprawdz("d2 działa: pierwszy sposób epizodu pętli to klik (inne miejsce), nie ponowienie planu", rea.historia and rea.historia[0][0] == "klik", rea.historia)
sprawdz("d2 działa: żaden krok postaci nie wszedł w ścianę/dziurę", s.nielegalne == 0, s.nielegalne)
sprawdz("d2 działa: detektor od nowa po epizodzie (okna pętli puste)", not b._straznik[0].pw and not b._straznik[0].cykl and not b._straznik[0].ost)
pierwsze = list(rea.historia); nr1 = len(straznik_tele(b, "start"))

# d3: drugi epizod w ciągu 30 min zaczyna od innego sposobu (zakaz powtórzenia tej samej naprawy)
random.seed(11)
s.poz[:] = list(KIESZEN); s.stoi = True; s.cel = None
ticki(b, 6000, az=lambda: rea.faza is not None)
sprawdz("d3 drugi epizod pętli wykryty", rea.faza is not None and len(straznik_tele(b, "start")) == nr1 + 1, (rea.faza, len(straznik_tele(b, "start")), nr1))
s.stoi = False
ticki(b, 6000, az=lambda: rea.faza is None or (rea.ep and rea.ep["n_met"] >= 1 and rea.historia))
sprawdz("d3 drugi epizod: pierwszy sposób inny niż w pierwszym (punkt zamiast klik)", rea.historia and rea.historia[0][0] == "punkt" and pierwsze[0][0] == "klik",
        (pierwsze[:2], rea.historia[:2]))
ticki(b, 6000, az=lambda: rea.faza is None)
sprawdz("d3 drugi epizod zakończony bez alarmu i STOP", rea.faza is None and not ALARMY and not (b.kat / "STOP").exists(), (rea.faza, ALARMY))

# d4: pokrętło PETLA=0 przy ORBITY=2: stanie w kieszeni 150 s nic nie uruchamia
s, b = nowy(KIESZEN, tryb=2, petla=0)
s.stoi = True
ticki(b, 600)
sprawdz("d4 PETLA=0, ORBITY=2: 150+ s stania w kieszeni bez reakcji", s.t > 100 and not any("ORBITA" in l for l in LOG) and b._straznik is not None
        and b._straznik[1].faza is None, (s.t, [l for l in LOG if "ORBITA" in l]))
# d5: ORBITY=0: strażnik w ogóle nie powstaje
s, b = nowy(KIESZEN, tryb=0, petla=1)
s.stoi = True
ticki(b, 600)
sprawdz("d5 ORBITY=0 (domyślnie), PETLA=1: strażnik nie powstaje, zero zmian", b._straznik is None and not any("ORBITA" in l for l in LOG))
# d6: stanowisko `stoj` (stacja run): detektory wyłączone
s, b = nowy(KIESZEN, tryb=2, petla=1)
stoj.wlacz(b.stoj_katalog)
s.stoi = True
ticki(b, 800)
sprawdz("d6 stanowisko stoj: 150+ s w miejscu, bez reakcji i bez wykrycia", s.t > 100 and not any("ORBITA" in l for l in LOG) and (b._straznik is None or b._straznik[1].faza is None),
        (s.t, [l for l in LOG if "ORBITA" in l]))
# d7: walka w miejscu: stwór obok, bot walczy (stan WALKA), nie ma pętli
s, b = nowy((32500, 32271, 8), tryb=2, petla=1)
s.stoi = True
s.stwory = [{"id": 7, "nazwa": "Troll", "gracz": False, "x": 32500, "y": 32270, "z": 8, "hp": 80}]
ticki(b, 1000)
sprawdz("d7 walka w miejscu: strażnik nie wykrywa pętli", not any("[ORBITA] wykryto" in l for l in LOG), [l for l in LOG if "ORBITA" in l])

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
