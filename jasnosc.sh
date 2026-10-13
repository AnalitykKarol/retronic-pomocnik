#!/bin/bash
# Przełącznik rozjaśnienia CAŁEGO ekranu (shader Hyprland). Bez argumentu: toggle. Argumenty: on | off | status
# Nic nie zapisuje w configu Hyprland, po restarcie Hyprland wraca do normy.
DIR="$(cd "$(dirname "$0")" && pwd)"
SHADER="$DIR/jasnosc.frag"
STAN="${XDG_RUNTIME_DIR:-/tmp}/retronic-jasnosc"
cur=$(hyprctl getoption decoration:screen_shader 2>/dev/null | awk -F': ' '/^str:/{print $2}')
case "${1:-toggle}" in
  status) [[ "$cur" == "$SHADER" ]] && echo on || echo off; exit 0 ;;
  on) want=on ;;
  off) want=off ;;
  *) [[ "$cur" == "$SHADER" ]] && want=off || want=on ;;
esac
if [[ $want == on ]]; then
  hyprctl keyword decoration:screen_shader "$SHADER" >/dev/null
  echo on > "$STAN"; notify-send -t 2000 "Retronic" "Rozjaśnienie włączone"
else
  hyprctl keyword decoration:screen_shader "" >/dev/null
  echo off > "$STAN"; notify-send -t 2000 "Retronic" "Rozjaśnienie wyłączone"
fi
