# Budżet czasu bota, 11.10.2026 17:01-18:20 (analiza read-only)

Dane: telemetria-20261011.jsonl (probka co ok. 1,4 s) + mozg-20261011-*.log. Skrypty: scratchpad/budzet/ (load.py, bud.py, kpi.py, rep.py, rep2.py).
Stan gry z socketu o 18:22: exp 3281, lvl 7, do lvl 8 (4200) brakuje 919 exp = ok. 184 szczurów.

## Okna i jak liczone

- A: 17:01:00-18:20:00 (79 min ściany zegara), 107 zabić, +547 exp.
- Wyłączone z oceny tempa: bot wyłączony 17:27:19-17:35:23 (484 s, restart), wypad nr 1 17:23:42-17:27:19 (209 s, bez zakupów, 6 nieudanych prób liny), wypad nr 2 17:36:27-17:42:54 (387 s, kupione 5 pochodni, w tym czasie i tak 9 zabić, +50 exp), przerwa 18:00:58-18:04:31 (210 s).
- C (czysty odcinek, po poprawce lootu pod nogami i po wypadzie): 17:42:54-18:20:00 = 37,1 min, bez przerwy 33,6 min, 59 zabić, +295 exp.
- P (przed poprawką, do pierwszego wypadu): 17:01:00-17:23:42 = 22,7 min, 34 zabicia, +178 exp.
- Uwaga metodyczna: próbkowanie milknie w trakcie lootu (luki 5-37 s), więc stan z `probka` sam zawyżałby walkę. Luki przypisałem po zdarzeniach z logu tekstowego (zabity / [LOOT] / Ctrl+klik / Loot: wynik / Nowy cel). Dane `zabicie` i `epizod_celu` w telemetrii są wielokrotnie zdublowane (284 `zabicie` vs 95 faktycznych zabić), więc zabicia liczę z logu tekstowego ("Cel Rat zabity") i potwierdzam exp/5.

## 1. Budżet czasu (% ściany zegara)

| Kategoria | A 17:01-18:20 (79 min) | C czysty 17:42:54-18:20 (37 min, z przerwą) | s na zabicie (C, bez przerwy) | P przed 17:23 (22,7 min) |
|---|---|---|---|---|
| Walka melee (stoi i bije, od "Nowy cel" do zabicia, bez pościgu) | 1332 s, 28,1% | 833 s, 37,4% | 14,1 s | 476 s, 35,0% |
| Pościg (podejście do celu w ruchu) | 189 s, 4,0% | 135 s, 6,1% | 2,3 s | 52 s, 3,8% |
| Dojście/trasa/szukanie celu (IDZ) | 1094 s, 23,1% | 577 s, 25,9% | 9,8 s | 496 s, 36,4% |
| Loot po walce (czekanie na zwłoki, szukanie, otwarcie, zbieranie, jedzenie) | 738 s, 15,6% | 435 s, 19,5% | 7,4 s | 290 s, 21,3% |
| Loot w walce | 74 s, 1,6% | 31 s, 1,4% | 0,5 s | 43 s, 3,2% |
| Przerwa (PRZERWA, 207 s) | 210 s, 4,4% | 210 s, 9,4% | (3,6 s) | 0 |
| Wymiana pochodni | 3 s, 0,1% | 2 s, 0,1% | 0 | 1 s |
| Wypad (2 sztuki) | 604 s, 12,7% | 0 | 0 | 0 |
| Bot wyłączony / restart | 493 s, 10,4% | 3 s | 0 | 2 s |
| Pauzy mózgu (stan MOZG/PAUZA) | 1 s | 0 | 0 | 1 s |
| Razem | 4739 s | 2225 s | 34,1 s/zab | 1361 s |

Pauzy mózgu i czat: patrz sekcja 4. Nie blokują ruchu, więc nie ma osobnej pozycji straty.

Rozbicie lootu w C (bez przerwy 435 + 31 s = 466 s, 7,9 s na zabicie): przed otwarciem (czekanie, dojście do zwłok) 255 s, otwarcie i zbieranie 171 s, w walce 31 s.
Rozbicie walki w C: od "Nowy cel" do pierwszego trafienia mediana 2,8 s (p90 8,3 s), od trafienia do zabicia mediana 8,9 s (p90 17,2 s).

## 2. KPI (czysty odcinek C, dziś) i cele

| KPI | P (przed poprawką) | C (dziś) | Cel |
|---|---|---|---|
| exp/min (bez przerw) | 7,84 | 8,79 | 10,5 |
| exp/min efektywne (z przerwami 9,1%) | 7,1 | 8,0 | 10,0 |
| zabicia/min | 1,50 | 1,76 | 2,1 |
| ściana zegara na zabicie | 40,1 s | 34,1 s | 28 s |
| Nowy cel -> zabity (mediana / p90) | 16 / 23 s | 14 / 22 s | 12 / 18 s |
| Skuteczność dobicia (zabite / zabite+naprawdę utracone) | 34/35 = 97% | 59/60 = 98% | utrzymać 98% |
| Exp utracony | 1 szczur | 1 szczur w 37 min (18:16:53, cel 5% HP, 40 s pościgu, odpuszczony) = 5 exp, 1,5% | 0 |
| Epizody "zgubiony" w telemetrii | 4 | 7, z czego 6 to zmiana celu na blokującego, ten sam szczur zabity chwilę później | - |
| Loot: zabity -> pierwszy klik w zwłoki (nieodłożone), mediana / p90 | 12 / 15 s | 5,0 / 33 s | 3 / 10 s |
| Loot: zabity -> pierwszy klik (odłożone na koniec walki) | 29 / 44 s | 17 / 29 s | 10 / 20 s |
| Loot: zabity -> "Loot: wynik" (mediana / p90 / średnia) | 15 / 38 / 19,8 s | 10 / 34 / 16,5 s | 7 / 20 / 10 s |
| Loot: Ctrl+klik -> ok (mediana / p90) | 6 / 20 s | 5 / 9 s | 4 / 7 s |
| Loot ok wg telemetrii `loot.s` (mediana / p90) | 7,0 / 11,4 s | 6,7 / 10,4 s | - |
| Odsetek "pod nogami" (z wyszukań zwłok) | 0% | 54% (20 z 37) | bez zmian |
| "Loot: brak_okna" (z prób) | 3 z 34 (9%) + 2 "stoję na zwłokach" | 12 z 59 (20%), tylko 4 odzyskane ponowieniem | < 8% |
| Zwłoki bez wyniku ok (zabite - ok - w walce) | 0 z 34 (0%) | 14 z 59 (24%) | < 8% |
| Loot odłożony ("najpierw walka") | 23 z 34 (68%) | 27 z 59 (46%) | - |
| Loot w walce obsłużony | 7 z 34 (21%) | 3 z 59 (5%) | 20-30% |
| Bezczynność > 10 s bez zmiany pozycji, poza melee | 19 luk, 324 s (24%) | 29 luk, 398 s (20% czasu bez przerwy), z czego 26 przy zabiciu/lootcie | < 10 luk, < 120 s |
| Zapytania modelu | 39 (5,6 s) | 61 (średnio 5,7 s, $0,0008, 19 zdarzeń, 17 z czatu) | - |

Wniosek z tabeli: poprawka "pod nogami" działa (0% -> 54% trafień pod nogami, loot od zabicia do wyniku 15 -> 10 s, wall/zabicie 40 -> 34 s), ale odsetek zwłok bez wyniku wzrósł z 0% do 24% (loot w walce spadł z 21% do 5%, brak_okna z 9% do 20%). To nie kosztuje exp, tylko ser (jedzenie) i złoto, ale każdy nieudany loot to średnio 9,8 s (108 s na 11 sekwencji w B).

## 3. Ile szczurów jest w zasięgu (gęstość spotu vs bot)

- Odstęp "Nowy cel" -> "Nowy cel": mediana 21 s, średnia 31,8 s (C), 23 / 31,5 s (P).
- Czas bez celu (IDZ między walkami): 27 przejść w C, średnio 17,3 s, mediana 13,3 s, p90 29,5 s, 11 z 27 trwa >= 20 s. Suma 466 s w C, to 26% ściany zegara (+ ok. 130 s szukania wewnątrz luk próbkowania).
- W stanie IDZ w 87% próbek nie ma w polu widzenia żadnego potwora, 13% próbek ma szczura w widoku, którego jeszcze nie atakujemy (pościg zaraz się zacznie).
- W walce widać 2+ potworów w 45% próbek WALKA (201+59+14 z 613): szczury przychodzą skupiskami.
- Rozkład po trasie kanaly2 (195 pkt, biny po 20 pkt, zabicia / sekundy IDZ w binie): bin 0: 10 / 141 s, bin 1: 0 / 66 s, bin 2: 33 / 156 s, bin 3: 7 / 155 s, bin 4: 5 / 17 s, bin 5: 1 / 36 s, bin 6: 22 / 144 s, bin 7: 5 / 158 s, bin 8: 12 / 98 s, bin 9: 1 / 21 s. Biny 0, 2, 6, 8 dają 77 z 96 zabić (80%) w 54% czasu IDZ, pozostałe 6 binów 19 zabić w 46% czasu.
- Ocena: spot daje szczura średnio co 17 s marszu (ok. 20 pól), czyli nie jest ograniczeniem przy dzisiejszych 1,76 zab/min (34 s na zabicie). Dopiero po zejściu z 34 do ok. 26 s na zabicie (walka 16,4 + szukanie ok. 10) trafimy w sufit ok. 2,3 zab/min = 11,5 exp/min, który wyznacza już gęstość i trasa, nie bot. Za dużo czasu IDZ spędzamy na odcinkach o niskiej gęstości (biny 1, 3, 5, 7, 9).

## 4. Pauzy mózgu i czat (czy blokują ruch)

- Model działa w wątku (`_watek_modelu`), wynik trafia do kolejki, `obieg_hybrydy` wykonuje go między tickami. 61 zapytań w C po średnio 5,7 s = 346 s, ale w 15% ściany zegara pokrywają się z oknami zapytań.
- Pomiar wpływu: w IDZ mediana odstępu próbek 1,4 s i w oknie zapytania, i poza nim; prędkość marszu 1,21 vs 1,22 pola/s; w WALKA 1,3 vs 1,2 s. Sampler nie milknie w czasie zapytań. Wniosek: 0 s straty, nie ma czego tu poprawiać.
- Jedyny pośredni koszt: po `brak_okna` loot czeka na model (7,6 s: "Zdarzenie brak_okna_lootu: pytam model" -> "[MOZG] ponowny loot"), 4 odzyskania z 11 prób. Bot sam mógłby ponowić od razu.
- Czat: 17 decyzji z `wiadomosc_czatu` w C, wszystkie "gram dalej", żadna nie zatrzymała ruchu.

## 5. TOP 6 źródeł straty czasu

Baza: 34,1 s na zabicie (bez przerw), 8,8 exp/min, 8,0 exp/min efektywnie z przerwami, 919 exp do lvl 8 = 115 min (ok. 20:16 od 18:22). Zysk liczony jako skrócenie sekund na zabicie dla (34,1 / (34,1 - dt)) i przeliczone na exp/min efektywne.

| # | Źródło | Koszt dziś | Założenie poprawy | Zysk | Do lvl 8 | Typ |
|---|---|---|---|---|---|---|
| 1 | Walka melee: 50% czasu stania w melee to odcinki >= 4 s bez zmiany HP celu (484 s z 967 s w melee po 17:42, mediana odcinka 7 s, 26 odcinków >= 8 s) | 14,1 s/zab (41% ściany) | Jeśli przyczyną jest zgubiona flaga ataku (toggle Alt+klik, ponow_atak) i da się odzyskać 20% czasu melee: -2,8 s/zab. Jeśli to chybienia (niski skill), pomaga tylko lepsza broń/trening: +30% obrażeń to ok. -3,3 s/zab | +0,7 do +0,9 exp/min | -9 do -11 min | najpierw diagnostyka w kodzie (log flagi ataku N+0xE1 w probce), potem fix; broń: decyzja Karola |
| 2 | Przerwy antybotowe (60-300 s co 20-40 min) | 9,1% długoterminowo, 210 s w oknie | PRZERWA_CO (45-90 min), PRZERWA_DLUGOSC (30-120 s): 1,8% | +0,64 exp/min (+8%) | -9 min | stałe (cavebot.py 219-220), restart; kompromis z "No bots" na serwerze, decyzja Karola |
| 3 | Loot po walce: czekanie na pierwszy klik 5 s mediana + nieudane próby (brak_okna 20%, 9,8 s każda) + ponowienie przez model | 7,9 s/zab (23%) | LOOT_RETRY_DALEJ 2 -> 0 (fail-fast, -1,0 s/zab); więcej loot w walce przez pokrętła LOOT_W_WALCE_* (obecnie 5% zabić, cel 25%, -1,3 s/zab). Razem -2,3 s/zab | +0,58 exp/min | -8 min | część stałe (LOOT_RETRY_DALEJ, LOOT_MAKS_PROB, LOOT_W_WALCE_*), reszta kod (ponowienie bez pytania modelu) |
| 4 | Dojście/szukanie celu (IDZ) | 9,8 s/zab (29%) | Przycięcie trasy do binów 0, 2, 6, 8 (przytnij_trase.py): połowa marszu w binach niskiej gęstości znika, minus 10% zabić z odciętych biny: ok. -1,5 s/zab netto | +0,37 exp/min | -5 min | dane trasy (narzędzie jest), wymaga testu na spocie |
| 5 | Pościg (podejście) | 2,3 s/zab (6%), t0->pierwsze trafienie mediana 2,8 s, p90 8,3 s | Ostatnie 30% z latencji kroków (lat_med 0,5 s/krok, 1,2 kroku/s) i z pościgów > 8 s | -0,7 s/zab: +0,17 exp/min | -2 min | kod, już mocno dopracowany |
| 6 | Odpuszczanie uciekającego szczura 40 s (POGON_TWARDY) i losowe pauzy na trasie (PAUZA_DLUGA 3-8 s co 200 kroków, PAUZA_KROTKA) | 1 zdarzenie 40 s w oknie, pauzy ok. 0,7 s/zab | POGON_TWARDY 40 -> 20 s oraz PAUZA_DLUGA szansa 0,005 -> 0,0025 | -0,5 s/zab: +0,12 exp/min | -1,5 min | stałe, mały zysk |

Pozycje które NIE są stratą (zmierzone): pauzy mózgu i czat (0 s), zmiana celu na świeżego (1 przypadek w C), pochodnie (2-3 s na wymianę, następny wypad za ok. 2 h, po lvl 8), unikanie graczy (51 s w A, 1,1%).

Poza botem: łączne kary sufitu sprzętowego. Hit->kill 8,9 s mediana na szczura (20 HP) przy ok. 2 HP na sensowny cios sugeruje słabą broń. Jeśli Karol ma możliwość lepszej broni, to jest największy pojedynczy ruch (pozycja 1).

## 6. Prognoza lvl 8

Start: 18:22, exp 3281, brakuje 919 exp (184 zabić).

| Scenariusz | exp/min efektywne | Czas | Lvl 8 o |
|---|---|---|---|
| Dziś, tempo C z przerwami | 8,0 | 115 min | ok. 20:16 |
| Dziś, bez przerw (jeśli następna wypadnie po 20:00) | 8,8 | 104 min | ok. 20:06 |
| Tempo sprzed poprawek (P, z przerwami) | 7,1 | 129 min | ok. 20:30 |
| Tanie (przerwy + loot fail-fast + pauzy): dt = 1,5 s | 9,0 | 102 min | ok. 20:04 |
| Rekomendowane 1-4 razem (melee -2,8, loot -2,3, trasa -1,5, przerwy 1,8%) | 11,2 | 82 min | ok. 19:44 |

Rzeczywiste tempo będzie się wahać (szczury skupiskami, losowe przerwy). Następna przerwa wypada najwcześniej 18:24, najpóźniej 18:44, a do lvl 8 prawdopodobnie jeszcze jedna lub dwie (średnio 3 min).

## 7. Rekomendowana kolejność wdrożeń

1. Diagnostyka melee (kod, mała): dodać do probki flagę ataku z pamięci i HP celu; potwierdzić czy stalle >= 4 s to chybienia czy zgubiony atak. Równolegle Karol sprawdza broń/skill (największy potencjał).
2. Przerwy: PRZERWA_CO i PRZERWA_DLUGOSC (stałe, restart). Decyzja o ryzyku po stronie Karola.
3. Loot, stałe: LOOT_RETRY_DALEJ 2 -> 0 lub 1, LOOT_MAKS_PROB 3 -> 4 (żeby nie mieć 24% bez wyniku), sprawdzić dlaczego loot w walce spadł z 21% do 5% (przerwania: stykajace, cel_daleko, brak_okna, po 17:35).
4. Loot, kod: ponowienie po `brak_okna` bez pytania modelu (oszczędza 7-8 s na przypadek).
5. Trasa: przycięcie kanaly2 do binów 0, 2, 6, 8 (przytnij_trase.py + waliduj_trase.py), test na 30 min.
6. Pościg / POGON_TWARDY / pauzy: na końcu, mały zysk.

Uwaga ogólna: nic z tego nie przesunie lvl 8 poza wieczór (19:45-20:15), a ryzyko regresji (24% zwłok bez lootu po ostatniej poprawce) warto zamknąć przed dalszym tuningiem.
