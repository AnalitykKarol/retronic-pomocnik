# Mapy spotów i trasy z mapy klienta (prototyp, 17.10)

Cel: nie rysować tras ręcznie. Z mapy klienta (`../../mapa/map74.otmm`, moduł `../../mapa.py`) i danych spawnów powstaje
obraz, trasa dojścia i pętla patrolowa po spawnach. Specyfikacja: `../SPEC_mapa_trasy_1017.md`.

## Co tu jest

| Plik | Co to |
|---|---|
| `port_hope_swamp_trolle.png/.json`, `rysuj_trase.py` | Port Hope (środek miasta) -> dżungla swamp trolli, 186 pól po powierzchni z7 |
| `patrol_gobliny_z8.png/.json`, `patrol.py` | Edron, jaskinia goblinów z8: 12 przystanków, ok. 39 goblinów, pętla 273 pola, start przy linie |

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
- **Lina.** Używasz jej na polu z8 (x, y), a lądujesz na z7 o jedno pole na południe, czyli (x, y+1).
  Przykład Edron: lądowanie (33107, 31847, z7) <-> lina na (33107, 31846, z8). Format tras bota nie ma typu "lina" (nie sprawdzone, czy bot umie ją użyć).
- **Mapa to tylko widziane pola.** Pola nigdy niewidziane są traktowane jak ściana. Plik klienta (`AppData/.../map74.otmm`) zapisuje się przy zamknięciu klienta
  (17.10 stan z 10:00), więc świeżo odkryte fragmenty nie są jeszcze w mapie.
- **Rozbieżności dwóch źródeł spawnów.** `monster.db` (CipSoft) i `Tibia74-spawns.xml` (gravak) dają inne liczby (swamp troll 82 vs 99).

## Wnioski z pierwszych dwóch map

- Port Hope: duży spot swamp trolli leży 150-200 kratek na północ od miasta (x 32650-32715, y 32575-32690, z7-10); na powierzchni z7 spawny są rozproszone.
- Edron, jaskinia goblinów: na z10 mapa ma cztery oddzielne kawałki bez widocznego dojścia, na z8 jedną dużą komorę z wyjściem na linę; sama mapa nie wystarczała do trasy z miasta
  (powierzchnia z7 Edronu kończy się w mapie na x = 33141), więc ostatni odcinek trzeba przejść raz i nagrać (`nagraj_trase.py`).
E