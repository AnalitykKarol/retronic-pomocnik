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
mkdir -p "$INST_LOGI"
cd "$DIR" || exit 1
LOG="$INST_LOGI/mozg-stdout-$(date +%m%d-%H%M).log"
# 22.10: start z paska/panelu/nadzoru bywa bez RETRONIC_POSTAC; strażnik pyta o pozycję PO NICKU, więc z pustym nickiem piętro
# wychodziło puste i dojście na spot było pomijane po cichu (odchyd 17:41, kutangen 21.10). Z ID nick bierzemy z profilu instancji
# (profil.json, pole postac); domyślny Jointoramix zostaje tylko dla instancji bez ID.
if [ -z "${RETRONIC_POSTAC:-}" ] && [ -n "${RETRONIC_ID:-}" ]; then
  RETRONIC_POSTAC=$(python3 -I -c "
import sys,json; sys.path.insert(0,sys.argv[1]); import profil
try: p=profil.wczytaj(sys.argv[2])
except Exception:
    try: p=json.load(open(sys.argv[2]+'/profil.json'))   # profil bez proxy/IP nie startuje gry, ale nick z niego nadal czytelny
    except Exception: p={}
print((p.get('postac') or '').strip())" "$DIR" "$INST_STAN" 2>/dev/null)
  export RETRONIC_POSTAC
fi
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
# mapa z "dojscie_z_dowolnego_pietra" (np. rook_bugi_z10) przechodzi dojście od najbliższego punktu także ze z8/z9/z10
{ [ "$Z" = "7" ] || [ -n "${MAPA_DOJSCIE_WSZEDZIE:-}" ]; } && [ -n "$MAPA_DOJSCIE" ] && DOJSCIE=(--dojscie "$MAPA_DOJSCIE")
# 22.10: bez piętra nie wiemy, czy dojście jest potrzebne; mapa z dojściem (nie "z dowolnego piętra") + puste piętro = głośna odmowa,
# nigdy cichy start bez dojścia (bot wbija się w ścianę w mieście). Pliki STOP nietknięte.
if [ -z "$Z" ] && [ -n "$MAPA_DOJSCIE" ] && [ -z "${MAPA_DOJSCIE_WSZEDZIE:-}" ]; then
  MSG="Nie znam piętra postaci '${RETRONIC_POSTAC:-?}' (strażnik nie zwrócił pozycji): bez tego dojście '$MAPA_DOJSCIE' byłoby pominięte. Start wstrzymany."
  notify-send -u critical "$TYTUL" "$MSG"; echo "$MSG" >&2; exit 3
fi
rm -f "$INST_STOP" "$INST_STOP_RECZNY" "$INST_STAN/WROC"   # stare zlecenie "Wróć do miasta" nie przeżywa restartu (po odmowach, żeby odmowa niczego nie kasowała)
# P4 (13.10): telemetria pisze tylko z tą zmienną (testy i skrypty pomocnicze jej nie mają)
export RETRONIC_TELEMETRIA=1
setsid nohup python3 -I -u mozg.py --tryb "${MOZG_TRYB:-skrypt}" --model haiku --trasa "$MAPA_TRASA" "${DOJSCIE[@]}" --potwory "$MAPA_POTWORY" --prog-hp "$MAPA_PROG_HP" ${MOZG_BEZ_RUCHU:+--bez-ruchu} > "$LOG" 2>&1 < /dev/null &
# dymek startu wysyła mozg.py ("Bot ruszył"), gdy bot naprawdę wystartuje (14.10: bez dubla)
# 15.10 (SPEC D3 Q4): obserwator ręcznych przejęć startuje razem z botem (etykiety dla modeli); RETRONIC_OBSERWATOR=0 = nie startuj
"$DIR/obserwator_z_botem.sh" start
echo "Start (mozg ${MOZG_TRYB:-skrypt}, $MAPA_TRASA${TRYB:+, tryb $TRYB}${DOJSCIE:+ + dojście})"
