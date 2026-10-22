# SPEC: tryb „stoję i robię runy” - 22.10 — ZATWIERDZONY przez Karola 22.10 ~17:05 (odpowiedzi w „Decyzje Karola”), F1 = Thais, wydra

Cel: postać od poziomu 11 przestaje chodzić na trolle (gracze narzekają, że zabieramy im exp) i stoi w jednym spokojnym miejscu
miasta, **poza strefą ochronną (PZ)**, gdzie je ham, robi runy (UH od 11, wcześniej HMM), uzupełnia zapasy przez istniejący serwis
i wraca na swoje pole. Nic więcej. Autor tego dokumentu: agent (rozpoznanie tylko do odczytu 22.10); żadnego kodu ani konfiguracji
nie zmieniono, żadnego bota nie ruszano.

## Decyzje Karola (22.10)

- Od poziomu 11 postaci stoją w jednym miejscu i robią runy zamiast tłoczyć się na trollach. Jedzą ham, robią runy, uzupełniają, nic więcej.
- Depo ma PZ (mana się tam nie regeneruje, nikt nikogo nie zabije), więc postać stoi **poza PZ** w cichym miejscu.
- Jedzenie = ham kupowany u NPC.
- Zaakceptowane („no to by było super”) pięć punktów propozycji: (1) pole przy wejściu do depo/świątyni, poza PZ, 1-2 kroki od PZ i blisko
  NPC z blankami i hamem, wybrane z mapy (nie na oko), osobno dla Edronu i Thais; (2) bezpieczeństwo: poza PZ można dostać, więc przy PK,
  ataku gracza, niskim HP, GM albo pytaniu „bot?” wejście do PZ i stanie tam + krytyczne powiadomienie (jak dzisiejsza obrona);
  (3) pętla: stój -> jedz ham, gdy głód -> rób runę, gdy jest mana -> brak blanków lub hamu = serwis -> powrót na pole; pełny plecak run do depo;
  (4) runy: UH (adura vita, tryb `uh`) od 11, wcześniej adori gran (tryb `runy`); (5) jedna nasza postać na miasto naraz.
- **Odpowiedzi Karola na „Do decyzji” (22.10 ok. 17:05) — wiążą ponad rekomendacje niżej:**
  - Pole: Karol stoi wydrą JEDNO pole od strefy ochronnej, za ścianą; PZ obejmuje teraz tylko wnętrze całego depo. Pierwsze stanowisko
    Thais = pozycja wydry zmierzona 22.10 17:04: **(32339,32221,7)** (status.sh, `w_depo: false`). Cel ucieczki = najbliższe pole wewnątrz depo (PZ), do pomiaru w F1.
  - Gotowe runy: **tylko do depo** (bez sprzedaży).
  - Czas: **maks. 3 h** stania pod depo na zmianę.
  - Zgoda na stanie poza PZ: **tak, test teraz na wydrze**.
  - Pierwsze miasto: **Thais** (nie Edron).
  - Gracze/„bot?”: dużo ludzi tak stoi, nie da się odróżnić bota od gracza — **bez specjalnej reakcji na rozmowę**; gdy ktoś **atakuje → uciekamy** (do PZ) i tyle.
  - Rodzaj run: **decyduje Karol** (ręcznie, tryb `runy`/`uh` w konfiguracji/grafiku); bez automatu przełączania na 11 lvl.
  - Bezczynność: **„coś trzeba robić”** — jedna runa to za rzadka aktywność, żeby uniknąć wylogowania; potrzebna lekka, ludzka aktywność między runami
    (np. obrót postaci, krok w bok i powrót, otwarcie/zamknięcie okna) z losowym odstępem krótszym niż limit bezczynności serwera (limit do zmierzenia).

## Poza zakresem

- Walka z potworami, loot, pościg, expienie (tryb nie ma potworów na liście celów).
- Sprzedaż run (patrz pytanie 2), handel graczami (osobny `stoj_trade`).
- Nowy odczyt flagi PZ z pamięci klienta (propozycja jako faza późniejsza, nie warunek F1).
- Zmiany w nadzorcy poza wyjątkiem dla map „stanowisko” (nadzorca nie dotyka pokręteł ani plików danych, `NADZORCA.md`).
- Automatyczny wybór poziomu 11 -> przełączenie `runy` na `uh` (dziś robi to Karol albo wpis w grafiku; patrz „Otwarte”).

## Stan dzisiaj (zmierzone 22.10, kod i dane; stan = checkout, wydane CLI nie sprawdzano)

### Co już jest i się nadaje

- **Runy w spokoju.** `uh.py` (tarcza do plecaka, blank do ręki, rzut hotkeyem, runa do plecaka, tarcza z powrotem); start w
  `uh.mozna_robic` (`uh.py:93-122`): HP >= `UH_MIN_HP` (90), mana >= `UH_MANA_MIN`, odstęp `UH_ODSTEP_S` 20 s, pauzy po porażkach (`UH_PRZERWA_PO_PORAZKACH_S` 60 s)
  i braku blanków (`UH_PRZERWA_BRAK_BLANK_S` 600 s); pokrętła `cavebot.py:324-356`. Tryby `runy` (adori gran, F6, 70 many) i `uh`
  (adura vita, F7, 100 many) w `tryby.json:34` i `:53`, oba z `JEDZENIE_CZAR_AKTYWNY=0` (ham z plecaka) i `ZDROWIE_CZAR_AKTYWNY=1` (exura przy HP < 80%).
- **Dane czarów serwera** (`dane_tibia/serwer74/czary.json`): adura vita = Ultimate Healing Rune, `LevelCast` 11, 100 many, 1 ładunek, tylko druid; adori gran =
  Heavy Magic Missile, `LevelCast` 3, 70 many, 5 ładunków. Czyli „UH od 11” zgadza się z danymi serwera; komentarz `uh.py:39` („UH wymaga lvl 24 u NPC”) jest
  nieaktualny albo dotyczy innej rzeczy (nie ruszam, tylko odnotowuję). Uwaga na koszt: HMM to 14 many na ładunek, UH 100 many na ładunek.
- **Jedzenie.** Głód wykrywany po niewzroście many (`JEDZENIE_MANA_BRAK_S` 90 s, `cavebot.py:98`), `jedzenie_potrzebne`/`zjedz`, zapas `JEDZENIE_ZAPAS_MIN` 5; brak hamu = wyprawa po jedzenie.
- **Serwis i powrót.** `serwis.sh`/`serwis.py` z planami `trasy/serwis_edron.json` (bank Ebenizer (33172,31803,7), depo (33175,31796,8), ham Mirabell
  (33173,31803,6), backpack Beatrice (33214,31805,6), blanki Alexander (33255,31841,3), wyjście (33167,31815,7)) i `trasy/serwis_thais.json` (depo (32348,32225,7),
  ham Frodo (32358,32210,7) za drzwiami (32365,32208,7), backpack Gorn (32377,32201,7), blanki Xodet (32400,32220,7) za drzwiami (32400,32217,7), bank Suzy (32319,32256,7));
  kroki `bank,depo,jedzenie,backpack,blanki,wyjscie`, `--pomin-brakujace`, `--na-sucho`; `refill.sh` (`--tlo`, `--spot`, `--przerwij`) z `STARTUJ=1` rusza bota ostatnią mapą i trybem.
  `wyprawa.py` z `WYPRAWA_DEPO_BLANKI`/`WYPRAWA_BLANKI`/`WROC_REFILL` (domyślne w `runy`) wraca po blanki do depo, robi refill (`wyprawa.py:2301-2349`, `refill_auto.py`, cooldown 20 min).
- **Obrona przed graczami.** `cavebot._pk_tick_u` (`cavebot.py:8162`): wykrycie ataku z danych (`obrona_pk.DetektorPK`), czaszki, lista wrogów, stany UCIECZKA -> DEPO -> POWROT
  (marsz do depo przez `wyprawa.start_pk`, `_pk_depo_tick` `cavebot.py:8650`: czekanie w depo, karencja `PK_KARENCJA_MIN` 30 min, po niej powrót). GM/CM: stan GRACZ i alarm (`cavebot.py:4763-4776`); zwykły
  przechodzień: gramy dalej. Pytania „bot?” obsługuje `czat_spot.py` (`PROWOKACJA` = tylko dymek, Karol przejmuje).
- **Rezerwacje miejsc.** `miejsca_koord.py` `Koordynator`: `instancje/_wspolne/zajete.json`, flock, TTL 900 s, zwolnienie po martwym pid; konflikt = ten sam klucz albo to samo piętro i odległość Chebysheva <= promień.
  Nadzorca: `mapy_zajete` (`nadzor.py:645`) - ta sama mapa nie idzie do dwóch botów.
- **Precedens „stoi w miejscu”.** Mapa `stoj_trade` (`mapy.json:116`) z trasą jednopunktową `trasy/stoj_trade.json`, ale startowana z `--bez-ruchu`.

### Czego brakuje (luki, każda z dowodem)

1. **`--bez-ruchu` się nie nadaje.** Wyłącza `cavebot.tick` (`mozg.py` ok. 2273-2321, `uruchom.sh` `${MOZG_BEZ_RUCHU:+--bez-ruchu}`), czyli także UH, jedzenie i obronę PK. Potrzebna mapa z jednopunktową trasą
   i pełnym cavebotem.
2. **Trasa jednopunktowa jest „okrążana” w kółko.** `_idz_trasa` (`cavebot.py:10228`) na jedynym punkcie loguje okrążenie przy każdym ticku; potrzebne jawne zachowanie „stanowisko”.
3. **Watchdog bezczynności** (`cavebot.py:5348`, wyjątki `_watchdog_wyjatek` `:5185`) po `WATCHDOG_BEZCZYNNOSC_S` 20 s bez ruchu „rusza trasą” (porzuca zwłoki, kasuje liczniki). Dla stania w miejscu
   bezczynność jest zamierzona; stan stanowiska musi być wyjątkiem.
4. **Nadzorca uzna stanie za zacięcie.** `Nadzor.zaciecie` (`nadzor.py:857-868`): `stoi_poza_walka_s` > `stoi_min` (8 min), telemetria starsza niż 120 s, „brak zabić” > `brak_zabic_min` (25 min) -> drabina napraw (restart/wznów...).
   Bez wyjątku nadzorca w kółko restartowałby poprawnie stojącego bota.
5. **UH blokuje każdy obcy byt w widoku.** `uh.mozna_robic` (`uh.py:111-117`) odrzuca start, gdy w widoku jest *dowolny* stwór lub gracz poza nami z `hp > 0`; `UH_MOB_DYSTANS` dotyczy tylko potworów, gracz „zawsze w pełnym widoku”
   (`cavebot.py:331`). W mieście przechodnie i NPC (lista `stwory` zawiera NPC, `serwis_akcje.py:499` je odfiltrowuje jako „nie zagrożenie”) mogą blokować runy niemal bez przerwy. **Nie zmierzono**, jak często.
6. **PZ nie jest nigdzie odczytywane.** Minimapa (`mapa.py:8-18`, flagi 1/2/4) nie zna PZ; odczyt flag statusu klienta (w tym PZ) jest tylko hipotezą (`dane_tibia/AUDYT_odczyt_i_mapa.md:10` i `:50`: „w kodzie nie ma ani jednego odczytu”).
   Bez tego „stoję poza PZ” i „uciekam do PZ” nie da się zweryfikować z danych; granicę PZ trzeba wpisać ręcznie (patrz „Projekt”, PZ).
7. **Thais: kroki za drzwiami** (Frodo, Xodet) serwis obsługuje od 22.10 (`serwis.py`, nagłówek, pole `drzwi`); bank Thais zmierzony na żywo 22.10 13:32 (`serwis_thais.json`). Pełnego przebiegu Thais od depo do wyjścia i powrotu na pole nie ma tu jako dowodu.
8. **Zerowe dane o bezczynności serwera.** Grep po kodzie, `CLAUDE.md` i `dane_tibia/*.md` nie znajduje żadnego pomiaru ani wzmianki o wyrzucaniu za bezczynność (poza własnym limitem nagrywania trasy). **UNKNOWN**, patrz pytanie 7.

## Projekt

### 1. Mapa typu „stanowisko” (dane, `mapy.json`; edytuje Karol/agent z poleceniem)

Nowy wpis na miasto, np. `stoj_runy_edron`, `stoj_runy_thais`:

```
{ "opis": "Stoi poza PZ i robi runy (SPEC_stoj_runy_1022)",
  "stanowisko": true, "miasto": "edron",
  "trasa": "stoj_runy_edron",            // 1 punkt = główne pole (trasy/stoj_runy_edron.json)
  "pola": [[x,y,z], ...],                // pola do rotacji (patrz 6), pierwsze = trasa
  "pz": [[x,y,z], ...],                  // 1-3 pola W PZ najbliżej stanowiska (cel ucieczki), zmierzone
  "potwory": "", "prog_hp": 50,
  "dojscie": "<trasa z depo/wyjścia serwisu na pole>", "dojscie_z_dowolnego_pietra": true }
```

Cavebot czyta `stanowisko` z wpisu mapy (tak jak czyta `dojscie`). Tryb mapy bez `stanowisko` zachowuje się dokładnie jak dziś.

### 2. Tryb pokręteł `stoj` (`tryby.json`, same pokrętła; łączy się z `runy` albo `uh`)

Start: `RETRONIC_ID=<id> RETRONIC_POSTAC=<nick> MAPA=stoj_runy_edron TRYB=uh,stoj ./uruchom.sh` (przed poziomem 11: `TRYB=runy,stoj`). Tryb `stoj` ustawia:
`STANOWISKO=1`, `UH_MOB_DYSTANS` jak w bazowym, `WYPRAWA_DEPO_BLANKI=1`, `WYPRAWA_BLANKI=20`, `WROC_REFILL=1`, `JEDZENIE_CZAR_AKTYWNY=0`, `ZDROWIE_CZAR_AKTYWNY=1`, `ML_CZAR_AKTYWNY=0`. Nowe pokrętła rejestrujemy w `pokretla.py` (`ZAKRESY` oraz ograniczenia „nie_wyzej/nie_nizej”, `pokretla.py:13`, `:413`, `:432`, aby analityk nie osłabił bezpieczeństwa).

Nowe pokrętła (wszystkie `STANOWISKO_*`, domyślnie wyłączone/bezpieczne; wartość domyślna = zachowanie dzisiejsze, dopóki `STANOWISKO=0`):

| Pokrętło | Domyślnie | Znaczenie |
|---|---|---|
| `STANOWISKO` | 0 | 1 = zachowanie „stanowisko” (pkt 3), ustawia je tryb `stoj` |
| `STANOWISKO_HP_PZ` | 70 | % HP poniżej tego (bez potwora w pobliżu) = wejście do PZ (nikt nas tu nie powinien bić) |
| `STANOWISKO_PZ_KARENCJA_MIN` | 30 | ile minut po ostatnim zagrożeniu zostajemy w PZ (jak `PK_KARENCJA_MIN`, `cavebot.py:688`) |
| `STANOWISKO_GRACZ_ODL` | 0 | 0 = dziś: dowolny obcy w widoku blokuje runę; N > 0 = blokuje tylko obcy gracz bliżej niż N pól (strojenie po F1, wymaga zgody Karola, bo podnosi ryzyko) |
| `STANOWISKO_NPC_IGNORUJ` | 1 | NPC (lista `wyprawa.wczytaj_npc`/`npc_pelne.json`) nie blokują rzutu |
| `STANOWISKO_WOLNE_SLOTY_MIN` | 2 | wolnych slotów w worku na runy poniżej tego = serwis z krokiem depo |
| `STANOWISKO_AKTYWNOSC_MAX_S` | 0 | >0 = po tylu sekundach bez żadnej akcji (rzut, jedzenie, krok) jeden krok w bok i z powrotem; 0 = wyłączone do czasu pomiaru bezczynności serwera (pyt. 7) |
| `STANOWISKO_ROTACJA_MIN` | 0 | >0 = co tyle minut (tylko gdy nikogo w widoku i poza rzutem) zmiana pola z `pola`; 0 = jedno pole na zmianę |

### 3. Zachowanie „stanowisko” w cavebocie

Pętla stanów (to nie nowy silnik, tylko warunki w istniejącym `tick`, kolejność jak `cavebot.py:4690-4830`):

1. **STOJ** - jesteśmy na polu; `_idz_trasa` nie loguje okrążeń; watchdog bezczynności pomija stan (`_watchdog_wyjatek` + `STANOWISKO`).
2. **JEDZ** - istniejący mechanizm głodu (`jedzenie_potrzebne` -> `zjedz`) z plecaka.
3. **RUNA** - istniejący `_uh_tick`; start dopiero gdy mana >= `UH_MANA_MIN`, brak obcych w widoku wg `STANOWISKO_GRACZ_ODL`/`STANOWISKO_NPC_IGNORUJ`.
4. **SERWIS** - brak blanków (`UH_PRZERWA_BRAK_BLANK_S`), zapas hamu < `JEDZENIE_ZAPAS_MIN`, albo wolnych slotów < `STANOWISKO_WOLNE_SLOTY_MIN`: istniejąca wyprawa (`WYPRAWA_DEPO_BLANKI`, `WROC_REFILL`) idzie do depo i robi refill (`bank,depo,jedzenie,backpack,blanki,wyjscie`; kroków, których miasto nie ma, serwis pomija: `--pomin-brakujace`), po czym
   **wraca na pole stanowiska** (cel powrotu = pierwszy punkt trasy; sprawdzić w F1 `--na-sucho`, że powrót nie wymaga `dojscie` w drugą stronę).
5. **PZ_OBRONA** - istniejące UCIECZKA -> DEPO -> POWROT (`_pk_tick_u`), z jedną różnicą: celem ucieczki jest pole `pz` z mapy (najbliższe, 1-3 kroki), nie depo. Karencja `STANOWISKO_PZ_KARENCJA_MIN`. Wyzwalacze: atak gracza z danych, groźna czaszka, wróg z listy w widoku, `GM/CM` (jak dziś stan GRACZ, tu dodatkowo wejście do PZ), HP < `STANOWISKO_HP_PZ`, pytanie „bot?” (`PROWOKACJA`: dziś tylko dymek; tu dodatkowo wejście do PZ do czasu, aż Karol odpowie, **do potwierdzenia**, pyt. 9).
   Krytyczne powiadomienie jak w obecnej obronie (`_pk_powiadom`).

Nie dodajemy zatrzymań z braku postępu: brak runy mimo pełnej many i blanków to naprawa (ponów, wznów, relog przez nadzorcę), nie STOP (reguła „naprawiaj, nie zatrzymuj”, `CLAUDE.md`). Wyjątek bez zmian: PK, niskie HP, śmierć.

### 4. PZ i wybór pól (dane, nie zgadywanie)

PZ nie ma w żadnych danych (luka 6). Źródło prawdy dla F1: **pomiar Karola**. Karol (albo agent w jednym wywołaniu, za zgodą) stawia postać na polu i potwierdza po ikonie PZ w kliencie, czy pole jest w PZ; zapis do `pz` i `pola` w `mapy.json`. Dla każdego pola trzeba:
(a) pole poza PZ, (b) 1-3 kroki do pola w PZ (zapisać w `pz`), (c) ruch graczy mały (do pomiaru, pyt. 6), (d) wolne sąsiedztwo (nie róg, nie schody; `mapa.py pole`).
Faza późniejsza (nie warunek): odczyt flagi PZ z pamięci (`m_states`, kontrolowana zmiana `szukaj`/`zawez`/`sledz`, `AUDYT_odczyt_i_mapa.md:298`), co pozwoli sprawdzać PZ w locie.

**Kandydaci z mapy (22.10, `mapa.py pole`/`droga`; flagi: pole przechodnie, nie schody; PZ i ruch graczy NIEZMIERZONE, to są propozycje do pomiaru, nie wybór):**

| Miasto | Kandydat | Skąd | Sąsiedzi wolni (z 8) | Droga z punktu odniesienia |
|---|---|---|---|---|
| Edron | E1 (33170,31819,7) | ulica tuż za wyjściem z budynku depo/banku, punkt odniesienia wyjście serwisu (33167,31815,7) | 6 | 6 pól |
| Edron | E2 (33171,31820,7) | j.w., jedno pole dalej | 8 | ok. 7 pól |
| Edron | E3 (33175,31819,7) | j.w., wschodnie wyjście budynku | 6 | do zmierzenia |
| Thais | T1 (32346,32229,7) | ulica za salą depo, punkt odniesienia przybycie do depo (32348,32225,7) | 7 | 4 pola |
| Thais | T2 (32349,32229,7) | j.w. | 7 | ok. 5 pól |
| Thais | T3 (32347,32228,7) | j.w., pole bliżej depo | 8 | ok. 3 pola |

Uwaga: te pola są najbliżej *znanych* punktów serwisu, nie najbliżej granicy PZ; granica PZ może leżeć dalej albo bliżej. NPC z hamem i blankami są w obu miastach daleko od depo (Edron: Alexander (33255,31841,3) ok. 80 pól od depo; Thais: Xodet (32400,32220,7) ok. 50 pól), więc „blisko NPC” nie da się spełnić jednym polem; służy do tego serwis (pkt 3). Świątynia: Edron (33217,31814,8), Thais (32369,32241,7) (`spoty_poczatkowe.json`); jeśli Karol woli stanie przy świątyni, kandydatów trzeba wyliczyć osobno.

### 5. Jedna postać na miasto

Klucz rezerwacji `stoj_<miasto>` w `Koordynator` (`miejsca_koord.py`, zasięg: miasto), zdejmowany przy wyjściu/zgonie (TTL 900 s + martwy pid już obsługuje zwolnienie). Dodatkowo `mapy_zajete` (`nadzor.py:645`) zapewnia, że ta sama mapa nie idzie do dwóch botów (każde miasto = jedna mapa `stoj_runy_<miasto>`). Rotacja pól (pkt 6) działa w obrębie jednej postaci.

### 6. Rotacja pól i godzin (obawa Karola: „cały dzień w jednym miejscu wygląda podejrzanie”)

- **Pola:** 2-3 pola na miasto w `pola`; przy starcie zmiany losujemy inne niż poprzednio (pamięć w `instancje/<id>/stan`), opcjonalnie zmiana w trakcie (`STANOWISKO_ROTACJA_MIN`).
- **Godziny:** grafik (`grafik.py`, `instancje/_wspolne/nadzor_konfig.json`) już daje zmiany 2-3 h, przerwy 7-25 min, limit dzienny 480 min, ciche godziny 01:00-08:00, zmianę dnia +-60 min. Dla stanowiska proponuję krótszy limit dzienny (pyt. 3), bo jedno miejsce jest bardziej widoczne niż wędrówka po jaskini. Wylogowanie między zmianami wg istniejącego `SPEC_logowanie_wylogowanie_1021.md`.

### 7. Nadzorca i grafik (wyjątek dla map „stanowisko”)

- `zaciecie` (`nadzor.py:857`): dla mapy ze `stanowisko` pomijamy `stoi_min` i `brak_zabic_min`; zastępujemy je kontrolą „brak runy”: mana >= koszt, blanki w plecaku, brak obcych w widoku, a od `brak_runy_min` (proponowane 40 min) nie przybyło run -> naprawa z drabiny (wznów, restart), nie STOP. Telemetria starsza niż 120 s nadal oznacza zawieszenie.
- `eskalacje_z_logu` (PK, GM, zgon) bez zmian; dodajemy tylko, że po ucieczce do PZ nadzorca nie restartuje bota w karencji.
- Zmiana poziomu 11: grafik/Karol przełącza `runy` -> `uh` na następnej zmianie (jak dziś `tryb` w zmianie); automat poziomu to osobna rzecz (Poza zakresem).
- `spoty_nadzorca.json`: wpis `stoj_runy_<miasto>` z `poziom` [11, 999] albo [3, 999] dla wariantu HMM, `jaskinia` brak, `auto: false`, dopóki Karol nie zdecyduje o samodzielnym wyborze (nadzorca dziś wybiera spoty wg tej tabeli, `SPEC_wybor_spotu_1021.md`).

## Pliki (wszystkie w repo bota, poziom 1; zmiany dopiero po zatwierdzeniu)

- `cavebot.py` (STANOWISKO_*, wyjątek watchdoga, zachowanie jedno-punktowe w `_idz_trasa`, cel ucieczki PK = `pz`, filtr NPC/gracz w wywołaniu `uh.mozna_robic`), `uh.py` (parametr „ignoruj_npc/odl_gracza”), `pokretla.py` (`ZAKRESY`, ograniczenia), `mozg.py` (odczyt `stanowisko` z mapy; bez `--bez-ruchu`).
- Dane: `mapy.json` (2 wpisy), `tryby.json` (tryb `stoj`), `trasy/stoj_runy_<miasto>.json` (+ `.meta`), `dane_tibia/spoty_nadzorca.json`, `miejsca_koord.py` (klucz).
- `nadzor.py` (wyjątek w `zaciecie`; `NADZORCA.md` - opis wyjątku).
- Testy: `testy/test_stoj_runy.py` (nowy).

## Testy i weryfikacja

Offline (atrapy, `RETRONIC_TESTY=1`, wzorzec `testy/test_patrol_edron.py`, `testy/test_cavebot.py`):
1. Na jedynym punkcie trasy nie powstaje log okrążenia; pozycja bez zmian przez 120 s nie uruchamia watchdoga przy `STANOWISKO=1`, a przy `STANOWISKO=0` zachowanie bez zmian (test regresji).
2. `uh.mozna_robic`: NPC w widoku nie blokuje przy `STANOWISKO_NPC_IGNORUJ=1`; gracz w widoku blokuje przy `STANOWISKO_GRACZ_ODL=0`; domyślne wywołanie (bez nowych parametrów) daje wynik jak dotąd.
3. Obrona: atak gracza, czaszka, GM, HP < `STANOWISKO_HP_PZ`, „bot?” prowadzą do stanu PZ_OBRONA z celem `pz`; karencja; powrót na pole dopiero po karencji i bez wroga w widoku.
4. Wyzwalacze serwisu: brak blanków, hamu < 5, wolnych slotów < 2 każdy osobno -> plan serwisu z `--na-sucho` (Edron i Thais) kończy się na polu stanowiska (droga powrotna istnieje, `mapa.droga`).
5. Nadzorca: mapa ze `stanowisko` nie dostaje diagnozy „stoi w miejscu”/„brak zabić”; brak runy 40 min daje naprawę z drabiny, nie STOP; mapa bez `stanowisko` bez zmian.
6. Koordynator: dwa wnioski o `stoj_edron` = drugi odrzucony; różne miasta oba przyjęte; zwolnienie po martwym pid.
7. Walidacja: `pokretla.waliduj` odrzuca wartości poza zakresem, analityk nie osłabia `STANOWISKO_HP_PZ`.
8. Higiena: `git diff --check`, brak numerów kont/danych sesji w zmianach.

Na żywo (jedno wywołanie, za zgodą Karola, jeden bot, ustawienia przywrócone po próbie):
- F0: pomiar PZ i ruchu graczy na kandydatach (bez bota), pomiar regeneracji many (pyt. 5).
- F1: jedna postać w jednym mieście: stanie 30-60 min, minimum 3 rzuty runy, jedzenie hamu, jeden pełny serwis i powrót, jedno wejście do PZ wywołane bezpiecznie (np. polecenie obrony na sucho), log + telemetria jako dowód.

## Kryteria akceptacji (weryfikowalne)

1. W logu 60-minutowej próby: >= 3 wpisów rzutu runy z przyrostem run w plecaku (odczyt pamięci), >= 1 `zjedz` po głodzie, 0 wpisów „Watchdog: bezczynność”, 0 restartów przez nadzorcę z powodu „stoi”.
2. Postać stoi na polu z `pola`/`trasa` i `STANOWISKO=1` (telemetria: pozycja stała poza serwisem i obroną), w mieście zgodnym z mapą, **poza PZ** (potwierdzone pomiarem Karola, nie hipotezą).
3. Serwis wywołany brakiem blanków kończy się wynikiem `OK`, plecak ma blanki i ham, a postać wraca na pole w <= 10 min od wyjścia z serwisu (czas z logu).
4. Zagrożenie (test na sucho obrony) wprowadza postać na pole `pz` w <= 10 s od wykrycia i wysyła krytyczne powiadomienie; po karencji i bez wroga wraca na pole.
5. W jednym mieście nigdy dwie nasze postacie w trybie stanowiska (test Koordynatora + log nadzorcy).
6. Brak STOP z powodu braku postępu; jedyne STOP-y: PK/HP/śmierć lub `STOP_RECZNY`.
7. Żadne istniejące zachowanie (inne mapy i tryby) nie zmienia się: istniejący zestaw `testy/` przechodzi bez modyfikacji oczekiwań.

## Ryzyka

- **PZ nieznane** - jeśli pole jest w PZ, mana nie rośnie i tryb jest bezużyteczny; jeśli dalej od PZ niż założono, ucieczka trwa dłużej. Stąd pomiar F0 przed kodem.
- **Zabijanie postaci poza PZ** (zasada „życie postaci”, `CLAUDE.md`): stanie poza PZ podnosi ryzyko wobec dzisiejszego stania w depo. To zmiana podnosząca ryzyko, dlatego F1 dopiero po „tak” Karola; do tego `STANOWISKO_GRACZ_ODL` i inne luzowanie bezpieczeństwa bez zgody nie wchodzi.
- **UH zagłodzone przez widok miasta** (luka 5): jeśli blokady są zbyt częste, tryb produkuje mało; wtedy wybrać inne pole (2-3 kandydatów) zamiast luzować blokadę.
- **Serwis Thais** (drzwi, sklepy daleko od depo ok. 50 pól) i **Edron** (Alexander ok. 80 pól) = długie wyprawy poza polem; w czasie marszu postać jest bez PZ.
- **Wyrzucenie za bezczynność** (UNKNOWN); nadzorca naprawi relogiem (`SPEC_rozlaczenie_1021.md`), ale częste relogi też wyglądają podejrzanie.
- **Stanie w jednym miejscu** zwraca uwagę graczy i GM (obawa Karola): rotacja pól i krótsze zmiany, ale ryzyko zostaje.
- **Koszt**: UH to 100 many i 1 ładunek (blank 10 gp); wartość run bez sprzedaży (pyt. 2) to tylko zapas własny.

## Fazy

- **F0 (bez bota, za zgodą):** pomiar PZ na kandydatach, ruchu graczy, regeneracji many i bezczynności serwera; wpis `pola`/`pz` do `mapy.json`. Wynik: zatwierdzone pola.
- **F1 (poziom 1 w repo bota, potem jedno wywołanie na żywo):** kod + testy offline (1-7), jedna postać, jedno miasto (rekomendacja: Edron, bo serwis Edron jest kompletny na żywo od 19.10), próba 30-60 min.
- **F2:** drugie miasto (Thais) po dowodzie serwisu z drzwiami; wyjątek nadzorcy; wpis `spoty_nadzorca.json`.
- **F3:** rotacja pól/godzin w grafiku, automat `runy` -> `uh` przy poziomie 11, ewentualnie odczyt PZ z pamięci.
Każda zmiana działającego bota/konfiguracji to osobna zgoda; commit/merge wyłącznie na polecenie.

## Czego nie zmierzono na żywo (UNKNOWN)

- Granica PZ w Edronie i Thais; ruch graczy na kandydatach.
- Czy rzut czaru zeruje licznik bezczynności serwera i jaki to limit.
- Tempo regeneracji many poza PZ z hamem (Karol: w PZ nie rośnie; poza PZ brak pomiaru).
- Jak często gracze/NPC blokują rzut w widoku miasta.
- Pełen przebieg serwisu Thais z drzwiami (od depo do wyjścia) i powrót na pole.
- Czy `adura vita` od 11 działa zgodnie z `czary.json` na żywym serwerze (dane serwera mówią tak, `uh.py:39` mówi 24).

## Do decyzji Karola (każde z rekomendacją)

1. **Konkretne pola stania.** Edron: E1 (33170,31819,7), E2 (33171,31820,7), E3 (33175,31819,7); Thais: T1 (32346,32229,7), T2 (32349,32229,7), T3 (32347,32228,7) - to propozycje z mapy, granicy PZ nie znamy. *Rekomendacja:* w F0 stań na każdym z nich i powiedz, czy to PZ; zostaw 2-3 poza PZ najbliżej PZ jako `pola`, a pole w PZ tuż obok jako `pz`. Czy wolisz stanie przy świątyni (Edron (33217,31814,8), Thais (32369,32241,7)) zamiast przy depo?
2. **Co z gotowymi runami: sprzedaż czy tylko depo?** W danych serwera żaden NPC nie kupuje run od gracza (`npc_pelne.json`: u Alexandra i Xodeta `gracz_sprzedaje_npc` bez run). *Rekomendacja:* tylko depo (krok `depo` w serwisie), bez sprzedaży w F1-F2; sprzedaż graczom to osobny tor (`stoj_trade`).
3. **Ile godzin dziennie na postać?** Grafik pozwala dziś na 480 min. *Rekomendacja:* stanowisko max 6 h/dobę na postać (zmiany 2-3 h, przerwy 7-25 min z wylogowaniem, ciche godziny 01:00-08:00 bez zmian), bo stanie w jednym miejscu jest bardziej widoczne; rotacja pól między zmianami.
4. **Czy w F1 zgadzasz się na stanie poza PZ?** To podnosi ryzyko śmierci postaci względem depo. *Rekomendacja:* tak, ale tylko postać o niskiej wartości (np. nowa na poziomie 11-15), jedna na miasto, pierwsza próba z Tobą przy komputerze.
5. **Jak mierzyć regenerację many poza PZ?** *Rekomendacja:* pasywnie z telemetrii (zapis many co kilka sekund przy wolnej postaci z hamem w F1), bez dodatkowych kliknięć; wynik wpisać tu przed F2.
6. **Jak ocenić ruch graczy na polu?** *Rekomendacja:* 15 minut obserwacji w F0 (liczba obcych graczy i NPC w widoku z `stwory`), pole z największym ruchem odrzucić.
7. **Bezczynność serwera (idle-kick).** Nie wiemy, czy rzut czaru zeruje licznik. *Rekomendacja:* nie dodawać sztucznych ruchów w F1 (`STANOWISKO_AKTYWNOSC_MAX_S=0`); jeśli w próbie nastąpi rozłączenie, nadzorca zrobi relog, a my wpiszemy `STANOWISKO_AKTYWNOSC_MAX_S` na podstawie zmierzonego czasu.
8. **Które miasto pierwsze?** *Rekomendacja:* Edron (serwis kompletny i sprawdzony na żywo 19.10), Thais w F2.
9. **Pytanie „bot?” od gracza.** Dziś tylko dymek i przejęcie przez Ciebie. *Rekomendacja:* poza PZ dodatkowo wejście do PZ do czasu Twojej odpowiedzi (zgodnie z punktem 2 Twojej propozycji), z krytycznym powiadomieniem.
10. **Przełączenie `runy` -> `uh` na poziomie 11.** *Rekomendacja:* ręcznie przez wpis `tryb` w grafiku na następnej zmianie (F1-F2), automat dopiero w F3.
