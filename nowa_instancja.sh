#!/bin/bash
# Przygotowuje instancję: katalog stanu pomocnik/instancje/<id>/, osobny WINEPREFIX (kopia prefiksu domyślnej gry,
# reflink gdzie się da) i katalog gry z kopiami exe/dll. NIE uruchamia gry ani bota.
# Użycie: ./nowa_instancja.sh <id> [źródłowy_prefix]     (id: małe litery, cyfry, - _ ; do 24 znaków)
set -euo pipefail
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
GRA="$(dirname "$DIR")"
ID="${1:-}"
[ -n "$ID" ] || { echo "użycie: $0 <id> [źródłowy_prefix]" >&2; exit 2; }
INST=$(RETRONIC_ID="$ID" python3 -I "$DIR/instancja.py" powloka) || exit 2; eval "$INST"
ZRODLO="${2:-$GRA/prefix}"
[ -d "$ZRODLO" ] || { echo "brak prefiksu źródłowego: $ZRODLO" >&2; exit 1; }

mkdir -p "$INST_STAN" "$INST_LOGI" "$INST_WSPOLNE"

# 1) prefix wine: kopia (reflink na btrfs/xfs = prawie za darmo); nie nadpisujemy istniejącego
if [ -e "$INST_PREFIX" ]; then
  echo "prefix już istnieje: $INST_PREFIX (zostawiam)"
else
  if pgrep -x wineserver >/dev/null 2>&1; then
    echo "UWAGA: działa wineserver (np. gra domyślnej instancji). Kopia prefiksu w trakcie pracy może mieć" >&2
    echo "       niedopisany rejestr (user.reg/system.reg); w razie dziwnych błędów skopiuj ponownie po zamknięciu gry." >&2
  fi
  cp -a --reflink=auto "$ZRODLO" "$INST_PREFIX.tmp.$$"
  mv "$INST_PREFIX.tmp.$$" "$INST_PREFIX"
  echo "prefix: $INST_PREFIX"
fi

# 2) katalog gry: exe i dll (reflink), własny Retronic.log klienta będzie tu, nie we wspólnym katalogu
mkdir -p "$INST_GRA"
for f in "$GRA"/*.exe "$GRA"/*.dll; do
  [ -f "$f" ] || continue
  [ -e "$INST_GRA/$(basename "$f")" ] || cp --reflink=auto "$f" "$INST_GRA/"
done
echo "gra: $INST_GRA"

# 3) pokrętła startowe: kopia na_zywo.json i uciekanie.json domyślnej instancji (tylko gdy brak); stan postaci
#    (uh_stan.json, mozg_pamiec.json) zaczyna się pusty. znane_pola.json i pochodnia_ids.json są wspólne.
for f in na_zywo.json uciekanie.json; do
  [ -f "$DIR/$f" ] && [ ! -e "$INST_STAN/$f" ] && cp "$DIR/$f" "$INST_STAN/$f"
done
[ -e "$INST_WSPOLNE/zajete.json" ] || echo '{}' > "$INST_WSPOLNE/zajete.json"

cat <<TXT

Instancja '$ID' gotowa: $INST_STAN
Dalej (patrz INSTANCJE.md):
  1. RETRONIC_ID=$ID RETRONIC_POSTAC=<nick> ./sesja.sh        # gra w zagnieżdżonym sway (okno na pulpicie)
  2. zaloguj postać ręcznie, ustaw ją w wybranym miejscu
  3. ./uruchom_instancje.sh $ID <MAPA> <TRYB>                  # bot
  4. stop: RETRONIC_ID=$ID ./zatrzymaj.sh
TXT
