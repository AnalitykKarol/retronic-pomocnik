# SPEC: unikanie graczy — nie idziemy za graczem, przerwa nie stoi obok niego (17.10.2026)

Status: **ZATWIERDZONA przez Karola 17.10 ("ok zrób to")** w zakresie F1 i F2. F3 czeka na decyzję. Kod za pokrętłami, domyślnie 0.
Branch: `feat/unikanie-tor-gracza` (worktree `pomocnik-unikanie`), baza `ruch-r1-1014` (`a6026dc`). Bez merge, bez restartu bota.

## Problem (dowód: telemetria i log 17.10, 18:24–18:28, gracz Harley Queen)

1. **Przerwa stoi obok gracza.** `PRZERWA` (113 s od 18:24:52) nie kończy się, gdy gracz podchodzi: komentarz w `cavebot.py`
   ("kończy się wcześniej, gdy coś podejdzie") nie ma pokrycia w kodzie. Gracz był 6 pól o 18:26:40 i obok o 18:26:48; przerwa trwała do końca.
2. **Postać idzie za graczem.** 18:27:41–18:27:59 bot i gracz szli krok w krok, 0–2 pola od siebie
   (bot (33089,31761)→(33094,31754), gracz (33089,31763)→(33095,31750)). `unikanie.decyduj` wybiera "następne punkty rotacji"
   z kryterium odległości od **bieżącej** pozycji gracza (>= `UNIKANIE_PUNKT_D`), więc nie widzi, że gracz idzie tam, dokąd my.
   W logu ciąg "punkt 8→9→…→15", potem "cofam się". Gdy gracz zniknął z widoku, unikanie kończyło się po 10 s i patrol wracał na ten sam tor.
3. **Pauza na rozmowę** (`mozg.py`, "staję na czas rozmowy") zatrzymuje postać obok gracza. Poza F1/F2, patrz F3.

## Zasady (F1: tor gracza, `UNIKANIE_TOR`)

- Z ostatnich `UNIKANIE_TOR_OKNO_S` (4 s) pozycji każdego gracza liczymy kierunek ruchu `h` (przesunięcie okno-początek→koniec).
  Przesunięcie < `UNIKANIE_TOR_RUCH_MIN` (2 pola) = stoi: bez toru, działają dotychczasowe reguły dystansu.
- **Droga "idzie za graczem"**, gdy dla gracza w promieniu `UNIKANIE_TOR_ZASIEG` (12 pól) kierunek jej pierwszych
  `UNIKANIE_TOR_LOOK` (8) pól `v` spełnia `v·h > 0` oraz `v·r > 0` (`r` = wektor od nas do gracza): idziemy tam, dokąd on idzie, w jego stronę.
  Taka droga jest odrzucana jako cel: bieżący punkt (gałąź "bezpieczny"), następne punkty rotacji, cofnięcie.
- Kolejność wyboru: (1) punkty bez "za graczem" do przodu, (2) bez "za graczem" do tyłu (cofanie od gracza jest dozwolone),
  (3) czekanie w ruchu (`_wiggle`, punkty bez "za graczem"), (4) **dopiero gdy nic**: stare zachowanie bez filtra
  (bieżący bezpieczny cel, potem przód/tył/czekanie jak dawniej; nigdy nie zawieszamy bota).
- **Pamięć ("duch")**: gracz, który zniknął z widoku, zachowuje ostatnią pozycję i kierunek przez `UNIKANIE_TOR_PAMIEC_S` (25 s).
  W tym czasie unikanie trwa (nie kończy się po `UNIKANIE_ZNIKL_S`), a duch bierze udział w teście "za graczem". Duch nie blokuje pól dystansem.
- Wybór jest stabilny: raz wybrany punkt jest utrzymywany, dopóki spełnia warunki (jak dziś), bez przeskoków punkt po punkcie za graczem.
- `UNIKANIE_TOR=0`: kod zachowuje się bajt w bajt jak przed zmianą (test regresji: istniejące `test_unikanie.py` bez zmian).

## F2: przerwa (`UNIKANIE_PRZERWA`)

- Gracz (zwykły, ten sam poziom wyszukiwania co unikanie) w odległości <= `UNIKANIE_PROMIEN` kończy `PRZERWA` natychmiast:
  log "Przerwa przerwana: gracz X blisko", `przerwa_do=None`, następna przerwa wg `PRZERWA_CO_MIX`.
- `UNIKANIE_PRZERWA=0`: jak dziś.

## F3: pauza na rozmowę (NIE w tej paczce; decyzja Karola)

Czy w `mozg.py` pauza rozmowy ma zdejmować postać z drogi gracza (odejście na bezpieczny punkt), czy zostaje stanie (bardziej "ludzkie")?
Do czasu decyzji bez zmian.

## Pokrętła

| Pokrętło | Domyślnie | Zakres (`pokretla.py`) |
|---|---|---|
| `UNIKANIE_TOR` | 0 | 0..1 (analityk: tylko w górę) |
| `UNIKANIE_TOR_OKNO_S` | 4.0 | 2..10 |
| `UNIKANIE_TOR_RUCH_MIN` | 2 | 1..5 |
| `UNIKANIE_TOR_ZASIEG` | 12 | 6..20 |
| `UNIKANIE_TOR_LOOK` | 8 | 4..16 |
| `UNIKANIE_TOR_PAMIEC_S` | 25.0 | 0..120 |
| `UNIKANIE_PRZERWA` | 0 | 0..1 (analityk: tylko w górę) |

## Weryfikacja

- `testy/test_unikanie_tor.py` (atrapa `Swiat` z `test_unikanie.py`): odtworzenie 18:27 (gracz idzie trasą bota, bot nie zbliża się do jego toru),
  korytarz z graczem odchodzącym, gracz stojący, duch po zniknięciu, brak alternatywy (fallback, brak postoju), pokrętło 0 = stare zachowanie.
- Test przerwy na atrapie cavebota.
- Istniejące `test_unikanie.py`, `test_patrol_gracz_zmiana.py` bez zmian i zielone.
- **Nie zweryfikowane w grze.** Naturalna QA: kolejne spotkanie z graczem na spocie po włączeniu pokręteł (po restarcie bota, za zgodą Karola).

## Poza zakresem / ryzyka

- Kierunek z historii pozycji jest przybliżeniem (zakręty korytarza); stąd test iloczynu skalarnego dla krótkiego odcinka drogi, nie promień.
- Zmiana patrolu (wybór respa) żyje w `cavebot.py` (`PATROL_GRACZ_ZMIEN`) i nie jest ruszana.

## Wynik realizacji (17.10, branch `feat/unikanie-tor-gracza`)

- Zmiany: `unikanie.py` (tor, duch, filtr w `decyduj`/`_wiggle`), `cavebot.py` (pokrętła, `_przerwa_przerwij_gdy_gracz`, marsz krokami także dla ducha),
  `pokretla.py`, `testy/test_unikanie_tor.py` (26 asercji). Pełny zestaw `testy/`: 94 pliki, wyniki identyczne z bazą `a6026dc`
  (2 dawne FAIL w tych samych plikach, `test_cavebot` 5 starych czerwonych).
- Przegląd niezależny (checker): CHANGES-REQUIRED -> poprawione: (1) przy `UNIKANIE_TOR=0` budżet A* znów jak w bazie (51 wywołań, test T9),
  (2) kolejność czekanie-w-ruchu przed starym zachowaniem zgodna ze specyfikacją (T10), (3) duplikat logu "Koniec przerwy." po przerwaniu przerwy.
  Pozostałe uwagi NITS: nowe zdarzenie telemetrii `unikanie_tor` (świadome, do naturalnej QA), koszt A* przy TOR=1 bez profilu na prawdziwej mapie.
- Nie zweryfikowane w grze, nie wdrożone. Proces bota ma stary kod.

## Wdrożenie (po zgodzie Karola, wymaga restartu bota)

1. Merge brancha do gałęzi, z której startuje bot (decyzja Karola; branch nie jest scalany ani wypychany).
2. Restart bota (kod wczytuje się przy starcie).
3. W `na_zywo.json`: `"UNIKANIE_TOR": 1`, `"UNIKANIE_PRZERWA": 1` (pozostałe pokrętła toru mają sensowne domyślne). Cofnięcie: wartości na 0, bez restartu dla samych pokręteł.
4. Naturalna QA: następne spotkanie z graczem na spocie. Szukać w logu "Unikanie: nie idę za graczem" i "Przerwa przerwana"; w telemetrii `unikanie_tor`;
   sprawdzić, że bot nie idzie jego torem (pozycje w `probka`), a `ruch_okno` nie pokazuje postoju > 10 s obok gracza.
