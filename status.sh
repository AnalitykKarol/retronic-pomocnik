#!/bin/bash
# JSON statusu dla paska: {"text","tooltip","class"}; klasy: dziala, alarm, stop, brak
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
exec python3 -I "$DIR/panel.py" --json
