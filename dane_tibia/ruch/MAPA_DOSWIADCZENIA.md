# Mapa z doświadczenia: jaskinia trolli (z7 wejście, z8, z9)

Analiza tylko do odczytu, dane 11-14.10.2026 (telemetria 171 tys. rekordów, logi mozg, mapa OTMM). Żaden plik bota nie był zmieniany. Pełne dane: `mapa_doswiadczenia.json` w tym samym katalogu (pola, rozbieżności, przejścia, drzwi, obiekty). Skrypty pomocnicze są w scratchpadzie sesji, nie w projekcie.

## 1. Najważniejsze wnioski

1. **Mapa OTMM jest bardzo dokładna.** Na 598 chodzonych pól (47707 próbek w regionie) tylko 4 pola, które mapa uznaje za ścianę, były faktycznie chodzone, i żadne chodzone pole nie jest nieznane mapie. Jedno z 4 to drzwi (32505,32270,z8), trzy to błędy mapy (gniazdo z9 i jedna wnęka).
2. **Schody mają dwa typy, które mapa rozróżnia.** Dziura w dół (z8, flaga 2, kolor 210) plus drabina w górę (z9, flaga 1, kolor 210, lądowanie o 1 pole na południe) to 7 z 8 używanych obiektów. Prawdziwe schody (oba końce flaga 2) to tylko (32498,32270). Wchodzenie w górę zawsze zaczyna od Ctrl+klik "R", więc na schodach (32498,32270) pierwsza próba (R) przepada: 36 z 38 wejść w górę udało się dopiero drugą próbą (krok), mediana 4,4 s zamiast 0,9 s. To około 130 s straconych w ciągu 4 dni.
3. **Pierwszy krok w dół zawodzi w 10-22% przypadków** (np. (32494,32289): 20 nieudanych pierwszych kroków na 106, p90 czasu 5,5 s, max 64,6 s). Drugi krok z tego samego pola zwykle się udaje, więc to nie dziura zasypana, tylko gubiony klawisz albo zajęta chwilowo komórka. Łopata dla dziur 8->9 nigdy nie była potrzebna i nigdy się nie udała (brak łopaty w plecaku, PIETRA_LOPATA=0 przez większość czasu).
4. **Dziura zasypana (łopata) potwierdzona tylko przy wejściu do jaskini (32493,32259,z7).** 13.10 15:21-15:24 cztery użycia łopaty (próby 2, 5, 2, 2) i dopiero potem krok w dół zadziałał (15:25:08). Wszystkie dziury 8->9 są odkopane na stałe.
5. **Pole (32483,32296,z9), chodliwe wg mapy, jest praktycznie nie do wejścia krokiem z (32483,32297).** 297 prób "krok Up", 1 udana, 259 powtórek bez ruchu, 36 pominięć. Postać ma tam 374 próbki, ale prawie wszystkie to lądowanie po zeskoku z góry, nie dojście. Tymczasem Ctrl+klik R działa ze skosu (32483,32297): 100 z 129 wejść na (32482,32296) z tego pola. Pole startowe (32483,32297) wystarcza, ortogonalne ustawianie się jest zbędne.
6. **82% odpuszczeń "za ścianą" to jeden korytarz skośny, 16% to drzwi.** Z 1358 odpuszczeń w regionie 1120 ma gracza w 32491-32498 x 32288-32301 (z8), a 221 w 32499-32507 x 32268-32273 (z8, drzwi). 1377 z 1397 wszystkich odpuszczeń ma "brak drogi" (pościg liczy tylko drogi proste, a korytarz (32492,32295)->(32495,32298) i drzwi (32505,32270) tego nie spełniają).
7. **Drzwi (32505,32270,z8) są pewne** (potwierdzenie Karola, 46 próbek na ścianie wg mapy, 6 przejść prosto, ręczny łącznik w miejsca_troll.json). Inne kandydatury drzwi w okolicy nie mają dowodów.
8. **Przejść 8<->9 w logach: 692 udanych, 9 nieudanych, 8 przerwanych.** Szczegóły porażek w sekcji 4.4 (część to hipotezy; kandydat (32482,32294) i przyczyna "zwłoki na polu" są niepewne).

## 2. Dane i filtr szumu

- Prawdziwych próbek: 78574; odrzucono 2240 próbek z graczem "Ja" (testy/symulacje zapisujące do tej samej telemetrii; stan None albo IDZ, mana 0). Przeplatały się z prawdziwymi próbkami "Jointoramix" i dawały sztuczne "skoki" 8->9 o ponad 100 pól oraz 1900 fałszywych zdarzeń pietra_start/krok/blad.
- Zdarzenia pietra_*: prawdziwe są te, przy których w +-3 s jest prawdziwa próbka w odległości <=3 pól. Wyszło 729 pietra_start, 700 pietra_krok, 22 pietra_blad, co zgadza się z 709 przejściami w logach mozg.
- Region: x 32440-32530, y 32240-32320. Próbki w regionie: z7 527 (186 pól), z8 23848 (198 pól), z9 23332 (214 pól). Pól "prawdopodobnych" (pośrednich) bez własnej próbki: 111.
- Pola pośrednie: gdy dwie kolejne próbki (dt <= 3 s, to samo piętro) dzielą 2 pola, pole pośrednie jest "prawdopodobne" (jednoznaczne tylko przy ruchu prostym albo po przekątnej 2,2; przy skoku 2,1 oba kandydaci w osobnym polu `prawdopodobne_niejednoznaczne`).

Najczęściej odwiedzane pola:

| pole | próbki | wejścia |
|---|---|---|
| (32485,32297,z9) | 1691 | 165 |
| (32481,32293,z8) | 1291 | 298 |
| (32482,32293,z8) | 1103 | 204 |
| (32492,32290,z8) | 980 | 168 |
| (32484,32297,z9) | 937 | 223 |
| (32497,32281,z9) | 928 | 123 |
| (32485,32293,z8) | 863 | 168 |
| (32474,32272,z9) | 839 | 67 |
| (32485,32301,z9) | 755 | 65 |
| (32483,32297,z9) | 701 | 160 |

## 3. Rozbieżności z mapą

### 3.1 Pola chodzone, które mapa ma jako ścianę

| pole | próbki | wejścia | przejścia prosto przez pole | ocena |
|---|---|---|---|---|
| (32505,32270,z8) | 46 | 30 | 6 | drzwi (pewne) |
| (32474,32273,z9) | 16 | 12 | 4 | błąd mapy w gnieździe (pewne, znane_bledy_mapy) |
| (32473,32273,z9) | 9 | 9 | 0 | błąd mapy w gnieździe (pewne) |
| (32488,32296,z9) | 3 | 3 | 0 | błąd mapy albo wnęka (prawdopodobne) |

Brak chodzonych pól nieznanych mapie (flaga 0). Pola pośrednie leżące na ścianie (8 najczęstszych: (32480,32280,z8) 8, (32489,32292,z8) 4 itd.) to ruchy po skosie przez róg, nie błąd mapy; osobno w sekcji 3.3.

### 3.2 Pola z flagą 2 (bez drogi), ale bez zmiany piętra

Flaga 2 nie oznacza zawsze schodów. Kolor 210 (żółty) odróżnia schody od pól blokujących pathfinding przedmiotem. Postać chodzi po takich polach (kolor 121, podłoga): (32509,32282,z9) 94 próbki, (32475,32273,z9) 38, (32508,32282,z9) 18, (32473,32272,z9) 12, (32505,32277,z9) 4, (32508,32279,z9) 4, (32470,32268,z9) 3, (32506,32277,z9) 2, (32469,32270,z9) 1. Wszystkie bez zmiany piętra. Pole (32493,32259,z7) (33 próbki) to prawdziwa dziura wejścia (kolor 24).

### 3.3 Korytarz tylko po skosie (z8)

Osiem par pól (60 przejść w próbkach), przy których oba pola ortogonalne są ścianą wg mapy:

| z | do | razy |
|---|---|---|
| (32492,32295,z8) | (32493,32296) | 16 |
| (32493,32296,z8) | (32494,32297) | 13 |
| (32493,32296,z8) | (32492,32295) | 11 |
| (32494,32297,z8) | (32493,32296) | 10 |
| (32495,32298,z8) | (32494,32297) | 3 |
| (32500,32272,z8) | (32501,32273) | 3 |
| (32494,32297,z8) | (32495,32298) | 3 |
| (32491,32261,z7) | (32492,32260) | 1 |

Najważniejszy jest łańcuch (32492,32295)->(32493,32296)->(32494,32297)->(32495,32298), a dalej korytarz do schodów (32500,32303) (pola (32496,32299) 42 próbki, (32498,32301) 13, (32499,32303) 89). Fragment mapy z8 z liczbą próbek (# ściana, S flaga 2, . chodliwe):

```
       489  490  491  492  493  494  495  496  497  498  499  500  501  502
32292    #    #  .93    #    #    #    #    #    #    #    #    #    #    #
32293    #    #  .71    #    #    #    #    #    #    #    #    #    #    #
32294 .130 .139 .602  .66    #    #    #    #    #    #    #    #    #    #
32295    #    #    # .243    #    #    #    #    #    #    #    #    #    #
32296    #    #    #    #  .40    #    #    #    #    #    #    #    #    #
32297    #    #    #    #    #  .86    #    #    #    #    #    #    #    #
32298    #    #    #    #    #    # .134   .1    #    #    #    #    #    #
32299    #    #    #    #    #    #  .22  .42   .1    #    #    #    #    #
32300    #    #    #    #    #    #    #   .5    S   .5    #    #    #    #
32301    #    #    #    #    #    #    #    #   .4  .13    #    #    #    #
32302    #    #    #    #    #    #    #    #    #  .25  .14    #    #    #
32303    #    #    #    #    #    #    #    #    #    #  .89    S    #    #
32304    #    #    #    #    #    #    #    #    #    #    .   .4    #    #
32305    #    #    #    #    #    #    #    #    #    #    #    #    #    #
```

### 3.4 Pola chodliwe wg mapy, ale ruch na nie nie wychodzi

- **(32483,32296,z9)** przy schodach (32482,32296): ortogonalne ustawianie się ("krok Up" z (32483,32297,z9)) 297 razy, wynik: 1 ok, 259 powtórek bez ruchu, 36 "nie dochodzę na pole... pomijam", 1 przerwane. Pole jest w trasa/pietra_zle.json. Co ciekawe, 374 próbki na polu to głównie lądowanie po zeskoku z (32482,32295,z8) (21 razy) i dojście z innej strony, nie z (32483,32297). Domysł: pole zajęte przedmiotem/statuetką widoczną dopiero z góry; nie ma tego w mapie.
- **Pierwszy krok w dół** na dziurę: 16-22% nieudanych pierwszych kroków przy (32482,32296) i (32494,32289), 10% przy (32476,32272), 9% przy (32483,32285) (patrz sekcja 4).
- **Utknięcia** (telemetria, tylko prawdziwe w regionie): 263 zdarzenia `utkniecie` (238 w stanie WALKA, 19 IDZ, 4 WYPAD) i 28 `utkniecie_trasa`. Skupiają się w polach walki (np. (32485,32297,z9) 16, (32482,32293,z8) 14, (32474,32272,z9) 8), czyli w gniazdach, a nie przy konkretnej ścianie. 19 utknięć w stanie IDZ to w większości pola przy schodach, których przejście właśnie się nie udawało: (32495,32289,z9) 2, (32476,32272,z9) 1, (32498,32271,z9) 1.
- Nauczona ściana ("ściana (nauczona)") pojawiła się w logach tylko 3 razy, wszystkie przy drzwiach: (32504,32270,z8) tuż przed (32505,32270).

### 3.5 "Za ścianą" z linii Odpuszczam

Gracz stoi (najbliższa prawdziwa próbka): (32496,32299,z8) 648 odpuszczeń, (32492,32295,z8) 225, (32504,32271,z8) 124, (32495,32298,z8) 73, (32492,32289,z8) 66, (32493,32296,z8) 52, (32503,32271,z8) 39, (32495,32299,z8) 30. Wszystkie dotyczą trolli. Wskazane przez log pola "ściana (mapa)", których postać też dotknęła: tylko (32505,32270,z8) (drzwi) i (32509,32273,z8) 1 raz. Reszta wskazanych ścian ((32493,32295), (32492,32296), (32491,32295), (32504,32272), (32505,32271), ...) ma 0 próbek, czyli są to prawdziwe ściany.

Przyczyny: (a) korytarz skośny: trolle w nim są poza prostą drogą (pościg liczy z `skosy=False`, "droga naokoło: brak drogi"), (b) drzwi (32505,32270): trolle za drzwiami, mapa widzi ścianę. W obu miejscach postać potrafi tam dojść w trasie, bo trasa nagrana jest po skosie i przez łącznik.

## 4. Przejścia między piętrami

Zmiany piętra w próbkach: 820 (z8<->z9, z7<->z8 w regionie) po odfiltrowaniu skoków. Ruchy dalekie (ponad 3 pola) były wyłącznie artefaktem szumu "Ja".

**Typy.** Mapa daje jednoznaczny wzorzec: górne pole flaga 3 (widziane + bez drogi), kolor 210; dolne pole kolor 210 i flaga 1 (chodliwe) to **dziura + drabina**; dolne pole flaga 3 to **schody**.
- Dziura + drabina: zejście "krok" na górne pole T, lądowanie (T.x, T.y, z+1); wejście Ctrl+klik "R" na T w dolnym piętrze, lądowanie (T.x, T.y+1, z).
- Schody (32498,32270): zejście "krok" z (32499,32270,z8) (z prawej, Left), lądowanie (32498,32271,z9); wejście "krok Up" z (32498,32271,z9), lądowanie (32498,32269,z8). R tu nie działa.

| obiekt (pole T, piętro górne) | typ | w dół: ok/porażki/przerwane, tryb, mediana/p90 s | w górę: ok/porażki/przerwane, tryb, mediana/p90 s | próbki zmian dół/góra |
|---|---|---|---|---|
| schody_32484_32265 (32484,32265,z8) | dziura+drabina | 2/0/0, krok 2, 0.8/0.9 | 1/0/0, R 1, 1.0/1.0 | 3/8 |
| schody_32478_32269 (32478,32269,z8) | dziura+drabina | 1/0/0, krok 1, 5.3/5.3 | 4/0/0, R 4, 0.9/0.9 | 9/3 |
| schody_32498_32270 (32498,32270,z8) | schody | 30/0/0, krok 30, 0.9/1.9 | 38/1/0, krok 36,R 2, 4.4/5.2 | 37/37 |
| schody_32476_32272 (32476,32272,z8) | dziura+drabina | 64/0/0, krok 64, 0.7/4.0 | 50/1/1, R 48,krok->use_wlasne 2, 0.9/1.0 | 74/69 |
| schody_32483_32285 (32483,32285,z8) | dziura+drabina | 33/0/0, krok 33, 0.7/1.0 | 33/0/0, R 33, 0.9/1.0 | 32/33 |
| schody_32474_32286 (32474,32286,z8) | dziura+drabina | 3/0/2, krok 3, 0.7/0.9 | 3/0/0, R 3, 0.9/0.9 | 5/6 |
| schody_32494_32289 (32494,32289,z8) | dziura+drabina | 86/0/0, krok 86, 0.8/5.5 | 72/2/0, R 72, 0.9/1.0 | 83/86 |
| schody_32482_32296 (32482,32296,z8) | dziura+drabina | 143/0/3, krok 143, 0.7/5.6 | 129/0/1, R 129, 0.9/1.3 | 150/149 |
| wejscie_32493_32259 (32493,32259,z7) | dziura z7 (zasypywana) + drabina | 0/0/0, -, 0.6/0.7 | 0/0/0, -, - | 4/7 |
| schody_32500_32303 (32500,32303,z8) | dziura+drabina | 0/0/0, -, - | 0/0/0, -, - | 1/1 |
| schody_32508_32273 (32508,32273,z8) | dziura+drabina | 0/0/0, -, - | 0/0/0, -, - | 1/0 |

Wiersz wejście_32493_32259 (z7<->z8) nie ma wpisów w logach przejść (idzie przez wypad/dojście), dane z telemetrii: w dół 4 zmiany w próbkach (3 z pietra_krok "krok" z (32492,32259,z7) i (32494,32259,z7)), w górę 7 zmian z (32492,32260,z8)/(32493,32260,z8) w stanie WYPAD (wypad_krok "drabina", lądowanie (32493,32260,z7)). Czas w dół 0,6 s (n=2).

### 4.1 Lądowania (z próbek, pola po zmianie)

| obiekt | w dół ląduje | w górę ląduje |
|---|---|---|
| schody_32484_32265 | (32484,32265,z9) | (32484,32266,z8) |
| schody_32478_32269 | (32478,32269,z9) | (32478,32270,z8) |
| schody_32498_32270 | (32498,32271,z9) | (32498,32269,z8) |
| schody_32476_32272 | (32476,32272,z9) | (32476,32273,z8) |
| schody_32483_32285 | (32483,32285,z9) | (32483,32286,z8) |
| schody_32474_32286 | (32474,32286,z9) | (32474,32287,z8) |
| schody_32494_32289 | (32494,32289,z9) | (32494,32290,z8) |
| schody_32482_32296 | (32482,32296,z9) | (32482,32297,z8) |
| wejscie_32493_32259 | (32493,32259,z8) | (32493,32260,z7) |
| schody_32500_32303 | (32500,32303,z9) | (32500,32304,z8) |
| schody_32508_32273 | (32508,32273,z9) | (32508,32274,z8) |

### 4.2 Pola startowe (z których przejście się udało)

- **schody_32484_32265**: w dół z 32485,32265 x2; w górę z 32484,32265 x1.
- **schody_32478_32269**: w dół z 32478,32270 x1; w górę z 32479,32269 x4.
- **schody_32498_32270**: w dół z 32499,32270 x30; w górę z 32498,32271 x38.
- **schody_32476_32272**: w dół z 32477,32272 x57, 32476,32273 x7; w górę z 32476,32273 x42, 32476,32272 x6.
- **schody_32483_32285**: w dół z 32482,32285 x32, 32483,32286 x1; w górę z 32484,32284 x31, 32483,32285 x2.
- **schody_32474_32286**: w dół z 32474,32287 x3; w górę z 32474,32285 x2, 32474,32286 x1.
- **schody_32494_32289**: w dół z 32494,32290 x86; w górę z 32495,32289 x72.
- **schody_32482_32296**: w dół z 32482,32295 x137, 32482,32297 x6; w górę z 32483,32297 x100, 32482,32296 x28, 32483,32296 x1.

### 4.3 Nieudane próby (pole i tryb) na obiekt, tylko to, co poprzedzało sukces albo porażkę

- schody_32478_32269 dół: 32478,32270 krok Up x1
- schody_32498_32270 dół: 32499,32270 krok Left x3
- schody_32498_32270 góra: 32498,32271 R x38, 32498,32271 krok Up x1, 32498,32271 lina z plecaka x1, 32498,32271 wlasne x1, 32498,32271 E x1
- schody_32476_32272 dół: 32477,32272 krok Left x6, 32476,32273 krok Up x1
- schody_32476_32272 góra: 32476,32272 R x4, 32476,32273 R x2, 32476,32272 lina z plecaka x2, 32476,32273 krok Up x1, 32476,32272 wlasne x1
- schody_32483_32285 dół: 32482,32285 krok Right x3
- schody_32483_32285 góra: 32484,32284 R x1, 32483,32284 krok Down x1
- schody_32474_32286 dół: 32474,32287 krok Up x2
- schody_32494_32289 dół: 32494,32290 krok Up x20, 32494,32290 use x1
- schody_32494_32289 góra: 32495,32289 R x9, 32495,32289 krok Left x7, 32495,32289 lina z plecaka x2, 32495,32289 wlasne x2, 32495,32289 E x2
- schody_32482_32296 dół: 32482,32295 krok Down x24, 32482,32297 krok Up x1, 32482,32295 łopata na (32482 x1
- schody_32482_32296 góra: 32483,32297 R x1, 32483,32296 krok Left x1

Wnioski z tabeli: pierwsza próba "krok" w dół zawodzi w 10-22% (przy (32494,32289): 20 z 106 pierwszych kroków), druga zwykle wychodzi. Nie ma różnicy w polach startowych (zawsze to samo pole ortogonalne, 99% z tego jednego pola), więc to nie geometria.

### 4.4 Porażki całkowite i przerwania

| kiedy | kierunek | obiekt | opis |
|---|---|---|---|
| 10-12 14:29:05 | z8->z9 | (32482, 32296) | przerwane: przerwane po 60 s; prób 1 |
| 10-12 14:51:09 | z9->z8 | (32482, 32294) | porazka: wyczerpane pola przejścia; prób 0 |
| 10-12 15:07:03 | z9->z8 | (32482, 32294) | porazka: wyczerpane pola przejścia; prób 0 |
| 10-12 15:41:32 | z9->z8 | (32482, 32294) | przerwane: przerwane po 41 s; prób 0 |
| 10-12 15:52:51 | z9->z8 | (32482, 32294) | porazka: wyczerpane pola przejścia; prób 0 |
| 10-12 17:02:36 | z8->z9 | (32482, 32296) | przerwane: przerwane po 269 s; prób 0 |
| 10-12 17:52:30 | z9->z8 | (32476, 32272) | porazka: wyczerpane pola przejścia; prób 8 |
| 10-12 17:53:28 | z9->z8 | (32476, 32272) | przerwane: przerwane po 1171 s; prób 3 |
| 10-12 18:39:04 | z9->z8 | (32482, 32294) | porazka: wyczerpane pola przejścia; prób 0 |
| 10-13 08:20:37 | z8->z9 | (32474, 32286) | przerwane: przerwane po 25 s; prób 1 |
| 10-13 08:26:39 | z8->z9 | (32474, 32286) | przerwane: przerwane po 22 s; prób 1 |
| 10-13 08:27:57 | z9->z8 | (32482, 32294) | porazka: wyczerpane pola przejścia; prób 0 |
| 10-13 22:04:14 | z9->z8 | (32494, 32289) | porazka: wyczerpane pola przejścia; prób 7 |
| 10-13 22:12:03 | z9->z8 | (32494, 32289) | porazka: wyczerpane pola przejścia; prób 7 |
| 10-14 09:49:09 | z8->z9 | (32482, 32296) | przerwane: przerwane po 60 s; prób 1 |
| 10-14 12:50:18 | z9->z8 | (32498, 32270) | porazka: wyczerpane pola przejścia; prób 7 |
| 10-14 12:54:56 | z9->z8 | (32482, 32296) | przerwane: przerwane po 19 s; prób 0 |

Kandydat (32482,32294,z9) z oznaczeniem "domysł" (5 porażek 12-13.10) jest pomyłką: to nie obiekt, tylko błędna hipoteza (po 13.10 08:27 nie wystąpiła, bo pietra_start.json zna prawdziwe pole). Trzy pełne porażki 8 prób: (32476,32272,z9) 12.10 17:52, (32494,32289,z9) 13.10 22:04 i 22:12, schody (32498,32270,z9) 14.10 12:50. Wszystkie zaczynają się od R, krok, R, lina (brak liny w plecaku), "wlasne", E, W, N, bez żadnej zmiany piętra; potwory w telemetrii: tylko gracz. Przy (32494,32289) 10 s wcześniej padł troll na samym polu startowym (32495,32289,z9) i leżały zwłoki (log "Watchdog... porzucam odłożone zwłoki"), więc domysł: zwłoki na drabinie/polu blokują Ctrl+klik.

### 4.5 Dziura odkopana a zasypana

- Odkopane na stałe (krok wystarcza): wszystkie dziury z8->z9 z listy (7 obiektów, 0 przypadków użycia łopaty zakończonych sukcesem). Łopata próbowana raz: 13.10 13:43:54 przy (32482,32296,z8), błąd "nie widzę łopaty (shovel) w oknie plecaka"; 10.14 10:10 i 13.10 15:01 w wypadzie przy (32476,32272,z8), też bez efektu. Pokrętło PIETRA_LOPATA bywa 0, więc próba łopaty jest wtedy pomijana po cichu, a licznik prób rośnie (stąd sukcesy w próbie 3: krok, pominięta łopata, krok).
- Zasypana, łopata pomogła (prawdopodobne): wejście do jaskini (32493,32259,z7). 13.10 15:21:46 start, pietra_lopata (poz 32493,32259) próby 2 i 5, 15:22:40 porażka "wyczerpane pola przejścia", ponowne starty i łopata 15:22:49 i 15:24:20, a potem 15:25:07 "krok" z (32492,32259,z7) i zmiana piętra po 1 s (pietra_krok, próba 1).

### 4.6 Obiekty z mapy, których postać nie użyła

Pary z mapy (górne flaga 3 i dolne kolor 210) bez ruchu w danych: (32487,32286,z8), (32498,32260,z8), (32507,32260,z8) (schody, oba końce flaga 3), (32519,32248,z8), z7: (32468,32275) i wejście (32503,32266,z7) (dolne (32503,32266,z8) ma 2 próbki, ale to wchodzenie na pokój, nie zmiana piętra). Dwie dziury zostały wykryte tylko przypadkowymi zeskokami: (32500,32303,z8) 16.10 nie, 12.10 16:50:40 (stan LOOT, zeskok z (32499,32303,z8)) i powrót drabiną 12.10 17:02:36 ze stanu IDZ; (32508,32273,z8) 13.10 21:36:33 (LOOT->WALKA, zeskok z (32508,32271,z8)). Obie to "prawdopodobne", bo nigdy nie były obiektem trasy.

## 5. Drzwi

```
       495  496  497  498  499  500  501  502  503  504  505  506  507  508  509  510
32264    #    #    #    #    #    #    #    #    #    #    #    #    #    #    #    #
32265    #    #    #    #    #    #    #    #    #    #    #    #    #    #    #    #
32266    #  .26    #    #  .11    #    #    .   .2   .1   .3    #   .2    .    #    #
32267    #    S .188  .28 .142   .9    #    .  .33   .8   .7  .12  .67   .1    #    #
32268    #    S  .12  .26  .82   .3    #   .1    .   .2    #  .32  .32   .9    #    #
32269    #    #  .15 .549  .87  .30    #    #    #    #    #  .29  .19   .4    #    #
32270    #    #  .34    S  .94 .152  .55  .65 .102 .113  D46  .50  .42  .11    #    #
32271    #    #  .10  .21  .38  .40  .29  .97  .72 .336    #    #    #  .16    #    #
32272    #    #    #    #    .  .26    #    #  .22    #    #    #    #  .14  .11    #
32273    #    #    #    #    #    #  .59  .41   .6    #    #    #    #    S  .77    #
32274    #    #    #    #    #    #    S    .    #    #    #    #    #    .    .    #
```

- **(32505,32270,z8)**: pewne. Karol potwierdził drzwi w okolicy 32501-32506,32268-32272 z8. mapa: ściana (flaga 5), a pole ma 46 próbek i 30 wejść; 6 razy próbki (32504,32270)<->(32506,32270) w odstępie 1,1-1,4 s (przejście przez pole). trasy/miejsca_troll.json: lacznik_32506_32270_32502_32270 ręczny, pola_oznaczone_jako_sciana [[32505,32270]]. 21 odpuszczeń "za ścianą" wymienia (32505,32270) jako "ściana (mapa)", razem ok. 221 odpuszczeń gdy gracz stoi w 32499-32507 x 32268-32273 (trolle po drugiej stronie drzwi, pościg nie ma drogi). oś drzwi: wschód-zachód, korytarz y=32270 od x=32497 do 32504, za drzwiami pokój 32506-32508 x 32266-32270.
- **(32474,32273,z9)**: pewne (błąd mapy, nie drzwi). 16 próbek, 4 przekroczenia prosto (32473,32273)->(32475,32273) w 1,0-1,2 s, flaga 5 mimo podłogi. trasy/miejsca_troll.json znane_bledy_mapy: gniazdo.
- **(32473,32273,z9)**: pewne (błąd mapy, nie drzwi). 9 próbek, 9 wejść, sąsiad gniazda 32474,32273.
- **(32488,32296,z9)**: prawdopodobne (błąd mapy). 3 próbki, 3 wejścia; pole ściana wg mapy, pod nim (32488,32297) 17 próbek, nad nim ściana.
- **(32504,32269,z8)**: domysł. ściana w osi pionowej między (32504,32268) 2 próbki a (32504,32270) 113 próbek. brak przekroczeń, brak odpuszczeń; tylko geometria, odrzucić bez nowych danych.
- **(32502,32269,z8)**: domysł. ściana w osi pionowej między (32502,32268) 1 próbka a (32502,32270) 65 próbek. brak przekroczeń.
- **(32505,32268,z8)**: domysł. ściana między (32504,32268) 2 próbki a (32506,32268) 32 próbki, ale pokoje łączy chodzone (32505,32267) 8 próbek, więc to raczej zwykła ściana.
- **(32501,32268,z8)**: domysł. ściana między (32500,32268) 3 próbki a (32502,32268) 1 próbka; nikt nie przeszedł.

W danych nie ma `wypad_krok` rodzaj drzwi w jaskini: dwa takie wpisy dotyczą Thais (32365,32208,z7) i (32400,32217,z7) (17:18-17:20 13.10).

## 6. Lista obiektów z pewnością

| obiekt | rodzaj | pole | pewność | dowód |
|---|---|---|---|---|
| schody_32484_32265 | dziura+drabina | (32484,32265,z8) | prawdopodobne | zmiany piętra w próbkach: w dół 3, w górę 8; udane w logach: dół 2, góra 1 |
| schody_32478_32269 | dziura+drabina | (32478,32269,z8) | prawdopodobne | zmiany piętra w próbkach: w dół 9, w górę 3; udane w logach: dół 1, góra 4 |
| schody_32498_32270 | schody | (32498,32270,z8) | pewne | zmiany piętra w próbkach: w dół 37, w górę 37; udane w logach: dół 30, góra 38 |
| schody_32476_32272 | dziura+drabina | (32476,32272,z8) | pewne | zmiany piętra w próbkach: w dół 74, w górę 69; udane w logach: dół 64, góra 50 |
| schody_32483_32285 | dziura+drabina | (32483,32285,z8) | pewne | zmiany piętra w próbkach: w dół 32, w górę 33; udane w logach: dół 33, góra 33 |
| schody_32474_32286 | dziura+drabina | (32474,32286,z8) | prawdopodobne | zmiany piętra w próbkach: w dół 5, w górę 6; udane w logach: dół 3, góra 3 |
| schody_32494_32289 | dziura+drabina | (32494,32289,z8) | pewne | zmiany piętra w próbkach: w dół 83, w górę 86; udane w logach: dół 86, góra 72 |
| schody_32482_32296 | dziura+drabina | (32482,32296,z8) | pewne | zmiany piętra w próbkach: w dół 150, w górę 149; udane w logach: dół 143, góra 129 |
| wejscie_32493_32259 | dziura z7 (zasypywana) + drabina | (32493,32259,z7) | prawdopodobne | zmiany piętra w próbkach: w dół 4, w górę 7; udane w logach: dół 0, góra 0 |
| schody_32500_32303 | dziura+drabina | (32500,32303,z8) | prawdopodobne | zmiany piętra w próbkach: w dół 1, w górę 1; udane w logach: dół 0, góra 0 |
| schody_32508_32273 | dziura+drabina | (32508,32273,z8) | domysł | zmiany piętra w próbkach: w dół 1, w górę 0; udane w logach: dół 0, góra 0 |
| drzwi_32505_32270_z8 | drzwi | (32505,32270,z8) | pewne | patrz sekcja drzwi |
| korytarz_skosny_z8 | korytarz tylko po skosie (A* prosty "brak drogi") | (32492,32295,z8) | pewne | skosy przez róg (obie ortogonalne ściany): (32492,32295)->(32493,32296)->(32494,32297)->(32495,32298) razem 56 przejść w próbkach; 1120 z 1358 odpuszczeń "za ścianą" stoi gracz w 32491-32498 x 32288-32301 z8 |

Dodatkowo (domysł): druga możliwa dziura z z7 do z8 na (32503,32266,z7) (mapa jak wejście (32493,32259), brak zmian piętra w danych).

## 7. Co jest niepewne

- Telemetria ma ok. 1,2 s między próbkami, więc ruch po przekątnej przez róg i dwa kroki w 1,2 s są niejednoznaczne; zdarzenia z zapisów bota (logi mozg) traktuję jako pewniejsze niż próbki.
- Zdarzenia testowe (nazwa gracza "Ja") odfiltrowałem po nazwie gracza w próbkach i po obecności prawdziwej próbki obok zdarzeń pietra_*. Zdarzenia pietra_* bez prawdziwej próbki w +-3 s uznałem za testowe; mogły się trafić pojedyncze prawdziwe odrzucone.
- Czasy przejścia z telemetrii to czas od pietra_start do pietra_krok; nie obejmują dojścia do pola startowego przed startem przejścia.
- Przyczyny pierwszego nieudanego kroku i pełnych porażek (zwłoki, opóźnienie klawisza) to hipotezy, żadnej nie da się udowodnić z danych.
- Ruchy `skos` w sekcji 3.3 liczone tylko dla dt <= 3 s.
