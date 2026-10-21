# AUDYT 21.10: 5 postaci, dane 20.10 13:00 – 21.10 ~14:10, jeden plan naprawy (SZKIC DO DECYZJI KAROLA)

Audyt wykonały workflow `audyt-retronic-1021` (9 agentów sonnet, tylko odczyt) i osobny agent dla bobra.
- **Struktura:** 4 obszary (loot, piętra, walka, pętla) plus katalog znanych problemów. Sceptyk każdego obszaru przeliczył liczby i próbował obalić ustalenia.
- **Dane źródłowe:** surowe wyniki są w scratchpadzie sesji (`audyt/journal_results.json`, skrypty `a*.py`, `b*.py`).
- **Etykiety przy punktach:** [P] = potwierdzone przez sceptyka, [C] = potwierdzone częściowo (korekta podana), [H] = hipoteza.
- **Bezpieczeństwo:** [BEZP] oznacza ryzyko śmierci postaci albo bana. Takie punkty wchodzą wyłącznie po pytaniu i odpowiedzi „tak”.
- **Bober:** osobna analiza w `DIAGNOZA_bober_smierc_sygnaly_bota_1021.md`.

## Etap 0: natychmiast, same pokrętła lub ekwipunek, bez kodu

| # | Co | Dowód | Zmiana | Cofnięcie |
|---|---|---|---|---|
| 0.1 | **Rytm skanu z 13:29 (moja zmiana) spowolnił boty** [P] | tick/s w walce −25…−37% u wszystkich 5; trafienia cache 95% → 67–77%; CPU strażników 73–96%; „strażnik puścił klawisz” 1,8/h → 5,9/h; zysku nie zmierzono. Limit 0,15 s jest krótszy niż sam skan (0,25–0,4 s), więc skan idzie bez przerwy (rdzen.py:555) | `SKAN_WIEK_WALKA`=0,5 i `SKAN_WIEK_SPOKOJ`=0,5 u wszystkich (= zachowanie sprzed 21.10), na żywo bez restartu | kopie `na_zywo.json.bak-20261021-rytm` |
| 0.2 | **Wydra od 12:07 nie zbiera nic** [P] | 117 ze 169 prób lootu kończy się „pełny plecak, slot_ukryty” (zajęte 13/20, widoczne 12); złoto 152–224 gp/h → 0 gp/h; bot nic z tym nie robi | rozciągnąć okno plecaka albo opróżnić plecak (Karol lub depo); kod w 1.3 | — |
| 0.3 | **Invincible bez `LOOT_BEZ_DRABIN`** [P] | 15 z 24 wpadnięć (62%) w ≤1 s po kliku lootu; 13:16 wejście na z7, ALARM i STOP, 4 min stania. U dawajkesha od włączenia (10:45): 0 wpadnięć w 3 h | `LOOT_BEZ_DRABIN`=1 i `WPADNIECIE_PLAN_PULE`=1 dla invincible, kutangena i wydry, potem restart | kopie `.bak` |
| 0.4 | **Kutangen: dane przejść do depo na Rooku błędne** (korekta Karola 21.10: tam są SCHODY, lina niepotrzebna) | `mozg-stdout-1021-*.log` kutangena: na (32029,32195,z9) bot próbuje sąsiedniego pola (32029,32194) jako drabina → lina → lina → drabina; działa dopiero próba 5/7 „wlasne” na polu, na którym stoi (07:40, 07:42, 11:03, za każdym razem ~40–80 s). Na z8 przejście opisane jako LINA (32027,32198,8)→(32027,32197,7): 60 s bez próby, ALARM 11:06:10 | poprawić dane trasy depo Rooka: typ „schody/krok” i właściwe pole (do potwierdzenia z mapy i `pietra_statystyki_przejsc`), test jak `test_kratki_drabiny_thais` | kopia danych `.bak` |
| 0.5 | Restart reszty botów po 0.3 | nowa `pietra.py` (kratka: najpierw Use) i `DOJSCIE_POMIN_ODL` działają tylko po restarcie; dziś mają je kolanoth i dawajkesh | po jednym bocie, poza walką | — |

### Wykonanie etapu 0 (Karol „tak”, 21.10 ~14:45)

- 0.1: `SKAN_WIEK_*`=0,5/0,5 u 5 instancji, na żywo o 14:45:23 (kopie `na_zywo.json.bak-20261021-rytm-cofniecie`). Pomiar tick/s i CPU strażników do zrobienia po 30–60 min.
- 0.3: `LOOT_BEZ_DRABIN`=1 i `WPADNIECIE_PLAN_PULE`=1 dla invincible, kutangena i wydry o 14:45:38–44, log „Loot: 76 pól drabin” (kopie `.bak-20261021-drabiny`). W zbiorze są schody (32494,32289,9) i (32498,32270,9). Pola (32503,32267,8) jeszcze nie ma: bot nauczy się go przy pierwszym wyjściu w górę, na stałe zamknie to punkt 1.4.
- 0.5: restart invincibla (14:47:03), kutangena (14:47:58) i wydry (14:48:29) z ustawieniami z `ostatni_start`, każdy poza walką. Wszystkie wystartowały od razu na trasie.
- 0.4: poprawka w kodzie, nie w danych. `wypad.zbuduj_etapy`: przejście w górę, którego lądowanie wypada obok pola stania i ma flagę 2, jest teraz schodami (krok). Przy nagraniu bez zmiany (x, y) druga próba to Use na własnym polu.
  - Zmiana dotyczy 3 etapów „schody” (Rook, 2 pola) i 17 etapów „własne”. Kopia: `wypad.py.bak-20261021-schody`.
  - Test `testy/test_wypad_schody_rook.py`: 9/9, na starym kodzie FAIL.
  - Testy wypraw bez zmian: lina_najpierw 5/5, wypad_drzwi 30/30, wypad_bieg 6/6, oscylacja 9/9, wyprawa_dojscie 25/25, droga_depo 50/50, dziura_zajeta 21/21, wyprawa 216/216.
  - Przegląd checkera w toku. Na żywo dopiero po restarcie kutangena przed jego wyprawą.
- 0.2 (plecak wydry): po stronie Karola, w grze.

### Wykonanie 1.1, 1.2 i zasady Karola o przejściach (21.10 15:00–15:47)

- **1.1 `WPADNIECIE_BEZ_STOP`** (`SPEC_wpadniecie_bez_stop_1021.md`, test 35/35, na starym kodzie 16/35): checker APPROVE, uwaga wprowadzona (`_odsun` omija nauczone drabiny). Włączone tylko u kutangena (15:36).
- **1.2 `ROZLACZENIE_STOP`** (`SPEC_rozlaczenie_1021.md`, test 52/52, na starym kodzie 8/28; 139 plików testów bez zmian): checker APPROVE.
  - Włączone u wszystkich: kutangen 15:36, dawajkesh 15:45, invincible 15:46 i wydra 15:47 (restart, każdy na swojej bieżącej mapie).
  - U kolanotha (`STOP_RECZNY`, gra Karol) tylko wpis w `na_zywo.json`, bez restartu.
  - Prawdziwy test: reset serwera 22.10 o 10:00.
- **`PRZEJSCIE_TRZY_SPOSOBY`** (Karol 15:10: „wejść, kliknąć, lina; pamiętać, który zadziałał”; `SPEC_przejscia_trzy_sposoby_1021.md`, test 14/14): checker NITS, 5 uwag wprowadzonych. Włączone u kutangena.
  - Na żywo jeszcze nie było udanego przejścia, plik `przejscia_nauczone.json` jeszcze nie istnieje.
- **Błąd:** 15:36 kutangen zrestartowany na mapie z `ostatni_start` (Rook), choć od 15:24 chodził po raty w Thais. WROC wystartował z Thais, nieudane wyjście (32360,32242,z8) zakończyło się ALARMEM 15:38. Od 15:39 bot znowu chodzi po raty. Reguła dopisana w `CLAUDE.md`.
- **Nowy problem:** trasa `thais_kanaly_do_miasta` zaczyna od wyjścia (32360,32242,z8)→z7, którego nikt nigdy nie przeszedł (zgadnięte). Do poprawy jest wyjście przez znaną drabinę pod kratką (F1). Do tego czasu bez wypraw do depo z kanałów Thais.

## Etap 1: kod, największy zysk i małe ryzyko (każdy punkt: test regresji z logów, checker, wdrożenie u 1 postaci)

1. **Zamiast STOP po wpadnięciu: naprawa i ponawianie** [P]
   - Skala: 6 ALARM/STOP w 2 dni, łącznie 47 min przestoju. W 4 z 6 przypadków ALARM przyszedł po mniej niż 10 s, choć budżet to 150 s.
   - Mechanizm (wpadniecie.py:681-790): kandydaci trafiają na stałe do listy `zle`, a po 3× „brak planu” następuje STOP.
   - Naprawa:
     - wyczyścić `zle` i odczekać 10–20 s, potem ponowić;
     - STOP dopiero po 150 s i 3 cyklach;
     - nie planować wyjścia przez pole, na którym bot właśnie stoi: plan zaczynał od niego w 5 z 7 upadków na Rooku (P5).
   - Gotowy silnik napraw (`NAPRAWA_ZAMIAST_STOP`, K01) czeka na gałęzi na decyzję o scaleniu.
2. **Wylogowanie i ekran wyboru postaci → bot przestaje naciskać klawisze i wysyła powiadomienie** [P]
   - O 10:00:01 wszystkie 5 botów stało 9–17 min i wysyłało klawisze do wylogowanego klienta; 3 boty same się zakończyły.
   - Kutangen 20.10: 1 h 40 min. `SMIERC_STOP` tu nie pomoże, bo pamięć zostaje na ostatnim HP.
   - Naprawa: brak postaci w rdzeniu przez >30 s albo zrzut „Character List”/„Enter Game” → pauza i powiadomienie; opcjonalnie auto-logowanie.
3. **Pełny lub „ukryty” plecak** [P]
   - Wolne sloty pod suwakiem nie są liczone (loot.py:636-652). `rozciagnij_plecak` jest wywoływany tylko przy otwieraniu plecaka (loot.py:1855).
   - Naprawa:
     - przy `slot_ukryty` rozciągnąć okno;
     - po 3× `pelny_plecak` uruchomić depo albo powiadomienie, zamiast zbierać w nieskończoność.
4. **Loot nie klika pól przejść, domyślnie w kodzie** [P]
   - `LOOT_BEZ_DRABIN` domyślnie 1, a zbiór drabin uzupełniany z mapy: każde pole z flagą przejścia, nie tylko nauczone.
   - `trasy/drabiny_nauczone.json` jeszcze nie istnieje.
5. **Schody nie blokują się po jednej porażce** [P/C]
   - Pojedyncza porażka (2 z 47 podejść na (32498,32270)) blokuje krawędź na 300 s i 2 punkty patrolu na 150 s (cavebot.py:161, 9561).
   - Naprawa: blokada dopiero po 2 porażkach z rzędu albo na 30–60 s, wcześniej jedno ponowienie po kilku sekundach.
   - Przyczyna 32% nieudanych pierwszych kroków Up: nieustalona, patrz 2.1.
6. **Wyjście z jaskini trolli na z7: postęp dojścia liczony długością drogi A*, nie odległością w linii prostej** [P]
   - Teraz pomiar w linii prostej (Chebyshev) i limit 25 s odrzucają dobre wejścia przy objeździe (pietra.py:524-536).
   - Zegar postępu powinien stać w czasie walki.
7. **Zwłoki odłożone („najpierw walka”) giną 2–4× częściej** [C]
   - Odłożone: około 5–9% bez lootu; po spokojnej walce: 1,5–1,9%. Łącznie bot traci 2–6% zwłok, trolle częściej.
   - Naprawa:
     - po `brak_okna` spróbować sąsiednich pól grupy;
     - nie kasować wpisu, gdy drugie zabicie padnie na tym samym polu;
     - zachować kolejkę zwłok po wpadnięciu i zmianie piętra.
   - Bramka „loot szybki”: bez żywego moba w promieniu 4. Dziś przerywany jest w 50–90% przypadków (LOOT-5) [P].

## Etap 2: pomiary, bez nich nie da się ocenić reszty (dodatkowa telemetria, zachowanie bez zmian)

1. Do `pietra_start` i `pietra_blad` dopisać:
   - pozycję,
   - czas od ostatniego kliku,
   - stwory na polu lądowania.
   Cel: wyjaśnić, czemu schody zawodzą przy pierwszej próbie.
2. **Epizod celu: zapisywać powód każdego `cel = None`** [P]
   - Powody: blokujący, rozprawa, ogień, dziura, drugi cel, poza widokiem.
   - Dziś „zniknął z widoku żywy” to najczęściej zwykłe przełączenie celu, a 5–16% epizodów nie ma id (telemetria.py:449).
   - Bez tego wskaźniki „porzuconych rannych” wprowadzają w błąd.
3. Co 60 s: CPU i pamięć mózgu, strażnika i klienta; czas pojedynczego zapytania do strażnika. Cel: spadek tempa pętli w długich sesjach (20.10 wieczór −50%) [C], przyczyna nieustalona.
4. T1–T5 ze specyfikacji ruchu (K15) oraz zapis każdego naciśnięcia klawisza (niewidzialna blokada kroku, K10).
5. Zapis czatu od obcych graczy, także w trybie skrypt (bober: wiadomo tylko o jednym „bot?”).

## Etap 3: [BEZP] decyzje Karola (bezpieczeństwo postaci i wygląd dla innych graczy)

1. **Invincible walczy z 3–4 trollami bez leczenia** [P]
   - HP poniżej 60% przez 20% czasu z mobami, minimum 36%.
   - `ZDROWIE_CZAR_AKTYWNY`=0 w trybie runy. „UH” w tym trybie oznacza robienie run, nie leczenie.
   - Do wyboru:
     - (a) leczenie w walce,
     - (b) wycofanie przy 3+ trollach obok i HP poniżej 60%,
     - (c) inny spot.
2. **`SMIERC_STOP`** jest wyłączony u wszystkich (K02).
3. **Pytanie „bot?”:** po 2–3 min pauzy krótka odpowiedź albo wylogowanie, zamiast stania „do odwołania” (bober: 16,5 min w miejscu obok pytającego).
4. **Sesje:** przerwy, rozłożone godziny startu, po resecie serwera nie wracać wszystkimi naraz; jeden bot na jaskinię.
5. **Ogień w jaskini trolli** (K03): inny spot albo trasa omijająca ogień. Bez ignorowania ognia: ZAKAZ Karola.
6. **Mana na ML a exura** (dawajkesh 12:52): rezerwa many na leczenie przed czarem ML.

## Etap 4: niski priorytet albo zysk niepewny

- **Kolejność lootu** [C]: zwłoki wybierane są tylko po odległości (cavebot.py:7596), bez wieku i gatunku. Strata z samej kolejności jest niemierzalna, dopóki nie zostaną naprawione 1.3, 1.4 i 1.7.
  - Potem jedna zmiana: najstarsze w zasięgu 2 pól i Troll przed Rat, z pomiarem przed i po.
  - **Zgłoszenie „priorytetyzacja nie działa” najpewniej wynika z błędów z 1.3, 1.4 i 1.7, a nie z kolejności.**
- **Czas lootu** około 5 s na zwłoki: krótsze pauzy, jeden zrzut zamiast kilku, bez prób jedzenia przy „najedzony” (LOOT-4, część liczb w zgłoszeniu była błędnie przypisana).
- **Pościg na pamięć** (1 udany na 17 startów, sama próbka szczurów), DRUGI_CEL przy uciekającym, rozprawa z blokującym (W2, W3).
  - Korekta sceptyka: ranne moby i tak są dobijane w 68–78% przypadków, więc szkoda jest mniejsza, niż wyglądało.
- Dziury znane, a mimo to wpadanie w pościgu (kutangen 3× to samo pole) [H]; wspólny moduł przejść zamiast `pietra.py` i `wypad.py` (K05).
- Mijanie graczy: 20.10 zabierało 6–28% czasu, 21.10 po rozdzieleniu spotów mniej (kolanoth nadal 4,8% przez obcych).

## Obalone lub skorygowane (nie naprawiać na tej podstawie)

- „Minuta bez wpisu w logu invincible 13:36:12–13:37:08”: **obalone**. Log `mozg-20261021-1334.log` ma w tym oknie około 60 wpisów.
- „Strażnik puszcza klawisz na schodach”: zdarza się przy starcie pościgu, nie na schodach. Wzrost po 13:34 pewny tylko u kutangena i wydry.
- „Zmiana celu porzuca ranne”: kod wraca do rannego (`wroc`), a dobicie w 15 min jest równie częste (69% wobec 68%).
- „Invincible traci 31 min na cele odrzucane przez ogień”: tylko około 20% takich epizodów ma ogień lub dziurę w pobliżu, łącznie około 5 min.
- „Crash kolanotha na starcie”: zła nazwa w `profil.json` („Kolanoth” zamiast „Kolanosh”), a nie zimny rdzeń.

## Kolejność proponowana

Etap 0 (dziś) → 1.1 + 1.2 (koniec ze STOP-ami i ślepym chodzeniem) → 1.3 + 1.4 (loot) → 2.1–2.3 (pomiary) → 1.5–1.7 → Etap 3 po rozmowie → Etap 4 po pomiarach.
Każdy punkt kodu zgodnie z regułą repo: spec, test na starym kodzie (FAIL), checker, jedna postać na żywo, potem reszta.

## Czego nie ustalono

- Wpływ zmian z 21.10 po 13:30 na exp i loot: tylko 20–40 min danych.
- Dlaczego okno plecaka wydry ma 3 rzędy zamiast 5.
- Przyczyna rozłączenia o 10:00:01: reset serwera? Czy powtarza się codziennie?
- Czy spadek tick/s wieczorem 20.10 to wiek procesów, czy obciążenie 6 gier.
- Brak w dokumentach: skąd ogień w jaskini trolli i czy jest stały.

### Nowe z 21.10 17:00–17:10 (do planu naprawy)

- **Dojście poddaje się, gdy pole pod kratką zajmuje inny bot.**
  - 17:08:15–17:08:36 invincible: kratka Edron (33168,31823,z8)→z9 sekundę po zejściu Kolanosha. Use bez skutku, druga próba ze stania na kratce też.
  - Lista prób pietra skończyła się po 2 próbach, a dojście po 5 podejściach w 21 s skończyło się „Koniec”. Restart o 17:09 przeszedł za 1. razem.
  - Naprawa: przy porażce przejścia w dół odczekać 5–10 s i ponowić (lądowanie mogło być zajęte), zanim dojście się podda; dojście nie powinno kończyć bota, tylko ponawiać (zasada „naprawiaj, nie zatrzymuj”).
- **Bot czeka na samego siebie.** 17:09:28 „na polu (33168,31823) stoi gracz Invincible, czekam (max 20 s)”: pietra uznaje własną postać za gracza blokującego pole. Naprawa: wykluczyć własny nick przy sprawdzaniu zajętości pola przejścia.
- **Brak dojścia z depo Edronu (z8).** `uruchom.sh` przekazuje dojście tylko ze z7 albo przy `dojscie_z_dowolnego_pietra`. Depo Edronu leży na z8, więc mapy `trolle_edron_patrol`, `trolle_edron_z9w`, `gobliny_edron` i `gobliny_edron_z9` startowały bez dojścia. Kolanosh 17:05 przez 2 min błądził po z8. Poprawione: flaga dopisana w `mapy.json` (kopia `mapy.json.bak-20261021-dojscie-edron`).
- **Dwa własne boty na jednym spocie:** od 17:09 kolanoth i invincible chodzą po `trolle_edron_z9w`. Rozdzielenie spotów to zadanie nadzorcy (Q5 w `SPEC_nadzorca_rotacja_1021.md`).
- **Dojście wymagające liny bez sprawdzenia ekwipunku.**
  - `trolle_edron_z9w_dojscie` wchodzi liną z11→z7.
  - Kolanosh bez liny utknął na (33134,31806,z11), Karol go wylogował o ~17:12.
  - Postać jest offline w jaskini, ma `STOP_RECZNY`, do wyciągnięcia ręcznie.
  - Naprawa: przed startem dojścia/trasy z przejściem „lina” bot sprawdza linę w ekwipunku. Bez liny: nie startuje, wysyła powiadomienie i wybiera inny spot.
  - To samo musi robić nadzorca przy wyborze spotu.
  - **Zrobione 21.10 ~17:40 (Karol „tak”):** `liny.py` (znane pola lin z logów → `dane_tibia/ruch/liny_znane.json`, 8 pól, plus `przejscia_nauczone.json`), `mozg.sprawdz_line` przed dojściem/trasą, stała `mozg.LINA_SPRAWDZ`=1.
    - Brak odczytu pamięci albo błąd sprawdzenia: start jak dotąd.
    - Test `testy/test_lina_start.py` 16/16; test_mozg 246/246 bez zmian.
    - Odczyt na żywo: invincible i dawajkesh mają linę, kutangen i wydra nie (ich trasy liny nie wymagają).
    - Działa od następnego startu każdego bota. Kopia `mozg.py.bak-20261021-lina`.
