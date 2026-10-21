# SPEC: przejście pięter na trzy sposoby, z pamięcią (21.10, polecenie Karola)

Karol, 21.10 ~15:10: „postać powinna próbować podczas przejść 3 rzeczy: wejść na punkt, kliknąć na niego i użyć liny, bo tylko takie
możliwości są; zaznaczać, która zadziałała, i już pamiętać”.

## Problem (dowód)

- Kutangen, 15:06, ręczna wyprawa do depo na Rooku (`mozg-stdout-1021-1457.log`):
  - Bot stanął na (32029,32194,z9), czyli obok drabiny (32029,32195,z9).
  - W 8 próbach klikał tylko pole, na którym stał (to „drabina” liczona jako b.y-1 i „własne”), próbował liny (której nie ma) i sąsiednich pól E/W/N.
  - Drabiny nie kliknął ani razu. O 15:07:31 ALARM i STOP.
- Rano (07:40, 07:42, 11:03) to samo przejście udawało się dopiero w próbie 5/7, Use na polu (32029,32195), kiedy bot na nim stał.

## Zachowanie (pokrętło `PRZEJSCIE_TRZY_SPOSOBY`=1, domyślnie 0 = jak dotąd)

- **Kandydaci na punkt przejścia (wyprawa, przejście w górę):** pole stania z nagrania trasy, pole pod lądowaniem i pole „drabiny” (b.y-1). Liczą się tylko pola w promieniu 1 od postaci.
- **Kolejność prób:**
  - dla każdego kandydata: wejść (krok, gdy pole jest obok), kliknąć (Use), użyć liny;
  - sposób z pamięci zawsze idzie pierwszy;
  - lista jest liczona raz na etap;
  - po „brak liny” kolejne próby liny w tym etapie są pomijane.
- **Przejście w dół (wyprawa):** sposób z pamięci (krok/Use/łopata) idzie pierwszy, dalej lista jak dotąd.
- **Patrol i powrót po wpadnięciu (`pietra.py`):**
  - sposób z pamięci idzie pierwszy: `use` w górę oznacza `R`;
  - w liście są zawsze krok i Use, a przy przejściu w górę także lina.
- **Pamięć:** plik `dane_tibia/ruch/przejscia_nauczone.json`, wspólny dla wszystkich postaci.
  - Klucz to `x,y,z>z_do`, wartość: `{"tryb": krok|use|lina|lopata, "n", "t"}`.
  - Zapis jest atomowy, po każdym udanym przejściu na oczekiwane piętro.

## Pliki

- `wypad.py`: funkcje pamięci, `proby_trzy_sposoby`, `_lina`, `_dziura`, `_po_przejsciu(nauka)`. Kopia `wypad.py.bak-20261021-trzy-sposoby`.
- `pietra.py`: `_tryby` → `_tryby_baza` oraz uzupełnienie trybów i pamięci, `_naucz`. Kopia `pietra.py.bak-20261021-trzy-sposoby`.
- Pokrętło: `cavebot.py`, `pokretla.py`, `na_zywo.przyklad.json`.

## Test

`testy/test_przejscia_trzy_sposoby.py`: 14/14. Atrapa gry odtwarza 15:06:
- pokrętło 0: awaria po 8 próbach, drabina nie kliknięta;
- pokrętło 1: wyjście w 2 próbach (krok na drabinę, Use), zapis do pamięci, drugi raz 1 próba;
- pietra: pamięć `R` jest pierwsza, w liście są krok, R i lina.

Regresja: wypad, wyprawa i pietra przechodzą bez zmian (17 plików).

## Wdrożenie i cofnięcie

- Najpierw kutangen: pokrętło 1 w `na_zywo.json` i restart, potem ręczna wyprawa do depo jako jedno wywołanie.
- Cofnięcie: pokrętło 0 (zachowanie bit w bit jak dotąd) albo kopie `.bak`. Plik pamięci można usunąć bez skutków ubocznych.
