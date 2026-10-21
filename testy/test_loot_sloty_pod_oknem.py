import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""21.10 dawajkesh: okno zwłok zaczynało się dokładnie 33 px pod dolną krawędzią ostatniego rzędu plecaka, więc
_sloty() brało jego górną krawędź za dolną krawędź nieistniejącego slotu i gubiło cały rząd ('okno_niewidoczne').
Zrzut: panel prawy (x=990..1175) z 3 oknami. Uruchom: python3 -I test_loot_sloty_pod_oknem.py"""
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import os
from PIL import Image
import loot

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dane", "panel_zwloki_pod_plecakiem_1021.png")
crop = Image.open(p).convert("RGB")
im = Image.new("RGB", (1175, 910)); im.paste(crop, (990, 0))
okna = loot.znajdz_okna(im)
ok = len(okna) == 3 and len(okna[2].sloty) == 4 and okna[2].sloty[0].y == 739
print("OK  " if ok else "BŁĄD", "okno zwłok pod pełnym plecakiem wykryte:", [(len(o.sloty), o.sloty[0].y) for o in okna])
sys.exit(0 if ok else 1)
