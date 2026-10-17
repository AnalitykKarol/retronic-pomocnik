# Stan bota Retronic (projekt prywatny: nic do Notion/Slacka)

Ostatnia aktualizacja: 2026-10-15 ~23:00. Kod: `ruch-r1-1014` = `main` = `007ab9d` (GitHub AnalitykKarol/retronic-pomocnik).
Specyfikacje i decyzje: `dane_tibia/SPEC_*.md`. Ten plik streszcza i linkuje.
**Dokument nadrzędny (16.10, szkic do akceptu): `dane_tibia/SYSTEM_RETRONIC.md`** (warstwy, rejestr specyfikacji, sprzeczności, fazy F0-F6, decyzje).  Szczegóły w `SPEC_*.md`.
**F0/F1 (16.10, wykonane, wszystko za pokrętłami 0):** testy 77/79 zielone (2 pomijane: brak zrzutów `testy/dane/zwloki.png`, `atrapa_zwloki.png`, `z6.png`). Nowe pokrętła `DRZWI_PONOW`, `D3_REAKCJA` (0/1 cień), `D3_ALARM_S` w `cavebot.py`/`d3_zawieszka.py`/`pokretla.py`/`na_zywo.przyklad.json`; `testy/test_drzwi_ponow.py` odtwarza zawieszkę drzwi (32505,32270,z8) i jest czerwony na kodzie sprzed zmiany (tylko na atrapach, w grze niepotwierdzone). Do włączenia po NASTĘPNYM restarcie bota (działający proces ma stary kod; nic nie restartowano): `D3_REAKCJA=1` w `na_zywo.json`. `test_zdrowie_czar` był niestabilny z powodu losowości czaru w teście (naprawione, 0/60 czerwonych).
**F2 + poprawka wpadniecie (16.10, zacommitowane, za pokrętłami 0):** `narzedzia/symulator_zawieszek.py` (offline, wyniki `dane_tibia/SYMULATOR_wyniki_1016.md`), test zgodności z `pietra.py` (208/1535 pól rozbieżnych, sklasyfikowane). Audyt `dziury_nauczone.json`: `[32498,32271,8]` FAŁSZYWA (zwykła podłoga po zejściu schodami; wpadniecie.py uczy bez sprawdzenia flagi 2 i schodów). Poprawka za `WPADNIECIE_WALIDACJA` (0 domyślnie, `testy/test_wpadniecie_walidacja.py`). Do zrobienia po zgodzie Karola przy restarcie: usunąć ten wpis z pliku, `D3_REAKCJA=1`, potem `WPADNIECIE_WALIDACJA=1`.
**Paczka 16.10 (commit `4c60421`, wypchnięta na origin/ruch-r1-1014, potem main):** P5 `SMIERC_STOP`, P6 `PK_SZYBKIE`, P8 `PK_UH_SZYBKIE`/`PK_UH_CTRL`, P10 `OBSERWATOR_PK_KONTEKST`, F3 cień w `D3_REAKCJA>=1`, P7 tylko zbieranie próbek czaszek. Wszystkie pokrętła domyślnie 0, 88 plików testowych (czerwone tylko 2 pomijane `test_loot_*`), przegląd NITS bez blokerów. Szczegóły, rejestr P1-P14, wyniki przeglądu i protokół testu na żywo: `dane_tibia/PACZKA_ZMIAN_1016.md`. Nadzorca okna: `podglad_stroz.sh`. Po zgonie bot ma tylko STOP + popup (decyzja Karola). Bot zatrzymany od 17:00 (`STOP`), postać wylogowana/gra ręczna.

## Gdzie jesteśmy

- **17.10 unikanie: tor gracza (branch `feat/unikanie-tor-gracza`, niewdrożone, bez merge):** bot nie idzie za graczem (kierunek z historii pozycji, "duch" 25 s po zniknięciu z widoku) i `PRZERWA` kończy się, gdy gracz podejdzie. Pokrętła `UNIKANIE_TOR`, `UNIKANIE_PRZERWA` (domyślnie 0). Spec i wdrożenie: `dane_tibia/SPEC_unikanie_tor_gracza_1017.md`; testy `testy/test_unikanie_tor.py` 26/26, zestaw jak baza. Pauza na rozmowę z graczem (F3) czeka na decyzję Karola.

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


## 2026-10-17 — rozpoznanie nakładu UI i pełnego AI OFF (bez implementacji)

Życzenie Karola: proste UI do ustawiania bota przez człowieka oraz przycisk
odłączający wszystkie funkcje AI. To ocena zakresu, nie zatwierdzony brief/spec.
Odczyt kodu HEAD 722a8c1: panel.py to TUI start/stop/status; pokretla.py ma
254 klucze liczbowe i 3 tekstowe, walidację i hot-reload. tryb.py/mapy.json/tryby.json
obsługują presety map i zachowań. uruchom.sh wymusza hybryda/haiku.
mozg.py --tryb skrypt wyłącza główny model i analityków, ale CLI nadal tworzy
CzytnikCzaszki(Claude(...)) niezależnie od trybu (okolice linii 3897), więc nie jest
pełnym AI OFF. Główne kanały: decyzje/czat, analitycy, odczyt czaszek.
Ważna weryfikacja przyszłej implementacji: AI OFF = zero uruchomień modelu,
zero późnego zastosowania wyników i brak nadpisania ustawień użytkownika.
Szacunek inżynierski z rozpoznania (nie zobowiązanie): użytkowe minimum 16–28 h;
pełne obecne ustawienia w sekcjach UI łącznie 28–48 h; jeśli przełączenie AI ma
być w locie bez restartu bota, dodatkowo 6–12 h na synchronizację, kolejki i anulowanie.
Nie wybrano technologii UI. Nie wyceniono graficznego edytora tras/map.
Otwarte: czy przełącznik AI działa po restarcie bota, czy ma działać w locie;
czy pełna konfiguracja obejmuje edycję tras na mapie, czy istniejące trasy i parametry.
Nie uruchamiano bota/modeli ani nie zmieniano konfiguracji w ramach rozpoznania.


## 2026-10-17 — spec zakresu UI / AI OFF

Na żądanie Karola powstał `dane_tibia/SPEC_ui_reczne_ai_1017.md` (draft, bez implementacji).
Zakres: panel sterowania, ręczna konfiguracja i pełna polityka AI OFF; otwarte Q1 forma UI,
Q2 przełączanie w locie vs restart samego bota, Q3 pełny rejestr parametrów vs minimum.
Rekomendacje w specu są propozycjami, nie decyzjami użytkownika.

2026-10-17 — Karol zatwierdził Q1/Q2/Q3 specu UI: okno desktopowe, przełączanie AI
w locie, pełne parametry w zaawansowanych. Dopisał oczekiwanie nagrywania spotów,
dojść do miasta i run: rozszerzono zakres w `dane_tibia/SPEC_ui_reczne_ai_1017.md`.
Q4: produkcja obsługiwanych run czy również własne typy/receptury; technologia UI
jeszcze niewybrana. Spec nadal draft, brak implementacji.

2026-10-17 — Q4 UI rozstrzygnięte: Karol chce zmieniać koszt/próg many i hotkey
(np. F8) przez UI bez kodowania. Spec uaktualniony; nie wymaga to katalogu własnych
nazwanych receptur. Q1–Q4 zamknięte, technologia/kontrakty jeszcze do zatwierdzenia.

## 2026-10-17 09:33 — Edron: dojście z depo na trolle (ręczna pomoc na 3 przejściach)

Bot (`MAPA=trolle_edron`, WYMUS_DOJSCIE=1) dotarł do (33117,31775,z8) i zaczął pętlę. Dojście `edron_depo_trolle` samo
NIE przechodzi trzech miejsc (pierwsze jego uruchomienie na żywo), Karol/agent pomagał ręcznie:
- z8->z9: **kratka** na (33169,31823,z8), nie (33168,31823); stać na (33168,31823) i Ctrl+klik w prawo (`ekran.otworz(1,0)`).
  Wpis `pietra_start.json` "33168,31823,8" jest błędny (domysł).
- z11->z10 (33133,31805), z10->z9 (33130,31809), z9->z8 (33131,31806), z8->z7 (33128,31810): **lina** na polu obok;
  trzeba stać na SĄSIEDNIM polu i `OperacjeZywe.uzyj_line(pole, poz)`; lina na własnym polu = "You cannot use this object".
  `TRYBY_GORA_DRABINA` (pietra.py) nie zawiera "lina" -> 3 próby R/krok bez skutku.
- Poprawka do zrobienia (po zgodzie): "lina" w trybach w górę z pola sąsiedniego + kratka jako tryb "use" sąsiedniego pola; test.
Uwaga: mana 22/215, brak jedzenia (patrz wyżej).

## 2026-10-17 09:40 — test strzału runą kliknięciami (tryb `agresywny`)
3 strzały HMM trafiły (HP celu 100->44->0, 60->16), 3 kliki "bez efektu". Okno Battle niepotrzebne (cel z pamięci, klik w pole moba).
Ocena Karola: bot klika PRAWYM na runie i wybiera "Use with" z menu - gracz tak nie robi, wolno; do przepięcia na Ctrl+klik
(w kliencie działa, np. lina) - niezrobione, czeka na zgodę. Runy wyłączone (RUNA_AKTYWNA=0), bot wznowiony 09:41.

## 2026-10-17 09:48 — strzał runą Ctrl+lewy (nowe pokrętło `RUNA_KLIK_CTRL`, domyślnie 0)
Karol: bot klikał prawym na runie i wybierał z menu (trafiał w "Look") - nieludzkie. Zmiana: `runa_klik.strzel(..., ctrl_cel=True)`:
Ctrl+lewy na runie, losowa pauza 60-180 ms, lewy na polu celu; bez menu i OCR. Pliki: runa_klik.py, cavebot.py (`_runa_klik`),
pokretla.py, testy/test_runa_klik.py (sekcja 17, 52/52). Test na żywo (1 próba, trolle Edron): strzał 1 "ubyło runy" (OK),
strzał 2 "bez efektu". Pokrętła przywrócone do RUNA_AKTYWNA=0, RUNA_KLIK_CTRL=0 (bot działa bez run). Niezacommitowane.

2026-10-17 — Panel UI/AI powstał w oddzielnym worktree `../pomocnik-ui` na feat/ui-reczne-ai; głównego kodu nie podmieniono. Aktywny spec i wyniki39/39+review/QA są wyłącznie tam (README_UI.md, STAN.md). Brak commita/merge/pusha, próby na żywej grze otwarte.

## 2026-10-17 15:45 — nie przeszkadzamy innym graczom (CUDZY_MOB + zmiana respa), nadzorca podglądu
Powód: 15:30-15:31 bot zabił 2 trolle poranione przez gracza Thanos (HP 78% i 20% przy wyborze celu); gracz napisał "?".
Zmiany (cavebot.py, pokretla.py, testy; niezacommitowane, brak niezależnego przeglądu):
- `CUDZY_MOB`=1 (`CUDZY_MOB_S`=60): po zobaczeniu obcego gracza nie bierzemy poranionego moba, którego sami nie zaczęliśmy
  (`moje_cele`); wyjątek: mob, który nas gryzie w odl <= 2. Test `testy/test_cudzy_mob.py` 10/10.
- `PATROL_GRACZ_ZMIEN`=1 (R=12, BLOK_S=240, PAUZA_S=15): obcy gracz blisko nas albo celu patrolu = od razu (bez debounce
  unikania) blokada miejsc w PATROL_GRACZ_PAM_R od niego i wybór innego respa. `testy/test_patrol_gracz_zmiana.py` 13/13.
- `CZAT_SPOT_AKTYWNY`=0 (bot nie pisze do graczy). Tryb: MAPA=trolle_edron_patrol (patrol po respach), nie pętla trasy.
- Nadzorca `podglad_stroz.sh` uruchomiony w tle (podnosi wayvnc i okno po awarii; zatrzymanie: pkill -f podglad_stroz.sh).
- Regresja: test_cavebot 481/481, test_patrol* (80, 47, 17, 13, 11), test_unikanie 39/39, test_runa_klik 57/57.
Otwarte: test na żywo przy obcym graczu; runy nadal wyłączone (RUNA_AKTYWNA=0, interwał 3,5-4,5 s, Ctrl+klik gotowe).

## 2026-10-17 16:05 — niezależny przegląd (checker, Sonnet, tylko odczyt): NITS, poprawki naniesione
Znaleziska i poprawki (cavebot.py, testy): (1) CUDZY_MOB przepuszcza moba tuż obok (odl <= 1) bez warunku gryzienia (jak unikanie.pomin_moba);
(2) PATROL_GRACZ_ZMIEN: brak alternatywnego respa NIE kończy już wizyty (sprawdzenie _patrol_kandydaci przed zakończeniem), pauza także
przy braku alternatywy, po nieudanym wyborze zwykły _patrol_wybierz zamiast kroku trasą; (3) log zmiany respa z id i współrzędnymi
(miejsca nie mają "nazwa"); (4) blokady miejsc dopiero gdy cel faktycznie leży przy graczu; (5) luka=False po zmianie respa;
(7) przycinanie moje_cele przy dopisywaniu; (8) patrol_zmiana_ost atrybutem; (9) komentarz RUNA_INTERWAL_S. Testy: patrol_gracz_zmiana 17/17,
cudzy_mob 12/12, runa_klik 59/59 (18f _runa używa _runa_odstep, 18g pauza Ctrl->lewy), regresja cavebot 481/481, patrol 80/17/13/11/47, unikanie 39/39.
Nie zrobione: test integracyjny tick() ("Nowy cel" -> moje_cele -> filtr). Nieoceniane bez gry: czy Ctrl+lewy na runie daje celownik w tym kliencie (jedna
udana próba 09:48), dobór R=12/60 s do ruchu graczy, czy droga A* po zmianie respa omija gracza. Uwaga: PVP_HMM_CO_S=2.0 (walka PvP, wyłączona) też zakłada exhaust 2 s - do korekty przed PVP_WALKA=1.

## 2026-10-17 wieczór — mapa spotów i trasy z mapy klienta (prototyp, bez zmian w kodzie bota)

- Powstały `dane_tibia/serwer74/` (potwory z lootem i **wszystkie spawny**, 69 czarów graczy, 312 NPC z cenami; źródło OCircles/TibiantisHelper) i `dane_tibia/serwer76_jamera/` (osobno, serwer 7.6 z Port Hope; **loot zmodyfikowany**, nie ufać; spawny i lista potworów do użytku). Opis: `dane_tibia/README.md`.
- `dane_tibia/mapy/`: obraz i trasa Port Hope -> swamp trolle (186 pól, z7) oraz pętla patrolowa po jaskini goblinów Edron z8 (12 przystanków, ok. 39 goblinów, 273 pola). Metoda i ograniczenia: `dane_tibia/mapy/README.md`.
- Spec `dane_tibia/SPEC_mapa_trasy_1017.md` (F0-F4), kierunek zatwierdzony przez Karola ("będzie klasa"), kod F2/F3 jeszcze nie ruszony; F4 (wysłanie postaci) dopiero po przebiegu na żywo.
- Otwarte: lina nie jest typem przejścia w formacie tras (czy `cavebot.py` umie ją użyć - nie sprawdzone); dojście do z10 goblinów nieznane (mapa ma 4 odcięte kawałki); mapa klienta zapisuje się przy zamknięciu klienta (stan z 10:00).
- Pozycja postaci do planowania: `nagraj_trase.pozycja(nazwa_postaci())` (tylko odczyt). Zrzut tylko okna gry: `hyprctl clients -j` + `grim -g`.
- Nie zacommitowane (inne zmiany w `cavebot.py`, `runa_klik.py`, `pokretla.py` są z innych sesji).

## 2026-10-17 21:10 — gobliny Edron z8: wynik godziny, plan powrotu podpięty (restart bota czeka)

- **Wynik 1 h** (19:49-20:49, telemetria, tryb `ostrozny`): +3800 exp = **3793 exp/h**, ok. 150 goblinów/h, HP min 85% / średnio 99%, bez alarmów i bez innych graczy w widoku. Trolle Edron: 2180-2600 exp/h. Spot zostaje (decyzja Karola 21:00: "warto zostać"). Karol testuje -2 (z9) osobno, drugą postacią (instancja `RETRONIC_ID=dwa`, `INSTANCJE.md`).
- **Bot nadal działa** na starym kodzie (start 19:49, `ostatni_start.env` = `MAPA=gobliny_edron TRYB=ostrozny`). UH robi sam (`UH_AKTYWNY=1` w `na_zywo.json`, 6 run w 1. h). Postać **nie ma jedzenia**.
- **Plan powrotu do depo** dopisany w `wyprawa.py` (`PLANY_PK`: `gobliny_edron`) + trasy `trasy/gobliny_edron_do_depo.json` (184 pkt, z8 kończy się o pole przed liną, lina z8 (33107,31846) -> z7 (33107,31847), dalej nagrane `edron_do_depo` od dziury (33127,31810)) i `trasy/gobliny_edron_z_depo.json` (178 pkt, powrót z depo; nieużywany, bo `WYPRAWA_DEPO_POWROT=0`). Testy: wyprawa 126/126, droga_depo 50/50, dojście 25/25; z jaskini goblinów `wybierz_baze` daje `gobliny_edron`, z jaskini trolli `edron`.
- **Lina (poprawione 17.10 23:30):** pierwsze założenie (33107,31846,z8) zawiodło (bot 23:09 siedem prób, ALARM, STOP). Rejestrator trasy zapisał przejście na żywo: lina na (33107,31847,z8) ze stania (33107,31846,z8), lądowanie (33107,31848,z7), zejście przez otwór (33107,31847,z7) -> (33107,31847,z8). Trasy `gobliny_edron_do_depo/z_depo` poprawione na branchu `fix/lina-gobliny-edron` (niewdrożone, wymaga restartu), test `testy/test_trasa_lina_edron.py` 9/9, nagranie w `dane_tibia/nagrania/`. Naprawione 17.10 23:35 (branch `fix/lina-najpierw`, ważne od następnego restartu bota): lina od pierwszej próby, gdy pole liny w mapie jest żółte bez flagi 2 (`wypad.zbuduj_etapy` -> `lina_pierwsza`, test `testy/test_lina_najpierw.py`); 17.10 23:23 wyprawa przeszła linę dopiero w 7. próbie po ~60 s. Dawniej: ~60 s zbędnych prób "drabina" przed liną (`_proby_drabiny`), ostrzeżenie planu depo etap 19 (stoi (33167,31811,7) nie sąsiaduje z dziurą (33167,31813,7)) obsługuje dojście po 15 s.
- **Restart bota czeka na "teraz" Karola** (`./zatrzymaj.sh`, potem `MAPA=gobliny_edron TRYB=ostrozny RETRONIC_POSTAC=Mastafian ./uruchom.sh`; pętla stoi ok. 20 s). Dopiero po nim plan działa. Gdy skończą się blanki (`WYPRAWA_DEPO_BLANKI=1`, `WYPRAWA_AKTYWNA=1`, `WYPRAWA_TYLKO_DEPO=1`), bot idzie do depo i tam STOP.
- **Dane i metoda:** `dane_tibia/mapy/README.md`, `dane_tibia/SPEC_mapa_trasy_1017.md`. Lewa górna jaskinia z10 (-3): 5 spawnów, 18 goblinów, pętla 134 pola, wejście dziurą z9 (33063,31822), nieprzetestowana.
- **Git:** commity 17.10 wypchnięte do `7f25739` (main i ruch-r1-1014). Zmiany po nim (ten wpis, `wyprawa.py`, nowe trasy) zacommitowane lokalnie, niewypchnięte.
