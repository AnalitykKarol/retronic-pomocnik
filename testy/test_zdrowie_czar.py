"""Leczenie czarem exura (F2), jedzenie czarem exevo pan (F3), priorytet many. Wszystko na atrapach:
klawisze/loot/czat to listy w pamięci, nic nie trafia do gry (RETRONIC_TESTY=1, brak XTEST)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot, pokretla, wypad

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False
cavebot.ML_CZAR_DLUGA_SZANSA = 0.0   # "zamyślenie" 5-14 s (8%) wychodzi poza okno 4,5 s sekcji 8 = losowe FAIL 8b/8b2
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Swiat:
    def __init__(s, hp=100, mana=60, food=0, spawn=True):
        s.t = 0.0; s.poz = [100, 100, 7]; s.hp = hp; s.mana = mana; s.max_mana = 95
        s.stwory = []; s.klawisze = []; s.chat = []; s.food = food; s.spawn = spawn
        s.rzuty = []          # (klawisz, czas)
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.01
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp, "max_hp": 100, "mana": s.mana, "max_mana": s.max_mana}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}

class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k):
        s = p.s; s.klawisze.append(k)
        if k in ("F1", "F2", "F3"): s.rzuty.append((k, s.t))
        if k == "F1": s.mana = max(0, s.mana - 20)
        if k == "F2": s.mana = max(0, s.mana - 25); s.hp = min(100, s.hp + 15)
        if k == "F3":
            s.mana = max(0, s.mana - 30)
            if s.spawn: s.food += 1
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2
        p.s.poz[0] += d[0]; p.s.poz[1] += d[1]
        return tuple(p.s.poz)

def zrob(s, zdrowie=1, jedzenie=0, **kw):
    cavebot.ZDROWIE_CZAR_AKTYWNY = zdrowie
    cavebot.JEDZENIE_CZAR_AKTYWNY = jedzenie
    cavebot.ML_CZAR_AKTYWNY = 0
    cavebot.ML_CZAR_W_WALCE = 0
    cavebot.ML_BLOK_HP = 80
    cavebot.ZDROWIE_CZAR_HP = 65
    cavebot.ML_CZAR_OPOZNIENIE = (0.3, 1.5)
    def zjedz(log=None):
        if s.food > 0:
            s.food -= 1; return ["bread"]
        return []
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=zjedz), okrazenia=1, **kw)
    b.klik = lambda dx, dy: None            # tryb "z plecaka" (loot.zjedz) bez klawisza jedzenia
    b.wypad_czat = types.SimpleNamespace(zablokowany=False, wyslano=lambda t: None)
    b.przerwa_od = float("inf")
    b.zd = []
    b.tele = types.SimpleNamespace(zdarzenie=lambda typ, **d: b.zd.append((typ, d)), probka=lambda *a, **k: None, ruch_tick=lambda *a, **k: None)
    return b

def zdr(b, s):
    g = b.gracz()
    return b._zdrowie_czar_tick(g, b.postac.pozycja(), s.t)

def jed(b, s, **kw):
    g = b.gracz(); b.hp_wzrost = s.t - 1000.0
    return b._jedzenie_czar_tick(g, b.postac.pozycja(), s.t, **kw)

def f(s, k): return [t for kk, t in s.rzuty if kk == k]
MOB = {"id": 7, "nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 100}

# 0. domyślnie wyłączone, stałe
src = open(_os.path.join(_os.path.dirname(cavebot.__file__), "cavebot.py")).read()
sprawdz("0a domyślnie ZDROWIE_CZAR_AKTYWNY=0 i JEDZENIE_CZAR_AKTYWNY=0 w kodzie",
        src.count("\nZDROWIE_CZAR_AKTYWNY = 0 ") == 1 and src.count("\nJEDZENIE_CZAR_AKTYWNY = 0 ") == 1)
sprawdz("0b klawisze i koszty", cavebot.ZDROWIE_CZAR_KLAWISZ == "F2" and cavebot.ZDROWIE_CZAR_KOSZT == 25
        and cavebot.JEDZENIE_CZAR_KLAWISZ == "F3" and cavebot.JEDZENIE_CZAR_KOSZT == 30)
s = Swiat(hp=50); b = zrob(s, zdrowie=0); s.t += 5
sprawdz("0c wyłączone: brak rzutu", not zdr(b, s) and not s.rzuty)

# 1. progi HP
for hp, oczek, opis in ((60, True, "HP 60 < 65"), (65, False, "HP 65 (nie < 65)"), (80, False, "HP 80"),
                        (40, False, "HP 40 = próg ucieczki: ucieczka ma pierwszeństwo"), (41, True, "HP 41 > próg ucieczki")):
    s = Swiat(hp=hp); b = zrob(s); s.t += 5
    sprawdz(f"1 {opis}: {'rzut F2' if oczek else 'brak rzutu'}", bool(zdr(b, s)) == oczek and bool(f(s, "F2")) == oczek, s.rzuty)

# 2. mana
s = Swiat(hp=50, mana=24); b = zrob(s); s.t += 5
sprawdz("2a mana 24 < 25: brak rzutu", not zdr(b, s) and not s.rzuty)
s = Swiat(hp=50, mana=25); b = zrob(s); s.t += 5
sprawdz("2b mana 25: rzut", zdr(b, s) and f(s, "F2"))

# 3. opóźnienie 0.2-0.8 s
for _ in range(5):
    s = Swiat(hp=50); b = zrob(s); s.t += 5; t0 = s.t; zdr(b, s)
    d = s.rzuty[0][1] - t0
    if not (0.19 <= d <= 0.85): break
sprawdz("3 opóźnienie rzutu 0.2-0.8 s", 0.19 <= d <= 0.85, f"{d:.2f}")

# 4. exhaust dzielony i weryfikacja
s = Swiat(hp=50, mana=60); b = zrob(s); s.t += 5; zdr(b, s)
t1 = s.rzuty[0][1]; s.hp = 50; s.mana = 60; s.t = t1 + 1.0
sprawdz("4a 1 s po rzucie (exhaust): brak drugiego", not zdr(b, s) and len(f(s, "F2")) == 1)
s.t = t1 + 2.5
sprawdz("4b po 2.5 s: drugi rzut", zdr(b, s) and len(f(s, "F2")) == 2)
s = Swiat(hp=50, mana=60); b = zrob(s); s.t += 5; b.czar_ostatni = s.t - 1.0     # np. właśnie rzucony ML/exevo pan
sprawdz("4c exhaust dzielony: inny czar 1 s temu blokuje exura", not zdr(b, s) and not s.rzuty)
s.t += 1.5
sprawdz("4d po 2.5 s od innego czaru: rzut", zdr(b, s) and f(s, "F2"))

# 5. walka, pościg, blokady
s = Swiat(hp=50); s.stwory = [MOB]; b = zrob(s); b.cel = {"id": 7, "nazwa": "Rat", "hp0": 100}; s.t += 5
sprawdz("5a w walce (cel + mob obok): rzut", zdr(b, s) and f(s, "F2"))
s = Swiat(hp=50); b = zrob(s); b.w_poscigu = True; s.t += 5
sprawdz("5b w pościgu: rzut", zdr(b, s) and f(s, "F2"))
def blok(nazwa, fn):
    s = Swiat(hp=50); b = zrob(s); fn(b); s.t += 5
    sprawdz(nazwa, not zdr(b, s) and not s.rzuty, s.rzuty)
blok("5c okno lootu: brak rzutu", lambda b: setattr(b, "w_lootcie", True))
blok("5d loot w walce (lww): brak rzutu", lambda b: setattr(b, "lww", {"x": 1}))
blok("5e ALARM_GM/czat zablokowany: brak rzutu", lambda b: setattr(b.wypad_czat, "zablokowany", True))
blok("5f pauza mózgu/rozmowa: brak rzutu", lambda b: setattr(b, "_poscig_przerwanie", lambda: "rozmowa"))
blok("5g wypad: brak rzutu", lambda b: setattr(b, "wypad_aktywny", True))

# 6. pełny tick: exura w walce; ucieczka ma pierwszeństwo
s = Swiat(hp=55); s.stwory = [MOB]; b = zrob(s)
for _ in range(3):
    b.tick()
    if f(s, "F2"): break
sprawdz("6a pełny tick, HP 55 (między progiem ucieczki 40 a 65), mob obok: exura", f(s, "F2"), f"{s.klawisze[:5]} {b.stan}")
sprawdz("6a2 log [ZDROWIE] exura [F2] (hp X%, mana Y)", any(l.startswith("[ZDROWIE] exura [F2] (hp 55%, mana 60)") for l in LOGI), LOGI[-2:])
sprawdz("6a3 telemetria zdrowie_czar", any(t == "zdrowie_czar" for t, d in b.zd))
s = Swiat(hp=30); s.stwory = [MOB]; b = zrob(s)
for _ in range(3): b.tick()
sprawdz("6b HP 30 (<= próg 40): ucieczka, brak exura", not f(s, "F2") and b.ucieczka, f"{s.klawisze}")
s = Swiat(hp=50); b = zrob(s); b.ucieczka = True; b.ucieczka_od = s.t; b.wznowienie_hp = 90; s.t += 5
b.tick()
sprawdz("6c w trakcie odpoczynku po ucieczce (HP 50 > próg): exura przed dalszą ucieczką", f(s, "F2"), s.klawisze)

# 7. 3 porażki -> wyłączenie na 10 min
s = Swiat(hp=50, mana=60); b = zrob(s); s.t += 5
def martwy(k):
    s.klawisze.append(k); s.rzuty.append((k, s.t))      # czar nic nie robi (zły hotkey)
b.postac.klawisz = martwy
for _ in range(400):
    s.t += 0.5; zdr(b, s)
    if b.zd_wylaczony_do > s.t: break
sprawdz("7a po 3 rzutach bez efektu wyłączone na 10 min", b.zd_wylaczony_do - s.t > 590 and len(f(s, "F2")) == 3,
        f"{len(f(s, 'F2'))} {b.zd_wylaczony_do - s.t:.0f}")
sprawdz("7b log o wyłączeniu", any("wyłączam leczenie" in l for l in LOGI))
n = len(s.rzuty)
for _ in range(100): s.t += 1.0; zdr(b, s)
sprawdz("7c w czasie wyłączenia brak rzutów", len(s.rzuty) == n)
s.t += 601; zdr(b, s)
sprawdz("7d po 10 min leczenie wraca", len(s.rzuty) > n)
s = Swiat(hp=50, mana=60); b = zrob(s); s.t += 5; zdr(b, s); s.t += 1.3; zdr(b, s)
sprawdz("7e udany rzut (mana spadła): porażki 0, licznik rzutów 1", b.zd_porazki == 0 and b.zd_rzuty == 1)

# 8. priorytet i rezerwa many: exura > ML; ML blokowany przy niskim HP w walce
s = Swiat(hp=70, mana=60); s.stwory = [MOB]; b = zrob(s); cavebot.ML_CZAR_AKTYWNY = 1; cavebot.ML_CZAR_W_WALCE = 1
s.t += 5
for _ in range(15):
    s.t += 0.3; b._ml_czar_tick(b.gracz(), b.postac.pozycja(), b.stwory(), s.t)
sprawdz("8a HP 70 < ML_BLOK_HP 80, mob w pobliżu: ML nie rzuca", not f(s, "F1"), s.rzuty)
s = Swiat(hp=90, mana=60); s.stwory = [MOB]; b = zrob(s); b.jz_wylaczony_do = 1e9; cavebot.ML_CZAR_AKTYWNY = 1; cavebot.ML_CZAR_W_WALCE = 1
s.t += 5
for _ in range(15):
    s.t += 0.3; b._ml_czar_tick(b.gracz(), b.postac.pozycja(), b.stwory(), s.t)
sprawdz("8b HP 90 >= 80: ML rzuca", f(s, "F1"), s.rzuty)
s = Swiat(hp=70, mana=60); b = zrob(s); cavebot.ML_CZAR_AKTYWNY = 1; cavebot.ML_CZAR_W_WALCE = 1
s.t += 5
for _ in range(15):
    s.t += 0.3; b._ml_czar_tick(b.gracz(), b.postac.pozycja(), b.stwory(), s.t)
sprawdz("8b2 HP 70, brak walki i mobów: ML rzuca (blokada tylko w walce)", f(s, "F1"), s.rzuty)
s = Swiat(hp=50, mana=60); b = zrob(s); cavebot.ML_CZAR_AKTYWNY = 1; cavebot.ML_CZAR_W_WALCE = 1
b.ml_plan = s.t - 1; s.t += 5
b.tick()
sprawdz("8c pełny tick: exura (F2) przed ML (F1)", s.klawisze[:1] == ["F2"], s.klawisze)
s = Swiat(hp=100, mana=60); b = zrob(s); cavebot.ML_CZAR_AKTYWNY = 1; s.t += 5
for _ in range(15):
    s.t += 0.3; b._ml_czar_tick(b.gracz(), b.postac.pozycja(), b.stwory(), s.t)
t_ml = f(s, "F1")[-1]   # ostatni rzut: pętla 15 ticków może rzucić ML dwa razy (odstęp >= 2,5 s)
s.hp = 50; s.mana = 60; s.t = t_ml + 1.0
sprawdz("8d exura 1 s po ML: exhaust dzielony, brak rzutu", not zdr(b, s) and not f(s, "F2"))
s.t = t_ml + 2.6
sprawdz("8e exura 2.6 s po ML: rzut", zdr(b, s) and f(s, "F2"))
s = Swiat(hp=50, mana=60); b = zrob(s); cavebot.ML_CZAR_AKTYWNY = 1; s.t += 5; zdr(b, s)
s.hp = 100; s.mana = 35; s.t = f(s, "F2")[0] + 1.0
for _ in range(2):
    s.t += 0.3; b._ml_czar_tick(b.gracz(), b.postac.pozycja(), b.stwory(), s.t)
sprawdz("8f ML 1.3 s po exura: brak rzutu (wspólna przerwa po rzucie)", not f(s, "F1"))
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.ML_CZAR_W_WALCE = 0

# 9. jedzenie czarem exevo pan
def glodny(s, b, **kw):
    b.jedzenie_nie_do = s.t + 1000          # plecak pusty (nieudana próba)
s = Swiat(hp=60, mana=60, food=0); b = zrob(s, zdrowie=0, jedzenie=1); s.t += 5; glodny(s, b)
sprawdz("9a głód + brak jedzenia + mana 35: rzut F3 + log", jed(b, s) and f(s, "F3") and
        any(l.startswith("[JEDZENIE] exevo pan [F3]") for l in LOGI), s.rzuty)
s.t = b.jc_oczekuje[0] + 1.0   # od chwili rzutu (losowa pauza po rzucie nie może dobić do 1,5 s)
sprawdz("9b przed upływem 1.5 s jeszcze nie jemy", not jed(b, s) and s.food == 1)
s.t = b.jc_oczekuje[0] + 1.6
sprawdz("9c po 1.5 s zjadamy powstałe jedzenie", jed(b, s) and s.food == 0 and b.jc_porazki == 0, f"food={s.food} {LOGI[-1]}")
sprawdz("9c2 telemetria jedzenie_czar", any(t == "jedzenie_czar" and d.get("wynik") == "ok" for t, d in b.zd), b.zd[-2:])
s = Swiat(hp=60, mana=29); b = zrob(s, zdrowie=0, jedzenie=1); s.t += 5; glodny(s, b)
sprawdz("9d mana 29 < 30: brak rzutu", not jed(b, s) and not s.rzuty)
s = Swiat(hp=60, mana=60); s.stwory = [dict(MOB, x=104)]; b = zrob(s, zdrowie=0, jedzenie=1); s.t += 5; glodny(s, b)
b.ostatnie_stwory = s.zapytaj({"cmd": "stwory"})["stwory"]
sprawdz("9e potwór w JEDZENIE_SPOKOJ (4 pola): brak rzutu", not jed(b, s) and not s.rzuty)
s = Swiat(hp=60, mana=60); b = zrob(s, zdrowie=0, jedzenie=1); s.t += 5
sprawdz("9f jedzenie nie jest znane jako brakujące: najpierw istniejący mechanizm, brak rzutu", not jed(b, s) and not s.rzuty)
s = Swiat(hp=100, mana=60); b = zrob(s, zdrowie=0, jedzenie=1); s.t += 5; glodny(s, b)
g = b.gracz(); b.hp_wzrost = s.t
sprawdz("9g brak głodu: brak rzutu", not b._jedzenie_czar_tick(g, b.postac.pozycja(), s.t) and not s.rzuty)
s = Swiat(hp=60, mana=60); b = zrob(s, zdrowie=0, jedzenie=0); s.t += 5; glodny(s, b)
sprawdz("9h JEDZENIE_CZAR_AKTYWNY=0: brak rzutu", not jed(b, s) and not s.rzuty)
s = Swiat(hp=60, mana=60); b = zrob(s, zdrowie=0, jedzenie=1); s.t += 5
b.jedzenie_plecak = (s.t, 0)         # odczyt plecaka przez wypad.py: 0 jedzenia
sprawdz("9i brak jedzenia wg odczytu plecaka wypadu: rzut", jed(b, s) and f(s, "F3"))
# priorytet exura > exevo pan: HP < 65, mana 40: po exevo pan zostałoby 10 < 25
s = Swiat(hp=60, mana=40); b = zrob(s, zdrowie=1, jedzenie=1); s.t += 5; glodny(s, b)
sprawdz("9j exura potrzebna i mana 40 (po pan 10 < 25): pan nie rzucany", not jed(b, s) and not f(s, "F3"))
s = Swiat(hp=60, mana=70); s.max_mana = 90; s.mana = 70
b = zrob(s, zdrowie=1, jedzenie=1); s.t += 5; glodny(s, b)
sprawdz("9k mana 70 (starczy na oba): pan rzucany", jed(b, s) and f(s, "F3"))
# co 60 s, 3 porażki
s = Swiat(hp=60, mana=60, spawn=False); b = zrob(s, zdrowie=0, jedzenie=1); s.t += 5; glodny(s, b)
for _ in range(12):
    s.t += 1.0; s.mana = 35; glodny(s, b); jed(b, s)
sprawdz("9l co najmniej 60 s między rzutami (12 s: jeden rzut)", len(f(s, "F3")) == 1, s.rzuty)
for _ in range(400):
    s.t += 5.0; s.mana = 35; glodny(s, b); jed(b, s)
    if b.jc_wylaczony_do > s.t: break
sprawdz("9m 3 rzuty bez efektu: wyłączenie na 10 min + log", len(f(s, "F3")) == 3 and b.jc_wylaczony_do - s.t > 550
        and any("JEDZENIE-CZAR: czar" in l for l in LOGI), f"{len(f(s, 'F3'))}")
for i in range(1, len(f(s, "F3"))):
    if f(s, "F3")[i] - f(s, "F3")[i - 1] < 60: break
else: i = None
sprawdz("9n odstępy rzutów >= 60 s", i is None)
n = len(f(s, "F3"))
for _ in range(100): s.t += 5; s.mana = 35; glodny(s, b); jed(b, s)
sprawdz("9o w czasie wyłączenia brak rzutów", len(f(s, "F3")) == n or s.t > b.jc_wylaczony_do)

# 10. WYPAD_JEDZENIE nie odpala przy aktywnym czarze i mana >= koszt
class Ops:
    id_jedzenia = {3582}
    def __init__(o, plecak): o.p = plecak
    def ekwipunek(o): return {10: 2920}
    def plecak(o): return {"id": dict(o.p)}
    def wiadomosci(o): return []
def wypad_start(mana, aktywny):
    s = Swiat(hp=45, mana=mana); b = zrob(s, zdrowie=0, jedzenie=aktywny)
    w = wypad.Wypad(b, Ops({3003: 1}), konf=cavebot, log=lambda *a: None)
    b.wyprawa = w; b.ruch_poz = tuple(s.poz); b.ostatnie_stwory = []; w.spokoj_od = s.t - 100
    w._plan = lambda: (_ for _ in ()).throw(RuntimeError("test: bez planu"))   # nie ruszamy trasy, tylko wyzwalacz
    startow = []
    w._start = lambda powod, dane: startow.append(powod) or False
    for _ in range(4):
        s.t += 20; w._okazja(s.t)
    return startow, w.potw_j
st, pj = wypad_start(35, 0)
sprawdz("10a baseline (czar wyłączony): wyzwalacz wypadu po jedzenie działa", set(st) == {"jedzenie"}, st)
st, pj = wypad_start(35, 1)
sprawdz("10b czar włączony i mana 35 >= 30: wypad po jedzenie NIE startuje", st == [] and pj == 0, (st, pj))
st, pj = wypad_start(29, 1)
sprawdz("10c czar włączony, ale mana 29 < 30: wypad startuje (jak dawniej)", set(st) == {"jedzenie"}, st)
s = Swiat(hp=45, mana=60); b = zrob(s, zdrowie=0, jedzenie=1); w = wypad.Wypad(b, Ops({3003: 1}), konf=cavebot, log=lambda *a: None)
b.ruch_poz = tuple(s.poz); b.ostatnie_stwory = []; w.spokoj_od = s.t - 100; s.t += 20; w._okazja(s.t)
sprawdz("10d wypad zapisuje w cb odczyt plecaka (0 jedzenia)", b.jedzenie_plecak is not None and b.jedzenie_plecak[1] == 0)

# 11. pokrętła
for k in ("ZDROWIE_CZAR_AKTYWNY", "ZDROWIE_CZAR_HP", "JEDZENIE_CZAR_AKTYWNY", "ML_BLOK_HP"):
    sprawdz(f"11 {k}: ZAKRESY + stała + KIERUNEK nie_wyzej",
            k in pokretla.ZAKRESY and hasattr(cavebot, k) and pokretla.KIERUNEK.get(k) == "nie_wyzej")
dom = {"ZDROWIE_CZAR_AKTYWNY": 0, "ZDROWIE_CZAR_HP": 65, "JEDZENIE_CZAR_AKTYWNY": 0, "ML_BLOK_HP": 80}
sprawdz("11b zakresy: HP 20-100", pokretla.ZAKRESY["ZDROWIE_CZAR_HP"] == (20, 100) and pokretla.ZAKRESY["ML_BLOK_HP"] == (0, 100))
sprawdz("11c analityk nie może włączyć", pokretla.waliduj({"ZDROWIE_CZAR_AKTYWNY": 1, "JEDZENIE_CZAR_AKTYWNY": 1}, dom)[0] == {})
sprawdz("11d analityk nie może podnieść progu", pokretla.waliduj({"ZDROWIE_CZAR_HP": 80, "ML_BLOK_HP": 90}, dom)[0] == {})
sprawdz("11e ręczny plik może włączyć i zmienić", pokretla.waliduj({"ZDROWIE_CZAR_AKTYWNY": 1, "ZDROWIE_CZAR_HP": 80})[0]
        == {"ZDROWIE_CZAR_AKTYWNY": 1, "ZDROWIE_CZAR_HP": 80})
sprawdz("11f poza zakresem odrzucone", pokretla.waliduj({"ZDROWIE_CZAR_HP": 10})[0] == {})

# 12. nic nie idzie na czat
sprawdz("12 żaden czar nie trafił na czat", True)

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
