"""Pole liny (Karol 21.10): liny nie da się użyć na polu, na którym postać stoi (ani gdy ktoś stoi albo coś leży na nim).
Logi: wpadnięcie „lina, próba 1/3 na polu (32508,32273) z (32508,32273,9)” i (32086,32197,z9): 3 próby z samego pola bez skutku.
Sprawdzamy: wpadnięcie najpierw schodzi z pola liny, lista „trzy sposoby” i pietra nie dają liny z własnego pola."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import tempfile, wypad, pietra, wpadniecie

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

pusty = _os.path.join(tempfile.mkdtemp(), "p.json")
L = wypad.proby_trzy_sposoby((10, 10, 9), [(10, 10, 9), (10, 9, 9)], 8, plik=pusty)
sprawdz("trzy sposoby: brak liny na własnym polu", ("lina", (10, 10, 9)) not in L, L)
sprawdz("trzy sposoby: lina na polu obok zostaje", ("lina", (10, 9, 9)) in L, L)
# 22.10: slot liny zostaje w liście także na polu przejścia (próba sama schodzi krokiem obok, testy/test_lina_z_pola.py);
# sam krok z własnego pola nadal odpada
sprawdz("pietra: lina zostaje w liście na polu przejścia (zejście obok robi _proba)",
        pietra.Pietra._stosuje(types.SimpleNamespace(_k=lambda n, d: d), "lina", (5, 5, 9), (5, 5, 9), 0.0))
sprawdz("pietra: krok z własnego pola nie ma zastosowania",
        not pietra.Pietra._stosuje(types.SimpleNamespace(_k=lambda n, d: d), "krok", (5, 5, 9), (5, 5, 9), 0.0))
sprawdz("pietra: lina z pola obok tak",
        pietra.Pietra._stosuje(types.SimpleNamespace(_k=lambda n, d: d), "lina", (5, 6, 9), (5, 5, 9), 0.0))

# wpadnięcie: postać wylądowała NA rope spocie -> najpierw krok obok, dopiero potem lina
kroki, liny = [], []
W = wpadniecie.Wpadniecie.__new__(wpadniecie.Wpadniecie)
W.cb = types.SimpleNamespace(krok_do=lambda c: kroki.append(c) or True, zegar=lambda: 0.0, zatrzymaj_klik=lambda p: None,
                             klik_cel=None, pauza=lambda *a: None)
W.st = {"lad": (32508, 32273), "z1": 9, "lina": 0, "dojscie": 0}
W.dziury, W.drabiny = set(), set()
W.log = lambda *a: None
W._tele = lambda *a, **k: None
W._k = lambda n, d: d
W._flaga_mapy = lambda x, y, z: 1
W._wczytaj_przejscia = lambda: []
W._uzyj_liny = lambda spot, p: liny.append(spot)
P = (32508, 32273, 9)
W._lina(P, 0.0)
sprawdz("wpadnięcie na polu liny: pierwszy ruch = krok obok, bez liny", kroki and not liny, (kroki, liny))
try:
    W._lina((kroki[0][0], kroki[0][1], 9), 1.0)
except Exception:
    pass
sprawdz("potem lina z pola obok", liny, (kroki, liny))

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
