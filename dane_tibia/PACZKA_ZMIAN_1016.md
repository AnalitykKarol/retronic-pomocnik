# PACZKA ZMIAN (16.10) — wszystko do jednego testu zbiorczego — SZKIC do akceptu Karola

Powiązane: `SYSTEM_RETRONIC.md` (warstwy, fazy), `SPEC_obrona_pk_szybka_1016.md` (zgon 15:52), `ANALIZA_zaciecie_schody_1016.md`, `SYMULATOR_wyniki_1016.md`.
Zasada: najpierw wszystko napisane i przetestowane offline (atrapy + symulator), potem JEDEN restart bota z włączeniem pokręteł w ustalonej kolejności.

## 0. Co się stało (dowody z logów, nie z pamięci)

- **Zgon 15:52:33** (z9, (32500,32279)): wg SPEC_obrona_pk_szybka (log mózgu); w telemetrii pierwsza próbka `hp=0` o 15:52:33 — zgodne.
- **Telemetria po zgonie** (`logi/telemetria-20261016.jsonl`): `hp=0` w próbkach do **16:08:23** (572 próbki, ~16 min), choć postać stała już w świątyni z7 (WYPAD 15:58:37 przy (32351,32228,7)). To potwierdza dziurę R5 (odczyt HP po respawnie = UNKNOWN przyczyna).
- **Od 15:58:46 bot stoi w `PAUZA_PK`** (≈1500 próbek, 0 zabić). To NIE jest zawieszka D3 (stan zamierzony): `_pk_depo_tick` czeka na koniec karencji. `wrogowie.json`: ostatnie zobaczenie Tojsona (czaszka) o 16:18:46 odsunęło karencję o 30 min → **`karencja_do` = 16:48:46**; po niej, bez wroga w widoku, bot sam wraca na spot (`start_pk("powrot")`). Czas stracony: od 15:52 do ok. 16:50 (~1 h), plus zgon.
- Obserwator (Haiku) zgłasza „PAUZA_PK bez przyczyny” co minutę od 16:15, bo nie widzi karencji w swoim kontekście → szum (to też do poprawy: dać mu `karencja_pozostalo_s`).
- UNKNOWN: w próbce 16:39 w `stwory` jest gracz o nicku „Mastafian” (dx 5, dy −3) obok własnej postaci — czy to druga instancja, czy błąd odczytu nicku.

## 1. Rejestr zmian

| ID | Zmiana | Stan | Pokrętło | Test |
|----|--------|------|----------|------|
| P1 | Drzwi: ponowne podejście przy nieaktualnej fladze `otw` | KOD GOTOWY (2d6a7bd) | `DRZWI_PONOW` 0 | test_drzwi_ponow (czerwony na starym) |
| P2 | D3: cień (log pierwszej dopuszczalnej opcji) i alarm | KOD GOTOWY | `D3_REAKCJA` 0/1, `D3_ALARM_S` | test_d3_zawieszka 8b |
| P3 | Wpadnięcie: nauka dziur tylko z flagą 2 i bez schodów | KOD GOTOWY (a556d1a) | `WPADNIECIE_WALIDACJA` 0 | test_wpadniecie_walidacja |
| P4 | Usunąć fałszywy wpis `[32498,32271,8]` z `dziury_nauczone.json` | CZEKA NA ZGODĘ (dane na żywo) | — | symulator waliduj, test zgodności |
| P5 | PK R5: wykrycie śmierci → stan `MARTWY`, STOP, popup „Bot zginął” (1 raz), model blokowany w `mozg.py` | KOD GOTOWY, niezacommitowany→patrz git log; checker NITS | `SMIERC_STOP` 0 (+ `SMIERC_ODCZYTY` 3, `SMIERC_SKOK` 8) | test_smierc_stop 20/20; replay telemetrii: zgon 15:52:33 potwierdzony po ok. 2 s, 0 fałszywych STOP w całym dniu |
| P6 | PK R2: reakcja na PK bez wywołania modelu na ścieżce (model w tle, `pauza_bota`/`kontynuuj` zablokowane przy HP<50% / alarmie) | SPEC, bez kodu | `PK_SZYBKIE` | odtworzenie 15:52:08–33, pętla nie blokuje >0,3 s |
| P7 | PK R1: czaszka lokalnie (<200 ms) | SPEC, UNKNOWN kolory ikon | `PK_SZYBKIE` | zrzuty czaszek (do zebrania) |
| P8 | PK R3/R4: UH przy 30% + predykcja, szybsza sekwencja (Ctrl+klik), ucieczka nie zamienia się w walkę z orkiem | SPEC, decyzje Karola (sekcja 6 speca) | `PK_UH_HP`, `PK_UH_CTRL` | odtworzenie, atrapa UH |
| P9 | **DECYZJA KAROLA 16.10: po zgonie bot nic nie robi** (żadnej ucieczki/powrotu), tylko STOP i popup — realizuje P5 | ZDECYDOWANE | `SMIERC_STOP` | j.w. |
| P10 | Obserwator: kontekst z karencją PK (koniec szumu co minutę) | NOWE, małe | — | test_obserwator |
| P11 | F3: reguły z symulatora wybierają opcję D3 (cień → wykonanie) | PLAN | `D3_REAKCJA` 1→2 | symulator + 99 epizodów |
| P12 | Serwis w mieście (bank/depo/bag/blanki) | SPEC, UNKNOWN NPC i progi | `WYPRAWA_SERWIS` 0 | atrapy, potem na żywo z Karolem |
| P13 | Naprawy z ANALIZY zacięcia schody (poza fałszywą dziurą: krok „w górę” (32497,32269)) | UNKNOWN przyczyna kroku | — | repro `dane_tibia/repro/` |
| P14 | „Kilka rzeczy do zmian” od Karola | **CZEKA NA LISTĘ** | — | — |

## 2. Test zbiorczy (jeden przebieg)

1. **Offline, bez bota:** wszystkie `testy/test_*.py` (dziś 77/79, 2 pomijane przez brak zrzutów), `narzedzia/symulator_zawieszek.py waliduj`, test zgodności z `pietra.py`, nowe testy P5–P10.
2. **Odtworzenia z logów:** sekwencja 15:52:08–33 (P6/P8), zawieszka drzwi 11:21–11:49 (P1), zacięcie 14:51–14:53 (P3/P4), pętla PAUZA_PK po zgonie (P9).
3. **Jeden restart** (z Twojej zgody): kolejność włączania po restarcie — `D3_REAKCJA=1` (cień) → `WPADNIECIE_WALIDACJA=1` → `PK_SZYBKIE=1`; po każdym 15 min obserwacji w logu (bez nowych ostrzeżeń), cofnięcie = wpis 0 w `na_zywo.json` (hot-reload).
4. **Na żywo z Twoim udziałem (osobne zgody):** pomiar sekwencji UH na siebie (jedna runa, poza walką), sprawdzenie Ctrl+klik na runie.

## 3. Decyzje do Karola

1. Lista „kilku rzeczy do zmian” (P14).
2. Sekcja 6 speca PK: próg UH 30% (+predykcja?), rezerwa many w trybie UH, kolejność paczek (P5+P6+P7 pierwsza, P8 druga).
3. P9: czy po zgonie bot ma wracać sam (jak dziś, po karencji), czy tylko alarm + STOP do Twojej decyzji (zgon = utrata plecaka z UH).
4. P4 i restart: kiedy (dziś bot i tak stoi w PAUZA_PK do ok. 16:48, więc restart teraz niczego nie przerywa — ale to Twoja decyzja).

## 4. Znane ograniczenia P5 (checker + budowniczy)
- Zgon potwierdzany po 3 kolejnych odczytach HP 0 (ok. 2 s) lub przy HP 0 ze skokiem >=8 pól/zmianą piętra; w tym oknie bot nie leczy (1-2 obiegi).
- Bot uruchomiony z fałszywym HP 0 trwającym >=3 odczyty zatrzyma się jako „martwy” (nie do odróżnienia bez dodatkowej przesłanki).
- Dymek `notify-send` nieprzetestowany w grze (testy wyłączają powiadomienia); możliwy drugi, generyczny dymek „Bot zatrzymany” z `mozg.py`.
- Przyczyna HP 0 po respawnie (~16 min w telemetrii) nadal UNKNOWN, obejście: w `MARTWY` odczyt HP nie ma znaczenia.

## 5. Stan po integracji (16.10 wieczór)
Patch zbiorczy wprowadzony do repo (P6, P7-narzędzie, P8, P10, F3-cień). 88 plików testowych, czerwone tylko 2 znane (`test_loot_*`, brak zrzutów).
**Bez niezależnego przeglądu** (checker padł na ECONNRESET, klasyfikator bezpieczeństwa był niedostępny przy P6 i integracji). Wszystkie nowe pokrętła domyślnie 0
(`PK_SZYBKIE`, `PK_UH_SZYBKIE`, `PK_UH_CTRL`, `OBSERWATOR_PK_KONTEKST`, `SMIERC_STOP`, `D3_REAKCJA`, `D3_ALARM_S`, `DRZWI_PONOW`, `WPADNIECIE_WALIDACJA`);
`PK_UH_PREDYKCJA=1` i `PK_UH_HP_SZYBKI=30` działają tylko przy `PK_UH_SZYBKIE=1`.
Odkrycie P6: 4 s martwego czasu przed zgonem to synchroniczny `paplay` w `cavebot.alarm_dzwiekowy` (log: dokładnie +4 s po każdej linii ALARM), nie model.
Inne synchroniczne alarmy na ścieżkach reakcji (niskie HP `cavebot.py` ~7508, gracz na ekranie ~3827, strażnik ~4296/4354, PVP ~7101, UH ~1644/1706) NIE zmienione: do osobnej poprawki.
P7: detektora czaszki nie ma (2 próbki białej, 0 czerwonej/żółtej, 0 obrazów z czaszką); jest `narzedzia/zbierz_czaszki.py` i `CZASZKA_ZAPIS_PROBEK` do zbierania próbek.
P10: licznik pauzy w obserwatorze ograniczony oknem 300 s, więc warunek „PAUZA_PK > 5 min” praktycznie nie zadziała (do decyzji: dłuższe okno albo licznik w cavebocie).

## 6. Przegląd paczki (16.10 wieczór, 2 niezależnych recenzentów): NITS, bez blokerów startu
Potwierdzone: przy pokrętłach 0 zachowanie bez zmian, import i walidacja `na_zywo.przyklad.json` OK, testy zielone, kierunki pokręteł (`nie_wyzej`) blokują samodzielne włączenie przez analityka, `SMIERC_STOP` wymaga 3 odczytów HP 0 albo skoku pozycji.
Do poprawki po teście na żywo (nie blokują):
1. `PK_UH_SZYBKIE=1` obniża próg UH z 40 do 30 (stary próg pomijany); predykcja (spadek >=15 pp/2 s przy HP<=50) częściowo równoważy.
2. Gałąź „UH bez menu” w `_pk_uh_na_siebie` woła alarm synchronicznie (`paplay` do 4 s) przy HP<=30%; reszta synchronicznych alarmów (HP niskie ~7508, gracz ~3827, strażnik ~4296/4354, PVP ~7101, UH ~1644/1706) też.
3. `PK_SZYBKIE=1` wycina `obcy_gracz` przy HP<50% także, gdy HP spadło od moba (np. prośba o handel dostaje samo „kontynuuj”).
4. P10: `pauza_pk_trwa_s` ograniczone oknem 300 s, więc alert o pauzie po wygaśnięciu karencji praktycznie nie zadziała.
5. `PK_UH_CTRL`: licznik porażek Ctrl zerowany przy każdym `ok` (też z menu); weryfikacja `ok` przez wzrost HP może przypisać sukces exurze. `_pk_szybkie` czyta `ostatni_gracz` bez sprawdzania wieku próbki. Cień F3: budżet 50 ms dopiero po 3 próbkach. `czaszka._zapisz_probke`: nadpisywanie w tej samej sekundzie, brak limitu katalogu.

## 7. Protokół testu na żywo (runy drogie: minimum prób)
Kolejność pokręteł po restarcie: `D3_REAKCJA=1` → `WPADNIECIE_WALIDACJA=1` → `SMIERC_STOP=1` → `PK_SZYBKIE=1` → na końcu `PK_UH_SZYBKIE=1` i `OBSERWATOR_PK_KONTEKST=1`.
- **UH na siebie:** jedna runa, poza walką, przy HP<100%; zmierzyć czas sekwencji (cel <=1 s) i ile HP leczy. `PK_UH_CTRL=0` (Ctrl+klik na runie = UNKNOWN; test osobno, za zgodą, jedna runa).
- **HMM na potwory:** runa z ręki Karola w moba, który i tak jest w walce; zmierzyć odstęp użyć (exhaust 2 s po ataku? UNKNOWN) i czy telemetria/`obserwator_reczny` zapisują użycie run.
- **Czaszki:** `CZASZKA_ZAPIS_PROBEK=1` (env) zapisuje wycinki do `logi/czaszki/<wynik>/`; cel >=30 obrazów na klasę (biała/czerwona/żółta/brak), potem `narzedzia/zbierz_czaszki.py` i decyzja o detektorze lokalnym. Do tego czasu rozpoznawanie czaszki to nadal Haiku w wątku (3-4 s).
