"""Głosowe alarmy: "<nick> pomocy, <powód>" (Piper, polski głos offline) zamiast dźwięku systemowego.

mow(powod) nigdy nie rzuca wyjątku i nie blokuje bota (generowanie i odtwarzanie idą w osobnym wątku).
Frazy są cache'owane jako wav w ~/.cache/retronic-glos, więc powtórzony alarm gra od razu.
Nick = RETRONIC_ID (postać instancji). Wyłączniki jak w powiadom.py: RETRONIC_POWIADOMIENIA=0 albo plik pomocnik/cisza;
RETRONIC_GLOS=0 albo plik pomocnik/glos_wylaczony (./glos.sh) wyłącza sam głos. Zwraca True, gdy głos poszedł do odtworzenia (False = wywołujący może użyć dawnego dźwięku).
Tylko stdlib; model: RETRONIC_GLOS_MODEL (domyślnie ~/.local/share/piper-glosy/pl_PL-gosia-medium.onnx)."""
import hashlib
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

KATALOG = Path(__file__).resolve().parent
CACHE = Path.home() / ".cache" / "retronic-glos"
MODEL = Path(os.environ.get("RETRONIC_GLOS_MODEL") or Path.home() / ".local/share/piper-glosy/pl_PL-gosia-medium.onnx")
POWOD_MAX = 90
WYLACZNIK = KATALOG / "glos_wylaczony"   # plik = głos wyłączony (toggle: ./glos.sh), sprawdzany przy każdym alarmie
TEN_SAM_S = 20            # s: ta sama fraza nie częściej
GENEROWANIE_S = 30
_ostatnie = {}
_blokada = threading.Lock()   # jedna fraza naraz w tym procesie


def _piper():
    return shutil.which("piper") or str(Path.home() / ".local/bin/piper")


def dostepny():
    return MODEL.exists() and (shutil.which("piper") or (Path.home() / ".local/bin/piper").exists()) \
        and bool(shutil.which("paplay"))


def wylaczony():
    if os.environ.get("RETRONIC_TESTY") or os.environ.get("RETRONIC_GLOS", "").strip() == "0":
        return True
    if os.environ.get("RETRONIC_POWIADOMIENIA", "").strip() == "0":
        return True
    try:
        return (KATALOG / "cisza").exists() or WYLACZNIK.exists()
    except OSError:
        return True


def nick():
    return (os.environ.get("RETRONIC_ID") or os.environ.get("RETRONIC_POSTAC") or "bot").strip() or "bot"


def fraza(powod, kto=None):
    """'<nick> pomocy, <powód>' bez znaków, które TTS czyta literowo (nawiasy, strzałki, długie liczby)."""
    powod = re.sub(r"^\s*ALARM:?\s*", "", str(powod or ""), flags=re.I)
    powod = re.sub(r"[\[\](){}<>_=|\\/*#~^`\"]+", " ", powod)
    powod = re.sub(r"\s+", " ", powod).strip(" .,:;-")[:POWOD_MAX].strip()
    return f"{kto or nick()} pomocy" + (f", {powod}" if powod else "")


def _wav(tekst):
    CACHE.mkdir(parents=True, exist_ok=True)
    plik = CACHE / (hashlib.sha1(f"{MODEL.name}|{tekst}".encode()).hexdigest()[:16] + ".wav")
    if plik.exists() and plik.stat().st_size > 1000:
        return plik
    tmp = plik.with_suffix(f".{os.getpid()}.tmp.wav")
    subprocess.run([_piper(), "-m", str(MODEL), "-f", str(tmp)], input=tekst.encode(),
                   capture_output=True, timeout=GENEROWANIE_S, check=True)
    os.replace(tmp, plik)
    return plik


def _graj(tekst):
    try:
        with _blokada:
            subprocess.run(["paplay", str(_wav(tekst))], capture_output=True, timeout=15)
    except Exception:
        pass


def mow(powod, kto=None):
    """Mówi 'nick pomocy, powód' w tle. True = poszło do odtworzenia."""
    try:
        if wylaczony() or not dostepny():
            return False
        tekst = fraza(powod, kto)
        t = time.monotonic()
        if t - _ostatnie.get(tekst, float("-inf")) < TEN_SAM_S:
            return True            # ta sama fraza przed chwilą: nie powtarzamy, ale też nie wołamy starego dźwięku
        _ostatnie[tekst] = t
        threading.Thread(target=_graj, args=(tekst,), daemon=True).start()
        return True
    except Exception:
        return False
