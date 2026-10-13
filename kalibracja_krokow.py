#!/usr/bin/env python3
"""Aktywna kalibracja kroków postaci (czas kroku, opóźnienie strzałki, gubienie wciśnięć).

URUCHAMIAĆ RĘCZNIE, przy ZATRZYMANYM bocie (zatrzymaj.sh), na prostym odcinku bez potworów
(w poziomie ok. 5 wolnych pól, postać stoi na środku). Nie używa pliku STOP ani mózgu bota:
klawisze idą prosto przez klawisz_x11.

  python3 -I kalibracja_krokow.py            pełna kalibracja (ok. 6 min)
  python3 -I kalibracja_krokow.py --szybko   krótsze serie po 10 wciśnięć (ok. 3 min)
  python3 -I kalibracja_krokow.py --sucho    tylko kontrole bezpieczeństwa, bez klawiszy

Serie naprzemiennych strzałek Right/Left (netto zero) w odstępach 0.60 ... 0.10 s, z czasem
przytrzymania 40/70/110 ms, tryb "czekaj na zmianę pozycji" (poll 20 ms), tryb przytrzymania
klawisza oraz krótka seria po ukośnych (numpad). Wynik: tabela + rekomendowane stałe
w logi/kalibracja-<data>.json. Przerywa przy potworze/graczu w widoku, spadku HP, pliku STOP,
ścianie na torze; zawsze wraca na pole startowe.
"""
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.dont_write_bytecode = True
KATALOG = Path(__file__).resolve().parent
sys.path.insert(0, str(KATALOG))
import instancja  # noqa: E402

ODSTEPY = (0.60, 0.50, 0.42, 0.36, 0.30, 0.25, 0.20, 0.15, 0.10)
PRZYTRZYMANIA = (40, 70, 110)
POLL = 0.02
ZASIEG_POL = 2              # tyle pól na lewo/prawo od startu musi być przechodnich
DRENAZ = 1.6                # s czekania na dokończenie kolejkowanych kroków po serii
HP_SPADEK = 3               # pp HP: tyle straty przerywa
PROCESY = ("mozg.py", "cavebot.py")
PRAWO, LEWO = ("Right", 1, 0), ("Left", -1, 0)
UKOS_DOL, UKOS_GORA = ("KP_Next", 1, 1), ("KP_Home", -1, -1)


class Przerwano(Exception):
    pass


@dataclass
class Srodowisko:
    zegar: object        # () -> s
    spij: object         # (s)
    pozycja: object      # () -> (x, y, z)
    wcisnij: object      # (nazwa, ms): press+przytrzymanie+release (blokuje na ms)
    stwory: object       # () -> lista cudzych stworów/graczy w widoku
    hp: object           # () -> % HP
    przechodnie: object  # (x, y, z) -> True/False/None
    przytrzymaj: object = None   # (nazwa, ile_zmian, maks_s) -> lista czasów zmian (s od wciśnięcia)
    stop: object = None  # () -> True, gdy pojawił się plik STOP w trakcie


# --- bezpieczeństwo ---

def procesy_bota():
    """Nazwy skryptów bota działających teraz (czytamy /proc, nic nie ruszamy)."""
    wynik = []
    for wpis in os.listdir("/proc"):
        if not wpis.isdigit() or int(wpis) == os.getpid():
            continue
        try:
            arg = Path(f"/proc/{wpis}/cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if not arg or not Path(arg[0].decode(errors="replace")).name.startswith("python"):
            continue
        for a in arg[1:4]:
            nazwa = Path(a.decode(errors="replace")).name
            if nazwa in PROCESY and instancja.nalezy(int(wpis)):
                wynik.append(nazwa)
    return wynik


def sprawdz_bezpieczenstwo(stop_pliki=None, procesy=None):
    """Odmowa, gdy działa mozg.py/cavebot.py. Plik STOP bez działającego procesu to zwykły ślad po
    zatrzymaj.sh (zwraca ostrzeżenie); STOP przy działającym bocie = zatrzymywanie w toku, odmowa."""
    if stop_pliki is None:
        stop_pliki = [instancja.S.stop, instancja.S.stop_reczny]
    dziala = (procesy or procesy_bota)()
    stop = [str(p) for p in stop_pliki if Path(p).exists()]
    if dziala:
        raise Przerwano(f"działa {', '.join(sorted(set(dziala)))}"
                        + (" (plik STOP już ustawiony, poczekaj aż się zakończy)" if stop else "")
                        + ": zatrzymaj bota (zatrzymaj.sh) i uruchom ponownie")
    return [f"plik STOP istnieje ({', '.join(stop)}), ale bot nie działa: kontynuuję"] if stop else []


def sprawdz_trase(env, start):
    x, y, z = start
    for dx in range(-ZASIEG_POL, ZASIEG_POL + 1):
        for dy in (0, 1, -1) if abs(dx) <= 1 else (0,):
            if env.przechodnie(x + dx, y + dy, z) is not True:
                raise Przerwano(f"pole ({x + dx},{y + dy},{z}) nieprzechodnie albo nieznane na mapie: "
                                "stań na prostym, wolnym odcinku")


def _straz(env, hp0, start):
    if env.stop and env.stop():
        raise Przerwano("pojawił się plik STOP")
    cudze = env.stwory()
    if cudze:
        n = cudze[0]
        raise Przerwano(f"potwór/gracz w widoku: {n.get('nazwa', '?')}")
    hp = env.hp()
    if hp is not None and hp0 is not None and hp <= hp0 - HP_SPADEK:
        raise Przerwano(f"HP spadło z {hp0:.0f}% do {hp:.0f}%")


# --- ruch pomocniczy ---

def czekaj_na_zmiane(env, p0, maks):
    t0 = env.zegar()
    while env.zegar() - t0 < maks:
        env.spij(POLL)
        p = tuple(env.pozycja())
        if p != p0:
            return p, env.zegar() - t0
    return None, None


def wroc(env, start, przytrzymanie_ms=70):
    """Z powrotem na pole startowe krokami po jednym (czekając na każdy)."""
    for _ in range(12):
        p = tuple(env.pozycja())
        if p[:2] == tuple(start[:2]):
            return True
        # dryf drobny: najpierw dokończ trwający krok
        czekaj_na_zmiane(env, p, 0.7)
        p = tuple(env.pozycja())
        dx, dy = start[0] - p[0], start[1] - p[1]
        if dx:
            nazwa = "Right" if dx > 0 else "Left"
        elif dy:
            nazwa = "Down" if dy > 0 else "Up"
        else:
            return True
        env.wcisnij(nazwa, przytrzymanie_ms)
        czekaj_na_zmiane(env, p, 2.0)
    return tuple(env.pozycja())[:2] == tuple(start[:2])


def _policz(wciski, zmiany, t_koniec):
    """wciski: [t...], zmiany: [t...] -> słownik metryk."""
    n = len(wciski)
    if not n:
        return dict(wcisniec=0, zmian=0, skutecznosc=0.0, opoznienie_med=None, opoznienie_max=None, krok_med=None)
    op = []
    for i, t in enumerate(wciski):
        nast = wciski[i + 1] if i + 1 < n else t_koniec
        c = [z for z in zmiany if t <= z < nast]
        if len(c) == 1:                  # jednoznaczne przypisanie zmiany do wciśnięcia
            op.append(c[0] - t)
    kroki = [b - a for a, b in zip(zmiany, zmiany[1:]) if b - a < 2.0]
    return dict(wcisniec=n, zmian=len(zmiany), skutecznosc=round(min(1.0, len(zmiany) / n), 3),
                opoznienie_med=round(statistics.median(op), 3) if op else None,
                opoznienie_max=round(max(op), 3) if op else None,
                krok_med=round(statistics.median(kroki), 3) if kroki else None)


# --- tryby ---

def seria(env, odstep, n, przytrzymanie_ms, ruchy=(PRAWO, LEWO)):
    """n wciśnięć naprzemiennie co `odstep` s (od początku wciśnięcia do początku następnego)."""
    start = tuple(env.pozycja())
    hp0 = env.hp()
    wciski, zmiany = [], []
    ostatnia = start
    dryf = 0
    przerwana = None
    try:
        for i in range(n):
            _straz(env, hp0, start)
            nazwa, dx, dy = ruchy[i % 2]
            t = env.zegar()
            wciski.append(t)
            env.wcisnij(nazwa, przytrzymanie_ms)
            dryf += dx if dx else dy
            # do następnego wciśnięcia odpytujemy pozycję co POLL
            while env.zegar() - t < odstep:
                p = tuple(env.pozycja())
                if p != ostatnia:
                    zmiany.append(env.zegar()); ostatnia = p
                env.spij(max(0.001, min(POLL, odstep - (env.zegar() - t))))
            p = tuple(env.pozycja())
            if p != ostatnia:
                zmiany.append(env.zegar()); ostatnia = p
            if abs(ostatnia[0] - start[0]) >= ZASIEG_POL or abs(ostatnia[1] - start[1]) >= ZASIEG_POL:
                przerwana = "dryf"       # gubione wciśnięcia rozjechały parzystość: wracamy na start
                break
        t_end = env.zegar()
        while env.zegar() - t_end < DRENAZ:   # dokończenie kolejkowanych kroków
            env.spij(POLL)
            p = tuple(env.pozycja())
            if p != ostatnia:
                zmiany.append(env.zegar()); ostatnia = p
    finally:
        wroc(env, start, przytrzymanie_ms)
    w = _policz(wciski, zmiany, env.zegar())
    w.update(tryb="seria", odstep=odstep, przytrzymanie_ms=przytrzymanie_ms,
             ukosne=ruchy[0] not in (PRAWO, LEWO), przerwana=przerwana)
    return w


def tryb_czekaj(env, n, przytrzymanie_ms, ruchy=(PRAWO, LEWO), po_zmianie=0.0):
    """Wciskamy dopiero po stwierdzeniu zmiany pozycji (poll 20 ms): czysty czas kroku + opóźnienie."""
    start = tuple(env.pozycja())
    hp0 = env.hp()
    zmiany, wciski, op = [], [], []
    idx = 0                      # kierunek zmieniamy dopiero po udanym kroku: dryf nigdy > 1 pole
    try:
        for _ in range(n):
            _straz(env, hp0, start)
            nazwa, dx, dy = ruchy[idx % 2]
            p0 = tuple(env.pozycja())
            t = env.zegar()
            wciski.append(t)
            env.wcisnij(nazwa, przytrzymanie_ms)
            p, dt = czekaj_na_zmiane(env, p0, 2.0)
            if p is None:
                continue
            idx += 1
            zmiany.append(env.zegar())
            op.append(env.zegar() - t)
            if po_zmianie:
                env.spij(po_zmianie)
    finally:
        wroc(env, start, przytrzymanie_ms)
    w = _policz(wciski, zmiany, env.zegar())
    if op:
        w["opoznienie_med"], w["opoznienie_max"] = round(statistics.median(op), 3), round(max(op), 3)
    w.update(tryb="czekaj", odstep=None, przytrzymanie_ms=przytrzymanie_ms)
    return w


def tryb_przytrzymaj(env, powtorzen=5, ile_zmian=2):
    """Klawisz wciśnięty aż do ile_zmian zmian pozycji (Right, potem Left): czas kroku przy
    przytrzymaniu (autorepeat/ciągły marsz) i opóźnienie pierwszej zmiany."""
    if env.przytrzymaj is None:
        return None
    start = tuple(env.pozycja())
    hp0 = env.hp()
    pierwsze, miedzy = [], []
    try:
        for i in range(powtorzen):
            _straz(env, hp0, start)
            nazwa = "Right" if i % 2 == 0 else "Left"
            cz = env.przytrzymaj(nazwa, ile_zmian, 2.5)
            if cz:
                pierwsze.append(cz[0])
                miedzy += [b - a for a, b in zip(cz, cz[1:])]
            czekaj_na_zmiane(env, tuple(env.pozycja()), 0.9)   # dokończ trwający krok
    finally:
        wroc(env, start)
    return dict(tryb="przytrzymanie", odstep=None, przytrzymanie_ms=None, wcisniec=powtorzen,
                zmian=len(pierwsze) + len(miedzy),
                skutecznosc=round(min(1.0, len(pierwsze) / powtorzen), 3),
                opoznienie_med=round(statistics.median(pierwsze), 3) if pierwsze else None,
                opoznienie_max=round(max(pierwsze), 3) if pierwsze else None,
                krok_med=round(statistics.median(miedzy), 3) if miedzy else None)


# --- wnioski ---

def rekomendacje(tab, krok=None, opoznienie_max=None):
    """Z tabeli wyników: odstęp (najkrótszy z skutecznością >= 0.95 w seriach), próg braku zmiany
    (1.5 x najdłuższy z kroku/opóźnienia, min. 0.45), przytrzymanie (najskuteczniejsze)."""
    serie = [r for r in tab if r.get("tryb") == "seria" and not r.get("ukosne") and r.get("odstep")]
    dobre = [r for r in serie if r["skutecznosc"] >= 0.95]
    odstep = min((r["odstep"] for r in dobre), default=None)
    if krok is None:
        kroki = [r["krok_med"] for r in tab if r.get("krok_med")]
        krok = statistics.median(kroki) if kroki else None
    if opoznienie_max is None:
        ops = [r["opoznienie_max"] for r in tab if r.get("opoznienie_max")]
        opoznienie_max = max(ops) if ops else None
    baza = max([x for x in (krok, opoznienie_max) if x] or [0.3])
    brak = max(0.45, round(1.5 * baza / 0.05 + 0.4999) * 0.05)
    brak = round(brak, 2)
    po_przytrzymaniu = {}
    for r in serie:
        po_przytrzymaniu.setdefault(r["przytrzymanie_ms"], []).append(r["skutecznosc"])
    przytrz = None
    if po_przytrzymaniu:
        przytrz = max(sorted(po_przytrzymaniu), key=lambda p: statistics.mean(po_przytrzymaniu[p]))
    # zachowanie przy wciśnięciu w trakcie kroku: seria wyraźnie krótsza od kroku
    zach = None
    if krok:
        krotkie = [r for r in serie if r["odstep"] < 0.8 * krok]
        if krotkie:
            s = statistics.mean(r["skutecznosc"] for r in krotkie)
            zach = "kolejkowane" if s >= 0.9 else "odrzucane" if s < 0.75 else "mieszane"
    return {"POSCIG_KROK_MIN": odstep, "POSCIG_BRAK_ZMIANY": brak, "PRZYTRZYMANIE_MS": przytrz,
            "krok_s": round(krok, 3) if krok else None, "wcisniecie_w_trakcie_kroku": zach}


def zapisz(katalog, dane):
    katalog = Path(katalog)
    katalog.mkdir(parents=True, exist_ok=True)
    plik = katalog / time.strftime("kalibracja-%Y%m%d-%H%M%S.json")
    plik.write_text(json.dumps(dane, ensure_ascii=False, indent=1))
    return plik


def drukuj(tab):
    print(f"{'tryb':14}{'odstęp':>7}{'przytrz':>8}{'wciśn':>6}{'zmian':>6}{'skut.':>7}{'opóźn.med':>10}{'opóźn.max':>10}{'krok.med':>9}")
    for r in tab:
        f = lambda v, d=3: "-" if v is None else f"{v:.{d}f}"
        print(f"{r['tryb'] + ('/ukos' if r.get('ukosne') else ''):14}{f(r.get('odstep'), 2):>7}"
              f"{str(r.get('przytrzymanie_ms') or '-'):>8}{r['wcisniec']:>6}{r['zmian']:>6}"
              f"{r['skutecznosc']:>7.2f}{f(r['opoznienie_med']):>10}{f(r['opoznienie_max']):>10}{f(r['krok_med']):>9}"
              + (f"  [{r['przerwana']}]" if r.get("przerwana") else ""))


# --- środowisko prawdziwe ---

def srodowisko_gry():
    import bot
    import klawisz_x11
    import mapa as mapa_mod
    nazwa = bot.nazwa_postaci()
    ekran = bot.ekran_gry()
    m = mapa_mod.mapa()
    if m is None:
        raise Przerwano("brak pliku mapy (mapa/map74.otmm): nie sprawdzę przechodniości pól")
    stop_pliki = [instancja.S.stop, instancja.S.stop_reczny]
    istnialy = any(p.exists() for p in stop_pliki)

    def pozycja():
        p = bot.zapytaj({"cmd": "pozycja", "nazwa": nazwa})["pozycja"]
        return p["x"], p["y"], p["z"]

    def stwory():
        poz = pozycja()
        wynik = []
        for s in bot.zapytaj({"cmd": "stwory"})["stwory"]:
            if s.get("z") != poz[2] or s.get("hp", 100) <= 0:
                continue
            if s.get("gracz") and s.get("nazwa") == nazwa:
                continue
            wynik.append(s)
        return wynik

    def hp():
        g = bot.zapytaj({"cmd": "gracz"})["gracz"]
        return 100.0 * g["hp"] / g["max_hp"] if g.get("max_hp") else None

    def przytrzymaj(nazwa_k, ile, maks):
        from Xlib import X, XK
        from Xlib.ext import xtest
        with klawisz_x11._zamek:
            dpy = klawisz_x11._polaczenie(ekran)
            kod = dpy.keysym_to_keycode(XK.string_to_keysym(nazwa_k))
            p0 = pozycja(); t0 = time.monotonic(); zm = []
            xtest.fake_input(dpy, X.KeyPress, kod); dpy.sync()
            try:
                while time.monotonic() - t0 < maks and len(zm) < ile:
                    time.sleep(POLL)
                    p = pozycja()
                    if p != p0:
                        zm.append(time.monotonic() - t0); p0 = p
            finally:
                xtest.fake_input(dpy, X.KeyRelease, kod); dpy.sync()
        return zm

    return Srodowisko(
        zegar=time.monotonic, spij=time.sleep, pozycja=pozycja,
        wcisnij=lambda k, ms: klawisz_x11.wyslij(k, ms, ekran=ekran),
        stwory=stwory, hp=hp,
        przechodnie=lambda x, y, z: m.przechodnie(x, y, z),
        przytrzymaj=przytrzymaj,
        stop=lambda: not istnialy and any(p.exists() for p in stop_pliki))


def main(argv):
    szybko = "--szybko" in argv
    sucho = "--sucho" in argv
    n = 10 if szybko else 20
    for w in sprawdz_bezpieczenstwo():
        print("UWAGA:", w)
    env = srodowisko_gry()
    start = tuple(env.pozycja())
    sprawdz_trase(env, start)
    _straz(env, env.hp(), start)
    print(f"Start {start}, HP {env.hp():.0f}%. Kontrole OK." + (" (--sucho: koniec)" if sucho else ""))
    if sucho:
        return 0
    print("Za 5 s zaczynam (Ctrl+C przerywa; postać wróci na start).")
    time.sleep(5)
    tab = []
    try:
        for ms in PRZYTRZYMANIA:
            for odstep in ODSTEPY:
                w = seria(env, odstep, n, ms)
                tab.append(w)
                print(f"  seria {odstep:.2f}s/{ms}ms: skuteczność {w['skutecznosc']:.2f}, krok {w['krok_med']}", flush=True)
                time.sleep(1.0)
        for ms in PRZYTRZYMANIA:
            tab.append(tryb_czekaj(env, n, ms)); time.sleep(1.0)
        w = tryb_przytrzymaj(env)
        if w:
            tab.append(w)
        tab.append(seria(env, 0.9, 10, 70, ruchy=(UKOS_DOL, UKOS_GORA)))
    except (Przerwano, KeyboardInterrupt) as e:
        print(f"PRZERWANO: {e or 'Ctrl+C'}")
    finally:
        wroc(env, start)
    if not tab:
        return 1
    drukuj(tab)
    rek = rekomendacje(tab)
    print("\nRekomendacje:", json.dumps(rek, ensure_ascii=False))
    plik = zapisz(instancja.S.logi, {"start": list(start), "czas": time.strftime("%F %T"), "tabela": tab, "rekomendacje": rek})
    print("Zapisano:", plik)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
