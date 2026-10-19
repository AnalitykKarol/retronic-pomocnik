Status: approved do fazy 1–2 w repo; fazy 1–2 wykonane 19.10 (plugins/charlie.retronic, 32/32 testów), faza 3 czeka na zgodę poz. 2 (19.10, Charlie: „puść agenta, żeby zrobił ten guzik”; Q1 5 s, Q2 tylko włączone/wyłączone,
Q4 najgorszy stan przyjęte jako rekomendacje, Q3 rozstrzygnięte). Faza 3 (symlink w `~/.config`, restart shella) = poziom 2, osobna zgoda.
Weight: Feature
Projekt: Retronic, zarządzanie instancjami z paska Omarchy

# Wtyczka paska `charlie.retronic`: status i start/stop botów instancji

## TLDR

Mała wtyczka paska Omarchy (QML), jedna ikona `RT` o kolorze najgorszego stanu. Hover daje jedno zdanie
(„2 instancje: 1 działa, 1 stop”), klik otwiera panel z wierszem na instancję: kropka stanu, `[Stop]` albo `[Start]`
(start bota z ostatnią mapą i trybem tej instancji). Wtyczka jest cienka: nie ma własnej logiki bota, czyta JSON i woła
istniejące skrypty. Decyzje Charliego (19.10): wygląd = ikona + panel po kliknięciu; zakres = tylko bot (grę
i sesję uruchamia i loguje ręcznie, jak dotąd).

## Co już istnieje (zmierzone 19.10, katalog `/home/charlie/Games/Retronic/pomocnik`)

- Status instancji: `RETRONIC_ID=<id> python3 -I panel.py --json` → `{"text","tooltip","class","alt"}`, klasy
  `dziala` / `alarm` / `stop` / `brak`. Bez ID = główna. Sprawdzone: główna `dziala` (HP, mana, tryb, wniosek analityka),
  `test` `stop`.
- Stop: `RETRONIC_ID=<id> ./zatrzymaj.sh` (flagi STOP, nie rusza gry/wine/sway).
- Start: `RETRONIC_ID=<id> ./uruchom.sh` bez `MAPA`/`TRYB` bierze `ostatni_start[.<id>].env` (obecnie główna:
  `gobliny_edron`, `ostrozny`); odmawia, gdy bot już działa albo brak gniazda gry.
- Lista instancji: główna (pusty ID) + katalogi w `instancje/` poza `_wspolne`.
- Brak jakiegokolwiek podpięcia Retronic w `~/.config/omarchy` ani waybarze.

## Zakres

- Nowa wtyczka `plugins/charlie.retronic/` (manifest, `Panel.qml`, mały model odczytu), symlink w
  `~/.config/omarchy/plugins/charlie.retronic` (jak pozostałe, rekord `.ai/system/omarchy-plugins/STATE.md`).
- Odczyt statusu co 5 s przez `Process` (bez demona), jedna instancja = jedno wywołanie `panel.py --json`.
- Każda instancja ma własne, oddzielne `[Stop]`/`[Start]` w swoim wierszu (Charlie 19.10); żadnego „stop wszystkich”
  domyślnie. Przy 3+ instancjach panel dostaje kolejne wiersze.
- Kliknięcie `[Stop]`/`[Start]` woła skrypt tylko tej instancji; wynik (odmowa „gra nie działa”) pokazuje w wierszu panelu.
- Ścieżka do pomocnika w ustawieniach wtyczki (domyślnie powyższa), nie zaszyta w QML.

## Poza zakresem (non-goals)

- Start i zamykanie sesji gry/proxy z paska, logowanie postaci.
- Powiadomienia (zostają w `powiadom.py` bota); alerty na telefon.
- Zmiana kodu bota; zmiana trybu/mapy z paska (tylko „ostatni”).
- Dowolna liczba klientów poza listą z `instancje/` (skalowanie przyjdzie z tej listy bez zmian kodu).

## Open Questions

- **Q1 — odświeżanie.** Rekomenduję 5 s (tanie, wystarczy do „czy działa”). Zgoda?
- **Q2 — wiersz proxy w panelu.** Rekomenduję tylko stan „proxy włączone / wyłączone” (czy proces instancji siedzi w
  `siec_proxy.sh`), bez pomiaru IP (pomiar to sieć i opóźnienie). Czy chcesz też wyjściowe IP?
- **Q3 — potwierdzenie Stop. ROZSTRZYGNIĘTE (19.10, Charlie: „muszę móc zatrzymać dowolną instancję”):** `[Stop]` działa
  od razu, bez potwierdzenia, dla każdej instancji, także głównej. Stop jest odwracalny jednym kliknięciem `[Start]`.
- **Q4 — kolor ikony.** Najgorszy stan (alarm > stop > działa) czy „czy cokolwiek działa”? Rekomenduję najgorszy.

## Poziom zgody i ryzyka

- Poziom 1 dla kodu w repo; **poziom 2** dla symlinku w `~/.config/omarchy/plugins` i `omarchy restart shell`
  (osobna zgoda, kopia, cofnięcie: usunięcie symlinku + restart shella).
- Ryzyko: przypadkowe kliknięcie `Stop` przerywa bota w trakcie (reguła Charliego: nie przerywać bez zgody). Przycisk
  jest jego świadomą decyzją, bez potwierdzenia (Q3); skutek cofa `[Start]` z ostatnim trybem. Przyciski `Stop` i `Start`
  mają różne miejsce/kolor, by ograniczyć przypadkowy klik.
- Ryzyko: `panel.py --json` pokazuje wniosek analityka w tooltipie. W panelu skracamy do stanu i trybu, bez treści logów.

## Fazy

1. Model odczytu + panel z atrapą JSON (testy QML/`qmllint`, bez dotykania prawdziwych botów).
2. Podpięcie skryptów Stop/Start, test na instancji `test` (start/stop bota na zalogowanej postaci wymaga Charliego).
3. Symlink + restart shella (poziom 2), zrzut paska, rekord `.ai/system/omarchy-plugins/STATE.md`, wpis w README mapy.

## Weryfikacja (kryterium zaliczenia)

Zrzut paska z ikoną w obu kolorach; panel pokazuje obie instancje zgodnie z `status.sh`; `[Start]` na `test` uruchamia
bota z `ostatni_start.test.env`, `[Stop]` go zatrzymuje (`panel.py --json` → `stop`); główna nietknięta w czasie testów.
