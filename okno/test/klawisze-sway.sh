#!/bin/bash
# Prawdziwe klawisze w prawdziwym kompozytorze: okno na ATRAPIE w headless sway (osobny WAYLAND_DISPLAY, żadnego okna na pulpicie),
# klawisze przez wtype, zrzuty przez grim. Sprawdza Ctrl+K, pisanie w wyszukiwarce, strzałki, Enter (przejście do pokrętła), Esc, Ctrl+K jako przełącznik.
# Użycie: okno/test/klawisze-sway.sh KATALOG_WYNIKOW     Wymaga: sway, wtype, grim, quickshell. Kończy własny sway i quickshell.
set -u
OUT="${1:?podaj katalog wyników}"
DOM="$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)"
mkdir -p "$OUT"
for t in sway wtype grim quickshell; do command -v "$t" >/dev/null || { echo "brak $t"; exit 2; }; done
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
eval "$(python3 "$DOM/okno/test/atrapa.py" "$WORK")"
cat > "$WORK/sway.conf" <<CONF
default_border none
default_floating_border none
output * resolution 1280x820
exec bash $WORK/wnetrze.sh
CONF
# Jedno wywołanie wtype = jedna wirtualna klawiatura (kolejne wywołania zmieniają mapę klawiszy i Qt gubi fokus okna). Klawiatura powstaje PRZED
# oknem (sleep 8 s), potem idzie cały scenariusz klawiszy; zrzuty grim są w tle w tych samych momentach.
cat > "$WORK/wnetrze.sh" <<INNER
cd "$DOM"
wtype -s 8000 -M ctrl -k k -m ctrl -s 1500 "uh koszt" -s 1200 -k Down -s 700 -k Up -s 500 -k Return -s 2200 -M ctrl -k k -m ctrl -s 1200 -k Escape -s 1200 -M ctrl -k k -m ctrl -s 1000 -M ctrl -k k -m ctrl -s 1200 &
WT=\$!
QT_QPA_PLATFORM=wayland quickshell -p "$DOM/okno" > "$OUT/sway-qs.log" 2>&1 &
QS=\$!
T0=\$(date +%s.%N)
at() { sleep "\$(awk -v t0="\$T0" -v x="\$1" -v n="\$(date +%s.%N)" 'BEGIN { d = t0 + x - n; if (d < 0) d = 0; print d }')"; }
( at 6.0;  grim "$OUT/sway-1-start.png"
  at 8.7;  grim "$OUT/sway-2-ctrlk-pusty.png"
  at 10.2; grim "$OUT/sway-3-ctrlk-uh-koszt.png"
  at 11.2; grim "$OUT/sway-4-strzalka-w-dol.png"
  at 13.0; grim "$OUT/sway-5-po-enter.png"
  at 14.7; grim "$OUT/sway-6-ctrlk-ponownie.png"
  at 16.0; grim "$OUT/sway-7-po-esc.png"
  at 18.3; grim "$OUT/sway-8-ctrlk-dwa-razy-zamkniete.png" ) &
wait \$WT
sleep 2
kill \$QS 2>/dev/null
swaymsg exit
INNER
WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 WLR_RENDERER=pixman timeout 90 sway -c "$WORK/sway.conf" > "$OUT/sway.log" 2>&1
echo "zrzuty w $OUT (sway-*.png), log quickshella: $OUT/sway-qs.log"
