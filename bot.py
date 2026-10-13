#!/usr/bin/env python3
"""Chodzenie i trasy dla Retronic. Pozycję czyta ze strażnika (odczyt pamięci),
klawisze wysyła przez XTEST do ekranu XWayland sesji gry z sesja.sh
(wtype nie dociera do okien XWayland, a Wine działa właśnie przez XWayland).

  bot.py pozycja                    bieżąca pozycja postaci
  bot.py idz <x> <y> [z]            dojdź na pole (strzałkami, z obchodzeniem przeszkód)
  bot.py krok <Up|Down|Left|Right>  jeden krok z potwierdzeniem
  bot.py nagraj <nazwa> [sekundy]   zapisuj pozycje, kiedy chodzisz (trasy/<nazwa>.json)
  bot.py trasa <nazwa> [okrazenia]  przejdź nagraną trasę (od najbliższego punktu)

Zatrzymanie w dowolnym momencie: plik STOP w katalogu pomocnika (touch STOP).
"""

import json
import os
import random
import re
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.dont_write_bytecode = True
import instancja  # noqa: E402
import klawisz_x11  # noqa: E402

KATALOG = Path(__file__).resolve().parent
TRASY = KATALOG / "trasy"
STOP = instancja.S.stop            # bez RETRONIC_ID: pomocnik/STOP
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
GNIAZDO = instancja.gniazdo()      # bez RETRONIC_ID: retronic-pomocnik.sock
LOG_KLIENTA = instancja.S.log_klienta

KIERUNKI = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}
CZAS_KROKU = 1.5  # ile czekać na zmianę pozycji po wciśnięciu strzałki


class Zatrzymano(Exception):
    pass


def zapytaj(zadanie):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(str(GNIAZDO))
        s.sendall((json.dumps(zadanie) + "\n").encode())
        odpowiedz = json.loads(s.makefile("rb").readline())
    if not odpowiedz.pop("ok"):
        raise RuntimeError(odpowiedz["blad"])
    return odpowiedz


def nazwa_postaci():
    if os.environ.get("RETRONIC_POSTAC"):      # jawny nick (wiele klientów: log klienta bywa wspólny)
        return os.environ["RETRONIC_POSTAC"]
    nazwy = re.findall(r"Connecting to character (.+?) on ", LOG_KLIENTA.read_text(errors="replace"))
    if not nazwy:
        sys.exit("Nie wiem, kim grasz (brak logowania w Retronic.log).")
    return nazwy[-1]


def ekran_gry():
    """DISPLAY procesu gry, czyli ekran XWayland zagnieżdżonej sesji."""
    for wpis in os.listdir("/proc"):
        if not wpis.isdigit():
            continue
        try:
            cmd = Path(f"/proc/{wpis}/cmdline").read_bytes().lower()
            if b"retronicgl-" not in cmd and b"retronicdx-" not in cmd:
                continue
            srodowisko = Path(f"/proc/{wpis}/environ").read_bytes().split(b"\0")
            if instancja.id_z_environ(srodowisko) != instancja.ID:     # gra innej instancji
                continue
            for zmienna in srodowisko:
                if zmienna.startswith(b"DISPLAY="):
                    return zmienna[8:].decode()
        except OSError:
            continue
    raise RuntimeError("gra nie działa")


def sprawdz_stop():
    if STOP.exists() and not os.environ.get("RETRONIC_TESTY"):   # testy nie zależą od pliku STOP
        raise Zatrzymano("plik STOP")


class Postac:
    def __init__(self):
        self.nazwa = nazwa_postaci()
        self.ekran = None

    def pozycja(self):
        p = zapytaj({"cmd": "pozycja", "nazwa": self.nazwa})["pozycja"]
        return p["x"], p["y"], p["z"]

    def klawisz(self, nazwa):
        sprawdz_stop()
        self.ekran = self.ekran or ekran_gry()
        klawisz_x11.wyslij(nazwa, ekran=self.ekran)

    # --- klawisze TRZYMANE (ciągłe chodzenie w pościgu); stan i zabezpieczenia w klawisz_x11 ---
    def _ekran_gry(self):
        self.ekran = self.ekran or ekran_gry()
        return self.ekran

    def trzymaj_kierunek(self, dx, dy):
        """Trzymaj klawisz kierunku (dx, dy): oś strzałką, skos numpadem. Zmiana kierunku bez luki."""
        sprawdz_stop()
        return klawisz_x11.trzymaj_kierunek(dx, dy, ekran=self._ekran_gry())

    def trzymany_kierunek(self):
        return klawisz_x11.trzymany_kierunek(self.ekran)

    def puszczaj(self):
        """Puść wszystkie trzymane klawisze (bez sprawdzania STOP: ma działać także przy zatrzymaniu)."""
        klawisz_x11.puszczaj(ekran=self.ekran)

    def puls(self):
        klawisz_x11.puls()

    def puszcz_wszystko(self):
        """Start bota / wyjście: puszcza trzymane i wysyła KeyRelease dla strzałek i numpadu."""
        return klawisz_x11.puszczaj_wszystkie_strzalki(self._ekran_gry())

    def krok(self, kierunek):
        """Jeden krok. Zwraca nową pozycję albo None, gdy postać się nie ruszyła."""
        start = self.pozycja()
        self.klawisz(kierunek)
        koniec = time.monotonic() + CZAS_KROKU
        while time.monotonic() < koniec:
            time.sleep(0.05)
            teraz = self.pozycja()
            if teraz != start:
                time.sleep(random.uniform(0.02, 0.12))
                return teraz
        return None

    def skos(self, dx, dy):
        """Jedno stuknięcie skosu numpadem w stronę (dx, dy) (znaki +-1), bez czekania na ruch."""
        sprawdz_stop()
        klawisz_x11.skos((dx, dy), ekran=self._ekran_gry())

    def krok_skos(self, dx, dy):
        """Jeden krok po skosie (numpad). Zwraca nową pozycję albo None, gdy postać się nie ruszyła."""
        start = self.pozycja()
        self.skos(dx, dy)
        koniec = time.monotonic() + CZAS_KROKU
        while time.monotonic() < koniec:
            time.sleep(0.05)
            teraz = self.pozycja()
            if teraz != start:
                time.sleep(random.uniform(0.02, 0.12))
                return teraz
        return None

    def idz(self, cel, limit_prob=12):
        """Dochodzi na pole `cel` (x, y[, z]). Zwraca True po dojściu."""
        nieudane = 0
        zablokowane = set()
        while True:
            sprawdz_stop()
            x, y, z = self.pozycja()
            cx, cy = cel[0], cel[1]
            if (x, y) == (cx, cy) and (len(cel) < 3 or z == cel[2]):
                return True
            if len(cel) > 2 and z != cel[2] and abs(cx - x) + abs(cy - y) == 0:
                return True  # schody już przeniosły nas piętro wyżej/niżej
            dx, dy = cx - x, cy - y
            ruchy = []
            if dx:
                ruchy.append("Right" if dx > 0 else "Left")
            if dy:
                ruchy.append("Down" if dy > 0 else "Up")
            if abs(dy) > abs(dx):
                ruchy.reverse()
            # obejście: kierunki prostopadłe, gdy główne są zablokowane
            for k in list(ruchy):
                ruchy += [p for p in (("Up", "Down") if k in ("Left", "Right") else ("Left", "Right"))
                          if p not in ruchy]
            for kierunek in ruchy:
                if ((x, y, z), kierunek) in zablokowane:
                    continue
                if self.krok(kierunek):
                    break
                zablokowane.add(((x, y, z), kierunek))
            else:
                nieudane += 1
                zablokowane.clear()
                if nieudane >= limit_prob:
                    return False
                time.sleep(random.uniform(0.3, 0.8))


def nagraj(postac, nazwa, sekundy):
    TRASY.mkdir(exist_ok=True)
    plik = TRASY / f"{nazwa}.json"
    punkty = []
    koniec = time.monotonic() + sekundy
    print(f"Nagrywam trasę '{nazwa}' przez {sekundy:.0f} s. Chodź normalnie. (touch STOP kończy)", flush=True)
    try:
        while time.monotonic() < koniec:
            sprawdz_stop()
            p = postac.pozycja()
            if not punkty or punkty[-1] != list(p):
                punkty.append(list(p))
                plik.write_text(json.dumps(punkty))
                print(len(punkty), p, flush=True)
            time.sleep(0.1)
    except Zatrzymano:
        pass
    print(f"Zapisano {len(punkty)} punktów w {plik}")


def trasa(postac, nazwa, okrazenia):
    punkty = [tuple(p) for p in json.loads((TRASY / f"{nazwa}.json").read_text())]
    for okrazenie in range(okrazenia):
        x, y, z = postac.pozycja()
        # zacznij od najbliższego punktu na tym samym piętrze
        start = min(range(len(punkty)),
                    key=lambda i: (punkty[i][2] != z, abs(punkty[i][0] - x) + abs(punkty[i][1] - y)))
        for i in range(start, len(punkty)):
            if not postac.idz(punkty[i]):
                print(f"Nie mogę dojść do punktu {i} {punkty[i]}, przerywam.")
                return False
        print(f"Okrążenie {okrazenie + 1}/{okrazenia} gotowe", flush=True)
    return True


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd, args = argv[0], argv[1:]
    postac = Postac()
    try:
        if cmd == "pozycja":
            print(postac.pozycja())
        elif cmd == "krok":
            print(postac.krok(args[0]))
        elif cmd == "idz":
            print("dotarłem" if postac.idz(tuple(int(a) for a in args)) else "nie dało się dojść")
        elif cmd == "nagraj":
            nagraj(postac, args[0], float(args[1]) if len(args) > 1 else 300)
        elif cmd == "trasa":
            trasa(postac, args[0], int(args[1]) if len(args) > 1 else 1)
        else:
            sys.exit(__doc__)
    except Zatrzymano:
        print("Zatrzymano (plik STOP).")


if __name__ == "__main__":
    main(sys.argv[1:])
