# Okno zarządzania Retronic (QML, Quickshell) — fazy F2 i F3

Spec: `wtyczka-paska/specs/2026-10-19-retronic-okno.md`. Osobny proces od paska; okno tylko czyta JSON z `okno_api.py` i woła
skrypty bota. F2 = szkielet, pasek boczny (karty postaci, menu sekcji, akcje), sekcje **Ratunek** i **Mapa i tryb**.
F3 = sekcja **Ustawienia** (edycja pokręteł) i wyszukiwarka **Ctrl+K**. Sesja gry (F4) jest w menu wyszarzona.

## Uruchomienie

```bash
./okno.sh        # quickshell -p okno/ --no-duplicate; drugi start nie otwiera drugiego okna (w Hyprlandzie podnosi istniejące)
```

Zamknięcie okna kończy proces. Wejście skrótem/launcherem (`~/.config`, `.desktop`) to poziom 2, osobna zgoda.

## Odświeżanie

Wybrana postać: `okno_api.py stan --instancja ID` co 2 s; wszystkie: `stan` co 5 s; otwarta sekcja (`ratunek`, `mapy-tryby`) co 5 s.
Jedno wywołanie danego rodzaju naraz, wszystko asynchronicznie (`Job.qml`).

## Ustawienia (F3)

Wybrana w pasku bocznym postać wyznacza instancję; zapis idzie do jej `na_zywo.json` (bot czyta plik na żywo, bez restartu).
Zapis **od razu** po puszczeniu suwaka, kliknięciu przełącznika albo przycisku wyboru, Enterze w polu liczby (decyzja Q3, bez „Zapisz”);
pod listą stoi wynik ostatniej zmiany i **Cofnij ostatnią** (jeden wpis dziennika `okno_cofnij.jsonl`; zestaw run to jeden wpis).
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

## Akcje

Stop/Start, ⌂ Miasto, ↻ Refill, ↗ Spot to dokładnie to, co na pasku: reguły szarości i polecenia z `../wtyczka-paska/RetronicModel.js`
(w `okno/` jest do niego symlink `RetronicModel.js`, bo Quickshell nie importuje plików spoza katalogu konfiguracji). „Start z tym” =
`uruchom.sh` z `MAPA`, `TRYB`, `RETRONIC_ID` (i `RETRONIC_POSTAC`, gdy znany nick), z potwierdzeniem; aktywny tylko gdy bot instancji
stoi, jest gra i nie trwa serwis. „To fałszywy alarm” = `okno_api.py ratunek-oznacz`. „Pokaż w logu” = otwieracz (`xdg-open`,
`RETRONIC_OKNO_OTWIERACZ`) na pliku `logi/ratunek-*.jsonl`; ścieżka z linią jest też w szczegółach.

## Testy

```bash
node --test okno/test/*.test.js            # model, polecenia i zapis/cofnięcie na atrapie (OknoModel + UstawieniaModel)
okno/test/qml-atrapa.sh KATALOG_WYNIKOW    # Quickshell offscreen na atrapie: zrzuty PNG + dziennik wywołań stubów (Ratunek, Mapa i tryb, akcje)
okno/test/qml-ustawienia.sh KATALOG_WYNIKOW  # to samo dla Ustawień i palety: zapis przez prawdziwy okno_api, asercje na plikach atrapy
okno/test/klawisze-sway.sh KATALOG_WYNIKOW   # prawdziwe klawisze (Ctrl+K, pisanie, ↑↓, Enter, Esc) w headless sway: wtype + grim, bez okna na pulpicie
/usr/lib/qt6/bin/qmllint okno/*.qml
```

Atrapa (`okno/test/atrapa.py`) to katalog tymczasowy z własnym `panel.py`, atrapą `/proc` i stubami skryptów, które tylko logują
wywołanie. Zmienne: `RETRONIC_OKNO_KATALOG` (dane i skrypty akcji), `RETRONIC_OKNO_PROC`, `RETRONIC_OKNO_OTWIERACZ`; tylko testy:
`RETRONIC_OKNO_SCENARIUSZ` (kroki, zob. `Scenariusz.qml`; F3: `grupa:`, `filtr:`, `ustaw:`, `suwak:`, `wpisz:`, `paleta…`, `stan`), `RETRONIC_OKNO_ROZMIAR=WxH`. Odczyt na prawdziwych danych bez klikania:
`RETRONIC_OKNO_KATALOG=<pomocnik> QT_QPA_PLATFORM=offscreen RETRONIC_OKNO_SCENARIUSZ="czekaj:1500;zrzut:/tmp/a.png;koniec" quickshell -p okno`.
