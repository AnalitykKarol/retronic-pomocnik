#!/bin/bash
# Obserwator ręcznych przejęć Karola razem z botem (decyzja Karola 15.10, SPEC D3 Q4): uruchom.sh woła "start", zatrzymaj.sh "stop".
#   obserwator_z_botem.sh start|stop
# RETRONIC_OBSERWATOR=0 -> nic nie robi (domyślnie 1). RETRONIC_OBSERWATOR_SKRYPT=<ścieżka> podmienia obserwator_reczny.sh (testy).
# Idempotentny (obserwator_reczny.sh sam sprawdza, czy już działa) i best effort: błąd obserwatora nigdy nie psuje startu ani stopu bota.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
if [ "${RETRONIC_OBSERWATOR:-1}" = "0" ]; then
  echo "obserwator: wyłączony (RETRONIC_OBSERWATOR=0)"
  exit 0
fi
case "${1:-}" in
  start|stop) ;;
  *) echo "użycie: $0 start|stop" >&2; exit 0 ;;
esac
SK="${RETRONIC_OBSERWATOR_SKRYPT:-$DIR/obserwator_reczny.sh}"
if [ ! -x "$SK" ]; then
  echo "obserwator: brak skryptu $SK" >&2
  exit 0
fi
echo "obserwator: $(timeout 10 "$SK" "$1" 2>&1 | tail -1)"
exit 0
