# SPEC: kanały Thais — zejście kratką, powrót po drabinie, loot bez drabin (21.10) — ZATWIERDZONA (Karol 21.10: Q1 tak, Q2 tak, Q3 tak); F1–F3 WDROŻONE 21.10 10:45 dla dawajkesha

Źródło: `dane_tibia/ruch/DIAGNOZA_dawajkesh_drabina_kanaly_thais_1021.md`. Karol 21.10 ~10:00: „wszędzie są kratki, może schodzić
dowolnym wejściem”. Kratka leży na z7 dokładnie nad drabiną z8: zejście = Use na kratce (x,y,7) → (x,y,8); wyjście = Use na drabinie
(x,y,8) → (x,y+1,7).

## F1 — dane (ZROBIONE 21.10 ~10:10, bez restartu bota)

- `trasy/thais_dojscie_kratka.json` (+ `.meta`): (32367,32215,7) → (32369,32214,7) → (32370,32214,7) → kratka (32370,32213) → (32370,32213,8).
- `trasy/thais_kratka_32422_32214.json`, `trasy/thais_kratka_32339_32183.json`: dwupunktowe zejścia kratką (dla planera wpadnięcia).
- `mapy.json` `raty.dojscie`: `thais_dojscie` → `thais_dojscie_kratka` (kopia `mapy.json.bak-20261021-kratka`). Stare `thais_dojscie`
  (przez świątynię, prowadzi na z6) zostaje jako plik, nieużywane.
- Dowód offline: `_znajdz_plan` z lądowań (32370,32214,7), (32422,32215,7), (32338,32184,7) daje jedno przejście przez kratkę obok;
  `dojscie_od_pozycji` z 5 pozycji z7 (w tym (32422,32215) i (32338,32200)) kończy kratką (32370,32213); `pietra.kandydaci` = kratka,
  `pewne=False` (tryby zaczynają od Use). Testy: pietra_zajete 16/16, symulator 124/124, wielopietrowa 95/95, wpadniecie_poscig OK,
  wpadniecie_walidacja 10/10, wyprawa_dojscie 25/25; wpadniecie 74/75 i trasy_rook 17/19 czerwone **tak samo bez tych zmian**.
- Działa bez restartu: `Wpadniecie._przejscia` wczytuje się leniwie przy pierwszym wpadnięciu. Dojście z `mapy.json` = od następnego startu.
- Cofnięcie: `cp mapy.json.bak-20261021-kratka mapy.json; rm trasy/thais_dojscie_kratka.* trasy/thais_kratka_*`.
- QA na żywo (otwarta): następne wyjście drabiną → w logu `Wpadnięcie: … plan …` przez kratkę i powrót na z8 bez ALARM.

## F2 — planer wpadnięcia: pewne przejścia nie mogą wypaść z puli (kod)

Dziś `kand.sort(key=(cheb, not pewne))[:PLAN_MAX_KAND]`: w mieście 46–52 niepewnych przejść w górę z flag mapy (dachy) w 6–11 polach
zajmuje wszystkie 14 miejsc i znane schody 27+ pól dalej nie są liczone. Zmiana w `wpadniecie._znajdz_plan`: dwie pule —
do `PLAN_MAX_KAND` najbliższych pewnych + do `PLAN_MAX_KAND` najbliższych niepewnych; koszt (Dijkstra) bez zmian.
Test regresji: lądowanie (32370,32214,7) bez pliku kratki, oczekiwany plan przez schody (32360,32241/32242,7) (dziś None).

## F3 — loot nie klika w drabinę (kod)

Pola drabin = `L` zejść w dół przez kratkę z danych (`_wczytaj_przejscia`) + pola nauczone przy każdym wpadnięciu w górę o 1 piętro
(R = (lądowanie.x, lądowanie.y−1, z0), zapis jak `dziury_nauczone.json`, osobny plik `trasy/drabiny_nauczone.json`; NIE jako ściana:
(32422,32214,8) jest punktem trasy). Każdy Ctrl+klik/Use lootu (`loot.py`: `ekran.otworz` w otwieraniu zwłok, `_otworz_dalsze`,
`krok_w_walce`) pomija pole drabiny i loguje to raz. Test: zwłoki na polu drabiny → zero kliknięć w to pole.

## Pytania (Q)

- Q1: zwłoki leżące na drabinie — **zostawić** (rekomendacja: strata to kilka gp ze szczura) czy brać z innego pola (nie da się bez ryzyka)?
- Q2: F2 i F3 za pokrętłami (`WPADNIECIE_PLAN_PULE`, `LOOT_BEZ_DRABIN`) z domyślną 1 dla dawajkesha, czy domyślnie 0 jak reszta nowych rzeczy?
- Q3: wdrożenie F2+F3 wymaga restartu bota dawajkesha (jedno wywołanie, ustawienia bez zmian) — po akcepcie.

## Wdrożenie 21.10 10:45 (dawajkesh)

- Odpowiedzi: Q1 zwłoki na drabinie zostają; Q2 pokrętła w kodzie domyślnie 0, w `instancje/dawajkesh/na_zywo.json` = 1
  (kopia `na_zywo.json.bak-20261021-drabiny`); Q3 restart.
- Kod: `cavebot.py` (pokrętła, podpięcie `loot.DRABINY` w `_wp()` przy każdym obiegu, bo pokrętła z `na_zywo.json` przychodzą po
  pierwszym `_wp()`; „drabina” w powodach odłożenia lootu w walce), `wpadniecie.py` (pule F2, `wczytaj_drabiny`, `ucz_drabine`,
  nauka przy wyjściu w górę), `loot.py` (`DRABINY`, `_drabina`, straż w `_otworz_z_pamiecia`, `_otworz_dalsze`, `_otworz_bez_pamieci`,
  `krok_w_walce`), `pokretla.py`, `na_zywo.przyklad.json`. Kopie przed zmianą: `*.bak-20261021-drabiny`.
- Test: `testy/test_kratki_drabiny_thais.py` 25/25 (na kodzie sprzed zmian: F2 FAIL, F3 nie istnieje). Bez zmian względem bazy:
  test_cavebot 478/481, test_wpadniecie 74/75, loot_otwieranie 24/24, loot_walka 35/35, wielopietrowa 95/95, pietra_zajete 16/16,
  wpadniecie_walidacja 10/10, wpadniecie_poscig OK, wyprawa_dojscie 25/25, uh_cavebot 51/54.
- Przegląd: checker NITS (bez blokerów); poprawione: try przy podpięciu, docstring, format listy w `ucz_drabine`; podpięcie po
  pokrętłach (wyszło na żywo przy pierwszym restarcie 10:43: brak linii „Loot: … pól drabin”, drugi restart 10:45).
  Zostawione świadomie: zbiór obejmuje też lądowania zwykłych dziur (więcej pominiętego lootu, kierunek bezpieczny).
- Na żywo 10:45:14: `pokrętło WPADNIECIE_PLAN_PULE: 1`, `LOOT_BEZ_DRABIN: 1`, `Loot: 76 pól drabin bez Ctrl+klik`, bot walczy na z8.
- Cofnięcie: `cp instancje/dawajkesh/na_zywo.json.bak-20261021-drabiny instancje/dawajkesh/na_zywo.json` (+ restart), kod z kopii `*.bak-20261021-drabiny`.
- QA na żywo (otwarta): szczur zabity na drabinie → w logu „(x,y) drabina” albo `przerwane drabina`, postać zostaje na z8;
  gdyby jednak wyszła: plan wpadnięcia przez kratkę i powrót bez ALARM.

## F4 — zejście kratką z planu wpadnięcia: najpierw Use (21.10 13:46, kolanoth)

- Objaw (zgłoszenie Karola ~13:40): kolanoth po wyjściu z kanałów nie wraca, Karol schodzi ręcznie. Log `instancje/kolanoth/logi/mozg-stdout-1021-1330.log`
  13:37:31–41: plan po mapie `(32370,32213)z7>z8` (kratka z F1 znaleziona), `próba 1/5 (krok Up)`, `pole bez skutku po 1 próbach`,
  `wyczerpane pola przejścia`, ALARM, STOP. To samo o 13:04.
- Mechanizm: przejścia z `trasy/*.json` są w `wpadniecie._wczytaj_przejscia` „pewne”, a `Pietra._tryby` dla pewnego zejścia brał
  `TRYBY_DOL_DANE` (krok, łopata…). Kratki nie otwiera się krokiem (tylko Ctrl+klik), a po kroku postać stoi na kratce i krok wypada z listy.
- Poprawka `pietra.py` `_tryby`: pewne zejście, którego pole nie ma na mapie flagi 2 (dziura) = kratka/klapa → `TRYBY_DOL_DANE_DOMYSL`
  (use, krok, use, łopata, krok). Pewne dziury z flagą 2, wejścia w górę i niepewne przejścia bez zmian. Kopia `pietra.py.bak-20261021-kratka-use`.
- Zasięg (checker): 24 z 59 zejść bez flagi 2, czyli też kratki Edronu (33168,31823,z8; 33167/33169,31813,z7: uwaga z 19.10 w `pietra.py` o depo)
  i kanały Rooka. Na schodach koszt to jeden zbędny Ctrl+klik; krok jest drugą próbą.
- Test: `testy/test_pietra_kratka.py` 11/11 (na starym kodzie 3 FAIL). Bez zmian: wielopietrowa 95/95, symulator_pietra_zgodnosc 124/124,
  wpadniecie 74/75 (ten sam FAIL na starym kodzie). Przegląd: checker APPROVE (2 drobne uwagi: komentarz dopisany, test Edronu opcjonalny).
- Wdrożenie: kolanoth `na_zywo.json` `LOOT_BEZ_DRABIN`=1 i `WPADNIECIE_PLAN_PULE`=1 od 13:42 (kopia `na_zywo.json.bak-20261021-drabiny`),
  restart bota 13:46:13 (`raty ostrozny,ml`): `Loot: 76 pól drabin`, start na trasie (punkt 70/90). dawajkesh jest teraz w Edronie;
  nowa `pietra.py` wejdzie u innych botów przy ich najbliższym restarcie.
- Nie ustalono: kto sprowadził kolanotha na z8 między 13:37:40 a 13:39:13, gdy bot stał, i kto uruchomił bota o 13:39:12.
- QA na żywo (otwarta): następne wyjście kolanotha na z7 → w logu `próba 1/5 (use …)` i powrót na z8 bez ALARM.
