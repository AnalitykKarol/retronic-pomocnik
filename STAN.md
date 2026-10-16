# Stan bota Retronic (projekt prywatny: nic do Notion/Slacka)

Ostatnia aktualizacja: 2026-10-15 ~23:00. Kod: `ruch-r1-1014` = `main` = `007ab9d` (GitHub AnalitykKarol/retronic-pomocnik).
Specyfikacje i decyzje: `dane_tibia/SPEC_*.md`. Ten plik streszcza i linkuje.
**Dokument nadrzędny (16.10, szkic do akceptu): `dane_tibia/SYSTEM_RETRONIC.md`** (warstwy, rejestr specyfikacji, sprzeczności, fazy F0-F6, decyzje).  Szczegóły w `SPEC_*.md`.
**F0/F1 (16.10, wykonane, wszystko za pokrętłami 0):** testy 77/79 zielone (2 pomijane: brak zrzutów `testy/dane/zwloki.png`, `atrapa_zwloki.png`, `z6.png`). Nowe pokrętła `DRZWI_PONOW`, `D3_REAKCJA` (0/1 cień), `D3_ALARM_S` w `cavebot.py`/`d3_zawieszka.py`/`pokretla.py`/`na_zywo.przyklad.json`; `testy/test_drzwi_ponow.py` odtwarza zawieszkę drzwi (32505,32270,z8) i jest czerwony na kodzie sprzed zmiany (tylko na atrapach, w grze niepotwierdzone). Do włączenia po NASTĘPNYM restarcie bota (działający proces ma stary kod; nic nie restartowano): `D3_REAKCJA=1` w `na_zywo.json`. `test_zdrowie_czar` był niestabilny z powodu losowości czaru w teście (naprawione, 0/60 czerwonych).
**F2 + poprawka wpadniecie (16.10, zacommitowane, za pokrętłami 0):** `narzedzia/symulator_zawieszek.py` (offline, wyniki `dane_tibia/SYMULATOR_wyniki_1016.md`), test zgodności z `pietra.py` (208/1535 pól rozbieżnych, sklasyfikowane). Audyt `dziury_nauczone.json`: `[32498,32271,8]` FAŁSZYWA (zwykła podłoga po zejściu schodami; wpadniecie.py uczy bez sprawdzenia flagi 2 i schodów). Poprawka za `WPADNIECIE_WALIDACJA` (0 domyślnie, `testy/test_wpadniecie_walidacja.py`). Do zrobienia po zgodzie Karola przy restarcie: usunąć ten wpis z pliku, `D3_REAKCJA=1`, potem `WPADNIECIE_WALIDACJA=1`.

## Gdzie jesteśmy

- Bot i gra **wyłączone** (Karol: "dziś już nie"). Cały nowy kod czeka na pierwszy start; drugi komputer: Karol robi `git pull` + restart sam.
- Exp/h 15.10 (Mastafian, trolle Thais): 08-15 2,1-2,8 tys.; 18-21 0-860 wyłącznie przez nawigację (szczegóły niżej). Walka i wybór celu działały.

## Przyczyny wieczornego spadku 15.10 [POTW, logi mozg-stdout-1015-*]

1. Dziura (32508,32273,z8) przy spawnie: klient gry idzie za uciekającym trollem (follow po kliknięciu ataku) przez dziurę
   (18:39, 21:33). Pod spodem kieszeń z9 (32506..32509, 32267..32273), wyjście drabiną (32506,32269/32270).
2. Wschodnia część jaskini (m4/m6/m7, pokój z8 (32496..32499, 32266..32269), kieszeń) łączy się z resztą tylko schodami/drabinami;
   wyprawa do depo i wpadnięcie znały tylko nagraną trasę -> utknięcia/ALARM (19:05, 20:29-20:46, 20:48, 21:37).
3. Widmo postaci po relogu 18:39 (drugi wpis i blok statystyk w pamięci) - bot czytał zamrożoną pozycję/HP 1 h 45 min.
- Hipoteza [HIP]: patrol po m1-m8 częściej wchodzi do części wschodniej niż dawna trasa.

## Wgrane 15.10 (po recenzji, testy zielone; test_cavebot 476/481 = 5 starych czerwonych U1a/b/d/e, 42g)

| Co | Spec / pliki | Pokrętła |
|---|---|---|
| Widmo: wybór żywej kopii (ruch, exp bloku) | bot.py, rdzen.py | - |
| Blokada `zmien_trase` modelu przy zamrożonej pozycji / trasie > 60 pól | mozg.py | MODEL_TRASA_ZAMROZENIE_S, MODEL_TRASA_MAX_ODL |
| Wyprawa: oscylacja = utknięcie; nieosiągalny etap -> najbliższy osiągalny punkt | wypad.py | - |
| Jedzenie nie jest powodem wyprawy (tylko blanki) | wyprawa.py | WYPRAWA_JEDZENIE (na_zywo: 0) |
| Kieszeń: wyjście drabiną (flaga 2 mapy), hak "brak osiągalnego miejsca"; cel przy dziurze -> własne kroki albo odpuść | wpadniecie.py, cavebot.py | DZIURA_PRZY_CELU |
| Wyprawa z odciętej części dochodzi do trasy grafem patrolu | wypad.py | WYPRAWA_DOJSCIE_PATROLEM |
| Obrona PK: atak gracza z danych -> ucieczka do depo, leczenie, `wrogowie.json`, karencja 30 min (także po restarcie), czaszka (Haiku ze zrzutu) -> ucieczka, czary nie są czatem | SPEC_obrona_pk_1015, obrona_pk.py, czaszka.py | PK_*, CZASZKA_* |
| Walka PvP z napastnikiem (HMM do końca, UH 20%, exura 80%) - **wyłączona** do próby na żywo | SPEC_walka_pvp_1015 | PVP_WALKA=0, PVP_HMM_STOP_PP=0 |
| D3 krok A: zapis zawieszek (opcje + wynik), zbiór D3 | SPEC_model_D3_utkniecia_1015, d3_zawieszka.py | D3_LOG, D3_PROG_S=30 |
| Obserwator przejęć startuje z botem (STOP go nie zatrzymuje) | obserwator_z_botem.sh | RETRONIC_OBSERWATOR |
| Okno gry 1175x910 + dopasowanie sesji do okna podglądu w locie | SPEC_okno_gry_1015, dopasuj_okno.py | RETRONIC_BEZ_OKNA_ROZ, RETRONIC_DOPASUJ_OKNO |
| Dane do treningu z obu komputerów bez duplikatów | model_lokalny/zbierz_dane.py | - |

Detektor PK na 70 h telemetrii 3 botów: 15.10 20:35:08 (prawdziwy atak, Brezniev Leonid) i 13.10 19:16:15 (wątpliwe); poza tym 0.

## Lokalny model [stan]

- Zaplecze gotowe (zapis decyzji D1/D2/D4/D3/pvp, zbierz_dane, trenuj, numpy 0,007 ms). **Żaden model nie steruje botem.**
- D1 AUC 0,51 (bez sygnału), D2 0,83 (= sama odległość) - nie wgrane. D4: 19 decyzji w cieniu. PvP: 1 prawdziwy atak.
- Prawdziwe zawieszki w 70 h: 54 epizody, 162 min (rekord `utkniecie` się nie nadaje: 91% to walka).

## Następna sesja (kolejność)

1. Start gry: zrzut przy 1175x910 (pasy? panel?) - inaczej `RETRONIC_BEZ_OKNA_ROZ=800x910`; zmiana rozmiaru okna podglądu.
2. Bot stoi: klik w moba, zwłoki, strzał HMM w moba, UH na siebie (próba przed PVP_WALKA=1).
3. Zakładki czatu Trade (mozg.py TRADE_*) przestawić po zrzucie 1175, zanim bot wystawi ogłoszenie.
4. Odpalić bota (trolle_patrol); obserwować: wyjście z kieszeni, droga do depo po blanki, wpisy D3.
5. Propozycja do decyzji: Haiku oznacza 54 historyczne zawieszki -> pierwszy model D3 offline (raport, bez zmiany bota).
   16.10: plan testu gotowych modeli decyzyjnych (Mapika Decider, Strands Decider 2B, Laya; 3060 Ti 8 GB) -> `dane_tibia/SPEC_modele_decyzyjne_test_1016.md`
   (szkic, nic nie wgrane; własnego modelu od zera nie trenujemy, za mało danych).
   16.10 wynik: gotowe modele szybkie (33-129 ms na GPU), ale zero-shot NIE bije klasy większościowej (54 zawieszki, etykiety Haiku) -> kierunek i etapy: `dane_tibia/SPEC_model_steruje_gra_1016.md` (szkic do akceptu).
   16.10 ~13:30 decyzja Karola: Haiku NIE jest nauczycielem; prawda = dane + zasady + symulator. Dane: 46/99 zawieszek w małych zamkniętych obszarach (65% czasu), wyjście schody/dziura mediana 2 kroki, a wyjście trwało mediana 173 s -> `SPEC_model_steruje_gra_1016.md` sekcja 7.

## Otwarte

- test_wpadniecie "2 zasiany dziury_nauczone.json ma jedno pole" - test zakłada 1 dziurę, w danych są 3 prawdziwe (poprawić test).
- test_rdzen_widmo 3 FAIL (stary, nieaktualny wobec logiki w bot.py), test_ruch_okno, test_grim, test_ogien 1a - czerwone sprzed zmian.
- Brak jedzenia w plecaku Mastafiana (HP/mana bez regeneracji) - kupić przy wizycie w mieście.
