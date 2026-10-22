#!/bin/bash
# Test QML okna w Quickshell offscreen na atrapie (nic z prawdziwego katalogu, żadnych prawdziwych skryptów akcji).
# Użycie: okno/test/qml-atrapa.sh KATALOG_WYNIKOW   (zrzuty PNG i dziennik wywołań lądują tam)
# Sprawdza: render obu sekcji, akcje wołają właściwe skrypty z właściwym RETRONIC_ID, szare przyciski nie klikają.
set -u
OUT="${1:?podaj katalog wyników}"
DOM="$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)"
mkdir -p "$OUT"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
FAIL=0
ok()   { echo "  ok    $1"; }
fail() { echo "  FAIL  $1"; FAIL=1; }

uruchom() {   # $1 = scenariusz
  rm -rf "$WORK"/* "$OUT/qml.log"
  local env; env="$(python3 "$DOM/okno/test/atrapa.py" "$WORK" "${ATRAPA_ILE:-2}")" || { fail "budowa atrapy"; return; }
  eval "$env"
  : > "$WORK/wywolania.log"
  QT_QPA_PLATFORM=offscreen RETRONIC_OKNO_ROZMIAR="${RETRONIC_OKNO_ROZMIAR:-1280x820}" RETRONIC_OKNO_SCENARIUSZ="$1" timeout 90 quickshell -p "$DOM/okno" 2>&1 | grep -E "scenariusz|ERROR|WARN.*qml|TypeError|ReferenceError" | grep -v "WAYLAND\|window masks" > "$OUT/qml.log"
  grep -E "ERROR|TypeError|ReferenceError" "$OUT/qml.log" && fail "błędy QML w $OUT/qml.log"
}
ma() { grep -qF -- "$2" "$WORK/wywolania.log" && ok "$1" || fail "$1 (brak: $2)"; }
nie() { grep -qF -- "$2" "$WORK/wywolania.log" && fail "$1 (jest: $2)" || ok "$1"; }

echo "== A: Ratunek, główna (bot działa): zrzuty, Stop, Miasto, fałszywy alarm, Pokaż w logu"
uruchom "sekcja:ratunek;czekaj:800;zrzut:$OUT/ratunek.png;sygnal:0;czekaj:300;zrzut:$OUT/ratunek-haiku.png;klik:falszywy-alarm;czekaj:2500;zrzut:$OUT/ratunek-po-oznaczeniu.png;klik:pokaz-w-logu;czekaj:800;klik:akcja-glowna;czekaj:1900;klik:akcja-miasto;czekaj:1900;klik:akcja-refill;czekaj:1900;koniec"
cp "$WORK/wywolania.log" "$OUT/dziennik-A.log"
ma "Stop = zatrzymaj.sh dla głównej (bez RETRONIC_ID)" "zatrzymaj.sh RETRONIC_ID=<brak>"
ma "Miasto = wroc.sh dla głównej" "wroc.sh RETRONIC_ID=<brak> MAPA=<brak> TRYB=<brak> POSTAC=<brak> ARGS=[]"
nie "Refill szary przy działającym bocie: refill.sh nie poszedł" "refill.sh"
ma "Pokaż w logu = otwieracz z plikiem ratunek-" "otwieracz ARGS=[$WORK/pomocnik/logi/ratunek-"
[ "$(grep -c falszywy "$WORK/pomocnik/logi/ratunek-etykiety.jsonl" 2>/dev/null)" = "1" ] && ok "fałszywy alarm: jedna etykieta w ratunek-etykiety.jsonl" || fail "etykieta fałszywy alarm"

echo "== B: Mapa i tryb, test (bot stoi): wybór, potwierdzenie, Start z tym, Refill, Spot, Start"
uruchom "wybierz:test;sekcja:mapa;czekaj:600;zrzut:$OUT/mapa-test.png;mapa:raty;tryb:wyprawa;tryb:runy;tryb:runy;klik:start-z-tym;czekaj:500;zrzut:$OUT/mapa-potwierdzenie.png;klik:start-anuluj;klik:start-z-tym;klik:start-potwierdz;czekaj:2500;zrzut:$OUT/mapa-po-starcie.png;klik:akcja-refill;czekaj:1900;klik:akcja-spot;czekaj:1900;klik:akcja-glowna;czekaj:1900;klik:akcja-miasto;czekaj:1900;koniec"
cp "$WORK/wywolania.log" "$OUT/dziennik-B.log"
ma "Start z tym = uruchom.sh z RETRONIC_ID=test, MAPA=raty, TRYB=ml,ostrozny,wyprawa (start ml,ostrozny z ostatniego + wyprawa), nick" "uruchom.sh RETRONIC_ID=test MAPA=raty TRYB=ml,ostrozny,wyprawa POSTAC=Johny Dang"
ma "Refill = refill.sh --tlo dla test" "refill.sh RETRONIC_ID=test MAPA=<brak> TRYB=<brak> POSTAC=<brak> ARGS=[--tlo]"
ma "Spot = refill.sh --spot dla test" "refill.sh RETRONIC_ID=test MAPA=<brak> TRYB=<brak> POSTAC=<brak> ARGS=[--spot]"
ma "Start (pasek) = uruchom.sh dla test bez MAPA/TRYB" "uruchom.sh RETRONIC_ID=test MAPA=<brak> TRYB=<brak> POSTAC=<brak> ARGS=[]"
nie "Miasto szare przy bocie w mieście: wroc.sh nie poszedł" "wroc.sh"
[ "$(grep -c '^uruchom.sh' "$WORK/wywolania.log")" = "2" ] && ok "dokładnie dwa uruchom.sh (Start z tym raz po potwierdzeniu + Start)" || fail "liczba uruchom.sh != 2"

echo "== C: Mapa i tryb, główna (bot działa): Start z tym szary, nic nie rusza"
uruchom "sekcja:mapa;czekaj:600;mapa:raty;klik:start-z-tym;klik:start-potwierdz;czekaj:800;zrzut:$OUT/mapa-glowna-dziala.png;koniec"
cp "$WORK/wywolania.log" "$OUT/dziennik-C.log"
nie "bot działa: uruchom.sh nie poszedł" "uruchom.sh"

echo "== D: 10 postaci: lista kart przewijana, menu i akcje widoczne (1280x820 i najmniejsze 1000x600)"
ATRAPA_ILE=10 uruchom "sekcja:ratunek;czekaj:1500;wybierz:p5;czekaj:800;zrzut:$OUT/dziesiec-1280.png;koniec"
ATRAPA_ILE=10 RETRONIC_OKNO_ROZMIAR=1000x600 uruchom "czekaj:1500;wybierz:p5;sekcja:mapa;czekaj:800;zrzut:$OUT/dziesiec-1000x600.png;koniec"
grep -q "zrzut .*dziesiec-1000x600.png true" "$OUT/qml.log" && ok "zrzut 1000x600 zapisany" || fail "zrzut 1000x600"

echo "== E: zamknięcie okna kończy proces (bez 'koniec' i bez timeoutu)"
rm -rf "$WORK"/*; env="$(python3 "$DOM/okno/test/atrapa.py" "$WORK")" && eval "$env"
QT_QPA_PLATFORM=offscreen RETRONIC_OKNO_SCENARIUSZ="czekaj:500;zamknij" timeout 30 quickshell -p "$DOM/okno" >/dev/null 2>&1
[ "$?" = 0 ] && ok "proces wyszedł sam po zamknięciu okna" || fail "proces nie zakończył się po zamknięciu okna"

[ "$FAIL" = 0 ] && echo "WSZYSTKO OK" || echo "BŁĘDY"
exit "$FAIL"
