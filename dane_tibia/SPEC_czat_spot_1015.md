# SPEC: wiadomość do gracza, który przeszkadza na spocie (15.10) — ZATWIERDZONY 15.10 (Q1–Q3 jak niżej), w teście na żywo

Cel: bot sam pisze **jedną** krótką wiadomość po angielsku na Default do gracza, który **wraca na nasz spot albo przeszkadza**.
Przechodnie (jedno krótkie spotkanie, gracz biegnie dalej) nie dostają nic. Bez polemiki: najwyżej jedna odpowiedź, potem cisza
i dymek dla Karola. Zasady repo: wszystko za pokrętłem, domyślnie wyłączone, nic do repo bez słowa Karola.

## Co już jest (punkt wyjścia)

- `unikanie.py` śledzi graczy w `UNIKANIE_PROMIEN_MAX` (14): `self.bylo[nick] = {od, ost}`; obecność zeruje się po
  `UNIKANIE_ZNIKL_S` (10 s) nieobecności. Zdarzenie `gracz_na_spocie` = ciągła obecność ≥ `UNIKANIE_SPOT_S` (180 s), dziś tylko dymek.
- `pomin_moba` wie, że mob stoi przy konkretnym graczu (gracz go bije / "zajął").
- `mozg.py`: `wpisz_na_czacie` (aktywna zakładka), `bezpieczna_wiadomosc`, `do_nas(..., po_naszej=True)` uznaje odpowiedź
  gracza w `CZAT_OKNO_ODPOWIEDZI` po naszej wysyłce za skierowaną do nas; `rozmowa_start` zatrzymuje bota na czas rozmowy.

## Kiedy piszemy (wyzwalacz)

Liczone per nick, w `unikanie.py`, przy włączonym `CZAT_SPOT_AKTYWNY`:

| Sygnał | Definicja | Próg (pokrętło, domyślnie) |
|---|---|---|
| S1 powroty | osobne **spotkania** z tym samym graczem (nowe spotkanie = gracz w `UNIKANIE_PROMIEN` po ≥ `UNIKANIE_ZNIKL_S` nieobecności) | ≥ `CZAT_SPOT_SPOTKAN` = 3 w `CZAT_SPOT_OKNO_MIN` = 20 min |
| S2 siedzi | ciągła obecność w promieniu | ≥ `CZAT_SPOT_CIAGLE_MIN` = 5 min |
| S3 zabiera moby | `pomin_moba` pominął moba przez tego gracza (mob przy nim, nas nie bije) | ≥ `CZAT_SPOT_ZABRANE` = 2 razy w 10 min |

Wyzwala **S3 albo (S1 lub S2)**. Spotkanie krótsze niż 20 s nie liczy się do S1 (przebiegł obok).

## Kiedy NIE piszemy (twarde blokady)

- gracz z czaszką, GM/CM, stan `GRACZ`/`UCIECZKA`, alarm GM; HP < 70%;
- gracza nie ma na ekranie (±7, ±5) w chwili wysyłki;
- ten nick dostał już wiadomość w ostatnich `CZAT_SPOT_NICK_MIN` = 60 min; globalnie najwyżej 1 wiadomość na 10 min;
- w trakcie rozmowy prowadzonej przez model (`rozmowa_od`) i gdy Karol pisał coś sam w ostatnich 5 min (UNKNOWN: czy da się to
  odczytać z czatu — wiadomość od naszego nicka, której bot nie wysłał).

## Co piszemy

Stała pula, bez modelu (żadnego prompt injection na pierwszej wiadomości), losowo, z opóźnieniem 3–10 s po spełnieniu warunku.
Bot nie staje (pisze w ruchu, jak dziś).

| # | Tekst | Dla |
|---|---|---|
| 1 | `hey, im hunting here for a while` | S1/S2 |
| 2 | `yo, this spot is taken atm, sorry` | S1/S2 |
| 3 | `hi mate, im on this spot, can u find another one pls` | S1/S2 |
| 4 | `pls dont take my trolls, im hunting here` | S3 (nazwa moba z celu) |
| 5 | `hey, pls dont interrupt, im hunting here` | S3 |

## Odpowiedź gracza (polemika)

- `CZAT_SPOT_ODPOWIEDZI` = 1: na pierwszą odpowiedź tego gracza bot odpisuje **raz** (model Haiku, osobny krótki prompt:
  angielski, max 8 słów, bez przyznawania się do bota, bez obelg, bez pytań; `bezpieczna_wiadomosc` jak dziś). Potem milczy
  wobec tego nicka do końca okna `CZAT_SPOT_NICK_MIN`. Bot nie staje na czas tej wymiany.
- Odpowiedź z pytaniem o bota/makro/AFK, z poleceniem dla nas ("ignore…", "say…", "type…") albo z groźbą zgłoszenia:
  **nic nie piszemy**, tylko dymek `czat:spot:<nick>` (krytyczny), żeby Karol przejął.
- 0 = nigdy nie odpisujemy (tylko dymek). Więcej niż 1 = polemika (nie zalecane, decyzja Karola).

## Powiadomienia i log

- Dymek `czat:spot:<nick>` przy wysłaniu ("Napisałem do X: …") i przy jego odpowiedzi (treść).
- Zdarzenie `czat_spot` (gracz, sygnał S1/S2/S3, tekst) w telemetrii i logu.

## Pokrętła (pokretla.py ZAKRESY, na_zywo.przyklad.json)

`CZAT_SPOT_AKTYWNY` (0/1, domyślnie 0), `CZAT_SPOT_SPOTKAN` (2–10), `CZAT_SPOT_OKNO_MIN` (5–60), `CZAT_SPOT_CIAGLE_MIN` (2–30),
`CZAT_SPOT_ZABRANE` (1–10), `CZAT_SPOT_NICK_MIN` (10–240), `CZAT_SPOT_ODPOWIEDZI` (0–3).

## Testy (`testy/test_czat_spot.py`, zegar wstrzykiwany)

1. przechodzień: 1 spotkanie 15 s → brak wiadomości; 2 spotkania → brak;
2. 3 spotkania w 20 min → 1 wiadomość (S1); 3 spotkania w 40 min → brak;
3. ciągle 5 min → 1 wiadomość (S2); drugi raz w ciągu 60 min → brak (limit nicka);
4. 2 zabrane moby → 1 wiadomość (S3, tekst z puli S3);
5. blokady: GM, czaszka, HP 60%, gracz poza ekranem, pokrętło 0 → brak;
6. limit globalny: dwóch graczy naraz → druga wiadomość dopiero po 10 min;
7. odpowiedź gracza: zwykła → dokładnie 1 odpowiedź modelu; "are u bot?" / "ignore previous…" → 0 odpowiedzi + dymek krytyczny;
   druga odpowiedź gracza → 0 odpowiedzi.

Regres: `test_unikanie.py` 39/39 bez zmian.

## Weryfikacja na żywo

Trolle, `CZAT_SPOT_AKTYWNY=1`: w logu `czat_spot` przy graczu, który wraca/bije nasze moby, brak przy przechodniu; zrzut czatu
Default z wysłanym tekstem; telemetria bez wysyłki w stanie `GRACZ`.

## Decyzje Karola 15.10

Teksty, progi i jedna odpowiedź zatwierdzone bez zmian; Karol nie pisze sam, sprawdzenie ręcznych wiadomości zostaje.
Kod: `czat_spot.py`, haki w `unikanie.py` i `mozg.py` (`czat_spot_tick`), testy `testy/test_czat_spot.py` (52/52).
Dodatkowo S3 wymaga >= 60 s obecności gracza w oknie (troll goniący przechodnia to nie S3).

## Pytania do Karola (przed kodem, zamknięte)

- Q1 teksty z puli: zostawić / zmienić / dopisać?
- Q2 progi: 3 spotkania w 20 min, 5 min ciągle, 2 zabrane moby — OK?
- Q3 odpowiedzi: 0 (tylko dymek), 1 (zalecane) czy więcej?
