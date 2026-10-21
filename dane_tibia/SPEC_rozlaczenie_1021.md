# SPEC 21.10: rozłączenie klienta (ekran wyboru postaci) = bot przestaje naciskać klawisze i powiadamia (ROZLACZENIE_STOP)

Status: zatwierdzone przez Karola 21.10 (punkt 1.2 z `dane_tibia/ruch/AUDYT_1021.md`: „Wylogowanie / ekran wyboru postaci -> bot przestaje naciskać klawisze + powiadomienie”). Auto-logowanie poza zakresem (osobna decyzja).
Pokrętło `ROZLACZENIE_STOP` domyślnie 0 = zachowanie bit w bit jak dziś. Zakres kodu: `rozlaczenie.py` (nowy), `cavebot.py` (tick + stałe), `mozg.py` (bramka modelu i czatu), `testy/test_rozlaczenie.py`.

## 1. Problem (dowody)

21.10 o 10:00:01 serwer wylogował wszystkie postacie (Retronic.log „Minimap saved” w tej samej sekundzie u wszystkich). To nie jedyny raz: 20.10 test-johny miał ten sam przebieg o 10:00:01 (telemetria: seria bez zmian od 10:00:01 do 10:04:21), a zrzut `logi/slepota/20261020-110138.png` (postać lvl 21) też pokazuje ekran logowania. Prawdopodobnie codzienny reset serwera o 10:00 (nie potwierdzone; do sprawdzenia, czy powtórzy się 22.10).

Klient po wylogowaniu zostaje z zamrożoną pamięcią: HP, pozycja i lista stworów stoją na ostatnim stanie, a bot dalej „gra”. Dowód z bobra (`mozg-20261021-0804.log` 6573-6600, telemetria 10:00-10:05):
- 10:00:02 wszystkie moby znikają w jednej próbce (także cel z HP 77% w odległości 1): bot loguje fałszywe „Cel Cave Rat zabity”, potem loot kończy się „brak_okna”, „pamięć nie widzi otwartych kontenerów”.
- 10:00:16-10:05:11 bot wysyła strzałki Left/Up/Down co ~8 s do klienta, który ich nie przyjmuje; [RATUNEK] S5 10:00:27, Watchdog 10:00:53, D3 zawieszka 10:01:00, S3 10:01:01.
- 10:05:11 „Trzy punkty z rzędu nieosiągalne, przerywam” = proces kończy się sam (tak skończyły 3 boty). Pozostałe stały do restartu przez admina (10:33-10:59).
- Zrzut slepoty z 10:02:01 (`instancje/_archiwum/bober-20261021/logi/slepota/20261021-100201.png`): okno „Character List”, a 11:20:24 u bobra „Enter Game” (drugie wylogowanie 11:18).
- Kutangen 20.10 (zgłoszone przez Karola jako 1 h 40 min na ekranie wyboru postaci): telemetria pokazuje inaczej niż „samo wylogowanie”. 21:01:06 postać ginie (HP 0, dwa Bugi, `mozg-20261020-2035.log`: „[UCIECZKA] HP 0%” 21:01:41), pozycja stoi 28 min, o 21:29:38 pozycja skacze do świątyni (32097,32205,7) (czyli ktoś zalogował postać ponownie), po czym pamięć znów stoi z HP 0 do STOP o 22:43:04 (stan UCIECZKA/JEDZENIE, „ALARM: niskie HP 0%”). Czy ekran wyboru postaci był widoczny, nie da się z logów rozstrzygnąć (brak zrzutu). Ten epizod to w głównej mierze zgon z `HP 0` (`SMIERC_STOP` wyłączony), nie jest liczony jako potwierdzone wylogowanie, a drugą połowę (żywa pozycja, nieaktualne HP z widma bloku statystyk) ta funkcja nie obejmuje.
- `SMIERC_STOP` tu nie pomaga: pamięć stoi na HP > 0 (`straznik_gracz` w JSON-ie slepoty: hp 172/175, exp bez zmian).
- Nic w kodzie nie obsługuje tego stanu: `grep -i "Character List\|Enter Game" *.py` pusto; `SLEPOTA_RESTART_S` = 0; `slepota.py` to tylko diagnostyka (i błąd: `zrzuc` pyta strażnika o `pozycja` bez nazwy, stąd „KeyError: 'nazwa'” w `straznik_pozycja`; to nie jest sygnał rozłączenia).

## 2. Który sygnał

Sprawdzone na telemetrii (`probka` co ~1,2 s) wszystkich instancji z 20-21.10: 13 par instancja-dzień, 71,7 h obserwacji (skrypt: `dane_tibia/ruch/rozlaczenie_zamrozone_serie_1021.py`; seria = kolejne próbki z identycznymi: pozycja, HP, mana, max_mana, exp i lista stworów).

| Kandydat | Wynik |
|---|---|
| Brak postaci w odczycie rdzenia | NIE występuje: po wylogowaniu wpis postaci zostaje w pamięci, `pozycja()` działa i oddaje zamrożoną pozycję. Nie nadaje się. |
| Kroki „nie ruszył” | Zależny od ruchu: ten sam objaw dają drzwi, ściana i gracz na drodze (30 zdarzeń `utkniecie` u bobra w jeden dzień). Nie nadaje się. |
| Sama zamrożona pamięć (>= 25 s) | Wykrywa wszystkie 8 potwierdzonych epizodów wylogowania (zrzut z ekranem logowania: 6 x 21.10 o 10:00, bober 21.10 11:18, test-johny 20.10 10:00; każdy trwa >= 260 s), ale daje 48 FAŁSZYWYCH serii >= 25 s (0,67 na godzinę; 3799 s; pomijając 11 serii zgonu kutangena 20.10, patrz wyżej) w zdrowej grze: LOOT 22, PRZERWA 8, PAUZA 4, WYPAD 4, IDZ 4, WALKA 2, pojedyncze UCIECZKA/WPADNIECIE/JEDZENIE/POGON. Przykład: bober 10:52:48-10:59:34 pusta pętla „Okrążenie N gotowe”, kutangen 20.10 PRZERWA. Gdyby pauzowała bota sama, wstrzymywałaby go w zwykłym postoju. Nie nadaje się jako jedyny. |
| Zrzut ekranu = ekran logowania | Okno logowania („Character List” albo „Enter Game”) to stała, narysowana tapeta „Retronic”. Zrzut `grim` (ok. 40 ms) po zmniejszeniu do siatki 32x24 i pominięciu paska FPS oraz środka (okna dialogowe) jest IDENTYCZNY na wszystkich 9 zrzutach z 20-21.10 (zgodność komórek 100%, także po przeskalowaniu okna 1175x910 -> 600x465), a na 27 obrazach spoza logowania z repo (pełne klatki gry 1175x910/940x1030/734x910, wycinki paneli i makiety) zgodność wynosi 0-7,4% (próg 90%). Średni kolor: tapeta 145/126/99, gra 23/17/12. Zrzut nie zależy od ruchu postaci. |

Wybór: **pamięć zamrożona >= 25 s ORAZ ostatnie 2 zrzuty z rzędu = ekran logowania** (pewny sygnał od chwili, gdy oba są prawdziwe). Pamięć zamrożona służy za tani wstępny filtr (zrzut robimy dopiero po 10 s bez zmian, co 5 s), a zrzut za rozstrzygnięcie.
- Fałszywe alarmy: 0 z konstrukcji. Zdrowa gra nie pokazuje tapety logowania, a 48 zamrożonych serii z tabeli kończy się odrzuceniem na zrzucie. Koszt filtru: 124 serie >= 10 s w 71,7 h = ok. 795 zrzutów (11 na godzinę na wszystkie boty razem, 40 ms).
- Pominięcia: (1) klient pokazuje inny ekran niż tapeta (okno błędu „Connection lost” nad grą, inne proporcje okna): nie wykryjemy; zostaje dzisiejsze zachowanie. (2) Zrzut niedostępny (`grim` wisi, okno ukryte): brak wyniku = brak alarmu. (3) Pamięć „migocze” po wylogowaniu (ghost-blok przy 20 s zamrożeniu `rdzen.gracz`): filtr się resetuje, alarm później; w 8 potwierdzonych epizodach pamięć stała bez żadnej zmiany do wznowienia.
- Opóźnienie: ok. 25-30 s po wylogowaniu (u bobra: alarm ok. 10:00:27, zdążyłyby 3-4 strzałki zamiast ~300 s).
- Powtórka na prawdziwej telemetrii (`dane_tibia/ruch/rozlaczenie_powtorka_1021.py`: detektor karmiony `probka` z 13 par instancja-dzień, zrzut = wyrocznia „czy to okno wylogowania”, bo zrzutów z całych dni nie ma): **8 alarmów na 8 wylogowań, 0 poza nimi**, alarm 26-36 s po zamrożeniu (kutangen 79 s przy rzadkich próbkach; bober 10:00:28 i 11:18:55, test-johny 20.10 10:00:31, dawajkesh 10:00:30, invincible 10:00:26, kolanoth 10:00:43, wydra 10:00:48, kutangen 10:01:22); każdy kończy się jednym wznowieniem po zakończeniu okna. Dwa najpóźniejsze (kutangen, wydra) to sparse'owe próbki: bot siedział wtedy w pojedynczym obiegu LOOT 37-42 s (patrz Ryzyka).

## 3. Zachowanie (ROZLACZENIE_STOP=1)

Odcisk życia = (hp, max_hp, mana, max_mana, cap, exp, level z `gracz`; pozycja; lista stworów: id, x, y, z, hp, kierunek). Liczony w każdym obiegu, bez nowych zapytań do strażnika.

1. Obieg `tick`: po odczycie `gracz` i pozycji (przed SMIERC, PK, walką, lootem, modelem) detektor dostaje odcisk. Gdy odcisk stoi >= 10 s: zrzut co 5 s (`rozlaczenie.ekran_logowania`).
2. Rozłączenie = odcisk stoi >= 25 s i dwa ostatnie zrzuty z rzędu to ekran logowania. Wtedy jednorazowo:
   - log „ROZŁĄCZENIE: ...”, stan `ROZLACZONY`;
   - telemetria typ `rozlaczenie` (poz, ostatni stan, zamrożone s, wynik zrzutu);
   - puszczenie trzymanych klawiszy (jak przy zgonie; to jedyna rzecz, która idzie do klienta);
   - powiadomienie critical z nazwą postaci i czasem (`_pk_powiadom`, klucz „rozlaczenie”);
   - `self.rozlaczony = True`.
3. Dopóki `rozlaczony`: `tick` nie robi nic poza odczytem (odporny na błąd odczytu: brak statystyk gracza w trakcie logowania nie kończy bota) i zrzutem co 3 s; po każdym obiegu sen 1 s. Brak klawiszy, klików, pytań do modelu. `mozg.obieg_hybrydy` też pomija model i czat (bramka jak `_martwy`). Proces NIE kończy się, żadnego STOP.
4. Wznowienie: dwa kolejne zrzuty bez ekranu logowania (postać znów w grze), albo, gdy zrzut jest niedostępny, 3 zmiany odcisku pod rząd (pamięć się rusza). Wtedy: log „Rozłączenie zakończone po N s”, telemetria `rozlaczenie_koniec`, reset liczników bezczynności, wymuszenie ponownego wyboru własnego wpisu postaci (`bot._wlasny`, widmo po relogu), brak powiadomienia (sukces = cisza).
5. ROZLACZENIE_STOP=0 (domyślnie): żaden z tych kodów się nie wykonuje, brak zrzutów, brak telemetrii, brak zmian (test porównuje sekwencję klawiszy z ROZLACZENIE_STOP=0 na wejściu z rozłączeniem: identyczna jak na starym kodzie). Przełączenie 1 -> 0 w trakcie pauzy natychmiast zwalnia pauzę (ręczne odblokowanie).

Poza zakresem (wprost): auto-logowanie; reakcja na inne ekrany niż tapeta; STOP lub kończenie procesu; ponowny start po relogu przez nadzorcę; naprawa `slepota.py` (KeyError `nazwa`).

## 4. Pokrętło i stałe

- `cavebot.ROZLACZENIE_STOP` = 0 (0/1). Wpis do `pokretla.ZAKRESY`: `"ROZLACZENIE_STOP": (0, 1)`, kierunek `"nie_wyzej"` (większa wartość = więcej pauzowania; 1 to ręczne włączenie), `na_zywo.przyklad.json`: `"ROZLACZENIE_STOP": 0`. Dodaje lead (poza zakresem pliku `pokretla.py`).
- Progi w `rozlaczenie.py` (nie pokrętła): `PROG_S` 25, `PODEJRZENIE_S` 10, `ZRZUT_CO_S` 5 (w pauzie 3), `ZRZUTY_POTW` 2, `ZRZUTY_WZNOW` 2, `ZMIANY_WZNOW` 3, próg zgodności komórek 0,90.
- Wzorzec: `dane_tibia/ekran_logowania_wzorzec.json` (siatka 32x24 uśredniona z 9 zrzutów; odtworzenie: `python3 rozlaczenie.py zbuduj <png...>`; ocena zrzutu: `python3 rozlaczenie.py ocen <png...>`).

## 5. Test (testy/test_rozlaczenie.py, offline)

- Detektor (czysta logika): sekwencja z 10:00 (odcisk stoi, zrzuty = logowanie) -> alarm między 25 a 31 s, dokładnie raz; zdrowa gra z 48 postojami (odcisk stoi, zrzut = gra) -> 0 alarmów; zrzut niedostępny -> 0 alarmów; wznowienie po 2 zrzutach gry; wznowienie po 3 zmianach odcisku bez zrzutu; zmiana odcisku w trakcie zerowania.
- Klasyfikator na plikach: 9 zrzutów logowania z repo (jeśli są) -> prawda, zrzuty gry -> fałsz; synteza: tapeta przeskalowana -> prawda.
- Cavebot z atrapami (jak `test_smierc_stop.py`): odtworzenie 10:00 u bobra (świat zamrożony, strzałki w kolejce) przy ROZLACZENIE_STOP=1 -> po alarmie zero klawiszy/klików w ciągu 5 minut, jedno powiadomienie, jeden rekord `rozlaczenie`; potem zrzut „gra” -> wznowienie i klawisze wracają; przy ROZLACZENIE_STOP=0 -> bot dalej wysyła klawisze (zachowanie dzisiejsze), brak powiadomienia; normalna gra z postojami -> brak alarmu; `mozg._rozlaczony` blokuje akcje modelu.
- FAIL na starym kodzie: kopia całego katalogu z `.bak` plików (patrz niżej) -> test wykrywa brak `rozlaczenie`/pokrętła i 5 minut klawiszy po wylogowaniu.

## 5a. Wyniki (21.10, katalog `~/Games/Retronic/pomocnik`)

- `testy/test_rozlaczenie.py`: na kopii starego kodu (`cavebot.py`/`mozg.py` z `*.bak-20261021-rozlaczenie`, bez `rozlaczenie.py`) **8 z 28 OK, 20 FAIL** (m.in. C5: po „wylogowaniu” 822 akcje w 5 min zamiast 0; stary kod w tej symulacji kończy się też „Trzy punkty z rzędu nieosiągalne, przerywam”, jak 3 prawdziwe boty); na nowym kodzie **51 z 51 OK**.
- Pokrętło 0: skrót sekwencji klawiszy (`INFO C11`) identyczny na starym i nowym kodzie (adf83e47e71e).
- Cały zestaw `testy/test_*.py` przed i po: identyczne wyniki w 139 plikach (te same 17 plików nadal czerwone co przed zmianą, m.in. `test_cavebot` 478/481, `test_uh_cavebot` 51/54); nowe: `test_rozlaczenie` 51/51 (i `test_wpadniecie_bez_stop` 35/35 od innego zadania).

## 6. Cofnięcie

`ROZLACZENIE_STOP`=0 w `na_zywo.json` (działa bez restartu, także w trakcie pauzy). Pełne: przywrócenie `cavebot.py` i `mozg.py` z `*.bak-20261021-rozlaczenie`, usunięcie `rozlaczenie.py`, wzorca i testu.

## 7. Ryzyka

- Sub-pętle w jednym obiegu (loot, wypad) mogą jeszcze wysyłać klawisze po alarmie, bo detektor działa na początku obiegu (z telemetrii: luka między obiegami u bobra do 14 s, u kutangena i wydry w LOOT do 37-42 s: 10:00:03-10:00:40-10:01:22 jednym obiegiem). Pełne zatrzymanie wymagałoby bramki w `bot.py`/`klawisz_x11.py` (poza zakresem).
- Wznowienie po relogu w tym samym procesie nie było testowane na żywo: widmo własnego wpisu (`adres_postaci` w `rdzen.py`, duplikat nazwy) może pokazywać starą pozycję; zalecany jak dotąd restart bota po ręcznym zalogowaniu.
- Wzorzec zakłada tapetę Retronic w proporcjach okna dopasowanych przez `dopasuj_okno` (1175x910 lub mniej, te same proporcje). Zmiana tapety klienta wymaga `python3 rozlaczenie.py zbuduj`.
