#!/usr/bin/env python3
"""Strażnik: uruchamia klienta Retronic jako swój proces potomny i udostępnia
odczyt jego pamięci przez gniazdo Unix.

Linux (Yama ptrace_scope=1) pozwala czytać pamięć tylko procesów potomnych.
Updater klienta kończy się po starcie właściwego exe, więc strażnik ustawia
PR_SET_CHILD_SUBREAPER, żeby osierocone procesy gry trafiały do niego, a nie
do systemd --user.

Sama logika odczytu jest w rdzen.py i przeładowuje się po każdej zmianie pliku,
więc poprawki nie wymagają restartu gry.

Użycie: straznik.py <polecenie uruchamiające grę...>
"""

import ctypes
import importlib
import json
import os
import socket
import subprocess
import sys
import threading
import time

KATALOG = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KATALOG)
sys.dont_write_bytecode = True

import instancja  # noqa: E402
import rdzen  # noqa: E402
from proces_gry import ProcesGry  # noqa: E402

GNIAZDO = str(instancja.gniazdo())     # bez RETRONIC_ID: $XDG_RUNTIME_DIR/retronic-pomocnik.sock
LOG = str(instancja.S.straznik_log)    # bez RETRONIC_ID: pomocnik/straznik.log
PR_SET_CHILD_SUBREAPER = 36


def log(tekst):
    with open(LOG, "a") as f:
        f.write(time.strftime("%H:%M:%S ") + tekst + "\n")


class Rdzen:
    """Trzyma moduł rdzen i przeładowuje go, gdy plik się zmieni."""

    def __init__(self):
        self.plik = os.path.join(KATALOG, "rdzen.py")
        self.mtime = os.path.getmtime(self.plik)
        self.stan = {}

    def obsluz(self, zadanie):
        global rdzen
        mtime = os.path.getmtime(self.plik)
        if mtime != self.mtime:
            rdzen = importlib.reload(rdzen)
            self.mtime = mtime
            log("przeładowano rdzen.py")
        return rdzen.obsluz(self.stan, zadanie)


def serwer():
    obsluga = Rdzen()
    if os.path.exists(GNIAZDO):
        os.unlink(GNIAZDO)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(GNIAZDO)
    os.chmod(GNIAZDO, 0o600)
    s.listen(4)
    while True:
        polaczenie, _ = s.accept()
        try:
            with polaczenie, polaczenie.makefile("rwb") as f:
                try:
                    zadanie = json.loads(f.readline())
                    odpowiedz = {"ok": True, **obsluga.obsluz(zadanie)}
                except Exception as e:  # odpowiedź zamiast wywrócenia strażnika
                    odpowiedz = {"ok": False, "blad": f"{type(e).__name__}: {e}"}
                f.write((json.dumps(odpowiedz) + "\n").encode())
                f.flush()
        except OSError as e:  # klient rozłączył się przed odpowiedzią
            log(f"zerwane połączenie: {e}")


def main():
    if len(sys.argv) < 2:
        sys.exit("użycie: straznik.py <polecenie gry...>")
    ctypes.CDLL(None, use_errno=True).prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0)
    log(f"start: {' '.join(sys.argv[1:])}")
    gra = subprocess.Popen(sys.argv[1:])
    threading.Thread(target=serwer, daemon=True).start()

    glowny_zakonczony = False
    puste = 0
    proces_gry = ProcesGry(lambda: rdzen.znajdz_gre())
    while True:
        # zbieranie zakończonych potomków (jesteśmy subreaperem)
        try:
            while True:
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
                if pid == gra.pid:
                    glowny_zakonczony = True
        except ChildProcessError:
            pass
        if glowny_zakonczony or gra.poll() is not None:
            glowny_zakonczony = True
            # Manifest pozwala wdrożyć optymalizację na jednej instancji.
            pid_gry = (proces_gry.sprawdz() if (getattr(rdzen, "CPU_OPTYMALIZACJE", True)
                                             and getattr(rdzen, "CPU_PID", True))
                       else rdzen.znajdz_gre())
            puste = puste + 1 if pid_gry is None else 0
            if puste >= 3:
                break
        time.sleep(1)

    log("gra zamknięta, koniec")
    if os.path.exists(GNIAZDO):
        os.unlink(GNIAZDO)


if __name__ == "__main__":
    main()
