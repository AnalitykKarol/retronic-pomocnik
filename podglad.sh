#!/bin/bash
# Podgląd gry uruchomionej bez okna (sesja.sh, RETRONIC_BEZ_OKNA=1): vncviewer na wayvnc sesji, z myszą i klawiaturą.
# Zamknięcie podglądu nie zatrzymuje gry ani bota. RETRONIC_ID=<id> wybiera instancję.
# --czekaj: czeka do 60 s, aż wayvnc sesji zacznie słuchać (tak woła go sesja.sh przy starcie).
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
INST=$(python3 -I "$DIR/instancja.py" powloka) || exit 1; eval "$INST"
CZEKAJ=0; [ "${1:-}" = "--czekaj" ] && CZEKAJ=60
for i in $(seq 0 "$CZEKAJ"); do
  PORT=$(cat "$INST_SESJA/vnc_port" 2>/dev/null)
  [ -n "$PORT" ] && (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null && break
  PORT=""; [ "$i" -lt "$CZEKAJ" ] && sleep 1
done
[ -n "$PORT" ] || { echo "podglad.sh: gra bez okna nie działa (brak wayvnc w $INST_SESJA)" >&2; exit 1; }
if pgrep -f "^vncviewer .*127\.0\.0\.1::$PORT\b" >/dev/null; then echo "podgląd już otwarty (port $PORT)"; exit 0; fi
exec vncviewer -RemoteResize=0 -ReconnectOnError=0 127.0.0.1::"$PORT"
