#!/usr/bin/env python3
"""23.10 (Karol: "Musi go bić, jeśli nie ma przejścia, bo inaczej po prostu zginie"): w dojściu i wypadzie (marsz bez walki) stwór DOWOLNY,
także spoza --potwory (Poison Spider), który stoi na jedynym kroku drogi (brak objazdu wg mapy/A*), jest bity jak blokujący
(po WYPAD_BLOK_S bez ruchu). Gdy objazd istnieje - bez walki. Gracze nigdy. BLOKADA_BIJ_KAZDEGO=0 = jak dawniej. Atrapy, bez gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
import types

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import cavebot
import bot
import pokretla

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.RUNA_AKTYWNA = 0
if not hasattr(cavebot, "BLOKADA_BIJ_KAZDEGO"):      # stary kod (bez poprawki): test ma się wysypać na asercjach, nie na braku stałej
    cavebot.BLOKADA_BIJ_KAZDEGO = 1
logi = []
cavebot.log = lambda *a: logi.append(" ".join(str(x) for x in a))
ok = []


def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


Z = 7
START = (100, 100, Z)


class Mapa:
    """Siatka przechodnich pól; droga = BFS (8 kierunków), omija `zajete`."""
    def __init__(m, pola):
        m.p = set(pola)

    def flagi(m, x, y, z):
        return 1 if (x, y, z) in m.p else 4

    def przechodnie(m, x, y, z):
        return (x, y, z) in m.p

    def droga(m, start, cel, zajete=(), dlugosc=1, skosy=True, **kw):
        zaj = {tuple(q[:3]) for q in zajete}
        z = start[2]
        kol, skad = [tuple(start[:2])], {tuple(start[:2]): None}
        while kol:
            x, y = kol.pop(0)
            if max(abs(x - cel[0]), abs(y - cel[1])) <= dlugosc and (x, y) != tuple(start[:2]) or (dlugosc == 0 and (x, y) == tuple(cel[:2])):
                w = []
                k = (x, y)
                while k != tuple(start[:2]):
                    w.append((k[0], k[1], z)); k = skad[k]
                return w[::-1]
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (x + dx, y + dy)
                    if (dx or dy) and n not in skad and (n[0], n[1], z) in m.p and (n[0], n[1], z) not in zaj \
                            and (skosy or not (dx and dy)):
                        skad[n] = (x, y); kol.append(n)
        return None


KORYTARZ = {(x, 100, Z) for x in range(90, 121)}
POKOJ = {(x, y, Z) for x in range(90, 121) for y in range(97, 104)}


class Swiat:
    def __init__(s, kto, x=101, gracz=False):
        s.t = 0.0; s.poz = [100, 100, Z]; s.kto = kto; s.x = x; s.gracz = gracz
        s.zabity = False; s.hp = 190

    def zegar(s): return s.t
    def spij(s, d): s.t += d

    def zapytaj(s, z):
        s.t += 0.01
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp, "max_hp": 190, "mana": 100, "max_mana": 100}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": Z, "hp": 100}
            l = [ja]
            if not s.zabity:
                l.append({"id": 77, "nazwa": s.kto, "gracz": s.gracz, "x": s.x, "y": 100, "z": Z, "hp": 100})
            return {"stwory": l}
        return {}


class P:
    nazwa = "Ja"

    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): pass

    def krok(p, k):                # stwór na polu 1 w prawo blokuje: nigdzie nie idziemy
        p.s.t += 0.2
        return tuple(p.s.poz)


def zrob(s, mapa, tryb, atak):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: [])
    b = cavebot.Cavebot(P(s), [(105 + i, 100, Z) for i in range(0, 10)], zapytaj=s.zapytaj, atak=atak, alarm=lambda w: None,
                        spij=s.spij, zegar=s.zegar, loot=loot, okrazenia=1, jedzenie="F5", potwory=["troll"], mapa=mapa)
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    if tryb == "dojscie":
        b.dojscie_aktywne = True
    else:
        b.wypad_aktywny = True
    b.ruch_czas = 0.0
    return b


def przebieg(kto, mapa, tryb="dojscie", gracz=False, ile=40):
    s = Swiat(kto, gracz=gracz)
    ataki = []
    b = zrob(s, mapa, tryb, lambda m, g: ataki.append(m["nazwa"]))
    for _ in range(ile):
        s.t += 0.5
        b.tick()
    return ataki, b


# 1. korytarz 1 pole: Poison Spider na jedynym kroku, spoza listy --potwory -> bijemy (dojście i wypad)
for tryb in ("dojscie", "wypad"):
    logi.clear()
    ataki, b = przebieg("Poison Spider", Mapa(KORYTARZ), tryb)
    sprawdz(f"1a {tryb}: Poison Spider w korytarzu jest bity", "Poison Spider" in ataki, ataki)
    sprawdz(f"1b {tryb}: log 'droga zablokowana przez Poison Spider, walczę'", any("zablokowana przez Poison Spider" in l for l in logi), logi[-4:])
    sprawdz(f"1c {tryb}: log o braku objazdu", any("objazdu nie ma" in l for l in logi), logi[-4:])

# 2. pokój (objazd istnieje): bez walki
logi.clear()
ataki, b = przebieg("Poison Spider", Mapa(POKOJ))
sprawdz("2 objazd istnieje: Poison Spider nie jest bity", not ataki, ataki)

# 3. gracz na jedynym kroku: nigdy nie jest celem
ataki, b = przebieg("Bob", Mapa(KORYTARZ), gracz=True)
sprawdz("3 gracz w korytarzu: bez ataku", not ataki, ataki)

# 4. pokrętło 0: jak dawniej (Poison Spider spoza listy nie jest celem)
cavebot.BLOKADA_BIJ_KAZDEGO = 0
ataki, b = przebieg("Poison Spider", Mapa(KORYTARZ))
sprawdz("4 BLOKADA_BIJ_KAZDEGO=0: bez ataku", not ataki, ataki)
cavebot.BLOKADA_BIJ_KAZDEGO = 1

# 5. stwór z listy (Troll) nadal bity jak dawniej, niezależnie od pokrętła
cavebot.BLOKADA_BIJ_KAZDEGO = 0
ataki, b = przebieg("Troll", Mapa(KORYTARZ))
sprawdz("5 Troll z listy: bity jak dawniej", "Troll" in ataki, ataki)
cavebot.BLOKADA_BIJ_KAZDEGO = 1

# 6. stwór 2 pola dalej (nieprzylegający): jeszcze nie blokuje, bez ataku
s = Swiat("Poison Spider", x=102); ataki = []
b = zrob(s, Mapa(KORYTARZ), "dojscie", lambda m, g: ataki.append(m["nazwa"]))
for _ in range(20):
    s.t += 0.5; b.tick()
sprawdz("6 stwór 2 pola dalej: bez ataku (jeszcze nie przylega)", not ataki, ataki)

# 7. poza dojściem/wypadem zwykła walka nie obejmuje stworów spoza listy
s = Swiat("Poison Spider"); ataki = []
b = zrob(s, Mapa(KORYTARZ), "dojscie", lambda m, g: ataki.append(m["nazwa"]))
b.dojscie_aktywne = False
for _ in range(30):
    s.t += 0.5; b.tick()
sprawdz("7 zwykła trasa: Poison Spider spoza listy nie jest celem", not ataki, ataki)

# 8. pokrętło zarejestrowane
sprawdz("8 pokrętło w ZAKRESY, domyślnie 1", pokretla.ZAKRESY.get("BLOKADA_BIJ_KAZDEGO") == (0, 1) and cavebot.BLOKADA_BIJ_KAZDEGO == 1)
sprawdz("8b kierunek bezpieczeństwa nie_nizej", pokretla.KIERUNEK.get("BLOKADA_BIJ_KAZDEGO") == "nie_nizej")

print(f"WYNIK: {sum(ok)} / {len(ok)}")
sys.exit(0 if all(ok) else 1)
