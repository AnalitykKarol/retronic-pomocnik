# SPEC: nadzorca zestawu (grafik zmian + pilnowanie botów) - 21.10 — SZKIC, czeka na Karola (Q1–Q8)

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

## Pytania otwarte (Karol)

- Q1: Ramy grafiku. Propozycja: zmiana 2–4 h, najwyżej 4 postacie naraz, między logowaniami/wylogowaniami 7–25 min,
  przesunięcie dzienne ±1 h, cisza 01:00–08:00, limit 8 h na postać dziennie. Zmienić coś?
- Q2: Czy **zatwierdzony grafik = zgoda** na przerwanie expienia na koniec zmiany? (Dziś: bota nie przerywam bez Twojej zgody.)
  Propozycja: tak, ale koniec zmiany czeka do spokojnej chwili (bez walki), najdłużej 15 min.
- Q3: Sonnet jako **świeże wywołanie z timera co 10 min** (rekomendacja: stabilne, tanie, działa bez otwartej sesji)
  czy jedna długa sesja `/loop`?
- Q4: Mapy: każda postać ma stałą mapę w grafiku czy rotację między kilkoma (mniej powtarzalny wzór)?
- Q5: Zgon: tylko powiadomienie i postać zostaje wylogowana do Twojej decyzji (rekomendacja) czy nadzorca po zgonie
  wraca z postacią na spot?
- Q6: Gdzie powiadomienia krytyczne: pulpit (`notify-send`) czy też telefon?
- Q7: Czy w F1 mają być krótkie przerwy w trakcie zmiany (np. 5–15 min AFK w mieście), czy to później?
- Q8: Limit kosztu obchodu: Sonnet co 10 min ≈ 100 wywołań dziennie. Czy zamiast tego Haiku do rutynowego obchodu,
  a Sonnet tylko przy odchyleniu?

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
