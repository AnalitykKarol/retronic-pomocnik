# Spoty expowe: Rookgaard i miasta (20.10)

Źródło: `serwer74/potwory_pelne.json` (monster.db CipSoft 7.4: punkty spawnu, ilość, respawn) + `potwory.json` (`atak_max_szac`).
Generator: `dane_tibia/spoty_poczatkowe.py` → pełna lista `dane_tibia/spoty_poczatkowe.json` (środek, obszar, skład, liczby).

Jak czytać:
- **sufit exp/h** = suma (ilość × exp × 3600 / respawn). Górna granica z respawnu, NIE pomiar. Realnie ogranicza szybkość zabijania,
  regeneracja i inni gracze („full ppl”). Służy do porównania spotów między sobą.
- **cios** = najgroźniejszy potwór spotu (`atak_max_szac`, zawyżony, więc ostrożny; brak → atak CipSoft × 3,5).
  Przedziały: 8–15 (cios ≤ 45), 15–30 (≤ 110). Groźniejsze pominięte.
- Odległość: linia prosta od standardowej świątyni 7.4 (do sprawdzenia w kliencie), bez pięter i ścieżki.
- Wejścia do jaskiń NIEZNANE z danych spawnów: trasa = generator z mapy klienta (jak `generuj_trasy_rook.py`).

## Rookgaard (lvl 1–8)
| spot (środek x,y,z) | skład | potw. | sufit | cios | trasa bota |
|---|---|---|---|---|---|
| 32036,32193,10 | rat 30, spider 16, bug 9, cave rat 8 | 71 | 4644 | 23 | brak |
| 31984,32221,8 | troll 15, snake 10, wolf 9 | 34 | 3372 | 17 | brak |
| 31991,32193,7 (powierzchnia) | snake 19, wolf 11, spider 8 | 38 | 3336 | 17 | brak |
| 32044,32195,9 | rat 43, cave rat 5, poison spider 3 | 56 | 2997 | 23 | brak |
| 32056,32203,8 | rat 62, bug 2, spider 2 | 66 | 2728 | 23 | `rook_raty_z8` (pod miastem) |
| 31985,32211,12 | orc 4, goblin 3, orc spearman 3, minotaur 2 | 13 | 2478 | 45 | brak (minotaur: od ~lvl 6) |
Kanały z11 (`rook_kanaly_z11`) i patrol: szczury, poza top 6 po sufit.

## Main, lvl 8–15 (najlepsze w miastach)
| miasto | spot | skład | potw. | sufit | odl. |
|---|---|---|---|---|---|
| Edron | 33239,31872,9 | rotworm 36 | 36 | 10368 | 62 |
| Venore | 33048,32105,9 | rotworm 37 | 37 | 9696 | 96 |
| Thais | 32323,32131,7 | wolf 8 | 8 | 5184 | 119 |
| Venore | 32935,32196,8 | swamp troll 32 | 32 | 4800 | 122 |
| Darashia | 33129,32426,8 | rotworm 15 | 15 | 4320 | 89 |
| Thais | 32352,32154,11 | rotworm 10 | 10 | 4160 | 89 |
| Kazordoon | 32712,32007,9 / 32643,31995,9 | rotworm 12 / troll 20 | 12 / 24 | 3578 / 3164 | 103 / 70 |
| Ab'Dendriel | 32648,31610,8 / 32624,31695,10 | elfy 9 / wasp 20 | 9 / 20 | 3462 / 3283 | 87 / 124 |
| Edron | 33105,31808,10 | goblin 19 (+ bug cave obok) | 21 | 3138 | 112 |
| Carlin | 32361,31766,8 | bug 21 | 21 | 2441 | 16 |

## Main, lvl 15–30
| miasto | spot | skład | potw. | sufit | cios |
|---|---|---|---|---|---|
| Ab'Dendriel | 32804,31586,6 | ghoul 17, skeleton 13 | 30 | 11400 | 70 |
| Ab'Dendriel | 32802,31587,7 | scorpion 18, skeleton 17, rotworm 7 | 42 | 10446 | 50 |
| Thais (Mintwallin) | 32415,32170,15 | minotaur 11, guard 6, archer 3 | 20 | 9037 | 100 |
| Edron (orc cave góra) | 33154,31913,8 | orc spearman 17, orc 15, poison spider 11 | 48 | 9078 | 60 |
| Kazordoon | 32608,31902,13 | dwarf soldier 11, dwarf 6, rotworm 5 | 22 | 7680 | 70 |
| Darashia | 33273,32541,13 | mummy 13, cobra 8, ghoul 8, stalker 7 | 49 | 20046 | 110 (raczej 25+) |
Darashia djinny (33147,32509,9) mają sufit 37200, ale blue djinn/fire elemental to cios ~110 i czary: od ~lvl 30.

## Wnioski
- Rook: najlepszy jest mieszany spot z10 (32036,32193): 71 potworów, sufit ~4600, szczury+pająki+bugi; bot musi mieć `--potwory Rat,Spider,Bug,Cave Rat`.
  Dla lvl 5–8 troll/snake/wolf z8 na zachodzie (31984,32221).
- Main 8–15: rotwormy w Edronie (36, 62 pola od świątyni; Edron ma już serwis i trasy bota) i w Venore (37).
- Main 15–30: Ab'Dendriel ghoule/skeletony/skorpiony (z6–7), krasnale Kazordoon (z13), Mintwallin.
Niezweryfikowane w grze: wejścia, świątynie, realny exp/h, tłok graczy.

## Dopisek 20.10 ~17:00: łatwe spoty na runy (Karol: „mega łatwo, mało osób, food i gold”)
Gold/kill i jedzenie/kill z lootu CipSoft (serwer74): rotworm 4,2 g + 0,4 jedz.; troll 3,0 g + 0,15 (meat); swamp troll 1,2 g + 0,6 (fish);
rat 1,4 g + 0,4 (cheese); wolf 0 g + 0,75 (meat x2); goblin 2,2 g + 0,2. Sufity na godzinę z respawnu (model):
| spot | skład | gold/h | jedz./h | najbliższe miasto |
|---|---|---|---|---|
| 32935,32196,8 | swamp troll 32 | 288 | 115 | Venore 122 pól |
| 33084,31755,8 + 33081,31732,9 | troll 19 + 16 | 376 + 317 | 17 + 14 | Edron 146–159 (trasy bota są; 15.10 „full ppl”) |
| 32657,31967,7 | troll 15, snake 11 | 341 | 15 | Kazordoon 43 |
| 33083,31837,9 | goblin 33 | 495 | 26 | Edron 136 |
| 32323,32131,7 | wolf 8 | 0 | 216 | Thais 119 |
| 33239,31872,9 / 33048,32105,9 (lvl 8+) | rotworm 36 / 37 | 1205 / 1127 | 104 / 97 | Edron 62 / Venore 95 |
Swamp trolle w okolicy 32686,32597 (25–28 szt.) to rejon Port Hope: w monster.db są, czy Retronic ma to miasto — NIEZNANE.
Tłok graczy niemierzony (do zmierzenia logiem obecności bota).

## Dopisek 20.10 ~17:10: niszowe, słabe respy blisko miast (Karol: „mało znane, nikomu się nie chce iść”)
Filtr: cios <= 25, 3–15 potworów w skupisku, <= 80 pól od świątyni, brak dużego spotu (>= 20 potw.) w promieniu 30 pól na tym/sąsiednim piętrze.
- **Ab'Dendriel, kieszenie trolli z9–z12** (9 małych kieszeni po 3–8 trolli, 24–76 pól od świątyni, resp 600 s): razem ~45 trolli, sufit ~900 gold/h.
  Pojedynczo nikt tam nie chodzi; jako jedna pętla przez kieszenie. Środki: 32681,31630,9 (8), 32683,31610,12 (7), 32693,31661,11 (6),
  32666,31613,9 (6), 32661,31606,10 (4), 32677,31590,10 (4), 32718,31654,11 (4), 32703,31633,10 (3), 32708,31604,10 (3).
- **Carlin, troll z9** 32397,31802,9: 13 trolli, resp 400 s (szybszy niż zwykle), 42 pola od świątyni, ~280 gold/h; obok 32394,31774,9 (4).
- **Thais, kanały z8**: 7 kieszeni szczurów po 3–5 (13–65 pól od świątyni, resp 200–300 s): ~30 szczurów, ser, ~600 gold/h razem, blisko depo/sklepu.
- Tylko jedzenie: Edron powierzchnia 33292,31810,7 (deer/rabbit, ~74 jedz./h), Kazordoon wilki 32579,31958,7 i 32646,31873,7.
Wejścia i tłok do sprawdzenia w grze.

## Dopisek 20.10 ~17:20: niszowe bez limitu odległości (Karol: „może być dalej, hunt i tak 2–3 h”)
Filtr: cios <= 25, 5–20 potw., brak dużego spotu w 45 polach, gold >= 120/h i jedzenie >= 8/h. Sprawdzone, że teren istnieje w `mapa/map74.otmm` (17x17 pól wokół środka).
| spot | skład | resp | gold/h | jedz./h | przechodnie pola | uwagi |
|---|---|---|---|---|---|---|
| 32574,32215,15 | rat 12 | **70 s** | ~1080 | ~250 | 22/289 | anomalia: szybki resp w małej komorze, 207 pól na wschód od Thais; dojście NIEZNANE (może quest) |
| 32604,31779,8 + 32600,31785,9 | goblin 13+11, wolf 4, pig 5 | 600 s | ~310 | ~80 | 272 / 247 | 150 pól na północ od Kazordoon, z dala od wszystkiego |
| 32397,31802,9 | troll 13 | 400 s | ~280 | ~13 | 148 | Carlin, 42 pola od świątyni |
| 32648,31630,9 | troll 13 | 500 s | ~280 | ~13 | 118 | Ab'Dendriel, 84 pola |
| 32473,32250,7 | troll 8, wolf 3 | 600 s | ~160 | ~16 | 275 | Thais, 104 pola na wschód, powierzchnia |
| 32106,31621,8 | troll 12 | 600 s | ~230 | ~10 | 69 | 300 pól na NW od Carlin, bardzo na uboczu |
Edron trolle (6 jaskiń 33080–33135, 31713–31755) mają razem najwięcej, ale bot już tam chodzi i 15.10 był tłok.

## Dopisek 20.10 ~17:35: Port Hope (Karol pyta o dane)
Środek miasta jak w trasie `mapy/port_hope_swamp_trolle.json` (32623,32772,7); trasa z mapy klienta = miasto jest w mapie Retronica. Spawny z monster.db (serwer74), 382 punkty w 320 polach.
| spot | skład | gold/h | jedz./h | od PH | uwagi |
|---|---|---|---|---|---|
| 32686,32597,8 | swamp troll 28 | ~250 | ~100 | 186 | koniec istniejącej trasy bota (186 pól z7) |
| 32693,32614,9 | swamp troll 25, skeleton 5, poison spider 4 | ~310 | ~90 | 173 | piętro niżej |
| 32678,32654,10 | swamp troll 18 | ~165 | ~65 | 130 | |
| 32661,32724,8 | cave rat 21, bug 9, spider 4 | ~250 | ~40 | 61 | najbliżej miasta |
Razem ~70 swamp trolli na z8–z10 = jedna pętla przez trzy piętra. Ryzyko po drodze: dżungla z7 (dworce, krokodyle, tygrysy w danych 7.6 jamera) — trasa omija? do sprawdzenia.
Niewiadome: czy Port Hope jest miastem respu na Retronicu, statek, tłok.

## Dopisek 20.10 ~17:55: trucizna (Karol: „wasp truje bardzo dużo”)
`cios` w tej analizie liczy tylko atak wręcz, BEZ trucizny. Trucizna CipSoft (pole `trucizna`, serwer74): wasp 25, poison spider 30, snake 20,
swamp troll 10, scorpion 350, cobra 100; bug/spider/cave rat/troll 0. Trucizna 7.4 zadaje malejące obrażenia co turę, łącznie wielokrotność wartości.
Bot nie leczy trucizny (brak antidote/exana pox w kodzie). `ph_raty_z8`: jaskinia bez trujących; przy dojściu wasp x3 / snake mogą zalecieć →
dopisane do `potwory` spotu (zabić od razu, wasp 35 HP).
