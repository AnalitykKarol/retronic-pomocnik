# Analiza prędkości pościgu (11.10.2026, dane 13:13-15:59)

Tylko odczyt: zero zmian w kodzie, zero inputu do gry. Źródła: `telemetria-20261011.jsonl` (605 zdarzeń `poscig_koniec`, z czego 153 z pełną ścieżką krok po kroku `sciezka`, od 14:41), `rdzen-skan.log`, `mozg-*.log` (log "strażnik puścił"), `poscig-wnioski.jsonl`, `pomoc-karola.jsonl`, kod (`cavebot.py`, `rdzen.py`, `klawisz_x11.py`, `ekran.py`). Dodatkowo 12 zapytań RPC zmierzonych na żywo. Skrypty liczące: scratchpad sesji (`krok.py`, `rozbicie2.py`, `rpc.py`). Numery linii są z 15:57 i dryfują, bo `cavebot.py` jest teraz edytowany przez inne agenty.

## 0. TL;DR

1. **Postać biegnie z mniej więcej maksymalną prędkością, kiedy w ogóle biegnie** (mediana odstępu między krokami = 1,0x teoretycznego kroku pola), ale **sprawność całego pościgu to ok. 77%** teoretycznego tempa w pętli i tylko **ok. 54% w epizodzie** (z lukami między pętlami: 0,82 kroku/s wobec 1,52 możliwego na tym spocie).
2. **Najtańszy duży zysk jest w rdzeniu, nie w cavebocie**: każde zapytanie RPC (`gracz`, `pozycja`, `poscig`, `stwory`) robi pełny skan `/proc` (`rdzen.py:624` -> `podlacz()` -> `znajdz_gre()` -> `potomkowie()`), **ok. 65-70 ms** z ~80-90 ms całego RPC. To 2-3 RPC na tick (0,25 s), 1 RPC na obrót pętli pościgu (0,12 s) i 2 RPC na przegląd (0,17 s, a ten blokuje pętlę i wyzwala strażnika klawiszy).
3. **Klawisz nie jest wciśnięty przez 27% czasu pętli** (`trzymane_s/czas` = 0,73). Przyczyny wg danych: strażnik klawiszy 0,6 s (51 puszczeń przy 227 pościgach w trybie trzymaj), puszczenie klawisza przed ostatnim krokiem ("ostatni"/"zajete") i wynikający z tego timeout `brak_zmiany` 0,8 s (`ponow_brak` 97 razy), kliki Alt (blokują pętlę 0,35-0,6 s, już wyłączone przez `ATAK_TYLKO_PRZY_CELU`).
4. **Szczur ucieka z ok. 0,85 pola/s** (Chebyshev, mediana 0,88), my w pościgu średnio 1,26 pola/s, więc **prędkość zbliżania to tylko ok. 0,4 pola/s**. Maksimum na tym spocie 1,5 pola/s dałoby 0,65 pola/s, czyli ok. 1,6x szybsze dogonienie. Każdy +1% naszej prędkości to ok. +2,5% prędkości zbliżania, dlatego "dużo za wolno" jest odczuwalne bardziej, niż wynika z samych procentów.
5. Skręty o 90 stopni **nic nie kosztują** (0,96x kroku). Kosztują: stalle w prostej linii (36% kroków w tym samym kierunku trwa >1,3x kroku), niezamierzone skosy i start pętli.

## 1. Teoretyczna prędkość a faktyczna

### 1.1 Teoria

Prędkość kafla z `mapa.pole()[2]` (jednostka x10 = prędkość podłoża). Czas kroku mierzony z odstępów między przyjściami na kolejne pole (`sciezka`, tylko kroki proste, n=350):

| v kafla | % kroków na spocie | `0,047*v` (kod) | mediana odstępu | p10 | p90 | średnia |
|---|---|---|---|---|---|---|
| 12 | 61% | 0,56 s | 0,60 s | 0,42 | 1,31 | 0,74 |
| 14 | 7% | 0,66 s | 0,65 s | 0,54 | 1,52 | 0,94 |
| 16 | 17% | 0,75 s | 0,74 s | 0,61 | 1,63 | 0,97 |
| 20 | 15% | 0,94 s | 0,96 s | 0,80 | 1,69 | 1,17 |

- Stała `POSCIG_KROK_S_NA_PREDKOSC = 0.047` jest dobra (mediana/teoria 0,98-1,06). Zgadza się też z modelem serwera `ceil(1000*10v/230 / 50)*50` dla level 6 (speed 230): 0,55 / 0,65 / 0,70 / 0,90 s, plus ok. 0,03-0,05 s opóźnienia detekcji z pętli.
- **Maksimum na tym spocie: średni teoretyczny krok 0,657 s = 1,52 kroku/s** (najlepiej 1,8/s na samych polach v12, najgorzej 1,06/s na v20).
- Krok po skosie: ruch następuje od razu, a koszt płaci się PO nim (kolejny krok po skosie czeka ok. 2,3x kroku prostego: mediana 2,32, p90 2,68, n=15; wartości 1,33 s dla v12 wobec 0,58 s po prostym). `POSCIG_SKOS_KOSZT = 3.0` ("niezmierzony") jest za wysoki, realnie ok. 2,0-2,4 (`sonda_skosu.py` nigdy nie była uruchomiona, brak pliku `sonda-skosu-*.json`, brak `kalibracja-*.json`).

### 1.2 Faktyczne tempo

| tryb | pościgów | kroki | czas | kroki/s | uwagi |
|---|---|---|---|---|---|
| trzymaj (od 14:27) | 235 | 719 | 615 s | **1,17** | lat_med 0,39 s, dec_med 0,001 s, odrzucone 0 |
| stuk / starsze | 146 | 346 | 327 s | **1,06** | 29,5% wysłanych klawiszy bez zmiany pozycji (145/491), dec_med 0,11 s, lat_med 0,27 s |
| po naprawie skanu (od 15:30) | 83 | | | 1,28 | |
| w epizodzie (z lukami między pętlami, od 14:30) | 94 epizody | 751 | 916 s | **0,82** | luki 265 s (29%) |

Sprawność kroków (teoria/rzeczywistość, 153 pościgi ze `sciezka`): **0,77** (mediana na pościg 0,90, p10 0,69, p90 1,09).

### 1.3 Rozkład czasu pościgu (153 pościgi trzymaj, 463 s, średnio 3,0 s, mediana 2,3 s)

| ogniwo | s | udział | na pościg |
|---|---|---|---|
| idealny bieg (suma teoretycznych kroków) | 252 | 54% | 1,65 s |
| nadmiar odstępów ponad teorię (stalle) | 88 | 19% | 0,57 s |
| czas do PIERWSZEGO kroku (mediana 0,33 s, p90 0,54 s) | 59 | 13% | 0,39 s |
| ogon po ostatnim kroku do wyjścia (mediana 0,0, p90 1,5 s: okno/gryzący/brak_ruchu) | 65 | 14% | 0,42 s |

Nadmiar 88 s, rozbity wg klasy kroku:

| klasa interwału | n | mediana/teoria | udział >1,3x | nadmiar |
|---|---|---|---|---|
| ten sam kierunek | 152 | 1,02 | **36%** | **40 s** |
| skręt 90 stopni | 82 | 0,96 | 16% | 7,6 s |
| po skosie (koszt skosu) | 15 | 2,32 | 100% | 13,6 s |
| wejście w skos | 16 | 0,99 | 38% | 3,8 s |
| zawrót 180 stopni | 2 | 1,97 | 100% | 1,3 s |
| pozostałe (pierwsze interwały) | | | | ok. 21 s |

Stalle w prostej linii mają wyraźny wzór: **przy odległości do celu 2 pola stoi 61% takich kroków**, przy 3-6 polach 7-22%. Trwają 1,5-2,5x kroku (0,85-1,4 s), czyli tyle co `POSCIG_BRAK_ZMIANY`/`BRAK_WSPOL` (0,8 s) plus ponowne naciśnięcie. To pasuje do puszczania klawisza przez `_poscig_decyzja` ("ostatni": krok w toku kończy się przy celu, `cavebot.py:2027`; "zajete": pole po drodze zajmuje inny szczur, `:2047`), po którym krok w toku nie dochodzi do skutku i pętla czeka na `brak_zmiany`. To jest hipoteza mocno poparta rozkładem, ale nie licznikiem (patrz plan pomiaru).

### 1.4 Ile pościg stoi, a ile biegnie

- Klawisz wciśnięty przez 73% czasu pętli (tryb trzymaj, 560 s). 27% czasu to: start (0,33 s), puszczenia, stalle.
- Pościg to tylko ok. 13% czasu sesji (1254 s z ok. 9900 s), ale to ten czas decyduje o dobiciach: po 14:30 dobicie ("odl<=1" lub "cel_martwy") w 139 z 249 pościgów (56%). Skuteczność silnie zależy od odległości startowej: odl 2: 75%, odl 3: 51%, odl 4: 27%, odl 5: 33%, odl 6-7: 38-50%.
- Zbliżanie: szczur ok. 0,85 pola/s, my 1,26 pola/s w pościgach >=5 kroków. Różnica 0,4 pola/s. Dla odległości startowej 4: 10 s teraz, ok. 6 s przy 1,5 pola/s.
- Geometria jest dobra: 95% kroków zmniejsza dystans Manhattan do aktualnej pozycji celu (343 z 362). Straty to czas, nie droga.

## 2. Pętla: ile trwa obrót i co w nim siedzi

### 2.1 RPC (pomiar na żywo, 12 prób każde, bot działał)

| zapytanie | mediana | p90 | max |
|---|---|---|---|
| `pozycja` | 0,091 s | 0,154 | 0,176 |
| `gracz` | 0,076 s | 0,161 | 0,183 |
| `stwory` (maks_wiek 0,8, trafienie w cache) | 0,080 s | 0,157 | 0,309 |
| `stwory` (maks_wiek 0, świeży skan) | 0,462 s | 0,539 | 0,885 |

Rozkład kosztu: `potomkowie()` skanuje `/proc` (427 procesów, ok. 66 ms zmierzone osobno, `znajdz_gre()` 70 ms) przy KAŻDYM zapytaniu (`rdzen.py:624`), a sam `pread` pozycji to ułamek milisekundy. Czyli **ok. 80% czasu RPC to marnotrawstwo**. Plus osobne połączenie UNIX i JSON na każde zapytanie (`bot.py:43`).

### 2.2 Skan stworów (rdzen-skan.log)

| okres | szybki skan (regiony) | pełny skan |
|---|---|---|
| 13:03 | 0,23-0,29 s (2) | 1,0-1,2 s |
| 13:30-15:29 | 2,1-3,1 s średnio (12 regionów, bug zagnieżdżonych zakresów) | 1,05-1,2 s |
| 15:30-15:59 | **0,55-0,60 s (3 regiony)**, max 0,7-1,5 s | 1,25-1,45 s |

Po naprawie z 15:29 szybki skan to nie 0,1-0,2 s, tylko ok. 0,55 s (3 regiony). Pełny skan co ok. 3,5 s, gdy w pamięci nie ma stworów poza graczem (`OKRES_PELNEGO_PUSTO = 2.0` + 1,3 s skanu): nowy szczur wchodzący w widok jest wykrywany średnio po ok. 1,7 s. "wolny tick" do 15:29: 9 wpisów, `gracz` mediana 0,53 s (max 6,6 s, kolejka za zamkiem skanu), `stwory` mediana 1,6 s (max 4 s); po 15:29: jeden (4,3 s, tuż po przeładowaniu).

### 2.3 Składniki obrotu pętli pościgu (tryb trzymaj, `poscig_szybki`)

| element | koszt | gdzie |
|---|---|---|
| `spij(POSCIG_POLL)` | 0,02-0,035 s | `cavebot.py:128`, `:2265` |
| RPC `poscig` | ok. 0,09 s (z tego ok. 0,07 `/proc`) | `_odczyt_poscig` `:1958` |
| `puls()` | ms | `klawisz_x11.py:305` |
| A* + decyzja (`_poscig_decyzja`, `mapa.py`) | `dec_med` 0,001 s (p100 0,07 s) | `:2017` |
| przegląd co 0,6 s: `gracz()` + `stwory(0,8)` | 2 RPC = 0,16-0,45 s, **blokuje** pętlę | `:1912`, `POSCIG_TRZYMAJ_PRZEGLAD` `:138` |
| `ponow_atak`/`atak` (Alt+klik, `ekran.py:160-260`) | 0,35-0,6 s blokady (ruch 3-6x8-25 ms, +30-90, Alt 40-90, trzymanie 40-110, +30-70, +50-150) i nowe `Display()` | `:1809`; teraz wyłączone przy odl>1 przez `ATAK_TYLKO_PRZY_CELU` (`:61`) |
| `pauza(POSCIG_PO_KROKU/ZAWAHANIE)` | 0,045 s średnio + 6% x 0,35 s (tylko stuk) | `:129-131`, `:2395` |

Obrót w trybie trzymaj: ok. 0,12-0,13 s (granularność detekcji kroku), a z przeglądem do 0,4-0,7 s. Nie jest to wąskie gardło dla samego marszu (klawisz trzymany), ale opóźnia decyzje przy zakręcie, start i wykrycie ucieczki.

Obrót `tick()` (między pościgami): `gracz` + `pozycja` + `stwory` = 3 RPC (0,25 s), plus `pauza(0.05, 0.15)` po każdym ticku (`cavebot.py:3530`, `mozg.py:2317`), czyli minimum ok. 0,35 s. Zgadza się z lukami: mediana luki po wyjściu "okno" 0,65 s, p25 0,4 s, minimum 0,2-0,3 s.

Pierwszy krok po wejściu w pętlę: 0,33 s mediana (RPC `poscig` 0,09 + naciśnięcie + `spij` 0,03 + RPC 0,09 + opóźnienie klienta/serwera ok. 0,05-0,1).

### 2.4 Strażnik klawiszy

`WATCHDOG_S = 0.6` (`klawisz_x11.py:56`). 51 komunikatów "strażnik puścił ... (brak pulsu pętli > 0.6 s)" w logach 14:27-15:47, przy 227 pościgach trzymaj (22%; skupione: 15:19-15:33 22 szt.). Pętla traci puls, gdy blokuje ją przegląd (2 RPC, z czekaniem do `CZEKANIE_NA_SKAN = 0,6 s` na zamek skanu, `rdzen.py:326`) albo klik Alt. Każde puszczenie kosztuje ok. 0,6 s blokady + ponowne naciśnięcie z postoju. Szacunek: 51 x 0,6-0,8 s = 30-40 s na ok. 615 s trzymania (5-6%).

`HOLD_LIMIT_S = 1.5` (obrót puść+naciśnij w jednej partii, `klawisz_x11.py:54`) nie daje widocznego wzoru w stallach (rozkład stalli w czasie od startu płaski, bez piku co 1,5 s). `TRZYMANIE_MAX_S = 20` nie dotyczy (pętla <=12 s).

## 3. Przyczyny przerwań i ich koszt

Po 14:30 (249 pościgów; kolumna "luka" = czas do następnej pętli tego samego celu <=5 s):

| powód | n | czas pętli | luka po | udział | uwagi |
|---|---|---|---|---|---|
| odl<=1 | 111 | 132 s | 81 s | 23% | sukces, walka wręcz |
| okno | 28 | 176 s | 26 s | 22% | cel wciąż daleko (odl_koniec med 3), 6,3 s i 6,2 kroku na pościg |
| zawracanie | 31 | 109 s | **66 s** | 19% | luka 3,1 s = `POSCIG_PRZERWA_PO_ZAWROCIE` (`:151`), potem 5 s stuku (`:152`, wolniejszego) |
| gryzacy | 35 | 98 s | 40 s | 15% | przegląd widzi innego szczura obok (`:1928`) |
| cel_martwy | 31 | 89 s | 38 s | 14% | sukces |
| cel_znikl | 12 | 27 s | 8 s | 4% | |
| oscylacja | 3 | 15 s | 7 s | 2% | |
| brak_ruchu | 2 | 10 s | 0 | 1% | (przed 14:30: 124 przy stuku, 185 s) |

- **Zawracanie**: co 8. pościg, 3 s kary w luce. Od 15:06 jest wariant "bez kary" dla historii <4 pól (`POSCIG_ZAWR_MIN_HIST`, `:~154`), ale 15:30+ nadal 10 z 83 pościgów to zawracanie.
- **Gryzący**: realne zagrożenie (R3 w `analiza-tlum.md`), nie strata prędkości, ale kończy pętlę i przenosi decyzję do ticka (luka 1,1 s).
- **Okno**: 28 pościgów (176 s). `POSCIG_OKNO_DOBRY` 6 s (stuk) / `POSCIG_TRZYMAJ_OKNO_DOBRY` 12 s (`:121`, `:139`). W oknie 12 s mediana 10,7 s i 10 kroków: to czyste "uciekł szybciej niż biegniemy".
- **Histereza/ping-pong**: filtr zmienia kierunek w 4 z 14 kroków w przykładzie (histereza 4, pingpong 2). Nie widać kosztu czasowego (skręty 0,96x), ewentualny koszt to geometria (zawracanie).
- **Skosy niezamierzone**: 41 z 391 kroków (10,5%) to skosy, choć `POSCIG_SKOS_KOSZT=3.0` je wyłącza. Wszystkie przy zmianie osi bez puszczenia klawisza (nowy klawisz naciśnięty przed puszczeniem starego, `klawisz_x11.py:_naciskanie`; klient widzi dwie strzałki naraz). 33% zakrętów kończy się skosem. Koszt netto skosu: kolejny krok po 2,3x zamiast 2x (dwa proste), czyli +0,2 s/skos, ok. 8 s na 463 s (1,7%). Przy modelu "ruch od razu, koszt po" skos jest jednak szybszy do POLA (przybywamy o 1 krok wcześniej), więc to nie jest jednoznaczna strata.
- **Odrzucone klawisze w stuku**: 29,5% (145/491) i `ponow_brak` 142. W trzymaj 0 odrzuceń, ale `ponow_brak` 97 (timeouty po puszczeniu).
- **Zmiany kierunku**: 310 na 688 kroków trzymaj (0,45/krok). Sama zmiana nic nie kosztuje (0,96x); kosztują stalle i skosy wokół zmian.

## 4. Co robi człowiek

Wejścia Karola nie są nigdzie zapisywane (potwierdza `analiza-tlum.md` pkt 1; `pomoc-karola.jsonl` ma tylko agregaty z próbkowania 0,7 s). Co się da powiedzieć:

- Reguły gry są te same: człowiek z trzymaną strzałką albo klikiem w mapę ma ten sam krok (0,56-0,94 s), czyli też ok. 1,5 pola/s na tym spocie. Różnica to ciągłość: brak puszczeń, brak kliknięć w trakcie, brak kolejek RPC.
- Krótkie przebiegi z `pomoc-karola.jsonl` (1-4 s, bot cichy): 1,14-1,43 pola/s (próbkowanie 0,7 s, n małe); długie (89-140 s): 0,37-0,71 pola/s, ale z walką i uciekaniem (uciekał o 41 i 15 pól od skupiska), więc nie nadają się jako tempo biegu.
- Karol w analizie tłumu: "przewaga to bezpieczeństwo HP, nie szybkość" (tempo zabijania bota 9,6 exp/min w tłumie nie jest gorsze). Subiektywne "dużo za wolno" najpewniej pochodzi z tego, że bot zatrzymuje się i wznawia (stalle 0,8-1,4 s, luki 0,3-3 s), a człowiek tego nie robi.
- **Brak twardych danych o tempie Karola w czystym pościgu.** Zalecane: nagrywanie wejścia przez XI2 (opis w `analiza-tlum.md` pkt 129) albo prosty zapis pozycji co 0,1 s przy ręcznej grze (rdzeń `poscig`/`pozycja` w osobnym procesie, tylko odczyt).

## 5. Ranking ogniw wg zysku czasu

Podstawa: epizod pościgu jednego szczura = 9,7 s (94 epizody, średnio 2,67 pętli i 2,8 s luk). Zyski szacowane konserwatywnie, nakładają się częściowo (pozycje 1, 3 i 5 dotykają tych samych stalli).

| # | ogniwo | s/epizod | s/pościg | pewność | rodzaj zmiany |
|---|---|---|---|---|---|
| 1 | Stalle klawisza: strażnik 0,6 s, puszczenie "ostatni"/"zajete" + `brak_zmiany`, przegląd blokujący | 0,9-1,5 | 0,35-0,55 | wysoka (rozkład 61% przy dystansie 2, 51 puszczeń), mechanizm średnia | szybkie + strukturalne |
| 2 | Pełny skan `/proc` przy każdym RPC (65-70 ms x 2-3 RPC na tick, 1 na obrót, 2 na przegląd) | 0,8-1,0 | 0,3-0,4 | bardzo wysoka (zmierzone) | szybka (rdzeń) |
| 3 | Czas do pierwszego kroku (0,33 s, p90 0,54 s) | 0,5 (po #2) | 0,2 | wysoka | szybka/strukturalna |
| 4 | Kara 3 s po zawracaniu + 5 s stuku | 0,7 | 0,26 | wysoka (zmierzone luki), ryzyko oscylacji | szybka (stała) |
| 5 | Tick między pętlami (3 RPC + `pauza(0.05, 0.15)` + 0,3-0,6 s `stwory`) | 0,3-0,5 | | wysoka | szybka |
| 6 | Skosy niezamierzone (10% kroków) | -0,1 do +0,3 | | niska (zależy od pomiaru D/S) | pomiar, potem decyzja |
| 7 | Skan stworów (pełny co 3,5 s: wykrycie nowego szczura po 1,7 s, szybki 0,55 s) | wpływ na start, nie bieg | | średnia | strukturalna |
| 8 | Przewidywanie/przechwyt celu | do ok. 1 s na długie pościgi | | niska (do symulacji offline) | strukturalna |
| 9 | Kliki Alt w pościgu (0,35-0,6 s każdy) | 0 po `ATAK_TYLKO_PRZY_CELU`, brak licznika wcześniej | | niska (brak logu) | już zrobione |

Wpływ na skuteczność jest nieliniowy: +19% prędkości (1,26 -> 1,5) to +60-70% prędkości zbliżania (0,4 -> 0,65 pola/s). Dla odl 4: ok. 10 s -> ok. 6 s. To przekłada się na część pościgów kończonych "okno" (28 z 249) i "cel_znikl".

## 6. Propozycje zmian

### 6.1 Szybkie (stałe, pauzy, jedno miejsce)

| # | zmiana | miejsce | zysk | ryzyko |
|---|---|---|---|---|
| Q1 | **Cache PID w `podlacz()`**: sprawdź `os.path.exists(f"/proc/{self.pid}")` i czy cmdline się nie zmieniło, pełny `znajdz_gre()` tylko co 5 s albo po błędzie odczytu (`OSError` w `czytaj`). Hot reload działa (rdzen.py). | `rdzen.py:624`, `:69`, `:145` | -65 ms na RPC: obrót pętli 0,12 -> 0,05 s, tick -0,2 s, przegląd -0,13 s, pierwszy krok -0,15 s | niskie: błąd to zły PID po restarcie gry, łapany `OSError` + okresowy skan; test: restart gry w sesji |
| Q2 | **Strażnik 0,6 -> 1,2 s** albo `puls()` przed i po przeglądzie/RPC (puls co obrót nie wystarcza, gdy RPC trwa 0,5 s). Bezpieczeństwo: `HOLD_LIMIT_S` 1,5 s i `finally` w `poscig_szybki` zostają. | `klawisz_x11.py:56`, `cavebot.py:~1912` (przegląd), `:2265` | usunięcie ok. 50 puszczeń na 600 s trzymania | niskie-średnie: dłuższe wiszenie klawisza, gdy cavebot padnie (wartownik i `finally` pokrywają) |
| Q3 | `POSCIG_TRZYMAJ_PRZEGLAD` 0,6 -> 1,0-1,2 s; przegląd bez `gracz()` (HP z `poscig`, patrz S1) | `cavebot.py:138`, `:1912` | -0,15 s blokady na przegląd, mniej puszczeń | niskie: opóźnione wykrycie "gryzący" o do 0,6 s |
| Q4 | `POSCIG_PRZERWA_PO_ZAWROCIE` 3,0 -> 0,8-1,0, `POSCIG_STUK_PO_OSCYLACJI` 5,0 -> 0-1,5 | `cavebot.py:151-152` | ok. 2 s na zawracanie (0,7 s/epizod) | średnie: wraca ryzyko oscylacji A-B-A; chroni je `POSCIG_PINGPONG_S`/`COFNIECIE`; 3 oscylacje na 249 |
| Q5 | `pauza(0.05, 0.15)` po ticku -> `(0.0, 0.03)`, gdy poprzedni obieg to WALKA z celem odl>1 lub pościg w ostatnich 3 s | `cavebot.py:3530`, `mozg.py:2317`, `cavebot.py:2477` | ok. 0,1 s na wejście w pętlę | niskie |
| Q6 | `POSCIG_SKOS_KOSZT` ustawić na zmierzone 2,2 po `sonda_skosu.py` (bot zatrzymany) | `cavebot.py:157` | do ustalenia | pomiar wymaga zatrzymania bota i postaci na wolnym polu |
| Q7 | Pętla `okno`: `POSCIG_OKNO_DOBRY` 6 -> 12 także dla stuku (stuk i tak tylko po oscylacji) | `cavebot.py:121` | mało | niskie |

### 6.2 Strukturalne

| # | zmiana | opis | zysk | ryzyko |
|---|---|---|---|---|
| S1 | **Jedno zapytanie "poscig+"**: odpowiedź zawiera pozycję gracza, stwór-cel, HP% gracza i listę sąsiadów (z cache skanera) w jednym RPC. Przegląd odpada jako osobne 2 RPC, wykrycie "gryzący"/HP przy każdym obrocie. | `rdzen.py` komenda `poscig` (`:643`), `cavebot.py:_odczyt_poscig/_poscig_przeglad` | usuwa blokady przeglądu, pętla 1 RPC/obrót | średnie (nowe pola, kompatybilność wstecz już jest) |
| S2 | **Szybki skan bez regionów**: odczyt znanych adresów stworów (`stwor_szybki`, ~0,1 ms) zamiast skanu 3 regionów (0,55 s); pełny skan tylko na odkrycie nowych (co 3-5 s, w tle). Daje świeże pozycje/HP stworów w ms i zdejmuje zamek skanu z RPC. | `rdzen.py:357` `_skanuj_stwory`, `:478` `skaner_krok` | świeże dane przy każdym tiku, koniec czekania na zamek (0,6 s) i GIL | średnie: stwór usunięty z pamięci (zwraca None, już obsłużone) |
| S3 | **Trwałe połączenie + "czekaj na zmianę"**: `poscig_czekaj` blokuje do zmiany pozycji lub timeoutu; rdzeń sprawdza pozycję co 10 ms w swoim wątku. Opóźnienie detekcji kroku ze ok. 0,06-0,12 s do 0,01 s, brak `spij` i brak nowego `socket.connect` na zapytanie. | `bot.py:43`, `rdzen.py`, `poscig_szybki` | decyzja przy zakręcie i start szybsze o ok. 0,1 s | średnie |
| S4 | **Ciągłe trzymanie z korektą**: nie puszczaj klawisza w "ostatni"; zostaw go, aż pętla zobaczy `odl<=1` (wtedy `finally` puszcza), a "zajete" traktuj jako zmianę kierunku/oczekiwanie bez puszczania (klient przy zajętym polu i tak nie wykona kroku). Usuwa stalle 61% przy odl 2. | `cavebot.py:2017-2060` (`_poscig_decyzja`), `:2200-2215` (`brak_zmiany`) | do 0,9 s na pościg z podejściem końcowym | średnie: ryzyko jednego kroku za dużo przy ostatnim polu; mierzyć |
| S5 | **Planowanie kilku kroków naprzód**: A* raz na 1-2 kroki celu, bez przeliczania przy każdym obrocie (dziś `przelicz=True` przy zmianie `poz` lub `sxy`); wyznaczyć sekwencję klawiszy i naciskać z wyprzedzeniem (kolejka klienta ma 1 krok). | `cavebot.py:2226-2262` | mało (decyzja i tak 1 ms) | niskie, ale mały zysk |
| S6 | **Przechwyt zamiast dojścia do pozycji**: dla celu idącego prosto k kroków (z `tgt`) celować w pole k = d*v_cel/(v_nasza-v_cel) naprzód wzdłuż jego kierunku (mapa: korytarz). Dziś przewidywanie tylko +1 krok i tylko gdy dystans >3 (`POSCIG_PRZEWIDYWANIE_ODL`). Zweryfikować offline na `sciezka` (mamy tory celu cx, cy) zanim ruszy w kodzie. | `cavebot.py:_poscig_cel_przewidziany ~2090` | do kilku s na długie pościgi, zero przy ucieczce wprost | średnie: gdy cel zawraca, gonimy cień |
| S7 | **Skosy wg czasu przybycia**: skos trzymanym numpadem na ostatnich <=4 krokach (n_skos <= 4: 2,3(n-1) < 2n-1), proste dalej. Reguła `POSCIG_SKOS_KOSZT < 2` (czas przejazdu) jest zła dla modelu "ruch od razu, koszt po". | `cavebot.py:_poscig_skos 2003` | ok. 1 krok czasu na końcowe podejście po skosie | wymaga pomiaru D/S (`sonda_skosu.py`) |
| S8 | Klik-marsz (autowalk z `idz_do`) dla odległości >=5: serwer wykonuje trasę bez udziału pętli i klawiszy. | `cavebot.py:idz_do 1056` | zależy od krótszego klika (Alt+klik 0,35-0,6 s, `ekran.py:160-210`) | wysokie; nie polecam przed S1-S3 |

## 7. Plan pomiaru po wdrożeniu

Istniejące metryki w `poscig_koniec` + skrypt `rozbicie2.py` (scratchpad) wystarczą. Do dopisania w telemetrii (tanie):

1. `rpc_n`, `rpc_czas_sum` (średni koszt RPC; cel <= 0,02 s po Q1) oraz `przeglad_n`, `przeglad_czas`.
2. Liczniki zdarzeń klawisza w pętli: `puszczenia_ostatni`, `puszczenia_zajete`, `puszczenia_brak_zmiany`, `puszczenia_strazni` (delta `klawisz_x11.WATCHDOG_PUSZCZENIA`).
3. `kliki_ataku` i ich łączny czas.
4. `t_pierwszy_krok` jawnie (dziś `sciezka[0][2]`).

Progi sukcesu (dziś -> cel):

| metryka | dziś | cel |
|---|---|---|
| `trzymane_s/czas` | 0,73 | >= 0,90 |
| czas do pierwszego kroku (mediana) | 0,33 s | <= 0,15 s |
| udział kroków w prostej z odstępem >1,3x | 36% | <= 10% |
| stalle przy odl 2 | 61% | <= 20% |
| puszczenia strażnika | 51 / 227 pościgów | 0 |
| `ponow_brak` na pościg | 0,43 | <= 0,1 |
| sprawność kroków (teoria/rzeczywistość) | 0,77 | >= 0,9 |
| luka między pętlami tego samego celu, mediana | 0,65-1,0 s | <= 0,4 s |
| kroki/s w epizodzie z lukami | 0,82 | >= 1,1 |
| udział dobić przy odl_start 3-5 | 27-51% | >= 55% |
| niezamierzone skosy | 10,5% kroków | rejestrować (zależnie od S7) |

Kolejność wdrażania z pomiarem: Q1 (osobno, 20 pościgów), potem Q2+Q3, potem Q4+Q5, potem S4. Po każdym etapie min. 30 pościgów trzymaj, porównanie mediany `t_pierwszy_krok`, `trzymane_s/czas`, udziału stalli. Pomiar skosów (`sonda_skosu.py`, 3 min) i pomiar RPC (`rpc.py`) przy zatrzymanym bocie, żeby wynik nie był zafałszowany ruchem.

## 8. Ograniczenia danych

- Czas ticka nie jest próbkowany w telemetrii; udział składników wyprowadzony z luk między pościgami i 12 pomiarów RPC na żywo (bot działał, skaner w tle).
- `sciezka` dostępna od 14:41 (153 pościgi o formacie "krok po kroku"); wcześniej tylko agregaty.
- Kod zmieniał się w ciągu dnia (stuk -> trzymaj o 14:27, skan 15:29, kara zawracania 15:06, `ATAK_TYLKO_PRZY_CELU` ok. 15:10-15:56), więc liczby są mieszaniną wersji. Szczególnie liczba klików Alt w pościgu nie jest zapisana.
- Prędkość szczura liczona z 42 pościgów >=5 kroków (ucieczka), z poprawką Chebyshev: 0,85 pola/s. To ograniczenie z góry dla szczurów uciekających, nie dla wszystkich.
- Teoria `ceil(10000*v/230/50)*50` jest zgodna z danymi (4 wartości v), ale speed 230 dla level 6 to założenie.
