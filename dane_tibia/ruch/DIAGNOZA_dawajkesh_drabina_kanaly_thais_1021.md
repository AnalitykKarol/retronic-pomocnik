# DIAGNOZA: dawajkesh wychodzi z kanałów Thais (z8 → z7) i nie umie wrócić — 21.10

Status: **DIAGNOSED** (mechanizm pokazany na logach i offline; poprawka niezrobiona, czeka na decyzję Karola).
Zgłoszenie Karola 21.10 ~09:35: „dawajkesh mi cały czas wychodzi i nie umie wrócić, a nasz admin też nie potrafi go naprawić”.
„Admin” = druga sesja Claude w repo bota (obchód `pilnuj-botow`, transkrypt `cbcf25aa…`), która restartowała bota o 08:59 i 09:12.

## Przebieg (logi `instancje/dawajkesh/logi/mozg-stdout-1021-*.log`)

| Czas | Co |
|---|---|
| 08:47 | start `raty` (`thais_szczury_opt`), `ostrozny,ml`, bez wypraw |
| 08:53:04 | szczur zabity na (32422,32214,8); 08:53:09 loot `Ctrl+klik od gracza (32423,32214)` na (-1,0) = (32422,32214), potem (0,0), (-1,-1), (-1,1): „pusto”, `brak_okna` |
| 08:53:09 | `Wpadłem: (32423,32214,8) -> (32422,32215,7)`; 3× „brak planu po mapie”, ALARM, STOP |
| 08:59 | restart przez „admina” **bez dojścia**; bot 12 min na z7 (`[RATUNEK] cień: S2 złe piętro`), dochodzi do (32338,32200,7) i kręci się tam do 09:12 |
| 09:12 | restart z dojściem `thais_dojscie`; punkt 0 (32367,32215,7) nieosiągalny („There is no way.” wg sesji admina); do z8 postać trafia ok. 09:18 (wg sesji admina z pomocą Karola, niepotwierdzone w logu bota), 09:21 dojście zakończone |
| 09:30:25 | szczur zabity na (32370,32213,8); 09:30:26 `Loot w walce: zwłoki (32370,32213) obok` |
| 09:30:27 | `Wpadłem: (32369,32212,8) -> (32370,32214,7)`; 3× „brak planu po mapie”, ALARM, STOP. Postać stoi na z7 w (32370,32214,7) |

## Hipotezy

| # | Hipoteza | Co ją obala | Wynik |
|---|---|---|---|
| H1 | Klik lootu (Use/Ctrl+klik) w pole zwłok, które leżą na drabinie, wspina postać na z7 | lądowanie inne niż (R.x, R.y+1, z-1) albo brak kliku w R tuż przed skokiem | **POTWIERDZONA 2/2**: 08:53 klik w (32422,32214) → (32422,32215,7); 09:30 zwłoki (32370,32213) → (32370,32214,7). Wzór lądowania drabiny z `pietra.py`. Sam krok na to pole nie wspina: (32422,32214,8) jest punktem trasy `thais_szczury_opt` i bot przechodził po nim bez skoku |
| H2 | Krok na schody w górę (pościg/A*) | skok bez wcześniejszego kliku lootu | obalona dla obu przypadków (w obu klik lootu w R w tej samej sekundzie) |
| H3 | Klient idzie za uciekającym szczurem (follow) na schody | brak ataku na szczura w tej chwili | obalona 08:53 (cel już zabity, trwał loot); 09:30 atak trwał, ale lądowanie = wzór drabiny pod zwłokami |
| N1 | „Nie umie wrócić”: brak znanego przejścia z z7 do z8 w pobliżu | znane przejście w zasięgu i droga do niego po mapie | **obalona**: `thais_kanaly_z_miasta` (32360,32241,7)→z8 i `thais_dojscie` (32360,32242,7)→z8, droga A* po mapie 36 pól z (32370,32214) i 87 z (32422,32215) |
| N2 | Planner `wpadniecie._znajdz_plan` nie dochodzi do znanych schodów, bo niepewni kandydaci w górę z flag mapy zajmują wszystkie miejsca | plan znaleziony mimo kandydatów z mapy | **POTWIERDZONA offline** (prawdziwa mapa, zwykły A* `mapa.droga`, limit 4000): z kandydatami `_z_mapy_w_gore` PLAN = None w obu punktach lądowania; bez nich PLAN = jedno przejście, schody (32360,32241/32242,7) |

## Mechanizm

1. **Wyjście:** w kanałach Thais są drabiny na z8 (co najmniej (32422,32214,8) i (32370,32213,8)), których mapa nie oznacza flagą.
   Loot klika Ctrl+klik (Use) w pole zwłok i sąsiednie (`loot.py:1536`). Gdy szczur zginie na drabinie, Use wspina postać na z7.
2. **Brak powrotu:** po skoku w górę `wpadniecie.tick` (lina tylko przy spadku w dół) woła `_plan`. W `_znajdz_plan` kandydaci są
   sortowani najpierw po odległości (`kand.sort(key=(cheb, not pewne))`), a tniętych do `PLAN_MAX_KAND = 14`. Na z7 w mieście
   `_z_mapy_w_gore` daje 46–52 niepewnych przejść w górę (flaga 2 na z6, dachy/piętra domów) w odległości 6–11 pól, więc
   wszystkie 14 miejsc zajmują one, a pewne schody w dół 27+ pól dalej nie są w ogóle rozważane. Rozwinięcia na z6 zjadają
   `PLAN_MAX_ROZWINIEC = 40`. Wynik: „brak planu” 3×, ALARM, STOP (zgodnie z kodem, ale wbrew zasadzie „naprawiaj, nie zatrzymuj”).
3. **Dlaczego admin nie naprawił:** restart 08:59 bez dojścia (bot błądził po z7 i utknął w (32338,32200,7); BFS po mapie
   z tego pola nie dochodzi ani do schodów, ani do początku dojścia), restart 09:12 z dojściem od (32338,32200,7):
   punkt 0 dojścia nieosiągalny („There is no way.”).

## Czego NIE ustalono

- Czy w grze `cb.droga` (z blokadami: `_zakaz_lista`, ognie, nauczone ściany) też by dała drogę do schodów — test offline użył czystej mapy.
- Czy pod zwłokami na pewno jest drabina (nie widziałem ekranu); dowód to wzór lądowania i klik w tej samej sekundzie, 2/2.
- Ile jest takich drabin na trasie `thais_szczury_opt` (znane 2).
- Jak postać zeszła na z8 o ~09:18 (log bota tego nie pokazuje).
- Dlaczego (32338,32200,7) jest zamknięte na mapie (BFS None) i jak bot tam wszedł.

## Kierunki poprawki (do decyzji)

- A. Loot: nie robić Use na polu drabiny. Znane pola drabin (R = lądowanie − (0,1), piętro niżej) zapisać przy każdym skoku w górę
  (jak `dziury_nauczone.json`) i omijać je w Ctrl+klikach lootu (zwłoki na drabinie zostawić albo brać tylko z pola, które nie jest R).
- B. Planner: po skoku w górę o 1 piętro najpierw spróbować zejść tą samą drogą (Use na R z piętra wyżej = właz/kratka nad drabiną),
  a w `_znajdz_plan` dawać pewnym przejściom pierwszeństwo przed niepewnymi (sort `(not pewne, cheb)` albo osobna pula miejsc).
- C. Zamiast ALARM+STOP po braku planu: dojście (`thais_dojscie`) albo trasa `thais_kanaly_z_miasta` od najbliższego punktu (zasada 20.10).

Test regresji: odtworzenie offline z tego pliku (lądowania (32370,32214,7) i (32422,32215,7), oczekiwany plan przez schody (32360,32241/32242,7)).

## Dopisek 21.10 ~10:05: dojście `thais_dojscie` nigdy nie sprowadziło postaci do kanałów („utknął w świątyni”)

Zgłoszenie Karola: restart z dojściem był robiony kilka razy, bot ani razu nie doszedł, utknął w świątyni.

**Zmiany piętra dawajkesha 21.10 z telemetrii** (`instancje/dawajkesh/logi/telemetria-20261021.jsonl`, próbki `probka`):

| Przed | Po | Kto |
|---|---|---|
| 08:38 (32046,32157,11) Rook | 08:47 (32311,32248,8) | bot wyłączony, ręcznie |
| 08:53:04 (32423,32214,8) | 08:53:09 (32422,32215,7) | bot: loot na drabinie (H1) |
| 09:18:48 (32338,32184,7) | 09:18:54 (32339,32183,8) | w trakcie dojścia, ale dojście w tej sekundzie loguje „przejście pięter nieudane”; sesja admina dziękuje Karolowi = ręcznie (niepotwierdzone w logu) |
| 09:30:26 (32369,32212,8) | 09:30:27 (32370,32214,7) | bot: loot na drabinie (H1) |
| 09:34:43 (32364,32242,7) | 09:34:45 **(32360,32240,6)** | bot: dojście, krok na punkt 9 (32360,32241,7) |
| 09:35:14 (32360,32240,6) | 09:40:19 (32369,32209,8) | bot zatrzymany, ręcznie |

Bot **ani razu** nie zszedł sam z z7 na z8. Starsze logi: jedyne inne użycie `thais_dojscie` (14.10 20:07) startowało już z z8, więc to przejście
nigdy nie było sprawdzone przez bota. Trasy `thais_dojscie`, `thais_kanaly_z_miasta`, `thais_kanaly_do_miasta` są z pierwszego commita 13.10 (`2c0f38f`).

**Mechanizm (09:34):** dojście idzie poprawnie x=32367 na południe do świątyni, (32366,32239) → (32364,32240) → (32364,32242)
→ (32361..32360,32241). Ostatnie przejście trasy to (32360,32241,7) → (32360,32242,8) (`z_miasta`: (32361,32241,7) → (32360,32241,8)).
W grze krok na (32360,32241,7) przeniósł postać **w górę**, na (32360,32240,6). Mapa ma tam flagę 3 (chodliwe + 2) na z6 i na z7,
czyli według `pietra._schody` to typ „schody” (flaga 2 na obu piętrach), a lądowanie (x, y−1, z−1) pasuje do konwencji schodów
w górę z Edronu. Potem `pietra.py` z z6: „punkt przed 0 jest na z8 (cel z7)”, 5× „Przejście pięter NIEUDANE (wyczerpane pola przejścia)”,
`Dojście nieukończone … nie zaczynam głównej trasy`. Bot stoi na z6 nad świątynią.

**Restart 09:12** startował z (32338,32200,7). Z tego pola BFS po mapie nie dochodzi do żadnego punktu dojścia (wynik None), a klient
mówi „There is no way.”: to drugi, osobny powód, który zależy od tego, gdzie postać stała przy restarcie.

**Czego nie ustalono:** którędy naprawdę schodzi się do kanałów pod świątynią (nagranie z 13.10 pokazuje z8 pod (32360,32241/32242),
a dziś krok na to pole prowadzi w górę: zapis 13.10 mógł zgubić Use/inne pole przejścia); którędy Karol sprowadzał postać ręcznie o 09:18
(okolice (32338,32184,7) → (32339,32183,8), wygląda na kratkę nad drabiną) i 09:35–09:40.

**Wniosek:** restart z `thais_dojscie` nie może zadziałać, dopóki ostatnie przejście tej trasy jest złe. Potrzebne jedno sprawdzone
wejście z z7 na z8 (najlepiej kratka nad jedną z drabin: (32370,32213), (32422,32214) albo (32339,32183)) i z nim nowe dojście.

## 21.10 ~10:10: poprawka F1 (dane) wdrożona

Karol: „wszędzie są kratki, może schodzić dowolnym wejściem”. Nowe dojście `thais_dojscie_kratka` i zejścia kratkami (32370,32213),
(32422,32214), (32339,32183); `mapy.json` `raty.dojscie` przełączone. Szczegóły, dowody i F2/F3: `dane_tibia/SPEC_kratki_drabiny_thais_1021.md`.
Status: **FIX APPLIED (F1) — NATURAL QA PENDING**; F2 (planer) i F3 (loot) czekają na akcept.

Uwaga 10:10: zatrzymanie bota 10:04:57 („Trzy punkty z rzędu nieosiągalne”, kroki „nie ruszył” od 10:00 w (32368,32220,8)) NIE jest z tej
diagnozy: reset serwera ~10:00, wszystkie klienty na „Character List” (zrzut dawajkesha 10:10, obchód sesji admina 10:02). Bot chodził
niezalogowaną postacią. Ponowne logowanie prowadzi sesja admina (skrypt po jednej instancji od 10:08:59).

21.10 10:45: F2 (planer) i F3 (loot bez drabin) wdrożone dla dawajkesha, szczegóły w specu. Status: **FIX APPLIED — NATURAL QA PENDING**.
