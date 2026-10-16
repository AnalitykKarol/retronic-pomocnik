# SPEC: lokalny model decyzyjny steruje grą, Haiku tylko do rozmów — SZKIC do akceptu Karola (16.10)

Cel Karola 16.10: "Haiku zostaje do odpisywania graczom, a ten model kontroluje grę: zawsze gdy coś idzie nie tak, coś się zatnie,
wyciąga wnioski; docelowo gra cały czas". Zgoda Karola 16.10 "dawaj dalej tak": (1) etykiety Haiku dla 54 zawieszek, (2) ogień/ucieczka/leczenie
zostają w kodzie na stałe, (3) najpierw spec, potem kod. Ten dokument = (3), NIE zatwierdzony: kod dopiero po akceptie.
Dowody: `SPEC_modele_decyzyjne_test_1016.md` (sekcje 8-8d). Poprzednie: `SPEC_model_lokalny_1015.md`, `SPEC_model_D3_utkniecia_1015.md`.

## 1. Stan faktyczny (z kodu, 16.10)

`mozg.py` ma DWIE role Haiku (`claude -p --model haiku`, bez narzędzi):
- **Czat** (`SYSTEM_CZAT_SPOT`, klasa `Czat`, odpowiedzi graczom): zostaje przy Haiku (tekst swobodny, reguły językowe, filtry).
- **"Głowa"** (`SYSTEM`, ok. co kilkadziesiąt s; 96% odpowiedzi to `kontynuuj`, mediana 11,6 s, max 46 s): wybiera akcje z listy
  (kontynuuj, pauza_bota, wznow_bota, zmien_trase, sprobuj_loot, idz_do, ignoruj_zdarzenie, notatka, alarm_gm, zakoncz_sesje, napisz_na_czacie)
  oraz reaguje na ZDARZENIA (brak_okna_lootu, nie_doszedl_do_zwlok, punkt_nieosiagalny, odpuszczone_poscigi, obcy_gracz, ucieczka, seria_bledow,
  brak_zabic, brak_jedzenia, bot_zatrzymany). Wynik przechodzi przez `waliduj` i filtry (`filtr_konca`, `filtr_jedzenia`, `filtr_zmiany_trasy`,
  `filtr_bezpieczenstwa`): kod już teraz odrzuca niebezpieczne akcje.
- Odruchy (chód, walka, loot, jedzenie, ucieczka przy niskim HP) robi kod w pętli co 50-300 ms; krok postaci 0,6-0,9 s.

## 2. Architektura docelowa

```
cavebot/mozg (kod: fakty + opcje dopuszczalne)  --stan+pytanie-->  serwer decyzji (osobny proces, model w VRAM)  --P(opcje)-->  kod: próg pewności, filtry, wykonanie
                                                                         ^                                                          |
                                                                         +---- fallback: dzisiejsza reguła / Haiku "głowa" <---------+
Haiku: tylko Czat (odpowiedzi graczom)
```

- **Serwer decyzji**: jeden proces trzyma model w VRAM (ładowanie 7 s, więc nie per decyzja), gniazdo lokalne (Unix socket), JSON in/out,
  timeout 300 ms, przy błędzie/timeoucie bot używa reguły. Mierzone: 2B bf16 33-93 ms (krótki do 700 tokenów), VRAM ok. 3,9 GB (z bazą 2,5 GB razem ok. 6,4 z 8 GB).
- **Kod liczy fakty i opcje dopuszczalne** (ściana, ogień, dziura, HP, A*); model TYLKO wybiera spośród nich (wzorzec testu Marcina na Snake: kod liczy, model wybiera).
- **Granica bezpieczeństwa (decyzja Karola 16.10, stała)**: model NIGDY nie decyduje o ogniu, ucieczce, leczeniu, UH, pauzie PK ani alarmie GM jako wykonawca;
  to kod. Model może tylko PODNIEŚĆ alarm (zatrzymać bota i wezwać człowieka), nie go zdjąć.
- **Próg pewności i kalibracja**: odpowiedź modelu wykonywana tylko przy P >= próg dobranym na naszych danych (temperatura/kalibracja); poniżej = reguła.
- **"Wyciąga wnioski"**: każda decyzja zapisuje rekord (`decyzja` + `*_wynik` po id, jak D1/D2/D3 dziś), z wejściem, opcjami, wyborem, pewnością i wynikiem
  (ruszyliśmy w 20 s? exp/h po decyzji?). Z tego powstają etykiety do dotrenowania i kalibracji (`zbierz_dane.py`, `trenuj.py`); przejęcia Karola = etykiety złote (waga x5).

## 3. Co STWIERDZIŁY POMIARY (blokada przed krokiem 2)

Gotowe modele zero-shot (Mapika 2B, Strands 2B) NIE biją zgadywania klasy większościowej na etykietach D3, są niestabilne przy permutacji opcji i nigdy
nie są pewne (sekcja 8d). Sam model niczego nie "wywnioskuje". Wprowadzenie ich do bota teraz pogorszyłoby grę względem reguły.
Szybkość NIE jest problemem. Brakuje jakości, a ta zależy od (a) bogatszego opisu sytuacji, (b) dobrych etykiet, (c) dotrenowania.

## 4. Etapy i bramki

| Etap | Zakres | Bramka wejścia do następnego |
|---|---|---|
| 0 (dziś, gotowe) | serwer-prototyp w skryptach, pomiar czasu, zbiór 107 epizodów + 54 etykiety Haiku | jakość zero-shot zmierzona: NIE przechodzi |
| 1 Dane | D3_LOG zbiera pełne rekordy (cel, A*, flagi pól, opcje) + wynik; uzupełnić `cel` w próbce telemetrii; etykiety złote z `pomoc-karola.jsonl`; powtórny pomiar na nowych danych | min. kilkadziesiąt pełnych rekordów D3 i 62 przejęcia opisane tym samym schematem |
| 2 Dotrenowanie | LoRA na Mapika 0.8B/2B na naszych etykietach (offline, gra wyłączona, bo trening nie mieści się obok gry na 8 GB) albo własny mały klasyfikator na cechach | na zbiorze, którego model nie widział: lepiej niż reguła i niż klasa większościowa, stabilny przy permutacji, skalibrowany |
| 3 Tryb cienia | serwer liczy obok reguły i tylko loguje (krok C speca D3) przez kilka godzin gry | zgodność/przewaga z logu, brak spadku klatek gry i opóźnień bota |
| 4 D3 na żywo | model wybiera wyjście z zawieszki, próg pewności, fallback do reguły; cofnięcie = pokrętło MODEL_D3=0 | minuty zawieszek/h i exp/h nie gorsze od reguły przez >= 1 dzień |
| 5 Rola "głowy" | zdarzenia operacyjne (brak_okna_lootu, punkt_nieosiagalny, seria_bledow, brak_zabic...) przejmuje model zamiast Haiku; czat zostaje przy Haiku | j.w., per typ zdarzenia osobno |
| 6 Docelowo | model prowadzi więcej decyzji (cel D1, pościg D2, runy D5), kod = siatka bezpieczeństwa | wiele godzin bez regresji |

## 5. Pokrętła, cofnięcie, bezpieczeństwo

Każdy etap za pokrętłem w `pokretla.py` (domyślnie 0, "nie_wyzej" na produkcji): MODEL_SERWER, MODEL_D3, MODEL_GLOWA, MODEL_PROG. Cofnięcie = pokrętło 0, bot wraca do reguły/Haiku bez restartu modelu.
Serwer nie wolno uruchamiać obok sesji bota bez pomiaru VRAM (bufor min. 1 GB). Wagi i venv poza gitem (`~/Games/Retronic/modele-test/`).

## 6. Do decyzji Karola

- Q1 Zatwierdzasz ten szkic jako kierunek (etapy 1-6) i kolejność: najpierw dane i dotrenowanie, dopiero potem cień i sterowanie?
- Q2 Etap 2: czy mogę trenować na GPU przy wyłączonej grze (kiedy możesz ją zatrzymać), czy wolisz CPU/mały klasyfikator na cechach?
- Q3 Etykiety złote: czy mogę zamienić 62 przejęcia z `pomoc-karola.jsonl` na zbiór etykiet w schemacie D3 (odtworzenie sytuacji z telemetrii)?
- Q4 Czy rola "głowy" (etap 5) ma przejść w całości na model, czy zostawić Haiku na zdarzenia "nieznane/dziwne" jako drugą opinię?

## 7. ZMIANA KIERUNKU (decyzja Karola 16.10 ~13:30) i pierwsze dane

Decyzja Karola: Haiku też słabo działał, więc NIE jest nauczycielem. Prawdą mają być prawdziwe dane z gry, dokładne zasady z oczekiwanym rezultatem
i SYMULACJA; model (jeśli w ogóle) uczy się na tym, a nie na opinii innego modelu. Etykiety Haiku z sekcji 8d speca testowego zostają tylko jako ślad (słaby punkt odniesienia).
Pytanie 1 z sekcji 6 zaakceptowane (kierunek i etapy), z tą zmianą etykiet. Pytania 2-4 otwarte.

### 7.1 Co mówią dane (skrypty w `modele-test/skrypty/`: `epizody.py`, `analiza_przyczyn.py`, `ucieczka_z_obszaru.py`, `oracle_wyjscie.py`) [POTW]

Zawieszki 11-16.10 (definicja ze speca D3, bez zamierzonych): 99 epizodów, 286 min.
- Rozmiar obszaru osiągalnego z pozycji (BFS po przechodnich polach tego piętra): **46 epizodów w małych zamkniętych obszarach (12-54 pola) = 187 min (65% czasu)**;
  43 z 46 mają co najmniej jedno wyjście schody/dziura/drabina. Duże obszary: 53 epizody, 99 min.
- Zamknięte obszary: 28 z 46 się skończyło wyjściem (mediana 87 s do opuszczenia obszaru, p90 362 s, max 637 s); pozostałe 18 to urwana seria telemetrii,
  czyli koniec sesji w trakcie zawieszki (sprawdzone: wszystkie 18 urwane < 60 min po starcie, żadne nie stało >= 60 min).
- Najbliższe wyjście z zamkniętego obszaru jest BARDZO blisko: mediana **2 kroki**, max 5 (43/43 w <= 10 krokach). Rzeczywisty czas do wyjścia (19 epizodów z potwierdzonym wyjściem):
  suma 75 min, mediana 173 s; idealny (2 kroki x 0,9 s) ok. 0,6 min. [WNIOSEK ROBOCZY] większość tych minut jest do odzyskania prostą regułą z mapy, bez żadnego modelu.
- Walidacja wyroczni: dla kieszeni (32508,32273,z9) wyrocznia wskazuje (32506,32270) = znana drabina z `STAN.md` (15.10, wyjście z kieszeni). Dla (32496,32267,z8) wskazuje (32496,32268).
- 8 epizodów z oscylacją (N,S,N,S...), 81 z 99 w stanie IDZ, 18 w WYPAD (wyprawa).

### 7.2 Zastrzeżenia (nie ukrywam) [HIP]

- "Idealny czas" to dolna granica: wyrocznia bierze najbliższe wyjście niezależnie od KIERUNKU piętra; część wyjść prowadzi głębiej (np. dziura z8 -> kieszeń z9, z której dopiero drabina
  wraca do z8). Poprawna wyrocznia musi planować po grafie pięter do piętra celu (jak `pietra.py`), nie brać najbliższego pola.
- Flaga "2" mapy (schody/dziury) bywa też polem magicznym lub przedmiotem blokującym; niektóre pola z flagą 2 nie są wyjściem (`dziury_nauczone.json`, ogień).
- Krok 0,6-0,9 s to stała z kodu, nie pomiar na żywo. W symulatorze parametr, do skalibrowania z telemetrii (`ruch_okno`, `pietra_krok`).
- Wynik "wyszedł z obszaru" (7 z 19 bez zmiany piętra) może oznaczać pole z mapy oznaczone nieprzechodnie, a przejściem w praktyce (drzwi, nauczone pola); trzeba sprawdzić.
- 23 epizody nie mają danych "po" (koniec serii).

### 7.3 Nowe etapy (zamiast "etykiety Haiku")

| Etap | Zakres | Wynik / bramka |
|---|---|---|
| 1a Zasady | Spisać dokładnie, co jest poprawną reakcją na zawieszkę: wykrycie zamkniętego obszaru, wybór wyjścia po grafie pięter, czas/koszt, kiedy alarm. Każda zasada z oczekiwanym rezultatem i testem | `SPEC_zasady_zawieszki.md` zaakceptowany przez Karola |
| 1b Symulator | Świat z prawdziwej mapy (`mapa.py`), graf pięter ze schodami/dziurami i kierunkiem, nauczone dziury, ogień, parametry kroku; agent wykonuje opcje D3, symulator liczy czas do wyjścia/celu. Walidacja na 99 epizodach: przewidziany czas wyjścia vs rzeczywisty, trafienie w znane wyjścia | symulator odtwarza znane drabiny; błąd względem rzeczywistego czasu zmierzony |
| 1c Wyrocznia | Optymalna opcja = wynik symulacji (nie opinia modelu); ewentualnie badanie, ile minut zawieszek zdejmuje sama reguła z mapy | liczba minut do odzyskania policzona na historii |
| 2 Reguła w bocie | Jeśli reguła z mapy zdejmuje większość strat: wdrożyć ją w cavebot (kod, nie model), za pokrętłem, najpierw tryb cienia (loguje "co zrobiłbym") | exp/h i minuty zawieszek/h nie gorsze; kolejne kroki jak w sekcji 4 |
| 3+ Model | Dopiero tam, gdzie reguła nie wystarcza (np. niejednoznaczne wyjścia, gracze/moby blokują): model uczony na wynikach symulatora i na prawdziwych wynikach decyzji | wg bramek z sekcji 4 |

### 7.4 KOREKTA (Karol 16.10 ~14:00: "dużo z tych rzeczy już zostało naprawione") [POTW]

Liczby z 7.1 i z rozmowy mieszały okres PRZED i PO naprawach. Wdrożenia: 13.10 (pietra R1b), 14.10 (SPEC naprawy 1014, ruch pięter), 15.10 ~21:47-21:53 (kieszeń po upadku w dziurę,
dojście wyprawy patrolem, DZIURA_PRZY_CELU), bot restartowany 16.10 08:12 z całością. Dzień po dniu (telemetria 11-16.10, `skrypty/straty.py` + ad hoc):

| Dzień | Godz. gry | Zawieszki (min / udział) | % celów zabitych | Odpuszczeń "za ścianą" | exp/h |
|---|---|---|---|---|---|
| 11.10 | 12,6 | 7 / 1,0% | 27% | 16 | 404 |
| 12.10 | 21,0 | 25 / 2,0% | 44% | 177 | 569 |
| 13.10 | 17,9 | 29 / 2,7% | 33% | 451 | 1111 |
| 14.10 | 29,5 | 109 / 6,2% | 83% | 56 | 1223 |
| 15.10 | 32,6 | 75 / 3,8% | 86% | 10 | 2095 |
| 16.10 (po fixach, 08:12-) | 4,4 | 31 / 11,9% (1 zdarzenie = 27,5 min) | 75% | 6 | 2064 |

- Wybór celu (zgubiony/porzucony, odpuszczenia "za ścianą") był naprawiony 14.10: te straty z 7.1/rozmowy NIE są aktualne.
- "luki w pętli" (luki_s w ruch_okno) loguje się dopiero od 14.10: 42% -> 33% -> 26%; wcześniejsze 0% to brak pola, więc średnia 32,9% była myląca. Nadal niewyjaśnione.
- Po naprawach (16.10, 4,4 h, tylko 6 rekordów D3 na żywo) zostają głównie OGONY: 1 zawieszka 1652 s (27,5 min) na z8 (32507,32270): cel patrolu (32478,32290,z8) 29 pól dalej, `cel_droga` None
  (brak drogi po tym piętrze), `inny_punkt` niemożliwy (0 osiągalnych), `przejscie_pietra` możliwe (schody w dół (32498,32270), 8 kroków), `cofnij` możliwe; bot nic nie wybrał, koniec = STOP człowieka
  (`d3_wynik.koniec="stop"`). 4 z 6 rozwiązało się samo w 7-65 s, 1 w 235 s. D3 jest dziś tylko logiem (krok A), nic nie reaguje.
- Poprawka do wyroczni: naiwna wyrocznia (7.1) dała dla tego pola wyjście w 2 krokach (32505,32268), a bot policzył najbliższe prawdziwe przejście na 8 kroków. Wyrocznia z flag mapy zawyża
  bliskość wyjść (flaga 2 to nie zawsze przejście); symulator musi używać reguł z `pietra.py` i listy przejść bota, nie samej flagi.
- Przykład wprost dla symulatora/zasady Z2-Z3: cel na piętrze, do którego z kieszeni nie ma drogi po tym piętrze -> trzeba zejść/wejść po grafie pięter, nie stać.

Wniosek po korekcie: średnia strata od zawieszek po naprawach jest rzędu pojedynczych procent (15.10: 3,8%), ale występują rzadkie długie zdarzenia (27 min), które kosztują dużo
i wymagają człowieka. Wartość reakcji D3 = ochrona ogona i eskalacja (alarm/wyjście), nie skok średniego exp/h. Szacunki "+2,4-5,5%" z rozmowy traktować jako górną granicę
sprzed korekty; dla danych po fixach próba jest za mała (4,4 h, 6 rekordów), by podać liczbę.

### 7.5 Przyczyna zawieszki 27,5 min z 16.10 11:21 (z logu `logi/mozg-20261016-0829.log` + kodu) [POTW dowody, przyczyna HIP]

Dowody z logu: 11:21:20 `[IDZ] patrol m4 (32507,32268)`; 11:21:23 `Drzwi (32505,32270) z8: zamknięte, Use z (32504,32270) (próba 1/3)` (strona zachodnia);
11:21:24 `m4 pusty, zawracam`, `cel m1 (32478,32290) przez lacznik_32506_32270_32502_32270:tam, schody_32498_32270:w_dol, schody_32494_32289:w_gore`;
od 11:21:54 `D3 zawieszka 30 s w (32507,32270,8)`; do 11:48:57 (STOP) tylko: Watchdog "bezczynność 20-60 s, porzucam odłożone zwłoki" co ok. minutę, "wizyta m1/m3/m7 nieudana (limit czasu)",
Haiku "głowa" ok. 30 razy `kontynuuj` ("patrol trolli działa normalnie") po ok. 0,017 USD (razem ok. 0,5 USD), `brak_zabic` -> Haiku `ignoruj_zdarzenie 600 s`, OBSERWATOR co minutę "timeout 60 s".
To samo zdarzenie drzwi wcześniej: 09:54:49, 09:55:01, 10:08:05, 10:08:30, 10:08:39 (zawsze "zamknięte"), czyli drzwi (32505,32270) są ZAMKNIĘTE przy każdym podejściu (zamykają się po przejściu).
Mapa traktuje (32505,32270) jako ścianę (`pola_oznaczone_jako_sciana` w łączniku), dlatego A* nie widzi drogi (cel_droga None, inny_punkt 0 osiągalnych).

Hipoteza przyczyny (kod `cavebot.py::_drzwi_hak`, ~l. 3401-3470): obsługa drzwi startuje tylko przy odległości < 2 od drzwi w osi. Bot po przejściu na wschód ma `st["otw"]=True` (staliśmy na kafelku drzwi),
a ta flaga resetuje się tylko po DRZWI_PROB nieudanych Use. Przy powrocie z (32507,32270) (odległość 2) gałąź `odl >= 2` z `not st["otw"]` jest wyłączona, więc bot nie podchodzi krokami do drzwi, tylko idzie klikiem
za ZAMKNIĘTE drzwi (komentarz w kodzie: "klik za zamknięte drzwi nie prowadzi nigdzie"), stoi, a nic go z tego nie wyprowadza. [HIP, do odtworzenia testem]

Wnioski dla projektu:
- To DOKŁADNIE ten typ sytuacji, w którym dzisiejszy nadzorca (Haiku "głowa", `kontynuuj` co ok. 50 s) NIE widzi problemu: dostaje opis "patrol działa", a brak postępu (30 s, 5 min, 27 min) go nie zmienia.
  Potrzebny jest wykrywacz braku postępu z twardym progiem, który eskaluje (D3 reakcja, potem alarm), niezależnie od opinii modelu tekstowego.
- Model świata symulatora MUSI zawierać: drzwi zamykające się po przejściu (stan drzwi), łączniki ręczne z listy `laczniki`, pola "ściana w mapie" będące drzwiami.
- Kandydat na test regresji: bot na (32507,32270,z8) z `drzwi_stan["otw"]=True` i drzwiami zamkniętymi -> ma podejść do (32506,32270) i użyć drzwi.
- Opcja "cofnij" w rekordzie D3 miała cel (32502,32270), czyli drugi koniec łącznika, więc opcje już znały wyjście; zabrakło tylko wykonawcy (D3 dziś tylko loguje).

### 7.6 AKTUALIZACJA Claude Code i Haiku 5.5 (16.10 ~14:30) [POTW pomiar]

Claude Code zaktualizowany 2.1.289 -> 2.1.300 (`mise upgrade claude`; poprzednia wersja usunięta przez mise, powrót: `mise install claude@2.1.289`).
Alias `--model haiku` w CLI 2.1.300 wskazuje już na `claude-haiku-5-5` (w 2.1.289 na `claude-haiku-4-5-20251001`), więc bot dostaje nowy model bez zmiany kodu.
Ten sam test co przed aktualizacją (prompt systemowy bota, prosty stan, `claude -p --model haiku`, 3 wywołania):
| | CLI 2.1.289 / Haiku 4.5 | CLI 2.1.300 / Haiku 5.5 |
|---|---|---|
| tokeny wejścia (cache zapis + odczyt) | ok. 5 000 (zapis w 3 z 4 prób) | ok. 6 700 (2 182 zapis + 4 479 odczyt, za każdym razem) |
| tokeny wyjścia / "myślenie" | 300-560 / 240-510 | 57-66 / 0 |
| koszt orientacyjny jednego wywołania | 0,011-0,013 USD (logi bota średnio 0,017) | **0,0005 USD** |
| czas | 3,8-6,8 s | **1,4-1,6 s** |
=> ok. 25x taniej (34x względem średniej z logów bota) i ok. 4x szybciej na tym samym wejściu. Pomiar na prostym stanie, nie na prawdziwych stanach bota.
Skutek dla projektu: argument kosztowy przeciw Haiku jako nadzorcy z sekcji 7.5 znika; argument jakościowy zostaje (27 min `kontynuuj` nie zależało od ceny), więc wykrywacz braku postępu z twardym progiem nadal jest potrzebny.

### 7.7 Symulacja zawieszki przy drzwiach (16.10 ~15:00) [POTW sym., HIP rzeczywistość]

Skrypty (poza repo, `~/Games/Retronic/modele-test/skrypty/`): `odtworz_drzwi.py`, `odtworz_drzwi_stat.py`. Używają istniejącego symulatora patrolu z `testy/test_patrol_troll.py`
(prawdziwa mapa, `miejsca_troll.json`) i PRAWDZIWEGO kodu `Cavebot._drzwi_hak`; świat rozszerzony o drzwi (32505,32270,8) zamykające się po przejściu. Repo bota niezmienione.
- Scenariusz: bot idzie zachodnią stroną na wschód do m4 (32507,32268), potem cel m1 (32478,32290) przez łącznik z powrotem.
- ORYGINAŁ, 40 powtórzeń (różne ziarna), doszło na wschód 31: **30 zawieszek, 1 powrót (307 s sym.)**.
- Z obejściem (zerowanie flagi `otw` po zejściu z kafelka drzwi, nakładka w skrypcie, nie zmiana pliku): **0 zawieszek, 31 powrotów w ok. 3 s**.
- Kontrola jednej zmiennej: ten sam kod i ziarno, różnica tylko flaga `otw` (stoi 766 s sym. vs wychodzi w 4 s z Use z (32506,32270)).
Wniosek: mechanizm (przeterminowana flaga `otw` + zamknięte drzwi) WYSTARCZA do zawieszki przy powrocie ze wschodniego pokoju. [POTW w symulacji]

ZASTRZEŻENIE (log 16.10 nie potwierdza 97%): w prawdziwej grze bot wracał łącznikiem na zachód co najmniej dwa razy poprawnie (09:14:01 m4 #3 -> cel przez lacznik..., 10:45:18 m4 #12 -> m1 przez lacznik w 141 s),
a stanął raz (11:21). Symulator zakłada, że drzwi zamykają się natychmiast za graczem; w grze nie wiadomo, kiedy i czy zawsze. Różnica: w udanych przypadkach bot był "na miejscu" 5-14 s, w nieudanym
zawrócił po ok. 1 s od Use. Niewyjaśniony warunek (czas zamknięcia drzwi? inna ścieżka kodu po walce?). Poprawka bez tej wiedzy może być niepotrzebna lub niepełna; potrzebny pomiar zachowania drzwi w grze.
Test regresji do dodania do repo dopiero po zatwierdzeniu poprawki (obecnie czerwony na oryginale).

### 7.8 KOREKTA 7.7: test pasywny drzwi obalił założenie symulatora (16.10 ~15:30) [POTW]

Skrypt `modele-test/skrypty/drzwi_czas.py` (telemetria `probka` + logi bota 14-16.10; bot chodził w tle, nie sterowałem postacią): ok. 290 przejść przez drzwi (32505,32270,8).
Use ("zamknięte") było potrzebne przy 8 z nich (ok. 3%), reszta przeszła bez Use także po przerwach rzędu godzin (do 13 788 s). Odstępy przy Use: 3, 4, 26, 634, 772, 1258, 2162, 2456 s,
czyli brak zależności od czasu od poprzedniego przejścia. WNIOSEK: drzwi NIE zamykają się same po przejściu; założenie z 7.7 ("zamykają się natychmiast za graczem") jest FAŁSZYWE,
więc wynik symulatora (30/31 zawieszek) opisuje mechanizm, ale nie jego częstość w grze. W grze zawieszka wymaga rzadkiego połączenia: drzwi zamknięte po stronie wschodniej + flaga `otw` z poprzedniego przejścia.
Skąd zamknięcia (3%): nieznane [HIP]. Kandydat: heurystyka `_drzwi_hak` (bez ruchu 1 s = "zamknięte", wtedy Use) mogłaby ZAMYKAĆ otwarte drzwi, gdy bot stoi z innego powodu
(np. czeka na loot/mob); w Tibii Use na otwartych drzwiach może je zamknąć. Do sprawdzenia testem na żywo przy zatrzymanym bocie.
Przy okazji (bot od ok. 12:59 na Haiku 5.5): patrz wynik liczenia w odpowiedzi.

## 8. Haiku jako nadzorca w sytuacjach, których skrypt nie rozumie (propozycja Karola 16.10 ~15:30) — SZKIC do akceptu

Zmiana kierunku względem 7: Haiku nie jest "nauczycielem" ani sterownikiem na zegarze, tylko **nadzorcą wołanym na zdarzenia**,
w których skrypt nie wie, co robić. Powód z danych: 1941 z 2035 odpowiedzi to `kontynuuj` (95%), a w zawieszce 16.10 11:21-11:49
Haiku trzy razy odpowiedział `kontynuuj`, bo zdarzenia "zawieszka" nie dostawał.

### 8.1 Już wdrożone w kodzie (16.10, bez restartu bota)
Tętno zegarowe rzadkie: `mozg.py CO_ILE["hybryda"]` 30-60 s -> 600-900 s; obserwator `OBS_CYKL_S` 60 -> 600 s; analityk pościgu
`CO_ILE` 180-300 -> 900-1200 s. Zdarzenia (gracz, czat, loot) dalej przyspieszają pytanie (`przyspiesz`, `czas_na_zdarzenie`).
Szacunek: ok. 150 -> ok. 15 wywołań/h. Testy: test_mozg 246/246, test_obserwator, test_analityk_poscigu zielone. Cofnięcie: trzy stałe.

### 8.2 Momenty, w których wołamy Haiku
| moment | stan dziś | rola Haiku |
|---|---|---|
| zawieszka (brak ruchu >= 30-45 s poza walką, `d3_zawieszka.py`) | wpis w logu, model nie wie | rozmowa wieloetapowa (8.3) |
| nietypowy ekran (okno NPC, dialog, logowanie, śmierć, rozłączenie) | brak reakcji | rozpoznanie ze zrzutu, jedna akcja (zamknij, alarm) |
| gracz zaczepia/atakuje | czat i PK osobno | decyzja walcz/uciekaj/odpisz z kontekstem |
| GM/test ("czy jesteś botem") | `alarm_gm` | bez zmian |
| problem z lootem/plecakiem | `sprobuj_loot` (51 razy) | bez zmian |
| powtarzający się błąd (np. 3x ta sama pętla `[DZIURA]`) | log | jedna notatka + `ignoruj_zdarzenie` |

### 8.3 Rozmowa o zawieszce (nowe zdarzenie `zawieszka`)
- Start: pozycja nie zmienia się >= HAIKU_ZAWIESZKA_S = **10 s** (decyzja Karola 16.10; osobne od D3_PROG_S = 30 s, które zostaje dla zbioru D3), brak walki, brak PAUZA/PRZERWA/GRACZ. Postać staje (cavebot wstrzymany jak `pauza_bota`).
- Jedna rozmowa na zawieszkę, max 8 kroków i budżet (np. $0,02). Krok: stan (pozycja, zrzut, dziury i drzwi w promieniu 10, ostatnie linie logu,
  wynik poprzedniej akcji) -> jedna akcja z listy: `idz_do` (max 10 pól), `otworz_drzwi` (NOWA: Use z pola obok, jak `_drzwi_hak`),
  `zmien_trase`, `sprobuj_loot`, `pauza_bota`, `alarm_gm`. Bot wykonuje, weryfikuje ruch i zwraca wynik.
- Wyjście: pozycja poza kotwicą o >= 3 pola albo exp rośnie -> koniec rozmowy, wznowienie bota. Limit kroków bez poprawy -> alarm + STOP,
  nie ciche stanie. **Bez `zakoncz_sesje`** w tej rozmowie.
- Bezpieczeństwo: akcje te same co dziś (filtry `filtr_zmiany_trasy`, limity `idz_do`), nowa tylko `otworz_drzwi`; pokrętło `HAIKU_ZAWIESZKI=0` domyślnie.

### 8.4 Dane pod lokalny model
Cały przebieg (stan, odpowiedź, wynik, czy odblokowało) -> zbiór D3 (`d3_zawieszka.py`). Z tego uczy się lokalny model: najpierw Haiku, z czasem
model przejmuje powtarzalne przypadki; Haiku zostaje przy nowych. Bez zmiany decyzji Karola, że to prawda z gry (mapa, `pietra.py`) jest wzorcem.

### 8.5 Kolejność i bramki
1. Zdarzenie `zawieszka` + rozmowa + `otworz_drzwi`, testy na atrapach (drzwi 2 pola od, `otw`=True, jak 16.10 11:21), potem na żywo przy Karolu.
2. Nietypowy ekran (rozpoznanie ze zrzutu).
3. Powtarzające się błędy -> notatka + uciszenie.
Każdy etap za pokrętłem, włączenie po udanym przebiegu na żywo.

### 8.6 Decyzje Karola (16.10 ~15:45)
- Próg zawieszki: **10 s**. Ryzyko: 10 s bez ruchu zdarza się też zwyczajnie (loot, jedzenie, czekanie na mob, UH), więc warunek "poza walką, lootem, jedzeniem, UH i pauzą"
  musi być ścisły, a rozmowa ma twardy limit na godzinę (np. 6), inaczej wróci zalew wywołań. Do zmierzenia na telemetrii przed włączeniem: ile 10-sekundowych postojów
  w 70 h to prawdziwe zawieszki (wg `d3_zawieszka.py`: 54 epizody / 162 min).
- `otworz_drzwi`: **dla wszystkich drzwi**, nie tylko z `drzwi_jaskinia.json` (Haiku wskazuje pole drzwi ze zrzutu; Use tylko z pola obok, jak `_drzwi_hak`).
- Nadal do ustalenia: budżet i limit kroków rozmowy (8 / $0,02).
