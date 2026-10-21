"""Zejście kratką z planu wpadnięcia (21.10, kolanoth 13:04 i 13:37): przejście z trasy jest "pewne", a pewne w dół próbowało tylko kroku
i łopaty; krok na kratkę (32370,32213,z7) nie otwiera jej, lista prób pusta po 1 kroku, ALARM i STOP. Teraz pewne w dół bez dziury
na mapie (flaga 2) = kratka/klapa: najpierw Use. Prawdziwa mapa (mapa.py), atrapa Pietra (tylko _tryby/_wybierz)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa, pietra

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

M = _mapa.mapa()
def atrapa(dane=True):
    p = types.SimpleNamespace(cb=types.SimpleNamespace(mapa=M), _dane=lambda: dane, _k=lambda n, d: d, ops=None)
    for nazwa in ("_tryby", "_stosuje", "_wybierz"):
        setattr(p, nazwa, types.MethodType(getattr(pietra.Pietra, nazwa), p))
    return p

KRATKA = (32370, 32213, 7)
k = {"pole": KRATKA, "pewne": True, "lad": (32370, 32213, 8)}
st = {"z0": 7}
sprawdz("mapa: kratka Thais bez flagi 2", not pietra._flaga(M, *KRATKA) & 2, pietra._flaga(M, *KRATKA))
tr = atrapa()._tryby(k, st)
sprawdz("pewne w dół bez dziury na mapie (kratka): pierwsza próba Use", tr and tr[0] == "use", tr)
sprawdz("kratka: jest też krok (druga szansa)", "krok" in tr, tr)

# przypadek 13:37: krok wprowadził postać NA kratkę; lista ma jeszcze zastosowanie (Use na polu przejścia)
p = atrapa()
st2 = {"z0": 7, "tryby": list(tr), "proby": 1}
sprawdz("stojąc na kratce po kroku: lista prób nie jest wyczerpana",
        p._wybierz(st2, k, KRATKA, 0.0) is not None, st2["tryby"])
stare = list(pietra.TRYBY_DOL_DANE)
st3 = {"z0": 7, "tryby": stare, "proby": 1}
sprawdz("kontrola: stara lista (krok, łopata, ...) na kratce = wyczerpana (błąd 13:37)", p._wybierz(st3, k, KRATKA, 0.0) is None, st3["tryby"])

# pewna dziura z flagą 2 (jaskinia trolli (32484,32265,z8), mapa_doswiadczenia: dziura+drabina) bez zmian: najpierw krok
DZIURA = (32484, 32265, 8)
kd = {"pole": DZIURA, "pewne": True, "lad": (32484, 32265, 9)}
sprawdz("mapa: dziura trolli ma flagę 2", pietra._flaga(M, *DZIURA) & 2, pietra._flaga(M, *DZIURA))
sprawdz("pewna dziura z flagą 2: jak dotąd TRYBY_DOL_DANE (krok pierwszy)", atrapa()._tryby(kd, {"z0": 8}) == list(pietra.TRYBY_DOL_DANE))
sprawdz("niepewne w dół: jak dotąd TRYBY_DOL_DANE_DOMYSL",
        atrapa()._tryby(dict(k, pewne=False), st) == list(pietra.TRYBY_DOL_DANE_DOMYSL))
sprawdz("bez danych (PIETRA_TRYBY_Z_DANYCH=0): kratka pewna = lista niepewnych (use pierwsze)",
        atrapa(False)._tryby(k, st) == list(pietra.TRYBY_DOL[False]))
sprawdz("bez danych: dziura z flagą 2 jak dotąd", atrapa(False)._tryby(kd, {"z0": 8}) == list(pietra.TRYBY_DOL[True]))
ku = {"pole": (32370, 32213, 8), "pewne": True, "lad": (32370, 32214, 7)}
sprawdz("w górę bez zmian (drabina pod kratką)", atrapa()._tryby(ku, {"z0": 8})[0] in ("R", "krok"))

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
