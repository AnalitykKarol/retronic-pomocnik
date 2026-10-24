#!/usr/bin/env python3
"""Magic level i procent do następnego ML z pamięci klienta (tylko odczyt), zapis do `instancje/<id>/ostatnie.json`.

Skąd: blok statystyk gracza (`rdzen.POLA_GRACZA`, doubles f8; adres zwraca strażnik w polu `adres` odpowiedzi `gracz`) ma za polem
`max_mana` (+0x40) kolejne pola OTClient `LocalPlayer`: +0x48 magic level, +0x50 procent do następnego ML (0-100), +0x58 bazowy ML
(bez bonusów z przedmiotów). Ustalone 22.10 (odchyd, układ) i potwierdzone 23.10 na 6 żywych klientach (ML 0, 1, 6, 11, 14, 14; bazowy
= ML, procent 0-100; `dane_tibia/ml_pamiec_1022/NOTATKI.txt`, `STAN.md` 23.10). Zero zmian w `rdzen.py`: odczyt to istniejące polecenie
strażnika `hexdump` pod adresem bloku z `gracz`.

Pisarze `ostatnie.json` (pola ml, ml_proc, ml_t, ml_zrodlo = "pamiec"):
  - bot: `ostatnie.Pisarz.tik(..., zapytaj=cb.zapytaj)` co `ostatnie.ML_CO_S` s (po restarcie bota),
  - ten plik (odczyt jednorazowy / pętla, bez restartu botów; nie rusza `zapisano` ani `zrodlo`, więc wiek danych bota się nie zmienia):

  python3 -I ml_zywo.py --sucho [--instancja ID ...]        wydruk odczytu, zero zapisów
  python3 -I ml_zywo.py [--instancja ID ...]                odczyt i zapis ml/ml_proc/ml_t/ml_zrodlo (instancje z działającym strażnikiem)
  python3 -I ml_zywo.py --petla 30 [--instancja ID ...]     to samo co 30 s do SIGTERM/Ctrl+C

Tylko stdlib. Nic stąd nie rzuca wyjątku do wołającego (błąd odczytu = None, nic nie zapisano)."""
import argparse
import json
import math
import os
import socket
import struct
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
KORZEN = Path(__file__).resolve().parent
if str(KORZEN) not in sys.path:         # `python3 -I` nie dodaje katalogu skryptu
    sys.path.insert(0, str(KORZEN))

OFFSET_ML = 0x48
OFFSET_ML_PROC = 0x50
OFFSET_ML_BAZA = 0x58
DLUGOSC = 0x60              # od początku bloku gracza do końca bazowego ML (12 doubles)
ZRODLO = "pamiec"
LIMIT_ML = 999              # jak ostatnie.ml_ustaw
TIMEOUT_S = 5.0


def _liczba(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _calkowite(x):
    return math.isfinite(x) and x == math.floor(x)


def parsuj(bufor, g=None):
    """Bajty bloku gracza (>= DLUGOSC) -> {"ml": int, "ml_proc": float, "ml_baza": int} albo None.
    Walidacja chroni przed zapisem śmieci, gdy blok się przesunął: hp <= max_hp, level całkowity 1-2000 (i równy `g["level"]`, jeśli
    podano), ML całkowity 0-999, procent 0-100, bazowy ML całkowity 0-999."""
    try:
        if not isinstance(bufor, (bytes, bytearray)) or len(bufor) < DLUGOSC:
            return None
        v = struct.unpack_from("<12d", bytes(bufor), 0)
        if not all(math.isfinite(x) for x in v):
            return None
        hp, max_hp, level = v[0], v[1], v[5]
        if not (0 <= hp <= max_hp) or not (_calkowite(level) and 1 <= level <= 2000):
            return None
        if isinstance(g, dict) and _liczba(g.get("level")) and int(g["level"]) != int(level):
            return None
        ml, proc, baza = v[OFFSET_ML // 8], v[OFFSET_ML_PROC // 8], v[OFFSET_ML_BAZA // 8]
        if not (_calkowite(ml) and 0 <= ml <= LIMIT_ML) or not (_calkowite(baza) and 0 <= baza <= LIMIT_ML):
            return None
        if not (0 <= proc <= 100):
            return None
        return {"ml": int(ml), "ml_proc": round(float(proc), 1), "ml_baza": int(baza)}
    except Exception:       # noqa: BLE001
        return None


def odczytaj(zapytaj, g):
    """`zapytaj({"cmd": ...}) -> dict` (strażnik), `g` = odpowiedź `gracz` z polem `adres` -> wynik `parsuj` albo None. Nie rzuca."""
    try:
        adres = g.get("adres") if isinstance(g, dict) else None
        if not isinstance(adres, str):
            return None
        int(adres, 16)
        odp = zapytaj({"cmd": "hexdump", "adres": adres, "dlugosc": DLUGOSC})
        return parsuj(bytes.fromhex(odp["hex"]), g)
    except Exception:       # noqa: BLE001
        return None


def odczytaj_z_gracza(zapytaj):
    """-> (g, wynik): `gracz` i odczyt ML spod jego adresu. Błąd = (None albo g, None). Nie rzuca."""
    try:
        g = zapytaj({"cmd": "gracz"})["gracz"]
    except Exception:       # noqa: BLE001
        return None, None
    return g, odczytaj(zapytaj, g)


def zapisz(katalog, wynik, t=None):
    """Zapis TYLKO ml, ml_proc, ml_t, ml_zrodlo do ostatnie.json. `zapisano` i `zrodlo` istniejącego pliku zostają (odczyt zewnętrzny nie
    udaje świeżych danych bota). -> zapisany obiekt albo None (zły wynik / blokada / błąd)."""
    import ostatnie  # noqa: PLC0415  (ostatnie importuje ten moduł; tu import leniwy)
    try:
        if not isinstance(wynik, dict) or isinstance(wynik.get("ml"), bool) or not isinstance(wynik.get("ml"), int) \
                or not 0 <= wynik["ml"] <= LIMIT_ML or not _liczba(wynik.get("ml_proc")) or not 0 <= wynik["ml_proc"] <= 100:
            return None
        t = time.time() if t is None else t
        return ostatnie.zapisz(katalog, "bot", {"ml": wynik["ml"], "ml_proc": round(float(wynik["ml_proc"]), 1),
                                                "ml_t": round(t, 1), "ml_zrodlo": ZRODLO}, t=t, znacznik=False)
    except Exception:       # noqa: BLE001
        return None


def odswiez_instancje(katalog, zapytaj, t=None, sucho=False):
    """Jeden odczyt + zapis dla instancji. -> {"ml", "ml_proc", "ml_baza"} (zapisane albo, przy `sucho`, odczytane) albo None."""
    g, wynik = odczytaj_z_gracza(zapytaj)
    if wynik is None:
        return None
    if sucho:
        return wynik
    return wynik if zapisz(katalog, wynik, t=t) is not None else None


# ---------- CLI ----------
def zapytaj_gniazdo(sciezka):
    """Klient gniazda strażnika (ten sam protokół co bot._zapytaj_surowe: linia JSON, odpowiedź z polem `ok`)."""
    def zapytaj(zadanie):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT_S)
            s.connect(str(sciezka))
            s.sendall((json.dumps(zadanie) + "\n").encode())
            odp = json.loads(s.makefile("rb").readline())
        if not odp.pop("ok", False):
            raise RuntimeError(odp.get("blad"))
        return odp
    return zapytaj


def instancje(korzen=KORZEN):
    kat = Path(korzen) / "instancje"
    return sorted(p.name for p in kat.iterdir() if p.is_dir() and not p.name.startswith("_")) if kat.is_dir() else []


def przebieg(ids, korzen=KORZEN, sucho=False, runtime=None, wypisz=print):
    """Jeden przebieg po instancjach z gniazdem strażnika. -> {id: wynik|None}."""
    import instancja  # noqa: PLC0415
    rt = runtime or instancja.runtime("/tmp")
    wyniki = {}
    for id_ in ids:
        gniazdo = instancja.sciezki(id_, rt, katalog=korzen).gniazdo
        if not Path(gniazdo).exists():
            wypisz(f"{id_:<11} brak strażnika (gra nie działa)")
            continue
        w = odswiez_instancje(Path(korzen) / "instancje" / id_, zapytaj_gniazdo(gniazdo), sucho=sucho)
        wyniki[id_] = w
        wypisz(f"{id_:<11} " + (f"ML {w['ml']} ({w['ml_proc']}%), bazowy {w['ml_baza']}" + ("  [sucho: nie zapisano]" if sucho else "  zapisano")
                              if w else "brak odczytu (gracz niezalogowany albo blok nieczytelny), nic nie zapisano"))
    return wyniki


def main(argv=None):
    p = argparse.ArgumentParser(prog="ml_zywo.py", description=__doc__.split("\n")[0])
    p.add_argument("--instancja", action="append", metavar="ID", help="tylko ta instancja (można powtarzać); domyślnie wszystkie")
    p.add_argument("--sucho", action="store_true", help="tylko wydruk, zero zapisów")
    p.add_argument("--petla", type=float, metavar="S", help="powtarzaj co S sekund (>= 10) do SIGTERM / Ctrl+C")
    a = p.parse_args(argv)
    ids = a.instancja or instancje()
    if a.petla is None:
        przebieg(ids, sucho=a.sucho)
        return 0
    if a.petla < 10:
        p.error("--petla: co najmniej 10 s")
    try:
        while True:
            przebieg(ids, sucho=a.sucho, wypisz=lambda x: print(time.strftime("%H:%M:%S"), x, flush=True))
            time.sleep(a.petla)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
