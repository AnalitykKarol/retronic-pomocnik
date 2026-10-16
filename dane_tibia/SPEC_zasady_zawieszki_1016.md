# SPEC: zasady reakcji na zawieszkę (D3) — SZKIC do poprawek Karola (16.10)

Cel: wprost opisać, co jest POPRAWNĄ reakcją bota na zawieszkę, z oczekiwanym rezultatem i testem, zanim powstanie symulator.
Prawda = dane z gry + mapa + reguły przejść pięter z `pietra.py`; Haiku nie jest nauczycielem (decyzja Karola 16.10).
Dowody: `SPEC_model_steruje_gra_1016.md` sekcja 7. Status: SZKIC, Karol poprawia (szczególnie sekcje 4 i 5).

## 1. Definicje (już w kodzie: `d3_zawieszka.py`)

Zawieszka = pozycja w promieniu 2 pól od kotwicy >= 30 s (D3_PROG_S), poza walką (< 30% czasu okna), exp bez zmian. Stany zamierzone (PRZERWA, PAUZA, PAUZA_PK, GRACZ) to nie zawieszka.
Obszar osiągalny = pola przechodnie połączone z pozycją (8 kierunków, to samo piętro, bez wejścia na pola zmiany piętra).

## 2. Model świata (do symulatora; reguły z `pietra.py`, zweryfikowane na żywo wg jego nagłówka)

- W dół (piętro a -> a+1): pole zmiany T na piętrze a ma flagę mapy 2 ("bez drogi": dziura/schody); lądowanie (T.x, T.y, a+1).
- W górę (piętro a -> a-1): pole R na piętrze a, nad którym (piętro a-1, to samo x,y) jest pole z flagą 2 (dziura); lądowanie (R.x, R.y+1, a-1). Drabina/lina/schody w górę.
- Wejście: strzałką na pole, awaryjnie Ctrl+klik (Use); próby i pola startowe w `trasy/pietra_start.json`, złe w `pietra_zle.json`.
- Pola do ominięcia: nauczone dziury (`trasy/dziury_nauczone.json`), ogień (pola ognia z `ogien.py`), ściany (flaga 4), nieznane (brak flagi 1).
- Czas: krok 0,6-0,9 s zależnie od prędkości pola (stała z cavebot.py, do skalibrowania z telemetrii `ruch_okno`/`pietra_krok`).

## 3. Zasady (reguła -> oczekiwany rezultat -> test)

| # | Reguła | Oczekiwany rezultat | Test na danych |
|---|---|---|---|
| Z1 | Zawieszka wykryta -> policz obszar osiągalny (BFS) | decyzja zależy od rozmiaru: zamknięty (< 60 pól, brak drogi do celu po tym piętrze) vs otwarty | 46/99 historycznych epizodów to zamknięte obszary |
| Z2 | Zamknięty obszar -> wyjście ma być PO GRAFIE PIĘTER do piętra celu (nie najbliższe pole z flagą 2 bez względu na kierunek) | postać opuszcza obszar w <= N kroków, ląduje na piętrze, z którego jest droga do celu | wyrocznia wskazuje znane wyjścia (drabina (32506,32270) z9, 15.10) |
| Z3 | Wyjście prowadzące w głąb do kolejnej kieszeni (dziura z8 -> kieszeń z9) wybieraj tylko, gdy z kieszeni jest znane wyjście w górę | brak pętli kieszeń-kieszeń | symulacja grafu pięter: zero cykli bez wyjścia |
| Z4 | Pole wyjścia zawodzi (brak zmiany piętra po próbach) -> oznacz je złym (`pietra_zle.json`), weź następne wyjście | max PIETRA_PORAZKI_STOP prób, potem alarm | zgodne z `pietra.py` |
| Z5 | Otwarty obszar, oscylacja (<= 3 różne pola w ostatnich 8 krokach) -> przełamanie (inny punkt trasy osiągalny A*, nie ten sam kierunek) | zmiana wzorca w <= 10 s | 8 epizodów z oscylacją |
| Z6 | Gracz/mob blokuje przejście -> czekaj 5-10 s (z losowym czasem), potem inny punkt | brak wiecznego czekania (limit prób) | do zebrania z D3_LOG na żywo |
| Z7 | Brak jakiegokolwiek wyjścia/drogi (dane mapy niepełne, nieznane granice) -> alarm (STOP + powiadomienie człowieka), nie zgadywanie | człowiek wie, gdzie i dlaczego | 18 epizodów kończyło się końcem sesji w zawieszce |
| Z8 | Ogień, ucieczka, leczenie, UH, pauza PK: zawsze kod, nigdy model (decyzja Karola 16.10) | model nie nadpisuje | test filtrów |

## 4. Pytania do Karola (zasady)

- Q-Z1 Próg zawieszki 30 s: dla ZAMKNIĘTEGO obszaru krócej (np. 15 s), bo wyjście jest 1-5 kroków? Czy zostawić 30 s?
- Q-Z2 Ile prób wyjścia przed alarmem (dziś PIETRA_PORAZKI_STOP)? Czy alarm ma zatrzymać bota, czy tylko powiadomić i próbować dalej po przerwie?
- Q-Z3 Czy w kieszeni bot może użyć liny z plecaka (w `pietra.py` jest), czy tylko drabiny/schodów?
- Q-Z4 Czy ma być losowość w wyborze między równorzędnymi wyjściami/punktami (żeby nie wyglądać schematycznie), i w jakim zakresie?
- Q-Z5 Czy 62 przejęcia Karola (`pomoc-karola.jsonl`) mam odtworzyć jako przypadki testowe symulatora?

## 5. Symulator (etap 1b, po akceptacji zasad)

Wejście: pozycja + piętro, mapa (`mapa.py`), nauczone dziury, ogień, cel (punkt trasy). Opcje D3: krok_skos, cofnij, inny_punkt, przejscie_pietra, czekaj, alarm.
Wyjście: czas (kroki x 0,6-0,9 s) do opuszczenia obszaru/dojścia do celu albo "brak wyjścia". Walidacja: 99 epizodów (przewidziany czas vs rzeczywisty), znane drabiny, 62 przejęcia Karola.
