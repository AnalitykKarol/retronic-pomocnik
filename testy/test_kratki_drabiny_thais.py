"""Kanały Thais 21.10 (SPEC_kratki_drabiny_thais_1021, DIAGNOZA_dawajkesh_drabina_kanaly_thais_1021): dawajkesh wychodził
z z8 na z7 przez Ctrl+klik lootu na drabinie pod zwłokami (08:53 (32422,32214,8), 09:30 (32370,32213,8)) i nie wracał, bo plan
wpadnięcia nie liczył znanych zejść (niepewne przejścia w górę z mapy zajmowały wszystkie miejsca). Atrapy: bez X11 i gry,
prawdziwa mapa (mapa.py) i prawdziwe pliki tras; bez zapisu trasy/drabiny_nauczone.json."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, tempfile, types
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import cavebot, mapa as _mapa, wpadniecie, loot, ekran, pokretla
from pathlib import Path

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

M = _mapa.mapa()
LOG = []

class CB:
    mapa = M
    cel = None
    pamiec = None
    def droga(self, s, c, dlugosc=1):
        return M.droga(s, c, [], dlugosc, True, limit=cavebot.MAPA_LIMIT)
    def zatrzymaj_klik(self, p): pass
    def _wypad_reset_klik(self): pass

def wpad(**konf):
    k = types.SimpleNamespace(**konf)
    w = wpadniecie.Wpadniecie(CB(), konf=k, log=LOG.append, plik=None)
    w.plik_drabin = None
    return w

KRATKI = ("thais_dojscie_kratka.json", "thais_kratka_32422_32214.json", "thais_kratka_32339_32183.json")

def bez_kratek(w):
    w._przejscia = [t for t in w._wczytaj_przejscia() if t["zrodlo"] not in KRATKI]

def plan(w, lad):
    w.st = {"z0": 8}
    return [(t["T"], t["L"]) for t in (w._znajdz_plan(lad, set()) or [])]

# --- F2: pule planu (bez plików kratek: jedyne pewne zejście to schody pod świątynią) ---
LAD_0930 = (32370, 32214, 7)
w = wpad(WPADNIECIE_PLAN_PULE=0); bez_kratek(w)
sprawdz("F2 stare zachowanie: bez kratek plan z (32370,32214,7) = brak (przypadek 21.10 09:30)", plan(w, LAD_0930) == [])
w = wpad(WPADNIECIE_PLAN_PULE=1); bez_kratek(w)
p = plan(w, LAD_0930)
sprawdz("F2 PULE=1: bez kratek plan przez znane schody (32360,32241/32242,7)",
        len(p) == 1 and p[0][0][:2] in ((32360, 32241), (32360, 32242)) and p[0][0][2] == 7 and p[0][1][2] == 8, p)

# --- F1: dane kratek ---
for lad, kratka in ((LAD_0930, (32370, 32213, 7)), ((32422, 32215, 7), (32422, 32214, 7)), ((32338, 32184, 7), (32339, 32183, 7))):
    for pule in (0, 1):
        w = wpad(WPADNIECIE_PLAN_PULE=pule)
        p = plan(w, lad)
        sprawdz(f"F1 z {lad} (PULE={pule}): zejście kratką {kratka[:2]}",
                p == [(kratka, (kratka[0], kratka[1], 8))], p)

# --- F3: zbiór drabin ---
w = wpad(LOOT_BEZ_DRABIN=1)
d = w.wczytaj_drabiny()
for r in ((32370, 32213, 8), (32422, 32214, 8), (32339, 32183, 8)):
    sprawdz(f"F3 drabina pod kratką {r} w zbiorze", r in d)
sprawdz("F3 punkt trasy szczurów (32422,32214,8) nie jest nauczoną dziurą (drabina to nie ściana)", (32422, 32214, 8) not in w.dziury)

# F3: nauka przy wyjściu w górę (lądowanie x, y+1, z-1 -> drabina x, y, z)
with tempfile.TemporaryDirectory() as tmp:
    for flaga, oczek in ((0, False), (1, True)):
        w = wpad(LOOT_BEZ_DRABIN=flaga, DZIURY_NAUCZONE=1)
        w.plik_drabin = Path(tmp) / f"drabiny_{flaga}.json"
        w._trasa_osiagalna = lambda p: True
        w._wykryto((32423, 32214, 8), (32422, 32215, 7), 0.0)
        sprawdz(f"F3 LOOT_BEZ_DRABIN={flaga}: wyjście 08:53 uczy drabinę (32422,32214,8) = {oczek}",
                ((32422, 32214, 8) in w.drabiny) == oczek and w.plik_drabin.exists() == oczek)
        sprawdz(f"F3 LOOT_BEZ_DRABIN={flaga}: wyjście w górę nie uczy dziury", not w.dziury)

# --- F3: loot nie klika w drabinę ---
KLIKI = []
ekran.otworz = lambda dx, dy: KLIKI.append((dx, dy))
loot._odczyt_kontenerow = lambda: {}
loot._pola_ze_stworami = lambda g: set()
loot._czekaj_na_otwarcie = lambda przed, *a, **k: (None, None)
loot._otworz_dalsze = lambda *a, **k: (None, None)
loot._pozycja_gracza = lambda: (32423, 32214, 8)
loot.POD_NOGAMI_PIERWSZE = 0

loot.DRABINY = set()
stan = {}
r = loot.krok_w_walce(stan, (32422, 32214, 8), (32423, 32214, 8), log=LOG.append)
sprawdz("F3 bez drabin (pusty zbiór): loot w walce klika zwłoki jak dotąd", KLIKI == [(-1, 0)], (r, KLIKI))

loot.DRABINY = set(d)
KLIKI.clear(); stan = {}
r = loot.krok_w_walce(stan, (32422, 32214, 8), (32423, 32214, 8), log=LOG.append)
sprawdz("F3 loot w walce: zwłoki na drabinie = przerwane/drabina, zero kliknięć (09:30)", r == ("przerwane", "drabina") and KLIKI == [], (r, KLIKI))

KLIKI.clear()
loot._otworz_z_pamiecia(-1, 0, (32423, 32214, 8), {}, False, LOG.append)
sprawdz("F3 loot po walce: Ctrl+klik pomija (-1,0) = drabina (32422,32214,8) (08:53), inne pola klika",
        (-1, 0) not in KLIKI and len(KLIKI) >= 1, KLIKI)
sprawdz("F3 log próby oznacza drabinę", any("(-1,0) drabina" in str(x) for x in LOG))

KLIKI.clear()
loot._pozycja_gracza = lambda: (32371, 32214, 8)
loot._plan_teraz = lambda mysz, lista, log: (None, {"zwloki": None})
loot._pauza = lambda *a: None
loot._otworz_bez_pamieci(None, -1, -1, [], LOG.append)
sprawdz("F3 ścieżka bez pamięci: (-1,-1) od (32371,32214) = drabina (32370,32213) bez kliku", (-1, -1) not in KLIKI and KLIKI, KLIKI)

# --- F3: podpięcie w cavebot._wp(), gdy pokrętło z na_zywo.json przychodzi po utworzeniu Wpadniecie (start 21.10 10:43) ---
cavebot.log = LOG.append
w = wpad()
gosc = types.SimpleNamespace(wpadniecie=w, loot=loot)
loot.DRABINY = set()
cavebot.LOOT_BEZ_DRABIN = 0
cavebot.Cavebot._wp(gosc)
sprawdz("F3 _wp przy LOOT_BEZ_DRABIN=0: loot.DRABINY puste", loot.DRABINY == set())
cavebot.LOOT_BEZ_DRABIN = 1
cavebot.Cavebot._wp(gosc)
sprawdz("F3 _wp po włączeniu pokrętła: loot.DRABINY = zbiór wpadnięcia (ten sam obiekt) z drabiną (32370,32213,8)",
        loot.DRABINY is w.drabiny and (32370, 32213, 8) in loot.DRABINY)
w.drabiny.add((1, 2, 3))
cavebot.Cavebot._wp(gosc)
sprawdz("F3 _wp kolejny obieg nie przeładowuje (nauczone w trakcie zostają)", (1, 2, 3) in loot.DRABINY)
cavebot.LOOT_BEZ_DRABIN = 0

# --- pokrętła ---
sprawdz("pokrętła w ZAKRESY (0/1) i domyślnie 0 w cavebot",
        pokretla.ZAKRESY.get("WPADNIECIE_PLAN_PULE") == (0, 1) and pokretla.ZAKRESY.get("LOOT_BEZ_DRABIN") == (0, 1)
        and cavebot.WPADNIECIE_PLAN_PULE == 0 and cavebot.LOOT_BEZ_DRABIN == 0)

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
