#!/usr/bin/env python3
"""Nagrywanie trasy z ręcznego chodzenia (tylko odczyt pozycji, zero inputu do gry).

  python3 -I nagraj_trase.py <nazwa> [--krok 4] [--nadpisz] [--bezczynnosc 10]

Czyta wyłącznie pozycję gracza z gniazda $XDG_RUNTIME_DIR/retronic-pomocnik.sock (komenda
`pozycja`) 4x/s. Zapisuje punkt, gdy odejdziesz o >= krok pól od ostatniego punktu albo
zmienisz piętro; na zakrętach dogęszcza (zapisuje narożnik), tak by trasę dało się przejść
kliknięciami po punktach. Zmiana piętra i teleport (skok > 2 pól w < 1 s) trafiają jako
punkty specjalne do trasy/<nazwa>.meta (schody/dziura/teleport).

Koniec: plik STOP_NAGRYWANIA w katalogu pomocnika, Ctrl+C / SIGTERM albo brak ruchu przez
--bezczynnosc minut. Zapis przyrostowy do trasy/<nazwa>.json (+ kopia .json.partial co 30 s).
"""
import argparse
import json
import math
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import instancja  # noqa: E402
import trasa_io  # noqa: E402

KATALOG = trasa_io.KATALOG
STOP_PLIK = instancja.S.stop_nagrywania
GNIAZDO = instancja.gniazdo()
LOG_KLIENTA = instancja.S.log_klienta

OKRES = 0.25            # s między próbkami (4/s)
KROK_DOMYSLNY = 4       # pól między punktami na prostej
ZAKRET = 0.6            # odchylenie od prostej (pola), po którym zapisujemy narożnik
SKOK_POL = 2            # skok większy niż tyle pól w < SKOK_CZAS = teleport
SKOK_CZAS = 1.0
KOPIA_CO = 30.0
BEZCZYNNOSC_MIN = 10.0


def _odl_od_prostej(p, a, b):
    """Odległość punktu p od odcinka a-b (w polach, euklidesowo)."""
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    d2 = dx * dx + dy * dy
    if d2 == 0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / d2))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


class Rejestrator:
    """Czysta logika: karmiona próbkami (t, (x, y, z)), zwraca nic; wynik w .punkty / .specjalne."""

    def __init__(self, krok=KROK_DOMYSLNY):
        self.krok = max(2, int(krok))
        self.punkty = []        # [(x, y, z)]
        self.specjalne = []     # [{"idx", "typ", "komentarz"}]
        self.bufor = []         # pozycje od ostatniego punktu (bez powtórzeń)
        self.ostatnia = None    # (t, poz) ostatniej próbki
        self.zmiana = False     # czy ostatnia próbka coś dodała

    def _dodaj(self, poz, typ=None, komentarz=""):
        if self.punkty and self.punkty[-1] == poz:
            if typ and not any(s["idx"] == len(self.punkty) - 1 for s in self.specjalne):
                self.specjalne.append({"idx": len(self.punkty) - 1, "typ": typ, "komentarz": komentarz})
            return
        self.punkty.append(poz)
        if typ:
            self.specjalne.append({"idx": len(self.punkty) - 1, "typ": typ, "komentarz": komentarz})
        self.bufor = []
        self.zmiana = True

    def probka(self, t, poz):
        poz = tuple(poz)
        self.zmiana = False
        if self.ostatnia is None:
            self.ostatnia = (t, poz)
            self._dodaj(poz, "start", "początek nagrania")
            return
        t0, p0 = self.ostatnia
        self.ostatnia = (t, poz)
        if poz == p0:
            return
        dx, dy, dz = poz[0] - p0[0], poz[1] - p0[1], poz[2] - p0[2]
        odl = max(abs(dx), abs(dy))
        if dz:
            # ostatnie pole przed zmianą piętra to wejście na schody/dziurę/drabinę
            self._dodaj(p0, "przed_zmiana_pietra", f"ostatnie pole na piętrze {p0[2]}, potem piętro {poz[2]}")
            kier = "w górę" if dz < 0 else "w dół"
            typ = "schody_w_gore" if dz < 0 else "schody_w_dol"
            self._dodaj(poz, typ, f"zmiana piętra {p0[2]} -> {poz[2]} ({kier}), z ({p0[0]},{p0[1]})")
            return
        if odl > SKOK_POL and t - t0 < SKOK_CZAS:
            self._dodaj(p0, "przed_teleportem", f"ostatnie pole przed skokiem o {odl} pól")
            self._dodaj(poz, "teleport", f"skok o {odl} pól w {t - t0:.1f} s z ({p0[0]},{p0[1]})")
            return
        ost = self.punkty[-1]
        self.bufor.append(poz)
        if max(abs(poz[0] - ost[0]), abs(poz[1] - ost[1])) >= self.krok:
            self._dodaj(poz)
            return
        # zakręt: któraś z pozycji od ostatniego punktu odbiega od prostej ost -> poz; narożnik to
        # pozycja najdalsza od tej prostej (jak w Douglasie-Peuckerze)
        if len(self.bufor) >= 2:
            odch = [_odl_od_prostej(b, ost, poz) for b in self.bufor[:-1]]
            if max(odch) > ZAKRET:
                k = odch.index(max(odch))
                reszta = self.bufor[k + 1:]
                self._dodaj(self.bufor[k])
                self.bufor = reszta

    def zakoncz(self):
        """Dopisuje ostatnią pozycję jako punkt końcowy."""
        if self.ostatnia is not None:
            self._dodaj(self.ostatnia[1])


def nazwa_postaci(plik=LOG_KLIENTA):
    nazwy = re.findall(r"Connecting to character (.+?) on ", Path(plik).read_text(errors="replace"))
    return nazwy[-1] if nazwy else None


def pozycja(nazwa, gniazdo=GNIAZDO):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(2.0)
        s.connect(str(gniazdo))
        s.sendall((json.dumps({"cmd": "pozycja", "nazwa": nazwa}) + "\n").encode())
        o = json.loads(s.makefile("rb").readline())
    if not o.get("ok"):
        raise RuntimeError(o.get("blad", "błąd odczytu pozycji"))
    p = o["pozycja"]
    if gniazdo == GNIAZDO:
        # widmo gracza po przelogowaniu (dwa wpisy o tej samej nazwie): rdzeń potrafi oddać stojący wpis,
        # bot.zapytaj wybiera żywy (18.10: nagranie miało 1 punkt, bo stało na widmie)
        import bot  # noqa: E402
        p = bot._pozycja_wlasna(nazwa) or p
    return p["x"], p["y"], p["z"]


def powiadom(tytul, tresc):
    try:
        subprocess.run(["notify-send", "-a", "Retronic", tytul, tresc], timeout=3, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        pass


def nagrywaj(nazwa, krok=KROK_DOMYSLNY, nadpisz=False, bezczynnosc_min=BEZCZYNNOSC_MIN,
             czytaj=None, zegar=time.monotonic, spij=time.sleep, stop_plik=STOP_PLIK,
             katalog=None, wypisz=print, powiadomienie=powiadom):
    """Pętla nagrywania. `czytaj()` zwraca (x,y,z) (w testach atrapa). Zwraca Rejestrator."""
    plik = trasa_io.sciezka(nazwa, katalog)
    if plik.exists() and not nadpisz:
        raise FileExistsError(f"{plik} już istnieje (użyj --nadpisz)")
    plik.parent.mkdir(exist_ok=True)
    partial = plik.with_name(plik.name + ".partial")
    if czytaj is None:
        postac = nazwa_postaci()
        if not postac:
            raise RuntimeError("nie wiem, kim grasz (brak logowania w Retronic.log)")
        czytaj = lambda: pozycja(postac)  # noqa: E731
    try:
        Path(stop_plik).unlink()
    except FileNotFoundError:
        pass
    stop = {"sygnal": False}

    def _sig(*_):
        stop["sygnal"] = True
    stare = {}
    if "RETRONIC_TESTY" not in os.environ:
        for s in (signal.SIGINT, signal.SIGTERM):
            stare[s] = signal.signal(s, _sig)

    rej = Rejestrator(krok)
    ostatni_ruch = zegar()
    ostatnia_kopia = zegar()
    zapisane = 0
    bledy = 0
    powod = "koniec"
    wypisz(f"Nagrywam trasę '{nazwa}' (krok {rej.krok}). Koniec: touch {stop_plik.name} / Ctrl+C / "
           f"{bezczynnosc_min:g} min bez ruchu.")
    try:
        while True:
            if stop["sygnal"]:
                powod = "sygnał (Ctrl+C / zatrzymaj)"
                break
            if Path(stop_plik).exists():
                powod = f"plik {Path(stop_plik).name}"
                break
            t = zegar()
            try:
                poz = czytaj()
                bledy = 0
            except Exception as e:  # chwilowo brak gry/odczytu: czekamy dalej, to zwykłe wylogowanie
                bledy += 1
                if bledy in (1, 40):
                    wypisz(f"Błąd odczytu pozycji: {e!r} (próbuję dalej)")
                poz = None
            if poz is not None:
                przed = rej.ostatnia[1] if rej.ostatnia else None
                rej.probka(t, poz)
                if przed != tuple(poz):
                    ostatni_ruch = t
                if rej.zmiana:
                    trasa_io.zapisz(nazwa, rej.punkty, rej.specjalne, katalog)
                    nowe = len(rej.punkty) - zapisane
                    zapisane = len(rej.punkty)
                    wypisz(f"punkt {zapisane}: {rej.punkty[-1]}" +
                           (f"  [{rej.specjalne[-1]['typ']}]" if rej.specjalne and
                            rej.specjalne[-1]["idx"] == zapisane - 1 else "") +
                           (f"  (+{nowe})" if nowe > 1 else ""))
            if t - ostatnia_kopia >= KOPIA_CO and plik.exists():
                shutil.copyfile(plik, partial)
                ostatnia_kopia = t
            if t - ostatni_ruch > bezczynnosc_min * 60:
                powod = f"bezczynność > {bezczynnosc_min:g} min"
                break
            spij(OKRES)
    finally:
        for s, h in stare.items():
            signal.signal(s, h)
        rej.zakoncz()
        if rej.punkty:
            trasa_io.zapisz(nazwa, rej.punkty, rej.specjalne, katalog)
        try:
            Path(stop_plik).unlink()
        except FileNotFoundError:
            pass
        try:
            partial.unlink()
        except FileNotFoundError:
            pass
    opis = trasa_io.podsumowanie(rej.punkty)
    wypisz(f"Zapisano {plik} ({powod}): {opis}")
    for s in rej.specjalne:
        if s["typ"] not in ("start",):
            wypisz(f"  #{s['idx']} {rej.punkty[s['idx']]} {s['typ']}: {s['komentarz']}")
    powiadomienie("Trasa zapisana", f"{nazwa}: {opis}")
    return rej


def main(argv=None):
    p = argparse.ArgumentParser(description="Nagrywanie trasy z ręcznego chodzenia (tylko odczyt pozycji)")
    p.add_argument("nazwa", help="nazwa trasy (trasy/<nazwa>.json)")
    p.add_argument("--krok", type=int, default=KROK_DOMYSLNY, help=f"pól między punktami (3-5, domyślnie {KROK_DOMYSLNY})")
    p.add_argument("--nadpisz", action="store_true", help="pozwól nadpisać istniejącą trasę")
    p.add_argument("--bezczynnosc", type=float, default=BEZCZYNNOSC_MIN, help="minut bez ruchu do końca (10)")
    a = p.parse_args(argv)
    if not GNIAZDO.exists():
        sys.exit(f"Brak gniazda {GNIAZDO}: gra/strażnik nie działa.")
    try:
        nagrywaj(a.nazwa, a.krok, a.nadpisz, a.bezczynnosc)
    except (FileExistsError, ValueError, RuntimeError) as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
