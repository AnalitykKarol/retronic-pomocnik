import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot, pokretla

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False
cavebot.ML_CZAR_OPOZNIENIE = (0.3, 1.5)
cavebot.ML_CZAR_DLUGA_SZANSA = 0.0
cavebot.ML_CZAR_EXTRA_PRZERWA = (0.0, 0.0)
cavebot.ML_CZAR_ZAPAS_MANY = (0, 0)
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Swiat:
    def __init__(s, mana=35, spada=True):
        s.t = 0.0; s.poz = [100, 100, 7]; s.mana = mana; s.max_mana = 35
        s.stwory = []; s.wyslane = []; s.spada = spada; s.klawisze = []; s.chat = []
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": s.mana, "max_mana": s.max_mana}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}
    def wyslij(s, tekst):          # czat: czar NIE może tędy iść
        s.chat.append(tekst)

class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k):
        p.s.klawisze.append(k)
        if k == cavebot.ML_CZAR_KLAWISZ:
            p.s.wyslane.append((k, p.s.t))
            if p.s.spada: p.s.mana = max(0, p.s.mana - 20)
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2
        p.s.poz[0] += d[0]; p.s.poz[1] += d[1]
        return tuple(p.s.poz)

def zrob(s, aktywny=1, **kw):
    cavebot.ML_CZAR_AKTYWNY = aktywny
    cavebot.ML_CZAR_W_WALCE = 0
    cavebot.ML_CZAR_MIN_PRZERWA_S = 2.5
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=types.SimpleNamespace(zbierz=lambda z, g: "ok"), okrazenia=1, **kw)
    b.wypad_wyslij = s.wyslij
    b.wypad_czat = types.SimpleNamespace(zablokowany=False, wyslano=lambda t: None)
    b.przerwa_od = float("inf")
    return b

def ml(b, s):
    """Jedno wywołanie logiki rzutu z aktualnym odczytem."""
    g = b.gracz(); poz = b.postac.pozycja(); lista = b.stwory()
    return b._ml_czar_tick(g, poz, lista, s.t)

def cykl(b, s, n=30, krok=0.3):
    for _ in range(n):
        s.t += krok
        ml(b, s)

# 1. domyślnie wyłączone (stała i brak rzutu)
sprawdz("1a domyślnie ML_CZAR_AKTYWNY=0 w pliku (stała)", _l0 is not None and
        open(_os.path.join(_os.path.dirname(cavebot.__file__), "cavebot.py")).read().count("ML_CZAR_AKTYWNY = 0") == 1)
s = Swiat(); b = zrob(s, aktywny=0); cykl(b, s)
sprawdz("1b wyłączone: brak rzutów", not s.wyslane)

# 2. warunki: mana >= koszt, rzut z losowym opóźnieniem 0.3-1.5 s
s = Swiat(mana=19); b = zrob(s); cykl(b, s, 10)
sprawdz("2a mana 19 < 20: brak rzutu", not s.wyslane)
s = Swiat(mana=35); b = zrob(s)
t0 = s.t; ml(b, s)
sprawdz("2b pierwszy obieg tylko planuje (opóźnienie)", not s.wyslane and b.ml_plan is not None)
plan = b.ml_plan - t0
sprawdz("2c opóźnienie w 0.3-1.5 s", 0.3 <= plan <= 1.6, f"{plan:.2f}")
cykl(b, s, 8)
sprawdz("2d rzut naciśnięciem F1", s.wyslane and s.wyslane[0][0] == "F1" and s.klawisze == ["F1"], s.wyslane)
sprawdz("2d2 nic nie trafia na czat", s.chat == [])
sprawdz("2d3 stała ML_CZAR_KLAWISZ = F1", cavebot.ML_CZAR_KLAWISZ == "F1")
t_rzut = s.wyslane[0][1]
cykl(b, s, 4)       # mana 15 < 20, weryfikacja
sprawdz("2e weryfikacja: mana spadła, licznik rzutów i wydanej many", b.ml_rzuty == 1 and b.ml_mana_wydana == 20 and b.ml_porazki == 0,
        f"{b.ml_rzuty} {b.ml_mana_wydana}")

# 3. exhaust i max 1 rzut / 2.5 s
s = Swiat(mana=35, spada=False); b = zrob(s)
cavebot.ML_CZAR_MIN_PRZERWA_S = 0.5      # i tak min 2.5 s
cykl(b, s, 40, krok=0.1)                  # 4 s
czasy = [t for _, t in s.wyslane]
sprawdz("3a max 1 rzut na 2.5 s (odstępy >= 2.5 s, bez spadku many)", len(czasy) >= 2 and all(b_ - a_ >= 2.5 for a_, b_ in zip(czasy, czasy[1:])), czasy)
cavebot.ML_CZAR_MIN_PRZERWA_S = 2.5
s = Swiat(mana=35); b = zrob(s); b.ml_ostatni = s.t - 1.0
cykl(b, s, 2, krok=0.3)
sprawdz("3b exhaust (rzut 1 s temu): brak rzutu", not s.wyslane)

# 4. brak rzutu w walce / z żywym mobem; z W_WALCE=1 rzuca
mob = {"id": 7, "nazwa": "Rat", "gracz": False, "x": 102, "y": 100, "z": 7, "hp": 100}
s = Swiat(mana=35); s.stwory = [mob]; b = zrob(s); cykl(b, s, 15)
sprawdz("4a żywy mob w pobliżu: brak rzutu", not s.wyslane)
s = Swiat(mana=35); b = zrob(s); b.cel = {"id": 7, "nazwa": "Rat", "hp0": 100}; cykl(b, s, 15)
sprawdz("4b trwa cel/walka: brak rzutu", not s.wyslane)
s = Swiat(mana=35); b = zrob(s); b.w_poscigu = True; cykl(b, s, 15)
sprawdz("4c pościg: brak rzutu", not s.wyslane)
s = Swiat(mana=35); s.stwory = [mob]; b = zrob(s); cavebot.ML_CZAR_W_WALCE = 1; cykl(b, s, 15)
sprawdz("4d ML_CZAR_W_WALCE=1 z mobem: rzuca", s.wyslane)
cavebot.ML_CZAR_W_WALCE = 0

# 5. blokada czatu / pauza / rozmowa / loot / wypad / ucieczka
def blok(nazwa, fn):
    s = Swiat(mana=35); b = zrob(s); fn(b); cykl(b, s, 15)
    sprawdz(nazwa, not s.wyslane, s.wyslane)
blok("5a ALARM_GM (czat zablokowany): brak rzutu", lambda b: setattr(b.wypad_czat, "zablokowany", True))
blok("5b pauza_bota/rozmowa (_poscig_przerwanie): brak rzutu", lambda b: setattr(b, "_poscig_przerwanie", lambda: "rozmowa"))
blok("5c okno lootu: brak rzutu", lambda b: setattr(b, "w_lootcie", True))
blok("5d wypad (NPC): brak rzutu", lambda b: setattr(b, "wypad_aktywny", True))
blok("5e ucieczka: brak rzutu", lambda b: setattr(b, "ucieczka", True))
s = Swiat(mana=35); b = zrob(s); b.wypad_wyslij = None; cykl(b, s, 15)
sprawdz("5f brak funkcji czatu nie blokuje rzutu F1", s.wyslane and s.wyslane[0][0] == "F1")
blok("5g stan POCHODNIA: brak rzutu", lambda b: setattr(b, "stan", "POCHODNIA"))

# 6. rzuca w stanie PRZERWA i w IDZ (w pełnym ticku)
s = Swiat(mana=35); b = zrob(s); b.przerwa_od = 0.0
for _ in range(60):
    if not b.tick(): break
    if s.wyslane: break
sprawdz("6a rzut w pełnym ticku podczas PRZERWA", s.wyslane and str(b.stan) in ("ML", "PRZERWA"), f"{b.stan} {s.wyslane}")
s = Swiat(mana=35); b = zrob(s)
for _ in range(60):
    if not b.tick(): break
    if s.wyslane: break
sprawdz("6b rzut w pełnym ticku podczas patrolu/IDZ", s.wyslane, f"{b.stan}")

# 7. 3 porażki z rzędu: wyłączenie na 10 min
s = Swiat(mana=35, spada=False); b = zrob(s)
for _ in range(400):
    s.t += 0.3; ml(b, s)
    if b.ml_wylaczony_do > s.t: break
sprawdz("7a po 3 rzutach bez spadku many wyłączone na 10 min", b.ml_wylaczony_do - s.t > 590 and len(s.wyslane) == 3,
        f"rzutów {len(s.wyslane)} do={b.ml_wylaczony_do - s.t:.0f}")
n = len(s.wyslane); cykl(b, s, 100, krok=1.0)     # 100 s
sprawdz("7b w czasie wyłączenia brak rzutów", len(s.wyslane) == n)
s.t += 601; cykl(b, s, 10)
sprawdz("7c po 10 min rzucanie wraca", len(s.wyslane) > n)
sprawdz("7d log o wyłączeniu", any("wyłączam rzucanie" in l for l in LOGI))

# 8. log co 10 rzutów + telemetria
s = Swiat(mana=35); b = zrob(s); zd = []
b.tele = types.SimpleNamespace(zdarzenie=lambda typ, **d: zd.append((typ, d)))
LOGI.clear()
for _ in range(2000):
    s.t += 0.5
    s.mana = min(35, s.mana + 20 if s.t % 20 < 0.5 else s.mana)   # regeneracja co 20 s
    ml(b, s)
    if b.ml_rzuty >= 10: break
sprawdz("8a log 'ML: rzucono 10, many wydane 200'", any("ML: rzucono 10, many wydane 200" in l for l in LOGI), LOGI[-3:])
sprawdz("8b zdarzenia ml_czar w telemetrii", len([z for z in zd if z[0] == "ml_czar" and z[1].get("wynik") == "ok"]) == 10)

# 9. pokrętła
for k in ("ML_CZAR_AKTYWNY", "ML_CZAR_KOSZT", "ML_CZAR_MIN_PRZERWA_S", "ML_CZAR_W_WALCE"):
    sprawdz(f"9 {k} w ZAKRESY i stała w cavebot", k in pokretla.ZAKRESY and hasattr(cavebot, k))
sprawdz("9e analityk nie może włączyć", pokretla.waliduj({"ML_CZAR_AKTYWNY": 1}, {"ML_CZAR_AKTYWNY": 0})[0] == {})
sprawdz("9f ręczny plik może włączyć", pokretla.waliduj({"ML_CZAR_AKTYWNY": 1})[0] == {"ML_CZAR_AKTYWNY": 1})

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
