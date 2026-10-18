#!/bin/bash
# Trzyma okno podglądu (vncviewer) pływające i w rozmiarze logicznym sesji (18.10).
# Ekran sesji ma stały rozmiar (sesja.sh, 1175x910), a vncviewer rysuje go 1:1 w pikselach fizycznych, więc okno musi mieć
# rozmiar sesji / skala monitora (skala 2: 588x456). Gdy Hyprland je zakafelkuje albo zmieni rozmiar, wracamy do stanu wzorcowego.
# Użycie: trzymaj_okno.sh PID_VNCVIEWERA   (kończy się razem z vncviewerem). RETRONIC_OKNO_LOGICZNE=SZERxWYS nadpisuje rozmiar.
VPID="${1:?brak PID vncviewera}"
SZER=588; WYS=456
[ -n "${RETRONIC_OKNO_LOGICZNE:-}" ] && { SZER=${RETRONIC_OKNO_LOGICZNE%x*}; WYS=${RETRONIC_OKNO_LOGICZNE#*x}; }
while kill -0 "$VPID" 2>/dev/null; do
  # adres okna vncviewera, gdy jest zakafelkowane albo ma zły rozmiar
  A=$(hyprctl clients -j 2>/dev/null | python3 -c "
import sys, json
try:
    for c in json.load(sys.stdin):
        if c['pid'] == $VPID or c['class'] == 'Vncviewer':
            if (not c['floating']) or c['size'] != [$SZER, $WYS]:
                print(c['address'], 'T' if not c['floating'] else 'F')
            break
except Exception:
    pass
")
  if [ -n "$A" ]; then
    ADR=${A% *}
    hyprctl dispatch "hl.dsp.window.float({ action = \"enable\", window = \"address:$ADR\" })" >/dev/null 2>&1
    hyprctl dispatch "hl.dsp.window.resize({ x = $SZER, y = $WYS, window = \"address:$ADR\" })" >/dev/null 2>&1
    [ "${A#* }" = "T" ] && hyprctl dispatch "hl.dsp.window.center({ window = \"address:$ADR\" })" >/dev/null 2>&1
  fi
  sleep 1
done
