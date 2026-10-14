#!/bin/bash
# Start bota Retronic (mozg.py hybryda). Trasa: thais_szczury (Thais z8); rook: --trasa patrol (albo kanaly2, kanaly3). Odmawia, gdy bot już działa albo brak gry.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
INST=$(python3 -I "$DIR/instancja.py" powloka) || exit 1; eval "$INST"   # RETRONIC_ID -> INST_* (bez ID: dzisiejsze ścieżki)
TYTUL="Bot Retronic${RETRONIC_ID:+ [$RETRONIC_ID]}"
pidy() { python3 -I "$DIR/instancja.py" pidy '(mozg|cavebot)\.py'; }   # tylko bot tej instancji
SOCK="$INST_SOCK"
p=$(pidy | head -1)
[ -n "$p" ] && { notify-send "$TYTUL" "Bot już działa (pid $p)"; echo "bot już działa" >&2; exit 1; }
[ -S "$SOCK" ] || { notify-send "$TYTUL" "Gra nie działa (brak socketu)"; echo "brak socketu gry" >&2; exit 1; }
rm -f "$INST_STOP" "$INST_STOP_RECZNY"
mkdir -p "$INST_LOGI"
cd "$DIR" || exit 1
LOG="$INST_LOGI/mozg-stdout-$(date +%m%d-%H%M).log"
# na powierzchni (z7) bot najpierw przechodzi dojście do kanałów (dziura 32360,32241), na z8 startuje od razu
DOJSCIE=()
Z=$(python3 -I -c "
import os,socket,json
s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect('$SOCK')
s.sendall(b'{\"cmd\":\"pozycja\",\"nazwa\":\"${RETRONIC_POSTAC:-Jointoramix}\"}\n');print(json.loads(s.recv(400))['pozycja']['z'])" 2>/dev/null)
# MAPA (mapy.json: miejsce i moby) i TRYB (tryby.json: zachowanie, kilka po przecinku) są opcjonalne:
#   MAPA=raty TRYB=sredni,runy ./uruchom.sh   Bez obu zmiennych zachowanie jak dotąd (raty, bieżący na_zywo.json).
MAPA_TRASA=thais_szczury_opt; MAPA_POTWORY=Rat; MAPA_PROG_HP=30; MAPA_DOJSCIE=thais_dojscie
# Ostatnio uruchomiona mapa i tryb (guzik na pasku i panel wołają skrypt bez zmiennych): bez MAPA/TRYB
# bierzemy to, co ostatnio działało; z MAPA/TRYB zapisujemy dla następnego razu.
OSTATNI="$DIR/ostatni_start${RETRONIC_ID:+.$RETRONIC_ID}.env"
if [ -z "$MAPA$TRYB" ] && [ -f "$OSTATNI" ]; then
  . "$OSTATNI"
elif [ -n "$MAPA$TRYB" ]; then
  printf 'MAPA=%q\nTRYB=%q\n' "$MAPA" "$TRYB" > "$OSTATNI"
fi
if [ -n "$MAPA$TRYB" ]; then
  WYN=$(python3 -I "$DIR/tryb.py" --mapa "${MAPA:-raty}" --tryb "${TRYB:-}") || { notify-send "$TYTUL" "Błąd mapy/trybu (patrz terminal)"; exit 1; }
  eval "$WYN"
fi
[ "$Z" = "7" ] && [ -n "$MAPA_DOJSCIE" ] && DOJSCIE=(--dojscie "$MAPA_DOJSCIE")
# P4 (13.10): telemetria pisze tylko z tą zmienną (testy i skrypty pomocnicze jej nie mają)
export RETRONIC_TELEMETRIA=1
setsid nohup python3 -I -u mozg.py --tryb hybryda --model haiku --trasa "$MAPA_TRASA" "${DOJSCIE[@]}" --potwory "$MAPA_POTWORY" --prog-hp "$MAPA_PROG_HP" > "$LOG" 2>&1 < /dev/null &
notify-send "$TYTUL" "Start (mozg hybryda, $MAPA_TRASA${TRYB:+, tryb $TRYB}${DOJSCIE:+ + dojście})"
