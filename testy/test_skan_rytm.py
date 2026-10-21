"""Skan stworów: częściej w walce, rzadziej w spokoju (SPEC_skan_walka_spokoj_1021). Atrapy: bez pamięci gry, bez strażnika.
rdzen.Pamiec: pole "rytm" w zapytaniu steruje planowaniem skanera w tle (bez pola = jak dotąd, WIEK_* 0,5 s).
cavebot.stwory(): przy pokrętłach domyślnych (0.5/0.5) zapytanie bez "rytm"; inaczej rytm wg stanu bota."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, time, types
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import rdzen, cavebot, pokretla

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

STWOR = {"gracz": False, "nazwa": "Troll"}

def pamiec(wiek_cache):
    p = rdzen.Pamiec()
    p.mem = object()
    teraz = time.monotonic()
    p._cache = ([STWOR], teraz - wiek_cache, "szybki", teraz)
    p._ostatnie_zapytanie = teraz
    p._czas_skanu = 0.1
    p._potrzebny_pelny = lambda t: False
    p.podlacz = lambda: 1
    p.skany = 0
    def skan(pelny):
        p.skany += 1
        p._cache = ([STWOR], time.monotonic(), "szybki", time.monotonic())
        return p._cache
    p._skanuj_stwory = skan
    return p

# --- rdzeń: bez pola "rytm" jak dotąd ---
p = pamiec(0.1)
p.stwory_info()
sprawdz("rdzeń: zapytanie bez rytmu nie ustawia rytmu", p._rytmy is None and p._rytm_teraz(time.monotonic()) is None)
sen = p.skaner_krok()
sprawdz("rdzeń bez rytmu: cache 0,1 s przy limicie 0,5 s = bez skanu, sen > 0", p.skany == 0 and sen > 0, f"sen={sen:.3f}")

# --- rdzeń: rytm walki 0,15 s ---
p = pamiec(0.1)
p.stwory_info(rytm=0.15)
sprawdz("rdzeń: rytm 0,15 zapamiętany", p._rytm_teraz(time.monotonic()) == 0.15)
p.skaner_krok()
sprawdz("rdzeń rytm 0,15: cache 0,1 s już do odświeżenia (skan w tle)", p.skany == 1)

# --- rdzeń: rytm spokoju 1,0 s ---
p = pamiec(0.6)
p.stwory_info(maks_wiek=1.0, rytm=1.0)
sen = p.skaner_krok()
sprawdz("rdzeń rytm 1,0: cache 0,6 s bez skanu (dawniej limit 0,5 = skan)", p.skany == 0 and sen > 0, f"sen={sen:.3f}")
p0 = pamiec(0.6)
p0.skaner_krok()
sprawdz("rdzeń bez rytmu: cache 0,6 s = skan (kontrola)", p0.skany == 1)

# --- rdzeń: rytm wygasa po RYTM_WAZNY_S ---
p = pamiec(0.1)
p._rytmy = {0.15: time.monotonic() - rdzen.Pamiec.RYTM_WAZNY_S - 0.5}
p.skaner_krok()
sprawdz("rdzeń: rytm starszy niż RYTM_WAZNY_S = jak dotąd (bez skanu przy cache 0,1 s)", p.skany == 0)

# --- rdzeń: zakres i śmieci ---
p = pamiec(0.1)
p.stwory_info(rytm=0.0)
sprawdz("rdzeń: rytm 0 przycięty do 0,05", p._rytm_teraz(time.monotonic()) == 0.05)
p = pamiec(0.1)
p.stwory_info(rytm=99)
sprawdz("rdzeń: rytm 99 przycięty do 2,0", p._rytm_teraz(time.monotonic()) == 2.0)
p.stwory_info(rytm="x")
p.stwory_info(rytm=float("nan"))
p.stwory_info(rytm=float("inf"))
sprawdz("rdzeń: rytm nie-liczba / NaN / inf ignorowany", p._rytmy is not None and set(p._rytmy) == {2.0}, p._rytmy)

# --- rdzeń: obsluz przekazuje pole rytm ---
p = pamiec(0.1)
p.obsluz({"cmd": "stwory", "rytm": 0.2})
sprawdz("rdzeń: obsluz({'cmd':'stwory','rytm':0.2}) ustawia rytm", p._rytm_teraz(time.monotonic()) == 0.2)

# --- rdzeń: najmniejszy rytm z okna (przegląd 21.10, znalezisko 1) ---
p = pamiec(0.35)
p.stwory_info(maks_wiek=0.3, rytm=0.3)
p.stwory_info(maks_wiek=1.0, rytm=1.0)
sprawdz("rdzeń: 0,3 potem 1,0 w 2 s = plan pod 0,3 (nie ostatni)", p._rytm_teraz(time.monotonic()) == 0.3)
p.skany = 0
p._cache = ([STWOR], time.monotonic() - 0.35, "szybki", time.monotonic())
p.skaner_krok()
sprawdz("rdzeń: cache 0,35 s przy rytmie 0,3 = skan w tle", p.skany == 1)
p2 = pamiec(0.35); p2._rytmy = {1.0: time.monotonic()}; p2.skaner_krok()
sprawdz("rdzeń: kontrola: sam rytm 1,0 przy cache 0,35 s = bez skanu", p2.skany == 0)
p._rytmy = {0.15: time.monotonic() - 3.0, 1.0: time.monotonic()}
sprawdz("rdzeń: walka wygasła po 2 s = spokój 1,0", p._rytm_teraz(time.monotonic()) == 1.0)

# --- cavebot: zapytania ---
ZAPYTANIA = []
def bot(stan, cel=None):
    b = types.SimpleNamespace(stan=stan, cel=cel, pet=None, postac=types.SimpleNamespace(nazwa="X"), gracz_grozny=None, zegar=time.monotonic)
    b.zapytaj = lambda z: (ZAPYTANIA.append(dict(z)), {"stwory": []})[1]
    b.skan_rytm = types.MethodType(cavebot.Cavebot.skan_rytm, b)
    b.stwory = types.MethodType(cavebot.Cavebot.stwory, b)
    return b

def ostatnie():
    return ZAPYTANIA[-1]

cavebot.SKAN_WIEK_WALKA, cavebot.SKAN_WIEK_SPOKOJ = 0.5, 0.5
bot("WALKA").stwory()
sprawdz("cavebot domyślnie: walka bez pola rytm i bez maks_wiek (jak dotąd)", ostatnie() == {"cmd": "stwory"}, ostatnie())
bot("IDZ").stwory(0.3)
sprawdz("cavebot domyślnie: jawne maks_wiek bez zmian", ostatnie() == {"cmd": "stwory", "maks_wiek": 0.3}, ostatnie())

cavebot.SKAN_WIEK_WALKA, cavebot.SKAN_WIEK_SPOKOJ = 0.15, 1.0
for stan in cavebot.SKAN_STANY_WALKI:
    bot(stan).stwory()
    sprawdz(f"cavebot {stan}: rytm 0,15 i maks_wiek 0,15", ostatnie() == {"cmd": "stwory", "rytm": 0.15, "maks_wiek": 0.15}, ostatnie())
bot("IDZ", cel=(1, 2, 7)).stwory()
sprawdz("cavebot IDZ z ustawionym celem = walka (0,15)", ostatnie().get("rytm") == 0.15, ostatnie())
bot("IDZ").stwory()
sprawdz("cavebot IDZ bez celu: rytm 1,0 i maks_wiek 1,0", ostatnie() == {"cmd": "stwory", "rytm": 1.0, "maks_wiek": 1.0}, ostatnie())
bot("IDZ").stwory(0.3)
sprawdz("cavebot IDZ stwory(0.3) w spokoju: rytm 0,3 (skaner nadąża za marszem)", ostatnie() == {"cmd": "stwory", "rytm": 0.3, "maks_wiek": 0.3}, ostatnie())
bot("IDZ").stwory(0.0)
sprawdz("cavebot IDZ stwory(0.0): rytm spokoju, nie 0", ostatnie() == {"cmd": "stwory", "rytm": 1.0, "maks_wiek": 0.0}, ostatnie())
bot("LOOT").stwory()
sprawdz("cavebot LOOT = walka (0,15)", ostatnie().get("rytm") == 0.15, ostatnie())
bot("WALKA").stwory(0.0)
sprawdz("cavebot jawne stwory(0.0) zostaje świeżym skanem (maks_wiek 0) z rytmem walki", ostatnie() == {"cmd": "stwory", "rytm": 0.15, "maks_wiek": 0.0}, ostatnie())
cavebot.SKAN_WIEK_WALKA, cavebot.SKAN_WIEK_SPOKOJ = 0.5, 0.5

# --- pokrętła ---
pop, bl = pokretla.waliduj({"SKAN_WIEK_WALKA": 0.15, "SKAN_WIEK_SPOKOJ": 1.0})
sprawdz("pokretla: 0,15 / 1,0 poprawne", not bl and pop == {"SKAN_WIEK_WALKA": 0.15, "SKAN_WIEK_SPOKOJ": 1.0}, (pop, bl))
pop, bl = pokretla.waliduj({"SKAN_WIEK_WALKA": 0.05, "SKAN_WIEK_SPOKOJ": 3.0})
sprawdz("pokretla: poza zakresem odrzucone", len(bl) == 2, bl)

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
