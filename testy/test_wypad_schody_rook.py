"""Wyprawa do depo na Rooku (21.10, kutangen; Karol: „tam są schody”): przejście w górę (32027,32198,z8) -> z7 to schody na
(32027,32197,z8) (flaga 2 na mapie), a etap LINA celował w „drabinę” (32027,32196,z8), 2 pola od pola stania: brak próby przez 60 s,
ALARM 11:06:10. Na (32029,32195,z9) działało tylko Use na własnym polu (próba 5/7, 40-80 s). Teraz: schody = krok, a przy nagraniu
bez zmiany (x, y) Use własnego pola jako druga próba. Prawdziwa mapa (mapa.py) i trasa, atrapa wyprawy (tylko _lina)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, types
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa, wypad

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

M = _mapa.mapa()
pts = [tuple(p) for p in json.load(open(_os.path.join(_R, "trasy", "rook_raty_z9_dojscie_odwrocona.json")))]
et = wypad.zbuduj_etapy(pts, M)
liny = {e["stoi"]: e for e in et if e["typ"] == "LINA"}
Z8, Z9 = (32027, 32198, 8), (32029, 32195, 9)
e8, e9 = liny.get(Z8), liny.get(Z9)
sprawdz("trasa ma oba przejścia w górę", e8 and e9, list(liny))
sprawdz("z8: schody (32027,32197) z flagą 2 = cel etapu, obok pola stania", e8 and e8.get("schody") and e8["cel"] == (32027, 32197, 8), e8)
sprawdz("z8: plan bez uwag (cel sąsiaduje z polem stania)", not [b for b in wypad.sprawdz_plan(et, M) if "32027, 32198" in b],
        wypad.sprawdz_plan(et, M))
p8 = wypad.Wypad._proby_drabiny(Z8, e8["cel"], e8)
sprawdz("z8: pierwsza próba to krok na schody", p8[0] == ("krok", (32027, 32197, 8)), p8[:3])
sprawdz("z9: nagranie bez zmiany (x, y) -> Use własnego pola jako 2. próba", e9 and e9.get("wlasne")
        and [t for t, _ in wypad.Wypad._proby_drabiny(Z9, e9["cel"], e9)][:2] == ["drabina", "wlasne"])
t9 = [t for t, _ in wypad.Wypad._proby_drabiny(Z9, e9["cel"], e9)]
sprawdz("z9: pełna kolejność bez duplikatu własnego pola", t9[:5] == ["drabina", "wlasne", "lina", "lina", "drabina"]
        and t9.count("wlasne") == 1, t9)
sprawdz("z9: nie schody (pole lądowania bez flagi 2)", not e9.get("schody"), e9)
bez = {e["stoi"]: e for e in wypad.zbuduj_etapy(pts) if e["typ"] == "LINA"}
sprawdz("bez mapy: z8 jak dawniej (drabina b.y-1, bez schodów)", bez[Z8]["cel"] == (32027, 32196, 8) and not bez[Z8].get("schody"))
sprawdz("bez etapu (stare wywołanie): kolejność jak 17.10", [t for t, _ in wypad.Wypad._proby_drabiny(Z8, (32027, 32196, 8))][:3]
        == ["drabina", "lina", "lina"])

# atrapa wyprawy: _lina na z8 wysyła strzałkę Up (krok na schody), nie Ctrl+klik
kroki, uzycia = [], []
w = types.SimpleNamespace(
    cb=types.SimpleNamespace(postac=types.SimpleNamespace(krok=kroki.append), pauza=lambda *a: None),
    ops=types.SimpleNamespace(uzyj_pole=lambda *a: uzycia.append(a), uzyj_line=lambda *a: uzycia.append(("lina",) + a)),
    log=lambda *a: None, pj_proby=0, ei=1, etapy=et, _zajete_pola=lambda poz: set(), _k=lambda n, d: d,
    _pilnuj_przejscia=lambda *a: None, _nie_czas=lambda *a: False, _po_przejsciu=lambda *a: True)
for n in ("_lina", "_kier_do_pola"):
    setattr(w, n, types.MethodType(getattr(wypad.Wypad, n), w))
w._proby_drabiny = wypad.Wypad._proby_drabiny
e = dict(e8)
w._lina(Z8, e, 0.0)
sprawdz("_lina z8: strzałka Up, bez Use", kroki == ["Up"] and not uzycia, (kroki, uzycia))

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
