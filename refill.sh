#!/bin/bash
# Refill (guzik paska charlie.retronic): zakupy w mieście (jedzenie, backpack, blanki, wyjście z miasta) i powrót na spot.
# Kroki bank i depo POMIJAMY (decyzja Karola 19.10): po „Wróć do miasta” (wroc.sh) bot stoi już w depo.
#   ./refill.sh              praca w pierwszym planie: STARTUJ=1 ./serwis.sh --kroki jedzenie,backpack,blanki,wyjscie
#   ./refill.sh --tlo        to samo odłączone (setsid), log w <stan>/refill.log; wraca od razu (używa go guzik paska)
#   ./refill.sh --spot       jak --tlo, ale BEZ zakupów: tylko krok „wyjscie” (serwis prowadzi postać do wyjścia z miasta, potem
#                            STARTUJ=1 rusza bota ostatnią mapą i trybem; uruchom.sh dodaje dojście na spot, gdy postać stoi na z7).
#                            To samo odłączone zadanie, ten sam log, to samo --przerwij; znacznik logu `REFILL: START <czas> spot`
#   ./refill.sh --przerwij   przerywa: ubija refill.sh i serwis.sh tej instancji, daje STOP (serwis.py sam wychodzi, jego `finally`
#                            puszcza wejście), dopiero potem TERM/KILL, na końcu ./zatrzymaj.sh i zwolnij_wejscie.py. Gdy nic
#                            nie biegło: "nic do przerwania", BEZ STOP (klik w nieodświeżone „Przerwij” nie ubije świeżego bota)
# Odmawia (bez ruchu w grze), gdy bot albo serwis tej instancji już działa albo brak gry. RETRONIC_ID wybiera instancję.
# Porażka serwisu = plik STOP (robi to serwis.sh), znacznik `REFILL: BLAD <powód>` w logu, nic nie ponawia się po cichu.
# Ponowne wywołanie po porażce wznawia przerwany serwis (kroki już zrobione serwis pomija; serwis.py pamięta je do 3 h, ale
# --tlo kasuje stan starszy niż REFILL_WZNOW_MIN=15 min: wznowienie ma służyć natychmiastowemu ponowieniu, nie po cichu pomijać zakupy).
# REFILL_KROKI (env, domyślnie jedzenie,backpack,blanki,wyjscie) zmienia listę kroków; REFILL_CZEKAJ_STOP_S (domyślnie 5) = ile
# --przerwij czeka, aż serwis.py sam wyjdzie po STOP, zanim ubije go TERM.
# Po sukcesie kasujemy serwis_stan.json: kroki bank/depo nie są tu robione, więc serwis.py nie uznałby przebiegu za
# zakończony i następny refill pomijałby wszystkie kroki (zakupy tylko raz na 3 h).
# Znaczniki w logu (czyta je panel.py --json): `REFILL: START <czas>`, potem `REFILL: OK` | `REFILL: BLAD <powód>` | `REFILL: PRZERWANO`.
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
INST=$(python3 -I "$DIR/instancja.py" powloka) || exit 1; eval "$INST"   # RETRONIC_ID -> INST_* (bez ID: dzisiejsze ścieżki)
TYTUL="Refill Retronic${RETRONIC_ID:+ [$RETRONIC_ID]}"
KROKI="${REFILL_KROKI:-jedzenie,backpack,blanki,wyjscie}"
LOG="$INST_STAN/refill.log"
pidy() { python3 -I "$DIR/instancja.py" pidy '(mozg|cavebot)\.py'; }                           # bot tej instancji
pidy_serwis() { python3 -I "$DIR/instancja.py" pidy '(^|[ /])serwis\.py '; }                    # serwis.py tej instancji
pidy_serwis_sh() { python3 -I "$DIR/instancja.py" pidy-skrypt '^(\S*/)?bash (\S*/)?serwis\.sh( .*)?$'; }   # serwis.sh tej instancji
pidy_refill() { python3 -I "$DIR/instancja.py" pidy-skrypt '^(\S*/)?bash (\S*/)?refill\.sh *$'; }   # praca refill.sh tej instancji

case "${1:-}" in
  "") ;;
  --tlo|--spot)
    [ "$1" = --spot ] && { export REFILL_KROKI=wyjscie REFILL_TRYB=spot; }   # praca dziedziczy env (setsid)
    [ -n "$(pidy_refill; pidy_serwis)" ] && { notify-send "$TYTUL" "Serwis już trwa"; echo "serwis już działa" >&2; exit 1; }
    p=$(pidy | head -1)
    [ -n "$p" ] && { notify-send "$TYTUL" "Bot działa (pid $p): zatrzymaj go przed refillem"; echo "bot działa (pid $p), zatrzymaj: ./zatrzymaj.sh" >&2; exit 1; }
    [ -S "$INST_SOCK" ] || { notify-send "$TYTUL" "Gra nie działa (brak socketu)"; echo "brak socketu gry" >&2; exit 1; }
    mkdir -p "$INST_STAN"
    # stan przerwanego serwisu starszy niż REFILL_WZNOW_MIN (domyślnie 15) min nie wznawia: inaczej po cichu pominąłby zakupy
    [ -n "$(find "$INST_STAN/serwis_stan.json" -mmin +"${REFILL_WZNOW_MIN:-15}" 2>/dev/null)" ] && rm -f "$INST_STAN/serwis_stan.json"
    REFILL_LOG_PRACY="$LOG" setsid -f bash "$DIR/refill.sh" > "$LOG" 2>&1 < /dev/null     # własna sesja i grupa: przeżywa wtyczkę i powłokę, grupa = pid pracy
    echo "refill ruszył, log: $LOG"
    exit 0 ;;
  --przerwij)
    # (1) refill.sh i serwis.sh (żeby nie wystartował bota i nie dopisał nic po serwisie), bez grupy i bez serwis.py
    ubito=0
    for p in $(pidy_refill) $(pidy_serwis_sh); do kill -TERM "$p" 2>/dev/null && ubito=1; done
    [ -n "$(pidy_serwis)" ] && ubito=1
    if [ "$ubito" = 0 ]; then echo "nic do przerwania"; exit 0; fi   # bez STOP i bez zatrzymaj.sh: nie ubijamy świeżo wystartowanego bota
    # (2) STOP: każda akcja myszy w serwis.py woła sprawdz_stop(), więc serwis sam wychodzi, a jego `finally` puszcza wejście
    touch "$INST_STOP" "$INST_STOP_RECZNY"
    for _ in $(seq $(( ${REFILL_CZEKAJ_STOP_S:-5} * 10 ))); do [ -z "$(pidy_serwis)" ] && break; sleep 0.1; done
    # (3) dopiero potem TERM, na końcu KILL
    if [ -n "$(pidy_serwis)" ]; then
      pidy_serwis | xargs -r kill -TERM 2>/dev/null
      for _ in $(seq 20); do [ -z "$(pidy_serwis)" ] && break; sleep 0.1; done
      pidy_serwis | xargs -r kill -KILL 2>/dev/null
    fi
    # (4) bot mógł zdążyć wystartować; potem bezwarunkowe zwolnienie wejścia (zatrzymaj.sh nic nie puszcza, gdy bota nie ma)
    "$DIR/zatrzymaj.sh" > /dev/null 2>&1
    python3 -I "$DIR/zwolnij_wejscie.py" > /dev/null 2>&1
    echo "refill przerwany (STOP ustawiony)"
    exit 0 ;;
  *) echo "użycie: ./refill.sh [--tlo | --spot | --przerwij]" >&2; exit 2 ;;
esac

# --- praca ---
cd "$DIR" || exit 1
echo "REFILL: START $(date +%s) ${REFILL_TRYB:-refill}"
trap 'echo "REFILL: PRZERWANO"; exit 143' TERM INT HUP
STARTUJ=1 "$DIR/serwis.sh" --kroki "$KROKI" &
wait $!
kod=$?
if [ "$kod" = 0 ]; then
  rm -f "$INST_STAN/serwis_stan.json"
  echo "REFILL: OK"
  exit 0
fi
# powód: linia porażki z serwis.py ("SERWIS: PORAŻKA w kroku X: ..."), inaczej ostatnia linia wyjścia (np. odmowa serwis.sh)
# (log czytamy tylko wtedy, gdy ten przebieg pisze do refill.log, czyli z --tlo; w pierwszym planie powód widać na ekranie)
powod=
if [ -n "${REFILL_LOG_PRACY:-}" ]; then
  powod=$(grep -h 'SERWIS: PORAŻKA' "$REFILL_LOG_PRACY" 2>/dev/null | tail -1 | sed 's/^SERWIS: PORAŻKA w kroku //')
  [ -n "$powod" ] || powod=$(grep -hv '^REFILL:' "$REFILL_LOG_PRACY" 2>/dev/null | grep . | tail -1)
fi
echo "REFILL: BLAD ${powod:-kod $kod}"
notify-send "$TYTUL" "Błąd: ${powod:-kod $kod}"
exit "$kod"
