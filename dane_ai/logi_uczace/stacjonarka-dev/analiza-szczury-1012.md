# Analiza szczurow w kanalach Thais (z=8) i propozycja trasy, 12.10.2026

Dane: telemetria-20261011/12.jsonl (3794 probki bota na z=8 w prostokacie x 32300-32450, y 32150-32300), mozg-2026101[12]-*.log (132 zabicia "Cel Rat zabity"), epizod_celu (144 zabite szczury), nowy_cel. Cztery sesje: 11.10 21:08-22:43 (3 podsesje) i 12.10 07:51-08:39, razem ok. 84,5 min czasu bota na z=8. Wszystko po trasie thais_szczury (jedna krotka sesja 21:26 na kanaly2 pominieta w wnioskach). Bot caly czas jest w promieniu 3 pol od trasy (96% probek), wiec dane mowia o szczurach TYLKO wzdluz trasy i ok. 8 pol obok (zasieg ekranu), nie o reszcie kanalow.

## 1. Gdzie sa szczury (siatka 5x5)

zab = zabicia (log mozg), obs = obserwacje szczura (unikalne na 2x2 pola / 20 s), bot_min r8 = minuty bota w promieniu 8 pol od srodka komorki, zab/h = zab / bot_min r8 * 60 (przyblizenie, komorki sie nakladaja).

| # | komorka (x,y lewy gorny) | miejsce | zab | obs | bot_min r8 | zab/h |
|---|---|---|---|---|---|---|
| 1 | 32365,32210 | kregoslup N-S (D), skrzyzowanie z korytarzem wschodnim y=32214 | 17 | 26 | 12,0 | 85 |
| 2 | 32365,32190 | skrzyzowanie kregoslupa z korytarzem zachodnim | 14 | 36 | 19,0 | 44 |
| 3 | 32365,32215 | j.w., kilka pol nizej | 12 | 40 | 12,6 | 57 |
| 4 | 32340,32185 | zachodni koniec korytarza y=32189 (E) | 11 | 23 | 13,2 | 50 |
| 5 | 32335,32260 | odnoga poludniowa x=32338, y 32260-32264 (A) | 10 | 21 | 4,3 | 140 |
| 6 | 32340,32190 | E zachod | 8 | 25 | 13,2 | 36 |
| 7 | 32355,32185 | E srodek | 8 | 21 | 15,2 | 32 |
| 8 | 32350,32185 | E srodek | 6 | 18 | 14,7 | 25 |
| 9 | 32365,32185 | polnocny koniec kregoslupa | 4 | 22 | 17,6 | 14 |
| 10 | 32350,32190 | E | 4 | 18 | 14,7 | 16 |

Zabicia wg odcinkow korytarzy (ze stalych regionow, stan ok. 08:40):

| odcinek | kroki bota | czas | zabicia | zab / 100 krokow |
|---|---|---|---|---|
| A: odnoga poludniowa x=32338, y 32253-32270 | 148 | 4,6 min | 12 | 8,1 |
| B: korytarz y=32251/52, x 32338-32366 | 682 | 11,4 min | 0 | 0 |
| C: kregoslup y 32223-32250 | 759 | 11,8 min | 1 | 0,1 |
| D: kregoslup y 32191-32222 | 778 | 20,4 min | 49 | 6,3 |
| E: korytarz y=32189/90, x 32330-32364 | 997 | 25,1 min | 46 | 4,6 |
| F: odnoga polnocno-wschodnia (32377,32183) | 113 | 2,3 min | 3 | 2,7 |

Poza regionami (19 zabic): wschodni korytarz y=32214 za x=32376 (4 zabicia przy x 32420-32423 + 2 przy 32421-22, y 32221-22), wschodni koniec korytarza B (x 32378-32382, y 32252: 3), poludniowa komora y 32272-73 (3), reszta wokol skrzyzowan.

## 2. Obecna trasa thais_szczury (88 pkt, 259 pol punkt-do-punktu, 396 pol z A* wraz z zawinieciem)

- Trasa to nie petla, tylko drzewo korytarzy: A -> B -> C (martwy) -> D -> F -> E, potem zawiniecie A* (133 pola) wraca ta sama droga E -> kregoslup -> B -> A.
- Martwe strefy: B+C (korytarz y=32251 i kregoslup y 32225-32250), 1 zabicie na ok. 23 min = ok. 28% czasu bota (1391 z ok. 4900 s), 0-1 zabicia. To ok. 60 pol przejscia w jedna strone, konieczne tylko po to, zeby dojsc do odnogi A (12 zabic).
- Gesto, a trasa tam nie wchodzi: poludniowa komora y 32272-73 (odnoga A konczy sie 12 pol wczesniej, y=32261), wschodni koniec B (x 32370-32388), wschodni korytarz y=32214 za x=32376 (jedyne wejscie bota w ten rejon to start 21:08 poza trasa: 4 zabicia w ok. 90 s).
- Szum w trasie: powrot 32369,32219 -> 32231 -> 32219 (ok. 24 kroki w kolko), zygzaki 32356-32362,y=32189 i odnoga x=32339,y 32183-32188 (0 zabic) - 
  nie szkodza, ale tez nic nie daja.
- Tempo: 1,03 pola/s (mediana z 2250 par probek w stanie IDZ). Marsz jednego okrazenia 396 / 1,03 = 385 s; IDZ to 67% czasu (IDZ 56,5 min, WALKA 23,9 min, LOOT 2,5 min z 84,5), wiec okrazenie trwa ok. 9,6 min, ok. 8,5 okrazenia w danych, ok. 15 zabic na okrazenie. Zrodlo: 132 zabicia / 84,5 min = 94 zabicia na godzine czasu bota (exp ok. 5 na szczura).

## 3. Najwazniejszy wniosek: strefy sa ograniczone respawnem, nie dlugoscia trasy

Zabicia na wizyte w D lub E rosna z przerwa od poprzedniej wizyty (30 wizyt):

| przerwa miedzy wizytami | wizyt | srednio zabic / wizyte |
|---|---|---|
| < 2 min | 6 | 1,0 |
| 2-3,5 min | 11 | 1,7 |
| 3,5-5 min | 6 | 2,3 |
| 5-9 min | 7 | 4,0 |

Czyli D i E produkuja ok. 30-35 szczurow/h kazde (49 i 46 zabic w ok. 84 min), niezaleznie od tego, jak czesto bot tam zaglada. Skrocenie trasy do samych D+E+F (ok. 170 pol zamiast 396) NIE da proporcjonalnego zysku: bot zabijalby tyle samo i czesciej czekal na respawn. Zysk moze dac tylko objecie nowych terenow, w ktorych szczury sie nie wyzynaja. Danych o tych terenach jest malo (patrz nizej).

## 4. Nowa trasa trasy/thais_szczury_opt.json

91 punktow, z=8, ten sam format (lista [x,y,z]), bez .meta. waliduj_trase.py: "trasa OK" (0 bledow, 0 ostrzezen, 370 pol punkt-do-punktu, x 32332..32422, y 32183..32272). Kazdy odcinek ma droge A* rowna odleglosci prostej, poza zawinieciem (ostatni punkt -> pierwszy, 129 pol, jak w oryginale).

Zmiany wzgledem oryginalu:
1. Odnoga poludniowa A wydluzona do komory y=32272 (x 32338-32342) - tam padly 3 zabicia (32341-43, 32272-73), a trasa konczyla sie na y=32261.
2. Wschodni koniec korytarza B (do x=32386, y 32251-52) - 3 zabicia i obserwacje bez trasy.
3. Wschodni korytarz y=32214 od kregoslupa do x=32422 i w dol do y=32224 (4+2 zabicia przy pierwszej wizycie, ok. 10 obserwacji). To najdluzsza i najmniej pewna odnoga (+128 kroki).
4. Usuniete: szum 32369 y 32219-32231 (zygzak), odnoga x=32339 y 32183-32188, zygzaki y=32189 przy x 32356-32362. Reszta po tych samych korytarzach, punkty co 4-5 pol.
5. Znane pola niebezpieczne: w repo nie ma listy niebezpiecznych pol na z=8. znane_pola.json to pola, na ktorych stal gracz, a minimapa ich nie widzi (przechodnie), nie zakazane. W logach z=8 nie ma epizodow obrazen od pol (tylko "tlum" na z=11 w analiza-tlum.md). Trasa leci po polach, na ktorych bot juz stal albo ktore mapa oznacza jako przechodnie, nie ma pol ze schodami (flaga 2) ani niewidzianych.

Dlugosc: 506 pol z A* (+28% wzgledem 396), okrazenie ok. 12 min zamiast ok. 9,6 min przy tym samym udziale marszu. Odnogi (A-poludnie, B-wschod, korytarz wschodni) odwiedzane raz na okrazenie, D i E dwa razy (idac i na zawinieciu), tak jak teraz.

## 5. Oczekiwany zysk (szacunek, NIE pomiar)

- Teraz: ok. 94 zabic/h czasu bota (132 zabicia / 84,5 min), ok. 15 na okrazenie.
- Nowa trasa: nowe odnogi A-poludnie i B-wschod to ok. 3 zabicia na 82 min kazda w danych (czyli rzedu +2...+4/h), korytarz wschodni: 4 zabicia w 90 s przy pierwszym wejsciu to zapas nagromadzony przez wiele godzin, w stanie ustalonym raczej tyle, ile A (ok. 9/h) albo mniej. Rozsadny zakres: 95-115 zabic/h (od 0% do +20%), najbardziej prawdopodobnie ok. +5-10%. Jesli odnogi okaza sie puste, zysku nie bedzie, a okrazenie bedzie o 28% dluzsze (strata kilku %, bo D/E sa ograniczone respawnem, a nie czasem).
- Czego NIE obiecuje: 130-170/h z "krotkiej petli" (sam liczy marsz bez respawnu, dane tego nie potwierdzaja).

## 6. Uczciwie: wiarygodnosc

- To tylko 4 sesje, ok. 84 min, 132 zabicia; komorki 5x5 maja po 3-17 zabic, wiec ranking komorek 4-10 jest w granicach szumu. Wiarygodne sa tylko: B i C sa martwe (0-1 zabicie przy ponad 20 min), D i E sa gesto zasiedlone, A jest gesta, ale rzadko odwiedzana, i ze kazdy region jest ograniczony respawnem.
- Brak danych o terenach, do ktorych bot nie wchodzil (duze sale x 32385-32400, y 32181-32215; polnocna czesc korytarza x=32421-22 y<32214; poludniowa czesc za y 32273). Obserwacje szczurow nie obejmuja miejsc dalej niz ok. 8 pol od bota.
- Zaleznosc "zabic na wizyte vs przerwa" opiera sie na 30 wizytach, z grubsza liniowa, ale n w przedzialach to 6-11.
- Brak informacji, ile czasu szczur respawnuje na tym serwerze i ile jest spawnow w D/E (nie ma danych z samej mapy spawnow).

Co dozbierac:
1. Puscic bota na thais_szczury_opt przez min. 60-90 min w jednym ciagu bez przerw (telemetria zapisuje sama) i porownac zab/h oraz zabicia na odcinkach A-poludnie, B-wschod i korytarz wschodni z tabela powyzej. Jesli korytarz wschodni da < 0,5 zab na odwiedziny po pierwszym okrazeniu, wyciac go (punkty od (32372,32214) do (32422,32214) i z powrotem).
2. Jedno przejscie reczne (tylko na patrolu) przez sale wschodnie x 32385-32400 i polnocna czesc x=32421-22 y 32205-32213, zeby telemetria zapisala obecnosc szczurow (obserwacje bez zabijania).
3. Zapisywac pozycje i id kazdego szczura w probce (teraz sa tylko dx,dy i HP), wtedy da sie policzyc unikalne szczury i zasieg ich wedrowania, a nie obserwacje.
4. Notowac czas smierci i pojawienia sie w tym samym miejscu (respawn) - jeden dluzszy postoj bota na skrzyzowaniu y=32214 daje wprost czas respawnu.

## 7. Przelaczenie bota

W uruchom.sh zmienic jedna rzecz, w linii z setsid nohup:

    --trasa thais_szczury   ->   --trasa thais_szczury_opt

Np. `sed -i 's/--trasa thais_szczury "/--trasa thais_szczury_opt "/' uruchom.sh` (zmienia tylko to wywolanie; DOJSCIE=thais_dojscie zostaje bez zmian). Wymaga restartu bota (zatrzymaj.sh, potem uruchom.sh); w tej analizie bot nie byl ruszany. Powrot do starej trasy: odwrotna zmiana.
