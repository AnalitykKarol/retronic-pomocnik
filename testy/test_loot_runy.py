import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""Pojemnik na runy (Purple backpack, id 2868) w lootcie: nie zwłoki, nie plecak lootu, nie zamykany.
Syntetyczny zrzut + atrapa pamięci, bez gry. Uruchom: python3 -I test_loot_runy.py"""
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from PIL import Image, ImageDraw
import loot

ok = True
def sprawdz(opis, warunek, info=""):
    global ok
    print(("OK    " if warunek else "BŁĄD "), opis, "" if warunek else info)
    ok &= bool(warunek)

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

PAMIEC = []
loot._zapytaj = lambda z: {"kontenery": PAMIEC}

# 0. rozpoznawanie
sprawdz("0a czy_runy po ID i nazwie", loot.czy_runy({"id": 2868}) and loot.czy_runy({"nazwa": "Purple backpack"})
        and loot.czy_runy({"nazwa": "purple backpack (2)"}) and not loot.czy_runy({"nazwa": "backpack", "id": 2854})
        and not loot.czy_runy({"nazwa": "dead rat", "id": 3994}))
sprawdz("0b role z tytułu", loot.rola_z_tytulu("purple backpack") == "runy" and loot.rola_z_tytulu("backpack") == "plecak"
        and loot.rola_z_tytulu("bag") == "plecak" and loot.rola_z_tytulu(None) == "zwloki")
sprawdz("0c purple nie jest plecakiem lootu", not loot.czy_plecak({"nazwa": "purple backpack", "id": 2868}))

# 1. plecak (okno górne) + purple (okno dolne), pamięć: purple pierwszy (numer 0) i plecak
im = Image.new("RGB", (734, 910), (20, 20, 20))
okno_syn(im, 580, 360, 2, zajete=(0, 1))
okno_syn(im, 580, 560, 2, zajete=(0, 1, 2))
bag = kont(1, "backpack", 2854, 8, (3031, 74), (3035, 4))
purple = kont(0, "purple backpack", 2868, 8, (3198, 1), (3198, 1), (3198, 1))
PAMIEC[:] = [purple, bag]
p = loot.plan(im)
sprawdz("1a plan z pamięci: źródło pamięć", p["zrodlo"] == "pamiec", p["pamiec"])
sprawdz("1b okno pojemnika ma rolę runy, plecak to główny backpack",
        p["runy"] is p["okna"][1] and p["runy"].rola == "runy" and p["plecak"] is p["okna"][0], p["okna"])
sprawdz("1c pojemnik nie jest zwłokami: brak zwłok i przedmiotu", p["zwloki"] is None and p["przedmiot"] is None)
sprawdz("1d _zwloki_w pomija plecak i pojemnik na runy",
        loot._zwloki_w([purple, bag, kont(2, "dead rat", 3994, 5, (3031, 3))]).keys() == {(2, 3994)})

# 2. nie zamykamy go: nawet gdy plan wskaże go jako zwłoki (nierozpoznany)
kliki = []
loot.zamknij_okno = lambda mysz, okno: kliki.append(okno) or True
loot._plan_teraz = lambda mysz, lista, log: (None, {"zwloki": p["runy"]})
sprawdz("2a _zamknij_okno_z_planu nie klika pojemnika", loot._zamknij_okno_z_planu(None, loot.DO_ZEBRANIA, print) is False and not kliki)

# 3. wariant bez pojemnika: sam plecak (+ zwłoki), działa jak dotąd
im2 = Image.new("RGB", (734, 910), (20, 20, 20))
okno_syn(im2, 580, 360, 2, zajete=(0, 1))
okno_syn(im2, 580, 560, 2, zajete=(0,))
zw = kont(3, "dead rat", 3994, 8, (3031, 3))
PAMIEC[:] = [zw, bag]
p2 = loot.plan(im2, lista=("gold coin",))
sprawdz("3a bez pojemnika: zwłoki i plecak jak dotąd", p2["zrodlo"] == "pamiec" and p2["runy"] is None
        and p2["zwloki"] is p2["okna"][1] and p2["plecak"] is p2["okna"][0], (p2["pamiec"], p2["okna"]))

# 4. pojemnik otwarty na ekranie, a pamięć go nie widzi (stary odczyt): bez wyjątku, plan z obrazu
PAMIEC[:] = [bag]
p3 = loot.plan(im)
sprawdz("4 pamięć bez pojemnika: bez wyjątku, fallback obrazkowy", p3["zrodlo"] == "obraz" and p3["pamiec"])

# 5. pojemnik w pamięci, a okna nie ma na ekranie: ignorowany, dopasowanie działa
im4 = Image.new("RGB", (734, 910), (20, 20, 20))
okno_syn(im4, 580, 360, 2, zajete=(0, 1))
PAMIEC[:] = [purple, bag]
p4 = loot.plan(im4)
sprawdz("5 bez okna pojemnika na ekranie: plecak dopasowany", p4["zrodlo"] == "pamiec" and p4["plecak"] is p4["okna"][0]
        and p4["zwloki"] is None and p4["runy"] is None, p4["pamiec"])

print("WYNIK:", "OK" if ok else "BŁĄD")
sys.exit(0 if ok else 1)
