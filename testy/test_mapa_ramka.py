"""Prostokąt mapy z czarnej ramki (ekran.prostokat_mapy), 24.10 (serwis Thais, odchyd 14:00 i gebelish 12:52: "UWAGA: blok mapy 424 px
zamiast 505 px"). Ciemna scena (ciemne piksele 10..40 R~G~B liczą się jako tło UI) skracała ciągi treści: R-L wychodziło ~688 zamiast 981,
więc klik w pole szedł z ~70% skali (klik_bez_ruchu x16, postać w bocznej uliczce, "krążę" przy banku). Mapa ma 1-px czarną ramkę otoczoną tłem UI:
przy rozjeździe prostokąt liczymy z ramki (jej szerokość i wysokość muszą trzymać 15:11). Atrapy i syntetyczny zrzut, bez X11, bez inputu."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import contextlib, io, sys
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import numpy as np
from PIL import Image
import ekran

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

ROZ = (1175, 910)
TLO = (31, 32, 29)                      # tło UI jak na zrzucie odchyda (odchyd_now.png)
MAPA = (5, 38, 986, 757)                # prostokąt mapy z poprawnego wykrycia na 1175x910 (ramka: kolumny 5 i 985, wiersze 37 i 756)

def ekran_gry(ciemno_od_x=None, ciemno_od_y=None, ramka=True, dziura_gora=0, dziura_x=400):
    """Mapa = szum jak trawa/podłoga; `ciemno_od_x/y`: część sceny w ciemnym szarym (25,25,25), którą wykrywanie bierze za tło UI."""
    rng = np.random.default_rng(11)
    a = np.empty((ROZ[1], ROZ[0], 3), np.uint8); a[:] = TLO
    L, T, R, B = MAPA
    a[T:B - 1, L + 1:R - 1] = rng.integers(60, 220, (B - 1 - T, R - 1 - L - 1, 3), dtype=np.uint8)
    a[T:B - 1, L + 1:R - 1, 0] = np.maximum(a[T:B - 1, L + 1:R - 1, 0], 90)
    if ramka:
        a[T - 1, L:R - 1] = 0; a[B - 1, L:R - 1] = 0                 # góra i dół ramki (wiersze 37 i 756)
        a[T - 1:B, L] = 0; a[T - 1:B, R - 1] = 0                     # lewa i prawa (kolumny 5 i 985)
    if ciemno_od_x is not None:
        a[T:B - 1, ciemno_od_x:R - 1] = (25, 25, 25)
    if ciemno_od_y is not None:
        a[ciemno_od_y:B - 1, L + 1:R - 1] = (25, 25, 25)
    if dziura_gora:                                                   # jasne piksele w górnym wierszu ramki (jak kolumna 980 = 39 na prawdziwym zrzucie)
        a[T - 1, dziura_x:dziura_x + dziura_gora] = (39, 39, 39)
    a[45:50, 1000:1170] = (200, 40, 40)                               # kawałek panelu bocznego (krótszy niż 1/5 szerokości)
    return Image.fromarray(a)

def czysto():
    ekran._cache_mapy.clear(); ekran._ostatni_rozmiar = None; ekran._rozmiar_od = 0.0
    for nazwa in ("_niepewny", "_zapomniany"):
        if hasattr(ekran, nazwa): getattr(ekran, nazwa).clear()

def wykryj(obraz):
    err, out = io.StringIO(), io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        r = ekran.prostokat_mapy(obraz)
    return r, err.getvalue() + out.getvalue()

def blisko(r, wz, tol=2):
    return all(abs(x - y) <= tol for x, y in zip(r, wz))

# --- a) jasna scena: bez zmian ---
czysto()
r, tekst = wykryj(ekran_gry())
sprawdz("a1 pełna mapa: prostokąt = mapa, bez ostrzeżenia", blisko(r, MAPA) and "UWAGA" not in tekst, f"{r} {tekst!r}")
sprawdz("a2 pełna mapa trafia do cache", ekran._cache_mapy.get(ROZ) == r)

# --- b) ciemna prawa i dolna część sceny (odtworzenie z logu 14:00: R-L ~688, blok 424 zamiast 505) ---
czysto()
ciemna = ekran_gry(ciemno_od_x=693, ciemno_od_y=38 + 424)
r, tekst = wykryj(ciemna)
sprawdz("b1 ciemna scena: prostokąt = cała mapa (z ramki), nie 688 px szerokości", blisko(r, MAPA), f"{r} {tekst!r}")
sprawdz("b2 ciemna scena: wynik jest pewny (bez UWAGA) i trafia do cache", "UWAGA" not in tekst and ekran._cache_mapy.get(ROZ) == r, f"{tekst!r} {ekran._cache_mapy}")
sprawdz("b3 log [EKRAN] z powodem naprawy", "[EKRAN]" in tekst and "ramki" in tekst, tekst)
szer_klik = ekran.pole_na_ekran(3, 0, r)[0] - ekran.pole_na_ekran(0, 0, r)[0]
sprawdz("b4 klik 3 pola w prawo = 3 x ~65 px (nie 3 x ~46 px)", abs(szer_klik - 3 * (MAPA[2] - MAPA[0]) / 15) <= 4, str(szer_klik))

# --- c) tylko ciemna prawa część (rozjazd wysokości z samej szerokości) ---
czysto()
r, tekst = wykryj(ekran_gry(ciemno_od_x=693))
sprawdz("c1 ciemna prawa część: prostokąt = cała mapa", blisko(r, MAPA), f"{r} {tekst!r}")

# --- d) bez ramki (okno UI zasłania mapę): zachowanie jak przed zmianą, niepewny wynik, brak cache ---
czysto()
r, tekst = wykryj(ekran_gry(ciemno_od_x=693, ciemno_od_y=38 + 424, ramka=False))
sprawdz("d1 bez ramki: nadal ostrzeżenie o rozjeździe i brak cache (nic nie zgadujemy)", "UWAGA" in tekst and ROZ not in ekran._cache_mapy, f"{r} {tekst!r}")

# --- e) pojedynczy jasny piksel w górnym wierszu ramki nie rozbija jej na dwa odcinki (24.10, przegląd: gra_ciemna_kolanoth.png, kolumna 980) ---
czysto()
r, tekst = wykryj(ekran_gry(ciemno_od_x=693, ciemno_od_y=38 + 424, dziura_gora=1))
sprawdz("e1 ciemna scena + 1 jasny piksel w ramce: prostokąt = cała mapa (z ramki), wynik pewny", blisko(r, MAPA) and "UWAGA" not in tekst and ekran._cache_mapy.get(ROZ) == r, f"{r} {tekst!r}")
czysto()
r, tekst = wykryj(ekran_gry(ciemno_od_x=693, ciemno_od_y=38 + 424, dziura_gora=3))
sprawdz("e2 przerwa 3 px w ramce też jest scalana", blisko(r, MAPA) and "UWAGA" not in tekst, f"{r} {tekst!r}")
czysto()
r, tekst = wykryj(ekran_gry(ciemno_od_x=693, ciemno_od_y=38 + 424, dziura_gora=40))
sprawdz("e3 szeroka przerwa (40 px) nie jest scalana: brak zgodnego zasięgu = ostrzeżenie i brak cache (warunki bez osłabienia)",
        "UWAGA" in tekst and ROZ not in ekran._cache_mapy, f"{r} {tekst!r}")
sprawdz("e4 _scal_przedzialy: luka <= 3 scala, większa nie",
        ekran._scal_przedzialy([(0, 10), (11, 20)], 3) == [(0, 20)] and ekran._scal_przedzialy([(0, 10), (14, 20)], 3) == [(0, 10), (14, 20)]
        and ekran._scal_przedzialy([], 3) == [])

# --- f) prawdziwy zrzut ciemnej sceny (Kolanoth): prostokąt z treści jest poprawny, a _z_ramki bezpośrednio daje ten sam wynik ---
# (na tym zrzucie nie ma rozjazdu, więc prostokat_mapy nie woła _z_ramki: sprawdzamy oba tory osobno)
PNG = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "dane", "logowanie", "gra_ciemna_kolanoth.png")
czysto()
zrzut = Image.open(PNG).convert("RGB")
r, tekst = wykryj(zrzut)
sprawdz("f1 gra_ciemna_kolanoth.png: prostokat_mapy = (5, 38, 986, 757), bez ostrzeżenia", r == MAPA and "UWAGA" not in tekst, f"{r} {tekst!r}")
b = np.asarray(zrzut).astype(np.int16); mx_, mn_ = b.max(2), b.min(2)
tlo_ = (mx_ <= 40) & (mn_ >= 10) & (mx_ - mn_ <= 6)
sprawdz("f2 gra_ciemna_kolanoth.png: _z_ramki bezpośrednio = (5, 38, 986, 757) mimo jasnego piksela (kolumna 980) w wierszu 37",
        mx_[37, 980] > 8 and ekran._z_ramki(mx_, tlo_) == MAPA, f"{ekran._z_ramki(mx_, tlo_)} {mx_[37, 980]}")

print("WYNIK", "OK" if all(ok) else "FAIL"); sys.exit(0 if all(ok) else 1)
