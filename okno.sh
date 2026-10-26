#!/bin/bash
# Okno zarządzania Retronic (QML, Quickshell): osobny proces od paska (restart paska/powłoki go nie zamyka i odwrotnie).
# Spec: wtyczka-paska/specs/2026-10-19-retronic-okno.md (F2, F3). Jeden egzemplarz: drugi start nie otwiera drugiego okna,
# tylko (w Hyprlandzie) przenosi fokus na istniejące. Okno czyta okno_api.py i woła skrypty bota; samo nic w grze nie robi.
#   ./okno.sh            otwórz okno (albo wyróżnij już otwarte)
# Zmienne (tylko testy/atrapa): RETRONIC_OKNO_KATALOG (dane i skrypty akcji zamiast tego repo), RETRONIC_OKNO_OTWIERACZ.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
QML="$DIR/okno"
command -v quickshell >/dev/null 2>&1 || { echo "brak quickshell w PATH" >&2; exit 1; }

if quickshell -p "$QML" list 2>/dev/null | grep -q '^Instance '; then
  # już otwarte: nie startuj drugiego; wyróżnij istniejące okno, o ile powłoka to umie (Hyprland)
  if [ -n "$HYPRLAND_INSTANCE_SIGNATURE" ] && command -v hyprctl >/dev/null 2>&1; then
    hyprctl dispatch focuswindow 'title:^Retronic · okno zarządzania$' >/dev/null 2>&1
  fi
  exit 0
fi
# 26.10: okno startuje z powłoki Omarchy (quickshell), a ta ma RLIMIT_RTTIME=0 (twardy, dziedziczony). Sway 1.12 (sway/realtime.c) wchodzi
# w czas rzeczywisty i przy takim limicie dostaje SIGKILL po ok. 0,2 s: każda sesja gry startowana z okna (Zaloguj, Uruchom grę) ginęła.
# Przez `systemd-run --user` okno dziedziczy limity menedżera użytkownika (unlimited), reszta środowiska jest ta sama (porównane 26.10).
# RETRONIC_OKNO_BEZ_SYSTEMD=1 (albo brak systemd-run): dawny start bez zmiany limitu. Cofnięcie: okno.sh.bak-20261026-rttime.
if [ "${RETRONIC_OKNO_BEZ_SYSTEMD:-0}" != "1" ] && command -v systemd-run >/dev/null 2>&1; then
  USTAW=()
  for z in RETRONIC_OKNO_KATALOG RETRONIC_OKNO_REPO RETRONIC_OKNO_OTWIERACZ RETRONIC_OKNO_SCENARIUSZ RETRONIC_OKNO_SORT_PLIK QT_QPA_PLATFORM; do
    [ -n "${!z:-}" ] && USTAW+=("--setenv=$z=${!z}")
  done
  exec systemd-run --user --quiet --collect --unit=retronic-okno --description="Retronic: okno zarządzania" \
    --setenv=QS_DISABLE_FILE_WATCHER=1 --setenv=QS_NO_RELOAD_POPUP=1 "${USTAW[@]}" -- quickshell -p "$QML" --no-duplicate
fi
# --no-duplicate domyka wyścig dwóch startów w tej samej chwili
exec quickshell -p "$QML" --no-duplicate
