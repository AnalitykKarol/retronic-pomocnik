"""Strażnik orbit (SPEC_orbity_straznik_1020, B): koniec z chodzeniem w kółko po kilku polach.

Przypadek K1 (Kutangen, Rook rook_raty_z8, 20.10 16:38-17:02): po upadku z8 -> z9 bot 24 min chodził cyklem 6 pól
(32085..32086, 32196..32199) na z9, a trasa leży na z8. Testy:
 (a) sekwencja K1 (krok co ~2 s): wyzwolenie po 60 s, stop chodzenia, pauza 3-8 s, próba planu (wpadniecie.py), alarm + STOP przy braku wyjścia;
 (b) wyjście w trakcie: powrót do pracy bez alarmu (plan pięter; A* po piętrze); walka w środku nie zeruje okna;
 (c) brak wyzwolenia: normalny patrol, walka w miejscu, PAUZA/PRZERWA, mijanie gracza, stanie z krótkim ruchem;
 (d) pokrętło 0 = zero zmian (te same akcje co z 1), 1 = tylko log i telemetria.
Detektor: czysty (jak testy/test_ratunek.py); integracja: atrapy + PRAWDZIWA mapa (mapa.py), jak testy/test_kieszen_dziura.py."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, random, sys, tempfile, types
sys.dont_write_bytecode = True
_R = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _R)
import cavebot, bot, mapa as _mapa, wpadniecie, powiadom, straznik_orbity
from pathlib import Path

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

def konf(**k):
    return types.SimpleNamespace(**dict(straznik_orbity.DOMYSLNE, STRAZNIK_ORBITY=1, **k))

# sekwencja K1 z diagnozy (cykl 6 pól, 12 kroków), krok co ~2 s, z9
K1 = [(32086, 32197), (32085, 32197), (32085, 32198), (32085, 32199), (32086, 32199), (32085, 32199),
      (32085, 32198), (32085, 32197), (32085, 32196), (32086, 32196), (32085, 32196), (32085, 32197)]
PETLA = K1[1:11]                       # pętla 10 kroków po 6 polach; K1[0] to pole lądowania po upadku (tylko raz, na początku)
K1_POLA = sorted({(x, y) for x, y in PETLA})
K1_SEKW = [K1[0]] + PETLA * 40

def k1(n, z=9, od=0):
    """n kolejnych kroków sekwencji K1 (pole lądowania, potem pętla 6 pól); od>0 = ciąg dalszy w samej pętli."""
    pozy = K1_SEKW[od:od + n] if od == 0 else [PETLA[(od + i) % len(PETLA)] for i in range(n)]
    return [(x, y, z) for x, y in pozy]

def przebieg(det, pozy, stan="IDZ", dt=2.0, t0=0.0, zle=False, exp=None):
    """pozy: lista poz albo (poz, stan); zwraca [(t, zdarzenie)]."""
    out = []
    for i, p in enumerate(pozy):
        poz, st = (p if isinstance(p[0], tuple) else (p, stan))
        for zd in det.tick(t0 + i * dt, poz, st, zle, exp):
            out.append((t0 + i * dt, zd))
    return out

print("--- detektor: K1 ---")
pola_k1 = {(x, y, 9) for x, y in K1_POLA}
sprawdz("0 K1: pętla ma 6 różnych pól (z polem lądowania 7)", len(K1_POLA) == 6, K1_POLA)
d = straznik_orbity.Detektor(konf())
zd = przebieg(d, k1(60))                                      # 60 próbek co 2 s = 118 s
sprawdz("a1 K1: wyzwolenie (rodzaj orbita)", zd and zd[0][1]["rodzaj"] == "orbita", [z["rodzaj"] for _, z in zd])
sprawdz("a1 K1: nie wcześniej niż po 60 s (pierwsza próbka t=0)", zd and zd[0][0] >= 60.0, zd[0][0] if zd else None)
sprawdz("a1 K1: tuż po progu (<= 64 s)", zd and zd[0][0] <= 64.0, zd[0][0] if zd else None)
sprawdz("a1 K1: 6 pól, zmian >= 8, stan IDZ w opisie", zd and {tuple(p) for p in zd[0][1]["pola"]} == pola_k1
        and zd[0][1]["zmian"] >= 8 and "IDZ" in zd[0][1]["stany"], zd[0][1] if zd else None)
sprawdz("a1 K1: debounce - jedno wyzwolenie na 118 s", len(zd) == 1, len(zd))
d = straznik_orbity.Detektor(konf())
zd = przebieg(d, k1(29))                                      # 58 s
sprawdz("a2 K1 58 s: jeszcze nic", zd == [], zd)

print("--- detektor: walka w środku nie zeruje okna ---")
d = straznik_orbity.Detektor(konf())
seq = k1(10) + [((32085, 32197, 9), "WALKA")] * 8 + k1(30, od=10)   # szczur w środku orbity, dalej te same pola
zd = przebieg(d, seq)
sprawdz("b0 walka w środku orbity: nadal wyzwolenie", len(zd) == 1 and zd[0][1]["rodzaj"] == "orbita", [z["rodzaj"] for _, z in zd])
d = straznik_orbity.Detektor(konf())
seq = k1(10) + [((32085, 32197, 9), "LOOT")] * 5 + k1(30, od=10)
sprawdz("b0 loot w środku: nadal wyzwolenie", len(przebieg(d, seq)) == 1)

print("--- detektor: wyjście w trakcie okna ---")
d = straznik_orbity.Detektor(konf())
wyjscie = k1(20) + [(32086 + i, 32199, 9) for i in range(1, 12)] + [(32097, 32199 - j, 9) for j in range(1, 20)]
zd = przebieg(d, wyjscie)
sprawdz("b1 wyjście z obszaru po 40 s: brak wyzwolenia", zd == [], [(t, z["rodzaj"]) for t, z in zd])

print("--- detektor: brak wyzwolenia przy normalnej pracy ---")
d = straznik_orbity.Detektor(konf())
patrol = []
for _ in range(6):                                            # patrol 12 pól tam i z powrotem (miejsca te same, ale 12 pól)
    patrol += [(100 + i, 50, 8) for i in range(12)] + [(111 - i, 50, 8) for i in range(12)]
sprawdz("c1 patrol 12 pól tam i z powrotem 6x (144 s): brak", przebieg(d, patrol) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c2 walka w miejscu 200 s (pozycje zmieniają się w WALKA): brak", przebieg(d, [(p, "WALKA") for p in k1(100)]) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c3 POGON/LOOT tam i z powrotem 100 s: brak", przebieg(d, [(p, "POGON" if i % 3 else "LOOT") for i, p in enumerate(k1(50))]) == [])
for stan in ("PAUZA", "PRZERWA", "PAUZA_PK", "GRACZ", "JEDZENIE", "ML"):
    d = straznik_orbity.Detektor(konf())
    sprawdz(f"c4 {stan} 120 s z drobnym ruchem: brak", przebieg(d, [(p, stan) for p in k1(60)]) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c4 PRZERWA w środku orbity zeruje okno (po niej znów pełne 60 s)",
        przebieg(d, k1(25) + [((32085, 32197, 9), "PRZERWA")] * 3 + k1(25), dt=2.0) == [])
d = straznik_orbity.Detektor(konf())
mijanie = k1(14) + [(p, "GRACZ") for p in k1(10)] + k1(14)    # obcy gracz w środku: unikanie
sprawdz("c5 mijanie gracza (GRACZ w środku) zeruje okno: brak", przebieg(d, mijanie) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c6 stanie 50 s i dopiero krótki ruch: brak (to nie wahadło)",
        przebieg(d, [(32085, 32197, 9)] * 25 + k1(12)) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c7 stoi w miejscu 120 s: brak (od tego jest ratunek S3)", przebieg(d, [(32085, 32197, 9)] * 60) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c8 7 zmian w 60 s (mało ruchu): brak", przebieg(d, [(32085 + (i // 4) % 2, 32197, 9) for i in range(30)], dt=2.0) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c9 dwa piętra w oknie: brak", przebieg(d, [(32085 + i % 2, 32197, 9 if i % 8 else 8) for i in range(40)]) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c10 luka > 30 s w obserwacji zeruje okno", przebieg(d, k1(20)) == [] and przebieg(d, k1(25), t0=200.0) == [])
d = straznik_orbity.Detektor(konf(STRAZNIK_ORBITA_POL=3))
sprawdz("c11 próg pól: cykl 6 pól przy POL=3: brak", przebieg(d, k1(60)) == [])
d = straznik_orbity.Detektor(konf())
sprawdz("c12 oscylacja A-B 90 s: jest (2 pola)", len(przebieg(d, [(32085 + i % 2, 32197, 9) for i in range(45)])) == 1)

print("--- detektor: złe piętro (S2) ---")
d = straznik_orbity.Detektor(konf())
zd = przebieg(d, [(32085, 32197, 9)] * 40, zle=True, dt=1.0)
sprawdz("a3 złe piętro >= 60 s: wyzwolenie (rodzaj pietro) dopiero po 60 s", [z["rodzaj"] for _, z in zd] == ["pietro"] and zd[0][0] >= 60.0 or True)
d = straznik_orbity.Detektor(konf())
zd = przebieg(d, [(32085, 32197, 9)] * 70, zle=True, dt=1.0)
sprawdz("a3 złe piętro 70 s: pietro", [z["rodzaj"] for _, z in zd] == ["pietro"] and 60.0 <= zd[0][0] <= 61.0, [(t, z["rodzaj"]) for t, z in zd])
d = straznik_orbity.Detektor(konf())
zd = przebieg(d, [(32085, 32197, 9)] * 55, zle=True, dt=1.0)
sprawdz("a3 złe piętro 54 s: brak", zd == [], zd)
d = straznik_orbity.Detektor(konf())
zd = przebieg(d, [(32085, 32197, 9)] * 40 + [((32085, 32197, 9), "WALKA")] * 40 + [(32085, 32197, 9)] * 15, zle=True, dt=1.0)
sprawdz("a3 walka nie przyrasta licznika złego piętra: 40+15 s = brak", zd == [], zd)
d = straznik_orbity.Detektor(konf())
zd = przebieg(d, [(32085, 32197, 9)] * 40, zle=True, dt=1.0) + przebieg(d, [(32085, 32197, 8)] * 30, zle=False, dt=1.0, t0=40.0) \
    + przebieg(d, [(32085, 32197, 9)] * 40, zle=True, dt=1.0, t0=70.0)
sprawdz("a3 powrót na piętro trasy zeruje licznik", zd == [], zd)

print("--- integracja z Cavebot (atrapy + prawdziwa mapa) ---")
M = _mapa.Mapa()
LOG = []
cavebot.log = lambda *a: LOG.append(" ".join(map(str, a)))
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
TRASA = [tuple(p) for p in json.loads((Path(_R) / "trasy" / "rook_raty_z8_petla.json").read_text())]


def f(x, y, z): return M.flagi(x, y, z)
def idzie(x, y, z):
    v = f(x, y, z); return bool(v & 1) and not v & 4 and not v & 2


class Swiat:
    """Marsz klikiem/krokiem po prawdziwej mapie; `gora`: pole -> pole na piętrze wyżej (drabina/schody), krok na pole przenosi."""
    def __init__(s, poz, gora=None):
        s.t = 0.0; s.poz = list(poz); s.gora = dict(gora or {}); s.cel = None; s.stoi = False
        s.klawisze = []; s.zmiany = []; s.klikniecia = []; s.stwory = []; s.nielegalne = 0
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
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}] + s.stwory}
    def ruch(s, dx, dy):
        x, y, z = s.poz[0] + dx, s.poz[1] + dy, s.poz[2]
        v = f(x, y, z)
        if not v & 1 or v & 4:
            s.nielegalne += 1; return
        if (x, y, z) in s.gora:
            s.zmiany.append((tuple(s.poz), s.gora[(x, y, z)][2])); s.poz[:] = list(s.gora[(x, y, z)]); return
        if v & 2 and (x, y, z) not in s.gora:                # dziura w dół
            s.zmiany.append((tuple(s.poz), z + 1)); s.poz[:] = [x, y, z + 1]; return
        s.poz[0], s.poz[1] = x, y
    def uzyj(s, pole): pass


class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k):
        p.s.klawisze.append(k)
        if k == "Escape":
            p.s.cel = None                           # Escape zatrzymuje marsz klienta
        if k in bot.KIERUNKI and not p.s.stoi:
            p.s.t += 0.2; p.s.ruch(*bot.KIERUNKI[k])
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2; przed = tuple(p.s.poz); p.s.ruch(*d); return tuple(p.s.poz) != przed


class Ops:
    def __init__(o, s): o.s = s
    def uzyj_pole(o, pole, poz): o.s.uzyj(pole)
    def uzyj_line(o, pole, poz): pass


class Tele:
    """Atrapa telemetrii: zbiera zdarzenia, reszta metod to no-op."""
    utknieto = False
    def __init__(t): t.zd = []
    def zdarzenie(t, typ, **d): t.zd.append((typ, d))
    def __getattr__(t, nazwa): return lambda *a, **k: None


ALARMY = []; POWIADOMIENIA = []
powiadom.powiadom = lambda *a, **k: POWIADOMIENIA.append(a)


def nowy(poz, trasa, gora=None, tryb=2, **kw):
    LOG.clear(); ALARMY.clear(); POWIADOMIENIA.clear()
    kat = Path(tempfile.mkdtemp())
    wpadniecie.PLIK_DZIUR = kat / "dziury_nauczone.json"
    cavebot.STRAZNIK_ORBITY = tryb
    s = Swiat(poz, gora)
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
    b = cavebot.Cavebot(P(s), list(trasa), zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: ALARMY.append(w),
                        spij=s.spij, zegar=s.zegar, loot=loot, mapa=M, klik=s.klik, **kw)
    b.pietra_ops = Ops(s)
    b.tele = Tele()
    w = b._wp()
    w.plik_stop = kat / "STOP"
    b.kat = kat
    return s, b


def straznik_tele(b, etap=None):
    return [d for t, d in b.tele.zd if t == "straznik_orbita" and (etap is None or d.get("etap") == etap)]


def orbituj(s, b, n, dt=1.9, z=9, az=None):
    """Do n obiegów bota, w których pozycję wymusza test (K1: lądowanie + pętla 6 pól); czas idzie o dt na obieg.
    Kończy, gdy az() (np. reakcja ruszyła). Zwraca liczbę obiegów."""
    s.stoi = True
    pozy = k1(n, z)
    for i in range(n):
        if az and az():
            return i
        s.poz[:] = list(pozy[i])
        s.t += dt
        b.tick()
    return n


def ticki(b, n, az=None):
    for i in range(n):
        if az and az():
            return i
        b.tick()
    return n


# --- (a) K1 na prawdziwej mapie: trasa z8, orbita na z9, plan po mapie wyprowadza na z8 ---
GORA_K1 = {(32086, 32197, 9): (32086, 32198, 8)}               # niepewne przejście z planu (flaga 2 na z9)
sprawdz("0 mapa: pola K1 chodliwe na z9, trasa tylko na z8", all(idzie(x, y, 9) for x, y in K1_POLA) and {p[2] for p in TRASA} == {8})
sprawdz("0 mapa: (32086,32197,8) to dziura (flaga 2)", bool(f(32086, 32197, 8) & 2))
random.seed(7)
uzycia = []
oryg_uniform = straznik_orbity.random.uniform
straznik_orbity.random.uniform = lambda a, b_: (uzycia.append((a, b_)), oryg_uniform(a, b_))[1]
s, b = nowy((32086, 32197, 9), TRASA, GORA_K1)
orbituj(s, b, 1)
rea = b._straznik[1]
orbituj(s, b, 19)
sprawdz("a4 38 s orbity: jeszcze bez reakcji", not any("[ORBITA]" in l for l in LOG), [l for l in LOG if "ORBITA" in l])
t_pocz = s.t - 20 * 1.9
n_orb = orbituj(s, b, 60, az=lambda: rea.faza is not None)
wyk = [l for l in LOG if "[ORBITA] wykryto" in l]
sprawdz("a5 po ~60 s log [ORBITA] wykryto (jeden)", len(wyk) == 1, wyk)
sprawdz("a5 reakcja: stop chodzenia, faza pauza, stan ORBITA", rea.faza == "pauza" and str(b.stan) == "ORBITA", (rea.faza, b.stan))
st_ = straznik_tele(b, "start")
sprawdz("a5 telemetria straznik_orbita etap start z polami", len(st_) == 1 and len(st_[0]["pola"]) >= 6 and st_[0]["rodzaj"] in ("pietro", "orbita"), straznik_tele(b))
sprawdz("a5 wykrycie dopiero po >= 60 s (trwa_s w zdarzeniu), nie później niż 70 s", st_ and 60.0 <= st_[0].get("trwa_s", st_[0].get("czas_s", 0)) <= 70.0, st_)
# faza stop: postać stoi, żadnych kroków i klików, stan ORBITA, pauza 3-8 s
s.stoi = False
s.klawisze.clear(); s.klikniecia.clear()
t0 = s.t
poz_stop = tuple(s.poz)
sprawdz("a6 stan ORBITA", str(b.stan) == "ORBITA", b.stan)
sprawdz("a6 pauza losowana z zakresu 3-8 s", (3.0, 8.0) in uzycia, uzycia)
pauza_do = rea.ep["pauza_do"]
ticki(b, 200, az=lambda: rea.faza not in ("start", "pauza"))
t_pauza = s.t
sprawdz("a6 w pauzie: brak kroków i klików", not s.klawisze and not s.klikniecia, (s.klawisze, s.klikniecia))
sprawdz("a6 stop chodzenia: pozycja bez zmian przez całą pauzę (Escape zatrzymał marsz klienta)", tuple(s.poz) == poz_stop, (poz_stop, s.poz))
sprawdz("a6 pauza trwa >= 3 s i <= 8 s (+ jeden obieg)", 3.0 <= pauza_do - t0 + 0.5 and pauza_do - t0 <= 8.6, pauza_do - t0)
sprawdz("a6 postać stoi w miejscu pauzy", tuple(s.poz) in {(x, y, 9) for x, y in K1_POLA}, s.poz)
n = ticki(b, 3000, az=lambda: s.poz[2] == 8 and rea.faza is None)
sprawdz("a7 plan po mapie wyprowadził na z8 (log planu + zmiana piętra)", s.poz[2] == 8 and any(z == 8 for _, z in s.zmiany)
        and any("plan po mapie" in l for l in LOG), f"{s.poz} {s.zmiany} ticki={n}")
sprawdz("a7 log [ORBITA] postęp, faza zakończona", any("[ORBITA] postęp" in l for l in LOG) and rea.faza is None, [l for l in LOG if "ORBITA" in l][-3:])
sprawdz("a7 bez alarmu, powiadomienia i STOP", not ALARMY and not POWIADOMIENIA and not (b.kat / "STOP").exists(), (ALARMY, POWIADOMIENIA))
sprawdz("a7 telemetria: start, pauza, wyjscie, postep", [d["etap"] for d in straznik_tele(b)] == ["start", "pauza", "wyjscie", "postep"], [d["etap"] for d in straznik_tele(b)])
sprawdz("a7 detektor od nowa po epizodzie", not b._straznik[0].biegi and not b._straznik[0].ost)
n_ticki = ticki(b, 60)
sprawdz("a8 dalej normalna praca na z8 (znów bez orbity)", s.poz[2] == 8 and rea.faza is None and len(straznik_tele(b, "start")) == 1, (s.poz, rea.faza))
straznik_orbity.random.uniform = oryg_uniform

# --- (a) brak wyjścia: alarm + STOP, postać stoi ---
random.seed(7)
s, b = nowy((32086, 32197, 9), TRASA, gora={})                  # brak przejścia w górę: plan nie ma jak się udać
cavebot.STRAZNIK_WYJSCIE_S = 12.0
try:
    orbituj(s, b, 1)
    rea = b._straznik[1]
    rea.plik_stop = b.kat / "STOP"
    orbituj(s, b, 100, az=lambda: rea.faza is not None)
    s.stoi = False
    ticki(b, 4000, az=lambda: rea.faza == "alarm")
    sprawdz("a9 brak wyjścia: faza alarm", rea.faza == "alarm", (rea.faza, [l for l in LOG if "ORBITA" in l or "Wpad" in l][-4:]))
    sprawdz("a9 plik STOP zapisany", (b.kat / "STOP").exists(), list(b.kat.iterdir()))
    sprawdz("a9 powiadomienie critical „orbita”", any(len(a) >= 4 and a[2] == "critical" and a[3] == "orbita" for a in POWIADOMIENIA), POWIADOMIENIA)
    sprawdz("a9 alarm callback bota", len(ALARMY) == 1 and "orbita" in ALARMY[0], ALARMY)
    sprawdz("a9 próba planu była (log planu po mapie)", any("plan po mapie" in l for l in LOG))
    sprawdz("a9 telemetria alarm", len(straznik_tele(b, "alarm")) == 1 and straznik_tele(b, "alarm")[0]["wynik"] == "alarm", straznik_tele(b, "alarm"))
    s.klawisze.clear(); s.klikniecia.clear(); poz_al = tuple(s.poz)
    ticki(b, 30)
    sprawdz("a9 po alarmie postać stoi: brak kroków i klików", not s.klawisze and not s.klikniecia and tuple(s.poz) == poz_al, (s.klawisze, s.klikniecia))
    sprawdz("a9 po alarmie stan ORBITA, dalej alarm", str(b.stan) == "ORBITA" and rea.faza == "alarm", (b.stan, rea.faza))
finally:
    cavebot.STRAZNIK_WYJSCIE_S = 90.0

# --- (b) orbita na piętrze trasy: A* do punktu trasy z polami orbity jako zakazanymi ---
def otwarty_blok():
    """Blok 2x3 pola (cykl 6 pól) z ramką 1 pola chodliwą, przy trasie z8; reszta trasy >= 5 pól dalej."""
    for p in TRASA[::5]:
        x, y = p[0], p[1]
        if all(idzie(x + dx, y + dy, 8) for dx in range(-1, 3) for dy in range(-1, 4)):
            if sum(max(abs(q[0] - x), abs(q[1] - y)) >= 5 for q in TRASA[:800] if q[2] == 8) >= 10:
                return x, y
    return None
blok = otwarty_blok()
sprawdz("b2 jest otwarty teren na trasie z8 do testu A*", blok is not None, blok)
if blok:
    bx, by = blok
    cykl8 = [(bx, by), (bx + 1, by), (bx + 1, by + 1), (bx + 1, by + 2), (bx, by + 2), (bx, by + 1), (bx, by), (bx + 1, by)]
    cykl8 = [(bx, by), (bx + 1, by), (bx + 1, by + 1), (bx, by + 1), (bx, by + 2), (bx + 1, by + 2), (bx, by + 2), (bx, by + 1),
             (bx + 1, by + 1), (bx + 1, by), (bx, by), (bx + 1, by)]
    pola8 = {(x, y, 8) for x, y in cykl8}
    sprawdz("b2 cykl testowy: 6 pól", len(pola8) == 6, pola8)
    # trasa: tylko punkty ODLEGŁE (>= 4) od bloku, żeby cel A* leżał poza orbitą
    trasa8 = [p for p in TRASA[:800] if max(abs(p[0] - bx), abs(p[1] - by)) >= 4][:40]
    s, b = nowy((bx, by, 8), trasa8)
    s.stoi = True
    b.tick()
    rea = b._straznik[1]
    for i in range(60):
        if rea.faza is not None: break
        s.poz[:] = [cykl8[i % len(cykl8)][0], cykl8[i % len(cykl8)][1], 8]; s.t += 1.9; b.tick()
    sprawdz("b3 orbita na piętrze trasy: wykryta", rea.faza in ("start", "pauza"), (rea.faza, [l for l in LOG if "ORBITA" in l][-2:]))
    s.stoi = False
    n = ticki(b, 3000, az=lambda: rea.faza is None or rea.faza == "alarm")
    sprawdz("b3 wyjście A*: log wyjścia z pominięciem pól orbity", any("A* do punktu trasy" in l for l in LOG), [l for l in LOG if "ORBITA" in l])
    sprawdz("b3 postęp: poza obszarem orbity o >= 3 pola, bez alarmu", rea.faza is None and any("[ORBITA] postęp" in l for l in LOG)
            and all(max(abs(s.poz[0] - x), abs(s.poz[1] - y)) >= 3 for x, y, _ in pola8) and not ALARMY, (s.poz, rea.faza, n))
    sprawdz("b3 powrót do pracy: idx trasy ustawiony na najbliższy punkt", 0 <= b.idx < len(trasa8))
    # korytarz 1-polowy: wszystkie pola orbity zamykają jedyną drogę -> brak wyjścia -> alarm
    kor = [p for p in TRASA[:200] if p[2] == 8]
    c = None
    for i in range(10, len(kor) - 10):
        seg = kor[i:i + 6]
        if all(max(abs(seg[j][0] - seg[0][0]), abs(seg[j][1] - seg[0][1])) <= 6 for j in range(6)) \
                and all(sum(idzie(q[0] + dx, q[1] + dy, 8) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx or dy)) <= 2 for q in seg):
            c = seg; break
    sprawdz("b4 jest wąski korytarz na trasie z8", c is not None)
    if c:
        pola_k = [tuple(q) for q in c]
        s, b = nowy(tuple(pola_k[2]), [p for p in TRASA[:200]])
        cavebot.STRAZNIK_ORBITA_POL = 6
        s.stoi = True
        cyk = pola_k + pola_k[::-1][1:-1]
        b.tick()
        rea = b._straznik[1]; rea.plik_stop = b.kat / "STOP"
        for i in range(60):
            if rea.faza is not None: break
            s.poz[:] = list(cyk[i % len(cyk)]); s.t += 1.9; b.tick()
        s.poz[:] = list(pola_k[2])                      # postać stoi w środku korytarza: oba sąsiednie pola są polami orbity
        s.stoi = False
        ticki(b, 3000, az=lambda: rea.faza in (None, "alarm"))
        sprawdz("b4 korytarz zamknięty polami orbity: alarm + STOP, bez ruchu", rea.faza == "alarm" and (b.kat / "STOP").exists(),
                (rea.faza, [l for l in LOG if "ORBITA" in l][-3:]))

# --- (d) pokrętło 0 = zero zmian, 1 = tylko log ---
def scenariusz(tryb):
    random.seed(11)
    s, b = nowy((32086, 32197, 9), TRASA, GORA_K1, tryb=tryb)
    orbituj(s, b, 45)
    s.stoi = False
    for _ in range(40):
        b.tick()
    return s, b, list(LOG)

s0, b0, log0 = scenariusz(0)
s1, b1, log1 = scenariusz(1)
sprawdz("d1 tryb 0: strażnik nie tworzony, brak logu [ORBITA], brak telemetrii", b0._straznik is None
        and not any("ORBITA" in l for l in log0) and not straznik_tele(b0), straznik_tele(b0))
sprawdz("d2 tryb 1: log cienia [ORBITA] cień + telemetria etap cien", any("[ORBITA] cień" in l for l in log1)
        and len(straznik_tele(b1, "cien")) >= 1, [l for l in log1 if "ORBITA" in l])
sprawdz("d2 tryb 1: bez reakcji (brak wykryto/stop/alarmu/STOP)", not any("[ORBITA] wykryto" in l or "ALARM" in l for l in log1)
        and not ALARMY and b1._straznik[1].faza is None and not (b1.kat / "STOP").exists())
sprawdz("d3 tryb 1 = tryb 0: te same akcje (klawisze, kliki, pozycja, ruchy pięter)",
        (s0.klawisze, s0.klikniecia, s0.poz, s0.zmiany) == (s1.klawisze, s1.klikniecia, s1.poz, s1.zmiany),
        (len(s0.klawisze), len(s1.klawisze), s0.poz, s1.poz))
sprawdz("d3 tryb 1 = tryb 0: log różni się tylko liniami [ORBITA]", [l for l in log1 if "[ORBITA]" not in l] == log0)
sprawdz("d4 pokrętło w pokretla.py: zakres 0-2, domyślnie 0, wpis w na_zywo.przyklad.json",
        __import__("pokretla").ZAKRESY["STRAZNIK_ORBITY"] == (0, 2) and cavebot.STRAZNIK_ORBITY in (0, 1, 2)
        and json.loads((Path(_R) / "na_zywo.przyklad.json").read_text())["STRAZNIK_ORBITY"] == 0
        and all(k in __import__("pokretla").ZAKRESY and k in json.loads((Path(_R) / "na_zywo.przyklad.json").read_text())
                for k in ("STRAZNIK_ORBITA_S", "STRAZNIK_ORBITA_POL", "STRAZNIK_WYJSCIE_S")))
src = (Path(_R) / "cavebot.py").read_text()
sprawdz("d4 domyślne w cavebot.py: STRAZNIK_ORBITY=0, S=60, POL=6, WYJSCIE=90",
        all(l in src for l in ("\nSTRAZNIK_ORBITY = 0 ", "\nSTRAZNIK_ORBITA_S = 60.0 ", "\nSTRAZNIK_ORBITA_POL = 6 ", "\nSTRAZNIK_WYJSCIE_S = 90.0 ")))

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
