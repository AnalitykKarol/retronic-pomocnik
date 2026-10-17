#!/bin/bash
# Nadzorca podglądu gry (16.10): wayvnc 0.10.1 sam pada na błędzie protokołu schowka ("not a valid new object id ...
# message data_offer"), a wtedy vncviewer dostaje "End of stream" i okno znika. Ten skrypt:
#  - podnosi wayvnc sesji, gdy go nie ma (gra, bot i sway nie są ruszane; bot robi zrzuty grim-em, nie przez wayvnc),
#  - otwiera podgląd (podglad.sh) z powrotem TYLKO gdy okno zniknęło przez awarię wayvnc w ostatnich 15 s
#    (zamknięcie okna przez Ciebie przy żyjącym wayvnc = brak ponownego otwarcia).
# Start: ./podglad_stroz.sh &   Stop: pkill -f podglad_stroz.sh   Cofnięcie: samo zatrzymanie skryptu, nic nie zostaje.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
INST=$(python3 -I "$DIR/instancja.py" powloka) || exit 1; eval "$INST"
PORT=$(cat "$INST_SESJA/vnc_port" 2>/dev/null); PORT=${PORT:-5901}
log() { echo "$(date +%T) podglad_stroz: $*" >> "$DIR/logi/podglad_stroz.log"; }
wayvnc_pid() { pgrep -f "^wayvnc (-S [^ ]+ )?127\.0\.0\.1 $PORT\$" | head -1; }
viewer_pid() { pgrep -f "^vncviewer .*127\.0\.0\.1::$PORT\b" | head -1; }
ostatni_pad=0; widzialem_viewer=0
log "start (port $PORT)"
while true; do
  [ -S "$INST_SOCK" ] || { sleep 5; continue; }       # gra nie działa: nic nie robimy
  W=$(cat "$INST_SESJA/wayland" 2>/dev/null)
  if [ -z "$(wayvnc_pid)" ] && [ -n "$W" ]; then
    ostatni_pad=$(date +%s)
    XDG_RUNTIME_DIR="/run/user/$(id -u)" WAYLAND_DISPLAY="$W" setsid nohup wayvnc ${RETRONIC_ID:+-S "$INST_SESJA/wayvnc.sock"} 127.0.0.1 "$PORT" >> "$DIR/logi/podglad_stroz.log" 2>&1 < /dev/null &
    log "wayvnc padł albo go nie było: uruchomiony ponownie"
    sleep 3
  fi
  if [ -n "$(viewer_pid)" ]; then
    widzialem_viewer=1
  elif [ "$widzialem_viewer" = 1 ]; then
    widzialem_viewer=0
    if [ $(( $(date +%s) - ostatni_pad )) -le 15 ]; then
      log "okno zniknęło po awarii wayvnc: otwieram podgląd"
      setsid nohup "$DIR/podglad.sh" >/dev/null 2>&1 < /dev/null &
      sleep 3
    else
      log "okno zamknięte przy działającym wayvnc: nie otwieram"
    fi
  fi
  sleep 2
done
