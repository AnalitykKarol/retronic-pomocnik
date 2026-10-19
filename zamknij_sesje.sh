#!/bin/bash
# Zamyka sesję headless Retronic (sway, wayvnc, wine, strażnik, podgląd, helpery). Nie rusza niczego innego.
for p in $(pgrep -f 'pomocnik/dopasuj_okno.py|^/bin/bash ./podglad.sh|^/bin/bash ./sesja.sh|trzymaj_okno.sh [0-9]'); do
  [ "$p" = "$$" ] || [ "$p" = "$PPID" ] || kill -TERM "$p" 2>/dev/null
done
pkill -TERM -x vncviewer; pkill -TERM -x wayvnc
for p in $(pgrep -f 'pomocnik/straznik.py'); do kill -TERM "$p" 2>/dev/null; done
sleep 1; pkill -TERM -x sway
sleep 4
for p in $(pgrep -f 'RetronicGL'); do kill -TERM "$p" 2>/dev/null; done
sleep 2; wineserver -k 2>/dev/null; sleep 1
ps -eo pid,etime,args | grep -Ei 'vncviewer|wayvnc|sway|straznik|wine|RetronicGL|sesja\.sh|podglad|dopasuj|trzymaj' | grep -v -e grep -e zamknij_sesje | cut -c1-120
echo "--- koniec listy (pusta = wszystko zamknięte)"
