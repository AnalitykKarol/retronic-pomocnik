# SPEC: Haiku ratuje postać, która zgubiła trasę (np. złe piętro) - 19.10 — DRAFT (czeka na Q1-Q6, Karol)

Cel: gdy bot się poddaje, bo postać stoi poza trasą (inne piętro, miejsce bez drogi), zanim zawoła człowieka pyta Haiku
o jeden ruch z zamkniętej listy, wykonuje go, sprawdza skutek i wraca do zwykłej trasy. Karol 19.10: „na takie sytuacje
powinien być haiku”, „dodaj taki case”.

## Przypadek R1 (zmierzony 19.10, Mastafian, dojście na gobliny Edron) — test akceptacyjny

- Start ręczny 20:22:54: `mozg.py --tryb skrypt --trasa gobliny_edron_z8_petla --dojscie gobliny_edron_z_depo` z (33166,31825,z8).
- Kratka z8->z9, z9->z10->z11 i liny z11->z7 przeszły (1.-2. próba). Na z7 przy otworze do jaskini 20:25:06 walka z goblinami
  („Trasa wstrzymana: Goblin 4 pól od nas”), ostatni log trasy `[IDZ] punkt 99/121`.
- 20:25:20 postać na **z6 (33106,31849)**, cel dojścia (33106,31849,**z8**), zejście do jaskini to otwór (33107,31847,z7)
  wchodzony z (33107,31848,z7). Log: „stoję na z6, a punkt przed 110 jest na z7 … szukam punktu trasy na tym piętrze” ->
  „Przejście pięter NIEUDANE (wyczerpane pola przejścia)”. Próby 2-5 dojścia: trasa 1 pkt, „koniec trasy bez osiągnięcia celu”.
- 20:25:46 `mozg.py` kończy: „Dojście nieukończone … postać jest daleko od trasy, nie zaczynam głównej trasy” + powiadomienie.
- Zrzut: postać na skale obok drabiny, niżej schody, gobliny na trawie (z7). HP 250/250, mana 425/425, nikt nie atakuje.
- Jak weszła na z6 — **NIEUSTALONE** (brak wpisu przejścia pięter w logu; hipotezy: wejście na schody w walce, klik w goblina
  trafił w drabinę). Karol: „pewnie przez przypadek”.
- Dowody: `dane_tibia/repro/ratunek_1019/mastafian_z6_po_walce.png`, `dane_tibia/repro/ratunek_1019/mozg-1019-2022-wycinek.log`.

Oczekiwane po wdrożeniu: zamiast końca o 20:25:46 ratunek prowadzi postać z z6 na z7 (schody/drabina), dojście ponawia się
od najbliższego punktu na z7, otwór (33107,31847) -> z8, bot zaczyna `gobliny_edron_z8_petla`.

## Stan dzisiaj (kod 19.10)

- `mozg.przejdz_dojscie` (~3776): `DOJSCIE_PROBY` prób od `dojscie_od_pozycji`; przy innym piętrze bierze najbliższy punkt na
  piętrze postaci, a gdy piętra nie ma w trasie, wybiera punkt najbliższy Manhattanem z dowolnego piętra (tu: ostatni, 1 pkt).
- `main` (~3909): porażka dojścia + `blisko_trasy` False -> log, powiadomienie „potrzebny człowiek”, koniec procesu.
- Model: `claude -p --model haiku` bez narzędzi (`mozg.py` ~1808, zrzut przez `grim`), dziś tylko w trybach doradca/hybryda/ai
  i dopiero w pętli głównej trasy. Tryb `skrypt` (domyślny w `uruchom.sh`) nie pyta modelu wcale.
- Decyzja 16.10 („Haiku nie jest nauczycielem”) dotyczy etykiet do treningu; tu Haiku jest awaryjnym wykonawcą, nie źródłem prawdy.

## Zachowanie (propozycja)

1. **Wyzwalacz** (Q1): `przejdz_dojscie` zwraca False i postać nie jest przy trasie, ALBO postać stoi na piętrze, którego trasa
   (dojścia/główna) nie zawiera, dłużej niż `RATUNEK_PO_S` (domyślnie 10 s) poza walką.
2. **Kontekst dla Haiku:** zrzut gry, pozycja (x,y,z), cel (najbliższy punkt trasy na docelowym piętrze), 5 najbliższych punktów
   trasy, znane przejścia pięter w promieniu 10 pól (`pietra_start.json`, `dziury_nauczone.json`, przejścia z map), HP/mana,
   stwory w widoku. Bez czatu i nicków innych graczy w promptcie.
3. **Odpowiedź = jeden ruch z zamkniętej listy** (Q2), JSON walidowany: `krok <N|S|E|W|NE|NW|SE|SW>`, `uzyj_pola <dx,dy>`
   (Ctrl+klik: drabina/schody/otwór), `lina <dx,dy>`, `idz_do <x,y>` (w widoku, to samo piętro), `czekaj`, `czlowiek`.
   Odpowiedź spoza listy albo pole poza widokiem = `czlowiek`.
4. **Wykonanie i kontrola:** bot wykonuje ruch istniejącym kodem (`pietra.py`, kroki cavebota), po 2 s czyta pozycję. Zmiana
   piętra na docelowe albo wejście na trasę -> ponów dojście/trasę od najbliższego punktu. Brak postępu -> kolejne pytanie z
   informacją, co nie zadziałało.
5. **Limity** (Q3): do `RATUNEK_MAX_RUCHOW` (domyślnie 6) ruchów i `RATUNEK_MAX_S` (180 s) na zdarzenie; potem stary koniec
   (log, powiadomienie, STOP). Walka, ucieczka przy niskim HP, PK i STOP mają pierwszeństwo i przerywają ratunek.
6. **Zapis:** każde zdarzenie do `logi/ratunek-<data>.jsonl` (wejście, odpowiedź, ruch, pozycja przed/po, wynik). Udane
   przejście pięter (Q6) dopisywane do danych przejść, żeby następnym razem skrypt poradził sobie sam.
7. **Pokrętło** `RATUNEK_HAIKU` (0/1), domyślnie 0; działa niezależnie od `--tryb` (także w `skrypt`) (Q4, Q5).

## Pytania otwarte (decyzja Karola)

- **Q1 Zakres wyzwalacza:** tylko dojście na spot (przypadek R1), czy też główna trasa/patrol, wyprawa do depo i serwis w mieście?
  Rekomendacja: dojście + wyprawa (ta sama klasa: trasa wielopiętrowa, porażka kończy proces); główna trasa w F2.
- **Q2 Lista ruchów:** czy wystarczy powyższa? Czy Haiku może kliknąć w dowolne pole w widoku (szerzej, ryzykowniej)?
- **Q3 Limity:** 6 ruchów / 180 s / ile wywołań Haiku na godzinę na instancję (proponuję 20)?
- **Q4 Tryb `skrypt`:** ratunek ma działać także w `skrypt` (dziś „bez modelu”), czy tylko w hybrydzie? Rekomendacja: także
  w `skrypt`, bo ten tryb chodzi na co dzień, a wtedy R1 by się nie powtórzył.
- **Q5 Pełne AI OFF** (`SPEC_ui_reczne_ai_1017.md`): przycisk AI OFF wyłącza też ratunek? Rekomendacja: tak.
- **Q6 Uczenie:** udane przejście dopisujemy automatycznie do danych przejść, czy tylko do logu do przeglądu?

## Fazy

- F1: wyzwalacz w `przejdz_dojscie`/`main` + kontekst + walidacja odpowiedzi + wykonanie ruchu + log, za `RATUNEK_HAIKU=0`.
  Testy: R1 na atrapie (pozycja z6, cel z8, otwór z7) — czerwony bez zmiany; odpowiedź spoza listy -> `czlowiek`; limit ruchów;
  walka/STOP przerywa ratunek.
- F2: wyprawa, serwis, główna trasa (wg Q1).
- QA na żywo: jedno wywołanie (zasada testów na żywo), postać z R1 albo podobna sytuacja; ustawienia przywrócone po próbie.

## Poza zakresem

Sterowanie walką i wyborem celu przez Haiku, pisanie na czacie, zakupy w mieście, trenowanie modeli na zapisach ratunku.
