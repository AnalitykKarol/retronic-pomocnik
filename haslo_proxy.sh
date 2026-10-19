#!/bin/bash
# Okienko (zenity) na hasło proxy SOCKS5 instancji; zapisuje je w keyringu (service=retronic-proxy instance=<id>).
# Użycie: haslo_proxy.sh [id]   (domyślnie test). Hasło idzie stdinem do secret-tool, nigdy w argumentach ani w repo.
# Odczyt robi siec_proxy.sh. Cofnięcie: secret-tool clear service retronic-proxy instance <id>
set -u
ID="${1:-test}"
HASLO="$(zenity --password --title="Proxy Retronic: instancja $ID" 2>/dev/null)" || exit 1
[ -n "$HASLO" ] || { zenity --error --text="Puste hasło, nic nie zapisano." 2>/dev/null; exit 1; }
printf '%s' "$HASLO" | secret-tool store --label="retronic-proxy ($ID)" service retronic-proxy instance "$ID" \
  && zenity --info --timeout=3 --text="Zapisano w keyringu (instancja $ID)." 2>/dev/null
