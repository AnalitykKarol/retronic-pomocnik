"""W wypadzie (wypad_aktywny) bot biegnie i nie walczy; walka tylko gdy stoi >= WYPAD_BLOK_S ze stworem obok. Atrapy."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.RUNA_AKTYWNA = 0
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Swiat:
    def __init__(s): s.t = 0.0; s.poz = [100, 100, 7]; s.zablok = False
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.01
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 190, "max_hp": 190, "mana": 100, "max_mana": 100}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": 7, "hp": 100}
            m = {"id": 1234510, "nazwa": "Troll", "gracz": False, "x": s.poz[0] + 1, "y": s.poz[1], "z": 7, "hp": 100}
            return {"stwory": [ja, m]}
class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): pass
    def krok(p, k):
        p.s.t += 0.2
        if not p.s.zablok:
            d = bot.KIERUNKI[k]; p.s.poz[0] += d[0]; p.s.poz[1] += d[1]
        return tuple(p.s.poz)
def zrob(s, atak):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: [])
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj, atak=atak,
                        alarm=lambda w: None, spij=s.spij, zegar=s.zegar, loot=loot, okrazenia=1, jedzenie="F5")
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    return b

# 1. bieg: stwór obok, ale bot się rusza -> brak ataku
s = Swiat(); klik = []
b = zrob(s, lambda m, g: klik.append(s.t)); b.wypad_aktywny = True
for _ in range(30):
    s.t += 0.5; b.tick()
sprawdz("bieg: bez ataku gdy się ruszamy", not klik, f"kliki {len(klik)}")

# 2. zablokowany: stoimy >= WYPAD_BLOK_S, stwór obok -> walka
s = Swiat(); klik = []; s.zablok = True
b = zrob(s, lambda m, g: klik.append(s.t)); b.wypad_aktywny = True
b.ruch_czas = 0.0
for _ in range(30):
    s.t += 0.5; b.tick()
sprawdz("zablokowany: bije", bool(klik), f"kliki {len(klik)}")

# 3. bez wypadu: normalna walka
s = Swiat(); klik = []
b = zrob(s, lambda m, g: klik.append(s.t))
for _ in range(10):
    s.t += 0.5; b.tick()
sprawdz("bez wypadu: walka jak zwykle", bool(klik))

# 4. pokrętło 0: walczy także w wypadzie
cavebot.WYPAD_BIEGNIJ = 0
s = Swiat(); klik = []
b = zrob(s, lambda m, g: klik.append(s.t)); b.wypad_aktywny = True
for _ in range(10):
    s.t += 0.5; b.tick()
sprawdz("WYPAD_BIEGNIJ=0: walka", bool(klik))
cavebot.WYPAD_BIEGNIJ = 1
# 5. pętla (dziura/drabina): bot ciągle "się rusza" (ruch_czas świeży) w promieniu 2 pól, stwór obok -> walka po WYPAD_PETLA_S
s = Swiat(); klik = []; s.zablok = True
b = zrob(s, lambda m, g: klik.append(s.t)); b.wypad_aktywny = True
for _ in range(40):
    s.t += 0.5; b.ruch_czas = s.t; b.tick()
sprawdz("pętla bez postępu: bije", bool(klik), f"kliki {len(klik)}")

# 6. ten sam układ, ale dalej od trasy bez stwora obok: bez walki, bez błędu
cavebot.WYPAD_PETLA_S = 0.0
s = Swiat(); klik = []; s.zablok = True
b = zrob(s, lambda m, g: klik.append(s.t)); b.wypad_aktywny = True
for _ in range(40):
    s.t += 0.5; b.ruch_czas = s.t; b.tick()
sprawdz("WYPAD_PETLA_S=0: dawne zachowanie (bez ataku)", not klik, f"kliki {len(klik)}")
cavebot.WYPAD_PETLA_S = 8.0
print("WYNIK", sum(ok), "/", len(ok)); sys.exit(0 if all(ok) else 1)
