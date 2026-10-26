#!/usr/bin/env python3
"""Powiadomienia o wiadomościach do postaci (22.10, Karol: kutangen sprzedaje HMM ręcznie, „niech tylko powiadomienia mi
wysyła, jak ktoś napisze”). TYLKO ODCZYT: co ODSWIEZ_S pyta strażnika instancji (komenda "wiadomosci", bez skanu) i dla
nowych wpisów od innych graczy daje dymek `notify-send`. Nic nie klika i nic nie pisze w grze.

Kanały: strażnik nie zawsze przypisuje bufor do zakładki (u kutangena wszystko ma kanal=None), więc Trade rozpoznajemy po
treści: bufor, w którym większość wpisów to ogłoszenia (sell/buy), uznajemy za Trade i pomijamy. Server Log pomijamy po
nazwie. Dymek PILNY (critical) dostaje to, co wygląda na rozmowę z nami: wiadomość prywatna (kolor jasnoniebieski klienta,
zakładka inna niż Default), wisper („Nick whispers: …”), a przy nieznanym kanale także każdy kolor inny niż żółty (mowa
lokalna/Trade = ffff00). Czat obok (Default, żółty) = dymek zwykły. 26.10: autor bywa tylko w tekście („Nick [lvl]: …”,
wtedy strażnik daje nadawca=None), więc czytamy go stamtąd; dawniej taki wisper był pomijany jako „bez nadawcy”.

Trwały zapis: KAŻDA wiadomość prywatna/wisper/obok idzie do logu (czas, rodzaj, nick, pełna treść), bo klient gry nie zapisuje
historii rozmów na dysk (22.10 → 26.10 wisper przepadł razem z tekstem).

Start automatyczny (26.10): sesja.sh woła `powiadom_czat.py --uruchom`; gdy profil.json instancji ma "powiadom_czat": true
i czytnik tej instancji jeszcze nie działa (po /proc: cmdline + RETRONIC_ID), startuje go odłączonego (setsid). Drugi start
= „już działa”. Czytnik sam pilnuje jednego egzemplarza (flock w katalogu runtime).

Uproszczenie (Karol 26.10, kutangen tylko powiadamia, nie sprzedaje): z `"okienka": false` w handel.json trade_logger tylko
ZAPISUJE rozmowy (handel/priv.jsonl), a ten czytnik daje jedyny alert na każdą wiadomość (priv, wisper, czat obok) i wpis w logu.
Poniższa współpraca dotyczy tylko handel.json BEZ tego klucza (okienka trade_loggera włączone).

Współpraca z trybem handlu (trade_logger.py, instancje/<id>/handel.json): trade_logger już daje okienko (critical, "Retronic
handel") przy wiadomości z nadawcą w kolorze 5ff7f7. Gdy jego proces tej instancji żyje, ten czytnik NIE dubluje dymku dla
dokładnie tych wiadomości (w logu dopisek „[dymek: trade_logger]”), ale zapisuje je do swojego logu i dymi wszystko, czego
trade_logger nie rozpoznaje: wisper „Nick whispers: …”, „Nick [lvl]: …” bez nadawcy, priv w innym kolorze, zakładka z nickiem,
czat obok. Gdy trade_logger padnie, czytnik od razu przejmuje także wiadomości 5ff7f7 (sprawdzenie co 10 s). Jedyny wyjątek od
„jeden alert na wiadomość”: trade_logger sam ucisza kolejne priv od tego samego nicka na 60 s (CISZA_PRIV); treść zostaje w obu logach.
`--uruchom` startuje też trade_logger.py, gdy instancja ma handel.json (ten sam mechanizm: /proc + RETRONIC_ID, setsid).

Samonaprawa: zerwane połączenie / brak gniazda strażnika (restart klienta) = pętla ponowień co PONOW_S, w logu linia
„przerwa …” i „wznowione po N s”; nieoczekiwany wyjątek też tylko trafia do logu i pętla trwa. Brak strażnika dłużej niż
MAX_BRAK_S (1 h) kończy czytnik (sesja.sh wystartuje go znowu). Czytnik startowany przez --uruchom kończy się też, gdy ktoś
zdejmie flagę z profilu.

Użycie:  RETRONIC_ID=kutangen python3 -I powiadom_czat.py             (na pierwszym planie; w tle: setsid nohup ... &)
         RETRONIC_ID=kutangen python3 -I powiadom_czat.py --uruchom   (jak sesja.sh: start w tle, jeśli flaga w profilu)
Log:     instancje/<id>/logi/powiadom-czat-RRRRMMDD.log (wiadomości), powiadom-czat-stdout.log (wyjście procesu).
Wyłączenie: "powiadom_czat": false w instancje/<id>/profil.json i kill czytnika (ps: `python3 -I …/powiadom_czat.py`).
Zmienne (testy): RETRONIC_POWIADOM_KATALOG (zamiast katalogu pomocnika), RETRONIC_POWIADOM_NOTIFY (zamiast notify-send),
RETRONIC_POWIADOM_ODSWIEZ_S, RETRONIC_POWIADOM_PONOW_S, RETRONIC_POWIADOM_MAX_BRAK_S.
"""
import fcntl
import json
import os
import re
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import instancja  # noqa: E402

ODSWIEZ_S = float(os.environ.get("RETRONIC_POWIADOM_ODSWIEZ_S", "3.0"))
PONOW_S = float(os.environ.get("RETRONIC_POWIADOM_PONOW_S", "10.0"))
MAX_BRAK_S = float(os.environ.get("RETRONIC_POWIADOM_MAX_BRAK_S", "3600"))
PRZYPOMNIJ_PRZERWE_S = 300.0                        # w długiej przerwie linia „nadal brak” co 5 min
SPRAWDZ_FLAGE_S = 30.0
ZALEGLE_S = 900                                     # po starcie czytnika: prywatne z ostatnich 15 min, jeszcze nie w logu
OGLOSZENIE = re.compile(r"\b(sell|buy|wts|wtb|trade)\b|/bp|k/|>>|<<", re.I)
KOLORY_PRIV = {"5ff7f7", "9f9dfd"}                  # OTClient: prywatna od gracza / wisper (jasnoniebieski)
KOLOR_ZOLTY = "ffff00"                              # mowa lokalna i kanały (Trade)
MIN_WPISOW_TRADE = 3
SPRAWDZ_TL_S = 10.0                                 # jak często sprawdzamy, czy trade_logger tej instancji żyje
IGNOROWANE_KANALY = ("server log", "trade", "game-chat", "help", "advertising", "npcs")
SYSTEMOWE = ("You ", "Loot of", "Monster loot", "Welcome ", "Your ", "Warning", "Server ")
# autor tylko w tekście: „Nick [45]: …” (mowa lokalna z poziomem) albo „Nick whispers: …”
_NICK = r"([A-Za-z][A-Za-z0-9 '\-.]{0,29}?)"
AUTOR_LVL = re.compile(_NICK + r" \[\d{1,4}\]: ")
AUTOR_CZASOWNIK = re.compile(_NICK + r" (whispers|says|yells): ")
WISPER_W_NICKU = re.compile(r"^(.+?) whispers$")    # strażnik potrafi wziąć „Nick whispers” za nadawcę


def zapytaj(gniazdo, z):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as so:
        so.settimeout(3)
        so.connect(str(gniazdo))
        so.sendall((json.dumps(z) + "\n").encode())
        return json.loads(so.makefile("rb").readline())


class Bufory:
    """Statystyka buforów czatu: ile wpisów, ile ogłoszeń; bufor z przewagą ogłoszeń = Trade."""

    def __init__(self):
        self.n, self.ogl = {}, {}

    def dodaj(self, bufor, tekst):
        self.n[bufor] = self.n.get(bufor, 0) + 1
        self.ogl[bufor] = self.ogl.get(bufor, 0) + bool(OGLOSZENIE.search(tekst or ""))

    def trade(self, bufor):
        n = self.n.get(bufor, 0)
        return n >= MIN_WPISOW_TRADE and self.ogl.get(bufor, 0) / n >= 0.6


def autor_wiadomosci(w):
    """(autor, czy_wisper): z pola nadawca/autor, a gdy puste, z początku tekstu „Nick [lvl]: …” / „Nick whispers: …”.
    Z samego tekstu tylko przy [lvl] albo czasowniku (inaczej „Loot of a rat: …” byłoby graczem)."""
    a = (w.get("nadawca") or w.get("autor") or "").strip()
    if a:
        m = WISPER_W_NICKU.match(a)
        return (m.group(1), True) if m else (a, False)
    t = (w.get("tekst") or "").strip()
    if not t or t.startswith(SYSTEMOWE):
        return "", False
    m = AUTOR_LVL.match(t)
    if m:
        return m.group(1).strip(), False
    m = AUTOR_CZASOWNIK.match(t)
    if m:
        return m.group(1).strip(), m.group(2) == "whispers"
    return "", False


def rodzaj(w, bufory, nazwy_kanalow, ja):
    """None = pomiń, inaczej "priv" (pilny) albo "obok"."""
    autor, wisper = autor_wiadomosci(w)
    if not autor or autor.lower() == ja.lower():
        return None
    kanal = (w.get("kanal") or nazwy_kanalow.get(w.get("bufor")) or "").lower()
    if kanal in IGNOROWANE_KANALY:
        return None
    kolor = (w.get("kolor") or "").lower()
    if kolor in KOLORY_PRIV or wisper:
        return "priv"
    if bufory.trade(w.get("bufor")):
        # w buforze ogłoszeń zostaje tylko to, co nie wygląda na ogłoszenie i ma kolor inny niż żółty kanału
        if kolor and kolor != KOLOR_ZOLTY and not OGLOSZENIE.search(w.get("tekst") or ""):
            return "priv"
        return None
    if kanal and kanal not in ("default",):
        return "priv"                               # nazwana zakładka inna niż Default = rozmowa prywatna
    if kolor and kolor != KOLOR_ZOLTY:
        return "priv"                               # nieznany kanał, kolor spoza mowy lokalnej = wisper/priv o nietypowym kolorze
    return "obok"


# ---------------------------------------------------------------------------------------------
# start automatyczny

def profil_wlaczony(stan):
    try:
        return json.loads((Path(stan) / "profil.json").read_text()).get("powiadom_czat") is True
    except (OSError, ValueError, AttributeError):
        return False


def czytniki(id_, proc="/proc"):
    """Pidy działających czytników tej instancji (cmdline + RETRONIC_ID); starter `--uruchom` się nie liczy."""
    return instancja.procesy(r"powiadom_czat\.py(?! --uruchom)", id_=id_, proc=proc)


def trade_loggery(id_, proc="/proc"):
    return instancja.procesy(r"trade_logger\.py", id_=id_, proc=proc)


def _wystartuj(nazwa, skrypt, plik_wyjscia, id_, s, katalog, dziala, popen, env_dod=None):
    if dziala:
        return f"{nazwa}: już działa (pid {dziala[0]})"
    s.logi.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, RETRONIC_ID=id_, **(env_dod or {}))
    with open(s.logi / plik_wyjscia, "ab") as out:
        p = popen([sys.executable, "-I", str(skrypt)], env=env, stdin=subprocess.DEVNULL,
                  stdout=out, stderr=out, start_new_session=True, cwd=str(s.katalog))
    return f"{nazwa}: wystartowany (pid {p.pid})"


def uruchom(id_, katalog=None, runtime_dir=None, proc="/proc", popen=subprocess.Popen, skrypt_tl=None):
    """Idempotentny start usług instancji w tle: czytnik powiadomień (flaga "powiadom_czat": true w profilu) i trade_logger
    (jest instancje/<id>/handel.json). Zwraca zdania po polsku (po jednym na usługę); nigdy nie rzuca (best effort dla sesja.sh)."""
    if not id_:
        return "powiadom_czat: brak RETRONIC_ID (główna instancja nieobsługiwana)"
    wyniki = []
    try:
        s = instancja.sciezki(id_, runtime_dir or instancja.runtime(f"/run/user/{os.getuid()}"),
                              katalog or instancja.KATALOG)
        if profil_wlaczony(s.stan):
            env_dod = {"RETRONIC_POWIADOM_AUTO": "1"}
            if katalog:
                env_dod["RETRONIC_POWIADOM_KATALOG"] = str(katalog)
            wyniki.append(_wystartuj("powiadom_czat", os.path.abspath(__file__), "powiadom-czat-stdout.log", id_, s,
                                     katalog, czytniki(id_, proc), popen, env_dod))
        else:
            wyniki.append(f"powiadom_czat: wyłączony w profilu {id_} (brak \"powiadom_czat\": true)")
    except Exception as e:  # noqa: BLE001 - start sesji nie może przez to paść
        wyniki.append(f"powiadom_czat: błąd startu: {type(e).__name__}: {e}")
    try:
        s = instancja.sciezki(id_, runtime_dir or instancja.runtime(f"/run/user/{os.getuid()}"),
                              katalog or instancja.KATALOG)
        if (s.stan / "handel.json").exists():
            tl = skrypt_tl or Path(os.path.abspath(__file__)).with_name("trade_logger.py")
            wyniki.append(_wystartuj("trade_logger", tl, "trade-logger-stdout.log", id_, s, katalog,
                                     trade_loggery(id_, proc), popen))
        else:
            wyniki.append(f"trade_logger: bez handel.json w instancji {id_}, nie startuję")
    except Exception as e:  # noqa: BLE001
        wyniki.append(f"trade_logger: błąd startu: {type(e).__name__}: {e}")
    return "\n".join(wyniki)


def nick_handlu(stan):
    """Nick z handel.json (tak trade_logger rozpoznaje własne wiadomości), gdy trade_logger daje okienka; None, gdy nie ma
    handel.json albo ma "okienka": false (wtedy trade_logger tylko zapisuje, a WSZYSTKIE alerty daje ten czytnik)."""
    try:
        k = json.loads((Path(stan) / "handel.json").read_text())
        return None if k.get("okienka") is False else (k.get("nick") or "")
    except (OSError, ValueError, AttributeError):
        return None


def trade_logger_obejmuje(w, nick):
    """Odzwierciedla trade_logger.rodzaj(m, nick) == "priv": nadawca z pola, nie własny, kolor 5ff7f7 (test pilnuje zgodności)."""
    nadawca = w.get("nadawca")
    return bool(nadawca) and nadawca != nick and (w.get("kolor") or "").lower() == "5ff7f7"


# ---------------------------------------------------------------------------------------------
# czytnik

def dymek(komenda, pilny, tytul, tresc):
    try:
        subprocess.run([*komenda.split(), "-u", "critical" if pilny else "normal", "-a", "Retronic sklep",
                        tytul, tresc[:200]], check=False, timeout=15)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def linie_pliku(plik):
    try:
        return Path(plik).read_text(errors="replace").splitlines()
    except OSError:
        return []


def petla(s, ja, zegar=time.time, spij=time.sleep, notify=None, auto=False, limit_obiegow=None, tl_zyje=None):
    """Główna pętla czytnika. limit_obiegow tylko dla testów (None = bez końca). Zwraca przyczynę zakończenia."""
    notify = notify or os.environ.get("RETRONIC_POWIADOM_NOTIFY", "notify-send")
    logi = Path(s.logi)
    logi.mkdir(parents=True, exist_ok=True)

    def plik_logu():
        return logi / f"powiadom-czat-{time.strftime('%Y%m%d')}.log"

    def log(t):
        with open(plik_logu(), "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {t}\n")

    if tl_zyje is None:
        tl_zyje = lambda: bool(trade_loggery(s.id))   # noqa: E731
    nick_tl = nick_handlu(s.stan)                     # None = instancja bez handel.json: trade_logger nie alarmuje
    tl_stan, tl_sprawdzony = False, None
    bufory, nr, epoka = Bufory(), None, None
    przerwa_od = przypomniano = None
    ostatni_blad = None
    flaga_sprawdzona = zegar()
    obiegi = 0
    log(f"start: {ja} ({s.id}), gniazdo {s.gniazdo}{' [auto]' if auto else ''}")
    while True:
        obiegi += 1
        if limit_obiegow is not None and obiegi > limit_obiegow:
            return "limit"
        blad = None
        try:
            z = {"cmd": "wiadomosci", "limit": 100}
            if nr is not None:
                z.update(od=nr, epoka=epoka)
            try:
                odp = zapytaj(s.gniazdo, z)
                if not odp.get("ok"):
                    blad = f"strażnik odpowiedział błędem: {odp.get('blad')}"
            except (OSError, ValueError) as e:
                blad = f"{type(e).__name__}: {e}"
            teraz = zegar()
            if blad:
                if przerwa_od is None:
                    przerwa_od = przypomniano = teraz
                    log(f"przerwa: {blad}")
                elif teraz - przypomniano >= PRZYPOMNIJ_PRZERWE_S:
                    przypomniano = teraz
                    log(f"przerwa trwa {int(teraz - przerwa_od)} s: {blad}")
                if MAX_BRAK_S and teraz - przerwa_od > MAX_BRAK_S:
                    log(f"koniec: brak strażnika przez {int(teraz - przerwa_od)} s (sesja.sh uruchomi czytnik ponownie)")
                    return "brak-strażnika"
                if auto and not profil_wlaczony(s.stan):
                    log("koniec: flaga powiadom_czat zdjęta z profilu")
                    return "flaga"
                spij(PONOW_S)
                continue
            if przerwa_od is not None:
                log(f"wznowione po {int(teraz - przerwa_od)} s przerwy (epoka {odp.get('epoka')})")
                przerwa_od = None
            ostatni_blad = None
            if auto and teraz - flaga_sprawdzona >= SPRAWDZ_FLAGE_S:
                flaga_sprawdzona = teraz
                if not profil_wlaczony(s.stan):
                    log("koniec: flaga powiadom_czat zdjęta z profilu")
                    return "flaga"
            nazwy = {k: v for k, v in (odp.get("kanaly") or {}).items()}
            start = nr is None
            pierwszy = start or odp.get("epoka") != epoka
            nr, epoka = odp.get("znacznik"), odp.get("epoka")
            dzis = None
            for w in odp.get("wiadomosci", []):
                r = rodzaj(w, bufory, nazwy, ja)          # ocena przed dodaniem: pierwsze wpisy nowego bufora nie są „Trade”
                bufory.dodaj(w.get("bufor"), w.get("tekst"))
                if r is None:
                    continue
                autor, wisper = autor_wiadomosci(w)
                tekst = " / ".join((w.get("tekst") or "").strip().splitlines())
                zalegla = False
                if pierwszy:
                    # historia bufora przy starcie: nic nie dymimy, poza prywatnymi sprzed chwili (czytnik padł, wisper
                    # mógł przyjść w przerwie), których nie ma jeszcze w dzisiejszym logu; po restarcie klienta (nowa epoka)
                    # bufory są puste, więc nie ma czego odzyskiwać
                    ts = w.get("ts")
                    if not (start and r == "priv" and ts and teraz - ts <= ZALEGLE_S):
                        continue
                    if dzis is None:
                        dzis = linie_pliku(plik_logu())
                    if any(l.endswith(f" {autor}: {tekst}") for l in dzis):
                        continue
                    zalegla = True
                znacznik = ("WISPER" if wisper else "priv") if r == "priv" else "obok"
                if nick_tl is not None and (tl_sprawdzony is None or teraz - tl_sprawdzony >= SPRAWDZ_TL_S):
                    tl_stan, tl_sprawdzony = tl_zyje(), teraz
                pokryta = r == "priv" and nick_tl is not None and tl_stan and trade_logger_obejmuje(w, nick_tl)
                log(f"{znacznik}{'*' if zalegla else ''} {autor}: {tekst}{' [dymek: trade_logger]' if pokryta else ''}")
                if pokryta:
                    continue                          # okienko da trade_logger; my tylko zapis
                if r == "priv":
                    tytul = f"{ja}: {'WISPER' if wisper else 'prywatna'} od {autor}{' (zaległa)' if zalegla else ''}"
                else:
                    tytul = f"{ja}: czat obok od {autor}"
                if not dymek(notify, r == "priv", tytul, f"{autor}: {tekst}"):
                    log(f"UWAGA: dymek nie wyszedł ({notify}); wiadomość jest w logu powyżej")
        except Exception as e:  # noqa: BLE001 - czytnik nie może paść od jednej dziwnej wiadomości
            opis = f"{type(e).__name__}: {e}"
            if opis != ostatni_blad:
                ostatni_blad = opis
                log(f"BŁĄD w pętli (czytnik trwa): {opis}")
            spij(PONOW_S)
            continue
        spij(ODSWIEZ_S)


def main():
    id_ = os.environ.get("RETRONIC_ID")
    if not id_:
        sys.exit("ustaw RETRONIC_ID (np. kutangen)")
    katalog = os.environ.get("RETRONIC_POWIADOM_KATALOG") or instancja.KATALOG
    rt = instancja.runtime(f"/run/user/{os.getuid()}")
    if "--uruchom" in sys.argv[1:]:
        print(uruchom(id_, katalog, rt))
        return
    s = instancja.sciezki(id_, rt, katalog)
    # jeden czytnik na instancję: flock (obok kontroli po /proc w --uruchom, która nie widzi wyścigu dwóch startów naraz)
    blokada = open(Path(rt) / f"retronic-powiadom-czat-{id_}.lock", "w")
    try:
        fcntl.flock(blokada, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(f"powiadom_czat {id_}: już działa (blokada)")
    if "DBUS_SESSION_BUS_ADDRESS" not in os.environ and Path(rt, "bus").exists():
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={rt}/bus"
    ja = id_.capitalize()
    try:
        ja = json.loads((s.stan / "profil.json").read_text()).get("postac") or ja
    except (OSError, ValueError):
        pass
    petla(s, ja, auto=os.environ.get("RETRONIC_POWIADOM_AUTO") == "1")


if __name__ == "__main__":
    main()
