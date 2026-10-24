#!/usr/bin/env python3
"""23.10 zgon odchyda (thais_pn_z8, 15:49:33): po zabiciu trolla loot robił Ctrl+klik po polach wokół gracza; pole (-1,0) to dziura
(32354,32131,z8) - mapa klienta ma tam flagi 5 (ściana), kolor 186 - i postać spadła na z9 do zamkniętej kieszeni ze Skorpionem.
Odtwarza prawdziwe pozycje: gracz (32355,32131,8), zwłoki (-1,1), próby (-1,1), (0,0), (-1,0), (0,1).
Sprawdza: (1) hak loot.POLE_ZAKAZANE: pole dziury nie dostaje Ctrl+klika (żadna ścieżka lootu), (2) bez haka zachowanie jak dotąd,
(3) cavebot._loot_pole_zakazane: wpis z trasy/dziury_omijaj.json oraz reguła 'ściana wg mapy' (poza polem zwłok), (4) wpis w danych.
Atrapy; bez gry i bez gniazd."""
import json
import os
import sys

os.environ["RETRONIC_TESTY"] = "1"
sys.dont_write_bytecode = True
KAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KAT)
import ekran
import loot

GRACZ = (32355, 32131, 8)
DZIURA = (32354, 32131, 8)
klik = []
stan = {"zwloki_na": None, "stwory": []}
k = loot.kont


def zapytaj(z):
    if z["cmd"] == "kontenery":
        lista = [k(1, "bag", 2853, 8)]
        if stan.get("otwarte"):
            lista.append(k(2, "troll", 3994, 5))
        return {"kontenery": lista}
    if z["cmd"] == "stwory":
        return {"stwory": stan["stwory"]}
    raise AssertionError(z)


def otworz(dx, dy):
    klik.append((dx, dy))
    cel = (GRACZ[0] + dx, GRACZ[1] + dy)
    if cel == stan["zwloki_na"]:
        stan["otwarte"] = True


ekran.otworz = otworz
loot.POD_NOGAMI_PIERWSZE = False
loot._pauza = lambda a=0, b=0: None
loot._zapytaj = zapytaj
loot._pozycja_gracza = lambda: GRACZ
ok = []


def sprawdz(opis, warunek, info=""):
    print(("OK    " if warunek else "BŁĄD ") + opis + ("" if warunek else f"  [{info}]"))
    ok.append(bool(warunek))


def scenariusz(zwloki_na, dx, dy, hak):
    klik.clear()
    stan.update(zwloki_na=zwloki_na, otwarte=False, stwory=[])
    loot.POLE_ZAKAZANE = hak
    logi = []
    wynik = loot._otworz_z_pamiecia(dx, dy, GRACZ, {}, True, logi.append)
    return wynik, logi


# 1. dziura na liście: pole (-1,0) nie dostaje klika (zwłok nigdzie nie ma = pełny obchód 3x3 i pola dalsze)
hak = lambda x, y, z, glowne=False: (x, y, z) == DZIURA
(pole, kont), logi = scenariusz((1, 1), -1, 1, hak)
sprawdz("dziura (-1,0): ŻADEN Ctrl+klik w to pole (3x3 + pola dalsze)", (-1, 0) not in klik, klik)
sprawdz("dziura (-1,0): reszta pól 3x3 klikana normalnie", {(-1, 1), (0, 0), (0, 1), (1, 1)} <= set(klik) or (0, 1) in klik, klik)
sprawdz("dziura (-1,0): log wymienia pole jako zakazane", any("(-1,0) dziura" in l for l in logi), logi)

# 2. dziura jako pole 'dalsze' (odl. 2): zwłoki o krok dalej, a pole dalsze wypada na dziurze
DZ2 = (GRACZ[0] - 2, GRACZ[1], 8)
hak2 = lambda x, y, z, glowne=False: (x, y, z) == DZ2
(pole, kont), logi = scenariusz((200, 200), -1, 0, hak2)
sprawdz("dziura jako pole dalsze (-2,0): bez klika", (-2, 0) not in klik, klik)

# 3. bez haka (None): zachowanie jak dotąd, pole (-1,0) jest klikane (dowód, że test 1 coś mierzy)
(pole, kont), logi = scenariusz((200, 200), -1, 1, None)
sprawdz("bez haka: pole (-1,0) klikane jak dotąd", (-1, 0) in klik, klik)

# 4. hak zakazuje też pola zwłok (glowne): nie klikamy go, ale reszta idzie
hak4 = lambda x, y, z, glowne=False: (x, y, z) == (GRACZ[0] - 1, GRACZ[1] + 1, 8)
(pole, kont), logi = scenariusz((200, 200), -1, 1, hak4)
sprawdz("zakazane pole zwłok (-1,1): bez klika", (-1, 1) not in klik, klik)

# 5. hak rzucający wyjątek nie wywraca lootu (pole jest wtedy klikane jak dotąd)
def hak5(x, y, z, glowne=False):
    raise RuntimeError("test")
(pole, kont), logi = scenariusz((GRACZ[0] + 1, GRACZ[1]), 1, 0, hak5)
sprawdz("hak z wyjątkiem: loot działa dalej (zwłoki znalezione)", kont is not None and pole == (1, 0), (pole, kont))
loot.POLE_ZAKAZANE = None

# 6. cavebot: _loot_pole_zakazane z prawdziwą listą dziur z trasy/dziury_omijaj.json i regułą 'ściana wg mapy'
import cavebot
cavebot.log = lambda *a: None


class Mapa:
    """flagi: 5 = widziane + ściana (jak dziura 32354,32131 na z8); 1 = chodliwe."""
    def __init__(m, sciany=()):
        m.s = set(sciany)

    def pole(m, x, y, z):
        return (5, 186, 255) if (x, y, z) in m.s else (1, 0, 100)

    def przechodnie(m, x, y, z):
        return (x, y, z) not in m.s


dane = json.load(open(os.path.join(KAT, "trasy", "dziury_omijaj.json")))
sprawdz("dane: dziury_omijaj.json zawiera (32354,32131,8)", [32354, 32131, 8] in dane["dziury"], dane["dziury"])
sprawdz("dane: wpis ma _dowody z mapą i logiem", "32354,32131,8" in dane.get("_dowody", {})
        and "186" in dane["_dowody"]["32354,32131,8"] and "15:49" in dane["_dowody"]["32354,32131,8"])

import wpadniecie
w = wpadniecie.Wpadniecie.__new__(wpadniecie.Wpadniecie)
w.plik, w.plik_omijaj, w.dziury, w.omijaj, w.drabiny, w.log = None, os.path.join(KAT, "trasy", "dziury_omijaj.json"), set(), set(), set(), lambda t: None
w.wczytaj()
sprawdz("wpadniecie.wczytaj: dziura (32354,32131,8) na liście", DZIURA in w.dziury, sorted(w.dziury))

cb = cavebot.Cavebot.__new__(cavebot.Cavebot)
cb.mapa = Mapa(sciany={DZIURA, (32360, 32131, 8)})
cb.wpadniecie = w
cavebot.DZIURY_NAUCZONE = 1
cavebot.LOOT_BEZ_DZIUR = 1
sprawdz("cavebot: dziura z listy zakazana", cb._loot_pole_zakazane(*DZIURA, glowne=False) is True)
sprawdz("cavebot: dziura z listy zakazana także jako pole zwłok", cb._loot_pole_zakazane(*DZIURA, glowne=True) is True)
sprawdz("cavebot: ściana wg mapy (nieznana dziura) zakazana jako pole poboczne", cb._loot_pole_zakazane(32360, 32131, 8, glowne=False) is True)
sprawdz("cavebot: ściana wg mapy NIE zakazuje pola zwłok (stwór tam zginął = mapa się myli)",
        cb._loot_pole_zakazane(32360, 32131, 8, glowne=True) is False)
sprawdz("cavebot: zwykłe pole nie jest zakazane", cb._loot_pole_zakazane(32356, 32131, 8, glowne=False) is False)
cavebot.LOOT_BEZ_DZIUR = 0
sprawdz("LOOT_BEZ_DZIUR=0: nic nie jest zakazane", cb._loot_pole_zakazane(*DZIURA, glowne=False) is False)
cavebot.LOOT_BEZ_DZIUR = 1
cb.mapa = None
sprawdz("brak mapy: tylko lista dziur", cb._loot_pole_zakazane(*DZIURA, glowne=False) is True
        and cb._loot_pole_zakazane(32360, 32131, 8, glowne=False) is False)

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
