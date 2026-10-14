"""Twarde ignorowanie (13.10, P1a): ignorowanie nie znika przy podejściu obok. Atrapy, bez X11."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.RUNA_AKTYWNA = 0
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Swiat:
    def __init__(s):
        s.t = 0.0; s.poz = [100, 100, 7]; s.flaga = False; s.w_grze = 99; s.klik = []; s.klawisze = []; s.hp_m = 100
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.01
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 190, "max_hp": 190, "mana": 100, "max_mana": 100}}
        if z["cmd"] == "cel_ataku":
            return {"id": s.w_grze}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": 7, "hp": 100}
            m = {"id": 1234510, "nazwa": "Troll", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": s.hp_m}
            if s.flaga is not None:
                m["atakowany"] = s.flaga
            return {"stwory": [ja, m]}

class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
    def krok(p, *a, **k): p.s.klawisze.append('krok')
    def kliknij(p, *a, **k): return True

def zrob(s):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: [])
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: s.klik.append(s.t), alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=loot, okrazenia=1, jedzenie="F5", czy_atakowany=lambda m, g: m.get("atakowany"))
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    return b

def tick(s, b, dt=0.1):
    s.t += dt; b.tick()



cavebot.ATAK_INNY_CEL = False
cavebot.STRAZNIK_CEL = 0       # tu mierzymy tylko ignorowanie po limicie kliknięć
def nowe_cele(): return sum(1 for l in LOGI if l.startswith("Nowy cel"))

# 1. IGNOR_TWARDE=1: po ATAK_LIMIT_KLIKOW cel obok jest ignorowany ATAK_LIMIT_IGNOROWANIE s (bez ponownego wyboru)
cavebot.IGNOR_TWARDE = 1
s = Swiat(); s.flaga = False; s.w_grze = 99
b = zrob(s)
for _ in range(60):
    tick(s, b, 0.5)
    if "Escape" in s.klawisze:
        break
sprawdz("1a Escape po limicie", "Escape" in s.klawisze)
n0 = nowe_cele()
for _ in range(20):
    tick(s, b, 0.5)
sprawdz("1b brak ponownego wyboru przez 10 s mimo d = 1", nowe_cele() == n0, f"nowe={nowe_cele() - n0}")
sprawdz("1c powód atak_klik", b.ignor_powod.get(1234510, ("?",))[0] == "atak_klik")

# 2. IGNOR_TWARDE=0: dawne zachowanie (ignorowanie zdejmowane przy d <= IGNOROWANIE_BLISKO)
cavebot.IGNOR_TWARDE = 0
LOGI.clear()
s = Swiat(); s.flaga = False; s.w_grze = 99
b = zrob(s)
for _ in range(60):
    tick(s, b, 0.5)
    if "Escape" in s.klawisze:
        break
n0 = nowe_cele()
for _ in range(10):
    tick(s, b, 0.5)
sprawdz("2 IGNOR_TWARDE=0: cel wybrany ponownie", nowe_cele() > n0, f"nowe={nowe_cele() - n0}")
cavebot.IGNOR_TWARDE = 1

# 3. ignorowany(): limit_walki obok bez ugryzienia = True, z ugryzieniem = False
s = Swiat(); b = zrob(s)
m = {"id": 7, "nazwa": "Troll", "x": 101, "y": 100, "z": 7, "hp": 50, "gracz": False}
b._ignoruj(7, 100.0, "limit_walki")
sprawdz("3a limit_walki obok: ignorowany", b.ignorowany(m, (100, 100, 7), 10.0) is True)
b.hp_gracza_spadek = 10.0
sprawdz("3b limit_walki obok i nas gryzie: zdjęte", b.ignorowany(m, (100, 100, 7), 10.0) is False)
# 4. sciana: daleko, bez drogi (atrapa) = ignorowany; obok = zdjęte
b._ignoruj(8, 100.0, "sciana")
m2 = dict(m, id=8, x=103)
b._ignor_droga_otwarta = lambda *a: False
sprawdz("4a sciana d=3, brak drogi: ignorowany mimo IGNOROWANIE_BLISKO", b.ignorowany(m2, (100, 100, 7), 10.0) is True)
b._ignor_droga_otwarta = lambda *a: True
b.ignor_droga_cache.clear()
sprawdz("4b sciana d=3, droga otwarta: zdjęte", b.ignorowany(m2, (100, 100, 7), 10.0) is False)
b._ignoruj(9, 100.0, "sciana")
sprawdz("4c sciana d=1: zdjęte", b.ignorowany(dict(m, id=9), (100, 100, 7), 10.0) is False)
# 5. log odpuszczenia najwyżej raz na ODPUSZCZ_LOG_S
LOGI.clear()
for t in (1.0, 2.0, 3.0, 7.0):
    b._log_odpuszczenia({"id": 5}, "Odpuszczam X", t)
sprawdz("5 log odpuszczenia raz na 5 s", len([l for l in LOGI if "Odpuszczam" in l]) == 2)
print("WYNIK", "OK" if all(ok) else "FAIL"); sys.exit(0 if all(ok) else 1)
