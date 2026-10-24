# Retronic: analiza CPU i plan optymalizacji

2026-10-24. Status: **analiza zakończona; propozycja do specyfikacji i zatwierdzenia, bez wdrożenia**.
Zakres: pomocnik, strażnik, klient gry i otoczenie działających instancji. Projekt prywatny.

**Dokument wykonawczy: [Zweryfikowany plan naprawy CPU](PLAN_NAPRAWY_CPU_2026-10-24.md).**
Uzupełnienie po próbach: filtr natywny i odczyt do stałego bufora są już sprawdzone offline. Pełny skan
64 MiB pamięci własnego procesu testowego: 97,04 → 40,39 ms CPU, te same 256 obiektów i liczba odczytów.
Ponowne używanie masek NumPy okazało się wolniejsze i zostało odrzucone. Poniższy audyt opisuje
wcześniejsze rozpoznanie; aktualny zakres rekomendowanych zmian określa plan. Dowody:
[zweryfikowane prototypy](wydajnosc/2026-10-24/validated-prototypes).

## Wniosek

Największy zmierzony koszt jest w **wątkach skanera pamięci `rdzen.py`**, a nie w samej logice decyzji `cavebot.py`.
Siedem aktywnych strażników zajmowało łącznie **3,70–3,75 rdzenia logicznego**, z czego ich wątki skanera
**3,45–3,54 rdzenia**. Cztery uchwycone procesy botów zużywały łącznie **0,18 rdzenia**.
To wskazuje kolejność pracy: najpierw koszt przetworzenia pamięci, potem odczyty i odkrywanie obiektów,
następnie koszty RPC, panelu, obrazu i wyznaczania dróg.

Znaleziono konkretną przyczynę nadmiarowych skanów przy pustym wyniku. Samo przywrócenie w tej ścieżce
odstępu dwóch sekund mogłoby jednak opóźnić wykrycie nowych obiektów względem dzisiejszej implementacji.
**Nie kwalifikuje się automatycznie jako optymalizacja bez pogorszenia.** Pierwsza ścieżka realizacji musi
obniżać koszt obliczeń przy zachowaniu pokrycia i terminów odczytów. Zmiana harmonogramu to osobna decyzja.

Nie ma jeszcze podstaw do obietnicy konkretnego procentu redukcji ani stwierdzenia, że osiągnięto minimum.
Kod klienta gry jest tu dostępny jako plik wykonywalny; jego wewnętrznych algorytmów nie analizowano.

## 1. Kontrakt wynikający z polecenia Karola

Cel: minimalizować zużyty czas CPU, zachowując co najmniej dotychczasową jakość i terminowość pracy.
Liczba instrukcji maszynowych może maleć; zakres wymaganych sprawdzeń i kompletność wyników pozostają.

Proponowane warunki odbioru, do zamrożenia w specyfikacji:

- Dla tego samego niezmiennego wejścia wyniki deterministyczne pozostają identyczne: lista obiektów,
  identyfikatory, kolejność, wybór kopii obiektu, pozycje, HP, flagi ramek, klasyfikacja graczy i widm.
- Zachowane zostają wszystkie kontrole bezpieczeństwa: HP, PK, GM, ogień, dziury, zmiana piętra, STOP,
  rozłączenie i anulowanie akcji. Brak opuszczonych zdarzeń w odtwarzanych scenariuszach.
- Każdy odczyt wymagający świeżych danych zachowuje swój kontrakt; nie zwiększamy `maks_wiek`, rytmów,
  pauz, okresów pełnego skanu ani progów reakcji jako sposobu uzyskania oszczędności.
- Wykrycie nowego obiektu, także poza znanymi regionami, nie może być późniejsze wskutek optymalizacji.
  Sam odczyt znanych adresów nie zastępuje odkrywania nowych obiektów.
- Opóźnienia p50/p95/p99, najgorsze zaobserwowane reakcje oraz odstępy między kontrolami bezpieczeństwa
  nie mogą pogarszać się ponad rozdzielczość pomiaru względem dopasowanej bazy. Przekroczenie lub zbyt mało danych
  oznacza brak odbioru. Żaden skończony test nie dowodzi braku regresji we wszystkich możliwych stanach.
- Skuteczność pościgu, lootu, leczenia i marszu porównujemy w tych samych scenariuszach. Sam exp/h nie wystarczy:
  zależy również od respawnu, graczy i mapy. Przed testem na żywo trzeba ustalić minimalną próbę i sposób
  liczenia niepewności; brak mocy statystycznej oznacza UNKNOWN, nie „bez zmian”.

Pamięć żywej gry zmienia się również podczas pojedynczego skanu. Równość wyjść badamy na zamrożonych wejściach,
a świeżość i zachowanie na zsynchronizowanych śladach oraz później na żywo. Nie obiecujemy bitowej identyczności
dwóch odczytów z różnych chwil.

## 2. Dowody i ograniczenia pomiaru

Baza kodu: `ruch-r1-1014`, HEAD `0d3295c`, **liczne istniejące zmiany lokalne**. Faktyczną bazą audytu jest
robocza zawartość plików, której SHA-256 zapisano w [manifeście](wydajnosc/2026-10-24/source-manifest.json).
Odczytano instrukcje projektu `CLAUDE.md` i stan `STAN.md`; pliku `AGENTS.md` w katalogu pomocnika nie było.
Uruchomiono `graphify query` i zweryfikowano wskazania bezpośrednio w źródłach.

Dwa pomiary po około 30 s: start 10:44:34 i 10:45:43 CEST. Różnica `utime + stime` z `/proc/PID/stat`
i `/proc/PID/task/TID/stat`, podzielona przez `SC_CLK_TCK` i czas ścienny. **100% oznacza jeden logiczny CPU**;
maszyna zgłaszała 20 logicznych CPU. Definicje pól: [dokumentacja jądra Linux](https://docs.kernel.org/filesystems/proc.html).
Bez dołączania profilera, sygnałów, RPC do gry, klików, odczytu `/proc/PID/mem`, restartów i zmian ustawień.

| Warstwa | Pomiar 1, % jednego CPU | Pomiar 2 | Odpowiednik rdzeni |
|---|---:|---:|---:|
| Strażnicy, cały proces | 369,957 | 375,054 | 3,70–3,75 |
| W tym wątki skanera, podzbiór poprzedniego wiersza | 344,826 | 353,731 | 3,45–3,54 |
| Klienci gry | 128,312 | 134,122 | 1,28–1,34 |
| wayvnc | 48,327 | 56,282 | 0,48–0,56 |
| Procesy botów | 18,472 | 17,996 | 0,18 |
| Osobne okno quickshell Retronic | 4,493 | 3,892 | 0,04 |

| Instancja | Strażnik, pomiar 1 | Strażnik, pomiar 2 | Jego wątek skanera, pomiar 1 |
|---|---:|---:|---:|
| wydra | 96,026% | 96,333% | 91,865% |
| borsuk | 63,507% | 62,337% | 59,446% |
| invincible | 55,685% | 55,385% | 51,857% |
| dawajkesh | 49,161% | 51,593% | 46,731% |
| gebelish | 47,164% | 51,127% | 44,768% |
| odchyd | 36,912% | 36,724% | 33,051% |
| marianni | 21,502% | 21,555% | 17,108% |

Źródła: [pomiar 1](wydajnosc/2026-10-24/cpu-proc-30s.json),
[pomiar 2](wydajnosc/2026-10-24/cpu-proc-30s-round2.json).
Nazwy wątków w `/proc` są skrócone; w źródłach odpowiadają `_petla_skanera`, `serwer` i pętli głównej strażnika.
Skrypt heurystycznie oznacza również wrappery z `straznik.py` w argumentach; te miały 0% i nie zmieniają sum.
Wartości wątku i procesu mogą minimalnie różnić się wskutek kolejności odczytów i rozdzielczości licznika.

Pomiary obejmują procesy istniejące na obu końcach okna. Pomijają krótkotrwałe `grim`, `panel.py`, `okno_api.py`
i ich zużycie po zakończeniu. Wybór po katalogu roboczym może dołączyć np. terminal; nie zaliczono go do tabeli warstw.
Nie jest to całodobowy profil ani baza osobno dla walki, postoju i relogu. Wersji modułów faktycznie załadowanych
w każdym procesie nie potwierdzono przez instrumentację; manifest opisuje pliki na dysku.

## 3. Ustalenia w kodzie

### A. Pełne skany po pustym wyniku — mechanizm potwierdzony offline, najwyższy priorytet analizy

`rdzen.py`: `_skanuj_stwory` (ok. 396), `_potrzebny_pelny` (388), `skaner_krok` (544).

1. Pełny skan bez trafień zostawia `regiony_stworow = None` (`sorted(wiek) or None`).
2. `_potrzebny_pelny` dla `None` zwraca `True` niezależnie od czasu ostatniego skanu.
3. `skaner_krok` pomija gałąź planowania następnego terminu, ponownie skanuje i zwraca sen 0,01 s.
4. Trwa to, dopóki skaner jest aktywny; po braku zapytań o stwory dłuższym niż `SKANER_BEZCZYNNY=20 s`
   przechodzi w bezczynność. To nie dowodzi, że każda wylogowana instancja skanuje stale.

Odtworzenie na sztucznym zegarze, pamięci i skanerze: 12 obiegów = **12 pełnych skanów / 2,52 s** przy
symulowanym koszcie skanu 0,2 s. Kontrola ze znanym regionem: 12 obiegów = 6 skanów, w tym 1 pełny / 3,31 s.
[Wynik reprodukcji](wydajnosc/2026-10-24/empty-scan-reproduction.json).

W [ostatnich 250 wierszach logu](wydajnosc/2026-10-24/scan-log-excerpt.txt) było 184 wpisów pełnego skanu
z `stwory=0`. Pełne skany są bez identyfikatora instancji: **nie przypisujemy ich na pewno wydrze**.
To zgodne z odtworzonym mechanizmem i dominacją wątku skanera, ale nie zastępuje profilowania konkretnego procesu.

Propozycja rozdzielenia stanów „jeszcze nie skanowano”, „udany pusty wynik”, „błąd/niepełny odczyt” jest zasadna.
Przestawienie pustego wyniku na pełny skan co 2 s wymaga jednak osobnej oceny: dzisiejsza pętla może wcześniej
wykryć pojawienie się postaci. Bez dowodu równoważnej detekcji zdarzenia nie spełni ścisłego zakazu pogorszenia.

### B. Skanowanie całych regionów i maski NumPy — koszt strukturalny potwierdzony; podział czasu UNKNOWN

`rdzen.py`: `czytaj` (198), `_kandydaci_stworow` (326), `_skanuj_stwory` (396).
Nawet „szybki” skan czyta całe zapamiętane regiony, nie same znane obiekty.
Następnie filtr tworzy tablicę porównań dla całego bufora i kolejne maski logiczne, listę trafień oraz słowniki.
Odczyt map siedmiu klientów wskazał około **353–382 MiB** kwalifikujących się regionów na pełny skan.
To rozmiar zakresów adresowych, nie pomiar faktycznie przeczytanych bajtów ani RSS.

Kierunek pierwszego eksperymentu: zachować całe pokrycie i harmonogram, ale ograniczyć alokacje oraz liczbę
przejść po buforze. Porównać maski z buforami roboczymi i ewentualny natywny filtr w jednym przebiegu.
Dobór technologii dopiero po próbie pomiarowej; przepisanie całego bota na inny język nie jest uzasadnione.

Ponowne użycie bufora przez `preadv` jest kandydatem, nie gotowym rozwiązaniem. `preadv` odczytuje od jednego
offsetu do kolejnych buforów; **nie jest listą dowolnych odległych adresów**.
Wymaga sprawdzenia obsługi `/proc/PID/mem`, częściowych odczytów i własności bufora:
[dokumentacja Python](https://docs.python.org/3/library/os.html#os.preadv).
NumPy potrafi zwalniać GIL; współdzielony mutowalny bufor bez synchronizacji nie jest bezpiecznym skrótem:
[dokumentacja NumPy](https://numpy.org/doc/stable/reference/thread_safety.html).

Przy dzieleniu regionu na fragmenty trzeba zachować granice obiektów, wyrównanie, kolejność odwiedzin,
pełny zakres pól obiektu i zasadę „ostatnia kopia danego ID wygrywa”. Zmniejszenie liczby odczytanych pól
bez dowodu ich niezmienności nie jest optymalizacją równoważną.

### C. Jednowątkowy serwer, blokady i powtarzane odkrywanie

`straznik.py:60–81` obsługuje po jednym żądaniu na połączenie. `bot.py:44–52` tworzy nowe gniazdo dla każdego RPC.
`rdzen.stwory_info` może czekać na zamek skanera; `gracz` potrafi uruchomić pełne szukanie statystyk, jeśli
blok przestał być poprawny albo nie zmieniał się przez 20 s. `wiadomosci` przeładowuje moduł przy każdym
żądaniu, podczas gdy kontenery mają już sprawdzanie mtime. W `wiadomosci._odswiez` brak żywych buforów
również wymusza pełne szukanie; jego aktualnego udziału w CPU nie wyodrębniono.

Pętla główna strażnika po zakończeniu launchera co sekundę woła `znajdz_gre`, które przeszukuje `/proc`.
Główne wątki siedmiu strażników zużywały po około 1,4–1,7% CPU w pierwszym pomiarze.
To mniejszy, ale mierzalny obszar: walidacja znanego PID z czasem startu i pełne szukanie po jego utracie,
z zachowaniem obsługi updatera i subreapera.

Kandydaci: przeładowanie wiadomości po zmianie pliku, współdzielenie jednego wyniku między równoczesnymi
zgodnymi żądaniami oraz ewentualny pakiet odczytów. Trwałe połączenie do obecnego serwera mogłoby zablokować
innych klientów: wymaga zmiany protokołu i sprawiedliwej obsługi wielu połączeń. W pierwszej kolejności
usuwamy koszt samego skanu. „Cache na cały tick” jest niedopuszczalny przez klik/ruch/leczenie bez unieważnienia.

### D. Panel i QML — potwierdzone powielanie pracy, zysk jeszcze niezmierzony

`okno/Backend.qml`: odświeżanie wybranej postaci co 2 s i wszystkich co 5 s, niezależne zadania.
`okno_api.cmd_stan` robi wspólny skan procesów, lecz `odczyt_panelu` uruchamia osobne `panel.py` dla instancji,
a `panel.procesy_bota` ponownie przeszukuje `/proc`. Jest więc już częściowa agregacja, ale nie obejmuje całej ścieżki.
Panel pyta też o statystyki gracza; ma istniejącą 30-sekundową pauzę po nieudanym odczycie, której nie wolno zgubić.

Plan: jeden kontekst inwentaryzacji na odświeżenie oraz wykorzystanie go przez panel i okno; współdzielenie
pokrywających się odświeżeń bez pogarszania dzisiejszej świeżości. Liczyć także koszt krótkotrwałych procesów.
Ograniczanie pracy niewidocznych sekcji jest osobnym kandydatem, dopiero po sprawdzeniu wymogów powiadomień.

### E. Zrzuty, trasy i telemetria — kandydaci drugiej kolejności

`ekran.grim/zrzut` uruchamia `grim`, koduje PNG, a Python dekoduje obraz. `ekran._rozmiar_ekranu` otwiera
połączenie X11. Do porównania: surowe piksele, pojedynczy zrzut dla kilku analiz tej samej klatki i ewentualny
wycinek obrazu, zawsze z zachowaniem wymiarów, formatu kolorów i momentu odczytu.
Zrzut po akcji nie może używać obrazu sprzed akcji. Nie zmieniamy FPS ani rozdzielczości jako skrótu.

`cavebot.droga` ma już część szybkich ścieżek i cache pól piętra; telemetria ma limit 1 próbki/s,
oblicza A* dla najwyżej trzech celów co 2 s. Nie proponujemy ich jako brakujących mechanizmów.
Ewentualny cache dróg musi obejmować wersję przeszkód, piętro, zajętość, ogień, drzwi i reguły ruchu.
Przy ~0,18 rdzenia całych botów oszczędności w tym obszarze mają obecnie mniejszy sufit niż skaner.

## 4. Eksperyment: krótszy kod nie oznacza niższego CPU

Poza kodem produkcyjnym porównano obecny filtr NumPy z filtrem `bytes.find` i walidacją trafień.
Python 3.14.7, NumPy 2.5.2; bufor 8 MiB, mediana pięciu powtórzeń, czas CPU procesu.
603 małe przypadki i pięć dużych korpusów dały identyczne listy trafień. To sprawdza tylko filtr kandydatów,
nie całe dekodowanie obiektu ani równoważność wszystkich możliwych wejść.

| Korpus | NumPy, ms CPU | bytes.find, ms CPU | Ocena kandydata |
|---|---:|---:|---|
| Same zera | 5,765 | 22,023 | wolniejszy |
| Losowe bajty | 5,222 | 2,773 | szybszy |
| Rzadkie obiekty | 3,161 | 20,784 | wolniejszy |
| Gęste obiekty | 12,783 | 48,131 | wolniejszy |
| Sam znacznik | 70,225 | 612,142 | wolniejszy |

**Wariant odrzucony jako ogólna zamiana filtra.** Wyniki syntetyczne przy obciążonej maszynie nie przewidują
wprost przyspieszenia całego strażnika. [Pełny wynik](wydajnosc/2026-10-24/synthetic-scanner-bench.json).

## 5. Plan wykonania i bramki

| Faza | Praca | Warunek przejścia |
|---|---|---|
| F0 — kontrakt i baza | Zamrozić wymagania, stan kodu i pokrętła; baza CPU/latencji osobno dla walki, marszu, postoju, pustej listy, relogu i pracy panelu. Dodać identyfikator instancji do pełnych skanów w izolowanej wersji diagnostycznej. | Zatwierdzona specyfikacja; znane terminy kontroli i metoda porównania; bez zmian aktywnego `rdzen.py`. |
| F1 — równoważne przetwarzanie | Profilować na odtwarzanych danych odczyt, filtr, dekodowanie i publikację; porównać maski/bufory i ewentualny natywny filtr. Zachować pokrycie i rytmy. | Identyczne pełne wyniki, brak regresji granic/duplikatów/błędów; mniej CPU w reprezentatywnych przypadkach, bez regresji w trudnych wejściach. |
| F2 — odczyty i współbieżność | Zmierzyć bajty/s i oczekiwanie na blokadę; usunąć dowiedzione duplikaty pracy. Walidować znane PID, przeładowywać wiadomości po mtime. | Testy konkurencji, aktualizacji klienta, anulowania i odzyskiwania; brak opóźnienia kontroli HP/PK. |
| F3 — odkrywanie obiektów | Rozdzielić stan niezainicjalizowany/pusty/błąd. Zbadać indeks obiektów lub wiarygodny sygnał zmiany z pełnym fallbackiem. | Osobna decyzja dla zmiany harmonogramu; nowe obiekty wykrywane co najmniej tak szybko jak obecnie. Same cykliczne odczyty znanych adresów nie przechodzą. |
| F4 — otoczenie | Wspólny kontekst panelu; potem obrazy i trasy, jeśli profil nadal uzasadnia. | Zachowane wszystkie pola API, świeżość obrazu, reguły dróg i powiadomienia; koszt potomków wliczony. |
| F5 — odbiór | Niezależny review, odtworzenia, następnie jedna instancja na żywo i stopniowe rozszerzenie. | Zgoda na konkretny test/wdrożenie, gotowe cofnięcie; pełna macierz niepogorszenia i spadek CPU; nierozstrzygnięte wyniki blokują rozszerzenie. |

Najpierw tania próba F1. Jeśli maski NumPy nie dadzą wystarczającego zysku, przedstawić zmierzony wybór
modułu natywnego wraz z kosztem utrzymania, budowania i dystrybucji. Nie podejmowano tej decyzji w audycie.

F0 powinno rejestrować: CPU user/system procesu i wątku, CPU potomków, bajty i liczbę odczytów,
liczbę skanów pełnych/szybkich, czas skanu, kolejki RPC, czekanie na zamek, wiek danych przy decyzji,
odstęp między kontrolami oraz maksymalne przerwy ticka. Wiek liczony dziś od końca skanu nie ujawnia,
jak dawno odczytano jego pierwszy region: mierzyć początek i koniec pozyskania danych.
Liczniki agregować poza gorącą ścieżką; osobno zmierzyć narzut instrumentacji.

Macierz zgodności: nowe i znikające obiekty, identyczne ID w różnych adresach, relog/PID reuse,
nowy region pamięci, przesunięcie granic regionów, niepełny odczyt, obiekt przy granicy fragmentu,
nieprawidłowy tekst/ID, gracze i widma, HP=0, ramki, brak buforów czatu, taby, zmiana piętra,
ogień/drzwi/dziury, równoczesne RPC panelu i bota, STOP podczas odczytu i po wykonaniu akcji.
Zamrożone wejścia i losowość pozwalają porównać także decyzje i kolejność akcji.

Próby CPU: przeplatane stara/nowa wersja z rozgrzewką, tą samą próbką i ustawieniami; raportować rozrzut,
nie tylko średnią. Nie porównywać dwóch różnych spotów jako dowodu równoważności. Maksymalna liczba
obsługiwanych instancji jest kryterium pomocniczym, a nie zamiennikiem pomiaru kosztu pojedynczego zadania.

## 6. Bezpieczne przygotowanie zmian i cofnięcie

`rdzen.py` jest **przeładowywany przez działających strażników po zmianie pliku**. Edycja w głównym katalogu
mogłaby zmienić aktywny system bez restartu. `wiadomosci.py` i `kontenery.py` też mają przeładowywanie.
Właściwe wdrażanie zaczyna się w izolowanej kopii zawierającej również dzisiejsze niezacommitowane zmiany;
worktree z samego HEAD nie odtworzy obecnej bazy. Nie wolno stracić zmian innych sesji.

Każda paczka ma osobny dowód zgodności i zestaw skrótów plików. Uruchomienie nowego wariantu na jednej
postaci dopiero po uzgodnieniu z prowadzącą ją sesją. Cofnięcie obejmuje nie tylko plik, ale też stan cache,
wątek skanera i ewentualny protokół RPC. Samo przywrócenie kodu nie gwarantuje usunięcia nowego stanu.
Plan cofnięcia musi zostać sprawdzony na izolowanym procesie przed próbą na żywo.

## 7. Co wykonano, co pozostaje

Wykonano dwa pomiary procesów i wątków, analizę gorących ścieżek, odtworzenie pustego skanowania,
porównanie dwóch filtrów i kontrolne uruchomienie istniejących testów skanera. Dowody w katalogu
[wydajnosc/2026-10-24](wydajnosc/2026-10-24).

- `timeout 50s python3 -I testy/test_rdzen_stwory.py`: **34/34 OK**, zero linii FAIL;
  [zapis wyniku](wydajnosc/2026-10-24/baseline-test-rdzen-stwory.txt).
- `timeout 50s python3 -I testy/test_skan_rytm.py`: **31/31 OK**, zero linii FAIL;
  [zapis wyniku](wydajnosc/2026-10-24/baseline-test-skan-rytm.txt).

Są to testy obecnej bazy, nie dowód poprawności przyszłej optymalizacji. Osobny test regresji pętli pustych
skanów należy zamrozić razem z kontraktem F0; teraz utrwalono reprodukcję diagnostyczną, bo nie wdrażano naprawy.

Źródła eksperymentów zachowano jako tekst:
[próbkowanie CPU](wydajnosc/2026-10-24/cpu-proc-30s.py.txt),
[benchmark filtra](wydajnosc/2026-10-24/synthetic-scanner-bench.py.txt).
To zapis przeprowadzonych prób: ponowne wykonanie nadpisałoby ich stałe ścieżki wyjściowe, więc do nowych
pomiarów należy wybrać nowy katalog/plik.

Nie wprowadzono optymalizacji produkcyjnej, nie zmieniono ustawień ani nie uruchomiono/zatrzymano botów.
Nie dowiedziono jeszcze docelowej oszczędności, parzystości zachowania nowej implementacji ani pełnego profilu
każdego stanu gry. **Następny krok: specyfikacja F0/F1 z powyższym kontraktem, następnie izolowane pomiary i implementacja.**
