import os as _os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import klawisz_x11

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

polaczenia, zdarzenia = [], []
class Dpy:
    def __init__(s, ekran):
        s.ekran = ekran; s.zepsuty = False; s.zamkniety = False; polaczenia.append(s)
    def keysym_to_keycode(s, ks): return 113 if ks else 0
    def sync(s):
        if s.zepsuty: raise ConnectionError("zerwane")
    def close(s): s.zamkniety = True
klawisz_x11.display.Display = Dpy
klawisz_x11.xtest.fake_input = lambda dpy, typ, kod: zdarzenia.append((id(dpy), typ, kod))
klawisz_x11.time.sleep = lambda d: None

klawisz_x11.wyslij("Right", 50, ekran=":9")
klawisz_x11.wyslij("Left", 50, ekran=":9")
sprawdz("jedno połączenie na wiele klawiszy", len(polaczenia) == 1 and not polaczenia[0].zamkniety, len(polaczenia))
sprawdz("press+release na klawisz", len(zdarzenia) == 4)
polaczenia[0].zepsuty = True
klawisz_x11.wyslij("Up", 50, ekran=":9")
sprawdz("po błędzie połączenie odnowione i klawisz wysłany", len(polaczenia) == 2 and polaczenia[0].zamkniety and not polaczenia[1].zamkniety, len(polaczenia))
klawisz_x11.wyslij("Down", 50, ekran=":9")
sprawdz("nowe połączenie znów współdzielone", len(polaczenia) == 2)
try:
    klawisz_x11.wyslij("", 50, ekran=":9"); blad = None
except ValueError as e:
    blad = e
sprawdz("zła nazwa klawisza -> ValueError, połączenie zostaje", blad is not None and not polaczenia[1].zamkniety and len(polaczenia) == 2)

# --- skosy ---
class Root:
    def __init__(s, d): s.d = d
    def query_pointer(s):
        class R: pass
        r = R(); r.mask = 0x10 if s.d.numlock else 0; return r
class Dpy2(Dpy):
    KODY = {"KP_7": 79, "KP_9": 81, "KP_1": 87, "KP_3": 89, "q": 24, "e": 26, "z": 52, "c": 54, "Num_Lock": 77}
    numlock = False
    def keysym_to_keycode(s, ks):
        from Xlib import XK as _XK
        for n, k in s.KODY.items():
            if _XK.string_to_keysym(n) == ks: return k
        return 0
    def screen(s):
        class S: pass
        o = S(); o.root = Root(s); return o
klawisz_x11.display.Display = Dpy2
klawisz_x11._polaczenia.clear()
zdarzenia.clear()
def kody(): return [k for (_, _, k) in zdarzenia]
sprawdz("kierunek_skosu", klawisz_x11.kierunek_skosu(-3, 2) == "DownLeft" and klawisz_x11.kierunek_skosu(1, 0) is None)
Dpy2.numlock = True
n = klawisz_x11.skos("UpLeft", 50, ekran=":8")
sprawdz("skos NW = KP_7 (keycode 79), bez dotykania NumLock przy włączonym", n == "KP_7" and kody() == [79, 79], kody())
zdarzenia.clear(); Dpy2.numlock = False
klawisz_x11.skos("DownRight", 50, ekran=":8")
sprawdz("NumLock wyłączony: stuknięcie Num_Lock przed i po klawiszu", kody() == [77, 77, 89, 89, 77, 77], kody())
zdarzenia.clear(); Dpy2.numlock = True
klawisz_x11.skos((1, -1), 50, ekran=":8", tryb="wsad")
sprawdz("tryb wsad: E bez NumLock, krotka (dx,dy)", kody() == [26, 26], kody())
try:
    klawisz_x11.skos("Up", 50, ekran=":8"); blad = None
except ValueError as e:
    blad = e
sprawdz("skos z kierunkiem prostym -> ValueError", blad is not None)

# --- klawisze TRZYMANE: zmiana bez luki, limit, strażnik, czyszczenie ---
import threading as _th
class Dpy3(Dpy2):
    KODY = dict(Dpy2.KODY, Up=111, Down=116, Left=113, Right=114)
    ar = []
    def change_keyboard_control(s, **kw): Dpy3.ar.append((kw.get("key"), kw.get("auto_repeat_mode")))
klawisz_x11.display.Display = Dpy3
klawisz_x11._polaczenia.clear(); klawisz_x11._trzymane.clear(); klawisz_x11._numlock_przelaczony.clear()
klawisz_x11.STRAZNIK_PROCES = False
klawisz_x11.WYLACZ_AUTOREPEAT = True
zegar = [100.0]
klawisz_x11.ZEGAR = lambda: zegar[0]
KP, KR = klawisz_x11.X.KeyPress, klawisz_x11.X.KeyRelease
def zd(): return [(typ, k) for (_, typ, k) in zdarzenia]
Dpy2.numlock = True
zdarzenia.clear(); Dpy3.ar.clear()
klawisz_x11.trzymaj("Right", ":7")
sprawdz("trzymaj: KeyPress bez zwolnienia, stan zapamiętany", zd() == [(KP, 114)] and klawisz_x11.trzymany(":7") == "Right", zd())
sprawdz("autorepeat per klawisz wyłączony na czas trzymania", Dpy3.ar and Dpy3.ar[0] == (114, klawisz_x11.X.AutoRepeatModeOff), Dpy3.ar)
zdarzenia.clear()
klawisz_x11.trzymaj("Right", ":7")
sprawdz("ten sam klawisz: bez nowych zdarzeń X", zd() == [], zd())
zdarzenia.clear(); Dpy3.ar.clear()
stary = klawisz_x11.zmien("Down", ":7")
sprawdz("zmiana kierunku BEZ LUKI: nowy naciśnięty przed puszczeniem starego, jedna partia",
        zd() == [(KP, 116), (KR, 114)] and stary == "Right" and klawisz_x11.trzymany(":7") == "Down", zd())
sprawdz("po zmianie: autorepeat starego przywrócony", (114, klawisz_x11.X.AutoRepeatModeDefault) in Dpy3.ar, Dpy3.ar)
# limit czasu trzymania: puść i naciśnij ponownie w tej samej partii (bez sync pomiędzy)
zdarzenia.clear()
syncy = []
oryg_sync = Dpy3.sync
Dpy3.sync = lambda s: (syncy.append(len(zdarzenia)), oryg_sync(s))[1]
zegar[0] += 1.6
klawisz_x11.puls()
sprawdz("limit 1,5 s: KeyRelease+KeyPress tego samego klawisza w jednej partii (jeden sync po obu)",
        zd() == [(KR, 116), (KP, 116)] and syncy == [2], (zd(), syncy))
Dpy3.sync = oryg_sync
zdarzenia.clear()
zegar[0] += 0.3
klawisz_x11.puls()
sprawdz("przed upływem limitu puls nic nie wysyła", zd() == [])
# strażnik: cisza > 0,6 s
zegar[0] += 0.5; sprawdz("strażnik: 0,5 s ciszy jeszcze nie puszcza", klawisz_x11.sprawdz_watchdog() is False and klawisz_x11.trzymany() == "Down")
zegar[0] += 0.2
zdarzenia.clear()
sprawdz("strażnik: > 0,6 s ciszy puszcza wszystko", klawisz_x11.sprawdz_watchdog() is True and klawisz_x11.trzymany() is None and zd() == [(KR, 116)], zd())
# wyjście puszcza wszystko; skos trzymany numpadem z NumLock
Dpy2.numlock = False; zdarzenia.clear()
n = klawisz_x11.skos("UpRight", ekran=":7", trzymaj=True)
sprawdz("skos trzymany: NumLock włączony (stuknięcie), KP_9 wciśnięty i trzymany",
        n == "KP_9" and zd() == [(KP, 77), (KR, 77), (KP, 81)] and klawisz_x11.trzymany() == "KP_9", zd())
zdarzenia.clear()
klawisz_x11.zmien("Left", ":7")
sprawdz("zmiana z numpadu na strzałkę: Left przed puszczeniem KP_9, NumLock przywrócony po puszczeniu numpadu",
        zd()[:2] == [(KP, 113), (KR, 81)] and zd()[2:] == [(KP, 77), (KR, 77)], zd())
zdarzenia.clear()
klawisz_x11.puszczaj(ekran=":7")
sprawdz("puszczaj() puszcza wszystkie trzymane", zd() == [(KR, 113)] and klawisz_x11.trzymany() is None, zd())
klawisz_x11.trzymaj("Up", ":7"); klawisz_x11.trzymaj("Up", ":7")
zdarzenia.clear()
okno = klawisz_x11.puszczaj_wszystkie_strzalki(":7")
kr = [k for typ, k in zd() if typ == KR]
sprawdz("puszczaj_wszystkie_strzalki: trzymany + KeyRelease dla 4 strzałek i 4 klawiszy numpadu (start po zabitym procesie)",
        okno and klawisz_x11.trzymany() is None and {111, 116, 113, 114, 79, 81, 87, 89} <= set(kr), zd())
# czyszczenie przy świeżym procesie: stan pusty, ale strzałki puszczone
klawisz_x11._trzymane.clear(); zdarzenia.clear()
klawisz_x11.puszczaj_wszystkie_strzalki(":7")
sprawdz("świeży proces bez stanu: i tak KeyRelease na strzałki", len([1 for typ, k in zd() if typ == KR]) >= 8)
# błąd połączenia podczas puszczania: stan i tak wyczyszczony, połączenie odnowione
klawisz_x11.trzymaj("Right", ":7")
klawisz_x11._polaczenia[":7"].zepsuty = True
klawisz_x11.puszczaj(ekran=":7")
sprawdz("zerwane połączenie przy puszczaniu: stan czysty, bez wyjątku", klawisz_x11.trzymany() is None)
# prawdziwy wątek strażnika: cisza puszcza (zegar sterowany)
klawisz_x11.WATCHDOG_CO = 0.02
klawisz_x11._watchdog_stan["stop"].set()
klawisz_x11._watchdog_stan["watek"] = None
klawisz_x11.trzymaj("Left", ":7")
zegar[0] += 5.0
import time as _t
for _ in range(100):
    if klawisz_x11.trzymany() is None: break
    _th.Event().wait(0.01)   # time.sleep jest w tym teście podmieniony na atrapę
sprawdz("wątek-strażnik sam puszcza po ciszy", klawisz_x11.trzymany() is None)
klawisz_x11._watchdog_stan["stop"].set()
# sygnał: puść, potem poprzednia obsługa
import signal as _sg
wolane = []
_sg.signal(_sg.SIGUSR1, lambda *a: wolane.append("poprzednia"))
klawisz_x11.zainstaluj_sygnaly(("SIGUSR1",))
klawisz_x11.trzymaj("Up", ":7"); zdarzenia.clear()
import os as _os
_os.kill(_os.getpid(), _sg.SIGUSR1)
sprawdz("sygnał: klawisze puszczone, potem poprzedni handler", klawisz_x11.trzymany() is None and wolane == ["poprzednia"], (wolane, zd()))
try:
    klawisz_x11.trzymaj("", ":7"); blad = None
except ValueError as e:
    blad = e
sprawdz("trzymaj('') -> ValueError, nic nie trzymane", blad is not None and klawisz_x11.trzymany() is None)
# oscylacja: ciągłe zmiany kierunku bez puszczenia nie omijają limitu TRZYMANIE_MAX_S (puls puszcza wszystko)
klawisz_x11.puszczaj(ekran=":7")
klawisz_x11.trzymaj("Left", ":7")
for i in range(1, 8):
    zegar[0] += 3.0
    klawisz_x11.zmien("Right" if i % 2 else "Left", ":7")
    klawisz_x11.puls()
sprawdz("oscylacja Left/Right 21 s bez puszczenia: puls() puszcza po TRZYMANIE_MAX_S", klawisz_x11.trzymany() is None)
klawisz_x11.trzymaj("Up", ":7"); zegar[0] += 5.0; klawisz_x11.puls()
sprawdz("krótkie trzymanie po puszczeniu nie jest ucinane", klawisz_x11.trzymany() == "Up")
klawisz_x11.puszczaj(ekran=":7")
print(f"\n{sum(ok)}/{len(ok)} OK"); sys.exit(0 if all(ok) else 1)
