"""LOOT_SZYBKI_STYKAJACE (23.10, decyzja Karola): zwłoki obok zbieramy OD RAZU po zabiciu także wtedy, gdy kolejny mob
przylega (odl 1); dopiero potem walka z następnym. Atrapy (RETRONIC_TESTY=1), bez gry."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types, tempfile
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot, pokretla

cavebot.REAKCJA = (0.0, 0.0); cavebot.ML_CZAR_AKTYWNY = 0; cavebot.UH_AKTYWNY = 0
cavebot.UH_STAN_PLIK = Path(tempfile.mkdtemp()) / "uh.json"
cavebot.log = lambda *a: None
LOGI = []
cavebot.log = lambda *a: LOGI.append(" ".join(str(x) for x in a))
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Swiat:
    def __init__(s): s.t = 0.0; s.poz = [100, 100, 7]; s.stwory = []; s.hp = 100
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def gracz(s): return {"hp": s.hp * 1.9, "max_hp": 190, "mana": 50, "max_mana": 125, "proc": float(s.hp)}
    def zapytaj(s, z):
        s.t += 0.01
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

def mob(x, y=100, id=9, hp=100, z=7, nazwa="Troll"):
    return {"id": id, "nazwa": nazwa, "gracz": False, "x": x, "y": y, "z": z, "hp": hp}

def nowy(styk=1, pelny=False):
    cavebot.LOOT_DYNAMICZNY = 1
    cavebot.LOOT_SZYBKI_STYKAJACE = styk
    s = Swiat()
    wywolania = []
    def zbierz(z, g):
        wywolania.append((tuple(z), getattr(b, "loot_styk", None) and dict(b.loot_styk)))
        return "ok"
    loot = types.SimpleNamespace(zbierz=zbierz, zjedz=lambda log=None: [], ile_jedzenia=lambda: 10)
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj, atak=lambda m, g: None,
                        alarm=lambda w: None, spij=s.spij, zegar=s.zegar, loot=loot, okrazenia=1, jedzenie="F5")
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    b.REC = []; b.WYW = wywolania
    if not pelny:
        def zl(zw):
            b.REC.append(tuple(zw)); b.REC_styk = getattr(b, "loot_styk", None)
            return "ok"
        b.zbierz_loot = zl
    return s, b

def zabij(s, b, zwloki_xyz, zywe):
    s.stwory = list(zywe)
    b.ostatnie_stwory = [dict(m) for m in s.stwory]
    b.cel = {"id": 5, "nazwa": "Troll", "poz": zwloki_xyz, "hp": 0, "odl": 1}
    del LOGI[:]
    b.zgon_celu(s.gracz(), tuple(s.poz), pewny=True)

ZW = (101, 100, 7)

# 0. pokrętło w pokretla
try:
    sprawdz("0a zakres 0-2", pokretla.ZAKRESY["LOOT_SZYBKI_STYKAJACE"] == (0, 2))
    sprawdz("0b analityk nie może podnieść (nie_wyzej)", pokretla.KIERUNEK["LOOT_SZYBKI_STYKAJACE"] == "nie_wyzej")
    sprawdz("0c waliduj 3 poza zakresem odrzucone", pokretla.waliduj({"LOOT_SZYBKI_STYKAJACE": 3})[0] == {})
    sprawdz("0d waliduj 0 ok", pokretla.waliduj({"LOOT_SZYBKI_STYKAJACE": 0})[0] == {"LOOT_SZYBKI_STYKAJACE": 0})
except Exception as e:
    sprawdz("0 pokrętło", False, repr(e))
sprawdz("0e domyślnie 1 w cavebot", getattr(cavebot, "LOOT_SZYBKI_STYKAJACE", None) == 1)

# 1. mob przylega, HP wysoko: loot od razu
s, b = nowy(1); zabij(s, b, ZW, [mob(100, 101, id=11)])
sprawdz("1a mob przylega, HP 100: zwłoki zbierane OD RAZU", b.REC == [ZW] and not b.zwloki_czekajace, (b.REC, b.zwloki_czekajace))
sprawdz("1b w trakcie lootu aktywny tryb styku (dop=1)", (getattr(b, "REC_styk", None) or {}).get("dop") == 1, getattr(b, "REC_styk", None))
sprawdz("1c po lootcie tryb styku wyczyszczony, cel None (atak niezgubiony: następny wybierze tick)",
        getattr(b, "loot_styk", None) is None and b.cel is None)
sprawdz("1d log 'Loot szybki' z liczbą przylegających", any("Loot szybki" in l and "przyleg" in l for l in LOGI), LOGI)
sprawdz("1e brak logu 'Loot odłożony'", not any("Loot odłożony" in l for l in LOGI), LOGI)

# 2. dwa przylegające przy pokrętle 1: odłożone
s, b = nowy(1); zabij(s, b, ZW, [mob(100, 101, id=11), mob(99, 100, id=12)])
sprawdz("2a 2 przylegające, pokrętło 1: odłożone", b.REC == [] and b.zwloki_czekajace and any("Loot odłożony" in l for l in LOGI), (b.REC, LOGI))
s, b = nowy(2); zabij(s, b, ZW, [mob(100, 101, id=11), mob(99, 100, id=12)])
sprawdz("2b 2 przylegające, pokrętło 2: od razu (dop=2)", b.REC == [ZW] and b.REC_styk and b.REC_styk.get("dop") == 2, b.REC)
s, b = nowy(2); zabij(s, b, ZW, [mob(100, 101, id=11), mob(99, 100, id=12), mob(99, 101, id=13)])
sprawdz("2c 3 przylegające, pokrętło 2: odłożone", b.REC == [] and b.zwloki_czekajace)

# 3. HP niskie / ucieczka / groźny gracz: odłożone
s, b = nowy(1); s.hp = 40; zabij(s, b, ZW, [mob(100, 101, id=11)])
sprawdz("3a HP 40% (<= próg+15), mob przylega: odłożone", b.REC == [] and b.zwloki_czekajace)
s, b = nowy(1); b.ucieczka = True; zabij(s, b, ZW, [mob(100, 101, id=11)])
sprawdz("3b ucieczka: odłożone", b.REC == [] and b.zwloki_czekajace)
s, b = nowy(1); b.ostrozny = True; zabij(s, b, ZW, [mob(100, 101, id=11)])
sprawdz("3c ostrożny: odłożone", b.REC == [] and b.zwloki_czekajace)
s, b = nowy(1); b._ogien_na = lambda p: True; zabij(s, b, ZW, [mob(100, 101, id=11)])
sprawdz("3d zwłoki na ogniu: odłożone", b.REC == [] and b.zwloki_czekajace)
s, b = nowy(1); b._grozni_w_zasiegu = lambda l, p: [{"nazwa": "PK"}]; zabij(s, b, ZW, [mob(100, 101, id=11)])
sprawdz("3e groźny gracz: odłożone", b.REC == [] and b.zwloki_czekajace)

# 4. pokrętło 0: stare zachowanie
s, b = nowy(0); zabij(s, b, ZW, [mob(100, 101, id=11)])
sprawdz("4a pokrętło 0, mob przylega: odłożone (jak dotąd)", b.REC == [] and b.zwloki_czekajace and any("Loot odłożony" in l for l in LOGI))
s, b = nowy(0); zabij(s, b, ZW, [mob(103)])
sprawdz("4b pokrętło 0, mob w odl 3: dalej od razu (bez zmian)", b.REC == [ZW] and getattr(b, "REC_styk", None) is None, (b.REC, getattr(b, "REC_styk", None)))

# 5. zwłoki dalej niż 1 przy przylegającym: odłożone, bez kroków
s, b = nowy(1); zabij(s, b, (102, 100, 7), [mob(100, 101, id=11)])
sprawdz("5a zwłoki w odl 2, mob przylega: odłożone", b.REC == [] and b.zwloki_czekajace)
s, b = nowy(1); zabij(s, b, (103, 100, 7), [mob(100, 101, id=11)])
sprawdz("5b zwłoki w odl 3, mob przylega: odłożone", b.REC == [] and b.zwloki_czekajace)
s, b = nowy(1); zabij(s, b, (100, 100, 7), [mob(100, 101, id=11)])
sprawdz("5c zwłoki pod nogami (wymaga kroku), mob przylega: odłożone", b.REC == [] and b.zwloki_czekajace)
# bez przylegającego bez zmian
s, b = nowy(1); zabij(s, b, (103, 100, 7), [mob(106, id=12)])
sprawdz("5d zwłoki w odl 3, mob daleko: od razu (jak dotąd), bez trybu styku", b.REC == [(103, 100, 7)] and getattr(b, "REC_styk", None) is None)

# 6. kandydaci: przy styku tylko pola w odl 1
s, b = nowy(1)
s.stwory = [mob(100, 101, id=11)]; b.ostatnie_stwory = [dict(m) for m in s.stwory]
b.cel = {"id": 5, "nazwa": "Troll", "poz": (101, 100, 7), "hp": 0, "odl": 1, "krok": (1, 0), "krok_czas": s.t, "slad": [(100, 99), (101, 100)]}
b.zbierz_loot = lambda zw: (b.REC.append(tuple(zw)), "brak_okna")[1]
b.zgon_celu(s.gracz(), tuple(s.poz), pewny=True)
sprawdz("6 kandydaci przy styku tylko w odl 1 (ekstrapolowane (102,100) pominięte)", all(max(abs(z[0] - 100), abs(z[1] - 100)) == 1 for z in b.REC) and b.REC, b.REC)

# 7. _przerwij_loot w trybie styku
def tryb(styk_dop=1, t0=None):
    s, b = nowy(1)
    b.przeglad_odl = 1; b.przeglad_loot_ost = -9; b.hp_gracza_spadek = -1e9
    b.loot_styk = {"dop": styk_dop, "t0": s.t if t0 is None else t0, "hp": [(s.t, 100.0)]}
    return s, b
s, b = tryb(); s.stwory = [mob(101, 101, id=11)]
sprawdz("7a 1 przylegający, dop=1: nie przerywa", b._przerwij_loot() is False)
s, b = tryb(); s.stwory = [mob(101, 101, id=11), mob(99, 99, id=12)]
sprawdz("7b 2 przylegające, dop=1: przerywa", b._przerwij_loot() is True)
s, b = tryb(2); s.stwory = [mob(101, 101, id=11), mob(99, 99, id=12)]
sprawdz("7c 2 przylegające, dop=2: nie przerywa", b._przerwij_loot() is False)
s, b = tryb(); s.stwory = [mob(101, 101, id=11)]; s.hp = 90
sprawdz("7d spadek HP o 10 pp: przerywa (hp_spadek)", b._przerwij_loot() is True)
s, b = tryb(); s.stwory = [mob(101, 101, id=11)]; s.hp = 98
sprawdz("7e spadek HP o 2 pp (szum): nie przerywa", b._przerwij_loot() is False)
s, b = tryb(); s.stwory = [mob(101, 101, id=11)]; s.t += cavebot.LOOT_SZYBKI_STYK_MAX_S + 1
sprawdz("7f limit czasu: przerywa", b._przerwij_loot() is True)
s, b = tryb(); s.stwory = [mob(101, 101, id=11)]; b.loot_styk = None
sprawdz("7g bez trybu styku 1 przylegający przerywa jak dotąd", b._przerwij_loot() is True)

# 8. pełny _zbierz_loot (prawdziwa pętla): styk
s, b = nowy(1, pelny=True); zabij(s, b, ZW, [mob(100, 101, id=11)])
sprawdz("8a pełny zbierz_loot: loot.zbierz wywołane, tryb styku aktywny, brak 'Przerywam loot'",
        len(b.WYW) == 1 and b.WYW[0][0] == ZW and (b.WYW[0][1] or {}).get("dop") == 1
        and not any("Przerywam loot" in l for l in LOGI), (b.WYW, LOGI))
sprawdz("8b po lootcie zwłoki zdjęte z listy, tryb wyczyszczony", not b.zwloki_czekajace and b.loot_styk is None)
s, b = nowy(0, pelny=True)
b.loot_styk = None
b.odloz_zwloki(ZW, nowe=True)
b.ostatnie_stwory = [mob(100, 101, id=11)]; s.stwory = [mob(100, 101, id=11)]
r = b.zbierz_loot(ZW)
sprawdz("8c bez trybu styku (loot po walce) mob przylega: przerwany jak dotąd", r == "przerwany" and not b.WYW, (r, b.WYW))
# 8d. trzy ścieżki wyjścia czyszczą tryb styku (wyjątek w zbierz)
s, b = nowy(1, pelny=True)
b.loot.zbierz = lambda z, g: (_ for _ in ()).throw(RuntimeError("x"))
zabij(s, b, ZW, [mob(100, 101, id=11)])
sprawdz("8d wyjątek w lootcie: tryb styku wyczyszczony", b.loot_styk is None)

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
