#!/usr/bin/env python3
"""Dane serwisu Edron z ręcznego nagrania Karola (19.10): przystanki, łączniki pięter, stanowiska depo.

  python3 -I generuj_serwis_edron.py [--nagranie trasy/edron_serwis_surowa.json] [--znaczniki trasy/edron_serwis_znaczniki.jsonl]
                                      [--wyjscie trasy/serwis_edron.json]

Czyta tylko pliki (zero gry). Wejście: nagranie nagraj_trase.py (lista punktów [x,y,z]) i znaczniki z etykietami przystanków.
Wyjście `trasy/serwis_edron.json` używa serwis.py:
  przystanki  nazwa -> {rodzaj, npc, stoi}  (pole stania zmierzone na żywo przy NPC / skrzyni depo)
  laczniki    [{"z": [x,y,z], "do": [x,y,z]}]  wszystkie przejścia pięter z nagrania (obie strony, bo Karol przeszedł je w obie)
  depo_stoiska pola stania przy skrzyniach depo (osiem wnęk), od najbliższego wejścia
  wyjscie     pole na z7 przy wyjściu z depo, skąd uruchom.sh startuje z dojściem do spotu
  kolejnosc   domyślna kolejność kroków (edytowalna ręcznie w pliku)
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
KATALOG = Path(__file__).resolve().parent
TRASY = KATALOG / "trasy"

# etykieta znacznika -> nazwa przystanku (pole stania = pozycja z tego znacznika)
ZNACZNIKI = {
    "bank": "bank_stoje",
    "depo": "depo_stoje_przy_wolnej",
    "jedzenie": "jedzenie_stoje_kupuje_5_ham",
    "backpack": "beatrice_stoje",
    "blanki": "alexander_stoje",
}
OPIS = {
    "bank": {"rodzaj": "bank", "npc": "Ebenizer"},
    "depo": {"rodzaj": "depo", "npc": None},
    "jedzenie": {"rodzaj": "kup", "npc": "Mirabell"},
    "backpack": {"rodzaj": "kup", "npc": "Beatrice"},
    "blanki": {"rodzaj": "kup", "npc": "Alexander"},
}
KOLEJNOSC = ["bank", "depo", "jedzenie", "backpack", "blanki", "wyjscie"]
# wnęki depo Edron (z8): y = 31796, x nieparzyste od 33161 do 33175 (mapa klienta 19.10); skrzynia stoi dy = -1 od pola stania
DEPO_X = list(range(33161, 33176, 2))
DEPO_Y = 31796
DEPO_Z = 8


def laczniki(punkty):
    """Pary kolejnych punktów nagrania o różnym piętrze: [{"z": a, "do": b}] bez duplikatów, w kolejności nagrania."""
    wynik, widziane = [], set()
    for a, b in zip(punkty, punkty[1:]):
        if a[2] != b[2]:
            klucz = (tuple(a), tuple(b))
            if klucz not in widziane:
                widziane.add(klucz)
                wynik.append({"z": list(a), "do": list(b)})
    return wynik


def stanowiska_depo():
    """Pola stania przy skrzyniach depo, od najbliższego wschodniego (to, na którym Karol testował) w stronę zachodu."""
    return [[x, DEPO_Y, DEPO_Z] for x in sorted(DEPO_X, reverse=True)]


def zbuduj(punkty, znaczniki):
    po_etykiecie = {z["etykieta"]: z for z in znaczniki}
    przystanki = {}
    for nazwa, etykieta in ZNACZNIKI.items():
        if etykieta not in po_etykiecie:
            raise SystemExit(f"brak znacznika {etykieta!r} (przystanek {nazwa})")
        przystanki[nazwa] = dict(OPIS[nazwa], stoi=list(po_etykiecie[etykieta]["poz"]))
    return {
        "_opis": "Serwis Edron: dane z nagrania Karola 19.10 (generuj_serwis_edron.py). Kolejność edytowalna; stoi = pole stania.",
        "miasto": "edron",
        "przystanki": przystanki,
        "wyjscie": list(po_etykiecie["koniec_nagrania_pod_depo"]["poz"]),
        "laczniki": laczniki(punkty),
        "depo_stoiska": stanowiska_depo(),
        "kolejnosc": KOLEJNOSC,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--nagranie", default=str(TRASY / "edron_serwis_surowa.json"))
    p.add_argument("--znaczniki", default=str(TRASY / "edron_serwis_znaczniki.jsonl"))
    p.add_argument("--wyjscie", default=str(TRASY / "serwis_edron.json"))
    a = p.parse_args(argv)
    punkty = [tuple(x) for x in json.loads(Path(a.nagranie).read_text())]
    znaczniki = [json.loads(l) for l in Path(a.znaczniki).read_text().splitlines() if l.strip()]
    dane = zbuduj(punkty, znaczniki)
    Path(a.wyjscie).write_text(json.dumps(dane, ensure_ascii=False, indent=1) + "\n")
    print(f"zapisano {a.wyjscie}: {len(dane['przystanki'])} przystanków, {len(dane['laczniki'])} łączników, "
          f"{len(dane['depo_stoiska'])} stanowisk depo")


if __name__ == "__main__":
    main()
