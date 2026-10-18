# SPEC: mijanie graczy po ludzku — nie wchodzimy sobie w drogę (18.10.2026)

Status: **ZATWIERDZONA przez Karola 18.10** (odpowiedzi Q1–Q5 poniżej, „odpal”). Zakres F1+F2; F3 (wdrożenie, restart bota) tylko za osobną zgodą.
Branch: `feat/mijanie-graczy` (osobny worktree), baza `ruch-r1-1014`. Bez merge, bez pusha, bez restartu bota.
Zastępuje (za pokrętłem) zachowanie z `unikanie.py` opisane w `SPEC_unikanie_tor_gracza_1017.md`; stare zostaje jako wyłącznik.

## Problem (dowód: telemetria 15–18.10, skrypt analizy w scratchpadzie sesji 18.10)

84 spotkania z obcym graczem na spocie (bot w IDZ/WALKA/LOOT/PRZERWA), z 150 wszystkich (reszta: miasto, depo):

| Typ spotkania | Ile | Czas (med.) | Bot włączył unikanie | Zawroty/min (med.) |
|---|---|---|---|---|
| przechodzi (< 30 s w widoku) | 63 | 15 s | 50 | 0 (P75 2,1) |
| poluje obok | 15 | 44 s | 14 | 3,7 (max 16, Eliu 17.10 17:44) |
| stoi w miejscu | 6 | 41 s | 4 | 1,8 (P75 7,6) |

Tło: 4,15 zawrotu/min poza spotkaniami.

Co wygląda jak bot (nie czas reakcji; ten jest naturalny, poniżej 1 s — decyzja Karola 18.10):
1. **Reakcja na każdego, na sztywnym progu.** 111 ze 178 startów unikania na 8–9 polach (`UNIKANIE_PROMIEN=9`). Przechodzień zmienia plan w 50 z 63 przypadków.
2. **Bańka dystansu.** Punkt bliżej niż `UNIKANIE_PUNKT_D` (6) pomijany, droga nie bliżej niż `UNIKANIE_DROGA_MIN` (4); odległość w trakcie unikania 4–8 pól. Ludzie mijają się o 1 pole.
3. **Dreptanie.** W blokadzie „krok w tył, krok w przód, nigdy nie stoimy” (`_wiggle`). Człowiek staje z boku albo idzie zdecydowanie.
4. **Jedyny koniec to „gracz zniknął”** (175/175). Bot czeka, aż gracz zejdzie, i wraca na ten sam tor.

## Zasady (kultura gry według Karola, 18.10)

Z1. **Oceniam, w którą stronę on idzie, i nie idę w tę samą stronę.** Cel: jak najszybciej zniknąć mu z oczu (widok 15×11 pól, dx ±7, dy ±5), nie powielając jego strony.
Z2. **Kolejność wyboru kierunku:** (a) nie w jego stronę, (b) tam, gdzie nie był ani on, ani my, (c) gdy się nie da: mijamy się i idziemy tam, skąd on przyszedł.
Z3. **Walka ma pierwszeństwo.** Mam moby na sobie: biję je, on ma mnie minąć. Nie zabiera się mobów ludziom (w obie strony).
Z4. **Przechodzień:** ma przejście — biję dalej, nic nie zmieniam. Nie ma przejścia (zatykam korytarz) — udostępniam przejście (krok w bok, stoję, aż przejdzie).
Z5. **Mijanie jest normalne** w korytarzu i w otwartej komorze: idę dalej. Bez zawracania o 180° tylko dlatego, że ktoś idzie z naprzeciwka.
Z6. **Spotkanie ponownie = to samo jeszcze raz.** Spot jest duży, nie opuszczamy go z powodu zwykłego gracza.

## Zachowanie (F1, pokrętło `MIJANIE`)

**Wejście:** lista stworów (gracze z `gracz: true`), historia pozycji graczy (już liczona w `_tor_aktualizuj`), trasa pętli, mapa (A*), stan walki.

1. **Kierunek gracza** `h` jak dziś w `UNIKANIE_TOR` (okno 4 s, ruch >= 2 pola). Gracz stoi = brak kierunku (patrz Q1).
2. **Klasyfikacja w locie** (bez opóźnienia ponad tick):
   - *przechodzi / idzie inną stroną*: jego `h` nie prowadzi w naszą część pętli → **nic nie zmieniamy** (Z4, Z5).
   - *idzie w naszą stronę albo my w jego*: nasz kierunek pętli `v` i jego `h` zgodne (`v·h > 0`) i jest przed nami → zmiana (krok 3).
   - *zatykamy przejście*: gracz chce przejść przez pole/wąskie gardło, na którym stoimy (on stoi albo dreptał przy nas >= Q2 s, korytarz szerokości 1) → krok 4.
3. **Wybór kierunku (Z1, Z2)** — punkty kandydujące na pętli i poza nią (bliskie odnogi):
   - odrzucone: droga, której pierwsze `LOOK` pól idzie w kierunku `h` przed graczem (jego strona);
   - ocena reszty: (a) strona bez śladu gracza ani naszego (świeżość z mapy obecności / historii pozycji), (b) czas do wyjścia z jego widoku, (c) jego ślad (skąd przyszedł) dopiero na końcu;
   - mechanika pętli: najczęściej to **odwrócenie kierunku obiegu** pętli albo skrót do dalszej części pętli; nowy kierunek **trzymamy na stałe** (Q3): nie wracamy do starego kierunku po zniknięciu gracza, nie przeliczamy co sekundę na inny punkt; zmiana tylko przy kolejnym spotkaniu (Z6).
4. **Udostępnienie przejścia (Z4, Q2):** tylko gdy jednocześnie: (a) gracz faktycznie idzie w naszą stronę (`h` w naszą stronę), (b) nie ma przejścia (wąskie gardło, nie zmieści się obok), (c) widzimy go (w widoku, nie duch). Wtedy krok na najbliższe wolne pole poza osią jego ruchu (bok korytarza, wnęka), **stoimy**, obserwując go, aż przejdzie (bezpiecznik 15 s), potem dalej swoją drogą. Bez `_wiggle`.
5. **Walka (Z3):** gdy mamy cel albo moby nas biją — kroki 3–4 czekają do końca walki (loot wg Q4). Wyjątek: zagrożenie PK (obrona_pk) jak dziś.
6. **Moby (Q4):** nasze moby (te, które bijemy, i te, które biją nas) bijemy i lootujemy normalnie, także przy graczu. **Cudzy mob** = taki, którego on bije, który idzie na niego **albo jest w jego obrębie** (`UNIKANIE_MOB_PROMIEN`, dziś 4 pola), nawet jeśli go nie bije — nie bierzemy go na cel. Zostaje dzisiejsza reguła `pomin_moba` (mob obok nas przy graczu i nas nie bije = jego) i `CUDZY_MOB`. Promień do przetestowania na żywo.
7. **Bez bańki:** nie ma minimalnego dystansu do gracza na drodze; jedyne zakazane pole to jego pole (i pole, na które wchodzi, w wąskim gardle).
8. **Koniec:** gracz poza widokiem → normalna pętla w **aktualnym** (nowym) kierunku; nie wracamy na stary tor (Q3).

`MIJANIE=0`: zachowanie bajt w bajt jak dziś (`UNIKANIE_*`). `MIJANIE=1`: `unikanie.decyduj` i `_wiggle` nieużywane na spocie; `pomin_moba` według pkt 6 (bez zmian względem dziś).
**Gracz stoi (Q1):** omijamy jego komorę skrótem pętli; przez nią/obok niego tylko, gdy nie ma innej drogi.
**Odnogi (Q5):** w F1 tylko pętla i jej skróty, bez zejścia w boczne komory.
Poza zakresem tej zmiany (bez zmian): obrona PK, GM, `PATROL_GRACZ_ZMIEN`/`PATROL_GRACZ_PAM` (patrol po respach), czat_spot, powiadomienie „gracz na spocie”.

## Odpowiedzi Karola (18.10)

- Q1: tak. Q2: postój tylko, gdy faktycznie idzie w naszą stronę, nie ma przejścia i go obserwujemy. Q3: trzymamy nowy kierunek, nie wracamy, nie idziemy w jego stronę.
- Q4: zbieramy i expimy normalnie nasze moby; cudze (bije je albo są w jego obrębie, nawet niebite) nie — do testów. Q5: na razie tylko pętla i skróty.

## Pytania (zamknięte, treść dla historii)

- **Q1. Gracz stoi w miejscu na naszej pętli** (obozuje w komorze). Propozycja: omijamy jego komorę (pętla idzie dalej skrótem), nie przechodzimy przez nią, chyba że to jedyna droga — wtedy przechodzimy obok normalnie. OK?
- **Q2. Udostępnienie przejścia** — ile maks. stoimy z boku, zanim idziemy dalej? Propozycja: 5 s.
- **Q3. Trzymanie decyzji** — ile po zniknięciu gracza z widoku trzymamy nowy kierunek? Propozycja: do końca bieżącego okrążenia pętli (naturalne), min. 20 s.
- **Q4. Loot przy graczu** — po walce, gdy on jest obok: zbieramy normalnie (propozycja; to nasz mob) czy od razu odchodzimy?
- **Q5. Odnogi poza pętlą** — wolno zejść z pętli (np. boczna komora) dla Z1, czy tylko kierunek i skróty w obrębie pętli? Propozycja: tylko pętla i jej skróty w F1 (mniejsze ryzyko utknięcia).

## Fazy

- **F1** — logika w `unikanie.py` (nowa ścieżka za `MIJANIE`) + hak w `cavebot.py` (odwrócenie kierunku pętli, krok w bok i postój), pokrętła w `pokretla.py`, `na_zywo.przyklad.json`. Testy na atrapie.
- **F2** — test offline na nagranych spotkaniach (odtworzenie z telemetrii: Palandysz 18.10 13:31 i 14:03, Harley Queen 17.10 18:26, Eliu 17.10 17:44, przechodnie) — co zrobiłby nowy kod w tych chwilach.
- **F3** — wdrożenie po zgodzie Karola (restart bota), naturalna QA na spocie.

## Weryfikacja i miary „ludzkości”

Testy (atrapa `Swiat` z `test_unikanie.py`), nowy plik `testy/test_mijanie.py`:
- przechodzień z boku, ma przejście → zero zmian planu; przechodzień w korytarzu szer. 1 → krok w bok, postój, powrót na trasę;
- gracz idzie w tę samą stronę przed nami → odwrócenie obiegu, brak drogi w kierunku `h`;
- gracz z naprzeciwka w komorze → mijamy się, bez zawracania;
- w walce gracz podchodzi → dobijamy, kierunek zmienia się dopiero po walce;
- mob przy graczu tracący HP → pominięty; mob 3 pola od gracza, pełne HP → nasz;
- `MIJANIE=0` → istniejące `test_unikanie.py`, `test_unikanie_tor.py`, `test_patrol_gracz_zmiana.py` bez zmian, zielone.

Miary na żywo (porównanie z tabelą z „Problemu”, z telemetrii po wdrożeniu):
- przechodnie bez zmiany planu: cel >= 80% (dziś ok. 21%);
- zawroty/min w spotkaniach „poluje obok”: nie więcej niż tło (ok. 4/min; dziś mediana 3,7, max 16);
- brak sekwencji tył-przód (dreptania) przy graczu; postoje tylko przy udostępnianiu przejścia;
- czas w widoku gracza po decyzji (cel: krótszy niż dziś; miara nowa, do policzenia w F2).

## Ryzyka

- Kierunek z 4 s historii myli się na zakrętach — stąd ocena krótkiego odcinka drogi, nie promienia.
- Odwrócenie pętli: trasa `gobliny_edron_z8_petla` musi być przechodnia w obie strony (liny/drabiny tylko poza pętlą — sprawdzić w F1).
- „Kto bije moba” zgadujemy z pozycji i HP; pomyłka = KS albo pominięty nasz mob. Do potwierdzenia na żywo.
- Pętla bota: reakcja zależy od ticka cavebota; dziś telemetria 1/s, faktyczny tick do zmierzenia w F1.

## Wynik realizacji (18.10)

Zakres F1 + F2 wykonany w worktree `pomocnik-mijanie` (branch `feat/mijanie-graczy`, baza `1f18bc7`). **Bez commita, bez pusha, bez restartu bota, nic nie uruchomiono w grze.** F3 (wdrożenie) czeka na zgodę.

### Pliki

| Plik | Zmiana |
|---|---|
| `unikanie.py` | klasa `Mij` i ścieżka `Unikanie.mijanie()` (osobna od `decyduj`/`_wiggle`, które nie zostały ruszone); pamięć decyzji per gracz, skrót, odwrócenie obiegu, ustępowanie przejścia; `_tor_aktualizuj` liczy kierunek także przy `MIJANIE` (bez `UNIKANIE_TOR`) i dopisuje `g["obs_s"]`; `_start`/`_koniec` emitują `mijanie_start`/`mijanie_koniec` przy `MIJANIE=1` |
| `cavebot.py` | 13 stałych `MIJANIE*` (domyślnie `MIJANIE = 0`), `_mijanie_trasa` / `_mijanie_zastosuj` / `_mijanie_wolne`, hak w `_idz_trasa` (`if MIJANIE: ... else: _unikanie_trasa`), `_unikanie_krokami()` zwraca False przy `MIJANIE` |
| `pokretla.py` | zakresy 13 pokręteł, kierunek analityka (`MIJANIE`, `MIJANIE_POSTOJ_S`, `MIJANIE_PRZEJSCIE_ODL`, `MIJANIE_BOK_R`: tylko w dół) |
| `na_zywo.przyklad.json` | 13 wpisów z wartościami domyślnymi |
| `testy/test_mijanie.py` | nowy, 82 sprawdzenia (102 po przeglądzie) |
| `narzedzia/odtworz_mijanie.py` | F2: odtwarzanie spotkań z telemetrii (offline, tylko odczyt) |
| `dane_tibia/RAPORT_mijanie_F2_1018.md` | raport F2 (generowany: `python3 -I narzedzia/odtworz_mijanie.py --do 2026-10-18T21:00 --raport dane_tibia/RAPORT_mijanie_F2_1018.md`) |

### Testy

- `python3 testy/test_mijanie.py` → **82 / 82**: golden master `MIJANIE=0` (5 scenariuszy `decyduj`, ślad pozycji i zdarzeń identyczny z bazą `1f18bc7`, także bez klucza `MIJANIE`), wszystkie przypadki z „Weryfikacja” (przechodzień z boku, korytarz szer. 1 z wnęką, ta sama strona przed nami, z naprzeciwka, walka, moby), trzymanie kierunku po zniknięciu gracza, ponowne spotkanie (Z6), obozowicz (Q1), brak bezpiecznego kierunku, wyłączniki, pokrętła, pętla goblinów w obie strony, prawdziwy `Cavebot.tick()` na atrapie świata, F2 na telemetrii syntetycznej.
- Cały zestaw `testy/` (99 plików, z limitem 300 s na plik): wynik **identyczny z bazą `1f18bc7`** poza nowym `test_mijanie` (93 pliki rc=0 w obu). Te same 5 plików nie przechodzi w bazie i po zmianach: `test_cavebot` (478/481: 37k, 37k2, 37k3 — wypad/drabina), `test_czaszka_czat` (60/61), `test_wpadniecie` (74/75), `test_loot_jedzenie` i `test_loot_zbierz` (rc=2, brak zrzutów w `testy/dane/`). Żadnej nowej czerwieni.
- `test_unikanie` 39/39, `test_unikanie_tor` 26/26, `test_patrol_gracz_zmiana` 17/17, `test_cudzy_mob` 12/12 — bez zmian.

### Pętla `gobliny_edron_z8_petla` w obie strony

Tak. 273 punkty (271 różnych pól; zamknięcie = pierwszy punkt i jedno skrzyżowanie `(33092,31846,8)` odwiedzane dwa razy), wszystkie na z8, każdy krok o jedno pole w osi (zero skosów, zero zawrotów a-b-a), wszystkie pola przechodnie wg mapy klienta, **zero pól z flagą 2 (schody/dziury/liny)**, wszystkie 271 pól są w `znane_pola.json` (postać tam stała). Cavebot umiał iść pętlą wstecz tylko na końcu okrążenia (`punkty.reverse()` przy `ODWROCENIE_TRASY`/trasie otwartej); odwrócenie w środku okrążenia dodane za `MIJANIE` (`_mijanie_zastosuj`, następny cel = punkt tuż za nami; przetestowane na każdym 7. punkcie pętli i na polach odwiedzanych dwa razy).

### Odstępstwa od specyfikacji

1. **Test „mob 3 pola od gracza, pełne HP → nasz” z sekcji Weryfikacja zastąpiony przeciwnym** zgodnie z odpowiedzią Karola Q4 i briefem: mob w obrębie `UNIKANIE_MOB_PROMIEN` (4 pola) gracza jest jego, także niebity (`pomin_moba` bez zmian); nasz jest mob 6 pól od gracza. Sprzeczność w samej specyfikacji (Weryfikacja pisana przed Q4).
2. **Moby „idzie na niego” / „bity przez niego” poza obrębem 4 pól**: bez nowej reguły (brief: `pomin_moba` bez zmian); zostaje heurystyka HP z `CUDZY_MOB` (mob z HP < 100%, którego nie zaczęliśmy, 60 s po zobaczeniu obcego). Nie ma wykrywania kierunku ruchu moba.
3. **Q2 (postój)**: bezpiecznik 15 s (brief) zamiast 5 s z pytania. Postój kończy się wcześniej: gracz przeszedł / zniknął z widoku / stanął na 3 s / odchodzi / walka.
4. **Q3**: nowy kierunek trzymany na stałe, bez zegara (min. 20 s z pytania nie jest potrzebne). Decyzja wobec gracza wygasa, gdy zniknie z widoku na `MIJANIE_ZNIKL_S` (6 s) = „kolejne spotkanie” (Z6); wobec obozowicza po `MIJANIE_OBOZ_PAMIEC_S` (60 s).
5. **Bezpieczniki dodane ponad specyfikację** (żeby nie było przeskoków i zapętleń): odstęp co najmniej 8 s między dwiema zmianami kierunku (`MIJ_ZMIANA_MIN_S`, stała w kodzie), co najwyżej 2 odwrócenia przez tego samego obozowicza w 120 s (potem „przechodzę obok niego”, Q1), 2 s przerwy po braku bezpiecznego kierunku, powrót z wnęki na oś korytarza po ustąpieniu, `MIJANIE_PONOW_S` 20 s między ustąpieniami temu samemu graczowi.
6. **Q5 (tylko pętla i skróty)**: celem skrótu jest zawsze punkt pętli, ale droga A* do niego może przejść po polach poza pętlą (do `MIJANIE_SKROT_MAX` = 40 pól), jeśli to najkrótsze obejście strefy obozowicza; bez zejścia w boczne komory jako cel.
7. **Aktywacja unikania**: przy `MIJANIE=1` zostaje stara maszyneria spotkania (`aktywne`, debounce, `znikl`), bo używa jej patrol (`_patrol_gracze`); zdarzenia nazywają się wtedy `mijanie_start`/`mijanie_koniec`, a `unikanie_start`/`unikanie_koniec`/`unikanie_punkt`/`unikanie_blokada` nie powstają. Decyzje mijania nie zależą od debounce.
8. Pokrętła `MIJANIE_*` poza `MIJANIE` są dostępne dla analityka w granicach `ZAKRESY` (brak mechanizmu wyłączenia pojedynczych kluczy z listy analityka); `MIJANIE` i trzy pokrętła zasięgu postoju są zablokowane w górę.

### Faktyczny okres pętli decyzji cavebota

`Cavebot.tick()` + `pauza_po_ticku()` (0,05–0,15 s, w pościgu 0–0,03 s); krok strzałką czeka do `CZAS_KROKU` = 1,5 s na zmianę pozycji (zwykle ok. 0,3–0,5 s), klik wraca od razu. Pomiar z telemetrii (`ruch_okno`: okno_s / liczba ticków, 3577 okien z >= 10 ticków, 15–18.10): **mediana 0,40 s** (P25 0,34, P75 0,52, P90 0,85). Próbka telemetrii jest ograniczona do 1/s (`telemetria.py` `probka`: >= 1,0 s), czyli ok. 2,5 ticka na próbkę. Model F2 używa ticka 0,4 s i kroku marszu co 0,55 s (tempo z telemetrii: P75 1,7 pola/s w IDZ).

### F2 w skrócie (model, nie gra; szczegóły w `RAPORT_mijanie_F2_1018.md`)

108 z 137 spotkań na spocie dopasowano do trasy i odtworzono (reszta to patrol po miejscach, wypad, dojście). Przechodnie bez zmiany planu: model **90%** (82/91), nagrany bot 9% bez `unikanie_start` (63% bez zmiany punktu trasy). Zawroty/min przy graczu polującym/stojącym: nagranie 4,9, model 1,0 (kontrola modelu bez mijania 1,1), tło 3,0. Czas w widoku obcego od pierwszej decyzji: 175 s → 74 s (15 spotkań z decyzją po obu stronach). Palandysz 13:31: odwrócenie obiegu 7 pól od stojącego gracza; Eliu 17:44: odwrócenie, gracz znika z widoku (21 s → 0 s); Harley Queen 18:26 i Eliu 17:46: skrót wokół obozowicza; Palandysz 14:03: bez zmiany planu.

### Niezweryfikowane

- Cokolwiek w grze: klasyfikacja „idzie w naszą stronę / stoi / zatyka przejście” na żywym ruchu, działanie `krok_do` w skrócie i przy ustępowaniu w trybie kliku, mijanie w prawdziwym korytarzu (nagrania dają jedno ustąpienie na 108 spotkań; reszta to testy syntetyczne).
- Miary F2 to model: gracze z nagrania nie reagują na bota, brak mobów, w stanach innych niż IDZ pozycja bota jest nagrana. „Zawroty/min ≤ tło” jest spełnione w modelu, ale model nie dreptuje z natury (nie ma walki i mobów), więc to dolne oszacowanie, nie dowód.
- Liczby spotkań z raportu nie zgadzają się z tabelą ze specyfikacji (84; 63/15/6): skrypt tamtej analizy nie jest w repo, definicja spotkania jest inna (przerwa 30 s).
- Promień „obrębu” moba (`UNIKANIE_MOB_PROMIEN`), pomyłki „kto bije moba”. (Losowe odwrócenie obiegu na końcu okrążenia cofało trzymany kierunek - naprawione po przeglądzie, patrz niżej.)
- Wpływ na tryb patrolu po miejscach (`TRYB_PATROL`): bez zmian, mijanie dotyczy tylko marszu po trasie (`_idz_trasa`).
- Nie zaktualizowano `STAN.md` (zmiana poza zakresem zadania); do zrobienia przy wdrożeniu.

### Przegląd i poprawki

Niezależny checker: **NITS** (bez blokera; jedna luka w Q3, kilka niepokrytych mutacji, trzy drobiazgi). Poprawki w tym samym worktree, bez commita.

**Co poprawiono**

1. **Q3 - losowe odwrócenie trasy cofało trzymany kierunek** (`cavebot._idz_trasa`, koniec okrążenia). Przy `MIJANIE=1` odwrócenie losowe (`ODWROCENIE_TRASY`) jest pomijane, gdy `Unikanie.mijanie_trzyma()`: trwa decyzja wobec któregoś gracza (`mij_dec`) albo jakikolwiek gracz był w widoku w ostatnich `MIJANIE_ZNIKL_S`. Trasa otwarta (`self.otwarta`) odwraca się na końcu jak dotąd (inaczej bot stoi). `MIJANIE=0`: ta sama instrukcja, to samo losowanie (bez zmian). Drugi skutek: gdy mijanie trzyma kierunek, a okrążenie się kończy, bot idzie dalej w tę samą stronę.
2. **`przebyte` zerowane przy odwróceniu mijania** (`_mijanie_zastosuj`, akcja `odwroc`): "koniec okrążenia" liczy się znów od zera po zmianie kierunku (wcześniej mógł przyjść po kilku krokach).
3. **Testy** (+20, razem 102/102). Każdy nowy test sprawdzony na kopii projektu z jedną mutacją (kopia w katalogu roboczym sesji, nie w repo; skrypt mutacji nie jest w repo). Wynik w tabeli poniżej.
4. **Drobne**: docstring `_tor_aktualizuj` (duchy powstają także przy `MIJANIE`, tylko `mijanie()` z nich nie korzysta); `MIJANIE_OBOZ_S` w `pokretla.py` zawężone z 1-15 s do **1-3,5 s** (wybrane zamiast liczenia `obs_s` z `mij_slad`: `obs_s` wynika z okna `UNIKANIE_TOR_OKNO_S` = 4 s, więc wartość >= 4 s oznaczałaby, że obozowicz nigdy nie powstaje; zmiana jednej linii i jeden test `K4`, bez zmiany semantyki "stoi = bez ruchu w oknie"); komentarz w `_mijanie_zastosuj`, że po `odwroc` krok robi następny `_idz_trasa` (obieg niezużyty).

**Mutacje: które teraz padają** (mutacja = jedna zmiana w kodzie na kopii; "przeżyła" = test nie padł)

| Mutacja | Przed | Teraz padają |
|---|---|---|
| M4 (a: `ta_strona`, b: `oboz`) usunięty warunek `kt < kp` (gracz za nami) | przeżyła obie | R1a, R1b |
| M6 usunięta pamięć decyzji `klucz in mij_dec` | przeżyła | R2a-R2d |
| M7 usunięty odstęp `MIJ_ZMIANA_MIN_S` | przeżyła | R2b |
| M10 usunięty cooldown `MIJANIE_PONOW_S` | przeżyła | R4 |
| M12 `_mij_ku_graczowi` nie liczy drugiego gracza | przeżyła (B1 było puste: drugi gracz wychodził z zasięgu, a A stał jako obozowicz) | R3 |
| M16 decyzja nie wygasa po zniknięciu gracza | wykryta (Z6, M8) | Z6, Z6b, M8b, M8c + R2d, R5 |
| M17 decyzja wygasa od razu | przeżyła | R2a-R2d |
| C4 `w_walce` bez `self.cel` | przeżyła | I4b |
| C5 `w_walce` bez `hp_gracza_spadek` | przeżyła | I4c |
| Q3a (nowa) bez pominięcia losowego odwrócenia | - | Q3a, Q3e |
| Q3b (nowa) bez `przebyte = 0` | - | L5d |
| Q3c (nowa) `mijanie_trzyma` tylko z `mij_dec`, bez "gracz niedawno w widoku" | - | Q3e |
| Q3d (nowa) `mijanie_trzyma` tylko z widoczności, bez `mij_dec` | - | **przeżyła: mutant równoważny** (decyzja wygasa razem z widocznością, `mij_dec` ⊂ "niedawno widziany"; warunek `mij_dec` zostaje jako czytelny, tani bezpiecznik) |

Nowe testy: R1a/R1b (gracz/obozowicz za nami na małej pętli z `MIJANIE_PRZOD=30`), R2a-R2d (decyzje bez stosowania: bot idzie starą trasą, gracz dalej przed nim; powtórzenie decyzji, odstęp 8 s przy dwóch graczach, poza widokiem 4 s vs 8 s), R3 (drugi gracz za nami idący w stronę odwróconego obiegu), R4/R4b (cooldown ustępowania + kontrola z `MIJANIE_PONOW_S=1`), R5 (`mijanie_trzyma()` w czasie), I4a-I4c (`Cavebot._mijanie_trasa`: cel / spadek HP = brak decyzji, kontrola bez walki), Q3a-Q3e (`Cavebot.tick()` z `ODWROCENIE_TRASY=1.0`: z decyzją, przechodzień bez decyzji, bez graczy, `MIJANIE=0`, trasa otwarta), L5d, K4.

**Wyniki komend (po poprawkach)**

- `testy/test_mijanie.py` **102 / 102** (było 82); `test_unikanie` 39/39; `test_unikanie_tor` 26/26; `test_patrol_gracz_zmiana` 17/17; `test_cudzy_mob` 12/12; `test_cavebot` **478/481** (te same 3 padają jak w bazie: 37k, 37k2, 37k3).
- Raport F2 wygenerowany ponownie: `timeout 600 python3 -I narzedzia/odtworz_mijanie.py --do 2026-10-18T21:00 --raport dane_tibia/RAPORT_mijanie_F2_1018.md` - **plik identyczny z poprzednim** (liczby bez zmian: model nie odtwarza końca okrążenia ani losowego odwrócenia, a zmiany dotyczą tylko tych miejsc i zakresu pokrętła).

**Nie zrobiono / zastrzeżenia**

- Losowe odwrócenie na końcu okrążenia nie jest modelowane w F2, więc raport F2 nie pokazuje zysku z poprawki Q3; dowód to testy Q3a-Q3e na `Cavebot.tick()`.
- Pomijanie losowego odwrócenia obejmuje też sytuację, w której gracz tylko przeszedł obok (bez decyzji) i był w widoku przez ostatnie 6 s (zgodnie z poleceniem: "gracz był widziany w MIJANIE_ZNIKL_S"); skutek: najwyżej jedno okrążenie w tym samym kierunku więcej, nie zmiana kierunku w stronę gracza.
- Nic nie uruchamiano w grze, bez commita i pusha.

