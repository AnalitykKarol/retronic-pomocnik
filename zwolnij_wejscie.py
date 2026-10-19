#!/usr/bin/env python3
"""Zwalnia wejście (XTEST) na ekranie gry tej instancji (RETRONIC_ID): lewy i prawy przycisk myszy, Control/Alt/Shift
oraz strzałki i numpad. Dla refill.sh --przerwij: ubity serwis.py mógł zostawić wciśnięty przycisk albo modyfikator
(jego `finally` w ekran.py nie biegnie po SIGKILL), a zatrzymaj.sh przy braku bota nic nie puszcza.
Nie rusza gniazda rdzenia ani gry; brak gry albo błąd = cicho kod 0 (to sprzątanie, nie akcja)."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))


def zwolnij():
    import bot
    import klawisz_x11
    from Xlib import X, XK, display
    from Xlib.ext import xtest
    ekran = bot.ekran_gry()
    klawisz_x11.puszczaj_wszystkie_strzalki(ekran)
    dpy = display.Display(ekran)
    try:
        for przycisk in (1, 3):
            xtest.fake_input(dpy, X.ButtonRelease, przycisk)
        for nazwa in ("Control_L", "Alt_L", "Shift_L"):
            kod = dpy.keysym_to_keycode(XK.string_to_keysym(nazwa))
            if kod:
                xtest.fake_input(dpy, X.KeyRelease, kod)
        dpy.sync()
    finally:
        dpy.close()


if __name__ == "__main__":
    try:
        zwolnij()
        print("wejście zwolnione")
    except (Exception, SystemExit) as e:
        print(f"wejście: pominięte ({e})", file=sys.stderr)
    sys.exit(0)
