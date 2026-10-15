#!/bin/bash
# Start bota na trollach (troll_cave, z8+z9, trasa wielopiętrowa). Postać ma stać na z8 przy punkcie 0 (32493,32260). Odmawia, gdy bot już działa albo brak gry.
# Domyślnie pętla troll_cave. Zmienna TRASA wybiera inną trasę albo tryb:
#   TRASA=patrol:troll ./uruchom_trolle.sh   mapa spotu trolli (z8+z9): patrol po miejscach z trasy/miejsca_troll.json,
#                                            między miejscami po grafie schodów (trasa awaryjna: pole "trasa" z pliku)
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
# na powierzchni (z7, np. przy depo) bot najpierw przechodzi nagrane dojście do troll_cave (dziura 32493,32259), na z8 startuje od razu
DOJSCIE=()
LOG="$INST_LOGI/mozg-stdout-$(date +%m%d-%H%M).log"
# P7g (13.10): odczyt piętra ponawiamy 3 razy po 1 s i logujemy wartość; gdy nadal pusty, dojście i tak jest
# przekazane (--dojscie-jesli-z7: mozg.py sam sprawdza piętro po starcie i pomija dojście, gdy z != 7)
Z=""
for _p in 1 2 3; do
  Z=$(python3 -I -c "
import os,socket,json
s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect('$SOCK')
s.sendall(b'{\"cmd\":\"pozycja\",\"nazwa\":\"${RETRONIC_POSTAC:-Jointoramix}\"}\n');print(json.loads(s.recv(400))['pozycja']['z'])" 2>/dev/null)
  [ -n "$Z" ] && break
  sleep 1
done
echo "$(date +%T) uruchom_trolle: odczytane piętro Z='${Z}'" >> "$LOG" 2>/dev/null
if [ "$Z" = "7" ]; then
  DOJSCIE=(--dojscie depo_troll_cave)
elif [ -z "$Z" ]; then
  notify-send "$TYTUL" "Nie znam piętra postaci: dojście z depo zdecyduje mozg po starcie"
  DOJSCIE=(--dojscie depo_troll_cave --dojscie-jesli-z7)
fi
# BEZ_DOJSCIA=1: start bez dojścia z depo (np. najpierw wyprawa po blanki/jedzenie; wyprawa nie startuje w trakcie dojścia)
[ "${BEZ_DOJSCIA:-0}" = "1" ] && DOJSCIE=()
# WYMUS_DOJSCIE=1: dojście także poza z7 (np. postać już zeszła pod ziemię; mozg startuje od najbliższego punktu na jej piętrze)
[ "${WYMUS_DOJSCIE:-0}" = "1" ] && DOJSCIE=(--dojscie depo_troll_cave)
# Opcjonalnie MAPA=trolle_nowe (mapy.json) zamiast TRASA, TRYB=sredni,runy (tryby.json). Bez obu zmiennych bez zmian.
if [ -n "$MAPA$TRYB" ]; then
  printf 'MAPA=%q\nTRYB=%q\n' "$MAPA" "$TRYB" > "$DIR/ostatni_start${RETRONIC_ID:+.$RETRONIC_ID}.env"   # guzik/panel (uruchom.sh) startuje ostatni tryb
  WYN=$(python3 -I "$DIR/tryb.py" --mapa "${MAPA:-trolle}" --tryb "${TRYB:-}") || exit 1
  eval "$WYN"; [ -n "$MAPA" ] && TRASA="$MAPA_TRASA"
  # dojście z mapy (mapy.json "dojscie"), np. edron_depo_trolle zamiast domyślnego depo_troll_cave
  [ -n "$MAPA_DOJSCIE" ] && [ ${#DOJSCIE[@]} -gt 0 ] && DOJSCIE[1]="$MAPA_DOJSCIE"
fi
# P4 (13.10): telemetria pisze tylko z tą zmienną (testy i skrypty pomocnicze jej nie mają)
export RETRONIC_TELEMETRIA=1
setsid nohup python3 -I -u mozg.py --tryb hybryda --model haiku --trasa "${TRASA:-troll_cave}" "${DOJSCIE[@]}" --potwory "${MAPA_POTWORY:-Troll}" --prog-hp "${MAPA_PROG_HP:-60}" >> "$LOG" 2>&1 < /dev/null &
notify-send "$TYTUL" "Start (mozg hybryda, ${TRASA:-troll_cave}${DOJSCIE:+ + dojście z depo})"
