#!/usr/bin/env python3
"""Atrapa katalogu pomocnika do testów okna (QML offscreen i skrypty): `atrapa.py KATALOG_DOCELOWY`.

Tworzy `KATALOG/pomocnik/` (dane i skrypty akcji), `KATALOG/proc/` (atrapa /proc dla okno_api: RETRONIC_OKNO_PROC) i wypisuje
na stdout dwie linie `export`. Wszystkie skrypty akcji (zatrzymaj.sh, uruchom.sh, wroc.sh, refill.sh) i otwieracz TYLKO dopisują
jedną linię do `KATALOG/wywolania.log` (skrypt, RETRONIC_ID, MAPA, TRYB, RETRONIC_POSTAC, argumenty); niczego nie uruchamiają.

Stan atrapy (jak dwa boty z makiety): główna (Mastafian) działa, bot na gobliny_edron; instancja `test` (Johny Dang) stoi w Edronie,
więc widać i guziki aktywne dla działającego bota (Stop, ⌂ Miasto), i dla stojącego (▶ Start, ↻ Refill, ↗ Spot, Start z tym).

F4 (Sesja gry): `XDG_RUNTIME_DIR` wskazuje na `KATALOG/run` (okno_api liczy ścieżki sesji z niego, więc prawdziwe sesje nigdy nie wpadają do testu),
`sesja_gry.py` to stub (tylko dziennik wywołań). Opcja `--sesja` dokłada trzy instancje do testu sekcji Sesja gry:
  dzial       sesja i gra działają, bot działa, proxy działa, podgląd OTWARTY (vncviewer na porcie 5901), profil ok, IP zgodne
  ipzle       sesja i gra działają, bot stoi, podgląd zamknięty (port 5902), IP z ostatniego startu SPOZA profilu, konto nieprzypisane
  bezprofilu  brak sesji i brak profil.json (błąd profilu, start niemożliwy)
a `test` ma profil ok i brak sesji (start możliwy). Główna: bez profilu, sesja nie działa.
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


def proces(proc, pid, argv, env=None):
    """Wpis atrapy /proc: cmdline (argv rozdzielone NUL) i environ."""
    d = Path(proc) / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    (d / "environ").write_bytes(b"".join(f"{k}={v}\0".encode() for k, v in (env or {}).items()))


def profil(user, ip, postac, konto, uwagi):
    return json.dumps({"proxy": {"host": "p.example.test", "port": 80, "user": user}, "ip_oczekiwane": [ip],
                       "postac": postac, "konto": konto, "uwagi": uwagi}, ensure_ascii=False)


def sesja_instancji(kat, run, proc, teraz, id_, nick, panel_json, mapa, pid0, *, wiek_s=None, profil_json=None, tozsamosc=False,
                    sway=False, bot=False, proxy=False, port=None, podglad_otwarty=False, ip_log=None, log_akcji=()):
    """Jedna instancja z F4: katalog, panel, profil i (opcjonalnie) żywa sesja w atrapie /proc oraz pliki sesji w run/."""
    inst = kat / "instancje" / id_
    zapisz(inst / "gra" / "Retronic.log", f"Connecting to character {nick} on world X\n", False)
    zapisz(kat / f"panel.{id_}.json", json.dumps(panel_json), False)
    zapisz(kat / f"ostatni_start.{id_}.env", f"MAPA={mapa}\nTRYB=ostrozny\n", False)
    if profil_json:
        zapisz(inst / "profil.json", profil_json, False)
    if tozsamosc:
        zapisz(inst / "tozsamosc.json", "{}", False)
    sesja = run / f"retronic-sesja-{id_}"
    if sway:
        sesja.mkdir(parents=True, exist_ok=True)
        conf = sesja / "sway.conf"
        zapisz(conf, "# atrapa\n", False)
        if wiek_s:
            os.utime(conf, (teraz - wiek_s, teraz - wiek_s))
        linie = ["siec_proxy: start", "uruchom_gre.sh: WINEPREFIX instancji"]
        if ip_log:
            linie.insert(1, ip_log)
        zapisz(sesja / "sway.log", "\n".join(linie) + "\n", False)
        zapisz(sesja / "vnc_port", f"{port}\n", False)
        zapisz(run / f"retronic-{id_}.sock", "", False)
        env = {"RETRONIC_ID": id_}
        proces(proc, pid0, ["sway", "-c", str(conf)])
        proces(proc, pid0 + 1, ["python3", "-I", "-u", "straznik.py"], env)
        proces(proc, pid0 + 2, ["bash", str(kat / "sesja.sh")], env)
        if proxy:
            proces(proc, pid0 + 3, ["bash", str(kat / "siec_proxy.sh")], env)
        if podglad_otwarty:
            proces(proc, pid0 + 4, ["vncviewer", f"127.0.0.1::{port}"])
        if bot:
            proces(proc, pid0 + 5, ["python3", "-I", "-u", "mozg.py", "--tryb", "skrypt"], dict(env, RETRONIC_POSTAC=nick))
    if log_akcji:
        data = time.strftime("%Y%m%d", time.localtime(teraz))
        zapisz(inst / "logi" / f"sesja-{data}.log", "\n".join(log_akcji) + "\n", False)


def buduj(korzen, ile=2, sesja=False):
    """ile = liczba instancji łącznie (główna + test + p2..); ponad dwie to postacie pomocnicze do testu układu na 10.
    sesja=True dokłada instancje do testu sekcji Sesja gry (dzial, ipzle, bezprofilu, patrz opis modułu)."""
    korzen = Path(korzen)
    kat = korzen / "pomocnik"
    kat.mkdir(parents=True, exist_ok=True)
    run = korzen / "run"                       # XDG_RUNTIME_DIR atrapy: gniazda i katalogi sesji instancji
    run.mkdir(mode=0o700, parents=True, exist_ok=True)
    run.chmod(0o700)
    teraz = time.time()

    # ---- stuby akcji: tylko dziennik wywołań
    dziennik = korzen / "wywolania.log"
    dziennik.write_text("", encoding="utf-8")
    stub = (f'#!/bin/bash\necho "$(basename "$0") RETRONIC_ID=${{RETRONIC_ID-<brak>}} MAPA=${{MAPA-<brak>}} TRYB=${{TRYB-<brak>}} '
            f'POSTAC=${{RETRONIC_POSTAC-<brak>}} ARGS=[$*]" >> "{dziennik}"\nexit 0\n')
    for nazwa in ("zatrzymaj.sh", "uruchom.sh", "wroc.sh", "refill.sh"):
        zapisz(kat / nazwa, stub, True)
    zapisz(korzen / "otwieracz.sh", f'#!/bin/bash\necho "otwieracz ARGS=[$*]" >> "{dziennik}"\nexit 0\n', True)
    # sesja_gry.py (start | zamknij | podglad): dziennik wywołań + jedna linia wyniku (jak prawdziwy skrypt) + zmiana STANU ATRAPY
    # (pliki w run/ i wpisy atrapy /proc), żeby okno po akcji zobaczyło sesję wstającą, zamkniętą albo podgląd otwarty. Nic prawdziwego nie rusza.
    zapisz(kat / "sesja_gry.py", stub.replace("\nexit 0\n", "\n") +
           f'RUN="{run}"; PROC="{korzen / "proc"}"; ID="${{RETRONIC_ID}}"\n'
           'case "$1" in\n'
           '  start)\n'
           '    d="$RUN/retronic-sesja-$ID"; mkdir -p "$d"; : > "$d/sway.conf"; echo 5990 > "$d/vnc_port"; : > "$RUN/retronic-$ID.sock"\n'
           '    p="$PROC/8$$"; mkdir -p "$p"; printf \'sway\\0-c\\0%s\\0\' "$d/sway.conf" > "$p/cmdline"; : > "$p/environ"\n'
           '    echo "sesja $ID wystartowała (atrapa): gra sprawdza IP proxy, potem zaloguj postać w podglądzie";;\n'
           '  zamknij)\n'
           f'    [ -f "{korzen}/opoznienie-zamknij-$ID" ] && sleep "$(cat "{korzen}/opoznienie-zamknij-$ID")"\n'      # test: wolne zamknięcie jednej instancji
           '    for p in "$PROC"/*; do\n'
           '      if tr \'\\0\' \' \' < "$p/cmdline" 2>/dev/null | grep -q "retronic-sesja-$ID/" || tr \'\\0\' \'\\n\' < "$p/environ" 2>/dev/null | grep -qx "RETRONIC_ID=$ID"; then rm -rf "$p"; fi\n'
           '    done\n'
           '    rm -rf "$RUN/retronic-sesja-$ID" "$RUN/retronic-$ID.sock"\n'
           '    echo "gra $ID zamknięta (atrapa)";;\n'
           '  podglad)\n'
           '    port="$(cat "$RUN/retronic-sesja-$ID/vnc_port" 2>/dev/null)"\n'
           '    if [ -n "$port" ]; then p="$PROC/7$$"; mkdir -p "$p"; printf \'vncviewer\\0%s\\0\' "127.0.0.1::$port" > "$p/cmdline"; : > "$p/environ"; fi\n'
           '    echo "podgląd $ID otwiera się (atrapa)";;\n'
           'esac\nexit 0\n', True)

    # ---- atrapa panel.py: czyta panel.<id|glowna>.json (okno_api woła `panel.py --json` z RETRONIC_ID)
    zapisz(kat / "panel.py",
           'import json, os, sys\n'
           'id_ = os.environ.get("RETRONIC_ID", "") or "glowna"\n'
           'p = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"panel.{id_}.json")\n'
           'print(open(p).read().strip())\n', False)
    zapisz(kat / "panel.glowna.json", json.dumps(panel(
        "dziala", "Retronic: działa\nTryb: mozg.py skrypt, działa 1h 08m\nHP 250/250  mana 25/425\nWniosek analityka: atrapa",
        [33107, 31874, 8], level=31, level_procent=42.0, podglad={"port": None, "otwarty": False, "pid": None})), False)
    zapisz(kat / "panel.test.json", json.dumps(panel(
        "stop", "Retronic: stop\nHP 190/190  mana 65/65", [33160, 31810, 7], w_miescie="edron",
        serwis_ukonczone=["jedzenie"], serwis_wiek_s=5735, level=18, level_procent=7.5,
        podglad={"port": None, "otwarty": False, "pid": None})), False)

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

    # profil `test`: ok, sesja nie działa (Uruchom grę możliwe)
    zapisz(kat / "instancje" / "test" / "profil.json", profil("fx-3", "10.0.0.3", "Johny Dang", "konto-test", "atrapa: profil ok, sesja zatrzymana"), False)
    zapisz(kat / "instancje" / "test" / "tozsamosc.json", "{}", False)

    proc = korzen / "proc"
    if sesja:
        pg = lambda port, otwarty, pid=None: {"port": port, "otwarty": otwarty, "pid": pid}
        sesja_instancji(kat, run, proc, teraz, "dzial", "Dzialajaca Postac", panel(
            "dziala", "Retronic: działa\nTryb: mozg.py skrypt, działa 2h 05m\nHP 410/410  mana 120/300", [33000, 31800, 8],
            level=58, level_procent=63.0, podglad=pg(5901, True, 9004)), "gobliny_edron", 9000,
            wiek_s=3 * 3600 + 12 * 60, sway=True, bot=True, proxy=True, port=5901, podglad_otwarty=True, tozsamosc=True,
            profil_json=profil("fx-1", "10.0.0.1", "Dzialajaca Postac", "konto-dzial", "Webshare, proxy nr 1 (atrapa)"),
            ip_log="siec_proxy: IP wyjściowe 10.0.0.1 (zgodne z profilem)",
            log_akcji=["sesja.sh dzial: start", "gra wystartowała o 09:12"])
        sesja_instancji(kat, run, proc, teraz, "ipzle", "Pomylone Ip", panel(
            "stop", "Retronic: stop\nHP 150/150  mana 40/40", [33001, 31801, 8],
            level=12, level_procent=90.0, podglad=pg(5902, False)), "trolle_patrol", 9100,
            wiek_s=95, sway=True, proxy=True, port=5902, tozsamosc=True,
            profil_json=profil("fx-2", "10.0.0.2", "Pomylone Ip", "", "atrapa: konto jeszcze nieprzypisane"),
            ip_log="siec_proxy: IP wyjściowe 203.0.113.9 spoza profilu")
        sesja_instancji(kat, run, proc, teraz, "bezprofilu", "Bez Profilu", panel(
            "brak", "Retronic: brak gry", [33002, 31802, 8], podglad=pg(None, False)), "raty", 9200)

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
    print(f'export XDG_RUNTIME_DIR="{run}"')


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--sesja"]
    if len(args) not in (1, 2):
        sys.exit("użycie: atrapa.py KATALOG_DOCELOWY [LICZBA_INSTANCJI] [--sesja]")
    buduj(args[0], int(args[1]) if len(args) == 2 else 2, sesja="--sesja" in sys.argv[1:])
