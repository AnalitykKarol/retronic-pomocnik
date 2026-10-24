# SPEC: przerwa postaci pod nadzorcą (24.10)

Status: IMPLEMENTOWANE z domyślnymi (Karol nie czeka na akcept; decyzje oznaczone **DO POTWIERDZENIA KAROLA** zmienia się jednym polem albo jedną stałą).
Zlecenie (Karol 24.10): „nadzorca ma sam robić przerwy postaci i ewentualnie zmieniać spot”. Powód: gebelish po refillu potrzebowała ok. godziny przerwy, bo gracz
(Tuhandryt) ściągał na nią moby. Ręcznie (`zostan_w_depo` + `wyloguj_w_depo`) postać zostaje offline na zawsze, a `zatrzymaj.sh` stawia `STOP_RECZNY`, który
blokuje nadzorcę.

## Cel
Nadzorca (a) wylogowuje postać po refillu albo od razu, (b) po ustalonym czasie sam ją loguje i startuje bota, (c) opcjonalnie przenosi ją na inny wolny spot,
jeśli przeszkadzał gracz. Wszystko z bramkami nadzorcy; bez wpisu `przerwa` zachowanie jest dokładnie dotychczasowe.

## Pole planu (`instancje/_wspolne/plan_postaci.json`, na postać)
```
"przerwa": {"min": 60, "rozrzut_min": 10, "kiedy": "po_refillu" | "teraz", "powod": "...", "zmien_spot": "nie" | "jesli_gracz", "gracz": "Nick"}
```
- `min` 1-720 (całkowite), `rozrzut_min` 0..min (domyślnie 10; powrót = teraz + min ± rozrzut, losowo, całe minuty), `kiedy` domyślnie `po_refillu`,
  `zmien_spot` domyślnie `nie`, `gracz` opcjonalny nick, który przeszkadza (do 4 słów). Walidacja: `przerwa.py:parsuj` (zły wpis = błąd planu w `pokaz`/dzienniku,
  postać działa jak bez przerwy).
- Pola stanu pisze tylko nadzorca (atomowo, pod flockiem, razem z resztą planu): `wylogowano_t`, `do_t`, `gracz_wykryty`, `zrobione_t`, `nowy_spot`.
- **Jednorazowa**: `zrobione_t` po udanym powrocie; następna przerwa = nowy wpis (CLI `--nadpisz`).
- Format czasu w polach stanu: `RRRR-MM-DD GG:MM:SS` (jak `zrobione_t` kroków planu, NIE format grafiku bez sekund).

## Przepływ `kiedy: po_refillu` (domyślny)
1. Pierwszy refill po wpisie (też powrót po samym cap i WROC, patrz decyzje): `refill_auto.czekaj` woła `refill.sh --tlo` z `REFILL_BEZ_WYJSCIA=1`.
   `refill.sh` robi zakupy (kroki bez `wyjscie`), NIE startuje bota, stawia `STOP` (postać zostaje w mieście) i zapisuje znacznik `instancje/<id>/przerwa_refill.ok`
   (epoch, ważny 3 h).
2. Nadzorca (tick co ok. 1 min): postać online, bez bota, ze `STOP`, ze świeżym znacznikiem -> zapis `wylogowano_t` + `do_t` do planu **przed** wylogowaniem
   (nieudany zapis = brak wylogowania; nieudane wylogowanie = zapis cofnięty), potem `wyloguj.sh` + zamknięcie sesji (systemowy `STOP`, **nie** `STOP_RECZNY`).
   Kod decyzji `plan-przerwa-wyloguj` (na żywo już przy `NADZOR_NAPRAWY`). Bramki jak `wyloguj_w_depo`: `STOP_RECZNY`, `NADZOR_PAUZA`, `nadzor:false`, hold, nie w serwisie,
   spokój (brak walki 20 s), jedno zdarzenie logowania na przebieg i odstęp od poprzedniego, 3 porażki = eskalacja. Wylogowanie na przerwę NIE kończy zmiany z grafiku
   (nie trafia do `zakonczone`).
3. Offline do `do_t` (`plan-przerwa-czeka`). Po `do_t`: `sesja_start` (kod `plan-przerwa-powrot`, bramki logowania: odstęp, `max_online`, cisza nocna 01:00-08:00 odracza), potem
   `zaloguj` (kod `plan-przerwa-zaloguj`, także przy aktywnej zmianie z grafiku), potem start z miasta: `refill.sh --spot` (kod `plan-przerwa-spot`, bez zakupów) na tym samym
   albo nowym spocie. Po sukcesie `zrobione_t` i usunięcie znacznika.
4. Bot już działa po powrocie (ktoś go uruchomił): przerwa kończy się bez `refill.sh --spot` (`plan-przerwa-juz`). Zalogowana nie przez nadzorcę (ręczna gra, brak `sesja_nasza`): nie startuję bota.

## `kiedy: teraz` (CLI `--teraz`)
- Online z botem: `wroc` (kod `plan-przerwa-wroc`, nie w walce, najwyżej raz na 20 min, po 3 próbach eskalacja; nie liczy się do drabiny napraw). Postać stoi w mieście ze STOP, refill
  nie czeka (panel `wroc_refill` puste/`brak_planu`/`pominiety`, STOP starszy niż 2 min) -> wylogowanie jak wyżej. Gdy auto-refill czeka albo trwa, nadzorca czeka (`plan-przerwa-refill`,
  `plan-przerwa-stop-swiezy`), a refill idzie w trybie bez wyjścia.
- Już w mieście ze STOP: wylogowanie od razu.
- Offline: odliczanie od razu (`przerwa_start`, `wylogowano_t` = teraz), powrót po czasie jak wyżej.

## Zmiana spotu (`zmien_spot: jesli_gracz`)
Przy powrocie: jeśli `gracz` jest w planie albo przy wylogowaniu log bota (`mozg-stdout-*.log`) pokazał tego samego gracza (nie naszą postać) >= 4 razy w 60 min
(`gracz_wykryty`), a postać nie ma `spot_przypiety`, nadzorca wybiera inny wolny spot z `spoty.py` (to samo miasto, poziom, jeden bot na jaskinię; `spot_zapasowy` jeśli profil go ma)
i startuje tam (`refill.sh --spot` z MAPA/TRYB); brak alternatywy = zostaje i dziennik mówi dlaczego. Niezależnie od `zmien_spot`: jeśli dotychczasowa jaskinia jest w międzyczasie zajęta przez innego
bota, postać idzie na wolny spot (jeden bot na jaskinię). Spot przypięty nigdy się nie zmienia.

## CLI
`python3 -I plan_postaci.py przerwa <id> <min> [--teraz] [--rozrzut N] [--powod "..."] [--zmien-spot nie|jesli_gracz] [--gracz Nick] [--nadpisz]`; `przerwa <id> --anuluj` (nie rusza przerwy już trwającej).
`pokaz` wypisuje stan przerwy. Domyślnie z CLI `--zmien-spot jesli_gracz` (wpis w pliku bez pola = `nie`).

## Wyłącznik
`NADZOR_PRZERWY=0` (env) albo `"przerwy": false` w `instancje/_wspolne/nadzor_konfig.json`; domyślnie włączone. Wstrzymuje NOWE przerwy (refill idzie jak dotąd, nikt nie jest wylogowywany);
przerwa już trwająca (`wylogowano_t`) kończy się powrotem, żeby postać nie została offline na zawsze.

## Decyzje z domyślnymi (DO POTWIERDZENIA KAROLA)
1. Pierwszy refill DOWOLNEGO rodzaju (także powrót po samym cap, WROC) uruchamia przerwę. Alternatywa: tylko pełny refill po blankach.
2. Próg gracza: >= 4 wpisów „Gracz w pobliżu” tego samego nicku w 60 min przed wylogowaniem (stałe `GRACZ_PROG`, `GRACZ_OKNO_MIN` w `przerwa.py`); własne postacie pomijane.
3. Powrót czeka przez ciszę nocną (01:00-08:00): przerwa, która wypada w nocy, kończy się rano.
4. Ręczny `./refill.sh` (bez nadzorcy i bez `refill_auto`) ignoruje `przerwa` (zmienna `REFILL_BEZ_WYJSCIA` ustawia tylko `refill_auto`).
5. `zostan_w_depo` ma pierwszeństwo przed `przerwa` (postać stoi w depo bez wylogowania, przerwa czeka).
6. Wyłącznik nie przerywa trwającej przerwy (patrz wyżej).
7. `--teraz` offline od razu zaczyna odliczanie.
8. `--teraz` przy trwającym refillu czeka na jego koniec (refill idzie bez wyjścia), nie przerywa go.
9. CLI domyślnie ustawia `zmien_spot: jesli_gracz`, wpis bez pola oznacza `nie`.

## Poza zakresem / ryzyka
- `grafik.py` zostaje w cieniu; przerwa nie zmienia grafiku (zmiana, która kończy się w trakcie przerwy, kończy się bez wylogowania, bo postać już jest offline).
- Jeśli `refill.sh --spot` padnie PO zapisaniu `zrobione_t`, dalej działa istniejąca ścieżka alarm/drabina (nie ma drugiej przerwy).
- Nie sprawdzone na żywo (zakaz uruchamiania gry): zachowanie klienta przy `wyloguj.sh` po refillu, realny `refill.sh --spot` z MAPA/TRYB po relogu.

## Cofnięcie
Usuń wpis `przerwa` z planu (`plan_postaci.py przerwa <id> --anuluj`) albo `NADZOR_PRZERWY=0` / `"przerwy": false`. Pełne: przywróć kopie `*.bak-20261024-przerwa`
(`nadzor.py`, `plan_postaci.py`, `refill_auto.py`, `refill.sh`, `testy/test_wroc_refill_auto.py`, `testy/test_cap_bank.py`, `NADZORCA.md`, `STAN.md`) i usuń nowe pliki `przerwa.py`, `testy/test_przerwa.py`.

## Testy
`python3 -I testy/test_przerwa.py` (48 przypadków: walidacja, CLI, łańcuch po_refillu, bramki, `--teraz`, zmiana spotu, wyłącznik, cień, brak wpisu = jak dotąd, `refill_auto`, `refill.sh` w piaskownicy).
