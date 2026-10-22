# Zgon kutangena 21.10 ok. 19:11: wyprawa do depo przez dziurę (32356,32122,z8) w Thais północ

Status: zamknięte w kodzie (dziura oznaczona, plan `thais_pn` wyłączony). Odzyskanie rzeczy ze zwłok: ręcznie, Karol.

## Zlecenie
Karol: „cofnij kutangena do Thais, nie ma jak wrócić” + „jak dotrze to go wyloguj”. Kutangen (lvl 10) stał w jaskini `thais_pn_z8`
na (32344,32133,z8), 4/70 many, bez jedzenia, bez profesji (brak działającego `exura`).

## Przebieg
1. `wroc.sh` anulowane („poza planami troll, thais_kanaly”): dopisałem plan `thais_pn` (`wypad.PLANY`, `wyprawa.BAZY`) i wygenerowałem
   trasy `thais_pn_do_miasta` / `thais_pn_z_miasta` (`generuj_trase_miasta.py`, wariant `thais_pn`).
2. Pierwsza trasa: lina pod otworem (32339,32135,z8). 4 próby, bez skutku, ALARM, STOP.
3. Druga trasa: „schody w górę” wybrane **wyłącznie z flag mapy** (flaga 2 na z8 + chodliwe pole nad nim na z7) = (32356,32122,z8).
   Nikt tamtędy nie przechodził, nie było wpisu w `przejscia_nauczone.json`. Nie sprawdziłem tego na zrzucie ani nie zapytałem Karola.
4. 19:09:22 start wyprawy, 19:09:34 postać dochodzi do (32356,32123,z8). 19:09:37 Use (32356,32123): bez zmiany piętra.
   19:09:39 krok na (32356,32122,z8): **upadek na (32356,32122,z9)** = dziura w dół.
5. Na z9 stały trzy Poison Spidery (z8 omija je strefą zakazaną, z9 nie). Zatrucie, HP 52% → 33% → 14% → 0 w ok. 1,5 min, mimo UCIECZKI.
   Brak many i jedzenia = brak leczenia. Zgon ok. 19:11, okolice (32356,32123,z9).

## Przyczyna
Generator nie odróżnia schodów w górę od dziury w dół (flaga 2 jest taka sama; `wypad.py` sam to zaznacza). Wyprawę „do depo” skierowałem
na niesprawdzone przejście, a próbę wykonał bot na żywej postaci w jaskini z trucizną. To błąd procesu, nie bota.

## Co zrobiono (21.10 wieczór)
- `trasy/dziury_nauczone.json`: dodane **[32356,32122,8]** (bot traktuje jako ścianę we wszystkich drogach A* i krokach, pokrętło
  `DZIURY_NAUCZONE`=1). Pole (32356,32123,z8) NIE jest dziurą (Use bez efektu), tylko stoi się na nim obok dziury.
- `wypad.PLANY` i `wyprawa.BAZY`: `thais_pn` usunięty. Z jaskini z8 `wybierz_plan` daje teraz `None`, czyli wyprawa się anuluje, zamiast zgadywać.
- Błędne trasy przeniesione do `dane_tibia/ruch/bledne_trasy_thais_pn_1021/` (nie do `trasy/`, nie do użytku).
- `testy/test_wielopietrowa.py`: sprawdza brak planu `thais_pn` i obecność dziury w pliku.
- Uwaga: wariant `thais_pn` w `generuj_trase_miasta.py` nadal istnieje i powtórzyłby ten błąd. Nie uruchamiać `--zapisz` dla niego bez prawdziwego,
  przeszłego przejścia w górę.
- `mapy.json` `thais_pn_z8` ma w opisie „żółte pola nad jaskinią (np. 32345,32146) to schody W GÓRĘ na z6”. To też tylko z mapy, niesprawdzone.

## Wyjście z jaskini z8: nadal NIEZNANE
Znane i sprawdzone: wejście przez zasypaną dziurę (32347,32123,z7) łopatą (spada się w dół). W górę: brak potwierdzonego przejścia.
Do ustalenia: Karol pokazuje/przechodzi je ręcznie raz (postacią z pełnym HP), wpis ląduje w `przejscia_nauczone.json`, dopiero wtedy plan powrotu.

## Odzyskanie rzeczy (hajs)
Zwłoki leżą na **z9 przy (32356,32123)**, wśród 3 Poison Spiderów (respawn). Rzeczy z ekwipunku i plecaka zostają w zwłokach przez ograniczony czas.
Odzysk tylko ręcznie, nowa postać z antidote/jedzeniem, nie botem, nie z zadania w tle. Dojście na z9: przez tę samą dziurę (32356,32122,z8) albo drugą drogą.

## Lekcje
- Nowe przejście pięter bez wpisu w `przejscia_nauczone.json` = niesprawdzone. Nie wysyłać na nie żywej postaci; zrzut ekranu albo pytanie Karola.
- Wyprawa „do depo” z postaci bez many i jedzenia w jaskini z trucizną to zagrożenie życia (zasada życia postaci w CLAUDE.md).

## Co wypadło (oględziny po zalogowaniu, 21.10 ok. 19:55, zrzut ekwipunku przed/po)
Logowanie: okno „Connection Error 10060” po zgonie, Ok i Ok na liście postaci kliknięte ręcznie (jednorazowy skrypt na `PortZywy.klik`, każdy klik po
porównaniu zrzutu); `zaloguj.sh` blokuje zgon i okno błędu. Postać wstała w świątyni Thais: lvl 10, HP 195/195, mana 70/70, cap 256 (przed zgonem 74).
- ZGINĘŁO (zostało w zwłokach na z9 przy (32356,32123)): **broń** z lewej ręki (narzędzie z zakrzywionym ostrzem na drzewcu, jak kosa/sierp) oraz **plecak razem z całą zawartością**
  (cap 74 → 256 = ok. 180 oz rzeczy: zapasy, loot, łopata, lina). W slocie plecaka leży teraz mała torba (sack).
- ZOSTAŁO na postaci: hełm, zbroja, spodnie, buty, tarcza. Naszyjnik i pierścień były puste już wcześniej.
