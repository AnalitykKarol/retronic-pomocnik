#!/bin/bash
# Start/stop obserwatora ręcznej pomocy Karola (tylko odczyt, bez okien).
#   obserwator_reczny.sh start|stop|status|restart
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
INST=$(python3 -I "$DIR/instancja.py" powloka) || exit 1; eval "$INST"   # RETRONIC_ID -> INST_* (bez ID: dzisiejsze ścieżki)
PID="$INST_LOGI/obserwator_reczny.pid"
LOG="$INST_LOGI/obserwator-reczny.log"
dziala() {
  [ -f "$PID" ] || return 1
  local p; p="$(cat "$PID" 2>/dev/null)"
  [ -n "$p" ] && tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | grep -q 'obserwator_reczny.py'
}
case "${1:-status}" in
  start)
    dziala && { echo "już działa (pid $(cat "$PID"))"; exit 0; }
    mkdir -p "$INST_LOGI"; cd "$DIR" || exit 1
    setsid nohup "$DIR/w_scope.sh" obserwator python3 -I -u obserwator_reczny.py >> "$LOG" 2>&1 < /dev/null &
    echo $! > "$PID"; sleep 0.5
    dziala && echo "start, pid $(cat "$PID")" || { echo "nie wystartował, zobacz $LOG" >&2; exit 1; } ;;
  stop)
    dziala || { echo "nie działa"; rm -f "$PID"; exit 0; }
    kill "$(cat "$PID")"; for _ in 1 2 3 4 5 6 7 8 9 10; do dziala || break; sleep 0.3; done
    dziala && kill -9 "$(cat "$PID")"; rm -f "$PID"; echo "zatrzymany" ;;
  restart) "$0" stop; "$0" start ;;
  status) dziala && echo "działa (pid $(cat "$PID"))" || { echo "nie działa"; exit 1; } ;;
  *) echo "użycie: $0 start|stop|status|restart" >&2; exit 2 ;;
esac
