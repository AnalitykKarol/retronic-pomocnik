# SPEC: szybka obrona przed PK (bez modelu na ścieżce reakcji) — 16.10.2026

Status: **DRAFT — czeka na akcept Karola. Żadnego kodu.** (Karol 16.10: „na razie przygotuj spec”; w repo trwają duże zmiany kodu.)
Rozszerza i koryguje `SPEC_obrona_pk_1015.md` (tam: detekcja ataku z danych, ucieczka, leczenie, nick wrogów). Tu: czas reakcji.

## 1. Co się stało (dowody w logu `logi/mozg-20261016-1259.log` i `logi/telemetria-20261016.jsonl`)
Mastafian zginął 15:52:33 na z9 (32500,32279), trolle/orki, od pojawienia się Tojsona (biała czaszka) minęło 24 s.
Drugi taki zgon w 2 dni (15.10 20:35 Edron: ucieczka „po trasie” jak przed trollem, śmierć, wypadł plecak z UH).

| Czas | Zdarzenie |
|---|---|
| 15:52:08 | Tojson w widoku, 6 pól; bot: „omijam jego okolicę”, bez akcji |
| 15:52:09–11 | Tojson biegnie z 5 do 4 pól |
| 15:52:12 | model rozpoznaje czaszkę (`Czaszka: biala`, ~3–4 s od zobaczenia); decyzja „UCIEKAM” = tylko wpis w logu |
| 15:52:12–16 | **bot stoi 4 s**: `obcy_gracz` woła model SYNCHRONICZNIE (Decyzja 4,0 s); w telemetrii brak próbek i akcji |
| 15:52:16 | dopiero teraz `Wypad: start (pk_ucieczka)`, pierwszy `exura` (HP 73%); od razu `droga zablokowana przez Orc, walczę 8 s` |
| 15:52:17 | pierwsze obrażenia, HP 100→66% w ~1 s; potem ok. 14 HP/s (220 HP w 16 s); Tojson stoi 4 pola dalej (strzelec) |
| 15:52:16–18 | `exura` ×2 (25 many każde): mana 59→10 (tryb UH trzyma niską manę 28–58/245) |
| 15:52:23 | pierwsza próba UH na siebie (HP 45%); 3 próby, wszystkie `bez_efektu`: `[RUNA-KLIK] 'Use with' nie rozpoznane` (OCR menu zawiódł, klik w zgadnięty offset); ścieżka `runa_klik.py` nigdy wcześniej nie działała w tej sesji (komentarz „nie testowane na X11”) |
| 15:52:33 | HP 0; bot nie wykrywa śmierci, ~20 s dalej klika w orka; obserwator zauważa o 15:52:54 |

Wnioski: (a) 8 s martwego czasu od zobaczenia do startu ucieczki, z czego ok. 7,5 s to dwa wywołania modelu na ścieżce reakcji;
(b) ucieczka piechotą (ok. 100 pól do depo) przed strzelcem z 4 pól jest nierealna nawet bez opóźnienia — realnie ratuje leczenie;
(c) UH jest użyty za późno (HP 45%, 7 s po pierwszym trafieniu) i kliknięciami zbyt wolno (3–4 s na próbę);
(d) bot walczy z mobem blokującym zamiast kontynuować ucieczkę; (e) brak wykrycia śmierci.

## 2. Wymagania

### R1. Czaszka lokalnie (bez modelu)
- Odczyt czaszki obcego gracza z obrazu (wycinek przy nicku) lokalnym detektorem koloru/kształtu: < 200 ms, bez Haiku.
  Model tylko jako zapas, gdy detektor zwróci „nieznane”, i nigdy na ścieżce reakcji (R2).
- UNKNOWN: kształt/kolor ikon czaszek w tym kliencie — do zebrania z istniejących zrzutów (`logi/`, czaszki biała/czerwona/żółta) przed implementacją.

### R2. Reakcja na PK nie czeka na model
- Od wykrycia gracza z groźną czaszką w zasięgu (<= 8 pól) lub utraty HP od gracza: natychmiast (w tym samym obiegu) start `pk_ucieczka`, leczenie, nick do wrogów.
- Zdarzenie `obcy_gracz` w trakcie aktywnego PK-alarmu: bez wywołania modelu albo wywołanie w tle (wątek), wynik tylko informacyjny.
- Haiku nie może zwrócić `pauza_bota` ani `kontynuuj`, gdy HP < 50% albo trwa PK-alarm (akcje ignorowane z wpisem w logu).
- Test: żadne wywołanie modelu nie blokuje pętli > 0,3 s w stanie PK (pomiar w telemetrii).

### R3. UH przy 20–30% HP (decyzja Karola 16.10)
- `PK_UH_HP` (dziś 40): **30**, plus ponowne użycie co `PK_UH_ODSTEP_S` (dziś 2,5 s; cooldown run ok. 2 s) aż HP > 50% albo wróg znikł.
  Zakres 20–30% do strojenia; **ryzyko do akceptu:** przy skoku 34% w 1 s i ok. 14 HP/s zapas od 30% do zera to ok. 2 s, czyli 1 użycie.
  Opcja do wyboru: dodatkowy próg predykcyjny (spadek >= 15 pp w 2 s => UH już przy 50%), jak istniejące „przewiduję przekroczenie progu”.
- **Hotkey odpada** (Karol 16.10: runy nie da się przypisać do klawisza; trzeba kliknąć Use na runę i potem na siebie).
  Zostaje ręczna sekwencja kliknięć, więc cały wysiłek idzie w jej SZYBKOŚĆ i niezawodność:
  1. Bez OCR menu na ścieżce PK: dziś prawy klik + 0,25 s + zrzut + tesseract (do 8 s limitu) + klik + 0,15 s + klik w cel + 1,6 s weryfikacji = 3–4 s na próbę.
  0. Cel „na siebie” jest zawsze w tym samym punkcie: postać stoi na środku widoku gry (Karol 16.10), czyli klik w pole (0,0) = stały piksel
     środka obszaru gry (dziś `ekran.klik_pola(0, 0)`); jedyną zmienną w sekwencji jest pozycja slotu runy i sam krok „Use with”.
  0b. **Losowość kliknięć zostaje** (Karol 16.10: człowiek nie trafia w środek za każdym razem). Kliknięcie „na siebie” = środek pola postaci
     z losowym przesunięciem w obrębie jej pola (rozkład normalny, sigma ok. 1/6 pola, obcięty do pola, nigdy poza nie; dziś `Mysz.klik` ma
     `drganie=3` px, a ścieżka UH na siebie ma `drganie=1` — ujednolicić i nie wyłączać w trybie PK). Losowe też: czas między Ctrl+klikiem runy a klikiem
     w siebie (ok. 60–180 ms, nie stałe), tor kursora (`Mysz.ruch` już płynny), kolejność/odstęp ponowień (w granicach `PK_UH_ODSTEP_S` +- 20%).
     Granica: losowość nie może wydłużyć sekwencji ponad budżet 1 s (R3.6); w alarmie obowiązuje „tryb szybki” z wąskimi zakresami, poza walką pełne zakresy.
  2. Sprawdzić w kliencie szybszy wariant: **Ctrl+klik na runie = „Use with”** bez menu (kod przejść pięter już używa „R, Ctrl+klik”, `pietra.py`).
     Wtedy sekwencja to 2 kliknięcia: Ctrl+klik runy, klik w siebie (offset 0,0). UNKNOWN: czy Ctrl+klik działa dla run w tym kliencie.
  3. Wariant zapasowy, gdy Ctrl+klik nie działa: stały, ZMIERZONY offset „Use with” w menu (offset zapamiętywany po pierwszym udanym
     OCR już jest w `pamiec["offset"]`) zapisany do pliku po udanej próbie poza walką, bez OCR w trakcie PK.
  4. Weryfikacja skrócona do ~0,6 s (spadek ilości run albo wzrost HP własnego), a przy braku efektu natychmiast kolejna próba, bez przerwy 60 s
     po 3 porażkach, gdy HP < 30% (dziś `PK_UH: przerwa 60 s` po 3 nieudanych odbiera jedyne leczenie w najgorszym momencie).
  5. Rozgrzewka: runa i geometria okna plecaka gotowe zawczasu (geometria z cache `ttl_geometrii=20 s`; odświeżać co obieg, gdy w widoku gracz z czaszką),
     żeby pierwsze kliknięcie nie czekało na zrzut/OCR okna.
  6. Test na żywo poza walką (z Twoją zgodą na ruszenie postaci): jedno UH na siebie przy < 100% HP, pomiar czasu sekwencji (cel: <= 1 s).
- Zasada: gdy runa/menu niepotwierdzone, nie zgadywać offsetu po cichu (dziś: klik w (28,22) bez weryfikacji) — krótki powtórny odczyt, potem alarm.
- UNKNOWN: ile HP leczy UH na tym poziomie (do zmierzenia z logu/z gry); od tego zależy, czy 1 użycie wystarcza.

### R4. Ucieczka nie zamienia się w walkę z mobem
- W `pk_ucieczka` mob obok nie jest powodem do „Wypad: droga zablokowana … walczę 8 s”, o ile da się go obejść; walka tylko gdy droga całkowicie zamknięta,
  max 2 s, a leczenie (R3) idzie równolegle.
- Test na odtworzeniu 15:52:16–33 (ork 1,0 + Tojson −4,0).

### R5. Wykrycie śmierci
- HP == 0 (albo okno śmierci / pozycja w świątyni po respawnie) = natychmiastowe zakończenie walki, alarm do Karola, stan `MARTWY`,
  zero kliknięć w moby, zero wywołań modelu o „kontynuuj”. Po respawnie nie ufać HP == 0 jako odczytowi: osobno zbadać, dlaczego telemetria po respawnie
  dalej podaje HP 0 (screenshot miał 215/215) — **UNKNOWN**.

### R6. Rezerwa many na obronę (do decyzji Karola)
- W trybie UH `exura` kosztuje 25 many (mana 28–58 z 245 nie starcza na 3 rzuty). Opcje: zostawiać rezerwę ~60–100 many w trybie UH
  (mniej run/h), albo liczyć wyłącznie na UH z plecaka (R3). Nie wybrano.

## 3. Poza zakresem (dalej)
- Kontratak, ucieczka magią/teleportem, wylogowanie (w Tibii zablokowane w walce z graczem). Walka z PK: „dojdziemy do tego później” (SPEC 15.10).
- Odzyskiwanie zwłok i plecaka po zgonie.

## 4. Testy (atrapy, bez gry; `RETRONIC_TESTY=1`, wzorzec `testy/test_patrol_edron.py`)
1. Odtworzenie sekwencji 15:52:08–33 (stwory + HP z telemetrii): czas od pierwszej próbki z graczem (czaszka biała) do `pk_ucieczka` start < 0,5 s; zero wywołań modelu blokujących pętlę.
2. UH na siebie przy HP 30% (atrapa dwóch kliknięć): użycie w tym samym obiegu, kolejne po `PK_UH_ODSTEP_S`.
3. `obcy_gracz` w PK-alarmie nie woła modelu synchronicznie; akcje `pauza_bota`/`kontynuuj` przy HP < 50% odrzucone.
4. Ork blokujący pole przy `pk_ucieczka`: obejście albo walka <= 2 s, leczenie nieprzerwane.
5. HP 0 => stan `MARTWY`, brak ataków.

## 5. Wdrożenie
Za pokrętłami (`PK_SZYBKIE=1`, `PK_UH_HP`, `PK_UH_CTRL`); wejście na żywego bota dopiero przy restarcie za zgodą Karola
(druga maszyna: `git pull` + restart). Commit tylko na polecenie. Powiązane: `SPEC_obrona_pk_1015.md`, `SPEC_model_steruje_gra_1016.md` (sekcja 8: Haiku nie na ścieżce reakcji),
`ANALIZA_zaciecie_schody_1016.md` (inne dzisiejsze zacięcia).

## 6. Do decyzji Karola
1. Próg UH: 30% (zalecane, bo 20% = 1 użycie zapasu) czy 20–25%? Dodać próg predykcyjny przy gwałtownym spadku?
2. R6: rezerwa many w trybie UH — tak/nie.
3. UH na siebie: sprawdzić w kliencie, czy Ctrl+klik na runie otwiera „Use with” (2 kliknięcia); jeśli nie — wariant zapasowy bez OCR (punkt R3.3). Test na żywo wymaga Twojej zgody na ruszenie postaci.
4. Zakres pierwszego wdrożenia: R5 (śmierć) + R2 (model poza ścieżką) + R1 (czaszka lokalnie) jako pierwsza paczka, R3/R4 druga?
