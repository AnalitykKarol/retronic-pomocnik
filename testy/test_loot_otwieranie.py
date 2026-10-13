import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""Test offline otwierania zwłok z pamięci (bez obrazków): kolejność pól, pola o krok dalej (_otworz_dalsze).
Atrapy myszy i pamięci, nic nie trafia do gry. Uruchom: python3 -I test_loot_otwieranie.py"""
import os
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ekran, loot

klik = []
stan = {"zwloki_na": None, "gracz": (100, 100, 7), "idzie_do": None, "stwory": []}
k = loot.kont


def zapytaj(z):
    if z["cmd"] == "kontenery":
        lista = [k(1, "bag", 2853, 8)]
        if stan["otwarte"]:
            lista.append(k(2, "dead rat", 3994, 5))
        return {"kontenery": lista}
    if z["cmd"] == "stwory":
        return {"stwory": stan["stwory"]}
    raise AssertionError(z)


def otworz(dx, dy):
    klik.append((dx, dy))
    g = stan["gracz"]
    cel = (g[0] + dx, g[1] + dy)
    if cel == stan["zwloki_na"]:
        # serwer podprowadza postać o krok, gdy zwłoki są dalej niż 1 pole
        if max(abs(dx), abs(dy)) > 1:
            stan["gracz"] = (g[0] + (dx > 0) - (dx < 0), g[1] + (dy > 0) - (dy < 0), g[2])
        stan["otwarte"] = True


def scenariusz(zwloki_na, dx, dy, stwory=()):
    klik.clear()
    stan.update(zwloki_na=zwloki_na, gracz=(100, 100, 7), otwarte=False, stwory=list(stwory))
    logi = []
    wynik = loot._otworz_z_pamiecia(dx, dy, (100, 100, 7), {}, True, logi.append)
    return wynik, logi


ekran.otworz = otworz
loot.POD_NOGAMI_PIERWSZE = False      # testy 1-7: dawne zachowanie (pokrętło wyłączone)
loot._pauza = lambda a=0, b=0: None
loot._zapytaj = zapytaj
loot._pozycja_gracza = lambda: stan["gracz"]
ok = []


def sprawdz(opis, warunek):
    print(("OK    " if warunek else "BŁĄD "), opis)
    ok.append(bool(warunek))


# 1. zwłoki na zgadniętym polu: jeden klik
(pole, kont), logi = scenariusz((101, 100), 1, 0)
sprawdz("zgadnięte pole: jeden klik, pole (1,0)", klik == [(1, 0)] and pole == (1, 0) and kont["nazwa"] == "dead rat")

# 2. zwłoki na sąsiednim polu: znalezione w 3x3, bez pól dalszych
(pole, kont), logi = scenariusz((101, 101), 1, 0)
sprawdz("sąsiednie pole: znalezione w 3x3", pole == (1, 1) and all(max(abs(x), abs(y)) <= 1 for x, y in klik))

# 3. zwłoki o krok dalej niż zgadnięte (odległość 2 od gracza): znalezione polami dalszymi
(pole, kont), logi = scenariusz((102, 100), 1, 0)
sprawdz("o krok dalej: znaleziono", kont is not None and kont["nazwa"] == "dead rat")
sprawdz(f"o krok dalej: pole względem pozycji po podejściu to (1,0), jest {pole}", pole == (1, 0))
sprawdz("o krok dalej: najpierw 3x3 (9 klików z powtórką), potem pole (2,0)", klik[-1] == (2, 0) and len(klik) == 10)
sprawdz("o krok dalej: log", any("o krok dalej" in l for l in logi))

# 4. nigdzie: brak, wszystkie próby zalogowane, pola dalsze tylko przy zgadniętym polu
(pole, kont), logi = scenariusz((110, 110), 1, 0)
sprawdz("brak zwłok: (None, None)", pole is None and kont is None)
sprawdz("brak zwłok: pola dalsze to tylko przyległe do (1,0)",
        {p for p in klik if max(abs(p[0]), abs(p[1])) == 2} == {(2, -1), (2, 0), (2, 1)})
sprawdz("brak zwłok: log z próbami", any("Ctrl+klik od gracza" in l and "dalej pusto" in l for l in logi))

# 5. stwór na polu dalszym: pomijamy
(pole, kont), logi = scenariusz((110, 110), 1, 0, stwory=[{"x": 102, "y": 100, "z": 7, "hp": 50}])
sprawdz("stwór na polu dalszym: bez klika", (2, 0) not in klik)

# 6. kolejność pól dalszych: najbliższe zgadniętemu najpierw
sprawdz("_pola_dalsze: kolejność", loot._pola_dalsze(1, 0)[0] == (2, 0) and len(loot._pola_dalsze(1, 1)) == 5)

# 7. Ctrl+klik pola dalszego poprowadził nas na pole zwłok: przerywamy, nie klikamy dalej
_stara = ekran.otworz
def _wchodzi(dx, dy):
    klik.append((dx, dy))
    if max(abs(dx), abs(dy)) == 2:
        stan["gracz"] = (101, 100, 7)
ekran.otworz = _wchodzi
(pole, kont), logi = scenariusz((110, 110), 1, 0)
ekran.otworz = _stara
dalsze = [p for p in klik if max(abs(p[0]), abs(p[1])) == 2]
sprawdz("stoję na polu zwłok: jedna próba dalsza i koniec", len(dalsze) == 1 and pole is None)
sprawdz("stoję na polu zwłok: log", any("stoję na polu zwłok" in l for l in logi))

# --- 12.10: pole pod nogami pierwsze, budżet prób, pomijanie pustych pól ---
loot.POD_NOGAMI_PIERWSZE = True
loot.MAKS_PROB = 3
loot.ALTERNATYWY = []
loot.PROBOWANE.clear()

# 8. zwłoki pod graczem, cavebot zgadł sąsiednie pole: (-1,0) pusto, potem własne (0,0)
(pole, kont), logi = scenariusz((100, 100), -1, 0)
sprawdz("pod nogami: kliki (-1,0) potem (0,0)", klik[:2] == [(-1, 0), (-1, 0)] or klik[:3] == [(-1, 0), (-1, 0), (0, 0)])
sprawdz("pod nogami: znaleziono na (0,0)", pole == (0, 0) and kont is not None and len(klik) <= 3)

# 9. alternatywa = pole gracza: zaraz po zgadniętym
loot.PROBOWANE.clear()
loot.ALTERNATYWY = [(100, 100)]
(pole, kont), logi = scenariusz((100, 100), 1, 0)
sprawdz("alternatywa pole gracza: (1,0) i (0,0)", pole == (0, 0) and [p for p in klik if p != (1, 0)] == [(0, 0)])
loot.ALTERNATYWY = []

# 10. zwłok pod graczem (dx,dy)==(0,0): pierwsza próba (0,0)
loot.PROBOWANE.clear()
(pole, kont), logi = scenariusz((100, 100), 0, 0)
sprawdz("zwłoki == pozycja gracza: pierwszy klik (0,0)", klik == [(0, 0)] and pole == (0, 0))

# 11. zwłoki jedno pole obok zgadniętego, w 3 próbach: znalezione, budżet nie przekroczony
loot.PROBOWANE.clear()
(pole, kont), logi = scenariusz((101, 99), 1, 0)       # względem (1,-1): sąsiad zgadniętego (1,0)
sprawdz("sąsiad zgadniętego: znaleziony w budżecie 3 pól", pole == (1, -1) and len({p for p in klik}) <= 3)

# 12. brak zwłok: najwyżej 3 różne pola + brak pól dalszych, flaga NIEDOKONCZONE, pola zapamiętane
loot.PROBOWANE.clear()
(pole, kont), logi = scenariusz((110, 110), 1, 0)
sprawdz("brak: tylko 3 różne pola (i bez dalszych)", len(set(klik)) == 3 and pole is None
        and not any(max(abs(x), abs(y)) == 2 for x, y in klik))
sprawdz("brak: NIEDOKONCZONE=True", loot.NIEDOKONCZONE is True)
puste = len(loot.PROBOWANE)
# 13. ponowienie: puste pola pomijane, własne pole nie klikane drugi raz przy tej samej pozycji
(pole, kont), logi = scenariusz((110, 110), 1, 0)
pierwsze = set(klik)
sprawdz("ponowienie: kolejne 3 pola, bez powtórek (poza dalszymi)", len(pierwsze) >= 3 and not (pierwsze & {(1, 0), (0, 0)}))
# 14. po trzech rundach wszystkie 3x3 puste: dalsze pola 1 klik
loot.PROBOWANE.clear()
loot.MAKS_PROB = 9
(pole, kont), logi = scenariusz((110, 110), 1, 0)
sprawdz("MAKS_PROB=9: całe 3x3 + 1 pole dalsze", len(set(klik)) == 10 and loot.NIEDOKONCZONE is False)
loot.MAKS_PROB = 3
loot.PROBOWANE.clear()

# 15. pokrętło wyłączone = stare zachowanie: (0,0) nie jest klikane, 9 pól 3x3 + dalsze
loot.POD_NOGAMI_PIERWSZE = False
(pole, kont), logi = scenariusz((100, 100), -1, 0)
sprawdz("pokrętło wyłączone: (0,0) nie klikane, brak zwłok", (0, 0) not in klik and pole is None)
(pole, kont), logi = scenariusz((110, 110), 1, 0)
sprawdz("pokrętło wyłączone: 8 pól 3x3 + dalsze (>8 kliknięć)", len(klik) > 8)
loot.POD_NOGAMI_PIERWSZE = True

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
