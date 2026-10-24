"""Wylogowanie bota (23.10, decyzja Karola po resecie serwera: „Boty powinny być wyłączane po wylogowaniu od razu i włączane ponownie”).

Bot, który wykrył rozłączenie / ekran logowania / listę postaci, KOŃCZY PROCES (bez klawiszy, ze stanem zapisanym) i zostawia
w stanie instancji znacznik `wylogowany.json` (czas, powód, mapa i tryb z tryb.log), żeby relog wiedział, co wznowić.
Nie czeka na powrót do gry: relog to pełny restart klienta (sesja_gry zamknij -> start -> zaloguj.sh -> uruchom.sh).

Drugie zadanie modułu: start bota dopiero, gdy strażnik widzi postać (`czekaj_na_postac`). Bez tego `uruchom.sh` zaraz po
`zaloguj.sh` startował bota, który rzucał Traceback „nie widzę postaci … (zalogowana?)” w pierwszej odczytanej pozycji.

Moduł bez zależności od bota i gry (zegar, spanie, ścieżki wstrzykiwane): testy offline. Cienkie CLI dla skryptów:
  python3 -I wylogowanie.py stan <katalog_instancji>     wypisuje znacznik (JSON) albo nic; kod 0 = jest, 1 = brak
  python3 -I wylogowanie.py usun <katalog_instancji>     kasuje znacznik
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

NAZWA = "wylogowany.json"
CZEKAJ_NA_POSTAC_S = 60.0            # ile czekamy, aż strażnik zwróci pozycję postaci po starcie
CZEKAJ_NA_POSTAC_KROK_S = 2.0
RE_TRYB_MAPA = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) \[TRYB\] mapa (\S+?):")
RE_TRYB_TRYB = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) \[TRYB\] tryb (\S*?):")


PROCES = {"powod": None}             # decyzja o wylogowaniu w TYM procesie (cavebot ustawia; dojście i main sprawdzają)
ZRZUTY_POTW = 2                      # tyle kolejnych zrzutów z ekranem logowania (przy błędach odczytu postaci) potwierdza wylogowanie
ZRZUT_MIN_ODSTEP_S = 1.0             # min. odstęp między takimi zrzutami (mozg liczy LIMIT_BLEDOW = 5 błędów w ~1-2 s odstępach)


def ogloszono(powod):
    PROCES["powod"] = str(powod)


def ogloszone():
    """Powód wylogowania ogłoszonego w tym procesie albo None."""
    return PROCES["powod"]


class BrakPostaci:
    """Błędy odczytu postaci (gracz()/pozycja() rzucają: strażnik nie widzi postaci) + zrzut ekranu. Zrzut robimy TYLKO przy
    błędzie (zdrowa gra: koszt 0). `krok(t, zrzut)` -> True, gdy ZRZUTY_POTW kolejnych zrzutów (>= ZRZUT_MIN_ODSTEP_S od siebie)
    pokazało ekran logowania; zrzut False/None zeruje licznik. `ok()` = odczyt się udał."""

    def __init__(self, potw=ZRZUTY_POTW, odstep_s=ZRZUT_MIN_ODSTEP_S):
        self.potw, self.odstep_s = potw, odstep_s
        self.pozytywne = 0
        self.t_zrzut = float("-inf")
        self.od = None

    def ok(self):
        self.pozytywne, self.od = 0, None

    def krok(self, t, zrzut):
        if self.od is None:
            self.od = t
        if t - self.t_zrzut < self.odstep_s:
            return False
        self.t_zrzut = t
        try:
            w = zrzut() if zrzut is not None else None
        except Exception:                              # noqa: BLE001  detekcja nigdy nie wywraca bota
            w = None
        self.pozytywne = self.pozytywne + 1 if w is True else 0
        return self.pozytywne >= self.potw


def plik(stan):
    return Path(stan) / NAZWA


def mapa_tryb_z_logu(tryb_log):
    """(mapa, tryb) z ostatnich wpisów `[TRYB] mapa X:` i `[TRYB] tryb a+b:` w tryb.log (tryb po `+` -> po przecinku, jak nadzor).
    Brak pliku / wpisu = None."""
    mapa = tryb = None
    try:
        tekst = Path(tryb_log).read_text(encoding="utf-8", errors="replace")[-300_000:]
    except OSError:
        return None, None
    for l in tekst.splitlines():
        m = RE_TRYB_MAPA.match(l)
        if m:
            mapa, tryb = m[2], None
            continue
        m = RE_TRYB_TRYB.match(l)
        if m and mapa is not None:
            tryb = ",".join(x for x in m[2].split("+") if x)
    return mapa, tryb


def zapisz(stan, powod, tryb_log=None, poz=None, nick=None, teraz=None, zrodlo="cavebot"):
    """Zapisuje (atomowo: tmp + rename) znacznik wylogowania w katalogu stanu instancji i zwraca słownik. Nie rzuca przy błędzie
    zapisu (zwraca słownik z kluczem `blad`): wyjście z procesu nie może zależeć od dysku."""
    teraz = time.time() if teraz is None else teraz
    mapa, tryb = mapa_tryb_z_logu(tryb_log) if tryb_log else (None, None)
    d = {"czas": datetime.fromtimestamp(teraz).strftime("%Y-%m-%d %H:%M:%S"), "ts": round(teraz, 1), "powod": str(powod),
         "nick": nick, "poz": list(poz[:3]) if poz else None, "mapa": mapa, "tryb": tryb, "pid": os.getpid(), "zrodlo": zrodlo}
    try:
        cel = plik(stan)
        cel.parent.mkdir(parents=True, exist_ok=True)
        tmp = cel.with_name(NAZWA + f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, cel)
    except OSError as e:
        d["blad"] = repr(e)
    return d


def wczytaj(stan):
    """Znacznik jako słownik albo None (brak / uszkodzony)."""
    try:
        d = json.loads(plik(stan).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def usun(stan):
    try:
        plik(stan).unlink()
        return True
    except OSError:
        return False


def czekaj_na_postac(pozycja, limit_s=CZEKAJ_NA_POSTAC_S, krok_s=CZEKAJ_NA_POSTAC_KROK_S, zegar=time.monotonic, spij=time.sleep,
                     log=None, przepusc=()):
    """Czeka (do `limit_s`) aż `pozycja()` zwróci pozycję postaci (strażnik widzi postać). Zwraca pozycję albo None po upływie
    limitu. Wyjątki z `przepusc` (np. bot.Zatrzymano) lecą dalej; każdy inny = „jeszcze nie widzę”. Nigdy Traceback."""
    start = zegar()
    ostatni = None
    proby = 0
    while True:
        proby += 1
        try:
            p = pozycja()
            if p is not None:
                if log and proby > 1:
                    log(f"Start: strażnik widzi postać po {zegar() - start:.0f} s ({proby} prób).")
                return tuple(p)
        except przepusc if przepusc else ():
            raise
        except Exception as e:                     # noqa: BLE001  strażnik jeszcze nie widzi postaci / socket nie odpowiada
            ostatni = e
        if zegar() - start >= limit_s:
            if log:
                log(f"Start: strażnik nie widzi postaci przez {limit_s:.0f} s (ostatni błąd: {ostatni!r}).")
            return None
        if log and proby == 1:
            log(f"Start: czekam do {limit_s:.0f} s, aż strażnik zobaczy postać ({ostatni!r}).")
        spij(krok_s)


def _cli(argv):
    if len(argv) >= 3 and argv[1] in ("stan", "usun"):
        if argv[1] == "usun":
            return 0 if usun(argv[2]) else 1
        d = wczytaj(argv[2])
        if d is None:
            return 1
        print(json.dumps(d, ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
