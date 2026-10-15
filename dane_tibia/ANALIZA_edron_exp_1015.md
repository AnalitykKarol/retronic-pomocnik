# Analiza exp/h: Edron trolle 15.10 vs poprzednie spoty

Źródła: telemetria-2026101[1-5].jsonl (dev i stabilny), mozg-stdout-1015-1807.log, RAPORT_obecnosc_1015.md, SPEC_patrol_respawn_1015.md.
Metoda: exp/h = przyrost `exp` w próbkach między kolejnymi próbkami odległymi o mniej niż 10 s (bez przerw, wylogowań i dojść do depo). [POTW] = z danych, [HIP] = hipoteza.
Uwaga: każdy troll daje 20 exp (1811 z 1918 zabić; reszta 25), więc exp/h = 20 x zabić/h. Poziom nie zmienia exp za zabicie, liczy się tylko kills/h.

## 1. Wniosek w skrócie

- Dane NIE potwierdzają, że poprzedni spot był "dużo lepszy". Troll cave w Thais (x 32470-32510, y 32265-32300) dawał 1650-1960 exp/h (13-14.10, 97-108 zabić/h), przy nowym patrolu 15.10 rano ok. 2240. Edron rano 15.10 dawał 2600 exp/h, wieczorem 2180. Edron jest o 10-35% lepszy niż Thais przy porównywalnym kodzie.
- Natomiast Edron sam się pogorszył w ciągu dnia: 2650 (09h) -> 2400 (13h) -> 2050-2300 (17-20h), po 18:07 średnio 2150-2180. Spadek rano -> wieczór to ok. -16% (129 -> 108 zabić/h). To pewnie wrażenie "było lepiej" [HIP: Karol patrzy na poranek lub na szczyt 14.10 10:29-11:21 = 2315].
- Przyczyna spadku [POTW]: dłuższy udział chodzenia bez celu (IDZ 26% -> 41% czasu) i mniej zabić na przejściu (zab/wizytę 2,9-3,1 -> 2,07). Czas walki na jednego trolla się nie zmienił (9,1-9,9 s). To jest sygnał mniejszej gęstości trolli (inni gracze zabierają spawny, "full ppl") plus bezpośredni koszt unikania graczy.

## 2. Spoty i exp/h (telemetria)

| spot | okres | aktywne min | exp/h | zabić/h | IDZ % | WALKA % |
|---|---|---|---|---|---|---|
| Thais szczury (32020,32150) | 11.10 | ok. 600 | 350-470 | n/d | n/d | n/d |
| Thais kanały (32360,32215) | 11-12.10 | ok. 450 | 350-420 | n/d | n/d | n/d |
| Thais troll cave stara trasa | 12.10 | ok. 450 | 1050-1280 | n/d | n/d | n/d |
| Thais troll cave | 13.10 dzień | 559 | 919 | 85 | 17 | 73 |
| Thais troll cave | 13.10 wieczór | 117 | 1652 | 105 | 39 | 44 |
| Thais troll cave | 14.10 rano | 345 | 1950 | 108 | 44 | 39 |
| Thais troll cave | 14.10 wieczór | 195 | 1959 | 97 | 37 | 45 |
| Thais troll cave patrol (nowy kod) | 15.10 08:20-09:38 | 78 | 2244 | 108 | 30 | 65 |
| Edron | 15.10 09:00-12:00 | 127 | 2603 | 129 | 26 | 56 |
| Edron | 15.10 12:55-15:49 | 171 | 2353 | 118 (ep. 333/171 min = 117) | 32 | 49 |
| Edron | 15.10 17:12-18:07 | 43 | 2077 | n/d | 34 | 48 |
| Edron | 15.10 18:07-20:29 | 140 | 2179 | 108 | 41 | 43 |

Najlepsze godziny Edronu: 09-11h (2580-2650). Najgorsze: 17h (2049), 20h (1949).

## 3. Rozbicie czasu na Edronie po 18:07 (140 min aktywnych, 253 zabicia)

Na jedno zabicie przypada ok. 33 s (3600/108): walka 14,3 s (43%), chodzenie bez celu 13,7 s (41%), loot 4,3 s (13%), UH/inne 1,2 s. Rano: walka 56%, IDZ 26%, loot 16%.

| składnik | 18:07-20:29 | rano 09-12h | uwagi |
|---|---|---|---|
| WALKA | 43,3% | 54,3% | do zabicia śr. 9,1 s (rano 9,9 s) |
| IDZ (patrol) | 41,5% | 27,8% | główna różnica |
| LOOT | 12,9% | 15,7% | śr. 4,7 s; wyniki: 176 ok, 9 brak_okna, 4 pełny_plecak |
| UH (rzut runy) | 0,8% | 1,2% | 12 runów w 143 min |
| unikanie graczy | 26 epizodów, 666 s (7,8% czasu) | 1 epizod, 23 s | patrz sekcja 5 |
| utknięcia (WALKA) | 11, 209 s (2,4%) | 21, 434 s (4,0%) | nie jest problemem |
| pościg | 762 startów, ok. 515 s (6% czasu, wliczone w WALKA) | 969 startów | 678 z 766 kończy się `odl<=1`, działa dobrze |
| zgubione cele | 9 zgubionych, 10 porzuconych | 23 / 35 | po 18:07 mniej niż rano, więc cele nie uciekają częściej |

Wizyty patrolu po 18:07: 119 wizyt, 27 pustych (23%, 0 zabić w drodze i na miejscu), 50 wizyt zakończonych `pusto w widoku` (zawrót), na miejscu śr. 2,0 s, dojście śr. 68 s, mediana 53 s, max 185 s. Zabicia dzieją się w drodze, nie na miejscu (zgodnie ze SPEC_patrol_respawn).

Zabicia na minutę dojścia: rano 2,14, wieczorem 1,83 (-14%). To jest bezpośredni miernik gęstości trolli na trasie.

## 4. Miejsca patrolu (po 18:07, 15 wizyt każde; rano/popołudnie w nawiasie)

| m | (x,y) | mobów w spawnie | zab/wizytę | puste z 15 | dojście s | zab/s dojścia+miejsca |
|---|---|---|---|---|---|---|
| m1 | 33073,31732 | 6 | 3,38 (5,0-6,0) | 1 | 95 (139-163) | 0,035 |
| m2 | 33096,31737 | 3 | 3,00 (1,9-3,3) | 0 | 81 | 0,036 |
| m3 | 33085,31738 | 4 | 0,60 (0,6-1,0) | 8 | 33 | 0,017 |
| m4 | 33115,31748 | 4 | 1,67 (2,0-3,4) | 3 | 73 | 0,022 |
| m5 | 33078,31757 | 4 | 2,36 (3,8-5,8) | 1 | 70 | 0,033 |
| m6 | 33081,31762 | 4 | 1,07 (1,6-3,8) | 5 | 42 | 0,024 |
| m7 | 33082,31772 | 6 | 2,40 (2,3-2,6) | 5 | 72 | 0,032 |
| m8 | 33115,31774 | 4 | 1,93 (3,5-4,8) | 4 | 75 | 0,025 |

- m3 jest najsłabszym miejscem: 0,6 zabicia na wizytę i 53% wizyt pustych, niezależnie od pory dnia (rano 3 z 7 puste, popołudnie 8 z 14). Leży 12-18 pól od m1 i m2, więc jest przy okazji, ale kosztuje wizytę.
- m1, m2, m5, m7 dają najwięcej zabić na sekundę (0,032-0,036). m4, m6, m8 średnio (0,022-0,025).
- Nie dotarł do miejsca: 13 z 119 wizyt po 18:07 (11%), rano 1 z 57. Najczęściej m1 (3), m5 (2), m6 (2), m7 (2). Wygląda na przerwanie wizyty przez walkę, unikanie lub zmianę celu.
- Ostatni czas wizyty vs wydajność (cały dzień, ta sama trasa): wizyty w < 300 s od poprzedniej tego samego miejsca: 1,45 zab/wizytę, 45% pustych; 300-600 s: 2,07 i 24%; 600-900 s: 2,64 i 24%; > 900 s: 3,62 i 14%. Ale zab/min dojścia prawie stałe (1,80, 1,92, 1,91, 2,07), bo dłuższa wizyta to dłuższy marsz. Czyli sam odstęp między wizytami zmienia wynik słabo: dobry zwrot daje się z samego pokrywania nowych pól po drodze.
- Pominięte spawny poza trasą (miejsca_edron.json `pominiete_spawny`): (33130,31751) 4 trolle, (33057,31762) 3, (33063,31778) 2, razem 9 trolli przy 35 mobach na 8 głównych miejscach (+26% spawnów), nieprzetestowane drogi.

## 5. Inni gracze: ile kosztują exp/h

Spot jest ludny: 15 różnych graczy widzianych w próbkach (Qersamo, Gempper, Qk Loka, Vermitor, Thorin, Ucho, Deetasea, Kezz, Milfhunter, Prolvldeus, Deoku Easmei, Yeiko, Eliu, Harley Queen, Loveliy). Koszt dzieli się na dwa:

A) Bezpośredni (gracz w widoku, unikanie) [POTW]:
- Cały dzień: gracz w widoku tylko ok. 3% czasu (po odfiltrowaniu własnej postaci). W tym czasie exp/h to 670-740 przy graczu <= 10 pól (zamiast 2320), ale to tylko 17 minut w ciągu dnia.
- Unikanie: 42 epizody w ciągu dnia, razem 21 min, w tym czasie 1134 exp/h (reszta 2308). Strata ok. 1170 exp/h x 21 min = ok. 410 exp na dzień (ok. 40-45 exp/h dziennie).
- Po 18:07: 26 epizodów, 666 s, plus 59 zmian punktu rotacji (39 "omin", 20 "tyl"), 11 blokad, 14 pominiętych trolli przy graczu. Strata ok. 90-130 exp/h (4-6% po 18:07). Najczęściej: Kezz 12 razy, Prolvldeus 5, Eliu 5.
- Efekt "gracz przy miejscu" w patrolu: 9 wizyt po 18:07 (powód `gracz przy miejscu`).

B) Pośredni (gracze zabierają spawny, których bot nie widzi) [HIP, ale z mocnym sygnałem]:
- Udział czasu z graczem w widoku jest taki sam w ciągu dnia (0-6%), a exp/h spada 2650 -> 2050-2300, zab/min dojścia spada o 14%, a zab/wizytę o 29-33% po 18:07. Inni gracze bez bezpośredniego kontaktu zmniejszają gęstość trolli. Szacunek: rano-do-wieczora różnica 430 exp/h (16%), z czego bezpośrednie unikanie to ok. 100, reszta ok. 330 exp/h (13%) to pośrednio zabrane trolle i/lub pora dnia.
- Łącznie koszt obecności innych graczy na Edronie wieczorem: ok. 400-450 exp/h (ok. 17-20% w stosunku do poranka). To górna granica, bo nie umiem oddzielić go od zwykłego rozkładu respawnu.

## 6. Mana, jedzenie, cap, pętla

- Mana średnio 18% (rano 34%) [POTW]. W logu 6 razy `mana nie rośnie od X s (ML off)` i zapas jedzenia 0 (`brak_jedzenia`, WYPRAWA_AKTYWNA=0). Mana stoi na 49-86 z 305 przez wiele minut. Skutek na exp/h: pośredni. UH robi się rzadko (12 runów/143 min), zdrowie czar tylko 6 razy. Nie zaobserwowałem, żeby brak many blokował leczenie (HP 100% w próbkach decyzji).
- Cap/loot: `pełny_plecak` 4 razy po 18:07, `brak_okna` 9 razy (rano 20, popołudnie 20) = 4-8% prób lootu. Niski wpływ (ok. 1% czasu).
- Pętla: 188 punktów edron_trolle_petla jest tylko trasą awaryjną, patrol idzie po 8 miejscach (TRYB_PATROL=1). Odstęp między wizytami tego samego miejsca ok. 10 min, bliski czasowi respawnu (mediana 465 s wg RAPORT_obecnosc, przy czym to Thais), więc nie jest "za szybko".
- "Pomijam": 14 razy po 18:07, wszystkie to trolle przy graczu (1 pole). Nie jest to utrata własnych trolli.

## 7. Czy włączenie patrolu według respawnu (obecnosc.py / PATROL_RESPAWN_CIEN) pomoże na Edronie

Stan: tryb cienia (`PATROL_RESPAWN_CIEN=1` w cavebot.py dev); w stabilnym katalogu nie ma obecnosc.py, więc live bot tego nie liczy. Kod tworzy mapę dla każdego spotu z "troll" w nazwie potworów, czyli także dla Edronu (Troll,Bear,Swamp Troll,Frost Troll), bbox z miejsc_edron. Raport kalibracyjny (Spearman 0,60, 54% wizyt do miejsc wyczyszczonych < 300 s temu: 1,85 vs 3,27 zab/wizytę) dotyczy tylko Thais, na Edronie mapa startuje od zera i uczy się od domyślnej gęstości.
Ocena dla Edronu na moich danych:
- Jest podobny wzorzec: wizyta po < 300 s od poprzedniej: 1,45 zab, 45% pustych (31 wizyt z 292, czyli 11%); po 5+ min: 2,1-3,6. To zgodne z założeniem SPEC.
- Ale zab/min dojścia jest prawie płaskie (1,80 -> 2,07) między przedziałami, więc zysk z samego wyboru według respawnu jest mały. Szacunek: +2-4% (50-90 exp/h), po nauczeniu się mapy (kilka godzin). Edron ma tylko 8 miejsc w jednym związanym obszarze, mniej do optymalizacji niż w Thais (m1..m8 + piętra).
- Nie rozwiąże głównego problemu (inni gracze zabierają spawny), ale gracz przy komórce obniża jej wartość, co może dać dodatkowe ok. 1-2%.
Rekomendacja: wdrożyć obecnosc.py do stabilnego jako cień (dane z Edronu się przydadzą), włączać dopiero po A/B. Nie oczekiwać cudów.

## 8. Rekomendacje (rankingowo, z szacunkiem exp/h)

Bazowo: 2180 exp/h (po 18:07). Szacunki nie sumują się liniowo.

1. Zwiększ DPS / skróć czas walki (WALKA 43% = 14,3 s na zabicie, 9,1 s na trolla): najwyższy potencjał, +5-10% (+110-220 exp/h) [HIP]. Mana jest prawie zawsze pusta (18%), ML_CZAR_AKTYWNY=0 i brak jedzenia (zapas 0). Przywrócić regenerację: kupić jedzenie (WYPRAWA_AKTYWNA=1 lub ręczne uzupełnienie plecaka, JEDZENIE_ZAPAS_MIN=2 spełnione dopiero po zakupie), a przy mniejszej many niż potrzeba na UH wstrzymać produkcję UH w czasie pełnej walki. Jeśli postać ma czar ofensywny, włączyć ML_CZAR_AKTYWNY. UH_MANA_MIN=100 zjada całą manę, która mogłaby iść w atak. Weryfikować: czas do zabicia (do_zab_s) przed i po.
2. Przejście przez inne godziny / zmiana pory (17-20h to najgorsze: 1950-2050 vs 2600 rano): +10-20% (+200-400 exp/h), to nie zmiana w bocie, tylko plan dnia. Wieczorem (po 17h) ruch graczy najbardziej niszczy spawny: exp/h 17h 2049, 20h 1949. Jeśli bot ma biegać wieczorem, rozważ drugi spot na wieczór.
3. Wypisz m3 z patrolu lub obniż jego wagę (0,165 -> ok. 0,03), zredukuj m6/m4 (waga 0,128 / 0,095 -> ok. 0,06): +1-3% (30-60 exp/h). Dane: m3 0,6 zab/wizytę, 53% pustych, 0,017 zab/s; zawrót skraca puste wizyty tylko częściowo. Edycja w trasy/miejsca_edron.json (pole `waga`), albo `PATROL_WAGA_MIN` 0.5 -> 0.0 i zwiększenie `PATROL_CZAS_MAX`. Wagi wzmocnić dla m1 (0,154 -> 0,25), m2 (0,085 -> 0,18), m5 (0,068 -> 0,15), m7 (0,184, bez zmian): to miejsca o 0,032-0,036 zab/s.
4. Zmniejsz koszt unikania graczy: +2-4% (50-90 exp/h). Dane: po 18:07 666 s w unikaniu + 59 zmian punktów, w tym czasie 1134 vs 2308 exp/h. Pokrętła: UNIKANIE_PROMIEN 9 -> 6 (gracz bliżej niż 6 pól, nie 9), UNIKANIE_BLOK_S, UNIKANIE_PUNKT_D 5 -> 3. Ryzyko: kontakt z graczem (zwykli gracze, nie PK, wg logu `brak graczy z czaszką`), więc tylko po decyzji Karola.
5. Przetestuj 3 pominięte spawny: (33130,31751) 4 trolle, (33057,31762) 3, (33063,31778) 2, jako nowe miejsca m9-m11 (+26% spawnów na tej samej pętli): +3-8% (70-170 exp/h) [HIP], bo gdy gęstość spada, więcej spawnów to więcej celów. Dojścia nieprzetestowane (15-16 pól od nagranej pętli), więc najpierw ręcznie nagrać odnogę.
6. PATROL_RESPAWN (obecnosc.py) jako cień na stabilnym, A/B po zebraniu danych z Edronu: +2-4% (50-90 exp/h), małe ryzyko (cień).
7. Nie wracać do Thais troll cave: 1650-1960 exp/h (13-14.10) vs 2180-2600 na Edronie. Wyjątek: jeśli Karol ma dla Thais lepszą liczbę z innego okresu (np. 14.10 10:29-11:21 = 2315 przy 52 min), to jest ona w zakresie zwykłych wahań Edronu.
8. Poprawki techniczne (małe): przerwane wizyty (13 z 119 nie dotarło), 11% do zbadania; `brak_okna` w lootcie (4-8% prób), ma ok. 1% wpływu.

## 9. Co jest nieznane

- Nie wiem, co dokładnie Karol uważa za "poprzedni spot". Jeśli to spot sprzed 13.10 (Thais szczury, kanały), to dawał 350-470 exp/h, więc nie. Jeśli to Thais troll cave z 14.10 (10:29-11:21, 2315), to jest to pojedynczy 52-minutowy odcinek.
- Udział pośredniego kosztu graczy (330 exp/h) jest estymatą, nie pomiarem; w danych nie ma śladu zabić "skradzionych" poza `zgubiony: zniknął z widoku żywy` (9-23 na sesję, co nie wzrosło wieczorem).
- Dane o poziomie postaci nie wpływają na exp za trolla, ale mogły wpłynąć na szybkość zabijania (lvl 17).
