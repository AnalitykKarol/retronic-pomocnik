"""Przejście w dół przez zgadywaną kratkę (domysł, 19.10): pierwsza próba to Ctrl+klik (use), nie krok. Atrapy, bez gry."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
_R = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _R)
import pietra

OK = FAIL = 0
def spr(nazwa, warunek):
    global OK, FAIL
    OK, FAIL = (OK + 1, FAIL) if warunek else (OK, FAIL + 1)
    print(("OK   " if warunek else "FAIL ") + nazwa)

ja = types.SimpleNamespace(_dane=lambda: True)
st = {"z0": 8}
domysl = {"pole": (33168, 31823, 8), "pewne": False, "lad": (33168, 31823, 9)}
pewne = dict(domysl, pewne=True)

spr("domysł w dół (kratka): pierwsza próba use", pietra.Pietra._tryby(ja, domysl, st)[0] == "use")
spr("domysł w dół: krok też jest w liście", "krok" in pietra.Pietra._tryby(ja, domysl, st))
spr("pewna dziura w dół: bez zmian (krok pierwszy, bez use)",
    pietra.Pietra._tryby(ja, pewne, st) == list(pietra.TRYBY_DOL_DANE) and "use" not in pietra.Pietra._tryby(ja, pewne, st))
spr("w górę: jedna ze znanych list trybów", pietra.Pietra._tryby(types.SimpleNamespace(_dane=lambda: True, cb=types.SimpleNamespace(mapa=None)),
    {"pole": (1, 1, 8), "pewne": True, "lad": (1, 2, 7)}, {"z0": 8}) in (list(pietra.TRYBY_GORA_DRABINA), list(pietra.TRYBY_GORA_SCHODY), list(pietra.TRYBY_GORA_NIEZNANE)))
spr("dawny porządek (PIETRA_TRYBY_Z_DANYCH=0): domysł zaczyna od use", pietra.Pietra._tryby(types.SimpleNamespace(_dane=lambda: False), domysl, st)[0] == "use")
# 19.10 lina: wspinaczka na polu bez danych (Edron z11, dojście z depo) próbuje liny z plecaka
gora = {"pole": (33133, 31805, 11), "pewne": True, "lad": (33133, 31806, 10)}
ja_gora = types.SimpleNamespace(_dane=lambda: True, cb=types.SimpleNamespace(mapa=None))
tr = pietra.Pietra._tryby(ja_gora, gora, {"z0": 11})
spr("wspinaczka bez danych: w liście jest lina, R pierwsze", "lina" in tr and tr[0] == "R")
spr("wspinaczka bez danych: lina przed krokiem", tr.index("lina") < tr.index("krok"))

# 22.10: kratka Edron (33168,31823,z8): Use w trakcie kroku klient gubi, a z samego pola kratki trafia w postać
class _Postac:
    def __init__(p, poz, ruch=()): p.poz, p.ruch, p.kroki = list(poz), list(ruch), []
    def pozycja(p):
        if p.ruch:
            p.poz = list(p.ruch.pop(0))
        return tuple(p.poz)
    def krok(p, k):
        p.kroki.append(k); d = {"Down": (0, 1), "Left": (-1, 0), "Right": (1, 0), "Up": (0, -1)}[k]
        p.poz = [p.poz[0] + d[0], p.poz[1] + d[1], p.poz[2]]
def _ja(postac):
    cb = types.SimpleNamespace(mapa=None, postac=postac, spij=lambda s: None, pauza=lambda a, b: None)
    return types.SimpleNamespace(cb=cb, log=lambda *a: None)
T = (33168, 31823, 8)
p = _Postac(T)
poz = pietra.Pietra._przed_use(_ja(p), T, T, 8, zejdz=True)
spr("stojąc na kratce: krok z niej (Down) przed Ctrl+klik", p.kroki == ["Down"] and poz == (33168, 31824, 8))
p = _Postac((33167, 31825, 8), ruch=[(33167, 31825, 8), (33168, 31824, 8), (33168, 31824, 8)])
poz = pietra.Pietra._przed_use(_ja(p), T, (33167, 31825, 8), 8, zejdz=False)
spr("w trakcie kroku: czekamy, aż postać stanie, Ctrl+klik liczony z pozycji końcowej", p.kroki == [] and poz == (33168, 31824, 8))
print(f"\nOK={OK} FAIL={FAIL}")
sys.exit(1 if FAIL else 0)
