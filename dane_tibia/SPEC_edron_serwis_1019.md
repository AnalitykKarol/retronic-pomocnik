# SPEC: serwis w Edronie (wymiana gold, jedzenie, backpack, blanki) - 19.10 — ZATWIERDZONA do implementacji (Karol 19.10: „celem jest kompletny skrypt, test na drugiej postaci, push na main”)

Cel: bot główny (Mastafian, `gobliny_edron`) po wizycie w depo Edron sam robi zakupy, które dziś robi tylko Thais-owy szkic
(`SPEC_wyprawa_serwis_1016.md`, niezaimplementowany): wymienia gold na platinum, kupuje jedzenie, backpack i blank runy, po czym
wraca na spot. Ten sam silnik ma obsłużyć Thais przez dane (lista przystanków per miasto), bez drugiej kopii kodu.

## Stan dzisiaj (zmierzone 19.10, kod i dane)

- `wyprawa.py` kupuje tylko w Thais (Gorn, Frodo, Xodet; `NPC_DOMYSLNE`, `trasy/wyprawa_sklepy.json` ma tylko `frodo`, `xodet`).
- Plany Edron (`PLANY_PK`: `edron`, `gobliny_edron`) mają `"npc": None`: bot jedzie do depo (33173,31796,z8) i tam STOP/powrót, bez zakupów.
- Moduł `kup_u_npc` i dialog `hi -> buy N x -> yes` są sprawdzone na żywo (Thais, 13.10). Brak: komendy `change gold` (grep: 0 trafień),
  zakupu backpacka, przystanków Edron, przerwy między depo a sklepami.
- Zakup zależy od alarmów i STOP-ów istniejącej maszyny wyprawy (utknięcie, HP, PK), więc nowe przystanki dziedziczą ochronę.

## Wymagania Karola (19.10, w trakcie nagrywania trasy)

- **Depo: wolna skrzynia, nie jedna konkretna.** Bot ma podejść do dowolnej wolnej skrzyni depo (inni gracze zajmują pola),
  a nie stać zawsze przy jednej. Dziś `zloz_w_depo` próbuje sąsiednich pól, ale najpierw stałej skrzyni z Thais
  (`SKRZYNIA_DEPO`, `POLE_ZLOZ_DEPO`); dla Edronu potrzebna lista skrzyń/pól stania i wybór najbliższej wolnej.
- **Do depo schodzą 3 schody, dowolne.** Wybór najtańszego wejścia z bieżącej pozycji.
- **Depo ma dwa poziomy (19.10):** Use na wolnej skrzyni otwiera depo (locker), a w nim trzeba jeszcze otworzyć jedną skrzynkę,
  dopiero do niej idzie loot/runy/platinum. Dzisiejszy `zloz_w_depo` traktuje pierwszy nowy kontener jako cel składania, więc
  w Edronie wstawiłby przedmioty do lockera zamiast do skrzynki albo zgłosił porażkę. Potrzebny drugi krok „otwórz skrzynkę w
  depo” i kryterium wolnej skrzyni (pole sąsiadujące, nie zajęte przez gracza). Pole stania zmierzone: (33175,31796,z8).
- **Zmierzone na żywo 19.10 12:33 (próba bez przenoszenia czegokolwiek):** z pola (33175,31796,z8) Ctrl+klik na pole `(0,-1)`
  (`ekran.otworz`) otwiera kontener `locker` (pojemność 30, 1 pozycja „DEPOT”, postać stoi). Ctrl+klik na slot 0 tego okna
  (ekran 786,522) zamienia go w `depot chest` (pojemność 30; ten sam numer kontenera 1, nie nowy, więc kryterium „nowy numer” nie
  wystarczy, trzeba sprawdzić `nazwa == "depot chest"`). Próbę trzeba wywołać z `RETRONIC_TESTY=1` (STOP blokuje input).
- **Składanie wykonane na żywo 19.10 12:36 (przez bota, po współrzędnych):** backpack z UH przeciągnięty (przeciągnięcie ze slotu 0
  plecaka na wolne pole `depot chest`), potem platinum 13 → przeciągnięcie na stos 36: okno „Move Objects” ma suwak od 1 do 13 (bez pola
  tekstowego), ustawione 10 klikiem lewej strzałki 3 razy, Ok. Wynik z pamięci: plecak 3 platinum (300 gold), depo 46 platinum, 4 backpacki.
  **Błąd do naprawy:** `loot.przenies_miedzy` odmawia na tym oknie: `okna: niezgodne z ekranem (4 slotów)`; `_okno_ilosci_ok` zawsze zatwierdza
  całą ilość (suwak na maksimum), więc „zostaw 3” wymaga nowej funkcji (liczba strzałek = ilość − cel).
- **Ham zmierzony na żywo 19.10 12:38 (zakup Karola, odczyt pamięci):** plecak po zakupie = 5 ham (id 3582), gold 68, platinum 2 (przed: gold 8,
  platinum 3). Czyli 5 ham = 40 gp (8 za sztukę, zgodne z danymi), płatność z automatycznym rozmienieniem: serwer zabrał 1 platinum, resztę
  60 gold oddał. Wniosek: bot nie musi trzymać gold na ham; wystarczą platinum, więc „zostaw 3 platinum” pokrywa zakupy.
- **Dialog u Mirabell (czat 12:37–12:38):** `hi` -> „Welcome to the Horn of Plenty, Mastafian.” -> `5 ham` (bez słowa `buy`) -> `yes` ->
  „Here it is.” -> „Come back soon, traveller.”. Linii z ofertą „… for N gold” w czacie nie było, więc `ODP_OFERTA` z `kup_u_npc`
  (`buy N x for G gold`) tu nie złapie oferty: trzeba albo komendę `buy 5 ham` (do sprawdzenia, czy też działa), albo weryfikować
  zakup po plecaku, nie po tekście. Cap po 5 ham: 96 (ham 20 oz/szt.), co mieści się w `WYPRAWA_CAP_REZERWA`.
- **Backpack u Beatrice zmierzony (czat 12:40, pamięć plecaka):** `hi` -> `backpack` (literówka `backpackl` też przeszła) -> Beatrice: „Do you want to
  buy a blue backpack for 20 gold coins?” -> `yes` -> „Here you are.” -> „See you later.”. Plecak: gold 68 -> 48 (20 gp), nowy backpack
  (id 2869) w slocie 0 głównego plecaka, cap 96 -> 80 (18 oz). Oferta ma postać „buy a <rzecz> for N gold coins” (bez liczby sztuk i
  z „coins”), więc `ODP_OFERTA` (`buy\s+(\d+)\s+...\s+gold`) jej nie dopasuje: wzór do poszerzenia o rodzajnik i „coins”.
- **Beatrice** stoi 2 pola na północ od pola stania (33214,31805,z6), za ladą (zgodne z danymi: 33214,31803,z6).
- **Blanki u Alexandra zmierzone na żywo 19.10 12:50 (test przez bota):** stoi (33255,31841,z3), Alexander 2 pola na północ za ladą.
  Dialog: `hi` -> „Hi there Mastafian.” -> `20 blank rune` (bez `buy`) -> „Do you want to buy 20 blank runes for 200 gold?” -> `yes` ->
  „Here you are.”. Zapłacone 2 platinum (200 gp), 10 gp/szt. Oferta zawiera liczbę, więc `ODP_OFERTA` pasuje, ale komenda w `kup_u_npc`
  to `buy N x` (czy działa u Alexandra: niesprawdzone; `N x` działa u Mirabell, Alexandra i `backpack` u Beatrice).
  Pierwszy `hi` z `kup_u_npc` zgubił się (brak echa w czacie) po moich kliknięciach w panelu; drugi przeszedł. Do ustalenia: powtórka `hi`.
  Blanki trafiły: 5 do niebieskiego baga (otwartego), 15 do głównego plecaka (po 1 na slot, niescalone). Przeniesione 15 szt. do baga:
  `loot.przenies_miedzy` (okna po nazwie) działa, `loot.przenies_do_runow` NIE: główny plecak z 15 blankami z 19 pozycji spełnia
  `czy_runy` (n_run*4 >= len*3), więc oba okna to „runy” i `plan` nie znajduje plecaka (znany błąd „klasyfikacja bagów”).
  Końcowo: bag na runy 20/20 blanków, plecak bez blanków.
- **UI okien plecaków (Karol 19.10: „pamiętaj o rozszerzaniu plecaków w UI”):** w układzie z minimapą (940x1030) panel kończy się
  na y≈733: główny plecak widać tylko w 8 slotach (2 rzędy), a `rozciagnij_plecak` i `SLOT_PLECAKA_EKWIPUNEK = (1089,143)` mają
  współrzędne z okna 1175x910, więc `otworz_plecak` kliknął w pustkę (minimapa). Do naprawy: współrzędne względem rozpoznanego panelu,
  rozciągnięcie obu okien po otwarciu (bag na runy i plecak), obsługa minimapy w układzie.
- **Rozszerzenie plecaka wykonane na żywo 19.10 12:54:** minimapa zwinięta przyciskiem „–” (909,42), co zwolniło ok. 150 px panelu;
  `loot.rozciagnij_plecak` rozciągnęło okno plecaka z 2 do 5 rzędów (20 widocznych slotów, oba okna w pełni widoczne: bag na runy
  760,296..., plecak 760,507...). Wniosek: przed serwisem bot musi sam zwinąć minimapę (albo ustawić układ bez niej) i rozciągnąć oba okna.
- **Wymóg Karola (19.10): skrypt sam rozciąga okna plecaków** (oba: bag na runy i plecak), także gdy trzeba najpierw zwolnić miejsce w panelu
  (minimapa). Bez ręcznego ustawiania UI przed startem serwisu; sprawdzenie widocznych slotów po rozciągnięciu jest bramką startu.
  Karol zakończył zakupy i wraca na spot (19.10 ~12:55), więc nagranie obejmuje też drogę powrotną.
- **Kolejność przystanków edytowalna** (lista w danych, nie zaszyta w kodzie). Domyślna: bank, depo, jedzenie, backpack, blanki.
- Trasę nagrywa Karol ręcznie: `trasy/edron_serwis_surowa.json` + znaczniki `trasy/edron_serwis_znaczniki.jsonl`; potem cięcie na odcinki.

## NPC Edron (dane 7.4 `dane_tibia/serwer74/npc_pelne.json`; pozycje NIEZWERYFIKOWANE w grze)

| Rola | NPC | Pozycja z danych | Oferta z danych |
|---|---|---|---|
| Bank (wymiana gold) | Ebenizer | 33175,31801,7 | dialog zmierzony 19.10 (niżej) |
| Jedzenie z ham | **Mirabell** (tawerna „Horn of Plenty”, z6, 19.10 potwierdzone na żywo) | 33174,31801,6 | **ham 8 gp**, meat 5, cheese 6, bread 4 |
| (jedzenie, nieużywany) | Bonifacius | 33165,31801,7 | meat 5, cheese 5, salmon 4...; brak ham |
| Backpack | Beatrice | 33214,31803,6 | backpack 20 gp (też rope 50, shovel 50, torch 2) |
| Blanki | Alexander | 33256,31839,3 | blank rune 10 gp |

Depo Edron: 33173,31796,z8 (koniec `gobliny_edron_do_depo.json`). Bank i jedzenie są ~5 pól od depo; Beatrice ~40, Alexander ~85.
Uwaga: piętra NPC w danych (Alexander z3, Beatrice z6) wyglądają podejrzanie; przed użyciem potwierdzić z mapy klienta albo z widoku
(`_ucz_npc` zapisuje pozycje NPC, które bot zobaczy).

## Proponowana sekwencja (po wejściu do depo Edron, `WYPRAWA_SERWIS=0` domyślnie)

1. **Depo (Karol 19.10):** odkłada do skrzynki pełny backpack z UH oraz platinum tak, by w plecaku zostały **3 platinum (= 300 gold)**
   na dalsze zakupy (spójne z „ok. 300” ze szkicu Thais). Stan przed składaniem (odczyt 12:34): plecak = backpack (id 2869),
   13 platinum (3035), 8 gold (3031), 1 przedmiot id 3198; `depot chest` ma m.in. 83 gold, 36 platinum, 3 backpacki.
   Nadwyżka platinum = ilość − 3 (przy 13: 10 sztuk, przeniesienie stosu z oknem ilości).
2. **Bank (Ebenizer):** zmierzony dialog (19.10, z czatu): `hi` -> `change gold` -> bankier pyta „How many platinum coins do you want
   to get?” -> liczba platinum (np. `13`) -> `yes` -> „Here you are.”. N = setki gold w plecaku (nie `change gold N` jak w szkicu Thais).
   Weryfikacja: gold spadło, platinum przybyło.
3. **Jedzenie (Mirabell, schody z7 (33171,31818) na z6, stoi (33173,31803,z6)):** `5 ham` (do celu 5 sztuk), bez jedzenia na miejscu: Karol tego nie robił, a głód obsługuje bot własną logiką.
4. **Backpack (Beatrice):** `hi` -> `backpack` -> `yes` (20 gp). Kiedy i po co: pytanie Q3.
5. **Blanki (Alexander):** `buy N blank rune`, przenieś do baga na runy (`przenies_runy`, `BLANKI_AUTO_BAG`).
6. **Powrót na spot:** `gobliny_edron_z_depo.json` (3 zejścia + 4 liny + z7->z8; sprawdzone na żywo 19.10).

Każdy krok ma weryfikację przed/po jak w `kup_u_npc`; porażka = alarm + STOP, nie ciche stanie. Budżet: min. gold na całą kolejkę
(np. 24 ham/meat + 20 backpack + 200 blanki + zapas) sprawdzany przed startem; brak = alarm + STOP bez zakupów.

## Zakres kodu (szacunek, do potwierdzenia po odpowiedziach)

- Dane: `trasy/wyprawa_sklepy.json` + przystanki Edron (npc, stoi/npc_poz, dojście), plan `gobliny_edron`/`edron` z listą NPC zamiast `None`.
- `wyprawa.py`: przystanki per plan (dziś zaszyte `gorn/frodo/xodet`), nowe kroki `bank` i `backpack`, trasa depo -> sklepy -> depo -> spot.
- Testy na atrapach (jak `test_wyprawa.py`), potem próba na żywo każdego NPC osobno przy Karolu, na końcu cała kolejka.

## Do ustalenia z Karolem (UNKNOWN, nie zgadujemy)

- **Q1 jedzenie. ROZSTRZYGNIĘTE (19.10):** ham jest w Edronie u Mirabell (tawerna, piętro z6), 8 gp wg danych; Karol kupił 5 ham. Mój pierwszy wniosek
  „brak ham w Edronie” był błędny: sprawdziłem tylko Bonifaciusa.
- **Q2 wymiana gold. ROZSTRZYGNIĘTE (19.10, z czatu):** `hi` -> `change gold` -> liczba platinum -> `yes`.
- **Q3 backpack.** Do czego: zapasowy do podmiany pełnego, czy nowy bag na runy po złożeniu starego do depo (jak w szkicu Thais)? Ile sztuk i kiedy kupować?
- **Q4 wyzwalacz.** Serwis tylko przy okazji wyprawy do depo (brak blanków/jedzenia/pełny bag), czy też co N godzin? Rekomendacja: tylko
  z wyprawy, istniejące wyzwalacze, bez nowego.
- **Q5 budżet.** Ile gold zostawić po zakupach i ile blanków brać (dziś `WYPRAWA_BLANKI=15` cel, `..._MAX_KOSZT=500`).
- **Q6 start.** Cała kolejka naraz, czy fazami (najpierw bank + blanki, potem backpack)? Rekomendacja: fazami, każda za osobnym pokrętłem.

## Poza zakresem

- Thais (osobna decyzja; silnik ma jednak być na tyle ogólny, by dopisać je samymi danymi).
- Sprzedaż lootu NPC, obsługa depo poza tym, co jest, F4/PvP.
- Zmiana masek ognia i danych bezpieczeństwa.

## Weryfikacja (kryterium zaliczenia)

Testy jednostkowe zielone, plus przebieg na żywo: depo -> bank (gold spadło, platinum przybyło) -> jedzenie (zapas rośnie) -> backpack
(nowy plecak w ekwipunku) -> blanki (liczba rośnie, bag na runy) -> powrót na spot bez alarmu. Pomiar w telemetrii (`wyprawa_koniec`).


## Decyzje i architektura (19.10, po nagraniu i testach na żywo)

Decyzje (odpowiedzi z pomiarów i poleceń Karola): Q1 ham u Mirabell; Q2 `change gold` -> liczba platinum -> `yes`; Q3 backpack to nowy
bag na runy po złożeniu pełnego baga z UH w depo (kupiony u Beatrice za 20 gp); Q4 wyzwalacz: skrypt uruchamiany ręcznie albo z wyprawy
do depo (pokrętło `WYPRAWA_SERWIS`, domyślnie 0); Q5 budżet: po depo w plecaku zostają 3 platinum, kolejka kosztuje 260 gp
(5 ham 40 + backpack 20 + 20 blanków 200); Q6 jeden skrypt z listą kroków, kolejność edytowalna w danych.

Pliki (nowe): `serwis.py` (orkiestrator, chodzenie, CLI `python3 -I serwis.py edron [--kroki bank,depo,...] [--na-sucho]`),
`serwis_akcje.py` (UI plecaków, rozmowa z NPC, depo; wołają istniejące `loot`, `ekran`, `mozg`), `generuj_serwis_edron.py` (dane z nagrania),
`trasy/serwis_edron.json` (przystanki, łączniki pięter, kolejność), testy `testy/test_serwis*.py` na atrapach.

Chodzenie: A* po piętrze (`Trasownik.odcinek`) + tabela łączników pięter wyciągnięta z nagrania (pary kolejnych punktów o różnym z).
Dzięki temu dowolna kolejność przystanków działa bez nagranych odcinków; nagranie zostaje dowodem i wzorcem do porównania.

Zasady bezpieczeństwa: start tylko przy zatrzymanym bocie głównym albo z jego wyprawy; HP >= próg, brak potworów obok; każdy krok
weryfikowany po plecaku (przed/po); porażka = alarm + STOP z opisem kroku; krok idempotentny (nie kupuje drugi raz, gdy cel osiągnięty);
brak gold na kolejkę (< 260 gp po wymianie) = alarm bez zakupów.


## Stan wykonania i przegląd (19.10 ~14:00)

Zrobione (repo bota, niescommitowane do chwili tego wpisu): `serwis.py`, `serwis_akcje.py`, `serwis_blad.py`, `generuj_serwis_edron.py`,
`serwis.sh`, `trasy/serwis_edron.json`, testy `testy/test_serwis.py` (62) i `testy/test_serwis_akcje.py` (51), fixtury `testy/dane/panel_*.png`.
Uruchomienie: `./serwis.sh` (bot musi stać), `./serwis.sh --na-sucho [--od x,y,z]`, `STARTUJ=1 ./serwis.sh`, `--od-nowa`, `--kroki a,b`.
Nieprzetestowane na żywo przez ten kod (Mastafian gra): rozmowa przez `Rozmowa`, `przygotuj_okna`, `depo_zloz`, `kup`, `przenies_blanki`,
chodzenie po łącznikach (stopnie to zmiany pięter z nagrania, `pietra.py` ma je przejść jak zwykłe schody). Cały skrypt czeka na
test na drugiej postaci w Edronie (min. 260 gp, do wymiany min. 100 gold) i dopiero potem na włączenie w główny przepływ wyprawy.

Szacunek kosztu w kontroli budżetu jest celowo zapasowy: ham 10, backpack 20, blank 10 za sztukę = 270 gp dla domyślnej kolejki
(zmierzone realnie 260: ham 8). Majątek 260-269 gp zostanie więc odrzucony; to zapas, nie błąd.

Przegląd niezależny (agent `checker`, dwie rundy, tylko odczyt). Runda 1: CHANGES-REQUIRED, naprawione:
- #1 weryfikacja przeciągnięcia na OBU końcach (plecak ubył i skrzynka/bag przybył), pojemność okna vs kontener; spadnięcie na podłogę = błąd;
- #2 idempotencja: plik stanu `serwis_stan.json` (wznawia przerwany przebieg tej samej listy kroków do 3 h, `--od-nowa` ignoruje),
  strażnik „nie odkładaj baga z samymi blankami”, zamykanie każdego okna poza plecakiem po składaniu, bag rozpoznawany po nazwie
  (`*backpack`, `*bag`), zwłoki nie są bagiem, dwa kontenery o nazwie plecaka = błąd;
- #3 budżet przed startem (szacunek ham 10, backpack 20, blank 10 za sztukę; po depo zostaje 3 platinum), HP >= 60%, brak potworów w 4 polach,
  brak odczytu stworów = błąd, błąd chodzenia kończy serwis (bez szukania po cichu innych stanowisk), najbliższe stanowisko depo wg drogi;
- #4 zakup: dokładna ilość (nie „co najmniej”) i górny limit wydanych gp; bank sprawdza także spadek gold;
- #5 gałąź „bag w plecaku -> otwórz w oknie” przetestowana, `IndexError` zastąpiony SerwisBlad;
- drobne: tolerancja dojścia 0 (wyjście 2), kanał bez rozróżniania wielkości liter, stare echo nie potwierdza nowej wiadomości,
  każdy wyjątek (nie tylko SerwisBlad) zapisuje STOP, scalanie platinum z istniejącym stosem w depo.
Runda 2 (CHANGES-REQUIRED): R1 start blokowany przez NPC obok (teraz NPC z bazy serwera i martwe istoty są pomijane), R2 budżet liczył
pieniądze z baga, który odchodzi do depo (teraz tylko plecak, gdy depo przed nami), R3 postęp przerwanego przebiegu nie zależy od listy
kroków, R5 scalanie platinum tylko do 100, R6 kontrola wolnego miejsca w bagu PRZED zakupem blanków, R7 testy zamykania okien i prawdziwego
`_okna_numery`; puste asercje usunięte. Wszystkie naprawione i sprawdzone mutacyjnie; trzeciej rundy przeglądu nie było.
Otwarte (świadomie): depo ma ~16 widocznych slotów, po wielu serwisach może zabraknąć miejsca (wtedy błąd „bez wolnego pola”);
mapowanie okien po numerze kontenera jest sprawdzane skutkiem na obu końcach, nie zawartością slotów; ślepe `yes` u Mirabell
(brak linii oferty w logu) chronią dokładna ilość i limit ceny po fakcie; automatyczne wywołanie z wyprawy (bez człowieka) nie jest zrobione.
