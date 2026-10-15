"""Wyprawa/wypad: dojście do planu drogą patrolu (WYPRAWA_DOJSCIE_PATROLEM, 15.10). Postać stoi w części jaskini trolli,
z której żaden punkt planu (troll_do_miasta) nie jest osiągalny po tym samym piętrze (z9 przy (32497,32279), kieszeń z8
(32496..32499, 32266..32269)): wypad ma dojść schodami z pliku miejsc (graf patrolu + pietra.py) do osiągalnego punktu planu,
a nie kończyć utknięciem + alarmem. Prawdziwa mapa serwera offline (Cavebot._wczytaj_mape), symulator świata z test_patrol_troll."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, types, random
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



# --- plan wypadu: troll_do_miasta (jak plan wyprawy do depo, bez doklejonej trasy depo) ----------------------------
MI = json.loads((TRASY / "miejsca_troll.json").read_text())
troll = [tuple(p) for p in json.loads((TRASY / f"{MI['trasa']}.json").read_text())]
cavebot.TRYB_PATROL = 1
cavebot.PATROL_PLIK = "miejsca_troll.json"
DO = [tuple(p) for p in json.loads((TRASY / "troll_do_miasta.json").read_text())]
ETAPY = wypad.zbuduj_etapy(DO, M)
PUNKTY_PLANU = {tuple(p) for e in ETAPY if e["typ"] == "IDZ" for p in e["punkty"]}

class Ops2(Ops):
    def wiadomosci(o): return []

def wypad_na(s, konf=None, dojscie=True):
    """Wypad (wyprawa) z planem troll_do_miasta na prawdziwym Cavebocie w symulatorze. -> (cb, w, logi wypadu)."""
    b = zrob(s, list(troll), okrazenia=999)
    b.wypad_aktywny = True
    logi = []
    k = types.SimpleNamespace(WYPRAWA_DOJSCIE_PATROLEM=1 if dojscie else 0) if konf is None else konf
    w = wypad.Wypad(b, Ops2(s), konf=k, log=logi.append, plan=(ETAPY, ETAPY))
    w.logi = logi
    return b, w

def start_wypadu(b, w):
    poz = tuple(b.postac.pozycja())
    return w._start("test", {})

def reachable_from(b, poz):
    return any(b.droga(tuple(poz), p[:2], dlugosc=0) is not None for p in PUNKTY_PLANU if p[2] == poz[2])

def biegnij(b, w, s, max_obiegow=800, stop=lambda: False):
    n = 0
    while n < max_obiegow and w.stan == "WYPAD":
        w._obieg(b.zegar()); n += 1
        if stop(): break
    return n

BIEZ = lambda w: any("dojście do planu zakończone" in l for l in w.logi)

# 1. punkt wyjścia: z9 przy (32497,32279) nie ma połączenia z planem po tym samym piętrze (zweryfikowane na mapie serwera)
START_Z9 = (32497, 32279, 9)
START_Z8 = (32497, 32268, 8)
random.seed(5)
s = Swiat(START_Z9, gora="use")
b, w = wypad_na(s)
sprawdz("1a z9 (32497,32279): żaden punkt planu nie jest osiągalny po tym piętrze", not reachable_from(b, START_Z9))
sprawdz("1b kieszeń z8 (32497,32268): też odcięta od planu", not reachable_from(b, START_Z8))

# 2. start wyprawy z odciętego miejsca: dojście schodami do osiągalnego punktu planu
ok_start = start_wypadu(b, w)
sprawdz("2a start wypadu przyjęty", ok_start and w.stan == "WYPAD", w.logi[-1:] )
n = biegnij(b, w, s, stop=lambda: BIEZ(w) or w.stan != "WYPAD")
poz = tuple(b.postac.pozycja())
dojscie_log = [l for l in w.logi if "dojście do planu" in l]
sprawdz("2b dojście zaplanowane przez schody z pliku miejsc", any("przez schody_" in l for l in dojscie_log), dojscie_log[:1])
sprawdz("2c dojście zakończone na punkcie planu (cel zsynchronizowany)", BIEZ(w) and w.dojscie is None, f"n={n} poz={poz}")
sprawdz("2d postać na piętrze innym niż start (schody)", poz[2] != START_Z9[2] and len({q[2] for q in s.odwiedzone}) >= 2, f"poz={poz}")
sprawdz("2e z miejsca końcowego punkt planu jest osiągalny", reachable_from(b, poz) and (poz in PUNKTY_PLANU or reachable_from(b, poz)))
sprawdz("2f ei/pi wskazują punkt planu na piętrze postaci i blisko niej",
        ETAPY[w.ei]["typ"] == "IDZ" and ETAPY[w.ei]["punkty"][w.pi][2] == poz[2]
        and max(abs(ETAPY[w.ei]["punkty"][w.pi][0] - poz[0]), abs(ETAPY[w.ei]["punkty"][w.pi][1] - poz[1])) <= 1, f"ei={w.ei} pi={w.pi}")
sprawdz("2g bez alarmu/awarii/utknięcia", w.stan == "WYPAD" and not any("awaria" in l or "utknięcie" in l for l in w.logi) and s.nielegalne <= 5,
        f"nielegalne={s.nielegalne}")
sprawdz("2h flaga przejść pięter zdjęta po dojściu", not getattr(b, "wypad_dojscie", False) and not b._pietra_wlaczone())

# 2i. po dojściu wypad idzie dalej planem (stara maszyneria): kolejne obiegi nie wracają do dojścia
ei0 = w.ei
for _ in range(15):
    w._obieg(b.zegar())
sprawdz("2i po dojściu zwykłe chodzenie po planie (bez nowego dojścia)", w.dojscie is None and w.dojscie_plany == 1 and w.stan == "WYPAD",
        f"plany={w.dojscie_plany} stan={w.stan}")

# 3. kieszeń z8
random.seed(6)
s = Swiat(START_Z8, gora="use")
b, w = wypad_na(s)
start_wypadu(b, w)
biegnij(b, w, s, stop=lambda: BIEZ(w) or w.stan != "WYPAD")
poz = tuple(b.postac.pozycja())
sprawdz("3 kieszeń z8 (32497,32268): dojście do planu", BIEZ(w) and reachable_from(b, poz), f"poz={poz} {[l for l in w.logi if 'dojście' in l][:1]}")

# 4. postać połączona z planem: stare zachowanie (bez dojścia)
p0 = next(p for p in DO if p[2] == 9)
random.seed(7)
s = Swiat(p0, gora="use")
b, w = wypad_na(s)
start_wypadu(b, w)
biegnij(b, w, s, max_obiegow=40)
sprawdz("4 połączona z planem: dojścia brak", w.dojscie is None and w.dojscie_plany == 0 and not any("dojście" in l for l in w.logi),
        [l for l in w.logi if "dojście" in l][:1])

# 5. pokrętło WYPRAWA_DOJSCIE_PATROLEM=0: dawne zachowanie (żadnego dojścia)
random.seed(8)
s = Swiat(START_Z9, gora="use")
b, w = wypad_na(s, dojscie=False)
start_wypadu(b, w)
biegnij(b, w, s, max_obiegow=60)
sprawdz("5 pokrętło 0: bez dojścia, cavebot nie dostaje flagi", w.dojscie_plany == 0 and w.dojscie is None and not any("dojście" in l for l in w.logi))

# 6. brak sprawdzenia na starcie, ale etap nieosiągalny wykryty po ETAP_NIEOSIAG_S: dojście zamiast utknięcia
random.seed(9)
s = Swiat(START_Z9, gora="use")
b, w = wypad_na(s)
start_wypadu(b, w)
w.dojscie_sprawdz = False
biegnij(b, w, s, stop=lambda: w.dojscie is not None or BIEZ(w) or w.stan != "WYPAD")
sprawdz("6a nieosiągalny etap (A*): dojście ruszyło", w.dojscie is not None or BIEZ(w), f"t={s.t:.0f}")
sprawdz("6b ... po ETAP_NIEOSIAG_S, nie po ETAP_UTK_S", s.t < wypad.ETAP_UTK_S, f"t={s.t:.0f}")
biegnij(b, w, s, stop=lambda: BIEZ(w) or w.stan != "WYPAD")
sprawdz("6c ... i kończy się na punkcie planu", BIEZ(w) and reachable_from(b, tuple(b.postac.pozycja())))

# 7. przejście pięter nie działa (schody nieczynne): kilka planów, potem istniejąca eskalacja (awaria), nie pętla bez końca
random.seed(10)
s = Swiat(START_Z9, gora="nigdy")
b, w = wypad_na(s)
start_wypadu(b, w)
n = biegnij(b, w, s, max_obiegow=3000, stop=lambda: w.faza != "do" or w.stan != "WYPAD")
awarie = [l for l in w.logi if "dojscie_trasy" in l or "dojscie_nieudane" in l]
sprawdz("7a nieczynne schody: dojście kończy się awarią (istniejąca eskalacja)", w.faza != "do" or w.stan != "WYPAD", f"n={n} faza={w.faza} t={s.t:.0f}")
sprawdz("7b ... w skończonym czasie i z ograniczoną liczbą planów", w.dojscie_plany <= wypad.DOJSCIE_PLANY_MAX and s.t < wypad.DOJSCIE_MAX_S + 200, f"plany={w.dojscie_plany} t={s.t:.0f}")

# 8. brak przejść pięter w pliku miejsc (nic do wykorzystania): stara ścieżka, bez wyjątku
random.seed(11)
s = Swiat(START_Z9, gora="use")
b, w = wypad_na(s)
b.miejsca = []; b.przejscia = []; b.laczniki = []; b.patrol_graf = None
start_wypadu(b, w)
biegnij(b, w, s, max_obiegow=30)
sprawdz("8 brak przejść: dojście nie startuje, wypad działa po staremu", w.dojscie is None and w.dojscie_plany == 0 and w.stan == "WYPAD")

# 9. atrapa Cavebota bez maszynerii patrolu (inne testy wypadu): _dojscie_start nie robi nic
class Goly:
    wypad_aktywny = True
w9 = wypad.Wypad(Goly(), types.SimpleNamespace(), log=lambda *_: None, plan=(ETAPY, ETAPY))
w9.etapy = ETAPY
sprawdz("9 atrapa bez _patrol_droga: dojście wyłączone", w9._dojscie_start((32497, 32279, 9), 0.0, "x") is False)

# 10. pokrętło zarejestrowane tak jak pozostałe
import pokretla
sprawdz("10a stała w cavebot.py = 1", getattr(cavebot, "WYPRAWA_DOJSCIE_PATROLEM", None) == 1)
sprawdz("10b ZAKRESY w pokretla.py", pokretla.ZAKRESY.get("WYPRAWA_DOJSCIE_PATROLEM") == (0, 1))
przyklad = json.loads((Path(_R) / "na_zywo.przyklad.json").read_text())
sprawdz("10c na_zywo.przyklad.json", przyklad.get("WYPRAWA_DOJSCIE_PATROLEM") == 1)
import wyprawa
sprawdz("10d domyślna w wyprawa.DOMYSLNE", wyprawa.DOMYSLNE.get("WYPRAWA_DOJSCIE_PATROLEM") == 1)

print("WYNIK", sum(ok), "/", len(ok)); sys.exit(0 if all(ok) else 1)
