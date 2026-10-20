#!/usr/bin/env python3
"""Auto-refill po powrocie do depo (20.10, pokrętło WROC_REFILL=1).

Bot, który dochodzi do depo w „Wróć do miasta” (wroc.sh) albo w wyprawie tylko-do-depo, zapisuje STOP i staje. Z tego STOP-u
wyprawa.py (`_zakoncz_depo`) woła `zlec()`: gdy miasto ma plan serwisu (trasy/serwis_<miasto>.json obsługiwane przez serwis.py)
i nic innego nie trwa, rusza odłączony „czekacz” (`refill_auto.py czekaj`). Czekacz czeka, aż proces bota tej instancji zniknie
(refill.sh odmawia przy działającym bocie), sprawdza jeszcze raz STOP_RECZNY / serwis, zwalnia wejście i wykonuje
`refill.sh --tlo` (jedzenie, backpack, blanki, wyjście, potem start bota na spot; log `refill.log`).

Pierwszeństwo ma człowiek: STOP_RECZNY (guzik Stop, zatrzymaj.sh, refill.sh --przerwij) = bez auto-refillu. Anulowanie:
`refill_auto.py anuluj` (woła je `wroc.sh --anuluj` i `refill.sh --przerwij`). Decyzje i powody w pliku stanu instancji
`wroc_refill.json` ({"stan": czeka|uruchomiony|pominiety|brak_planu, "powod", "t"}); czyta go `panel.py --json` (pole wroc_refill).

  python3 -I refill_auto.py czekaj    czekacz (uruchamiany przez bota, nie ręcznie)
  python3 -I refill_auto.py anuluj    ubija czekacza tej instancji (jeśli jest), zapisuje powód
"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
KATALOG = Path(__file__).resolve().parent
sys.path.insert(0, str(KATALOG))
import instancja  # noqa: E402

TRASY = KATALOG / "trasy"
PLIK = "wroc_refill.json"
MIASTA_SERWISU = ("edron",)                             # miasta, które serwis.py umie obsłużyć (jego argparse: choices)
WZOR_BOT = r"(mozg|cavebot)\.py"
WZOR_SERWIS = r"(^|[ /])serwis\.py "
WZOR_REFILL = r"^(\S*/)?bash (\S*/)?refill\.sh *$"
WZOR_CZEKACZ = r"(^|[ /])refill_auto\.py czekaj"
CZEKAJ_NA_BOTA_S = 60.0                                  # tyle czekacz czeka, aż bot zniknie po STOP (potem rezygnuje, niczego nie ubija)


def sciezka_stanu(stan_dir):
    return Path(stan_dir) / PLIK


def czytaj_stan(stan_dir):
    try:
        d = json.loads(sciezka_stanu(stan_dir).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def zapisz_stan(stan_dir, stan, powod="", teraz=time.time):
    """Atomowy zapis decyzji (czyta ją panel). Błąd zapisu nie przerywa niczego."""
    p = sciezka_stanu(stan_dir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(PLIK + ".tmp")
        tmp.write_text(json.dumps({"stan": stan, "powod": powod, "t": round(teraz(), 1)}, ensure_ascii=False))
        os.replace(tmp, p)
    except OSError:
        pass
    return stan, powod


def miasto_serwisu(poz, katalog=TRASY):
    """(miasto, w_depo): miasto z planem serwisu, w którym stoi `poz` (None, gdy takiego nie ma), i czy stoimy przy depo.
    Źródło prawdy to to samo, co w panelu („w_miescie”): prostokąt punktów trasy/serwis_<miasto>.json."""
    try:
        import panel  # noqa: PLC0415
        miasto, w_depo = panel.miasto_pozycji(tuple(poz), panel.dane_serwisu(katalog))
    except Exception:
        return None, False
    return (miasto, w_depo) if miasto in MIASTA_SERWISU else (None, False)


def trwa_serwis(procesy=None):
    """Serwis, praca refill.sh albo czekacz tej instancji już działają."""
    procesy = procesy or instancja.procesy
    return bool(procesy(WZOR_SERWIS) or procesy(WZOR_REFILL, comm=None) or procesy(WZOR_CZEKACZ))


def start_czekacza():
    """Odłączony czekacz (własna sesja: przeżywa bota, który zaraz wychodzi po STOP). Dziedziczy RETRONIC_ID bota."""
    return subprocess.Popen([sys.executable, "-I", str(KATALOG / "refill_auto.py"), "czekaj"], cwd=str(KATALOG),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)


def zlec(poz, stan_dir, katalog=TRASY, start=start_czekacza, procesy=None):
    """Decyzja przy STOP w depo (woła ją bot). -> (stan, powód); `start()` tylko wtedy, gdy stan == "czeka".
    brak_planu = miasto bez planu serwisu (np. Thais): nic się nie dzieje poza wpisem w logu, panelu i dymku."""
    stan_dir = Path(stan_dir)
    if (stan_dir / "STOP_RECZNY").exists():
        return zapisz_stan(stan_dir, "pominiety", "ręczny stop (STOP_RECZNY) ma pierwszeństwo")
    miasto, w_depo = miasto_serwisu(poz, katalog)
    if miasto is None:
        return zapisz_stan(stan_dir, "brak_planu",
                           f"brak planu serwisu dla tego miasta (pozycja {tuple(poz)}); serwis ma: {', '.join(MIASTA_SERWISU)}")
    if not w_depo:
        return zapisz_stan(stan_dir, "pominiety", f"postać nie stoi przy depo {miasto} (pozycja {tuple(poz)})")
    if trwa_serwis(procesy):
        return zapisz_stan(stan_dir, "pominiety", "serwis albo refill już trwa")
    try:
        start()
    except Exception as e:                                # noqa: BLE001
        return zapisz_stan(stan_dir, "pominiety", f"nie udało się uruchomić czekacza: {e!r}")
    return zapisz_stan(stan_dir, "czeka", f"refill {miasto} ruszy po zatrzymaniu bota")


def czekaj(stan_dir=None, katalog=KATALOG, czekaj_s=CZEKAJ_NA_BOTA_S, procesy=None, uruchom=subprocess.run,
           spij=time.sleep, zegar=time.monotonic):
    """Czekacz: bot zniknął -> ponowna kontrola STOP_RECZNY i serwisu -> zwolnienie wejścia -> refill.sh --tlo. -> kod wyjścia."""
    stan_dir = Path(stan_dir or instancja.S.stan)
    katalog = Path(katalog)
    procesy = procesy or instancja.procesy
    zapisz_stan(stan_dir, "czeka", "czekam na zatrzymanie bota")
    t0 = zegar()
    while procesy(WZOR_BOT):
        if zegar() - t0 > czekaj_s:
            zapisz_stan(stan_dir, "pominiety", f"bot nie zatrzymał się w {czekaj_s:.0f} s po STOP")
            return 1
        spij(0.5)
    if (stan_dir / "STOP_RECZNY").exists():
        zapisz_stan(stan_dir, "pominiety", "ręczny stop (STOP_RECZNY) ma pierwszeństwo")
        return 0
    if procesy(WZOR_SERWIS) or procesy(WZOR_REFILL, comm=None):
        zapisz_stan(stan_dir, "pominiety", "serwis albo refill już trwa")
        return 0
    try:                                                   # bot mógł wyjść z wciśniętym klawiszem; brak gry = cicho
        uruchom([sys.executable, "-I", str(katalog / "zwolnij_wejscie.py")], timeout=20, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        r = uruchom(["bash", str(katalog / "refill.sh"), "--tlo"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        zapisz_stan(stan_dir, "pominiety", f"refill.sh nie wystartował: {e!r}")
        return 1
    if r.returncode != 0:
        wyj = (r.stderr or r.stdout or "").strip().splitlines()
        zapisz_stan(stan_dir, "pominiety", "refill.sh odmówił: " + (wyj[-1] if wyj else f"kod {r.returncode}"))
        return r.returncode
    zapisz_stan(stan_dir, "uruchomiony", "refill.sh --tlo")
    return 0


def anuluj(stan_dir=None, procesy=None, zabij=os.kill):
    """Ubija czekacza tej instancji (jeśli jest) i zapisuje powód. -> liczba ubitych."""
    stan_dir = Path(stan_dir or instancja.S.stan)
    pidy = (procesy or instancja.procesy)(WZOR_CZEKACZ)
    for p in pidy:
        try:
            zabij(p, signal.SIGTERM)
        except OSError:
            pass
    if pidy:
        zapisz_stan(stan_dir, "pominiety", "anulowane (wroc.sh --anuluj albo refill.sh --przerwij)")
    return len(pidy)


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if a == ["czekaj"]:
        return czekaj()
    if a == ["anuluj"]:
        n = anuluj()
        print("auto-refill anulowany" if n else "brak oczekującego auto-refillu")
        return 0
    print("użycie: refill_auto.py czekaj | anuluj", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
