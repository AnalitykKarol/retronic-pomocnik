# SPEC: ręczne wywołanie powrotu do miasta („Wróć do miasta”) - 19.10 — ZATWIERDZONA do implementacji (Karol 19.10: „puść agenta niech robi”; trasa goblinów -> Edron była wielokrotnie przechodzona)

Cel: Karol może w dowolnej chwili kazać botowi wrócić do miasta (depo), bez czekania na głód albo brak zapasów i bez
przepinania pokręteł w `na_zywo.json`. Dziś jedyne wyzwalacze wyprawy są automatyczne (jedzenie, głód, blanki, pochodnie),
a akcja modelu `wroc_do_miasta` jest atrapą (`mozg.py` ~2673: loguje i woła człowieka). 19.10 Mastafian (zero jedzenia,
`WYPRAWA_CZEKAJ_NA_GLOD=1`) nie ruszył do Edronu mimo gotowego planu `gobliny_edron`.

## Decyzje Karola (19.10)

1. **Wyzwalacz:** polecenie `./wroc.sh` **i** guzik „Wróć do miasta” w wtyczce paska `charlie.retronic` (obok Stop/Start).
   Jedno wspólne źródło prawdy: plik `WROC` w katalogu stanu instancji (`$INST_STAN/WROC`).
2. **Cel:** bot dochodzi do pola depo i **staje** (plik STOP, powiadomienie). Dalej Karol: `./serwis.sh` albo ręcznie.
   Bez zakupów, bez powrotu na spot (zachowanie `WYPRAWA_TYLKO_DEPO` dla tej jednej wyprawy, nie jako pokrętło globalne).
3. **Moment:** w najbliższej spokojnej chwili (jak każda wyprawa: po walce i locie, `_blokada_startu`). Ucieczka przy niskim HP
   zachowuje pierwszeństwo przed wyprawą (jak dotąd `WYPRAWA_MIN_HP`).

## Stan dzisiaj (zmierzone 19.10, kod)

- `wyprawa.py`: `_okazja_wyprawa()` (wyzwalacze) -> `_start_wyprawa(powód, dane, teraz)`; plany `PLANY_PK` (`edron`,
  `gobliny_edron`) wybierane po położeniu postaci; `wypad.PLANY` (`rook`, `troll`, `thais_kanaly`) służą wypadowi po zapasy, a tryb
  depo ich nie używa (`BAZY_PK` nie ma `rook`: ręczne wywołanie z Rookgaardu kończy się komunikatem o braku planu, korekta po przeglądzie 19.10); stan wyprawy w
  `wyprawa_stan.json` (restart wznawia); STOP / STOP_RECZNY / ALARM_GM przerywają.
- Maszyna jest już per instancja (`bot.STOP.with_name(...)`, `INST_STAN`), więc plik `WROC` obejmie `test` i główną osobno.

## Zachowanie

- `WROC` istnieje i bot działa: przy najbliższym obiegu `_okazja_wyprawa` pomija wymagania „powody + POTWIERDZENIE” i cooldown
  (`nast_wyprawa`), zostawia **wszystkie bezpieczniki** (zablokowany/PK, `_blokada_startu`, HP, pozycja znana, plan pasuje do piętra).
  Startuje `_start_wyprawa("depo:reczny", dane, teraz)` w semantyce „tylko depo”; plik `WROC` jest usuwany **po** ruszeniu.
- Brak planu dla miejsca postaci, albo blokada trwa > `WROC_BLOKADA_MAX_S` (domyślnie 180 s): log + powiadomienie
  „Wróć do miasta: nie mogę ruszyć (powód)”, plik `WROC` usuwany (bez ponawiania po cichu).
- Wyprawa po ręcznym wywołaniu działa także przy `WYPRAWA_AKTYWNA=0` (otwarte: czy obiekt `Wyprawa` istnieje bez tego pokrętła;
  sprawdzić i w razie potrzeby tworzyć go, gdy jest `WROC`).
- Anulowanie: `./wroc.sh --anuluj` (usuwa `WROC`, jeśli wyprawa jeszcze nie ruszyła); w trakcie marszu: zwykły STOP.
- `./wroc.sh` odmawia, gdy bot tej instancji nie działa (nie ma kto wykonać) i pisze, jak uruchomić; `RETRONIC_ID` wybiera instancję.
- Dojście: ta sama trasa, co automatyczna wyprawa do depo (nagrane „do” + A*), z linami/dziurami wg mapy.

## Pliki

- `wyprawa.py`: odczyt `WROC` w `_okazja_wyprawa` (+ stała `WROC_BLOKADA_MAX_S`), flaga „depo na jedną wyprawę”.
- `wroc.sh` (nowy), w stylu `zatrzymaj.sh`. `CLAUDE.md` bota: jedna linia o poleceniu.
- Wtyczka paska (repo omarchy, `plugins/charlie.retronic/`): guzik woła `wroc.sh` z `RETRONIC_ID` instancji (dziś guziki
  Stop/Start); zmiana w repo to poziom 1, **instalacja w `~/.config` (faza 3 specyfikacji wtyczki) to poziom 2, osobna zgoda**.

## Testy i weryfikacja

1. Jednostkowe w `testy/` (atrapy jak w `test_wyprawa*`): `WROC` startuje wyprawę „depo:reczny” w spokoju i przy `WYPRAWA_AKTYWNA=0`;
   nie startuje w walce, przy niskim HP i przy PK (plik zostaje do czasu, potem komunikat po limicie); plik znika po starcie;
   plan wybierany po położeniu (`gobliny_edron`, `troll`; `rook` = odmowa z komunikatem); po dojściu STOP + powiadomienie, bez zakupów; `--anuluj`.
2. Test dymny na sucho: `./wroc.sh` na instancji bez bota (odmowa) i z botem na atrapie.
3. **Test na żywo** (osobna zgoda Karola, bot obserwowany): Mastafian z jaskini goblinów do depo Edron; kryterium: dojście bez
   utknięcia, STOP w depo, powiadomienie, zero akcji w mieście.
4. Niezależny przegląd (checker) zmian w `wyprawa.py` przed testem na żywo.

## Poza zakresem

- Zakupy/serwis po dojściu i powrót na spot (osobny krok; `serwis.sh` czeka na test na żywo).
- Akcja modelu `wroc_do_miasta` (zostaje atrapą; Haiku nie wysyła bota samodzielnie bez osobnej decyzji).
- Nowe trasy; używamy istniejących planów.

## Ryzyka

- Plan `gobliny_edron` (lina z8->z7, dojście do depo 182 pkt) był wielokrotnie przechodzony ręcznie i przez bota (Karol 19.10), ale
  ręczny wyzwalacz uruchamia go pierwszy raz: bezpieczniki wyprawy (alarm + STOP w miejscu) działają, postać może stanąć w drodze.
- Przycisk w pasku może być wciśnięty przez pomyłkę w trakcie walki: bot ruszy dopiero w spokojnej chwili, a `--anuluj` cofa.

## Fazy

- F1: `wyprawa.py` + `wroc.sh` + testy (poziom 1, repo bota). F2: test na żywo (zgoda). F3: guzik w pasku (repo) i jego
  instalacja (poziom 2, zgoda).
