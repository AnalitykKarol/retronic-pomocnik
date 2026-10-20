#!/usr/bin/env python3
"""Jednorazowo (20.10.2026), idempotentnie: poprawka danych przy schodach (32498,32270,z8) w jaskini trolli.

  python3 -I narzedzia_jednorazowe/napraw_schody_32498_1020.py [--trasy KATALOG] [--zapisz]

Bez --zapisz: tylko raport (co zostałoby zmienione). KATALOG = katalog z miejsca_troll.json i dziury_nauczone.json
(domyślnie trasy/ obok skryptu; na żywym pomocniku: `--trasy /home/charlie/Games/Retronic/pomocnik/trasy`).
Drugie uruchomienie niczego nie zmienia (kontrola: "bez zmian").

Co poprawia i skąd wiadomo (szczegóły: commit i raport 20.10):
 1. trasy/dziury_nauczone.json: usuwa TYLKO pole [32498, 32271, 8]. To zwykła podłoga (flaga mapy 1, 58 próbek gracza
    na polu bez zmiany piętra), a nie dziura: wpadniecie.py nauczył je 15.10 18:15:30 z lądowania (32498,32271,9) po
    zejściu SCHODAMI (T = (32498,32270,8)), zakładając lądowanie = pole dziury. Pole zamykało patrolowi wyjście z
    kieszeni (32497,32270)/(32497,32271) na wschód i wymuszało krokowe chodzenie w jego otoczeniu. Reszta pliku
    zostaje bez zmian (bot dopisuje tam nowe wpisy na żywo); wpisy prawdziwe: (32482,32296,8) = pole schodów,
    (32508,32273,8) = prawdziwa dziura (upadek 15.10 21:33:59).
 2. trasy/miejsca_troll.json, przejście schody_32498_32270: pola lądowania wyjscie_dol -> (32498,32271,9) i
    wyjscie_gora -> (32498,32269,8) (było (32498,32270,9) = samo pole schodów z9 bez drogi A* i (32498,32271,8) =
    fałszywa dziura; generator liczył schody jak dziurę + drabinę). Dowód: telemetria `pietra_krok` (zejście 154x ląduje
    w (32498,32271,9), wejście 166x w (32498,32269,8)), `dane_tibia/ruch/MAPA_DOSWIADCZENIA.md` 4.1. Potem przelicza
    "graf" (węzły, składowe, długości A*), "sasiedzi", "od_startu" i "komp" miejsc tym samym kodem co generator
    (generuj_miejsca_troll.graf_i_sasiedzi); pola ze statystyk telemetrii (zabicia, mobow, gniazdo) zostają.
 3. znane_pola.json: BEZ zmian (w okolicy schodów nie ma pola znanego, którego mapa nie widzi, więc A* nie korzysta
    z niczego, co trzeba by usunąć; ściany ze znanych pól A* i tak odrzuca).

Uwaga na żywo: bot trzyma nauczone dziury w pamięci i przy nauce następnej zapisuje cały zbiór z pamięci, więc zmianę
w dziury_nauczone.json stosuj przy ZATRZYMANYM bocie (wczytuje plik przy starcie) albo od razu przed restartem.
"""
import argparse
import copy
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("RETRONIC_TESTY", "1")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import generuj_miejsca_troll as G  # noqa: E402

FALSZYWA_DZIURA = [32498, 32271, 8]
ID_SCHODOW = "schody_32498_32270"


def napraw_dziury(plik, zapisz):
    """-> opis zmiany albo None. Usuwa tylko FALSZYWA_DZIURA, reszta pliku bez zmian (format jak w wpadniecie.zapisz)."""
    if not plik.is_file():
        return None
    d = json.loads(plik.read_text())
    lista = d.get("dziury", [])
    if FALSZYWA_DZIURA not in lista:
        return None
    d["dziury"] = [p for p in lista if p != FALSZYWA_DZIURA]
    if zapisz:
        tmp = Path(str(plik) + ".tmp")
        tmp.write_text(json.dumps(d, indent=1))
        os.replace(tmp, plik)
    return f"{plik.name}: usunięto {FALSZYWA_DZIURA} ({len(lista)} -> {len(d['dziury'])} wpisów)"


def napraw_miejsca(plik, zapisz):
    """-> opis zmiany albo None. Landing schodów z mapy (G.ladowania), potem graf i drogi jak w generatorze."""
    d = json.loads(plik.read_text())
    nowy = copy.deepcopy(d)
    e = next((p for p in nowy["przejscia"] if p["id"] == ID_SCHODOW), None)
    if e is None:
        raise SystemExit(f"{plik}: brak przejścia {ID_SCHODOW}")
    m = G._mapa.mapa()
    G.cavebot.log = lambda *a: None
    T = e["pole"]
    e["wyjscie_dol"], e["wyjscie_gora"] = G.ladowania(m, T, T[2])
    graf, brak = G.graf_i_sasiedzi(m, nowy, nowy["miejsca"])
    if brak:
        raise SystemExit(f"{plik}: po poprawce brak drogi dla par {brak} - nie zapisuję")
    nowy["graf"] = graf
    for mm in nowy["miejsca"]:
        mm["komp"] = next(n["komp"] for n in graf["wezly"] if n["pole"] == [mm["x"], mm["y"], mm["z"]])
    if nowy == d:
        return None
    if zapisz:
        tmp = Path(str(plik) + ".tmp")
        tmp.write_text(json.dumps(nowy, ensure_ascii=False, indent=1) + "\n")
        os.replace(tmp, plik)
    stare = {k: d["przejscia"][[p["id"] for p in d["przejscia"]].index(ID_SCHODOW)][k] for k in ("wyjscie_dol", "wyjscie_gora")}
    return (f"{plik.name}: {ID_SCHODOW} wyjscie_dol {stare['wyjscie_dol']} -> {e['wyjscie_dol']}, "
            f"wyjscie_gora {stare['wyjscie_gora']} -> {e['wyjscie_gora']}; graf przeliczony "
            f"({len(d['graf']['wezly'])} -> {len(graf['wezly'])} węzłów, {len(d['graf']['odl'])} -> {len(graf['odl'])} odcinków)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trasy", default=str(ROOT / "trasy"))
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    kat = Path(a.trasy)
    zm = [napraw_dziury(kat / "dziury_nauczone.json", a.zapisz), napraw_miejsca(kat / "miejsca_troll.json", a.zapisz)]
    zm = [z for z in zm if z]
    for z in zm:
        print(("ZAPISANO " if a.zapisz else "DO ZMIANY ") + z)
    if not zm:
        print("bez zmian")
    return 0


if __name__ == "__main__":
    sys.exit(main())
