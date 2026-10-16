# SYMULATOR zawieszek: wyniki walidacji (16.10)

Wygenerowano `python3 narzedzia/symulator_zawieszek.py waliduj` (offline; czyta mapę, trasy, dane z `modele-test/dane/`, `logi/`; nic nie zapisuje).
Krok 0,6-0,9 s to stała z kodu (`cavebot.py`), nie pomiar. Świat: prawdziwa mapa + przejścia i łączniki z `trasy/miejsca_troll.json` + nauczone dziury; drzwi (32505,32270,z8) ZAMKNIĘTE (stan drzwi w historycznych epizodach = UNKNOWN, więc wariant konserwatywny).

Wejścia symulatora w odtworzeniu epizodów (nic ponad to, co jest w danych epizodu):
- **A** = pozycja + piętro + historia (`ostatnie_kroki`, 10 pozycji tuż przed epizodem). Bez celu i bez punktów trasy.
- **B** = A + wszystkie punkty z `trasy/*.json` na tym piętrze w promieniu 30 pól (która trasa była aktywna = UNKNOWN, więc suma wszystkich).
- **C** = B + cel-piętro "skąd przyszedłem" ([HIP]: ostatnia pozycja historii z innego piętra; intencji bota w danych nie ma).

## 1. Odtworzenie 107 epizodów zawieszek

- epizodów: 107; zasymulowanych: 107 (wszystkie mają pozycję i piętro).
- z rzeczywistym wynikiem (`ucieczka.json`/`przyczyny.json`): 99; bez: 8 (powód: zamierzone przerwy/pauzy PRZERWA/PAUZA wyłączone z analizy: 8/8).

### 1a. Wynik symulacji (ziarno 1) vs klasa referencyjna z przyczyny.json: zamknięte 46, otwarte 53

| wariant | zamknięte: wyszedl | zamknięte: brak_wyjscia | otwarte: wyszedl | otwarte: brak_wyjscia | otwarte: brak_danych |
|---|---|---|---|---|---|
| A | 42 | 4 | 49 | 0 | 4 |
| B | 42 | 4 | 53 | 0 | 0 |
| C | 42 | 4 | 53 | 0 | 0 |

Otwarte bez celu i bez punktów (A) są poza zakresem Z5: symulator nie wie dokąd iść, więc nie twierdzi, że wyjścia nie ma (wynik `brak_danych`, nie alarm). Z punktami trasy (B, C) wszystkie otwarte epizody kończą się wyjściem poza promień 2.

Zamknięte, w których symulator nie znajduje wyjścia: 4. Wszystkie leżą w kieszeni z7 przy (32338-32340, 32200-32202, z7). Flaga 2 mapy na (32340,32202,z7) nie ma ważnego lądowania (ani (x,y,z+1), ani (x,y+1,z-1) nie są przechodnie), więc to nie jest wyjście wg reguł `pietra.py`. Telemetria zgadza się z tym (sprawdzone ręcznie na próbkach wszystkich 4 epizodów z 14.10: cała trasa w x 32338-32340, y 32200-32202, wyłącznie z7, pole (32340,32202) odwiedzane wielokrotnie bez zmiany piętra; ucieczka.json liczy to jako 'skok_poza_obszar', bo jej BFS wyklucza pola z flagą 2). Czasy tych epizodów: 203 s, 491 s, 343 s, 1125 s (bot nie wyszedł do końca epizodu). Wniosek: symulator -> alarm Z7, rzeczywistość -> zawieszka bez wyjścia. Zgodne.

### 1b. Błąd czasu wyjścia (zamknięte obszary z rzeczywistym wyjściem w telemetrii)

Błąd = przewidziany - rzeczywisty, oba od początku zawieszki. Przewidziany = próg 15 s + czas symulacji; rzeczywisty = `po_s` z `ucieczka.json` (pierwsza próbka poza obszarem lub na innym piętrze). Epizody bez wyjścia w telemetrii (urwana seria) są cenzurowane i wyłączone.

| wariant | zbiór | n | mediana błędu | mediana modułu błędu | p90 modułu | min | max | sim wolniejszy niż rzecz. |
|---|---|---|---|---|---|---|---|---|
| A | wszystkie z wyjściem | 25 | -76.9 s | 76.9 s | 344.7 s | -620.9 s | 13.3 s | 6/25 |
| A | tylko zmiana piętra | 12 | -217.1 s | 217.1 s | 501.5 s | -620.9 s | -38.6 s | 0/12 |
| B | wszystkie z wyjściem | 25 | -76.9 s | 76.9 s | 344.7 s | -620.9 s | 13.3 s | 6/25 |
| B | tylko zmiana piętra | 12 | -217.1 s | 217.1 s | 501.5 s | -620.9 s | -38.6 s | 0/12 |
| C | wszystkie z wyjściem | 25 | -76.9 s | 76.9 s | 343.9 s | -620.9 s | 13.3 s | 6/25 |
| C | tylko zmiana piętra | 12 | -217.1 s | 217.1 s | 501.5 s | -620.9 s | -38.6 s | 0/12 |

[HIP] Symulator opisuje reakcję według Z1-Z8, a nie obecnego bota, więc to nie jest test trafności przewidywania czasu bota. Ujemny błąd = czas, który reguła mogłaby odzyskać; dodatni = przypadki, w których bot wyszedł szybciej (np. natychmiast po wejściu na drabinę) niż próg 15 s + ruch.

Przypadki szczegółowo (wariant A):

| pozycja | wyjście rzeczywiste | rzeczywisty s | przewidziany s | błąd s |
|---|---|---|---|---|
| [32496, 32267, 8] | pietro | 636.7 | 15.8 | -620.9 |
| [32485, 32297, 9] | pietro | 518.7 | 17.2 | -501.5 |
| [32508, 32273, 9] | pietro | 361.9 | 17.2 | -344.7 |
| [32508, 32273, 9] | pietro | 349.8 | 17.2 | -332.6 |
| [32484, 32284, 9] | pietro | 319.7 | 15.8 | -303.9 |
| [32496, 32267, 8] | pietro | 247.0 | 15.8 | -231.2 |
| [32501, 32271, 8] | pietro | 220.3 | 17.2 | -203.1 |
| [32506, 32270, 9] | skok_poza_obszar | 180.2 | 16.5 | -163.7 |
| [32474, 32271, 9] | skok_poza_obszar | 156.9 | 17.2 | -139.7 |
| [32475, 32272, 9] | skok_poza_obszar | 133.7 | 16.5 | -117.2 |
| [32508, 32273, 9] | skok_poza_obszar | 130.7 | 17.2 | -113.5 |
| [32474, 32274, 9] | pietro | 118.8 | 17.2 | -101.6 |
| [33129, 31810, 8] | pietro | 94.9 | 18.0 | -76.9 |
| [33128, 31810, 8] | pietro | 86.9 | 18.0 | -68.9 |
| [32485, 32276, 9] | pietro | 83.2 | 21.8 | -61.4 |
| [32496, 32267, 8] | pietro | 54.4 | 15.8 | -38.6 |
| [32358, 32210, 7] | skok_poza_obszar | 55.9 | 18.8 | -37.1 |
| [32504, 32270, 8] | skok_poza_obszar | 37.6 | 15.8 | -21.8 |
| [32497, 32268, 8] | skok_poza_obszar | 24.4 | 15.8 | -8.6 |
| [32496, 32266, 8] | skok_poza_obszar | 13.9 | 15.8 | 1.9 |
| [32360, 32209, 7] | skok_poza_obszar | 11.9 | 18.0 | 6.1 |
| [32360, 32209, 7] | skok_poza_obszar | 11.7 | 18.0 | 6.3 |
| [32496, 32266, 8] | skok_poza_obszar | 7.7 | 15.8 | 8.1 |
| [32506, 32270, 9] | skok_poza_obszar | 3.4 | 16.5 | 13.1 |
| [32506, 32270, 9] | skok_poza_obszar | 3.2 | 16.5 | 13.3 |

### 1c. Kierunek piętra: rzeczywiste wyjście ze zmianą piętra (12 epizodów) vs piętro lądowania symulatora

| wariant | zgodne piętro | niezgodne | symulator bez wyjścia |
|---|---|---|---|
| A | 5 | 7 | 0 |
| B | 5 | 7 | 0 |
| C | 7 | 5 | 0 |

Kieszeń z9 (32508,32273|32272) z rzeczywistym wyjściem w górę: 2 epizodów; wariant A schodzi dziurą na z10 w 2/2 (najtańsze wyjście, bez piętra celu, Z2 nieaktywne), wariant C (2/2 ma podpowiedź piętra) trafia w piętro rzeczywistego wyjścia w 2/2. Pozostałe niezgodności to epizody, w których rzeczywisty bot wybrał inne piętro niż najtańsze wyjście (jego cel = UNKNOWN). Wniosek: reguła Z2 działa tylko z piętrem celu; bot musi je przekazać, bez niego symulator nie wskaże znanej drabiny.

### 1d. Otwarte obszary: kiedy symulator by zareagował vs jak długo bot rzeczywiście stał

- otwartych z wyjściem w wariancie B: 53/53; przewidziana reakcja po (próg 30 s + czas): mediana 32.2 s
- rzeczywisty czas stania (`trwa_s`, epizod kończy się wyjściem poza promień 2, przerwą > 30 s albo zmianą piętra): mediana 75.9 s
- różnica (stał - reakcja symulatora): mediana 43.7 s, p90 198.9 s, reakcja symulatora wcześniejsza w 53/53
- [HIP] To nie jest błąd czasu: punkty trasy i cel są założone (B), a koniec epizodu nie musi być wyjściem wg reguły Z5.

## 2. Świat symulatora vs plansze 15x11 zapisane w epizodach

- porównanych pól: 17465, zgodnych: 17442 (99.87%); różnych: 23
- rodzaje różnic (epizod -> symulator): {('s', '#'): 10, ('.', '#'): 13}
- Wszystkie różnice leżą na polach z `trasy/dziury_nauczone.json` ((32498,32271,z8), (32508,32273,z8), (32482,32296,z8)): plansze powstały przed nauczeniem tych dziur, symulator traktuje je jak ścianę (zgodnie ze specyfikacją).
- Ograniczenie: plansze pochodzą z tej samej `mapa.py`, więc to test spójności (dziury, kodowanie), nie niezależna weryfikacja mapy względem gry.

## 3. Znane wyjścia: wyrocznia z flag mapy (oracle_wyjscie.json) vs symulator

- przypadków: 43; symulator kończy 'wyszedl': 39, bez wyjścia: 4
- ten sam punkt wejścia co wyrocznia (odległość <= 1 pole): 24/43
- wyjście przez drzwi (32505,32270,z8), wyrocznia go nie widzi (ściana w mapie): 5
- inne wyjście niż wyrocznia: 10; symulator nie widzi wyjścia wyroczni (flaga 2 bez ważnego lądowania): 4

| pozycja | wyrocznia: pole (kroki) | symulator: wynik, rodzaj, pole wejścia | kroki sym. | czas sym. s | rzeczywisty s | zgodność |
|---|---|---|---|---|---|---|
| [32475, 32272, 9] | [32475, 32273] (1) | wyszedl, lacznik, [32476, 32273] | 2 | 1.5 | 133.7 | to samo wyjście |
| [32474, 32271, 9] | [32473, 32272] (1) | wyszedl, lacznik, [32476, 32273] | 3 | 2.2 | 156.9 | inne wyjście |
| [32474, 32274, 9] | [32475, 32273] (1) | wyszedl, lacznik, [32476, 32273] | 3 | 2.2 | 118.8 | to samo wyjście |
| [32360, 32209, 7] | [32361, 32209] (1) | wyszedl, drabina, [32359, 32206] | 4 | 3.0 | 208.1 | inne wyjście |
| [32360, 32209, 7] | [32361, 32209] (1) | wyszedl, drabina, [32359, 32206] | 4 | 3.0 | 119.4 | inne wyjście |
| [32508, 32273, 9] | [32506, 32270] (3) | wyszedl, dziura, [32510, 32271] | 3 | 2.2 | 361.9 | inne wyjście |
| [32358, 32210, 7] | [32359, 32206] (4) | wyszedl, drabina, [32359, 32206] | 5 | 3.8 | 55.9 | to samo wyjście |
| [32508, 32273, 9] | [32506, 32270] (3) | wyszedl, dziura, [32510, 32271] | 3 | 2.2 | 349.8 | inne wyjście |
| [32049, 32154, 10] | [32050, 32155] (1) | wyszedl, drabina, [32050, 32155] | 1 | 0.8 | UNKNOWN | to samo wyjście |
| [32048, 32155, 10] | [32050, 32155] (2) | wyszedl, drabina, [32050, 32155] | 2 | 1.5 | UNKNOWN | to samo wyjście |
| [32048, 32155, 10] | [32050, 32155] (2) | wyszedl, drabina, [32050, 32155] | 2 | 1.5 | UNKNOWN | to samo wyjście |
| [32049, 32154, 10] | [32050, 32155] (1) | wyszedl, drabina, [32050, 32155] | 1 | 0.8 | UNKNOWN | to samo wyjście |
| [32048, 32154, 10] | [32050, 32155] (2) | wyszedl, drabina, [32050, 32155] | 2 | 1.5 | UNKNOWN | to samo wyjście |
| [32048, 32154, 10] | [32050, 32155] (2) | wyszedl, drabina, [32050, 32155] | 2 | 1.5 | UNKNOWN | to samo wyjście |
| [32048, 32154, 10] | [32050, 32155] (2) | wyszedl, drabina, [32050, 32155] | 2 | 1.5 | UNKNOWN | to samo wyjście |
| [32338, 32200, 7] | [32340, 32202] (2) | brak_wyjscia, -, - | 0 | 0.0 | UNKNOWN | brak wyjścia w sym. |
| [32338, 32202, 7] | [32340, 32202] (2) | brak_wyjscia, -, - | 0 | 0.0 | UNKNOWN | brak wyjścia w sym. |
| [32340, 32202, 7] | [32340, 32197] (5) | brak_wyjscia, -, - | 0 | 0.0 | UNKNOWN | brak wyjścia w sym. |
| [32504, 32271, 8] | [32501, 32274] (3) | wyszedl, -, - | 2 | 1.5 | UNKNOWN | drzwi |
| [32504, 32271, 8] | [32501, 32274] (3) | wyszedl, -, - | 2 | 1.5 | UNKNOWN | drzwi |
| [32504, 32270, 8] | [32501, 32274] (4) | wyszedl, -, - | 1 | 0.8 | 37.6 | drzwi |
| [32485, 32297, 9] | [32483, 32299] (2) | wyszedl, lacznik, [32483, 32297] | 3 | 2.2 | 518.7 | inne wyjście |
| [32503, 32270, 8] | [32500, 32273] (4) | wyszedl, -, - | 2 | 1.5 | UNKNOWN | drzwi |
| [32049, 32156, 10] | [32050, 32155] (1) | wyszedl, drabina, [32050, 32155] | 1 | 0.8 | UNKNOWN | to samo wyjście |
| [32050, 32156, 10] | [32050, 32155] (1) | wyszedl, drabina, [32050, 32155] | 1 | 0.8 | UNKNOWN | to samo wyjście |
| [32338, 32202, 7] | [32340, 32202] (2) | brak_wyjscia, -, - | 0 | 0.0 | UNKNOWN | brak wyjścia w sym. |
| [33129, 31810, 8] | [33131, 31806] (4) | wyszedl, drabina, [33131, 31806] | 4 | 3.0 | 94.9 | to samo wyjście |
| [32508, 32272, 9] | [32506, 32270] (2) | wyszedl, dziura, [32510, 32271] | 2 | 1.5 | UNKNOWN | inne wyjście |
| [32506, 32270, 9] | [32506, 32269] (1) | wyszedl, drabina, [32506, 32269] | 2 | 1.5 | UNKNOWN | to samo wyjście |
| [32497, 32268, 8] | [32496, 32267] (1) | wyszedl, drabina, [32496, 32267] | 1 | 0.8 | UNKNOWN | to samo wyjście |
| [32496, 32267, 8] | [32496, 32268] (1) | wyszedl, drabina, [32496, 32267] | 1 | 0.8 | UNKNOWN | to samo wyjście |
| [32496, 32267, 8] | [32496, 32268] (1) | wyszedl, drabina, [32496, 32267] | 1 | 0.8 | 636.7 | to samo wyjście |
| [32496, 32267, 8] | [32496, 32268] (1) | wyszedl, drabina, [32496, 32267] | 1 | 0.8 | 247.0 | to samo wyjście |
| [32496, 32267, 8] | [32496, 32268] (1) | wyszedl, drabina, [32496, 32267] | 1 | 0.8 | 54.4 | to samo wyjście |
| [33128, 31810, 8] | [33131, 31806] (4) | wyszedl, drabina, [33131, 31806] | 4 | 3.0 | 86.9 | to samo wyjście |
| [32508, 32273, 9] | [32506, 32270] (3) | wyszedl, dziura, [32510, 32271] | 3 | 2.2 | UNKNOWN | inne wyjście |
| [32501, 32271, 8] | [32500, 32273] (2) | wyszedl, schody, [32498, 32270] | 3 | 2.2 | 220.3 | inne wyjście |
| [32506, 32270, 9] | [32506, 32269] (1) | wyszedl, drabina, [32506, 32269] | 2 | 1.5 | UNKNOWN | to samo wyjście |
| [32506, 32270, 9] | [32506, 32269] (1) | wyszedl, drabina, [32506, 32269] | 2 | 1.5 | 180.2 | to samo wyjście |
| [32496, 32266, 8] | [32496, 32267] (1) | wyszedl, drabina, [32496, 32267] | 1 | 0.8 | UNKNOWN | to samo wyjście |
| [32496, 32266, 8] | [32496, 32267] (1) | wyszedl, drabina, [32496, 32267] | 1 | 0.8 | 718.8 | to samo wyjście |
| [32508, 32273, 9] | [32506, 32270] (3) | wyszedl, dziura, [32510, 32271] | 3 | 2.2 | 172.9 | inne wyjście |
| [32507, 32270, 8] | [32505, 32268] (2) | wyszedl, -, - | 2 | 1.5 | UNKNOWN | drzwi |

Drabina (32506,32269|32270) z9: wpisów wyroczni z tym startem 3; symulator wychodzi drabiną w 3/3.

### 3b. Znane przypadki (komendy `symuluj` na świecie z repo)

| przypadek | wynik | kroki | czas s | koniec | zdarzenia |
|---|---|---|---|---|---|
| kieszeń z9, bez celu | wyszedl | 3 | 2.2 | [32510, 32271, 10] | przejscie:dziura |
| kieszeń z9, cel (32502,32270,z8) | wyszedl | 5 | 3.8 | [32506, 32270, 8] | przejscie:drabina, drzwi |
| na polu drabiny (32506,32270,z9), bez celu | wyszedl | 2 | 1.5 | [32506, 32270, 8] | przejscie:drabina, drzwi |
| pokój za drzwiami, drzwi ZAMKNIĘTE, cel (32478,32290,z8) | wyszedl | 2 | 1.5 | [32506, 32270, 8] | drzwi |
| pokój za drzwiami, drzwi OTWARTE, cel (32478,32290,z8) | wyszedl | 9 | 6.8 | [32498, 32270, 9] | przejscie:schody |

Wyjaśnienie "2 vs 8 kroków" (SPEC_model_steruje_gra_1016 sekcja 7): pokój (32507,32270,z8) ma drzwi (32505,32270). Przy ZAMKNIĘTYCH drzwiach najtańsze wyjście to podejście do (32506,32270) i użycie drzwi (2 kroki); naiwna wyrocznia widziała 2 kroki do flagi (32505,32268), której nie da się użyć. Przy OTWARTYCH drzwiach droga do schodów (32498,32270) ma 9 kroków (8 do pola przed schodami + wejście), co odpowiada 8 krokom policzonym przez bota. Symulator odtwarza obie liczby, a stan drzwi decyduje, która jest właściwa (stan drzwi w epizodach = UNKNOWN).

## 4. Przejęcia Karola jako przypadki testowe

- przypadków (bez trybu brak_bota; plik rośnie na żywo, 62 w chwili decyzji): 65; start zamknięty: 34, otwarty: 31
- ślad pozycji z telemetrii (próbki w czasie przejęcia): 49/65 (przy zatrzymanym bocie telemetrii nie ma: UNKNOWN trasa Karola)
- Karol opuścił obszar startu (zmiana piętra albo poza BFS): 6/65; UNKNOWN (obszar uciety limitem BFS, to samo piętro): 5
- zamknięte: symulacja 'wyszedl' w 33/34, inny wynik: [32356, 32208, 7]=brak_wyjscia
- otwarte (bez celu, punkty z tras = wariant B): symulacja 'wyszedl' w 31/31; cel Karola w otwartych = UNKNOWN, więc bez oceny zgodności

### 4a. Przejęcia, w których Karol faktycznie wyszedł z obszaru (jedyne porównywalne ze zdaniem symulatora)

| start | pozycja | klasa | Karol: koniec | symulator | sim koniec | ocena |
|---|---|---|---|---|---|---|
| 08:16:52 | [32481, 32279, 8] | otwarty | [32448, 32240, 7] | wyszedl drabina | [32472, 32290, 7] | otwarty: bez oceny |
| 08:23:50 | [32356, 32208, 7] | zamkniety | [32400, 32220, 7] | brak_wyjscia  | [32356, 32208, 7] | luka modelu: Karol wyszedł, symulator nie zna wyjścia (alarm Z7) |
| 08:41:33 | [32485, 32301, 9] | zamkniety | [32482, 32295, 8] | wyszedl lacznik | [32482, 32297, 8] | zgodne (to samo piętro, <= 3 pola) |
| 11:48:56 | [32507, 32270, 8] | zamkniety | [32505, 32270, 8] | wyszedl drzwi | [32506, 32270, 8] | zgodne (to samo piętro, <= 3 pola) |
| 14:41:15 | [32485, 32298, 9] | zamkniety | [32483, 32296, 8] | wyszedl lacznik | [32482, 32297, 8] | zgodne (to samo piętro, <= 3 pola) |
| 15:18:36 | [32499, 32269, 8] | zamkniety | [32507, 32270, 8] | wyszedl schody | [32498, 32270, 9] | rozbieżne (inne wyjście niż Karol) |

Zamknięte starty, w których Karol wyszedł: zgodne 3, rozbieżne 1, luka modelu 1.
Pozostałe przejęcia w zamkniętych obszarach (Karol został w obszarze) to krótkie korekty (mediana 2.8 s) w trybie bot_aktywny: nie dowód, że Karol rozwiązywał zawieszkę; zgodność z jego intencją = UNKNOWN bez jego opisu.

Najczęstsze startu w zamkniętych obszarach: [32499, 32269, 8] x7, [32485, 32297, 9] x6, [32498, 32269, 8] x3, [32499, 32268, 8] x2.

### 4b. Wszystkie przypadki

| start | poz | klasa | obszar | tryb | Karol s | Karol wyszedł | sim | sim s |
|---|---|---|---|---|---|---|---|---|
| 08:16:52 | [32481, 32279, 8] | otwarty | 119 | bot_zatrzymany | 177.1 | tak | wyszedl (B) | - |
| 08:19:54 | [32448, 32240, 7] | otwarty | 4000+ | bot_zatrzymany | 52.5 | UNKNOWN | wyszedl (B) | - |
| 08:21:43 | [32422, 32217, 7] | otwarty | 4000+ | bot_zatrzymany | 47.6 | UNKNOWN | wyszedl (B) | - |
| 08:23:50 | [32356, 32208, 7] | zamkniety | 9 | bot_zatrzymany | 114.1 | tak | brak_wyjscia | 0.0 |
| 08:36:30 | [32502, 32280, 9] | otwarty | 101 | bot_aktywny | 3.5 | nie | wyszedl (B) | - |
| 08:39:25 | [32499, 32280, 9] | otwarty | 101 | bot_aktywny | 2.1 | nie | wyszedl (B) | - |
| 08:41:15 | [32485, 32297, 9] | zamkniety | 43 | bot_aktywny | 2.8 | nie | wyszedl | 2.2 |
| 08:41:33 | [32485, 32301, 9] | zamkniety | 43 | bot_aktywny | 7.0 | tak | wyszedl | 3.8 |
| 08:44:26 | [32498, 32269, 8] | zamkniety | 35 | bot_aktywny | 4.2 | nie | wyszedl | 0.8 |
| 08:45:09 | [32499, 32269, 8] | zamkniety | 35 | bot_aktywny | 1.4 | nie | wyszedl | 1.5 |
| 08:47:06 | [32480, 32290, 8] | otwarty | 119 | bot_aktywny | 3.5 | nie | wyszedl (B) | - |
| 08:48:15 | [32476, 32272, 9] | zamkniety | 32 | bot_aktywny | 1.4 | nie | wyszedl | 1.5 |
| 08:52:36 | [32503, 32282, 9] | otwarty | 101 | bot_aktywny | 1.4 | nie | wyszedl (B) | - |
| 08:57:55 | [32484, 32298, 9] | zamkniety | 43 | bot_aktywny | 7.0 | nie | wyszedl | 1.5 |
| 09:00:17 | [32498, 32269, 8] | zamkniety | 35 | bot_aktywny | 11.9 | nie | wyszedl | 0.8 |
| 09:17:01 | [32491, 32290, 8] | otwarty | 119 | bot_aktywny | 2.8 | nie | wyszedl (B) | - |
| 09:25:58 | [32487, 32301, 9] | zamkniety | 43 | bot_aktywny | 3.5 | nie | wyszedl | 3.8 |
| 09:29:48 | [32499, 32280, 9] | otwarty | 101 | bot_aktywny | 11.2 | nie | wyszedl (B) | - |
| 09:44:41 | [32502, 32282, 9] | otwarty | 101 | bot_aktywny | 1.4 | nie | wyszedl (B) | - |
| 09:48:41 | [32474, 32272, 9] | zamkniety | 32 | bot_aktywny | 2.8 | nie | wyszedl | 2.2 |
| 09:51:37 | [32497, 32281, 9] | otwarty | 101 | bot_aktywny | 3.5 | nie | wyszedl (B) | - |
| 09:57:51 | [32491, 32290, 8] | otwarty | 119 | bot_aktywny | 2.8 | nie | wyszedl (B) | - |
| 10:07:33 | [32499, 32268, 8] | zamkniety | 35 | bot_aktywny | 4.2 | nie | wyszedl | 1.5 |
| 10:17:13 | [32503, 32271, 8] | zamkniety | 35 | bot_aktywny | 0.7 | nie | wyszedl | 1.5 |
| 10:17:52 | [32500, 32281, 9] | otwarty | 101 | bot_aktywny | 3.5 | nie | wyszedl (B) | - |
| 10:21:00 | [32485, 32297, 9] | zamkniety | 43 | bot_aktywny | 2.8 | nie | wyszedl | 2.2 |
| 10:36:45 | [32501, 32281, 9] | otwarty | 101 | bot_aktywny | 2.8 | nie | wyszedl (B) | - |
| 10:42:26 | [32507, 32277, 9] | otwarty | 101 | bot_aktywny | 5.6 | nie | wyszedl (B) | - |
| 10:42:42 | [32508, 32278, 9] | otwarty | 101 | bot_cichy | 18.2 | nie | wyszedl (B) | - |
| 10:43:21 | [32507, 32277, 9] | otwarty | 101 | bot_cichy | 12.6 | nie | wyszedl (B) | - |
| 10:46:06 | [32500, 32280, 9] | otwarty | 101 | bot_aktywny | 4.9 | nie | wyszedl (B) | - |
| 10:48:26 | [32499, 32269, 8] | zamkniety | 35 | bot_aktywny | 1.4 | nie | wyszedl | 1.5 |
| 10:51:51 | [32485, 32297, 9] | zamkniety | 43 | bot_aktywny | 2.8 | nie | wyszedl | 2.2 |
| 10:52:12 | [32484, 32296, 9] | zamkniety | 43 | bot_aktywny | 2.8 | nie | wyszedl | 1.5 |
| 10:59:26 | [32485, 32298, 9] | zamkniety | 43 | bot_aktywny | 2.8 | nie | wyszedl | 2.2 |
| 11:04:53 | [32500, 32281, 9] | otwarty | 101 | bot_aktywny | 6.3 | nie | wyszedl (B) | - |
| 11:06:17 | [32491, 32290, 8] | otwarty | 119 | bot_aktywny | 2.8 | nie | wyszedl (B) | - |
| 11:07:36 | [32485, 32297, 9] | zamkniety | 43 | bot_aktywny | 1.4 | nie | wyszedl | 2.2 |
| 11:11:48 | [32501, 32282, 9] | otwarty | 101 | bot_aktywny | 4.9 | nie | wyszedl (B) | - |
| 11:12:39 | [32491, 32290, 8] | otwarty | 119 | bot_aktywny | 7.7 | nie | wyszedl (B) | - |
| 11:15:40 | [32485, 32297, 9] | zamkniety | 43 | bot_aktywny | 1.4 | nie | wyszedl | 2.2 |
| 11:48:56 | [32507, 32270, 8] | zamkniety | 31 | bot_zatrzymany | 16.1 | tak | wyszedl | 1.5 |
| 11:58:24 | [32348, 32225, 7] | otwarty | 4000+ | bot_zatrzymany | 49.7 | UNKNOWN | wyszedl (B) | - |
| 12:00:42 | [32320, 32248, 7] | otwarty | 4000+ | bot_zatrzymany | 2.8 | UNKNOWN | wyszedl (B) | - |
| 12:01:03 | [32319, 32253, 7] | otwarty | 4000+ | bot_zatrzymany | 141.4 | UNKNOWN | wyszedl (B) | - |
| 12:11:39 | [32499, 32280, 9] | otwarty | 101 | bot_aktywny | 3.5 | nie | wyszedl (B) | - |
| 12:15:31 | [32484, 32297, 9] | zamkniety | 43 | bot_aktywny | 5.6 | nie | wyszedl | 1.5 |
| 12:45:44 | [32499, 32269, 8] | zamkniety | 35 | bot_zatrzymany | 170.1 | nie | wyszedl | 1.5 |
| 12:48:45 | [32499, 32268, 8] | zamkniety | 35 | bot_zatrzymany | 142.1 | nie | wyszedl | 1.5 |
| 12:59:38 | [32503, 32271, 8] | zamkniety | 35 | bot_aktywny | 2.1 | nie | wyszedl | 1.5 |
| 13:10:13 | [32500, 32280, 9] | otwarty | 101 | bot_aktywny | 2.1 | nie | wyszedl (B) | - |
| 13:11:09 | [32499, 32269, 8] | zamkniety | 35 | bot_aktywny | 5.6 | nie | wyszedl | 1.5 |
| 13:15:40 | [32500, 32280, 9] | otwarty | 101 | bot_aktywny | 4.9 | nie | wyszedl (B) | - |
| 13:24:09 | [32502, 32273, 8] | zamkniety | 35 | bot_aktywny | 0.7 | nie | wyszedl | 3.0 |
| 13:37:53 | [32499, 32269, 8] | zamkniety | 35 | bot_aktywny | 8.4 | nie | wyszedl | 1.5 |
| 13:54:59 | [32485, 32297, 9] | zamkniety | 43 | bot_aktywny | 2.1 | nie | wyszedl | 2.2 |
| 14:01:10 | [32500, 32280, 9] | otwarty | 101 | bot_aktywny | 3.5 | nie | wyszedl (B) | - |
| 14:06:57 | [32499, 32269, 8] | zamkniety | 35 | bot_aktywny | 1.4 | nie | wyszedl | 1.5 |
| 14:11:32 | [32508, 32277, 9] | otwarty | 101 | bot_cichy | 14.7 | nie | wyszedl (B) | - |
| 14:41:15 | [32485, 32298, 9] | zamkniety | 43 | bot_aktywny | 0.7 | tak | wyszedl | 2.2 |
| 14:54:03 | [32500, 32280, 9] | otwarty | 101 | bot_aktywny | 2.8 | nie | wyszedl (B) | - |
| 15:07:06 | [32484, 32297, 9] | zamkniety | 43 | bot_aktywny | 7.0 | nie | wyszedl | 1.5 |
| 15:18:36 | [32499, 32269, 8] | zamkniety | 35 | bot_aktywny | 2.1 | tak | wyszedl | 1.5 |
| 15:19:48 | [32509, 32272, 8] | zamkniety | 31 | bot_cichy | 37.8 | nie | wyszedl | 3.0 |
| 15:35:14 | [32498, 32269, 8] | zamkniety | 35 | bot_aktywny | 4.9 | nie | wyszedl | 0.8 |

## 5. Błędy symulatora znalezione w walidacji i poprawione

1. **Fałszywe `brak_wyjscia` dla otwartego obszaru bez danych.** Epizod w otwartej jaskini (np. 1124 pola) bez celu i bez punktów trasy kończył się `brak_wyjscia` + `alarm=True`, czyli twierdził Z7 ("nie ma wyjścia"), choć symulator po prostu nie miał dokąd iść. Teraz wynik to `brak_danych` (`alarm=False`, powód `brak_celu_i_punktow_trasy`). Zmierzone przed poprawką (A bez historii): 11 otwartych epizodów `brak_wyjscia`; po poprawce są `brak_danych` (w tabeli 1a wariant A, z historią: `brak_wyjscia` otwarte tylko tam, gdzie jest cel albo punkty, czyli 0).
2. **Raport `karol_wyszedl_z_obszaru` przy obszarze uciętym limitem BFS (4000).** Pole spoza uciętego BFS było liczone jako 'wyszedł'. Teraz tylko zmiana piętra jest pewna, reszta = UNKNOWN (dotyczyło 5 przejęć w otwartym obszarze 4000).
3. **Brak śladu pola wejścia w zdarzeniu `przejscie`.** Dopisano `od` (pole wejścia), potrzebne do porównania z wyrocznią.

## 6. Ograniczenia i UNKNOWN

- Czas rzeczywisty vs przewidziany to NIE test trafności: symulator opisuje regułę Z1-Z8, bot w telemetrii działał wg starej logiki, więc błąd mierzy potencjał do odzyskania, nie jakość modelu.
- `po_s` w ucieczka.json to pierwsza próbka poza obszarem BFS bez pól z flagą 2; wejście na pole z flagą 2 bez zmiany piętra bywa tam liczone jako wyjście (np. (32340,32202,z7)).
- Cenzurowanie: epizody z urwaną serią (bez wyjścia w telemetrii) nie wchodzą do błędu czasu.
- Cel i punkty trasy nie są w epizodach: A bez nich, B z sumą wszystkich tras w promieniu 30, C z celem 'skąd przyszedłem' ([HIP]). Wynik wyboru piętra zależy od C (sekcja 1c).
- Drzwi: znane jedne, (32505,32270,z8). Przejęcie Karola 08:23:50 (32356,32208,z7, zatrzymany bot, 114 s, 81 pól do (32400,32220,z7)) pokazuje wyjście, którego model nie zna (prawdopodobnie kolejne drzwi traktowane przez mapę jak ściana; UNKNOWN). Symulator zgłasza tam alarm, co zgadza się z zasadą Z7.
- Flagi 2 bez ważnego lądowania nie są wyjściami; czy gra pozwala wejść tam inaczej (lina, Use) = UNKNOWN. Lina z plecaka: opcja wyłączona (decyzja Karola 16.10).
- Koszt nieudanej próby 6 s, czekanie Z6 5-10 s i skos liczony jak krok prosty: założenia, nie pomiary. Stan drzwi w historii = UNKNOWN.
- Przejęcia Karola bez telemetrii (zatrzymany bot, bot cichy) nie mają trasy: porównanie tylko po pozycji końcowej.
- Nie odtworzono: wpływu graczy/mobów blokujących przejście (Z6) i ognia (Z8) na epizodach: dane epizodu mają graczy w pierwszej próbce, ale brak ich dalszych pozycji (UNKNOWN).

