#!/bin/bash
# Start klienta gry INSTANCJI (RETRONIC_ID=<id>): własny WINEPREFIX i katalog gry, gra jako potomek strażnika
# (socket retronic-<id>.sock). Wywołuje to sesja.sh w zagnieżdżonym sway; ręcznie zwykle niepotrzebne.
# Domyślna (jedyna dziś) gra startuje przez ../retronic.sh i tego pliku nie dotyka.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
INST=$(python3 -I "$DIR/instancja.py" powloka) || exit 1; eval "$INST"
[ -n "$RETRONIC_ID" ] || { echo "uruchom_gre.sh: ustaw RETRONIC_ID (domyślna gra: ../retronic.sh)" >&2; exit 2; }
[ -d "$INST_PREFIX" ] && [ -d "$INST_GRA" ] || { echo "brak $INST_PREFIX lub $INST_GRA: najpierw ./nowa_instancja.sh $RETRONIC_ID" >&2; exit 1; }
export WINEPREFIX="$INST_PREFIX"
export WINEDEBUG=-all
cd "$INST_GRA" || exit 1
EXE="${1:-RetronicGL.exe}"
[ -f "$EXE" ] || { echo "brak $INST_GRA/$EXE (nowa_instancja.sh kopiuje exe i dll)" >&2; exit 1; }
if python3 -I -c 'import numpy' 2>/dev/null; then
    exec python3 -I "$DIR/straznik.py" wine "$EXE"
fi
exec wine "$EXE"
