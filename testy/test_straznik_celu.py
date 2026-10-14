"""Strażnik celu (13.10, P2a): Escape po 12 s, ignorowanie po 25 s. Atrapy, bez X11."""
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
cavebot.ATAK_LIMIT_KLIKOW = 0

def przebieg(hp_co=None, sekund=40):
    s = Swiat(); s.flaga = True; s.w_grze = 1234510
    b = zrob(s)
    esc = []; ign = None; nastepny_hp = 5.0
    while s.t < sekund:
        if hp_co and s.t >= nastepny_hp:
            s.hp_m = max(1, s.hp_m - 10); nastepny_hp += hp_co
        n = len(s.klawisze)
        tick(s, b, 0.5)
        if len(s.klawisze) > n and "Escape" in s.klawisze[n:]:
            esc.append(round(s.t, 1))
        if ign is None and 1234510 in b.ignorowane:
            ign = round(s.t, 1)
    return s, b, esc, ign

s, b, esc, ign = przebieg()
sprawdz("1 HP stałe: Escape po ~12 s", esc and 11.5 <= esc[0] <= 15, str(esc))
sprawdz("1b ignorowanie po ~25 s", ign is not None and 24 <= ign <= 29, str(ign))
sprawdz("1c powód straznik", b.ignor_powod.get(1234510, ("?",))[0] == "straznik")
sprawdz("1d brak ponownego wyboru mimo d = 1", b.ignorowany({"id": 1234510, "x": 101, "y": 100, "z": 7, "hp": 100}, (100, 100, 7), s.t) is True)
s, b, esc, ign = przebieg(hp_co=5.0)
sprawdz("2 HP spada co 5 s: strażnik nie odpala", not esc and ign is None, f"esc={esc} ign={ign}")
cavebot.STRAZNIK_CEL = 0
s, b, esc, ign = przebieg()
sprawdz("3 STRAZNIK_CEL=0: brak odpalenia", not esc and ign is None, f"esc={esc} ign={ign}")
cavebot.STRAZNIK_CEL = 1
s = Swiat(); s.flaga = True; s.w_grze = 1234510
b = zrob(s)
for _ in range(4): tick(s, b, 0.5)
s.t += 60.0            # walcz() nie wołane przez 60 s (np. PAUZA/rozmowa mózgu)
n0 = len(s.klawisze)
tick(s, b, 0.5)
sprawdz("4 przerwa w wywołaniach resetuje okno: brak fałszywego Escape/ignorowania",
        "Escape" not in s.klawisze[n0:] and 1234510 not in b.ignorowane, f"{s.klawisze[n0:]} {b.ignorowane}")
print("WYNIK", "OK" if all(ok) else "FAIL"); sys.exit(0 if all(ok) else 1)
