#!/usr/bin/env python3
"""20.10: KROK_BEZ_SCIAN (cavebot.krok_do): po nieudanym pierwszym kierunku ponawiamy go raz i nie wciskamy zapasowych
kierunków w pola, które mapa jednoznacznie uznaje za ścianę (dane z logów 19-20.10: 44% nieudanych kroków to bicie w ściany).
Atrapa postaci ze skryptem wyników strzałek; bez gry i bez gniazd."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
import types

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import cavebot
import bot
import pokretla as _pk

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


cavebot.log = lambda *a: None
Z = 8
POZ = (100, 50, Z)
CEL = (110, 52)             # kierunki: Right, Down, Up, Left


class Mapa:
    def __init__(m, nad=None):
        m.nad = dict(nad or {})

    def flagi(m, x, y, z):
        return m.nad.get((x, y, z), 1)

    def przechodnie(m, x, y, z):
        f = m.flagi(x, y, z)
        return None if not f & 1 else not f & 4


class Post:
    """krok(k): wynik ze skryptu `skrypt[k]` (lista True/False po kolei, po wyczerpaniu ostatnia wartość); True = przesunięcie."""
    nazwa = "Ja"

    def __init__(p, skrypt):
        p.skrypt, p.poz, p.klawisze = {k: list(v) for k, v in skrypt.items()}, list(POZ), []

    def pozycja(p):
        return tuple(p.poz)

    def krok(p, k):
        p.klawisze.append(k)
        w = p.skrypt.get(k, [False])
        r = w.pop(0) if len(w) > 1 else w[0]
        if r:
            d = bot.KIERUNKI[k]
            p.poz[0] += d[0]
            p.poz[1] += d[1]
        return r


def nowy(skrypt, nad=None):
    t = [0.0]
    pr = Post(skrypt)
    b = cavebot.Cavebot(pr, [POZ], zapytaj=lambda z: {}, atak=lambda m, g: None, alarm=lambda w: None,
                        spij=lambda d: t.__setitem__(0, t[0] + d), zegar=lambda: t[0], loot=types.SimpleNamespace(zbierz=lambda a, b: "ok"),
                        mapa=Mapa(nad), czas_s=10 ** 6)
    return pr, b


SCIANA_DOL = {(100, 51, Z): 5}          # (100,51) = Down: ściana wg mapy (widziana, flaga 4)
NIEZNANE_DOL = {(100, 51, Z): 0}        # Down: pole niewidziane (przechodnie None)

# ---------- 0. pokrętło ----------
sprawdz("0a domyślnie 0", cavebot.KROK_BEZ_SCIAN == 0)
sprawdz("0b zakres 0-1, kierunek nie_wyzej", _pk.ZAKRESY.get("KROK_BEZ_SCIAN") == (0, 1) and _pk.KIERUNEK.get("KROK_BEZ_SCIAN") == "nie_wyzej")

# ---------- 1. przy 0: dotychczasowe zachowanie (kolejne kierunki, także w ścianę) ----------
cavebot.KROK_BEZ_SCIAN = 0
pr, b = nowy({"Right": [False], "Down": [False], "Up": [False], "Left": [False]}, SCIANA_DOL)
r = b.krok_do(CEL)
sprawdz("1a przy 0 po nieudanym Right próbujemy Down (ściana), Up, Left, bez ponowienia", r is False and pr.klawisze == ["Right", "Down", "Up", "Left"], pr.klawisze)
pr, b = nowy({"Right": [False, True]}, SCIANA_DOL)
r = b.krok_do(CEL)
sprawdz("1b przy 0 po nieudanym Right idzie Down (ściana) zamiast ponowienia Right", pr.klawisze[:2] == ["Right", "Down"], pr.klawisze)

# ---------- 2. przy 1 ----------
cavebot.KROK_BEZ_SCIAN = 1
pr, b = nowy({"Right": [False, True]}, SCIANA_DOL)
r = b.krok_do(CEL)
sprawdz("2a ponowienie pierwszego kierunku: Right, Right -> True, bez Down (ściana)", r is True and pr.klawisze == ["Right", "Right"] and pr.poz[0] == 101, (r, pr.klawisze))
sprawdz("2b po udanym ponowieniu zablokowane wyczyszczone, nieudane = 0", not b.zablokowane and b.nieudane == 0, (b.zablokowane, b.nieudane))

pr, b = nowy({"Right": [False], "Up": [False], "Left": [False]}, SCIANA_DOL)
r = b.krok_do(CEL)
sprawdz("2c Right zawodzi zawsze: Right, Right (ponowienie), potem Up i Left, nigdy Down (ściana)", r is False
        and pr.klawisze == ["Right", "Right", "Up", "Left"], pr.klawisze)

pr, b = nowy({"Right": [False], "Up": [True]}, SCIANA_DOL)
r = b.krok_do(CEL)
sprawdz("2d po dwóch nieudanych Right idzie kolejny przechodni kierunek (Up)", r is True and pr.klawisze == ["Right", "Right", "Up"], pr.klawisze)

pr, b = nowy({"Right": [False], "Down": [True]}, NIEZNANE_DOL)
r = b.krok_do(CEL)
sprawdz("2e pole nieznane (przechodnie None) nadal próbowane: Right, Right, Down -> True", r is True and pr.klawisze == ["Right", "Right", "Down"], pr.klawisze)

pr, b = nowy({"Right": [True]}, SCIANA_DOL)
r = b.krok_do(CEL)
sprawdz("2f udany pierwszy krok: jedna strzałka, bez zmian", r is True and pr.klawisze == ["Right"], pr.klawisze)

# pierwszy kierunek sam jest ścianą wg mapy: bez ponowienia, jak dotąd idzie dalej (pierwsza strzałka zawsze próbowana)
pr, b = nowy({"Right": [False], "Down": [True]}, {(101, 50, Z): 5})
r = b.krok_do(CEL)
sprawdz("2g pierwszy kierunek = ściana wg mapy: bez ponowienia, następny (Down) próbowany", r is True and pr.klawisze == ["Right", "Down"], pr.klawisze)

# flaga 4 bez bitu 'widziane' też jest ścianą
pr, b = nowy({"Right": [False], "Up": [False], "Left": [False]}, {(100, 51, Z): 4})
r = b.krok_do(CEL)
sprawdz("2h flaga 4 (bez 1) = ściana: Down pomijany", "Down" not in pr.klawisze, pr.klawisze)

# ogień/schody/dziury: logika bez zmian (pole ognia nadal pomijane przed ponowieniem)
pr, b = nowy({"Right": [False], "Up": [False], "Left": [False]})
b.ogien_pola = {(100, 51, Z): 1}
r = b.krok_do(CEL)
sprawdz("2i pole ognia nadal pomijane (jak dotąd)", "Down" not in pr.klawisze and pr.klawisze[:2] == ["Right", "Right"], pr.klawisze)

# bez mapy: nic się nie zmienia poza ponowieniem
t = [0.0]
pr = Post({"Right": [False], "Down": [False], "Up": [False], "Left": [False]})
b = cavebot.Cavebot(pr, [POZ], zapytaj=lambda z: {}, atak=lambda m, g: None, alarm=lambda w: None,
                    spij=lambda d: None, zegar=lambda: 0.0, loot=None, mapa=None, czas_s=10 ** 6)
b.krok_do(CEL)
sprawdz("2j bez mapy: ścian nie znamy, Down próbowany (po ponowieniu Right)", pr.klawisze == ["Right", "Right", "Down", "Up", "Left"], pr.klawisze)

cavebot.KROK_BEZ_SCIAN = 0
print(f"WYNIK: {sum(ok)} / {len(ok)}")
sys.exit(0 if all(ok) else 1)
