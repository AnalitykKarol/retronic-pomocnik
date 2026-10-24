# Profil CPU strażników (odczyt, 24.10.2026 ~13:55-13:58)

Metoda: wyłącznie /proc (bez ptrace, sygnałów, py-spy - nie jest zainstalowany: `command -v py-spy` puste). Brak RPC od siebie do strażników.
Uruchomione procesy pomiarowe: tylko krótkie `python3 -I samp.py` i pętle bash `grep /proc/...`; wszystkie zakończone.
Strażniki działające: 6 (marianni 748232, odchyd 1231481, borsuk 1257094, invincible 1306379, wydra 1437057, gebelish 2397366), po 3 wątki każdy.
Manifest wdrożenia (.ai/cpu-wdrozenie.json): scan, chat, pid - wszystkie włączone.

## 1. CPU per wątek (45 s, /proc/<pid>/task/<tid>/stat, utime+stime)

| instancja | wątek skanera `_petla_skanera` (user + sys) | wątek RPC `serwer` | wątek główny |
|---|---|---|---|
| marianni | 0.083 + 0.167 = 0.250 | 0.008 | 0.012 |
| odchyd | 0.089 + 0.191 = 0.280 | 0.036 | 0.011 |
| borsuk | 0.118 + 0.255 = 0.373 | 0.018 | 0.010 |
| invincible | 0.115 + 0.247 = 0.362 | 0.008 | 0.011 |
| wydra | 0.093 + 0.189 = 0.282 | 0.063 | 0.011 |
| gebelish | 0.085 + 0.180 = 0.265 | 0.004 | 0.000 |
| **suma** | **1.812 rdzenia (90 %)** | 0.137 | 0.055 |

Łącznie 2.003 rdzenia (`total_cores 2.003` w wyniku skryptu). Wątek skanera to jedyna istotna pozycja; stan `S`/`R` na przemian, ~2/3 jego czasu to system (kopiowanie pamięci przez `/proc/<pid>/mem`), ~1/3 użytkownik (filtr kandydatów w C + dekodowanie).
Wątek skanera: rdzen.py:911 `_petla_skanera` -> `Pamiec.skaner_krok` (rdzen.py:623) -> `_skanuj_stwory` (rdzen.py:469, 476).

## 2. Szybkie skany to właśnie ta reszta

Log logi/rdzen-skan.log, okno 15 min (do 13:56:10), suma `szybki xN * srednio` / czas okna:

| instancja | szybkich skanów/s | średnio s/skan | rdzeń-czasu (wall) | zapytań o stwory/s | z cache |
|---|---|---|---|---|---|
| borsuk | 2.27 | 0.168 | 0.381 | 3.62 | 99 % |
| invincible | 2.17 | 0.152 | 0.331 | 3.50 | 98 % |
| wydra | 2.58 | 0.124 | 0.319 | 5.25 | 81 % |
| gebelish | 2.29 | 0.116 | 0.264 | 3.41 | 99 % |
| odchyd | 2.26 | 0.114 | 0.259 | 3.43 | 98 % |
| marianni | 2.26 | 0.104 | 0.235 | 3.50 | 99 % |
| **suma szybkich** | | | **1.789** | | |
| pełne (427 w 900 s, wszystkie instancje) | 0.47/s łącznie | 0.219 | **0.104** | | |

Czyli ~1.79 rdzenia to szybkie skany, 0.10 to pełne (zgadza się z pomiarem 0.09). Skan jest CPU-bound: wall = CPU (0.124 s CPU/skan z wątku vs 0.13 s wall w logu).
Rozbicie 1.84 (pomiar bieżący): ~1.81 wątki skanerów + ~0.19 RPC/główny.

## 3. Ile pamięci czyta jeden szybki skan

`/proc/<pid>/io` per wątek (10 s, odchyd): wątek skanera rchar 625.8 MB/s, syscr 89/s; wątek RPC 0.0 MB/s, 120 syscr/s; główny 0.1 MB/s, 1499 syscr/s.
Całe procesy (20 s): 509 / 624 / 854 / 769 / 636 / 581 MB/s, razem 3.97 GB/s odczytu cudzej pamięci.
625 MB/s / 2.26 skanów/s = ~277 MB na skan (odchyd). Regiony rw poniżej 4 GB gry odchyd: 174 regionów, 450 MB razem (`/proc/1231638/maps`); największe 101, 66, 47, 31, 19 MB. Szybki skan czyta więc ~60 % całej pamięci rw gry, żeby znaleźć kilka struktur stworów.
Koszt: ~0.124 s CPU/skan = ~0.08 s kopiowanie w kernelu (sys, ~3.4 GB/s) + ~0.04 s filtr kandydatów w C (rdzen_skan.kandydaci) i reszta.
Liczba regionów w szybkim skanie (log, 80 wpisów/instancję): borsuk 9, invincible 6-7, gebelish 6, marianni 5-6, wydra 4, odchyd 2-4. Czas skanu zależy od ROZMIARU regionów, nie liczby (borsuk 9 reg. = 0.165 s; wcześniej 10:45 marianni 1 region = 0.009 s).

## 4. Skąd 2.26 skanu/s - kadencja

Wszystkie instancje mają SKAN_WIEK_WALKA = SKAN_WIEK_SPOKOJ = 0.5 (instancje/*/na_zywo.json; `cavebot.skan_rytm` cavebot.py:4013 zwraca wtedy None, bot nie wysyła pola "rytm"). Skaner planuje więc pod WIEK_STWORY/WIEK_PUSTO = 0.5 s (rdzen.py:421-422):
okres = 0.5 - czas_skanu(~0.13) - ZAPAS_SKANU 0.05 (rdzen.py:425, :636) = sen ~0.32 s + skan 0.13 s = ~0.45 s -> 2.2 skanu/s. To zgadza się z logiem (2.17-2.58/s).
Skaner pracuje tylko gdy ktoś pytał o stwory w ostatnich 20 s (SKANER_BEZCZYNNY, rdzen.py:~433/624), czyli zawsze, gdy bot żyje.

## 5. RPC (kto pyta)

- Zapytania `stwory` do strażnika: 3.4-3.6/s na instancję (5.25/s wydra), 98-99 % obsłużone z cache (81 % wydra). Źródło: cavebot.py:4021 `stwory()` (obieg bota, wiele wywołań: 5190 `PAMIEC_SKAN_WIEK` 0.4, 6507 0.8, 9000/9233 `PK_SKAN_WIEK` 0.25, 4122/9823 0.3, 1741/2071/5188 `maks_wiek=0.0` = świeży skan w wątku RPC); bot.py:155 (pościg). runa_klik.py:401 też `maks_wiek=0.0`.
- Zapytania z `maks_wiek=0.0` (wydra: 19 % poza cache = ~1 skan/s w wątku RPC) to jedyne skany poza wątkiem skanera; wątek RPC wydry: 0.063 rdzenia (najwięcej z RPC). Reszta wątków RPC 0.004-0.036.
- RPC `gracz`, `pozycja`, `stwor`, `kontenery`, `wiadomosci`: wątek RPC zużywa łącznie 0.137 rdzenia na 6 strażników, więc całość RPC (poza skanami) to pomijalna pozycja. Częstotliwości tych poleceń: UNKNOWN (strażnik ich nie loguje; bez strace nie da się policzyć). Inni klienci (nadzór, panel, trade_logger co 5 s, powiadom_czat, monitor_wykrycia) - skala wątku RPC pokazuje, że nie są źródłem.
- Główny wątek: 1499 syscr/s przy 0.011 rdzenia na strażnika (0.055 razem). Wygląda na przebieg po /proc (~740 procesów) co ok. sekundę - najpewniej `znajdz_gre`/`potomkowie` (rdzen.py:48, 81) wołane z pętli (straznik.py:~110) mimo cache PID. Przyczyna UNKNOWN (nie mierzono, czy `ProcesGry.sprawdz` ciągle chybia); koszt 0.055 rdzenia razem.

## 6. Pozycje do uwagi

1. **Szybki skan = 1.79 rdzenia (89 % całości).** Miejsce: rdzen.py:476 `_skanuj_stwory_pod_zamkiem`, odczyt rdzen.py:392/408 (`os.preadv`), filtr rdzen_skan.py:65. Liczby: 2.2-2.6 skanu/s x ~277 MB x 6 instancji = ~3.97 GB/s odczytu; ~0.124 s CPU/skan.
2. **Kadencja 0.5 s = kompromis zgodny z domyślnymi pokrętłami** (SKAN_WIEK_*: 0.5/0.5; pokrętło SPOKOJ do 1.5 s istnieje, cavebot.py:767-768, zakres pokretla.py:212-213; skan wypada średnio co ~0.45 s). To nie jest wyciek ani błąd, tylko cena świeżości.
3. **Pełne skany 0.10 rdzenia** (rdzen.py:419-420; 0.47/s łącznie, 0.22 s każdy) - drugorzędne.
4. Główny wątek + RPC ~0.19 rdzenia razem - drugorzędne.

UNKNOWN: częstotliwość poleceń innych niż `stwory` per klient; dokładny podział czasu skanera między kernel/filtr/dekodowanie w Pythonie (tylko proporcja user:sys 1:2); przyczyna 1500 syscr/s głównego wątku; czy bot w stanach walki wymusza gęstszy skan (pole "rytm" nie jest wysyłane przy 0.5/0.5, więc dziś nie); rozkład kadencji w walce vs spokoju (log nie rozdziela).

## 7. Kierunki (bez wdrażania), ocena ryzyka dla jakości wykrywania

| kierunek | spodziewany zysk | ryzyko |
|---|---|---|
| a) SKAN_WIEK_SPOKOJ 0.5 -> 1.0-1.5 (istniejące pokrętło, wymaga rytmu z bota) | poza walką ~2x-3x mniej skanów (do ~-0.5..-0.8 rdzenia przy spokoju) | średnie: wolniejsze wykrycie wejścia moba/gracza/PK w spokoju o do 1 s; PK_SKAN_WIEK 0.25 i zapytania z krótkim `maks_wiek` wymuszają i tak świeżość |
| b) odchudzić zestaw regionów szybkiego skanu (wypychać regiony bez trafień od N minut, mniejszy REGIONY_STWOROW_MAX=12) | mniejsze MB/skan (nawet kilkukrotnie dla dużych regionów 100 MB) | średnie/wysokie: nowy stwór może zaalokować się w regionie spoza zestawu i do pełnego skanu (2 s pusto / 20 s w walce) go nie widać; potrzebny pomiar trafień per region |
| c) szybki skan tylko po znanych adresach stworów (`stwor_szybki`, rdzen.py:671, już używany w pościgu) + pełny skan rzadziej | skan z ~277 MB do KB | wysokie dla nowych stworów (pojawienie się) - wykrycie dopiero z pełnym skanem; niskie dla śledzenia już znanych |
| d) dłuższy `OKRES_PELNEGO_PUSTO` 2.0 -> 4-5 s | -0.05 rdzenia | niskie/średnie: wolniejsze znalezienie pierwszego stwora po zmianie piętra |
| e) skan wyzwalany zdarzeniem (np. po zmianie pozycji gracza lub ramki), nie zegarem | duży w spokoju | wysokie: wymaga wiarygodnego wyzwalacza; mogą uciec stwory niezależne od gracza |

## 8. Dowody (komendy)

- `ps -eo pid,ppid,nlwp,comm,etimes,cputimes,args | awk '$4 ~ /^python/ && /straznik\.py/'` -> 6 strażników, 3 wątki każdy.
- Skrypt próbkujący /proc/<pid>/task/<tid>/stat co 45 s (jedno okno, dwa snapshoty; skrypt tymczasowy w scratchpadzie, nie zapisany w repo): wynik w sekcji 1.
- `grep -E '^(rchar|syscr)' /proc/<pid>/io` dla procesów i dla wątków (przed/po 10-20 s): sekcja 3.
- Statystyki logu: Python regex po ostatnich 900 s logi/rdzen-skan.log (941 linii): sekcja 2.
- `/proc/1231638/maps` (odczyt): 174 regionów rw < 4 GB, 450 MB.
- Odczyt kodu: rdzen.py (421-436, 469-560, 623-645, 911-935), straznik.py (68-120), proces_gry.py, cavebot.py:4013-4045.
- Nic nie zatrzymano, nie zrestartowano, nie zasygnalizowano; kod i konfiguracja bez zmian.
