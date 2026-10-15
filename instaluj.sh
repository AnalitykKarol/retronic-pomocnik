#!/bin/bash
# Instalator Retronic + pomocnik na nowej maszynie (Linux, Arch/Wayland).
# Użycie: sklonuj repo jako ~/Games/Retronic/pomocnik, potem:  ~/Games/Retronic/pomocnik/instaluj.sh
# Robi: sprawdza zależności, kopiuje klienta (klient/) do ~/Games/Retronic, tworzy prefix wine,
# uruchamia testy. NIE uruchamia gry ani bota, NIE dotyka kont ani haseł.
set -euo pipefail
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
GRA="$(dirname "$DIR")"
[ "$GRA" = "$HOME/Games/Retronic" ] || echo "UWAGA: skrypty zakładają ~/Games/Retronic/pomocnik, a jesteś w $DIR" >&2

brak=()
for p in wine python3 grim sway; do command -v "$p" >/dev/null || brak+=("$p"); done
python3 -c 'import numpy' 2>/dev/null || brak+=("python-numpy")
python3 -c 'import PIL' 2>/dev/null || brak+=("python-pillow (opcjonalnie, część testów)")
if [ "${#brak[@]}" -gt 0 ]; then
  echo "Brakuje: ${brak[*]}" >&2
  echo "Arch: sudo pacman -S wine python-numpy python-pillow grim sway xorg-xwayland" >&2
  echo "Opcjonalnie: libnotify (powiadomienia), claude (mózg Haiku: npm i -g @anthropic-ai/claude-code)" >&2
  [ -z "${INSTALUJ_MIMO_BRAKOW:-}" ] && exit 1
fi

echo "== klient do $GRA"
for f in "$DIR"/klient/*; do
  b="$(basename "$f")"
  if [ -e "$GRA/$b" ]; then echo "  jest: $b"; else cp -a "$f" "$GRA/$b"; echo "  skopiowano: $b"; fi
done
chmod +x "$GRA/retronic.sh" "$DIR"/*.sh 2>/dev/null || true

echo "== prefix wine"
export WINEPREFIX="$GRA/prefix" WINEDEBUG=-all WINEDLLOVERRIDES="mscoree,mshtml=d"
if [ -d "$WINEPREFIX/drive_c" ]; then
  echo "  prefix już istnieje, zostawiam"
else
  wineboot -u >/dev/null 2>&1 || true
  wineserver -w 2>/dev/null || true
  echo "  utworzono $WINEPREFIX"
fi

echo "== testy (bez gry)"
cd "$DIR"
fail=0
for t in testy/test_uh.py testy/test_mozg.py testy/test_trade_logger.py; do
  [ -f "$t" ] || continue
  if RETRONIC_TESTY=1 timeout 300 python3 -I "$t" >/dev/null 2>&1; then echo "  OK   $t"; else echo "  FAIL $t"; fail=1; fi
done

cat <<TXT

Gotowe. Dalej ręcznie (patrz PRZENOSINY.md):
  1. start gry:  $DIR/sesja.sh   (gra bez okna + podgląd; zaloguj postać w podglądzie)
  2. bot:        MAPA=trolle_patrol TRYB=uh $DIR/uruchom_trolle.sh
Druga instancja obok pierwszej: patrz INSTANCJE.md (nowa_instancja.sh).
TXT
exit $fail
