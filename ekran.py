#!/usr/bin/env python3
"""Ekran gry: zrzut, wykrywanie prostokąta mapy, mysz przez XTEST (atak, otwieranie zwłok).

CLI (nic z tego nie wysyła inputu do gry):
  ekran.py mapa [plik.png]   wypisuje prostokąt mapy i zapisuje podgląd z siatką pól
  ekran.py test              sprawdza wykrywanie na zapisanych zrzutach (scratchpad)
"""
import io
import os
import random
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from Xlib import X, XK, display  # noqa: E402
from Xlib.ext import xtest  # noqa: E402

import bot  # noqa: E402

POLA_X, POLA_Y = 15, 11          # widok mapy w polach
GRACZ_X, GRACZ_Y = 7, 5          # pole gracza (od 0)
SESJA = bot.instancja.sesja() / "wayland"   # bez RETRONIC_ID: retronic-sesja/wayland
SCRATCH = Path(__file__).resolve().parent / "testy" / "dane"   # zrzuty do testów (ekran.py test)

_cache_mapy = {}                 # (szerokość, wysokość) -> (L, T, R, B)


# --- zrzut i wykrywanie mapy -------------------------------------------------

GRIM_TIMEOUT = {"png": 4.0, "ppm": 2.0, "jpeg": 5.0}   # s na jedną próbę (13.10: 10 s x5 = zawieszenie bota)
GRIM_PROBY = 2                   # liczba prób zrzutu
GRIM_PAUZA = 0.3                 # s między próbami
GRIM_BLEDY = 0                   # licznik zrzutów, które nie udały się mimo ponowień
GRIM_OSTATNI_OK = 0.0            # time.time() ostatniego udanego zrzutu


class ZrzutNiedostepny(subprocess.TimeoutExpired):
    """Zrzut ekranu (grim) nie powiódł się mimo ponowień. Podklasa TimeoutExpired (cmd = grim), więc
    dotychczasowe pętle "okno gry niewidoczne" w mozg.py i cavebot.py traktują go jak wiszący grim;
    uh.py rozpoznaje go po nazwie i nie liczy porażki."""

    def __init__(self, cmd, timeout, czas=0.0, proby=1):
        super().__init__(cmd, timeout)
        self.czas = czas
        self.proby = proby

    def __str__(self):
        return f"zrzut ekranu niedostępny: {self.proby} prób, {self.czas:.1f} s (timeout {self.timeout} s)"


def grim(format="png", timeout=None, proby=None, gniazdo=None):
    """Bajty zrzutu sesji gry (grim na gnieździe Wayland sesji). `proby` prób z `timeout` s każda
    i pauzą GRIM_PAUZA; po porażce wszystkich: ZrzutNiedostepny."""
    global GRIM_BLEDY, GRIM_OSTATNI_OK
    timeout = GRIM_TIMEOUT.get(format, 5.0) if timeout is None else timeout
    proby = max(1, int(GRIM_PROBY if proby is None else proby))
    gniazdo = gniazdo or SESJA.read_text().strip()
    srodowisko = dict(os.environ, WAYLAND_DISPLAY=gniazdo)
    cmd = ["grim", "-t", format, "-"]
    t0 = time.time()
    for n in range(proby):
        try:
            wynik = subprocess.run(cmd, env=srodowisko, capture_output=True, timeout=timeout, check=True)
            GRIM_OSTATNI_OK = time.time()
            return wynik.stdout
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            if n + 1 < proby:
                time.sleep(GRIM_PAUZA)
    GRIM_BLEDY += 1
    raise ZrzutNiedostepny(cmd, timeout, czas=time.time() - t0, proby=proby)


def zrzut():
    """PIL.Image ekranu sesji gry (grim na gnieździe Wayland sesji; timeout 4 s, 2 próby)."""
    return Image.open(io.BytesIO(grim("png"))).convert("RGB")


def _rozmiar_ekranu(ekran=None):
    dpy = display.Display(ekran or bot.ekran_gry())
    try:
        s = dpy.screen()
        return s.width_in_pixels, s.height_in_pixels
    finally:
        dpy.close()


def _przedzialy(maska):
    """Lista (początek, koniec) ciągów True w wektorze."""
    d = np.diff(np.concatenate([[0], maska.astype(np.int8), [0]]))
    return list(zip(np.where(d == 1)[0].tolist(), np.where(d == -1)[0].tolist()))


def prostokat_mapy(obraz):
    """Wykrywa (L, T, R, B) mapy na zrzucie. Tło UI jest jednolicie ciemnoszare
    (R~G~B, 10..40), treść mapy już nie (nawet czarna winieta ma wartości < 10).
    Wynik w cache pod kluczem = rozmiar zrzutu."""
    klucz = obraz.size
    if klucz in _cache_mapy:
        return _cache_mapy[klucz]
    a = np.asarray(obraz.convert("RGB")).astype(np.int16)
    szer, wys = klucz
    mx, mn = a.max(2), a.min(2)
    tlo = (mx <= 40) & (mn >= 10) & (mx - mn <= 6)
    tresc = ~tlo
    # 1. L i R: najczęstszy początek/koniec długich ciągów treści w wierszach
    poczatki, konce = Counter(), Counter()
    for y in range(wys):
        dluga = [p for p in _przedzialy(tresc[y]) if p[1] - p[0] >= szer // 5]
        if dluga:
            p = max(dluga, key=lambda p: p[1] - p[0])
            poczatki[p[0]] += 1
            konce[p[1]] += 1
    if not poczatki:
        raise RuntimeError("nie widzę mapy na zrzucie")
    L, R = poczatki.most_common(1)[0][0], konce.most_common(1)[0][0]
    # 2. T i B: najdłuższy pionowy blok wierszy wypełnionych treścią na [L, R)
    wypelnienie = tresc[:, L:R].mean(1) >= 0.9
    T, B = max(_przedzialy(wypelnienie), key=lambda p: p[1] - p[0])
    # 3. dopasowanie do proporcji 15:11 (kafelek kwadratowy)
    wysokosc = round((R - L) * POLA_Y / POLA_X)
    # 2b. 13.10: ciemna scena (jaskinia) ma szare wiersze wzięte za tło i blok wychodzi za niski/przesunięty;
    # mapa ma 1-px czarną ramkę nad i pod sobą otoczoną jednolitym szarym UI: szukamy pary ramek w odstępie ~wysokosc
    wiersz_czarny = mx[:, L:R].mean(1) <= 8
    wiersz_tlo = tlo[:, L:R].mean(1) >= 0.97
    for y in range(1, wys - wysokosc - 2):
        if wiersz_czarny[y] and wiersz_tlo[y - 1]:
            for y2 in range(y + wysokosc - 6, y + wysokosc + 2):
                if y2 < wys - 1 and wiersz_czarny[y2] and wiersz_tlo[y2 + 1]:
                    T, B = y + 1, y + 1 + wysokosc
                    break
            else:
                continue
            break
    if abs((B - T) - wysokosc) > max(6, wysokosc // 25):
        print(f"UWAGA: blok mapy {B - T} px zamiast {wysokosc} px, przyjmuję górę bloku", file=sys.stderr)
    B = T + wysokosc
    # przy krawędzi ekranu pierwszy/ostatni piksel bywa tłem lub winietą
    if L <= 2:
        L = 0
    if R >= szer - 2:
        R = szer
    _cache_mapy[klucz] = (L, T, R, B)
    return _cache_mapy[klucz]


def aktualny_prostokat(ekran=None):
    """Prostokąt mapy dla bieżącego rozmiaru ekranu; zrzut robi tylko przy nowym rozmiarze."""
    rozmiar = _rozmiar_ekranu(ekran)
    if rozmiar not in _cache_mapy:
        obraz = zrzut()
        if obraz.size != rozmiar:
            obraz = obraz.resize(rozmiar)
        prostokat_mapy(obraz)
    return _cache_mapy[rozmiar]


def pole_na_ekran(dx, dy, prostokat=None):
    """Środek pola przesuniętego o (dx, dy) względem gracza -> (px, py) w pikselach ekranu."""
    L, T, R, B = prostokat or aktualny_prostokat()
    return (round(L + (GRACZ_X + dx + 0.5) * (R - L) / POLA_X),
            round(T + (GRACZ_Y + dy + 0.5) * (B - T) / POLA_Y))


def czerwona_ramka(obraz, dx, dy, prostokat):
    """Czy pole (dx, dy) ma czerwoną ramkę ataku. Liczy czerwone piksele w pasach
    przy krawędziach pola; krew na podłodze nie tworzy ciągłych krawędzi."""
    L, T, R, B = prostokat
    bok = (R - L) / POLA_X
    x0 = L + (GRACZ_X + dx) * bok
    y0 = T + (GRACZ_Y + dy) * bok
    pole = np.asarray(obraz.convert("RGB").crop((round(x0), round(y0), round(x0 + bok), round(y0 + bok))),
                      dtype=np.int16)
    if pole.size == 0:
        return False
    czerwone = (pole[..., 0] > 170) & (pole[..., 1] < 70) & (pole[..., 2] < 70)
    pas = max(2, round(bok * 0.08))
    krawedzie = [czerwone[:pas].any(axis=0), czerwone[-pas:].any(axis=0),
                 czerwone[:, :pas].any(axis=1), czerwone[:, -pas:].any(axis=1)]
    return sum(k.mean() > 0.6 for k in krawedzie) >= 3


def atakowany(stwor, gracz):
    """Czy stwór ma teraz czerwoną ramkę (atak trwa). Robi świeży zrzut."""
    obraz = zrzut()
    rozmiar = _rozmiar_ekranu()
    if obraz.size != rozmiar:
        obraz = obraz.resize(rozmiar)
    prostokat = aktualny_prostokat()
    if jasnosc_mapy(obraz, prostokat) < PROG_CIEMNOSCI:
        # po ciemku ramki nie widać: None = nie wiadomo (cavebot zdecyduje po HP celu)
        return None
    return czerwona_ramka(obraz, stwor["x"] - gracz["x"], stwor["y"] - gracz["y"], prostokat)


PROG_CIEMNOSCI = 3   # średnia jasność mapy (0-255), poniżej której nie oceniamy ramki


def jasnosc_mapy(obraz, prostokat):
    """Średnia jasność obszaru mapy (zgaszona pochodnia w jaskini daje prawie czarny obraz)."""
    return float(np.asarray(obraz.convert("L").crop(prostokat), dtype=np.float32).mean())


# --- mysz (XTEST) ------------------------------------------------------------

def _przerwa(a=50, b=150):
    time.sleep(random.randint(a, b) / 1000)


def _przytrzymanie():
    time.sleep(random.randint(40, 110) / 1000)


class Mysz:
    """Mysz i modyfikatory przez XTEST na ekranie gry. Każda akcja sprawdza STOP."""

    def __init__(self, ekran=None):
        self.ekran = ekran or bot.ekran_gry()
        self.dpy = display.Display(self.ekran)

    def zamknij(self):
        self.dpy.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.zamknij()

    def _kod(self, keysym):
        kod = self.dpy.keysym_to_keycode(XK.string_to_keysym(keysym))
        if not kod:
            raise ValueError(f"nieznany klawisz: {keysym}")
        return kod

    def _wejscie(self, rodzaj, szczegol=0, **kw):
        xtest.fake_input(self.dpy, rodzaj, szczegol, **kw)
        self.dpy.sync()

    @staticmethod
    def _drganie(x, y, drganie):
        return x + random.randint(-drganie, drganie), y + random.randint(-drganie, drganie)

    def ruch(self, x, y, drganie=3, kroki=None):
        """Płynny ruch kursora do (x, y) z losowym przesunięciem +-drganie px."""
        bot.sprawdz_stop()
        x, y = self._drganie(x, y, drganie)
        p = self.dpy.screen().root.query_pointer()
        x0, y0 = p.root_x, p.root_y
        kroki = kroki or random.randint(3, 6)
        for i in range(1, kroki + 1):
            bot.sprawdz_stop()
            self._wejscie(X.MotionNotify, x=round(x0 + (x - x0) * i / kroki),
                          y=round(y0 + (y - y0) * i / kroki))
            time.sleep(random.randint(8, 25) / 1000)
        _przerwa(30, 90)
        return x, y

    def klik(self, x, y, przycisk=1, modyfikator=None, drganie=3):
        """Klik przyciskiem (1 lewy, 3 prawy), opcjonalnie z modyfikatorem (Alt_L, Control_L, Shift_L)."""
        x, y = self.ruch(x, y, drganie)
        kod = self._kod(modyfikator) if modyfikator else None
        try:
            if kod:
                self._wejscie(X.KeyPress, kod)
                _przerwa(40, 90)
            bot.sprawdz_stop()
            self._wejscie(X.ButtonPress, przycisk)
            try:
                _przytrzymanie()
            finally:
                self._wejscie(X.ButtonRelease, przycisk)
        finally:
            if kod:
                _przerwa(30, 70)
                self._wejscie(X.KeyRelease, kod)
        _przerwa()

    def klawisz(self, keysym):
        """Naciśnięcie i puszczenie jednego klawisza (np. "Return" w oknie ilości)."""
        kod = self._kod(keysym)
        self._wejscie(X.KeyPress, kod)
        try:
            _przerwa(40, 90)
        finally:
            self._wejscie(X.KeyRelease, kod)
        _przerwa()

    def lewy(self, x, y, modyfikator=None, drganie=3):
        self.klik(x, y, 1, modyfikator, drganie)

    def prawy(self, x, y, modyfikator=None, drganie=3):
        self.klik(x, y, 3, modyfikator, drganie)

    def przeciagnij(self, x1, y1, x2, y2, drganie=3):
        """Wciska lewy na (x1, y1), przesuwa kilkoma krokami do (x2, y2) i puszcza."""
        x1, y1 = self.ruch(x1, y1, drganie)
        x2, y2 = self._drganie(x2, y2, drganie)
        self._wejscie(X.ButtonPress, 1)
        try:
            _przerwa(50, 120)
            kroki = random.randint(5, 9)
            for i in range(1, kroki + 1):
                bot.sprawdz_stop()
                self._wejscie(X.MotionNotify, x=round(x1 + (x2 - x1) * i / kroki),
                              y=round(y1 + (y2 - y1) * i / kroki))
                time.sleep(random.randint(15, 40) / 1000)
            _przerwa(40, 100)
        finally:
            self._wejscie(X.ButtonRelease, 1)
        _przerwa()

    def przeciagnij_pola(self, dx1, dy1, dx2, dy2):
        """Przeciągnięcie z pola (dx1, dy1) na pole (dx2, dy2) względem gracza."""
        prostokat = aktualny_prostokat(self.ekran)
        self.przeciagnij(*pole_na_ekran(dx1, dy1, prostokat), *pole_na_ekran(dx2, dy2, prostokat))


def klik_pola(dx, dy, przycisk=1, modyfikator=None):
    """Klik na polu (dx, dy) względem gracza, z drganiem w obrębie pola."""
    if abs(dx) > GRACZ_X or abs(dy) > GRACZ_Y:
        raise ValueError(f"pole ({dx}, {dy}) poza widokiem mapy, nie klikam")
    with Mysz() as mysz:
        mysz.klik(*pole_na_ekran(dx, dy, aktualny_prostokat(mysz.ekran)), przycisk, modyfikator)


ATAK_MODYFIKATOR = "Alt_L"   # None = zwykły klik (do testu); Alt+klik był trybem od początku


def atakuj(stwor, gracz):
    """Lewy klik na polu stwora zaznacza cel (ATAK_MODYFIKATOR: None = zwykły, "Alt_L" = dawny Alt+klik)."""
    klik_pola(stwor["x"] - gracz["x"], stwor["y"] - gracz["y"], 1, ATAK_MODYFIKATOR)


def otworz(dx, dy):
    """Ctrl + lewy klik na polu (dx, dy) względem gracza: otwiera zwłoki/kontener."""
    klik_pola(dx, dy, 1, "Control_L")


# --- CLI (tylko offline) -----------------------------------------------------

def podglad(obraz, prostokat, plik):
    L, T, R, B = prostokat
    kopia = obraz.copy()
    r = ImageDraw.Draw(kopia)
    kw, kh = (R - L) / POLA_X, (B - T) / POLA_Y
    for i in range(POLA_X + 1):
        r.line([(L + i * kw, T), (L + i * kw, B)], fill=(0, 255, 255))
    for j in range(POLA_Y + 1):
        r.line([(L, T + j * kh), (R, T + j * kh)], fill=(0, 255, 255))
    r.rectangle([L + GRACZ_X * kw, T + GRACZ_Y * kh, L + (GRACZ_X + 1) * kw, T + (GRACZ_Y + 1) * kh],
                outline=(255, 0, 0), width=2)
    kopia.save(plik)


ZNANE = {"z2.png": ((1536, 960), (127, 38, 1227, 845)),
         "z3.png": ((1536, 960), (127, 38, 1227, 845)),
         "z6.png": ((734, 910), (0, 215, 550, 617))}


def test(tolerancja=3):
    ok = True
    for nazwa, (rozmiar, oczekiwany) in ZNANE.items():
        _cache_mapy.clear()
        obraz = Image.open(SCRATCH / nazwa).convert("RGB")
        wynik = prostokat_mapy(obraz)
        zgodny = obraz.size == rozmiar and all(abs(a - b) <= tolerancja for a, b in zip(wynik, oczekiwany))
        ok &= zgodny
        print(f"{nazwa} {obraz.size}: wykryto {wynik}, zmierzono {oczekiwany} -> {'OK' if zgodny else 'BŁĄD'}")
    return ok


def main(argv):
    komenda = argv[1] if len(argv) > 1 else "mapa"
    if komenda == "test":
        return 0 if test() else 1
    if komenda == "mapa":
        obraz = Image.open(argv[2]).convert("RGB") if len(argv) > 2 else zrzut()
        prostokat = prostokat_mapy(obraz)
        L, T, R, B = prostokat
        print(f"ekran {obraz.size[0]}x{obraz.size[1]}  mapa L={L} T={T} R={R} B={B}  pole {(R - L) / POLA_X:.1f}x{(B - T) / POLA_Y:.1f} px")
        plik = SCRATCH / "podglad_mapy.png"
        podglad(obraz, prostokat, plik)
        print("podgląd:", plik)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
