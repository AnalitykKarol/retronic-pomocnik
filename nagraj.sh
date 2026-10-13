#!/bin/bash
# Nagrywanie trasy z ręcznego chodzenia: ./nagraj.sh <nazwa> [--krok 4] [--nadpisz]
# Tylko odczyt pozycji (zero inputu do gry). Koniec: ./zatrzymaj_nagrywanie.sh albo touch STOP_NAGRYWANIA.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
INST=$(python3 -I "$DIR/instancja.py" powloka) || exit 1; eval "$INST"   # RETRONIC_ID -> INST_* (bez ID: dzisiejsze ścieżki)
SOCK="$INST_SOCK"
[ -n "$1" ] || { echo "użycie: nagraj.sh <nazwa> [--krok N] [--nadpisz]" >&2; exit 2; }
p=$(python3 -I "$DIR/instancja.py" pidy 'nagraj_trase\.py' | head -1)
[ -n "$p" ] && { notify-send "Retronic" "Nagrywanie już trwa (pid $p)"; echo "nagrywanie już trwa" >&2; exit 1; }
[ -S "$SOCK" ] || { notify-send "Retronic" "Gra nie działa (brak socketu)"; echo "brak socketu gry" >&2; exit 1; }
cd "$DIR" || exit 1
mkdir -p "$INST_LOGI"
LOG="$INST_LOGI/nagranie-$1-$(date +%m%d-%H%M).log"
rm -f "$INST_STOP_NAGRYWANIA"
setsid nohup python3 -I -u nagraj_trase.py "$@" > "$LOG" 2>&1 < /dev/null &
sleep 0.5
if ! kill -0 $! 2>/dev/null; then
  notify-send -u critical "Retronic" "Nagrywanie nie ruszyło: $(tail -n1 "$LOG")"; cat "$LOG" >&2; exit 1
fi
notify-send "Retronic" "nagrywanie ruszyło: $1"
echo "nagrywam '$1' (log: $LOG). Koniec: ./zatrzymaj_nagrywanie.sh"
