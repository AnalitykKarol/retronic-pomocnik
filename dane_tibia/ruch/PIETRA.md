# Logika zmian pięter: analiza i propozycja wspólnej logiki

Stan na 14.10. Analiza tylko do odczytu. Dane: logi mozg-stdout (2708 linii "Przejście pięter"), czysta telemetria 14.10 (src=mozg), statystyki w `pietra_statystyki_przejsc.json`. Telemetria 12-13.10 jest zanieczyszczona zdarzeniami z testów, dlatego statystyki oparto na logach.

## 1. Dwie implementacje

### pietra.py (patrol i trasa wielopiętrowa, dojście)
- `kandydaci(mapa, a, b)` wylicza pola przejścia z flag mapy (2 = BEZ_DROGI, 4 = ściana), kotwiczy je na punkcie trasy `a`, nie na pozycji gracza. W górę wymaga `cheb((x,y+1),(b.x,b.y)) <= 1`.
- `TRYBY_DOL`: pewne `krok, lopata, krok, use, lopata, krok, use_wlasne`; niepewne `use, krok, use_wlasne, lopata, krok, use, use_wlasne`.
- `TRYBY_GORA`: `R, krok, R, lina, wlasne, E, W, N`.
- Pole startowe ortogonalne (`_start/_na_start`, `START_KROK_NIE_MAX=2`, `START_RUCHY_MAX=8`), pamięć w `trasy/pietra_start.json` i `trasy/pietra_zle.json`.
- Weryfikacja: `_po_przejsciu` (5 x 0,4 s), odstępy `_odstep` (1,2,4,6 s), `PIETRA_MAX_S` 150, `PIETRA_DOJSCIE_S` 25, `PIETRA_PORAZKI_STOP` 3.
- `_resync` odtwarza stan po rozjeździe; w ostatniej gałęzi tworzy `kand: []`, co od razu daje "wyczerpane pola przejścia".
- Porażka wywołuje `cb._pietra_zawroc` (odwrócenie trasy albo porzucenie miejsca w patrolu).
- Patrol (`_patrol_droga/_patrol_plan`) już planuje po grafie `przejscia` i `laczniki` z `miejsca_troll.json`.

### wypad.py (wyprawa, dojście)
- Etapy LINA/DZIURA/DRZWI z `zbuduj_etapy`; dziura `h=(b.x,b.y,a.z)`, drabina `cel=(b.x,b.y-1,a.z)`.
- `_dziura`: kierunek kroku liczony tylko z dx,dy, więc ze skosu pierwszy krok idzie w bok. Cykl `krok, lopata, krok, use, lopata, krok`. Poprawka TYLKO_Z7 (łopata tylko na z7) dodana 14.10 11:35.
- `_lina` używa `_proby_drabiny` (drabina, drabina, wlasne, E, W, N, lina). Brak trybu "krok", więc nie obsłuży schodów (32498,32270).
- `PRZEJSCIE_ODSTEP` (1,3,6,8), `ETAP_PRZEJSCIE_PROB` 6, potem awaria. Brak uczenia i pola startowego.

### Różnice
| aspekt | pietra.py | wypad.py |
|---|---|---|
| źródło przejścia | flagi mapy + pamięć startu | punkty trasy wyprawy |
| pole startowe | ortogonalne, zapamiętywane | gdzie stoi gracz |
| uczenie | pietra_start/zle.json | brak |
| schody | tryb krok w obu kierunkach | brak |
| łopata | w cyklu (zużywa próbę nawet gdy z!=7) | w cyklu dziury, TYLKO_Z7 od 14.10 |
| limit | 150 s, 3 porażki, zawrócenie | 6 prób, awaria |

## 2. Statystyki

728 prób, 2884 s łącznie. Bezpośrednio (1 próba): 567 prób, 511 s, średnio 0,9 s. Skuteczność trybów: krok 406/485 (84%), R 298/353 (84%).

Czas udanej próby (telemetria 14.10): krok 1. próba mediana 0,7 s (p99 1,5 s); R 1. próba 0,9 do 1,0 s (p99 1,8 s); krok w 2. próbie 4,35 s; w 3. 5,6 s; R w 3. 9,1 s.

Per przejście (1. próba bez wstępnych kroków):
| przejście | n | 1. próba OK | mediana s | p90 s | max s |
|---|---|---|---|---|---|
| z8>z9 (32482,32296) | 148 | 82% | 1 | 6 | 269 |
| z9>z8 (32482,32296) | 132 | 70% | 1 | 12 | 67 |
| z8>z9 (32494,32289) | 88 | 78% | 1 | 5 | 65 |
| z9>z8 (32494,32289) | 75 | 91% | 1 | 2 | 59 |
| z8>z9 (32476,32272) | 66 | 89% | 1 | 1 | 7 |
| z9>z8 (32476,32272) | 54 | 93% | 1 | 1 | 62 |
| z8>z9 (32483,32285) | 33 | 91% | 1 | 1 | 6 |
| z9>z8 (32483,32285) | 33 | 97% | 1 | 1 | 9 |
| z8>z9 schody (32498,32270) | 32 | 91% | 1 | 2 | 6 |
| z9>z8 schody (32498,32270) | 41 | 7% | 5 | 6 | 50 |
| z7>z8 (32493,32259) | 7 | 29% | 33 | 54 | 89 |
| z9>z8 domysł (32482,32294) | 6 | 0% | 26 | 26 | 41 |
| z8>z7 (32348,32224) | 1 | 0% | 36 | 36 | 36 |

### Gdzie giną sekundy
- A. Pole startowe: 8 pre-kroków w zablokowane (32483,32296) z (32483,32297,9), 36 prób x ok. 13,9 s, ok. 500 s (297 stuknięć, 13.10 22:20 do 14.10 12:55). R po skosie z (1,1) miał 99/100 przed tą funkcją, więc ortogonalny start jest potrzebny tylko dla "krok". Zapis w `pietra_zle.json` już istnieje.
- B. Schody (32498,32270) z9>z8: R najpierw, krok działa. 36 prób x 4,7 s, ok. 170 s. R 3/40, krok 36/36 w 2. próbie.
- C. Ponowienie po nieudanym pierwszym kroku/R: 66 prób, 530 s (część to walka). Pierwszy krok w dół zawodzi 10 do 22%. Koszt nieudanej próby ok. 4,5 s (krok 1,5 s + `_po_przejsciu` 2 s + odstęp 1 s).
- D. Kandydat "domysł" (32482,32294,z9; ściana): 6 porażek po 26 s, ok. 166 s; plus (32348,32224) z8>z7, 144 pola od gracza. Przyczyna: tolerancja cheb<=1 względem b i kotwica na `a`.
- E. Wszystkie tryby wyczerpane, ok. 55 s: 5 przypadków. Tryby lina/wlasne/E/W/N/use/lopata/use_wlasne miały 0 sukcesów na ok. 27 prób.
- F. Przerwane (walka, STOP, restart): 729 s.

## 3. Znane problemy

1. (32482,32296) z9>z8, 8 kroków Up w zablokowane (32483,32296): efekt A. `_start` wymusza ortogonalne pole startowe dla R, choć R działa ze skosu i z własnego pola. Pole (32483,32296) jest ścianą/blokadą, a pamięć `pietra_zle` uczy się dopiero po wielu stuknięciach.
2. 14.10 10:10 łopata na schodach/dziurze (32476,32272) z8 (wypad): start po skosie (32477,32273,8), `_dziura` wybiera Left, 1. próba bez zmiany piętra, 2. próba "lopata" (jeszcze bez TYLKO_Z7), 3. krok Up działa. 5 z 6 przejść wypadu przez tę dziurę zawiodło w 1. próbie (mediana 3,45 s, maks 9,8 s). Podobnie 13.10 w pietra.py: łopata na (32482,32296,8) jako 2. próba "pewnego" przejścia.
3. Start z z7 (32400,32220) kończy się "wyczerpane pola przejścia": 14.10 11:30 trasa troll_cave nie ma punktów z7, `_resync` tworzy stan z `kand=[]`, 3 porażki w 3 s, bot STOP. Analogicznie 13.10 12:55:18 (porażka "domysł" > `_pietra_zawroc` > rozjazd a/z > 2 natychmiastowe porażki). To błąd planowania, nie przejścia.

## 4. Semantyka obiektów (8 przejść w jaskini trolli + z7)

- Dziura+drabina (7 z 8): flaga 2 tylko na piętrze górnym T(z8). Dół = krok na T(z8), ląduje (x,y,z9). Góra = Use (Ctrl+klik, "R") na T(z9) z dowolnego sąsiada, także po skosie i z własnego pola; ląduje (x,y+1,z8).
- Schody (32498,32270): flaga 2 na obu końcach. Dół = krok > (x,y+1,z9). Góra = krok > (x,y-1,z8). R działa rzadko (3/40).
- Wejście z7 (32493,32259): dziura bywa zasypana. Krok wchodzi na T bez zmiany piętra (sygnał "zamknięta"). Łopata działa z pola sąsiedniego, nie z własnego (0/5 z własnego, 1/1 z sąsiedniego 15:24:20); potem krok OK w 1 s o 15:25:07.

## 5. Propozycja: jedna wspólna logika

### Obiekt przejścia (z mapy doświadczenia, np. `trasy/przejscia.json` budowany z miejsca_troll.json)
```
{ id, typ: dziura_drabina | schody | dziura_zasypana,
  pole: (x,y,z_gorne),
  dol:  {tryb: krok, start: [pola ortogonalne], ladowanie: (x,y,z-1)},
  gora: {tryb: R | krok, start: [dowolne sąsiednie], ladowanie: (x,y+1,z)},
  stat: {tryb: {n, ok, mediana_s}}, zasypana_do: ts|null }
```
Typ klasyfikowany z flag (2 tylko na górnym = dziura+drabina; 2 na obu = schody), potwierdzany statystyką.

### Kolejność i terminy
- Kolejność prób wg skuteczności (ok/n z wygładzeniem), prior z typu: dziura_drabina dół=krok, góra=R; schody dół=krok, góra=krok; zasypana: krok > (jeśli krok wszedł na T bez zmiany piętra) łopata z sąsiedniego pola > krok.
- Terminy oczekiwania na zmianę piętra: krok 1,2 s, R 2,0 s (zamiast ok. 3,5 s + 1 s). Wartości z p99 (1,5 s i 1,8 s). Ponowienie ma być natychmiastowe po wykryciu braku zmiany.
- Usunąć tryby lina/wlasne/E/W/N/use/use_wlasne (0 sukcesów); lina tylko dla obiektu typu "lina" z mapy.
- Łopata wyłącznie dla zasypanych dziur: po kroku, który wszedł na T i pozostał na tym samym piętrze (sygnał zamknięcia), z pola sąsiedniego, następnie krok po ok. 1 s. Nie zużywać numeru próby gdy slot nie ma zastosowania.
- Start: dla "krok" pole ortogonalne z `start`; dla R aktualne pole (bez pre-kroków). Pre-kroki najwyżej 1 i tylko gdy pole nie jest znanym zablokowanym.
- Uczenie na bieżąco: po każdej próbie zapis (obiekt, tryb, pole startu, wynik, czas) do statystyk; porażka z potworem na lądowaniu lub w walce nie karze trybu; pole stuknięte 2 razy bez ruchu trafia do `zle`.
- Kandydat spoza listy obiektów ("domysł") dopuszczony tylko w promieniu ok. 3 pól od gracza i z flagą 2 w mapie.
- Resync i start na obcym piętrze: planowanie po grafie przejść (jak `_patrol_plan`) do najbliższego obiektu wiodącego do piętra celu, zamiast `kand=[]`.

## 6. Funkcje do zmiany
- pietra.py: `kandydaci`, `_resync` (graf zamiast pustego stanu), `_start/_na_start`, `TRYBY_*` (zastąpić kolejnością z danych), `_po_przejsciu` (terminy), `_odstep`, `_porazka`, slot "lopata".
- wypad.py: `zbuduj_etapy`, `_dziura`, `_lina`, `_proby_drabiny` (delegować do wspólnego modułu), dodać obsługę schodów.
- cavebot.py: `_pietra_tick`, `_pietra_zawroc`, `_idz_trasa`, stałe PIETRA_*, `CavebotDojscie`.
- Nowy moduł `przejscia.py`: ładowanie obiektów, wybór trybu, zapis statystyk.
- telemetria.py: znacznik testów, żeby nie mieszać z danymi produkcyjnymi.

## 7. Testy
- Rozszerzyć `testy/test_wielopietrowa.py` (symulator `s.zmiany`, `s.nielegalne`), uwaga na test nr 8 zakładający pierwszą próbę z pola ortogonalnego.
- Nowe: R ze skosu bez pre-kroków; schody góra krokiem; zasypana dziura (krok bez zmiany > łopata z sąsiedniego pola > krok); start z z7 (32400,32220) planuje do wejścia (32493,32259); brak łopaty na dziurze otwartej; kolejność trybów po zmianie statystyk; porażka z potworem nie obniża trybu; kandydat spoza promienia odrzucony.
- Regresja z logów: odtworzyć przypadki A, B, D, E jako scenariusze symulatora.

## 8. Ryzyka
- Skrócenie terminów (1,2 s / 2,0 s) przy lagu da fałszywe porażki; mitygacja: ponowna weryfikacja pozycji przed kolejną próbą.
- Uczenie na zanieczyszczonych danych (testy) wypaczy kolejność; wymagany guard telemetrii.
- Zmiana wspólna dla wypadu i patrolu dotyka dwóch stabilnych ścieżek; wdrożyć za flagą i porównać skuteczność.
- Zasypana dziura może otworzyć się po czasie (TTL nieznany); nie blokować jej na stałe.

## 9. Niepewne
- Przyczyna 10 do 22% nieudanych pierwszych kroków (lag? potwór na lądowaniu? trzymany klawisz kierunku?). `zatrzymaj_klik` wysyła tylko Escape i nie puszcza klawiszy, więc hipoteza trzymanego klawisza niesprawdzona.
- Przyczyna E (wszystkie tryby wyczerpane): prawdopodobnie przejściowa blokada, niepotwierdzona.
- Czas życia otwartej dziury z7.
- Rozbieżność liczników wypadu: telemetria 42/26 (drabina/dziura) vs log 38/22.
