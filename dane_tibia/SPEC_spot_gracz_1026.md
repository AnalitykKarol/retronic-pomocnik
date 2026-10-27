# SPEC: zmiana spotu po 3. spotkaniu tego samego gracza (26.10.2026)

Projekt prywatny. Decyzja Karola 26.10: bot ma sam zmieniać spot („kombinacje”), gdy na spocie wielokrotnie spotyka tego samego gracza; po 3. spotkaniu
postać idzie gdzie indziej. Przypadek: Odchyd, Edron z9 zachód, gracz Statutum szedł tą samą drogą i bił te same trolle (przenosiliśmy ręcznie).
Doprecyzowanie Karola 26.10: zmiana najpierw w obrębie TEJ SAMEJ jaskini/rejonu (inne piętra i składowe), dopiero potem inne miejsce.
Kod: `spot_gracz.py` (logika), `cavebot.py` (`_spot_gracz_tick`), `nadzor.py` (`decyzja_spot_gracz`), `spoty.py` (`ta_sama_rodzina`, `wybierz(..., wyklucz_mapy, rodzina_z)`).
Test: `RETRONIC_TESTY=1 python3 -I testy/test_spot_gracz.py`. Pokrętło: `SPOT_ZMIANA_PRZY_GRACZU` (0/1, domyślnie 0).

## Podział ról (dlaczego tak)
- **Bot** wykrywa i liczy (ma dokładne obiegi, stan, pozycję) i zapisuje ZLECENIE. Sam spotu nie zmienia: restart z nową mapą to robota nadzorcy (jak
  `napraw <id> zmien_spot`), drugiego mechanizmu nie ma. Zachowanie bota na spocie jest identyczne jak dotąd (zero kliknięć, zero zużytych obiegów).
- **Nadzorca** (`nadzor.py tick`, co minutę) czyta zlecenie, sprawdza bramki, wybiera nowy spot istniejącym `spoty.wybierz` i robi ten sam restart co `zmien_spot`.
  Postać bez nadzorcy (`nadzor: false`: borsuk, pomszta, kutangen) tylko liczy i loguje; zlecenie wygasa po 20 min.

## Definicje
- **Obcy gracz**: wpis stwora z `gracz`, w oknie mapy (|dx|<=7, |dy|<=5) na piętrze postaci; NIE: własny nick, nasze postacie (`instancje/*/profil.json` `postac` +
  lista Kolanosh, Kutangen, Hammburger, Marinarra, Geblish, Wydra, Pomszta, Odchyd, Borsuk, Invincible, Dawajkesh, Makumba), NPC, widmo, martwy (hp<=0), GM,
  wróg z `wrogowie.json`, gracz z czaszką/PK (te idą ścieżką PK, której nie ruszamy).
- **Na spocie / w trakcie expienia** (26.10 ~12:08, Karol: „nie ma znaczenia czy patrol czy inne expienie”): obieg zwykłego Cavebota PO zakończonym dojściu, bez wypadu (`wypad_aktywny`, marsz do depo),
  STÓJ, stanowiska, ucieczki, stanu PK, zgonu, rozłączenia i bez stanu `WPADNIECIE`/`PAUZA_STOJ`/`STOJ_POWROT`/`WYLOGUJ_OBCY`. Kryterium NIE zależy od rodzaju trasy (pętla, patrol `patrol:*`, kieszeń) ani od piętra
  trasy: dawny warunek „piętro postaci należy do punktów trasy” usunięty (wykluczał patrol po innym piętrze i kieszenie). Miasto, depo, droga i dojście nie liczą się (obiegi niezaliczone zrywają ciągłość czasu widoku).
- **Spotkanie** = obcy nick widoczny łącznie >= `MIN_WIDOK_S` w jednym epizodzie. **Epizod** trwa, dopóki przerwy w widoku są krótsze niż `PRZERWA_S`; po przerwie
  >= `PRZERWA_S` bez nicka następne zobaczenie to NOWY epizod (nowe spotkanie). Czyli gracz kręcący się obok 10 minut = jedno spotkanie; trzy spotkania wymagają trzech
  pojawień się rozdzielonych >= 5 min.
- Licznik jest **per nick** (bez wielkości liter), w pliku `instancje/<id>/spotkania_graczy.json` (zapis atomowy tmp+replace), wpisy starzeją się po 12 h od ostatniego zobaczenia; luka w obiegach > 10 s
  nie nabija czasu widoku.
- **Licznik liczy OD OSTATNIEGO ODPALENIA BOTA NA SPOCIE** (Karol 26.10 ~12:05, pokrętło/stała `LICZNIK_OD_STARTU`, domyślnie 1; 0 = dawne zachowanie, licznik trwały 12 h przez restarty): plik niesie
  klucz `sesja` (identyfikator procesu bota `cavebot.SESJA_PROC` = `pid-czas startu`); przy tworzeniu licznika wpisy zapisane przez INNĄ sesję (albo plik bez klucza `sesja`, np. sprzed zmiany) są pomijane,
  więc restart procesu bota zeruje spotkania. Ta sama sesja (kolejny obiekt Cavebota po dojściu w tym samym procesie) nie zeruje. Zmiana spotu = restart bota = licznik od zera na nowym spocie.
  Zostają: limity zmian (`zadania`: 1/30 min, 4/dobę), unikane spoty trzymane przez nadzorcę (3 h). Zlecenie `spot_gracz_zadanie.json` niesie `sesja`; bot przy starcie kasuje zlecenie innej sesji (lub bez klucza),
  a nadzorca nie wykonuje zlecenia starszego niż start bieżącego bota (`start_bota_ep`; pokrętło `LICZNIK_OD_STARTU` w `na_zywo.json` instancji, brak klucza = 1). Pokrętło czytane przy pierwszym obiegu procesu.

## Progi (stałe w `spot_gracz.py`, każda z komentarzem)
| Stała | Wartość | Skąd |
|---|---|---|
| `SPOTKAN_MAX` | 3 | Karol |
| `PRZERWA_S` | 300 | Karol („~5 min bez niego w widoku”) |
| `MIN_WIDOK_S` | 3 | Karol 27.10: „15 s to nierealny czas, 2-3 s to już dużo; dajmy 3 sekundy” (26.10 było 15, „kilkanaście sekund”) |
| `LIMIT_ODSTEP_S`, `LIMIT_DOBA` | 30 min, 4 / dobę | Karol |
| `BEZPIECZNY_ODL`, `BEZPIECZNY_HP` | potwór w <= 4 polach blokuje; HP >= 70 % | Karol |
| `MAX_KROK_S` | 10 s | moja wartość: dwa obiegi dalej od siebie nie liczą czasu widoku |
| `STARZENIE_H` | 12 | Karol |
| `UNIKAJ_H` | 3 | moja wartość („np. 3 h” u Karola): spot, na którym spotkaliśmy gracza, jest wykluczony z wyboru |
| `ZADANIE_WAZNE_S` | 20 min | moja wartość: zlecenie starsze wygasa (bot może zlecić nowe po limicie) |
| `GOTOWY_SWIEZY_S`, `GOTOWY_CO_S` | 20 s, 3 s | moje wartości: nadzorca wykona zmianę tylko, gdy bot potwierdził spokój nie dalej niż 20 s temu |
| `ZAPIS_CO_S` | 20 | moja wartość: „ostatnio widziany” trafia na dysk najwyżej co tyle s (zmiana licznika spotkań: od razu) |

## Przebieg
1. Bot (pokrętło 1): każdy obieg po odczycie stworów -> `Licznik.obserwuj`. Licznik gracza >= 3 i `limit_ok` -> zapis `spot_gracz_zadanie.json`
   `{t, nick, spotkan, gotowy_t: null}`, licznik tego gracza od zera (bieżący epizod nie liczy się drugi raz), czas zlecenia do limitów, jedna linia w logu bota.
2. Dopóki zlecenie czeka, bot co 3 s odświeża `gotowy_t`, ale tylko gdy: HP >= 70 %, żaden żywy potwór w <= 4 polach, bez ucieczki/PK, HP nie spada (okno `GRYZIE_OKNO`).
3. Nadzorca: `decyzja_spot_gracz` -> bramki w kolejności: pokrętło `SPOT_ZMIANA_PRZY_GRACZU` == 1 w `instancje/<id>/na_zywo.json` (inaczej zlecenie wycofane), limity
   po jego stronie (z WYKONANYCH zmian), `spot_przypiety` (dawajkesh, invincible: nigdy), bot nie w walce (log), `gotowy_t` świeży. Dopiero wtedy wybór spotu, restart
   (stop bota, start na nowej mapie i tym samym trybie; `zalicz=False`, więc nie zużywa drabiny napraw), skasowanie zlecenia, powiadomienie (nick, licznik, stary -> nowy),
   zapis unikanego spotu. Nieudany start: do 3 prób na zlecenie, potem wycofanie. W cieniu (bez `NADZOR_NAPRAWY`) tylko wpis „zrobiłbym”.
4. Brak sensownego spotu: patrz „Ostatni szczebel: powrót do miasta” niżej (domyślnie powrót do depo; przy `SPOT_GRACZ_POWROT_DO_MIASTA=0`, braku danych albo spocie przypiętym postać ZOSTAJE, zlecenie kasowane, wpis `spot-gracz-brak`, bez STOP).

## Wybór nowego spotu (kolejność Karola)
`spoty.wybierz` z faktami postaci (miasto z pozycji, poziom z gry, ekwipunek) i: wykluczone mapy = bieżąca + unikane (3 h) + `SPOTY_ZAKAZANE` (+ `auto: false` w tabeli, + mapy bez wpisu
w tabeli); zajęte jaskinie innych naszych instancji odpadają jak zawsze. Potem rankingi:
1. **ta sama rodzina** co bieżąca mapa (inne piętra, składowe, kolejne mapy rejonu),
2. dopiero gdy żadna z rodziny nie pasuje: reszta tego samego miasta (z mieszaniem jaskiń jak przy `zmien_spot`).
Rodzina: pole `rodzina` w `spoty_nadzorca.json` (gdy OBA spoty je mają: równość nazw). Brak pola = zapasowe grupowanie `spoty.ta_sama_rodzina`: to samo miasto + wspólny potwór
w `potwory` mapy + środki pętli w <= 60 polach w osi x i y, bez względu na piętro. Wynik wyboru ma pole `rodzina` (czy z rodziny).
Postać w jaskini Thais z z8/z9: nowe spoty wymagają dojścia ze z7 (`spoty.wybierz`: „dojście tylko ze z7”), więc wybór zwykle daje brak, a od 26.10 ~10:50 to oznacza powrót do miasta (ostatni szczebel). Edron (`dojscie_z_dowolnego_pietra`) znajduje spot na miejscu.

## Ostatni szczebel: powrót do miasta (Karol 26.10 ~10:50)
Drabina: (1) kolejne mapy z tej samej rodziny, (2) reszta miasta, (3) **powrót do miasta**. Gdy po progu spotkań na bieżącym spocie `spoty.wybierz` NIE zwraca kandydata (wszystkie z rodziny i z miasta wykluczone:
unikany po spotkaniu graczy, zajęty przez naszą instancję, zakazany, poza widełkami poziomu, brak wymaganej liny/łopaty, dojście niemożliwe z piętra postaci), nadzorca zleca to samo, co `wroc.sh`
(plik `WROC`: bot sam idzie do depo w spokojnej chwili). Decyzja ma własny kod `spot-gracz-powrot` (akcja `wroc`, problem `spot_gracz_wroc`), wpisany na listę kodów wykonywanych na żywo przy `NADZOR_NAPRAWY`
obok `wroc-poziom` i `spot-gracz`; ZWYKŁE `wroc` (inny kod) dalej tylko w cieniu — zakaz nie jest poluzowany (test F7b). W cieniu (bez `NADZOR_NAPRAWY`) tylko wpis „zrobiłbym wroc”.
- Warunek: powrót tylko, gdy ustalono, że spotu nie ma (`brak: "spot"` z `wybierz`, albo wyczerpane `spoty_zapasowe`). Brak DANYCH (pozycja/poziom/tabela nieznane) = postać zostaje (`spot-gracz-brak`).
- Wszystkie bramki jak przy zmianie spotu: pokrętło, `spot_przypiety` (nie wraca, tylko loguje), postać bez nadzoru (`nadzor: false`: nadzorca jej nie dotyka, bot tylko liczy i loguje), walka, świeże potwierdzenie spokoju
  (HP >= 70 %, zero potworów w <= 4 polach), limity 1 / 30 min i 4 / dobę — **powrót wlicza się do tych samych limitów** (lista wykonanych zmian) i dopisuje bieżący spot do unikanych (3 h).
- Powiadomienie: jedna linia „<nick> spotkany N. raz na <spot>: brak wolnego spotu -> powrót do miasta”. WROC raz na zlecenie (zlecenie kasowane po zleceniu powrotu; nieudane `wroc.sh`: do 3 prób).
- **Postać po powrocie zostaje w depo** (bez zapętlenia): nadzorca zapisuje `instancje/<id>/spot_gracz_depo.json` (`zostan_depo.spot_gracz_depo`), który działa jak `zostan_w_depo` dla nadzorcy
  (`zostan_w_depo`: żadnego serwisu, refillu, startu na spot, wznowienia ani relogu) i dla `refill_auto.zostaje_w_depo` (bot po STOP w depo nie robi auto-refillu ani nie wraca na spot).
  Wylogowanie wg planu (`wyloguj_w_depo` / `domyslne`), znacznik sam wylogowania nie włącza. Znacznik wygasa po 12 h i gdy bot wystartował PO jego zapisie (decyzja Karola / planu); nadzorca go wtedy kasuje.
- Pokrętło: to samo `SPOT_ZMIANA_PRZY_GRACZU` (0 = nic) + `SPOT_GRACZ_POWROT_DO_MIASTA` (0/1, domyślnie 1, tylko gdy pierwsze = 1; czyta je nadzorca z `na_zywo.json` instancji, brak klucza = 1; 0 = zostaje na spocie).
- Cofnięcie: `SPOT_GRACZ_POWROT_DO_MIASTA=0` (nowe powroty stają), kasowanie `instancje/<id>/spot_gracz_depo.json` zwalnia postać z „stoi w depo”; kod: kopie `*.bak-20261026-spot-powrot`.

## Przypadki brzegowe
- Gracz stoi przy nas cały czas -> jedno spotkanie, nie zmiana. Wraca po godzinie 3 razy -> zmiana (licznik przeżywa wyjścia do depo i restarty).
- Gracz widziany podczas wypadu/dojścia/w mieście -> nie liczy się. Wróg z PK -> ścieżka PK, nie licznik.
- Zmiana zlecona, ale nadzorca nie wykona (walka, brak potwierdzenia, limit): zlecenie wygasa po 20 min; kolejne dopiero po następnych 3 spotkaniach i limicie bota.
- Pokrętło 0: ani odczytu, ani zapisu, ani linii w logu (bit w bit). Zmiana pokrętła na gorąco; kod działa po restarcie bota (żywe procesy mają stary kod).
- Plik licznika uszkodzony -> start od zera; zapis nieudany -> linia w logu, postać zostaje.
- Limity: bot (zlecenia) i nadzorca (wykonane zmiany) liczą niezależnie: 1 na 30 min, 4 na dobę.

### Próg widoku 15 s -> 3 s (27.10, Karol)
Decyzja Karola 27.10: „15 sekund to nierealny czas, 2-3 sekundy to już dużo; dajmy 3 sekundy”. Zmieniona tylko stała `MIN_WIDOK_S` (15 -> 3); pozostałe progi bez zmian. Zależności sprawdzone:
- Widok liczy się z kroków między KOLEJNYMI obiegami z nickiem; krok > `MAX_KROK_S` (10 s) nie liczy się. Dla 3 s potrzeba więc ciągłych obiegów, ale widok w epizodzie jest ŁĄCZNY (jak dotąd): trzy mignięcia po 1 s w < 5 min = 3 s = jedno spotkanie (test A2c2).
- `PRZERWA_S` (300 s) bez zmian: to ona, nie próg widoku, rozdziela spotkania; gracz kręcący się obok > 5 min bez przerwy to nadal JEDNO spotkanie. `ZAPIS_CO_S` (20 s) dotyczy tylko „ostatnio widziany”; zaliczone spotkanie zapisuje się od razu, więc krótszy próg nic nie gubi.
- Licznik działa tylko na spocie (`cavebot._sg_aktywny`: bez dojścia, wypadu, STÓJ, ucieczki, PK, WPADNIĘCIA), więc mijanie graczy w mieście, w depo i na dojściu nie nabija spotkań także przy 3 s. Na spocie nabija każde przejście obcego przez okno mapy 15x11 trwające >= 3 s (przechodnie, nie tylko stojący).
- Skutek na telemetrii (7 botów, raport `--dzien`): 26.10 spotkań wg reguł bota 3 (15 s) -> 16 (3 s), a bez progu 20; 27.10 do 13:25 2 -> 4 (bez progu 4). Z licznikiem od restartu bota (sesje) tylko jeden przypadek dobija do 3: Geblish/Vados 26.10 ok. 09:27; zmiana spotu dalej wymaga 3 spotkań TEGO SAMEGO gracza rozdzielonych >= 5 min, limity 1/30 min i 4/dobę nadzorcy bez zmian.
- Nazwy pól `spotkan_prog15`, `nicki_prog15`, `bywalec_prog15` w raporcie, API okna i testach zostają (historyczne; czytają je okno i testy); wartość progu to zawsze `SG.MIN_WIDOK_S`. Opisy w oknie (zakładka/karta „Spotkania”) i raporcie podają „3 s”.
- Proces bota czyta stałą z `spot_gracz.py` przy pierwszym imporcie, więc bot podejmie 3 s dopiero po restarcie procesu (nadzorca importuje moduł przy każdym ticku, ale progu widoku nie używa).
Cofnięcie: `MIN_WIDOK_S = 15` w `spot_gracz.py` albo kopie `*.bak-20261027-widok3`.

## Czego NIE robi
Nie rusza progów ucieczki/PK/HP/ognia, nie klika, nie zatrzymuje bota w walce, nie zmienia spotu przypiętego, nie reaguje na wrogów z listy PK (osobna ścieżka), nie wchodzi na spoty
`auto:false`/zakazane, nie wysyła niczego poza jednym powiadomieniem przy zmianie. NIESPRAWDZONE NA ŻYWO: pełny restart na nowym spocie z tej ścieżki (to samo wywołanie co `zmien_spot`),
wiarygodność odczytu graczy z `stwory` w kliencie, dobór progów 3 s / 5 min na prawdziwym ruchu.

## Raport spotkań z telemetrii (26.10 ~12:10, tylko ODCZYT): `narzedzia/spotkania_graczy_raport.py`
`python3 -I narzedzia/spotkania_graczy_raport.py [--dzien RRRRMMDD | --od-startu] [--instancja ID] [--json] [--min-widok S] [--przerwa S]`. Dla każdej instancji liczy z `logi/telemetria-*.jsonl` (próbki `typ: probka`)
TYMI SAMYMI regułami co bot (ten sam `spot_gracz.Licznik`, wersja w pamięci `Licznik(None)`): nick `gracz:true` w `stwory`, nie nasze (profil.json + lista), nie własny, HP > 0, nie GM; spotkanie = >= `MIN_WIDOK_S` (od 27.10 3 s; wcześniej 15 s) w epizodzie, przerwa 300 s.
„Na spocie” = stan inny niż WYPAD/WPADNIECIE/PAUZA_STOJ/STOJ_POWROT/WYLOGUJ_OBCY/brak i próbka poza DOJŚCIEM (z `logi/mozg-stdout-MMDD-GGMM.log`: „Dojście: trasa” bez jeszcze „Dojście zakończone” = dojście; brak „Dojście:” = od razu na spocie).
Domyślnie od ostatniego startu bota (ostatnia `sesja` telemetrii), `--dzien` = cały dzień. Wyjście: tabela (instancja, postać, czas na spocie, graczy, spotkań, spotkań/h, najczęstsi nicki z licznikami) albo JSON.
**Dlaczego bez geometrii trasy** (pierwsza wersja filtrowała próbki ≤ 8 pól od punktów pętli z `tryb.log`): (1) patrol (`patrol:troll`, Wydra) nie ma pętli — filtr dawał 0 h; (2) Pomszta 26.10 miała w `tryb.log` i w `Mózg:` trasę
`rook_raty_z8_petla` (491 pkt, z8 x 32022..32116, y 32190..32234), ale CAŁY dzień expiła w kieszeni (x 32011..32035, y 32161..32171, spadki na z9: `[RATUNEK] cień: S2 złe piętro`; 7794 z 9517 próbek <= 8 pól od
`rook_raty_z8_kieszen_petla`, tylko 4 próbki od jej własnej pętli) — nazwa trasy w logach nie opisuje miejsca expienia; (3) dla Pomszty 25.10 geometria dawała 1,91 h, stan bota 4,63 h (przed 20:04 była na `rook_raty_z9`).
Regresja (fixture z prawdziwej telemetrii 25.10, `testy/dane/spotkania_graczy`): oficjalne reguły Stekt 10, Flower Power 5, Hansi 0, Apock 3; z `--min-widok 5` Stekt 10, Flower Power 7, Hansi 4, Apock 3 (ręczne liczenie Karola: 10, 7, 3, 4 —
najbliższe progowi ~5 s, nie dokładnie). Wydra 25.10 (patrol): ~8,2 h na spocie, 5 graczy. Granice: telemetria nie niesie listy wrogów PK ani czaszek (raport może liczyć więcej niż bot), czas „na spocie” zawiera marsz między celami i spadki bez WPADNIECIE.
