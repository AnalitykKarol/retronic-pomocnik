# Specyfikacja naprawy bota po dniu 13.10.2026

Status: specyfikacja, nic nie jest zaimplementowane. Źródła: `ANALIZA_gry_1013.md`, `AUDYT_odczyt_i_mapa.md`, `logi/mozg-20261013-*.log`, `logi/mozg-stdout-1013-*.log`, `logi/telemetria-20261013.jsonl` (czytana skryptem, strumieniowo), kod w stanie z 13.10 ok. 22:15 (cavebot.py zmieniony o 22:15 przez agenta P3, numery linii mogą się przesunąć o kilka). Mapa: `mapa/map74.otmm` przez `mapa.Mapa` (tylko odczyt).

Oznaczenia: **FAKT** = potwierdzone w kodzie albo policzone z logów/telemetrii; **HIPOTEZA** = wniosek bez bezpośredniego pomiaru; **BRAK POMIARU** = czego nie da się ustalić z odczytu i jak to zmierzyć.

## 0. Najważniejsze ustalenia (zmieniają obraz z analizy dnia)

1. **Liczba 944 "odpuszczeń za ścianą" i skuteczność dobijania 35% to w dużej części artefakt.** FAKT: 938 linii "Odpuszczam ...: za ścianą" w logach mozg to ok. **72 epizody** (ta sama nazwa i HP celu w oknie 15 s). Bot w pętli wybiera i odpuszcza tego samego trolla kilka razy w tej samej sekundzie (np. 07:52:20: trzy pary "Odpuszczam" / "Nowy cel: Troll (32496,32300) HP 28%"). Przyczyna: `ignorowany()` zdejmuje ignorowanie, gdy potwór jest w odległości <= `IGNOROWANIE_BLISKO` (3), a 846 z 938 odpuszczeń jest przy "prosto 2" albo "prosto 3". Liczone po unikalnym `id` trolla (telemetria `epizod_celu` z id, bez wpisów testowych): **553 z 577 trolli zabite (96%)**; 570 epizodów bez id to głównie te pętle.
2. **Telemetria jest zanieczyszczana przez testy.** FAKT: testy tworzą `Cavebot` z atrapą `klik`, co włącza `_hak_telemetrii()` i zapis do prawdziwego `logi/telemetria-RRRRMMDD.jsonl`. Wszystkie wpisy "Rat" (1708 `nowy_cel`, 289 `zabicie`), wszystkie "Loot: 4 pola puste" (140) i próbki bez `exp` z `mana: 0` pochodzą z minut, w których szły testy (np. 22:01-22:14 dziś: `timeout 600 python3 testy/test_cavebot.py` w `ps` podczas tej analizy).
3. **Długie przerwy to w większości brak procesu bota, nie zawieszenie.** FAKT: z 10 466 s przerw ok. 7 956 s to dziury w próbkach (restarty pod wdrożenia, STOP 19:16-20:08, wyprawa do depo 11:13, gra ręczna 09:31-09:42). Postoje z działającym botem: 10 przypadków, 2 411 s, z czego 867 s to 10:00-10:14 (pętla ataku na widmie gracza, już częściowo naprawione w `bot.py`).
4. **Przypadek 22:06-22:08 ma konkretną przyczynę z mapy:** postać stała w zaułku (32496,32266,8), z którego jedyne wyjścia to schody (32496,32267) (zakazane) i skos (32497,32267), na którym stał troll id..4426. Droga "ze skosem 10 pól" prowadziła przez zajęte pole, więc żaden krok nie przechodził przez 40 s.
5. **Pola ognia: 5 006 linii dziennie, ale większość to te same, stałe pola** (np. (32480,32294,8) widziane 1 371 razy od 07:51 do 22:21), część na ścianach. To głównie szum; realny wpływ: 14 odłożonych zwłok.

---

## P1. Trolle "za ścianą" / za rogiem

### Objaw (liczby)
- 938 linii "Odpuszczam Troll: za ścianą (droga naokoło: brak drogi ...)" w logach mozg 13.10; wszystkie z "brak drogi", przy pełnej mapie. Rozkład "prosto": 2 pola 356, 3 pola 490, 4 pola 51, 5+ 41.
- Po scaleniu powtórzeń: ok. 72 epizody. Telemetria `epizod_celu` Troll (unikalne rekordy, bez minut testowych): porzucony 613, zabity 584, zgubiony 149; po unikalnym id: 553/577 zabitych.
- Przykład żywy 22:06:54-22:08:15 (`mozg-stdout-1013-2142.log` linie 1546-1600): zmiana celu z 4426 (HP 60%) na 5554, 5554 ucieka z 16%, bot w stanie POGON 22:07:16-22:07:49 stoi na (32496,32266) (wszystkie linie debug "Jointoramix 0,0"), co ok. 8 s "Skos awaryjny ... droga ze skosem 10 pól", potem "od 40 s gonię uciekającego bez skutku". Powrót do 4426: kliki 22:07:51 (pierwszy), 22:07:54 i 22:07:56 (`ramka_false`, "cel w grze id..5554"), HP 4426 spada dopiero 22:07:58.
- Telemetria w tym czasie: 4426 `osiagalny: true, droga: 0`.

### Przyczyna źródłowa
1. **Pętla wybierz-odpuść** (FAKT):
   - `cavebot.py: walcz(): ok. 4347-4357` przy braku drogi ustawia `ignorowane[id] = teraz + objazd_ignorowanie()`, a `nieosiagalne[id]` tylko gdy `droga > NIEOSIAGALNY_DROGA` i cel NIE jest umierający.
   - `cavebot.py: objazd_ignorowanie(): ok. 3444` daje umierającemu (`hp <= próg+10` albo `<= 30`) tylko `OBJAZD_DOBICIE = 7 s`.
   - `cavebot.py: ignorowany(): ok. 2659-2675`: zwykłe ignorowanie kończy się, gdy `d <= IGNOROWANIE_BLISKO` (3). Troll za ścianą 2-3 pola od nas jest więc od razu kandydatem, wybierany ponownie (często z premią za dobicie), odpuszczany, i tak w kółko w jednej sekundzie.
   - Ten sam mechanizm psuje inne ignorowania: `LIMIT_WALKI` (ok. 4233, log 10:05:52 "trwa za długo, ignoruję na 60 s" i w tej samej sekundzie "Nowy cel" ten sam id..7748) i `ATAK_LIMIT_KLIKOW` (ok. 4283-4303, ignorowanie 30 s zdejmowane od razu, gdy cel stoi obok).
2. **Zaułek i stwór na jedynym wyjściu** (FAKT dla 22:07; jak częste: patrz BRAK POMIARU):
   - Mapa wokół (32496,32266,8): sąsiedzi W, E, N to ściana, S (32496,32267) to schody (flaga 2, kolor żółty), SE (32497,32267) przechodnie. Jedyne wyjście bez zmiany piętra to skos SE, a tam stał troll 4426.
   - `cavebot.py: droga(): ok. 2164-2173`: gdy z blokadami (`zajete`, nauczone ściany) drogi nie ma albo jest objazdem, liczona jest `d2` po samej mapie BEZ stworów i jest brana. Komentarz mówi wprost "stwory ... nie mogą zamykać wąskiego korytarza". W zaułku d2 prowadzi przez pole z trollem.
   - `cavebot.py: podejdz(): ok. 2322-2334` (skos awaryjny) bierze tę drogę; `_krok_skos` nie sprawdza zajętości pola; `_skos_kandydat(): ok. 2604-2627` też nie sprawdza stworów (tylko ściany, ogień, schody, `skos_zle`).
   - `cavebot.py: tick(), gałąź POGON: ok. 2895-2911` (cel poza ekranem) nie ma reguły "blokujący obok": `_rozprawa_blok` i `blokujacy_na_drodze` działają tylko dla celu w widoku. Dodatkowo `_droga_do(): ok. 3243-3250` liczy drogę bez skosów, więc w zaułku "wolna droga" = None i blokującego nigdy nie wykryje.
   - Pościg kończy dopiero `POGON_TWARDY = 40 s` (pokrętło `POGON_LIMIT` = 30 w `na_zywo.json`).
3. **Telemetria "osiagalny/droga" kłamie w tę samą stronę** (FAKT): `telemetria.py: probka(): ok. 145-153` woła `cb.droga(...)`, więc dostaje tę samą drogę bez stworów (d2). Dla celu obok `droga([]) = 0`, `osiagalny: true` jest technicznie prawdą (cel stoi obok po skosie, atak wręcz po skosie działa), więc rekomendacja z analizy ("wybieraj tylko cele z `osiagalny`") nie rozwiązałaby 22:07.
4. **Kliki `ramka_false` na sąsiednim celu, gdy gra trzyma inny cel** (HIPOTEZA): w 22:07:51-56 gra trzymała 5554 (8 pól dalej, poza ekranem), dwa Alt+kliki na 4426 nie przełączyły celu, trzeci tak. Cały dzień: 258 klików `ramka_false`, w tym 157 z "cel w grze" = inny id, 101 z "cel w grze id?". Nie da się z odczytu ustalić, czy klik trafia w złe pole, czy klient odrzuca przełączenie. **BRAK POMIARU**: zrzut ekranu i ostatnie 3 linie czatu/statusu ("Sorry, not possible.", "You may not attack...") przy 2. kolejnym `ramka_false`.

Uwaga do "mapa a rzeczywistość": klasyfikacja 198 odpuszczeń, dla których w ostatniej próbce był cel z pozycją, A* po samej mapie (bez ognia i nauczonych ścian): 169 miało krótką drogę prostą po mapie (czyli drogę zamknęły stwory, ogień albo nauczone ściany w chwili decyzji), 20 tylko ze skosem, 6 inny obszar (np. wschodnia kieszeń x >= 32506 za ścianą x = 32505, dostępna tylko przez łącznik), 1 zamknięta przez stwory. **BRAK POMIARU**: telemetria nie zapisuje, co dokładnie blokowało (ogień, ściana nauczona, stwór) w chwili odpuszczenia. Log ma to częściowo (`[pola: ...]`: 3 220 "wolne", 468 "ściana (mapa)", 47 "stwór", 3 "ściana (nauczona)"), ale opisuje tylko sąsiadów w stronę celu.

### Proponowana zmiana
**P1a. Twarde ignorowanie z wygaśnięciem po czasie albo po pojawieniu się drogi** (`cavebot.py`):
- Nowy słownik `self.ignor_powod = {id: ("sciana"|"limit_walki"|"atak_klik"|"pogon", od_t)}` ustawiany razem z `ignorowane[id]` w czterech miejscach: odpuszczenie za ścianą (walcz ok. 4352 i POGON ok. 2907), `LIMIT_WALKI` (ok. 4235), `ATAK_LIMIT_KLIKOW` (ok. 4300).
- `ignorowany()`: dla powodów `limit_walki` i `atak_klik` ignorowanie trwa do końca czasu bez względu na odległość (wyjątek: cel nas bije, `bije_nas` True i HP gracza spada w `GRYZIE_OKNO`). Dla `sciana`: zdejmujemy wcześniej tylko, gdy (a) potwór stoi obok (d <= 1) albo (b) `droga()` do niego istnieje i nie jest objazdem; sprawdzenie drogi najwyżej co `IGNOR_DROGA_CO_S = 1.0 s` na id (cache jak `astar_cache` w telemetrii).
- `objazd_ignorowanie()`: umierający za ścianą: `OBJAZD_DOBICIE` 7 s zostaje, ale wygasa tylko wg punktu (b) albo czasu (koniec pętli w tej samej sekundzie).
- Log "Odpuszczam ... za ścianą" najwyżej raz na `ODPUSZCZ_LOG_S = 5 s` na id; telemetria `odpuszczenie` dostaje `id` (dziś go nie ma) i `blok` (patrz P1d).
- Nowe stałe i pokrętła (`pokretla.ZAKRESY`): `IGNOR_TWARDE = 1` (0/1, wyłącznik całej zmiany), `IGNOR_DROGA_CO_S = 1.0` (0.5-3.0), `ODPUSZCZ_LOG_S = 5.0` (1-30).

**P1b. Blokujący na jedynym wyjściu** (`cavebot.py: droga()`, `podejdz()`, gałąź POGON):
- `droga()`: gdy wybierana jest `d2` (droga bez stworów), sprawdź, czy któreś z pierwszych `BLOK_KROKI = 2` pól d2 leży w `zajete`. Jeśli tak, zapisz `self.ostatni_blokujacy = (pole, id_stwora)` i NIE zwracaj d2 jako drogi do marszu (zwróć `None` z `ostatni_objazd = "blokada stworem (x,y)"`), chyba że alternatywna droga z blokadami istnieje i jest <= `2*prosto + MAPA_OBJAZD`.
- `_skos_kandydat()` i skos awaryjny w `podejdz()`: pole skosu zajęte przez żywego stwora (z `ostatnie_stwory`, to samo piętro) = brak skosu.
- Gałąź POGON (ok. 2895-2911) i `walcz()` przy `wynik is None`: jeśli `ostatni_blokujacy` wskazuje potwora z `kand` w odległości <= 1, zamiast odpuszczać: log "Wyjście zablokowane przez X (x,y), bije blokującego", `self.rozprawa = {"id": blokujący, "wroc": cel["id"], "do": teraz + ROZPRAWA_BLOK_MAX}` (istniejący mechanizm z `_rozprawa_blok`), cel = blokujący.
- `blokujacy_na_drodze()` / `_droga_do()`: liczyć `wolna` ze skosami, gdy `POSCIG_SKOS_AWARYJNY` (wtedy zaułek ze skosem jako jedynym wyjściem jest rozpoznany).
- Nowe stałe: `BLOK_KROKI = 2` (1-4), `BLOK_WYJSCIE = 1` (0/1, wyłącznik).

**P1c. Cel gry różny od celu bota** (`cavebot.py: walcz()`):
- Gdy bot zmienia cel (każde "Nowy cel"/"Zmiana celu") i poprzedni cel jest dalej niż 1 pole albo poza ekranem, a `_cel_w_grze()` zwraca poprzedni id: najpierw `Escape` (zdjęcie celu w kliencie), potem klik w nowy cel. Dziś `ATAK_INNY_CEL = False` (ok. 74), a ta ścieżka klika bez Escape.
- Nowa stała `ATAK_ESCAPE_PRZY_ZMIANIE = 1` (0/1). Ryzyko i pomiar: patrz niżej (P1 ryzyka, P2 pomiar `ramka_false`).

**P1d. Telemetria przyczyny** (`telemetria.py` + `cavebot.py`):
- `odpuszczenie`: dodać `id`, `poz_bota`, `poz_celu`, `blok` = lista (pole, powód) z `_powod_braku_drogi` w formie strukturalnej (nie tylko tekst), oraz `droga_mapa` = długość A* po samej mapie (bez stworów, ognia, nauczonych ścian).
- Próbka: `osiagalny`/`droga` liczyć dwoma wariantami: `droga_z_blokadami` (bez fallbacku d2) i `droga_mapa`. Wymaga parametru `droga(..., bez_fallbacku=True)`.

### Ryzyka i ograniczenie
- Twarde ignorowanie może pominąć trolla, który podszedł i jest osiągalny. Ograniczenie: zdejmowanie przy d <= 1 i przy istnieniu drogi (punkt b); wyjątek "bije nas".
- Bicie blokującego zamiast dobijania uciekającego: tylko gdy blokujący stoi na jednym z pierwszych 2 pól jedynej drogi; rozprawa ma limit `ROZPRAWA_BLOK_MAX = 15 s` i powrót do `wroc`.
- Escape przy zmianie celu zdejmuje też atak, który by się udał: robić tylko, gdy `_cel_w_grze()` wskazuje inny id niż nowy cel.
- Każda zmiana ma wyłącznik w `na_zywo.json` (`IGNOR_TWARDE`, `BLOK_WYJSCIE`, `ATAK_ESCAPE_PRZY_ZMIANIE`).

### Testy akceptacyjne
- `testy/test_ignor_twarde.py` (nowy): (1) troll za ścianą 2 pola, HP 20%: po odpuszczeniu w kolejnych 50 tickach z atrapą zegara nie ma ponownego "Nowy cel" tego id, dopóki atrapa mapy nie otworzy drogi; po otwarciu: wybrany w <= 2 tickach. (2) `LIMIT_WALKI` na celu obok: ignorowany przez `IGNOROWANIE` s mimo d = 1. (3) `ATAK_LIMIT_KLIKOW` obok: ignorowany 30 s. (4) wyjątek "bije nas": zdejmuje ignorowanie.
- `testy/test_zaulek.py` (nowy): odtworzenie 22:07 na prawdziwym wycinku mapy (`mapa.Mapa`, pole (32496,32266,8)), stwór na (32497,32267), uciekający cel poza ekranem (32502,32274): oczekiwane "bije blokującego" w <= 1 s, zero kroków w zajęte pole, brak "Skos awaryjny ... 10 pól".
- Rozszerzyć `testy/test_atak_inny_cel.py`: zmiana celu przy celu gry = stary id, poza ekranem: sekwencja Escape, klik.
- Pomiar w telemetrii po wdrożeniu (pierwsze 2 h): liczba linii "Odpuszczam za ścianą" / liczba unikalnych id odpuszczonych <= 1,5 (dziś ok. 13); `epizod_celu` bez `id` < 10% (dziś ok. 40%); skuteczność po id >= 95%; brak serii "Skos awaryjny" z tej samej pozycji dłuższych niż 10 s.

### Kolejność i zależności
P1a najpierw (mała zmiana, usuwa pętlę i szum w danych). P1d razem z P4 (ten sam plik). P1b po P1a (P1b korzysta z rozprawy i z twardego ignorowania). P1c ostatnie, po pomiarze `ramka_false` z P2.

---

## P2. Zawieszenia i długie przerwy

### Objaw (liczby)
- Przerwy >= 120 s bez zmiany pozycji i exp: łącznie ok. 10 466 s. Rozbicie (telemetria, tylko próbki z `exp`):
  - Postoje z działającym botem: 10, razem 2 411 s. Największy 10:00:00-10:14:27 (867 s, IDZ/WALKA, (32488,32294,8)). Pozostałe: 07:47 (130 s), 08:58 (142 s, zaplanowana "Przerwa na 141 s"), 14:28 (128 s), 14:37 (174 s, WYPAD), 16:00 (242 s, zaplanowana "Przerwa na 239 s" + UH), 17:06 i 17:11 (restart i pętla `ramka_false`), 17:50 (123 s, z7 miasto), 21:18 (160 s, IDZ bez ruchu, watchdog odpala co 60 s bez skutku).
  - Dziury w próbkach >= 120 s (proces nie pisał): ok. 7 956 s, w tym STOP 19:16-20:08 (3 122 s), wyprawa do depo 11:13 (1 257 s), awaria grim 09:29-09:42 (805 s, w tym gra ręczna Karola: "buy 5 ham", "buy 6 blank rune"), restarty pod wdrożenia (17:00 348 s, 21:38 217 s, 15:03, 17:24, 17:30 i inne).
- Pętla ataku 10:04:25-10:11:04: 142 kliki `ramka_false` na Troll id..7748, potem 29 kolejnych 10:11:41-10:12:59. Cały dzień: 4 serie >= 5 klików (498 s).
- `TimeoutExpired` grim: 09:29:34-09:31:04 (5 x png 10 s, 2 x ppm 5 s), proces zakończył się "Za dużo błędów z rzędu"; 09:43:05-09:43:15 UH przerwany wyjątkiem grim.

### Przyczyna źródłowa
1. **10:00-10:14: widmo własnej postaci** (FAKT): `mozg-stdout-1013-0942.log` ma 353 z 1 139 linii debug z dwoma wpisami "Jointoramix" (np. 10:04:20 "Jointoramix 0,0; Troll 0,0; Jointoramix 1,0"), troll "0,0" stoi na polu, które bot uważa za swoje. Pozycja bota była nieaktualna, kliki szły w złe pole. Poprawka już jest: `bot.py: wybierz_wlasny()/wlasny_wpis()/_pozycja_wlasna(): ok. 54-131` (plik zmieniony 10:14, nie ma jej w commicie z 10:01). Po 10:15 w logach stdout nie ma już podwójnych wpisów. Stan zastany, nie dublować.
2. **Brak strażnika postępu przy celu** (FAKT): `cavebot.py: _watchdog_bezczynnosci(): ok. 3202-3227` nie działa, gdy `self.cel is not None` albo żywy potwór jest w promieniu 8, czyli dokładnie w pętli ataku. `LIMIT_WALKI = 90 s` odpala, ale jego ignorowanie zdejmuje `IGNOROWANIE_BLISKO` (P1, przyczyna 1): po 10:05:52 ten sam id..7748 jest od razu nowym celem. `ATAK_LIMIT_KLIKOW = 5` (dodany ok. 17:00, 2 odpalenia o 17:10:25 i 17:11:05) ma ten sam problem.
3. **21:18 IDZ bez ruchu 160 s** (HIPOTEZA): stdout nie ma linii debug między 21:18:29 i 21:20:40, a mozg log ma "Watchdog: bezczynność 60 s ... idę dalej trasą" o 21:19:31 i 21:20:31. Watchdog odpalał, ale ruch nie następował. **BRAK POMIARU**: nie wiadomo, czy pętla stała na blokującym wywołaniu (np. model, zrzut), czy `idz_do` klikał w pole, którego klient nie przyjmował. Potrzebny log czasu ticku > 3 s z nazwą fazy (dziś jest tylko "wolny tick" > 5 s) i log wyniku `idz_do` przy watchdogu.
4. **grim bez ponowienia** (FAKT): `ekran.py: zrzut(): ok. 37-43` `timeout=10`, bez ponowienia; `ogien.py: zrzut_ppm(): ok. 84-90` `timeout=5`; wyjątek leci do `uh.py` (`geometria()` ok. 849, `weryfikuj_*` ok. 874-885: UH kończy się "przerwane", porażka 1/3) albo do pętli `mozg.py: ok. 2313-2331`. W obecnym kodzie mozg traktuje grim jako "okno niewidoczne" i czeka bez limitu ("bot stoi"). Przebieg 08:15-09:31 policzył grim jako błędy i się zakończył: HIPOTEZA, że proces działał na starszej wersji mozg.py (gałąź grim jest w commicie z 10:01). **BRAK POMIARU**: przyczyna zawieszenia grim (okno gry na innym workspace? obciążenie kompozytora?). Mierzyć: czas każdego grim, kod wyjścia, i czy okno gry jest widoczne (hyprctl, tylko odczyt) przy timeoucie.

### Proponowana zmiana
**P2a. Strażnik celu** (`cavebot.py: walcz()`, nowa metoda `_straznik_celu(cel, odl, teraz)`, woływana na początku `walcz()`):
- Postęp celu = spadek HP celu albo przyrost exp gracza albo zmiana odległości do celu o >= 1.
- Próg 1: `STRAZNIK_CEL_S1 = 12 s` bez postępu przy `odl <= 1`: jeden `Escape`, krótka pauza 0,3-0,6 s, wymuszone odświeżenie pozycji własnej (`bot._wlasny["t"] = -inf`), jeden klik ataku. Log "[STRAZNIK] cel X bez postępu 12 s: Escape i ponowny klik".
- Próg 2: `STRAZNIK_CEL_S2 = 25 s`: porównaj pozycję z `postac.pozycja()` z wpisem gracza w `stwory`; różnica > 0 albo stwór na naszym polu = "pozycja niespójna", log i telemetria `straznik_celu` z oboma pozycjami. Ignoruj cel twardo (P1a, powód `straznik`) na `STRAZNIK_IGNOR_S = 45 s`.
- Próg 3: trzy odpalenia progu 2 w 5 min: zdarzenie do modelu `utkniecie_walki` i powiadomienie (`powiadom`), bez zatrzymywania bota.
- Pokrętła: `STRAZNIK_CEL = 1` (0/1), `STRAZNIK_CEL_S1` (8-20), `STRAZNIK_CEL_S2` (15-40), `STRAZNIK_IGNOR_S` (20-120).

**P2b. Strażnik postępu globalny** (`cavebot.py: tick()`, nowa metoda `_straznik_postepu(g, poz, teraz)`):
- Postęp = zmiana pozycji, przyrost exp, spadek HP celu albo zebrany loot. Wyłączony w stanach PRZERWA, PAUZA, UH, WYPAD w mieście, JEDZENIE oraz gdy plik STOP.
- `STRAZNIK_POSTEP_S1 = 90 s`: reset stanu walki (cel = None, Escape, wyczyszczenie `zwloki_czekajace`, `klik_cel`, `skos_zle`), log, telemetria `straznik_postepu` z fazą ostatniego ticku.
- `STRAZNIK_POSTEP_S2 = 180 s`: w patrolu zmiana celu patrolu (jak przy "wizyta nieudana"), na trasie skok do najbliższego osiągalnego punktu trasy (`ustaw_najblizszy`).
- `STRAZNIK_POSTEP_S3 = 300 s`: zdarzenie do modelu i powiadomienie krytyczne.
- Pokrętła: `STRAZNIK_POSTEP = 1`, progi S1 (60-180), S2 (120-300), S3 (240-600).

**P2c. Zrzut ekranu z timeoutem i ponowieniem** (`ekran.py`, `ogien.py`, `uh.py`, `mozg.py`):
- Wspólna funkcja `ekran.grim(format, timeout, proby)`: `timeout` png 4 s, ppm 2 s, 2 próby z pauzą 0,3 s; po porażce `ZrzutNiedostepny(Exception)` z czasem trwania; licznik `ekran.GRIM_BLEDY` i znacznik czasu ostatniego sukcesu.
- `ogien`: przy `ZrzutNiedostepny` nie loguje co obieg; jedna linia na 60 s, ogień traktowany jak "nieznany" (stan sprzed awarii wygasa po `OGIEN_TRWA_S`).
- `uh.py`: wyjątek zrzutu w kroku przed rzutem kończy UH jako `brak_zrzutu` (bez liczenia porażki do limitu 3), w kroku po przełożeniu tarczy ma ścieżkę przywrócenia tarczy z pamięci `kontenery` bez zrzutu (weryfikacja tylko z pamięci). **BRAK POMIARU**: czy 09:43:15 tarcza wróciła do ręki; logi tego nie mówią.
- `mozg.py: ok. 2313-2331`: przy `ZrzutNiedostepny` bot nie stoi bez końca: walka i leczenie z pamięci działają dalej (atak i HP nie potrzebują zrzutu, ramka z pamięci), pomijane są tylko funkcje obrazowe (loot, ogień, UH); po `GRIM_STOP_S = 300 s` ciągłej awarii: pauza bota i powiadomienie.
- Pomiar: telemetria `grim` (czas, wynik, format) co każde wywołanie > 1 s.

**P2d. Pomiar `ramka_false`** (`cavebot.py: _log_klik_ataku()`): przy 2. kolejnym `ramka_false` na tym samym id: zrzut JPEG do `logi/zrzuty/` (jak `mozg.py: ok. 1141`), 3 ostatnie wiadomości czatu z kanału Default/Server Log, pozycja z `pozycja` i z `stwory`. Limit 1 zrzut na 60 s.

### Ryzyka i ograniczenie
- Strażnik zbyt czuły odpali w długiej walce z trollem, który się leczy: próg 1 robi tylko Escape i klik (koszt 1 klik), ignorowanie dopiero przy 25 s bez spadku HP.
- Escape zdejmuje cel w trakcie dobrego ataku: tylko gdy HP celu nie spadło w progu.
- Krótszy timeout grim może dać więcej fałszywych porażek przy obciążeniu: 2 próby, a UH bez zrzutu nie liczy porażki.
- Strażnik postępu nie może walczyć z zaplanowaną przerwą: wyłączony w PRZERWA/PAUZA (PRZERWA ma od 13.10 max 120 s, `PRZERWA_DLUGOSC_MIX` ok. 448).

### Testy akceptacyjne
- `testy/test_straznik_celu.py`: atrapa celu obok z HP stałym: Escape po 12 s (zegar atrapy), ignorowanie po 25 s, brak ponownego wyboru przez 45 s mimo d = 1; cel z HP spadającym co 5 s: strażnik nie odpala.
- `testy/test_straznik_postepu.py`: pozycja i exp stałe 90 s w IDZ: reset; 180 s: zmiana celu patrolu; w PRZERWA: brak odpaleń.
- `testy/test_grim.py`: atrapa `subprocess.run` rzucająca `TimeoutExpired` raz: druga próba udana; dwa razy: `ZrzutNiedostepny`; UH dostaje `brak_zrzutu` i nie zwiększa licznika porażek.
- Pomiar po wdrożeniu (doba): postoje >= 120 s z działającym botem i bez stanu PRZERWA/PAUZA: <= 2 (dziś 8 bez przerw zaplanowanych); serie `ramka_false` >= 5 na id: 0 dłuższych niż 30 s; zero zakończeń procesu przez grim.

### Kolejność i zależności
P2a wymaga P1a (twarde ignorowanie). P2c niezależne. P2b po P2a (żeby globalny nie dublował celu). P2d najwcześniej (sam pomiar, bez zmiany zachowania), bo od niego zależy P1c.

---

## P3. Przejścia pięter

### Stan zastany (agent Sonnet, nie dublować)
FAKT z plików: `pietra.py` (zmieniony 22:00:53): pole startowe ortogonalne do schodów (`_start()`, `_na_start()`, `START_RUCHY_MAX = 8`), pamięć pola, z którego przejście wyszło (`_zapamietaj_start()`, plik `trasy/pietra_start.json`, w testach wyłączony przez `RETRONIC_TESTY`), krok w osi przed próbą zamiast serii skosów (ok. 337-366), "Ctrl+klik bez skutku: następna próba z innego pola ortogonalnego" (ok. 446). `testy/test_wielopietrowa.py` zmieniony 22:09, `cavebot.py` zmieniony 22:15 (zakres zmian w cavebot nieznany z odczytu, brak migawki sprzed). Agent w chwili analizy uruchamiał `testy/test_cavebot.py` (to on pisze teraz wpisy "Rat" do telemetrii, patrz P4).

### Objaw (liczby, do weryfikacji poprawki)
Telemetria `pietra_start` -> `pietra_krok` (bez minut testowych), czas od startu próby do udanego kroku:

| Schody (pole) | kierunek | n | mediana s | p90 s | max s | porażki |
|---|---|---|---|---|---|---|
| (32482,32296) | 8->9 | 95 | 0,6 | 5,4 | 13,2 | 1 |
| (32482,32296) | 9->8 | 90 | 0,8 | 1,1 | 47,9 | 0 |
| (32494,32289) | 8->9 | 41 | 0,8 | 5,5 | 64,6 | 0 |
| (32484,32265) | 8->9 | 40 | 0,0 | 0,0 | 0,9 | **13** |
| (32478,32269) | 9->8 | 29 | 0,0 | 0,1 | 0,9 | **26** |
| (32476,32272) | 9->8 | 43 | 0,0 | 0,9 | 2,1 | 6 |

Suma czasu udanych prób: 563 s na 589 przejść; porażek 63. Czas samych prób jest mały; koszt to porażki (każda kończy wizytę patrolu, np. 22:05:13 "dojście 63 s ... przejście pięter nieudane") i ogony (47,9 s, 64,6 s).

### Uzupełnienie do specyfikacji agenta (nie zmienia jego zakresu)
- Najwięcej porażek nie ma (32482,32296), tylko (32478,32269) 9->8 (26) i (32484,32265) 8->9 (13). Po wdrożeniu poprawki sprawdzić te dwa pola osobno. **BRAK POMIARU**: dlaczego zawodzą (pole zajęte przez stwora? zła strona schodów w `miejsca_troll.json`?). Potrzebny w `pietra_blad` zapis: pole startowe, tryby prób, stwory na polach przy schodach.
- Telemetria `pietra_krok` dostaje `start` (pole, z którego wyszło) i `czas_dojscia_s` (od wejścia w stan przejścia, nie od pierwszej próby).

### Testy akceptacyjne (pomiar)
- Doba po wdrożeniu: p90 dla (32482,32296) w obu kierunkach <= 2 s, max <= 15 s; porażki (32478,32269) i (32484,32265) spadek o >= 50% albo wyjaśnienie z nowego pola `pietra_blad`.

---

## P4. Zafałszowana telemetria

### Objaw (liczby)
- 436 par próbek w odstępie < 0,9 s (proces bota pisze najwyżej 1/s), 388 skoków pozycji > 20 pól w XY, w godzinach 08 (104), 13 (56), 22 (164).
- 483 próbki bez `exp`, z `mana: 0`, `hp: 100`, w 19 minutach (08:38, 08:41-42, 09:26, 11:32-35, 12:54-55, 13:02, 13:10, 22:01-22:11). Pozycje typu (32493,32260,8), (32376,32202,7) przeplatane z prawdziwą pozycją.
- `nowy_cel Rat`: 1 708 wpisów w 41 minutach, po ok. 45-48 na minutę, pozycje (101,100) 610, (32015,32142) 351, (32017,32138) 207. Zero "Nowy cel: Rat" w logach mozg.
- `loot`: telemetria ok 1 267, logi mozg "Loot: ok" 360. Po odrzuceniu minut z wpisami Rat: ok 391 (zgodne z logami w granicach "Loot w walce"), a "4" (140) i 75 z 217 "zwłoki" leżą w minutach testów.

### Przyczyna źródłowa
1. **Testy piszą do produkcyjnego pliku** (FAKT):
   - `cavebot.py: __init__: ok. 830-832`: `self.zapis_znanych = self.klik is not None`; gdy prawda, `_hak_telemetrii()` (ok. 838-850) tworzy `telemetria.Telemetria()` z domyślnym `katalog=LOGI` (`instancja.S.logi` = `pomocnik/logi`) i `zapis=True`, oraz dopisuje `self.tele.linia` do globalnej listy `HAKI_LOGU`.
   - Testy z atrapą klika: `testy/test_wielopietrowa.py: ok. 101` (`klik=s.klik`), `testy/test_powrot_na_spot.py: ok. 55` (podmienia `b.tele = None` dopiero po konstrukcji, hak w `HAKI_LOGU` już jest), `testy/test_ogien.py: ok. 123`, `testy/test_cavebot.py: zrob_lab(klik=True)` ok. 437. Wyjątek: `test_patrol_troll.py: ok. 107` wyłącza haki.
   - Każda linia logu testu (np. "Nowy cel: Rat (101,100) HP 100%", "Loot: 4 pola puste ...") przechodzi przez `HAKI_LOGU` do `Telemetria.linia()` i jest zapisywana z prawdziwym `time.time()`.
   - Serie ok. 45-48 "Rat" na minutę pasują do jednego przebiegu zestawu testów; 22:01-22:14 w `ps` był `python3 testy/test_cavebot.py` (agent P3).
2. **Regex łupu** (FAKT): `telemetria.py: ok. 28` `RE_LOOT = r"^Loot: (\w+)"` łapie "Loot: 4 pola puste" (`cavebot.py: ok. 5018`), "Loot: zwłoki ... bez okna" (ok. 3114) i "Loot: stoję na zwłokach" (ok. 5011). Prawdziwy wynik to tylko `log(f"Loot: {wynik}")` (ok. 5027) ze statusem z `loot.py: ok. 1492` (`daleko`, `brak_okna`, `okno_niewidoczne`, `brak_plecaka`, `pelny_plecak`, `ok`, plus `przerwany`).
3. **Brak identyfikacji źródła rekordu** (FAKT): rekord nie ma `pid` ani id sesji, plik otwierany w trybie "a" przez każdy proces, bez blokady.
4. Mieszanie z widmem gracza (przyczyna 1 z P2) dotyczyło próbek 09:42-10:15 (pozycja bota zła, ale z jednego procesu). Po poprawce w `bot.py` nie występuje.
5. "Stary bufor" i "kilka procesów bota": nie znalazłem dowodów. Jeden `mozg.py` (pid 3931733) i jeden `klawisz_x11 --straznik`. Analityk/obserwator czytają telemetrię, nie piszą próbek.

### Proponowana zmiana
- `telemetria.py: Telemetria.__init__`: `zapis` domyślnie `None` = `os.environ.get("RETRONIC_TELEMETRIA") == "1" and not os.environ.get("RETRONIC_TESTY")`. Ustawić `RETRONIC_TELEMETRIA=1` w `uruchom.sh`, `uruchom_trolle.sh`, `sesja.sh` i w `mozg.main()` (gdy uruchomiony bez skryptu). Testy, `kup_test.py`, `zakupy_miasto.py` i inne skrypty nie piszą, chyba że jawnie.
- Blokada pisarza: przy pierwszym zapisie `fcntl.flock(LOCK_EX | LOCK_NB)` na `logi/telemetria.lock` trzymany przez życie procesu; gdy zajęty: `zapis=False` i jedna linia "telemetria: inny proces pisze (pid N), nie zapisuję".
- Każdy rekord: `pid`, `sesja` (czas startu procesu), `src` ("mozg"|"cavebot"|"test").
- `cavebot.py: _hak_telemetrii()`: nie dopisuje do `HAKI_LOGU`, gdy `RETRONIC_TESTY`; ponadto `HAKI_LOGU` zamienić na listę z kontrolą duplikatów (ten sam obiekt tylko raz).
- Testy: `testy/__init__` nie istnieje (testy to skrypty), więc na początku każdego testu, który buduje `Cavebot`, `os.environ["RETRONIC_TESTY"] = "1"` (część już to ma: `test_czar.py`, `test_jedzenie_mana.py`, `test_atak_inny_cel.py`, `test_analityk_poscigu.py`). Lepiej: wspólny `testy/_wspolne.py` importowany jako pierwszy.
- `RE_LOOT = re.compile(r"^Loot: (ok|brak_okna|okno_niewidoczne|daleko|brak_plecaka|pelny_plecak|przerwany)$")`. "Loot: zwłoki ... bez okna" jako osobne zdarzenie `loot_wstrzymany` (pole `zwloki`, `n`).
- Czyszczenie danych 13.10 (skrypt jednorazowy, nie w bocie): odrzucić rekordy z minut, w których są próbki bez `exp` albo `nowy_cel` "Rat"; wynik do `telemetria-20261013.czysta.jsonl` (oryginał zostaje).

### Ryzyka i ograniczenie
- Zapomniana zmienna środowiska w skrypcie startowym = brak telemetrii. Ograniczenie: `mozg.main()` ustawia ją sam; analityk/obserwator przy braku świeżych próbek > 120 s zgłasza "telemetria nie pisze".
- `flock` na NFS/tmpfs: katalog `logi` jest lokalny, ryzyko pomijalne.

### Testy akceptacyjne
- `testy/test_telemetria.py`: (1) `Telemetria()` przy `RETRONIC_TESTY=1` nie tworzy pliku w `tmp` katalogu; (2) dwa obiekty z `RETRONIC_TELEMETRIA=1` w tym samym katalogu: pisze tylko pierwszy; (3) `RE_LOOT` nie łapie "Loot: 4 pola puste", "Loot: zwłoki (1, 2) bez okna", "Loot: stoję na zwłokach"; łapie "Loot: ok" i "Loot: pelny_plecak".
- Test regresji: po przebiegu `python3 testy/test_cavebot.py` rozmiar `logi/telemetria-<dziś>.jsonl` się nie zmienia.
- Pomiar: doba po wdrożeniu: 0 próbek bez `exp`, 0 par próbek < 0,9 s, 0 `nowy_cel` spoza piętra/trasy, `loot.ok` w telemetrii = "Loot: ok" w logach (+-2%).

### Kolejność i zależności
Pierwsza w kolejce: bez niej żaden pomiar z P1, P2, P5 nie jest wiarygodny. Niezależna od innych zmian.

---

## P5. Loot: pełny plecak, cap, wagi, brak okna

### Objaw (liczby)
- `Loot: pelny_plecak` 1 raz (21:54:53 wg telemetrii, poza minutami testów), `brak_plecaka` 1 raz. "nie przeszedł" (przeciągnięcie bez zmiany pamięci): gold coin 9 + 3 w walce, meat 2.
- Cap na żywo (audyt): `cap 14, max_cap 14`. `wypad_start`: cap 95, 96, 82, 79, 85, 29, 29, 32, 104 oz.
- `WAGI_DOMYSLNE` w `wyprawa.py: ok. 54-57`: ham 13,6 (dane i pomiar: 20,0 / 20,05; `wyprawa_stan.json` ma nauczone 20,3), bread 3,0 (dane 5,0), cheese 5,0 (dane 4,0), dragon ham 15,0 (dane 30,0). meat 13,0, fish 5,2, blank 1,2 zgodne.
- `brak_okna`: 89 "Loot: brak_okna" + 56 "Loot w walce przerwany: brak_okna" = ok. 145 dziennie (logi mozg 149 linii z tym słowem).

### Przyczyna źródłowa
1. **"Pełny plecak" nie rozróżnia przyczyn** (FAKT): `loot.py: _cel_w_plecaku(): ok. 604-622` zwraca `(None, None)`, gdy `len(zajete) >= pojemnosc` (sloty pełne) albo gdy żaden z `min(widoczne, pojemnosc)` slotów nie jest wolny (wolny slot może być schowany pod suwakiem okna). Cap nie jest sprawdzany nigdzie w loot. Przeciągnięcie odrzucone przez serwer za ciężar daje "nie przeszedł" (ok. 1580-1590), bez rozróżnienia.
2. **`max_cap`** (FAKT anomalia, HIPOTEZA przyczyny): blok gracza zwraca `max_cap == cap`. Protokół 7.4 wysyła tylko wolny cap. `wyprawa.py: _cap(): ok. 398-408` dzieli przez 100, gdy `max_cap > 5000` (niezweryfikowane). HIPOTEZA (wiedza o Tibii 7.4, do potwierdzenia): pełny cap druida = 400 + 10 x (level - 8) = 450 oz na lvl 13.
3. **Wagi domyślne** (FAKT): wpisane ręcznie, niezgodne z `dane_tibia/przedmioty.json`.
4. **`brak_okna`** (HIPOTEZA): część to zwłoki, które zniknęły albo leżą pod innym przedmiotem, część to okno zwłok zasłonięte (np. 22:08:20-32: trzy Ctrl+kliki na trzech polach, wszystkie "pusto"). **BRAK POMIARU**: przy `brak_okna` nie zapisujemy liczby otwartych kontenerów przed i po kliku ani czasu od śmierci celu.

### Proponowana zmiana
- `loot.py`: nowa funkcja `klasyfikuj_brak_miejsca(plecak, ident, ilosc, cap)` zwracająca jeden z: `sloty_pelne` (`len(zajete) >= pojemnosc`), `slot_ukryty` (`len(zajete) < pojemnosc` i brak wolnego w `widoczne`), `za_ciezki` (`cap < waga(ident) * ilosc`, waga z `przedmioty.json` po `id_klienta`), `nieznany`. Status `pelny_plecak` zostaje (zgodność z mozg.py:444), ale z polem `powod` i zapisem w telemetrii: `zajete`, `pojemnosc`, `widoczne`, `cap`, `waga`, `ilosc`, `id`.
- Przy "nie przeszedł": ta sama klasyfikacja + odczyt czatu z ostatnich 2 s (wzorzec jak `wypad.py: ODP_BRAK_MIEJSCA`, ok. 73: "too heavy|carry|no room|not enough room|backpack is full"). Gdy `za_ciezki`: przedmiot dopisany do `pomin_ciezkie` na 300 s (nie próbujemy meat przy cap 14), gold dalej.
- `slot_ukryty`: przewinięcie okna plecaka (jeśli jest już funkcja suwaka; **BRAK POMIARU** czy klient pozwala, nie widzę jej w loot.py) albo zrzucenie w pierwszy widoczny slot kontenera wewnętrznego (bag). Na start: tylko klasyfikacja i log.
- Cap: wszędzie `cap` = wolne oz; `max_cap` z pamięci nie jest używany do decyzji. Opcjonalnie `cap_max_szac = 400 + 10 * (level - 8)` tylko do raportu, oznaczone jako szacunek.
- `wyprawa.py: WAGI_DOMYSLNE`: zamiast ręcznego słownika ładować z `dane_tibia/przedmioty.json` po nazwie (ham 20,0, dragon ham 30,0, meat 13,0, cheese 4,0, bread 5,0, fish 5,2, blank rune 1,2). Stały słownik zostaje tylko jako zapas, gdy pliku brak, z wartościami z danych. Torch nie ma w `przedmioty.json` (kategoria pominięta przy budowie danych, audyt 3.2): zostaje 5,0 jako niezweryfikowane. Nauczone wagi z `wyprawa_stan.json` mają pierwszeństwo jak dziś.
- `brak_okna`: dopisać do telemetrii `loot`: `kontenery_przed`, `kontenery_po`, `s_od_smierci`, `pola_sprawdzone`.

### Ryzyka i ograniczenie
- Błędna waga w danych = fałszywe `za_ciezki`: klasyfikacja tylko loguje i blokuje dany przedmiot na 300 s, gold nie jest blokowany (0,1 oz).
- `przedmioty.json` nie ma rope/shovel/backpack/bag: przedmiot bez wagi = `nieznany`, bez blokady.

### Testy akceptacyjne
- `testy/test_loot_zbierz.py` (rozszerzenie): plecak 20/20 -> `sloty_pelne`; 19/20 z wolnym slotem 19 przy `widoczne = 16` -> `slot_ukryty`; 10/20, cap 14, meat x1 -> `za_ciezki`; gold x5 przy cap 14 -> idzie.
- `testy/test_wyprawa.py`: `_waga("ham") == 20.0` bez nauczonej wagi; nauczona 20,3 ma pierwszeństwo.
- Pomiar: każde `pelny_plecak` i "nie przeszedł" w telemetrii ma `powod`; po dobie raport: ile `za_ciezki` vs `sloty_pelne` vs `slot_ukryty`.

### Kolejność
Po P4 (żeby liczniki były czyste). Niezależne od P1/P2.

---

## P6. Spam [OGIEN] i obchodzenie pól ognia

### Objaw (liczby)
- 5 006 linii "[OGIEN] pola" dziennie (ok. 350/h), 314 różnych pól.
- Najczęstsze pola widziane cały dzień od 07:51 do 22:21: (32480,32294,8) 1 371 razy, (32491,32289,8) 1 146, (32504,32281,9) 1 107, (32504,32280,9) 1 103, (32505,32280,9) 968, (32505,32281,9) 958, (32483,32299,9) 865, (32483,32298,9) 744, (32491,32298,9) 693.
- Flagi mapy tych pól: (32480,32294,8), (32491,32289,8), (32472,32289,8): flaga 3 (przechodnie, "OTClient nie prowadzi tędy drogi", kolor 121, czyli nie schody o kolorze 210); (32504..32505, 32280..32281, 9), (32483,32299,9), (32491,32298,9): flaga 7 (nieprzechodnie + bit 2, kolor 86).
- Skutki realne: "zwłoki leżą na polu ognia, odkładam loot" 14 razy; "ogień zamyka drogę od 30 s" 1 raz; "nie wykryję ognia: TimeoutExpired" 3 razy (patrz P2).

### Przyczyna źródłowa
1. **Stałe pola** (FAKT liczby, HIPOTEZA interpretacji): te same pola przez 14 h to nie fire field z runy (żyje ok. 1-2 min, HIPOTEZA wg Tibii 7.4). Na polach z flagą 7 nie da się stanąć, więc ogień tam nie ma znaczenia dla ruchu. Na polach z flagą 3 bit 2 oznacza, że minimapa OTClienta i tak omija te pola (`mapa.droga()` blokuje flagę 2 domyślnie, `mapa.py: ok. 117`), więc wykrycie ognia nic nie dodaje do decyzji ruchu. Albo to stałe pola ognia z mapy serwera, albo fałszywe trafienia detektora (`ogien.py: maska_ognia`) na pomarańczowej dekoracji. **BRAK POMIARU**: zrzut tych pól (jeden JPEG przy następnym wykryciu na (32504,32280,9)) rozstrzygnie.
2. **Log przy każdej zmianie zbioru** (FAKT): `cavebot.py: ok. 2065-2068` loguje, gdy zbiór aktualny różni się od zapisanego, co `OGIEN_LOG_S = 1 s`. Migotanie animacji (`OGIEN_BRAK_S = 1,5 s`) zmienia zbiór co chwilę.
3. **Koszt** (FAKT): zrzut ppm co `OGIEN_ODSWIEZ_S = 0,8 s` w każdym ticku (ok. 40 ms + ok. 20 ms analiza wg komentarza), to jest też kolejne miejsce zawieszenia grim.

### Wniosek
Głównie szum. Realny problem blokujący: 14 odłożonych zwłok (część na polach stałych, np. (32472,32289,8) 4 razy, (32480,32293,8), (32481,32294,8)) i potencjalne zamknięcie drogi przy prawdziwym ogniu (1 przypadek). Nie jest to główne źródło strat exp.

### Proponowana zmiana
- `cavebot.py` (odświeżanie ognia ok. 2029-2068): maska pól stałych. Pole, na którym ogień widziano >= `OGIEN_STALY_N = 20` razy w ciągu >= `OGIEN_STALY_S = 600 s`, albo pole z flagą mapy 4 (ściana), trafia do `ogien_stale` (zapis w `znane_pola.json` albo osobnym `ogien_stale.json`). Pola stałe: nie logowane, nie liczone do `_ogien_blok` (ściana i flaga 2 są już blokowane przez mapę), ale zwłoki na nich nadal są odkładane (bezpieczeństwo).
- Log: jedna linia na zmianę zbioru pól NIESTAŁYCH, najwyżej co `OGIEN_LOG_S = 10 s`, plus podsumowanie co 10 min "ogień: N stałych, M zmiennych".
- Odświeżanie: `OGIEN_ODSWIEZ_S` 0,8 s tylko w IDZ/LOOT i gdy zmienne pola są w widoku; w WALKA bez zmiennych pól 3 s.
- Pokrętła: `OGIEN_STALY = 1` (0/1), `OGIEN_LOG_S` (1-60), `OGIEN_ODSWIEZ_WALKA_S` (0,8-5).

### Ryzyka i ograniczenie
- Prawdziwy ogień na polu uznanym za stałe (np. troll stoi w ogniu): maska nie wyłącza odkładania lootu ani schodzenia z ognia, gdy stoimy na nim (`cavebot.py: ok. 2091-2133`), wyłącza tylko log i blok drogi.

### Testy akceptacyjne
- `testy/test_ogien.py`: 25 wykryć tego samego pola w 11 min (atrapa zegara) -> pole stałe, brak linii "[OGIEN] pola" przy kolejnych; pole na ścianie z mapy -> stałe od razu; nowe pole obok -> log.
- Pomiar: "[OGIEN] pola" <= 30 linii/h (dziś ok. 350), "zwłoki na polu ognia" bez zmian albo mniej, czas ticku WALKA (mediana) spada.

---

## P7. Powrót z depo do troll cave (dojście `depo_troll_cave`, `--dojscie`)

### Objaw (liczby)
FAKT, logi `mozg-stdout-1013-*.log`: 8 startów dojścia w dniu, **2 udane** (15:24:13 -> 15:25:08, 17:52:08 -> 17:53:53), **6 nieudanych**:

| Start | Koniec | Co się stało |
|---|---|---|
| 11:34:48 | 11:38:03 | "Zatrzymano (plik STOP)" w trakcie dojścia (ręcznie albo przez wyprawę, log nie mówi) |
| 12:52:46 | 12:55:18 | stara wersja dojścia: "utknięcie, wracam na trasę do punktu 108", 3 porażki przejść pięter, zawracanie trasy ("trasa w drugą stronę"); dziś już nie występuje (CavebotDojscie nie zawraca) |
| 15:19:38 | 15:22:55 | dziura (32493,32259,7): "bez skutku po 7 próbach" (krok, Ctrl+klik, łopata, use_wlasne); potem próby 2/3 i 3/3 kończą się po 4-10 s komunikatem "trasa zawinęła się na punkt 0" |
| 17:24:19 | 17:24:42 | po 19 s dojścia start "wyprawa:blanki" (blanki 0, zapas 3, cap 29), przystanki depo_zloz/frodo/xodet; 4 s później STOP |
| 17:30:09 | 17:30:58 | to samo: po 21 s "Wypad: start (wyprawa:blanki)", potem STOP |
| 20:08:29 | 20:11:05 | unikanie gracza (63 s), "punkt 6 nieosiągalny mimo bliskości", STOP po 2,5 min |

Dodatkowo: 15:24:14-15:25:05 dojście stoi przy dziurze z trollem obok: "Trasa wstrzymana: Troll 1 pól", potem 5 x "droga zablokowana przez Troll, walczę 8 s" (40 s), dopiero gdy troll ucieka przy 30% HP dziura przechodzi. 17:24 i 17:30 w obu startach przed wyprawą 16-19 s "Unikanie: gracz Morphyo blokuje drogę ... czekam" i rotacja punktów 0 -> 5 -> 10 przy samym depo. 22:25:04 kolejna wyprawa "depo:blanki" ze spotu (TYLKO_DEPO=1, blanki 0, zapas 0, powód tylko "blanki"), 22:28:36 depo osiągnięte i STOP: następny start będzie znów z z7 i znów z blanki = 0.

### Przyczyna źródłowa
1. **Kolizja dojścia z wyprawą** (FAKT):
   - `CavebotDojscie` (`cavebot.py: ok. 6620-6675`) dziedziczy po `Cavebot`; z atrapą/żywym klikiem `__init__` woła `_hak_wypadu()` (ok. 830-834), więc wyprawa jest aktywna także w dojściu.
   - `wyprawa.py: _blokada_startu(): ok. 479-500` blokuje start przy `wypad_aktywny`, walce, locie, ale NIE przy `cb.dojscie_aktywne`.
   - `wyprawa.py: _okazja_wyprawa(): ok. 558-631`: powód `"blanki"` wchodzi, gdy `WYPRAWA_BLANKI > 0` i `blanki < WYPRAWA_BLANKI_PROG` (na_zywo: 15 i 1), bez warunku potwierdzonego głodu (ten dotyczy tylko "zapas"/"glod"). Po wyprawie zakończonej STOP-em w depo blanki dalej są 0, więc pierwszy obieg po restarcie (po `POTWIERDZ` odczytach, ok. 20 s) znów startuje wyprawę, i to z dojścia, w kierunku przeciwnym.
   - W trybie `WYPRAWA_TYLKO_DEPO = 1` (22:25) wyprawa "depo:blanki" nic nie kupuje (`_tryb_depo()`: "do depo nic nie kupujemy"), kończy się STOP-em w depo; blanki trzeba uzupełnić ręcznie. Bot nie ma pamięci "byłem w depo z powodu blanki, czekam na człowieka", więc pętla depo -> STOP -> restart -> dojście -> wyprawa jest wbudowana.
   - `wyprawa_stan.json` ma `nast_wall`, ale wyprawa zakończona w depo zapisuje `nast_wall: 0` (stan z 22:28 w pliku: `"nast_wall": 0`), więc nie ma okresu karencji po powrocie.
2. **Blokada trollem przy dziurze (32493,32259,7)** (FAKT przebieg, HIPOTEZA mechanizmu):
   - `cavebot.py: _wypad_bieg(): ok. 974-1008`: w dojściu bot nie walczy, dopóki nie stoi >= `WYPAD_BLOK_S` ze stworem obok; potem `WYPAD_WALKA_S = 8 s` walki i ponowna ocena. Troll przy dziurze nie umiera w 8 s (trollowi z 100% trzeba ok. 30-40 s), więc cykl "walczę 8 s" powtarza się, a między cyklami bot próbuje dziury i przerywa atak.
   - 15:19-15:22: 7 prób przejścia dziury bez skutku. HIPOTEZA: pole lądowania na z8 albo pole dziury zajęte przez stwora (troll stał przy dziurze na z7 o 15:24, (32492,32258,7)), albo dziura zasypana (łopata użyta, wynik nieznany). **BRAK POMIARU**: lista stworów na z7 i z8 w promieniu 2 od dziury w chwili każdej próby (dziś `pietra_blad` nie ma tych danych).
3. **Fałszywe "trasa zawinęła się" w ponowieniach** (FAKT objaw, HIPOTEZA mechanizmu): `mozg.py: przejdz_dojscie(): ok. 2418-2449` ponawia od `dojscie_od_pozycji()` (ok. 2405-2415), która przy dziurze zostawia 4 punkty (dziura + pierwsze pola z8). `CavebotDojscie.tick()` kończy, gdy `idx == 0` po `_dojscie_prev >= n - 5` (ok. 6669): przy trasie 4-punktowej warunek `n - 5 < 0` jest prawdziwy od pierwszego obiegu, a bazowy `Cavebot` po "Okrążenie 1 gotowe ... w drugą stronę" ustawia `idx` na 0. Wynik: próba trwa 4-10 s i nie próbuje dziury ponownie (15:22:41-45, 15:22:46-55). 15:25:05 ta sama ścieżka zadziałała przypadkiem, bo postać właśnie zeszła na z8 (15:25:08 "jestem przy końcu trasy").
4. **Unikanie graczy przy depo** (FAKT): `Unikanie: ... następny punkt rotacji: punkt 0 -> 5 -> 10` i "czekam w ruchu" w dojściu przy depo Thais (17:24, 17:30, 20:08: 63 s). Depo w mieście jest zawsze zatłoczone; unikanie w dojściu kosztuje 16-63 s i cofa indeks trasy.
5. **Start z z7** (FAKT): `uruchom_trolle.sh` dodaje `--dojscie depo_troll_cave` tylko, gdy osobne zapytanie gniazda zwraca `z == 7` (inline python, `timeout 3 s`, zapytanie `pozycja` bez obsługi widma z `bot.py`). Gdy odczyt zawiedzie (pusty `Z`), bot startuje główną trasę z z7 bez dojścia. Gdy postać stoi na z7 przy dziurze (nie przy depo), dojście startuje od najbliższego punktu (to działa). **BRAK POMIARU**: ile startów dnia poszło z pustym `Z` (skrypt nie loguje wartości).

### Proponowana zmiana
- **P7a. Wyprawa nie startuje w dojściu**: `wyprawa.py: _blokada_startu()` zwraca `"dojscie"`, gdy `getattr(cb, "dojscie_aktywne", False)`. Prostsze i pewniejsze: `CavebotDojscie.__init__` ustawia `self.wyprawa = None` po `super().__init__` (albo `_hak_wypadu` pomija wyprawę przy `dojscie_aktywne`). Do tego karencja po dojściu: pierwsza ocena wyprawy najwcześniej `WYPRAWA_PO_DOJSCIU_S = 300 s` po wejściu na główną trasę.
- **P7b. Blanki w trybie depo**: w `_okazja_wyprawa()` przy `_tryb_depo()` powód `"blanki"` tylko, gdy `WYPRAWA_DEPO_BLANKI = 1` (nowe pokrętło, domyślnie 0): do depo nie kupujemy blanków, więc sama ich brak nie jest powodem marszu. Zamiast wyprawy: jednorazowa notatka i powiadomienie "brak blanków, UH wyłączone do uzupełnienia" (UH i tak nie zrobi runy bez blanka).
- **P7c. Pamięć "depo z powodu X"**: po wyprawie zakończonej w depo zapis w `wyprawa_stan.json`: `depo_powody`, `depo_wall`, stan plecaka (blanki, jedzenie). Po restarcie: jeśli plecak nadal ma te same braki (blanki 0 i powód był "blanki"), wyprawa z tym powodem zablokowana do zmiany stanu plecaka; log "Wyprawa: brak blanków jak przy ostatnim depo, czekam na uzupełnienie". `nast_wall` po depo = teraz + `WYPRAWA_PO_DEPO_S = 900 s`.
- **P7d. Troll przy dziurze w dojściu**: w `_wypad_bieg()` dla `dojscie_aktywne`: jeśli stwór obok stoi na polu przejścia (dziura/schody z trasy) albo na sąsiednim polu, a następny punkt trasy to zmiana piętra, walka do skutku (nie 8 s), z limitem `DOJSCIE_WALKA_PRZEJSCIE_S = 60 s` i z normalną ucieczką/leczeniem. W pozostałych sytuacjach zostaje bieg.
- **P7e. Ponowienia dojścia bez fałszywego zawinięcia**: `CavebotDojscie`: wyłączyć "okrążenie w drugą stronę" (`okrazenia` i odwracanie w bazowym `Cavebot` nie mają sensu dla trasy jednokierunkowej: koniec trasy bez osiągnięcia celu = porażka próby, nie odwrócenie). Warunek zawinięcia: tylko gdy `n > 5` (ok. 6669). Przy porażce przejścia pięter w ponowieniu: pauza 3-6 s przed kolejną próbą (troll mógł zejść z pola) i `DOJSCIE_PROBY` 3 -> 5 (pokrętło w mozg, zakres 3-8).
- **P7f. Unikanie w dojściu**: przy `dojscie_aktywne` i postaci w promieniu `DOJSCIE_BEZ_UNIKANIA_POL = 25` od depo (pierwszy punkt `depo_troll_cave`) unikanie wyłączone (gracze w mieście nie są zagrożeniem dla druida w PZ okolicy depo). Bezpieczeństwo (gracz z czaszką, GM) zostaje.
- **P7g. Start z z7**: `uruchom_trolle.sh` loguje odczytane `Z` do pliku stdout; gdy `Z` pusty, ponawia odczyt 3 razy po 1 s; gdy nadal pusty, nie startuje (notify "nie znam piętra postaci"). Alternatywa trwalsza: decyzja o dojściu w `mozg.py` (po starcie `bot.Postac().pozycja()` z obsługą widma), a skrypt zawsze przekazuje `--dojscie depo_troll_cave` jako "jeśli z == 7".

### Ryzyka i ograniczenie
- Wyłączenie wyprawy w dojściu: przy prawdziwym głodzie w drodze z depo bot nie zawróci. Ograniczenie: dojście trwa ok. 2-3 min, a jedzenie w plecaku jest sprawdzane przed wyjściem z depo (przypadek głodu w dojściu nie wystąpił w logach dnia).
- P7b: bez wyprawy po blanki bot gra bez robienia UH. To świadoma zmiana: dziś i tak STOP w depo czeka na człowieka; powiadomienie mówi wprost, czego brakuje.
- P7d: dłuższa walka przy dziurze na z7 (powierzchnia, inni gracze): limit 60 s i normalny próg ucieczki.
- P7f: wyłączenie unikania przy depo może prowadzić bota przez tłum: tylko unikanie "omijam okolicę", nie reakcja na zagrożenie.

### Testy akceptacyjne
- `testy/test_dojscie.py` (nowy; dziś dojście testuje częściowo `testy/test_wyprawa.py`/`test_powrot_na_spot.py`): (1) `CavebotDojscie` z plecakiem bez blanków i `WYPRAWA_AKTYWNA=1`: przez całe dojście 0 zdarzeń `wypad_start`; (2) po zakończonym dojściu wyprawa nie startuje przez `WYPRAWA_PO_DOJSCIU_S`; (3) trasa 4-punktowa z nieudanym przejściem: próba nie kończy się "zawinęła się", kończy porażką przejścia, następna próba po pauzie; (4) troll obok dziury: walka trwa do zabicia albo 60 s, bez cyklu "walczę 8 s"; (5) unikanie przy depo wyłączone, przy graczu z czaszką działa.
- `testy/test_wyprawa.py`: tryb depo, blanki 0, zapas 5: brak wyprawy przy `WYPRAWA_DEPO_BLANKI=0`; po depo z powodem blanki i niezmienionym plecaku: brak ponownej wyprawy po restarcie (stan z pliku).
- Pomiar: przez 3 kolejne dni każdy start z z7 kończy się "Dojście zakończone" (cel 100%, dziś 2/8); czas dojścia mediana <= 180 s; 0 zdarzeń `wypad_start` w trakcie dojścia; 0 sekwencji depo -> STOP -> restart -> wyprawa z tym samym powodem.

### Kolejność i zależności
P7a, P7b i P7e najpierw (małe, usuwają 3 z 6 porażek dnia). P7c po P7b. P7d korzysta z twardego ignorowania tylko pośrednio (niezależne). P7f i P7g na końcu. Wszystkie w tym samym pakiecie co P4/P1a (jeden restart); P7 dotyczy tylko startu z z7, więc efekt widać dopiero przy następnym powrocie z depo.

---

## 7. Tabela priorytetów

Szacunki exp/h przyjmują ok. 1 000-1 500 exp/h w dobrej godzinie i 20 exp za trolla (analiza dnia). To szacunki rzędu wielkości, nie pomiary.

| Nr | Zmiana | Wpływ na exp/h | Koszt | Uzasadnienie |
|---|---|---|---|---|
| 1 | P4 telemetria (zapis tylko na żywo, blokada, `pid`, `RE_LOOT`) | pośredni, duży: bez tego nie zmierzymy reszty | mały (ok. 40 linii + skrypty startowe) | dziś ok. 40% epizodów i wszystkie "Rat" to szum |
| 2 | P1a twarde ignorowanie | średni: koniec pętli wybierz-odpuść (ok. 13 linii na epizod), mniej zmarnowanych ticków; naprawia też ignorowanie LIMIT_WALKI i ATAK_LIMIT | mały | 938 linii = 72 epizody |
| 3 | P2a strażnik celu | duży w złe dni: 10:00-10:14 to 867 s (ok. 250-350 exp) | średni | watchdog dziś nie działa przy celu |
| 4 | P2c grim z timeoutem i ponowieniem | średni: jedna awaria = 11-13 min (09:29-09:42) | mały | dziś bot staje albo kończy |
| 5 | P2d pomiar `ramka_false` | brak bezpośredniego, odblokowuje P1c | mały | przyczyna `ramka_false` nieustalona |
| 6 | P1b blokujący na jedynym wyjściu | mały do średniego: przypadek 22:07 to 60 s; serie skosu w miejscu rzadkie (1 >= 20 s w dobie) | średni | rzadkie, ale kosztowne |
| 7 | P2b strażnik postępu | średni: 21:18 (160 s), 17:50 (123 s) | średni | siatka bezpieczeństwa |
| 8 | P5 loot (klasyfikacja, wagi z danych) | mały: 1 `pelny_plecak`, 14 "nie przeszedł"; wagi wpływają na wyprawę (zakupy ham) | mały | poprawność wypraw |
| 9 | P6 ogień stały i log | mały na exp, duży na czytelność logów i CPU | mały | 5 006 linii szumu |
| 4b | P7a, P7b, P7e dojście bez wyprawy, bez blanków w trybie depo, bez fałszywego zawinięcia | duży przy każdym powrocie z depo: dziś 6 z 8 dojść nieudanych, każde = ręczny restart (minuty do dziesiątek minut przestoju) | mały | pętla depo -> STOP -> dojście -> wyprawa |
| 7b | P7c, P7d, P7f, P7g reszta dojścia | średni | średni | troll przy dziurze, unikanie przy depo, start z z7 |
| 10 | P1c Escape przy zmianie celu | nieznany do czasu pomiaru P2d | mały | czeka na dane |
| - | P3 | w toku (agent Sonnet) | - | weryfikacja wg tabeli P3 |

Uczciwie: realna strata z P1 jest mniejsza niż sugerowała analiza dnia (24 niezabite trolle z 577 po id, ok. 480 exp na dobę bez kosztu czasu), więc największy zysk exp/h dają P2a/P2c (postoje), a P4 i P1a są pierwsze, bo są tanie i naprawiają pomiar.

## 8. Plan wdrożenia przy jednym restarcie

Założenie: Karol robi jeden restart `mozg.py` (dziś restarty pod wdrożenia kosztowały kilka razy po 2-6 min). Wszystko przygotowane i przetestowane przed zatrzymaniem bota.

1. Przed restartem (bot gra dalej, testy z `RETRONIC_TESTY=1`, żeby nie brudzić telemetrii; do czasu wdrożenia P4 uruchamiać testy z `RETRONIC_TESTY=1` w środowisku):
   - Zaimplementować w kolejności: P4, P1a, P7a, P7b, P7e, P2d, P2c, P2a, P5 (wagi + klasyfikacja jako log), P6, P7c. P1b i P2b opcjonalnie w tym samym pakiecie, ale domyślnie WYŁĄCZONE pokrętłami (`BLOK_WYJSCIE = 0`, `STRAZNIK_POSTEP = 0`). P1c nie wchodzi (czeka na dane z P2d).
   - Wszystkie testy z `testy/` zielone, w tym nowe; sprawdzić, że rozmiar `logi/telemetria-<dziś>.jsonl` nie rośnie podczas testów.
   - `python3 -I -m py_compile` na zmienionych plikach.
   - Kopia: `git stash`/commit przed zmianą (repo ma `.git`, ostatni commit 13.10 10:01, 24 pliki zmienione od tego czasu): commit "przed naprawą 1013" ze stanem działającym, potem commit z naprawą.
   - Do `na_zywo.json` dopisać nowe klucze z wartościami domyślnymi (`IGNOR_TWARDE: 1`, `STRAZNIK_CEL: 1`, `BLOK_WYJSCIE: 0`, `STRAZNIK_POSTEP: 0`, `OGIEN_STALY: 1`), żeby było jasne, co jest włączone. Nowe klucze muszą być w `pokretla.ZAKRESY`, inaczej są odrzucane.
2. Restart: STOP, start skryptem z `RETRONIC_TELEMETRIA=1`. Sprawdzić w pierwszych 2 min: linia "telemetria: zapis" z pid, brak "inny proces pisze", próbki co ok. 1 s.
3. Po restarcie bez kolejnego restartu (hot-reload `na_zywo.json` co tick):
   - po 1 h: jeśli P1a/P2a zachowują się dobrze, włączyć `BLOK_WYJSCIE: 1`; po kolejnej godzinie `STRAZNIK_POSTEP: 1`.
   - `rdzen.py` ma hot-reload po zmianie pliku, ale żadna zmiana tej specyfikacji nie dotyka rdzenia.
4. Pomiar po 2 h i po dobie wg punktów "Testy akceptacyjne".

## 9. Plan wycofania

- Poziom 1, bez restartu: wyłączniki w `na_zywo.json`: `IGNOR_TWARDE: 0` (dawne ignorowanie), `STRAZNIK_CEL: 0`, `BLOK_WYJSCIE: 0`, `STRAZNIK_POSTEP: 0`, `OGIEN_STALY: 0`, `OGIEN_LOG_S: 1`. Działa w następnym ticku. Uwaga: auto-cofanie pokrętła przez analityka (`pokretla.py`, "Auto-cofnięcie ... po COFNIECIE_S") dotyczy tylko zmian analityka; nowe wyłączniki oznaczyć w `pokretla` jako "tylko Karol" (jak `TRASA_PIETRA` ok. 182).
- Poziom 2, z restartem: `git checkout <commit przed naprawą> -- <pliki>` i restart. Telemetria: gdy brak `RETRONIC_TELEMETRIA` po cofnięciu, stary kod pisze jak dawniej (zachowanie domyślne starej wersji).
- Kryteria wycofania (dowolne): dobijanie po id < 90% przez 2 h; więcej niż 3 postoje >= 120 s/h z działającym botem; "Odpuszczam za ścianą" na unikalne id > 5; jakikolwiek zgon postaci powiązany z Escape/ignorowaniem (sprawdzić w telemetrii stan i HP z 30 s przed).
- P5 wagi: cofnięcie = przywrócenie słownika; nauczone wagi w `wyprawa_stan.json` nie są ruszane.

## 10. Czego nie dało się ustalić (lista pomiarów do dodania)

1. Dlaczego klik ataku daje `ramka_false` (157 przypadków z innym celem w grze, 101 bez celu): zrzut + czat przy 2. kolejnym (P2d).
2. Co blokowało drogę w chwili odpuszczenia (ogień, nauczona ściana, stwór): pole `blok` w `odpuszczenie` (P1d).
3. Pętla 21:18 bez ruchu przy działającym watchdogu: czas faz ticku > 3 s i wynik `idz_do` po watchdogu.
4. Przyczyna zawieszeń grim: czas każdego zrzutu > 1 s, widoczność okna gry.
5. Czy tarcza wróciła do ręki po UH przerwanym wyjątkiem (09:43:15).
6. `max_cap`: porównać odczyt po podniesieniu i odłożeniu przedmiotu (czy `max_cap` zmienia się razem z `cap`) i z oknem Skills klienta.
7. Pola ognia stałe: jeden zrzut (32504,32280,9) i (32480,32294,8), żeby rozstrzygnąć stały ogień z mapy czy fałszywe trafienie detektora.
8. Porażki przejść (32478,32269) 9->8 i (32484,32265) 8->9: pole startowe, stwory przy schodach, tryby prób w `pietra_blad`.
9. Dojście: stwory na z7/z8 przy dziurze (32493,32259) przy każdej próbie przejścia; wartość `Z` odczytana przez `uruchom_trolle.sh` przy każdym starcie; kto zapisał STOP o 11:38:03 i 20:11:05 (Karol czy bot).
10. Zakres zmian agenta P3 w `cavebot.py` (plik zmieniony 22:15, bez migawki sprzed zmian): `git diff` po zakończeniu jego pracy.
