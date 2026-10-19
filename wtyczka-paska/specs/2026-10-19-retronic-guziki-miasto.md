Status: draft do przeglądu prowadzącego; logika i testy gotowe w worktree (19.10), instalacja w `~/.config` = poziom 2, osobna zgoda
Weight: Feature (mała, rozszerza spec `2026-10-19-retronic-wtyczka-paska.md`)
Projekt: Retronic, zarządzanie instancjami z paska Omarchy

# Guziki „Wróć do miasta”, „Refill” i „Spot” we wtyczce `charlie.retronic`

## TLDR

Obok `■ Stop` / `▶ Start` każdy wiersz instancji dostaje trzy guziki: `⌂ Miasto` (bot idzie do depo i staje), `↻ Refill`
(zakupy w mieście i powrót na spot) i `↗ Spot` (dodany 19.10 wieczorem: z miasta na spot bez zakupów). Cel Karola (19.10): cały cykl **spot → miasto → refill → spot** idzie spod guzików, bez
terminala. Wtyczka dalej jest cienka: stan liczy czysta logika (`RetronicModel.js`), a robotę robią skrypty bota
(`wroc.sh`, nowy `refill.sh` jako opakowanie `serwis.sh`).

## Zachowanie (stany per instancja)

Wszystko osobno dla każdej instancji (`RETRONIC_ID`), nic wspólnego między wierszami. Pola stanu pochodzą z `panel.py --json`
(nowe, opcjonalne; stare pola bez zmian).

### `⌂ Miasto` (woła `RETRONIC_ID=<id> ./wroc.sh`)

| Warunek (po kolei, pierwszy pasujący) | Guzik | Powód (pod myszą) |
|---|---|---|
| brak odczytu | szary `⌂ Miasto` | brak odczytu |
| `panel.py` bez pól miasta (stary) | szary | panel.py bez danych o mieście |
| serwis w toku | szary | serwis w toku |
| bot nie działa / brak gry | szary | bot nie działa / gra nie działa |
| bot idzie do depo (ręczna wyprawa aktywna) | szary `w marszu…` | bot idzie do depo (zatrzymanie: ■ Stop) |
| jest plik `WROC`, bot jeszcze nie ruszył | żółty `✕ Anuluj` (`wroc.sh --anuluj`) | cofa zlecenie, dopóki bot nie ruszył |
| postać już w strefie miasta | szary | postać już jest w mieście |
| pozycja nieznana | szary | pozycja postaci nieznana |
| brak planu depo dla pozycji (np. Rookgaard) | szary | brak planu depo dla tej pozycji |
| bot działa, plan depo jest | **zielony `⌂ Miasto`** | bot dojdzie do depo w najbliższej spokojnej chwili i stanie |

Linia stanu pod wierszem: `czeka na spokojną chwilę` (WROC jest) → `w marszu do depo` → po dojściu (bot stoi, postać przy
polu depo) `w depo, bot stoi`; w mieście poza depo `w mieście, bot stoi`.
Po dojściu bot sam staje (plik STOP, dymek: robi to `wyprawa.py`, spec `SPEC_wroc_do_miasta_1019.md`).
Odmowy `wroc.sh` (bot nie działa) pokazują się jak przy Stop/Start (krótki komunikat w wierszu, gaśnie po 8 s).

### `↻ Refill` (woła `RETRONIC_ID=<id> ./refill.sh --tlo`)

`refill.sh` = `STARTUJ=1 ./serwis.sh --kroki jedzenie,backpack,blanki,wyjscie` (kroki **bank i depo POMIJAMY**, decyzja
Karola 19.10: po „Wróć do miasta” zasoby są już w depo). Odłączony od wtyczki (`setsid -f`), log w
`instancje/<id>/refill.log` (główna: `refill.log` w katalogu pomocnika); po sukcesie `STARTUJ=1` startuje bota na spot
ostatnią mapą i trybem.

| Warunek | Guzik | Powód |
|---|---|---|
| brak odczytu / stary `panel.py` | szary `↻ Refill` | jak wyżej |
| **serwis w toku** (`serwis.py` albo praca `refill.sh` tej instancji) | **czerwony `■ Przerwij`** (`refill.sh --przerwij`) | przerywa serwis i zatrzymuje bota (STOP) |
| brak gry | szary | gra nie działa |
| `alarm` | szary | alarm: poczekaj, aż minie |
| bot działa | szary | najpierw zatrzymaj bota |
| postać poza strefą miasta | szary | postać jest poza miastem (najpierw ⌂ Miasto) / pozycja nieznana |
| bot stoi, postać w mieście z planem serwisu, serwis nie działa | **zielony `↻ Refill`** | zakupy w mieście (bez banku i depo), potem bot rusza na spot |

Linia stanu: `serwis w toku (krok: jedzenie|plecak|blanki|wyjście)`; krok z `refill.log` (`serwis: krok X`).
**Przerwij** (`refill.sh --przerwij`, procesy rozpoznawane po `RETRONIC_ID` w `/proc`, jak `pidy` w `instancja.py`), kolejność:
1. TERM tylko dla `refill.sh` i `serwis.sh` (żeby nie wystartował bota); **nie** dla `serwis.py` i bez grupy procesów;
2. plik STOP (+ STOP_RECZNY) i czekanie do 5 s (`REFILL_CZEKAJ_STOP_S`), aż `serwis.py` sam wyjdzie: każda akcja myszy woła
   `bot.sprawdz_stop()`, więc rzuca `Zatrzymano`, a `finally` w `ekran.py` puszcza przycisk/modyfikator (SIGTERM/KILL by go ominął);
3. dopiero potem TERM, na końcu KILL dla `serwis.py`, który nie wyszedł;
4. `./zatrzymaj.sh` (bot mógł zdążyć wystartować) i **zawsze** `zwolnij_wejscie.py` (ButtonRelease 1/3, KeyRelease Control/Alt/Shift
   i strzałki/numpad na ekranie gry instancji; `zatrzymaj.sh` przy braku bota nic nie puszcza i robi `exit 0`).
Jeśli nic nie biegło (żaden `refill.sh`/`serwis.sh`/`serwis.py` tej instancji: np. klik w „Przerwij” sprzed odświeżenia statusu po udanym
Refillu, gdy bot już wystartował) → `nic do przerwania`, **bez STOP** i bez `zatrzymaj.sh`: świeży bot nie jest ubijany.
Znane: po przerwaniu `serwis.py` zgłasza dymek „Serwis: porażka” (jego `except` na `Zatrzymano`; `serwis.py` poza zakresem).
Po przerwaniu bot stoi, a Refill jest znów aktywny: ponowny klik **wznawia** serwis (kroki już zrobione pomijane), ale tylko gdy stan
serwisu jest młodszy niż 15 min (`REFILL_WZNOW_MIN`); starszy `refill.sh --tlo` kasuje przy starcie (inaczej po cichu pominąłby
zakupy, bo `serwis.py` wznawia do 3 h).

Porażka: `refill.sh` zapisuje w logu `REFILL: BLAD <powód>` (powód = linia `SERWIS: PORAŻKA w kroku X: …`), serwis zostawia plik
STOP, a wiersz pokazuje czerwoną linię `błąd: <powód>` (do godziny, dopóki bot stoi). Nic nie ponawia się po cichu; kolejna próba
to świadomy klik. Błąd znika po starcie bota albo nowym refillu: `panel.py` oddaje `serwis_wynik: null`, gdy któryś
`logi/mozg-stdout-*.log` (tworzy go `uruchom.sh` przy każdym starcie) jest nowszy niż `refill.log`, więc nie wraca także po późniejszym
Stopie. (Wybrane zamiast znacznika dopisywanego przez `uruchom.sh`: nie wymaga zmiany `uruchom.sh` ani działa przy starcie z terminala.)
Krok serwisu pochodzi z linii `serwis: krok X` w `refill.log`; fallback ze `serwis_stan.json` tylko dla serwisu puszczonego z terminala.

### `↗ Spot` (woła `RETRONIC_ID=<id> ./refill.sh --spot`)

Semantyka (ustalona na żywo 19.10): „na spot” z miasta = `STARTUJ=1 ./serwis.sh --kroki wyjscie`: serwis prowadzi postać do wyjścia z
miasta (33167,31815,z7), po sukcesie `STARTUJ=1` uruchamia bota ostatnią mapą i trybem; `uruchom.sh` dodaje dojście na spot tylko wtedy,
gdy postać stoi na z7 (stąd krok `wyjscie`; sam `▶ Start` robi to tylko z z7). Wybrane **`refill.sh --spot`** zamiast samego
`REFILL_KROKI=wyjscie`: ten sam odłączony proces, ten sam `refill.log`, to samo `--przerwij`, te same markery i obsługa błędów
(`REFILL: START <czas> spot`, więc panel wie, że to „spot”, a wtyczka pisze „idę na spot…”); jedno wywołanie bez znajomości
zmiennych środowiskowych po stronie wtyczki. `--spot` = `REFILL_KROKI=wyjscie` + `REFILL_TRYB=spot` i dalej jak `--tlo`.

| Warunek | Guzik | Powód |
|---|---|---|
| brak odczytu / stary `panel.py` | szary `↗ Spot` | jak wyżej |
| **serwis w toku** | szary; przy `--spot` z napisem `idę na spot…` | serwis w toku / postać idzie do wyjścia z miasta (■ Przerwij po lewej) |
| brak gry / `alarm` | szary | gra nie działa / alarm: poczekaj, aż minie |
| bot działa | szary | najpierw zatrzymaj bota |
| postać poza strefą miasta | szary | już poza miastem: użyj ▶ Start / pozycja postaci nieznana |
| bot stoi, postać w mieście z planem serwisu, serwis nie działa | **zielony `↗ Spot`** | bez zakupów: postać wychodzi z miasta, potem bot rusza na spot |

- Jedno wspólne **`■ Przerwij`**: w trakcie serwisu (Refill albo Spot) zajmuje miejsce `↻ Refill`, `↗ Spot` jest wtedy szary (nie dubluje).
  Przerwanie i wznowienie jak przy Refillu (STOP, ponowny klik, stan serwisu do 15 min).
- Linia stanu: `idę na spot… (krok: wyjście)`; porażka `błąd: <powód>` i jej znikanie po starcie bota dokładnie jak przy Refillu
  (wspólny `refill.log`); po sukcesie bot działa, więc guzik szarzeje.
- Odchylenie od zlecenia: oczekujący `WROC` przy STOJĄCYM bocie traktuję jak nieaktualny (wroc.sh odmawia bez bota, `serwis.sh` i
  `uruchom.sh` go kasują), więc nie blokuje Spotu.
- Układ: trzy guziki w jednym rzędzie pod wierszem (3 × 96 px + odstępy + wcięcie ≈ 318 px < 360 px zawartości panelu 380 px; render
  offscreen: mieszczą się, bez elipsy w `idę na spot…`).

### Zasady wspólne

- Po kliknięciu **dowolnego** guzika wiersza blokada ok. 1,5 s (`…`), jak przy Stop/Start (ten sam `busy`).
- Guziki tylko pod myszą (Enter/Spacja ich nie wciskają); żadnych niejawnych akcji, nic nie rusza samo (także nie po
  zakończeniu Wróć → Refill: Refill zawsze świadomy klik).
- **`▶ Start` jest zablokowany, gdy serwis trwa** (bot stoi, ale serwis steruje myszą i czatem gry; drugi sterujący psułby
  zakupy). Dotąd Start był aktywny przy `stop`.
- Powód szarego guzika pokazuje się w linii pod wierszem, gdy mysz stoi nad guzikiem (bez tooltipu okna: nie zależy od
  popupów w warstwie panelu). Bez myszy w tej linii jest stan cyklu.
- Wygląd: ten sam język co Stop/Start (akcent zielony/żółty/czerwony motywu, obrys 1 px, wysokość 26, krój i rozmiary
  bez zmian). Dwa nowe guziki w osobnym rzędzie pod wierszem (nie w tej samej linii co Stop/Start, bo przy panelu 380 px
  ściskałyby nazwę i stan).

```
● główna   działa 8m 26s                    [ ■ Stop  ]
   [ ⌂ Miasto ] [ ↻ Refill ] [ ↗ Spot ]
   czeka na spokojną chwilę      <- stan cyklu / powód szarego guzika pod myszą / "błąd: …" (czerwone)
   HP 235/235  mana 33/335
   ostatni: gobliny_edron, ostrozny
   proxy włączone
```

Układ do oceny przez prowadzącego (alternatywa: trzy guziki w jednym rzędzie z węższym stanem).

## Backend (repo bota, branch `feat/guziki-miasto`)

- `panel.py --json`: dodatkowe, opcjonalne pola (dotychczasowe `text/tooltip/class/alt` bez zmian):
  `pozycja`, `w_miescie` (nazwa miasta z `trasy/serwis_<miasto>.json` albo `null`), `w_depo`, `plan_depo_dostepny`
  (`true/false`, `null` = pozycja nieznana), `wroc_oczekuje` (plik `WROC`), `wroc_w_marszu` (bot działa i `wyprawa_stan.json`
  ma aktywną wyprawę `depo:reczny`), `serwis_dziala`, `serwis_krok`, `serwis_ukonczone`, `serwis_wynik`
  (`ok|blad|przerwano|null`), `serwis_tryb` (`refill|spot|null`, z markera `REFILL: START <czas> <tryb>`), `serwis_komunikat`, `serwis_wiek_s`.
  - Strefa miasta = prostokąt punktów serwisu z `serwis_edron.json` (+8 pól) na piętrach tych punktów; `w_depo` = ≤ 2 pola od pola depo.
  - `plan_depo_dostepny` = te same reguły wyboru planu co `wyprawa._start_wyprawa` dla `depo` (nie liczy drogi; to robi bot).
  - Pozycja: jedno zapytanie `pozycja` do gniazda gry, twardy limit 2 s (wyjątek limitu to `BaseException`, nie do połknięcia przez
    `except Exception` w `bot.wlasny_wpis`); błąd = `null`. Awaria pól guzików: ostrzeżenie na stderr, stary kontrakt bez zmian.
- `refill.sh` (nowy): tryby `--tlo`, `--przerwij`, bez argumentu = praca w pierwszym planie; po sukcesie kasuje
  `serwis_stan.json` (kroki bank/depo nie są tu robione, więc `serwis.py` nie uznawałby przebiegu za zakończony i **drugi refill w
  ciągu 3 h pomijałby wszystkie zakupy**; po porażce stan zostaje i wznawia).
- Zmienne środowiskowe `refill.sh`: `REFILL_KROKI` (lista kroków, domyślnie jedzenie,backpack,blanki,wyjscie), `REFILL_WZNOW_MIN` (15),
  `REFILL_CZEKAJ_STOP_S` (5). Wtyczka ich nie ustawia; to hak dla ręcznych wywołań i testów.
- `zwolnij_wejscie.py` (nowy): sprzątanie wejścia po `--przerwij` (patrz wyżej).
- `instancja.py`: `procesy(..., comm=None)` i CLI `pidy-skrypt` (rozpoznanie pracy skryptu powłoki po `RETRONIC_ID`).
- Bez zmian: `serwis.py`, `wyprawa.py`, `dopasuj_okno.py`, `wroc.sh`, `serwis.sh`.

## Poza zakresem

- Chodzenie serwisu po mieście (diagnozowane osobno), zmiana planów i tras, `STARTUJ` z mapą/trybem innym niż ostatni.
- Zakupy z bankiem i depo (pełny `./serwis.sh` z terminala dalej działa).
- Automatyczne łączenie Wróć → Refill (decyzja: tylko świadome kliknięcia).

## Ryzyka

- Pozycja z paska nie rozstrzyga widma gracza po przelogowaniu tak dobrze jak działający bot (nowy proces bez historii ruchu):
  szary guzik zamiast złego zlecenia jest tu bezpieczniejszym błędem; przy duplikacie nazwy odpowiada reguła HP/adres bloku.
- Refill odmawia przy „alarm” do 60 s (okno alarmu `panel.py`).
- Pierwsze uruchomienie odłączone (`setsid -f` pod `Quickshell.Io.Process`) nie było sprawdzone w prawdziwym pasku, tylko na atrapie.

## Weryfikacja

Testy: `node --test test/*.test.js` (wtyczka), `python3 testy/test_refill.py` + `test_instancja.py` (bot), render
offscreen `PanelContent.qml`. Na żywo (osobna zgoda): instancja `test`, cykl Wróć → Refill na prawdziwej postaci w Edronie.
