#!/usr/bin/env python3
"""Dopasowuje rozmiar ekranu sesji gry (wayvnc w headless sway) do okna podglądu vncviewer na pulpicie (SPEC 15.10).

Start z podglad.sh w tle, kończy się razem z podglądem:
  dopasuj_okno.py [--port PORT] --pid PID_VNCVIEWERA

Co ~1 s czyta rozmiar okna vncviewera (hyprctl clients -j: pid, a w zapasie klasa Vncviewer + port w tytule).
Gdy rozmiar (min. 800x600, wymiary parzyste) różni się od wyjścia sesji o >= 8 px i stoi >= 1 s (debounce), wysyła do wayvnc
sesji RFB SetDesktopSize (typ 251). Połączenie RFB jest krótkie (współdzielone, shared=1: nie rozłącza podglądu użytkownika),
osobne na odczyt rozmiaru i na każdą zmianę. Bot po zmianie rozmiaru sam wykrywa mapę od nowa (ekran.py).

RETRONIC_DOPASUJ_OKNO=0 wyłącza (stare zachowanie: wyjście sesji ma stały rozmiar z sesja.sh).
"""
import argparse
import json
import os
import socket
import struct
import subprocess
import sys
import time

sys.dont_write_bytecode = True

MIN_SZER, MIN_WYS = 800, 600       # decyzja Karola 15.10: nie schodzimy poniżej (klient potrzebuje >= 800 px szerokości)
MAKS_WYMIAR = 4096                 # bezpiecznik na głupie odczyty
PROG_PX = 8                        # różnica okna i wyjścia, od której dopasowujemy
DEBOUNCE_S = 1.0                   # tyle rozmiar okna musi stać bez zmian
CO_S = 1.0                         # okres odczytu okna
ODSWIEZ_S = 15.0                   # co tyle odczytujemy rozmiar wyjścia ponownie (ktoś inny mógł go zmienić)
TIMEOUT_RFB_S = 3.0
ENC_EXTENDED_DESKTOP_SIZE = -308


def wlaczone(env=None):
    """RETRONIC_DOPASUJ_OKNO: domyślnie włączone, '0' wyłącza."""
    return (env if env is not None else os.environ).get("RETRONIC_DOPASUJ_OKNO", "1").strip() != "0"


def ogranicz(szer, wys):
    """Rozmiar docelowy wyjścia: min. 800x600, max. MAKS_WYMIAR, wymiary parzyste (zaokrąglone w dół)."""
    szer = min(max(int(szer), MIN_SZER), MAKS_WYMIAR)
    wys = min(max(int(wys), MIN_WYS), MAKS_WYMIAR)
    return szer - szer % 2, wys - wys % 2


MAKS_SZER_GRY = 1175               # sprawdzone zrzutem 15.10: 1175x910 daje pełny widok, 1468x1136 już nie
PROPORCJE_GRY = 1175 / 910         # proporcje ekranu, przy których klient pokazuje mapę 15x11 i prawy panel w całości


def wpisz_proporcje(rozm, proporcje=PROPORCJE_GRY, maks_szer=MAKS_SZER_GRY):
    """Największy prostokąt o proporcjach gry mieszczący się w oknie (rozm), nie mniejszy niż 800x600 po ogranicz().

    Okno w kafelku bywa wąskie i wysokie (np. 1468x1820): ekran sesji w takim kształcie powiększa mapę i chowa panele
    klienta (15.10), więc zamiast wypełniać okno, wpisujemy w nie ekran o dobrych proporcjach (reszta okna jest szara)."""
    if rozm is None:
        return None
    szer, wys = rozm
    if szer / wys < proporcje:
        wys = int(szer / proporcje)
    else:
        szer = int(wys * proporcje)
    if maks_szer and szer > maks_szer:                        # większy ekran: klient chowa panele i zoomuje mapę (15.10)
        szer, wys = maks_szer, int(maks_szer / proporcje)
    return szer, wys


def rozmiar_docelowy(rozm, bot):
    """Docelowy ekran sesji dla okna podglądu `rozm`. Bez bota = rozmiar okna (wypełnia podgląd, bez pasów; SKALUJ ustawia
    skalę). Z botem None = nie ruszamy ekranu sesji: klient przy zmianie kształtu okna chowa panele i przestawia układ,
    a bot (plecak, HP/mana, kliki) traci wtedy odczyt (19.10: Mastafian stanął po zmianie okna podglądu)."""
    return None if bot else rozm


def skaluj_wlaczone(env=None):
    """RETRONIC_SKALUJ (domyślnie włączone, "0" wyłącza): tryb do grania ręcznego, wyłączany sam, gdy chodzi bot. Ekran sesji ma piksele okna, a sway skaluje go tak, by klient dalej
    widział logiczne 1175x910 (układ jak zawsze, obraz powiększony). Bot (ekran.py szuka mapy w pikselach) wymaga skali 1."""
    return (env if env is not None else os.environ).get("RETRONIC_SKALUJ", "1").strip() != "0"


def _id_instancji_procesu(proc, w):
    """RETRONIC_ID z /proc/<pid>/environ ("" = główna instancja); None, gdy środowiska nie da się odczytać."""
    try:
        with open(f"{proc}/{w}/environ", "rb") as f:
            for wpis in f.read().split(b"\0"):
                if wpis.startswith(b"RETRONIC_ID="):
                    return wpis[len(b"RETRONIC_ID="):].decode("utf-8", "replace")
    except OSError:
        return None
    return ""


def bot_dziala(proc="/proc", instancja=None):
    """True, gdy chodzi bot TEJ instancji (mozg.py albo cavebot.py w argv procesu python z tym samym RETRONIC_ID co
    wołający; `instancja` wymusza id, "" = główna). Wtedy sesja musi mieć piksele wzorcowe 1175x910 w skali 1 (ekran.py
    szuka mapy w pikselach), więc SKALUJ ustępuje. 19.10: dawniej bot DOWOLNEJ instancji (bot `test` blokował serwis
    Mastafiana i zatrzymywał helper); gdy środowiska procesu nie da się odczytać, liczymy go jak dawniej (ostrożnie)."""
    moje = os.environ.get("RETRONIC_ID", "") if instancja is None else instancja
    try:
        wpisy = os.listdir(proc)
    except OSError:
        return False
    for w in wpisy:
        if not w.isdigit() or int(w) == os.getpid():
            continue
        try:
            with open(f"{proc}/{w}/cmdline", "rb") as f:
                argv = f.read().split(b"\0")
        except OSError:
            continue
        if argv and os.path.basename(argv[0]).startswith(b"python") and any(
                os.path.basename(a) in (b"mozg.py", b"cavebot.py", b"serwis.py") for a in argv[1:]):
            cudza = _id_instancji_procesu(proc, w)
            if cudza is not None and cudza != moje:
                continue
            return True
    return False


def skala_stala(env=None):
    """Stała skala trybu SKALUJ (RETRONIC_SKALA, domyślnie 1.5): elementy mają tę samą wielkość w kafelku i na pełnym
    ekranie, a klient dostaje logiczny ekran = okno / skala (zmierzone 18.10: 2048x1280 przy 3072x1920, panele całe,
    mapa wypełnia ekran). 2.2 było za bardzo zbliżone i rozmyte."""
    try:
        return max(1.0, float((env if env is not None else os.environ).get("RETRONIC_SKALA", "1.5")))
    except ValueError:
        return 1.5


def skala_dla(szer, bot=None, env=None):
    """Skala sway dla ekranu sesji o szerokości `szer` px: 1 przy bocie (piksele wzorcowe), inaczej stała skala, ale tak,
    by logiczna szerokość nie spadła poniżej minimum klienta (MIN_SZER)."""
    if bot_dziala() if bot is None else bot:
        return 1.0
    return round(max(1.0, min(skala_stala(env), szer / MIN_SZER)), 3)


def ustaw_skale_sway(szer, uruchom=subprocess.run):
    """swaymsg output * scale = szer/1175 na gniazdie sway sesji (jedyny headless sway w XDG_RUNTIME_DIR)."""
    import glob  # noqa: PLC0415
    gniazda = sorted(glob.glob(os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid()),
                                            "sway-ipc.*.sock")), key=os.path.getmtime)
    if not gniazda:
        return False
    skala = skala_dla(szer)
    w = uruchom(["swaymsg", "-s", gniazda[-1], "output", "*", "scale", str(skala)], capture_output=True, timeout=3)
    return w.returncode == 0


def roznia_sie(a, b, prog=PROG_PX):
    return abs(a[0] - b[0]) >= prog or abs(a[1] - b[1]) >= prog


# --- okno vncviewera (hyprctl) ------------------------------------------------

def hyprctl_klienci(uruchom=subprocess.run):
    """Lista okien z `hyprctl clients -j` albo [] (brak hyprctl / nie Hyprland / zły JSON)."""
    try:
        w = uruchom(["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=3)
        dane = json.loads(w.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    return dane if isinstance(dane, list) else []


def hyprctl_skale(uruchom=subprocess.run):
    """{id monitora: skala} z `hyprctl monitors -j` albo {} (brak hyprctl / zły JSON)."""
    try:
        w = uruchom(["hyprctl", "monitors", "-j"], capture_output=True, text=True, timeout=3)
        dane = json.loads(w.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}
    if not isinstance(dane, list):
        return {}
    return {m.get("id"): float(m["scale"]) for m in dane
            if isinstance(m, dict) and isinstance(m.get("scale"), (int, float)) and m["scale"] > 0}


def rozmiar_okna(klienci, pid=None, port=None, skale=None):
    """(szer, wys) okna vncviewera tej instancji w pikselach fizycznych albo None.

    Najpierw po pid; w zapasie klasa Vncviewer + port w tytule. hyprctl podaje rozmiar logiczny, a vncviewer (XWayland)
    rysuje framebuffer 1:1 w pikselach fizycznych, więc przy skali monitora 2 ekran sesji o rozmiarze okna logicznego
    zajmował tylko pół okna, reszta była szara (15.10). Dlatego mnożymy przez skalę monitora okna (`skale`)."""
    def rozmiar(k):
        r = k.get("size")
        if isinstance(r, (list, tuple)) and len(r) == 2 and all(isinstance(v, (int, float)) for v in r):
            sk = (skale or {}).get(k.get("monitor"), 1.0)
            return int(round(r[0] * sk)), int(round(r[1] * sk))
        return None
    vnc = [k for k in klienci if isinstance(k, dict) and "vncviewer" in str(k.get("class", "")).lower()
           and k.get("mapped", True) is not False]
    if pid is not None:
        for k in klienci:
            if isinstance(k, dict) and k.get("pid") == pid and rozmiar(k):
                return rozmiar(k)
    if port is not None:
        for k in vnc:
            if str(port) in str(k.get("title", "")) and rozmiar(k):
                return rozmiar(k)
    return None


# --- RFB (wayvnc sesji) -------------------------------------------------------

def _czytaj(s, n):
    bufor = b""
    while len(bufor) < n:
        kawalek = s.recv(n - len(bufor))
        if not kawalek:
            raise ConnectionError("serwer zamknął połączenie")
        bufor += kawalek
    return bufor


def rfb_polacz(port, host="127.0.0.1", timeout=TIMEOUT_RFB_S):
    """Połączenie RFB 3.8, security None, ClientInit shared=1. Zwraca (gniazdo, (szer, wys)) z ServerInit."""
    s = socket.create_connection((host, int(port)), timeout=timeout)
    try:
        s.settimeout(timeout)
        wersja = _czytaj(s, 12)
        if not wersja.startswith(b"RFB 003."):
            raise ConnectionError(f"to nie RFB: {wersja!r}")
        s.sendall(b"RFB 003.008\n" if int(wersja[8:11]) >= 8 else wersja)
        if int(wersja[8:11]) >= 7:
            n = _czytaj(s, 1)[0]
            if n == 0:
                dlugosc = struct.unpack(">I", _czytaj(s, 4))[0]
                raise ConnectionError("serwer odmówił: " + _czytaj(s, dlugosc).decode("utf-8", "replace"))
            typy = _czytaj(s, n)
            if 1 not in typy:
                raise ConnectionError(f"serwer nie oferuje security None (oferuje {list(typy)})")
            s.sendall(b"\x01")
            if int(wersja[8:11]) >= 8 and struct.unpack(">I", _czytaj(s, 4))[0] != 0:
                raise ConnectionError("security None odrzucone")
        else:
            raise ConnectionError("RFB 3.3 nieobsługiwane")
        s.sendall(b"\x01")                                    # ClientInit: shared = 1 (nie rozłączamy podglądu)
        szer, wys = struct.unpack(">HH", _czytaj(s, 4))
        _czytaj(s, 16)                                        # PixelFormat
        dlugosc_nazwy = struct.unpack(">I", _czytaj(s, 4))[0]
        _czytaj(s, dlugosc_nazwy)
        return s, (szer, wys)
    except BaseException:
        s.close()
        raise


def komunikat_set_desktop_size(szer, wys):
    """Bajty SetDesktopSize (typ 251), jeden ekran id 0: sprawdzona sekwencja z SPEC 15.10."""
    return struct.pack(">BxHHBx", 251, szer, wys, 1) + struct.pack(">IHHHHI", 0, 0, 0, szer, wys, 0)


def _odczytaj_odpowiedz(s):
    """Czyta wiadomości serwera do rekordu ExtendedDesktopSize. Zwraca (kod_wyniku, (szer, wys)) albo None."""
    for _ in range(8):
        typ = _czytaj(s, 1)[0]
        if typ == 0:                                          # FramebufferUpdate
            n = struct.unpack(">xH", _czytaj(s, 3))[0]
            wynik = None
            for _ in range(n):
                x, y, w, h, enc = struct.unpack(">HHHHi", _czytaj(s, 12))
                if enc != ENC_EXTENDED_DESKTOP_SIZE:
                    return wynik                              # nieznane kodowanie: nie umiemy czytać dalej
                ekrany = _czytaj(s, 4)[0]
                _czytaj(s, 16 * ekrany)
                if x == 1 or wynik is None:                   # x = powód: 1 = zażądał ten klient (nasza odpowiedź)
                    wynik = (y, (w, h))
            if wynik:
                return wynik
        elif typ == 2:                                        # Bell
            continue
        elif typ == 3:                                        # ServerCutText
            _czytaj(s, 3)
            _czytaj(s, struct.unpack(">I", _czytaj(s, 4))[0])
        else:
            return None
    return None


def odczytaj_rozmiar(port, polacz=rfb_polacz):
    """Aktualny rozmiar wyjścia sesji (ServerInit)."""
    s, rozmiar = polacz(port)
    s.close()
    return rozmiar


def ustaw_rozmiar(port, szer, wys, polacz=rfb_polacz):
    """Wysyła SetDesktopSize i czeka na odpowiedź. Zwraca (kod_wyniku|None, rozmiar po zmianie|None, rozmiar przed)."""
    s, przed = polacz(port)
    try:
        s.sendall(struct.pack(">BxHi", 2, 1, ENC_EXTENDED_DESKTOP_SIZE))   # SetEncodings: tylko ExtendedDesktopSize
        s.sendall(komunikat_set_desktop_size(szer, wys))
        try:
            odp = _odczytaj_odpowiedz(s)
        except (OSError, ConnectionError, struct.error):
            odp = None
    finally:
        s.close()
    return (odp[0], odp[1], przed) if odp else (None, None, przed)


# --- logika dopasowania -------------------------------------------------------

class Dopasowywacz:
    """Jeden tik = jeden odczyt okna. Wstrzykiwane: czytaj_okno() -> (w, h)|None, odczytaj() -> (w, h),
    ustaw(w, h) -> (kod|None, rozmiar po|None, rozmiar przed), zegar() -> s."""

    def __init__(self, czytaj_okno, odczytaj, ustaw, zegar=time.monotonic, log=print, po_zmianie=None):
        self.po_zmianie = po_zmianie
        self.czytaj_okno, self.odczytaj, self.ustaw, self.zegar, self.log = czytaj_okno, odczytaj, ustaw, zegar, log
        self.znany = None            # ostatni znany rozmiar wyjścia sesji
        self.znany_od = 0.0
        self.kandydat = None         # cel, który widzimy od self.od
        self.od = 0.0
        self.proba = None            # cel, który już wysłaliśmy (nie powtarzamy, dopóki okno się nie zmieni)

    def tik(self):
        okno = self.czytaj_okno()
        if okno is None:
            self.kandydat = None
            return None
        cel = ogranicz(*okno)
        t = self.zegar()
        if self.znany is None or t - self.znany_od >= ODSWIEZ_S:
            try:
                self.znany, self.znany_od = self.odczytaj(), t
            except (OSError, ConnectionError, struct.error) as e:
                self.log(f"dopasuj_okno: brak odczytu rozmiaru wyjścia ({e})")
                return None
        if not roznia_sie(cel, self.znany):
            self.kandydat = None
            return None
        if cel == self.proba:
            return None              # już próbowaliśmy tego celu (np. wayvnc ograniczył): czekamy na nowy rozmiar okna
        if self.kandydat != cel:
            self.kandydat, self.od = cel, t
            return None
        if t - self.od < DEBOUNCE_S:
            return None
        self.proba, self.kandydat = cel, None
        try:
            kod, po, przed = self.ustaw(*cel)
        except (OSError, ConnectionError, struct.error) as e:
            self.log(f"dopasuj_okno: zmiana rozmiaru nieudana ({e})")
            self.znany = None
            self.proba = None        # błąd połączenia, nie decyzja serwera: spróbujemy ponownie
            return None
        # kod wyniku z wayvnc bywa niezerowy mimo udanej zmiany (zmierzone 15.10: 1 i 4), więc wierzymy rozmiarowi z odpowiedzi;
        # bez odpowiedzi (None) odczytamy rozmiar wyjścia od nowa w następnym tiku
        self.znany, self.znany_od = po, self.zegar()
        if self.po_zmianie:
            try:
                self.po_zmianie(po or cel)
            except Exception as e:  # noqa: BLE001 - skala nie może zabić helpera
                self.log(f"dopasuj_okno: skala sway nieudana ({e})")
        self.log(f"dopasuj_okno: okno {okno[0]}x{okno[1]} -> wyjście sesji {przed[0]}x{przed[1]} => "
                 f"{cel[0]}x{cel[1]} (kod {kod if kod is not None else 'brak odpowiedzi'}, jest {'?' if po is None else f'{po[0]}x{po[1]}'})")
        return cel


def zyje(pid):
    try:
        os.kill(pid, 0)
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, help="port wayvnc sesji (domyślnie z $INST_SESJA/vnc_port)")
    ap.add_argument("--pid", type=int, help="pid vncviewera; helper kończy się razem z nim")
    a = ap.parse_args(argv)
    if not wlaczone():
        print("dopasuj_okno: wyłączone (RETRONIC_DOPASUJ_OKNO=0)")
        return 0
    port = a.port
    if port is None:
        import instancja  # noqa: PLC0415
        port = int((instancja.sesja() / "vnc_port").read_text().strip())
    skaluj = skaluj_wlaczone()
    def okno():
        r = rozmiar_okna(hyprctl_klienci(), a.pid, port, hyprctl_skale())
        return rozmiar_docelowy(r, bot_dziala())

    d = Dopasowywacz(okno,
                     lambda: odczytaj_rozmiar(port), lambda w, h: ustaw_rozmiar(port, w, h),
                     po_zmianie=(lambda rozm: ustaw_skale_sway(rozm[0])) if skaluj else None)
    if skaluj:
        print("dopasuj_okno: tryb SKALUJ (sway skaluje ekran do okna; gdy chodzi bot, wraca sam do 1175x910 w skali 1)", flush=True)
    print(f"dopasuj_okno: start (port {port}, pid {a.pid})", flush=True)
    while a.pid is None or zyje(a.pid):
        try:
            d.tik()
        except Exception as e:  # noqa: BLE001 - helper pomocniczy nie może paść i zostawić śmieci
            print(f"dopasuj_okno: błąd tiku: {type(e).__name__}: {e}", flush=True)
        sys.stdout.flush()
        time.sleep(CO_S)
    print("dopasuj_okno: podgląd zamknięty, koniec", flush=True)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())
