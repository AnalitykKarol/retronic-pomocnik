# SPEC: wybór robionej runy (GFB) w każdym trybie + jedzenie dowolnego jedzenia w trybie stanowisko (27.10.2026)

Decyzje Karola 27.10 (zatwierdzone): (A) w każdym trybie, w którym bot robi runy, pokrętło wyboru robionej runy; domyślnie DOKŁADNIE
dzisiejsze zachowanie; GFB = Great Fireball. (B) w trybie `stanowisko` postać je dowolne jedzenie z bagu, ham zostaje pierwszym wyborem.
Żadna postać nie jest teraz przełączana na GFB. Strzelanie GFB w walce NIE wchodzi w zakres (strzał zostaje przy HMM).
Poziom zgody 1 (repo bota), kod działa dopiero po restarcie bota i tylko po włączeniu pokrętła.

## 1. Stan zastany (dowody)

- Runy robi JEDNO miejsce: `cavebot.Cavebot._uh` -> `uh.ustaw(UH_CZAR, klawisz=UH_KLAWISZ, koszt=UH_KOSZT)` -> `uh.zrob_runa`. Tryby `runy`, `uh`, `stoj`
  (`stanowisko.py`), wyprawy, `blanki_start.py`, serwis i `pokretla.py` tylko dostarczają blanki, układ okien i pokrętła; same runy nie powstają nigdzie indziej
  (`tryb_obronny` robi runę LECZENIA osobnym polem `UH_LECZ_*`, `runa_klik.py` strzela). Zmiana w `_uh` obejmuje więc wszystkie tryby.
- Weryfikacja rzutu w `uh._cast` jest niezależna od rodzaju runy: slot ręki zmienia zawartość z blanka (3147) na cokolwiek innego i mana spada.
  Hotkey rzuca czar; bot NIE wpisuje słów czaru (`UH_CZAR` to tylko log/telemetria).
- Dziś: tryb `runy` = `adori gran` (HMM 3198), F6, 70 many; tryb `uh` = `adura vita` (UH 3160), F7, 100 many (`tryby.json`). Pokrętła `UH_CZAR`
  (tekst: adori gran / adura gran / adura vita / adura), `UH_KLAWISZ`, `UH_KOSZT` już istnieją, ale nie obejmują GFB, a zmiana jednego bez pozostałych daje
  niespójny zestaw. `UH_MANA_MIN` bramkuje start (koszt jest podnoszony do `max(koszt, min(UH_MANA_MIN, max_mana))`).
- ID runy GFB = 3191: jest w `loot.ID_RUN_W_POJEMNIKU` i `okno_api.RUNY_NAZWY` (status "GFB"). Nie ma go w `serwis_akcje.ID_RUNY_BAGU`,
  w kontroli baga do depo (`_sprawdz_bag_do_depo` rozpoznaje tylko UH 3160), w `wyprawa.ID_DEPO_ZLOZ` ({3160}) i w `mozg.policz_uh` (ogłoszenia Trade liczą tylko UH).
- Jedzenie (B): obsługa jest już ogólna. `cavebot.jedzenie_potrzebne` -> `cb.zjedz` -> `loot.zjedz` je pierwsze znalezione jedzenie z `loot.KOLEJNOSC_JEDZENIA`
  (27 ID z `dane_tibia/przedmioty.json`, ham 3582 i dragon ham 3583 na początku, banana 3587 w środku listy). Zapas (`loot.ile_jedzenia`), wyprawa i
  `wypad.py` też liczą wszystkie ID. Hamu na sztywno wymaga TYLKO serwis: `serwis_akcje.stan_cap` i `brakuje("ham")` liczą wyłącznie ham 3582, więc krok `cap`
  (`SERWIS_HAM_MIN`) kupuje ham u postaci, która ma banany (komentarz pokrętła mówi "gdy postać nie ma jedzenia"). Fallback obrazkowy `loot.JEDZENIE`
  (ham/meat/cheese) działa tylko gdy pamięć klienta nie działa; bez zmian.

## 2. Co zmieniam (A: wybór runy)

| Pokrętło | Gdzie | Zakres | Domyślnie | Kierunek (analityk) |
|---|---|---|---|---|
| `UH_RUNA_WYBOR` | `TEKSTY` w `pokretla.py`, stała w `cavebot.py` | `domyslna` albo `gfb` | `domyslna` (= dzisiejsze zachowanie: `UH_CZAR`/`UH_KLAWISZ`/`UH_KOSZT` z trybu) | tekst: analityk nie może ruszyć, tylko Karol w `na_zywo.json` |
| `UH_GFB_KLAWISZ` | `TEKSTY` | `""` albo F1..F12 | `""` (brak = GFB nie startuje; nigdy nie rzuca innym klawiszem) | tekst, tylko Karol |
| `UH_GFB_KOSZT` | `ZAKRESY` | 1..500 | 120 (obie paczki danych zgodne: serwer74 `Mana 120`, serwer76 `mana 120`) | `nie_nizej` |
| `UH_GFB_PRZERWA_S` | `ZAKRESY` | 0..7200 | 0 (= jak dziś: tylko pauza po 3 porażkach, `UH_PRZERWA_PO_PORAZKACH_S`) | `nie_nizej` |

Słowa czaru GFB (`adori gran flam`) to stała `UH_GFB_CZAR` (log/telemetria, jak `UH_CZAR`), nie pokrętło.

Działanie przy `UH_RUNA_WYBOR=gfb`: `cavebot._uh_runa()` zwraca (`adori gran flam`, `UH_GFB_KLAWISZ`, `UH_GFB_KOSZT`) zamiast (`UH_CZAR`, `UH_KLAWISZ`, `UH_KOSZT`).
Ta trójka zastępuje tamtą wszędzie, gdzie `_uh` i `_uh_walka_ok` liczą próg many i wołają `uh.ustaw`. `UH_CZAR`/`UH_KLAWISZ`/`UH_KOSZT` nie są nadpisywane
(`tryb_obronny` czyta je do runy leczenia). Próg many GFB = `max(UH_GFB_KOSZT, min(UH_MANA_MIN, max_mana))`: aby zostawić zapas na exurę, Karol podnosi
istniejące `UH_MANA_MIN` (np. 145). Przy wyborze `gfb` bez `UH_GFB_KLAWISZ` `_uh` nie robi runy (jedna linia w logu na proces), ale przywracanie
zdjętej tarczy (`restore`) działa jak zawsze.

Ochrona przed brakiem soul (bot soul NIE odczytuje, patrz 4): porażka `nieudany_cast` (dwa rzuty bez zmiany slotu) przy GFB i `UH_GFB_PRZERWA_S` > 0
wydłuża pauzę UH do `UH_GFB_PRZERWA_S` (log + telemetria `uh_run`). Przy 0 działa dotychczasowy limit: 3 porażki z rzędu = pauza `UH_PRZERWA_PO_PORAZKACH_S`.

Rozpoznanie runy GFB w serwisie (bez zmiany zachowania dla UH/HMM): `serwis_akcje.ID_GFB = 3191` dopisany do `ID_RUNY_BAGU` i do kontroli
`_sprawdz_bag_do_depo` (bag z blankami i GFB nie jest "nowym bagiem"); `wyprawa.ID_DEPO_ZLOZ` = {3160, 3191} (dotyczy tylko `WYPRAWA_DEPO_ZLOZ=1`).
Nie zmieniam: `mozg.policz_uh` / ogłoszeń Trade (liczą UH), strzału GFB, `PK_UH_*`, planu postaci i wyboru trybu.

## 3. Co zmieniam (B: jedzenie)

- Jedzenie z bagu w stanowisku: BEZ zmian kodu eating (`loot.zjedz` już je dowolne jedzenie z listy; ham pierwszy). Dodaję test, który to pilnuje
  (banan bez hama, ham przed bananem).
- Serwis: pokrętło `SERWIS_JEDZENIE_DOWOLNE` (0/1, `ZAKRESY`, grupa "Wyprawa i serwis", czyta je `serwis.py` z `na_zywo.json`, jak pozostałe `SERWIS_*`).
  Domyślnie 0 = dzisiejsze liczenie samego hama. Przy 1 krok `cap` (minimum `SERWIS_HAM_MIN`) i oszacowanie kosztu liczą jako jedzenie wszystkie ID
  z `loot.JEDZENIE_ID` (sztuki), więc postać z bananami nie dostaje "minimum ham". Zakup w kroku `jedzenie` dalej celuje w ham (ham = preferowany zapas).
  `cel_ham` (rezerwa capa) bez zmian. Pokrętło: kierunek `nie_wyzej` (analityk nie włącza).
- Tryb `stoj` w `tryby.json` dostaje `SERWIS_JEDZENIE_DOWOLNE: 1` (tylko stanowisko, zgodnie z decyzją; inne tryby zostają przy 0).
  Skutek dopiero przy następnym zastosowaniu trybu `stoj` na instancji; teraz żadna instancja nie jest ruszana.

## 4. UNKNOWN i pytania otwarte

1. **Serwer 74 czy 76: UNKNOWN (brak dowodu).** Repo nie ma deklaracji wersji serwera Retronic. Za 7.4: README `dane_tibia` ("Tibia 7.4", ID z `objects.srv` zgadzają się z klientem:
   gold 3031, UH 3160, HMM 3198), "UH od lvl 11" (`SPEC_stoj_runy_1022.md`, zgodne z serwer74 `LevelCast` 11). Za 7.6: komentarz `uh.py:39` ("UH wymaga lvl 24", zgodne z
   serwer76 `lvl 24`) oraz "UH wymaga ML 11" (serwer76 `maglv 11`; serwer74 nie ma ML w czarach). Wymagania Karola "HMM od lvl 10" nie pasują do żadnego zestawu (74: lvl 3, 76: lvl 25).
   Wniosek: bot nie sprawdza poziomu ani ML przy GFB; Karol ustala, czy postać może rzucić (74: lvl 9, S/D; 76: lvl 23, ML 9, soul 3, S/MS/D/ED). Wspólne dla obu: runa 3191 (74), mana 120.
2. **Soul: bot go NIE odczytuje** (grep w kodzie: brak; `AUDYT_odczyt_i_mapa.md`: "Soul points [BRAK]"). `dane_tibia/ml_pamiec_1022/NOTATKI.txt` notuje kandydata: w bloku gracza
   (doubles) `+0x60 = 100.0 (soul?)`, niezweryfikowany, nie używam. Zużycie soul na runę: serwer76 `soul 3`; w serwer74 brak pola. Regeneracja soul: UNKNOWN. Skutek: gdy soul się wyczerpie,
   rzut GFB nie powstanie i UH zakończy próbę `nieudany_cast` (tarcza wraca; tak samo jak dziś przy każdym nieudanym rzucie). `UH_GFB_PRZERWA_S` jest jedyną ochroną; wartości NIE zgaduję
   (domyślnie 0). Zalecenie: po pierwszej próbie na żywo zmierzyć, ile run starcza z pełnego soul, i dopiero wtedy ustawić pauzę.
3. **Hotkey GFB w kliencie** musi istnieć (`adori gran flam` na wybranym F-klawiszu); bot nie wpisuje czarów. UNKNOWN, czy klient przyjmie hotkey tego czaru na tej postaci.
4. **Czy blanki z `blanki_start`/`serwis` i pojemnik na runy wystarczają GFB**: GFB zajmuje 1 pole jak UH (ładunki 2 wg serwer76 `charges 2`, w serwer74 brak). Niepotwierdzone na żywo.
5. Banan: ID 3587 pochodzi z `dane_tibia/przedmioty.json` i listy startowej `loot.JEDZENIE_ID` (komentarz: potwierdzone na żywo tylko cheese 3607 i meat 3577). Do potwierdzenia jednym odczytem
   `kontenery` na postaci z bananem. Jedzenie w zagnieżdżonym worku (nie "plecak") nie jest widziane przez `_jedzenie_z_pamieci`: poza zakresem.

## 5. Non-goals

Strzał GFB; wybór runy automatyczny (plan postaci, grafik, nadzorca); odczyt soul/ML/poziomu; sprzedaż/Trade GFB; zmiana trybów `runy`/`uh`/`stoj` poza jednym kluczem serwisu w `stoj`;
dotykanie instancji, `na_zywo.json` instancji, profili, STOP/STOP_RECZNY, uruchamianie czegokolwiek w grze.

## 6. Jak włączyć i cofnąć

- Włączenie (bot musi być zrestartowany na nowym kodzie; po tym pokrętła są "na gorąco"), po ustawieniu hotkeya `adori gran flam` w kliencie:
  `python3 -I okno_api.py ustaw --instancja <id> UH_RUNA_WYBOR=gfb UH_GFB_KLAWISZ=F8` (ewentualnie `UH_MANA_MIN=145`, `UH_AKTYWNY=1` albo tryb `uh`/`runy`/`stoj`).
- Cofnięcie: `okno_api.py ustaw --instancja <id> UH_RUNA_WYBOR=domyslna` (albo skasować klucz z `na_zywo.json`). Kod: kopie `*.bak-20261027-gfb`
  (`cavebot.py`, `pokretla.py`, `na_zywo.przyklad.json`, `serwis.py`, `serwis_akcje.py`, `wyprawa.py`, `tryby.json`, `STAN.md`) + restart; usunąć `testy/test_gfb_runa.py`, `testy/test_jedzenie_dowolne.py`.
- Jedzenie: `SERWIS_JEDZENIE_DOWOLNE=0` w `na_zywo.json` instancji.

## 7. Testy (offline)

`testy/test_gfb_runa.py`: domyślnie bez zmian (klawisz/koszt/czar jak w trybie, próg many), wybór GFB (czar, klawisz, koszt 120, próg many, tryb walki), brak klawisza = brak rzutu,
restore działa, przerwa po `nieudany_cast`, walidacja pokręteł (zakresy, analityk nie ruszy), tryby, `na_zywo.przyklad.json`, rozpoznanie 3191 w serwisie.
`testy/test_jedzenie_dowolne.py`: banan bez hama jest jedzony, ham przed bananem (`loot`), serwis liczy dowolne jedzenie (pokrętło 0 = stare, 1 = nowe), `stoj` ustawia pokrętło.
