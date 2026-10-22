"""Regresja 22.10 (odchyd, mozg-stdout-1022-1811.log): dojście rook_kanaly_z11_dojscie z7 -> z8 przy depo Rook.
Punkt trasy (32060,32172,z8) leży pod ścianą wg mapy (z7 (32060,32172) flaga 5), kratka jest pole bliżej, (32060,32173,z7)
(flaga 1, bez flagi 2). Stary kod: kandydaci [] -> "wyczerpane pola przejścia" x5, bez ruchu. Nowy: pola z trasy, Use pierwsze.
Stary kod ładowany z kopii pietra.py.bak-20261022-kratka-kandydaci (gdy jest)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types, json, glob
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa, pietra

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

M = _mapa.mapa()
A, B = (32060, 32174, 7), (32060, 32172, 8)       # z logu: stoimy w (32060,32174,7), punkt trasy 5
sprawdz("mapa: pole nad punktem trasy to ściana (flaga 4)", pietra._flaga(M, 32060, 32172, 7) & 4, pietra._flaga(M, 32060, 32172, 7))
sprawdz("mapa: pole między A i B chodliwe, bez flagi 2", pietra._flaga(M, 32060, 32173, 7) == 1, pietra._flaga(M, 32060, 32173, 7))

stary = _os.path.join(_R, "pietra.py.bak-20261022-kratka-kandydaci")
if _os.path.isfile(stary):
    from importlib.machinery import SourceFileLoader
    from importlib.util import spec_from_loader, module_from_spec
    ld = SourceFileLoader("pietra_stare", stary); mod = module_from_spec(spec_from_loader("pietra_stare", ld)); ld.exec_module(mod)
    sprawdz("stary kod (kopia): kandydaci [] jak w logu", mod.kandydaci(M, A, B, A, 3) == [], mod.kandydaci(M, A, B, A, 3))

k = pietra.kandydaci(M, A, B, A, 3)
sprawdz("nowy kod: niepusta lista", len(k) >= 1, k)
sprawdz("pierwszy kandydat = kratka (32060,32173,z7), domysł, lądowanie pod nią", k and k[0]["pole"] == (32060, 32173, 7)
        and not k[0]["pewne"] and k[0]["lad"] == (32060, 32173, 8), k[:1])
sprawdz("kandydaci blisko gracza (cheb <= 3) i chodliwi", all(pietra.cheb(x["pole"], A) <= 3 and pietra._flaga(M, *x["pole"]) & 1 for x in k))

# trzy sposoby: domysł w dół zaczyna od Use (ctrl+klik na kratkę), potem krok
p = types.SimpleNamespace(cb=types.SimpleNamespace(mapa=M), _dane=lambda: True, _k=lambda n, d: d, ops=None)
for nazwa in ("_tryby", "_stosuje", "_wybierz"):
    setattr(p, nazwa, types.MethodType(getattr(pietra.Pietra, nazwa), p))
tr = p._tryby(k[0], {"z0": 7})
sprawdz("tryby dla kratki z trasy: pierwszy 'use', jest 'krok'", tr and tr[0] == "use" and "krok" in tr, tr)

# bez regresji: wszystkie skoki pięter w trasy/*.json mają kandydata (poz = punkt a)
puste = []
for f in sorted(glob.glob(_os.path.join(_R, "trasy", "*.json"))):
    try:
        t = json.load(open(f))
    except Exception:
        continue
    if not (isinstance(t, list) and t and isinstance(t[0], list) and len(t[0]) == 3):
        continue
    for i in range(1, len(t)):
        if t[i - 1][2] != t[i][2] and not pietra.kandydaci(M, tuple(t[i - 1]), tuple(t[i]), tuple(t[i - 1]), 3):
            puste.append((_os.path.basename(f), i))
sprawdz("żaden skok piętra w trasy/*.json nie ma pustej listy kandydatów", not puste, puste)

# pusta lista naprawdę (mapa-atrapa: wszędzie ściana): jasny komunikat i porażka, nie ciche wyczerpanie
class Sciana:
    def flagi(self, x, y, z): return 4
logi = []
cb = types.SimpleNamespace(punkty=[A, B], idx=1, mapa=Sciana(), zegar=lambda: 0.0, pauza=lambda *a: None, pietra_porazki=0,
                           _wypad_reset_klik=lambda: None, _pietra_zawroc=lambda poz: None, _trasa_stop_potwor=lambda poz: False)
pt = pietra.Pietra(cb, log=logi.append)
r = pt.tick(A, B)
sprawdz("bez żadnego pola: porażka z jasnym komunikatem 'BEZ kandydatów'", any("BEZ kandydatów" in l for l in logi)
        and any("brak pola przejścia" in l for l in logi), logi)
logi2 = []
cb2 = types.SimpleNamespace(punkty=[A, B], idx=1, mapa=M, zegar=lambda: 0.0, pauza=lambda *a: None, pietra_porazki=0,
                            _wypad_reset_klik=lambda: None, _pietra_zawroc=lambda poz: None, _trasa_stop_potwor=lambda poz: False)
try:
    pt2 = pietra.Pietra(cb2, log=logi2.append); pt2.tick(A, B)
except Exception as e:                                   # dalsza część tick wymaga pełnego cb; liczy się linia o kandydatach
    logi2.append(f"wyjątek po liście kandydatów: {type(e).__name__}")
sprawdz("tick na prawdziwej mapie loguje kandydata (32060, 32173), nie []", any("(32060, 32173)" in l and "kandydaci" in l for l in logi2), logi2[:2])

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
