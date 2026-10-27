"""Trasa powrotna jaskinia trolli (Thais) -> Gorn, troll_do_miasta (25.10, Wydra: okrężna droga, 3 zbędne zejścia w dziury, ok. 43 pkt kręcenia po z9).
Offline: prawdziwa mapa serwera + prawdziwy Wypad/Cavebot w symulatorze świata (jak test_wyprawa_dojscie). Nic nie trafia do gry.

  python3 -I testy/test_troll_powrot.py                      plan = trasy/troll_do_miasta_v2.json, a gdy go nie ma (po wdrożeniu) troll_do_miasta.json
  python3 -I testy/test_troll_powrot.py troll_do_miasta.json  wskazany plik z trasy/ (dawna trasa = CZERWONA)

Wymagania (z zadania Karola): z KAŻDEGO pola jaskini (z8 i z9, także kieszenie z9 i część wschodnia) wypad dochodzi do wyjścia na z7 i do Gorna,
droga krótsza niż odwrócone nagranie, najwyżej JEDNO zejście w dziurę z8 -> z9 (dziura (32478,32269): z8 pod jaskinią jest rozcięte, innej drogi
na północ nie ma), bez wejścia w pole nieprzechodnie, końcówka (wyjście liną na z7 i droga do Gorna) bez zmian."""
import json, sys, types, random, os
sys.dont_write_bytecode = True
_R = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _R)
import cavebot, bot, mapa as _mapa, pietra, wypad
from pathlib import Path

TRASY = Path(_R) / "trasy"
LOG = []
cavebot.log = lambda *a: LOG.append(" ".join(map(str, a)))
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False
cavebot.PATROL_POSTOJ = (0.2, 0.4)
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

M = _mapa.Mapa()
DRZWI = (32505, 32270, 8)        # pole łącznika: w mapie ściana, w symulatorze przechodnie (jak w grze, do potwierdzenia)
_MI = json.loads((TRASY / "miejsca_troll.json").read_text())
# pola lądowania po zejściu (T.x, T.y, z+1) mają w mapie flagę 2 (dziura), w grze to zwykłe pole: symulator ich nie spuszcza niżej
LADOWANIA = {(p["pole"][0], p["pole"][1], p["pole"][2] + 1) for p in _MI["przejscia"]}
def f(x, y, z):
    v = M.flagi(x, y, z)
    if (x, y, z) in LADOWANIA:
        return v & ~2
    return (v | 1) & ~4 if (x, y, z) == DRZWI else v
def idzie(x, y, z):
    v = f(x, y, z); return bool(v & 1) and not v & 4 and not v & 2


class Swiat:
    """gora: 'use' (drabina: Ctrl+klik na R), 'krok' (schody: krok na R), 'nigdy' (przejście nie działa)."""
    def __init__(s, poz, gora="use", dol="krok"):
        s.t = 0.0; s.poz = list(poz); s.gora = gora; s.dol = dol
        s.zmiany = []; s.uzycia = []; s.nielegalne = 0; s.odwiedzone = set()
    def zegar(s): return s.t
    def klik(s, dx, dy):                                   # klient: klik w pole = marsz po najkrótszej drodze (8 kierunków)
        s.cel = (s.poz[0] + dx, s.poz[1] + dy, s.poz[2])
    def spij(s, d):
        s.t += d
        c = getattr(s, "cel", None)
        if c is None or d < 0.08 or tuple(s.poz) == c:
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
            return {"gracz": {"hp": 195, "max_hp": 195, "mana": 95, "max_mana": 95}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in getattr(s, "inni", [])]}
    def ruch(s, dx, dy):
        x, y, z = s.poz[0] + dx, s.poz[1] + dy, s.poz[2]
        v = f(x, y, z)
        if not v & 1 or v & 4:
            s.nielegalne += 1; return
        if v & 2:                                           # dziura/schody w dół
            if s.dol == "nigdy":
                return
            s.zmiany.append((tuple(s.poz), z + 1)); s.poz[:] = [x, y, z + 1]; s.odwiedzone.add(tuple(s.poz)); return
        g = f(x, y, z - 1) if z else 0
        if s.gora == "krok" and g & 1 and g & 2 and idzie(x, y, z):    # schody w górę: sam krok na R
            s.zmiany.append((tuple(s.poz), z - 1)); s.poz[:] = [x, y + 1, z - 1]; s.odwiedzone.add(tuple(s.poz)); return
        s.poz[0], s.poz[1] = x, y; s.odwiedzone.add(tuple(s.poz))
    def uzyj(s, pole):
        s.uzycia.append(tuple(pole))
        x, y, z = pole
        if s.gora == "use" and z and f(x, y, z - 1) & 2 and f(x, y, z - 1) & 1 and idzie(x, y, z):
            s.zmiany.append((tuple(s.poz), z - 1)); s.poz[:] = [x, y + 1, z - 1]; s.odwiedzone.add(tuple(s.poz))
class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): pass
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2; przed = tuple(p.s.poz); p.s.ruch(*d); return tuple(p.s.poz) != przed
class Ops:
    def __init__(o, s): o.s = s
    def uzyj_pole(o, pole, poz): o.s.uzyj(pole)
    def uzyj_line(o, pole, poz): pass
class Gracz: pass

# bez haków na żywo (telemetria do logi/, pokrętła z pliku Karola, zapis znane_pola.json): to test offline
for _h in ("_hak_telemetrii", "_hak_pochodni", "_hak_wypadu"):
    setattr(cavebot.Cavebot, _h, lambda self: None)
def zrob(s, punkty, **kw):
    atak = lambda m, g: None
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
    b = cavebot.Cavebot(P(s), punkty, zapytaj=s.zapytaj, atak=atak, alarm=lambda w: None, spij=s.spij,
                        zegar=s.zegar, loot=loot, mapa=M, klik=s.klik, **kw)
    b.pietra_ops = Ops(s)
    b.zapis_znanych = False
    return b

def bieg(b, s, n):
    for i in range(n):
        if not b.tick(): return i
    return n




import generuj_trase_miasta as GEN, waliduj_trase

PLIK = sys.argv[1] if len(sys.argv) > 1 else ("troll_do_miasta_v2.json" if (TRASY / "troll_do_miasta_v2.json").exists() else "troll_do_miasta.json")
print("PLAN:", PLIK)
DO = [tuple(p) for p in json.loads((TRASY / PLIK).read_text())]
LIVE = [tuple(p) for p in json.loads((TRASY / "troll_do_miasta.json").read_text())]
ETAPY = wypad.zbuduj_etapy(DO, M)
WEJSCIE_Z7 = (32493, 32260, 7)
WYJSCIE_Z8 = (32493, 32260, 8)
GORN = (32377, 32201, 7)
MI = json.loads((TRASY / "miejsca_troll.json").read_text())
cavebot.TRYB_PATROL = 1
cavebot.PATROL_PLIK = "miejsca_troll.json"
troll = [tuple(p) for p in json.loads((TRASY / f"{MI['trasa']}.json").read_text())]

# --- A. plik trasy ------------------------------------------------------------------------------------------------------
def cheb(a, b): return max(abs(a[0] - b[0]), abs(a[1] - b[1]))
def pola(pts): return sum(cheb(a, b) for a, b in zip(pts, pts[1:]) if a[2] == b[2])
i7 = next(i for i, p in enumerate(DO) if p[2] == 7)
sprawdz("A1 pierwszy punkt z7 = (32493,32260,7) (wyprawa._do_depo_odwrocona bierze go jako wejście na z7)", DO[i7] == WEJSCIE_Z7, DO[i7])
sprawdz("A2 koniec trasy = pole przy Gornie (32377,32201,7)", DO[-1] == GORN, DO[-1])
j7 = LIVE.index(WEJSCIE_Z7)
sprawdz("A3 droga po z7 do Gorna taka sama jak w żywej trasie", DO[i7:] == LIVE[j7:], f"{len(DO) - i7} vs {len(LIVE) - j7} pkt")
zm = [(DO[i], DO[i + 1]) for i in range(len(DO) - 1) if DO[i][2] != DO[i + 1][2]]
dol = [(a, b) for a, b in zm if b[2] > a[2]]
sprawdz("A4 jedno zejście w dziurę: (32478,32269) z8 -> z9, wyjście z jaskini dwiema drabinami + liną",
        dol == [((32478, 32270, 8), (32478, 32269, 9))] and len(zm) <= 4, f"przejścia {[(a, b[2]) for a, b in zm]}")
w = waliduj_trase.waliduj(DO, M)
bl = [x for x in w if x[0] == "BLAD"]
sprawdz("A5 waliduj_trase: brak błędów (punkty nie w ścianie, droga między sąsiednimi punktami)", not bl, bl[:2])
sprawdz("A6 żaden punkt nie powtórzony (jedna droga, bez dublowania)", len(set(DO)) == len(DO), f"{len(DO)} pkt, {len(set(DO))} różnych")
prob = wypad.sprawdz_plan(ETAPY, M, rampy_ok=True)
sprawdz("A7 wypad.sprawdz_plan: plan wykonalny (przejścia przy polach liny/dziury, stoi na końcu etapu)", not prob, prob[:2])
NAGRANIE = pola(troll)   # dawna trasa = odwrócone nagranie troll_cave (213 pól wg pomiaru 25.10; nagranie ma tyle samo)
NOW_J = pola(DO[:i7])
sprawdz("A8 część w jaskini: co najmniej 2x krótsza niż odwrócone nagranie troll_cave", NOW_J * 2 <= NAGRANIE, f"{NOW_J} pól vs {NAGRANIE} pól nagrania")

# --- B. wypad w symulatorze: start z różnych pól jaskini ---------------------------------------------------------------------
class Ops2(Ops):
    def wiadomosci(o): return []

class Sw(Swiat):
    """Swiat + licznik kroków (zmiana pola), żeby porównać z najkrótszą drogą."""
    kroki = 0
    def ruch(s, dx, dy):
        przed = tuple(s.poz); Swiat.ruch(s, dx, dy)
        if tuple(s.poz) != przed: s.kroki += 1

G2 = GEN.GrafDrabiny(M)
def idealnie(start):
    """Najkrótsza droga (kroki) start -> pole pod liną wyjścia (32493,32260,z8); None, gdy graf jej nie zna (część wschodnia: łączniki z pliku miejsc)."""
    d = G2.astar(start, WYJSCIE_Z8)
    return None if d is None else len(d) - 1

def wypad_z(start, seed):
    random.seed(seed)
    s = Sw(start, gora="use")
    b = zrob(s, list(troll), okrazenia=999)
    b.wypad_aktywny = True
    logi = []
    k = types.SimpleNamespace(WYPRAWA_DOJSCIE_PATROLEM=1)
    w = wypad.Wypad(b, Ops2(s), konf=k, log=logi.append, plan=(ETAPY, ETAPY))
    w.logi = logi
    if not w._start("test", {}):
        return s, w, logi, 0, False
    n = 0
    while n < 4000 and w.stan == "WYPAD" and tuple(s.poz)[2] != 7:
        w._obieg(b.zegar()); n += 1
    return s, w, logi, n, True

STARTY = [
    ("kieszeń z9 komora południe (Wydra 25.10)", (32485, 32297, 9)),
    ("kieszeń z9 komora południe, głęboko", (32488, 32299, 9)),
    ("kieszeń z9 komora południe, północ", (32484, 32301, 9)),
    ("z8 przy drabinie komory", (32482, 32294, 8)),
    ("z8 hala, spawn #1", (32478, 32290, 8)),
    ("z8 wschodni kraniec hali, spawn #2", (32491, 32294, 8)),
    ("z8 zachodnia odnoga hali", (32474, 32289, 8)),
    ("z8 korytarz przy pojemniku", (32481, 32285, 8)),
    ("kieszeń z9 pod (32474,32286)", (32474, 32284, 9)),
    ("gniazdo z9, spawn #5", (32471, 32270, 9)),
    ("gniazdo z9, środek", (32474, 32274, 9)),
    ("z8 przy schodach gniazda", (32478, 32277, 8)),
    ("z9 korytarz środkowy", (32480, 32269, 9)),
    ("z8 północ, przy wyjściu", (32488, 32264, 8)),
    ("z9 nowa część (część wschodnia)", (32503, 32284, 9)),
    ("z9 (32497,32279) odcięte od planu", (32497, 32279, 9)),
    ("z8 kieszeń wschodnia", (32497, 32268, 8)),
]
suma = 0; suma_idealnie = 0
for i, (opis, st) in enumerate(STARTY):
    s, w, logi, n, start_ok = wypad_z(st, 100 + i)
    dol_n = sum(1 for a, z in s.zmiany if z > a[2])
    zle = [l for l in logi if "awaria" in l.lower() or "utknię" in l.lower() or "zgubiona" in l.lower()]
    id_ = idealnie(st)
    dojscie = w.dojscie_plany > 0
    info = f"{st} kroki {s.kroki}, ideał {id_}, zejść w dół {dol_n}, obiegów {n}, t={s.t:.0f}s" + (", dojście" if dojscie else "")
    sprawdz(f"B{i + 1} {opis}: dochodzi na z7 (wyjście z jaskini)", start_ok and s.poz[2] == 7 and not zle and s.nielegalne <= 5,
            info + f" nielegalne {s.nielegalne} {zle[:1]}")
    if id_ is not None and not dojscie:
        sprawdz(f"B{i + 1}a ... droga bez objazdów: kroki <= ideał + 25%", s.kroki <= id_ * 1.25 + 6, info)
    sprawdz(f"B{i + 1}b ... najwyżej jedno zejście w dziurę z planu (nieuniknione (32478,32269)); przy dojściu +1", dol_n <= (2 if dojscie else 1), info + " (dojście patrolem z odciętej kieszeni może dołożyć jedno zejście z pliku miejsc)")
    if id_ is not None:
        suma += s.kroki; suma_idealnie += id_
print(f"SUMA kroków do wyjścia z jaskini: {suma}, ideał: {suma_idealnie}")
sprawdz("B* suma kroków <= 1.2 x ideał", suma <= suma_idealnie * 1.2, f"{suma} vs {suma_idealnie}")

print("WYNIK", sum(ok), "/", len(ok)); sys.exit(0 if all(ok) else 1)
