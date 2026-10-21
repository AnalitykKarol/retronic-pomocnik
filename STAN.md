# Stan bota Retronic (projekt prywatny: nic do Notion/Slacka)

Ostatnia aktualizacja: 2026-10-15 ~23:00. Kod: `ruch-r1-1014` = `main` = `007ab9d` (GitHub AnalitykKarol/retronic-pomocnik).
Specyfikacje i decyzje: `dane_tibia/SPEC_*.md`. Ten plik streszcza i linkuje.
**Dokument nadrzędny (16.10, szkic do akceptu): `dane_tibia/SYSTEM_RETRONIC.md`** (warstwy, rejestr specyfikacji, sprzeczności, fazy F0-F6, decyzje).  Szczegóły w `SPEC_*.md`.
**F0/F1 (16.10, wykonane, wszystko za pokrętłami 0):** testy 77/79 zielone (2 pomijane: brak zrzutów `testy/dane/zwloki.png`, `atrapa_zwloki.png`, `z6.png`). Nowe pokrętła `DRZWI_PONOW`, `D3_REAKCJA` (0/1 cień), `D3_ALARM_S` w `cavebot.py`/`d3_zawieszka.py`/`pokretla.py`/`na_zywo.przyklad.json`; `testy/test_drzwi_ponow.py` odtwarza zawieszkę drzwi (32505,32270,z8) i jest czerwony na kodzie sprzed zmiany (tylko na atrapach, w grze niepotwierdzone). Do włączenia po NASTĘPNYM restarcie bota (działający proces ma stary kod; nic nie restartowano): `D3_REAKCJA=1` w `na_zywo.json`. `test_zdrowie_czar` był niestabilny z powodu losowości czaru w teście (naprawione, 0/60 czerwonych).
**F2 + poprawka wpadniecie (16.10, zacommitowane, za pokrętłami 0):** `narzedzia/symulator_zawieszek.py` (offline, wyniki `dane_tibia/SYMULATOR_wyniki_1016.md`), test zgodności z `pietra.py` (208/1535 pól rozbieżnych, sklasyfikowane). Audyt `dziury_nauczone.json`: `[32498,32271,8]` FAŁSZYWA (zwykła podłoga po zejściu schodami; wpadniecie.py uczy bez sprawdzenia flagi 2 i schodów). Poprawka za `WPADNIECIE_WALIDACJA` (0 domyślnie, `testy/test_wpadniecie_walidacja.py`). Do zrobienia po zgodzie Karola przy restarcie: usunąć ten wpis z pliku, `D3_REAKCJA=1`, potem `WPADNIECIE_WALIDACJA=1`.
**Paczka 16.10 (commit `4c60421`, wypchnięta na origin/ruch-r1-1014, potem main):** P5 `SMIERC_STOP`, P6 `PK_SZYBKIE`, P8 `PK_UH_SZYBKIE`/`PK_UH_CTRL`, P10 `OBSERWATOR_PK_KONTEKST`, F3 cień w `D3_REAKCJA>=1`, P7 tylko zbieranie próbek czaszek. Wszystkie pokrętła domyślnie 0, 88 plików testowych (czerwone tylko 2 pomijane `test_loot_*`), przegląd NITS bez blokerów. Szczegóły, rejestr P1-P14, wyniki przeglądu i protokół testu na żywo: `dane_tibia/PACZKA_ZMIAN_1016.md`. Nadzorca okna: `podglad_stroz.sh`. Po zgonie bot ma tylko STOP + popup (decyzja Karola). Bot zatrzymany od 17:00 (`STOP`), postać wylogowana/gra ręczna.

## Gdzie jesteśmy

- **21.10 17:40 PODSUMOWANIE DNIA: `dane_tibia/PODSUMOWANIE_1021.md`.** Wszystkie nowe pokrętła włączone u 5 postaci, 4 boty zrestartowane z nowym kodem (wydra: ręczna gra). Nadzorca zbudowany, na żywo jeszcze nie działa (start: timer w cieniu → jedna postać → zestaw).
- **21.10 ~17:30 nadzorca, który zarządza (Karol 16:20: rotacja postaci, miasto, przerwy, „zarządzać jak ja”) — klocki zbudowane offline, NA ŻYWO NIC.** Spec `dane_tibia/SPEC_nadzorca_rotacja_1021.md` (decyzje: 5 online + nowe konta, hunt 2–3 h, cała biała lista, „wszystko naraz”).
  - K1 `logowanie.py`/`zaloguj.sh`/`wyloguj.sh` (`SPEC_logowanie_wylogowanie_1021.md`, test 64/64, checker NITS).
  - K2 powroty (kanały Thais przez drabiny pod kratkami, Edron, Rook; `SPEC_powroty_k2_1021.md`, test 136/136, checker APPROVE).
  - K3 serwis Thais (depo + Gorn; jedzenie i blanki za drzwiami = K3b; `SPEC_serwis_thais_1021.md`, test 57/57; poprawka: serwis w złym mieście kończy się od razu).
  - F1–F2 `grafik.py`/`nadzor.py`/`NADZORCA.md` (`SPEC_nadzor_wykonawca_1021.md`, testy 8/8 i 37/37). Tryb na żywo tylko z `instancje/_wspolne/NADZOR_ZYWO`, którego nie ma. Ponowny przegląd poprawek B-1..B-5 w toku.
  - Plik `cisza` (wyciszał wszystkie powiadomienia od 20.10 09:45) zdjęty na polecenie Karola: `cisza.wylaczona-20261021`.
  - Testy na żywo, każdy po „tak” Karola: wyloguj/zaloguj na jednej postaci → WROC z kanałów Thais → pełny cykl nadzorcy na dawajkeshu (Edron).
- **21.10 ~14:20 AUDYT 5 postaci (workflow, 9 agentów, tylko odczyt) — jeden plan naprawy, SZKIC do decyzji Karola: `dane_tibia/ruch/AUDYT_1021.md`.** Najpilniejsze: rytm skanu 0,15 s spowolnił pętlę o 25–37% (do cofnięcia na 0,5/0,5), wydra od 12:07 nie lootuje (plecak `slot_ukryty`), invincible wpada po lootcie (brak `LOOT_BEZ_DRABIN`), kutangen: przejścia do depo na Rooku opisane jako lina/drabina na złym polu, a to schody (korekta Karola), STOP po wpadnięciu i ślepe chodzenie po wylogowaniu. Bober: `dane_tibia/ruch/DIAGNOZA_bober_smierc_sygnaly_bota_1021.md` (zgonu w logach brak; sygnały bota: „bot?” bez odpowiedzi + 16 min stania).
- **21.10 13:46 kolanoth (kanały Thais): po wyjściu przez kratkę nie wracał (plan znajdował kratkę, ale próbował tylko kroku → ALARM/STOP 13:04, 13:37) — naprawione w `pietra.py` (pewne zejście bez dziury na mapie = najpierw Use), test 11/11, checker APPROVE; restart 13:46, QA otwarta.** Kolanoth ma też `LOOT_BEZ_DRABIN`/`WPADNIECIE_PLAN_PULE`=1. Start na spocie bez dojścia: `mozg.DOJSCIE_POMIN_ODL`=10 (test 7/7). `dane_tibia/SPEC_kratki_drabiny_thais_1021.md` F4.
- **21.10 13:30 skan stworów: częściej w walce, rzadziej w spokoju — test na kolanocie (0,15/1,0 s), kontrola kutangen.** Rdzeń z polem `rytm` wdrożony 13:29 na wszystkie gry (bez pola = jak dotąd). Pierwszy pomiar: walka ~3,4 skanu/s, spokój ~1/s (kontrola ~2,2/s). Do oceny po 1–2 h. ML u dawajkesha wyłączony 12:59 (mana na exurę). `dane_tibia/SPEC_skan_walka_spokoj_1021.md`, `dane_tibia/ruch/ANALIZA_skaner_wplyw_1021.md`, `dane_tibia/ruch/DIAGNOZA_dawajkesh_walka_7_trolli_1021.md`.
- **21.10 ~11:00 invincible, jaskinia trolli (trolle_patrol, ostrozny+ml): źle chodzi i gubi loot — przyczyna częściowo znana, INVESTIGATING.**
  Względem 20.10 wieczór: „nie ruszył” 0,07 → 1,6–2,2 na zabitego, loot `brak_okna` 4% → 14–43%. Ustalone: od dziś w korytarzu stoi prawdziwy ogień
  (wczoraj 0 wykryć, dziś 53–72/h; głównie (32491,32289), (32480,32294); zrzut 10:55 = troll w płomieniach); bot ognia nie przechodzi i w 1-polowym korytarzu bije w ściany
  (38% / 13% zacięć przy ogniu). Wykluczone: czar ML, rozjazd pozycji, znane pola, zmiana kodu ognia, ogień przy zwłokach. Nierozstrzygnięte: reszta zacięć;
  `brak_okna` po resecie serwera 10:00 (trop: inny układ klienta invincible'a, mapa 806×592 od x=183, pole 54 px; potrzebny zapis prostokąta i zrzut przy `brak_okna`);
  ucieczka 10:48 z HP 36% stała w miejscu („nie ruszył” na pola przechodnie). Bot uruchomiony ponownie 10:58:31, ustawienia bez zmian
  (`OGIEN_IGNORUJ_S` włączone przez pomyłkę 10:59:06–10:59:56 i cofnięte; bot przez ogień nie przeszedł). Następny krok: inny spot albo trasa omijająca ognie — decyzja Karola.
  `dane_tibia/ruch/DIAGNOZA_invincible_trolle_chodzenie_loot_1021.md`.
- **21.10 10:45 dawajkesh, kanały Thais (raty, ostrozny+ml, bez wypraw): wychodził przez drabiny i nie wracał — naprawione, QA na żywo otwarta.**
  Przyczyny: Ctrl+klik lootu na zwłokach leżących na drabinie wspinał postać z8→z7; plan wpadnięcia nie liczył znanych zejść (niepewne przejścia z mapy zajmowały pulę);
  `thais_dojscie` przez świątynię prowadzi na z6. Wdrożone: dojście `thais_dojscie_kratka` + 3 kratki w `trasy/`, pokrętła `WPADNIECIE_PLAN_PULE`=1 i `LOOT_BEZ_DRABIN`=1
  w `instancje/dawajkesh/na_zywo.json` (w kodzie domyślnie 0), test `testy/test_kratki_drabiny_thais.py` 25/25, checker NITS. Bez commita.
  `dane_tibia/SPEC_kratki_drabiny_thais_1021.md`, `dane_tibia/ruch/DIAGNOZA_dawajkesh_drabina_kanaly_thais_1021.md`. Restart 10:00 = reset serwera (wszystkie postacie wylogowane), nie ten błąd.

- **20.10 21:01 Kutangen (lvl 7) ZGINĄŁ w jaskini bugów z10 na (32056,32199,z10)** (zrzut 22:43: ekran wyboru postaci). Przebieg z telemetrii: od 20:55 `exura` nie działa (3x bez efektu, leczenie wyłączone), HP stało na ~38% i bot dalej walczył z bugami (próg ucieczki 32%); 20:57:58 ucieczka, od ~20:58 HP spada równo 35%→0 przez 3 min BEZ widocznych wrogów (wygląda na truciznę; bot trucizny nie leczy) przy stojącej postaci na polu lądowania schodów; zgon 21:01:06. Potem bot kręcił się 1 h 40 min na ekranie wyboru postaci (`UCIECZKA HP 0%`, alarmy co ~5 min); zatrzymany 22:45 `zatrzymaj.sh`. Do ustalenia: źródło trucizny, czy `exura` wymaga wyższego lvl niż 7, brak reakcji bota na zgon na ekranie logowania (SMIERC_STOP nie zadziałał). Wniosek dla mapy `rook_bugi_z10`: bez leczenia i bez ucieczki w bezpieczne miejsce nie startować.
- **20.10 ~20:53 Bober ogarnięty:** od startu 20:27 bot szedł trasą z9 (`rook_raty_z9_do_smierci`) z postacią na z8 w jaskini szczurów z8 (872 pola; start z z8 = bez dojścia, `[RATUNEK] S2 złe piętro`, kroki „nie ruszył”), a o 20:36 gracz Trikin napisał na czacie „bot?” → `ALARM_GM`, PAUZA do odwołania (bot nie odpisuje, tak ma być). Bot zatrzymany `zatrzymaj.sh` i uruchomiony na nowej mapie `rook_raty_z8_do_smierci` (pętla `rook_raty_z8_petla` 491 pól, `prog_hp` -100 jak decyzja Karola; kopia `mapy.json.bak-20261020-bober-z8`). Po 2 min: 4 szczury, exp 65%→85%, jeden proces bota. **Pytanie Trikina bez odpowiedzi: czat zostawiony człowiekowi.**
- **20.10 ~20:41 Kutangen na bugach z10 (Rook), ZWERYFIKOWANE NA ŻYWO:** nowa mapa `rook_bugi_z10` (pętla 85 pól, 9 bugów w 4 przystankach, jaskinia 165 pól pod miastem; generator `generuj_trasy_rook_bugi_z10.py`, test `testy/test_trasy_rook_bugi_z10.py` 8/8). Dojście `rook_bugi_z10_dojscie` z z7 przez schody (32050,32187,z7), kieszeń z8, schody (32061,32197,z8) i (32056,32199,z9): z kieszeni z8 (32048,32188) bot zszedł na z10 w ok. 25 s, przeszedł pętlę (9 zabitych bugów, lvl 7, 5%→8%, bez orbit i alarmów). Nowość: pole `dojscie_z_dowolnego_pietra` w `mapy.json` (`tryb.py` → `MAPA_DOJSCIE_WSZEDZIE`, `uruchom.sh` przechodzi dojście od najbliższego punktu także ze z8/z9/z10, dawniej tylko ze z7; kopie `*.bak-20261020-dojscie-pietra`). Start: `./uruchom_instancje.sh kutangen rook_bugi_z10 ostrozny`. Drobiazg: po końcu dojścia log `Przejście pięter NIEUDANE … do punktu 0` (próba wrócenia do punktu 0 dojścia), bez skutków, bot zaczyna pętlę. `rook_bugi_z8` (z8 za pocztą) zostaje w zapasie.
- **20.10 ~20:30 Kutangen na bugi (Rook): nowa mapa `rook_bugi_z8` (trasa `rook_bugi_z8_petla`, 144 pól, 11 bugów w 5 spawnach za pocztą, generator `generuj_trasy_rook_bugi.py`, kopia `mapy.json.bak-20261020-rook-bugi`); bez dojścia — Karol wchodzi ręcznie schodami z7 (32077,32151) lub (32056,32146); start: `./uruchom_instancje.sh kutangen rook_bugi_z8 ostrozny`. Wejścia z mapy, niezweryfikowane botem; start bota czeka na Karola.**
- **20.10 ~20:30 trasy Rook z9/z10: dojście naprawione (droga od Karola).** `rook_raty_z9` (27 szczurów, pętla 283 pola) i `rook_raty_z10` (19 + 3 jaskiniowe, 122 pola): dojście z depo przez schody w depo (32027,32197,z7), kieszeń z8 i kratkę (32029,32195,z8) na z9, na z10 przez (32038,32212,z9). Pierwsza wersja (szyb (32046,32188)) była błędna: jedne schody z7-z8, w kieszeni węże. Testy 31/31 i 19/19, `waliduj_trase` OK, `pietra.kandydaci` rozpoznaje przejścia; **bot sam jeszcze nie przeszedł dojścia** (Bober lvl 1 stoi w jaskini z9 po ręcznym zejściu). Szczegóły i reguła przejść: `dane_tibia/mapy/README.md`.
- **20.10 ~19:17 F4c na żywo zaliczone:** testowa instancja `proba` (Webshare nr 3, bez konta): `sesja_gry.py start` (IP zgodne, Remmina sama) i `zamknij` (`sway: exit` 3 s, bez TERM, Remmina zamknięta, 4 boty nietknięte). Start z okna nie odpala już TigerVNC (`RETRONIC_PODGLAD=0` + Remmina po nasłuchu wayvnc). `proba` zarchiwizowana; proxy nr 3 wolne.
- **20.10 wieczór ORBITY (bot chodzi w kółko = zdradza bota) — F1 gotowe na `integracja-orbity` (worktree `pomocnik-orbity-integracja`, baza `dccfb2b`), checker APPROVE; **scalone do `ruch-r1-1014` = `646a999` (bez pusha, zgoda Karola); Kutangen zrestartowany 19:16 z `WPADNIECIE_POSCIG=1`, `STRAZNIK_ORBITY=1` (cień; kopia `instancje/kutangen/na_zywo.json.bak-20261020-orbity`), pozostałe boty na starym kodzie; następnie po obejrzeniu logów `[ORBITA]` → 2. Szkic dalszego kroku: `dane_tibia/SPEC_naprawa_zamiast_stop_1020.md` (Q1–Q3).** spec `dane_tibia/SPEC_orbity_straznik_1020.md` (diagnoza K1: Kutangen 16:38–17:02 24 min wahadła na z9 po upadku w dziurę w pościgu; skan 14–20.10: 7 takich orbit 5–25 min). A `WPADNIECIE_POSCIG` (wykrycie upadku w pościgu), B `STRAZNIK_ORBITY` 0/1/2 (`straznik_orbity.py`, progi 60 s/8 pól/15 zmian, reakcja = rotacja napraw, NIGDY STOP — zasada w `CLAUDE.md`), C `narzedzia/orbity.py` (skan logów, wahadła), D lina z każdego otwartego pojemnika (bez pokrętła). Pokrętła domyślnie 0. Testy: nowe zielone (strażnik 116/116), pełny zestaw = te same 10 czerwonych co baza. Pomiar strażnika: 14 epizodów, 0 fałszywych. Czeka na Karola: scalenie, postać na start (tryb 1 → 2), przeróbka starych STOP-ów (`wpadniecie._alarm`, `wyprawa.py:2097`, `pietra.py:856`) na naprawę.
- **20.10 ~18:28 WSZYSTKIE 4 proxy Webshare wychodzą z NOWYCH IP (zmierzone `siec_proxy.sh curl api.ipify.org`, stabilnie 4/4 na invincible):** invincible 84.247.60.125 → 77.83.233.69, dawajkesh 64.137.10.153 → 45.147.187.18, kolanoth 64.137.96.74 → 31.57.91.122, kutangen 45.38.107.97 → 64.137.10.120. Kontrola `ip_oczekiwane` blokuje każdy NOWY start gry tych instancji; działające gry mają stare połączenia (stan po reconnect nieznany). Przyczyna NIEZNANA (darmowy plan podmienił listę proxy? limit 1 GB?). Przyczyna: Karol kupił Webshare premium (nowa lista proxy). **Rozwiązane ~18:40 (zgoda Karola):** `ip_oczekiwane` = nowe IP (zmierzone ponownie), stare w `ip_poprzednie`, kopie `profil.json.bak-20261020-ip`; kontrola startu `siec_proxy.sh` przechodzi. Uwaga: kutangen 64.137.10.120 w tej samej /24 co dawne IP dawajkesha.
- **20.10 ~19:05 podgląd z paska/okna = Remmina (jak okna Karola), nie TigerVNC:** `sesja_gry.py podglad` otwiera `remmina -c ~/.local/share/remmina/retronic-<id>.remmina` albo daje fokus na jego okno; „otwarty” = połączenie z wayvnc (`instancja.podglad_polaczony`). Pasek po `omarchy restart shell`: lvl + znaczniki działają na żywo.
- **20.10 ~18:50 okno F4b + level/„Zobacz postać” (pasek i okno) gotowe, bez commita (3 agentów + checker NITS poprawione):** sekcja Sesja gry w oknie, `lvl N` w pasku i na kartach, klik w nick = podgląd (otwiera albo fokus `hl.dsp.focus` Hyprland 0.56), znacznik otwarty/zamknięty; `panel.py` czyta postać też przy zatrzymanym bocie (z 30 s przerwą po nieudanym odczycie). Testy py 53/141/30/67/35/69, node 203/203, QML offscreen OK. Do zobaczenia na żywo: przeładowanie paska (shell) i restart okna. F4c (start/zamknij na żywo) czeka na nową instancję i nowe IP w profilach.
- **20.10 okno: F4a „Sesja gry” — zaplecze gotowe (bez commita):** `okno_api.py sesja --instancja ID` (tylko odczyt: procesy, podgląd VNC, profil bez hasła, IP ze startu) i `sesja_gry.py start|zamknij|podglad` (TYLKO jedna instancja; `zamknij_sesje.sh` zamyka wszystkie, okno go nie używa). Testy `test_sesja_gry` 48/48, `test_okno_api` 136/136, checker NITS poprawione. Decyzje Karola: profil/proxy w oknie tylko do odczytu, próba na żywo na NOWEJ instancji (F4c). Dalej F4b (QML). Osobny spec do akceptu: `wtyczka-paska/specs/2026-10-20-retronic-lvl-i-podglad.md` (level w pasku/oknie, guzik „Zobacz postać”, Q1–Q3).
- **20.10 panel paska bez „głównej”:** po śmierci Mastafiana i Johny'ego główna instancja jest ukryta w panelu wtyczki i w `okno_api.py` znacznikiem `instancje/_bez_glownej` (katalog; `RetronicModel.instanceIds`, `lista_instancji`; testy JS 72/72, `test_okno_api` 136/136). Dane i prefiks główne nietknięte. Cofnięcie: `rmdir instancje/_bez_glownej`.
- **20.10 trasy szczurów na Rooku z mapy (bez dotykania gry):** `generuj_trasy_rook.py` -> `rook_raty_z8` (jaskinia tuż pod miastem, 34 szczury, pętla 491 pól, dojście z7 przez (32046,32221), **przejście niezweryfikowane w grze**) i `rook_kanaly_z11` (35 szczurów, pętla 479 pól, dojście = odwrócone `do_miasta`, przejścia sprawdzone). Wpisy w `mapy.json`, test `testy/test_trasy_rook.py` 19/19, `waliduj_trase` OK, `tryb.py --sucho` OK; podglądy `dane_tibia/mapy/rook_*.png`. Start: `MAPA=rook_raty_z8 TRYB=ostrozny ./uruchom.sh`. Otwarte: pierwszy zjazd z7 na żywo z Karolem (typ przejścia, lądowanie), zob. `dane_tibia/mapy/README.md`.
- **20.10 UH: tarcza zdjęta i niezałożona (08:09, Mastafian) — poprawka gotowa na branchu `fix/uh-tarcza-ratunek` (2 przeglądy, niewdrożona, czeka na merge+restart):** `dane_tibia/ruch/DIAGNOZA_tarcza_nie_wrocila_1020.md` (dowody, przyczyny, 7 kroków naprawy). Doraźnie naprawione ręcznie; lokalnie `UH_PRZERWA_PO_PORAZKACH_S`=60 (`cavebot.py`, bez commita), `UH_W_WALCE_MANA_MARGINES`=50 (`na_zywo.json`).
- **19.10 ratunek Haiku — F1 WDROŻONE w cieniu (merge `b089fc8`, bez push):** `RATUNEK_HAIKU=1` w `na_zywo.json` i `instancje/test/na_zywo.json` (kopie `.bak-20261019-ratunek`), boty zrestartowane 20:52 (Johny) i 20:54 (Mastafian). Sygnały: `logi/ratunek-<data>.jsonl` (+ instancje/test/logi). Pomiar offline 3,3/h, szczyt 14/h. Następnie: przegląd sygnałów na żywo z Karolem, potem F2 (Haiku wykonuje ruchy). Spec `dane_tibia/SPEC_ratunek_haiku_1019.md`. Czerwone sprzed merge: `test_serwis_akcje` (Slot.wnetrze), `test_serwis_marsz` 30/31.

- **Do zrobienia (zgłosił Karol 18.10, wymaga specyfikacji):** lina/drabina/dziura zajęte przez przedmioty (np. zwłoki szczura na polu liny) — nie da się skorzystać z przejścia. Bot ma nauczyć się zdejmować śmieci z pola przejścia (przesunąć/zabrać przedmiot) przed użyciem liny; dziś próba 18.10 11:30 na z9->z8 (33131,31806) skończyła się `Przejście pięter NIEUDANE` i dojście przerwane. Przyczyna zajętego pola niepotwierdzona zrzutem.

- **18.10 izolacja okna (poprawka w `bot.py`, bez commita):** `ekran_gry()` łapał dowolny proces z tekstem `retronicgl-` w wierszu poleceń (też powłokę z grepem) -> DISPLAY pulpitu `:0` (4480x1440) zamiast gry `:1`; bot ślepy, stał w miejscu. Teraz tylko argv[0] `RetronicGL-<n>.exe` + `RETRONIC_ID` + `WAYLAND_DISPLAY` z `sesja/wayland` swojej instancji (każdy bot widzi tylko swoje okno; docelowo kilka klientów). Test `testy/test_ekran_gry.py` 7/7. Start z z9 / z8 wymaga ręcznego `--dojscie gobliny_edron_z_depo` (uruchom.sh dodaje dojście tylko z z7 i tylko z `RETRONIC_POSTAC=Mastafian`). Inne źródła wspólne dla instancji (gniazdo `retronic-pomocnik.sock`) nie sprawdzone.

- **17.10 unikanie: tor gracza (branch `feat/unikanie-tor-gracza`, **wdrożone 17.10 23:21**: scalone ff do `ruch-r1-1014`, bez pusha, pokrętła `UNIKANIE_TOR`=1 i `UNIKANIE_PRZERWA`=1 w `na_zywo.json`, kopia `na_zywo.json.bak-20261017-unikanie-tor`; naturalna QA w grze otwarta):** bot nie idzie za graczem (kierunek z historii pozycji, "duch" 25 s po zniknięciu z widoku) i `PRZERWA` kończy się, gdy gracz podejdzie. Pokrętła `UNIKANIE_TOR`, `UNIKANIE_PRZERWA` (domyślnie 0). Spec i wdrożenie: `dane_tibia/SPEC_unikanie_tor_gracza_1017.md`; testy `testy/test_unikanie_tor.py` 26/26, zestaw jak baza. Pauza na rozmowę z graczem (F3) czeka na decyzję Karola.

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
- 20.10 10:07: `cavebot.alarm_dzwiekowy` (paplay) omijał plik `cisza` - teraz respektuje `cisza` i `RETRONIC_POWIADOMIENIA=0` (sprawdzone: 0 wywołań paplay przy pliku). Działa od następnego startu `mozg.py`; proces 620346 (start 09:41) ma stary kod.


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
- **Lina (poprawione 17.10 23:30):** pierwsze założenie (33107,31846,z8) zawiodło (bot 23:09 siedem prób, ALARM, STOP). Rejestrator trasy zapisał przejście na żywo: lina na (33107,31847,z8) ze stania (33107,31846,z8), lądowanie (33107,31848,z7), zejście przez otwór (33107,31847,z7) -> (33107,31847,z8). Trasy `gobliny_edron_do_depo/z_depo` poprawione scalone ff do `ruch-r1-1014` i wdrożone 17.10 23:21 (lina zadziałała 23:24; cała wyprawa do depo doszła do celu 23:29:12), test `testy/test_trasa_lina_edron.py` 9/9, nagranie w `dane_tibia/nagrania/`. Wyprawa 23:23-23:29 przeszła 4 liny (z8, z11, z10, z9) po 5-6 nieudanych próbach drabiny każda (~2,5 min zmarnowane) i 1 drabinę (z8->z7 (33165,31827)) w 1. próbie; minimapa nie odróżnia liny od drabiny. Poprawione (branch `fix/lina-druga-proba`, od następnego restartu bota): kolejność drabina, lina, lina, drabina, własne, E, W, N (`wypad._proby_drabiny`, `testy/test_lina_najpierw.py`), ostrzeżenie planu depo etap 19 (stoi (33167,31811,7) nie sąsiaduje z dziurą (33167,31813,7)) obsługuje dojście po 15 s.
- **Restart bota czeka na "teraz" Karola** (`./zatrzymaj.sh`, potem `MAPA=gobliny_edron TRYB=ostrozny RETRONIC_POSTAC=Mastafian ./uruchom.sh`; pętla stoi ok. 20 s). Dopiero po nim plan działa. Gdy skończą się blanki (`WYPRAWA_DEPO_BLANKI=1`, `WYPRAWA_AKTYWNA=1`, `WYPRAWA_TYLKO_DEPO=1`), bot idzie do depo i tam STOP.
- **Dane i metoda:** `dane_tibia/mapy/README.md`, `dane_tibia/SPEC_mapa_trasy_1017.md`. Lewa górna jaskinia z10 (-3): 5 spawnów, 18 goblinów, pętla 134 pola, wejście dziurą z9 (33063,31822), nieprzetestowana.
- **Git:** commity 17.10 wypchnięte do `7f25739` (main i ruch-r1-1014). Zmiany po nim (ten wpis, `wyprawa.py`, nowe trasy) zacommitowane lokalnie, niewypchnięte.

## 2026-10-17 23:45 — druga instancja testowa (`RETRONIC_ID=test`) obok głównej, bez bota

- **Co jest:** `instancje/test/` (świeży prefiks wine, `MachineGuid` ec12d217… przy d479dc50… głównej, pusty klient, konto testowe
  zalogowane ręcznie przez Karola). Sesja `RETRONIC_PODGLAD=0 ./sesja.sh`, podgląd `./podglad.sh` (z `dopasuj_okno`), nadzorca
  `./podglad_stroz.sh &` (wszystko z `RETRONIC_ID=test`). Zamykanie: `SWAYSOCK=$(cat $XDG_RUNTIME_DIR/retronic-sesja-test/swaysock) swaymsg exit`;
  NIE `zatrzymaj.sh` obok działającego bota (w razie błędu ustawia STOP domyślnej instancji).
- **Poprawka (`dac6b86`):** drugi wayvnc odmawiał startu (wspólne gniazdo sterujące) → `wayvnc -S <sesja>/wayvnc.sock` per instancja w
  `sesja.sh` i `podglad_stroz.sh`; sprawdzone na prawdziwym starcie (linia w `sway.conf`, nasłuch 5930, brak błędów). Bez ID bez zmian.
- **Pomiar identyfikatora (zmierzone):** klient składa `OTCLIENT-HARDWARE-ID-V2` (DISK/VOLUME/MACHINE/LAST-RESORT-MAC), a przy starcie do ekranu
  logowania czyta tylko `MachineGuid`. NIEZMIERZONE: odczyty przy logowaniu, to co trafia na serwer, czy serwer porównuje. Skrypty Lua klienta są
  zaszyfrowane (nie odszyfrowywano). Pierwsze minuty z dwoma klientami (to samo IP): brak komunikatu serwera, główna sesja bez zmian — nie dowód.
- **Otwarte:** obserwacja kilka godzin; czy porty 5501/5502 to ten sam świat (adresy gry testu częściowo inne niż głównego);
  maskowanie IP/proxy NIE zrobione (wymaga dostawcy); bot na testowej postaci dopiero po wyniku obserwacji. Kopia prefiksu głównego niesie
  `MachineGuid` i zapisane konto z `autoReconnect` (może wyrzucić główną postać) — robić świeży prefiks.
- Procedura i pułapki: repo omarchy, `docs/cheatsheets/retronic-podglad.md`.

## 2026-10-19 14:00 — serwis w Edronie (wymiana gold, depo, ham, backpack, blanki): skrypt gotowy, test na żywo czeka

**Co:** `./serwis.sh` robi całą kolejkę jednym skryptem z listą kroków w danych (`trasy/serwis_edron.json`, kolejność edytowalna):
bank (Ebenizer: `change gold` -> liczba platinum -> `yes`) -> depo (wolna wnęka z 8, locker -> depot chest, bag z UH i platinum ponad 3) ->
jedzenie (Mirabell, `5 ham`, cel 5 szt.) -> backpack (Beatrice, `backpack`, 20 gp) -> blanki (Alexander, `20 blank rune`, przeniesienie do nowego baga)
-> wyjście na z7 przy depo (stąd `uruchom.sh` dodaje dojście na gobliny). Opcje: `--na-sucho [--od x,y,z]`, `--kroki a,b`, `--od-nowa`, `STARTUJ=1`.
**Dane:** z Twojego ręcznego nagrania (`trasy/edron_serwis_surowa.json`, 208 pkt, 14 łączników pięter) i znaczników; wnęki depo z mapy klienta.
**Specyfikacja i pomiary na żywo (dialogi, współrzędne, układ panelu, Move Objects):** `dane_tibia/SPEC_edron_serwis_1019.md`.
**Testy:** `testy/test_serwis.py` 69/69, `testy/test_serwis_akcje.py` 62/62 (atrapy + prawdziwa mapa + zrzuty panelu `testy/dane/panel_*.png`);
kontrola mutacyjna (16 celowo wstrzykniętych błędów wykrytych). Niezależny przegląd (checker, 2 rundy), uwagi #1-#5 i R1-R7 naprawione; trzeciej rundy nie było.
**Nie sprawdzone na żywo tym kodem** (Mastafian gra): rozmowa przez `Rozmowa`, `przygotuj_okna`, `depo_zloz`, `kup`, `przenies_blanki`, chodzenie po łącznikach.
Do testu na drugiej postaci: postać w Edronie, >= 260 gp i >= 100 gold do wymiany, bot zatrzymany (`./zatrzymaj.sh`), potem `./serwis.sh`.
**Otwarte:** automatyczne wywołanie serwisu z wyprawy do depo (dziś depo kończy się STOP i dymkiem, potem ręcznie `./serwis.sh`);
`loot.czy_runy` bierze plecak z większością blanków za bag na runy (błąd „klasyfikacja bagów”, serwis go omija nazwami okien);
`loot.przenies_miedzy` odmawia na `depot chest`; `SLOT_PLECAKA_EKWIPUNEK` w `loot.py` ma współrzędne starego układu (serwis liczy z układu panelu).

## 2026-10-19 — „Wróć do miasta” na żądanie (WROC), F1 + test na żywo
- Spec: `dane_tibia/SPEC_wroc_do_miasta_1019.md` (zatwierdzona). Kod: `wroc.sh` + hook w `wyprawa.py` (`_okazja_wroc`, `_wroc_czeka`),
  flaga `potrzeby["reczny"]` (zawsze depo, bez powrotu), czyszczenie `WROC` w `uruchom.sh`/`serwis.sh`/`uruchom_trolle.sh`.
  Testy: `test_wyprawa` 160/160, `_dojscie` 25/25, `_droga_depo` 50/50, `test_wypad_bieg` 6/6, `test_instancja` 33/33; checker: CHANGES-REQUIRED -> poprawione.
- **Test na żywo (Mastafian, gobliny_edron z8, 16:28-16:33):** `./wroc.sh` 16:28:xx, bot dokończył walkę, ruszył 16:29:03 (`wyprawa:depo:reczny`),
  4 przejścia pięter (lina z8->z7, z11->z10->z9, dziura z7->z8), `DEPO osiągnięte w (33173,31796,8)` 16:33:01, STOP zapisany, bot zatrzymany;
  plik WROC usunięty po ruszeniu. Całość ok. 4 min. NIE sprawdzono: powiadomienie na pulpicie, powrót na spot (z założenia nie robi), serwis po dojściu.
- Otwarte: F3 guzik w pasku (`plugins/charlie.retronic`, instalacja = poziom 2), `rook` nie ma planu depo, zmiany niezacommitowane (branch `feat/wroc-do-miasta`
  w worktree `pomocnik-wroc` = ta sama zmiana; worktree do usunięcia), `bot_dziala()` w `dopasuj_okno.py` globalne zamiast per instancja,
  przyczyna 2-godzinnej awarii lootu (`okno_niewidoczne` 13:00-14:57) nieustalona (pomógł restart sesji), `hybryda` z Haiku nie włączona.
- Poprawka Mijania (`MIJANIE_OBOZ_BLISKO=3`, `unikanie.py`, testy M10a-d): gracz bez kierunku <= 3 pola nie jest obozowiczem; nieweryfikowana na żywo.

## 2026-10-20 22:45 — zbiórka botów z Rooka (Karol: „do miasta albo wylogować”)
- Żaden bot nie miał planu powrotu (wszystkie na Rooku, `plan_depo_dostepny: false`). Wylogowanie Ctrl+L działa, ale `autoReconnect: true`
  loguje z powrotem po < 60 s, więc po Ctrl+L trzeba zamknąć klienta (`sesja_gry.py zamknij`).
- **Błąd agenta:** wylogowany i zamknięty został kutangen, na którym Karol grał ręcznie (bot stał z `STOP_RECZNY`). Klient uruchomiony ponownie
  (`sesja_gry.py start`), Karol loguje sam. Reguła: instancji z `STOP_RECZNY` i bez procesu bota nie ruszać bez wymienienia jej z nazwy.
- kolanoth wylogowany i zamknięty (22:49). Karol: „wyłącz wszystkie, sam pójdę” — boty invincible, dawajkesh, bober, wydra zatrzymane
  (`zatrzymaj.sh`), gry i podglądy otwarte. Spec powrotu i wylogowania: `dane_tibia/SPEC_powrot_rook_1020.md` (szkic, Q1–Q4).
- 23:15 spec `dane_tibia/SPEC_powrot_rook_1020.md` **ZATWIERDZONY** (cele: 2 depo na z8 + 4 sklepy, losowane i rezerwowane między
  instancjami; po dojściu STOP; `wyloguj.sh` zamyka klienta; bez nowego guzika, Rook = kolejne miasto dla `wroc.sh`/`⌂ Miasto`).
  **Następny krok:** implementacja F1 (PLANY_PK Rooka z odwróconych dojść + losowy cel) i F2 (`wyloguj.sh`, prototyp `narzedzia_jednorazowe/wyloguj_prototyp_1020.py`
  Claude 20.10; logika opisana w specu). Punkt wejścia w kodzie: `wyprawa._okazja_wroc` -> `_start_wyprawa("depo:reczny")`, `_baza_dojscie`, `PLANY_PK`.

## 2026-10-21 16:20 — nowe spoty z mapy: Edron trolle wschód (trasy gotowe), przegląd Thais/Edron

- **Edron trolle, wschodnie skrzydło** (`generuj_trasy_edron_wschod.py`, z mapy klienta + monster.db): `trolle_edron_z9w_petla` (składowa 309 pól, 15 trolli, 5 przystanków, pętla 133 pola) i `trolle_edron_z10w_petla` (275 pól, 13 potworów, pętla 35 pól: za mała na osobny spot). Dojścia `*_dojscie` = `edron_depo_trolle` + z8 do przejścia (33115,31744) [+ z9 (33127,31726) na z10]. Typ przejść i lądowanie NIEZWERYFIKOWANE w grze. Podglądy `dane_tibia/mapy/trolle_edron_z9w.png`, `z10w.png`. Wpis `mapy.json` `trolle_edron_z9w` dodany po akcepcie Karola 21.10 (kopia `mapy.json.bak-20261021-nowe-spoty`); test na żywo czeka na wskazanie postaci. `generuj_trasy_rook.obraz` dostał opcjonalne `jedn`/`opis_przyst` (domyślnie bez zmian).
- Trolle Edron po składowych mapy: z8 jeden obszar (44 trolle), z9 zachód (34 + 5 niedźwiedzi, osobny), z9 wschód (15), z10 kieszenie. Na z8 na północ (33097,31686) 2 smoki w osobnej składowej (wejście z z7).
- **Thais północ, jaskinia trolli** (bez trasy bota): z8 składowa 984 pola (trolle 8 przy (32356,32131)/(32357,32145), resp 400–450 s, pająki, szczury, cave raty), wejścia z powierzchni m.in. (32346,32137), (32359,32131); z9 składowa 260 pól, 16 trolli, zejścia z z8 przy (32326,32158)/(32339,32122). UWAGA: z z8 przejścia (32368,32112), (32374,32100), (32376,32128) prowadzą do z9 z cyklopami (32347,32110), (32356,32100): trasa ma je omijać.
- Kandydaci lvl 8–12 (sufit z respawnu, nie pomiar): Edron rotwormy z8 (33247,31919) 26 szt., z10 (33255,31855) 13, z9 (33234,31846) 10 (41 pól od świątyni); Edron gobliny z10 (33105,31808) 19 i bugi z10 (33105,31849) 18. Skrypty analizy w scratchpadzie sesji (nie w repo).
- **Thais północ — trasy gotowe (decyzja Karola 21.10: robimy, trasa omija poison spidery):** `generuj_trasy_thais_pn.py` → `thais_pn_z8_petla` (334 pola, 8 przystanków, 33 potwory: Troll,Rat,Cave Rat,Spider,Bug; strefa zakazana 6 pól wokół poison spiderów (32326,32155,z8) = ślepy korytarz na południu, pętla i przystanki poza nią) i `thais_pn_z9_petla` (109 pól, 16 trolli; poison spidery z9 za ścianą). Wpisy `thais_pn_z8`, `thais_pn_z9` w `mapy.json` **bez dojścia**: mapa nie mówi, które wejście z z7 prowadzi w dół ani jak zejść z z8 na trolle z9 (z9 (32339,32122) to drabina w górę pod ścianą z8; (32326,32158) 3 pola od poison spiderów). Dojście = nagranie Karola (`nagraj.sh`) z depo Thais do z8, potem na z9. `waliduj_trase.py`: obie pętle i z9w OK; `trolle_edron_z9w_dojscie` ma 1 błąd #15 odziedziczony z `edron_depo_trolle` (ten sam w oryginale, bot chodzi nim codziennie). Podglądy `dane_tibia/mapy/thais_pn_z8.png`, `thais_pn_z9.png`.
- **Thais północ — dojście z8 dopisane (21.10, po pytaniu Karola „nie mamy dojścia z Thais?”):** na z7 nad jaskinią są żółte bloki zejść (kolor 210 + flaga 2): (32338,32122..32124), (32339,32134..32135), (32345,32146). Generator wybiera najkrótsze z depo Thais (32348,32225,z7): `thais_pn_z8_dojscie` 125 pkt przez (32345,32146), lądowanie (32345,32146,z8), 19 pól od poison spiderów; `waliduj_trase.py` OK; wpis `thais_pn_z8` ma `dojscie`. Typ zejścia niezweryfikowany. Karol chce wysłać kutangena (lvl 9, exura już włączona: `ZDROWIE_CZAR_AKTYWNY=1`, HP < 80%).
- **Thais północ — poprawka dojścia (21.10 16:30, test na żywo kutangen):** pierwsze dojście przez żółte pole (32345,32146,z7) wprowadziło postać na z6: **żółte pola (kolor 210) nad jaskinią to schody W GÓRĘ** (nad nimi chodliwe z6). Bot zatrzymany, postać na (32344,32146,z6). Generator wykrywa teraz zejścia sam: z7 z flagą 2, bez chodliwego z6 w 3x3 nad polem, z lądowaniem w składowej pętli bez strefy → (32347,32123) i (32335,32174) (kolor 24). Wybór: najpierw >= 15 pól od poison spiderów, potem najkrótsze → (32347,32123): z7 144 + z8 19 pól do pętli, min. 23 pola od poison spiderów (drugie: 11 pól). Dojście ciągnie się po z8 do pętli, bo A* bota nie zna strefy. `waliduj_trase.py` OK. Wcześniej tego dnia start bez `RETRONIC_POSTAC` pominął dojście (lekcja w `CLAUDE.md`).
- **Thais północ — DOSZEDŁ (21.10 16:36, kutangen, potwierdził Karol):** zejście (32347,32123,z7) to **zasypana dziura, trzeba łopaty**. Pierwsza próba 16:35 (use stojąc na polu) bez skutku; dopisane do `pietra.ZASYPANE` (kopia `pietra.py.bak-20261021-zasypane-thais-pn`; testy pietra_kratka 11/11, pietra_zajete 16/16, wielopietrowa 95/95, symulator 124/124). Po restarcie: zejście Left, łopata na (32347,32123), krok Right → z8 (32347,32123) 16:36:32. Kutangen dalej na pętli `thais_pn_z8`. Wcześniej tego dnia: z6 przez żółte schody w górę; po zatrzymaniu zszedł jednym klawiszem Right wysłanym do jego ekranu `:5` (`klawisz_x11.wyslij`, ekran z `bot.ekran_gry()` z RETRONIC_ID).
- **Procedura „nowy spot przez AI” spisana (21.10 16:45, polecenie Karola):** `dane_tibia/mapy/PROCEDURA_nowy_spot.md` (8 kroków + przypadek Thais północ), skill `skille/nowy-spot/SKILL.md` (link `~/.agents/skills/nowy-spot`, `~/.claude/skills/nowy-spot`; cofnięcie: usunąć oba linki), narzędzia `narzedzia/spoty_skladowe.py` i `narzedzia/przejscia_pieter.py` (sprawdzone: odtwarzają ranking Thais i kierunki (32345,32146) W GÓRĘ, (32347,32123) W DÓŁ). Następny krok wymagający specu: jeden ogólny generator i samowykrywanie zasypanej dziury.
- **Spec ogólnego generatora spotów (21.10 16:50, DRAFT):** `dane_tibia/SPEC_generator_spotow_1021.md` — F0 biblioteka z regresją bajtową, F1 `generuj_spot.py` + deklaracje JSON, F2 walidacja i wpis `mapy.json`, F3 pierwszy spot tylko generatorem na żywo, F4 (opcja) łopata bez ręcznego `ZASYPANE` + poprawka pamięci przejść (`przejscia_nauczone.json` ma Thais północ jako „krok”, choć działa łopata + krok). Czeka na Q1–Q5 Karola; kodu brak.
- **Generator spotów: decyzje Karola + F4 zrobione (21.10 ~17:00):** spec `dane_tibia/SPEC_generator_spotow_1021.md` ZATWIERDZONY (JSON; Thais+Edron, dojście z najbliższego depo; pętle wielopiętrowe tak (F1b); F4 teraz; spoty wybiera Karol). F4: `pietra._zasypana` (ZASYPANE / pamięć „lopata” / `PIETRA_LOPATA_AUTO`), krok po łopacie zapisuje „lopata”; pamięć Thais północ `32347,32123,7>8` poprawiona krok→lopata. Test `testy/test_lopata_pamiec.py` 10/10 (stary kod: 5 FAIL, w tym pamięć „krok”), regresja 9 testów pięter/wyprawy zielona. Kopie `*.bak-20261021-lopata-pamiec`, `przejscia_nauczone.json.bak-20261021-lopata`. Działa od następnego restartu botów. Następna faza: F0 (biblioteka z regresją bajtową) — czeka na „tak”.
- **Generator spotów F0 ZROBIONE (21.10 ~17:30, agentami):** `spot_lib.py` + 7 generatorów na bibliotece, bramka bajtowa `testy/test_spot_lib_regresja.py` 57/57 (sabotaż czerwony), checker NITS (6 wymagań dopisanych do F1 w specu), scalone do głównego checkoutu, kopie `.bak-f0-20261021/`, worktree usunięty. Nie ruszało kodu botów. Następne: F1 (`generuj_spot.py` + deklaracje JSON, dojście z najbliższego depo) — czeka na „tak”.
- **OGIEŃ na Edron z9 wschód (21.10 17:14, invincible):** dojście `trolle_edron_z9w` prowadziło na (33115,31744,z8), które generator wziął za zejście (flaga 2), a to ogień: telemetria 17:14:20–17:14:51 HP 91% → 58% stojąc na tym polu; bota zatrzymał Karol. Kolanoth stanął wcześniej na z11 (brak liny, STOP 17:09:36). Poprawka: wejście (33119,31740) (kolor 210 = prawdziwe schody), generator omija znany ogień (`ogien_pola`, bufor 1), nowe punkty 0 na/obok ognia, waliduj OK (dojście: stary #15). Reguła: flaga 2 w kolorze podłogi poza z7 = PRZESZKODA (`spot_lib.przeszkoda_na_podlodze`, `zejscia(ogien=)`, `przejscia_pieter` pisze PRZESZKODA). Zapisane w skillu `nowy-spot`, procedurze, `CLAUDE.md`. Kopie `*.bak-20261021-ogien`. Boty invincible/kolanoth NIE restartowane (decyzja Karola). Uwaga: `ogien_stale.json` to w większości fałszywe ognie („bez spadku HP”) — prawdziwego ognia (33115,31744) w nim NIE było jako pola, tylko sąsiedzi.
- **Edron z9 wschód DZIAŁA (21.10 17:24–17:28, Kolanosh/kolanoth lvl 8, start z (33167,31823,z9) na polecenie Karola):** dojście `trolle_edron_z9w_dojscie` (169 pkt): z9→z10→z11 krokiem, z11→z10 (33133,31805) i z9→z8 LINĄ (próba 2; rano bez liny utknął), z8→z7, z7→z8 dziura (33117,31776), z8 po odcinku bez ognia do schodów (33119,31740), zejście krokiem na z9 17:27:40, pierwszy troll zabity 17:27:58 na (33114,31741,9). HP 100% przez całe dojście. Wymagania: rope w plecaku. Invincible nadal zatrzymany (decyzja Karola „nie”).

## 2026-10-21 17:35 — PODSUMOWANIE dnia: nowe spoty przez AI (sesja Claude z omarchy)

**Działa na żywo:** Thais północ `thais_pn_z8` (kutangen, od 16:36; łopata na (32347,32123)) i Edron z9 wschód `trolle_edron_z9w`
(kolanoth/Kolanosh, od 17:27; lina na dojściu). **Gotowe bez testu:** `trolle_edron_z10w` (35 pól, doczepka), `thais_pn_z9` (bez dojścia).
**Narzędzia:** skill `nowy-spot`, `dane_tibia/mapy/PROCEDURA_nowy_spot.md` (8 kroków, 2 przypadki), `narzedzia/spoty_skladowe.py`,
`narzedzia/przejscia_pieter.py` (W GÓRĘ / W DÓŁ / PRZESZKODA), `spot_lib.py` (F0), F4 łopata w pamięci (`testy/test_lopata_pamiec.py`).
**Reguły z porażek (wszystkie w procedurze i `CLAUDE.md`):** start z `RETRONIC_POSTAC`; żółte 210 bywa w górę; stoi i nie spada = łopata;
flaga 2 w kolorze podłogi poza z7 = ogień/przeszkoda; omijać `trasy/ogien_*.json`; ekwipunek z opisu mapy (lina/łopata);
monitor dwufazowy. **Otwarte:** invincible zatrzymany na (33112,31747,z8) 144/205 HP (Karol: nie puszczać); F1 generatora
(czeka na „tak”; przed nim odświeżyć bazę bramki F0 — edron_wschod zmieniony celowo); `thais_pn_z9` bez zejścia z z8;
`test_trasy_rook` 17/19 i `_raty2` 30/31 czerwone od wcześniej (test vs `mapy.json` „potwory”). Bez commita.
