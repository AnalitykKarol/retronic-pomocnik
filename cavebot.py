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
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bot  # noqa: E402
import instancja  # noqa: E402

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
PIETRA_RESYNC_MAX = 6              # tyle resynchronizacji (piętro poza trasą) w 120 s = porażka
PIETRA_DOJSCIE_S = 25.0            # s bez zbliżenia do pola przejścia = następny kandydat
TRYB_PATROL = 0                    # 12.10: 1 = patrol po miejscach z trasy/miejsca.json (losowo, ważony zabiciami i odległością) zamiast pętli trasy; mozg --trasa patrol ustawia 1; pokrętło 0-1
PATROL_PLIK = "miejsca.json"       # plik miejsc w trasy/
PATROL_KOORD = 0                   # 1 = koordynator miejsc między instancjami (miejsca_koord.py): nie wybieram miejsc zajętych przez inną instancję, swoje rezerwuję; 0 = wył. (domyślnie); pokrętło 0-1
PATROL_KOORD_PROMIEN = 0           # pola: rezerwacja blokuje też miejsca tak blisko (to samo piętro); 0 = tylko to samo miejsce; pokrętło 0-30
PATROL_WAGA_MIN = 0.04             # dolny próg udziału zabić miejsca w losowaniu (miejsca bez danych też bywają odwiedzane)
PATROL_ODL_SKALA = 22.0            # waga odległości: 1 / (1 + d / skala), d = pola prosto (|dx| + |dy|)
PATROL_BYLO_WYKLUCZ = 4            # tyle ostatnich odwiedzonych miejsc nie jest losowane
PATROL_BYLO_KARA = 0.4             # mnożnik wagi dla miejsc odwiedzonych 5-8 wizyt temu
PATROL_ODL_MIN = 3                 # miejsca bliżej niż tyle pól od nas nie są losowane (już tam jesteśmy)
PATROL_PRZYJECIE = 1               # pola: tak blisko miejsca = dotarliśmy
PATROL_POSTOJ = (1.0, 3.0)         # s rozglądania się na miejscu
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
LOOT_DYNAMICZNY = 1                # 13.10: loot dynamiczny (pokrętło 0/1; 0 = dawne zachowanie, DOMYŚLNIE 1 od decyzji Karola 13.10; 0 = dawne zasady): zwłoki w odl <= 1 zaraz po zabiciu także przy
                                   # żywym mobie w odl >= 2; dalsze gdy mob >= 3 pola; okno lootu otwarte nie jest przerywane "cel_daleko";
                                   # po "brak_okna" zwłoki wstrzymane do końca walki (jedna próba po walce); zwłoki z innego piętra odłożone
LOOT_SZYBKI_ODL = 3                # LOOT_DYNAMICZNY: zwłoki tak blisko (pola) zbieramy zaraz po zabiciu, gdy żaden mob nie przylega
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
WYPRAWA_DEPO_BLANKI = 0            # P7b: 1 = w trybie WYPRAWA_TYLKO_DEPO sam brak blanków też jest powodem wyprawy (domyślnie 0: do depo nie kupujemy blanków, tylko powiadomienie)
WYPRAWA_PO_DEPO_S = 900            # P7c: s: minimalna karencja kolejnej wyprawy po wyprawie zakończonej w depo (liczy się większa z tego i WYPRAWA_CO_MIN)
WYPRAWA_PO_DOJSCIU_S = 300         # P7a: s: po dojściu z depo na spot pierwsza ocena wyprawy najwcześniej po tylu sekundach (0 = bez karencji)
DOJSCIE_WALKA_PRZEJSCIE_S = 60     # P7d: s: w dojściu stwór obok przy zmianie piętra (dziura/schody) = walka do skutku, ale max tyle s (0 = dawne WYPAD_WALKA_S)
DOJSCIE_BEZ_UNIKANIA_POL = 0       # P7f: >0 = w dojściu, gdy postać jest w tylu polach od początku dojścia (depo), unikanie graczy wyłączone; 0 = bez zmiany (domyślnie wył.)
DOJSCIE_PROBY = 5                  # P7e: tyle razy ponawiamy dojście od aktualnej pozycji, zanim uznamy porażkę (mozg.przejdz_dojscie; zakres 3-8)
DOJSCIE_PAUZA_PROBY_S = 4.0        # P7e: s pauzy (losowo 0,75x-1,5x) przed kolejną próbą dojścia po porażce przejścia pięter
DOJSCIE_BIEGNIJ = 1                # 1 = w dojściu na spot (--dojscie, CavebotDojscie) biegniemy: bez walki, lootu, przerw i pościgu; bijemy tylko blokujące moby (WYPAD_BLOK_S/WYPAD_WALKA_S); ucieczka i leczenie zostają
PIETRA_LOPATA_TYLKO_Z7 = 1         # pokrętło 0/1: łopata tylko na z7 (wejście do jaskini z powierzchni); 0 = na każdym piętrze (dawne)
PIETRA_LOPATA_BRAK_S = 600.0       # s: po "nie widzę łopaty" w plecaku nie próbujemy łopaty ponownie
PIETRA_LOPATA = 1                  # 1 = przy wejściu w dół dziurą (pole z flagą 2) po nieudanym kroku odkopujemy ją łopatą z plecaka (Use with, ID 3457)
WYPRAWA_DEPO_POWROT = 0            # 1 = po dojściu do depo wyprawa sama wraca na spot (faza "z" po trasie depo_troll_cave) zamiast STOP
WYPRAWA_DEPO_POSTOJ_S = 0          # s: postój w depo przed powrotem (czas na ręczne odłożenie rzeczy)
WYPRAWA_CZEKAJ_NA_GLOD = 0         # 1 = wyprawa po jedzenie dopiero po potwierdzonym głodzie (nieudana próba jedzenia), nie od razu przy zapasie 0
WYPRAWA_DEPO_W_WALCE = 1           # 1 = wyprawa do depo (po potwierdzonym głodzie) startuje także w walce i biegnie; 0 = tylko w spokoju
WYPRAWA_DEPO_ZLOZ = 0                # 1 = zwykła wyprawa zaczyna od depo: składa UH w skrzyni, potem Frodo/Xodet
WYPRAWA_TYLKO_DEPO = 0              # 1 = wyprawa idzie tylko do depo (troll_do_miasta + A* do pola depo), tam STOP + powiadomienie; bez zakupów i powrotu
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
# --- jedzenie czarem exevo pan (F3): tworzy jedzenie, które zjadamy istniejącym mechanizmem. Domyślnie WYŁĄCZONE ---
RUNA_AKTYWNA = 0                   # pokrętło 0/1 (na_zywo.json): 1 = strzał runą (hotkey) w cel w walce; nie kosztuje many
RUNA_KLAWISZ = "F4"                # hotkey w kliencie: "użyj runy na celu" (HMM w zaznaczony cel); pokrętło tekstowe
RUNA_INTERWAL_S = 2.0              # pokrętło: min. odstęp między strzałami (cooldown run ok. 2 s)
RUNA_MIN_HP_CELU = 0               # pokrętło: cel poniżej tego HP% nie dostaje runy (0 = bez limitu)
RUNA_ZASIEG = 3                    # pola: dalej nie strzelamy
RUNA_LOG_CO = 20                   # log licznika strzałów co tyle
RUNA_TRYB_KLIK = 0                 # pokrętło 0/1: 1 = strzał kliknięciami (prawy klik na runie -> "Use with" -> lewy na mobie) zamiast hotkeya
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
UH_PRZERWA_PO_PORAZKACH_S = 1800.0 # s wyłączenia po porażkach / alarmie
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
UH_PRZERWA_PO_PORAZKACH_S = 1800.0 # s wyłączenia po porażkach / alarmie
UH_PRZERWA_BRAK_BLANK_S = 600.0    # s wyłączenia, gdy brak blank run
UH_HOLD_MAX_S = 300.0              # s: tyle ML (utevo lux) czeka na manę dla UH (potem rzuca; bez zakleszczenia)
UH_W_WALCE = 0                     # pokrętło 0/1 (na_zywo.json): 1 = runa także W TRAKCIE WALKI, gdy mana prawie pełna (regen się marnuje)
UH_W_WALCE_MANA_MARGINES = 5       # pokrętło: w walce start, gdy mana >= max_mana - tyle (i >= UH_KOSZT)
UH_W_WALCE_DYSTANS = 0             # pokrętło 0-3: w trybie walki stwór w tej odległości (Chebyshev) blokuje start i przerywa runę; 0 = moby ignorowane (tylko gracz, HP, ucieczka), 1 = przylegający
UH_W_WALCE_SPADEK_HP = 25          # pokrętło: w trakcie runy w walce przerwij, gdy HP spadło o tyle pp od startu runy (kilka trolli naraz)
UH_W_WALCE_MIN_HP = 90             # pokrętło: % HP wymagane do startu runy w walce (w trakcie: ta wartość minus 10)
# --- ogłoszenia sprzedaży UH na kanale Trade (mozg.py: TradeOgloszenia; szablon trade_ogloszenie.txt) ---
TRADE_OGLOSZENIA = 0               # pokrętło 0/1 (na_zywo.json): 1 = ogłoszenie [SELL] UH na zakładce Trade (domyślnie WYŁĄCZONE)
TRADE_MIN_S = 180                  # pokrętło: s min. odstępu między ogłoszeniami (losowo równomiernie MIN-MAX)
TRADE_MAX_S = 300                  # pokrętło: s max. odstępu między ogłoszeniami
TRADE_MIN_UH = 20                  # pokrętło: ogłaszamy dopiero, gdy w plecakach jest tyle run UH ({bp} = pełne po 20)
# --- pola ognia (ogien.py): wykrywane ze zrzutu (pomijają je pamięć stworów i mapa), liczone jak zablokowane pole ---
OGIEN_UNIKAJ = 1                   # pokrętło 0/1 (na_zywo.json): 1 = omijamy pola ognia, schodzimy z nich, nie lootujemy z ognia
OGIEN_ODSWIEZ_S = 0.8              # s: min. odstęp między wykryciami w tickach (zrzut ppm ok. 40 ms + analiza ok. 20 ms)
OGIEN_BRAK_S = 1.5                 # s: widoczne pole bez ognia w kolejnych wykryciach tak długo = ogień zgasł (animacja migocze)
OGIEN_TRWA_S = 25.0                # s: pole ognia, którego nie widać (poza widokiem), pamiętamy tyle od ostatniego wykrycia
OGIEN_KROK_S = 0.6                 # s: min. odstęp między krokami z pola ognia (poprzedni krok jeszcze trwa)
OGIEN_SZUKAJ = 6                   # pola (Manhattan): tak daleko szukamy wolnego pola poza ogniem
OGIEN_ZLY_KROK_S = 3.0             # s: krok z ognia, który nie przesunął postaci, pomijamy tak długo
OGIEN_CZEKAJ_MAX_S = 30.0          # s: tyle czekamy, aż ogień zgaśnie, gdy zamyka drogę; potem go ignorujemy
OGIEN_IGNORUJ_S = 20.0             # s ignorowania ognia po wyczerpaniu czekania
OGIEN_LOOT_CHLOD_S = 5.0           # s: zwłoki leżące na ogniu wracają do kolejki po tym czasie
OGIEN_LOG_S = 10.0                 # s: min. odstęp między wpisami "[OGIEN] pola" (13.10, P6: było 1; pokrętło 1-60)
OGIEN_STALY = 1                    # pokrętło 0/1: 1 = maska stałych pól ognia (nie logujemy, nie blokują drogi)
OGIEN_STALY_N = 20                 # tyle wykryć tego samego pola ...
OGIEN_STALY_S = 600.0              # ... w ciągu co najmniej tylu sekund = pole stałe (nie run-fire z 1-2 min)
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
_K = 1 << 17                       # klucz pola w droga(): x*_K + y (|y| < 65536)
PROG_UCIEKANIA_DOMYSLNY = {"rat": 30}   # % HP, przy którym gatunek zaczyna uciekać (uczony na żywo)
CZUJNOSC = 15                      # pp nad progiem ucieczki: od tego HP celu sprawdzamy go bardzo często
KLIK_PONOW = 1.5                   # s: ponów klik w ten sam cel, jeśli jeszcze nie doszliśmy
KLIK_BEZ_RUCHU = 1.2               # s bez zmiany pozycji po kliku -> klik nie działa, idziemy strzałkami
KLIK_ODSTEP = 0.4                  # s: min. odstęp między kliknięciami w mapę (maks. ~2,5 kliku/s)
NAUKA_KROK = 5                     # pp: o tyle maks. przesuwa próg uciekania jedna obserwacja
PROG_UCIEKANIA_MIN = 25            # % HP: niżej progu nie uczymy (ucieczkę widzimy z opóźnieniem, przy niższym HP)
UTKNIECIE_TRASA = 27.0             # s w IDZ bez zmiany punktu i na <= UTKNIECIE_POLA polach = utknięcie na trasie
UTKNIECIE_POLA = 4                 # tyle różnych pól (albo mniej) w oknie utknięcia
UTKNIECIE_LUKA = 6.0               # s: przerwa w IDZ (walka, loot) dłuższa niż to zeruje okno utknięcia
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
    """Dźwięk przez paplay/canberra, a gdy ich brak, sam wydruk."""
    log(f"ALARM: {powod}")
    try:
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
        self.czekanie_do = None        # do kiedy stoimy i czekamy na podejście celu
        self.reakcja_do = 0            # do kiedy "zauważamy" nowy cel, zanim go zaatakujemy
        self.pogon_odl = 0             # najmniejszy dystans do celu w tej pogoni
        self.tele = self.pokretla = None   # telemetria.py + pokretla.py (tylko na żywo, patrz _hak_telemetrii)
        self.mana_ostatnia = None      # poprzedni odczyt many (śledzenie "mana nie rośnie")
        self.mana_wzrost = zegar()     # kiedy mana ostatnio rosła, była pełna albo po jedzeniu/rzucie czaru
        self.jedzenie_nie_do = float("-inf")   # do kiedy nie ponawiamy jedzenia (brak jedzenia w plecaku)
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
        self.skos_zle = {}             # (z_pola, na_pole) -> do kiedy: skos, który nie przesunął postaci (nie ściana!)
        self.skos_ost = None           # (z_pola, na_pole) ostatniego skosu awaryjnego
        self.skos_awaryjny_n = 0       # ile razy droga poszła skosem awaryjnym (telemetria / test)
        self._skos_log_t = float("-inf")
        self.w_poscigu = False         # True w trakcie poscig_szybki (mózg nie skanuje wtedy pamięci)
        self.w_lootcie = False         # True w trakcie zbierania zwłok
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
        self.ostatni_objazd = ""       # opis ostatniego odrzuconego celu (do logu)
        self._klucze, self._klucze_n = {}, -1   # pamięć podręczna droga(): piętro -> klucze pól
        self.pietra = None             # pietra.Pietra: przejścia pięter z trasy wielopiętrowej (tworzone przy pierwszym użyciu)
        self.pietra_ops = None         # operacje na ekranie (Use/lina); None = z wypadu / wypad.OperacjeZywe; testy wstrzykują atrapę
        self.pietra_porazki = 0        # kolejne nieudane przejścia pięter
        self._pietra_cache = None      # (id listy punktów, długość, wynik): czy trasa ma > 1 piętro
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
        self.czar_ostatni = float("-inf")  # czas ostatniego rzutu DOWOLNEGO czaru bota (wspólny exhaust)
        self.zd_oczekuje = None        # exura: (czas rzutu, mana przed, hp przed)
        self.zd_porazki = 0
        self.zd_wylaczony_do = float("-inf")
        self.zd_rzuty = 0
        self.runa_ostatni = float("-inf")  # czas ostatniego strzału runą
        self.klik_ramka_false = {}     # id celu -> liczba kliknięć "ramka_false" bez spadku HP (ATAK_LIMIT_KLIKOW)
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
        self.uh_restore = None         # None = nie sprawdzono; True = po restarcie/alarmie tarcza może być zdjęta
        self.uh_czeka_ts = float("-inf")   # kiedy ostatnio UH czekał tylko na manę (ML wtedy nie zjada many)
        self.uh_hold_od = None
        self.uh_przerwal_cavebot = None    # powód przerwania zgłoszony przez callback (to nie porażka mechanizmu)
        self.unikanie = None           # unikanie.Unikanie: omijanie zwykłych graczy (haki: tick, _unikanie_filtr, _idz_trasa)
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
            przy_depo = False
            if self.dojscie_aktywne and DOJSCIE_BEZ_UNIKANIA_POL > 0 and poz is not None:
                d0 = getattr(self, "_dojscie_start", None)      # P7f: tłum przy depo nie jest zagrożeniem
                przy_depo = bool(d0 and d0[2] == poz[2]
                                 and max(abs(d0[0] - poz[0]), abs(d0[1] - poz[1])) <= DOJSCIE_BEZ_UNIKANIA_POL)
            u.obserwuj(lista, poz, self.postac.nazwa,
                       wylacz=not self.zatrzymaj_przy_graczu or self.wypad_aktywny or w_miescie or przy_depo)
            self._patrol_pamietaj_graczy()
        except bot.Zatrzymano:
            raise
        except Exception as e:
            log(f"unikanie: błąd {e!r}")

    def _unikanie_filtr(self, kand, poz):
        """Wybór celu w tick(): bez mobów stojących w UNIKANIE_MOB_PROMIEN od innego gracza (poza tym, co stoi
        obok nas albo nas gryzie). Inne użycia kandydaci() (loot, pościg) widzą wszystkie moby."""
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
        zaj = list(blok) + [p for p in list(self.sciany) if p[2] == z and self.sciana(p)]
        if self.mapa_zna(start, cel):
            return self.mapa.droga(start, cel, zaj, 0, False, limit=MAPA_LIMIT, znane=self._pola_pietra(z))
        return self._droga_znane(start, cel, zaj, 0, False)

    def _unikanie_krokami(self):
        """True, gdy unikanie jest aktywne i gracz jest w zasięgu: idziemy krok po kroku po bezpiecznej drodze
        (klik prowadziłby klienta własną, krótszą trasą tuż przy graczu albo przy mobie)."""
        u = self.unikanie
        return u is not None and u.aktywne and bool(u.gracze) and not self.wypad_aktywny

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
        if not bieg:
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
        if obok and self.dojscie_aktywne and DOJSCIE_WALKA_PRZEJSCIE_S > 0 and self._dojscie_przy_przejsciu(poz):
            walka_s = max(WYPAD_WALKA_S, float(DOJSCIE_WALKA_PRZEJSCIE_S))   # P7d: przy dziurze nie cyklujemy co 8 s
            self._walka_przejscie = walka_s > WYPAD_WALKA_S
        if obok and teraz - self.ruch_czas >= WYPAD_BLOK_S:
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
        mana = g.get("mana")
        if mana is None:
            return False
        blok = self._uh_blokada(g, poz, teraz, lista)
        if blok is not None:
            self.uh_hold_od = None
            return False
        import uh  # noqa: PLC0415
        mx = g.get("max_mana")
        mana_min = max(int(UH_KOSZT), min(int(UH_MANA_MIN), int(mx))) if mx else int(UH_MANA_MIN)
        walka = (not restore) and self._uh_walka_ok(g)     # ten sam warunek co w _uh_blokada (g bez zmian)
        widoczne = [s for s in lista if s.get("z") == poz[2] and self._uh_widoczny(s, poz, walka)]
        if walka:
            mana_min = max(int(UH_KOSZT), int(mx) - int(UH_W_WALCE_MANA_MARGINES))
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

    def _runa(self, g, poz, lista, teraz):
        # walka = jest cel (stan bywa chwilowo "ZDROWIE"/"JEDZENIE" po czarze: nie głodzimy wtedy runy)
        if not RUNA_AKTYWNA or self.cel is None or self.ucieczka:
            return False
        if teraz - self.runa_ostatni < max(float(RUNA_INTERWAL_S), 0.5):
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
            runa_id=int(RUNA_ID), menu_dx=int(RUNA_MENU_DX), menu_dy=int(RUNA_MENU_DY))
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
        if self.wypad_aktywny:
            return "wypad"
        return None

    def _zdrowie_gotowy(self, g, teraz):
        """Czy leczenie exura jest teraz wskazane i możliwe (bez blokad i opóźnienia). Pokrętło/mana/HP/exhaust."""
        if not ZDROWIE_CZAR_AKTYWNY or teraz < self.zd_wylaczony_do or self.zd_oczekuje is not None:
            return False
        mana, proc = g.get("mana"), g.get("proc")
        if mana is None or proc is None or mana < ZDROWIE_CZAR_KOSZT:
            return False
        if not self.prog_aktualny < proc < ZDROWIE_CZAR_HP:     # <= prog ucieczki: ucieczka ma pierwszeństwo
            return False
        if teraz - self.czar_ostatni < CZAR_MIN_PRZERWA_S:
            return False
        return self._czar_blokada() is None

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
        if teraz < self.jedzenie_nie_do:
            return True
        w = self.jedzenie_plecak
        return bool(w is not None and w[1] == 0 and teraz - w[0] <= JEDZENIE_CZAR_PLECAK_WAZNE_S)

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
        if self.mapa is not None and self.zegar() - t > SCIANA_WAZNA and self.mapa.przechodnie(*pole):
            del self.sciany[pole]
            return False
        return True

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
        return self.ogien_stale if OGIEN_STALY else frozenset()

    def _ogien_xy(self, z, bez_stalych=False):
        """Zbiór (x, y) pól ognia na piętrze z (pusty, gdy ogień nie obowiązuje). bez_stalych=True: bez pól stałych
        (droga, A*, klik); ze stałymi: zejście z ognia i zwłoki na ogniu (bezpieczeństwo)."""
        if not self._ogien_aktywny():
            return set()
        st = self._ogien_stale_ef() if bez_stalych else ()
        return {(x, y) for (x, y, pz) in self.ogien_pola if pz == z and (x, y, pz) not in st}

    def _ogien_stale_aktualizuj(self, widziane, teraz):
        """P6: liczy wykrycia pól; pole widziane >= OGIEN_STALY_N razy w ciągu >= OGIEN_STALY_S, albo będące
        ścianą mapy (flaga 4), trafia do ogien_stale. Wpisy nie widziane od OGIEN_STALY_S są zapominane."""
        for p in widziane:
            w = self.ogien_widz.get(p)
            if w is None:
                w = self.ogien_widz[p] = [0, teraz, teraz]
                if p not in self.ogien_stale and self.mapa is not None:
                    try:
                        if self.mapa.flagi(*p) & 4:
                            self.ogien_stale.add(p)
                    except Exception:
                        pass
            w[0] += 1
            w[2] = teraz
            if w[0] >= OGIEN_STALY_N and teraz - w[1] >= OGIEN_STALY_S:
                self.ogien_stale.add(p)
        for p, w in list(self.ogien_widz.items()):
            if p not in self.ogien_stale and teraz - w[2] > OGIEN_STALY_S:
                del self.ogien_widz[p]

    def _ogien_na(self, pole):
        """Czy pole (x, y, z) jest polem ognia."""
        return self._ogien_aktywny() and (pole[0], pole[1], pole[2]) in self.ogien_pola

    def _ogien_blok(self, start, cel=None):
        """Pola ognia piętra startu jako lista (x, y, z) dla A* (bez pola, na którym stoimy)."""
        return [(x, y, start[2]) for (x, y) in self._ogien_xy(start[2], bez_stalych=True) if (x, y) != tuple(start[:2])]

    def _ogien_na_drodze(self, poz, cel_xy):
        """Czy pole ognia leży w prostokącie poz-cel (+1 pole zapasu): klik poprowadziłby klienta przez ogień."""
        ogien = self._ogien_xy(poz[2], bez_stalych=True)    # stałe pola: mapa/minimapa i tak je omija (P6)
        if not ogien:
            return False
        x0, x1 = sorted((poz[0], cel_xy[0]))
        y0, y1 = sorted((poz[1], cel_xy[1]))
        return any(x0 - 1 <= x <= x1 + 1 and y0 - 1 <= y <= y1 + 1 for x, y in ogien)

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
        stare = set(self.ogien_pola)
        widziane = {(x + dx, y + dy, z) for dx, dy in wzgl}
        self._ogien_stale_aktualizuj(widziane, teraz)
        for p in widziane:
            self.ogien_pola[p] = teraz
        for p, t in list(self.ogien_pola.items()):
            if p in widziane:
                continue
            w_widoku = p[2] == z and abs(p[0] - x) <= ZASIEG_X and abs(p[1] - y) <= ZASIEG_Y
            if p[2] != z or (w_widoku and teraz - t >= OGIEN_BRAK_S) or teraz - t > OGIEN_TRWA_S:
                del self.ogien_pola[p]
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
        ogien = self._ogien_xy(z)
        if (x, y) not in ogien:
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
        self.klik_cel = None
        cel_kroku = d[0][:2] if d else (krok[:2] if krok else cel_xy)
        if self.krok_do(cel_kroku):
            self.ogien_czeka_od = None
            return True
        if self.ogien_czeka_od is None:
            self.ogien_czeka_od = teraz
        elif teraz - self.ogien_czeka_od >= OGIEN_CZEKAJ_MAX_S:
            log(f"[OGIEN] ogień zamyka drogę od {OGIEN_CZEKAJ_MAX_S:.0f} s, ignoruję go przez {OGIEN_IGNORUJ_S:.0f} s.")
            self.ogien_ignoruj_do = teraz + OGIEN_IGNORUJ_S
            self.ogien_czeka_od = None
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
            znane = self._pola_pietra(z)
            d = self.mapa.droga(start, cel, blok, dlugosc, skosy, limit=MAPA_LIMIT, znane=znane)
            prosto = max(abs(cel[0] - start[0]), abs(cel[1] - start[1]))
            if blok and (d is None or len(d) > 2 * prosto + MAPA_OBJAZD):
                # stwory i nauczone ściany (często fałszywe: stwór na polu) nie mogą zamykać
                # wąskiego korytarza ani zmuszać do objazdu: liczymy też drogę po samej mapie
                # i bierzemy krótszą (gdy bez blokad nie jest to objazd)
                d2 = self.mapa.droga(start, cel, zakaz + ogien, dlugosc, skosy, limit=MAPA_LIMIT, znane=znane)
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
                      and not (s.get("gracz") and s.get("nazwa") == self.postac.nazwa)]
        if self.sprawdz_krok(poz, zajete, cel) and natychmiast:
            if not poscig:
                self.pauza(0.03, 0.06)        # poprzednia strzałka jeszcze nie przesunęła postaci
            return True
        prosto = max(abs(cel[0] - poz[0]), abs(cel[1] - poz[1]))
        # strzałki chodzą tylko prosto, więc dla nich droga bez skosów; skosem (klikiem) tylko blisko celu
        skosy = self.klik is not None and not poscig and (not natychmiast or prosto <= DIAGONAL_ODL)
        d = self.droga(poz, cel, zajete, dlugosc, skosy=skosy)
        if POSCIG_SKOS_AWARYJNY and not skosy and self._skos_mozliwy():
            # 12.10: róg, w którym jedyne przejście jest po skosie (dwa pola w osiach = ściana): bez drogi prostej
            # (albo przy długim objazdzie) bierzemy drogę ze skosami, jeśli jest; skos tylko awaryjnie
            limit_d = 2 * prosto + (MAPA_OBJAZD if self.mapa_zna(poz, cel) else DROGA_OBJAZD)
            if d is None or (d and len(d) > limit_d):
                teraz_s = self.zegar()
                zle = [q for (z0, q), do in self.skos_zle.items() if z0 == tuple(poz[:2]) and do > teraz_s]
                d2 = self.droga(poz, cel, list(zajete) + zle, dlugosc, skosy=True)
                if BLOK_WYJSCIE and d2 and tuple(d2[0][:2]) in {tuple(p[:2]) for p in zajete}:
                    d2 = None          # pierwszy krok skosu w pole zajęte przez stwora: nie idziemy
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

    def stwory(self, maks_wiek=None):
        z = {"cmd": "stwory"}
        if maks_wiek is not None:
            z["maks_wiek"] = maks_wiek     # cache skanera rdzenia zamiast świeżego skanu
        return self.zapytaj(z)["stwory"]

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
        self.klik_cel, self.klik_czas = cel_kliku, teraz
        self.pauza(0.15, 0.3)
        return True

    def zatrzymaj_klik(self, poz):
        """Postać idzie jeszcze po starym kliku: Escape przerywa marsz (i atak - ponowimy go)."""
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
        for k in kier:
            if self.zablokowane.get(((x, y, z), k)):
                continue
            if self._ogien_na((x + bot.KIERUNKI[k][0], y + bot.KIERUNKI[k][1], z)):
                continue                       # pole ognia: nie wchodzimy (najpierw omijanie, potem czekanie)
            if pietra_on:
                d = bot.KIERUNKI[k]
                n_xy = (x + d[0], y + d[1])
                if n_xy != (cel[0], cel[1]) and self.pole_zmiany_pietra((n_xy[0], n_xy[1], z)):
                    continue                   # trasa wielopiętrowa: schodów nie wchodzimy "przy okazji" (cel kroku wolno)
            if self.postac.krok(k):
                self.zablokowane.clear()
                d = bot.KIERUNKI[k]
                if wstecz is not None and (x + d[0], y + d[1], z) == wstecz and k != kier[0]:
                    pass                      # krok wstecz (nie w stronę celu): to nie postęp
                else:
                    self.nieudane = 0
                self.krok_z = ((x, y, z), teraz)
                return True
            self.zablokowane[((x, y, z), k)] = True
        if sk is not None and self._krok_do_skos(x, y, z, sk, teraz, wstecz):
            return True                       # strzałki w osiach nie ruszyły, skos tak
        self.nieudane += 1
        self.zablokowane.clear()
        self.pauza(0.3, 0.8)
        return False

    def _skos_kandydat(self, x, y, z, cel, pietra_on):
        """(dx, dy) skosu w stronę celu, gdy skos awaryjny jest włączony, postać umie skos, a pole po skosie nie jest
        zablokowane (ściana z mapy/nauczona, zmiana piętra, świeżo nieudany skos); inaczej None."""
        if not POSCIG_SKOS_AWARYJNY or not hasattr(self.postac, "krok_skos"):
            return None
        dx, dy = cel[0] - x, cel[1] - y
        if not dx or not dy:
            return None
        v = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))
        pole = (x + v[0], y + v[1], z)
        if self.sciana(pole) or self._ogien_na(pole):
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
                                for q in self.ostatnie_stwory):
            return None          # pole skosu zajęte przez żywego stwora
        if self.skos_zle.get(((x, y), pole[:2]), 0) > self.zegar():
            return None
        if self.zablokowane.get(((x, y, z), "skos")):
            return None
        return v

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
            if teraz - self._skos_log_t >= SKOS_LOG_S:
                self._skos_log_t = teraz
                log(f"Skos awaryjny: krok ({v[0]},{v[1]}) z ({x},{y}), pola w osiach zablokowane.")
            return True
        self.zablokowane[((x, y, z), "skos")] = True
        self.skos_zle[((x, y), pole[:2])] = teraz + SKOS_ZLY_S
        return False

    @staticmethod
    def dystans(a, b):
        return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

    # --- decyzje ---

    @staticmethod
    def w_widoku(s, poz):
        return s["z"] == poz[2] and abs(s["x"] - poz[0]) <= ZASIEG_X and abs(s["y"] - poz[1]) <= ZASIEG_Y

    def inni_gracze(self, lista, poz):
        return [s for s in lista if s["gracz"] and s["nazwa"] != self.postac.nazwa and s["z"] == poz[2]
                and abs(s["x"] - poz[0]) <= ZASIEG_X and abs(s["y"] - poz[1]) <= ZASIEG_Y]

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
                      and not (m.get("gracz") and m.get("nazwa") == self.postac.nazwa)]
            c_xy = (s["x"], s["y"])
            dr = self.droga(tuple(poz[:3]), c_xy, zajete, 1, skosy=False)
            limit = 2 * d + (MAPA_OBJAZD if self.mapa_zna(poz, c_xy) else DROGA_OBJAZD)
            ok = dr is not None and len(dr) <= limit
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
        """GM/CM/God/Tutor po nicku albo czaszka/PK, jeśli odczyt stworów ją podaje.
        Rdzeń (rdzen.py stwory) NIE czyta jeszcze czaszki z pamięci; gdy dojdzie pole "czaszka"
        (albo "skull", >0 / True), ten warunek zacznie działać bez zmian tutaj."""
        if GM_NAZWA.search(s.get("nazwa") or ""):
            return True
        return bool(s.get("czaszka") or s.get("skull") or s.get("pk"))

    def kandydaci(self, lista, poz):
        teraz = self.zegar()
        wynik = []
        for s in lista:
            if s["gracz"] or s["z"] != poz[2] or s.get("hp", 100) <= 0:
                continue
            if abs(s["x"] - poz[0]) > ZASIEG_X or abs(s["y"] - poz[1]) > ZASIEG_Y:
                continue
            if self.potwory is not None and s["nazwa"].casefold() not in self.potwory:
                continue
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
        if self.czas_s and self.zegar() - self.start >= self.czas_s:
            log("Upłynął limit czasu.")
            return False
        if self.okrazenia and self.okrazenie >= self.okrazenia:
            log("Wykonano zadaną liczbę okrążeń.")
            return False
        self.walka_odl_tick = None          # Q5 11.10: ustawia walcz() w tym obiegu (pauza po ticku zależy od odległości)
        t_start = self.zegar()
        g = self.gracz()
        poz = self.postac.pozycja()
        teraz = self.zegar()
        fazy = {"gracz": teraz - t_start}
        self.zapamietaj_pole(poz)
        self.exp_przed, self.exp_teraz = self.exp_teraz, g.get("exp")
        if self.ruch_poz != tuple(poz):
            self.ruch_poz, self.ruch_czas = tuple(poz), teraz
            self.aktywnosc_ts = teraz
        if self.cel is not None or str(self.stan) == "WALKA":
            self.aktywnosc_ts = teraz      # walka z miejsca to nie bezczynność
        if g.get("max_hp"):
            pct = 100.0 * g["hp"] / g["max_hp"]
            self.hp_hist = [(t, p) for t, p in self.hp_hist if teraz - t <= GRYZIE_OKNO] + [(teraz, pct)]
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
            if g["proc"] >= self.wznowienie_hp:
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
        # leczenie czarem (exura): także w walce/pościgu; ucieczka (HP <= próg) ma pierwszeństwo, bo wtedy proc <= prog
        if self._zdrowie_czar_tick(g, poz, teraz):
            return True

        # pola ognia: odświeżenie wykrycia (co OGIEN_ODSWIEZ_S) i zejście z pola, na którym stoimy;
        # po leczeniu, przed ucieczką, lootem, ML i walką (każdy obieg w ogniu to kolejne 10 HP)
        self._ogien_tick(poz, teraz)
        if self._ogien_wyjdz(poz, teraz):
            return True

        if self.ucieczka:
            self.cel = None
            if self.lww:
                self._lww_przerwij("ucieczka", teraz, pilne=True)
            if self.pamiec:
                self._pamiec_koniec("przerwany", "ucieczka", poz)
            return self.uciekaj(g, poz)

        # wyprawa do depo po potwierdzonym głodzie startuje także w walce: od teraz biegniemy (bez walki), bijemy
        # tylko gdy droga zablokowana (_wypad_bieg); bez tego trolle w jaskini blokowałyby wyjazd w nieskończoność
        if self.wyprawa is not None and not self.wypad_aktywny:
            fn = getattr(self.wyprawa, "okazja_w_walce", None)
            if fn is not None and fn(teraz):
                self.cel = None

        # jedzenie czarem (exevo pan): gdy brak jedzenia w plecaku; potem istniejące jedzenie
        if self._jedzenie_czar_tick(g, poz, teraz):
            return True
        # jedzenie: także w walce, bo regeneracja (i głód) nie zależy od walki
        if self.jedzenie_potrzebne(g, teraz, poz):
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
        self._straznik_postepu(g, poz, teraz)

        # 2. obcy gracz: zatrzymuje tylko groźny (GM/CM/God/Tutor, czaszka/PK) albo każdy przy stop_przy_graczach
        if self.zatrzymaj_przy_graczu:
            obcy = self.inni_gracze(lista, poz)
            grozni = [s for s in obcy if self.stop_przy_graczach or self.gracz_grozny(s)]
            if grozni:
                nazwy = ", ".join(s["nazwa"] for s in grozni)
                self.ustaw_stan("GRACZ", nazwy)
                if teraz - self.ostatni_alarm > 15:
                    self.ostatni_alarm = teraz
                    self.alarm("gracz na ekranie: " + nazwy)
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

        # 2a''. runa (F4) w walce: przed ML i meleem, po leczeniu i jedzeniu
        if self._runa_tick(g, poz, lista, teraz):
            return True

        # 2a UH (uh.py): robienie run w spokoju; po leczeniu/jedzeniu, przed ML (ma pierwszeństwo przy mana >= UH_MANA_MIN)
        if self._uh_tick(g, poz, lista, teraz):
            return True

        # 2a'. ML: czar na magic level (tylko w spokoju; rzut pochłania obieg)
        if self._ml_czar_tick(g, poz, lista, teraz):
            return True

        # 2b. pościg na pamięć: ranny cel zniknął z widoku żywy, idziemy za nim (do POSCIG_PAMIEC_S s)
        if self.pamiec and self.cel is None and not (self.dojscie_aktywne and DOJSCIE_BIEGNIJ) \
                and self._pamiec_tick(g, poz, lista, teraz):
            return True

        # 3. walka
        ludzie = {s["id"]: s for s in lista}
        if self.cel and self.cel["id"] not in ludzie:
            return self.zgon_celu(g, poz, pewny=False)
        if self.cel and ludzie[self.cel["id"]].get("hp", 100) <= 0:
            return self.zgon_celu(g, poz, pewny=True)
        kand = self._unikanie_filtr(self.kandydaci(lista, poz), poz)   # moby przy graczu: nie kradniemy
        biegnij = self._wypad_bieg(kand, poz, teraz)
        if biegnij:
            if self.cel:
                log(f"{'Dojście' if self.dojscie_aktywne else 'Wypad'}: biegnę, nie walczę z {self.cel['nazwa']} (droga wolna).")
                self.cel = None
            kand = []
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
            kolejka = sorted(kand, key=klucz)
            cel = kolejka[1] if len(kolejka) > 1 and random.random() < DRUGI_CEL else kolejka[0]
            if self.pamiec_znaleziony:
                # cel odnaleziony po zniknięciu: wracamy do dobicia właśnie jego (chyba że gryzie nas świeży)
                w = next((x for x in kand if x["id"] == self.pamiec_znaleziony[0]), None)
                if w is not None and not gryzie:
                    cel = w
            roz = self.rozprawa
            if roz:
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
            log(f"Nowy cel: {cel['nazwa']} ({cel['x']},{cel['y']}) HP {cel['hp']}%")
        if cel is not None:
            self.zapamietaj_ruch_celu(cel)
            self.cel.update(poz=(cel["x"], cel["y"], cel["z"]), hp=cel["hp"], odl=self.dystans((cel["x"], cel["y"]), poz))
            return self.walcz(cel, g, poz)

        if self.lww is not None:
            self._lww_przerwij("brak_celu", teraz, pilne=True)
        if self.lww_zalegle is not None:
            self._lww_zamknij_zalegle(teraz, poz, lista)
        # przerwa od gry (nieregularnie, patrz PRZERWA_CO_MIX); kończy się wcześniej, gdy coś podejdzie
        if teraz >= self.przerwa_od and not self.wypad_aktywny and not (self.dojscie_aktywne and DOJSCIE_BIEGNIJ):
            if self.przerwa_do is None:
                self.przerwa_do = teraz + losuj_z_mieszanki(PRZERWA_DLUGOSC_MIX)
                log(f"Przerwa na {self.przerwa_do - teraz:.0f} s.")
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
        if self.loot and not (WYPAD_BIEGNIJ and self.wypad_aktywny) and not (self.dojscie_aktywne and DOJSCIE_BIEGNIJ):
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
        if not self.loot or not self.zwloki_czekajace or self.w_lootcie or self.lww is not None:
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

    def _watchdog_wyjatek(self):
        """Stany, w których bezczynność jest zamierzona (pauza/rozmowa mózgu, przerwa, wypad, jedzenie, pochodnia)."""
        if str(self.stan).startswith(("PAUZA", "PRZERWA", "WYPAD", "JEDZENIE", "POCHODNIA", "MOZG", "GRACZ", "UCIECZKA")):
            return True
        if self.przerwa_do is not None:
            return True
        teraz = self.zegar()
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
        bez blokad (jak w droga()): None = brak drogi."""
        if self.mapa_zna(start, cel):
            z = start[2]
            blok = list(zajete) + [p for p in list(self.sciany) if p[2] == z and self.sciana(p)]
            return self.mapa.droga(start, cel, blok, 1, skosy, limit=MAPA_LIMIT, znane=self._pola_pietra(z))
        return self._droga_znane(start, cel, zajete, 1, skosy)

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
        self._tele_poscig("poscig_start", cel=cel["nazwa"], odl=odl0, hp_celu=cel.get("hp"))
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
                               and not (m.get("gracz") and m.get("nazwa") == self.postac.nazwa)}
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
                              puszczenia=puszczenia_t or None,
                              kliki_ataku=getattr(self, "kliki_ataku_poscig", 0) - kliki0,
                              t_pierwszy_krok=round(t_pierwszy_krok, 2) if t_pierwszy_krok is not None else None)
        return None if wynik is None else True

    def walcz(self, cel, g, poz):
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
            if ramka is not False:
                self.klik_ramka_false.pop(cel["id"], None)
            elif ATAK_LIMIT_KLIKOW:
                n = self.klik_ramka_false.get(cel["id"], 0) + 1
                self.klik_ramka_false[cel["id"]] = n
                if n > ATAK_LIMIT_KLIKOW:
                    # klik nie działa (zła pozycja gracza, stary cel w grze, "Sorry, not possible."): nie klikamy w nieskończoność
                    log(f"[ATAK] {n - 1} klików bez efektu w {cel['nazwa']} id{self._koncowka_id(cel['id'])}, "
                        f"Escape i ignoruję cel na {ATAK_LIMIT_IGNOROWANIE} s.")
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
        zyje = self.zywy_w_poblizu([x for x in self.ostatnie_stwory if x["id"] != c["id"]], poz) \
            if self.loot and c.get("poz") else None
        szybki = False
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
                              and not self._zywe_w_promieniu(swieze, poz, 1)
                              and not self._grozni_w_zasiegu(swieze, poz)
                              and not self._ogien_na(pola[0]))
                except Exception:
                    szybki = False
                if szybki:
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
        if not LOOT_W_WALCE or self.loot is None or not hasattr(self.loot, "krok_w_walce"):
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
            if opis in ("brak_okna", "brak_pamieci", "obce_okno", "stwor_na_zwlokach", "daleko", "na_zwlokach"):
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
        odl = LOOT_PRZEGLAD_ODL if self.przeglad_odl is None else self.przeglad_odl
        return any(self.dystans((s["x"], s["y"]), poz) <= odl for s in self.kandydaci(lista, poz))

    def zajete_bez_nas(self, poz):
        return [(s["x"], s["y"]) for s in self.ostatnie_stwory
                if s["z"] == poz[2] and s.get("hp", 100) > 0 and (s["x"], s["y"]) != tuple(poz[:2])
                and not (s.get("gracz") and s.get("nazwa") == self.postac.nazwa)]

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
        self.hp_wzrost = teraz
        self.hp_regen = teraz
        self.mana_wzrost = teraz        # po jedzeniu dajemy manie JEDZENIE_MANA_BRAK_S na ruszenie
        self.pauza(0.5, 1.2)

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

    def _wroc_na_trase(self, poz):
        """Po utknięciu: najbliższy punkt trasy PO DRODZE (A*, nie Manhattan) i idx na niego.
        True, gdy jakiś punkt jest osiągalny."""
        n = len(self.punkty)
        z = poz[2]
        kand = sorted((k for k in range(n) if self.punkty[k][2] == z),
                      key=lambda k: self.dystans(poz, self.punkty[k]))[:UTKNIECIE_KAND]
        najlepszy = None
        teraz = self.zegar()
        zakaz = self.__dict__.setdefault("utk_zakaz", {})   # punkt -> do kiedy pomijany po powtórnym utknięciu
        for k in kand:
            q = self.punkty[k]
            if zakaz.get(k, 0) > teraz:
                continue
            d = [] if tuple(poz[:2]) == q[:2] else self.droga(tuple(poz), q[:2], dlugosc=0)
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
        if k == self.idx:
            zakaz[k] = teraz + 180.0
            log(f"utknięcie: punkt {k} nieosiągalny mimo bliskości, pomijam go na 3 min")
            alt = sorted((kk for kk in kand if kk != k and zakaz.get(kk, 0) <= teraz),
                         key=lambda kk: (kk - k) % n)
            if alt:
                k = alt[0]
                najlepszy = ((self.dystans(poz, self.punkty[k]),), k)
        self.utkniecia_trasy += 1
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
        if not v or self.wypad_aktywny:
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
        if not r:
            return False
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
        return self.pietra.tick(poz, cel)

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

    def pole_zmiany_pietra(self, pole):
        """True, gdy wejście na to pole (x, y, z) zmieniłoby piętro, a zmiana jest zakazana (poza wypadem)."""
        if not self._zakaz_aktywny():
            return False
        return (pole[0], pole[1]) in self._zakaz_pol(pole[2])

    def _zakaz_lista(self, start, cel):
        """Pola zmiany piętra w prostokącie start-cel (+ margines drogi) jako lista (x, y, z) dla A*."""
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
        return bool(PATROL_PIETRA and TRASA_PIETRA and self.przejscia and not self.wypad_aktywny)

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
        """Wizyta w miejscu m: droga A* z bieżącej pozycji; None (i blokada miejsca), gdy drogi nie ma."""
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
        if self._patrol_sweep_buduj(p, poz, teraz):
            powod += ", sweep zachodu"
        log(f"Patrol: cel m{m['id']} ({m['x']},{m['y']}) {powod}, droga {len(p['seg'])} pól{wtxt}.")
        self._patrol_tele("patrol_cel", id=m["id"], x=m["x"], y=m["y"], powod=powod, droga=len(p["seg"]),
                          waga=round(waga, 4) if waga is not None else None, poz=list(poz[:3]))
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
        """Losuje następne miejsce (waga: udział zabić z dolnym progiem, odległość, kara za niedawne wizyty);
        None, gdy żadne nie jest osiągalne. Pierwszy wybór po starcie / wypadzie: najbliższe miejsce."""
        kand = self._patrol_kandydaci(poz, pomin)
        if not kand:
            return None
        if self.patrol_pierwszy:
            self.patrol_pierwszy = False
            for m, d in sorted(kand, key=lambda md: md[1])[:6]:
                p = self._patrol_nowy(poz, m, "najbliższe")
                if p is not None:
                    return p
            return None
        hist = self.patrol_historia
        pula = [(m, d) for m, d in kand if d >= PATROL_ODL_MIN] or kand
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
            p = self._patrol_nowy(poz, m, "losowo", waga=wagi[i] / (sum(wagi) or 1.0))
            if p is not None:
                return p
            pula = [(mm, dd) for mm, dd in pula if mm["id"] != m["id"]]
            if not pula:
                break
        return None

    def _patrol_dotarl(self, p, poz, teraz):
        m = p["m"]
        p["faza"] = "postoj"
        p["t_dotarl"] = teraz
        p["zab_dotarl"] = self.patrol_zabicia
        p["do"] = teraz + random.uniform(*PATROL_POSTOJ)
        self.patrol_historia.append(m["id"])
        del self.patrol_historia[:-40]
        self.patrol_ost[m["id"]] = teraz
        if p.get("sweep"):
            self._patrol_sweep_zalicz(p, teraz)
        elif m.get("zrodlo") != "B":
            self.sweep_wschod += 1
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
                return None
        luka = p["tick"] is not None and teraz - p["tick"] > PATROL_LUKA_S
        dt = min(teraz - p["tick"], 2.0) if p["tick"] is not None else 0.0
        p["tick"] = teraz
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
                self._patrol_zakoncz(p, "ok")
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
        if self._wypad_tick():
            return True
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
        self.ustaw_stan("IDZ", f"punkt {self.idx}/{len(self.punkty)}")
        x, y, z = self.postac.pozycja()
        self._unikanie_trasa((x, y, z))      # gracz w pobliżu: inny punkt rotacji / cofnięcie (unikanie.py)
        if self._pietra_wlaczone() and self._trasa_stop_potwor((x, y, z)):
            return True                      # potwór tuż obok: ani krok trasy, ani przejście pięter; walka w następnym obiegu
        # punkty już osiągnięte zaliczamy od razu, bez pustego obiegu pętli; przy chodzeniu
        # kliknięciem postać mija kilka punktów między obiegami, więc szukamy jej pozycji do przodu
        n = len(self.punkty)
        for dalej in range(min(10, n)):
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
                        koniec_okrazenia = True
                if koniec_okrazenia and self.dojscie_aktywne:
                    # P7e: trasa dojścia jest jednokierunkowa: koniec bez osiągnięcia celu = porażka próby, bez odwracania
                    self.dojscie_porazka = True
                    log(f"Dojście: koniec trasy w {(x, y, z)} bez osiągnięcia celu, kończę próbę (bez odwracania).")
                    return True
                if koniec_okrazenia:
                    if self.otwarta or random.random() < ODWROCENIE_TRASY:
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
        if cel[2] != z and self._pietra_wlaczone():
            # kolejny punkt trasy leży na innym piętrze: przejście schodami/dziurą/drabiną (pietra.py)
            r = self._pietra_tick((x, y, z), cel)
            if r is not None:
                return r
        if self._utknieto_na_trasie((x, y, z), cel) and self._wroc_na_trase((x, y, z)):
            return True
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
