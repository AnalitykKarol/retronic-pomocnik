# SPEC: ręczne wywołanie powrotu do miasta („Wróć do miasta”) - 19.10 — ZATWIERDZONA do implementacji (Karol 19.10: „puść agenta niech robi”; trasa goblinów -> Edron była wielokrotnie przechodzona)

Cel: Karol może w dowolnej chwili kazać botowi wrócić do miasta (depo), bez czekania na głód albo brak zapasów i bez
przepinania pokręteł w `na_zywo.json`. Dziś jedyne wyzwalacze wyprawy są automatyczne (jedzenie, głód, blanki, pochodnie),
a akcja modelu `wroc_do_miasta` jest atrapą (`mozg.py` ~2673: loguje i woła człowieka). 19.10 Mastafian (zero jedzenia,
`WYPRAWA_CZEKAJ_NA_GLOD=1`) nie ruszył do Edronu mimo gotowego planu `gobliny_edron`.

## Decyzje Karola (19.10)

1. **Wyzwalacz:** polecenie `./wroc.sh` **i** guzik „Wróć do miasta” w wtyczce paska `charlie.retronic` (obok Stop/Start).
   Jedno wspólne źródło prawdy: plik `WROC` w katalogu stanu instancji (`$INST_STAN/WROC`).
2. **Cel:** bot dochodzi do pola depo i **staje** (plik STOP, powiadomienie). Dalej Karol: `./serwis.sh` albo ręcznie.
   Bez zakupów, bez powrotu na spot (zachowanie `WYPRAWA_TYLKO_DEPO` dla tej jednej wyprawy, nie jako pokrętło globalne).
3. **Moment:** w najbliższej spokojnej chwili (jak każda wyprawa: po walce i locie, `_blokada_startu`). Ucieczka przy niskim HP
   zachowuje pierwszeństwo przed wyprawą (jak dotąd `WYPRAWA_MIN_HP`).

## Stan dzisiaj (zmierzone 19.10, kod)

- `wyprawa.py`: `_okazja_wyprawa()` (wyzwalacze) -> `_start_wyprawa(powód, dane, teraz)`; plany `PLANY_PK` (`edron`,
  `gobliny_edron`) wybierane po położeniu postaci; `wypad.PLANY` (`rook`, `troll`, `thais_kanaly`) służą wypadowi po zapasy, a tryb
  depo ich nie używa (`BAZY_PK` nie ma `rook`: ręczne wywołanie z Rookgaardu kończy się komunikatem o braku planu, korekta po przeglądzie 19.10); stan wyprawy w
  `wyprawa_stan.json` (restart wznawia); STOP / STOP_RECZNY / ALARM_GM przerywają.
- Maszyna jest już per instancja (`bot.STOP.with_name(...)`, `INST_STAN`), więc plik `WROC` obejmie `test` i główną osobno.

## Zachowanie

- `WROC` istnieje i bot działa: przy najbliższym obiegu `_okazja_wyprawa` pomija wymagania „powody + POTWIERDZENIE” i cooldown
  (`nast_wyprawa`), zostawia **wszystkie bezpieczniki** (zablokowany/PK, `_blokada_startu`, HP, pozycja znana, plan pasuje do piętra).
  Startuje `_start_wyprawa("depo:reczny", dane, teraz)` w semantyce „tylko depo”; plik `WROC` jest usuwany **po** ruszeniu.
- Brak planu dla miejsca postaci, albo blokada trwa > `WROC_BLOKADA_MAX_S` (domyślnie 180 s): log + powiadomienie
  „Wróć do miasta: nie mogę ruszyć (powód)”, plik `WROC` usuwany (bez ponawiania po cichu).
- Wyprawa po ręcznym wywołaniu działa także przy `WYPRAWA_AKTYWNA=0` (otwarte: czy obiekt `Wyprawa` istnieje bez tego pokrętła;
  sprawdzić i w razie potrzeby tworzyć go, gdy jest `WROC`).
- Anulowanie: `./wroc.sh --anuluj` (usuwa `WROC`, jeśli wyprawa jeszcze nie ruszyła); w trakcie marszu: zwykły STOP.
- `./wroc.sh` odmawia, gdy bot tej instancji nie działa (nie ma kto wykonać) i pisze, jak uruchomić; `RETRONIC_ID` wybiera instancję.
- Dojście: ta sama trasa, co automatyczna wyprawa do depo (nagrane „do” + A*), z linami/dziurami wg mapy.

## Pliki

- `wyprawa.py`: odczyt `WROC` w `_okazja_wyprawa` (+ stała `WROC_BLOKADA_MAX_S`), flaga „depo na jedną wyprawę”.
- `wroc.sh` (nowy), w stylu `zatrzymaj.sh`. `CLAUDE.md` bota: jedna linia o poleceniu.
- Wtyczka paska (repo omarchy, `plugins/charlie.retronic/`): guzik woła `wroc.sh` z `RETRONIC_ID` instancji (dziś guziki
  Stop/Start); zmiana w repo to poziom 1, **instalacja w `~/.config` (faza 3 specyfikacji wtyczki) to poziom 2, osobna zgoda**.

## Testy i weryfikacja

1. Jednostkowe w `testy/` (atrapy jak w `test_wyprawa*`): `WROC` startuje wyprawę „depo:reczny” w spokoju i przy `WYPRAWA_AKTYWNA=0`;
   nie startuje w walce, przy niskim HP i przy PK (plik zostaje do czasu, potem komunikat po limicie); plik znika po starcie;
   plan wybierany po położeniu (`gobliny_edron`, `troll`; `rook` = odmowa z komunikatem); po dojściu STOP + powiadomienie, bez zakupów; `--anuluj`.
2. Test dymny na sucho: `./wroc.sh` na instancji bez bota (odmowa) i z botem na atrapie.
3. **Test na żywo** (osobna zgoda Karola, bot obserwowany): Mastafian z jaskini goblinów do depo Edron; kryterium: dojście bez
   utknięcia, STOP w depo, powiadomienie, zero akcji w mieście.
4. Niezależny przegląd (checker) zmian w `wyprawa.py` przed testem na żywo.

## Poza zakresem

- Zakupy/serwis po dojściu i powrót na spot (osobny krok; `serwis.sh` czeka na test na żywo).
- Akcja modelu `wroc_do_miasta` (zostaje atrapą; Haiku nie wysyła bota samodzielnie bez osobnej decyzji).
- Nowe trasy; używamy istniejących planów.

## Ryzyka

- Plan `gobliny_edron` (lina z8->z7, dojście do depo 182 pkt) był wielokrotnie przechodzony ręcznie i przez bota (Karol 19.10), ale
  ręczny wyzwalacz uruchamia go pierwszy raz: bezpieczniki wyprawy (alarm + STOP w miejscu) działają, postać może stanąć w drodze.
- Przycisk w pasku może być wciśnięty przez pomyłkę w trakcie walki: bot ruszy dopiero w spokojnej chwili, a `--anuluj` cofa.

## Fazy

- F1: `wyprawa.py` + `wroc.sh` + testy (poziom 1, repo bota). F2: test na żywo (zgoda). F3: guzik w pasku (repo) i jego
  instalacja (poziom 2, zgoda).

## Rozszerzenie 20.10: marsz klikiem i auto-refill (polecenie Karola 20.10; DWA POKRĘTŁA, domyślnie 0 = zachowanie sprzed zmiany)

Cel: powrót do miasta ma być płynny. (A) w drodze do depo postać idzie klikiem w mapę (klient prowadzi ją ciągiem), (B) po dojściu do
depo bot sam startuje refill, zamiast stawać i czekać na ręczne `refill.sh` / guzik. Kod: `marsz_klik.py` (wspólne klocki), `wypad.py`
(`_marsz_klik`), `refill_auto.py` (decyzja + czekacz), `wyprawa.py` (`_zakoncz_depo`), `panel.py` (pole), `wroc.sh`/`refill.sh` (anulowanie).
Stałe w `cavebot.py`, zakres i kierunek (analityk nie włączy) w `pokretla.py`.

### A. `WYPRAWA_MARSZ_KLIK` (0/1, `na_zywo.json`)

- **Gdzie:** `Wypad._idz_faza`, TYLKO faza `do` (droga do miasta/depo: „Wróć do miasta” i każda wyprawa), przed `cb._idz_odcinek`. Klik dotyczy
  jednego odcinka (etapu IDZ) na jednym piętrze; postać musi stać na punkcie odcinka (inaczej zostają dotychczasowe kroki).
- **Reguła kliku (klocki `marsz_klik.py`; serwis nadal używa swojej gęstej Dijkstry i działa jak dotąd):** ścieżka kliku to GĘSTA ścieżka odcinka:
  kolejne pola sąsiednie (nagrania bywają rzadkie, co 2+ pola: luki uzupełnia linia prosta), to samo piętro, do 5 pól naprzód (`KLIK_MAKS_POL`, liczone
  w POLACH, nie w punktach nagrania) i w zasięgu widoku (|dx| ≤ 6, |dy| ≤ 4, klik poza widokiem nie jest wołany). Każde pole ścieżki musi być zwykłe wg
  mapy (bez blokady, schodów/dziur, bez pola z flagą 2 także bez odpowiednika, np. krzesło = koszt 6), wolne (bez ognia, bez stworów i graczy; widma i wpis
  własny pomijane). Obszar kontrolny: prostokąt obejmujący postać i WSZYSTKIE pola ścieżki do celu kliku z marginesem 1 pola nie może zawierać pola z flagą 2
  ani ognia ani dziury/zmiany piętra znanej Cavebotowi (klient wybiera własną drogę i przy obejściu przeszkody ma objazdy po obu stronach, więc znana dziura
  przy depo (33167,31812,z7), omijana przez nagranie, blokuje klik w okolicy); inaczej ścieżkę skracamy, < 2 pola = kroki jak dotąd. Mob (nie gracz) w 3
  polach od postaci albo w 2 polach od pola ścieżki = bez kliku albo skrócenie; groźny gracz (GM/czaszka) w widoku, `ucieczka`, `ostrozny` = bez kliku.
  Na prawdziwych planach (bez stworów): troll 119/197, gobliny_edron 136/182, edron 80/117 pozycji ma dozwolony klik, 0 naruszeń prostokąta.
- **Po kliku:** czekanie na ruch jak w serwisie (do 0,8 s + 0,45 s na pole); co 3. odczyt kontrola: mob w 3 polach, groźny gracz albo spadek HP o
  > 5 pp = przerwanie (Escape, obieg oddany; walka/ucieczka/PK idą dotychczasową logiką w następnym obiegu, kolejny klik najwcześniej po 3 s).
  Zmiana piętra = przerwanie obiegu (dalej `_resync` / etap przejścia). Klik bez ruchu = powrót do kroków i 8 s przerwy w klikach. Limit czasu 0,8 s + 0,45 s
  na POLE ścieżki; klik odrzucony (poza widokiem) = 3 s przerwy.
- **Cofnięcie:** `WYPRAWA_MARSZ_KLIK=0` (albo usunięcie z `na_zywo.json`). Przy 0 ścieżka jest identyczna jak przed zmianą (test 20r).
- **Czego nie obejmuje:** faza `z` (powrót na spot), dojście do planu drogą patrolu (`WYPRAWA_DOJSCIE_PATROLEM`), przejścia pięter (lina, dziura,
  drzwi), sklepy, patrol i walka w `cavebot.py` (osobna gałąź `feat/marsz-klik-patrol`, pokrętło `MARSZ_KLIK`: tam `not self.wypad_aktywny`, więc
  oba pokrętła się nie nakładają).

### B. `WROC_REFILL` (0/1, `na_zywo.json`)

- **Które powroty obejmuje:** każdy powrót, który kończy się w `Wyprawa._zakoncz_depo(wynik="depo")`, czyli STOP w depo: ręczne `./wroc.sh` ORAZ
  automatyczna wyprawa w trybie `WYPRAWA_TYLKO_DEPO=1` (głód, brak blanków). Powód: to jedno miejsce, w którym bot staje w depo i dziś czeka na
  człowieka; refill kupuje dokładnie to, czego te wyprawy brakuje (jedzenie, blanki). Nie obejmuje: ucieczki PK, awarii (utknięcie, limit czasu,
  teleport), `WYPRAWA_DEPO_POWROT=1` (tam bot sam wraca na spot, bez STOP).
- **Mechanizm:** `refill_auto.zlec()` (decyzja przy STOP) → odłączony czekacz `refill_auto.py czekaj` → czeka, aż proces bota tej instancji zniknie
  (`refill.sh` odmawia przy działającym bocie; bot sam wychodzi po STOP, na żywo ta sama sekunda) → ponownie sprawdza STOP_RECZNY i serwis →
  `zwolnij_wejscie.py` → `refill.sh --tlo` (jedzenie, backpack, blanki, wyjście, `STARTUJ=1` startuje bota na spot; log `refill.log`).
  Limit czekania na zatrzymanie bota 60 s (potem rezygnacja z wpisem, nic nie jest ubijane).
- **Pierwszeństwo człowieka i warunki odmowy** (wszystko ląduje w `wroc_refill.json` instancji z powodem; bot i tak stoi w depo jak dotąd):
  `STOP_RECZNY` (guzik Stop, `zatrzymaj.sh`, `refill.sh --przerwij`) = bez auto-refillu; serwis / praca `refill.sh` / czekacz już działa = bez drugiego;
  postać nie stoi przy depo = bez; błąd startu czekacza = bez (STOP zostaje).
- **Anulowanie:** `./wroc.sh --anuluj` (usuwa zlecenie ORAZ oczekującego czekacza: „auto-refill anulowany”; gdy czekacz już wołał `refill.sh` albo refill trwa:
  „refill już ruszył: ./refill.sh --przerwij” i nic nie ubija), `./refill.sh --przerwij` (ubija czekacza, potem jak dotąd).
- **Cooldown:** auto-refill nie rusza, jeśli poprzedni ruszył mniej niż 20 min temu (`COOLDOWN_S`, `ostatni_start` w `wroc_refill.json`): pętla wyprawa → depo → refill.
- Anulowanie ręcznego zlecenia przed ruszeniem (plik WROC) nic nie uruchamia, bo wyprawa nie doszła do depo.
- **Miasto bez planu serwisu:** plan serwisu ma tylko Edron (`trasy/serwis_edron.json`, `serwis.py` przyjmuje wyłącznie `edron`). Miasto ocenia się po
  położeniu postaci tak jak pole panelu `w_miescie`. Poza Edronem: `stan: brak_planu`, wpis w logu bota („auto-refill pominięty: brak planu serwisu…”), dymek
  „Wróć do miasta: bez auto-refillu”, pole `wroc_refill: "brak_planu"` w panelu; nic innego nie jest zatrzymywane ani zmieniane.
  **Johny Dang** (instancja `test`, trolle przy x≈32480, y≈32290) ma plan wyprawy `troll` → depo Thais (początek `depo_troll_cave.json`, (32348,32225,z7)),
  a Thais NIE ma planu serwisu (zmierzone: `panel.miasto_pozycji` → brak miasta, test 20zd i 2d): jego powrót kończy się STOP-em w depo jak dotąd,
  z wpisem „brak planu”. Auto-refill dla Thais wymaga osobnej specyfikacji serwisu (NPC, depo, trasy).
- **Cofnięcie:** `WROC_REFILL=0`. Pliki: `wroc_refill.json` w katalogu stanu (kasowany ręcznie, panel pokazuje go tylko do następnego startu bota).
- **Ryzyko:** po refillu bot rusza na spot (`STARTUJ=1`); jeśli zakupy się nie powiodły, wyprawa po `WYPRAWA_PO_DEPO_S` (900 s) może znów wrócić do depo i
  refill ruszy znowu najwcześniej po cooldownie 20 min (pętla co >= 20 min); `REFILL: BLAD` zostawia STOP, wtedy pętli nie ma.

### C. `panel.py --json` (addytywnie)

`wroc_refill`: `null` | `"czeka"` (czekacz żyje, bot się zatrzymuje) | `"trwa"` (refill ruszył, serwis działa) | `"pominiety"` | `"brak_planu"`;
`wroc_refill_komunikat`: powód (do 200 znaków). Wynik samego refillu zostaje w `serwis_wynik` / `serwis_komunikat`. Pominięty/brak planu zostają widoczne do następnego STARTU bota (żywy proces bota nowszy niż decyzja), a nie do pierwszej linii logu bota.

### Testy i weryfikacja

`testy/test_wyprawa.py` sekcja 20 (marsz klikiem: tylko zwykłe pola, przerwania, brak ruchu, faza `do`; decyzje auto-refillu: raz po dojściu, nie przy
STOP_RECZNY / działającym serwisie / mieście bez planu / nieudanym dojściu / błędzie startu), `testy/test_wroc_refill_auto.py` (klocki, czekacz, panel,
`refill.sh --przerwij` i `wroc.sh --anuluj` w atrapie). **Niezweryfikowane na żywo** (wymaga zgody i obserwacji): klik w mapę w drodze do depo (zachowanie
klienta na schodach/liniach, skuteczność kliku po ręcznym zatrzymaniu), pełny łańcuch STOP → czekacz → `refill.sh` → refill z prawdziwym serwisem.
