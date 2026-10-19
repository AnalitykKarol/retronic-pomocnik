#!/bin/bash
# Uruchamia klienta Retronic przez Wine z osobnym prefiksem.
# Gra startuje jako potomek strażnika (pomocnik/straznik.py), który daje
# odczyt jej pamięci bez sudo. Jeśli strażnik nie wystartuje, gra rusza normalnie.
export WINEPREFIX="$HOME/Games/Retronic/prefix"
export WINEDEBUG=-all
# opcje klienta wymuszane przed startem (pomocnik/ustawienia_klienta.py: priv we własnych zakładkach)
python3 -I "$HOME/Games/Retronic/pomocnik/ustawienia_klienta.py" "$WINEPREFIX" || true
cd "$HOME/Games/Retronic" || exit 1
if python3 -I -c 'import numpy' 2>/dev/null; then
    exec python3 -I pomocnik/straznik.py wine "${1:-RetronicGL.exe}"
fi
exec wine "${1:-RetronicGL.exe}"
