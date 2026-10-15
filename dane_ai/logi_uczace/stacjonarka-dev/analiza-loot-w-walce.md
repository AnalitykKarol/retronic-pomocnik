# Analiza: loot w walce i odłożone zwłoki (11.10.2026, okno 15:29-15:49)

Źródła: logi/mozg-20261011-1519.log, -1539.log, -1547.log (łącznie od 11:32), logi/telemetria-20261011.jsonl
(próbki co ~1,7 s: poz, hp, stwory z odl/cel), kod cavebot.py/loot.py (numery linii wg pliku z godz. ~15:50;
plik jest równolegle edytowany, część poprawek w `_hp_nisko`/watchdogu/`zwloki_chlod` już tam jest).
Zdarzenia typu `zabicie`/`loot` z `walka_s 0.0` seriami po 4 w jednej sekundzie (15:25:21, 15:32:05, 15:32:23,
15:32:39, 15:42:37) to śmieci z testów, pominięte.

## Wniosek w jednym zdaniu

Loot w walce nie odpala się, bo postać siedzi cały czas poniżej `LOOT_W_WALCE_HP=70` (HP 68% od 15:30:02,
potem 45% od 15:42:05, bez regeneracji, bo `brak jedzenia w plecaku`), a zwłoki odłożone przepadają, bo
w ciągłej walce z szczurami tick prawie nigdy nie dochodzi do bloku „odłożone zwłoki”, a TTL=60 s i
przycinanie >8 pól kasuje je bezpowrotnie.

## a) Czy loot w walce miał szansę wystartować

Metoda: dla każdej próbki telemetrii sprawdziłem, czy na liście odłożonych jest zwłok w odl dokładnie 1
(Chebyshev, więc skos wliczony), czym była flaga celu (`cel` w próbce) i ile żywych w odl <=1.

| Wskaźnik (15:29-15:46) | Wartość |
|---|---|
| Zwłok odłożonych ("Loot odłożony") | 17 |
| Wystartowań "Loot w walce:" w logach | 0 (w całym dniu 3, wszystkie ok. 15:20:40-15:21:34, zob. niżej) |
| Zdarzeń telemetrii loot_w_walce_* po 15:22 | 0 |
| Próbek (~1,7 s) z odłożonymi zwłokami w odl 1 | 203 |
| z tego z HP < 70 | 190 (94%) |
| z tego tylko HP blokuje (reszta warunków OK) | 85 (~2,4 min łącznie, ok. 10 oddzielnych zwłok po 6-10 próbek) |
| HP<70 + inny powód (cel nie obok, po walce bez mobów, stan LOOT) | 105 |
| tylko `stykajace>2` (3 żywe w odl<=1, HP 86%) | 13 (zwłoki 32001,32154, 15:29:46-15:30:11) |
| tylko cel nie obok | 4 |
| wszystkie warunki OK | 0 |

Kolejność blokad: 1) HP<70 (jedyny powód w 85 próbkach, współpowód w 190), 2) `cel_daleko`/brak celu obok
(próbki w pościgu lub po zabiciu ostatniego), 3) `stykajace>2` (13 próbek, jedna sytuacja przy HP 86%).
Nie widać w danych: `hp_spadek` (0 z 75 próbek "tylko HP" wypadło w 2 s po spadku HP), `obce_okno`
(w nowym kodzie nie wystąpiło ani razu, bo nie doszło do próby), zwłoki nieznane (zawsze były na liście),
zwłoki diagonalnie (Chebyshev w `dystans` i `przylega` już je liczy, to nie jest blokada).
Niewidoczne w próbkach (tylko zmniejszają liczbę okazji): flaga ataku (`atak_false`), 1 s po kliku ataku,
0,6 s postoju, 3 s chłodu.

Zwłoki w odl 2 (nie można kliknąć): 5 z 20 zabić z okna (15:30:20, 15:31:23, 15:32:20, 15:33:46, 15:42:18),
bo cel ginął w odl 2; zwłoki na odl 0 (pod nami) po schodzeniu celu też się zdarzają, ale mały odsetek.

Przebieg HP: 86% do 15:30:02, potem 68% płasko do 15:39 (restart 70%), 61->57->54->48->45 do 15:42:05 i
45% do końca. W całym oknie regeneracja ~0 (jedzenia brak: "Zjedzono: nic (brak jedzenia)" 15:42:32,
15:49:22). Każdy próg HP bezwzględny typu 70 jest więc dla tej sesji progiem nieosiągalnym. Próg ucieczki to
30 + losowe 0-5 (`ROZRZUT_PROGU`, losowane przy każdym nowym celu, cavebot.py:~1260).

Dawne próby (stary kod, HP 100%): 15:20:40 start, 15:20:59 `przerwa_w_krokach` po 18,3 s (okno zwłok
zostało otwarte: `zamkniete null`), 15:21:08 i 15:21:34 `obce_okno` na tych samych zwłokach
(32002,32138), czyli okno zostawione przez przerwanie pilne blokuje kolejne próby (`krok_w_walce` odmawia
przy jakimkolwiek otwartym kontenerze zwłok, loot.py: `if przed: return "przerwane","obce_okno"`).
To drugi, niezależny od HP powód, że funkcja nie działa: 0 ukończonych ("koniec") w całym dniu.

## b) Los zwłok odłożonych

Mechanika (cavebot.py):
- `odloz_zwloki` (2862) dopisuje (pole, czas), nie odświeża czasu istniejącego wpisu.
- `zwloki_do_zebrania` (2881) przy KAŻDYM wywołaniu nadpisuje listę, usuwając wpisy starsze niż
  `ZWLOKI_WAZNE=60` s albo dalsze niż `ZWLOKI_ZASIEG=8` pól, bezpowrotnie (bot nie wróci, nawet jeśli
  później znowu będzie blisko). Wywoływane tylko z bloku "odłożone zwłoki" w ticku (~1300), który
  dochodzi do głosu dopiero, gdy nie ma celu (walka ma pierwszeństwo, a "Nowy cel" pada w tej samej
  sekundzie co zabicie) i `zywy_w_poblizu` (8 pól, uciekający nawet dalej) nie wstrzymuje loota
  (do `LOOT_BLOK_MAX=8` s).
- Czyszczenie przy ucieczce/utknięciu/zmianie celu: brak. Ucieczka (45 s odpoczynku) nie zatrzymuje
  zegara TTL, więc po powrocie zostaje ~15 s. Jedyne jawne czyszczenie to watchdog bezczynności (1357).
- Przerwanie lootu przy HP: pop z listy, `_zbierz_loot` -> `_hp_nisko` -> `odloz_zwloki` z NOWYM
  czasem. TTL resetuje się w kółko, zwłoki nigdy nie wygasają (dowód: zwłoki 32035,32151 zabite 15:43:58
  żyły do 15:46:35, 157 s > 60 s).

Liczby:
- 15:29-15:46: 17 odłożonych, tylko 2 zebrane po walce (15:42:42, 8 s po zabiciu; 15:46:35, po 157 s i
  pętli), czyli 15 przepadło (88%). W oknie 15:31-15:46: 13 odłożonych, 2-3 zebrane.
- Cały dzień (11:32-15:48): 143 "Loot odłożony" vs 29 "[LOOT] odłożone" (20%), ok. 80% zwłok nie
  zebrano (dolna granica dla zebranych: część może wejść przez ścieżkę zabicia z `pola_zwlok`).
- Z 13 zwłok z 15:31-15:46: 5 oddaliło się >8 pól w ciągu TTL (po 15, 16, 20, 33, 44, 48 s; bot goni
  uciekające szczury i trasa idzie dalej), więc przycięte dystansem; reszta (zostały w odl <=4) wygasła
  po 60 s, bo między zabiciami tick nie miał wolnej chwili (próbki bez celu: 2-12 z 12-41 w oknie 60 s).
- Przykład 15:41:45-15:42:51: trzy zwłoki w odl 1-3, bot zbiera jedne (8 s), kolejne wygasają o 15:42:45
  i 15:43:02, próba 15:43:19 trafia w puste pole (`brak_okna`, wszystko "pusto").

## c) Spam "Przerywam loot: niskie HP gracza"

173 linie w mozg-20261011-1539.log, 15:44:13-15:46:51 (99 s po 1/s, 37 s po 2/s). Przyczyna:
`_hp_nisko` (stary kod: HP <= próg_aktualny+10, tu 45 <= ~35+10) zwraca True zawsze, więc
`zbierz_loot` kończy się w pierwszej iteracji, `odloz_zwloki` wrzuca zwłoki z powrotem, `tick` zwraca
True BEZ pauzy (blok ~1305 nie ma `self.pauza`). To nie blokuje ticka od strony bezpieczeństwa (ucieczka,
walka są sprawdzane na początku każdego obiegu, pętla ~0,75 s na `gracz()` + `stwory()`), ale:
- bot stoi w miejscu na czas HP>45 (czyli na zawsze bez jedzenia): `idz()` nigdy nie jest wywołane,
- `pauza_bota 120 s` z modelu (15:45:10) nie działa na ten blok, bo wstrzymanie dotyka tylko `idz()`
  w mozg.py (1346); 114 z 173 linii padło już PO ogłoszeniu pauzy,
- pętla generuje zdarzenia do modelu ("loot wpada w pętlę przerywania", koszt LLM) i szum w logu,
- pętla kończy się tylko nowym szczurem (nowy cel losuje nowy próg ucieczki, loot przeszedł o 15:46:35/15:49:14).
Obecny kod pliku ma już `zwloki_chlod` (LOOT_PRZERWANY_CHLOD_S, 2713), `LOOT_HP_ZAGROZENIE=3`,
`LOOT_HP_MOBY_ODL=6` i watchdog; to zamyka pętlę, ale nie rozwiązuje a) i b).

## Propozycje zmian (nie wdrażałem)

1. Próg HP względem progu ucieczki zamiast 70 (cavebot.py:73 i test w `_lww_powod` ~2546).
   `proc < prog_aktualny + LOOT_W_WALCE_HP_MARGINES` z marginesem 12-15 (czyli ok. 42-50% przy prog 30).
   Efekt na danych: odblokowuje ~85 próbek / ok. 10 sytuacji z 15:30-15:46 (HP 68-57), a poniżej ~45
   dalej nie rusza. Ryzyko średnie: szczur zdejmuje 1-6 pp na uderzenie, ale krok jest atomowy (<1 s),
   warunki są sprawdzane każdy krok, a ucieczka (predykcja do 15 pp) działa w każdym obiegu. Pokrętło
   w pokretla.py trzeba przestawić na "w dół" (dziś 70-95 tylko w górę).
2. Zostawić `LOOT_W_WALCE_STYKAJACE=2`. Obniżanie do 1 kosztowałoby 13 próbek (jedna sytuacja przy HP 86%),
   zysk nieistotny; tłum 3+ to dobra blokada.
3. `ZWLOKI_WAZNE` 60 -> 120 s i `ZWLOKI_ZASIEG` 8 -> 12 (cavebot.py:88-89), a w `zwloki_do_zebrania`
   (2881) nie kasować wpisów za odległość, tylko je pomijać do TTL (bot mógł się oddalić pościgiem,
   a wróci). Ryzyko niskie, o ile zwłoki nie gniją szybciej: nie mam pomiaru czasu rozkładu "dead rat"
   w tej grze, najstarsze udane loty w logach miały 41 s. Jednorazowy test: zebrać zwłoki w wieku
   90 s i zalogować `brak_okna` vs ok.
4. Ucieczka nie powinna palić TTL: przy wyjściu z ucieczki (cavebot.py:~1057, `po_ucieczce`) dosunąć
   czasy wszystkich wpisów o czas trwania ucieczki, a po odzyskaniu HP (>= próg+margines) ustawić
   priorytet powrotu (patrz 5). Ryzyko niskie.
5. Priorytet powrotu po zwłoki: w ticku (blok ~1300) po zabiciu ostatniego żywego w promieniu
   LOOT_PO_WALCE bot od razu zbiera najbliższe (jest), ale ciągła walka z nowym celem w tej samej
   sekundzie tego nie dopuszcza. Dodać: gdy `cel` w odl >=2 (nie bijemy) i zwłoki w odl 1-2 i nic nie
   styka, zbierz zwłoki zanim ruszysz za celem (jeden krok `krok_w_walce` zamiast pościgu). Ryzyko
   średnie (zmiana kolejności walka/loot), do włączenia pokrętłem.
6. `zywy_w_poblizu` dla uciekających (cavebot.py:~2880): rozszerzony zasięg `DOBICIE_ZASIEG_UCIEKAJACY`
   wstrzymał loot o 15:42:31 na 8 s przy szczurze w odl 9 (15% HP, nie do dogonienia, 15:25:50
   "od 40 s gonię uciekającego bez skutku"). Stosować rozszerzony zasięg tylko, gdy zwłoki są w odl >1
   albo uciekający jest <= 4 pola.
7. `obce_okno` w `krok_w_walce` (loot.py ~1340): zamiast przerywać przy każdym otwartym oknie, jeśli
   kontener jest w odl >1 lub nie jest przy zwłokach z listy, zamknij go (X / Ctrl+klik) i ponów w
   następnym kroku; oraz przy `_lww_przerwij(pilne=True)` zamykać okno, gdy faza == "czekaj"
   (okno już otwarte, brak ryzyka). Ryzyko średnie (input w walce), ale ten sam kod `zamknij_w_walce`
   już istnieje.
8. Blok "odłożone" w ticku (~1305): dodać `self.pauza(0.3, 0.6)` po `zbierz_loot`, gdy wynik to
   "przerwany", i respektować `wstrzymany()` z mozg.py (pauza_bota). Ryzyko znikome.
9. Telemetria: w `_lww_tele` (2543-2545 w starym pliku) zdarzenie było wysyłane dwa razy
   (zdublowana linia); sprawdzić, czy to już poprawione. Dodać do próbki flagę `atak` i `lww_powod`,
   żeby następna analiza widziała `atak_false`/`hp_spadek` wprost, nie przez zgadywanie.

## Czego nie da się stwierdzić z logów

Dokładnej flagi ataku w czasie okazji, czasu rozkładu zwłok, oraz tego, czy 2 "Loot: ok" z 15:33:16/15:33:22
dotyczyły dwóch odłożonych zwłok (przyjąłem najwyżej 1 z odłożonych).
