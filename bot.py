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


def _zapytaj_surowe(zadanie):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(str(GNIAZDO))
        s.sendall((json.dumps(zadanie) + "\n").encode())
        odpowiedz = json.loads(s.makefile("rb").readline())
    if not odpowiedz.pop("ok"):
        raise RuntimeError(odpowiedz["blad"])
    return odpowiedz


# --- widmo własnej postaci (13.10) ------------------------------------------------------------
# Po przelogowaniu (reset/save serwera, auto-reconnect) klient bywa zostawia w pamięci DRUGI wpis gracza o tej
# samej nazwie (stara sesja, inne id). Rdzeń ("pozycja" po nazwie, adres zapamiętany) potrafi trzymać się
# nieaktualnego wpisu: pozycja stoi w miejscu, kliki trafiają w złe pole ("Sorry, not possible."), pętla ataku.
# Tu wybieramy wpis własny: zgodny z HP z bloku statystyk gracza, a przy remisie najbliższy adresem blokowi
# statystyk (blok żywej sesji leży tuż przy żywym wpisie). Tożsamość odświeżana co WLASNY_ODSWIEZ s.
WLASNY_ODSWIEZ = 2.0
# 15.10: widmo trzymało i blok statystyk, więc zgodność HP/adresu wskazywała widmo przez 1 h 45 min. Dlatego
# pierwszeństwo ma ruch: wpis, który zmienił pozycję w ciągu WLASNY_RUCH s, jest żywy (widmo stoi w miejscu).
WLASNY_RUCH = 60.0
_wlasny = {"nazwa": None, "t": float("-inf"), "wpis": None, "duplikat": None}
_ruch = {}      # (id, adres) -> [ostatnia pozycja, czas ostatniej zmiany albo None = nie widziano ruchu]


def sledz_ruch(ruch, kandydaci, teraz):
    """Aktualizuje ruch wpisów (pozycja, czas ostatniej zmiany); wpisy spoza listy znikają ze słownika."""
    for k in kandydaci:
        klucz, poz = (k["id"], k["adres"]), (k.get("x"), k.get("y"), k.get("z"))
        zapis = ruch.get(klucz)
        if zapis is None:
            ruch[klucz] = [poz, None]
        elif zapis[0] != poz:
            ruch[klucz] = [poz, teraz]
    for klucz in [c for c in ruch if c not in {(k["id"], k["adres"]) for k in kandydaci}]:
        del ruch[klucz]


def _po_ruchu(kandydaci, ruch, teraz):
    """Wpis o najświeższym ruchu (w oknie WLASNY_RUCH) albo None, gdy żaden się nie rusza."""
    if not ruch or teraz is None:
        return None
    ruszone = [(ruch[(k["id"], k["adres"])][1], k) for k in kandydaci
               if (k["id"], k["adres"]) in ruch and ruch[(k["id"], k["adres"])][1] is not None
               and teraz - ruch[(k["id"], k["adres"])][1] <= WLASNY_RUCH]
    if not ruszone:
        # nikt nie ruszył się w oknie (postój): jeśli od pojawienia się duplikatu ruszał się tylko jeden wpis,
        # to on jest żywy (widmo nie rusza się nigdy) - bez powrotu do zgadywania po bloku (ping-pong)
        kiedys = [k for k in kandydaci if (k["id"], k["adres"]) in ruch and ruch[(k["id"], k["adres"])][1] is not None]
        return kiedys[0] if len(kiedys) == 1 else None
    ruszone.sort(key=lambda p: p[0], reverse=True)
    return ruszone[0][1]


def _id_liczba(k):
    try:
        return int(k.get("id"))
    except (TypeError, ValueError):
        return None


def _wybierz_wlasny(kandydaci, gracz, ruch=None, teraz=None):
    """(wpis, powód) albo (None, None). Kolejność dowodów:
    1. ruch wpisu (widmo nie rusza się nigdy),
    2. HP zgodne z blokiem statystyk (zawęża pulę),
    3. NAJWYŻSZE id (19.10, logi 14:57 i 20:14: trzy kolejne sesje Mastafiana miały id 268479676 < 268555116 < 268653019 i za
       każdym razem ruch wskazał żywym wpis o wyższym id, a "hp/adres bloku" - starszy, bo blok statystyk też bywa widmem; id
       gracza rośnie przy każdym logowaniu, więc widmo po relogu ma zwykle niższe id niż żywa sesja).
       UWAGA: to HEURYSTYKA z jednego dnia (19.10, 3 sesje Mastafiana), mechanizmu nie sprawdzono w kodzie serwera. Kontrprzykład
       z 13.10 (Jointoramix: żywy 268478551, widmo 268852462) pokazuje, że po restarcie serwera licznik id może się odwrócić.
       Dlatego RUCH ZAWSZE wygrywa pierwszy, a wybór po id loguje się z ostrzeżeniem, gdy wpisy są na różnych piętrach.
       Zgodności z pozycją z `gracz`/`pozycja` jako tie-breaku NIE ma: `gracz` nie zawiera pozycji, a `pozycja` czyta ten sam
       wpis, który tu wybieramy (koło); ciągłość z ostatnią pozycją wskazałaby w relogu wpis STARY,
    4. najbliższy adres bloku statystyk (tylko gdy brak id)."""
    if len(kandydaci) < 2:
        return None, None
    zywy = _po_ruchu(kandydaci, ruch, teraz)
    if zywy is not None:
        return zywy, "ruch"
    pula, powod = kandydaci, "hp/adres bloku"
    try:
        proc = 100.0 * gracz["hp"] / gracz["max_hp"]
        zgodne = [k for k in kandydaci if abs(k.get("hp", 100) - proc) <= 1.5]
        pula = zgodne or kandydaci
    except (KeyError, TypeError, ZeroDivisionError):
        pass
    if len(pula) == 1:
        return pula[0], "hp"
    ident = [_id_liczba(k) for k in pula]
    if all(i is not None for i in ident) and len(set(ident)) == len(ident):
        return pula[ident.index(max(ident))], "najwyzsze id"
    try:
        baza = int(gracz["adres"], 16)
        return min(pula, key=lambda k: abs(int(k["adres"], 16) - baza)), powod
    except (KeyError, TypeError, ValueError):
        return None, None


def wybierz_wlasny(kandydaci, gracz, ruch=None, teraz=None):
    """Z wpisów gracza o naszej nazwie wybiera żywy (dict z 'adres', 'id') albo None, gdy nie da się rozstrzygnąć
    (reguły: patrz _wybierz_wlasny)."""
    return _wybierz_wlasny(kandydaci, gracz, ruch, teraz)[0]


def wlasny_wpis(nazwa):
    """Wpis własnej postaci przy duplikacie nazwy (widmo po przelogowaniu), inaczej None."""
    teraz = time.monotonic()
    w = _wlasny
    if w["nazwa"] == nazwa and teraz - w["t"] < WLASNY_ODSWIEZ:
        return w["wpis"]
    wpis, powod, kand = None, None, []
    try:
        lista = _zapytaj_surowe({"cmd": "stwory"})["stwory"]
        kand = [s for s in lista if s.get("gracz") and s.get("nazwa") == nazwa]
        if len(kand) > 1:
            sledz_ruch(_ruch, kand, teraz)
            wpis, powod = _wybierz_wlasny(kand, _zapytaj_surowe({"cmd": "gracz"})["gracz"], _ruch, teraz)
        else:
            _ruch.clear()
    except Exception:
        wpis = None
    w.update(nazwa=nazwa, t=teraz, wpis=wpis)
    klucz = (wpis["id"], wpis["adres"]) if wpis else None
    if klucz != w["duplikat"]:
        w["duplikat"] = klucz
        if wpis:
            print(f"[bot] widmo gracza {nazwa}: używam wpisu id{wpis['id']} {wpis['adres']} "
                  f"({wpis['x']},{wpis['y']},{wpis['z']}; wybór: {powod})", file=sys.stderr, flush=True)
            inne = [k for k in kand if k is not wpis]
            if powod != "ruch" and any(k.get("z") != wpis.get("z") for k in inne):
                # ostrzeżenie: wpisy na RÓŻNYCH piętrach i wybór bez dowodu ruchu - serwis/trasa mogą planować z fałszywego piętra
                print(f"[bot] UWAGA widmo gracza {nazwa}: wpisy na różnych piętrach "
                      f"({', '.join(f'id{k['id']} z{k.get('z')}' for k in kand)}); wybrano id{wpis['id']} (z{wpis.get('z')}) "
                      f"bez dowodu ruchu, sprawdź pozycję", file=sys.stderr, flush=True)
    return wpis


def _pozycja_wlasna(nazwa):
    """Świeża pozycja wpisu własnego przy duplikacie nazwy albo None (wtedy odpowiada rdzeń)."""
    wpis = wlasny_wpis(nazwa)
    if not wpis:
        return None
    try:
        s = _zapytaj_surowe({"cmd": "stwor", "adres": wpis["adres"], "id": wpis["id"]})["stwor"]
    except Exception:
        s = None
    if not s:
        _wlasny["t"] = float("-inf")      # wpis zniknął: następne zapytanie rozstrzyga od nowa
        return None
    return {"x": s["x"], "y": s["y"], "z": s["z"]}


def zapytaj(zadanie):
    odp = _zapytaj_surowe(zadanie)
    cmd = zadanie.get("cmd")
    if cmd in ("pozycja", "poscig") and zadanie.get("nazwa"):
        p = _pozycja_wlasna(zadanie["nazwa"])
        if p is not None:
            odp["pozycja"] = p
    return odp


def nazwa_postaci():
    if os.environ.get("RETRONIC_POSTAC"):      # jawny nick (wiele klientów: log klienta bywa wspólny)
        return os.environ["RETRONIC_POSTAC"]
    nazwy = re.findall(r"Connecting to character (.+?) on ", LOG_KLIENTA.read_text(errors="replace"))
    if not nazwy:
        sys.exit("Nie wiem, kim grasz (brak logowania w Retronic.log).")
    return nazwy[-1]


_PROCES_GRY = re.compile(rb"retronic(gl|dx)-\d+\.exe$")


def _gniazdo_sesji():
    """Gniazdo Wayland sesji tej instancji (plik sesji/wayland); None, gdy go nie ma."""
    try:
        return (instancja.sesja() / "wayland").read_text().strip() or None
    except OSError:
        return None


def ekran_z_procesu(cmdline, srodowisko, id_instancji, gniazdo=None):
    """DISPLAY gry tej instancji z jednego procesu albo None, gdy to nie jest jej gra.
    Gra = proces, którego plik wykonywalny (argv[0]) to RetronicGL-<n>.exe (18.10: dawniej wystarczał ten tekst
    gdziekolwiek w wierszu poleceń, więc łapała się powłoka z `grep RetronicGL-` i bot dostawał DISPLAY pulpitu).
    Gra innej instancji (RETRONIC_ID) i gra w innej sesji Wayland (WAYLAND_DISPLAY != gniazdo sesji) odpadają:
    każdy bot widzi i steruje tylko swoim oknem."""
    if not _PROCES_GRY.search(cmdline.split(b"\0")[0].lower()):
        return None
    if instancja.id_z_environ(srodowisko) != id_instancji:
        return None
    if gniazdo:
        wl = next((z[16:].decode() for z in srodowisko if z.startswith(b"WAYLAND_DISPLAY=")), None)
        if wl != gniazdo:
            return None
    for zmienna in srodowisko:
        if zmienna.startswith(b"DISPLAY="):
            return zmienna[8:].decode()
    return None


def ekran_gry():
    """DISPLAY procesu gry, czyli ekran XWayland zagnieżdżonej sesji tej instancji."""
    gniazdo = _gniazdo_sesji()
    for wpis in os.listdir("/proc"):
        if not wpis.isdigit():
            continue
        try:
            cmd = Path(f"/proc/{wpis}/cmdline").read_bytes()
            if b"etronic" not in cmd:
                continue
            srodowisko = Path(f"/proc/{wpis}/environ").read_bytes().split(b"\0")
        except OSError:
            continue
        ekran = ekran_z_procesu(cmd, srodowisko, instancja.ID, gniazdo)
        if ekran:
            return ekran
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
