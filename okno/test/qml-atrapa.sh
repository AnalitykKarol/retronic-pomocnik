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
export RETRONIC_OKNO_SORT_PLIK="$WORK/sortowanie-okna"      # zapamiętane sortowanie okna (25.10): w atrapie, nigdy w prawdziwym ~/.local/state
FAIL=0
ok()   { echo "  ok    $1"; }
fail() { echo "  FAIL  $1"; FAIL=1; }

uruchom() {   # $1 = scenariusz
  rm -rf "$WORK"/* "$OUT/qml.log"
  local env; env="$(python3 "$DOM/okno/test/atrapa.py" "$WORK" "${ATRAPA_ILE:-2}" ${ATRAPA_FLAGI:-})" || { fail "budowa atrapy"; return; }
  eval "$env"
  [ -n "${ATRAPA_PRZED:-}" ] && eval "$ATRAPA_PRZED"        # np. wstępnie zapisane sortowanie (restart okna)
  : > "$WORK/wywolania.log"
  QT_QPA_PLATFORM=offscreen RETRONIC_OKNO_ROZMIAR="${RETRONIC_OKNO_ROZMIAR:-1280x820}" RETRONIC_OKNO_SCENARIUSZ="$1" timeout 90 quickshell -p "$DOM/okno" 2>&1 | grep -E "scenariusz|ERROR|WARN.*qml|TypeError|ReferenceError" | grep -v "WAYLAND\|window masks" > "$OUT/qml.log"
  grep -E "ERROR|TypeError|ReferenceError" "$OUT/qml.log" && fail "błędy QML w $OUT/qml.log"
}
ma() { grep -qF -- "$2" "$WORK/wywolania.log" && ok "$1" || fail "$1 (brak: $2)"; }
nie() { grep -qF -- "$2" "$WORK/wywolania.log" && fail "$1 (jest: $2)" || ok "$1"; }

echo "== A: główna (bot działa): Stop, Miasto, Refill szary; menu bez Ratunku (26.10: Ratunek wyłączony, w jego miejscu Spotkania)"
uruchom "sekcja:mapa;czekaj:800;zrzut:$OUT/menu-glowna.png;klik:akcja-glowna;czekaj:1900;klik:akcja-miasto;czekaj:1900;klik:akcja-refill;czekaj:1900;spotkania-stan:;koniec"
cp "$WORK/wywolania.log" "$OUT/dziennik-A.log"
ma "Stop = zatrzymaj.sh dla głównej (bez RETRONIC_ID)" "zatrzymaj.sh RETRONIC_ID=<brak>"
ma "Miasto = wroc.sh dla głównej" "wroc.sh RETRONIC_ID=<brak> MAPA=<brak> TRYB=<brak> POSTAC=<brak> ARGS=[]"
nie "Refill szary przy działającym bocie: refill.sh nie poszedł" "refill.sh"
grep -q "SPOTKANIA-DANE .* nav=jest nav-ratunek=brak" "$OUT/qml.log" && ok "menu: jest „Spotkania”, nie ma „Ratunek”" || fail "menu Spotkania/Ratunek: $(grep SPOTKANIA-DANE "$OUT/qml.log" || echo brak)"

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
ATRAPA_ILE=10 uruchom "sekcja:mapa;czekaj:1500;wybierz:p5;czekaj:800;zrzut:$OUT/dziesiec-1280.png;koniec"
ATRAPA_ILE=10 RETRONIC_OKNO_ROZMIAR=1000x600 uruchom "czekaj:1500;wybierz:p5;sekcja:mapa;czekaj:800;zrzut:$OUT/dziesiec-1000x600.png;koniec"
grep -q "zrzut .*dziesiec-1000x600.png true" "$OUT/qml.log" && ok "zrzut 1000x600 zapisany" || fail "zrzut 1000x600"

echo "== F: Zaloguj postać (24.10): klik wola zaloguj_postac.sh z RETRONIC_ID, szare nie klikają (w grze, stracona, główna, inne logowanie)"
ATRAPA_FLAGI="--zaloguj" uruchom "wybierz:ekran;sekcja:sesja;czekaj:900;zaloguj-stan:ekran;zrzut:$OUT/zaloguj-pasek.png;klik:akcja-zaloguj;czekaj:100;zaloguj-stan:ekran;zaloguj-stan:bezsesji;klik:zaloguj-bezsesji;zrzut:$OUT/zaloguj-w-toku.png;czekaj:4200;zrzut:$OUT/zaloguj-po-wyniku.png;zaloguj-stan:ekran;klik:zaloguj-bezsesji;czekaj:2200;wybierz:test;czekaj:700;zaloguj-stan:test;klik:akcja-zaloguj;czekaj:800;wybierz:strata;czekaj:700;zaloguj-stan:strata;klik:akcja-zaloguj;czekaj:800;wybierz:glowna;czekaj:700;zaloguj-stan:glowna;klik:akcja-zaloguj;czekaj:800;sekcja:przeglad;czekaj:1000;zrzut:$OUT/zaloguj-przeglad.png;koniec"
cp "$WORK/wywolania.log" "$OUT/dziennik-F.log"
ma "Zaloguj (pasek, ekran logowania) = zaloguj_postac.sh dla ekran, bez MAPA/TRYB/ARGS" "zaloguj_postac.sh RETRONIC_ID=ekran MAPA=<brak> TRYB=<brak> POSTAC=<brak> ARGS=[]"
nie "Zaloguj nie robi startu: uruchom.sh nie poszedł" "uruchom.sh"
nie "Zaloguj nie rusza bota: zatrzymaj.sh nie poszedł" "zatrzymaj.sh"
nie "w grze (test): zaloguj_postac.sh nie poszedł" "RETRONIC_ID=test"
nie "stracona (strata): zaloguj_postac.sh nie poszedł" "RETRONIC_ID=strata"
nie "główna: zaloguj_postac.sh nie poszedł" "zaloguj_postac.sh RETRONIC_ID=<brak>"
[ "$(grep -c '^zaloguj_postac.sh' "$WORK/wywolania.log")" = "2" ] && ok "dokładnie dwa zaloguj_postac.sh (ekran z paska + bezsesji z wiersza Przeglądu lub drugi po cooldownie)" || fail "liczba zaloguj_postac.sh != 2: $(grep -c '^zaloguj_postac.sh' "$WORK/wywolania.log")"
grep -q "ZALOGUJ id=ekran wlaczony=true powod= " "$OUT/qml.log" && ok "stan ekran: guzik aktywny" || fail "stan ekran: guzik aktywny"
grep -q "ZALOGUJ id=test wlaczony=false powod=in-game busy=false podpowiedz=już w grze" "$OUT/qml.log" && ok "stan test: szary, już w grze" || fail "stan test: szary, już w grze"
grep -q "ZALOGUJ id=strata wlaczony=false powod=lost" "$OUT/qml.log" && ok "stan strata: szary, stracona" || fail "stan strata: szary, stracona"
grep -q "ZALOGUJ id=glowna wlaczony=false powod=main" "$OUT/qml.log" && ok "stan główna: szary" || fail "stan główna: szary"
grep -q "ZALOGUJ id=ekran wlaczony=false powod=login busy=true" "$OUT/qml.log" && ok "w trakcie: ekran busy, Backend.loginId ustawione" || fail "w trakcie logowania ekran busy"
grep -q "ZALOGUJ id=bezsesji wlaczony=false powod=other" "$OUT/qml.log" && ok "w trakcie logowania innej postaci: bezsesji szary (jedno naraz)" || fail "bezsesji szary podczas cudzego logowania"
grep -q "ZALOGUJ id=ekran wlaczony=.* wynik=ok:Postać zalogowana (atrapa)" "$OUT/qml.log" && ok "wynik logowania (stub, RC=0) = ok + zdanie skryptu" || fail "brak wyniku logowania"

echo "== G: stracone ukryte (25.10): lista postaci bez straconych, przełącznik, spadek wyboru, Przegląd: wszystkie bez straconych / chip „stracone” je pokazuje"
ATRAPA_FLAGI="--zaloguj" uruchom "czekaj:1500;lista-stan;zrzut:$OUT/stracone-pasek-ukryte.png;sekcja:przeglad;czekaj:700;zrzut:$OUT/stracone-przeglad-wszystkie.png;klik:filtr-stracone;czekaj:500;zrzut:$OUT/stracone-przeglad-chip.png;klik:pokaz-stracone;lista-stan;wybierz:strata;czekaj:500;lista-stan;klik:pokaz-stracone;czekaj:800;lista-stan;zrzut:$OUT/stracone-po-ukryciu.png;klik:filtr-stracone;klik:wiersz-strata;czekaj:900;lista-stan;zrzut:$OUT/stracone-po-kliku-wiersza.png;koniec"
cp "$WORK/wywolania.log" "$OUT/dziennik-G.log"
mapfile -t LISTA < <(grep "LISTA " "$OUT/qml.log")
echo "${LISTA[0]:-}" | grep -q "widoczne=[^ ]*" && ! echo "${LISTA[0]:-}" | grep -q "strata" && ok "start: lista bez straconej (strata)" || fail "start: lista bez straconej: ${LISTA[0]:-brak}"
echo "${LISTA[0]:-}" | grep -q "stracone=1 pokazStracone=false przelacznik=true:pokaż stracone (1)" && ok "start: przełącznik „pokaż stracone (1)” widoczny" || fail "start: przełącznik"
echo "${LISTA[0]:-}" | grep -q "stracone-chip=1" && ok "chip „stracone” liczy 1, „wszystkie” bez niej" || fail "chip stracone"
echo "${LISTA[1]:-}" | grep -q "widoczne=[^ ]*strata[^ ]* .*pokazStracone=true przelacznik=true:ukryj stracone (1)" && ok "po kliku przełącznika: strata na liście, napis „ukryj stracone”" || fail "po kliku przełącznika: ${LISTA[1]:-brak}"
echo "${LISTA[2]:-}" | grep -q "wybrana=strata" && ok "wybrana strata (widoczna)" || fail "wybór straty: ${LISTA[2]:-brak}"
echo "${LISTA[3]:-}" | grep -q "pokazStracone=false" && ! echo "${LISTA[3]:-}" | grep -q "wybrana=strata" && ! echo "${LISTA[3]:-}" | grep -qE "widoczne=[^ ]*strata" && ok "ukrycie przy wybranej stracie: wybór spadł na widoczną, strata znika z listy" || fail "spadek wyboru: ${LISTA[3]:-brak}"
echo "${LISTA[4]:-}" | grep -q "pokazStracone=true" && echo "${LISTA[4]:-}" | grep -q "wybrana=strata" && ok "klik w straconą w Przeglądzie (chip) włącza listę i wybiera ją" || fail "klik w wiersz straty: ${LISTA[4]:-brak}"
nie "stracone: żadna akcja bota nie poszła" "uruchom.sh"

echo "== H: sortowanie (25.10): domyślnie poziom ↓, wybór sortowania (tabela Przeglądu + pasek), filtry razem z sortowaniem, wybór przeżywa odświeżenie stanu i restart okna"
ATRAPA_FLAGI="--sesja --zaloguj" uruchom "czekaj:1500;sekcja:przeglad;czekaj:700;kolejnosc;zrzut:$OUT/sortowanie-domyslne.png;klik:sort-nazwa;czekaj:700;kolejnosc;zrzut:$OUT/sortowanie-nazwa.png;klik:sort-stan;czekaj:700;kolejnosc;zrzut:$OUT/sortowanie-stan.png;klik:sort-level;czekaj:700;kolejnosc;klik:filtr-w-grze;czekaj:600;kolejnosc;zrzut:$OUT/sortowanie-w-grze.png;klik:filtr-wszystkie;klik:sort-nazwa;czekaj:6500;kolejnosc;sekcja:sesja;czekaj:700;kolejnosc;koniec"
mapfile -t KOL < <(grep "KOLEJNOSC " "$OUT/qml.log")
# dane atrapy: znany poziom mają tylko dzial (58) i ipzle (12, oba w grze); reszta bez poziomu ląduje na końcu, wg nicku (Bez Profilu, Bez Sesji, Ekran…, Johny Dang, Mastafian = główna); główna jest w atrapie poza „w grze”
echo "${KOL[0]:-}" | grep -q "KOLEJNOSC sort=level " && ok "start: sortowanie domyślne = level" || fail "domyślne sortowanie: ${KOL[0]:-brak}"
echo "${KOL[0]:-}" | grep -q "tabela=\[gra\],dzial,ipzle,ekran,\[offline\],bezprofilu,bezsesji,test,glowna " && ok "tabela domyślnie: w grze dzial (58) przed ipzle (12), ekran bez poziomu na końcu grupy; OFFLINE bez poziomów wg nazwy" || fail "kolejność domyślna: ${KOL[0]:-brak}"
echo "${KOL[0]:-}" | grep -q "pasek=dzial,ipzle,bezprofilu,bezsesji,ekran,test,glowna$" && ok "pasek boczny: ta sama kolejność po poziomie (58, 12, potem bez poziomu wg nazwy)" || fail "pasek domyślnie: ${KOL[0]:-brak}"
echo "${KOL[0]:-}" | grep -q "strata" && fail "stracona widoczna mimo ukrycia" || ok "stracona nadal ukryta przy sortowaniu"
echo "${KOL[1]:-}" | grep -q "KOLEJNOSC sort=nazwa tabela=\[gra\],dzial,ekran,ipzle,\[offline\],bezprofilu,bezsesji,test,glowna pasek=bezprofilu,bezsesji,dzial,ekran,test,glowna,ipzle$" && ok "nazwa A→Z: tabela (w grupach) i pasek alfabetycznie wg nicku" || fail "sortowanie po nazwie: ${KOL[1]:-brak}"
echo "${KOL[2]:-}" | grep -q "KOLEJNOSC sort=stan " && ok "klik „stan” zmienia sortowanie" || fail "sortowanie po stanie: ${KOL[2]:-brak}"
echo "${KOL[3]:-}" | grep -q "KOLEJNOSC sort=level tabela=\[gra\],dzial,ipzle,ekran,\[offline\],bezprofilu,bezsesji,test,glowna pasek=dzial,ipzle,bezprofilu,bezsesji,ekran,test,glowna$" && ok "powrót do poziomu przywraca kolejność" || fail "powrót do poziomu: ${KOL[3]:-brak}"
echo "${KOL[4]:-}" | grep -q "KOLEJNOSC sort=level tabela=\[gra\],dzial,ipzle,ekran pasek=dzial,ipzle,bezprofilu" && ok "filtr „w grze” razem z sortowaniem: tylko grupa W GRZE po poziomie, pasek bez zmian" || fail "filtr + sortowanie: ${KOL[4]:-brak}"
echo "${KOL[5]:-}" | grep -q "KOLEJNOSC sort=nazwa " && ok "po 6,5 s (odświeżenie stanu co 5 s) sortowanie zostaje" || fail "reset sortowania przy odświeżeniu: ${KOL[5]:-brak}"
echo "${KOL[6]:-}" | grep -q "KOLEJNOSC sort=nazwa .*pasek=bezprofilu,bezsesji,dzial,ekran,test,glowna,ipzle" && ok "w sekcji postaci pasek boczny też wg wybranego sortowania" || fail "pasek w sekcji Sesja: ${KOL[6]:-brak}"
[ "$(cat "$RETRONIC_OKNO_SORT_PLIK" 2>/dev/null)" = "nazwa" ] && ok "wybór zapisany w pliku stanu okna (nazwa)" || fail "plik sortowania: $(cat "$RETRONIC_OKNO_SORT_PLIK" 2>/dev/null || echo brak)"
ATRAPA_PRZED='printf "exp_h\n" > "$RETRONIC_OKNO_SORT_PLIK"' ATRAPA_FLAGI="--sesja --zaloguj" uruchom "czekaj:1800;sekcja:przeglad;czekaj:700;kolejnosc;zrzut:$OUT/sortowanie-po-restarcie.png;koniec"
grep -q "KOLEJNOSC sort=exp_h " "$OUT/qml.log" && ok "restart okna: zapisane sortowanie (exp_h) odczytane z pliku" || fail "odczyt zapisanego sortowania: $(grep KOLEJNOSC "$OUT/qml.log" || echo brak)"
ATRAPA_PRZED='printf "bzdura\n" > "$RETRONIC_OKNO_SORT_PLIK"' ATRAPA_FLAGI="--sesja --zaloguj" uruchom "czekaj:1800;sekcja:przeglad;czekaj:700;kolejnosc;koniec"
grep -q "KOLEJNOSC sort=level " "$OUT/qml.log" && ok "plik z nieznanym kluczem: zostaje domyślne sortowanie (level)" || fail "nieznany klucz w pliku: $(grep KOLEJNOSC "$OUT/qml.log" || echo brak)"
RETRONIC_OKNO_ROZMIAR=1000x600 ATRAPA_FLAGI="--sesja --zaloguj" uruchom "czekaj:1500;sekcja:przeglad;czekaj:700;klik:sort-hp;czekaj:700;zrzut:$OUT/sortowanie-1000x600.png;koniec"
grep -q "zrzut .*sortowanie-1000x600.png true" "$OUT/qml.log" && ok "zrzut 1000x600 (najmniejsze okno, wiersz sortowania) zapisany" || fail "zrzut sortowanie 1000x600"
nie "sortowanie: żadna akcja bota nie poszła" "uruchom.sh"

echo "== I: Spotkania z graczami (26.10): linie na kartach postaci i zakładka (tabela, czas i tempo, zmiany spotu, unikane), „-” przy braku danych, stracone ukryte"
ATRAPA_FLAGI="--spotkania --zaloguj" uruchom "czekaj:6500;wybierz:spohot;sekcja:spotkania;czekaj:2500;spotkania-stan:spohot,spolow,spozero,spobot,spostoi,test,strata;zrzut:$OUT/spotkania-zakladka.png;sekcja:sesja;czekaj:1200;zrzut:$OUT/spotkania-karty.png;koniec"
cp "$WORK/wywolania.log" "$OUT/dziennik-I.log"
grep -qE "SPOTKANIA id=spohot karta=👥 spotkań 3/3 · Statutum ×3 \| na spocie 1h 2[0-9]m · 2,9/h \| hot=true wiersz=1h 2[0-9]m \| 2 \| 3/3 \| 2,9 \| Statutum ×3" "$OUT/qml.log" && ok "spohot: 3/3 = próg (hot), Statutum ×3, czas i tempo na karcie i w tabeli" || fail "spohot: $(grep 'SPOTKANIA id=spohot' "$OUT/qml.log" || echo brak)"
grep -qE "SPOTKANIA id=spolow karta=👥 spotkań 1/3 · Statutum ×1 \| na spocie 5[0-9]m · 1,2/h \| hot=false" "$OUT/qml.log" && ok "spolow: 1/3, bez wyróżnienia" || fail "spolow: $(grep 'SPOTKANIA id=spolow' "$OUT/qml.log" || echo brak)"
grep -qE "SPOTKANIA id=spozero karta=👥 spotkań 0/3 \| na spocie 3[0-9]m · 0/h \| hot=false" "$OUT/qml.log" && ok "spozero: 0/3 bez bywalca (prawdziwe zero z pomiaru)" || fail "spozero: $(grep 'SPOTKANIA id=spozero' "$OUT/qml.log" || echo brak)"
grep -qE "SPOTKANIA id=spobot karta=👥 spotkań 2/3 · Statutum ×2 " "$OUT/qml.log" && ok "spobot: licznik bota bieżącej sesji (2/3)" || fail "spobot: $(grep 'SPOTKANIA id=spobot' "$OUT/qml.log" || echo brak)"
grep -q "SPOTKANIA id=spostoi karta=👥 spotkań - | na spocie - · -/h | hot=false wiersz=- | - | - | - | -" "$OUT/qml.log" && ok "bot stoi: same „-” na karcie i w tabeli, bez zer" || fail "spostoi: $(grep 'SPOTKANIA id=spostoi' "$OUT/qml.log" || echo brak)"
grep -q "SPOTKANIA id=test karta=ukryta wiersz=- | - | - | - | -" "$OUT/qml.log" && ok "postać poza grą: karta bez linii, w tabeli „-”" || fail "test: $(grep 'SPOTKANIA id=test' "$OUT/qml.log" || echo brak)"
grep -q "SPOTKANIA id=strata karta=brak wiersz=brak" "$OUT/qml.log" && ok "stracona (strata): ani karty, ani wiersza (ukryta jak w reszcie okna)" || fail "strata: $(grep 'SPOTKANIA id=strata' "$OUT/qml.log" || echo brak)"
grep -q "SPOTKANIA-DANE zmiany=3 unikane=2 blad= nav=jest nav-ratunek=brak" "$OUT/qml.log" && ok "zmiany spotu (3) i unikane spoty (2) z dziennika nadzorcy i nadzor_stan.json; menu Spotkania zamiast Ratunku" || fail "dane zakładki: $(grep SPOTKANIA-DANE "$OUT/qml.log" || echo brak)"
grep -q "zrzut .*spotkania-karty.png true" "$OUT/qml.log" && ok "zrzut kart zapisany" || fail "zrzut kart"
nie "spotkania: żadna akcja bota nie poszła" "uruchom.sh"
nie "spotkania: żadna akcja bota nie poszła (zatrzymaj.sh)" "zatrzymaj.sh"
RETRONIC_OKNO_ROZMIAR=1000x600 ATRAPA_FLAGI="--spotkania" uruchom "czekaj:6500;wybierz:spohot;sekcja:spotkania;czekaj:2500;zrzut:$OUT/spotkania-1000x600.png;koniec"
grep -q "zrzut .*spotkania-1000x600.png true" "$OUT/qml.log" && ok "zrzut zakładki 1000x600 (najmniejsze okno) zapisany" || fail "zrzut zakładki 1000x600"

echo "== E: zamknięcie okna kończy proces (bez 'koniec' i bez timeoutu)"
rm -rf "$WORK"/*; env="$(python3 "$DOM/okno/test/atrapa.py" "$WORK")" && eval "$env"
QT_QPA_PLATFORM=offscreen RETRONIC_OKNO_SCENARIUSZ="czekaj:500;zamknij" timeout 30 quickshell -p "$DOM/okno" >/dev/null 2>&1
[ "$?" = 0 ] && ok "proces wyszedł sam po zamknięciu okna" || fail "proces nie zakończył się po zamknięciu okna"

[ "$FAIL" = 0 ] && echo "WSZYSTKO OK" || echo "BŁĘDY"
exit "$FAIL"
