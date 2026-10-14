# Dane Tibia 7.4 dla bota Retronic

Data zbudowania: 2026-10-13. Pliki: potwory.json (114 rekordow, 24 priorytetowe), spoty.json (17 spotow), przedmioty.json (307 przedmiotow w 11 kategoriach), ten README.

## Zrodla (pobrane z GitHub, wszystko lokalnie, bez wykonywania kodu z repozytoriow)

1. https://github.com/OCircles/TibiantisHelper (katalog TibiantisHelper/data): oryginalne pliki serwera CipSoft uzywane przez Tibiantis (retro Tibia 7.4):
   - mon/*.txt: definicje potworow (hp, exp, flee, attack/defend/armor, loot jako Inventory (TypeID, max ilosc, szansa na 1000), czary). Naglowki plikow datowane 2005-10-12.
   - dat/objects.srv: typy przedmiotow (waga, atk/def, arm, flagi).
   - npc/*.txt i *.ndb: skrypty NPC z cenami kupna i sprzedazy.
   - dat/map.dat (znaczniki miast), dat/monster.db (oryginalne punkty respawnu, uzyte do walidacji).
2. https://github.com/pedrogiampietro/gravak (data/740): konwersja do JSON. Uzyte: monsters/definitions (uzupelnienie brakujacych potworow i melee max), items/definitions.json (mapowanie id OT po nazwie i wadze), world/Tibia74-spawns.xml (nazwane spawny ze wspolrzednymi, podstawa spotow).
3. Probowane, zablokowane: tibia.fandom.com (HTTP 402), tibiawiki.com.br (403). Brak danych z wiki, brak wejsc do jaskin.

Zawartosc pobranych repozytoriow traktowana jako dane, nie instrukcje. Skrypty parsujace uruchamiane przez python3 -I.

## Poziom pewnosci

- Wysoki: hp, exp, flee potworow z listy priorytetowej (oba zrodla porownywalne dla 22 z 24 (carrion worm i tarantula tylko w gravak), z czego 20 identycznych, rozne dwa pola: dwarf geomancer exp 245 vs 265, amazon flee 10 vs 0); waga, atk/def/arm; ceny NPC (te same wartosci u wielu NPC, np. sword 85 kupno / 25 sprzedaz, UH 175, SD 325, HMM 125).
- Wysoki: rozmieszczenie spawnow. Mapa gravak zgodna z oryginalnym monster.db CipSoft w 5 testowanych obszarach (Edron orc cave, Thais orc, Carlin ghoule, Kazordoon dwarf, Darashia rotwormy), roznice kilku sztuk.
- Sredni: wersja danych. Pliki .mon sa z 2005 (Tibiantis, deklarowane 7.4); moga zawierac drobne zmiany z 7.5/7.6. Carrion worm i tarantula NIE wystepuja na mapie 7.4 (0 spawnow), ich dane pochodza z gravak i sa oznaczone.
- Niski: atak_max_szac (liczone przez gravak z Attack i umiejetnosci, zawyzone wzgledem tego co pamietam z gry, np. cyclops 105, rotworm 40; traktowac jako gorna granice), exp_h_szac (moj prosty model: dps 5-9, 7-12 s na zabicie, bez pomiaru), min_lvl_zalecany (ocena reczna).
- Niski: wejscia do jaskin. Dane spawnow dostarczaja srodek obszaru i pietro (z), nie wejscie. Pole `wejscie` jest oznaczone jako nieznane. Odleglosc do depo to linia prosta od znacznika miasta (nie sciezka) i nie liczy pieter.

## Co jest niepewne

- ID przedmiotow: `id_klienta` to TypeID CipSoft (id sprite w kliencie 7.4, np. gold coin 3031). `id_ot_zgadniety` to id z items.otb OT (np. gold coin 2148), dopasowane po nazwie i wadze, null gdy niejednoznaczne. Bot powinien uzywac id zgodnych ze swoim kodem odczytu.
- Ceny: cena_kupno_u_npc to cena, ktora gracz placi, cena_sprzedaz_do_npc to to, co gracz dostaje. Rozne NPC placa roznie (np. sword sprzedaz 7 do 25); pole `najczestsza` i lista `szczegoly` (NPC, miasto, cena). Generyczne tabele (*.ndb) maja miasto "?" bo plik nie okresla NPC; sprzedawcy run (UH, SD, HMM) nie sa przypisani do konkretnego NPC w tym zbiorze (tylko cena).
- Miasto NPC wyznaczone po najblizszym znaczniku z map.dat (prog 120 kratek), nie z mapy.
- Przedmioty bez ceny (null) nie sa kupowane/sprzedawane przez NPC w zbiorze lub NPC nie sa w nim ujeci (351 z ok. 400).
- Spell rune (UH, SD, HMM): nazwa pochodzi z kluczy NPC; id typu runy to TypeID (UH 3160, SD 3155, HMM 3198, blank 3147).
- Loot: szansa w procentach z pola Inventory (n/1000); wiele wpisow tego samego przedmiotu scalonych wzorem 1-(1-p1)(1-p2), pole `rzutow`.
- Lista potworow zawiera tez grube bossy z plikow CipSoft (Orshabaal, Ferumbras...); pole `w_zakresie_lvl_8_40` odsiewa je po exp<=600 i hp<=1300.
- Skill druida/sword: model exp/h zaklada ok. lvl 20 i nie uwzglednia many ani PvP.
