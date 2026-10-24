#!/usr/bin/env python3
"""23.10 (Karol po resecie serwera 10:00: „Boty powinny być wyłączane po wylogowaniu od razu i włączane ponownie”).
Offline: bez gry, X11 i sesji, na atrapach świata. Czego dowodzi:
  (A) bot, który wykrył ekran logowania, KOŃCZY proces: tick() zwraca False, zero klawiszy po wykryciu, log `WYLOGOWANY: kończę bota`
      z powodem, znacznik instancji `wylogowany.json` (czas, powód, mapa i tryb z tryb.log), jedno powiadomienie;
  (B) domyślne pokrętła w kodzie: ROZLACZENIE_STOP=1 i ROZLACZENIE_WYJSCIE=1 (gebelish i odchyd nie miały klucza w na_zywo.json,
      więc 23.10 domyślne 0 nie wykryło wylogowania i bot naciskał klawisze na liście postaci);
  (C) postać zniknęła z pamięci (gracz()/pozycja() rzucają), a zrzut = ekran logowania: też koniec; zrzut = gra albo brak zrzutu: błąd
      leci dalej jak dotąd (mozg liczy LIMIT_BLEDOW), bez znacznika;
  (D) pokrętło ROZLACZENIE_WYJSCIE=0: dawne zachowanie (pauza, proces trwa, powrót do gry wznawia pracę);
  (E) start: czekanie na pozycję ze strażnika (do 60 s) albo głośna odmowa, bez Traceback;
  (F) start na piętrze spoza pętli, blisko trasy (upadek do dziury): najpierw wyjście w górę (wpadniecie.z_kieszeni), bez dojścia;
      dalej od trasy albo trasa niżej niż postać: bez zmian."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import random
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
KORZEN = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
import bot  # noqa: E402
import cavebot  # noqa: E402
import mozg  # noqa: E402
try:
    import wylogowanie  # noqa: E402
except ImportError:          # stary kod: testy poniżej dają FAIL, nie wyjątek
    wylogowanie = None

cavelog = []
_log0 = cavebot.log


def _log(*a):
    cavelog.append(" ".join(map(str, a)))
    _log0(*a)


cavebot.log = _log
cavebot.REAKCJA = (0.0, 0.0)
cavebot.DRUGI_CEL = 0.0
cavebot.ROZRZUT_PROGU = 0.0
cavebot.STRAZNIK_CEL = 0
cavebot.ODWROCENIE_TRASY = 0.0
cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5)
cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False
cavebot.ZDROWIE_CZAR_AKTYWNY = 0
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


KROK = 1.2
DOMYSLNE = {k: getattr(cavebot, k, None) for k in ("ROZLACZENIE_STOP", "ROZLACZENIE_WYJSCIE")}

# ------------------------------------------------------------------------------------------------- (B) domyślne
sprawdz("B1 domyślnie ROZLACZENIE_STOP == 1 (brak klucza w na_zywo.json = ochrona włączona)", DOMYSLNE["ROZLACZENIE_STOP"] == 1, DOMYSLNE)
sprawdz("B2 domyślnie ROZLACZENIE_WYJSCIE == 1 (koniec procesu po wylogowaniu)", DOMYSLNE["ROZLACZENIE_WYJSCIE"] == 1, DOMYSLNE)
przyklad = json.loads((KORZEN / "na_zywo.przyklad.json").read_text())
sprawdz("B3 na_zywo.przyklad.json: ROZLACZENIE_STOP 1 i ROZLACZENIE_WYJSCIE 1",
        przyklad.get("ROZLACZENIE_STOP") == 1 and przyklad.get("ROZLACZENIE_WYJSCIE") == 1, {k: przyklad.get(k) for k in DOMYSLNE})
import pokretla  # noqa: E402
sprawdz("B4 pokretla.ZAKRESY zna ROZLACZENIE_WYJSCIE (0-1)", pokretla.ZAKRESY.get("ROZLACZENIE_WYJSCIE") == (0, 1), pokretla.ZAKRESY.get("ROZLACZENIE_WYJSCIE"))


# ------------------------------------------------------------------------------------------------- (A) świat
class Swiat:
    """Żywy do `t_stop` (potem wszystko stoi: pamięć klienta na liście postaci). Zrzut: `ekran` (True = ekran logowania)."""

    def __init__(s, t_stop=48.0):
        s.t, s.t_stop = 0.0, t_stop
        s.poz = [32500, 32279, 9]
        s.ekran = True
        s.klawisze, s.ataki, s.zrzuty = [], [], 0
        s.brak_postaci = False       # gracz()/pozycja() rzucają „nie widzę postaci”

    def zegar(s):
        return s.t

    def spij(s, d):
        pass

    def zywy(s):
        return s.t < s.t_stop

    def zapytaj(s, z):
        if s.brak_postaci and z["cmd"] in ("gracz", "pozycja"):
            raise RuntimeError("nie widzę postaci Bober Qrwa (zalogowana?)")
        if z["cmd"] == "gracz":
            n = int(s.t) if s.zywy() else int(s.t_stop)
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 20, "max_mana": 25, "exp": 1000 + n, "level": 6, "cap": 151}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            if s.zywy():
                szczur = {"id": 8416, "nazwa": "Cave Rat", "gracz": False, "x": s.poz[0] + 6 - int(s.t) % 4, "y": s.poz[1] + 2,
                          "z": s.poz[2], "hp": 100}
                return {"stwory": [ja, szczur]}
            return {"stwory": [ja]}
        return {}


class P:
    nazwa = "Bober Qrwa"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        if p.s.brak_postaci:
            raise RuntimeError("nie widzę postaci Bober Qrwa (zalogowana?)")
        return tuple(p.s.poz)

    def klawisz(p, k):
        p.s.klawisze.append(k)

    def krok(p, k):
        p.s.klawisze.append(k)
        return None


class Tele:
    def __init__(t):
        t.zd = []

    def zdarzenie(t, typ, **d):
        t.zd.append((typ, d))

    def probka(t, *a, **k):
        return None

    def ruch_tick(t, *a, **k):
        pass


def zrob(s, **knoby):
    """Cavebot na atrapie. Pokrętła wylogowania zostają DOMYŚLNE z kodu, chyba że podane w `knoby`."""
    for k, v in DOMYSLNE.items():
        if v is not None:
            setattr(cavebot, k, v)
    for k, v in knoby.items():
        setattr(cavebot, k, v)
    cavebot.SMIERC_STOP = 0
    katalog = Path(tempfile.mkdtemp(prefix="wylog-test-"))
    (katalog / "logi").mkdir()
    (katalog / "logi" / "tryb.log").write_text(
        "2026-10-23 07:42:11 [TRYB] mapa trolle_edron_z9z: trasa trolle_edron_z9z_petla, potwory Troll,Bear, prog-hp 30\n"
        "2026-10-23 07:42:11 [TRYB] tryb ostrozny+runy+uh: pokrętła {\"A\": 1}\n")

    def atak(m, g):
        s.ataki.append(m["id"])
    loot = types.SimpleNamespace(zbierz=lambda zw, g: "ok")
    punkty = [(32500 + i, 32279, 9) for i in range(1, 11)]
    b = cavebot.Cavebot(P(s), punkty, okrazenia=999, zapytaj=s.zapytaj, atak=atak, alarm=lambda w: None,
                        spij=s.spij, zegar=s.zegar, loot=loot)
    b.stopy, b.pow = [], []
    b._pk_stop = lambda opis: b.stopy.append(opis)
    b._pk_powiadom = lambda tytul, tresc, klucz: b.pow.append((tytul, tresc, klucz))
    b.tele = Tele()
    b.wylog_stan = katalog
    b.wylog_tryb_log = katalog / "logi" / "tryb.log"

    def zrzut():
        s.zrzuty += 1
        return s.ekran
    b._rozl_zrzut = zrzut
    b.katalog = katalog
    return b


def obiegi(b, s, n, krok=KROK):
    """Do n obiegów; zwraca (liczba wykonanych, czy tick zwrócił False Z POWODU WYLOGOWANIA, wyjątek). Po takim False nie wołamy dalej
    (jak mozg: break). False z innych powodów (atrapa świata: „trzy punkty nieosiągalne”) ignorujemy jak test_rozlaczenie.py."""
    blad = None
    for i in range(n):
        s.t += krok
        try:
            if not b.tick() and getattr(b, "wylogowany", False):
                return i + 1, True, blad
        except Exception as e:      # noqa: BLE001  mozg łapie wyjątek ticka, liczy błędy i woła tick dalej
            blad = e
    return n, False, blad


def akcje(s):
    return len(s.klawisze) + len(s.ataki)


# (A) wylogowanie na ekran logowania, pamięć stoi: koniec procesu
random.seed(7)
s = Swiat()
b = zrob(s)
n0, koniec0, _ = obiegi(b, s, 40)
sprawdz("A0 (przygotowanie) żywa gra: bot chodzi i nie kończy", akcje(s) > 0 and not koniec0 and not b.pow, f"{akcje(s)} {koniec0} {b.pow}")
a0 = akcje(s)
n1, koniec, blad = obiegi(b, s, 300)
sprawdz("A1 po wykryciu wylogowania tick() zwraca False (proces się kończy), bez wyjątku", koniec and blad is None, f"{koniec} {blad!r}")
sprawdz("A2 koniec 25-45 s po zamrożeniu pamięci (nie po 5 min)", koniec and 25.0 <= s.t - 48.0 <= 45.0, f"t={s.t}")
a_wykr = akcje(s)
if koniec:                                                    # jeszcze kilka obiegów: nawet gdyby ktoś zawołał tick, zero akcji
    obiegi(b, s, 10)
sprawdz("A3 zero klawiszy i ataków od wykrycia do końca", akcje(s) == a_wykr, f"{a_wykr} -> {akcje(s)}")
sprawdz("A4 w logu WYLOGOWANY: kończę bota + powód (ekran logowania)", any("WYLOGOWANY: kończę bota" in l and "logowania" in l for l in cavelog), cavelog[-4:])
sprawdz("A5 jedno powiadomienie critical z nazwą postaci", len(b.pow) == 1 and "Bober Qrwa" in b.pow[0][1], b.pow)
znacznik = Path(b.katalog / "wylogowany.json")
d = json.loads(znacznik.read_text()) if znacznik.exists() else {}
sprawdz("A6 znacznik wylogowany.json: czas, powód, nick, pozycja", d.get("czas") and "logowania" in str(d.get("powod")) and d.get("nick") == "Bober Qrwa"
        and d.get("poz") == [32500, 32279, 9], d)
sprawdz("A7 znacznik: mapa i tryb z tryb.log (do wznowienia po relogu)", d.get("mapa") == "trolle_edron_z9z" and d.get("tryb") == "ostrozny,runy,uh", d)
sprawdz("A8 po końcu flaga cb.wylogowany i brak STOP", getattr(b, "wylogowany", False) is True and not b.stopy, f"{getattr(b, 'wylogowany', None)} {b.stopy}")
sprawdz("A9 telemetria: rekord 'rozlaczenie' (jak dotąd)", any(t == "rozlaczenie" for t, _ in b.tele.zd), b.tele.zd[-2:])

# (A2) zdrowa gra z postojem (zrzut = gra): bez końca, ani znacznika
random.seed(7)
s = Swiat()
s.ekran = False
b = zrob(s)
n1, koniec, blad = obiegi(b, s, 340)
sprawdz("A10 zdrowy postój pamięci (zrzut = gra): bot nie kończy, bez znacznika", not koniec and blad is None and not (b.katalog / "wylogowany.json").exists(),
        f"{koniec} {blad!r}")

# (A3) „lista postaci bez komunikatu”: odciski się nie zmieniają, ale to pokrętła domyślne (jak gebelish/odchyd bez klucza w na_zywo.json)
random.seed(7)
s = Swiat()
b = zrob(s)                                      # NIC nie ustawiamy: tylko domyślne z kodu
obiegi(b, s, 40)
n1, koniec, blad = obiegi(b, s, 300)
sprawdz("A11 bez żadnego klucza w na_zywo.json (domyślne z kodu): bot kończy po wylogowaniu", koniec, f"{koniec} {blad!r}")

# ------------------------------------------------------------------------------------------------- (C) postać znikła z pamięci
random.seed(7)
s = Swiat(t_stop=1e9)
b = zrob(s)
obiegi(b, s, 30)
s.brak_postaci = True
s.ekran = True
a0 = akcje(s)
n1, koniec, blad = obiegi(b, s, 10)
sprawdz("C1 gracz()/pozycja() rzucają, zrzut = ekran logowania: tick() zwraca False w ciągu kilku obiegów", koniec and n1 <= 4, f"n={n1} {koniec} {blad!r}")
d = json.loads((b.katalog / "wylogowany.json").read_text()) if (b.katalog / "wylogowany.json").exists() else {}
sprawdz("C2 znacznik z powodem „postaci brak w pamięci” i mapą/trybem", "brak" in str(d.get("powod")) and d.get("mapa") == "trolle_edron_z9z", d)
sprawdz("C3 zero klawiszy od zniknięcia postaci", akcje(s) == a0, f"{a0} -> {akcje(s)}")

random.seed(7)
s = Swiat(t_stop=1e9)
b = zrob(s)
obiegi(b, s, 30)
s.brak_postaci = True
s.ekran = False                                   # zrzut = gra: to nie wylogowanie, błąd leci dalej (mozg liczy LIMIT_BLEDOW)
n1, koniec, blad = obiegi(b, s, 10)
sprawdz("C4 postaci brak, zrzut = gra: wyjątek leci dalej, bez końca i znacznika", (not koniec) and isinstance(blad, RuntimeError)
        and not (b.katalog / "wylogowany.json").exists(), f"{koniec} {blad!r}")
random.seed(7)
s = Swiat(t_stop=1e9)
b = zrob(s)
obiegi(b, s, 30)
s.brak_postaci = True
s.ekran = None                                    # brak zrzutu: bez decyzji
n1, koniec, blad = obiegi(b, s, 10)
sprawdz("C5 postaci brak, zrzut niedostępny: wyjątek leci dalej, bez znacznika", (not koniec) and isinstance(blad, RuntimeError)
        and not (b.katalog / "wylogowany.json").exists(), f"{koniec} {blad!r}")

# ------------------------------------------------------------------------------------------------- (D) pokrętło WYJSCIE=0
random.seed(7)
s = Swiat()
b = zrob(s, ROZLACZENIE_WYJSCIE=0)
obiegi(b, s, 40)
n1, koniec, blad = obiegi(b, s, 120)
sprawdz("D1 ROZLACZENIE_WYJSCIE=0: dawna pauza, proces trwa, bez znacznika", (not koniec) and blad is None and b.rozlaczony is True
        and not (b.katalog / "wylogowany.json").exists(), f"{koniec} {blad!r} {getattr(b, 'rozlaczony', None)}")
s.t_stop = 1e9
s.ekran = False
obiegi(b, s, 40)
sprawdz("D2 ROZLACZENIE_WYJSCIE=0: po powrocie do gry praca wraca", b.rozlaczony is False)

# ------------------------------------------------------------------------------------------------- (E) start po zalogowaniu
if wylogowanie is None:
    sprawdz("E0 moduł wylogowanie.py istnieje", False, "brak modułu (stary kod)")
else:
    zegar_t = [0.0]
    spania = []

    def zegar():
        return zegar_t[0]

    def spij(d):
        spania.append(d)
        zegar_t[0] += d

    wywolania = [0]

    def pozycja_po_5():
        wywolania[0] += 1
        if wywolania[0] <= 5:
            raise RuntimeError("nie widzę postaci Dawajkesh (zalogowana?)")
        return (33084, 31743, 10)
    logE = []
    w = wylogowanie.czekaj_na_postac(pozycja_po_5, limit_s=60, krok_s=2, zegar=zegar, spij=spij, log=logE.append)
    sprawdz("E1 strażnik widzi postać po 5 próbach: czekanie kończy się pozycją (bez wyjątku)", w == (33084, 31743, 10) and wywolania[0] == 6 and sum(spania) == 10,
            f"{w} {wywolania} {sum(spania)}")
    zegar_t[0], spania[:] = 0.0, []

    def nigdy():
        raise RuntimeError("nie widzę postaci Dawajkesh (zalogowana?)")
    w = wylogowanie.czekaj_na_postac(nigdy, limit_s=60, krok_s=2, zegar=zegar, spij=spij, log=logE.append)
    sprawdz("E2 strażnik nie widzi postaci przez 60 s: None (odmowa), czas oczekiwania 60 s, bez wyjątku", w is None and 58 <= sum(spania) <= 62, f"{w} {sum(spania)}")
    sprawdz("E3 odmowa zostawia czytelny wpis w logu", any("nie widzi postaci" in l for l in logE), logE)
    zegar_t[0], spania[:] = 0.0, []

    class Przerwij(Exception):
        pass
    try:
        wylogowanie.czekaj_na_postac(lambda: (_ for _ in ()).throw(Przerwij()), limit_s=60, zegar=zegar, spij=spij, przepusc=(Przerwij,))
        przepuszczony = False
    except Przerwij:
        przepuszczony = True
    sprawdz("E4 wyjątek z `przepusc` (bot.Zatrzymano) leci dalej", przepuszczony)

# mozg.main: odmowa startu bez Tracebacku (postać niewidoczna)
sprawdz("E5 mozg.postac_widoczna istnieje", hasattr(mozg, "postac_widoczna"))
if hasattr(mozg, "postac_widoczna"):
    class PBrak:
        nazwa = "Dawajkesh"

        def pozycja(self):
            raise RuntimeError("nie widzę postaci Dawajkesh (zalogowana?)")
    cavebot.START_CZEKAJ_POSTAC_S = 4
    logM = []
    t0 = [0.0]
    try:
        wynik = mozg.postac_widoczna(PBrak(), logM.append, zegar=lambda: t0[0], spij=lambda d: t0.__setitem__(0, t0[0] + d))
        blad = None
    except Exception as e:      # noqa: BLE001
        wynik, blad = None, e
    sprawdz("E6 postać niewidoczna: odmowa startu (False) bez wyjątku", wynik is False and blad is None, f"{wynik} {blad!r}")
    sprawdz("E7 odmowa głośna: wpis `ODMOWA STARTU` w logu", any("ODMOWA STARTU" in l for l in logM), logM)

    class PJest:
        nazwa = "Dawajkesh"

        def pozycja(self):
            return (33084, 31743, 9)
    sprawdz("E8 postać widoczna: True od razu", mozg.postac_widoczna(PJest(), logM.append, zegar=lambda: 0.0, spij=lambda d: None) is True)

# uruchom.sh czeka na strażnika
tekst_sh = (KORZEN / "uruchom.sh").read_text()
sprawdz("E9 uruchom.sh czeka na pozycję ze strażnika (pętla prób przed decyzją o dojściu)", "for _ in" in tekst_sh.split("Z=$(")[0] or "CZEKAJ_NA_POSTAC" in tekst_sh,
        "brak pętli czekania")

# uruchom.sh na atrapie strażnika, który nie widzi postaci: odmowa (exit 3) po czekaniu, bez startu bota i bez dymku (notify-send = atrapa)
import socket  # noqa: E402
import subprocess  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
if not _os.environ.get("RETRONIC_ID"):
    rt = Path(tempfile.mkdtemp(prefix="wylog-rt-"))
    bin_ = Path(tempfile.mkdtemp(prefix="wylog-bin-"))
    (bin_ / "notify-send").write_text("#!/bin/sh\necho \"$@\" >> " + str(bin_ / "dymki.txt") + "\n")
    (bin_ / "notify-send").chmod(0o755)
    serwer = socket.socket(socket.AF_UNIX)
    serwer.bind(str(rt / "retronic-pomocnik.sock"))
    serwer.listen(8)
    zapytania = [0]

    def obsluz():
        while True:
            try:
                c, _ = serwer.accept()
            except OSError:
                return
            zapytania[0] += 1
            try:
                c.recv(400)
                c.sendall(b'{"error": "nie widze postaci Dawajkesh (zalogowana?)"}\n')
            finally:
                c.close()
    threading.Thread(target=obsluz, daemon=True).start()
    env = dict(_os.environ, XDG_RUNTIME_DIR=str(rt), PATH=f"{bin_}:{_os.environ['PATH']}", RETRONIC_CZEKAJ_POSTAC_S="4", RETRONIC_POSTAC="Dawajkesh",
               MAPA="raty")
    env.pop("RETRONIC_ID", None)
    t0 = time.time()
    r = subprocess.run(["bash", str(KORZEN / "uruchom.sh")], env=env, capture_output=True, text=True, timeout=60)
    dt = time.time() - t0
    serwer.close()
    sprawdz("E10 uruchom.sh: strażnik nie widzi postaci -> odmowa exit 3 po ~4 s czekania (kilka prób), bez startu bota",
            r.returncode == 3 and 3.0 <= dt <= 15 and zapytania[0] >= 2 and "ODMOWA STARTU" in r.stderr, f"rc={r.returncode} dt={dt:.1f} zapytań={zapytania[0]} stderr={r.stderr[-200:]!r}")
    sprawdz("E11 uruchom.sh: odmowa jest głośna (notify-send critical)", "critical" in (bin_ / "dymki.txt").read_text() if (bin_ / "dymki.txt").exists() else False)
else:
    print("INFO E10/E11 pominięte: RETRONIC_ID ustawione w środowisku testu")

# ------------------------------------------------------------------------------------------------- (F) start po upadku
sprawdz("F0 mozg.start_po_upadku istnieje", hasattr(mozg, "start_po_upadku"))
if hasattr(mozg, "start_po_upadku"):
    PETLA = [(33081, 31742, 9), (33082, 31742, 9), (33083, 31741, 9)]

    class WP:
        def __init__(w):
            w.wywolania = []

        def z_kieszeni(w, poz, teraz):
            w.wywolania.append(tuple(poz))
            return True

    class CB:
        def __init__(c):
            c.wp = WP()

        def _wp(c):
            return c.wp

        def zegar(c):
            return 0.0

    class PP:
        def __init__(p, poz):
            p.poz = poz

        def pozycja(p):
            return p.poz
    logF = []
    # Dawajkesh 23.10: z10 (33084,31743), pętla na z9
    cb = CB()
    r = mozg.start_po_upadku(cb, PP((33084, 31743, 10)), PETLA, logF.append)
    sprawdz("F1 start na z10, pętla na z9 tuż obok: traktowany jak upadek (z_kieszeni wywołane raz z pozycją startu)", r is True and cb.wp.wywolania == [(33084, 31743, 10)],
            f"{r} {cb.wp.wywolania}")
    sprawdz("F2 log wyjaśnia: upadek, piętro startu i pętli", any("z10" in l and "z9" in l and "upad" in l.lower() for l in logF), logF)
    cb = CB()
    r = mozg.start_po_upadku(cb, PP((33084, 31743, 9)), PETLA, logF.append)
    sprawdz("F3 start na piętrze pętli: nic (False)", r is False and not cb.wp.wywolania)
    cb = CB()
    r = mozg.start_po_upadku(cb, PP((33300, 31743, 10)), PETLA, logF.append)
    sprawdz("F4 piętro spoza pętli, ale daleko poziomo (>12 pól): nic (zostaje dojście)", r is False and not cb.wp.wywolania)
    cb = CB()
    r = mozg.start_po_upadku(cb, PP((33084, 31743, 8)), PETLA, logF.append)
    sprawdz("F5 pętla NIŻEJ niż postać (z8 -> z9): to nie upadek, nic", r is False and not cb.wp.wywolania)
    cb = CB()
    cavebot.START_PO_UPADKU = 0
    r = mozg.start_po_upadku(cb, PP((33084, 31743, 10)), PETLA, logF.append)
    cavebot.START_PO_UPADKU = 1
    sprawdz("F6 pokrętło START_PO_UPADKU=0: nic", r is False and not cb.wp.wywolania)
    cb = CB()
    cb.wp.z_kieszeni = lambda poz, teraz: False
    r = mozg.start_po_upadku(cb, PP((33084, 31743, 10)), PETLA, logF.append)
    sprawdz("F7 z_kieszeni odmawia (trasa osiągalna): False, dojście jak dotąd", r is False)


print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
