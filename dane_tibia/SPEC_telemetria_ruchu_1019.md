# SPEC: brakujące dane o chodzeniu (telemetria ruchu, 5 dopisków) - 19.10 — SZKIC, czeka na Q1-Q3 Karola

Cel: zbierać dane, których brakowało w analizie `dane_tibia/ruch/ANALIZA_ruch_1019.md`, tak żeby po jednym dniu pracy obu
botów dało się rozstrzygnąć: czy zmieniać trasę (puste odcinki, mobki zabierane przez innych), sposób mijania graczy i wejście
na trzy drabiny do depo Edron. Karol 19.10: „zrób to” (punkty 1, 2, 3, 4 i 6 z analizy).

**Zasada nadrzędna: zachowanie bota się nie zmienia.** Tylko nowe pola i rekordy w telemetrii. Żadnej nowej decyzji, kliku,
pauzy ani RPC. Wszystkie dopiski są addytywne: stare pola zostają z tym samym znaczeniem (analityk.py, porównania z 14-19.10).

## Zakres

### T1 — „stoi” liczone na czasie, nie na obiegu (punkt 1 analizy)

Dziś `ruch_okno.stany[stan][1]` i `powody_idz_s` liczą jako postój każdy odstęp między obiegami (ok. 0,37 s) bez zmiany pola.
Krok postaci trwa ok. 0,6 s, więc w ciągłym marszu co drugi odstęp wygląda na postój: 30% „stoi” wobec 4% z próbek co 1 s.

- Nowe pole w `ruch_okno`: `stoi_1s` = {stan: sekundy} — postój liczony dopiero, gdy pozycja nie zmieniła się przez
  >= `RUCH_STOI_PROG_S` (1,0 s); liczone od chwili ostatniej zmiany pola, odcinek poniżej progu idzie do marszu.
- Nowe pole `powody_idz_1s` = {powód: sekundy} w tej samej definicji.
- Stare `stany`, `powody_s`, `powody_idz_s` bez zmian.
- Miejsce: `telemetria.py` `ruch_tick` (licznik czasu od ostatniej zmiany pola w `self._ruch`).

### T2 — przyczyny postoju zamiast „inne” (punkt 2)

`cavebot._ruch_powod` zna dziś: schody, ogien, utkniecie, walka, loot, patrol_postoj, inne (75-80% postojów to „inne”).
Nowe powody, sprawdzane przed „inne”, wyłącznie z gotowego stanu bota (bez RPC):

| powód | skąd (stan już istniejący) |
|---|---|
| `mijanie` | `self.unikanie` aktywne w trybie mijania (decyzja/udostępnianie przejścia w toku) |
| `unikanie` | `self.unikanie.aktywne` poza mijaniem |
| `wypad` | stan WYPAD/WYPRAWA (wypad.py prowadzi) |
| `przerwa` | `self.przerwa_do` w przyszłości albo stan PRZERWA/PAUZA_PK |
| `pauza_ludzka` | trwa `pauza(PAUZA_DLUGA)` w `_idz_trasa` (znacznik czasu końca ustawiany przed pauzą) |
| `d3` | otwarta zawieszka `self._d3` |
| `pole_zajete` | ostatnia droga/krok odrzucony przez zajęte pole (stwór/gracz na kolejnym polu) w ostatnich 2 s |
| `czeka_na_klik` | od ostatniego kliku w mapę minęło < `KLIK_BEZ_RUCHU` i postać jeszcze nie ruszyła |
| `trasa_stop_potwor` | trasa wstrzymana przez potwora na innym piętrze |

Lista jest zamknięta; czego nie da się ustalić bez RPC, zostaje `inne`. Kolejność sprawdzania jak w tabeli, po istniejących.

### T3 — co blokuje obieg (luki >= 1,5 s, punkt 3)

Luki to 28% czasu bez informacji, który krok obiegu trwał. Dziś `fazy` w `tick` mierzą tylko gracz/stwory/telemetria
i trafiają do logu tylko przy „wolnym ticku”.

- Każdy obieg zapamiętuje etykietę gałęzi, którą się zakończył (np. `leczenie`, `jedzenie`, `ogien_wyjdz`, `uh`, `walka`,
  `loot`, `idz_klik`, `idz_krok`, `pietra`, `wypad`, `pauza`, `model`) i czas od początku obiegu do jego końca.
- `ruch_tick` przypisuje lukę (odstęp >= `RUCH_LUKA_S`) etykiecie obiegu, który ją spowodował (poprzedniego).
- Nowe pole w `ruch_okno`: `luki_wg` = {etykieta: [liczba, sekundy]}. Stare `luki`, `luki_s`, `luka_max` bez zmian.
- Etykiety ustawiane jednym przypisaniem w miejscach `return` w `tick` (lista miejsc ustalona przy implementacji, każda
  gałąź bez etykiety daje `nieznane`, żeby było widać, czego brakuje).

### T4 — id stwora w próbce (punkt 4)

- `probka.stwory[]` dostaje pole `id` (jest w `lista` już dziś, w `decyzja.opcje` też). Dla graczy również.
- Koszt: ok. +15 bajtów na wpis, szacunkowo +10% rozmiaru pliku telemetrii (dziś 10-20 MB/dzień na instancję).
- To pozwala policzyć offline: mobki, którym spada HP, gdy nie są naszym celem (bije ktoś inny), mobki znikające żywe
  z widoku, czas od zniknięcia do pojawienia się w tym samym miejscu (przybliżony respawn).

### T5 — pełny błąd wyprawy (punkt 6)

`wypad._blad` zapisuje dziś `rodzaj`, `faza` i to, co przekaże wołający (przy drabinie tylko `proba`, `tryb`).

- `_blad` dokłada zawsze: `poz` (ostatnia znana pozycja), `etap` (indeks etapu planu), `cel` (pole przejścia/etapu,
  jeśli znane), `czas_s` (od początku bieżącego etapu).
- Po udanym przejściu etapu, który miał błędy: zdarzenie `wypad_etap_ok` z `etap`, `poz`, `proby`, `czas_s` (żeby było
  widać, ile kosztuje każda z trzech drabin: (33146,31823,11), (33150,31820,10), (33167,31824,9)).

## Poza zakresem

Punkty 5, 7, 8 analizy (statystyki odcinków pętli, prędkość postaci, rozjazd `poz`/`stwory`). Jakakolwiek zmiana trasy,
mijania, drabin czy progów. Ratunek Haiku (osobny spec).

## Weryfikacja

- Testy jednostkowe (`testy/test_ruch_okno.py`, `testy/test_telemetria.py`, nowe przypadki):
  - T1: marsz z obiegami co 0,37 s i krokiem co 0,6 s daje `stoi_1s` = 0; postój 3 s daje 3 s; stare pola bez zmian.
  - T2: każdy nowy powód z atrapy stanu bota; brak stanu daje `inne`.
  - T3: luka 2 s po obiegu z etykietą `loot` trafia do `luki_wg.loot`; obieg bez etykiety daje `nieznane`.
  - T4: każdy wpis `stwory` ma `id`; reszta próbki identyczna jak przed zmianą.
  - T5: `_blad` z drabiny ma `poz`, `etap`, `czas_s`; udany etap po błędzie daje `wypad_etap_ok`.
- Kontrola „bez zmiany zachowania”: pełny zestaw testów jak baza (te same stare czerwone, bez nowych); diff nie dotyka
  żadnej gałęzi decyzyjnej poza przypisaniem etykiety/znacznika.
- Niezależny przegląd diffu (checker).
- Na żywo: po restarcie bota 10 min pracy, odczyt `ruch_okno` i `probka` z nowymi polami, rozmiar pliku telemetrii.
- Po dniu pracy obu botów: raport z nowych pól (`narzedzia/raport_ruchu.py`, tylko odczyt) — odpowiedzi na trzy pytania z celu.

## Fazy (bramki)

- **F1 implementacja** T1-T5 na branchu `feat/telemetria-ruchu` (worktree, baza: bieżący `ruch-r1-1014`), testy, przegląd.
  Bramka: wynik testów i przeglądu do Karola, zgoda na merge i restart.
- **F2 zbieranie**: restart botów w chwili wskazanej przez Karola (Q2), dzień pracy.
- **F3 raport**: liczby z nowych pól i rekomendacja (trasa / mijanie / drabiny) do decyzji Karola.

## Pytania do Karola

| # | Pytanie | Rekomendacja |
|---|---|---|
| Q1 | Nowa miara postoju (T1) obok starej czy zamiast? | **Obok**: stare liczby 14-19.10 zostają porównywalne; po F3 można usunąć starą. |
| Q2 | Kiedy restart botów z nową telemetrią? (bez zgody nie przerywam expienia) | Przy najbliższym naturalnym postoju (refill/powrót do miasta) albo przy Twoim następnym starcie. |
| Q3 | Obie instancje (główna i test) czy tylko główna? | **Obie**: testowa chodzi wolniej (1,0 pola/s) i ma najwięcej zawieszek, warto ją widzieć. |

## Niewiadome

- Czy da się bez RPC odróżnić `pole_zajete` od zwykłego braku drogi we wszystkich ścieżkach marszu (klik, strzałka, pietra) —
  ustalane przy implementacji; gdzie się nie da, zostaje `inne`.
- Rzeczywisty przyrost rozmiaru telemetrii po T4 — zmierzony w F2.
