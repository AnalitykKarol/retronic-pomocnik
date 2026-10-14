# Analiza gry 13.10.2026 (Jointoramix, troll_cave)

Zakres: telemetria-20261013.jsonl (07:44 do 22:01, 14,3 h, 28969 probek), mozg-20261013-*.log, mozg-stdout-1013-*.log. Tylko odczyt. Bot nie był uruchamiany ani zatrzymywany.

Uwaga o źródłach: liczniki z telemetrii dla łupu (typ `loot`) nie zgadzają się z logami. Patrz punkt 1 i problem 3.

## 1. Loot

Logi (mozg-20261013-*.log, główne źródło):
- Obsłużone zwłoki zakończone sukcesem: `Loot: ok` 356 razy (w tym 108 wpisów "Loot w walce: zwłoki obsłużone (ok)").
- Porażki i wstrzymania:
  - `Loot: brak_okna` 79 (plus 56 "Loot w walce przerwany: brak_okna").
  - "Loot w walce przerwany": cel_daleko 31, zgon_celu 7, obce_okno 6, stykające 3, atak_false 3, brak_celu 2, na_zwłokach 2 (łącznie 110 przerwań, w tym 56 brak_okna).
  - Zwłoki bez okna wstrzymane do końca walki: 97 (porzucone po drugiej próbie: 8).
  - Zwłoki na innym piętrze pominięte: 9. Zwłoki na polu ognia odłożone: 14.
- Odłożone (żywy mob obok): ok. 340 komunikatów "Loot odłożony" (głównie Troll 1 pól) plus 35 wpisów "[LOOT] odłożone".
- Przerwane przez żywego potwora w trakcie zbierania: 30.
- Szacunek: ok. 460 zakończonych zbieraniem na ok. 1100 zwłok, czyli ok. 40 procent zwłok bywa odkładanych lub przerywanych.

Telemetria (`loot.wynik`, 1773 zdarzeń): ok 1233, zwłoki 200, brak_okna 199, "4" 136, daleko 2, stoję 1, brak_plecaka 1, pelny_plecak 1. Te liczby są zawyżone i błędne:
- "4" pochodzi z komunikatu "Loot: 4 pola puste" (loot.py / cavebot.py:5018), a "zwłoki" z "Loot: zwłoki ... bez okna". Regex telemetrii `^Loot: (\w+)` łapie te komunikaty.
- "ok" 1233 w telemetrii przy 356 w logach: regex łapie też inne wpisy zaczynające się od "Loot:".

Zebrane przedmioty (logi): gold coin 247 wpisów "zebrano" o łącznej sumie ok. 1268 gold (średnio ok. 5 na zwłoki). Meat: 3 wpisy "zebrano meat", plus jedzenie ze zwłok (meat) ok. 48+14 razy.

pelny_plecak: 1 zdarzenie (21:54:53). Brak_plecaka: 1 (21:52:16). Nie da się potwierdzić, że plecak miał wolne miejsce, bo w logach nie ma wpisu o stanie plecaka w tej chwili. Mechanizm (loot.py ~linia 603): `_cel_w_plecaku` zwraca None, gdy `len(zajete) >= pojemnosc` (zajęte sloty z pamięci) albo gdy nie ma wolnego slotu w zakresie `min(widoczne, pojemnosc)`. Jeśli pamięć plecaka jest nieaktualna albo część slotów jest schowana, bot uzna plecak za pełny mimo wolnego miejsca. Sam wpis z 07:58 pisze o plecaku "pełnym golda", więc gold zajmuje sloty (stosy po 100), co bywa prawdziwym pełnym plecakiem.

## 2. Walka

Zabicia (telemetria `zabicie`, 954 razem): Troll 625, Rat 279, Orc 50. Logi: "Cel Troll zabity" 566 (różnica ok. 10 procent). Rat: patrz problem 3 (dane wątpliwe, zero exp).
- Zabicia w ostatniej godzinie (21:02 do 22:01): Troll 67, Orc 7 (razem 74).

Exp (z pola `exp` w probkach):
- Przyrost w całym dniu: 13815 do 26549, czyli +12734 (ok. 890 exp/h średnio przy 14,3 h).
- Ostatnia godzina (21:02 do 22:01): +1555 exp, czyli 1555 exp/h.
- Ostatnie 30 min (21:32 do 22:01): +660 exp, czyli ok. 1320 exp/h.
- Przyrost po godzinach (start godziny): 08:00 +840, 09:00 +740, 10:00 +710, 11:00 +545, 12:00 +1105, 13:00 +1101, 14:00 +993, 15:00 +686, 16:00 +1035, 17:00 +140, 18:00 +1080, 19:00 +294, 20:00 +1570, 21:00 +1565, 22:00 +90 (niepełna).

Dobijanie (epizody celu z telemetrii, `epizod_celu`):
- Cały dzień, Troll: zabity 625, porzucony 1005, zgubiony 158. Skuteczność dobicia (zabity / wszystkie epizody Troll) = 35 procent.
- Ostatnia godzina, wszystkie cele: zabity 75, porzucony 93, zgubiony 13. Skuteczność 41 procent.
- Ostatnie 30 min: zabity 32, porzucony 57, zgubiony 9. Skuteczność 28 procent.
- Obserwator raportował 80 do 100 procent dobijania w oknach 5 min. Jego wskaźnik liczy tylko część epizodów (ten z trafieniem i przy progu 6 epizodów), więc nie odzwierciedla strat z porzuceń.
- Główny powód porzuceń: "odpuszczony za ścianą (brak drogi naokoło)" 944 razy. Pogoń za uciekającym bez skutku: 9 razy.

Czas w stanach (cały dzień, z probek): WALKA 71,2 procent (7,3 h), IDZ 21,6 procent (2,2 h), WYPAD 3,2 procent, LOOT 1,6 procent, PRZERWA 1,1 procent, PAUZA 0,5 procent, UH 0,3 procent.
Ostatnia godzina: WALKA 48,7 procent, IDZ 45,8 procent, LOOT 4,5 procent, UH 0,5 procent.

## 3. Straty czasu

Przerwy bez zmiany pozycji i exp (probki, >= 120 s): 25 przypadków, łącznie 10466 s (2,9 h, ok. 20 procent dnia). Z tego 9 przerw >= 300 s.

Najdłuższe:
- 19:16:31 do 20:08:35, 52 min, stan WYPAD (w praktyce None), HP 61. Po `wypad_koniec` z powodem "STOP" o 19:16:34 bot stał do 20:08, gdy ruszył z nową wartością pokrętła WYPRAWA_ZLOTO_MIN. Wygląda na ręczne zatrzymanie, nie błąd bota.
- 11:13:53, 18,8 min, WYPAD w depo (32367,32215,7). Wyprawa do depo trwała 579 s (`wyprawa_koniec`, wynik depo). Reszta to czas poza depo, do potwierdzenia.
- 10:00:00 do 10:14:28, 14,5 min, IDZ, poz (32488,32294,8). Log: punkt 4 trasy "nieosiągalny przez pola ognia". Równocześnie cel Troll id..7748 był klikany co ok. 10 s (`[ATAK] klik ... powód ramka_false`) przez ok. 10 min przy HP 100 procent i bez zmiany exp. Dwa razy padło "Cel Troll trwa za długo, ignoruję na 60 s" (10:05:52 i 10:08:53).
- 09:29:40 do 09:42, 13,4 min, IDZ, poz (32492,32290,8). W tym czasie w UH wystąpił `TimeoutExpired` (grim -t png), a plik logu mozg-20261013-0815.log kończy się 09:31, następny zaczyna się 09:42. Prawdopodobnie zawieszenie i restart; do potwierdzenia.
- 17:14 do 17:31, WYPAD po blanki: w depo "nie otworzyłem skrzyni depo", wyprawa zakończona bez zakupów (`depo_zloz` otwarte false). Wyprawa odłożona 17:09 z powodem "za mało złota (0)".
- 15:03 (WYPAD, 6 min) i 17:30 (WYPAD, 9 min): wyprawy do depo/sklepu.

Przejścia pięter (`pietra_start`): 530 razy (8 do 9: 259, 9 do 8: 237, 7 do 8: 21, 8 do 7: 13). Porażki: `wyczerpane pola przejścia` 42 (ok. 8 procent prób), `nie widzę łopaty` 1, łopata użyta 5 razy. Kroki: krok 293, R (Ctrl+klik) 176, klik po skosie 9. W probkach 576 zmian piętra. Ok. 530 przejść dziennie to ok. 37 na godzinę.

Spam OGIEN (logi "[OGIEN] pola"): 5006 linii w dniu (ok. 350 na godzinę, ok. 6 na minutę). Najgęściej 08:00 (534), 13:00 (463), 21:00 (470), 20:00 (440). Maksimum 22 linie w minucie (08:32, 16:46). Zwłoki na polu ognia odłożone 14 razy.

Watchdog bezczynności (20 s bez akcji): 59 zdarzeń.
Patrol wizyt: 248 (ok. 205 zakończonych "ok", 1 nieudana po zmianie celu).

## Trzy najważniejsze problemy z liczbami

1. Porzucone trolle za ścianą: 944 odpuszczenia "za ścianą (brak drogi naokoło)" i 1005 epizodów porzucenia Troll przy 625 zabiciach (skuteczność 35 procent). Każdy Troll to ok. 20 exp (exp_zabicie), więc potencjał to rzędu 18 tys. exp (górna granica, nie każdy porzucony miał pełne HP). W ostatniej godzinie: 93 porzucenia przy 75 zabiciach.
   Rekomendacja: przed wejściem w cel sprawdzać flagę `osiagalny` / `droga` z telemetrii `stwory` (już jest w probkach) i nie wybierać celu, który nie ma drogi, zamiast go atakować i odpuszczać.

2. Zawieszenia i długie przerwy: 25 przerw >= 120 s, łącznie 2,9 h (20 procent dnia). Najgroźniejsze to klik ataku bez postępu przez ok. 10 min (10:00 do 10:14, cel Troll klikany co 10 s, "ramka_false"), 13 min stanu bez zmiany (09:29 do 09:42, timeout grim w UH) i 52 min po STOP (19:16 do 20:08).
   Rekomendacja: strażnik celu, który po N sekundach (np. 20 s) bez zmiany HP celu i bez exp zmienia cel lub odpuszcza. Dodać timeout i ponowienie dla wywołania grim w UH, zamiast blokować pętlę.

3. Zaburzone telemetria i dane: 1651 zdarzeń `nowy_cel Rat` z pozycjami poza trasą (101,100 w 610 przypadkach; 32015,32142 w 347), zero wpisów "Nowy cel: Rat" w logach mozg, 279 "zabić" Rat z czasem walki 0,0 s i zero exp (exp_zabicie tylko Troll i Orc). Plus regex łupu, który zlicza "Loot: 4 pola puste" i "Loot: zwłoki" jako wyniki (1773 zdarzeń loot vs 356 realnych "Loot: ok").
   Rekomendacja: zawęzić RE_LOOT w telemetria.py do znanych wyników (ok, brak_okna, daleko, brak_plecaka, pelny_plecak, stoję, zwłoki), odfiltrować Rat z telemetrii (źródło do sprawdzenia), a przy pelny_plecak zapisać zajete/pojemnosc/widoczne, żeby sprawdzić fałszywie pełny plecak.

Dodatkowo: 42 porażki przejść pięter (8 procent) i 5006 linii OGIEN to koszt, ale rząd wielkości mniejszy niż przerwy.
