"""PATROL_GRACZ_ZMIEN: obcy gracz blisko nas albo celu = od razu zmiana respa na dalszy od niego (bez X11)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cavebot, pokretla

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

LOGI = []
cavebot.log = lambda *a: LOGI.append(" ".join(map(str, a)))
f = cavebot.Cavebot._patrol_gracz_zmiana
MIEJSCA = [{"id": 1, "x": 100, "y": 100, "z": 8},      # realne miejsca patrolu nie mają klucza "nazwa"
           {"id": 2, "x": 110, "y": 100, "z": 8},
           {"id": 3, "x": 160, "y": 100, "z": 8},
           {"id": 4, "x": 100, "y": 170, "z": 8}]
T = 1000.0

def cb(gracze, miejsca=None, wybierz_none=False):
    s = types.SimpleNamespace(unikanie=types.SimpleNamespace(gracze=gracze), miejsca=miejsca or MIEJSCA, patrol_blok={},
                              patrol="stara", zakonczone=[], tele=[], patrol_zmiana_ost=float("-inf"))
    def zakoncz(p, powod): s.zakonczone.append(powod)
    def kandydaci(poz, pomin=None):
        return [(m, 0) for m in s.miejsca if m["id"] != pomin and s.patrol_blok.get(m["id"], float("-inf")) <= T]
    def wybierz(poz, pomin=None):
        k = kandydaci(poz, pomin)
        return None if wybierz_none or not k else {"m": k[0][0]}
    s._patrol_zakoncz, s._patrol_wybierz, s._patrol_kandydaci = zakoncz, wybierz, kandydaci
    s._patrol_tele = lambda typ, **d: s.tele.append((typ, d))
    return s

def gracz(x, y, z=8, n="Thanos"): return {"nazwa": n, "x": x, "y": y, "z": z}
POZ = (102, 100, 8)
P = lambda mid: {"m": MIEJSCA[mid - 1]}

cavebot.PATROL_GRACZ_ZMIEN, cavebot.PATROL_GRACZ_ZMIEN_R = 1, 12
cavebot.PATROL_GRACZ_PAM_R, cavebot.PATROL_GRACZ_ZMIEN_BLOK_S, cavebot.PATROL_GRACZ_ZMIEN_PAUZA_S = 14, 240.0, 15.0

c = cb([gracz(108, 100)])
n = f(c, P(1), POZ, T)
sprawdz("1 gracz 6 pól od nas, cel przy nim: zmiana na daleki respa (3)", n is not None and n["m"]["id"] == 3, n)
sprawdz("2 miejsca 1 i 2 (<=14 od gracza) zablokowane na 240 s", c.patrol_blok.get(1) == T + 240 and c.patrol_blok.get(2) == T + 240, c.patrol_blok)
sprawdz("3 miejsca 3 i 4 bez blokady", 3 not in c.patrol_blok and 4 not in c.patrol_blok)
sprawdz("4 wizyta zakończona, telemetria zapisana", len(c.zakonczone) == 1 and c.tele and c.tele[0][0] == "patrol_gracz_zmiana", c.tele)
sprawdz("5 log z id i współrzędnymi (miejsca nie mają nazw)", any("m1 (100,100) -> m3 (160,100)" in l for l in LOGI), LOGI[-1:])
n2 = f(c, n, POZ, T + 5)
sprawdz("6 pauza 15 s: bez drugiej zmiany", n2 is None)

c = cb([gracz(108, 100)])
sprawdz("7 gracz blisko nas, cel (3) daleko od niego: bez zmiany i BEZ blokad",
        f(c, P(3), POZ, T) is None and not c.zakonczone and not c.patrol_blok, c.patrol_blok)
c = cb([gracz(108, 100, z=9)])
sprawdz("8 gracz na innym piętrze: nic", f(c, P(1), POZ, T) is None)
c = cb([gracz(140, 100)])
sprawdz("9 gracz 38 pól od nas i od celu 1: nic", f(c, P(1), POZ, T) is None)
c = cb([gracz(160, 100)])
n = f(c, P(3), POZ, T)
sprawdz("10 gracz przy celu 3 (58 pól od nas): zmiana na inny", n is not None and n["m"]["id"] != 3, n)

# brak alternatywy: tylko dwa miejsca, oba przy graczu
c = cb([gracz(105, 100)], miejsca=[MIEJSCA[0], MIEJSCA[1]])
r = f(c, P(1), POZ, T)
sprawdz("11 brak alternatywy: None, wizyta NIE zakończona, blokady cofnięte",
        r is None and not c.zakonczone and c.patrol_blok.get(1, float("-inf")) == float("-inf") and c.patrol == "stara", (c.zakonczone, c.patrol_blok))
sprawdz("12 brak alternatywy: pauza ustawiona (bez ponawiania co obieg)", c.patrol_zmiana_ost == T)
r2 = f(c, P(1), POZ, T + 1)
sprawdz("13 kolejny obieg w pauzie: nic", r2 is None and not c.zakonczone)

# są kandydaci, ale _patrol_wybierz zawiódł (np. brak drogi): blokady cofnięte, self.patrol=None
c = cb([gracz(108, 100)], wybierz_none=True)
r = f(c, P(1), POZ, T)
sprawdz("14 wybór zawiódł: None, blokady cofnięte, patrol=None (zwykły wybór w _idz_patrol)",
        r is None and c.patrol is None and c.patrol_blok.get(1, float("-inf")) == float("-inf") and len(c.zakonczone) == 1, (c.patrol, c.patrol_blok))

cavebot.PATROL_GRACZ_ZMIEN = 0
c = cb([gracz(108, 100)])
sprawdz("15 pokrętło 0: bez zmiany", f(c, P(1), POZ, T) is None and not c.patrol_blok)
sprawdz("16 pokrętła zarejestrowane", all(k in pokretla.ZAKRESY for k in ("PATROL_GRACZ_ZMIEN", "PATROL_GRACZ_ZMIEN_R",
        "PATROL_GRACZ_ZMIEN_BLOK_S", "PATROL_GRACZ_ZMIEN_PAUZA_S")))
sprawdz("17 domyślnie wyłączone w kodzie", cavebot.Cavebot.__init__ is not None and
        "PATROL_GRACZ_ZMIEN = 0" in Path(cavebot.__file__).read_text())

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
