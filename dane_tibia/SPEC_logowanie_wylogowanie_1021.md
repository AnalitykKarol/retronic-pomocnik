# SPEC: klocki wejścia i wyjścia: `zaloguj.sh`, `wyloguj.sh`, `stan-ekranu` (K1) - 21.10

Status: zatwierdzony plan `SPEC_nadzorca_rotacja_1021.md` (Karol 21.10 ~16:30, faza K1). Poprzednicy: pomiar F0 w `SPEC_nadzorca_zestawu_1021.md`,
prototyp `narzedzia_jednorazowe/wyloguj_prototyp_1020.py`, `SPEC_powrot_rook_1020.md` F2, klasyfikator `rozlaczenie.py`.
Pliki: `logowanie.py` (cała logika, CLI), `zaloguj.sh`, `wyloguj.sh`, `dane_tibia/logowanie_szablony.npz`, `testy/test_logowanie.py`,
`testy/dane/logowanie/*.png`. Nic z istniejących plików bota nie zmienione (`rozlaczenie.py`, `sesja_gry.py`, `cavebot.py` bez zmian).

## 1. Problem

Nadzorca (rotacja postaci) nie ma czym wejść do gry ani z niej wyjść. Dziś: logowanie to ręczne klikanie albo jednorazowy pomiar F0 z
21.10 07:34; wylogowanie to prototyp bez kontroli stanu bota i walki. Do tego dochodzi luka z 20.10: po zgonie bot kręcił się 1 h 40 min
na ekranie wyboru postaci, bo nic nie rozpoznaje tego ekranu.

## 2. Kroki

### `zaloguj.sh` (z `RETRONIC_ID`; sesja już działa, `sesja_gry.py start` robi kto inny)

1. Odmowa: brak sesji (kod 3); `STOP_RECZNY` bez bota = Karol gra (kod 4, wymuszenie `--reczny-ok`).
2. Pętla co 0,5 s do limitu (90 s): zrzut -> rozpoznanie ekranu (§3) -> decyzja:
   - `gra`: jeśli nic nie klikano, koniec kodem 0 bez kliku ("już w grze"); jeśli klikano, 2 zrzuty `gra` z rzędu = wejście, potem sprawdzenie
     nicku (§5);
   - `enter_game`: klik Login (588,594), potem 10 s bez ponownego kliku; najwyżej 2 kliki, potem kod 1 (zły login/hasło, okno błędu);
   - `character_list`: klik Ok (641,628), potem 12 s bez ponownego kliku; najwyżej 2 kliki;
   - `zgon`: kod 6, zero kliknięć; `nieznany`: zero kliknięć, czekanie do limitu, potem kod 7.
3. **Każdy klik:** kursor na przycisk (XTEST, drganie +-2 px), potem NOWY zrzut i rozpoznanie, dopiero wtedy naciśnięcie, i tylko gdy ekran to
   dokładnie oczekiwany (`enter_game` dla Login, `character_list` dla Ok). Inaczej klik odwołany (zdarzenie `klik_odwolany` w jsonl).
   **Żadnych klawiszy** (Enter w F0 nie działał, a 21.10 07:33 trafił do gry kolanotha).
4. Współrzędne obowiązują tylko dla ekranu 1175x910 (rozmiar sesji; F0). Klik sprawdza też, że ekran X ma ten rozmiar. Inny rozmiar = ekran
   `nieznany` (brak kliku).

### `wyloguj.sh` (z `RETRONIC_ID`, wg `SPEC_powrot_rook_1020.md` F2)

1. Brak sesji = kod 0 (nic do zamknięcia). `STOP_RECZNY` bez bota = kod 4. Zgon = kod 6. Ekran `nieznany` = kod 7.
2. Ekran = lista postaci albo Enter Game (np. po resecie serwera): od razu `sesja_gry.py zamknij`.
3. Ekran = gra: bot działa i nie jest w mieście (`panel.py --json` -> `w_miescie`) = kod 8. Bot zatrzymany albo w mieście = dalej.
4. Pętla do limitu (300 s): odczyt rdzenia (`gracz`, `stwory`) -> **spokój**: żaden potwór (nie gracz) na piętrze postaci w odległości <= 2, żadne
   stworzenie z `bije_nas`/`atakowany`, HP nie spada między odczytami, własna postać widoczna na liście. Bez spokoju: czekanie (co 1,5 s),
   po 120 s ciągłego braku spokoju kod 5 (w Tibii nie wylogujesz się w walce, logout block).
   Przy spokoju i ekranie `gra`: Ctrl+L, potem podgląd ekranu co 0,5 s przez 2 s (pierwszy raz) / 4 s (kolejne). Pierwszy zrzut z oknem
   logowania = natychmiast `sesja_gry.py zamknij` (autoReconnect loguje z powrotem w < 60 s, patrz F2).
5. Kod 0 = lista postaci zobaczona i `zamknij` zwróciło 0. Zamknięcie z działającym botem (w mieście) zatrzymuje go `zatrzymaj.sh`, co zostawia
   `STOP_RECZNY` (zachowanie `sesja_gry.py zamknij`, nietknięte); nadzorca ma zatrzymać bota sam przed `wyloguj`.

### `logowanie.py stan-ekranu [--json]` (dla nadzorcy)

Jedno słowo: `gra | enter_game | character_list | zgon | nieznany` (brak sesji: `nieznany` + kod 3). `--json` dokłada zgodność szablonów, rozmiar, powód.

## 3. Rozpoznanie ekranów (dane z dysku)

Źródło: 9 zrzutów slepoty z `instancje/**/logi/slepota/` (20-21.10, 1175x910): 7 x „Character List”, 1 x „Enter Game” (bober 21.10 11:20), 1 x gra
(kolanoth 14:52, ciemny loch) + 4 żywe zrzuty gry 21.10 16:30 (dawajkesh, invincible, kutangen, wydra; odczyt `grim`, bez wysyłania czegokolwiek).

- **Czy `rozlaczenie.py` odróżnia „Enter Game” od „Character List”? NIE.** Jego siatka 32x24 maskuje środek (okna dialogowe) i rozpoznaje samą tapetę:
  8 z 8 zrzutów logowania = prawda (obu okien), 5 z 5 klatek gry = fałsz. Do kliknięcia to za mało (Login nie wolno klikać na liście postaci).
  Bez zmian w `rozlaczenie.py`: `logowanie.py` używa go jako pierwszego warunku (tapeta) i dokłada własny.
- **Okna po paskach** (`logowanie.py`, `OBSZARY`; paski wycięte ze środka okien: tytuł, przyciski, jednolite pole listy; bez pól tekstowych konta, hasła i
  nicku): szablon = średnia pasków, zgodność paska = część komórek z |dR|+|dG|+|dB| < 24, **zgodność okna = NAJGORSZY pasek** (nie średnia: ciemne okno błędu
  nad paskiem zgadza się z nim w ~94%, bo tło jest to samo, różni się tylko tekst).
  - okna są statyczne: różnica względem szablonu wynosi 0 w każdym pikselu pasków na wszystkich zrzutach tego samego okna (`grim`, bez kompresji);
  - „Character List”: zgodność 1,00 na 7 z 7 zrzutów (zmierzone też bez tego zrzutu w szablonie: 7 z 7), zgodność szablonu „Enter Game” na nich 0,33;
  - „Enter Game”: 1,00 na zrzucie wzorcowym (jedyny), zgodność „Character List” 0,02;
  - gra (5 z 5): tapeta = fałsz, `ikony_klienta` (piksele W-80,17 niebieski i W-50,17 zielony, jak prototyp) = prawda; na wszystkich 8 zrzutach logowania
    ikony = fałsz.
  - Reguła: okno rozpoznane, gdy zgodność >= 0,97 i przewyższa drugie o >= 0,40 (zmierzone marginesy 0,67-0,98); tapeta bez rozpoznanego okna
    (okno błędu, „Connecting...”, inny rozmiar) = `nieznany`.
  - Wynik na 13 zrzutach (9 z dysku + 4 żywe): 7 character_list, 1 enter_game, 5 gra, 0 pomyłek. Czas klasyfikacji 2-40 ms.
- Ograniczenia: tylko jeden wzorcowy zrzut „Enter Game” (okno statyczne; jeśli kiedyś inny, `logowanie.py zbuduj --lista ... --enter ...`);
  rozpoznanie tylko dla 1175x910.

## 4. Zgon

Dane (kutangen 20.10, `telemetria-20261020.jsonl`): 21:00:30 HP 19, 21:01:06 HP 0 (własny wpis na liście stworów ma jeszcze hp 2), 21:01:07 własny wpis
znika z listy, HP 0 stoi dalej, pozycja stoi; 21:29:38 skok do świątyni (ktoś zalogował ponownie), HP w pamięci nadal 0 (nieaktualny blok statystyk)
do 22:43. Zrzutu ekranu po zgonie nie ma na dysku (kutangen 20.10, bober 21.10 bez potwierdzonej śmierci).

Wniosek: **okna „You are dead” nie da się rozpoznać ze zrzutu** (brak wzorca). Zgon = HP 0 w pamięci gry przez 3 kolejne odczyty (jak
`cavebot.SMIERC_ODCZYTY`, odstęp 0,4 s), na ekranie `gra`, `character_list` albo `nieznany`. Nie na `enter_game` (świeży klient, pamięć nieaktualna).
Przy ekranie `character_list` z HP 0 w zamrożonej pamięci też `zgon`: ostatni stan przed wylogowaniem to był zgon (kutangen), więc `zaloguj`/
`wyloguj` odmawiają (decyzja Karola, Q5). Ryzyko (fałszywy zgon): po respawnie i ponownym logowaniu blok statystyk bywa nieaktualny z HP 0 (kutangen
21:29-22:43) i `stan-ekranu` daje `zgon` do restartu klienta; to kierunek bezpieczny (nadzorca woła Karola).
Do zmierzenia na żywo przy pierwszym zgonie: zrzut okna „You are dead” (wtedy dodać szablon jak dla Login/Ok).

## 5. Potwierdzenie wejścia i nick

Po kliknięciu Ok czekamy na `gra` (2 zrzuty z rzędu), potem log klienta `instancje/<id>/gra/Retronic.log`: nowa linia „Connecting to character X on …” z
nickiem różnym od `profil.json` `postac` (albo `RETRONIC_POSTAC`) = kod 9 (konto z wieloma postaciami, zła postać w grze). Pusty `postac` w profilu
(wydra dziś) = brak porównania, nick tylko w logu. Zakładamy konta z jedną postacią albo z właściwą domyślnie zaznaczoną (F0: jedna, zaznaczona).

## 6. Logi i kody wyjścia

`instancje/<id>/logi/logowanie.log` (tekst, też na stdout) i `logowanie.jsonl` (zdarzenia: `start`, `ekran`, `klik` / `klik_odwolany` z ekranem tuż
przed kliknięciem, `ctrl_l`, `wylogowano`, `zamkniecie`, `w_grze`, `koniec`). Blokada `instancje/<id>/logowanie.lock`: jedna akcja naraz na instancję.

| kod | znaczenie |
|---|---|
| 0 | zrobione albo nic do zrobienia (zaloguj: już w grze; wyloguj: sesja już zamknięta) |
| 1 | limit czasu / porażka (2 kliki bez skutku, `zamknij` się nie udało, inna akcja trwa) |
| 2 | złe użycie (brak `RETRONIC_ID`) |
| 3 | brak sesji gry |
| 4 | `STOP_RECZNY` bez bota (Karol gra ręcznie) |
| 5 | wyloguj: brak spokoju w limicie (walka, potwór obok) |
| 6 | zgon |
| 7 | ekran nierozpoznany |
| 8 | wyloguj: bot działa poza miastem |
| 9 | zaloguj: w grze inna postać niż oczekiwana |

Limity: zaloguj 90 s, wyloguj 300 s (`--limit`), czekanie na spokój 120 s (`--czekaj-spokoj`), zasięg potwora 2 (`--zasieg`).

## 7. Test (`testy/test_logowanie.py`, offline)

Wynik: 64 z 64 OK. Zrzuty z dysku (`testy/dane/logowanie/`: 2 x Character List, Enter Game z zamazanymi polami konta/hasła, ciemna gra) i atrapy Portu (zrzut, klik,
Ctrl+L, rdzeń, zegar wstrzykiwane): klasyfikacja i marginesy; zaloguj z ekranu Enter Game i Character List (dokładnie 2 kliki w dobrych punktach, zero klawiszy); **klik nigdy
nie idzie, gdy ekran = gra**, także gdy ekran zmienia się między decyzją a naciśnięciem; wyloguj odmawia przy potworze obok / bije_nas / HP spada /
zgonie / bocie poza miastem / STOP_RECZNY, czeka do spokoju, Ctrl+L tylko na ekranie gra, `zamknij` zaraz po liście postaci; `stan-ekranu` dla
5 stanów; dane 20.10 21:01 (HP 0, własny wpis znika) = `zgon`.

## 8. Cofnięcie

Usunięcie `logowanie.py`, `zaloguj.sh`, `wyloguj.sh`, `dane_tibia/logowanie_szablony.npz`, `testy/test_logowanie.py`, `testy/dane/logowanie/`. Żaden istniejący plik
nie jest zmieniony. Po `wyloguj.sh`: `sesja_gry.py start` + `zaloguj.sh` przywraca postać.

## 9. Czego NIE zmierzono na żywo

- `zaloguj.sh` jako całość (F0 zmierzył kliki ręcznie przez XTEST, skrypt nie był uruchomiony na grze); współrzędne Login/Ok z F0 (588,594 / 641,628)
  zgadzają się z zrzutami (środek przycisków na 1175x910), ale klik przez `logowanie.py` nie był wykonany.
- `wyloguj.sh` jako całość (prototyp 20.10 działał: kutangen 1 próba, kolanoth 30 prób), nowa jest kontrola spokoju na prawdziwej walce i
  zamykanie przez `subprocess` (`sesja_gry.py zamknij` z działającym botem w mieście).
- Czy `Ctrl+L` przechodzi, gdy aktywne jest pole czatu; czy klient po Ctrl+L zawsze pokazuje „Character List”, nie „Enter Game”.
- Okno „You are dead” (§4) i zachowanie `stan-ekranu` na prawdziwym zgonie.
- „Connecting to character” w logu klienta jako potwierdzenie (linia pojawia się u kutangena 21.10 07:35:51 po ręcznym logowaniu F0; opóźnienie zapisu nie mierzone).
- Konto z wieloma postaciami (lista z 2 wierszami: test-johny 20.10): zaznaczony wiersz nie jest sprawdzany poza kontrolą nicku w logu.
- Rozmiar sesji inny niż 1175x910.

## 10. Lista kroków do „jednego wywołania” z Karolem (kolejność)

1. `stan-ekranu` na wszystkich działających instancjach (tylko odczyt): oczekiwane `gra`.
2. `zaloguj.sh` na instancji z klientem już w grze: oczekiwane „już w grze”, kod 0, zero kliknięć (jsonl bez zdarzenia `klik`).
3. Instancja zatrzymana przez Karola: `wyloguj.sh` w mieście/bezpiecznym miejscu (Karol obok): Ctrl+L, lista postaci, zamknięcie sesji.
4. `sesja_gry.py start` tej samej instancji, potem `zaloguj.sh`: Enter Game -> Login -> Character List -> Ok -> gra, nick zgodny; czas ~3 s.
5. `wyloguj.sh` w walce / przy potworze obok: oczekiwane czekanie, potem kod 5 po 120 s (albo wylogowanie po końcu walki).
6. (Przy okazji) zrzut okna zgonu, gdy któraś postać zginie: dołożyć szablon.
