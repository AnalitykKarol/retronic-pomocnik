# SPEC: mapa spotów i trasy z mapy, wysyłanie postaci na spot - 17.10 — SZKIC, czeka na zatwierdzenie Karola

Cel: Karol nie rysuje tras ręcznie. Z mapy klienta (`mapa/map74.otmm`, `mapa.py`) i danych spawnów (`dane_tibia/serwer74/`,
`serwer76_jamera/`) powstaje (1) obraz spotu z trasą, (2) interaktywna mapa HTML, (3) plik trasy dla bota i wysłanie postaci.

## Stan wyjściowy (zweryfikowany 17.10)

- `mapa.py droga` liczy A* po jednym piętrze: Port Hope (32623,32773,z7) -> wejście w dżunglę swamp trolli (32686,32599,z7), 237 pól, 12 ms.
- `mapa.py podglad` rysuje PNG wycinka (z trasą). Przykład: scratchpad `port_hope_podglad.png`.
- Format trasy bota: lista `[x,y,z]` + `.meta` ze znacznikami (`start`, `przed_zmiana_pietra`, `schody_w_gore`), np. `trasy/do_miasta.json`.
- Mapa nie liczy przejść pięter ("bez przejść pięter"); schody i dziury mają flagę `BEZ_DROGI` (2) i bywają nauczone (`dziury_nauczone.json`).
- Klient i `straznik.py` działają w tle (sprawdzone `ps`). Każdy test na żywo wymaga zgody Karola.

## Fazy (każda zamknięta bramką)

| Faza | Wynik | Weryfikacja | Dotyka gry? |
|---|---|---|---|
| F0 | Rozpoznanie: czy z flagi 2 da się wyliczyć schody/dziury i połączyć piętra z7-10 w dżungli | zrzut + lista przejść, porównanie z `dziury_nauczone.json` | nie |
| F1 | Obraz spotu: wycinek mapy + spawny + trasa + podpisy | PNG obejrzany przez Karola | nie |
| F2 | Interaktywna mapa HTML (lokalny plik, bez publikacji): piętra, warstwy spawnów, trasa, klik = współrzędne | makiety do wyboru PRZED kodem; zrzut z przeglądarki headless | nie |
| F3 | Generator trasy `trasy/<nazwa>.json` + `.meta` z wybranego punktu na mapie | test: każda para sąsiednich pól przechodnia wg mapy; trasa zgodna z formatem `cavebot` | nie |
| F4 | Wysłanie postaci po trasie | przebieg na żywo z Karolem przy ekranie, jedno wywołanie, pokrętło domyślnie `0` | tak |

## Do ustalenia z Karolem (UNKNOWN, nie zgadujemy)

1. Gdzie jest teraz postać i który spot jest pierwszym celem: swamp trolle koło Venore (pieszo z Thais) czy dżungla koło Port Hope (inny ląd, wymaga łodzi; NPC od łodzi nie ma w danych).
2. Gdzie żyje kod: główny checkout (`ruch-r1-1014`) czy osobna gałąź/worktree (UI zostaje na `feat/ui-reczne-ai`).
3. Poziom, profesja i ekwipunek postaci (ryzyko trasy przez dżunglę: poison spidery, slime).
4. Czy bot ma po drodze walczyć (jak w `troll_do_miasta`), czy omijać potwory (`_unikanie_*`).
5. Wejścia do jaskiń z8-10: rozstrzyga F0.

## Poza zakresem

Zmiana celów nagranych tras, mapa Port Hope z 7.6 (jameraServer76) jako źródło geometrii (geometria idzie z klienta), publikacja mapy poza komputer (poziom 3, osobna zgoda).

## Postęp 17.10 (wieczór)

- **F1 wykonane na żywo** dla dwóch map: Port Hope -> dżungla swamp trolli (`mapy/port_hope_swamp_trolle.*`) i pętla patrolowa po jaskini goblinów Edron z8 (`mapy/patrol_gobliny_z8.*`). Obie obejrzane przez Karola.
- **Odpowiedź na pytanie 1-4 (częściowo):** Karol jest na miejscu w Edronie (z8), start = pozycja postaci (odczyt przez `nagraj_trase.pozycja`), bot nie walczył po trasie.
- **F0 częściowo:** mapa nie zna celów przejść między piętrami; lina nie jest typem przejścia w formacie tras (wymaga sprawdzenia w `cavebot.py`).
- **Decyzja Karola:** kierunek zatwierdzony ("będzie klasa, trzeba to zapisać"): z mapy robimy nowe spoty i dojścia z miasta. Kolejne kroki: F2 (interaktywna mapa, makiety przed kodem), F3 (generator trasy do `trasy/`), F4 dopiero po ustaleniu liny i przebiegu na żywo.
- **Otwarte (UNKNOWN):** czy bot umie użyć liny; jak wejść do z10 goblinów; źródło prawdziwych połączeń pięter (opcja: mapa 7.6 `world.otbm` z jameraServer76).
