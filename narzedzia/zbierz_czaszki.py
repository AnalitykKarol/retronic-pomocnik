#!/usr/bin/env python3
"""P7 (SPEC R1): inwentarz próbek czaszek, offline i tylko do odczytu. Odpowiada: czy mamy dość danych na lokalny detektor?

  python3 -I narzedzia/zbierz_czaszki.py [--logi KATALOG] [--json] [--min N]

Źródła: linie "Czaszka: <nick> = <wynik>" z logi/mozg-*.log (odczyty Haiku; etykieta słaba), zdjęcia w logi/zrzuty/czaszka-*.png
(wycinki, które nie zostały skasowane) i zbiór logi/czaszki/<wynik>/*.png (zapis włączany CZASZKA_ZAPIS_PROBEK=1).
Wynik: tabela próbek per kolor (biala / czerwona / zolta / brak / nieczytelne) i werdykt: detektor tylko, gdy KAŻDA klasa
(biala, czerwona, brak) ma >= --min próbek obrazu (domyślnie 30). Żółta: serwer 7.4 jej nie używa w odczytach bota, więc
liczona informacyjnie. Bez próbek obrazu NIE zgadujemy kolorów.
"""
import argparse
import glob
import json
import os
import re

KLASY = ("biala", "czerwona", "zolta", "brak", "nieczytelne")
WYMAGANE = ("biala", "czerwona", "brak")
WZOR = re.compile(r"Czaszka: (?P<nick>.+?) = (?P<w>biala|czerwona|zolta|brak|nieczytelne)\b")


def odczyty_z_logow(katalog):
    """{klasa: [(plik, nick), ...]} z linii dziennika mózgu."""
    wynik = {k: [] for k in KLASY}
    for plik in sorted(glob.glob(os.path.join(katalog, "mozg-*.log"))):
        try:
            with open(plik, encoding="utf-8", errors="replace") as f:
                for linia in f:
                    m = WZOR.search(linia)
                    if m:
                        wynik[m["w"]].append((os.path.basename(plik), m["nick"]))
        except OSError:
            continue
    return wynik


def obrazy_probek(katalog):
    """{klasa: liczba plików png} ze zbioru logi/czaszki/<klasa>/; luźne logi/zrzuty/czaszka-*.png osobno (bez etykiety)."""
    wynik = {k: 0 for k in KLASY}
    for k in KLASY:
        wynik[k] = len(glob.glob(os.path.join(katalog, "czaszki", k, "*.png")))
    bez_etykiety = len(glob.glob(os.path.join(katalog, "zrzuty", "czaszka-*.png")))
    return wynik, bez_etykiety


def raport(katalog, minimum=30):
    odczyty = odczyty_z_logow(katalog)
    obrazy, bez_etykiety = obrazy_probek(katalog)
    brakuje = {k: max(0, minimum - obrazy[k]) for k in WYMAGANE}
    return {
        "odczyty_log": {k: len(v) for k, v in odczyty.items()},
        "unikalne_nicki_log": {k: len({n for _, n in v}) for k, v in odczyty.items()},
        "obrazy": obrazy,
        "obrazy_bez_etykiety": bez_etykiety,
        "minimum_na_klase": minimum,
        "brakuje_obrazow": brakuje,
        "wystarczy": all(v == 0 for v in brakuje.values()),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--logi", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logi"))
    ap.add_argument("--min", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = raport(a.logi, a.min)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    print(f"{'klasa':<12}{'odczyty w logu':>16}{'nicki':>8}{'obrazy':>9}")
    for k in KLASY:
        print(f"{k:<12}{r['odczyty_log'][k]:>16}{r['unikalne_nicki_log'][k]:>8}{r['obrazy'][k]:>9}")
    print(f"wycinki bez etykiety (logi/zrzuty/czaszka-*.png): {r['obrazy_bez_etykiety']}")
    print("WYSTARCZY na detektor." if r["wystarczy"] else
          "ZA MALO obrazow (min " + str(a.min) + "/klase), brakuje: "
          + ", ".join(f"{k} {v}" for k, v in r["brakuje_obrazow"].items() if v)
          + ". Wlacz CZASZKA_ZAPIS_PROBEK=1 i zbieraj.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
