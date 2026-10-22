# Analiza nadzorcy w trybie cienia — 21.10 17:40 do 22.10 14:06

Praca tylko do odczytu (kod `nadzor.py`, `podglad_nadzoru.sh`, dzienniki `nadzor-2026102[12].jsonl`,
logi botów, `obchod-podglad-20261022.log`). Nic nie uruchamiano ani nie zmieniano.

## 1. Co naprawdę włączają pliki

| Plik | Skutek w kodzie |
|---|---|
| `NADZOR_NAPRAWY` | Sprawdzany WYŁĄCZNIE w podkomendzie `napraw` (`main()`, ok. linii 1486-1500). Czyni `napraw <id> <rodzaj>` żywym, ale tylko dla `restart`, `wznow`, `relog`; inne rodzaje: odmowa, exit 3. `tick` (timer) go IGNORUJE i zostaje w cieniu. Sam plik nie uruchamia więc żadnej automatycznej naprawy. Realnym wywołującym jest dziś obchód AI (`podglad_nadzoru.sh`, Haiku co ok. 5 min, ustawia `NADZOR_NAPRAWY=1`). |
| `NADZOR_ZYWO` | Czyni żywym `tick` (sesja_start, zaloguj, start_bota, wroc, serwis, wyloguj, relog, restart, eskaluj + hold) oraz wszystkie rodzaje `napraw`. Zabezpieczenie B-1: przy wyciszonych powiadomieniach (plik `cisza` / `RETRONIC_POWIADOMIENIA=0`) tryb żywy nie startuje. |

Uwaga: faktyczny takt timera to ok. 5 min (wpisy 13:46:06, 13:55:22, 13:56:06, 14:01:08), nie "co minutę".
Dziennik cienia deduplikuje (ta sama decyzja najwyżej raz na 30 min, spot_podglad na 60), więc liczby poniżej to
zdarzenia dziennika, nie tiki.

Obchód AI ma zakaz `wroc`/`wyloguj`/`zmien_spot` oraz "GRAFIK ZMIAN IGNORUJ" (po incydencie 22.10 10:16:58) — to jedyny
powód, dla którego NADZOR_NAPRAWY jest bezpieczniejszy niż ZYWO.

## 2. Liczby (zdarzenia dziennika, 21.10 + 22.10)

| Rodzaj | Razem | TRAFNA | ZBĘDNA | BŁĘDNA | PRZEOCZONA | Nieustalone |
|---|---|---|---|---|---|---|
| wznow | 5 | 3 | 2 | 0 | 0 | 0 |
| restart (cień) | 3 | 1 | 2 | 0 | 0 | 0 |
| restart (odmowa: nadzor:false kolanoth) | 2 | 2 (słusznie odmówione) | 0 | 0 | 0 | 0 |
| relog | 1 | 0 | 0 | 1 (prawdopodobnie) | 0 | 0 |
| wroc | 21 (20 cień + 1 żywe) | 0 | 0 | 21 | 0 | 0 |
| wyloguj | 3 | 0 | 0 | 3 (1 pewna, 2 prawdopodobne) | 0 | 0 |
| serwis | 1 | 0 | 0 | 0 | 0 | 1 |
| sesja_start | 2 | 0 | 0 | 0 | 0 | 2 |
| eskaluj ("powrót > 40 min") | 3 | 0 | 0 | 3 (fałszywe) | 0 | 0 |
| "kręci się" / ratunek (nie zadziałał) | ok. 9 | 0 | 9 (samo ustąpiło; brak akcji był słuszny) | 0 | 0 | 0 |
| PRZEOCZONA (problem, nadzorca nic) | 0 | | | | 0 | |

Per postać (akcje inne niż czekaj):
- dawajkesh: wznow 4 (21.10 18:10 TRAFNA; 22.10 08:10 TRAFNA; 08:15 ZBĘDNA, artefakt cienia; 13:56 TRAFNA), restart 1 (08:15 ZBĘDNA), relog 1 (BŁĘDNA?), serwis 1 (nieustalone), sesja_start 1 (nieustalone), wroc 6 (BŁĘDNA), eskaluj 1 (BŁĘDNA).
- invincible: restart 2 (10:50 TRAFNA, probable; Karol zrestartował 10:52:53; drugi ZBĘDNY), wroc 10 (BŁĘDNA, w tym 1 żywe 10:16:58 i 1 z nieaktualnego grafiku 07:50), wyloguj 1 (13:16, BŁĘDNA prawdopodobnie).
- wydra: wroc 5 (BŁĘDNA), eskaluj 2 (BŁĘDNA), wyloguj 1 (12:46, prawdopodobnie BŁĘDNA).
- kolanoth: wznow 1 (21.10 20:16 TRAFNA, prawdopodobnie), restart 2 odmowy (`nadzor:false`, słusznie), wyloguj 1 (21.10 20:21, BŁĘDNA), sesja_start 1 (nieustalone; 22.10 08:15, w cieniu niewykonane).
- kutangen, gebelish: tylko `zablokowane`/ostrzeżenie; brak akcji do oceny.

## 3. Przykład dnia: dawajkesh 22.10 13:55

STOP po nieudanej drabinie w wyprawie, nadzorca w cieniu "zrobiłbym wznow", obchód AI zawołał `napraw wznow` 13:55:22,
człowiek wznowił 13:56. TRAFNA: bot stał po alarmie w wyprawie, wznowienie było właściwe i identyczne z tym, co zrobił
człowiek. Zastrzeżenie: wznow po alarmie wyprawy startuje bota w zwykłym trybie trasy ("Start: trasa N pkt") i
zapomina stan wyprawy do depo; tu wyszło dobrze, ale to ryzyko na przyszłość.

## 4. Decyzje BŁĘDNE (z dowodami)

1. **invincible 22.10 10:16:58 `wroc` (ŻYWE, przez obchód AI).** Powód: koniec zmiany z grafiku, bot zabijał normalnie.
   Skutek: ok. 35 min expa stracone, Karol odrzucił (reguła "o zejściu z expa decyduje Karol"). Po tym incydencie
   obchód dostał zakaz wroc/wyloguj/zmien_spot (`podglad_nadzoru.sh` linie 22-24).
2. **20 cieniowych `wroc` po końcu zmiany z grafiku** (invincible od 10:15 co ok. 30 min, dawajkesh od 10:50, wydra od 11:15),
   za każdym razem gdy boty normalnie biły potwory. W trybie ZYWO tick wykonałby je wszystkie. Sprzeczne z decyzją
   Karola, że grafik jest tylko informacją.
3. **invincible 22.10 07:50 `wroc` z nieaktualnego grafiku** (zmiana z wczoraj 19:56) podczas ręcznych startów.
4. **kolanoth 21.10 20:21 `wyloguj` ("postać w mieście (spokój)")** — postać stała w jaskini trolli z9. Przyczyna:
   `_bez_bota` liczy `w_depo` z linii logu "[IDZ] wyprawa do depo zakończona", którą bot drukuje także po alarmie/STOP
   w wyprawie. `dowod_miasta` staje się prawdą dla postaci zaklinowanej w jaskini, `_miasto` → `_wylogowanie`.
   Żywo: wylogowanie postaci w niebezpiecznym miejscu.
5. **Fałszywe eskalacje "powrót > 40 min"** (w trybie ZYWO: hold plus krytyczne powiadomienie): wydra 09:30 i 12:25,
   dawajkesh 11:20. Dowód: wydra w oknie 09:10-09:50 miała 31 zabić przed i 19 po zdarzeniu, WROC dostała dopiero
   09:27:43 (ręcznie, `wyprawa:depo:reczny`), dawajkesh o 11:20 miała 24 zabicia i grała do STOP 11:25:21, wydra 12:25:57
   w tym czasie szła w wyprawie po blanki (12:25:36 start, DEPO 12:28:11). Przyczyna: `_poza_gra` nie zeruje
   `powrot_od`/fazy POWROT przy obserwowanym polowaniu; stary stan WROC/wyprawy trzyma POWROT.
6. **dawajkesh 21.10 20:31 `relog`** — prawdopodobnie BŁĘDNA, nie dowiedziona: `logowanie.log` 20:08:00 "klient już w grze",
   brak ROZŁĄCZENIE w logach bota, ta sama sesja trwała do 07:45 następnego dnia. Warunek `rozl` lub ekran
   logowania/lista opierał się na przestarzałym sygnale.
7. **invincible 22.10 13:16 `wyloguj`** — prawdopodobnie BŁĘDNA: depo 13:09:36, "auto-refill: refill edron ruszy po
   zatrzymaniu bota", bot wystartował znów 13:26:14; wylogowanie 13:16 trafiłoby w trakcie serwisu.
8. **wydra 22.10 12:46 `wyloguj`** — prawdopodobnie BŁĘDNA: po wyprawie stała w depo (12:28:11, "brak planu serwisu
   dla tego miasta"), potem STOP_RECZNY 13:16 i ręczny start 13:35, czyli Karol z nią pracował.

## 5. Decyzje PRZEOCZONE

Nie znaleziono żadnej potwierdzonej. Sprawdzone i niezakwalifikowane:
- dawajkesh 22.10 08:30-08:52 zaklinowanie w (33080,31741,8) zakończone STOP (08:29:43) i STOP_RECZNY (Karol przejął);
  nadzorca słusznie nic nie robił (STOP_RECZNY).
- Wpisy "kręci się" (dawajkesh 11:49, 12:10, 13:05; wydra 11:42, 12:03; invincible 11:41, 13:54; gebelish 12:35, 12:53)
  ustępowały same; progi 8 min / 25 min były właściwe.
- Luka dziennika 21.10 20:31 do 22.10 07:45 (timer/PC wyłączone) uniemożliwia ocenę nocy.

## 6. Ocena obchodu AI (Haiku), 09:38-13:57, ok. 50 rund

1 naprawa żywa (błędny `wroc` 10:16:58, przed zakazem), potem 0 napraw żywych; `napraw wznow` 13:55 był w cieniu
(brak NADZOR_NAPRAWY). Odmowy i przepuszczenia zgodne z regułami; rundy zgłaszały DECYZJA/WYNIK: karol dla kolanoth
(offline od 20:14, `nadzor:false`) i wydry (stoi w depo).

## 7. Rekomendacja

### NADZOR_NAPRAWY: WŁĄCZYĆ (po drobnych warunkach)
Plik sam nic nie zmienia dla timera; włącza tylko `napraw restart|wznow|relog` wołane przez obchód AI. Wynik cienia:
wznow/restart 5 trafnych/ zbędnych bez żadnej szkody, żadnej błędnej naprawy z tej puli. Warunki:
1. Obchód zostaje z zakazem wroc/wyloguj/zmien_spot i ignorowaniem grafiku.
2. Dodać w `napraw restart|wznow` deterministyczne sprawdzenie, że istnieje zaciecie/alarm/STOP (dziś jedynym sędzią jest Haiku).
3. `napraw relog` ma sprawdzać świeżość sygnału rozłączenia i dla postaci OFFLINE respektować grafik, ciszę nocną, przerwę i limit dobowy (dziś `_relog` ich nie sprawdza).
4. Bramy STOP_RECZNY / `nadzor:false` / hold zostają (działały poprawnie, kolanoth).

### NADZOR_ZYWO: NIE (włączyć dopiero po poprawkach)
Żywy tick wykonałby 21 błędnych `wroc`, 3 błędne wylogowania, 1 relog i 3 fałszywe eskalacje z holdem w ciągu jednego dnia.
Poprawki przed włączeniem:
1. `w_depo` / `dowod_miasta`: nie liczyć "[IDZ] wyprawa do depo zakończona" po ALARM/STOP wyprawy; wymagać pozycji w mieście.
2. `_poza_gra`: zerować `powrot_od` i fazę POWROT, gdy bot obserwowanie poluje (zabicia/ruch na trasie); stary stan WROC/wyprawy nie trzyma POWROT.
3. Grafik koniec zmiany nie może wysyłać `wroc` botowi, który poluje; ignorować grafik z poprzedniego dnia; zgodnie z regułą Karola grafik tylko informuje (albo `wroc` tylko na jawne zlecenie).
4. `relog`: wymagać świeżego dowodu rozłączenia (ROZŁĄCZENIE w logu/ekran logowania ze świeżego odczytu).
5. `wyloguj`: nie w trakcie trwającego refill/serwisu, nie dla postaci z ostatnią aktywnością człowieka (STOP_RECZNY w ostatnich N min).
6. `relog` dla OFFLINE: respektować grafik, ciszę, przerwę, limit dobowy.
7. K3: brak serwisu dla Thais/Rook ("brak planu serwisu dla tego miasta") — dla tych postaci nie wolno planować serwisu ani wylogowania "po serwisie".
8. Po poprawkach co najmniej jedna doba czystego cienia (0 BŁĘDNYCH z puli wroc/wyloguj/eskaluj), potem włączenie etapami (np. najpierw sesja_start/zaloguj/start_bota, na końcu wroc/wyloguj).

## 8. Czego nie ustalono

- dawajkesh 21.10 20:10 `serwis`: Karol zalogował się ręcznie 20:07, brak logów bota 19:00-20:45; nie da się ocenić.
- `sesja_start` (dawajkesh 21.10 18:55, kolanoth 22.10 08:15): w cieniu niewykonane, brak kontrfaktu.
- dawajkesh 21.10 20:31 `relog`: BŁĘDNA tylko wnioskowana z braku ROZŁĄCZENIA, bez bezpośredniego dowodu.
- kolanoth 21.10 20:16 `wznow` TRAFNA tylko prawdopodobnie (Karol potem ustawił `nadzor:false` do 24.10 08:30).
- Noc 21/22.10 (luka dziennika), runda obchodu 09:18:17 (błąd "Input must be provided"), niewczytany `monitor-wykrycia-20261022.log`.
- Czy `zaloguj.sh` po `relog` startuje też bota, nie sprawdzono do końca.
- Różnica "co minutę" (opis zadania) vs. ok. 5 min (dziennik).
