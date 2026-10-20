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

Wybrana postać: `okno_api.py stan --instancja ID` co 2 s; wszystkie: `stan` co 5 s; otwarta sekcja (`ratunek`, `mapy-tryby`) co 5 s;
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
