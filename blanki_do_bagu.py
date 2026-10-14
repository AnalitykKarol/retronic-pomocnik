"""Jednorazowo: blanki z głównego plecaka (numer 0) do drugiego bagu (numer 1), także pustego."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loot
print(loot.przenies_miedzy({3147}, lambda k: k.get("numer") == 0, lambda k: k.get("numer") == 1, maks=20, log=print), flush=True)
kon, _ = loot.kontenery_z_pamieci()
for k in kon: print(k["numer"], k.get("nazwa"), [(q["id"], q.get("ilosc", 1)) for q in k.get("przedmioty", [])])
