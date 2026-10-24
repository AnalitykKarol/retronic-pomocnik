# Plan naprawy CPU Retronic — zweryfikowany kierunek zmian

Status: in-progress — Karol zatwierdził realizację 2026-10-24; wdrożenie aktywnego runtime pozostaje osobnym krokiem po weryfikacji.
Weight: contract-fix — zachowanie obecnych wyników, zakresu i terminów odczytów.
Zlecenie Karola: mniej CPU przy co najmniej tej samej jakości i szybkości działania.

## Stan realizacji

Zatwierdzenie Karola: 2026-10-24, „dobra to teraz możesz podjąć się realizacji tego”.
Implementacja w odizolowanej kopii `../pomocnik-cpu-20261024`, branch `fix/cpu-20261024`.
Bieżąca baza robocza zachowana wraz z niezacommitowanymi zmianami; bez commita/pusha.

- [x] 0: zamrożona baza (1037 plików, SHA256).
- [x] 1: filtr C, ctypes, jawny build i fallback; 1727 przypadków × 4 typy bufora, ASan/UBSan.
- [x] 2: preadv i wyłączny bufor; zgodność pełnych obiektów, short reads, błędy, współbieżność.
- [x] 3: cache tożsamości PID; 19 testów, rzeczywisty testowy launcher/klient/exec/zniknięcie.
- [x] 4: źródłowy reload czatu; nanosekundy, stary sys.modules i .pyc, retry po błędzie, 100 handlerów bez reloadu.
- [x] 5a: rzeczywisty prywatny socket RPC i własny proces pamięci, hotreload oraz rollback/restore.
- [x] 5b: selektor instancji i instalator dry-run/backup; 12 testów w katalogach tymczasowych.
- [x] 5c: końcowy niezależny checker READY i QA PASS offline, dowody w raporcie realizacji.
- [ ] 5d: osobna zgoda na aktywny runtime, wdrożenie na jednej instancji, pomiar CPU i odbiór na żywo.

Wariant canary: `cpu_wdrozenie.py` odczytuje przy imporcie/reloadzie rdzen manifest
`.ai/cpu-wdrozenie.json` (`schema: 1`, `instances: [id]`, `components: [scan/chat/pid]`). Instalator tworzy go PRZED podmianą kodu.
Niewybrane instancje i niewłączone komponenty używają poprzednich ścieżek.
Instalacja domyślnie włącza wyłącznie `scan` (filtr+odczyt); `chat` i `pid` mają osobne przełączenie. Brak manifestu w zwykłej
nowej instalacji oznacza wszystkie optymalizacje włączone; błędny manifest wyłącza je z ostrzeżeniem.
`disable` zapisuje pustą listę i zmienia mtime rdzen, co przy kolejnym RPC przywraca stare ścieżki;
wyłączony skaner zwalnia duży bufor pod tą samą blokadą. Nie zatrzymuje gry ani bota.
Pętla `main` istniejących strażników nie jest przeładowywana: zmiana PID zacznie działać dopiero po
ich naturalnym restarcie; instalator nie restartuje procesów.

Dowody implementacji i gotowe polecenia: [realizacja](../../pomocnik-cpu-20261024/.ai/cpu-20261024/implementation.md).

## Co dokładnie zmienić

**Pierwsza paczka: zastąpić wieloprzebiegowy filtr NumPy sprawdzonym filtrem natywnym i czytać regiony
pamięci do ponownie używanego bufora.** Druga paczka: usunąć pełny przegląd `/proc` z każdego obiegu
strażnika oraz przeładowywać moduł czatu tylko po zmianie jego pliku.

Te cztery zmiany mają już prototypy lub wyodrębnione próby kosztu. Implementacja ma przenieść opisane
rozwiązania do projektu i sprawdzić ich integrację. Nie ma zaczynać od wybierania algorytmu na chybił trafił.

Wcześniejszy wariant planu zakładał optymalizację masek NumPy. Próba wykazała, że jest wolniejszy:
**ten kierunek został odrzucony**, podobnie jak `bytes.find` i selektywne indeksowanie NumPy z regresjami.

## Podstawa wyboru rozwiązania

Wszystkie poniższe wyniki dotyczą prób diagnostycznych, bez zmian aktywnego kodu i odczytów pamięci gry.

| Sprawdzone rozwiązanie | Przed | Po | Dowód |
|---|---:|---:|---|
| Filtr natywny zamiast filtra NumPy | filtr obecny | 1,65–31,00× szybciej zależnie od korpusu | 1727 zgodnych porównań; siedem korpusów po 8 MiB; 34/34 testy istniejącego skanera |
| Pełny skan: filtr natywny + odczyt do stałego bufora | 97,04 ms CPU | 40,39 ms CPU | 64 MiB pamięci własnego procesu testowego, 256 identycznych obiektów, po 14 odczytów obu wersji; 13 par pomiarów |
| Sam odczyt: `preadv` do bufora zamiast alokującego `pread` | 53,49 ms CPU | 36,39 ms CPU | ten sam zakres 64 MiB własnego procesu; identyczne bajty, 11 powtórzeń |
| Walidacja znanego PID/czasu startu zamiast przeglądu `/proc` | 13,30 ms CPU | 0,10 ms CPU | 15 powtórzeń operacji; nie obejmuje zachowania launchera |
| Sprawdzenie mtime zamiast bezwarunkowego reloadu czatu | 4,30 ms CPU | 0,032 ms CPU | 30 powtórzeń samej operacji; nie całego żądania czatu |

W pełnym skanie nowy wariant był szybszy w każdej z 13 par. Redukcja mediany wyniosła 58,38%.
Maszyna była obciążona: czasy mają duży rozrzut; wartości bezwzględne nie są prognozą wydajności produkcyjnej.
Filtr sprawdzono dodatkowo na 8192 buforach dokładnej długości pod AddressSanitizer i UndefinedBehaviorSanitizer:
brak zgłoszeń. Dowody i źródła prototypów: [zweryfikowane próby](wydajnosc/2026-10-24/validated-prototypes).

## Kolejność realizacji

### 0. Zamrozić bieżącą bazę i przygotować izolowane wykonanie

- Skopiować aktualną zawartość roboczą wraz z niezacommitowanymi zmianami do izolowanego katalogu.
  Sam HEAD nie odtwarza działającej bazy. `cavebot.py` zmienił się już od wcześniejszego audytu.
- Zapisać SHA-256 plików i ustawienia porównania. Nie zmieniać pokręteł.
- Skopiować korpusy i runner prototypu jako powtarzalne testy projektu; ścieżki `/tmp` zastąpić parametrami.
- Potwierdzić, że żadne polecenie testowe nie łączy się z prawdziwym gniazdem gry.

**Wynik zadania:** odtwarzalna stara i nowa wersja na tej samej bazie, bez zmiany aktywnego `rdzen.py`.
Powód izolacji: strażnicy przeładowują ten plik po edycji bez restartu.
Deployed-probe: n/a — przygotowanie offline.

### 1. Przenieść sprawdzony filtr natywny do projektu

**Pliki do utworzenia:** `native/skan_stworow.c`, `rdzen_skan.py`, `narzedzia/zbuduj_skan.sh`.
**Plik do zmiany:** `rdzen.py`, funkcja `Pamiec._kandydaci_stworow`.

- Punktem wyjścia jest [sprawdzony kod C](wydajnosc/2026-10-24/validated-prototypes/filter.c.txt).
  Filtr przechodzi po wszystkich pozycjach wyrównanych do 4 B w jednym przebiegu.
- Sprawdza najpierw pojemność nazwy 15, następnie jej rozmiar 1–15 i zakres ID, a potem cztery znaczniki
  float. To te same warunki logiczne co dzisiaj, w tańszej kolejności, bez masek dla całego regionu.
- Zachowuje dokładny zakres `i < len(bufor)//4 - 11` i wynik `(i+5)*4`, rosnącą kolejność przesunięć
  oraz wszystkie obecne reguły dalszego dekodowania. Nie skraca zakresu pamięci ani listy wynikowej.
- Wrapper wywołuje bibliotekę przez `ctypes`. Dla bufora krótszego niż 48 B zwraca od razu pustą listę.
  Dla `bytes` i zapisywalnego bufora przekazuje wskaźnik bez kopiowania całej zawartości.
- Zwolnienie tablicy przesunięć w `finally`; brak współdzielonego mutowalnego stanu w filtrze.
- Budować lokalnie przez `cc -std=c11 -O3 -fPIC -shared`. Wersjonować źródło i skrypt, nie gotowy plik `.so`.
  Prototyp zweryfikowano na little-endian x86_64; wrapper musi sprawdzać obsługiwaną platformę/ABI.
- Zachować obecną funkcję NumPy jako zgodny fallback przy braku biblioteki lub nieobsługiwanej platformie.
  Błąd załadowania ma być widoczny raz w diagnostyce. Nie wolno zamienić błędu filtra w pusty wynik.

**Odbiór:** uruchomić porównanie starej i nowej funkcji na utrwalonych 1727 przypadkach oraz testy
`python3 -I testy/test_rdzen_stwory.py` z natywną implementacją. Oczekiwane: zero różnic, 34/34 OK.
Powtórzyć kompilację i kontrolę ASan/UBSan z [harnessa granic](wydajnosc/2026-10-24/validated-prototypes/bounds.c.txt).
Wymagane: zero błędów pamięci. Zmierzyć także krótkie bufory i ścieżkę fallbacku.
Deployed-probe: n/a — filtr offline; odbiór na żywo w zadaniu 5.

### 2. Połączyć filtr z odczytem do stałego bufora

**Plik:** `rdzen.py`, ścieżka odczytu regionów w `Pamiec._skanuj_stwory`.

- Dodać osobny wewnętrzny odczyt regionu do `bytearray` przez `os.preadv`, używany tylko przez skaner.
  Nie zmieniać kontraktu `Pamiec.czytaj` dla statystyk, kontenerów, czatu i pozostałych konsumentów.
- Ponownie używać bufora między regionami; powiększać go przed odczytem większego regionu.
  Zwracać `memoryview` ograniczony do faktycznie odczytanej liczby bajtów.
- Tego samego widoku używać w filtrze i obecnym dekoderze. Po zakończeniu regionu nie zachowywać
  widoków ani referencji do jego zawartości w publikowanej liście obiektów.
- Bufor ma jednego właściciela pod blokadą skanera. Następny odczyt nie może go nadpisać, dopóki trwa
  filtrowanie/dekodowanie poprzedniego regionu, także gdy `ctypes` zwolni GIL.
- Zachować obsługę błędów i częściowych odczytów. Przy nieobsługiwanym `preadv` użyć dotychczasowego
  odczytu; nie ucinać regionu i nie analizować bajtów pozostałych z poprzedniej operacji.
- Zachować obecne regiony, ich kolejność, częstotliwość skanów i wszystkie wyliczane pola.

**Odbiór:** odtworzyć [pełną próbę skanu](wydajnosc/2026-10-24/validated-prototypes/integrated.py.txt)
na pamięci własnego procesu testowego. Wymagane: identyczne pełne słowniki 256 obiektów i ta sama liczba
odczytów, mniej CPU. Dodać przypadki krótkiego odczytu, błędu, przejścia większy → mniejszy region,
ponownego użycia bufora i fallbacku. Nie wymagać dokładnie 40,39 ms — to pomiar, nie gwarantowany termin.
Deployed-probe: n/a — kontrolowany proces testowy, bez gry.

### 3. Usunąć pełne przeszukiwanie `/proc` z każdego obiegu strażnika

**Pliki:** `straznik.py`: `main`; `rdzen.py`: istniejące funkcje odkrywania/identyfikacji procesu.

- Po znalezieniu właściwej gry zapamiętać PID i `starttime` z `/proc/PID/stat`.
- Co obieg sprawdzić tylko ten proces: istnienie, czas startu i zgodność pliku wykonywalnego/argumentów
  z kryteriami gry. Nie przeglądać pozostałych procesów, jeśli znana gra nadal działa.
- Pełne `znajdz_gre()` wykonywać przy pierwszym odkrywaniu, utracie procesu lub zmianie jego tożsamości.
- Zachować częstotliwość kontroli, obsługę launchera/updatera, zbieranie potomków i trzy potwierdzenia
  braku gry przed zakończeniem. Nie zmieniać zatrzymywania pozostałych procesów.

**Odbiór:** na procesach testowych sprawdzić launcher → klient, zniknięcie klienta, start nowego klienta
oraz to samo PID z innym czasem startu w fixture. Przy stabilnym kliencie licznik pełnych przeglądów `/proc`
nie rośnie. Czasy wykrycia zniknięcia/pojawienia się klienta nie pogarszają się względem obecnej pętli.
Zysk kosztu samej operacji został już zmierzony; te testy sprawdzają integrację i zachowanie.
Deployed-probe: n/a — lokalny test procesów.

### 4. Usunąć bezwarunkowy reload modułu czatu

**Plik:** `rdzen.py`, gałąź `cmd == "wiadomosci"` w `Pamiec.obsluz`.

- Przy pierwszym użyciu wykonać aktualne źródło modułu i zapamiętać na nim sygnaturę pliku `(mtime_ns, size)`.
  Bezpośrednie `compile/exec` pomija timestampowy `.pyc`, który nie rozróżnia edycji w tej samej sekundzie
  o tym samym rozmiarze. Istniejący moduł bez znacznika kodu musi zostać raz odświeżony.
  To doprecyzowanie integracji po niezależnym review, bez zmiany zakresu ani formatu RPC.
- Przeładować aktualne źródło tylko po zmianie sygnatury. Użyć wzorca
  warunkowego przeładowania jak w kontenerach. Błędy czatu nadal zwraca osłona RPC (bez pustej listy zastępującej błąd).
- Każde żądanie nadal wywołuje `wiadomosci.obsluz`; nie buforować treści odpowiedzi i nie zmniejszać
  częstotliwości czytania czatu. Zachować stan wiadomości, znaczników i kanałów w `Pamiec`.

**Odbiór:** przy 100 żądaniach bez edycji pliku — zero reloadów; po edycji — jeden reload przed następną
obsługą. Te same odpowiedzi i znaczniki na fixture czatu, także po pustym Default i zmianie zakładek.
Sprawdzić `python3 -I testy/test_wiadomosci_pusty_default.py` oraz fixture aktualizacji modułu.
Deployed-probe: n/a — lokalne RPC na fixture, bez gry.

### 5. Sprawdzić integrację i wdrożyć gotowe paczki

- Niezależny review kodu C, własności buforów, częściowych odczytów, błędów i hot-reloadu.
- Porównać pełne wyniki i decyzje dla tych samych wejść. Dodatkowe przypadki: nowy obiekt w innym
  regionie, duplikaty ID, relog, zmiana piętra, HP/PK, STOP i rozłączenie.
- Przeprowadzić próbę cofnięcia kodu i stanu buforów w izolowanym strażniku.
- Po osobnej zgodzie na wdrożenie zastosować paczkę 1+2 na jednej instancji. Zmierzyć CPU całego
  zestawu jej procesów, nie tylko filtra. Zachować mapę, tryb i pokrętła dla dopasowanego porównania.
- Sprawdzić świeżość danych, czas wykrywania nowych obiektów, opóźnienia RPC/ticka i wyniki walki,
  pościgu, lootu i leczenia. Obserwować każdy istotny stan; brak odpowiedniej próbki nie oznacza sukcesu.
- Dopiero po odbiorze rozszerzyć wdrożenie. Paczki 3 i 4 wdrażać osobno, z takim samym pomiarem i cofnięciem.

**Odbiór końcowy:** zero różnic wyników na stałych wejściach; niższe CPU przy tej samej pracy;
bez pogorszenia wykrywania i działania w sprawdzonych scenariuszach. Podać wyniki procesu i wątków
przed/po oraz materialne ograniczenia próby. Nie przenosić automatycznie wyniku −58,38% na cały system.
Deployed-probe: n/a — aplikacja lokalna; wymagana kontrola rzeczywistej instancji.

## Co zostało rozstrzygnięte, a co nie należy do tej naprawy

Rozstrzygnięte na potrzeby rekomendowanego planu: konkretny filtr, sposób odczytu i dwie zbędne operacje
pomocnicze. Ich kod lub koszt sprawdzono. Testy implementacji nadal są potrzebne: mają wykryć błędy
przeniesienia i integracji, a nie dopiero ustalić, gdzie leży zmierzony problem i jaki algorytm zastosować.

Nie zaliczać do naprawy rzadszego skanowania pustej pamięci, indeksu obiektów, zmian RPC, panelu,
zrzutów ani A*. Wcześniejszy audyt wskazał tam możliwości, ale nie potwierdził równoważnej szybszej
implementacji. Pętla pustych skanów pozostaje osobnym rozpoznanym problemem: w tej paczce obniżamy
koszt jej pracy bez wydłużania odstępu wykrycia obiektu. Zmiana harmonogramu nie jest potrzebna do
wdrożenia opisanych czterech optymalizacji.

Kod czterech optymalizacji i infrastruktura wdrożenia próbnego powstały w odizolowanej kopii.
Otwarte pozostają końcowe bramki oraz wdrożenie i odbiór aktywnego systemu. Implementacja offline
nie jest dowodem obniżenia CPU uruchomionych strażników.
