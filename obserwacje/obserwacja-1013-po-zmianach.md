# Obserwacja bota Retronic po zmianach (UH_W_WALCE=1, LOOT_DYNAMICZNY=1, ucieczka 30%)

Start obserwacji: 12:36 (restart bota 12:35:17, log logi/mozg-20261013-1235.log). Tylko odczyt.
Wyniki przed zmianami (logi 1139 i 1209): zebrane zwłoki ok. 36-46%, loot w walce 6/6 przerwany, dobijanie 38-100%, exp 1600-2400/h, mana marnowana.

R0 12:36 | HP 200 (100%) start, 12:37 HP 171 (85%) | mana 24 (12:37:30) | exp 17640 (12:35:30) -> 17660 (12:37:30), +20/2 min, tempo ok. ~600/h (krótka próba) | wnioski:
  - 12:35:53 UH 'robię runę' w PATROLU (rozglądam się na m1, mana 108, HP 100%), nie w walce: stara ścieżka, nie UH_W_WALCE. Działa poprawnie (wynik ok 12:35:58).
  - 12:37:20-12:37:56 walka z trollami i orkiem: zmiany celu ("Troll stoi obok, ... 2 pól dalej") 4x w 3 min; dobicie Troll 12% (odl 7) zostawione dla Orca (12:37:35).
  - 12:37:37 exura przy HP 79% i mana 25: leczenie działa, UH nie odpala (mana < 120, poprawnie).
R1 12:41 | HP 165 (82%, 12:40:30) | mana 29 (nie dobija do 120, UH w walce nieodpalone, poprawnie) | exp 17680 (12:40:30, +40 od 12:35:30 w 5 min, ~480/h; tempo słabe, dobijanie) | wnioski:
  - Loot DZIAŁA w walce: 12:38:49-12:38:54 zwłoki obok zebrane (gold coin +10), 12:40:43-12:40:49 zwłoki obok zebrane przy HP 81% (+1). "Loot w walce: obsłużone (ok)" 2x.
  - Loot odłożony 4x ("1 pól od nas, najpierw walka"), zabite 5 (Troll 12:38:47, Orc 12:40:39/42, Troll 12:41:04). Kolejka odłożona nie gubi zwłok.
  - 12:41:08 "Loot w walce przerwany: brak_okna" (zwłoki 32498,32273): czyli przerwy nadal się zdarzają, ale po jednej próbie.
  - OBSERWATOR [problem] 12:40:39: dobijanie 29% (2 z 7 epizodów), "zniknął z widoku żywy", ok. 40 exp straconych. Powód problemu nie jest nowy, zmiana LOOT_DYNAMICZNY go nie dotyczy.
  - Brak UCIEKŁ/zniknął-w-trakcie-ucieczki w logu, brak tracebacków, brak błędów UH.
R2 12:44 | HP 180 (90%, 12:43:31) | mana 59 (12:43:31, rośnie; poniżej 120, UH w walce nie odpala, poprawnie) | exp 17810 (12:43:31, +130 od 12:40:30 w 3 min, ~2600/h chwilowo; od startu +170 w 8 min, ~1270/h) | wnioski:
  - Zabite 7 (od startu), Loot ok 2 (wskaźnik ok. 30% z wyłączeniem; tzw. "Loot w walce" obsłużone 2x, 12:38:54, 12:40:49, plus szybki 12:42:52 "Loot szybki" ok).
  - Problemy zebrania: brak_okna 4x (np. 12:41:08, 12:42:14, 12:43:06), cel_daleko 1x (12:41:50), "Loot w walce przerwany" 3x. Zwłoki z 12:42:14 i 12:43:06 zwolnione po jednej próbie (zgodnie z kodem: "jedna próba po walce").
  - Brak powtórek na tych samych zwłokach wykrytych w logu, ale 12:43:06 "Zdarzenie brak_okna_lootu: pytam model" -> model dostaje zdarzenie zamiast automatycznej obsługi.
  - OBSERWATOR [uwaga] 12:42:41: dobijanie 71% (5/7), tuż nad progiem 70%; OBSERWATOR [problem] 12:41:41: 50% (4/8), ok. 115 exp. Dobijanie poprawiło się, ale zmiany celu nadal główny powód.
  - Ucieczka bota (próg 30%) nieuruchomiona (HP min. 82%); "Troll ucieka przy ~25%" x2 (12:41:48, 12:41:50) to ucieczka trolla, nie bota.
ZDARZENIE 12:43:10: bot zatrzymany plikiem STOP ("Zatrzymano (plik STOP)", log 1235). Nie ja, nie dotykałem. Ponowny start 12:44:14 (log logi/mozg-20261013-1244.log), ta sama konfiguracja: UH_W_WALCE=1 (z na_zywo.json), próg ucieczki 30%, LOOT_DYNAMICZNY nie jest w na_zywo.json, więc działa domyślne 1 z cavebot.py:149. Przerwa ok. 1 min. Liczby poniżej: suma obu runów.
R3 12:46 | HP 195 (97%, 12:46:31) | mana 88 (12:46:31; rośnie, nadal <120, UH w walce nie odpala) | exp 17875 (12:46:31, od startu 12:35:30 +235 w 11 min, ~1280/h) | wnioski:
  - Zabite od startu: 11 (obie sesje). Loot ok: 5, "brak_okna": 10, "Loot w walce przerwany": 5, "Loot odłożony": 7, cel_daleko 1. Wskaźnik zebranych zwłok ok. 5/11 = 45%, poniżej celu 70%.
  - Na nowym runie (12:44-12:46): zabite 4 (Orc 12:44:44, Troll 12:45:21, 12:46:05, 12:46:37), Loot ok 2 (12:44:52, 12:46:48/53), brak_okna 3x na tym samym miejscu (zwłoki 32480,32293,8 i 32482,32293 oraz 32491,32290): NOWA powtórka brak_okna na tej samej pozycji (12:46:43, 12:46:48, 12:46:54 "ponawiam loot raz").
  - 12:46:48 "Zdarzenie brak_okna_lootu: pytam model" + 12:46:54 model: "ponawiam loot raz" -> zwłoki zebrane 12:46:53 (Loot ok). Pętla jednej powtórki działa.
  - OBSERWATOR [ok] 12:45:18 i 12:46:24: dobijanie 100% (3/3 w oknie 5 min). Dobrze, ale próba mała.
  - Brak UH w walce w tym czasie (mana 60-90 < 120), zgodnie z regułą. Brak ucieczki bota, HP min. 90%.
R4 12:49 | HP 195 (97%, 12:49:31) | mana 88 (rośnie, <120, brak UH w walce, poprawnie) | exp 17915 (12:49:31, +40 od 12:46:31 w 3 min, ~800/h chwilowo; od startu +275 w 14 min, ~1180/h) | wnioski:
  - 12:47:06 zwłoki (32491,32290) "bez okna (2x): wstrzymane do końca walki, porzucone": drugie brak_okna porzuca zwłoki (zgodnie z kodem), ale to jest strata łupu i nie powtórka z dynamicznego lootu.
  - 12:46:54 model: "ponawiam loot raz" -> zebrane (12:46:53 Loot ok). Powtórka na tym samym polu w jednej rundzie: 1 raz, poprawnie.
  - 12:47:54 Wypad (zapas, depo, zapas 0, blanki 9, zloto 192): start poprawny. 12:48:12 błąd "dziura_bez_zmiany_pietra" (1 próba, krok), wypad idzie dalej.
  - OBSERWATOR [ok] 12:48:25 i 12:49:26: dobijanie 100% (5 zabić / 5 min bez porzucenia). Najlepsza seria od początku, ale wycinek to 1 pętla.
  - Od restartu 12:44: brak UH start, brak ucieczki bota (HP min 90%), brak tracebacków.
R5 12:51 | HP 195 (97%) | mana 88 (12:51:31), 97 (12:52:32) | exp 17915 (12:50:31-12:51:31 bez zmian; bot ZATRZYMANY) | wnioski:
  - 12:50:50 "Wyprawa: DEPO osiągnięte, koniec wyprawy, zatrzymuję bota" -> zapisany plik STOP, bot zatrzymany. Obserwacja walki przerwana (koniec danych do polowania). Nie ruszałem STOP ani procesu bota.
  - STOP z 12:43:10 (bez wyprawy w logu) też zatrzymał bota; ktoś wznowił o 12:44:14. Przyczyna 12:43:10 nieznana z logu.

WERDYKT (okno 12:35-12:51, 12 zabić, ok. 15 min polowania)
Czy idzie w dobrą stronę: CZĘŚCIOWO.
- Zebrane zwłoki: "Loot: ok" 6 / "zabity na" 12 = 50% (przed: 36-46%). Cel >70% nieosiągnięty. Loot w walce działa (12:38:54, 12:40:49, 12:42:57, 12:46:53).
- brak_okna 11x, powtórki na tym samym miejscu (12:46:43-54, zwłoki 32480,32293,8; ponowienie raz i zebrane). 12:47:06 zwłoki 32491,32290 porzucone po 2 próbach (łup stracony).
- Dobijanie (OBSERWATOR): 25%, 40%, 29%, 50%, 71% (12:38-12:42), potem 100% (12:45, 12:46, 12:48, 12:50). Przed: 38-100%. Trolle uciekły 2x przy 22-28% (12:41:48, 12:41:50), zniknęły z widoku 3x.
- Exp: 17640 (12:35:30) -> 17915 (12:50:31), ok. +275 w ok. 15 min, ok. 1100/h, przy 12 zabiciach i wyprawie. Przed: 1600-2400/h. Próba mała, ale poniżej bazy.
- UH w walce: 0 odpaleń w walce. Mana w walce 9-104 (poniżej 120 = max-5), więc UH_W_WALCE nie zadziałał. Mana nie była marnowana w tym oknie (nie dobijała do 125). Brak regresu, brak dowodu na efekt. Exura 6x przy HP <80% (mana 25-60), leczenie działa.
- Ucieczka 30% nie padła (HP min 82%, próbki 165/200). Brak Traceback, "[UH] błąd", strike'ów. Jedna UH runa (12:35:53) w patrolu, nie w walce, OK.
- Problemy z dowodem: 12:43:10 STOP (przyczyna nieznana), 12:50:50 STOP po wyprawie (bot zatrzymany, nie wraca sam).
Rekomendacja:
  1. ZOSTAWIĆ UH_W_WALCE=1 (brak regresu; nie miał okazji zadziałać, dane za krótkie, żeby go ocenić).
  2. ZOSTAWIĆ LOOT_DYNAMICZNY (domyślnie 1 w cavebot.py:149; loot w walce działa), ale poprawić powtórki brak_okna (11x) i porzucanie po 2 próbach.
  3. Usprawnienia: (a) po wyprawie bot kończy się STOP-em (12:50:50), decyzja czy to zamierzone; (b) zmiana celu na świeżego 5x (12:36:33, 12:37:37, 12:37:43, 12:37:53, 12:46) koszt dobijania; (c) ucieczki trolli przy 22-28% vs próg 26% (12:41:48); (d) pętla brak_okna na tym samym polu (12:46:43-54).
  4. Do oceny ponownie po 30-60 min polowania bez wyprawy (UH w walce, mana >=120 musi wystąpić).
KOREKTA 12:53: bot NIE został na stałe zatrzymany. Plik STOP zniknął, a o 12:52:46 wystartował nowy run (logi/mozg-20261013-1252.log, ta sama konfiguracja, dojście depo_troll_cave -> troll_cave). Start z depo, obserwacja trwa dalej od 12:53 (punkt "bot zatrzymany" w R5 i w werdykcie nieaktualny).
ZDARZENIA 12:52-12:55: run 1252 (start 12:52:46) przerwał dojście do troll_cave ("Dojście nieukończone" 12:55:18) i został zastąpiony runem 1255 (start ok. 12:55:1x, ta sama konfiguracja, potwory Troll,Orc,Orc Spear, trasa patrol:troll). Nie ja. Sampler (probki.py, timeout 1900 s) skończył się ok. 12:55, próbki kończą się 12:52:32.
R6 12:56 | HP 199 (99%, 12:52:32, ostatnia próbka) | mana 97 (12:52:32) | exp 17915 (12:52:32; od startu 12:35:30 +275) | wnioski:
  - Od 12:52 brak zabić w logu 1252 (run krótki). Run 1255: 12:55:31 walka z trollem (odl 5), 12:55:34 droga zablokowana, bicie blokującego. Kolejne linie patrz następna runda.
  - Pełna pętla start/stop: 1235 (STOP 12:43:10), 1244 (wznowiony 12:44:14), STOP po wyprawie 12:50:50, 1252 (12:52:46), 1255 (12:55). W 12 min 5 startów: duże ryzyko dla ciągłości obserwacji i dla dobijania (każdy start wraca z depo/dojścia).
R7 12:58 | HP 100% (12:56-12:58, wg OBSERWATORA) | mana ok. (brak próbki po 12:52:32, sampler zakończony; wg logu brak alarmu) | exp: brak próbki, do odczytu z logu | wnioski (run 1255, start 12:55):
  - 12:56:26 - 12:58:09: 3 zabicia trolli (12:57:06, 12:57:32, 12:58:09), Loot ok 12:57:14, brak_okna 12:57:38 -> "Loot w walce przerwany: brak_okna" 12:57:42, model: "obok stoją jeszcze trolle, loot poczeka na walkę". Zgodne z LOOT_DYNAMICZNY (wstrzymane do końca walki).
  - OBSERWATOR dobijanie 25% (12:57:27) przy 4 epizodach, za mało danych na ocenę (wymaga 6).
  - Brak UH w walce (mana < 120), brak ucieczki, brak Traceback.
R8 13:04 (koniec obserwacji) | HP: min. gracza 82% (wg decyzji modelu), brak ucieczki 30% | mana 102 (13:03:04) | exp: brak próbek po 12:52:32 (sampler zakończony), brak odczytu tempa po 12:52 | wnioski:
  - Run 1255 (od 12:55) żyje, pid 3101256, od 12:58 bez przerw. Zabite w runie 1255: 7 (trolle i orc), Loot ok 13/19 od startu (ok. 68%, blisko celu 70%), brak_okna 20, przerwane 6.
  - 12:59:10 model: "loot na tych zwłokach udał się po ponowieniu, brak okna wraca często przy trollach". Powtórka działa, ale nadal dużo brak_okna.
  - 13:03:04 UH "robię runę" w IDZ (patrol m6), mana 102 >= 100, stara ścieżka, nie walka. wynik ok 13:03:08. UH w walce nadal 0.
  - OBSERWATOR [problem] 12:58:28, 12:59:29, 13:00:31: dobijanie 50-57% przy 6-7 epizodach, ok. 60 exp straconych na zniknięcie żywego moba z widoku.
  - Troll ucieka przy ~26% (zaobserwowano 30% i 12%): 13:00:37, 13:00:42.
