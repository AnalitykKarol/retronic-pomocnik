# SPEC: skan stworów częściej w walce, rzadziej w spokoju (21.10) — ZATWIERDZONA (Karol 21.10 „tak”: Q1–Q3); WDROŻONA 13:29 (rdzeń) / 13:30 (kolanoth), QA w toku

Źródło: Karol 21.10 ~13:15 „w walce więcej czytał, a poza mniej”; `dane_tibia/ruch/ANALIZA_skaner_wplyw_1021.md`.

## Stan dziś (kod)
- `rdzen.Pamiec.stwory_info(maks_wiek)`: wynik z cache, jeśli młodszy niż `maks_wiek`, inaczej `WIEK_STWORY`/`WIEK_PUSTO` = 0,5 s.
- Wątek w tle (`_obieg_skanera`, commit `1705fd9`) skanuje dopiero, gdy cache zbliża się do **stałego** 0,5 s — nie wie o walce.
- Bot (`cavebot.stwory()`): w walce/pościgu/loocie większość wywołań bez `maks_wiek` (= 0,5 s); wyjątki `stwory(0.0)` (2 miejsca), `0.3`, `POSCIG_PRZEGLAD_WIEK`, `PK_SKAN_WIEK`.
- Pomiar 21.10: szybki skan śr. 0,18–0,28 s (max 0,56 s) przy 6 grach; wiek danych przy decyzji do ~0,8 s.

## Zmiana
1. **Bot mówi, w jakim jest trybie**: w stanach WALKA, POŚCIG, loot w walce, ucieczka — domyślny wiek zapytań = `SKAN_WIEK_WALKA`;
   w IDZ/spokoju = `SKAN_WIEK_SPOKOJ` (`cavebot.stwory()` gdy `maks_wiek` nie podano). Jawne `stwory(0.0)` i PK bez zmian.
2. **Skaner w tle słucha zapytań**: planuje kolejny skan pod najmniejszy `maks_wiek` z zapytań z ostatnich ~2 s (zamiast stałego 0,5 s);
   po 2 s bez „walkowych” zapytań wraca do rytmu spokoju.
3. Pokrętła (`cavebot.py` + `pokretla.py` + `na_zywo.przyklad.json`): `SKAN_WIEK_WALKA` (0,1–0,5 s), `SKAN_WIEK_SPOKOJ` (0,5–1,5 s).
   **Domyślnie 0,5 / 0,5 = dziś bez zmian**; włączane per instancja w `na_zywo.json`.

## Ryzyko
- Serwer strażnika jest jednowątkowy: skan 0,25 s blokuje inne zapytania (pozycja, HP). W walce przy wieku 0,15 s skaner pracuje prawie bez przerwy
  → możliwe opóźnienia innych odczytów i więcej CPU (6 strażników już 56–98% CPU każdy). Dlatego pomiar przed rozszerzeniem.
- Realna świeżość ograniczona czasem skanu (~0,25 s), nie tylko wiekiem.

## Pomiar (QA)
Jedna instancja z `SKAN_WIEK_WALKA`=0,15, druga bez zmian, ta sama mapa, 1–2 h: ranne zgubione / zabite, loot ok, loot w walce ok,
`rdzen-skan.log` (skany/s, czas skanu), CPU strażnika, „wolny tick”, „nie ruszył”. Restart sesji gry instancji testowej (relog) — nowy `rdzen.py`.

## Pytania
- Q1: wartości startowe 0,15 s w walce / 1,0 s w spokoju? (rekomendacja: tak; spokój 1,0 zwraca CPU z pustych chwil)
- Q2: instancja testowa: kolanoth (stała mapa `rook_raty_z8`)? (rekomendacja: tak; porównanie z kutangenem na podobnej mapie)
- Q3: restart gry kolanotha po wdrożeniu (relog jednej postaci) — zgoda.

## Wdrożenie 21.10

- Przegląd: checker CHANGES-REQUIRED (rytm „ostatni wygrywa”, NaN, LOOT) → poprawione (najmniejszy rytm z 2 s, `rytm=min(rytm, maks_wiek)` przy jawnym
  `maks_wiek>0`, LOOT w `SKAN_STANY_WALKI`, NaN/inf ignorowane) → APPROVE. Pominięte świadomie: ponowne sprawdzenie świeżości po blokadzie (stare zachowanie).
- Testy: `testy/test_skan_rytm.py` 31/31 (na starym rdzeniu: błąd); `test_rdzen_stwory` 34/34, `test_rdzen_widmo` OK, `test_orbity_skan` 20/20, `test_cavebot` 478/481 (jak przed).
- `rdzen.py` podmieniony atomowo 13:29:06 (kopia `rdzen.py.bak-20261021-rytm`); 5 strażników: „przeładowano rdzen.py” 13:29:06, bez błędów.
- kolanoth: `SKAN_WIEK_WALKA`=0,15, `SKAN_WIEK_SPOKOJ`=1,0 w `instancje/kolanoth/na_zywo.json` (kopia `.bak-20261021-rytm`), bot 13:30:50
  (`raty`, `ostrozny,ml`; postać „Kolanosh” — `profil.json` ma błędnie „Kolanoth”, start z `RETRONIC_POSTAC=Kolanoth` padł 13:29).
- Pierwszy pomiar 13:31 (`logi/rdzen-skan.log`): kolanoth spokój 10–11 skanów/11 s, walka 33–35/10 s; kutangen (kontrola) 21–24/10 s stale.
  Czas skanu bez zmian 0,24–0,31 s. W walce z cache tylko 21–32 z 27–41 zapytań (reszta czeka na skan).
- Cofnięcie: kolanoth `SKAN_WIEK_*` = 0,5 (przeładowanie na żywo); rdzeń `cp rdzen.py.bak-20261021-rytm rdzen.py` (przeładuje się sam).
- QA (1–2 h): kolanoth vs kutangen — ranne zgubione/zabite, loot ok, loot w walce ok, „nie ruszył”, wolny tick, CPU strażnika.
