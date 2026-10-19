# SPEC: Haiku ratuje bota, gdy ten zachowuje się „jak bot” (kręci się, stoi, zgubił trasę) - 19.10 — F1 ZAIMPLEMENTOWANE (cień, branch feat/ratunek-haiku), czeka na bramkę F1 -> F2

Cel: w każdej sytuacji, w której bot zaczyna robić coś, po czym od razu widać, że to bot (chodzi w kółko, stoi bez sensu,
klika bez skutku, zgubił trasę lub piętro), zanim się podda albo będzie to powtarzał, pyta Haiku o jeden ruch z zamkniętej
listy, wykonuje go, sprawdza skutek i wraca do zwykłej pracy. Karol 19.10: „na takie sytuacje powinien być haiku”,
„dodaj taki case”, zakres Q1: „w każdej sytuacji kiedy bot zaczyna coś odpierdalać, chodzi w kółko, zawsze kiedy dzieje się
coś, co sprawia, że od razu można stwierdzić, że to bot”.

## Decyzje Karola (19.10)

| Pytanie | Decyzja |
|---|---|
| Q1 wyzwalacz | **Każde zachowanie zdradzające bota** (sygnały S1-S7 niżej), nie tylko dojście. Wszystkie tryby pracy: dojście, główna trasa/patrol, wyprawa, serwis. |
| Q2 lista ruchów | „Nie wiem” -> domyślnie agent: **zamknięta lista** (bezpieczniej). Do ponownej oceny po QA na żywo. |
| Q3 limity | **Tak**: 6 ruchów i 180 s na zdarzenie, do 20 wywołań Haiku na godzinę na instancję. |
| Q4 tryb `skrypt` | **Tak**: ratunek działa także w `skrypt` (tryb codzienny). |
| Q5 AI OFF | **Tak**: przycisk pełnego AI OFF (`SPEC_ui_reczne_ai_1017.md`) wyłącza też ratunek. |
| Q6 uczenie | **Tak**: udane przejście pięter dopisywane automatycznie do danych przejść (z wpisem w logu ratunku). |

## Przypadek R1 (zmierzony 19.10, Mastafian, dojście na gobliny Edron) — test akceptacyjny

- Start ręczny 20:22:54: `mozg.py --tryb skrypt --trasa gobliny_edron_z8_petla --dojscie gobliny_edron_z_depo` z (33166,31825,z8).
- Kratka z8->z9, z9->z10->z11 i liny z11->z7 przeszły (1.-2. próba). Na z7 przy otworze do jaskini 20:25:06 walka z goblinami
  („Trasa wstrzymana: Goblin 4 pól od nas”), ostatni log trasy `[IDZ] punkt 99/121`.
- 20:25:20 postać na **z6 (33106,31849)**, cel dojścia (33106,31849,**z8**), zejście do jaskini to otwór (33107,31847,z7)
  wchodzony z (33107,31848,z7). Log: „stoję na z6, a punkt przed 110 jest na z7 … szukam punktu trasy na tym piętrze” ->
  „Przejście pięter NIEUDANE (wyczerpane pola przejścia)”. Próby 2-5 dojścia: trasa 1 pkt, „Okrążenie 1 gotowe”, „koniec trasy
  bez osiągnięcia celu” (5 prób w 25 s).
- 20:25:46 `mozg.py` kończy: „Dojście nieukończone … postać jest daleko od trasy, nie zaczynam głównej trasy” + powiadomienie.
- Zrzut: postać na skale obok drabiny, niżej schody, gobliny na trawie (z7). HP 250/250, mana 425/425, nikt nie atakuje.
- Jak weszła na z6 — **NIEUSTALONE** (brak wpisu przejścia pięter w logu; hipotezy: wejście na schody w walce, klik w goblina
  trafił w drabinę). Karol: „pewnie przez przypadek”.
- Dowody: `dane_tibia/repro/ratunek_1019/mastafian_z6_po_walce.png`, `dane_tibia/repro/ratunek_1019/mozg-1019-2022-wycinek.log`.

Oczekiwane po wdrożeniu: zamiast końca o 20:25:46 ratunek prowadzi postać z z6 na z7 (schody/drabina), dojście ponawia się
od najbliższego punktu na z7, otwór (33107,31847) -> z8, bot zaczyna `gobliny_edron_z8_petla`.

Inne przypadki do zestawu testów (z wcześniejszych logów, do odtworzenia w F1): serwis 19.10 20:12 — 6 nieudanych kroków „Right”
z rzędu na z6 w Edronie, pozycja cofa się w lewo (krążenie, serwis przerwał marsz); 15.10 20:29 — 6+ min oscylacji wyprawy bez
alarmu (`wypad.py` ~711); 54 zawieszki D3 z 70 h telemetrii (`SPEC_model_steruje_gra_1016.md`).

## Sygnały „to wygląda na bota” (Q1) — wspólny detektor

Każdy sygnał liczony z tego, co bot już ma w każdym obiegu (pozycja, stan, exp, wynik kroku/kliku); zero dodatkowych RPC.
Progi to pokrętła; wartości startowe poniżej, strojone po pomiarze w cieniu (F1).

| Sygnał | Definicja (start) | Gdzie dziś jest podobny licznik |
|---|---|---|
| S1 porażka trasy | dojście / wyprawa / serwis kończy się porażką (zamiast od razu STOP i „potrzebny człowiek”) | `mozg.main` ~3909, `wypad.py`, `serwis.py` SerwisBlad |
| S2 złe piętro | postać na piętrze, którego bieżąca trasa nie ma, > `RATUNEK_PIETRO_S` = 10 s poza walką | brak (R1) |
| S3 stoi | zawieszka D3: promień 2 pól >= `RATUNEK_STOI_S` = 30 s poza walką, exp bez zmian | `d3_zawieszka.py` (cień) |
| S4 kręci się | to samo pole odwiedzone >= 4 razy w 60 s albo pętla A-B-A >= 3 razy, bez walki i bez zabicia | `serwis.py` MAKS_WIZYT_POLA, cavebot POSCIG_OSCYLACJA |
| S5 kroki bez skutku | >= 6 nieudanych kroków z rzędu („krok … nie ruszył”) | `serwis.py` MAKS_ZLYCH_Z_RZEDU, debug cavebota |
| S6 klik bez skutku | >= 5 kliknięć w ten sam cel/pole bez efektu (atak, use, loot) | „5 klików bez efektu” w cavebocie |
| S7 pusta pętla trasy | >= 3 „Okrążenie gotowe” w 60 s bez ruchu > 2 pola (R1: trasa 1 pkt) | `mozg.py` wzorzec „Okrążenie (\d+) gotowe” |

Stany zamierzone (PRZERWA, PAUZA, PAUZA_PK, GRACZ — jak w D3), walka, ucieczka, leczenie, STOP i alarm GM nie są sygnałem.

## Zachowanie

1. **Wykrycie** (S1-S7) -> bot przerywa bieżącą czynność (nie powtarza jej), staje w miejscu i woła ratunek.
2. **Kontekst dla Haiku:** zrzut gry, pozycja (x,y,z), który sygnał i jego liczby, cel (najbliższy punkt trasy na docelowym
   piętrze), 5 najbliższych punktów trasy, znane przejścia pięter w promieniu 10 pól (`pietra_start.json`, `dziury_nauczone.json`,
   przejścia z map), ostatnie 10 ruchów bota, HP/mana, stwory w widoku. Bez czatu i nicków innych graczy w promptcie.
   Wywołanie jak dziś: `claude -p --model haiku` bez narzędzi (`mozg.py` ~1808), limit czasu.
3. **Odpowiedź = jeden ruch z zamkniętej listy** (Q2), JSON walidowany: `krok <N|S|E|W|NE|NW|SE|SW>`, `uzyj_pola <dx,dy>`
   (Ctrl+klik: drabina/schody/otwór), `lina <dx,dy>`, `idz_do <x,y>` (w widoku, to samo piętro), `czekaj <s>` (<= 10),
   `czlowiek`. Odpowiedź spoza listy, pole poza widokiem albo błąd wywołania = `czlowiek`.
4. **Wykonanie i kontrola:** ruch istniejącym kodem (`pietra.py`, kroki cavebota); po 2 s odczyt pozycji. Postęp (inne piętro
   zgodne z celem, wejście na trasę, wyjście z obszaru sygnału) -> bot wraca do przerwanej czynności od najbliższego punktu.
   Brak postępu -> kolejne pytanie z informacją, co nie zadziałało.
5. **Limity** (Q3): 6 ruchów i 180 s na zdarzenie, 20 wywołań Haiku na godzinę na instancję. Po limicie: stare zachowanie
   (log, powiadomienie, STOP tam, gdzie był STOP). Walka, ucieczka przy niskim HP, PK, STOP i AI OFF (Q5) przerywają ratunek.
6. **Zapis:** każde zdarzenie do `logi/ratunek-<data>.jsonl` (sygnał, wejście, odpowiedź, ruch, pozycja przed/po, wynik).
   Udane przejście pięter (Q6) dopisywane automatycznie do danych przejść (z wpisem „źródło: ratunek” do przeglądu).
7. **Pokrętło** `RATUNEK_HAIKU`: 0 wyłączone, 1 cień (detektor i log „wołałbym ratunek”, bez Haiku i bez ruchów), 2 działa.
   Niezależne od `--tryb`, także `skrypt` (Q4). Domyślnie 0.

## Fazy (bramki)

- **F1 detektor w cieniu** (`RATUNEK_HAIKU=1`): sygnały S1-S7 + log. Testy: R1 na atrapie (z6, cel z8, otwór z7) daje S2/S7;
  serwis 20:12 daje S5/S4; walka i stany zamierzone nie dają sygnału. Pomiar na telemetrii z 3 dni: ile wywołań na godzinę
  dałby detektor (musi się mieścić w 20/h; inaczej strojenie progów przed F2). Bramka: wynik pomiaru do Karola.
- **F2 ratunek** (`RATUNEK_HAIKU=2`): prompt, walidacja odpowiedzi, wykonanie ruchu, kontrola postępu, limity, AI OFF, zapis przejść.
  Testy: odpowiedź spoza listy -> `czlowiek`; limit ruchów i wywołań; walka/STOP przerywa; udane przejście trafia do danych.
- **QA na żywo:** jedno wywołanie (zasada testów na żywo), sytuacja jak R1; ustawienia przywrócone po próbie.

## Stan F1 (19.10, branch `feat/ratunek-haiku`, worktree `pomocnik-ratunek`, baza 9ea7d9b)

- Kod: `ratunek.py` (Detektor, jeden na proces, `zglos`), haki w `cavebot.py` (tick po D3, „krok … nie ruszył”, „klików bez efektu”,
  „Okrążenie gotowe”), `mozg.py` (porażka dojścia -> S1), `wypad.py` (`_awaria` -> S1), `serwis.py` (porażka -> S1, pokrętło z
  `na_zywo.json` instancji). Pokrętła `RATUNEK_*` w `pokretla.py` (RATUNEK_HAIKU 0-1, analityk nie może podnieść).
- Odstępstwo od tabeli: serwis w F1 daje tylko **S1**. Jego własne bezpieczniki (6 nieudanych kroków, 4. wejście na pole)
  kończą serwis porażką, więc S4/S5 serwisu dochodzą jako S1 z powodem. Krok S5 w cavebocie liczy każdy nieudany klawisz
  (jak linia logu), nie krok.
- JEDZENIE i ML dopisane do stanów zamierzonych (przegląd 19.10: krótkie własne czynności bota, nie postój).
- Testy `testy/test_ratunek.py` 51/51, kontrola mutacyjna (12 mutacji, każda czerwona); pełny zestaw jak baza.
- Pomiar offline `narzedzia/ratunek_pomiar.py` (telemetria 17-19.10, główna + test): **33,2 h pracy, 110 sygnałów = 3,3/h**
  (S3 stoi 68, S4 kręci się 39, S1 3) + S5 z logów stdout 5; **szczyt 14 w godzinie** (limit 20). Najgęstsza sesja: 17.10
  gobliny Edron, 26 sygnałów w 3,2 h. Pomiar NIE liczy S2 (telemetria nie zapisuje trasy) i zaniża S4 (próbka co 1 s).
  Pierwsza wersja S4 liczyła oscylacje w całym oknie (36 x S4 w jednej sesji) — poprawione na lokalny ogon ruchu.
- Niezależny przegląd: CHANGES-REQUIRED (S1 z wyprawy/serwisu wywracał się na `opis=`, mieszane zegary monotonic/epoch,
  testy hooków przez grep) — wszystko poprawione, testy na zachowanie dodane.

## Poza zakresem

Sterowanie walką i wyborem celu przez Haiku, pisanie na czacie, zakupy w mieście, trenowanie modeli na zapisach ratunku.

## Niewiadome

- Ile realnie trwa wywołanie Haiku ze zrzutem w tej maszynie (stanie w czasie pytania też wygląda na bota) — mierzone w F2.
- Czy progi S3-S7 nie łapią normalnej pracy (np. patrol wraca na te same miejsca) — mierzone w F1.
