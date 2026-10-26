#!/bin/bash
# Jedna klatka podglądu sesji gry instancji na stdout (JPEG). TYLKO ODCZYT (grim na sesji sway tej instancji), zero inputu do gry.
#   ./podglad_klatka.sh <id> [skala]      domyślnie skala 0.6 (ok. 700x550, ~40 KB)
id_="$1"; skala="${2:-0.6}"
[[ "$id_" =~ ^[a-z0-9_-]+$ ]] || { echo "zle id" >&2; exit 2; }
uid_=$(id -u); kat="/run/user/$uid_/retronic-sesja-$id_"
[ -r "$kat/wayland" ] || { echo "brak sesji $id_" >&2; exit 1; }
XDG_RUNTIME_DIR="/run/user/$uid_" WAYLAND_DISPLAY="$(cat "$kat/wayland")" exec grim -t jpeg -q 60 -s "$skala" -
