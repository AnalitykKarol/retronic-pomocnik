#!/bin/bash
# Obchód nadzorcy z AI (Karol 22.10). Co PODGLAD_CO_S (domyślnie 300 s): przebieg nadzorcy w cieniu (`nadzor.py cien --raz`,
# zero zapisów; grafik logowań/wylogowań NIE działa na żywo), potem jeden obchód modelu wg NADZORCA.md (Haiku, `claude -p`).
# NAPRAWY (Karol 22.10 ~09:40 „tak zrób”): obchód może wołać `nadzor.py napraw <id> <restart|wznow|relog>` (10:17: bez wroc/zmien_spot, grafik ignorowany)
# na żywo (NADZOR_NAPRAWY=1; wykonawca i tak sprawdza bramki: STOP_RECZNY, nadzor:false, pauza, hold, walka, odstępy)
# oraz `notify-send`. Bez `wyloguj` (wylogowania ustala Karol). PODGLAD_NAPRAWY=0 = sam podgląd jak wcześniej.
# Wynik na ekranie i w instancje/_wspolne/logi/obchod-podglad-RRRRMMDD.log. Uruchom w osobnym oknie:
#   xdg-terminal-exec --title="Nadzorca: obchód AI" ./podglad_nadzoru.sh
# Koniec: Ctrl+C albo zamknięcie okna. Pauza wszystkich napraw: touch instancje/_wspolne/NADZOR_PAUZA.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$DIR" || exit 1
CO="${PODGLAD_CO_S:-300}"
NAPRAWY="${PODGLAD_NAPRAWY:-1}"
LOGI="$DIR/instancje/_wspolne/logi"
mkdir -p "$LOGI"
NARZEDZIA=("Bash(python3 -I nadzor.py stan:*)" "Bash(python3 -I nadzor_stan.py:*)" "Bash(python3 -I logowanie.py stan-ekranu:*)"
           "Bash(RETRONIC_ID=*)" Read)
if [ "$NAPRAWY" = 1 ]; then
  export NADZOR_NAPRAWY=1
  NARZEDZIA+=("Bash(python3 -I nadzor.py napraw:*)" "Bash(notify-send:*)")   # rodzaj „wyloguj” zakazany w poleceniu
  PROMPT="Jeden obchód wg NADZORCA.md. TRYB NAPRAW WŁĄCZONY przez Karola (22.10): mimo że 'nadzor.py stan' pokazuje tryb 'cien'
(to dotyczy tylko grafiku logowań), wolno Ci wołać 'python3 -I nadzor.py napraw <id> <rodzaj>' TYLKO z rodzajami: restart, wznow, relog.
NIGDY wroc, wyloguj ani zmien_spot (22.10: obchód odesłał invincible'a do miasta przez koniec zmiany z grafiku, a Karol tego nie chciał).
GRAFIK ZMIAN IGNORUJ CAŁKOWICIE: koniec zmiany, przerwy i limity minut nie są powodem żadnej akcji; o zejściu z expa decyduje Karol.
Zasady z NADZORCA.md obowiązują: najwyżej jedna naprawa na postać, trzy na obchód, odmowa = nie ponawiaj.
Szczególnie: postać na złym piętrze (wpadła w dziurę) > 1 min, stoi/krąży > 8 min, STOP po alarmie bota bez PK/zgonu/GM.
Dla każdej postaci w grze jedna linia: stan, co widzisz, co zrobiłeś (albo nic) i dlaczego. Zwróć uwagę na zachowanie, po którym gracze
poznają bota. Krótko, po polsku, bez wstępu. Na końcu linia WYNIK: <ok|naprawiono|do_sonneta|karol>."
else
  PROMPT="Jeden obchód wg NADZORCA.md, ale w TRYBIE PODGLĄDU: nie masz narzędzia napraw ani notify-send i niczego nie zmieniasz.
Dla każdej postaci w grze napisz jedną linię: stan, co widzisz, i co BYŚ zrobił (rodzaj naprawy z białej listy albo nic) i dlaczego.
Zwróć też uwagę na zachowanie, po którym gracze poznają bota (zawieszki, kręcenie się, bicie w ściany, długie stanie, brak odpowiedzi na czat).
Krótko, po polsku, bez wstępu. Na końcu linia WYNIK: <ok|naprawiłbym|do_sonneta|karol>."
fi
while true; do
  log="$LOGI/obchod-podglad-$(date +%Y%m%d).log"
  clear
  {
    echo "=== $(date '+%H:%M:%S') przebieg nadzorcy (cień) ==="
    python3 -I nadzor.py cien --raz 2>&1 | cut -c1-170
    echo
    echo "=== $(date '+%H:%M:%S') obchód AI (Haiku, naprawy: $([ "$NAPRAWY" = 1 ] && echo TAK || echo nie)) ==="
    printf '%s\n' "$PROMPT" | timeout 300 claude -p --model haiku --no-session-persistence \
      --append-system-prompt-file NADZORCA.md --allowedTools "${NARZEDZIA[@]}" 2>&1 \
      || echo "(obchód AI: błąd albo limit czasu, kod $?)"
    echo
    echo "następny przebieg: $(date -d "+$CO seconds" '+%H:%M:%S')  (Ctrl+C kończy; pauza napraw: touch instancje/_wspolne/NADZOR_PAUZA)"
  } | tee -a "$log"
  sleep "$CO"
done
