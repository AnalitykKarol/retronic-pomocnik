# Analiza utknięć postaci, 21–23.10 (23.10 do ok. 14:20)

Zgłoszenie Karola 23.10: „postacie ostatnio ogólnie utykają w jakichś miejscach”. Tylko analiza: żadnych zmian w kodzie,
ustawieniach, trasach ani akcji w grze. Dane: `instancje/<id>/logi/` (`mozg-stdout-*`, `telemetria-*.jsonl`, `ratunek-*.jsonl`),
`refill.log`, `serwis-*.log`. Odniesienia: `STAN.md`, `PIETRA.md`, `DIAGNOZA_*_1021.md`.

## 0. Jak czytać liczby (ograniczenia metody)

- Twarda miara stania to tylko telemetria D3 (`d3_wynik.stoi_s`). Zawieszki D3 w stanie PRZERWA to zaplanowane przerwy bota
  (`Przerwa na 115 s`) i zostały WYKLUCZONE. Zostało 77 zawieszek / 117,7 min (z 118 / 169 min surowych).
- Czasy „okno” przy skupiskach pochodzą z epizodów (linie logu w tym samym miejscu, przerwa <=120 s) i są GÓRNYM szacunkiem:
  obejmują normalne polowanie i loot. Skupisko bez D3 (np. Edron `trolle_edron` z9) to polowanie, nie zacięcie.
- Surowa liczba linii `krok <Dir> … nie ruszył` (ok. 5900 w trzech dniach) NIE jest miarą zacięcia: to zwykłe tarcie w walce
  (stwór zmienia pole między zrzutem a krokiem). Przykład: `wydra/mozg-stdout-1023-0806.log`, 258 takich linii rozproszonych
  po korytarzu bez zacięcia.
- Dni nie są znormalizowane godzinami pracy bota. 23.10 obejmuje tylko pół dnia.

## 1. Ogólny obraz (D3 bez PRZERWA)

| Dzień | zawieszek | minut stania |
|---|---|---|
| 21.10 | 29 | 71,2 |
| 22.10 | 17 | 16,9 |
| 23.10 | 31 | 29,5 |

- Po instancji: wydra 34 / 34,2 min; invincible 14 / 33,5; dawajkesh 11 / 21,4; kolanoth 5 / 9,3; kutangen 5 / 7,8;
  gebelish 3 / 5,8; odchyd 5 / 5,7.
- Zakończenie: ruch (sam ruszył) 35 / 65,8 min; stop 19 / 34,0; walka 16 / 11,3 (wszystkie 23.10, wydra); piętro 7 / 6,5.
- Tendencja: 21.10 to głównie bicie w ściany i „ukryte blokady” (do 844 s). Po KROK_ZLY (wdrożone 22.10 ~12:30) zacięcia
  w osiach spadły (od 22.10 12:32: 35 zdarzeń / 33,9 min), a RATUNEK S4 spadł 87 -> 81 -> 49, S2 58 -> 22 -> 11.
  Rośnie klasa „stwór na polu kroku / klik bez efektu”: `krok_mob` 132 -> 142 -> 220 (21/22/23.10).
- Zdarzenia ogółem (21+22+23.10): STOP 173 (z czego 20.10 12), ALARM 57, RATUNEK 509 (S1 21, S2 91, S3 85, S4 217, S5 33, S6 22),
  `pietra_proba` 1463, `pietra_fail` 108, `wpadniecie_fail` 138, `wypad_pietra` 179, `krok_zly` 167 (0/56/111).

## 2. Tabela: miejsce x przyczyna

Skróty zakończeń: sam = ruszył samoczynnie; STOP-bot = bot sam zapisał STOP po ALARM-ie; STOP-? = STOP bez ustalonego źródła
(człowiek `STOP_RECZNY` albo globalny; w `mozg-stdout` nie da się odróżnić). „Czas” to D3 bez PRZERWA, chyba że napisano „okno”.

| # | Miejsce (mapa/spot) | Współrzędne | Przyczyna | Zdarzeń | Postaci | Czas stania | Zakończenie | Przykład (plik:linia) |
|---|---|---|---|---|---|---|---|---|
| 1 | Thais jaskinia trolli, `trolle_patrol` z8 (wydra, 23.10) | (32464–32482, 32232–32288), (32481,32287) | Troll „odl 1”, wydra hp100, żadnych obrażeń, ale 5 klików bez efektu -> ign 30 s -> pętla ~42 s (duch w kliencie / inne piętro?) | 16 D3 koniec=walka + 62 „5 klików” (wydra 37, invincible 25); 15 razy w (32469–72,32235–37) | 1 (wydra); wcześniej też invincible | 11,3 min D3 + ok. 20 min okna 23.10 | pętla; RATUNEK S3/S4/S6; ALARM „Walka: 3 utknięcia w 5 min (Troll)”; STOP-? 11:38:28 | `wydra/logi/mozg-stdout-1023-1106.log:1001–2147`, `:3238`, `:3457` |
| 2 | Thais `thais_pn_z9`/dojście Gebelisha z10 | (32339,32122,z10) | Cave Rat (spoza `--potwory`) na polu kroku Down; brak walki z blokującym; ściany dostają zakaz 300 s | 1 epizod 3 min 12 s (Cave Rat 41 wzmianek w klastrze; D3 195 s) | 1 (gebelish) | 195 s | STOP-bot (ALARM `wyprawa: utkniecie`, bot sam zapisał STOP 13:45:13) | `gebelish/logi/mozg-stdout-1023-1248.log:3442–3593` |
| 3 | Thais kanały `trolle_patrol` z8, korytarz | (32479–32494, 32283–32297) | bicie w ścianę (`mapa przechodnie False`), oscylacja Left/Right/Down, stwór na polu kroku, loot przerwany | 223 epizody, mapaF 689, krok_mob 101 (Rotworm 60, Troll 29), loot_przerwany 92, ratunek 44, D3 11 | 2 (wydra 137, invincible 86) | D3 23 min; okno 247 min (górne) | głównie sam, 9 STOP-? | `wydra/logi/mozg-stdout-1022-0838.log:848–937` (oscylacja), `invincible/logi/mozg-stdout-1021-1208.log:3608–3641` (Rotworm na polu) |
| 4 | Thais kanały: przejście pięter z8 <-> z9 | z8 (32497–32509, 32267–32273), z9 (32497–32509, 32271–32284) | wielokrotne próby przejścia (krok Up/Left/Down, R+Ctrl+klik), `pietra_proba` 109 + 79, drzwi 17, `wpadniecie_fail` 12 | 164 epizody; D3 16 | wydra, invincible | D3 22,4 min; okno 181 min (górne) | sam | `wydra/logi/mozg-stdout-1023-0806.log:464, 688, 834, 891`; `invincible/logi/mozg-stdout-1021-0809.log:8692` (10 razy „5 klików” z9 (32497,32281)) |
| 5 | Brak liny: wypad `gobliny_edron` z8 -> z7 | (33107,31846,z8) -> (33107,31848,z7) | `lina_ekran: nie widzę liny` (plecaki bez liny); 3 warianty (drabina/schody) nie mogą zadziałać; 15 prób `bez_zmiany_pietra`; rotacja napraw 3/3 | wypad_pietra 42 i ALARM 7, STOP 6 w skupisku; lina_ekran 23 (kutangen 14, invincible 7, gebelish 2) | invincible, kutangen, gebelish | D3 34 s (23.10 11:46) | STOP-bot po rotacji 3/3 | `invincible/logi/mozg-stdout-1023-1012.log:6056–6166` |
| 6 | Przejścia pięter Edron, depo/zejścia | (33170,31820,z8), (33070,31720,z10), (33130,31730,z10, kolanoth) | `pietra_fail` 15 + 5 + …, `wpadniecie_fail` 13 + 22 | pietra_fail 108, wpadniecie_fail 138 (105/27/6 w 21/22/23.10) | dawajkesh, invincible, kolanoth | brak w D3 | sam / wyprawa kończy | `dawajkesh/logi/mozg-stdout-1022-0818.log:407`; `kolanoth/logi/mozg-stdout-1021-1736.log:356`; `dawajkesh/logi/mozg-stdout-1022-1012.log:2818, 2843` |
| 7 | Edron `trolle_edron` z8/z9 | z9 (33081–33094, 31739–31745); z8 (33069–33088, 31731–31745) | Troll na polu kroku (krok_mob 47 + 65); `utknięcie`; KROK_ZLY nie nakłada zakazu przy stworze na polu | 95 epizodów, D3 1 | dawajkesh, invincible | D3 2,2 min (reszta to polowanie); dawajkesh 22.10 08:26–08:30 219 s | STOP-? (4 STOP w skupisku) | dawajkesh 22.10 08:26 (krok_mob 20 + utknięcie 4) |
| 8 | Rook `rook_kanaly_z11` | (31977–31986, 32150–32161), (32022–32046, 32143–32151) | ukryta blokada przy `mapa True` bez stwora (Left/Up nie ruszają), skosy awaryjne 26 | 51 epizodów, D3 14 | wydra, kutangen, odchyd | D3 ok. 20 min; wydra 21.10 (32041,32147,z11) 477 s | sam; bez STOP | `telemetria-20261021.jsonl:10223`, `wydra/logi/mozg-stdout-1021-0747.log:8154–8156` |
| 9 | Thais z8 kanały (invincible 21.10) | (32473,32289,z8), (32502,32273,z8) | pola w osiach nie ruszają przy `mapa True`, bez stwora (ukryta blokada) | 3 duże D3 | invincible | 844 s (najdłuższy), 264 s | sam | `invincible/logi/telemetria-20261021.jsonl:11071`, `mozg-stdout-1021-0809.log` ok. 10:00 |
| 10 | Thais `raty` z7 / drabina | (32340,32200,z7), (32368,32220,z8), (32370,32210) | brak stania w pętli; wpadniecie_fail 9, RATUNEK S2/S4 po 9 razy; D3 stop 273 s | kilka | dawajkesh, kolanoth, odchyd | 352 s (21.10, dawajkesh) + 273 s + 335 s (kolanoth (32049,32216,z8) stop) | stop / sam | `telemetria-20261021.jsonl:7714` |
| 11 | Serwis Edron: depo | (33171–33172, 31797–31806, z8) | „krążę: 4. wejście na pole”, 6 nieudanych Up; okna niezgodne z ekranem; wiadomość 'hi' bez odpowiedzi | ok. 6 przebiegów serwisu | invincible, dawajkesh, wydra | D3 97 s (invincible 23.10 13:56:53) | STOP-bot serwisu | `invincible/serwis-1022-koniec.log:16–17`, `serwis-1022-koniec2.log:18`, `dawajkesh/serwis-1022-reczny.log:22` |
| 12 | STOP równoczesny | gebelish (32328,32124,z8) i odchyd (32005,32139,z11), 23.10 10:01:44/45 | prawdopodobnie STOP globalny (człowiek/system); wniosek, nie dowód | 2 | 2 | 107 s i 105 s | STOP-? | `telemetria-20261023.jsonl` (obie D3 stop) |

Przyczyny, których w danych NIE widać jako osobnych skupisk: „loot przy drabinie” poza znanym przypadkiem odchyda; „drzwi” poza
znanym Xodetem (31 zdarzeń `drzwi` ogółem, głównie w skupisku #4: 17); „plecak/okna” poza serwisem (#11) i lina_ekran (#5).

## 3. Ranking: top problemów (częstość x czas x ryzyko dla życia)

### P1. Troll „odl 1”, ale klik bez efektu (wydra, jaskinia trolli Thais) — NOWE, rośnie

- Liczby: 62 razy „5 klików bez efektu” (tylko Troll; wydra 37, invincible 25); 23.10 16 D3 koniec=walka (11,3 min) + ok. 20 min
  epizodów, ALARM i STOP w jednym okresie 11:11–11:38.
- Mechanizm (kod): limit klików `ATAK_LIMIT_KLIKOW`, `cavebot.py` ~7035–7060: po 5 klikach bez efektu Escape i ignorowanie
  celu 30 s, potem „brak postępu przez 8 s, walczę 8 s”, cykl ~42 s. Bot stoi, bo żadna gałąź nie zmienia POZYCJI. Wydra ma hp100
  przez 17 min, więc stwór jej nie bije: wygląda na „ducha” w kliencie albo stwora z innego piętra widzianego na ekranie
  (zob. `monitor_wykrycia.py`, sygnał „duch w kliencie” od 23.10; STAN.md:51, :69 o duchach po relogu).
- Przyczyna: NIEUSTALONA (brak `z` stwora w logu).
- Poprawka (naprawa, nie STOP): po drugim cyklu „5 klików” na tym samym `id` wymusić zmianę pozycji: inna droga / klik obok /
  odejście o >=4 pola od celu, a po trzecim restart klienta mechanizmem okna (jak po resecie serwera).
- Ryzyko: odejście od tłumu trolli raczej zmniejsza ryzyko; ale zmiana progów ignoru/walki dotyka życia -> DECYZJA KAROLA.

### P2. Potwór spoza listy `--potwory` blokuje dojście/wypad, a bot kończy STOP-em — ZNANE, w toku (a)

- Liczby: gebelish 23.10 13:42–13:45 Cave Rat, 3 min 12 s, STOP-bot; Cave Rat 41 wzmianek w skupisku; ta sama klasa: Poison Spider
  (14:09 `gebelish/logi/mozg-stdout-1023-1407.log`). Znane, w toku u innego agenta (`cavebot.py`/STAN.md). Nie ruszać.
- Mechanizm (kod): `kand` filtrowane listą (`cavebot.py` ~4883), `_wypad_bieg` liczy `obok` tylko z `kand` (`cavebot.py:1523–1570`,
  linia ~1537), a `KROK_ZLY` pomija pola ze stworem (`krok_do`, `cavebot.py` ~4189, warunek `not inni_`), więc ściany dostają zakaz,
  a stwór nigdy nie jest atakowany. Efekt: `Wypad: błąd utkniecie` -> ALARM -> bot sam zapisuje STOP (`:3593–3597`).
- Poprawka: w dojściu/wypadzie walka z DOWOLNYM stworem stojącym na polu kroku >=N s; zamiast STOP rotacja napraw.
- Ryzyko: Poison Spider, ogień (`OGIEN_*`), PK, progi HP -> DECYZJA KAROLA, każde poszerzenie celów walki.

### P3. Przejścia pięter bez wymaganego narzędzia (lina) i wielokrotne próby — CZĘŚCIOWO ZNANE

- Liczby: lina_ekran 23; błędy `*_bez_zmiany_pietra` dawajkesh 51, invincible 34, kutangen 33, wydra 17, gebelish 8;
  `pietra_proba` 1463 (13/738/405/307), `pietra_fail` 108 (54/47/7 w 21/22/23.10), `wypad_pietra` 179, `wpadniecie_fail` 138 (105/27/6);
  skupisko #5 (invincible 23.10 11:44–11:46: 15 prób, rotacja 3/3, STOP).
- Mechanizm: wypad `gobliny_edron` wymaga liny przy (33107,31846,z8) (STAN.md:308), a przy braku liny w obu plecakach
  (blue backpack 20 rzeczy, backpack 15) rotacja napraw próbuje drabiny i schodów, które tam nie działają (`wypad.py`/`pietra.py`;
  numery linii niezbadane w tej analizie).
- Poprawka: sprawdzić linę przed wypadem/wyprawą (już w serwisie) i, gdy brak, odpuścić ten wypad na dany cykl i iść trasą,
  która liny nie wymaga, albo doprowadzić linę w serwisie; nie wchodzić w rotację 3/3 prowadzącą do STOP.
- Ryzyko: niskie (zmiana kolejności decyzji), nie dotyka walki/HP.

### P4. Stwór na polu kroku w ciasnych korytarzach (Rotworm, Troll) — częściowo pokryte KROK_ZLY

- Liczby: `krok_mob` 515 (21/132/142/220 w 20/21/22/23.10), skupisko #3 (223 epizody, D3 23 min), Edron #7 (dawajkesh 22.10 219 s STOP).
- Mechanizm: `KROK_ZLY` (stałe `cavebot.py:617–623`, zapis ~2741) nakłada zakaz po 2 nieudanych krokach (45–180 s; ściana wg mapy
  300 s; dojście 4 s), ale `krok_do` (~4189) nie nakłada go, gdy na polu kroku stoi stwór. Nieudana strzałka kosztuje ok. 1,5 s.
- Poprawka: przy stworze na polu kroku >=2 razy z rzędu: atak tego stwora (jeśli z listy) albo klik obok/inne pole obok; nie bić
  w to samo pole.
- Ryzyko: małe, jeśli dotyczy stworów z listy celów; poza listą jak P2 (decyzja Karola).

### P5. „Ukryta blokada” w osiach przy `mapa True` bez stwora — duża, ale głównie 21.10, po KROK_ZLY słabnie

- Liczby: invincible 21.10 (32473,32289,z8) 844 s; wydra 21.10 (32041,32147,z11) 477 s; dawajkesh `raty` (32340,32200,z7) 352 s;
  kolanoth (32049,32216,z8) 335 s; Rook `rook_kanaly_z11` D3 14 zdarzeń / ok. 20 min; skosy awaryjne 206.
- Mechanizm: greedy kroki w osiach bijące w pole z błędnym „przechodnie” (`krok_do`, `cavebot.py` ~4090–4210). KROK_ZLY (22.10) i
  dziura z7 (32467,32233) (oznaczona offline 23.10 ~11:50, STAN.md:18, działa od następnego startu bota) to wdrożone/znane poprawki.
- Poprawka: zostaje obserwacja; po 22.10 12:32 jest 35 zdarzeń / 33,9 min w całym systemie. Ocenić po restarcie wszystkich instancji.
- Ryzyko: brak.

### P6. Bot sam zapisuje STOP po ALARM-ie (naruszenie zasady „naprawa, nie STOP”) — przekrojowe

- Liczby: STOP 173 (80/52/29 w 21/22/23.10), ALARM 57 (31/3/6), z czego `wyprawa: utkniecie`, `*_bez_zmiany_pietra`, „wpadłem z z8 na z7”,
  krok serwisu „krążę”. Przykłady: `gebelish/logi/mozg-stdout-1023-1248.log:3593–3597`; `invincible/serwis-1022-koniec.log:16–17`;
  `invincible/logi/mozg-stdout-1023-1012.log:6056–6166`.
- Poprawka: zamiast STOP po wyczerpaniu rotacji napraw: powrót do ostatniego bezpiecznego punktu trasy (pętla `wroc`) i dalej;
  STOP tylko, gdy postać jest zagrożona.
- Ryzyko: zależy od implementacji; powrót zamiast STOP raczej zmniejsza ryzyko stania w polu walki, ale zmiana
  zachowania przy niskim HP lub PK to DECYZJA KAROLA.

### P7. Serwis Edron: depo (33172,31797–31806) i okna — ZNANE (Invincible)

- Liczby: ok. 6 przebiegów z zacięciem; D3 97 s (23.10 13:56:53). Znane: 6 nieudanych kroków Up z (33171,31797,z8) przy depo.
  Plus krok `blanki` (wydra `refill.log` ok. 14:06) — znane, w toku (b) u innego agenta. Nie ruszać `serwis_akcje.py`.

### P8. Zacięcia znane, nie odkrywane na nowo

- Drzwi sklepu Xodeta (32400,32217,z7): 3 nieudane próby (wydra), potem przejście przy `use`.
- Odchyd: dwa wejścia na drabinę (32370,32213,z8) przy lootowaniu (`odchyd/logi/mozg-stdout-1023-1345.log` 13:46).
- KROK_ZLY: ukryta blokada (32478,32273,z8): wdrożone 22.10 ~12:30, 20/20 testów (`testy/test_krok_zly.py`).

## 4. Znane / w toku (tylko wymienione, nie badane)

- (a) Dojście Gebelisha na `thais_pn_z9` blokowane przez Poison Spider spoza `--potwory` + brak leczenia w dojściu
  (`gebelish/logi/mozg-stdout-1023-1407.log` 14:09): znane, w toku u innego agenta (P2).
- (b) Krok `blanki` serwisu nie przeniósł blanków do torby (wydra `refill.log` ok. 14:06): znane, w toku.
- Drzwi Xodeta; Invincible Up przy depo Edron; drabina odchyda (32370,32213,z8); dziura (32467,32233,z7) oznaczona offline,
  działa od następnego startu; KROK_ZLY wdrożone.

## 5. Czego nie dało się ustalić z logów

- Przyczyna „5 klików bez efektu” na Trollach (wydra 23.10): duch w kliencie, stwór z innego piętra, nieatakowalny? Brak pola `z`
  stwora i zrzutu ekranu w logu.
- Źródło STOP-ów: człowiek (`STOP_RECZNY`) czy bot? W `mozg-stdout` nie ma rozróżnienia (`STOP_RECZNY` występuje tylko w `logowanie.log`
  i `obchod-podglad`). Wydra 23.10 11:38:28 oraz równoczesne STOP-y gebelisha i odchyda 10:01:44/45: nieustalone.
- Przyczyna „ukrytych blokad” przy `mapa True` bez stwora (21.10): nieustalona; zakładany błąd mapy, ale bez dowodu.
- Czas stania z epizodów to tylko górny szacunek; twardy dowód daje wyłącznie D3.
- Czy naprawy z 22–23.10 działają na instancjach, które nie były restartowane: nieznane. Brak normalizacji zacięć na godziny
  pracy bota; 23.10 tylko do ok. 14:20; logi `glowna` w katalogu głównym to dane z 20.10.
- Numery linii w `wypad.py`/`pietra.py` dla P3 nie zostały zbadane.
- Brak odczytu z gry (zakaz): nie sprawdzono, czy lina jest faktycznie w plecakach w chwili porażki.
