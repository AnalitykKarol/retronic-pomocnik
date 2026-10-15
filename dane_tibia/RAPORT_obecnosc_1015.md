# Raport: mapa obecności i patrol według respawnu (15.10, krok 1)

Wygenerowany przez `python3 -I obecnosc.py --raport` (tylko odczyt telemetrii). Bot się nie zmienia.

## 1. Dane

- Pliki: telemetria-20261014.jsonl, telemetria-20261015.jsonl; rekordy użyte: 44027 (uszkodzonych linii: 0); próbek: 40606; sesji: 33.
- Obszar: x 32465-32515, y 32250-32305, z 8-9; komórki 4x4, widok 15x11 pól; cele-moby: troll.
- Komórek z danymi (>= 10 s w widoku): 170; zabić przypisanych komórkom: 941.
- Zdarzeń `patrol_cel` w jaskini (miejsca m1..m8 osiągalne z pozycji bota): 386 z 619 (dni: 14.10, 15.10); pozostałe to patrol poza jaskinią (miasto, inne piętra), pomijane.

## 2. Gęstość (średnia liczba trolli w komórce, gdy była w widoku)

Wygładzona wartością domyślną (waga 120 s). Uwaga: to gęstość stanu faktycznego, z udziałem zabić bota (bot sam czyści komórki, więc wartości są lekko zaniżone).

| komórka (x,y,z) lewy-górny róg | gęstość | czas w widoku [min] | zabicia | respawn mediana [s] |
|---|---|---|---|---|
| (32484,32296,z9) | 0.93 | 48 | 53 | 519 |
| (32472,32272,z9) | 0.69 | 29 | 22 | 791 |
| (32496,32268,z8) | 0.68 | 71 | 57 | 376 |
| (32500,32268,z8) | 0.48 | 80 | 68 | 370 |
| (32480,32292,z8) | 0.41 | 80 | 79 | 302 |
| (32504,32268,z8) | 0.25 | 50 | 14 | 449 |
| (32496,32280,z9) | 0.24 | 114 | 41 | 306 |
| (32508,32272,z8) | 0.23 | 14 | 11 | 3438 |
| (32488,32288,z8) | 0.22 | 74 | 43 | 390 |
| (32472,32268,z9) | 0.22 | 23 | 2 | 996 |
| (32488,32292,z8) | 0.20 | 80 | 34 | 235 |
| (32484,32300,z9) | 0.18 | 27 | 23 | 761 |
| (32476,32272,z9) | 0.17 | 29 | 24 | 1154 |
| (32488,32296,z9) | 0.16 | 42 | 29 | 928 |
| (32500,32272,z8) | 0.15 | 49 | 26 | 619 |

## 3. Respawn (czas od wyczyszczenia komórki do następnego moba w niej)

Start odliczania: pierwsza obserwacja komórki w widoku i pustej po tym, jak był w niej mob (albo zabicie); koniec: następna obserwacja moba w komórce. Tylko komórki, które bot widział (w całości w widoku). Przypadek "dokładny" = bot patrzył na komórkę ciągle (przerwy <= 10 s), "luka" = bot wrócił po czasie, więc to górne ograniczenie (mob mógł się pojawić wcześniej, a nawet wejść i wyjść). Moby wchodzące z sąsiednich komórek też liczą się jako powrót obecności. Przypadki krótsze niż 30 s odrzucam (to sąsiad z grupy, nie respawn); liczba dokładnych przypadków po filtrze jest niska, a rozkład dwumodalny, więc prawdziwy czas respawnu jest tylko przybliżony (UNKNOWN dokładnie).

| zbiór | przypadków | Q1 [s] | mediana [s] | Q3 [s] | P90 [s] |
|---|---|---|---|---|---|
| wszystkie | 1075 | 284 | 465 | 1074 | 2807 |
| dokładne (ciągły widok) | 8 | 32 | 39 | 43 | 44 |
| z luką w widoku | 1067 | 291 | 471 | 1084 | 2807 |

Komórek z własnym respawnem (>= 5 przypadków): 38; kwartyle ich median (Q1/mediana/Q3/P90): 466/928/1543/2929 s.
Respawn globalny używany przez model: 465 s (domyślny 300 s).

## 4. Symulacja wyboru celu patrolu

Dla każdego historycznego `patrol_cel` odtwarzam mapę obecności z danych WYŁĄCZNIE sprzed tej chwili (próbki, zabicia z `epizod_celu`) i oceniam wszystkie miejsca z `trasy/miejsca_troll.json` (m1..m8).

Założenia (uczciwie):
- Droga: A* z `mapa.py` (pola przechodnie z minimapy + `znane_pola.json`) na piętrze do węzłów grafu, dalej graf z pliku miejsc (`graf.odl`, `przejscia`, `laczniki`) algorytmem Dijkstry. Czas = pola x 0.4 s + 3 s za przejście pięter. Miejsca bliżej niż 3 pola od bota odpadają (jak `PATROL_ODL_MIN`); reszty reguł bota (ostatnie 4 wizyty, runda, gniazda wymagające HP/many, blokady) NIE odtwarzam, więc nowa metoda ma tu więcej swobody niż bot.
- Wartość = suma oczekiwanych mobów w unikalnych komórkach drogi i miejsca (promień 4 pól) / max(czas, 10 s), komórka przy obcym graczu (<= 10 pól) x 0.2. Pewność = udział komórek z danymi x przewaga nad drugim; próg domyślny 0.15.
- Mapa uczy się w trakcie odtwarzania: początek (pierwsze godziny) to mapa prawie pusta (gęstość domyślna), więc wartości z początku są słabe i pewność niska.
- Kontrfaktycznego wyniku (ile zabić dałby inny wybór) NIE znamy: wiemy tylko, co się stało po wyborze bota. Stąd ocena pośrednia: kalibracja (czy wartość modelu przewiduje zabicia wizyt bota) i zgodny/niezgodny z modelem.

- Zdarzeń `patrol_cel`: 619; ewaluowalnych (wybór bota osiągalny w modelu, >= 2 kandydatów): 366; z wynikiem wizyty: 350.

### 4a. Czy nowa metoda wybrałaby inaczej

| próg pewności | zdarzeń z pewnością >= próg | wybrałaby inne miejsce niż bot | odsetek |
|---|---|---|---|
| 0.00 | 366 | 291 | 80% |
| 0.05 | 302 | 242 | 80% |
| 0.10 | 258 | 203 | 79% |
| 0.15 | 215 | 165 | 77% |
| 0.25 | 125 | 94 | 75% |
| 0.40 | 63 | 46 | 73% |

### 4b. Oczekiwane moby po drodze i przy miejscu (wg samego modelu, więc to nie dowód na rzeczywiste zabicia)

W 291 zdarzeniach, gdzie nowy wybór != wybór bota (bez progu pewności):

| | oczekiwane moby na drodze+miejscu | wartość (moby/s) | czas dojścia (model) [s] |
|---|---|---|---|
| wybór bota | 0.42 | 0.0219 | 17 |
| nowa metoda | 0.98 | 0.0506 | 23 |

Średnio oczekiwanych mobów na drodze+miejscu (wszystkie ewaluowalne): bot 0.54, nowa 0.99.
Nowa metoda z definicji maksymalizuje wartość (moby/s), więc ta tabela pokazuje tylko, jak duża jest różnica w oczach modelu, nie czy model ma rację.

### 4c. Czy model ma sygnał: wartość wybranego przez bota celu a faktyczne zabicia wizyty

Wizyt z wynikiem: 350, średnio 2.53 zabić na wizytę (na miejscu + w drodze).
- Spearman(wartość modelu, zabicia wizyty) = 0.600; (oczekiwane moby, zabicia) = 0.743; (wartość, zabicia na minutę dojścia) = 0.622; (ranga wyboru bota w rankingu modelu, zabicia) = 0.625.

| kwartyl wartości wybranego celu | zakres wartości | wizyt | zabicia / wizyta | zabicia / min dojścia |
|---|---|---|---|---|
| Q1 | 0.0001 - 0.0118 | 87 | 0.78 | 1.44 |
| Q2 | 0.0118 - 0.0199 | 88 | 1.66 | 1.64 |
| Q3 | 0.0200 - 0.0351 | 87 | 3.59 | 2.05 |
| Q4 | 0.0354 - 0.3040 | 88 | 4.07 | 2.42 |

| wybór bota względem modelu | wizyt | zabicia / wizyta | zabicia / min dojścia | wizyt bez zabicia |
|---|---|---|---|---|
| zgodny z modelem (model wybrałby to samo) | 71 | 4.25 | 2.35 | 4% |
| niezgodny z modelem | 279 | 2.09 | 1.89 | 34% |

Kontrola zakłócenia: kto jeszcze przewiduje zabicia wizyty?

| predyktor | Spearman z zabiciami wizyty |
|---|---|
| sam czas dojścia wg modelu (dłuższa droga = więcej walk) | 0.655 |
| liczba komórek na drodze i przy miejscu | 0.616 |
| tylko gęstość historyczna / czas (bez zegara respawnu) | 0.073 |
| tylko zegar respawnu / czas (bez gęstości) | 0.236 |
| pełna wartość modelu | 0.600 |

Korelacja cząstkowa (po odjęciu liniowego wpływu rang wymienionych zmiennych):

- pełna wartość | czas dojścia: 0.559; | gęstość i czas: 0.525; | gęstość, czas i liczba komórek: 0.523.
- sam zegar respawnu | gęstość i czas: 0.358.

Wybór bota względem najlepszej wartości modelu (trzy równe przedziały stosunku wartość_bota / wartość_najlepsza):

| przedział stosunku | wizyt | zabicia / wizyta | zabicia / min dojścia | wizyt bez zabicia |
|---|---|---|---|---|
| 0.00 - 0.35 | 116 | 0.99 | 1.59 | 54% |
| 0.35 - 0.73 | 117 | 2.64 | 1.93 | 23% |
| 0.76 - 1.00 | 117 | 3.93 | 2.26 | 7% |

Szacunek górny (ekstrapolacja z kwartyli, zakłócona długością drogi, NIE prognoza): w 291 zdarzeniach z innym wyborem przewidywane zabicia/min dojścia: bot 1.78, nowa metoda 2.29 (+29%). Dojścia to ok. 35% czasu, więc w exp/h zysk byłby wielokrotnie mniejszy; offline nie da się go policzyć wiarygodnie, bo wynik innego wyboru jest nieznany.

### 4d. Wizyty w komórki świeżo wyczyszczone (< 300 s)

Świeże = co najmniej połowa komórek przy miejscu ma czas odniesienia (ostatnio pusta w widoku / po zabiciu) młodszy niż 300 s. Liczone tam, gdzie mapa ma w ogóle jakąś informację o komórkach miejsca.

- Wizyt bota z informacją o komórkach miejsca: 359; z tego świeżych: 193; nowa metoda wybrałaby świeże: 66 razy (na tych samych zdarzeniach).

| wizyty bota | wizyt | zabicia / wizyta | zabicia / min dojścia | wizyt bez zabicia |
|---|---|---|---|---|
| do świeżo wyczyszczonych | 186 | 1.85 | 1.91 | 42% |
| do pozostałych (z informacją) | 158 | 3.27 | 2.10 | 13% |

### 4e. Kalibracja czasu dojścia

Stosunek faktycznego `dojscie_s` do czasu modelu (pola x 0.4 s + schody) dla wizyt, które dotarły i nie miały zabić (91): Q1/mediana/Q3/P90 = 1.13/1.29/1.65/2.56.

### 4f. Warianty i kontrola zakłócenia

Zakłócenie: bot wybiera miejsce zwykle zaraz po walce, gdy trolle są w widoku i na drodze, więc sama obecność mobów w widoku "przewiduje" kolejne zabicia, bez żadnego zegara respawnu. Stąd warianty: `bez świeżych` = model bez wzmocnienia komórek ze świeżym mobem (został tylko zegar od wyczyszczenia i gęstość); `widok pusty` = tylko zdarzenia, gdy w chwili wyboru w widoku nie było żadnego trolla; `promień 1` = droga rozszerzona o sąsiednie komórki.

| wariant | wizyt | Spearman(wartość, zabicia) | Spearman(wartość, zab./min) | zgodne zab./min (n) | niezgodne zab./min (n) | inny wybór niż bot | decyzji pewnych / z nich inny wybór |
|---|---|---|---|---|---|---|---|
| model pełny (jak raport) | 350 | 0.600 | 0.622 | 2.35 (71) | 1.89 (279) | 80% | 215 / 77% |
| bez świeżych | 350 | 0.602 | 0.605 | 2.34 (70) | 1.89 (280) | 80% | 215 / 77% |
| pełny, widok pusty | 344 | 0.596 | 0.615 | 2.35 (71) | 1.89 (273) | 79% | 213 / 77% |
| bez świeżych, widok pusty | 344 | 0.600 | 0.603 | 2.34 (70) | 1.89 (274) | 79% | 212 / 76% |
| pełny, pierwsza połowa zdarzeń | 176 | 0.564 | 0.630 | 2.24 (33) | 1.83 (143) | 81% | 71 / 73% |
| pełny, druga połowa zdarzeń | 174 | 0.629 | 0.638 | 2.43 (38) | 1.97 (136) | 78% | 144 / 78% |
| promień 1 | 350 | 0.652 | 0.640 | 2.41 (54) | 1.90 (296) | 84% | 179 / 82% |
| promień 1, bez świeżych, widok pusty | 344 | 0.654 | 0.626 | 2.41 (54) | 1.90 (290) | 84% | 179 / 82% |

## 5. Wnioski (z liczb powyżej)

- Wartość modelu wybranego przez bota celu koreluje z zabiciami wizyty (Spearman 0.600), ale sama długość drogi koreluje podobnie (0.655): dłuższe dojście = więcej walk po drodze. Po odjęciu wpływu czasu i gęstości zostaje 0.525 (zegar respawnu sam: 0.358).
- Gęstość historyczna bez zegara prawie nic nie przewiduje (0.073), zegar respawnu bez gęstości więcej (0.236): czas od wyczyszczenia niesie informację, której stały rozkład gęstości nie ma.
- Zabicia/wizyta w kwartylach wartości: Q1 0.78, Q2 1.66, Q3 3.59, Q4 4.07; na minutę dojścia: 1.44 / 1.64 / 2.05 / 2.42.
- Wizyty zgodne z modelem: 2.35 zabić/min dojścia (n=71), niezgodne: 1.89 (n=279).
- Do świeżo wyczyszczonych (< 300 s): 1.85 zab./wizyta, 42% bez zabicia (n=186); do pozostałych: 3.27, 13% bez zabicia (n=158).

- Nowa metoda wybrałaby inne miejsce niż bot w 80% zdarzeń (przy progu pewności 0.15: 77% z 215 decyzji), czyli często; szacunek górny zysku na minutę dojścia +29%.

Werdykt: model ma WALIDACJĘ PREDYKCYJNĄ (wartość przewiduje zabicia ponad samą długość drogi i gęstość), ale to NIE jest pomiar zysku: wyniku innego wyboru nie znamy, a bot wybierał własnymi regułami (blisko, po wagach), więc część sygnału to pamięć tego, gdzie trolle niedawno były w drodze bota. Zysk w exp/h rozstrzygnie dopiero tryb cienia, a potem A/B (krok 3).

Ograniczenia: wynik wizyty zależy też od walk w drodze, których wybór miejsca nie kontroluje; odtwarzam tylko część reguł bota; zabicia liczone z `epizod_celu` (pozycja zabitego), moby z próbek co ~1-5 s; respawn jest tylko przybliżony (patrz sekcja 3); mapa uczy się w trakcie na tych samych danych, na których ocenia (kauzalnie: tylko dane sprzed chwili wyboru, ale początek to mapa prawie pusta); dwa dni danych, jedna jaskinia.
