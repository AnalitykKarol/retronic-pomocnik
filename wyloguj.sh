#!/bin/bash
# Wylogowanie postaci instancji i zamknięcie jej sesji (K1, spec dane_tibia/SPEC_logowanie_wylogowanie_1021.md, F2 z SPEC_powrot_rook_1020):
# wymaga zatrzymanego bota albo bota w mieście i spokoju (bez walki, bez potwora obok); Ctrl+L co ~4 s, po pojawieniu się listy postaci
# od razu `sesja_gry.py zamknij` (autoReconnect loguje z powrotem w < 60 s). RETRONIC_ID z środowiska albo pierwszy argument.
# Opcje: --limit S (300) · --czekaj-spokoj S (120) · --zasieg N (2) · --reczny-ok (wymuś mimo STOP_RECZNY bez bota).
# Kody wyjścia: 0 ok · 1 limit/porażka · 2 użycie · 4 ręczna gra · 5 brak spokoju (walka) · 6 zgon · 7 ekran nierozpoznany · 8 bot poza miastem.
# Log: instancje/<id>/logi/logowanie.log i logowanie.jsonl. Powrót: sesja_gry.py start + ./zaloguj.sh.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
exec python3 -I "$DIR/logowanie.py" wyloguj "$@"
