# RAPORT F2: mijanie graczy — odtworzenie spotkań z telemetrii (18.10.2026)

Wygenerowano: `narzedzia/odtworz_mijanie.py` (offline, tylko odczyt) z `telemetria-2026101[5-8].jsonl` w `/home/charlie/Games/Retronic/pomocnik/logi`, 71338 próbek, rekordy do 2026-10-18T21:00, ostatnia 18.10 20:59:59. Spec: `SPEC_mijanie_graczy_1018.md`. Kod: `unikanie.Unikanie.mijanie()` + `cavebot.Cavebot._mijanie_zastosuj()` (te same funkcje, które wykona bot przy MIJANIE=1), mapa klienta `mapa/map74.otmm`.

## Wynik w skrócie (model, nie gra)

- **Przechodnie bez zmiany planu** (cel >= 80%): model 82/91 = **90%**; nagrany bot: 8/91 = 9% bez `unikanie_start`, 57/91 = 63% bez zmiany punktu trasy (specyfikacja podaje 21%, inna definicja spotkania).
- **Zawroty na minutę przy graczu polującym/stojącym obok** (cel: nie więcej niż tło): nagrany bot 4.9/min (40 w 8 min IDZ), model z mijaniem 1.0/min (12), kontrola modelu bez mijania 1.1/min (13), tło poza spotkaniami 3.0/min.
- **Czas w widoku obcego od pierwszej decyzji** (miara nowa; spotkania z decyzją po obu stronach: 15): nagrany bot 175 s, model 74 s.
- **Ustępowanie przejścia** (wąski korytarz, gracz idzie na nas, widzimy go): w 108 odtworzonych spotkaniach model ustąpił 1 raz(y); nagrania zawierają mało takich sytuacji, więc ta część jest sprawdzona głównie testami syntetycznymi (`testy/test_mijanie.py`, korytarz z wnęką), nie nagraniami.
- **Dreptanie przy graczu**: model nie ma `_wiggle`; postoje powstają tylko przy ustępowaniu (suma postoju w modelu: 1 s).

Spotkania obowiązkowe (szczegóły w sekcji niżej):

| Spotkanie | Rodzaj | Stary kod (zdarzenia) | Nowy kod (model) | Zawroty stary/nowy | W widoku stary/nowy |
|---|---|---|---|---|---|
| Palandysz 18.10 13:31:34 | poluje (117 s) | koniec×1, punkt×10, start×2, tor×2 | kierunek:odwrocenie | 4/2 | 34/24 s |
| Palandysz 18.10 14:03:40 | poluje (85 s) | blokada×1, koniec×1, punkt×8, start×2, tor×4 | bez zmian | 10/2 | 27/10 s |
| Harley Queen 17.10 18:26:40 | poluje (79 s) | koniec×1, punkt×13, start×1 | kierunek:skrot | 2/0 | 63/64 s |
| Eliu 17.10 17:44:14 | poluje (48 s) | koniec×1, punkt×6, start×1 | kierunek:odwrocenie | 1/2 | 21/0 s |
| Eliu 17.10 17:46:06 | poluje (39 s) | blokada×1, punkt×3, start×1 | kierunek:skrot | 0/0 | 25/29 s |

**Czego ten raport nie dowodzi:** zachowania w grze (gracze w nagraniu nie reagują na bota, nie ma mobów ani walki, skoki modelu na nagraną pozycję w stanach innych niż IDZ), trafności klasyfikacji „idzie w naszą stronę / stoi / zatyka przejście” na żywym ruchu, ani promienia „obrębu” mobów (UNIKANIE_MOB_PROMIEN). Sprawdza dopiero naturalna QA po wdrożeniu (F3, za zgodą Karola).

## Jak to liczono i czego to nie dowodzi

- Źródło: próbki telemetrii co ~1 s (poz, stan, stwory z `gracz: true`) i zdarzenia `unikanie_*`. **Nie ma tu mobów ani nagrania ruchu co tick**, więc to nie jest powtórka z gry, tylko model: nagrani gracze (interpolacja liniowa między próbkami) + nasz model bota (tick 0.4 s, krok co 0.55 s po trasie, A* z mapy klienta), który podejmuje decyzje nowym kodem. W stanach innych niż IDZ (WALKA, LOOT, PRZERWA, ...) model przyjmuje nagraną pozycję bota i nie decyduje (walka ma pierwszeństwo, Z3).
- Spotkanie = ciągła obecność tego samego obcego gracza w widoku (przerwa do 30 s) na spocie (z >= 8). Obcy = nie nasza postać (nasze: Mastafian, Sau Moreno, Ucho, Vermitor). Rodzaj: przechodzi (< 30 s), poluje (>= 30 s, rusza się), stoi (>= 30 s, rozrzut <= 3 pola).
- **Liczby spotkań nie zgadzają się z tabelą w specyfikacji** (84 na spocie; 63/15/6): skrypt z analizy 18.10 nie został w repo, definicja spotkania jest tu inna (przerwa 30 s zamiast nieznanej), więc porównuję stare i nowe tą samą miarą, nie z tamtą tabelą. Wszystkich spotkań z obcymi (także poza spotem): 246.
- Zawrót = krok w tył po kroku w przód: zmiana kierunku o > 90° między kolejnymi różnymi pozycjami z próbek co ~1 s w IDZ (odstępy <= 3 s). Tło (IDZ na spocie poza spotkaniami +-15 s, 5.8 h): **3.0 zawrotu/min** (specyfikacja: 4,15; miara jest zbliżona, nie identyczna).
- Model nie wie, co zrobiłby gracz, gdyby bot zachował się inaczej (gracze są nagraniem, nie reagują na nas), nie zna mobów, a pozycja bota w stanach innych niż IDZ jest nagrana, nie modelowana. Odtwarzane są tylko spotkania z dopasowaną trasą (pętla/trasa w `trasy/`); patrol po miejscach, wypad i dojście nie są objęte MIJANIE.

## Wyniki zbiorcze

| Rodzaj | Spotkań | Odtworzonych | Stary: włączył unikanie | Stary: zmienił punkt | Nowy: bez zmiany planu | Nowy: odwrócenie | Nowy: skrót | Nowy: ustąpienie |
|---|---|---|---|---|---|---|---|---|
| przechodzi | 116 | 91 | 83 (91%) | 34 (37%) | 82 (90%) | 7 | 1 | 1 |
| poluje | 19 | 15 | 15 (100%) | 14 (93%) | 9 (60%) | 3 | 3 | 0 |
| stoi | 2 | 2 | 2 (100%) | 0 (0%) | 2 (100%) | 0 | 0 | 0 |
| razem | 137 | 108 | 100 (93%) | 48 (44%) | 93 (86%) | 10 | 4 | 1 |

„Stary: włączył unikanie” = zdarzenie `unikanie_start` w oknie spotkania (to miara „zmienia plan” ze specyfikacji); „zmienił punkt” = `unikanie_punkt`/`unikanie_blokada`. „Nowy: bez zmiany planu” = żadnego odwrócenia, skrótu ani ustąpienia w modelu. Wszystkie wiersze liczą tylko spotkania odtworzone (z dopasowaną trasą).

Decyzje nowego kodu wg powodu (rodzaj spotkania, powód, akcja): poluje/oboz/odwrocenie ×3, poluje/oboz/skrot ×3, przechodzi/idzie_na_nas_wasko/ustapienie ×1, przechodzi/oboz/odwrocenie ×4, przechodzi/oboz/skrot ×1, przechodzi/ta_strona/odwrocenie ×3. Powód `ta_strona` = gracz idzie przed nami tą samą stroną pętli, `oboz` = stoi na pętli (Q1).

### Przechodnie (cel: >= 80% bez zmiany planu, dziś ok. 21%)

- Stary kod (nagranie): bez `unikanie_start` 8/91 = **9%**.
- Nowy kod (model): bez zmiany planu 82/91 = **90%**.

### Zawroty na minutę i czas w widoku gracza

| Rodzaj | Zawroty/min stary (nagranie) | Zawroty/min model bez mijania (kontrola) | Zawroty/min nowy (MIJANIE=1) | Czas w widoku stary (med. s) | Czas w widoku nowy (med. s) | Postój nowy (suma s) |
|---|---|---|---|---|---|---|
| przechodzi | 2.4 (58) | 1.6 (57) | 1.7 (60) | 0.0 | 0.0 | 1 |
| poluje | 5.4 (39) | 1.1 (12) | 1.0 (11) | 16.9 | 10.8 | 0 |
| stoi | 1.2 (1) | 0.6 (1) | 0.6 (1) | 0.0 | 0.0 | 0 |

Tło (IDZ na spocie poza spotkaniami): 3.0 zawrotu/min. Kontrola = ten sam model bota z tymi samymi graczami, ale bez decyzji mijania (sam marsz po trasie ze skokami na nagraną pozycję): to dolna granica szumu modelu, nie zachowanie bota.

Czas w widoku obcego od pierwszej decyzji (miara nowa ze specyfikacji; tylko spotkania, w których zdecydowały obie strony: 15): stary suma 175 s (med. 5.8 s), nowy suma 74 s (med. 1.2 s).

Zawroty/min = zawroty / minuty IDZ w oknie spotkania (+-15 s). W nawiasie liczba zawrotów. Czas w widoku = sekundy z obcym w oknie 15x11 pól wokół bota.

## Trasy dopasowane do spotkań

- `troll_cave`: 38
- `gobliny_edron_z8_petla`: 35
- `brak (patrol/wypad/dojście)`: 29
- `edron_trolle_petla`: 16
- `troll_pelny`: 15
- `troll_nowa_czesc`: 4

## Spotkania obowiązkowe

### Palandysz 18.10 13:31:34 (117 s w widoku, poluje, trasa gobliny_edron_z8_petla)

- Stary kod (nagranie): koniec×1, punkt×10, start×2, tor×2.
  - 18.10 13:31:35 `unikanie_start` gracz_w_promieniu
  - 18.10 13:31:35 `unikanie_punkt` punkt (33065, 31832) 5 pól od gracza Palandysz, następny punkt rotacji
  - 18.10 13:31:55 `unikanie_koniec` gracz_zniknal
  - 18.10 13:32:00 `unikanie_start` gracz_w_promieniu
  - 18.10 13:32:00 `unikanie_tor` 
  - 18.10 13:32:00 `unikanie_punkt` punkt (33079, 31838) 8 pól od gracza Palandysz, cofam się do poprzedniego punktu
  - 18.10 13:32:01 `unikanie_punkt` punkt (33080, 31838) 7 pól od gracza Palandysz, cofam się do poprzedniego punktu
  - 18.10 13:32:01 `unikanie_punkt` punkt (33081, 31838) 6 pól od gracza Palandysz, cofam się do poprzedniego punktu
- Nowy kod (model): odwróceń 1, skrótów 0, ustąpień 0, postój 0.0 s; zawrotów stary/nowy 4/2; w widoku gracza stary/nowy 34/24 s.
  - 18.10 13:31:37 `mijanie_start` {'gracz': 'Palandysz', 'odl': 7, 'kier': None}
  - 18.10 13:31:38 `mijanie_kierunek` {'akcja': 'odwrocenie', 'powod': 'oboz', 'gracz': 'Palandysz', 'odl': 7, 'kier': None, 'czas_widoku': 1}
  - 18.10 13:31:49 `mijanie_koniec` {'powod': 'gracz_zniknal', 'czas_s': 11.6, 'zmian_kierunku': 1, 'przejsc': 0}
  - 18.10 13:32:29 `mijanie_start` {'gracz': 'Palandysz', 'odl': 6, 'kier': None}
  - 18.10 13:32:53 `mijanie_koniec` {'powod': 'gracz_zniknal', 'czas_s': 24.4, 'zmian_kierunku': 0, 'przejsc': 0}
  - 18.10 13:33:10 `mijanie_start` {'gracz': 'Palandysz', 'odl': 2, 'kier': None}
  - 18.10 13:33:42 `mijanie_koniec` {'powod': 'gracz_zniknal', 'czas_s': 32.4, 'zmian_kierunku': 0, 'przejsc': 0}

| t od początku | dystans do gracza: nagranie | dystans: model | pozycja nagrana | pozycja modelu |
|---|---|---|---|---|
| 0 s | 7 | 10 | (33063, 31832) | (33060, 31832) |
| 5 s | 5 | - | (33065, 31832) | (33060, 31832) |
| 10 s | - | - | (33064, 31831) | (33054, 31832) |
| 15 s | - | - | (33067, 31834) | (33050, 31830) |
| 20 s | - | - | (33073, 31835) | (33049, 31835) |
| 25 s | - | - | (33078, 31838) | (33047, 31839) |
| 30 s | 5 | 40 | (33083, 31838) | (33049, 31843) |
| 35 s | 7 | - | (33082, 31839) | (33054, 31844) |
| 40 s | - | - | (33082, 31840) | (33058, 31846) |
| 45 s | - | - | (33082, 31842) | (33061, 31849) |
| 50 s | - | - | (33082, 31842) | (33080, 31838) |
| 55 s | - | 6 | (33082, 31842) | (33085, 31847) |
| 60 s | - | 4 | (33082, 31842) | (33085, 31847) |
| 65 s | - | 7 | (33082, 31842) | (33085, 31847) |
| 70 s | 10 | - | (33091, 31846) | (33085, 31847) |
| 75 s | 10 | - | (33091, 31846) | (33087, 31847) |
| 80 s | 10 | - | (33091, 31846) | (33089, 31847) |
| 85 s | 8 | - | (33093, 31846) | (33092, 31847) |
| 90 s | 8 | - | (33094, 31846) | (33091, 31841) |
| 95 s | 7 | - | (33095, 31847) | (33088, 31838) |
| 100 s | 4 | 2 | (33099, 31845) | (33100, 31846) |
| 105 s | 4 | - | (33099, 31845) | (33100, 31846) |
| 110 s | 5 | - | (33098, 31844) | (33096, 31846) |
| 115 s | 6 | 12 | (33097, 31846) | (33091, 31847) |

### Palandysz 18.10 14:03:40 (85 s w widoku, poluje, trasa gobliny_edron_z8_petla)

- Stary kod (nagranie): blokada×1, koniec×1, punkt×8, start×2, tor×4.
  - 18.10 14:03:40 `unikanie_start` gracz_w_promieniu
  - 18.10 14:03:43 `unikanie_punkt` punkt (33098, 31844) 5 pól od gracza Palandysz, następny punkt rotacji
  - 18.10 14:03:59 `unikanie_koniec` gracz_zniknal
  - 18.10 14:04:02 `unikanie_start` gracz_w_promieniu
  - 18.10 14:04:06 `unikanie_punkt` punkt (33106, 31849) 5 pól od gracza Palandysz, następny punkt rotacji
  - 18.10 14:04:07 `unikanie_punkt` punkt (33107, 31853) 4 pól od gracza Palandysz, następny punkt rotacji
  - 18.10 14:04:09 `unikanie_punkt` punkt (33103, 31856) 4 pól od gracza Palandysz, następny punkt rotacji
  - 18.10 14:04:34 `unikanie_tor` 
- Nowy kod (model): odwróceń 0, skrótów 0, ustąpień 0, postój 0.0 s; zawrotów stary/nowy 10/2; w widoku gracza stary/nowy 27/10 s.
  - 18.10 14:03:40 `mijanie_start` {'gracz': 'Palandysz', 'odl': 5, 'kier': None}
  - 18.10 14:03:51 `mijanie_koniec` {'powod': 'gracz_zniknal', 'czas_s': 11.2, 'zmian_kierunku': 0, 'przejsc': 0}
  - 18.10 14:04:02 `mijanie_start` {'gracz': 'Palandysz', 'odl': 6, 'kier': None}
  - 18.10 14:04:27 `mijanie_koniec` {'powod': 'gracz_zniknal', 'czas_s': 24.4, 'zmian_kierunku': 0, 'przejsc': 0}

| t od początku | dystans do gracza: nagranie | dystans: model | pozycja nagrana | pozycja modelu |
|---|---|---|---|---|
| 0 s | - | 5 | (33104, 31842) | (33105, 31842) |
| 5 s | - | - | (33104, 31842) | (33105, 31842) |
| 10 s | - | - | (33101, 31841) | (33106, 31839) |
| 15 s | - | - | (33107, 31840) | (33108, 31843) |
| 20 s | 8 | - | (33108, 31845) | (33106, 31849) |
| 25 s | 8 | 7 | (33108, 31849) | (33107, 31853) |
| 30 s | 3 | 3 | (33105, 31849) | (33103, 31855) |
| 35 s | 5 | 12 | (33103, 31848) | (33106, 31858) |
| 40 s | 6 | 20 | (33101, 31848) | (33108, 31862) |
| 45 s | 8 | 24 | (33097, 31848) | (33110, 31866) |
| 50 s | 8 | - | (33095, 31848) | (33108, 31872) |
| 55 s | - | - | (33095, 31848) | (33107, 31877) |
| 60 s | - | - | (33097, 31847) | (33104, 31880) |
| 65 s | - | - | (33099, 31850) | (33100, 31878) |
| 70 s | - | - | (33099, 31851) | (33095, 31879) |
| 75 s | 9 | 30 | (33099, 31852) | (33091, 31877) |
| 80 s | 4 | 18 | (33099, 31851) | (33088, 31873) |
| 85 s | 4 | 19 | (33100, 31849) | (33084, 31871) |

### Harley Queen 17.10 18:26:40 (79 s w widoku, poluje, trasa edron_trolle_petla)

- Stary kod (nagranie): koniec×1, punkt×13, start×1.
  - 17.10 18:26:40 `unikanie_start` gracz_w_promieniu
  - 17.10 18:26:48 `unikanie_punkt` punkt (33088, 31762) 0 pól od gracza Harley Queen, następny punkt rotacji
  - 17.10 18:27:15 `unikanie_punkt` punkt (33088, 31762) 1 pól od gracza Harley Queen, następny punkt rotacji
  - 17.10 18:27:47 `unikanie_punkt` punkt (33091, 31760) 1 pól od gracza Harley Queen, następny punkt rotacji
  - 17.10 18:27:48 `unikanie_punkt` punkt (33094, 31755) 5 pól od gracza Harley Queen, następny punkt rotacji
  - 17.10 18:27:52 `unikanie_punkt` punkt (33094, 31754) 5 pól od gracza Harley Queen, następny punkt rotacji
  - 17.10 18:27:53 `unikanie_punkt` punkt (33094, 31753) 5 pól od gracza Harley Queen, następny punkt rotacji
  - 17.10 18:27:53 `unikanie_punkt` punkt (33094, 31752) 5 pól od gracza Harley Queen, następny punkt rotacji
- Nowy kod (model): odwróceń 0, skrótów 1, ustąpień 0, postój 0.0 s; zawrotów stary/nowy 2/0; w widoku gracza stary/nowy 63/64 s.
  - 17.10 18:26:40 `mijanie_start` {'gracz': 'Harley Queen', 'odl': 6, 'kier': None}
  - 17.10 18:27:18 `mijanie_kierunek` {'akcja': 'skrot', 'powod': 'oboz', 'gracz': 'Harley Queen', 'odl': 2, 'kier': None, 'czas_widoku': 6, 'punkt': 81}
  - 17.10 18:28:10 `mijanie_koniec` {'powod': 'gracz_zniknal', 'czas_s': 89.6, 'zmian_kierunku': 1, 'przejsc': 0}

| t od początku | dystans do gracza: nagranie | dystans: model | pozycja nagrana | pozycja modelu |
|---|---|---|---|---|
| 0 s | 1 | - | (33088, 31763) | (33090, 31761) |
| 5 s | 1 | 3 | (33088, 31763) | (33090, 31761) |
| 10 s | 1 | - | (33088, 31763) | (33088, 31763) |
| 15 s | 1 | 1 | (33088, 31763) | (33088, 31763) |
| 20 s | 1 | 1 | (33088, 31763) | (33088, 31763) |
| 25 s | 2 | 1 | (33089, 31761) | (33088, 31763) |
| 30 s | 2 | 1 | (33089, 31761) | (33088, 31763) |
| 35 s | 2 | 1 | (33089, 31761) | (33088, 31763) |
| 40 s | 4 | - | (33091, 31761) | (33092, 31760) |
| 45 s | 4 | 1 | (33091, 31761) | (33091, 31761) |
| 50 s | 2 | 1 | (33089, 31762) | (33090, 31760) |
| 55 s | 1 | 6 | (33088, 31762) | (33093, 31757) |
| 60 s | 2 | 1 | (33089, 31761) | (33088, 31762) |
| 65 s | 3 | - | (33090, 31760) | (33090, 31760) |
| 70 s | 2 | 3 | (33092, 31758) | (33093, 31757) |
| 75 s | 2 | 5 | (33094, 31756) | (33094, 31751) |

### Eliu 17.10 17:44:14 (48 s w widoku, poluje, trasa edron_trolle_petla)

- Stary kod (nagranie): koniec×1, punkt×6, start×1.
  - 17.10 17:44:14 `unikanie_start` gracz_w_promieniu
  - 17.10 17:44:15 `unikanie_punkt` punkt (33088, 31746) 5 pól od gracza Eliu, cofam się do poprzedniego punktu
  - 17.10 17:44:15 `unikanie_punkt` punkt (33088, 31745) 5 pól od gracza Eliu, cofam się do poprzedniego punktu
  - 17.10 17:44:56 `unikanie_punkt` punkt (33087, 31745) 4 pól od gracza Eliu, cofam się do poprzedniego punktu
  - 17.10 17:44:56 `unikanie_punkt` punkt (33087, 31742) 2 pól od gracza Eliu, cofam się do poprzedniego punktu
  - 17.10 17:44:58 `unikanie_punkt` punkt (33087, 31742) 3 pól od gracza Eliu, cofam się do poprzedniego punktu
  - 17.10 17:44:59 `unikanie_punkt` punkt (33087, 31742) 4 pól od gracza Eliu, następny punkt rotacji
  - 17.10 17:45:15 `unikanie_koniec` gracz_zniknal
- Nowy kod (model): odwróceń 1, skrótów 0, ustąpień 0, postój 0.0 s; zawrotów stary/nowy 1/2; w widoku gracza stary/nowy 21/0 s.
  - 17.10 17:44:15 `mijanie_start` {'gracz': 'Eliu', 'odl': 8, 'kier': None}
  - 17.10 17:44:17 `mijanie_kierunek` {'akcja': 'odwrocenie', 'powod': 'oboz', 'gracz': 'Eliu', 'odl': 6, 'kier': None, 'czas_widoku': 1}
  - 17.10 17:44:36 `mijanie_koniec` {'powod': 'gracz_zniknal', 'czas_s': 20.8, 'zmian_kierunku': 1, 'przejsc': 0}

| t od początku | dystans do gracza: nagranie | dystans: model | pozycja nagrana | pozycja modelu |
|---|---|---|---|---|
| 0 s | 6 | 9 | (33089, 31747) | (33092, 31747) |
| 5 s | 4 | 9 | (33087, 31744) | (33092, 31747) |
| 10 s | 5 | 11 | (33088, 31745) | (33094, 31751) |
| 15 s | 5 | - | (33088, 31745) | (33093, 31756) |
| 20 s | 5 | - | (33088, 31745) | (33091, 31760) |
| 25 s | 4 | 21 | (33087, 31744) | (33087, 31762) |
| 30 s | 4 | 19 | (33087, 31744) | (33082, 31760) |
| 35 s | 5 | 23 | (33088, 31745) | (33080, 31764) |
| 40 s | 4 | - | (33088, 31745) | (33078, 31768) |
| 45 s | 5 | 33 | (33087, 31744) | (33081, 31771) |

### Eliu 17.10 17:46:06 (39 s w widoku, poluje, trasa edron_trolle_petla)

- Stary kod (nagranie): blokada×1, punkt×3, start×1.
  - 17.10 17:46:06 `unikanie_start` gracz_w_promieniu
  - 17.10 17:46:34 `unikanie_blokada` punkt (33076, 31732) 5 pól od gracza Eliu
  - 17.10 17:46:36 `unikanie_punkt` punkt (33074, 31732) 3 pól od gracza Eliu, cofam się do poprzedniego punktu
  - 17.10 17:46:37 `unikanie_punkt` punkt (33074, 31733) 3 pól od gracza Eliu, następny punkt rotacji
  - 17.10 17:46:39 `unikanie_punkt` punkt (33073, 31734) 2 pól od gracza Eliu, następny punkt rotacji
- Nowy kod (model): odwróceń 0, skrótów 1, ustąpień 0, postój 0.0 s; zawrotów stary/nowy 0/0; w widoku gracza stary/nowy 25/29 s.
  - 17.10 17:46:06 `mijanie_start` {'gracz': 'Eliu', 'odl': 6, 'kier': None}
  - 17.10 17:46:37 `mijanie_kierunek` {'akcja': 'skrot', 'powod': 'oboz', 'gracz': 'Eliu', 'odl': 4, 'kier': None, 'czas_widoku': 22, 'punkt': 78}
  - 17.10 17:46:56 `mijanie_koniec` {'powod': 'gracz_zniknal', 'czas_s': 49.2, 'zmian_kierunku': 1, 'przejsc': 0}

| t od początku | dystans do gracza: nagranie | dystans: model | pozycja nagrana | pozycja modelu |
|---|---|---|---|---|
| 0 s | 5 | - | (33076, 31732) | (33075, 31732) |
| 5 s | 5 | 5 | (33076, 31732) | (33075, 31732) |
| 10 s | 5 | 4 | (33076, 31732) | (33075, 31732) |
| 15 s | 5 | 4 | (33076, 31732) | (33075, 31731) |
| 20 s | 5 | 4 | (33076, 31732) | (33075, 31731) |
| 25 s | 5 | - | (33076, 31732) | (33076, 31731) |
| 30 s | 4 | 5 | (33075, 31732) | (33076, 31732) |
| 35 s | 1 | 5 | (33072, 31734) | (33076, 31736) |

## Wszystkie przechodnie (jedna linia na spotkanie)

| Kiedy | Gracz | s w widoku | Trasa | Stary (zdarzenia) | Nowy (decyzje) | Bez zmiany planu (nowy) |
|---|---|---|---|---|---|---|
| 15.10 11:49:17 | So Mi | 13 | troll_cave | start×1 | bez zmian | tak |
| 15.10 11:59:12 | So Mi | 28 | troll_cave | start×1 | bez zmian | tak |
| 15.10 12:12:04 | So Mi | 6 | troll_cave | start×1 | bez zmian | tak |
| 15.10 12:26:40 | So Mi | 6 | troll_pelny | start×1 | bez zmian | tak |
| 15.10 12:27:03 | Socrates | 0 | troll_cave | blokada×1 | bez zmian | tak |
| 15.10 12:27:25 | So Mi | 16 | troll_cave | - | bez zmian | tak |
| 15.10 12:33:38 | Socrates | 21 | troll_pelny | punkt×2, start×1 | bez zmian | tak |
| 15.10 12:34:23 | So Mi | 1 | troll_pelny | koniec×1, start×1 | bez zmian | tak |
| 15.10 12:46:42 | So Mi | 1 | troll_pelny | start×1 | bez zmian | tak |
| 15.10 12:48:23 | So Mi | 0 | troll_cave | start×1 | bez zmian | tak |
| 15.10 12:55:16 | Quben | 14 | troll_pelny | blokada×1, start×1 | bez zmian | tak |
| 15.10 12:58:40 | So Mi | 1 | troll_cave | koniec×1, start×1 | bez zmian | tak |
| 15.10 12:59:25 | So Mi | 0 | troll_cave | - | bez zmian | tak |
| 15.10 13:01:25 | So Mi | 1 | - | koniec×1 | (nie odtwarzano: brak trasy) | - |
| 15.10 13:02:03 | So Mi | 3 | troll_nowa_czesc | start×1 | bez zmian | tak |
| 15.10 13:04:58 | So Mi | 6 | troll_pelny | start×1 | bez zmian | tak |
| 15.10 13:06:04 | So Mi | 0 | troll_cave | koniec×1, start×1 | bez zmian | tak |
| 15.10 13:12:17 | So Mi | 1 | troll_cave | start×1 | bez zmian | tak |
| 15.10 13:13:31 | So Mi | 0 | troll_cave | koniec×1, start×1 | bez zmian | tak |
| 15.10 13:26:09 | So Mi | 1 | troll_cave | koniec×1, start×1 | bez zmian | tak |
| 15.10 13:29:29 | So Mi | 1 | - | koniec×1, start×1 | (nie odtwarzano: brak trasy) | - |
| 15.10 13:34:15 | So Mi | 1 | troll_cave | start×1 | bez zmian | tak |
| 15.10 13:35:30 | So Mi | 0 | troll_cave | start×1 | bez zmian | tak |
| 15.10 13:48:09 | So Mi | 0 | troll_pelny | koniec×1, start×1 | bez zmian | tak |
| 15.10 13:49:23 | So Mi | 0 | troll_cave | start×1 | bez zmian | tak |
| 15.10 13:53:39 | So Mi | 1 | troll_cave | start×1 | bez zmian | tak |
| 15.10 13:54:49 | So Mi | 0 | troll_cave | koniec×1, start×1 | bez zmian | tak |
| 15.10 14:03:32 | So Mi | 0 | troll_cave | koniec×1, start×1 | bez zmian | tak |
| 15.10 14:05:41 | So Mi | 0 | troll_cave | start×1 | bez zmian | tak |
| 15.10 14:18:35 | So Mi | 0 | troll_cave | start×1 | bez zmian | tak |
| 15.10 14:26:45 | So Mi | 0 | troll_cave | start×1 | bez zmian | tak |
| 15.10 14:28:19 | So Mi | 0 | troll_cave | start×1 | bez zmian | tak |
| 15.10 14:42:40 | So Mi | 23 | troll_cave | koniec×1, start×1 | bez zmian | tak |
| 15.10 14:46:13 | So Mi | 0 | troll_pelny | start×1 | bez zmian | tak |
| 15.10 14:48:15 | So Mi | 0 | troll_cave | koniec×1, start×1 | bez zmian | tak |
| 15.10 14:57:30 | So Mi | 0 | - | start×1 | (nie odtwarzano: brak trasy) | - |
| 15.10 14:57:57 | Kreator | 0 | - | - | (nie odtwarzano: brak trasy) | - |
| 15.10 15:00:16 | So Mi | 1 | troll_cave | start×1 | bez zmian | tak |
| 15.10 15:02:04 | So Mi | 0 | troll_cave | koniec×1, start×1 | bez zmian | tak |
| 15.10 15:26:23 | Kreator | 19 | troll_nowa_czesc | koniec×1, punkt×2, start×1 | bez zmian | tak |
| 15.10 15:29:19 | So Mi | 0 | troll_cave | - | bez zmian | tak |
| 15.10 15:30:49 | So Mi | 0 | troll_cave | blokada×1, start×1 | bez zmian | tak |
| 15.10 15:30:56 | Kreator | 1 | troll_cave | blokada×1 | bez zmian | tak |
| 15.10 15:56:22 | So Mi | 14 | troll_cave | start×1 | bez zmian | tak |
| 15.10 15:57:44 | Griefwarden | 0 | - | start×1 | (nie odtwarzano: brak trasy) | - |
| 15.10 15:58:16 | So Mi | 22 | troll_cave | start×1 | bez zmian | tak |
| 15.10 15:58:55 | Griefwarden | 4 | troll_cave | punkt×2 | odw 0, skrót 0, ustąp 1 | nie |
| 15.10 16:03:13 | Griefwarden | 3 | troll_nowa_czesc | blokada×1, koniec×1, start×1 | bez zmian | tak |
| 15.10 17:13:56 | So Mi | 8 | troll_cave | start×1 | bez zmian | tak |
| 15.10 17:31:23 | So Mi | 0 | troll_cave | start×1 | bez zmian | tak |
| 15.10 17:40:55 | So Mi | 28 | troll_pelny | koniec×1, start×1 | bez zmian | tak |
| 15.10 17:47:50 | So Mi | 7 | troll_pelny | start×1 | bez zmian | tak |
| 15.10 17:49:50 | So Mi | 1 | - | start×1 | (nie odtwarzano: brak trasy) | - |
| 15.10 17:52:02 | So Mi | 0 | troll_cave | koniec×1, start×1 | bez zmian | tak |
| 15.10 17:54:01 | So Mi | 0 | troll_cave | start×1 | bez zmian | tak |
| 15.10 18:05:55 | So Mi | 29 | troll_pelny | punkt×2, start×1 | bez zmian | tak |
| 15.10 18:12:33 | So Mi | 16 | troll_cave | start×1 | bez zmian | tak |
| 15.10 18:42:19 | Avelo | 0 | - | start×1 | (nie odtwarzano: brak trasy) | - |
| 15.10 18:43:21 | Avelo | 2 | - | start×1 | (nie odtwarzano: brak trasy) | - |
| 15.10 21:28:31 | So Mi | 0 | troll_cave | koniec×1, start×1 | bez zmian | tak |
| 16.10 09:34:29 | Starprince | 9 | - | start×1 | (nie odtwarzano: brak trasy) | - |
| 16.10 15:35:43 | Garnuch | 5 | - | start×1 | (nie odtwarzano: brak trasy) | - |
| 17.10 15:14:42 | Dominator | 15 | - | koniec×1, start×1 | (nie odtwarzano: brak trasy) | - |
| 17.10 15:14:43 | Eliu | 9 | - | start×1 | (nie odtwarzano: brak trasy) | - |
| 17.10 15:30:06 | Thanos | 30 | edron_trolle_petla | punkt×6 | odw 1, skrót 0, ustąp 0 | nie |
| 17.10 15:43:23 | Nelo | 6 | edron_trolle_petla | start×1 | odw 1, skrót 0, ustąp 0 | nie |
| 17.10 16:08:45 | Yeiko | 0 | edron_trolle_petla | koniec×1, start×1 | bez zmian | tak |
| 17.10 16:50:14 | Eliu | 4 | edron_trolle_petla | start×1 | bez zmian | tak |
| 17.10 16:55:48 | Yeiko | 28 | edron_trolle_petla | blokada×2, punkt×3, start×1 | odw 1, skrót 0, ustąp 0 | nie |
| 17.10 17:09:07 | Starosa | 0 | - | koniec×1, start×1 | (nie odtwarzano: brak trasy) | - |
| 17.10 17:28:13 | Eliu | 18 | edron_trolle_petla | start×1 | bez zmian | tak |
| 17.10 17:39:02 | Eliu | 0 | edron_trolle_petla | start×1 | bez zmian | tak |
| 17.10 17:43:48 | Harley Queen | 7 | edron_trolle_petla | koniec×1, punkt×4, start×1 | odw 1, skrót 0, ustąp 0 | nie |
| 17.10 18:13:07 | Harley Queen | 5 | edron_trolle_petla | koniec×1, start×1 | bez zmian | tak |
| 17.10 20:10:55 | Raczek | 7 | - | koniec×1, start×1 | (nie odtwarzano: brak trasy) | - |
| 17.10 20:29:44 | Kangurek | 15 | - | koniec×1, start×1 | (nie odtwarzano: brak trasy) | - |
| 17.10 20:32:44 | Raczek | 1 | gobliny_edron_z8_petla | koniec×1, start×1 | bez zmian | tak |
| 17.10 20:38:54 | Raczek | 19 | gobliny_edron_z8_petla | koniec×1, punkt×1, start×1 | odw 1, skrót 0, ustąp 0 | nie |
| 17.10 20:57:05 | Kangurek | 1 | gobliny_edron_z8_petla | start×1 | bez zmian | tak |
| 17.10 21:07:43 | Raczek | 11 | gobliny_edron_z8_petla | punkt×1, start×1 | bez zmian | tak |
| 17.10 21:46:55 | Kangurek | 5 | - | koniec×1, start×1 | (nie odtwarzano: brak trasy) | - |
| 17.10 22:10:22 | Kangurek | 9 | gobliny_edron_z8_petla | koniec×1, punkt×1, start×1 | bez zmian | tak |
| 17.10 22:18:42 | Szogun | 17 | - | start×1 | (nie odtwarzano: brak trasy) | - |
| 17.10 22:19:46 | Kangurek | 26 | gobliny_edron_z8_petla | koniec×1, punkt×5, start×1 | bez zmian | tak |
| 17.10 22:21:14 | Szogun | 12 | gobliny_edron_z8_petla | koniec×1, punkt×2, start×1 | bez zmian | tak |
| 17.10 22:26:17 | Szogun | 3 | gobliny_edron_z8_petla | koniec×1, punkt×1, start×1 | odw 1, skrót 0, ustąp 0 | nie |
| 17.10 22:34:39 | Szogun | 16 | gobliny_edron_z8_petla | punkt×2, start×1 | bez zmian | tak |
| 17.10 22:38:25 | Szogun | 18 | gobliny_edron_z8_petla | koniec×1, start×1 | bez zmian | tak |
| 17.10 22:41:22 | Szogun | 28 | gobliny_edron_z8_petla | punkt×5, start×1 | bez zmian | tak |
| 18.10 11:16:58 | Szogun | 1 | - | start×1 | (nie odtwarzano: brak trasy) | - |
| 18.10 11:29:45 | Kangurek | 0 | - | - | (nie odtwarzano: brak trasy) | - |
| 18.10 11:29:50 | Kangurek | 15 | - | - | (nie odtwarzano: brak trasy) | - |
| 18.10 11:49:47 | Kangurek | 2 | gobliny_edron_z8_petla | start×1 | bez zmian | tak |
| 18.10 11:53:42 | Boski G | 19 | gobliny_edron_z8_petla | koniec×1, start×1 | bez zmian | tak |
| 18.10 11:55:08 | Kangurek | 5 | - | start×1 | (nie odtwarzano: brak trasy) | - |
| 18.10 11:59:01 | Palandysz | 4 | gobliny_edron_z8_petla | punkt×3, start×1, tor×1 | bez zmian | tak |
| 18.10 12:03:16 | Kangurek | 10 | gobliny_edron_z8_petla | koniec×1, start×1 | bez zmian | tak |
| 18.10 12:11:16 | Palandysz | 24 | - | punkt×9, tor×2 | (nie odtwarzano: brak trasy) | - |
| 18.10 12:12:35 | Palandysz | 6 | gobliny_edron_z8_petla | koniec×1, punkt×2, start×1 | bez zmian | tak |
| 18.10 12:13:21 | Palandysz | 12 | gobliny_edron_z8_petla | punkt×2, start×1 | bez zmian | tak |
| 18.10 12:16:00 | Palandysz | 26 | gobliny_edron_z8_petla | punkt×9, start×1, tor×2 | odw 0, skrót 1, ustąp 0 | nie |
| 18.10 12:19:12 | Palandysz | 7 | gobliny_edron_z8_petla | punkt×2, start×1 | bez zmian | tak |
| 18.10 12:31:07 | Pogchamp | 10 | gobliny_edron_z8_petla | punkt×1, start×1 | bez zmian | tak |
| 18.10 12:31:57 | Palandysz | 0 | gobliny_edron_z8_petla | - | bez zmian | tak |
| 18.10 12:41:01 | Pogchamp | 3 | gobliny_edron_z8_petla | punkt×1, start×1 | bez zmian | tak |
| 18.10 12:50:48 | Pogchamp | 2 | - | koniec×1, start×1 | (nie odtwarzano: brak trasy) | - |
| 18.10 13:01:00 | Pogchamp | 0 | gobliny_edron_z8_petla | punkt×1, start×1 | bez zmian | tak |
| 18.10 13:03:59 | Raczek | 6 | gobliny_edron_z8_petla | punkt×1, start×1, tor×1 | bez zmian | tak |
| 18.10 13:17:30 | Palandysz | 9 | - | start×1 | (nie odtwarzano: brak trasy) | - |
| 18.10 13:57:15 | Palandysz | 22 | gobliny_edron_z8_petla | punkt×3, start×1 | bez zmian | tak |
| 18.10 14:08:52 | Palandysz | 6 | gobliny_edron_z8_petla | punkt×2, start×1 | bez zmian | tak |
| 18.10 14:09:53 | Palandysz | 12 | gobliny_edron_z8_petla | koniec×1, punkt×3, start×1, tor×2 | bez zmian | tak |
| 18.10 14:20:51 | Palandysz | 18 | gobliny_edron_z8_petla | start×1 | bez zmian | tak |
| 18.10 20:43:19 | Deoku Easmei | 14 | gobliny_edron_z8_petla | punkt×3, start×1 | odw 1, skrót 0, ustąp 0 | nie |
| 18.10 20:45:35 | Szogun | 30 | - | - | (nie odtwarzano: brak trasy) | - |
| 18.10 20:55:13 | Szogun | 6 | gobliny_edron_z8_petla | punkt×1, start×1 | bez zmian | tak |

