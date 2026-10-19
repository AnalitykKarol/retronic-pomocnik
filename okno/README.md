# Okno zarządzania Retronic (QML, Quickshell) — faza F2

Spec: `wtyczka-paska/specs/2026-10-19-retronic-okno.md`. Osobny proces od paska; okno tylko czyta JSON z `okno_api.py` i woła
skrypty bota. F2 = szkielet, pasek boczny (karty postaci, menu sekcji, akcje), sekcje **Ratunek** i **Mapa i tryb**.
Sesja gry (F4) i Ustawienia (F3) są w menu wyszarzone.

## Uruchomienie

```bash
./okno.sh        # quickshell -p okno/ --no-duplicate; drugi start nie otwiera drugiego okna (w Hyprlandzie podnosi istniejące)
```

Zamknięcie okna kończy proces. Wejście skrótem/launcherem (`~/.config`, `.desktop`) to poziom 2, osobna zgoda.

## Odświeżanie

Wybrana postać: `okno_api.py stan --instancja ID` co 2 s; wszystkie: `stan` co 5 s; otwarta sekcja (`ratunek`, `mapy-tryby`) co 5 s.
Jedno wywołanie danego rodzaju naraz, wszystko asynchronicznie (`Job.qml`).

## Akcje

Stop/Start, ⌂ Miasto, ↻ Refill, ↗ Spot to dokładnie to, co na pasku: reguły szarości i polecenia z `../wtyczka-paska/RetronicModel.js`
(w `okno/` jest do niego symlink `RetronicModel.js`, bo Quickshell nie importuje plików spoza katalogu konfiguracji). „Start z tym” =
`uruchom.sh` z `MAPA`, `TRYB`, `RETRONIC_ID` (i `RETRONIC_POSTAC`, gdy znany nick), z potwierdzeniem; aktywny tylko gdy bot instancji
stoi, jest gra i nie trwa serwis. „To fałszywy alarm” = `okno_api.py ratunek-oznacz`. „Pokaż w logu” = otwieracz (`xdg-open`,
`RETRONIC_OKNO_OTWIERACZ`) na pliku `logi/ratunek-*.jsonl`; ścieżka z linią jest też w szczegółach.

## Testy

```bash
node --test okno/test/*.test.js            # model + polecenia na atrapie (28)
okno/test/qml-atrapa.sh KATALOG_WYNIKOW    # Quickshell offscreen na atrapie: zrzuty PNG + dziennik wywołań stubów
/usr/lib/qt6/bin/qmllint okno/*.qml
```

Atrapa (`okno/test/atrapa.py`) to katalog tymczasowy z własnym `panel.py`, atrapą `/proc` i stubami skryptów, które tylko logują
wywołanie. Zmienne: `RETRONIC_OKNO_KATALOG` (dane i skrypty akcji), `RETRONIC_OKNO_PROC`, `RETRONIC_OKNO_OTWIERACZ`; tylko testy:
`RETRONIC_OKNO_SCENARIUSZ` (kroki, zob. `Scenariusz.qml`), `RETRONIC_OKNO_ROZMIAR=WxH`. Odczyt na prawdziwych danych bez klikania:
`RETRONIC_OKNO_KATALOG=<pomocnik> QT_QPA_PLATFORM=offscreen RETRONIC_OKNO_SCENARIUSZ="czekaj:1500;zrzut:/tmp/a.png;koniec" quickshell -p okno`.
