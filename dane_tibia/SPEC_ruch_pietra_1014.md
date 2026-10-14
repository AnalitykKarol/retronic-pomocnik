# SPEC: płynny ruch, przejścia pięter, mapa z doświadczenia (14.10)

Źródła: `dane_tibia/ruch/MAPA_DOSWIADCZENIA.md`, `PLYNNOSC.md`, `PIETRA.md`, `mapa_doswiadczenia.json`,
`pietra_statystyki_przejsc.json` (analiza 12 h telemetrii i logów, 692 udane przejścia z8/z9).

## Cel i granice

- Postać ma iść przez jaskinię bez szarpania: bez stukania w zablokowane pola, bez powtórek przejść, bez omijania fałszywego
  ognia i bez odpuszczania trolli, do których da się dojść.
- **Nie zmieniamy**: losowania celów patrolu (freestyle), postoju i rozglądania się na miejscu, walki, lootu, UH, wypraw.
- Każda zmiana za pokrętłem (stała w `cavebot.py`, ZAKRESY i KIERUNEK w `pokretla.py`, wpis w `na_zywo.przyklad.json`),
  domyślna = nowe zachowanie dopiero po akceptacji 1 h obserwacji, wcześniej testowane przez `na_zywo.json`.
- Bot gra na żywo: realizacja bez restartu, bez STOP, bez wysyłania czegokolwiek do gry. Restart tylko po zgodzie Karola.
  Kopie zmienianych plików w scratchpadzie (`*.bak-ruch-<etap>`). Bez commita i pusha bez słowa Karola.

## Stan wyjściowy (do porównania)

| Metryka | Teraz | Cel po R1 |
|---|---|---|
| Efektywny marsz w IDZ (patrol) | ok. 49% | co najmniej 60% |
| Sekundy na pole na wizycie ze schodami | 0,85 | 0,70 lub mniej |
| Ogień: strata czasu IDZ | 11,4% (STALY=0) | poniżej 4% |
| Przejścia z udaną 1. próbą | 567/728 (78%) | 90% |
| Średni czas przejścia | 2884 s / 728 = 4,0 s | 1,5 s |
| Odpuszczenia "za ścianą" | ok. 1340 w danych, 82% korytarz skośny, 16% drzwi | spadek o 70% |
| Postój na miejscu patrolu | 7,3% IDZ | bez zmian (zamierzony) |

Przy pomiarze odfiltrować szum testowy w telemetrii (gracz "Ja", zdarzenia pietra_* bez próbki w ±3 s), patrz R0.

## R0. Czysta telemetria i pomiar ruchu (najpierw, mały)

- **R0a, szum testów:** w 12-13.10 telemetria ma ok. 2240 próbek gracza "Ja" i ok. 1900 fałszywych zdarzeń pietra_*.
  Sprawdzić, czy po G1 (RETRONIC_TELEMETRIA + brak RETRONIC_TESTY) testy nadal coś piszą (np. testy uruchamiane bez
  RETRONIC_TESTY albo w innym katalogu). Zablokować zapis, gdy nazwa postaci to "Ja" albo proces nie jest mozg.py z launchera.
- **R0b, rekord `ruch_okno` co 30 s:** czas marszu, czas stania, przyczyna postoju (schody, ogień, utknięcie, loot, walka,
  patrol_postoj, inne), luki ticku powyżej 1,5 s, liczba kroków i klików. Plus próbka telemetrii przed wczesnymi `return True`
  w `Cavebot.tick` (cavebot.py ~2956), żeby postoje nie znikały między próbkami co 1,2 s.
- **R0c, skrypt porównania** `narzedzia/porownaj_ruch.py OKNO_A OKNO_B`: tabela metryk z tabeli wyżej dla dwóch okien czasu.
- Test: `test_telemetria.py`, rekord `ruch_okno` z atrap; postać "Ja" nie zapisuje nic.

## R1. Szybkie naprawy (jeden restart)

### R1a. Ogień: maska tylko dla pól-ścian (przywraca OGIEN_STALY=1)

- Dane: 5878 wpisów ognia, część na polach z flagą ściany w minimapie (fałszywe wykrycia detektora). Przy STALY=0 bot omija je
  wszystkie (11,4% czasu IDZ), przy starej masce STALY=1 wchodził w prawdziwy ogień (09:40-09:42).
- Zmiana: `_ogien_stale_aktualizuj` / `_ogien_blok` / `_ogien_na_drodze`: do maski stałej trafia pole tylko, gdy mapa ma na nim
  flagę ściany/blokady (bit 4) albo jest niechodliwe; pole przechodnie wg mapy **nigdy** nie jest maskowane, niezależnie od
  liczby wykryć. Maska zasiana z pliku `trasy/ogien_stale.json` (pola-ściany z logów) i zapisywana po każdej zmianie.
- Pokrętło: `OGIEN_MASKA_TYLKO_SCIANY=1`; po wdrożeniu `OGIEN_STALY=1` w na_zywo.
- Przed wdrożeniem: zrzut ekranu (tylko odczyt) przy (32480,32294,z8) i (32491,32289,z8), czy to prawdziwy ogień.
- Testy (`test_ogien.py`): pole przechodnie wykryte 25 razy w 10 min nie wchodzi do maski i blokuje drogę; pole-ściana wchodzi;
  wczytanie maski z pliku; prawdziwy ogień pod nami nadal daje "schodzę".

### R1b. Przejścia pięter: porządek prób z danych

- **Drabina w górę (dziura z8 nad drabiną z9):** Ctrl+klik R od razu z bieżącego pola, bez ustawiania ortogonalnego
  (R ze skosu działa 99/100). Pole startowe ortogonalne tylko dla trybu "krok".
- **Schody (32498,32270) w górę:** pierwsza próba "krok Up" z (32498,32271) (krok 36/36, R 3/40); w dół krok z (32499,32270).
  Ogólnie: typ "schody" (flaga 2 na obu piętrach) = krok w obie strony.
- **Usunąć tryby z zerową skutecznością** w jaskini: `lina` (poza obiektem typu lina), `wlasne`, `E`, `W`, `N`, `use`,
  `use_wlasne`; łopata tylko dla dziury zasypanej (dziś tylko (32493,32259,z7)) i z pola sąsiedniego, nie z własnego (0/5 vs 1/1).
  Slot trybu, który nie ma zastosowania, nie zużywa numeru próby.
- **Czekanie na zmianę piętra:** ok. 1,2 s dla kroku i 2,0 s dla R (p99 udanych 1,5 s i 1,8 s), zamiast ok. 3,5 s + 1 s odstępu;
  przed kolejną próbą ponowny odczyt pozycji (próba mogła się udać z opóźnieniem).
- **Pole startowe:** pre-kroków najwyżej jeden; pole stuknięte 2 razy bez ruchu od razu do `pietra_zle.json` (jest od 12:55,
  sprawdzić, że licznik nie zeruje się przy migotaniu pozycji: liczyć "nie dotarł na S" zamiast "krok zwrócił None").
  Zasiać stałe dobre pola z danych: (32499,32270), (32477,32272), (32494,32290), (32495,32289), (32482,32295), (32483,32297).
- **Kandydaci "domysł":** tylko w promieniu 3 pól od gracza i z flagą 2 w mapie; kotwica na pozycji gracza, nie na punkcie trasy
  (dziś (32482,32294,z9) dał 6 porażek po 26 s, a (32348,32224) leżał 144 pola od gracza).
- Miejsca: `pietra.py` (`TRYBY_DOL`/`TRYBY_GORA` ~90-92, `kandydaci` ~49, `_start`/`_na_start`, `_odstep` ~500,
  `_po_przejsciu` ~504, `_resync` ~538).
- Testy (`test_wielopietrowa.py`): R ze skosu bez pre-kroków; schody w górę krokiem; brak łopaty na otwartej dziurze;
  odrzucenie dalekiego kandydata; pole stuknięte 2 razy trafia do złych także przy migotaniu; regresja testu nr 8
  (pierwsza próba z pola ortogonalnego) przepisana pod nowe zasady.

### R1c. Pościg i drogi: korytarz skośny i drzwi

- **Korytarz (32492,32295) do (32500,32303), z8:** chodliwy tylko po skosie; pościg liczy drogę z `skosy=False`
  (cavebot.py ~2891 i `_droga_do` ~3643), więc 82% odpuszczeń "za ścianą" to trolle w tym korytarzu.
  Zmiana: jeśli droga bez skosów nie istnieje, druga próba z `skosy=True` (krok skośny przez `krok_skos`, numpad), z limitem
  długości; alternatywnie łączniki w `trasy/miejsca_troll.json` dla tego korytarza. Pokrętło `POSCIG_SKOSY_ZAPAS=1`.
- **Drzwi (32505,32270,z8):** dodać jako przejście dla pościgu i patrolu (pole przechodnie, gdy otwarte); gdy zamknięte, Use
  na drzwiach z pola obok (jak `wypad._drzwi`), max 3 próby, potem odpuść z notatką. Plik `trasy/drzwi_jaskinia.json`.
  Pokrętło `PATROL_DRZWI=1`.
- Testy: `test_poscig_*`/`test_patrol.py`: troll w korytarzu skośnym jest osiągalny; drzwi zamknięte -> Use, potem dojście;
  drzwi niedziałające 3 razy -> odpuszczenie i jedna notatka.

### R1, akceptacja

1 h obserwacji po restarcie, potem 1 h porównania (R0c): metryki z tabeli, zero "stoję na ogniu" z utratą HP, brak nowych
utknięć przy schodach, exp/h nie niższy niż przed R1. Wtedy domyślne pokręteł w kodzie na nowe zachowanie.

## R2. Wspólna logika przejść (`przejscia.py`)

- Dziś dwie implementacje: `pietra.py` (patrol, trasa, dojście; kandydaci z flag mapy, pole startowe, pamięć) i `wypad.py`
  (`_dziura`, `_drabina`, `_lina`, bez uczenia, bez obsługi schodów (32498,32270); `_dziura` liczy kierunek z dx,dy, więc
  ze skosu pierwszy krok idzie w bok: 5 z 6 przejść wypadu przez (32476,32272) zawiodło w pierwszej próbie).
- Nowy moduł `przejscia.py` z obiektem przejścia: `typ` (dziura_drabina, schody, dziura_zasypana, lina), `pole`,
  `ladowanie` (dla dziury: (T.x,T.y,z+1); dla drabiny w górę: (T.x,T.y+1,z-1)), `start_dol`/`start_gora` (pole + tryb),
  statystyki per tryb (sukcesy, porażki, czas). Wczytywany z `mapa_doswiadczenia.json`, uzupełniany na bieżąco do
  `trasy/przejscia_stat.json`.
- Kolejność prób wg wygładzonej skuteczności z priorami typu: dziura z drabiną: dół krok, góra R; schody: krok w obie strony;
  zasypana dziura: krok, po wejściu na T bez zmiany piętra łopata z pola sąsiedniego, potem krok.
- Uczenie: po każdej próbie zapis obiekt/tryb/start/wynik/czas; porażki z potworem na lądowaniu albo w walce nie obniżają
  statystyki trybu.
- Użycie w `pietra.py`, `wypad.py` (zastąpić `_dziura`/`_drabina`/`_lina` i dodać schody) i `cavebot.py`.
- **Start na obcym piętrze / z z7:** `_resync` planuje po grafie przejść (jak `_patrol_plan`) do wejścia (32493,32259,z7)
  zamiast tworzyć pustą listę kandydatów; bot nie kończy procesu po "wyczerpanych polach" (dziś 13.10 12:55:18 i 14.10 11:30:14),
  tylko czeka, alarmuje i ponawia.
- Za pokrętłem `PRZEJSCIA_WSPOLNE=0/1`, porównanie skuteczności ze starą logiką (R0c).
- Testy: wszystkie z R1b dla obu ścieżek (patrol i wypad), zasypana dziura (krok, łopata z sąsiedniego, krok), start z z7
  (32400,32220) planuje do (32493,32259), zmiana kolejności po statystykach, potwór na lądowaniu nie karze trybu.

## R3. Sterowanie marszem (opcjonalne, po pomiarze R0)

- Analiza: zwykłe odcinki patrolu to mediana 0,55 s na pole; pościg z trzymanym klawiszem i klik w mapę dają to samo
  (ok. 1,3 pola/s). Trzymany klawisz na prostych **nie przyspieszy** marszu w mierzalny sposób.
- Do zrobienia tylko, jeśli R0b pokaże luki: (a) nie ponawiać kliku co 1,5 s, gdy pozycja się zmienia (`idz_do`,
  cavebot.py ~2676); (b) krótsze czekanie w `Postac.krok` (bot.py:205) po nieudanym kierunku; (c) wolne RPC `gracz`
  (1,5-3,4 s) odpowiada za 60 z 85 wolnych ticków: cache wartości gracza na 0,5 s albo odczyt w wątku.
- Wykonawca `PLYNNY_RUCH` (0/1/2, domyślnie 0) z `PLYNNOSC.md` zostaje jako projekt, bez wdrażania na teraz.

## Otwarte pytania (dane nie rozstrzygają)

- Przyczyna 10-22% nieudanych pierwszych kroków w dół (np. (32494,32289)): lag, potwór na lądowaniu, zgubiony klawisz.
  R0b + logowanie stanu klawisza i potworów na polu lądowania przy porażce.
- 5 przypadków "wszystkie tryby wyczerpane" (ok. 55 s każdy) i 3 pełne porażki: hipoteza zwłoki/potwór na polu.
- Czas życia odkopanej dziury z7 (32493,32259): 7 prób, mała próba.
- Czy wykrycia ognia w (32480,32294,z8) i (32491,32289,z8) to prawdziwy ogień: sprawdzić zrzutem przed R1a.

## Powiązane punkty z SPEC_naprawy_1014.md

N1 (ogień) = R1a. N6 (drzwi) = R1c. N7 (zejście schodami) = R1b + R2. N8 (start z z7) = R2. N11 (ping-pong pięter) odłożony:
losowanie celów zostaje.

## Kolejność realizacji

1. R0a + R0b + R0c (bez zmiany zachowania), testy.
2. R1a, R1b, R1c po kolei (wspólne pliki: cavebot.py, pietra.py), testy, przegląd, **restart za zgodą**, 1 h obserwacji.
3. R2 za pokrętłem, porównanie, restart za zgodą.
4. R3 tylko, gdy pomiar R0b to uzasadni.
