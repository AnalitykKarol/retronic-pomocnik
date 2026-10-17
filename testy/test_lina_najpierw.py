"""Kolejność prób przejścia w górę (17.10): jedna próba drabiny, zaraz potem lina. Na trasie goblinów Edron przy każdej z 4 lin
bot tracił 30-60 s na sześć prób drabiny, a przy drabinie (z8 -> z7, (33165,31827)) pierwsza próba od razu działała."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wypad

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

POZ, CEL = (33107, 31846, 8), (33107, 31847, 8)
p = wypad.Wypad._proby_drabiny(POZ, CEL)
t = [x for x, _ in p]
sprawdz("L1 pierwsza próba to drabina (drabina działa od 1. próby), druga i trzecia to lina", t[:3] == ["drabina", "lina", "lina"], t)
sprawdz("L2 lina pada najpóźniej w 2. próbie (dawniej w 7.)", t.index("lina") == 1, t)
sprawdz("L3 zapas jak dawniej: drabina, pole własne, E, W, N", t[3:] == ["drabina", "wlasne", "E", "W", "N"], t)
sprawdz("L4 lina i drabina celują w pole obok (33107,31847,8)", all(c == CEL for n, c in p if n in ("lina", "drabina")), p)
p2 = wypad.Wypad._proby_drabiny((33150, 31820, 10), (33151, 31820, 10))
sprawdz("L5 sąsiad pokrywający się z polem celu jest pomijany (E dla celu na E)", "E" not in [x for x, _ in p2] and len(p2) == 7, [x for x, _ in p2])
print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
