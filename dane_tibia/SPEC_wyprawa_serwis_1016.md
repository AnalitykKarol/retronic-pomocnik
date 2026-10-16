# SPEC: pełny serwis w mieście (bank, depo, plecak, jedzenie, blanki) - 16.10 — SZKIC, czeka na zatwierdzenie Karola

Cel: gdy pojemnik na runy jest pełny, bot sam robi to, co Karol robił ręcznie (16.10): schodzi do Thais, wymienia gold,
składa runy i bag w depo, kupuje nowy bag, jedzenie i blanki, ustawia okna i wraca na spot. Każdy krok jest weryfikowany
(przed/po), a każde zacięcie to alarm + STOP, nie ciche stanie. Dane z przebiegów idą do telemetrii pod model D3.

## Sekwencja (z opisu Karola, 16.10)

1. **Start:** pojemnik na runy pełny (20/20), poza walką/lootem/UH, HP ok. Trasa `troll_do_miasta` do Gorna (jak dziś).
2. **Bank (NPC od wymiany gold; nick i pozycja UNKNOWN, `Sonia` to niepewne wspomnienie Karola):** `hi` -> `change gold <N>` -> `yes`, gdzie N = liczba setek gold w plecaku (900 gold -> `9`).
   Weryfikacja: gold spadło, platinum przybyło. W repo nie ma pozycji ani nazwy tego NPC (grep 16.10), Karol pokazuje na żywo.
3. **Depo:** odkłada pełny bag z runami i platinum; zostaje ok. 300 gold, nie mniej niż 260 (minimum 260: 200 na blanki, 24 na ham, 20 na bag).
   Weryfikacja: bag zniknął z plecaka, gold w plecaku w widełkach. Istnieje: `zloz_depo.py`, WYPRAWA_DEPO_ZLOZ.
4. **Frodo:** `buy 3 ham`, od razu zjedz (jak `zakupy_miasto.py`, zweryfikowane na żywo 13.10).
5. **Sprzedawca bagów (naprzeciw Froda):** `hi` -> `backpack` -> `yes`, cena 20 gold. Karol: nazwa `Gustaw` była zmyślona. W kodzie
   to przystanek `gorn` (koniec nagranej trasy do miasta, `wyprawa.py`, NPC_DOMYSLNE), do którego bot idzie po Frodo (`powrot`);
   do potwierdzenia, czy to ten sam NPC (komenda `backpack` też).
6. **Okna:** otwórz nowy bag, potem jeszcze raz stary plecak, żeby powstały oba okna w tej kolejności
   (nowy = pojemnik na runy, wyżej; stary = główny). Weryfikacja: dwa okna, rola z `dopasuj_okna`.
7. **Xodet:** `buy 20 blank rune`, przenieś do nowego bagu (przenoszenie po położeniu okien, nie po heurystyce ról).
8. **Powrót na spot:** `depo_troll_cave` -> `troll_cave`, wtedy bot wraca do patrolu w trybie `uh`.

## Poprawki, które ten serwis wymusza (osobno, od razu)

- Drzwi (32505,32270,z8): `_drzwi_hak` pomija drzwi w odległości >= 2 i status `otw`, więc po zamknięciu za sobą bot
  stoi bez końca (16.10 11:21-11:49). Poprawka + test regresji (rekord D3 1455 jako przypadek).
- Zakupy: `czekaj()` łapie cudze `buy N` z Trade (16.10: "buy 2 bp uhs") i nick jest wpisany na sztywno (Jointoramix).
  Odpowiedź ma pochodzić od NPC (autor = nazwa NPC), nick z `RETRONIC_POSTAC`.
- Klasyfikacja bagów: `czy_runy` bierze główny plecak za pojemnik na runy, gdy większość to blanki (16.10 po zakupie).

## Do ustalenia z Karolem (UNKNOWN, nie zgadujemy)

- Nazwa i pozycja NPC od wymiany gold (Karol pokazuje na żywo; zapis do `trasy/wyprawa_sklepy.json`).
- Czy sprzedawca bagów to `gorn` z kodu i czy komenda to `backpack` (Karol: `hi`, `backpack`, `yes`).
- Budżet po depo: min. 260 gold = 3 ham (24) + bag (20) + 20 blanków (200) + zapas; Karol zostawia ok. 300. Brak 260: alarm + STOP, bez zakupów.
- Czy start dla pełnego pojemnika (20/20), czy wcześniej (np. 18).
- Czy po depo odłożyć wszystkie runy (UH, blanki, HMM), czy tylko UH.

## Weryfikacja i bramki

Testy jednostkowe na atrapach (jak `test_cavebot`), potem przebieg na żywo z Karolem przy ekranie: najpierw każdy NPC osobno,
potem cała kolejka. Pokrętło `WYPRAWA_SERWIS=0` domyślnie; włączenie dopiero po udanym przebiegu na żywo.
