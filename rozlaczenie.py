"""Rozłączenie klienta (21.10, ROZLACZENIE_STOP): serwer wylogował postać, klient pokazuje ekran logowania
(„Character List” / „Enter Game”), a pamięć gry stoi na ostatnim stanie, więc bot dalej „gra” (strzałki w próżnię).
Spec: dane_tibia/SPEC_rozlaczenie_1021.md.

Sygnał = pamięć zamrożona >= PROG_S ORAZ ZRZUTY_POTW ostatnich zrzutów z rzędu to ekran logowania.
  * odcisk życia (hp, mana, exp, pozycja, lista stworów...) stoi: tani filtr wstępny (sama pamięć w zdrowej grze stoi
    0,66 raza na godzinę: loot, przerwa, pauza), zrzut robimy dopiero po PODEJRZENIE_S i co ZRZUT_CO_S;
  * zrzut: tapeta logowania to stała grafika, siatka 32x24 po pominięciu paska FPS i okien dialogowych jest identyczna
    na wszystkich zrzutach (wzorzec dane_tibia/ekran_logowania_wzorzec.json), a klatki gry zgadzają się w 0-7%.

Moduł nie ma zależności od bota; zrzut i zegar wstrzykiwane (testy bez gry). CLI:
  python3 rozlaczenie.py zbuduj <png...>   zapisuje wzorzec (uśrednione siatki zrzutów logowania)
  python3 rozlaczenie.py ocen <png...>     wypisuje zgodność zrzutów z wzorcem i werdykt
"""
import io
import json
import sys
from pathlib import Path

PROG_S = 25.0              # s zamrożonego odcisku, od których (i przy potwierdzeniu zrzutami) mamy rozłączenie
PODEJRZENIE_S = 10.0       # s zamrożenia, po których zaczynamy robić zrzuty
ZRZUT_CO_S = 5.0           # s między zrzutami przy podejrzeniu
ZRZUT_CO_PAUZA_S = 3.0     # s między zrzutami w stanie rozłączenia (szukamy powrotu do gry)
ZRZUTY_POTW = 2            # tyle kolejnych zrzutów z ekranem logowania potwierdza rozłączenie
ZRZUTY_WZNOW = 2           # tyle kolejnych zrzutów bez ekranu logowania wznawia pracę
ZMIANY_WZNOW = 3           # wznowienie bez zrzutu: tyle zmian odcisku z rzędu (pamięć się rusza), bez zrzutu z logowaniem
ZGODNOSC_PROG = 0.90       # część komórek siatki zgodnych z wzorcem = ekran logowania
KOMORKA_L1 = 60            # komórka zgodna, gdy suma |dR|+|dG|+|dB| < tyle (0-765)
SIATKA = (32, 24)          # szerokość, wysokość siatki (komórki uśrednione z całego zrzutu)
PLIK_WZORCA = Path(__file__).resolve().parent / "dane_tibia" / "ekran_logowania_wzorzec.json"
ZRZUT_TIMEOUT_S = 1.5      # grim: jedna próba (wiszący grim nie blokuje obiegu na 4 s)

_wzorzec = None


def odcisk(g, poz, stwory):
    """Hashowalny odcisk „życia” klienta: gdy stoi, pamięć gry nie żyje. Tylko to, co bot już ma (bez nowych zapytań)."""
    g = g or {}
    pola = tuple(g.get(k) for k in ("hp", "max_hp", "mana", "max_mana", "cap", "exp", "level"))
    lista = tuple(sorted((s.get("id"), s.get("x"), s.get("y"), s.get("z"), s.get("hp"), s.get("kierunek"))
                         for s in (stwory or ()) if isinstance(s, dict)))
    return (pola, tuple(poz) if poz is not None else None, lista)


class Detektor:
    """Czysta logika. `krok(t, odcisk, zrzut)` -> None | "rozlaczenie" | "wznowienie".
    `zrzut` = funkcja bez argumentów zwracająca True (ekran logowania), False (gra) albo None (brak zrzutu); wołana tylko
    wtedy, gdy zrzut jest potrzebny (podejrzenie albo pauza), więc w zdrowej grze koszt = 0."""

    def __init__(self, prog_s=PROG_S, podejrzenie_s=PODEJRZENIE_S, zrzut_co_s=ZRZUT_CO_S, zrzut_co_pauza_s=ZRZUT_CO_PAUZA_S,
                 potw=ZRZUTY_POTW, wznow=ZRZUTY_WZNOW, zmiany=ZMIANY_WZNOW):
        self.prog_s, self.podejrzenie_s = prog_s, podejrzenie_s
        self.zrzut_co_s, self.zrzut_co_pauza_s = zrzut_co_s, zrzut_co_pauza_s
        self.potw, self.wznow, self.zmiany = potw, wznow, zmiany
        self.rozlaczony = False
        self.ostatni = None            # ostatni odcisk
        self.t_zm = None               # kiedy odcisk ostatnio się zmienił (albo pierwsza próbka)
        self.t_rozl = None             # kiedy ogłoszono rozłączenie
        self.t_zrzut = float("-inf")   # kiedy ostatnio zrobiono zrzut
        self.pozytywne = 0             # kolejne zrzuty z ekranem logowania
        self.negatywne = 0             # kolejne zrzuty bez ekranu logowania (w pauzie)
        self.zmiany_pod_rzad = 0       # kolejne zmiany odcisku (w pauzie, bez zrzutu z logowaniem)
        self.ostatni_zrzut = None      # wynik ostatniego zrzutu: True/False/None
        self.zamrozone_s = 0.0

    def reset(self, t, odcisk=None):
        self.rozlaczony = False
        self.ostatni, self.t_zm, self.t_rozl = odcisk, t, None
        self.t_zrzut = float("-inf")
        self.pozytywne = self.negatywne = self.zmiany_pod_rzad = 0
        self.ostatni_zrzut = None

    def _zrzut(self, t, zrzut):
        self.t_zrzut = t
        try:
            w = zrzut() if zrzut is not None else None
        except Exception:                       # noqa: BLE001  detekcja nigdy nie wywraca bota
            w = None
        self.ostatni_zrzut = w if w in (True, False) else None
        return self.ostatni_zrzut

    def krok(self, t, odcisk, zrzut=None):
        if self.t_zm is None:
            self.ostatni, self.t_zm = odcisk, t
            zmiana = False
        else:
            zmiana = odcisk != self.ostatni
            if zmiana:
                self.ostatni, self.t_zm = odcisk, t
        self.zamrozone_s = t - self.t_zm
        if self.rozlaczony:
            return self._pauza(t, zmiana, zrzut)
        if zmiana:
            self.pozytywne = 0
            return None
        if self.zamrozone_s < self.podejrzenie_s or t - self.t_zrzut < self.zrzut_co_s:
            return None
        w = self._zrzut(t, zrzut)
        if w is True:
            self.pozytywne += 1
        elif w is False:
            self.pozytywne = 0
        if self.pozytywne >= self.potw and self.zamrozone_s >= self.prog_s:
            self.rozlaczony, self.t_rozl = True, t
            self.negatywne = self.zmiany_pod_rzad = 0
            return "rozlaczenie"
        return None

    def _pauza(self, t, zmiana, zrzut):
        w = None
        if t - self.t_zrzut >= self.zrzut_co_pauza_s:
            w = self._zrzut(t, zrzut)
        if w is True:
            self.negatywne = self.zmiany_pod_rzad = 0
            return None
        if w is False:
            self.negatywne += 1
            if self.negatywne >= self.wznow:
                self.reset(t, self.ostatni)
                return "wznowienie"
            return None
        # brak zrzutu w tym kroku: liczą się tylko zmiany pamięci, i tylko gdy zrzut nie pokazuje ekranu logowania
        if zmiana and self.ostatni_zrzut is not True:
            self.zmiany_pod_rzad += 1
            if self.zmiany_pod_rzad >= self.zmiany:
                self.reset(t, self.ostatni)
                return "wznowienie"
        elif not zmiana:
            self.zmiany_pod_rzad = 0
        return None


# --- zrzut ekranu i klasyfikator ekranu logowania -------------------------------------------------------------

def _siatka(obraz):
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    return np.asarray(obraz.convert("RGB").resize(SIATKA, Image.BOX), dtype=float)


def _maska():
    import numpy as np  # noqa: PLC0415
    w, h = SIATKA
    m = np.ones((h, w), dtype=bool)
    m[:int(h * 0.06) + 1, :] = False                                         # pasek FPS / nazwa serwera
    m[int(h * 0.24):int(h * 0.86) + 1, int(w * 0.32):int(w * 0.68) + 1] = False   # okna dialogowe (Character List, Enter Game)
    return m


def wzorzec():
    """Siatka wzorca (h, w, 3) albo None, gdy pliku nie ma (wtedy zrzut nic nie rozstrzyga: brak alarmu)."""
    global _wzorzec
    if _wzorzec is None:
        try:
            import numpy as np  # noqa: PLC0415
            d = json.loads(PLIK_WZORCA.read_text())
            _wzorzec = np.array(d["siatka"], dtype=float)
        except (OSError, ValueError, KeyError):
            _wzorzec = False
    return _wzorzec if _wzorzec is not False else None


def zgodnosc(obraz, wz=None):
    """Część komórek siatki zgodnych z wzorcem logowania (0..1); None bez wzorca."""
    wz = wzorzec() if wz is None else wz
    if wz is None:
        return None
    import numpy as np  # noqa: PLC0415
    d = np.abs(_siatka(obraz) - wz).sum(axis=2)
    return float((d[_maska()] < KOMORKA_L1).mean())


def ekran_logowania(obraz, wz=None):
    """True = ekran logowania (tapeta Retronic z oknem Character List / Enter Game), False = nie, None = brak wzorca."""
    z = zgodnosc(obraz, wz)
    return None if z is None else z >= ZGODNOSC_PROG


def zrzut_ekranu(gniazdo=None):
    """Zrzut sesji gry (grim ppm, jedna próba). Rzuca przy braku zrzutu (wołający łapie i traktuje jako None)."""
    import ekran  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    bajty = ekran.grim("ppm", timeout=ZRZUT_TIMEOUT_S, proby=1, gniazdo=gniazdo)
    return Image.open(io.BytesIO(bajty)).convert("RGB")


def zrzut_logowania():
    """Funkcja dla Detektor.krok: True/False/None. Nigdy nie rzuca."""
    try:
        return ekran_logowania(zrzut_ekranu())
    except Exception:                           # noqa: BLE001
        return None


# --- CLI -------------------------------------------------------------------------------------------------------

def _zbuduj(pliki):
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    siatki = [_siatka(Image.open(p)) for p in pliki]
    sr = np.mean(siatki, axis=0)
    PLIK_WZORCA.write_text(json.dumps({"opis": "wzorzec ekranu logowania Retronic (siatka 32x24, uśredniona); "
                                                "odtworzenie: python3 rozlaczenie.py zbuduj <png...>",
                                       "zrodla": len(pliki), "siatka": [[[int(round(v)) for v in kom] for kom in w] for w in sr]}))
    print(f"zapisano {PLIK_WZORCA} ({len(pliki)} zrzutów)")


def _ocen(pliki):
    from PIL import Image  # noqa: PLC0415
    for p in pliki:
        z = zgodnosc(Image.open(p))
        print(f"{p}\tzgodność {z if z is None else round(z, 3)}\t{'EKRAN LOGOWANIA' if z is not None and z >= ZGODNOSC_PROG else 'gra/inne'}")


if __name__ == "__main__":
    komenda, *args = sys.argv[1:] or ["?"]
    if komenda == "zbuduj" and args:
        _zbuduj(args)
    elif komenda == "ocen" and args:
        _ocen(args)
    else:
        print(__doc__)
