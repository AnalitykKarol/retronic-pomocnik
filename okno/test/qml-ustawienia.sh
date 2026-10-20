#!/bin/bash
# Test QML sekcji Ustawienia i Ctrl+K w Quickshell offscreen na atrapie (nic z prawdziwego katalogu, żadnych prawdziwych skryptów akcji).
# Użycie: okno/test/qml-ustawienia.sh KATALOG_WYNIKOW   (zrzuty PNG i log lądują tam)
# Sprawdza na prawdziwym okno_api (walidacja pokretla.py): zapis UH_CZAR=adori gran z widoku, zestaw run (jedno wywołanie = jeden wpis dziennika),
# przełącznik, suwak, pole z odrzuceniem wartości spoza zakresu, wróć do domyślnej, Cofnij ostatnią, filtr, grupa tylko do odczytu, ostrzeżenie o trybie, paleta.
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
  rm -rf "$WORK"/* "$OUT/qml-ust.log"
  local env; env="$(python3 "$DOM/okno/test/atrapa.py" "$WORK")" || { fail "budowa atrapy"; return; }
  eval "$env"
  : > "$WORK/wywolania.log"
  NA_ZYWO="$WORK/pomocnik/na_zywo.json"; NA_ZYWO_TEST="$WORK/pomocnik/instancje/test/na_zywo.json"
  cp "$NA_ZYWO" "$WORK/na_zywo.start.json"
  QT_QPA_PLATFORM=offscreen RETRONIC_OKNO_ROZMIAR="${RETRONIC_OKNO_ROZMIAR:-1280x820}" RETRONIC_OKNO_SCENARIUSZ="$1" timeout 90 quickshell -p "$DOM/okno" 2>&1 | grep -E "scenariusz|ERROR|WARN.*qml|TypeError|ReferenceError|Binding loop" | grep -v "WAYLAND\|window masks" > "$OUT/qml-ust.log"
  grep -E "ERROR|TypeError|ReferenceError|Binding loop" "$OUT/qml-ust.log" && fail "błędy QML w $OUT/qml-ust.log"
}
wartosc() { python3 -c "import json,sys; print(json.dumps(json.load(open(sys.argv[1])).get(sys.argv[2],'<brak>'), ensure_ascii=False))" "$1" "$2"; }
jest() { [ "$(wartosc "$2" "$3")" = "$4" ] && ok "$1" || fail "$1 (jest $(wartosc "$2" "$3"), miało być $4)"; }
dziennik() { wc -l < "$WORK/pomocnik/okno_cofnij.jsonl" 2>/dev/null || echo 0; }
ma() { grep -qF -- "$2" "$OUT/qml-ust.log" && ok "$1" || fail "$1 (brak w logu: $2)"; }

S="$OUT/ust"
echo "== A: główna: zapis z widoku (UH_CZAR=adori gran kliknięciem), Cofnij, zrzuty"
uruchom "czekaj:600;sekcja:ustawienia;czekaj:800;zrzut:$S-1-runy.png;klik:opcja-UH_CZAR-adori gran;czekaj:2200;stan;zrzut:$S-2-po-zapisie-hmm.png;klik:cofnij-ostatnia;czekaj:2200;zrzut:$S-3-po-cofnieciu.png;koniec"
jest "po cofnięciu UH_CZAR wraca do adura vita" "$NA_ZYWO" UH_CZAR '"adura vita"'
[ -f "$NA_ZYWO.bak-$(date +%Y%m%d)-okno" ] && ok "kopia .bak-DATA-okno powstała przy pierwszej zmianie dnia" || fail "brak kopii .bak"
cmp -s "$WORK/na_zywo.start.json" "$NA_ZYWO" && ok "plik po zapisie i cofnięciu identyczny z początkowym (z dokładnością do formatu)" || python3 -c "
import json,sys; a=json.load(open(sys.argv[1])); b=json.load(open(sys.argv[2])); sys.exit(0 if a==b else 1)" "$WORK/na_zywo.start.json" "$NA_ZYWO" && ok "plik po zapisie i cofnięciu zawiera te same wartości" || fail "plik po cofnięciu różni się od początkowego"
ma "notka zapisu po kliknięciu" "notka=ok:zapisano UH_CZAR: adura vita"
[ "$(dziennik)" = "0" ] && ok "dziennik cofania pusty po Cofnij" || fail "dziennik nie jest pusty po Cofnij ($(dziennik))"

echo "== B: zestaw run HMM (jedno wywołanie), przełącznik, suwak, pole, domyślna, zakresy"
uruchom "czekaj:600;sekcja:ustawienia;czekaj:800;klik:zestaw-runy;czekaj:2200;zrzut:$S-4-zestaw-hmm.png;koniec"
jest "zestaw: UH_CZAR=adori gran" "$NA_ZYWO" UH_CZAR '"adori gran"'
jest "zestaw: UH_KLAWISZ=F6" "$NA_ZYWO" UH_KLAWISZ '"F6"'
jest "zestaw: UH_KOSZT=70" "$NA_ZYWO" UH_KOSZT 70
jest "zestaw: UH_MANA_MIN=70" "$NA_ZYWO" UH_MANA_MIN 70
jest "zestaw: UH_AKTYWNY nietknięty (zostaje 0; włącza się osobnym przełącznikiem)" "$NA_ZYWO" UH_AKTYWNY 0
[ "$(dziennik)" = "1" ] && ok "zestaw = jeden wpis dziennika (jedno Cofnij)" || fail "zestaw zapisał $(dziennik) wpisów dziennika"
uruchom "czekaj:600;sekcja:ustawienia;czekaj:800;klik:przelacznik-UH_AKTYWNY;czekaj:1800;suwak:UH_KOSZT=120;czekaj:1800;wpisz:UH_KOSZT=9999;czekaj:1500;stan;zrzut:$S-5-pole-poza-zakresem.png;wpisz:UH_KOSZT=85;czekaj:1800;ustaw:POGON_ZASIEG=99;czekaj:1200;stan;koniec"
jest "przełącznik UH_AKTYWNY = 1" "$NA_ZYWO" UH_AKTYWNY 1
jest "pole liczby: 9999 odrzucone, potem 85 zapisane" "$NA_ZYWO" UH_KOSZT 85
jest "ustaw spoza zakresu (POGON_ZASIEG=99) nie trafia do pliku" "$NA_ZYWO" POGON_ZASIEG '"<brak>"'
ma "pole: komunikat o zakresie" "notka=bad:UH_KOSZT: poza zakresem 1 do 500"
ma "ustaw spoza zakresu: komunikat odrzucenia" "notka=bad:nie zapisano: wartość poza zakresem"
uruchom "czekaj:600;sekcja:ustawienia;czekaj:800;klik:domyslna-UH_KOSZT;czekaj:1800;klik:domyslna-UH_KLAWISZ;czekaj:1800;koniec"
jest "wróć do domyślnej: UH_KOSZT = 70" "$NA_ZYWO" UH_KOSZT 70
jest "wróć do domyślnej: UH_KLAWISZ = F6" "$NA_ZYWO" UH_KLAWISZ '"F6"'
jest "pokrętło poza listą (STARY_KLUCZ) nietknięte" "$NA_ZYWO" STARY_KLUCZ 5

echo "== C: filtr, grupa tylko do odczytu, tylko zmienione, ostrzeżenie o trybie (instancja test)"
uruchom "czekaj:600;sekcja:ustawienia;czekaj:800;grupa:Walka i pościg;czekaj:500;zrzut:$S-6-grupa-walka.png;filtr:koszt;czekaj:500;zrzut:$S-7-filtr-koszt.png;filtr:;grupa:Poza listą;czekaj:500;zrzut:$S-8-poza-lista.png;grupa:Runy (UH);zmienione;czekaj:500;zrzut:$S-9-tylko-zmienione.png;koniec"
uruchom "wybierz:test;sekcja:ustawienia;czekaj:1500;zrzut:$S-10-test-ostrzezenie-trybu.png;koniec"
ma "zrzut ostrzeżenia trybu zapisany" "zrzut $S-10-test-ostrzezenie-trybu.png true"

echo "== D: paleta Ctrl+K (logika; skrót klawiszowy: klawisze-sway.sh)"
uruchom "czekaj:600;paleta;czekaj:900;paleta-wpisz:uh koszt;czekaj:500;zrzut:$S-11-paleta-uh-koszt.png;paleta-enter;czekaj:1800;stan;zrzut:$S-12-po-enter.png;koniec"
ma "Enter w palecie: sekcja ustawienia, grupa Runy (UH), pokrętło UH_KOSZT, paleta zamknięta" "STAN section=ustawienia grupa=Runy (UH) filtr= fokus=UH_KOSZT paleta=false"
uruchom "czekaj:600;paleta;czekaj:900;paleta-wpisz:pościg;czekaj:500;paleta-enter;czekaj:1800;stan;koniec"
ma "paleta: 'pościg' otwiera pokrętło z grupy Walka i pościg" "grupa=Walka i pościg"
uruchom "czekaj:600;paleta;czekaj:900;paleta-wpisz:szczury;czekaj:500;paleta-enter;czekaj:1500;stan;koniec"
ma "paleta: mapa (szczury) przenosi do Mapa i tryb" "STAN section=mapa"

echo "== E: najmniejsze okno 1000x600"
RETRONIC_OKNO_ROZMIAR=1000x600 uruchom "czekaj:600;sekcja:ustawienia;czekaj:1000;zrzut:$S-13-1000x600.png;paleta;czekaj:800;paleta-wpisz:uh;czekaj:500;zrzut:$S-14-paleta-1000x600.png;koniec"
ma "zrzut 1000x600 zapisany" "zrzut $S-13-1000x600.png true"

[ "$FAIL" = 0 ] && echo "WSZYSTKO OK" || echo "BŁĘDY"
exit "$FAIL"
