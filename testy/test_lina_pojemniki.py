"""Lina z każdego pojemnika (20.10, SPEC_orbity_straznik_1020 D). Kutangen miał linę, a bot nie znalazł jej (log 17:02:52):
szukał tylko w oknach 'plecaka' (loot.czy_plecak). Teraz: plecaki mają pierwszeństwo (lina w głównym plecaku = jak dotąd),
potem każdy inny otwarty pojemnik z oknem na ekranie, potem ekwipunek; brak = BrakEkranu / log z listą sprawdzonych pojemników.
Atrapy: okna (loot.znajdz_okna), pamięć (kontenery_z_pamieci), dopasowanie okien, mysz."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import loot, ekran, wypad, wpadniecie, bot

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

LINA = 3003
class Slot:
    def __init__(s, srodek): s.srodek = srodek
class Okno:
    def __init__(s, y, n=8): s.sloty = [Slot((100 + 36 * i, y)) for i in range(n)]

def kont(nr, nazwa, id_, *przedm):
    return {"numer": nr, "nazwa": nazwa, "id": id_, "pojemnosc": 8,
            "przedmioty": [{"slot": i, "id": p, "ilosc": 1} for i, p in enumerate(przedm)]}

MAIN = kont(0, "backpack", 2854, 3031, 3607)                  # główny plecak (czy_plecak)
BAG2 = kont(1, "blue backpack", 2870, 3035, LINA)             # kolejny pojemnik, nie 'bag'/'backpack' dokładnie (czy_plecak = False)
BAG_LINA_MAIN = kont(0, "backpack", 2854, 3031, LINA)

def ustaw(kontenery, okna, dopasowanie=None):
    loot.znajdz_okna = lambda obraz: okna
    loot.kontenery_z_pamieci = lambda: (kontenery, None) if kontenery else (None, "pamięć nie widzi otwartych kontenerów")
    loot.dopasuj_okna = lambda obraz, o, k: ((dopasowanie, None) if dopasowanie is not None else (list(k[:len(o)]), None))

class FakeMysz:
    klik_log = []
    ekran = None
    def __init__(s, ekran_=None): pass
    def __enter__(s): return s
    def __exit__(s, *a): return False
    def klik(s, x, y, przycisk=1, mod=None, drganie=0): FakeMysz.klik_log.append((x, y, mod))
ekran.Mysz = FakeMysz
ekran.aktualny_prostokat = lambda e=None: None
ekran.pole_na_ekran = lambda dx, dy, pr=None: (900 + dx, 500 + dy)
loot._zrzut = lambda mysz: None

LOGI = []
ops = wypad.OperacjeZywe(zapytaj=lambda z: {}, log=LOGI.append)
ops.ekwipunek = lambda: {5: 3426, 10: 3447}                   # bez liny w ekwipunku

def _rzuca(f, typ=wypad.BrakEkranu):
    try: f()
    except typ as e: return str(e)
    return None

# 1. lina w głównym plecaku: jak dotąd (slot 0 okna głównego plecaka)
ustaw([BAG_LINA_MAIN], [Okno(300)])
FakeMysz.klik_log.clear()
ops.uzyj_line((100, 100, 9), (100, 101, 9))
sprawdz("1 lina w głównym plecaku: Ctrl+klik na jej slocie, potem klik na polu", FakeMysz.klik_log[0] == (100 + 36, 300, "Control_L") and len(FakeMysz.klik_log) == 2, FakeMysz.klik_log)

# 2. lina w DRUGIM pojemniku (nie plecak): znaleziona w jego oknie
ustaw([MAIN, BAG2], [Okno(300), Okno(500)])
FakeMysz.klik_log.clear()
ops.uzyj_line((100, 100, 9), (100, 101, 9))
sprawdz("2 lina w drugim pojemniku: Ctrl+klik w oknie drugiego pojemnika (slot 1, y=500)", FakeMysz.klik_log[0] == (100 + 36, 500, "Control_L"), FakeMysz.klik_log)
sprawdz("2c łopata/inne (wszystkie=False): lina w drugim pojemniku NIE jest znaleziona, jak dotąd", _rzuca(lambda: ops._przedmiot_na_ekranie(None, LINA, "liny")) is not None)

# 3. lina w obu: plecak ma pierwszeństwo
INNY = kont(1, "blue backpack", 2870, LINA, LINA)
ustaw([INNY, kont(0, "backpack", 2854, 3031, LINA)], [Okno(300), Okno(500)])
FakeMysz.klik_log.clear()
ops.uzyj_line((100, 100, 9), (100, 101, 9))
sprawdz("3 lina w obu: pierwszeństwo ma plecak (okno 2, y=500)", FakeMysz.klik_log[0][1] == 500, FakeMysz.klik_log)

# 4. brak liny nigdzie: BrakEkranu z listą sprawdzonych pojemników (nazwa, id, liczba rzeczy) i ekwipunkiem
ustaw([MAIN, kont(1, "blue backpack", 2870, 3035)], [Okno(300), Okno(500)])
FakeMysz.klik_log.clear()
msg = _rzuca(lambda: ops.uzyj_line((100, 100, 9), (100, 101, 9)))
sprawdz("4 brak liny: wyjątek z listą pojemników i ekwipunkiem",
        msg and "backpack (id 2854) 2 rzecz." in msg and "blue backpack (id 2870) 1 rzecz." in msg and "ekwipunek" in msg, msg)
sprawdz("4b bez kliknięć", not FakeMysz.klik_log)

# 5. lina w pamięci, ale okno nie dopasowane: komunikat mówi, gdzie lina leży
ustaw([MAIN, BAG2], [Okno(300)])
loot.dopasuj_okna = lambda obraz, o, k: (None, "niejednoznaczne dopasowanie okien")
msg = _rzuca(lambda: ops.uzyj_line((100, 100, 9), (100, 101, 9)))
sprawdz("5 niedopasowane okna: komunikat z listą pojemników i miejscem liny", msg and "niejednoznaczne" in msg and "blue backpack" in msg and "leży w: blue backpack" in msg, msg)

# 6. lina w ekwipunku (slot 10), nie w oknach: stara ścieżka dalej działa
import pochodnia
pochodnia.pozycje_ekwipunku = lambda obraz: {10: (50, 60)}
ops.ekwipunek = lambda: {5: 3426, 10: LINA}
ustaw([MAIN], [Okno(300)])
FakeMysz.klik_log.clear()
ops.uzyj_line((100, 100, 9), (100, 101, 9))
sprawdz("6 lina w ekwipunku: Ctrl+klik na slocie 10", FakeMysz.klik_log[0] == (50, 60, "Control_L"), FakeMysz.klik_log)
ops.ekwipunek = lambda: {5: 3426, 10: 3447}

# 7. wpadniecie._uzyj_liny: lina w drugim pojemniku -> użycie; brak -> log z listą pojemników
class Cb:
    def __init__(s, o): s.pietra_ops = o
w = wpadniecie.Wpadniecie(Cb(ops), log=LOGI.append, plik=None)
ustaw([MAIN, BAG2], [Okno(300), Okno(500)])
FakeMysz.klik_log.clear(); LOGI.clear()
w._uzyj_liny((100, 100, 9), (100, 101, 9))
sprawdz("7 wpadnięcie: lina z drugiego pojemnika użyta", FakeMysz.klik_log and FakeMysz.klik_log[0][1] == 500, FakeMysz.klik_log)
ustaw([MAIN, kont(1, "blue backpack", 2870, 3035)], [Okno(300), Okno(500)])
FakeMysz.klik_log.clear(); LOGI.clear()
blad = None
try: w._uzyj_liny((100, 100, 9), (100, 101, 9))
except Exception as e: blad = e
tekst = "\n".join(LOGI) + " " + str(blad)
sprawdz("7b wpadnięcie, brak liny: wyjątek, a log ma listę pojemników",
        blad is not None and "backpack (id 2854) 2 rzecz." in tekst and "blue backpack (id 2870) 1 rzecz." in tekst, tekst)

print("\nWSZYSTKO OK" if all(ok) else "\nSĄ BŁĘDY")
sys.exit(0 if all(ok) else 1)
