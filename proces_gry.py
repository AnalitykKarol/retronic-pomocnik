"""Tania kontrola tożsamości gry; odkrywanie potomków należy do callbacku."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Tozsamosc:
    pid: int
    starttime: int
    cmdline: bytes
    exe: str | None


def _stat(katalog):
    # comm może zawierać spacje i nawiasy; starttime to pole 22 (ogon od 3).
    pola = (katalog / "stat").read_text().rsplit(")", 1)[1].split()
    if pola[0] in ("Z", "X", "x"):
        raise ValueError("proces zakończony")
    return int(pola[19])


def odczytaj_tozsamosc(pid, proc=Path("/proc")):
    """None przy utracie/braku dostępu; niedostępne exe nie blokuje Wine."""
    katalog = Path(proc) / str(pid)
    try:
        starttime = _stat(katalog)
        cmdline = (katalog / "cmdline").read_bytes()
        cmd = cmdline.decode(errors="replace").lower()
        if "retronic" not in cmd or ".exe" not in cmd or "straznik" in cmd:
            return None
        try:
            exe = os.readlink(katalog / "exe")
        except OSError:
            exe = None
        if _stat(katalog) != starttime:
            return None
        return Tozsamosc(pid, starttime, cmdline, exe)
    except (OSError, IndexError, ValueError):
        return None


class ProcesGry:
    """Pełne odkrywanie tylko na początku i po utracie znanej tożsamości.

    Dokładne argumenty i exe wykrywają także exec z zachowaniem PID/starttime.
    Gdy exe chwilowo nie da się odczytać, zachowujemy ostatnią znaną wartość.
    """

    def __init__(self, znajdz_gre, *, odczytaj=odczytaj_tozsamosc):
        self._znajdz_gre = znajdz_gre
        self._odczytaj = odczytaj
        self._znany = None

    def sprawdz(self):
        znany = self._znany
        if znany is not None:
            teraz = self._odczytaj(znany.pid)
            if (teraz is not None
                    and teraz.starttime == znany.starttime
                    and teraz.cmdline == znany.cmdline
                    and (teraz.exe is None or znany.exe is None
                         or teraz.exe == znany.exe)):
                if teraz.exe is not None:
                    self._znany = teraz
                return znany.pid
        self._znany = None
        pid = self._znajdz_gre()
        if pid is not None:
            self._znany = self._odczytaj(pid)
        return self._znany.pid if self._znany is not None else None
