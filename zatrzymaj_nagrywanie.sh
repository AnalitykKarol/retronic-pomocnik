#!/bin/bash
# Kończy nagrywanie trasy (nagraj_trase.py zapisze plik i pokaże powiadomienie).
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
INST=$(python3 -I "$DIR/instancja.py" powloka) || exit 1; eval "$INST"   # RETRONIC_ID -> INST_* (bez ID: dzisiejsze ścieżki)
pidy() { python3 -I "$DIR/instancja.py" pidy 'nagraj_trase\.py'; }
[ -n "$(pidy)" ] || { notify-send "Retronic" "Nagrywanie nie trwa"; echo "nagrywanie nie trwa" >&2; exit 0; }
touch "$INST_STOP_NAGRYWANIA"
for _ in $(seq 100); do [ -z "$(pidy)" ] && break; sleep 0.1; done
if [ -n "$(pidy)" ]; then pidy | xargs -r kill -TERM; sleep 2; fi
echo "zatrzymano"
