# Mapy spotów i trasy z mapy klienta (prototyp, 17.10)

Cel: nie rysować tras ręcznie. Z mapy klienta (`../../mapa/map74.otmm`, moduł `../../mapa.py`) i danych spawnów powstaje
obraz, trasa dojścia i pętla patrolowa po spawnach. Specyfikacja: `../SPEC_mapa_trasy_1017.md`.

## Co tu jest

| Plik | Co to |
|---|---|
| `port_hope_swamp_trolle.png/.json`, `rysuj_trase.py` | Port Hope (środek miasta) -> dżungla swamp trolli, 186 pól po powierzchni z7 |
| `patrol_gobliny_z8.png/.json`, `patrol.py` | Edron, jaskinia goblinów z8: 12 przystanków, ok. 39 goblinów, pętla 273 pola, start przy linie |
| `rook_raty_z8.png/.json`, `../../generuj_trasy_rook.py` | Rookgaard, jaskinia szczurów z8 tuż pod miastem (20.10): składowa 872 pola, 25 przystanków, 34 szczury, pętla 491 pól; dojście z7 do wejścia (32046,32221) |
| `rook_kanaly_z11.png/.json`, tamże | Rookgaard, kanały z11 (20.10): składowa 774 pola, 17 przystanków, 35 szczurów, pętla 479 pól; dojście = odwrócone `do_miasta` |

Skrypty to prototypy (stałe współrzędne w kodzie). Skrypt wymaga `skladowa_z8.json` (wynik flood-fill z pozycji gracza), więc `patrol.py`
nie uruchomi się sam bez kroku 2 poniżej (przykładowy wynik jest obok: `skladowa_z8.json`); docelowo F3 ma to zamknąć w jednym poleceniu.

## Metoda (działa, sprawdzona na żywo)

1. **Pozycja postaci** (tylko odczyt, bez inputu do gry): `nagraj_trase.pozycja(nagraj_trase.nazwa_postaci())` zwraca `(x, y, z)` z gniazda `straznik.py`.
2. **Dostępny obszar**: flood-fill po polach przechodnich piętra (`mapa.Mapa.pole`: flaga 1 widziane, 4 ściana, 2 schody/dziura/lina) od pozycji gracza.
3. **Spawny w obszarze**: `../serwer74/potwory_pelne.json` (CipSoft 7.4, ten sam układ co mapa klienta), pole `spawny` (x, y, z, ilość, respawn_s).
4. **Kolejność**: najbliższy sąsiad + 2-opt po odległościach A* (`Mapa.droga`), pętla wraca na start.
5. **Obraz**: PIL, kolory minimapy klienta, trasa czerwona, spawny różowe, numer = kolejność.
6. **Zrzut gry (do weryfikacji)**: tylko okno gry, nie pulpit: `hyprctl clients -j` (okno `Vncviewer`), potem `grim -g "x,y WxH" plik.png`.

## Czego mapa NIE wie (ważne przy planowaniu)

- **Przejścia między piętrami.** Schody, dziury i liny mają w mapie flagę 2 (`BEZ_DROGI`), ale nie mówi ona, dokąd prowadzą.
  Znamy tylko przejścia nauczone z nagranych tras (`trasy/*.meta`, `dziury_nauczone.json`).
- **Żółta kropka (kolor 210) to każda zmiana piętra: schody, lina, dziura albo drabina.** Minimapa nie mówi, które to. Typ rozstrzyga nagranie przejścia (`nagraj.sh`) albo log wypadu. 17.10 w jaskini goblinów Edron cztery liny i jedna drabina (z8 -> z7 przy (33165,31827)) wyglądają w mapie tak samo.
- **Lina.** Używasz jej na polu z8 (x, y), a lądujesz na z7 o jedno pole na południe, czyli (x, y+1).
  Przykład Edron (sprawdzone w grze 17.10 23:15, nagranie `dane_tibia/nagrania/gobliny_edron_lina_potw.json`): lina na (33107, 31847, z8), używana ze stania (33107, 31846, z8), lądowanie (33107, 31848, z7); otwór na z7 to (33107, 31847, z7), zejście ląduje w (33107, 31847, z8). Wskazówka z mapy: żółte pole (kolor 210) na z8 pod żółtym otworem na z7 = pole liny; pole lądowania nie ma flagi 2. Bot zna linę (`wypad.zbuduj_etapy`: stoi obok R = (lądowanie.x, lądowanie.y-1)).
- **Mapa to tylko widziane pola.** Pola nigdy niewidziane są traktowane jak ściana. Plik klienta (`AppData/.../map74.otmm`) zapisuje się przy zamknięciu klienta
  (17.10 stan z 10:00), więc świeżo odkryte fragmenty nie są jeszcze w mapie.
- **Rozbieżności dwóch źródeł spawnów.** `monster.db` (CipSoft) i `Tibia74-spawns.xml` (gravak) dają inne liczby (swamp troll 82 vs 99).

## Wnioski z pierwszych dwóch map

- Port Hope: duży spot swamp trolli leży 150-200 kratek na północ od miasta (x 32650-32715, y 32575-32690, z7-10); na powierzchni z7 spawny są rozproszone.
- Edron, jaskinia goblinów: na z10 mapa ma cztery oddzielne kawałki bez widocznego dojścia, na z8 jedną dużą komorę z wyjściem na linę; sama mapa nie wystarczała do trasy z miasta
  (powierzchnia z7 Edronu kończy się w mapie na x = 33141), więc ostatni odcinek trzeba przejść raz i nagrać (`nagraj_trase.py`).
E
## Rookgaard, szczury (20.10)

`python3 -I generuj_trasy_rook.py [--zapisz]` (z `pomocnik/`) liczy z mapy i spawnów szczurów dwie trasy (`mapy.json`: `rook_raty_z8`, `rook_kanaly_z11`; test `testy/test_trasy_rook.py`).
Uruchomienie: `MAPA=rook_raty_z8 TRYB=ostrozny ./uruchom.sh` (na z7 bot najpierw idzie dojściem, na z8/z11 startuje od razu).

- **z8 pod miastem:** wejście z miasta to (32046,32221,z7). Wniosek z mapy: to jedyne pole z kolorem 210 i flagą 2 po obu stronach (z7 i z8 w tym samym polu) przy składowej 872 pól; pozostałe pola z flagą 2 przy tej składowej na z7 mają zwykły kolor (blokujące przedmioty). **Typ przejścia (dziura, schody, kratka) i pole lądowania niezweryfikowane w grze**: w dojściu przyjęto lądowanie (32046,32222,z8). Pierwsze przejście sprawdzić na żywo (jedno wywołanie) i poprawić `rook_raty_z8_dojscie`, jeśli lądowanie jest inne.
- **z11 kanały:** dojście to odwrócone nagranie `do_miasta` (z7 -> z8 -> z9 -> z10 -> z11, przejścia sprawdzone w grze). Dziura nauczona (31979,32153,z11) jest ścianą dla A*.
- Obie składowe zawierają tylko szczury (z listy 114 potworów serwera 7.4); pozostałe składowe z8 pod miastem (np. 159 pól z robakiem i pająkiem) pominięte.
