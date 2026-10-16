# Czaszka lokalnie (P7, SPEC R1): inwentarz danych, 16.10

Wniosek: **danych za mało na detektor, nie implementowano `czaszka_lokalna.py` ani `PK_CZASZKA_LOKALNA`.** Kolorów nie zgadujemy (UNKNOWN).

## Co jest (odczyt 16.10, `narzedzia/zbierz_czaszki.py`)

| Źródło | Biała | Czerwona | Żółta | Brak | Obrazy z czaszką |
|---|---|---|---|---|---|
| linie `Czaszka:` w `logi/mozg-*.log` (Haiku, etykieta słaba) | 2 (1 nick: Tojson) | 0 | 0 | 14 (5 nicków) | n/d |
| zapisane wycinki | 0 | 0 | 0 | 0 | 0 |

- Dodatkowo 12 odczytów `nieczytelne`. Łącznie 28 odczytów, 0 czerwonych, 0 żółtych.
- `logi/zrzuty/czaszka-cjczr3q7.png`: jedyny zachowany wycinek, to podłoga z workiem i rurą, bez postaci i bez czaszki (po oględzinach).
- `ikony/`, `ikony/nieznane/` (29 plików 32x32), `testy/dane/` (9 zrzutów ognia/UI): ikony przedmiotów i UI, zero czaszek.
- Klient (`klient/`) to RetronicGL.exe bez plików `.spr`, więc ikony czaszek nie da się wyciąć z zasobów.
- Wycinek z odczytu jest kasowany zaraz po wywołaniu modelu (`CzytnikCzaszki.odczytaj`, `finally`), dlatego z 28 odczytów nie został żaden obraz.

## Czego brakuje

Obrazów wycinka przy nicku z etykietą: biała, czerwona, żółta (jeśli serwer jej używa) i brak, min. 30 na klasę (próg w `zbierz_czaszki.py --min`), z różnych teł i godzin. Kształt i kolor ikony w tym kliencie (rozmiar w px, odcień, położenie względem nicku/paska HP) to nadal UNKNOWN. Bez dokładności zmierzonej na takim zbiorze nie ma podstaw do włączenia detektora na ścieżce ucieczki.

## Co dodano

- `narzedzia/zbierz_czaszki.py`: offline, tylko odczyt; tabela próbek per klasa i werdykt "wystarczy / brakuje N". `python3 -I narzedzia/zbierz_czaszki.py`.
- `czaszka.py`: `CZASZKA_ZAPIS_PROBEK` (env, domyślnie 0). Przy 1 każdy wycinek zapisuje się do `logi/czaszki/<wynik>/<nick>-<czas>.png` (katalog w .gitignore przez `logi/`). Etykieta = odpowiedź Haiku, więc przed treningiem przejrzeć ręcznie (zwłaszcza `biala`/`czerwona`). Koszt zero ponad dotychczasowe odczyty; zachowanie bota bez zmian. Pokrętło nie jest w `pokretla.py`, bo jak `CZASZKA_ODCZYT` czyta env w czytniku, nie stałą cavebota.
- `testy/test_zbierz_czaszki.py` (10 testów).

## Następny krok (decyzja Karola)

Włączyć `CZASZKA_ZAPIS_PROBEK=1` na żywym bocie (wymaga restartu, poziom 2) i zbierać, aż `zbierz_czaszki.py` pokaże "WYSTARCZY"; dopiero wtedy P7 w pełnej formie. Alternatywa: ręczne zrzuty wycinków z czaszkami do `logi/czaszki/<klasa>/`. Do tego czasu czaszkę czyta Haiku (3-4 s), czyli SPEC R1 nie jest domknięty.
