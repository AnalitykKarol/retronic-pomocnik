#!/usr/bin/env python3
"""Sesja gry JEDNEJ instancji z okna zarządzania (spec wtyczka-paska/specs/2026-10-19-retronic-okno.md, F4a).

  RETRONIC_ID=<id> sesja_gry.py start     sprawdza profil (profil.sprawdz_unikalnosc: proxy, IP, konto), odmawia przy
                                          działającej sesji, startuje sesja.sh odłączony (setsid) z RETRONIC_POSTAC z profilu;
                                          wyjście sesja.sh dopisywane do instancje/<id>/logi/sesja-RRRRMMDD.log
  RETRONIC_ID=<id> sesja_gry.py zamknij   tylko ta instancja: zatrzymaj.sh (bot), `swaymsg -s <swaysock tej sesji> exit`,
                                          czekanie; awaryjnie TERM strażnika i sway TEJ instancji, `wineserver -k` z jej WINEPREFIX
  RETRONIC_ID=<id> sesja_gry.py podglad   Remmina z profilem ~/.local/share/remmina/retronic-<id>.remmina (brak = tworzony z wzoru;
                                          istniejący: tylko linia server= jest poprawiana, gdy port sesji jest inny, a jeśli okno
                                          tej instancji jest wtedy otwarte, najpierw jest zamykane, bo Remmina nadpisuje profil);
                                          otwarty = fokus na jego okno (`hyprctl dispatch 'hl.dsp.focus({ window = "address:…" })'`,
                                          składnia Lua od Hyprland 0.56), niepowodzenie fokusu = komunikat, kod 0

Nigdy nie rusza innych instancji (w odróżnieniu od zamknij_sesje.sh, który zamyka wszystko): sway wybierany po ścieżce
sway.conf tej sesji, strażnik po RETRONIC_ID w środowisku procesu (okno_api.skan_procesow). Główna instancja (pusty
RETRONIC_ID): odmowa, ona startuje po staremu (retronic.sh / sesja.sh). Proxy i profil tylko do odczytu (D-F4-1).
Wynik: tekst dla okna, kod 0 = zrobione, 1 = odmowa albo błąd, 2 = złe użycie.
"""
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

ID = os.environ.get("RETRONIC_ID", "").strip()
sys.path.insert(0, str(Path(__file__).resolve().parent))
import okno_api  # noqa: E402  (zdejmuje RETRONIC_ID z os.environ; ID mamy wyżej)
import instancja  # noqa: E402

CZEKAJ_START_S = 8.0          # tyle czekamy, aż wstanie sway nowej sesji (gra i proxy dalej startują same)
CZEKAJ_ZAMKNIECIE_S = 25.0    # po `swaymsg exit`: gra traci Xwayland i kończy się, strażnik i sieć proxy za nią
CZEKAJ_TERM_S = 8.0
CZEKAJ_PODGLAD_S = 10.0       # po wstaniu sway: tyle czekamy, aż wayvnc zacznie słuchać, zanim otworzymy Remminę           # po awaryjnym TERM
CZEKAJ_OKNO_S = 5.0           # po zamknięciu okna Remminy (zmiana portu podglądu): tyle czekamy, aż zniknie, zanim ruszymy profil
KROK_S = 0.5

# punkty podmiany dla testów (testy/test_sesja_gry.py)
sleep = time.sleep
zabij = os.kill


class Odmowa(Exception):
    pass


def stan():
    return okno_api.cmd_sesja(ID)


def zyje(s):
    """Czy cokolwiek z sesji tej instancji jeszcze działa (sway, strażnik/klient, siec_proxy.sh, sesja.sh)."""
    return bool(s["sesja"] or s["klient_pids"] or s["proxy_pids"] or s["sesja_sh_pids"])


def opis(s):
    return f"sway {s['sway_pids']}, klient {s['klient_pids']}, proxy {s['proxy_pids']}, sesja.sh {s['sesja_sh_pids']}"


def srodowisko():
    """RETRONIC_ID i WINEPREFIX tej instancji (prefiks z okno_api.sciezki: ten sam katalog danych co odczyt stanu)."""
    env = instancja.srodowisko(ID, bazowe=os.environ)
    env["WINEPREFIX"] = str(okno_api.sciezki(ID).prefix)
    return env


def uruchom(argv, limit):
    """Krótkie polecenie, czekamy na koniec. -> (kod, ostatnie linie wyjścia)."""
    try:
        r = subprocess.run([str(a) for a in argv], capture_output=True, timeout=limit, env=srodowisko(),
                           cwd=str(okno_api.katalog()), stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return 124, f"przekroczony limit {limit:g} s"
    except OSError as e:
        return 127, str(e)
    wyj = (r.stdout + r.stderr).decode(errors="replace").strip().splitlines()
    return r.returncode, " | ".join(wyj[-3:])


def odlacz(argv, log, env=None):
    """Długo żyjący proces (sesja.sh, Remmina) w osobnej sesji; wyjście do logu, nie do okna.
    26.10: we własnej jednostce systemd (w_scope.sh; rodzaj: podglad dla Remminy, sesja dla reszty), nie w cgroupie okna: restart okna (retronic-okno.service)
    zabijał wszystkie sesje gry. Wrapper robi exec: ten sam PID i cmdline, zamknięcie dalej szuka procesów po /proc."""
    env = env or srodowisko()
    rodzaj = "podglad" if os.path.basename(str(argv[0])) == "remmina" else "sesja"
    return subprocess.Popen(instancja.w_scope(rodzaj, argv, env), stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            env=env, cwd=str(okno_api.katalog()), start_new_session=True)


def log_akcji():
    sc = okno_api.sciezki(ID)
    Path(sc.logi).mkdir(parents=True, exist_ok=True)
    return open(Path(sc.logi) / time.strftime("sesja-%Y%m%d.log"), "a", encoding="utf-8")


def inne_sesje():
    """{id: [pidy sway]} pozostałych instancji: kontrola, że zamknięcie ich nie ruszyło."""
    return {i: sorted(p["sway"]) for i, p in okno_api.skan_procesow().items() if i != ID and p["sway"]}


# ---------- akcje ----------
def start():
    # blokada: podwójne kliknięcie nie wystartuje dwóch sesja.sh, zanim pierwszy postawi sway
    Path(okno_api.sciezki(ID).stan).mkdir(parents=True, exist_ok=True)
    with open(Path(okno_api.sciezki(ID).stan) / "sesja_start.lock", "a") as zamek:
        try:
            fcntl.flock(zamek, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Odmowa(f"start {ID} już trwa (inne kliknięcie)")
        return _start()


def _start():
    s = stan()
    if zyje(s):
        raise Odmowa(f"sesja {ID} już działa ({opis(s)})")
    p = s["profil"] or {}
    if not p.get("start_mozliwy"):
        raise Odmowa(f"start wstrzymany: {p.get('blad') or 'profil instancji nie przechodzi kontroli'}")
    postac = p.get("postac") or ""          # tylko z profilu (stały profil instancji), nie ze środowiska okna
    env = srodowisko()
    env.pop("RETRONIC_POSTAC", None)
    if postac:
        env["RETRONIC_POSTAC"] = postac
    env["RETRONIC_PODGLAD"] = "0"           # bez automatycznego TigerVNC z sesja.sh: podgląd = Remmina (niżej), jak okna Karola
    with log_akcji() as log:
        log.write(f"=== {time.strftime('%H:%M:%S')} start z okna: {ID} (postać {postac or '?'}, proxy {p.get('proxy')})\n")
        log.flush()
        proc = odlacz([okno_api.katalog() / "sesja.sh"], log, env)
    koniec = time.monotonic() + CZEKAJ_START_S
    while time.monotonic() < koniec:
        sleep(KROK_S)
        if stan()["sesja"]:
            print(f"sesja {ID} wystartowała: gra sprawdza IP proxy (do ~30 s), potem zaloguj postać {postac or ''} w podglądzie; "
                  + otworz_remmine_po_starcie())
            return 0
        kod = proc.poll()
        if kod is not None:
            ogon = okno_api.ogon(log.name, 3)
            raise Odmowa(f"sesja.sh zakończył się od razu (kod {kod}): {' | '.join(ogon)}")
    kod = proc.poll()
    if kod is not None:
        raise Odmowa(f"sesja.sh zakończył się (kod {kod}) bez sesji sway: {' | '.join(okno_api.ogon(log.name, 3))}")
    print(f"sesja.sh {ID} działa, sway jeszcze nie wstał (po {CZEKAJ_START_S:g} s); stan odświeży się w oknie")
    return 0


def otworz_remmine_po_starcie():
    """Po wstaniu sway: czeka, aż wayvnc zacznie słuchać (wcześniej Remmina dostaje „VNC connection timed out”), i otwiera
    podgląd Remmina tej instancji. -> krótki opis do komunikatu akcji."""
    koniec = time.monotonic() + CZEKAJ_PODGLAD_S
    proc = os.environ.get("RETRONIC_OKNO_PROC") or "/proc"
    while time.monotonic() < koniec:
        port = stan()["podglad"]["port"]
        if port is not None and instancja.port_nasluchuje(port, proc):
            try:
                plik, _ = przygotuj_profil_podgladu(port)
            except Odmowa as e:
                return str(e)
            with log_akcji() as log:
                log.write(f"=== {time.strftime('%H:%M:%S')} podgląd po starcie: remmina {plik.name} (port {port})\n")
                log.flush()
                odlacz(["remmina", "--disable-toolbar", "-c", plik], log)
            return f"podgląd Remmina otwiera się (port {port})"
        sleep(KROK_S)
    return "podgląd jeszcze niegotowy (wayvnc nie słucha): otwórz go później klikiem w nick"


def czekaj_na_koniec(limit):
    koniec = time.monotonic() + limit
    while True:
        s = stan()
        if not zyje(s):
            return s
        if time.monotonic() >= koniec:
            return s
        sleep(KROK_S)


def zamknij():
    s = stan()
    if not s["mozna_zamknac"]:
        print(f"gra {ID} nie działa, nie ma czego zamykać")
        return 0
    inne_przed = inne_sesje()
    kroki = []
    if s["bot"]:
        kod, wyj = uruchom([okno_api.katalog() / "zatrzymaj.sh"], 30)
        kroki.append("bot zatrzymany" if kod == 0 else f"zatrzymaj.sh kod {kod} ({wyj})")
    sock = ""
    try:
        sock = (Path(okno_api.sciezki(ID).sesja) / "swaysock").read_text().strip()
    except OSError:
        pass
    # gniazdo z pliku sesji tylko, gdy należy do żywego sway TEJ sesji (nazwa sway-ipc.<uid>.<pid>.sock)
    if sock and not any(f".{pid}." in Path(sock).name for pid in s["sway_pids"]):
        sock = ""
    if s["sesja"] and sock:
        kod, wyj = uruchom(["swaymsg", "-s", sock, "exit"], 10)
        # sway kończy się, zanim odpowie: "Unable to receive IPC response" z kodem 1 to też udane exit (zmierzone 20.10 na żywo)
        udane = kod == 0 or (kod == 1 and "Unable to receive IPC response" in wyj)
        kroki.append("sway: exit" if udane else f"swaymsg kod {kod} ({wyj})")
    s = czekaj_na_koniec(CZEKAJ_ZAMKNIECIE_S if kroki and kroki[-1] == "sway: exit" else 0)
    if zyje(s):
        # wyłącznie procesy tej instancji (strażnik i siec_proxy.sh po RETRONIC_ID, sway po ścieżce sesji);
        # sesja.sh kończy się sam po wyjściu sway
        pidy = list(s["klient_pids"]) + list(s["proxy_pids"]) + list(s["sway_pids"])
        for pid in pidy:
            try:
                zabij(pid, signal.SIGTERM)
            except OSError:
                pass
        kroki.append(f"awaryjnie TERM {pidy}")
        s = czekaj_na_koniec(CZEKAJ_TERM_S)
    kod, wyj = uruchom(["wineserver", "-k"], 15)                    # WINEPREFIX tej instancji (srodowisko())
    if kod not in (0, 1):
        kroki.append(f"wineserver -k kod {kod} ({wyj})")
    s = stan()
    inne_po = inne_sesje()
    zniknely = sorted(i for i in inne_przed if i not in inne_po)   # tylko informacja: zamykanie ich nie dotyka
    if not zyje(s) and zamknij_okno_podgladu():
        kroki.append("podgląd Remmina zamknięty")
    if zyje(s):
        raise Odmowa(f"gra {ID} nie zamknęła się: {opis(s)} ({'; '.join(kroki)})")
    uwaga = f"; UWAGA: w tym czasie skończyły się też sesje {zniknely}" if zniknely else ""
    print(f"gra {ID} zamknięta ({'; '.join(kroki) or 'bez kroków'}); inne sesje: {len(inne_po)}{uwaga}")
    return 0


REMMINA_KLASA = "org.remmina.Remmina"
# profil Remminy jak w narzedzia/remmina_podglad.sh: obraz skalowany do okna, ekran gry (bot) bez zmian
REMMINA_WZOR = """[remmina]
name=Retronic {id}
group=Retronic {id}
protocol=VNC
server=127.0.0.1:{port}
scale=1
quality=9
colordepth=32
viewonly=0
disableclipboard=0
showcursor=0
disableencryption=0
disabletoolbar=1
keymap=Retronic Alt
"""


def katalog_remminy():
    return Path(os.environ.get("RETRONIC_REMMINA_KATALOG") or Path.home() / ".local/share/remmina")


SERWER_WZOR = re.compile(r"^(server=)(.*?)(:(\d+))?\s*$")


def port_w_profilu(plik):
    """Port z linii server= profilu Remminy (host:port) albo None (brak pliku/linii/portu)."""
    try:
        for linia in Path(plik).read_text(errors="replace").splitlines():
            if linia.startswith("server="):
                m = SERWER_WZOR.match(linia)
                return int(m[4]) if m and m[4] else None
    except OSError:
        pass
    return None


def popraw_serwer_profilu(plik, port):
    """Ustawia server=127.0.0.1:<port> w istniejącym profilu, gdy port się różni; reszta pliku bez zmian (kolejność, końcowy
    newline). Brak linii server= = dopisana na końcu. -> czy plik zmieniono. Zapis przez plik tymczasowy + replace."""
    plik = Path(plik)
    tekst = plik.read_text(errors="replace")
    nowa = f"server=127.0.0.1:{port}"
    linie = tekst.split("\n")
    idx = next((i for i, l in enumerate(linie) if l.startswith("server=")), None)
    if idx is None:
        koniec = tekst.endswith("\n") or not tekst
        wynik = tekst + ("" if koniec else "\n") + nowa + "\n"
    else:
        if port_w_profilu(plik) == port:
            return False
        linie[idx] = nowa
        wynik = "\n".join(linie)
    tmp = plik.with_name(plik.name + ".tmp")
    tmp.write_text(wynik)
    os.replace(tmp, plik)
    return True


def profil_remminy(port):
    """-> (ścieżka profilu, tytuł okna). Brak profilu (np. nowa instancja) = tworzony z wzoru. Istniejący zostaje, poza linią
    server=: gdy port sesji jest inny (kolizja portów 23.10, ręczny RETRONIC_PODGLAD_PORT), server= jest poprawiane.
    Uwaga: Remmina przy zamykaniu okna zapisuje swój server= z powrotem, więc przy otwartym oknie tej instancji wołaj to
    DOPIERO po jego zamknięciu (podglad() tak robi)."""
    plik = katalog_remminy() / f"retronic-{ID}.remmina"
    if not plik.exists():
        plik.parent.mkdir(parents=True, exist_ok=True)
        plik.write_text(REMMINA_WZOR.format(id=ID, port=port))
    else:
        popraw_serwer_profilu(plik, port)
    tytul = f"Retronic {ID}"
    for linia in plik.read_text(errors="replace").splitlines():
        if linia.startswith("name="):
            tytul = linia[5:].strip() or tytul
    return plik, tytul


def klienci_hyprland():
    """hyprctl clients -j (lista okien); błąd = []."""
    try:
        r = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, timeout=5, stdin=subprocess.DEVNULL)
        d = json.loads(r.stdout)
        return d if isinstance(d, list) else []
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []


def fokus(selektor):
    """-> (udany, opis). Hyprland 0.56 (Lua): brak okna = kod 0 i "warning: … window not found" (zmierzone 20.10)."""
    kod, wyj = uruchom(["hyprctl", "dispatch", f'hl.dsp.focus({{ window = "{selektor}" }})'], 5)
    nieudany = re.search(r"not found|^error|^warning", wyj.strip(), re.I | re.M)
    return kod == 0 and not nieudany, f"hyprctl kod {kod}: {wyj or 'brak odpowiedzi'}"


def okno_podgladu():
    """Okno Remmina tej instancji (tytuł = name= z jej profilu) albo None. Nie tworzy profilu."""
    plik = katalog_remminy() / f"retronic-{ID}.remmina"
    tytul = f"Retronic {ID}"
    try:
        for linia in plik.read_text(errors="replace").splitlines():
            if linia.startswith("name="):
                tytul = linia[5:].strip() or tytul
    except OSError:
        pass
    return next((k for k in klienci_hyprland() if k.get("title") == tytul and k.get("class") == REMMINA_KLASA), None)


def zamknij_okno_podgladu():
    """Po zamknięciu gry: okno Remmina tej instancji (po zerwanym VNC) zamykane po adresie. -> czy było co zamknąć."""
    okno = okno_podgladu()
    if okno is None:
        return False
    uruchom(["hyprctl", "dispatch", f'hl.dsp.window.close({{ window = "address:{okno.get("address")}" }})'], 5)
    return True


def zamknij_okno_i_poczekaj(okno):
    """Zamyka okno Remminy po adresie i czeka (do CZEKAJ_OKNO_S), aż zniknie z hyprctl clients. -> czy zniknęło."""
    adres = okno.get("address")
    uruchom(["hyprctl", "dispatch", f'hl.dsp.window.close({{ window = "address:{adres}" }})'], 5)
    koniec = time.monotonic() + CZEKAJ_OKNO_S
    while True:
        if not any(k.get("address") == adres for k in klienci_hyprland()):
            return True
        if time.monotonic() >= koniec:
            return False
        sleep(KROK_S)


def przygotuj_profil_podgladu(port):
    """Profil Remminy tej instancji z server=127.0.0.1:<port> -> (ścieżka, tytuł okna). Gdy profil ma inny port, a okno tej
    instancji jest otwarte (pokazuje starą albo cudzą sesję), KOLEJNOŚĆ jest ważna, bo Remmina przy zamykaniu okna zapisuje
    swój server= do profilu: najpierw zamknięcie okna i czekanie aż zniknie, dopiero potem poprawka profilu. Okno, które nie
    zniknęło w CZEKAJ_OKNO_S = Odmowa, profil nietknięty."""
    stary_port = port_w_profilu(katalog_remminy() / f"retronic-{ID}.remmina")
    okno = okno_podgladu()
    if okno is not None and stary_port is not None and stary_port != port:
        if not zamknij_okno_i_poczekaj(okno):
            raise Odmowa(f"podgląd {ID} otwarty na porcie {stary_port}, a sesja ma port {port}: okno nie zamknęło się "
                         f"w {CZEKAJ_OKNO_S:g} s, profil Remminy bez zmian (zamknij okno ręcznie i powtórz)")
        print(f"podgląd {ID}: okno na starym porcie {stary_port} zamknięte, profil poprawiony na {port}")
    return profil_remminy(port)


def podglad():
    """Q1/Q2 (spec 2026-10-20-retronic-lvl-i-podglad.md): podgląd w Remminie, jak okna Karola (decyzja 20.10 ~19:00,
    „ustaw tak jak było na invincible”). Otwarty = fokus na jego okno; zamknięty = remmina -c profil instancji.
    Bez vncviewera i dopasuj_okno.py (to zmieniało rozmiar ekranu sesji gry)."""
    s = stan()
    if not s["sesja"]:
        raise Odmowa(f"gra {ID} nie działa (brak sesji), nie ma czego podglądać")
    port = s["podglad"]["port"]
    if port is None:
        raise Odmowa(f"sesja {ID} nie ma jeszcze portu podglądu (wayvnc wstaje), spróbuj za chwilę")
    plik, tytul = przygotuj_profil_podgladu(port)
    okno = next((k for k in klienci_hyprland() if k.get("title") == tytul and k.get("class") == REMMINA_KLASA), None)
    if okno is None and s["podglad"].get("pid"):           # stary podgląd vncviewer tej instancji
        okno = next((k for k in klienci_hyprland() if k.get("pid") == s["podglad"]["pid"]), None)
    if okno is not None:
        ok, opis = fokus(f"address:{okno.get('address')}")
        print(f"podgląd {ID} już otwarty: fokus na okno" if ok else f"podgląd {ID} już otwarty, ale fokus się nie udał ({opis})")
        return 0
    with log_akcji() as log:
        log.write(f"=== {time.strftime('%H:%M:%S')} podgląd z okna: remmina {plik.name} (port {port})\n")
        log.flush()
        odlacz(["remmina", "--disable-toolbar", "-c", plik], log)
    print(f"podgląd {ID} otwiera się w Remminie (port {port})")
    return 0


AKCJE = {"start": start, "zamknij": zamknij, "podglad": podglad}


def main(argv=None):
    a = sys.argv[1:] if argv is None else argv
    if len(a) != 1 or a[0] not in AKCJE:
        print("użycie: RETRONIC_ID=<id> sesja_gry.py start|zamknij|podglad", file=sys.stderr)
        return 2
    global ID
    try:
        ID = okno_api.normalizuj_id(ID)              # "główna" -> "" (odmowa niżej)
        if not ID:
            print("główna instancja: sesji nie uruchamia ani nie zamyka okno (retronic.sh / sesja.sh ręcznie)")
            return 1
        return AKCJE[a[0]]()
    except (Odmowa, okno_api.Blad) as e:
        print(getattr(e, "komunikat", None) or str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
