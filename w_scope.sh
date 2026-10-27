#!/bin/bash
# Wrapper: długo żyjące procesy gry i bota we WŁASNEJ przejściowej jednostce systemd (scope), nie w cgroupie tego, kto je wywołał.
#   w_scope.sh <rodzaj> <polecenie> [argumenty...]       rodzaj: sesja | bot | podglad | obserwator | refill | relog | ...
# Dlaczego (incydent 26.10): okno zarządzania działa jako retronic-okno.service, a sesje gry i boty startowane z okna były jego procesami
# potomnymi (cgroup). `quickshell -p okno kill` / `systemctl --user stop retronic-okno` (KillMode=control-group) zabiło wszystkie sesje i boty.
# setsid ani nohup tego nie zmieniają: cgroup dziedziczy się po rodzicu. Jednostka retronic-<rodzaj>-<id>-<GGMMSS>.scope jest osobna;
# kończy się, gdy zniknie ostatni jej proces, i nic wspólnego z oknem, nadzorem ani powłoką już nie ma.
# Skutki:
#  - systemd-run --scope robi `exec` (przez bash -c 'exec "$@"', patrz niżej): PID, cmdline (pgrep -f, okno_api.skan_procesow), środowisko (RETRONIC_ID), sesja i grupa
#    procesów są te same co bez wrappera; dzieci (sway, Xwayland, wine, wayvnc, siec_proxy.sh) dziedziczą scope.
#  - dalej nic nie zależy od cgroupa: zamknięcie/STOP znajduje procesy po /proc (cmdline + RETRONIC_ID), nie po jednostce.
#  - zatrzymanie całej sesji jednym poleceniem (awaryjnie): systemctl --user stop 'retronic-sesja-<id>-*.scope'.
# Bez scope'a (zwykły exec polecenia): RETRONIC_BEZ_SCOPE=1, RETRONIC_TESTY=1, brak systemd-run albo brak menedżera usług użytkownika,
# oraz gdy proces już siedzi w scope'ie tego samego rodzaju i instancji (np. drugi start z wnętrza sesji).
# Id jednostki: RETRONIC_ID z środowiska ("glowna", gdy puste). Cofnięcie: RETRONIC_BEZ_SCOPE=1 albo usunąć wywołania wrappera.
RODZAJ="${1:-}"
[ -n "$RODZAJ" ] && [ "$#" -ge 2 ] || { echo "użycie: $0 <rodzaj> <polecenie> [argumenty...]" >&2; exit 2; }
shift
bez_scope() { exec "$@"; }
[ "${RETRONIC_BEZ_SCOPE:-0}" = "1" ] && bez_scope "$@"
[ "${RETRONIC_TESTY:-0}" = "1" ] && bez_scope "$@"
command -v systemd-run >/dev/null 2>&1 || bez_scope "$@"
ID=$(printf '%s' "${RETRONIC_ID:-glowna}" | tr -c 'A-Za-z0-9_-' '_')
RODZAJ=$(printf '%s' "$RODZAJ" | tr -c 'A-Za-z0-9_-' '_')
# już w scope'ie tego rodzaju i instancji: bez zagnieżdżania
case "$(cat /proc/self/cgroup 2>/dev/null)" in *"/retronic-$RODZAJ-$ID-"*.scope) bez_scope "$@" ;; esac
# menedżer użytkownika odpowiada? (to samo zapytanie sprawdza wolność nazwy jednostki)
BAZA="retronic-$RODZAJ-$ID-$(date +%H%M%S)"
JEDN="$BAZA"; N=1
while :; do
  stan=$(systemctl --user show -p LoadState --value "$JEDN.scope" 2>/dev/null) || bez_scope "$@"
  [ "$stan" = "loaded" ] || break
  N=$((N + 1)); JEDN="$BAZA-$N"
  [ "$N" -lt 50 ] || bez_scope "$@"
done
# systemd-run podmienia argv[0] na pełną ścieżkę z PATH (/usr/bin/python3, /usr/bin/bash), co zmieniłoby cmdline, po którym szukają
# procesów pgrep -f i instancja.py (wzorce `^bash refill.sh`, `python3 -I -u mozg.py`). Dlatego krótki `bash -c 'exec "$@"'`:
# ten sam PID, a polecenie dostaje argv[0] dokładnie takie, jak je podano.
exec systemd-run --user --scope --quiet --collect --unit="$JEDN" --description="Retronic $RODZAJ $ID" -- /bin/bash -c 'exec "$@"' w_scope "$@"
