# SPEC: model D3 - wyjście z utknięcia (15.10 wieczór) — ZATWIERDZONY 15.10 ~22:30 (decyzje niżej)

Decyzja Karola 15.10 ~21:50: "D3 tak, najpierw spec". Kontekst: `SPEC_model_lokalny_1015.md` (sekcja 4, D3) oraz
dzisiejsze straty: exp/h spadł z ~2,4 tys. (08-15) do 0-860 (18-21) wyłącznie przez nawigację (dziura przy spawnie, kieszeń
na z9, wyprawa bez drogi, widmo po relogu). Walka i wybór celu działały.

## 1. Fakty z danych (70 h telemetrii, 3 boty, 11-15.10) [POTW]

- Rekord `utkniecie` (755 szt., mediana 20 s) **nie nadaje się** na etykiety: 91% to stan WALKA (stoimy przy mobie = "utknięcie"),
  a prawdziwe dzisiejsze zawieszki (kieszeń, pokój na z8) w ogóle nie dawały tego rekordu.
- Prawdziwe zawieszki liczone z próbek (pozycja w promieniu 2 pól >= 45 s, < 30% czasu walki, exp bez zmian): **54 epizody,
  162 min** (IDZ 41, WYPAD 8, PRZERWA 3, UCIECZKA 1, PAUZA 1). Najdłuższe: 1127 s (32338,32200,7), 1099 s (32049,32156,10),
  716 s WYPAD (32496,32266,8), 427 s (32485,32297,9), 314 s (32508,32273,9).
- Ręczne przejęcia Karola (`pomoc-karola.jsonl`, 62 rekordy, 11-15.10) - etykiety o największej wadze (co zrobił człowiek).

## 2. Co model ma robić

Gdy kod wykryje zawieszkę (brak postępu >= D3_PROG_S, domyślnie 30 s, poza walką), kod liczy **opcje dopuszczalne** (bez ognia,
bez znanej dziury, HP ok), a model wybiera jedną:

| Opcja | Co robi kod | Cechy (przykład) |
|---|---|---|
| krok_skos | jeden krok po skosie w stronę celu | wolne pola wokół, kierunek do celu, mob na polu |
| cofnij | 2-3 kroki wstecz po ostatniej drodze | ile kroków wstecz, czy tam był postęp |
| inny_punkt | resync na najbliższy OSIĄGALNY (A*) punkt trasy/planu | długość A*, ile punktów osiągalnych |
| przejscie_pietra | najbliższe przejście (schody/drabina/lina) z grafu patrolu | odległość, pewność (pewny/niepewny), piętro docelowe |
| czekaj | 5-10 s (gracz/mob blokuje) | gracz/mob na drodze, czas od ostatniego ruchu |
| alarm | STOP + powiadomienie (ostatnia deska) | czas zawieszki, liczba prób |

Wyjście modelu: dla każdej opcji P(ruszymy w ciągu 20 s). Bez modelu albo poniżej progu pewności: dzisiejsza reguła.
Bezpieczeństwo jak w SPEC_model_lokalny: model nigdy nie decyduje o ogniu, ucieczce, leczeniu.

## 3. Etykiety (nauczyciel offline)

- Dla 54 epizodów historycznych + nowych: Haiku dostaje opis sytuacji (pozycja, mapa 15x11 wokół z flagami pól: ściana / wolne /
  ogień / schody / dziura, cel etapu, ostatnie 10 kroków, stan, gracze i moby) i wskazuje najlepszą opcję + krótkie uzasadnienie.
  Koszt: ~54-200 wywołań jednorazowo (nie 750 - patrz wyżej), w ramach subskrypcji.
- Przejęcia Karola z `pomoc-karola` nadpisują etykietę nauczyciela (waga x5).
- Od wdrożenia kroku A: każda zawieszka w grze zapisuje rekord `decyzja` D3 z opcjami i cechami + wynik (czy i kiedy ruszyliśmy).

## 4. Kroki (bramki)

1. **Krok A (bez zmiany zachowania):** detektor zawieszki z próbek (jak w sekcji 1) w cavebot + rekord `decyzja` D3 (opcje, cechy,
   wybrana przez regułę, wynik). Pokrętło D3_LOG=1. Testy.
2. **Krok B (offline):** zbiór 54 epizodów + etykiety Haiku/Karola, `model_lokalny/zbior.py` D3, trening, raport: czy model
   wskazuje opcję, która w danych faktycznie ruszyła postać, lepiej niż reguła.
3. **Krok C (tryb cienia):** model liczy wybór obok reguły i tylko loguje.
4. **Krok D (włączenie):** pokrętło MODEL_D3=1, próg pewności; miara: minuty zawieszek na godzinę gry (dziś ~2,3 min/h średnio,
   wieczorem 15.10 kilkadziesiąt), exp/h. Cofnięcie = pokrętło 0.

## 5. Pytania do Karola

- Q1 Próg zawieszki 30 s poza walką - OK? (krócej = więcej fałszywych, dłużej = większa strata)
- Q2 Nauczyciel: Haiku (subskrypcja, wolniej) - OK, czy Jev przez API?
- Q3 Zaczynamy od kroku A (samo logowanie) od razu po wgraniu dzisiejszych poprawek nawigacji?
- Q4 Czy mam też uruchamiać `obserwator_reczny` w trakcie gry, żeby Twoje przejęcia były etykietami (dziś 62 rekordy)?

## Decyzje Karola 15.10 ~22:30

- Q1 próg zawieszki 30 s poza walką; Q2 nauczyciel Haiku (przejęcia Karola nadpisują); Q3 krok A od razu;
  Q4 obserwator ręcznych przejęć startuje zawsze razem z botem.
