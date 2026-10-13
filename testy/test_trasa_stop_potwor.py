"""Trasa wielopiętrowa: potwór w TRASA_STOP_PRZY_POTWORZE_R wstrzymuje krok trasy i przejście pięter, także gdy
lista stworów z początku obiegu jest stara/pusta (cache rdzenia tuż po zmianie piętra). Atrapy, bez X11."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot, pokretla

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Swiat:
    def __init__(s):
        s.t = 0.0; s.poz = [99, 100, 8]; s.stwory = []; s.stary_cache = False; s.skany = []
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            s.skany.append(z.get("maks_wiek"))
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            if s.stary_cache and z.get("maks_wiek") is None:
                return {"stwory": [ja]}          # cache rdzenia sprzed zmiany piętra: pusto
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}
class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): pass
    def krok(p, k): p.s.t += 0.2; return tuple(p.s.poz)

def troll(x, y, i=10): return {"id": i, "nazwa": "Troll", "x": x, "y": y, "z": 8, "hp": 100, "gracz": False}

def zrob(s):
    ataki = []
    b = cavebot.Cavebot(P(s), [(98, 100, 8), (100, 100, 9), (101, 100, 9), (101, 100, 8)], zapytaj=s.zapytaj,
                        atak=lambda m, g: ataki.append(m), alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=types.SimpleNamespace(zbierz=lambda z, g: "ok"), okrazenia=1)
    b.przerwa_od = float("inf"); b.idx = 1          # następny punkt: inne piętro (z9)
    b.pietra_wywolania = []
    b._pietra_tick = lambda poz, cel: (b.pietra_wywolania.append((poz, cel)), True)[1]
    b.ataki = ataki
    return b

sprawdz("0a domyślnie R=4", cavebot.TRASA_STOP_PRZY_POTWORZE_R == 4)
sprawdz("0b pokrętło w ZAKRESY/KIERUNEK", pokretla.ZAKRESY.get("TRASA_STOP_PRZY_POTWORZE_R") == (0, 8)
        and pokretla.KIERUNEK.get("TRASA_STOP_PRZY_POTWORZE_R") == "nie_nizej")
sprawdz("0c analityk nie wyłączy", pokretla.waliduj({"TRASA_STOP_PRZY_POTWORZE_R": 0}, {"TRASA_STOP_PRZY_POTWORZE_R": 4})[0] == {})

# 1. bez potwora: próba przejścia pięter idzie jak zwykle
s = Swiat(); b = zrob(s)
b.tick()
sprawdz("1 brak potwora: pietra.tick wywołane", len(b.pietra_wywolania) == 1)

# 2. potwór 2 pola obok, lista z początku obiegu pusta (stary cache): brak próby przejścia, walka w następnym obiegu
s = Swiat(); b = zrob(s); s.stwory = [troll(101, 100)]; s.stary_cache = True
b._z_poprz = 9                       # właśnie zmieniliśmy piętro 9 -> 8
LOGI.clear()
b.tick()
sprawdz("2a przy trollu w odl 2 brak próby przejścia", b.pietra_wywolania == [], b.pietra_wywolania)
sprawdz("2b świeży odczyt od razu daje walkę (Nowy cel), nie trasę", any("Nowy cel: Troll" in l for l in LOGI), LOGI[-2:])
sprawdz("2c po zmianie piętra odczyt stworów był świeży (maks_wiek 0)", 0.0 in s.skany, s.skany)
s.stary_cache = False
LOGI.clear(); b.tick()
sprawdz("2d następny obieg: nadal bez przejścia", b.pietra_wywolania == [], LOGI[-3:])

# 3. sam guard w _idz_trasa (stary cache bez zmiany piętra: lista pusta, potwór tuż obok)
s = Swiat(); b = zrob(s); s.stwory = [troll(100, 101)]; s.stary_cache = True
LOGI.clear(); b.tick()
sprawdz("3a stara pusta lista (bez zmiany piętra): guard łapie potwora, brak próby", b.pietra_wywolania == [])
sprawdz("3b log po polsku", any(l.startswith("Trasa wstrzymana: Troll 1 pól") for l in LOGI), LOGI[-2:])
sprawdz("3c telemetria/stan WALKA", str(b.stan) == "WALKA", b.stan)
for _ in range(cavebot.TRASA_STOP_MAX + 2):
    b.tick()
sprawdz("3d bezpiecznik: potwór, który nie wchodzi do walki, nie blokuje trasy w nieskończoność",
        b._trasa_stop_n >= cavebot.TRASA_STOP_MAX or b.cel is not None, f"n={b._trasa_stop_n} cel={b.cel}")

# 4. pokrętło 0 = dawne zachowanie
cavebot.TRASA_STOP_PRZY_POTWORZE_R = 0
s = Swiat(); b = zrob(s); s.stwory = [troll(100, 101)]; s.stary_cache = True
b.tick()
sprawdz("4 R=0: guard wyłączony (próba przejścia jak dawniej)", len(b.pietra_wywolania) == 1)
cavebot.TRASA_STOP_PRZY_POTWORZE_R = 4

# 5. bezpiecznik: potwór niewalczalny (ignorowany nie wchodzi do kand), więc nie zatrzymuje trasy
s = Swiat(); b = zrob(s); s.stwory = [troll(103, 100)]; s.stary_cache = True
b.ignorowane[10] = s.t + 100
b.tick()
sprawdz("5 ignorowany potwór nie wstrzymuje trasy", len(b.pietra_wywolania) == 1)

# 6. potwór na innym piętrze nie wstrzymuje
s = Swiat(); b = zrob(s); m = troll(100, 101); m["z"] = 9; s.stwory = [m]; s.stary_cache = True
b.tick()
sprawdz("6 potwór z innego piętra nie wstrzymuje", len(b.pietra_wywolania) == 1)

# 7. pietra.Pietra.tick sam odmawia próby przy potworze (wywołanie bezpośrednie)
import pietra
s = Swiat(); b = zrob(s); s.stwory = [troll(100, 101)]
p = pietra.Pietra(b, konf=cavebot, log=lambda t: None)
r = p.tick((100, 100, 8), (100, 100, 9))
sprawdz("7 Pietra.tick przy potworze: True, bez stanu przejścia", r is True and p.st is None, f"r={r} st={p.st}")

print(f"OK={sum(ok)} FAIL={len(ok) - sum(ok)}")
sys.exit(0 if all(ok) else 1)
