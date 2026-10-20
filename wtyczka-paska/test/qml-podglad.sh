#!/bin/bash
# Test QML popupu offscreen: level w wierszu i klik w nick ("Zobacz postać"). Atrapa statusów, żadnych prawdziwych skryptów ani procesów bota.
# Użycie: wtyczka-paska/test/qml-podglad.sh KATALOG_WYNIKOW   (zrzut pasek-popup.png i qml.log lądują tam)
# qs.Commons (motyw) bierze z zainstalowanego Omarchy (tylko odczyt, symlink); inny katalog: RETRONIC_COMMONS=/ścieżka/Commons.
set -u
OUT="${1:?podaj katalog wyników}"
DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
COMMONS="${RETRONIC_COMMONS:-/usr/share/omarchy/shell/Commons}"
[ -d "$COMMONS" ] || { echo "brak $COMMONS (ustaw RETRONIC_COMMONS)"; exit 2; }
mkdir -p "$OUT"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
for f in PanelContent.qml CityButton.qml RetronicModel.js; do ln -s "$DIR/$f" "$WORK/$f"; done
ln -s "$COMMONS" "$WORK/Commons"
cp "$DIR/test/qml-harness/shell.qml" "$WORK/shell.qml"
QT_QPA_PLATFORM=offscreen PASEK_WYNIK="$OUT" timeout 60 quickshell -p "$WORK" 2>&1 | grep -E "scenariusz|ERROR|TypeError|ReferenceError" > "$OUT/qml.log"
FAIL=0
ok()   { echo "  ok    $1"; }
fail() { echo "  FAIL  $1"; FAIL=1; }
has() { grep -qF -- "$2" "$OUT/qml.log" && ok "$1" || fail "$1 (brak: $2)"; }
grep -E "ERROR|TypeError|ReferenceError" "$OUT/qml.log" && fail "błędy QML"
has "znaczniki: otwarty, zamknięty, start gry (główna i brak sesji bez znacznika)" "widoczne-znaczniki false,true,true,true,false"
has "klik w nick otwartego podglądu woła akcję podglad" "run invincible podglad"
has "klik w nick zamkniętego podglądu woła akcję podglad" "run test podglad"
has "start gry (port jest, klasa brak): nick klikalny" "run startup podglad"
grep -qE "run (ghost|) podglad" "$OUT/qml.log" && fail "główna albo brak sesji nie mogą wołać akcji" || ok "główna i brak sesji nie wołają akcji"
has "zrzut zapisany" "zrzut true"
[ "$FAIL" = 0 ] && echo "WSZYSTKO OK" || echo "BŁĘDY"
exit "$FAIL"
