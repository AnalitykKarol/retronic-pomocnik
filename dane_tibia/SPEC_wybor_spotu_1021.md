# SPEC: wybór spotu przez nadzorcę (Q5) - 21.10

Realizuje Q5 z `SPEC_nadzorca_rotacja_1021.md` (Karol 21.10 ~17:05: „wybór spotu też robi nadzorca i miesza postacie między spotami”).
Kod: `spoty.py`, tabela `dane_tibia/spoty_nadzorca.json`, wpięcie w `nadzor.py`. Testy: `testy/test_spoty.py`, przypadki w `testy/test_nadzor.py`.

## Przypadki, z których to wynika

- 21.10 17:02 Kolanosh stał w depo w Edronie, a bot ruszył na `raty` (Thais) z `tryb.log` z 15:22: mapa była „ostatnia”, nie pasowała do miasta.
- 21.10 17:12 Kolanosh bez liny na `trolle_edron_z9w` (dojście wchodzi liną z11 -> z7) utknął na (33134,31806,z11).

## Tabela: `dane_tibia/spoty_nadzorca.json` (dlaczego tu i pod tą nazwą)

Tabela jest **redakcyjną nakładką na `mapy.json`**, nie jego kopią: miejsce, potwory, trasa i dojście zostają w `mapy.json` (jedno źródło).
W `spoty_nadzorca.json` jest tylko to, czego `mapy.json` nie wie i co Karol chce móc zmienić: `miasto`, `jaskinia` (grupa spotów dzielących
jaskinię), `poziom` [min, max] z `poziom_zrodlo` (`domyslne` -> po przeglądzie Karola `karol`), `waga`, `auto` (false = nadzorca tego
spotu nie wybiera) z `powod`, `wymaga_dodatkowo` (np. `pochodnia`). Nazwa `spoty_nadzorca.json`, bo `dane_tibia/spoty.json` już istnieje i jest czym innym (model spotów ze spawnów CipSoft, E1…, exp/h z modelu, nie ruszany). Wybrano `dane_tibia/` a nie `instancje/_wspolne/`, bo `instancje/` jest w `.gitignore`
(tabela ma historię zmian i przegląd w diffie), a to dane o świecie gry, nie konfiguracja uruchomieniowa. `nadzor_konfig.json` zostaje przy limitach czasu.

Wyprowadzane na bieżąco (nie ma ich w pliku, więc nie rozjadą się z trasami):
- **piętra** i **miasto kontrolne** z punktów dojścia i trasy (`spoty.py sprawdz` zgłasza rozbieżność z wpisanym `miasto`);
- **lina**: `liny.wymaga_liny` na dojściu i pętli (`liny.znane_liny()`, rośnie z logów); **łopata**: przejście w dół przy dziurze z `pietra.ZASYPANE` albo
  zapamiętane `tryb: lopata` (`wypad.przejscia_nauczone`), pole w odległości <= 1 od punktów przejścia (jak lina); patrol (`patrol`, `patrol:X`) rozwiązywany jak `mozg.rozwiaz_patrol`;
- mapa z `mapy.json`, której nie ma w tabeli, jest **wykluczona** (`brak wpisu w spoty_nadzorca.json`) i widać ją w `spoty.py sprawdz`: nowy spot z `nowy-spot` trzeba świadomie dopisać.

Miasta to prostokąty x/y w `spoty_nadzorca.json` (`miasta`): `edron`, `thais`, `rook`, `port_hope` (nazwy jak w `trasy/serwis_*.json`). Rook nie ma pliku serwisu, więc
`panel.miasto_pozycji` go nie zna; prostokąty obejmują też jaskinie (postać w jaskini też „stoi” w mieście). Poza prostokątami miasto = nieznane.

## Wybór: `spoty.wybierz(postac, zajete, historia, ...)`

Wejście `postac`: `id`, `poz` (x,y,z z gry: `panel.pozycja` z `okno_api stan`), `poziom` (`gracz.level`), `ekwipunek` (słownik albo funkcja:
`{"lina": True|False|None, "lopata": ...}`, odczyt leniwy i tylko gdy kandydat czegoś wymaga). Filtry w tej kolejności, każde odrzucenie dostaje powód:

1. wpis `auto: false` albo brak wpisu;
2. **miasto spotu = miasto z pozycji** (nieznana pozycja albo miasto -> brak wyboru, nigdy zgadywanie); Rook i kontynent się nie mieszają, bo to inne prostokąty;
3. **poziom w widełkach** (nieznany poziom -> brak wyboru);
4. **piętro startu**: dojście działa tylko ze z7 albo przy `dojscie_z_dowolnego_pietra` (jak `uruchom.sh`); spot bez dojścia wymaga `auto: true` jawnie;
5. **jeden własny bot na spot**: `zajete` (mapy innych postaci) rozszerzone o całą `jaskinia` (`trolle_edron` i `trolle_edron_patrol` to jeden spot);
6. **ekwipunek**: spot wymagający liny/łopaty tylko przy `True`; `False` = odrzucony; `None` (brak odczytu) = odrzucony, **chyba że nie ma żadnego innego** kandydata
   (wtedy ten sam wybór co `mozg.sprawdz_line`: nieznane = startuj; jawne `False` nigdy);
7. **mieszanie**: jaskinia ostatniej zmiany tej postaci (`historia`) odpada, o ile zostaje alternatywa.

Z reszty losowanie ważone `waga` z ziarnem `RRRR-MM-DD|id|przyczyna` (przyczyna = początek zmiany albo `zmien_spot`), więc wynik w obrębie zmiany jest powtarzalny.
Wynik: `{"mapa", "jaskinia", "powod" (jedno zdanie), "odrzucone": [(mapa, powód)], "kandydaci"}` albo `{"mapa": None, "eskalacja": "brak_spotu", "powod"}`.
Wagi z `ekonomia-*.jsonl` NIE są użyte: rekordy ekonomii nie zawierają mapy (trzeba by łączyć sesje z `tryb.log` po czasie), więc zostaje `waga` ręczna, domyślnie równa
(warianty jednej jaskini mają wagi sumujące się do 1, żeby jaskinia z czterema wariantami nie wygrywała czterokrotnie częściej).

## Wpięcie w `nadzor.py` (kopia `nadzor.py.bak-20261021-spoty`)

- **Start zmiany** (po zalogowaniu, w `_bez_bota`, przed `start_bota`): mapa z grafiku/konfiguracji postaci (jawne ustawienie Karola) wygrywa jak dotąd;
  inaczej wybór z tabeli. Tryb (`sredni,runy` itd.) zostaje bieżący z `tryb.log` (to cecha postaci, nie spotu).
  Brak danych (pozycja/poziom nieczytelne): czekaj do 10 min od logowania, potem eskalacja `nieustalony`. Brak spotu: eskalacja `brak_spotu`
  (powiadomienie critical, **bez wstrzymania** postaci i bez startu; kolejny przebieg próbuje znów).
- **`zmien_spot`** (drabina napraw i CLI): `spoty_zapasowe` z `profil.json` (jawna lista Karola) wygrywa, gdy jest; inaczej wybór z tabeli z bieżącą mapą jako „ostatnią”.
  Szczebel `zmien_spot` jest w drabinie także wtedy, gdy tabela ma alternatywę.
- **Restart/wznów w trakcie zmiany**: bez zmian, zostaje bieżąca mapa (`tryb.log`).
- **Zajętość** liczona z BIEŻĄCYCH map innych postaci (`mapa_tryb_biezace`, `tryb.log` + `Mózg: … trasa`), nie z `ostatni_start.*.env` (które `okno_api` podaje w polu `mapa`),
  plus spot przypisany w tym przebiegu i spot zapisany w stanie nadzorcy dla postaci online (`spot`).
- **Historia** w stanie postaci (`spoty_hist`, ostatnie 10); gdy pusta, „poprzednia zmiana” = ostatnia mapa z `tryb.log`.
- **Dziennik**: każda decyzja ma jedno zdanie („wybrano X: miasto edron, poziom 11 w 10-30, wolna jaskinia; odrzucone: Y (…), Z (…)”).
- **Cień**: `nadzor.py cien --raz` dopisuje do wydruku `spot_podglad` dla każdej postaci w grze („wybrałbym teraz”), zero zapisów; w cieniu z zapisem wpis najwyżej raz na godzinę na zmianę wyboru.
  Bez `spoty_nadzorca.json` nadzorca zachowuje się jak dotąd (bieżąca mapa z `tryb.log`) i pisze o tym raz w dzienniku.

## CLI `spoty.py`

`tabela` (wszystkie spoty z kolumnami wyliczonymi), `sprawdz` (rozbieżności tabeli z `mapy.json`/trasami), `ekwipunek` (odczyt liny/łopaty bieżącej instancji, `RETRONIC_ID`; tylko odczyt pamięci gry).

## Granice

Nie rusza: `cavebot.py`, `mozg.py`, `wypad.py`, `wyprawa.py`, `pietra.py`, `wpadniecie.py`, `mapy.json`, `rdzen.py`, `straznik.py`, `instancje/<postać>/*`.
Pochodnia: brak danych, które trasy jej wymagają (brak w `mapy.json`/trasach), więc nadzorca jej nie sprawdza; do dopisania przez `wymaga_dodatkowo` po decyzji Karola.
Poziomy to **domyślne widełki wg potworów**, nie dane: Karol przegląda je w `spoty_nadzorca.json` (`poziom_zrodlo: domyslne`).
