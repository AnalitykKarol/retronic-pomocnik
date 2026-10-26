# Okno zarządzania Retronic (QML, Quickshell) — fazy F2, F3 i F4

Spec: `wtyczka-paska/specs/2026-10-19-retronic-okno.md`. Osobny proces od paska; okno tylko czyta JSON z `okno_api.py` i woła
skrypty bota. F2 = szkielet, pasek boczny (karty postaci, menu sekcji, akcje), sekcje **Ratunek** i **Mapa i tryb**.
F3 = sekcja **Ustawienia** (edycja pokręteł) i wyszukiwarka **Ctrl+K**. F4 = sekcja **Sesja gry** (start/zamknięcie gry instancji, podgląd,
profil tylko do odczytu) oraz level i podgląd na kartach postaci; wszystkie cztery sekcje menu są aktywne.

## Uruchomienie

```bash
./okno.sh        # quickshell -p okno/ --no-duplicate; drugi start nie otwiera drugiego okna (w Hyprlandzie podnosi istniejące)
```

Zamknięcie okna kończy proces. Wejście skrótem/launcherem (`~/.config`, `.desktop`) to poziom 2, osobna zgoda.

## Odświeżanie

Wybrana postać: `okno_api.py stan --instancja ID` co 2 s; wszystkie: `stan` co 5 s; otwarta sekcja (`mapy-tryby`, `spotkania`) co 5 s;
`okno_api.py spotkania` zawsze co 30 s (karty postaci biorą licznik z cache, który to polecenie odświeża; zaplecze liczy najwyżej raz na 60 s);
sekcja Sesja gry (`okno_api.py sesja --instancja ID`) co 2 s, tylko gdy jest otwarta.
Jedno wywołanie danego rodzaju naraz, wszystko asynchronicznie (`Job.qml`).

## Ustawienia (F3)

Wybrana w pasku bocznym postać wyznacza instancję; zapis idzie do jej `na_zywo.json` (bot czyta plik na żywo, bez restartu).
Zapis **od razu** po puszczeniu suwaka, kliknięciu przełącznika albo przycisku wyboru, Enterze w polu liczby (decyzja Q3, bez „Zapisz”);
pod listą stoi wynik ostatniej zmiany i **Cofnij ostatnią** (jeden wpis dziennika `okno_cofnij.jsonl`; zestaw run to jeden wpis). Cofnięcie przywraca tylko klucze, które nadal mają wartość ustawioną z okna (zmiany z zewnątrz zostają, lista „pominięto”), a przycisk przekazuje `--epoch` wpisu z podpisu: gdy ostatni wpis jest już inny, zaplecze odmawia. Zapisy czekające w kolejce nie giną przy zmianie postaci (każdy niesie własną instancję).
Zapis robi `okno_api.py ustaw` (granice i dozwolone wartości z `pokretla.py`, kopia `na_zywo.json.bak-DATA-okno` przy pierwszej zmianie dnia,
zapis atomowy); okno liczy tylko polecenie (`UstawieniaModel.js`) i pokazuje wynik.

- **Grupy**: z `okno_api` (jawna tabela prefiks klucza → grupa, najdłuższy prefiks wygrywa, reszta = Zaawansowane). Okno dodaje dwie:
  przypiętą na górze **Runy (UH)** = klucze `UH_*` (jaką runę robi postać) i **Poza listą** = klucze z `na_zywo.json`, których bot nie zna
  (tylko odczyt, bez kontrolki). Pole „szukaj pokrętła” po lewej szuka po nazwie, opisie i grupie we wszystkich grupach.
- **Kontrolki** (Q2: nazwy techniczne + opis z komentarza `pokretla.py`): liczby = suwak z zakresem `ZAKRESY` + pole liczby; `0/1` = przełącznik;
  pokrętła tekstowe (`TEKSTY`: `UH_CZAR`, `UH_KLAWISZ`, `RUNA_KLAWISZ`, `PET_NAZWA`) = przyciski z dozwolonych wartości (przy `UH_CZAR`
  podpisy: `adori gran` = HMM, `adura vita` = UH). Wartość inna niż domyślna jest wyróżniona, jest „wróć do domyślnej”.
- **Zestawy run** (górna grupa): jedno kliknięcie ustawia `UH_CZAR` + `UH_KLAWISZ` + `UH_KOSZT` + `UH_MANA_MIN` z trybu z `tryby.json`, który ustawia
  `UH_CZAR` (dziś `runy` = HMM i `uh`). `UH_AKTYWNY` zostaje osobnym przełącznikiem.
- **Ostrzeżenie o trybie**: tryby z `ostatni_start[.<id>].env` przy następnym starcie (`uruchom.sh` → `tryb.py`) nadpisują swoje pokrętła; okno
  pokazuje nad listą i przy wierszu, które pokrętła tryb ustawi inaczej niż są teraz. Samej listy trybów okno tu nie edytuje (to sekcja Mapa i tryb).
- **Ctrl+K** (albo „⌕ szukaj” w pasku tytułu): nakładka z wyszukiwaniem pokręteł, map i trybów dla wybranej postaci; ↑↓ wybór, Enter przenosi
  do pokrętła w Ustawieniach (grupa, przewinięcie, mignięcie wiersza), mapa/tryb → sekcja Mapa i tryb, Esc zamyka. Puste pole podpowiada pokrętła run.

## Sesja gry (F4b)

Spec: `wtyczka-paska/specs/2026-10-19-retronic-okno.md` („F4: rozpiska”) i `2026-10-20-retronic-lvl-i-podglad.md`. Widok `SesjaView.qml`, reguły i teksty
w `OknoModel.js` (czyste funkcje, testy `test/Sesja.test.js`). Okno niczego nie zgaduje: o tym, czy start/zamknięcie są możliwe, decyduje zaplecze
(`mozna_uruchomic`, `mozna_zamknac` z `okno_api.py sesja`).

- **Stan sesji**: sway, gra, bot, `siec_proxy`, podgląd (otwarty / zamknięty z portem), od kiedy sesja (z mtime `sway.conf`); chip „sesja: działa / zatrzymana / …” w nagłówku.
- **Profil tylko do odczytu** (D-F4-1, bez hasła): proxy `host:port`, użytkownik, oczekiwane IP, postać, konto (przypisane / nie), tożsamość sprzętu, uwagi;
  odznaka **IP z ostatniego startu** (też nieudanego): zielona „zgodne z profilem”, czerwona „SPOZA profilu” (z radą: nie loguj postaci, zamknij grę, sprawdź proxy);
  błąd profilu na czerwono, ostrzeżenie na bursztynowo. Okno nie zmienia ani profilu, ani proxy.
- **Guziki** (pasek akcji na dole): **Uruchom grę** (`gra-start`, aktywny tylko gdy `mozna_uruchomic`; potem podpowiedź „zaloguj postać w podglądzie”),
  **Zamknij grę** (`gra-zamknij`, aktywny gdy `mozna_zamknac`, **zawsze z potwierdzeniem**; gdy bot działa, w oknie dodatkowe ostrzeżenie: bot zostanie zatrzymany,
  a postać w walce może zostać w grze), **Otwórz podgląd** (`podglad`; gdy podgląd już otwarty guzik nazywa się **Pokaż podgląd** i przenosi na niego fokus).
  Szary guzik pokazuje powód w linii obok (najechanie albo od razu przy blokadzie profilu). Pod guzikami wynik ostatniej akcji (jedna linia skryptu) i ostatnie linie logów
  (`sway.log` startu, `logi/sesja-*.log`). Akcje: `Rules.actionCommand` z `RetronicModel.js` → `sesja_gry.py start|zamknij|podglad` z `RETRONIC_ID`; limit czasu akcji sesji 120 s (zamknięcie gry to w najgorszym razie ok. 90 s; po przekroczeniu komunikat „zamykanie trwa dłużej, stan odświeży się sam”, a stan dociąga odczyt). Zajętość akcji jest per instancja (`busyIds`, `ActionRun.qml`): trwające `Zamknij grę` jednej postaci nie szarzy Stop/⌂ Miasto innych, a na jedną instancję idzie jedna akcja naraz. Guzik podglądu w tej sekcji zgadza się z `Rules.previewState` (sesja stoi = jest port VNC).
- **Główna instancja**: sekcja tylko wyjaśnia, że startuje ręcznie (`retronic.sh` / `sesja.sh`); bez guzików.
- **Karty postaci** (pasek boczny): `lvl N` (z `gracz.level`, pole `level` ze `stan`); **klik w nick = podgląd** tej instancji (decyzja Q1 20.10), znacznik przy nicku jak na pasku:
  wypełnione koło w akcencie = podgląd otwarty, pusty pierścień = zamknięty, brak znacznika i nick nieklikalny = brak sesji (albo główna). Stany liczy `Rules.previewState`.

## Akcje

Stop/Start, ⌂ Miasto, ↻ Refill, ↗ Spot to dokładnie to, co na pasku: reguły szarości i polecenia z `../wtyczka-paska/RetronicModel.js`
(w `okno/` jest do niego symlink `RetronicModel.js`, bo Quickshell nie importuje plików spoza katalogu konfiguracji). „Start z tym” =
`uruchom.sh` z `MAPA`, `TRYB`, `RETRONIC_ID` (i `RETRONIC_POSTAC`, gdy znany nick), z potwierdzeniem; aktywny tylko gdy bot instancji
stoi, jest gra i nie trwa serwis. „To fałszywy alarm” = `okno_api.py ratunek-oznacz`. „Pokaż w logu” = otwieracz (`xdg-open`,
`RETRONIC_OKNO_OTWIERACZ`) na pliku `logi/ratunek-*.jsonl`; ścieżka z linią jest też w szczegółach.

### Zaloguj postać (24.10)

Guzik **Zaloguj** (pasek boczny: obok Start; Przegląd: w komórce STAN wiersza postaci niezalogowanej) loguje postać instancji do gry
**bez uruchamiania bota** (Karol: „nie odpalaj całego bota, tylko loguj same postacie”). Polecenie: `Rules.actionCommand(…, "zaloguj")` →
`zaloguj_postac.sh` z `RETRONIC_ID` (w `ACTION_SCRIPTS`/`SESSION_KINDS` współdzielonego `RetronicModel.js`, więc pasek też ma to polecenie, ale
guzika na pasku nie ma). Skrypt: odmawia dla postaci straconej (`profil.json` `stracony`) i gdy trwa inne logowanie; gdy sesji nie ma, startuje ją
tą samą drogą co „Uruchom grę” (`sesja_gry.py start`, otwiera też podgląd Remmina); czeka do 60 s na `siec_proxy: IP wyjściowe … (zgodne z profilem)`
(IP spoza profilu albo brak potwierdzenia = przerwanie bez logowania); potem `zaloguj.sh --reczny-ok` (klika Login i Ok, zero klawiszy, na ekranie gry
nic nie klika). NIE usuwa STOP/STOP_RECZNY, nie woła `uruchom.sh`/`mozg.py`, nie zmienia profilu ani planu. Kody wyjścia i cofnięcie: nagłówek
`zaloguj_postac.sh`; ostatnia linia wyjścia to zdanie po polsku, które okno pokazuje pod guzikami (zielone = OK, czerwone = odmowa/błąd; gaśnie po 40 s).
Limit czasu akcji w oknie 240 s (`Model.LOGIN_TIMEOUT_MS`); wynik liczy `Model.parseLoginResult`, nie `Rules.parseActionResult`.

Stracone (25.10): postacie z `stracony` są domyślnie ukryte: w Przeglądzie „wszystkie”/„w grze”/„z alarmem” ich nie pokazują (widać je w chipie „stracone N”, a „wszystkie” i liczniki liczą tylko widoczne), a lista postaci w pasku bocznym i stopka je pomijają; wiersz „pokaż stracone (N)” pod listą włącza je z powrotem. Wybrana postać, która stanie się stracona/ukryta, spada na pierwszą widoczną; klik w straconą w Przeglądzie sam włącza listę. Logika: `PrzegladModel.js` (`passes`, `filterCounts`, `visibleInstances`, `selectionAfter`), stan `Backend.showLost`.

Sortowanie (25.10): wiersz „SORTUJ” w Przeglądzie (chipy: poziom ↓ · nazwa A→Z · exp/h ↓ · stan · HP% ↑ · ostatnio ↓), domyślnie poziom malejąco; remis: wyższy % do następnego poziomu, potem nazwa (bez polskich znaków diakrytycznych w porównaniu), potem kolejność źródłowa (stabilnie); brak danych zawsze na końcu, niezależnie od kierunku. Jedno wspólne ustawienie (`Backend.sortKey`) dla Przeglądu (sortowanie wewnątrz grup W GRZE / OFFLINE, razem z filtrami i ukrywaniem straconych) i listy postaci w pasku bocznym - dwa osobne ustawienia dałyby dwa różne porządki tych samych postaci. Wybór przeżywa odświeżenia i restart okna: jednowierszowy plik `~/.local/state/retronic-okno/sortowanie` (`RETRONIC_OKNO_SORT_PLIK` w testach); nieznany klucz w pliku = domyślny poziom; wybór kliknięty przed odczytem pliku wygrywa. Logika: `PrzegladModel.js` (`SORTS`, `validSort`, `sortRows`, `sortInstances`), testy w `Przeglad.test.js` ("sortowanie") i scenariusz H w `qml-atrapa.sh`.

Stany guzika (`Model.loginState`, kolejność reguł): główna instancja = szary („loguje się ręcznie”) · stracona (profil) = szary · własne logowanie w toku = „…” ·
inne logowanie w toku = szary z nazwą postaci (**jedno naraz**: wybrano szarość z podpowiedzią zamiast kolejki, bo kolejka ukrywałaby kliknięcia na
minuty, a logowanie wymaga uwagi Karola przy podglądzie) · już w grze = szary „już w grze” · inna akcja tej postaci w toku = szary · inaczej aktywny.
„W grze” = pozycja z panelu, gracz z telemetrii albo działający bot; samo `przeglad.w_grze` (klient/sesja stoi) NIE wystarcza, bo ekran logowania
też je ma. Fałszywe „nie w grze” jest bezpieczne (`zaloguj.sh` na ekranie gry nic nie robi). Ograniczenie: nadzorca nie bierze blokady
`$XDG_RUNTIME_DIR/retronic-zaloguj.lock`, więc logowanie nadzorcy wystartowane w tej samej sekundzie nie jest wykluczone (skrypt wykrywa tylko
trwające `logowanie.py zaloguj|wyloguj` innej instancji).

Test scenariuszy: `okno/test/qml-atrapa.sh` scenariusz F (atrapa `--zaloguj`: `ekran`, `bezsesji`, `strata`; stub `zaloguj_postac.sh` nic nie loguje) oraz
`python3 testy/test_zaloguj_postac.py` (sam skrypt na atrapie: kody wyjścia, brak wywołań `uruchom.sh`/`mozg.py`/`zatrzymaj.sh`). Krok scenariusza
`zaloguj-stan:<id>` loguje stan guzika. Okno trzeba **uruchomić ponownie**, żeby guzik się pojawił (sam skrypt działa od razu).

## Spotkania z graczami (26.10)

Karol 26.10: „statystyki spotkań z graczami na spocie” w oknie. Układ „karta + zakładka”. **Ratunek jest wyłączony z menu** (`RATUNEK_HAIKU=0` u wszystkich; `RatunekView.qml`
zostaje w plikach, nieużywany, `Backend` go nie odpytuje); w jego miejscu zakładka **Spotkania** (`SpotkaniaView.qml`, model `SpotkaniaModel.js`).

- **Karta postaci** (pasek boczny, pod HP/MP i linią blanków/run, oddzielone cienką linią): `👥 spotkań 1/3 · Statutum ×1` (licznik n/PRÓG od ostatniego startu bota i najczęstszy gracz;
  n >= próg = bursztyn `Theme.warn` i pogrubienie) oraz `na spocie 1h 24m · 0,7/h` (czas na spocie od startu i spotkań na godzinę, po 10 minutach na spocie). Brak danych (bot stoi, inna
  sesja bota niż bieżąca, jeszcze nie policzone, telemetria nieświeża): `👥 spotkań -` i `na spocie - · -/h`, powód w podpowiedzi po najechaniu; karta postaci poza grą bez linii.
- **Zakładka Spotkania**: tabela per postać (Postać, Na spocie, Graczy, Spotk. n/próg, /h, Bywalec ×n; kolejność i ukrywanie straconych jak w Przeglądzie, klik wybiera postać),
  „Czas i tempo” wybranej postaci (na spocie od startu, spotkań/h, exp/h, zabicia/h), „Zmiany spotu · dziś” (godzina, postać, z którego na który spot, powód, status: wykonano / tylko zapis
  (cień) / błąd / zostaje) i „Unikane spoty” (spot, gracz, czas do końca 3 h); w nagłówku chip „ostatnio: nick · godzina · postać”. Bez „Historii dnia”. Plakietka w menu = ile postaci na progu.
- **Dane** (zaplecze `spotkania_okno.py`, TYLKO odczyt, nic nie zapisuje w `instancje/*`): licznik, czas i tempo z `narzedzia/spotkania_graczy_raport.py` (telemetria, te same reguły co bot),
  a gdy `instancje/<id>/spotkania_graczy.json` jest z bieżącej sesji bota (klucz `sesja` = pid działającego bota), licznik z pliku bota (`zrodlo: bot`). Zmiany spotu: dziennik nadzorcy
  `nadzor-RRRRMMDD.jsonl` (spot-gracz / spot-gracz-powrot / spot-gracz-brak), unikane i limity: `nadzor_stan.json`. `stan` niesie lekką sekcję `spotkania` (tylko z cache), polecenie
  `okno_api.py spotkania` pełne dane; cache w katalogu runtime (`$XDG_RUNTIME_DIR/retronic-okno-spotkania-*.json`, TTL 60 s, flock), błąd = `dostepne: false` z powodem, okno się nie wysypuje.
- **Wiarygodność**: wpis ma `dostepne: true` tylko gdy bot instancji działa TERAZ, jego pid jest pidem próbek telemetrii liczonej sesji i `ostatnie.json` `sesja.start` zgadza się z sesją telemetrii;
  `stan` sprawdza to przy każdym odczycie (restart bota natychmiast kasuje liczby starej sesji z karty). Granice: telemetria nie niesie listy wrogów PK ani czaszek, więc raport liczy więcej niż
  bot; licznik bota po zleceniu zmiany spotu startuje od zera; spotkań/h tylko po 10 minutach na spocie. Pełna lista w stopce zakładki (`granice` z API).
- Testy: `okno/test/Spotkania.test.js` (model + kontrakt na atrapie `atrapa.py --spotkania`), `testy/test_okno_api.py` (sekcja spotkania), `qml-atrapa.sh` scenariusz I. Cofnięcie: kopie `*.bak-20261026-spotkania-okno`
  i przywrócenie `RatunekView` w menu (`Sidebar.qml`, `shell.qml`, `Backend.setSection/refreshSection`).

## Testy

```bash
node --test okno/test/*.test.js            # model, polecenia i zapis/cofnięcie na atrapie (OknoModel + UstawieniaModel + Sesja)
okno/test/qml-atrapa.sh KATALOG_WYNIKOW    # Quickshell offscreen na atrapie: zrzuty PNG + dziennik wywołań stubów (Ratunek, Mapa i tryb, akcje)
okno/test/qml-ustawienia.sh KATALOG_WYNIKOW  # to samo dla Ustawień i palety: zapis przez prawdziwy okno_api, asercje na plikach atrapy
okno/test/qml-sesja.sh KATALOG_WYNIKOW       # Sesja gry i karty: zrzuty (główna, działająca z podglądem, zatrzymana, błąd profilu, IP spoza profilu, potwierdzenie Zamknij), asercje na dzienniku stubów sesja_gry.py
okno/test/klawisze-sway.sh KATALOG_WYNIKOW   # prawdziwe klawisze (Ctrl+K, pisanie, ↑↓, Enter, Esc) w headless sway: wtype + grim, bez okna na pulpicie
/usr/lib/qt6/bin/qmllint okno/*.qml
```

Atrapa (`okno/test/atrapa.py`) to katalog tymczasowy z własnym `panel.py`, atrapą `/proc` i stubami skryptów, które tylko logują
wywołanie. Opcja `atrapa.py KATALOG [N] --sesja` dokłada instancje do testu Sesji gry (`dzial`: działa, bot działa, podgląd otwarty, IP zgodne; `ipzle`: podgląd zamknięty, IP spoza profilu;
`bezprofilu`: brak profilu), a stub `sesja_gry.py` przestawia tylko pliki atrapy (`run/`, atrapa `/proc`), więc po „Uruchom grę” okno widzi sesję wstającą. Atrapa ustawia też
`XDG_RUNTIME_DIR` na własny katalog, więc `okno_api.py sesja` w testach nigdy nie czyta prawdziwych sesji. Zmienne: `RETRONIC_OKNO_KATALOG` (dane i skrypty akcji), `RETRONIC_OKNO_PROC`, `RETRONIC_OKNO_OTWIERACZ`; tylko testy:
`RETRONIC_OKNO_SCENARIUSZ` (kroki, zob. `Scenariusz.qml`; F3: `grupa:`, `filtr:`, `ustaw:`, `suwak:`, `wpisz:`, `paleta…`, `stan`; F4: `sekcja:sesja`, `wybierz:<id>`, `klik:sesja-uruchom|sesja-zamknij|sesja-zamknij-potwierdz|sesja-podglad|nick-<id>`, `sesja-stan`), `RETRONIC_OKNO_ROZMIAR=WxH`. Odczyt na prawdziwych danych bez klikania:
`RETRONIC_OKNO_KATALOG=<pomocnik> QT_QPA_PLATFORM=offscreen RETRONIC_OKNO_SCENARIUSZ="czekaj:1500;zrzut:/tmp/a.png;koniec" quickshell -p okno`.
