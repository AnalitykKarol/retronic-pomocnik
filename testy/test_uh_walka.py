"""UH_W_WALCE: runa w trakcie walki przy prawie pełnej manie. Na atrapach (RETRONIC_TESTY=1), bez gry."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, tempfile, types
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot, pokretla, uh

cavebot.REAKCJA = (0.0, 0.0); cavebot.ML_CZAR_AKTYWNY = 0
TMP = Path(tempfile.mkdtemp())
cavebot.UH_STAN_PLIK = TMP / "uh_stan.json"
_l0 = cavebot.log
cavebot.log = lambda *a: None
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Swiat:
    def __init__(s):
        s.t = 0.0; s.poz = [100, 100, 7]; s.stwory = []; s.mana = 120; s.hp = 100
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def gracz(s): return {"hp": s.hp * 1.9, "max_hp": 190, "mana": s.mana, "max_mana": 125, "proc": float(s.hp)}
    def zapytaj(s, z):
        s.t += 0.05
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

def zrob(s):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: ["mięso"], ile_jedzenia=lambda: 10)
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj, atak=lambda m, g: None,
                        alarm=lambda w: None, spij=s.spij, zegar=s.zegar, loot=loot, okrazenia=1, jedzenie="F5")
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0; b.jz_odczyt = (0.0, 10)
    return b

WYW = []
TRYB = []
def fake_zrob(env, *a, **k):
    WYW.append(1); return {"wynik": "ok", "powod": "ok", "alarm": False, "czas_s": 5.0, "rzuty": 1}
uh.zrob_runa = fake_zrob
def mob(x, id=9, nazwa="Troll", gracz=False, dx=None):
    return {"id": id, "nazwa": nazwa, "gracz": gracz, "x": x, "y": 100, "z": 7, "hp": 100}

def proba(walka=1, mana=120, hp=100, stwory=(), cel=True, ucieczka=False, w_poscigu=True):
    WYW.clear(); cavebot.UH_AKTYWNY = 1; cavebot.UH_W_WALCE = walka
    s = Swiat(); s.mana = mana; s.hp = hp; s.stwory = list(stwory); b = zrob(s)
    b.cel = {"id": 9, "poz": (stwory[0]["x"], 100, 7)} if (cel and stwory) else None
    b.w_poscigu = w_poscigu and bool(cel); b.ucieczka = ucieczka
    lista = s.zapytaj({"cmd": "stwory"})["stwory"]
    wyn = b._uh_tick(s.gracz(), (100, 100, 7), lista, 50.0)
    return wyn, b

# 0. kontrakt
sprawdz("0a domyślnie 0", cavebot.UH_W_WALCE == 0 and cavebot.UH_W_WALCE_MANA_MARGINES == 5 and cavebot.UH_W_WALCE_MIN_HP == 90)
sprawdz("0b zakresy", pokretla.ZAKRESY["UH_W_WALCE"] == (0, 1)
        and pokretla.waliduj({"UH_W_WALCE": 1}, {"UH_W_WALCE": 0})[0] == {}
        and pokretla.waliduj({"UH_W_WALCE": 1})[0] == {"UH_W_WALCE": 1})

# (a) wyłączone: walka blokuje jak dotąd
w, b = proba(walka=0, stwory=[mob(103)])
sprawdz("a UH_W_WALCE=0 blokada", w is False and not WYW)
# (b) włączone, mana 120/125, HP 100, troll w odl 3 -> start
w, b = proba(stwory=[mob(103)])
sprawdz("b start w walce", w is True and len(WYW) == 1 and b.uh_tryb_walki is False, WYW)
# (c) troll w odl 1 -> blokada; odl 2 -> start
cavebot.UH_W_WALCE_DYSTANS = 1
w, b = proba(stwory=[mob(101)])
sprawdz("c DYSTANS=1: przylegający blokuje (stare zachowanie)", w is False and not WYW)
cavebot.UH_W_WALCE_DYSTANS = 0
w, b = proba(stwory=[mob(101)])
sprawdz("c0 DYSTANS=0 (domyślnie): przylegający troll NIE blokuje startu", w is True and len(WYW) == 1, WYW)
w, b = proba(stwory=[mob(102)])
sprawdz("c2 odl 2 startuje", w is True and len(WYW) == 1)
# (d) mana 80 -> blokada; granica 120 ok, 119 nie
w, b = proba(mana=80, stwory=[mob(103)])
sprawdz("d mana 80", w is False and not WYW)
w, b = proba(mana=119, stwory=[mob(103)])
sprawdz("d2 mana 119 (< 125-5)", w is False and not WYW)
# (e) HP 80% -> blokada
w, b = proba(hp=80, stwory=[mob(103)])
sprawdz("e HP 80%", w is False and not WYW)
# (f) gracz w widoku (także daleko) -> blokada
w, b = proba(stwory=[mob(103), mob(107, id=20, nazwa="Obcy", gracz=True)])
sprawdz("f gracz w widoku", w is False and not WYW)
# (g) ucieczka -> blokada
w, b = proba(stwory=[mob(103)], ucieczka=True)
sprawdz("g ucieczka", w is False and not WYW)
# ostrożny, stan WYPAD, czar w toku
w, b = proba(stwory=[mob(103)]); WYW.clear()
b.ostrozny = True
sprawdz("g2 ostrozny", b._uh_blokada(Swiat().gracz(), (100, 100, 7), 50.0, []) == "ucieczka")
b.ostrozny = False; b.ustaw_stan("WYPAD", "x")
sprawdz("g3 stan WYPAD", b._uh_blokada(Swiat().gracz(), (100, 100, 7), 50.0, []) == "stan")
# cel o nieznanym położeniu
WYW.clear(); cavebot.UH_W_WALCE = 1; cavebot.UH_W_WALCE_DYSTANS = 1; s = Swiat(); b = zrob(s); b.cel = {"id": 77}
sprawdz("h DYSTANS=1: cel nieznany", b._uh_blokada(s.gracz(), (100, 100, 7), 50.0, []) == "walka_cel_nieznany")

cavebot.UH_W_WALCE_DYSTANS = 0
# przerwanie w trakcie runy: tryb walki (DYSTANS=0: moby nie przerywają)
cavebot.UH_W_WALCE = 1
s = Swiat(); b = zrob(s); b.uh_tryb_walki = True
s.stwory = [mob(103)]
sprawdz("i moby dalej nie przerywają", b._uh_przerwanie() is None)
s.stwory = [mob(101)]
sprawdz("i2 DYSTANS=0: przylegający troll nie przerywa", b._uh_przerwanie() is None)
s.stwory = [mob(101, id=9), dict(mob(99, id=10), y=100)]
sprawdz("i2b dwa przylegające trolle (HP 100%) nie przerywają", b._uh_przerwanie() is None)
cavebot.UH_W_WALCE_DYSTANS = 1; s.stwory = [mob(101)]
sprawdz("i2c DYSTANS=1: przylegający przerywa (stare zachowanie)", b._uh_przerwanie() is not None)
cavebot.UH_W_WALCE_DYSTANS = 0
s.stwory = [mob(101)]
# troll dochodzi w trakcie: start przy trollu w 3, potem przylega
b.uh_hp_start = 100.0
s.stwory = [mob(103)]; sprawdz("i2d start: troll w odl 3 nie przerywa", b._uh_przerwanie() is None)
s.stwory = [mob(101)]; sprawdz("i2e troll doszedł w trakcie: nie przerywa", b._uh_przerwanie() is None)
s.hp = 70; b.uh_hp_start = 100.0
sprawdz("i2f HP 70 < 80: przerywa", "HP" in (b._uh_przerwanie() or ""))
s.hp = 100; b.uh_hp_start = None
s.stwory = [mob(103), mob(106, id=20, nazwa="Obcy", gracz=True)]
sprawdz("i3 gracz przerywa", b._uh_przerwanie() is not None)
s.stwory = [mob(103)]; s.hp = 85
sprawdz("i4 HP 85 >= 80 trwa (start nieznany)", b._uh_przerwanie() is None)
b.uh_hp_start = 100.0
sprawdz("i4b HP 85, start 100: spadek 15 < 25, trwa", b._uh_przerwanie() is None)
s.hp = 83; b.uh_hp_start = 110.0
sprawdz("i4c spadek >= 25 pp od startu: przerywa", "spada" in (b._uh_przerwanie() or ""))
b.uh_hp_start = None; s.hp = 85
s.hp = 75
sprawdz("i5 HP 75 < 80 przerywa", b._uh_przerwanie() is not None)
s.hp = 100; b.ucieczka = True
sprawdz("i6 ucieczka przerywa", b._uh_przerwanie() == "ucieczka")
b.ucieczka = False; b.uh_tryb_walki = False; s.stwory = [mob(103)]
sprawdz("i7 poza trybem walki mob w 3 przerywa jak dotąd", b._uh_przerwanie() is not None)

sprawdz("j pokrętło w pokretla", pokretla.ZAKRESY["UH_W_WALCE_DYSTANS"] == (0, 3) and cavebot.UH_W_WALCE_DYSTANS == 0
        and pokretla.waliduj({"UH_W_WALCE_DYSTANS": 0}, {"UH_W_WALCE_DYSTANS": 1})[0] == {})
cavebot.UH_W_WALCE = 0; cavebot.UH_AKTYWNY = 0
print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
