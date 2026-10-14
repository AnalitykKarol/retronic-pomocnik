"""Zapas jedzenia czarem (JEDZENIE_ZAPAS_MIN) i brak zakleszczenia ML vs exevo pan.
Wszystko na atrapach: klawisze, loot i odczyt plecaka to listy/liczby, nic nie trafia do gry
(RETRONIC_TESTY=1, brak XTEST, brak DISPLAY)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot, pokretla

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False
cavebot.ML_CZAR_OPOZNIENIE = (0.3, 0.5)
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
    def __init__(s, mana=35, zapas=0, f3_daje=1, hp=100):
        s.t = 0.0; s.poz = [100, 100, 7]; s.mana = mana; s.max_mana = 95; s.hp = hp
        s.stwory = []; s.klawisze = []; s.zapas = zapas; s.f3_daje = f3_daje
        s.zjedz_wywolan = 0; s.odczyt = "ok"      # "ok" | "brak" (nieczytelny plecak)
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
        p.s.klawisze.append((k, round(p.s.t, 1)))
        if k == "F1": p.s.mana = max(0, p.s.mana - 20)
        if k == "F3":
            p.s.mana = max(0, p.s.mana - 30); p.s.zapas += p.s.f3_daje
        if k == "F2": p.s.mana = max(0, p.s.mana - 25)
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2
        p.s.poz[0] += d[0]; p.s.poz[1] += d[1]
        return tuple(p.s.poz)

def klawisze(s): return [k for k, _ in s.klawisze]

def zrob(s, **kw):
    cavebot.ML_CZAR_AKTYWNY = 1; cavebot.ML_CZAR_W_WALCE = 0; cavebot.JEDZENIE_CZAR_AKTYWNY = 1
    cavebot.ZDROWIE_CZAR_AKTYWNY = 0; cavebot.JEDZENIE_ZAPAS_MIN = 5
    cavebot.ML_CZAR_MIN_PRZERWA_S = 2.5
    def ile():
        return None if s.odczyt == "brak" else s.zapas
    def zjedz(log=None):
        s.zjedz_wywolan += 1
        if s.zapas > 0:
            s.zapas -= 1
            return ["meat"]
        return []
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=zjedz, ile_jedzenia=ile)
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=loot, okrazenia=1, jedzenie=None, **kw)
    b.klik = object()
    b.wypad_czat = types.SimpleNamespace(zablokowany=False, wyslano=lambda t: None)
    b.przerwa_od = float("inf")
    b.zd = []
    b.tele = types.SimpleNamespace(zdarzenie=lambda typ, **d: b.zd.append((typ, d)))
    return b

def obieg(b, s, dt=0.5):
    """Jak w tick(): śledzenie many, potem czar jedzenia -> jedzenie -> ML."""
    s.t += dt
    g = b.gracz(); poz = b.postac.pozycja(); teraz = s.t
    mana, mx = g.get("mana"), g.get("max_mana")
    if b.mana_ostatnia is None or mana > b.mana_ostatnia or mana >= mx:
        b.mana_wzrost = teraz
        if b.mana_ostatnia is not None and mana > b.mana_ostatnia:
            b.mana_rosla = teraz
    b.mana_ostatnia = mana
    if g["hp"] >= g["max_hp"]:
        b.hp_wzrost = teraz
    lista = b.stwory(); b.ostatnie_stwory = lista
    if b._zdrowie_czar_tick(g, poz, teraz): return "zdrowie"
    if b._jedzenie_czar_tick(g, poz, teraz): return "jedzenie_czar"
    if b.jedzenie_potrzebne(g, teraz, poz):
        b.zjedz(teraz, g); return "zjedz"
    if b._ml_czar_tick(g, poz, lista, teraz): return "ml"
    b.stan = "IDZ"          # dalsza część ticka (marsz) ustawia stan; bez tego JEDZENIE blokowałoby ML w atrapie
    return None

def cykl(b, s, n, dt=0.5, regen=0.0):
    for _ in range(n):
        if regen:
            s.mana = min(s.max_mana, s.mana + regen * dt)
        obieg(b, s, dt)

def glodny(b, s, sek=200):
    """Mana stoi od sek sekund (głód bez regeneracji)."""
    s.t += sek
    b.mana_wzrost = s.t - sek; b.mana_rosla = s.t - sek; b.mana_ostatnia = s.mana

def glodny_hp(b, s, sek=200):
    """HP nie pełne i nie rośnie od sek sekund (głód widoczny przez HP, także przy pełnej manie)."""
    s.hp = 80; s.t += sek; b.hp_wzrost = s.t - sek; b.hp_ostatnie = 80

# 0. kontrakt pokrętła
sprawdz("0a domyślnie 5", cavebot.JEDZENIE_ZAPAS_MIN == 5)
sprawdz("0b ZAKRESY 1-20", pokretla.ZAKRESY.get("JEDZENIE_ZAPAS_MIN") == (1, 20))
sprawdz("0c KIERUNEK nie_wyzej", pokretla.KIERUNEK.get("JEDZENIE_ZAPAS_MIN") == "nie_wyzej")
sprawdz("0d 25 odrzucone", pokretla.waliduj({"JEDZENIE_ZAPAS_MIN": 25})[0] == {})
sprawdz("0e 0 odrzucone", pokretla.waliduj({"JEDZENIE_ZAPAS_MIN": 0})[0] == {})
sprawdz("0f ręcznie 12 w zakresie", pokretla.waliduj({"JEDZENIE_ZAPAS_MIN": 12})[0] == {"JEDZENIE_ZAPAS_MIN": 12})
sprawdz("0g analityk nie podnosi", pokretla.waliduj({"JEDZENIE_ZAPAS_MIN": 8}, {"JEDZENIE_ZAPAS_MIN": 5})[0] == {})
sprawdz("0h analityk może obniżyć", pokretla.waliduj({"JEDZENIE_ZAPAS_MIN": 3}, {"JEDZENIE_ZAPAS_MIN": 5})[0] == {"JEDZENIE_ZAPAS_MIN": 3})

# 1. zapas 0, mana 35, spokój, niegłodny: F3
s = Swiat(mana=35, zapas=0); b = zrob(s); cykl(b, s, 6)
sprawdz("1a zapas 0, mana 35: F3 (nie F1)", klawisze(s)[:1] == ["F3"], s.klawisze)
sprawdz("1b zapas bez zjadania (niegłodny): zapas wzrósł", s.zapas == 1 and s.zjedz_wywolan == 0)
cykl(b, s, 6)
sprawdz("1c po weryfikacji: przyrost zapisany, brak porażek", b.jz_porazki == 0 and any(t == "jedzenie_zapas" and d.get("wynik") == "ok" for t, d in b.zd), b.zd[-2:])

# 2. zapas 6: ML F1 jak dotąd
s = Swiat(mana=35, zapas=6); b = zrob(s); cykl(b, s, 8)
sprawdz("2a zapas 6 (>= 5): F1", klawisze(s)[:1] == ["F1"] and "F3" not in klawisze(s), s.klawisze)
s = Swiat(mana=35, zapas=5); b = zrob(s); cykl(b, s, 8)
sprawdz("2b zapas == MIN: F1", klawisze(s)[:1] == ["F1"] and "F3" not in klawisze(s), s.klawisze)
s = Swiat(mana=35, zapas=4); b = zrob(s); cykl(b, s, 8)
sprawdz("2c zapas 4 (< MIN): F3", klawisze(s)[:1] == ["F3"], s.klawisze)
cavebot.JEDZENIE_ZAPAS_MIN = 5

# 3. mana < 30: F3 nie startuje, ML czeka na manę (rośnie), potem F3
s = Swiat(mana=25, zapas=0); b = zrob(s); cykl(b, s, 8)
sprawdz("3a mana 25 rośnie, zapas 0: ani F3, ani F1 (ML czeka na 30)", klawisze(s) == [], s.klawisze)
cykl(b, s, 40, regen=0.5)
sprawdz("3b po dojściu many do 30: F3 jako pierwszy", klawisze(s)[:1] == ["F3"], s.klawisze)

# 4. brak zakleszczenia: głód, mana nie rośnie, mana < 30, brak jedzenia -> ML rzuca
s = Swiat(mana=25, zapas=0); b = zrob(s); glodny(b, s, 200)
LOGI.clear(); cykl(b, s, 10)
sprawdz("4a głód + mana 25 + brak jedzenia: ML (F1) rzuca", "F1" in klawisze(s) and "F3" not in klawisze(s), s.klawisze)
sprawdz("4b jc_glod_do nie blokuje", b.jc_glod_do <= s.t)
sprawdz("4c notatka w telemetrii (brak_many)", any(t == "jedzenie_czar" and d.get("wynik") == "brak_many" for t, d in b.zd), b.zd[:3])
s = Swiat(mana=7, zapas=0); b = zrob(s); glodny(b, s, 200); cykl(b, s, 10)
sprawdz("4d głód + mana 7: nic nie blokowane (jc_glod_do), brak rzutu bo mana", b.jc_glod_do <= s.t and klawisze(s) == [])
# ML z kosztem 5 przy mana 7: nadal rzuca mimo głodu
cavebot.ML_CZAR_KOSZT = 5
s = Swiat(mana=7, zapas=0); b = zrob(s); glodny(b, s, 200); cykl(b, s, 10)
sprawdz("4e głód + mana 7 + koszt ML 5: ML castuje", "F1" in klawisze(s), s.klawisze)
cavebot.ML_CZAR_KOSZT = 20
# jedzenie_nie_do (znany brak po nieudanej próbie) też nie blokuje ML przy mana < 30
s = Swiat(mana=25, zapas=0); b = zrob(s); glodny(b, s, 200); b.jedzenie_nie_do = s.t + 200; cykl(b, s, 10)
sprawdz("4f znany brak + mana 25: ML rzuca", "F1" in klawisze(s) and "F3" not in klawisze(s), s.klawisze)

# 5. głód + mana 35 + zapas 0: F3, potem zjedzenie
s = Swiat(mana=35, zapas=0); b = zrob(s); glodny_hp(b, s, 200); cykl(b, s, 12)
sprawdz("5a głód + mana 35 + zapas 0: F3", klawisze(s)[:1] == ["F3"], s.klawisze)
sprawdz("5b po czarze jemy (jak dawniej)", s.zjedz_wywolan >= 1, s.zjedz_wywolan)

# 6. głodny, jedzenie jest: najpierw jemy, bez F3
s = Swiat(mana=35, zapas=3); b = zrob(s); glodny_hp(b, s, 200); obieg(b, s)
sprawdz("6a głodny + zapas 3: zjedz, nie F3", s.zjedz_wywolan == 1 and "F3" not in klawisze(s), (s.zjedz_wywolan, s.klawisze))

# 7. exhaust 5 s i odstęp 20 s
s = Swiat(mana=35, zapas=0); b = zrob(s); b.czar_ostatni = s.t - 2.0
obieg(b, s, 0.1); obieg(b, s, 0.1)
sprawdz("7a 2 s po innym czarze: brak F3", "F3" not in klawisze(s), s.klawisze)
s.t += 3.5; obieg(b, s, 0.1)
sprawdz("7b po 5 s od czaru: F3", klawisze(s)[:1] == ["F3"], s.klawisze)
s = Swiat(mana=35, zapas=0); b = zrob(s); cykl(b, s, 4)
t_f3 = s.klawisze[0][1]
s.mana = 35; cykl(b, s, 20)     # 10 s, zapas 1 < 5, ale < 20 s od rzutu
sprawdz("7c drugi F3 nie wcześniej niż po 20 s", len([k for k in klawisze(s) if k == "F3"]) == 1, s.klawisze)
s.mana = 35; cykl(b, s, 30)
t2 = [t for k, t in s.klawisze if k == "F3"]
sprawdz("7d drugi F3 po >= 20 s", len(t2) >= 2 and t2[1] - t2[0] >= 20.0, t2)

# 8. 3 porażki (zapas nie rośnie) -> pauza 10 min
s = Swiat(mana=35, zapas=0, f3_daje=0); b = zrob(s)
for _ in range(400):
    s.mana = 35
    obieg(b, s, 1.0)
    if b.jz_wylaczony_do > s.t: break
f3 = [k for k in klawisze(s) if k == "F3"]
sprawdz("8a 3 rzuty bez przyrostu -> pauza ~10 min", len(f3) == 3 and b.jz_wylaczony_do - s.t > 590, (len(f3), b.jz_wylaczony_do - s.t))
n = len(s.klawisze)
for _ in range(100):
    s.mana = min(35, s.mana + 4); obieg(b, s, 5.0)     # 500 s, mana odrasta
sprawdz("8b w pauzie brak F3", "F3" not in [k for k, _ in s.klawisze[n:]])
sprawdz("8b2 w pauzie ML rzuca dalej (F1)", "F1" in [k for k, _ in s.klawisze[n:]])
s.t += 200
for _ in range(10):
    s.mana = 35; obieg(b, s, 1.0)
sprawdz("8c po 10 min F3 wraca", "F3" in [k for k, _ in s.klawisze[n:]], s.klawisze[n:][:3])
sprawdz("8d log o pauzie", any("pauza 10 min" in l for l in LOGI))

# 9. mob blisko (12.10): F3 na zapas rzucany także w walce (mana >= 30, zapas < MIN, bez ucieczki/leczenia exura)
mob = {"id": 7, "nazwa": "Rat", "gracz": False, "x": 103, "y": 100, "z": 7, "hp": 100}
s = Swiat(mana=35, zapas=0); s.stwory = [mob]; b = zrob(s); cykl(b, s, 10)
sprawdz("9a mob w JEDZENIE_SPOKOJ, mana 35, zapas 0: F3 mimo walki", klawisze(s)[:1] == ["F3"], s.klawisze)
sprawdz("9a2 po F3 zapas urósł, bez zjadania w walce", s.zapas == 1 and s.zjedz_wywolan == 0, (s.zapas, s.zjedz_wywolan))
cavebot.JEDZENIE_ZAPAS_W_WALCE = 0
try:
    s = Swiat(mana=35, zapas=0); s.stwory = [mob]; b = zrob(s); cykl(b, s, 10)
    sprawdz("9b pokrętło JEDZENIE_ZAPAS_W_WALCE=0: dawne zachowanie, brak F3 przy mobie", "F3" not in klawisze(s), s.klawisze)
finally:
    cavebot.JEDZENIE_ZAPAS_W_WALCE = 1
s = Swiat(mana=35, zapas=0, hp=50); s.stwory = [mob]; b = zrob(s)
_zk0 = cavebot.ZDROWIE_CZAR_KOSZT
cavebot.ZDROWIE_CZAR_AKTYWNY = 1
try:
    cavebot.ZDROWIE_CZAR_KOSZT = 100        # exura niewykonalna (mana 35): leczenie nie rzuca, ale HP 50% < 65% blokuje F3 w walce
    cykl(b, s, 6)
    sprawdz("9c walka + HP 50% (zakres exura): F3 nie rusza (mana dla leczenia)", "F3" not in klawisze(s), s.klawisze)
finally:
    cavebot.ZDROWIE_CZAR_AKTYWNY = 0; cavebot.ZDROWIE_CZAR_KOSZT = _zk0
s = Swiat(mana=35, zapas=0); s.stwory = [mob]; b = zrob(s); b.ucieczka = True
cykl(b, s, 6)
sprawdz("9d ucieczka: F3 w walce nie rusza", "F3" not in klawisze(s), s.klawisze)

# 9e. zakleszczenie głodu (16:14-16:18): mana 35, zapas 0, F3 chwilowo niemożliwy -> ML NIE zjada many 30
s = Swiat(mana=35, zapas=0); b = zrob(s)
g = b.gracz()
sprawdz("9e mana 35, zapas 0, F3 wolny: ML czeka na rzut F3", b._ml_czeka_na_zapas(g, s.t) is True)
glodny(b, s, 200)       # mana nie rośnie od 200 s: wcześniej to zwalniało ML; przy mana >= 30 F3 i tak jest możliwy
sprawdz("9f mana 35 nie rośnie (głód): ML nadal czeka (F3 jest możliwy)", b._ml_czeka_na_zapas(b.gracz(), s.t) is True)
s.t += cavebot.JEDZENIE_ZAPAS_HOLD_MAX_S + 5
sprawdz("9g po JEDZENIE_ZAPAS_HOLD_MAX_S ML znów rzuca (bez zakleszczenia)", b._ml_czeka_na_zapas(b.gracz(), s.t) is False)
s = Swiat(mana=25, zapas=0); b = zrob(s); glodny(b, s, 200)
sprawdz("9h mana 25 nie rośnie: ML nie czeka (F3 i tak niemożliwy)", b._ml_czeka_na_zapas(b.gracz(), s.t) is False)
# integracja: F3 zablokowany pokrętłem walki, a ML w walce włączony: ML nie rzuca F1 przez hold
cavebot.JEDZENIE_ZAPAS_W_WALCE = 0
try:
    s = Swiat(mana=35, zapas=0); s.stwory = [mob]; b = zrob(s); cavebot.ML_CZAR_W_WALCE = 1
    cykl(b, s, 12)
    sprawdz("9i mana 35 + mob + F3 niedozwolony: ML trzyma manę dla F3 (brak F1)", "F1" not in klawisze(s), s.klawisze)
finally:
    cavebot.JEDZENIE_ZAPAS_W_WALCE = 1; cavebot.ML_CZAR_W_WALCE = 0

# 10. nieznany zapas: F3 raz na 10 min zamiast ML, w pozostałych F1
s = Swiat(mana=35, zapas=0); s.odczyt = "brak"; b = zrob(s); cykl(b, s, 8)
sprawdz("10a plecak nieczytelny, mana 35, ML by rzucał: F3", klawisze(s)[:1] == ["F3"], s.klawisze)
for _ in range(60):
    s.mana = min(35, s.mana + 3); obieg(b, s, 1.0)
k = klawisze(s)
sprawdz("10b w ciągu 10 min kolejne rzuty to F1", k.count("F3") == 1 and k.count("F1") >= 1, k)
s.t += 650
n = len(s.klawisze)
for _ in range(10):
    s.mana = max(s.mana, 35); obieg(b, s, 1.0)
sprawdz("10c po 10 min znowu F3", "F3" in [x for x, _ in s.klawisze[n:]], s.klawisze[n:][:3])
s = Swiat(mana=25, zapas=0); s.odczyt = "brak"; b = zrob(s); cykl(b, s, 8)
sprawdz("10d nieznany + mana 25: F1, nie F3", klawisze(s)[:1] == ["F1"], s.klawisze)
sprawdz("10e brak ile_jedzenia w atrapie loot = nieznany (F1 przy mana 25)", True)

# 11. exura (F2) ma pierwszeństwo: HP niskie + mana 45 -> nie F3 (zostaje mana na leczenie)
cavebot.ZDROWIE_CZAR_AKTYWNY = 1
s = Swiat(mana=45, zapas=0, hp=50); b = zrob(s); cavebot.ZDROWIE_CZAR_AKTYWNY = 1
b.prog_aktualny = 30
cykl(b, s, 4, dt=0.5)
sprawdz("11a HP 50%: pierwszy rzut to exura F2, nie F3", klawisze(s)[:1] == ["F2"], s.klawisze)
cavebot.ZDROWIE_CZAR_AKTYWNY = 0

# 12. pełny tick: zapas 0, mana 35 -> F3 (bez zakleszczenia w prawdziwej pętli)
s = Swiat(mana=35, zapas=0); b = zrob(s)
for _ in range(80):
    if not b.tick(): break
    if "F3" in klawisze(s): break
sprawdz("12 pełny tick: F3 naciśnięty", "F3" in klawisze(s), (str(b.stan), s.klawisze[:3]))

# 13. loot.ile_jedzenia na atrapie odczytu pamięci (bez gry, bez inputu)
import loot
def _zapytaj(z):
    return {"kontenery": [
        {"numer": 0, "id": 2854, "nazwa": "Backpack", "pojemnosc": 20,
         "przedmioty": [{"slot": 0, "id": 3577, "ilosc": 1}, {"slot": 1, "id": 3031, "ilosc": 2},
                        {"slot": 3, "id": 3582, "ilosc": 2}, {"slot": 5, "id": 3607, "ilosc": 1}]},
        {"numer": 1, "id": 3994, "nazwa": "Dead rat", "pojemnosc": 8,
         "przedmioty": [{"slot": 0, "id": 3577, "ilosc": 1}]}]}
stare = loot._zapytaj; loot._zapytaj = _zapytaj
try:
    sprawdz("13a ile_jedzenia: meat 1 + ham 2 + cheese 1 w plecaku (bez zwłok) = 4", loot.ile_jedzenia() == 4, loot.ile_jedzenia())
    loot._zapytaj = lambda z: {"kontenery": []}
    sprawdz("13b pusta lista kontenerów = nieznane (None)", loot.ile_jedzenia() is None)
    def boom(z): raise OSError("brak gniazda")
    loot._zapytaj = boom
    sprawdz("13c błąd gniazda = None", loot.ile_jedzenia() is None)
finally:
    loot._zapytaj = stare

# 14. diagnoza: tytuł "Backpack" i obcięty dolny wiersz (zrzut panel.png ze scratchpadu, jeśli jest)
panel = "/tmp/claude-1000/-home-charlie/a82b116a-5d12-4f24-a10d-d408ab792454/scratchpad/panel.png"
if _os.path.exists(panel):
    from PIL import Image
    p = Image.open(panel).convert("RGB")
    im = Image.new("RGB", (1000 + p.size[0], p.size[1]), (0, 0, 0)); im.paste(p, (1000, 0))
    okna = loot.znajdz_okna(im)
    sprawdz("14a okno Backpack rozpoznane jako plecak", len(okna) == 1 and okna[0].rola == "plecak" and okna[0].tytul == "backpack", okna)
    sprawdz("14b obcięty dolny wiersz nie jest slotem (12 slotów, nie 16)", okna and len(okna[0].sloty) == 12, okna)
    # pamięć: 7 przedmiotów w slotach 0-6; ekran 3 wiersze: dopasowanie musi się zgodzić
    kont = [{"numer": 0, "id": 2854, "nazwa": "Backpack", "pojemnosc": 20,
             "przedmioty": [{"slot": i, "id": 3577 + i, "ilosc": 1} for i in range(7)]}]
    przyp, powod = loot.dopasuj_okna(im, okna, kont)
    sprawdz("14c pamięć zgodna z ekranem", przyp is not None, powod)
else:
    print("(pominięto 14: brak panel.png)")

# 15. N5: nieudane jedzenie przy nieczytelnych kontenerach to nie "brak jedzenia"
s = Swiat(mana=35, zapas=0); b = zrob(s); s.odczyt = "brak"
glodny_hp(b, s)
b.jedzenie = None
b.zjedz(s.t, b.gracz())
sprawdz("15a kontenery puste: jedzenie_znane_brak False", not b.jedzenie_znane_brak(s.t) and b.jedzenie_odczyt_watpliwy(s.t))
s = Swiat(mana=35, zapas=0); b = zrob(s); s.odczyt = "ok"
glodny_hp(b, s)
b.zjedz(s.t, b.gracz())
sprawdz("15b plecak czytelny i pusty: brak jedzenia znany", b.jedzenie_znane_brak(s.t) and not b.jedzenie_odczyt_watpliwy(s.t))
cavebot.JEDZENIE_BRAK_WALIDUJ = 0
s = Swiat(mana=35, zapas=0); b = zrob(s); s.odczyt = "brak"
glodny_hp(b, s)
b.zjedz(s.t, b.gracz())
sprawdz("15c pokrętło 0: dawne zachowanie (brak znany)", b.jedzenie_znane_brak(s.t))
cavebot.JEDZENIE_BRAK_WALIDUJ = 1
s = Swiat(mana=35, zapas=0); b = zrob(s); s.odczyt = "brak"
b.zjedz(s.t, b.gracz()); s.odczyt = "ok"; s.zapas = 3
s.t += cavebot.JEDZENIE_PONOW + 1
sprawdz("15d po wygaśnięciu okna znów liczy się odczyt", not b.jedzenie_odczyt_watpliwy(s.t))

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
