"""Jedzenie w walce (JEDZENIE_W_WALCE): głód po braku wzrostu HP z regeneracji. Na atrapach, bez X11
(RETRONIC_TESTY=1, klawisz/loot to listy)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot, pokretla

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Swiat:
    def __init__(s):
        s.t = 0.0; s.poz = [100, 100, 7]; s.stwory = []; s.klawisze = []
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 20, "max_mana": 35}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}

class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)

def zrob(s, jedzenie="F5", plecak=False):
    zjedzone = []
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: (zjedzone.append(1), ["mięso"])[1])
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=loot, okrazenia=1, jedzenie=None if plecak else jedzenie)
    if plecak:
        b.klik = object()
    b.przerwa_od = float("inf"); b.zjedzone_plecak = zjedzone; b.prog_aktualny = 30.0
    return b

def troll(x, y, i=10): return {"id": i, "nazwa": "Troll", "x": x, "y": y, "z": 7, "hp": 100}
def gr(proc): return {"hp": proc * 1.9, "max_hp": 190.0, "proc": float(proc), "mana": 20, "max_mana": 35}

def odczyt(b, s, proc, dt=1.0):
    """Jak w tick(): odczyt gracza i stworów, śledzenie regeneracji."""
    s.t += dt
    g = gr(proc)
    if b.hp_ostatnie is None or g["hp"] > b.hp_ostatnie or g["hp"] >= g["max_hp"]:
        b.hp_wzrost = s.t
        if b.hp_ostatnie is None or g["hp"] >= g["max_hp"] or s.t - b.zdrowie_rzut_ts > cavebot.JEDZENIE_WALKA_LECZENIE_S:
            b.hp_regen = s.t
    b.hp_ostatnie = g["hp"]
    b.ostatnie_stwory = [dict(m) for m in s.stwory]
    return g

# 0. kontrakt pokręteł
sprawdz("0a domyślne", cavebot.JEDZENIE_W_WALCE == 1 and cavebot.CZAS_JEDZENIA_WALKA == 20.0
        and cavebot.JEDZENIE_WALKA_HP_MARGINES == 20)
sprawdz("0b ZAKRESY", all(k in pokretla.ZAKRESY for k in ("JEDZENIE_W_WALCE", "CZAS_JEDZENIA_WALKA", "JEDZENIE_WALKA_HP_MARGINES")))
sprawdz("0c analityk nie wyłączy", pokretla.waliduj({"JEDZENIE_W_WALCE": 0}, {"JEDZENIE_W_WALCE": 1})[0] == {})
sprawdz("0d analityk nie wydłuży okna", pokretla.waliduj({"CZAS_JEDZENIA_WALKA": 40.0}, {"CZAS_JEDZENIA_WALKA": 20.0})[0] == {})
sprawdz("0e analityk może skrócić okno", pokretla.waliduj({"CZAS_JEDZENIA_WALKA": 15.0}, {"CZAS_JEDZENIA_WALKA": 20.0})[0] == {"CZAS_JEDZENIA_WALKA": 15.0})
sprawdz("0f analityk nie podniesie marginesu", pokretla.waliduj({"JEDZENIE_WALKA_HP_MARGINES": 40}, {"JEDZENIE_WALKA_HP_MARGINES": 20})[0] == {})

# 1. głód w walce, troll w zasięgu 1: jemy klawiszem mimo JEDZENIE_BLISKO
s = Swiat(); b = zrob(s); s.stwory = [troll(101, 100)]
b.cel = {"id": 10, "nazwa": "Troll", "x": 101, "y": 100, "z": 7, "odl": 1, "hp": 100}
g = odczyt(b, s, 84)
for _ in range(15): g = odczyt(b, s, 84)           # 15 s: jeszcze nie
sprawdz("1a po 15 s bez wzrostu jeszcze nie", not b.jedzenie_potrzebne(g, s.t, (100, 100, 7)))
for _ in range(6): g = odczyt(b, s, 84)            # 21 s
sprawdz("1b po 21 s w walce przy trollu odl 1 jemy", b.jedzenie_potrzebne(g, s.t, (100, 100, 7)))
sprawdz("1c log po polsku", any(l.startswith("Jedzenie w walce: HP nie rośnie od 2") and "troll odl 1" in l for l in LOGI), LOGI[-1:])
t_j = s.t
b.zjedz(s.t, g)
sprawdz("1d klawisz jedzenia wciśnięty", s.klawisze == ["F5"])
sprawdz("1e po jedzeniu zegar zresetowany", b.hp_regen == t_j and b.hp_wzrost == t_j)
for _ in range(25): g = odczyt(b, s, 84)
sprawdz("1f odstęp JEDZENIE_WALKA_PONOW_S: nie jemy znowu", not b.jedzenie_potrzebne(g, s.t, (100, 100, 7)))

# 2. stara ścieżka bez walki: potwór daleko, głód 30 s -> jak dawniej
s = Swiat(); b = zrob(s); s.stwory = []
g = odczyt(b, s, 80)
for _ in range(25): g = odczyt(b, s, 80)
sprawdz("2a bez potworów po 25 s nie (stare 30 s)", not b.jedzenie_potrzebne(g, s.t, (100, 100, 7)))
for _ in range(6): g = odczyt(b, s, 80)
sprawdz("2b bez potworów po 31 s tak", b.jedzenie_potrzebne(g, s.t, (100, 100, 7)))

# 3. HP poniżej progu bezpieczeństwa: nie jemy (leczenie/ucieczka pierwsze)
s = Swiat(); b = zrob(s); s.stwory = [troll(101, 100)]
b.cel = {"id": 10, "nazwa": "Troll", "x": 101, "y": 100, "z": 7, "odl": 1, "hp": 100}
g = odczyt(b, s, 45)
for _ in range(25): g = odczyt(b, s, 45)           # próg 30 + 20 = 50 > 45
sprawdz("3a HP 45% < prog+margines: nie jemy w walce", not b.jedzenie_potrzebne(g, s.t, (100, 100, 7)))
b.ucieczka = True
g = odczyt(b, s, 80)
for _ in range(25): g = odczyt(b, s, 80)
sprawdz("3b w ucieczce ścieżka walki nie działa", b._glod_w_walce(g, s.t, (100, 100, 7)) is None)
b.ucieczka = False

# 4. brak fałszywego alarmu przy regeneracji (HP rośnie co kilka s mimo obrażeń)
s = Swiat(); b = zrob(s); s.stwory = [troll(101, 100)]
b.cel = {"id": 10, "nazwa": "Troll", "x": 101, "y": 100, "z": 7, "odl": 1, "hp": 100}
proc = 80.0; g = odczyt(b, s, proc); alarm = False
for i in range(60):
    proc += 1.0 if i % 8 == 7 else (-0.5 if i % 3 == 0 else 0.0)   # tick regeneracji co 8 s, w międzyczasie obrażenia
    g = odczyt(b, s, proc)
    alarm = alarm or b.jedzenie_potrzebne(g, s.t, (100, 100, 7))
sprawdz("4a regeneracja co 8 s przez 60 s: bez alarmu", not alarm)

# 5. leczenie exura nie maskuje głodu: HP rośnie tylko po rzucie
s = Swiat(); b = zrob(s); s.stwory = [troll(101, 100)]
b.cel = {"id": 10, "nazwa": "Troll", "x": 101, "y": 100, "z": 7, "odl": 1, "hp": 100}
proc = 70.0; g = odczyt(b, s, proc)
for i in range(30):
    if i % 6 == 0:
        b.zdrowie_rzut_ts = s.t + 1.0; proc += 8        # exura: HP skacze zaraz po rzucie
    else:
        proc -= 1.5                                     # trolle biją
    g = odczyt(b, s, proc)
sprawdz("5a exura resetuje hp_wzrost (stare liczenie zamaskowane)", s.t - b.hp_wzrost < 8)
sprawdz("5b ale hp_regen stoi: głód wykryty mimo leczenia", b.jedzenie_potrzebne(g, s.t, (100, 100, 7)),
        f"bez_regen={s.t - b.hp_regen:.0f}")

# 6. wyłączenie pokrętłem
s = Swiat(); b = zrob(s); s.stwory = [troll(101, 100)]
b.cel = {"id": 10, "nazwa": "Troll", "x": 101, "y": 100, "z": 7, "odl": 1, "hp": 100}
g = odczyt(b, s, 84)
for _ in range(25): g = odczyt(b, s, 84)
cavebot.JEDZENIE_W_WALCE = 0
sprawdz("6a JEDZENIE_W_WALCE=0: stare blokady (cel odl 1) działają", not b.jedzenie_potrzebne(g, s.t, (100, 100, 7)))
cavebot.JEDZENIE_W_WALCE = 1

# 7. jedzenie z plecaka: więcej HP wymagane przy wielu trollach (blok 3-5 s)
s = Swiat(); b = zrob(s, plecak=True); s.stwory = [troll(101, 100, 10), troll(99, 100, 11), troll(100, 101, 12)]
b.cel = {"id": 10, "nazwa": "Troll", "x": 101, "y": 100, "z": 7, "odl": 1, "hp": 100}
g = odczyt(b, s, 60)
for _ in range(25): g = odczyt(b, s, 60)           # 30 + 20 + 3*5 = 65 > 60
sprawdz("7a plecak, 3 trolle, HP 60%: nie jemy", not b.jedzenie_potrzebne(g, s.t, (100, 100, 7)))
s.stwory = [troll(101, 100, 10)]
g = odczyt(b, s, 60)
sprawdz("7b plecak, 1 troll, HP 60%: jemy", b.jedzenie_potrzebne(g, s.t, (100, 100, 7)))

print(f"OK={sum(ok)} FAIL={len(ok) - sum(ok)}")
sys.exit(0 if all(ok) else 1)
