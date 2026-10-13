#!/bin/bash
# Cienka nakładka: start bota instancji <id> na mapie z mapy.json i trybie z tryby.json (jak uruchom.sh).
# Użycie: ./uruchom_instancje.sh <id> <MAPA> [TRYB]      np. ./uruchom_instancje.sh dwa trolle_patrol sredni,runy
# Gra instancji musi już działać (RETRONIC_ID=<id> ./sesja.sh, postać zalogowana); inaczej uruchom.sh odmówi.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
ID="${1:-}"; MAPA_ARG="${2:-}"; TRYB_ARG="${3:-}"
[ -n "$ID" ] && [ -n "$MAPA_ARG" ] || { echo "użycie: $0 <id> <MAPA> [TRYB]" >&2; exit 2; }
[ -d "$DIR/instancje/$ID" ] || { echo "brak instancji '$ID': najpierw ./nowa_instancja.sh $ID" >&2; exit 1; }
export RETRONIC_ID="$ID"
export MAPA="$MAPA_ARG" TRYB="$TRYB_ARG"
exec "$DIR/uruchom.sh"
