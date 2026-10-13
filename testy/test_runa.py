"""Strzał runą (RUNA_AKTYWNA, hotkey RUNA_KLAWISZ=F4) w walce. Na atrapach, bez X11 (RETRONIC_TESTY=1)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot, pokretla

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0
cavebot.ZDROWIE_CZAR_OPOZNIENIE = (0.0, 0.0)
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Swiat:
    def __init__(s):
        s.t = 0.0; s.poz = [100, 100, 7]; s.stwory = []; s.klawisze = []; s.mana = 100; s.hp = 100; s.zapas = None
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp * 1.9, "max_hp": 190, "mana": s.mana, "max_mana": 100}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}

class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)

def zrob(s):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: ["mięso"],
                                 ile_jedzenia=lambda: s.zapas)
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=loot, okrazenia=1, jedzenie="F5")
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    return b

def troll(x, y, hp=100, i=10): return {"id": i, "nazwa": "Troll", "gracz": False, "x": x, "y": y, "z": 7, "hp": hp}
def walka(s, b, stwor):
    s.stwory = [stwor]
    tick(s, b, 1)      # bot sam wybiera cel (Nowy cel) i wchodzi w WALKA; strzał dopiero w następnym obiegu
    assert b.cel is not None and str(b.stan) == "WALKA", (b.cel, b.stan)
def klaw(s, k): return [x for x in s.klawisze if x == k]
def tick(s, b, n=1):
    for _ in range(n):
        s.t += 0.1
        b.tick()

# 0. kontrakt pokręteł
sprawdz("0a domyślnie wyłączone", cavebot.RUNA_AKTYWNA == 0 and cavebot.RUNA_KLAWISZ == "F4"
        and cavebot.RUNA_INTERWAL_S == 2.0 and cavebot.RUNA_MIN_HP_CELU == 0)
sprawdz("0b ZAKRESY", all(k in pokretla.ZAKRESY for k in ("RUNA_AKTYWNA", "RUNA_INTERWAL_S", "RUNA_MIN_HP_CELU")))
sprawdz("0c klawisz tekstowy", pokretla.waliduj({"RUNA_KLAWISZ": "F6"})[0] == {"RUNA_KLAWISZ": "F6"}
        and pokretla.waliduj({"RUNA_KLAWISZ": "ctrl+x"})[0] == {})
sprawdz("0d analityk nie włączy", pokretla.waliduj({"RUNA_AKTYWNA": 1}, {"RUNA_AKTYWNA": 0})[0] == {}
        and pokretla.waliduj({"RUNA_KLAWISZ": "F6"}, {"RUNA_KLAWISZ": "F4"})[0] == {})
sprawdz("0e Pokretla widzi klawisz", "RUNA_KLAWISZ" in pokretla.Pokretla(cavebot, plik="/nie/ma").domyslne)

# 1. wyłączone domyślnie: bez strzału
cavebot.RUNA_AKTYWNA = 0
s = Swiat(); b = zrob(s); walka(s, b, troll(101, 100))
tick(s, b, 5)
sprawdz("1 wyłączone: brak F4", not klaw(s, "F4"), s.klawisze)

# 2. włączone, walka z celem w zasięgu: strzela
cavebot.RUNA_AKTYWNA = 1
s = Swiat(); b = zrob(s); walka(s, b, troll(101, 100))
tick(s, b, 1)
sprawdz("2a strzał F4", klaw(s, "F4") == ["F4"], s.klawisze)
sprawdz("2b log", any(l.startswith("[RUNA] strzał F4 w Troll (HP 100%)") for l in LOGI), LOGI[-2:])

# 3. interwał (czas jawny, bez pauz ticka)
s = Swiat(); b = zrob(s); walka(s, b, troll(101, 100)); s.klawisze.clear()
L = [troll(101, 100)]; P0 = (100, 100, 7)
b.runa_ostatni = float("-inf")
sprawdz("3a pierwszy strzał", b._runa_tick({}, P0, L, 100.0) is True and len(klaw(s, "F4")) == 1)
sprawdz("3b po 1,9 s nie", b._runa_tick({}, P0, L, 101.9) is False and len(klaw(s, "F4")) == 1)
sprawdz("3c po 2,0 s tak", b._runa_tick({}, P0, L, 102.0) is True and len(klaw(s, "F4")) == 2)

# 4. brak celu / dalej niż 3 pola / cel poza listą / nieżywy
s = Swiat(); b = zrob(s); b.cel = None
sprawdz("4a bez celu nie strzela", not b._runa_tick({}, (100, 100, 7), [troll(101, 100)], 10.0) and not klaw(s, "F4"))
s = Swiat(); b = zrob(s); walka(s, b, troll(101, 100))
b._runa_tick({"mana": 100}, (100, 100, 7), [troll(104, 100)], 10.0)
sprawdz("4b 4 pola: nie strzela", not klaw(s, "F4"))
b._runa_tick({"mana": 100}, (100, 100, 7), [troll(103, 100)], 10.0)
sprawdz("4c 3 pola: strzela", len(klaw(s, "F4")) == 1)
b.runa_ostatni = float("-inf")
sprawdz("4d cel nieobecny na liście", not b._runa_tick({}, (100, 100, 7), [], 20.0))
sprawdz("4e cel martwy (hp 0)", not b._runa_tick({}, (100, 100, 7), [troll(101, 100, hp=0)], 20.0))
b.ucieczka = True
sprawdz("4f w ucieczce nie strzela", not b._runa_tick({}, (100, 100, 7), [troll(101, 100)], 20.0))
b.ucieczka = False
b.w_lootcie = True
sprawdz("4g okno lootu blokuje", not b._runa_tick({}, (100, 100, 7), [troll(101, 100)], 20.0))
b.w_lootcie = False

# 5. RUNA_MIN_HP_CELU
cavebot.RUNA_MIN_HP_CELU = 20
s = Swiat(); b = zrob(s); walka(s, b, troll(101, 100, hp=15))
sprawdz("5a cel 15% < 20: nie strzela", not b._runa_tick({}, (100, 100, 7), [troll(101, 100, hp=15)], 10.0))
sprawdz("5b cel 25% >= 20: strzela", b._runa_tick({}, (100, 100, 7), [troll(101, 100, hp=25)], 10.0) is True)
cavebot.RUNA_MIN_HP_CELU = 0

# 6. nie bramkowane manną
s = Swiat(); s.mana = 0; b = zrob(s); walka(s, b, troll(101, 100))
tick(s, b, 1)
sprawdz("6 mana 0: strzela", len(klaw(s, "F4")) == 1, s.klawisze)

# 7. F2 (leczenie) ma pierwszeństwo, potem runa
cavebot.ZDROWIE_CZAR_AKTYWNY = 1
s = Swiat(); b = zrob(s); walka(s, b, troll(101, 100)); s.klawisze.clear(); b.runa_ostatni = float("-inf")
s.hp = 50
tick(s, b, 1)
sprawdz("7a niskie HP: F2, bez F4 w tym obiegu", s.klawisze == ["F2"], s.klawisze)
s.hp = 100; tick(s, b, 1)
sprawdz("7b po leczeniu F4", s.klawisze == ["F2", "F4"], s.klawisze)
cavebot.ZDROWIE_CZAR_AKTYWNY = 0

# 8. F3 (exevo pan na zapas, w walce) ma pierwszeństwo
cavebot.JEDZENIE_CZAR_AKTYWNY = 1; cavebot.JEDZENIE_ZAPAS_W_WALCE = 1
s = Swiat(); b = zrob(s); walka(s, b, troll(101, 100)); s.klawisze.clear(); b.runa_ostatni = float("-inf")
s.zapas = 0; b.jz_odczyt = None        # plecak pusty: zapas < MIN
tick(s, b, 1)
sprawdz("8a zapas 0: F3 przed F4", s.klawisze[:1] == ["F3"], s.klawisze)
cavebot.JEDZENIE_CZAR_AKTYWNY = 0

# 9. runa przed ML (ML w walce)
cavebot.ML_CZAR_AKTYWNY = 1; cavebot.ML_CZAR_W_WALCE = 1
s = Swiat(); b = zrob(s); walka(s, b, troll(101, 100))
b.ml_plan = 0.0
tick(s, b, 1)
sprawdz("9 F4 przed F1", s.klawisze[:1] == ["F4"], s.klawisze)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.ML_CZAR_W_WALCE = 0

# 10. licznik co 20 strzałów
s = Swiat(); b = zrob(s); walka(s, b, troll(101, 100))
t = 10.0
for _ in range(20):
    t += 3.0; b._runa_tick({}, (100, 100, 7), [troll(102, 100)], t)
sprawdz("10 licznik co 20", any("RUNA: strzałów 20" in l for l in LOGI))

cavebot.RUNA_AKTYWNA = 0
print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
