#!/usr/bin/env python3
"""Pola ognia (fire field) wykrywane z zrzutu ekranu gry. Czysta logika na PIL.Image, bez X11.

Sprite ognia to jaskrawa pomarańczowo-czerwona plama z czystym kolorem (B ~ 0, G 25..50% R).
Czego NIE bierzemy: czerwonej ramki ataku (G = 0), krwi (cienkie plamki, ciemniejsza), złotych
przedmiotów i lamp (B >= ~20, G/R ~ 0.6), pasków HP i łuków ramki
(cienkie, 1-2 piksele grubości) i podłogi jaskini (R < 150). Pole liczymy, gdy ma dość pikseli
ognia, dość pikseli z pełnym sąsiedztwem 2x2 i obwiednię szerszą niż kreska (plama, nie pasek HP).
"""
import io
import os
import subprocess

import numpy as np
from PIL import Image

POLA_X, POLA_Y = 15, 11          # widok mapy w polach (jak w ekran.py)
GRACZ_X, GRACZ_Y = 7, 5

R_MIN = 200                      # jaskrawy czerwony/pomarańczowy
B_MAX = 12                       # czysty kolor: złoto/drewno ma B >= 20
G_MIN = 25                       # G = 0 to ramka ataku
G_RATIO_MAX = 0.5                # G/R: pomarańcz ognia ~0.15-0.45, złoto/żółć >= 0.6
UDZIAL_MIN = 0.012               # min. udział pikseli ognia w polu (ogień zasłonięty stworem ~2%)
OBWIEDNIA_MIN = 0.22             # min. szerokość i wysokość obwiedni pikseli ognia w polu (ułamek boku): kreska/pasek to nie ogień
PLAMA_MIN = 18                   # min. pikseli ognia z pełnym sąsiedztwem 2x2 w polu (ogień ~25-45, pasek HP/ramka ~0-12)


def maska_ognia(a):
    """a: tablica HxWx3 (int16). -> maska bool pikseli o kolorze ognia."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (r >= R_MIN) & (b <= B_MAX) & (g >= G_MIN) & (g * 2 <= r)


def _plama(maska):
    """Piksele maski, które mają w prawo/dół/skos też piksele maski (erozja 2x2)."""
    o = maska.copy()
    o[:-1] &= maska[1:]
    o[-1] = False
    o[:, :-1] &= maska[:, 1:]
    o[:, -1] = False
    o[:-1, :-1] &= maska[1:, 1:]
    return o


def pola_ognia(obraz, prostokat=None):
    """Zbiór (dx, dy) pól z ogniem względem gracza w widoku mapy. `prostokat` = (L, T, R, B)
    mapy na zrzucie (domyślnie ekran.prostokat_mapy)."""
    if prostokat is None:
        import sys  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ekran  # noqa: PLC0415
        prostokat = ekran.prostokat_mapy(obraz)
    L, T, R, B = prostokat
    mapa = obraz.convert("RGB").crop((L, T, R, B))     # tylko widok mapy (ok. 1/3 zrzutu)
    a = np.asarray(mapa, dtype=np.int16)
    wys_a, szer_a = a.shape[0], a.shape[1]
    bok_x, bok_y = (R - L) / POLA_X, (B - T) / POLA_Y
    maska = maska_ognia(a)
    plama = _plama(maska)
    wynik = set()
    for ty in range(POLA_Y):
        y0, y1 = round(ty * bok_y), min(round((ty + 1) * bok_y), wys_a)
        if y0 >= wys_a or y1 <= y0:
            continue
        for tx in range(POLA_X):
            x0, x1 = round(tx * bok_x), min(round((tx + 1) * bok_x), szer_a)
            if x0 >= szer_a or x1 <= x0:
                continue
            if int(maska[y0:y1, x0:x1].sum()) < UDZIAL_MIN * (y1 - y0) * (x1 - x0):
                continue
            if int(plama[y0:y1, x0:x1].sum()) < PLAMA_MIN:
                continue
            wiersze = np.flatnonzero(maska[y0:y1, x0:x1].any(axis=1))
            kolumny = np.flatnonzero(maska[y0:y1, x0:x1].any(axis=0))
            if (wiersze[-1] - wiersze[0] + 1 < OBWIEDNIA_MIN * (y1 - y0)
                    or kolumny[-1] - kolumny[0] + 1 < OBWIEDNIA_MIN * (x1 - x0)):
                continue
            wynik.add((tx - GRACZ_X, ty - GRACZ_Y))
    return wynik


def zrzut_ppm(gniazdo):
    """Szybki zrzut sesji gry (grim, PPM bez kompresji: ok. 40 ms zamiast ok. 0,5-0,9 s dla PNG).
    Tylko odczyt; `gniazdo` = nazwa gniazda Wayland sesji (ekran.SESJA). Timeout 2 s, 2 próby;
    po porażce ekran.ZrzutNiedostepny."""
    import ekran  # noqa: PLC0415
    return Image.open(io.BytesIO(ekran.grim("ppm", gniazdo=gniazdo))).convert("RGB")


def opis(pola):
    """Krótki tekst do logu: posortowane (dx,dy) albo 'brak'."""
    return " ".join(f"({dx:+d},{dy:+d})" for dx, dy in sorted(pola)) or "brak"


if __name__ == "__main__":
    import sys
    for plik in sys.argv[1:]:
        print(plik, opis(pola_ognia(Image.open(plik))))
