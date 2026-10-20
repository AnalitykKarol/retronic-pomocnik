#!/bin/bash
# Test QML sekcji Sesja gry (F4b) i kart postaci (level, znacznik podglądu) w Quickshell offscreen na atrapie z opcją --sesja
# (nic z prawdziwego katalogu; sesja_gry.py w atrapie tylko loguje wywołanie i przestawia pliki ATRAPY, nigdy prawdziwych sesji).
# Użycie: okno/test/qml-sesja.sh KATALOG_WYNIKOW   (zrzuty PNG i logi lądują tam)
# Sprawdza: render sekcji dla głównej, działającej instancji z otwartym podglądem, zatrzymanej z profilem ok, z błędem profilu i z IP spoza
# profilu; dostępność guzików; potwierdzenie Zamknij (z ostrzeżeniem o działającym bocie); Uruchom/Zamknij/Podgląd wołają sesja_gry.py
# start|zamknij|podglad z właściwym RETRONIC_ID; szare guziki i główna nie wołają nic; klik w nick na karcie = podgląd.
# G: zajętość akcji jest per instancja (wolne `Zamknij grę` ipzle nie blokuje Stop dzial; ipzle blokuje tylko samą siebie).
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
  rm -rf "$WORK"/* "$OUT/qml-sesja.log"
  local env; env="$(python3 "$DOM/okno/test/atrapa.py" "$WORK" "${ATRAPA_ILE:-2}" --sesja)" || { fail "budowa atrapy"; return; }
  eval "$env"
  : > "$WORK/wywolania.log"
  [ -n "${WOLNE_ZAMKNIJ:-}" ] && echo "${WOLNE_ZAMKNIJ_S:-12}" > "$WORK/opoznienie-zamknij-$WOLNE_ZAMKNIJ"     # atrapa: wolne zamknięcie gry jednej instancji
  QT_QPA_PLATFORM=offscreen RETRONIC_OKNO_ROZMIAR="${RETRONIC_OKNO_ROZMIAR:-1280x820}" RETRONIC_OKNO_SCENARIUSZ="$1" timeout 120 quickshell -p "$DOM/okno" 2>&1 \
    | grep -E "scenariusz|ERROR|WARN.*qml|TypeError|ReferenceError|Binding loop" | grep -v "WAYLAND\|window masks" > "$OUT/qml-sesja.log"
  grep -E "ERROR|TypeError|ReferenceError|Binding loop" "$OUT/qml-sesja.log" && fail "błędy QML w $OUT/qml-sesja.log"
}
ma()  { grep -qF -- "$2" "$WORK/wywolania.log" && ok "$1" || fail "$1 (brak w wywolania.log: $2)"; }
nie() { grep -qF -- "$2" "$WORK/wywolania.log" && fail "$1 (jest: $2)" || ok "$1"; }
log() { grep -qF -- "$2" "$OUT/qml-sesja.log" && ok "$1" || fail "$1 (brak w qml-sesja.log: $2)"; }
liczba() { [ "$(grep -c '^sesja_gry.py' "$WORK/wywolania.log")" = "$2" ] && ok "$1" || fail "$1 (sesja_gry.py wołany $(grep -c '^sesja_gry.py' "$WORK/wywolania.log") razy, miało być $2)"; }
zrzut() { grep -q "zrzut $1 true" "$OUT/qml-sesja.log" && ok "zrzut $(basename "$1")" || fail "zrzut $1"; }

S="$OUT/sesja"
echo "== A: główna: wyjaśnienie zamiast guzików, żaden guzik nic nie woła"
uruchom "czekaj:1200;wybierz:glowna;sekcja:sesja;czekaj:900;sesja-stan;zrzut:$S-1-glowna.png;klik:sesja-uruchom;klik:sesja-zamknij;klik:sesja-podglad;klik:nick-;czekaj:600;sesja-stan;koniec"
zrzut "$S-1-glowna.png"
log "główna: wszystkie guziki szare" "SESJA id= uruchom=false zamknij=false podglad=false:Otwórz podgląd potwierdzenie=false"
liczba "główna: sesja_gry.py nie wołany" 0

echo "== B: dzial (działa, bot działa, podgląd otwarty): zrzut, Pokaż podgląd, Zamknij z potwierdzeniem i ostrzeżeniem o bocie, Anuluj, potem Zamknij"
uruchom "czekaj:1200;wybierz:dzial;sekcja:sesja;czekaj:900;sesja-stan;zrzut:$S-2-dzial-podglad-otwarty.png;klik:sesja-uruchom;klik:sesja-podglad;czekaj:2200;sesja-stan;zrzut:$S-3-dzial-po-podgladzie.png;klik:sesja-zamknij;czekaj:600;sesja-stan;zrzut:$S-4-dzial-potwierdzenie-zamknij.png;klik:sesja-zamknij-anuluj;czekaj:300;sesja-stan;klik:sesja-zamknij;klik:sesja-zamknij-potwierdz;czekaj:3000;sesja-stan;zrzut:$S-5-dzial-po-zamknieciu.png;koniec"
zrzut "$S-2-dzial-podglad-otwarty.png"; zrzut "$S-4-dzial-potwierdzenie-zamknij.png"; zrzut "$S-5-dzial-po-zamknieciu.png"
log "dzial: Zamknij i Pokaż podgląd aktywne, Uruchom szare" "SESJA id=dzial uruchom=false zamknij=true podglad=true:Pokaż podgląd potwierdzenie=false wynik=:"
log "dzial: po Zamknij okno potwierdzenia jest otwarte" "SESJA id=dzial uruchom=false zamknij=true podglad=true:Pokaż podgląd potwierdzenie=true"
log "dzial: po Anuluj potwierdzenie zamknięte" "potwierdzenie=false wynik=ok:Podgląd: podgląd dzial otwiera się (atrapa)"
log "dzial: po potwierdzeniu wynik akcji w oknie" "wynik=ok:Zamknij grę: gra dzial zamknięta (atrapa)"
log "dzial: po zamknięciu sesja zatrzymana, Uruchom możliwe" "SESJA id=dzial uruchom=true zamknij=false podglad=false:Otwórz podgląd potwierdzenie=false wynik=ok:Zamknij grę"
ma "Podgląd = sesja_gry.py podglad dla dzial" "sesja_gry.py RETRONIC_ID=dzial MAPA=<brak> TRYB=<brak> POSTAC=<brak> ARGS=[podglad]"
ma "Zamknij = sesja_gry.py zamknij dla dzial" "sesja_gry.py RETRONIC_ID=dzial MAPA=<brak> TRYB=<brak> POSTAC=<brak> ARGS=[zamknij]"
nie "szare Uruchom przy działającej sesji: start nie poszedł" "ARGS=[start]"
liczba "dokładnie dwa wywołania (podgląd, zamknij; Anuluj i szary Uruchom nic)" 2

echo "== C: test (zatrzymana, profil ok): Uruchom aktywne, Zamknij i Podgląd szare, po starcie podpowiedź 'zaloguj postać w podglądzie'"
uruchom "czekaj:1200;wybierz:test;sekcja:sesja;czekaj:900;sesja-stan;zrzut:$S-6-test-zatrzymana-profil-ok.png;klik:sesja-zamknij;klik:sesja-podglad;klik:sesja-uruchom;czekaj:3200;sesja-stan;zrzut:$S-7-test-po-starcie.png;koniec"
zrzut "$S-6-test-zatrzymana-profil-ok.png"; zrzut "$S-7-test-po-starcie.png"
log "test: tylko Uruchom aktywne" "SESJA id=test uruchom=true zamknij=false podglad=false:Otwórz podgląd potwierdzenie=false wynik=:"
log "test: po starcie sesja żyje (Zamknij, Otwórz podgląd aktywne), wynik startu" "SESJA id=test uruchom=false zamknij=true podglad=true:Otwórz podgląd potwierdzenie=false wynik=ok:Uruchom grę: sesja test wystartowała (atrapa)"
ma "Uruchom = sesja_gry.py start dla test" "sesja_gry.py RETRONIC_ID=test MAPA=<brak> TRYB=<brak> POSTAC=<brak> ARGS=[start]"
liczba "szare Zamknij i Podgląd nic nie wołają (tylko jeden start)" 1

echo "== D: błąd profilu (bezprofilu) i IP spoza profilu (ipzle)"
uruchom "czekaj:1200;wybierz:bezprofilu;sekcja:sesja;czekaj:900;sesja-stan;zrzut:$S-8-blad-profilu.png;klik:sesja-uruchom;wybierz:ipzle;czekaj:900;sesja-stan;zrzut:$S-9-ip-spoza-profilu.png;koniec"
zrzut "$S-8-blad-profilu.png"; zrzut "$S-9-ip-spoza-profilu.png"
log "bezprofilu: wszystko szare" "SESJA id=bezprofilu uruchom=false zamknij=false podglad=false:Otwórz podgląd"
log "ipzle: Zamknij i Otwórz podgląd aktywne, Uruchom szare" "SESJA id=ipzle uruchom=false zamknij=true podglad=true:Otwórz podgląd"
liczba "błąd profilu: Uruchom nic nie woła" 0

echo "== E: klik w nick na karcie = podgląd tej instancji (ipzle zamknięty -> otwarty), nick bez sesji nic nie robi"
uruchom "czekaj:1200;zrzut:$S-10-karty-przed.png;klik:nick-test;czekaj:600;klik:nick-ipzle;czekaj:2600;sesja-stan;zrzut:$S-11-karty-po-kliknieciu-nicku.png;koniec"
zrzut "$S-10-karty-przed.png"; zrzut "$S-11-karty-po-kliknieciu-nicku.png"
ma "klik w nick ipzle = sesja_gry.py podglad z RETRONIC_ID=ipzle" "sesja_gry.py RETRONIC_ID=ipzle MAPA=<brak> TRYB=<brak> POSTAC=<brak> ARGS=[podglad]"
liczba "nick test (brak sesji) nie wołał nic" 1

echo "== F: 13 kart (10 + 3 z sesją), najmniejsze okno 1000x600: karty z lvl i znacznikiem mieszczą się, sekcja przewijalna"
ATRAPA_ILE=10 RETRONIC_OKNO_ROZMIAR=1000x600 uruchom "czekaj:1500;wybierz:dzial;sekcja:sesja;czekaj:900;zrzut:$S-12-1000x600.png;koniec"
zrzut "$S-12-1000x600.png"

echo "== G: wolne Zamknij grę instancji ipzle (12 s) nie blokuje Stop instancji dzial; ipzle blokuje tylko samą siebie"
WOLNE_ZAMKNIJ=ipzle WOLNE_ZAMKNIJ_S=12 uruchom "czekaj:1200;wybierz:ipzle;sekcja:sesja;czekaj:900;akcje-stan:ipzle,dzial;klik:sesja-zamknij;klik:sesja-zamknij-potwierdz;czekaj:700;akcje-stan:ipzle,dzial;klik:akcja-glowna;klik:akcja-glowna;zrzut:$S-13-ipzle-zamyka-sama-zablokowana.png;wybierz:dzial;czekaj:900;akcje-stan:ipzle,dzial;zrzut:$S-14-dzial-stop-aktywny-gdy-ipzle-zamyka.png;klik:akcja-glowna;akcje-stan:ipzle,dzial;czekaj:2600;akcje-stan:ipzle,dzial;czekaj:11000;akcje-stan:ipzle,dzial;wybierz:ipzle;czekaj:900;sesja-stan;koniec"
zrzut "$S-13-ipzle-zamyka-sama-zablokowana.png"; zrzut "$S-14-dzial-stop-aktywny-gdy-ipzle-zamyka.png"
log "przed akcją nic nie jest zajęte, Zamknij klikalny" "AKCJE wybrana=ipzle busy=ipzle:false,dzial:false stop-klikalny=true zamknij-klikalny=true"
log "w trakcie zamykania ipzle: zajęta tylko ipzle, jej Stop/Start i Zamknij zablokowane" "AKCJE wybrana=ipzle busy=ipzle:true,dzial:false stop-klikalny=false zamknij-klikalny=false"
log "dzial wybrany podczas zamykania ipzle: Stop klikalny, dzial wolny" "AKCJE wybrana=dzial busy=ipzle:true,dzial:false stop-klikalny=true"
log "po kliknięciu Stop dzial: obie zajęte równolegle" "AKCJE wybrana=dzial busy=ipzle:true,dzial:true"
log "Stop dzial skończył (i cooldown) gdy ipzle jeszcze zamyka" "AKCJE wybrana=dzial busy=ipzle:true,dzial:false stop-klikalny=true"
log "na końcu obie wolne" "AKCJE wybrana=dzial busy=ipzle:false,dzial:false"
log "wynik zamknięcia przypisany do ipzle" "SESJA id=ipzle uruchom=true zamknij=false podglad=false:Otwórz podgląd potwierdzenie=false wynik=ok:Zamknij grę: gra ipzle zamknięta (atrapa)"
ma "zamknij dla ipzle poszedł" "sesja_gry.py RETRONIC_ID=ipzle MAPA=<brak> TRYB=<brak> POSTAC=<brak> ARGS=[zamknij]"
ma "Stop dzial dotarł do zatrzymaj.sh mimo zamykania ipzle" "zatrzymaj.sh RETRONIC_ID=dzial"
nie "kliknięcie ipzle podczas jej zamykania nie wołało skryptu" "uruchom.sh RETRONIC_ID=ipzle"
[ "$(grep -n 'ARGS=\[zamknij\]' "$WORK/wywolania.log" | head -1 | cut -d: -f1)" -lt "$(grep -n 'zatrzymaj.sh RETRONIC_ID=dzial' "$WORK/wywolania.log" | head -1 | cut -d: -f1)" ] \
  && ok "kolejność w dzienniku: zamknij ipzle, potem Stop dzial" || fail "kolejność w dzienniku wywołań"

[ "$FAIL" = 0 ] && echo "WSZYSTKO OK" || echo "BŁĘDY"
exit "$FAIL"
