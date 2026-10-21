# SPEC: wpadnięcie bez STOP — naprawa i ponawianie — 21.10 — ZATWIERDZONY (Karol 21.10 „tak” dla pkt 1.1 `ruch/AUDYT_1021.md`)

## Problem (dowody, telemetria 21.10)
- 6 zdarzeń `wpadniecie_alarm` w 2 dni (dawajkesh 08:53:14 i 09:30:33, invincible 20.10 15:53:50 i 21.10 13:18:09, kolanoth 13:04:06 i 13:37:41), 47 min przestoju (STOP + critical).
- 4 z 6 ALARM-ów przyszły po 5–10 s (`czas_s` 5,3 / 6,1 / 9,3 / 9,5), choć budżet `PIETRA_MAX_S`=150 s. Powód zawsze „lina i plan po mapie nie działają”.
- Mechanizm (`wpadniecie.py`): `_plan` — `PLAN_PROBY`=3 razy z rzędu „brak planu” co 2 s → `None` → `_alarm` (plik STOP + powiadomienie critical).
  `_krok_porazka` dodaje pole przejścia T do `st['zle']` NA STAŁE, więc po jednym nieudanym kroku (jedyny kandydat) nie ma już czego planować.
- Przykład kolanoth 13:37:41: upadek z (32369,32212,8) na (32370,32214,7); plan: jedyne przejście z danych (kratka `thais_dojscie_kratka.json`)
  T=(32370,32213,7)→(32370,32213,8); krok „Up” stawia postać NA T, nic się nie dzieje (`pietra_blad: wyczerpane pola przejścia`),
  T → `zle`, 3× „brak planu” (4 s), ALARM po 9,3 s. Ręcznie wyszedł dopiero po ~90 s.
- Przykład Rook (dawajkesh, wydra 21.10): upadek z (32049,32155,11) na (32050,32156,10); pierwszy plan bierze przejście z danych T=(32049,32155,10) (xy = pole, z którego
  spadł; na mapie zwykłe pole), krok kończy się porażką po ~4 s i postać stoi NA T; dopiero drugi plan (T=(32050,32155,10), prawdziwa dziura) wychodzi. Gdy i on zawiedzie,
  `zle` zawiera oba pola i zostaje STOP; ponowny plan (po wyczyszczeniu `zle`) znów zaczynałby od przejścia liczonego z pola, na którym postać już stoi.
- Zasada Karola (20.10): bot utknął → rotacja napraw, nigdy STOP za brak postępu. Wyjątki życia (zgon, PK, niskie HP, teleport) zostają STOP i tej ścieżki nie dotykamy.

## Zachowanie przy `WPADNIECIE_BEZ_STOP=1` (domyślnie 0 = bit w bit jak dziś)
1. Brak planu (3 próby, jak dziś) albo `WPADNIECIE_PLAN=0` po wyczerpaniu liny kończy **cykl**, nie wpadnięcie: licznik cykli +1, `st['zle']` wyczyszczone,
   licznik prób liny od zera, czekanie 10–20 s (losowo; stała `BEZ_STOP_CZEKAJ_S`). W czasie czekania `tick()` nie robi nic poza krótką pauzą,
   a walka, ucieczka, strażnik i inne kroki ticka przed 3b działają jak dziś (wpadnięcie jest wołane dopiero po nich).
2. Po czekaniu, jeśli postać stoi NA polu przejścia, które już zawiodło (krok na nim bez skutku): jeden krok na sąsiednie chodliwe pole (nie dziura, nie inne przejście,
   `cb.krok_do`), żeby kolejna próba była prawdziwym wejściem na pole, nie „krokiem na siebie”.
3. Kandydatem planu nie jest pole T o tym samym (x, y), co postać (albo punkt liczony), jeśli T już zawiodło (`st['zawiodlo']`, nie czyszczone między cyklami).
4. Po każdym cyklu: log „Wpadnięcie: cykl N …” i telemetria `wpadniecie_cykl` (`cykl`, `poz`, `z0`, `czas_s`, `zle`, `czekaj_s`).
5. ALARM + STOP + critical dopiero, gdy minął budżet `PIETRA_MAX_S` **i** są ≥ 3 pełne cykle (stała `BEZ_STOP_CYKLE_MIN`). Twardy bezpiecznik: po
   `BEZ_STOP_TWARDY_S`=900 s alarm niezależnie od cykli (żeby ścieżka nie mogła kręcić się bez końca, gdyby cykle się nie zamykały).
6. `bez_alarmu` (strażnik orbit prowadzi plan): cykl się nie włącza. `NAPRAWA_ZAMIAST_STOP` (K01, gałąź `integracja-naprawa`, niescalona): obejmuje to samo miejsce
   (`_alarm` → `_naprawa`) i wymaga `cavebot.naprawa_z_alarmu` z tamtej gałęzi, więc tu nie przenoszone. Po scaleniu oba pokrętła się uzupełniają: cykle idą pierwsze,
   a gdy cykle i budżet się wyczerpią, `_alarm` przekazuje postać silnikowi napraw zamiast STOP.
7. Czego ten punkt nie zmienia: wyjątki życia (zgon, PK, niskie HP, teleport) i walka/ucieczka (wykonują się w ticku przed wpadnięciem), powiadomienia pietra.py
   (normal, najwyżej raz na `KLUCZ_S` na klucz), wykrywanie i nauka dziur.

## Pokrętło
`WPADNIECIE_BEZ_STOP` (0/1, domyślnie 0), czytane przez `self._k(...)`. Wpisy do `cavebot.py`, `pokretla.ZAKRESY` = (0, 1), `KIERUNEK` = `nie_nizej`, `na_zywo.przyklad.json` — doda lead.

## Test
`testy/test_wpadniecie_bez_stop.py` (atrapy, bez gry): kolanoth 13:37 (krok bez skutku → dziś ALARM po ~9 s), Rook (stoi na T), wyjście po drugim wejściu na T,
STOP dopiero po budżecie i 3 cyklach, pokrętło 0 jak dziś. Musi dać FAIL na `wpadniecie.py.bak-20261021-bez-stop`.

## Cofnięcie
`WPADNIECIE_BEZ_STOP=0` w `na_zywo.json` (bez restartu) albo `cp wpadniecie.py.bak-20261021-bez-stop wpadniecie.py` + restart.
