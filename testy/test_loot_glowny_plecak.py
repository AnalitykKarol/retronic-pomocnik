import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""15.10: pełny bag na runy (blue backpack: UH 3160 + blanki 3147) nie jest głównym plecakiem lootu, a gold
trafia na istniejący stos w głównym plecaku. Syntetyczny zrzut + atrapa pamięci. Uruchom: python3 -I test_loot_glowny_plecak.py"""
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from PIL import Image, ImageDraw
import loot

def okno_syn(im, x, y, wiersze, zajete=()):
    d = ImageDraw.Draw(im)
    for r in range(wiersze):
        for c in range(4):
            x0, y0 = x + c * 37, y + r * 37
            d.rectangle((x0, y0, x0 + 33, y0 + 33), outline=loot.RAMKA)
            if r * 4 + c in zajete:
                d.rectangle((x0 + 8, y0 + 8, x0 + 24, y0 + 24), fill=(200, 60, 160))
                d.rectangle((x0 + 12, y0 + 12, x0 + 20, y0 + 20), fill=(60, 200, 120))

def kont(numer, nazwa, ident, poj, *przedm):
    return {"numer": numer, "nazwa": nazwa, "id": ident, "pojemnosc": poj,
            "przedmioty": [{"slot": i, "id": a, "ilosc": b} for i, (a, b) in enumerate(przedm)]}

ok = True
def sprawdz(opis, warunek, info=""):
    global ok
    print(("OK    " if warunek else "BŁĄD "), opis, "" if warunek else info)
    ok &= bool(warunek)

PAMIEC = []
loot._zapytaj = lambda z: {"kontenery": PAMIEC}

runy20 = [(3160, 1)] * 4 + [(3147, 1)] * 16
blue = kont(0, "blue backpack", 2854, 20, *runy20)
backpack = kont(1, "backpack", 2854, 20, (3031, 11), (3031, 24), (3035, 1), (2869, 1), (3457, 1))
zwloki = kont(2, "dead troll", 3994, 8, (3031, 7))

sprawdz("1a pełny bag z samymi runami to bag na runy", loot.czy_runy(blue) and not loot.czy_runy(backpack))
mieszany = kont(0, "blue backpack", 2854, 20, *(runy20[:15] + [(3031, 5), (2120, 1), (3457, 1), (2869, 1), (3035, 1)]))
sprawdz("1b bag z runami w większości (+ loot) nadal bag na runy", loot.czy_runy(mieszany))
sprawdz("1c plecak z jedną blank rune z lootu nie jest bagiem na runy",
        not loot.czy_runy(kont(1, "backpack", 2854, 20, (3147, 1), (3031, 11), (3031, 24), (2869, 1))))

# okna: blue (5 wierszy, pełne), backpack (5 wierszy, 5 zajętych), zwłoki (2 wiersze)
im = Image.new("RGB", (734, 1100), (20, 20, 20))
okno_syn(im, 580, 100, 5, zajete=range(20))
okno_syn(im, 580, 340, 5, zajete=range(5))
okno_syn(im, 580, 580, 2, zajete=(0,))
PAMIEC[:] = [blue, backpack, zwloki]
p = loot.plan(im)
sprawdz("2a plan z pamięci", p["zrodlo"] == "pamiec", p["pamiec"])
sprawdz("2b główny plecak to backpack, nie blue", p["plecak"] is not None and p["plecak"].kontener is backpack, p["plecak"])
sprawdz("2c blue backpack ma rolę runy", p["runy"] is not None and p["runy"].kontener is blue)
sprawdz("2d gold ze zwłok idzie na stos (slot 0 x11 albo 1 x24), nie na wolny slot",
        p["cel"] is not None and p["cel_stos"] in (11, 24) and p["cel"] in (p["plecak"].sloty[0], p["plecak"].sloty[1]), p["cel_stos"])

# kolejność okien odwrotna (backpack nad blue): ten sam wynik
backpack2 = dict(backpack, numer=0); blue2 = dict(blue, numer=1)
im2 = Image.new("RGB", (734, 1100), (20, 20, 20))
okno_syn(im2, 580, 100, 5, zajete=range(5))
okno_syn(im2, 580, 340, 5, zajete=range(20))
okno_syn(im2, 580, 580, 2, zajete=(0,))
PAMIEC[:] = [backpack2, blue2, zwloki]
p = loot.plan(im2)
sprawdz("3a odwrócona kolejność: nadal backpack", p["zrodlo"] == "pamiec" and p["plecak"].kontener is backpack2, p["pamiec"])

# sortowanie: nawet gdyby oba miały rolę plecaka, runowy przegrywa mimo większej liczby rzeczy
sprawdz("4a _wyglada_na_runy", loot._wyglada_na_runy(blue) and not loot._wyglada_na_runy(backpack))

# plan z obrazka (pamięć niezgodna): okno z zajętością bagu na runy dostaje rolę runy
PAMIEC[:] = [blue, backpack, zwloki]
okna = loot.znajdz_okna(im)
for o in okna:
    o.rola = "plecak" if len(o.sloty) == 20 else "zwloki"
loot._role_luzno_z_pamieci(im, okna, PAMIEC)
sprawdz("5a rola luźno z pamięci: pełne okno = runy, drugie plecak",
        [o.rola for o in okna] == ["runy", "plecak", "zwloki"], [o.rola for o in okna])

print("WSZYSTKO OK" if ok else "SĄ BŁĘDY")
sys.exit(0 if ok else 1)
