#!/bin/bash
# Ręczne "Wróć do miasta": bot tej instancji idzie do depo i tam staje (plik STOP, powiadomienie), bez zakupów i powrotu na spot.
# Zostawia plik WROC w katalogu stanu instancji; bot zabiera go sam w najbliższej spokojnej chwili (po walce i locie,
# wyprawa.py). --anuluj usuwa plik, o ile wyprawa jeszcze nie ruszyła (w marszu: ./zatrzymaj.sh). Nie rusza gry.
# Odmawia, gdy bot (mozg|cavebot) tej instancji nie działa. RETRONIC_ID wybiera instancję.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
INST=$(python3 -I "$DIR/instancja.py" powloka) || exit 1; eval "$INST"   # RETRONIC_ID -> INST_* (bez ID: dzisiejsze ścieżki)
TYTUL="Wróć do miasta${RETRONIC_ID:+ [$RETRONIC_ID]}"
pidy() { python3 -I "$DIR/instancja.py" pidy '(mozg|cavebot)\.py'; }   # tylko bot tej instancji
WROC="$INST_STAN/WROC"
case "${1:-}" in
  "") ;;
  --anuluj)
    if [ -e "$WROC" ]; then
      rm -f "$WROC"; notify-send "$TYTUL" "Zlecenie anulowane"; echo "zlecenie anulowane"
    else
      notify-send "$TYTUL" "Brak zlecenia do anulowania (wyprawa mogła już ruszyć: ./zatrzymaj.sh)"; echo "brak zlecenia (w marszu: ./zatrzymaj.sh)"
    fi
    exit 0 ;;
  *) echo "użycie: ./wroc.sh [--anuluj]" >&2; exit 2 ;;
esac
p=$(pidy | head -1)
[ -n "$p" ] || { notify-send "$TYTUL" "Bot nie działa: uruchom go (./uruchom.sh), potem wywołaj ponownie"; echo "bot nie działa, uruchom: ./uruchom.sh" >&2; exit 1; }
mkdir -p "$INST_STAN"
touch "$WROC"
notify-send "$TYTUL" "Zlecenie przyjęte: bot ruszy w najbliższej spokojnej chwili (anuluj: ./wroc.sh --anuluj)"
echo "zlecenie przyjęte (bot pid $p), anuluj: ./wroc.sh --anuluj"
