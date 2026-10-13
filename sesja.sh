#!/bin/bash
# Uruchamia Retronic w osobnej, zagnieżdżonej sesji sway (okno na pulpicie).
# W tej sesji gra jest jedynym oknem i zawsze ma fokus, więc klawisze wysłane
# przez `klawisz.sh` trafiają do gry, nawet gdy pracujesz w innym oknie.
# Sesja kończy się razem z grą.
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
# RETRONIC_BEZ_OKNA=1: sway z backendem headless (wirtualny output, brak okna na pulpicie hosta). Render i grim
# działają niezależnie od widoczności, bo nic nie zależy od klatek kompozytora hosta. Brak podglądu i ręcznego
# logowania w oknie: patrz INSTANCJE.md (podgląd: wayvnc na gnieździe sesji albo zrzut grim).
# RETRONIC_BEZ_OKNA_ROZ=SZERxWYS (domyślnie 734x910, jak okno dotąd).
BEZ_OKNA="${RETRONIC_BEZ_OKNA:-0}"
ROZ="${RETRONIC_BEZ_OKNA_ROZ:-734x910}"
OUTPUT_KONF=""
if [ "$BEZ_OKNA" = "1" ]; then
  OUTPUT_KONF="output * resolution $ROZ"
fi
mkdir -p "$STAN"
rm -f "$STAN/wayland"

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
}exec sh -c '"$START_GRY"; swaymsg exit'
EOF2

if [ "$BEZ_OKNA" = "1" ]; then
  export WLR_BACKENDS=headless WLR_HEADLESS_OUTPUTS=1
  export WLR_RENDERER="${WLR_RENDERER:-gles2}"
  export WLR_LIBINPUT_NO_DEVICES=1
else
  export WLR_BACKENDS=wayland WLR_WL_OUTPUTS=1
fi
exec sway --unsupported-gpu -c "$STAN/sway.conf" > "$STAN/sway.log" 2>&1
