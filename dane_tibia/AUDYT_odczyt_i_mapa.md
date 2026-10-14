# Audyt: co czytamy z gry, co mamy z mapy, czy model LLM może sterować postacią

Data: 2026-10-13. Tryb: tylko odczyt (kod, pliki danych, kilka odczytów gniazda; żadnego inputu do gry, bota nie ruszałem).
Oznaczenia: **[POTW]** = potwierdzone w kodzie albo zmierzone teraz na żywo, **[HIP]** = hipoteza (wiedza o OTClient/Tibii, nieweryfikowana w tym repo), **[BRAK]** = nie ma w kodzie.

## 0. Wniosek w skrócie

1. Czytamy już dość, żeby model widział świat "na poziomie decyzji": pozycja własna, stwory z pozycją/HP%/kierunkiem/flagą "atakowany"/"bije nas", HP/mana/cap/exp/level, ekwipunek (id + ilość), otwarte kontenery z przedmiotami, cały czat (z kanałami, nadawcą, kolorem), w tym "Loot of ...".
2. Mapa jest pełna (16 pięter, cały serwer, ~6 mln pól widzianych), z flagami przechodnie/ściana/"zmiana piętra" i A* na jednym piętrze. Schody w dół i dziury rozpoznajemy z mapy (8/8 na nagranych przejściach), w górę trzeba wnioskować z odwrócenia, drzwi to ściana w mapie.
3. Czego nie czytamy: skille, flagi statusu (trucizna, paraliż, haste, PZ), prędkość, outfit, przedmioty leżące na polach (pola ognia, zwłoki), VIP, cooldowny czarów. Wszystko to jest w pamięci klienta [HIP], ale w kodzie nie ma ani jednego odczytu.
4. Brakuje jednego endpointu "swiat", który zwraca spójny snapshot (dzisiaj model dostaje tekst złożony przez mozg.py z kilku zapytań). Propozycja w sekcji 5.
5. Dane przedmiotów mają wagę i ID klienta, ale brakuje w nich rope, shovel, backpack, bag (zbiór 307 przedmiotów to tylko 11 kategorii). Wagi tych czterech: patrz sekcja 3.

---

## 1. Co czytamy z pamięci klienta

Architektura [POTW]: `straznik.py` uruchamia grę jako proces potomny (subreaper), serwuje JSON po gnieździe Unix `$XDG_RUNTIME_DIR/retronic-pomocnik.sock` (u nas `/run/user/1000/retronic-pomocnik.sock`, 0600, jedna linia JSON na zapytanie i na odpowiedź, serwer jednowątkowy). Logika w `rdzen.py` (hot-reload po zmianie pliku), `kontenery.py`, `wiadomosci.py`. Odczyt przez `/proc/<pid>/mem` w trybie "rb" i skan regionów rw poniżej 4 GB.

### 1.1 Komendy gniazda [POTW, w kodzie `Pamiec.obsluz`]

| cmd | parametry | zwraca | uwagi |
|---|---|---|---|
| `status` | - | pid, liczba kandydatów, typ, liczba regionów | diagnostyka skanera |
| `gracz` | - | `hp,max_hp,mana,max_mana,cap,max_cap,exp,level,procent,adres` | blok 9 doubli; znaleziony skanem wzorca (level/exp zgodne ze wzorem Tibii). Cache adresu, pełny skan 1-2 s tylko po utracie bloku |
| `stwory` | `maks_wiek` | lista `{id,nazwa,gracz,x,y,z,hp,kierunek,atakowany,ramka,bije_nas,adres}` + `skan,wiek_s,wiek_pelnego_s` | skan wzorca obiektu Creature (4 x float 1.0, ID, std::string nazwy). Wątek w tle odświeża co 0,05-0,15 s |
| `stwor` | `adres,id` | jeden stwór spod znanego adresu | jeden pread, do pościgu |
| `poscig` | `nazwa,adres,id` | pozycja gracza + stwór | jedna odpowiedź zamiast dwóch |
| `pozycja` | `nazwa` | `{x,y,z}` postaci o nazwie | jedno pread po zapamiętanym adresie |
| `cel_ataku` | - | stwór z czerwoną ramką (nasz cel) albo `{id:null}` | z bool "static square" klienta |
| `kontenery` | `ekwipunek:true` opcjonalnie, `diagnostyka` | lista `{numer,nazwa,id,pojemnosc,przedmioty:[{id,ilosc,slot}]}`; z `ekwipunek`: `{slot:{id,ilosc}}` | std::map Game::m_containers; ekwipunek = tablica 11 slotów LocalPlayer |
| `wiadomosci` | `od,epoka,kanal,limit,skan` | `{wiadomosci:[{nr,ts,czas,nadawca,tekst,kanal,kolor,t,bufor}],znacznik,epoka,kanaly,zakladki}` | UILabel w `consoleBuffer` każdej zakładki; przyrostowo po `nr` |
| `szukaj`, `zawez`, `sledz`, `pokaz`, `czytaj`, `bajty`, `hexdump`, `profil_stworow` | | | narzędzia do badania pamięci (nowe pola), nie do sterowania |

### 1.2 Pola, które realnie mamy

Zmierzone na żywo teraz (jeden odczyt każdej komendy):

- `gracz`: `{hp 210/210, mana 115/185, cap 14, max_cap 14, exp 26524, level 13, procent 49}`. **Uwaga [POTW anomalia]: `cap == max_cap == 14`.** Protokół 7.4 wysyła klientowi tylko wolną pojemność, więc `max_cap` prawdopodobnie nie jest prawdziwym maksimum [HIP]; z logów wynika, że `cap` faktycznie się zmienia (32, 104 oz w `wypad_start`). Do decyzji "ile jeszcze uniosę" używać `cap` (wolne oz), nie ilorazu `cap/max_cap`. Jednostka w oz (bot ma dzielenie /100 dla `max_cap>5000`, niezweryfikowane).
- `stwory` (4 sztuki w chwili pomiaru, w tym gracze, `gracz = id < 0x40000000`): klucze `adres, atakowany, bije_nas, gracz, hp, id, kierunek, nazwa, ramka, x, y, z`. **Pozycję własną dostajemy stąd** (stwór o nazwie postaci), `pozycja` to tylko szybka ścieżka.
- `kontenery`: 2 otwarte (`backpack` pojemność 20, 16 i 8 przedmiotów), przedmiot = `{id, ilosc, slot}`. Brak wagi (waga tylko z `przedmioty.json`).
- `ekwipunek`: sloty 1 głowa 3376 (studded helmet), 3 plecak 2854, 4 zbroja 3359 (brass armor), 5 prawa ręka 3409 (steel shield), 6 lewa ręka 3271 (spike sword), 7 nogi 3557 (plate legs), 8 buty 3552 (leather boots), 10 amunicja/strzały 3003 (rope; slot 10 używany jako schowek na linę).
- `wiadomosci`: kanały Default, Game-Chat, Trade, Server Log + prywatne; `znacznik=8986` wiadomości. Rozpoznawane prefiksy systemowe: `You `, `Loot of`, `Monster loot`, `Welcome `, `Your `, `Warning`, `Server `.

### 1.3 Co klient trzyma, a my nie czytamy

| Dane | Status | Komentarz |
|---|---|---|
| **Skille** (sword, shield, magic level, % do następnego) | [BRAK], [HIP] w `LocalPlayer::m_skills` | W 7.4 serwer wysyła skille w pakiecie stats; klient ma je w pamięci. Wzorzec do znalezienia: `skille` obok bloku gracza, jak `POLA_GRACZA`. Do `szukaj`/`zawez`: zmiana po treningu |
| **Flagi statusu** (poison, burning, paralyze, haste, drunk, magic shield, PZ, battle, w-skórze) | [BRAK], [HIP] `m_states` (u32 bitmask) | Dziś bot tego nie wie z pamięci: ucieczka i leczenie idą po HP. Paraliż i trucizna to najbardziej opłacalny brakujący odczyt |
| **Prędkość własna / `m_speed`**, haste | [BRAK], [HIP] | Przydatne do liczenia czasu kroku (dziś `kalibracja_krokow.py` mierzy to empirycznie) |
| **Kierunek własny** | [POTW] odczytywany (`kierunek` u32 w obiekcie stwora, offset 0x1C), [HIP] interpretacja 0..3 = N,E,S,W | Pole jest w `stwory`, ale nie ma w repo testu semantyki |
| **Cel ataku / follow** | [POTW] przez ramki: czerwona = atak, zielona = follow, czarna chwilowa = ktoś nas bije | To nie jest ID celu z pamięci gracza, tylko wnioskowanie z ramki obiektu stwora (przy kilku aktywnych: `ilu`) |
| **Lista battle** | [BRAK] osobnego odczytu, [HIP] to pochodna `stwory` | `stwory` to wszystkie obiekty Creature w pamięci (także z innych pięter i z cache), bez gwarancji "widoczny teraz". Filtr po `z` i `wiek_s` na odpowiedzialności wołającego |
| **Outfit, kolor, światło, HP-bar, skull, party shield, emblem** | [BRAK], [HIP] pola obiektu Creature | Skull/party przydatne do rozróżnienia PK i drużyny |
| **Przedmioty na polach (tile items)** | [BRAK] | Pola ognia ogień wykrywa `ogien.py` ze zrzutu ekranu (kolor), zwłoki otwiera klik. Tabela `m_tiles` w `Map`/`MapView` jest w pamięci [HIP] |
| **Kontener: waga, nazwa przedmiotu, opis** | [BRAK] | Waga tylko z danych; ID -> nazwa tylko mały słownik `NAZWY` w kontenery.py (6 wpisów) |
| **VIP lista** | [BRAK], [HIP] | Nieistotne dla lovienia |
| **Cooldowny czarów/grup, hotkeye** | [BRAK], [HIP] | Dziś bot wylicza czas po wysłaniu czaru |
| **Okna NPC / trade / dialog** | [POTW pośrednio] | Dialog z NPC wraca w kanale Default czatu (`trasy/sklep_torche.json` ma `odpowiedzi_npc`), ale nie ma odczytu otwartego okna trade |
| **Pozycja i stan innych okien UI** (otwarte okno "Skills", "Battle" zwinięte) | [BRAK] | `loot.py` zakłada układ ekranu i rozpoznaje okna po ikonach/tytułach wzorcami PNG (`ikony/`). To jedyny kawałek oparty o rozpoznawanie obrazu |
| **Soul points, stamina, offline training** | [BRAK], [HIP] | Brak potrzeby |

Uwaga o pełności odczytu: pozycja stwora i własna pochodzą z `x,y,z` obiektu (u32,u32,u8). Poza polem widzenia klient zwykle usuwa stwory z mapy, więc to "to, co widzi klient" (okno 15x11, plus bufor), nie "cały świat".

---

## 2. Mapa, trasownik, wejścia do jaskiń

### 2.1 Plik i format [POTW]

`mapa/map74.otmm` (1,66 MB, wersja 1, wygenerowany 2026-10-11): minimapa OTClienta, nie plik serwera. Czytnik: `mapa.py` (`Mapa`). Wczytanie: ~31 ms (3267 bloków 64x64, rozpakowanie zlib leniwie, ~0,1 ms na blok).

- Bloki wg pięter: z0: 15, z1: 44, z2: 70, z3: 115, z4: 163, z5: 234, z6: 288, **z7: 409**, z8: 373, z9: 345, z10: 303, z11: 252, z12: 230, z13: 167, z14: 145, z15: 114 (czyli wszystkie 16 pięter; z7 = powierzchnia).
- Na pole 3 bajty: `flagi, kolor, prędkość`.
- Histogram flag (liczba pól w zapisanych blokach): 0 = niewidziane 7,37 mln; 1 = widziane i przechodnie 1,26 mln; 5 = widziane i nieprzechodnie (ściana/woda/skała) 4,73 mln; 3 = widziane, przechodnie, "zmiana piętra/bez drogi" 20,8 tys.; 7 = nieprzechodnie z flagą 2: 1,8 tys.
- `flagi`: bit 1 = pole widziane, bit 2 = OTClient nie prowadzi tędy drogi ("not pathable": schody/dziury/rampy, czasem pole z polem magicznym), bit 4 = nieprzechodnie. [POTW, docstring + zgodne z OTClient]
- `kolor`: indeks palety Tibii 6x6x6 (255 = lita skała, 210 = żółty = zmiana piętra). Najczęstsze: 255 (3,39 mln), 24, 40, 129, 121, 114, 86 (trawa, woda, podłogi), 210 (20,9 tys. pól schodów).
- `prędkość`: bajt prędkości podłoża (najczęściej 0 dla nieprzechodnich, 10, 15, 16, 12, 14, 20). [HIP] to `groundSpeed/10`. A* (`droga`) tego **nie używa** (koszt 1 prosto, 3 po skosie).

Zasięg współrzędnych w pliku: bloki od x=0 do ~35199 i y do ~42879 (indeksy), realny serwer to x ~31744-34560, y ~30976-32896. Powierzchnia testowana: Thais, Venore, Darashia, Carlin, Kazordoon, Edron, centra spotów z `spoty.json`; w oknach 41x41 wokół nich pola są w 100% "widziane" (1681/1681), więc mapa pokrywa te obszary (nie jest dziurawa jak "tylko co chodził gracz").

Skąd plik [POTW z nagłówka]: standardowy OTMM z OTClienta (z klienta Retronic, nie z naszych tras); `waliduj_trase.py` i `znane_bledy_mapy` w `miejsca_troll.json` pokazują, że bywają pojedyncze błędy ("flaga 5 mimo koloru podłogi" na (32473,32273,9)).

### 2.2 Co potrafi API mapy [POTW]

| Pytanie | Funkcja | Wynik |
|---|---|---|
| "co jest na polu (x,y,z)" | `Mapa.pole(x,y,z)` -> `(flagi, kolor, prędkość)` albo `None` | CLI: `mapa.py pole x y z` |
| "czy da się wejść" | `przechodnie(x,y,z)` -> True/False/None (None = niewidziane) | |
| "czy to schody/dziura" | `schody_lub_dziura(x,y,z)` | flaga 2 |
| "co jest wokół" | pętla po `flagi()`; `mapa.py podglad z x y r plik.png` rysuje PNG | brak gotowej funkcji "zwróć okno NxN jako tekst" (do dopisania, 20 linii) |
| "czy da się przejść z A do B (to samo piętro)" | `droga(start, cel, zajete, dlugosc, skosy, limit=20000, schody, nieznane, znane)` | A* na kubełkach, 8 kierunków, zwraca listę pól albo None; typowo < 1000 rozwiniętych pól dla 30 pól trasy |
| "przejście między piętrami" | `pietra.py kandydaci(mapa, a, b)` + `wypad.py` | patrz 2.3 |
| "drzwi" | brak osobnej flagi | zamknięta drzwi = ściana (flaga 5): trasa `drzwi_frodo` przechodzi przez (32365,32208,7) z flagą 5. Obsługa drzwi jest w `wyprawa_sklepy.json: "drzwi"` + klik "Use" |

Czego mapa nie ma: sprite'ów przedmiotów i potworów na polach, stanu drzwi, zasięgu aktualnych pól ognia (`ogien.py` ze zrzutu), nazw lokacji.

### 2.3 Łączniki pięter (schody/dziury/liny/drabiny)

Reguły zaimplementowane w `pietra.py` i zweryfikowane na żywo w `wypad.py` [POTW]:

- **w dół**: pole z flagą 2 na piętrze `z`, lądowanie `(x, y, z+1)` (dziura) albo sąsiednie.
- **w górę**: pole `R` na piętrze `z`, nad którym (piętro `z-1`) leży dziura z flagą 2; lądowanie `(R.x, R.y+1, z-1)`; próby: Ctrl+klik (drabina), krok (schody), lina z plecaka (`ID_LOPATA = 3457` to shovel do odkopania zasypanej dziury, rope = 3003).

Sprawdzenie na nagranych przejściach trolli (`trasy/miejsca_troll.json`, 8 przejść): **wszystkie 8 schodów w dół ma flagę 2 na górnym piętrze** (8/8). Pola dolne (schody w górę) mają zwykle flagę 1 (zwykłe przechodnie): mapa **nie oznacza** schodów w górę, trzeba wnioskować odwrotnością (z dolnego pola w pobliżu lądowania). W jednym przypadku dolne pole też ma flagę 2 (para schodów).

### 2.4 Wejścia do jaskiń

Potwierdzone nagraniami Karola [POTW]:

- **Troll cave Thais** (z7 -> z8): zejście z powierzchni z pola ok. `(32492, 32259, 7)`; pierwszy punkt na z8 to `(32493, 32260, 8)` (trasa `depo_troll_cave.json`: 111 punktów od `(32348,32225,7)` depo do `(32492,32261,8)`; `troll_z_miasta.json`: 77 punktów od `(32377,32201,7)`). Z8 wewnątrz to ok. x 32474-32506, y 32260-32297; z9 pod spodem, 8 par schodów między z8 i z9 w `miejsca_troll.json` (np. `(32484,32265,8)` -> `(32484,32265,9)`, `(32476,32272,8)` = gniazdo, `(32482,32296,8)`). **Zadane `ok. 32508,32277,z9` leży w obrębie jaskini (z9, strona wschodnia), ale nie jest wejściem; wejście to z7 `(32492,32259)`.**
- **Thais orc cave** (T1 w `spoty.json`, środek `(32388,32204,11)`, pietra 11): **brak nagrania wejścia** i `wejscie` w spotach = "nieznane". Z mapy: patrz niżej.
- **Rotworm Thais SE (T3)**: środek `(32462,32287,9)`, w danych jest tam 7 rotwormów, 8 os, 8 trolli, 3 szkielety. To ta sama jaskinia co troll cave, od strony wschodniej z9 (w modelu poniżej droga idzie przez znane schody trolli).

Wyznaczanie z mapy programowo (wykonałem w skrypcie jednorazowym, **nie dodałem go do repo**): Dijkstra po siatce 1100x960x16 pól z modelem "chodzenie po polach bez flagi 2; wejście na pole z flagą 2 = zejście o piętro z lądowaniem w sąsiedztwie; odwrócone krawędzie jako wejście w górę" (koszt: prosto 1, skos 3, przejście piętra 14).

| Cel | Start | Wynik modelu | Ocena |
|---|---|---|---|
| Troll cave z9 `(32508,32277,9)` | świątynia Thais `(32369,32241,7)` | osiągalne, koszt 325, 4 przejścia pięter przez schody w `(32488,32264,7)` i znane schody trolli `(32484,32265,8)`, `(32478,32269,8)`, `(32494,32289,8)` | zgodne z nagraniami (inna dziura wejściowa, ale w tym samym obszarze). [POTW porównanie] |
| T3 rotworm `(32462,32287,9)` (najbliższe pole `(32472,32281,9)`) | Thais | osiągalne, koszt 296, 4 przejścia | wspólny wlot z troll cave. [HIP, nie testowane na żywo] |
| T1 orc cave `(32388,32204,11)` (najbliższe `(32389,32202,11)`) | Thais | osiągalne, koszt 436, 6 przejść: m.in. `(32334,32206,7)` w dół, `(32334,32208,8)` w dół, `(32371,32242,9)` w dół, `(32388,32255,10)` w dół | ścieżka wygląda wiarygodnie na końcu, ale początek ma sztuczne "w górę/w dół" przez z6 `(32327,32205,6)`, czyli model produkuje artefakty. **[HIP] wejścia nie ma co brać wprost, wymaga walidacji ręcznej lub nagrania** |
| T2 `(32365,32114,9)` | Thais | osiągalne, koszt 225, 2 przejścia: `(32347,32123,7)`, `(32368,32112,8)` | [HIP] |
| T4 minotaury `(32429,32139,15)` | Thais | koszt 909, 12 przejść, w tym kilka "w górę" | podejrzane, model za luźny dla z14-15 |

Wniosek: **da się wyznaczyć kandydatów wejść i sensowną kolejność pięter z mapy** (flaga 2 + odwrócenie), ale bez nagrania/walidacji model pomyli kierunek schodów i powoduje fałszywe skoki przez z6. Do sterowania modelem LLM potrzebny jest dopracowany graf łączników z kierunkiem (np. wyciągany z nagrań: `miejsca_troll.json` ma już taki graf dla troll cave: `przejscia`, `laczniki`, `graf` z komponentami spójności i odległościami A*). Brakuje tego samego grafu dla Thais orc cave, rotwormów i innych spotów.

Wejść do jaskiń nie ma w `spoty.json` (pole `wejscie` = "nieznane z danych spawnow") [POTW].

---

## 3. dane_tibia: przedmioty, potwory, spoty

### 3.1 Struktura [POTW]

- `przedmioty.json`: 307 przedmiotów w 11 kategoriach (miecze 30, inne_bronie 48, helmy 32, zbroje 27, nogi 12, buty 4, tarcze 34, amulety 24, pierścienie 26, jedzenie 39, runy_i_inne 31). Pola: `id_klienta, nazwa, waga_oz, atk, def, arm, flagi, id_ot_zgadniety, cena_kupno_u_npc{min,max,najczestsza,szczegoly}, cena_sprzedaz_do_npc, gdzie_kupic, bonus_skill, ochrona..., swiatlo, odzywianie`. **Tak, każdy przedmiot ma `waga_oz` i `id_klienta` (= TypeID CipSoft = id sprite w kliencie 7.4).**
- Zgodność ID z kliencie Retronic [POTW]: `ekwipunek` na żywo zwraca 3271 (spike sword), 3409 (steel shield), 3359 (brass armor), 3557 (plate legs), 3552 (leather boots), 3376 (studded helmet), wszystkie istnieją w `przedmioty.json` z tymi samymi nazwami. Dodatkowo kontenery.py ma 3031 gold coin, 3607 cheese, 3577 meat. Również ham 3582 w `wyprawa.py`. Zgodność 1:1 dla 9 sprawdzonych ID.
- Weryfikacja wagi na żywo [POTW]: `logi` pokazują "Wyprawa: waga ham z delty cap: 20.05 oz", `przedmioty.json` ma ham = 20.0. Domyślna wartość w `wyprawa.py WAGI_DOMYSLNE` (ham 13.6) jest **błędna**, dane są poprawne; `meat` 13.0 zgodne.
- `potwory.json`: 114 rekordów (24 priorytetowe), pola m.in. `hp, exp, atak_max_szac, atak_skill, obrona, pancerz, ucieczka_hp, loot[{przedmiot,id_klienta,szansa_proc,max_ilosc}]`.
- `spoty.json`: 17 spotów (E1-E5 Edron, T1-T4 Thais, C1-C4 Carlin, K1-K2 Kazordoon, V1 Venore, D1 Darashia), pola: `lokalizacja_srodek, obszar{x1,y1,x2,y2,pietra}, wejscie (= "nieznane"), potwory[], odleglosc_do_depo_kratek (linia prosta od znacznika miasta, bez pięter), exp_h_szac (model), min_lvl_zalecany, ryzyko`.

### 3.2 Wagi kluczowych przedmiotów

| Przedmiot | id_klienta | waga (oz) | źródło |
|---|---|---|---|
| gold coin | 3031 | **0,1** | [POTW] dane |
| platinum coin | 3035 | 0,1 | [POTW] dane |
| ham | 3582 | **20,0** | [POTW] dane, zgodne z pomiarem delty cap 20,05 |
| meat | 3577 | **13,0** | [POTW] dane |
| cheese | 3607 | 4,0 | [POTW] dane |
| bread | 3600 | 5,0 | [POTW] dane |
| spike sword | 3271 | **50,0** (atk 24, def 21; kupno 8000 gp u Nah'boba w Drefii) | [POTW] dane |
| steel shield | 3409 | **69,0** (def 21; kupno 240, sprzedaż 80) | [POTW] dane |
| ultimate healing rune (UH) | 3160 | **1,2** (kupno 175) | [POTW] dane |
| blank rune | 3147 | **1,2** (kupno/sprzedaż 10) | [POTW] dane |
| rope | 3003 | brak w danych; z pamięci Tibii ok. 18 oz [HIP] | **BRAK w `przedmioty.json`** |
| shovel | 3457 | brak w danych; z pamięci Tibii ok. 40 oz [HIP] | **BRAK** |
| backpack | 2854 | brak w danych; z pamięci Tibii ok. 18 oz pusty [HIP] | **BRAK** (id z `testy/*`, kontenery) |
| bag | 2853 | brak w danych; ok. 8 oz [HIP] | **BRAK** |

Dane o rope/shovel/backpack/bag leżą w `objects.srv` CipSoft (źródło 1 w README), ale build kategorii ich nie wziął (11 kategorii: bez narzędzi i kontenerów). Do dopisania przy następnym budowaniu danych (trywialne: rozszerzyć filtr).

**100 gold coin = 100 x 0,1 oz = 10 oz** [POTW]. 1000 gp = 100 oz, 100 platinum coin (=10 000 gp) też 10 oz. Dla porównania: 1 ham = 20 oz = 200 gold coin; jedna UH = 12 monet.

### 3.3 Przedmioty o niskiej wadze i dobrych statystykach dla druida lvl 13 z mieczem [POTW dane, ocena moja]

Druid nie ma ograniczenia sprzętowego w 7.4. Cap to wąskie gardło (cap 14 oz wolne teraz, spike sword + steel shield + brass armor już ważą 199 oz), więc liczy się def/atk na uncję.

Miecze (skill sword; wolne dane = nie kupuje NPC, tylko drop):
- **fire sword** 35/20, 23 oz (lekki, ale rzadki; światło), **djinn blade** 38/22, 24,5 oz, **bright sword** 36/30, 29 oz (rzadkie), **scimitar** 19/13, 29 oz, **katana** 16/12, 31 oz, **sabre** 12/10, 25 oz (35 gp), **machete** 12/9, 16,5 oz (Thais, 40 gp) jako lekki zapas, **rapier** 10/8, 15 oz (15 gp).
- Kupowane: **sword** 14/12, 35 oz (85 gp), **longsword** 17/14, 42 oz (160 gp, Ab'Dendriel i Greenshore), **carlin sword** 15/13, 40 oz (473 gp), **spike sword** 24/21, 50 oz (8000 gp) = to, co mamy.
- Uwaga [HIP]: miecze 2-ręczne (two handed sword 30/25, 70 oz, magic longsword) wykluczają tarczę.

Tarcze (def na oz): **demon shield** 35, 26 oz (rzadkie), **phoenix shield** 34, 35 oz, **vampire shield** 34, 38 oz (rzadkie); kupowane: **wooden shield** 14, 40 oz (15 gp), studded 15, 58 oz (50 gp), brass 16, 60 oz (65 gp), plate 17, 65 oz (125 gp), **steel shield 21, 69 oz (240 gp)** = obecna, dwarven 26, 55 oz (500 gp).

Zbroje: **blue robe** arm 11, 22 oz (bardzo dobra dla druida, drop), magic plate armor 22/85 (6400 gp), brass armor 8/80 (obecna), studded armor 5/71, leather armor 4/60, **doublet** 2/25, **jacket** 1/24.

Nogi: **elven legs** 4, 33 oz (drop), brass legs 5, 38 oz (195 gp), chain legs 3/35, plate legs 7/50 (obecne, nie kupowane przez NPC w danych), studded legs 2/26.

Hełmy: **winged helmet** 14, 12 oz (rzadki, SkillBoost), soldier helmet 5, 32 oz (110 gp), iron helmet 5, 30 oz (390 gp), brass helmet 3, 27 oz (120 gp), studded helmet 2, 24,5 oz (obecny, 63 gp).

Buty: leather boots 1/9 (obecne), patched boots 2/10 (rzadkie), steel boots 5/29.

Pierścienie/amulety lekkie (poniżej 1 oz): life ring 0,8, ring of healing 0,8, power/energy ring 0,8, might ring 1,0; amulet: elven amulet 2,7, strange talisman 2,9, garlic necklace 3,8, stone skin amulet 7,0 (5000 gp), protection amulet 5,5 (700 gp), dragon necklace 6,3.

Jedzenie (waga): brown mushroom 0,2 oz (10 gp), cheese 4 oz (6 gp), bread 5 oz, fish 5,2 oz, meat 13 oz, ham 20 oz. Przy ciasnym capie opłaca się najlżejsze na jednostkę odżywiania; pole `odzywianie` jest w danych dla jedzenia (do policzenia oz na minutę regeneracji).

---

## 4. Rotwormy: spoty i droga

Dane ze `spoty.json` [POTW], odległości z mapy [HIP: model Dijkstry jw., bez walidacji na żywo].

| Spot | Środek (x,y,z) | Piętra | Rotwormów (spawny) | Inne | Od znacznika miasta (linia prosta) | Dojście lądem w mapie | min lvl (dane) |
|---|---|---|---|---|---|---|---|
| **T3 Thais SE** (wasp i rotworm) | 32462,32287,9 | 9-11 | 7 | 8 wasp, 8 troll, 3 skeleton | 117 | TAK przez znane schody troll cave (z7 `(32492,32259)` -> z8 -> z9); koszt modelu 296 (ok. 150-250 kroków, 4 przejścia pięter) | 10 |
| **V1 Venore rotworm cave** | 33053,32099,9 | 8-10 | **35**, 2 slime | slime 150 hp, 110 dmg | 100 | TAK w modelu, koszt 558 ze świątyni Venore (32957,32076,7), 10 przejść pięter, w tym podejrzane skoki przez z6 | 10 |
| **D1 Darashia** | 33183,32445,9 | 7-11 | **34**, 2 scarab | scarab 320 hp, poison spider, rat | 44 | TAK, koszt 296 z `(33213,32454,1)` (Darashia leży na z1), 8 przejść w dół, wszystkie "w dół" (spójne) | 10 |
| **K2 Kazordoon** (troll/rotworm/dwarf) | 32614,31977,15 | 7-15 | 20 | dwarf soldier 26, guard 5, troll 28, dwarf 12, minotaur guard/mage | 63 | TAK, koszt 196 z `(32649,31925,11)`, 4 przejścia, ale wysokie piętra z dwarf guard (140 dmg) | 12 |
| E1 Edron orc cave | 33158,31903,9 | 7-9 | 4 | orki | 91 | nie liczono | 13 |
| Carlin (C1-C4) | | | **0** w danych | ghoule, szkielety, skorpiony | | nie dotyczy | |

Rekomendacja pod druida lvl 13 z mieczem (HP 210, mana 185): rotworm = 65 hp, 40 exp, ok. 18 skill, atak max ok. 40 (szac. górna granica). **Spot D1 Darashia jest najbliżej (44 kratek), ma 34 rotwormy i dojście tylko w dół (spójne) a V1 Venore daje najgęstszy skupisko (35 w jednym obszarze)**, ale zalecane `min_lvl` 10 i `exp_h_szac` 5084-8936 (D1) vs 6456-11359 (V1) to model, nie pomiar. T3 jest najbliższy naszemu obecnemu miejscu (ta sama jaskinia co trolle), ale ma tylko 7 rotwormów w 4 gatunkach, więc to raczej nowy fragment dla patrolu niż spot na rotworma.

Bez łodzi: dojście lądem w mapie z miasta bazowego do spotu istnieje w modelu dla każdego spotu osobno (z własnego miasta: D1 z Darashii, V1 z Venore, K2 z Kazordoonu, T3 z Thais). **Połączenia między miastami nie badałem** (każde Dijkstra startowało z własnego miasta). Z wiedzy o Tibii [HIP]: Venore i Thais łączy ląd, a Darashia (pustynia Darama) w 7.4 wymaga statku od Thais/Carlin/Venore. Dla "z Thais bez łodzi" realnie wchodzi więc T3 (i ewentualnie V1 po spacerze do Venore), nie D1.

---

## 5. Propozycja API "swiat" (JSON przez gniazdo)

Cel: jedno zapytanie, jeden spójny snapshot (bez składania z 6 wywołań), przyjazny dla modelu (małe, czytelne, bez adresów pamięci), i lista dostępnych akcji z warunkami.

### 5.1 Zapytanie

```json
{"cmd":"swiat","promien":7,"nazwa":"Jointoramix","wiadomosci_od":8986,"epoka":"1a13456bd8a",
 "kontenery":true,"mapa":true}
```

### 5.2 Odpowiedź (szkic)

```json
{
 "ok": true,
 "t": 1791921720.4,
 "wiek": {"gracz_s":0.0,"stwory_s":0.25,"kontenery_s":0.0,"czat_s":0.1},
 "ja": {
  "nazwa":"Jointoramix","x":32481,"y":32291,"z":8,"kierunek":"S",
  "hp":210,"max_hp":210,"mana":115,"max_mana":185,
  "cap_wolne_oz":14.0,"level":13,"exp":26524,"do_nastepnego_proc":49,
  "cel_ataku":{"id":1073741840,"nazwa":"Troll","x":32482,"y":32292,"hp":60},
  "bije_mnie":[1073741841],
  "statusy":null
 },
 "otoczenie": {
  "promien":7,
  "pola":["#######.......#","...",
  "legenda":{"#":"ściana/woda","_":"przechodnie",">":"schody/dziura w dół","<":"wyjście w górę (wnioskowane)","D":"drzwi (ściana w mapie)","?":"niewidziane","@":"ja","T":"stwór"},
  "przejscia":[{"x":32484,"y":32265,"z":8,"typ":"w_dol","laduje":[32484,32265,9],"odl":26,"zrodlo":"mapa+nagranie"}]
 },
 "stwory":[
  {"id":1073741840,"nazwa":"Troll","x":32482,"y":32292,"z":8,"dx":1,"dy":1,"odl":1,"hp_proc":60,
   "gracz":false,"atakowany":true,"bije_mnie":false,"kierunek":"W","w_zasiegu_melee":true}
 ],
 "ekwipunek":{"glowa":{"id":3376,"nazwa":"studded helmet","waga":24.5},"prawa_reka":{"id":3409,"nazwa":"steel shield","waga":69.0}},
 "kontenery":[
  {"numer":0,"nazwa":"backpack","pojemnosc":20,"zajete":16,"waga_oz":123.4,
   "przedmioty":[{"slot":0,"id":3031,"nazwa":"gold coin","ilosc":74,"waga_szt":0.1,"waga":7.4}]}
 ],
 "czat":{"znacznik":8990,"epoka":"1a13456bd8a","nowe":[{"nr":8987,"kanal":"Default","nadawca":"","tekst":"Loot of a troll: 12 gold coins","systemowa":true}]},
 "akcje":[
  {"typ":"idz_do","parametry":{"x":"int","y":"int","z":"int"},"limit":"to samo piętro, A* po mapie, najwyżej N pól","dostepna":true},
  {"typ":"krok","parametry":{"kierunek":"N|E|S|W|NE|NW|SE|SW"},"dostepna":true},
  {"typ":"atakuj","parametry":{"id":"int"},"dostepna":true,"warunek":"stwór widoczny na ekranie"},
  {"typ":"przestan_atakowac","dostepna":true},
  {"typ":"uzyj_na","parametry":{"przedmiot_id":"int","cel":"pole|stwor|ja"},"dostepna":true,"uwaga":"rope/shovel/UH/jedzenie"},
  {"typ":"zjedz","parametry":{"przedmiot_id":"opcjonalnie"},"dostepna":true},
  {"typ":"zbierz_loot","parametry":{"x":"int","y":"int","z":"int"},"dostepna":true},
  {"typ":"zmien_pietro","parametry":{"przejscie_id":"string"},"dostepna":true},
  {"typ":"powiedz","parametry":{"tekst":"str","kanal":"Default"},"dostepna":true,"limit":"1/30 s"},
  {"typ":"uciekaj","dostepna":true},
  {"typ":"czekaj","parametry":{"sekundy":"float"},"dostepna":true}
 ],
 "odruchy_skryptu":["uciekanie przy niskim HP","zjadanie","UH/leczenie","obrona przed stworem obok"]
}
```

Uzasadnienie wybranych pól:
- `cel_ataku`, `bije_mnie`: już czytamy z ramek [POTW].
- `ja.kierunek`, `stwory.kierunek`: u32 w obiekcie [POTW], opis jako tekst po sprawdzeniu semantyki.
- `statusy`: **wymaga nowego odczytu** (m_states z LocalPlayer). Do czasu odczytu zwracać `null` (model ma wiedzieć, że "brak danych", a nie "brak trucizny").
- `kontenery.waga`: z `przedmioty.json` po `id`; **dla nieznanych id (rope, shovel, backpack, bag) uzupełnić dane**. Waga całego plecaka bez podwójnego liczenia zagnieżdżonych kontenerów.
- `otoczenie.pola`: okno `promien` x `promien` z `Mapa.flagi`, z naniesionymi stworami; `przejscia` z `miejsca_troll.json` (graf) i z flagi 2.
- `akcje`: realne wejścia już istnieją w kodzie [POTW]: `Cavebot.idz_do`, `Postac.krok`, atak klikiem w `cavebot._atak_domyslny`, `zjedz`, `zbierz_loot`, `pietra`/`wypad` (rope, shovel, schody), `runa_klik`, `napisz_na_czacie` w mozg.py. Dziś model w `mozg.py` ma tylko 11 akcji (pauza, wznow, zmien_trase, czat, idz_do, sprobuj_loot, alarm_gm itp.), nie ma "atakuj" ani "zjedz" ani "uzyj_na".

### 5.3 Opóźnienia (zmierzone teraz, tylko odczyt gniazda, bot działa równolegle)

8 prób na komendę co 0,25 s, klient w Pythonie, wartości w ms:

| cmd | min | mediana | max | rozmiar odpowiedzi |
|---|---|---|---|---|
| `gracz` | 2,1 | **2,6** | 528 | 169 B |
| `cel_ataku` | 0,9 | **1,2** | 601 | 24 B |
| `kontenery` (ekwipunek) | 1,3 | **1,5** | 2,9 | 276 B |
| `kontenery` | 2,4 | **2,6** | 360 | 1,2 KB |
| `stwory` | 1,2 | **38** | 602 | 0,8 KB |
| `wiadomosci` (limit 3) | 60 | **98** | 2348 | 1 KB |

Interpretacja [POTW]: typowo **1-3 ms** na czysty odczyt z cache, **~40 ms** gdy `stwory` czeka na świeży skan (wiek wyniku <= 0,5 s zgodnie z `WIEK_STWORY`), **~100 ms** dla czatu (odświeżenie listy buforów). Skoki 350-600 ms i jeden 2,3 s wynikają z tego, że serwer gniazda jest jednowątkowy i konkuruje z pętlą bota (`mozg.py`/`cavebot`), pełnym skanem stworów (co 2 s bez stworów, co 20 s w walce) i skanem gracza przy utracie bloku (1-2 s). Wniosek: **snapshot "swiat" realnie do ~50 ms mediany i do ~0,6 s w ogonie** po zebraniu w jednym wywołaniu, a świeżość pozycji stwora ~0,25-0,5 s.

Istotniejsze od odczytu jest opóźnienie modelu: obecny `mozg.py` woła `claude -p --model haiku` (CLI, start procesu + generacja, rzędu sekund, limit 150 wywołań/h w kodzie). Sterowanie "klatka po klatce" modelem jest więc nierealne; realne jest **sterowanie na poziomie celów** (idź do X, atakuj Y, wróć po zapasy) z odruchami w skrypcie (ucieczka, UH, jedzenie), tak jak dziś, tylko z bogatszym snapshotem i szerszą listą akcji. Jeśli ma być model typu Jeff w "prawie czasie rzeczywistym", warto: (a) stały proces z kontekstem zamiast `claude -p` na każdy ruch, (b) pętla decyzji co 1-3 s z akcjami wielokrokowymi (A* i pościg wykonuje skrypt), (c) bezpiecznik: odruchy zawsze działają niezależnie od modelu.

---

## 6. Luki i kolejność prac (propozycja)

1. Endpoint `swiat` (jedno wywołanie, spójny snapshot, wagi, okno mapy tekstem). Mała robota, same dane, które już mamy.
2. Odczyt skilli i flag statusu (poison/paralyze/haste/PZ): `szukaj`/`zawez`/`sledz` przy kontrolowanej zmianie (np. jedzenie trucizny, świeca/światło). Największy zysk bezpieczeństwa.
3. Uzupełnić `przedmioty.json` o narzędzia i kontenery (rope, shovel, backpack, bag, torch, parcel, itd.) z `objects.srv`; poprawić `wyprawa.WAGI_DOMYSLNE` (ham 20,0, nie 13,6).
4. Graf łączników z kierunkiem dla pozostałych spotów (jak `miejsca_troll.json`): najpierw Thais orc cave i T3 (nagranie wejścia 1x), potem D1 Darashia/V1 Venore. Mapa podpowiada kandydatów (flaga 2), nagranie ustala kierunek.
5. Funkcja `okno(x,y,z,r)` w `mapa.py` zwracająca tekstową siatkę i listę przejść; `droga_wielopietrowa` (Dijkstra jak w tym audycie, ale z grafem z nagrań zamiast domysłów).
6. Test semantyki `kierunek` i `max_cap` (porównać z oknem Skills w kliencie).
7. Rozszerzyć akcje w `mozg.py` o `atakuj`, `uzyj_na`, `zjedz`, `krok` z walidacją po stronie Pythona (jak dziś `DOZWOLONE`/`DEFENSYWNE`).

## 7. Pewność i czego nie sprawdzałem

- Nie uruchamiałem i nie zatrzymywałem bota, nie wysyłałem klawiszy ani kliknięć; do gniazda poszło ok. 60 zapytań `gracz/stwory/kontenery/wiadomosci/cel_ataku` (tylko odczyt).
- Trasowanie wielopiętrowe w sekcjach 2.4 i 4 to mój model z mapy, nie funkcja repo; jedyną weryfikacją jest zgodność z nagranymi schodami trolli (8/8 flagi 2 na górnym piętrze).
- Wagi rope/shovel/backpack/bag z pamięci Tibii, nie z danych.
- `max_cap`, `kierunek`, prędkość pola: semantyka niepotwierdzona.
