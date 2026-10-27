# SPEC naprawy 14.10 (po sesji 09:00-11:40)

Cel: zebrać w jednym miejscu wszystko, co 14.10 wyszło na żywo, z przyczyną, poprawką, testem i kolejnością.
Zasady: każda zmiana za pokrętłem (cavebot.py + pokretla.py ZAKRESY/KIERUNEK), domyślna w kodzie = zachowanie, które
Karol uznał za poprawne, i wpis w `na_zywo.przyklad.json`. Restart bota tylko raz, po zebraniu zmian kodu.
Nie ruszać: stanu gry, kont, `na_zywo.json` bez kopii. Nic do repo bez słowa Karola.

## Stan na żywo (obejścia, które trzeba zastąpić poprawką w kodzie)

| Pokrętło w na_zywo.json | Wartość | Po co | Docelowo |
|---|---|---|---|
| OGIEN_STALY | 0 | maska "stałych" pól ognia wpuszczała bota w ogień | N1: przeprojektować, potem 1 |
| PIETRA_LOPATA | 1 | łopata tylko z7 (wejście do jaskini) | N2: domyślna w kodzie |
| WYPRAWA_DEPO_BLANKI | 1 | brak blanków = wyprawa do depo (działało 13.10) | N2: domyślna w kodzie |
| WYPRAWA_TYLKO_DEPO | 1 | wyprawa tylko do depo | bez zmian |
| WYPRAWA_BLANKI | 15 | cel zakupu u Xodeta przy wyprawie pełnej | bez zmian |

Kopie: scratchpad `na_zywo.json.bak-*`, `wyprawa_stan.json.bak*`, `mozg.py.bak-trasa`, `wypad.py.bak-lopata`, `uruchom_trolle.sh.bak`.

## N1. Ogień: maska stałych pól (priorytet wysoki)

- **Objaw:** 09:40-09:42 bot trzy razy "stoję na ogniu" (HP traci), w logu `34 stałych, 0 zmiennych`.
- **Przyczyna:** G1 (P6) uznaje pole za "stałe" po `OGIEN_STALY_N=20` wykryciach w `OGIEN_STALY_S=600 s` i wyłącza je z blokowania
  w A* i klikach. W jaskini ogień pojawia się i znika na tych samych współrzędnych (orkowie, runy), więc maskuje prawdziwy ogień.
- **Poprawka:** maska tylko dla pól, które mapa klasyfikuje jako ściana/nieprzechodnie (fałszywe wykrycie na teksturze), nigdy dla pól
  przechodnich wg mapy. Dodatkowo: pole z maski odblokowuje się, gdy wykrycie ma barwę/kształt ognia w bieżącej klatce
  (nie tylko historię) albo gdy bot w nie wszedł i stracił HP.
- **Miejsca:** `cavebot.py` `_ogien_stale_aktualizuj` (~2103), `_ogien_blok` (~2128), `_ogien_na_drodze`; `ogien.py`.
- **Test:** `test_ogien.py`: pole przechodnie wykrywane 25 razy w 10 min nie wchodzi do maski; pole-ściana tak.
  Regres: log `[OGIEN]` max 1 linia/10 s (OGIEN_LOG_S) zostaje.
- **Akceptacja:** 1 h patrolu bez "stoję na ogniu" i bez spadku HP od ognia; wtedy OGIEN_STALY=1 w na_zywo.

## N2. Domyślne pokrętła w kodzie = zachowanie z działającego dnia (priorytet wysoki, mały)

- **Objaw:** brak blanków nie wysyłał bota do depo (regresja G3/P7b), mimo że 13.10 działało.
- **Przyczyna:** nowe pokrętło `WYPRAWA_DEPO_BLANKI` dostało domyślną 0 (`cavebot.py:196`) i nie było w `na_zywo.json`.
- **Poprawka:** domyślna 1 dla `WYPRAWA_DEPO_BLANKI` (zgodnie z "wróć do depo, gdy skończą się jedzenie/blanki").
  `PIETRA_LOPATA`: w kodzie jest 1 (`cavebot.py:206`), ale log pokazał "(domyślna 0)" przy hot reload. Sprawdzić,
  skąd bierze się 0 (pokretla.py? start z env?) i wyrównać, żeby log i kod mówiły to samo.
- **Reguła na przyszłość:** każde nowe pokrętło zmieniające zachowanie wchodzi z domyślną = stare zachowanie albo od razu
  do `na_zywo.json` i `na_zywo.przyklad.json`.
- **Test:** `test_wyprawa.py`: tryb depo + 0 blanków + zapas OK -> wyprawa `depo:blanki` startuje bez żadnego pokrętła w na_zywo.

## N3. Łopata tylko na z7 także w kodzie wyprawy (zrobione, do weryfikacji)

- **Objaw:** 10:10 `Wypad: dziura (32476,32272) zasypana? odkopuję łopatą` na schodach w jaskini (z8). Potem wyłączyłem łopatę
  całkiem, co odcięło kopanie przy wejściu z z7; Karol kopał ręcznie.
- **Zrobione:** `wypad.py` `_dziura`: gałąź "lopata" pomija się, gdy `PIETRA_LOPATA_TYLKO_Z7=1` i `poz[2] != 7`; na_zywo `PIETRA_LOPATA=1`.
  Testy: wypad_drzwi 26/26, wielopietrowa 38/38, wyprawa 96/96. Kod `wypad.py` ładuje się dopiero po restarcie bota.
- **Do zrobić:** test dedykowany (z8 + nieudany krok -> brak łopaty; z7 -> łopata) w `test_wypad_*`.
  Dodatkowo: pierwszy nieudany krok w dół po schodach (bot "nie trafia w schody") sprawdzić osobno, patrz N7.

## N4. Mózg: fałszywe "plecak pełny, cap 0, brak jedzenia" (priorytet wysoki)

- **Objaw:** 10:23:40 `brak_zabic`: Haiku wnioskuje "plecak pełny (cap 0), brak jedzenia" i zmienia trasę na `troll_do_miasta`.
  Powtarza się przy każdym `odpuszczone_poscigi`.
- **Przyczyna:** do kontekstu modelu trafia `cap` z odczytu (0 = brak odczytu, nie zero capa) oraz zapas jedzenia z chwili,
  gdy kontenery były niewidoczne.
- **Zrobione tymczasowo:** `mozg.py` odrzuca `zmien_trase` na nazwę zawierającą "miasta" (log "Odrzucam zmien_trase...").
- **Poprawka docelowa:** (a) w stanie dla modelu `cap: null` zamiast 0, gdy `max_cap` = 0/nieznany, plus wzmianka "cap
  niewiarygodny" w prompcie; (b) zapas jedzenia/blanków `null`, gdy `kontenery` puste, z notatką "plecak niewidoczny";
  (c) w prompcie zakaz wnioskowania "plecak pełny" bez `wolne_sloty`; (d) powrót do miasta decyduje tylko wyprawa.py.
- **Miejsca:** `mozg.py` ~1833 (`"cap": g.get("cap")`), prompt systemowy (~253-280), walidacja akcji ~1467.
- **Test:** `test_mozg.py`: stan z `cap 0` i bez kontenerów nie zawiera "pełny"/"0 oz"; zmien_trase na *miasta* odrzucone.

## N5. Fałszywy głód przy niewidocznych kontenerach (priorytet wysoki)

- **Objaw:** 10:00 "pamięć nie widzi otwartych kontenerów" -> "Zjedzono: nic (brak jedzenia)" -> potwierdzony głód ->
  10:07 wyprawa `depo:glod`, choć w plecaku jest 3 ham, 7 blanków, UH. Wyprawa jest zapisana w `wyprawa_stan.json`, więc po
  restarcie wznowiona i bot wracał do miasta mimo STOP.
- **Poprawka:** (a) `jedzenie_znane_brak` (cavebot.py:1714) = False, gdy odczyt kontenerów jest pusty/błąd; wtedy najpierw
  otworzyć plecak (jest ścieżka obrazkowa "szukam obrazkiem"), dopiero potem sądzić; (b) `glod_potw_do` ważny tylko, gdy zapas
  był odczytany wiarygodnie w ostatnich N s; (c) wznowienie wyprawy po restarcie (`wyprawa.py:~1022`) re-waliduje powód:
  jeśli powód `glod`/`zapas` już nie zachodzi (zapas OK, kontenery widoczne), wyprawę kasuje zamiast wznawiać.
- **Test:** `test_wyprawa.py`: stan zapisany `depo:glod` + zapas 3 + kontenery widoczne -> po restarcie brak wznowienia.
  `test_jedzenie*`: kontenery puste -> brak `brak_jedzenia` i brak glod_potw.

## N6. Drzwi w jaskini (priorytet średni, potrzebna współrzędna)

- **Objaw:** trolle "za ścianą (droga naokoło: brak drogi)" w okolicy (32501-32506, 32268-32272) na z8; pole między nimi
  oznaczone jako ściana z mapy. Karol otworzył drzwi ręcznie, wtedy 7/7 zabić. Patrol nie ma obsługi drzwi (jest tylko w wyprawach:
  `wypad.py` `drzwi_z_mapy`, `_drzwi`, trasy `drzwi_frodo`).
- **Dane od Karola:** dokładna pozycja drzwi (stanąć obok, odczytać z pamięci; zapisać w `trasy/drzwi_jaskinia.json`).
- **Poprawka:** w patrolu, gdy cel odpuszczony "za ścianą", a na linii leży znane pole-drzwi: podejdź na pole `stoi`,
  Use na drzwiach (jak `wypad._drzwi`), potwierdź zmianę pola w pamięci/ekranie, powtórz max 3 razy, potem odpuść z notatką.
  Pokrętło `PATROL_DRZWI` (domyślnie 1).
- **Test:** symulacja: wolne pola po obu stronach, pole drzwi "ściana" na mapie -> bot wykonuje Use, nie odpuszcza.
- **Akceptacja:** po zamknięciu drzwi (ręcznie, żeby sprawdzić) bot sam je otwiera i bije trolle za nimi.

## N7. Zejście w dół schodami: "nie trafia w schody" (priorytet średni)

- **Objaw (Karol):** "przy zejściu w dół nie trafia w dziurę, to są schody, ich nie da się zasypać"; log 10:10:41
  `dziura_bez_zmiany_pietra` przy pierwszym kroku (próba 1/`krok`), potem próby łopatą, za trzecim razem wchodzi.
- **Hipoteza:** (a) krok z pola po skosie albo z pola nie sąsiadującego ortogonalnie ze schodami (pietra.py ma pole startowe
  ortogonalne, `wypad._dziura` liczy kierunek tylko z `dx,dy`); (b) `_po_przejsciu` sprawdza zmianę piętra zbyt wcześnie.
- **Poprawka:** w `wypad._dziura` użyć tej samej logiki co `pietra.py` (pole startowe ortogonalne + pamięć
  `trasy/pietra_start.json`) i poczekać do ~1 s na zmianę piętra przed uznaniem próby za nieudaną; schody (flaga "stairs" /
  `typ` w przejściach) nie dostają łopaty w ogóle.
- **Test:** `test_wypad_*`/`test_wielopietrowa`: start po skosie -> krok najpierw w poziomie, potem w schody, 1 próba.

## N8. Start bota z miasta/z7: dojście przerwane (priorytet średni)

- **Objaw:** 11:28-11:30 start z (32400,32220,7): `Dojście nieukończone ... nie zaczynam głównej trasy`; potem z `BEZ_DOJSCIA=1`
  `Przejście pięter NIEUDANE (wyczerpane pola przejścia)` x3 i `Koniec.` (bot zakończył pracę).
- **Poprawka:** (a) z7 bez dojścia nie ma sensu: `uruchom_trolle.sh` gdy `Z=7` -> zawsze dojście z depo (jest), a
  `BEZ_DOJSCIA=1` (dodane przeze mnie) ostrzega, że z z7 to nie zadziała; (b) przy nieukończonym dojściu bot nie kończy procesu,
  tylko czeka i powiadamia (ALARM), żeby Karol mógł dojść ręcznie, a bot dalej pilnował; (c) zbadać, czemu dojście
  `depo_troll_cave` przerwało się po 45 s (ostatnia pozycja, drzwi sklepu `(32400,32217,7)`).
- **Test:** `test_dojscie_*` (nowy): przerwane dojście -> proces nie kończy, loguje ALARM.

## N9. Przenoszenie blanków do baga na runy (priorytet niski)

- **Objaw:** po zakupie poza wyprawą blanki zostały w głównym plecaku; skrypt `blanki_do_bagu.py` przenosił tylko 3.
- **Ustalenia:** funkcja istnieje (`loot.przenies_do_runow`, krok wyprawy `przenies_runy`, `wyprawa.py:1339`), przeciąga na
  pierwsze wolne widoczne pole okna baga. Pomocniczo `przenies_runy.py` przeniósł 10, bag jest teraz 20/20.
- **Do zrobienia:** (a) wołać `przenies_do_runow` także po zakupie poza pełną wyprawą (np. na starcie bota, gdy w głównym
  plecaku są blanki, a w bagu jest miejsce); (b) log "brak wolnego widocznego pola" zamiast cichego przerwania;
  (c) przy pełnym bagu (20/20) nie marnować prób.
- **Test:** `test_wyprawa.py`/`test_loot_*`: blanki w plecaku + wolne pole -> przeniesione; brak pola -> 0 i jedna linia logu.
- **Status 27.10:** zrobione 27.10 (start bota + wyzwalacz w trakcie pracy, `blanki_start.py`, rola okna z położenia), NIEPOTWIERDZONE NA ŻYWO.

## N10. Rzeczy poboczne

- `kup_blanki.py` (jednorazowy skrypt zakupu) i `kup_test.py`: wynieść wspólny kod do `wyprawa.py` jako `kup_u_npc(npc, przedmiot, n, limit_gp)`;
  limit 150 gp w skrypcie testowym odrzucił ofertę 200 gp za 20 blanków (poprawny zakup). Powitanie Xodeta
  "Oh, please come in" jest już w `wypad.ODP_POWITANIE`, błąd był w skrypcie.
- Xodet w `trasy/wyprawa_sklepy.json` jest `zweryfikowane: false`: oznaczyć jako zweryfikowany po dzisiejszym zakupie
  (`buy 20 blank rune` -> `200 gold`, `yes` -> `Here you are.`, stoi (32400,32220,7)).
- Cap: przy 10 oz wolnych wyprawa pełna kupiłaby ~8 blanków, a `WYPRAWA_CAP_REZERWA=8` zeruje zakup (limit = cap - rezerwa).
  Przy trybie depo problem nie występuje. Rozważyć: jeśli powodem jest `blanki`, rezerwa 0 i komunikat o niedokupionej liczbie.
- Ogłoszenia Trade: kod gotowy i wyłączony (`TRADE_OGLOSZENIA=0`); Karol powiedział "na razie niepotrzebne". Bez zmian.
- Repo: nowy commit po wdrożeniu N1-N5; push tylko po zgodzie. Dopisać `na_zywo.przyklad.json`.

## Kolejność i restarty

1. **Restart 1 (jeden):** N2 + N4 + N5 + N3-test + N9 + N10 (kod w cavebot/mozg/wyprawa/wypad, testy zielone przed restartem:
   test_mozg 239+, test_wyprawa 96+, test_wielopietrowa 38, test_uh 90, test_wypad_drzwi 26, test_ogien).
2. **Restart 2:** N1 (ogień) po 1 h obserwacji, potem N7 i N8.
3. **N6:** gdy Karol poda współrzędną drzwi.

Obserwacja po restarcie 1 (60 min): brak powrotów do miasta bez powodu, brak "stoję na ogniu", UH ok przy pełnym bagu,
brak `zmien_trase` modelu, exp/h vs. 09:30-10:10 (ok. 600 exp w 40 min po naprawie).
