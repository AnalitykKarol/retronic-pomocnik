import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""27.10: bot nie klika (Ctrl+klik / loot) zwłok leżących na polu przejścia między piętrami.
Dowody z dnia: Gebelish 12:49:04 (troll zabity na (32404,31728,9), pole schodów w górę; Ctrl+klik od gracza (32405,31729) -> z8)
i Pomszta 13:12:39 (troll zabity na (32480,31721,9), pole nad dziurą z8 (32480,31721,8); gracz (32480,31720) -> z8).
Zbiór pól przejścia = ten sam co zakaz zmiany piętra w pościgu (flaga 2 na polu albo piętro wyżej) + dziury/drabiny wpadnięcia.
Prawdziwa mapa klienta (mapy/mapa.dat przez mapa.Mapa) dla dwóch przypadków z logów, atrapy dla reszty. Bez gry.
Uruchom: python3 -I testy/test_loot_przejscia.py"""
import sys, types, tempfile
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot, loot, ekran, mapa as mapa_mod

cavebot.REAKCJA = (0.0, 0.0); cavebot.ML_CZAR_AKTYWNY = 0; cavebot.UH_AKTYWNY = 0
cavebot.UH_STAN_PLIK = Path(tempfile.mkdtemp()) / "uh.json"
LOGI = []
cavebot.log = lambda *a: LOGI.append(" ".join(str(x) for x in a))
ok = []


def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info if not warunek else "")


class Swiat:
    def __init__(s, poz): s.t = 0.0; s.poz = list(poz); s.stwory = []; s.hp = 100
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def gracz(s): return {"hp": s.hp * 1.9, "max_hp": 190, "mana": 50, "max_mana": 125, "proc": float(s.hp)}
    def zapytaj(s, z):
        s.t += 0.01
        if z["cmd"] == "gracz": return {"gracz": s.gracz()}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}
        return {}


class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): pass


def nowy(poz, mapa=None):
    cavebot.LOOT_DYNAMICZNY = 1
    cavebot.LOOT_BEZ_DZIUR = 1
    s = Swiat(poz)
    wywolania = []

    def zbierz(z, g):
        wywolania.append(tuple(z))
        return "ok"
    lt = types.SimpleNamespace(zbierz=zbierz, zjedz=lambda log=None: [], ile_jedzenia=lambda: 10)
    b = cavebot.Cavebot(P(s), [(poz[0] + i, poz[1], poz[2]) for i in range(1, 11)], zapytaj=s.zapytaj, atak=lambda m, g: None,
                        alarm=lambda w: None, spij=s.spij, zegar=s.zegar, loot=lt, okrazenia=1, jedzenie="F5")
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    b.mapa = mapa
    b.WYW = wywolania
    return s, b


def zabij(s, b, zwloki_xyz):
    b.cel = {"id": 5, "nazwa": "Troll", "poz": zwloki_xyz, "hp": 0, "odl": 1}
    del LOGI[:]
    b.zgon_celu(s.gracz(), tuple(s.poz), pewny=True)


def linie_przejscia():
    return [l for l in LOGI if "zwłoki na polu przejścia" in l]


M = mapa_mod.Mapa()

# 1. zbiór pól przejścia na prawdziwej mapie klienta: oba dzisiejsze pola TAK, sąsiedzi NIE
s, b = nowy((32405, 31729, 9), M)
sprawdz("1a Gebelish: (32404,31728,9) = pole przejścia (flaga 2 na z8 nad nim)", b._pole_przejscia(32404, 31728, 9))
sprawdz("1b Pomszta: (32480,31721,9) = pole przejścia (pole nad dziurą z8)", b._pole_przejscia(32480, 31721, 9))
sprawdz("1c Gebelish: pole gracza (32405,31729,9) zwykłe", not b._pole_przejscia(32405, 31729, 9))
sprawdz("1d Pomszta: pole gracza (32480,31720,9) zwykłe", not b._pole_przejscia(32480, 31720, 9))
sprawdz("1e zwykłe pola obok zwłok (32404,31727,9), (32481,31721,9)",
        not b._pole_przejscia(32404, 31727, 9) and not b._pole_przejscia(32481, 31721, 9))

# 2. Gebelish: zwłoki na polu przejścia -> bez lootu, jedna linia logu, wpis zwłok zdjęty z listy
s, b = nowy((32405, 31729, 9), M)
ZW = (32404, 31728, 9)
zabij(s, b, ZW)
sprawdz("2a Gebelish: loot.zbierz NIE wywołany (zero Ctrl+klików)", b.WYW == [], b.WYW)
sprawdz("2b Gebelish: dokładnie jedna linia 'zwłoki na polu przejścia (32404, 31728, 9), pomijam'",
        len(linie_przejscia()) == 1 and "(32404, 31728, 9)" in linie_przejscia()[0] and "pomijam" in linie_przejscia()[0], LOGI)
b.zbierz_loot(ZW); b.zbierz_loot(ZW)
sprawdz("2c Gebelish: ponowne próby nie spamują logu i nie klikają", len(linie_przejscia()) == 1 and b.WYW == [], (LOGI, b.WYW))
sprawdz("2d Gebelish: wpis zdjęty z listy oczekujących", all(tuple(z) != ZW for z, _ in b.zwloki_czekajace))
sprawdz("2e Gebelish: zbierz_loot zwraca None (normalny dalszy krok, bez 'brak_okna')", b.zbierz_loot(ZW) is None)
sprawdz("2f Gebelish: zwłoki nie trafiły na licznik brak_okna", b._zw_brak_okna_n(ZW) == 0)

# 3. Pomszta: gracz (32480,31720), zwłoki (0,1) na polu nad dziurą
s, b = nowy((32480, 31720, 9), M)
ZW2 = (32480, 31721, 9)
zabij(s, b, ZW2)
sprawdz("3a Pomszta: loot.zbierz NIE wywołany", b.WYW == [], b.WYW)
sprawdz("3b Pomszta: jedna linia logu z polem (32480, 31721, 9)",
        len(linie_przejscia()) == 1 and "(32480, 31721, 9)" in linie_przejscia()[0], LOGI)

# 4. zwłoki obok (nie na przejściu): bez zmian, loot wywołany
s, b = nowy((32405, 31729, 9), M)
ZN = (32405, 31728, 9)
sprawdz("4a pole zwłok obok zwykłe", not b._pole_przejscia(*ZN))
zabij(s, b, ZN)
sprawdz("4b zwykłe zwłoki obok: loot.zbierz wywołany raz", b.WYW == [ZN], b.WYW)
sprawdz("4c zwykłe zwłoki: brak linii o polu przejścia", linie_przejscia() == [], LOGI)
s, b = nowy((32480, 31720, 9), M)
ZN2 = (32481, 31721, 9)
zabij(s, b, ZN2)
sprawdz("4d Pomszta, zwłoki na zwykłym polu obok: loot.zbierz wywołany", b.WYW == [ZN2], b.WYW)

# 5. żywy mob obok: zwłoki zostają odłożone; po walce zbierz_loot pomija zwłoki z przejścia (zwloki_do_zebrania -> zbierz_loot)
s, b = nowy((32405, 31729, 9), M)
s.stwory = [{"id": 11, "nazwa": "Troll", "gracz": False, "x": 32406, "y": 31729, "z": 9, "hp": 100}]
b.ostatnie_stwory = [dict(m) for m in s.stwory]
zabij(s, b, ZW)
s.stwory = []
b.ostatnie_stwory = []
b.zbierz_loot(ZW)
sprawdz("5a odłożone zwłoki z przejścia też pominięte po walce, log raz", b.WYW == [] and len(linie_przejscia()) == 1, (b.WYW, LOGI))

# 6. loot w walce nie wybiera zwłok z przejścia, zwykłe wybiera
s, b = nowy((32405, 31729, 9), M)
teraz = b.zegar()
b.zwloki_czekajace = [(ZW, teraz)]
sprawdz("6a _lww_wybierz: zwłoki na przejściu odrzucone", b._lww_wybierz(tuple(s.poz), [], teraz) is None)
b.zwloki_czekajace = [(ZN, teraz)]
sprawdz("6b _lww_wybierz: zwykłe zwłoki wybrane", b._lww_wybierz(tuple(s.poz), [], teraz) == ZN)

# 7. hak lootu: pole przejścia zakazane także jako pole zwłok i jako pole poboczne; zwykłe pola nie
s, b = nowy((32405, 31729, 9), M)
sprawdz("7a hak: pole przejścia zakazane (glowne=True)", b._loot_pole_zakazane(*ZW, glowne=True) is True)
sprawdz("7b hak: pole przejścia zakazane (glowne=False)", b._loot_pole_zakazane(*ZW, glowne=False) is True)
sprawdz("7c hak: zwykłe pole obok nie", b._loot_pole_zakazane(32405, 31728, 9, glowne=True) is False)

# 8. loot.py na dziś: Ctrl+klik od gracza (32405,31729), zwłoki (-1,-1): żaden klik w (-1,-1), pozostałe pola 3x3 klikane
GRACZ = (32405, 31729, 9)
klik = []
ekran.otworz = lambda dx, dy: klik.append((dx, dy))
loot.POD_NOGAMI_PIERWSZE = False
loot._pauza = lambda a=0, b_=0: None
loot._zapytaj = lambda z: {"kontenery": [loot.kont(1, "bag", 2853, 8)]} if z["cmd"] == "kontenery" else {"stwory": []}
loot._pozycja_gracza = lambda: GRACZ
loot.POLE_ZAKAZANE = b._loot_pole_zakazane
logi_l = []
wynik = loot._otworz_z_pamiecia(-1, -1, GRACZ, {}, True, logi_l.append)
sprawdz("8a loot.py: zero Ctrl+klików w pole przejścia (-1,-1)", (-1, -1) not in klik, klik)
sprawdz("8b loot.py: log wymienia (-1,-1) jako zakazane", any("(-1,-1) dziura" in l for l in logi_l), logi_l)
sprawdz("8c loot.py: wynik bez okna (None), bot dalej", wynik == (None, None), wynik)
loot.POLE_ZAKAZANE = None
klik.clear()
loot._otworz_z_pamiecia(-1, -1, GRACZ, {}, True, lambda t: None)
sprawdz("8d bez haka (dawne zachowanie): pole (-1,-1) klikane (dowód, że test 8a coś mierzy)", (-1, -1) in klik, klik)

# 9. pokrętło LOOT_BEZ_DZIUR=0 = dawne zachowanie
s, b = nowy((32405, 31729, 9), M)
cavebot.LOOT_BEZ_DZIUR = 0
zabij(s, b, ZW)
sprawdz("9a LOOT_BEZ_DZIUR=0: loot idzie jak dotąd (zbierz wywołany)", b.WYW == [ZW] and linie_przejscia() == [], (b.WYW, LOGI))
cavebot.LOOT_BEZ_DZIUR = 1


# 10. źródła spoza mapy: atrapa mapy bez flag; dziury, ZASYPANE, przejścia z danych
class MapaPusta:
    def __init__(m, flagi=None): m.f = flagi or {}
    def pole(m, x, y, z): return (m.f.get((x, y, z), 1), 0, 100)


s, b = nowy((100, 100, 8), MapaPusta({(50, 50, 8): 3, (60, 60, 7): 3}))
sprawdz("10a flaga 2 na polu (schody w dół z8)", b._pole_przejscia(50, 50, 8))
sprawdz("10b pole pod flagą 2 piętro wyżej (schody w górę z9)", b._pole_przejscia(60, 60, 8))
sprawdz("10c zwykłe pole", not b._pole_przejscia(70, 70, 8))
import wpadniecie
w = wpadniecie.Wpadniecie.__new__(wpadniecie.Wpadniecie)
w.plik = w.plik_omijaj = w.plik_drabin = None
w.dziury, w.omijaj, w.drabiny, w.log = {(11, 12, 8)}, set(), {(21, 22, 9)}, lambda t: None
w._przejscia = [{"T": (31, 32, 8), "L": (31, 32, 9)}, {"T": (41, 42, 9), "L": (41, 43, 8)}]
b.wpadniecie = w
sprawdz("10d nauczona dziura", b._pole_przejscia(11, 12, 8))
sprawdz("10e drabina nauczona", b._pole_przejscia(21, 22, 9))
sprawdz("10f wejście zejścia w dół z przejść w danych", b._pole_przejscia(31, 32, 8))
sprawdz("10g pole lądowania pod dziurą (lina w górę)", b._pole_przejscia(31, 32, 9))
sprawdz("10h R przejścia w górę (drabina)", b._pole_przejscia(41, 42, 9))
sprawdz("10i brak mapy: tylko dane, nic nie wywraca", (setattr(b, "mapa", None), b._pole_przejscia(11, 12, 8))[1]
        and not b._pole_przejscia(70, 70, 8))

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
