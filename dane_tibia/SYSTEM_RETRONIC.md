# SYSTEM RETRONIC: jeden kompletny system (16.10) — SZKIC do akceptu Karola

Dokument nadrzędny. Zbiera w jedno wszystkie specyfikacje i pomiary z 13-16.10. Nie zastępuje ich szczegółów (zostają jako załączniki),
ale mówi, co obowiązuje, co jest wdrożone, co wyłączone, co jest szkicem i co jest ze sobą sprzeczne.
Nic tu nie jest wdrożone przez sam dokument. Zmiany w bocie dopiero po akceptacji, fazami z bramkami (sekcja 7).

Źródła statusu: (a) moje pomiary i skrypty 16.10 (`~/Games/Retronic/modele-test/`), (b) dwa odczyty repo przez agentów (tylko odczyt, bez uruchamiania:
`podsumowanie_A` nawigacja/ruch, `podsumowanie_B` zachowania/bezpieczeństwo), (c) `STAN.md`. Status oznaczony [wg agenta] nie był przeze mnie sprawdzony w kodzie.
Znaczniki: [POTW] udowodnione dowodem, [HIP] hipoteza, UNKNOWN brak danych (nie zgadujemy).

## 1. Cel i zasady nadrzędne

Cel: bot Tibii (Retronic, trolle Thais), który gra bezpiecznie i długo bez człowieka, nie traci godzin na zawieszki, reaguje na sytuacje spoza schematu
i zachowuje się mniej schematycznie. AI ma wspierać grę tam, gdzie reguły nie wystarczają, a nie zastępować odruchy.

Zasady (z decyzji Karola 15-16.10):
1. **Kod to odruchy i bezpieczeństwo.** Ogień, ucieczka, leczenie, UH, pauza PK, alarm GM zawsze w kodzie; żaden model ich nie wykonuje ani nie zdejmuje. Model może tylko PODNIEŚĆ alarm.
2. **Kod liczy fakty i opcje dopuszczalne; model wybiera spośród nich** (wzorzec testu Marcina na Snake'u). Poniżej progu pewności lub przy awarii: dzisiejsza reguła.
3. **Prawda pochodzi z danych z gry, mapy i symulatora**, nie z opinii innego modelu (decyzja 16.10: Haiku nie jest nauczycielem). Etykiety złote: przejęcia Karola.
4. **Każda zmiana za pokrętłem, domyślnie 0**, z tryb cienia przed włączeniem i prostym cofnięciem (pokrętło 0, bez restartu modelu).
5. **Spec -> test -> cień -> włączenie -> pomiar.** Bez dowodu nie ma "gotowe". Człowiek decyduje, agent rekomenduje.
6. **Brak danych = UNKNOWN i pytanie**, nigdy zgadywanie.
7. Bot gra na żywo: nie zmieniamy kodu pod działającym procesem bez wiedzy Karola; restart i `git pull` robi Karol.

## 2. Architektura (warstwy)

```
L9  Dane i uczenie        telemetria, zbiór, symulator, etykiety Karola, trening        (offline + zapis na żywo)
L8  Ekonomia              serwis w mieście, wyprawy, zakupy, blanki, depo              (szkic)
L7  Bezpieczeństwo        PK, GM, PvP, granice twarde, powiadomienia                   (wdrożone, PvP wyłączone)
L6  AI językowe           Haiku 5.5: czat, "głowa", czaszka, obserwator; agent trudnych (częściowo)
L5  Decyzje               reguły z mapy -> symulator -> modele D1-D6, losowość         (szkic + tryb cienia)
L4  Nadzór i reakcja      wykrywacz braku postępu, D3, strażniki, eskalacja            (NOWE: tylko log dziś)
L3  Nawigacja             patrol, pościg, przejścia pięter, wyprawa, dojście, wpadnięcie
L2  Odruchy i walka       stany cavebota, UH/leczenie, loot, jedzenie, ucieczka
L1  Odczyt i świat        pamięć gry (strażnik), mapa OTMM, graf pięter, drzwi, łączniki, dziury, ogień
L0  Platforma             sesja sway/wine, strażnik, instancje, start/stop, panel, powiadomienia, claude CLI
```
Przepływ decyzji: L1 fakty -> L2/L3 odruchy i marsz -> L4 wykrywa brak postępu -> L5 wybiera reakcję z opcji (kod podaje tylko dopuszczalne) ->
L7 filtruje bezpieczeństwo -> wykonanie. L6 działa obok (rozmowy, rzadkie trudne przypadki), L9 zapisuje wszystko i karmi uczenie.

## 3. Warstwy: stan, pokrętła, słabe punkty

### L0 Platforma i eksploatacja [wg agenta + własny odczyt]
- Moduły: `sesja.sh` (zagnieżdżony sway + wine, okno 1175x910), `straznik.py` (pamięć gry przez gniazdo), `uruchom*.sh`/`zatrzymaj.sh` (STOP/STOP_RECZNY), `panel.py`/`status.sh` (pasek),
  `powiadom.py` (limity 1/60 s na klucz, 20/h), `instancja.py` (`RETRONIC_ID`, drugi klient), `retronic-mozg.service` (NIE zainstalowana), `instaluj.sh`/`PRZENOSINY.md`.
- Zależność zewnętrzna: Claude Code CLI (`claude -p`). 16.10: 2.1.289 -> 2.1.300, alias `haiku` = `claude-haiku-5-5` [POTW], logowanie karol@sailes.tech (Max), bez klucza API [POTW].
- Słabe punkty: pokrętła z trzech miejsc (sekcja 5); stan git != drzewo robocze (niezacommitowane `mozg.py`, `analityk.py`, specyfikacje, STAN.md); okno 1175x910 bez zrzutu weryfikacyjnego (UNKNOWN).

### L1 Odczyt i świat
- `rdzen.py`/`bot.py` (pozycja, HP, stwory, widmo po relogu), `mapa.py` (OTMM: flagi 1 widziane, 2 bez drogi (schody/dziura/ramp, czasem pole magiczne/przedmiot), 4 ściana; A* ze skosami),
  `ogien.py`, `trasy/dziury_nauczone.json`, `znane_pola.json`, graf patrolu `trasy/miejsca_troll.json` (8 miejsc, 8 przejść schodowych, 1 łącznik ręczny).
- Reguły przejść pięter (`pietra.py`, zweryfikowane na żywo): w dół = pole z flagą 2 na piętrze a, lądowanie (x,y,a+1); w górę = pole R z dziurą (flaga 2) piętro wyżej, lądowanie (R.x, R.y+1, a-1).
- Drzwi (32505,32270,8): w mapie ściana, w grze przechodnie po otwarciu; mapa nie widzi przejścia, więc łącznik ręczny (32506,32270)->(32502,32270). `PATROL_DRZWI=1` [wg agenta].
  **Zachowanie drzwi [POTW pasywnie]: nie zamykają się same po przejściu; Use potrzebne tylko przy 8 z ok. 290 przejść (3%), bez zależności od czasu.** Powód zamknięć UNKNOWN.
- Słabe punkty: dwie rozbieżne implementacje przejść (`pietra.py` i `wypad.py`; R2 `przejscia.py` nie powstało); flaga 2 mapy nie zawsze = przejście; detektor ognia daje fałszywe/stałe wykrycia (maska z trzech mechanizmów).

### L2 Odruchy i walka
- `cavebot.py` (stany IDZ, WALKA, LOOT, JEDZENIE, UCIECZKA, GRACZ, UH, ZDROWIE), `uh.py`/`runa_klik.py`/`runa.py`, loot (`loot*.py`), jedzenie, ucieczka przy niskim HP. Pętla co 50-300 ms; krok 0,6-0,9 s zależnie od pola.
- Wdrożone [wg agenta]: `IGNOR_TWARDE=1`, `STRAZNIK_CEL=1`, `OGIEN_STALY=1`, `OGIEN_MASKA_TYLKO_SCIANY=1`, `OGIEN_MASKA_DANE=1`, `UH_AKTYWNY=1`, `ZDROWIE_CZAR_AKTYWNY=1` (HP 80), `UH_W_WALCE=1`.
- Po naprawach 14-15.10 wybór celu działa: zabite cele 27-44% (11-13.10) -> 83-86% (14-15.10), odpuszczenia "za ścianą" 451 -> 10 [POTW z telemetrii].
- Wyłączone: `STRAZNIK_POSTEP=0`, `BLOK_WYJSCIE=0` (zabezpieczenia istnieją w kodzie, nigdy nie włączone), `P1c` (Escape przy zmianie celu) nie zrobione.

### L3 Nawigacja
- `cavebot.py` (patrol po miejscach, pościg ze skosami, dojście), `pietra.py`, `wypad.py`/`wyprawa.py` (wyprawy i dojście do depo), `wpadniecie.py` (upadek w dziurę/kieszeń), `obecnosc.py` (patrol wg respawnu).
- Wdrożone [wg agenta]: `PIETRA_TRYBY_Z_DANYCH=1`, `POSCIG_SKOSY_ZAPAS=1`, `DOJSCIE_BIEGNIJ=1`, `DZIURA_PRZY_CELU`, `WYPRAWA_DOJSCIE_PATROLEM`, wyjście z kieszeni z9 drabiną.
- Patrol wg respawnu: krok 1-2 zrobione, tryb cienia (`PATROL_RESPAWN_CIEN=1`), włączenie (`PATROL_RESPAWN=1`) nie zrobione; zysk exp/h nierozstrzygnięty.
- Niewdrożone: R2 (wspólne przejścia), R3 (`PLYNNY_RUCH`); N8(b) (nieudane dojście wciąż kończy proces zamiast czekać) [wg agenta].
- Dane: tylko ok. 49% czasu w IDZ to marsz; straty: ogień 11,8%, manewry przy schodach 9,5% (`ruch/PLYNNOSC.md`, dane 12 h).

### L4 Nadzór i reakcja (do zbudowania; sedno niezawodności)
- Stan dziś: `d3_zawieszka.py` (krok A, tylko log: rekord `decyzja` D3 + `d3_wynik`), `straznik_celu`, watchdog bezczynności (przy zawieszce tylko "porzucam odłożone zwłoki"), `powiadom`.
- **Dowód potrzeby [POTW]:** 16.10 11:21-11:48 bot stał 27,5 min przy (32507,32270,z8). Dla Haiku "głowa" odpowiadała ok. 30 razy `kontynuuj`, zdarzenie `brak_zabic` zignorowała na 600 s; D3 tylko zalogował opcje (cofnij i przejscie_pietra były możliwe).
  Zawieszki po naprawach: 15.10 3,8% czasu, 16.10 jedno zdarzenie 27,5 min (89% zawieszek tego dnia).
- Hipoteza przyczyny (kod `_drzwi_hak`, przeterminowana flaga `otw` + zamknięte drzwi po wschodniej stronie): symulacja 30/31 zawieszek bez poprawki, 0/31 z poprawką, ale założenie symulatora (drzwi zamykają się natychmiast) okazało się fałszywe; w grze to rzadkie połączenie [HIP].
- Projekt docelowy: wykrywacz braku postępu z progami (30 s lokalnie -> reakcja D3 -> 5 min eskalacja -> alarm i STOP), niezależny od modeli tekstowych, z zamkniętym zbiorem opcji (krok_skos, cofnij, inny_punkt, przejscie_pietra, czekaj, alarm). Zasady Z1-Z8: `SPEC_zasady_zawieszki_1016.md`.

### L5 Decyzje
- Stan: modele numpy D1 (brak sygnału, AUC 0,51-0,54), D2 (AUC 0,83-0,93, równe samej odległości) nie wgrane; D4 19 decyzji w cieniu; rekord `pvp` bez modelu. Żaden model nie steruje botem [POTW STAN.md].
- Zmierzone 16.10 [POTW]: gotowe modele decyzyjne zero-shot (Mapika Decider 2B, Strands Decider 2B) są szybkie (33-129 ms na RTX 3060 Ti, ok. 3,9 GB VRAM; CPU 1,6-2,4 s), ale nie biją klasy większościowej na 54 zawieszkach
  (46%/39% wobec 61%), są niestabilne przy permutacji opcji (22%/30%) i nigdy nie są pewne. Nie nadają się do sterowania D3 w obecnej postaci.
- Kolejność: (1) reguły z mapy i symulatora (graf pięter, drzwi, łączniki; wyrocznia MUSI iść po grafie pięter i liście przejść bota, nie po fladze 2), (2) tryb cienia, (3) model dopiero tam, gdzie reguła nie rozstrzyga, uczony na wynikach symulatora i prawdziwych wynikach decyzji.
- **Losowość (mniej schematyczne zachowanie):** wybór między równorzędnymi opcjami próbkowany z rozkładu (softmax z temperaturą, ograniczony do opcji dopuszczalnych), losowy czas oczekiwania i wybór punktu trasy; nigdy w obrębie granic z zasady 1.
- Szczegóły: `SPEC_model_steruje_gra_1016.md`, `SPEC_model_lokalny_1015.md`, `SPEC_model_D3_utkniecia_1015.md` (zatwierdzony 15.10, krok A zrobiony).

### L6 AI językowe
- Wdrożone: "głowa" (`mozg.py`, decyzje i zdarzenia; 94% to `kontynuuj`), czat do graczy (`czat_spot.py` + `Czat`; włączony na żywo `CZAT_SPOT_AKTYWNY=1`, pisze Haiku z kontekstem, odstępstwo od pierwotnej puli tekstów),
  czaszka ze zrzutu (`czaszka.py`, `CZASZKA_ODCZYT=1`, limit 20/h), obserwator i analityk pościgu (tylko doradcze).
- Model: wszystkie wywołania przez alias `haiku`. Haiku 4.5 -> 5.5: ok. 25x taniej (0,0127 -> 0,0005 USD/wywołanie), ok. 4x szybciej (4-7 s -> 1,4-1,6 s), bez "myślenia" [POTW pomiar na prostym stanie]; w nowym logu 4 s/0,001 USD na decyzję, obserwator i analityk 22 udane, 0 błędów
  (wcześniej 75% timeoutów) [POTW 12:59-13:40]. Skala przed zmianą: 2445 udanych + 1368 nieudanych wywołań w 66 h, 94% `kontynuuj`.
- Niezacommitowane zmiany interwałów (`mozg.py` hybryda 30-60 s -> 600-900 s, `analityk.py` 180-300 -> 900-1200 s, obserwator 60 -> 600 s): jeszcze nieaktywne w działającym procesie (zmienione 13:33, bot wystartował 12:59).
- **Agent trudnych przypadków (do zbudowania):** silniejszy model wołany rzadko (kilka razy na godzinę) przez wykrywacz anomalii z L4 (brak rozwiązania reguły, powtarzające się błędy, nieznane okno), ze zrzutem i telemetrią, z zamkniętym zbiorem akcji;
  jego wnioski wracają jako PROPOZYCJE nowych reguł do akceptu człowieka, nie jako bezpośrednie sterowanie. Ryzyko: ten sam błąd co dziś (rutynowe `kontynuuj`), dlatego wyzwalaczem jest wykrywacz progowy, a nie opinia modelu.

### L7 Bezpieczeństwo [wg agenta]
- Włączone: obrona PK (`PK_OBRONA=1`, `PK_LECZ=1`, ucieczka do depo, karencja 30 min), czaszka (`CZASZKA_ODCZYT=1`), alarm GM po nicku (`GM_NAZWA`), filtr czatu (`bezpieczna_wiadomosc`, max 10 słów, HP >= 70%, cisza po ręcznej wiadomości Karola).
- Wdrożone, WYŁĄCZONE do próby na żywo: walka PvP (`PVP_WALKA=0`; progi: UH 20%, exura 80%, HP_MIN 40, HMM do końca); nie zrobiono próby strzału HMM i UH w gracza.
- Słabe punkty: detektor PK przetestowany na jednym prawdziwym ataku (brak pomiaru fałszywych alarmów); skuteczność czaszki z Haiku niezmierzona; ucieczka do depo przez pułapki (dziury, drzwi, kieszenie) już raz skończyła się śmiercią 15.10; czat z modelem = ryzyko prompt injection ograniczone filtrem.

### L8 Ekonomia
- Wdrożone: wyprawa tylko do depo (`WYPRAWA_AKTYWNA=1`, `WYPRAWA_TYLKO_DEPO=1`, `WYPRAWA_JEDZENIE=0`), `zakupy_miasto.py`, `zloz_depo.py` (`WYPRAWA_DEPO_ZLOZ` domyślnie 0), przenoszenie blanków do baga, `kup_u_npc`.
- Szkic: pełny serwis w mieście (`SPEC_wyprawa_serwis_1016.md`): wymiana gold, depo, jedzenie, nowy bag, okna, blanki, powrót; w kodzie brak `WYPRAWA_SERWIS`.
  UNKNOWN: NPC od wymiany gold, czy sprzedawca bagów to `gorn`, próg startu (20/20 czy 18), czy odkładać wszystkie runy. Budżet po depo min. 260 gold. Brak pieniędzy = alarm i STOP.

### L9 Dane i uczenie
- Telemetria `logi/telemetria-RRRRMMDD.jsonl` (próbka co ok. 1,2 s: poz, stan, hp, mana, exp, stwory, cel; zdarzenia; rekordy `decyzja` D1/D2/D3/D4, `d3_wynik`, `pvp`), `model_lokalny/` (zbierz, zbiór, trening numpy), dane z dwóch komputerów (`dane_ai/telemetria/`).
- Dziś: 11-16.10 ok. 100 h gry, 178 tys. exp, 1776 exp/h średnio; exp/h po dniach: 404, 569, 1111, 1223, 2095, 2064 (11-16.10) [POTW].
- Narzędzia z 16.10 (poza repo): ekstraktor epizodów zawieszek, analiza przyczyn z mapy, symulator drzwi na istniejącym symulatorze patrolu (`testy/test_patrol_troll.py`), porównanie modeli, pomiar zużycia Haiku.
- Luki: brak pola `cel` w próbkach sprzed 15.10 (44/54 epizodów), brak stałego raportu miesięcznego, brak testów regresji dla L4.

## 4. Rejestr specyfikacji

| Spec | Warstwa | Status | Uwagi |
|---|---|---|---|
| `SPEC_naprawy_1013` | L2/L3 | w większości wdrożony (2b74e6b, b901ad5), spec mówi "nic nie zaimplementowane" | P1c, P1d niezrobione; P1b i P2b wyłączone; sprzeczność z kodem co do domyślnych |
| `SPEC_naprawy_1014` | L2/L3/L8 | wdrożony poza N8(b) i N7 (część) | N11 odłożony |
| `SPEC_ruch_pietra_1014` | L3 | R0, R1a-c wdrożone; R2, R3 nie | brak pomiaru akceptacji |
| `SPEC_patrol_respawn_1015` | L3/L5 | kroki 1-2 (cień) | włączenie po porównaniu; D4 w cieniu |
| `SPEC_czat_spot_1015` | L6/L7 | zatwierdzony, włączony na żywo | odstępstwo: pisze Haiku |
| `SPEC_obrona_pk_1015` | L7 | wdrożony, domyślnie włączony | wym. 5 (log serwera) częściowo |
| `SPEC_walka_pvp_1015` | L7 | wdrożony, wyłączony | próba na żywo nie zrobiona |
| `SPEC_okno_gry_1015` | L0 | wdrożony | brak zrzutu weryfikacyjnego 1175x910 |
| `SPEC_model_lokalny_1015` | L5 | kroki A, B zrobione | D1 bez sygnału, D2 = odległość |
| `SPEC_model_D3_utkniecia_1015` | L4/L5 | zatwierdzony, krok A zrobiony | etykiety Haiku zastąpione symulatorem (decyzja 16.10) |
| `SPEC_modele_decyzyjne_test_1016` | L5 | wyniki zmierzone | zero-shot nie bije klasy większościowej |
| `SPEC_model_steruje_gra_1016` | L4-L6 | szkic, kierunek zaakceptowany 16.10 | sekcje 7.1-7.8 = dane, korekty |
| `SPEC_zasady_zawieszki_1016` | L4 | szkic do poprawek | Q-Z1..Z5 otwarte |
| `SPEC_wyprawa_serwis_1016` | L8 | szkic (inna sesja 12:27) | twierdzi, że drzwi "zamykają się za sobą", co podważa test pasywny; brak planu cofnięcia i współdziałania z D3 |
| `SYSTEM_RETRONIC` (ten) | wszystkie | szkic | nadrzędny |

## 5. Pokrętła i konfiguracja (jedno źródło prawdy)

Dziś trzy miejsca: stałe w `cavebot.py`/`mozg.py`, zakresy i kierunek strojenia w `pokretla.py`, nadpisania w `na_zywo.json` (poza gitem, 28 kluczy).
Skutek: zachowanie zależy od pliku, którego nie ma w repo (np. `WYPRAWA_JEDZENIE` 0 vs kod 1, `WYPRAWA_TYLKO_DEPO` 1 vs 0, `WYPRAWA_BLANKI` 1 vs 0).
Docelowo: (a) `na_zywo.przyklad.json` odzwierciedla produkcję i jest w gicie, (b) test porównujący domyślne z kodu z przykładem i zgłaszający rozjazd, (c) każde nowe pokrętło domyślnie 0 z wpisem w `pokretla.py` ("nie_wyzej"/"nie_nizej").
Nowe pokrętła tego systemu: `MODEL_SERWER`, `D3_REAKCJA` (0 log, 1 cień, 2 wykonuje), `D3_PROG_S`, `D3_ALARM_S`, `LOSOWOSC_*`, `AGENT_TRUDNY`, `WYPRAWA_SERWIS`.

## 6. Znane sprzeczności i długi (skonsolidowane)

1. Specyfikacje 1013/1014 opisują stan "nie wdrożone", a kod już jest; rozbieżne domyślne (`WYPRAWA_DEPO_BLANKI`).
2. Dwie implementacje przejść pięter (`pietra.py`, `wypad.py`); R2 niezrobione. Najwyższe ryzyko dla symulatora i L4.
3. Drzwi: spec serwisu mówi "zamknięte za sobą", dane mówią "zamknięcia rzadkie (3%), nie zależą od czasu"; `_drzwi_hak` ma potencjalną usterkę (flaga `otw`), nieodtworzona w grze.
4. `STRAZNIK_POSTEP=0` i `BLOK_WYJSCIE=0`: istniejące zabezpieczenia nigdy nie włączone, a dokładnie przeciw zawieszkom.
5. N8(b): nieudane dojście z depo daleko od trasy nadal kończy proces zamiast czekać/alarmować.
6. Czerwone testy (wg STAN.md): `ruch_okno`, `grim`, `ogień 1a`, `rdzen_widmo`, `wpadniecie` (zakłada 1 dziurę, w danych 3), `test_cavebot` 5 starych.
7. Stan w gicie != drzewo robocze (niezacommitowane: `mozg.py`, `analityk.py`, 4 specyfikacje z 16.10, `STAN.md`, dane); ostatni commit 15.10 23:02 (1c82733).
8. Czat włączony z modelem wbrew pierwotnej specyfikacji (pula tekstów); akceptacja Karola 15.10 15:40 jest w specyfikacji, ale ryzyko wymaga monitoringu.
9. Różnica 99-104 zawieszek (mój ekstraktor) vs 54 (spec D3, 162 min vs 269-286 min): NIEWYJAŚNIONA.
10. Nadzór tekstowy (Haiku "głowa", obserwator) nie wykrywa braku postępu: dowód 27 min `kontynuuj`.

## 7. Plan jednego systemu: fazy, bramki, cofnięcie

| Faza | Zakres | Bramka wejścia do następnej | Cofnięcie |
|---|---|---|---|
| F0 Higiena | commit bieżącego stanu (z akceptem Karola), `na_zywo.przyklad.json` i test zgodności, naprawa czerwonych testów, rotacja STAN.md, decyzja co do interwałów Haiku | testy zielone, git = drzewo, pokrętła zgodne | git |
| F1 Wykrywacz braku postępu | D3 z progami i eskalacją (D3_REAKCJA 0->1 cień->2), alarm po D3_ALARM_S, odtworzenie drzwi testem na kodzie (czerwony na oryginale), ewentualna poprawka `_drzwi_hak` po ustaleniu w grze, włączenie `STRAZNIK_POSTEP` jako siatka | w cieniu: brak zawieszek > 5 min bez alarmu; brak fałszywych alarmów w >= 20 h gry | pokrętło 0 |
| F2 Symulator i zasady | model świata: graf pięter z kierunkiem, łączniki, drzwi, dziury, ogień; walidacja na 99 epizodach i 62 przejęciach Karola; zasady Z1-Z8 zatwierdzone | symulator odtwarza znane wyjścia (drabina (32506,32270) z9) i błąd czasu mierzony | - (offline) |
| F3 Reakcja wg reguł | reguły z mapy wybierają opcję D3 (cień, potem wykonanie), losowość wśród równorzędnych | minuty zawieszek/h i p99 czasu zawieszki nie gorsze; exp/h nie gorsze przez >= 1 dzień | `D3_REAKCJA=0` |
| F4 Model i agent | model tylko tam, gdzie reguła nie rozstrzyga (dotrenowany na wynikach symulatora i decyzji; GPU tylko po zatrzymaniu gry), agent trudnych przypadków za wykrywaczem; wnioski jako propozycje reguł | przewaga nad regułą na danych niewidzianych, stabilność przy permutacji, kalibracja, VRAM obok gry | `MODEL_SERWER=0`, `AGENT_TRUDNY=0` |
| F5 Serwis w mieście | decyzje z sekcji 8, testy na atrapach, przebieg na żywo z Karolem NPC po NPC, potem cała kolejka | każdy krok zweryfikowany przed/po, brak STOP przy poprawnym przebiegu | `WYPRAWA_SERWIS=0` |
| F6 Dokończenia | próba PvP na żywo, zrzut 1175x910, pomiar akceptacji R0, patrol wg respawnu (włączenie po porównaniu), R2/R3 jeśli nadal potrzebne | wg ich specyfikacji | pokrętła |

## 8. Metryki sukcesu

- exp/h (dziś ok. 2000-2100 dla 15-16.10) i udział okien 30 min poniżej 500 exp/h (11-16.10: 29%, głównie dni sprzed napraw),
- minuty zawieszek na godzinę gry i p99 czasu jednej zawieszki (cel: żadna > 5 min bez alarmu),
- liczba alarmów/h i odsetek fałszywych (alerty: krótko, sam konkret),
- zużycie modeli: wywołań/h (po zmianie interwałów ok. 4-6/h rutyna + zdarzenia [HIP, nie zmierzone]), tokeny i koszt orientacyjny, odsetek timeoutów (cel 0),
- bezpieczeństwo: zero śmierci z przyczyn nawigacyjnych, zero akcji modelu poza zbiorem dozwolonym.

## 9. Decyzje do Karola (skonsolidowane)

1. Akcept tego dokumentu jako nadrzędnego i kolejności F0-F6?
2. Interwały Haiku (`mozg` 600-900 s, `analityk` 900-1200 s, obserwator 600 s): zostawić, czy odłożyć do czasu wykrywacza z F1 (rekomendacja: odłożyć analityka/obserwatora, "głowę" zostawić)?
3. Zasady zawieszki: Q-Z1 (próg 30 s dla zamkniętego obszaru krócej?), Q-Z2 (ile prób przed alarmem, czy alarm zatrzymuje bota), Q-Z3 (lina z plecaka w kieszeni), Q-Z4 (zakres losowości), Q-Z5 (62 przejęcia jako testy).
4. Drzwi: test aktywny w grze (zatrzymany bot, kilka kroków przy drzwiach: czy Use na otwartych je zamyka?) czy odłożyć na rzecz ogólnego wykrywacza?
5. Serwis w mieście: NPC od wymiany gold (pokaż na żywo), czy sprzedawca bagów to `gorn`, próg startu, czy odkładać wszystkie runy.
6. N8(b): nieudane dojście ma czekać/alarmować zamiast kończyć proces?
7. Włączyć `STRAZNIK_POSTEP` i `BLOK_WYJSCIE` (istnieją, wyłączone) jako siatkę w F1?
8. Globalny domyślny model Claude Code (`sonnet` w `~/.claude/settings.json`): zostawić?
9. Commit bieżącego stanu (F0): na Twoje polecenie, grupami, bez pusha.

## 10. UNKNOWN (nie zgadujemy)

Przyczyna zamknięć drzwi (3%); dlaczego 2 poprawne powroty łącznikiem w logu, a jeden 27-minutowy; skuteczność czaszki z Haiku; fałszywe alarmy detektora PK; czy `runa_klik.strzel` działa na gracza;
`GRIM_STOP_S` (P2d) i zrzut przy `ramka_false`; zrzut okna 1175x910; różnica w liczbie zawieszek (99-104 vs 54); aktualny udział zużycia Haiku w Twoim limicie (nie widać w usage).
