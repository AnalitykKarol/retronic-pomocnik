"""bot.ekran_z_procesu / ekran_gry: tylko gra swojej instancji i sesji (18.10: powłoka z `grep RetronicGL-` dawała DISPLAY pulpitu).
Offline (RETRONIC_TESTY=1)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import bot

ok = []
def sprawdz(nazwa, warunek):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa)

GRA = b"C:\\users\\charlie\\AppData\\Roaming\\Retronic\\Retronic\\RetronicGL-1791965275.exe\0"
def env(display, wl, id_=None):
    w = [b"HOME=/x", b"DISPLAY=" + display, b"WAYLAND_DISPLAY=" + wl]
    if id_: w.append(b"RETRONIC_ID=" + id_)
    return w

sprawdz("1 gra swojej sesji", bot.ekran_z_procesu(GRA, env(b":1", b"wayland-2"), "", "wayland-2") == ":1")
sprawdz("2 powłoka z tekstem RetronicGL- w poleceniu nie jest grą",
        bot.ekran_z_procesu(b"bash\0-c\0ps | grep RetronicGL-1\0", env(b":0", b"wayland-1"), "", "wayland-2") is None)
sprawdz("3 gra innej sesji Wayland odpada", bot.ekran_z_procesu(GRA, env(b":2", b"wayland-3"), "", "wayland-2") is None)
sprawdz("4 gra innej instancji (RETRONIC_ID) odpada", bot.ekran_z_procesu(GRA, env(b":2", b"wayland-3", b"test"), "", None) is None)
sprawdz("5 instancja test widzi swoją", bot.ekran_z_procesu(GRA, env(b":2", b"wayland-3", b"test"), "test", "wayland-3") == ":2")
sprawdz("6 bez pliku sesji (gniazdo None) działa jak dotąd", bot.ekran_z_procesu(GRA, env(b":1", b"wayland-2"), "", None) == ":1")
sprawdz("7 RetronicDX też", bot.ekran_z_procesu(GRA.replace(b"GL", b"DX"), env(b":1", b"wayland-2"), "", "wayland-2") == ":1")
print(f"{sum(ok)}/{len(ok)}"); sys.exit(0 if all(ok) else 1)
