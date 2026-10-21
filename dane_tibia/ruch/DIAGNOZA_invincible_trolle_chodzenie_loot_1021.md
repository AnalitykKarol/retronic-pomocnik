# DIAGNOZA: invincible (trolle_patrol, ostrozny+ml) źle chodzi, nie zbiera lootu — 21.10 ~11:00

Status: **INVESTIGATING** (część mechanizmu pokazana, loot nierozstrzygnięty). Tylko odczyt: gra i bot nietknięte.
Zgłoszenie Karola 21.10 ~10:50: „invincible ma cały czas problem, źle chodzi, boty się tną, nie zbierał loota mimo że go widział”.
Stan 10:49:27: `STOP` + `STOP_RECZNY` (Karol przejął postać), wcześniej 10:48:05 `[UCIECZKA] HP 36%`, `ALARM: niskie HP`.

## Pomiary (logi `instancje/invincible/logi/mozg-stdout-*.log`)

| Przebieg | Zabite | „nie ruszył” / zabity | Loot `brak_okna` | Wykrycia ognia/h | ML (utevo lux) |
|---|---|---|---|---|---|
| 20.10 16:10–22:50 (`ostrozny`) | 779 | 0,07 | 30 (4%) | 0 | 0 |
| 21.10 08:09–10:31 (`ostrozny,ml`) | 177 | 1,6 | 24 (14%) | 53 | 51 |
| 21.10 10:31–10:49 | 21 | 2,2 | 9 (43%) | 72 | 2 |

Pozostałe boty dziś (10-min okna): „nie ruszył” zwykle 0–15, invincible 11–36 przez cały ranek. 10:00–10:10 wszyscy stoją = reset serwera.

## Hipotezy

| # | Hipoteza | Wynik |
|---|---|---|
| H1 | Przeciążenie maszyny (load 15 min = 32 o 10:52, `straznik.py` 56–98% CPU każdy) | **nierozstrzygnięta, raczej nie**: „wolny tick” 0–4 na bota przez cały dzień; load mógł podbić też moje testy 10:35–10:45 |
| H2 | Czar ML (F1) przerywa kroki | **obalona**: 6% „nie ruszył” ≤5 s po czarze przy 3% czasu w tych oknach; po 10:31 0 |
| H3 | Rozjazd pozycji gracza i listy stworów | **obalona jako różnica**: wczoraj 31% próbek poza 0,0, dziś 15–16% |
| H4 | Znane pola ze ścianami w jaskini | **obalona**: 5 ścian w 451 polach jaskini, tyle samo co w `HEAD`, 0 nowych |
| H5 | Ogień w korytarzu jaskini: bot nie wchodzi na pole ognia (`cavebot` krok_do), w korytarzu 1-polowym bije w ściany | **częściowo potwierdzona**: wczoraj 0 wykryć ognia w 6,7 h, dziś 53–72/h w tych samych punktach ((32491,32289) 77+16, (32480,32294) 75+9); zrzut 10:55 = prawdziwe pole ognia pod trollem (`ogien.pola_ognia` → (−3,1)); 38% „nie ruszył” (08:09–10:31) i 13% (10:31–10:49) ≤2 pola od ognia w ≤120 s; przykład 09:59:38 ogień (32474,32289) → 10 s prób Up/Down w ściany z (32473,32289). Kod ognia bez zmian od 14.10 |
| H6 | Ogień na zwłokach blokuje okno lootu | **obalona**: 1 z 7 `brak_okna` z ogniem ≤1 pole |
| H7 | Prostokąt mapy (cache po rozmiarze 1175×910) zły po relogu | **nierozstrzygnięta**: invincible ma inny układ klienta niż kolanoth (mapa 806×592 od x=183, pole 54 px, u kolanotha 985×724, 65 px); wykrycie na zrzucie 10:55 poprawne (183,102,992,695) z ostrzeżeniem „blok mapy 299 px”; loot w tym samym procesie raz działa, raz nie (17 ok / 9 brak) |

## Ustalone

- Dziś w jaskini trolli są pola ognia, których wczoraj nie było (skąd: nieznane — gracz? zdarzenie serwera?). Bot ich nie przechodzi
  i w wąskich korytarzach marnuje kroki; to część „źle chodzi”, nie całość.
- `brak_okna` wzrosło po resecie serwera 10:00 i relogu (10:20–10:49: 13 z 27), także w procesie z 08:09 (stary kod), więc nie przez
  zmiany F2/F3 z 10:3x (pokrętła 0 u invincible'a, ścieżki nieaktywne).
- Ucieczka 10:48 na z9: kroki „nie ruszył” także na pola przechodnie (`mapa przechodnie True`), postać nie odeszła.

## Czego NIE ustalono

- Przyczyna `brak_okna` po 10:20 (H7 i inne). Następny pomiar: zapis prostokąta mapy przy starcie bota i zrzut ekranu przy `brak_okna` (zmiana kodu, decyzja Karola).
- Reszta „nie ruszył” (62–87%) poza ogniem.
- Skąd ogień i czy jest stały.
- „Boty się tną” — wolnych ticków brak; może chodzić o płynność podglądu (Remmina/wayvnc) przy obciążeniu, niezmierzone.

## 21.10 10:58–10:59: restart i przejście przez ogień

Karol: „odpal tego bota”, „nie może przejść przez ogień”. Bot invincible uruchomiony 10:58:31 (`trolle_patrol`, `ostrozny,ml`, HP 88/195);
pełny reset sesji pominięty (wylogowałby 6 postaci naraz). Pokrętło `OGIEN_IGNORUJ_S` = 30 w `instancje/invincible/na_zywo.json`
(kopia `na_zywo.json.bak-20261021-ogien`; przeładowane na żywo 10:59:06): po `OGIEN_CZEKAJ_MAX_S` = 30 s bez drogi bot ignoruje ogień 30 s
i przechodzi. Cofnięcie: `OGIEN_IGNORUJ_S` = 0. QA na żywo: w logu `[OGIEN] ogień zamyka drogę od 30 s, ignoruję go przez 30 s` i postęp trasy.

**10:59:56 COFNIĘTE** (`OGIEN_IGNORUJ_S` = 0, przeładowane na żywo). Karol: „nie może przejść przez ogień” znaczyło ZAKAZ wchodzenia w ogień
(postać zginie), nie skargę na brak przejścia. Między 10:59:06 a 10:59:56 w logu brak „ignoruję go” — bot przez ogień nie przeszedł.
