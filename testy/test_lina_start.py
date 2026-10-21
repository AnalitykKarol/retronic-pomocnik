"""Lina przed startem (21.10): Kolanosh 17:05 na `trolle_edron_z9w` bez liny, dojście wchodzi liną z11 -> z7, utknął na
(33134,31806,z11). mozg.sprawdz_line: trasa przy znanym polu liny + brak liny w pamięci gry = bot nie rusza (powiadomienie).
Prawdziwe trasy i dane lin, atrapa odczytu pamięci."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, types
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import liny, mozg

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

def trasa(n):
    return json.loads(open(_os.path.join(_R, "trasy", f"{n}.json")).read())

znane = liny.znane_liny()
sprawdz("znane liny: 4 liny dojścia z9w (z11->z7)", {(33133, 31805, 11), (33130, 31809, 10), (33131, 31806, 9), (33128, 31810, 8)} <= znane,
        sorted(znane))
w = liny.wymaga_liny(trasa("trolle_edron_z9w_dojscie"), znane)
sprawdz("dojście trolle_edron_z9w wymaga liny (4 przejścia)", len(w) == 4, w)
sprawdz("kanały Thais (raty) i Rook raty z9 bez liny", not liny.wymaga_liny(trasa("thais_dojscie_kratka"), znane)
        and not liny.wymaga_liny(trasa("thais_szczury_opt"), znane) and not liny.wymaga_liny(trasa("rook_raty_z9_dojscie"), znane))

a = types.SimpleNamespace(trasa="trolle_edron_z9w_petla", dojscie="trolle_edron_z9w_dojscie")
pts = trasa("trolle_edron_z9w_petla")
logi = []
sprawdz("brak liny (Kolanosh 17:05): nie startuje", mozg.sprawdz_line(a, pts, logi.append, ma_line=lambda: False) is False, logi[-1:])
sprawdz("brak liny: log mówi dlaczego", logi and "Nie startuję" in logi[-1])
sprawdz("lina jest: startuje", mozg.sprawdz_line(a, pts, logi.append, ma_line=lambda: True) is True)
sprawdz("brak odczytu pamięci: startuje jak dotąd", mozg.sprawdz_line(a, pts, logi.append, ma_line=lambda: None) is True)
wolany = []
b = types.SimpleNamespace(trasa="thais_szczury_opt", dojscie="thais_dojscie_kratka")
sprawdz("trasa bez liny: nie pyta o ekwipunek, startuje",
        mozg.sprawdz_line(b, trasa("thais_szczury_opt"), logi.append, ma_line=lambda: wolany.append(1) or False) is True and not wolany)
c = types.SimpleNamespace(trasa="trolle_edron_z9w_petla", dojscie=None)
sprawdz("na spocie (dojście pominięte), pętla bez liny: startuje bez pytania",
        mozg.sprawdz_line(c, pts, logi.append, ma_line=lambda: wolany.append(1) or False) is True and not wolany)
def boom():
    raise RuntimeError("x")
sprawdz("błąd sprawdzenia nie blokuje startu", mozg.sprawdz_line(a, pts, logi.append, ma_line=boom) is True)

# odczyt pamięci (atrapa odpowiedzi rdzenia)
sprawdz("ma_line: lina w plecaku", liny.ma_line(lambda z: {"kontenery": [{"przedmioty": [{"id": 3003, "slot": 2}]}], "ekwipunek": {}}) is True)
sprawdz("ma_line: lina w slocie ekwipunku", liny.ma_line(lambda z: {"kontenery": [], "ekwipunek": {"10": {"id": 3003}}}) is True)
sprawdz("ma_line: brak liny", liny.ma_line(lambda z: {"kontenery": [{"przedmioty": [{"id": 3031, "slot": 0}]}],
                                                       "ekwipunek": {"1": {"id": 3355}}}) is False)
sprawdz("ma_line: błąd odczytu = None", liny.ma_line(lambda z: {"blad": "x"}) is None)
sprawdz("ma_line: wyjątek = None", liny.ma_line(lambda z: boom()) is None)
sprawdz("LINA_SPRAWDZ włączone", mozg.LINA_SPRAWDZ == 1)

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
