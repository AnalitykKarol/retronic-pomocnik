#!/usr/bin/env python3
"""22.10: KROK_ZLY (cavebot.krok_do): pole, w które krok strzałką nie udał się KROK_ZLY_N razy z rzędu, dostaje zakaz (nie bijemy w nie
dalej, A* i patrol je omijają). Odtwarza pętlę wydry z 22.10 12:03 w (32478,32274,z8): Up w ukryte, wg mapy przechodnie pole nie rusza,
Left/Right to ściany, Down (krok wstecz) się udaje, następny obieg Up (udany) i znów Up w blokadę - kilkanaście obiegów po ~5 s.
Atrapa postaci ze skryptem blokad; bez gry i bez gniazd."""
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


for _n, _v in (("KROK_ZLY", None), ("KROK_ZLY_N", 2), ("KROK_ZLY_S", 45.0), ("KROK_ZLY_OKNO_S", 60.0)):
    if not hasattr(cavebot, _n):          # stary kod (bez poprawki): test ma się wysypać na asercjach, nie na braku stałych
        setattr(cavebot, _n, _v)
logi = []
cavebot.log = lambda *a: logi.append(" ".join(str(x) for x in a))
Z = 8
START = (100, 52, Z)        # (100,52) = odpowiednik (32478,32274)
CEL = (99, 50)              # kierunki z START: Up, Left, Right, Down
BLOK = (100, 51, Z)         # ukryta blokada: mapa mówi "przechodnie", klawisz nie rusza
CZAS_KROKU = 1.5


class Mapa:
    def __init__(m, sciany=()):
        m.s = set(sciany)
        m.blok_drogi = None

    def flagi(m, x, y, z):
        return 4 if (x, y, z) in m.s else 1

    def przechodnie(m, x, y, z):
        return (x, y, z) not in m.s

    def droga(m, start, cel, zajete=(), dlugosc=1, skosy=True, **kw):
        m.blok_drogi = list(zajete)
        return [(start[0], start[1] - 1, start[2])]


class Post:
    """krok(k) w pole z `zle` (zbiór) albo ze ścian mapy = False i CZAS_KROKU s zegara; poza tym przesunięcie."""
    nazwa = "Ja"

    def __init__(p, t, zle, sciany):
        p.t, p.zle, p.sciany, p.poz, p.klawisze = t, set(zle), set(sciany), list(START), []

    def pozycja(p):
        return tuple(p.poz)

    def krok(p, k):
        d = bot.KIERUNKI[k]
        n = (p.poz[0] + d[0], p.poz[1] + d[1], p.poz[2])
        p.klawisze.append((tuple(p.poz[:2]), k))
        if n in p.zle or n in p.sciany:
            p.t[0] += CZAS_KROKU
            return False
        p.poz[:] = n
        p.t[0] += 0.3
        return True


def nowy(zle=(BLOK,), sciany=((99, 52, Z), (101, 52, Z), (99, 51, Z), (101, 51, Z))):
    t = [0.0]
    pr = Post(t, zle, sciany)
    b = cavebot.Cavebot(pr, [START], zapytaj=lambda z: {}, atak=lambda m, g: None, alarm=lambda w: None,
                        spij=lambda d: t.__setitem__(0, t[0] + d), zegar=lambda: t[0], loot=types.SimpleNamespace(zbierz=lambda a, b: "ok"),
                        mapa=Mapa(sciany), czas_s=10 ** 6)
    return pr, b, t


def petla(b, pr, ile):
    """Jak _idz_trasa: ile obiegów krok_do(CEL); wynik = lista True/False."""
    return [b.krok_do(CEL) for _ in range(ile)]


def w_blok(pr):
    return sum(1 for (p, k) in pr.klawisze if k == "Up" and p == (100, 52))


# ---------- 0. pokrętło ----------
sprawdz("0a domyślnie 1, zakres 0-1, kierunek nie_nizej", cavebot.KROK_ZLY == 1 and _pk.ZAKRESY.get("KROK_ZLY") == (0, 1)
        and _pk.KIERUNEK.get("KROK_ZLY") == "nie_nizej")

# ---------- 1. pętla z 22.10: KROK_ZLY=0 (stare zachowanie) bije w blokadę w każdym obiegu ----------
cavebot.KROK_ZLY = 0
pr, b, t = nowy()
petla(b, pr, 24)
sprawdz("1a KROK_ZLY=0: Up w blokadę wciskany w każdym obiegu z (100,52) (>= 8 razy w 24 obiegach)", w_blok(pr) >= 8, w_blok(pr))
sprawdz("1b KROK_ZLY=0: liczba nieudanych strzałek >= 30", sum(1 for (p, k) in pr.klawisze if k in ("Up", "Left", "Right") and p == (100, 52)) >= 30,
        len(pr.klawisze))

# ---------- 2. KROK_ZLY=1: po 2 nieudanych krokach zakaz, koniec bicia ----------
cavebot.KROK_ZLY = 1
pr, b, t = nowy()
w = petla(b, pr, 24)
sprawdz("2a Up w blokadę wciśnięty najwyżej KROK_ZLY_N razy (a nie w każdym obiegu)", w_blok(pr) <= cavebot.KROK_ZLY_N, w_blok(pr))
bite = sum(1 for (p, k) in pr.klawisze if k in ("Up", "Left", "Right") and p == (100, 52))
sprawdz("2b wszystkich nieudanych strzałek <= 3 * KROK_ZLY_N (blokada + 2 ściany)", bite <= 3 * cavebot.KROK_ZLY_N, bite)
sprawdz("2c blokada i obie ściany (Left, Right) mają zakaz (sciana() True)", all(b.sciana(p) for p in (BLOK, (99, 52, Z), (101, 52, Z))),
        [b.sciana(p) for p in (BLOK, (99, 52, Z), (101, 52, Z))])
sprawdz("2d po zakazie krok_do zwraca False i nie cofa się o pole (stoi na (100,52) po obiegach)", w[-1] is False and pr.poz[:2] == [100, 52], (w, pr.poz))
t[0] += cavebot.SCIANA_WAZNA + 1.0
sprawdz("2e zakaz trwa po SCIANA_WAZNA s mimo przechodnie=True na mapie (stara nauka wygasałaby)", b.mapa.przechodnie(*BLOK) and b.sciana(BLOK))
sprawdz("2f log zakazu i log nieudanego kroku z prawdziwą wartością zablok", any("[KROK_ZLY]" in l for l in logi)
        and any("nie ruszył" in l and "nieudane 2" in l for l in logi), logi[-3:])
sprawdz("2g flaga dla patrolu (krok_zly_blok) ustawiona", getattr(b, "krok_zly_blok", False) is True)

# ---------- 3. zakaz wygasa po KROK_ZLY_S; udany krok kasuje licznik, drugi zakaz trwa dłużej ----------
t[0] += cavebot.KROK_ZLY_S + 1.0
sprawdz("3a po KROK_ZLY_S s zakaz wygasł", not b.sciana(BLOK))
n0 = w_blok(pr)
b.krok_do(CEL)
sprawdz("3b po wygaśnięciu pole znów próbowane (Up)", w_blok(pr) == n0 + 1, (n0, w_blok(pr)))
sprawdz("3c jedna nieudana próba po wygaśnięciu = od razu kolejny zakaz, 2x dłuższy (90 s)",
        b.sciana(BLOK) and abs((getattr(b, "sciany_do", {})[BLOK] - t[0]) - 2 * cavebot.KROK_ZLY_S) < 5.0, (getattr(b, "sciany_do", {}).get(BLOK), t[0]))

# udane wejście kasuje licznik
pr, b, t = nowy()
b.krok_do(CEL)                                   # Up zawodzi (1), Down się udaje
pr.zle.clear()                                   # blokada zniknęła
r = [b.krok_do(CEL) for _ in range(3)]
sprawdz("3d blokada zniknęła: bot przechodzi przez pole (100,51) i nie dostaje zakazu", pr.poz[1] < 51 and not b.sciana(BLOK), (pr.poz, b.sciany))
sprawdz("3e udane wejście kasuje licznik nieudanych", BLOK not in getattr(b, "krok_zly", {}), getattr(b, "krok_zly", {}))

# ---------- 4. okno: nieudane próby oddalone o > KROK_ZLY_OKNO_S nie sumują się ----------
pr, b, t = nowy()
b.krok_do(CEL)                                   # Up (1) + ściany, Down udany
t[0] += cavebot.KROK_ZLY_OKNO_S + 5
b.krok_do(CEL)                                   # Up udany? nie: blokada stoi, wracamy z (100,53) w (100,52)
b.krok_do(CEL)                                   # Up zawodzi (tu pierwszy w nowym oknie)
sprawdz("4 próby starsze niż KROK_ZLY_OKNO_S nie dają zakazu", not b.sciana(BLOK), (getattr(b, "krok_zly", {}).get(BLOK), getattr(b, "sciany_do", {})))

# ---------- 5. stwór na polu: to nie ukryta blokada, bez zakazu ----------
pr, b, t = nowy()
b.ostatnie_stwory = [{"nazwa": "Troll", "x": BLOK[0], "y": BLOK[1], "z": Z, "id": 1, "hp": 100}]
petla(b, pr, 8)
sprawdz("5 stwór na polu = brak zakazu (to walka/unikanie, nie ściana)", not b.sciana(BLOK) and BLOK not in getattr(b, "sciany_do", {}),
        (b.sciany, getattr(b, "krok_zly", {})))

# ---------- 6. A*: zakaz trafia do blokad drogi (także w drugiej drodze "po samej mapie") ----------
pr, b, t = nowy()
petla(b, pr, 6)
b.droga(START, CEL, (), 0, False)
sprawdz("6a droga() dostaje zakazane pole w blokadach", BLOK in (b.mapa.blok_drogi or []), b.mapa.blok_drogi)
b.mapa.droga = lambda start, cel, zajete=(), *a, **kw: (setattr(b.mapa, "blok_drogi", list(zajete)) or ([(1, 1, Z)] * 30 if BLOK in zajete else [(1, 1, Z)]))
d = b.droga(START, CEL, (), 0, False)
sprawdz("6b druga droga bez blokad (fallback) też zna zakaz", BLOK in (b.mapa.blok_drogi or []), b.mapa.blok_drogi)

# ---------- 7. drzwi: otwarcie drzwi kasuje zakaz ----------
pr, b, t = nowy()
petla(b, pr, 6)
getattr(b, "_krok_zly_ok", lambda p: None)(BLOK)
b.sciany.pop(BLOK, None)
sprawdz("7 _krok_zly_ok kasuje zakaz i licznik", not b.sciana(BLOK) and BLOK not in getattr(b, "krok_zly", {}))

cavebot.KROK_ZLY = 1
print(f"WYNIK: {sum(ok)} / {len(ok)}")
sys.exit(0 if all(ok) else 1)
