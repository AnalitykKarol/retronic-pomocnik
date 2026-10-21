#!/bin/bash
# Logowanie postaci instancji (K1, spec dane_tibia/SPEC_logowanie_wylogowanie_1021.md): sesja już działa (sesja_gry.py start),
# klient stoi na „Enter Game” (albo „Character List”). Kliki Login i Ok myszą, ZERO klawiszy; zrzut i rozpoznanie ekranu tuż przed
# każdym klikiem; nic nie kliknie, gdy ekran to gra. RETRONIC_ID z środowiska albo pierwszy argument. Opcje: --limit S, --reczny-ok.
# Kody wyjścia: 0 ok (też „już w grze”) · 1 limit/porażka · 2 użycie · 3 brak sesji · 4 ręczna gra · 6 zgon · 7 ekran nierozpoznany
# · 9 zalogowano inną postać. Log: instancje/<id>/logi/logowanie.log i logowanie.jsonl. Cofnięcie: ./wyloguj.sh.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
exec python3 -I "$DIR/logowanie.py" zaloguj "$@"
