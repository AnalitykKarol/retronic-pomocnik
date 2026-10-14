# Obserwacja bota Retronic, 13.10.2026 (start 11:52)

Tryb: uh, patrol trolli (trolle_patrol, z8/z9). Log: logi/mozg-20261013-1139.log. Tylko odczyt.

## PILNE
(brak na razie)

## Rundy

R0 11:52 | HP 140/200 (70%) | mana 21/125 | cap 15 oz (NISKI, <20) | exp 16770 (lvl 11) | poz. (32496,32282,z9) | walka z trollami, bot żyje | UH wyłączone do ~12:17 (3 porażki z "blank poza oknem")

R1 11:54 | HP 86% (wg decyzji modelu) | mana 2/125 wg próbki 11:53 (exura 25 mana o 11:50) | cap 15 oz | exp 16770 (bez zmiany od R0, ~0 przyrost w 2 min, 1 zabójstwo troll 11:53) | poz. z8 wg notatki modelu (zwłoki z z9, pętla "brak_okna_lootu") | walka z trollami, bot żyje | UH nadal wyłączone (do ~12:17)
  - ucieczka 11:50:28 przy HP 64% (log: "próg 62%"; model w decyzji pisze "próg 50%" = rozjazd promptu z progiem), trwała 156 s, HP 64 -> 84%: bot nie używa UH i leczy tylko exurą, wolno.
  - leczenie exurą przy mana 25 (11:50) i mana 2 (11:53): brak many = brak leczenia, a UH wyłączone. Hipoteza: brak mana-potionu/odnowy many w pętli trolli.
  - 11:53:56 zabity troll na z9, bot na z8: loot "brak_okna" (Ctrl+klik z innego piętra). Powtarza się (notatka modelu 11:54:08).
- 11:54 przegląd crona: bot żyje, HP 173/200 (86%), mana 12 (exura niedostępna, UH i tak wyłączone), cap 15, walka z trollami na z8; powtarzające się brak_okna_lootu dla zwłok na z9 (ja na z8); w widoku 7 Rotworm + Rabbit.

R2 11:56 | HP 90-181 (ok, 181 w próbce 11:56:18) | mana 27/125 (22%) | cap 15 oz (max_cap nieczytany w próbkach) | exp 16810 (+40 od 11:52, ~600 exp/h) | poz. z8 (~32480,32293) | walka z trollami, dobicie działa, zabite 2 trole, bot żyje | UH nadal wyłączone
  - 11:56:22 "Jedzenie w walce: HP nie rośnie od 33 s (hp 90%)" -> zjadł ham z plecaka, mana i tak rosła sama. Hipoteza: logika "HP nie rośnie" bierze brak regeneracji za głód; jedzenie zbędne, a UH wyłączone.
  - 11:56:30 "Droga do Troll zablokowana" + bicie blokującego: poprawnie.
  - 11:56:46 loot: zwłoki na (0,0) zamiast (0,-1) -> "Loot: ok" po fallbacku. Działa, ale kosztuje dodatkowe kliknięcie.
  - Sample 11:54-11:56: bot przeszedł na z8 i wszedł w króliki/rotwormy (Rabbit x4), co jest ok, ale w tym samym czasie troll zostaje na z9 (zwłoki z 11:53 nie zlootowane).

R3 11:57 | HP 185 (~92%) | mana 36 | cap 55 oz (w próbce 11:57:18; wcześniej 15 przez cały czas -> poprzedni "NISKI cap" to BŁĄD ODCZYTU, nie realny stan) | exp 16850 (+40 od 11:56, ~+80 od 11:52 w ~5 min) | poz. z8 (32478,32271) | walka z trollami i szczurem, bot żyje
  - 11:57 OBSERWATOR [problem]: dobicie w oknie 5 min spadło do 67% przy 6 epizodach; główny powód porzuceń to zmiana celu na świeżego (koszt exp).
  - Hipoteza: po "Zmiana celu" bot nie dokańcza trolla z HP 6-10% (porzuca na rzecz trolla z 100%). Zmiana na Świeży przy odl 2-5.

R4 11:59 | HP 195 (98%) | mana 56 (rośnie sama, bez czarów) | cap 55 oz | exp 16870 (+20 od 11:57, ~+60 od 11:52; tempo spadło do ~600/h, 11:57-11:58 exp stał w miejscu) | poz. z8 (32493,32290) | walka/patrol, bot żyje, UH nadal wyłączone
  - 11:59:21 OBSERWATOR [problem]: dobicie w oknie 5 min 43%; cele znikają z widoku żywe, porzucone.
  - 11:59:31 "Cel Troll wyszedł z widoku (32503,32283), odpuszczam" przy odl 7: bot odpuszcza trolla i od razu bierze następnego z tej samej pozycji (32503,32283). Hipoteza: marnuje ruch; cel był 7 pól, po czym wraca na patrol.
  - 11:59:27 "utknięcie, wracam na trasę do punktu 0 (droga 0 pól)" przy przejściu piętra z8 na z9: bot stoi na z8, punkt przed 3 jest na z9. Przejście wykonane dopiero w próbie 1 o 11:59:28 (zadziałało). Hipoteza: punkt trasy z8 wymaga sprawdzenia kroku Up przed startem patrolu.
  - 11:59:24 loot gold coin +6, zbiera poprawnie po pytaniu o ilość.

R5 12:00 | HP ~98% (wg logu 11:59-12:00) | mana 56+ | cap 55 oz | exp ~16870 (bez nowych zabójstw od 11:59:21) | poz. z8/z9 okolice m8 | walka z trollem (ucieczka trolla przy 27%, 12:00:06), bot żyje, UH nadal wyłączone
  - 12:00 tempo exp spada: 1 zabójstwo w ~4 min. Hipoteza: długie dojścia i zmiany celu zjadają czas.

R6 12:00 | HP 200 (100%) | mana 66 | cap 54 oz | exp 16890 (+20 od 11:59, ~+40 od 11:57) | poz. z9 (32507,32278), walka z orkiem i trollami, bot żyje | UH nadal wyłączone
  - 12:00:23 OBSERWATOR [problem]: dobicie 43% przy 7 epizodach; utracone ok. 80 exp (50% potencjału) przez porzucone cele znikające z widoku.
  - 12:00:19 "Troll ucieka przy ~26% (zaobserwowano 22%)": próg ucieczki trolla ustawiony na 26%, a zaobserwowane wartości 18-30%. Hipoteza: trolle uciekają przed dobiciem; próg zbyt wysoki dla 10 pkt HP dobicia.
  - 12:00:13 "Pościg: zawracanie na krótkiej historii (3 pól)": poprawna reakcja, bez kary.

R7 12:02-12:03 | HP 200 (100%) | mana 86 (rośnie, bez czarów; ok) | cap 53 oz | exp 16960 (+70 od 12:00, tempo chwilowo ~2000/h: 2 trolle i ork) | poz. z9 (32506,32279), walka i loot, bot żyje | UH nadal wyłączone
  - Kilka zabójstw z rzędu i zbieranie gold coin bez problemów (loot "ok" x4). Zmiana celu nie widoczna w tym oknie.
  - 12:02:27 OBSERWATOR [problem]: dobicie w oknie 5 min 57% (7 epizodów); ~60 exp straconych przez cele znikające z widoku.
  - 12:02:16 "patrol m8 (32497,32283) 16 pól": po lootcie bot wraca na patrol, 16 pól, a kolejne trolle są 7 pól od miejsca. Hipoteza: ruch powrotny do punktu patrolu (m8) zabiera czas, zanim zobaczy kolejne trolle.

R8 12:03 | HP ~100% | mana ~90 | cap 53 oz | exp ~16960+ (bez zmian w próbce 12:02:19, log: kolejny troll 20% w walce) | poz. z9 w pobliżu schodów (32495,32289) | walka, bot żyje | UH nadal wyłączone
  - 12:02:56 "Patrol: wizyta m8 #1 (ok): dojście 935 s": liczba 935 s to czas od ostatniej wizyty, nie czas dojścia. Log myli pola; sprawdzić etykietę w kodzie (poza zakresem obserwacji).
  - 12:02:57 "cel m6 ... droga 31 pól, waga 0.243": bot wybiera losowy punkt patrolu 31 pól drogi zamiast trolli w zasięgu. Hipoteza: wybór patrolu przy trollach w pobliżu marnuje czas (koszt ~30 pól = ~60 s).

R9 12:03 | HP 200 (100%) | mana 96 | cap 53 oz | exp 17000 (+40 od 12:02, +110 od 12:00; ~2000/h w ostatnich 5 min) | poz. z9 (32495,32289) | walka i loot, bot żyje | UH nadal wyłączone
  - 12:03:23 loot: zwłoki (0,0) zamiast (-1,0): fallback, "pod nogami" działa, to dobry znak. Zwłoki zebrane po lootcie.
  - Mana 96/125, rośnie ~10 na minutę. Przy tym tempie bot ma manę do 125 za ok. 3 min; UH bez potrzeby many nie jest w tej chwili przeszkodą (HP 100%).

## Loot vs dobijanie (dodatkowe zadanie od Karola, dane z logu 11:39-12:04)

1) Zwłoki vs cele
- Zabitych celów (linie "zabity na"): 21 w ~25 min logu (11:39-12:04).
- Pełne sesje lootu "[LOOT] (...)": 5. Linie "Loot: ok": 9. Linie "Loot: brak_okna": 3 (plus 4 "brak_okna" w trybie walki).
- Odłożony loot ("Loot odłożony ... najpierw walka"): 16 razy. Każde odłożenie kończy się pod koniec walki; w wielu przypadkach zwłoki nie są zebrane w ogóle (różnica 21 zabitych vs 5 pełnych sesji).
- Loot w walce ("Loot w walce:"): 6 prób, WSZYSTKIE 6 przerwane: "cel_daleko" 2 razy (11:55:37, 11:57:34), "brak_okna" 4 razy (12:00:49, 12:01:11, 12:01:33, 12:04:06). Przy trzech próbach z rzędu na tych samych zwłokach (32510,32281) bot klikał ten sam pusty punkt za każdym razem (ok. 6 s).
- Loot gdy żywy mob blisko: w 6 z 6 prób w walce żywy troll/ork był w 1-2 polach (HP 90-100%). Odłożony loot przy trollu w zasięgu 1 pola: 16 razy.
- Czas: pojedyncza próba lootu w walce to 1-2 s, pełna sesja z gold coin ok. 3-8 s (np. 11:59:21-11:59:27). Razem ok. 2-3 min z ~25 min logu, czyli ok. 10%.

2) Cele niedobite
- "ucieka przy ~25-27% HP": 16 zdarzeń (np. 11:42:45, 11:48:33, 11:55:30, 12:00:19). Zaobserwowane HP uciekającego 18-30%.
- "wyszedł z widoku / zniknął z widoku": 4; "Odpuszczam": 1 (11:59:31, trol 7 pól).
- "Zmiana celu" na świeżego: 3 (11:47:46, 11:48:36, 11:55:49). W każdym przypadku poprzedni troll był w ucieczce (26%), a bot przechodził na świeżego 100% w odl. 3-5.
- Wskaźnik dobicia z OBSERWATORA (okno 5 min): 50%, 67%, 43%, 62%, 57%, 78% (ostatni 12:03:28, 9 epizodów). Główny powód: cel zniknął z widoku żywy.
- Szacunek: około 16 uciekających trolli, z których część została dobita (widoczne zabójstwa po 26%), a 4-5 znikło z widoku. Dokładne liczby wymagają pełnego logu.

3) Czy loot i zmiana celu zabierają czas?
- Hipoteza silna: tak. Zmiana na świeżego 100% trolla (11:48:36, 11:55:49) następuje zaraz po ucieczce rannego (26%). Rannego wtedy się nie dobija, a exp z dobicia przepada (OBSERWATOR 12:00:23: ok. 80 exp straconych, 50% potencjału).
- Loot w walce 1-2 pola od żywego trolla: każda próba przerwana, bot i tak wraca do walki. Zysku nie ma, a koszt to kilka sekund bez ataku.
- Powrót na patrol po lootcie (12:02:16, 16 pól; 12:02:50, 11 pól): w tym czasie pojawiają się nowe trolle 7 pól dalej, na które bot wraca dopiero po dojściu.

4) Propozycje (dowód -> zmiana -> ryzyko)
A. Priorytet dobicia nad lootem: jeśli w promieniu 3 pól jest mob z HP < 30% (uciekający), najpierw go gonić, dopiero potem zwłoki. Dowód: 11:48:33-11:48:36 (troll 26%, bot przeszedł na świeżego); 12:00:19 OBSERWATOR 80 exp straconych. Ryzyko: zwłoki mogą zniknąć przy długim gonieniu, a ucieczka może prowadzić dalej od patrolu.
B. Zakaz powtórnego "brak_okna" na tych samych zwłokach w tej samej walce: po jednej nieudanej próbie oznaczyć zwłoki na czas walki i przejść do celu. Dowód: 12:00:49, 12:01:11, 12:01:33 (trzy próby na (32510,32281), ok. 6 s). Ryzyko: niski, dane do zebrania po walce mogą się zdezaktualizować.
C. Zwłoki na innym piętrze: przed Ctrl+klikiem sprawdzić z, a przy różnicy poziomów odłożyć loot. Dowód: 11:54:03 (zwłoki z z9, bot na z8, brak_okna), 11:53:56. Ryzyko: średnie, zwłoki mogą zostać bez lootu (ok. 2-3 w ostatnich 25 min).

Uwaga: w tej sekcji nie zmieniano kodu ani żadnych plików poza obserwacja-1013.md. Hipotezy zaznaczone jako hipotezy.

R10 12:05 | HP 200 (100%) | mana 116 | cap 53 oz | exp 17060 (+60 od 12:03, +170 od 12:00; ~2000-2400/h) | poz. z8 (32486,32293) | walka z trollem, potem patrol, bot żyje | UH nadal wyłączone (wg R0: do ~12:17)
  - 12:05:30 OBSERWATOR [ok]: dobicie 88% przy 8 epizodach (powyżej progu 85%). Poprawa względem 43% (11:59) i 57% (12:02).
  - 12:04:29 OBSERWATOR [ok]: okno 5 min czyste, 7 z 7 dobitych (100%).
  - Pozytywnie: loot po zabiciu odłożony do końca walki (12:05:28), potem zebrany.

R11 12:06 | HP 200 (100%) | mana 125 (pełna) | cap 53 oz | exp 17100 (+40 od 12:05, ~2400/h) | poz. z8 (32487,32293) -> patrol m6 | walka zakończona, zabity troll 12:06:13, loot ok, bot żyje | UH nadal wyłączone
  - Mana pełna (125): UH/exura nieużywane, ale to zbędne przy HP 100%.
  - Ostatni wpis UH w logu 11:47:30 (3 porażki "blank w pojemniku na runy poza oknem"). Brak nowych prób UH od tego czasu. Wznowienie zaplanowane ok. 12:17.
  - 12:06:18 "[LOOT] odłożone (32481,32294,8)": loot na patrolu odłożony do dalszej pracy, ok.

R12 12:08 | HP 193 (~97%) | mana 125 | cap 53 oz | exp 17100 (bez przyrostu od 12:06, ~2 min bez zabójstw; wcześniej 2400/h) | poz. z9 (32483,32297), patrol m6 i walka z rotwormami/trollami, bot żyje | UH nadal wyłączone
  - 12:08:35 OBSERWATOR [problem]: dobijanie 38% w oknie 5 min, utracone 100 exp (62% potencjału), główny powód: cel zniknął z widoku żywy.
  - 12:08:41-12:08:43: troll zabity, nowy cel 44% HP w odl 1, potem "Loot w walce przerwany: brak_celu" po 0.6 s, i od razu "patrol m6 8 pól" oraz nowy troll 100% w odl 5. Dobicie 44% nie zostało potwierdzone (brak ucieczka/zniknięcie w logu). Hipoteza: po zabiciu cel z 44% zmienił się w świeży 100% bez dobicia.

R13 12:09 | HP 193 (~97%) | mana 125 | cap 53 oz | exp 17100 (bez zmian 12:06-12:09, ~3 min bez przyrostu) | poz. z9 (32482,32293), walka z trollem 100% | bot RESTART
  - 12:09:10 bot zrestartowany (stary proces zakończony: log "Przerwano." 12:09:08; nowy log logi/mozg-20261013-1209.log). Nowe nastawy z logu startowego: próg HP 30.0% (było 60/62), UH_AKTYWNY 1 (było 0), UH_KLAWISZ F7, UH_CZAR "adura vita", UH_KOSZT 100, UH_MANA_MIN 100, POGON_LIMIT 30, POGON_ZASIEG 14, POSCIG_TRZYMAJ 1.
  - Od tej chwili UH włączone. Zgodnie z poprzednim wpisem (UH wyłączone do ~12:17) wyłączenie 30 min z 11:47 już nie obowiązuje po restarcie (stan nie jest trwały, wg wpisu startowego). DO SPRAWDZENIA w logu 1209: pierwsze próby UH i "blank" poza oknem.
  - Nowy wpis startowy: czat odczytuje stare wpisy "ja" 'exura' (11:49, 11:50, 11:53) jako "ręczne". Hipoteza: po restarcie bot błędnie odczytuje historię czatu jako świeże wpisy właściciela; sprawdzić, czy to nie wpływa na decyzje.
  - Mana 125 >= UH_MANA_MIN 100, więc warunek many spełniony; koszt 100 mieści się w manie. Przy pełnej manie UH zadziała, jeśli okno (F7) jest widoczne.
  - 12:09:19 próbka: mana 125 -> 25 przy HP 198, exp 17120. Spadek many to ręczny "adura vita" o 12:09:22 (log: "ręczny", bot nie wysłał). Bot nie użył UH, bo UH_MIN_HP 90 nie był spełniony. Nie traktować jako próby UH bota.
  - Nowe nastawy: UH_MIN_HP 90, UH_MOB_DYSTANS 10 (domyślnie 3). Od restartu bot ma UH aktywny przy HP < 90%.

R14 12:11-12:12 | HP 200 (100%) | mana 45 (rośnie, ok) | cap 52 oz | exp 17180 (+80 od 12:09, ~+60 od 12:10; ~2400/h) | poz. z8/z9 (32482,32296), walka z trollem 30%->8%, bot żyje | bot z nowymi nastawami (log 1209)
  - UH w logu 1209 dotąd bez prób (HP 200, brak potrzeby). Brak "blank poza oknem".
  - 12:11:38 "Rozprawa skończona, wracam do dobicia: Troll HP 30% (odl 6)" -> "Droga zablokowana przez Troll (...)" -> nowy cel HP 8%: dobicie działa, cel dobity w 12:11:43.
  - 12:11:43 "Loot odłożony: Troll 3 pól": loot odłożony do końca walki, zgodnie z zasadą.
  - Cap 53 -> 52: zbieranie łupu zmniejsza cap; cap nie spadł do niskich wartości.

R15 12:12 | HP 200 (100%) | mana 55 | cap 52 oz | exp 17220 (+40 od 12:11, +120 od 12:09; ~2400/h) | poz. z9 (32490,32297), walka z trollami, bot żyje | bot z nowymi nastawami (log 1209)
  - 12:12:03 zabity troll 30%, potem troll 100% w odl 1: dobicie działa.
  - 12:11:23 OBSERWATOR [uwaga]: w jednej minucie 6 odpuszczeń "za ścianą (droga naokoło: brak)" i tylko 1 zabicie. Hipoteza: w jednym miejscu (okolice 32485-32490,32296-32302) trolle stoją za ścianą; bot odpuszcza cele bez drogi. Sprawdzić przy następnej rundzie, czy wzorzec wraca.
  - 12:12:24 OBSERWATOR [ok]: seria odpuszczeń się nie powtórzyła (2 zabicia w minutę).

R16 12:14-12:15 | HP 200 (100%) | mana 75 | cap 52 oz | exp 17260 (+40 od 12:12, ~1600/h ostatnie 15 min) | poz. z8 (32478,32274), walka z trollami, bot żyje | bot z nowymi nastawami (log 1209), UH aktywny (nie użyty: HP 100%)
  - 12:14:03 "Troll ucieka przy ~25% (zaobserwowano 12%)": ucieczka przy 12%, poniżej 14-18% dobicia (trzeba sprawdzić, czy trafił kliknięciem).
  - 12:14:29 OBSERWATOR [ok]: brak odpuszczeń w ostatniej minucie.

## Podsumowanie (obserwacja 11:52-12:15, bot żyje)

Stan: bot żyje cały czas, HP 100% od 12:00, exp 16770 (11:52) -> 17260 (12:14) = +490 w ~22 min, ok. 1340 exp/h; ostatnie 15 min ok. 1600 exp/h. Restart 12:09:10 (próg 30%, UH włączone, log 1209).

Największe problemy:
1. Dobijanie: wskaźnik 43-57% (11:59-12:02) i 38% (12:08:35), potem 78-100%. Straty ok. 60-100 exp na okno. Główny powód: cel znikł z widoku żywy lub zmiana na świeży 100%.
2. Loot: 6 z 6 prób w walce przerwanych (cel_daleko, brak_okna, brak_celu); 16 odłożonych lootów; 3x brak_okna na tych samych zwłokach (12:00:49-12:01:33). Ok. 10% czasu.
3. Ucieczka 11:50:28 (HP 64%, próg 62%) trwała 156 s bez UH (UH wyłączone 11:47 po 3 porażkach) i z manią 2-25: leczenie exurą nie działało, a model w decyzji pisał "próg 50%".

Propozycje (problem, dowód, zmiana, ryzyko):
1. Dobicie przed lootem. Dowód: 11:48:33-36, 12:08:41-43. Zmiana: cel HP<30% w odl<=3 ma pierwszeństwo nad lootem i nad zmianą celu. Ryzyko: zwłoki mogą zniknąć przy długim gonieniu.
2. Nie przełączać na świeżego trolla, gdy poprzedni ma HP<30% i jest w odl<=3. Dowód: 11:47:46, 11:48:36, 11:55:49 (hipoteza). Ryzyko: dłuższe walki z jednym trollem.
3. Po jednym "brak_okna" na tych samych zwłokach w walce odłożyć je do końca walki. Dowód: 12:00:49, 12:01:11, 12:01:33 (ok. 6 s). Ryzyko: niskie.
4. Zwłoki na innym piętrze: sprawdzić z przed Ctrl+klikiem. Dowód: 11:53:56-11:54:03. Ryzyko: średnie (zwłoki zostają).
5. Ucieczka przy HP<60% powinna włączać UH/leczenie i mieć manę (UH_MANA_MIN 100 już ustawione). Dowód: 11:50:28-11:53:04 (156 s, HP 64->84%, mana 2-25). Ryzyko: zużycie many na UH zamiast ataków.
6. Próg w promptcie decyzji modelu zgodny z progiem z pliku mapy. Dowód: 11:50:38 "próg 50%" przy progu 62%. Ryzyko: niskie.
7. Jedzenie w walce tylko przy HP<70%. Dowód: 11:56:22 jedzenie przy HP 90% ("HP nie rośnie 33 s", ham). Ryzyko: niskie.
8. Patrol nie zmieniać na punkt 31 pól od miejsca, gdzie są trolle w zasięgu 7. Dowód: 12:02:57 "m6, droga 31 pól". Ryzyko: pętla patrolu, trzeba limitu.
9. Etykieta "dojście 935 s" w logu patrolu to czas od ostatniej wizyty, nie dojście. Dowód: 12:02:57. Ryzyko: brak, poprawić opis w logu.
10. Po restarcie czat czyta stare wpisy "ja" (11:49-11:53) jako ręczne (12:09:10). Hipoteza: filtrować po czasie od startu. Ryzyko: pominięcie świeżych wpisów właściciela.

Uwagi: UH po restarcie aktywne (UH_AKTYWNY 1), ale nie użyte (HP 100%). Proces bota (PID 3022628) i próbkowanie probki.py działają; nie zatrzymywałem ich. Wpis "Przerwano." 12:09:08 to zamknięcie starego procesu bota (nie przeze mnie).
12:43 STOP: bot zatrzymany (plik STOP, log 'Zatrzymano' 12:43:10), prawdopodobnie ręcznie przez Karola; nie restartuję.
12:52 bot zatrzymany po dotarciu do depo (koniec wyprawy, STOP zapisany przez bota); czeka na decyzje o powrocie.
