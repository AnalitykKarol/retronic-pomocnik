"""ATAK_INNY_CEL: cel bota obok, flaga ataku False, gra celuje w innego = klik od razu (max 1 na 1.5 s).
Na atrapach, bez X11 (RETRONIC_TESTY=1)."""
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
        s.t = 0.0; s.poz = [100, 100, 7]; s.flaga = False; s.w_grze = 99; s.klik = []
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
            m = {"id": 1234510, "nazwa": "Troll", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 100}
            if s.flaga is not None:
                m["atakowany"] = s.flaga
            return {"stwory": [ja, m]}

class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): pass

def zrob(s):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: [])
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: s.klik.append(s.t), alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=loot, okrazenia=1, jedzenie="F5", czy_atakowany=lambda m, g: m.get("atakowany"))
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    return b

def tick(s, b, dt=0.1):
    s.t += dt; b.tick()

def scenariusz(flaga, w_grze, ustaw=True):
    cavebot.ATAK_INNY_CEL = ustaw
    s = Swiat(); s.flaga = flaga; s.w_grze = w_grze
    b = zrob(s)
    tick(s, b)                 # nowy cel + pierwszy klik
    return s, b

# 1. inny cel w grze + flaga False: klik od razu (poza pierwszym)
s, b = scenariusz(False, 99)
n0 = len(s.klik)
sprawdz("1a pierwszy klik", n0 == 1, s.klik)
tick(s, b)
sprawdz("1b klik inny_cel od razu", len(s.klik) == 2, s.klik)
tick(s, b)
sprawdz("1c limit 1.5 s na cel", len(s.klik) == 2, s.klik)
tick(s, b, 1.6)
sprawdz("1d po 1.5 s znów klik", len(s.klik) == 3, s.klik)
sprawdz("1e log inny_cel", any("[ATAK] klik: Troll id..4510" in l and "powód inny_cel" in l and "cel w grze id..99" in l
                              for l in LOGI), [l for l in LOGI if "[ATAK]" in l][:3])
sprawdz("1f log pierwszy", any("powód pierwszy" in l for l in LOGI))

# 2. cel w grze == cel bota: bez kliku
s, b = scenariusz(False, 1234510)
tick(s, b); tick(s, b)
sprawdz("2 ten sam cel w grze: tylko pierwszy klik", len(s.klik) == 1, s.klik)

# 3. brak celu w grze (None) + flaga False: klik
s, b = scenariusz(False, None)
tick(s, b)
sprawdz("3 cel w grze None: klik", len(s.klik) == 2, s.klik)

# 4. flaga True / None: bez kliku
s, b = scenariusz(True, 99)
tick(s, b); tick(s, b)
sprawdz("4a flaga True: bez kliku", len(s.klik) == 1, s.klik)
s, b = scenariusz(None, 99)
tick(s, b); tick(s, b)
sprawdz("4b flaga None: bez kliku", len(s.klik) == 1, s.klik)

# 5. pokrętło wyłączone: bez kliku (przed upływem PONOWIENIE_ATAKU)
s, b = scenariusz(False, 99, ustaw=False)
tick(s, b); tick(s, b)
sprawdz("5 ATAK_INNY_CEL=False: bez kliku", len(s.klik) == 1, s.klik)
cavebot.ATAK_INNY_CEL = True

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
