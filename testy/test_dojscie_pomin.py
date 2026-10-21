"""Start bota na spocie bez dojścia (21.10, DIAGNOZA_dawajkesh_walka_7_trolli_1021): dojście biegnie bez walki i lootu, więc restart
na spocie (dawajkesh 13:34, (33094,31753,8), mapa trolle_edron z dojściem z dowolnego piętra) mijał rannego trolla.
mozg.DOJSCIE_POMIN_ODL: postać na piętrze trasy głównej <= tylu pól od niej = bez dojścia. Prawdziwe trasy, atrapa postaci."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, types
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mozg
from pathlib import Path

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

TRASY = Path(_R) / "trasy"
def trasa(n):
    return json.loads((TRASY / f"{n}.json").read_text())

def pomija(poz, punkty):
    postac = types.SimpleNamespace(pozycja=lambda: poz)
    return mozg.DOJSCIE_POMIN_ODL > 0 and mozg.blisko_trasy(postac, punkty, mozg.DOJSCIE_POMIN_ODL)

sprawdz("DOJSCIE_POMIN_ODL = 10", mozg.DOJSCIE_POMIN_ODL == 10)
edron = trasa("edron_trolle_petla")
dojscie_edron = trasa("edron_depo_trolle")
sprawdz("dawajkesh 13:34 (33094,31753,8) na spocie Edron: bez dojścia", pomija((33094, 31753, 8), edron))
start = tuple(dojscie_edron[0])
sprawdz(f"początek dojścia Edron {start} (depo): dojście zostaje", not pomija(start, edron))
z7 = [tuple(p) for p in dojscie_edron if p[2] == 7]
sprawdz("żaden punkt dojścia Edron na z7 nie pomija dojścia", z7 and not any(pomija(p, edron) for p in z7), len(z7))

thais = trasa("thais_szczury_opt")
sprawdz("Thais: ulica nad kanałami (32370,32214,7): dojście zostaje", not pomija((32370, 32214, 7), thais))
sprawdz("Thais: kolanoth w kanałach (32368,32219,8): bez dojścia", pomija((32368, 32219, 8), thais))

stare = mozg.DOJSCIE_POMIN_ODL
mozg.DOJSCIE_POMIN_ODL = 0
sprawdz("DOJSCIE_POMIN_ODL = 0: dojście zawsze (jak przed 21.10)", not pomija((33094, 31753, 8), edron))
mozg.DOJSCIE_POMIN_ODL = stare

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
