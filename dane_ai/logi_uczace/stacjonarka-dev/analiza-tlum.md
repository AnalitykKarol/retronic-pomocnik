# Analiza: bot i Karol przy tłumie mobów (11.10.2026, 11:58 - 14:53)

Analiza tylko z istniejących danych (telemetria-20261011.jsonl, mozg-2026101*.log, rdzen-skan.log, STOP/STOP_RECZNY, mapa/map74.otmm). Zero zmian w kodzie, zero inputu do gry.

## 0. Najważniejsze (TL;DR)

1. **Ruchów Karola nie ma w danych.** Telemetria i skan rdzenia działają tylko, gdy działa mozg.py. Gdy Karol zatrzymuje bota (STOP_RECZNY), dziura w danych trwa od 38 s do 11,6 min. Widać tylko stan tuż przed STOP i tuż po restarcie oraz przyrost expa w przerwie. Taktyka Karola jest więc wnioskowana pośrednio i ma niską pewność. Reguły poniżej opieram głównie na tym, co mierzalne: jak tłum szkodzi i co bot robi źle.
2. **Tylko 1 z 4 wymienionych STOP-ów (14:44:59) wypada w tłumie.** 14:03:54, 14:12:30 i 14:32:11 to chwile z 0-1 szczurem w pobliżu i HP 91-100% (bot gonił uciekającego szczura 7-9 pól dalej, odpuszczał "za ścianą", dobijał pojedynczego). Karol zatrzymywał bota głównie dlatego, że bot marnuje czas i jest w złym miejscu, a nie z powodu tłumu.
3. **Tłum jest kosztowny dokładnie od 3 stykających się mobów.** Przy 0-2 stykających HP spada 0,01-0,07 %/s. Przy 3: 0,59 %/s, przy 4: 1,11 %/s. 7% czasu walki (267 s, 20 segmentów) = 165 pp utraconego HP (ok. 2/3 całej straty).
4. **Bot w tłumie stoi** (189 z 197 próbek stał, 8 razy się ruszył), bije głównie najsłabszego stykającego (88%) i nie ma żadnej reguły cofnięcia/ustawienia się. Najgorsze momenty: pościg za uciekającym 20-25% szczurem prosto w rój (14:44) i celowanie w oddalonego uciekiniera, gdy 3 gryzą (14:09:47-14:10:05).

## 1. Źródła i ich ograniczenia

| Źródło | Co daje | Czego brakuje |
|---|---|---|
| telemetria-20261011.jsonl | próbka co ~1 s: stan, poz, hp, stwory (dx,dy,odl,hp,`cel` = cel BOTA), zdarzenia | tylko gdy mozg działa; brak id stworów, brak flagi "atakowany" (rzeczywisty cel w grze), brak ucieczki/ucieczka stan nie jest próbkowany (np. 13:04:07-13:13:35 pusto), luki 8-60 s przy LOOT/JEDZENIE/pościg |
| mozg-*.log | decyzje, "Nowy cel", "Zmiana celu", odpuszczenia, "Zatrzymano (plik STOP)" | nie odróżnia STOP-u nadzoru (przerwa 2-5 s) od STOP-u Karola (przerwa 38 s+) |
| rdzen-skan.log | liczba stworów co kilka s | tylko gdy mozg działa; tylko liczby |
| STOP_RECZNY | tylko ostatni (14:44:58,77) | historia nie jest zachowana |
| exp (pole `exp` w próbkach) | Δexp w przerwie = zabite szczury (5 exp/szczur; zdarzają się częściowe 1-2 exp) | |
| czat "ja" | Karol kupował w NPC 13:38-13:40 (przerwa 13:34-13:46 to zakupy, nie walka) | brak logu walki z konsoli |

Wejście Karola (klawisze, myszka) nie jest nigdzie zapisywane. W systemie działa `rolling_input_monitor.py` (projekt omarchy-tibia), ale to inny projekt/inna gra; jego log (`/run/user/1000/tibia-bot/input-monitor.jsonl`) zawiera same `status_error` (brak `session.info`), więc nie nadaje się.

Metoda: "styczne" = mob na polu w odległości Chebysheva 1 od postaci (pozycje względem gracza z próbki, korygowane o dx/dy postaci). Szkoda = spadek HP gracza między kolejnymi próbkami (dt <= 3 s), gdy postać stoi w miejscu w stanie WALKA.

## 2. Epizody "tłum" (>= 3 szczury w odl <= 5), od 11:58

Kolumny: maks. = max liczba szczurów w odl <= 5 / max styczne; HP = start / min / koniec; zab. = zabicia w oknie; zmiany = "Nowy cel" w oknie.

| # | czas | dł. | maks. | HP | zab. | zmiany | jak się skończył |
|---|---|---|---|---|---|---|---|
| 1 | 12:17:44-12:18:29 | 46 s | 4/4 | 99/89/91 | 1 | 5 | zabicia, bot dalej |
| 2 | 12:19:25-12:19:34 | 10 s | 5/1 | 95/95/95 | 0 | 1 | rozeszło się |
| 3 | 12:20:44-12:20:55 | 11 s | 4/0 | 91/91/91 | 1 | 1 | zabicie |
| 4 | 12:30:33-12:31:20 | 47 s | 4/4 | 92/80/82 | 2 | 5 | zabicia |
| 5 | 12:36:04-12:37:44 | 100 s | 4/4 | 98/60/61 | 3 | 8 | zabicia; w środku bot gonił 20% szczura 10 pól na południe (12:36:22-35), potem wrócił do grupy i bił na polu z 7 otwartymi sąsiadami |
| 6 | 12:43:20-12:43:38 | 18 s | 3/3 | 75/75/75 | 1 | 2 | zabicie |
| 7 | 12:53:25-12:56:40 | 195 s | 5/3 | 96/58/63 | 3 | 8 | zabicia; HP 58-63 do 13:04, potem ucieczka (13:04:08, 59%) i ~6 min pauzy/"wróć do miasta" bez jedzenia; STOP 13:09:59 |
| 8-12 | 13:16:50, 13:25:35, 13:52:36, 13:56:20, 13:56:46 | 0-3 s | 3-5/0-1 | 100 | 0 | 0-3 | muśnięcia (1-3 próbki) |
| 13 | 13:58:47-13:59:03 | 16 s | 3/3 | 100/100/100 | 1 | 1 | zabicie |
| 14 | 14:03:44-14:03:45 | 1 s | 3/1 | 100 | 1 | 1 | bot gonił 25% szczura 7-9 pól, STOP_RECZNY 14:03:54 (bez tłumu) |
| 15 | 14:04:51-14:05:06 | 15 s | 3/3 | 98/93/93 | 1 | 2 | restart bota przez Karola w środku 3 stykających 100% szczurów |
| 16 | 14:08:57-14:10:16 | 79 s | 5/4 | 100/86/86 | 1 (!) | 7 | 1 zabicie w 79 s; 3x "zniknął z widoku żywy", 1 odpuszczenie; ping-pong między uciekinierem 25% a stykającymi |
| 17-18 | 14:18:25, 14:19:47 | 5 s | 3/1 | 100 | 0 | 0-1 | muśnięcia |
| 19 | 14:28:58-14:29:53 | 54 s | 5/3 | 100/95/98 | 3 | 4 | zabicia (najlepszy epizod: 3 zab., -5 pp) |
| 20 | 14:31:12-14:31:16 | 4 s | 3/2 | 100 | 0 | 0 | muśnięcie |
| 21 | 14:39:39-14:39:56 | 17 s | 3/3 | 97/86/86 | 1 | 2 | restart po ręcznym przeniesieniu o 43 pola na zachód, 3 stykające na starcie |
| 22 | 14:41:18-14:41:43 | 26 s | 4/3 | 91/83/83 | 2 | 2 | zabicia (pościg 15 kroków przed) |
| 23 | 14:43:51-14:44:57 | 67 s | 7/5 | 91/59/59 | 0 | 4 | **STOP_RECZNY 14:44:59**; patrz 4.1 |

Segmenty >= 3 stykające (20 sztuk, 267 s): HP spadło o 165 pp, w tym 3 segmenty po 19-32 pp (12:37:18 -19, 12:53:50 -27, 14:44:22 -32).

Model szkody (postać stoi, WALKA, od 11:58):

| stykające | szkoda %HP/s | czas obserwacji |
|---|---|---|
| 0 | 0,01 | 361 s |
| 1 | 0,02 | 1362 s |
| 2 | 0,06 | 470 s |
| 3 | 0,59 | 199 s |
| 4 | 1,11 | 37 s |
| 5 | 1,28 | 8 s |

Kontrola: przy >= 4 szczurach w odl <= 5, ale tylko 2 stykających, szkoda to 0,14 %/s (nie 0,6). Czyli liczą się stykające, nie "widoczne". Próg 3 jest ostry.

Bot przy tym nie ma "ciasnych" pól: pole z <= 3 otwartymi sąsiadami (wg mapy) miało stykające >= 3 w 1,4% próbek, pole z >= 7 otwartymi w 21%. Wszystkie 3 największe straty HP miały miejsce na polach z 4-7 otwartymi sąsiadami.

## 3. Co robił Karol (wnioskowane, nie obserwowane)

Przerwy dłuższe niż 30 s (STOP ręczny):

| STOP | stan bota przed | HP | przerwa | pozycja przed -> po | HP | exp Δ (~zab.) | stan po restarcie |
|---|---|---|---|---|---|---|---|
| 13:09:59 | ucieczka od 13:04:08 ("wróć do miasta", brak jedzenia) | 56 | 3,6 min | (32021,32150) -> (32049,32155) | 59 -> 55 | +8 (od 13:04:07) | 1 szczur 20% w odl 8 |
| 13:34:49 | po lootcie, nikogo | 98 | 11,6 min | (32053,32159) -> (32013,32149) | 98 -> 100 | +15 (3) | zakupy w NPC (13:38-13:40) |
| 14:03:54 | pościg za 25% szczurem w odl 7-9; 100% w odl 5 | 100 | 56 s | (32046,32156) -> (32018,32149) | 100 -> 98 | +5 (1) | **3 stykające 100%** (restart w środku grupy) |
| 14:12:30 | "Odpuszczam: za ścianą" (szczur w odl 7) | 91 | 98 s | (32031,32142) -> (32007,32151) | 91 -> 99 | +5 (1) | 1 stykający 100% + uciekinier 5% |
| 14:32:11 | bije pojedynczego szczura (45%) obok | 100 | 38 s | (32025,32148) -> (32012,32148) | 100 | +2 | nikogo |
| 14:34:07 | IDZ, szczur w odl 10 | 100 | 188 s | (32036,32149) -> (32014,32142) | 100 | +10 (2) | nikogo |
| 14:38:40 | dobija 20% szczura w odl 4 | 100 | 58 s | (32031,32149) -> (31988,32135) | 100 -> 97 | 0 | **3 stykające 100%** |
| 14:44:59 | tłum 5-7 szczurów, 3-5 stykających | **59** | 6,5 min | (32032,32150) -> (32013,32149) | 59 -> 85 | **+55 (~11)** | nikogo, bot dalej (prog-hp 30) |

Wnioski:
- **Motyw dominujący: zmiana miejsca, nie ratunek.** 7 z 8 interwencji przy HP 91-100% i bez tłumu. Po każdej Karol przenosił postać o 12-43 pola na zachód (x 31988-32018, y 32135-32151) i oddawał bota tam. Kilkukrotnie (14:04:51, 14:39:39) oddał bota w środek 3 świeżych szczurów (HP 97-98%); bot z nimi poradził sobie (HP -5 i -11 pp w 12-17 s, 1 zabicie).
- **Jedyny prawdziwy epizod tłumu to 14:44.** Karol wszedł najpewniej już ok. 14:44:37-52: w tym oknie 3 różne szczury, które NIE są celem bota, straciły 20, 35 i 35% HP (pozycje (0,-1), (-1,0), (+1,0)), a cel bota (-1,-1) dostał tylko 2 trafienia. Jedna postać bije jeden cel naraz, więc to najpewniej ręczne przełączanie celów kliknięciem (pewność średnia-niska; nie ma flagi "atakowany"). Zatrzymał bota przy HP 59%, czyli daleko powyżej progu ucieczki bota (30% od 13:13, wcześniej 55%).
- **Przerwa 14:44:59-14:51:27 pokazuje wynik, nie sposób.** +55 exp (~11 szczurów) w 389 s (8,5 exp/min) i HP 59 -> 85. Sama regeneracja bez jedzenia to ok. 3-6 %/min (13:17-13:23: 58 -> 94 w 6 min; 12:38-12:48: 63 -> 91 w 10 min), czyli +20-39 pp, więc bilans strat HP w trakcie ręcznego czyszczenia to ok. 0 do -15 pp. Tempo zabijania nie jest wyraźnie lepsze od bota (bot: 6,2 exp/min ogółem, 9,6 exp/min w tłumie). Przewaga Karola to raczej bezpieczeństwo HP, nie szybkość.
- Z danych NIE da się odtworzyć: cofania do korytarza, kolejności zabijania, użycia ściany/rogu, momentu jedzenia, ucieczki. Brak próbek w przerwach.

## 4. Zachowanie bota w tych samych sytuacjach

Zmierzone na 20 segmentach >= 3 stykające i na 612 próbkach z >= 2 stykającymi:

| Aspekt | Zachowanie bota | Dane |
|---|---|---|
| Ruch przy tłumie | stoi i bije; w 189 z 197 próbek (>= 3 stykające) pozycja bez zmian | brak reguły cofnięcia, ucieczka dopiero przy HP <= próg (30%, wcześniej 55%) |
| Wybór celu przy >= 3 stykających | cel stykający 175/195; w 154 z nich jest to najsłabszy stykający; w 4 cel świeży mimo rannego stykającego | dobra reguła, zostawić |
| Cel NIE stykający przy >= 2 stykających | 64/612 próbek (10%), przy >= 3: 15/195 (8%) | patrz 4.2 |
| Zmiana celu | 49 z 91 niedobitych epizodów = "zmiana celu na świeżego" (mediana HP porzuconego 25%); 13 "zniknął z widoku żywy"; 16 "gonię uciekającego bez skutku" (25 s / 40 s) | uciekinier (<= 25%) bywa porzucany słusznie; zabicie uciekiniera trwa średnio ok. 24 s wobec 10,8 s dla nieuciekającego |
| Pościg | 411 pościgów, w tym 286 za <= 30% HP; z >= 2 innymi szczurami w odl <= 6 startuje tylko 29 (25 uciekających) | rzadko, ale to właśnie te kończą się źle; 9 z 20 segmentów tłumu było poprzedzone pościgiem (do 20 s wcześniej) |
| HP | tłum nie uruchamia ucieczki (min. 58-60%); ucieczka przy 59% przyszła po walce (13:04) i dała ~6 min przestoju | 29x "brak jedzenia", regeneracja tylko z czasu i z cheese ze zwłok |
| Obrona "gryzie" | wyzwalacz = spadek HP >= 3 pp w 2 s; przy 0,6 %/s często nie zadziała | reguła tłumu (`len(obok)>=2 and odl>3`) działa tylko dla dobijania, nie dla pościgu |

### 4.1 Epizod 14:43:51-14:44:57 (kluczowy)
- 14:44:01 cel (25% -> 20% szczur) uciekł na (+3,-1), obok 2 stykające 100%. Bot go gonił w pościgu 'okno' ok. 10 s, 14 kroków, 8 pól na wschód (32023 -> 32031).
- 14:44:19: 7 szczurów w odl <= 5, 2 stykające, po 3 s 5 stykających. Uciekinier dalej 20% w odl 6, nigdy nie dobity (po pościgu "zniknął z widoku żywy").
- 14:44:22-57: stoi w miejscu z 4-5 stykającymi, HP 91 -> 59 (-0,9 %/s, w 14:44:22-31 -1,9 %/s), 0 zabić w 35 s; 3 zmiany celu ("zmiana celu na świeżego"), każda wracała do 100% szczura, a trzy stykające stały na 65/70/80%. Pole (32031,32150) ma 5 otwartych sąsiadów; do pola z 2 otwartymi sąsiadami było 3 kroki ((32033,32153)).

### 4.2 Ping-pong 14:09:47-14:10:05
Bot 3 razy zmienia cel na uciekającego 25% szczura 5-6 pól dalej ("Nowy cel: Rat HP 25%", "Atak na Rat nie wrócił po kliku") przy 3 stykających 100%. HP 94 -> 86. Powód: warunek "gryzie" wymaga spadku >= 3 pp w 2 s, a tłum zdejmuje ~0,6 %/s.

## 5. Proponowane reguły (z progami i pewnością)

| # | Reguła | Dane za | Pewność |
|---|---|---|---|
| R1 | **Tryb tłumu = >= 3 żywe moby w odl 1** (nie >= 3 widoczne w odl 5 i nie spadek HP). W tym trybie priorytet ma tylko obrona. | skok 0,06 -> 0,59 %/s; 4 szczury w odl 5 przy 2 stykających = 0,14 %/s | wysoka (267 s, 20 segmentów, 1 postać, 1 mob) |
| R2 | W trybie tłumu bij **najsłabszego stykającego**; nie klikaj w niestykającego, nie startuj pościgu, nie rób Alt+klik na uciekinierze. Uciekiniera (<= 30%) odpuść bez kary (wróci po regeneracji). | cel już jest najsłabszym stykającym w 88% (zachować); 8-10% czasu tłumu bot celuje w niestykającego (14:09:47-14:10:05: -8 pp; 14:44:01-19) | wysoka dla "nie goń", średnia dla "zawsze najsłabszy" |
| R3 | **Nie startuj pościgu uciekiniera, gdy w promieniu 8 jest >= 2 innych żywych szczurów** albo droga pościgu prowadzi w kierunku większej liczby mobów niż przy starcie. | 14:44 (rój 7 szczurów po 8 polach pościgu); 9/20 segmentów tłumu po pościgu; zabicie uciekiniera = ok. 24 s | średnia (mało przypadków: 29 pościgów z >= 2 obcymi) |
| R4 | **Wyprzedzające ustawienie**: gdy liczba żywych w odl <= 8 wzrośnie do >= 3, a pole ma >= 5 otwartych sąsiadów: w <= 3 krokach wejdź na wolne pole z <= 3 (idealnie <= 2) otwartymi sąsiadami, nie w stronę mobów, i tam stój. Tłum narasta 14-20 s (0 -> 4 mobów w odl 8), więc jest czas. | pole z <= 2 sąsiadami: max 2 stykające (z mapy); z <= 3: stykające >= 3 w 1,4% próbek. Dostępność: pole <= 3 sąsiadów w <= 2 krokach w 46% próbek tłumu, pole <= 2 sąsiadów w <= 3 krokach w 19%, w <= 5 krokach w 27% | niska-średnia: efekt wynika z tabeli szkód, to NIE jest potwierdzone zachowanie Karola |
| R5 | W tłumie nie ucieczka trasą wstecz, tylko R2/R4. Alarm miękki przy HP < 60% i >= 3 stykających (pauza wchodzenia w nowe grupy, wezwanie Karola). | od 59% do 30% przy 0,6-1,1 %/s zostaje 26-48 s; ucieczka 13:04 = 6 min przestoju bez regeneracji | średnia-niska |
| R6 | Po tłumie z HP < 70% i bez jedzenia: nie wchodź w następną grupę, stój na polu o <= 3 sąsiadach do ok. 85%. | brak jedzenia, regeneracja 3-6 %/min; epizody 5 i 7 -> 58-63% | niska |
| R7 | Telemetria: dopisz do próbki rzeczywisty cel z pamięci (id atakowanego), liczbę stykających i licznik klików bota. | bez tego nie odróżnia się bota od ręcznych kliknięć | (narzędzie, nie reguła) |

Czego NIE wolno wnioskować z tych danych: że Karol cofał się do korytarza, bił od najsłabszego, albo uciekał. To są hipotezy zgodne z tabelą szkód, nie obserwacje.

## 6. Czego brakuje i jak to zdobyć (tylko opis, nic nie wdrożono)

1. **Obserwator "tylko odczyt" działający także po STOP.** `nagraj_trase.py` już czyta pozycję przez gniazdo `retronic-pomocnik.sock` 4x/s bez inputu. Analogiczny, osobny proces (np. `obserwuj.py`, niezależny od mozg.py i pliku STOP) zapisywałby co 0,5-1 s: poz, hp, stwory (dx, dy, hp, id), id atakowanego celu, exp, do `logi/obserwacja-RRRRMMDD.jsonl`. Pokrywa całą ręczną grę, a nie tylko okna z botem. To jest największa pojedyncza dziura.
2. **Nagrywanie wejścia Karola na :1 (osobne narzędzie).** Python (python-xlib) z rozszerzeniem XRecord, albo lepiej XInput2 raw events (XI_RawKeyPress/RawButtonPress), podłączone do wyświetlacza :1 (XWayland, na którym chodzi RetronicGL.exe). Zapisuje: czas (wall + monotonic), kod/nazwa klawisza, press/release, przyciski myszy, współrzędne wskaźnika i okno pod wskaźnikiem. XI2 ma `sourceid`, więc odróżnia fizyczną klawiaturę/mysz Karola od urządzenia XTEST (input bota); przy samym XRecord zdarzenia XTEST są nie do odróżnienia, więc wtedy trzeba korelować z logiem wysyłki w `klawisz_x11.py` (dopisać log wysłanych klawiszy z czasem). Ograniczenia: pod XWayland/Hyprland widać zdarzenia tylko, gdy fokus ma okno XWayland (gra), co tu akurat wystarcza; log trzeba rotować i traktować jak dane wrażliwe (czat). Połączenie z pkt 1 po znaczniku czasu daje: kliknięcie w mob X -> zmiana id atakowanego -> trafienie.
3. Zachować historię STOP_RECZNY (dopisywać wpis z czasem do `logi/stop-historia.log`), żeby odróżniać STOP Karola od STOP nadzoru bez zgadywania z długości przerwy.
4. Próbkować stan UCIECZKA (dziś pusto: 13:04:07-13:13:35).
5. Powtórzyć analizę po zebraniu kilku sesji; dziś próba to 1 postać, 1 typ moba (Rat), 1 trasa, 1 dzień. Wnioski o progu 3 stykających mogą nie przenosić się na inne moby (np. silniejsze).

## 7. Notatki o jakości danych

- HP szczurów jest skwantowane co 5%; kolejność trafień w jednej sekundzie jest niepewna.
- Identyfikacja moba między próbkami po pozycji (<= 2 pola, |dHP| <= 60); przy tłoku zdarzają się zamiany. Flaga `cel` w telemetrii bywa spóźniona o jedną próbkę (20 "obcych" trafień w całym oknie, z czego tylko 3 w 14:44 nie mają innego wyjaśnienia).
- Mapa: "otwarte pola" z flag przechodniości OTMM; nie uwzględnia przedmiotów blokujących ani innych graczy.
- Okno analizy: próbki do 14:53 (bot restartowany przez Karola 14:51:25, `--prog-hp 30`).
