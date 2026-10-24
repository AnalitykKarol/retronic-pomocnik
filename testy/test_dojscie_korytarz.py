#!/usr/bin/env python3
"""23.10 (geblish, trasa thais_pn_z9_dojscie): w korytarzu z8 o szerokości 1 pola dwa przejściowo nieudane kroki strzałką w jedyne pole drogi
dawały KROK_ZLY na 45 s (zakaz jedynego przejścia: bot oscylował 14:08:49-14:09:41, aż D3 go ruszył). Poprawka:
 - w dojściu (dojscie_aktywne) zakaz pola, które mapa uznaje za przechodnie, trwa KROK_ZLY_DOJSCIE_S (4 s, x2, maks 16 s), nie 45 s;
 - ściana z mapy w dojściu dalej dostaje KROK_ZLY_SCIANA_S; poza dojściem zakaz bez zmian (45 s);
 - stwór z INNEGO piętra na polu (pająki z z9 widziane z korytarza z8) nie tłumi zakazu; stwór z tego piętra nadal go tłumi.
Atrapa postaci jak w test_krok_zly.py; bez gry i bez gniazd."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
import types

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import cavebot
import bot

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


logi = []
cavebot.log = lambda *a: logi.append(" ".join(str(x) for x in a))
Z = 8
START = (100, 52, Z)
CEL = (103, 52)                  # korytarz w prawo: jedyne pole drogi z START to (101,52)
PRZEJSCIE = (101, 52, Z)
CZAS_KROKU = 1.5
SC = {(x, y, Z) for x in range(98, 106) for y in (51, 53)} | {(99, 52, Z)}


class Mapa:
    def __init__(m, sciany):
        m.s = set(sciany)

    def flagi(m, x, y, z):
        return 4 if (x, y, z) in m.s else 1

    def przechodnie(m, x, y, z):
        return (x, y, z) not in m.s

    def droga(m, start, cel, zajete=(), dlugosc=1, skosy=True, **kw):
        return [(start[0] + 1, start[1], start[2])]


class Post:
    nazwa = "Ja"

    def __init__(p, t, zle):
        p.t, p.zle, p.poz = t, set(zle), list(START)

    def pozycja(p):
        return tuple(p.poz)

    def krok(p, k):
        d = bot.KIERUNKI[k]
        n = (p.poz[0] + d[0], p.poz[1] + d[1], p.poz[2])
        if n in p.zle or n in SC:
            p.t[0] += CZAS_KROKU
            return False
        p.poz[:] = n
        p.t[0] += 0.3
        return True


def nowy(dojscie, zle=(PRZEJSCIE,)):
    t = [0.0]
    pr = Post(t, zle)
    b = cavebot.Cavebot(pr, [START], zapytaj=lambda z: {}, atak=lambda m, g: None, alarm=lambda w: None,
                        spij=lambda d: t.__setitem__(0, t[0] + d), zegar=lambda: t[0], loot=types.SimpleNamespace(zbierz=lambda a, b: "ok"),
                        mapa=Mapa(SC), czas_s=10 ** 6)
    b.dojscie_aktywne = dojscie
    return pr, b, t


def zakaz_s(b, t, pole):
    """Ile s zostało do końca zakazu pola (None = brak zakazu)."""
    do = getattr(b, "sciany_do", {}).get(pole)
    return None if do is None else do - t[0]


def petla(b, ile=6):
    for _ in range(ile):
        b.krok_do(CEL)


cavebot.KROK_ZLY = 1
# ---------- 1. dojście: zakaz przechodniego pola jest krótki ----------
pr, b, t = nowy(True)
petla(b)
r = zakaz_s(b, t, PRZEJSCIE)
sprawdz("1a dojście: jedyne przechodnie pole dostaje zakaz po nieudanych krokach", r is not None, getattr(b, "sciany_do", {}))
sprawdz("1b dojście: zakaz krótszy niż 10 s (było 45 s)", r is not None and r <= 10.0, r)
if r is not None:
    t[0] += r + 0.5
    sprawdz("1c dojście: po zakazie pole znów jest próbowane (sciana() False)", not b.sciana(PRZEJSCIE))
    pr.zle.clear()
    petla(b, 4)
    sprawdz("1d dojście: po ustąpieniu blokady bot wchodzi w korytarz (x > 100)", pr.poz[0] > 100, pr.poz)
# eskalacja ma górną granicę
pr, b, t = nowy(True)
duzo = 0.0
for _ in range(8):
    petla(b, 4)
    r = zakaz_s(b, t, PRZEJSCIE)
    if r is not None:
        duzo = max(duzo, r)
        t[0] += r + 0.1
sprawdz("1e dojście: kolejne zakazy nie przekraczają 16 s", 0 < duzo <= 16.0, duzo)

# ---------- 2. poza dojściem zakaz bez zmian ----------
pr, b, t = nowy(False)
petla(b)
r = zakaz_s(b, t, PRZEJSCIE)
sprawdz("2 poza dojściem pierwszy zakaz = KROK_ZLY_S (45 s)", r is not None and 30.0 <= r <= 45.0, r)

# ---------- 3. ściana z mapy w dojściu: nadal długi zakaz ----------
pr, b, t = nowy(True)
for _ in range(6):
    b.krok_do((100, 50))          # cel w górę: Up w ścianę z mapy
r = zakaz_s(b, t, (100, 51, Z))
sprawdz("3 dojście: krok w ścianę z mapy = KROK_ZLY_SCIANA_S (300 s)", r is not None and r > 250.0, r)

# ---------- 4. stwór z innego piętra nie tłumi zakazu, z tego piętra tłumi ----------
pr, b, t = nowy(True)
b.ostatnie_stwory = [{"nazwa": "Poison Spider", "x": PRZEJSCIE[0], "y": PRZEJSCIE[1], "z": Z + 1, "id": 1, "hp": 100}]
petla(b)
sprawdz("4a pająk z z9 na polu (x,y) z8 nie tłumi zakazu", zakaz_s(b, t, PRZEJSCIE) is not None, getattr(b, "krok_zly", {}))
sprawdz("4b log nieudanego kroku nie wymienia pająka z innego piętra",
        not any("nie ruszył" in l and "Poison Spider" in l for l in logi), [l for l in logi if "Poison" in l][:2])
pr, b, t = nowy(True)
b.ostatnie_stwory = [{"nazwa": "Cave Rat", "x": PRZEJSCIE[0], "y": PRZEJSCIE[1], "z": Z, "id": 2, "hp": 100}]
petla(b)
sprawdz("4c szczur na polu na tym piętrze = brak zakazu (walka/unikanie, nie ściana)", zakaz_s(b, t, PRZEJSCIE) is None,
        getattr(b, "sciany_do", {}))

print(f"WYNIK: {sum(ok)} / {len(ok)}")
sys.exit(0 if all(ok) else 1)
