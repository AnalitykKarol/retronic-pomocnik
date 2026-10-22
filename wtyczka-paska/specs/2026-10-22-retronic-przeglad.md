Status: ZATWIERDZONY 2026-10-22 (Karol); F1 ZROBIONE 2026-10-22 (kontrakt `stan` zamrożony, sekcja na końcu); F2 ZROBIONE 2026-10-22 (fe-dev, sekcja „F2: wynik” na końcu, czeka na bramkę leada); F3 otwarte
Weight: Feature (nowy widok okna + nowy plik stanu + 1 pole `okno_api.py stan`; rozszerza `2026-10-19-retronic-okno.md`)
Projekt: Retronic, okno zarządzania. Projekt prywatny (bez Notion/Slacka). Makiety: `scratchpad/makiety-retronic-menu/2-przeglad-tabela.png` (wariant A, wybrany 22.10) i `1-karty-offline.png`.

# Przegląd postaci i „ostatnio znane” dane

## Cel

Jedno miejsce, w którym widać, co stoi z całą ekipą (docelowo 10 postaci): kto jest w grze i co robi, kto stoi, kto gra ręcznie,
kto jest offline i z jakimi danymi zszedł. Dziś okno pokazuje tylko to, co żyje (`okno_api.py stan`, panel). Postać offline to
puste paski; level, miejsce, powód zatrzymania i czas wyjścia znikają razem z procesem. Brakuje też magic levelu (nikt go nie czyta).

## Zakres

1. Nowa sekcja **Przegląd** (pierwsza pozycja menu w `Sidebar.qml`, powyżej listy postaci): tabela wszystkich postaci, wariant A.
2. **Ostatnio znane**: plik `instancje/<id>/ostatnie.json` (pisze bot/logowanie), pokazywany (a) w wierszach offline Przeglądu,
   (b) na kartach offline w pasku bocznym (2 linie zamiast pustych pasków), (c) jako sekcja „Ostatnio znane” na górze Sesji gry,
   gdy gry nie ma (makieta 1).
3. **Magic level** jako osobna faza (F3): odczyt z czatu, z jawnym UNKNOWN o zakładce i planem pomiaru.

## Non-goals

Wykresy i historia exp; zmiana `grafik.py`/nadzoru; poprawki profili (patrz Open Questions, Q-N); akcje zbiorcze (start/stop wielu
postaci); odczyt ML z pamięci procesu; zmiana paska; nowe procesy w tle (zapis idzie z istniejących: bot, logowanie).
Przegląd tylko czyta: żadnej akcji zmieniającej grę/bota.

## Model danych: `instancje/<id>/ostatnie.json`

Jeden obiekt, wersja `v:1`, nadpisywany w całości (nie dziennik). Wszystkie pola poza `v`, `zapisano`, `zrodlo` mogą być `null`
(„nie wiem” ≠ 0). Czas = epoch (s, jak `telemetria-*.jsonl`).

| Pole | Treść | Źródło |
|---|---|---|
| `v`, `zapisano`, `zrodlo` | wersja, czas zapisu, kto: `bot`/`logowanie`/`stop`/`backfill`/`reczny` | pisarz |
| `postac` | nick | `cb.postac.nazwa` (`telemetria.py` `probka`) |
| `exp`, `level`, `level_proc` | exp z próbki; level i % liczone `rdzen.exp_na_level` (`rdzen.py:34`), jak w `ostatnie.py` makiet | `g["exp"]` |
| `hp`, `max_hp`, `mana`, `max_mana` | wartości bezwzględne (telemetria ma tylko HP%) | `g` (`rdzen.py:30` POLA_GRACZA) |
| `ml`, `ml_proc`, `ml_t`, `ml_zrodlo` | magic level (F3); do F3 zawsze `null` | patrz F3 |
| `poz` `[x,y,z]`, `pietro` | ostatnia pozycja | próbka telemetrii |
| `miasto`, `w_depo` | `panel.miasto_pozycji(poz)` (`panel.py:345`); „poza miastem” = `null` | liczone przy zapisie |
| `mapa`, `tryb[]` | z `ostatni_start.<id>.env` (`okno_api.ostatni_start`, `:641`) | przy zapisie |
| `stan_bota` | `cb.stan` (WYPAD, WALKA, …) | próbka |
| `sesja` | `{start, koniec, zab, exp_start, gold, uh}`; `koniec`=null gdy trwa; liczniki z `ekon_razem` w `telemetria.py` (`zab_razem`, `gold_razem`, `uh_razem` w rekordzie `tik`, `:190`) | bot |
| `na_spocie_od` | czas wejścia na obecną mapę/spot (zmiana `mapa` lub pierwszy zapis po `w_grze`) | bot |
| `w_grze_t` | ostatnia chwila, gdy postać była w grze (do „ostatnio online”) | każdy zapis przez bota/logowanie |
| `alarm` | `{t, tekst(<=200), kod}`; trwały „ostatni alarm” (panel pokazuje alarm tylko 60 s, `panel.py:128-132`) | ścieżki alarmu/STOP bota |
| `stop` | `{t, powod, reczny}`: treść pliku `STOP` (np. „wyprawa: utkniecie…”) lub `STOP_RECZNY` | zapis przy STOP |
| `koniec_sesji` | `alarm_stop` / `wylogowanie` / `znikniecie` (bot padł bez zapisu końca) | logowanie / bot |

Kto pisze: nowy moduł `ostatnie.py` (stdlib, `zapisz(sc, **pola)` = wczytaj stary, scal, zapisz atomowo: plik tymczasowy w tym
samym katalogu + `os.replace`, jak `okno_api.zapisz_atomowo` `:156`; błąd zapisu nigdy nie psuje bota; blokada pisarza jak
`telemetria.lock`). Wywołania:
- **co 60 s** z bota: obok `_ekon_tik` (`telemetria.py:190`, `ekonomia.TIK_S=60`), czyli w tym samym `try/except` i tych samych
  bezpiecznikach zapisu (`_zapis_wlaczony`, atrapa „Ja” nie pisze). Zero nowych wątków i odczytów, dane są już w pamięci próbki;
- **natychmiast** przy: zmianie levelu (porównanie z poprzednim zapisem), zmianie ML (F3), alarmie bota, powstaniu `STOP`/`STOP_RECZNY`,
  wylogowaniu (`logowanie.py:416,434` zdarzenie `wylogowano`), wejściu do gry (`logowanie.py:319` zdarzenie `w_grze`).
  Zdarzenia logowania piszą tylko `w_grze_t`, `koniec_sesji`, `sesja.start/koniec` (bot może nie żyć).
- **backfill jednorazowy**: `ostatnie.py --uzupelnij` odtwarza plik z `telemetria-*.jsonl` (trzymane 4 dni, `telemetria.py:19`),
  `ekonomia-*.jsonl`, `logowanie.jsonl`, `profil.json` (logika ze skryptu `ostatnie.py` z rozpoznania), żeby offline-owe postacie
  (Wydra, Kutangen, Kolanosh) miały dane od razu, nie po następnym uruchomieniu. `zrodlo:"backfill"`.
- Odczyt nie pisze nic. Plik nieczytelny/stary format: `null` we wszystkich polach i znacznik `blad`, nie wyjątek.

## Zmiany w `okno_api.py stan`

`stan_instancji` (`okno_api.py:794`) dostaje jeden dodatkowy krok `krok("ostatnie", ...)` (awaria nie psuje reszty, jak pozostałe
kroki) i `pusty_stan` (`:787`) nowe pola. Kontrakt wsteczny: żadne istniejące pole nie zmienia nazwy ani sensu.

| Pole `stan` | Treść |
|---|---|
| `ostatnie` | zawartość `ostatnie.json` + `wiek_s` (od `zapisano`); `null`, gdy brak pliku |
| `przeglad.stan` | jeden z: `bot_dziala`, `karol_gra`, `zatrzymany`, `zawieszony`, `offline`, `alarm` (reguły niżej) |
| `przeglad.zab_h`, `przeglad.exp_h` | z `ostatnie.sesja`: `zab / (zapisano − start)`, `(exp − exp_start) / …`; tylko gdy bot działa, inaczej `null`; wiek danych ≤ 60 s |
| `przeglad.na_spocie_od` | z `ostatnie.na_spocie_od` (UI liczy „N min”) |
| `przeglad.ostatni_alarm` | `ostatnie.alarm` albo `null` |
| `przeglad.nadzor` | `{aktywny, powod, do, zrodlo}` z **`grafik.poza_nadzorem`** (`grafik.py:94`) na `profil.json` i `wczytaj_konfig()` (`grafik.py:58`); bez własnej kopii reguł |
| `przeglad.stop` | `{auto: bool, reczny: bool}` z istnienia plików `STOP` / `STOP_RECZNY` instancji |

Reguły `przeglad.stan` (kolejność = pierwszeństwo): `alarm` gdy panel zgłasza alarm (`klasa=="alarm"`) → `karol_gra` gdy sesja
działa, bot nie działa i jest `STOP_RECZNY` → `bot_dziala` (`klasa=="dziala"`) → `zatrzymany` (gra jest, bot nie, `STOP`) →
`zawieszony` (nie w grze, `nadzor_do` w przyszłości lub `nadzor:false`) → `offline`. „W grze” = `gra` albo `sesja` z `stan`.
Wydajność: bez nowych podprocesów (`panel.py` już jest wołany per instancja, limit `PANEL_LIMIT_S`); `ostatnie.json` i `profil.json`
to dwa małe pliki. Żadnego skanu logów w `stan` (liczniki są w pliku).

## UI

Widok `PrzegladView.qml` + logika w `RetronicModel.js` (testowana w node jak reszta). Nagłówek: „Przegląd · N postaci”, podtytuł
(klik w wiersz otwiera postać), filtry po prawej, pasek liczników.

**Liczniki:** W GRZE `x / N` · BOT DZIAŁA · KAROL GRA · ZATRZYMANE · OFFLINE (podpis „w tym n zawieszona”) · EXP/H RAZEM (suma
`exp_h`, podpis „n boty”) · RATUNEK DZIŚ (suma `ratunek_dzis`).
**Filtry (chipy `Chip.qml`):** `wszystkie` · `w grze` · `z alarmem` (z licznikiem). „z alarmem” = `przeglad.stan=="alarm"` albo
`ostatni_alarm` z ostatnich 24 h. Filtr jest stanem widoku, nie zapisuje się.
**Grupy:** „W GRZE · n” u góry (dane na żywo), „OFFLINE · n — ostatnio znane, wyszarzone” niżej; w grupie sort wg stanu, potem nick.
**Kolumny (kolejność z makiety):** POSTAĆ (nick + id) · STAN (+ „od kiedy”) · SPOT · PIĘTRO · TRYB · LEVEL (+%) · ML · HP (pasek +
x/max) · MANA · GDZIE (poz lub „Miasto · depo z”) · NA SPOCIE / OSTATNI · ZAB/H · EXP/H · OSTATNI ALARM · NADZÓR.
Offline: HP/MANA jako „max N”, ZAB/H i EXP/H jako „—”, kolumna czasu = „ostatnio hh:mm / wczoraj hh:mm”. ML do F3: „?”.

**Mapowanie stan → kolor (`Theme.qml`):** `bot_dziala` = `Theme.ok`; `karol_gra` = `Theme.cyan` (nowy wariant w
`stateColor` albo w `tone`, bo dziś `stateColor` zna tylko alarm/dziala/stop/brak, `Theme.qml:43`); `zatrzymany` = `Theme.warn`;
`alarm` = `Theme.bad`; `zawieszony` = `Theme.mag`; `offline` = `Theme.dim2`. Tekst alarmu `bad`, „nadzór: do …” `mag`,
„wstrzymany · STOP ręczny” `warn`, „tak” `ok`. Chip stanu = tło `Theme.alpha(kolor, 0.15)` jak `Chip.qml`. Zasada: stan
„Karol gra” nigdy nie jest czerwony ani bursztynowy (to nie awaria).
**Kolumna NADZÓR:** `tak` · `nie · profil` (`nadzor:false`) · `do 24.10 08:30` (`nadzor_do`) · `wstrzymany · STOP ręczny`. Gdy profil
ma jednocześnie `nadzor:false` i `nadzor_do`, pokazujemy to, co faktycznie wynika z `poza_nadzorem` („nie · profil”) i dopisek
w tooltipie (patrz Q-N).
**Klik w wiersz:** wybiera postać i przełącza na jej Sesję gry (`ctl.selected`, jak klik w kartę). Brak innych akcji w wierszu.
**Karta offline w `CharCard.qml`/`Sidebar.qml`:** zamiast pasków HP/MP: linia 1 `✦ z9 · 33121,31756   wczoraj 20:14`, linia 2
`HP 188 · MP 95 · ML ?   do 24.10` (albo powód blokady: `STOP ręczny`). Wysokość karty 92 px (makieta 1).
**Sesja gry, „Ostatnio znane”:** blok nad „Stanem sesji” tylko gdy gry nie ma: LEVEL/%, MAGIC LEVEL, HP max, MANA max, EXP (do
następnego levelu), GOLD Z SESJI; trzy kolumny (gdzie stoi · ostatnia sesja · alarm i nadzór); stopka „źródło: ostatnie.json,
zapisane … przez …”.
Odświeżanie: jak reszta okna (wybrana postać 2 s, pozostałe 5 s, `Backend.qml` timery), bez osobnego timera Przeglądu.

## Fazy (bramki)

- **F1 zapis i API:** `ostatnie.py` + hooki zapisu + backfill; `okno_api.py stan` z polami `ostatnie`/`przeglad`; testy (atrapy
  katalogów: zapis atomowy, scalanie, zapis przy zmianie levelu/alarmie/STOP, odporność na uszkodzony plik, reguły `przeglad.stan`,
  `zab_h`/`exp_h`, `nadzor` zgodne z `grafik.poza_nadzorem`); `test_okno_api`, `test_telemetria` zielone. Na żywo: tylko odczyt
  backfillu dla 7 instancji (żadnego startu/stopu).
- **F2 Przegląd i karty offline:** `PrzegladView.qml`, nowy ton `cyan`, filtry, liczniki, karty offline, blok „Ostatnio znane”; testy
  `RetronicModel.js` (node) i atrapa Quickshell offscreen (wszystkie stany z makiety); zrzut z prawdziwymi danymi.
- **F3 magic level:** patrz niżej; osobna bramka, bo wymaga pomiaru na żywo i może zakończyć się odpowiedzią „nie da się z czatu”.

## F3: odczyt ML z czatu (UNKNOWN do pomiaru)

Fakt: wiadomość „You advanced to magic level N” pojawia się na czacie. **UNKNOWN: w której zakładce** (Default / Server Log /
inna). Magic levelu nie czyta dziś żaden kod: `rdzen.POLA_GRACZA` (`rdzen.py:30`) go nie ma, a `ML_CZAR_AKTYWNY` w `cavebot.py` to
czar treningowy, nie odczyt skilla. Rdzeń wiadomości widzi kanały Default, Game-Chat, Trade, Server Log i prywatne
(`dane_tibia/AUDYT_odczyt_i_mapa.md:43`), a pętla czatu w `mozg.py` (ok. `:940-960`) iteruje po wszystkich zakładkach naraz.
1. **Pomiar (F3a, tylko odczyt):** w tej pętli dopisać zapis każdej linii pasującej do `(advanced|magic level)` razem z polem
   `kanal` do `logi/ml-pomiar-RRRRMMDD.jsonl`. Dwie drogi, bez czekania na pechowy termin: (a) przeszukać istniejące bufory
   (`Server Log` i pozostałe) przez `wiadomosci.py` (`:383`, zapytanie `wiadomosci` z `kanal` i `skan:true`) na działającej postaci
   — tylko odczyt, jedno wywołanie; (b) gdy bufor nie ma starej linii, zostawić pomiar włączony do najbliższego awansu ML (postacie
   z trybem `ml` awansują co kilka godzin do dni; termin nieznany).
2. **Parser (F3b):** gdy kanał znany, regex `You advanced to magic level (\d+)` tylko na tym kanale (i nie od graczy: autor pusty/serwer),
   deduplikacja po `nr` wiadomości i epoce jak w `mozg.py`. Wynik → `ostatnie.ml`, `ml_t`, `ml_zrodlo:"czat"`, zapis natychmiast.
3. **Bazowa wartość:** czat daje tylko zmiany, więc do pierwszego awansu po wdrożeniu ML jest nieznany. Stąd `ml_zrodlo:"reczny"`
   (Q-ML). `ml_proc` zostaje `null` (czat go nie podaje).
4. Gdy ani czat, ani bufory nie dają stałego kanału: F3 kończy się wnioskiem w specu i kolumna ML zostaje „?”. Nie sięgamy po pamięć procesu bez osobnej decyzji.

## Kryteria akceptacji

1. `ostatnie.json` powstaje i odświeża się co 60 s tylko u działającego bota; przy zmianie levelu, alarmie, STOP, wylogowaniu i wejściu
   do gry zapis jest natychmiastowy; plik nigdy nie jest w połowie zapisany (test: przerwanie między tmp a replace).
2. `okno_api.py stan` zwraca stare pola bez zmian + nowe; czas odczytu 10 postaci mieści się w `CALOSC_LIMIT_S` (pomiar na atrapie 10 instancji).
3. Reguły stanu: atrapy dla wszystkich 6 stanów, w tym `karol_gra` (STOP_RECZNY + sesja + brak bota) i `zawieszony`.
4. `nadzor` dla Kolanosh zgodne z `grafik.poza_nadzorem` (test na kopii jego profilu).
5. UI: wiersz offline nie ma pustych pasków; „Karol gra” w cyjanie; liczniki zgadzają się z liczbą wierszy; filtry zmieniają listę i
   liczniki chipów; klik w wiersz otwiera Sesję gry właściwej postaci.
6. **Weryfikacja na żywo przez zrzut okna:** okno uruchomione na prawdziwych danych (tylko odczyt, bez ruszania botów i graczy), zrzut
   widoku Przeglądu z ≥1 wierszem „w grze” i ≥1 offline, zrzut karty offline i bloku „Ostatnio znane” (np. Kolanosh); porównanie z
   `okno_api.py stan` i z makietą. Zrzut sprawdzony wzrokiem, nie tylko przez test offscreen.
7. Backfill dla Kolanosh daje level 10, 13%, ostatni alarm 21.10 20:14 (wartości z rozpoznania; do potwierdzenia na dniu testu,
   bo telemetria żyje 4 dni).
8. F3: kolumna ML nie pokazuje wartości niepotwierdzonej; „?” zostaje, dopóki nie ma odczytu albo ręcznego `ml`.

## Ryzyka

| Ryzyko | Ograniczenie |
|---|---|
| Zapis w pętli bota (opóźnienie ticka) | 1 zapis/60 s, ~1 KB, `try/except` jak telemetria; natychmiastowe zapisy tylko przy rzadkich zdarzeniach; pomiar czasu zapisu w teście (<5 ms) |
| Dwa pisarze (bot i logowanie) nadpisują się | zapis = wczytaj+scal pod blokadą pliku; pola rozdzielone (logowanie nie dotyka pól bota) |
| Wyścig odczyt/zapis | atomowy `os.replace`; czytnik toleruje brak/uszkodzenie |
| Dane „stare” wyglądają jak świeże | `wiek_s` + podpis „ostatnio …” w każdym wierszu offline; w grze liczniki pokazują wiek, gdy >120 s |
| `okno_api stan` przy 10 postaciach | brak nowych podprocesów i skanów logów; limit i równoległość bez zmian (`cmd_stan`, `:850`) |
| Bot pada bez zapisu końca sesji | `koniec_sesji:"znikniecie"` wnioskowane w API (brak bota, gra jest/nie ma, `zapisano` stare) |
| ML z czatu z fałszywego źródła (gracz pisze) | parser tylko na kanale systemowym, autor pusty; do pomiaru nie ufamy |
| Rozjazd reguły „w grze” między oknem a nadzorcą (`nadzor_stan.py`) | wspólne pola z `stan`, bez drugiej implementacji |

## Open Questions (rekomendacja)

- **Q-N (osobny punkt) Kolanosh, `nadzor:false` razem z `nadzor_do`.** `instancje/kolanoth/profil.json` ma `"nadzor": false` i
  `"nadzor_do": "2026-10-24 08:30"` (uwagi: „tymczasowo zablokowany na dwa dni… potem wraca do grafiku sam”). `grafik.poza_nadzorem`
  (`grafik.py:98-100`) sprawdza `nadzor is False` jako pierwsze, więc zwraca „bezterminowo” i do `nadzor_do` w ogóle nie dochodzi:
  24.10 08:30 postać **nie wróci** do nadzoru sama. Opis bez poprawki; Przegląd pokaże „nie · profil” + tooltip o rozbieżności,
  dopóki Karol nie zdecyduje. Rekomendacja: osobna drobna zmiana poza tym specem (usunięcie `nadzor:false` z profilu albo reguła
  „`nadzor_do` wygrywa”), z testem w `testy/` dla `grafik`. Decyzja Karola.
- **Q-ML Ręczne ustawienie ML.** Czat nie poda wartości bazowej. Rekomendacja: `okno_api.py ml-ustaw --instancja ID N`
  (zapisuje `ml`, `ml_zrodlo:"reczny"`, tylko `ostatnie.json`; do wywołania z konsoli), bez pola edycji w UI v1. Alternatywa: ML „?”
  do pierwszego awansu.
- **Q-Zakres „ostatnie” dla `test*`.** Instancje `test*` są poza nadzorem (`grafik.py:117`). Rekomendacja: pokazywać je w Przeglądzie
  w grupie offline/zawieszone, ale bez wliczania do EXP/H i „W GRZE x/N”.
- **Q-Alarm 24 h.** Filtr „z alarmem” = alarm z ostatnich 24 h? Rekomendacja: tak (na makiecie 5 z 7), bo alarm sprzed godziny też wymaga
  przejrzenia; kasowanie flagi przy następnej udanej sesji nie jest potrzebne (znika sam po 24 h).
- **Q-Backfill.** Wymaga jednorazowego uruchomienia `ostatnie.py --uzupelnij` (zapis w `instancje/*`, poziom repo/dane, bez systemu).
  Rekomendacja: tak, w F1, po przeglądzie wyniku na sucho.
- **Q-Kolejność faz.** F3 równolegle do F2 czy po? Rekomendacja: pomiar F3a uruchomić od razu po F1 (zbiera dane w tle),
  parser F3b po F2.

## F1: kontrakt ZAMROŻONY (22.10, be-dev)

Stan: F1 zaimplementowane i zweryfikowane testami + backfill na 5 offline-owych instancjach. Poniższe nazwy i sens pól są
**FROZEN**: F2 (QML) importuje je 1:1, zmiana tylko przez lead + wpis tutaj. Wsteczność: wszystkie dotychczasowe pola `stan`
bez zmian; dodane tylko `ostatnie` i `przeglad` (w `pusty_stan` oba `null`).

### `stan.instancje[].ostatnie` (`null`, gdy brak pliku; przy uszkodzonym pliku obiekt z samymi `null` + `blad`)
Wszystkie klucze zawsze obecne (`ostatnie.KLUCZE`), wartość nieznana = `null` (nigdy 0): `v`(=1) `zapisano` `zrodlo`
(`bot`/`logowanie`/`stop`/`backfill`/`reczny`) `dane_t` (czas ostatnich DANYCH z gry; `zapisano` to czas zapisu pliku, to nie to samo)
`postac` `exp` `level` `level_proc` `hp` (wartość bezwzględna lub null) `max_hp` `mana` `max_mana` `ml` `ml_proc` `ml_t` `ml_zrodlo`
(`reczny`/`czat`) `poz[x,y,z]` `pietro` `miasto` `w_depo` `mapa` `tryb[]` `stan_bota` `sesja{start,koniec,zab,exp_start,gold,uh}`
`na_spocie_od` `w_grze_t` `alarm{t,tekst,kod}` `stop{t,powod,reczny}` `koniec_sesji` (`alarm_stop`/`wylogowanie`/`znikniecie`/null)
`przyblizone[]` (nazwy pól odtworzonych/przybliżonych w backfillu, np. `["max_hp"]`) + dodane przez API: `wiek_s` (od `zapisano`), `blad`.

### `stan.instancje[].przeglad`
`stan` (`bot_dziala`|`karol_gra`|`zatrzymany`|`zawieszony`|`offline`|`alarm`) · `w_grze` bool · `test` bool (id `test*`) ·
`zab_h` · `exp_h` (liczby lub null) · `dane_wiek_s` (od `ostatnie.dane_t`) · `na_spocie_od` · `ostatni_alarm` (`{t,tekst,kod}`|null) ·
`alarm_24h` bool · `koniec_sesji` · `nadzor{aktywny,powod,do,zrodlo}` (`zrodlo`: null|`profil`|`konfiguracja`|`test`|`brak_profilu`|`glowna`;
z `grafik.powod_poza_pula`/`poza_nadzorem`, bez kopii reguł) · `stop{auto,reczny}`.
Reguły `stan` (kolejność): `alarm` (panel `klasa=="alarm"`) → `karol_gra` (w grze, brak bota, `STOP_RECZNY`) → `bot_dziala`
(`klasa=="dziala"` albo bot żyje bez klasy) → `zatrzymany` (w grze, brak bota, nie `karol_gra`) → `zawieszony` (nie w grze,
`nadzor.zrodlo` = `profil`/`konfiguracja`) → `offline`.
`zab_h`/`exp_h`: tylko `stan` ∈ {`bot_dziala`,`alarm`} z żywym botem, `dane_wiek_s ≤ 90`, sesja ≥ 60 s i `koniec_sesji == null`.

### Rozstrzygnięcia Open Questions (lead 22.10) i odstępstwa od szkicu
- **Q-N:** zrobione w `grafik.poza_nadzorem`: przyszły `nadzor_do` wygrywa z `nadzor:false` (test `test_grafik`); wygasły `nadzor_do` = postać wraca.
  Profil Kolanosh bez zmian (po 24.10 08:30 wróci sama). Dopisek w tooltipie z Q-N staje się zbędny.
- **Q-ML:** `okno_api.py ml-ustaw --instancja ID N` zapisuje wyłącznie `ml`, `ml_proc=null`, `ml_t`, `ml_zrodlo:"reczny"` w `ostatnie.json`.
- **Q-Zakres:** instancje `test*` są w `stan` (`przeglad.test:true`); F2 nie wlicza ich do sum.
- **Q-Alarm:** `alarm_24h` = alarm młodszy niż 24 h (filtr „z alarmem” = `stan=="alarm"` lub `alarm_24h`).
- **Q-Backfill:** wykonany jednorazowo (`ostatnie.py --uzupelnij`, najpierw `--sucho`), tylko instancje offline (kolanoth, kutangen, wydra, invincible, dawajkesh); odchyd i gebelish (żywe boty) bez pliku do pierwszego zapisu przez bota po restarcie.
- **Odstępstwa od szkicu:** (1) tolerancja świeżości `zab_h/exp_h` 90 s zamiast 60 s (bot pisze co 60 s); (2) minimalna sesja 60 s; (3) `zawieszony` tylko z `profil`/`konfiguracja`, nie dla `test*`/brak profilu/główna; (4) `zatrzymany` = w grze bez bota i bez `STOP_RECZNY` (niezależnie od istnienia pliku `STOP`); (5) dodane pola `dane_t`, `przyblizone`, `dane_wiek_s`, `alarm_24h`, `w_grze`, `test`.
- **UNKNOWN:** `max_hp` w backfillu jest przybliżeniem z HP% i HP z logowania (`przyblizone:["max_hp"]`); bot po restarcie zapisze wartość dokładną. Zakładka czatu dla ML — nadal F3.
- Hooki zapisu: bot (co 60 s z `Telemetria.probka`, natychmiast przy zmianie levelu ≤1/5 s, alarmie ≤1/30 s dla tego samego tekstu), STOP (`mozg.py`), logowanie (`w_grze`, `zaloguj` kod 0, `wylogowano`; wyłączone przy `RETRONIC_TESTY`). Zapis: blokada `ostatnie.lock` (bot czeka ≤ 0,05 s, inni 2 s), `os.replace`, błąd tylko diagnostyka. Zmiany w botach działają od ich najbliższego restartu.

## F2: wynik (22.10, fe-dev)
Stan: zaimplementowane i wdrożone do `okno/` (hot reload otwartego okna), zweryfikowane offscreen; czeka na bramkę leada.
- Pliki: nowe `PrzegladView.qml`, `PrzegladModel.js`, `OstatnioZnane.qml`, `test/Przeglad.test.js`, `test/stan-przeglad.json`; zmienione (kopie `.bak-20261022-przeglad-f2`) `Theme.qml`, `NavItem.qml`, `CharCard.qml`, `Sidebar.qml`, `SesjaView.qml`, `Backend.qml`, `shell.qml`, `qmldir`, `Scenariusz.qml`.
- Kontrakt `stan` użyty 1:1, API bez zmian. Kutangen: „rezerwa / poza nadzorem” wyliczane w UI (`stan zawieszony` bez `nadzor.do`); sensowniejsze byłoby pole `przeglad.rezerwa` w API (propozycja, nie zrobione).
- Odstępstwa od makiety: tabela ma stałe szerokości kolumn i przewija się poziomo w oknie węższym niż ok. 2250 px (makieta zakłada szerszy ekran); na karcie offline HP/MP max bez „~” (brak miejsca; przybliżenie widać w tabeli i w bloku „Ostatnio znane”); nagłówek „N postaci” liczy też instancje testowe, sumy w licznikach ich nie.
- UNKNOWN: wygląd przy `ostatnie` z dużo dłuższymi powodami blokady (zawijane w „Ostatnio znane”, obcinane z elipsą w tabeli); ML zawsze „?” do F3.
- Domyślna sekcja okna = `przeglad` (decyzja Karola 22.10, `okno/Backend.qml:30`); `okno/test/qml-atrapa.sh` A i D jawnie zaczynają od `sekcja:ratunek`.
