"""Jednorazowo (13.10): stoi w depo -> staje przy skrzyni i składa UH (wyprawa.OperacjeZywe.zloz_w_depo)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot, mozg, wyprawa

postac = bot.Postac()
ops = wyprawa.OperacjeZywe(log=print, wyslij=lambda t: mozg.wpisz_na_czacie(t))
cel = wyprawa.POLE_ZLOZ_DEPO
for _ in range(8):
    x, y, z = postac.pozycja()
    print("poz", (x, y, z), flush=True)
    if (x, y, z) == tuple(cel):
        break
    dx, dy = cel[0] - x, cel[1] - y
    kier = ("Right" if dx > 0 else "Left") if dx else ("Down" if dy > 0 else "Up")
    postac.krok(kier)
    time.sleep(0.5)
print(ops.zloz_w_depo(postac.pozycja), flush=True)
