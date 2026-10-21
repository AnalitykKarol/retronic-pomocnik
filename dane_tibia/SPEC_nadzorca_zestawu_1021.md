# SPEC: nadzorca zestawu (grafik zmian + pilnowanie botów) - 21.10 — ZATWIERDZONA (Karol 21.10 ~07:40: „ok” na propozycje Q1–Q8)

Cel: zestaw instancji gra według grafiku, bez Karola przy klawiaturze. Postacie logują się i wylogowują pojedynczo,
o różnych porach, nigdy wszystkie naraz. Ktoś pilnuje, żeby boty działały, naprawia drobne zawieszki, a Karola woła tylko,
gdy trzeba człowieka. Zlecenie Karola 21.10 ~07:10: „żebyś ich pilnował, odpalał i jakiś plan, żeby wszystkie na raz się
nie logowały i nie wylogowywały, bo to będzie dziwne”; po ocenie: „raczej odpalimy jakąś sesję Sonneta do tego”.

## Stan dzisiaj (zmierzone 21.10 ~07:20)

- Sześć instancji z profilem i własnym proxy: `invincible`, `kutangen`, `dawajkesh`, `kolanoth`, `bober`, `wydra`.
  `wydra` nie ma konta ani postaci; `dawajkesh` i `kolanoth` nie mają `konto` w `profil.json`.
- Start sesji: `RETRONIC_ID=<id> sesja_gry.py start` (sprawdza IP proxy, otwiera Remminę). 21.10 07:11–07:18 sześć startów
  po kolei, odstępy 63–116 s, wszystkie z IP zgodnym z profilem (`okno_api.py sesja`). Skrypt jednorazowy, poza repo.
- Logowanie postaci: **ręcznie** w podglądzie. Skryptu brak. Klienty mają `autoReconnect: true` i zapisany login.
  Czy po starcie klienta wystarczy Enter na ekranie logowania i Enter na liście postaci: **niezmierzone**.
  21.10 07:27 (zrzut `grim`, kutangen i kolanoth): po starcie klient stoi na „Enter Game” z wypełnionym kontem i hasłem
  („Remember password” zaznaczone), serwer Retronic 7.4, świat Danubia.
- **F0 pomiar logowania (21.10 07:34–07:36, kutangen, ekran 1175x910, XTEST na DISPLAY instancji):**
  - sam Enter na ekranie „Enter Game”: **bez skutku** przez 12 s (formularz bez fokusu klawiatury);
  - klik w „Login” (588,594) → „Character List” z jedną postacią (zaznaczona) po ≤ 2,2 s;
  - klik w „Ok” (641,628) → w grze po 0,8 s (wykrycie: ikony paska klienta, piksele W-80,17 / W-50,17, jak w prototypie
    wylogowania). Kutangen pojawił się w świątyni Rooka, HP pełne, lvl 7 (po zgonie 20.10). Razem ok. 3 s.
  - Wniosek dla `zaloguj.sh`: kliki zamiast Enter; **zrzut i rozpoznanie ekranu tuż przed każdym klikiem** (07:33 Enter
    wysłany do kolanotha, którego Karol zalogował minutę wcześniej, trafił do gry: „Sorry, not possible.”); współrzędne
    zależą od rozmiaru sesji, więc przycisk szukać na zrzucie albo sprawdzać rozmiar przed klikiem.
- Wylogowanie: tylko prototyp `narzedzia_jednorazowe/wyloguj_prototyp_1020.py` (Ctrl+L, po zniknięciu ikon paska klienta
  natychmiast `sesja_gry.py zamknij`, bo autoReconnect loguje z powrotem w < 60 s). `wyloguj.sh` to F2 specu
  `SPEC_powrot_rook_1020.md`, niezrobione.
- Powrót do miasta na Rooku: niezrobiony (`wyprawa.BAZY` = `troll`, `thais_kanaly`), F1 tego samego specu.
- Bot: `uruchom_instancje.sh <id> <MAPA> [TRYB]`, stan w `panel.py --json` (z `RETRONIC_ID`), alarm gracza w logu
  (`ALARM_GM|ALARM: gracz`), powiadomienia `powiadom.py`. 20.10 Kutangen zginął, a bot kręcił się 1 h 40 min na ekranie wyboru
  postaci (`SMIERC_STOP` nie zadziałał na tym ekranie).
- Maszyna: 20 rdzeni, 31 GB RAM (przy 6 sesjach ok. 9 GB zajęte), Claude Code 2.1.300 (`claude -p --model sonnet`).

## Proponowane zachowanie: trzy warstwy

Zasada: **co da się zrobić deterministycznie, robi skrypt; Sonnet ocenia i naprawia odchylenia.** Model nie wymyśla godzin
i nie klika po oknie gry.

### A. Grafik (`grafik.py`, deterministyczny)

- Raz na dobę (i na żądanie) generuje `instancje/_wspolne/grafik-RRRRMMDD.json`: dla każdej postaci w grafiku zmiany
  `{od, do, mapa, tryb}`.
- Reguły (wartości do Q1): długość zmiany losowa w widełkach; najwyżej N postaci naraz; między **dowolnymi dwoma**
  logowaniami albo wylogowaniami co najmniej X min (losowo X–Y); pory przesuwają się z dnia na dzień (nie codziennie 08:00);
  postać nie gra dłużej niż limit dzienny; okna ciszy (np. noc).
- Podgląd: `python3 -I grafik.py pokaz` (tabela na dziś), `grafik.py nowy --od-teraz` po zmianie zasad.
  Ręczna edycja pliku przez Karola jest dozwolona i wygrywa.

### B. Wykonawca (`nadzor.py`, deterministyczny, timer systemd użytkownika co ~1 min)

Prowadzi każdą postać przez cykl:
`sesja_gry.py start` → `zaloguj.sh` (nowy) → `uruchom_instancje.sh <id> <mapa> <tryb>` → na koniec zmiany `wroc.sh`
→ po STOP w mieście `wyloguj.sh` → sesja zamknięta.

- **Jedna akcja logowania/wylogowania naraz** w całym zestawie (blokada pliku w `_wspolne/`), odstęp z grafiku.
- **Blokady w kodzie, nie w promptcie:**
  - instancja z `STOP_RECZNY` i bez procesu bota (= Karol gra) jest pomijana w całości;
  - globalna pauza: plik `instancje/_wspolne/NADZOR_PAUZA`;
  - wyłączenie jednej postaci: `"nadzor": false` w jej `profil.json`;
  - poza grafikiem nadzorca niczego nie startuje.
- Wszystko trafia do `instancje/_wspolne/logi/nadzor-RRRRMMDD.jsonl` (czas, instancja, akcja, wynik).
- Stan zbiorczy dla Sonneta i paska: `instancje/_wspolne/nadzor_stan.json` (krótki: faza cyklu, zdrowie bota, ostatni alarm,
  liczba napraw).

### C. Obchód Sonneta (co ~10 min, świeży kontekst przy każdym wywołaniu)

- Timer uruchamia `claude -p --model sonnet` z plikiem reguł `NADZORCA.md`, wejściem `nadzor_stan.json` i ostatnimi
  zdarzeniami. Bez historii rozmowy, więc reguły nie rozmywają się po godzinach.
- Sonnet może tylko:
  - czytać stan, logi i zrzut ekranu instancji (`grim`) do rozpoznania ekranu: gra / lista postaci / śmierć / rozłączenie;
  - wołać akcje z białej listy: `nadzor.py napraw <id> <rodzaj>` (restart bota, restart sesji, `wroc.sh`, ponowne
    logowanie, rotacja napraw z `CLAUDE.md` bota).
- Każda decyzja jest zapisana w logu nadzoru z uzasadnieniem w jednym zdaniu.
- **Eskalacja do Karola** (powiadomienie krytyczne, bez Slacka/Notion): PK albo atak gracza, zgon, „bot?”/pytanie na czacie,
  GM, IP proxy niezgodne, wyczerpana rotacja napraw, a także instancja, której stanu nie da się ustalić.
- Sonnet nigdy nie pisze na czacie gry, nie zmienia map, pokręteł ani grafiku i nie dotyka ręcznej gry.

## Zależności

1. `SPEC_powrot_rook_1020.md` F1 (powrót do miasta na Rooku) i F2 (`wyloguj.sh`), bo bez nich koniec zmiany = wylogowanie
   w środku jaskini.
2. Nowy `zaloguj.sh` (F0 niżej).
3. Wykrycie zgonu na ekranie wyboru postaci (luka z 20.10): bot ma stanąć, a nadzorca ma to zobaczyć jako zgon,
   nie jako „bot nie idzie”.

## Fazy

- **F0 pomiary (jedna instancja, Karol obok):**
  1. co pokazuje klient po starcie z zapisanym loginem i jak go zalogować bez myszy;
  2. ekran po zgonie;
  3. czas od Ctrl+L do listy postaci przy spokojnym bocie.
  Wynik: `zaloguj.sh` (z limitem czasu, sprawdzeniem, że postać jest w grze) i kryterium zgonu.
- **F1 grafik:** `grafik.py` + testy reguł (nigdy dwa logowania w odstępie < X, limit N naraz, przesunięcie dzienne).
- **F2 wykonawca w cieniu:** `nadzor.py` tylko loguje, co by zrobił, przez jeden dzień obok ręcznej gry; Karol przegląda log.
- **F3 wykonawca na żywo na 1–2 postaciach**, reszta ręcznie.
- **F4 obchód Sonneta** (najpierw tylko ocena i powiadomienia, potem naprawy z białej listy).
- **F5 cały zestaw.**

## Decyzje (Karol 21.10 ~07:40, „ok” na propozycje)

- Q1: zmiana 2–4 h, najwyżej 4 postacie naraz, między logowaniami/wylogowaniami 7–25 min, przesunięcie dzienne ±1 h,
  cisza 01:00–08:00, limit 8 h na postać dziennie.
- Q2: zatwierdzony grafik = zgoda na koniec zmiany; wylogowanie czeka do spokojnej chwili (bez walki), najdłużej 15 min.
- Q3: Sonnet jako świeże wywołanie z timera co ~10 min, nie długa sesja `/loop`.
- Q4: (bez propozycji w szkicu, przyjęte domyślnie) stała mapa i tryb na postać w grafiku, start od `ostatni_start.<id>.env`;
  rotacja map później.
- Q5: zgon = powiadomienie, postać wylogowana do decyzji Karola, bez powrotu na spot.
- Q6: (przyjęte domyślnie) powiadomienia krytyczne na pulpit (`powiadom.py`, pilność critical); telefon później.
- Q7: (przyjęte domyślnie) przerwy AFK w trakcie zmiany poza F1, osobny krok po F5.
- Q8: rutynowy obchód Haiku (`--model haiku`), Sonnet tylko przy odchyleniu wskazanym przez obchód albo `nadzor.py`.

## Weryfikacja

- Testy `grafik.py`: reguły odstępów i limitu naraz na 1000 losowych dób, przesunięcie dzienne, ręczna edycja wygrywa.
- Testy `nadzor.py` na atrapach: `STOP_RECZNY` bez bota = zero akcji; `NADZOR_PAUZA` = zero akcji; dwie zmiany kończące się
  w tej samej minucie → wylogowania rozsunięte o co najmniej X.
- Na żywo (zasada „jedno wywołanie”): F2 pełny dzień w cieniu z porównaniem logu z grafikiem; F3 jeden pełny cykl start → zmiana
  → powrót → wylogowanie na jednej postaci, pozostałe instancje nietknięte.
- Obchód Sonneta: zestaw nagranych sytuacji (bot stoi, orbita, lista postaci, zgon, „bot?” na czacie, ręczna gra) i oczekiwana
  decyzja dla każdej; zielone przed włączeniem napraw.

## Poza zakresem

Odpisywanie graczom, zakładanie kont i postaci (`wydra`), zakupy i serwis na Rooku, zmiana map i pokręteł przez model,
handel, drugi komputer.
