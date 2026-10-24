#!/bin/bash
# Przełącznik STÓJ (23.10): postać przestaje chodzić (trasa, dojście, patrol, wyprawy, pościg), stoi na polu, robi runy,
# leczy się, je i broni się w miejscu; ucieka tylko przy zagrożeniu życia (progi bez zmian). Po przesunięciu wraca na pole.
# Działa na gorąco (bez restartu bota), na każdej mapie. Wyłączenie = powrót do zwykłej pracy od najbliższego punktu trasy.
#   ./stoj.sh <id> on|off|stan        np. ./stoj.sh invincible on
# Skutek: plik instancje/<id>/STOJ (jak STOP, ale bot dalej pracuje). Cofnięcie: ./stoj.sh <id> off.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$DIR" || exit 1
exec python3 "$DIR/stoj.py" "$@"
