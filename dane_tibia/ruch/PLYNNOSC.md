# ZADANIE B: płynność marszu (stan IDZ), analiza i projekt PLYNNY_RUCH

Data analizy: 14.10.2026, dane z telemetrii 11.10 do 14.10 (80 634 próbek, z tego IDZ 27 054 = 33,6%, WALKA 48 267 = 59,9%).
Analiza tylko do odczytu. Żaden plik bota nie został zmieniony. Skrypty pomocnicze: `/tmp/claude-1000/-home-charlie/a82b116a-5d12-4f24-a10d-d408ab792454/scratchpad/ruch/` (a1 do c7).

## 0. Streszczenie (najważniejsze liczby)

1. **Samo chodzenie jest już płynne.** Na zwykłych odcinkach bez schodów i bez walki wizyta patrolu zajmuje mediana 0,55 s na pole (p25 0,47, p75 0,81, p90 1,09, n=137). Pościg z TRZYMANYM klawiszem daje mediana 1,31 pola/s (p10 0,99, p90 1,71, n=544 pościgów dłuższych niż 3 s), a marsz kliknięciem w mapę na odcinkach zwykłych ma te same 1,25 do 1,67 pola/s (Manhattan). Nowy wykonawca z trzymaniem klawisza nie przyspieszy prostych odcinków w sposób mierzalny, bo klient i tak idzie z prędkością postaci.
2. **Mediana 0,91 pola/s i "stoi 19%" to artefakt miary plus prawdziwe postoje w kilku konkretnych miejscach.** 0,91 to odległość Czebyszewa na próbce 1,2 s (Manhattan daje 1,33 do 1,43, bo marsz po skosie liczy się jako 1 pole). W patrolu od 13.10 postać nie zmienia pola w 24,9% czasu IDZ; po odjęciu schodów, postoju na miejscu, walki i utknięć zostaje 19,4%.
3. **Gdzie ucieka czas w patrolu (13.10 do 14.10, 4,5 h IDZ):** tylko ok. 49% czasu IDZ to efektywny marsz (oszacowane względem sufitu prędkości pola z mapy, zob. 2.4). Strata ok. 51% czasu IDZ rozkłada się tak:

| przyczyna | % czasu IDZ | % straty |
|---|---|---|
| pola ognia w promieniu 3 pól (82% tej straty w promieniu 4 pól od schodów) | 11,8 | 23,0 |
| manewr pietra.py przy schodach (ustawianie się, próby R, krok) | 9,5 | 18,6 |
| postój patrolu na miejscu ("rozglądam się" + obchód), z założenia | 7,3 | 14,2 |
| okolica schodów (<=3 pola) bez aktywnego manewru | 6,9 | 13,5 |
| sama zmiana piętra w oknie próbki | 6,3 | 12,3 |
| luki ticka >2,5 s bez żadnego zdarzenia w telemetrii | 2,6 | 5,2 |
| utknięcie / watchdog | 2,6 | 5,0 |
| pojedynczy postój bez przyczyny (mikroprzerwa) | 1,6 | 3,0 |
| marsz wolniejszy od sufitu (mikroprzerwy między kliknięciami) | 1,5 | 3,0 |
| potwór <=2 pola bez walki, unikanie gracza, wypad | 1,1 | 2,2 |

   Klaster "schody + ogień przy schodach" to ok. 34% czasu IDZ w patrolu. Postój na miejscu (7,3%) jest zamierzony i zostaje.
4. **Walka i loot prawie nie powodują postoju w IDZ**: ogon po walce lub lootcie (do 4 s po ostatniej próbce innego stanu) to w sumie 0,6% czasu postoju w patrolu.
5. **Tick w IDZ trwa ok. 0,6 do 0,9 s** (estymacja z rozkładu odstępów próbek: średni nadmiar ponad 1,0 s = 0,39 s, co przy stałym ticku daje ok. 0,78 s; kod: klik 0,30 do 0,45 s + pauza 0,15 do 0,30 s + pauza po ticku 0,05 do 0,15 s + RPC). Ticki wolniejsze niż 2 s zdarzają się głównie przez RPC `gracz` (60 z 85 zalogowanych "wolny tick", 1,9 do 3,4 s).
6. **Co proponuję:** nie "kolejny wykonawca chodzenia" jako pierwszy krok, tylko trzy etapy (rozdział 5): (E0) instrumentacja ruchu, (E1) naprawy bez nowego wykonawcy (maska ognia stałego, rzadsze re-kliki, nie-blokujące `krok`), (E2) wykonawca `PLYNNY_RUCH` oparty na sprawdzonej maszynerii trzymania klawisza z `poscig_szybki`, który prowadzi postać przez całą wizytę patrolu włącznie z dojściem do schodów i obchodem, za pokrętłem, z bezpiecznym przerwaniem.

## 1. Ścieżka wykonania marszu (numery linii z 14.10)

### 1.1 Łańcuch wywołań w jednym obiegu

```
mozg.uruchom_hybryde  (mozg.py ok. 2709)
  obieg_hybrydy()                       decyzje modelu (wątek), czat co CZAT_POLLING, trade_tick
  cb.tick()                             cavebot.py:2956
     gracz() RPC, pozycja() RPC, stwory() RPC (cache rdzenia)
     leczenie czarem, _ogien_tick (zrzut ppm co OGIEN_ODSWIEZ_S=0,8 s), _ogien_wyjdz
     jedzenie, UH, ML, walka (walcz), przerwa, loot, pochodnia
     idz()                              cavebot.py:6828  (mozg.py:1699 dokłada pauzę/rozmowę)
        _wypad_tick()
        _idz_patrol()                   cavebot.py:6672  (TRYB_PATROL=1)
           _patrol_wybierz()            losowanie miejsca (nie zmieniamy)
           faza "dojscie": _idz_segment(seg, idx)    cavebot.py:6657
                 _idz_trasa()           cavebot.py:~6844 na tymczasowo podmienionych punkty/idx
                    _trasa_stop_potwor  (świeży stwory(0.3) co obieg, gdy trasa wielopiętrowa)
                    _pietra_tick -> pietra.Pietra.tick  gdy kolejny punkt jest na innym piętrze
                    _droga_trasy -> idz_do(klik) albo krok_do(strzałka)
           faza "postoj": pauza(0.25, 0.5), PATROL_POSTOJ=(1,3) s, potem 50% obchód
           faza "obchod": _idz_segment po 2 do 5 polach
        _idz_trasa()                    gdy brak miejsc (fallback 60 s)
  pauza_po_ticku()                      cavebot.py:2656 (0,05 do 0,15 s; 0 do 0,03 s w pościgu)
```

### 1.2 Co robi marsz konkretnie

* **Klik w mapę (domyślny sposób, `self.klik = _klik_domyslny`, cavebot.py:690).** `idz_do` (2676) klika `ekran.klik_pola` w pole 3 do 6 pól do przodu (`TRASA_DO_PRZODU=(4,6)` punktów odcinka w patrolu, `DROGA_DO_PRZODU=(3,5)` w `podejdz`). Klient (OTClient przez wine, zamknięty binarek `klient/RetronicGL.exe`) prowadzi postać sam.
  * Koszt jednego kliknięcia (ekran.py:250 do 283): ruch kursora 3 do 6 kroków po 8 do 25 ms, `_przerwa(30,90)`, przytrzymanie 40 do 110 ms, `_przerwa(50,150)` = ok. 0,30 do 0,45 s. Nowe połączenie `display.Display` przy każdym kliku (`Mysz.__init__`).
  * Dodatkowo `pauza(0.15, 0.3)` po kliku i `pauza(0.08, 0.18)` w obiegach "postać idzie sama".
  * Reguły ponawiania: `KLIK_ODSTEP=0,4 s`, `KLIK_PONOW=1,5 s` (ten sam cel jest klikany ponownie co 1,5 s, mimo że postać idzie), `KLIK_BEZ_RUCHU=1,2 s` (brak ruchu = przejście na strzałki `krok_do`). `_idz_trasa` zmienia cel kliku dopiero, gdy do niego zostają <2 punkty, więc normalnie re-klik co 1,5 s do tego samego pola albo co 2 do 4 pól.
* **Strzałka (`krok_do`, 2727, `Postac.krok`, bot.py:205).** Wysyła tap, potem pętla `sleep(0.05)` + RPC `pozycja` do `CZAS_KROKU=1,5 s` czekania na zmianę pozycji, po zmianie `sleep(0.02..0.12)`. Nieudany kierunek kosztuje pełne 1,5 s zanim spróbuje się następny; po nieudanych kierunkach `pauza(0.3, 0.8)`. Używany: gdy `klik is None`, po `KLIK_BEZ_RUCHU`, w `_ogien_krok` (cavebot.py:2298), w `pietra._na_start/_proba` (pietra.py:276, 347), w obchodzie przy ogniu.
* **Trzymanie klawisza (klawisz_x11.trzymaj_kierunek / zmien / puls, bot.Postac.trzymaj_kierunek:186)** jest używane WYŁĄCZNIE w pościgu (`poscig_szybki`, cavebot.py:4254) z zabezpieczeniami: HOLD_LIMIT_S=1,5 s (puść i naciśnij w jednej partii XTEST), watchdog 0,6 s bez `puls()`, TRZYMANIE_MAX_S=20 s, atexit/sygnały, osobny proces-wartownik, wyłączony autorepeat. To jest gotowa i przetestowana (test_klawisz_x11.py, test_poscig_przechwyt.py) maszyneria dla nowego wykonawcy.
* **Pauzy "ludzkie" w trasie**: `PAUZA_DLUGA=(0,005; 3,0; 8,0)` i `PAUZA_KROTKA` w gałęziach `_idz_trasa` bez kliku (cavebot.py:~6960 do 7040); w gałęzi kliku `PAUZA_DLUGA` też działa (3 do 8 s z szansą 0,5% na obieg, czyli średnio co ok. 160 s po ok. 5 s). W patrolu gałąź z pauzą jest używana, gdy `_droga_trasy` zwraca None (odcinek patrolu jest już A*, kolejny punkt leży obok).
* **Rozglądanie się**: faza "postoj" w `_idz_patrol`: `do = teraz + uniform(1, 3)` s, w tym czasie obiegi z `pauza(0.25, 0.5)`; potem z p=0,5 obchód (`PATROL_OBCHOD_*`: pole w promieniu 3, droga 2 do 5 pól), po obchodzie 0,4 do 1,2 s postoju. Mediana "na miejscu" = 3,1 s (591 wizyt).
* **Przeliczanie A\***: `_patrol_droga` raz na wizytę i po zejściu z drogi (max co 1,0 s, `p["replan"]`); `_droga_trasy` pamięta drogę do 10 s; `droga()` ogranicza `MAPA_LIMIT=4000` pól. Wybór celu jest natychmiastowy: opóźnienie między `patrol_wizyta` a następnym `patrol_cel` ma medianę 0,00 s, p90 0,10 s. To NIE jest źródło postoju.
* **Tick główny**: kolejność w `tick` powoduje, że wczesne `return True` (leczenie, jedzenie, `_ogien_wyjdz`, UH) omijają `_tele_tick`; próbka telemetrii powstaje tylko w obiegach, które do niej dojdą i najwyżej co 1,0 s. Stąd "luki" między próbkami (zob. 2.5).

### 1.3 Gdzie marsz zamienia się z kliku w kroki (wolny tryb)

1. `_ogien_na_drodze` (2167): pole ognia w prostokącie poz do cel + 1 pole, `idz_do` zamiast kliku wywołuje `_ogien_krok` (jeden `krok_do` na obieg, A\* z ogniem jako przeszkodą).
2. `pietra._na_start/_proba`: dojście do pola przy schodach strzałką, próby `krok`, `R`, klik po skosie; `START_RUCHY_MAX`, `PIETRA_DOJSCIE_S=25 s`.
3. `_unikanie_krokami` (gracz w pobliżu) i `KLIK_BEZ_RUCHU`.

## 2. Pomiary

### 2.1 Metodyka i definicje

* Telemetria `probka` ma odstęp 1,0 s + opóźnienie do następnego ticku (rozkład: 1,0 do 1,3 s w 51%, ogon do 40 s). Parę kolejnych próbek traktuję jako "okno" tylko gdy oba końce mają `stan=IDZ`, to samo piętro, odstęp 0,9 do 1,6 s (prędkości, 17 917 okien) lub <=15 s (bilans czasu, 43 393 s IDZ = 12,1 h), przesunięcie <=6 pól (inaczej teleport/wypad).
* Rozróżniam tryby: **patrol** (okno w promieniu 400 s od zdarzenia `patrol_cel/patrol_wizyta`; 17 375 s = 4,8 h, głównie od 13.10 08:15) i **trasa** (pętla punktów, 11 do 12.10; 26 069 s = 7,2 h).
* Przyczynę okna przypisuję w kolejności: zmiana piętra w oknie, okno `pietra_start..pietra_krok` (-1,5 s / +2,5 s), postój patrolu (`patrol_wizyta.t - na_miejscu_s`), wypad, unikanie gracza, utknięcie/watchdog, ogień (z logów `[OGIEN] pola`, promień 3 pola, ważne 40 s), potwór <=2 pola, okolica schodów (<=3 pola od pola startu przejścia z `pietra_start`), luka >2,5 s, brak przyczyny.
* Sufit prędkości: czas kroku z minimapy (bajt prędkości pola * 0,047 s, jak `POSCIG_KROK_S_NA_PREDKOSC`). **To jest szacunek**: na polach o prędkości 12 mediana osiąga 1,67 pola/s (Manhattan) przy "suficie" 1,79, a p90 2,3, więc sufit jest zaniżony o ok. 20% (marsz po skosie liczony jako 2 pola Manhattan zawyża). Bilans straty poniżej jest więc przybliżeniem rzędu wielkości (+/- ok. 20% względnych), a ranking przyczyn jest odporny, bo wynika z liczenia czasu okien, nie z sufitu (zob. macierz 2.4).

### 2.2 Rozkład prędkości w IDZ (okna 0,9 do 1,6 s)

| zestaw | n | Czebyszew mediana / p95 | Manhattan mediana / p95 | stoi (czas) |
|---|---|---|---|---|
| wszystko, 11 do 14.10 | 17 917 | 0,91 / 2,00 | 1,33 / 2,31 | 14,3% |
| patrol | 7 207 | 0,91 / 2,14 | 1,43 / 2,50 | 23,3% |
| trasa (pętla) | 10 710 | 1,00 / 2,00 | 1,25 / 2,14 | 8,3% |
| patrol od 13.10, bez zmiany piętra | 6 068 | 0,91 / 2,14 | 1,54 / 2,50 | 24,9% |
| patrol od 13.10, "zwykłe odcinki" (bez schodów, postoju, walki, wypadu, utknięcia) | 2 869 | 1,00 / 2,31 | 1,67 / 2,50 | 19,4% |

Liczba pól na okno 1,2 s w "zwykłych" odcinkach trasy: 0:8%, 1:40%, 2:45%, 3:6%. Liczby z zadania (0,91; p95 2,2; 19%) odtwarzają się: to miara Czebyszewa na oknach patrolu.

Wartość odniesienia: poscig z trzymanym klawiszem `kroki_na_s`: mediana 1,31, p10 0,99, p90 1,71, max 2,16 (n=544); pościg stuknięciami 1,32 (n=95). Patrol w odcinkach zwykłych, Manhattan 1,54 do 1,67 (z marszem skośnym). Czyli **mediana trzymania klawisza i kliku jest ta sama**.

### 2.3 Kiedy i gdzie postać stoi (okna ze zerowym przesunięciem, udział w czasie STOJĄCYM)

Patrol (od 11.10, 1 691 okien bez ruchu):

| przyczyna | udział w postoju | uwaga |
|---|---|---|
| pietra.py manewr | 30,8% | 34,5% okien w manewrze to postój |
| "reszta" (marsz zwykły) | 32,6% | skupione przy schodach i ogniu, nie przy punktach patrolu (526 z 565 postojów jest >=10 s po `patrol_cel`, 514 bez widocznego potwora) |
| patrol rozglądanie/obchód | 25,7% | zamierzone |
| utknięcie/watchdog | 8,0% | |
| potwór <=2 pola | 1,5% | |
| ogon po walce/loot/jedzeniu/UH | 1,2% | tu walka i loot praktycznie nie istnieją jako przyczyna |

Trasa (pętla): 70,8% postoju to "reszta" (pojedyncze mikropostoje 1,2 s), 12,7% utknięcia, 5,8% schody, 4,3% unikanie graczy, 3,7% po lootcie.

**Długość postojów (serie kolejnych okien bez ruchu):** patrol 875 serii, mediana 1,3 s, p90 4,8 s, max 61 s, razem 2 100 s; 551 serii to pojedyncza próbka (1,2 s). Czas wg długości serii w patrolu: 1,2 s: 637 s; 2,4 do 3,6 s: 488 s; 4,8 do 8 s: 402 s; 8,5 do 20 s: 342 s; >20 s: 231 s. Trasa: 817 serii, mediana 1,2 s, p90 2,5 s, max 12 s, razem 1 207 s.

**Gorące punkty (komórki 4x4 pola, czas stania):** (z9, 32484..87, 32296..99) 527 s (35% IDZ w komórce), (z9, 32480, 32296) 408 s (67%), (z8, 32488, 32292) 271 s, (z8, 32476, 32268) 244 s (89%), (z8, 32368, 32192) 229 s, (z8, 32488, 32288) 227 s, (z8, 32492, 32288) 206 s, (z9, 32500, 32300) 179 s, (z9, 32508, 32276) 158 s (96%). 14 komórek = 60% całego postoju. Wszystkie leżą przy schodach (32482,32296), (32494,32289), (32476,32272), (32498,32270) albo łączniku (32506,32270 do 32502,32270). Piętra: z9 72 serie, z8 67, z7 26, z11 8 (postoje "reszta" w patrolu).

### 2.4 Bilans czasu IDZ w patrolu (od 13.10, 16 060 s = 4,46 h)

Rodzaje okien: ruch (>=1 pole w oknie <=2,5 s) 51,1%, stoi (0 pól, okno <=2,5 s) 13,3%, **luka >2,5 s między próbkami 29,3%**, okno ze zmianą piętra 6,3%. Luka >2,5 s to czas, w którym nie powstała żadna próbka (obiegi kończące się wcześniej niż `_tele_tick`, długie manewry, blokady); postać w tym czasie zwykle się porusza, ale wolno (np. 1 pole na 4 s przy schodach).

Macierz czasu wg przyczyny (patrol od 13.10, % czasu IDZ):

| przyczyna | ruch | stoi | luka >2,5 s | razem |
|---|---|---|---|---|
| ogień w pobliżu (<=3 pola) | 13,0 | 0,4 | 11,3 | 24,7 |
| pietra.py manewr przy schodach | 10,5 | 3,7 | 5,7 | 19,9 |
| okolica schodów bez manewru | 9,3 | 3,0 | 4,5 | 16,8 |
| patrol postój/obchód | 8,0 | 3,3 | 1,8 | 13,1 |
| mikroprzerwy ("marsz poniżej sufitu") | 8,8 | 0 | 0 | 8,8 |
| luka ticka bez zdarzenia | 0 | 0 | 3,9 | 3,9 |
| utknięcie/watchdog | 0,4 | 1,1 | 1,4 | 2,9 |
| postój 1 próbka bez przyczyny | 0 | 1,6 | 0 | 1,6 |
| potwór <=2 pola | 0,5 | 0,2 | 0,5 | 1,2 |
| unikanie gracza | 0,5 | 0 | 0,2 | 0,7 |

(zmiana piętra w oknie 6,3% poza tabelą.) Kolumna "razem" pokazuje czas, w którym działo się coś związanego z przyczyną, a nie stratę; rozkład straty jest w streszczeniu.

**Trasa (pętla, 11 do 12.10, starsza wersja kodu):** ruch efektywny 70%; strata 30%: luka ticka bez zdarzenia 7,1% czasu IDZ (844 luki po ok. 4,5 s, w większości 11 do 12.10 i znikają do 14.10: 236 s), mikroprzerwy 6,9%, pojedyncze postoje 3,5%, schody 4,0%, utknięcie 2,3%, unikanie gracza 2,2%.

### 2.5 Co dokładnie dzieje się przy ogniu i schodach

* Pola ognia z logów `[OGIEN] pola`: 5 878 wpisów (12.10: 104, 13.10: 4 820, 14.10: 954). Najczęstsze pola: (z8, 32480, 32294) 1 695 wpisów, (z8, 32491, 32289) 1 448, (z9, 32504, 32281) 1 306, (z9, 32504, 32280) 1 305, (z9, 32505, 32280/81) ok. 1 130, (z9, 32483, 32299) 1 047, (z9, 32483, 32298) 913, (z9, 32491, 32298) 853, (z8, 32481, 32294) 489. Wpis jest logowany najwyżej co 10 s (`OGIEN_LOG_S`), więc to godziny obecności: **to są pola stałe, nie jednorazowe pożary**.
* W minimapie część z nich ma flagę ściany (4: (z9, 32504, 32280/81), (z9, 32483, 32299), (z9, 32491, 32298), (z8, 32480, 32295)) albo flagę "bez drogi" (2: (z8, 32480, 32294), (z8, 32491, 32289)). Ogień na polu będącym ścianą wg mapy to prawie na pewno fałszywe wykrycie detektora (kolor pochodni/dekoracji), pole z flagą 2 to stałe pole magiczne albo przedmiot blokujący pathfinding.
* Maska pól stałych (`OGIEN_STALY=1`, `OGIEN_STALY_N=20` wykryć w >=600 s) uczy się od zera po każdym restarcie (53 sesje w 4 dni, mediana ok. 15 min), więc w krótkich sesjach rzadko jest rozgrzana. W `na_zywo.json` jest obecnie `OGIEN_STALY: 0` (maska wyłączona) i wszystkie 10 sesji 14.10 zaczęły z `OGIEN_STALY: 0`. Efekt: 82% straty przypisanej ogniowi (1 549 z 1 897 s) leży w promieniu 4 pól od schodów, a strata ogniowa wynosi 11,4% czasu IDZ przy `STALY=0` i 14,5% przy domyślnym (13.10, przed P6), czyli maska w obecnej postaci nie rozwiązuje problemu.
* Mechanizm straty: `_ogien_na_drodze` wyłącza klik (autowalk) na rzecz `_ogien_krok` = jeden krok na obieg z `krok_do`, A\* z ogniem jako przeszkodą (`_ogien_blok`), a `_ogien_wyjdz` kończy obieg wcześnie (bez próbki, stąd luki). Koszt jednego kroku w tym trybie to krok klienta (0,45 do 0,75 s) + `sleep(0.02..0.12)` + pauza po ticku + RPC, szacunkowo 1,0 do 1,5 s zamiast 0,55 s na pole przy kliku.
* Schody: 57% celów patrolu wymaga przejścia pięter. Wizyta bez schodów: 0,55 s/pole; ze schodami (bez walki): 0,85 s/pole (n=52, +55%); jedno przejście dodaje ok. 6 do 8 s ponad czas marszu. 2 656 startów `pietra_start`, 2 343 `pietra_krok` (czas_s średnio 0,70 s, p90 3,2 s, razem 1 649 s = 27 min), 296 `pietra_blad: porazka` (11% startów). Wizyty: 591, z czego 82 (14%) nieudane/przerwane (65 "zmiana celu po walce").
* Z logu 12:36:40 do 12:36:50 (14.10): 8 prób "ustawiam się ortogonalnie ze schodami (32482,32296): krok Up z (32483,32297,9)" przez 8 s zanim "nie dochodzę na pole... pomijam" i dopiero próba R działa. Dokładnie to jest "pod przejściem pięter": ok. 10 s stania w jednym miejscu.

### 2.6 Tick: jak często, ile trwa

* Okres ticku w IDZ: średni nadmiar odstępu próbek ponad 1,0 s = 0,39 s (mediana 0,30; p95 1,20). Dla stałego okresu T nadmiar ma średnią T/2, więc T ok. 0,78 s. W WALKA odstępy są krótsze (30% w 1,1 s), w IDZ 12% w 1,0 s, 16% w 1,1 s, ogon do 3 s (5,8% >=3 s).
* Z kodu: tick z kliknięciem = RPC (gracz, pozycja, stwory z cache, zrzut ppm ognia 40 + 20 ms) + klik 0,30 do 0,45 s + `pauza(0.15, 0.3)` + `pauza_po_ticku` 0,05 do 0,15 s = ok. 0,7 do 1,0 s. Tick "postać idzie sama" (klik w toku) = RPC + `pauza(0.08, 0.18)` + 0,05 do 0,15 s = ok. 0,3 do 0,45 s. Zgodne z estymacją.
* "wolny tick" (próg 2 s, najwyżej raz na 30 s, więc to próbka): 85 wpisów w 4 dniach (12.10: 49, 11.10: 12, 13.10: 11, 14.10: 13). Najdłuższa faza: `gracz` 60 razy (1,5 do 3,4 s; rdzeń: pełny skan bloku gracza trwa 1 do 2 s i "blokuje strażnika", rdzen.py:641), `stwory` 13 razy (2,1 do 3,1 s, rdzen.py:455 "zapytanie czekające na zamek blokuje WSZYSTKIE inne"), `telemetria` 12 razy (1,7 do 1,8 s), w kilku wpisach 4,3 do 5,0 s przy zerowych trzech zmierzonych fazach, czyli czas w niemierzonym odcinku (leczenie, ogień, jedzenie, UH).
* Decyzje modelu (2 888 "Decyzja", mediana 5,2 s, razem 4,0 h) idą w osobnym wątku i **nie spowalniają ticku** (gęstość próbek w oknach decyzji i poza nimi taka sama: 1,52 vs 1,59 s). Kilka luk pokrywa się z końcem decyzji tylko przypadkowo.

### 2.7 Wnioski z pomiarów

1. Ruch po prostych jest płynny. Jedyny mierzalny koszt ścieżki klikowej to mikroprzerwy: 1,5% do 3% (patrol), 7% do 11% (trasa, stary kod) czasu IDZ.
2. 51% straty w patrolu to klaster schody plus ogień przy schodach, czyli sposób **przechodzenia przez miejsca zmiany poziomu**, nie technika chodzenia. Naprawa samego kliku/trzymania klawisza nie ruszy tej części, chyba że wykonawca obejmie także podejście do schodów.
3. Postój "rozglądam się" to 7,3% czasu IDZ i 14% straty. Zostaje bez zmian (freestyle). Można go tylko zrobić mniej "martwym" (np. rozglądanie obrotem postaci), ale to kosmetyka.
4. Walka i loot nie są istotną przyczyną postoju w IDZ.

## 3. Rekomendowana kolejność prac

| etap | zakres | oczekiwany zysk (szacunek, % czasu IDZ w patrolu) | ryzyko |
|---|---|---|---|
| E0 | Telemetria ruchu: nowy rekord `ruch_okno` co 30 s (zob. 6.1), znacznik przyczyny postoju w `_tele_tick` | 0 (pomiar) | minimalne |
| E1 | Maska ognia stałego z mapy i z pliku (zob. 4.4), rzadsze re-kliki, nieblokujące `krok_do`, wcześniejsza próbka w obiegach `return True` | 4 do 8 | niskie |
| E2 | Wykonawca `PLYNNY_RUCH` (rozdział 4), najpierw tylko odcinki zwykłe i obchód, potem dojście do schodów | 3 do 6 dodatkowo (łącznie z E1 ok. 8 do 14 z 51% straty) | średnie (klawisz trzymany) |

Zyski są szacunkami: założenie, że ok. 50% straty ogniowej, 30% okołoschodowej i 60% mikroprzerw da się odzyskać. Realnie wyższą wartością niż "szybsze pole/s" jest skrócenie cyklu wizyty (dojście + postój), czyli więcej wizyt na godzinę przy tym samym losowaniu miejsc.

## 4. Projekt wykonawcy PLYNNY_RUCH

### 4.1 Założenia

* **Wybór celów patrolu, losowanie, wagi, postój i obchód są nietknięte.** Wykonawca dostaje gotowy odcinek A\* (`p["seg"]`) i tylko go przechodzi; `_patrol_wybierz`, `_patrol_dotarl`, `PATROL_POSTOJ`, `PATROL_OBCHOD_P` zostają.
* Walka, pościg (`poscig_szybki`), loot, leczenie, UH, jedzenie, pochodnia, wypad do depo, unikanie graczy: bez zmian. Wykonawca działa tylko w ticku, który i tak kończy się `idz()`, czyli po wszystkich wyższych priorytetach.
* Pokrętło `PLYNNY_RUCH` (0/1/2) w `na_zywo.json`, domyślnie 0. 1 = tylko odcinki zwykłe, 2 = także dojście do schodów i obchód. Zmiana w locie ma natychmiast puszczać klawisze.

### 4.2 Algorytm (jedna "seria marszu" w ramach jednego ticku)

Wejście: `_idz_segment(seg, idx)` przy `PLYNNY_RUCH>=1`, warunki startu: brak potwora (kandydata) w `ZASIEG_X`/`ZASIEG_Y` widoku, brak GRACZ-a groźnego, HP powyżej progu + margines (jak `poscig_wejscie`, cavebot.py:4003), nie ucieczka, brak wykrytego ognia w następnych 6 polach odcinka, brak nowego kroku pietra w następnych 2 polach (tam przejmuje `pietra.py`).

1. **Plan lokalny**: z `seg[idx:]` wybierz do `MARSZ_ZASIEG` (np. 8 pól) pól do przodu zatrzymując się przed (a) polem zmiany piętra (`pole_zmiany_pietra`), (b) polem ognia, (c) polem zajętym przez stwora, (d) końcem odcinka. Z planu wylicz listę kierunków osiowych (skosy tylko na rogach, jak `_poscig_skos`/`POSCIG_SKOS_AWARYJNY`).
2. **Pętla trzymania (wzór `poscig_szybki`, cavebot.py:4254)**: `postac.trzymaj_kierunek(dx,dy)` dla bieżącego kierunku; co obieg `postac.puls()`; pozycja z lekkiego RPC (`poscig`/`pozycja`, jak `_odczyt_poscig` 4090); decyzję o następnym kierunku podejmuj dla pola Q, na którym skończy się krok w toku (tak jak `_poscig_decyzja` 4149), więc zakręt jest naciśnięty jeszcze w trakcie kroku (`POSCIG_ANTYCYPACJA`, `zmien` bez luki); na prostych zostaje ten sam klawisz (jeden `KeyPress`).
3. **Wyprzedzające podawanie celu**: w trakcie marszu przesuwaj okno planu (dokładaj kolejne pola z `seg`), żeby następny kierunek zawsze był znany o 2 do 3 kroków wcześniej; nie czekaj na koniec odcinka.
4. **Przegląd co `MARSZ_PRZEGLAD` (1,0 s, jak `POSCIG_TRZYMAJ_PRZEGLAD`)**: `gracz()` (HP) i `stwory(0.8)` w czasie trwania kroku (`_poscig_przeglad`, 4030), zrzut ognia (`_ogien_tick` w wątku/pętli) i sprawdzenie HP. Wyjście z serii (puść klawisz, wróć do pełnego ticku) gdy: potwór kandydat w widoku w zasięgu `MARSZ_STOP_POTWOR_R` (jak `TRASA_STOP_PRZY_POTWORZE_R`), HP spadło o `POSCIG_HP_SPADEK`, `_zdrowie_gotowy`, obcy gracz groźny, nowe pole ognia w oknie planu lub pod nami, `_poscig_przerwanie()` (pauza mózgu/rozmowa), plik STOP, `Zatrzymano`, brak zmiany pozycji przez `POSCIG_BRAK_ZMIANY`(0,45 s) po ponowieniu, oscylacja (`POSCIG_OSCYLACJA_*`), limit okna `MARSZ_OKNO_MAX` (12 s jak `POSCIG_TRZYMAJ_OKNO_DOBRY`).
5. **Koniec serii**: dojście do końca planu, następnie powrót do `_idz_patrol`, który i tak ma własne fazy. Krok przed polem docelowym (`PATROL_PRZYJECIE=1`) puszczamy klawisz zanim postać wejdzie w pole zmiany piętra, żeby `pietra.py` nie dostał postaci "w pędzie".
6. **Rozglądanie się w trakcie marszu** (opcjonalnie, `MARSZ_ROZGLADANIE_P`, domyślnie 0): z małym p krótkie (0,2 do 0,6 s) puszczenie klawisza w losowym punkcie odcinka dłuższego niż 12 pól, tylko przy braku potworów. Pokrętło służy zachowaniu "ludzkiego" rytmu.
7. **Dojście do schodów (poziom 2)**: zamiast `_na_start` (pietra.py:276) z pojedynczymi krokami i 8 próbami, wykonawca prowadzi aż do pola `wejscie_gora/wejscie_dol` w jednej serii, z hamowaniem na ostatnim polu (puść klawisz, `pietra.py` robi krok na schody/`R`). Szczegóły przejścia pozostają zadaniem A.
8. **Ogień**: zamiast `_ogien_krok` (jeden krok na obieg) plan omija pola ognia (A\* z `_ogien_blok` już to robi), seria trwa ciągle; pole ognia wykryte na planie kończy serię PRZED wejściem (sprawdzenie pól Q i Q+1 przy każdej decyzji).

### 4.3 Miejsca w kodzie do zmiany (propozycja, nic nie zmieniam)

| plik | funkcja | zmiana |
|---|---|---|
| cavebot.py | nowe pokrętło `PLYNNY_RUCH` i stałe `MARSZ_*` (obok `POSCIG_TRZYMAJ*`, ok. 404), wpis w mapie pokręteł `na_zywo.json` | nowe |
| cavebot.py | nowa metoda `marsz_plynny(seg, idx, poz)` obok `poscig_szybki` (4254); współdzieli `_poscig_decyzja`, `_poscig_stabilny`, `_pole_zablokowane`, `_poscig_puszcz`, `_poscig_przeglad` | nowe, kopiuje szkielet pętli trzymania bez logiki celu |
| cavebot.py | `_idz_segment` (6657): przy `PLYNNY_RUCH` najpierw `marsz_plynny`, wynik `None` = stary `_idz_trasa` | warunkowe wywołanie |
| cavebot.py | `idz_do` (2676): nie ponawiaj kliku co `KLIK_PONOW`, gdy poprzedni cel jest nadal przed nami i pozycja się zmienia (E1) | mała zmiana |
| cavebot.py | `_ogien_krok` (2298) / `_ogien_na_drodze` (2167): maska stałych pól z mapy (flaga 2 lub 4) i z pliku `trasy/ogien_stale.json` ładowanego na starcie (E1) | rozszerzenie |
| cavebot.py | `tick` (2956): `_tele_tick` przed wczesnymi `return True` albo osobna próbka `ruch` (E0) | telemetria |
| bot.py | `Postac.krok` (205): wersja nieblokująca / skrócony `CZAS_KROKU` z wcześniejszym powrotem po zmianie pozycji, brak 1,5 s na nieudany kierunek (E1) | mała zmiana |
| klawisz_x11.py | bez zmian (jest `trzymaj_kierunek`, `zmien`, `puls`, `puszczaj`, watchdog) | brak |
| pietra.py | `_na_start`, `_dojdz` (276, 320): przekazanie dojścia wykonawcy (poziom 2), `START_RUCHY_MAX` | poziom 2 |
| wypad.py | `_dziura/_drabina/_drzwi`: bez zmian na starcie (własne przejścia) | brak |

### 4.4 Naprawy E1 bez nowego wykonawcy (mogą dać część zysku od razu)

1. Przywrócić `OGIEN_STALY=1` i dodać zasiew maski: pola ognia, które mapa oznacza jako ściany (flaga 4) lub BEZ_DROGI (flaga 2) oraz najczęstsze pola z 5 878 wpisów (lista w 2.5), zapisywane do pliku między sesjami (`ogien_stale.json`). Najpierw ręcznie zweryfikować na zrzucie, czy (z8, 32480, 32294) i (z8, 32491, 32289) to prawdziwy ogień czy detektor.
2. Zaprzestać ponawiania kliku do tego samego celu co 1,5 s, gdy pozycja się zmienia (każdy re-klik to 0,3 do 0,45 s kursora i restart autowalku w kliencie).
3. W `Postac.krok` kończyć czekanie po zmianie pozycji natychmiast (jest) i nie czekać pełnych 1,5 s na kierunek, który wg mapy jest wolny; po pierwszej porażce w kierunku od razu próbować następny.
4. Próbka telemetrii przed wczesnymi `return True` w `tick`, żeby luki nie zasłaniały obrazu.

## 5. Ryzyka i jak je ograniczyć

| ryzyko | zabezpieczenie |
|---|---|
| Trzymany klawisz po wyjątku/zabiciu procesu | już jest: `finally: _poscig_puszcz()`, atexit/sygnały, watchdog 0,6 s, wartownik, `TRZYMANIE_MAX_S`; nowa metoda MUSI używać tego samego wzorca try/finally i `puls()` w każdym obiegu pętli (także w przeglądzie, jak `puls=True` w `_poscig_przeglad`) |
| Wejście w ogień | sprawdzenie Q i Q+1 przy każdej decyzji; ogień z zrzutu w pętli co <=0,8 s; po wejściu `_ogien_wyjdz` jak dotąd |
| Wejście w pole zmiany piętra "w pędzie" | `_pole_zablokowane` (zawiera `pole_zmiany_pietra`) w planie; hamowanie na polu przed schodami; pietra.py dostaje postać w spoczynku |
| Potwór/gracz pojawia się w trakcie serii | przegląd co 1,0 s plus nasłuch `_poscig_przerwanie`; wyjście z puszczeniem klawisza, walka w następnym ticku jak dotąd; limit `MARSZ_OKNO_MAX` 12 s |
| Rozjazd mapy i świata (ściana wg mapy, stwór nie widoczny) | licznik braku zmiany pozycji + ponowienie 1 raz (`POSCIG_PONOW_BRAK`), potem wyjście do starego `_idz_trasa`; nauka ścian jak `krok_prosto_ost` |
| Oscylacja przy zakrętach | `_poscig_stabilny` (ping-pong, histereza) i `POSCIG_OSCYLACJA_*` |
| Przekroczenie zasięgu widoku (klik poza widokiem trafia w panel) | trzymanie klawisza nie klika, więc ryzyko znika; do hamowania i planu nie używać kliku |
| Zmiana zachowania "ludzkiego" (wykrywalność) | zachować losowe `POSCIG_PO_KROKU`, `POSCIG_ZAWAHANIE`, opcjonalne rozglądanie; wizyty, postoje i obchody bez zmian |
| Konflikt dwóch trybów ruchu (klik w toku i klawisz) | przed startem serii `zatrzymaj_klik(poz)` (Escape) jak w `pietra._proba` |
| Wolne RPC `gracz` 2 do 3 s w środku serii | przegląd w serii nie blokuje klawisza (puls), a przy braku świeżych danych >2,5 s seria się kończy; to samo dla `stwory` |

## 6. Testy atrapami i metryki

### 6.1 Testy

* Atrapy: `testy/zapytaj.py` (RPC), `postac` z `trzymaj_kierunek/trzymany_kierunek/puszczaj/puls` jak w `test_poscig_przechwyt.py`, `klawisz_x11` z `ZEGAR` i `RETRONIC_TESTY=1` (bez wartownika, jak w `test_klawisz_x11.py`).
* Przypadki: (1) prosty odcinek 8 pól: jeden `KeyPress`, brak puszczeń pośrednich, zakręt w trakcie kroku bez luki; (2) potwór pojawia się w polu planu: klawisz puszczony w <=1,0 s; (3) pole ognia pojawia się 3 pola przed nami: stop przed ogniem; (4) wyjątek w środku serii: `finally` puszcza klawisz (asercja na `trzymany_kierunek()==None`); (5) brak `puls()` przez 0,7 s: watchdog puszcza; (6) odcinek kończy się polem zmiany piętra: seria kończy się pole wcześniej, klawisz puszczony; (7) brak zmiany pozycji (ściana): ponowienie raz, potem wyjście do `_idz_trasa`; (8) `PLYNNY_RUCH=0`: wyniki identyczne jak dziś (regresja `test_patrol.py`, `test_wielopietrowa.py`, `test_ogien.py`, `test_trasa_stop_potwor.py`); (9) zmiana pokrętła w locie na 0 puszcza klawisze; (10) replay: przepuścić zapisane odcinki `patrol_cel` + mapę przez planer i porównać liczbę zmian kierunku z `kroki` w `poscig_koniec`.
* Test integracyjny na żywo dopiero po przejściu atrap: krótka sesja 20 min w jaskini z `PLYNNY_RUCH=1`, obserwacja `ruch_okno` i logu, bez zbliżania się do depo.

### 6.2 Nowy rekord telemetrii `ruch_okno` (E0)

Co 30 s w IDZ: `czas_marszu_s`, `czas_stoi_s`, `pola_osiowe`, `pola_skos`, `kliki`, `klawisze_zmiany`, `ticki`, `tick_med_s`, `tick_p95_s`, `postoj_s` rozbity na przyczyny kodowane w kodzie (`schody`, `ogien`, `postoj_patrolu`, `utkniecie`, `krok_nieudany`, `rpc_wolne`, `inne`), `luki_gt25_s`. Pozwala porównać 1 h z 1 h bez zgadywania z próbek co 1,2 s.

### 6.3 Metryki do porównania 1 h kontra 1 h

Losowanie miejsc zostaje, więc porównujemy znormalizowane wskaźniki, nie surowe liczniki. Minimum 3 godziny na ramię, naprzemiennie (np. 1 h PLYNNY_RUCH=0, 1 h =1, powtórzone), ta sama trasa/miejsca, bez wyprawy do depo w oknie (albo osobno).

1. **Efektywność marszu** = pola przebyte / (czas IDZ bez postoju patrolu). Cel: z ok. 49% do >=60%.
2. **s na pole** w wizytach bez walki: osobno bez schodów (dziś 0,55 mediana) i ze schodami (0,85). Cel schodów <=0,70.
3. **Udział czasu stania** (okna 0 pól) w IDZ bez postoju patrolu: dziś 13% stoi + 29% luk w oknach. Cel: stoi <=8%, luki <=12%.
4. **Czas dojścia na wizytę** (`patrol_wizyta.dojscie_s` / `patrol_cel.droga`, tylko `zabicia_droga=0`) i **wizyty/godz.** (dziś ok. 17 na godzinę IDZ).
5. **Czas na postój przy schodach** (suma serii postoju w komórkach przy schodach, pkt 2.3) i **liczba prób** `pietra_krok.proba` (>1) oraz `pietra_blad`.
6. **Strata ogniowa** (czas okien z ogniem <=3 pola / czas IDZ): dziś 11,8%.
7. **Bezpieczeństwo (muszą nie pogorszyć się)**: `utkniecie`, `watchdog_bezczynnosc`, `pietra_blad`, zgony/ucieczki (`zdrowie`, `uciekanie`), HP min na godzinę, liczba wejść w ogień (`[OGIEN] stoję na ogniu`), `wolny tick`, liczba puszczeń przez watchdog klawiszy (`WATCHDOG_PUSZCZENIA`).
8. **Wynik gry**: zabicia/godz. i exp/godz. (ostatni miernik, bo zależy od losowania miejsc i gęstości potworów).

## 7. Niepewności i czego nie wiem

* Telemetria co 1,2 s nie widzi postojów <1 s ani dokładnego momentu kliku/klawisza; dlatego E0 jest pierwszym krokiem. Okres ticku podałem jako estymację (ok. 0,78 s), nie pomiar.
* Sufit prędkości (bajt minimapy * 0,047 s) jest przybliżony i zaniżony o ok. 20%; procent efektywnego marszu (ok. 49%) może być o kilka punktów inny, ale ranking przyczyn i udziały czasu okien (2.3, macierz w 2.4) od niego nie zależą.
* Przypisanie przyczyn jest hierarchiczne (zmiana piętra, manewr, postój, wypad, unikanie, utknięcie, ogień, potwór, schody, luka); przy nakładaniu (ogień przy schodach: 82%) czas trafia do pierwszej pasującej kategorii, więc "ogień" bez schodów jest zaniżony względem "ogień przy schodach".
* Nie wiem, czy pola (z8, 32480, 32294) i (z8, 32491, 32289) to prawdziwy trwały ogień czy fałszywe wykrycie. Pola z flagą ściany w minimapie na pewno są fałszywe. Trzeba obejrzeć zrzut.
* Zachowania klienta (OTClient/wine, binarka bez źródeł) przy re-klikaniu w trakcie autowalku nie da się potwierdzić z telemetrii; hipoteza, że re-klik co 1,5 s do tego samego celu powoduje mikroprzerwy, jest tylko rozsądnym podejrzeniem (mikroprzerwy to w patrolu 1,5% do 3% czasu IDZ).
* Luki >2,5 s w trybie trasa 11 do 12.10 (7% czasu) zniknęły w kodzie z 14.10 (236 s); nie ustaliłem, która zmiana to naprawiła. Wolne RPC `gracz`/`stwory` (rdzeń jednowątkowy, pełne skany 1 do 2 s) pozostają ryzykiem dla każdego wykonawcy.
* Dane patrolu to ok. 4,5 h IDZ (591 wizyt); wnioski dla rzadkich schodów (np. (32476,32272), (32498,32270)) opierają się na kilkudziesięciu zdarzeniach.
* Równolegle ktoś zmieniał kod (pietra.py zmieniony w ostatnich 90 min przed analizą, bot aktywny od 13:27 14.10): dane z 14.10 po południu mogą już odzwierciedlać nowszą logikę przejść pięter (zadanie A).
