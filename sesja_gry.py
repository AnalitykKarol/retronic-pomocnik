#!/usr/bin/env python3
"""Sesja gry JEDNEJ instancji z okna zarządzania (spec wtyczka-paska/specs/2026-10-19-retronic-okno.md, F4a).

  RETRONIC_ID=<id> sesja_gry.py start     sprawdza profil (profil.sprawdz_unikalnosc: proxy, IP, konto), odmawia przy
                                          działającej sesji, startuje sesja.sh odłączony (setsid) z RETRONIC_POSTAC z profilu;
                                          wyjście sesja.sh dopisywane do instancje/<id>/logi/sesja-RRRRMMDD.log
  RETRONIC_ID=<id> sesja_gry.py zamknij   tylko ta instancja: zatrzymaj.sh (bot), `swaymsg -s <swaysock tej sesji> exit`,
                                          czekanie; awaryjnie TERM strażnika i sway TEJ instancji, `wineserver -k` z jej WINEPREFIX
  RETRONIC_ID=<id> sesja_gry.py podglad   Remmina z profilem ~/.local/share/remmina/retronic-<id>.remmina (brak = tworzony z wzoru);
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
CZEKAJ_TERM_S = 8.0           # po awaryjnym TERM
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
    """Długo żyjący proces (sesja.sh, podglad.sh) w osobnej sesji; wyjście do logu, nie do okna."""
    return subprocess.Popen([str(a) for a in argv], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            env=env or srodowisko(), cwd=str(okno_api.katalog()), start_new_session=True)


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
    with log_akcji() as log:
        log.write(f"=== {time.strftime('%H:%M:%S')} start z okna: {ID} (postać {postac or '?'}, proxy {p.get('proxy')})\n")
        log.flush()
        proc = odlacz([okno_api.katalog() / "sesja.sh"], log, env)
    koniec = time.monotonic() + CZEKAJ_START_S
    while time.monotonic() < koniec:
        sleep(KROK_S)
        if stan()["sesja"]:
            print(f"sesja {ID} wystartowała: gra sprawdza IP proxy (do ~30 s), potem zaloguj postać {postac or ''} w podglądzie")
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
        kroki.append("sway: exit" if kod == 0 else f"swaymsg kod {kod} ({wyj})")
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


def profil_remminy(port):
    """-> (ścieżka profilu, tytuł okna). Brak profilu (np. nowa instancja) = tworzony z wzoru; istniejący zostaje."""
    plik = katalog_remminy() / f"retronic-{ID}.remmina"
    if not plik.exists():
        plik.parent.mkdir(parents=True, exist_ok=True)
        plik.write_text(REMMINA_WZOR.format(id=ID, port=port))
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
    plik, tytul = profil_remminy(port)
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
