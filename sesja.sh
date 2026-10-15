#!/bin/bash
# Uruchamia Retronic w osobnej, zagnieżdżonej sesji sway. Domyślnie bez okna (headless) z podglądem VNC na pulpicie:
# gra i bot działają niezależnie od tego, co jest na ekranie; podgląd można zamknąć i otworzyć ponownie (podglad.sh).
# W tej sesji gra jest jedynym oknem i zawsze ma fokus, więc klawisze wysłane
# przez `klawisz.sh` trafiają do gry, nawet gdy pracujesz w innym oknie.
# Sesja kończy się razem z grą (podgląd też).
# RETRONIC_ID=<id> sesja.sh: osobna sesja instancji (retronic-sesja-<id>, własny sway/WAYLAND_DISPLAY, własny prefix wine).
set -euo pipefail

DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
if [ -z "${RETRONIC_ID:-}" ]; then
  STAN="${XDG_RUNTIME_DIR:-/tmp}/retronic-sesja"
  START_GRY="$HOME/Games/Retronic/retronic.sh"
  ZATRZYMAJ="$HOME/Games/Retronic/pomocnik/zatrzymaj.sh"
  EXTRA=""
else
  INST=$(python3 -I "$DIR/instancja.py" powloka)
  eval "$INST"
  STAN="$INST_SESJA"
  START_GRY="$DIR/uruchom_gre.sh"
  ZATRZYMAJ="env RETRONIC_ID=$RETRONIC_ID $DIR/zatrzymaj.sh"
  EXTRA="exec sh -c 'printf \"%s\" \"\$SWAYSOCK\" > \"$STAN/swaysock\"'"
  export RETRONIC_ID
fi
# RETRONIC_BEZ_OKNA=1 (domyślnie od 14.10): sway z backendem headless (wirtualny output, brak okna sway na pulpicie
# hosta). Render i grim działają niezależnie od widoczności, bo nic nie zależy od klatek kompozytora hosta.
# W sesji działa wayvnc (127.0.0.1, port w $STAN/vnc_port), a na pulpicie otwiera się vncviewer z myszą i klawiaturą.
# RETRONIC_BEZ_OKNA=0: dawny tryb z oknem (bot staje, gdy okno jest niewidoczne).
# RETRONIC_BEZ_OKNA_ROZ=SZERxWYS (domyślnie 800x910). RETRONIC_PODGLAD=0: bez automatycznego podglądu
# (wayvnc i tak działa, podglad.sh otwiera go później). RETRONIC_PODGLAD_PORT: port VNC (domyślnie 5901, instancje 5902+).
BEZ_OKNA="${RETRONIC_BEZ_OKNA:-1}"
ROZ="${RETRONIC_BEZ_OKNA_ROZ:-800x910}"   # klient z 13.10 rysuje min. 800 px szerokości; przy 734 prawy panel był ucięty (14.10)
if [ -z "${RETRONIC_ID:-}" ]; then PORT_DOM=5901; else PORT_DOM=$((5902 + $(printf '%s' "$RETRONIC_ID" | cksum | cut -d' ' -f1) % 90)); fi
PORT="${RETRONIC_PODGLAD_PORT:-$PORT_DOM}"
OUTPUT_KONF=""
VNC_KONF=""
if [ "$BEZ_OKNA" = "1" ]; then
  OUTPUT_KONF="output * resolution $ROZ"
  VNC_KONF="exec wayvnc 127.0.0.1 $PORT"
fi
mkdir -p "$STAN"
rm -f "$STAN/wayland" "$STAN/vnc_port"

cat > "$STAN/sway.conf" <<EOF2
# Wygenerowane przez pomocnik/sesja.sh, bez skrótów i bez configu użytkownika.
bindsym Mod4+Shift+F12 exec $ZATRZYMAJ
default_border none
default_floating_border none
output * bg #101010 solid_color
${OUTPUT_KONF:+$OUTPUT_KONF
}for_window [class=".*"] floating disable, fullscreen enable
exec sh -c 'printf "%s" "\$WAYLAND_DISPLAY" > "$STAN/wayland"'
${EXTRA:+$EXTRA
}${VNC_KONF:+$VNC_KONF
}exec sh -c '"$START_GRY"; swaymsg exit'
EOF2

PODGLAD_PID=""
if [ "$BEZ_OKNA" = "1" ]; then
  printf '%s' "$PORT" > "$STAN/vnc_port"
  if [ "${RETRONIC_PODGLAD:-1}" = "1" ]; then
    "$DIR/podglad.sh" --czekaj > "$STAN/podglad.log" 2>&1 &
    PODGLAD_PID=$!
  fi
fi

if [ "$BEZ_OKNA" = "1" ]; then
  export WLR_BACKENDS=headless WLR_HEADLESS_OUTPUTS=1
  # gles2 = render na GPU (XWayland dostaje kartę, gra: "OpenGL ... NVIDIA"); pixman = render programowy (Mesa, ~1,6 rdzenia
  # na klienta). Przy szerokości 734 grim na gles2 dawał "Invalid stride"; przy 800 działa (14.10). Awaryjnie: WLR_RENDERER=pixman
  export WLR_RENDERER="${WLR_RENDERER:-gles2}"
  export WLR_LIBINPUT_NO_DEVICES=1
else
  export WLR_BACKENDS=wayland WLR_WL_OUTPUTS=1
fi
status=0
sway --unsupported-gpu -c "$STAN/sway.conf" > "$STAN/sway.log" 2>&1 || status=$?
# koniec gry = koniec podglądu (także otwartego później przez podglad.sh)
[ -n "$PODGLAD_PID" ] && kill "$PODGLAD_PID" 2>/dev/null || true
pkill -f "^vncviewer .*127\.0\.0\.1::$PORT\b" 2>/dev/null || true
rm -f "$STAN/vnc_port"
exit "$status"
