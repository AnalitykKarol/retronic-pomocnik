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
| P5 | PK R5: wykrycie śmierci → stan `MARTWY`, alarm, zero kliknięć/modelu; naprawa odczytu HP po respawnie | SPEC, bez kodu | `PK_SZYBKIE` | atrapa: HP 0 ⇒ `MARTWY` |
| P6 | PK R2: reakcja na PK bez wywołania modelu na ścieżce (model w tle, `pauza_bota`/`kontynuuj` zablokowane przy HP<50% / alarmie) | SPEC, bez kodu | `PK_SZYBKIE` | odtworzenie 15:52:08–33, pętla nie blokuje >0,3 s |
| P7 | PK R1: czaszka lokalnie (<200 ms) | SPEC, UNKNOWN kolory ikon | `PK_SZYBKIE` | zrzuty czaszek (do zebrania) |
| P8 | PK R3/R4: UH przy 30% + predykcja, szybsza sekwencja (Ctrl+klik), ucieczka nie zamienia się w walkę z orkiem | SPEC, decyzje Karola (sekcja 6 speca) | `PK_UH_HP`, `PK_UH_CTRL` | odtworzenie, atrapa UH |
| P9 | PK po zgonie: jawny przepływ „respawn → powrót”, zamiast przypadkowego PAUZA_PK; krótsza/dynamiczna karencja? | NOWE, do decyzji | do ustalenia | atrapa po zgonie |
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
