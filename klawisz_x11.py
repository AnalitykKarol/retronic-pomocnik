#!/usr/bin/env python3
"""Wysyła klawisz do gry przez XTEST na ekranie XWayland zagnieżdżonej sesji.
  klawisz_x11.py <keysym> [przytrzymanie_ms]     np. Right, Up, F1, space
  klawisz_x11.py skos <UpLeft|UpRight|DownLeft|DownRight> [przytrzymanie_ms]

Ruch po skosie: skos(kierunek). Domyślnie klawiatura numeryczna (KP_7/9/1/3 = NW/NE/SW/SE
w OTClient), niezależnie od NumLock: przy wyłączonym NumLock klawisz fizyczny wysyła KP_Home/
KP_Prior/..., więc na czas wciśnięcia włączamy NumLock (XTEST na klawiszu Num_Lock) i przywracamy.
Tryb "wsad" (Q/E/Z/C) działa tylko przy wsadWalking i wyłączonym czacie.

Chodzenie CIĄGŁE (pościg): klawisz TRZYMANY (KeyPress bez zwolnienia), bo w OTClient tap = jeden krok
i postać staje, a przy trzymanym klawiszu idzie jednostajnie.
  trzymaj(klawisz[, ekran])  naciśnij i trzymaj (jeśli trzymany jest inny: najpierw nowy, potem stary)
  zmien(klawisz_nowy)        zmiana kierunku BEZ LUKI: nowy naciśnięty przed puszczeniem starego
  skos(kier, trzymaj=True)   to samo dla skosu (numpad; NumLock włączany na czas trzymania)
  puszczaj([klawisz])        puść wskazany albo wszystkie trzymane
  puszczaj_wszystkie_strzalki()  czyszczenie (start bota, każde wyjście): puszcza trzymane ORAZ
                                 wysyła KeyRelease dla strzałek i KP_1/3/7/9 (na wypadek zabitego procesu)
  puls()                     "żyję" z pętli pościgu (co obrót), pilnuje limitu trzymania
Zabezpieczenia przed zakleszczonym klawiszem:
  * limit HOLD_LIMIT_S (1,5 s) ciągłego trzymania jednego klawisza: puść i naciśnij ponownie w TEJ SAMEJ
    partii zdarzeń XTEST (jeden sync), więc bez luki;
  * wątek-strażnik (co WATCHDOG_CO = 0,2 s): brak puls()/trzymaj() przez WATCHDOG_S (0,6 s) = puść wszystko;
  * atexit + zainstaluj_sygnaly() (SIGTERM/SIGINT/SIGHUP: puść, potem dotychczasowa obsługa);
  * proces-wartownik (STRAZNIK_PROCES): osobny, bardzo mały proces, który po śmierci procesu bota
    (także SIGKILL) puszcza strzałki i kończy się. Wyłączany w testach (RETRONIC_TESTY).
Autorepeat: serwer X generuje powtórzenia KeyPress także dla klawisza z XTEST (zmierzone na Xvnc/Xorg:
~22 KeyPress w 1,5 s przy trzymaniu). OTClient powtarza krok sam (stan klawisza), więc na czas trzymania
wyłączamy autorepeat per klawisz (ChangeKeyboardControl, AutoRepeatModeOff) i po puszczeniu przywracamy
AutoRepeatModeDefault (WYLACZ_AUTOREPEAT=False wyłącza tę ingerencję).
"""
import atexit
import os
import random
import signal
import subprocess
import sys
import threading
import time

from Xlib import X, XK, display
from Xlib.ext import xtest

EKRAN = ":1"


_polaczenia = {}          # ekran -> display.Display (jedno połączenie na sesję, odnawiane przy błędzie)
_zamek = threading.RLock()   # RLock: obsługa sygnału i strażnik wchodzą w tym samym wątku / po zwolnieniu
PRZYTRZYMANIE_MS = (30, 70)   # ms: losowy czas przytrzymania klawisza (dawniej 40-110; cofnięcie: (40, 110))
WYSLANE = 0               # licznik wysłanych klawiszy w tym procesie (pomiar pościgu: wysłane vs zmiany pozycji)


ZEGAR = time.monotonic        # testy podmieniają
HOLD_LIMIT_S = 1.5            # s ciągłego trzymania jednego klawisza, potem puść i naciśnij ponownie (jedna partia XTEST)
TRZYMANIE_MAX_S = 20.0        # s nieprzerwanego trzymania jakiegokolwiek klawisza (też przy zmianach kierunku): puls() puszcza wszystko
WATCHDOG_S = 0.6              # s bez puls()/trzymaj() = puść wszystko
WATCHDOG_CO = 0.2             # s: co ile strażnik sprawdza puls
WYLACZ_AUTOREPEAT = True      # autorepeat X per klawisz wyłączony na czas trzymania
STRAZNIK_PROCES = not os.environ.get("RETRONIC_TESTY")   # osobny proces-wartownik (SIGKILL bota)
STRZALKI = ("Up", "Down", "Left", "Right")
KLAWISZE_RUCHU = STRZALKI + ("KP_7", "KP_9", "KP_1", "KP_3")
KLAWISZ_WEKTOR = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0),
                  "KP_7": (-1, -1), "KP_9": (1, -1), "KP_1": (-1, 1), "KP_3": (1, 1)}
NACISNIETE = 0                # liczniki w procesie: naciśnięcia trzymane, zmiany klawisza, rollovery, puszczenia strażnika
ZMIANY = 0
ROLLOVERY = 0
WATCHDOG_PUSZCZENIA = 0

_trzymane = {}                # nazwa klawisza -> {"ekran", "kod", "od", "numpad"}
_ciagle_od = [None]           # [ZEGAR() od kiedy NIEPRZERWANIE trzymany jest jakiś klawisz; None = nic nie trzymamy]
_puls_czas = [None]           # [ZEGAR() ostatniego puls()/trzymaj()]
_numlock_przelaczony = {}     # ekran -> True: to MY włączyliśmy NumLock (przywracamy po puszczeniu numpadu)
_watchdog_stan = {"watek": None, "stop": threading.Event(), "straznik_proces": None}


def _polaczenie(ekran):
    dpy = _polaczenia.get(ekran)
    if dpy is None:
        dpy = _polaczenia[ekran] = display.Display(ekran)
    return dpy


def _zamknij(ekran):
    dpy = _polaczenia.pop(ekran, None)
    if dpy is not None:
        try:
            dpy.close()
        except Exception:
            pass


SKOSY_NUMPAD = {"UpLeft": "KP_7", "UpRight": "KP_9", "DownLeft": "KP_1", "DownRight": "KP_3"}
SKOSY_WSAD = {"UpLeft": "q", "UpRight": "e", "DownLeft": "z", "DownRight": "c"}
SKOSY_TRYBY = {"numpad": SKOSY_NUMPAD, "wsad": SKOSY_WSAD}
SKOS_TRYB = "numpad"      # który zestaw klawiszy wysyła skos() (wynik sonda_skosu.py)
SKOS_WEKTORY = {"UpLeft": (-1, -1), "UpRight": (1, -1), "DownLeft": (-1, 1), "DownRight": (1, 1)}
NUMLOCK_POCZEKAJ = 0.03   # s: czas na przetworzenie zmiany stanu NumLock przez serwer i Wine


def kierunek_skosu(dx, dy):
    """(dx, dy) o znakach +-1 (Tibia: y rośnie w dół) -> nazwa skosu albo None."""
    for nazwa, (x, y) in SKOS_WEKTORY.items():
        if (x, y) == ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0)) and dx and dy:
            return nazwa
    return None


def numlock_wlaczony(dpy):
    """Stan NumLock z maski modyfikatorów wskaźnika (Mod2). None, gdy nie da się ustalić."""
    try:
        return bool(dpy.screen().root.query_pointer().mask & X.Mod2Mask)
    except Exception:
        return None


def _stuknij(dpy, kod):
    xtest.fake_input(dpy, X.KeyPress, kod)
    xtest.fake_input(dpy, X.KeyRelease, kod)
    dpy.sync()
    time.sleep(NUMLOCK_POCZEKAJ)


def _wyslij_raz(dpy, nazwa, przytrzymanie_ms, numlock=False):
    kod = dpy.keysym_to_keycode(XK.string_to_keysym(nazwa))
    if not kod:
        raise ValueError(f"nieznany klawisz: {nazwa}")
    if numlock and numlock_wlaczony(dpy) is False:
        kod_nl = dpy.keysym_to_keycode(XK.string_to_keysym("Num_Lock"))
        if kod_nl:
            _stuknij(dpy, kod_nl)           # włącz na czas wciśnięcia
            try:
                _wyslij_raz(dpy, nazwa, przytrzymanie_ms)
            finally:
                _stuknij(dpy, kod_nl)       # przywróć wyłączony
            return
    xtest.fake_input(dpy, X.KeyPress, kod)
    try:
        dpy.sync()
        time.sleep((przytrzymanie_ms or random.randint(*PRZYTRZYMANIE_MS)) / 1000)
    finally:
        xtest.fake_input(dpy, X.KeyRelease, kod)
    dpy.sync()


def wyslij(nazwa, przytrzymanie_ms=None, ekran=EKRAN, numlock=False):
    """Jedno trwałe połączenie Display na ekran (zamiast connect+close na każdy klawisz);
    po błędzie połączenia odnawiamy je i próbujemy raz jeszcze."""
    with _zamek:
        for proba in (0, 1):
            try:
                _wyslij_raz(_polaczenie(ekran), nazwa, przytrzymanie_ms, numlock)
                global WYSLANE
                WYSLANE += 1
                return
            except ValueError:
                raise                   # zła nazwa klawisza: połączenie jest w porządku
            except Exception:
                _zamknij(ekran)         # zerwane połączenie: nowe przy następnej próbie
                if proba:
                    raise


# ---------------------------------------------------------------- klawisze TRZYMANE (ciągłe chodzenie)

def _kod_klawisza(dpy, nazwa):
    kod = dpy.keysym_to_keycode(XK.string_to_keysym(nazwa))
    if not kod:
        raise ValueError(f"nieznany klawisz: {nazwa}")
    return kod


def _autorepeat(dpy, kod, tryb_wl):
    """Autorepeat per klawisz (ChangeKeyboardControl). Błąd (atrapa, stary serwer) nie przerywa trzymania."""
    if not WYLACZ_AUTOREPEAT:
        return
    try:
        dpy.change_keyboard_control(
            key=kod, auto_repeat_mode=X.AutoRepeatModeDefault if tryb_wl else X.AutoRepeatModeOff)
    except Exception:
        pass


def _numpad_trzymany(ekran):
    return any(w["numpad"] and w["ekran"] == ekran for w in _trzymane.values())


def _numlock_przywroc(dpy, ekran):
    """Po puszczeniu ostatniego klawisza numpadu: NumLock z powrotem na wyłączony, jeśli to my go włączyliśmy."""
    if _numlock_przelaczony.get(ekran) and not _numpad_trzymany(ekran):
        _numlock_przelaczony.pop(ekran, None)
        kod_nl = dpy.keysym_to_keycode(XK.string_to_keysym("Num_Lock"))
        if kod_nl:
            _stuknij(dpy, kod_nl)


def _puls_ustaw():
    _puls_czas[0] = ZEGAR()


def _naciskanie(dpy, nazwa, ekran, numpad):
    """Naciśnij nazwa (jeśli trzymany inny klawisz na ekranie: NAJPIERW nowy, POTEM stary, jeden sync),
    albo odśwież limit trzymania, gdy to ten sam klawisz."""
    global NACISNIETE, ZMIANY, ROLLOVERY
    teraz = ZEGAR()
    w = _trzymane.get(nazwa)
    if w is not None and w["ekran"] == ekran:
        if teraz - w["od"] >= HOLD_LIMIT_S:       # limit: puść i naciśnij w tej samej partii zdarzeń
            xtest.fake_input(dpy, X.KeyRelease, w["kod"])
            xtest.fake_input(dpy, X.KeyPress, w["kod"])
            dpy.sync()
            w["od"] = teraz
            ROLLOVERY += 1
        return
    kod = _kod_klawisza(dpy, nazwa)
    if numpad and not _numpad_trzymany(ekran) and numlock_wlaczony(dpy) is False:
        kod_nl = dpy.keysym_to_keycode(XK.string_to_keysym("Num_Lock"))
        if kod_nl:
            _stuknij(dpy, kod_nl)
            _numlock_przelaczony[ekran] = True
    stare = [(n, s) for n, s in _trzymane.items() if s["ekran"] == ekran]
    _autorepeat(dpy, kod, False)
    xtest.fake_input(dpy, X.KeyPress, kod)       # najpierw nowy...
    for n, s in stare:
        xtest.fake_input(dpy, X.KeyRelease, s["kod"])   # ...potem stary: bez luki
    dpy.sync()
    for n, s in stare:
        _trzymane.pop(n, None)
        _autorepeat(dpy, s["kod"], True)
    _trzymane[nazwa] = {"ekran": ekran, "kod": kod, "od": teraz, "numpad": numpad}
    if not stare or _ciagle_od[0] is None:
        _ciagle_od[0] = teraz
    NACISNIETE += 1
    if stare:
        ZMIANY += 1
    _numlock_przywroc(dpy, ekran)


def _z_ponowieniem(ekran, fn):
    """fn(dpy) pod blokadą; po błędzie połączenia odnawiamy je i próbujemy raz jeszcze."""
    for proba in (0, 1):
        try:
            return fn(_polaczenie(ekran))
        except ValueError:
            raise
        except Exception:
            _zamknij(ekran)
            if proba:
                raise


def trzymaj(klawisz, ekran=EKRAN, numlock=None):
    """Naciśnij i TRZYMAJ klawisz (KeyPress bez zwolnienia). Gdy trzymany jest inny: najpierw naciśnięcie
    nowego, potem puszczenie starego (bez luki). Ten sam klawisz: tylko odświeżenie pulsu i limitu.
    numlock: None = automatycznie (nazwy KP_*), wtedy NumLock jest włączany na czas trzymania."""
    numpad = klawisz.startswith("KP_") if numlock is None else bool(numlock)
    _uruchom_strazy(ekran)
    with _zamek:
        _puls_ustaw()
        _z_ponowieniem(ekran, lambda dpy: _naciskanie(dpy, klawisz, ekran, numpad))
    return klawisz


def zmien(klawisz_nowy, ekran=EKRAN, numlock=None):
    """Zmiana kierunku w marszu bez luki. Zwraca nazwę zastąpionego klawisza albo None."""
    with _zamek:
        stary = trzymany(ekran)
        trzymaj(klawisz_nowy, ekran, numlock)
        return stary if stary != klawisz_nowy else None


def trzymaj_kierunek(dx, dy, ekran=EKRAN):
    """Trzymaj klawisz kierunku (dx, dy) o znakach +-1/0 (y w dół): oś = strzałka, skos = numpad (SKOS_TRYB)."""
    dx, dy = (dx > 0) - (dx < 0), (dy > 0) - (dy < 0)
    if dx and dy:
        return skos((dx, dy), ekran=ekran, trzymaj=True)
    nazwa = {(0, -1): "Up", (0, 1): "Down", (-1, 0): "Left", (1, 0): "Right"}.get((dx, dy))
    if nazwa is None:
        raise ValueError("kierunek (0, 0)")
    return trzymaj(nazwa, ekran)


def trzymany_kierunek(ekran=None):
    """Wektor (dx, dy) trzymanego klawisza albo None."""
    n = trzymany(ekran)
    if n is None:
        return None
    if n in KLAWISZ_WEKTOR:
        return KLAWISZ_WEKTOR[n]
    for zestaw in SKOSY_TRYBY.values():        # tryb "wsad"
        for kier, nazwa in zestaw.items():
            if nazwa == n:
                return SKOS_WEKTORY[kier]
    return None


def trzymany(ekran=None):
    """Nazwa trzymanego klawisza (na ekranie) albo None."""
    with _zamek:
        for n, w in _trzymane.items():
            if ekran is None or w["ekran"] == ekran:
                return n
    return None


def puls():
    """"Pętla żyje": odświeża puls strażnika i pilnuje limitu trzymania (puść+naciśnij w jednej partii)
    oraz TRZYMANIE_MAX_S ciągłego trzymania (zmiany kierunku bez puszczenia, np. oscylacja lewo-prawo)."""
    global ROLLOVERY
    with _zamek:
        _puls_ustaw()
        teraz = ZEGAR()
        if _trzymane and _ciagle_od[0] is not None and teraz - _ciagle_od[0] > TRZYMANIE_MAX_S:
            sys.stderr.write(f"klawisz_x11: ciągłe trzymanie > {TRZYMANIE_MAX_S:.0f} s, puszczam\n")
            puszczaj()
            return
        for n, w in list(_trzymane.items()):
            if teraz - w["od"] >= HOLD_LIMIT_S:
                try:
                    _z_ponowieniem(w["ekran"], lambda dpy, n=n, e=w["ekran"], num=w["numpad"]:
                                   _naciskanie(dpy, n, e, num))
                except Exception:
                    pass


def _zwolnij(dpy, ekran, nazwy):
    for n in nazwy:
        w = _trzymane.get(n)
        if w is not None:
            xtest.fake_input(dpy, X.KeyRelease, w["kod"])
    dpy.sync()
    for n in nazwy:                  # stan czyścimy dopiero po udanej wysyłce (ponowienie po błędzie połączenia)
        _trzymane.pop(n, None)
    if not _trzymane:
        _ciagle_od[0] = None
    _numlock_przywroc(dpy, ekran)


def puszczaj(klawisz=None, ekran=None):
    """Puść wskazany klawisz albo wszystkie trzymane (na ekranie albo na wszystkich). Zawsze czyści stan,
    nawet gdy wysyłka się nie uda. Zwraca listę puszczonych nazw."""
    with _zamek:
        wpisy = [(n, w) for n, w in _trzymane.items()
                 if (klawisz is None or n == klawisz) and (ekran is None or w["ekran"] == ekran)]
        puszczone = []
        for e in sorted({w["ekran"] for _, w in wpisy}):
            nazwy = [n for n, w in wpisy if w["ekran"] == e]
            kody = {n: _trzymane[n]["kod"] for n in nazwy if n in _trzymane}
            try:
                _z_ponowieniem(e, lambda dpy: _zwolnij(dpy, e, nazwy))
            except Exception as err:
                sys.stderr.write(f"klawisz_x11: puszczanie {nazwy} nieudane: {err!r}\n")
            for n in nazwy:
                _trzymane.pop(n, None)
            for n, kod in kody.items():
                try:
                    _autorepeat(_polaczenie(e), kod, True)
                    _polaczenie(e).sync()
                except Exception:
                    pass
            puszczone += nazwy
        if not _trzymane:
            _ciagle_od[0] = None
        return puszczone


def puszczaj_wszystkie_strzalki(ekran=EKRAN):
    """Czyszczenie na starcie i na każdym wyjściu: puszcza trzymane i dodatkowo wysyła KeyRelease dla
    strzałek i KP_1/3/7/9 (proces mógł zginąć z wciśniętym klawiszem). Błędów nie propaguje."""
    try:
        puszczaj(None, ekran)
    except Exception:
        pass
    try:
        with _zamek:
            def wyslij_release(dpy):
                for nazwa in KLAWISZE_RUCHU:
                    kod = dpy.keysym_to_keycode(XK.string_to_keysym(nazwa))
                    if kod:
                        xtest.fake_input(dpy, X.KeyRelease, kod)
                        _autorepeat(dpy, kod, True)
                dpy.sync()
            _z_ponowieniem(ekran, wyslij_release)
        return True
    except Exception:
        return False


def sprawdz_watchdog(teraz=None):
    """Strażnik: puls starszy niż WATCHDOG_S przy trzymanym klawiszu = puść wszystko. True, gdy puścił."""
    global WATCHDOG_PUSZCZENIA
    zdobyty = _zamek.acquire(timeout=0.3)
    try:
        if not _trzymane:
            return False
        teraz = ZEGAR() if teraz is None else teraz
        ost = _puls_czas[0]
        if ost is not None and teraz - ost <= WATCHDOG_S:
            return False
        puszczone = puszczaj()
        WATCHDOG_PUSZCZENIA += 1
        sys.stderr.write(f"klawisz_x11: strażnik puścił {puszczone} (brak pulsu pętli > {WATCHDOG_S} s)\n")
        return True
    finally:
        if zdobyty:
            _zamek.release()


def _strazny_petla(stop):
    while not stop.wait(WATCHDOG_CO):
        try:
            sprawdz_watchdog()
        except Exception:
            pass


def _zyje(pid):
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()[0] not in ("Z", "X")
    except (OSError, IndexError):
        return False


def _uruchom_strazy(ekran=EKRAN):
    """Wątek-strażnik (raz na proces) i proces-wartownik (raz, gdy STRAZNIK_PROCES)."""
    st = _watchdog_stan
    if st["watek"] is None or not st["watek"].is_alive():
        st["stop"].clear()
        st["watek"] = threading.Thread(target=_strazny_petla, args=(st["stop"],), daemon=True,
                                       name="klawisz-strazni")
        st["watek"].start()
    if STRAZNIK_PROCES and st["straznik_proces"] is None:
        try:
            st["straznik_proces"] = subprocess.Popen(
                [sys.executable, os.path.abspath(__file__), "--straznik", str(os.getpid()), ekran],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True)
        except Exception:
            st["straznik_proces"] = False   # nie ponawiamy


def _wartownik(ppid, ekran):
    """Proces-wartownik: po śmierci rodzica (także SIGKILL) puść strzałki i zakończ."""
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    while _zyje(ppid):
        time.sleep(0.15)
    puszczaj_wszystkie_strzalki(ekran)


def _zakoncz_atexit():
    try:
        _watchdog_stan["stop"].set()
        puszczaj()
    except Exception:
        pass


atexit.register(_zakoncz_atexit)


def zainstaluj_sygnaly(sygnaly=("SIGTERM", "SIGINT", "SIGHUP")):
    """Na SIGTERM/SIGINT/SIGHUP: puść trzymane klawisze, potem dotychczasowa obsługa (np. KeyboardInterrupt
    z mozg.py/cavebot.py), a gdy jej nie było - domyślna. Wołać PO własnym signal.signal() aplikacji."""
    if threading.current_thread() is not threading.main_thread():
        return
    for nazwa in sygnaly:
        sig = getattr(signal, nazwa, None)
        if sig is None:
            continue
        poprzedni = signal.getsignal(sig)

        def obsluga(numer, ramka, poprzedni=poprzedni):
            try:
                puszczaj()
            except Exception:
                pass
            if callable(poprzedni):
                poprzedni(numer, ramka)
            elif poprzedni == signal.SIG_IGN:
                return
            else:
                signal.signal(numer, signal.SIG_DFL)
                os.kill(os.getpid(), numer)
        signal.signal(sig, obsluga)


def skos(kierunek, przytrzymanie_ms=None, ekran=EKRAN, tryb=None, trzymaj=False):
    """Jeden krok po skosie: kierunek UpLeft/UpRight/DownLeft/DownRight (albo krotka (dx, dy)).
    tryb "numpad" (domyślnie SKOS_TRYB) lub "wsad". Zwraca nazwę wysłanego klawisza.
    trzymaj=True: klawisz zostaje wciśnięty (ciągły marsz po skosie; NumLock włączany na czas trzymania),
    puszcza go puszczaj()/zmien()/watchdog."""
    if isinstance(kierunek, tuple):
        kierunek = kierunek_skosu(*kierunek)
    zestaw = SKOSY_TRYBY.get(tryb or SKOS_TRYB)
    if zestaw is None or kierunek not in zestaw:
        raise ValueError(f"nieznany skos/tryb: {kierunek!r}/{tryb or SKOS_TRYB!r}")
    nazwa = zestaw[kierunek]
    if trzymaj:
        _trzymaj_klawisz(nazwa, ekran, zestaw is SKOSY_NUMPAD)
        return nazwa
    wyslij(nazwa, przytrzymanie_ms, ekran, numlock=(zestaw is SKOSY_NUMPAD))
    return nazwa


_trzymaj_klawisz = trzymaj    # skos() ma parametr o nazwie trzymaj


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--straznik":
        _wartownik(int(a[1]), a[2])
    elif a and a[0] == "puszczaj":
        puszczaj_wszystkie_strzalki(a[1] if len(a) > 1 else EKRAN)
    elif a and a[0] == "skos":
        skos(a[1], int(a[2]) if len(a) > 2 else None)
    else:
        wyslij(a[0], int(a[1]) if len(a) > 1 else None)
