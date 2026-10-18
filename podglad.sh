#!/bin/bash
# Podgląd gry uruchomionej bez okna (sesja.sh, RETRONIC_BEZ_OKNA=1): vncviewer na wayvnc sesji, z myszą i klawiaturą.
# Zamknięcie podglądu nie zatrzymuje gry ani bota. RETRONIC_ID=<id> wybiera instancję.
# Okno podglądu rządzi rozmiarem ekranu sesji: dopasuj_okno.py (w tle, z życiem vncviewera) ustawia wayvnc na rozmiar okna
# (min. 800x600); RETRONIC_DOPASUJ_OKNO=0 wyłącza (ekran sesji ma wtedy stały rozmiar z sesja.sh). vncviewer zostaje z
# -RemoteResize=0: TigerVNC 1.16 sam nie prosi o zmianę rozmiaru, a skalowania (zoom) w tej wersji nie da się ustawić z CLI.
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
vncviewer -RemoteResize=0 -ReconnectOnError=0 127.0.0.1::"$PORT" &
VPID=$!
HPID=""
if [ "${RETRONIC_DOPASUJ_OKNO:-1}" != "0" ]; then
  python3 -I "$DIR/dopasuj_okno.py" --port "$PORT" --pid "$VPID" &
  HPID=$!
fi
# podgląd (ten skrypt) zabity przez sesja.sh albo terminal: zabij też vncviewera i helpera (dawniej exec = jeden proces)
# RETRONIC_TRZYMAJ_OKNO=1: nadzorca trzyma okno pływające i w rozmiarze sesji (trzymaj_okno.sh, kończy się z vncviewerem); domyślnie wyłączony
TPID=""
if [ "${RETRONIC_TRZYMAJ_OKNO:-0}" = "1" ]; then "$DIR/trzymaj_okno.sh" "$VPID" & TPID=$!; fi
koniec() { kill "$VPID" ${HPID:+"$HPID"} ${TPID:+"$TPID"} 2>/dev/null || true; }
trap 'koniec; exit 143' TERM INT HUP
wait "$VPID"; status=$?
[ -n "$HPID" ] && kill "$HPID" 2>/dev/null || true
[ -n "$TPID" ] && kill "$TPID" 2>/dev/null || true
exit "$status"
