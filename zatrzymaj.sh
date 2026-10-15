#!/bin/bash
# Natychmiastowe zatrzymanie bota Retronic (mozg.py / cavebot.py). Nie rusza gry, wine, straznika ani sway.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
# RETRONIC_ID -> INST_* (bez ID: dzisiejsze ścieżki). STOP ma zadziałać także, gdy instancja.py zawiedzie: ścieżki domyślne.
eval "$(python3 -I "$DIR/instancja.py" powloka 2>/dev/null)" || true
: "${INST_STAN:=$DIR}" "${INST_STOP:=$DIR/STOP}" "${INST_STOP_RECZNY:=$DIR/STOP_RECZNY}"
TYTUL="Bot Retronic${RETRONIC_ID:+ [$RETRONIC_ID]}"
mkdir -p "$INST_STAN"
touch "$INST_STOP" "$INST_STOP_RECZNY"
# tylko prawdziwe procesy python3 (nie powłoki z tekstem w argumentach)
pidy() {   # tylko bot tej instancji; awaryjnie (instancja.py nie działa) dawna pętla po wszystkich botach
  python3 -I "$DIR/instancja.py" pidy '(mozg|cavebot)\.py' 2>/dev/null && return
  for p in $(pgrep -x 'python3?'); do tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -Eq '(mozg|cavebot)\.py' && echo "$p"; done
}
bylo=$(pidy)
czekaj() { for _ in $(seq $(( $1 * 10 ))); do [ -z "$(pidy)" ] && return 0; sleep 0.1; done; return 1; }
if [ -z "$bylo" ]; then
  notify-send "$TYTUL" "Nie było uruchomionego bota (flaga STOP ustawiona)"; exit 0
fi
wynik="zatrzymany"
if ! czekaj 3; then
  pidy | xargs -r kill -TERM
  wynik="zatrzymany (SIGTERM)"
  if ! czekaj 2; then
    pidy | xargs -r kill -KILL
    wynik="zatrzymany (SIGKILL)"
  fi
fi
# bot zabity w trakcie pościgu mógł zostawić wciśnięty klawisz ruchu (trzymany XTEST): puść strzałki i numpad
timeout 5 python3 -I -c "import sys; sys.path.insert(0, '$DIR'); import bot, klawisz_x11; klawisz_x11.puszczaj_wszystkie_strzalki(bot.ekran_gry())" >/dev/null 2>&1
# zwykły stop zgłasza mozg.py ("Bot zatrzymany"); tu tylko wymuszone zabicie, którego bot sam nie zgłosi (14.10)
[ "$wynik" = "zatrzymany" ] || notify-send -u critical "$TYTUL" "$wynik"
echo "$wynik"
