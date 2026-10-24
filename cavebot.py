#!/usr/bin/env python3
"""Cavebot dla Retronic: chodzi nagraną trasą, bije potwory, zbiera loot, je i ucieka.
Wszystkie decyzje na podstawie odczytu pamięci (bot.zapytaj), bez rozpoznawania obrazu.

  cavebot.py <trasa> [-o OKRAZENIA] [-c MINUTY] [--prog-hp 40] [--jedzenie KLAWISZ]
             [--potwory "Rat,Cave Rat"] [--ignoruj-graczy] [--stop-przy-graczach]

Stany: IDZ, WALKA, LOOT, JEDZENIE, UCIECZKA, GRACZ (pauza, gdy na ekranie gracz groźny: PK/GM/CM/God/Tutor;
zwykły obcy gracz tylko się loguje, a --stop-przy-graczach przywraca stare "każdy gracz zatrzymuje").
Zatrzymanie: plik STOP w katalogu pomocnika albo Ctrl+C.
"""

import argparse
import heapq
import json
import os
import random
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bot  # noqa: E402
import czaszka  # noqa: E402
import instancja  # noqa: E402
import widma  # noqa: E402

ZASIEG_X, ZASIEG_Y = 7, 5          # widok mapy: |dx|<=7, |dy|<=5
CZAS_JEDZENIA = 30                 # s bez żadnego wzrostu HP (regeneracja działa też w walce) -> głód
ZACIECIE_ATAKU = 6.0               # s: potwór obok bez spadku HP -> ponów atak bez patrzenia na ramkę
PONOWIENIE_ATAKU = (2.0, 3.5)      # s bez spadku HP celu -> sprawdź ramkę i w razie potrzeby ponów atak
LIMIT_WALKI = 90                   # s na jeden cel, potem go ignorujemy
IGNOROWANIE = 60                   # s ignorowania celu po przekroczeniu limitu
CZEKANIE_NA_CEL = (3.0, 6.0)       # s stania w miejscu, aż cel sam podejdzie (tylko z --czekaj)
HP_UCIEKAJACEGO = 50               # % HP celu, poniżej którego go gonimy od razu (potwory uciekają)
POGON_ZASIEG = 10                  # pola: uciekający cel poza ekranem gonimy, dopóki jest tak blisko
POGON_LIMIT = 14.0                 # s bez zmniejszenia dystansu do celu, potem odpuszczamy
POGON_TWARDY = 40.0                # s: twardy limit pościgu za prawie martwym celem (<= POGON_DOBICIE_HP w zasięgu)
POGON_TWARDY_INNY = 25.0           # s: twardy limit pościgu za innym uciekającym (od chwili, gdy zaczął uciekać)
POGON_RUCH = 1.5                   # s: bot ruszył się tak niedawno = zbliża się po drodze (to nie jest "brak postępu")
POGON_ROZRZUT = 1                  # pola: ruch bota liczy się jako postęp, gdy cel nie oddalił się od poprzedniej oceny o więcej
POGON_LUKA = 1.5                   # s: przerwa w pościgu (jedzenie, loot) dłuższa niż to nie liczy się do braku postępu
POGON_IGNOROWANIE_DOBICIE = 8      # s ignorowania uciekającego celu odpuszczonego z braku postępu (potem próba od nowa)
UCIEKAJACY_HP = 30                 # % HP: taki cel zawsze uważamy za uciekającego (niezależnie od progu)
BLOKADA_STOI = 4.0                 # s: bot stoi w pościgu, a świeży potwór obok blokuje drogę = bijemy świeżego
POGON_DOBICIE_HP = 20              # % HP: taki cel w zasięgu DOBICIE_ZASIEG gonimy do POGON_TWARDY
DOBICIE_ZASIEG = 6                 # pola: ranny cel tak blisko dobijamy (nie zamieniamy na świeżego)
DOBICIE_ZASIEG_UCIEKAJACY = 10     # pola: uciekającego (hp <= próg+10 albo <= UCIEKAJACY_HP) gonimy tak daleko
DOBICIE_MARGINES = 15              # pp nad progiem ucieczki: tak ranny cel to dobicie
DOBICIE_PREMIA_MARGINES = 10       # pp nad progiem ucieczki: tak ranny cel dostaje premię w wyborze celu
DOBICIE_PREMIA = 6.0               # pola: premia w sortowaniu celów (dobicie ważniejsze niż świeży cel)
GRYZIE_OKNO = 2.0                  # s: HP gracza spadło tak niedawno = ktoś nas gryzie
GRYZIE_SPADEK_PP = 3.0             # pp max HP: tyle HP musi spaść w GRYZIE_OKNO (mniejszy skok to szum odczytu)
ROZPRAWA_SPOKOJ = 6.0              # s po powrocie do rannego, gdy blokuje/tlum nie odpalają ponownie (tylko gryzie)
POSCIG_GRYZACY_MIN_HP = 30         # % HP celu: ranny cel (HP <= tyle) w odl <= 3 nie jest porzucany przez gryzącego obok (0 = wyłączone)
ROZPRAWA_BLOK_MIN_HP_CELU = 30     # % HP celu: ranny cel (HP <= tyle) w odl <= 2 nie jest zasłaniany blokującym (obejście zamiast bicia; 0 = wyłączone)
PATROL_POWROT_DO_CELU = 1          # 1 = po walce wracamy do pierwotnego celu patrolu (jeśli nie dalej niż PATROL_POWROT_MAX_ODL), zamiast brać bliższe miejsce
PATROL_SWEEP = 1                   # 1 = wizyta w miejscu zachodnim (zrodlo B) = przeczesanie nagranej trasy zachodu (PATROL_SWEEP_PLIK)
PATROL_SWEEP_PLIK = "nowe_miejsca.json"  # trasa zachodu w trasy/ (lista punktow x,y,z)
PATROL_SWEEP_MIN_S = 480.0         # s: min. przerwa miedzy poczatkami sweepow zachodu
PATROL_SWEEP_WSCHOD_MIN = 3        # tyle wizyt w miejscach nie-B (wschod) musi byc po sweepie, zanim ruszy kolejny
PATROL_SWEEP_BLISKO = 3            # pola: miejsca B tak blisko trasy sweepu liczą się po nim jako odwiedzone
PATROL_CZAS_SKALA_S = 300.0        # s: waga miejsca rośnie o 1x co tyle sekund od ostatniej wizyty...
PATROL_CZAS_MAX = 3.0              # ...ale najwyżej o tyle (mnożnik 1 + min(czas / skala, max)); 0 = bez wpływu czasu
PATROL_POWROT_MAX_ODL = 40         # pola: dalszy pierwotny cel jest porzucany po walce
ROZPRAWA_BLOK_MAX = 15.0           # s: rozprawa z blokującym drogę do rannego (przerywana dopiero po tym czasie)
BLOK_OBJAZD = 3                    # pola: droga z zajętymi polami dłuższa o tyle niż bez nich = cel zasłonięty przez moby
ROZPRAWA_MAX = 8.0                 # s: tyle czasu na rozprawę ze świeżym po "Zmianie celu" (potem wolny wybór); w tym czasie nie wracamy do uciekającego
OBJAZD_DOBICIE = 7                 # s ignorowania prawie martwego celu za ścianą (zamiast OBJAZD_IGNOROWANIE)
POSCIG_ATAK_CO = 2.5               # s: min. odstęp między klikami ponawiającymi atak w pościgu (Alt+klik to przełącznik)
POSCIG_ATAK_ODCZYTY = 2            # tyle kolejnych odczytów flagi "atakowany" = False przed ponowieniem
ATAK_INNY_CEL = False              # cel bota obok, flaga ataku False, a gra celuje w kogoś innego: klik od razu (max 1 na 1.5 s na cel)
ATAK_INNY_CEL_CO_S = 1.5           # s: min. odstęp między takimi klikami na tego samego celu (Alt+klik bywa przełącznikiem)
ATAK_LIMIT_KLIKOW = 5              # tyle kliknięć "ramka_false" na tym samym celu bez spadku jego HP, potem: Escape (zdejmuje stary cel), ignoruj cel
ATAK_LIMIT_IGNOROWANIE = 30        # s ignorowania celu po przekroczeniu ATAK_LIMIT_KLIKOW (13.10: pętla ataku po przelogowaniu)
MAPA_ZAPOMNIJ_KLIKI = 3            # 23.10: tyle kliknięć ataku "ramka_false" z rzędu (na jakichkolwiek celach) bez spadku HP żadnego celu = prostokąt mapy w cache ekran.py mógł być zły (wydra po serwisie: 136x ramka_false): ekran.zapomnij_prostokat; 0 = wyłączone
MAPA_ZAPOMNIJ_CO_S = 60.0          # s: min. odstęp między takimi unieważnieniami (bez pętli, gdy kliki nie działają z innej przyczyny)
ATAK_TYLKO_PRZY_CELU = True         # na serwerze do 8 lvla atak działa tylko tuż obok celu (dystans <= 1): bez klików z dystansu; False = dawne zachowanie
POSCIG_ATAK_WERYF = 0.0            # s blokującej weryfikacji po kliku; 0 = flagę czytamy w następnym obrocie pętli
POSCIG_ATAK_WERYF_MIN = 0.3        # s po kliku, zanim flaga w następnym obrocie liczy się jako weryfikacja
POSCIG_ATAK_WERYF_MAX = 2.0        # s po kliku: po tym czasie weryfikację porzucamy (flaga i tak bywa nieaktualna)
POSCIG_ATAK_BLOK = 10.0            # s: blokada ponawiania ataku na tym celu po nieudanej weryfikacji
JEDZENIE_PONOW = 240               # s: po "brak jedzenia" nie ponawiamy próby
JEDZENIE_BLISKO = 3                # pola: przy celu/potworze tak blisko nie jemy klawiszem (jedzenie z plecaka trwa 3-5 s)
JEDZENIE_SPOKOJ = 8                # pola: jedzenie z plecaka (3-5 s bloku) tylko, gdy w tym promieniu nie ma potwora
TRASA_STOP_PRZY_POTWORZE_R = 4     # pokrętło 0-8 (nie_nizej): potwór z listy w tym promieniu (to samo piętro) wstrzymuje krok trasy i przejście pięter; 0 = wył.
TRASA_STOP_MAX = 5                 # tyle kolejnych obiegów wstrzymania trasy bez walki, potem idziemy dalej (bezpiecznik przed zawieszeniem)
TRASA_SWIEZY_SKAN_S = 1.5          # s po zmianie piętra: każdy odczyt stworów to świeży skan (nie cache rdzenia do 0,5 s)
JEDZENIE_W_WALCE = 1               # pokrętło 0/1 (nie_nizej): 1 = głód wykryty po HP jemy też w walce (obok trolla), gdy bezpiecznie
CZAS_JEDZENIA_WALKA = 20.0         # pokrętło (10-60, nie_wyzej): s bez wzrostu HP z regeneracji (nie z exura), potem jemy w walce
JEDZENIE_WALKA_HP_MARGINES = 20    # pokrętło (10-60, nie_wyzej): pp nad progiem ucieczki; poniżej leczenie/ucieczka mają pierwszeństwo
JEDZENIE_WALKA_PLECAK_PP = 5       # pp HP na każdego potwora w odl <= 2 dodane do marginesu, gdy jemy z plecaka (blok 3-5 s)
JEDZENIE_WALKA_LECZENIE_S = 3.0    # s po rzucie exura, w których wzrost HP liczymy jako leczenie, nie regenerację
JEDZENIE_WALKA_PONOW_S = 90.0      # s: min. odstęp między jedzeniem w walce (zapobiega pętli przy fałszywym alarmie)
JEDZENIE_MANA_BRAK_S = 90.0      # pokrętło (30-600): mana < max, bot nie rzucał czaru i mana nie rośnie tyle s = głód (jemy)
JEDZENIE_LOG_S = 3600              # s: "brak jedzenia" w logu (i powiadomieniu) najwyżej raz na tyle
ALARM_HP_S = 300                   # s: alarm "niskie HP" najwyżej raz na tyle (bez pętli co 15 s)
PAUZA_BLISKO = 3                   # pola: potwór tak blisko wyłącza długie, ślepe pauzy na trasie
LOOT_W_WALCE = True                # loot odłożonych zwłok w trakcie walki: po jednym atomowym kroku na obieg (False = dawne: dopiero po walce)
LOOT_W_WALCE_HP = 0                # % HP gracza: twarda dolna granica bezwzględna (0 = wyłączona; pokrętło tylko w górę)
LOOT_W_WALCE_HP_MARGINES = 15      # pp nad progiem ucieczki (prog_aktualny): loot w walce tylko, gdy HP jest wyżej; pokrętło 15-40 (tylko w górę)
LOOT_W_WALCE_STYKAJACE = 2         # maks. żywych potworów w odl 1 (z celem); 3+ przerywa (tłum: analiza-tlum.md); pokrętło 1-2 (tylko w dół)
LOOT_POD_NOGAMI_PIERWSZE = True    # loot: Ctrl+klik własnego pola (0,0) zaraz po polu zgadniętym i alternatywnym, budżet LOOT_MAKS_PROB pól (False = dawne 3x3 po kolei); pokrętło 0-1
LOOT_RETRY_DALEJ = 0               # ile dodatkowych rund po wyczerpaniu budżetu LOOT_MAKS_PROB (12.10: 2 -> 0, rundy marnowały czas)
LOOT_MAKS_PROB = 4                 # ile różnych pól maks. klikamy przy jednym otwieraniu zwłok (pokrętło 1-9; 12.10: 3 -> 4)
LOOT_PONOW_LOKALNIE = 1            # 12.10: brak okna, budżet pól wyczerpany, w widoku brak żywych mobów: tyle razy ponów loot od razu (bez czekania na model)
LOOT_POMIN_CIEZKIE = 0            # 13.10 (P5): 1 = przedmiot, który nie mieści się przez cap (za_ciezki), pomijamy w lootcie na 300 s (domyślnie 0: tylko klasyfikacja i log; pokrętło 0-1)
POSCIG_BEZ_ZMIANY_PIETRA = True    # 12.10: pościg/podejście nigdy nie wchodzi na schody/dziurę (zmiana piętra); tylko wypad do miasta wolno; pokrętło 0-1
TRASA_PIETRA = 2                   # 13.10: trasa wielopiętrowa w pętli łowiska (pietra.py): 0 = wyłączona, 1 = zawsze, 2 = tylko gdy trasa ma > 1 piętro (domyślnie); pokrętło 0-2
PIETRA_MAX_S = 150.0               # s na jedno przejście pięter (dojście do schodów + próby), potem porażka (zawrócenie trasy)
PIETRA_PORAZKI_STOP = 3            # tyle porażek przejścia z rzędu = bot przerywa (powiadomienie krytyczne)
WPADNIECIE = 1                     # 15.10: pokrętło 0/1: 1 = niespodziewana zmiana piętra (wpadnięcie w dziurę) = nauka dziury, wyjście liną / planem po mapie, a gdy się nie da ALARM + STOP (wpadniecie.py)
WPADNIECIE_LINA = 1                # pokrętło 0/1: 1 = pierwsza próba wyjścia: Use liny na polu lądowania (rope spot pod dziurą)
WPADNIECIE_LINA_PROB = 3           # prób liny (pokrętło 1-5)
WPADNIECIE_PLAN = 1                # pokrętło 0/1: 1 = gdy lina nie działa, plan wielopiętrowy po mapie i przejściach z danych (wykonuje pietra.py)
WPADNIECIE_ODL = 3                 # pola: tak blisko poprzedniej pozycji musi być lądowanie, żeby zmiana piętra była upadkiem (nie teleportem/śmiercią); pokrętło 1-6
WPADNIECIE_PLAN_PULE = 0           # pokrętło 0/1 (domyślnie 0 = jak dotąd): 1 = plan wpadnięcia liczy drogę do PLAN_MAX_KAND najbliższych PEWNYCH przejść i osobno do tylu niepewnych z flag mapy (w mieście niepewne „w górę” zajmowały wszystkie miejsca i znane schody/kratki nie były liczone; SPEC_kratki_drabiny_thais_1021 F2)
LOOT_BEZ_DRABIN = 0                # pokrętło 0/1 (domyślnie 0 = jak dotąd): 1 = loot nie robi Ctrl+klik (Use) na polu drabiny (wspina postać piętro wyżej); drabiny z przejść w danych + nauczone przy wyjściu w górę (trasy/drabiny_nauczone.json; SPEC_kratki_drabiny_thais_1021 F3)
LOOT_BEZ_DZIUR = 1                 # 23.10 pokrętło 0/1 (domyślnie 1; zgon odchyda: Ctrl+klik lootu w pole dziury (32354,32131,z8) = upadek do kieszeni na z9): 1 = loot nie robi Ctrl+klik w pole dziury z listy (nauczone + trasy/dziury_omijaj.json) ani w ścianę wg mapy (poza polem zwłok); 0 = jak dotąd
WPADNIECIE_UCIECZKA = 1           # pokrętło 0/1: 1 = wpadnięcie bez drogi do trasy (kieszeń na innym piętrze): UCIECZKA nie przejmuje obiegu (kroki do punktu trasy z innego piętra), wyjście (Use/lina) i walka mają pierwszeństwo; leczenie exura także poniżej progu ucieczki (23.10, zgon odchyda)
WPADNIECIE_BIJ = 1                # pokrętło 0/1: 1 = stwór spoza --potwory, który stoi na polu wyjścia albo zagradza wyjście z kieszeni, jest celem (23.10)
WPADNIECIE_DRABINA = 1            # pokrętło 0/1: 1 = przy wpadnięciu Use (Ctrl+klik) na polu wyjścia jak na drabinie, zanim lina (minimapa nie odróżnia drabiny od liny, 23.10)
ZATRUCIE_AKTYWNY = 1              # pokrętło 0/1: 1 = wykrywanie zatrucia (pamięć `stany` albo wnioskowanie z HP, zatrucie.py) i leczenie: exana pox (klawisz) albo antidote rune (23.10, zgon odchyda/gebelisha)
ZATRUCIE_CZAR_KLAWISZ = ""        # hotkey czaru exana pox w kliencie ("" = brak, nie naciskamy nic); wymaga ML i many >= ZATRUCIE_CZAR_KOSZT
ZATRUCIE_CZAR_KOSZT = 30          # mana exana pox
ZATRUCIE_RUNA = 1                 # pokrętło 0/1: 1 = antidote rune (id 3153) z otwartego plecaka użyta na siebie
WPADNIECIE_BEZ_STOP = 0            # 21.10 pokrętło 0/1 (domyślnie 0 = jak dotąd): 1 = wpadnięcie bez STOP: cykle ponawiania (czyszczenie złych przejść, czekanie 10-20 s, zejście z pola przejścia), STOP+critical dopiero po PIETRA_MAX_S i >=3 cyklach (wpadniecie.py, SPEC_wpadniecie_bez_stop_1021)
PRZEJSCIE_TRZY_SPOSOBY = 0         # 21.10 pokrętło 0/1 (Karol): 1 = przejście pięter próbuje na punkcie przejścia: wejść, kliknąć (Use), lina (w górę); działający sposób zapamiętany dla wszystkich postaci (dane_tibia/ruch/przejscia_nauczone.json) i próbowany pierwszy (wypad.py, pietra.py; SPEC_przejscia_trzy_sposoby_1021)
WPADNIECIE_POSCIG = 0              # pokrętło 0/1 (domyślnie 0 = jak dotąd): 1 = pozycje czytane w pętli pościgu/lootu odświeżają ostatnią próbkę wpadnięcia, więc upadek w dziurę podczas pościgu jest wykrywany (wpadniecie.w_petli; SPEC_orbity_straznik_1020 A)
WPADNIECIE_WALIDACJA = 0           # pokrętło 0/1 (domyślnie 0 = jak dotąd): 1 = przed nauką dziury sprawdź mapę (flaga 2, brak 4) i brak schodów w cheb<=1 od lądowania/p0; inaczej bez nauki (wpadniecie.py)
DZIURY_NAUCZONE = 1                # pokrętło 0/1: 1 = pola z trasy/dziury_nauczone.json są ścianą dla każdej drogi A* i kroku na danym piętrze
DZIURA_PODEJSCIE_S = 10.0           # s: tyle idziemy sami obok celu stojącego przy dziurze, potem go odpuszczamy (DZIURA_PRZY_CELU)
DZIURA_PRZY_CELU = 1               # 15.10: pokrętło 0/1: 1 = nie atakujemy/nie gonimy celu stojącego przy znanej dziurze (chebyshev <= 1) w prostokącie między nami a nim, chyba że sami dojdziemy A* (dziury = ściany) do pola obok celu krótką drogą (klient w trybie ataku sam idzie za celem i wpadł w dziurę)
PIETRA_RESYNC_MAX = 6              # tyle resynchronizacji (piętro poza trasą) w 120 s = porażka
PIETRA_DOJSCIE_S = 25.0            # s bez zbliżenia do pola przejścia = następny kandydat
TRYB_PATROL = 0                    # 12.10: 1 = patrol po miejscach z trasy/miejsca.json (losowo, ważony zabiciami i odległością) zamiast pętli trasy; mozg --trasa patrol ustawia 1; pokrętło 0-1
PATROL_PLIK = "miejsca.json"       # plik miejsc w trasy/
PATROL_KOORD = 0                   # 1 = koordynator miejsc między instancjami (miejsca_koord.py): nie wybieram miejsc zajętych przez inną instancję, swoje rezerwuję; 0 = wył. (domyślnie); pokrętło 0-1
PATROL_KOORD_PROMIEN = 0           # pola: rezerwacja blokuje też miejsca tak blisko (to samo piętro); 0 = tylko to samo miejsce; pokrętło 0-30
PATROL_WAGA_MIN = 0.04             # dolny próg udziału zabić miejsca w losowaniu (miejsca bez danych też bywają odwiedzane)
PATROL_RUNDA = 1                   # 1 = runda: każde miejsce (spawn) raz, kolejność losowa wg wag, po wszystkich reset
PATROL_ODL_SKALA = 22.0            # waga odległości: 1 / (1 + d / skala), d = pola prosto (|dx| + |dy|)
PATROL_BYLO_WYKLUCZ = 4            # tyle ostatnich odwiedzonych miejsc nie jest losowane
PATROL_BYLO_KARA = 0.4             # mnożnik wagi dla miejsc odwiedzonych 5-8 wizyt temu
PATROL_ODL_MIN = 3                 # miejsca bliżej niż tyle pól od nas nie są losowane (już tam jesteśmy)
PATROL_PRZYJECIE = 1               # pola: tak blisko miejsca = dotarliśmy
PATROL_POSTOJ = (1.0, 3.0)         # s rozglądania się na miejscu
PATROL_ZAWROT = 1                  # 15.10: pokrętło 0/1: miejsce spawnu (z jego okolicą) już w widoku, a przy nim od PATROL_ZAWROT_S
                                   # nie ma żadnego celu: wizyta zaliczona bez dochodzenia do końca (ślepe zaułki, puste spawny)
PATROL_ZAWROT_S = 1.5              # s pustki przy miejscu, zanim zawrócimy
PATROL_ZAWROT_PROMIEN = 2          # pola wokół miejsca, które muszą być w widoku i puste
WIDOK_X, WIDOK_Y = 7, 5            # widok mapy klienta 15x11: gracz w środku, tyle pól w bok / w pionie
PATROL_OBCHOD_P = 0.5              # szansa na krótki obchód (2-4 kroki w promieniu PATROL_OBCHOD_PROMIEN) po postoju
PATROL_OBCHOD_PROMIEN = 3          # pola
PATROL_OBCHOD_DROGA = (2, 5)       # min/maks długość drogi obchodu (pola)
PATROL_LIMIT_S = (45.0, 2.5)       # s aktywnego marszu do miejsca: stała + mnożnik * długość drogi, potem miejsce jest odpuszczane
PATROL_BLOK_S = 150.0              # s: miejsce bez drogi/nieosiągalne/zagrożone nie jest losowane
PATROL_LUKA_S = 4.0                # s przerwy w patrolu (walka, loot): po niej możliwa zmiana celu na miejsce tuż obok
PATROL_BLISKO = 4                  # pola: po przerwie, gdy stoimy tak blisko innego (nieodwiedzonego) miejsca, bierzemy je
PATROL_FALLBACK_S = 60.0           # s jazdy po trasie (kanaly) po niepowodzeniu wyboru miejsca, potem próba patrolu od nowa
PATROL_STAT_CO = 20                # co tyle wizyt zbiorcza linia KPI w logu
# --- mapa spotu: miejsca na kilku piętrach (z8+z9), przejścia z pliku miejsc, bezpieczeństwo, pamięć graczy (13.10) ---
PATROL_PIETRA = 1                  # 1 = miejsca na innych piętrach (plik miejsc ma "przejscia"; marsz przez pietra.py); 0 = tylko piętro, na którym stoimy
PATROL_PIETRO_KARA = 14            # pola doliczane do odległości (wagi) miejsca za każde piętro różnicy
PATROL_PRZEJSCIE_KOSZT = 8         # pola: koszt jednego przejścia pięter przy planowaniu drogi
PATROL_PRZEJSCIE_LIMIT_S = 40.0    # s dodawane do limitu marszu za każde przejście pięter na drodze
PATROL_PRZEJSCIA_MAX = 5           # maks. przejść pięter w jednej drodze
PATROL_PRZEJSCIE_BLOK_S = 300.0    # s: przejście pięter, które zawiodło, nie jest planowane
PATROL_GNIAZDO_MOBOW = 4           # miejsce/przejście, gdzie widywano tyle mobów naraz, to gniazdo (wymaga HP i many)
PATROL_GNIAZDO_HP = 85             # % HP wymagane, by wybrać gniazdo (0 = bez warunku)
PATROL_GNIAZDO_MANA = 40           # % many wymagane, by wybrać gniazdo (0 = bez warunku)
PATROL_MOBY_BEZP = 2               # tyle mobów naraz nie obniża wagi miejsca
PATROL_MOBY_KARA = 0.35            # waga miejsca /= 1 + KARA * max(0, mobow - BEZP) (0 = bez wpływu)
PATROL_GRACZ_PAM = 1               # 1 = pamiętamy, gdzie niedawno widziano obcego gracza, i omijamy tę część spotu
PATROL_GRACZ_PAM_S = 600.0         # s: tak długo ostatnia pozycja gracza zniechęca do miejsc w pobliżu
PATROL_GRACZ_PAM_R = 14            # pola: miejsce tak blisko ostatniej pozycji gracza dostaje karę
PATROL_GRACZ_PAM_KARA = 0.1        # mnożnik wagi takiego miejsca (0 = blokada; inne piętro: pierwiastek)
PATROL_GRACZ_ZMIEN = 0             # pokrętło 0/1 (17.10, na_zywo: 1): obcy gracz w PATROL_GRACZ_ZMIEN_R polach od nas albo od celu = od razu (bez debounce unikania) blokada
                                   # miejsc w PATROL_GRACZ_PAM_R od niego na PATROL_GRACZ_ZMIEN_BLOK_S s i wybór innego respa (dalej od gracza)
PATROL_GRACZ_ZMIEN_R = 12          # pola: tak blisko nas albo celu patrolu obcy gracz wywołuje zmianę respa
PATROL_GRACZ_ZMIEN_BLOK_S = 240.0  # s: tak długo miejsca przy graczu są zablokowane
PATROL_GRACZ_ZMIEN_PAUZA_S = 15.0  # s: min. odstęp między zmianami respa z tego powodu
LOOT_DYNAMICZNY = 1                # 13.10: loot dynamiczny (pokrętło 0/1; 0 = dawne zachowanie, DOMYŚLNIE 1 od decyzji Karola 13.10; 0 = dawne zasady): zwłoki w odl <= 1 zaraz po zabiciu także przy
                                   # żywym mobie w odl >= 2; dalsze gdy mob >= 3 pola; okno lootu otwarte nie jest przerywane "cel_daleko";
                                   # po "brak_okna" zwłoki wstrzymane do końca walki (jedna próba po walce); zwłoki z innego piętra odłożone
LOOT_SZYBKI_ODL = 3                # LOOT_DYNAMICZNY: zwłoki tak blisko (pola) zbieramy zaraz po zabiciu, gdy żaden mob nie przylega
LOOT_SZYBKI_STYKAJACE = 1          # 23.10 (decyzja Karola: "zabija moba, od razu lootuje i bije kolejnego"): ile żywych mobów może PRZYLEGAĆ (odl 1), gdy zaraz po
                                   # zabiciu zbieramy zwłoki obok (LOOT_SZYBKI_ODL; przy styku tylko zwłoki w odl 1, bez kroków). Pokrętło 0-2 (tylko w dół);
                                   # 0 = dawne zachowanie (przylegający mob = loot odłożony do lootu w walce / po walce). Pozostałe warunki bez zmian
                                   # (ucieczka/ostrożny, HP > próg + LOOT_W_WALCE_HP_MARGINES, groźny gracz, ogień); przerwanie: spadek HP, limit czasu
LOOT_SZYBKI_STYK_MAX_S = 8.0       # s: twardy limit jednego lootu zaraz po zabiciu przy przylegającym mobie (potem zwłoki zostają na liście)
LOOT_W_WALCE_MAX_S = 20.0          # s: tyle maks. na jedne zwłoki w walce (reszta po walce)
LOOT_W_WALCE_PO_ATAKU_S = 1.0      # s po kliku ataku, zanim wolno klikać zwłoki (flaga ataku musi się ustalić)
LOOT_W_WALCE_POSTOJ_S = 0.6        # s bez ruchu postaci (klik w zwłoki w trakcie kroku trafiłby w sąsiednie pole)
LOOT_W_WALCE_CHLOD_S = 3.0         # s przerwy po każdym przerwaniu lootu w walce
LOOT_W_WALCE_POMIN_S = 20.0        # s: zwłok, których w walce nie udało się otworzyć, nie próbujemy znów w walce
LOOT_W_WALCE_KARA_S = 120.0        # s wyłączenia lootu w walce, gdy klik w zwłoki wyłączył atak
LOOT_W_WALCE_MAX_KAR = 2           # tyle wyłączeń ataku przez klik w zwłoki = loot w walce wyłączony do restartu
LOOT_W_WALCE_STARY_S = 4.0         # s bez kroku: stan lootu w walce uznajemy za przerwany (ucieczka, pościg...)
LOOT_PRZEGLAD_ODL = 2              # pola: żywy potwór tak blisko przerywa zbieranie w loot.zbierz
# ZMIANA 11.10: "ham" usunięty z WYPAD_ZAKUPY (Al Dee go nie sprzedaje; ~30 s zakupu kończyło się brak_npc)
POCHODNIA_W_PRZERWIE = True        # 1 = w trakcie zaplanowanej przerwy (PRZERWA) nadal wymieniamy wypaloną pochodnię; 0 = dawne (stoi w ciemności)
WYPAD_PO_TORCHE = True             # wypad do miasta po pochodnie (wypad.py), gdy ostatnia się kończy i brak zapasu; pokrętło: tylko 1
WYPAD_ILE_TORCHY = 5               # ile pochodni mieć po zakupie (kupujemy do tej liczby); pokrętło 1-10 (tylko w górę)
WYPAD_ZAKUPY = {"torch": 5}   # lista zakupów u Al Dee w kolejności: przedmiot -> docelowa liczba sztuk w plecaku
WYPAD_JEDZENIE = True              # drugi wyzwalacz wypadu: brak jedzenia w plecaku + HP < WYPAD_JEDZENIE_HP + spokój
WYPAD_JEDZENIE_HP = 50.0           # % HP: poniżej (i powyżej progu ucieczki) brak jedzenia wyzwala wypad
WYPAD_JEDZENIE_SPOKOJ_S = 10.0     # s bez żywych potworów w promieniu 8, zanim wypad po jedzenie ruszy
WYPAD_SPRAWDZ_S = 15.0             # s: co ile (w spokoju) czytamy ekwipunek i plecak w poszukiwaniu wyzwalacza
# Wyprawa po zapasy (wyprawa.py, 13.10): jedzenie u Frodo w Thais, opcjonalnie blank runy (Xodet) i pochodnie (Gorn).
# Wyłączona domyślnie; włącza tryb "wyprawa" z tryby.json albo pokrętło w na_zywo.json (po restarcie bota).
WYPRAWA_AKTYWNA = 0                # pokrętło 0/1 (analityk nie może włączyć)
WYPRAWA_ZAPAS_PROG = 0             # sztuk jedzenia w plecaku, poniżej których ruszamy (0 = JEDZENIE_ZAPAS_MIN)
WYPRAWA_JEDZENIE_CEL = 20          # docelowa liczba sztuk jedzenia po zakupie (cap może obciąć)
WYPRAWA_JEDZENIE_DOKUP = 5         # dokup ponad cel po zjedzeniu do "full" u NPC
WYPRAWA_JEDZ_NA_MIEJSCU = 1        # 1 = jemy u Frodo aż klient przestanie zjadać ("You are full")
WYPRAWA_JEDZ_MAKS = 12             # twardy limit zjedzonych sztuk przy NPC
WYPRAWA_BLANKI = 0                 # 0 = bez blank run; >0 = docelowa liczba blank run (Xodet), wymaga pozycji Xodeta
WYPRAWA_BLANKI_PROG = 2            # poniżej tylu blank run w plecaku wyprawa startuje też z tego powodu
WYPRAWA_BLANKI_MAX_KOSZT = 500     # gp: maks. wydatek na blanki w jednej wyprawie
WYPRAWA_POCHODNIE = 1              # 1 = przy okazji pochodnie u Gorna (gdy zapas < WYPAD_ILE_TORCHY)
WYPRAWA_CAP_REZERWA = 8            # oz capa zostawione wolne po zakupach
WYPRAWA_ZLOTO_MIN = 30             # gp: mniej = wyprawa nie startuje (30 min przerwy)
WYPRAWA_CAP_MIN = 10               # 23.10 oz: wolny cap poniżej tego (przez POTWIERDZ odczytów) = powód "cap": w TRYBIE DEPO (WYPRAWA_TYLKO_DEPO=1) wyprawa do depo, a refill po niej (WROC_REFILL=1) robi bank (gold->platinum) i depo. 0 = wyłączone. Wartość tymczasowa (invincible 23.10 cap 0.0: loot za_ciezki, brak powrotu). Po depo z tego powodu, gdy cap się nie poprawił, kolejna wyprawa nie rusza (ostrzeżenie raz)
WYPRAWA_MIN_HP = 70                # % HP gracza wymagane do startu
WYPRAWA_CO_MIN = 20                # min: minimalny odstęp między wyprawami (także po porażce)
WYPRAWA_MAX_CZAS_S = 1800          # s: twardy limit czasu jednej wyprawy
WYPRAWA_MAX_KROKOW = 6000          # twardy limit obiegów maszyny wyprawy
WYPRAWA_STOP_PRZY_UTKNIECIU = 1    # 1 = utknięcie/teleport w mieście: alarm + plik STOP (bot się zatrzymuje)
WYPAD_BIEGNIJ = 1                  # 1 = w wypadzie/wyprawie nie walczymy po drodze (biegniemy), bijemy tylko gdy droga zablokowana
WYPAD_BLOK_S = 3.0                 # s: tyle stoimy w miejscu ze stworem obok = droga zablokowana, wtedy walka
WYPAD_WALKA_S = 8.0                # s: po zablokowaniu walczymy tak długo, zanim znów ocenimy "biegnij"
WYPAD_PETLA_S = 8.0                # s: stwór obok i brak postępu (kręcimy się w promieniu WYPAD_PETLA_PROMIEN, np. dziura/drabina) = droga zablokowana, walka; 0 = wyłączone
WYPAD_PETLA_PROMIEN = 2            # pola (Chebyshev): tyle bot może się ruszać w oknie WYPAD_PETLA_S, a i tak liczy się jako brak postępu
WYPRAWA_DEPO_BLANKI = 1            # P7b: 1 = w trybie WYPRAWA_TYLKO_DEPO sam brak blanków też jest powodem wyprawy (domyślnie 1, jak działało 13.10; 0 = tylko powiadomienie)
WYPRAWA_PO_DEPO_S = 900            # P7c: s: minimalna karencja kolejnej wyprawy po wyprawie zakończonej w depo (liczy się większa z tego i WYPRAWA_CO_MIN)
BLANKI_AUTO_BAG = 1                # N9: 1 = blanki z głównego plecaka do bagu na runy także poza wyprawą (start bota, potem co BLANKI_AUTO_BAG_MIN min w spokoju)
BLANKI_AUTO_BAG_MIN = 10           # N9: min odstępu między próbami przeniesienia blanków do bagu
WYPRAWA_PO_DOJSCIU_S = 300         # P7a: s: po dojściu z depo na spot pierwsza ocena wyprawy najwcześniej po tylu sekundach (0 = bez karencji)
DOJSCIE_WALKA_PRZEJSCIE_S = 60     # P7d: s: w dojściu stwór obok przy zmianie piętra (dziura/schody) = walka do skutku, ale max tyle s (0 = dawne WYPAD_WALKA_S)
DOJSCIE_BEZ_UNIKANIA_CALE = 1      # 16.10: 1 = w całym dojściu (depo -> spot) unikanie graczy wyłączone
DOJSCIE_BEZ_UNIKANIA_POL = 0       # P7f: >0 = w dojściu, gdy postać jest w tylu polach od początku dojścia (depo), unikanie graczy wyłączone; 0 = bez zmiany (domyślnie wył.)
DOJSCIE_PROBY = 5                  # P7e: tyle razy ponawiamy dojście od aktualnej pozycji, zanim uznamy porażkę (mozg.przejdz_dojscie; zakres 3-8)
DOJSCIE_PAUZA_PROBY_S = 4.0        # P7e: s pauzy (losowo 0,75x-1,5x) przed kolejną próbą dojścia po porażce przejścia pięter
DOJSCIE_BIEGNIJ = 1                # 1 = w dojściu na spot (--dojscie, CavebotDojscie) biegniemy: bez walki, lootu, przerw i pościgu; bijemy tylko blokujące moby (WYPAD_BLOK_S/WYPAD_WALKA_S); ucieczka i leczenie zostają
BLOKADA_BIJ_KAZDEGO = 1            # 23.10 (Karol: "musi go bić, jeśli nie ma przejścia, bo inaczej zginie"): 1 = w dojściu i wypadzie stwór DOWOLNY (też spoza --potwory, np. Poison Spider) na jedynym kroku drogi (brak objazdu wg mapy/A*) jest bity jak blokujący (WYPAD_BLOK_S/WYPAD_WALKA_S); gracze nigdy; 0 = jak dawniej
BLOKADA_BIJ_OBJAZD = 10            # pola: objazd dłuższy od drogi bez stworów o więcej niż tyle nie liczy się jako objazd (stwór nadal blokuje)
HP_PRZED_PIETREM = 90              # 23.10 (Karol: "dobrze by było, jakby miał dużo HP"): w dojściu i wypadzie przed przejściem pięter (dziura, lina, schody, drabina, łopata) postać czeka w miejscu, aż HP% >= tyle (leczy się exura, jeśli ma manę); 0 = wyłączone
HP_PRZED_PIETREM_MAX_S = 120.0     # s: najdłuższe czekanie na HP przed jednym przejściem; potem idzie dalej (wpis w logu, bez STOP)
PIETRA_LOPATA_TYLKO_Z7 = 1         # pokrętło 0/1: łopata tylko na z7 (wejście do jaskini z powierzchni); 0 = na każdym piętrze (dawne)
PIETRA_LOPATA_BRAK_S = 600.0       # s: po "nie widzę łopaty" w plecaku nie próbujemy łopaty ponownie
DOJSCIE_BRAK_POSTEPU_S = 240.0   # 24.10: dojście bez nowego punktu trasy tyle sekund (w stanie IDZ) = porażka próby, ponowienie od pozycji; 0 = wyłączone
PIETRA_LOPATA_WEJSCIE = 1          # 24.10: 1 = zaraz po udanej łopacie krok w odkopaną dziurę w tym samym przejściu (przez bramkę HP_PRZED_PIETREM), a po przesunięciu (walka) powrót i krok zamiast „wyczerpane pola”; 0 = dawne
PIETRA_LOPATA_OKNO_S = 90.0        # 24.10: s po łopacie, w których dziura jest uznana za otwartą: dojście do pola nie oddaje kandydata (PIETRA_DOJSCIE_S) i krok ponawiany
PIETRA_LOPATA = 1                  # 1 = przy wejściu w dół dziurą (pole z flagą 2) po nieudanym kroku odkopujemy ją łopatą z plecaka (Use with, ID 3457)
PIETRA_LOPATA_AUTO = 0             # 21.10 (F4 SPEC_generator_spotow_1021): 1 = łopata na każdym zejściu w dół; 0 = tylko ZASYPANE i pamięć "lopata"
PIETRA_TRYBY_Z_DANYCH = 1          # R1b pokrętło 0/1: przejścia pięter tylko trybami, które działają w danych (schody: krok w obie strony; drabina: R ze skosu bez pre-kroków; łopata tylko zasypana dziura z pola sąsiedniego); ortogonalne pole startowe tylko przed krokiem; slot bez zastosowania nie zużywa próby; 0 = dawny porządek prób
PIETRA_CZEKAJ_KROK_S = 1.2         # R1b: s czekania na zmianę piętra po kroku (p99 udanych 1,5 s), potem ponowny odczyt pozycji; 0 = dawne 2,0 s + odstępy 1,2,4,6 s
PIETRA_CZEKAJ_R_S = 2.0            # R1b: s czekania na zmianę piętra po R (Ctrl+klik); p99 udanych 1,8 s
PIETRA_DOMYSL_PROMIEN = 3          # R1b: kandydat "domysł" tylko w tylu polach od gracza i z flagami mapy zgodnymi z przejściem; 0 = dawne (kotwica na punkcie trasy, bez sprawdzenia)
PIETRA_PRE_MAX = 1                 # R1b: najwyżej tyle pre-kroków strzałką na pole startowe na przejście; pole, na które nie dotarliśmy START_KROK_NIE_MAX (2) razy, idzie do pietra_zle.json (liczone po pozycji); 0 = dawne (8 ruchów, licznik "krok zwrócił None")
PIETRA_ZAJETE_MAX_S = 20.0         # 15.10: s czekania/bicia, gdy na polu przejścia pięter (np. lina) stoi stwór lub gracz; w tym czasie próby nie są liczone, potem zwykłe próby; 0 = wyłączone (dawne)
PIETRA_ZAJETE_ATAK = 1             # 15.10: 1 = stwór (nie gracz) na polu przejścia atakujemy niezależnie od listy łowiska; 0 = tylko czekamy
PIETRA_STARTY_DOMYSLNE = 1         # R1b: zasiane dobre pola startowe z trasy/pietra_starty_domyslne.json (poniżej pamięci z pietra_start.json); 0 = bez zasiewu
WYPRAWA_DEPO_POWROT = 0            # 1 = po dojściu do depo wyprawa sama wraca na spot (faza "z" po trasie depo_troll_cave) zamiast STOP
WYPRAWA_DEPO_POSTOJ_S = 0          # s: postój w depo przed powrotem (czas na ręczne odłożenie rzeczy)
JEDZENIE_BRAK_WALIDUJ = 1          # 1 = "Zjedzono: nic" przy nieczytelnych kontenerach to NIE brak jedzenia (14.10: fałszywy głód -> wyprawa do depo)
JEDZENIE_BRAK_PROBY = 2            # ile razy ponownie odczytać kontenery po nieudanym jedzeniu, zanim uznamy odczyt za nieczytelny
GLOD_ZAPAS_WAZNY_S = 120           # s: potwierdzony głód (wyprawa) ważny tylko, gdy zapas był odczytany wiarygodnie w tym oknie
WYPRAWA_WZNOW_WALIDUJ = 1          # 1 = po restarcie wyprawa po jedzenie sprawdza powód (zapas/kontenery) i wygasa, gdy już nie zachodzi
WYPRAWA_CZEKAJ_NA_GLOD = 0         # 1 = wyprawa po jedzenie dopiero po potwierdzonym głodzie (nieudana próba jedzenia), nie od razu przy zapasie 0
WYPRAWA_JEDZENIE = 1             # 0 = brak jedzenia nie jest powodem wyprawy (wyprawa.py; 15.10 decyzja Karola: na razie tylko blanki)
WYPRAWA_DEPO_W_WALCE = 1           # 1 = wyprawa do depo (po potwierdzonym głodzie) startuje także w walce i biegnie; 0 = tylko w spokoju
WYPRAWA_DEPO_ZLOZ = 0                # 1 = zwykła wyprawa zaczyna od depo: składa UH w skrzyni, potem Frodo/Xodet
WYPRAWA_DOJSCIE_PATROLEM = 1       # 15.10: 1 = wyprawa/wypad startujący w części jaskini niepołączonej z planem (inna strona schodów, kieszeń) najpierw dochodzi do planu drogą patrolu (graf przejść pięter z pliku miejsc + pietra.py), zamiast kończyć utknięciem; 0 = dawne zachowanie; pokrętło 0-1
WYPRAWA_TYLKO_DEPO = 0              # 1 = wyprawa idzie tylko do depo (troll_do_miasta + A* do pola depo), tam STOP + powiadomienie; bez zakupów i powrotu
WYPRAWA_MARSZ_KLIK = 0             # 20.10 pokrętło 0/1: 1 = w drodze do miasta/depo (wypad.py, faza "do": wyprawa i "Wróć do miasta") klik w najdalsze zwykłe pole odcinka (marsz_klik.py, jak serwis); 0 = dotychczasowe chodzenie bit w bit
STANOWISKO = 0                     # 22.10 pokrętło 0/1 (tryb "stoj"): 1 = tryb stanowisko (stanowisko.py): postać stoi w mieście poza PZ i robi runy; wymaga też stanowisko_mapa.json (tryb.py z mapy stoj_runy_*); 0 = wył.
STANOWISKO_HP_PZ = 70              # 22.10 pokrętło %: HP poniżej tego (i bez potwora obok) = marsz do PZ; ucieczka HP zawsze do PZ
STANOWISKO_PZ_KARENCJA_MIN = 30    # 22.10 pokrętło min: po zagrożeniu PK (atak, wróg, czaszka) stoimy w PZ tyle minut
STANOWISKO_GRACZ_ODL = 0           # 22.10 pokrętło pól: 0 = każdy obcy gracz w widoku wstrzymuje UH (jak dotąd); N > 0 = tylko bliżej niż N pól
STANOWISKO_NPC_IGNORUJ = 1         # 22.10 pokrętło 0/1: 1 = NPC (serwis_akcje.NPC_NAZWY) nie wstrzymują UH ani nie liczą się jako obcy gracz
STANOWISKO_WOLNE_SLOTY_MIN = 2     # 22.10 pokrętło: próg wolnych slotów plecaka do serwisu (F2, dziś nieużywane)
STANOWISKO_AKTYWNOSC_MAX_S = 0     # 22.10 pokrętło s: 0 = wył.; >0 = bez akcji dłużej niż 0,55-0,95 tego czasu -> krok w bok i z powrotem (anty-idle)
STANOWISKO_ROTACJA_MIN = 0         # 22.10 pokrętło min: 0 = wył.; >0 = zmiana pola co tyle minut (gdy mapa ma kilka pól)
STANOWISKO_ZMIANA_MAX_MIN = 180    # 22.10 pokrętło min: maks. czas stania na zmianę (decyzja Karola 22.10: 3 h); 0 = bez limitu
WROC_REFILL = 0                    # 20.10 pokrętło 0/1: 1 = po dojściu do depo Edron (STOP w depo: wroc.sh i wyprawa tylko-do-depo) sam startuje refill (refill_auto.py -> refill.sh --tlo); 0 = bot staje i czeka na człowieka
RUCH_OKNO = 1                      # pokrętło 0/1 (R0b): rekord telemetrii ruch_okno co 30 s (czas marszu/stania, przyczyny, luki)
RUCH_PROBKA_WCZESNA = 1            # pokrętło 0/1 (R0b): próbka telemetrii także przy wczesnym zakończeniu obiegu (bez A*, bez RPC)
TICK_WOLNY = 1.0                   # s: tick wolniejszy loguje podział czasu na fazy (debug)
POKRETLA_CO = 2.0                  # s: pokretla.odswiez nie częściej
# --- ML: automatyczne rzucanie czaru dla magic levelu (ML rośnie od wydanej many). Domyślnie WYŁĄCZONE ---
ML_CZAR_AKTYWNY = 0                # pokrętło 0/1 (na_zywo.json): 1 = rzucaj czar, gdy jest mana i spokój
ML_CZAR_TEKST = "utevo lux"        # nazwa czaru: tylko do logów/telemetrii (nic nie wpisujemy na czat)
ML_CZAR_KLAWISZ = "F1"             # hotkey czaru w kliencie (F1 = utevo lux); naciskany tym samym XTEST co klawisz jedzenia
ML_CZAR_KOSZT = 20                 # pokrętło: koszt many czaru
ML_CZAR_MIN_PRZERWA_S = 2.5        # pokrętło: exhaust, min. odstęp między rzutami (nie mniej niż 2.5 s)
ML_CZAR_W_WALCE = 0                # pokrętło 0/1: 1 = rzucaj też, gdy żywy mob w pobliżu / trwa walka lub pościg
ML_CZAR_OPOZNIENIE = (0.5, 3.0)    # s: losowe opóźnienie od spełnienia warunków do rzutu (brak regularności)
ML_CZAR_DLUGA_SZANSA = 0.08        # szansa na "zamyślenie": opóźnienie z ML_CZAR_DLUGA zamiast zwykłego
ML_CZAR_DLUGA = (5.0, 14.0)        # s: długie opóźnienie rzadkiego zamyślenia
ML_CZAR_EXTRA_PRZERWA = (0.0, 2.5) # s: losowy dodatek do exhaustu, losowany od nowa po każdym rzucie
ML_CZAR_ZAPAS_MANY = (0, 4)        # losowa nadwyżka many ponad koszt czaru, losowana od nowa po każdym rzucie (pula 35: małe wartości)
ML_CZAR_WERYFIKACJA_S = 1.2        # s po rzucie: tyle czekamy, zanim sprawdzimy, czy mana spadła
ML_CZAR_PORAZKI = 3                # tyle nieudanych rzutów z rzędu (mana nie spadła) wyłącza rzucanie
ML_CZAR_PRZERWA_PO_PORAZKACH_S = 600.0   # s wyłączenia po porażkach
ML_CZAR_LOG_CO = 10                # log "ML: rzucono N, many wydane M" co tyle rzutów
ML_BLOK_HP = 80                    # pokrętło 0-100 (nie_wyzej): HP% poniżej + walka/mob w pobliżu = bez ML (mana zostaje na exurę)
CZAR_MIN_PRZERWA_S = 2.0           # s: exhaust dzielony przez WSZYSTKIE czary bota (ML, exura, exevo pan); min. odstęp między rzutami
# --- leczenie czarem exura (F2): także w walce i w pościgu. Domyślnie WYŁĄCZONE ---
ZDROWIE_CZAR_AKTYWNY = 0           # pokrętło 0/1 (na_zywo.json): 1 = rzucaj exura, gdy HP% < ZDROWIE_CZAR_HP i jest mana
ZDROWIE_CZAR_TEKST = "exura"   # tylko do logów/telemetrii (F2 = exura, Light Healing)
ZDROWIE_CZAR_KLAWISZ = "F2"        # hotkey czaru w kliencie (F2 = exura, Light Healing)
ZDROWIE_CZAR_KOSZT = 25            # koszt many (exura 25; exura gran 40)
ZDROWIE_CZAR_HP = 65               # pokrętło 20-90 (nie_wyzej): HP% poniżej = leczymy (nad progiem ucieczki)
ZDROWIE_CZAR_OPOZNIENIE = (0.2, 0.8)   # s: losowe opóźnienie tuż przed rzutem
ZDROWIE_CZAR_WERYFIKACJA_S = 1.2   # s po rzucie: tyle czekamy, zanim sprawdzimy, czy HP/mana się zmieniły
ZDROWIE_CZAR_PORAZKI = 3           # tyle nieudanych rzutów z rzędu wyłącza leczenie
ZDROWIE_CZAR_PRZERWA_PO_PORAZKACH_S = 600.0
# --- pet (utevo res "nazwa", pet.py + pet_ster.py). Domyślnie WYŁĄCZONE; pet nie idzie po schodach/dziurach ---
PET_WLACZONY = 0                   # pokrętło 0/1 (na_zywo.json): 1 = przywołuj peta poza walką, gdy mana >= PET_MANA_MIN
PET_MANA_MIN = 360                 # pokrętło (nie_nizej): mana wymagana do rzutu (Elf Scout ok. 360; nie zjadamy rezerwy UH/leczenia)
PET_NAZWA = "Elf Scout"            # pokrętło tekstowe: nazwa stworzenia w czarze i w liście stworów (utevo res "Elf Scout")
PET_CZAR = "utevo res"             # słowa czaru (wpisywane na Default przez mozg.wpisz_na_czacie)
PET_STABILNE_S = 45.0              # pokrętło: s na tym samym piętrze, zanim uznamy je za piętro spota i wolno przywołać
PET_PIETRO = 0                     # pokrętło: 0 = piętro spota z PET_STABILNE_S; 1-15 = przywołuj tylko na tym piętrze (z)
PET_ZMIANY_MAX = 2                 # pokrętło: tyle zmian pięter w oknie PET_ZMIANY_OKNO_S = spot wielopiętrowy, bez przywoływania
PET_ZMIANY_OKNO_S = 600.0          # pokrętło: s okna liczenia zmian pięter
PET_PRZERWA_S = 30.0               # pokrętło: min. odstęp między rzutami czaru (exhaust i ochrona przed pętlą)
PET_PORAZKI = 2                    # pokrętło: tyle czarów z rzędu bez nowego stworzenia obok = przerwa
PET_PRZERWA_PO_PORAZKACH_S = 900.0 # pokrętło: s przerwy po porażkach
PET_ZGONY_MAX = 5                  # pokrętło: po tylu zgonach peta w sesji bez przywoływania (0 = bez limitu; zgon kosztuje cała manę)
PET_PRZYWOLAJ_PLIK = Path(__file__).resolve().parent / "PRZYWOLAJ_PETA"   # 17.10 "przyzwij teraz": plik jednorazowy, ignoruje walkę, znika po rzucie
# --- jedzenie czarem exevo pan (F3): tworzy jedzenie, które zjadamy istniejącym mechanizmem. Domyślnie WYŁĄCZONE ---
RUNA_AKTYWNA = 0                   # pokrętło 0/1 (na_zywo.json): 1 = strzał runą (hotkey) w cel w walce; nie kosztuje many
RUNA_KLAWISZ = "F4"                # hotkey w kliencie: "użyj runy na celu" (HMM w zaznaczony cel); pokrętło tekstowe
RUNA_INTERWAL_S = 2.0              # pokrętło: min. odstęp między strzałami (17.10: exhaust run w kliencie >3 s i <= ok. 5 s, na_zywo: 3.5-4.5)
RUNA_INTERWAL_MAX_S = 0.0          # pokrętło: > RUNA_INTERWAL_S = odstęp losowany z [RUNA_INTERWAL_S, RUNA_INTERWAL_MAX_S] po każdym strzale (0 = stały)
RUNA_MIN_HP_CELU = 0               # pokrętło: cel poniżej tego HP% nie dostaje runy (0 = bez limitu)
RUNA_ZASIEG = 3                    # pola: dalej nie strzelamy
RUNA_LOG_CO = 20                   # log licznika strzałów co tyle
RUNA_TRYB_KLIK = 0                 # pokrętło 0/1: 1 = strzał kliknięciami (prawy klik na runie -> "Use with" -> lewy na mobie) zamiast hotkeya
RUNA_KLIK_CTRL = 0                 # pokrętło 0/1: 1 = (z RUNA_TRYB_KLIK) Ctrl+lewy na runie, lewy na celu, bez menu "Use with" i OCR
RUNA_ID = 3198                     # pokrętło: ID runy w plecaku do strzału (HMM; blank 3147 to nie to)
RUNA_MENU_DX = 28                  # pokrętło (px): awaryjny offset "Use with" od punktu prawego kliku, gdy OCR menu zawiedzie
RUNA_MENU_DY = 22                  # pokrętło (px): j.w., w pionie (domyślnie drugi wiersz menu)
RUNA_KLIK_PORAZKI = 3              # tyle nieudanych strzałów z rzędu = chłodzenie
RUNA_KLIK_CHLODZENIE_S = 90.0      # s przerwy po serii porażek
RUNA_BRAK_SPRAWDZ_S = 20.0         # s: jak często sprawdzamy plecak, gdy runy nie ma (log tylko raz)
# --- UH (uh.py): robienie run czarem runowym z blank runy w spokoju (tarcza do plecaka, blank do ręki, rzut, runa do plecaka).
# Trenuje ML tak samo jak utevo lux. Domyślnie WYŁĄCZONE (włącza Karol: "UH_AKTYWNY": 1 w na_zywo.json albo tryb raty_runy) ---
UH_AKTYWNY = 0                     # pokrętło 0/1 (na_zywo.json): 1 = rób runy, gdy spokój i mana >= UH_MANA_MIN
UH_KLAWISZ = "F6"                  # hotkey czaru runowego w kliencie; pokrętło tekstowe
UH_CZAR = "adori gran"             # słowa czaru (HMM): tylko log/telemetria, rzut idzie hotkeyem
UH_KOSZT = 70                      # pokrętło: koszt many czaru
UH_MANA_MIN = 95                   # pokrętło: mana wymagana do startu (koszt + 25 rezerwy na exurę)
UH_MIN_HP = 90                     # pokrętło: % HP gracza wymagane do startu (w trakcie: ta wartość minus 10)
UH_MOB_DYSTANS = 3                # pokrętło: stwory (moby) dalej niż tyle pól (Chebyshev) nie blokują ani nie przerywają runy; gracz zawsze w pełnym widoku
UH_ODSTEP_S = 20.0                 # pokrętło: min. odstęp między próbami
UH_PORAZKI = 3                     # tyle nieudanych prób z rzędu wyłącza UH
UH_PRZERWA_PO_PORAZKACH_S = 60.0   # s wyłączenia po porażkach / alarmie (20.10: z 1800, Karol: próbuj co minutę)
UH_PRZERWA_BRAK_BLANK_S = 600.0    # s wyłączenia, gdy brak blank run
UH_HOLD_MAX_S = 300.0              # s: tyle ML (utevo lux) czeka na manę dla UH (potem rzuca; bez zakleszczenia)
# --- UH (uh.py): robienie run czarem runowym z blank runy w spokoju (tarcza do plecaka, blank do ręki, rzut, runa do plecaka).
# Trenuje ML tak samo jak utevo lux. Domyślnie WYŁĄCZONE (włącza Karol: "UH_AKTYWNY": 1 w na_zywo.json albo tryb raty_runy) ---
UH_AKTYWNY = 0                     # pokrętło 0/1 (na_zywo.json): 1 = rób runy, gdy spokój i mana >= UH_MANA_MIN
UH_KLAWISZ = "F6"                  # hotkey czaru runowego w kliencie; pokrętło tekstowe
UH_CZAR = "adori gran"             # słowa czaru (HMM): tylko log/telemetria, rzut idzie hotkeyem
UH_KOSZT = 70                      # pokrętło: koszt many czaru
UH_MANA_MIN = 95                   # pokrętło: mana wymagana do startu (koszt + 25 rezerwy na exurę)
UH_MIN_HP = 90                     # pokrętło: % HP gracza wymagane do startu (w trakcie: ta wartość minus 10)
UH_MOB_DYSTANS = 3                # pokrętło: stwory (moby) dalej niż tyle pól (Chebyshev) nie blokują ani nie przerywają runy; gracz zawsze w pełnym widoku
UH_ODSTEP_S = 20.0                 # pokrętło: min. odstęp między próbami
UH_PORAZKI = 3                     # tyle nieudanych prób z rzędu wyłącza UH
UH_PRZERWA_PO_PORAZKACH_S = 60.0   # s wyłączenia po porażkach / alarmie (20.10: z 1800, Karol: próbuj co minutę)
UH_PRZERWA_BRAK_BLANK_S = 600.0    # s wyłączenia, gdy brak blank run
UH_HOLD_MAX_S = 300.0              # s: tyle ML (utevo lux) czeka na manę dla UH (potem rzuca; bez zakleszczenia)
UH_PONOW_BRAK_EKW_S = 25.0         # s do kolejnej próby, gdy ekwipunek nieczytelny (po relogu); bez liczenia porażek
UH_W_WALCE = 0                     # pokrętło 0/1 (na_zywo.json): 1 = runa także W TRAKCIE WALKI, gdy mana prawie pełna (regen się marnuje)
UH_W_WALCE_MANA_MARGINES = 5       # pokrętło: w walce start, gdy mana >= max_mana - tyle (i >= UH_KOSZT)
UH_W_WALCE_DYSTANS = 0             # pokrętło 0-3: w trybie walki stwór w tej odległości (Chebyshev) blokuje start i przerywa runę; 0 = moby ignorowane (tylko gracz, HP, ucieczka), 1 = przylegający
UH_W_WALCE_SPADEK_HP = 25          # pokrętło: w trakcie runy w walce przerwij, gdy HP spadło o tyle pp od startu runy (kilka trolli naraz)
UH_W_WALCE_MIN_HP = 90             # pokrętło: % HP wymagane do startu runy w walce (w trakcie: ta wartość minus 10)
# --- ogłoszenia sprzedaży UH na kanale Trade (mozg.py: TradeOgloszenia; szablon trade_ogloszenie.txt) ---
MODEL_TRASA_MIASTA = 0            # pokrętło 0/1: 1 = model może zmien_trase na trasę *miasta* (domyślnie 0: powrót do miasta decyduje tylko wyprawa.py)
MODEL_TRASA_ZAMROZENIE_S = 180       # pokrętło: s; model nie zmienia trasy, gdy pozycja postaci stoi w miejscu tak długo (zamrożony odczyt/utknięcie to nie zła trasa; mozg.py)
MODEL_TRASA_MAX_ODL = 60            # pokrętło: pola (Chebyshev, bez z); model nie zmienia trasy na taką, której najbliższy punkt jest dalej od postaci (inny obszar)
TRADE_OGLOSZENIA = 0               # pokrętło 0/1 (na_zywo.json): 1 = ogłoszenie [SELL] UH na zakładce Trade (domyślnie WYŁĄCZONE)
TRADE_MIN_S = 180                  # pokrętło: s min. odstępu między ogłoszeniami (losowo równomiernie MIN-MAX)
TRADE_MAX_S = 300                  # pokrętło: s max. odstępu między ogłoszeniami
TRADE_MIN_UH = 20                  # pokrętło: ogłaszamy dopiero, gdy w plecakach jest tyle run UH ({bp} = pełne po 20)
TRADE_PRIV_ODPOWIEDZI = 0            # pokrętło 0/1 (na_zywo.json): 1 = prywatna odpowiedź (trade_odpowiedz.txt) komuś, kto pisze na priv z intencją kupna (domyślnie WYŁĄCZONE)
# --- pola ognia (ogien.py): wykrywane ze zrzutu (pomijają je pamięć stworów i mapa), liczone jak zablokowane pole ---
OGIEN_UNIKAJ = 1                   # pokrętło 0/1 (na_zywo.json): 1 = omijamy pola ognia, schodzimy z nich, nie lootujemy z ognia
OGIEN_ODSWIEZ_S = 0.8              # s: min. odstęp między wykryciami w tickach (zrzut ppm ok. 40 ms + analiza ok. 20 ms)
OGIEN_BRAK_S = 1.5                 # s: widoczne pole bez ognia w kolejnych wykryciach tak długo = ogień zgasł (animacja migocze)
OGIEN_TRWA_S = 25.0                # s: pole ognia, którego nie widać (poza widokiem), pamiętamy tyle od ostatniego wykrycia
OGIEN_KROK_S = 0.6                 # s: min. odstęp między krokami z pola ognia (poprzedni krok jeszcze trwa)
OGIEN_SZUKAJ = 6                   # pola (Manhattan): tak daleko szukamy wolnego pola poza ogniem
OGIEN_ZLY_KROK_S = 3.0             # s: krok z ognia, który nie przesunął postaci, pomijamy tak długo
OGIEN_CZEKAJ_MAX_S = 30.0          # s: tyle czekamy, aż ogień zgaśnie, gdy zamyka drogę; potem go ignorujemy
OGIEN_IGNORUJ_S = 0.0              # s ignorowania ognia po wyczerpaniu czekania; 15.10: 0 = nigdy (droga skosem jest zawsze,
                                   # skoro mob tam wszedł; bez drogi: inny cel trasy zamiast marszu przez ogień)
OGIEN_LOOT_CHLOD_S = 5.0           # s: zwłoki leżące na ogniu wracają do kolejki po tym czasie
OGIEN_LOG_S = 10.0                 # s: min. odstęp między wpisami "[OGIEN] pola" (13.10, P6: było 1; pokrętło 1-60)
OGIEN_STALY = 1                    # pokrętło 0/1: 1 = maska stałych pól ognia (nie logujemy, nie blokują drogi)
OGIEN_STALY_N = 20                 # tyle wykryć tego samego pola ...
OGIEN_STALY_S = 600.0              # ... w ciągu co najmniej tylu sekund = pole stałe (nie run-fire z 1-2 min)
OGIEN_MASKA_TYLKO_SCIANY = 1       # pokrętło 0/1 (R1a): 1 = do maski stałych pól trafiają tylko pola-ściany wg mapy (flaga 4 / niechodliwe), nigdy pole przechodnie
OGIEN_WYJDZ_POTWIERDZ = 1            # pokrętło 0/1: 1 = z pola ognia schodzimy tylko po potwierdzeniu (spadek HP albo to samo pole >= OGIEN_POTW_S); w walce ze stworem obok tylko po spadku HP
OGIEN_HP_OKNO_S = 3.0                # s: okno, w którym spadek HP potwierdza ogień (i kasuje kwalifikację pola do maski danych)
OGIEN_HP_SPADEK_PP = 3.0             # pp max HP: tyle musi spaść HP w OGIEN_HP_OKNO_S (jak GRYZIE_SPADEK_PP; trafienie ognia to ok. 5 pp)
OGIEN_POTW_S = 1.6                   # s: to samo pole wykryte jeszcze raz po tylu sekundach = ogień potwierdzony czasem
OGIEN_IGNORUJ_LOG_S = 30.0           # s: log "ignoruję: bez spadku HP" najwyżej raz na pole w tym czasie
OGIEN_MASKA_DANE = 1                 # pokrętło 0/1: 1 = trwała maska pól przechodnich z danych (epizody), omija OGIEN_MASKA_TYLKO_SCIANY
OGIEN_EPIZOD_PRZERWA_S = 60.0        # s: wykrycie po takiej przerwie to nowy epizod pola
OGIEN_EPIZODY_N = 3                  # tyle epizodów bez spadku HP ...
OGIEN_EPIZODY_GODZ = 2               # ... w tylu różnych godzinach doby kwalifikuje pole przechodnie do maski danych
OGIEN_EPIZODY_ZAPIS_S = 30.0         # s: zapis trasy/ogien_epizody.json najwyżej co tyle
OGIEN_PODPALENIE_S = 60.0           # 15.10: s po spadku HP na polu ognia: postać się pali (7.4: obrażenia długo po zejściu z ognia);
                                     # w tym czasie spadki HP nie obciążają innych pól (zginęliśmy przez złe przypisanie i maskę)
OGIEN_PODPALENIE_ZNANE = 1           # 24.10 pokrętło 0/1 (wydra 12:21): 1 = wejście na ZNANE parzące pole (hp:true w danych) też otwiera okno
                                     # podpalenia OGIEN_PODPALENIE_S; wcześniej okno otwierało tylko nowe oznaczenie pola, więc po przejściu przez
                                     # znane pole spadki HP z podpalenia fałszywie oznaczały sąsiednie pole (32497,32301) i wyrzucały je z maski
OGIEN_EPIZODY_SCAL = 1               # 24.10 pokrętło 0/1: 1 = zapis epizodów scala plik z pamięcią (hp = LUB, n/ost = max, godziny = suma);
                                     # wcześniej ostatni piszący proces nadpisywał cały plik i gubił cudze oznaczenia hp. 0 = jak dawniej
OGIEN_WEJSCIE_S = 2.0                # 15.10: s: spadek HP przypisujemy polu ognia tylko tuż po wejściu na nie (i bez stwora obok)
OGIEN_PARZY_ODL_CELU = 1             # 15.10: pola: celu tak blisko znanego parzącego pola nie atakujemy (klient poszedłby za nim w ogień)
OGIEN_PARZY_BUFOR = 0                # 22.10 (Karol: invincible wszedł w ogień przy lootcie, (33069,31730,z8), ~20 HP): pola wokół znanego
                                     # parzącego pola (Chebyshev) też są zakazane dla każdego ruchu (krok, klik, A*, loot, pościg);
                                     # wykrycie u invincible'a bywa przesunięte o pole. 0 = samo pole jak dawniej
OGIEN_POMIJAJ_PRZY_STWORZE = 1       # pokrętło 0/1: 1 = wykrycia ognia na polu stwora/celu albo obok niego (odl <= 1) pomijamy, dopóki HP nie spadnie
PLIK_OGIEN_EPIZODY = None if os.environ.get("RETRONIC_TESTY") else Path(__file__).resolve().parent / "trasy" / "ogien_epizody.json"
PLIK_OGIEN_STALE = None if os.environ.get("RETRONIC_TESTY") else Path(__file__).resolve().parent / "trasy" / "ogien_stale.json"   # zasiew i zapis maski
OGIEN_PODSUMOWANIE_S = 600.0       # s: odstęp podsumowania "[OGIEN] ogień: N stałych, M zmiennych"
OGIEN_ODSWIEZ_WALKA_S = 0.8        # s: odstęp wykryć w WALKA, gdy w widoku nie ma zmiennych pól (domyślnie jak OGIEN_ODSWIEZ_S = bez zmiany; spec P6 sugeruje 3, pokrętło 0.8-5)

JEDZENIE_CZAR_AKTYWNY = 0          # pokrętło 0/1 (na_zywo.json); 1 = czar zamiast wypadu po jedzenie, gdy mana wystarcza
JEDZENIE_CZAR_TEKST = "exevo pan"
JEDZENIE_CZAR_KLAWISZ = "F3"       # hotkey czaru w kliencie (F3 = exevo pan, Food)
JEDZENIE_CZAR_KOSZT = 30           # koszt many
JEDZENIE_CZAR_CZEKAJ_S = 1.5       # s po rzucie, zanim zjemy powstałe jedzenie
JEDZENIE_CZAR_CO_S = 60.0          # s: min. odstęp między rzutami
JEDZENIE_CZAR_PORAZKI = 3          # tyle rzutów z rzędu bez efektu wyłącza czar
JEDZENIE_CZAR_PRZERWA_PO_PORAZKACH_S = 600.0
JEDZENIE_CZAR_PLECAK_WAZNE_S = 120.0   # s: tyle ważny jest odczyt plecaka (wypad.py) "brak jedzenia"
# zapas jedzenia czarem (tylko z JEDZENIE_CZAR_AKTYWNY=1): exevo pan (F3), gdy w plecaku jest < JEDZENIE_ZAPAS_MIN sztuk
JEDZENIE_ZAPAS_MIN = 5             # pokrętło 1-20 (nie_wyzej): poniżej tylu sztuk (meat/ham/cheese/bread...) rzucamy F3
JEDZENIE_ZAPAS_EXHAUST_S = 5.0     # s: min. odstęp od DOWOLNEGO czaru bota przed rzutem F3 na zapas
JEDZENIE_ZAPAS_CO_S = 20.0         # s: min. odstęp między rzutami F3 na zapas
JEDZENIE_ZAPAS_PORAZKI = 3         # rzutów z rzędu bez przyrostu sztuk = pauza
JEDZENIE_ZAPAS_PAUZA_S = 600.0     # s pauzy po porażkach
JEDZENIE_ZAPAS_ODCZYT_S = 10.0     # s: tyle ważny jest odczyt plecaka (pamięć gry przez loot.ile_jedzenia)
JEDZENIE_ZAPAS_NIEZNANY_CO_S = 600.0   # s: plecak nieczytelny = F3 (zamiast ML) najwyżej raz na tyle
JEDZENIE_ZAPAS_REGEN_S = 45.0      # s: ML czeka na manę 30 tylko, gdy mana urosła w tym oknie (regeneracja działa)
JEDZENIE_ZAPAS_HOLD_MAX_S = 240.0  # s: tyle ML czeka na manę 30 dla F3 (potem rzuca, nie ma zakleszczenia)
JEDZENIE_ZAPAS_W_WALCE = 1         # 12.10: 1 = F3 na zapas także z potworem w JEDZENIE_SPOKOJ (nie w ucieczce ani przy HP do exura)
JEDZENIE_ZAPAS_NOTATKA_S = 120.0   # s: telemetria "głód, mana < 30, brak jedzenia" najwyżej raz na tyle
DIAGONAL_ODL = 2                   # pola: pościg do tak bliskiego celu może iść skosem (klikiem)
PRZEGLAD_W_LOOCIE = 0.8            # s: co tyle sprawdzamy potwory w trakcie podchodzenia do zwłok
ZWLOKI_WAZNE = 120                 # s od ZABICIA: odłożone zwłoki zbieramy, jeśli nie są starsze (nie resetowane przy przerwaniu)
ZWLOKI_ZASIEG = 12                 # pola: i nie dalej niż tyle (dalsze zostają na liście do końca TTL, tylko pomijane)
ZWLOKI_PRZED_CELEM = True          # zwłoki w odl 1-2, nic nie styka, cel nie ucieka w odl <= 4: najpierw zbierz, potem pościg (False = dawne)
ZWLOKI_PRZED_CELEM_ODL = 2         # pola: tak blisko zwłoki zbieramy przed ruszeniem za nowym celem
ZWLOKI_PRZED_CELEM_STYK = 2        # pola: żywy potwór tak blisko = walka przed zwłokami (loot.zbierz i tak by przerwał)
ZWLOKI_PRZED_CELEM_UCIEKAJACY = 4  # pola: uciekający cel tak blisko ma pierwszeństwo przed zwłokami
ZWLOKI_PRZED_CELEM_CHLOD_S = 3.0   # s: po przerwaniu takiego zbierania (mob obok) nie ponawiamy od razu
ZWLOKI_PO_UCIECZCE = True          # po ucieczce: czasy zwłok dosunięte o czas ucieczki + priorytet powrotu po nie (False = dawne)
ZWLOKI_PO_UCIECZCE_PRIORYTET_S = 30.0  # s po wyjściu z ucieczki, w których zwłoki mają pierwszeństwo przed szukaniem celu
LOOT_PRZERWANY_PAUZA = (0.3, 0.6)  # s: pauza po przerwanym zbieraniu zwłok (bez niej tick kręci się bez przerwy)
LWW_ZAMKNIECIE_PROB = 3            # tyle prób zamknięcia zaległego okna zwłok po przerwanym locie w walce
LWW_ZAMKNIECIE_S = 20.0            # s: po tylu sekundach od przerwania porzucamy zamykanie zaległego okna
CZEKAJ_BLISKO = 5                  # pola: tak blisko cel bez drogi nie jest odpuszczany, tylko czekamy
LOOT_PO_WALCE = 8                  # pola: żywy potwór tak blisko wstrzymuje zbieranie zwłok
LOOT_BLOK_MAX = 8                  # s: po tylu sekundach wstrzymania loot i tak rusza
IGNOROWANIE_BLISKO = 3             # pola: ignorowany potwór tak blisko jest znów brany pod uwagę
# 13.10 (spec P1a): twarde ignorowanie; podejście na IGNOROWANIE_BLISKO samo go nie zdejmuje
IGNOR_TWARDE = 1                   # 0/1: wyłącznik (0 = dawne ignorowanie zdejmowane przy d <= IGNOROWANIE_BLISKO)
IGNOR_DROGA_CO_S = 1.0             # s: najczęściej tak sprawdzamy, czy za ścianą otworzyła się droga (na id)
ODPUSZCZ_LOG_S = 5.0               # s: log "Odpuszczam ... za ścianą" najwyżej raz na tyle s na id
# spec P1b: blokujący na jedynym wyjściu (domyślnie WYŁĄCZONE do pomiaru)
BLOK_WYJSCIE = 0                   # 0/1: droga bez stworów przez zajęte pole = bij blokującego, nie idź w stwora
BLOK_KROKI = 2                     # tyle pierwszych pól drogi bez stworów sprawdzamy pod kątem stworów
# spec P2a: strażnik celu (cel obok bez postępu)
STRAZNIK_CEL = 1                   # 0/1
STRAZNIK_CEL_S1 = 12.0             # s bez postępu przy odl <= 1: Escape, ponowny klik
STRAZNIK_CEL_S2 = 25.0             # s bez postępu: kontrola pozycji i twarde ignorowanie celu
STRAZNIK_CEL_PRZERWA = 4.0         # s: przerwa między wywołaniami strażnika (walcz() nie wołane) resetuje okno bez postępu
STRAZNIK_IGNOR_S = 45.0            # s ignorowania celu po S2
STRAZNIK_S2_SERIA = 3              # tyle odpaleń S2 w STRAZNIK_S2_OKNO_S = powiadomienie
STRAZNIK_S2_OKNO_S = 300.0
# spec P2b (w zadaniu: P2c): strażnik postępu globalny (domyślnie WYŁĄCZONY)
STRAZNIK_POSTEP = 0                # 0/1
STRAZNIK_POSTEP_S1 = 90.0          # s bez postępu: reset stanu walki
STRAZNIK_POSTEP_S2 = 180.0         # s: zmiana celu patrolu / skok na najbliższy punkt trasy
STRAZNIK_POSTEP_S3 = 300.0         # s: powiadomienie krytyczne
OBJAZD_IGNOROWANIE = 90            # s ignorowania potwora za ścianą (inaczej wybieramy go w kółko)
POGON_IGNOROWANIE = 20             # s ignorowania odpuszczonego celu
PLIK_UCIEKANIA = instancja.S.uciekanie   # bez RETRONIC_ID: pomocnik/uciekanie.json
KATALOG_TRAS = Path(__file__).resolve().parent / "trasy"
# poza trasy/: mozg.py traktuje każdy trasy/*.json jako trasę do wyboru
PLIK_DRZWI = KATALOG_TRAS / "drzwi_jaskinia.json"   # R1c: drzwi w jaskini (przejście dla pościgu i patrolu)
PLIK_ZNANYCH = Path(__file__).resolve().parent / "znane_pola.json"
ZNANE_ZAPIS_CO = 120               # s między zapisami nowych znanych pól (tylko na żywo)
RUCH_PRZED_SMIERCIA = 1.5          # s: krok celu tak niedawno = zwłoki mogą być na polu, na które wchodził
POSCIG_OKNO = 3.0                  # s jednej szybkiej pętli pościgu (potem pełny obieg tick)
POSCIG_OKNO_DOBRY = 6.0            # s: twardy limit jednej pętli przy ciągłym pościgu (okno przedłużane co POSCIG_OKNO_KONTYN)
POSCIG_OKNO_KONTYN = 1.5           # s: o tyle przedłużamy okno, gdy pętla biegnie (>= 3 kroki, cel dalej niż obok), po świeżym przeglądzie
POSCIG_KROK_S_NA_PREDKOSC = 0.047  # s kroku na jednostkę prędkości pola z mapy (pole 12 ~0,6 s, 16 ~0,75 s, 20 ~0,9 s)
POSCIG_BRAK_WSPOL = 1.4            # próg braku zmiany pozycji = max(POSCIG_BRAK_ZMIANY, WSPOL * czas kroku pola)
POSCIG_SERIA_MAX = 7.0             # s ciągłego pościgu bez zbliżania się, po których jest krótka przerwa
POSCIG_PRZERWA = 1.5               # s bez szybkiej pętli po przekroczeniu POSCIG_SERIA_MAX
POSCIG_SERIA_LUKA = 1.5            # s przerwy między pętlami kończy "ciągły" pościg
POSCIG_POLL = (0.02, 0.035)        # s: sen między odczytami pozycji w oczekiwaniu na zmianę po strzałce (+ koszt jednego RPC "poscig")
POSCIG_PO_KROKU = (0.02, 0.07)     # s: losowe opóźnienie po zmianie pozycji, przed następną strzałką
POSCIG_ZAWAHANIE = (0.25, 0.45)    # s: rzadkie "zawahanie" po kroku
POSCIG_ZAWAHANIE_P = 0.06          # prawdopodobieństwo zawahania po kroku (ok. 1 na 16; dawniej 0,125)
POSCIG_KROK_MIN = 0.08             # s: najkrótszy odstęp między kolejnymi strzałkami
POSCIG_BRAK_ZMIANY = 0.45          # s bez zmiany pozycji po strzałce = ściana/blokada, wyjście z pętli
POSCIG_PRZEGLAD = 1.2              # s: jak często pętla sprawdza HP gracza i otoczenie (robione w czasie trwania kroku, nie przed strzałką)
POSCIG_PRZEGLAD_WIEK = 0.8         # s: najstarszy akceptowany skan stworów w przeglądzie (cache wątku skanera rdzenia)
POSCIG_PONOW_BRAK = 1              # ile razy po braku zmiany pozycji ponowić strzałkę, zanim pętla uzna ścianę (0 = wył.)
POSCIG_TRZYMAJ = True              # pościg: TRZYMANY klawisz (ciągły marsz) zamiast stuknięć; False = dawne stuknięcia
POSCIG_TRZYMAJ_PRZEGLAD = 1.0      # s: przegląd HP/otoczenia w trybie trzymania (ZMIANA Q3 11.10: 0.6 -> 1.0; strażnik klawiszy
                                   # dostaje puls przed, w trakcie (między gracz a stwory) i po przeglądzie, WATCHDOG_S bez zmian)
POSCIG_TRZYMAJ_OKNO_DOBRY = 12.0   # s: twardy limit jednej pętli w trybie trzymania (przerwa = puszczenie klawisza)
POSCIG_ANTYCYPACJA = True          # nowy kierunek (zakręt A*) naciskany jeszcze w trakcie bieżącego kroku (kolejka klienta)
POSCIG_ANTYCYP_PO = 0.08           # s po naciśnięciu z postoju, zanim wolno nacisnąć klawisz kolejnego kroku (klient musi zacząć krok)
POSCIG_HISTEREZA_S = 0.4           # s: tyle po zmianie kierunku nie zmieniamy go znowu (o ile stary nadal zbliża do celu)
POSCIG_HISTEREZA_ODL = 3           # pola: zmiana osi tylko, gdy cel jest na nowej osi co najmniej tyle pól dalej
POSCIG_PINGPONG_S = 1.5            # s: na pole, na którym staliśmy w tym czasie, nie cofamy się (ping-pong)
POSCIG_OSCYLACJA_N = 2             # powrotów A-B-A w POSCIG_OSCYLACJA_S s = oscylacja: wyjście z pętli
POSCIG_OSCYLACJA_S = 3.0           # s
POSCIG_BEZ_POSTEPU_KROKI = 6       # tyle kroków w POSCIG_BEZ_POSTEPU_S s i przesunięcie <= 1 pole = oscylacja
POSCIG_BEZ_POSTEPU_S = 4.0         # s
POSCIG_COFNIECIE_S = 0.25          # s: powrót na poprzednie pole szybciej = serwer cofnął krok (pole zajęte)
POSCIG_BLOK_S = 3.0                # s: tyle pole, z którego cofnięto krok, liczymy za zajęte
POSCIG_PRZERWA_PO_ZAWROCIE = 1.0   # s bez szybkiej pętli po oscylacji/zawracaniu: stoimy i bijemy (zwykły tick); ZMIANA Q4 11.10: 3.0 -> 1.0
POSCIG_STUK_PO_OSCYLACJI = 1.5     # s: po oscylacji pościg stuknięciami (nie trzymaniem); ZMIANA Q4 11.10: 5.0 -> 1.5
POSCIG_ZAWR_MIN_HIST = 4           # pól w historii pętli (start + kroki): krócej to nie oscylacja (cel tylko zmienił stronę
                                   # w trakcie pierwszego kroku) = wyjście bez kary POSCIG_PRZERWA_PO_ZAWROCIE/STUK_PO_OSCYLACJI
POSCIG_PRZEWIDYWANIE_ODL = 3       # pola: kierunek względem celu przewidzianego o krok, gdy cel idzie prosto i jest dalej niż tyle
POSCIG_SKOS = True                 # skos trzymanym klawiszem numpadu, gdy POSCIG_SKOS_KOSZT < 2 (taniej niż dwa proste)
POSCIG_SKOS_KOSZT = 3.0            # czas kroku po skosie / czas kroku prostego (NIEZMIERZONY: zmierz sonda_skosu.py; <2 włącza skosy)
POSCIG_SKOS_ODL = 3                # skos tylko, gdy cel jest co najmniej tyle pól (Chebyshev) dalej
POSCIG_SKOS_AWARYJNY = 1           # 12.10: 1 = gdy drogi prostej nie ma (albo to długi objazd), a po skosie jest (róg: dwa pola
                                   # w osiach to ściana, pole po skosie wolne) - skos numpadem/klikiem, niezależnie od KOSZT
POSCIG_SKOSY_ZAPAS = 1             # R1c: 1 = gdy drogi bez skosów nie ma (korytarz (32492,32295)-(32500,32303) z8 chodliwy tylko po skosie), druga
                                   # próba z skosami (krok_skos numpadem) i do ignorowanego "za ścianą" też; niezależnie od POSCIG_SKOS_AWARYJNY
POSCIG_SKOSY_MAX_DL = 40           # R1c: najdłuższa droga ze skosami (pola), którą ta druga próba przyjmuje
PATROL_DRZWI = 1                   # R1c: 1 = drzwi z trasy/drzwi_jaskinia.json to przejście dla pościgu i patrolu (zamknięte: Use z pola obok)
DRZWI_KROK_S = 1.0                 # R1c: s bez ruchu przy drzwiach (zwykły krok/klik) = zamknięte, wtedy Use
DRZWI_STARA_S = 20.0             # R1c: s od ostatniej próby, po których epizod przy drzwiach zaczyna się od nowa (licznik prób do zera)
DRZWI_PROB = 3                     # R1c: max Use na drzwiach, potem odpuszczenie z jedną notatką
DRZWI_ODPUSC_S = 60.0              # R1c: s, przez które odpuszczone drzwi nie są przejściem
DRZWI_PONOW = 0                    # F1 (17.10): 1 = flaga "drzwi otwarte" starsza niż DRZWI_STARA_S s jest przeterminowana (drzwi mogły się zamknąć): podejście do drzwi i Use znów możliwe; 0 = jak dotąd
DRZWI_TRASA = 1                    # 22.10: 1 = zamknięte drzwi NA NAGRANEJ TRASIE (dojście, trasa; pole trasy albo pole pośrednie na prostym odcinku, które mapa uznaje za ścianę, trasa_io.drzwi_na_trasie): bot dochodzi na pole przed drzwiami, staje, krok, a gdy nic - Use i krok (max DRZWI_TRASA_PROB), potem jak dotąd; 0 = jak dotąd (invincible 22.10 10:52 biła w ścianę (33166,31817,z7) 10x)
DRZWI_TRASA_PROB = 3               # 22.10: max Use na drzwiach trasy, potem odpuszczenie na DRZWI_TRASA_ODPUSC_S s i dawne zachowanie
DRZWI_TRASA_ODPUSC_S = 60.0        # 22.10: s, przez które odpuszczone drzwi trasy nie są obsługiwane
DRZWI_TRASA_OKNO = 3               # 22.10: drzwi obsługujemy, gdy indeks celu trasy jest nie dalej niż tyle punktów przed pierwszym punktem za drzwiami (ścinanie zakrętów nie przeskoczy ściany)
DRZWI_TRASA_ODL = 8                # 22.10: ...i postać jest nie dalej niż tyle pól od pola przed drzwiami
DRZWI_SPOKOJ = 1                   # 22.10: 1 = przed Use na drzwiach (trasa i pościg/patrol, _drzwi_hak) czekamy na stojącą pozycję (2 odczyty co 0,4 s, jak pietra._przed_use): Use w trakcie kroku klient gubi (wydra (32505,32270,z8) 22.10); 0 = jak dotąd
DRZWI_NAJPIERW_KROK = 1            # 24.10 (Karol: „sam je zamyka, próbuje, otwiera i przechodzi”): 1 = przed KAŻDYM Use na drzwiach (trasa i _drzwi_hak) najpierw krok przez pole drzwi (po chwili stania jeszcze raz); Use tylko gdy krok nie ruszył postaci, po Use znowu krok. Use na OTWARTYCH drzwiach je zamyka, a stanu drzwi bot nie czyta (mapa jest statyczna, drzwi = ściana); 0 = jak dotąd (trasa: tylko pierwszy krok epizodu, potem Use)
DRZWI_KLUCZ = 1                    # 24.10 (Karol: „niech się nauczy otwierać drzwi”, Marinarra): 1 = DOJŚCIE (CavebotDojscie) przechodzi drzwi zamknięte na klucz z wyprawa.PLANY_PK["klucze"] (A* przez nie, krok, Use klucza z plecaka na drzwiach, krok; jak wypad._drzwi); 0 = jak dotąd (drzwi to ściana, dojście z korytarza z9 Ab'Dendriel się nie udawało)
SMIERC_STOP = 0                    # 16.10 (R5/P5): 1 = po zgonie bot nic nie robi: stan MARTWY, jeden STOP + jedno powiadomienie (nick, czas, miejsce), zero kliknięć i modelu; 0 = jak dotąd
OBSERWATOR_PK_KONTEKST = 0         # 16.10 (P10): 1 = obserwator (Haiku) dostaje pk_stan, karencję PK i wrogów oraz instrukcję, że PAUZA_PK z aktywną karencją to stan zamierzony; 0 = jak dotąd
SMIERC_ODCZYTY = 3                 # SMIERC_STOP: tyle kolejnych odczytów HP == 0 potwierdza zgon (jeden/dwa to możliwy fałszywy odczyt; w tym czasie obieg stoi bez akcji)
SMIERC_SKOK = 8                    # SMIERC_STOP: HP == 0 i skok pozycji o tyle pól (albo zmiana piętra) względem ostatniej żywej próbki = respawn w świątyni, zgon potwierdzony od razu
ROZLACZENIE_STOP = 1                # 21.10 (spec SPEC_rozlaczenie_1021): 1 = klient wylogowany (pamięć gry stoi >= 25 s, a zrzut pokazuje ekran logowania "Character List"/"Enter Game"): bot nie wysyła żadnych klawiszy ani kliknięć, jedno powiadomienie critical; 23.10: domyślnie 1 (gebelish i odchyd nie miały klucza w na_zywo.json i po resecie naciskały klawisze na liście postaci); 0 = jak dotąd
ROZLACZENIE_WYJSCIE = 1             # 23.10 (decyzja Karola: boty wyłączane po wylogowaniu od razu): 1 = wykryte wylogowanie KOŃCZY proces (log WYLOGOWANY: kończę bota, znacznik instancji wylogowany.json z mapą i trybem; relog w nadzorcy uruchamia bota od nowa); 0 = dawna pauza w żywym procesie z wznowieniem po powrocie do gry
START_PO_UPADKU = 1                 # 23.10: 1 = start bota na piętrze spoza pętli, tuż pod nią (<= START_UPADEK_ODL pól poziomo, 1-2 piętra niżej) = upadek w dziurę: najpierw wyjście w górę (wpadniecie.z_kieszeni), bez dojścia (które biegło po ścianach); 0 = jak dotąd
START_UPADEK_ODL = 12               # pola poziomo (Chebyshev) od punktu pętli, w których start na innym piętrze liczy się jako upadek
START_CZEKAJ_POSTAC_S = 60          # 23.10: s, przez które start bota (mozg.py) czeka, aż strażnik zwróci pozycję postaci; po tym czasie głośna odmowa startu (bez Traceback)
SKOS_ZLY_S = 30.0                  # s: pole po skosie, na które nie weszliśmy (brak zmiany pozycji), nie jest ponawiane
SKOS_LOG_S = 3.0                   # s: min. odstęp wpisów "Skos awaryjny" w logu
POSCIG_HP_SPADEK = 8               # pp HP gracza: tyle straty w oknie kończy pętlę
POSCIG_HP_MARGINES = 10            # pp nad progiem ucieczki: poniżej nie wchodzimy w szybki pościg
POSCIG_PAMIEC = True               # pościg "na pamięć": ranny cel zniknął z widoku żywy = idziemy za nim (False = wył.)
POSCIG_PAMIEC_S = 7.0              # s: tyle trwa pościg na pamięć (potem wracamy do trasy); pokrętło 3-12
POSCIG_PAMIEC_POL = 9              # pola: najdalej tyle za ostatnią pozycją celu (wzdłuż wektora ucieczki); pokrętło 4-14
POSCIG_PAMIEC_MAKS_ODL = 5         # pola: dalej niż tyle od nas zniknął cel = bez pościgu na pamięć (ZMIANA 11.10: dwa żywe
                                   # przypadki skończyły się limitem 7 s przy odl 8-10; cel HP 20% ucieka 0,85 pola/s, my 1,26); pokrętło 2-10
POSCIG_OSTATNI_TRZYMAJ = True      # S4 11.10: w "ostatni" nie puszczamy klawisza, gdy cel stoi dokładnie przed nami na kierunku
                                   # marszu (kolejny krok blokuje on sam, nie ma kroku za dużo); False = dawne puszczanie
POSCIG_OSTATNI_DOCISKAJ = True     # 12.10: cel dalej niż 1 pole, a krok z klawisza kończy się przy nim (q <= 1 od celu): klawisz TRZYMAMY
                                   # dalej (dociskamy ten krok), zamiast puszczać. Pozycja gracza zmienia się na STARCIE kroku, więc
                                   # puszczenie tu odbierało krok, który zbliża do celu: postać stała ~1,3 s (POSCIG_BRAK_WSPOL * czas
                                   # kroku) i ruszała dopiero po ponowieniu = 1,5 s/krok zamiast 0,9; uciekający szczur (krok ~1,5 s)
                                   # zostawał w odl 2-3 przez 25 s. Pętla i tak wychodzi i puszcza klawisz przy odl <= 1; False = dawne
POSCIG_DZIURA_KROK = True          # 22.10: zakręt kolejkowany w pościgu (hold) nie może wchodzić z POZ w nauczoną dziurę / pole zmiany piętra
                                   # (klient ruszał dopiero po zmianie klawisza z poz, nie z pola po kroku w toku: dawajkesh 10:49 wpadł w znaną
                                   # dziurę); False = dawne
POSCIG_VKROK_SCIANA = True         # 11.10: trzymany klawisz po dojściu prowadzący w ścianę/zajęte pole nie jest krokiem w toku
                                   # (v_krok=None, decyzja liczona z poz): bez fałszywego "zawracania" (39 z 152 pościgów); False = dawne
POSCIG_PAUZA_TICK_DALEKO = (0.0, 0.03)   # s: Q5 11.10: pauza po ticku z WALKA i celem dalej niż 1 pole (było 0.05-0.15)
PAMIEC_HP = 35                     # % HP: cel, który zniknął żywy z tak niskim HP (albo trafiony wcześniej), ścigamy na pamięć
PAMIEC_ODL_MIN = 2                 # pola: cel, który zniknął bliżej, zginął (atakujemy tylko z bliska), nie uciekł
PAMIEC_HP_MARGINES = 15            # pp nad progiem ucieczki: poniżej nie wchodzimy w pościg na pamięć (ani w nim nie zostajemy)
PAMIEC_HP_TOL = 20                 # pp: tyle HP może różnić się cel odnaleziony (inne id, ta sama nazwa) od zapamiętanego
PAMIEC_LOOT_ODL = 3                # pola: odłożone zwłoki tak blisko zbieramy przed pościgiem na pamięć
PAMIEC_SKAN_WIEK = 0.4             # s: najstarszy skan stworów z cache rdzenia w trakcie pościgu na pamięć
PAMIEC_BEZ_RUCHU = 2.0             # s bez zmiany pozycji w pościgu na pamięć = zablokowani, kończymy
WAGA_HP = 25                       # wybór celu: 100% HP liczy się jak 4 pola dalej
CELE_PIERWSZE = ""                 # 24.10 (Karol: "waspy zawsze w pierwszej kolejności, bo trują"): nazwy potworów po przecinku (np. "Wasp,Snake"; wielkość liter bez znaczenia), bite PRZED każdym innym kandydatem (bliższy z listy pierwszy); "" = wyłączone, klucz wyboru jak dawniej. Cel musi być też w --potwory. Nie omija ucieczki, HP, PK, ognia, dziur ani stref zakazanych (kandydaci filtrowani jak zawsze); tylko ręcznie w na_zywo.json
CELE_PIERWSZE_ZMIANA_ODL = 3       # pola: potwór z CELE_PIERWSZE tak blisko (i w widoku) odrywa nas od bitego celu spoza listy; dalszy czeka, aż obecny cel padnie; w dojściu/wypadzie: z listy OBOK nas = walka zamiast biegu
PROSTO_ZASIEG = 4                  # pościg: do tylu pól idziemy prosto, gdy mapa nie zna krótkiej drogi
DROGA_OBJAZD = 4                   # bez pełnej mapy: droga dłuższa niż 2x linia prosta + tyle pól = objazd
DROGA_LIMIT = 400                  # maks. węzłów BFS przy szukaniu drogi po znanych polach
MAPA_OBJAZD = 8                    # pełna mapa: objazd dopiero, gdy droga > 2x linia prosta + tyle pól
MAPA_LIMIT = 4000                  # maks. rozwiniętych pól A* na pełnej mapie (brak drogi w limicie = objazd)
SCIANA_WAZNA = 6                   # s: nauczona ściana na polu przechodnim wg mapy (stwór, gracz, drzwi)
SCIANA_STWOR = 1.5                 # s: pole, na którym tak niedawno stał stwór, nie zostaje ścianą
CZEKAJ_DROGA = 8                   # pola drogi: tylko przy tak krótkiej drodze czekamy, aż cel podejdzie
NIEOSIAGALNY_DROGA = 15            # pola drogi: dłuższa (albo brak) = cel nieosiągalny, ignorujemy twardo
NIEOSIAGALNY_ZBLIZENIE = 2         # o ile pól musi zmaleć dystans prosty, by zdjąć "nieosiągalny"
KROK_SCIANA = 0.45                 # s bez ruchu po strzałce = krok się nie udał (wcześniej krok może trwać)
DROGA_DO_PRZODU = (3, 5)           # ile pól drogi do przodu celujemy kliknięciem
_CP_CACHE = ("", frozenset())      # 24.10: (tekst CELE_PIERWSZE, zbiór nazw casefold)
_K = 1 << 17                       # klucz pola w droga(): x*_K + y (|y| < 65536)
PROG_UCIEKANIA_DOMYSLNY = {"rat": 30}   # % HP, przy którym gatunek zaczyna uciekać (uczony na żywo)
CZUJNOSC = 15                      # pp nad progiem ucieczki: od tego HP celu sprawdzamy go bardzo często
KLIK_PONOW = 1.5                   # s: ponów klik w ten sam cel, jeśli jeszcze nie doszliśmy
KLIK_BEZ_RUCHU = 1.2               # s bez zmiany pozycji po kliku -> klik nie działa, idziemy strzałkami
KLIK_ODSTEP = 0.4                  # s: min. odstęp między kliknięciami w mapę (maks. ~2,5 kliku/s)
# marsz klikiem w patrolu i dojściu (20.10, wzór: serwis.idz_pewnie): jeden klik w najdalsze pole drogi w widoku, do którego WSZYSTKIE
# pola po drodze są zwykłe (bez schodów/dziur i ich sąsiedztwa, ognia, dziur nauczonych, drzwi, zajęte przez stwory/graczy), klient idzie ciągiem
MARSZ_KLIK = 0                     # pokrętło 0/1 (nie_wyzej): 1 = marsz klikiem w patrolu/dojściu; 0 = dotychczasowe chodzenie bit w bit
MARSZ_KLIK_MAKS_POL = 5            # pokrętło 2-7: ile pól naprzód klikamy naraz (widok ma ±7 x ±5, klikamy z 1 polem zapasu od krawędzi)
KROK_BEZ_SCIAN = 0                 # pokrętło 0/1 (nie_wyzej): 1 = krok_do po nieudanym pierwszym kierunku ponawia go raz i nie wciska zapasowych kierunków w pola, które mapa jednoznacznie uznaje za ścianę (przechodnie False / flaga 4); pole nieznane (None) nadal próbujemy; 0 = dotychczasowe
# 22.10 (wydra, trolle_patrol z8/z9: 88 "krok X nie ruszył" w 20 min, gracze widzą "bicie w ściany"): krok_do nie miał pamięci między obiegami.
# `zablokowane` jest czyszczone po każdym udanym kroku (także kroku wstecz), `nieudane` zeruje udany krok w stronę celu, a nauczona ściana na polu
# przechodnim wg mapy wygasa po SCIANA_WAZNA = 6 s: pętla "Up (nie rusza), Left/Right (ściany), Down (wstecz, udany), Up (udany), Up (nie rusza)..."
# trwała ponad 40 s (32478,32274,z8). KROK_ZLY=1: pole, w które krok strzałką nie udał się KROK_ZLY_N razy z rzędu (bez udanego wejścia między
# próbami, bez stwora na polu), jest zakazane na KROK_ZLY_S s (kolejny nieudany próbny krok po wygaśnięciu: x2, maks KROK_ZLY_MAX_S; pole, które
# mapa uznaje za ścianę: KROK_ZLY_SCIANA_S). Zakaz = pominięcie w krok_do (bez cofania się o pole), nauczona ściana dla A* (droga/patrol/skos)
# i sygnał dla patrolu (zmiana miejsca zamiast kręcenia się). 0 = dotychczasowe zachowanie.
KROK_ZLY = 1                       # pokrętło 0/1 (nie_nizej)
KROK_ZLY_N = 2                     # tyle nieudanych kroków w to samo pole z rzędu = zakaz (1-5)
KROK_ZLY_S = 45.0                  # s: pierwszy zakaz pola (potem x2 do KROK_ZLY_MAX_S)
KROK_ZLY_MAX_S = 180.0             # s: górna granica kolejnych zakazów tego samego pola
KROK_ZLY_SCIANA_S = 300.0          # s: zakaz pola, które mapa uznaje za ścianę (krok w ścianę z mapy to nie przejściowa blokada)
KROK_ZLY_OKNO_S = 60.0             # s: nieudane kroki starsze niż tyle (i po zakazie) nie sumują się z kolejnymi
KROK_ZLY_DOJSCIE_S = 4.0           # s: w dojściu zakaz pola, które mapa uznaje za przechodnie, jest krótki (x2 do 4x); 0 = jak poza dojściem
MARSZ_BEZ_RUCHU_S = 1.2            # s bez zmiany pozycji po kliku = klient nie idzie: ten odcinek wraca do kroków klawiszem
MARSZ_BLOK_S = 8.0                 # s: tyle (i w promieniu MARSZ_BLOK_R pól) po braku ruchu nie klikamy, tylko krok klawiszem
MARSZ_BLOK_R = 3
MARSZ_LIMIT_BAZA_S = 0.8           # limit czasu jednego marszu: baza + na pole (jak serwis)
MARSZ_LIMIT_POLE_S = 0.45
MARSZ_PORZUCONY_S = 1.5            # s bez obiegu marszu = inny priorytet przejął pętlę, marsz uznajemy za skończony
NAUKA_KROK = 5                     # pp: o tyle maks. przesuwa próg uciekania jedna obserwacja
PROG_UCIEKANIA_MIN = 25            # % HP: niżej progu nie uczymy (ucieczkę widzimy z opóźnieniem, przy niższym HP)
UTKNIECIE_TRASA = 27.0             # s w IDZ bez zmiany punktu i na <= UTKNIECIE_POLA polach = utknięcie na trasie
UTKNIECIE_POLA = 4                 # tyle różnych pól (albo mniej) w oknie utknięcia
UTKNIECIE_LUKA = 6.0               # s: przerwa w IDZ (walka, loot) dłuższa niż to zeruje okno utknięcia
UTKNIECIE_SEGMENT = 1               # 1 = w dojściu (CavebotDojscie) powrót na trasę po utknięciu tylko w bieżącym odcinku (to samo piętro, przed najbliższym przejściem pięter); nigdy dalej
UH_BEZ_DOJSCIA = 1                  # 1 = UH (robienie run) nie startuje w trakcie dojścia na spot (w mieście/po drodze); wznawia się na łowisku
UTKNIECIE_KAND = 14                # tylu najbliższych (prosto) punktów trasy sprawdzamy A* po utknięciu
KROK_WSTECZ_S = 5.0                # s: pole, z którego dopiero przyszliśmy, to "poprzednie" (krok_do)
TRASA_OBJAZD = 3                   # pola: droga do punktu trasy dłuższa od prostej o tyle = prowadzimy po A*
TRASA_DO_PRZODU = (4, 6)           # ile punktów trasy do przodu celujemy kliknięciem
ODLEGLOSC_ZBLIZANIA = 1            # potwór bliżej niż przy wyborze o tyle pól = podchodzi
SCINANIE = (0.3, 2)                # szansa i maks. ile punktów trasy do przodu celować
PAUZA_KROTKA = (0.04, 0.4, 1.5)    # szansa na krok, min s, max s
PAUZA_DLUGA = (0.005, 3.0, 8.0)
REAKCJA = (0.15, 0.45)             # s od zauważenia potwora do pierwszego ataku
DRUGI_CEL = 0.15                   # szansa wyboru drugiego najbliższego potwora
DECYZJE_LOG = 1                    # 15.10: telemetria "decyzja" (D1 wybór celu, D2 start pościgu: opcje z cechami); tylko log, 0 = wyłączone
D3_LOG = 1                         # 16.10 (SPEC_model_D3_utkniecia_1015, krok A): telemetria "decyzja" D3 + "d3_wynik" przy zawieszce poza walką (opcje wyjścia z cechami); tylko log, 0 = wyłączone
D3_PROG_S = 30.0                   # s: pozycja w promieniu 2 pól poza walką (< 30% czasu walki), exp bez zmian, tak długo = zawieszka (d3_zawieszka.py)
D3_REAKCJA = 0                     # F1 (17.10): 0 = D3 tylko loguje (jak dotąd); 1 = cień: rekord "d3_reakcja" z opcją, którą wybrałaby reguła (bez wykonania)
D3_ALARM_S = 0.0                   # F1 (17.10): >0 = zawieszka D3 trwająca tyle s daje jedno powiadomienie krytyczne (bez STOP); 0 = wyłączone
RATUNEK_HAIKU = 0                  # 19.10 (SPEC_ratunek_haiku_1019, F1): 0 = wyłączone; 1 = cień: detektor zachowań „jak bot” (S1-S7, ratunek.py) tylko loguje „wołałbym Haiku”; 2 (wykonanie) NIE istnieje
RATUNEK_HAIKU_PYTAJ = 0            # 19.10 (F2a): 1 (przy RATUNEK_HAIKU=1) = przy każdym sygnale Haiku W CIENIU (osobny wątek, bez ruchu i bez czekania; ratunek_cien.py): rekord haiku_cien w logi/ratunek-<data>.jsonl
RATUNEK_PIETRO_S = 10.0            # S2: s poza walką na piętrze, którego bieżąca trasa nie ma
RATUNEK_STOI_S = 30.0              # S3: s w promieniu RATUNEK_STOI_PROMIEN pól poza walką, exp bez zmian
RATUNEK_STOI_PROMIEN = 2           # S3: pola (Czebyszew)
RATUNEK_KRAG_WIZYT = 4             # S4: tyle wejść na to samo pole w RATUNEK_KRAG_S s poza walką = kręci się
RATUNEK_KRAG_S = 60.0              # S4: okno [s]
RATUNEK_OSC_N = 3                  # S4: tyle powrotów A-B-A w oknie = oscylacja
RATUNEK_KROKI_N = 6                # S5: nieudane kroki z rzędu bez zmiany pozycji
RATUNEK_KLIK_N = 5                 # S6: kliknięcia bez efektu w ten sam cel
RATUNEK_OKRAZENIA_N = 3            # S7: tyle końców okrążenia trasy w RATUNEK_OKRAZENIA_S s bez ruchu > 2 pola
RATUNEK_OKRAZENIA_S = 60.0         # S7: okno [s]
RATUNEK_PRZERWA_S = 120.0          # debounce: ten sam sygnał w tym samym miejscu najwcześniej po tylu s
RATUNEK_LIMIT_H = 20               # limit wywołań Haiku na godzinę (Q3); w cieniu tylko flaga „ponad limit”
STRAZNIK_ORBITY = 0                # 20.10 (SPEC_orbity_straznik_1020, B): 0 = wyłączony (zero zmian); 1 = cień: log [ORBITA] + telemetria straznik_orbita; 2 = działa: stop chodzenia, potem rotacja sposobów naprawy aż do skutku, nigdy STOP (straznik_orbity.py)
STRAZNIK_ORBITA_S = 60.0           # s okno orbity: >= STRAZNIK_ORBITA_ZMIAN zmian pozycji w <= STRAZNIK_ORBITA_POL polach poza walką (albo złe piętro tak długo)
STRAZNIK_ORBITA_POL = 8            # maks. różnych pól orbity (Karol 20.10: 8; pomiar 14-20.10 0 fałszywych)
STRAZNIK_ORBITA_ZMIAN = 15         # min. zmian pozycji w oknie (Karol 20.10: 15)
STRAZNIK_WYJSCIE_S = 90.0          # s aktywne (bez walki/lootu) na dłuższe sposoby naprawy (plan pięter, A* do punktu trasy); potem następny sposób z rotacji, nigdy STOP
STRAZNIK_PETLA = 0                 # 24.10 (Wydra 12:43-12:49: 6,5 min w kieszeni 4x4, 0 zabić): 0 = wyłączone (zero zmian); 1 = strażnik orbit (STRAZNIK_ORBITY 1 = cień, 2 = działa) wykrywa też PĘTLĘ: ta sama sekwencja pól > POWTORZ razy albo STRAZNIK_PETLA_S s w ramce bez postępu (exp, piętro)
STRAZNIK_PETLA_S = 45.0            # s w ramce STRAZNIK_PETLA_RAMKA bez zabicia i zmiany piętra (tylko stan IDZ + walka/loot do udziału)
STRAZNIK_PETLA_RAMKA = 4           # maks. rozmiar ramki (pól na bok): 4 = 4x4
STRAZNIK_PETLA_POWTORZ = 3         # tyle powtórzeń tej samej sekwencji pól wolno; czwarte = pętla (Karol 24.10: „nie więcej niż 3 razy")
STRAZNIK_PETLA_CYKL_S = 12.0       # sekwencja musi trwać co najmniej tyle s (mrugnięcie A-B-A-B w sekundę to nie pętla)
STRAZNIK_PETLA_WALKA = 0.3         # maks. udział walki/lootu w oknie ramki (walka w miejscu to nie pętla)
ZWIECHA = 1                        # 23.10 (wydra: 29 min walki bez zabicia): 1 = detektor zwiechy walki + drabina napraw (zwiecha.py), 0 = wyłączony; NAPRAWA, nigdy STOP
ZWIECHA_N = 3                      # zdarzeń ("klików bez efektu" / S2 strażnika celu) w ZWIECHA_OKNO_S bez przyrostu expa = zwiecha (szczebel 1)
ZWIECHA_OKNO_S = 300.0             # s okno liczenia pierwszych zdarzeń
ZWIECHA_KROK_N = 2                 # kolejnych zdarzeń do następnego szczebla (albo >= 1 zdarzenie i ZWIECHA_KROK_S)
ZWIECHA_KROK_S = 100.0             # s od szczebla do następnego (przy >= 1 nowym zdarzeniu)
ZWIECHA_CISZA_S = 240.0            # s bez zdarzeń kończy epizod
ZWIECHA_ODSTEP_S = 15.0            # zdarzenia bliżej niż tyle s to jedno (klik bez efektu + S2 w tym samym cyklu)
ZWIECHA_IGNOR_S = 30.0             # szczebel 2: s ignorowania stworów w pobliżu (inny punkt patrolu / trasy)
ZWIECHA_RESTART = 1                # szczebel 3: 1 = restart procesu bota (os.execv, jak ŚLEPOTA), 0 = tylko powtórka szczebla 2
ZWIECHA_RESTART_HP = 50.0          # % HP: poniżej restart jest odłożony (nie restartujemy w środku groźnej walki)
D3_ASTAR_MAX = 6                   # najwyżej tyle wywołań A* na jedną zawieszkę przy liczeniu opcji D3 (koszt ograniczony)
PATROL_RESPAWN_CIEN = 1            # 15.10: tryb cienia (SPEC_patrol_respawn_1015 krok 2): mapa obecności mobów liczona na żywo (obecnosc.py), a przy wyborze
                                   # celu patrolu w telemetrii patrol_cel (cel_respawn, wartosci, zgodny) i "decyzja" D4 wybór nowej metody; bot idzie jak dziś; pokrętło 0/1
PATROL_RESPAWN = 0                 # 20.10: pokrętło 0/1 (SPEC_patrol_respawn_1015 krok 3; domyślnie 0 = ruch jak dotąd, bit w bit): 1 = patrol IDZIE do celu wybranego metodą respawnu
                                   # (mapa obecności: gdzie trolle powinny już być; cel_respawn), gdy metoda ma zdanie i dane wystarczają; inaczej losowanie wg wag jak dziś.
                                   # Liczy mapę obecności także przy PATROL_RESPAWN_CIEN=0. Blokady miejsc (gracz, PATROL_GRACZ_*, PATROL_KOORD, gniazdo) zostają; cofnięcie = 0
OBECNOSC_ZAPIS_S = 60.0            # s: najwyżej tak często zapis stanu mapy obecności (poza tym na końcu pracy)
OBECNOSC_STAN_PLIK = None if os.environ.get("RETRONIC_TESTY") else instancja.S.stan / "obecnosc_stan.json"   # stan mapy obecności (przeżywa restart); None = bez pliku
ODWROCENIE_TRASY = 0.35            # szansa na przejście kolejnego okrążenia w drugą stronę
# Przerwy: nieregularne, losowane z mieszanki przedziałów (szansa, od s, do s); ostatni przedział bierze resztę.
# Odstęp: okazjonalnie bardzo krótki, najczęściej 20-45 min, czasem do 100 min. Długość: krótkie częściej, czasem długa.
PRZERWA_CO_MIX = ((0.08, 8 * 60, 20 * 60), (0.41, 20 * 60, 45 * 60), (0.51, 45 * 60, 100 * 60))
PRZERWA_DLUGOSC_MIX = ((0.55, 10, 40), (0.45, 40, 120))     # 13.10: max 120 s (było do 240 s)
PRZERWA_CO = (PRZERWA_CO_MIX[0][1], PRZERWA_CO_MIX[-1][2])            # s gry między przerwami (granice)
PRZERWA_DLUGOSC = (PRZERWA_DLUGOSC_MIX[0][1], PRZERWA_DLUGOSC_MIX[-1][2])  # s przerwy (granice)


def losuj_z_mieszanki(mix):
    """Wybiera przedział wg szans (ostatni = reszta), potem losuje jednostajnie wewnątrz niego.
    Jedno wywołanie random (tyle co dawne uniform), żeby nie przesuwać strumienia losowego reszty bota."""
    r = random.uniform(0.0, 1.0)
    for szansa, od, do in mix[:-1]:
        if r < szansa:
            return od + (do - od) * (r / szansa)
        r -= szansa
    szansa = 1.0 - sum(m[0] for m in mix[:-1])
    return mix[-1][1] + (mix[-1][2] - mix[-1][1]) * min(r / szansa, 1.0)


ROZRZUT_PROGU = 5                  # +% losowany ponad próg ucieczki na każdą walkę (tylko w górę: próg to dolna granica)
UCIECZKA_PREDYKCJA_OKNO = 4.0      # s: z tylu ostatnich sekund bierzemy największy spadek HP między odczytami
UCIECZKA_PREDYKCJA_MAX = 15        # pp: tyle maks. liczymy na kolejne uderzenie (wejście w ucieczkę, gdy HP - tyle <= próg)
UCIECZKA_ODPOCZYNEK_S = 45         # s w ucieczce, po których (bez regeneracji) wracamy do gry ostrożnie
UCIECZKA_MARGINES_WZNOWIENIA = 15  # pp nad progiem: od tego HP wracamy po UCIECZKA_ODPOCZYNEK_S, nawet bez regeneracji
# --- obrona przed graczami (obrona_pk.py, SPEC_obrona_pk_1015 wym. 1): atak PK rozpoznany z danych, ucieczka do depo bez modelu ---
PK_OBRONA = 1                      # 0/1: spadek HP + obcy gracz obok + brak potwora przy nas = ucieczka do depo, nick na listę wrogów
PK_ODL = 1                         # pola (chebyshev): obcy gracz tak blisko przy spadku HP = atak PK (1 = obok)
PK_ODL_CZAR = 0                    # pola: >0 = atak także od gracza w tym zasięgu czaru (0 = wyłączone)
PK_SPADEK_PP = 8.0                 # pp: min. spadek HP w oknie UCIECZKA_PREDYKCJA_OKNO uznawany za atak (100 -> 82 = 18 pp)
PK_KARENCJA_MIN = 30               # min: tyle po ostatnim zobaczeniu wroga nie wracamy na spot (wróg w widoku = bez powrotu)
PK_DEPO_PROMIEN = 8              # pola: start w karencji tak blisko depo = czekamy na miejscu, dalej = ucieczka do depo
PK_WROG_WAZNY_H = 72               # h: wróg z listy wywołuje ucieczkę na sam widok, jeśli ostatnio widziany nie dalej niż tyle godzin temu
PK_LECZ = 1                        # 0/1: w ucieczce PK leczymy po drodze (exura z hotkeya F2, UH z plecaka na siebie)
PK_SZYBKIE = 0                     # 16.10 (P6/R2): 1 = reakcja na PK nie czeka na dźwięk alarmu ani na model: alarm PK w wątku, leczenie w tym samym obiegu co start ucieczki; mózg nie pyta modelu o obcego gracza w PK-alarmie / przy HP < 50% i odrzuca wtedy pauza_bota/kontynuuj; 0 = jak dotąd
CZASZKA_POTWIERDZ = 0              # 23.10 pokrętło 0/1: 1 = groźna czaszka (biała/czerwona) z jednego odczytu Haiku NIE uruchamia ucieczki PK; potrzebny drugi odczyt na świeżym zrzucie, wycinek wokół tej postaci (czaszka.py). Niezgodność / postać znikła = bez ucieczki + log „Czaszka niepotwierdzona” + wycinki w dane_tibia/czaszki_niepotwierdzone/. Atak gracza (spadek HP) ucieka jak dotąd, bez czekania. Ryzyko: wolniejsza reakcja na prawdziwą czaszkę o jeden odczyt Haiku (~5-6 s); włącza tylko Karol (domyślnie 0)
PK_UH_HP = 40                      # % HP: poniżej tego w ucieczce klikamy UH z plecaka na siebie (0 = wyłączone)
PK_UH_ODSTEP_S = 2.5               # s: minimalny odstęp między próbami UH na siebie
PK_UH_SZYBKIE = 0                  # 16.10 (SPEC R3+R4, P8): 1 = szybkie UH na siebie w ucieczce PK (próg PK_UH_HP_SZYBKI + predykcja, bez przerwy 60 s przy HP<progu, weryfikacja ~0,6 s, bez zgadywania menu, losowy klik w polu postaci) i ucieczka bez 8 s walki z mobem; 0 = jak dotąd
PK_UH_HP_SZYBKI = 30               # % HP: próg UH przy PK_UH_SZYBKIE=1 (nigdy niżej niż 30)
PK_UH_PREDYKCJA = 1                # 0/1: przy PK_UH_SZYBKIE=1 spadek >= PK_UH_PRED_SPADEK pp w PK_UH_PRED_OKNO_S s => UH już przy HP <= PK_UH_PRED_HP
PK_UH_CTRL = 0                     # 0/1: przy PK_UH_SZYBKIE=1 Ctrl+klik runy (Use with bez menu/OCR); UNKNOWN czy działa w kliencie, więc domyślnie 0
PK_UH_PRED_SPADEK = 15.0           # pp: spadek HP w oknie wywołujący predykcję
PK_UH_PRED_OKNO_S = 2.0            # s: okno predykcji
PK_UH_PRED_HP = 50                 # % HP: predykcyjne UH tylko poniżej tego
PK_UH_WERYF_S = 0.6                # s: skrócona weryfikacja UH (spadek ilości run albo wzrost HP)
PK_UH_BUDZET_S = 1.0               # s: budżet sekwencji UH w trybie szybkim
PK_UH_ODSTEP_LOS = 0.2             # +-: losowość odstępu między ponowieniami UH (ułamek PK_UH_ODSTEP_S)
PK_UH_CTRL_PORAZKI = 2             # tyle nieudanych Ctrl+klików z rzędu = wracamy do menu (Ctrl+klik nie działa)
PK_UCIECZKA_BLOK_S = 1.0           # s: w ucieczce PK (PK_UH_SZYBKIE=1) tyle bez postępu ze stworem obok = droga zamknięta
PK_UCIECZKA_WALKA_S = 2.0          # s: maks. walka z blokującym w ucieczce PK (PK_UH_SZYBKIE=1)
PK_UH_ID = 3160                    # id runy Ultimate Healing (jak mozg.TRADE_ID_UH)
PK_SKAN_WIEK = 0.25                # s: cache skanu stworów w detekcji PK (bez drugiego pełnego skanu w obiegu)
SKAN_WIEK_WALKA = 0.5              # pokrętło 0.1-0.5 s (21.10, SPEC_skan_walka_spokoj_1021): wiek listy stworów w walce/pogoni/ucieczce/leczeniu; 0.5 + SKAN_WIEK_SPOKOJ 0.5 = jak dotąd (bez pola "rytm")
SKAN_WIEK_SPOKOJ = 0.5             # pokrętło 0.5-1.5 s: wiek listy stworów poza walką (rzadszy skan = mniej CPU)
SKAN_STANY_WALKI = ("WALKA", "POGON", "WALKA_PVP", "UCIECZKA", "ZDROWIE", "LOOT")   # LOOT: żywy mob obok przerywa zbieranie
_PK_TEST_N = 0                     # licznik plików wrogów w testach (RETRONIC_TESTY)
PK_FALLBACK_PONOW_S = 10.0         # s: w ucieczce awaryjnej (brak planu do depo) co tyle ponawiamy start trasy do depo
PK_DEPO_MAX_MIN = 20               # min: tyle w depo czekamy na regenerację HP (bez jedzenia HP nie rośnie), potem STOP + powiadomienie
PK_POWROT_PROBY = 3                # nieudane starty powrotu z depo na spot, po których STOP (potrzebny człowiek)
# --- walka z napastnikiem (SPEC_walka_pvp_1015, decyzje Karola 15.10): bijemy TYLKO gracza, który nas uderzył (detekcja PK) ---
PVP_WALKA = 0                      # 0/1: 1 = zamiast ucieczki do depo walczymy z jedynym napastnikiem (HMM + UH/exura); DOMYŚLNIE 0 do próby na żywo
PVP_MAX_WROGOW = 1                 # tylu napastników w widoku naraz dopuszcza wejście w walkę (więcej = ucieczka jak dotąd)
PVP_DRUGI_ODL = 5                  # pola: inny obcy gracz (nie GM) tak blisko, znany wróg albo gracz z groźną czaszką liczy się jako DRUGI napastnik
PVP_HP_MIN = 40                    # % HP: wejście w walkę tylko przy HP >= tyle (w trakcie walki nie uciekamy przy 40%)
PVP_UH_HP = 20                     # % HP: <= tyle w walce -> UH na siebie (brak UH = ucieczka)
PVP_HMM_STOP_PP = 0              # pp nad PVP_UH_HP, poniżej których nie strzelamy HMM (strzał blokuje ~2 s); 0 = strzelamy do końca (decyzja Karola)
PVP_EXURA_HP = 80                  # % HP: <= tyle w walce i jest mana -> exura (hotkey F2)
PVP_HMM_CO_S = 2.0                 # s: odstęp między strzałami HMM w napastnika (cooldown runy)
PVP_ZASIEG = 7                     # pola (chebyshev): dalej od napastnika nie strzelamy, tylko podchodzimy
PVP_POGON = 3                      # pola: nie oddalamy się od miejsca startu walki dalej niż tyle (podejście)
PVP_ZNIKL_S = 5.0                  # s: napastnik poza widokiem/zasięgiem tak długo = koniec walki (wynik uciekl_on), dalej zwykły przebieg PK
PVP_ZABITY_HP = 15                 # % HP napastnika: zniknięcie w widoku przy HP <= tyle (albo HP 0) = zabity
PVP_HMM_PORAZKI = 3                # tyle nieudanych strzałów HMM z rzędu (poza brakiem runy) = ucieczka
PVP_SKOK_POL = 30                  # pola: przeskok pozycji większy niż tyle między obiegami w walce = teleport do świątyni (śmierć)
LOOT_HP_MARGINES = 10              # pp nad progiem ucieczki: poniżej przerywamy loot (bijemy się dalej / uciekamy)
LOOT_HP_ZAGROZENIE = 3             # pp nad progiem ucieczki: HP tak blisko przerywa loot także bez mobów w pobliżu
LOOT_HP_MOBY_ODL = 6               # pola: żywy potwór tak blisko + HP w LOOT_HP_MARGINES = realne zagrożenie walką
LOOT_PRZERWANY_CHLOD_S = 8         # s: zwłoki po przerwaniu lootu z powodu HP nie wracają od razu do kolejki
LOOT_PRZERWANY_LOG_S = 5           # s: tak rzadko logujemy "Przerywam loot: niskie HP"
WATCHDOG_BEZCZYNNOSC_S = 20        # s bez zmiany pozycji (bez mobów, HP ok, nie pauza), po których watchdog rusza trasą
WATCHDOG_MOBY_ODL = 8              # pola: żywy potwór tak blisko = to nie bezczynność (walka/czekanie)
WATCHDOG_HP_MARGINES = 3           # pp nad progiem ucieczki: poniżej watchdog nie działa
WATCHDOG_LOOT_CHLOD_S = 30         # s: po odpaleniu watchdoga nie zbieramy odłożonych zwłok
WATCHDOG_CO_S = 60                 # s: watchdog odpala najwyżej raz na tyle
KROKI_DO_ZWLOK = 30                # ile obiegów maks. podchodzenia do zwłok przed lootem
LIMIT_BLEDOW = 5                   # tyle błędów odczytu/akcji z rzędu kończy bota
DZWIEKI = ["/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
           "/usr/share/sounds/freedesktop/stereo/dialog-warning.oga"]


class _ListaHakow(list):
    """Lista haków logu: ten sam hak (==) tylko raz (13.10, P4: drugi Cavebot w procesie nie dubluje zdarzeń)."""
    def append(self, h):
        if h not in self:
            super().append(h)


HAKI_LOGU = _ListaHakow()    # funkcje(txt) wołane z każdą linią logu (telemetria); mozg.py woła je ze swojego log_bota


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)
    for h in HAKI_LOGU:
        h(" ".join(map(str, a)))


# nick wyglądający na GM/CM/God/Tutor (ta sama reguła co GM_NAZWA w mozg.py)
GM_NAZWA = re.compile(r"^(gm|cm|god|tutor)\s|\[gm\]|\[cm\]", re.IGNORECASE)
GRACZ_INFO_PONOW = 120             # s: ten sam zwykły gracz w widoku jest w logu najwyżej raz na tyle
# unikanie zwykłych graczy (unikanie.py): zmiana punktu rotacji i pominięcie celów przy graczu, bez zatrzymywania bota
UNIKANIE = 1                       # 1 = bot omija zwykłych graczy; analityk nie może wyłączyć (tylko w górę)
CUDZY_MOB = 0                      # pokrętło 0/1 (na_zywo: 1): nie bierzemy na cel poranionego moba, którego sami nie zaczęliśmy, gdy niedawno był obcy gracz
CUDZY_MOB_S = 60.0                 # s: tak długo po zobaczeniu obcego gracza (w UNIKANIE_PROMIEN_MAX) obowiązuje CUDZY_MOB
UNIKANIE_TYLKO_SPOT = 1            # 1 = unikanie graczy tylko na spocie (piętra 8+), nie w mieście ani na powierzchni (z7)
UNIKANIE_PROMIEN = 9               # pola: gracz tak blisko (przez UNIKANIE_DEBOUNCE s) włącza unikanie
UNIKANIE_PROMIEN_MAX = 14          # pola: unikanie trwa, dopóki ktoś jest w tym promieniu (dalej gracz się nie liczy)
UNIKANIE_DEBOUNCE = 1.5            # s: gracz musi być w UNIKANIE_PROMIEN tak długo
UNIKANIE_ZNIKL_S = 10.0            # s bez gracza w UNIKANIE_PROMIEN_MAX = koniec unikania (normalny plan)
UNIKANIE_MOB_PROMIEN = 4           # pola: moby tak blisko gracza nie są celami (nie kradniemy, bez konfliktu)
UNIKANIE_PUNKT_D = 6               # pola: punkt trasy bliżej gracza jest pomijany
UNIKANIE_DROGA_MIN = 4             # pola: droga do punktu nie schodzi bliżej gracza (ani bliżej niż stoimy)
UNIKANIE_BLOK_S = 45.0             # s blokady bez zmiany: inny punkt rotacji z całej trasy, potem luz
UNIKANIE_SPOT_S = 180.0            # s: gracz na spocie dłużej = powiadomienie
UNIKANIE_POWIADOM_S = 300.0        # s: powiadomienie o graczu na spocie najwyżej raz na tyle
UNIKANIE_TOR = 0                   # 1 = nie idziemy za graczem: droga w kierunku jego ruchu i w jego stronę jest odrzucana (17.10, SPEC_unikanie_tor_gracza_1017)
UNIKANIE_TOR_OKNO_S = 4.0          # s historii pozycji gracza, z której liczymy kierunek jego ruchu
UNIKANIE_TOR_RUCH_MIN = 2          # pola: przesunięcie gracza w oknie poniżej tego = stoi (bez toru)
UNIKANIE_TOR_ZASIEG = 12           # pola: gracz (albo jego "duch") dalej niż tyle nie wyznacza toru
UNIKANIE_TOR_LOOK = 8              # pola drogi, z których liczymy jej kierunek
UNIKANIE_TOR_PAMIEC_S = 25.0       # s: gracz, który zniknął z widoku, nadal wyznacza tor (ostatnia pozycja i kierunek); unikanie w tym czasie trwa
UNIKANIE_PRZERWA = 0               # 1 = gracz w UNIKANIE_PROMIEN kończy PRZERWĘ od razu (dawniej stała do końca)
STWORY_WIDMA = 1                   # 19.10: 1 = wpisy-widma na liście stworów (obcy gracz na polu bota, kilku graczy na jednym polu) dostają `widmo` (widma.py) i NIE liczą się do zajętości pól ani do oceny graczy (unikanie/mijanie); PK, czaszki, GM i stan modelu widzą wszystko; 0 = stare zachowanie
SLEPOTA_DIAG_S = 120               # 19.10: s bez expa i bez potworów (stan IDZ/WALKA/LOOT/POGON, bot już polował) = zrzut diagnostyki do logi/slepota/ (slepota.py); 0 = wyłączone
SLEPOTA_RESTART_S = 0              # 19.10: s takiej ślepoty = restart procesu mozg.py (os.execv, ten sam pid; najwyżej raz na 15 min); 0 = bez restartu
# mijanie graczy (18.10, dane_tibia/SPEC_mijanie_graczy_1018.md; unikanie.Unikanie.mijanie): ocena kierunku gracza względem pętli
MIJANIE = 0                        # 1 = zamiast bańki dystansu i dreptania (unikanie.decyduj): nie idziemy tą samą stroną co gracz, mijamy się bez zawracania, obozowicza omijamy, przejście udostępniamy tylko w wąskim miejscu; 0 = dotychczasowe UNIKANIE_*
MIJANIE_PRZOD = 16                 # punkty trasy przed nami, na których gracz "jest na naszej drodze"
MIJANIE_TRASA_R = 2                # pola: idący gracz tak blisko punktu trasy leży na naszej drodze
MIJANIE_OBOZ_S = 3.0               # s obserwacji bez ruchu, zanim gracz jest "obozowiczem" (stoi); obserwacja liczona w oknie UNIKANIE_TOR_OKNO_S (4 s), więc zakres pokrętła do 3,5 s
MIJANIE_OBOZ_R = 3                 # pola: komora obozowicza (punkty trasy tak blisko niego omijamy)
MIJANIE_OBOZ_BLISKO = 3            # pola: gracz bez kierunku tak blisko nas (walczy obok) to nie obozowicz: bez odwracania obiegu; 0 = wyłączone (19.10)
MIJANIE_OBOZ_PAMIEC_S = 60.0       # s: decyzję wobec obozowicza podejmujemy ponownie po tylu s (stoi dalej, pętla znów do niego dochodzi)
MIJANIE_OBOZ_ODWROTY = 2           # tyle odwróceń obiegu przez tego samego obozowicza w 120 s, potem przechodzimy obok niego
MIJANIE_SKROT_MAX = 40             # pola: najdłuższy skrót omijający komorę obozowicza
MIJANIE_ZNIKL_S = 6.0              # s: gracz poza widokiem tak długo = kolejne spotkanie (decyzja wobec niego wygasa)
MIJANIE_PRZEJSCIE_ODL = 6          # pola: dalej idącego na nas gracza nie ustępujemy
MIJANIE_BOK_R = 6                  # kroki: tak daleko szukamy wnęki, w której stajemy
MIJANIE_POSTOJ_S = 15.0            # s: bezpiecznik postoju przy udostępnianiu przejścia
MIJANIE_PONOW_S = 20.0             # s: po udostępnieniu przejścia temu samemu graczowi nie ustępujemy ponownie
# 15.10 czat_spot.py (SPEC_czat_spot_1015): jedna wiadomość na Default do gracza, który wraca na spot albo zabiera moby
CZAT_SPOT_AKTYWNY = 0              # pokrętło 0/1 (domyślnie wyłączone)
CZAT_SPOT_SPOTKAN = 3              # S1: tyle osobnych spotkań (każde >= 20 s) z tym samym graczem...
CZAT_SPOT_OKNO_MIN = 20            # ...w tylu minutach
CZAT_SPOT_CIAGLE_MIN = 5           # S2: gracz przy nas bez przerwy tyle minut
CZAT_SPOT_ZABRANE = 2              # S3: tyle różnych mobów zabranych nam przez gracza w 10 min
CZAT_SPOT_NICK_MIN = 60            # jeden gracz dostaje wiadomość najwyżej raz na tyle minut
CZAT_SPOT_ODPOWIEDZI = 1           # ile razy odpisujemy (model) na jego odpowiedź; potem cisza


UH_STAN_PLIK = instancja.S.uh_stan   # trwały stan UH (tarcza_id): przeżywa restart bota


class _UhStan(dict):
    """dict zapisywany do pliku po każdej zmianie (uh.py trzyma w nim tarcza_id zdjętej tarczy)."""

    def __init__(self, plik):
        super().__init__()
        self._plik = Path(plik)
        try:
            d = json.loads(self._plik.read_text())
            if isinstance(d, dict):
                super().update(d)
        except (OSError, ValueError):
            pass

    def _zapisz(self):
        try:
            if self:
                self._plik.write_text(json.dumps(dict(self)))
            elif self._plik.exists():
                self._plik.unlink()
        except OSError:
            pass

    def __setitem__(self, k, v):
        super().__setitem__(k, v)
        self._zapisz()

    def __delitem__(self, k):
        super().__delitem__(k)
        self._zapisz()

    def pop(self, *a):
        r = super().pop(*a)
        self._zapisz()
        return r

    def clear(self):
        super().clear()
        self._zapisz()


def alarm_dzwiekowy(powod):
    """Dźwięk przez paplay/canberra, a gdy ich brak, sam wydruk. Te same wyłączniki co powiadom.py."""
    log(f"ALARM: {powod}")
    if os.environ.get("RETRONIC_POWIADOMIENIA", "").strip() == "0" or (Path(__file__).resolve().parent / "cisza").exists():
        return
    if (Path(__file__).resolve().parent / "dzwiek_wylaczony").exists():  # 22.10 (Karol): bez pikania; notify-send zostaje
        return
    try:
        import glos  # noqa: PLC0415  21.10 (Karol): głos "<nick> pomocy, <powód>" zamiast dźwięku systemowego
        if glos.mow(powod):
            return
        for plik in DZWIEKI:
            if os.path.exists(plik):
                subprocess.run(["paplay", plik], timeout=4, capture_output=True)
                return
        subprocess.run(["canberra-gtk-play", "-i", "dialog-warning"], timeout=4, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        print("\a", end="", flush=True)


def kierunki_do(x, y, cx, cy):
    """Kierunki prowadzące z (x,y) do (cx,cy), od najlepszego; potem prostopadłe (obejście)."""
    dx, dy = cx - x, cy - y
    ruchy = []
    if dx:
        ruchy.append("Right" if dx > 0 else "Left")
    if dy:
        ruchy.append("Down" if dy > 0 else "Up")
    if abs(dy) > abs(dx):
        ruchy.reverse()
    for k in list(ruchy):
        ruchy += [p for p in (("Up", "Down") if k in ("Left", "Right") else ("Left", "Right"))
                  if p not in ruchy]
    return ruchy


class Cavebot:
    dojscie_aktywne = False            # True tylko w CavebotDojscie (bieg zamiast walki, bez lootu i przerw)
    dojscie_wroc = False               # 24.10: True, gdy ręczne WROC (plik WROC) przerwało dojście wyprawą do depo; po niej dojście się kończy
    stoj_wl = False                    # 23.10 przełącznik STÓJ (stoj.py, plik instancje/<id>/STOJ): True = nie chodzimy, robimy runy
    stoj_pole = None                   # pole (x, y, z) zapamiętane przy włączeniu STÓJ: po przesunięciu wracamy na nie
    stoj_katalog = None                # None = katalog stanu instancji (instancja.S.stan); testy podstawiają własny
    marsz = None                       # MARSZ_KLIK: trwający marsz klikiem (stan w __init__; None także w atrapach testowych)
    marsz_blok = None

    def __init__(self, postac, punkty, okrazenia=None, czas_s=None, prog_hp=40, jedzenie=None,
                 potwory=None, zatrzymaj_przy_graczu=True, zapytaj=None, atak=None,
                 alarm=alarm_dzwiekowy, spij=time.sleep, zegar=time.monotonic, loot=None,
                 czy_atakowany=None, czekaj=False, klik=None, mapa=None, stop_przy_graczach=False):
        self.postac = postac
        # start: puść klawisze ruchu, które mógł zostawić zabity poprzedni proces (trzymany klawisz = postać by szła)
        czysc = getattr(postac, "puszcz_wszystko", None)
        if czysc is not None:
            try:
                czysc()
            except Exception as e:
                log(f"debug: czyszczenie klawiszy przy starcie: {e!r}")
        self.punkty = [tuple(p) for p in punkty]
        # trasa otwarta (koniec daleko od startu): chodzimy tam i z powrotem
        self.otwarta = len(self.punkty) > 1 and (
            self.punkty[0][2] != self.punkty[-1][2]
            or abs(self.punkty[0][0] - self.punkty[-1][0]) + abs(self.punkty[0][1] - self.punkty[-1][1]) > 3)
        self.okrazenia = okrazenia if (okrazenia or czas_s) else 1
        self.czas_s = czas_s
        self.prog_hp = prog_hp
        self.wznowienie_hp = min(100, prog_hp + 30)   # histereza po ucieczce
        self.jedzenie = jedzenie
        self.potwory = {p.casefold() for p in potwory} if potwory else None
        # zatrzymaj_przy_graczu: pilnujemy graczy w ogóle (False = --ignoruj-graczy, nic nie zatrzymuje);
        # stop_przy_graczach: True = stare zachowanie, każdy obcy gracz zatrzymuje i alarmuje;
        # domyślnie zatrzymuje tylko gracz groźny (GM_NAZWA albo czaszka/PK), zwykły tylko się loguje
        self.zatrzymaj_przy_graczu = zatrzymaj_przy_graczu
        self.stop_przy_graczach = stop_przy_graczach
        self.gracze_zalogowani = {}    # nick -> czas ostatniego wpisu "gracz w pobliżu" w logu
        self.zapytaj = zapytaj or (lambda z: bot.zapytaj(z))
        self.atak = atak or self._atak_domyslny
        # Ponowny Alt+klik na atakowanym celu WYŁĄCZA atak, więc przed ponowieniem
        # sprawdzamy, czy atak trwa: flaga czerwonej ramki z pamięci klienta (działa
        # po ciemku), a gdy jej brak - czerwona ramka na zrzucie. Z atrapą ataku (testy) bez tego.
        self.czy_atakowany = czy_atakowany or (
            (lambda stwor, gracz: False) if atak else self._atakowany_domyslny)
        self.alarm = alarm
        self.spij = spij
        self.zegar = zegar
        self.loot = loot if loot is not None else self._wczytaj_loot()
        self.stan = None
        self.idx = 0
        self.okrazenie = 0
        self.przebyte = 0              # punkty zaliczone w bieżącym okrążeniu
        self.start = zegar()
        self.cel = None                # {"id","nazwa","poz","hp"} ostatnio widziany
        self.cel_start = 0
        self.czekaj = czekaj            # False: od razu podchodzimy do celu (domyślnie)
        # chodzenie kliknięciem w mapę (klient sam prowadzi postać pełną prędkością);
        # z atrapą ataku (testy) bez klikania - wtedy chodzimy strzałkami
        self.klik = klik if klik is not None else (None if atak else self._klik_domyslny)
        self.klik_cel = None           # (x, y) pola, w które ostatnio kliknęliśmy
        self.klik_czas = float("-inf")
        self.klik_poz = None           # pozycja gracza przy ostatnim ruchu po kliku
        self.klik_ruch = float("-inf") # kiedy po kliku ostatnio zmieniła się pozycja
        self.klik_j = None             # indeks punktu trasy, w który ostatnio kliknęliśmy
        self.marsz = None              # MARSZ_KLIK: trwający marsz klikiem {"cel","poz0","z","n","t0","limit","ost","ruch","hook"}
        self.marsz_blok = None         # (pole, do): brak ruchu po marszu, w pobliżu pola krok klawiszem do czasu `do`
        self.czekanie_do = None       # do kiedy stoimy i czekamy na podejście celu
        self.reakcja_do = 0            # do kiedy "zauważamy" nowy cel, zanim go zaatakujemy
        self.pogon_odl = 0             # najmniejszy dystans do celu w tej pogoni
        self.tele = self.pokretla = None   # telemetria.py + pokretla.py (tylko na żywo, patrz _hak_telemetrii)
        self.martwy = False            # 16.10 (SMIERC_STOP): po potwierdzonym zgonie True; tick nic nie robi, model nie wykonuje akcji
        self._smierc_zero = 0          # kolejne odczyty HP == 0
        self._smierc_zywy = None       # (poz, czas) ostatniej próbki z HP > 0
        self.rozlaczony = False        # 21.10 (ROZLACZENIE_STOP): True od potwierdzenia ekranu logowania do powrotu do gry; tick nic nie wysyła, model i czat milczą
        self._rozl_det = None          # rozlaczenie.Detektor (tworzony przy pierwszym obiegu z ROZLACZENIE_STOP=1)
        self._rozl_zrzut = None        # funkcja zrzutu -> True (ekran logowania) / False / None; None = rozlaczenie.zrzut_logowania (testy wstrzykują atrapę)
        self._rozl_start = None        # (czas zegara, czas ścienny, poz, stan sprzed rozłączenia) chwili ogłoszenia rozłączenia
        self.wylogowany = False        # 23.10 (ROZLACZENIE_WYJSCIE): True po decyzji o końcu procesu z powodu wylogowania; tick zwraca wtedy False
        self.wylog_stan = None         # katalog stanu, w którym ląduje wylogowany.json (None = instancja.S.stan; w testach bez tego nic nie piszemy)
        self.wylog_tryb_log = None     # tryb.log, z którego bierzemy mapę i tryb do znacznika (None = instancja.S.tryb_log)
        self._brak_postaci = None      # wylogowanie.BrakPostaci: błędy odczytu gracza/pozycji + zrzut = ekran logowania
        self._d3 = None                # d3_zawieszka.Zawieszka (16.10): detektor zawieszki, tworzony przy pierwszym obiegu
        self._decyzja_nr = 0           # 15.10: licznik rekordów "decyzja" w tej sesji (id łączące z nowy_cel/epizod_celu/poscig_*)
        self._d1_id_cel = None         # id decyzji D1, z której wybrano bieżący cel (do powiązania z D2)
        self.mana_ostatnia = None      # poprzedni odczyt many (śledzenie "mana nie rośnie")
        self.mana_wzrost = zegar()     # kiedy mana ostatnio rosła, była pełna albo po jedzeniu/rzucie czaru
        self.jedzenie_nie_do = float("-inf")   # do kiedy nie ponawiamy jedzenia (brak jedzenia w plecaku)
        self.jedzenie_nieczytelne_do = float("-inf")   # do kiedy ostatnie "brak jedzenia" uznajemy za niewiarygodne (kontenery niewidoczne)
        self.brak_jedzenia_log = float("-inf") # kiedy ostatnio zalogowano "brak jedzenia" (raz na JEDZENIE_LOG_S)
        self.ostatni_alarm_hp = float("-inf")
        self.hp_gracza_spadek = float("-inf")  # kiedy HP gracza ostatnio spadło o >= GRYZIE_SPADEK_PP w GRYZIE_OKNO
        self.hp_hist = []              # (czas, HP% max) z ostatnich GRYZIE_OKNO s
        self.obok_od = {}              # id świeżego potwora -> od kiedy stoi obok (odl 1) bez przerwy
        self.rozprawa_spokoj_do = float("-inf")   # po powrocie do rannego blokuje/tlum nie zmieniają celu od razu znów
        self.rozprawa = None           # {"id": świeży do rozprawy, "wroc": id porzuconego rannego, "do": czas}
        self.pokretla_ost = float("-inf")
        self.tick_wolny_ost = float("-inf")
        self.przeglad_loot_ost = float("-inf")
        self.droga_bez_blokad = 0      # ile razy droga istniała tylko po zdjęciu blokad (stwory/ściany)
        self.loot_blok_od = None
        self.stwory_pola = {}          # (x, y) -> kiedy ostatnio stał tam stwór (nauka ścian)
        self.nieosiagalne = {}         # id celu -> dystans prosty w chwili odpuszczenia (twarde ignorowanie)
        self.ostatnia_droga_dl = None  # długość drogi z ostatniego podejdz (inf = brak drogi, None = nie wiadomo)
        self.sciany = {}               # pole -> kiedy krok strzałką na nie się nie udał (ściana)
        self.sciany_do = {}            # KROK_ZLY: pole -> do kiedy (zegar) zakaz wejścia (wpis w `sciany` też jest)
        self.krok_zly = {}             # KROK_ZLY: pole -> [nieudane kroki z rzędu, kiedy ostatni, ile zakazów już było]
        self.krok_zly_blok = False     # KROK_ZLY: krok_do właśnie nałożył zakaz / pominął zakazane pole (sygnał dla patrolu)
        self.zw_grupa = {}             # LOOT_DYNAMICZNY: pole zwłok -> krotka kandydatów tego samego zabicia (po udanym lootcie znikają)
        self.zw_brak_okna = {}         # LOOT_DYNAMICZNY: pole zwłok -> liczba "brak_okna" (1 = wstrzymane do końca walki, 2 = porzucone)
        self.przeglad_odl = None       # LOOT_DYNAMICZNY: odległość żywego potwora przerywającego loot.zbierz (None = LOOT_PRZEGLAD_ODL)
        self.zwloki_czekajace = []     # [(pole zwłok, czas ZABICIA)] odłożone, bo walka miała pierwszeństwo
        self.zwloki_wiek = {}          # pole -> czas zabicia (przeżywa pop z listy i ponowne odłożenie po przerwaniu)
        self.zwloki_priorytet_do = float("-inf")   # do kiedy zwłoki mają pierwszeństwo przed szukaniem celu (po ucieczce)
        self.lww_zalegle = None        # {"stan","t","proby"}: okno zwłok zostawione przez pilne przerwanie, do zamknięcia
        self.zwloki_chlod = {}         # pole zwłok -> do kiedy nie wracamy do niego (przerwany loot przy niskim HP)
        self.loot_chlod_do = float("-inf")     # do kiedy w ogóle nie zbieramy odłożonych zwłok (watchdog)
        self.loot_hp_log_ost = float("-inf")   # kiedy ostatnio zalogowano "Przerywam loot: niskie HP"
        self.watchdog_ost = float("-inf")      # kiedy ostatnio odpalił watchdog bezczynności
        self.lww = None                # loot w walce: {"zw","stan","t0","t_ost","klik_t","kroki"} albo None
        self.lww_chlod_do = float("-inf")   # do kiedy nie zaczynamy lootu w walce (po przerwaniu)
        self.lww_pomin = {}            # pole zwłok -> do kiedy nie próbujemy go w walce
        self.lww_diag = None           # {"t","powod","atak"}: ostatnia ocena lootu w walce (telemetria)
        self.lww_kary = 0              # ile razy klik w zwłoki wyłączył atak
        self.lww_kara_do = float("-inf")    # do kiedy loot w walce wyłączony po wyłączeniu ataku
        self.krok_prosto_ost = None    # (skąd, dokąd, czas) ostatniej strzałki - do nauki ścian
        self.poprzednia_odl = None     # dystans do celu w poprzednim obiegu (wykrycie początku ucieczki)
        self.obok_hp = None            # najwyższe HP celu, odkąd stoi obok (nauka progu uciekania)
        self.hp_spadek_czas = 0        # kiedy HP celu ostatnio spadło
        self.atak_czas = float("-inf") # kiedy ostatnio kliknęliśmy atak
        self.atak_falsz = (None, 0)    # (id celu, ile kolejnych odczytów flagi "atakowany" = False)
        self.atak_blok = {}            # id celu -> do kiedy nie ponawiamy ataku (po nieudanej weryfikacji)
        self.atak_weryf = None         # (id celu, czas kliku): flagę sprawdzamy w następnym obrocie pętli pościgu
        self._poscig_rpc = True        # False: rdzeń bez komendy "poscig" (dwa zapytania zamiast jednego)
        self._ruch_przechwyt = None    # lista (kierunek, droga) w trybie trzymania; None = strzałki idą od razu
        self.drzwi_def = None          # R1c: lista drzwi z PLIK_DRZWI (wczytywana przy pierwszym użyciu)
        self.drzwi_stan = {}           # R1c: pole drzwi -> {"poz","t0","proby","zle_do","nota"}
        self.skos_zle = {}             # (z_pola, na_pole) -> do kiedy: skos, który nie przesunął postaci (nie ściana!)
        self.skos_ost = None           # (z_pola, na_pole) ostatniego skosu awaryjnego
        self.skos_awaryjny_n = 0       # ile razy droga poszła skosem awaryjnym (telemetria / test)
        self._skos_log_t = float("-inf")
        self.w_poscigu = False         # True w trakcie poscig_szybki (mózg nie skanuje wtedy pamięci)
        self.w_lootcie = False         # True w trakcie zbierania zwłok
        self.loot_styk = None          # 23.10: {"dop", "t0", "hp"} w trakcie lootu zaraz po zabiciu przy przylegającym mobie (LOOT_SZYBKI_STYKAJACE)
        self.loot_hp_proc = None       # ostatni świeży odczyt HP% z _hp_nisko (do wykrycia spadku HP w lootcie przy styku)
        self.poscig_seria = None       # [początek, najmniejsza odl, koniec ostatniej pętli] ciągłego pościgu
        self.poscig_przerwa_do = float("-inf")
        self.poscig_stuk_do = float("-inf")   # do kiedy pościg stuknięciami zamiast trzymania (po oscylacji)
        self.pamiec = None             # pościg na pamięć: {"cel","do","cel_xy","kroki","t0",...} (patrz _pamiec_start)
        self.pamiec_znaleziony = None  # (id, hp0) celu odnalezionego po zniknięciu: wybierany jako cel przy najbliższym wyborze
        self.exp_przed = self.exp_teraz = None   # exp gracza w poprzednim i bieżącym obiegu (wzrost = zabicie)
        self.progi_uciekania = dict(PROG_UCIEKANIA_DOMYSLNY)
        if self.klik is not None:      # na żywo: wczytaj progi nauczone w poprzednich sesjach
            try:
                self.progi_uciekania.update(json.loads(PLIK_UCIEKANIA.read_text()))
            except (OSError, ValueError):
                pass
        self.pogon_postep = 0          # kiedy ostatnio się do niego zbliżyliśmy
        self.pogon_odl_ost = 0         # dystans do celu przy poprzedniej ocenie pościgu
        self.pogon_tick_ost = 0        # kiedy ostatnio oceniano postęp pościgu (luki = jedzenie, loot)
        self.pogon_uciek = (None, 0)   # (id celu, od kiedy ucieka) - do twardego limitu pościgu
        self.ruch_poz = None           # ostatnia pozycja bota (do pomiaru "ruszył się")
        self.ruch_czas = 0             # kiedy bot ostatnio zmienił pole
        self.aktywnosc_ts = 0          # ostatnia aktywność bota (ruch, walka, zgon celu, loot, jedzenie, pochodnia); baza watchdoga
        self.prog_aktualny = prog_hp   # próg ucieczki z losowym rozrzutem, losowany na walkę
        self.przerwa_od = zegar() + losuj_z_mieszanki(PRZERWA_CO_MIX)
        self.przerwa_do = None
        self.czekanie_odl = 0
        self.cel_hp = None
        self.cel_spadek = 0            # czas ostatniego ataku lub spadku HP
        self.ignorowane = {}           # id -> do kiedy
        self.ignor_powod = {}          # id -> (powód, do): "sciana"|"limit_walki"|"atak_klik"|"straznik" (IGNOR_TWARDE)
        self.ignor_droga_cache = {}    # id -> (czas, droga otwarta?)
        self.odpuszczenie_log = {}     # id -> czas ostatniego logu "Odpuszczam ... za ścianą"
        self.ostatni_blokujacy = None  # (pole, id stwora) gdy droga bez stworów prowadzi przez zajęte pole (BLOK_WYJSCIE)
        self.straznik_cel = None       # stan strażnika celu {"id", "t", "hp", "odl", "exp", "s1"}
        self.straznik_s2_t = []        # czasy odpaleń progu 2 strażnika celu
        self.straznik_post = {"t": None, "poz": None, "exp": None, "cel_hp": None, "s": 0, "ostr": None}
        self.hp_ostatnie = None
        self.hp_wzrost = zegar()       # kiedy HP ostatnio rosło (też od leczenia) albo było pełne
        self.hp_regen = zegar()        # kiedy HP ostatnio urosło NIE od exura (regeneracja), było pełne albo jedliśmy
        self.zdrowie_rzut_ts = float("-inf")   # czas ostatniego rzutu exura (do odróżnienia leczenia od regeneracji)
        self.jedzenie_walka_ost = float("-inf")
        self._z_poprz = None           # piętro z poprzedniego obiegu (wykrycie zmiany piętra)
        self._swiezy_skan_do = float("-inf")
        self._trasa_stop_n = 0         # kolejne obiegi wstrzymania trasy przez potwora (TRASA_STOP_MAX)
        self.brak_klawisza_zalogowany = False
        self.zablokowane = {}          # (poz, kierunek) -> True, czyszczone po ruchu
        # pola ognia (ogien.py): (x, y, z) -> czas ostatniego wykrycia; wykrywanie tylko na żywo (nie w testach)
        self.ogien_pola = {}
        self.ogien_t = float("-inf")           # czas ostatniego wykrycia
        self.ogien_log_ost = (None, float("-inf"))   # (ostatni zalogowany zbiór, czas wpisu)
        self.ogien_krok_t = float("-inf")      # czas ostatniego kroku z pola ognia
        self.ogien_zle = {}                    # (z_xy, do_xy) -> do kiedy pomijamy (krok nie przesunął postaci)
        self.ogien_czeka_od = None             # od kiedy ogień zamyka nam drogę (czekamy)
        self.ogien_ignoruj_do = float("-inf")  # po wyczerpaniu czekania: do kiedy ignorujemy ogień
        self.ogien_blad_t = float("-inf")
        self.ogien_widz = {}                   # P6: pole -> [ile wykryć, pierwsze, ostatnie] (do maski stałych pól)
        self.ogien_stale = set()               # P6: pola stałe (widziane >= OGIEN_STALY_N razy przez >= OGIEN_STALY_S albo ściana mapy)
        self._ogien_stale_wczytaj()
        self.ogien_pierw = {}                  # pole ognia -> czas pierwszego wykrycia w bieżącej serii (potwierdzenie czasem)
        self.ogien_hp_hist = []                # (czas, HP% max) z ostatnich OGIEN_HP_OKNO_S s
        self.ogien_poz_ost = None              # 15.10: ostatnia pozycja w _ogien_tick i czas wejścia na nią
        self.ogien_poz_od = float("-inf")
        self.ogien_podpalony_do = float("-inf")   # 15.10: do kiedy postać się pali (spadki HP nie obciążają innych pól)
        self.ogien_ign_log = {}                # pole -> czas ostatniego logu "ignoruję"
        self.ogien_epizody = {}                # "x,y,z" -> {"n", "godz", "hp", "ost"} (trwałe, trasy/ogien_epizody.json)
        self.ogien_dane_maska = set()          # pola przechodnie zakwalifikowane z danych (epizody)
        self.ogien_ep_brudne = False
        self.ogien_ep_zapis_t = float("-inf")
        self.ogien_wall = time.time            # zegar ścienny (godzina doby, przerwa epizodu); testy podmieniają
        self._ogien_epizody_wczytaj()
        self.ogien_podsum_t = None             # P6: czas ostatniego podsumowania w logu
        self.ogien_odczyt = self._ogien_odczyt_domyslny \
            if ((klik is not None or not atak) and not os.environ.get("RETRONIC_TESTY")) else None
        self.nieudane = 0
        self.krok_z = None             # (pole, czas): z którego pola ostatnio zrobiliśmy udany krok_do
        self.utk_okno = None           # okno wykrywania utknięcia w IDZ: [start, idx, pola, dystans0, ost]
        self.utkniecia_trasy = 0       # ile razy wykryto utknięcie na trasie (telemetria)
        self.trasa_droga = None        # (cel, lista pól drogi, czas) - A* do punktu trasy poza prostą
        self.pominiete = 0
        self._patrol_init()
        self.ostatni_alarm = float("-inf")
        self.ucieczka = False
        self.ucieczka_od = None        # kiedy weszliśmy w ucieczkę
        self.ostrozny = False          # wróciliśmy do gry bez pełnej regeneracji: bez szybkiego pościgu do HP >= wznowienie
        self.hp_historia = []          # [(czas, % HP)] z ostatnich UCIECZKA_PREDYKCJA_OKNO s
        self.ostatnie_stwory = []      # lista stworów z ostatniego obiegu (zajęte pola dla drogi)
        # mapa znanych pól: każde pole, na którym kiedyś stał gracz (trasy + to, co widzimy teraz);
        # droga do potwora liczona tylko po nich omija ściany, których nie znamy wprost
        self.znane = self._wczytaj_znane() | {p for p in self.punkty if len(p) == 3}
        # pełna mapa serwera (mapa.py, minimapa OTClienta): główne źródło dróg. Na żywo wczytana
        # sama (brak pliku = None, wtedy jak dawniej tylko znane pola); w testach tylko wstrzyknięta
        self.mapa = mapa if mapa is not None else (
            self._wczytaj_mape() if (klik is not None or not atak) else None)
        self._ogien_stale_wczytaj()    # R1a: zasiew maski stałych pól (wymaga mapy)
        self.ostatni_objazd = ""       # opis ostatniego odrzuconego celu (do logu)
        self._klucze, self._klucze_n = {}, -1   # pamięć podręczna droga(): piętro -> klucze pól
        self.zwiecha = None            # 23.10: zwiecha.Detektor (tworzony przy pierwszym zdarzeniu); epizod: klik bez efektu bez zabicia
        self.zwiecha_restart = False   # 23.10: szczebel 3 prosi mozg.py o restart procesu (mozg._slepota_watchdog)
        self._zwiecha_hp = 100.0
        self._straznik = None          # 20.10: straznik_orbity (Detektor, Reakcja); tworzony przy pierwszym obiegu z STRAZNIK_ORBITY > 0
        self.wpadniecie = None         # wpadniecie.Wpadniecie (15.10): wykrycie upadku, nauczone dziury, wyjście (tworzone przy pierwszym użyciu)
        self.pietra = None             # pietra.Pietra: przejścia pięter z trasy wielopiętrowej (tworzone przy pierwszym użyciu)
        self.ruch_kliki = self.ruch_strzalki = 0   # R0b: liczniki do ruch_okno (klik w mapę / krok strzałką)
        self.ruch_pietra_t = float("-inf")         # R0b: kiedy ostatnio pietra.py zużyło obieg
        self.pietra_ops = None         # operacje na ekranie (Use/lina); None = z wypadu / wypad.OperacjeZywe; testy wstrzykują atrapę
        self.pietra_porazki = 0        # kolejne nieudane przejścia pięter
        self._pietra_cache = None      # (id listy punktów, długość, wynik): czy trasa ma > 1 piętro
        self.stanowisko = None         # 22.10 stanowisko.Stanowisko (tryb stoj), tworzony w _stanowisko_sync; None = zachowanie bez zmian
        self.stanowisko_proba = False
        self.g_tick = None             # 22.10 gracz z bieżącego obiegu (dla haka stanowiska w idz)
        self.wyprawa = None            # wypad.Wypad (tylko na żywo, patrz _hak_wypadu; testy wstrzykują własny)
        self.wypad_aktywny = False     # True w trakcie wypadu po pochodnie: przerwa i trasa łowiska nie działają
        self.wypad_czat = None         # mozg.Czat (ustawia mozg.py): NPC nie jest "obcym graczem"
        self.wypad_wyslij = None       # funkcja(tekst): wpisanie na Default (ustawia mozg.py)
        self.ml_plan = None            # kiedy rzucić czar (losowe opóźnienie od spełnienia warunków)
        self.ml_ostatni = float("-inf")  # czas ostatniego rzutu
        self.ml_extra_przerwa = random.uniform(*ML_CZAR_EXTRA_PRZERWA)   # losowy dodatek do exhaustu
        self.ml_zapas_many = random.randint(*ML_CZAR_ZAPAS_MANY)         # losowa nadwyżka many ponad koszt
        self.ml_oczekuje = None        # (czas rzutu, mana przed): weryfikacja spadku many
        self.ml_porazki = 0            # kolejne rzuty bez spadku many
        self.ml_wylaczony_do = float("-inf")
        self.pet = None                # pet_ster.PetSterowanie (leniwie, patrz _pet_ster)
        self.stwory_surowe = []        # ostatnia lista stworów z petem (stwory() zwraca bez niego)
        self.widma_log = {}            # (nick, powód) -> czas ostatniego wpisu "Widmo: ..." (widma.loguj)
        self.czar_ostatni = float("-inf")  # czas ostatniego rzutu DOWOLNEGO czaru bota (wspólny exhaust)
        self.zd_oczekuje = None        # exura: (czas rzutu, mana przed, hp przed)
        self.zd_porazki = 0
        self.zatruty = False
        self.zatrucie = None             # zatrucie.Zatrucie (23.10), tworzone przy pierwszym użyciu
        self.zd_wylaczony_do = float("-inf")
        self.zd_rzuty = 0
        self.runa_ostatni = float("-inf")  # czas ostatniego strzału runą
        self.runa_los = (None, 0.0)        # (runa_ostatni, wylosowany odstęp do następnego strzału)
        self.klik_ramka_false = {}     # id celu -> liczba kliknięć "ramka_false" bez spadku HP (ATAK_LIMIT_KLIKOW)
        self.mapa_ramka_false_seria = 0            # ramka_false z rzędu bez spadku HP jakiegokolwiek celu (MAPA_ZAPOMNIJ_KLIKI)
        self.mapa_zapomnij_ost = float("-inf")     # czas ostatniego ekran.zapomnij_prostokat (MAPA_ZAPOMNIJ_CO_S)
        self.atak_inny_ost = {}        # id celu -> czas ostatniego kliku "inny_cel" (ATAK_INNY_CEL)
        self.runa_strzaly = 0
        self.runa_klik_env = None      # runa_klik.SrodowiskoKlik (tworzone leniwie)
        self.runa_klik_porazki = 0
        self.runa_klik_do = float("-inf")   # chłodzenie po serii porażek
        self.runa_brak_do = float("-inf")   # do kiedy nie sprawdzamy plecaka po "brak runy"
        self.runa_brak_zalogowany = False
        self.jc_oczekuje = None        # exevo pan: (czas rzutu, mana przed)
        self.jc_ostatni = float("-inf")
        self.jc_porazki = 0
        self.jc_wylaczony_do = float("-inf")
        self.jc_glod_do = float("-inf")    # do kiedy blokujemy ML (mana ma zostać na exevo pan)
        self.jedzenie_plecak = None    # (czas, liczba jedzenia w plecaku wg wypad.py)
        self.jz_odczyt = None          # (czas, sztuk jedzenia w plecaku | None = nieczytelny): odczyt własny (loot.ile_jedzenia)
        self.jz_oczekuje = None        # F3 na zapas: (czas rzutu, mana przed, sztuk przed | None)
        self.jz_ostatni = float("-inf")
        self.jz_porazki = 0
        self.jz_wylaczony_do = float("-inf")
        self.jz_nieznany_ostatni = float("-inf")   # kiedy ostatnio rzucono F3 przy nieczytelnym plecaku
        self.jz_hold_od = None         # od kiedy ML czeka na manę 30 dla F3
        self.mana_rosla = zegar()      # kiedy mana ostatnio FAKTYCZNIE urosła (bez resetu po jedzeniu): dowód regeneracji
        self.jz_notatka_ost = float("-inf")
        self.ml_rzuty = 0
        self.ml_mana_wydana = 0
        self.uh_hp_start = None        # % HP w chwili startu runy w walce (do wykrycia szybkiego spadku)
        self.uh_tryb_walki = False     # True tylko w trakcie runy startowanej w walce (UH_W_WALCE): łagodzi _uh_przerwanie
        self.uh_env = None             # uh.SrodowiskoGry (tworzone leniwie; stan["tarcza_id"] trwały w UH_STAN_PLIK)
        self.uh_ostatni = float("-inf")  # czas ostatniej próby robienia runy
        self.uh_wylaczony_do = float("-inf")
        self.uh_porazki = 0
        self.uh_runy = 0
        self.uh_naprawa_ok = False     # True po starcie: kontrola "slot tarczy pusty, tarcza w plecaku" już wykonana
        self.uh_naprawa_od = float("-inf")
        self.uh_restore = None         # None = nie sprawdzono; True = po restarcie/alarmie tarcza może być zdjęta
        self.uh_czeka_ts = float("-inf")   # kiedy ostatnio UH czekał tylko na manę (ML wtedy nie zjada many)
        self.uh_hold_od = None
        self.uh_przerwal_cavebot = None    # powód przerwania zgłoszony przez callback (to nie porażka mechanizmu)
        self.unikanie = None           # unikanie.Unikanie: omijanie zwykłych graczy (haki: tick, _unikanie_filtr, _idz_trasa)
        self.moje_cele = {}            # CUDZY_MOB: id moba -> czas, kiedy wzięliśmy go na cel (nasze moby)
        self.cudzy_log = {}            # id moba -> czas ostatniego wpisu "pomijam cudzego moba" (bez spamu)
        self.patrol_zmiana_ost = float("-inf")   # czas ostatniej zmiany respa z powodu gracza (PATROL_GRACZ_ZMIEN)
        self.pk_stan = None            # obrona PK: None | "UCIECZKA" (do depo / awaryjna) | "DEPO" (czekamy) | "POWROT" (na spot) | "WALKA" (PvP, PVP_WALKA=1)
        self.pk_fallback = False       # True: brak planu do depo, ucieczka awaryjna (stary stan UCIECZKA po trasie)
        self.pk_od = float("-inf")     # kiedy ostatnio weszliśmy w ucieczkę PK
        self.pk_widoczni_ost = float("-inf")   # kiedy ostatnio widzieliśmy wroga (atak albo znany nick)
        self.pk_alarm_ost = float("-inf")
        self.pk_proba_ost = float("-inf")      # ostatnia próba startu trasy (fallback / powrót)
        self.pk_powrot_proby = 0
        self.pk_lista_ref = None       # lista stworów z poprzedniego obiegu już zapisana w pamięci potworów detektora
        self.pk_start_sprawdzony = False   # karencja z pliku sprawdzona przy pierwszym obiegu po starcie
        self.pk_start_wait = False     # DEPO wynika ze startu w karencji (po niej koniec obrony, bez trasy powrotnej)
        self.pk_depo_hp_od = None      # od kiedy w DEPO czekamy na zdrowie (HP < wznowienie_hp)
        self.pk_uh_ost = float("-inf")
        self.pk_uh_porazki = 0
        self.pk_uh_do = float("-inf")
        self.pk_uh_nast = float("-inf")    # PK_UH_SZYBKIE: najwcześniejszy czas kolejnej próby UH (odstęp z losowością)
        self.pk_uh_hist = []               # PK_UH_SZYBKIE: (czas, HP%) z ostatnich ~2,5 s do predykcji
        self.pk_uh_ctrl_porazki = 0
        self.pk_uh_alarm_ost = float("-inf")
        self.pk_rng = random.Random()      # losowość UH (test podaje ziarno)
        self.pk_exura_ost = float("-inf")
        self.pk_det = self.pk_wrogowie = None   # obrona_pk.DetektorPK / Wrogowie (tworzone przy pierwszym użyciu)
        self.pvp = None                # walka z napastnikiem (pk_stan "WALKA"): dict stanu walki albo None
        self._hak_unikania()
        self.znane_nowe = 0
        self.znane_zapis = zegar()
        self.zapis_znanych = self.klik is not None   # tylko na żywo (z atrapą ataku w testach - nie)
        if self.zapis_znanych:
            self._hak_telemetrii()
            self._hak_pochodni()
            self._hak_wypadu()

    # --- pomocnicze ---

    def _hak_telemetrii(self):
        try:
            import pokretla  # noqa: PLC0415
            import telemetria  # noqa: PLC0415
            self.tele = telemetria.Telemetria()
            nz = getattr(self.postac, "nazwa", None)
            if isinstance(nz, str):
                self.tele.nazwa_postaci = nz     # R0a: atrapa "Ja" z testów/skryptów nie zapisuje telemetrii
            self.tele.sprzatnij_stare()
            if not os.environ.get("RETRONIC_TESTY"):     # testy nie karmią telemetrii liniami logu (P4)
                HAKI_LOGU.append(self.tele.linia)
            self.pokretla = pokretla.Pokretla(sys.modules[__name__], log=lambda t: log(t))
            import powiadom  # noqa: PLC0415
            HAKI_LOGU.append(powiadom.z_logu)
            self.podsumowanie = powiadom.Podsumowanie()
        except Exception as e:   # telemetria nigdy nie wywraca bota
            print("telemetria wyłączona:", repr(e), flush=True)

    def _hak_pochodni(self):
        self.pochodnia = None
        try:
            import pochodnia  # noqa: PLC0415
            self.pochodnia = pochodnia.zywa(log=lambda t: log(t))
        except Exception as e:   # wymiana pochodni nigdy nie wywraca bota
            print("pochodnia wyłączona:", repr(e), flush=True)

    def _hak_unikania(self):
        try:
            import unikanie  # noqa: PLC0415
            self.unikanie = unikanie.Unikanie(sys.modules[__name__], zegar=self.zegar, log=lambda t: log(t),
                                              zdarzenie=self._unikanie_tele)
        except Exception as e:   # unikanie nigdy nie wywraca bota
            print("unikanie wyłączone:", repr(e), flush=True)

    def _unikanie_tele(self, typ, **d):
        tele = getattr(self, "tele", None)
        if tele:
            try:
                tele.zdarzenie(typ, **d)
            except Exception:
                pass

    def _unikanie_obserwuj(self, lista, poz):
        """Detekcja zwykłych graczy (debounce, koniec po zniknięciu, powiadomienie o długim pobycie)."""
        u = self.unikanie
        if u is None:
            return
        try:
            w_miescie = bool(UNIKANIE_TYLKO_SPOT and poz is not None and poz[2] <= 7)
            przy_depo = bool(self.dojscie_aktywne and DOJSCIE_BEZ_UNIKANIA_CALE)   # 16.10 (Karol): w całym dojściu na spot bez unikania graczy
            if not przy_depo and self.dojscie_aktywne and DOJSCIE_BEZ_UNIKANIA_POL > 0 and poz is not None:
                d0 = getattr(self, "_dojscie_start", None)      # P7f: tłum przy depo nie jest zagrożeniem
                przy_depo = bool(d0 and d0[2] == poz[2]
                                 and max(abs(d0[0] - poz[0]), abs(d0[1] - poz[1])) <= DOJSCIE_BEZ_UNIKANIA_POL)
            u.obserwuj(self.bez_widm(lista), poz, self.postac.nazwa,
                       wylacz=not self.zatrzymaj_przy_graczu or self.wypad_aktywny or w_miescie or przy_depo)
            self._patrol_pamietaj_graczy()
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"unikanie: błąd {e!r}")

    def _cudzy_mob_filtr(self, kand, poz):
        """CUDZY_MOB (Karol 17.10: nie przeszkadzamy innym graczom): gdy w ostatnich CUDZY_MOB_S s widzieliśmy obcego
        gracza (UNIKANIE_PROMIEN_MAX), nie bierzemy na cel moba z HP < 100%, którego sami nie zaczęliśmy (to mob tego
        gracza). Wyjątek: mob, który nas gryzie (spadek własnego HP w GRYZIE_OKNO) i stoi w odl <= 2."""
        if not CUDZY_MOB or not kand:
            return kand
        t = self.zegar()
        if not any(t - v[3] <= CUDZY_MOB_S for v in self.patrol_gracze_pam.values()):
            return kand
        gryzie = t - self.hp_gracza_spadek < GRYZIE_OKNO
        wynik = []
        for s in kand:
            odl = max(abs(s["x"] - poz[0]), abs(s["y"] - poz[1]))
            # mob tuż obok nas to nasz problem (bije nas, nawet słabo); czy stoi przy graczu, rozstrzyga unikanie.pomin_moba
            cudzy = s.get("hp", 100) < 100 and s.get("id") not in self.moje_cele \
                and odl > 1 and not (gryzie and odl <= 2)
            if not cudzy:
                wynik.append(s)
            elif t - self.cudzy_log.get(s.get("id"), float("-inf")) > 30.0:
                self.cudzy_log[s.get("id")] = t
                if len(self.cudzy_log) > 200:
                    self.cudzy_log = {k: v for k, v in self.cudzy_log.items() if t - v < 30.0}
                log(f"Unikanie: pomijam cudzego moba {s.get('nazwa')} ({s['x']},{s['y']}) HP {s.get('hp')}%: "
                    f"nie nasz, a niedawno był tu obcy gracz.")
        return wynik

    def _unikanie_filtr(self, kand, poz):
        """Wybór celu w tick(): bez mobów stojących w UNIKANIE_MOB_PROMIEN od innego gracza (poza tym, co stoi
        obok nas albo nas gryzie). Inne użycia kandydaci() (loot, pościg) widzą wszystkie moby."""
        kand = self._cudzy_mob_filtr(kand, poz)
        u = self.unikanie
        if u is None or not u.gracze or not kand:
            return kand
        try:
            gryzie = self.zegar() - self.hp_gracza_spadek < GRYZIE_OKNO
            return [s for s in kand if not u.pomin_moba(s, poz, gryzie=gryzie)]
        except Exception as e:
            log(f"unikanie: błąd {e!r}")
            return kand

    def _unikanie_droga(self, start, cel, blok):
        """Droga A* do `cel` (x,y) z pominięciem pól `blok` (strefa gracza) i nauczonych ścian; bez
        fallbacku "bez blokad" z droga() (on wprowadzałby nas z powrotem w strefę gracza)."""
        z = start[2]
        zaj = list(blok) + self._zakaz_lista(start, cel) + [p for p in list(self.sciany) if p[2] == z and self.sciana(p)]
        if self.mapa_zna(start, cel):
            return self.mapa.droga(start, cel, zaj, 0, False, limit=MAPA_LIMIT, znane=self._pola_pietra(z))
        return self._droga_znane(start, cel, zaj, 0, False)

    def _unikanie_krokami(self):
        """True, gdy unikanie jest aktywne i gracz jest w zasięgu: idziemy krok po kroku po bezpiecznej drodze
        (klik prowadziłby klienta własną, krótszą trasą tuż przy graczu albo przy mobie)."""
        if MIJANIE:
            return False                  # mijanie: marsz jak zwykle (klik), kroki tylko w skrócie i przy ustępowaniu (_mijanie_zastosuj)
        u = self.unikanie
        return u is not None and u.aktywne and bool(u.gracze or getattr(u, "duchy", None)) and not self.wypad_aktywny

    def _przerwa_przerwij_gdy_gracz(self, teraz):
        """UNIKANIE_PRZERWA (17.10): zwykły gracz w UNIKANIE_PROMIEN kończy PRZERWĘ od razu (dawniej stała do końca obok niego).
        True = przerwa zakończona, następna wg PRZERWA_CO_MIX."""
        u = self.unikanie
        if not UNIKANIE_PRZERWA or u is None or not u.gracze or u.gracze[0]["odl"] > UNIKANIE_PROMIEN:
            return False
        g0 = u.gracze[0]
        log(f"Przerwa przerwana: gracz {g0['nazwa']} {g0['odl']} pól od nas.")
        self.przerwa_do = None
        self.przerwa_od = teraz + losuj_z_mieszanki(PRZERWA_CO_MIX)
        return True

    def _unikanie_trasa(self, poz):
        """Hak w _idz_trasa: unikanie.py może przestawić self.idx (inny punkt rotacji / cofnięcie) i podać
        bezpieczną drogę (trasa_droga), więc zwykły marsz nie wchodzi na gracza. Priorytety (ucieczka,
        jedzenie, walka) są wyżej w tick(), tu dotyczy tylko kierunku marszu."""
        u = self.unikanie
        if u is None or self.wypad_aktywny or not self.punkty:
            return
        try:
            r = u.decyduj(poz, self.punkty, self.idx, self._unikanie_droga)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"unikanie: błąd {e!r}")
            return
        if r is None:
            return
        if r.zmiana:
            self.idx = r.idx
            self.klik_j = None
            self.klik_cel = None
            self.nieudane = 0
            self.pominiete = 0
            self.zablokowane.clear()
        if r.tryb in ("tyl", "czekaj", "omin"):
            self.utk_okno = None          # chodzenie tam i z powrotem przy graczu to nie utknięcie na trasie
        if r.droga:
            self.trasa_droga = (self.punkty[r.idx], [tuple(poz)] + [tuple(p) for p in r.droga], self.zegar())
        if r.pauza:
            self.pauza(*r.pauza)

    def _mijanie_wolne(self, pole):
        """Pole do stania/przejścia dla mijania: znane mapie (albo kiedyś odwiedzone), bez ściany, ognia i zmiany piętra."""
        pole = tuple(pole)
        if self._pole_zablokowane(pole, ()):
            return False
        if self.mapa is not None and self.mapa.flagi(*pole) & 1:
            return True
        return pole in self.znane

    def _mijanie_trasa(self, poz):
        """Hak w _idz_trasa przy MIJANIE=1 (zamiast _unikanie_trasa): unikanie.mijanie() ocenia kierunek graczy względem pętli
        i może odwrócić obieg, poprowadzić skrótem, zejść z drogi albo kazać stać. True = obieg zużyty (krok / postój)."""
        u = self.unikanie
        if u is None or self.wypad_aktywny or not self.punkty:
            return False
        teraz = self.zegar()
        w_walce = bool(self.cel) or teraz - self.hp_gracza_spadek < GRYZIE_OKNO
        try:
            r = u.mijanie(poz, self.punkty, self.idx, self._unikanie_droga, wolne_fn=self._mijanie_wolne,
                          otwarta=self.otwarta, w_walce=w_walce)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"mijanie: błąd {e!r}")
            return False
        return self._mijanie_zastosuj(poz, r)

    def _mijanie_trzyma(self):
        """True, gdy mijanie trzyma obecny kierunek obiegu (Q3): trwa decyzja wobec któregoś gracza albo był w widoku w ostatnich
        MIJANIE_ZNIKL_S. Wtedy losowe odwrócenie na końcu okrążenia jest pomijane (nie cofamy się w stronę gracza)."""
        u = self.unikanie
        return u is not None and u.mijanie_trzyma()

    def _mijanie_zastosuj(self, poz, r):
        """Wykonanie decyzji mijania. "odwroc": odwracamy listę punktów jak na końcu okrążenia (następny cel = punkt, który
        właśnie minęliśmy), marsz idzie dalej w tym samym obiegu; "marsz": jeden krok `r.krok` (skrót / krok w bok), przy skrócie
        z nowym `idx`; "stoj": stoimy i patrzymy. True = obieg zużyty."""
        if r is None:
            return False
        n = len(self.punkty)
        if r.akcja == "odwroc":
            # stoimy na punkcie k (do 9 przed idx, kliknięcie mija kilka punktów między obiegami) albo między punktami (k = idx)
            k = next((j % n for j in range(self.idx - 1, self.idx + 10) if tuple(self.punkty[j % n]) == tuple(poz)), self.idx)
            self.punkty.reverse()
            self.idx = (n - k) % n
            self.przebyte = 0                    # nowe okrążenie liczymy od zera: "koniec okrążenia" nie przychodzi zaraz po odwróceniu
            self.klik_j = None
            self.klik_cel = None
            self.__dict__["utk_zakaz"] = {}      # klucze = indeksy punktów: po odwróceniu znaczą co innego
            self.trasa_droga = None
            self.nieudane = 0
            self.pominiete = 0
            self.zablokowane.clear()
            self.utk_okno = None
            return False                         # krok w nowym kierunku robi dopiero następny _idz_trasa (obieg niezużyty)
        if r.idx is not None and r.idx != self.idx:
            self.idx = r.idx
            self.klik_j = None
            self.klik_cel = None
            self.nieudane = 0
            self.pominiete = 0
            self.trasa_droga = None
            self.zablokowane.clear()
        self.utk_okno = None                      # stanie i krok w bok przy graczu to nie utknięcie na trasie
        if r.akcja == "marsz":
            self.klik_j = None
            self.krok_do(r.krok)
            return True
        if r.akcja == "stoj":
            if getattr(self, "marsz", None) is not None:      # getattr: testy mijania wołają tę metodę na atrapie bez stanu marszu
                self._marsz_stop(poz, "mijanie: stoimy")          # MARSZ_KLIK: stoimy, więc klient nie może iść dalej sam
            self.pauza(0.2, 0.45)
            return True
        return False

    def _hak_wypadu(self):
        try:
            import wypad  # noqa: PLC0415
            ops = wypad.OperacjeZywe(log=lambda t: log(t), wyslij=self._wypad_wyslij_tekst,
                                     zarejestruj=self._wypad_zarejestruj_tekst)
            try:
                import wyprawa  # noqa: PLC0415
                ops = wyprawa.OperacjeZywe(log=lambda t: log(t), wyslij=self._wypad_wyslij_tekst,
                                           zarejestruj=self._wypad_zarejestruj_tekst)
                self.wyprawa = wyprawa.Wyprawa(self, ops, konf=sys.modules[__name__], log=lambda t: log(t))
            except Exception as e:   # wyprawa nigdy nie wywraca wypadu po pochodnie
                print("wyprawa wyłączona:", repr(e), flush=True)
                self.wyprawa = wypad.Wypad(self, ops, konf=sys.modules[__name__], log=lambda t: log(t))
        except Exception as e:   # wypad nigdy nie wywraca bota
            print("wypad wyłączony:", repr(e), flush=True)

    def _wypad_wyslij_tekst(self, tekst):
        if self.wypad_wyslij is None:
            raise RuntimeError("brak funkcji wysyłania na czat")
        self.wypad_wyslij(tekst)

    def _wypad_zarejestruj_tekst(self, tekst):
        if self.wypad_czat is not None:
            self.wypad_czat.wyslano(tekst)

    def _wypad_bieg(self, kand, poz, teraz):
        """True = w wypadzie/wyprawie omijamy walkę (kand puste, bot biegnie dalej). Walka tylko, gdy stoimy w miejscu
        >= WYPAD_BLOK_S ze stworem obok (droga zablokowana); potem WYPAD_WALKA_S s walki bez ponownej oceny."""
        bieg = DOJSCIE_BIEGNIJ if self.dojscie_aktywne else (WYPAD_BIEGNIJ and self.wypad_aktywny)
        if not bieg or self.stoj_wl:            # 23.10 STÓJ: wypad zawieszony, walka w miejscu jak zwykle
            self.wypad_walka_do = float("-inf")
            return False
        obok = [s for s in kand if self.dystans((s["x"], s["y"]), poz) <= 1]
        if teraz < getattr(self, "wypad_walka_do", float("-inf")):
            if getattr(self, "_walka_przejscie", False) and not obok:
                self.wypad_walka_do = float("-inf")      # P7d: blokujący zabity/odszedł: znów biegniemy
                self._walka_przejscie = False
                return True
            return False
        self._walka_przejscie = False
        walka_s = WYPAD_WALKA_S
        if obok and self._cele_pierwsze() and any(self._cel_pierwszy(s) for s in obok):
            # 24.10 CELE_PIERWSZE: potwór z listy (Wasp: trucizna) OBOK = walka od razu, bez czekania WYPAD_BLOK_S; po jego
            # zabiciu (nikogo obok) znów biegniemy (jak po blokującym przy przejściu)
            self.wypad_walka_do = teraz + walka_s
            self._walka_przejscie = True
            log(f"{'Dojście' if self.dojscie_aktywne else 'Wypad'}: {next(s for s in obok if self._cel_pierwszy(s))['nazwa']} obok "
                f"(CELE_PIERWSZE), walczę zamiast biec.")
            return False
        blok_s, ruch_od = WYPAD_BLOK_S, self.ruch_czas
        if PK_UH_SZYBKIE and self.pk_stan == "UCIECZKA" and not self.dojscie_aktywne:
            # R4: w ucieczce PK mob obok to nie powód do walki, dopóki idziemy; droga zamknięta = brak postępu
            # od startu ucieczki (nie od starego ruch_czas sprzed ucieczki) przez PK_UCIECZKA_BLOK_S, walka max PK_UCIECZKA_WALKA_S
            blok_s = PK_UCIECZKA_BLOK_S
            ruch_od = max(self.ruch_czas, getattr(self, "pk_od", float("-inf")))
            walka_s = min(walka_s, float(PK_UCIECZKA_WALKA_S))
        if obok and self.dojscie_aktywne and DOJSCIE_WALKA_PRZEJSCIE_S > 0 and self._dojscie_przy_przejsciu(poz):
            walka_s = max(WYPAD_WALKA_S, float(DOJSCIE_WALKA_PRZEJSCIE_S))   # P7d: przy dziurze nie cyklujemy co 8 s
            self._walka_przejscie = walka_s > WYPAD_WALKA_S
        if obok and teraz - ruch_od >= blok_s:
            self.wypad_walka_do = teraz + walka_s
            log(f"{'Dojście' if self.dojscie_aktywne else 'Wypad'}: droga zablokowana przez {obok[0]['nazwa']}, "
                f"walczę {walka_s:.0f} s.")
            return False
        # pętla dziura/drabina zmienia piętro, więc ruch_czas ciągle się zeruje: stwór obok + brak postępu w oknie
        # (ten sam rejon mimo ruchu) też jest zablokowaniem
        hist = getattr(self, "wypad_hist", None)
        if hist is None:
            hist = self.wypad_hist = []
        hist.append((teraz, poz[0], poz[1]))
        while hist and teraz - hist[0][0] > WYPAD_PETLA_S + 2.0:
            hist.pop(0)
        if WYPAD_PETLA_S > 0 and obok and hist and teraz - hist[0][0] >= WYPAD_PETLA_S \
                and max(max(abs(x - poz[0]), abs(y - poz[1])) for _, x, y in hist) <= WYPAD_PETLA_PROMIEN:
            self.wypad_walka_do = teraz + walka_s
            hist.clear()
            log(f"{'Dojście' if self.dojscie_aktywne else 'Wypad'}: brak postępu przez {WYPAD_PETLA_S:.0f} s przy "
                f"{obok[0]['nazwa']}, walczę {walka_s:.0f} s.")
            return False
        return True

    def _blokada_bij_tick(self, lista, poz, teraz):
        """BLOKADA_BIJ_KAZDEGO: w dojściu/wypadzie (marsz bez walki) stwór spoza listy `--potwory`, który stoi na JEDYNYM kroku drogi
        (pierwsze pole A* do celu marszu zajęte, a objazdu z mapy nie ma), staje się celem blokującym: kandydaci() go przepuszcza, a
        _wypad_bieg() po WYPAD_BLOK_S bez ruchu bije go WYPAD_WALKA_S s ("droga zablokowana przez X, walczę"). Gracze nigdy.
        Gdy objazd istnieje: nic (marsz obejdzie). Wpis wygasa sam; po zabiciu/odejściu stwora wracamy do biegu."""
        bij = self.__dict__.setdefault("blokada_bij", {})
        for k in [k for k, v in bij.items() if v < teraz]:
            del bij[k]
        if not BLOKADA_BIJ_KAZDEGO or self.potwory is None:
            return
        if not ((self.dojscie_aktywne and DOJSCIE_BIEGNIJ) or (self.wypad_aktywny and WYPAD_BIEGNIJ)):
            return
        ct = self.__dict__.get("cel_trasy")
        if ct is None or teraz - ct[1] > 5.0 or ct[0][2] != poz[2] or teraz - self.ruch_czas < WYPAD_BLOK_S:
            return
        try:
            zywe = [s for s in self.bez_widm(lista) if s.get("z") == poz[2] and s.get("hp", 100) > 0
                    and (s["x"], s["y"]) != tuple(poz[:2])]
            obcy = [s for s in zywe if not s.get("gracz") and self.dystans((s["x"], s["y"]), poz) <= 1
                    and s["nazwa"].casefold() not in self.potwory]
            if not obcy:
                return
            cel = ct[0]
            zapas = self.ostatni_blokujacy
            try:
                wolna = self.droga(tuple(poz), tuple(cel[:2]), (), 0)
                zaj = {(s["x"], s["y"]) for s in zywe}
                obj = self.droga(tuple(poz), tuple(cel[:2]), [(x, y, poz[2]) for x, y in zaj], 0)
            finally:
                self.ostatni_blokujacy = zapas
            if not wolna:
                return                                    # brak drogi z mapy / jesteśmy u celu: nie zgadujemy
            krok = tuple(wolna[0][:2])
            b = next((s for s in obcy if (s["x"], s["y"]) == krok), None)
            if b is None:
                return                                    # nic obcego na pierwszym kroku drogi
            if obj and len(obj) <= len(wolna) + BLOKADA_BIJ_OBJAZD \
                    and not any(tuple(q[:2]) in zaj for q in obj[:max(2, int(BLOK_KROKI))]):
                return                                    # jest objazd: marsz go użyje, bez walki
            nowy = b["id"] not in bij
            bij[b["id"]] = teraz + WYPAD_WALKA_S + 6.0
            if nowy:
                log(f"{'Dojście' if self.dojscie_aktywne else 'Wypad'}: {b['nazwa']} ({b['x']},{b['y']}) stoi na jedynym kroku drogi "
                    f"do {tuple(cel[:2])}, objazdu nie ma: bijemy go (poza listą --potwory).")
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"debug: blokada_bij: błąd {e!r}")

    def _hp_przed_pietrem(self, poz, teraz, klucz):
        """HP_PRZED_PIETREM: w dojściu/wypadzie tuż przed przejściem pięter (wołane z pietra.py i wypad.py) postać czeka w miejscu, aż
        HP% >= HP_PRZED_PIETREM (leczenie exura w _zdrowie_czar_tick; próg leczenia na czas czekania = ten próg). True = czekamy
        (obieg zużyty). Nie czeka: przy żywym stworze <= 2 pola, gdy HP spada (walka/ucieczka mają pierwszeństwo), po
        HP_PRZED_PIETREM_MAX_S s (log, bez STOP; to samo przejście nie czeka drugi raz). Progi ucieczki/HP/OGIEN bez zmian."""
        prog = HP_PRZED_PIETREM
        if not prog or not (self.dojscie_aktywne or self.wypad_aktywny):
            return False
        g = self.__dict__.get("g_tick") or {}
        proc = g.get("proc")
        if proc is None:
            return False
        kl = (poz[2],) + tuple(klucz)
        st = self.__dict__.get("hp_czeka")
        if st is not None and st["kl"] != kl:
            st = self.hp_czeka = None
        if proc >= prog:
            self.hp_czeka_odpuszczone = None          # HP znów w normie: kolejne przejście znów może poczekać
            if st is not None:
                log(f"HP {proc:.0f}% >= {prog}%: koniec czekania po {teraz - st['od']:.0f} s, idę dalej ({klucz}).")
                self.hp_czeka = None
                if str(self.stan) == "PAUZA_HP":
                    self.stan = "IDZ"
            return False
        if self.__dict__.get("hp_czeka_odpuszczone") == kl:
            return False
        gryzie = teraz - self.hp_gracza_spadek < GRYZIE_OKNO
        blisko = any(not s.get("gracz") and s.get("z") == poz[2] and s.get("hp", 100) > 0
                     and self.dystans((s["x"], s["y"]), poz) <= 2 for s in (self.ostatnie_stwory or ()))
        if gryzie and blisko:
            return False
        if st is None:
            st = self.hp_czeka = {"kl": kl, "od": teraz, "ost": teraz, "log": teraz}
            log(f"HP {proc:.0f}% < {prog}%: czekam w miejscu przed przejściem pięter {klucz} "
                f"(leczenie exura {'tak' if ZDROWIE_CZAR_AKTYWNY else 'wyłączone'}, mana {g.get('mana')}), najdłużej {HP_PRZED_PIETREM_MAX_S:.0f} s.")
        if teraz - st["od"] >= HP_PRZED_PIETREM_MAX_S:
            log(f"HP {proc:.0f}% nadal < {prog}% po {teraz - st['od']:.0f} s czekania: idę dalej mimo to ({klucz}).")
            self.hp_czeka_odpuszczone = kl
            self.hp_czeka = None
            if str(self.stan) == "PAUZA_HP":
                self.stan = "IDZ"
            return False
        self.__dict__["hp_czekal_s"] = self.__dict__.get("hp_czekal_s", 0.0) + min(5.0, teraz - st["ost"])
        st["ost"] = teraz
        if teraz - st["log"] >= 30.0:
            st["log"] = teraz
            log(f"HP {proc:.0f}% < {prog}%: czekam dalej ({teraz - st['od']:.0f} s, mana {g.get('mana')}).")
        self.hp_czeka_ts = teraz
        self.aktywnosc_ts = teraz
        self.stan = "PAUZA_HP"
        self.pauza(0.4, 0.9)
        return True

    def lopata_bezpiecznie(self, poz):
        """24.10 (review): tuż po Use łopaty (kilka sekund po początku obiegu) krok w odkopaną dziurę wolno zrobić w TYM SAMYM obiegu
        tylko po świeżym odczycie: HP (g_tick i hp_gracza_spadek są odświeżane, więc bramka _hp_przed_pietrem czyta świeże HP, nie
        z początku obiegu) i stworów. False = walka/ucieczka/HP mają pierwszeństwo, krok zostaje zwykłej ścieżce tick() (po bramce HP
        i _trasa_stop_potwor): żywy stwór <= 2 pola, potwór z listy w promieniu TRASA_STOP_PRZY_POTWORZE_R, HP spada (gryzie) albo
        odczyt się nie udał."""
        try:
            teraz = self.zegar()
            g = self.gracz()
            self.g_tick = g
            if g.get("max_hp"):
                pct = g["proc"]
                self.hp_hist = [(t, h) for t, h in self.hp_hist if teraz - t <= GRYZIE_OKNO] + [(teraz, pct)]
                if max(h for _, h in self.hp_hist) - pct >= GRYZIE_SPADEK_PP:
                    self.hp_gracza_spadek = teraz
            if teraz - self.hp_gracza_spadek < GRYZIE_OKNO:
                return False
            lista = self.stwory(0.0)
            self.ostatnie_stwory = lista
            if any(not s.get("gracz") and s.get("z") == poz[2] and s.get("hp", 100) > 0
                   and self.dystans((s["x"], s["y"]), poz) <= 2 for s in lista):
                return False
            return not self._trasa_stop_potwor(tuple(poz))
        except (bot.Zatrzymano, KeyboardInterrupt):
            raise
        except Exception as e:
            log(f"debug: lopata_bezpiecznie: błąd {e!r}")
            return False

    def _dojscie_przy_przejsciu(self, poz):
        """P7d: najbliższe punkty trasy (idx..idx+2) zmieniają piętro, a przejście jest <= 3 pola od postaci."""
        try:
            n = len(self.punkty)
            for k in range(self.idx, min(n, self.idx + 3)):
                q = self.punkty[k]
                if q[2] != poz[2] and max(abs(q[0] - poz[0]), abs(q[1] - poz[1])) <= 3:
                    return True
            return False
        except Exception:
            return False

    def _wypad_tick(self):
        """Wypad po pochodnie: True, gdy zużył obieg (wołane na początku idz(), więc dopiero po walce i locie)."""
        w = self.wyprawa
        if w is None:
            return False
        try:
            return bool(w.tick())
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"wypad: błąd {e!r}")
            return False

    def wypad_przerwij(self, powod):
        """ALARM_GM / zewnętrzny stop: wypad kończy się natychmiast i nie wznawia samoczynnie."""
        if self.wyprawa is not None:
            self.wyprawa.przerwij(powod)
        self.wypad_aktywny = False

    def _wypad_reset_klik(self):
        self.klik_cel = None
        self.klik_j = None
        self.trasa_droga = None
        self.utk_okno = None
        self.nieudane = 0
        self.zablokowane.clear()

    def _wypad_wroc_na_trase(self, poz):
        """Koniec wypadu: idx trasy łowiska na najbliższy punkt (po drodze) na piętrze gracza."""
        self._wypad_reset_klik()
        self._patrol_reset(True)           # patrol: po wypadzie najbliższe miejsce
        n = len(self.punkty)
        z = poz[2]
        kand = sorted((k for k in range(n) if self.punkty[k][2] == z),
                      key=lambda k: self.dystans(poz, self.punkty[k]))[:UTKNIECIE_KAND]
        wybrany = None
        for k in kand:
            q = self.punkty[k]
            d = [] if tuple(poz[:2]) == q[:2] else self.droga(tuple(poz), q[:2], dlugosc=0)
            if d is not None and (wybrany is None or len(d) < wybrany[0]):
                wybrany = (len(d), k)
        if wybrany is None and kand:
            wybrany = (0, kand[0])
        if wybrany is not None:
            self.idx = wybrany[1]
            log(f"Wypad: wracam na trasę łowiska do punktu {self.idx}")
            return True
        log("Wypad: brak punktu trasy łowiska na tym piętrze")
        return False

    def _idz_odcinek(self, punkty, idx):
        """Jeden obieg zwykłego chodzenia po trasie, ale po odcinku `punkty` (jedno piętro) zamiast po trasie
        łowiska (wypad). -> (wynik _idz_trasa, nowy idx w odcinku)."""
        zapas = (self.punkty, self.idx, self.przebyte, self.okrazenie, self.otwarta, self.pominiete)
        # kopie ostatniego punktu na końcu: zaliczanie punktów "do przodu" nie zawija się na początek odcinka
        # (krótki odcinek = fałszywe "okrążenie"); na ostatnim punkcie wypad sam kończy etap
        self.punkty, self.idx, self.otwarta, self.stan = list(punkty) + [punkty[-1]] * 10, idx, True, "IDZ"
        self.przebyte = 0
        try:
            wynik = self._idz_trasa()
            return wynik, min(self.idx, len(punkty) - 1)
        finally:
            self.punkty, self.idx, self.przebyte, self.okrazenie, self.otwarta, self.pominiete = zapas
            self.stan = "WYPAD"

    def _pochodnia_tick(self, lista, poz):
        """Co ~30 s sprawdza pochodnię w slocie (pochodnia.py); tylko gdy nic żywego w pobliżu."""
        if getattr(self, "pochodnia", None) is None:
            return False
        try:
            if self.zywy_w_poblizu(lista, poz) is not None or self.cel is not None:
                return False
            if self.pochodnia.tick(self.zegar()):
                self.ustaw_stan("POCHODNIA", "wymiana")
                self.aktywnosc_ts = self.zegar()
                self.pauza(0.3, 0.8)
                return True
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"pochodnia: błąd {e!r}")
        return False

    def _ml_blokada(self, lista, poz):
        """Powód, dla którego teraz nie rzucamy czaru (albo None). Czat zablokowany/pauza/rozmowa = zawsze blokada."""
        czat = self.wypad_czat
        if czat is not None and getattr(czat, "zablokowany", False):
            return "czat_zablokowany"             # ALARM_GM
        if self._poscig_przerwanie():
            return "pauza_mozgu"                  # pauza_bota / rozmowa z graczem
        if self.ucieczka or self.ostrozny:
            return "ucieczka"
        if self.w_lootcie or self.lww is not None or self.lww_zalegle is not None:
            return "loot"
        if self.wypad_aktywny or str(self.stan).startswith(("WYPAD", "POCHODNIA", "LOOT", "JEDZENIE", "GRACZ")):
            return "wypad"
        if not ML_CZAR_W_WALCE:
            if self.cel is not None or self.w_poscigu or self.pamiec is not None \
                    or str(self.stan) == "WALKA":
                return "walka"
            if self.zywy_w_poblizu(lista, poz) is not None:
                return "mob_blisko"
        return None

    # --- pet (pet_ster.py) ---
    def _pet_ster(self):
        if self.pet is None:
            import pet_ster  # noqa: PLC0415
            self.pet = pet_ster.PetSterowanie(instancja.S.logi, log=lambda t: log(t))
        return self.pet

    def pet_wiadomosc(self, w):
        """Hak mózgu: surowa linia czatu/Server Log (dict autor/tekst/kanal/czas/nr). Błąd nie wywraca bota."""
        if not PET_WLACZONY or self.pet is None:
            return
        try:
            self.pet.wiadomosc(w, nazwa=PET_NAZWA)
        except Exception as e:
            log(f"debug: pet wiadomość błąd {e!r}")

    def _pet_obserwuj(self, g, poz, lista, teraz):
        """Raz na tick, zaraz po odczycie stworów: statystyki i śledzenie peta. -> lista bez peta."""
        if not PET_WLACZONY and self.pet is None:
            return lista
        try:
            pet = self._pet_ster()
            surowa = self.stwory_surowe or lista
            pet.obserwuj(surowa, g, poz, teraz, cel_id=self.cel["id"] if self.cel else None, nazwa=PET_NAZWA,
                         stabilne_s=PET_STABILNE_S, porazki_max=PET_PORAZKI,
                         przerwa_po_porazkach_s=PET_PRZERWA_PO_PORAZKACH_S)
            return pet.bez_peta(surowa)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"[PET] błąd obserwacji {e!r}")
            return lista

    def _pet_tick(self, g, poz, lista, teraz):
        """True = obieg zużyty (rzucono czar). Wyłączone pokrętłem = brak śladu; błąd nigdy nie wywraca bota."""
        if not PET_WLACZONY:
            return False
        try:
            return self._pet(g, poz, lista, teraz)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"[PET] błąd {e!r}")
            return False

    def _pet(self, g, poz, lista, teraz):
        pet = self._pet_ster()
        surowa = self.stwory_surowe or lista
        mana = g.get("mana")
        blokada = self._ml_blokada(lista, poz)      # czat/pauza/ucieczka/loot/wypad (walka niżej, niezależnie od ML_CZAR_W_WALCE)
        walka = blokada is not None or self.cel is not None or self.w_poscigu or self.pamiec is not None \
            or str(self.stan) == "WALKA" or self.zywy_w_poblizu(lista, poz) is not None
        # 17.10 "przyzwij teraz": plik PRZYWOLAJ_PETA omija blokadę walki (bot stale poluje, więc spokoju nie ma)
        reczne = PET_PRZYWOLAJ_PLIK.exists()
        if reczne:
            walka = False
        powod = pet.powod_blokady(bool(PET_WLACZONY), mana, PET_MANA_MIN, walka, teraz, poz,
                                  pietro_spotu=PET_PIETRO, stabilne_s=PET_STABILNE_S, zmiany_max=PET_ZMIANY_MAX,
                                  zmiany_okno_s=PET_ZMIANY_OKNO_S, zgony_max=PET_ZGONY_MAX)
        if powod is not None or teraz - self.czar_ostatni < CZAR_MIN_PRZERWA_S:
            return False
        if self.wypad_wyslij is None:
            return False
        if self.zd_oczekuje is not None or self.jc_oczekuje is not None:
            return False                            # trwa weryfikacja exura/exevo pan
        tekst = f'{PET_CZAR} "{PET_NAZWA}"'
        self._poscig_puszcz()                       # pole czatu pochłonęłoby trzymane strzałki
        self.czar_ostatni = teraz
        self.aktywnosc_ts = teraz
        self.ustaw_stan("PET", f"{tekst} (mana {mana})")
        pet.rzucono(surowa, mana, teraz, PET_PRZERWA_S, tekst)
        self._wypad_zarejestruj_tekst(tekst)
        self._wypad_wyslij_tekst(tekst)
        self.pauza(0.3, 0.8)
        if reczne:
            PET_PRZYWOLAJ_PLIK.unlink(missing_ok=True)
            log("[PET] przywołanie ręczne (PRZYWOLAJ_PETA): rzucono, plik usunięty")
        return True

    def _ml_tele(self, typ, **d):
        self._tele_poscig(typ, **d)

    def _ml_czar_tick(self, g, poz, lista, teraz):
        """Rzuca czar (hotkey ML_CZAR_KLAWISZ), gdy mana >= koszt, minął exhaust i jest spokój. True = obieg zużyty."""
        try:
            return self._ml_czar(g, poz, lista, teraz)
        except bot.Zatrzymano:
            raise
        except Exception as e:                    # rzucanie czaru nigdy nie wywraca bota
            log(f"ML: błąd {e!r}")
            return False

    def _ml_czar(self, g, poz, lista, teraz):
        mana = g.get("mana")
        # weryfikacja poprzedniego rzutu (także gdy pokrętło wyłączono w międzyczasie)
        if self.ml_oczekuje is not None and mana is not None \
                and teraz - self.ml_oczekuje[0] >= ML_CZAR_WERYFIKACJA_S:
            t0, przed = self.ml_oczekuje
            self.ml_oczekuje = None
            if mana < przed:
                self.ml_porazki = 0
                wydane = przed - mana
                self.ml_rzuty += 1
                self.ml_mana_wydana += wydane
                self._ml_tele("ml_czar", wynik="ok", mana_przed=przed, mana_po=mana, wydane=wydane,
                              rzuty=self.ml_rzuty, wydane_razem=self.ml_mana_wydana)
                if self.ml_rzuty % ML_CZAR_LOG_CO == 0:
                    log(f"ML: rzucono {self.ml_rzuty}, many wydane {self.ml_mana_wydana}")
            else:
                self.ml_porazki += 1
                self._ml_tele("ml_czar", wynik="brak_spadku", mana_przed=przed, mana_po=mana, porazki=self.ml_porazki)
                log(f"ML: po rzucie mana nie spadła ({przed} -> {mana}), porażka {self.ml_porazki}/{ML_CZAR_PORAZKI}.")
                if self.ml_porazki >= ML_CZAR_PORAZKI:
                    self.ml_porazki = 0
                    self.ml_wylaczony_do = teraz + ML_CZAR_PRZERWA_PO_PORAZKACH_S
                    log(f"ML: czar '{ML_CZAR_TEKST}' nie działa ({ML_CZAR_PORAZKI}x bez spadku many, zły hotkey {ML_CZAR_KLAWISZ}/brak czaru?), "
                        f"wyłączam rzucanie na {ML_CZAR_PRZERWA_PO_PORAZKACH_S / 60:.0f} min.")
                    self._ml_tele("ml_czar_wylaczony", na_s=ML_CZAR_PRZERWA_PO_PORAZKACH_S, tekst=ML_CZAR_TEKST)
        if not ML_CZAR_AKTYWNY or mana is None or teraz < self.ml_wylaczony_do:
            self.ml_plan = None
            return False
        if self.ml_oczekuje is not None or mana < ML_CZAR_KOSZT:
            self.ml_plan = None
            return False
        # nie rzucamy zawsze w chwili, gdy mana dojdzie do kosztu: losowa nadwyżka (ale osiągalna)
        wymagana = ML_CZAR_KOSZT + self.ml_zapas_many
        mx = g.get("max_mana")
        if mx:
            wymagana = min(wymagana, max(ML_CZAR_KOSZT, int(mx)))
        if mana < wymagana:
            self.ml_plan = None
            return False
        exhaust = max(float(ML_CZAR_MIN_PRZERWA_S), 2.5) + self.ml_extra_przerwa
        if teraz - self.ml_ostatni < exhaust or teraz - self.czar_ostatni < CZAR_MIN_PRZERWA_S \
                or self._ml_blokada(lista, poz) is not None:
            self.ml_plan = None
            return False
        # priorytet many: exura > exevo pan > ML. W walce z niskim HP ML nie zjada many przeznaczonej na leczenie
        if g.get("proc", 100.0) < ML_BLOK_HP and self._walka_lub_mob(lista, poz):
            self.ml_plan = None
            return False
        if self.zd_oczekuje is not None or self.jc_oczekuje is not None \
                or (JEDZENIE_CZAR_AKTYWNY and teraz < self.jc_glod_do):
            self.ml_plan = None
            return False
        if self._ml_czeka_na_zapas(g, teraz):      # exevo pan (zapas < MIN) ma pierwszeństwo przed ML
            self.ml_plan = None
            return False
        if self._uh_trzyma_mane(teraz):            # UH czeka na manę (>= UH_MANA_MIN): ML jej nie zjada
            self.ml_plan = None
            return False
        if self.ml_plan is None:                   # losowe opóźnienie: bez regularności
            if random.random() < ML_CZAR_DLUGA_SZANSA:
                self.ml_plan = teraz + random.uniform(*ML_CZAR_DLUGA)
            else:
                self.ml_plan = teraz + random.uniform(*ML_CZAR_OPOZNIENIE)
            return False
        if teraz < self.ml_plan:
            return False
        self.ml_plan = None
        if self._zapas_nieznany_f3(g, mana, teraz):
            return True                            # plecak nieczytelny: zamiast ML raz na 10 min exevo pan
        self.jz_hold_od = None
        self.ml_ostatni = teraz
        self.czar_ostatni = teraz
        self.ml_extra_przerwa = random.uniform(*ML_CZAR_EXTRA_PRZERWA)
        self.ml_zapas_many = random.randint(*ML_CZAR_ZAPAS_MANY)
        self.ml_oczekuje = (teraz, mana)
        self.aktywnosc_ts = teraz
        self.ustaw_stan("ML", f"czar {ML_CZAR_TEKST} [{ML_CZAR_KLAWISZ}] (mana {mana})")
        self.postac.klawisz(ML_CZAR_KLAWISZ)      # hotkey w kliencie, nic nie trafia na czat
        self.pauza(0.2, 0.5)
        return True

    # --- UH: robienie run w spokoju (uh.py) ---
    def _uh_srodowisko(self):
        if self.uh_env is None:
            import uh  # noqa: PLC0415
            env = uh.SrodowiskoGry(self.postac, self.zapytaj, self._uh_przerwanie,
                                   alarm=lambda t: self.alarm(t), log=lambda t: log(f"[UH] {t}"))
            env.stan = _UhStan(UH_STAN_PLIK)
            self.uh_env = env
        return self.uh_env

    def _uh_przerwanie(self):
        """Callback uh.py: powód natychmiastowego powrotu tarczy albo None."""
        try:
            g = self.gracz()
            poz = self.postac.pozycja()
            powod = None
            walka = bool(self.uh_tryb_walki)       # runa startowana w walce: moby nie przerywają, chyba że przylegają
            prog_hp = (UH_W_WALCE_MIN_HP if walka else UH_MIN_HP) - 10
            if self.ucieczka or self.ostrozny:
                powod = "ucieczka"
            elif g.get("proc", 100.0) < prog_hp:
                powod = f"HP {g['proc']:.0f}%"
            elif walka and self.uh_hp_start is not None \
                    and self.uh_hp_start - g.get("proc", 100.0) >= UH_W_WALCE_SPADEK_HP:
                powod = f"HP spada {self.uh_hp_start:.0f}% -> {g['proc']:.0f}%"
            elif self._czar_blokada() is not None:
                powod = str(self._czar_blokada())
            else:
                for s in self.stwory(0.0):
                    if s.get("z") != poz[2] or s.get("hp", 100) <= 0:
                        continue
                    if s.get("gracz") and s.get("nazwa") == self.postac.nazwa:
                        continue
                    if self._uh_widoczny(s, poz, walka):
                        powod = f"w widoku {s.get('nazwa', '?')}"
                        break
        except bot.Zatrzymano:
            raise
        except Exception as e:
            powod = f"błąd odczytu {e!r}"
        if powod is not None:
            self.uh_przerwal_cavebot = powod
        return powod

    def _uh_widoczny(self, s, poz, walka=False):
        """True: byt s blokuje/przerywa UH. Gracz: cały widok (ZASIEG_X/Y). Stwór: tylko w odległości
        (Chebyshev) <= UH_MOB_DYSTANS; dalsze szczury krążące w pobliżu nie blokują robienia runy.
        walka=True (UH_W_WALCE): stwór blokuje/przerywa tylko gdy jest w odległości <= UH_W_WALCE_DYSTANS
        (0 = moby nie liczą się wcale: ryzyko kilku sekund bez tarczy akceptuje użytkownik); gracz nadal w pełnym widoku."""
        dx, dy = abs(s["x"] - poz[0]), abs(s["y"] - poz[1])
        if dx > ZASIEG_X or dy > ZASIEG_Y:
            return False
        if self.stanowisko is not None:
            if self.stanowisko.ignoruj(s):
                return False                          # 22.10: NPC w mieście nie wstrzymuje UH
            if s.get("gracz"):
                return self.stanowisko.gracz_blokuje(dx, dy)
        if s.get("gracz"):
            return True
        if walka:
            return int(UH_W_WALCE_DYSTANS) >= 1 and max(dx, dy) <= int(UH_W_WALCE_DYSTANS)
        return max(dx, dy) <= UH_MOB_DYSTANS

    def _uh_walka_ok(self, g):
        """True: tryb UH w walce włączony, a mana prawie pełna (regeneracja by się zmarnowała) i HP wysokie."""
        if not UH_W_WALCE:
            return False
        mana, mx = g.get("mana"), g.get("max_mana")
        if mana is None or not mx:
            return False
        if mana < max(int(UH_KOSZT), int(mx) - int(UH_W_WALCE_MANA_MARGINES)):
            return False
        proc = g.get("proc")
        if proc is None and g.get("hp") is not None and g.get("max_hp"):
            proc = 100.0 * g["hp"] / g["max_hp"]
        return proc is not None and proc >= UH_W_WALCE_MIN_HP

    def _uh_cel_blisko(self, poz, lista):
        """True: aktualny cel walki jest w odległości <= UH_MOB_DYSTANS (albo nie wiadomo, gdzie jest)."""
        c = self.cel
        if c is None:
            return False
        xyz = None
        for s in (lista or []):
            if s.get("id") == c.get("id"):
                xyz = (s["x"], s["y"], s.get("z", poz[2]))
                break
        if xyz is None:
            xyz = c.get("poz")
        if xyz is None:
            return True
        if len(xyz) > 2 and xyz[2] != poz[2]:
            return False
        return max(abs(xyz[0] - poz[0]), abs(xyz[1] - poz[1])) <= UH_MOB_DYSTANS

    def _uh_blokada(self, g, poz, teraz, lista=None):
        """Powód, dla którego UH nie wolno teraz zacząć (stwory w widoku, HP i manę sprawdza uh.mozna_robic)."""
        b = self._czar_blokada()
        if b is not None:
            return str(b)
        if self.ucieczka or self.ostrozny:
            return "ucieczka"
        walka_ok = self._uh_walka_ok(g)
        if walka_ok:
            # Tryb UH_W_WALCE: pościg/pamięć/cel w pobliżu NIE blokują (to właśnie walka). Blokuje stwór przylegający
            # (<= 1 pole: bije w trakcie runy bez tarczy), cel o nieznanym położeniu (nie wiemy, czy przylega)
            # oraz gracz w widoku (sprawdza go potem uh.mozna_robic). Reszta (stan, czary, exhaust, zapas) jak w spokoju.
            for s in (lista or []):
                if s.get("z", poz[2]) != poz[2] or s.get("hp", 100) <= 0 or s.get("gracz"):
                    continue
                if self._uh_widoczny(s, poz, True):
                    return "walka_przylegly"
            c = self.cel
            if int(UH_W_WALCE_DYSTANS) >= 1 and c is not None and c.get("poz") is None \
                    and not any(s.get("id") == c.get("id") for s in (lista or [])):
                return "walka_cel_nieznany"
        else:
            if self.w_poscigu or self.pamiec is not None:
                return "walka"
            if self._uh_cel_blisko(poz, lista):    # cel dalej niż UH_MOB_DYSTANS (i stary stan WALKA) nie blokuje
                return "walka"
        if str(self.stan).startswith(("WYPAD", "POCHODNIA", "LOOT", "JEDZENIE", "GRACZ")):
            return "stan"
        if self.zd_oczekuje is not None or self.jc_oczekuje is not None or self.jz_oczekuje is not None \
                or self.ml_oczekuje is not None:
            return "czar_w_toku"
        if teraz - self.czar_ostatni < CZAR_MIN_PRZERWA_S:
            return "exhaust"
        if self._ml_czeka_na_zapas(g, teraz):      # exevo pan (zapas jedzenia) ma pierwszeństwo
            return "zapas_jedzenia"
        if not walka_ok:
            # zwloki_do_zebrania zdejmuje wpis z listy: tylko sprawdzamy, więc przywracamy listę (inaczej UH gubił zwłoki)
            lista_zw = list(self.zwloki_czekajace)
            zw_jest = self.zwloki_do_zebrania(poz) is not None
            self.zwloki_czekajace = lista_zw
            if zw_jest:
                return "zwloki"                    # najpierw loot (w trybie walki: zwłoki zbierzemy po walce)
        return None

    def _uh_trzyma_mane(self, teraz):
        """True: UH czeka na manę UH_MANA_MIN, więc ML (utevo lux) jej nie zjada. Po UH_HOLD_MAX_S ML znów rzuca."""
        if teraz - self.uh_czeka_ts > 3.0 or self.uh_hold_od is None:
            return False
        return teraz - self.uh_hold_od <= UH_HOLD_MAX_S

    def _uh_tick(self, g, poz, lista, teraz):
        try:
            return self._uh(g, poz, lista, teraz)
        except bot.Zatrzymano:
            raise
        except Exception as e:                    # robienie run nigdy nie wywraca bota
            log(f"[UH] błąd {e!r}")
            return False

    def _uh(self, g, poz, lista, teraz):
        if self.uh_restore is None:
            try:
                self.uh_restore = bool(_UhStan(UH_STAN_PLIK).get("tarcza_id"))
            except Exception:
                self.uh_restore = False
            if self.uh_restore:
                log("[UH] w pliku stanu zapamiętana zdjęta tarcza: przywrócę ją w pierwszym spokoju.")
        if not (UH_AKTYWNY or self.uh_restore) or teraz < self.uh_wylaczony_do:
            self.uh_hold_od = None
            return False
        restore = bool(self.uh_restore)
        if UH_BEZ_DOJSCIA and self.dojscie_aktywne and not restore:
            self.uh_hold_od = None         # dojście na spot: runy dopiero na łowisku (a tarcza zdjęta wraca zawsze)
            return False
        mana = g.get("mana")
        if mana is None:
            return False
        blok = self._uh_blokada(g, poz, teraz, lista)
        if blok is not None:
            self.uh_hold_od = None
            return False
        import uh  # noqa: PLC0415
        if not self.uh_naprawa_ok and not restore and teraz >= self.uh_naprawa_od:
            # raz po starcie bota: slot tarczy pusty, a tarcza znanego ID w plecaku => załóż ("tarcza_naprawa")
            nap = uh.naprawa(self._uh_srodowisko())
            self.aktywnosc_ts = teraz
            if nap.get("wynik") in ("brak_ekwipunku",) or str(nap.get("powod")).startswith(("wolny_start", "brak_odczytu", "brak_zrzutu")):
                self.uh_naprawa_od = teraz + UH_PONOW_BRAK_EKW_S
                log(f"[UH] kontrola tarczy odroczona ({nap.get('powod')}), ponowię za {UH_PONOW_BRAK_EKW_S:.0f} s.")
            else:
                self.uh_naprawa_ok = True
                log(f"[UH] kontrola tarczy na starcie: {nap.get('wynik')} ({nap.get('powod')})")
                if nap.get("alarm"):
                    self.uh_wylaczony_do = self.zegar() + UH_PRZERWA_PO_PORAZKACH_S
                    try:
                        self.alarm(f"UH: {nap.get('powod')} (tarcza może być poza slotem)")
                    except Exception:
                        pass
                    return True
                if nap.get("wynik") == "naprawiono":
                    self.uh_ostatni = self.zegar()
                    self.pauza(0.1, 0.3)
                    return True
        mx = g.get("max_mana")
        mana_min = max(int(UH_KOSZT), min(int(UH_MANA_MIN), int(mx))) if mx else int(UH_MANA_MIN)
        walka = (not restore) and self._uh_walka_ok(g)     # ten sam warunek co w _uh_blokada (g bez zmian)
        widoczne = [s for s in lista if s.get("z") == poz[2] and self._uh_widoczny(s, poz, walka)]
        if walka:
            mana_min = max(int(UH_KOSZT), int(mx) - int(UH_W_WALCE_MANA_MARGINES))
        # 17.10 pet: bez żywego peta UH nie zjada many na kolejne przywołanie (PET_MANA_MIN); z petem UH działa jak dotąd
        if PET_WLACZONY and not restore and (self.pet is None or self.pet.pet_id is None):
            mana_min = max(int(mana_min), int(PET_MANA_MIN) + int(UH_KOSZT))
        if restore:
            ok, powod = uh.mozna_robic(g, widoczne, aktywny=1, min_hp=UH_MIN_HP - 10, mana_min=0,
                                       ja=self.postac.nazwa, teraz=teraz, ostatnia=self.uh_ostatni,
                                       odstep=UH_ODSTEP_S)
        else:
            ok, powod = uh.mozna_robic(g, widoczne, aktywny=1,
                                       min_hp=max(UH_MIN_HP, UH_W_WALCE_MIN_HP) if walka else UH_MIN_HP,
                                       mana_min=mana_min,
                                       ja=self.postac.nazwa, teraz=teraz, ostatnia=self.uh_ostatni,
                                       odstep=UH_ODSTEP_S)
        if not ok:
            if str(powod).startswith("mana"):
                self.uh_czeka_ts = teraz
                if self.uh_hold_od is None:
                    self.uh_hold_od = teraz
            else:
                self.uh_hold_od = None
            return False
        self.uh_hold_od = None
        env = self._uh_srodowisko()
        uh.ustaw(UH_CZAR, klawisz=UH_KLAWISZ, koszt=UH_KOSZT)
        self.uh_ostatni = teraz
        self.uh_przerwal_cavebot = None
        self.aktywnosc_ts = teraz
        self.ustaw_stan("UH", f"{'przywracam tarczę' if restore else 'robię runę ' + UH_CZAR} (mana {mana})")
        log(f"[UH] start ({'restore' if restore else 'run'}, mana {mana}, HP {g.get('proc', 0):.0f}%)")
        self.uh_tryb_walki = walka
        self.uh_hp_start = g.get("proc") if walka else None
        if walka:
            log(f"[UH] runa W WALCE (mana {mana}/{mx}, cel {'tak' if self.cel else 'nie'})")
        try:
            wynik = uh.przywroc(env) if restore else uh.zrob_runa(env)
        finally:
            self.uh_tryb_walki = False
            self.uh_hp_start = None
        t = self.zegar()
        self.uh_ostatni = t
        if not restore:
            self.czar_ostatni = t
        w, pw = wynik.get("wynik"), wynik.get("powod")
        self._ml_tele("uh_run", wynik=w, powod=str(pw), alarm=bool(wynik.get("alarm")),
                      czas_s=wynik.get("czas_s"), rzuty=wynik.get("rzuty"), restore=restore)
        log(f"[UH] wynik {w} ({pw}), {wynik.get('czas_s', 0):.0f} s")
        self.uh_restore = bool(getattr(env, "stan", {}).get("tarcza_id"))
        if wynik.get("alarm"):
            self.uh_wylaczony_do = t + UH_PRZERWA_PO_PORAZKACH_S
            log(f"[UH] ALARM ({pw}): wyłączam UH na {UH_PRZERWA_PO_PORAZKACH_S / 60:.0f} min.")
            try:
                self.alarm(f"UH: {pw} (tarcza może być poza slotem)")
            except Exception:
                pass
        elif w == "ok":
            self.uh_porazki = 0
            if not restore:
                self.uh_runy += wynik.get("rzuty") or 1
        elif w == "brak_ekwipunku" or str(pw).startswith(("wolny_start", "ekwipunek_nieaktualny")):
            # tablica ekwipunku nieczytelna (tuż po relogu; rdzeń szuka jej najwyżej co 20 s) albo wolny rdzeń:
            # nic nie ruszone, krótka pauza i ponowna próba, bez liczenia porażek
            self.uh_wylaczony_do = t + UH_PONOW_BRAK_EKW_S
            log(f"[UH] {pw}: ponowię za {UH_PONOW_BRAK_EKW_S:.0f} s (bez porażki).")
        elif w == "naprawiono":
            self.uh_wylaczony_do = t + 5.0
            log("[UH] tarcza założona z plecaka (tarcza_naprawa), runę zrobię w następnej próbie.")
        elif w == "brak_blank":
            self.uh_wylaczony_do = t + UH_PRZERWA_BRAK_BLANK_S
            log(f"[UH] brak blank run: wyłączam UH na {UH_PRZERWA_BRAK_BLANK_S / 60:.0f} min.")
        elif str(pw).startswith("blank w pojemniku na runy poza oknem"):
            # chwilowe: okno z runami przycięte (otwarte okno zwłok w panelu); to nie awaria mechanizmu, nie liczymy porażki
            self.uh_wylaczony_do = t + 15.0
            log("[UH] blank poza widocznym oknem, ponowię za 15 s (bez porażki).")
        elif str(pw).startswith("brak_zrzutu"):
            # chwilowe: grim nie dał zrzutu (2 próby); to nie awaria mechanizmu UH, nie liczymy porażki
            self.uh_wylaczony_do = t + 15.0
            log("[UH] brak zrzutu ekranu, ponowię za 15 s (bez porażki).")
        elif str(pw).startswith("brak_miejsca w plecaku na tarczę"):
            # chwilowe: brak widocznego wolnego pola na tarczę (plecak z runami zapełniony); nie liczymy porażki
            self.uh_wylaczony_do = t + 60.0
            log("[UH] brak widocznego miejsca na tarczę, ponowię za 60 s (bez porażki).")
        elif self.uh_przerwal_cavebot is None:        # przerwanie nie z naszego callbacku = mechanizm zawiódł
            self.uh_porazki += 1
            log(f"[UH] porażka {self.uh_porazki}/{UH_PORAZKI}")
            if self.uh_porazki >= UH_PORAZKI:
                self.uh_porazki = 0
                self.uh_wylaczony_do = t + UH_PRZERWA_PO_PORAZKACH_S
                log(f"[UH] {UH_PORAZKI} porażki z rzędu: wyłączam UH na {UH_PRZERWA_PO_PORAZKACH_S / 60:.0f} min.")
        self.pauza(0.1, 0.3)
        return True

    def _runa_tick(self, g, poz, lista, teraz):
        """Strzał runą (hotkey RUNA_KLAWISZ) w aktualny cel. Bez many (nie bramkujemy), bez exhaustu czarów.
        Wołane po leczeniu/jedzeniu (te zwracają obieg wcześniej), przed ML i zwykłym meleem. True = obieg zużyty."""
        try:
            return self._runa(g, poz, lista, teraz)
        except bot.Zatrzymano:
            raise
        except Exception as e:                    # strzał runą nigdy nie wywraca bota
            log(f"RUNA: błąd {e!r}")
            return False

    def _runa_odstep(self):
        """Odstęp do następnego strzału runą: RUNA_INTERWAL_S, a przy RUNA_INTERWAL_MAX_S > RUNA_INTERWAL_S losowy z tego
        zakresu, losowany raz po każdym strzale (exhaust run w tym kliencie 17.10: dłuższy niż 3 s, nie dłuższy niż ok. 5 s)."""
        lo = max(float(RUNA_INTERWAL_S), 0.5)
        hi = float(RUNA_INTERWAL_MAX_S)
        if hi <= lo:
            return lo
        if self.runa_los[0] != self.runa_ostatni:
            self.runa_los = (self.runa_ostatni, random.uniform(lo, hi))
        return self.runa_los[1]

    def _runa(self, g, poz, lista, teraz):
        # walka = jest cel (stan bywa chwilowo "ZDROWIE"/"JEDZENIE" po czarze: nie głodzimy wtedy runy)
        if not RUNA_AKTYWNA or self.cel is None or self.ucieczka:
            return False
        if teraz - self.runa_ostatni < self._runa_odstep():
            return False
        cel = next((s for s in lista if s["id"] == self.cel["id"]), None)
        if cel is None or cel.get("z") != poz[2]:
            return False
        hp = cel.get("hp", 100)
        if hp <= 0 or hp < RUNA_MIN_HP_CELU:
            return False
        if self.dystans((cel["x"], cel["y"]), poz) > RUNA_ZASIEG:
            return False
        if self._czar_blokada() is not None:
            return False
        if RUNA_TRYB_KLIK:
            return self._runa_klik(cel, hp, poz, teraz)
        self.runa_ostatni = teraz
        self.runa_strzaly += 1
        self.aktywnosc_ts = teraz
        log(f"[RUNA] strzał {RUNA_KLAWISZ} w {cel['nazwa']} (HP {hp:.0f}%)")
        self.postac.klawisz(RUNA_KLAWISZ)         # hotkey w kliencie, nic nie trafia na czat
        if self.runa_strzaly % RUNA_LOG_CO == 0:
            log(f"RUNA: strzałów {self.runa_strzaly}")
        self.pauza(0.05, 0.15)
        return True

    def _runa_klik(self, cel, hp, poz, teraz):
        """Strzał runą kliknięciami (runa_klik.py). True = obieg zużyty (klikaliśmy). Jedna próba na RUNA_INTERWAL_S,
        po RUNA_KLIK_PORAZKI porażkach z rzędu chłodzenie RUNA_KLIK_CHLODZENIE_S; brak runy: log raz, sprawdzanie rzadko."""
        if teraz < self.runa_klik_do or teraz < self.runa_brak_do:
            return False
        zdjeta = self.uh_restore
        if zdjeta is None:                        # UH jeszcze nie sprawdzał pliku stanu: zrób to sam
            try:
                zdjeta = bool(_UhStan(UH_STAN_PLIK).get("tarcza_id"))
            except Exception:
                zdjeta = False
        if self.ucieczka or self.ostrozny or zdjeta or str(self.stan) == "UH":
            return False                          # UH w toku / tarcza zdjęta: nie klikamy w plecaku
        if abs(cel["x"] - poz[0]) > ZASIEG_X or abs(cel["y"] - poz[1]) > ZASIEG_Y:
            return False
        import runa_klik  # noqa: PLC0415
        if self.runa_klik_env is None:
            self.runa_klik_env = runa_klik.SrodowiskoKlik(self.postac, self.zapytaj,
                                                          log=lambda t: log(t))
        self.runa_ostatni = teraz
        self.aktywnosc_ts = teraz
        wynik = runa_klik.strzel(
            self.runa_klik_env,
            {"id": cel["id"], "dx": cel["x"] - poz[0], "dy": cel["y"] - poz[1], "hp": hp},
            runa_id=int(RUNA_ID), menu_dx=int(RUNA_MENU_DX), menu_dy=int(RUNA_MENU_DY),
            ctrl_cel=bool(RUNA_KLIK_CTRL))
        w, pw = wynik["wynik"], wynik["powod"]
        if w == "brak_runy":
            self.runa_brak_do = teraz + max(float(RUNA_BRAK_SPRAWDZ_S), 5.0)
            if not self.runa_brak_zalogowany:
                self.runa_brak_zalogowany = True
                log(f"[RUNA] {pw}: nie strzelam (sprawdzam co {RUNA_BRAK_SPRAWDZ_S:.0f} s, bez spamu).")
            return False
        self.runa_brak_zalogowany = False
        if w == "ok":
            self.runa_klik_porazki = 0
            self.runa_strzaly += 1
            log(f"[RUNA] strzał klik w {cel['nazwa']} (HP {hp:.0f}%): {pw}")
            if self.runa_strzaly % RUNA_LOG_CO == 0:
                log(f"RUNA: strzałów {self.runa_strzaly}")
        else:
            self.runa_klik_porazki += 1
            log(f"[RUNA] klik bez efektu ({w}: {pw}), porażka {self.runa_klik_porazki}/{RUNA_KLIK_PORAZKI}")
            if self.runa_klik_porazki >= RUNA_KLIK_PORAZKI:
                self.runa_klik_porazki = 0
                self.runa_klik_do = teraz + float(RUNA_KLIK_CHLODZENIE_S)
                log(f"[RUNA] {RUNA_KLIK_PORAZKI} porażki z rzędu: przerwa {RUNA_KLIK_CHLODZENIE_S:.0f} s.")
        self.pauza(0.05, 0.15)
        return True

    def _walka_lub_mob(self, lista, poz):
        return bool(self.cel is not None or self.w_poscigu or self.pamiec is not None
                    or str(self.stan) == "WALKA" or self.zywy_w_poblizu(lista, poz) is not None)

    def _czar_blokada(self):
        """Powód, dla którego klawisza czaru zdrowia/jedzenia nie wolno teraz nacisnąć (albo None).
        Walka, pościg i ucieczka NIE blokują (to jedyny sens leczenia); okno lootu, czat i wypad tak."""
        czat = self.wypad_czat
        if czat is not None and getattr(czat, "zablokowany", False):
            return "czat_zablokowany"
        if self._poscig_przerwanie():
            return "pauza_mozgu"
        if self.w_lootcie or self.lww is not None or self.lww_zalegle is not None:
            return "loot"
        if self.wypad_aktywny and self.zegar() - self.__dict__.get("hp_czeka_ts", float("-inf")) >= 3.0:
            return "wypad"          # 23.10: wyjątek = czekanie na HP przed przejściem pięter (stoimy w miejscu, bez czatu)
        return None

    def _zdrowie_gotowy(self, g, teraz):
        """Czy leczenie exura jest teraz wskazane i możliwe (bez blokad i opóźnienia). Pokrętło/mana/HP/exhaust."""
        if not ZDROWIE_CZAR_AKTYWNY or teraz < self.zd_wylaczony_do or self.zd_oczekuje is not None:
            return False
        mana, proc = g.get("mana"), g.get("proc")
        if mana is None or proc is None or mana < ZDROWIE_CZAR_KOSZT:
            return False
        prog_hp = ZDROWIE_CZAR_HP
        if teraz - self.__dict__.get("hp_czeka_ts", float("-inf")) < 3.0:
            prog_hp = max(prog_hp, HP_PRZED_PIETREM)           # 23.10: czekanie na HP przed piętrem: leczymy do progu czekania
        dolny = self.prog_aktualny
        if proc <= dolny and self._wpadniecie_bez_drogi(self.postac.pozycja()):
            dolny = -1.0                                # 23.10: kieszeń po upadku: UCIECZKA nie działa, więc leczymy także poniżej progu ucieczki
        if not dolny < proc < prog_hp:                  # <= prog ucieczki: ucieczka ma pierwszeństwo
            return False
        if teraz - self.czar_ostatni < CZAR_MIN_PRZERWA_S:
            return False
        return self._czar_blokada() is None

    def _zatrucie_tick(self, g, poz, teraz):
        """23.10 (zgon odchyda/gebelisha, Scorpion): wykryte zatrucie -> exana pox (jeśli klawisz i mana) albo antidote rune na siebie.
        Wykrycie: pole `stany` z pamięci (gdy zmierzone) albo wnioskowanie z HP bez stwora w zwarciu (zatrucie.py). Błąd nigdy nie wywraca bota."""
        if not ZATRUCIE_AKTYWNY:
            return False
        try:
            return self._zatrucie(g, poz, teraz)
        except bot.Zatrzymano:
            raise
        except Exception as e:                    # noqa: BLE001
            log(f"ZATRUCIE: błąd {e!r}")
            return False

    def _zatrucie(self, g, poz, teraz):
        import zatrucie  # noqa: PLC0415
        if self.zatrucie is None:
            self.zatrucie = zatrucie.Zatrucie()
        z = self.zatrucie
        hp = g.get("hp")
        if hp is None:
            return False
        obok = any(not s.get("gracz") and s.get("z") == poz[2] and self.dystans((s["x"], s["y"]), poz) <= 1
                   for s in (self.ostatnie_stwory or ()))
        ogien = bool(self._ogien_aktywny() and self._ogien_xy(poz[2]) and tuple(poz[:2]) in self._ogien_xy(poz[2]))
        zatruty = z.odczyt(teraz, hp, g.get("stany"), stwor_obok=obok, ogien=ogien)
        self.zatruty = zatruty
        if not zatruty or not z.gotowy(teraz):
            if not zatruty and z.ostatnia is not None and teraz - z.ostatnia > zatrucie.PRZERWA_S:
                z.po_probie(z.ostatnia, False)    # zatrucie ustąpiło: zerujemy porażki
            return False
        mana = g.get("mana")
        z.po_probie(teraz, True)
        if ZATRUCIE_CZAR_KLAWISZ and mana is not None and mana >= ZATRUCIE_CZAR_KOSZT:
            log(f"[ZATRUCIE] {z.zrodlo}: exana pox [{ZATRUCIE_CZAR_KLAWISZ}] (hp {g.get('proc', 0):.0f}%, mana {mana})")
            self._ml_tele("zatrucie", wynik="czar", zrodlo=z.zrodlo, hp=hp, mana=mana)
            self.ustaw_stan("ZATRUCIE", "exana pox")
            self.postac.klawisz(ZATRUCIE_CZAR_KLAWISZ)
            self.pauza(0.1, 0.3)
            return True
        if ZATRUCIE_RUNA:
            ops = self.pietra_ops or getattr(getattr(self, "wyprawa", None), "ops", None)
            fn = getattr(ops, "uzyj_antidote", None)
            if fn is None:
                try:
                    import wypad  # noqa: PLC0415
                    ops = self.pietra_ops = wypad.OperacjeZywe(log=lambda t: log(t))
                    fn = ops.uzyj_antidote
                except Exception as e:            # noqa: BLE001
                    log(f"ZATRUCIE: brak operacji na ekranie ({e!r})")
                    return False
            log(f"[ZATRUCIE] {z.zrodlo}: antidote rune na siebie (hp {g.get('proc', 0):.0f}%)")
            self._ml_tele("zatrucie", wynik="runa", zrodlo=z.zrodlo, hp=hp)
            self.ustaw_stan("ZATRUCIE", "antidote rune")
            try:
                fn(tuple(poz))
            except bot.Zatrzymano:
                raise
            except Exception as e:                # noqa: BLE001
                log(f"ZATRUCIE: antidote nie wyszło ({e!r}; brak runy w otwartym plecaku?)")
                self._ml_tele("zatrucie", wynik="blad", blad=repr(e)[:80])
            self.pauza(0.2, 0.5)
            return True
        return False

    def _zdrowie_czar_tick(self, g, poz, teraz):
        try:
            return self._zdrowie_czar(g, poz, teraz)
        except bot.Zatrzymano:
            raise
        except Exception as e:                    # leczenie nigdy nie wywraca bota
            log(f"ZDROWIE: błąd {e!r}")
            return False

    def _zdrowie_czar(self, g, poz, teraz):
        mana = g.get("mana")
        if self.zd_oczekuje is not None and mana is not None \
                and teraz - self.zd_oczekuje[0] >= ZDROWIE_CZAR_WERYFIKACJA_S:
            t0, przed, hp_przed = self.zd_oczekuje
            self.zd_oczekuje = None
            if mana < przed or g.get("hp") != hp_przed:
                self.zd_porazki = 0
                self.zd_rzuty += 1
                self._ml_tele("zdrowie_czar", wynik="ok", mana_przed=przed, mana_po=mana,
                              hp_przed=hp_przed, hp_po=g.get("hp"))
            else:
                self.zd_porazki += 1
                self._ml_tele("zdrowie_czar", wynik="brak_zmiany", mana_przed=przed, mana_po=mana,
                              porazki=self.zd_porazki)
                log(f"ZDROWIE: po rzucie ani HP, ani mana się nie zmieniły ({przed} -> {mana}), "
                    f"porażka {self.zd_porazki}/{ZDROWIE_CZAR_PORAZKI}.")
                if self.zd_porazki >= ZDROWIE_CZAR_PORAZKI:
                    self.zd_porazki = 0
                    self.zd_wylaczony_do = teraz + ZDROWIE_CZAR_PRZERWA_PO_PORAZKACH_S
                    log(f"ZDROWIE: czar '{ZDROWIE_CZAR_TEKST}' nie działa ({ZDROWIE_CZAR_PORAZKI}x bez efektu, "
                        f"zły hotkey {ZDROWIE_CZAR_KLAWISZ}/brak czaru?), wyłączam leczenie na "
                        f"{ZDROWIE_CZAR_PRZERWA_PO_PORAZKACH_S / 60:.0f} min.")
                    self._ml_tele("zdrowie_czar_wylaczony", na_s=ZDROWIE_CZAR_PRZERWA_PO_PORAZKACH_S,
                                  tekst=ZDROWIE_CZAR_TEKST)
        if not self._zdrowie_gotowy(g, teraz):
            return False
        # losowe opóźnienie tuż przed rzutem (bez regularności); krótkie, więc blokujemy obieg
        self.spij(random.uniform(*ZDROWIE_CZAR_OPOZNIENIE))
        bot.sprawdz_stop()
        teraz = self.zegar()
        self.czar_ostatni = teraz
        self.zd_oczekuje = (teraz, mana, g.get("hp"))
        self.zdrowie_rzut_ts = teraz
        self.aktywnosc_ts = teraz
        self.ustaw_stan("ZDROWIE", f"czar {ZDROWIE_CZAR_TEKST} [{ZDROWIE_CZAR_KLAWISZ}] (hp {g['proc']:.0f}%, mana {mana})")
        log(f"[ZDROWIE] {ZDROWIE_CZAR_TEKST} [{ZDROWIE_CZAR_KLAWISZ}] (hp {g['proc']:.0f}%, mana {mana})")
        self._ml_tele("zdrowie_czar", wynik="rzut", hp_proc=round(g["proc"], 1), mana=mana,
                      klawisz=ZDROWIE_CZAR_KLAWISZ)
        self.postac.klawisz(ZDROWIE_CZAR_KLAWISZ)   # hotkey w kliencie, nic nie trafia na czat
        self.pauza(0.1, 0.3)
        return True

    # --- jedzenie czarem exevo pan ---
    def jedzenie_znane_brak(self, teraz):
        """Wiemy, że w plecaku nie ma jedzenia: nieudana próba jedzenia albo odczyt plecaka przez wypad.py."""
        if JEDZENIE_BRAK_WALIDUJ and self.jedzenie_odczyt_watpliwy(teraz):
            return False
        if teraz < self.jedzenie_nie_do:
            return True
        w = self.jedzenie_plecak
        return bool(w is not None and w[1] == 0 and teraz - w[0] <= JEDZENIE_CZAR_PLECAK_WAZNE_S)

    def jedzenie_odczyt_watpliwy(self, teraz):
        """True: ostatnia nieudana próba jedzenia nastąpiła przy nieczytelnych kontenerach (brak otwartych
        kontenerów w pamięci), więc nie wiemy, czy w plecaku jest jedzenie."""
        return bool(JEDZENIE_BRAK_WALIDUJ and teraz < self.jedzenie_nieczytelne_do)

    def _kontenery_czytelne_po_porazce(self):
        """Po nieudanym jedzeniu: czy pamięć widzi plecak? Do JEDZENIE_BRAK_PROBY odczytów (tylko odczyt,
        bez inputu do gry); najpierw próba otwarcia plecaka, jeśli loot ma taką funkcję."""
        fn = getattr(self.loot, "ile_jedzenia", None)
        if not callable(fn):
            return True                              # brak odczytu własnego: nie podważamy wyniku zjedz
        otworz = getattr(self.loot, "otworz_plecak", None)
        for i in range(max(1, int(JEDZENIE_BRAK_PROBY))):
            try:
                if i > 0 and callable(otworz):
                    otworz()
                if fn() is not None:
                    return True
            except bot.Zatrzymano:
                raise
            except Exception:
                pass
            self.spij(0.3)
        return False

    def jedzenie_czar_zastepuje_wypad(self, g, teraz):
        """True: czar jedzenia jest włączony i mana wystarcza, więc wypad po jedzenie nie startuje."""
        mana = g.get("mana") if g else None
        return bool(JEDZENIE_CZAR_AKTYWNY and teraz >= self.jc_wylaczony_do
                    and mana is not None and mana >= JEDZENIE_CZAR_KOSZT)

    def _jedzenie_czar_tick(self, g, poz, teraz, odswiez=False):
        try:
            return self._jedzenie_czar(g, poz, teraz, odswiez)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"JEDZENIE-CZAR: błąd {e!r}")
            return False

    def _jc_koniec(self, ok, powod, teraz):
        if ok:
            self.jc_porazki = 0
            return
        self.jc_porazki += 1
        log(f"JEDZENIE-CZAR: bez efektu ({powod}), porażka {self.jc_porazki}/{JEDZENIE_CZAR_PORAZKI}.")
        if self.jc_porazki >= JEDZENIE_CZAR_PORAZKI:
            self.jc_porazki = 0
            self.jc_wylaczony_do = teraz + JEDZENIE_CZAR_PRZERWA_PO_PORAZKACH_S
            log(f"JEDZENIE-CZAR: czar '{JEDZENIE_CZAR_TEKST}' nie daje jedzenia ({JEDZENIE_CZAR_PORAZKI}x), "
                f"wyłączam na {JEDZENIE_CZAR_PRZERWA_PO_PORAZKACH_S / 60:.0f} min.")
            self._ml_tele("jedzenie_czar_wylaczony", na_s=JEDZENIE_CZAR_PRZERWA_PO_PORAZKACH_S,
                          tekst=JEDZENIE_CZAR_TEKST)

    # --- zapas jedzenia: liczenie sztuk w plecaku i polityka rzutu F3 ---
    def _zapas_jedzenia(self, teraz, wymus=False):
        """Sztuk jedzenia w plecaku (odczyt z pamięci gry, cache JEDZENIE_ZAPAS_ODCZYT_S) albo None = nieznane."""
        o = self.jz_odczyt
        if o is not None and not wymus and teraz - o[0] < JEDZENIE_ZAPAS_ODCZYT_S:
            return o[1]
        ile = None
        fn = getattr(self.loot, "ile_jedzenia", None)
        if callable(fn):
            try:
                ile = fn()
            except bot.Zatrzymano:
                raise
            except Exception:
                ile = None
        if ile is None:                            # zapasowo: świeży odczyt plecaka z wypad.py
            w = self.jedzenie_plecak
            if w is not None and w[1] is not None and teraz - w[0] <= 3 * JEDZENIE_ZAPAS_ODCZYT_S:
                ile = w[1]
        self.jz_odczyt = (teraz, ile)
        return ile

    def _f3_wolny(self, teraz):
        """F3 na zapas nie jest wstrzymany (pokrętło, pauza po porażkach, czar jedzenia wyłączony)."""
        return bool(JEDZENIE_CZAR_AKTYWNY and teraz >= self.jz_wylaczony_do and teraz >= self.jc_wylaczony_do)

    def _ml_czeka_na_zapas(self, g, teraz):
        """True: F3 wolny, zapas jedzenia znany i < MIN: ML poczeka na rzut F3 (12.10: także przy mana >= 30,
        inaczej ML zjadał manę 30 przed F3 i bot głodował). Przy mana < 30 czeka tylko, gdy mana rośnie
        (głód: nie urośnie, wtedy F3 i tak się nie odbędzie). Po JEDZENIE_ZAPAS_HOLD_MAX_S ML znów rzuca
        (bez zakleszczenia), więc F3 zablokowany na stałe nie wyłącza ML na zawsze."""
        mana = g.get("mana")
        if not self._f3_wolny(teraz) or mana is None:
            self.jz_hold_od = None
            return False
        zapas = self._zapas_jedzenia(teraz)
        if zapas is None or zapas >= JEDZENIE_ZAPAS_MIN \
                or (mana < JEDZENIE_CZAR_KOSZT and teraz - self.mana_rosla >= JEDZENIE_ZAPAS_REGEN_S):
            self.jz_hold_od = None
            return False
        if self.jz_hold_od is None:
            self.jz_hold_od = teraz
        if teraz - self.jz_hold_od > JEDZENIE_ZAPAS_HOLD_MAX_S:
            return False
        return True

    def _zapas_nieznany_f3(self, g, mana, teraz):
        """ML i tak miałby rzucić, a plecak jest nieczytelny: raz na JEDZENIE_ZAPAS_NIEZNANY_CO_S rzuć F3 zamiast F1."""
        if not self._f3_wolny(teraz) or mana is None or mana < JEDZENIE_CZAR_KOSZT:
            return False
        if self._zapas_jedzenia(teraz) is not None:
            return False
        if teraz - self.jz_nieznany_ostatni < JEDZENIE_ZAPAS_NIEZNANY_CO_S or self.jz_oczekuje is not None \
                or self.jc_oczekuje is not None or teraz - self.czar_ostatni < JEDZENIE_ZAPAS_EXHAUST_S:
            return False
        self.jz_nieznany_ostatni = teraz
        self._f3_zapas_rzut(g, teraz, mana, None, "nieznany")
        return True

    def _f3_zapas_rzut(self, g, teraz, mana, zapas, powod):
        self.jz_ostatni = teraz
        self.czar_ostatni = teraz
        self.ml_ostatni = teraz                    # wspólny exhaust: ML nie rzuca zaraz po F3
        self.jz_oczekuje = (teraz, mana, zapas)
        self.jz_hold_od = None
        self.aktywnosc_ts = teraz
        self.ustaw_stan("JEDZENIE", f"zapas: czar {JEDZENIE_CZAR_TEKST} [{JEDZENIE_CZAR_KLAWISZ}] ({self._stan_many(g)})")
        log(f"[JEDZENIE] zapas {JEDZENIE_CZAR_TEKST} [{JEDZENIE_CZAR_KLAWISZ}] (mana {mana}, "
            f"zapas {'?' if zapas is None else zapas}/{JEDZENIE_ZAPAS_MIN}, {powod})")
        self._ml_tele("jedzenie_zapas", wynik="rzut", mana=mana, zapas=zapas, min=JEDZENIE_ZAPAS_MIN, powod=powod,
                      klawisz=JEDZENIE_CZAR_KLAWISZ)
        self.postac.klawisz(JEDZENIE_CZAR_KLAWISZ)
        self.pauza(0.2, 0.5)

    def _jz_weryfikacja(self, g, teraz):
        """Po rzucie F3 na zapas: czy sztuk przybyło. True = obieg zużyty (odczyt), False = jeszcze czekamy/nic."""
        t0, przed, zapas_przed = self.jz_oczekuje
        if teraz - t0 < JEDZENIE_CZAR_CZEKAJ_S:
            return False
        self.jz_oczekuje = None
        mana = g.get("mana")
        po = self._zapas_jedzenia(teraz, wymus=True)
        spadek = mana is not None and mana < przed
        if zapas_przed is not None and po is not None:
            ok = po > zapas_przed
        else:
            ok = spadek                            # plecak nieczytelny: sam spadek many
        self._ml_tele("jedzenie_zapas", wynik="ok" if ok else "brak_przyrostu", mana_przed=przed, mana_po=mana,
                      zapas_przed=zapas_przed, zapas_po=po)
        if ok:
            self.jz_porazki = 0
            log(f"JEDZENIE-ZAPAS: przybyło ({'?' if zapas_przed is None else zapas_przed} -> "
                f"{'?' if po is None else po}, mana {przed} -> {mana}).")
        else:
            self.jz_porazki += 1
            log(f"JEDZENIE-ZAPAS: bez przyrostu ({zapas_przed} -> {po}, mana {przed} -> {mana}), "
                f"porażka {self.jz_porazki}/{JEDZENIE_ZAPAS_PORAZKI}.")
            if self.jz_porazki >= JEDZENIE_ZAPAS_PORAZKI:
                self.jz_porazki = 0
                self.jz_wylaczony_do = teraz + JEDZENIE_ZAPAS_PAUZA_S
                log(f"JEDZENIE-ZAPAS: czar '{JEDZENIE_CZAR_TEKST}' nie zwiększa zapasu ({JEDZENIE_ZAPAS_PORAZKI}x), "
                    f"pauza {JEDZENIE_ZAPAS_PAUZA_S / 60:.0f} min.")
                self._ml_tele("jedzenie_zapas_wylaczony", na_s=JEDZENIE_ZAPAS_PAUZA_S, tekst=JEDZENIE_CZAR_TEKST)
        return True

    def _jedzenie_czar(self, g, poz, teraz, odswiez=False):
        mana = g.get("mana")
        # 2. krok: po rzucie i odczekaniu jemy powstałe jedzenie (plecak/ziemia albo klawisz jedzenia)
        if self.jz_oczekuje is not None:
            return self._jz_weryfikacja(g, teraz)
        if self.jc_oczekuje is not None:
            t0, przed = self.jc_oczekuje
            if teraz - t0 < JEDZENIE_CZAR_CZEKAJ_S:
                return False
            if poz is not None and self.mob_blisko(poz, JEDZENIE_SPOKOJ) and teraz - t0 < 20.0:
                return False                      # ktoś podszedł: jedzenie to kilka s ślepego bloku, czekamy
            self.jc_oczekuje = None
            spadek = mana is not None and mana < przed
            self.jedzenie_nie_do = float("-inf")  # po czarze plecak ma jedzenie: wolno próbować
            self.jedzenie_plecak = None
            self.zjedz(teraz, g)
            zjedzono = not (self.jedzenie_nie_do > teraz) if not self.jedzenie else True
            self._ml_tele("jedzenie_czar", wynik="ok" if (spadek and zjedzono) else "brak_efektu",
                          mana_przed=przed, mana_po=mana, zjedzono=int(bool(zjedzono)))
            if spadek and zjedzono:
                log(f"JEDZENIE-CZAR: powstało i zjedzono (mana {przed} -> {mana}).")
                self.jedzenie_nie_do = float("-inf")
            self._jc_koniec(spadek and zjedzono, "mana nie spadła" if not spadek else "brak jedzenia po czarze", teraz)
            return True
        if not JEDZENIE_CZAR_AKTYWNY or mana is None:
            return False
        glod_hp = g["hp"] < g["max_hp"] and teraz - self.hp_wzrost >= CZAS_JEDZENIA
        glod_mana = None if glod_hp else self.mana_nie_rosnie_s(g, teraz)
        glod = glod_hp or glod_mana is not None
        zapas = self._zapas_jedzenia(teraz)
        brak_znany = self.jedzenie_znane_brak(teraz) or zapas == 0
        if glod and brak_znany and teraz >= self.jc_wylaczony_do:
            tryb = "glod"                         # głodny, w plecaku nic: exevo pan, potem zjedzenie (jak dawniej)
        elif glod and zapas is not None and zapas > 0 and not brak_znany:
            return False                          # głodny i jest jedzenie: najpierw jemy (jedzenie_potrzebne)
        elif not glod and zapas is not None and zapas < JEDZENIE_ZAPAS_MIN and teraz >= self.jz_wylaczony_do:
            tryb = "zapas"                        # niegłodny, ale zapas poniżej progu: uzupełniamy
        else:
            return False
        if mana < JEDZENIE_CZAR_KOSZT:
            # exevo pan nie wystartuje: NIC nie blokujemy (ML rzuca dalej), tylko notatka do telemetrii
            if glod and teraz - self.jz_notatka_ost >= JEDZENIE_ZAPAS_NOTATKA_S:
                self.jz_notatka_ost = teraz
                self._ml_tele("jedzenie_czar", wynik="brak_many", mana=mana, koszt=JEDZENIE_CZAR_KOSZT,
                              zapas=zapas, glod="hp" if glod_hp else "mana")
            return False
        if tryb == "zapas":
            pauza = max(self.jz_ostatni, self.jc_ostatni)
            cooldown = teraz - pauza < JEDZENIE_ZAPAS_CO_S or teraz - self.czar_ostatni < JEDZENIE_ZAPAS_EXHAUST_S
        else:
            cooldown = teraz - self.jc_ostatni < JEDZENIE_CZAR_CO_S or teraz - self.czar_ostatni < CZAR_MIN_PRZERWA_S
        cooldown = cooldown or self.zd_oczekuje is not None
        if self._czar_blokada() is not None:
            return False
        if odswiez:
            try:
                self.ostatnie_stwory = self.stwory()
            except bot.Zatrzymano:
                raise
            except Exception:
                pass
        if poz is not None and self.mob_blisko(poz, JEDZENIE_SPOKOJ):
            # 12.10: F3 na zapas to zwykły czar (bez bloku, tylko exhaust): w ciągłej walce nie czeka na spokój, o ile
            # nie ma ucieczki ani HP w zakresie leczenia exura (inaczej bot w stałej walce głodował do końca)
            w_walce_ok = tryb == "zapas" and JEDZENIE_ZAPAS_W_WALCE and not self.ucieczka \
                and (not ZDROWIE_CZAR_AKTYWNY or g.get("proc", 100.0) >= ZDROWIE_CZAR_HP)
            if not w_walce_ok:
                return False
        # priorytet exura > exevo pan: nie zjadamy many, której exura będzie potrzebować za chwilę
        if ZDROWIE_CZAR_AKTYWNY and g.get("proc", 100.0) < ZDROWIE_CZAR_HP \
                and mana - JEDZENIE_CZAR_KOSZT < ZDROWIE_CZAR_KOSZT:
            return False
        if cooldown:
            self.jc_glod_do = teraz + 5.0         # F3 za chwilę (exhaust/odstęp): ML nie zjada many 30
            return False
        if tryb == "zapas":
            self._f3_zapas_rzut(g, teraz, mana, zapas, "zapas<min")
            return True
        self.jc_ostatni = teraz
        self.czar_ostatni = teraz
        self.jc_oczekuje = (teraz, mana)
        self.aktywnosc_ts = teraz
        self.ustaw_stan("JEDZENIE", f"czar {JEDZENIE_CZAR_TEKST} [{JEDZENIE_CZAR_KLAWISZ}] ({self._stan_many(g)})")
        log(f"[JEDZENIE] {JEDZENIE_CZAR_TEKST} [{JEDZENIE_CZAR_KLAWISZ}] (mana {mana}, "
            f"{'głód HP' if glod_hp else 'brak regeneracji many'})")
        self._ml_tele("jedzenie_czar", wynik="rzut", mana=mana, glod="hp" if glod_hp else "mana",
                      klawisz=JEDZENIE_CZAR_KLAWISZ)
        self.postac.klawisz(JEDZENIE_CZAR_KLAWISZ)
        self.pauza(0.2, 0.5)
        return True

    def _ruch_powod(self, poz, teraz):
        """R0b: przyczyna stania w odstępie przed tym obiegiem, z gotowego stanu bota (bez RPC)."""
        stan = str(self.stan)
        if teraz - self.ruch_pietra_t < 2.0:
            return "schody"
        if teraz - self.ogien_krok_t < 2.0:
            return "ogien"
        if self.tele is not None and getattr(self.tele, "utknieto", False):
            return "utkniecie"
        if stan == "WALKA" or self.cel is not None:
            return "walka"
        if stan == "LOOT":
            return "loot"
        p = self.patrol
        if isinstance(p, dict) and p.get("faza") == "postoj":
            return "patrol_postoj"
        return "inne"

    def _ruch_tick(self, poz, teraz):
        """R0b: wołane na początku obiegu, przed wczesnymi return True; tylko arytmetyka, bez RPC."""
        if not RUCH_OKNO or self.tele is None:
            return
        try:
            self.tele.ruch_tick(teraz, poz, self.stan, self._ruch_powod(poz, teraz), self.ruch_kliki, self.ruch_strzalki)
        except Exception as e:
            log(f"debug: ruch_okno błąd {e!r}")

    def _tele_wczesny(self, g, poz, powod):
        """R0b: próbka telemetrii przed wczesnym return True w tick (postoje nie znikają między próbkami co 1,2 s).
        Bez nowych RPC i bez A*: lista stworów z poprzedniego obiegu, najwyżej raz na sekundę."""
        if not RUCH_PROBKA_WCZESNA or self.tele is None:
            return
        try:
            self.tele.probka(self, g, poz, self.ostatnie_stwory or [], wczesna=powod)
        except Exception as e:
            log(f"debug: telemetria (wczesna) błąd {e!r}")

    def _tele_tick(self, g, poz, lista):
        try:
            if self.pokretla and self.zegar() - self.pokretla_ost >= POKRETLA_CO:
                self.pokretla_ost = self.zegar()
                self.pokretla.odswiez()
            if self.tele:
                if getattr(self, "podsumowanie", None):
                    self.podsumowanie.tick(self.tele, dict(g, ml_aktywny=int(bool(ML_CZAR_AKTYWNY)),
                                                           ml_rzuty=self.ml_rzuty))
                r = self.tele.probka(self, g, poz, lista)
                if r and (r["stwory"] or os.environ.get("CAVEBOT_DEBUG")):
                    import telemetria  # noqa: PLC0415
                    log(telemetria.linia_stworow(r))
        except Exception as e:
            log(f"debug: telemetria błąd {e!r}")

    @staticmethod
    def _wczytaj_znane():
        znane = set()
        pliki = sorted(KATALOG_TRAS.glob("*.json")) if KATALOG_TRAS.is_dir() else []
        for plik in pliki + [PLIK_ZNANYCH]:
            try:
                dane = json.loads(plik.read_text())
            except (OSError, ValueError):
                continue
            if not isinstance(dane, list):
                continue
            for p in dane:
                if isinstance(p, (list, tuple)) and len(p) == 3 and all(isinstance(v, int) for v in p):
                    znane.add(tuple(p))
        return znane

    @staticmethod
    def _wczytaj_mape():
        """Wspólna pełna mapa (mapa.mapa()); None, gdy pliku mapy nie ma albo jest uszkodzony."""
        try:
            import mapa  # noqa: PLC0415
            return mapa.mapa()
        except Exception as e:  # uszkodzony plik nie może zatrzymać bota: jedziemy na znanych polach
            log(f"Pełna mapa niedostępna ({e}), drogi tylko po znanych polach.")
            return None

    def zapamietaj_pole(self, poz):
        """Pozycja gracza = pole, po którym da się chodzić. Na żywo co ZNANE_ZAPIS_CO s zapis do pliku."""
        poz = tuple(poz)
        if WPADNIECIE_POSCIG and WPADNIECIE and self.wpadniecie:
            try:
                self.wpadniecie.w_petli(poz, self.zegar())      # 20.10: pętla pościgu/lootu nie wraca do ticka, a ostatnia próbka musi być świeża
            except Exception as e:
                log(f"debug: wpadniecie.w_petli błąd {e!r}")
        if poz not in self.znane:
            self.znane.add(poz)
            self.znane_nowe += 1
            if self._klucze_n == len(self.znane) - 1:   # pamięć podręczna aktualna: dopisz bez przebudowy
                self._klucze.setdefault(poz[2], set()).add(poz[0] * _K + poz[1])
                self._klucze_n += 1
        if self.zapis_znanych and self.znane_nowe and self.zegar() - self.znane_zapis > ZNANE_ZAPIS_CO:
            self.znane_zapis = self.zegar()
            try:
                tmp = PLIK_ZNANYCH.with_suffix(f".tmp{instancja.ID and '.' + instancja.ID}")
                tmp.write_text(json.dumps(sorted(self.znane)))
                tmp.replace(PLIK_ZNANYCH)
                self.znane_nowe = 0
            except OSError as e:
                log(f"Nie zapisałem znanych pól: {e}")

    def _pola_pietra(self, z):
        """Znane pola piętra z jako liczby x*_K + y (szybki BFS). Przebudowa, gdy self.znane urosło."""
        if self._klucze_n != len(self.znane):
            self._klucze = {}
            for x, y, pz in self.znane:
                self._klucze.setdefault(pz, set()).add(x * _K + y)
            self._klucze_n = len(self.znane)
        return self._klucze.get(z, set())

    def mapa_zna(self, start, cel):
        """Pełna mapa zna start i cel (pole widziane na minimapie albo takie, na którym stał gracz),
        więc jej droga jest prawdziwa."""
        if self.mapa is None:
            return False
        z = start[2]
        for x, y in ((start[0], start[1]), (cel[0], cel[1])):
            if not self.mapa.flagi(x, y, z) & 1 and (x, y, z) not in self.znane:
                return False
        return True

    def sciana(self, pole):
        """Pole nauczone jako ściana (krok strzałką się nie udał). Gdy pełna mapa mówi, że da się
        tam wejść, nauka wygasa po SCIANA_WAZNA s (to był raczej stwór, gracz albo zamknięte drzwi)."""
        t = self.sciany.get(pole)
        if t is None:
            return False
        do = self.__dict__.get("sciany_do", {}).get(pole)
        if do is not None:                  # KROK_ZLY: zakaz na czas, niezależnie od mapy
            if self.zegar() < do:
                return True
            del self.sciany_do[pole]
            del self.sciany[pole]
            return False
        if self.mapa is not None and self.zegar() - t > SCIANA_WAZNA and self.mapa.przechodnie(*pole):
            del self.sciany[pole]
            return False
        return True

    def _krok_zly_zapis(self, pole, k):
        """KROK_ZLY: nieudany krok strzałką `k` w `pole` (bez stwora na polu). KROK_ZLY_N nieudanych z rzędu (starsze niż
        KROK_ZLY_OKNO_S nie liczą się) = zakaz wejścia na pole: KROK_ZLY_S s (kolejne zakazy x2, maks KROK_ZLY_MAX_S),
        a gdy mapa uznaje pole za ścianę KROK_ZLY_SCIANA_S s. Zakaz trafia do `sciany`, więc widzą go droga, skos i patrol.
        -> True, gdy zakaz został nałożony."""
        kz = self.__dict__.setdefault("krok_zly", {})
        teraz = self.zegar()
        w = kz.get(pole)
        if w is None or teraz - w[1] > KROK_ZLY_OKNO_S:
            # stare nieudane próby się nie sumują; poprzednie zakazy (eskalacja) pamiętamy 2 x KROK_ZLY_MAX_S
            w = [0, teraz, w[2] if w is not None and teraz - w[1] <= 2 * KROK_ZLY_MAX_S else 0]
        w[0] += 1
        w[1] = teraz
        kz[pole] = w
        if w[0] < (1 if w[2] > 0 else KROK_ZLY_N):      # po zakazie jedna nieudana próba po jego wygaśnięciu = kolejny, dłuższy
            return False
        if self._krok_sciana_mapy(pole):
            czas = KROK_ZLY_SCIANA_S
        elif self.dojscie_aktywne and KROK_ZLY_DOJSCIE_S > 0:
            # 23.10 (geblish, korytarz thais_pn_z9 z8, 1 pole szerokości): dojście to jedna droga bez obejścia, a zakaz jedynego
            # przechodniego pola na 45 s zawiesza je do D3 (14:08-14:09). Pole przechodnie wg mapy dostaje tu krótki zakaz.
            czas = min(KROK_ZLY_DOJSCIE_S * (2 ** w[2]), 4 * KROK_ZLY_DOJSCIE_S, KROK_ZLY_MAX_S)
        else:
            czas = min(KROK_ZLY_S * (2 ** w[2]), KROK_ZLY_MAX_S)
        w[0], w[2] = 0, w[2] + 1
        self.__dict__.setdefault("sciany_do", {})[pole] = teraz + czas
        self.sciany[pole] = teraz
        self.__dict__["krok_zly_blok"] = True
        log(f"[KROK_ZLY] {w[2]}. zakaz wejścia na {pole[:2]} na {czas:.0f} s: krok {k} nie ruszył {KROK_ZLY_N}x z rzędu "
            f"(mapa przechodnie {self.mapa.przechodnie(*pole) if self.mapa else '?'})")
        return True

    def _krok_zly_ok(self, pole):
        """KROK_ZLY: udane wejście na pole kasuje licznik nieudanych (zakaz też, o ile jeszcze trwał)."""
        self.__dict__.setdefault("krok_zly", {}).pop(pole, None)
        if pole in self.__dict__.get("sciany_do", {}):
            del self.sciany_do[pole]
            self.sciany.pop(pole, None)

    def sprawdz_krok(self, poz, zajete, cel):
        """Wynik ostatniej strzałki: postać KROK_SCIANA s po niej stoi na tym samym polu = ściana na
        polu docelowym (chyba że stał tam stwór albo cel). True = krok może jeszcze trwać."""
        if self.krok_prosto_ost is None:
            return False
        skad, dokad, czas = self.krok_prosto_ost
        if tuple(poz) != skad:
            self.krok_prosto_ost = None
            return False
        if self.zegar() - czas < max(KROK_SCIANA, POSCIG_BRAK_WSPOL * self._czas_kroku(skad)):
            return True
        self.krok_prosto_ost = None
        if dokad[:2] in {tuple(p[:2]) for p in zajete} | {tuple(cel[:2])}:
            return False
        widziany = self.stwory_pola.get(tuple(dokad[:2]))
        if widziany is not None and self.zegar() - widziany <= SCIANA_STWOR:
            return False   # stwór dopiero co tam stał (i poszedł): to on blokował, nie ściana
        self.sciany[dokad] = self.zegar()
        return False

    def odnotuj_stwory(self, lista, poz):
        """Pola, na których stoją stwory (bez nas) - sprawdz_krok nie uczy ściany na świeżo
        opuszczonym przez stwora polu."""
        t = self.zegar()
        for s in lista:
            if s["z"] == poz[2] and s.get("hp", 100) > 0 \
                    and not (s.get("gracz") and s.get("nazwa") == self.postac.nazwa):
                self.stwory_pola[(s["x"], s["y"])] = t
        for p in [p for p, c in self.stwory_pola.items() if t - c > 5 * SCIANA_STWOR]:
            del self.stwory_pola[p]

    # --- pola ognia (ogien.py) ---

    @staticmethod
    def _ogien_odczyt_domyslny():
        """Zbiór (dx, dy) pól ognia względem gracza z świeżego zrzutu (grim ppm, tylko odczyt) albo None
        (po ciemku nie wiadomo)."""
        import ekran  # noqa: PLC0415
        import ogien  # noqa: PLC0415
        obraz = ogien.zrzut_ppm(ekran.SESJA.read_text().strip())
        ekran._zauwaz_rozmiar(obraz.size)                  # log zmiany rozmiaru ekranu (okno podglądu zmienia go w locie)
        prostokat = ekran._cache_mapy.get(obraz.size)      # cache prostokąta mapy po rozmiarze (bez zapytania do X)
        if prostokat is None:
            prostokat = ekran.aktualny_prostokat()
            if obraz.size not in ekran._cache_mapy:
                obraz = obraz.resize(ekran._rozmiar_ekranu())
        if ekran.jasnosc_mapy(obraz, prostokat) < ekran.PROG_CIEMNOSCI:
            return None
        return ogien.pola_ognia(obraz, prostokat)

    def _ogien_aktywny(self):
        """Czy w ogóle liczymy się z ogniem: pokrętło włączone, jakieś pole znane, nie trwa ignorowanie."""
        return bool(OGIEN_UNIKAJ and self.ogien_pola and self.zegar() >= self.ogien_ignoruj_do)

    def _ogien_stale_ef(self):
        """Pola stałe obowiązujące teraz (pusty zbiór, gdy maska wyłączona pokrętłem OGIEN_STALY=0)."""
        baza = self.ogien_stale if OGIEN_STALY else frozenset()
        if OGIEN_MASKA_DANE and self.ogien_dane_maska:
            return set(baza) | self.ogien_dane_maska     # maska danych (epizody): jak pola stałe, nie blokuje drogi ani kliku
        return baza

    def _ogien_xy(self, z, bez_stalych=False):
        """Zbiór (x, y) pól ognia na piętrze z (pusty, gdy ogień nie obowiązuje). bez_stalych=True: bez pól stałych
        (droga, A*, klik); ze stałymi: zejście z ognia i zwłoki na ogniu (bezpieczeństwo)."""
        if not self._ogien_aktywny():
            return set()
        st = self._ogien_stale_ef() if bez_stalych else ()
        return {(x, y) for (x, y, pz) in self.ogien_pola if pz == z and (x, y, pz) not in st}

    def _ogien_pole_sciana(self, p):
        """R1a: czy mapa uznaje pole za ścianę/niechodliwe (flaga 4 albo przechodnie == False). Brak mapy: False."""
        if self.mapa is None:
            return False
        try:
            return bool(self.mapa.flagi(*p) & 4) or self.mapa.przechodnie(*p) is False
        except Exception:
            return False

    def _ogien_stale_wczytaj(self):
        """R1a: zasiew maski z trasy/ogien_stale.json (przy pokrętle tylko ściany: tylko pola, które mapa uznaje za ścianę)."""
        if PLIK_OGIEN_STALE is None:
            return
        try:
            dane = json.loads(Path(PLIK_OGIEN_STALE).read_text())
            for x, y, z in dane.get("pola", []):
                p = (int(x), int(y), int(z))
                if not OGIEN_MASKA_TYLKO_SCIANY or self._ogien_pole_sciana(p):
                    self.ogien_stale.add(p)
        except FileNotFoundError:
            pass
        except Exception as e:
            log(f"[OGIEN] nie wczytam maski stałych pól: {e!r}")

    def _ogien_stale_zapisz(self):
        """R1a: zapis maski po każdej zmianie (atomowo); błąd zapisu nie zatrzymuje bota."""
        if PLIK_OGIEN_STALE is None:
            return
        try:
            cel = Path(PLIK_OGIEN_STALE)
            tmp = cel.with_suffix(".tmp")
            tmp.write_text(json.dumps({"opis": "pola ognia stale (sciany wg mapy), zapis bota",
                                       "pola": sorted([x, y, z] for x, y, z in self.ogien_stale)}, indent=0))
            tmp.replace(cel)
        except Exception as e:
            log(f"[OGIEN] nie zapiszę maski stałych pól: {e!r}")

    def _ogien_stale_aktualizuj(self, widziane, teraz):
        """P6: liczy wykrycia pól; pole widziane >= OGIEN_STALY_N razy w ciągu >= OGIEN_STALY_S, albo będące
        ścianą mapy (flaga 4), trafia do ogien_stale. Wpisy nie widziane od OGIEN_STALY_S są zapominane."""
        przed = len(self.ogien_stale)
        for p in widziane:
            w = self.ogien_widz.get(p)
            if w is None:
                w = self.ogien_widz[p] = [0, teraz, teraz]
                if p not in self.ogien_stale and self._ogien_pole_sciana(p):
                    self.ogien_stale.add(p)
            w[0] += 1
            w[2] = teraz
            if w[0] >= OGIEN_STALY_N and teraz - w[1] >= OGIEN_STALY_S \
                    and (not OGIEN_MASKA_TYLKO_SCIANY or self._ogien_pole_sciana(p)):
                self.ogien_stale.add(p)       # R1a: pole przechodnie wg mapy nigdy nie trafia do maski
        for p, w in list(self.ogien_widz.items()):
            if p not in self.ogien_stale and teraz - w[2] > OGIEN_STALY_S:
                del self.ogien_widz[p]
        if len(self.ogien_stale) != przed:
            self._ogien_stale_zapisz()

    def _ogien_na(self, pole):
        """Czy pole (x, y, z) jest polem ognia: widziany teraz ogień albo znane parzące pole z buforem (22.10: to drugie
        zawsze, także przy ignorowaniu ognia i gdy wykrycie ze zrzutu go nie widzi)."""
        if (pole[0], pole[1]) in self._ogien_parzy_dane(pole[2]):
            return True
        return self._ogien_aktywny() and (pole[0], pole[1], pole[2]) in self.ogien_pola

    def _ogien_parzy_dane(self, z, bufor=None):
        """15.10: pola z trasy/ogien_epizody.json z potwierdzonym spadkiem HP ("hp": true) na piętrze z. Omijamy je
        zawsze, także gdy wykrycie ze zrzutu chwilowo nie widzi ognia: wykrycie nie odróżnia dużego (parzy) od małego.
        22.10: razem z polami w promieniu `bufor` (domyślnie OGIEN_PARZY_BUFOR)."""
        if not OGIEN_UNIKAJ:
            return set()
        b = max(0, int(OGIEN_PARZY_BUFOR if bufor is None else bufor))
        wynik = set()
        for k, e in self.ogien_epizody.items():
            if e.get("hp"):
                try:
                    x, y, pz = (int(v) for v in k.split(","))
                except ValueError:
                    continue
                if pz == z:
                    wynik |= {(x + dx, y + dy) for dx in range(-b, b + 1) for dy in range(-b, b + 1)}   # 22.10: bufor
        return wynik

    def _ogien_blok(self, start, cel=None):
        """Pola ognia piętra startu jako lista (x, y, z) dla A* (bez pola, na którym stoimy)."""
        pola = self._ogien_xy(start[2], bez_stalych=True) | self._ogien_parzy_dane(start[2])
        return [(x, y, start[2]) for (x, y) in pola if (x, y) != tuple(start[:2])]

    def _ogien_przy_parzacym(self, pole):
        """15.10: czy pole (x, y, z) leży przy znanym parzącym polu (Chebyshev <= OGIEN_PARZY_ODL_CELU)."""
        return any(max(abs(a - pole[0]), abs(b - pole[1])) <= OGIEN_PARZY_ODL_CELU
                   for a, b in self._ogien_parzy_dane(pole[2]))

    def _ogien_na_drodze(self, poz, cel_xy):
        """Czy pole ognia leży w prostokącie poz-cel (+1 pole zapasu): klik poprowadziłby klienta przez ogień."""
        ogien = self._ogien_xy(poz[2], bez_stalych=True) | self._ogien_parzy_dane(poz[2])   # stałe: mapa omija (P6)
        if not ogien:
            return False
        x0, x1 = sorted((poz[0], cel_xy[0]))
        y0, y1 = sorted((poz[1], cel_xy[1]))
        return any(x0 - 1 <= x <= x1 + 1 and y0 - 1 <= y <= y1 + 1 for x, y in ogien)

    def _dziura_na_drodze(self, poz, cel_xy):
        """Czy nauczona dziura leży w prostokącie poz-cel (+1 pole zapasu): klik poprowadziłby klienta przez nią."""
        if not DZIURY_NAUCZONE:
            return False
        w = self._wp()
        if not w or not w.dziury:
            return False
        x0, x1 = sorted((poz[0], cel_xy[0]))
        y0, y1 = sorted((poz[1], cel_xy[1]))
        return any(h[2] == poz[2] and x0 - 1 <= h[0] <= x1 + 1 and y0 - 1 <= h[1] <= y1 + 1 for h in w.dziury)

    def _dziury_przy(self, pole, z):
        """Znane dziury piętra z (x, y) w Chebyshev <= 1 od pola (x, y): flaga 2 + chodliwe na mapie serwera albo nauczone."""
        wyn = set()
        m = self.mapa
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                x, y = pole[0] + dx, pole[1] + dy
                try:
                    if m is not None:
                        f = m.flagi(x, y, z)
                        if f & 1 and f & 2 and not f & 4:
                            wyn.add((x, y))
                except Exception:
                    pass
                if self.dziura_nauczona((x, y, z)):
                    wyn.add((x, y))
        return wyn

    def _cel_przez_dziure(self, s, poz, teraz=None):
        """15.10 (kieszeń): ocena celu `s` (stwór z x, y, z) stojącego przy znanej dziurze. None = bez zastrzeżeń;
        "idz" = dziura leży w prostokącie poz-cel, ale sami dojdziemy A* (dziury jako ściany) do pola obok celu drogą
        <= Chebyshev + 1: najpierw idziemy sami (klient w trybie ataku idzie za celem własną drogą i wpadał w dziurę:
        21:33:59 Troll (32509,32273) przy dziurze (32508,32273), upadek na z9); "skip" = takiej drogi nie ma (albo
        podejście trwa za długo): celu nie atakujemy. Cel obok nas (Chebyshev <= 1) nie jest sprawdzany."""
        if not DZIURA_PRZY_CELU or s.get("z", poz[2]) != poz[2]:
            return None
        cx, cy = s["x"], s["y"]
        odl = max(abs(cx - poz[0]), abs(cy - poz[1]))
        if odl <= 1:
            return None
        # dziury przy celu ORAZ przy nas (uciekający cel: klient idzie za nim i pierwszy krok może wejść w dziurę obok nas)
        dz = self._dziury_przy((cx, cy), poz[2]) | self._dziury_przy((poz[0], poz[1]), poz[2])
        if not dz:
            return None
        x0, x1 = sorted((poz[0], cx))
        y0, y1 = sorted((poz[1], cy))
        dz = {(x, y) for x, y in dz if x0 <= x <= x1 and y0 <= y <= y1 and (x, y) != (poz[0], poz[1])}
        if not dz:
            return None
        if teraz is not None and teraz < getattr(self, "_dziura_poddane", {}).get(s["id"], float("-inf")):
            return "skip"
        try:
            zajete = [(x, y, poz[2]) for x, y in dz]
            d = self.droga((poz[0], poz[1], poz[2]), (cx, cy), zajete=zajete, dlugosc=1)
        except bot.Zatrzymano:
            raise
        except Exception:
            return None                        # błąd A*: nie blokujemy walki
        return "idz" if d is not None and len(d) <= odl + 1 else "skip"

    def _dziura_cel_odpusc(self, cel, poz, teraz, escape=True):
        """Odpuszczenie celu przy dziurze: log (co 30 s na cel) i Escape (zatrzymuje follow/atak klienta)."""
        ost = getattr(self, "_dziura_cel_log", {})
        if teraz - ost.get(cel["id"], float("-inf")) >= 30.0:
            ost[cel["id"]] = teraz
            self._dziura_cel_log = ost
            log(f"[DZIURA] odpuszczam {cel['nazwa']} ({cel['x']},{cel['y']}): stoi przy dziurze na drodze klienta, "
                f"nie gonię (czekam aż odejdzie od dziury).")
        if not escape:
            return
        try:
            if not self.zatrzymaj_klik(poz):
                self.postac.klawisz("Escape")      # follow/atak klienta nie opiera się na klik_cel
        except bot.Zatrzymano:
            raise
        except Exception:
            pass

    def _dziura_podejscie(self, cel, poz, teraz):
        """Cel przy dziurze, ale mamy bezpieczną drogę: idziemy sami (A*, dziury = ściany) na pole obok celu zamiast klikać
        atak. Budżet DZIURA_PODEJSCIE_S na cel, potem odpuszczenie. True = obieg zużyty, False = odpuszczone."""
        st = getattr(self, "_dziura_poczatek", None)
        if st is None:
            st = self._dziura_poczatek = {}
        t0 = st.setdefault(cel["id"], teraz)
        if teraz - t0 > DZIURA_PODEJSCIE_S:
            st.pop(cel["id"], None)
            pd = getattr(self, "_dziura_poddane", None)
            if pd is None:
                pd = self._dziura_poddane = {}
            pd[cel["id"]] = teraz + DZIURA_PODEJSCIE_S
            return False
        if t0 == teraz or teraz - getattr(self, "_dziura_esc", float("-inf")) >= 3.0:
            self._dziura_esc = teraz
            try:
                self.postac.klawisz("Escape")      # klient mógł już iść za celem (follow): przerywamy, dalej idziemy sami
            except bot.Zatrzymano:
                raise
            except Exception:
                pass
            self.klik_cel = None
        if t0 == teraz:
            log(f"[DZIURA] {cel['nazwa']} ({cel['x']},{cel['y']}) przy dziurze: idę sam obok celu (A*, dziury jako ściany), bez kliku ataku.")
        self.ustaw_stan("POGON", f"{cel['nazwa']} przy dziurze -> ({cel['x']},{cel['y']})")
        r = self.podejdz((cel["x"], cel["y"]), poz, pilne=True, natychmiast=True)
        if r is None or r is False:
            self.nieudane += 1
            self.pauza(0.1, 0.25)
        return True

    def _ogien_tick(self, poz, teraz, wymus=False):
        """Odświeża pola ognia (najwyżej co OGIEN_ODSWIEZ_S; wymus=True: teraz). Wykrycie to jeden zrzut ppm
        (ok. 40 ms) + analiza; bez źródła (testy, brak gry) nic nie robi. Błąd odczytu nie zatrzymuje bota."""
        if not OGIEN_UNIKAJ:
            if self.ogien_pola:
                self.ogien_pola = {}
            return
        odstep = OGIEN_ODSWIEZ_S
        if OGIEN_ODSWIEZ_WALKA_S > odstep and str(self.stan) == "WALKA" \
                and not any(p not in self._ogien_stale_ef() for p in self.ogien_pola):
            odstep = OGIEN_ODSWIEZ_WALKA_S      # P6: w walce bez zmiennych pól ognia rzadziej (jeden zrzut ppm to ok. 60 ms)
        if self.ogien_odczyt is None or (not wymus and teraz - self.ogien_t < odstep):
            return
        self.ogien_t = teraz
        try:
            wzgl = self.ogien_odczyt()
        except bot.Zatrzymano:
            raise
        except Exception as e:
            if teraz - self.ogien_blad_t >= 60.0:
                self.ogien_blad_t = teraz
                log(f"[OGIEN] nie wykryję ognia: {e!r}")
            return
        if wzgl is None:
            return
        x, y, z = poz[0], poz[1], poz[2]
        if self.ogien_poz_ost != (x, y, z):
            self.ogien_poz_ost, self.ogien_poz_od = (x, y, z), teraz
        self._ogien_podpalenie_znane(poz, teraz)
        stare = set(self.ogien_pola)
        widziane = {(x + dx, y + dy, z) for dx, dy in wzgl}
        widziane = self._ogien_pomin_przy_stworze(widziane, z, teraz)
        self._ogien_epizody_tick(widziane, poz, teraz)
        if OGIEN_MASKA_DANE and self.ogien_dane_maska:
            widziane = {p for p in widziane if p not in self.ogien_dane_maska}    # pole z maski danych to nie ogień
            for p in self.ogien_dane_maska:
                self.ogien_pola.pop(p, None)
        self._ogien_stale_aktualizuj(widziane, teraz)
        for p in widziane:
            self.ogien_pola[p] = teraz
            self.ogien_pierw.setdefault(p, teraz)
        for p, t in list(self.ogien_pola.items()):
            if p in widziane:
                continue
            w_widoku = p[2] == z and abs(p[0] - x) <= ZASIEG_X and abs(p[1] - y) <= ZASIEG_Y
            if p[2] != z or (w_widoku and teraz - t >= OGIEN_BRAK_S) or teraz - t > OGIEN_TRWA_S:
                del self.ogien_pola[p]
        for p in [p for p in self.ogien_pierw if p not in self.ogien_pola]:
            del self.ogien_pierw[p]
        self._ogien_epizody_zapisz(teraz)
        nowe = set(self.ogien_pola) - stare
        if nowe and self.klik_cel is not None and self._ogien_na_drodze(poz, self.klik_cel):
            self.zatrzymaj_klik(poz)       # klik w toku prowadził przez nowy ogień: stop, krok po kroku z omijaniem
        stale = self._ogien_stale_ef()
        aktualne = frozenset(p for p in self.ogien_pola if p not in stale)    # P6: stałych pól nie logujemy
        zapisany, t_log = self.ogien_log_ost
        if zapisany is not None:
            zapisany = zapisany - stale        # pole, które właśnie uznano za stałe, nie jest "zmianą" zbioru
        if aktualne != zapisany and teraz - t_log >= OGIEN_LOG_S and (aktualne or zapisany):
            self.ogien_log_ost = (aktualne, teraz)
            opis = " ".join(f"({a},{b})" for a, b, _ in sorted(aktualne)) or "brak"
            log(f"[OGIEN] pola: {opis} (piętro {z}, {len(aktualne)})")
        if self.ogien_podsum_t is None:
            self.ogien_podsum_t = teraz
        elif teraz - self.ogien_podsum_t >= OGIEN_PODSUMOWANIE_S:
            self.ogien_podsum_t = teraz
            if stale or aktualne:
                log(f"[OGIEN] ogień: {len(stale)} stałych, {len(aktualne)} zmiennych")

    # --- potwierdzanie ognia i maska z danych (OGIEN_WYJDZ_POTWIERDZ, OGIEN_MASKA_DANE, OGIEN_POMIJAJ_PRZY_STWORZE) ---

    def _ogien_podpalenie_znane(self, poz, teraz):
        """24.10 (wydra 12:21): stoimy na ZNANYM parzącym polu (hp:true w danych, bez bufora) = postać się pali przez
        OGIEN_PODPALENIE_S. Okno otwiera tylko to wejście (nie spadek HP), więc spadki HP z podpalenia nie oznaczą innego
        pola jako parzącego ani nie wyrzucą go z maski danych. Nie dotyka nowych pól: te uczy _ogien_epizody_tick."""
        if not OGIEN_PODPALENIE_ZNANE or not OGIEN_UNIKAJ or poz is None:
            return False
        if (poz[0], poz[1]) not in self._ogien_parzy_dane(poz[2], bufor=0):
            return False
        do = teraz + OGIEN_PODPALENIE_S
        if do > self.ogien_podpalony_do:
            if teraz >= self.ogien_podpalony_do:
                log(f"[OGIEN] wszedłem na znane parzące pole ({poz[0]},{poz[1]}): podpalenie ok. {OGIEN_PODPALENIE_S:.0f} s, "
                    f"spadki HP w tym czasie nie obciążają innych pól.")
            self.ogien_podpalony_do = do
        return True

    def _ogien_spadek_hp(self, teraz):
        """Spadek HP (pp max HP) w ostatnich OGIEN_HP_OKNO_S s: najwyższy odczyt z okna minus ostatni."""
        h = [p for t, p in self.ogien_hp_hist if teraz - t <= OGIEN_HP_OKNO_S]
        return max(h) - h[-1] if len(h) >= 2 else 0.0

    def _ogien_stwory_xy(self, z):
        """Pola stworów (bez graczy) na piętrze z, z ostatniego obiegu, plus pole celu."""
        pola = {(s["x"], s["y"]) for s in (self.ostatnie_stwory or [])
                if s.get("z", z) == z and not s.get("gracz") and s.get("hp", 100) > 0}
        c = self.cel
        if isinstance(c, dict) and c.get("poz") and (len(c["poz"]) < 3 or c["poz"][2] == z):
            pola.add((c["poz"][0], c["poz"][1]))
        return pola

    def _ogien_pomin_przy_stworze(self, widziane, z, teraz):
        """Pkt 4: wykrycia na polu stwora/celu albo obok niego (odl <= 1) pomijamy, dopóki HP nie spadło."""
        if not OGIEN_POMIJAJ_PRZY_STWORZE or not widziane or self._ogien_spadek_hp(teraz) >= OGIEN_HP_SPADEK_PP:
            return widziane
        st = self._ogien_stwory_xy(z)
        if not st:
            return widziane
        return {p for p in widziane if not any(abs(p[0] - a) <= 1 and abs(p[1] - b) <= 1 for a, b in st)}

    def _ogien_potwierdzony(self, poz, teraz):
        """Pkt 1: czy ogień pod nami jest prawdziwy. Spadek HP bez stwora obok = tak; stwór obok (odl <= 1, także cel
        w WALKA) bez spadku HP = nie; spadek HP przy stworze obok liczy się tylko razem z potwierdzeniem czasem;
        bez stwora i bez spadku HP wystarczy to samo pole wykryte dwa razy w odstępie >= OGIEN_POTW_S."""
        p = (poz[0], poz[1], poz[2])
        spadek = self._ogien_spadek_hp(teraz) >= OGIEN_HP_SPADEK_PP
        obok = any(abs(a - p[0]) <= 1 and abs(b - p[1]) <= 1 for a, b in self._ogien_stwory_xy(p[2]))
        czasem = self.ogien_pola.get(p, teraz) - self.ogien_pierw.get(p, teraz) >= OGIEN_POTW_S
        if spadek:
            return (not obok) or czasem
        return czasem and not obok

    def _ogien_klucz(self, p):
        return f"{p[0]},{p[1]},{p[2]}"

    def _ogien_dane_przelicz(self):
        """Pola przechodnie z >= OGIEN_EPIZODY_N epizodami w >= OGIEN_EPIZODY_GODZ godzinach i bez spadku HP."""
        maska = set()
        for k, e in self.ogien_epizody.items():
            if e.get("n", 0) >= OGIEN_EPIZODY_N and len(set(e.get("godz", []))) >= OGIEN_EPIZODY_GODZ and not e.get("hp"):
                try:
                    x, y, z = (int(v) for v in k.split(","))
                except ValueError:
                    continue
                maska.add((x, y, z))
        for p in maska - self.ogien_dane_maska:
            log(f"[OGIEN] pole {p} do maski danych: {self.ogien_epizody[self._ogien_klucz(p)]['n']} epizodów, bez spadku HP.")
        for p in self.ogien_dane_maska - maska:
            log(f"[OGIEN] pole {p} wypada z maski danych (spadek HP albo zmiana danych).")
        self.ogien_dane_maska = maska

    def _ogien_epizody_wczytaj(self):
        if PLIK_OGIEN_EPIZODY is None:
            return
        try:
            dane = json.loads(Path(PLIK_OGIEN_EPIZODY).read_text()).get("pola", {})
            for k, e in dane.items():
                self.ogien_epizody[k] = {"n": int(e.get("n", 0)), "godz": sorted({int(h) for h in e.get("godz", [])}),
                                         "hp": bool(e.get("hp")), "ost": float(e.get("ost", 0.0))}
            self._ogien_dane_przelicz()
        except FileNotFoundError:
            pass
        except Exception as e:
            log(f"[OGIEN] nie wczytam epizodów ognia: {e!r}")

    def _ogien_epizody_scal(self):
        """24.10: dopisuje do pamięci to, co w pliku zapisały inne procesy (hp = LUB, n/ost = max, godziny = suma), żeby
        zapis całego pliku nie gubił cudzych oznaczeń hp (wcześniej: ostatni piszący wygrywał, 8 botów pisze ten sam plik)."""
        zmiana = False
        try:
            dane = json.loads(Path(PLIK_OGIEN_EPIZODY).read_text()).get("pola", {})
            for k, e in dane.items():
                m = self.ogien_epizody.get(k)
                nowe = {"n": int(e.get("n", 0)), "godz": sorted({int(h) for h in e.get("godz", [])}),
                        "hp": bool(e.get("hp")), "ost": float(e.get("ost", 0.0))}
                if m is None:
                    self.ogien_epizody[k] = nowe
                    zmiana = True
                    continue
                scalone = {"n": max(m["n"], nowe["n"]), "godz": sorted(set(m["godz"]) | set(nowe["godz"])),
                           "hp": bool(m["hp"] or nowe["hp"]), "ost": max(m["ost"], nowe["ost"])}
                if scalone != m:
                    self.ogien_epizody[k] = scalone
                    zmiana = True
        except FileNotFoundError:
            pass
        except Exception as e:
            log(f"[OGIEN] nie scalę epizodów ognia z plikiem: {e!r}")
        if zmiana:
            self._ogien_dane_przelicz()

    def _ogien_epizody_zapisz(self, teraz, wymus=False):
        """Atomowy zapis trasy/ogien_epizody.json, najwyżej co OGIEN_EPIZODY_ZAPIS_S (tylko po zmianie)."""
        if PLIK_OGIEN_EPIZODY is None or not self.ogien_ep_brudne:
            return
        if not wymus and teraz - self.ogien_ep_zapis_t < OGIEN_EPIZODY_ZAPIS_S:
            return
        self.ogien_ep_zapis_t = teraz
        if OGIEN_EPIZODY_SCAL:
            self._ogien_epizody_scal()
        try:
            cel = Path(PLIK_OGIEN_EPIZODY)
            tmp = cel.with_suffix(".tmp")
            tmp.write_text(json.dumps({"opis": "epizody wykryc ognia na polach (n po przerwie > 60 s, godziny doby, hp = spadek HP na polu); zapis bota",
                                       "pola": {k: self.ogien_epizody[k] for k in sorted(self.ogien_epizody)}}, indent=0))
            tmp.replace(cel)
            self.ogien_ep_brudne = False
        except Exception as e:
            log(f"[OGIEN] nie zapiszę epizodów ognia: {e!r}")

    def _ogien_epizody_tick(self, widziane, poz, teraz):
        """Pkt 2: liczy epizody wykryć pól (po przerwie > OGIEN_EPIZOD_PRZERWA_S), godziny doby, a spadek HP
        na polu, na którym stoimy, kasuje kwalifikację pola do maski danych."""
        if not OGIEN_MASKA_DANE or not widziane:
            return
        wall = self.ogien_wall()
        godz = time.localtime(wall).tm_hour
        zmiana = False
        for p in widziane:
            k = self._ogien_klucz(p)
            e = self.ogien_epizody.get(k)
            if e is None:
                e = self.ogien_epizody[k] = {"n": 0, "godz": [], "hp": False, "ost": 0.0}
            if wall - e["ost"] > OGIEN_EPIZOD_PRZERWA_S:
                e["n"] += 1
                if godz not in e["godz"]:
                    e["godz"] = sorted(e["godz"] + [godz])
                zmiana = True
            e["ost"] = wall
            if not e["hp"] and (poz[0], poz[1], poz[2]) == p and self._ogien_spadek_hp(teraz) >= OGIEN_HP_SPADEK_PP:
                obok = any(abs(a - p[0]) <= 1 and abs(b - p[1]) <= 1 for a, b in self._ogien_stwory_xy(p[2]))
                if teraz < self.ogien_podpalony_do or obok or teraz - self.ogien_poz_od > OGIEN_WEJSCIE_S:
                    continue        # 15.10: podpalenie z innego pola, stwór obok albo spadek nie tuż po wejściu: nie to pole
                e["hp"] = True
                zmiana = True
                self.ogien_podpalony_do = teraz + OGIEN_PODPALENIE_S
                log(f"[OGIEN] pole {p}: spadek HP tuż po wejściu, pole parzy (wypada z kwalifikacji do maski danych).")
        if zmiana:
            self.ogien_ep_brudne = True
            self._ogien_dane_przelicz()

    def _ogien_przechodnie(self, pole):
        """Czy pole (x, y, z) wygląda na przechodnie (nie ściana nauczona/mapowa, nie zmiana piętra, znane)."""
        if self.sciana(pole) or self.pole_zmiany_pietra(pole):
            return False
        if self.mapa is not None:
            try:
                if self.mapa.flagi(*pole) & 1:
                    return self.mapa.przechodnie(*pole) is not False
            except Exception:
                pass
        return tuple(pole) in self.znane

    def _ogien_wyjdz(self, poz, teraz):
        """Gracz stoi na polu ognia: krok na najbliższe wolne pole poza ogniem (BFS po przechodnich polach,
        przez inne pola ognia, jeśli trzeba). True = obieg wykorzystany (krok albo oczekiwanie na krok)."""
        if not self._ogien_aktywny():
            return False
        x, y, z = poz[0], poz[1], poz[2]
        self._ogien_podpalenie_znane(poz, teraz)
        ogien = self._ogien_xy(z)
        if (x, y) not in ogien:
            return False
        if OGIEN_WYJDZ_POTWIERDZ and not self._ogien_potwierdzony(poz, teraz):
            if teraz - self.ogien_ign_log.get((x, y, z), float("-inf")) >= OGIEN_IGNORUJ_LOG_S:
                self.ogien_ign_log[(x, y, z)] = teraz
                log(f"[OGIEN] pole ({x},{y},{z}) ignoruję: bez spadku HP")
            return False
        if teraz - self.ogien_krok_t < OGIEN_KROK_S:
            self.pauza(0.05, 0.1)            # poprzedni krok jeszcze trwa
            return True
        zajete = set(self.zajete_bez_nas(poz))
        for k_, do in list(self.ogien_zle.items()):
            if do <= teraz:
                del self.ogien_zle[k_]
        start = (x, y)
        skad = {start: None}
        kolejka = [start]
        cel = None
        i = 0
        while i < len(kolejka):
            c = kolejka[i]
            i += 1
            if c != start and c not in ogien:
                cel = c
                break
            if abs(c[0] - x) + abs(c[1] - y) >= OGIEN_SZUKAJ:
                continue
            for k, (dx, dy) in bot.KIERUNKI.items():
                n = (c[0] + dx, c[1] + dy)
                if n in skad or n in zajete or (c, n) in self.ogien_zle \
                        or not self._ogien_przechodnie((n[0], n[1], z)):
                    continue
                skad[n] = (c, k)
                kolejka.append(n)
        if cel is None:
            log(f"[OGIEN] stoję na ogniu ({x},{y}), nie widzę wolnego pola obok (ściany/stwory/ogień wokół).")
            self.ogien_krok_t = teraz
            return False
        n = cel
        while skad[n][0] != start:
            n = skad[n][0]
        k0 = skad[n][1]
        self.ogien_krok_t = teraz
        log(f"[OGIEN] stoję na ogniu ({x},{y}), schodzę na ({n[0]},{n[1]}) (wolne pole ({cel[0]},{cel[1]})).")
        self.klik_cel = None
        if self.postac.krok(k0):
            self.krok_z = ((x, y, z), teraz)
            self.zablokowane.clear()
        else:
            self.ogien_zle[(start, n)] = teraz + OGIEN_ZLY_KROK_S
        return True

    def _ogien_krok(self, poz, cel_xy, krok=None):
        """Zamiast kliku, który klient poprowadziłby przez ogień: jeden krok własną drogą (A* z ogniem jako
        przeszkodą), a bez drogi - zachłanny krok w stronę celu z pominięciem ognia, a gdy i to się nie da, czekamy
        (po OGIEN_CZEKAJ_MAX_S przestajemy się przejmować ogniem na OGIEN_IGNORUJ_S)."""
        teraz = self.zegar()
        d = self.droga(tuple(poz), (cel_xy[0], cel_xy[1]), dlugosc=0)
        if not d:
            # 15.10: cel to schody/dziura (zakaz w A*) albo pole zajęte: droga do pola obok celu (15:03 stał 162 s
            # w kieszeni (32491,32288) przy ogniu, jedyne wyjście skosem, a A* do samych schodów nie miał drogi)
            d = self.droga(tuple(poz), (cel_xy[0], cel_xy[1]), dlugosc=1)
        self.klik_cel = None
        cel_kroku = d[0][:2] if d else (krok[:2] if krok else cel_xy)
        if self.krok_do(cel_kroku):
            self.ogien_czeka_od = None
            return True
        if self.ogien_czeka_od is None:
            self.ogien_czeka_od = teraz
        elif teraz - self.ogien_czeka_od >= OGIEN_CZEKAJ_MAX_S:
            self.ogien_czeka_od = None
            if OGIEN_IGNORUJ_S <= 0:
                log(f"[OGIEN] ogień zamyka drogę do ({cel_xy[0]},{cel_xy[1]}) od {OGIEN_CZEKAJ_MAX_S:.0f} s "
                    f"(brak drogi także skosem): nie wchodzę, inny cel trasy.")
                return False
            log(f"[OGIEN] ogień zamyka drogę od {OGIEN_CZEKAJ_MAX_S:.0f} s, ignoruję go przez {OGIEN_IGNORUJ_S:.0f} s.")
            self.ogien_ignoruj_do = teraz + OGIEN_IGNORUJ_S
        return True

    def droga(self, start, cel, zajete=(), dlugosc=1, skosy=True):
        """Najkrótsza droga z start=(x,y,z) do pola, z którego do cel=(x,y) jest <= dlugosc.
        Z pełną mapą (gdy zna start i cel): A* po wszystkich przechodnich polach piętra (mapa.py),
        pola znane (stał na nich gracz) liczą się też tam, gdzie minimapa ich nie widziała, a
        nauczone ściany (self.sciany) i `zajete` omijamy; None = drogi nie ma (w MAPA_LIMIT pól).
        Bez mapy - po znanych polach (_droga_znane)."""
        if BLOK_WYJSCIE:
            self.ostatni_blokujacy = None
        if self.mapa_zna(start, cel):
            z = start[2]
            zakaz = self._zakaz_lista(start, cel)       # schody/dziury: nigdy po nich (poza wypadem)
            ogien = self._ogien_blok(start)             # pola ognia: nie wchodzimy (zamykają też drogę zapasową)
            blok = list(zajete) + zakaz + ogien + [p for p in list(self.sciany) if p[2] == z and self.sciana(p)]
            dz = self._drzwi_xy(z)                      # R1c: drzwi to przejście (nie ściana, nie nauczona ściana)
            przep = {x * _K + y for x, y in dz} or None
            if dz:
                blok = [p for p in blok if tuple(p[:2]) not in dz]
            znane = self._pola_pietra(z)
            d = self.mapa.droga(start, cel, blok, dlugosc, skosy, limit=MAPA_LIMIT, znane=znane, **({"przepusc": przep} if przep else {}))
            prosto = max(abs(cel[0] - start[0]), abs(cel[1] - start[1]))
            if blok and (d is None or len(d) > 2 * prosto + MAPA_OBJAZD):
                # stwory i nauczone ściany (często fałszywe: stwór na polu) nie mogą zamykać
                # wąskiego korytarza ani zmuszać do objazdu: liczymy też drogę po samej mapie
                # i bierzemy krótszą (gdy bez blokad nie jest to objazd)
                # 22.10 KROK_ZLY: zakaz po powtórnie nieudanych krokach obowiązuje także w tej drodze (inaczej korytarz wraca)
                twarde = [p for p in list(self.__dict__.get("sciany_do", {})) if p[2] == z and self.sciana(p)
                          and tuple(p[:2]) not in dz]
                d2 = self.mapa.droga(start, cel, zakaz + ogien + twarde, dlugosc, skosy, limit=MAPA_LIMIT, znane=znane,
                                     **({"przepusc": przep} if przep else {}))
                if BLOK_WYJSCIE and d2:
                    # 13.10 (22:07): droga po samej mapie przez pole zajęte stworem to nie droga do marszu
                    zset = {tuple(p[:2]) for p in zajete}
                    for p in d2[:max(1, int(BLOK_KROKI))]:
                        if tuple(p[:2]) in zset:
                            m = next((q for q in self.ostatnie_stwory if (q["x"], q["y"]) == tuple(p[:2])
                                      and q["z"] == z and q.get("hp", 100) > 0), None)
                            self.ostatni_blokujacy = (tuple(p[:2]), m["id"] if m else None)
                            d2 = None
                            break
                if d2 is not None and (d is None or (len(d2) < len(d) and len(d2) <= 2 * prosto + MAPA_OBJAZD)):
                    d = d2
                    self.droga_bez_blokad += 1
            return d
        return self._droga_znane(start, cel, list(zajete) + self._zakaz_lista(start, cel) + self._ogien_blok(start),
                                 dlugosc, skosy)

    def _droga_znane(self, start, cel, zajete=(), dlugosc=1, skosy=True):
        """Najkrótsza droga (Dijkstra na kubełkach, maks. DROGA_LIMIT pól) po znanych polach piętra
        start=(x,y,z) do najbliższego pola, z którego do cel=(x,y) jest <= dlugosc (Chebyshev).
        Pola z `zajete` omijamy. Krok prosty kosztuje 1, po skosie 3 (w 7.4 skos jest wolny), więc
        skos tylko tam, gdzie trasy go wymagają (zapisane przejścia po skosie). Zwraca listę pól
        drogi bez startu ([] = już jesteśmy przy celu) albo None, gdy drogi nie znamy."""
        sx, sy, z = start[0], start[1], start[2]
        cx, cy = cel[0], cel[1]
        if max(abs(sx - cx), abs(sy - cy)) <= dlugosc:
            return []
        pola = self._pola_pietra(z)
        blok = {p[0] * _K + p[1] for p in zajete}
        cele = {(cx + i) * _K + cy + j for i in range(-dlugosc, dlugosc + 1) for j in range(-dlugosc, dlugosc + 1)}
        ruchy = ((_K, 1), (-_K, 1), (1, 1), (-1, 1))
        if skosy:
            ruchy += ((_K + 1, 3), (_K - 1, 3), (-_K + 1, 3), (-_K - 1, 3))
        s = sx * _K + sy
        skad, koszt = {s: None}, {s: 0}
        kubly, i, gotowe = [[s]], 0, 0
        while i < len(kubly) and gotowe < DROGA_LIMIT:
            for k in kubly[i]:
                if koszt[k] != i:
                    continue                  # wpis nieaktualny (pole dostało tańszą drogę)
                gotowe += 1
                if k in cele and k != s:
                    wynik = []
                    while k != s:
                        y = (k + _K // 2) % _K - _K // 2
                        wynik.append(((k - y) // _K, y, z))
                        k = skad[k]
                    return wynik[::-1]
                for d, c in ruchy:
                    n = k + d
                    if n in pola and n not in blok and i + c < koszt.get(n, 1 << 30):
                        koszt[n], skad[n] = i + c, k
                        while len(kubly) <= i + c:
                            kubly.append([])
                        kubly[i + c].append(n)
            i += 1
        return None

    def _powod_braku_drogi(self, poz, cel, zajete):
        """Jedna linia: które sąsiednie pola (w stronę celu) są zablokowane i czym (stwór, nauczona
        ściana, mapa). Tylko do logu przy odmowie drogi."""
        zaj = {tuple(p[:2]) for p in zajete}
        nazwy = {"Right": "P", "Left": "L", "Down": "D", "Up": "G"}
        ruchy = {"Right": (1, 0), "Left": (-1, 0), "Down": (0, 1), "Up": (0, -1)}
        opisy = []
        try:
            for k in kierunki_do(poz[0], poz[1], cel[0], cel[1]):
                n = (poz[0] + ruchy[k][0], poz[1] + ruchy[k][1], poz[2])
                if n[:2] == tuple(cel[:2]):
                    continue
                if n[:2] in zaj:
                    powod = "stwór"
                elif self.sciana(n):
                    powod = "ściana (nauczona)"
                elif self.mapa is not None and self.mapa.flagi(*n) & 1 and self.mapa.przechodnie(*n) is False:
                    powod = "ściana (mapa)"
                elif self.mapa is not None and not self.mapa.flagi(*n) & 1 and n not in self.znane:
                    powod = "nieznane (mapa)"
                else:
                    powod = "wolne"
                opisy.append(f"{nazwy[k]}{n[:2]}={powod}")
        except Exception:
            return ""
        return " [pola: " + ", ".join(opisy) + "]" if opisy else ""

    def krok_prosto(self, cel, poz, pauza=True):
        """Strzałka w stronę celu omijająca poznane ściany. Krok, który nie przesunął postaci,
        oznacza ścianę na tym polu (zapamiętuje sprawdz_krok). None, gdy każdy kierunek przybliżający
        to ściana."""
        dx, dy = cel[0] - poz[0], cel[1] - poz[1]
        ruchy = []
        for k, mx, my in (("Right", 1, 0), ("Left", -1, 0), ("Down", 0, 1), ("Up", 0, -1)):
            zysk = mx * dx + my * dy            # o ile krok zbliża do celu (wzdłuż osi)
            if zysk > 0:
                ruchy.append((-zysk, k, (poz[0] + mx, poz[1] + my, poz[2])))
        for _, k, pole in sorted(ruchy):
            if self.sciana(pole) or self.pole_zmiany_pietra(pole) or self._ogien_na(pole):
                continue
            self.krok_prosto_ost = (tuple(poz), pole, self.zegar())
            self.klik_cel = None
            if os.environ.get("CAVEBOT_DEBUG"):
                log(f"debug: krok prosto {k} (ściany znane: {len(self.sciany)})")
            self._klawisz_ruchu(k, None)
            if pauza:
                self.pauza(0.12, 0.22)
            return True
        return None

    def _skos_mozliwy(self):
        """Czy da się wykonać skos: klik w pole obok, numpad postaci (krok_skos/skos) albo przechwyt pętli pościgu."""
        p = self.postac
        return self.klik is not None or self._ruch_przechwyt is not None \
            or hasattr(p, "krok_skos") or hasattr(p, "skos")

    def _krok_skos(self, nx, ny, poz, droga):
        """Skos (nx, ny) = znaki +-1 o jedno pole: w trybie trzymania zapis wektora (klawisz trzyma pętla pościgu),
        inaczej numpad postaci (stuknięcie) albo klik w pole po skosie. NIE ustawia krok_prosto_ost: brak ruchu po
        skosie to nie ściana (sprawdz_krok nie nauczy jej)."""
        self.klik_cel = None
        self.krok_prosto_ost = None
        self.skos_ost = (tuple(poz[:2]), (poz[0] + nx, poz[1] + ny))
        if self._ruch_przechwyt is not None:
            self._ruch_przechwyt.append(((nx, ny), droga))
            return True
        f = getattr(self.postac, "skos", None)
        if f is not None:
            f(nx, ny)
            return True
        return self.idz_do((poz[0] + nx, poz[1] + ny), poz, True, krok=droga[0] if droga else None)

    def _klawisz_ruchu(self, k, droga):
        """Strzałka kroku. W trybie trzymania (poscig_szybki) tylko zapisuje decyzję (k, droga), a klawisz
        trzyma pętla pościgu; poza nim zwykłe stuknięcie."""
        if self._ruch_przechwyt is not None:
            self._ruch_przechwyt.append((k, droga))
        else:
            self.postac.klawisz(k)

    def podejdz(self, cel, poz, pilne=False, zajete=None, dlugosc=1, natychmiast=False, objazd=True,
                poscig=False):
        """Ruch na pole przy cel=(x,y): po drodze z pełnej mapy (albo ze znanych pól, gdy mapy nie ma
        lub nie zna tych pól), a gdy drogi nie ma - na pole przy celu od naszej strony (po prostej).
        natychmiast=True (pościg): strzałka na następne pole drogi zamiast kliku.
        objazd=True: None, gdy droga to objazd (cel za ścianą) - wtedy nie idziemy.
        poscig=True (szybka pętla): tylko strzałki w osie (bez kliku skośnego) i bez pauzy po
        klawiszu - pętla sama czeka na zmianę pozycji."""
        if zajete is None:
            # bez nas samych (w pętli zbierz_loot lista jest sprzed ruchu: nasza stara pozycja)
            zajete = [(s["x"], s["y"]) for s in self.ostatnie_stwory
                      if s["z"] == poz[2] and s.get("hp", 100) > 0 and (s["x"], s["y"]) != tuple(poz[:2])
                      and not (s.get("gracz") and s.get("nazwa") == self.postac.nazwa) and not s.get("widmo")]
        if self.sprawdz_krok(poz, zajete, cel) and natychmiast:
            if not poscig:
                self.pauza(0.03, 0.06)        # poprzednia strzałka jeszcze nie przesunęła postaci
            return True
        prosto = max(abs(cel[0] - poz[0]), abs(cel[1] - poz[1]))
        # strzałki chodzą tylko prosto, więc dla nich droga bez skosów; skosem (klikiem) tylko blisko celu
        skosy = self.klik is not None and not poscig and (not natychmiast or prosto <= DIAGONAL_ODL)
        d = self.droga(poz, cel, zajete, dlugosc, skosy=skosy)
        if (POSCIG_SKOS_AWARYJNY or POSCIG_SKOSY_ZAPAS) and not skosy and self._skos_mozliwy():
            # 12.10: róg, w którym jedyne przejście jest po skosie (dwa pola w osiach = ściana): bez drogi prostej
            # (albo przy długim objazdzie) bierzemy drogę ze skosami, jeśli jest; skos tylko awaryjnie
            limit_d = 2 * prosto + (MAPA_OBJAZD if self.mapa_zna(poz, cel) else DROGA_OBJAZD)
            if (POSCIG_SKOS_AWARYJNY and (d is None or (d and len(d) > limit_d))) or (POSCIG_SKOSY_ZAPAS and d is None):
                teraz_s = self.zegar()
                zle = [q for (z0, q), do in self.skos_zle.items() if z0 == tuple(poz[:2]) and do > teraz_s]
                d2 = self.droga(poz, cel, list(zajete) + zle, dlugosc, skosy=True)
                if BLOK_WYJSCIE and d2 and tuple(d2[0][:2]) in {tuple(p[:2]) for p in zajete}:
                    d2 = None          # pierwszy krok skosu w pole zajęte przez stwora: nie idziemy
                if POSCIG_SKOSY_ZAPAS and d2 and len(d2) > POSCIG_SKOSY_MAX_DL:
                    d2 = None          # R1c: druga próba ze skosami tylko do limitu długości
                if d2 and (d is None or len(d2) < len(d)):
                    d = d2
                    self.skos_awaryjny_n += 1
                    if teraz_s - self._skos_log_t >= SKOS_LOG_S:
                        self._skos_log_t = teraz_s
                        log(f"Skos awaryjny: brak drogi prostej z ({poz[0]},{poz[1]}) do ({cel[0]},{cel[1]}), "
                            f"droga ze skosem {len(d)} pól.")
        if self.mapa_zna(poz, cel):
            self.ostatnia_droga_dl = float("inf") if d is None else len(d)
        else:
            self.ostatnia_droga_dl = len(d) if d else None
        if self.mapa_zna(poz, cel):
            # droga z pełnej mapy jest prawdziwa: odrzucamy cel tylko, gdy jej nie ma albo jest
            # naprawdę długa (cel za ścianą, droga naokoło)
            if objazd and (d is None or len(d) > 2 * prosto + MAPA_OBJAZD):
                self.ostatni_objazd = f"{'brak drogi' if d is None else f'droga {len(d)} pól'}, prosto {prosto}"
                if d is None:
                    self.ostatni_objazd += self._powod_braku_drogi(poz, cel, zajete)
                if os.environ.get("CAVEBOT_DEBUG"):
                    log(f"debug: mapa: {self.ostatni_objazd} - objazd, nie gonię")
                return None
        else:
            if natychmiast and self.klik is not None and prosto <= PROSTO_ZASIEG \
                    and (not d or len(d) > 2 * prosto + DROGA_OBJAZD):
                # mapa znanych pól jest uboga (tylko przechodzone pola): blisko celu idziemy prosto
                # strzałkami i uczymy się ścian z kroków, które nie przesunęły postaci
                wynik = self.krok_prosto(cel, poz, pauza=not poscig)
                if wynik is None:
                    self.ostatni_objazd = f"ściany na wprost, prosto {prosto}" \
                        + self._powod_braku_drogi(poz, cel, zajete)
                return wynik
            if objazd and d and len(d) > 2 * prosto + DROGA_OBJAZD:
                # cel za ścianą (droga naokoło): nie idziemy w przeciwną stronę
                self.ostatni_objazd = f"droga {len(d)} pól po znanych polach, prosto {prosto}"
                if os.environ.get("CAVEBOT_DEBUG"):
                    log(f"debug: droga {len(d)} pól do celu {prosto} pól w linii prostej - objazd, nie gonię")
                return None
        if d and PATROL_DRZWI and self._ruch_przechwyt is None:
            dr_ = self._drzwi_hak(poz, d[:3])        # R1c: zamknięte drzwi na drodze: Use z pola obok
            if dr_ is True:
                return True
            if dr_ is False:
                self.ostatni_objazd = "drzwi nie działają (odpuszczone)"
                return None
        if d and natychmiast and self.klik is not None:
            # pościg: strzałka na następne pole drogi od razu, bez czekania na potwierdzenie
            # (strzałka w trakcie kroku ustawia się w kolejce, więc postać idzie płynnie)
            nx, ny = d[0][0] - poz[0], d[0][1] - poz[1]
            if nx and ny:
                # skos: strzałki chodzą tylko prosto. W szybkiej pętli pościgu (poscig=True) numpad (przechwycony
                # wektor albo stuknięcie), poza nią klik w sąsiednie pole po skosie. Skos nie uczy ścian
                if os.environ.get("CAVEBOT_DEBUG"):
                    log(f"debug: pościg skosem ({nx},{ny}), droga {len(d)} pól")
                if poscig:
                    return self._krok_skos(nx, ny, poz, d)
                self.krok_prosto_ost = None
                return self.idz_do(d[0][:2], poz, True, krok=d[0])
            k = ("Right" if nx > 0 else "Left") if nx else ("Down" if ny > 0 else "Up")
            self.klik_cel = None
            self.krok_prosto_ost = (tuple(poz), tuple(d[0]), self.zegar())   # nauka ścian (stara mapa)
            if os.environ.get("CAVEBOT_DEBUG"):
                log(f"debug: pościg strzałką {k}, droga {len(d)} pól")
            self._klawisz_ruchu(k, d)
            if not poscig:
                self.pauza(0.12, 0.22)
            return True
        if not d:
            if poscig:
                # bez drogi: strzałka w oś o większej różnicy (omijając znane ściany), nie klik skośny
                wynik = self.krok_prosto(cel, poz, pauza=False)
                if wynik is None:
                    self.ostatni_objazd = f"ściany na wprost, prosto {prosto}" \
                        + self._powod_braku_drogi(poz, cel, zajete)
                return wynik
            sx = cel[0] - (cel[0] > poz[0]) + (cel[0] < poz[0])
            sy = cel[1] - (cel[1] > poz[1]) + (cel[1] < poz[1])
            return self.idz_do((sx, sy), poz, pilne)
        if self.klik is None:
            return self.krok_do(d[0])         # strzałki: dokładnie następne pole drogi
        # najdalsze pole drogi w widoku, maks. 3-5 do przodu (koniec, gdy droga krótka);
        # poprzedni klik zostawiamy, dopóki leży na drodze >= 2 pola przed nami
        def w_widoku(p):
            return abs(p[0] - poz[0]) <= ZASIEG_X - 1 and abs(p[1] - poz[1]) <= ZASIEG_Y - 1
        drogi_xy = [p[:2] for p in d]
        if self.klik_cel is not None and self.klik_cel in drogi_xy[1:] and w_widoku(self.klik_cel):
            cel_kliku = self.klik_cel
        else:
            ile = len(d) if len(d) <= DROGA_DO_PRZODU[1] else random.randint(*DROGA_DO_PRZODU)
            cel_kliku = d[0][:2]
            for p in d[:ile]:
                if not w_widoku(p):
                    break
                cel_kliku = p[:2]
        if os.environ.get("CAVEBOT_DEBUG"):
            log(f"debug: droga {len(d)} pól do {cel}, klik w {cel_kliku}")
        return self.idz_do(cel_kliku, poz, pilne, krok=d[0])

    @staticmethod
    def _wczytaj_loot():
        try:
            import loot  # noqa: PLC0415
            return loot
        except ImportError:
            return None

    def _atakowany_domyslny(self, stwor, gracz):
        """True/False z pamięci (pole "atakowany" w stwory albo komenda cel_ataku);
        gdy odczyt zawiedzie - ramka na zrzucie (po ciemku None)."""
        w = self._atakowany_z_pamieci(stwor)
        if w is not None:
            self.ramka_z_pamieci = True
            return w
        if getattr(self, "ramka_z_pamieci", True):
            log("Brak flagi ataku w pamięci, sprawdzam ramkę na zrzucie.")
            self.ramka_z_pamieci = False
        return self._atakowany_ze_zrzutu(stwor, gracz)

    def _atakowany_z_pamieci(self, stwor):
        w = stwor.get("atakowany")
        if isinstance(w, bool):
            return w
        try:   # starszy rdzen bez pola w stwory: osobna komenda
            odp = self.zapytaj({"cmd": "cel_ataku"})
            if isinstance(odp, dict) and "id" in odp:
                return odp["id"] is not None and odp["id"] == stwor["id"]
        except Exception:
            pass
        return None

    @staticmethod
    def _atakowany_ze_zrzutu(stwor, gracz):
        import ekran  # noqa: PLC0415
        try:
            return ekran.atakowany(stwor, gracz)
        except Exception as e:  # brak zrzutu nie może zatrzymać walki
            log(f"Nie sprawdzę ramki ataku: {e}")
            return False

    @staticmethod
    def _klik_domyslny(dx, dy):
        import ekran  # noqa: PLC0415
        ekran.klik_pola(dx, dy, 1)

    @staticmethod
    def _atak_domyslny(stwor, gracz):
        import ekran  # noqa: PLC0415
        ekran.atakuj(stwor, gracz)

    def ustaw_stan(self, stan, szczegol=""):
        if stan != self.stan:
            log(f"[{stan}] {szczegol}".rstrip())
            self.stan = stan

    def pauza(self, a=0.1, b=0.3):
        self.spij(random.uniform(a, b))

    def pauza_po_ticku(self):
        """Pauza między obiegami pętli głównej (cavebot.uruchom i mozg). Q5 11.10: gdy ten obieg to WALKA z celem
        dalej niż 1 pole (pościg), prawie bez pauzy (POSCIG_PAUZA_TICK_DALEKO); inaczej jak dawniej 0.05-0.15."""
        d = getattr(self, "walka_odl_tick", None)
        if d is not None and d > 1:
            self.pauza(*POSCIG_PAUZA_TICK_DALEKO)
        else:
            self.pauza(0.05, 0.15)

    def gracz(self):
        g = self.zapytaj({"cmd": "gracz"})["gracz"]
        g["proc"] = 100.0 * g["hp"] / g["max_hp"] if g["max_hp"] else 100.0
        return g

    def skan_rytm(self):
        """21.10: wiek listy stworów, którego bot teraz potrzebuje (walka krócej, spokój dłużej), albo None przy
        pokrętłach domyślnych (0.5/0.5 = zapytania bez pola "rytm", rdzeń jak dotąd)."""
        if SKAN_WIEK_WALKA == 0.5 and SKAN_WIEK_SPOKOJ == 0.5:
            return None
        walka = self.stan in SKAN_STANY_WALKI or getattr(self, "cel", None) is not None
        return float(SKAN_WIEK_WALKA if walka else SKAN_WIEK_SPOKOJ)

    def stwory(self, maks_wiek=None):
        z = {"cmd": "stwory"}
        rytm = self.skan_rytm()
        if rytm is not None:
            if maks_wiek is None:
                maks_wiek = rytm
            elif maks_wiek > 0:
                rytm = min(rytm, maks_wiek)  # marsz/PK pytają o 0,25-0,4 s: skaner ma za tym nadążać (świeży skan 0.0 nie wchodzi w rytm)
            z["rytm"] = rytm               # skaner w tle planuje pod najmniejszy rytm z 2 s (rdzen.Pamiec._rytm_teraz)
        if maks_wiek is not None:
            z["maks_wiek"] = maks_wiek     # cache skanera rdzenia zamiast świeżego skanu
        surowa = self.zapytaj(z)["stwory"]
        self.stwory_surowe = surowa
        pet = self.pet
        lista = pet.bez_peta(surowa) if pet is not None else surowa    # pet nie jest celem ani zagrożeniem
        if STWORY_WIDMA:
            # tylko ZNACZNIK (`widmo`), nic nie znika: PK/czaszki/GM czytają tę listę w całości (patrz widma.py)
            try:
                nick = getattr(self.postac, "nazwa", None)
                widma.loguj(widma.oznacz(lista, nick, wazny=self.gracz_grozny), log, self.zegar(),
                            self.__dict__.setdefault("widma_log", {}))
            except Exception as e:
                log(f"debug: widma: błąd {e!r}")
        return lista

    def bez_widm(self, lista):
        """Lista bez wpisów-widm: do ocen ZAJĘTOŚCI pól i "blokujących" graczy (nie do PK/GM; patrz widma.py)."""
        return widma.bez_widm(lista) if STWORY_WIDMA else lista

    def idz_do(self, cel, poz=None, pilne=False, krok=None):
        """Ruch w stronę cel=(x,y): kliknięciem w mapę (pełna prędkość), a gdy klik nie
        daje ruchu albo jest wyłączony - jednym krokiem strzałką (w stronę `krok`, jeśli podany,
        np. następnego pola drogi). True, gdy jesteśmy w ruchu."""
        if self.klik is None:
            return self.krok_do(krok or cel)
        teraz = self.zegar()
        poz = poz or self.postac.pozycja()
        dx = max(-(ZASIEG_X - 1), min(ZASIEG_X - 1, cel[0] - poz[0]))
        dy = max(-(ZASIEG_Y - 1), min(ZASIEG_Y - 1, cel[1] - poz[1]))
        if (dx, dy) == (0, 0):
            return True
        if poz != self.klik_poz:
            self.klik_poz, self.klik_ruch = poz, teraz
            self.nieudane = 0
        if self.klik_cel is not None and teraz - self.klik_czas > 2 * KLIK_PONOW:
            self.klik_cel = None             # stary klik (np. sprzed walki) już nie prowadzi
        if self.klik_cel is not None and teraz - self.klik_ruch > KLIK_BEZ_RUCHU:
            self.klik_cel = None
            if os.environ.get("CAVEBOT_DEBUG"):
                log(f"debug: klik nie prowadzi, strzałka w stronę {cel} z {poz}")
            return self.krok_do(krok or cel) # klik nie prowadzi (np. ściana, brak drogi) - krok strzałką
        cel_kliku = (poz[0] + dx, poz[1] + dy)
        if self._ogien_na_drodze(poz, cel_kliku):
            return self._ogien_krok(poz, cel_kliku, krok)    # klient poprowadziłby klik przez ogień: idziemy sami
        if self._dziura_na_drodze(poz, cel_kliku):
            self.klik_cel = None
            return self.krok_do(krok or cel)                 # 15.10: klient poprowadziłby klik przez nauczoną dziurę: idziemy sami
        if self.klik_cel is not None and (
                teraz - self.klik_czas < KLIK_ODSTEP
                or (pilne and cel_kliku == self.klik_cel and teraz - self.klik_czas < KLIK_PONOW)
                or (not pilne and teraz - self.klik_czas < KLIK_PONOW and poz[:2] != self.klik_cel
                    and abs(cel_kliku[0] - self.klik_cel[0]) + abs(cel_kliku[1] - self.klik_cel[1]) <= 1)):
            self.pauza(0.08, 0.18)           # postać idzie sama
            return True
        if self.klik_cel is None:
            self.klik_ruch = teraz           # nowa seria klików: czas na ruszenie liczymy od teraz
        if os.environ.get("CAVEBOT_DEBUG"):
            log(f"debug: klik ({dx},{dy}) cel {cel} z {poz} stan {self.stan}")
        self.klik(dx, dy)
        self.ruch_kliki += 1
        self.klik_cel, self.klik_czas = cel_kliku, teraz
        self.pauza(0.15, 0.3)
        return True

    # --- marsz klikiem w patrolu i dojściu (MARSZ_KLIK, 20.10) ---
    # Wzór: serwis.idz_pewnie (klik w najdalsze pole drogi z samych zwykłych pól, obserwacja pozycji, zmiana piętra = koniec).
    # Tu bez blokującej pętli: stan w self.marsz, obserwacja co obieg tick(), więc ucieczka, leczenie, PK i walka mają ten sam
    # priorytet co dotąd. Marsz przechodzi tylko przez _idz_trasa (patrol/dojście); walka, pościg, loot, ucieczka i przejście
    # pięter tam nie wchodzą, więc zostają przy własnych klawiszach i klikach. Klient po kliku idzie sam, dlatego każde
    # wejście innego priorytetu w jego marsz kończy się Escape (zatrzymaj_klik / walcz / zbierz_loot -> _marsz_stop).

    def _marsz_dozwolony(self):
        return bool(MARSZ_KLIK) and self.klik is not None and self.mapa is not None and not self.wypad_aktywny \
            and bool(self.__dict__.get("_w_segmencie") or self.dojscie_aktywne)

    def _marsz_gracz(self):
        """Gracz w zasięgu unikania/mijania: tam zostają kroki klawiszem (klik poprowadziłby klienta własną drogą)."""
        u = self.unikanie
        if u is None:
            return False
        try:
            if getattr(u, "gracze", None) or getattr(u, "duchy", None):
                return True
            return bool(MIJANIE) and bool(u.mijanie_trzyma())
        except Exception:
            return True

    def _marsz_otoczenie(self, poz):
        """(zajęte pola (x, y) włącznie z petem, bez widm; czy w widoku jest cel do walki) albo None, gdy odczyt zawiódł.
        W dojściu (bez walki po drodze, DOJSCIE_BIEGNIJ) cele nie przerywają marszu: zostają tylko zajęte pola."""
        try:
            lista = self.stwory(0.3)
            surowa = getattr(self, "stwory_surowe", None) or lista
            nick = getattr(self.postac, "nazwa", None)
            # własny wpis pomijamy (przy marszu odczyt listy bywa o krok dalej niż `poz`: bez tego pole przed nami wygląda na zajęte)
            zajete = {(s["x"], s["y"]) for s in surowa
                      if s.get("z") == poz[2] and not s.get("widmo") and (s["x"], s["y"]) != tuple(poz[:2])
                      and not (nick and s.get("gracz") and s.get("nazwa") == nick)}
            moby = [] if (self.dojscie_aktywne and DOJSCIE_BIEGNIJ) else \
                self._unikanie_filtr(self.kandydaci(lista, poz), poz)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"debug: marsz: odczyt stworów nie wyszedł ({e!r}), bez marszu klikiem")
            return None
        return zajete, bool(moby)

    def _marsz_zakazane(self, z):
        """Zbiory (x, y) piętra z, przez które klient nie może nas poprowadzić: ogień (bieżący, maska stała, pola parzące),
        drzwi, dziury nauczone."""
        ogien = set(self._ogien_xy(z)) | {(x, y) for (x, y, pz) in self._ogien_stale_ef() if pz == z} \
            | set(self._ogien_parzy_dane(z))
        drzwi = {tuple(e["pole"][:2]) for e in self._drzwi_lista() if e["pole"][2] == z}
        dziury = set()
        if DZIURY_NAUCZONE:
            w = self._wp()
            if w and w.dziury:
                dziury = {(h[0], h[1]) for h in w.dziury if h[2] == z}
        return ogien, drzwi, dziury

    def _marsz_pole_ok(self, xy, z, zajete, zakaz):
        """Zwykłe pole do marszu: przechodnie wg mapy (flaga 1, bez 4), bez flagi 2 (schody/dziury) i bez schodów/dziur w polach
        obok, nie ściana nauczona, nie zmiana piętra, nie ogień/drzwi/dziura nauczona, niezajęte."""
        ogien, drzwi, dziury = zakaz
        if xy in zajete or xy in ogien or xy in drzwi or xy in dziury:
            return False
        f = self.mapa.flagi(xy[0], xy[1], z)
        if not f & 1 or f & 4 or f & 2:
            return False
        p3 = (xy[0], xy[1], z)
        if self.sciana(p3) or self.pole_zmiany_pietra(p3) or self.dziura_nauczona(p3):
            return False
        return not any(self.mapa.flagi(xy[0] + dx, xy[1] + dy, z) & 2 for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    def _marsz_prostokat_czysty(self, poz, pola, zakaz):
        """Klient wybiera własną drogę do kliknięcia i przy obejściu ściany ma równorzędne objazdy po obu stronach, więc sprawdzamy
        prostokąt obejmujący postać i WSZYSTKIE pola odcinka `pola` (nie tylko poz-cel) z marginesem 1: nic z `zakaz` (ogień, drzwi,
        dziury) ani pola z flagą 2."""
        z = poz[2]
        xs = [poz[0]] + [p[0] for p in pola]
        ys = [poz[1]] + [p[1] for p in pola]
        for x in range(min(xs) - 1, max(xs) + 2):
            for y in range(min(ys) - 1, max(ys) + 2):
                if (x, y) == tuple(poz[:2]):
                    continue
                if any((x, y) in s for s in zakaz) or self.mapa.flagi(x, y, z) & 2:
                    return False
        return True

    def _marsz_sciezka(self, poz, prowadz):
        """Planowane pola przed nami (bez pola, na którym stoimy): kolejno sąsiadujące, to samo piętro, w widoku (z zapasem 1 pola),
        najwyżej MARSZ_KLIK_MAKS_POL. Źródło: droga A* (`prowadz`) albo kolejne punkty trasy/odcinka patrolu od self.idx."""
        z = poz[2]
        if prowadz:
            zrodlo = prowadz                      # A* z bieżącej pozycji: zaczyna się przy nas
        else:
            i0 = self._marsz_start_planu(poz)
            if i0 is None:
                return []
            zrodlo = self.punkty[i0:i0 + 12]       # punkty od najbliższej postaci do przodu (nigdy punkty za nami)
        maks = max(2, int(MARSZ_KLIK_MAKS_POL))
        wynik, prev = [], (poz[0], poz[1])
        byly = {prev}
        for q in zrodlo:
            if len(q) > 2 and q[2] != z:
                break
            xy = (q[0], q[1])
            if xy == prev and not wynik:
                continue                          # punkt = pole postaci (jeszcze nie ruszyliśmy dalej)
            if xy in byly:
                break                             # zawrót / odbicie / dopełnienie powtórzonym polem: klik nie może prowadzić z powrotem
            if max(abs(xy[0] - prev[0]), abs(xy[1] - prev[1])) != 1:
                break
            if abs(xy[0] - poz[0]) > ZASIEG_X - 1 or abs(xy[1] - poz[1]) > ZASIEG_Y - 1:
                break
            wynik.append(xy)
            byly.add(xy)
            prev = xy
            if len(wynik) >= maks:
                break
        return wynik

    @staticmethod
    def _marsz_opis(m):
        """Początek każdej linii wyniku marszu: ten sam opis co przy kliku, żeby dało się sparować klik z wynikiem i zmierzyć czas dojścia."""
        return f"[MARSZ] klik na {m['cel']} {m['n']} pól z {tuple(m['poz0'][:2])}"

    def _marsz_start_planu(self, poz):
        """Indeks punktu planu (self.punkty), od którego liczymy ścieżkę marszu: punkt najbliższy postaci w oknie wokół self.idx
        (to samo piętro, Chebyshev <= 1; remis -> bliżej self.idx, potem późniejszy). self.idx bywa w tyle (klik mija kilka punktów
        między obiegami), a start od niego dawałby klik ZA SIEBIE. Zwraca indeks PIERWSZEGO punktu, który wolno wziąć do ścieżki: ten
        najbliższy, gdy sąsiaduje z postacią i leży w planie przed nami (i >= self.idx), inaczej następny. None = postać poza planem.
        Nie zmienia self.idx."""
        pkt, idx = self.punkty, self.idx
        kand = [(max(abs(pkt[i][0] - poz[0]), abs(pkt[i][1] - poz[1])), abs(i - idx), -i)
                for i in range(max(0, idx - 4), min(len(pkt), idx + 12))
                if pkt[i][2] == poz[2] and max(abs(pkt[i][0] - poz[0]), abs(pkt[i][1] - poz[1])) <= 1]
        if not kand:
            return None
        d, _, ni = min(kand)
        i0 = -ni
        return i0 if (d == 1 and i0 >= idx) else i0 + 1

    def _marsz_czysc(self):
        self.marsz = None
        self.klik_cel = None

    def _marsz_stop(self, poz, powod):
        """Ktoś inny przejmuje sterowanie (walka, ucieczka, PK, ogień, loot, pauza): jeśli klient jeszcze idzie, Escape.
        True = wysłano Escape (jak zatrzymaj_klik: Escape zdejmuje też atak, więc wołamy to ZANIM zaczniemy atakować)."""
        m = self.marsz
        if m is None:
            return False
        self._marsz_czysc()
        idzie = tuple(poz[:2]) != m["cel"] and self.zegar() - m["ruch"] < MARSZ_BEZ_RUCHU_S
        if idzie:
            self.postac.klawisz("Escape")
        log(f"[MARSZ] przerwany ({powod}) w {tuple(poz[:2])}, klik na {m['cel']}{', Escape' if idzie else ''}")
        self._patrol_tele("marsz_przerwany", powod=powod, poz=list(poz[:3]), cel=list(m["cel"]), escape=bool(idzie))
        return idzie

    def _marsz_obserwuj(self, m, poz, teraz):
        """Kontrola trwającego marszu (wzór: pętla obserwacji serwisu). "idzie" = klient maszeruje; "koniec" = marsz skończony
        (doszedł, limit, stanął, pole zajęte), można planować następny; "przerwij" = oddajemy sterowanie zwykłej ścieżce
        (zmiana piętra, gracz, cel do walki); "blok" = klik nic nie ruszył, odcinek krokami klawiszem."""
        m["hook"] = teraz
        dt = teraz - m["t0"]
        if poz[2] != m["z"]:
            log(f"[MARSZ] zmiana piętra ({m['z']} -> {poz[2]}) po kliku na {m['cel']}, przerywam")
            self._patrol_tele("marsz_przerwany", powod="zmiana piętra", poz=list(poz[:3]), cel=list(m["cel"]), escape=False)
            self._marsz_czysc()
            return "przerwij"
        if tuple(poz[:2]) != m["ost"]:
            m["ost"], m["ruch"] = tuple(poz[:2]), teraz
        if tuple(poz[:2]) == m["cel"]:
            log(f"{self._marsz_opis(m)}: doszedł w {dt:.1f} s")
            self._patrol_tele("marsz_wynik", wynik="doszedl", n=m["n"], dt=round(dt, 2), cel=list(m["cel"]))
            self._marsz_czysc()
            return "koniec"
        if self._marsz_gracz():
            self._marsz_stop(poz, "gracz w zasięgu unikania")
            return "przerwij"
        ot = self._marsz_otoczenie(poz)
        if ot is not None:
            zajete, cel_walki = ot
            if cel_walki:
                self._marsz_stop(poz, "cel do walki w widoku")
                return "przerwij"
            reszta = m["sciezka"][m["sciezka"].index(tuple(poz[:2])) + 1:] if tuple(poz[:2]) in m["sciezka"] else m["sciezka"]
            if any(p in zajete for p in reszta):
                self._marsz_stop(poz, "pole na drodze zajęte")
                return "koniec"
        if teraz - m["ruch"] > MARSZ_BEZ_RUCHU_S:
            if tuple(poz[:2]) == tuple(m["poz0"][:2]):
                self.marsz_blok = (tuple(poz[:2]), teraz + MARSZ_BLOK_S)
                log(f"{self._marsz_opis(m)}: brak ruchu {dt:.1f} s, krokami klawiszem przez {MARSZ_BLOK_S:.0f} s")
                self._patrol_tele("marsz_wynik", wynik="bez_ruchu", n=m["n"], dt=round(dt, 2), cel=list(m["cel"]))
                self._marsz_czysc()
                return "blok"
            log(f"{self._marsz_opis(m)}: stanął w {tuple(poz[:2])} po {dt:.1f} s")
            self._patrol_tele("marsz_wynik", wynik="stanal", n=m["n"], dt=round(dt, 2), cel=list(m["cel"]))
            self._marsz_czysc()
            return "koniec"
        if dt > m["limit"]:
            log(f"{self._marsz_opis(m)}: limit czasu {m['limit']:.1f} s, jestem w {tuple(poz[:2])}")
            self._patrol_tele("marsz_wynik", wynik="limit", n=m["n"], dt=round(dt, 2), cel=list(m["cel"]))
            self._marsz_czysc()
            return "koniec"
        return "idzie"

    def _marsz_klik(self, poz, prowadz=None):
        """Hak w _idz_trasa przy MARSZ_KLIK=1 (patrol/dojście). True = obieg zużyty (klik, czekanie na marsz klienta albo krok
        klawiszem po braku ruchu); None = idź zwykłą ścieżką (też wtedy, gdy odcinek zwykłych pól ma < 2 pola)."""
        teraz = self.zegar()
        poz = tuple(poz[:3])
        z = poz[2]
        m = self.marsz
        wynik = None
        if m is not None:
            if teraz - m["hook"] > MARSZ_PORZUCONY_S:
                log(f"debug: marsz na {m['cel']} porzucony (obieg poszedł gdzie indziej)")
                self._marsz_czysc()
            else:
                wynik = self._marsz_obserwuj(m, poz, teraz)
                if wynik == "idzie":
                    self.pauza(0.08, 0.18)             # postać idzie sama
                    return True
                if wynik == "przerwij":
                    return None
        b = self.marsz_blok
        if b is not None and (teraz >= b[1] or max(abs(poz[0] - b[0][0]), abs(poz[1] - b[0][1])) > MARSZ_BLOK_R):
            b = self.marsz_blok = None
        if b is not None:
            # klik nic nie ruszył: ten odcinek idzie krokami klawiszem (nieudany krok -> dalej zwykła ścieżka z pomijaniem punktów)
            kroki = self._marsz_sciezka(poz, prowadz)
            self.klik_j = None
            if kroki and self.krok_do((kroki[0][0], kroki[0][1], z)):
                return True
            return None
        if self._marsz_gracz():
            return None
        ot = self._marsz_otoczenie(poz)
        if ot is None or ot[1]:
            return None
        zajete = ot[0]
        pola = self._marsz_sciezka(poz, prowadz)
        if len(pola) < 2:
            return None
        zakaz = self._marsz_zakazane(z)
        k = 0
        while k < len(pola) and self._marsz_pole_ok(pola[k], z, zajete, zakaz):
            k += 1
        while k >= 2 and not self._marsz_prostokat_czysty(poz, pola[:k], zakaz):
            k -= 1
        if k < 2:
            return None
        cel = pola[k - 1]
        if cel == poz[:2]:
            return None                        # klik w pole postaci nigdzie nie prowadzi
        if tuple(self.postac.pozycja()[:3]) != poz:
            self.pauza(0.04, 0.09)             # klik liczymy względem pola postaci: ruszyła się w trakcie planowania, planujemy od nowa
            return True
        try:
            self.klik(cel[0] - poz[0], cel[1] - poz[1])
        except ValueError:
            return None
        self.ruch_kliki += 1
        self.klik_cel, self.klik_czas, self.klik_poz, self.klik_ruch = cel, teraz, poz, teraz
        self.klik_j = None
        self.marsz = {"cel": cel, "poz0": poz, "z": z, "n": k, "t0": teraz, "ost": poz[:2], "ruch": teraz, "hook": teraz,
                      "limit": MARSZ_LIMIT_BAZA_S + MARSZ_LIMIT_POLE_S * k, "sciezka": pola[:k]}
        log(f"[MARSZ] klik na {cel} {k} pól z {poz[:2]}")
        self._patrol_tele("marsz_klik", poz=list(poz), cel=list(cel), n=k)
        self.pauza(0.1, 0.2)
        return True

    def zatrzymaj_klik(self, poz):
        """Postać idzie jeszcze po starym kliku: Escape przerywa marsz (i atak - ponowimy go)."""
        if self.marsz is not None:
            return self._marsz_stop(poz, "inny priorytet")
        if self.klik is None or self.klik_cel is None:
            return False
        idzie = poz[:2] != self.klik_cel and self.zegar() - self.klik_czas < 2 * KLIK_PONOW
        self.klik_cel = None
        if idzie:
            self.postac.klawisz("Escape")
        return idzie

    def krok_do(self, cel):
        """Jeden krok w stronę cel=(x,y[,z]). True, gdy postać się ruszyła.
        Pole, z którego dopiero przyszliśmy, próbujemy dopiero na końcu (o ile nie jest wprost w stronę celu) (inaczej zachłanny krok
        oscyluje w ślepej kieszeni), a krok wstecz nie zeruje licznika nieudanych."""
        x, y, z = self.postac.pozycja()
        teraz = self.zegar()
        self.ruch_strzalki += 1
        wstecz = None
        if self.krok_z is not None and teraz - self.krok_z[1] <= KROK_WSTECZ_S:
            wstecz = self.krok_z[0]
        kier = kierunki_do(x, y, cel[0], cel[1])
        if wstecz is not None:
            def pole(k):
                d = bot.KIERUNKI[k]
                return (x + d[0], y + d[1], z)
            # pierwszy kierunek (prosto do celu) zostaje: zawrócenie do celu leżącego z tyłu to nie oscylacja
            kier = kier[:1] + [k for k in kier[1:] if pole(k) != wstecz] + [k for k in kier[1:] if pole(k) == wstecz]
        pietra_on = self._pietra_wlaczone()
        sk = self._skos_kandydat(x, y, z, cel, pietra_on)
        if sk is not None and all(self.zablokowane.get(((x, y, z), k)) or self._pole_zablokowane(
                (x + bot.KIERUNKI[k][0], y + bot.KIERUNKI[k][1], z), ())
                for k in ("Right" if sk[0] > 0 else "Left", "Down" if sk[1] > 0 else "Up")):
            # 12.10: oba pola w osiach zablokowane (ściana z mapy/nauczona), pole po skosie wolne: skos (róg)
            wynik = self._krok_do_skos(x, y, z, sk, teraz, wstecz)
            if wynik:
                return True
            sk = None
        pierwszy = None                        # KROK_BEZ_SCIAN: pierwszy kierunek, w który faktycznie wcisnęliśmy strzałkę
        # 22.10: stojąc już w buforze parzącego pola, wolno iść po buforze (inaczej postać nie wyjdzie), ale nie na samo pole;
        # pole bufora spoza niego to krok "miękki": tylko gdy żaden inny kierunek nie ruszy (korytarz 1-polowy obok ognia,
        # wydra 08:41 w (32481,32292,z8) biła w ścianę, bo jedyna droga szła polem obok ognia (32480,32294))
        w_buforze = (x, y) in self._ogien_parzy_dane(z)
        miekkie = []

        def odl(p):
            return max(abs(p[0] - cel[0]), abs(p[1] - cel[1]))

        def miekki_krok():
            """Krok na pole obok znanego ognia (samo pole ognia nigdy); True, gdy postać się ruszyła."""
            while miekkie:
                k_ = miekkie.pop(0)
                n_ = (x + bot.KIERUNKI[k_][0], y + bot.KIERUNKI[k_][1], z)
                if self.dziura_nauczona(n_) or (pietra_on and n_[:2] != tuple(cel[:2]) and self.pole_zmiany_pietra(n_)):
                    continue
                if self.postac.krok(k_):
                    log(f"[OGIEN] krok {k_} na pole obok znanego ognia {n_[:2]}: inna droga do celu nie ruszyła")
                    self.zablokowane.clear()
                    self.nieudane = 0
                    self.krok_z = ((x, y, z), teraz)
                    return True
            return False

        zakaz_pominiety = False                # KROK_ZLY: pominięte pole z zakazem (po nim nie cofamy się o pole)
        self.__dict__["krok_zly_blok"] = False
        for k in kier:
            if self.zablokowane.get(((x, y, z), k)):
                continue
            n_pole = (x + bot.KIERUNKI[k][0], y + bot.KIERUNKI[k][1], z)
            if KROK_ZLY and self.sciana(n_pole) and n_pole in self.__dict__.get("sciany_do", {}):
                zakaz_pominiety = True
                self.__dict__["krok_zly_blok"] = True
                continue                       # 22.10: pole z zakazem KROK_ZLY (nie bijemy w nie ponownie)
            if KROK_ZLY and zakaz_pominiety and wstecz is not None and n_pole == wstecz and k != kier[0]:
                continue                       # zakaz na drodze do celu: zawracanie o pole to kręcenie się w kółko, niech patrol zmieni miejsce
            if self._ogien_na(n_pole):
                if n_pole[:2] in self._ogien_parzy_dane(z, bufor=0) or (self._ogien_aktywny() and n_pole in self.ogien_pola):
                    continue                   # pole ognia: nie wchodzimy (najpierw omijanie, potem czekanie)
                if not w_buforze:
                    miekkie.append(k)
                    continue                   # pole obok znanego ognia: dopiero gdy nic nie zbliża do celu
            elif miekkie and odl(n_pole) >= odl((x, y)) and miekki_krok():
                return True                    # krok w bok/wstecz: wcześniej pole obok ognia, które prowadzi do celu
            n_d = (x + bot.KIERUNKI[k][0], y + bot.KIERUNKI[k][1], z)
            if self.dziura_nauczona(n_d) and not (n_d[:2] == tuple(cel[:2]) and self._dziura_w_trasie(n_d)):
                continue                       # 15.10: nauczona dziura (wpadniecie.py): nigdy, chyba że trasa nią schodzi (22.10)
            if pietra_on:
                d = bot.KIERUNKI[k]
                n_xy = (x + d[0], y + d[1])
                if n_xy != (cel[0], cel[1]) and self.pole_zmiany_pietra((n_xy[0], n_xy[1], z)):
                    continue                   # trasa wielopiętrowa: schodów nie wchodzimy "przy okazji" (cel kroku wolno)
            if KROK_BEZ_SCIAN and pierwszy is not None and self._krok_sciana_mapy(
                    (x + bot.KIERUNKI[k][0], y + bot.KIERUNKI[k][1], z)):
                continue                       # po nieudanym pierwszym kierunku: nie bijemy w ścianę z mapy (każda próba ~1,5 s)
            if self.postac.krok(k):
                self.zablokowane.clear()
                d = bot.KIERUNKI[k]
                self._krok_zly_ok((x + d[0], y + d[1], z))
                if wstecz is not None and (x + d[0], y + d[1], z) == wstecz and k != kier[0]:
                    pass                      # krok wstecz (nie w stronę celu): to nie postęp
                else:
                    self.nieudane = 0
                self.krok_z = ((x, y, z), teraz)
                return True
            d_ = bot.KIERUNKI[k]
            n_ = (x + d_[0], y + d_[1], z)
            inni_ = []
            zablok_ = bool(self.sciana(n_))    # 22.10: wcześniej `zablok` czytał słownik tuż przed ustawieniem go (zawsze False)
            try:   # 18.10 diagnostyka: nieudana strzałka kosztuje CZAS_KROKU (1,5 s)
                # 23.10: stwór z innego piętra (np. pająki z z9 widziane z korytarza z8) nie blokuje pola — wcześniej tłumił zakaz
                inni_ = [(q.get("nazwa"), q["x"] - x, q["y"] - y) for q in (self.ostatnie_stwory or ())
                         if (q["x"], q["y"]) == n_[:2] and q.get("z", z) == z]
                log(f"debug: krok {k} z {(x, y, z)} nie ruszył (cel kroku {tuple(cel[:2])}, mapa przechodnie "
                    f"{self.mapa.przechodnie(*n_) if self.mapa else '?'}, na polu {inni_ or '-'}, "
                    f"zablok {zablok_}, nieudane {self.__dict__.get('krok_zly', {}).get(n_, [0])[0] + 1}).")
            except Exception:
                pass
            self._ratunek_zdarzenie("krok_nieudany", (x, y, z))
            self.zablokowane[((x, y, z), k)] = True
            if KROK_ZLY and not inni_ and self._krok_zly_zapis(n_, k):
                zakaz_pominiety = True
            if KROK_BEZ_SCIAN and pierwszy is None:
                pierwszy = k
                d_ = bot.KIERUNKI[k]
                if not self._krok_sciana_mapy((x + d_[0], y + d_[1], z)) and self.postac.krok(k):
                    # pierwszy (przechodni wg mapy) kierunek zawodzi przejściowo: ponowienie raz, zanim ruszymy kolejne kierunki
                    self.zablokowane.clear()
                    self._krok_zly_ok((x + d_[0], y + d_[1], z))
                    if wstecz is not None and (x + d_[0], y + d_[1], z) == wstecz and k != kier[0]:
                        pass
                    else:
                        self.nieudane = 0
                    self.krok_z = ((x, y, z), teraz)
                    return True
        if sk is not None and self._krok_do_skos(x, y, z, sk, teraz, wstecz):
            return True                       # strzałki w osiach nie ruszyły, skos tak
        if miekki_krok():                     # 22.10: jedyna droga wiedzie polem obok znanego ognia (samo pole ognia nigdy)
            return True
        self.nieudane += 1
        self.zablokowane.clear()
        self.pauza(0.3, 0.8)
        return False

    def _krok_sciana_mapy(self, pole):
        """KROK_BEZ_SCIAN: True, gdy mapa jednoznacznie uznaje pole za nieprzechodnie (przechodnie False albo flaga ściany 4);
        pole nieznane (None) to False: wciąż próbujemy."""
        if self.mapa is None:
            return False
        try:
            return self.mapa.przechodnie(*pole) is False or bool(self.mapa.flagi(*pole) & 4)
        except Exception:
            return False

    def _skos_kandydat(self, x, y, z, cel, pietra_on):
        """(dx, dy) skosu w stronę celu, gdy skos awaryjny jest włączony, postać umie skos, a pole po skosie nie jest
        zablokowane (ściana z mapy/nauczona, zmiana piętra, świeżo nieudany skos); inaczej None."""
        if not (POSCIG_SKOS_AWARYJNY or POSCIG_SKOSY_ZAPAS) or not hasattr(self.postac, "krok_skos"):
            return None
        dx, dy = cel[0] - x, cel[1] - y
        if not dx or not dy:
            return None
        v = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))
        pole = (x + v[0], y + v[1], z)
        if self.sciana(pole) or self._ogien_na(pole) or self.dziura_nauczona(pole):
            return None
        if self.mapa is not None:
            try:
                if self.mapa.flagi(*pole) & 1 and self.mapa.przechodnie(*pole) is False:
                    return None
            except Exception:
                pass
        if pietra_on and pole[:2] != (cel[0], cel[1]) and self.pole_zmiany_pietra(pole):
            return None
        if BLOK_WYJSCIE and any((q["x"], q["y"], q["z"]) == pole and q.get("hp", 100) > 0
                                and not (q.get("gracz") and q.get("nazwa") == self.postac.nazwa)
                                and not q.get("widmo")
                                for q in self.ostatnie_stwory):
            return None          # pole skosu zajęte przez żywego stwora
        if self.skos_zle.get(((x, y), pole[:2]), 0) > self.zegar():
            return None
        if self.zablokowane.get(((x, y, z), "skos")):
            return None
        return v

    # --- drzwi (R1c): przejście dla pościgu i patrolu, zamknięte = Use z pola obok ---

    def _drzwi_lista(self):
        """Drzwi z PLIK_DRZWI: [{"pole": (x,y,z)}]; brak pliku albo błąd = pusta lista."""
        if self.drzwi_def is None:
            wynik = []
            try:
                for e in json.loads(Path(PLIK_DRZWI).read_text()).get("drzwi") or []:
                    q = e["pole"]
                    h = (int(q[0]), int(q[1]), int(q[2]))
                    dx, dy = (1, 0) if e.get("os", "x") == "x" else (0, 1)
                    wynik.append({"pole": h, "id": e.get("id", str(q)),
                                  "strony": [(h[0] - dx, h[1] - dy, h[2]), (h[0] + dx, h[1] + dy, h[2])]})
            except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError):
                wynik = []
            wynik.extend(self._drzwi_klucz_lista(wynik))
            self.drzwi_def = wynik
        return self.drzwi_def

    def _drzwi_klucz_lista(self, juz):
        """24.10: drzwi zamknięte na klucz (wyprawa.PLANY_PK["klucze"] = jedno źródło, test_powrot_abdendriel pilnuje zgodności z
        generuj_powrot_abdendriel.KLUCZE_DRZWI) jako przejście, TYLKO w dojściu (CavebotDojscie): dojście z korytarza przed drzwiami nie miało drogi (drzwi to
        ściana w mapie). Pole -> {"pole","id","strony","klucz"}; oś z mapy (pola po obu stronach przechodnie). Brak klucza/błąd = pusta lista."""
        if not DRZWI_KLUCZ or not getattr(self, "dojscie_aktywne", False) or getattr(self, "mapa", None) is None:
            return []                         # bez mapy nie ma A* przez drzwi ani osi drzwi
        try:
            import wyprawa  # noqa: PLC0415
            klucze = [(tuple(int(v) for v in d), int(k)) for p in wyprawa.PLANY_PK for d, k in (p.get("klucze") or ())]
        except Exception:
            return []
        znane = {e["pole"] for e in juz}
        wynik = []
        for h, k in klucze:
            if h in znane:
                continue
            os_y = False
            try:
                m = self.mapa
                prz = lambda x, y: bool(m.flagi(x, y, h[2]) & 1) and not m.flagi(x, y, h[2]) & 6    # noqa: E731  (flaga 4 = ściana/blokada, 2 = dziura)
                os_y = prz(h[0], h[1] - 1) and prz(h[0], h[1] + 1) and not (prz(h[0] - 1, h[1]) and prz(h[0] + 1, h[1]))
            except Exception:
                os_y = False
            dx, dy = (0, 1) if os_y else (1, 0)
            wynik.append({"pole": h, "id": f"klucz_{h[0]}_{h[1]}", "klucz": k,
                          "strony": [(h[0] - dx, h[1] - dy, h[2]), (h[0] + dx, h[1] + dy, h[2])]})
        return wynik

    def _drzwi_xy(self, z):
        """Zbiór (x, y) drzwi na piętrze z, które teraz są przejściem (PATROL_DRZWI=1, nie odpuszczone)."""
        if not PATROL_DRZWI:
            return frozenset()
        t = self.zegar()
        return frozenset(e["pole"][:2] for e in self._drzwi_lista()
                         if e["pole"][2] == z and self.drzwi_stan.get(e["pole"], {}).get("zle_do", float("-inf")) <= t)

    def _drzwi_na_krokach(self, e):
        """Czy któryś krok łącznika to odpuszczone drzwi."""
        t = self.zegar()
        zle = {h["pole"] for h in self._drzwi_lista() if self.drzwi_stan.get(h["pole"], {}).get("zle_do", float("-inf")) > t}
        return bool(zle) and any(tuple(q) in zle for q in e["kroki"])

    def _drzwi_hak(self, poz, dalej, podejscie=False, tylko_klucz=False):
        """Drzwi na najbliższych polach drogi `dalej`, stoimy obok (w osi): zwykły krok/klik, a bez ruchu przez
        DRZWI_KROK_S s drzwi są zamknięte: Use z tego pola (max DRZWI_PROB), potem odpuszczenie z jedną notatką na
        DRZWI_ODPUSC_S s. None = nic (idź normalnie), True = obieg zużyty (Use), False = drzwi nie działają.
        podejscie=True (patrol, marsz klikiem): drzwi na drodze, jeszcze niepotwierdzone jako otwarte, dochodzimy do
        nich krokami strzałek (klik za zamknięte drzwi nie prowadzi nigdzie)."""
        if not PATROL_DRZWI:
            return None
        poz = tuple(poz[:3])
        t = self.zegar()
        for e in self._drzwi_lista():
            h = e["pole"]
            if poz[2] != h[2] or (tylko_klucz and not e.get("klucz")):
                continue
            st = self.drzwi_stan.setdefault(h, {"poz": None, "t0": t, "proby": 0, "zle_do": float("-inf"), "nota": False,
                                                "otw": False})
            odl = self.dystans(poz, h)
            na_drodze = any(tuple(q[:2]) == h[:2] for q in dalej if len(q) < 3 or q[2] == h[2])
            if st["zle_do"] <= t and st["nota"]:
                st["nota"] = False             # odpuszczenie wygasło: kolejne może znów dać notatkę
            if st["poz"] is not None and st["zle_do"] <= t and t - st["t0"] > DRZWI_STARA_S:
                st["proby"], st["poz"] = 0, None   # stary epizod (odeszliśmy): zaczynamy od nowa
            if poz[:2] == h[:2]:
                st["otw"] = True               # staliśmy na kafelku drzwi: są otwarte
                st["otw_t"] = t
                st["proby"], st["poz"] = 0, None
            if odl >= 2 or poz[:2] == h[:2]:
                otw = st["otw"]
                if otw and DRZWI_PONOW and t - st.get("otw_t", float("-inf")) > DRZWI_STARA_S:
                    otw = False                # DRZWI_PONOW: flaga przeterminowana, nie ufamy jej
                if podejscie and na_drodze and odl >= 2 and not otw and st["zle_do"] <= t and odl <= 8:
                    nast = next((q for q in dalej if self.dystans(poz, q) >= 1 and (len(q) < 3 or q[2] == poz[2])), None)
                    if nast is not None:
                        self.krok_do(nast)     # klik za zamknięte drzwi nie prowadzi: podchodzimy strzałkami
                        return True
                continue
            if not na_drodze:
                continue
            if poz[0] != h[0] and poz[1] != h[1]:
                # Use tylko z pola obok w osi: ze skosu (krok_do potrafi zejść w bok) wracamy na pole po tej stronie drzwi
                if podejscie and not st["otw"] and st["zle_do"] <= t:
                    bok = min(e["strony"], key=lambda q: self.dystans(poz, q))
                    if self.dystans(poz, bok) == 1:
                        self.krok_do(bok)
                        return True
                continue
            if st["zle_do"] > t:
                return False
            self.sciany.pop(h, None)        # zamknięte drzwi nie są ścianą (sprawdz_krok mógł ją nauczyć)
            self._krok_zly_ok(h)
            if st["poz"] is None:
                st["poz"], st["t0"] = poz, t       # nowy epizod: najpierw zwykły krok/klik
                return None
            if t - st["t0"] < DRZWI_KROK_S:
                return None
            if st["proby"] >= DRZWI_PROB:
                st["zle_do"] = t + DRZWI_ODPUSC_S
                st["proby"] = 0
                st["poz"] = None
                st["otw"] = False
                if not st["nota"]:
                    st["nota"] = True
                    log(f"Drzwi {h[:2]} z{h[2]} nie otwierają się po {DRZWI_PROB} próbach, odpuszczam na {DRZWI_ODPUSC_S:.0f} s.")
                return False
            if DRZWI_SPOKOJ and self._drzwi_spokoj()[:2] != poz[:2]:
                return True                    # 22.10: Use w trakcie kroku klient gubi; coś nas przesunęło - nowy obieg (próba nie liczona)
            kier = None
            klucz = e.get("klucz")
            if DRZWI_NAJPIERW_KROK or klucz:
                # 24.10: przed Use krok przez pole drzwi na stojącej postaci (Use na otwartych drzwiach je zamyka); ruszyła = drzwi były otwarte
                # (drzwi na klucz: ZAWSZE najpierw krok, jak wypad._drzwi: krok, klucz, krok)
                kier = ("Right" if h[0] > poz[0] else "Left") if h[0] != poz[0] else ("Down" if h[1] > poz[1] else "Up")
                if self.postac.krok(kier) or self.postac.krok(kier):    # dwa razy: pojedynczy krok bywa zgubiony, a zbędny Use zamyka otwarte drzwi
                    return self._drzwi_hak_krok_ok(h, st, t)
            st["proby"] += 1
            if klucz:
                log(f"Drzwi {h[:2]} z{h[2]} (na klucz {klucz}): zamknięte, klucz z {poz[:2]} (próba {st['proby']}/{DRZWI_PROB}).")
            else:
                log(f"Drzwi {h[:2]} z{h[2]}: zamknięte, Use z {poz[:2]} (próba {st['proby']}/{DRZWI_PROB}).")
            try:
                if klucz:
                    self._drzwi_ops().uzyj_klucz(klucz, h, poz)       # 24.10: Ctrl+klik na kluczu w plecaku, klik na drzwiach (wypad.uzyj_klucz)
                else:
                    self._drzwi_ops().uzyj_pole(h, poz)
            except bot.Zatrzymano:
                raise
            except Exception as ex:
                if klucz and type(ex).__name__ == "BrakPrzedmiotu":
                    st["proby"] = DRZWI_PROB      # brak klucza w otwartych pojemnikach: nie ponawiamy, następny obieg odpuszcza z notatką
                    log(f"Drzwi {h[:2]} z{h[2]}: brak klucza {klucz} w otwartych pojemnikach ({ex}).")
                else:
                    log(f"Drzwi {h[:2]}: {'klucz' if klucz else 'Use'} nie wyszło ({ex!r}).")
            self.pauza(0.6, 1.0)
            st["t0"] = self.zegar()
            if kier is not None and self.postac.krok(kier):
                return self._drzwi_hak_krok_ok(h, st, st["t0"])    # 24.10: po Use znowu krok
            return True
        return None

    def _drzwi_klucz_tick(self, poz, cel):
        """24.10: dojście przez drzwi zamknięte na klucz. Bierze najbliższe pola drogi A* do punktu trasy `cel` (A* prowadzi przez drzwi, bo
        _drzwi_lista zna je w dojściu; bez A* - najbliższe punkty trasy) i oddaje je _drzwi_hak(tylko_klucz=True). True = obieg zużyty."""
        z = poz[2]
        if not any(e.get("klucz") and e["pole"][2] == z for e in self._drzwi_lista()):
            return None
        dalej = None
        if cel[2] == z:
            dalej = self._droga_trasy(poz, cel)
            if not dalej:
                try:
                    dalej = self.droga(tuple(poz), tuple(cel[:2]), dlugosc=0)
                except Exception:
                    dalej = None
        n = len(self.punkty)
        dalej = list(dalej[:3]) if dalej else [self.punkty[(self.idx + i) % n] for i in range(min(3, n))]
        return True if self._drzwi_hak(poz, dalej, True, tylko_klucz=True) is True else None

    def _drzwi_hak_krok_ok(self, h, st, t):
        """24.10: krok przez pole drzwi (przed albo po Use) ruszył postać: drzwi są otwarte, epizod kończy się bez dalszych Use."""
        st["otw"], st["otw_t"] = True, t
        st["proby"], st["poz"] = 0, None
        self.zablokowane.clear()
        self.nieudane = 0
        self.sciany.pop(h, None)
        self._krok_zly_ok(h)
        return True

    def _drzwi_ops(self):
        """Operacje na ekranie (Use na polu): jak w pietra.py (wstrzyknięte, z wyprawy albo wypad.OperacjeZywe)."""
        o = self.pietra_ops
        if o is None:
            o = getattr(self.wyprawa, "ops", None)
        if o is None:
            import wypad  # noqa: PLC0415
            o = wypad.OperacjeZywe(log=lambda t: log(t))
        self.pietra_ops = o
        return o

    # --- drzwi na nagranej trasie (22.10): dojście i trasa; wykrywanie w trasa_io.drzwi_na_trasie ---

    def _drzwi_spokoj(self):
        """22.10: czeka, aż pozycja stoi (2 odczyty co 0,4 s, do 1,6 s), jak pietra._przed_use: Use (Ctrl+klik) w trakcie
        kroku klient gubi. Zwraca bieżącą pozycję (x, y, z)."""
        ost = tuple(self.postac.pozycja())
        for _ in range(4):
            self.spij(0.4)
            p = tuple(self.postac.pozycja())
            if p == ost:
                break
            ost = p
        return ost

    def _drzwi_trasy(self):
        """Drzwi na bieżącej trasie (trasa_io.drzwi_na_trasie); lista pamiętana do zmiany punktów (odwrócenie trasy)."""
        pk = self.punkty
        if not pk or self.mapa is None:
            return []
        klucz = (id(pk), len(pk), tuple(pk[0]), tuple(pk[-1]))
        c = self.__dict__.get("_drzwi_tr_cache")
        if c is None or c[0] != klucz:
            try:
                import trasa_io  # noqa: PLC0415
                znane = {h["pole"] for h in self._drzwi_lista()}      # drzwi z PLIK_DRZWI obsługuje _drzwi_hak (PATROL_DRZWI), nie dublujemy
                lista = [e for e in trasa_io.drzwi_na_trasie(pk, self.mapa) if e["pole"] not in znane]
            except Exception:
                lista = []
            c = self.__dict__["_drzwi_tr_cache"] = (klucz, lista)
        return c[1]

    def _drzwi_trasa_tick(self, poz):
        """22.10 (invincible 10:52, dojście edron_depo_trolle: 10x „krok Down nie ruszył” w zamknięte drzwi (33166,31817,z7), które
        leżą MIĘDZY punktami trasy; wydra: Use w trakcie ruchu): gdy tuż przed nami (okno punktów trasy) są zamknięte drzwi z trasy,
        dochodzimy na pole przed nimi (A* bez drzwi, żadne ścinanie zakrętu przez ścianę), tam stajemy: pierwszy raz sam krok
        (drzwi mogą stać otwarte), potem czekanie na stojącą pozycję, Use na drzwiach, ~0,6-1 s i krok. Po DRZWI_TRASA_PROB nieudanych
        Use drzwi są odpuszczone na DRZWI_TRASA_ODPUSC_S s (jedna notatka) i trasa idzie po staremu. True = obieg zużyty, None = nic."""
        if not DRZWI_TRASA or self.mapa is None:
            return None
        poz = tuple(poz[:3])
        t = self.zegar()
        stany = self.__dict__.setdefault("_drzwi_tr_stan", {})
        for e in self._drzwi_trasy():
            h = e["pole"]
            if h[2] != poz[2] or not (e["po"] - DRZWI_TRASA_OKNO <= self.idx <= e["po"] + 2):
                continue
            we = e["wejscie"]
            kr = e["kier"]
            if (poz[0] - h[0]) * kr[0] + (poz[1] - h[1]) * kr[1] >= 0 or self.dystans(poz, we) > DRZWI_TRASA_ODL:
                continue                          # na drzwiach / za nimi (po drugiej stronie osi, także z boku) albo daleko: nic do roboty
            st = stany.setdefault(h, {"proby": 0, "krok": False, "zle_do": float("-inf"), "nota": False, "t": t, "bledy": 0})
            if st["zle_do"] > t:
                continue
            if st["nota"]:
                st["nota"] = False                # odpuszczenie wygasło
            if t - st["t"] > DRZWI_STARA_S:
                st["proby"], st["krok"], st["bledy"] = 0, False, 0     # stary epizod: od nowa
            st["t"] = t
            if poz[:2] != we[:2]:
                # podejście na pole przed drzwiami: A* bez pola drzwi, krok po kroku (strzałki), nigdy skrót przez ścianę
                d = self.droga(poz, we[:2], [h], 0, skosy=False)
                ruszyl = self.krok_do(d[0] if d else we)
                st["bledy"] = 0 if ruszyl else st["bledy"] + 1
                if st["bledy"] >= 8:
                    return self._drzwi_trasa_odpusc(h, st, t, "nie mogę dojść na pole przed drzwiami")
                return True
            kier = {(0, 1): "Down", (0, -1): "Up", (1, 0): "Right", (-1, 0): "Left"}[tuple(e["kier"])]
            if DRZWI_NAJPIERW_KROK:
                # 24.10: KAŻDY obieg zaczyna się krokiem (nie tylko pierwszy w epizodzie): drzwi stoją otwarte (zostawione otwarte po
                # poprzednim przejściu, Use sprzed chwili, ktoś je otworzył), a Use na otwartych je ZAMYKA (odchyd 11:34:31: Use, Use, dopiero krok)
                st["krok"] = True
                if self.postac.krok(kier):
                    return self._drzwi_trasa_ok(h, st)
                if DRZWI_SPOKOJ:
                    if self._drzwi_spokoj() != poz:
                        return True               # coś nas przesunęło: nowy obieg (próba nie liczona)
                if self.postac.krok(kier):
                    return self._drzwi_trasa_ok(h, st)   # krok zgubiony w animacji poprzedniego (jak 11:34:31) - na stojącej postaci przeszedł
            elif not st["krok"]:
                st["krok"] = True                 # pierwszy raz sam krok: drzwi mogą stać otwarte (zamknięte nic nie zmienią)
                if self.postac.krok(kier):
                    return self._drzwi_trasa_ok(h, st)
            if st["proby"] >= DRZWI_TRASA_PROB:
                return self._drzwi_trasa_odpusc(h, st, t, f"nie otwierają się po {DRZWI_TRASA_PROB} próbach")
            if DRZWI_SPOKOJ and not DRZWI_NAJPIERW_KROK:
                if self._drzwi_spokoj() != poz:
                    return True                   # coś nas przesunęło: nowy obieg (próba nie liczona)
            st["proby"] += 1
            log(f"Drzwi {h[:2]} z{h[2]} (trasa): zamknięte, Use z {poz[:2]} (próba {st['proby']}/{DRZWI_TRASA_PROB}).")
            try:
                self._drzwi_ops().uzyj_pole(h, poz)
            except bot.Zatrzymano:
                raise
            except Exception as ex:
                log(f"Drzwi {h[:2]} (trasa): Use nie wyszło ({ex!r}).")
            self.pauza(0.6, 1.0)
            if self.postac.krok(kier):
                return self._drzwi_trasa_ok(h, st)
            return True
        return None

    def _drzwi_trasa_ok(self, h, st):
        st["proby"], st["krok"], st["bledy"] = 0, False, 0
        self.zablokowane.clear()
        self.nieudane = 0
        self.sciany.pop(h, None)
        self._krok_zly_ok(h)
        return True

    def _drzwi_trasa_odpusc(self, h, st, t, powod):
        st["zle_do"] = t + DRZWI_TRASA_ODPUSC_S
        st["proby"], st["krok"], st["bledy"] = 0, False, 0
        if not st["nota"]:
            st["nota"] = True
            log(f"Drzwi {h[:2]} z{h[2]} (trasa): {powod}, odpuszczam na {DRZWI_TRASA_ODPUSC_S:.0f} s.")
        return None

    def _krok_do_skos(self, x, y, z, v, teraz, wstecz):
        """Jeden krok po skosie numpadem (postac.krok_skos). True, gdy postać się ruszyła; porażka zapisuje się
        w `zablokowane` i skos_zle (nie jako ściana)."""
        pole = (x + v[0], y + v[1], z)
        self.krok_prosto_ost = None
        self.skos_ost = ((x, y), pole[:2])
        if self.postac.krok_skos(*v):
            self.zablokowane.clear()
            if wstecz is None or pole != wstecz:
                self.nieudane = 0
            self.krok_z = ((x, y, z), teraz)
            self.skos_awaryjny_n += 1
            self._d3_nota("krok_skos")
            if teraz - self._skos_log_t >= SKOS_LOG_S:
                self._skos_log_t = teraz
                log(f"Skos awaryjny: krok ({v[0]},{v[1]}) z ({x},{y}), pola w osiach zablokowane.")
            return True
        self.zablokowane[((x, y, z), "skos")] = True
        self.skos_zle[((x, y), pole[:2])] = teraz + SKOS_ZLY_S
        if teraz - self.__dict__.get("_skos_fail_log_t", float("-inf")) >= SKOS_LOG_S:   # 24.10: porażka skosu była cicha (wydra 12:21-12:23)
            self._skos_fail_log_t = teraz
            try:
                mp = self.mapa.przechodnie(*pole) if self.mapa else "?"
            except Exception:
                mp = "?"
            log(f"Skos awaryjny: krok ({v[0]},{v[1]}) z ({x},{y}) NIE ruszył (pole {pole[:2]}, mapa przechodnie "
                f"{mp}); ponowię najwcześniej za {SKOS_ZLY_S:.0f} s.")
        return False

    @staticmethod
    def dystans(a, b):
        return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

    # --- decyzje ---

    @staticmethod
    def w_widoku(s, poz):
        return s["z"] == poz[2] and abs(s["x"] - poz[0]) <= ZASIEG_X and abs(s["y"] - poz[1]) <= ZASIEG_Y

    def inni_gracze(self, lista, poz):
        st = self.stanowisko
        return [s for s in lista if s["gracz"] and s["nazwa"] != self.postac.nazwa and s["z"] == poz[2]
                and abs(s["x"] - poz[0]) <= ZASIEG_X and abs(s["y"] - poz[1]) <= ZASIEG_Y
                and not (st is not None and st.ignoruj(s))]          # 22.10: NPC w mieście to nie obcy gracz

    def ignorowany(self, s, poz, teraz):
        """True, gdy potwór jest ignorowany. Zwykłe ignorowanie kończy się, gdy podejdzie na
        IGNOROWANIE_BLISKO; "nieosiągalny" (droga długa albo brak) - dopiero gdy dystans prosty
        zmaleje o NIEOSIAGALNY_ZBLIZENIE pól (albo stoi obok i gryzie), albo po upływie czasu."""
        if self.ignorowane.get(s["id"], 0) <= teraz:
            self.nieosiagalne.pop(s["id"], None)
            return False
        d = self.dystans((s["x"], s["y"]), poz)
        zapis = self.nieosiagalne.get(s["id"])
        pw = self.ignor_powod.get(s["id"]) if IGNOR_TWARDE else None
        powod = pw[0] if pw and pw[1] == self.ignorowane.get(s["id"]) else None
        if powod in ("limit_walki", "atak_klik", "straznik"):
            # twarde ignorowanie do końca czasu bez względu na odległość; wyjątek: cel obok nas bije
            # (straznik jest bezwzględny: cel stał obok bez postępu, ponowny wybór by zapętlił)
            if powod == "straznik" or not (d <= 1 and teraz - self.hp_gracza_spadek < GRYZIE_OKNO):
                return True
        elif zapis is not None:
            if d > 1 and d > zapis - NIEOSIAGALNY_ZBLIZENIE:
                return True
            del self.nieosiagalne[s["id"]]
        elif powod == "sciana":
            # za ścianą: zdejmujemy tylko, gdy stoi obok albo otworzyła się droga (nie objazd)
            if d > 1 and not self._ignor_droga_otwarta(s, poz, d, teraz):
                return True
        elif d > IGNOROWANIE_BLISKO:
            return True
        del self.ignorowane[s["id"]]   # podszedł blisko: oceniamy go od nowa
        self.ignor_powod.pop(s["id"], None)
        return False

    def _ignoruj(self, id_, do, powod):
        """Ignorowanie celu do czasu `do` z powodem (IGNOR_TWARDE: patrz ignorowany())."""
        self.ignorowane[id_] = do
        self.ignor_powod[id_] = (powod, do)

    def _ignor_droga_otwarta(self, s, poz, d, teraz):
        """Czy do ignorowanego "za ścianą" potwora jest teraz droga (nie objazd). Cache IGNOR_DROGA_CO_S na id."""
        c = self.ignor_droga_cache.get(s["id"])
        if c is not None and teraz - c[0] < IGNOR_DROGA_CO_S:
            return c[1]
        zapas = self.ostatni_blokujacy
        try:
            zajete = [(m["x"], m["y"]) for m in self.ostatnie_stwory
                      if m["z"] == poz[2] and m["id"] != s["id"] and m.get("hp", 100) > 0
                      and (m["x"], m["y"]) != tuple(poz[:2])
                      and not (m.get("gracz") and m.get("nazwa") == self.postac.nazwa) and not m.get("widmo")]
            c_xy = (s["x"], s["y"])
            dr = self.droga(tuple(poz[:3]), c_xy, zajete, 1, skosy=False)
            limit = 2 * d + (MAPA_OBJAZD if self.mapa_zna(poz, c_xy) else DROGA_OBJAZD)
            ok = dr is not None and len(dr) <= limit
            if dr is None and POSCIG_SKOSY_ZAPAS and self._skos_mozliwy():
                # R1c: korytarz chodliwy tylko po skosie: droga ze skosami też otwiera ignorowanego "za ścianą"
                dr = self.droga(tuple(poz[:3]), c_xy, zajete, 1, skosy=True)
                ok = dr is not None and len(dr) <= min(limit, POSCIG_SKOSY_MAX_DL)
        except bot.Zatrzymano:
            raise
        except Exception:
            ok = False
        self.ostatni_blokujacy = zapas
        self.ignor_droga_cache[s["id"]] = (teraz, ok)
        return ok

    def _log_odpuszczenia(self, cel, tekst, teraz):
        """Log "Odpuszczam ...: za ścianą" najwyżej raz na ODPUSZCZ_LOG_S s na id (IGNOR_TWARDE)."""
        if IGNOR_TWARDE:
            if teraz - self.odpuszczenie_log.get(cel["id"], float("-inf")) < ODPUSZCZ_LOG_S:
                return
            self.odpuszczenie_log[cel["id"]] = teraz
            if len(self.odpuszczenie_log) > 200:
                self.odpuszczenie_log = {k: v for k, v in self.odpuszczenie_log.items() if teraz - v < 60}
        log(tekst)

    def _blokujacy_wyjscia(self, cel, kand, poz, teraz):
        """BLOK_WYJSCIE: droga do `cel` bez stworów prowadziła przez pole zajęte przez potwora obok nas
        (jedyne wyjście, np. zaułek): zamiast odpuszczać cel, rozprawa z blokującym (ROZPRAWA_BLOK_MAX s,
        potem powrót do `cel`). Zwraca blokującego albo None."""
        if not BLOK_WYJSCIE or not self.ostatni_blokujacy:
            return None
        pole, id_ = self.ostatni_blokujacy
        if kand is None:
            kand = self.kandydaci(self.ostatnie_stwory, poz)
        m = next((s for s in kand if s["id"] == id_ and s["id"] != cel["id"]), None)
        if m is None or self.dystans((m["x"], m["y"]), poz) > 1:
            return None
        log(f"Wyjście zablokowane przez {m['nazwa']} ({m['x']},{m['y']}), bije blokującego (cel {cel['nazwa']}).")
        self.rozprawa = {"id": m["id"], "wroc": cel["id"], "do": teraz + ROZPRAWA_BLOK_MAX}
        self.ostatni_blokujacy = None
        return m

    @staticmethod
    def gracz_grozny(s):
        """GM/CM/God/Tutor po nicku albo czaszka/PK. Rdzeń (rdzen.py stwory) NIE czyta czaszki z pamięci gry; źródłem jest
        odczyt ze zrzutu przez Haiku (czaszka.py, biała/czerwona) albo pole "czaszka"/"skull"/"pk" w odczycie stworów.
        Uwaga: gdy PK_OBRONA=1, gracz z groźną czaszką uruchamia ucieczkę do depo (_pk_tick) PRZED tym warunkiem;
        stan GRACZ (stój i alarmuj) zostaje dla GM/CM/God/Tutor i dla PK_OBRONA=0."""
        if GM_NAZWA.search(s.get("nazwa") or ""):
            return True
        if czaszka.czaszka_grozna(s.get("nazwa")):   # 15.10: czaszka odczytana ze zrzutu (czaszka.py, Haiku)
            return True
        return bool(s.get("czaszka") or s.get("skull") or s.get("pk"))

    def _wpadniecie_bij(self, s, poz):
        """23.10: stwór spoza --potwory zagradzający wyjście z kieszeni po wpadnięciu (wpadniecie.bij_potwora)."""
        if not WPADNIECIE_BIJ or not WPADNIECIE or not self.__dict__.get("wpadniecie"):
            return False
        try:
            return bool(self.wpadniecie.bij_potwora(s, poz))
        except Exception as e:                    # noqa: BLE001
            log(f"debug: wpadniecie.bij_potwora błąd {e!r}")
            return False

    def _wpadniecie_bez_drogi(self, poz):
        """23.10: wpadnięcie w toku i z tego piętra nie ma drogi do trasy (kieszeń): wyjście (drabina/lina) ma pierwszeństwo przed UCIECZKĄ."""
        if not WPADNIECIE_UCIECZKA or not WPADNIECIE:
            return False
        try:
            wp = self._wp()
            return bool(wp) and wp.bez_drogi(poz)
        except Exception as e:                    # noqa: BLE001
            log(f"debug: wpadniecie.bez_drogi błąd {e!r}")
            return False

    @staticmethod
    def _cele_pierwsze():
        """24.10: zbiór nazw (casefold) z pokrętła CELE_PIERWSZE; pusty = mechanizm wyłączony."""
        global _CP_CACHE
        t = CELE_PIERWSZE
        if _CP_CACHE[0] != t:
            _CP_CACHE = (t, frozenset(n.strip().casefold() for n in str(t or "").split(",") if n.strip()))
        return _CP_CACHE[1]

    def _cel_pierwszy(self, s):
        """True = potwór `s` jest na liście CELE_PIERWSZE (np. Wasp: trucizna)."""
        return str(s.get("nazwa", "")).casefold() in self._cele_pierwsze()

    def kandydaci(self, lista, poz):
        teraz = self.zegar()
        wynik = []
        for s in lista:
            if s["gracz"] or s["z"] != poz[2] or s.get("hp", 100) <= 0:
                continue
            if self.pet is not None and self.pet.pet_id == s.get("id"):
                continue                # pet nie jest celem (lista z stwory() jest już bez niego; tu dla wywołań z gotową listą)
            if abs(s["x"] - poz[0]) > ZASIEG_X or abs(s["y"] - poz[1]) > ZASIEG_Y:
                continue
            if self.stoj_wl and self.dystans((s["x"], s["y"]), poz) > 1:
                continue                # 23.10 STÓJ: bijemy tylko to, co stoi obok (bez pościgu i podejścia)
            if self.potwory is not None and s["nazwa"].casefold() not in self.potwory \
                    and self.__dict__.get("blokada_bij", {}).get(s.get("id"), float("-inf")) < teraz \
                    and not self._wpadniecie_bij(s, poz):
                continue                # 23.10: wyjątek = stwór spoza listy, który zasłania jedyny krok drogi (_blokada_bij_tick)
            if self.pole_zmiany_pietra((s["x"], s["y"], s["z"])) and self.dystans((s["x"], s["y"]), poz) > 1:
                continue        # stoi na schodach/dziurze: nie gonimy (pościg zmieniłby piętro)
            # ignorowany (np. po nieudanym pościgu), chyba że stoi obok i nas gryzie
            if self.ignorowany(s, poz, teraz):
                continue
            wynik.append(s)
        return wynik

    def tick(self):
        """Jeden obieg decyzyjny. Zwraca False, gdy trasa/limit się skończyły."""
        bot.sprawdz_stop()
        if self.wylogowany:
            return False                    # 23.10: wylogowanie już ogłoszone: proces się kończy, żadnych akcji
        self._stanowisko_sync()
        if SMIERC_STOP and self.martwy:
            return True                     # MARTWY: żadnych zapytań, kliknięć ani modelu; STOP kończy pętlę
        if ROZLACZENIE_STOP and self.rozlaczony:
            return self._rozl_pauza()       # 21.10: rozłączony klient: własny odczyt (odporny na błędy), zero klawiszy
        if self.czas_s and self.zegar() - self.start >= self.czas_s:
            log("Upłynął limit czasu.")
            return False
        if self.okrazenia and self.okrazenie >= self.okrazenia:
            log("Wykonano zadaną liczbę okrążeń.")
            return False
        self.walka_odl_tick = None          # Q5 11.10: ustawia walcz() w tym obiegu (pauza po ticku zależy od odległości)
        t_start = self.zegar()
        try:
            g = self.gracz()
            self.g_tick = g
            poz = self.postac.pozycja()
        except (bot.Zatrzymano, KeyboardInterrupt):
            raise
        except Exception as e:
            if ROZLACZENIE_STOP and ROZLACZENIE_WYJSCIE and self._brak_postaci_tick(e):
                return False                # 23.10: postaci nie ma w pamięci, a zrzut = ekran logowania: wylogowanie, koniec procesu
            raise
        if self._brak_postaci is not None:
            self._brak_postaci.ok()
        teraz = self.zegar()
        self._stoj_sync(poz, teraz)             # 23.10: przełącznik STÓJ (plik instancje/<id>/STOJ), na gorąco
        fazy = {"gracz": teraz - t_start}
        if ROZLACZENIE_STOP and self._rozl_tick(g, poz, teraz):
            return not self.wylogowany      # 21.10: wylogowany klient wykryty w tym obiegu (przed SMIERC, PK, walką, lootem i modelem)
        if SMIERC_STOP and self._smierc_tick(g, poz, teraz):
            return True                     # zgon (albo podejrzenie zgonu) przed PK, walką, lootem i modelem
        if WPADNIECIE:
            wp = self._wp()
            if wp is not None:
                try:
                    wp.obserwuj(poz, teraz)          # 15.10: piętro zmienione poza planowanym przejściem = wpadnięcie
                except bot.Zatrzymano:
                    raise
                except Exception as e:
                    log(f"debug: wpadniecie.obserwuj błąd {e!r}")
        self._ruch_tick(poz, teraz)
        self.zapamietaj_pole(poz)
        self.exp_przed, self.exp_teraz = self.exp_teraz, g.get("exp")
        self.ratunek_g = g                 # 19.10 (F2a): HP/mana do migawki dla Haiku w cieniu (bez nowego RPC)
        if not self.stoj_wl:               # 23.10 STÓJ: detektory zawieszki/ratunku/orbit nie liczą stania za awarię
            self._d3_tick(g, poz, teraz)       # 16.10: detektor zawieszki (D3 krok A), tylko log
            self._ratunek_tick(poz, teraz)     # 19.10: detektor zachowań „jak bot” (ratunek F1, cień), tylko log
        if (STRAZNIK_ORBITY or self._straznik is not None) and not self.stoj_wl:
            self._straznik_tick(poz, teraz)    # 20.10: strażnik orbit (straznik_orbity.py): wykrycie (1 = cień, 2 = + reakcja w kroku 3a)
        if self.ruch_poz != tuple(poz):
            self.ruch_poz, self.ruch_czas = tuple(poz), teraz
            self.aktywnosc_ts = teraz
        if self.cel is not None or str(self.stan) == "WALKA":
            self.aktywnosc_ts = teraz      # walka z miejsca to nie bezczynność
        if g.get("max_hp"):
            pct = 100.0 * g["hp"] / g["max_hp"]
            self.hp_hist = [(t, p) for t, p in self.hp_hist if teraz - t <= GRYZIE_OKNO] + [(teraz, pct)]
            self.ogien_hp_hist = [(t, p) for t, p in self.ogien_hp_hist if teraz - t <= OGIEN_HP_OKNO_S] + [(teraz, pct)]
            if max(p for _, p in self.hp_hist) - pct >= GRYZIE_SPADEK_PP:
                self.hp_gracza_spadek = teraz
        elif self.hp_ostatnie is not None and g["hp"] < self.hp_ostatnie:
            self.hp_gracza_spadek = teraz

        # śledzenie głodu: wzrost HP, pełne HP albo walka resetują zegar
        if self.hp_ostatnie is None or g["hp"] > self.hp_ostatnie or g["hp"] >= g["max_hp"]:
            self.hp_wzrost = teraz
            # regeneracja = wzrost HP poza oknem po rzucie exura (leczenie czarem nie dowodzi, że jesteśmy najedzeni)
            if self.hp_ostatnie is None or g["hp"] >= g["max_hp"] \
                    or teraz - self.zdrowie_rzut_ts > JEDZENIE_WALKA_LECZENIE_S:
                self.hp_regen = teraz
        self.hp_ostatnie = g["hp"]
        # śledzenie many: wzrost, pełna mana albo rzut czaru (spadek) resetują zegar "mana nie rośnie"
        mana, max_mana = g.get("mana"), g.get("max_mana")
        if mana is not None:
            if self.mana_ostatnia is None or mana > self.mana_ostatnia or (max_mana and mana >= max_mana):
                self.mana_wzrost = teraz
                if self.mana_ostatnia is not None and mana > self.mana_ostatnia:
                    self.mana_rosla = teraz
            self.mana_ostatnia = mana

        # 1. ucieczka (najwyższy priorytet, z histerezą)
        # wejście: HP <= próg albo kolejne uderzenie (największy niedawny spadek) zrzuciłoby je pod próg
        # (odczyt co ~0,6-0,9 s, a szczur zdejmuje do kilkunastu pp: sam próg bywa przeskoczony)
        spadek = self.spadek_hp(g["proc"], teraz)
        if g["proc"] <= self.prog_aktualny or (spadek > 0 and g["proc"] - spadek <= self.prog_aktualny):
            if not self.ucieczka:
                self.ucieczka_od = teraz
                if g["proc"] > self.prog_aktualny:
                    log(f"HP {g['proc']:.0f}% (spadek o {spadek:.0f} pp), przewiduję przekroczenie progu "
                        f"{self.prog_aktualny:.0f}%: uciekam.")
            self.ucieczka = True
        elif self.ucieczka:
            odpoczynek = teraz - (self.ucieczka_od if self.ucieczka_od is not None else teraz)
            if self._pk_blokuje_powrot(teraz):
                pass                      # ucieczka PK: ani zdrowie, ani czas nie wracają na spot (wróg w widoku / karencja)
            elif g["proc"] >= self.wznowienie_hp:
                log(f"HP {g['proc']:.0f}%, wracam do trasy.")
                self.ucieczka = False
                self.ostrozny = False
                self.nieudane = 0
                self._zwloki_po_ucieczce(teraz)
                self.po_ucieczce()
            elif odpoczynek >= UCIECZKA_ODPOCZYNEK_S \
                    and g["proc"] >= self.prog_aktualny + UCIECZKA_MARGINES_WZNOWIENIA:
                # HP nie rośnie (np. brak jedzenia = brak regeneracji): nie stoimy bez końca
                log(f"HP {g['proc']:.0f}% po {odpoczynek:.0f} s ucieczki (brak regeneracji?), wracam do gry ostrożnie.")
                self.ucieczka = False
                self.ostrozny = True
                self.nieudane = 0
                self._zwloki_po_ucieczce(teraz)
                self.po_ucieczce()
        if self.ostrozny and not self.ucieczka and g["proc"] >= self.wznowienie_hp:
            log(f"HP {g['proc']:.0f}%, koniec trybu ostrożnego.")
            self.ostrozny = False
        # 0. obrona przed graczami (obrona_pk.py): po aktualizacji ucieczki z progu HP (PK ma pierwszeństwo przed nią)
        if self._pk_tick(g, poz, teraz):
            self._tele_wczesny(g, poz, "pk")
            return True
        # leczenie czarem (exura): także w walce/pościgu; ucieczka (HP <= próg) ma pierwszeństwo, bo wtedy proc <= prog
        if self._zatrucie_tick(g, poz, teraz):
            self._tele_wczesny(g, poz, "zatrucie")      # 23.10: leczenie trucizny przed exurą (exura działa mimo zatrucia: kolejny obieg)
            return True
        if self._zdrowie_czar_tick(g, poz, teraz):
            self._tele_wczesny(g, poz, "zdrowie_czar")
            return True

        # pola ognia: odświeżenie wykrycia (co OGIEN_ODSWIEZ_S) i zejście z pola, na którym stoimy;
        # po leczeniu, przed ucieczką, lootem, ML i walką (każdy obieg w ogniu to kolejne 10 HP)
        self._ogien_tick(poz, teraz)
        if self._ogien_wyjdz(poz, teraz):
            self._tele_wczesny(g, poz, "ogien_wyjdz")
            return True

        if self.stanowisko is not None and self.stanowisko.przed_ucieczka(g, poz, teraz, self.ucieczka):
            self._tele_wczesny(g, poz, "stanowisko_pz")      # 22.10: HP/PK -> marsz do PZ zamiast uciekaj po trasie
            self.cel = None
            return True

        if self.ucieczka and not self._wpadniecie_bez_drogi(poz):
            self._tele_wczesny(g, poz, "ucieczka")
            self.cel = None
            if self.lww:
                self._lww_przerwij("ucieczka", teraz, pilne=True)
            if self.pamiec:
                self._pamiec_koniec("przerwany", "ucieczka", poz)
            return self.uciekaj(g, poz)

        # wyprawa do depo po potwierdzonym głodzie startuje także w walce: od teraz biegniemy (bez walki), bijemy
        # tylko gdy droga zablokowana (_wypad_bieg); bez tego trolle w jaskini blokowałyby wyjazd w nieskończoność
        if self.wyprawa is not None and not self.wypad_aktywny and not self.stoj_wl:
            fn = getattr(self.wyprawa, "okazja_w_walce", None)
            if fn is not None and fn(teraz):
                self.cel = None

        # jedzenie czarem (exevo pan): gdy brak jedzenia w plecaku; potem istniejące jedzenie
        if self._jedzenie_czar_tick(g, poz, teraz):
            self._tele_wczesny(g, poz, "jedzenie_czar")
            return True
        # jedzenie: także w walce, bo regeneracja (i głód) nie zależy od walki
        if self.pk_stan != "UCIECZKA" and self.jedzenie_potrzebne(g, teraz, poz):   # w ucieczce PK nie jemy (kilka sekund bez reakcji)
            self._tele_wczesny(g, poz, "jedzenie")
            self.zjedz(teraz, g)
            return True

        t0 = self.zegar()
        if self._z_poprz is not None and poz[2] != self._z_poprz:
            self._swiezy_skan_do = teraz + TRASA_SWIEZY_SKAN_S   # nowe piętro: cache rdzenia mógł być sprzed zmiany
        self._z_poprz = poz[2]
        if teraz < self._swiezy_skan_do:
            lista = self.stwory(0.0)
        else:
            lista = self.stwory(PAMIEC_SKAN_WIEK if self.pamiec else None)
        lista = self._pet_obserwuj(g, poz, lista, teraz)     # pet: obserwacja i lista bez niego (przed wyborem celów)
        self.ostatnie_stwory = lista
        self.odnotuj_stwory(lista, poz)
        t1 = self.zegar()
        self._tele_tick(g, poz, lista)
        t2 = self.zegar()
        fazy.update(stwory=t1 - t0, telemetria=t2 - t1)
        if (t2 - t_start > TICK_WOLNY and os.environ.get("CAVEBOT_DEBUG")) or \
                (t2 - t_start > 2 * TICK_WOLNY and t2 - self.tick_wolny_ost > 30):
            self.tick_wolny_ost = t2
            log("debug: wolny tick " + f"{t2 - t_start:.2f} s: " + ", ".join(f"{k} {v:.2f}" for k, v in fazy.items()))

        # 1b. strażnik postępu globalny (STRAZNIK_POSTEP, domyślnie wyłączony)
        if not self.stoj_wl:                   # 23.10 STÓJ: bez strażników postępu i zwiechy (stanie nie jest awarią)
            self._straznik_postepu(g, poz, teraz)
            self._zwiecha_tick(g, poz, teraz)      # 23.10: zwiecha walki (zwiecha.py): kolejny szczebel napraw, gdy zdarzenia wciąż bez zabicia

        # 2. obcy gracz: zatrzymuje tylko groźny (GM/CM/God/Tutor, czaszka/PK) albo każdy przy stop_przy_graczach
        if self.zatrzymaj_przy_graczu and self.pk_stan is None:   # w ucieczce PK stanie w GRACZ = śmierć
            obcy = self.inni_gracze(lista, poz)
            if PK_OBRONA and any(self._pk_czaszka(s) for s in obcy) and self._pk_tick(g, poz, teraz):
                self._tele_wczesny(g, poz, "pk")      # gracz z groźną czaszką w widoku: ucieczka PK, nie pauza GRACZ
                return True
            grozni = [s for s in obcy if self.stop_przy_graczach or self.gracz_grozny(s)]
            if grozni:
                nazwy = ", ".join(s["nazwa"] for s in grozni)
                self.ustaw_stan("GRACZ", nazwy)
                if teraz - self.ostatni_alarm > 15:
                    self.ostatni_alarm = teraz
                    self.alarm("gracz na ekranie: " + nazwy)
                if self.marsz is not None:
                    self._marsz_stop(poz, "gracz groźny w widoku")    # MARSZ_KLIK: pauza ma stać, a klient idzie sam
                self.pauza(0.5, 1.0)
                return True
            # zwykły gracz: gramy dalej; tylko wpis informacyjny (bez [GRACZ], bez alarmu).
            # Mózg i tak dostaje go jako zdarzenie "obcy_gracz" z odczytu stworów.
            for s in obcy:
                if teraz - self.gracze_zalogowani.get(s["nazwa"], float("-inf")) > GRACZ_INFO_PONOW:
                    self.gracze_zalogowani[s["nazwa"]] = teraz
                    log(f"Gracz w pobliżu: {s['nazwa']} ({self.dystans((s['x'], s['y']), poz)} pól), gram dalej.")

        # 2a. unikanie zwykłych graczy: detekcja (debounce), powiadomienie; cele i trasa w kandydaci()/_idz_trasa()
        self._unikanie_obserwuj(lista, poz)
        self._obecnosc_obserwuj(lista, poz)      # 15.10: mapa obecności mobów (tryb cienia patrolu), tylko odczyt, błąd nie przerywa ticka

        # 2a''. runa (F4) w walce: przed ML i meleem, po leczeniu i jedzeniu
        if self._runa_tick(g, poz, lista, teraz):
            return True

        # 2a UH (uh.py): robienie run w spokoju; po leczeniu/jedzeniu, przed ML (ma pierwszeństwo przy mana >= UH_MANA_MIN)
        if self._uh_tick(g, poz, lista, teraz):
            return True

        # 2a-pet. pet (utevo res): obserwacja i przywołanie w spokoju; rzut pochłania obieg
        if self._pet_tick(g, poz, lista, teraz):
            return True

        # 2a'. ML: czar na magic level (tylko w spokoju; rzut pochłania obieg)
        if self._ml_czar_tick(g, poz, lista, teraz):
            return True

        # 2b. pościg na pamięć: ranny cel zniknął z widoku żywy, idziemy za nim (do POSCIG_PAMIEC_S s)
        if self.pamiec and self.cel is None and not (self.dojscie_aktywne and DOJSCIE_BIEGNIJ) and not self.stoj_wl \
                and self._pamiec_tick(g, poz, lista, teraz):
            return True

        # 3. walka
        ludzie = {s["id"]: s for s in lista}
        if self.cel and self.cel["id"] not in ludzie:
            return self.zgon_celu(g, poz, pewny=False)
        if self.cel and ludzie[self.cel["id"]].get("hp", 100) <= 0:
            return self.zgon_celu(g, poz, pewny=True)
        self._blokada_bij_tick(lista, poz, teraz)     # 23.10: stwór spoza --potwory na jedynym kroku drogi = też cel
        kand = self._unikanie_filtr(self.kandydaci(lista, poz), poz)   # moby przy graczu: nie kradniemy
        biegnij = self._wypad_bieg(kand, poz, teraz)
        if biegnij:
            if self.cel:
                log(f"{'Dojście' if self.dojscie_aktywne else 'Wypad'}: biegnę, nie walczę z {self.cel['nazwa']} (droga wolna).")
                self.cel = None
            kand = []
        if self.stoj_wl and self.cel and self.dystans((ludzie[self.cel["id"]]["x"], ludzie[self.cel["id"]]["y"]), poz) > 1:
            # 23.10 STÓJ: cel odszedł dalej niż obok: nie gonimy; Escape zatrzymuje marsz klienta za celem (follow)
            log(f"STÓJ: cel {self.cel['nazwa']} odszedł, nie gonię.")
            self.cel = None
            if teraz - self.__dict__.get("_stoj_esc_ts", float("-inf")) >= 2.0:
                self._stoj_esc_ts = teraz
                self._escape()
        if self.cel:
            cel = ludzie[self.cel["id"]]
            if self.ignorowany(cel, poz, teraz) or cel["z"] != poz[2]:
                self.cel = None
                cel = None
            elif not self.w_widoku(cel, poz) and cel["hp"] < HP_UCIEKAJACEGO \
                    and self.dystans((cel["x"], cel["y"]), poz) <= POGON_ZASIEG:
                # uciekający cel poza ekranem: idziemy za nim, klikać nie można (klik trafiłby w panel UI)
                self.ustaw_stan("POGON", f"{cel['nazwa']} HP {cel['hp']}% ({cel['x']},{cel['y']})")
                odl_celu = self.dystans((cel["x"], cel["y"]), poz)
                self.zapamietaj_ruch_celu(cel)
                self.cel.update(poz=(cel["x"], cel["y"], cel["z"]), hp=cel["hp"], odl=odl_celu)
                powod = self.ocen_pogon(cel, odl_celu, teraz)
                if powod:
                    log(f"Odpuszczam {cel['nazwa']} poza ekranem: {powod} (odl {odl_celu}).")
                    self.odpusc_pogon(cel, teraz)
                    self.cel = None
                    return True
                if self.podejdz((cel["x"], cel["y"]), poz, pilne=True, natychmiast=True) is None:
                    m_ = self._blokujacy_wyjscia(cel, kand, poz, teraz)
                    if m_ is not None:
                        self.cel = None
                        return True
                    self._log_odpuszczenia(cel, f"Odpuszczam {cel['nazwa']}: za ścianą (droga naokoło: {self.ostatni_objazd}).", teraz)
                    self._ignoruj(cel["id"], teraz + self.objazd_ignorowanie(cel, odl_celu), "sciana")
                    self.cel = None
                return True
            elif not self.w_widoku(cel, poz):
                # poza widokiem nie da się kliknąć (klik trafiłby w panel UI): uznajemy, że uciekł
                log(f"Cel {cel['nazwa']} wyszedł z widoku ({cel['x']},{cel['y']}), odpuszczam.")
                self.cel = None
                cel = None
        else:
            cel = None
        roz = self.rozprawa
        if cel is not None and roz and teraz >= roz["do"] and cel["id"] == roz["id"] and roz.get("wroc") is not None:
            # świeży żyje dłużej niż ROZPRAWA_MAX: ranny w widoku w zasięgu 10 ma pierwszeństwo (o ile nas nie gryzą)
            w = next((s for s in kand if s["id"] == roz["wroc"]), None)
            if w is not None and self.w_widoku(w, poz) and teraz - self.hp_gracza_spadek >= GRYZIE_OKNO \
                    and self.dystans((w["x"], w["y"]), poz) <= DOBICIE_ZASIEG_UCIEKAJACY:
                log(f"Rozprawa z {cel['nazwa']} trwa ponad {ROZPRAWA_MAX:.0f} s, wracam do dobicia.")
                self.cel = None
                cel = None
        roz = self.rozprawa
        if cel is not None and not (roz and teraz < roz["do"] and cel["id"] == roz["id"]):
            wr = roz["wroc"] if roz and teraz < roz["do"] else None
            if self._rozprawa_blok(cel, poz, lista, kand, teraz, wr) is not None:
                self.cel = None
                cel = None
        if cel is not None:
            odl_celu = self.dystans((cel["x"], cel["y"]), poz)
            obok = [s for s in kand if s["id"] != cel["id"] and self.dystans((s["x"], s["y"]), poz) <= 1]
            if self._cele_pierwsze() and self._cel_pierwszy(cel):
                obok = [s for s in obok if self._cel_pierwszy(s)]   # 24.10 CELE_PIERWSZE: bity Wasp nie ustępuje Trollowi obok (tylko innemu z listy)
            # prawie martwego celu w zasięgu DOBICIE_ZASIEG nie zamieniamy na świeżego potwora obok,
            # chyba że świeży nas gryzie (HP gracza spada)
            dobijamy = (cel["hp"] <= self.prog_uciekania(cel["nazwa"]) + DOBICIE_MARGINES
                        or cel["hp"] < POGON_DOBICIE_HP or self.uciekajacy(cel)) \
                and odl_celu <= (DOBICIE_ZASIEG_UCIEKAJACY if self.uciekajacy(cel) else DOBICIE_ZASIEG)
            gryzie = teraz - self.hp_gracza_spadek < GRYZIE_OKNO
            # świeży potwór obok zagradza drogę (korytarz), a my stoimy w miejscu: bijemy świeżego
            # (stoimy >= BLOKADA_STOI, świeży stoi obok >= BLOKADA_STOI i pościg nie robi postępu)
            for s_ in kand:
                if self.dystans((s_["x"], s_["y"]), poz) <= 1:
                    self.obok_od.setdefault(s_["id"], teraz)
            self.obok_od = {k: v for k, v in self.obok_od.items()
                            if any(s_["id"] == k and self.dystans((s_["x"], s_["y"]), poz) <= 1 for s_ in kand)}
            blokuje = any(teraz - self.obok_od.get(s_["id"], teraz) >= BLOKADA_STOI for s_ in obok) \
                and teraz - self.ruch_czas > BLOKADA_STOI and teraz - self.pogon_postep > BLOKADA_STOI \
                and teraz >= self.rozprawa_spokoj_do
            # dwóch+ świeżych obok, a uciekający dalej niż 3 pola: najpierw rozprawa z nimi (potem wracamy do dobicia)
            tlum = len(obok) >= 2 and odl_celu > 3 and teraz >= self.rozprawa_spokoj_do
            if odl_celu > 1 and obok and (not dobijamy or gryzie or blokuje or tlum):
                log(f"Zmiana celu: {obok[0]['nazwa']} stoi obok, {cel['nazwa']} jest {odl_celu} pól dalej.")
                # zobowiązanie: bijemy tego świeżego do skutku (inaczej wybór z premią za dobicie wracał do
                # rannego, a ten warunek znów go zmieniał: pętla co obieg bez ataku)
                wroc = self.rozprawa["wroc"] if self.rozprawa and teraz < self.rozprawa["do"] \
                    else (cel["id"] if self.uciekajacy(cel) or cel["hp"] < POGON_DOBICIE_HP else None)
                if wroc == obok[0]["id"]:
                    wroc = cel["id"] if self.uciekajacy(cel) else None
                self.rozprawa = {"id": obok[0]["id"], "wroc": wroc, "do": teraz + ROZPRAWA_MAX}
                self.cel = None
                cel = None
            elif odl_celu > 1:
                powod = self.ocen_pogon(cel, odl_celu, teraz)
                if powod:
                    log(f"Odpuszczam {cel['nazwa']}: {powod} (odl {odl_celu}).")
                    self.odpusc_pogon(cel, teraz)
                    self.cel = None
                    cel = None
                    kand = [s for s in kand if s["id"] not in self.ignorowane]
            else:
                self.pogon_odl, self.pogon_postep = odl_celu, teraz
        # 15.10: cel przy znanym parzącym polu (duży ogień), a nie obok nas: nie atakujemy go (klient poszedłby za nim
        # w ogień); czekamy, aż wyjdzie. Stojący obok nas bije i tak, więc ten zostaje.
        if OGIEN_PARZY_ODL_CELU >= 0 and self._ogien_parzy_dane(poz[2]):
            if cel is not None and self.dystans((cel["x"], cel["y"]), poz) > 1 \
                    and self._ogien_przy_parzacym((cel["x"], cel["y"], cel["z"])):
                ost = getattr(self, "_ogien_cel_log", {})
                if teraz - ost.get(cel["id"], float("-inf")) >= 30.0:
                    ost[cel["id"]] = teraz
                    self._ogien_cel_log = ost
                    log(f"[OGIEN] {cel['nazwa']} stoi przy dużym ogniu ({cel['x']},{cel['y']}): nie gonię, czekam aż wyjdzie.")
                self.cel = None
                cel = None
            kand = [s_ for s_ in kand if self.dystans((s_["x"], s_["y"]), poz) <= 1
                    or not self._ogien_przy_parzacym((s_["x"], s_["y"], s_.get("z", poz[2])))]
        # 15.10: cel przy znanej dziurze, do którego klient poszedłby przez dziurę: nie atakujemy (jak ogień wyżej); Escape
        # zatrzymuje marsz klienta, który już wlecze się za celem (tryb ataku = follow). Cel obok nas zostaje.
        if DZIURA_PRZY_CELU and self.mapa is not None:
            if cel is not None and self._cel_przez_dziure(cel, poz, teraz) == "skip":
                self._dziura_cel_odpusc(cel, poz, teraz)
                self.cel = None
                cel = None
            for s_ in [x for x in kand if self._cel_przez_dziure(x, poz, teraz) == "skip"]:
                self._dziura_cel_odpusc(s_, poz, teraz, escape=False)      # tylko log (co 30 s na cel)
                kand.remove(s_)
        if cel is not None and self._cele_pierwsze() and not self._cel_pierwszy(cel):
            # 24.10 CELE_PIERWSZE: potwór z listy tuż obok (kand jest już po filtrach ognia/dziur/strefy) odrywa nas od celu
            # spoza listy; cel z listy (Wasp -> Wasp) nie jest zmieniany, więc bez migotania
            pr = [s_ for s_ in kand if self._cel_pierwszy(s_) and self.w_widoku(s_, poz)
                  and self.dystans((s_["x"], s_["y"]), poz) <= CELE_PIERWSZE_ZMIANA_ODL]
            if pr:
                n_ = min(pr, key=lambda s_: (self.dystans((s_["x"], s_["y"]), poz), s_["id"]))
                log(f"Zmiana celu (CELE_PIERWSZE): {n_['nazwa']} {self.dystans((n_['x'], n_['y']), poz)} pól od nas, "
                    f"zamiast {cel['nazwa']}.")
                self.cel = None
                cel = None
        if self._zwloki_przed_celem(cel, kand, g, poz, lista, teraz):
            return True
        if cel is None and kand:
            # priorytet: odległość + HP/WAGA_HP - ranny potwór w pobliżu to szybkie zabicie
            # dobicie (ranny cel w zasięgu) ważniejsze niż świeży cel, chyba że świeży stoi obok i nas gryzi
            gryzie = teraz - self.hp_gracza_spadek < GRYZIE_OKNO \
                and any(self.dystans((s["x"], s["y"]), poz) <= 1 for s in kand)

            def klucz(s):
                d = self.dystans((s["x"], s["y"]), poz)
                premia = DOBICIE_PREMIA if not gryzie and d <= DOBICIE_ZASIEG_UCIEKAJACY and \
                    self.uciekajacy(s) else 0.0
                return (d + s["hp"] / WAGA_HP - premia, s["id"])
            # 24.10 CELE_PIERWSZE: potwór z listy przed każdym innym (potem zwykły klucz); pusta lista = jak dawniej
            pierwsze = bool(self._cele_pierwsze())
            kolejka = sorted(kand, key=(lambda s: (0 if self._cel_pierwszy(s) else 1, klucz(s))) if pierwsze else klucz)
            z_listy = pierwsze and self._cel_pierwszy(kolejka[0])
            cel = kolejka[1] if len(kolejka) > 1 and not z_listy and random.random() < DRUGI_CEL else kolejka[0]
            if self.pamiec_znaleziony and not z_listy:
                # cel odnaleziony po zniknięciu: wracamy do dobicia właśnie jego (chyba że gryzie nas świeży)
                w = next((x for x in kand if x["id"] == self.pamiec_znaleziony[0]), None)
                if w is not None and not gryzie:
                    cel = w
            roz = self.rozprawa
            if roz and not z_listy:
                ids = {s["id"]: s for s in kand}
                w = ids.get(roz["wroc"]) if roz.get("wroc") is not None else None
                wroc_ok = w is not None and not gryzie and self.w_widoku(w, poz) \
                    and self.dystans((w["x"], w["y"]), poz) <= DOBICIE_ZASIEG_UCIEKAJACY
                if roz["id"] in ids and teraz < roz["do"]:
                    cel = ids[roz["id"]]          # rozprawa ze świeżym trwa
                elif wroc_ok:
                    # świeży zabity albo rozprawa trwa dłużej niż ROZPRAWA_MAX: wracamy do rannego
                    cel = w
                    log(f"Rozprawa skończona, wracam do dobicia: {cel['nazwa']} HP {cel['hp']}% "
                        f"(odl {self.dystans((cel['x'], cel['y']), poz)}).")
                    self.rozprawa = None
                    self.rozprawa_spokoj_do = teraz + ROZPRAWA_SPOKOJ
                elif teraz >= roz["do"] or w is None:
                    self.rozprawa = None
            # wybrany cel zasłonięty mobami w korytarzu: od razu bijemy pierwszego blokującego
            if not (self.rozprawa and cel["id"] == self.rozprawa["id"]):
                m = self._rozprawa_blok(cel, poz, lista, kand, teraz,
                                        self.rozprawa["wroc"] if self.rozprawa else None)
                if m is not None:
                    cel = m
            self.cel = {"id": cel["id"], "nazwa": cel["nazwa"], "hp0": cel["hp"]}
            if self.pamiec_znaleziony and self.pamiec_znaleziony[0] == cel["id"]:
                self.cel["hp0"] = max(cel["hp"], self.pamiec_znaleziony[1])   # trafiony przed zniknięciem
            self.pamiec_znaleziony = None
            self.reakcja_do = teraz + random.uniform(*REAKCJA)
            self.pogon_odl, self.pogon_postep = self.dystans((cel["x"], cel["y"]), poz), teraz
            self.pogon_tick_ost = teraz
            self.poprzednia_odl = None
            self.obok_hp = None
            self.hp_spadek_czas = teraz
            self.atak_czas = float("-inf")
            self.prog_aktualny = self.prog_hp + random.uniform(0, ROZRZUT_PROGU)
            self.cel_start = teraz
            self.czekanie_do = None
            self.cel_hp = cel["hp"]
            self.cel_spadek = float("-inf")
            self.nieudane = 0
            self.ignorowane = {k: v for k, v in self.ignorowane.items() if v > teraz}
            self.nieosiagalne = {k: v for k, v in self.nieosiagalne.items() if k in self.ignorowane}
            self.ignor_powod = {k: v for k, v in self.ignor_powod.items() if k in self.ignorowane}
            self.ignor_droga_cache = {k: v for k, v in self.ignor_droga_cache.items() if k in self.ignorowane}
            # 15.10: log decyzji D1 (tylko odczyt); id trafia do "nowy_cel" przez telemetria.linia (nast_decyzja)
            self._d1_id_cel = self._decyzja_d1(kand, cel, poz, g, lista, klucz, gryzie)
            if self.tele is not None:
                try:
                    self.tele.nast_decyzja = self._d1_id_cel
                except Exception:
                    pass
            log(f"Nowy cel: {cel['nazwa']} ({cel['x']},{cel['y']}) HP {cel['hp']}%")
            self.moje_cele[cel["id"]] = self.zegar()       # CUDZY_MOB: ten mob jest nasz (od teraz wolno go bić poranionego)
            if len(self.moje_cele) > 300:
                self.moje_cele = {k: v for k, v in self.moje_cele.items() if self.zegar() - v < 1800.0}
        if cel is not None:
            self.zapamietaj_ruch_celu(cel)
            self.cel.update(poz=(cel["x"], cel["y"], cel["z"]), hp=cel["hp"], odl=self.dystans((cel["x"], cel["y"]), poz))
            if DZIURA_PRZY_CELU and self.mapa is not None and self._cel_przez_dziure(cel, poz, teraz) == "idz":
                if self._dziura_podejscie(cel, poz, teraz):
                    return True
                self._dziura_cel_odpusc(cel, poz, teraz)       # podejście trwa za długo: jak "skip"
                self.cel = None
                return True
            st_dz = getattr(self, "_dziura_poczatek", None)
            if st_dz:
                st_dz.pop(cel["id"], None)                     # cel już nie przy dziurze: budżet podejścia od nowa
            return self.walcz(cel, g, poz)

        # 3a. strażnik orbit (STRAZNIK_ORBITY=2): stop chodzenia, rotacja sposobów naprawy (nigdy STOP); walka ma pierwszeństwo
        if self._straznik is not None and not self.stoj_wl and self._straznik_reakcja(poz, teraz):
            return True

        # 3b. wpadnięcie na piętro bez trasy (wpadniecie.py): lina / plan po mapie / ALARM; walka ma pierwszeństwo
        if WPADNIECIE and self.wpadniecie and not self.stoj_wl:
            try:
                if self.wpadniecie.tick(poz, teraz) is not None:
                    return True
            except bot.Zatrzymano:
                raise
            except Exception as e:
                log(f"Wpadnięcie: błąd {e!r}")
                self.wpadniecie.st = None

        if self.lww is not None:
            self._lww_przerwij("brak_celu", teraz, pilne=True)
        if self.lww_zalegle is not None:
            self._lww_zamknij_zalegle(teraz, poz, lista)
        # przerwa od gry (nieregularnie, patrz PRZERWA_CO_MIX); kończy się wcześniej, gdy coś podejdzie
        if teraz >= self.przerwa_od and not self.wypad_aktywny and not (self.dojscie_aktywne and DOJSCIE_BIEGNIJ) \
                and not self.stoj_wl:
            if self.przerwa_do is None:
                self.przerwa_do = teraz + losuj_z_mieszanki(PRZERWA_DLUGOSC_MIX)
                log(f"Przerwa na {self.przerwa_do - teraz:.0f} s.")
            if teraz < self.przerwa_do and self._przerwa_przerwij_gdy_gracz(teraz):
                pass                                   # gracz podszedł: przerwa skończona (log i losowanie następnej w metodzie)
            else:
                if teraz < self.przerwa_do:
                    # wymiana pochodni w trakcie przerwy (krótka, bez ruchu; _pochodnia_tick ma własne warunki: nic żywego
                    # w pobliżu, brak celu, interwał 30 s). Licznik przerwy (przerwa_do) zostaje nietknięty.
                    if POCHODNIA_W_PRZERWIE and self._pochodnia_tick(lista, poz):
                        return True
                    self.ustaw_stan("PRZERWA", f"jeszcze {self.przerwa_do - teraz:.0f} s")
                    self.pauza(1.5, 3.0)
                    return True
                log("Koniec przerwy.")
                self.przerwa_do = None
                self.przerwa_od = teraz + losuj_z_mieszanki(PRZERWA_CO_MIX)

        self._watchdog_bezczynnosci(g, poz, lista, teraz)

        # zwłoki odłożone w czasie walki (atak ma pierwszeństwo przed lootem); w biegu wypadu nie zbieramy
        if self.loot and not (WYPAD_BIEGNIJ and self.wypad_aktywny) and not (self.dojscie_aktywne and DOJSCIE_BIEGNIJ) \
                and not self.stoj_wl:               # 23.10 STÓJ: loot wymaga podejścia do zwłok = chodzenie
            zw = None
            zyje = self.zywy_w_poblizu(lista, poz)
            if zyje and self.loot_blok_od is None:
                self.loot_blok_od = teraz
            if not zyje:
                self.loot_blok_od = None
            if self._poscig_przerwanie():
                pass            # pauza_bota / rozmowa z graczem: nie zaczynamy lootu, zwłoki zostają na liście (idz() trzyma pauzę)
            elif zyje and teraz - self.loot_blok_od < LOOT_BLOK_MAX:
                if self._zwloki_w_zasiegu(poz):
                    self.ustaw_stan("WALKA", f"loot wstrzymany: {zyje['nazwa']} odl {self.dystans((zyje['x'], zyje['y']), poz)}")
                    self.pauza(0.2, 0.4)
                    return True
            else:
                zw = self.zwloki_do_zebrania(poz)
            if zw is not None:
                self.ustaw_stan("LOOT", f"odłożone {zw}")
                try:
                    wynik = self.zbierz_loot(zw)
                except bot.Zatrzymano:
                    raise
                except Exception as e:
                    wynik = None
                    log(f"Loot się nie udał: {e!r}")
                if wynik == "przerwany":
                    self.pauza(*LOOT_PRZERWANY_PAUZA)    # bez pauzy tick kręciłby się bez przerwy przy niskim HP / mobie obok
                return True

        # 4b. wymiana pochodni (poza walką i lootem)
        if self._pochodnia_tick(lista, poz):
            return True

        # 5. trasa
        return self.idz()

    def _zw_brak_okna_n(self, zw):
        """LOOT_DYNAMICZNY: ile razy zwłoki dały "brak_okna" (0 = nie wstrzymane)."""
        if not LOOT_DYNAMICZNY:
            return 0
        return self.zw_brak_okna.get(tuple(zw), 0)

    def _zw_oznacz_brak_okna(self, zw):
        if LOOT_DYNAMICZNY:
            k = tuple(zw)
            self.zw_brak_okna[k] = self.zw_brak_okna.get(k, 0) + 1
            self.lww_pomin[k] = self.zegar() + ZWLOKI_WAZNE      # w walce: bez powtórek do końca TTL
            log(f"Loot: zwłoki {k[:2]} bez okna ({self.zw_brak_okna[k]}x): wstrzymane do końca walki"
                + (", porzucone." if self.zw_brak_okna[k] >= 2 else ", jedna próba po walce."))

    def _zw_usun_grupe(self, zw):
        """LOOT_DYNAMICZNY: zwłoki obsłużone: kandydaci tego samego zabicia znikają z listy (nie próbujemy ich)."""
        grupa = self.zw_grupa.pop(tuple(zw), None)
        if not grupa:
            return
        for g_ in grupa:
            self.zw_grupa.pop(tuple(g_), None)
        reszta = set(tuple(g_) for g_ in grupa)
        self.zwloki_czekajace = [(a, t) for a, t in self.zwloki_czekajace if tuple(a) not in reszta]

    def _lww_okno_otwarte(self):
        """LOOT_DYNAMICZNY: trwa loot w walce z już otwartym oknem zwłok (przenoszenie/weryfikacja/zamknięcie)."""
        lw = self.lww
        return bool(LOOT_DYNAMICZNY and lw is not None
                    and lw["stan"].get("faza") in ("plan", "przenies", "weryfikuj", "weryfikuj_jedzenie", "zamknij"))

    def _zwloki_przed_celem(self, cel, kand, g, poz, lista, teraz):
        """Zbiera odłożone zwłoki ZANIM ruszymy w pościg za (nowym) celem: (a) zwłoki w odl <= ZWLOKI_PRZED_CELEM_ODL,
        gdy nic nie styka i żaden cel nie ucieka w odl <= ZWLOKI_PRZED_CELEM_UCIEKAJACY; (b) tuż po ucieczce
        (ZWLOKI_PO_UCIECZCE_PRIORYTET_S) zwłoki w całym ZWLOKI_ZASIEG. True = tick zużyty na zbieranie."""
        if not self.loot or not self.zwloki_czekajace or self.w_lootcie or self.lww is not None or self.stoj_wl:
            return False
        priorytet = ZWLOKI_PO_UCIECZCE and teraz < self.zwloki_priorytet_do
        dyn = bool(LOOT_DYNAMICZNY)
        if not (ZWLOKI_PRZED_CELEM or priorytet or dyn):
            return False
        if self.ucieczka or teraz < self.loot_chlod_do or self._poscig_przerwanie():
            return False
        if g.get("proc", 100.0) <= self.prog_aktualny + LOOT_W_WALCE_HP_MARGINES:
            return False
        if cel is None and not kand:
            return False                        # brak celów: zbierze zwykły blok odłożonych zwłok (z watchdogiem)
        if self._zywe_w_promieniu(lista, poz, 1 if dyn else ZWLOKI_PRZED_CELEM_STYK):
            return False                        # coś styka/jest tuż obok (loot i tak by przerwał): walka pierwsza
        if any(self.dystans((s["x"], s["y"]), poz) <= ZWLOKI_PRZED_CELEM_UCIEKAJACY and self.uciekajacy(s)
               for s in kand):
            return False                        # uciekający blisko: każda chwila się liczy
        odl_max = ZWLOKI_ZASIEG if priorytet else ZWLOKI_PRZED_CELEM_ODL
        if dyn:
            # zwłoki w odl <= 1 zawsze (żywy w odl >= 2 jeszcze nie bije); dalsze tylko gdy żaden mob nie jest bliżej niż 3 pola
            # (nie biegniemy po nie przez środek walki), wtedy do ZWLOKI_ZASIEG (po walce najpierw zwłoki, potem patrol)
            odl_max = ZWLOKI_ZASIEG if not self._zywe_w_promieniu(lista, poz, 2) else 1
        mozliwe = [z for z, t in self.zwloki_czekajace
                   if z[2] == poz[2] and teraz - t < ZWLOKI_WAZNE and self.dystans(z, poz) <= odl_max
                   and self.zwloki_chlod.get(tuple(z), float("-inf")) <= teraz
                   and self._zw_brak_okna_n(z) == 0]
        if not mozliwe:
            return False
        zw = min(mozliwe, key=lambda z: self.dystans(z, poz))
        self.zwloki_czekajace = [(a, t) for a, t in self.zwloki_czekajace if a != zw]
        self.ustaw_stan("LOOT", f"odłożone {zw} (przed celem)")
        try:
            wynik = self.zbierz_loot(zw)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            wynik = None
            log(f"Loot się nie udał: {e!r}")
        if wynik == "przerwany":
            self.zwloki_chlod[tuple(zw)] = max(self.zwloki_chlod.get(tuple(zw), float("-inf")),
                                               self.zegar() + ZWLOKI_PRZED_CELEM_CHLOD_S)
            self.pauza(*LOOT_PRZERWANY_PAUZA)
        return True

    def _stanowisko_sync(self):
        """22.10: tryb stanowisko (stanowisko.py) jest aktywny tylko, gdy pokrętło STANOWISKO=1 ORAZ instancja ma
        stanowisko_mapa.json (zapisuje je tryb.py z mapy stoj_runy_*). Pokrętło wraca na 0 = moduł zwolniony, zachowanie jak dotąd."""
        if not STANOWISKO:
            if self.stanowisko is not None:
                log("Stanowisko: pokrętło STANOWISKO=0, wracam do zwykłej pętli.")
                try:
                    self.stanowisko.zamknij()
                finally:
                    self.stanowisko = None
            self.stanowisko_proba = False
            return
        if self.stanowisko is not None or self.stanowisko_proba:
            return
        self.stanowisko_proba = True                      # jedna próba na włączenie; błąd = zwykła pętla, bez STOP
        try:
            import stanowisko  # noqa: PLC0415
            katalog = Path(instancja.S.stan)
            mapa = stanowisko.wczytaj_mape(katalog)
            if mapa is None:
                log("Stanowisko: STANOWISKO=1, ale brak poprawnego stanowisko_mapa.json w katalogu instancji "
                    "(uruchom przez tryb.py z mapą stoj_runy_*); tryb nieaktywny.")
                return
            koord = None
            try:
                import miejsca_koord  # noqa: PLC0415
                koord = miejsca_koord.Koordynator()
            except Exception as e:
                log(f"Stanowisko: koordynator niedostępny ({e!r}), stoję bez niego.")
            self.stanowisko = stanowisko.Stanowisko(self, mapa, k=lambda n, d=0: globals().get(n, d),
                                                    plik_stanu=katalog / "stanowisko_stan.json", koord=koord, log=log)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"Stanowisko: nie udało się uruchomić ({e!r}), zwykła pętla.")

    # --- przełącznik STÓJ (23.10, stoj.py) ---

    def _stoj_sync(self, poz, teraz):
        """Flaga STÓJ co obieg (jedno stat()). Zbocze włączenia: pole = zapisane w pliku flagi (restart bota) albo bieżące
        (zapisujemy je do pliku), stop marszu klienta (Escape), porzucenie śladów trasy. Zbocze wyłączenia: powrót do zwykłej
        pracy od najbliższego punktu trasy, liczniki zacięć od zera. Błąd odczytu flagi = bez zmiany stanu."""
        try:
            import stoj  # noqa: PLC0415
            wl = stoj.wlaczony(self.stoj_katalog)
        except Exception as e:      # noqa: BLE001
            log(f"debug: STÓJ: nie odczytałem flagi ({e!r}), stan bez zmian")
            return
        if wl and not self.stoj_wl:
            pole = stoj.pole(self.stoj_katalog)
            zapisane = pole is not None
            if pole is None:
                pole = tuple(poz[:3])
            self.stoj_wl, self.stoj_pole = True, pole
            if not zapisane:
                stoj.zapisz_pole(pole, self.stoj_katalog)
            self.cel = None
            self.patrol = None
            self.klik_j = self.klik_cel = self.trasa_droga = None
            self.aktywnosc_ts = teraz
            log(f"STÓJ: włączony (pole {pole}): nie chodzę, robię runy, leczę się, jem i bronię się w miejscu; "
                "ucieczka tylko przy zagrożeniu życia, po przesunięciu wracam na pole.")
            if self.marsz is not None:
                self._marsz_stop(poz, "STÓJ")
            else:
                self._escape()                      # klient mógł iść sam (klik w pole / follow celu): Escape zatrzymuje
        elif not wl and self.stoj_wl:
            self.stoj_wl, self.stoj_pole = False, None
            log("STÓJ: wyłączony: wracam do zwykłej pracy (najbliższy punkt trasy).")
            self._patrol_reset(True)
            self._patrol_sync_idx(tuple(poz[:3]))
            self.ruch_czas = self.aktywnosc_ts = teraz
            self.nieudane = 0
            try:
                self.straznik_post.update(t=None)
            except Exception:       # noqa: BLE001
                pass

    def _stoj_log_rzadko(self, klucz, tekst, co_s=30.0):
        ost = self.__dict__.setdefault("_stoj_log_ts", {})
        t = self.zegar()
        if t - ost.get(klucz, float("-inf")) >= co_s:
            ost[klucz] = t
            log(tekst)

    def _stoj_krok(self):
        """Obieg bez chodzenia (zamiast trasy / patrolu / wypadu): stoimy; po przesunięciu (pchnięcie, ucieczka) wracamy na pole
        zapamiętane przy włączeniu, jak stanowisko.py. Inne piętro, zajęte pole, brak drogi: stoimy tam, gdzie jesteśmy (bez STOP)."""
        teraz = self.zegar()
        poz = tuple(self.postac.pozycja())
        self.aktywnosc_ts = teraz
        pole = self.stoj_pole
        if pole is not None and poz[:3] != tuple(pole[:3]):
            if poz[2] != pole[2]:
                self._stoj_log_rzadko("pietro", f"STÓJ: jestem na innym piętrze niż pole {tuple(pole)}, stoję w {poz} (nie chodzę).")
            elif any((m["x"], m["y"], m["z"]) == tuple(pole[:3]) for m in (self.ostatnie_stwory or ())):
                self._stoj_log_rzadko("zajete", f"STÓJ: pole {tuple(pole)} zajęte, stoję w {poz}.")
            else:
                prowadz = self.droga(poz, tuple(pole[:2]), dlugosc=0)
                if prowadz:
                    self.ustaw_stan("STOJ_POWROT", f"wracam na pole {tuple(pole)} z {poz}")
                    if self.klik is not None:
                        zasieg = random.randint(*DROGA_DO_PRZODU)
                        j = 0
                        for i, q in enumerate(prowadz[:zasieg]):
                            if abs(q[0] - poz[0]) > ZASIEG_X - 1 or abs(q[1] - poz[1]) > ZASIEG_Y - 1:
                                break
                            j = i
                        self.idz_do(prowadz[j][:2], poz, krok=prowadz[0][:2])
                    else:
                        self.krok_do(prowadz[0])
                    return True
                self._stoj_log_rzadko("droga", f"STÓJ: brak drogi z {poz} na pole {tuple(pole)}, stoję (bez STOP).")
        self.ustaw_stan("PAUZA_STOJ", f"stoję w {poz}")
        self.pauza(0.3, 0.8)
        return True

    def _watchdog_wyjatek(self):
        """Stany, w których bezczynność jest zamierzona (pauza/rozmowa mózgu, przerwa, wypad, jedzenie, pochodnia)."""
        if self.stoj_wl:
            return True                                   # 23.10 STÓJ: stanie z woli Karola to nie zawieszenie
        if self.stanowisko is not None:
            return True                                   # 22.10: stanie na polu (runy) to nie zawieszenie; STOP z braku postępu zakazany
        if str(self.stan).startswith(("PAUZA", "PRZERWA", "WYPAD", "JEDZENIE", "POCHODNIA", "MOZG", "GRACZ", "UCIECZKA")):
            return True
        if self.przerwa_do is not None:
            return True
        teraz = self.zegar()
        if teraz - self.__dict__.get("hp_czeka_ts", float("-inf")) < 5.0:
            return True                                   # 23.10: celowe czekanie na HP przed przejściem pięter
        for nazwa in ("wstrzymany_do", "rozmowa_do"):       # mózg: pauza_bota / rozmowa z graczem
            v = getattr(self, nazwa, None)
            if v is not None and not callable(v) and teraz < v:
                return True
        for nazwa in ("wypad", "wypad_aktywny", "wypad_stan", "w_wypadzie", "wypad_trwa"):
            v = getattr(self, nazwa, None)
            if v and not callable(v):
                return True
        return False

    def _escape(self):
        """Escape (zdjęcie celu w kliencie); błąd klawisza nie wywraca obiegu."""
        klawisz = getattr(self.postac, "klawisz", None)
        if klawisz is None:
            return
        try:
            klawisz("Escape")
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"Escape nie poszedł: {e}")

    def _straznik_celu(self, cel, odl, poz, teraz):
        """Strażnik celu (13.10, spec P2a): cel bez postępu (spadek HP celu, przyrost exp, zmiana odległości
        o >= 1). S1 (STRAZNIK_CEL_S1 s, odl <= 1): Escape, odświeżenie pozycji własnej, ponowny klik.
        S2 (STRAZNIK_CEL_S2 s): kontrola pozycji (log + telemetria) i twarde ignorowanie celu na
        STRAZNIK_IGNOR_S s. Seria S2: powiadomienie. True = cel porzucony (self.cel = None)."""
        if not STRAZNIK_CEL:
            self.straznik_cel = None
            return False
        st = self.straznik_cel
        exp = self.exp_teraz
        if st is None or st["id"] != cel["id"]:
            self.straznik_cel = {"id": cel["id"], "t": teraz, "hp": cel["hp"], "odl": odl, "exp": exp, "s1": False,
                                 "ost": teraz}
            return False
        if teraz - st.get("ost", teraz) > STRAZNIK_CEL_PRZERWA:
            # walcz() nie było wołane (PAUZA, UCIECZKA, JEDZENIE, wypad, loot): okno liczymy od nowa
            st.update(t=teraz, hp=cel["hp"], odl=odl, exp=exp, s1=False)
        st["ost"] = teraz
        postep = cel["hp"] < st["hp"] or abs(odl - st["odl"]) >= 1 \
            or (exp is not None and st["exp"] is not None and exp > st["exp"])
        if postep:
            st.update(t=teraz, hp=cel["hp"], odl=odl, exp=exp, s1=False)
            return False
        st["hp"] = max(st["hp"], cel["hp"]) if cel["hp"] > st["hp"] else st["hp"]
        if exp is not None:
            st["exp"] = exp if st["exp"] is None else st["exp"]
        bez = teraz - st["t"]
        if bez >= STRAZNIK_CEL_S2:
            wlasna = tuple(self.postac.pozycja()[:3])
            wpis = next((m for m in self.ostatnie_stwory if m.get("gracz") and m.get("nazwa") == self.postac.nazwa), None)
            wp = (wpis["x"], wpis["y"], wpis["z"]) if wpis else None
            niespojna = wp is not None and wp != wlasna
            na_naszym = any((m["x"], m["y"], m["z"]) == wlasna and not m.get("gracz") and m.get("hp", 100) > 0
                            for m in self.ostatnie_stwory)
            log(f"[STRAZNIK] cel {cel['nazwa']} id{self._koncowka_id(cel['id'])} bez postępu {bez:.0f} s, "
                f"pozycja {'NIESPÓJNA ' if niespojna or na_naszym else ''}(postac {wlasna}, stwory {wp}), "
                f"ignoruję na {STRAZNIK_IGNOR_S:.0f} s.")
            self._tele_poscig("straznik_celu", id=cel["id"], nazwa=cel["nazwa"], sekundy=round(bez, 1),
                              poz_postac=list(wlasna), poz_stwory=list(wp) if wp else None,
                              niespojna=bool(niespojna or na_naszym), hp=cel["hp"], odl=odl)
            self.straznik_s2_t = [t for t in self.straznik_s2_t if teraz - t < STRAZNIK_S2_OKNO_S] + [teraz]
            if len(self.straznik_s2_t) >= STRAZNIK_S2_SERIA:
                self.straznik_s2_t = []
                log(f"[STRAZNIK] {STRAZNIK_S2_SERIA} utknięcia walki w {STRAZNIK_S2_OKNO_S:.0f} s.")
                self._tele_poscig("utkniecie_walki", poz=list(wlasna), nazwa=cel["nazwa"])
                try:
                    self.alarm(f"Walka: {STRAZNIK_S2_SERIA} utknięcia w {STRAZNIK_S2_OKNO_S / 60:.0f} min ({cel['nazwa']})")
                except Exception:
                    pass
            self._escape()
            self._zwiecha_zdarzenie("straznik_s2", poz, teraz)
            self._ignoruj(cel["id"], teraz + STRAZNIK_IGNOR_S, "straznik")
            self.straznik_cel = None
            self.klik_ramka_false.pop(cel["id"], None)
            self.cel = None
            return True
        if bez >= STRAZNIK_CEL_S1 and not st["s1"] and odl <= 1:
            st["s1"] = True
            log(f"[STRAZNIK] cel {cel['nazwa']} bez postępu {bez:.0f} s: Escape i ponowny klik.")
            self._escape()
            self.pauza(0.3, 0.6)
            try:
                bot._wlasny["t"] = float("-inf")       # wymuszone odświeżenie pozycji własnej
            except Exception:
                pass
            teraz = self.zegar()
            gracz = {"x": poz[0], "y": poz[1]}
            self._log_klik_ataku(cel, odl, None, "straznik")
            self.atak(cel, gracz)
            self.atak_czas = teraz
            self.cel_spadek = teraz
            self.pauza(0.05, 0.15)
        return False

    def _straznik_postepu(self, g, poz, teraz):
        """Strażnik postępu globalny (spec P2b, domyślnie WYŁĄCZONY: STRAZNIK_POSTEP). Postęp = zmiana
        pozycji, przyrost exp, spadek HP celu albo mniej zwłok do zebrania. S1: reset stanu walki;
        S2: zmiana celu patrolu albo skok na najbliższy punkt trasy; S3: powiadomienie krytyczne.
        Nie działa w PRZERWA/PAUZA/UH/WYPAD/JEDZENIE/LOOT i przy pliku STOP."""
        st = self.straznik_post
        poz3 = tuple(poz[:3])
        exp = g.get("exp")
        cel_hp = self.cel.get("hp") if self.cel else None
        n_zw = len(self.zwloki_czekajace)
        if not STRAZNIK_POSTEP or self._watchdog_wyjatek() \
                or (bot.STOP.exists() and not os.environ.get("RETRONIC_TESTY")) \
                or str(self.stan).startswith(("UH", "LOOT")):
            st.update(t=None)
            return False
        ref = st
        if ref["t"] is None or ref["poz"] != poz3 or (exp is not None and ref["exp"] is not None and exp > ref["exp"]) \
                or (cel_hp is not None and ref["cel_hp"] is not None and cel_hp < ref["cel_hp"]) \
                or n_zw < (ref.get("zw") or 0):
            st.update(t=teraz, poz=poz3, exp=exp, cel_hp=cel_hp, zw=n_zw, s=0)
            return False
        st["exp"] = exp if exp is not None else st["exp"]
        st["cel_hp"] = cel_hp if cel_hp is not None else st["cel_hp"]
        st["zw"] = n_zw
        bez = teraz - st["t"]
        if bez >= STRAZNIK_POSTEP_S3 and st["s"] < 3:
            st["s"] = 3
            log(f"[STRAZNIK] brak postępu {bez:.0f} s (stan {self.stan}).")
            self._tele_poscig("straznik_postepu", poziom=3, sekundy=round(bez, 1), faza=str(self.stan), poz=list(poz3))
            self._d3_nota("alarm")
            try:
                self.alarm(f"Bot bez postępu od {bez:.0f} s (stan {self.stan})")
            except Exception:
                pass
        elif bez >= STRAZNIK_POSTEP_S2 and st["s"] < 2:
            st["s"] = 2
            p = self.patrol if self._patrol_aktywny() else None
            log(f"[STRAZNIK] brak postępu {bez:.0f} s: {'zmiana celu patrolu' if p else 'skok na najbliższy punkt trasy'}.")
            self._tele_poscig("straznik_postepu", poziom=2, sekundy=round(bez, 1), faza=str(self.stan), poz=list(poz3))
            if p:
                try:
                    self.patrol_blok[p["m"]["id"]] = teraz + PATROL_BLOK_S
                    self._patrol_zakoncz(p, "straznik postępu")
                except Exception as e:
                    log(f"debug: strażnik postępu: {e!r}")
                self.patrol = None
            else:
                self._patrol_sync_idx(poz3)
            self.cel = None
        elif bez >= STRAZNIK_POSTEP_S1 and st["s"] < 1:
            st["s"] = 1
            log(f"[STRAZNIK] brak postępu {bez:.0f} s (stan {self.stan}): reset stanu walki.")
            self._tele_poscig("straznik_postepu", poziom=1, sekundy=round(bez, 1), faza=str(self.stan), poz=list(poz3))
            self.cel = None
            self._escape()
            self.zwloki_czekajace = []
            self.klik_cel = None
            self.skos_zle = {}
        return False

    def _watchdog_bezczynnosci(self, g, poz, lista, teraz):
        """Pozycja bez zmian >= WATCHDOG_BEZCZYNNOSC_S, nic żywego w pobliżu, HP ponad progiem ucieczki, bot nie
        jest wstrzymany: porzucamy odłożone zwłoki (to one zwykle trzymają bota w miejscu) i wracamy do trasy."""
        bezczynny = teraz - max(self.ruch_czas, self.aktywnosc_ts)
        if bezczynny < WATCHDOG_BEZCZYNNOSC_S or teraz - self.watchdog_ost < WATCHDOG_CO_S:
            return False
        if self.ucieczka or self.cel is not None or self.w_lootcie or self._watchdog_wyjatek():
            return False
        if g.get("proc", 100.0) <= self.prog_aktualny + WATCHDOG_HP_MARGINES:
            return False
        if self._zywe_w_promieniu(lista, poz, WATCHDOG_MOBY_ODL):
            return False
        # świeże zwłoki (< WATCHDOG_BEZCZYNNOSC_S od zabicia) zostają do lootu, porzucamy tylko stare
        def _swieze(z, t):
            return teraz - self.zwloki_wiek.get(tuple(z), t) < WATCHDOG_BEZCZYNNOSC_S
        swieze = [(z, t) for z, t in self.zwloki_czekajace if _swieze(z, t)]
        n = len(self.zwloki_czekajace) - len(swieze)
        self.watchdog_ost = teraz
        self.ruch_czas = teraz
        self.aktywnosc_ts = teraz
        self.zwloki_czekajace = swieze
        self.zwloki_chlod = {k: v for k, v in self.zwloki_chlod.items() if any(tuple(z) == tuple(k) for z, _ in swieze)}
        if not swieze:
            self.loot_chlod_do = teraz + WATCHDOG_LOOT_CHLOD_S
        log(f"Watchdog: bezczynność {bezczynny:.0f} s, porzucam odłożone zwłoki i idę dalej trasą")
        self._tele_poscig("watchdog_bezczynnosc", sekundy=round(bezczynny, 1), zwloki=n,
                          hp=round(g.get("proc", 0.0), 0), stan=str(self.stan), poz=list(poz[:3]))
        return True

    def _zywe_w_promieniu(self, lista, poz, odl):
        """Żywe potwory (nie gracze) na tym piętrze w promieniu `odl` pól."""
        wynik = []
        for s in lista or []:
            if s.get("gracz") or s.get("z") != poz[2] or s.get("hp", 100) <= 0:
                continue
            if self.potwory is not None and s.get("nazwa", "").casefold() not in self.potwory:
                continue
            if self.dystans((s["x"], s["y"]), poz) <= odl:
                wynik.append(s)
        return wynik

    def _droga_do(self, start, cel, zajete, skosy=False):
        """Droga (bez skosów, do pola przy celu) po mapie/znanych polach z `zajete`, bez ucieczki do drogi
        bez blokad (jak w droga()): None = brak drogi. R1c: bez drogi prostej druga próba ze skosami (limit długości)."""
        d = self._droga_do1(start, cel, zajete, skosy)
        if d is None and not skosy and POSCIG_SKOSY_ZAPAS and self._skos_mozliwy():
            d2 = self._droga_do1(start, cel, zajete, True)
            if d2 is not None and len(d2) <= POSCIG_SKOSY_MAX_DL:
                return d2
        return d

    def _droga_do1(self, start, cel, zajete, skosy):
        if self.mapa_zna(start, cel):
            z = start[2]
            blok = list(zajete) + self._zakaz_lista(start, cel) + [p for p in list(self.sciany) if p[2] == z and self.sciana(p)]
            dz = self._drzwi_xy(z)
            if dz:
                blok = [p for p in blok if tuple(p[:2]) not in dz]
            return self.mapa.droga(start, cel, blok, 1, skosy, limit=MAPA_LIMIT, znane=self._pola_pietra(z),
                                   **({"przepusc": {x * _K + y for x, y in dz}} if dz else {}))
        return self._droga_znane(start, cel, list(zajete) + self._zakaz_lista(start, cel), 1, skosy)

    def blokujacy_na_drodze(self, cel, poz, lista, kand):
        """Gdy cel jest nieosiągalny TYLKO dlatego, że drogę zajmują inne moby (bez nich droga jest i jest
        krótka, z nimi brak albo objazd): pierwszy po ścieżce mob, który ją zasłania (z kand), inaczej None."""
        c = (cel["x"], cel["y"])
        inne = [s for s in lista if s["id"] != cel["id"] and not s.get("gracz") and s["z"] == poz[2]
                and s.get("hp", 100) > 0 and (s["x"], s["y"]) != tuple(poz[:2])]
        prosto = self.dystans(c, poz)
        if (ROZPRAWA_BLOK_MIN_HP_CELU > 0 and prosto <= 2
                and 0 < cel.get("hp", 100) <= ROZPRAWA_BLOK_MIN_HP_CELU):
            return None      # ranny cel tuż obok: obchodzimy blokującego i dobijamy, nie bijemy go
        if prosto <= 1 or not self.mapa_zna(poz, c):
            return None      # tylko z pełną mapą serwera: znane pola (ślad trasy) nie mówią, gdzie jest korytarz
        if not any(self.dystans((s["x"], s["y"]), poz) <= prosto + 1 for s in inne):
            return None
        pola = {(s["x"], s["y"]): s for s in inne}
        skosy_ = bool(BLOK_WYJSCIE and POSCIG_SKOS_AWARYJNY)   # zaułek ze skosem jako jedynym wyjściem
        wolna = self._droga_do(poz, c, [], skosy_)
        if not wolna or len(wolna) > 2 * prosto + 3:
            return None
        zajeta = self._droga_do(poz, c, list(pola), skosy_)
        if zajeta is not None and len(zajeta) <= len(wolna) + BLOK_OBJAZD:
            return None
        ids = {s["id"] for s in kand}
        for p in wolna:
            m = pola.get(tuple(p[:2]))
            if m is not None:
                return m if m["id"] in ids else None
        return None

    def _rozprawa_blok(self, cel, poz, lista, kand, teraz, wroc=None):
        """Jeśli cel jest zasłonięty mobami: log, rozprawa z pierwszym blokującym i zwraca go (inaczej None)."""
        m = self.blokujacy_na_drodze(cel, poz, lista, kand)
        if m is None:
            return None
        log(f"Droga do {cel['nazwa']} zablokowana przez {m['nazwa']} ({m['x']},{m['y']}), bije blokującego.")
        self.rozprawa = {"id": m["id"], "wroc": wroc if wroc is not None else cel["id"],
                         "do": teraz + ROZPRAWA_BLOK_MAX}
        return m

    def mob_blisko(self, poz, odl):
        """Żywy potwór (nie gracz, z naszej listy) w odl polach, wg stworów z ostatniego obiegu."""
        for s in self.ostatnie_stwory:
            if s.get("gracz") or s["z"] != poz[2] or s.get("hp", 100) <= 0:
                continue
            if self.potwory is not None and s["nazwa"].casefold() not in self.potwory:
                continue
            if self.dystans((s["x"], s["y"]), poz) <= odl:
                return True
        return False

    def mana_nie_rosnie_s(self, g, teraz):
        """Ile s mana stoi w miejscu (< max, bez rzutu czaru w tym czasie), gdy to >= JEDZENIE_MANA_BRAK_S; inaczej None.
        Regeneracja many wymaga najedzenia, więc brak wzrostu = głód (tak jak brak wzrostu HP)."""
        mana, max_mana = g.get("mana"), g.get("max_mana")
        if mana is None or not max_mana or mana >= max_mana:
            return None
        okno = float(JEDZENIE_MANA_BRAK_S)
        stoi = teraz - self.mana_wzrost
        if stoi < okno or teraz - max(self.ml_ostatni, self.czar_ostatni) < okno:
            return None
        return stoi

    def _stan_many(self, g):
        mana, mx = g.get("mana"), g.get("max_mana")
        if mana is None or not mx:
            return "mana ?"
        return f"mana {int(mana)}/{int(mx)} ({100 * mana / mx:.0f}%), ML {'on' if ML_CZAR_AKTYWNY else 'off'}"

    def jedzenie_potrzebne(self, g, teraz, poz=None):
        glod_hp = g["hp"] < g["max_hp"] and teraz - self.hp_wzrost >= CZAS_JEDZENIA
        glod_mana = None if glod_hp else self.mana_nie_rosnie_s(g, teraz)
        glod_walka = self._glod_w_walce(g, teraz, poz)
        if glod_walka is not None and teraz >= self.jedzenie_nie_do \
                and (self.jedzenie or (self.klik is not None and hasattr(self.loot, "zjedz"))):
            # głód po HP w walce: nie blokują go JEDZENIE_BLISKO/JEDZENIE_SPOKOJ (inaczej bot głoduje do końca walki)
            self._log_glod_walka(g, glod_walka, poz)
            return True
        if not glod_hp and glod_mana is None:
            return False
        if teraz < self.jedzenie_nie_do:
            return False                     # niedawno "brak jedzenia": nie ponawiamy
        if self.cel is not None and self.cel.get("odl", 99) <= JEDZENIE_BLISKO:
            return False                     # jedzenie z plecaka to 3-5 s ślepego bloku przy celu
        if poz is not None and self.mob_blisko(poz, JEDZENIE_BLISKO):
            return False
        if not self.jedzenie and self.klik is not None and hasattr(self.loot, "zjedz"):
            # bez klawisza: jemy z plecaka (loot.zjedz), tylko w spokoju (brak potwora w JEDZENIE_SPOKOJ pól)
            if poz is not None and self.mob_blisko(poz, JEDZENIE_SPOKOJ):
                return False
            self._log_glod_many(g, glod_mana)
            return True
        if not self.jedzenie:
            if not self.brak_klawisza_zalogowany:
                log("Wygląda na głód (HP nie rośnie), ale nie ustawiono klawisza jedzenia (--jedzenie).")
                self.brak_klawisza_zalogowany = True
            return False
        self._log_glod_many(g, glod_mana)
        return True

    def _mobow_blisko(self, poz, odl):
        n = 0
        for s in self.ostatnie_stwory:
            if s.get("gracz") or s.get("z") != poz[2] or s.get("hp", 100) <= 0:
                continue
            if self.potwory is not None and s["nazwa"].casefold() not in self.potwory:
                continue
            if self.dystans((s["x"], s["y"]), poz) <= odl:
                n += 1
        return n

    def _glod_w_walce(self, g, teraz, poz):
        """Ile s HP nie rośnie z regeneracji, gdy to głód w walce i jedzenie jest bezpieczne; inaczej None.
        Tylko gdy potwór jest blisko (inaczej działa zwykła ścieżka). Exura i ucieczka mają pierwszeństwo:
        ich tick jest przed jedzeniem, a tu wymagamy HP% >= próg ucieczki + margines."""
        if not JEDZENIE_W_WALCE or poz is None:
            return None
        if g.get("hp") is None or not g.get("max_hp") or g["hp"] >= g["max_hp"]:
            return None
        if self.ucieczka or self.ostrozny:
            return None
        bez = teraz - self.hp_regen
        if bez < CZAS_JEDZENIA_WALKA:
            return None
        if teraz - self.jedzenie_walka_ost < JEDZENIE_WALKA_PONOW_S:
            return None
        walka = (self.cel is not None and self.cel.get("odl", 99) <= JEDZENIE_SPOKOJ) \
            or self.mob_blisko(poz, JEDZENIE_SPOKOJ)
        if not walka:
            return None
        proc = g.get("proc", 100.0 * g["hp"] / g["max_hp"])
        wymagane = self.prog_aktualny + JEDZENIE_WALKA_HP_MARGINES
        if not self.jedzenie:
            wymagane += JEDZENIE_WALKA_PLECAK_PP * self._mobow_blisko(poz, 2)
        if proc < wymagane:
            return None
        return bez

    def _log_glod_walka(self, g, bez, poz):
        self.jedzenie_walka_ost = self.zegar()
        odl = self.cel.get("odl") if self.cel is not None else None
        if odl is None:
            odl = min((self.dystans((s["x"], s["y"]), poz) for s in self.ostatnie_stwory
                       if not s.get("gracz") and s.get("hp", 100) > 0 and s.get("z") == poz[2]), default="?")
        proc = g.get("proc", 100.0 * g["hp"] / g["max_hp"])
        log(f"Jedzenie w walce: HP nie rośnie od {bez:.0f} s (hp {proc:.0f}%, troll odl {odl})")
        self._tele_poscig("jedzenie_walka", od_s=round(bez), hp_proc=round(proc, 1), odl=odl,
                          mobow=self._mobow_blisko(poz, 2), klawisz=int(bool(self.jedzenie)))

    def _log_glod_many(self, g, glod_mana):
        if glod_mana is None:
            return
        log(f"Jedzenie: mana nie rośnie od {glod_mana:.0f} s ({self._stan_many(g)})")
        self._tele_poscig("jedzenie_mana", od_s=round(glod_mana), mana=g.get("mana"), max_mana=g.get("max_mana"),
                          ml=int(bool(ML_CZAR_AKTYWNY)))

    def prog_uciekania(self, nazwa):
        # niżej niż PROG_UCIEKANIA_MIN nie schodzimy (też dla progów nauczonych dawniej i zapisanych w pliku)
        return max(PROG_UCIEKANIA_MIN, self.progi_uciekania.get(nazwa.casefold(), HP_UCIEKAJACEGO))

    def ucz_uciekania(self, cel, odl):
        """Potwór, który stał obok, odszedł: zapamiętaj HP, przy którym zaczął uciekać.
        Liczy się tylko, gdy obok walczył z HP ponad obecnym progiem i oberwał (inaczej to np.
        osaczony uciekinier albo zwykłe przejście), a jedna obserwacja przesuwa próg o <= NAUKA_KROK."""
        obok_hp, self.obok_hp = self.obok_hp, (max(self.obok_hp or 0, cel["hp"]) if odl <= 1 else None)
        if self.poprzednia_odl is not None and self.poprzednia_odl <= 1 and odl >= 2 \
                and 0 < cel["hp"] < HP_UCIEKAJACEGO + 20 and obok_hp is not None \
                and obok_hp > cel["hp"] and obok_hp >= self.prog_uciekania(cel["nazwa"]):
            nazwa = cel["nazwa"].casefold()
            stary = self.progi_uciekania.get(nazwa)
            nowy = cel["hp"] if stary is None else \
                round(stary + max(-NAUKA_KROK, min(NAUKA_KROK, 0.3 * (cel["hp"] - stary))))
            nowy = max(PROG_UCIEKANIA_MIN, nowy)
            if nowy != stary:
                self.progi_uciekania[nazwa] = nowy
                log(f"{cel['nazwa']} ucieka przy ~{nowy}% HP (zaobserwowano {cel['hp']}%).")
                if self.klik is not None:
                    try:
                        PLIK_UCIEKANIA.write_text(json.dumps(self.progi_uciekania, ensure_ascii=False))
                    except OSError:
                        pass
        self.poprzednia_odl = odl

    @staticmethod
    def przewidz_ucieczke(cel, poz):
        """Pole, na które uciekający potwór zaraz wejdzie: krok dalej od gracza."""
        return (cel["x"] + (cel["x"] > poz[0]) - (cel["x"] < poz[0]),
                cel["y"] + (cel["y"] > poz[1]) - (cel["y"] < poz[1]))

    def uciekajacy(self, cel):
        """Cel ucieka albo zaraz zacznie: hp <= próg ucieczki + 10 albo <= UCIEKAJACY_HP."""
        hp = cel.get("hp", 100)
        return hp <= self.prog_uciekania(cel["nazwa"]) + DOBICIE_PREMIA_MARGINES or hp <= UCIEKAJACY_HP

    def umierajacy(self, cel, odl):
        """Prawie martwy (uciekający) cel w zasięgu dobicia: DOBICIE_ZASIEG_UCIEKAJACY pól."""
        return self.uciekajacy(cel) and odl <= DOBICIE_ZASIEG_UCIEKAJACY

    def objazd_ignorowanie(self, cel, odl):
        """Jak długo ignorować cel bez drogi: umierającego tylko chwilę (OBJAZD_DOBICIE), reszta 90 s."""
        return OBJAZD_DOBICIE if self.umierajacy(cel, odl) else OBJAZD_IGNOROWANIE

    def limit_pogoni(self, cel, odl):
        """s bez postępu (ani zbliżenia, ani ruchu bota w stronę celu), po których odpuszczamy cel."""
        return POGON_LIMIT

    def twardy_limit(self, cel, odl):
        """s od chwili, gdy cel zaczął uciekać, po których odpuszczamy go niezależnie od postępu."""
        if cel["hp"] <= POGON_DOBICIE_HP and odl <= DOBICIE_ZASIEG_UCIEKAJACY:
            return POGON_TWARDY
        return POGON_TWARDY_INNY

    def ocen_pogon(self, cel, odl, teraz):
        """Licznik postępu pościgu; zwraca tekst powodu odpuszczenia albo None.
        Zwykły cel: postęp = dystans spadł poniżej dotychczasowego minimum.
        Uciekający: postęp także, gdy bot się rusza (A*) i cel nie jest dalej niż minimum + POGON_ROZRZUT;
        przerwy (jedzenie, loot) nie liczą się do braku postępu; twardy limit liczony od początku ucieczki."""
        luka = teraz - self.pogon_tick_ost
        self.pogon_tick_ost = teraz
        if luka > POGON_LUKA:
            self.pogon_postep = min(teraz, self.pogon_postep + luka)
        ucieka = self.uciekajacy(cel)
        if odl < self.pogon_odl:
            self.pogon_odl, self.pogon_postep = odl, teraz
        elif ucieka and teraz - self.ruch_czas < POGON_RUCH and odl <= self.pogon_odl_ost + POGON_ROZRZUT:
            self.pogon_postep = teraz        # bot idzie, a cel nie ucieka szybciej niż my (dystans nie rośnie)
        self.pogon_odl_ost = odl
        if ucieka:
            if self.pogon_uciek[0] != cel["id"]:
                self.pogon_uciek = (cel["id"], teraz)
            twardy = self.twardy_limit(cel, odl)
            if odl > 2 and teraz - self.pogon_uciek[1] > twardy:
                return f"od {twardy:.0f} s gonię uciekającego bez skutku"
        if odl > 2 and teraz - self.pogon_postep > self.limit_pogoni(cel, odl):
            return f"od {self.limit_pogoni(cel, odl):.0f} s nie zbliżam się"
        return None

    def odpusc_pogon(self, cel, teraz):
        """Ignorowanie odpuszczonego celu: uciekający krótko (potem próba od nowa), reszta POGON_IGNOROWANIE."""
        self.ignorowane[cel["id"]] = teraz + (POGON_IGNOROWANIE_DOBICIE if self.uciekajacy(cel) else POGON_IGNOROWANIE)

    def _cel_w_grze(self):
        """id aktualnie zaznaczonego celu w grze (komenda cel_ataku) albo None; (id, odczytano)."""
        try:
            odp = self.zapytaj({"cmd": "cel_ataku"})
            if isinstance(odp, dict) and "id" in odp:
                return odp["id"], True
        except bot.Zatrzymano:
            raise
        except Exception:
            pass
        return None, False

    @staticmethod
    def _koncowka_id(i):
        return "?" if i is None else f"..{str(i)[-4:]}"

    def _mapa_seria_ramka_false(self, teraz):
        """23.10: kolejny klik ataku z flagą ramki False. Po MAPA_ZAPOMNIJ_KLIKI takich z rzędu bez spadku HP żadnego celu
        unieważnia cache prostokąta mapy (ekran.zapomnij_prostokat): kliki trafiają obok celu, gdy cache zapamiętał zły
        prostokąt (przejściowy układ okien klienta po serwisie). Najwyżej raz na MAPA_ZAPOMNIJ_CO_S, jeden wpis [EKRAN]."""
        self.mapa_ramka_false_seria += 1
        n = self.mapa_ramka_false_seria
        if not MAPA_ZAPOMNIJ_KLIKI or n < MAPA_ZAPOMNIJ_KLIKI or teraz - self.mapa_zapomnij_ost < MAPA_ZAPOMNIJ_CO_S:
            return
        self.mapa_zapomnij_ost = teraz
        self.mapa_ramka_false_seria = 0
        try:
            import ekran  # noqa: PLC0415
            stare = ekran.zapomnij_prostokat()
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"[EKRAN] {n} klików ataku z rzędu ramka_false bez spadku HP, ale unieważnienie prostokąta mapy nie poszło: {e!r}")
            return
        log(f"[EKRAN] {n} klików ataku z rzędu ramka_false bez spadku HP żadnego celu: zapominam prostokąt mapy {stare}, "
            f"wykryję od nowa (najwyżej raz na {MAPA_ZAPOMNIJ_CO_S:.0f} s)")

    # --- zwiecha walki (23.10; zwiecha.py) ---

    def _zwiecha_det(self):
        if self.zwiecha is None:
            import zwiecha  # noqa: PLC0415
            self.zwiecha = zwiecha.Detektor(sys.modules[__name__])
        return self.zwiecha

    def _zwiecha_zdarzenie(self, rodzaj, poz, teraz):
        """Klik bez efektu / S2 strażnika celu: zdarzenie epizodu zwiechy. Kolejny szczebel napraw od razu (bez czekania na tick)."""
        if not ZWIECHA:
            return
        try:
            if self._zwiecha_det().zdarzenie(teraz, rodzaj, poz):
                self._zwiecha_tick(None, poz, teraz)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"debug: zwiecha błąd {e!r}")

    def _zwiecha_tick(self, g, poz, teraz):
        """Co obieg: przyrost expa kończy epizod; szczebel napraw, gdy zdarzenia wciąż bez zabicia. Nigdy STOP ani alarm krytyczny."""
        if g is not None and g.get("proc") is not None:
            self._zwiecha_hp = g.get("proc")
        if not ZWIECHA or (self.zwiecha is None):
            return
        try:
            if (bot.STOP.exists() and not os.environ.get("RETRONIC_TESTY")) or self._watchdog_wyjatek() \
                    or str(self.stan).startswith(("UH", "PRZERWA", "PAUZA", "WYPAD")):
                return
            k = self.zwiecha.tick(teraz, self.exp_teraz)
            if k:
                self._zwiecha_napraw(k, poz, teraz)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"debug: zwiecha błąd {e!r}")

    def _zwiecha_napraw(self, k, poz, teraz):
        """Szczebel 1: miękka (zapomnij prostokąt mapy, Escape, wyczyść ignorowanie z kliknięć/strażnika, liczniki, cel);
        2: + zignoruj stwory w pobliżu i zmień cel patrolu / skocz na najbliższy punkt trasy; 3: + restart procesu."""
        det = self.zwiecha
        poz3 = tuple(poz[:3])
        hp = self._zwiecha_hp
        opisy = {1: "miękka (prostokąt mapy, Escape, wyczyszczone ignorowanie i liczniki)",
                 2: "inny punkt (stwory w pobliżu ignorowane, zmiana celu patrolu / trasy)",
                 3: "restart procesu bota"}
        log(f"ZWIECHA: {len(det.zdarzenia)} nieudanych ataków bez zabicia od {det.od_s(teraz):.0f} s (stan {self.stan}, "
            f"poz {poz3}, HP {hp:.0f}%), naprawa {k}/3: {opisy[k]}.")
        self._tele_poscig("zwiecha", szczebel=k, sekundy=round(det.od_s(teraz), 1), zdarzen=len(det.zdarzenia),
                          faza=str(self.stan), poz=list(poz3))
        if teraz - self.mapa_zapomnij_ost >= MAPA_ZAPOMNIJ_CO_S:      # ten sam limit co _mapa_seria_ramka_false (najwyżej raz na MAPA_ZAPOMNIJ_CO_S s)
            self.mapa_zapomnij_ost = teraz
            try:
                import ekran  # noqa: PLC0415
                ekran.zapomnij_prostokat()
            except bot.Zatrzymano:
                raise
            except Exception as e:
                log(f"ZWIECHA: unieważnienie prostokąta mapy nie poszło: {e!r}")
        self._escape()
        for id_, (powod, _do) in list(self.ignor_powod.items()):
            if powod in ("atak_klik", "straznik", "limit_walki"):
                self.ignorowane.pop(id_, None)
                self.ignor_powod.pop(id_, None)
        self.klik_ramka_false.clear()
        self.straznik_cel = None
        self.cel = None
        self.klik_cel = None
        self.mapa_ramka_false_seria = 0
        if k >= 2:
            if hp >= ZWIECHA_RESTART_HP:
                for s in self.ostatnie_stwory or []:
                    if not s.get("gracz") and s.get("z") == poz3[2] and s.get("hp", 100) > 0 \
                            and self.dystans((s["x"], s["y"]), poz3) <= 3:
                        self._ignoruj(s["id"], teraz + ZWIECHA_IGNOR_S, "straznik")
            p = self.patrol if self._patrol_aktywny() else None
            if p:
                try:
                    self.patrol_blok[p["m"]["id"]] = teraz + PATROL_BLOK_S
                    self._patrol_zakoncz(p, "zwiecha")
                except Exception as e:
                    log(f"debug: zwiecha: patrol {e!r}")
                self.patrol = None
            else:
                self._patrol_sync_idx(poz3)
        if k >= 3:
            if not ZWIECHA_RESTART:
                log("ZWIECHA: restart procesu wyłączony (ZWIECHA_RESTART=0), zostaje powtórka szczebla 2.")
            elif hp < ZWIECHA_RESTART_HP:
                log(f"ZWIECHA: restart odłożony: HP {hp:.0f}% < {ZWIECHA_RESTART_HP:.0f}%, następna próba po kolejnych zdarzeniach.")
            else:
                self.zwiecha_restart = True      # mozg._slepota_watchdog: restart procesu (bez alarmu krytycznego i bez STOP)

    def _log_klik_ataku(self, cel, odl, flaga, powod, w_grze=None):
        if w_grze is None:
            w_grze = self._cel_w_grze()[0]
        elif w_grze == "?":
            w_grze = None                 # pościg: bez dodatkowego zapytania do rdzenia
        log(f"[ATAK] klik: {cel['nazwa']} id{self._koncowka_id(cel['id'])} odl {odl} HP {cel.get('hp')}% | "
            f"flaga w pamięci {flaga} | cel w grze id{self._koncowka_id(w_grze)} | powód {powod}")

    def _atak_poscig(self, cel, gracz):
        """Klik ataku z ponow_atak (pościg): zliczany do telemetrii poscig_koniec.kliki_ataku (11.10)."""
        self.kliki_ataku_poscig = getattr(self, "kliki_ataku_poscig", 0) + 1
        try:
            self._log_klik_ataku(cel, self.dystans((cel["x"], cel["y"]), (gracz["x"], gracz["y"])), None, "poscig", "?")
        except bot.Zatrzymano:
            raise
        except Exception:
            pass
        return self.atak(cel, gracz)

    def ponow_atak(self, cel, poz):
        """Pościg za uciekającym: co POSCIG_ATAK_CO s ponawiamy atak (Alt+klik), jeśli ramka (flaga
        w pamięci) mówi, że atak nie trwa; klik w atakowanego wyłączyłby atak, więc tylko przy False."""
        teraz = self.zegar()
        gracz = {"x": poz[0], "y": poz[1]}
        if ATAK_TYLKO_PRZY_CELU and self.dystans((cel["x"], cel["y"]), poz) > 1:
            # atak działa tylko obok celu: z dystansu ani nie klikamy, ani nie czekamy na weryfikację
            self.atak_weryf = None
            return False
        if self.atak_weryf is not None:
            # weryfikacja ostatniego kliku odczytem flagi z bieżącego obrotu (bez blokującego czekania)
            id_k, czas_k = self.atak_weryf
            if id_k != cel["id"] or teraz - czas_k > POSCIG_ATAK_WERYF_MAX:
                self.atak_weryf = None
            elif teraz - czas_k >= POSCIG_ATAK_WERYF_MIN:
                self.atak_weryf = None
                try:
                    po = self.czy_atakowany(cel, gracz)
                except bot.Zatrzymano:
                    raise
                except Exception:
                    po = None
                if po is False:
                    self._atak_poscig(cel, gracz)
                    self.atak_czas = self.zegar()
                    self.atak_blok[cel["id"]] = self.atak_czas + POSCIG_ATAK_BLOK
                    log(f"Atak na {cel['nazwa']} nie wrócił po kliku, klik cofający i blokada ponawiania {POSCIG_ATAK_BLOK:.0f} s.")
                    return True
                return False
        if teraz - self.atak_czas < POSCIG_ATAK_CO:
            return False
        if not self.w_widoku({**cel, "z": cel.get("z", poz[2])}, poz):
            return False                     # poza widokiem klik trafiłby w panel UI
        try:
            trwa = self.czy_atakowany(cel, gracz)
        except bot.Zatrzymano:
            raise
        except Exception:
            return False
        if trwa is not False:
            self.atak_falsz = (cel["id"], 0)
            return False
        # Alt+klik na atakowanym celu wyłącza atak: ponawiamy dopiero po kilku odczytach False z rzędu
        id_, n = self.atak_falsz
        n = n + 1 if id_ == cel["id"] else 1
        self.atak_falsz = (cel["id"], n)
        if n < POSCIG_ATAK_ODCZYTY or self.atak_blok.get(cel["id"], 0) > teraz or (self.dystans((cel["x"], cel["y"]), poz) <= 1 and not ATAK_TYLKO_PRZY_CELU):
            return False
        self._atak_poscig(cel, gracz)
        self.atak_czas = self.zegar()
        self.atak_falsz = (cel["id"], 0)
        # weryfikacja: flaga po kliku; nadal False = klik chybił albo wyłączył trwający atak -> jeden klik cofający
        if POSCIG_ATAK_WERYF <= 0:
            self.atak_weryf = (cel["id"], self.atak_czas)
            return True
        self.spij(POSCIG_ATAK_WERYF)
        try:
            po = self.czy_atakowany({k: v for k, v in cel.items() if k != "atakowany"}, gracz)
        except bot.Zatrzymano:
            raise
        except Exception:
            po = None
        if po is False:
            self._atak_poscig(cel, gracz)
            self.atak_czas = self.zegar()
            self.atak_blok[cel["id"]] = self.atak_czas + POSCIG_ATAK_BLOK
            log(f"Atak na {cel['nazwa']} nie wrócił po kliku, klik cofający i blokada ponawiania {POSCIG_ATAK_BLOK:.0f} s.")
        return True

    def _poscig_przerwanie(self):
        """Powód, dla którego szybki pościg trzeba przerwać z zewnątrz (mózg: pauza, rozmowa), albo None."""
        return None

    def _grozni_w_zasiegu(self, lista, poz):
        return [s for s in self.inni_gracze(lista, poz) if self.stop_przy_graczach or self.gracz_grozny(s)]

    def poscig_wejscie(self, cel, g, poz, odl):
        """Czy wolno wejść w szybką pętlę pościgu (odl >= 2, cel dalej niż obok)."""
        teraz = self.zegar()
        if odl < 2 or self.ucieczka or self.ostrozny or self.w_lootcie or self._poscig_przerwanie():
            return False
        if g and g.get("proc") is not None and g["proc"] <= self.prog_aktualny + POSCIG_HP_MARGINES:
            return False
        lista = self.ostatnie_stwory or []
        if any(s["id"] != cel["id"] and self.dystans((s["x"], s["y"]), poz) <= 1
               for s in self.kandydaci(lista, poz)):
            return False                     # inny potwór stoi obok: bijemy jego, nie gonimy
        if self._grozni_w_zasiegu(lista, poz):
            return False                     # groźny gracz (GM/PK) w zasięgu: wolniejszy tryb; zwykły gracz nie zmienia zachowania
        seria = self.poscig_seria
        if seria is not None and teraz - seria[2] > POSCIG_SERIA_LUKA:
            seria = self.poscig_seria = None
        if teraz < self.poscig_przerwa_do:
            return False
        if seria is not None:
            if odl < seria[1]:
                seria[0], seria[1] = teraz, odl   # zbliżamy się: liczymy ciągły pościg od nowa
            elif teraz - seria[0] > POSCIG_SERIA_MAX:
                self.poscig_przerwa_do = teraz + POSCIG_PRZERWA
                self.poscig_seria = None
                return False
        return True

    def _poscig_przeglad(self, cel, poz, hp_ref, puls=False):
        """Co POSCIG_PRZEGLAD s w pętli: HP gracza i otoczenie z odczytów pamięci (bez telemetrii).
        Zwraca (powód wyjścia albo None, odniesienie HP). puls=True (tryb trzymania, Q3 11.10): puls strażnika klawiszy
        przed, między dwoma RPC i po przeglądzie, żeby blokada pętli nie liczyła się jako jeden długi brak pulsu."""
        try:
            if puls:
                self.postac.puls()
            g = self.gracz()
            if puls:
                self.postac.puls()
            lista = self.stwory(POSCIG_PRZEGLAD_WIEK)
            if puls:
                self.postac.puls()
        except bot.Zatrzymano:
            raise
        except Exception:
            return None, hp_ref
        self.ostatnie_stwory = lista
        self.odnotuj_stwory(lista, poz)
        proc = g.get("proc", 100.0)
        if hp_ref is not None and proc <= hp_ref - POSCIG_HP_SPADEK:
            return "hp_spadek", hp_ref
        if proc <= self.prog_aktualny + POSCIG_HP_MARGINES:
            return "hp_prog", hp_ref
        if self._zdrowie_gotowy(g, self.zegar()):
            return "zdrowie_czar", hp_ref         # wyjście z pętli: główny tick rzuci exura
        if self._grozni_w_zasiegu(lista, poz):
            return "obcy_gracz", hp_ref
        if any(s["id"] != cel["id"] and self.dystans((s["x"], s["y"]), poz) <= 1
               for s in self.kandydaci(lista, poz)):
            if POSCIG_GRYZACY_MIN_HP > 0:
                c = next((s for s in lista if s["id"] == cel["id"]), cel)
                if (c.get("hp", 100) <= POSCIG_GRYZACY_MIN_HP and c.get("hp", 100) > 0
                        and self.dystans((c["x"], c["y"]), poz) <= 3):
                    return None, proc if hp_ref is None else max(hp_ref, proc)   # dobijamy rannego mimo gryzącego
            return "gryzacy", hp_ref
        return None, proc if hp_ref is None else max(hp_ref, proc)

    def _tele_poscig(self, typ, **d):
        if self.tele:
            try:
                self.tele.zdarzenie(typ, **d)
            except Exception as e:   # telemetria nigdy nie wywraca bota
                log(f"debug: telemetria błąd {e!r}")

    # --- 15.10: log decyzji D1/D2 dla przyszłego modelu lokalnego (SPEC_model_lokalny_1015, krok A) ---
    # Tylko odczyt: bez zapytań do gry, bez A*, bez losowania, bez zmiany stanu bota poza licznikiem id.
    def _cechy_opcji(self, s, poz, lista, ogien):
        """Cechy jednego kandydata na cel z tego, co bot już ma (lista stworów, pozycja, maska parzącego ognia)."""
        sx, sy = s["x"], s["y"]
        wokol = sum(1 for m in lista if m.get("id") != s.get("id") and not m.get("gracz") and m.get("hp", 100) > 0
                    and m.get("z", poz[2]) == poz[2] and max(abs(m["x"] - sx), abs(m["y"] - sy)) <= 2)
        gr = [max(abs(m["x"] - sx), abs(m["y"] - sy)) for m in lista
              if m.get("gracz") and m.get("nazwa") != self.postac.nazwa and m.get("z", poz[2]) == poz[2]]
        c = {"id": s["id"], "n": s["nazwa"], "dx": sx - poz[0], "dy": sy - poz[1],
             "odl": self.dystans((sx, sy), poz), "droga": None,   # droga A*: bot jej tu nie liczy, więc null
             "hp": s.get("hp"), "przy_celu2": wokol, "odl_gracza": min(gr) if gr else None,
             "ucieka": bool(self.uciekajacy(s))}
        if ogien is not None:
            c["ogien_przy"] = any(max(abs(a - sx), abs(b - sy)) <= OGIEN_PARZY_ODL_CELU for a, b in ogien)
        return c

    def _d3_tick(self, g, poz, teraz):
        """D3 krok A: detektor zawieszki poza walką + log opcji wyjścia; nic nie zmienia w ruchu. Błąd tylko w logu."""
        try:
            if not D3_LOG or not self.tele:
                self._d3 = None                # wyłączone w trakcie: bez wiszącej zawieszki
                return
            if getattr(self, "_d3", None) is None:
                import d3_zawieszka  # noqa: PLC0415
                self._d3 = d3_zawieszka.Zawieszka(self, sys.modules[__name__])
            self._d3.tick(g, poz, teraz)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"debug: D3 błąd {e!r}")

    def _ratunek_det(self):
        """Detektor ratunku (jeden na proces, ratunek.detektor) z trasą tej instancji; None, gdy RATUNEK_HAIKU=0."""
        if not RATUNEK_HAIKU:
            return None
        import ratunek  # noqa: PLC0415
        det = ratunek.detektor(sys.modules[__name__])
        if getattr(self, "_ratunek_trasa_id", None) != id(self.punkty):
            det.ustaw_trase(self.punkty)
            self._ratunek_trasa_id = id(self.punkty)
        return det

    def _ratunek_zglos(self, sygnaly):
        if sygnaly:
            import ratunek  # noqa: PLC0415
            plik = None if os.environ.get("RETRONIC_TESTY") else ratunek.plik_logu(instancja.S.logi)
            ratunek.zglos(sygnaly, log=log, tele=self.tele, plik_logu=plik, stan=str(self.stan),
                          pytaj=bool(RATUNEK_HAIKU_PYTAJ) and RATUNEK_HAIKU == 1, kontekst=self._ratunek_kontekst,
                          limit_h=RATUNEK_LIMIT_H)

    def _ratunek_kontekst(self, rek):
        """Migawka dla Haiku w cieniu (F2a), wołana w pętli bota TYLKO gdy pytamy: same kopie z pamięci, zero RPC i zero I/O.
        Ciężkie rzeczy (przejścia z mapy, pliki, zrzut) robi wątek (ratunek_cien). Bez czatu i nicków graczy."""
        poz = tuple(rek.get("poz") or ())
        g = getattr(self, "ratunek_g", None) or {}
        stwory = []
        for s in list(getattr(self, "ostatnie_stwory", None) or ())[:30]:
            try:
                if poz and s.get("z", poz[2]) != poz[2]:
                    continue
                if s.get("gracz") and s.get("nazwa") == getattr(self.postac, "nazwa", None):
                    continue                                   # to my
                stwory.append({"gracz": bool(s.get("gracz")), "nazwa": None if s.get("gracz") else s.get("nazwa"),
                               "dx": s["x"] - poz[0] if poz else None, "dy": s["y"] - poz[1] if poz else None,
                               "hp": s.get("hp")})
            except Exception:
                continue
        return {"poz": poz, "stan": str(self.stan), "wypad": bool(self.wypad_aktywny), "punkty": list(self.punkty),
                "idx": getattr(self, "idx", None), "hp": g.get("hp"), "max_hp": g.get("max_hp"), "mana": g.get("mana"),
                "max_mana": g.get("max_mana"), "stwory": stwory, "mapa": getattr(self, "mapa", None)}

    def _ratunek_tick(self, poz, teraz):
        """Ratunek F1 (SPEC_ratunek_haiku_1019): sygnały S2-S4 co obieg; tylko log. W wypadzie (wyprawa) trasa łowiska nie
        obowiązuje, więc piętro nie jest sprawdzane. Błąd tylko w logu."""
        try:
            det = self._ratunek_det()
            if det is None:
                return
            if self.wypad_aktywny:
                det.pietro_t = 0.0
                trasa, det.trasa_pietra = det.trasa_pietra, None
                try:
                    self._ratunek_zglos(det.tick(teraz, poz, self.stan, self.exp_teraz))
                finally:
                    det.trasa_pietra = trasa
                return
            self._ratunek_zglos(det.tick(teraz, poz, self.stan, self.exp_teraz))
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"debug: ratunek błąd {e!r}")

    # --- strażnik orbit (SPEC_orbity_straznik_1020, B) ---

    def _straznik_planowane(self):
        """Wypad/wyprawa/dojście mają własny cel i własne piętra: tam strażnik tylko loguje (cień), nie reaguje."""
        w = self.wyprawa
        return bool(self.wypad_aktywny or self.dojscie_aktywne or (w is not None and getattr(w, "w", None) is not None))

    def _straznik_zle_pietro(self, poz):
        """S2 strażnika: trasa/patrol nie ma żadnego punktu na piętrze postaci (nie w wypadzie/dojściu/wyprawie/przejściu pięter)."""
        if not self.punkty or self._straznik_planowane():
            return False
        if self.pietra is not None and getattr(self.pietra, "st", None) is not None:
            return False
        wp = self._wp()
        if wp is not None:
            return not wp._trasa_na_pietrze(poz[2])
        return not any(p[2] == poz[2] for p in self.punkty)

    def _straznik_tick(self, poz, teraz):
        """Wykrycie orbity co obieg. 0 = nic (nie tworzy niczego); 1 = cień: tylko log i telemetria; 2 = start reakcji
        (jej kroki w _straznik_reakcja, po walce). Błąd tylko w logu."""
        try:
            tryb = int(STRAZNIK_ORBITY)
            if not tryb:
                if self._straznik is not None and self._straznik[1].aktywna():
                    self._straznik[1].sprzatnij()          # 2->0 w locie: oddaj wp.st / pietra.st, które ustawił strażnik
                return
            if self._straznik is None:
                import straznik_orbity  # noqa: PLC0415
                mod = sys.modules[__name__]
                det = straznik_orbity.Detektor(mod)
                rea = straznik_orbity.Reakcja(self, mod, log=lambda t: log(t))
                rea.det = det
                self._straznik = (det, rea)
            det, rea = self._straznik
            if rea.aktywna():
                if tryb < 2:
                    rea.sprzatnij()
                return                          # reakcja trwa: okno nie liczy ruchu planu wyjścia
            wp = self._wp()
            if wp is not None and wp.st is not None:
                det.reset()                     # wpadniecie.py ma własne wyjście (i alarm)
                return
            for zd in det.tick(teraz, poz, self.stan, self._straznik_zle_pietro(poz), self.exp_teraz):
                if tryb >= 2 and not self._straznik_planowane():
                    if not rea.aktywna():          # dwa zdarzenia w jednym obiegu (np. pietro + orbita): jeden epizod
                        rea.start(zd, teraz)
                else:
                    log(f"[ORBITA] cień: {zd['rodzaj']} w {tuple(zd['poz'])}: {rea._opis(zd)}"
                        f"{'; bez reakcji (wypad/dojście/wyprawa)' if tryb >= 2 else ''}.")
                    self._straznik_tele("cien" if tryb < 2 else "cien_wypad", **{k: v for k, v in zd.items() if k != "t"})
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"debug: strażnik orbit błąd {e!r}")

    def _straznik_tele(self, etap, **d):
        if self.tele:
            try:
                self.tele.zdarzenie("straznik_orbita", etap=etap, **d)
            except Exception:
                pass

    def _straznik_reakcja(self, poz, teraz):
        """Krok reakcji strażnika (po walce, przed wpadnięciem): True = obieg zużyty."""
        try:
            rea = self._straznik[1]
            if not rea.aktywna():
                return False
            if int(STRAZNIK_ORBITY) < 2:
                rea.sprzatnij()
                return False
            return bool(rea.tick(poz, teraz))
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"[ORBITA] błąd reakcji {e!r}")
            try:
                self._straznik[1].sprzatnij()              # wyjątek w reakcji: oddaj wp.st / pietra.st (inaczej 3b doprowadzi do alarmu)
            except Exception:
                pass
            return False

    def _ratunek_zdarzenie(self, rodzaj, poz=None, **d):
        """Zdarzenie porażki (krok, klik, okrążenie) do detektora ratunku; tylko log."""
        try:
            det = self._ratunek_det()
            if det is not None:
                self._ratunek_zglos(det.zdarzenie(rodzaj, self.zegar(), poz, **d))
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"debug: ratunek błąd {e!r}")

    def _d3_nota(self, nazwa):
        """Akcja istniejącej reguły wyjścia z utknięcia -> d3_wynik.regula (tylko zapis)."""
        d3 = getattr(self, "_d3", None)
        if d3 is not None:
            d3.nota_reguly(nazwa)

    def _d3_zamknij(self):
        """Koniec pracy: zamknij trwającą zawieszkę (d3_wynik, koniec "stop")."""
        d3 = getattr(self, "_d3", None)
        if d3 is not None:
            d3.zamknij()

    def _decyzja_zapisz(self, rodzaj, poz, opcje, wybrana, **d):
        """Zapisuje rekord "decyzja" i zwraca jego id (None: wyłączone, brak telemetrii albo błąd)."""
        if not DECYZJE_LOG or not self.tele:
            return None
        try:
            self._decyzja_nr = getattr(self, "_decyzja_nr", 0) + 1
            self.tele.zdarzenie("decyzja", id=self._decyzja_nr, rodzaj=rodzaj, poz=list(poz[:3]), opcje=opcje,
                                wybrana=wybrana, **d)
            return self._decyzja_nr
        except Exception as e:   # telemetria nigdy nie wywraca bota
            log(f"debug: telemetria decyzja błąd {e!r}")
            return None

    def _decyzja_d1(self, kand, cel, poz, g, lista, klucz, gryzie):
        """D1: wybór celu. Opcje = kandydaci po filtrach (to, z czego bot faktycznie wybierał); regula = id pierwszego
        wg klucza (bez losowania DRUGI_CEL), wybrana = id faktycznego celu. Zwraca id decyzji albo None."""
        if not DECYZJE_LOG or not self.tele:
            return None
        try:
            ogien = self._ogien_parzy_dane(poz[2]) if OGIEN_PARZY_ODL_CELU >= 0 else None
            opcje = []
            for s_ in kand:
                c = self._cechy_opcji(s_, poz, lista, ogien)
                c["klucz"] = round(klucz(s_)[0], 2)      # wynik reguły bota (mniejszy = lepszy)
                opcje.append(c)
            regula = min(kand, key=klucz)["id"] if kand else None
            obok2 = sum(1 for m in lista if not m.get("gracz") and m.get("hp", 100) > 0
                        and m.get("z", poz[2]) == poz[2] and self.dystans((m["x"], m["y"]), poz) <= 2)
            return self._decyzja_zapisz("D1", poz, opcje, cel["id"], regula=regula, w_opcjach=any(
                s_["id"] == cel["id"] for s_ in kand), gryzie=bool(gryzie), mobow_obok2=obok2,
                hp_gracza=g.get("proc") if g else None)
        except Exception as e:
            log(f"debug: telemetria decyzja błąd {e!r}")
            return None

    def _decyzja_d2(self, cel, poz, g):
        """D2: start szybkiego pościgu (jedyna opcja "gonić" z cechami celu, jakie są pod ręką; tu bez A*)."""
        if not DECYZJE_LOG or not self.tele:
            return None
        try:
            lista = getattr(self, "ostatnie_stwory", None) or []
            ogien = self._ogien_parzy_dane(poz[2]) if OGIEN_PARZY_ODL_CELU >= 0 else None
            c = self._cechy_opcji(cel, poz, lista, ogien)
            c["akcja"] = "gonic"
            c["ogien_na_drodze"] = bool(self._ogien_na_drodze(poz, (cel["x"], cel["y"])))
            return self._decyzja_zapisz("D2", poz, [c], "gonic", cel_id=cel["id"], d1_id=getattr(self, "_d1_id_cel", None),
                                        hp_gracza=g.get("proc") if g else None)
        except Exception as e:
            log(f"debug: telemetria decyzja błąd {e!r}")
            return None

    # --- 15.10: mapa obecności mobów w trybie cienia (SPEC_patrol_respawn_1015, krok 2) ---
    # obecnosc.MapaObecnosci liczy z tego, co bot już ma (lista stworów, pozycja): zero zapytań do gry, zero A*,
    # zero losowania. Wynik trafia tylko do telemetrii (patrol_cel, decyzja D4); ruch bota się nie zmienia.
    _obecnosc = None             # None = jeszcze nie tworzona, False = nie da się (brak miejsc / błąd), inaczej MapaObecnosci
    _cien_wybor = None           # wynik cienia dla bieżącego _patrol_wybierz (None = brak)
    _wybor_meta = {}             # 20.10: metoda wyboru bieżącego _patrol_wybierz dla telemetrii/logu (patrz _patrol_nowy); {} = "inna"

    @staticmethod
    def _respawn_liczy():
        """Mapa obecności i wybór metody respawnu mają się liczyć: tryb cienia (PATROL_RESPAWN_CIEN) albo włączone
        PATROL_RESPAWN (20.10: sterowanie respawnem nie może zależeć od pokrętła cienia)."""
        return bool(PATROL_RESPAWN_CIEN or PATROL_RESPAWN)

    def _obecnosc_blad(self, gdzie, e):
        """Błąd mapy obecności: tylko log (pierwsze trzy razy i co 200.), nigdy wyjątek."""
        n = getattr(self, "_obecnosc_bledy", 0) + 1
        self._obecnosc_bledy = n
        if n <= 3 or n % 200 == 0:
            log(f"obecność: błąd w {gdzie} ({n}.): {e!r}")

    def _obecnosc_t(self):
        """Czas mapy obecności: zegar bota przesunięty do czasu ściennego (stan na dysku przeżywa restart)."""
        return self.zegar() + getattr(self, "_obecnosc_off", 0.0)

    def _obecnosc_mapa(self):
        """Mapa obecności; tworzona leniwie, gdy znamy miejsca patrolu (obszar = bbox miejsc + margines) i któreś z
        PATROL_RESPAWN_CIEN albo PATROL_RESPAWN jest włączone (tylko spot z trollami). Stan z OBECNOSC_STAN_PLIK (inny obszar = od zera).
        None = brak mapy (nic się nie dzieje)."""
        mo = self._obecnosc
        if mo is not None:
            return mo or None
        if not self._respawn_liczy() or not getattr(self, "miejsca", None):
            return None
        if not any("troll" in p for p in (self.potwory or ())):
            self._obecnosc = False                 # 15.10: mapa obecności zna tylko trolle (Edron/szczury: bez szumu)
            return None
        try:
            import obecnosc  # noqa: PLC0415
            self._obecnosc_off = time.time() - self.zegar()
            teraz = self._obecnosc_t()
            nowa = obecnosc.MapaObecnosci.dla_miejsc(self.miejsca)
            mo = None
            if OBECNOSC_STAN_PLIK is not None:
                mo = obecnosc.MapaObecnosci.wczytaj(OBECNOSC_STAN_PLIK, teraz)
                if mo is not None and (mo.bbox != nowa.bbox or mo.pietra != nowa.pietra):
                    mo = None              # stan z innego spotu: od zera
                if mo is not None:
                    log(f"obecność: wczytano stan mapy obecności ({len(mo.k)} komórek) z {OBECNOSC_STAN_PLIK}.")
            self._obecnosc = mo or nowa
            self._obecnosc_zapis_t = teraz
        except Exception as e:
            self._obecnosc = False
            self._obecnosc_blad("tworzeniu mapy", e)
        return self._obecnosc or None

    def _obecnosc_obserwuj(self, lista, poz):
        """Jedna obserwacja mapy obecności z ticka (lista stworów i pozycja są już w ręku) + zapis stanu co OBECNOSC_ZAPIS_S."""
        if not self._respawn_liczy() or poz is None:
            return
        try:
            mo = self._obecnosc_mapa()
            if mo is None:
                return
            import obecnosc  # noqa: PLC0415
            trolle = {n for n in (self.potwory or ()) if "troll" in n} or obecnosc.CEL_NAZWY   # tylko trolle
            mo.obserwuj(self._obecnosc_t(), poz, lista, trolle)
            self._obecnosc_zapisz()
        except bot.Zatrzymano:
            raise
        except Exception as e:
            self._obecnosc_blad("obserwacji", e)

    def _obecnosc_zabicie(self, c):
        """Zabity cel (c = słownik celu z "poz" = ostatnio widziane pole) do mapy obecności."""
        if not self._respawn_liczy():
            return
        try:
            mo = self._obecnosc_mapa()
            poz = c.get("poz") if c else None
            if mo is None or not poz:
                return
            import obecnosc  # noqa: PLC0415
            if "troll" not in str(c.get("nazwa", "")).casefold():       # mapa zna tylko trolle (jak _obecnosc_mapa)
                return
            mo.zabicie(self._obecnosc_t(), poz[0], poz[1], poz[2])
        except bot.Zatrzymano:
            raise
        except Exception as e:
            self._obecnosc_blad("zabiciu", e)

    def _obecnosc_zapisz(self, wymus=False):
        """Zapis stanu mapy (atomowo, obecnosc.zapisz) najwyżej co OBECNOSC_ZAPIS_S; wymus = na koniec pracy."""
        mo = self._obecnosc
        if not mo or OBECNOSC_STAN_PLIK is None:
            return
        try:
            t = self._obecnosc_t()
            if not wymus and t - getattr(self, "_obecnosc_zapis_t", float("-inf")) < OBECNOSC_ZAPIS_S:
                return
            self._obecnosc_zapis_t = t         # także przy błędzie: bez ponawiania co tick
            mo.zapisz(OBECNOSC_STAN_PLIK, t)
        except Exception as e:
            self._obecnosc_blad("zapisie stanu", e)

    def _patrol_cien_drogi(self, poz):
        """Drogi po grafie pliku miejsc (obecnosc.DrogiGraf, bez A*) {id: (pola, czas_s)} albo {} (wtedy linia prosta)."""
        try:
            g = self.__dict__.get("_cien_graf")
            if g is None:
                import obecnosc  # noqa: PLC0415
                g = obecnosc.DrogiGraf.z_pliku(bot.TRASY / PATROL_PLIK)
                self._cien_graf = g
            return g.drogi_z(poz) if g else {}
        except Exception as e:
            self._cien_graf = False
            self._obecnosc_blad("drogach grafu", e)
            return {}

    def _patrol_cien_przyblizenie(self, poz, m, d, drogi=None):
        """Droga i czas dojścia do miejsca m BEZ A*: najpierw graf pliku miejsc (`drogi` z _patrol_cien_drogi, rodzaj "graf");
        bez grafu: to samo piętro = linia prosta (Bresenham) po polach, czas = |dx|+|dy| pól
        (dzisiejsza odległość `d` kandydata) x KROK_S; inne piętro = tylko okolica miejsca, czas = pola poziome x KROK_S +
        SCHODY_S za piętro. Zwraca (droga [(x,y,z)], dojscie_s, rodzaj)."""
        import obecnosc  # noqa: PLC0415
        if drogi and m["id"] in drogi:
            pola, czas = drogi[m["id"]]
            return pola, czas, "graf"
        dz = abs(m["z"] - poz[2])
        if dz:
            pola = abs(m["x"] - poz[0]) + abs(m["y"] - poz[1])
            return [], pola * obecnosc.KROK_S + dz * obecnosc.SCHODY_S, "cel"
        x0, y0, x1, y1 = poz[0], poz[1], m["x"], m["y"]
        n = max(abs(x1 - x0), abs(y1 - y0))
        droga = [(x0 + (x1 - x0) * i // n, y0 + (y1 - y0) * i // n, m["z"]) for i in range(1, n + 1)] if n else []
        return droga, d * obecnosc.KROK_S, "linia"

    def _patrol_cien_licz(self, kand, poz):
        """Tryb cienia: wybór nowej metody (obecnosc.wybierz) na kandydatach `kand` [(m, d)], które patrol już ma. Wynik w
        self._cien_wybor (cel, wartosci, pewnosc, opcje) dla _patrol_cien_pola; błąd = brak wyniku, nigdy wyjątek."""
        self._cien_wybor = None
        if not self._respawn_liczy() or not kand:
            return
        try:
            mo = self._obecnosc_mapa()
            if mo is None:
                return
            t = self._obecnosc_t()
            gracze = [(gx, gy, poz[2]) for gx, gy in self._patrol_gracze(poz[2])]
            cele, opcje = [], []
            drogi = self._patrol_cien_drogi(poz)
            for m, d in kand:
                droga, dojscie_s, rodzaj = self._patrol_cien_przyblizenie(poz, m, d, drogi)
                cel = {"id": m["id"], "droga": droga, "dojscie_s": dojscie_s, "poz": (m["x"], m["y"], m["z"])}
                cele.append(cel)
                kom = mo.komorki_celu_i_drogi(cel)
                przy = mo.komorki_celu((m["x"], m["y"], m["z"]))
                wiek = [t - r for r in (mo.czas_odniesienia(k) for k in przy) if r is not None]
                opcje.append({"id": m["id"], "odl": d, "dojscie": round(dojscie_s, 1), "droga": len(droga), "przybl": rodzaj,
                              "oczekiwane": round(sum(mo.oczekiwane(k, t) * mo.kara_gracza(k, gracze) for k in kom), 3),
                              "od_wyczyszczenia_s": round(min(wiek), 1) if wiek else None,
                              "gracz_przy": any(mo.kara_gracza(k, gracze) < 1.0 for k in przy)})   # przy samym miejscu (droga: w wartości)
            cel_id, wart, pewnosc = mo.wybierz(cele, t, gracze)
            for o in opcje:
                o["wartosc"] = round(wart.get(o["id"], 0.0), 4)
            self._cien_wybor = {"cel": cel_id, "wartosci": {k: round(v, 4) for k, v in wart.items()},
                                "pewnosc": round(pewnosc, 3), "opcje": opcje}
        except bot.Zatrzymano:
            raise
        except Exception as e:
            self._cien_wybor = None
            self._obecnosc_blad("wyborze cienia", e)

    def _patrol_cien_pola(self, poz, m):
        """Pola cienia do rekordu patrol_cel wybranego miejsca m (+ rekord "decyzja" D4); {}, gdy nie ma wyniku cienia.
        cel_respawn = wybór nowej metody (None = za mała pewność, nowa metoda oddałaby decyzję dzisiejszej regule);
        zgodny = nowa metoda wybrałaby to samo miejsce (None, gdy cel_respawn None: metoda bez zdania)."""
        cw = self._cien_wybor
        if not cw:
            return {}
        try:
            cel = cw["cel"]
            zgodny = None if cel is None else cel == m["id"]     # None: nowa metoda bez zdania (nie zawyża zgodności)
            d4 = self._decyzja_zapisz("D4", poz, cw["opcje"], m["id"], regula=m["id"], cien=cel, zgodny=zgodny,
                                      pewnosc=cw["pewnosc"], w_opcjach=any(o["id"] == m["id"] for o in cw["opcje"]),
                                      metoda=self._wybor_meta.get("metoda", "inna"))     # 20.10: przy "respawn" regula == wybrana (nie wagi)
            return {"cel_respawn": cel, "wartosci": cw["wartosci"], "zgodny": zgodny, "pewnosc_respawn": cw["pewnosc"],
                    "d4_id": d4}
        except Exception as e:
            self._obecnosc_blad("polach cienia", e)
            return {}

    def _czas_kroku(self, poz):
        """Szacowany czas jednego kroku (s) po prędkości pola z mapy (najwolniejsze z pola i sąsiadów:
        czas zależy od pola, na które wchodzimy). 0.0, gdy mapa nie zna prędkości."""
        if self.mapa is None or not hasattr(self.mapa, "pole"):
            return 0.0
        try:
            v = 0
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                p = self.mapa.pole(poz[0] + dx, poz[1] + dy, poz[2])
                if p and 0 < p[2] <= 60:
                    v = max(v, p[2])
            return v * POSCIG_KROK_S_NA_PREDKOSC
        except Exception:
            return 0.0

    def _odczyt_poscig(self, cel):
        """Jednym RPC ("poscig"): pozycja gracza i stwór-cel (id, x, y, z, hp, flagi). Starszy rdzeń
        (nieznane polecenie) albo brak nazwy postaci: dwa zapytania jak dawniej ("stwor" + pozycja).
        -> (pozycja gracza (x, y, z), stwór albo None)."""
        nazwa = getattr(self.postac, "nazwa", None)
        if nazwa and self._poscig_rpc:
            try:
                o = self.zapytaj({"cmd": "poscig", "adres": cel["adres"], "id": cel["id"], "nazwa": nazwa})
                p = o["pozycja"]
                return (p["x"], p["y"], p["z"]), o["stwor"]
            except bot.Zatrzymano:
                raise
            except Exception as e:
                if "nieznane polecenie" in str(e) or isinstance(e, (KeyError, TypeError)):
                    self._poscig_rpc = False      # rdzeń bez komendy: do restartu zostają dwa zapytania
        s = self.zapytaj({"cmd": "stwor", "adres": cel["adres"], "id": cel["id"]})["stwor"]
        return tuple(self.postac.pozycja()), s

    # ---- szybki pościg w trybie TRZYMANIA klawisza (ciągły marsz) ----
    def _poscig_trzymaj_mozliwe(self):
        p = self.postac
        return bool(POSCIG_TRZYMAJ) and self.zegar() >= self.poscig_stuk_do and self.klik is not None and all(
            hasattr(p, a) for a in ("trzymaj_kierunek", "trzymany_kierunek", "puszczaj", "puls"))

    def _poscig_puszcz(self):
        """Puść trzymane klawisze (każde wyjście z pętli); błąd nie wywraca bota, tylko trafia do logu."""
        f = getattr(self.postac, "puszczaj", None)
        if f is None:
            return
        try:
            f()
        except Exception as e:
            log(f"BŁĄD puszczania klawiszy: {e!r}")

    def _pole_upadku(self, pole):
        """22.10: wejście na pole (x, y, z) zmienia piętro: nauczona dziura albo pole zmiany piętra z mapy (flaga 2) poza wypadem.
        Twardy podzbiór _pole_zablokowane: tego klawisz kolejkowany "na zapas" nie może nigdy zaryzykować."""
        return bool(self.dziura_nauczona(pole) or self.pole_zmiany_pietra(pole))

    def _pole_zablokowane(self, pole, zaj):
        """Pole, na które nie wolno wchodzić trzymanym klawiszem: stwór (nie cel), nauczona ściana, ściana z mapy."""
        if pole[:2] in zaj or self.sciana(pole) or self.pole_zmiany_pietra(pole) or self._ogien_na(pole):
            return True
        if self.mapa is not None:
            try:
                return self.mapa.flagi(*pole) & 1 and self.mapa.przechodnie(*pole) is False
            except Exception:
                return False
        return False

    def _poscig_skos(self, poz, xy, zaj):
        """Skos (dx, dy) trzymanym numpadem, gdy opłaca się (POSCIG_SKOS_KOSZT < 2 prostych kroków), cel jest
        daleko po obu osiach, a pole po skosie wolne i znane mapie. Inaczej None."""
        if not POSCIG_SKOS or POSCIG_SKOS_KOSZT >= 2.0 or self.mapa is None:
            return None
        ddx, ddy = xy[0] - poz[0], xy[1] - poz[1]
        if not ddx or not ddy or max(abs(ddx), abs(ddy)) < POSCIG_SKOS_ODL:
            return None
        v = ((ddx > 0) - (ddx < 0), (ddy > 0) - (ddy < 0))
        pole = (poz[0] + v[0], poz[1] + v[1], poz[2])
        if self._pole_zablokowane(pole, zaj) or not self.mapa_zna(poz, pole) or self.mapa.przechodnie(*pole) is not True:
            return None
        return v

    def _poscig_decyzja(self, s, poz, v_krok, zaj):
        """Który klawisz trzymać, gdy gracz stoi na poz, a krok w toku (v_krok, None = postać stoi) kończy
        się na Q = poz + v_krok. Kierunek wybieramy dla Q (tam zaczyna się następny krok), więc zakręt
        A* jest kolejkowany w kliencie jeszcze w trakcie kroku: postać ani się nie zatrzymuje, ani nie robi
        zbędnego kroku. -> (want, objazd, powod): want = wektor do trzymania albo None (puść),
        objazd=True gdy podejdz uznał cel za nieosiągalny."""
        xy = (s["x"], s["y"])
        poz = tuple(poz)
        if POSCIG_VKROK_SCIANA and v_krok is not None \
                and self._pole_zablokowane((poz[0] + v_krok[0], poz[1] + v_krok[1], poz[2]), zaj):
            v_krok = None       # trzymany klawisz w ścianę/zajęte pole: żaden krok nie trwa, liczymy z poz (skręt)
        q = poz if v_krok is None else (poz[0] + v_krok[0], poz[1] + v_krok[1], poz[2])
        if v_krok is not None and self.dystans(xy, q) <= 1:
            if POSCIG_OSTATNI_TRZYMAJ and (poz[0] + 2 * v_krok[0], poz[1] + 2 * v_krok[1]) == xy:
                # S4 11.10: cel stoi dokładnie przed nami na kierunku marszu: nie puszczamy, bo kolejny krok blokuje on sam
                # (nie ma kroku za dużo, a nie ma stalla po puszczeniu); pętla puści klawisz przy odl<=1 (finally)
                return v_krok, False, "ostatni_trzymany"
            if POSCIG_OSTATNI_DOCISKAJ and self.dystans(xy, poz) >= 2:
                # 12.10: stoimy dalej niż 1 pole od celu, a kolejny krok (klawisz trzymany) zbliża nas do niego:
                # puszczenie go zostawiało postać w odl 2-3 do czasu ponowienia (1,3 s), a cel w tym czasie odchodził
                return v_krok, False, "ostatni_dociska"
            return None, False, "ostatni"       # krok w toku kończy przy celu: klawisz puszczamy, krok się dokończy
        if v_krok is not None and not POSCIG_ANTYCYPACJA:
            return v_krok, False, None
        self.krok_prosto_ost = None             # nauka ścian w trybie trzymania robi licznik braku zmiany pozycji
        want = self._poscig_skos(q, xy, zaj)
        if want is None:
            self._ruch_przechwyt = []
            try:
                r = self.podejdz(xy, q, pilne=True, natychmiast=True, poscig=True)
                zlap = self._ruch_przechwyt
            finally:
                self._ruch_przechwyt = None
            if r is None:
                return None, True, None
            if not zlap:
                return v_krok, False, None
            k0 = zlap[-1][0]
            want = tuple(k0) if isinstance(k0, tuple) else bot.KIERUNKI[k0]
        pole = (q[0] + want[0], q[1] + want[1], q[2])
        if self._pole_zablokowane(pole, zaj):
            self.krok_prosto_ost = None         # to nie ściana do nauki: nie walczymy klawiszem o zajęte pole
            return None, False, "zajete"
        w = v_krok if v_krok is not None else want
        if want[0] and want[1] or w[0] and w[1]:
            self.krok_prosto_ost = None         # skos: brak ruchu to nie ściana (zły skos blokuje skos_zle)
        else:
            self.krok_prosto_ost = (poz, (poz[0] + w[0], poz[1] + w[1], poz[2]), self.zegar())
        self.klik_cel = None
        return want, False, None

    def _poscig_stabilny(self, want, q, xy, v_krok, zaj, st, teraz):
        """Filtr kierunku w trybie trzymania (przeciw oscylacji lewo-prawo przy zygzakującym celu):
        1) zakaz cofnięcia na pole, na którym staliśmy w ciągu POSCIG_PINGPONG_S (ping-pong A-B-A),
        2) histereza: po zmianie kierunku <POSCIG_HISTEREZA_S s temu albo gdy nowa oś ma <POSCIG_HISTEREZA_ODL
           pól różnicy, zostajemy przy dotychczasowym kierunku, o ile na jego osi cel jest jeszcze >= 2 pola dalej.
        st: {"ost": kierunek, "t_zm": czas zmiany, "hist": [(x, y, t)]}. -> (want, powod_zmiany albo None)."""
        if want is None:
            return None, None
        ost = st.get("ost")
        dx, dy = xy[0] - q[0], xy[1] - q[1]

        def pole(w):
            return (q[0] + w[0], q[1] + w[1], q[2])

        def banned(w):
            pp = pole(w)[:2]
            return any(h[:2] == pp and teraz - h[2] <= POSCIG_PINGPONG_S for h in st["hist"])

        def dobry(w):
            return not self._pole_zablokowane(pole(w), zaj)

        powod = None
        if banned(want):
            # cofnięcie na świeżo opuszczone pole: zamiast tego oś do celu albo krok dalej prosto; gdy nie ma
            # takiego kroku, pościg nie ma już sensu (cel za nami / droga zablokowana): wyjście, nie ping-pong
            osie = sorted(((abs(dx), (1 if dx > 0 else -1, 0)), (abs(dy), (0, 1 if dy > 0 else -1))), reverse=True)
            kand = [w for a, w in osie if a > 0]
            kand += [w for w in (v_krok, ost) if w is not None and w[0] * dx + w[1] * dy >= 0]   # nie od celu
            powod = "zawroc"
            for w in kand:
                if w != want and not banned(w) and dobry(w):
                    want, powod = w, "pingpong"
                    break
            if powod == "zawroc":
                return None, "zawroc"
        if ost is not None and want != ost:
            # histereza: stary kierunek wciąż zbliża do celu, a nowy nie jest wyraźnie lepszy
            zysk_ost = ost[0] * dx + ost[1] * dy
            nowa_odl = abs(dx) if want[0] else abs(dy)
            if zysk_ost >= 2 and not banned(ost) and dobry(ost) \
                    and (teraz - st.get("t_zm", float("-inf")) < POSCIG_HISTEREZA_S or nowa_odl < POSCIG_HISTEREZA_ODL):
                want, powod = ost, "histereza"
        return want, powod

    def _poscig_cel_przewidziany(self, tgt, xy, q):
        """Pozycja celu przewidziana o 1 krok, ale tylko gdy dwa ostatnie kroki celu były takie same (idzie prosto)
        i jest dalej niż POSCIG_PRZEWIDYWANIE_ODL od q; inaczej bieżąca."""
        if len(tgt) >= 3 and self.dystans(xy, q) > POSCIG_PRZEWIDYWANIE_ODL:
            (x0, y0), (x1, y1), (x2, y2) = tgt[-3][:2], tgt[-2][:2], tgt[-1][:2]
            v1, v2 = (x1 - x0, y1 - y0), (x2 - x1, y2 - y1)
            if v1 == v2 and v1 != (0, 0) and max(abs(v1[0]), abs(v1[1])) == 1:
                return (xy[0] + v2[0], xy[1] + v2[1])
        return xy

    def poscig_szybki(self, cel, poz, g=None):
        """Pościg za oddalającym się celem w szybkiej pętli: pozycję celu (i flagę ataku) czytamy jednym
        odczytem spod adresu jego obiektu (komenda "stwor"), strzałkę wysyłamy zaraz po zmianie pozycji
        gracza (bez stałych pauz). Wyjścia: cel martwy/zniknął/obok, HP gracza spadło, nowy gryzący
        potwór, obcy gracz, pauza/rozmowa mózgu, ściana (brak zmiany pozycji POSCIG_BRAK_ZMIANY s),
        okno POSCIG_OKNO s. W pętli nie ma telemetrii ani pokręteł. None = objazd."""
        t0 = self.zegar()
        koniec = t0 + POSCIG_OKNO
        if poz is None:
            poz = self.postac.pozycja()
        poz = tuple(poz)
        odl0 = self.dystans((cel["x"], cel["y"]), poz)
        hp_ref = g.get("proc") if g else None
        kroki, powod, wynik = 0, "okno", True
        wyslane0 = getattr(getattr(bot, "klawisz_x11", None), "WYSLANE", 0)
        podejscia = ponowione = ponow_brak = 0   # liczniki pomiaru: wywołania podejdz, powtórzenia bez nowego klawisza, ponowione po braku zmiany
        opoznienia = []                   # s od strzałki do zmiany pozycji (czas kroku widziany z pętli)
        decyzje = []                      # s od wykrycia zmiany pozycji do wysłania następnej strzałki
        przeglad, ost_klawisz = t0, float("-inf")
        odl = odl0
        s = None                          # ostatni odczyt celu (z RPC "poscig"; None = trzeba odczytać)
        t_wykr = None                     # kiedy pętla zobaczyła zmianę pozycji (do pomiaru decyzja -> klawisz)
        ponow_licznik = 0                 # ponowienia strzałki dla bieżącego kroku
        hold = self._poscig_trzymaj_mozliwe()
        trzymane_s = 0.0                  # s z wciśniętym klawiszem w tej pętli (tryb trzymania)
        zmiany_kier = naciski = 0         # zmiany kierunku bez puszczenia / naciśnięcia klawisza z postoju
        want, przelicz, t_ruch, ost_poz, ost_cel = None, True, t0, None, None
        v_krok = None                     # wektor kroku w toku (None = postać stoi)
        t_nacisk = None                   # kiedy nacisnęliśmy klawisz z postoju (po POSCIG_ANTYCYP_PO kolejkujemy zakręt)
        t_iter = t0
        stab = {"ost": None, "t_zm": float("-inf"), "hist": [(poz[0], poz[1], t0)]}   # filtr kierunku (_poscig_stabilny)
        tgt = []                          # ostatnie pozycje celu (przewidywanie tylko przy marszu prosto)
        filtry = {}                       # ile razy filtr zmienił kierunek (pingpong / histereza)
        wroty = []                        # czasy powrotów na poprzednie pole (A-B-A)
        blok = {}                         # pole (x, y) -> do kiedy zajęte (serwer cofnął na nie krok)
        cofniecia = 0                     # kroki cofnięte przez serwer (powrót w < POSCIG_COFNIECIE_S)
        slad = []                         # [x, y, t, cel_x, cel_y, trzymany] do telemetrii
        powod_d = None                    # ostatni powód z _poscig_decyzja (dla telemetrii puszczeń)
        puszczenia = {}                   # 11.10 telemetria: powód puszczenia klawisza -> ile razy (w tej pętli)
        t_pierwszy_krok = None            # 11.10 telemetria: s od startu pętli do pierwszej zmiany pozycji
        kliki0 = getattr(self, "kliki_ataku_poscig", 0)
        wd0 = getattr(getattr(bot, "klawisz_x11", None), "WATCHDOG_PUSZCZENIA", 0)

        def _puszcz(pow_):
            """Puść klawisze i zlicz powód (tylko gdy coś było trzymane)."""
            try:
                if self.postac.trzymany_kierunek() is not None:
                    puszczenia[pow_] = puszczenia.get(pow_, 0) + 1
            except Exception:
                pass
            self._poscig_puszcz()
        d2_id = self._decyzja_d2(cel, poz, g)          # 15.10: log decyzji D2 (tylko odczyt)
        d2_pole = {"decyzja_id": d2_id} if d2_id is not None else {}
        self._tele_poscig("poscig_start", cel=cel["nazwa"], odl=odl0, hp_celu=cel.get("hp"), **d2_pole)
        self.w_poscigu = True
        try:
            while True:
                bot.sprawdz_stop()
                teraz = self.zegar()
                if hold:
                    self.postac.puls()             # "pętla żyje" dla strażnika klawiszy + limit trzymania
                if teraz >= koniec:
                    # pętla biegnie (>= 3 kroki, cel nadal dalej niż obok): zamiast wracać przez pełny tick
                    # (martwy czas 0,6-0,9 s) przedłużamy okno po świeżym przeglądzie, do POSCIG_OKNO_DOBRY
                    if kroki >= 3 and odl >= 2 and teraz - t0 + POSCIG_OKNO_KONTYN <= (
                            max(POSCIG_OKNO_DOBRY, POSCIG_TRZYMAJ_OKNO_DOBRY) if hold else POSCIG_OKNO_DOBRY):
                        koniec = teraz + POSCIG_OKNO_KONTYN
                        przeglad = float("-inf")      # przegląd przy najbliższej strzałce
                    else:
                        powod = "okno"
                        break
                zewn = self._poscig_przerwanie()
                if zewn:
                    powod = zewn
                    break
                if s is None:
                    try:
                        p0, s = self._odczyt_poscig(cel)
                    except bot.Zatrzymano:
                        raise
                    except Exception:  # starszy rdzeń / atrapa bez komendy: zwykły krok i powrót do tick()
                        powod = "brak_komendy"
                        wynik = self.podejdz((cel["x"], cel["y"]), poz, pilne=True, natychmiast=True)
                        break
                    if s is not None:
                        poz = tuple(p0)
                if s is None or s["z"] != poz[2]:
                    powod = "cel_znikl"
                    break
                odl = self.dystans((s["x"], s["y"]), poz)
                if s["hp"] <= 0:
                    powod = "cel_martwy"
                    break
                if odl <= 1:
                    powod = "odl<=1"
                    break
                # flaga ataku prosto z "poscig"/"stwor" (świeża); bez niej ponow_atak zapyta cel_ataku
                cel = {**{k: v for k, v in cel.items() if k != "atakowany"},
                       "x": s["x"], "y": s["y"], "hp": s["hp"]}
                if isinstance(s.get("atakowany"), bool):
                    cel["atakowany"] = s["atakowany"]
                if 2 <= odl <= DOBICIE_ZASIEG_UCIEKAJACY:
                    self.ponow_atak(cel, poz)
                if hold:
                    # --- tryb trzymania: klawisz wciśnięty cały czas, pętla tylko steruje kierunkiem i wyjściami ---
                    teraz = self.zegar()
                    if teraz - przeglad >= POSCIG_TRZYMAJ_PRZEGLAD:
                        przeglad = teraz
                        powod_p, hp_ref = self._poscig_przeglad(cel, poz, hp_ref, puls=True)
                        if powod_p:
                            powod = powod_p
                            break
                        przelicz = True
                    trzymany = self.postac.trzymany_kierunek()
                    if t_nacisk is not None and teraz - t_nacisk >= POSCIG_ANTYCYP_PO:
                        t_nacisk = None
                        przelicz = True               # krok już ruszył: ponowna decyzja ustawi klawisz KOLEJNEGO kroku
                    brak_zmiany = max(POSCIG_BRAK_ZMIANY, POSCIG_BRAK_WSPOL * self._czas_kroku(poz))
                    if teraz - t_ruch > brak_zmiany:
                        # brak zmiany pozycji: puść, jedno ponowne naciśnięcie, potem wyjście
                        _puszcz("brak_zmiany")
                        if ponow_licznik < POSCIG_PONOW_BRAK:
                            ponow_licznik += 1
                            ponow_brak += 1
                            self.krok_prosto_ost = None
                            want, przelicz, t_ruch, trzymany, v_krok = None, True, teraz, None, None
                        else:
                            powod = "brak_ruchu"
                            break
                    sxy = (s["x"], s["y"])
                    if przelicz or poz != ost_poz or sxy != ost_cel:
                        zaj = {(m["x"], m["y"]) for m in (self.ostatnie_stwory or [])
                               if m["z"] == poz[2] and m.get("hp", 100) > 0 and m["id"] != cel["id"]
                               and not (m.get("gracz") and m.get("nazwa") == self.postac.nazwa) and not m.get("widmo")}
                        zaj.discard(tuple(poz[:2]))
                        zaj |= {pl for pl, do in blok.items() if do > self.zegar()}   # pola, z których serwer cofnął krok
                        if POSCIG_VKROK_SCIANA and v_krok is not None and self._pole_zablokowane(
                                (poz[0] + v_krok[0], poz[1] + v_krok[1], poz[2]), zaj):
                            v_krok = None    # trzymany klawisz w ścianę/zajęte: krok nie trwa (nie "zawracanie")
                        q = poz if v_krok is None else (poz[0] + v_krok[0], poz[1] + v_krok[1], poz[2])
                        if not tgt or tgt[-1] != sxy:
                            tgt.append(sxy)
                            del tgt[:-4]
                        xyp = self._poscig_cel_przewidziany(tgt, sxy, q)
                        s_dec = s if xyp == sxy else {**s, "x": xyp[0], "y": xyp[1]}
                        want, objazd, powod_d = self._poscig_decyzja(s_dec, poz, v_krok, zaj)
                        if objazd:
                            powod, wynik = "objazd", None
                            break
                        if want is not None:
                            want, filtr = self._poscig_stabilny(want, q, sxy, v_krok, zaj, stab, self.zegar())
                            if filtr:
                                filtry[filtr] = filtry.get(filtr, 0) + 1
                            if filtr == "zawroc":
                                powod = "zawracanie"
                                break
                        if POSCIG_DZIURA_KROK and want is not None and v_krok is not None and want != v_krok \
                                and self._pole_upadku((poz[0] + want[0], poz[1] + want[1], poz[2])):
                            # 22.10 (dawajkesh 10:49:29, (33068,31716,z9) -> nauczona dziura (33067,31716,z9)): zakręt kolejkowany
                            # sprawdzaliśmy tylko względem pola Q (po kroku w toku), a klient potrafi ruszyć dopiero po zmianie
                            # klawisza (krok w toku jeszcze się nie zaczął) i wtedy idzie z POZ w nowym kierunku. Gdy z POZ ten
                            # kierunek wchodzi w dziurę / zmianę piętra: nie zakręcamy "na zapas", decyzja od stojącej
                            # postaci (v_krok None: sprawdzenia liczone z POZ)
                            filtry["dziura_krok"] = filtry.get("dziura_krok", 0) + 1
                            v_krok = None
                            want, objazd, powod_d = self._poscig_decyzja(s_dec, poz, None, zaj)
                            if objazd:
                                powod, wynik = "objazd", None
                                break
                            if want is not None:
                                want, filtr = self._poscig_stabilny(want, poz, sxy, None, zaj, stab, self.zegar())
                                if filtr:
                                    filtry[filtr] = filtry.get(filtr, 0) + 1
                                if filtr == "zawroc":
                                    powod = "zawracanie"
                                    break
                        if want != stab["ost"] and want is not None:
                            stab["t_zm"] = self.zegar()
                        stab["ost"] = want
                        przelicz, ost_poz, ost_cel = False, tuple(poz), sxy
                        if t_wykr is not None:
                            decyzje.append(self.zegar() - t_wykr)
                            t_wykr = None
                    if powod_d == "ostatni_dociska" and want is not None:
                        filtry["ostatni_dociska"] = filtry.get("ostatni_dociska", 0) + 1   # telemetria (12.10)
                    if want is None:
                        if trzymany is not None:
                            _puszcz(powod_d or "brak_kierunku")
                            if POSCIG_OSTATNI_DOCISKAJ:
                                # 12.10: klawisz puszczony = żaden krok nie trwa. Dawne v_krok wymuszało kolejne
                                # "ostatni" aż do POSCIG_BRAK_WSPOL * czas kroku (1,3 s); teraz decyzja z poz od razu
                                v_krok, przelicz = None, True
                    elif trzymany != want:
                        if trzymany is not None:
                            zmiany_kier += 1
                        else:
                            naciski += 1
                            t_ruch = t_nacisk = self.zegar()   # ruszamy z postoju: liczymy brak zmiany pozycji od teraz
                        self.postac.trzymaj_kierunek(*want)
                        if v_krok is None:
                            v_krok = want                  # krok rusza od razu (kolejne klawisze to kolejka)
                    ost_klawisz = self.zegar()
                    # odczyt pozycji i celu (jedno RPC) po krótkiej pauzie; krok liczymy po ZMIANIE pozycji
                    self.spij(random.uniform(*POSCIG_POLL))
                    bot.sprawdz_stop()
                    try:
                        p, s_nowy = self._odczyt_poscig(cel)
                    except bot.Zatrzymano:
                        raise
                    except Exception:
                        _puszcz("brak_komendy")
                        powod = "brak_komendy"
                        wynik = self.podejdz((s["x"], s["y"]), poz, pilne=True, natychmiast=True)
                        break
                    s = s_nowy                   # None: cel zniknął, góra pętli to rozpozna
                    teraz = self.zegar()
                    if self.postac.trzymany_kierunek() is not None:
                        trzymane_s += teraz - t_iter
                    t_iter = teraz
                    p = tuple(p)
                    if p != poz:
                        kroki += 1
                        if t_pierwszy_krok is None:
                            t_pierwszy_krok = teraz - t0
                        t_wykr = teraz
                        opoznienia.append(teraz - t_ruch)    # w trybie trzymania: czas jednego kroku widziany z pętli
                        ponow_licznik = 0
                        t_ruch = teraz
                        poz = p
                        przelicz = True
                        v_krok = self.postac.trzymany_kierunek()   # nowy krok rusza z tym, co trzymamy w chwili dojścia
                        self.zapamietaj_pole(poz)
                        self.ruch_poz, self.ruch_czas = poz, teraz
                        h = stab["hist"]
                        cofniete = len(h) >= 2 and h[-2][:2] == poz[:2] and teraz - h[-1][2] < POSCIG_COFNIECIE_S
                        if cofniete:
                            # powrót szybszy niż jakikolwiek krok: serwer odrzucił krok (pole zajęte przez stwora)
                            cofniecia += 1
                            blok[h[-1][:2]] = teraz + POSCIG_BLOK_S
                        elif len(h) >= 2 and h[-2][:2] == poz[:2]:
                            wroty.append(teraz)                       # wróciliśmy na pole sprzed kroku: A-B-A
                        if s is not None:
                            slad.append([poz[0], poz[1], round(teraz - t0, 2), s["x"], s["y"],
                                         list(v_krok) if v_krok else None])
                            del slad[:-16]
                        h.append((poz[0], poz[1], teraz))
                        del h[:-24]
                        wroty[:] = [w for w in wroty if teraz - w <= POSCIG_OSCYLACJA_S]
                        stare = [e for e in h if teraz - e[2] <= POSCIG_BEZ_POSTEPU_S]
                        if cofniecia >= 2:
                            powod = "oscylacja"
                            break
                        if len(wroty) >= POSCIG_OSCYLACJA_N or (
                                len(stare) > POSCIG_BEZ_POSTEPU_KROKI
                                and max(abs(poz[0] - stare[0][0]), abs(poz[1] - stare[0][1])) <= 1):
                            powod = "oscylacja"
                            break
                    continue
                reszta = POSCIG_KROK_MIN - (self.zegar() - ost_klawisz)
                if reszta > 0:
                    self.spij(reszta)
                wys_przed = getattr(getattr(bot, "klawisz_x11", None), "WYSLANE", 0)
                if self.podejdz((s["x"], s["y"]), poz, pilne=True, natychmiast=True, poscig=True) is None:
                    powod, wynik = "objazd", None
                    break
                podejscia += 1
                wys_po = getattr(getattr(bot, "klawisz_x11", None), "WYSLANE", 0)
                if wys_po == wys_przed:
                    ponowione += 1        # podejdz uznał poprzednią strzałkę za nadal w toku: bez nowego klawisza
                if (wys_po != wys_przed or wys_po == 0) and t_wykr is not None:   # 0 = atrapa bez licznika
                    decyzje.append(self.zegar() - t_wykr)
                    t_wykr = None
                ost_klawisz = self.zegar()
                # przegląd (HP gracza, otoczenie) w czasie trwania kroku: nie opóźnia strzałki
                if ost_klawisz - przeglad >= POSCIG_PRZEGLAD:
                    przeglad = ost_klawisz
                    powod_p, hp_ref = self._poscig_przeglad(cel, poz, hp_ref)
                    if powod_p:
                        powod = powod_p
                        break
                # czekamy na ZMIANĘ pozycji (nie stałą pauzę); brak zmiany = ściana albo blokada
                nowa = None
                blad = False
                brak_zmiany = max(POSCIG_BRAK_ZMIANY, POSCIG_BRAK_WSPOL * self._czas_kroku(poz))
                while True:
                    self.spij(random.uniform(*POSCIG_POLL))
                    bot.sprawdz_stop()
                    try:
                        p, s_nowy = self._odczyt_poscig(cel)
                    except bot.Zatrzymano:
                        raise
                    except Exception:
                        blad = True
                        break
                    p = tuple(p)
                    if s_nowy is not None:
                        s = s_nowy          # odczyt celu jest świeższy niż ten sprzed strzałki
                    if p != poz:
                        nowa = p
                        break
                    if self.zegar() - ost_klawisz > brak_zmiany:
                        break
                if blad:
                    powod = "brak_komendy"
                    wynik = self.podejdz((s["x"], s["y"]), poz, pilne=True, natychmiast=True)
                    break
                if nowa is None:
                    if ponow_licznik < POSCIG_PONOW_BRAK:
                        # strzałka mogła zginąć (klient zajęty poprzednim krokiem): jedna próba, zanim uznamy ścianę
                        ponow_licznik += 1
                        ponow_brak += 1
                        self.krok_prosto_ost = None
                        continue
                    powod = "brak_ruchu"
                    break
                ponow_licznik = 0
                kroki += 1
                t_wykr = self.zegar()
                if t_pierwszy_krok is None:
                    t_pierwszy_krok = t_wykr - t0
                opoznienia.append(t_wykr - ost_klawisz)
                poz = nowa
                self.zapamietaj_pole(poz)
                self.ruch_poz, self.ruch_czas = poz, t_wykr
                if random.random() < POSCIG_ZAWAHANIE_P:
                    self.pauza(*POSCIG_ZAWAHANIE)
                else:
                    self.pauza(*POSCIG_PO_KROKU)
        finally:
            if hold:
                _puszcz("wyjscie")            # KAŻDE wyjście (też wyjątek, STOP, SIGTERM): klawisze puszczone
            self.w_poscigu = False
            teraz = self.zegar()
            so = self.skos_ost
            if powod == "brak_ruchu" and so is not None and self.dystans(so[1], poz) <= 1 \
                    and (so[1][0] != poz[0] and so[1][1] != poz[1]):
                self.skos_zle[so] = teraz + SKOS_ZLY_S      # skos nie przesunął postaci: nie ponawiamy go przez chwilę
            self.skos_zle = {k: v for k, v in self.skos_zle.items() if v > teraz}
            if powod == "zawracanie" and len(stab["hist"]) < POSCIG_ZAWR_MIN_HIST:
                # zawrócenie na krótkiej historii (<POSCIG_ZAWR_MIN_HIST pól): jedna zmiana strony celu, nie oscylacja;
                # kara 3 s + 5 s stuknięć tylko gubiła uciekającego (seria 15:06:30-15:06:52): bez przerwy i bez stuku
                log(f"Pościg: zawracanie na krótkiej historii ({len(stab['hist'])} pól), bez kary, wracamy do ticka.")
            elif powod in ("oscylacja", "zawracanie"):
                self.poscig_przerwa_do = max(self.poscig_przerwa_do, teraz + POSCIG_PRZERWA_PO_ZAWROCIE)
                self.poscig_stuk_do = teraz + POSCIG_STUK_PO_OSCYLACJI   # potem chwilowo stuknięcia zamiast trzymania
                log(f"Pościg: {powod} ({len(stab['hist'])} pól w historii, cofnięć serwera {cofniecia}), "
                    f"{POSCIG_PRZERWA_PO_ZAWROCIE:.0f} s bez pościgu, {POSCIG_STUK_PO_OSCYLACJI:.0f} s stuknięciami.")
            seria = self.poscig_seria
            if seria is None:
                self.poscig_seria = [t0, odl0, teraz]
            else:
                seria[2] = teraz
            czas = teraz - t0
            wyslane = getattr(getattr(bot, "klawisz_x11", None), "WYSLANE", 0) - wyslane0
            if hold:
                wyslane, ponowione = naciski + zmiany_kier, 0   # naciśnięcia klawisza (z postoju i zmiany kierunku)
                odrzucone = 0                                   # klawisz trzymany: nic nie jest "odrzucane"
            else:
                if not wyslane:
                    wyslane, ponowione = podejscia, 0   # atrapa/inny kanał klawiszy: liczymy wywołania podejdz
                odrzucone = max(0, wyslane - kroki)   # klawisze bez zmiany pozycji w oknie POSCIG_BRAK_ZMIANY
            lat = sorted(opoznienia)
            dec = sorted(decyzje)
            puszczenia_t = dict(puszczenia)
            wd = getattr(getattr(bot, "klawisz_x11", None), "WATCHDOG_PUSZCZENIA", 0) - wd0
            if wd > 0:
                puszczenia_t["strazni"] = wd
            try:
                self._cel_po_poscigu(cel)
            except Exception as e:
                log(f"debug: pościg: zapis pozycji celu: {e!r}")
            self._tele_poscig("poscig_koniec", cel=cel["nazwa"], kroki=kroki, czas=round(czas, 2),
                              powod=powod, odl_start=odl0, odl_koniec=odl,
                              kroki_na_s=round(kroki / czas, 2) if czas > 0 else 0.0,
                              wyslane=wyslane, zmiany_pozycji=kroki, ponowione=ponowione, odrzucone=odrzucone,
                              ponow_brak=ponow_brak, tryb="trzymaj" if hold else "stuk",
                              trzymane_s=round(trzymane_s, 2), zmiany_kierunku=zmiany_kier,
                              dec_med=round(dec[len(dec) // 2], 3) if dec else None,
                              dec_max=round(dec[-1], 3) if dec else None,
                              lat_med=round(lat[len(lat) // 2], 3) if lat else None,
                              lat_max=round(lat[-1], 3) if lat else None,
                              filtry=filtry or None,
                              cofniecia=cofniecia or None,
                              sciezka=slad if hold else None,
                              # 11.10: powód puszczenia klawisza (licznik per powód; "strazni" = watchdog klawisz_x11),
                              # kliki ataku (ponow_atak) w pętli, czas do pierwszego kroku
                              puszczenia=puszczenia_t or None, **d2_pole,
                              kliki_ataku=getattr(self, "kliki_ataku_poscig", 0) - kliki0,
                              t_pierwszy_krok=round(t_pierwszy_krok, 2) if t_pierwszy_krok is not None else None)
        return None if wynik is None else True

    def walcz(self, cel, g, poz):
        if self.marsz is not None:
            self._marsz_stop(poz, "walka")        # MARSZ_KLIK: klient idzie sam, a Escape zdejmuje atak, więc PRZED pierwszym atakiem
        teraz = self.zegar()
        odl = self.cel["odl"]
        self.walka_odl_tick = odl
        self.ustaw_stan("WALKA", f"{cel['nazwa']} odl {odl} HP {cel['hp']}%")
        if self._straznik_celu(cel, odl, poz, teraz):
            return True
        self.ucz_uciekania(cel, odl)
        prog = self.prog_uciekania(cel["nazwa"])
        ucieka = cel["hp"] <= prog + 10 or cel["hp"] <= UCIEKAJACY_HP
        if self.lww is not None and odl > 1 and self._lww_okno_otwarte() and odl <= 4 \
                and self._loot_w_walce(cel, g, poz, teraz):
            self.pauza(0.03, 0.1)          # okno zwłok otwarte: dokańczamy krok zamiast przerywać "cel_daleko"
            return True
        if self.lww is not None and odl > 1:
            # cel odszedł (uciekający: każda chwila się liczy): atak ma pierwszeństwo, okna zwłok nie zamykamy kliknięciem
            # (pilne=True; Ctrl+klik po walce i tak je obsłuży), żeby nic nie opóźniało pierwszego kroku pościgu
            self._lww_przerwij("cel_daleko", teraz, pilne=True)
        if teraz - self.cel_start > LIMIT_WALKI:
            log(f"Cel {cel['nazwa']} trwa za długo, ignoruję na {IGNOROWANIE} s.")
            self._ignoruj(cel["id"], teraz + IGNOROWANIE, "limit_walki")
            self.cel = None
            return True
        if cel["hp"] < self.cel_hp:
            self.klik_ramka_false.pop(cel["id"], None)
            self.mapa_ramka_false_seria = 0           # atak działa: prostokąt mapy trafia w pola
            self.cel_hp = cel["hp"]
            self.cel_spadek = teraz
            self.hp_spadek_czas = teraz
        if self.cel_spadek == float("-inf") and teraz < self.reakcja_do and not (ucieka and odl > 1):
            # "zauważanie" potwora, jak u człowieka; NIE dla uciekającego, który się oddala (każda chwila to pole dystansu)
            self.pauza(0.05, 0.12)
            return True
        if odl <= 1 and self.zatrzymaj_klik(poz):
            self.cel_spadek = float("-inf")   # Escape zdjął też atak: ponów go od razu
        if ATAK_INNY_CEL and odl <= 1 and self.cel_spadek != float("-inf") \
                and teraz - self.atak_inny_ost.get(cel["id"], float("-inf")) >= ATAK_INNY_CEL_CO_S:
            # gra celuje w kogoś innego niż cel bota (np. stary cel po zgonie sąsiada): nie czekamy PONOWIENIE_ATAKU
            gracz_ = {"x": poz[0], "y": poz[1]}
            try:
                flaga_ = self.czy_atakowany(cel, gracz_)
            except bot.Zatrzymano:
                raise
            except Exception:
                flaga_ = None
            if flaga_ is False:
                w_grze_, odczyt_ = self._cel_w_grze()
                if odczyt_ and w_grze_ != cel["id"]:
                    self.spij(random.uniform(0.1, 0.3))
                    teraz = self.zegar()
                    self.atak_inny_ost[cel["id"]] = teraz
                    self._log_klik_ataku(cel, odl, flaga_, "inny_cel", w_grze_)
                    self.atak(cel, gracz_)
                    self.atak_czas = teraz
                    self.cel_spadek = teraz
                    self.pauza(0.05, 0.15)
        if (odl <= 1 or (self.cel_spadek == float("-inf") and not ATAK_TYLKO_PRZY_CELU)) \
                and teraz - self.cel_spadek >= random.uniform(*PONOWIENIE_ATAKU):
            gracz = {"x": poz[0], "y": poz[1]}
            # potwór obok, a HP nie spada od dawna: atak na pewno nie trwa (np. po ciemku
            # ramki nie widać, a pierwszy klik chybił) - klikamy niezależnie od ramki.
            # Dotyczy tylko zrzutu (None); odczyt z pamięci zwraca zawsze True/False.
            zaciety = odl <= 1 and teraz - self.hp_spadek_czas > ZACIECIE_ATAKU \
                and teraz - self.atak_czas > ZACIECIE_ATAKU
            pierwszy = self.cel_spadek == float("-inf")
            ramka = None if pierwszy else self.czy_atakowany(cel, gracz)
            if ramka is False:
                self._mapa_seria_ramka_false(teraz)
            elif ramka is True:
                self.mapa_ramka_false_seria = 0
            if ramka is not False:
                self.klik_ramka_false.pop(cel["id"], None)
            elif ATAK_LIMIT_KLIKOW:
                n = self.klik_ramka_false.get(cel["id"], 0) + 1
                self.klik_ramka_false[cel["id"]] = n
                if n > ATAK_LIMIT_KLIKOW:
                    # klik nie działa (zła pozycja gracza, stary cel w grze, "Sorry, not possible."): nie klikamy w nieskończoność
                    log(f"[ATAK] {n - 1} klików bez efektu w {cel['nazwa']} id{self._koncowka_id(cel['id'])}, "
                        f"Escape i ignoruję cel na {ATAK_LIMIT_IGNOROWANIE} s.")
                    self._ratunek_zdarzenie("klik_bez_efektu", None, n=n - 1, cel=cel.get("nazwa"))
                    self._zwiecha_zdarzenie("klik_bez_efektu", poz, teraz)
                    self.klik_ramka_false.pop(cel["id"], None)
                    klawisz = getattr(self.postac, "klawisz", None)
                    if klawisz is not None:
                        try:
                            klawisz("Escape")
                        except bot.Zatrzymano:
                            raise
                        except Exception as e:
                            log(f"Escape nie poszedł: {e}")
                    self._ignoruj(cel["id"], teraz + ATAK_LIMIT_IGNOROWANIE, "atak_klik")
                    self.cel = None
                    return True
            # ramka False: atak nie trwa; None (zrzut po ciemku): klikamy tylko przy zacięciu;
            # True: atak trwa, ponowny klik by go wyłączył
            if pierwszy or ramka is False or (ramka is None and zaciety):
                self._log_klik_ataku(cel, odl, ramka, "pierwszy" if pierwszy else ("ramka_false" if ramka is False else "zacięty"))
                self.atak(cel, gracz)
                self.atak_czas = teraz
            self.cel_spadek = teraz
            self.pauza(0.05, 0.15)
        if odl > 1:
            if self.czekanie_do is None:
                self.czekanie_do = teraz + random.uniform(*CZEKANIE_NA_CEL)
                self.czekanie_odl = odl
            if odl < self.czekanie_odl:
                # potwór idzie w naszą stronę: czekaj dalej, licz od nowa
                self.czekanie_odl = odl
                self.czekanie_do = teraz + random.uniform(*CZEKANIE_NA_CEL)
            if self.czekaj and teraz < self.czekanie_do and cel["hp"] >= HP_UCIEKAJACEGO:
                self.ustaw_stan("WALKA", f"{cel['nazwa']} odl {odl}, czekam aż podejdzie")
                self.pauza(0.3, 0.6)
            else:
                # najbliższe znane pole przy potworze po drodze ze znanych pól (w krętym korytarzu
                # pole "od naszej strony" po prostej bywa ścianą); bez drogi - pole od naszej strony.
                # Uciekającego gonimy w trybie pilnym: nowe pole = klik od razu.
                self.ostatnia_droga_dl = None
                # szybka pętla pościgu: każdy cel dalej niż obok (także zdrowy, który się oddala)
                szybki = self.klik is not None and bool(cel.get("adres")) \
                    and self.poscig_wejscie(cel, g, poz, odl)
                if not szybki and ucieka and 2 <= odl <= DOBICIE_ZASIEG_UCIEKAJACY:
                    self.ponow_atak(cel, poz)     # Alt+klik na uciekającym zamiast samych strzałek
                if szybki:
                    wynik = self.poscig_szybki(cel, poz, g)
                else:
                    wynik = self.podejdz((cel["x"], cel["y"]), poz, pilne=ucieka, natychmiast=ucieka)
                droga = self.ostatnia_droga_dl
                # czekamy tylko, gdy cel naprawdę blisko po DRODZE (nie samej linii prostej);
                # bez wiedzy o drodze (stara mapa) - dawna zasada: blisko w linii prostej
                if droga is None:
                    czekaj_blisko = odl <= CZEKAJ_BLISKO
                else:
                    czekaj_blisko = droga <= CZEKAJ_DROGA and odl <= CZEKAJ_BLISKO
                if ucieka:
                    czekaj_blisko = False   # uciekającego się goni, nie czeka
                if wynik is None and czekaj_blisko:
                    # blisko i bez drogi: nie odpuszczamy (ping-pong), atak trwa, szczur sam podejdzie
                    self.ustaw_stan("WALKA", f"{cel['nazwa']} odl {odl}, brak drogi, czekam aż podejdzie")
                    if not self.cel.get("czeka_log"):
                        self.cel["czeka_log"] = True
                        log(f"Czekam na {cel['nazwa']} (odl {odl}): {self.ostatni_objazd}, atak trwa.")
                    self.pauza(0.3, 0.6)
                elif wynik is None:
                    if self._blokujacy_wyjscia(cel, None, poz, teraz) is not None:
                        self.cel = None
                        return True
                    self._log_odpuszczenia(cel, f"Odpuszczam {cel['nazwa']}: za ścianą (droga naokoło: {self.ostatni_objazd}).", teraz)
                    self._ignoruj(cel["id"], teraz + self.objazd_ignorowanie(cel, odl), "sciana")
                    if droga is not None and droga > NIEOSIAGALNY_DROGA and not self.umierajacy(cel, odl):
                        # twarde ignorowanie: nie kasuje go podejście na IGNOROWANIE_BLISKO
                        self.nieosiagalne[cel["id"]] = odl
                    self.cel = None
        else:
            self.czekanie_do = None
            if self._loot_w_walce(cel, g, poz, teraz):
                self.pauza(0.03, 0.1)    # krok lootu zajął czas: zaraz kontrola ataku w następnym obiegu
            elif cel["hp"] <= prog + CZUJNOSC:
                self.pauza(0.03, 0.08)   # zaraz ucieknie: sprawdzaj bardzo często
            else:
                self.pauza(0.1, 0.3)
        return True

    def zapamietaj_ruch_celu(self, cel):
        """Ostatni krok celu (do zgadywania pola zwłok, gdy ginie w ruchu)."""
        teraz = self.zegar()
        nowa = (cel["x"], cel["y"], cel["z"])
        stara = self.cel.get("poz") if self.cel else None
        if stara and stara != nowa and stara[2] == nowa[2]:
            self.cel["krok"] = (nowa[0] - stara[0], nowa[1] - stara[1])
            self.cel["krok_czas"] = teraz
        if self.cel is not None:
            slad = self.cel.setdefault("slad", [])     # ostatnie ~4 pola celu (wektor ucieczki)
            if not slad or slad[-1] != nowa[:2]:
                slad.append(nowa[:2])
                del slad[:-4]

    def pola_zwlok(self, c):
        """Kandydaci na pole zwłok: przy ruchu tuż przed śmiercią najpierw pole, na które
        cel wchodził (nasz odczyt pozycji jest o chwilę spóźniony), potem ostatnio widziane."""
        poz = c.get("poz")
        if not poz:
            return []
        krok, czas = c.get("krok"), c.get("krok_czas", float("-inf"))
        if LOOT_DYNAMICZNY:
            # 13.10: zwłoki leżą tam, gdzie cel był OSTATNIO WIDZIANY (log 12:57:32: ekstrapolacja kroku dawała pole obok
            # za każdym razem). Potem inne pola z historii celu przy tym polu (cel skacze między polami; odczyt co ~1 s
            # bywa o jeden skok spóźniony), na końcu dawna ekstrapolacja.
            wynik = [tuple(poz)]
            for q in reversed(c.get("slad") or []):
                q3 = (q[0], q[1], poz[2])
                if q3 not in wynik and max(abs(q[0] - poz[0]), abs(q[1] - poz[1])) <= 1:
                    wynik.append(q3)
            if krok and self.zegar() - czas < RUCH_PRZED_SMIERCIA and max(abs(krok[0]), abs(krok[1])) == 1:
                q3 = (poz[0] + krok[0], poz[1] + krok[1], poz[2])
                if q3 not in wynik:
                    wynik.append(q3)
            return wynik[:4]
        if krok and self.zegar() - czas < RUCH_PRZED_SMIERCIA and max(abs(krok[0]), abs(krok[1])) == 1:
            return [(poz[0] + krok[0], poz[1] + krok[1], poz[2]), poz]
        return [poz]

    def zgon_celu(self, g, poz, pewny=False):
        """pewny=True: cel jest na liście z HP 0. Inaczej zniknął z listy i zgon zgadujemy po odległości."""
        c, self.cel = self.cel, None
        self.aktywnosc_ts = self.zegar()
        self.nieudane = 0
        if self.lww is not None:
            self._lww_przerwij("zgon_celu", self.zegar(), pilne=True)
        # stwór na ekranie nie może wyjść z zasięgu klienta: zniknięcie na ekranie = śmierć.
        # Zniknięcie poza ekranem (pogoń) traktujemy jako ucieczkę.
        if not pewny:
            ostatnia = c.get("poz")
            na_ekranie = ostatnia is not None and ostatnia[2] == poz[2] \
                and abs(ostatnia[0] - poz[0]) <= ZASIEG_X and abs(ostatnia[1] - poz[1]) <= ZASIEG_Y
            if self._pamiec_start(c, g, poz, na_ekranie):
                return True
            if not na_ekranie:
                log(f"Cel {c['nazwa']} zniknął poza ekranem (odl {c.get('odl')}), pomijam loot.")
                return True
        log(f"Cel {c['nazwa']} zabity na {c.get('poz')}.")
        self.patrol_zabicia += 1
        self._obecnosc_zabicie(c)
        zyje = self.zywy_w_poblizu([x for x in self.ostatnie_stwory if x["id"] != c["id"]], poz) \
            if self.loot and c.get("poz") else None
        szybki = False
        styk = []                    # 23.10: przylegające żywe moby przy lootcie zaraz po zabiciu (LOOT_SZYBKI_STYKAJACE)
        if LOOT_DYNAMICZNY and self.loot and c.get("poz"):
            pola = self.pola_zwlok(c)
            if pola and pola[0][2] != poz[2]:
                # zwłoki z innego piętra: bez Ctrl+klik, odkładamy (zbierzemy po powrocie na to piętro, do końca TTL)
                self.odloz_zwloki(pola[0], nowe=True)
                log(f"Zwłoki {pola[0][:2]} na innym piętrze (z{pola[0][2]}, my z{poz[2]}): odkładam, bez próby lootu.")
                return True
            if zyje and pola and self.dystans(pola[0], poz) <= LOOT_SZYBKI_ODL:
                # zwłoki pod nogami / obok: zbieramy od razu, jeśli nic nie styka (żywy w odl >= 2 jeszcze nie bije),
                # HP wysoko, brak ucieczki i groźnego gracza (próba trwa 1-2 s)
                try:
                    swieze = [x for x in self.ostatnie_stwory if x.get("id") != c.get("id")]
                    szybki = (not (self.ucieczka or self.ostrozny)
                              and g.get("proc", 100.0) > self.prog_aktualny + LOOT_W_WALCE_HP_MARGINES
                              and not self._grozni_w_zasiegu(swieze, poz)
                              and not self._ogien_na(pola[0]))
                    if szybki:
                        styk = self._zywe_w_promieniu(swieze, poz, 1)
                        if styk:
                            # 23.10: mob przylega - loot od razu tylko do LOOT_SZYBKI_STYKAJACE mobów i tylko zwłoki w odl 1 (bez kroków)
                            szybki = len(styk) <= max(0, min(2, int(LOOT_SZYBKI_STYKAJACE))) \
                                and self.dystans(pola[0], poz) == 1
                except Exception:
                    szybki = False
                    styk = []
                if szybki and styk:
                    log(f"Loot szybki: zwłoki {pola[0][:2]} obok, {len(styk)} przylegających ({styk[0]['nazwa']}), "
                        f"loot od razu przed walką (limit {LOOT_SZYBKI_STYK_MAX_S:.0f} s, przerwanie przy spadku HP).")
                elif szybki:
                    log(f"Loot szybki: zwłoki {pola[0][:2]} obok, {zyje['nazwa']} w odl "
                        f"{self.dystans((zyje['x'], zyje['y']), poz)}.")
        if zyje and not szybki:
            # najpierw dobijamy pobliskie, zwłoki zbieramy po walce
            pola_l = self.pola_zwlok(c)
            if LOOT_DYNAMICZNY:
                # kandydaci przy nas (ostatnio widziane pole, skoki celu, ekstrapolacja): każdy dostaje wpis, a po udanym
                # lootcie jednego reszta grupy znika (zw_grupa); loot w walce próbuje je po kolei
                wybrane = [q for q in pola_l[:3] if self.dystans(q, poz) <= 1] or pola_l[:1]
                for pole in wybrane:
                    self.odloz_zwloki(pole, nowe=True)
                    self.zw_grupa[tuple(pole)] = tuple(wybrane)
            else:
                for pole in pola_l[:1]:
                    self.odloz_zwloki(pole, nowe=True)
            log(f"Loot odłożony: {zyje['nazwa']} {self.dystans((zyje['x'], zyje['y']), poz)} pól od nas, najpierw walka.")
        elif self.loot and c.get("poz"):
            self.ustaw_stan("LOOT", str(c["poz"]))
            try:
                kandydaci = self.pola_zwlok(c)
                if styk:
                    # przy przylegającym mobie tylko pola w odl 1 od nas (bez kroków); reszta zgadywanych pól odpada
                    kandydaci = [k for k in kandydaci if self.dystans(k, poz) == 1] or kandydaci[:1]
                    self.loot_styk = {"dop": max(0, min(2, int(LOOT_SZYBKI_STYKAJACE))), "t0": self.zegar(),
                                      "hp": [(self.zegar(), g.get("proc", 100.0))]}
                self.loot_probowane_czysc()
                for i, pole in enumerate(kandydaci):
                    # pozostałe pola tego zabicia loot próbuje zaraz po zgadniętym (np. pod nogami)
                    self.loot_alternatywy = [tuple(k[:2]) for j, k in enumerate(kandydaci) if j != i]
                    self.loot_seria = i > 0
                    wynik = self.zbierz_loot(pole)
                    if wynik != "brak_okna" or i == len(kandydaci) - 1:
                        if wynik == "przerwany" and i + 1 < len(kandydaci):
                            self.odloz_zwloki(kandydaci[i + 1], nowe=True)
                        break
                    log(f"Zwłok nie ma na {pole}, próbuję {kandydaci[i + 1]} (cel szedł w chwili śmierci).")
            except bot.Zatrzymano:
                raise
            except Exception as e:  # loot nie może wywrócić bota
                log(f"Loot się nie udał: {e!r}")
            finally:
                self.loot_alternatywy = []
                self.loot_seria = False
                self.loot_styk = None
        return True

    # --- pościg na pamięć: ranny cel zniknął z widoku żywy ---

    def _pamiec_start(self, c, g, poz, na_ekranie):
        """Cel (ranny albo trafiony) zniknął z listy żywy: zapamiętujemy ostatnią pozycję, wektor ucieczki
        i HP, po czym przez POSCIG_PAMIEC_S s idziemy za nim (tick -> _pamiec_tick). True = pościg ruszył."""
        try:
            if not POSCIG_PAMIEC or self.pamiec is not None:
                return False
            ost, hp, hp0 = c.get("poz"), c.get("hp"), c.get("hp0")
            if ost is None or hp is None or ost[2] != poz[2]:
                return False
            if not (hp <= PAMIEC_HP or (hp0 is not None and hp < hp0)):
                return False
            odl = self.dystans(ost, poz)
            if odl > POSCIG_PAMIEC_MAKS_ODL:
                # 11.10: cel zniknął za daleko (odl 8-10 kończyło się limitem 7 s: ucieka 0,85 pola/s, my 1,26): nie ścigamy
                log(f"Cel {c['nazwa']} zniknął {odl} pól od nas (> {POSCIG_PAMIEC_MAKS_ODL}): bez pościgu na pamięć.")
                return False
            if na_ekranie and odl < PAMIEC_ODL_MIN:
                return False                       # zniknął tuż obok nas: zabity
            if self.exp_przed is not None and self.exp_teraz is not None and self.exp_teraz > self.exp_przed:
                return False                       # exp wzrósł: zabity
            if self.ucieczka or self.ostrozny or self.w_lootcie or self._poscig_przerwanie():
                return False
            if g and g.get("proc") is not None and g["proc"] <= self.prog_aktualny + PAMIEC_HP_MARGINES:
                return False
            teraz = self.zegar()
            if teraz - self.hp_gracza_spadek < GRYZIE_OKNO:
                return False                       # coś nas gryzie
            lista = self.ostatnie_stwory or []
            if any(s["id"] != c["id"] and self.dystans((s["x"], s["y"]), poz) <= 1
                   for s in self.kandydaci(lista, poz)):
                return False                       # inne moby gryzą obok: bijemy je
            if self._grozni_w_zasiegu(lista, poz):
                return False
            v = self._wektor_ucieczki(c, poz)
            cel_xy = self._pamiec_koniec_korytarza(ost, v, int(POSCIG_PAMIEC_POL))
            self.pamiec = {"cel": {"id": c["id"], "nazwa": c["nazwa"], "hp": hp, "hp0": hp0, "poz": tuple(ost)},
                           "t0": teraz, "do": teraz + POSCIG_PAMIEC_S, "cel_xy": cel_xy, "kroki": 0,
                           "poz": tuple(poz), "ruch": teraz, "exp0": self.exp_teraz}
            log(f"Cel {c['nazwa']} zniknął z widoku żywy ({ost[0]},{ost[1]}) HP {hp}%, wektor {v[0]:+d},{v[1]:+d}: "
                f"ścigam na pamięć do ({cel_xy[0]},{cel_xy[1]}), do {POSCIG_PAMIEC_S:.0f} s.")
            self._tele_poscig("poscig_pamiec_start", cel=c["nazwa"], id=c["id"], poz=[ost[0], ost[1]], hp=hp,
                              wektor=[v[0], v[1]], odl=odl, cel_xy=list(cel_xy), limit_s=POSCIG_PAMIEC_S)
            self.ustaw_stan("POGON", f"{c['nazwa']} na pamięć -> ({cel_xy[0]},{cel_xy[1]})")
            return True
        except bot.Zatrzymano:
            raise
        except Exception as e:   # pościg na pamięć nigdy nie wywraca bota
            log(f"debug: pościg na pamięć: błąd {e!r}")
            self.pamiec = None
            return False

    @staticmethod
    def _wektor_ucieczki(c, poz):
        """Wektor ucieczki celu z ostatnich ~4 pozycji; bez śladu: od nas do ostatniej pozycji."""
        sl = c.get("slad") or []
        vx = vy = 0
        if len(sl) >= 2:
            vx, vy = sl[-1][0] - sl[0][0], sl[-1][1] - sl[0][1]
        if not vx and not vy:
            vx, vy = c["poz"][0] - poz[0], c["poz"][1] - poz[1]
        return vx, vy

    def _pamiec_pole_ok(self, x, y, z, znane):
        """Pole, na które wolno wejść w pościgu na pamięć: przechodnie wg mapy albo znane (stał tam gracz),
        nie schody/dziura i nie nauczona ściana."""
        if self.sciana((x, y, z)) or self.pole_zmiany_pietra((x, y, z)):
            return False
        if self.mapa is not None:
            if self.mapa.schody_lub_dziura(x, y, z):
                return False
            pr = self.mapa.przechodnie(x, y, z)
            if pr is not None:
                return bool(pr)
        return (x, y, z) in self.znane or (x * _K + y) in znane

    def _pamiec_koniec_korytarza(self, ost, v, pol):
        """Najdalsze sensowne pole (do `pol` kroków po przechodnich polach od ostatniej pozycji `ost`)
        wzdłuż wektora ucieczki v. Gdy nic nie leży dalej: sama ostatnia pozycja."""
        start, z = (ost[0], ost[1]), ost[2]
        n = (v[0] ** 2 + v[1] ** 2) ** 0.5
        if not n or pol <= 0:
            return start
        ux, uy = v[0] / n, v[1] / n
        znane = self._pola_pietra(z)
        skad = {start: 0}
        kolejka = [start]
        najlepsze, wynik = 0.0, start
        for a in kolejka:
            d = skad[a]
            if d >= pol:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                b = (a[0] + dx, a[1] + dy)
                if b in skad or not self._pamiec_pole_ok(b[0], b[1], z, znane):
                    continue
                skad[b] = d + 1
                kolejka.append(b)
                rzut = (b[0] - start[0]) * ux + (b[1] - start[1]) * uy
                if rzut < 0.5:
                    continue                      # nie w stronę ucieczki
                ocena = rzut + 0.3 * (d + 1)
                if ocena > najlepsze:
                    najlepsze, wynik = ocena, b
        return wynik

    def _pamiec_koniec(self, wynik, powod, poz):
        """Zamyka pościg na pamięć: log + telemetria (poscig_pamiec_koniec)."""
        p, self.pamiec = self.pamiec, None
        if not p:
            return
        c = p["cel"]
        czas = self.zegar() - p["t0"]
        odl = self.dystans(c["poz"], poz)
        log(f"Pościg na pamięć za {c['nazwa']}: {wynik} ({powod}), {czas:.1f} s, {p['kroki']} kroków, odl {odl}.")
        self._tele_poscig("poscig_pamiec_koniec", cel=c["nazwa"], id=c["id"], wynik=wynik, powod=powod,
                          czas=round(czas, 1), kroki=p["kroki"], odl=odl)

    def _pamiec_tick(self, g, poz, lista, teraz):
        """Jeden krok pościgu na pamięć (bez ukrytych pętli: wszystkie zabezpieczenia tick() działają).
        True = obieg wykorzystany (krok / loot); False = pościg skończony, dalej zwykła walka lub trasa."""
        p = self.pamiec
        c = p["cel"]
        if tuple(poz) != p["poz"]:
            p["kroki"] += 1
            p["poz"], p["ruch"] = tuple(poz), teraz
        if poz[2] != c["poz"][2]:
            self._pamiec_koniec("przerwany", "piętro", poz)
            return False
        if self.exp_teraz is not None and p["exp0"] is not None and self.exp_teraz > p["exp0"]:
            log(f"Cel {c['nazwa']} zabity na {c['poz']} (exp +{self.exp_teraz - p['exp0']}, po zniknięciu).")
            self.patrol_zabicia += 1
            self._obecnosc_zabicie(c)
            self._pamiec_koniec("przerwany", "zabity_exp", poz)
            return False
        if g.get("proc") is not None and g["proc"] <= self.prog_aktualny + PAMIEC_HP_MARGINES:
            self._pamiec_koniec("przerwany", "hp_prog", poz)
            return False
        if teraz - self.hp_gracza_spadek < GRYZIE_OKNO:
            self._pamiec_koniec("przerwany", "gryzie", poz)
            return False
        if self._grozni_w_zasiegu(lista, poz):
            self._pamiec_koniec("przerwany", "obcy_gracz", poz)
            return False
        zewn = self._poscig_przerwanie()
        if zewn or self.ostrozny:
            self._pamiec_koniec("przerwany", str(zewn or "ostrozny"), poz)
            return False
        pasuja = [s for s in lista if not s.get("gracz") and s["z"] == poz[2] and s.get("hp", 100) > 0
                  and (s["id"] == c["id"] or (s["nazwa"] == c["nazwa"] and abs(s["hp"] - c["hp"]) <= PAMIEC_HP_TOL))]
        if any(s["id"] not in {x["id"] for x in pasuja} and self.dystans((s["x"], s["y"]), poz) <= 1
               for s in self.kandydaci(lista, poz)):
            self._pamiec_koniec("przerwany", "gryzacy", poz)
            return False
        if pasuja:
            m = min(pasuja, key=lambda s: (s["id"] != c["id"], self.dystans((s["x"], s["y"]), poz)))
            if self.w_widoku(m, poz):
                self.pamiec_znaleziony = (m["id"], c["hp0"] if c.get("hp0") is not None else m["hp"])
                log(f"Cel {c['nazwa']} odnaleziony po zniknięciu ({m['x']},{m['y']}) HP {m['hp']}%.")
                self._pamiec_koniec("odnaleziony", "w_widoku", poz)
                return False
            # na liście, ale poza ekranem: celem pościgu jest jego bieżące pole
            c["poz"], c["hp"] = (m["x"], m["y"], m["z"]), m["hp"]
            p["cel_xy"] = (m["x"], m["y"])
        if teraz >= p["do"]:
            self._pamiec_koniec("limit", "czas", poz)
            return False
        # odłożone zwłoki tuż obok: najpierw loot (jego czas nie liczy się do limitu pościgu)
        if self.loot and self.zwloki_czekajace:
            bliskie = [(z, t) for z, t in self.zwloki_czekajace if z[2] == poz[2]
                       and self.dystans(z, poz) <= PAMIEC_LOOT_ODL and teraz - t < ZWLOKI_WAZNE
                       and self.zwloki_chlod.get(tuple(z), float("-inf")) <= teraz and teraz >= self.loot_chlod_do]
            if bliskie:
                zw = min(bliskie, key=lambda zt: self.dystans(zt[0], poz))[0]
                self.zwloki_czekajace = [(a, t) for a, t in self.zwloki_czekajace if a != zw]
                self.ustaw_stan("LOOT", f"odłożone {zw} (przed pościgiem na pamięć)")
                t0 = self.zegar()
                try:
                    self.zbierz_loot(zw)
                except bot.Zatrzymano:
                    raise
                except Exception as e:
                    log(f"Loot się nie udał: {e!r}")
                p["do"] += self.zegar() - t0
                p["ruch"] = self.zegar()
                return True
        cel_xy = p["cel_xy"]
        if tuple(poz[:2]) == tuple(cel_xy):
            self._pamiec_koniec("limit", "dotarto", poz)
            return False
        if teraz - p["ruch"] > PAMIEC_BEZ_RUCHU:
            self._pamiec_koniec("przerwany", "brak_ruchu", poz)
            return False
        self.ustaw_stan("POGON", f"{c['nazwa']} na pamięć -> ({cel_xy[0]},{cel_xy[1]})")
        self.podejdz(tuple(cel_xy), poz, pilne=True, natychmiast=True, dlugosc=0, objazd=False)
        return True

    def _cel_po_poscigu(self, cel):
        """Po szybkiej pętli pościgu: świeża pozycja celu (z odczytów pętli) trafia do self.cel, żeby
        zniknięcie celu miało właściwą ostatnią pozycję i wektor ucieczki."""
        c = self.cel
        if c is None or cel.get("id") != c.get("id") or "z" not in cel:
            return
        self.zapamietaj_ruch_celu(cel)
        c.update(poz=(cel["x"], cel["y"], cel["z"]), hp=cel["hp"])

    # --- loot w walce: po jednym atomowym kroku (loot.krok_w_walce) na obieg, w przerwie między kontrolami ataku ---

    def _lww_tele(self, typ, **d):
        if self.tele:
            try:
                self.tele.zdarzenie(typ, **d)
            except Exception as e:   # telemetria nigdy nie wywraca bota
                log(f"debug: telemetria błąd {e!r}")

    def _lww_diag(self, powod, atak=None):
        """Ostatnia ocena lootu w walce (powód odmowy i flaga ataku): dopisywana do próbki telemetrii."""
        self.lww_diag = {"t": self.zegar(), "powod": powod, "atak": atak}

    def _lww_powod(self, cel, g, poz, lista, teraz):
        """None = wolno lootować w walce; inaczej powód odmowy/przerwania (też do telemetrii)."""
        powod = self._lww_powod_licz(cel, g, poz, lista, teraz)
        flaga = cel.get("atakowany")
        atak = True if powod is None else (False if powod == "atak_false" else (flaga if isinstance(flaga, bool) else None))
        self._lww_diag(powod or "ok", atak)
        return powod

    def _lww_powod_licz(self, cel, g, poz, lista, teraz):
        if self.ucieczka or self.ostrozny:
            return "ucieczka"
        proc = g.get("proc", 100.0)
        if proc <= self.prog_aktualny + LOOT_W_WALCE_HP_MARGINES or proc < LOOT_W_WALCE_HP:
            return "hp"
        if teraz - self.hp_gracza_spadek < GRYZIE_OKNO:
            return "hp_spadek"
        if teraz - self.hp_wzrost >= CZAS_JEDZENIA - 5 and g.get("hp", 0) < g.get("max_hp", 0):
            return "glod"                          # zaraz jedzenie: nie zaczynamy
        if self.pamiec is not None or self.w_poscigu:
            return "poscig"
        if self._poscig_przerwanie():
            return "pauza_mozgu"                   # pauza_bota / rozmowa z graczem
        zywe = [s for s in lista if not s.get("gracz") and s.get("z") == poz[2] and s.get("hp", 100) > 0]
        if sum(1 for s in zywe if self.dystans((s["x"], s["y"]), poz) <= 1) > LOOT_W_WALCE_STYKAJACE:
            return "stykajace"
        if self._grozni_w_zasiegu(lista, poz):
            return "gracz"
        if self.dystans((cel["x"], cel["y"]), poz) > 1 or cel.get("z") != poz[2]:
            if not (self._lww_okno_otwarte() and cel.get("z") == poz[2]
                    and self.dystans((cel["x"], cel["y"]), poz) <= 4):
                return "cel_daleko"                # okno otwarte, cel blisko (<= 4): dokańczamy krok (limit LOOT_W_WALCE_MAX_S)
        trwa = cel.get("atakowany")
        if not isinstance(trwa, bool):
            trwa = self.czy_atakowany(cel, {"x": poz[0], "y": poz[1]})
        if trwa is not True:
            return "atak_false"
        return None

    def _lww_przerwij(self, powod, teraz, pilne=False, poz=None):
        """Kończy loot w walce (zwłoki zostają na liście: zbierze je loot po walce). Gdy nie ma pośpiechu,
        zamyka okno zwłok; przy pilnych powodach (HP, tłum, ucieczka) zostawia je otwarte - Ctrl+klik
        po walce i tak je obsłuży."""
        lw, self.lww = self.lww, None
        self.lww_chlod_do = teraz + LOOT_W_WALCE_CHLOD_S
        if lw is None:
            return
        zamkniete = None
        if not pilne and hasattr(self.loot, "zamknij_w_walce"):
            try:
                zamkniete = self.loot.zamknij_w_walce(lw["stan"], log=log)
            except bot.Zatrzymano:
                raise
            except Exception as e:
                log(f"Loot w walce: zamknięcie okna nie wyszło: {e!r}")
        if zamkniete is not True and powod != "zwykly_loot" \
                and lw["stan"].get("faza") in ("czekaj", "plan", "przenies", "weryfikuj", "zamknij"):
            # okno zwłok mogło zostać otwarte (pilne przerwanie / klik bez odpowiedzi): zamkniemy je przy okazji
            self.lww_zalegle = {"stan": lw["stan"], "t": teraz, "proby": 0}
        log(f"Loot w walce przerwany: {powod} (zwłoki {lw['zw'][:2]}, kroki {lw['kroki']}, "
            f"{teraz - lw['t0']:.1f} s).")
        self._lww_tele("loot_w_walce_przerwany", powod=powod, poz=list(lw["zw"][:2]), kroki=lw["kroki"],
                       czas=round(teraz - lw["t0"], 1), faza=lw["stan"].get("faza"), zamkniete=zamkniete)

    def _lww_zamknij_zalegle(self, teraz, poz, lista):
        """Zamyka okno zwłok zostawione przez pilne przerwanie lootu w walce (przy najbliższej spokojnej okazji:
        brak celu, nic żywego w odl <= 2). Najwyżej LWW_ZAMKNIECIE_PROB prób i LWW_ZAMKNIECIE_S s."""
        z = self.lww_zalegle
        if z is None or self.lww is not None or self.w_lootcie or self.ucieczka:
            return False
        if teraz - z["t"] > LWW_ZAMKNIECIE_S or z["proby"] >= LWW_ZAMKNIECIE_PROB \
                or self.loot is None or not hasattr(self.loot, "zamknij_w_walce"):
            self.lww_zalegle = None
            return False
        if self._zywe_w_promieniu(lista, poz, 2):
            return False
        z["proby"] += 1
        try:
            wynik = self.loot.zamknij_w_walce(z["stan"], log=log, swiezo=True)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"Loot w walce: zamknięcie zaległego okna nie wyszło: {e!r}")
            wynik = False
        if wynik is True:
            self.lww_zalegle = None
            log("Loot w walce: zamknięto okno zwłok zostawione przez przerwany loot.")
        return True

    def _lww_wybierz(self, poz, lista, teraz):
        """Odłożone zwłoki w odl 1, na których nie stoimy i nie stoi żywy stwór (albo None)."""
        zywe = {(s["x"], s["y"]) for s in lista if s.get("hp", 100) > 0 and s.get("z") == poz[2]}
        best = None
        for z, t in self.zwloki_czekajace:
            if z[2] != poz[2] or teraz - t >= ZWLOKI_WAZNE or self.lww_pomin.get(z, float("-inf")) > teraz \
                    or self._zw_brak_okna_n(z) > 0:
                continue
            if self.dystans(z, poz) != 1 or tuple(z[:2]) == tuple(poz[:2]) or tuple(z[:2]) in zywe \
                    or self._ogien_na(z):
                continue
            best = z if best is None else best
        return best

    def _loot_w_walce(self, cel, g, poz, teraz):
        """Jeden atomowy krok lootu odłożonych zwłok, gdy atak trwa, a my stoimy obok celu. True: krok wykonany
        (to obieg walki: walcz robi tylko krótką pauzę). Każdy warunek sprawdzany od nowa przy każdym kroku;
        zła flaga ataku po kliku w zwłoki = kara (klik mógł wyłączyć atak, do weryfikacji na żywo)."""
        if not LOOT_W_WALCE or self.loot is None or not hasattr(self.loot, "krok_w_walce") or self.stoj_wl:
            return False
        lw = self.lww
        if lw is None and not self.zwloki_czekajace:
            return False                                   # ścieżka gorąca: nie ma czego lootować
        lista = self.ostatnie_stwory or []
        if lw is not None and all(z != lw["zw"] for z, _ in self.zwloki_czekajace):
            self._lww_przerwij("zwloki_zabrane", teraz, pilne=True)    # np. zwykły loot po walce wziął je z listy
            return False
        if lw is not None and teraz - lw["t_ost"] > LOOT_W_WALCE_STARY_S:
            self._lww_przerwij("przerwa_w_krokach", teraz, pilne=True)
            return False
        if lw is None and (teraz < self.lww_chlod_do or teraz < self.lww_kara_do
                           or self.lww_kary >= LOOT_W_WALCE_MAX_KAR):
            self._lww_diag("chlod" if teraz < self.lww_chlod_do else "kara")
            return False
        powod = self._lww_powod(cel, g, poz, lista, teraz)
        if powod is None and lw is None:
            if teraz - self.atak_czas < LOOT_W_WALCE_PO_ATAKU_S or self.cel_spadek == float("-inf") \
                    or teraz - self.ruch_czas < LOOT_W_WALCE_POSTOJ_S:
                self._lww_diag("po_ataku_postoj", True)
                return False
        if lw is not None:
            if powod == "atak_false" and lw["klik_t"] is not None and teraz - lw["klik_t"] < 3.0 \
                    and teraz - self.atak_czas > teraz - lw["klik_t"]:
                # flaga ataku zgasła po naszym kliku (a nie po kliku bota w cel): klik w zwłoki wyłączył atak
                self.lww_kary += 1
                self.lww_kara_do = teraz + LOOT_W_WALCE_KARA_S
                log(f"UWAGA: atak wyłączony po kliku w zwłoki (kara {self.lww_kary}/{LOOT_W_WALCE_MAX_KAR}), "
                    f"loot w walce wstrzymany na {LOOT_W_WALCE_KARA_S:.0f} s" +
                    (" i wyłączony do restartu." if self.lww_kary >= LOOT_W_WALCE_MAX_KAR else "."))
                powod = "atak_wylaczony"
            elif powod is None and teraz - lw["t0"] > LOOT_W_WALCE_MAX_S:
                powod = "czas_limit"
                self.lww_pomin[lw["zw"]] = teraz + LOOT_W_WALCE_POMIN_S
            elif powod is None and tuple(poz[:2]) == tuple(lw["zw"][:2]):
                powod = "na_zwlokach"
            if powod is not None:
                self._lww_przerwij(powod, teraz, pilne=powod in ("hp", "hp_spadek", "stykajace", "ucieczka",
                                                                 "glod", "atak_wylaczony", "pauza_mozgu"))
                return False
            zw = lw["zw"]
        else:
            if powod is not None:
                return False
            zw = self._lww_wybierz(poz, lista, teraz)
            if zw is None:
                return False
            lw = self.lww = {"zw": zw, "stan": {}, "t0": teraz, "t_ost": teraz, "klik_t": None, "kroki": 0}
            log(f"Loot w walce: zwłoki {zw[:2]} obok, {cel['nazwa']} bity (HP {g['proc']:.0f}%).")
        try:
            try:
                self.loot.POMIN_CIEZKIE = int(LOOT_POMIN_CIEZKIE)
            except AttributeError:
                pass
            status, opis = self.loot.krok_w_walce(lw["stan"], zw, poz, log=log)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"Loot w walce: błąd {e!r}")
            self.lww_pomin[zw] = teraz + LOOT_W_WALCE_POMIN_S
            self._lww_przerwij("wyjatek", teraz, pilne=True)
            return False
        lw["t_ost"] = self.zegar()
        if status == "przerwane":
            if opis in ("brak_okna", "brak_pamieci", "obce_okno", "stwor_na_zwlokach", "daleko", "na_zwlokach", "drabina", "dziura"):
                self.lww_pomin[zw] = teraz + LOOT_W_WALCE_POMIN_S
            if opis == "brak_okna":
                self._zw_oznacz_brak_okna(zw)
            self._lww_przerwij(opis, teraz, pilne=True)
            return False
        if status == "gotowe":
            self.zwloki_czekajace = [(a, t) for a, t in self.zwloki_czekajace if a != zw]
            self.zwloki_wiek.pop(tuple(zw), None)
            self._zw_usun_grupe(zw)
            self.lww = None
            self.lww_chlod_do = teraz + LOOT_W_WALCE_CHLOD_S
            log(f"Loot w walce: zwłoki {zw[:2]} obsłużone ({opis}), {lw['kroki']} kroków, {teraz - lw['t0']:.1f} s.")
            self._lww_tele("loot_w_walce_krok", krok="koniec", opis=opis, poz=list(zw[:2]), kroki=lw["kroki"],
                           czas=round(teraz - lw["t0"], 1))
            return True
        if opis is None:
            return False        # tylko odczyt pamięci (czekamy na okno): bez zużycia obiegu walki
        lw["kroki"] += 1
        if opis in ("otwarcie", "przenies") or opis.startswith(("przenies", "jedz")):
            lw["klik_t"] = self.zegar()          # kliknięcie w zwłoki albo przeciągnięcie
        self._lww_tele("loot_w_walce_krok", krok=opis, poz=list(zw[:2]), kroki=lw["kroki"],
                       czas=round(teraz - lw["t0"], 1), hp=round(g.get("proc", 0), 0))
        return True

    def loot_probowane_czysc(self):
        """Zapomina puste pola z poprzednich prób lootu (nowe zabicie / nowe zwłoki)."""
        try:
            self.loot.PROBOWANE.clear()
        except AttributeError:
            pass

    def zbierz_loot(self, zwloki):
        if self.marsz is not None:
            self._marsz_stop(self.postac.pozycja(), "loot")     # MARSZ_KLIK: loot idzie własnymi klikami/krokami
        if not getattr(self, "loot_seria", False):
            self.loot_probowane_czysc()          # inne zwłoki niż w trwającej serii kandydatów: bez cudzych pustych pól
        # Zaległe okno zwłok (po pilnym przerwaniu lootu w walce) zostaje na liście: zwykły loot zamyka tylko
        # okno zwłok, które sam otworzył, a zaległe bywa innych zwłok (albo zostaje po przełączniku).
        # Zamkniemy je po lootcie (zamknij_w_walce: znika z pamięci = nic do roboty).
        if self.lww is not None:
            self._lww_przerwij("zwykly_loot", self.zegar(), pilne=True)   # loot po walce przejmuje okno zwłok
        self.w_lootcie = True
        self.aktywnosc_ts = self.zegar()
        wynik = None
        try:
            wynik = self._zbierz_loot(zwloki)
            if wynik == "brak_okna":
                self._zw_oznacz_brak_okna(zwloki)
            elif wynik == "ok":
                self._zw_usun_grupe(zwloki)
            return wynik
        finally:
            self.w_lootcie = False
            self.aktywnosc_ts = self.zegar()
            if self.lww_zalegle is not None:
                self.lww_zalegle.update(t=self.zegar(), proby=0)   # limit czasu liczymy od końca lootu
            if wynik != "przerwany":
                self.zwloki_wiek.pop(tuple(zwloki), None)   # obsłużone: następne zabicie na tym polu liczy od zera

    def _zbierz_loot(self, zwloki):
        """Podchodzi na pole obok zwłok (zwloki = (x, y, z)) i woła loot.zbierz(zwloki, pozycja_gracza).
        Atak ma pierwszeństwo: gdy w trakcie podchodzenia potwór stoi obok albo blokuje drogę,
        zwłoki trafiają na listę oczekujących (wracamy do nich po walce), a my wracamy do tick()."""
        ostatni_przeglad = float("-inf")
        retry_zejscia = False
        retry_dalej = 0
        retry_lokalny = 0
        for _ in range(KROKI_DO_ZWLOK + 1):
            bot.sprawdz_stop()
            poz = self.postac.pozycja()
            if poz[2] != zwloki[2]:
                log("Zwłoki na innym piętrze, pomijam loot.")
                return None
            self._ogien_tick(poz, self.zegar())
            if self._ogien_na(zwloki):
                # zwłoki leżą na polu ognia: nie wchodzimy po nie (a Ctrl+klik mógłby nas tam poprowadzić)
                self.odloz_zwloki(zwloki)
                self.zwloki_chlod[tuple(zwloki)] = self.zegar() + OGIEN_LOOT_CHLOD_S
                self.lww_pomin[tuple(zwloki)] = self.zegar() + OGIEN_LOOT_CHLOD_S
                log(f"[OGIEN] zwłoki {tuple(zwloki)} leżą na polu ognia, odkładam loot na później.")
                return "przerwany"
            if self.zegar() - ostatni_przeglad > PRZEGLAD_W_LOOCIE:
                ostatni_przeglad = self.zegar()
                if self._hp_nisko():
                    self.odloz_zwloki(zwloki)
                    # chłodzenie: bez mobów (HP ponad progiem ucieczki) bot nie kręci się w kółko przy zwłokach
                    self.zwloki_chlod[tuple(zwloki)] = self.zegar() + LOOT_PRZERWANY_CHLOD_S
                    self.lww_pomin[tuple(zwloki)] = self.zegar() + LOOT_PRZERWANY_CHLOD_S
                    if self.zegar() - self.loot_hp_log_ost >= LOOT_PRZERWANY_LOG_S:
                        self.loot_hp_log_ost = self.zegar()
                        log("Przerywam loot: niskie HP gracza, najpierw ucieczka.")
                    return "przerwany"
                try:
                    self.ostatnie_stwory = self.stwory()
                    self.odnotuj_stwory(self.ostatnie_stwory, poz)
                except Exception:
                    pass
                if LOOT_DYNAMICZNY:
                    # przerywa tylko mob stykający (żywy w odl >= 2 jeszcze nie bije, próba trwa 1-2 s); dotyczy też
                    # podejścia do zwłok (log 12:58:09: "Troll obok/na drodze" przy trollu 3 pola dalej)
                    blisko = [s for s in self.kandydaci(self.ostatnie_stwory, poz)
                              if self.dystans((s["x"], s["y"]), poz) <= 1]
                    if self.loot_styk is not None and len(blisko) <= self.loot_styk["dop"]:
                        blisko = []        # 23.10: loot przy przylegającym mobie - przerwania pilnuje _loot_styk_przerwij
                else:
                    blisko = [s for s in self.kandydaci(self.ostatnie_stwory, poz)
                              if self.dystans((s["x"], s["y"]), poz) <= 1
                              or self.dystans((s["x"], s["y"]), zwloki) < self.dystans(poz, zwloki)
                              and self.dystans((s["x"], s["y"]), poz) <= 2]
                    blisko = blisko or ([z] if (z := self.zywy_w_poblizu(self.ostatnie_stwory, poz)) is not None
                                        and self.dystans((z["x"], z["y"]), poz) <= 3 else [])
                if blisko:
                    self.odloz_zwloki(zwloki)
                    log(f"Przerywam loot: {blisko[0]['nazwa']} obok/na drodze, najpierw walka.")
                    return "przerwany"
            if self.loot_styk is not None and self.dystans(poz, zwloki) != 1:
                # 23.10: loot przy przylegającym mobie bez kroków (ani podejścia, ani zejścia ze zwłok): zwłoki na później
                self.odloz_zwloki(zwloki)
                log("Loot przy przylegającym mobie: zwłoki nie w odl 1 (bez kroków), odkładam na po walce.")
                return "przerwany"
            if tuple(poz[:2]) == tuple(zwloki[:2]):
                # stoimy na zwłokach: Ctrl+klik nie zadziała, schodzimy na wolne sąsiednie pole
                self.zejdz_ze_zwlok(poz, zwloki)
                continue
            if self.dystans(poz, zwloki) <= 1:
                if self.klik is not None and not (LOOT_DYNAMICZNY and self.zegar() - self.ruch_czas >= 1.0):
                    # (LOOT_DYNAMICZNY: stoimy od >= 1 s, nie czekamy dodatkowych ~0,5 s przed pierwszym klikiem)
                    poz = self.poczekaj_na_postoj(poz)   # klik w zwłoki liczymy od pola, na którym STOIMY
                    if tuple(poz[:2]) == tuple(zwloki[:2]):
                        continue
                    if self.dystans(poz, zwloki) > 1:
                        continue                         # dojście przesunęło nas dalej: jeszcze raz
                wynik = self._zbierz_z_przegladem(zwloki, poz)
                if wynik == "przerwany":
                    self.odloz_zwloki(zwloki)
                    log("Przerywam loot: potwór obok w trakcie zbierania, najpierw walka.")
                    return "przerwany"
                if wynik == "brak_okna" and not retry_zejscia:
                    po = self.postac.pozycja()
                    if tuple(po[:2]) == tuple(zwloki[:2]):
                        # Ctrl+klik podprowadził nas na zwłoki: schodzimy i otwieramy jeszcze raz
                        # (pola puste z tej próby loot pomija, nie powtarza identycznego przeszukania)
                        retry_zejscia = True
                        log("Loot: stoję na zwłokach, schodzę na sąsiednie pole i próbuję ponownie.")
                        continue
                if wynik == "brak_okna" and LOOT_POD_NOGAMI_PIERWSZE and retry_dalej < LOOT_RETRY_DALEJ \
                        and getattr(self.loot, "NIEDOKONCZONE", False) is True:
                    # budżet LOOT_MAKS_PROB pól wyczerpany, a zostały nieprzeszukane pola: kolejna runda
                    # (pola już puste są pomijane), zamiast 9 klików za jednym razem
                    retry_dalej += 1
                    log(f"Loot: {LOOT_MAKS_PROB} pola puste, szukam dalej wśród pozostałych (runda {retry_dalej + 1}).")
                    continue
                if wynik == "brak_okna" and LOOT_POD_NOGAMI_PIERWSZE and retry_lokalny < LOOT_PONOW_LOKALNIE \
                        and getattr(self.loot, "NIEDOKONCZONE", False) is True and self._brak_zywych_w_widoku(poz):
                    # 12.10: brak okna, zostały nieprzeszukane pola, nic żywego w widoku: jedna runda od razu,
                    # bez czekania na decyzję modelu (pola już puste są pomijane)
                    retry_lokalny += 1
                    log("Loot: puste pola, nic żywego w widoku, ponawiam od razu na pozostałych polach.")
                    continue
                log(f"Loot: {wynik}")
                return wynik
            self.zapamietaj_pole(poz)
            # do zwłok idziemy także naokoło, ale nigdy na ich pole (zwłoki liczą się jak zajęte)
            self.podejdz(zwloki, poz, objazd=False, zajete=self.zajete_bez_nas(poz) + [tuple(zwloki[:2])])
        log(f"Nie doszedłem do zwłok {zwloki}, pomijam loot.")
        return None

    def _brak_zywych_w_widoku(self, poz):
        """Świeży skan: brak żywych potworów (nie graczy) na tym piętrze w oknie widoku. Błąd odczytu = False."""
        try:
            lista = self.stwory()
        except bot.Zatrzymano:
            raise
        except Exception:
            return False
        self.ostatnie_stwory = lista
        return not any(not s.get("gracz") and s.get("z") == poz[2] and s.get("hp", 100) > 0
                       and abs(s["x"] - poz[0]) <= ZASIEG_X and abs(s["y"] - poz[1]) <= ZASIEG_Y for s in lista)

    def _zbierz_z_przegladem(self, zwloki, poz):
        """loot.zbierz z hakiem PRZERWIJ: w trakcie przenoszenia przedmiotów (kilka sekund) co ~0,5 s
        sprawdzamy stwory i przerywamy, gdy żywy potwór jest obok."""
        cele = [self.loot]
        modul = sys.modules.get("loot")
        if modul is not None and modul is not self.loot:
            cele.append(modul)
        ustawione = []
        alt = list(getattr(self, "loot_alternatywy", None) or [])
        for c in cele:
            try:
                c.PRZERWIJ = self._przerwij_loot
                c.POD_NOGAMI_PIERWSZE = bool(LOOT_POD_NOGAMI_PIERWSZE)
                c.MAKS_PROB = int(LOOT_MAKS_PROB)
                c.ALTERNATYWY = alt if LOOT_POD_NOGAMI_PIERWSZE else []
                c.NIEDOKONCZONE = False
                c.POMIN_CIEZKIE = int(LOOT_POMIN_CIEZKIE)
                ustawione.append(c)
            except AttributeError:
                pass
        self.przeglad_odl = 1 if LOOT_DYNAMICZNY else None
        try:
            return self.loot.zbierz(zwloki, poz)
        finally:
            self.przeglad_odl = None
            for c in ustawione:
                c.PRZERWIJ = None
                try:
                    c.ALTERNATYWY = []
                except AttributeError:
                    pass

    def _hp_nisko(self):
        """Świeży odczyt HP: czy jesteśmy blisko progu ucieczki (loot i inne dłuższe akcje wtedy przerywamy)."""
        try:
            g = self.gracz()
        except bot.Zatrzymano:
            raise
        except Exception:
            return False
        proc = g.get("proc", 100.0)
        self.loot_hp_proc = proc
        if proc <= self.prog_aktualny + LOOT_HP_ZAGROZENIE:
            return True
        if proc > self.prog_aktualny + LOOT_HP_MARGINES:
            return False
        # HP w marginesie: przerywamy tylko, gdy faktycznie grozi walka (żywy potwór w pobliżu).
        # Bez mobów to najbezpieczniejsza chwila na loot.
        try:
            lista = self.stwory()
            poz = self.postac.pozycja()
        except bot.Zatrzymano:
            raise
        except Exception:
            return True
        self.ostatnie_stwory = lista
        return bool(self._zywe_w_promieniu(lista, poz, LOOT_HP_MOBY_ODL))

    def _przerwij_loot(self):
        t = self.zegar()
        if t - self.przeglad_loot_ost < 0.5:
            return False
        self.przeglad_loot_ost = t
        if self._hp_nisko():
            return True
        try:
            lista = self.stwory()
            poz = self.postac.pozycja()
        except bot.Zatrzymano:
            raise
        except Exception:
            return False
        self.ostatnie_stwory = lista
        if self.loot_styk is not None:
            return self._loot_styk_przerwij(self.loot_styk, lista, poz, t)
        odl = LOOT_PRZEGLAD_ODL if self.przeglad_odl is None else self.przeglad_odl
        return any(self.dystans((s["x"], s["y"]), poz) <= odl for s in self.kandydaci(lista, poz))

    def _loot_styk_przerwij(self, st, lista, poz, t):
        """Loot zaraz po zabiciu przy przylegającym mobie (LOOT_SZYBKI_STYKAJACE): przerywamy, gdy przylega więcej mobów niż
        dopuszczone, HP spadło o >= GRYZIE_SPADEK_PP w GRYZIE_OKNO (jak hp_spadek w lootcie w walce) albo minął limit czasu.
        Zwłoki zostają na liście (odkłada je wołający), a walka rusza dalej."""
        if t - st["t0"] > LOOT_SZYBKI_STYK_MAX_S:
            log(f"Loot przy przylegającym mobie: limit {LOOT_SZYBKI_STYK_MAX_S:.0f} s, przerywam (zwłoki zostają na później).")
            return True
        proc = self.loot_hp_proc
        if proc is not None:
            st["hp"] = [(tt, p) for tt, p in st["hp"] if t - tt <= GRYZIE_OKNO] + [(t, proc)]
            if max(p for _, p in st["hp"]) - proc >= GRYZIE_SPADEK_PP:
                log(f"Loot przy przylegającym mobie: HP spadło ({proc:.0f}%), przerywam (hp_spadek).")
                return True
        styk = [s for s in self.kandydaci(lista, poz) if self.dystans((s["x"], s["y"]), poz) <= 1]
        if len(styk) > st["dop"]:
            log(f"Loot przy przylegającym mobie: przylega {len(styk)} (dopuszczone {st['dop']}), przerywam.")
            return True
        return False

    def zajete_bez_nas(self, poz):
        return [(s["x"], s["y"]) for s in self.ostatnie_stwory
                if s["z"] == poz[2] and s.get("hp", 100) > 0 and (s["x"], s["y"]) != tuple(poz[:2])
                and not (s.get("gracz") and s.get("nazwa") == self.postac.nazwa) and not s.get("widmo")]

    def zejdz_ze_zwlok(self, poz, zwloki):
        """Krok z pola zwłok na wolne sąsiednie pole (proste przed skosem, przechodnie wg mapy)."""
        zajete = set(self.zajete_bez_nas(poz))
        x, y, z = poz[0], poz[1], poz[2]
        kand = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)):
            n = (x + dx, y + dy, z)
            if (n[0], n[1]) in zajete or self.sciana(n):
                continue
            if self.mapa is not None and self.mapa.flagi(*n) & 1 and self.mapa.przechodnie(*n) is False:
                continue
            kand.append(n)
        kand.sort(key=lambda n: (n[0] != x and n[1] != y, not (self.mapa is not None and self.mapa.flagi(*n) & 1)))
        for n in kand:
            if self.krok_do((n[0], n[1])):
                self.poczekaj_na_postoj(poz)
                return n
        return None

    def poczekaj_na_postoj(self, poz, limit=1.5):
        """Czeka, aż postać przestanie iść (ta sama pozycja w dwóch odczytach co ~0,25 s)."""
        koniec = self.zegar() + limit
        while self.zegar() < koniec:
            self.pauza(0.2, 0.3)
            teraz = self.postac.pozycja()
            if teraz == poz:
                return teraz
            poz = teraz
        return poz

    def odloz_zwloki(self, zwloki, nowe=False):
        """Dopisuje zwłoki do listy oczekujących. Czas wpisu = czas ZABICIA: ponowne odłożenie po przerwaniu
        (loot przerwany przez HP/potwora) nie resetuje TTL. nowe=True: świeże zabicie, zegar od teraz."""
        klucz = tuple(zwloki)
        teraz = self.zegar()
        if nowe or klucz not in self.zwloki_wiek or teraz - self.zwloki_wiek[klucz] >= ZWLOKI_WAZNE:
            self.zwloki_wiek[klucz] = teraz
        if nowe:
            self.zw_brak_okna.pop(klucz, None)       # nowe zwłoki na tym polu: licznik "brak_okna" od zera
            self.lww_pomin.pop(klucz, None)
            self.zwloki_czekajace = [(z, t) for z, t in self.zwloki_czekajace if z != zwloki]
        if all(z != zwloki for z, _ in self.zwloki_czekajace):
            self.zwloki_czekajace.append((zwloki, self.zwloki_wiek[klucz]))

    def _zwloki_w_zasiegu(self, poz):
        """Czy któreś odłożone zwłoki (ważne, to samo piętro) są w ZWLOKI_ZASIEG od nas (bez zmiany listy)."""
        teraz = self.zegar()
        return any(teraz - t < ZWLOKI_WAZNE and z[2] == poz[2] and self.dystans(z, poz) <= ZWLOKI_ZASIEG
                   for z, t in self.zwloki_czekajace)

    def _zwloki_po_ucieczce(self, teraz):
        """Ucieczka nie pali TTL zwłok: dosuwamy czasy wpisów o czas jej trwania i dajemy zwłokom priorytet."""
        if not ZWLOKI_PO_UCIECZCE or not self.zwloki_czekajace:
            return
        dt = max(0.0, teraz - self.ucieczka_od) if self.ucieczka_od is not None else 0.0
        if dt > 0:
            self.zwloki_czekajace = [(z, min(t + dt, teraz)) for z, t in self.zwloki_czekajace]
            self.zwloki_wiek = {k: min(v + dt, teraz) for k, v in self.zwloki_wiek.items()}
        self.zwloki_priorytet_do = teraz + ZWLOKI_PO_UCIECZCE_PRIORYTET_S
        log(f"Po ucieczce ({dt:.0f} s): {len(self.zwloki_czekajace)} odłożonych zwłok, czasy dosunięte, wracam po nie.")

    def zywy_w_poblizu(self, lista, poz):
        """Najbliższy żywy potwór z naszej listy w LOOT_PO_WALCE polach (także ignorowany) albo None."""
        best = None
        for s in lista:
            if s["gracz"] or s["z"] != poz[2] or s.get("hp", 100) <= 0:
                continue
            if self.potwory is not None and s["nazwa"].casefold() not in self.potwory:
                continue
            d = self.dystans((s["x"], s["y"]), poz)
            # uciekający (prawie martwy) ma pierwszeństwo przed lootem także z dalszej odległości
            zasieg = max(LOOT_PO_WALCE, DOBICIE_ZASIEG_UCIEKAJACY) if self.uciekajacy(s) else LOOT_PO_WALCE
            if d <= zasieg and (best is None or d < best[0]):
                best = (d, s)
        return best[1] if best else None

    def zwloki_do_zebrania(self, poz):
        """Najbliższe oczekujące zwłoki (świeże, na tym piętrze, niedaleko) albo None."""
        teraz = self.zegar()
        # kasujemy tylko stare (TTL od zabicia) i z innego piętra; dalekie (> ZWLOKI_ZASIEG) zostają do końca TTL
        # i są tylko pomijane (bot mógł się oddalić pościgiem i wróci w okolicę)
        if LOOT_DYNAMICZNY:
            # zwłoki z innego piętra zostają na liście do końca TTL (nie próbujemy ich, dopóki jesteśmy gdzie indziej);
            # porzucone po drugim "brak_okna" znikają
            self.zwloki_czekajace = [(z, t) for z, t in self.zwloki_czekajace
                                     if teraz - t < ZWLOKI_WAZNE and self._zw_brak_okna_n(z) < 2]
            if len(self.zw_brak_okna) > 200:
                self.zw_brak_okna.clear()
        else:
            self.zwloki_czekajace = [(z, t) for z, t in self.zwloki_czekajace
                                     if teraz - t < ZWLOKI_WAZNE and z[2] == poz[2]]
        self.zwloki_wiek = {k: v for k, v in self.zwloki_wiek.items() if teraz - v < ZWLOKI_WAZNE}
        self.zwloki_chlod = {k: v for k, v in self.zwloki_chlod.items() if v > teraz}
        if not self.zwloki_czekajace or teraz < self.loot_chlod_do:
            return None
        gotowe = [zt for zt in self.zwloki_czekajace if self.zwloki_chlod.get(tuple(zt[0]), float("-inf")) <= teraz
                  and zt[0][2] == poz[2]
                  and self.dystans(zt[0], poz) <= ZWLOKI_ZASIEG and not self._ogien_na(zt[0])]
        if not gotowe:
            return None            # wszystkie w chłodzeniu: bot idzie trasą, wrócimy do nich po chłodzeniu
        z, _ = min(gotowe, key=lambda zt: self.dystans(zt[0], poz))
        self.zwloki_czekajace = [(a, t) for a, t in self.zwloki_czekajace if a != z]
        return z

    def spadek_hp(self, proc, teraz):
        """Zapisuje odczyt HP i zwraca największy spadek (pp, <= UCIECZKA_PREDYKCJA_MAX) między kolejnymi
        odczytami z ostatnich UCIECZKA_PREDYKCJA_OKNO s: tyle zdejmie kolejne uderzenie."""
        # starszy odczyt (np. sprzed długiego pościgu/lootu) zostaje jako punkt odniesienia: ostatni z nich
        stare = [(t, p) for t, p in self.hp_historia if teraz - t > UCIECZKA_PREDYKCJA_OKNO]
        h = stare[-1:] + [(t, p) for t, p in self.hp_historia if teraz - t <= UCIECZKA_PREDYKCJA_OKNO]
        h.append((teraz, proc))
        self.hp_historia = h
        spadek = max((a[1] - b[1] for a, b in zip(h, h[1:])), default=0.0)
        return min(max(spadek, 0.0), UCIECZKA_PREDYKCJA_MAX)

    def po_ucieczce(self):
        """Wywoływane po wyjściu z ucieczki (podklasy: np. zdjęcie pauzy narzuconej w trakcie ucieczki)."""

    def zjedz(self, teraz, g=None):
        self.aktywnosc_ts = teraz
        stan_many = self._stan_many(g) if g else ""
        if self.jedzenie:
            self.ustaw_stan("JEDZENIE", f"klawisz {self.jedzenie}" + (f" [{stan_many}]" if stan_many else ""))
            self.postac.klawisz(self.jedzenie)
        else:
            self.ustaw_stan("JEDZENIE", "z plecaka" + (f" [{stan_many}]" if stan_many else ""))
            # brak jedzenia nie jest awarią: po nieudanej próbie jedna linia w logu na JEDZENIE_LOG_S,
            # reszta cicho (bez alarmu, bez pauzy, bez zmiany trybu)
            glosno = self.zegar() - self.brak_jedzenia_log >= JEDZENIE_LOG_S
            szczegoly = []
            zjedzone = self.loot.zjedz(log=lambda *a, **k: szczegoly.append(" ".join(map(str, a))))
            if zjedzone:
                log(f"Zjedzono: {', '.join(zjedzone)}")
            else:
                if glosno:
                    self.brak_jedzenia_log = self.zegar()
                    log("Zjedzono: nic (brak jedzenia)" + (f" [{'; '.join(szczegoly)[:150]}]" if szczegoly else ""))
                # plecak pusty (albo najedzony): bez ponawiania przez JEDZENIE_PONOW s,
                # każda próba to 3-5 s ślepego bloku
                self.jedzenie_nie_do = self.zegar() + JEDZENIE_PONOW
                if any("najedzony" in t for t in szczegoly):
                    # 14.10 18:04: jedzenie jest, tylko postać syta ("nie ubyło, najedzony"): to NIE brak jedzenia
                    # (wcześniej potwierdzało głód i wysyłało do depo z 3 hamami w plecaku)
                    self.jedzenie_nieczytelne_do = self.zegar() + JEDZENIE_PONOW
                    log("JEDZENIE: postać najedzona, jedzenie w plecaku jest (to nie brak jedzenia)")
                elif JEDZENIE_BRAK_WALIDUJ and not self._kontenery_czytelne_po_porazce():
                    # kontenery niewidoczne: to nie dowód braku jedzenia (nie wołamy wyprawy ani F3 "głód")
                    self.jedzenie_nieczytelne_do = self.zegar() + JEDZENIE_PONOW
                    log("JEDZENIE: pamięć nie widzi plecaka, brak jedzenia niepotwierdzony")
                else:
                    self.jedzenie_nieczytelne_do = float("-inf")
        self.hp_wzrost = teraz
        self.hp_regen = teraz
        self.mana_wzrost = teraz        # po jedzeniu dajemy manie JEDZENIE_MANA_BRAK_S na ruszenie
        self.pauza(0.5, 1.2)

    # --- obrona przed graczami (obrona_pk.py) ---------------------------------------------------------------

    def _pk_dane(self):
        """(DetektorPK, Wrogowie), tworzone przy pierwszym użyciu. Zegar ścienny dla pliku wrogów: time.time na żywo,
        w testach (wstrzyknięty zegar) ten sam zegar; testy mogą podmienić self.pk_wrogowie (plik tymczasowy)."""
        if self.pk_det is None:
            import obrona_pk  # noqa: PLC0415
            czas = time.time if self.zegar is time.monotonic else self.zegar
            plik = None
            if os.environ.get("RETRONIC_TESTY"):          # testy nigdy nie piszą do prawdziwego wrogowie.json
                import tempfile  # noqa: PLC0415
                global _PK_TEST_N
                _PK_TEST_N += 1                       # osobny, świeży plik na instancję (id() bywa ponownie użyte)
                plik = os.path.join(tempfile.gettempdir(), f"wrogowie-test-{os.getpid()}-{_PK_TEST_N}.json")
                try:
                    os.remove(plik)
                except OSError:
                    pass
            self.pk_det = obrona_pk.DetektorPK(sys.modules[__name__], zegar=self.zegar, log=lambda t: log(t))
            self.pk_wrogowie = obrona_pk.Wrogowie(plik, czas=czas, log=lambda t: log(t))
        return self.pk_det, self.pk_wrogowie

    def _pk_blokuje_powrot(self, teraz):
        """Ucieczka awaryjna PK: nie wracamy na spot, dopóki trwa karencja albo wróg był w widoku przed chwilą."""
        if self.pk_stan is None or not self.pk_fallback:
            return False
        try:
            _, wr = self._pk_dane()
            return bool(wr.karencja_aktywna() or teraz - self.pk_widoczni_ost < 5.0)
        except Exception:
            return False

    def _alarm_pk(self, tekst):
        """Alarm PK. PK_SZYBKIE=1: w wątku (alarm_dzwiekowy blokuje do 4 s na paplay, a to martwy czas ucieczki); 0: jak dotąd."""
        if not PK_SZYBKIE:
            return self.alarm(tekst)

        def _graj():
            try:
                self.alarm(tekst)
            except Exception as e:
                log(f"PK: alarm nie zadziałał ({e!r})")
        threading.Thread(target=_graj, daemon=True).start()

    def _pk_powiadom(self, tytul, tresc, klucz):
        try:
            import powiadom  # noqa: PLC0415
            powiadom.powiadom(tytul, tresc, "critical", klucz)
        except Exception:
            pass

    def _pk_stop(self, opis):
        try:
            Path(bot.STOP).write_text(f"PK: {opis}\n")
            log(f"PK: zapisałem {bot.STOP} (zatrzymanie bota: {opis})")
        except OSError as e:
            log(f"PK: nie zapisałem STOP ({e})")

    def _rozl_detektor(self):
        if self._rozl_det is None:
            import rozlaczenie  # noqa: PLC0415
            self._rozl_det = rozlaczenie.Detektor()
        return self._rozl_det

    def _rozl_zrzut_fn(self):
        f = self._rozl_zrzut
        if f is None:
            import rozlaczenie  # noqa: PLC0415
            f = rozlaczenie.zrzut_logowania
        return f

    def _rozl_odcisk(self, g, poz):
        import rozlaczenie  # noqa: PLC0415
        return rozlaczenie.odcisk(g, poz, getattr(self, "stwory_surowe", None))

    def _rozl_tick(self, g, poz, teraz):
        """ROZLACZENIE_STOP (21.10). True = obieg zużyty (rozłączenie ogłoszone właśnie teraz). Detektor dostaje odcisk życia
        klienta (statystyki, pozycja, lista stworów z ostatniego skanu); zrzut ekranu tylko gdy odcisk stoi >= 10 s."""
        try:
            wynik = self._rozl_detektor().krok(teraz, self._rozl_odcisk(g, poz), self._rozl_zrzut_fn())
            if wynik == "rozlaczenie":
                self._rozl_ogloz(poz, teraz)
                return True
            return False
        except bot.Zatrzymano:
            raise
        except Exception as e:                            # detekcja nigdy nie wywraca bota
            log(f"debug: rozłączenie błąd {e!r}")
            return False

    def _rozl_ogloz(self, poz, teraz):
        """Jednorazowo: stan ROZLACZONY, log, telemetria 'rozlaczenie', puszczenie trzymanych klawiszy, powiadomienie critical."""
        det = self._rozl_detektor()
        self.rozlaczony = True
        ostatni_stan = str(self.stan)
        czas = time.strftime("%H:%M:%S")
        self._rozl_start = (teraz, time.time(), tuple(poz), self.stan)
        self.ustaw_stan("ROZLACZONY", f"klient wylogowany (ekran logowania), pamięć stoi {det.zamrozone_s:.0f} s, poz {tuple(poz)}")
        koniec = bool(ROZLACZENIE_WYJSCIE)
        log(f"ROZŁĄCZENIE: pamięć gry stoi {det.zamrozone_s:.0f} s, a zrzut pokazuje ekran logowania. Przestaję naciskać klawisze "
            + ("i kończę proces (WYLOGOWANIE_WYJSCIE)" if koniec else "i czekam na powrót do gry")
            + f" (poz {tuple(poz)}, ostatni stan {ostatni_stan}).")
        try:
            self._poscig_puszcz()                         # tylko puszcza klawisze ruchu, nic nie wciska
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"debug: rozłączenie: puszczenie klawiszy {e!r}")
        self._tele_poscig("rozlaczenie", poz=list(poz[:3]), czas=czas, ostatni_stan=ostatni_stan,
                          zamrozone_s=round(det.zamrozone_s, 1), zrzuty=det.pozytywne)
        nick = getattr(self.postac, "nazwa", None) or "?"
        if koniec:
            self._pk_powiadom("Bot: wylogowany, kończę", f"{nick}, {czas}: klient pokazuje ekran logowania. Bot kończy proces bez "
                              f"klawiszy; relog uruchomi go od nowa.", "rozlaczenie")
            self._wyloguj_koniec(f"ekran logowania, pamięć gry stoi {det.zamrozone_s:.0f} s", poz)
        else:
            self._pk_powiadom("Bot: rozłączony", f"{nick}, {czas}: klient pokazuje ekran logowania. Bot nie naciska klawiszy, "
                              f"czeka na powrót do gry (bez auto-logowania).", "rozlaczenie")

    def _wyloguj_koniec(self, powod, poz=None):
        """23.10: wylogowanie = koniec procesu. Zero klawiszy; log `WYLOGOWANY: kończę bota`; znacznik `wylogowany.json` w stanie
        instancji (czas, powód, mapa i tryb z tryb.log) dla relogu; tick() zwraca od teraz False, a mozg kończy pętlę i sprząta
        (stan zapisany w `finally`). Nie czeka na powrót do gry. Nigdy nie rzuca."""
        if self.wylogowany:
            return
        self.wylogowany = True
        try:
            self._poscig_puszcz()                         # tylko puszcza trzymane klawisze ruchu
        except bot.Zatrzymano:
            raise
        except Exception as e:                            # noqa: BLE001
            log(f"debug: wylogowanie: puszczenie klawiszy {e!r}")
        stan, tryb_log = self.wylog_stan, self.wylog_tryb_log
        if stan is None and not os.environ.get("RETRONIC_TESTY"):
            stan, tryb_log = instancja.S.stan, tryb_log or instancja.S.tryb_log
        znacznik = None
        try:
            import wylogowanie  # noqa: PLC0415
            wylogowanie.ogloszono(powod)
            if stan is not None:
                znacznik = wylogowanie.zapisz(stan, powod, tryb_log=tryb_log, poz=poz, nick=getattr(self.postac, "nazwa", None))
        except Exception as e:                            # noqa: BLE001
            log(f"debug: wylogowanie: znacznik {e!r}")
        gdzie = ""
        if znacznik:
            gdzie = f" Znacznik: {znacznik.get('blad') or 'wylogowany.json'}, mapa {znacznik.get('mapa')}, tryb {znacznik.get('tryb')}."
        log(f"WYLOGOWANY: kończę bota ({powod}). Bez klawiszy, stan zapisany, nie czekam na powrót do gry.{gdzie}")

    def _brak_postaci_tick(self, e):
        """23.10: odczyt gracza/pozycji rzucił (strażnik nie widzi postaci: zniknęła z pamięci po wylogowaniu). Zrzut tylko tu (zdrowa gra
        = koszt 0); ZRZUTY_POTW zrzutów z ekranem logowania = wylogowanie, koniec procesu (True). Zrzut = gra albo brak zrzutu = False
        (wywołujący puszcza błąd dalej, mozg liczy LIMIT_BLEDOW jak dotąd)."""
        try:
            if self._brak_postaci is None:
                import wylogowanie  # noqa: PLC0415
                self._brak_postaci = wylogowanie.BrakPostaci()
            if not self._brak_postaci.krok(self.zegar(), self._rozl_zrzut_fn()):
                return False
            log(f"ROZŁĄCZENIE: nie widzę postaci w pamięci gry ({e!r}), a zrzut pokazuje ekran logowania.")
            nick = getattr(self.postac, "nazwa", None) or "?"
            self._pk_powiadom("Bot: wylogowany, kończę", f"{nick}, {time.strftime('%H:%M:%S')}: postaci brak w pamięci gry, ekran "
                              f"logowania. Bot kończy proces bez klawiszy; relog uruchomi go od nowa.", "rozlaczenie")
            self._wyloguj_koniec("postaci brak w pamięci gry, zrzut = ekran logowania", None)
            return True
        except bot.Zatrzymano:
            raise
        except Exception as e2:                           # noqa: BLE001
            log(f"debug: brak postaci: {e2!r}")
            return False

    def _rozl_pauza(self):
        """Obieg w stanie ROZLACZONY: tylko odczyt i zrzut co 3 s (bez klawiszy, kliknięć i modelu). Błąd odczytu (trwa logowanie,
        brak statystyk gracza) nie kończy bota. True zawsze."""
        try:
            teraz = self.zegar()
            try:
                g = self.gracz()
                poz = self.postac.pozycja()
                self.stwory(1.0)
                odcisk = self._rozl_odcisk(g, poz)
            except bot.Zatrzymano:
                raise
            except Exception:
                odcisk = ("brak odczytu",)                # stały znacznik: brak odczytu nie liczy się jako ruch pamięci
            det = self._rozl_detektor()
            if det.krok(teraz, odcisk, self._rozl_zrzut_fn()) == "wznowienie":
                self._rozl_wznow(teraz)
            else:
                self.spij(1.0)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"debug: rozłączenie (pauza) błąd {e!r}")
            self.spij(1.0)
        return True

    def _rozl_wznow(self, teraz):
        """Powrót do gry: log, telemetria 'rozlaczenie_koniec', reset liczników bezczynności, ponowny wybór własnego wpisu."""
        start = self._rozl_start
        self.rozlaczony = False
        czas_s = (teraz - start[0]) if start else None
        log(f"Rozłączenie zakończone po {czas_s:.0f} s: klient znów w grze, wznawiam pracę." if czas_s is not None
            else "Rozłączenie zakończone: klient znów w grze, wznawiam pracę.")
        self._tele_poscig("rozlaczenie_koniec", czas_s=round(czas_s, 1) if czas_s is not None else None)
        self._rozl_start = None
        for pole in ("aktywnosc_ts", "ruch_czas", "hp_wzrost", "hp_regen", "mana_wzrost"):
            if hasattr(self, pole):
                setattr(self, pole, teraz)
        try:
            bot._wlasny["t"] = float("-inf")                # po relogu może być widmo własnego wpisu: wybór od nowa
        except Exception:
            pass
        self.ustaw_stan(start[3] if start and start[3] else "IDZ", "po rozłączeniu")

    def _smierc_tick(self, g, poz, teraz):
        """SMIERC_STOP (R5/P5). True = obieg zużyty (podejrzenie albo zgon): bez żadnej akcji. Zgon = HP == 0 przez
        SMIERC_ODCZYTY odczytów z rzędu albo HP == 0 ze skokiem pozycji (respawn). Pojedynczy odczyt 0 bez przesłanki
        tylko wstrzymuje ten obieg. Telemetria po respawnie potrafi długo dawać HP 0: po zgonie to już bez znaczenia (MARTWY)."""
        try:
            hp, mx = g.get("hp"), g.get("max_hp")
            if hp is None or not mx:
                return False                              # brak wiarygodnego odczytu: nie oceniamy
            if hp > 0:
                self._smierc_zero = 0
                self._smierc_zywy = (tuple(poz), teraz)
                return False
            self._smierc_zero += 1
            zyw = self._smierc_zywy
            skok = zyw is not None and (poz[2] != zyw[0][2] or max(abs(poz[0] - zyw[0][0]), abs(poz[1] - zyw[0][1])) >= SMIERC_SKOK)
            if self._smierc_zero < SMIERC_ODCZYTY and not skok:
                if self._smierc_zero == 1:
                    log("Śmierć?: HP 0 w jednym odczycie, czekam na potwierdzenie (obieg bez akcji).")
                return True
            self._smierc_potwierdz(poz, zyw, skok)
            return True
        except bot.Zatrzymano:
            raise
        except Exception as e:                            # detekcja nigdy nie wywraca bota
            log(f"debug: śmierć błąd {e!r}")
            return False

    def _smierc_potwierdz(self, poz, zyw, skok):
        """Jednorazowo: stan MARTWY, log, telemetria 'smierc', STOP i jedno powiadomienie."""
        self.martwy = True
        ostatni_stan = str(self.stan)
        czas = time.strftime("%H:%M:%S")
        miejsce = zyw[0] if zyw else tuple(poz)
        pow_ = f"{miejsce[0]},{miejsce[1]},{miejsce[2]}"
        przyczyna = "skok pozycji" if skok else f"HP 0 w {self._smierc_zero} odczytach"
        self.ustaw_stan("MARTWY", f"HP 0 ({przyczyna}), ostatnia żywa poz {tuple(miejsce)}, teraz {tuple(poz)}")
        self.cel = None
        try:
            self._poscig_puszcz()                         # tylko puszcza klawisze ruchu, nic nie wciska
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"debug: śmierć: puszczenie klawiszy {e!r}")
        stwory = []
        for m in (self.ostatnie_stwory or [])[:8]:
            try:
                stwory.append({"n": m.get("nazwa"), "dx": m["x"] - miejsce[0], "dy": m["y"] - miejsce[1],
                               "gracz": bool(m.get("gracz")), "hp": m.get("hp")})
            except Exception:
                continue
        self._tele_poscig("smierc", poz=list(poz[:3]), ostatnia_zywa_poz=list(miejsce[:3]), czas=czas,
                          ostatni_stan=ostatni_stan, przyczyna=przyczyna, stwory=stwory)
        nick = getattr(self.postac, "nazwa", None) or "?"
        self._pk_stop(f"zgon {nick} {czas} {pow_}")
        self._pk_powiadom("Bot zginął", f"{nick}, {czas}, poz {pow_}. Bot zatrzymany.", "smierc")

    def _pk_tick(self, g, poz, teraz):
        """True, gdy obieg zużyty (start ucieczki PK, czekanie w depo, leczenie z postojem)."""
        try:
            return self._pk_tick_u(g, poz, teraz)
        except bot.Zatrzymano:
            raise
        except Exception as e:                       # obrona nigdy nie wywraca bota
            log(f"PK: błąd {e!r}")
            return False

    def _pk_czaszka(self, s):
        """Obcy gracz z odczytaną groźną czaszką (biała/czerwona z czaszka.py albo pole czaszka/skull/pk): wróg, uciekamy
        zanim zaatakuje (SPEC pkt 2). GM/CM/God/Tutor to nie PK (obsługuje ich stan GRACZ)."""
        if not s.get("gracz") or GM_NAZWA.search(s.get("nazwa") or ""):
            return False
        wl = getattr(self.postac, "nazwa", None)
        if wl and " ".join(str(s.get("nazwa") or "").split()).casefold() == " ".join(str(wl).split()).casefold():
            return False
        return bool(czaszka.czaszka_grozna(s.get("nazwa")) or s.get("czaszka") or s.get("skull") or s.get("pk"))

    def _pk_tick_u(self, g, poz, teraz):
        if self.pk_stan is None and (not PK_OBRONA or not self.zatrzymaj_przy_graczu):
            return False                              # --ignoruj-graczy: żadnej reakcji na graczy, także PK
        det, wr = self._pk_dane()
        wr.odswiez()                                  # ręczna zmiana wrogowie.json (CLI --usun) trafia do działającego bota
        spadek = det.zapisz_hp(g["proc"], teraz)
        if self.ostatnie_stwory is not self.pk_lista_ref:       # lista poprzedniego obiegu (za darmo): pamięć potworów przy nas
            self.pk_lista_ref = self.ostatnie_stwory
            det.zapamietaj_moby(self.ostatnie_stwory, poz, teraz)
        if self.pk_stan == "WALKA":                   # walka z napastnikiem (PVP_WALKA=1): własny tick, bez detekcji wejścia
            return self._pvp_tick(g, poz, teraz, det, wr)
        wazny = float(PK_WROG_WAZNY_H)
        znani = any(wr.znany(r.get("nick"), wazny) for r in wr.dane.values())
        czaszki_wczesniej = self.pk_stan != "DEPO" and any(self._pk_czaszka(s) for s in self.ostatnie_stwory or ())
        if self.pk_stan is None and spadek < PK_SPADEK_PP and not znani and not czaszki_wczesniej:
            if not self.pk_start_sprawdzony:
                self.pk_start_sprawdzony = True
                if wr.karencja_aktywna():             # restart w karencji: nie wracamy na spot, dopóki nie minie
                    return self._pk_start_karencja(wr, g, poz, teraz)
            return False                              # tanie wyjście: bez spadku HP, wrogów i czaszek nie skanujemy
        lista = self.stwory(PK_SKAN_WIEK)
        wlasna = getattr(self.postac, "nazwa", None)
        pomin = lambda s: bool(GM_NAZWA.search(s.get("nazwa") or ""))      # GM/CM/God/Tutor to nie PK (obsługuje je GRACZ)
        atak = det.wykryj_atak(lista, poz, wlasna, spadek, ogien=bool(self._ogien_na(poz)), pomin=pomin, teraz=teraz)
        widoczni = det.wrogowie_w_widoku(lista, poz, wlasna, wr, pomin=pomin)
        czaszki = [] if self.pk_stan == "DEPO" else [s for s in lista if self._pk_czaszka(s)]
        nicki = []
        if atak:
            for s in atak["gracze"]:                  # tylko najbliżsi (prawdopodobny napastnik)
                if self.pk_stan is not None and wr.znany(s["nazwa"], 10.0 / 3600.0):
                    nicki.append(s["nazwa"])          # już uciekamy przed nim, wpis świeży: bez zapisu pliku co obieg
                    continue
                wr.dodaj(s["nazwa"], f"atak: HP -{atak['spadek']:.0f} pp, odl {atak['odl']}", (s["x"], s["y"], s["z"]))
                nicki.append(s["nazwa"])
            if self.pk_stan is None or teraz - getattr(self, "pk_log_atak_ost", -1e9) > 10.0:
                self.pk_log_atak_ost = teraz
                log(f"PK: ATAK gracza z danych: {', '.join(nicki)} (odl {atak['odl']}, HP -{atak['spadek']:.0f} pp "
                    f"do {g['proc']:.0f}%, bez potwora przy nas).")
        for s in czaszki:
            if not wr.znany(s["nazwa"]):
                wr.dodaj(s["nazwa"], "czaszka", (s["x"], s["y"], s["z"]))
                log(f"PK: gracz {s['nazwa']} z groźną czaszką w widoku: wróg, uciekam zanim zaatakuje.")
            if s["nazwa"] not in nicki:
                nicki.append(s["nazwa"])
        for s in widoczni:
            wr.widziany(s["nazwa"])
            if s["nazwa"] not in nicki:
                nicki.append(s["nazwa"])
        if atak or widoczni or czaszki:
            wr.przedluz_karencje(PK_KARENCJA_MIN)
            self.pk_widoczni_ost = teraz
        zagrozenie = bool(atak or widoczni or czaszki)

        if self.stanowisko is not None and zagrozenie:
            return self.stanowisko.pk_reakcja(g, poz, teraz, atak, widoczni, czaszki, nicki, wr)   # 22.10: do PZ, bez pk_stan i wyprawy PK

        if self.pk_stan is None:
            if zagrozenie:
                self.pk_start_sprawdzony = True
                if atak and PVP_WALKA and self._pvp_wejscie(atak, lista, poz, wlasna, pomin, det, wr, g, teraz):
                    return True
                self._pk_start("atak" if atak else ("czaszka" if czaszki else "wróg w widoku"), nicki, g, poz, teraz)
                if PK_SZYBKIE:                        # P6: leczenie w tym samym obiegu co start ucieczki (exura / UH wg progów)
                    self._pk_lecz(g, poz, teraz, lista)
                return True
            if not self.pk_start_sprawdzony:
                self.pk_start_sprawdzony = True
                if wr.karencja_aktywna():
                    return self._pk_start_karencja(wr, g, poz, teraz)
            return False
        if self.pk_stan == "POWROT":
            if zagrozenie:                            # wróg wrócił w drodze na spot: znów do depo
                self._pk_start("wróg w widoku w drodze powrotnej", nicki, g, poz, teraz)
                return True
            w = self.wyprawa
            if w is not None and getattr(w, "w", None) is None and not self.wypad_aktywny:
                # trasa powrotna przerwana z zewnątrz (Wypad.przerwij: ALARM_GM, STOP) bez zdarzenia końca
                self.pk_powrot_proby += 1
                log(f"PK: trasa powrotna na spot przerwana bez zdarzenia końca, wracam do czekania w depo "
                    f"(próba {self.pk_powrot_proby}/{PK_POWROT_PROBY}).")
                self.pk_stan = "DEPO"
                self.pk_proba_ost = teraz
                self.pk_depo_hp_od = None
                self.pauza(0.2, 0.4)
                return True                           # obieg zużyty: bez jednego obiegu zwykłej gry (np. startu wyprawy)
            return False
        if self.pk_stan == "DEPO":
            return self._pk_depo_tick(g, poz, teraz, zagrozenie)
        # "UCIECZKA"
        if self.pk_fallback:
            if not self.ucieczka:                     # stara ucieczka sama się skończyła (zdrowie i brak blokady PK)
                log("PK: koniec ucieczki awaryjnej, wracam do gry.")
                self.pk_stan, self.pk_fallback = None, False
                return False
            w = self.wyprawa
            if teraz - self.pk_proba_ost >= PK_FALLBACK_PONOW_S and w is not None and hasattr(w, "start_pk"):
                self.pk_proba_ost = teraz
                if w.start_pk("ucieczka", teraz):
                    log("PK: trasa do depo zbudowana, przechodzę z ucieczki awaryjnej na marsz do depo.")
                    self.pk_fallback, self.ucieczka = False, False
            return False
        # marsz do depo pod nadzorem wyprawy
        self.ucieczka = False                         # ucieczka z progu HP cofałaby nas w głąb jaskini
        w = self.wyprawa
        if w is not None and getattr(w, "w", None) is None and not self.wypad_aktywny:
            log("PK: wyprawa do depo przestała działać (bez zdarzenia końca), ucieczka awaryjna.")
            self._pk_awaryjna(teraz, "wyprawa do depo zgubiona")
            return False
        return self._pk_lecz(g, poz, teraz, lista)

    # --- walka z napastnikiem (SPEC_walka_pvp_1015): pk_stan "WALKA", tylko gdy PVP_WALKA=1 ---------------------

    def _pvp_zapas(self):
        """(UH, HMM): ilość run w plecakach i pojemniku na runy albo None, gdy plecaków nie da się odczytać."""
        try:
            import runa_klik  # noqa: PLC0415
            if self.runa_klik_env is None:
                self.runa_klik_env = runa_klik.SrodowiskoKlik(self.postac, self.zapytaj, log=lambda t: log(t))
            kont = self.runa_klik_env.kontenery()
            if not kont:
                return None
            return int(runa_klik._ilosc(kont, int(PK_UH_ID))), int(runa_klik._ilosc(kont, int(RUNA_ID)))
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"PVP: odczyt plecaka nieudany ({e!r})")
            return None

    def _pvp_drudzy(self, nick, lista, poz, wlasna, pomin, det, wr):
        """Inni obcy gracze (nie GM, nie my), których traktujemy jak kolejnych napastników: stoją w PVP_DRUGI_ODL, są na liście
        wrogów albo mają groźną czaszkę. -> lista unikalnych nicków."""
        import obrona_pk  # noqa: PLC0415
        k0 = obrona_pk.klucz_nicku(nick)
        pozxy = (poz[0], poz[1])
        wazny = float(PK_WROG_WAZNY_H)
        wynik = {}
        for s in det.obcy(lista, poz, wlasna, pomin):
            k = obrona_pk.klucz_nicku(s.get("nazwa"))
            if k == k0:
                continue
            if self.dystans((s["x"], s["y"]), pozxy) <= PVP_DRUGI_ODL or wr.znany(s.get("nazwa"), wazny) or self._pk_czaszka(s):
                wynik.setdefault(k, s["nazwa"])
        return list(wynik.values())

    def _pvp_rekord(self, typ, g, poz, teraz, nap=None, **d):
        st = self.pvp or {}
        pozxy = (poz[0], poz[1])
        self._tele_poscig(typ, wrog=st.get("nick"), hp=round(g.get("proc", 0.0), 1), mana=g.get("mana"),
                          wrog_hp=None if nap is None else nap.get("hp"),
                          odl=None if nap is None else self.dystans((nap["x"], nap["y"]), pozxy),
                          n_wrogow=st.get("n"), uh=st.get("uh"), hmm=st.get("hmm"), poz=list(poz[:3]),
                          czas_walki=round(teraz - st.get("od", teraz), 1), **d)

    def _pvp_wejscie(self, atak, lista, poz, wlasna, pomin, det, wr, g, teraz):
        """Czy zamiast ucieczki walczymy: PVP_WALKA, dokładnie jeden napastnik w widoku (PVP_MAX_WROGOW), nie GM, HP >= PVP_HP_MIN,
        co najmniej 1 HMM w plecaku. True = pk_stan "WALKA" (obieg zużyty), False = ucieczka jak dotąd (przyczyna w logu)."""
        gracze = atak["gracze"]
        nap = gracze[0]
        powod = None
        if len(gracze) != 1:
            powod = f"{len(gracze)} napastników równocześnie"
        elif GM_NAZWA.search(nap.get("nazwa") or ""):
            powod = "napastnik to GM"
        else:
            drudzy = self._pvp_drudzy(nap["nazwa"], lista, poz, wlasna, pomin, det, wr)
            if 1 + len(drudzy) > PVP_MAX_WROGOW:
                powod = f"napastników {1 + len(drudzy)} (+ {', '.join(drudzy)}), dopuszczam {PVP_MAX_WROGOW}"
            elif g["proc"] < PVP_HP_MIN:
                powod = f"HP {g['proc']:.0f}% < {PVP_HP_MIN}%"
        zapas = None
        if powod is None:
            zapas = self._pvp_zapas()
            if zapas is None:
                powod = "nie odczytałem plecaka (zapas HMM/UH nieznany)"
            elif zapas[1] < 1:
                powod = "brak HMM w plecaku"
        if powod is not None:
            log(f"PVP: nie walczę z {nap.get('nazwa')}: {powod} -> ucieczka.")
            return False
        self.pvp = {"nick": nap["nazwa"], "id": nap["id"], "start": (poz[0], poz[1]), "od": teraz, "hmm_ost": float("-inf"),
                    "hmm_porazki": 0, "niedost_od": None, "ost_hp": nap.get("hp", 100), "uh": zapas[0], "hmm": zapas[1], "n": 1,
                    "poz_ost": (poz[0], poz[1], poz[2]), "hp_start": g["proc"], "strzaly": 0, "uh_uzyc": 0, "exura": 0}
        self.pk_stan = "WALKA"
        self.pk_od = teraz
        self.pk_fallback = False
        self.cel = None
        self.rozprawa = None
        if self.lww:
            self._lww_przerwij("pk", teraz, pilne=True)
        if self.pamiec:
            self._pamiec_koniec("przerwany", "pk", poz)
        self._wypad_reset_klik()
        self.zatrzymaj_klik(poz)
        log(f"PVP: WALKA z {nap['nazwa']} (HP {g['proc']:.0f}%, jego HP {nap.get('hp', '?')}%, odl "
            f"{self.dystans((nap['x'], nap['y']), (poz[0], poz[1]))}, UH {zapas[0]}, HMM {zapas[1]}).")
        if teraz - self.pk_alarm_ost > 20:
            self.pk_alarm_ost = teraz
            try:
                self.alarm(f"PVP: walczę z {nap['nazwa']}")
            except Exception as e:
                log(f"PVP: alarm nie zadziałał ({e!r})")
        self._pk_powiadom("PVP: walka z graczem", f"Walczę z {nap['nazwa']} (HP {g['proc']:.0f}%, UH {zapas[0]}, HMM {zapas[1]}), "
                          f"poz {tuple(poz)}.", "pvp_walka")
        self._pvp_rekord("pvp", g, poz, teraz, nap, akcja="start")
        return True

    def _pvp_koniec(self, wynik, powod, g, poz, teraz, nap=None):
        """Koniec walki. wynik: zabity | uciekl_on | ucieczka | smierc. "ucieczka" = dzisiejsza ucieczka PK (depo, karencja);
        pozostałe wyniki: powrót do normalnej gry (karencja z listy wrogów nadal liczy się dla ponownego startu bota,
        a znany wróg w widoku od razu wywoła ucieczkę)."""
        st = self.pvp or {}
        nick = st.get("nick", "?")
        log(f"PVP: koniec walki z {nick}: {wynik} ({powod}); HMM {st.get('strzaly', 0)}, UH {st.get('uh_uzyc', 0)}, "
            f"HP {st.get('hp_start', 0):.0f}% -> {g.get('proc', 0):.0f}%.")
        self._pvp_rekord("pvp_koniec", g, poz, teraz, nap, wynik=wynik, powod=powod, strzaly_hmm=st.get("strzaly", 0),
                         uh_uzyc=st.get("uh_uzyc", 0), exura=st.get("exura", 0), hp_start=round(st.get("hp_start", 0), 1))
        if wynik != "ucieczka":                       # przy ucieczce powiadamia _pk_start ("PK: uciekam do miasta"): jedno powiadomienie
            self._pk_powiadom(f"PVP: koniec walki ({wynik})", f"{nick}: {powod}. HP {g.get('proc', 0):.0f}%.", "pvp_koniec")
        self.pvp = None
        if wynik == "ucieczka":
            self.pk_alarm_ost = float("-inf")         # walka mogła trwać < 20 s: bez tego _pk_start pominąłby alarm i powiadomienie
            self._pk_start(f"walka PvP przegrana: {powod}", [nick], g, poz, teraz)
        else:
            self.pk_stan = None
            self.pk_fallback = False
        return True

    def _pvp_tick(self, g, poz, teraz, det, wr):
        try:
            return self._pvp_tick_u(g, poz, teraz, det, wr)
        except bot.Zatrzymano:
            raise
        except Exception as e:                       # błąd w walce = ucieczka, nie wiszenie w pół-stanie
            log(f"PVP: błąd {e!r}, ucieczka")
            if self.pvp is not None:
                return self._pvp_koniec("ucieczka", f"błąd {e!r}", g, poz, teraz)
            self.pk_stan = None
            return False

    def _pvp_tick_u(self, g, poz, teraz, det, wr):
        import obrona_pk  # noqa: PLC0415
        st = self.pvp
        if st is None:                                # stan WALKA bez danych walki: nie zostajemy w pół-stanie
            self.pk_stan = None
            return False
        proc = g["proc"]
        pozxy = (poz[0], poz[1])
        self.ucieczka = False                         # ucieczka z progu HP cofałaby nas; w walce decydują progi PVP_*
        self.ustaw_stan("WALKA_PVP", f"{st['nick']}, HP {proc:.0f}%")
        wr.przedluz_karencje(PK_KARENCJA_MIN)
        if g.get("hp", 1) <= 0 or self.dystans(pozxy, st["poz_ost"]) > PVP_SKOK_POL:
            return self._pvp_koniec("smierc", f"HP {g.get('hp')} / skok pozycji {st['poz_ost']} -> {tuple(poz)}", g, poz, teraz)
        st["poz_ost"] = (poz[0], poz[1], poz[2])
        lista = self.stwory(PK_SKAN_WIEK)
        wlasna = getattr(self.postac, "nazwa", None)
        pomin = lambda s: bool(GM_NAZWA.search(s.get("nazwa") or ""))
        k0 = obrona_pk.klucz_nicku(st["nick"])
        kand = [s for s in det.obcy(lista, poz, wlasna, pomin) if obrona_pk.klucz_nicku(s.get("nazwa")) == k0]
        nap = min(kand, key=lambda s: self.dystans((s["x"], s["y"]), pozxy)) if kand else None   # TYLKO ten nick
        drudzy = self._pvp_drudzy(st["nick"], lista, poz, wlasna, pomin, det, wr)
        st["n"] = (1 if nap is not None else 0) + len(drudzy)
        if st.get("zapas_brudny") or teraz - st.get("zapas_t", float("-inf")) >= 1.0:   # plecak: co 1 s albo po strzale/UH
            zapas = self._pvp_zapas()
            st["zapas_t"], st["zapas_brudny"] = teraz, False
            if zapas is not None:
                st["uh"], st["hmm"] = zapas
        if nap is not None:
            st["ost_hp"] = nap.get("hp", 100)
            self.pk_widoczni_ost = teraz
            st["id"] = nap["id"]

        # --- wyjścia z walki ---
        if drudzy and 1 + len(drudzy) > PVP_MAX_WROGOW:
            self._pvp_rekord("pvp", g, poz, teraz, nap, akcja="ucieczka", powod="drugi napastnik")
            return self._pvp_koniec("ucieczka", f"dołączył drugi napastnik: {', '.join(drudzy)}", g, poz, teraz, nap)
        if nap is None or nap.get("hp", 100) <= 0:
            if nap is not None or st["ost_hp"] <= PVP_ZABITY_HP:
                return self._pvp_koniec("zabity", f"napastnik zniknął przy HP {st['ost_hp']}%", g, poz, teraz, nap)
        niedost = nap is None or nap.get("z") != poz[2]
        uh_ok = bool(st["uh"]) and teraz >= self.pk_uh_do         # bez uh_restore: runy nie zależą od tarczy, a moduł UH w walce nie pracuje
        if proc <= PVP_UH_HP and not uh_ok:
            self._pvp_rekord("pvp", g, poz, teraz, nap, akcja="ucieczka", powod="HP krytyczne, brak UH")
            return self._pvp_koniec("ucieczka", f"HP {proc:.0f}% <= {PVP_UH_HP}% i brak UH", g, poz, teraz, nap)
        if not st["hmm"]:
            self._pvp_rekord("pvp", g, poz, teraz, nap, akcja="ucieczka", powod="brak HMM")
            return self._pvp_koniec("ucieczka", "skończyły się HMM", g, poz, teraz, nap)
        if st["hmm_porazki"] >= PVP_HMM_PORAZKI:
            self._pvp_rekord("pvp", g, poz, teraz, nap, akcja="ucieczka", powod="HMM nie działa")
            return self._pvp_koniec("ucieczka", f"{st['hmm_porazki']} nieudane strzały HMM z rzędu", g, poz, teraz, nap)

        # --- leczenie (zawsze przed atakiem) ---
        if proc <= PVP_UH_HP:
            st["uh_uzyc"] += 1
            st["zapas_brudny"] = True
            self._pk_uh_na_siebie(g, poz, teraz)
            self._pvp_rekord("pvp", g, poz, teraz, nap, akcja="lecz_uh")
            return True
        akcje = []
        mana = g.get("mana")
        if proc <= PVP_EXURA_HP and mana is not None and mana >= ZDROWIE_CZAR_KOSZT \
                and teraz - self.czar_ostatni >= CZAR_MIN_PRZERWA_S and teraz - self.pk_exura_ost >= CZAR_MIN_PRZERWA_S:
            self.pk_exura_ost = self.czar_ostatni = self.zdrowie_rzut_ts = teraz
            st["exura"] += 1
            log(f"[PVP] leczenie: {ZDROWIE_CZAR_TEKST} [{ZDROWIE_CZAR_KLAWISZ}] (HP {proc:.0f}%, mana {mana})")
            self.postac.klawisz(ZDROWIE_CZAR_KLAWISZ)  # hotkey nie blokuje obiegu: po exurze nadal strzelamy, gdy HMM gotowe
            akcje.append("lecz_exura")

        # --- atak / podejście: TYLKO napastnik (id z listy po nicku) ---
        if nap is not None and not niedost:
            if self._pvp_w_zasiegu(nap, poz):
                st["niedost_od"] = None
                # tuż nad progiem UH nie blokujemy obiegu ~2 s strzałem (kliknięcia): UH ma być gotowe w następnym obiegu
                if teraz - st["hmm_ost"] >= PVP_HMM_CO_S and proc > PVP_UH_HP + PVP_HMM_STOP_PP:
                    self._pvp_strzal(st, nap, g, poz, teraz)
                    akcje.append("atak_hmm")
            elif self._pvp_podejdz(st, nap, poz):
                st["niedost_od"] = None
                akcje.append("podejscie")
            else:
                niedost = True                        # za daleko i nie możemy podejść (pogoń ograniczona): jak zniknięcie
        if niedost:
            if st["niedost_od"] is None:
                st["niedost_od"] = teraz
            elif teraz - st["niedost_od"] >= PVP_ZNIKL_S:
                return self._pvp_koniec("uciekl_on", f"napastnik poza widokiem/zasięgiem od {PVP_ZNIKL_S:.0f} s", g, poz, teraz, nap)
        self._pvp_rekord("pvp", g, poz, teraz, nap, akcja="+".join(akcje) if akcje else "czeka")
        self.pauza(0.05, 0.15)
        return True

    def _pvp_strzal(self, st, nap, g, poz, teraz):
        import runa_klik  # noqa: PLC0415
        if self.runa_klik_env is None:
            self.runa_klik_env = runa_klik.SrodowiskoKlik(self.postac, self.zapytaj, log=lambda t: log(t))
        st["hmm_ost"] = teraz
        st["zapas_brudny"] = True
        self.aktywnosc_ts = teraz
        try:
            wynik = runa_klik.strzel(self.runa_klik_env,
                                     {"id": nap["id"], "dx": nap["x"] - poz[0], "dy": nap["y"] - poz[1], "hp": nap.get("hp")},
                                     runa_id=int(RUNA_ID), menu_dx=int(RUNA_MENU_DX), menu_dy=int(RUNA_MENU_DY))
        except Exception as e:                       # np. klik poza widokiem: celownik "Use with" mógł zostać uzbrojony
            try:
                self.postac.klawisz("Escape")
            except Exception:
                pass
            if type(e).__name__ == "Zatrzymano":
                raise
            wynik = {"wynik": "blad", "powod": f"wyjątek {e!r}"}
        w, pw = wynik["wynik"], wynik["powod"]
        if w == "ok":
            st["hmm_porazki"] = 0
            st["strzaly"] += 1
            log(f"[PVP] HMM w {nap['nazwa']} (jego HP {nap.get('hp', '?')}%): {pw}")
        elif w == "brak_runy":
            st["hmm"] = 0
            log(f"[PVP] HMM: {pw}")
        else:
            st["hmm_porazki"] += 1
            log(f"[PVP] HMM bez efektu ({w}: {pw}), porażka {st['hmm_porazki']}/{PVP_HMM_PORAZKI}")

    def _pvp_w_zasiegu(self, nap, poz):
        """Napastnik w zasięgu strzału: PVP_ZASIEG i widok mapy klienta (|dx| <= ZASIEG_X, |dy| <= ZASIEG_Y; klik poza widokiem to wyjątek)."""
        dx, dy = abs(nap["x"] - poz[0]), abs(nap["y"] - poz[1])
        return dx <= min(PVP_ZASIEG, ZASIEG_X) and dy <= min(PVP_ZASIEG, ZASIEG_Y)

    def _pvp_podejdz(self, st, nap, poz):
        """Jeden krok w stronę napastnika, ale nie dalej niż PVP_POGON od miejsca startu walki (cel kroku obcięty do tego kwadratu,
        brak obejść). True, gdy się ruszyliśmy."""
        sx, sy = st["start"]
        tx = max(sx - PVP_POGON, min(sx + PVP_POGON, nap["x"]))
        ty = max(sy - PVP_POGON, min(sy + PVP_POGON, nap["y"]))
        if (tx, ty) == (poz[0], poz[1]):
            return False
        dx, dy = tx - poz[0], ty - poz[1]
        proste = [k for k in kierunki_do(poz[0], poz[1], tx, ty) if (bot.KIERUNKI[k][0] * dx > 0 or bot.KIERUNKI[k][1] * dy > 0)]
        for k in proste:
            d = bot.KIERUNKI[k]
            pole = (poz[0] + d[0], poz[1] + d[1], poz[2])
            if self.zablokowane.get(((poz[0], poz[1], poz[2]), k)) or self._ogien_na(pole) or self.dziura_nauczona(pole):
                continue
            if (pole[0], pole[1]) in self._dziury_przy(pole, poz[2]) or self.pole_zmiany_pietra(pole):
                continue                              # dziura z mapy / schody: w pogoni za graczem nie zmieniamy piętra
            self.ruch_strzalki += 1
            if self.postac.krok(k):
                return True
        return False

    def _pk_przy_depo(self, poz):
        """Postać przy polu depo bazy wyprawy (PK_DEPO_PROMIEN, to samo piętro). Nieznane depo = nie."""
        f = getattr(self.wyprawa, "_pole_depo", None)
        try:
            d = f() if f else None
        except Exception:
            d = None
        return bool(d) and d[2] == poz[2] and max(abs(d[0] - poz[0]), abs(d[1] - poz[1])) <= PK_DEPO_PROMIEN

    def _pk_start_karencja(self, wr, g, poz, teraz):
        """Start bota w trakcie karencji (zapisanej w wrogowie.json). Przy depo czekamy, aż minie; poza depo (restart
        w jaskini, np. po awarii) uciekamy do depo jak po ataku - stanie w miejscu bez obrony = śmierć (recenzja 15.10)."""
        if self.stanowisko is not None:
            return self.stanowisko.start_karencja(g, poz, teraz, wr.karencja_pozostalo_s())     # 22.10: stanowisko -> PZ
        if not self._pk_przy_depo(poz):
            log(f"PK: start w karencji (jeszcze {wr.karencja_pozostalo_s() / 60:.0f} min) poza depo {tuple(poz)}: "
                "uciekam do depo.")
            self._pk_start("karencja po restarcie", [], g, poz, teraz)
            return True
        log(f"PK: start w karencji po ataku gracza (jeszcze {wr.karencja_pozostalo_s() / 60:.0f} min): "
            "czekam, nie wracam na spot.")
        self.pk_stan, self.pk_fallback = "DEPO", False
        self.pk_start_wait = True
        self.pk_depo_hp_od = None
        self._pk_powiadom("PK: karencja po restarcie", f"Bot wystartował w karencji PK (jeszcze "
                          f"{wr.karencja_pozostalo_s() / 60:.0f} min), czeka.", "pk_karencja_start")
        return True

    def _pk_start(self, powod, nicki, g, poz, teraz):
        """Wejście w ucieczkę PK: stan, alarm + powiadomienie, trasa do depo (inaczej ucieczka awaryjna)."""
        log(f"PK: UCIEKAM do miasta ({powod}; wrogowie: {', '.join(nicki) or '?'}; HP {g['proc']:.0f}%, poz {tuple(poz)}).")
        powtorka = self.pk_stan is not None
        self.pk_stan = "UCIECZKA"
        self.pk_od = teraz
        self.pk_powrot_proby = 0
        self.cel = None
        self.rozprawa = None
        if self.lww:
            self._lww_przerwij("pk", teraz, pilne=True)
        if self.pamiec:
            self._pamiec_koniec("przerwany", "pk", poz)
        self._wypad_reset_klik()
        self.zatrzymaj_klik(poz)
        if teraz - self.pk_alarm_ost > 20:
            self.pk_alarm_ost = teraz
            tekst = f"gracz atakuje: {', '.join(nicki) or '?'} ({powod}), uciekam do depo"
            try:
                self._alarm_pk("PK: " + tekst)
            except Exception as e:
                log(f"PK: alarm nie zadziałał ({e!r})")
            self._pk_powiadom("PK: uciekam do miasta", f"{tekst}. HP {g['proc']:.0f}%, poz {tuple(poz)}.", "pk_atak")
        w = self.wyprawa
        ok = False
        if w is not None and hasattr(w, "start_pk"):
            ok = bool(w.start_pk("ucieczka", teraz))
        self.pk_proba_ost = teraz
        self.pk_fallback = not ok
        if ok:
            self.ucieczka = False
            log("PK: marsz do depo po zaplanowanej trasie" + (" (ponowny)" if powtorka else "") + ".")
        else:
            self._pk_awaryjna(teraz, "brak planu trasy do depo z tej pozycji")

    def _pk_awaryjna(self, teraz, powod):
        """Brak trasy do depo: stara ucieczka (po trasie łowiska), ale bez powrotu na spot dopóki wróg/karencja."""
        self.pk_stan, self.pk_fallback = "UCIECZKA", True
        if self.wypad_aktywny and self.wyprawa is not None:
            try:
                self.wyprawa.przerwij("PK: ucieczka awaryjna")
                self.wyprawa.zablokowany = False
            except Exception:
                pass
        if not self.ucieczka:
            self.ucieczka_od = teraz
        self.ucieczka = True
        log(f"PK: ucieczka awaryjna po trasie ({powod}); ponawiam budowę trasy do depo co {PK_FALLBACK_PONOW_S:.0f} s.")

    def _pk_wyprawa_koniec(self, rodzaj, wynik, opis, poz):
        """Wołane z Wyprawa._zakoncz_pk po dotarciu albo awarii trasy PK."""
        teraz = self.zegar()
        if rodzaj == "powrot":
            if wynik == "depo":
                log(f"PK: wróciłem na spot {tuple(poz)}, koniec obrony.")
                self.pk_stan, self.pk_fallback = None, False
                self.pk_powrot_proby = 0
                self._wypad_wroc_na_trase(poz)
            else:
                self.pk_powrot_proby += 1
                log(f"PK: powrót na spot nieudany ({opis}), próba {self.pk_powrot_proby}/{PK_POWROT_PROBY}.")
                self.pk_stan = "DEPO"
                self.pk_proba_ost = teraz
                self.pk_depo_hp_od = None
            return
        if wynik == "depo":
            log(f"PK: JESTEM W DEPO {tuple(poz)}, czekam co najmniej do końca karencji ({PK_KARENCJA_MIN} min po ostatnim "
                "zobaczeniu wroga) i aż żaden wróg nie będzie w widoku.")
            self.pk_stan, self.pk_fallback = "DEPO", False
            self.pk_start_wait = False
            self.pk_depo_hp_od = None
            self.pk_powrot_proby = 0
            self._pk_powiadom("PK: jestem w depo", f"Uciekłem przed graczem, stoję w depo {tuple(poz)}; "
                              f"na spot wrócę po karencji {PK_KARENCJA_MIN} min.", "pk_depo")
        else:
            log(f"PK: trasa do depo nie doszła do celu ({opis}), ucieczka awaryjna.")
            self._pk_awaryjna(teraz, f"trasa do depo przerwana: {opis}")

    def _pk_depo_tick(self, g, poz, teraz, zagrozenie):
        """Czekanie w depo: jedzenie (w strefie ochronnej bezpiecznie), potem po karencji i bez wroga w widoku powrót."""
        _, wr = self._pk_dane()
        self.ustaw_stan("PAUZA_PK", f"w depo, karencja jeszcze {wr.karencja_pozostalo_s() / 60:.0f} min")
        if g["hp"] < g["max_hp"] and self.jedzenie_potrzebne(g, teraz, poz):
            self.zjedz(teraz, g)
            return True
        if self.pk_start_wait:                        # start w karencji: po niej koniec obrony (bez trasy powrotnej z depo)
            if zagrozenie or wr.karencja_aktywna():
                self.pauza(1.0, 2.0)
                return True
            log("PK: karencja po restarcie minęła, nikogo w widoku: wracam do normalnej gry.")
            self.pk_stan, self.pk_start_wait = None, False
            return False
        slabe = g["proc"] < self.wznowienie_hp
        if slabe:                                     # bez jedzenia HP nie rośnie: ograniczony czas czekania na zdrowie
            if self.pk_depo_hp_od is None:
                self.pk_depo_hp_od = teraz
            elif teraz - self.pk_depo_hp_od > PK_DEPO_MAX_MIN * 60.0:
                self._pk_powiadom("PK: HP nie rośnie w depo", f"HP {g['proc']:.0f}% od {PK_DEPO_MAX_MIN} min (brak jedzenia?), "
                                  "bot zatrzymany.", "pk_depo_hp")
                self._pk_stop(f"HP {g['proc']:.0f}% w depo od {PK_DEPO_MAX_MIN} min")
                self.pk_depo_hp_od = teraz            # STOP zatrzyma pętlę; bez ponownego zapisu co obieg
        else:
            self.pk_depo_hp_od = None
        if zagrozenie or wr.karencja_aktywna() or slabe:
            self._pk_lecz(g, poz, teraz, [], uh=False)
            self.pauza(1.0, 2.0)
            return True
        if teraz - self.pk_proba_ost < 30.0 and self.pk_powrot_proby > 0:
            self.pauza(1.0, 2.0)
            return True
        if self.pk_powrot_proby >= PK_POWROT_PROBY:
            self._pk_powiadom("PK: nie wrócę sam na spot", "Powrót z depo nie udaje się, bot zatrzymany.", "pk_stop")
            self._pk_stop(f"powrót z depo nieudany {PK_POWROT_PROBY}x")
            self.pauza(2.0, 3.0)
            return True
        w = self.wyprawa
        self.pk_proba_ost = teraz
        if w is not None and hasattr(w, "start_pk") and w.start_pk("powrot", teraz):
            log("PK: karencja minęła, nikogo w widoku: wracam na spot.")
            self.pk_stan = "POWROT"
            return True
        self.pk_powrot_proby += 1
        log(f"PK: nie udało się zbudować trasy powrotnej ({self.pk_powrot_proby}/{PK_POWROT_PROBY}).")
        self.pauza(1.0, 2.0)
        return True

    def _pk_lecz(self, g, poz, teraz, lista, uh=True):
        """Leczenie w marszu do depo: exura z hotkeya (bez postoju, omija blokadę 'wypad'), UH z plecaka na siebie
        przy HP <= PK_UH_HP (uh=False w depo: tam tylko exura). True tylko, gdy kliknięcie UH zużyło obieg."""
        if not PK_LECZ:
            return False
        proc, mana = g.get("proc", 100.0), g.get("mana")
        if proc < 90 and mana is not None and mana >= ZDROWIE_CZAR_KOSZT \
                and teraz - self.czar_ostatni >= CZAR_MIN_PRZERWA_S and teraz - self.pk_exura_ost >= CZAR_MIN_PRZERWA_S:
            self.pk_exura_ost = self.czar_ostatni = self.zdrowie_rzut_ts = teraz
            log(f"[PK] leczenie: {ZDROWIE_CZAR_TEKST} [{ZDROWIE_CZAR_KLAWISZ}] (HP {proc:.0f}%, mana {mana})")
            self.postac.klawisz(ZDROWIE_CZAR_KLAWISZ)  # hotkey nie wymaga postoju: marsz trwa (UH poniżej może zużyć obieg)
        if uh and PK_UH_SZYBKIE:
            if self._pk_uh_szybkie_warunek(proc, teraz):
                return self._pk_uh_na_siebie(g, poz, teraz)
            return False
        if uh and PK_UH_HP > 0 and proc <= PK_UH_HP and teraz >= self.pk_uh_do and teraz - self.pk_uh_ost >= PK_UH_ODSTEP_S \
                and not self.uh_restore:
            return self._pk_uh_na_siebie(g, poz, teraz)
        return False

    def _pk_uh_prog(self):
        """Próg UH w trybie szybkim: PK_UH_HP_SZYBKI, ale nigdy niżej niż 30 (decyzja Karola)."""
        return max(30, int(PK_UH_HP_SZYBKI))

    def _pk_uh_szybkie_warunek(self, proc, teraz):
        """PK_UH_SZYBKIE=1: czy teraz próbować UH. Próg 30% albo predykcja (spadek >= PK_UH_PRED_SPADEK pp w
        PK_UH_PRED_OKNO_S s => już przy HP <= PK_UH_PRED_HP); kolejne próby po odstępie z losowością."""
        h = self.pk_uh_hist
        h.append((teraz, proc))
        while h and teraz - h[0][0] > PK_UH_PRED_OKNO_S + 0.5:
            h.pop(0)
        if self.uh_restore or teraz < self.pk_uh_do or teraz < self.pk_uh_nast:
            return False
        if self._pk_uh_prog() > 0 and proc <= self._pk_uh_prog():
            return True
        if PK_UH_PREDYKCJA and proc <= PK_UH_PRED_HP:
            okno = [p for t, p in h if teraz - t <= PK_UH_PRED_OKNO_S]
            if okno and max(okno) - proc >= PK_UH_PRED_SPADEK:
                return True
        return False

    def _pk_uh_na_siebie(self, g, poz, teraz):
        import runa_klik  # noqa: PLC0415
        if self.runa_klik_env is None:
            self.runa_klik_env = runa_klik.SrodowiskoKlik(self.postac, self.zapytaj, log=lambda t: log(t))
        env = self.runa_klik_env
        proc = g.get("proc", 100.0)
        szybko = bool(PK_UH_SZYBKIE)

        class _Sam:                                   # cel = my: weryfikuje tylko spadek liczby run (hp_celu nie kłamie "znikł")
            def __getattr__(s, n):
                return getattr(env, n)

            def hp_celu(s, ident):
                return 100.0

            def hp_wlasne(s):                         # tryb szybki: wzrost własnego HP też potwierdza użycie
                return self.gracz().get("proc")

        self.pk_uh_ost = teraz
        self.aktywnosc_ts = teraz
        kw = {}
        if szybko:
            ctrl = bool(PK_UH_CTRL) and self.pk_uh_ctrl_porazki < PK_UH_CTRL_PORAZKI
            kw = dict(szybko=True, ctrl=ctrl, rng=self.pk_rng, budzet_s=float(PK_UH_BUDZET_S),
                      weryfikacja_s=float(PK_UH_WERYF_S))
            self.pk_uh_nast = teraz + float(PK_UH_ODSTEP_S) * self.pk_rng.uniform(1.0 - PK_UH_ODSTEP_LOS,
                                                                                   1.0 + PK_UH_ODSTEP_LOS)
        wynik = runa_klik.strzel(_Sam(), {"id": None, "dx": 0, "dy": 0, "hp": None}, runa_id=int(PK_UH_ID),
                                 menu_dx=int(RUNA_MENU_DX), menu_dy=int(RUNA_MENU_DY), **kw)
        w, pw = wynik["wynik"], wynik["powod"]
        if w == "ok":
            self.pk_uh_porazki = 0
            self.pk_uh_ctrl_porazki = 0
            log(f"[PK] UH na siebie (HP {proc:.0f}%): {pw}")
        else:
            self.pk_uh_porazki += 1
            if szybko and kw.get("ctrl") and w == "bez_efektu":
                self.pk_uh_ctrl_porazki += 1
                if self.pk_uh_ctrl_porazki >= PK_UH_CTRL_PORAZKI:
                    log("[PK] UH: Ctrl+klik bez efektu, wracam do menu 'Use with'.")
            log(f"[PK] UH na siebie bez efektu ({w}: {pw}), porażka {self.pk_uh_porazki}/3")
            if szybko and w == "bez_menu" and teraz - self.pk_uh_alarm_ost >= 20.0:
                self.pk_uh_alarm_ost = teraz
                try:
                    self.alarm(f"PK: UH bez menu, HP {proc:.0f}%")
                except bot.Zatrzymano:
                    raise
                except Exception as e:
                    log(f"[PK] alarm UH nie zadziałał ({e!r})")
            krytyczne = szybko and proc <= self._pk_uh_prog()
            if w == "brak_runy" or (self.pk_uh_porazki >= 3 and not krytyczne):
                self.pk_uh_porazki = 0
                self.pk_uh_do = teraz + 60.0
                log("[PK] UH na siebie: przerwa 60 s (brak runy albo 3 porażki).")
            elif self.pk_uh_porazki >= 3:
                self.pk_uh_porazki = 0               # HP krytyczne: natychmiast kolejna próba, bez przerwy 60 s
                self.pk_uh_nast = teraz
                log(f"[PK] UH: 3 porażki, ale HP {proc:.0f}% <= {self._pk_uh_prog()}%: bez przerwy, próbuję dalej.")
        return True

    def uciekaj(self, g, poz):
        self.ustaw_stan("UCIECZKA", f"HP {g['proc']:.0f}% (próg {self.prog_aktualny:.0f}%)")
        teraz = self.zegar()
        if self._jedzenie_czar_tick(g, poz, teraz, odswiez=True):
            return True
        # bez jedzenia HP nie rośnie, a ucieczka kończy się dopiero po regeneracji: jemy także tu,
        # ale tylko gdy nikt nie stoi obok (jedzenie z plecaka to kilka sekund bez reakcji)
        if g["hp"] < g["max_hp"] and teraz - self.hp_wzrost >= CZAS_JEDZENIA and teraz >= self.jedzenie_nie_do:
            try:
                self.ostatnie_stwory = self.stwory()
            except bot.Zatrzymano:
                raise
            except Exception:
                pass
            if self.jedzenie_potrzebne(g, teraz, poz):
                self.zjedz(teraz, g)
                return True
        if teraz - self.ostatni_alarm_hp > ALARM_HP_S:
            self.ostatni_alarm_hp = teraz
            self.alarm(f"niskie HP {g['proc']:.0f}%")
        self.zatrzymaj_klik(poz)       # stary klik mógłby ciągnąć postać dalej, w stronę potworów
        if self.wypad_aktywny and self.wyprawa is not None:
            return self.wyprawa.uciekaj(poz)     # w wypadzie cofamy się po planie wypadu, nie po trasie łowiska
        if self.patrol_byl and not self.patrol_sync_uciecz:
            self.patrol_sync_uciecz = True       # patrol: ucieczka cofa się po trasie łowiska od najbliższego punktu
            self._patrol_sync_idx(poz)
        if self.idx > 0 and (poz[0], poz[1], poz[2]) == self.punkty[self.idx - 1]:
            self.idx -= 1
        if self.idx > 0 and self.punkty[self.idx - 1][2] != poz[2] and self._pietra_wlaczone():
            # poprzedni punkt trasy jest piętro obok (tuż po przejściu): nie wracamy schodami, czekamy na regenerację
            self.pauza(0.5, 1.0)
        elif self.idx > 0:
            cel = self.punkty[self.idx - 1]
            if (poz[0], poz[1]) == (cel[0], cel[1]):
                self.idx -= 1
            else:
                self.krok_do(cel)
        else:
            self.pauza(0.5, 1.0)   # na początku trasy: czekamy na regenerację
        return True

    def _utknieto_na_trasie(self, poz, cel):
        """Okno ~UTKNIECIE_TRASA s w IDZ: ten sam punkt trasy i <= UTKNIECIE_POLA różnych pól
        (albo dystans do punktu poza zasięgiem i nie maleje). True raz na okno (potem nowe okno)."""
        t = self.zegar()
        d = self.dystans(poz, cel) if poz[2] == cel[2] else 999
        o = self.utk_okno
        if o is None or o[1] != self.idx or t - o[4] > UTKNIECIE_LUKA:
            self.utk_okno = [t, self.idx, {tuple(poz)}, d, t, d]
            return False
        o[2].add(tuple(poz))
        o[4] = t
        o[5] = min(o[5], d)
        if t - o[0] < UTKNIECIE_TRASA:
            return False
        stoi = len(o[2]) <= UTKNIECIE_POLA
        daleko = d > ZASIEG_X - 1 and d >= o[3] - 1
        self.utk_okno = None
        return stoi or daleko

    def _odcinek_dojscia(self, poz):
        """(od, do) półotwarty zakres indeksów bieżącego odcinka trasy dojścia: ciągła seria punktów na piętrze
        postaci, zawierająca idx (lub kończąca się tuż przed idx, gdy idx to już następne piętro = przejście w toku).
        Za `do` leży przejście pięter, którego postać jeszcze nie przeszła, więc nic stamtąd nie wolno wybierać
        po utknięciu. Gdy idx jest na innym piętrze niż postać, odcinek = punkty przed idx na piętrze postaci
        (nigdy do przodu). Pusty zakres (0, 0), gdy nic nie pasuje."""
        n = len(self.punkty)
        z = poz[2]
        i = min(self.idx, n - 1)
        if self.punkty[i][2] != z:
            j = i
            while j > 0 and self.punkty[j - 1][2] != z:
                j -= 1
            if j == 0:
                return (0, 0)
            i = j - 1                      # ostatni punkt poprzedniego odcinka na tym piętrze
            do = i + 1
        else:
            do = i
            while do < n and self.punkty[do][2] == z:
                do += 1
        od = i
        while od > 0 and self.punkty[od - 1][2] == z:
            od -= 1
        return (od, do)

    def _droga_po_mapie(self, poz, q):
        """Droga po samej mapie (bez zajętych pól i nauczonych ścian) do punktu q; None, gdy brak."""
        try:
            if self.mapa is None or not self.mapa_zna(poz, q):
                return None
            return self.mapa.droga((poz[0], poz[1], poz[2]), (q[0], q[1]), [], 0, True, limit=MAPA_LIMIT)
        except Exception:
            return None

    def _wroc_na_trase(self, poz):
        """Po utknięciu: najbliższy punkt trasy PO DRODZE (A*, nie Manhattan) i idx na niego.
        True, gdy jakiś punkt jest osiągalny."""
        n = len(self.punkty)
        z = poz[2]
        seg = self._odcinek_dojscia(poz) if (self.dojscie_aktywne and UTKNIECIE_SEGMENT) else None
        kand = sorted((k for k in range(n) if self.punkty[k][2] == z and (seg is None or seg[0] <= k < seg[1])),
                      key=lambda k: self.dystans(poz, self.punkty[k]))[:UTKNIECIE_KAND]
        najlepszy = None
        teraz = self.zegar()
        zakaz = self.__dict__.setdefault("utk_zakaz", {})   # punkt -> do kiedy pomijany po powtórnym utknięciu
        if seg is not None and not kand:
            return False                   # dojście: brak punktu w bieżącym odcinku = zostajemy przy idx (nie skaczemy dalej)
        for k in kand:
            q = self.punkty[k]
            if zakaz.get(k, 0) > teraz:
                continue
            d = [] if tuple(poz[:2]) == q[:2] else self.droga(tuple(poz), q[:2], dlugosc=0)
            if d is None and seg is not None:
                d = self._droga_po_mapie(poz, q)     # dojście: gracze/stwory to przeszkoda chwilowa, nauczone ściany bywają fałszywe
            if d is None:
                continue
            klucz = (len(d), (k - self.idx) % n)
            if najlepszy is None or klucz < najlepszy[0]:
                najlepszy = (klucz, k)
        if najlepszy is None:
            return False
        k = najlepszy[1]
        # drugi raz ten sam punkt (utknięcie w pętli "wracam do punktu X, którego nie da się osiągnąć"):
        # pomijamy go na 3 min i następnym razem idziemy do kolejnego najbliższego
        if k == self.idx and seg is not None:
            # dojście: nie pomijamy punktu na 3 min (to wyrzucało na dalszy odcinek trasy). Czekamy, aż gracze/moby
            # zejdą, i próbujemy następnego punktu TEGO odcinka (do pola przy przejściu pięter włącznie)
            log(f"utknięcie w dojściu: punkt {k} zablokowany, czekam / próbuję dalej w odcinku {seg[0]}-{seg[1] - 1}")
            self.pauza(1.0, 2.5)
            nast = [kk for kk in kand if k < kk < seg[1] and zakaz.get(kk, 0) <= teraz]
            if nast:
                k = min(nast)
                najlepszy = ((self.dystans(poz, self.punkty[k]),), k)
        elif k == self.idx:
            zakaz[k] = teraz + 180.0
            log(f"utknięcie: punkt {k} nieosiągalny mimo bliskości, pomijam go na 3 min")
            alt = sorted((kk for kk in kand if kk != k and zakaz.get(kk, 0) <= teraz),
                         key=lambda kk: (kk - k) % n)
            if alt:
                k = alt[0]
                najlepszy = ((self.dystans(poz, self.punkty[k]),), k)
        self.utkniecia_trasy += 1
        self._d3_nota("inny_punkt")
        log(f"utknięcie, wracam na trasę do punktu {k} (było {self.idx}, droga {najlepszy[0][0]} pól)")
        if self.tele:
            try:
                self.tele.zdarzenie("utkniecie_trasa", poz=list(poz), idx_stary=self.idx, idx=k,
                                    droga=najlepszy[0][0], n=self.utkniecia_trasy)
            except Exception:
                pass
        self.idx = k
        self.klik_j = None
        self.klik_cel = None
        self.trasa_droga = None
        self.nieudane = 0
        self.zablokowane.clear()
        return True

    def _droga_trasy(self, poz, cel):
        """Lista pól drogi A* do punktu trasy `cel`, gdy zachłanny klik/krok w jego stronę
        nie ma sensu (poza zasięgiem kliku albo droga wyraźnie dłuższa niż prosta, np. ściana
        w poprzek); None = idziemy jak dawniej. Droga jest pamiętana, póki jesteśmy na niej."""
        if self.mapa is None or poz[2] != cel[2] or not self.mapa_zna(poz, cel):
            return None
        td = self.trasa_droga
        if td is not None and td[0] == cel and tuple(poz) in td[1] and self.zegar() - td[2] < 10:
            i = td[1].index(tuple(poz))
            return td[1][i + 1:] or None
        prosto = self.dystans(poz, cel)
        d = self.droga(tuple(poz), cel[:2], dlugosc=0)
        if not d:
            return None
        if prosto <= ZASIEG_X - 1 and len(d) <= prosto + TRASA_OBJAZD:
            return None
        self.trasa_droga = (cel, [tuple(poz)] + d, self.zegar())
        return d

    # --- trasa wielopiętrowa (13.10, pietra.py) ---

    def _pietra_wlaczone(self):
        """True, gdy główna pętla trasy ma wykonywać przejścia pięter z trasy (TRASA_PIETRA: 0 wył., 1 zawsze,
        2 tylko gdy trasa ma > 1 piętro). Nigdy w wypadzie (ma własne przejścia) ani bez pozycji."""
        v = TRASA_PIETRA
        if not v or (self.wypad_aktywny and not self.__dict__.get("wypad_dojscie")):
            return False
        if v == 1:
            return True
        c = self._pietra_cache
        if c is None or c[0] != id(self.punkty) or c[1] != len(self.punkty):
            c = self._pietra_cache = (id(self.punkty), len(self.punkty), len({p[2] for p in self.punkty}) > 1)
        return c[2]

    def _trasa_stop_potwor(self, poz):
        """Trasa wielopiętrowa: potwór z naszej listy w promieniu TRASA_STOP_PRZY_POTWORZE_R (to samo piętro, żywy,
        nie ignorowany) wstrzymuje krok trasy i przejścia pięter. Odczyt świeży (cache <= 0,3 s), bo tuż po
        zmianie piętra lista z początku obiegu bywa pusta/stara. True = obieg zużyty (walka w następnym obiegu)."""
        r = TRASA_STOP_PRZY_POTWORZE_R
        if not r or self.__dict__.get("wypad_dojscie"):
            return False                     # dojście wypadu do planu (wypad.py): biegnie, nie czeka na walkę
        try:
            lista = self.stwory(0.3)
        except bot.Zatrzymano:
            raise
        except Exception:
            return False
        self.ostatnie_stwory = lista
        try:
            kand = self._unikanie_filtr(self.kandydaci(lista, poz), poz)
        except Exception:
            return False
        bliskie = [s for s in kand if self.dystans((s["x"], s["y"]), poz) <= r]
        if not bliskie:
            self._trasa_stop_n = 0
            return False
        if self._trasa_stop_n >= TRASA_STOP_MAX:
            return False
        self._trasa_stop_n += 1
        s0 = min(bliskie, key=lambda s: self.dystans((s["x"], s["y"]), poz))
        odl = self.dystans((s0["x"], s0["y"]), poz)
        if self._trasa_stop_n == 1:
            log(f"Trasa wstrzymana: {s0['nazwa']} {odl} pól od nas (piętro {poz[2]}), najpierw walka.")
            self._tele_poscig("trasa_stop_potwor", nazwa=s0["nazwa"], odl=odl, z=poz[2], mobow=len(bliskie))
        self.ustaw_stan("WALKA", f"trasa wstrzymana: {s0['nazwa']} odl {odl}")
        self.pauza(0.05, 0.15)
        return True

    def _pietra_tick(self, poz, cel):
        """Jeden obieg przejścia pięter (True zużyty, False przerwij bota, None = idź starą ścieżką)."""
        if self.pietra is None:
            try:
                import pietra  # noqa: PLC0415
                self.pietra = pietra.Pietra(self, konf=sys.modules[__name__], log=lambda t: log(t))
            except Exception as e:   # moduł nigdy nie wywraca bota
                log(f"debug: pietra.py niedostępne ({e!r}), trasa po staremu")
                return None
        wynik = self.pietra.tick(poz, cel)
        if wynik is not None:
            self.ruch_pietra_t = self.zegar()      # R0b: obieg zużyty przez przejście pięter (przyczyna stania "schody")
        return wynik

    def _pietra_zawroc(self, poz):
        """Po nieudanym przejściu: trasa w drugą stronę od punktu przed przejściem (inne schody / spokojne pole)."""
        if self.__dict__.get("_w_segmencie"):
            # patrol po miejscach (odcinek, nie trasa): nie odwracamy odcinka, patrol wybierze inne miejsce/przejście
            self.__dict__["pietra_zawrot_seg"] = True
            self.klik_j = self.klik_cel = self.trasa_droga = None
            self.utk_okno = None
            log("Przejście pięter nieudane w patrolu: porzucam to miejsce, wybiorę inne przejście.")
            return
        n = len(self.punkty)
        if n < 2:
            return
        self.punkty.reverse()
        self.idx = (n - (self.idx - 1) % n) % n
        self.__dict__["utk_zakaz"] = {}
        self.klik_j = self.klik_cel = self.trasa_droga = None
        self.utk_okno = None
        log(f"Przejście pięter nieudane: trasa w drugą stronę od punktu {self.idx}.")

    # --- zakaz zmiany piętra w pościgu (12.10) ---

    def _zakaz_pol(self, z):
        """Pola (x, y) piętra z, na których krok zmienia piętro: pola oznaczone na mapie (schody/dziura w dół)
        oraz ich odpowiedniki piętro niżej (x, y z piętra z-1 = schody w górę). Liczone raz na piętro, w okolicy
        trasy i miejsc; brak mapy albo błąd = pusty zbiór."""
        c = self._zakaz.get(z)
        if c is not None:
            return c
        c = set()
        try:
            if self.mapa is not None:
                if self._bbox is None:
                    if TRYB_PATROL:
                        self._patrol_wczytaj()          # miejsca (zachód) też w obszarze zakazu
                    pts = [(p[0], p[1]) for p in self.punkty] + [(p[0], p[1]) for p in list(self.znane)[:3000]]
                    for m in (self.miejsca or []):
                        pts.append((m["x"], m["y"]))
                    if pts:
                        xs = [p[0] for p in pts]
                        ys = [p[1] for p in pts]
                        self._bbox = (max(0, min(xs) - 25), max(0, min(ys) - 25),
                                      min(max(xs) + 25, min(xs) + 700), min(max(ys) + 25, min(ys) + 700))
                    else:
                        self._bbox = (0, 0, -1, -1)
                x0, y0, x1, y1 = self._bbox
                flagi = self.mapa.flagi
                for pz in (z, z - 1):
                    if pz < 0:
                        continue
                    for x in range(x0, x1 + 1):
                        for y in range(y0, y1 + 1):
                            f = flagi(x, y, pz)
                            if f & 1 and f & 2:        # WIDZIANE i BEZ_DROGI = schody/dziura
                                c.add((x, y))
        except Exception as e:   # zakaz nigdy nie wywraca bota
            log(f"debug: zakaz zmiany piętra: {e!r}")
        self._zakaz[z] = c
        return c

    def _zakaz_aktywny(self):
        return bool(POSCIG_BEZ_ZMIANY_PIETRA) and not self.wypad_aktywny and self.mapa is not None

    def _wp(self):
        """wpadniecie.Wpadniecie (leniwie; None, gdy moduł niedostępny). Wczytuje nauczone dziury przy pierwszym użyciu."""
        w = self.wpadniecie
        if w is None:
            try:
                import wpadniecie  # noqa: PLC0415
                w = self.wpadniecie = wpadniecie.Wpadniecie(self, konf=sys.modules[__name__], log=lambda t: log(t))
                if w.dziury:
                    log(f"Wpadnięcie: wczytano {len(w.dziury)} nauczonych dziur ({sorted(w.dziury)[:5]}).")
            except Exception as e:   # moduł nigdy nie wywraca bota
                log(f"debug: wpadniecie.py niedostępne ({e!r})")
                w = self.wpadniecie = False
        # 21.10 (F3): pokrętła z na_zywo.json przychodzą PO pierwszym _wp(), więc podpinamy przy każdym obiegu (raz, test tożsamości)
        if w and LOOT_BEZ_DRABIN and hasattr(self.loot, "DRABINY") and self.loot.DRABINY is not w.drabiny:
            try:
                self.loot.DRABINY = w.wczytaj_drabiny()      # ten sam zbiór: nauka drabiny w trakcie gry od razu działa w loocie
                log(f"Loot: {len(w.drabiny)} pól drabin bez Ctrl+klik (LOOT_BEZ_DRABIN).")
            except Exception as e:   # drabiny nie mogą wyłączyć całego wpadnięcia
                log(f"debug: drabiny dla lootu niedostępne ({e!r})")
                self.loot.DRABINY = w.drabiny
        if w and LOOT_BEZ_DZIUR and hasattr(self.loot, "POLE_ZAKAZANE"):
            hak = self.__dict__.get("_loot_hak")
            if hak is None:
                hak = self._loot_hak = self._loot_pole_zakazane
            if self.loot.POLE_ZAKAZANE is not hak:
                self.loot.POLE_ZAKAZANE = hak           # 23.10: loot pyta cavebota o pola dziur przed każdym Ctrl+klikiem
        return w or None

    def _loot_pole_zakazane(self, x, y, z, glowne=False):
        """LOOT_BEZ_DZIUR: True = loot nie robi Ctrl+klik w pole (x, y, z), bo postać by tam weszła i spadła.
        Zakazane: pole z listy dziur (nauczone + trasy/dziury_omijaj.json, niezależnie od DZIURY_NAUCZONE) oraz pole, które mapa
        uznaje za ścianę (dziura z flagą 5 wygląda jak ściana: odchyd 23.10, (32354,32131,z8)), z wyjątkiem pola zwłok (`glowne`:
        stwór tam zginął, więc mapa się myli). Nie wywraca lootu: błąd = False."""
        if not LOOT_BEZ_DZIUR:
            return False
        try:
            w = self.wpadniecie or None
            if w and (x, y, z) in w.dziury:
                return True
            if not glowne and self.mapa is not None and self.mapa.przechodnie(x, y, z) is False:
                return True
        except Exception:
            return False
        return False

    def dziura_nauczona(self, pole):
        """True, gdy pole (x, y, z) to nauczona dziura (DZIURY_NAUCZONE): ściana dla dróg i kroków."""
        if not DZIURY_NAUCZONE:
            return False
        w = self._wp()
        return bool(w and (pole[0], pole[1], pole[2]) in w.dziury) if len(pole) > 2 else False

    def _dziura_w_trasie(self, pole):
        """22.10: nauczona dziura jest zaplanowanym zejściem bieżącej trasy: trasa ma (x, y, z) i zaraz po nim (x, y, z+1)
        (dojście trolle_edron_z9z schodzi dziurą (33081,31742,z8), w którą 15.10 bot wpadł przy polowaniu na z8)."""
        pk = [tuple(p[:3]) for p in (self.punkty or []) if len(p) > 2]
        cel = (pole[0], pole[1], pole[2])
        return any(a == cel and b == (cel[0], cel[1], cel[2] + 1) for a, b in zip(pk, pk[1:]))

    def _dziury_lista(self, start, cel):
        """Nauczone dziury piętra start[2] w prostokącie start-cel (+ margines) jako lista (x, y, z) dla A*."""
        if not DZIURY_NAUCZONE:
            return []
        w = self._wp()
        return w.lista(start[2], start, cel) if w else []

    def pole_zmiany_pietra(self, pole):
        """True, gdy wejście na to pole (x, y, z) zmieniłoby piętro, a zmiana jest zakazana (poza wypadem);
        nauczona dziura jest zakazana zawsze (DZIURY_NAUCZONE)."""
        if len(pole) > 2 and self.dziura_nauczona(pole):
            return True
        if not self._zakaz_aktywny():
            return False
        return (pole[0], pole[1]) in self._zakaz_pol(pole[2])

    def _zakaz_lista(self, start, cel):
        """Pola zmiany piętra w prostokącie start-cel (+ margines drogi) jako lista (x, y, z) dla A*
        oraz nauczone dziury (wpadniecie.py)."""
        return self._zakaz_pietra_lista(start, cel) + self._dziury_lista(start, cel)

    def _zakaz_pietra_lista(self, start, cel):
        if not self._zakaz_aktywny():
            return []
        z = start[2]
        c = self._zakaz_pol(z)
        if not c:
            return []
        x0, x1 = sorted((start[0], cel[0]))
        y0, y1 = sorted((start[1], cel[1]))
        m = 30
        return [(x, y, z) for (x, y) in c if x0 - m <= x <= x1 + m and y0 - m <= y <= y1 + m]

    # --- patrol po miejscach (12.10) ---

    def _patrol_init(self):
        self.miejsca = None            # lista miejsc z trasy/miejsca.json (leniwie); [] = niedostępne
        self.patrol = None             # bieżąca wizyta: {"m","faza","seg","idx",...}
        self.sweep_trasa = None        # trasa zachodu z nowe_miejsca.json (leniwie); [] = brak
        self.sweep_ostatni = float("-inf")   # czas początku ostatniego sweepu
        self.sweep_wschod = 99         # wizyt w nie-B od ostatniego sweepu (99 = pierwszy sweep bez czekania)
        self.patrol_ost = {}           # id -> czas ostatniej wizyty
        self.patrol_t0 = None          # czas startu patrolu (miejsca bez wizyty liczą od niego)
        self.patrol_historia = []      # id odwiedzonych miejsc (najnowsze na końcu)
        self.patrol_blok = {}          # id -> do kiedy miejsce nie jest losowane
        self.patrol_fallback_do = float("-inf")
        self.patrol_wylaczony = False  # True: model zmienił trasę ręcznie albo patrol się nie wczytał
        self.patrol_byl = False        # poprzedni obieg szedł patrolem (synchronizacja idx przy powrocie na trasę)
        self.patrol_zabicia = 0        # zabicia od startu (KPI na wizytę)
        self.patrol_wizyty = 0
        self.patrol_stat = {}          # id -> {"wizyty","zabicia","dojscie_s","na_miejscu_s"}
        self.patrol_pierwszy = True    # następny wybór = najbliższe miejsce (start, powrót z wypadu)
        self.patrol_sync_uciecz = False
        self.przejscia = []            # plik miejsc: schody/dziury między piętrami (patrz generuj_miejsca_troll.py)
        self.laczniki = []             # plik miejsc: ręczne przejścia po tym samym piętrze (mapa ich nie widzi)
        self.patrol_przejscie_blok = {}  # id przejścia/łącznika -> do kiedy nie jest planowane
        self.patrol_gracze_pam = {}    # nick -> (x, y, z, czas): gdzie ostatnio widziano obcego gracza
        self.patrol_gniazdo_cache = None  # (czas, wynik) odczytu HP/many do warunku gniazda
        self.patrol_graf = None        # plik miejsc: {"komp": {pole: nr}, "odl": {(pole, pole): długość}} (offline, A*)
        self._bbox = None
        self._zakaz = {}

    def _patrol_wczytaj(self):
        if self.miejsca is not None:
            return self.miejsca
        self.miejsca = []
        try:
            d = json.loads((KATALOG_TRAS / PATROL_PLIK).read_text())
            for m in d["miejsca"]:
                self.miejsca.append({"id": m["id"], "x": int(m["x"]), "y": int(m["y"]), "z": int(m["z"]),
                                     "udzial": float(m.get("udzial_zabic") or 0.0), "zrodlo": m.get("zrodlo"),
                                     "waga": (float(m["waga"]) if m.get("waga") is not None else None),
                                     "mobow": (int(m["mobow"]) if m.get("mobow") is not None else None),
                                     "nazwa": m.get("nazwa")})
            self.przejscia, self.laczniki = self._patrol_przejscia(d)
            self.patrol_graf = self._patrol_graf(d.get("graf"))
            if self.patrol_t0 is None:
                self.patrol_t0 = self.zegar()
            log(f"Patrol: wczytano {len(self.miejsca)} miejsc z {PATROL_PLIK}.")
        except Exception as e:
            self.miejsca = []
            log(f"Patrol: nie wczytano {PATROL_PLIK} ({e!r}), jadę po trasie.")
        return self.miejsca

    @staticmethod
    def _patrol_graf(g):
        """"graf" z pliku miejsc: {"wezly": [{"pole": [x,y,z], "komp": nr}], "odl": [[i, j, długość]]} -> słowniki
        po polach; None = brak (planer liczy odcinki A* leniwie)."""
        try:
            if not g:
                return None
            w = [tuple(int(v) for v in n["pole"]) for n in g["wezly"]]
            komp = {w[i]: n["komp"] for i, n in enumerate(g["wezly"])}
            odl = {}
            for i, j, n in g["odl"]:
                odl[(w[i], w[j])] = odl[(w[j], w[i])] = int(n)
            return {"komp": komp, "odl": odl}
        except (KeyError, TypeError, ValueError, IndexError):
            return None

    @staticmethod
    def _patrol_przejscia(d):
        """Z pliku miejsc: przejścia pięter i łączniki jako krawędzie grafu dróg. Krawędź = {"id", "z" (piętro wejścia),
        "wej" (pole, do którego idziemy A*), "kroki" (pola po wejściu aż do wyjścia, możliwie inne piętro),
        "wyj" (pole po przejściu), "koszt", "gniazdo", "pieta"}. Błędny wpis jest pomijany."""
        kraw, laczniki = [], []
        t = lambda q: (int(q[0]), int(q[1]), int(q[2]))
        for e in d.get("przejscia") or []:
            try:
                gora, dol = t(e["wejscie_gora"]), t(e["wejscie_dol"])
                w_dol, w_gora = t(e["wyjscie_dol"]), t(e["wyjscie_gora"])
                gn = bool(e.get("gniazdo"))
                kraw.append({"id": e["id"] + ":w_dol", "z": gora[2], "wej": gora, "kroki": [w_dol], "wyj": w_dol,
                             "koszt": PATROL_PRZEJSCIE_KOSZT, "gniazdo": gn, "pieta": True})
                kraw.append({"id": e["id"] + ":w_gore", "z": dol[2], "wej": dol, "kroki": [w_gora], "wyj": w_gora,
                             "koszt": PATROL_PRZEJSCIE_KOSZT, "gniazdo": False, "pieta": True})
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        for e in d.get("laczniki") or []:
            try:
                kr = [t(q) for q in e["kroki"]]
                if not kr:
                    continue
                for a, b, k in ((t(e["od"]), t(e["do"]), kr), (t(e["do"]), t(e["od"]), None)):
                    if k is None:
                        if e.get("dwa_kierunki", True) is False:
                            continue
                        k = list(reversed([a_ for a_ in kr[:-1]])) + [b]    # odwrotnie: od końca do początku
                        k = [x for x in k if x != a]
                    laczniki.append({"id": e["id"] + (":tam" if k is kr else ":z_powrotem"), "z": a[2], "wej": a,
                                     "kroki": k, "wyj": b, "koszt": len(k), "gniazdo": False, "pieta": False})
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        return kraw, laczniki

    def _patrol_aktywny(self):
        if not TRYB_PATROL and PATROL_PLIK != "miejsca.json" and not getattr(self, "_patrol_knob_ostrz", False):
            # --trasa patrol:NAZWA ustawia plik miejsc, a TRYB_PATROL=0 (na_zywo.json) po cichu wraca do pętli trasy
            self._patrol_knob_ostrz = True
            log(f"Patrol: pokrętło TRYB_PATROL=0 (na_zywo.json) wyłącza patrol po {PATROL_PLIK}, idę pętlą trasy; "
                f"ustaw TRYB_PATROL=1, żeby patrolować miejsca.")
        if not TRYB_PATROL or self.patrol_wylaczony or self.mapa is None:
            return False
        return bool(self._patrol_wczytaj())

    def patrol_wylacz(self, powod):
        if not self.patrol_wylaczony:
            log(f"Patrol wyłączony: {powod}.")
        self.patrol_wylaczony = True
        self.patrol = None

    def _patrol_reset(self, pierwszy=True):
        """Po wypadzie / zmianie trasy: porzuć wizytę, kolejny wybór = najbliższe miejsce."""
        self.patrol = None
        self.patrol_pierwszy = pierwszy

    def _patrol_tele(self, typ, **d):
        if self.tele:
            try:
                self.tele.zdarzenie(typ, **d)
            except Exception:
                pass

    def _patrol_sync_idx(self, poz):
        """Idx trasy łowiska na najbliższy punkt (to samo piętro): ucieczka i powrót z patrolu idą po trasie."""
        if not self.punkty:
            return
        self.idx = min(range(len(self.punkty)),
                       key=lambda i: (self.punkty[i][2] != poz[2],
                                      abs(self.punkty[i][0] - poz[0]) + abs(self.punkty[i][1] - poz[1])))
        self.klik_j = None
        self.klik_cel = None
        self.trasa_droga = None
        self.utk_okno = None

    def _patrol_gracze(self, z):
        u = self.unikanie
        if u is None or not u.aktywne or not u.gracze:
            return []
        return [(g["x"], g["y"]) for g in u.gracze if g.get("z") == z]

    @staticmethod
    def _patrol_baza(m):
        """Waga bazowa miejsca: ręczne pole "waga" z miejsca.json (jeśli jest), inaczej udział zabić z dolnym progiem."""
        if m.get("waga") is not None:
            return m["waga"]
        return max(m["udzial"], PATROL_WAGA_MIN)

    def _patrol_pamietaj_graczy(self):
        """Pamięć graczy (Karol 13.10: zapamiętywać, w której części jest gracz, i go unikać): ostatnia pozycja
        każdego widzianego obcego gracza (unikanie.py) przez PATROL_GRACZ_PAM_S s zniechęca do miejsc w pobliżu."""
        if not PATROL_GRACZ_PAM:
            return
        u = self.unikanie
        if u is None or not u.gracze:
            return
        t = self.zegar()
        for g in u.gracze:
            self.patrol_gracze_pam[g.get("nazwa") or g.get("id") or "?"] = (g["x"], g["y"], g["z"], t)
        for k in [k for k, v in self.patrol_gracze_pam.items() if t - v[3] > PATROL_GRACZ_PAM_S]:
            del self.patrol_gracze_pam[k]

    def _patrol_gracz_czynnik(self, m):
        """Mnożnik wagi miejsca: PATROL_GRACZ_PAM_KARA, gdy w ostatnich PATROL_GRACZ_PAM_S s widziano obcego gracza
        w PATROL_GRACZ_PAM_R polach od miejsca (inne piętro: pierwiastek z kary). 1.0 = bez kary."""
        if not PATROL_GRACZ_PAM or not self.patrol_gracze_pam:
            return 1.0
        t = self.zegar()
        f = 1.0
        for x, y, z, tt in self.patrol_gracze_pam.values():
            if t - tt > PATROL_GRACZ_PAM_S or max(abs(m["x"] - x), abs(m["y"] - y)) > PATROL_GRACZ_PAM_R:
                continue
            f = min(f, PATROL_GRACZ_PAM_KARA if z == m["z"] else PATROL_GRACZ_PAM_KARA ** 0.5)
        return f

    def _patrol_mnoznik(self, m):
        """Mnożnik wagi: liczba mobów naraz w miejscu (bezpieczeństwo druida) i pamięć graczy."""
        f = self._patrol_gracz_czynnik(m)
        mob = m.get("mobow")
        if mob is not None and PATROL_MOBY_KARA > 0 and mob > PATROL_MOBY_BEZP:
            f /= 1.0 + PATROL_MOBY_KARA * (mob - PATROL_MOBY_BEZP)
        return f

    def _patrol_gniazdo_ok(self):
        """Warunek wejścia do gniazda (miejsce/przejście z >= PATROL_GNIAZDO_MOBOW mobami naraz): HP i mana
        >= progi (odczyt cache 2 s). Brak odczytu = nie."""
        if not PATROL_GNIAZDO_HP and not PATROL_GNIAZDO_MANA:
            return True
        t = self.zegar()
        c = self.patrol_gniazdo_cache
        if c is not None and t - c[0] < 2.0:
            return c[1]
        try:
            g = self.gracz()
            ok = g.get("proc", 100.0) >= PATROL_GNIAZDO_HP
            if PATROL_GNIAZDO_MANA and g.get("max_mana"):
                ok = ok and 100.0 * g.get("mana", 0) / g["max_mana"] >= PATROL_GNIAZDO_MANA
        except bot.Zatrzymano:
            raise
        except Exception:
            ok = False
        self.patrol_gniazdo_cache = (t, ok)
        return ok

    def _patrol_waga(self, m, d, historia):
        w = self._patrol_baza(m) / (1.0 + d / PATROL_ODL_SKALA) * self._patrol_mnoznik(m)
        if PATROL_CZAS_MAX > 0 and PATROL_CZAS_SKALA_S > 0 and self.patrol_t0 is not None:
            # im dawniej odwiedzone, tym większa waga: równomierne pokrycie w czasie
            od = self.patrol_ost.get(m["id"], self.patrol_t0)
            w *= 1.0 + min(max(self.zegar() - od, 0.0) / PATROL_CZAS_SKALA_S, PATROL_CZAS_MAX)
        k = next((i for i, h in enumerate(reversed(historia)) if h == m["id"]), None)
        if k is not None:
            if k < PATROL_BYLO_WYKLUCZ:
                return 0.0
            if k < 2 * PATROL_BYLO_WYKLUCZ:
                w *= PATROL_BYLO_KARA
        return w

    def _patrol_kandydaci(self, poz, pomin=None):
        teraz = self.zegar()
        gracze = self._patrol_gracze(poz[2])
        pietra = self._patrol_pietra_ok()
        zajete = self._patrol_koord_zajete()     # miejsca zajęte przez inne instancje ({} gdy PATROL_KOORD=0)
        wynik = []
        for m in self.miejsca or []:
            if (m["z"] != poz[2] and not pietra) or m["id"] == pomin \
                    or self.patrol_blok.get(m["id"], float("-inf")) > teraz:
                continue
            if zajete and self._patrol_koord_koliduje(m, zajete):
                continue
            if m["z"] == poz[2] and gracze \
                    and min(max(abs(m["x"] - gx), abs(m["y"] - gy)) for gx, gy in gracze) < UNIKANIE_PUNKT_D:
                continue
            if m.get("mobow") is not None and m["mobow"] >= PATROL_GNIAZDO_MOBOW and not self._patrol_gniazdo_ok():
                continue
            if PATROL_GRACZ_PAM_KARA <= 0 and self._patrol_gracz_czynnik(m) <= 0:
                continue
            wynik.append((m, abs(m["x"] - poz[0]) + abs(m["y"] - poz[1]) + PATROL_PIETRO_KARA * abs(m["z"] - poz[2])))
        return wynik

    def _patrol_pietra_ok(self):
        """Miejsca na innych piętrach są kandydatami: plik miejsc ma przejścia, pokrętło i trasa wielopiętrowa włączone."""
        return bool(PATROL_PIETRA and TRASA_PIETRA and self.przejscia
                    and not (self.wypad_aktywny and not self.__dict__.get("wypad_dojscie")))

    # --- droga do miejsca: A* po piętrze albo graf (przejścia pięter + ręczne łączniki z pliku miejsc) ---

    def _patrol_a(self, od, do, memo):
        k = (od, do)
        if k not in memo:
            if od[:2] == do[:2]:
                memo[k] = []
            else:
                try:
                    memo[k] = self.droga(od, do[:2], dlugosc=0)
                except bot.Zatrzymano:
                    raise
                except Exception as e:
                    log(f"Patrol: błąd drogi {od} -> {do}: {e!r}")
                    memo[k] = None
        return memo[k]

    def _patrol_droga(self, poz, m, uzyte=None):
        """Droga (lista pól (x,y,z) bez pola startu) z poz do miejsca m albo None.
        To samo piętro i A* widzi drogę: zwykłe A*. Inaczej (inne piętro albo A* nie widzi drogi, np. błąd mapy)
        najtańsza droga po grafie: krawędzie to przejścia pięter i ręczne łączniki z pliku miejsc (kroki zapisane
        w pliku, niezależne od mapy), a odległości między ich końcami bierzemy z "graf" pliku (liczone offline tym
        samym A*), więc w czasie gry A* liczymy tylko dojście z bieżącego pola i składanie wybranej drogi.
        Pierwsze pole wejścia przejścia pięter jest zawsze w drodze (pietra.py bierze je jako punkt `a`).
        `uzyte` (lista, opcjonalnie) dostaje id użytych krawędzi."""
        start = tuple(poz[:3])
        cel = (m["x"], m["y"], m["z"])
        memo = {}
        if start[2] == cel[2]:
            d = self._patrol_a(start, cel, memo)
            if d is not None or not (self.laczniki or self._patrol_pietra_ok()):
                return d
        elif not self._patrol_pietra_ok():
            return None
        zle = set()                    # krawędzie wykluczone po nieudanym składaniu drogi
        for _ in range(3):
            plan = self._patrol_plan(start, cel, memo, zle)
            if plan is None:
                return None
            ops, uz = plan
            seg, cur, blad = [], start, None
            for e in ops:
                d = self._patrol_a(cur, e["wej"], memo)
                if d is None:
                    blad = e
                    break
                seg += [tuple(q) for q in d]
                if e["pieta"] and (not seg or seg[-1] != e["wej"]):
                    seg.append(e["wej"])        # pole `a` zawsze w drodze: pietra.py bierze je z punktu przed przejściem
                seg += list(e["kroki"])
                cur = e["wyj"]
            if blad is None:
                d = self._patrol_a(cur, cel, memo)
                if d is not None:
                    if uzyte is not None:
                        uzyte.extend(uz)
                    return seg + [tuple(q) for q in d]
                if not ops:
                    return None
                blad = ops[-1]
            zle.add(blad["id"])
        return None

    def _patrol_plan(self, start, cel, memo, zle):
        """Dijkstra po grafie: -> (lista krawędzi, id) albo None. Odcinki między końcami z pliku mają znane długości;
        dojście z `start` i brakujące odcinki sprawdzamy A* leniwie (dolna granica = Chebyshev)."""
        teraz = self.zegar()
        graf = self.patrol_graf
        gn_ok = None
        kraw = {}
        pieta = set()
        for e in self.przejscia + self.laczniki:
            if e["id"] in zle or self.patrol_przejscie_blok.get(e["id"], float("-inf")) > teraz:
                continue
            if PATROL_DRZWI and not e["pieta"] and self._drzwi_na_krokach(e):
                continue                   # R1c: łącznik przez odpuszczone drzwi
            if e["pieta"]:
                if not self._patrol_pietra_ok():
                    continue
                pieta.add(e["id"])
            if e["gniazdo"]:
                if gn_ok is None:
                    gn_ok = self._patrol_gniazdo_ok()
                if not gn_ok:
                    continue
            kraw.setdefault(e["z"], []).append(e)
        zle_komp = set()               # komponenty, do których z `start` nie ma drogi (A* się nie powiodło)

        def odcinek(a, b):
            """-> (dlugosc, pewna) albo None, gdy drogi nie ma."""
            if a[:2] == b[:2] and a[2] == b[2]:
                return 0, True
            if graf is not None:
                d = graf["odl"].get((a, b))
                if d is not None:
                    return d, True
                ka, kb = graf["komp"].get(a), graf["komp"].get(b)
                if a == start:
                    if kb is not None and kb in zle_komp:
                        return None
                elif ka is not None and kb is not None and ka != kb:
                    return None
            return max(abs(a[0] - b[0]), abs(a[1] - b[1])), False

        pq = [(0, 0, 1, (start, [], [], 0))]
        odw = {}
        licznik = 1

        def dodaj(prio, rodzaj, dane):
            nonlocal licznik
            licznik += 1
            heapq.heappush(pq, (prio, licznik, rodzaj, dane))

        while pq:
            prio, _, rodzaj, dane = heapq.heappop(pq)
            if rodzaj == 0:                               # gotowa droga
                return dane
            if rodzaj == 2:                               # leniwa weryfikacja odcinka A*
                loc, e, ops, uz, koszt = dane
                cz = cel if e is None else e["wej"]
                d = self._patrol_a(loc, cz, memo)
                if d is None:
                    if graf is not None and loc == start:
                        k = graf["komp"].get(cz)
                        if k is not None:
                            zle_komp.add(k)
                    continue
                k2 = koszt + len(d)
                if e is None:
                    dodaj(k2, 0, (ops, uz))
                else:
                    dodaj(k2 + e["koszt"], 1, (e["wyj"], ops + [e], uz + [e["id"]], k2 + e["koszt"]))
                continue
            loc, ops, uz, koszt = dane
            if odw.get(loc, float("inf")) <= koszt:
                continue
            odw[loc] = koszt
            if loc[2] == cel[2]:
                o = odcinek(loc, cel)
                if o is not None:
                    if o[1]:
                        dodaj(koszt + o[0], 0, (ops, uz))
                    else:
                        dodaj(koszt + o[0], 2, (loc, None, ops, uz, koszt))
                    if o[1]:
                        continue
            if sum(1 for u in uz if u in pieta) >= PATROL_PRZEJSCIA_MAX:
                continue
            for e in kraw.get(loc[2], []):
                o = odcinek(loc, e["wej"])
                if o is None:
                    continue
                if o[1]:
                    dodaj(koszt + o[0] + e["koszt"], 1, (e["wyj"], ops + [e], uz + [e["id"]], koszt + o[0] + e["koszt"]))
                else:
                    dodaj(koszt + o[0] + e["koszt"], 2, (loc, e, ops, uz, koszt))
        return None

    def _patrol_koord(self):
        """Koordynator miejsc (miejsca_koord.py); None, gdy PATROL_KOORD=0 (domyślnie) albo się nie wczytał."""
        if not PATROL_KOORD:
            return None
        k = getattr(self, "_koord", None)
        if k is None:
            try:
                import miejsca_koord  # noqa: PLC0415
                k = self._koord = miejsca_koord.Koordynator()
            except Exception as e:
                log(f"Patrol: koordynator miejsc niedostępny ({e!r}), jadę bez niego.")
                k = self._koord = False
        return k or None

    def _patrol_koord_zajete(self):
        """Cudze rezerwacje (klucz -> wpis); przy okazji odświeża moje. Błąd = {} (bot nie staje przez koordynatora)."""
        k = self._patrol_koord()
        if k is None:
            return {}
        try:
            k.odswiez()
            return k.zajete()
        except Exception as e:
            log(f"Patrol: koordynator miejsc: błąd odczytu {e!r}, jadę bez niego.")
            return {}

    @staticmethod
    def _patrol_koord_koliduje(m, zajete):
        import miejsca_koord  # noqa: PLC0415
        klucz, poz = miejsca_koord.klucz_miejsca(m), (m["x"], m["y"], m["z"])
        return any(miejsca_koord.konflikt(klucz, poz, PATROL_KOORD_PROMIEN, k2, r2) for k2, r2 in zajete.items())

    def _patrol_koord_rezerwuj(self, m):
        k = self._patrol_koord()
        if k is None:
            return True
        try:
            import miejsca_koord  # noqa: PLC0415
            return k.rezerwuj(miejsca_koord.klucz_miejsca(m), (m["x"], m["y"], m["z"]), PATROL_KOORD_PROMIEN)
        except Exception as e:
            log(f"Patrol: koordynator miejsc: błąd rezerwacji {e!r}, jadę bez niego.")
            return True

    def _patrol_nowy(self, poz, m, powod, waga=None):
        """Wizyta w miejscu m: droga A* z bieżącej pozycji; None (i blokada miejsca), gdy drogi nie ma.
        Metoda wyboru (20.10, pole `metoda` telemetrii patrol_cel) z self._wybor_meta, ustawianego tylko w _patrol_wybierz:
        "respawn" (mapa obecności, PATROL_RESPAWN=1; wartość i pewność do logu), "waga" (losowanie wg wag), "najblizsze"
        (pierwszy wybór); poza _patrol_wybierz (np. po walce, tuż obok) "inna"."""
        meta = self._wybor_meta
        metoda, wartosc, pewnosc = meta.get("metoda", "inna"), meta.get("wartosc"), meta.get("pewnosc")
        teraz = self.zegar()
        tgt = (m["x"], m["y"])
        uzyte = []
        try:
            if tuple(poz[:2]) == tgt and poz[2] == m["z"]:
                seg = []
            else:
                seg = self._patrol_droga(poz, m, uzyte)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"Patrol: błąd drogi do m{m['id']}: {e!r}")
            seg = None
        if seg is None:
            self.patrol_blok[m["id"]] = teraz + PATROL_BLOK_S
            log(f"Patrol: brak drogi do m{m['id']} ({m['x']},{m['y']}), pomijam na {PATROL_BLOK_S:.0f} s.")
            return None
        if not self._patrol_koord_rezerwuj(m):     # inna instancja zajęła to miejsce w międzyczasie
            self.patrol_blok[m["id"]] = teraz + PATROL_BLOK_S
            log(f"Patrol: miejsce m{m['id']} zajęte przez inną instancję, pomijam na {PATROL_BLOK_S:.0f} s.")
            return None
        p = {"m": m, "faza": "dojscie", "seg": [tuple(q) for q in seg], "idx": 0, "t_wyb": teraz, "tick": None,
             "t_marsz": 0.0, "t_dotarl": None, "zab_wyb": self.patrol_zabicia, "zab_dotarl": None, "do": None,
             "replan": teraz, "obchod": False, "powod": powod, "obchod_t": 0.0}
        p["seg_xy"] = {tuple(q[:3]) for q in p["seg"]}
        p["limit"] = PATROL_LIMIT_S[0] + PATROL_LIMIT_S[1] * len(p["seg"])
        p["przejscia"] = list(uzyte)
        if uzyte:
            p["limit"] += PATROL_PRZEJSCIE_LIMIT_S * len(uzyte)
            powod += ", przez " + ",".join(uzyte)
        self._wypad_reset_klik()
        wtxt = f", waga {waga:.3f}" if waga is not None else ""
        if metoda == "respawn" and wartosc is not None:
            wtxt = f", wartość {wartosc:.4f}" + (f", pewność {pewnosc:.2f}" if pewnosc is not None else "")
        if self._patrol_sweep_buduj(p, poz, teraz):
            powod += ", sweep zachodu"
        log(f"Patrol: cel m{m['id']} ({m['x']},{m['y']}) {powod}, droga {len(p['seg'])} pól{wtxt}.")
        cien = self._patrol_cien_pola(poz, m)      # 15.10: tryb cienia (puste {}, gdy wyłączony albo brak wyniku)
        self._patrol_tele("patrol_cel", id=m["id"], x=m["x"], y=m["y"], powod=powod, droga=len(p["seg"]),
                          waga=round(waga, 4) if waga is not None else None, poz=list(poz[:3]), metoda=metoda, **cien)
        return p

    def _sweep_wczytaj(self):
        if self.sweep_trasa is None:
            self.sweep_trasa = []
            try:
                d = json.loads((KATALOG_TRAS / PATROL_SWEEP_PLIK).read_text())
                self.sweep_trasa = [(int(q[0]), int(q[1]), int(q[2])) for q in d]
            except Exception as e:
                log(f"Patrol: brak trasy sweepu {PATROL_SWEEP_PLIK} ({e!r}), zachód bez przeczesywania.")
        return self.sweep_trasa

    def _sweep_odcinek(self, od, trasa, i0, z):
        """Droga: od `od` do trasa[i0], potem cała reszta trasy (kolejne punkty przez A*, gdy nie sąsiadują). None = brak drogi."""
        seg = []
        akt = tuple(od[:2])
        byly = {akt}
        for q in trasa[i0:]:
            if q[:2] in byly:
                continue             # odnogi nagranej trasy (tam i z powrotem): każde pole raz
            byly.add(q[:2])
            sasiad = max(abs(q[0] - akt[0]), abs(q[1] - akt[1])) <= 1
            if sasiad and q[0] != akt[0] and q[1] != akt[1] and self.mapa is not None:
                # skos przez róg ściany: nie ufamy nagraniu, droga A* (bez ścinania rogów)
                try:
                    sasiad = (self.mapa.przechodnie(q[0], akt[1], z) is True
                              and self.mapa.przechodnie(akt[0], q[1], z) is True)
                except Exception:
                    pass
            if sasiad:
                if akt != q[:2]:
                    seg.append(q)
            else:
                try:
                    d = self.droga((akt[0], akt[1], z), q[:2], dlugosc=0)
                except bot.Zatrzymano:
                    raise
                except Exception:
                    d = None
                if d is None:
                    if not seg and q is trasa[i0]:
                        return None      # pierwszy skok bez drogi: sweep nie ma wejścia
                    continue             # dziurę w trasie omijamy
                seg.extend(tuple(x) for x in d)
                byly.update(tuple(x[:2]) for x in d)
            akt = q[:2]
        return seg

    def _patrol_sweep_buduj(self, p, poz, teraz):
        """Dla celu = miejsce zachodnie (źródło B): dojście przez całą nagraną trasę zachodu (od bliższego końca)
        zamiast najkrótszą drogą do jednego punktu. True, gdy p dostał sweep."""
        m = p["m"]
        if not PATROL_SWEEP or m.get("zrodlo") != "B" or p.get("sweep"):
            return False
        if teraz - self.sweep_ostatni < PATROL_SWEEP_MIN_S or self.sweep_wschod < PATROL_SWEEP_WSCHOD_MIN:
            return False
        trasa = self._sweep_wczytaj()
        if len(trasa) < 5 or trasa[0][2] != poz[2]:
            return False
        # wejście: bliższy z dwóch końców trasy (całość przeczesana od niego do drugiego końca)
        dk = lambda q: abs(q[0] - poz[0]) + abs(q[1] - poz[1])
        tr = list(trasa) if dk(trasa[0]) <= dk(trasa[-1]) else list(reversed(trasa))
        seg = self._sweep_odcinek(poz, tr, 0, poz[2])
        if not seg:
            return False
        p["sweep"] = {"trasa": tr, "nast": 0}
        p["seg"] = seg
        p["seg_xy"] = {tuple(q[:3]) for q in seg}
        p["idx"] = 0
        p["limit"] = PATROL_LIMIT_S[0] + PATROL_LIMIT_S[1] * len(seg)
        p["koniec"] = tr[-1]
        self.sweep_ostatni = teraz
        self.sweep_wschod = 0
        self._wypad_reset_klik()
        return True

    def _patrol_sweep_zalicz(self, p, teraz):
        """Po sweepie: miejsca B leżące <= PATROL_SWEEP_BLISKO od trasy liczą się jako odwiedzone."""
        tr = p["sweep"]["trasa"]
        ids = []
        for mm in self.miejsca or []:
            if mm.get("zrodlo") != "B" or mm["z"] != tr[0][2] or mm["id"] == p["m"]["id"]:
                continue
            if any(max(abs(mm["x"] - q[0]), abs(mm["y"] - q[1])) <= PATROL_SWEEP_BLISKO for q in tr):
                ids.append(mm["id"])
        for i in ids:
            self.patrol_historia.append(i)
            self.patrol_ost[i] = teraz
            st = self.patrol_stat.setdefault(i, {"wizyty": 0, "zabicia": 0, "dojscie_s": 0.0, "na_miejscu_s": 0.0})
            st["wizyty"] += 1
            self.patrol_wizyty += 1
        del self.patrol_historia[:-40]
        log(f"Patrol: sweep zachodu zakończony, zaliczone miejsca: {sorted(ids + [p['m']['id']])}.")

    def _patrol_wybierz(self, poz, pomin=None):
        """Wybór następnego miejsca (dzisiejsza metoda: _patrol_wybierz_dzis). Opakowanie tylko pilnuje, by wynik cienia
        (_cien_wybor, liczony w środku na tych samych kandydatach) nie przeżył tego wywołania."""
        self._cien_wybor = None
        self._wybor_meta = {}
        try:
            return self._patrol_wybierz_dzis(poz, pomin)
        finally:
            self._cien_wybor = None
            self._wybor_meta = {}

    def _patrol_wybierz_dzis(self, poz, pomin=None):
        """Losuje następne miejsce (waga: udział zabić z dolnym progiem, odległość, kara za niedawne wizyty);
        None, gdy żadne nie jest osiągalne. Pierwszy wybór po starcie / wypadzie: najbliższe miejsce."""
        kand = self._patrol_kandydaci(poz, pomin)
        if not kand:
            return None
        if self.patrol_pierwszy:
            self.patrol_pierwszy = False
            self._patrol_cien_licz(kand, poz)      # tryb cienia: tylko odczyt, bez losowania i bez A*
            for m, d in sorted(kand, key=lambda md: md[1])[:6]:
                self._wybor_meta = {"metoda": "najblizsze"}
                p = self._patrol_nowy(poz, m, "najbliższe")
                if p is not None:
                    return p
            return None
        hist = self.patrol_historia
        if PATROL_RUNDA:
            # 14.10: runda bez powtórzeń: losujemy tylko spośród jeszcze nieodwiedzonych w tej rundzie
            runda = self.__dict__.setdefault("patrol_runda", set())
            wszystkie = {m["id"] for m, _d in kand}
            if wszystkie and wszystkie <= runda:
                self.__dict__["patrol_runda_nr"] = self.__dict__.get("patrol_runda_nr", 0) + 1
                log(f"Patrol: runda {self.patrol_runda_nr} zakończona ({len(runda)} miejsc), nowa runda.")
                runda.clear()
            kand = [(m, d) for m, d in kand if m["id"] not in runda] or kand
        pula = [(m, d) for m, d in kand if d >= PATROL_ODL_MIN] or kand
        if PATROL_RESPAWN:
            p, pula = self._patrol_respawn_wybor(poz, pula, hist)       # 20.10: krok 3, pokrętło PATROL_RESPAWN=1
            if p is not None:
                return p
            if not pula:
                return None
        else:
            self._patrol_cien_licz(pula, poz)      # tryb cienia: ci sami kandydaci co losowanie (tylko odczyt, bez losowania i bez A*)
        for _ in range(6):
            wagi = [self._patrol_waga(m, d, hist) for m, d in pula]
            if sum(wagi) <= 0:
                # za mało miejsc na zakaz niedawnych: wykluczamy tylko ostatnie
                ost = hist[-1] if hist else None
                wagi = [0.0 if m["id"] == ost else self._patrol_baza(m) / (1.0 + d / PATROL_ODL_SKALA)
                        * self._patrol_mnoznik(m) for m, d in pula]
                if sum(wagi) <= 0:
                    wagi = [1.0 for _ in pula]
            los = random.random() * sum(wagi)
            akum, i = 0.0, len(pula) - 1
            for j, w in enumerate(wagi):
                akum += w
                if los < akum:
                    i = j
                    break
            m, d = pula[i]
            self._wybor_meta = {"metoda": "waga"}
            p = self._patrol_nowy(poz, m, "losowo", waga=wagi[i] / (sum(wagi) or 1.0))
            if p is not None:
                return p
            pula = [(mm, dd) for mm, dd in pula if mm["id"] != m["id"]]
            if not pula:
                break
        return None

    def _patrol_respawn_wybor(self, poz, pula, historia):
        """20.10 (SPEC_patrol_respawn_1015 krok 3, PATROL_RESPAWN=1): cel patrolu wg mapy obecności (obecnosc.wybierz na
        drogach po grafie pliku miejsc, bez losowania). `pula` to kandydaci już po wszystkich filtrach dzisiejszego patrolu
        (_patrol_kandydaci: blokady przy graczu, patrol_blok, rezerwacje PATROL_KOORD, gniazdo; PATROL_RUNDA; PATROL_ODL_MIN),
        więc metoda wybiera tylko spośród nich. Dodatkowo, jak waga: bez PATROL_BYLO_WYKLUCZ ostatnio odwiedzonych miejsc
        i bez miejsc przy niedawno widzianym graczu (_patrol_gracz_czynnik < 1, PATROL_GRACZ_PAM_*).
        Zwraca (wizyta | None, pula): wizyta gotowa, gdy metoda ma zdanie (cel_respawn nie None, droga istnieje); None =
        metoda bez zdania / brak danych / puste → wołający losuje po staremu z zwróconej puli (bez miejsc, do których
        nie ma drogi). Błąd mapy = brak zdania, nigdy wyjątek."""
        pula = list(pula)
        ostatnie = {h for h in historia[-PATROL_BYLO_WYKLUCZ:]} if PATROL_BYLO_WYKLUCZ > 0 else set()
        for _ in range(6):
            kand = [(m, d) for m, d in pula if m["id"] not in ostatnie and self._patrol_gracz_czynnik(m) >= 1.0]
            self._patrol_cien_licz(kand, poz)
            cw = self._cien_wybor
            cel = cw["cel"] if cw else None
            if cel is None:
                return None, pula
            m = next((mm for mm, _d in kand if mm["id"] == cel), None)
            if m is None:
                return None, pula
            self._wybor_meta = {"metoda": "respawn", "wartosc": cw["wartosci"].get(cel), "pewnosc": cw["pewnosc"]}
            p = self._patrol_nowy(poz, m, "respawn")
            if p is not None:
                return p, pula
            pula = [(mm, dd) for mm, dd in pula if mm["id"] != cel]     # brak drogi / rezerwacja: miejsce zablokowane, następna próba
            if not pula:
                break
        self._cien_wybor = None      # ostatni wynik dotyczył puli sprzed usunięć: dzisiejszy wybór idzie bez pól cienia
        return None, pula

    def _patrol_zawrot(self, p, poz, tgt, odl, teraz):
        """15.10: miejsce spawnu razem z okolicą PATROL_ZAWROT_PROMIEN jest w widoku (to samo piętro) i od PATROL_ZAWROT_S
        nie widać przy nim żadnego celu: True = zaliczamy wizytę bez dojścia. Stwory z pamięci klienta są znane w całym
        widoku, także za ścianą; stary wpis przy miejscu tylko wstrzymuje zawrót (ostrożnie)."""
        r = PATROL_ZAWROT_PROMIEN
        if (not PATROL_ZAWROT or p.get("sweep") or poz[2] != tgt[2] or odl <= PATROL_PRZYJECIE
                or abs(tgt[0] - poz[0]) + r > WIDOK_X or abs(tgt[1] - poz[1]) + r > WIDOK_Y):
            p["pusto_od"] = None
            return False
        for st in self.ostatnie_stwory or []:
            if st.get("gracz") or st.get("hp", 100) <= 0 or st.get("z", tgt[2]) != tgt[2]:
                continue
            if self.potwory is not None and str(st.get("nazwa", "")).casefold() not in self.potwory:
                continue
            if max(abs(st["x"] - tgt[0]), abs(st["y"] - tgt[1])) <= r:
                p["pusto_od"] = None
                return False
        if p.get("pusto_od") is None:
            p["pusto_od"] = teraz
            return False
        return teraz - p["pusto_od"] >= PATROL_ZAWROT_S

    def _patrol_dotarl(self, p, poz, teraz, widok=False):
        m = p["m"]
        p["faza"] = "postoj"
        p["t_dotarl"] = teraz
        p["zab_dotarl"] = self.patrol_zabicia
        p["do"] = teraz + random.uniform(*PATROL_POSTOJ)
        self.patrol_historia.append(m["id"])
        self.__dict__.setdefault("patrol_runda", set()).add(m["id"])
        del self.patrol_historia[:-40]
        self.patrol_ost[m["id"]] = teraz
        if p.get("sweep"):
            self._patrol_sweep_zalicz(p, teraz)
        elif m.get("zrodlo") != "B":
            self.sweep_wschod += 1
        if widok:
            p["do"], p["obchod"], p["zawrot"] = teraz, True, True     # bez postoju i obchodu
            log(f"Patrol: m{m['id']} ({m['x']},{m['y']}) pusty w widoku ({max(abs(poz[0] - m['x']), abs(poz[1] - m['y']))} pól przed), zawracam.")
            return
        log(f"Patrol: na miejscu m{m['id']} ({m['x']},{m['y']}), rozglądam się {p['do'] - teraz:.1f} s.")

    def _patrol_zakoncz(self, p, powod):
        """Podsumowanie wizyty (KPI): czas dojścia, czas na miejscu, zabicia w drodze i na miejscu."""
        teraz = self.zegar()
        m = p["m"]
        dotarl = p["t_dotarl"] is not None
        dojscie = (p["t_dotarl"] if dotarl else teraz) - p["t_wyb"]
        na_miejscu = (teraz - p["t_dotarl"]) if dotarl else 0.0
        zab_droga = (p["zab_dotarl"] if dotarl else self.patrol_zabicia) - p["zab_wyb"]
        zab_miejsce = (self.patrol_zabicia - p["zab_dotarl"]) if dotarl else 0
        if dotarl:
            self.patrol_wizyty += 1
            st = self.patrol_stat.setdefault(m["id"], {"wizyty": 0, "zabicia": 0, "dojscie_s": 0.0, "na_miejscu_s": 0.0})
            st["wizyty"] += 1
            st["zabicia"] += zab_miejsce
            st["dojscie_s"] += dojscie
            st["na_miejscu_s"] += na_miejscu
        log(f"Patrol: wizyta m{m['id']} {'#' + str(self.patrol_stat[m['id']]['wizyty']) if dotarl else 'nieudana'}"
            f" ({powod}): dojście {dojscie:.0f} s, na miejscu {na_miejscu:.0f} s, "
            f"zabicia na miejscu {zab_miejsce}, w drodze {zab_droga}.")
        self._patrol_tele("patrol_wizyta", id=m["id"], x=m["x"], y=m["y"], dotarl=dotarl, powod=powod,
                          dojscie_s=round(dojscie, 1), na_miejscu_s=round(na_miejscu, 1),
                          zabicia_miejsce=zab_miejsce, zabicia_droga=zab_droga, wizyta=self.patrol_wizyty)
        if dotarl and self.patrol_wizyty % PATROL_STAT_CO == 0:
            top = sorted(self.patrol_stat.items(), key=lambda kv: -kv[1]["zabicia"])[:6]
            log("Patrol KPI (" + str(self.patrol_wizyty) + " wizyt): " + ", ".join(
                f"m{i}: {s['wizyty']}x {s['zabicia']} zab" for i, s in top))

    def _patrol_blokuj_przejscie(self, p, poz, teraz):
        """Nieudane przejście/łącznik: blokujemy użytą krawędź leżącą na naszym piętrze najbliżej nas."""
        e_by_id = {e["id"]: e for e in self.przejscia + self.laczniki}
        kand = [e_by_id[i] for i in p.get("przejscia") or [] if i in e_by_id and e_by_id[i]["z"] == poz[2]]
        if not kand:
            return
        e = min(kand, key=lambda e: max(abs(e["wej"][0] - poz[0]), abs(e["wej"][1] - poz[1])))
        self.patrol_przejscie_blok[e["id"]] = teraz + PATROL_PRZEJSCIE_BLOK_S
        log(f"Patrol: przejście {e['id']} zawiodło, nie planuję go przez {PATROL_PRZEJSCIE_BLOK_S:.0f} s.")

    def _patrol_obchod(self, poz, m):
        """Krótki obchód: losowe pole w promieniu PATROL_OBCHOD_PROMIEN od miejsca, droga PATROL_OBCHOD_DROGA pól."""
        z = poz[2]
        for _ in range(8):
            dx = random.randint(-PATROL_OBCHOD_PROMIEN, PATROL_OBCHOD_PROMIEN)
            dy = random.randint(-PATROL_OBCHOD_PROMIEN, PATROL_OBCHOD_PROMIEN)
            if not dx and not dy:
                continue
            pole = (m["x"] + dx, m["y"] + dy, z)
            try:
                if self.mapa.przechodnie(*pole) is not True or self.pole_zmiany_pietra(pole):
                    continue
                d = self.droga(tuple(poz), pole[:2], dlugosc=0)
            except bot.Zatrzymano:
                raise
            except Exception:
                continue
            if d and PATROL_OBCHOD_DROGA[0] <= len(d) <= PATROL_OBCHOD_DROGA[1]:
                return [tuple(q) for q in d]
        return None

    def _idz_segment(self, seg, idx):
        """Jeden obieg zwykłego chodzenia (_idz_trasa) po odcinku `seg` zamiast po trasie łowiska.
        -> (wynik _idz_trasa, nowy idx w odcinku); stan zostaje IDZ."""
        zapas = (self.punkty, self.idx, self.przebyte, self.okrazenie, self.otwarta, self.pominiete)
        self.punkty, self.idx, self.otwarta, self.stan = list(seg) + [seg[-1]] * 10, idx, True, "IDZ"
        self.przebyte = 0
        self.__dict__["_w_segmencie"] = True
        try:
            wynik = self._idz_trasa()
            return wynik, min(self.idx, len(seg) - 1)
        finally:
            self.__dict__["_w_segmencie"] = False
            self.punkty, self.idx, self.przebyte, self.okrazenie, self.otwarta, self.pominiete = zapas
            self.stan = "IDZ"

    def _patrol_gracz_zmiana(self, p, poz, teraz):
        """PATROL_GRACZ_ZMIEN (Karol 17.10): obcy gracz w PATROL_GRACZ_ZMIEN_R polach od nas albo od celu patrolu = od razu
        zmiana respa, bez czekania na debounce unikania. Miejsca w PATROL_GRACZ_PAM_R od gracza (to samo piętro) dostają
        blokadę na PATROL_GRACZ_ZMIEN_BLOK_S s, bieżąca wizyta się kończy, kolejny wybór idzie na respa dalej od gracza.
        Nowa wizyta (dict) albo None (bez zmiany; gdy nie ma gdzie iść, blokady są cofane i zostajemy przy unikaniu)."""
        if not PATROL_GRACZ_ZMIEN or p is None:
            return None
        u = self.unikanie
        if u is None or not u.gracze or teraz - self.patrol_zmiana_ost < PATROL_GRACZ_ZMIEN_PAUZA_S:
            return None
        m = p["m"]
        gr = [g for g in u.gracze if g.get("z") == poz[2]]
        blisko = [g for g in gr if max(abs(g["x"] - poz[0]), abs(g["y"] - poz[1])) <= PATROL_GRACZ_ZMIEN_R
                  or (m["z"] == g["z"] and max(abs(g["x"] - m["x"]), abs(g["y"] - m["y"])) <= PATROL_GRACZ_ZMIEN_R)]
        if not blisko:
            return None
        ids = [mm["id"] for mm in self.miejsca or []
               if mm["z"] == poz[2]
               and any(max(abs(mm["x"] - g["x"]), abs(mm["y"] - g["y"])) <= PATROL_GRACZ_PAM_R for g in blisko)]
        if m["id"] not in ids:
            return None          # gracz jest blisko nas, ale nasz cel leży daleko od niego: idziemy dalej, bez blokad
        stare = {i: self.patrol_blok.get(i, float("-inf")) for i in ids}
        for i in ids:
            self.patrol_blok[i] = max(stare[i], teraz + PATROL_GRACZ_ZMIEN_BLOK_S)
        self.patrol_zmiana_ost = teraz       # także przy braku alternatywy: bez ponawiania co obieg
        if not self._patrol_kandydaci(poz, m["id"]):
            self.patrol_blok.update(stare)   # nie ma dokąd uciec: wizyta trwa dalej, zostaje zwykłe unikanie
            return None
        self._patrol_zakoncz(p, "gracz blisko: zmiana respa")
        nowy = self._patrol_wybierz(poz, m["id"])
        if nowy is None:
            self.patrol_blok.update(stare)
            self.patrol = None
            return None
        zablok = ids
        log(f"Patrol: gracz {blisko[0].get('nazwa')} blisko ({max(abs(blisko[0]['x'] - poz[0]), abs(blisko[0]['y'] - poz[1]))} pól), "
            f"zmieniam respa m{m['id']} ({m['x']},{m['y']}) -> m{nowy['m']['id']} ({nowy['m']['x']},{nowy['m']['y']}) "
            f"(miejsc zablokowanych: {len(zablok)}).")
        self._patrol_tele("patrol_gracz_zmiana", gracz=blisko[0].get("nazwa"), z_miejsca=m["id"], na_miejsce=nowy["m"]["id"],
                          zablokowane=len(zablok))
        return nowy

    def _idz_patrol(self):
        """Jeden obieg patrolu po miejscach. True/False jak _idz_trasa; None = brak miejsca, jedziemy trasą."""
        teraz = self.zegar()
        poz = tuple(self.postac.pozycja())
        if teraz < self.patrol_fallback_do:
            return None
        p = self.patrol
        if p is not None and p["m"]["z"] != poz[2] and not self._patrol_pietra_ok():
            self._patrol_zakoncz(p, "zmiana piętra")
            p = self.patrol = None
        if p is None:
            p = self.patrol = self._patrol_wybierz(poz)
            if p is None:
                self.patrol_fallback_do = teraz + PATROL_FALLBACK_S
                self._patrol_sync_idx(poz)
                self.patrol_pierwszy = True
                log(f"Patrol: brak osiągalnego miejsca, jadę trasą {PATROL_FALLBACK_S:.0f} s.")
                if WPADNIECIE:
                    # 15.10: kieszeń (np. start bota po upadku z z8 do zamkniętego rope spotu na z9): żaden punkt trasy/miejsce
                    # na tym piętrze nie jest osiągalny A* = wyjście jak po wykrytym upadku (lina/plan po mapie), nie ślepy marsz
                    wp = self._wp()
                    try:
                        if wp is not None and wp.z_kieszeni(poz, teraz):
                            self.patrol_fallback_do = float("-inf")
                            return True
                    except bot.Zatrzymano:
                        raise
                    except Exception as e:
                        log(f"debug: wpadniecie.z_kieszeni błąd {e!r}")
                return None
        luka = p["tick"] is not None and teraz - p["tick"] > PATROL_LUKA_S
        dt = min(teraz - p["tick"], 2.0) if p["tick"] is not None else 0.0
        p["tick"] = teraz
        nowy_p = self._patrol_gracz_zmiana(p, poz, teraz)
        if nowy_p is not None:
            p = self.patrol = nowy_p
            p["tick"] = teraz
            luka = False
        elif self.patrol is None:
            # wizyta zakończona, a nowego miejsca nie wybrano (blokady cofnięte): zwykły wybór, bez kroku trasą na boku
            p = self.patrol = self._patrol_wybierz(poz)
            if p is None:
                return None
            p["tick"] = teraz
            luka = False
        for _ in range(5):
            m = p["m"]
            tgt = tuple(p["koniec"]) if p.get("sweep") else (m["x"], m["y"], m["z"])
            odl = max(abs(poz[0] - tgt[0]), abs(poz[1] - tgt[1]))
            if p["faza"] == "dojscie":
                sw = p.get("sweep")
                if sw:
                    # postęp sweepu: kolejny punkt trasy to pierwszy, którego jeszcze nie minęliśmy
                    for j in range(sw["nast"], len(sw["trasa"])):
                        q = sw["trasa"][j]
                        if max(abs(poz[0] - q[0]), abs(poz[1] - q[1])) <= 1:
                            sw["nast"] = j + 1
                if luka and sw and PATROL_POWROT_DO_CELU:
                    luka = False       # po walce wracamy do przerwanego sweepu, nie zmieniamy celu
                if luka:
                    luka = False
                    inne = [(mm, d) for mm, d in self._patrol_kandydaci(poz, m["id"])
                            if max(abs(mm["x"] - poz[0]), abs(mm["y"] - poz[1])) <= PATROL_BLISKO
                            and mm["id"] not in self.patrol_historia[-PATROL_BYLO_WYKLUCZ:]]
                    if (inne and PATROL_POWROT_DO_CELU and odl <= PATROL_POWROT_MAX_ODL
                            and self.patrol_blok.get(m["id"], float("-inf")) <= teraz):
                        # wracamy do pierwotnego celu; zmiana tylko na miejsce <= 2 pola, leżące bliżej celu niż my
                        inne = [(mm, d) for mm, d in inne
                                if max(abs(mm["x"] - poz[0]), abs(mm["y"] - poz[1])) <= 2
                                and max(abs(mm["x"] - tgt[0]), abs(mm["y"] - tgt[1])) < odl]
                    if inne and odl > PATROL_PRZYJECIE:
                        mm = min(inne, key=lambda md: md[1])[0]
                        np_ = self._patrol_nowy(poz, mm, "po walce, tuż obok")
                        if np_ is not None:
                            self._patrol_zakoncz(p, "zmiana celu po walce")
                            p = self.patrol = np_
                            p["tick"] = teraz
                            continue
                gracze = self._patrol_gracze(poz[2]) if poz[2] == tgt[2] else []
                if gracze and min(max(abs(tgt[0] - gx), abs(tgt[1] - gy)) for gx, gy in gracze) < UNIKANIE_PUNKT_D:
                    self.patrol_blok[m["id"]] = teraz + PATROL_BLOK_S
                    self._patrol_zakoncz(p, "gracz przy miejscu")
                    p = self.patrol = self._patrol_wybierz(poz, m["id"])
                    if p is None:
                        return None
                    p["tick"] = teraz
                    continue
                if odl <= PATROL_PRZYJECIE and poz[2] == tgt[2]:
                    self._patrol_dotarl(p, poz, teraz)
                    continue
                if self._patrol_zawrot(p, poz, tgt, odl, teraz):
                    self._patrol_dotarl(p, poz, teraz, widok=True)
                    continue
                p["t_marsz"] += dt
                dt = 0.0
                if p["t_marsz"] > p["limit"]:
                    self.patrol_blok[m["id"]] = teraz + PATROL_BLOK_S
                    self._patrol_zakoncz(p, "limit czasu")
                    p = self.patrol = self._patrol_wybierz(poz, m["id"])
                    if p is None:
                        return None
                    p["tick"] = teraz
                    continue
                if tuple(poz[:3]) not in p["seg_xy"] and teraz - p["replan"] >= 1.0:
                    # zeszliśmy z drogi (walka, loot, ucieczka): nowa droga A* z bieżącej pozycji
                    p["replan"] = teraz
                    d = None
                    if p.get("sweep") and p["sweep"]["nast"] < len(p["sweep"]["trasa"]):
                        d = self._sweep_odcinek(poz, p["sweep"]["trasa"], p["sweep"]["nast"], poz[2])
                    else:
                        uz = []
                        try:
                            d = self._patrol_droga(poz, m, uz)
                        except bot.Zatrzymano:
                            raise
                        except Exception:
                            d = None
                        p["przejscia"] = uz
                    if not d:
                        self.patrol_blok[m["id"]] = teraz + PATROL_BLOK_S
                        self._patrol_zakoncz(p, "brak drogi po zejściu z trasy")
                        p = self.patrol = self._patrol_wybierz(poz, m["id"])
                        if p is None:
                            return None
                        p["tick"] = teraz
                        continue
                    p["seg"] = [tuple(q) for q in d]
                    p["seg_xy"] = {tuple(q[:3]) for q in p["seg"]}
                    p["idx"] = 0
                    self._wypad_reset_klik()
                if not p["seg"]:
                    p["seg"] = [tgt]
                self.ustaw_stan("IDZ", f"patrol m{m['id']} ({m['x']},{m['y']}) {len(p['seg']) - p['idx']} pól")
                wynik, p["idx"] = self._idz_segment(p["seg"], p["idx"])
                if self.__dict__.pop("pietra_zawrot_seg", False):
                    # przejście pięter nie wyszło (pietra.py): nie zawracamy po trasie, bierzemy inne miejsce/przejście
                    self._patrol_blokuj_przejscie(p, poz, teraz)
                    self.patrol_blok[m["id"]] = teraz + PATROL_BLOK_S
                    self._patrol_zakoncz(p, "przejście pięter nieudane")
                    self.patrol = None
                    return True
                if wynik is False:
                    self._patrol_blokuj_przejscie(p, poz, teraz)
                    self.patrol_blok[m["id"]] = teraz + PATROL_BLOK_S
                    self._patrol_zakoncz(p, "nieosiągalne")
                    self.patrol = None
                    return True
                if self.__dict__.get("krok_zly_blok") and KROK_ZLY:
                    # 22.10 KROK_ZLY: krok_do nałożył zakaz na pole z drogi (albo je pominął): nowa droga A* omijająca zakaz
                    # w następnym obiegu; gdy jej nie ma, miejsce idzie na PATROL_BLOK_S i losujemy inne (bez blokady przejścia pięter)
                    self.__dict__["krok_zly_blok"] = False
                    p["replan"], p["seg_xy"] = 0.0, set()
                return True
            if p["faza"] == "postoj":
                if teraz < p["do"]:
                    self.ustaw_stan("IDZ", f"patrol m{m['id']} rozglądam się")
                    self.pauza(0.25, 0.5)
                    return True
                if not p["obchod"] and PATROL_OBCHOD_P > 0 and random.random() < PATROL_OBCHOD_P:
                    p["obchod"] = True
                    o = self._patrol_obchod(poz, {"x": tgt[0], "y": tgt[1]} if p.get("sweep") else m)
                    if o:
                        p["faza"], p["seg"], p["idx"], p["obchod_t"] = "obchod", o, 0, 0.0
                        p["seg_xy"] = {tuple(q[:3]) for q in o}
                        self._wypad_reset_klik()
                        continue
                self._patrol_zakoncz(p, "pusto w widoku" if p.get("zawrot") else "ok")
                p = self.patrol = self._patrol_wybierz(poz, m["id"])
                if p is None:
                    return None
                p["tick"] = teraz
                continue
            if p["faza"] == "obchod":
                cel = p["seg"][-1]
                p["obchod_t"] += dt
                dt = 0.0
                if tuple(poz[:2]) == tuple(cel[:2]) or p["obchod_t"] > 15.0:
                    p["faza"] = "postoj"
                    p["do"] = teraz + random.uniform(0.4, 1.2)
                    continue
                self.ustaw_stan("IDZ", f"patrol m{m['id']} obchód")
                wynik, p["idx"] = self._idz_segment(p["seg"], p["idx"])
                if wynik is False:
                    p["faza"] = "postoj"
                    p["do"] = teraz
                return True
        return True

    def idz(self):
        if self.stoj_wl:
            return self._stoj_krok()        # 23.10 STÓJ: ani trasa, ani patrol, ani wypad/wyprawa; tylko powrót na zapamiętane pole
        if self._wypad_tick():
            return True
        if self.stanowisko is not None and self.g_tick is not None:
            return self.stanowisko.krok(self.g_tick, tuple(self.postac.pozycja()), self.zegar())    # 22.10: stanie na polu zamiast trasy/okrążeń
        if self._patrol_aktywny():
            self.patrol_byl = True
            self.patrol_sync_uciecz = False
            wynik = self._idz_patrol()
            if wynik is not None:
                return wynik
        elif self.patrol_byl:
            # patrol wyłączony w locie (pokrętło): wracamy na trasę od najbliższego punktu
            self.patrol_byl = False
            self.patrol = None
            self._patrol_sync_idx(tuple(self.postac.pozycja()))
        return self._idz_trasa()

    def _idz_trasa(self):
        if not self.punkty:
            return False
        if self.stan != "IDZ" and self.idx >= len(self.punkty):
            self.idx = 0
        if self.zegar() - self.__dict__.get("hp_czeka_ts", float("-inf")) >= 3.0:     # 23.10: w czekaniu na HP stan zostaje PAUZA_HP
            self.ustaw_stan("IDZ", f"punkt {self.idx}/{len(self.punkty)}")
        x, y, z = self.postac.pozycja()
        if MIJANIE:
            if self._mijanie_trasa((x, y, z)):      # 18.10: kierunek gracza względem pętli (unikanie.mijanie), bez bańki i dreptania
                return True
        else:
            self._unikanie_trasa((x, y, z))      # gracz w pobliżu: inny punkt rotacji / cofnięcie (unikanie.py)
        if self._pietra_wlaczone() and self._trasa_stop_potwor((x, y, z)):
            return True                      # potwór tuż obok: ani krok trasy, ani przejście pięter; walka w następnym obiegu
        # punkty już osiągnięte zaliczamy od razu, bez pustego obiegu pętli; przy chodzeniu
        # kliknięciem postać mija kilka punktów między obiegami, więc szukamy jej pozycji do przodu
        n = len(self.punkty)
        for dalej in range(min(10, n)):
            if self.dojscie_aktywne and self.idx + dalej >= n:
                break        # 24.10: trasa dojścia jest jednokierunkowa: bez zawinięcia (k=(idx+dalej)%n łapało punkt 0 = pozycję startu i „kończyło okrążenie”)
            k = (self.idx + dalej) % n
            q = self.punkty[k]
            if (x, y, z) == q or ((x, y) == q[:2] and z != q[2] and not self._pietra_wlaczone()):
                koniec_okrazenia = False
                for _ in range(dalej + 1):
                    self.idx = (self.idx + 1) % n
                    self.pominiete = 0
                    self.przebyte += 1
                    if self.przebyte >= n:
                        self.przebyte = 0
                        self.okrazenie += 1
                        log(f"Okrążenie {self.okrazenie} gotowe.")
                        self._ratunek_zdarzenie("okrazenie", None)
                        koniec_okrazenia = True
                if koniec_okrazenia and self.dojscie_aktywne and z != self.punkty[-1][2] and self.__dict__.get("_dojscie_inne_pietro", 0) < 2:
                    # 24.10: koniec trasy dojścia liczy się tylko na piętrze celu; inaczej idziemy dalej do ostatniego punktu (przejście pięter);
                    # po 2 takich razach w jednej próbie (przejście nie działa) zwykła porażka próby, żeby mozg.przejdz_dojscie ponowił/obrócił
                    self._dojscie_inne_pietro = self.__dict__.get("_dojscie_inne_pietro", 0) + 1
                    log(f"Dojście: okrążenie na z{z}, cel na z{self.punkty[-1][2]}: to nie jest koniec trasy, idę do ostatniego punktu.")
                    self.idx = n - 1
                    return True
                if koniec_okrazenia and self.dojscie_aktywne:
                    # P7e: trasa dojścia jest jednokierunkowa: koniec bez osiągnięcia celu = porażka próby, bez odwracania
                    self.dojscie_porazka = True
                    log(f"Dojście: koniec trasy w {(x, y, z)} bez osiągnięcia celu, kończę próbę (bez odwracania).")
                    return True
                if koniec_okrazenia:
                    # 18.10 Q3: przy MIJANIE=1 losowe odwrócenie nie cofa kierunku trzymanego po mijaniu (decyzja wobec gracza trwa
                    # albo gracz był niedawno w widoku); trasa otwarta odwraca się zawsze (inaczej bot stoi na końcu)
                    if self.otwarta or (random.random() < ODWROCENIE_TRASY and not (MIJANIE and self._mijanie_trzyma())):
                        # postać stoi na punkcie k = idx-1; po odwróceniu ma indeks n-1-k, następny n-k
                        self.punkty.reverse()
                        self.idx = (n - (self.idx - 1) % n) % n
                        self.klik_j = None
                        self.__dict__["utk_zakaz"] = {}     # klucze = indeksy punktów: po odwróceniu znaczą co innego
                        self.trasa_droga = None
                        log("Następne okrążenie w drugą stronę.")
                    return True
                break
        cel = self.punkty[self.idx]
        self.__dict__["cel_trasy"] = (tuple(cel), self.zegar())     # 23.10: dokąd teraz idziemy (_blokada_bij_tick)
        if cel[2] != z and self._pietra_wlaczone():
            # kolejny punkt trasy leży na innym piętrze: przejście schodami/dziurą/drabiną (pietra.py)
            r = self._pietra_tick((x, y, z), cel)
            if r is not None:
                return r
        if DRZWI_TRASA and self._drzwi_trasa_tick((x, y, z)):
            return True                       # 22.10: zamknięte drzwi na nagranej trasie (dojście, trasa): podejście, stanie, Use, krok
        if DRZWI_KLUCZ and self.dojscie_aktywne and PATROL_DRZWI:
            if self._drzwi_klucz_tick((x, y, z), cel) is True:
                return True                   # 24.10: drzwi na klucz w dojściu: podejście, krok, klucz, krok (_drzwi_hak)
        if self._utknieto_na_trasie((x, y, z), cel) and self._wroc_na_trase((x, y, z)):
            return True
        if PATROL_DRZWI and self.__dict__.get("_w_segmencie"):
            dr_ = self._drzwi_hak((x, y, z), [self.punkty[(self.idx + i) % n] for i in range(8)], True)   # R1c
            if dr_ is True:
                return True
            if dr_ is False:
                return False                  # drzwi nie działają: patrol porzuca to miejsce
        prowadz = self._droga_trasy((x, y, z), cel)
        if prowadz and self._unikanie_krokami():
            self.klik_j = None
            self.krok_do(prowadz[0])
            if self.nieudane >= 12:
                self.pominiete += 1
                log(f"Nie mogę dojść do punktu {self.idx} {self.punkty[self.idx]}, pomijam ({self.pominiete}/3).")
                self.nieudane = 0
                self.idx = (self.idx + 1) % n
                self.trasa_droga = None
                if self.pominiete >= 3:
                    log("Trzy punkty z rzędu nieosiągalne, przerywam.")
                    return False
            return True
        if MARSZ_KLIK and self._marsz_dozwolony() and self._marsz_klik((x, y, z), prowadz):
            return True                       # 20.10: marsz klikiem (patrol/dojście), tylko przy MARSZ_KLIK=1
        if prowadz and self.klik is not None:
            # poza prostą (ściana w poprzek / daleko): klikamy kilka pól drogi do przodu
            zasieg = random.randint(*DROGA_DO_PRZODU)
            j = 0
            for i, q in enumerate(prowadz[:zasieg]):
                if abs(q[0] - x) > ZASIEG_X - 1 or abs(q[1] - y) > ZASIEG_Y - 1:
                    break
                j = i
            self.klik_j = None
            self.idz_do(prowadz[j][:2], (x, y, z), krok=prowadz[0][:2])
            if self.nieudane >= 12:
                self.pominiete += 1
                log(f"Nie mogę dojść do punktu {self.idx} {self.punkty[self.idx]}, pomijam ({self.pominiete}/3).")
                self.nieudane = 0
                self.idx = (self.idx + 1) % n
                self.trasa_droga = None
                if self.pominiete >= 3:
                    log("Trzy punkty z rzędu nieosiągalne, przerywam.")
                    return False
            return True
        if prowadz:
            cel = prowadz[0]
        if self.klik is not None:
            # klik w punkt kilka pól do przodu (ten sam poziom, w widoku) - klient prowadzi sam
            # poprzedni punkt kliku trzymamy, dopóki jest >= 2 punkty przed nami (bez klikania co obieg)
            j = self.klik_j
            if j is None or not 2 <= (j - self.idx) % n <= TRASA_DO_PRZODU[1] or self.klik_cel is None:
                zasieg = random.randint(*TRASA_DO_PRZODU)
                j = self.idx
                for dalej in range(1, zasieg + 1):
                    q = self.punkty[(self.idx + dalej) % n]
                    if q[2] != z or abs(q[0] - x) > ZASIEG_X - 1 or abs(q[1] - y) > ZASIEG_Y - 1:
                        break
                    j = (self.idx + dalej) % n
            self.klik_j = j
            self.idz_do(self.punkty[j], (x, y, z))
            if self.nieudane >= 12:
                self.pominiete += 1
                log(f"Nie mogę dojść do punktu {self.idx} {self.punkty[self.idx]}, pomijam ({self.pominiete}/3).")
                self.nieudane = 0
                self.idx = (self.idx + 1) % n
                self.klik_j = None
                if self.pominiete >= 3:
                    log("Trzy punkty z rzędu nieosiągalne, przerywam.")
                    return False
            if random.random() < PAUZA_DLUGA[0] and not self.mob_blisko((x, y, z), PAUZA_BLISKO):
                self.pauza(PAUZA_DLUGA[1], PAUZA_DLUGA[2])
            return True
        # losowo celuj kilka punktów dalej (ścinanie zakrętów), tylko na tym samym piętrze
        if random.random() < SCINANIE[0]:
            for dalej in range(SCINANIE[1], 0, -1):
                j = self.idx + dalej
                if j < len(self.punkty) and self.punkty[j][2] == z and \
                        all(p[2] == z for p in self.punkty[self.idx:j + 1]):
                    cel = self.punkty[j]
                    break
        if not self.krok_do(cel) and self.nieudane >= 12:
            self.pominiete += 1
            log(f"Nie mogę dojść do punktu {self.idx} {cel}, pomijam ({self.pominiete}/3).")
            self.nieudane = 0
            self.idx = (self.idx + 1) % len(self.punkty)
            if self.pominiete >= 3:
                log("Trzy punkty z rzędu nieosiągalne, przerywam.")
                return False
        if self.mob_blisko((x, y, z), PAUZA_BLISKO):
            pass                              # potwór obok: żadnych ślepych pauz
        elif random.random() < PAUZA_DLUGA[0]:
            self.pauza(PAUZA_DLUGA[1], PAUZA_DLUGA[2])
        elif random.random() < PAUZA_KROTKA[0]:
            self.pauza(PAUZA_KROTKA[1], PAUZA_KROTKA[2])
        return True

    def uruchom(self):
        x, y, z = self.postac.pozycja()
        try:
            for pz in {q[2] for q in self.punkty} | {z}:     # zakaz schodów: skan mapy raz, przed pętlą
                if self._zakaz_aktywny():
                    self._zakaz_pol(pz)
        except Exception as e:
            log(f"debug: zakaz zmiany piętra (start): {e!r}")
        self.idx = min(range(len(self.punkty)),
                       key=lambda i: (self.punkty[i][2] != z,
                                      abs(self.punkty[i][0] - x) + abs(self.punkty[i][1] - y)))
        if self._pietra_wlaczone():
            log(f"Trasa wielopiętrowa: piętra {sorted({q[2] for q in self.punkty})}, przejścia pięter włączone (TRASA_PIETRA={TRASA_PIETRA}).")
        log(f"Start: trasa {len(self.punkty)} pkt, najbliższy {self.idx}, próg HP {self.prog_hp}%, "
            f"jedzenie={self.jedzenie}, potwory={sorted(self.potwory) if self.potwory else 'wszystkie'}")
        bledy = 0
        grim_od = grim_log = None        # od kiedy wisi zrzut ekranu (okno gry niewidoczne)
        try:
            while True:
                try:
                    if not self.tick():
                        break
                    bledy = 0
                    if grim_od is not None:
                        log(f"Okno gry znów widoczne po {time.time() - grim_od:.0f} s, wznawiam.")
                        grim_od = None
                except (bot.Zatrzymano, KeyboardInterrupt):
                    raise
                except subprocess.TimeoutExpired as e:
                    # grim wisi, gdy okno gry jest niewidoczne (inny workspace/monitor): zagnieżdżony
                    # sway nie dostaje wtedy klatek. Czekamy na powrót okna zamiast kończyć bota.
                    if not str(getattr(e, "cmd", "")).startswith("['grim'"):
                        raise
                    teraz = time.time()
                    if grim_od is None:
                        grim_od = grim_log = teraz
                        log("Zrzut ekranu wisi: okno gry chyba niewidoczne (inny workspace?). "
                            "Czekam na jego powrót, bot stoi.")
                    elif teraz - grim_log > 120:
                        grim_log = teraz
                        log(f"Okno gry nadal niewidoczne od {teraz - grim_od:.0f} s.")
                    self.pauza(2.0, 4.0)
                    continue
                except Exception as e:  # chwilowy błąd odczytu/akcji nie może zabić bota w walce
                    bledy += 1
                    log(f"Błąd ({bledy}/{LIMIT_BLEDOW}): {e!r}")
                    if bledy >= LIMIT_BLEDOW:
                        log("Za dużo błędów z rzędu, przerywam.")
                        break
                    self.pauza(1.0, 2.0)
                self.pauza_po_ticku()        # Q5 11.10: przy WALKA i odl > 1 prawie bez pauzy
            log("Koniec.")
        except bot.Zatrzymano:
            log("Zatrzymano (plik STOP).")
        except KeyboardInterrupt:
            log("Przerwano (Ctrl+C).")
        finally:
            self._poscig_puszcz()     # żaden klawisz ruchu nie zostaje wciśnięty po wyjściu
            self._d3_zamknij()
            self._obecnosc_zapisz(wymus=True)     # stan mapy obecności na dysk (błąd tylko w logu)


DOJSCIE_SYNC_OKNO = 25             # CavebotDojscie: tyle punktów do przodu sprawdzamy, czy postać już tam stoi (po walce idx zostaje w tyle)


class CavebotDojscie(Cavebot):
    """Dojście na spot po nagranej trasie jednokierunkowej (mozg.py --dojscie, powrót z depo): bez patrolu, bez
    lootu i przerw, bez ataków po drodze (DOJSCIE_BIEGNIJ); kończy się, gdy postać stoi przy OSTATNIM punkcie
    (to samo piętro, <= tolerancja pól) albo gdy trasa by się zawinęła (idx wraca na 0 = zawracanie do depo).
    Po porażce nie zawraca; `dojscie_ok` mówi, czy cel osiągnięty."""
    dojscie_aktywne = True

    def __init__(self, *a, tolerancja=2, **kw):
        super().__init__(*a, **kw)
        self.patrol_wylaczony = True
        self.otwarta = True
        self.dojscie_tol = tolerancja
        self.dojscie_ok = False
        self.dojscie_porazka = False
        self._dojscie_cel = self.punkty[-1]    # cel zostaje, nawet gdyby trasa została odwrócona
        self._dojscie_prev = 0
        self._dojscie_start = tuple(self.punkty[0])    # P7f: początek dojścia (okolica depo)

    def _pietra_zawroc(self, poz):
        """Nieudane przejście pięter w dojściu: nie zawracamy do depo (inna strona trasy), tylko kończymy porażką;
        mozg.przejdz_dojscie ponowi dojście od aktualnej pozycji."""
        self.dojscie_porazka = True
        log("Dojście: przejście pięter nieudane, kończę próbę (bez zawracania trasy).")

    def _dojscie_sync(self, poz):
        n = len(self.punkty)
        z = poz[2]
        najl = None
        for k in range(self.idx + 1, min(n, self.idx + DOJSCIE_SYNC_OKNO)):
            q = self.punkty[k]
            if q[2] != z:
                break                      # zmiana piętra na trasie: nie przeskakujemy przejścia
            if max(abs(poz[0] - q[0]), abs(poz[1] - q[1])) <= 1:
                najl = k
        if najl is not None and najl > self.idx:
            self.idx = najl
            self.klik_j = None

    def tick(self):
        try:
            import stoj  # noqa: PLC0415
            if stoj.wlaczony(self.stoj_katalog):
                log("Dojście: włączony STÓJ, przerywam dojście (stoję tam, gdzie jestem).")
                return False
        except Exception:       # noqa: BLE001
            pass
        if self.dojscie_wroc and not self.wypad_aktywny:
            log("Dojście: ręczne „Wróć do miasta” przerwało dojście, wyprawa do depo skończona; nie wracam do dojścia.")
            return False
        poz = tuple(self.postac.pozycja())
        n = len(self.punkty)
        cel = self._dojscie_cel
        if self.dojscie_porazka:
            return False
        if poz[2] == cel[2] and max(abs(poz[0] - cel[0]), abs(poz[1] - cel[1])) <= self.dojscie_tol:
            self.dojscie_ok = True
            log(f"Dojście: jestem przy końcu trasy {tuple(cel)} (poz {poz}).")
            return False
        if n > 5 and self.idx == 0 and self._dojscie_prev > 0 and self._dojscie_prev >= n - 5:   # P7e: krótka trasa nie "zawija się"
            log(f"Dojście: trasa zawinęła się na punkt 0 w {poz}, nie zawracam.")
            return False
        self._dojscie_prev = self.idx
        self._dojscie_sync(poz)
        zeg = self.__dict__.get("zegar")
        if DOJSCIE_BRAK_POSTEPU_S > 0 and zeg is not None:      # bez zegara (niepełna atrapa) strażnik postępu się wyłącza, nie wywraca ticka
            # 24.10: zastępuje dawne „porażka przez zawinięcie lookaheadu na punkt 0”: ani jeden nowy punkt trasy przez N s w spokoju
            # (walka, ucieczka, czekanie na HP = stan inny niż IDZ zeruje odliczanie) = porażka próby, mozg.przejdz_dojscie ponawia
            t = zeg()
            if self.idx > self.__dict__.get("_dojscie_maxidx", -1) or str(self.__dict__.get("stan", "IDZ")) != "IDZ" or "_dojscie_postep_ts" not in self.__dict__:
                self._dojscie_maxidx = max(self.idx, self.__dict__.get("_dojscie_maxidx", -1))
                self._dojscie_postep_ts = t
            elif t - self._dojscie_postep_ts > DOJSCIE_BRAK_POSTEPU_S:
                self.dojscie_porazka = True
                log(f"Dojście: {int(t - self._dojscie_postep_ts)} s bez nowego punktu trasy (idx {self.idx}/{n}, poz {poz}), kończę próbę.")
                return False
        return super().tick()


def main(argv):
    p = argparse.ArgumentParser(description="Cavebot Retronic")
    p.add_argument("trasa", help="nazwa trasy (trasy/<nazwa>.json)")
    p.add_argument("-o", "--okrazenia", type=int, help="liczba okrążeń")
    p.add_argument("-c", "--czas", type=float, help="limit czasu w minutach")
    p.add_argument("--prog-hp", type=float, default=40, help="ucieczka przy tym %% HP i niżej (40)")
    p.add_argument("--jedzenie", help="klawisz jedzenia (np. F1)")
    p.add_argument("--potwory", help="lista nazw po przecinku (domyślnie wszystkie)")
    p.add_argument("--czekaj", action="store_true",
                   help="stój i czekaj, aż potwór podejdzie (zamiast od razu do niego iść)")
    p.add_argument("--ignoruj-graczy", action="store_true",
                   help="nie zatrzymuj się nawet przy graczu z czaszką/GM (domyślnie: tylko ci stoją)")
    p.add_argument("--stop-przy-graczach", action="store_true",
                   help="stare zachowanie: każdy obcy gracz na ekranie zatrzymuje bota i włącza alarm")
    a = p.parse_args(argv)
    if not os.environ.get("RETRONIC_TESTY"):
        os.environ.setdefault("RETRONIC_TELEMETRIA", "1")   # P4 (13.10): samodzielny cavebot na żywo pisze telemetrię
    def _sigterm(*_):
        raise KeyboardInterrupt           # uruchom() loguje "Przerwano", a pętla pościgu puszcza klawisze w finally
    signal.signal(signal.SIGTERM, _sigterm)
    bot.klawisz_x11.zainstaluj_sygnaly()  # SIGTERM/SIGINT/SIGHUP: najpierw puść strzałki, potem powyższa obsługa
    punkty = json.loads((bot.TRASY / f"{a.trasa}.json").read_text())
    potwory = [n.strip() for n in a.potwory.split(",") if n.strip()] if a.potwory else None
    Cavebot(bot.Postac(), punkty, a.okrazenia, a.czas * 60 if a.czas else None, a.prog_hp,
            a.jedzenie, potwory, not a.ignoruj_graczy, czekaj=a.czekaj,
            stop_przy_graczach=a.stop_przy_graczach).uruchom()


if __name__ == "__main__":
    main(sys.argv[1:])
