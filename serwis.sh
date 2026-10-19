#!/bin/bash
# Serwis w mieście (Edron): wymiana gold, depo (bag z UH + platinum ponad 3), ham, backpack, blanki, wyjście z depo.
#   ./serwis.sh                       cały serwis w domyślnej kolejności (trasy/serwis_edron.json)
#   ./serwis.sh --kroki bank,depo     tylko wybrane kroki (kolejność jak podasz)
#   ./serwis.sh --na-sucho [--od x,y,z]   tylko plan dróg, zero inputu do gry
#   STARTUJ=1 ./serwis.sh             po sukcesie startuje bota ostatnią mapą i trybem (uruchom.sh, z dojściem do spotu)
# Odmawia, gdy bot (mozg/cavebot) tej instancji działa: serwis steruje myszą i czatem, więc bot musi stać (zatrzymaj.sh).
# Przy porażce zostawia plik STOP i dymek; nic nie ponawia po cichu. Wymaga: gra, strażnik (gniazdo), postać w Edronie.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
INST=$(python3 -I "$DIR/instancja.py" powloka) || exit 1; eval "$INST"
TYTUL="Serwis Retronic${RETRONIC_ID:+ [$RETRONIC_ID]}"
pidy() { python3 -I "$DIR/instancja.py" pidy '(mozg|cavebot)\.py'; }
cd "$DIR" || exit 1
SUCHO=0; for a in "$@"; do [ "$a" = "--na-sucho" ] && SUCHO=1; done
if [ "$SUCHO" = 0 ]; then
  p=$(pidy | head -1)
  [ -n "$p" ] && { notify-send "$TYTUL" "Bot działa (pid $p): zatrzymaj go przed serwisem"; echo "bot działa (pid $p), zatrzymaj: ./zatrzymaj.sh" >&2; exit 1; }
  [ -S "$INST_SOCK" ] || { notify-send "$TYTUL" "Gra nie działa (brak socketu)"; echo "brak socketu gry" >&2; exit 1; }
  rm -f "$INST_STOP" "$INST_STOP_RECZNY" "$INST_STAN/WROC"        # STOP blokuje każdy input do gry; po zatrzymanym bocie nic innego nie działa
fi
export RETRONIC_POSTAC="${RETRONIC_POSTAC:-$(python3 -I -c "import sys; sys.path.insert(0,'$DIR'); import bot; print(bot.Postac().nazwa)" 2>/dev/null)}"
python3 -I -u serwis.py edron "$@"
kod=$?
if [ "$SUCHO" = 0 ] && [ "$kod" != 0 ]; then
  touch "$INST_STOP"; echo "serwis: porażka (kod $kod), zostawiam plik STOP" >&2; exit "$kod"
fi
if [ "$SUCHO" = 0 ] && [ "${STARTUJ:-0}" = 1 ]; then
  echo "serwis: gotowe, startuję bota ostatnią mapą i trybem"
  exec "$DIR/uruchom.sh"
fi
exit "$kod"
