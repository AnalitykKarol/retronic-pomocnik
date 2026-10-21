# SPEC: K2 pewne powroty do miasta (21.10) — faza K2 z `SPEC_nadzorca_rotacja_1021.md`

Zakres: tylko WROC / wyprawa do depo / ucieczka PK. Bez zmian zachowania patrolu, wpadnięcia i `pietra.py`. Żadnych działań na żywo.

## Problem 1 — kanały Thais -> miasto (kutangen 21.10 15:37–15:38, ALARM/STOP)

- Plan `thais_kanaly` zaczynał od wyjścia (32360,32242,z8)->z7. Nikt go nigdy nie przeszedł (zgadnięte w pierwszym commicie 13.10).
  Próby: krok / Use / lina na (32360,32242) i (32360,32241), 6 bez skutku. Dodatkowo krok na (32360,32241,z7) prowadzi na z6 (DIAGNOZA dawajkesh).
- Marsz do tego wyjścia wybierał `droga_do_depo` jako „marsz do trasy 'do' (punkt 0)”: pierwszy punkt `thais_kanaly_do_miasta` leży na z8.
- Pewne wyjścia to drabiny pod kratkami z F1 (`SPEC_kratki_drabiny_thais_1021.md`): R = (32370,32213,z8), (32422,32214,z8), (32339,32183,z8).
  Użycie drabiny R (Use) ląduje w (R.x, R.y+1, z7). Pola R to ostatnie punkty z8 w `thais_dojscie_kratka`, `thais_kratka_32422_32214`,
  `thais_kratka_32339_32183` (jedno źródło prawdy). Obserwowane lądowania: (32370,32214,7) 09:30, (32422,32215,7) 08:53; (32339,32184,7) z reguły.

### Zachowanie (wdrożone w kodzie, offline)

- `wyprawa.KANALY_THAIS_DRABINY` -> pola R z trzech plików; `Wyprawa._wyjscia_kanalow` buduje wyjścia dla `droga_do_depo`
  (R, lądowanie (R.x, R.y+1, z7), pola stania). Pole stania = sąsiad R na z8 bez ściany i bez flagi 2, najpierw prostopadły i nie pod
  lądowaniem; północ od R bywa ścianą (np. (32370,32212,z8)), więc nie wolno przyjmować „y-1” (domyślne dla Edronu).
- `Wyprawa._droga_kanaly`: dla każdej drabiny osobno `droga_do_depo(poz, pętla, [depo], …, wyjscia=(drabina,))` i wybór **najbliższej**
  = najmniej kroków po z8, dopiero przy remisie krótsza całość. Marsz po z8 jest dłuższą częścią ryzyka (szczury, ciemno), z7 to ulice.
  Opis w logu: `Wyprawa: depo: droga z …: N punktów, koszt K (drabina R -> L, M pól po z8; …)`.
- `do` przekazane do `droga_do_depo` to `[depo]` (z7, `depo_troll_cave[0]` = (32348,32225,7)). „marsz do trasy 'do' (punkt 0)” w opisie to
  pierwszy punkt tej listy (pole stania obok drabiny), nigdy (32360,32242,z8): plan tej drogi nie zawiera pól (32360|32361, 32241|32242).
- `_start_wyprawa`: dla żądań depo (WROC, głód, PK ucieczka) pozycja z8 w prostokącie `KANALY_THAIS_PROSTOKAT` zawsze wybiera plan
  `thais_kanaly` (bez tego 7 pól trasy przy x=32422 wybierało plan `troll` i prowadziło do wyjścia jaskini trolli ok. 100 pól dalej).
  `_z_poz` zapisuje się w stanie jak dla PLANY_PK, więc wznowienie po restarcie buduje ten sam plan.
- Z z8 bez mapy / bez drogi: `_zbuduj_depo` zwraca błąd -> „Wyprawa: nie startuję: depo: brak …” + powiadomienie, zamiast marszu do
  zgadniętych schodów. Pętlą jest `cb.punkty`; bez niej A* po mapie (bez wczytywania pętli Edronu).
- Zwykła wyprawa po zapasy z kanałów (Gorn/Frodo), powrót `thais_kanaly_z_miasta` i `_powrot_z_depo` (PK „powrót”, wiedzie do jaskini trolli):
  bez zmian, zob. ryzyka w raporcie.

## Problem 2 — wynik

Przyczyna potwierdzona (prawdziwa mapa): nagranie jest rzadkie, a w (33167,31812,z7) jest rampa z flagą 2 (lądowanie (33167,31813,z8)),
więc plan ma stoi 2 pola od „dziury”, a wykonanie sobie radzi (`Wypad._dziura_sasiednie` z 19.10, w tym zajęta rampa; test
`test_wyprawa_dziura_zajeta` 21/21). Uwaga planu była więc ostrzeżeniem o zachowaniu, które już działa, ale nie o błędnych danych.
Nie zmieniam struktury etapu (zachowanie zajętej rampy zostaje). Zmiany:
- `sprawdz_plan(…, rampy_ok=False)`: przy `True` dziura 2 pola od stoi nie jest uwagą, gdy obok pola stania jest rampa z flagą 2
  (`_rampa_obok`); `Wyprawa` loguje plany z `rampy_ok=True`. Domyślnie ścisły lint jak dotąd (test 0a `dziura_zajeta` bez zmian).
- `zbuduj_etapy` (tylko z mapą, tylko gdy stoi 2 pola od przejścia): LINA w górę dostaje pole stania obok liny (Edron `z`: (33170,31812,z8) vs lina
  (33169,31810,z8)); DZIURA w ścianie/niewidziana bez rampy obok to właz pod nią (Rook kanały `z`: właz (32060,32173,z7), Use);
  dziura z flagą 2 albo kratka bez rampy obok dostaje pole stania obok. Z rampą obok bez zmian.

## Problem 3 — przegląd (przed / po)

Przed (ścisły `sprawdz_plan`, wszystkie `wypad.PLANY` i `wyprawa.PLANY_PK`, kierunki `do` i `z`; plany Rook `do` bez uwag):
`edron do` e19 · `gobliny_edron do` e19 · `edron z` e1 (LINA) · `gobliny_edron z` e1 (LINA) · `rook_kanaly_z11 z` e1, e3, e5 (DZIURA).
Plany zbudowane z 150 pozycji pętli (Rook ×5, kanały Thais, Edron): uwagi tylko Edron (e19/21/23/27/29, ta sama rampa).
Po: z `rampy_ok=True` zero uwag we wszystkich 20 planach i ze 150 pozycji; ścisły lint: zostają 4 uwagi z rampą obok (edron do, gobliny do,
rook_kanaly z e3, e5). Rook: schody (32027,32198,z8) i (32046,32222,z8) = krok (poprawka z dziś), bez zmian.

## Test

`testy/test_powroty_k2.py` 136/136 (na starym kodzie 39/130 przy pierwszej wersji testu): dane rzeczywiste, mapa.py, atrapa wyprawy bez gry.
Kanały: plan z 19 pozycji `thais_szczury_opt` idzie przez jedną drabinę R, lądowanie (R.x, R.y+1, z7), pole stania obok R, bez pól
(32360|32361, 32241|32242), sprawdz_plan puste, ciągły, kończy w depo; najbliższa drabina wygrywa (3 pozycje); bez mapy wyprawa nie startuje;
jaskinia trolli dalej `troll`; ucieczka PK z kanałów; stan `z_poz` i odtworzenie planu. Edron/Rook: 20 planów (`do` i `z`) bez uwag z `rampy_ok`;
ścisły lint nadal widzi rzadkie nagranie; LINA/DZIURA po poprawce.
Regresja bez zmian względem bazy: wyprawa 216/216, droga_depo 50/50, wypad_drzwi 30/30, wypad_schody_rook 10/10, przejscia_trzy_sposoby 14/14,
lina_najpierw 5/5, kratki_drabiny_thais 25/25, wyprawa_dojscie 25/25, wyprawa_dziura_zajeta 21/21, wypad_bieg 6/6, wypad_oscylacja 9/9, pietra_kratka 11/11;
czerwone tak samo przed i po: wpadniecie 74/75, trasy_rook 17/19, trasy_rook_raty2 30/31.

## Na żywo (po akcepcie Karola, jedno wywołanie, jedna postać)

Kolejność: kutangen (mapa: kanały Thais, poza walką) -> `WROC` raz; obserwacja: w logu „Wyprawa: depo: droga z …” z „wyjście liną/drabiną”,
`Wypad: drabina próba 1/N`, „lina z8 -> z7 w (R.x, R.y+1, 7)”, dojście do depo. Cofnięcie: kopie `*.bak-20261021-k2`.
