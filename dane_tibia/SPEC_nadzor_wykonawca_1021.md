# SPEC: grafik + wykonawca nadzorcy (F1 + F2 + biała lista) - 21.10

Realizuje `SPEC_nadzorca_rotacja_1021.md` (decyzje Karola ~16:30: 5 online, zmiana = jeden hunt 2-3 h, przerwa 30-120 min,
limit 8 h/dzień, cisza 01:00-08:00, odstęp 7-25 min, cała biała lista bez pytania) i `SPEC_nadzorca_zestawu_1021.md` (warstwy
A/B/C, blokady). Ten dokument opisuje tylko kod: `grafik.py`, `nadzor.py`, `NADZORCA.md`, `instancje/_wspolne/nadzor_konfig.json`.

## Pliki

| plik | rola |
|---|---|
| `grafik.py` | deterministyczny grafik doby: `pokaz`, `nowy [--od-teraz]`, `waliduj` |
| `nadzor.py` | wykonawca: `cien --raz` / `tick` / `napraw <id> <rodzaj>` / `stan` / `odblokuj <id>` |
| `NADZORCA.md` | reguły obchodu modelu (świeże `claude -p`, Haiku; Sonnet przy odchyleniu) |
| `instancje/_wspolne/nadzor_konfig.json` | wszystkie widełki i limity (brak pliku = wartości domyślne w kodzie) |
| `instancje/_wspolne/grafik-RRRRMMDD.json` | grafik doby (ręczna edycja wygrywa: istniejący plik nigdy nie jest nadpisywany bez `nowy`) |
| `instancje/_wspolne/logi/nadzor-RRRRMMDD.jsonl` | każda decyzja i akcja z jednym zdaniem uzasadnienia |
| `instancje/_wspolne/nadzor_stan.json` | stan wykonawcy (fazy, liczniki napraw, minuty dziś, ostatnie zdarzenie logowania) i skrót dla obchodu |
| `instancje/_wspolne/NADZOR_PAUZA` | globalna pauza (zero akcji) |
| `instancje/_wspolne/NADZOR_ZYWO` | **włącznik trybu na żywo**; bez niego `nadzor.py` zawsze działa w CIENIU |

## Doba i grafik

- **Doba** = od 08:00 (koniec ciszy) do 08:00 następnego dnia; nazwa pliku to data jej początku. Logowania wolno od 08:00,
  wylogowania muszą być do 01:00 (cisza 01:00-08:00 = zero logowań i zero postaci online).
- **Zmiana** `{id, od, koniec, wylog, mapa, tryb}`: `od` = logowanie, `koniec` = początek powrotu do miasta (WROC),
  `wylog` = planowane wylogowanie (`koniec` + `miasto_min`). Zdarzeniami odstępu są `od` i `wylog`.
- Pula: `instancje/*/profil.json`, bez katalogów zaczynających się od `_`, bez `test*`, bez `"nadzor": false`.
- Generator (czysta funkcja daty, puli i konfiguracji, ziarno = data): dla każdej postaci łańcuch zmian (hunt 120-180 min +
  `miasto_min`, przerwa 30-120 min), pierwsze logowanie = 08:00 + przesunięcie, które z dnia na dzień zmienia się losowo o
  najwyżej ±60 min (błądzenie ograniczone do 0-240 min). Zmiany wstawiane po kolei; każda para (logowanie, wylogowanie)
  dostaje najwcześniejszy termin, w którym oba zdarzenia mają od wszystkich już wstawionych zdarzeń odstęp
  >= losowy 7-25 min, nie przekraczają `max_online` i mieszczą się w limicie dziennym i ciszy. Twarde gwarancje: odstęp >= 7 min,
  <= N online, <= 480 min/postać/dobę, zero zdarzeń w ciszy.
- `nowy --od-teraz`: postacie już online (sesja gry) są przyjęte jako zmiany w toku (`adoptowana`: start przyjęty 30 min temu, koniec = start + losowy hunt, nie wcześniej niż za 5 min),
  reszta dostaje zmiany od teraz. Stary plik trafia do kopii `.bak-HHMMSS`.
- `mapa`/`tryb` zmiany: konfiguracja postaci -> inaczej `null` i wykonawca bierze **bieżące** z `tryb.log` (nie z `ostatni_start.*.env`).

## Wykonawca

Cykl postaci: `OFFLINE -> LOGOWANIE -> DOJSCIE -> EXP -> POWROT -> MIASTO -> WYLOGOWANIE -> OFFLINE`. Faza jest wyprowadzana z
obserwacji (procesy, pliki STOP/WROC, log bota), a nie zgadywana z licznika; zapamiętane są tylko znaczniki (kiedy zaczęła się
zmiana, kiedy ostatnie zdarzenie logowania, liczniki napraw).

Koniec zmiany (co pierwsze): czas `koniec` z grafiku, limit dzienny, pełny plecak (>= 3 linie `powód sloty_pelne` w 10 min),
brak capu (>= 3 linie `powód za_ciezki` w 10 min), brak jedzenia (>= 2 linie `brak jedzenia w plecaku` w 20 min).
`slot_ukryty` NIE jest pełnym plecakiem (to wada odczytu okna, nie stan plecaka). Wylogowanie czeka na spokój (brak
`cel|WALKA|ATAK|Loot|POGON|UCIECZ` w liniach z ostatnich 20 s), najdłużej 15 min.

Blokady w kodzie (sprawdzane przed KAŻDĄ akcją, także eskalacją): `instancje/<id>/STOP_RECZNY` -> zero akcji dla postaci;
`NADZOR_PAUZA` -> zero akcji; `"nadzor": false` -> postać poza nadzorem. Poza grafikiem nic się nie startuje.
**Jedna akcja logowania/wylogowania naraz:** blokada pliku `_wspolne/nadzor_logowanie.lock` oraz zasada "najwyżej jedna taka
akcja na tick". Odstęp od ostatniego zdarzenia (także zewnętrznego: zmiana liczby sesji bez naszej akcji) >= 7 min, a po
wylogowaniu przerwa >= 30 min zanim ta sama postać znów się zaloguje.

Restart bota: zawsze mapa/tryb z OSTATNIEGO `[TRYB] mapa/tryb` w `tryb.log` i `Mózg: ... trasa` z najnowszego `mozg-stdout`
(nie `ostatni_start.<id>.env`, lekcja 21.10 15:36); zatrzymanie bez `STOP_RECZNY` (plik `STOP`, potem TERM); tylko poza walką.

## Biała lista (`nadzor.py napraw <id> <rodzaj>`, bez pytania)

| rodzaj | działanie |
|---|---|
| `restart` | zatrzymaj i uruchom bota na bieżącej mapie/trybie |
| `wznow` | po alarmie bota (STOP bez STOP_RECZNY, bez zgonu/PK/GM): uruchom bota na bieżącej mapie/trybie (zdejmuje STOP) |
| `wroc` | zlecenie WROC (`wroc.sh`) |
| `relog` | po rozłączeniu: ponowne logowanie (`zaloguj.sh`, w razie braku sesji najpierw `sesja_gry.py start`), potem start bota |
| `wyloguj` | `wyloguj.sh` + `sesja_gry.py zamknij` |
| `zmien_spot` | restart na kolejnym spocie z `spoty_zapasowe` w `profil.json` |

Drabina napraw dla zacięcia (okno 90 min): restart, restart, zmiana spotu (jeśli jest zapasowy), WROC i koniec zmiany, potem
eskalacja "wyczerpana rotacja napraw". Nigdy: czat gry, pokrętła ryzyka śmierci, `STOP_RECZNY`, zakładanie kont, handel.

## Eskalacje (`powiadom.py`, critical; bez Slacka/Notion; raz na 30 min na powód)

PK/atak gracza, zgon, GM albo "bot?", IP proxy niezgodne, wyczerpana rotacja napraw, stan nieustalony > 10 min. Po eskalacji
postać jest wstrzymana dla wykonawcy do `nadzor.py odblokuj <id>` (polecenie Karola, poza białą listą modelu).

## Tryby i zależności

- CIEŃ (domyślny): decyzje trafiają tylko do logu ("zrobiłbym X"), nic nie jest uruchamiane. Powtórzenie tej samej decyzji
  jest wpisywane najwyżej raz na 30 min. NA ŻYWO tylko, gdy istnieje `_wspolne/NADZOR_ZYWO`.
- `cien --raz`: jeden przebieg, tylko odczyt i wydruk, **zero zapisów** (także logu i stanu).
- Zależności przez interfejs poleceń: `zaloguj.sh`, `wyloguj.sh`, `logowanie.py stan-ekranu <id>` (K1), `serwis.sh` (miasta z
  planem), `wroc.sh`, `uruchom_instancje.sh`, `sesja_gry.py`, `powiadom.py`. Brak narzędzia = akcja zapisana jako "brak
  narzędzia" (na żywo liczy się jako nieudana naprawa).

## Weryfikacja

`testy/test_grafik.py`: 1000 losowych dób (odstęp >= 7, <= N online, limit dzienny, cisza), determinizm, przesunięcie dzienne,
ręczna edycja wygrywa, pula. `testy/test_nadzor.py` na atrapach w katalogu tymczasowym: STOP_RECZNY = zero akcji,
NADZOR_PAUZA = zero akcji, dwa końce zmian w tej samej minucie -> wylogowania >= 7 min od siebie, restart z `tryb.log`
a nie z env, restart nie w walce, eskalacja przy PK, tryb cienia nic nie uruchamia.

## Wdrożenie

**21.10 17:40 zainstalowane (Karol: „raz na 10, max 5 minut”):** `~/.config/systemd/user/retronic-nadzor.{service,timer}`, przebieg co 5 min
(`OnUnitActiveSec=5min`), tryb CIEŃ (brak `NADZOR_ZYWO`). Pierwszy przebieg 17:40:50 kod 0. Obchód modelu (`retronic-obchod`) jeszcze nie.
Cofnięcie: `systemctl --user disable --now retronic-nadzor.timer`, usunięcie obu plików.

### Propozycje z 21.10 (60 s zmienione na 5 min)

Włączenie na żywo = Karol tworzy `instancje/_wspolne/NADZOR_ZYWO` (usunięcie wraca do cienia); chwilowe wstrzymanie =
`instancje/_wspolne/NADZOR_PAUZA`. Zanim to nastąpi: dzień w cieniu (`tick` z timera, bez `NADZOR_ZYWO`), przegląd
`instancje/_wspolne/logi/nadzor-RRRRMMDD.jsonl` obok grafiku, potem F3 (jedna postać pełnym cyklem).
Uwaga: pierwszy `tick` na żywo przyjmie postacie już online jako zmiany w toku (start 30 min temu); `nowy --od-teraz` robi to samo.

Unit użytkownika `~/.config/systemd/user/retronic-nadzor.service`:

    [Unit]
    Description=Retronic nadzor: jeden przebieg wykonawcy (cien bez NADZOR_ZYWO)
    [Service]
    Type=oneshot
    WorkingDirectory=%h/Games/Retronic/pomocnik
    ExecStart=/usr/bin/python3 -I nadzor.py tick
    TimeoutStartSec=900

`retronic-nadzor.timer`: `[Timer] OnBootSec=2min`, `OnUnitActiveSec=60s`, `AccuracySec=5s`, `[Install] WantedBy=timers.target`.
Drugi przebieg w trakcie trwającego (np. długie wylogowanie) kończy się od razu na blokadzie `nadzor_przebieg.lock`.

Obchód modelu `retronic-obchod.service` + timer co 10 min (`OnUnitActiveSec=10min`), Haiku, Sonnet przy `WYNIK: do_sonneta`:

    ExecStart=/bin/bash -c 'cd %h/Games/Retronic/pomocnik && timeout 300 claude -p --model haiku --no-session-persistence \
      --append-system-prompt-file NADZORCA.md --allowedTools "Bash(python3 -I nadzor.py:*)" "Bash(python3 -I nadzor_stan.py:*)" \
      "Bash(python3 -I logowanie.py stan-ekranu:*)" "Bash(notify-send:*)" Read \
      "Jeden obchód wg NADZORCA.md" >> instancje/_wspolne/logi/obchod-$(date +%%Y%%m%%d).log 2>&1'

## Proponowana zmiana skilla `~/.claude/skills/pilnuj-botow/SKILL.md` (do przejęcia przez Karola/lead)

Zamiast zdania "Naprawy wolno wykonać dopiero po 'tak' Karola" i sekcji "Zakazy" (pierwsze dwa punkty):

    ## Dwa tryby
    - **Ręczny obchód (ta sesja, `/pilnuj-botow`)**: jak dotąd - ocena i powiadomienia. Naprawy tylko przez
      `python3 -I nadzor.py napraw <id> <restart|wznow|wroc|relog|wyloguj|zmien_spot>` (biała lista, bez pytania o "tak"),
      po sprawdzeniu `python3 -I nadzor.py stan` (czy kod już się tym zajmuje: wpis `czekaj` z powodem).
      Reguły szczegółowe: `~/Games/Retronic/pomocnik/NADZORCA.md`.
    - **Nadzór z timera**: wykonawca `nadzor.py tick` prowadzi cykl postaci wg grafiku; obchód modelu (Haiku/Sonnet) wg `NADZORCA.md`.
    Zakazy bez zmian: czat gry, klawisze/kliki, pokrętła (zwłaszcza ryzyka śmierci), `STOP_RECZNY`, `STOP*`/`WROC` ręcznie,
    zakładanie kont, handel, Notion/Slack. `STOP_RECZNY` bez bota = Karol gra: nie ruszać. Po eskalacji (`hold`) postać
    zostaje dla Karola; `nadzor.py odblokuj <id>` tylko na jego polecenie.

## Poprawki po recenzji checkera (21.10)

- **B-1 powiadomienia:** gdy `powiadom.py` jest wyciszony (plik `cisza` w katalogu pomocnika albo `RETRONIC_POWIADOMIENIA=0`), tryb na
  żywo NIE startuje: przebieg pracuje w cieniu, wpis `zywy_zablokowany` w dzienniku, `napraw` odmawia (kod 3), cień ostrzega
  ("eskalacje niewidoczne: plik cisza"), `nadzor.py stan` ma `powiadomienia_wylaczone` i `uwagi`. Hold zapisuje `powiadomiono`; hold bez
  dostarczonego powiadomienia jest w `stan.uwagi`, w odmowie bramki i jest ponawiany, gdy powiadomienia znów działają. Cień nie
  "zużywa" zdarzeń eskalacji (po włączeniu żywego trybu Karol je dostanie). Pliku `cisza` nie ruszamy.
- **B-2 bramki przed każdą akcją:** STOP_RECZNY / NADZOR_PAUZA / `nadzor: false` / hold sprawdzane w `wykonaj`, po zdobyciu blokady
  logowania w `_wykonaj_zywo`, tuż przed `start_bota` (uruchom.sh kasuje STOP_RECZNY) i w `_restart` po zatrzymaniu bota.
- **B-3 dowód miasta:** serwis i wylogowanie tylko przy dodatnim dowodzie z obserwacji (log `DEPO osiągnięte` po starcie bota albo
  `panel.w_depo`/`w_miescie`), niezależnie od zapamiętanej fazy; STOP bez dowodu (alarm w połowie WROC) = drabina napraw/eskalacja.
- **B-4 zalegający STOP:** w fazie LOGOWANIE/DOJSCIE naszej sesji start bota mimo pliku STOP (uruchom.sh go czyści), nigdy przy STOP_RECZNY.
- **B-5:** licznik porażek wylogowania (kody 1/5/7/8), po 3 eskalacja "stan nieustalony" (bez hold), kod 6 = zgon (hold); `zaloguj.sh`
  kod 9 (zła postać) i 6 = eskalacja z hold; strażnik walki także dla `zmien_spot`; `sys.dont_write_bytecode` w `nadzor.py` i
  `grafik.py` (cień nie zostawia `__pycache__`). Po własnym logowaniu/wylogowaniu zestaw sesji jest odświeżany (brak fałszywego
  "zdarzenia zewnętrznego").
