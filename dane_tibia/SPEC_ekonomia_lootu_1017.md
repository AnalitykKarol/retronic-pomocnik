# SPEC: dziennik ekonomii bota (gold, uhy, exp, jedzenie, cenne dropy) — 17.10

Status: ZAIMPLEMENTOWANE W WORKTREE, NIEWDROŻONE (27/27 testów `testy/test_ekonomia.py`; decyzje Karola z 17.10 niżej). Branch `feat/ekonomia-lootu`, worktree
`pomocnik-ekonomia`. Wdrożenie (restart bota) tylko na słowo Karola, w przerwie od expienia.

## Po co
17.10 porównanie goblinów z trollami (gold, jedzenie, uhy) dało się zrobić tylko z tabel potworów:
telemetria nie zapisuje, ile golda zebrano, a rotuje się po 4 dniach, więc nie nadaje się do trenowania
modeli i liczenia opłacalności spotów. Potrzebny trwały, prosty dziennik ekonomii.

## Decyzje Karola (17.10)
1. Telemetria rotuje się => dane ekonomii idą do **osobnego pliku, który się nie rotuje i nie jest sprzątany**.
2. Zakres: **ile golda looctimy, ile uhów robimy**, plus exp, zabicia, jedzenie (to samo „itd.” co do porównania spotów).
3. „Cenny przedmiot” = **NPC płaci >= 100 gp**. Bot takich rzeczy **nie zbiera** (zajmują cap, trzeba wracać do miasta),
   więc zapisujemy tylko, że wypadły i ile są warte. Nic z moby na obecnych spotach nie leci — to ma być wykrywacz.
4. Wdrożenie: kod i testy w osobnym worktree, bez ruszania działającego bota.

## Zakres (co się zmienia)
- Nowy plik `logi/ekonomia-RRRRMMDD.jsonl` (JSONL, dopisywanie, **bez rotacji i bez `sprzatnij_stare`**).
  Pisze go ten sam proces i ta sama blokada pisarza co telemetria, z tymi samymi bezpiecznikami
  (`RETRONIC_TELEMETRIA=1`, brak `RETRONIC_TESTY`, tylko `mozg.py`, atrapa „Ja” nie pisze).
- Nowy moduł `ekonomia.py` (stdlib): ceny NPC z `dane_tibia/przedmioty.json` (`cena_sprzedaz_do_npc`),
  `cenne(nazwy)`, regexy linii lootu i raport CLI `python3 -I ekonomia.py [--katalog logi] [--dni N]`.
- `telemetria.py`: kopiuje do dziennika wybrane zdarzenia i składa zdarzenie `lup` z linii logu.
- `loot.py`: **tylko dodatkowa linia logu** `loot: cenne zostały X (cena)` — zero zmiany zachowania zbierania.
- Bez zmian: decyzje bota, lista `do_zebrania.txt`, ruch, UH, leczenie.

## Rekordy (wspólne pola: `t` epoch, `typ`, `sesja`, `pid`, `src`; spot wynika z `poz` w `tik`, bot nie zna nazwy trasy w telemetrii)
| typ | pola |
|---|---|
| `start` | postać, wersja dziennika (`v`:1) |
| `tik` (co 60 s, z próbki) | exp, mana, max_mana, hp, poz, stan bota, `gold_razem` i `uh_razem` od startu procesu — mianownik czasu aktywnego |
| `zabicie` | n (potwór), walka_s |
| `exp` | n, exp, zab (z `exp_zabicie`) |
| `lup` | n (ostatni zabity), `zrodlo` (`zwloki` / `walka`), `gold` (int albo `null` = ilość nieznana), `zebrano` {nazwa: sztuk}, `jedzenie` {nazwa: sztuk}, `cenne` [{n, ile, cena}], `wynik` |
| `uh` | wynik, rzuty, czas_s, powod |
| `jedzenie` | rodzaj (`walka`/`mana`) |

`lup` składa się z linii `loot: zebrano gold coin +N` i `loot w walce: zebrano …`, wysyłany przy
`Loot: <status>` (zwłoki) albo `loot w walce: koniec` (walka). Przypisanie do potwora = ostatnie zabicie
w ciągu 30 s (`n_pewne`:false, gdy starsze/brak). `gold:null` gdy ilość nieznana (plan z obrazka), nie 0. Zwłoki otwarte w walce zamyka znacznik `loot w walce: koniec`
(nowa linia logu w `loot.py`). Lup przerwany w walce bez znacznika dolicza się do następnego rekordu (znane ograniczenie).

## Kryteria akceptacji (każde z dowodem)
1. Testy jednostkowe: linie lootu => `lup` z poprawnym goldem, cenne (>=100 gp) wykryte także gdy niezebrane,
   `gold:null` gdy „ilość nieznana”, brak zapisu w trybie testowym i dla atrapy „Ja”.
2. Dziennik nie rotuje się i nie jest kasowany: test z `max_bajtow` małym i `sprzatnij_stare`.
3. Raport CLI na danych testowych: gold/h, uh/h, exp/h, zabicia/h per potwór i per sesja.
4. `git diff --check`, istniejące testy bota bez regresji (59/59 itd. jak w `STAN.md`), checker w osobnym kontekście (NIE ZROBIONY — czeka przed wdrożeniem).
5. Próba na żywo dopiero po wdrożeniu, jednym wywołaniem (reguła „test na żywo = jedno wywołanie”).

## Poza zakresem / otwarte
- Archiwizacja dziennika do `dane_ai/ekonomia/<źródło>/*.jsonl.gz` (jak telemetria) — osobna decyzja.
- Zbieranie cennych przedmiotów — Karol: na razie nie opłaca się (cap, powrót do miasta).
- Liczenie golda z różnicy stosu w plecaku jako druga, niezależna miara — jeśli `gold:null` będzie częste.
- Ceny: tylko NPC 7.4; rynek/trade (`ceny_trade.jsonl`) nie wchodzi.

## Wynik weryfikacji (17.10)
- `testy/test_ekonomia.py` 27/27; `test_telemetria`, `test_loot_w_walce`, `test_loot_klasyfikacja`, `test_loot_otwieranie`,
  `test_loot_runy`, `test_loot_glowny_plecak`, `test_analityk_poscigu` zielone; `test_loot_zbierz` i `test_loot_jedzenie`
  kończą się kodem 2 (POMINIĘTO: brak zrzutów w `testy/dane/`) tak samo na bazie `ruch-r1-1014`.
- Regexy sprawdzone na prawdziwych logach bota (`logi/mozg-stdout-1015…1017*.log`): gold parsuje się bez luk
  (0 lupów z nieznaną ilością w 15 sesjach). Z tego odtworzono historyczne gold/kill i gold/h (patrz raport w rozmowie 17.10).
- Niewdrożone: brak restartu bota, `loot.py`/`telemetria.py` w działającym checkoutcie bez zmian.
