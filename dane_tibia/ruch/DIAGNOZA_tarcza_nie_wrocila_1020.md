# Problem: UH zdjął tarczę i jej nie założył (20.10 08:09, Mastafian)

Status: **POPRAWKA NAPISANA I PRZEJRZANA (2 rundy), NIEWDROŻONA** — branch `fix/uh-tarcza-ratunek` (worktree `../pomocnik-uh-tarcza`, commity `83f5dcb` + `224994a`, baza `2395bef`); testy UH 138/138, 90/90, 30/30, 59/59, pełny zestaw bez nowych czerwonych. Kroki 1–5 i 7 zrobione, krok 6 (sygnał na pasku) NIE. Czeka na decyzję Karola: merge do `ruch-r1-1014` + restart botów. Nic nie sprawdzone na żywo (progi ikon do zmierzenia). Doraźnie naprawione ręcznie 20.10. Zgłosił Karol 20.10 ~08:14: „ma tarcze w bagu i nie robi run”.

## Co się stało (dowody: `logi/mozg-20261020-0733.log`)

- 07:41–08:03: pięć cykli runy OK (tarcza do plecaka → blank do ręki → `adura vita` → runa do plecaka → tarcza do ręki).
- 08:09:35 `tarcza_do_plecaka` OK (pole 5). 08:09:37–39 `blank_do_reki` BŁĄD: `bez ruchu: ekran != pamięć (runy): pole 6: pamięć ma przedmiot 3160, na ekranie pusto`; `przerwanie: blank runa nie trafia do slotu`.
- 08:09:40–44 `tarcza_do_reki` ×2 i `tarcza_ratunek_ruch` BŁĄD: `ekran != pamięć: pole 6: pamięć ma pusto, na ekranie przedmiot` (plecak). `tarcza_nie_wrocila`.
- 08:09:48 ALARM `UH: tarcza poza slotem`, `wyłączam UH na 30 min` (`cavebot.py` ~1997, `UH_PRZERWA_PO_PORAZKACH_S` = 1800).
- Zrzut 08:14: slot tarczy pusty, tarcza w Backpacku (pole 1), w Backpacku pole 6 fioletowy przedmiot; HP 250/250, bot dalej walczy bez tarczy. Komunikat gry „Sorry, not possible.”.

## Przyczyny (potwierdzone w kodzie) i luki

1. **Ratunek używa tej samej kontroli co zwykły ruch.** `_ratunek` → `_przeciagnij` → `_przed_ruchem` odmawia, gdy pamięć klienta ≠ ekran w polu źródłowym. To dokładnie ten rozjazd, który zepsuł cykl, więc ratunek też odmawia (`tarcza_ratunek_ruch BŁĄD`, `uh.py` ~808–840).
2. **Kontrola „slot pusty, tarcza w plecaku → załóż” (`uh.naprawa`) działa raz po starcie bota** (`cavebot.py` ~1922, flaga `uh_naprawa_ok`). Po alarmie nikt jej nie ponawia.
3. **Pauza po alarmie 30 min** blokowała ponowną próbę (zmienione lokalnie na 60 s, patrz niżej).
4. **Restore po restarcie nie działa w jaskini.** `uh_stan.json` trzyma `tarcza_id`, ale `mozna_robic` blokuje restore, gdy w widoku jest jakikolwiek obcy byt (gobliny) — nigdy nie ma „spokoju”. Trzeba było wyczyścić plik ręcznie.
5. **Alarm tylko w logu/powiadomieniu**, brak trwałego sygnału na pasku, że postać walczy bez tarczy.

NIE ustalone: czemu pamięć klienta rozjechała się z ekranem o 08:09 (pole 6 w runach i w plecaku) po pięciu udanych cyklach; co to za fioletowy przedmiot w Backpacku pole 6 (hipoteza: runa `adura vita` 3160, która trafiła do Backpacka zamiast do pojemnika na runy).

## Naprawa doraźna (wykonana 20.10 ~08:20, za zgodą Karola)

1. `./zatrzymaj.sh` (tylko Mastafian), `rm STOP STOP_RECZNY`.
2. Tarcza ręcznie z Backpacka do slotu przez `ekran.Mysz().przeciagnij(1058,331 → 1091,200)`; pierwsze przeciągnięcie bez najechania kursorem dało „Sorry, not possible.”, drugie (najpierw `ruch` na źródło, 0,4 s pauzy) przeszło. Zrzut potwierdził tarczę w slocie.
3. `echo '{}' > uh_stan.json` (kopia `uh_stan.json.bak-20261020-restore`), `./uruchom.sh`. Log: `kontrola tarczy na starcie: ok`, 08:27:28 pierwsza runa po zmianie progu, cykl 4 s OK.

## Zmiany konfiguracji tej sesji

- `cavebot.py` (linie 326 i 340, kopia `.bak-20261020-uh-przerwa`): `UH_PRZERWA_PO_PORAZKACH_S` 1800 → 60. Decyzja Karola („30 min to żart”). Bez commita.
- `na_zywo.json` (kopia `.bak-20261020-uh-margines`): `UH_W_WALCE_MANA_MARGINES` 5 → 50 (maks. zakresu w `pokretla.py:267`). Karol: exura kosztuje 25, many ~400, więc próg może być dużo niższy; zostawione na 50 „na razie”. Opcja: zakres do 300 (próg ≈125) wymaga zmiany kodu + restartu.

## Kroki do naprawy kodu (propozycja, kolejność)

1. **Test regresji najpierw** (`testy/`): symulacja „po `tarcza_do_plecaka` pamięć ≠ ekran w polu plecaka”; oczekiwane: tarcza wraca do slotu w <= N s, UH nie zostaje z pustym slotem. Wersja czerwona na obecnym kodzie.
2. **Ratunek bez kontroli pamięci:** gdy slot pusty, a ikona tarczy jest na zrzucie w plecaku, przeciągnij po pozycji z ekranu (ikona), z odświeżeniem pamięci (`odswiez_ekwipunek`) i hoverem przed chwytem; weryfikacja wyniku zrzutem slotu, nie pamięcią.
3. **Ponawianie naprawy po alarmie:** `uh.naprawa` co `UH_NAPRAWA_PONOW_S` (np. 15–20 s), dopóki slot pusty i tarcza w plecaku, niezależnie od pauzy na robienie runy; `uh_naprawa_ok` nie ustawiać na stałe po jednej próbie.
4. **Restore w walce:** `uh_restore` ma działać także z obcymi bytami w widoku, jeśli nie są blisko (inny próg niż tworzenie runy), bo postać bez tarczy jest słabsza.
5. **Pauza po alarmie** 60 s tylko dla robienia runy; naprawa tarczy niezależna (pkt 3). Zacommitować zmianę stałej razem z testem.
6. **Sygnał dla człowieka:** stan „tarcza poza slotem” w `status.sh`/pasku (wtyczka `charlie.retronic`) i powiadomienie ponawiane, nie jednorazowe.
7. **Diagnoza rozjazdu pamięć/ekran:** zebrać do logu ekwipunek + kontenery tuż przed i po każdym kroku (jedna linia JSON), żeby przy następnym razie było widać, kto się rozjechał (klient czy `kontenery.py`).
