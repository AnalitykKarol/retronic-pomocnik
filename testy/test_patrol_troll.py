"""Patrol po mapie spotu trolli (trasy/miejsca_troll.json, z8+z9): wielopiętrowe przejścia, łącznik przez ścianę,
bramka gniazda, pamięć graczy, wybór pliku w mozg.rozwiaz_patrol. Wyłącznie atrapy, bez gry."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, types, random
sys.dont_write_bytecode = True
_R = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _R)
import cavebot, bot, mapa as _mapa, pietra
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


MI = json.loads((TRASY / "miejsca_troll.json").read_text())
START = tuple(MI["start"])
troll = [tuple(p) for p in json.loads((TRASY / f"{MI['trasa']}.json").read_text())]
cavebot.TRYB_PATROL = 1
cavebot.PATROL_PLIK = "miejsca_troll.json"
nazwy = [m["nazwa"] for m in MI["miejsca"]]
sprawdz("1 plik miejsc: 9 miejsc, graf, przejścia, łącznik", len(nazwy) == 9 and MI.get("graf") and MI.get("przejscia") and MI.get("laczniki"),
        f"{len(nazwy)} miejsc")

def poz_miejsca(m): return (m["x"], m["y"], m["z"])
mpoz = {m["nazwa"]: poz_miejsca(m) for m in MI["miejsca"]}

def bieg_patrolu(s, ticki, **kw):
    b = zrob(s, list(troll), okrazenia=999, **kw)
    n = bieg(b, s, ticki)
    return b, n

# 2. patrol wizytuje miejsca na z8 i z9, bez obić o ścianę i bez porażek przejść
random.seed(7); LOG.clear()
s = Swiat(START, gora="use")
b, n = bieg_patrolu(s, 15000)
z_ok = {p[2] for p in s.odwiedzone}
odw = {nm for nm, p in mpoz.items() if any(abs(q[0] - p[0]) <= 3 and abs(q[1] - p[1]) <= 3 and q[2] == p[2] for q in s.odwiedzone)}
sprawdz("2 patrol: aktywny, oba piętra odwiedzone", b._patrol_aktywny() and z_ok >= {8, 9}, f"z={z_ok} ticki={n} t={s.t:.0f}s")
sprawdz("2 patrol: kilka różnych miejsc odwiedzonych", len(odw) >= 4, f"{sorted(odw)}")
sprawdz("2 patrol: przejścia pięter bez porażek", b.pietra_porazki == 0 and len(s.zmiany) >= 2, f"zmian={len(s.zmiany)} porazki={b.pietra_porazki}")
sprawdz("2 patrol: nielegalne ruchy rzadkie", s.nielegalne <= 5, f"{s.nielegalne}")

# 3. wymuszony wybór miejsca za łącznikiem (z8_nowa_pokoj): dojście przez pole (32505,32270,8)
random.seed(1); LOG.clear()
s = Swiat(START, gora="use")
b = zrob(s, list(troll), okrazenia=999)
cel = mpoz["z8_nowa_pokoj"]
b._patrol_wczytaj()
m = next(x for x in b.miejsca if x["nazwa"] == "z8_nowa_pokoj")
b._patrol_nowy(tuple(s.poz), m, "test", waga=1.0)
for i in range(12000):
    if not b.tick(): break
    if DRZWI in s.odwiedzone and any(q[:2] == cel[:2] and q[2] == 8 for q in s.odwiedzone): break
sprawdz("3 dojście do pokoju za łącznikiem przez pole łącznika", DRZWI in s.odwiedzone, f"t={s.t:.0f}s poz={s.poz}")

# 4. pamięć graczy: obcy gracz w miejscu zmniejsza jego wagę
random.seed(3)
s = Swiat(START, gora="use")
b = zrob(s, list(troll), okrazenia=999); b._patrol_wczytaj()
cel2 = mpoz["z9_poludnie_zach"]
w0 = [x for x in b.miejsca if x["nazwa"] == "z9_poludnie_zach"][0]
s.t = 100.0
b.unikanie = types.SimpleNamespace(gracze=[{"id": 99, "nazwa": "Obcy", "x": cel2[0], "y": cel2[1], "z": cel2[2]}])
sprawdz("4 pamięć graczy: pole _patrol_gracz_czynnik istnieje", hasattr(b, "_patrol_gracz_czynnik") and hasattr(b, "_patrol_pamietaj_graczy"))
try:
    b._patrol_pamietaj_graczy()
    c_ = b._patrol_gracz_czynnik(w0)
    sprawdz("4 obcy gracz w miejscu: czynnik < 1", c_ < 1.0, f"{c_}")
    s.t += cavebot.PATROL_GRACZ_PAM_S + 10
    c2 = b._patrol_gracz_czynnik(w0)
    sprawdz("4 po czasie pamięci: czynnik wraca do 1", c2 == 1.0, f"{c2}")
except Exception as e:
    sprawdz("4 pamięć graczy", False, repr(e))

# 5. wybór pliku w mozg
import mozg
st = (cavebot.TRYB_PATROL, cavebot.PATROL_PLIK)
try:
    cavebot.PATROL_PLIK = "miejsca.json"
    r = mozg.rozwiaz_patrol("patrol:troll")
    sprawdz("5 patrol:troll -> miejsca_troll.json, trasa awaryjna troll_cave", r and r[0] == "troll_cave" and cavebot.PATROL_PLIK == "miejsca_troll.json", f"{r} {cavebot.PATROL_PLIK}")
    cavebot.PATROL_PLIK = "miejsca.json"
    r = mozg.rozwiaz_patrol("patrol")
    sprawdz("5 patrol -> miejsca.json, kanaly2", r and r[0] == "kanaly2" and cavebot.PATROL_PLIK == "miejsca.json", f"{r}")
    sprawdz("5 zwykła trasa: bez zmian", mozg.rozwiaz_patrol("troll_cave") is None)
finally:
    cavebot.TRYB_PATROL, cavebot.PATROL_PLIK = st

# 6. pokrętła w pokretla.py
import pokretla
need = [k for k in dir(cavebot) if k.startswith(("PATROL_PIETRA", "PATROL_GNIAZDO", "PATROL_GRACZ", "PATROL_MOBY"))]
sprawdz("6 nowe pokrętła patrolu w ZAKRESY", need and all(k in pokretla.ZAKRESY for k in need if k.isupper()), f"brak: {[k for k in need if k not in pokretla.ZAKRESY]}")

print(f"\nOK={sum(ok)} FAIL={len(ok) - sum(ok)}")
sys.exit(0 if all(ok) else 1)
