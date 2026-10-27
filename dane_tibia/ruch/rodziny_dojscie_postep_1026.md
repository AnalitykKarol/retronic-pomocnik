# Postęp: dojście z dowolnego piętra w obrębie jaskini (be-dev, 26.10 od ~11:30)
Wznowienie ma zacząć OD TEGO PLIKU. Zakazy: nie edytować żywych spoty.py/nadzor.py/plan_postaci.py/spot_gracz.py bezpośrednio; mapy.json i spoty_nadzorca.json atomowo po ponownym odczycie; bez commita; ZERO inputu do gry.

## Decyzje projektowe (wnioski)
- Przyczyna D3 (test_spot_gracz): połowiczny spoty.py odrzucał z z != 7 mapy, których dojście nie ma punktu na piętrze postaci w <= 60 polach DROGI (mozg._start_po_mapie) albo prowadzi przez z7; baza była flagą, ale brakowało łączników dla par z9z -> z8/z9w/z10w itd. D3 przejdzie, gdy istnieją warianty-łączniki (`<B>__z__<A>`, wpis w tabeli z `baza`), a `wybierz` wybiera wariant, gdy baza nie działa z pozycji.
- Wariant w tabeli musi mieć EFEKTYWNE auto = auto bazy (D3 sprawdza `.auto`); plan_postaci.wybierz_cel musi pomijać warianty (`s.baza`), żeby nie brać wariantu jako zamiennika z depo.
- Ocena dojścia = pozycja-zależna: spoty.dojscie_dziala_z (blisko pętli <= 10 pól = ok; punkt dojścia w <= 60 polach drogi; ogon bez z7). Flaga `dojscie_z_dowolnego_pietra` jest tylko operacyjnie potrzebna (uruchom.sh), wybór opiera się na ocenie pozycji.
- Droga (m.droga) liczy koszt prosty 1 / skos 3, więc długość w polach > BFS: pokrycie podajnikami liczyć przez SP.start_dojscia na uproszczonym łączniku (jest w rodziny_dojscie._z_pokryciem).
- Rook/Thais/Kazordoon: brak lin; łączników nie generuję (schody bez znanego kierunku, korytarz Poison Spiderów thais_pn z9 -> z8, Kazordoon z9 NIE).
## Pliki
- rodziny_dojscie.py (biblioteka: macierz, planer łączników). Roboczy egzemplarz: scratchpad .../wk/ (kopia repo); w repo wersja starsza — po zakończeniu skopiować.
- spoty.py.polowa-przerwane-20261026 = moja połowiczna wersja (funkcje start_dojscia, dojscie_dziala_z, wybierz z wariantami).
## Etapy
- [x] macierz źródło->cel dla wszystkich rodzin (edron_trolle: w górę/lateralnie brak; Rook/Thais pokrótce w STAN)
- [x] planer łączników: edron_trolle 8/8, edron_gobliny w górę OK, AbD: z10/z11 jako źródła wymagają podajników (w toku)
- [ ] zapis łączników trasy/<rodzina>_lacznik_<A>_<B>.json(+meta) i wpisy (mapy.json warianty, spoty_nadzorca: baza, auto, rodzina)
- [ ] spoty.py na kopii (spoty_nowy.py) + plan_postaci skip wariantów; testy: spot_gracz 135/135, spoty 19/19, nadzor 81/81, rodziny, plan_postaci 61/62, plan_2bp; potem JEDEN os.replace
- [ ] flagi w mapy.json (z dowodem sim) — po podmianie spoty
- [ ] testy rozszerzone (test_rodziny: każda para ma dojście albo jawny wyjątek; spoty/spot_gracz: wariant wybierany)
- [ ] STAN.md "26.10 ~12:00 — DOJŚCIE Z DOWOLNEGO PIĘTRA W OBRĘBIE JASKINI", raport przed->po

## Wznowienie 12:10 — wyniki planera (scratchpad drv2.py, ulimit -v 6 GB, każda rodzina osobno)
- edron_trolle: 8/8 łączników OK (34 s); edron_gobliny: 17/17 OK (103 s) — weryfikacja weryfikuj_lacznik True.
- abdendriel_trolle: planer NIE nadaje się (z10 -> z11_z9: łącznik 1428 pkt i weryfikacja False, 140 s/parę). Wszystkie mapy AbD mają auto:false (nadzorca ich nie wybiera) -> NIE generuję łączników AbD; opis w raporcie.
- Thais (trolle wschód, pn), Rook, Kazordoon: macierz z brak>0 — bez lin łącznika nie da się bezpiecznie zbudować (patrz raport); bez flag tam, gdzie brak>0 od któregokolwiek źródła.
- Flagi mapy.json: edron_trolle (wszystkie), edron_gobliny, thais_pn_z9, rook_bugi_z10, AbD *_z9 i abdendriel_gobliny już TRUE (potwierdzone 12:10). Nowe flagi tylko dla wariantów.
- Decyzja nazwy: łącznik `trasy/<rodzina>_lacznik_<A>_<B>` (A = mapa źródłowej pętli, B = mapa celu), mapa-wariant `<B>__z__<A>`.
- Uwaga UI: okno_api.cmd_mapy_tryby pokaże warianty na liście map (opis zaczyna się od "WARIANT NADZORCY").
- NIE używać `pkill -f <nazwa skryptu>` (zabija własną powłokę).

## 12:45 — STAN: wk2 (kopia roboczą repo + moje zmiany) ZIELONE: spot_gracz 159/159 (D3), spoty 19/19
- Zrobione w scratchpad `wk` / `wk2` (NIE w repo): generuj_lacznik_rodziny.py --zapisz (25 łączników OK: edron_trolle 8, edron_gobliny 17), nowy spoty.py (warianty `baza`, dojscie_dziala_z, auto dziedziczone od bazy, jeden wariant na bazę), plan_postaci.py (pomija `s.baza` w alternatywach).
- Przyczyna D3: pozycja testowa (33100,31760,9) NIE jest przechodnim polem mapy klienta (flaga 5), więc ocena drogi zwracała False dla każdej mapy; poprawka w kodzie: pozycja nie-przechodnia = `None` (nie da się ocenić, zostaje flaga jak wcześniej), nie obejście testu.
- TODO (kolejność): testy nadzor/plan_postaci/plan_2bp/rodziny w wk2 -> testy nowe -> przenies.py wk2->repo (trasy, mapy.json, tabela) -> atomowa podmiana spoty.py i plan_postaci.py w repo -> STAN.md
- Skrypt przenoszenia: scratchpad/przenies.py (kopiuje trasy *_lacznik_*, dopisuje klucze `__z__` do mapy.json i tabeli).

## 12:35 — wk2: test_rodziny rozszerzony (24/24, 1m41s); nadzor 81/81; plan_postaci 61/62; plan_2bp 19/19; spoty 19/19; spot_gracz 159/159
- Dodano warianty dla trolle_edron_patrol (alias z8): razem 28 wariantów (11 edron_trolle + 17 edron_gobliny).
- Luki (jawne wyjątki w test_rodziny.WYJATKI): AbD 18, Kazordoon 4, rook_bugi 1, rook_raty 36, thais_pn 2, thais_trolle_wschod 5. edron_* bez luk.
- TODO: test_spoty (nowe testy wariantów), test_spot_gracz (D3b), potem przenieś do repo: rodziny_dojscie.py, generuj_lacznik_rodziny.py, trasy łączników (przenies.py), mapy.json/tabela, testy, spoty.py + plan_postaci.py (atomowo, na końcu).

## 13:05 — wk2 ZIELONE (rodziny 24/24, spoty 25/25, spot_gracz 160/160, nadzor 81/81, plan_postaci 61/62, plan_2bp 19/19; reszta jak baseline). Zaczynam przenosić do repo.
- Wariant w tabeli ma `auto: false` (zabezpieczenie dla starego spoty.py w żywym procesie nadzorcy; nowy kod dziedziczy auto/powód po bazie w wczytaj + dynamicznie w wybierz).
- Skrypt: scratchpad/zastosuj.py stage|swap (stage: kopie *.bak-20261026-z-dowolnego, pliki, trasy, klucze __z__ w mapy.json/tabeli, spoty_nowy.py + plan_postaci_nowy.py; swap: import check + dwa os.replace).
- COFNIĘCIE: przywrócić spoty.py.bak-20261026-z-dowolnego, plan_postaci.py.bak-20261026-z-dowolnego, testy/*.bak-20261026-z-dowolnego; usunąć klucze z `__z__` w mapy.json i dane_tibia/spoty_nadzorca.json oraz trasy/*_lacznik_* (albo przywrócić mapy.json.bak-20261026-z-dowolnego i spoty_nadzorca.json.bak-20261026-z-dowolnego, jeśli inne sesje ich nie zmieniły).

## 13:25 — ZROBIONE (wszystko w repo, spoty.py podmieniony atomowo, testy zielone, STAN.md ~12:00 dopisany)
Nic do wznawiania poza ewentualnym: restart nadzorcy (nowy kod), pierwszy test lin łączników na żywo (decyzja Karola), AbD/Kazordoon/Rook/Thais bez łączników (patrz WYJATKI w testy/test_rodziny.py).
