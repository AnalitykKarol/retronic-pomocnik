#!/bin/bash
# Okno zarządzania Retronic (QML, Quickshell): osobny proces od paska (restart paska/powłoki go nie zamyka i odwrotnie).
# Spec: wtyczka-paska/specs/2026-10-19-retronic-okno.md (F2). Jeden egzemplarz: drugi start nie otwiera drugiego okna,
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
# --no-duplicate domyka wyścig dwóch startów w tej samej chwili
exec quickshell -p "$QML" --no-duplicate
