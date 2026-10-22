#!/bin/bash
# Przełącznik głosowych alarmów "<nick> pomocy, <powód>" (glos.py). Działa od razu we wszystkich botach (plik sprawdzany przy
# każdym alarmie, bez restartu). Bez argumentu przełącza; "on"/"off" ustawia; "status" pokazuje. Dymki i telefon bez zmian.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
F="$DIR/glos_wylaczony"
ustaw() {
  if [ "$1" = off ]; then touch "$F"; m="Głos alarmów: WYŁĄCZONY"; else rm -f "$F"; m="Głos alarmów: WŁĄCZONY"; fi
  echo "$m"; notify-send -a Retronic -t 3000 "Retronic" "$m" 2>/dev/null
}
case "${1:-}" in
  on) ustaw on ;;
  off) ustaw off ;;
  status) [ -e "$F" ] && echo "wyłączony" || echo "włączony" ;;
  "") [ -e "$F" ] && ustaw on || ustaw off ;;
  *) echo "użycie: ./glos.sh [on|off|status]" >&2; exit 2 ;;
esac
