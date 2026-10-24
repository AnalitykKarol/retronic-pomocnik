#!/usr/bin/env bash
# Wyłącza sklep instancji <id>: zabija TYLKO proces mozg.py --bez-ruchu tej instancji (po RETRONIC_ID w /proc; gra, strażnik, sway, wine
# i cudze boty zostają), cofa pokrętła TRADE_OGLOSZENIA / TRADE_PRIV_ODPOWIEDZI w instancje/<id>/na_zywo.json (trade_sklep.py wylacz)
# i, gdy coś zatrzymano, zostawia STOP i STOP_RECZNY (stan jak przed startem sklepu; kasuje je dopiero trade_start.sh --usun-stop albo
# uruchom.sh). Na koniec odczyt zrzutu: ostrzega, gdy aktywna zakładka czatu to nie Default (zabicie w trakcie wysyłki).
# Użycie: ./trade_stop.sh <id>        np. ./trade_stop.sh kutangen
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
ID="${1:-${RETRONIC_ID:-}}"
[ -n "$ID" ] && [ "${1:-}" != "-h" ] || { echo "użycie: $0 <id>" >&2; exit 2; }
[ -d "$DIR/instancje/$ID" ] || { echo "brak instancji '$ID' (instancje/$ID)" >&2; exit 1; }
export RETRONIC_ID="$ID"
eval "$(python3 -I "$DIR/instancja.py" powloka)" || exit 1
cd "$DIR" || exit 1
pidy() { python3 -I "$DIR/instancja.py" pidy 'mozg\.py .*--bez-ruchu'; }
pids=$(pidy | tr '\n' ' ')
python3 -I "$DIR/trade_sklep.py" wylacz || echo "UWAGA: nie cofnąłem pokręteł Trade w $INST_NA_ZYWO" >&2
if [ -z "$pids" ]; then
  echo "Nie działa (brak mozg.py --bez-ruchu instancji '$ID')."
  exit 0
fi
kill $pids
for _ in 1 2 3 4 5 6 7 8 9 10; do
  sleep 1
  [ -z "$(pidy)" ] && break
done
if [ -n "$(pidy)" ]; then kill -9 $(pidy); echo "Zabito (SIGKILL) PID $pids"; else echo "Zatrzymano PID $pids"; fi
touch "$INST_STOP" "$INST_STOP_RECZNY"
# kontrola (tylko odczyt): aktywna zakładka czatu; zrzut tej instancji
python3 -I -c "
import sys; sys.path.insert(0, '$DIR')
try:
    import ekran, mozg
    st = mozg.stan_zakladek(ekran.zrzut())
    print('Zakładki czatu:', st)
    if st.get('Default') != 'aktywna':
        print('UWAGA: aktywna nie jest zakładka Default: kliknij Default, zanim ktoś coś wpisze.')
except Exception as e:
    print('Zakładki czatu: nie odczytano (%r)' % (e,))
" 2>/dev/null
