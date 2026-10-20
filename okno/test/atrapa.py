#!/usr/bin/env python3
"""Atrapa katalogu pomocnika do testów okna (QML offscreen i skrypty): `atrapa.py KATALOG_DOCELOWY`.

Tworzy `KATALOG/pomocnik/` (dane i skrypty akcji), `KATALOG/proc/` (atrapa /proc dla okno_api: RETRONIC_OKNO_PROC) i wypisuje
na stdout dwie linie `export`. Wszystkie skrypty akcji (zatrzymaj.sh, uruchom.sh, wroc.sh, refill.sh) i otwieracz TYLKO dopisują
jedną linię do `KATALOG/wywolania.log` (skrypt, RETRONIC_ID, MAPA, TRYB, RETRONIC_POSTAC, argumenty); niczego nie uruchamiają.

Stan atrapy (jak dwa boty z makiety): główna (Mastafian) działa, bot na gobliny_edron; instancja `test` (Johny Dang) stoi w Edronie,
więc widać i guziki aktywne dla działającego bota (Stop, ⌂ Miasto), i dla stojącego (▶ Start, ↻ Refill, ↗ Spot, Start z tym).
"""
import json
import os
import shutil
import stat
import sys
import time
from pathlib import Path

DOM = Path(__file__).resolve().parents[2]


def zapisz(sciezka, tekst, wykonywalny=False):
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    sciezka.write_text(tekst, encoding="utf-8")
    if wykonywalny:
        sciezka.chmod(sciezka.stat().st_mode | stat.S_IXUSR)


def panel(klasa, tooltip, pozycja, w_miescie=None, **dodatki):
    d = {"text": "RT", "tooltip": tooltip, "class": klasa, "alt": klasa, "pozycja": pozycja, "w_miescie": w_miescie,
         "w_depo": False, "plan_depo_dostepny": True, "wroc_oczekuje": False, "wroc_w_marszu": False,
         "serwis_dziala": False, "serwis_krok": None, "serwis_ukonczone": [], "serwis_tryb": None,
         "serwis_wynik": None, "serwis_komunikat": "", "serwis_wiek_s": None}
    d.update(dodatki)
    return d


def sygnal(czas, kod, opis, poz, stan, **dane):
    r = {"kod": kod, "opis": opis, "t": 1.0, "poz": poz, "wolan_h": 1, "ponad_limit": False, "tryb": "cien", "stan": stan,
         "czas": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(czas))}
    r.update(dane)
    return r


def buduj(korzen, ile=2):
    """ile = liczba instancji łącznie (główna + test + p2..); ponad dwie to postacie pomocnicze do testu układu na 10."""
    korzen = Path(korzen)
    kat = korzen / "pomocnik"
    kat.mkdir(parents=True, exist_ok=True)
    teraz = time.time()

    # ---- stuby akcji: tylko dziennik wywołań
    dziennik = korzen / "wywolania.log"
    dziennik.write_text("", encoding="utf-8")
    stub = (f'#!/bin/bash\necho "$(basename "$0") RETRONIC_ID=${{RETRONIC_ID-<brak>}} MAPA=${{MAPA-<brak>}} TRYB=${{TRYB-<brak>}} '
            f'POSTAC=${{RETRONIC_POSTAC-<brak>}} ARGS=[$*]" >> "{dziennik}"\nexit 0\n')
    for nazwa in ("zatrzymaj.sh", "uruchom.sh", "wroc.sh", "refill.sh"):
        zapisz(kat / nazwa, stub, True)
    zapisz(korzen / "otwieracz.sh", f'#!/bin/bash\necho "otwieracz ARGS=[$*]" >> "{dziennik}"\nexit 0\n', True)

    # ---- atrapa panel.py: czyta panel.<id|glowna>.json (okno_api woła `panel.py --json` z RETRONIC_ID)
    zapisz(kat / "panel.py",
           'import json, os, sys\n'
           'id_ = os.environ.get("RETRONIC_ID", "") or "glowna"\n'
           'p = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"panel.{id_}.json")\n'
           'print(open(p).read().strip())\n', False)
    zapisz(kat / "panel.glowna.json", json.dumps(panel(
        "dziala", "Retronic: działa\nTryb: mozg.py skrypt, działa 1h 08m\nHP 250/250  mana 25/425\nWniosek analityka: atrapa",
        [33107, 31874, 8])), False)
    zapisz(kat / "panel.test.json", json.dumps(panel(
        "stop", "Retronic: stop\nHP 190/190  mana 65/65", [33160, 31810, 7], w_miescie="edron",
        serwis_ukonczone=["jedzenie"], serwis_wiek_s=5735)), False)

    # ---- mapy, tryby, ostatni start
    mapy = {"_opis": "mapy atrapy",
            "raty": {"trasa": "thais_szczury_opt", "potwory": "Rat", "prog_hp": 30, "dojscie": "thais_dojscie",
                     "opis": "Thais, kanały: szczury (trasa thais_szczury_opt), start z z7 przechodzi dojście thais_dojscie"},
            "trolle_patrol": {"trasa": "patrol:troll", "potwory": "Troll", "prog_hp": 30, "dojscie": "depo_troll_cave",
                              "opis": "Troll cave: patrol po miejscach z trasy/miejsca_troll.json (z8+z9)"},
            "gobliny_edron": {"trasa": "gobliny_edron_z8_petla", "potwory": "Goblin", "prog_hp": 30, "dojscie": "edron_depo",
                              "opis": "Edron, goblinowa jaskinia z8: pętla gobliny_edron_z8_petla, dojście z depo przy starcie z z7"},
            "edron_trolle": {"trasa": "edron_trolle_petla", "potwory": "Troll,Bear", "prog_hp": 30, "dojscie": "edron_depo_trolle",
                             "opis": "Edron troll cave z8: pętla edron_trolle_petla (nagrana 15.10), dojście z depo edron_depo_trolle"}}
    tryby = {"_opis": "tryby atrapy",
             "ostrozny": {"opis": "Bez run w walce (tylko melee, leczenie i jedzenie jak dotąd).", "pokretla": {"RUNA_AKTYWNA": 0}},
             "wyprawa": {"opis": "Wyprawy po zapasy w trakcie patrolu.", "pokretla": {"WYPRAWA_AKTYWNA": 1, "WYPRAWA_CO_MIN": 20}},
             "ml": {"opis": "Trening ML przez utevo lux (F1) w spokoju; robienie run wyłączone.",
                    "pokretla": {"ML_CZAR_AKTYWNY": 1, "UH_AKTYWNY": 0}},
             "runy": {"opis": "Robienie run w spokoju (adori gran, F6, 70 many): tarcza do plecaka, blank do ręki, rzut, runa do plecaka.",
                      "pokretla": {"UH_AKTYWNY": 1, "ML_CZAR_AKTYWNY": 0, "UH_KLAWISZ": "F6", "UH_CZAR": "adori gran", "UH_KOSZT": 70,
                                   "UH_MANA_MIN": 70}},
             "uh": {"opis": "Robienie run UH (adura vita, F7, 100 many): tarcza do plecaka, blank do ręki, rzut, runa do plecaka.",
                    "pokretla": {"UH_AKTYWNY": 1, "ML_CZAR_AKTYWNY": 0, "UH_KLAWISZ": "F7", "UH_CZAR": "adura vita", "UH_KOSZT": 100,
                                 "UH_MANA_MIN": 100}}}
    zapisz(kat / "mapy.json", json.dumps(mapy, ensure_ascii=False), False)
    zapisz(kat / "tryby.json", json.dumps(tryby, ensure_ascii=False), False)
    zapisz(kat / "ostatni_start.env", "MAPA=gobliny_edron\nTRYB=ostrozny,wyprawa\n", False)
    zapisz(kat / "ostatni_start.test.env", "MAPA=trolle_patrol\nTRYB=ml,ostrozny\n", False)

    # ---- instancja test: katalog + log klienta z nickiem (okno bierze nick postaci, gdy bot stoi)
    zapisz(kat / "instancje" / "test" / "gra" / "Retronic.log", "Connecting to character Johny Dang on world X\n", False)
    (kat / "instancje" / "_wspolne").mkdir(parents=True, exist_ok=True)

    for n in range(2, ile):
        id_ = f"p{n}"
        klasa = ("dziala", "stop", "alarm", "brak")[n % 4]
        zapisz(kat / f"panel.{id_}.json", json.dumps(panel(
            klasa, f"Retronic: {klasa}\nTryb: mozg.py skrypt, działa {n}0m 05s\nHP {50 + n * 15}/190  mana {n * 9}/65", [33000 + n, 31800, 8])), False)
        zapisz(kat / f"ostatni_start.{id_}.env", "MAPA=trolle_patrol\nTRYB=ml,ostrozny\n", False)
        zapisz(kat / "instancje" / id_ / "gra" / "Retronic.log", f"Connecting to character Postac Numer{n} on world X\n", False)

    # ---- sygnały ratunku (dziś, jeden z odpowiedzią Haiku w cieniu, jeden wczorajszy)
    data = time.strftime("%Y%m%d", time.localtime(teraz))
    wczoraj = time.strftime("%Y%m%d", time.localtime(teraz - 86400))
    main = [
        sygnal(teraz - 6200, "S4", "kręci się", [33080, 31871, 8], "IDZ", wizyt=3, oscylacje=3, okno_s=60.0),
        sygnal(teraz - 3100, "S4", "kręci się", [33086, 31863, 8], "IDZ", wizyt=4, oscylacje=3, okno_s=60.0),
        sygnal(teraz - 1500, "S6", "klik bez skutku", [33085, 31870, 8], "WALKA", n=5, cel="Goblin"),
        sygnal(teraz - 600, "S4", "kręci się", [33107, 31874, 8], "IDZ", wizyt=3, oscylacje=3, okno_s=60.0,
               haiku_cien={"odpowiedz": "Postać chodzi A-B-A; zatrzymałbym trasę i wrócił do punktu startu.", "model": "haiku"}),
    ]
    zapisz(kat / "logi" / f"ratunek-{data}.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in main), False)
    zapisz(kat / "logi" / f"ratunek-{wczoraj}.jsonl",
           json.dumps(sygnal(teraz - 86400 + 60, "S3", "stoi", [33100, 31860, 8], "IDZ", stoi_s=34.8, kotwica=[33101, 31860, 8])) + "\n", False)
    test = [sygnal(teraz - 900, "S6", "klik bez skutku", [32483, 32293, 8], "WALKA", n=5, cel="Troll")]
    zapisz(kat / "instancje" / "test" / "logi" / f"ratunek-{data}.jsonl", "".join(json.dumps(r) + "\n" for r in test), False)
    # ---- pokrętła: cavebot.py kopiowany tylko do odczytu (okno_api czyta z niego domyślne i komentarze przez ast, nigdy go nie uruchamia)
    shutil.copy(DOM / "cavebot.py", kat / "cavebot.py")
    zapisz(kat / "na_zywo.json", json.dumps({
        "RATUNEK_HAIKU": 1, "RATUNEK_LIMIT_H": 20, "RUNA_AKTYWNA": 1, "UH_AKTYWNY": 0, "UH_CZAR": "adura vita", "UH_KLAWISZ": "F7",
        "UH_KOSZT": 100, "UH_MANA_MIN": 100, "POGON_LIMIT": 25.0, "_opis": "ręczna notatka", "STARY_KLUCZ": 5}, indent=1), False)
    zapisz(kat / "instancje" / "test" / "na_zywo.json", json.dumps({
        "UH_AKTYWNY": 1, "UH_CZAR": "adori gran", "UH_KLAWISZ": "F6", "UH_KOSZT": 70, "UH_MANA_MIN": 70, "ML_CZAR_AKTYWNY": 0}, indent=1), False)

    # ---- atrapa /proc: tylko bot głównej instancji (python3 mozg.py, RETRONIC_POSTAC=Mastafian)
    proc = korzen / "proc" / "4242"
    proc.mkdir(parents=True, exist_ok=True)
    (proc / "cmdline").write_bytes(b"python3\0-I\0-u\0mozg.py\0--tryb\0skrypt\0")
    (proc / "environ").write_bytes(b"RETRONIC_POSTAC=Mastafian\0")

    print(f'export RETRONIC_OKNO_KATALOG="{kat}"')
    print(f'export RETRONIC_OKNO_PROC="{korzen / "proc"}"')
    print(f'export RETRONIC_OKNO_OTWIERACZ="{korzen / "otwieracz.sh"}"')
    print(f'export RETRONIC_OKNO_REPO="{DOM}"')


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit("użycie: atrapa.py KATALOG_DOCELOWY [LICZBA_INSTANCJI]")
    buduj(sys.argv[1], int(sys.argv[2]) if len(sys.argv) == 3 else 2)
