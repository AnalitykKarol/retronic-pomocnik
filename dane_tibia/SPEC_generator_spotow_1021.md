# SPEC: jeden ogólny generator spotów (21.10, polecenie Karola) — ZATWIERDZONY 21.10 ~16:55 (odpowiedzi Q1–Q5 niżej); F4 ZROBIONE

Karol, 21.10 ~16:45: „chcę, żeby trasy były tworzone i testowane przez AI od początku do końca” → „rozpisz plan zrobienia go”.
Procedura ręczna, którą ten generator ma zastąpić w krokach 2–5: `mapy/PROCEDURA_nowy_spot.md`. Skill: `skille/nowy-spot/`.

## Problem (stan 21.10, zweryfikowany)

- Każdy spot ma własny skrypt ze stałymi w kodzie: `generuj_trasy_rook.py`, `_rook_raty2.py`, `_rook_bugi.py`, `_rook_bugi_z10.py`,
  `_ph.py`, `_edron_wschod.py`, `_thais_pn.py` (+ `generuj_miejsca_edron.py`, `generuj_miejsca_troll.py`). Nowy spot = AI pisze
  i debuguje kolejny plik; to dziś trwało ~1 h na Thais północ, w tym 3 nieudane podejścia na żywo.
- Wiedza z 21.10 siedzi tylko w `generuj_trasy_thais_pn.py`: strefa zakazana, wykrywanie kierunku przejść (W GÓRĘ/W DÓŁ),
  wybór zejścia najdalej od zagrożenia, dojście ciągnięte po z8 do pętli. Starsze generatory tego nie mają.
- Zasypana dziura jest wpisywana ręcznie do `pietra.ZASYPANE`; pamięć przejść zapisała Thais północ jako `"tryb": "krok"`
  (`dane_tibia/ruch/przejscia_nauczone.json`, klucz `32347,32123,7>8`), choć działa łopata + krok. Po zasypaniu dziury
  (w grze się zasypuje) pamięć „krok” poprowadzi pierwszą próbę źle; ratuje tylko to, że `ZASYPANE` dokłada łopatę.

## Cel

Jedno polecenie robi spot z deklaracji, powtarzalnie:

    python3 -I generuj_spot.py dane_tibia/spoty/thais_pn_z8.json [--zapisz] [--mapy]

Deklaracja (JSON w repo, wersjonowana, pisze ją AI albo Karol):

    {"nazwa": "thais_pn_z8", "miasto": "Thais", "pietro": 8, "start": [32356, 32131],
     "cel": ["Troll", "Rat", "Cave Rat", "Spider", "Bug"],
     "zakazane": [{"potwor": "Poison Spider", "strefa": 6}],
     "dojscie": {"z": "depo"}, "zejscie": "auto", "prog_hp": 30,
     "wymaga": ["shovel"], "uwagi": "decyzja Karola 21.10: omijać poison spidery"}

Wynik: `trasy/<nazwa>_petla`, `trasy/<nazwa>_dojscie(.meta)`, `dane_tibia/mapy/<nazwa>.png/.json`, raport (liczby, odległość
od zakazanych, wybrane zejście i dlaczego), przy `--mapy` wpis w `mapy.json` (kopia, zmiana tylko własnego klucza).

## Fazy (każda zamknięta bramką: testy + „tak” Karola na przejście dalej). Kolejność: F4 (zrobione) → F0 (zrobione) → F1 → F1b → F2 → F3

**F0 — biblioteka bez zmiany zachowania.** `spot_lib.py` z klockami obecnych generatorów: `skladowa`, `przystanki`, `petla`,
`obraz` (+ strefa na fiolet), `strefa_zakazana`, `zejscia` (reguła kierunku z `narzedzia/przejscia_pieter.py`),
`przed_przejsciem`, `ladowanie`, `dojscie_do_petli`, `zapis_spotu`. Stare generatory przełączone na bibliotekę.
Bramka: każdy stary generator `--zapisz` do katalogu tymczasowego daje pliki **identyczne bajtowo** z obecnymi w `trasy/`
(test `testy/test_spot_lib_regresja.py`); `waliduj_trase.py` OK dla wszystkich.

**F0 — ZROBIONE 21.10 ~17:30 (agenci: tester + be-dev równolegle w worktree `pomocnik-spot-lib`, checker: NITS).** `spot_lib.py`
(289 linii; API: `skladowa`, `przystanki`, `petla`, `obraz(strefa=)`, `strefa_zakazana`, `zejscia`, `ladowanie`, `przed_przejsciem`,
`dojscie_do_petli`, `spawny`, `zapis_spotu` — w specu wcześniej „zapis_mapy”), 7 generatorów przełączonych (938 → 665 linii),
`generuj_trasy_rook`/`_raty2` reeksportują stare nazwy. Bramka `testy/test_spot_lib_regresja.py`: 57/57 (stare vs nowe w kopiach
drzewa, sha256 plików + stdout + 2 przebiegi), tryb `F0_SAMOKONTROLA=1 F0_SABOTAZ=1` czerwony 47/50 (test łapie różnice);
`waliduj_trase` OK dla 15 tras (dojście z9w: znany błąd #15 z `edron_depo_trolle`). Czerwone `test_trasy_rook` 17/19 i
`_raty2` 30/31 identyczne na starym kodzie (rozjazd testu z `mapy.json` „potwory”), niezwiązane. Scalone do głównego checkoutu
(kopie starych: `.bak-f0-20261021/`), worktree usunięty. `thais_pn_z8_dojscie.meta` wygenerowany ponownie (był ręcznie edytowany;
różnica tylko w komentarzach, łopata zostaje).

**Wymagania do F1 z przeglądu F0 (checker):** (1) jedna kolejność obszaru `(x0,y0,x1,y1)` wszędzie — dziś `spawny` bierze
`(x1,x2,y1,y2)` i zła kolejność daje po cichu 0 spawnów; (2) `zejscia` przyjmuje pola składowej z piętrem albo sprawdza piętro
(dziś składowa z9 na z7 daje `[]` bez błędu); (3) `zejscia` odrzuca pole przejścia ze ŚCIANĄ (11 ze 113 pól flagi 2 w Thais)
i jest zgodne z `narzedzia/przejscia_pieter.py`; (4) testy jednostkowe reguły kierunku na innych piętrach niż z7;
(5) tryb sabotażu bramki sprawdza, że czerwienieją dokładnie zabotowane generatory; (6) `spawny(nazwy)` odrzuca gołego stringa.

**Uwaga po F0 (21.10 ~17:35):** `generuj_trasy_edron_wschod.py` zmieniony CELOWO (ogień: wejście (33119,31740), `ogien_pola`) i
`spot_lib.zejscia` (reguła przeszkody `przeszkoda_na_podlodze`, parametr `ogien`) — bramka `test_spot_lib_regresja.py` na
edron_wschod będzie czerwona względem zamrożonej kopii. Przed F1: odświeżyć bazę (`testy/dane_f0_baza/`) do stanu po poprawce
ognia albo zastąpić bramkę F0 testami F1. **F1 musi**: omijać znany ogień (`trasy/ogien_*.json`, bufor 1) w każdej pętli
i dojściu, odrzucać przeszkody w kolorze podłogi poza z7, wpisywać wymagany ekwipunek (lina/łopata) do `opis` i do raportu
(z przejść dojścia: tryb `lina`/`lopata` z pamięci przejść albo meta trasy).

**F1 — `generuj_spot.py` + deklaracje.** Pętla jednego piętra, strefy zakazane, dojście z **najbliższego** znanego depo
(Q2: Thais (32348,32225,7), Edron — zweryfikowane trasami; „najbliższe” = najkrótsza droga A* łącznie z przejściami, nie linia
prosta) przez łańcuch przejść W DÓŁ wybranych automatycznie (najpierw ≥ `min_odl` od zakazanych, potem najkrótsze), dojście
ciągnięte do pętli. Depo miast jako dane (`dane_tibia/spoty/miasta.json`); nowe miasto = jeden wpis po pomiarze w grze. Bramka: deklaracje `thais_pn_z8.json` i `trolle_edron_z9w.json` odtwarzają dzisiejsze trasy (pętla identyczna,
dojście identyczne albo różnica uzasadniona w raporcie); testy jednostkowe reguł: żółte-w-górę odrzucone, strefa nietknięta,
asercja „0 punktów w strefie”.

**F1b — pętle przez kilka pięter (Q3: tak).** Deklaracja `"pietra": [9, 10]` (zamiast `"pietro"`): składowe pięter
połączone przejściami z `przejscia_pieter` (W DÓŁ i W GÓRĘ, typ z kierunku: schody/dziura/drabina/lina), przystanki ze
wszystkich pięter, kolejność po A* z kosztem przejścia; meta `przed_zmiana_pietra`/`schody_w_dol`/`schody_w_gore` jak w
nagranych trasach (`troll_cave`). Bramka: deklaracja Edron z9+z10 wschód (`trolle_edron_z9w` + `z10w`) daje jedną pętlę,
`waliduj_trase` OK, test atrapą przejść (wzór `testy/test_wielopietrowa.py`).

**F2 — walidacja i wpis w jednym przebiegu.** `--mapy`: `waliduj_trase` pętli i dojścia, `tryb.py --sucho`, kopia
`mapy.json.bak-<data>-<nazwa>`, zapis atomowy, porównanie z kopią (zmieniony tylko własny klucz) — każda porażka = brak wpisu.
Skill `nowy-spot` przechodzi z ręcznego pisania generatora na pisanie deklaracji. Bramka: test na kopii `mapy.json`.

**F3 — pierwszy spot zrobiony wyłącznie generatorem, na żywo.** Spot wybiera Karol (Q5) z rankingu
`narzedzia/spoty_skladowe.py`; propozycje: Edron trolle z9 zachód (34 trolle + 5 niedźwiedzi) albo Edron rotwormy z8 (26). Test wg procedury krok 7: start z
`RETRONIC_POSTAC`, Monitor do pierwszego zabicia. Bramka: przejście pięter bez ingerencji, ≥ 10 zabić, `STAN.md`.

**F4 — ZROBIONE 21.10 ~17:00 (Q4: teraz) — zasypana dziura bez ręcznego wpisu.** Zrobione: `pietra._zasypana` (ZASYPANE
albo pamięć „lopata” albo `PIETRA_LOPATA_AUTO`=1), krok po łopacie na tym samym polu zapisuje się jako „lopata”
(`st["lopata_pole"]`, `_naucz(lopata=)`); pokrętło `PIETRA_LOPATA_AUTO` (domyślnie 0) w `cavebot.py`, `pokretla.py`,
`na_zywo.przyklad.json`; pamięć Thais północ poprawiona ręcznie na „lopata” (kopia `przejscia_nauczone.json.bak-20261021-lopata`).
Kopie `*.bak-20261021-lopata-pamiec`. Test `testy/test_lopata_pamiec.py` 10/10 (na starym `pietra.py`: A/B/D FAIL, pamięć
„krok” = dzisiejszy błąd); regresja: pietra_kratka 11/11, pietra_zajete 16/16, wielopietrowa 95/95, symulator 124/124,
trzy_sposoby 14/14, wyprawa_dziura_zajeta 21/21, powrot_na_spot 64/64, wypad_drzwi 30/30, obrona_pk 68/68.
Działa od następnego restartu bota (kod ładowany przy starcie). Pierwotny opis: W `pietra.py`/`wypad.py`: stoi na polu przejścia W DÓŁ
(pewnym), use bez skutku, ma shovel → próba łopaty z pola obok; sukces zapisuje w pamięci `"tryb": "lopata"` (nie „krok”),
a pamięć „lopata” zawsze zaczyna od łopaty. Pokrętło domyślnie 0, kopia `.bak`, test atrapą odtwarzający 16:35 (use bez
skutku) i 16:36 (łopata + krok). Bramka: testy pięter (kratka, zajęte, wielopiętrowa, symulator) zielone + nowy test.

## Decyzje Karola (21.10 ~16:55)

- Q1 deklaracja = **JSON w repo**. Q2 **Thais i Edron**, dojście **z najbliższego** depo. Q3 pętle przez kilka pięter **tak** (F1b).
- Q4 F4 **teraz** (zrobione) + „niech zapisze jako dziura z łopatą” (pamięć). Q5 **spoty wybiera Karol**; AI pokazuje ranking.

## Pytania (stan przed decyzjami)

- **Q1** Deklaracja spotu jako plik JSON w repo (powtarzalna, historia zmian) czy same parametry w poleceniu? Rekomendacja: JSON.
- **Q2** Dojścia z jakich miast? Zweryfikowane depo: Thais, Edron. Carlin/Venore/Kazordoon/Ab'Dendriel/Port Hope wymagają
  pomiaru depo w grze (jedna wizyta postaci). Rekomendacja: na start Thais + Edron.
- **Q3** Pętle przez kilka pięter (np. z9 + z10 wschód w Edronie) w zakresie? Rekomendacja: nie teraz — jedno piętro na pętlę.
- **Q4** F4 (łopata sama, poprawka pamięci przejść) teraz czy później? Rekomendacja: razem z F1, bo pamięć „krok” to realne ryzyko.
- **Q5** Kto wybiera spot w F3 i w przyszłości: AI sama z rankingu, czy zawsze pokazuje 3–6 kandydatów do wyboru?

## Poza zakresem

- Zmiana zachowania walki, leczenia, ucieczki, PK, ognia (zasada życia postaci w `CLAUDE.md`).
- Rozpoznanie z8 → z9 Thais północ (16 trolli): mapa nie pokazuje bezpiecznego zejścia; osobne zadanie (nagranie albo F4).
- Restart innych botów; wpisy dla postaci bez zgody Karola.

## Ryzyka

- F0 dotyka generatorów działających tras: regresja bajtowa chroni przed cichą zmianą pętli, z których chodzą boty.
- `mapy.json` edytują też inne sesje: zapis tylko przez porównanie z kopią i atomowo.
- Mapa klienta zna tylko widziane pola (`README.md`): spot w nieodwiedzonym rejonie wyjdzie poszarpany — generator ma to
  zgłosić (składowa < progu, spawn bez pola w promieniu 4), nie zgadywać.
