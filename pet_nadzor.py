"""Nadzór nad petem od przywołania: zapis stanu co kilka minut i powrót do UH po przywołaniu.

  python3 -I -u pet_nadzor.py [--co 240] [--ile 3.0]

Co `--co` sekund zapisuje jedną linię do logi/pet-nadzor.jsonl: poziom, exp, HP, manę, pozycję gracza,
stan peta (id, HP, odległość), ustawienie UH i ilość przywołań z logów peta. Gdy w logach peta pojawi się
zdarzenie "przywolany" (po starcie nadzoru), ustawia UH_AKTYWNY=1 w na_zywo.json, bo po przywołaniu
wracamy do run UH. Kopia na_zywo.json robiona raz przed pierwszą zmianą.

Tylko odczyt gry (gniazdo straznika) i zapis konfiguracji. Nie wysyła nic do gry. Kończy się po --ile godzin,
po SIGTERM albo po zniknięciu procesu bota (mozg.py). Nie zabija bota.
"""
import argparse
import glob
import json
import os
import shutil
import signal
import socket
import sys
import time
from pathlib import Path

KATALOG = Path(__file__).resolve().parent
sys.path.insert(0, str(KATALOG))
import instancja  # noqa: E402
import pet  # noqa: E402

NA_ZYWO = KATALOG / "na_zywo.json"
STOP = False


def _zapytaj(cmd, **kw):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect(str(instancja.gniazdo()))
        s.sendall((json.dumps({"cmd": cmd, **kw}) + "\n").encode())
        dane = b""
        while not dane.endswith(b"\n"):
            kawalek = s.recv(65536)
            if not kawalek:
                break
            dane += kawalek
    return json.loads(dane.decode())


def _bot_zyje():
    return os.system("pgrep -f 'mozg.py' >/dev/null 2>&1") == 0


def _logi_peta(logi):
    """Najnowszy plik pet-*.jsonl w katalogu logów instancji."""
    # pet-nadzor.jsonl to zapis tego nadzoru, nie log peta (sortuje się za datami, więc trzeba go pominąć)
    pliki = sorted(p for p in glob.glob(os.path.join(logi, "pet-*.jsonl")) if not p.endswith("pet-nadzor.jsonl"))
    # plik, do którego bot pisze teraz (po wznowieniu peta to plik pierwszego przywołania, nie najnowszy z nazwy)
    return max(pliki, key=os.path.getmtime) if pliki else None


def _przywolania(plik, od_t):
    """Liczba zdarzeń 'przywolany' w pliku peta, po czasie od_t (sekundy od epoki)."""
    if not plik or not os.path.exists(plik):
        return 0, None
    n = 0
    ostatni = None
    for linia in open(plik, encoding="utf-8"):
        try:
            w = json.loads(linia)
        except ValueError:
            continue
        if w.get("zdarzenie") == "przywolany" and w.get("t", 0) >= od_t:
            n += 1
            ostatni = w
    return n, ostatni


def _ustaw_uh(wlaczone):
    """Ustawia UH_AKTYWNY w na_zywo.json (kopia raz, przed pierwszą zmianą)."""
    kopia = NA_ZYWO.with_name("na_zywo.json.przed_nadzorem_peta_1017")
    if not kopia.exists():
        shutil.copy2(NA_ZYWO, kopia)
    d = json.loads(NA_ZYWO.read_text(encoding="utf-8"))
    if d.get("UH_AKTYWNY") == int(wlaczone):
        return False
    d["UH_AKTYWNY"] = int(wlaczone)
    tmp = NA_ZYWO.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, NA_ZYWO)
    return True


def _obsluz_sygnal(_sig, _ramka):
    global STOP
    STOP = True


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--co", type=float, default=240.0, help="sekund między zapisami (3-5 min = 180-300)")
    p.add_argument("--ile", type=float, default=3.0, help="godzin działania nadzoru")
    a = p.parse_args(argv)
    signal.signal(signal.SIGTERM, _obsluz_sygnal)
    signal.signal(signal.SIGINT, _obsluz_sygnal)

    logi = str(instancja.S.logi)
    os.makedirs(logi, exist_ok=True)
    wyjscie = os.path.join(logi, "pet-nadzor.jsonl")
    start = time.time()
    koniec = start + a.ile * 3600
    uh_wlaczone_przez_nadzor = False

    def zapisz(wpis):
        with open(wyjscie, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": round(time.time(), 1), **wpis}, ensure_ascii=False) + "\n")

    zapisz({"zdarzenie": "start", "co_s": a.co, "ile_h": a.ile})
    while not STOP and time.time() < koniec:
        if not _bot_zyje():
            zapisz({"zdarzenie": "koniec_bota"})
            break
        try:
            gracz = _zapytaj("gracz").get("gracz", {})
            stwory = pet.stwory_z_gniazda()
        except (OSError, ValueError) as e:
            zapisz({"zdarzenie": "blad_odczytu", "blad": str(e)})
            time.sleep(a.co)
            continue
        plik = _logi_peta(logi)
        n_przyw, _ = _przywolania(plik, start)
        # ostatnie przywołanie z całego pliku dnia: pet mógł być przywołany przed startem nadzoru (17.10 22:38)
        _, ostatnie = _przywolania(plik, 0)
        if ostatnie and not uh_wlaczone_przez_nadzor:
            zmieniono = _ustaw_uh(True)
            uh_wlaczone_przez_nadzor = True
            zapisz({"zdarzenie": "przywolany_wracam_do_uh", "przywolanie": ostatnie, "uh_zmieniono": zmieniono})
        pet_id = ostatnie.get("pet_id") if ostatnie else None
        pet_stan = pet.stan_peta(stwory, pet_id) if pet_id else None
        cfg = json.loads(NA_ZYWO.read_text(encoding="utf-8"))
        zapisz({
            "zdarzenie": "stan",
            "gracz": gracz,
            "pet_id": pet_id,
            "pet": pet_stan,
            "przywolan_od_startu": n_przyw,
            "UH_AKTYWNY": cfg.get("UH_AKTYWNY"),
            "PET_WLACZONY": cfg.get("PET_WLACZONY"),
        })
        time.sleep(a.co)
    zapisz({"zdarzenie": "koniec_nadzoru", "powod": "sygnal" if STOP else "czas_lub_bot"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
