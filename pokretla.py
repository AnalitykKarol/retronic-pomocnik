"""Pokrętła na żywo: pomocnik/na_zywo.json czytany przez cavebota co tick (hot-reload po mtime).
Tylko klucze z ZAKRESY i tylko wartości w twardych granicach; reszta jest odrzucana z logiem.
Wartość = nadpisanie stałej modułu cavebot (klucz = nazwa stałej). Brak klucza w pliku = domyślna.
Auto-cofnięcie: zmiana z analityka jest oceniana po COFNIECIE_S wg zabić/min i odpuszczeń/min."""
import json
import time
from pathlib import Path

import instancja

PLIK = instancja.S.na_zywo      # bez RETRONIC_ID: pomocnik/na_zywo.json
# nazwa: (min, max); domyślna = wartość stałej w cavebot.py w chwili startu
ZAKRESY = {
    "POGON_ZASIEG": (10, 14),           # max odległość pościgu za celem poza ekranem
    "POGON_LIMIT": (12.0, 30.0),        # s bez zbliżania, potem odpuszczamy
    "POGON_IGNOROWANIE": (5, 90),       # s ignorowania odpuszczonego celu
    "OBJAZD_IGNOROWANIE": (20, 180),    # s ignorowania celu za ścianą
    "IGNOROWANIE": (20, 180),           # s ignorowania po limicie walki
    "IGNOROWANIE_BLISKO": (1, 5),       # ignorowany potwór tak blisko znów jest brany
    "LIMIT_WALKI": (40, 180),           # s na jeden cel
    "LOOT_PO_WALCE": (3, 8),            # min. odległość żywego celu blokująca loot
    "LOOT_BLOK_MAX": (5, 60),           # s wstrzymania lootu
    "KROKI_DO_ZWLOK": (10, 60),         # liczba prób podejścia do zwłok
    "CZEKAJ_BLISKO": (2, 5),
    "POSCIG_OKNO": (3.0, 5.0),          # s jednej szybkiej pętli pościgu
    "POSCIG_OKNO_DOBRY": (4.0, 8.0),    # s: okno przy dobrym postępie
    "POSCIG_KROK_MIN": (0.07, 0.2),     # s: min. odstęp między strzałkami w pościgu
    "POSCIG_PRZEGLAD": (0.4, 2.0),      # s: co ile przegląd HP/otoczenia w pościgu
    "POSCIG_BRAK_ZMIANY": (0.3, 1.0),   # s bez zmiany pozycji po strzałce = ściana/blokada
    "POSCIG_PONOW_BRAK": (0, 2),        # ponowienia strzałki po braku zmiany pozycji
    "POSCIG_TRZYMAJ": (0, 1),           # 1 = pościg trzymanym klawiszem (ciągły marsz), 0 = stuknięcia
    "JEDZENIE_ZAPAS_W_WALCE": (0, 1),   # 1 = F3 na zapas także w walce (mana >= 30, zapas < MIN, bez ucieczki/leczenia exura)
    "POSCIG_SKOS_AWARYJNY": (0, 1),     # 1 = gdy jedyne przejście jest po skosie (róg), pościg/podejście/krok idą skosem mimo KOSZT
    "POSCIG_SKOS_KOSZT": (1.0, 4.0),    # czas kroku po skosie / prostego; < 2 włącza skosy numpadem w pościgu
    "POSCIG_TRZYMAJ_PRZEGLAD": (0.2, 1.5),  # s: przegląd HP/otoczenia w trybie trzymania
    "POSCIG_VKROK_SCIANA": (0, 1),      # 1 = trzymany klawisz w ścianę po dojściu nie liczy się jako krok w toku (bez fałszywego zawracania)
    "POSCIG_OSTATNI_DOCISKAJ": (0, 1),  # 1 = klawisz trzymany dalej, gdy krok kończy przy celu dalszym niż 1 pole (bez postoju ~1,3 s)
    "POSCIG_PAMIEC": (0, 1),            # 1 = pościg na pamięć za celem, który zniknął z widoku żywy
    "POSCIG_PAMIEC_S": (3.0, 12.0),     # s: czas pościgu na pamięć
    "POSCIG_PAMIEC_POL": (4, 14),       # pola: najdalej tyle za ostatnią pozycją celu
    "POSCIG_PAMIEC_MAKS_ODL": (2, 10),  # pola: dalej niż tyle zniknął cel = bez pościgu na pamięć
    "LOOT_W_WALCE": (0, 1),             # 1 = loot odłożonych zwłok w trakcie walki (atomowe kroki); 0 tylko ręcznie
    "LOOT_W_WALCE_HP": (0, 95),         # % HP gracza: twarda dolna granica bezwzględna (domyślnie 0 = wyłączona)
    "LOOT_W_WALCE_HP_MARGINES": (15, 40),  # pp nad progiem ucieczki: HP wyżej niż prog_aktualny + margines pozwala lootować w walce
    "LOOT_W_WALCE_STYKAJACE": (1, 2),   # maks. żywych potworów w odl 1 przy lootowaniu w walce
    "WYPAD_PO_TORCHE": (0, 1),          # 1 = wypad do miasta po pochodnie; analityk nie może go wyłączyć (tylko w górę)
    "POCHODNIA_W_PRZERWIE": (0, 1),     # 1 = wymiana wypalonej pochodni także w trakcie zaplanowanej przerwy
    "WYPAD_ILE_TORCHY": (1, 10),        # ile pochodni mieć po zakupie u Al Dee
    "WYPAD_JEDZENIE": (0, 1),           # 1 = wypad po jedzenie (brak jedzenia + HP < WYPAD_JEDZENIE_HP)
    "LOOT_POD_NOGAMI_PIERWSZE": (0, 1), # 1 = loot próbuje własnego pola (0,0) zaraz po zgadniętym; 0 = dawne 3x3 po kolei
    "LOOT_MAKS_PROB": (1, 9),           # ile różnych pól maks. klikamy przy otwieraniu zwłok (dawne zachowanie ~9)
    "PATROL_WAGA_MIN": (0.0, 0.5),      # dolny próg wagi miejsca w losowaniu patrolu (miejsca bez pola "waga")
    "POSCIG_GRYZACY_MIN_HP": (0, 60),   # % HP celu: ranny cel w odl <= 3 nie jest porzucany przez gryzącego (0 = wyłączone)
    "ROZPRAWA_BLOK_MIN_HP_CELU": (0, 60),  # % HP celu: ranny cel w odl <= 2: obejście zamiast bicia blokującego (0 = wyłączone)
    "PATROL_POWROT_DO_CELU": (0, 1),    # 1 = po walce wracamy do pierwotnego celu patrolu zamiast brać bliższe miejsce
    "PATROL_POWROT_MAX_ODL": (10, 80),  # pola: dalszy pierwotny cel jest porzucany po walce
    "PATROL_SWEEP": (0, 1),             # 1 = wizyta w miejscu zachodnim (B) = przeczesanie nagranej trasy zachodu
    "PATROL_SWEEP_MIN_S": (60.0, 3600.0),  # s: min. przerwa między początkami sweepów zachodu
    "PATROL_SWEEP_WSCHOD_MIN": (0, 20),    # wizyt na wschodzie (nie-B) wymaganych po sweepie przed następnym
    "PATROL_CZAS_SKALA_S": (60.0, 3600.0), # s: waga miejsca rośnie o 1x co tyle od ostatniej wizyty
    "PATROL_CZAS_MAX": (0.0, 10.0),        # maks. dodatek do mnożnika czasu od ostatniej wizyty (0 = wyłączone)
    "TRYB_PATROL": (0, 1),              # 1 = patrol po miejscach (trasy/miejsca.json), 0 = pętla trasy łowiska
    "PATROL_PIETRA": (0, 1),            # 1 = patrol sięga miejsc na innych piętrach (plik miejsc z "przejscia", np. miejsca_troll.json)
    "PATROL_PIETRO_KARA": (0, 60),      # pola doliczane do odległości (wagi) miejsca za piętro różnicy
    "PATROL_GNIAZDO_MOBOW": (2, 10),    # miejsce/przejście z tyloma mobami naraz = gniazdo (wymaga HP i many)
    "PATROL_GNIAZDO_HP": (0, 100),      # % HP wymagane do wyboru gniazda (0 = bez warunku)
    "PATROL_GNIAZDO_MANA": (0, 100),    # % many wymagane do wyboru gniazda (0 = bez warunku)
    "PATROL_KOORD": (0, 1),             # 1 = koordynator miejsc między instancjami (miejsca_koord.py; domyślnie 0)
    "PATROL_KOORD_PROMIEN": (0, 30),    # pola: rezerwacja blokuje też miejsca tak blisko (0 = tylko to samo miejsce)
    "PATROL_MOBY_BEZP": (0, 6),         # tyle mobów naraz nie obniża wagi miejsca
    "PATROL_MOBY_KARA": (0.0, 2.0),     # waga miejsca /= 1 + KARA * (mobów - BEZP) (0 = bez wpływu)
    "PATROL_GRACZ_PAM": (0, 1),         # 1 = pamięć graczy: omijamy część spotu, w której niedawno widziano obcego gracza
    "PATROL_GRACZ_PAM_S": (30.0, 3600.0),  # s: jak długo ostatnia pozycja gracza zniechęca do miejsc w pobliżu
    "PATROL_GRACZ_PAM_R": (4, 40),      # pola: miejsce tak blisko ostatniej pozycji gracza dostaje karę
    "PATROL_GRACZ_PAM_KARA": (0.0, 1.0),  # mnożnik wagi takiego miejsca (0 = blokada)
    "MARSZ_KLIK": (0, 1),               # 20.10: 1 = marsz klikiem w patrolu/dojściu (klik w najdalsze pole drogi ze zwykłych pól, do MARSZ_KLIK_MAKS_POL; obserwacja ruchu, Escape przy walce); 0 = dotychczasowe chodzenie
    "KROK_BEZ_SCIAN": (0, 1),           # 20.10: 1 = krok_do po nieudanym pierwszym kierunku ponawia go raz i pomija zapasowe kierunki w pola, które mapa uznaje za ścianę; 0 = dotychczasowe
    "MARSZ_KLIK_MAKS_POL": (2, 7),      # pola: ile pól naprzód klikamy naraz w marszu klikiem
    "STWORY_WIDMA": (0, 1),             # 19.10: 1 = wpisy-widma (obcy gracz na polu bota, kilku graczy na jednym polu) nie liczą się do zajętości pól i oceny graczy; PK/GM widzą wszystko; 0 = stare zachowanie
    "POSCIG_BEZ_ZMIANY_PIETRA": (0, 1), # 1 = pościg nigdy nie wchodzi na schody/dziury (poza wypadem do miasta)
    "PET_WLACZONY": (0, 1),             # 17.10: 1 = przywołuj peta (utevo res) poza walką; domyślnie 0, tylko Karol
    "PET_MANA_MIN": (200, 1000),        # mana wymagana do przywołania (Elf Scout ok. 360)
    "PET_STABILNE_S": (10.0, 300.0),    # s na tym samym piętrze, zanim wolno przywołać
    "PET_PIETRO": (0, 15),              # 0 = piętro spota wykrywane; 1-15 = tylko to piętro (z)
    "PET_ZMIANY_MAX": (1, 6),           # tyle zmian pięter w oknie = spot wielopiętrowy, bez przywoływania
    "PET_ZMIANY_OKNO_S": (60.0, 3600.0),   # s okna liczenia zmian pięter
    "PET_PRZERWA_S": (10.0, 600.0),     # s min. odstęp między rzutami
    "PET_PORAZKI": (1, 10),             # czary z rzędu bez peta obok = przerwa
    "PET_PRZERWA_PO_PORAZKACH_S": (60.0, 7200.0),  # s przerwy po porażkach
    "PET_ZGONY_MAX": (0, 30),           # zgonów peta w sesji do zatrzymania przywoływania (0 = bez limitu)
    "TRASA_PIETRA": (0, 2),             # trasa wielopiętrowa w pętli łowiska: 0 = wył., 1 = zawsze, 2 = tylko gdy trasa ma > 1 piętro (domyślnie)
    "LOOT_PONOW_LOKALNIE": (0, 2),      # ile razy ponowić loot od razu po brak_okna, gdy w widoku brak żywych mobów
    "LOOT_POMIN_CIEZKIE": (0, 1),       # 1 = przedmiot za ciężki (cap) pomijamy w lootcie 300 s; 0 = tylko klasyfikacja w logu
    "UNIKANIE": (0, 1),                 # 1 = omijanie zwykłych graczy (zmiana punktu rotacji, pomijanie celów przy graczu)
    "CUDZY_MOB": (0, 1),                # 1 = nie bierz poranionego moba, którego nie zaczęliśmy, gdy niedawno był obcy gracz (17.10)
    "CUDZY_MOB_S": (10.0, 600.0),       # s: tak długo po zobaczeniu obcego gracza obowiązuje CUDZY_MOB (domyślnie 60)
    "PATROL_GRACZ_ZMIEN": (0, 1),       # 1 = obcy gracz blisko nas/celu patrolu = od razu zmiana respa na dalszy od niego (17.10)
    "PATROL_GRACZ_ZMIEN_R": (4, 20),    # pola: tak blisko nas albo celu obcy gracz wywołuje zmianę respa (domyślnie 12)
    "PATROL_GRACZ_ZMIEN_BLOK_S": (30.0, 1800.0),  # s: blokada miejsc przy graczu po zmianie respa (domyślnie 240)
    "PATROL_GRACZ_ZMIEN_PAUZA_S": (3.0, 120.0),   # s: min. odstęp między zmianami respa z tego powodu (domyślnie 15)
    "PK_OBRONA": (0, 1),                # 1 = atak gracza z danych (spadek HP + obcy obok + brak potwora) = ucieczka do depo
    "PK_ODL": (1, 3),                   # pola: obcy gracz tak blisko przy spadku HP = atak PK
    "PK_ODL_CZAR": (0, 8),              # pola: >0 = atak także od gracza w zasięgu czaru (0 = wyłączone)
    "PK_SPADEK_PP": (3.0, 40.0),        # pp: min. spadek HP w oknie uznawany za atak PK
    "PK_KARENCJA_MIN": (5, 240),        # min: tyle po ostatnim zobaczeniu wroga nie wracamy na spot
    "PK_WROG_WAZNY_H": (1, 720),        # h: wróg z listy wywołuje ucieczkę na sam widok
    "PK_LECZ": (0, 1),                  # 1 = leczenie po drodze do depo (exura F2, UH na siebie)
    "PK_DEPO_MAX_MIN": (5, 120),        # min: tyle w depo czekamy na regenerację HP, potem STOP + powiadomienie
    "PK_UH_HP": (0, 70),                # % HP: poniżej klikamy UH na siebie (0 = wyłączone)
    "PK_UH_SZYBKIE": (0, 1),            # 16.10 (SPEC R3+R4, P8): 1 = szybkie UH w ucieczce PK + ucieczka bez 8 s walki z mobem (domyślnie 0)
    "PK_UH_HP_SZYBKI": (30, 70),        # % HP: próg UH przy PK_UH_SZYBKIE=1 (nie niżej niż 30)
    "PK_UH_PREDYKCJA": (0, 1),          # 1 = spadek >= 15 pp w 2 s => UH już przy HP <= 50% (przy PK_UH_SZYBKIE=1)
    "PK_UH_CTRL": (0, 1),               # 1 = Ctrl+klik runy zamiast menu 'Use with' (UNKNOWN, czy działa w kliencie; domyślnie 0)
    "PVP_WALKA": (0, 1),                # 1 = z jedynym napastnikiem walczymy (HMM + UH/exura) zamiast uciekać; domyślnie 0 do próby na żywo
    "PVP_MAX_WROGOW": (1, 3),           # tylu napastników w widoku naraz dopuszcza wejście w walkę
    "PVP_DRUGI_ODL": (2, 8),            # pola: inny gracz tak blisko liczy się jako drugi napastnik
    "PVP_HP_MIN": (20, 100),            # % HP: wejście w walkę tylko przy HP >= tyle
    "PVP_UH_HP": (5, 60),               # % HP: <= tyle w walce -> UH na siebie (brak UH = ucieczka)
    "PVP_HMM_STOP_PP": (0, 40),         # pp nad PVP_UH_HP: tam bez strzału HMM, tylko leczenie (0 = strzelamy do końca)
    "PVP_EXURA_HP": (30, 95),           # % HP: <= tyle w walce i jest mana -> exura
    "PVP_HMM_CO_S": (1.0, 5.0),         # s: odstęp między strzałami HMM
    "PVP_ZASIEG": (1, 7),               # pola: dalej od napastnika nie strzelamy, tylko podchodzimy
    "PVP_POGON": (0, 6),                # pola: tyle najdalej od miejsca startu walki gonimy napastnika
    "PVP_ZNIKL_S": (2.0, 30.0),         # s: napastnik poza widokiem/zasięgiem tak długo = koniec walki
    "PVP_ZABITY_HP": (0, 40),           # % HP napastnika: zniknięcie przy HP <= tyle = zabity
    "PVP_HMM_PORAZKI": (1, 10),         # nieudane strzały HMM z rzędu = ucieczka
    "PVP_SKOK_POL": (10, 100),          # pola: przeskok pozycji w walce większy niż tyle = śmierć (teleport do świątyni)
    "UNIKANIE_PROMIEN": (5, 12),        # pola: gracz tak blisko włącza unikanie
    "UNIKANIE_PROMIEN_MAX": (10, 20),   # pola: dalej gracz się nie liczy
    "UNIKANIE_MOB_PROMIEN": (2, 8),     # pola: moby tak blisko gracza nie są celami
    "UNIKANIE_PUNKT_D": (3, 10),        # pola: punkt trasy bliżej gracza jest pomijany
    "UNIKANIE_DROGA_MIN": (2, 6),       # pola: droga do punktu nie schodzi bliżej gracza
    "UNIKANIE_BLOK_S": (20.0, 120.0),   # s blokady bez zmiany, potem inny punkt rotacji / luz
    "UNIKANIE_ZNIKL_S": (5.0, 30.0),    # s bez gracza = koniec unikania
    "UNIKANIE_TOR": (0, 1),             # 1 = nie idziemy za graczem (kierunek jego ruchu), pamięć gracza po zniknięciu (17.10)
    "UNIKANIE_TOR_OKNO_S": (2.0, 10.0),  # s historii pozycji do kierunku ruchu gracza
    "UNIKANIE_TOR_RUCH_MIN": (1, 5),    # pola: mniej = gracz stoi
    "UNIKANIE_TOR_ZASIEG": (6, 20),     # pola: dalej gracz nie wyznacza toru
    "UNIKANIE_TOR_LOOK": (4, 16),       # pola drogi branych do kierunku
    "UNIKANIE_TOR_PAMIEC_S": (0.0, 120.0),  # s pamięci gracza po zniknięciu z widoku
    "UNIKANIE_PRZERWA": (0, 1),         # 1 = gracz w promieniu kończy PRZERWĘ
    "MIJANIE": (0, 1),                  # 18.10: 1 = mijanie graczy po ludzku (kierunek gracza względem pętli, bez bańki i dreptania) zamiast unikanie.decyduj; 0 = dotychczasowe UNIKANIE_*
    "MIJANIE_PRZOD": (6, 30),           # punkty trasy przed nami, na których gracz leży na naszej drodze
    "MIJANIE_TRASA_R": (1, 4),          # pola: idący gracz tak blisko punktu trasy leży na naszej drodze
    "MIJANIE_OBOZ_S": (1.0, 3.5),       # s bez ruchu, zanim gracz jest obozowiczem (obserwacja liczona w oknie UNIKANIE_TOR_OKNO_S = 4 s: wyżej obozowicz nie powstałby nigdy)
    "MIJANIE_OBOZ_R": (2, 6),           # pola: komora obozowicza
    "MIJANIE_OBOZ_BLISKO": (0, 6),      # pola: gracz bez kierunku tak blisko nas nie jest obozowiczem (0 = wyjątek wyłączony)
    "MIJANIE_OBOZ_PAMIEC_S": (10.0, 600.0),  # s: decyzja wobec obozowicza wygasa po tylu s
    "MIJANIE_OBOZ_ODWROTY": (1, 5),     # odwróceń obiegu przez tego samego obozowicza w 120 s, potem przechodzimy obok niego
    "MIJANIE_SKROT_MAX": (10, 80),      # pola: najdłuższy skrót omijający komorę obozowicza
    "MIJANIE_ZNIKL_S": (2.0, 30.0),     # s poza widokiem = kolejne spotkanie z tym graczem
    "MIJANIE_PRZEJSCIE_ODL": (2, 10),   # pola: dalej idącego na nas gracza nie ustępujemy
    "MIJANIE_BOK_R": (2, 10),           # kroki: zasięg szukania wnęki do ustąpienia
    "MIJANIE_POSTOJ_S": (3.0, 30.0),    # s: bezpiecznik postoju przy ustępowaniu
    "MIJANIE_PONOW_S": (5.0, 120.0),    # s: odstęp między ustąpieniami temu samemu graczowi
    "TRASA_STOP_PRZY_POTWORZE_R": (0, 8),  # pola: potwór w tym promieniu wstrzymuje krok trasy/przejście pięter (0 = wył.)
    "JEDZENIE_W_WALCE": (0, 1),         # 1 = jedzenie także w walce, gdy HP nie rośnie z regeneracji (głód) i jest bezpiecznie
    "CZAS_JEDZENIA_WALKA": (10.0, 60.0),   # s bez wzrostu HP (nie od exura) w walce = głód
    "JEDZENIE_WALKA_HP_MARGINES": (10, 60), # pp nad progiem ucieczki, od których wolno jeść w walce
    "JEDZENIE_MANA_BRAK_S": (30.0, 600.0),  # s: mana < max, bez rzutu czaru i bez wzrostu tyle czasu = głód (jemy)
    "ML_CZAR_AKTYWNY": (0, 1),          # 1 = automatyczny czar na magic level (domyślnie 0)
    "ML_CZAR_KOSZT": (1, 500),          # koszt many czaru
    "ML_CZAR_MIN_PRZERWA_S": (2.5, 30.0),  # s: exhaust między rzutami
    "ML_CZAR_W_WALCE": (0, 1),          # 1 = rzucaj także z żywym mobem w pobliżu / w walce
    "ML_BLOK_HP": (0, 100),             # HP% poniżej + walka/mob w pobliżu = bez ML (mana zostaje na exurę)
    "ZDROWIE_CZAR_AKTYWNY": (0, 1),     # 1 = leczenie czarem exura (F2) także w walce (domyślnie 0)
    "ZDROWIE_CZAR_HP": (20, 100),       # HP% poniżej którego leczymy exura (100 = zawsze, gdy HP < 100%)
    "JEDZENIE_CZAR_AKTYWNY": (0, 1),    # 1 = exevo pan (F3) zamiast wypadu po jedzenie (domyślnie 0)
    "WYPRAWA_AKTYWNA": (0, 1),          # 1 = wyprawa po zapasy do Thais (wyprawa.py; domyślnie 0)
    "WYPRAWA_ZAPAS_PROG": (0, 20),      # sztuk jedzenia poniżej których ruszamy (0 = JEDZENIE_ZAPAS_MIN)
    "WYPRAWA_JEDZENIE_CEL": (1, 40),    # docelowa liczba sztuk jedzenia po zakupie
    "WYPRAWA_JEDZENIE_DOKUP": (0, 20),  # dokup ponad cel po zjedzeniu u NPC
    "WYPRAWA_JEDZ_NA_MIEJSCU": (0, 1),  # 1 = jemy u NPC do "full"
    "WYPRAWA_JEDZ_MAKS": (1, 30),       # maks. zjedzonych sztuk przy NPC
    "WYPRAWA_BLANKI": (0, 100),         # docelowa liczba blank run (0 = nie kupuj)
    "WYPRAWA_BLANKI_PROG": (1, 50),     # poniżej tylu blanków wyprawa startuje z tego powodu
    "WYPRAWA_BLANKI_MAX_KOSZT": (0, 5000),  # gp: limit wydatku na blanki
    "WYPRAWA_POCHODNIE": (0, 1),        # 1 = pochodnie u Gorna przy okazji
    "WYPRAWA_CAP_REZERWA": (0, 100),    # oz capa wolne po zakupach
    "WYPRAWA_ZLOTO_MIN": (0, 100000),   # gp: poniżej wyprawa nie startuje
    "WYPRAWA_MIN_HP": (30, 100),        # % HP do startu
    "WYPRAWA_CO_MIN": (1, 240),         # min: odstęp między wyprawami
    "WYPRAWA_MAX_CZAS_S": (300, 7200),  # s: twardy limit czasu wyprawy
    "WYPRAWA_MAX_KROKOW": (500, 50000), # twardy limit obiegów wyprawy
    "WYPRAWA_STOP_PRZY_UTKNIECIU": (0, 1),  # 1 = alarm + STOP przy utknięciu w mieście
    "WYPAD_BIEGNIJ": (0, 1),            # 1 = w wypadzie biegniemy, walka tylko gdy droga zablokowana
    "WYPAD_BLOK_S": (1.0, 10.0), "WYPAD_WALKA_S": (3.0, 20.0), "WYPAD_PETLA_S": (0.0, 30.0), "WYPAD_PETLA_PROMIEN": (1, 6),
    "WYPRAWA_DEPO_BLANKI": (0, 1),      # P7b: 1 = w trybie TYLKO_DEPO sam brak blanków = wyprawa do depo (domyślnie 1)
    "WYPRAWA_PO_DEPO_S": (0, 7200),     # P7c: s karencji wyprawy po depo (liczy się max z WYPRAWA_CO_MIN)
    "BLANKI_AUTO_BAG": (0, 1),          # N9: 1 = blanki do bagu na runy poza wyprawą (start + okresowo w spokoju)
    "BLANKI_AUTO_BAG_MIN": (1, 120),    # N9: min odstępu między próbami
    "WYPRAWA_PO_DOJSCIU_S": (0, 3600),  # P7a: s karencji wyprawy po dojściu z depo na spot
    "DOJSCIE_WALKA_PRZEJSCIE_S": (0, 120),  # P7d: s walki do skutku przy blokującym stworze przy dziurze/schodach w dojściu (0 = 8 s jak dawniej)
    "DOJSCIE_BEZ_UNIKANIA_POL": (0, 60),    # P7f: >0 = w tylu polach od początku dojścia (depo) bez unikania graczy (domyślnie 0)
    "DOJSCIE_PROBY": (3, 8),            # P7e: liczba prób dojścia od aktualnej pozycji
    "DOJSCIE_PAUZA_PROBY_S": (0.0, 15.0),   # P7e: s pauzy przed kolejną próbą dojścia
    "DOJSCIE_BIEGNIJ": (0, 1),          # 1 = w dojściu na spot (powrót z depo) biegniemy bez walki/lootu; bijemy tylko blokujące moby
    "PIETRA_LOPATA_TYLKO_Z7": (0, 1),   # 1 = łopata tylko na z7 (wejście z powierzchni), 0 = na każdym piętrze
    "PIETRA_LOPATA_BRAK_S": (60.0, 3600.0),  # s przerwy w próbach łopaty po braku jej w plecaku
    "WPADNIECIE": (0, 1),               # 15.10: 1 = niespodziewana zmiana piętra (upadek w dziurę): nauka dziury, wyjście liną / planem po mapie, w ostateczności ALARM + STOP
    "WPADNIECIE_LINA": (0, 1),          # 1 = pierwsza próba wyjścia: Use liny na polu lądowania (rope spot pod dziurą)
    "WPADNIECIE_LINA_PROB": (1, 5),     # prób liny przed planem po mapie
    "WPADNIECIE_PLAN": (0, 1),          # 1 = gdy lina nie działa, plan wielopiętrowy po mapie i przejściach z danych (pietra.py)
    "WPADNIECIE_POSCIG": (0, 1),        # 20.10: 1 = upadek w dziurę w trakcie pościgu też jest wykrywany (ostatnia próbka odświeżana w pętli); domyślnie 0
    "WPADNIECIE_WALIDACJA": (0, 1),     # 1 = nauka dziury tylko z flagą 2 mapy i bez schodów w pobliżu (domyślnie 0)
    "WPADNIECIE_ODL": (1, 6),           # pola: lądowanie tak blisko poprzedniej pozycji = upadek (dalej: teleport/śmierć)
    "DZIURA_PRZY_CELU": (0, 1),         # 15.10: 1 = nie atakujemy/nie gonimy celu stojącego przy znanej dziurze, gdy klient szedłby przez nią
    "DZIURY_NAUCZONE": (0, 1),          # 1 = pola z trasy/dziury_nauczone.json są ścianą dla dróg A* i kroków
    "PIETRA_LOPATA": (0, 1),            # 1 = wejście dziurą w dół: po nieudanym kroku odkopanie dziury łopatą z plecaka
    "PIETRA_TRYBY_Z_DANYCH": (0, 1),    # R1b: 1 = przejścia pięter tylko skutecznymi trybami (krok na schodach, R z drabiny ze skosu), start ortogonalny tylko dla kroku
    "PIETRA_CZEKAJ_KROK_S": (0.0, 4.0),  # R1b: s czekania na zmianę piętra po kroku (0 = dawne 2,0 s i dłuższe odstępy)
    "PIETRA_CZEKAJ_R_S": (0.0, 4.0),    # R1b: s czekania na zmianę piętra po R (Ctrl+klik)
    "PIETRA_DOMYSL_PROMIEN": (0, 10),   # R1b: promień (pola od gracza) kandydata "domysł" z flagą mapy; 0 = dawne bez sprawdzenia
    "PIETRA_PRE_MAX": (0, 8),           # R1b: max pre-kroków na pole startowe (0 = dawne 8 ruchów)
    "PIETRA_ZAJETE_MAX_S": (0.0, 60.0),  # 15.10: s czekania/bicia przy zajętym polu przejścia pięter (stwór/gracz na linie), próby niezliczane; 0 = wyłączone
    "PIETRA_ZAJETE_ATAK": (0, 1),       # 15.10: 1 = stwór na polu przejścia atakujemy niezależnie od listy łowiska
    "PIETRA_STARTY_DOMYSLNE": (0, 1),   # R1b: 1 = zasiane dobre pola startowe z pietra_starty_domyslne.json
    "WYPRAWA_DEPO_POWROT": (0, 1),      # 1 = po dojściu do depo wyprawa sama wraca na spot (bez STOP)
    "WYPRAWA_DEPO_POSTOJ_S": (0, 600),  # s: postój w depo przed powrotem
    "WYPRAWA_DEPO_W_WALCE": (0, 1),   # 1 = wyprawa do depo po głodzie startuje także w walce (biegnie, bije tylko zablokowana)
    "WYPRAWA_DEPO_ZLOZ": (0, 1),        # 1 = wyprawa najpierw składa UH w depo (skrzynia obok pola depo), potem Frodo/Xodet
    "JEDZENIE_BRAK_WALIDUJ": (0, 1),    # 1 = nieudane jedzenie przy nieczytelnych kontenerach nie jest dowodem braku jedzenia (domyślnie 1)
    "JEDZENIE_BRAK_PROBY": (1, 5),      # odczytów kontenerów po nieudanym jedzeniu, zanim uznamy je za nieczytelne
    "GLOD_ZAPAS_WAZNY_S": (30, 600),    # s: potwierdzony głód wyprawy wymaga wiarygodnego odczytu zapasu w tym oknie
    "WYPRAWA_WZNOW_WALIDUJ": (0, 1),    # 1 = po restarcie wyprawa po jedzenie wygasa, gdy powód (zapas/głód) już nie zachodzi
    "WYPRAWA_JEDZENIE": (0, 1),         # 0 = brak jedzenia nie jest powodem wyprawy (zostają blanki itd.; domyślnie 1)
    "WYPRAWA_CZEKAJ_NA_GLOD": (0, 1),   # 1 = powody zapas/glod dopiero po potwierdzonym głodzie (nieudana próba jedzenia)
    "WYPRAWA_DOJSCIE_PATROLEM": (0, 1),  # 1 = start/utknięcie wyprawy poza częścią jaskini połączoną z planem: najpierw dojście drogą patrolu (schody z pliku miejsc), nie od razu alarm
    "WYPRAWA_TYLKO_DEPO": (0, 1),       # 1 = wyprawa kończy się w depo (bez zakupów, bez powrotu): alarm + STOP (tryb wyprawa_depo)
    "WYPRAWA_MARSZ_KLIK": (0, 1),       # 1 = w drodze do miasta/depo klik w mapę zamiast kroków (wypad.py, marsz_klik.py); 0 = jak dotąd
    "WROC_REFILL": (0, 1),              # 1 = po dojściu do depo (wroc.sh / wyprawa tylko-do-depo) automatyczny refill (refill_auto.py)
    "JEDZENIE_ZAPAS_MIN": (1, 20),      # poniżej tylu sztuk jedzenia w plecaku rzucamy exevo pan (przy JEDZENIE_CZAR_AKTYWNY=1)
    "OGIEN_UNIKAJ": (0, 1),             # 1 = omijaj pola ognia (wykrywane ze zrzutu), schodź z nich i nie lootuj z ognia (domyślnie 1)
    "RUCH_OKNO": (0, 1),                # 1 = rekord telemetrii ruch_okno co 30 s (R0b, bez wpływu na zachowanie)
    "RUCH_PROBKA_WCZESNA": (0, 1),      # 1 = próbka telemetrii także przy wczesnym zakończeniu obiegu (R0b)
    "OGIEN_STALY": (0, 1),              # 1 = maska stałych pól ognia (widziane >= 20 razy przez >= 10 min): bez logu i bez bloku drogi (domyślnie 1)
    "POSCIG_SKOSY_ZAPAS": (0, 1),       # 1 = bez drogi prostej druga próba ze skosami (korytarz skośny z8), też dla ignorowanych "za ścianą"
    "PATROL_ZAWROT": (0, 1),            # 15.10: 1 = zawrót z miejsca, gdy jest w widoku i puste
    "PATROL_RESPAWN_CIEN": (0, 1),      # 15.10: 1 = tryb cienia patrolu według respawnu: mapa obecności + wybór nowej metody w telemetrii (patrol_cel, D4), bez wpływu na ruch
    "PATROL_RESPAWN": (0, 1),           # 20.10: 1 = patrol idzie do celu wybranego metodą respawnu (mapa obecności), gdy metoda ma zdanie; inaczej losowanie wg wag. 0 = jak dotąd (SPEC_patrol_respawn_1015, krok 3)
    "OGIEN_IGNORUJ_S": (0, 60),         # 15.10: s ignorowania ognia po OGIEN_CZEKAJ_MAX_S bez drogi; 0 = nigdy
    "CZAT_SPOT_AKTYWNY": (0, 1),        # 15.10: 1 = wiadomość do gracza, który wraca na spot / zabiera moby (SPEC_czat_spot_1015)
    "CZAT_SPOT_SPOTKAN": (2, 10),       # S1: spotkań z tym samym graczem w CZAT_SPOT_OKNO_MIN
    "CZAT_SPOT_OKNO_MIN": (5, 60),      # S1: okno w minutach
    "CZAT_SPOT_CIAGLE_MIN": (2, 30),    # S2: minuty ciągłej obecności
    "CZAT_SPOT_ZABRANE": (1, 10),       # S3: zabranych mobów w 10 min
    "CZAT_SPOT_NICK_MIN": (10, 240),    # minuty między wiadomościami do tego samego gracza
    "CZAT_SPOT_ODPOWIEDZI": (0, 3),     # odpowiedzi modelu na jego odpisanie (0 = tylko dymek)
    "PATROL_RUNDA": (0, 1),            # 1 = każde miejsce patrolu raz na rundę (losowo wg wag), potem reset
    "PATROL_DRZWI": (0, 1),             # 1 = drzwi z trasy/drzwi_jaskinia.json to przejście dla pościgu i patrolu (zamknięte: Use, max 3 próby)
    "OGIEN_MASKA_TYLKO_SCIANY": (0, 1), # 1 = maska stałych pól ognia tylko dla pól-ścian wg mapy, nigdy pole przechodnie (domyślnie 1)
    "OGIEN_WYJDZ_POTWIERDZ": (0, 1),    # 1 = z pola ognia schodzimy tylko po potwierdzeniu (spadek HP albo to samo pole >= 1,6 s); w walce ze stworem obok tylko po spadku HP (domyślnie 1)
    "OGIEN_MASKA_DANE": (0, 1),         # 1 = trwała maska pól przechodnich z epizodów (>= 3 epizody w >= 2 godzinach bez spadku HP), omija OGIEN_MASKA_TYLKO_SCIANY (domyślnie 1)
    "OGIEN_POMIJAJ_PRZY_STWORZE": (0, 1),  # 1 = wykrycia ognia na polu stwora/celu i obok niego pomijamy, dopóki HP nie spadnie (domyślnie 1)
    "OGIEN_LOG_S": (1.0, 60.0),         # s: min. odstęp między wpisami "[OGIEN] pola" (domyślnie 10)
    "OGIEN_ODSWIEZ_WALKA_S": (0.8, 5.0),  # s: odstęp wykryć ognia w WALKA bez zmiennych pól (domyślnie 0.8 = bez zmiany)
    "RUNA_AKTYWNA": (0, 1),             # 1 = strzał runą (hotkey RUNA_KLAWISZ) w celu w walce (domyślnie 0)
    "RUNA_TRYB_KLIK": (0, 1),           # 1 = strzał runą kliknięciami (plecak -> Use with -> mob) zamiast hotkeya
    "RUNA_KLIK_CTRL": (0, 1),           # 1 = przy RUNA_TRYB_KLIK: Ctrl+lewy na runie, lewy na celu (bez menu i OCR; domyślnie 0)
    "RUNA_ID": (1, 65535),              # ID runy w plecaku do strzału (HMM 3198)
    "RUNA_MENU_DX": (0, 150),           # px: awaryjny offset "Use with" od kliknięcia (gdy OCR menu zawiedzie)
    "RUNA_MENU_DY": (0, 150),
    "RUNA_KLIK_PORAZKI": (1, 10),       # porażki z rzędu przed chłodzeniem
    "RUNA_KLIK_CHLODZENIE_S": (10.0, 900.0),
    "RUNA_INTERWAL_S": (1.0, 10.0),     # s: min. odstęp między strzałami runą (exhaust run w kliencie: >3 s, <= ok. 5 s)
    "RUNA_INTERWAL_MAX_S": (0.0, 10.0), # s: > RUNA_INTERWAL_S = odstęp losowy z [RUNA_INTERWAL_S, to] po każdym strzale (0 = stały)
    "UH_AKTYWNY": (0, 1),               # 1 = robienie run czarem runowym w spokoju (uh.py; domyślnie 0)
    "UH_KOSZT": (1, 500),               # koszt many czaru runowego
    "UH_MANA_MIN": (1, 500),            # mana wymagana do startu runy
    "UH_MIN_HP": (50, 100),             # % HP gracza wymagane do startu runy
    "UH_MOB_DYSTANS": (1, 10),          # pola (Chebyshev): stwory dalej nie blokują ani nie przerywają runy (gracz zawsze)
    "LOOT_DYNAMICZNY": (0, 1),          # 1 = loot dynamiczny w walce (zwłoki obok od razu, bez powtórek brak_okna, bez innego piętra; 0 = dawne)
    "UH_W_WALCE": (0, 1),               # 1 = runa także w trakcie walki, gdy mana prawie pełna (domyślnie 0)
    "UH_W_WALCE_MANA_MARGINES": (0, 50),  # w walce start przy mana >= max_mana - tyle (i >= UH_KOSZT)
    "UH_W_WALCE_DYSTANS": (0, 3),       # w walce stwór tak blisko blokuje/przerywa runę (0 = moby ignorowane)
    "UH_W_WALCE_SPADEK_HP": (5, 60),    # pp: spadek HP w trakcie runy w walce, od którego przerywamy
    "UH_W_WALCE_MIN_HP": (50, 100),     # % HP wymagane do startu runy w walce (w trakcie: minus 10)
    "UH_ODSTEP_S": (5.0, 600.0),        # s: min. odstęp między próbami
    "MODEL_TRASA_MIASTA": (0, 1),       # 1 = model może zmien_trase na trasę z "miasta" (domyślnie 0; mozg.py)
    "MODEL_TRASA_ZAMROZENIE_S": (30, 3600),  # s: bez ruchu postaci tak długo -> odrzucamy zmien_trase modelu (domyślnie 180; mozg.py)
    "MODEL_TRASA_MAX_ODL": (5, 500),    # pola (Chebyshev, bez z): zmien_trase na trasę dalszą niż to -> odrzucona (domyślnie 60; mozg.py)
    "TRADE_OGLOSZENIA": (0, 1),         # 1 = ogłoszenia [SELL] UH na zakładce Trade (domyślnie 0; mozg.py)
    "TRADE_MIN_S": (120, 900),          # s: min. odstęp między ogłoszeniami
    "TRADE_MAX_S": (120, 1800),         # s: max. odstęp między ogłoszeniami
    "TRADE_MIN_UH": (20, 2000),         # run UH w plecakach wymaganych do ogłoszenia (min. 20 = 1 pełny BP)
    "TRADE_PRIV_ODPOWIEDZI": (0, 1),    # 1 = prywatne odpowiedzi na pytania o kupno UH (domyślnie 0; mozg.py TradePriv)
    "RUNA_MIN_HP_CELU": (0, 100),       # nie strzelaj do celu o HP% poniżej tego (0 = bez limitu)
    # 13.10 (G2: spec P1/P2): twarde ignorowanie, strażnicy, blokujący na wyjściu
    "IGNOR_TWARDE": (0, 1),             # 1 = ignorowanie celu nie znika przy podejściu na IGNOROWANIE_BLISKO (domyślnie 1)
    "IGNOR_DROGA_CO_S": (0.5, 3.0),     # s: jak często sprawdzamy, czy za ścianą otworzyła się droga
    "ODPUSZCZ_LOG_S": (1.0, 30.0),      # s: log "Odpuszczam ... za ścianą" najwyżej raz na tyle s na id
    "BLOK_WYJSCIE": (0, 1),             # 1 = bij blokującego jedyne wyjście (zaułek) zamiast iść w stwora (domyślnie 0)
    "BLOK_KROKI": (1, 4),               # pola drogi sprawdzane pod kątem stworów
    "STRAZNIK_CEL": (0, 1),             # 1 = strażnik celu: Escape i klik po S1, twarde ignorowanie po S2 (domyślnie 1)
    "STRAZNIK_CEL_S1": (8.0, 20.0),     # s bez postępu przy celu obok: Escape + ponowny klik
    "STRAZNIK_CEL_PRZERWA": (2.0, 10.0),  # s przerwy między wywołaniami strażnika celu, po której okno liczy się od nowa
    "STRAZNIK_CEL_S2": (15.0, 40.0),    # s bez postępu: kontrola pozycji + ignorowanie
    "STRAZNIK_IGNOR_S": (20.0, 120.0),  # s ignorowania celu po S2
    "STRAZNIK_POSTEP": (0, 1),          # 1 = strażnik postępu globalny (domyślnie 0)
    "STRAZNIK_POSTEP_S1": (60.0, 180.0),   # s: reset stanu walki
    "STRAZNIK_POSTEP_S2": (120.0, 300.0),  # s: zmiana celu patrolu / skok na trasę
    "STRAZNIK_POSTEP_S3": (240.0, 600.0),  # s: powiadomienie krytyczne
    "DECYZJE_LOG": (0, 1),              # 15.10: 1 = telemetria "decyzja" (D1 wybór celu, D2 start pościgu) z opcjami; tylko log, bez wpływu na ruch
    "D3_LOG": (0, 1),                   # 16.10: 1 = telemetria D3 (zawieszka poza walką: "decyzja" D3 z opcjami wyjścia + "d3_wynik"); tylko log, bez wpływu na ruch
    "D3_PROG_S": (10.0, 300.0),         # s: pozycja w promieniu 2 pól poza walką tak długo = zawieszka (domyślnie 30)
    "D3_REAKCJA": (0, 1),               # 17.10 (F1): 1 = cień: rekord "d3_reakcja" z opcją, którą wybrałaby reguła; nic nie wykonuje (domyślnie 0)
    "RATUNEK_HAIKU": (0, 1),            # 19.10 (SPEC_ratunek_haiku_1019, F1): 1 = cień: detektor zachowań „jak bot” S1-S7 tylko loguje „wołałbym Haiku” (logi/ratunek-<data>.jsonl); 2 jeszcze nie istnieje
    "RATUNEK_HAIKU_PYTAJ": (0, 1),      # 19.10 (F2a): 1 (tylko przy RATUNEK_HAIKU=1) = Haiku W CIENIU przy każdym sygnale: osobny wątek, bez ruchu i bez zatrzymywania bota; rekord haiku_cien w logi/ratunek-<data>.jsonl
    "RATUNEK_PIETRO_S": (3.0, 120.0),   # S2: s poza walką na piętrze spoza trasy (domyślnie 10)
    "RATUNEK_STOI_S": (10.0, 300.0),    # S3: s w miejscu poza walką, exp bez zmian (domyślnie 30)
    "RATUNEK_STOI_PROMIEN": (1, 4),     # S3: promień „w miejscu” [pola] (domyślnie 2)
    "RATUNEK_KRAG_WIZYT": (3, 10),      # S4: wejść na to samo pole w oknie (domyślnie 4)
    "RATUNEK_KRAG_S": (20.0, 300.0),    # S4: okno [s] (domyślnie 60)
    "RATUNEK_OSC_N": (2, 10),           # S4: powrotów A-B-A w oknie (domyślnie 3)
    "RATUNEK_KROKI_N": (3, 20),         # S5: nieudanych kroków z rzędu (domyślnie 6)
    "RATUNEK_KLIK_N": (3, 20),          # S6: klików bez efektu (domyślnie 5)
    "RATUNEK_OKRAZENIA_N": (2, 10),     # S7: okrążeń w oknie bez ruchu (domyślnie 3)
    "RATUNEK_OKRAZENIA_S": (20.0, 300.0),  # S7: okno [s] (domyślnie 60)
    "RATUNEK_PRZERWA_S": (30.0, 1800.0),   # debounce sygnału w tym samym miejscu [s] (domyślnie 120)
    "RATUNEK_LIMIT_H": (1, 120),        # limit wywołań Haiku na godzinę (Q3, domyślnie 20); w cieniu tylko flaga
    "STRAZNIK_ORBITY": (0, 2),          # 20.10 (SPEC_orbity_straznik_1020, B): 0 = wyłączony; 1 = cień: log [ORBITA] + telemetria straznik_orbita; 2 = działa: stop chodzenia, jedna próba wyjścia, ALARM + STOP (domyślnie 0)
    "STRAZNIK_ORBITA_S": (30.0, 600.0),    # s okno orbity: >= 8 zmian pozycji w <= STRAZNIK_ORBITA_POL polach poza walką (domyślnie 60)
    "STRAZNIK_ORBITA_POL": (3, 12),     # maks. różnych pól orbity (domyślnie 6)
    "STRAZNIK_WYJSCIE_S": (30.0, 300.0),   # s na jedną próbę wyjścia (plan po mapie / A* do trasy), potem alarm (domyślnie 90)
    "D3_ALARM_S": (0.0, 1800.0),        # 17.10 (F1): >0 = zawieszka D3 trwająca tyle s => jedno powiadomienie krytyczne, bez STOP (domyślnie 0 = wyłączone)
    "SLEPOTA_DIAG_S": (0.0, 900.0),     # 19.10: s bez expa i potworów (bot polował) => zrzut diagnostyki do logi/slepota/ (0 = wyłączone)
    "SLEPOTA_RESTART_S": (0.0, 1800.0), # 19.10: s takiej ślepoty => restart mozg.py (0 = bez restartu; min. rozsądnie 240)
    "DRZWI_PONOW": (0, 1),              # 17.10 (F1): 1 = flaga "drzwi otwarte" starsza niż DRZWI_STARA_S s jest przeterminowana: podejście i Use przy zamkniętych drzwiach (domyślnie 0)
    "OBSERWATOR_PK_KONTEKST": (0, 1),   # 16.10 (P10): 1 = obserwator dostaje karencję PK i wie, że PAUZA_PK z karencją jest zamierzona (domyślnie 0)
    "SMIERC_STOP": (0, 1),              # 16.10 (R5/P5): 1 = po zgonie stan MARTWY: jeden STOP + powiadomienie, zero kliknięć i modelu (domyślnie 0)
    "PK_SZYBKIE": (0, 1),               # 16.10 (P6/R2): 1 = reakcja na PK bez czekania na alarm dźwiękowy i model (domyślnie 0)
    "D3_ASTAR_MAX": (0, 12),            # najwyżej tyle wywołań A* na zawieszkę przy liczeniu opcji D3 (domyślnie 6)
}
# Pokrętła tekstowe (tylko ręcznie w na_zywo.json): nazwa -> dozwolone wartości
TEKSTY = {
    "PET_NAZWA": ("Elf Scout", "Dwarf Soldier", "Orc Warrior", "Scarab", "Minotaur Archer", "Amazon", "Smuggler"),
    "RUNA_KLAWISZ": tuple(f"F{i}" for i in range(1, 13)),   # hotkey runy w kliencie
    "UH_KLAWISZ": tuple(f"F{i}" for i in range(1, 13)),     # hotkey czaru runowego w kliencie
    "UH_CZAR": ("adori gran", "adura gran", "adura vita", "adura"),   # słowa czaru (log); koszt osobno
}
# Pokrętła dobijania: zmiana (z analityka/obserwatora) tylko w "dobrą" stronę względem domyślnej,
# nigdy w stronę skracania pościgu / zasięgu dobijania. "nie_nizej": wartość >= domyślna,
# "nie_wyzej": wartość <= domyślna. Ręczny plik na_zywo.json podlega tylko ZAKRESY.
KIERUNEK = {
    # pet: analityk nie może go włączyć ani obniżyć progu many / wydłużyć limitów (tylko Karol w na_zywo.json)
    "PET_WLACZONY": "nie_wyzej", "PET_MANA_MIN": "nie_nizej", "PET_PRZERWA_S": "nie_nizej",
    "PET_STABILNE_S": "nie_nizej",
    "POGON_ZASIEG": "nie_nizej", "POGON_LIMIT": "nie_nizej",
    "POGON_TWARDY": "nie_nizej", "POGON_TWARDY_INNY": "nie_nizej",
    "POGON_DOBICIE_HP": "nie_nizej",
    "DOBICIE_ZASIEG": "nie_nizej", "DOBICIE_ZASIEG_UCIEKAJACY": "nie_nizej", "DOBICIE_MARGINES": "nie_nizej",
    "POSCIG_OKNO": "nie_nizej", "POSCIG_OKNO_DOBRY": "nie_nizej",
    "POSCIG_VKROK_SCIANA": "nie_nizej", "POSCIG_OSTATNI_DOCISKAJ": "nie_nizej",
    "POSCIG_SKOS_AWARYJNY": "nie_nizej", "JEDZENIE_ZAPAS_W_WALCE": "nie_nizej",
    "MARSZ_KLIK": "nie_wyzej", "MARSZ_KLIK_MAKS_POL": "nie_wyzej", "KROK_BEZ_SCIAN": "nie_wyzej",   # analityk nie może włączyć marszu klikiem ani go wydłużyć (tylko Karol w na_zywo.json)
    "STWORY_WIDMA": "nie_nizej",        # analityk nie wyłącza filtra widm (wyłącza go tylko Karol w na_zywo.json)
    "POSCIG_PAMIEC": "nie_nizej", "POSCIG_PAMIEC_S": "nie_nizej", "POSCIG_PAMIEC_POL": "nie_nizej",
    "POSCIG_PAMIEC_MAKS_ODL": "nie_nizej",
    "CZEKAJ_BLISKO": "nie_wyzej", "CZEKAJ_DROGA": "nie_wyzej",
    # loot w walce: analityk nie może go wyłączyć (0) ani poluzować warunków bezpieczeństwa; tylko zaostrzyć
    "LOOT_W_WALCE": "nie_nizej", "LOOT_W_WALCE_HP": "nie_nizej", "LOOT_W_WALCE_HP_MARGINES": "nie_nizej",
    "LOOT_W_WALCE_STYKAJACE": "nie_wyzej",
    # szukanie zwłok: analityk nie może wyłączyć próby pod nogami ani zmniejszyć budżetu pól
    "LOOT_POD_NOGAMI_PIERWSZE": "nie_nizej", "LOOT_MAKS_PROB": "nie_nizej",
    # wypad po pochodnie/jedzenie: analityk nie może go wyłączyć ani zmniejszyć zapasu
    "POCHODNIA_W_PRZERWIE": "nie_nizej", "WYPAD_PO_TORCHE": "nie_nizej", "WYPAD_ILE_TORCHY": "nie_nizej", "WYPAD_JEDZENIE": "nie_nizej",
    # unikanie graczy: analityk nie może go wyłączyć ani poluzować (tylko zaostrzyć); ręczny plik tylko ZAKRESY
    "POSCIG_BEZ_ZMIANY_PIETRA": "nie_nizej",
    "TRASA_PIETRA": "nie_nizej",        # analityk nie może wyłączyć przejść pięter (tylko Karol w na_zywo.json)
    "LOOT_POMIN_CIEZKIE": "nie_wyzej",  # analityk nie może włączyć pomijania ciężkich (tylko Karol w na_zywo.json)
    # patrol po miejscach: analityk nie może poluzować bezpieczeństwa druida ani pamięci graczy (tylko Karol w na_zywo.json)
    "PATROL_GNIAZDO_HP": "nie_nizej", "PATROL_GNIAZDO_MANA": "nie_nizej", "PATROL_GNIAZDO_MOBOW": "nie_wyzej",
    "PATROL_MOBY_KARA": "nie_nizej", "PATROL_MOBY_BEZP": "nie_wyzej",
    "PATROL_GRACZ_PAM": "nie_nizej", "PATROL_GRACZ_PAM_S": "nie_nizej", "PATROL_GRACZ_PAM_R": "nie_nizej",
    "PATROL_GRACZ_PAM_KARA": "nie_wyzej",
    "PATROL_KOORD": "nie_wyzej",        # analityk nie może włączyć koordynatora (tylko Karol w na_zywo.json)
    # obrona PK: analityk nie może jej wyłączyć ani poluzować (tylko zaostrzyć); ręczny plik tylko ZAKRESY
    "PK_OBRONA": "nie_nizej", "PK_ODL": "nie_nizej", "PK_ODL_CZAR": "nie_nizej", "PK_SPADEK_PP": "nie_wyzej",
    "PK_KARENCJA_MIN": "nie_nizej", "PK_WROG_WAZNY_H": "nie_nizej", "PK_LECZ": "nie_nizej", "PK_UH_HP": "nie_nizej", "PK_DEPO_MAX_MIN": "nie_wyzej",
    "PK_UH_SZYBKIE": "nie_wyzej", "PK_UH_CTRL": "nie_wyzej", "PK_UH_HP_SZYBKI": "nie_nizej", "PK_UH_PREDYKCJA": "nie_nizej",
    # walka z napastnikiem: analityk nie może jej włączyć, poluzować wejścia ani opóźnić leczenia (tylko Karol w na_zywo.json)
    "PVP_WALKA": "nie_wyzej", "PVP_MAX_WROGOW": "nie_wyzej", "PVP_DRUGI_ODL": "nie_nizej", "PVP_HP_MIN": "nie_nizej",
    "PVP_UH_HP": "nie_nizej", "PVP_EXURA_HP": "nie_nizej", "PVP_POGON": "nie_wyzej", "PVP_HMM_PORAZKI": "nie_wyzej",
    # (kierunek bezpieczny = walka nie dłuższa/szersza niż dziś) HMM_CO_S: wolniejszy ogień to słabsza walka, nie wolno; ZASIEG: tylko krócej;
    # ZNIKL_S: tylko krócej czekamy na zniknięcie; ZABITY_HP: nie wolno podnosić (łatwiejsze uznanie "zabity" = wcześniejszy powrót do gry);
    # SKOK_POL: nie wolno obniżać (fałszywa "śmierć" kończyłaby walkę przy teleporcie)
    "PVP_HMM_CO_S": "nie_wyzej", "PVP_ZASIEG": "nie_wyzej", "PVP_ZNIKL_S": "nie_wyzej", "PVP_ZABITY_HP": "nie_wyzej",
    "PVP_SKOK_POL": "nie_nizej",
    "CUDZY_MOB": "nie_nizej", "CUDZY_MOB_S": "nie_nizej", "PATROL_GRACZ_ZMIEN": "nie_nizej", "PATROL_GRACZ_ZMIEN_R": "nie_nizej",
    "PATROL_GRACZ_ZMIEN_BLOK_S": "nie_nizej", "PATROL_GRACZ_ZMIEN_PAUZA_S": "nie_wyzej",
    "UNIKANIE": "nie_nizej", "UNIKANIE_PROMIEN": "nie_nizej", "UNIKANIE_PROMIEN_MAX": "nie_nizej",
    "UNIKANIE_MOB_PROMIEN": "nie_nizej", "UNIKANIE_PUNKT_D": "nie_nizej", "UNIKANIE_DROGA_MIN": "nie_nizej",
    "UNIKANIE_BLOK_S": "nie_wyzej", "UNIKANIE_ZNIKL_S": "nie_nizej",
    "UNIKANIE_TOR": "nie_nizej", "UNIKANIE_PRZERWA": "nie_nizej",
    # mijanie: analityk nie może go włączyć ani wydłużyć postoju / zasięgu ustępowania (tylko Karol w na_zywo.json)
    "MIJANIE": "nie_wyzej", "MIJANIE_POSTOJ_S": "nie_wyzej", "MIJANIE_PRZEJSCIE_ODL": "nie_wyzej", "MIJANIE_BOK_R": "nie_wyzej",
    # czar ML: analityk nie może go włączyć ani rzucać w walce (tylko Karol w na_zywo.json)
    "ML_CZAR_AKTYWNY": "nie_wyzej", "ML_CZAR_W_WALCE": "nie_wyzej",
    # czary zdrowia/jedzenia: analityk nie może ich włączyć ani podnieść progów (tylko Karol w na_zywo.json)
    "ZDROWIE_CZAR_AKTYWNY": "nie_wyzej", "ZDROWIE_CZAR_HP": "nie_wyzej",
    "JEDZENIE_CZAR_AKTYWNY": "nie_wyzej", "ML_BLOK_HP": "nie_wyzej",
    # jedzenie przy braku regeneracji many: analityk może tylko skrócić okno (jeść wcześniej), nie wydłużyć
    "JEDZENIE_MANA_BRAK_S": "nie_wyzej",
    # jedzenie w walce: analityk nie może go wyłączyć ani wydłużyć okna / podnieść marginesu (czyli jeść rzadziej)
    "TRASA_STOP_PRZY_POTWORZE_R": "nie_nizej",
    "JEDZENIE_W_WALCE": "nie_nizej", "CZAS_JEDZENIA_WALKA": "nie_wyzej", "JEDZENIE_WALKA_HP_MARGINES": "nie_wyzej",
    # zapas jedzenia czarem: analityk może tylko obniżyć próg (mniej rzutów), nie podnieść
    "JEDZENIE_ZAPAS_MIN": "nie_wyzej",
    # strzał runą: analityk nie może go włączyć (tylko Karol w na_zywo.json)
    "RUNA_AKTYWNA": "nie_wyzej", "RUNA_TRYB_KLIK": "nie_wyzej",
    # robienie run: analityk nie może go włączyć ani obniżyć progów bezpieczeństwa (tylko Karol w na_zywo.json)
    # wyprawa po zapasy: analityk nie może jej włączyć ani zwiększyć wydatków/ryzyka (tylko Karol w na_zywo.json)
    "WYPRAWA_AKTYWNA": "nie_wyzej", "WYPRAWA_BLANKI": "nie_wyzej", "WYPRAWA_BLANKI_MAX_KOSZT": "nie_wyzej",
    "WYPRAWA_JEDZENIE_CEL": "nie_wyzej", "WYPRAWA_JEDZENIE_DOKUP": "nie_wyzej", "WYPRAWA_MIN_HP": "nie_nizej",
    "WYPRAWA_CO_MIN": "nie_nizej", "WYPRAWA_MAX_CZAS_S": "nie_wyzej", "WYPRAWA_MAX_KROKOW": "nie_wyzej",
    "WYPRAWA_STOP_PRZY_UTKNIECIU": "nie_nizej", "WYPRAWA_CZEKAJ_NA_GLOD": "nie_wyzej", "JEDZENIE_BRAK_WALIDUJ": "nie_nizej", "JEDZENIE_BRAK_PROBY": "nie_nizej", "GLOD_ZAPAS_WAZNY_S": "nie_wyzej", "WYPRAWA_WZNOW_WALIDUJ": "nie_nizej", "WYPAD_BIEGNIJ": "nie_nizej", "DOJSCIE_BIEGNIJ": "nie_nizej", "WPADNIECIE": "nie_nizej", "WPADNIECIE_WALIDACJA": "nie_wyzej", "WPADNIECIE_POSCIG": "nie_wyzej", "WPADNIECIE_LINA": "nie_nizej", "WPADNIECIE_PLAN": "nie_nizej", "DZIURY_NAUCZONE": "nie_nizej", "DZIURA_PRZY_CELU": "nie_nizej", "WPADNIECIE_LINA_PROB": "nie_nizej", "PIETRA_LOPATA": "nie_nizej", "PIETRA_TRYBY_Z_DANYCH": "nie_nizej", "PIETRA_STARTY_DOMYSLNE": "nie_nizej", "WYPRAWA_DEPO_POWROT": "nie_wyzej", "WYPRAWA_DEPO_POSTOJ_S": "nie_wyzej", "WYPRAWA_TYLKO_DEPO": "nie_wyzej", "WYPRAWA_MARSZ_KLIK": "nie_wyzej", "WROC_REFILL": "nie_wyzej", "WYPRAWA_ZLOTO_MIN": "nie_nizej", "WYPRAWA_CAP_REZERWA": "nie_nizej",
    # ogłoszenia Trade: analityk nie może ich włączyć ani skrócić odstępów (tylko Karol w na_zywo.json)
    "MODEL_TRASA_MIASTA": "nie_wyzej", "MODEL_TRASA_ZAMROZENIE_S": "nie_wyzej", "MODEL_TRASA_MAX_ODL": "nie_wyzej",
    "TRADE_OGLOSZENIA": "nie_wyzej", "TRADE_PRIV_ODPOWIEDZI": "nie_wyzej", "TRADE_MIN_S": "nie_nizej", "TRADE_MAX_S": "nie_nizej", "TRADE_MIN_UH": "nie_nizej",
    "UH_AKTYWNY": "nie_wyzej", "UH_MIN_HP": "nie_nizej", "UH_MOB_DYSTANS": "nie_nizej", "UH_MANA_MIN": "nie_nizej", "UH_ODSTEP_S": "nie_nizej",
    "LOOT_DYNAMICZNY": "nie_nizej",
    "UH_W_WALCE": "nie_wyzej", "UH_W_WALCE_MANA_MARGINES": "nie_wyzej", "UH_W_WALCE_MIN_HP": "nie_nizej",
    "UH_W_WALCE_DYSTANS": "nie_nizej", "UH_W_WALCE_SPADEK_HP": "nie_wyzej",
    # pola ognia: analityk nie może wyłączyć omijania (tylko Karol w na_zywo.json)
    "OGIEN_UNIKAJ": "nie_nizej", "OGIEN_STALY": "nie_nizej", "OGIEN_MASKA_TYLKO_SCIANY": "nie_nizej", "OGIEN_WYJDZ_POTWIERDZ": "nie_nizej", "OGIEN_MASKA_DANE": "nie_nizej", "OGIEN_POMIJAJ_PRZY_STWORZE": "nie_nizej", "POSCIG_SKOSY_ZAPAS": "nie_nizej", "PATROL_DRZWI": "nie_nizej", "D3_REAKCJA": "nie_wyzej", "RATUNEK_HAIKU": "nie_wyzej", "RATUNEK_HAIKU_PYTAJ": "nie_wyzej", "D3_ALARM_S": "nie_wyzej", "DRZWI_PONOW": "nie_wyzej", "SMIERC_STOP": "nie_wyzej", "PK_SZYBKIE": "nie_wyzej", "OBSERWATOR_PK_KONTEKST": "nie_wyzej", "RUCH_OKNO": "nie_nizej", "RUCH_PROBKA_WCZESNA": "nie_nizej", "OGIEN_ODSWIEZ_WALKA_S": "nie_wyzej",
    # ignorowanie/strażnicy/blokujący: analityk nie może wyłączyć strażników ani włączyć bicia blokującego (tylko Karol)
    # dojście z depo: analityk nie może włączyć wypraw po blanki w depo ani wyłączyć karencji/walki przy przejściu (tylko Karol)
    "WYPRAWA_DEPO_BLANKI": "nie_wyzej", "WYPRAWA_PO_DEPO_S": "nie_nizej", "WYPRAWA_PO_DOJSCIU_S": "nie_nizej", "BLANKI_AUTO_BAG": "nie_wyzej", "BLANKI_AUTO_BAG_MIN": "nie_nizej",
    "DOJSCIE_WALKA_PRZEJSCIE_S": "nie_wyzej", "DOJSCIE_BEZ_UNIKANIA_POL": "nie_wyzej", "DOJSCIE_PROBY": "nie_nizej",
    "DOJSCIE_PAUZA_PROBY_S": "nie_nizej",
    "IGNOR_TWARDE": "nie_nizej", "STRAZNIK_CEL": "nie_nizej", "BLOK_WYJSCIE": "nie_wyzej", "STRAZNIK_POSTEP": "nie_wyzej",
    # strażnik orbit: analityk nie może go włączyć ani poluzować progów (tylko Karol w na_zywo.json)
    "STRAZNIK_ORBITY": "nie_wyzej", "STRAZNIK_ORBITA_S": "nie_nizej", "STRAZNIK_ORBITA_POL": "nie_wyzej",
}
COFNIECIE_S = 300


def _powiadom(*a, **k):
    try:
        import powiadom  # noqa: PLC0415
        powiadom.powiadom(*a, **k)
    except Exception:
        pass


def waliduj(zmiany, domyslne=None):
    """-> (poprawne, bledy). Wartości liczbowe w zakresie; typ jak domyślny (int/float).
    Z `domyslne` (słownik nazwa -> domyślna): pokrętła z KIERUNEK tylko w dozwoloną stronę."""
    ok, bledy = {}, []
    for k, v in (zmiany or {}).items():
        if k.startswith("_"):
            continue
        if k in TEKSTY:
            if domyslne:
                bledy.append(f"{k}: tylko ręcznie w na_zywo.json")
            elif v not in TEKSTY[k]:
                bledy.append(f"{k}={v!r}: dozwolone {TEKSTY[k]}")
            else:
                ok[k] = v
        elif k not in ZAKRESY:
            bledy.append(f"{k}: nieznany klucz")
        elif isinstance(v, bool) or not isinstance(v, (int, float)):
            bledy.append(f"{k}: nie liczba")
        elif not ZAKRESY[k][0] <= v <= ZAKRESY[k][1]:
            bledy.append(f"{k}={v}: poza zakresem {ZAKRESY[k]}")
        elif domyslne and k in KIERUNEK and k in domyslne and (
                (KIERUNEK[k] == "nie_nizej" and v < domyslne[k])
                or (KIERUNEK[k] == "nie_wyzej" and v > domyslne[k])):
            bledy.append(f"{k}={v}: zły kierunek względem domyślnej {domyslne[k]} ({KIERUNEK[k]})")
        else:
            ok[k] = v
    return ok, bledy


class Pokretla:
    def __init__(self, modul, plik=PLIK, log=print, zegar=time.time):
        self.modul, self.plik, self.log, self.zegar = modul, Path(plik), log, zegar
        # domyślne zapamiętane raz na moduł: drugi Pokretla w tym samym procesie (np. nowa instancja Cavebot)
        # widziałby już nadpisane hot reloadem wartości i w logu pisał "domyślna" = bieżąca
        zap = getattr(modul, "_POKRETLA_DOMYSLNE", None)
        if not isinstance(zap, dict):
            zap = {}
            try:
                modul._POKRETLA_DOMYSLNE = zap
            except Exception:
                pass
        for k in (*ZAKRESY, *TEKSTY):
            if k not in zap and hasattr(modul, k):
                zap[k] = getattr(modul, k)
        self.domyslne = {k: zap[k] for k in (*ZAKRESY, *TEKSTY) if k in zap}
        self.mtime = None
        self.aktywne = {}
        self.oczekuje = None      # {"t","przed":dict pliku,"zmiany","metryki","powod"}
        self.zakazane = {}        # klucz -> do kiedy nie zmieniać po cofnięciu

    def odswiez(self):
        """Wołane co tick: tani stat, wczytanie tylko przy zmianie pliku."""
        try:
            m = self.plik.stat().st_mtime
        except OSError:
            m = None
        if m == self.mtime:
            return
        self.mtime = m
        try:
            dane = json.loads(self.plik.read_text()) if m else {}
        except (OSError, ValueError) as e:
            self.log(f"na_zywo.json: błąd odczytu {e!r}, zostają poprzednie wartości")
            return
        self.zastosuj(dane if isinstance(dane, dict) else {})

    def zastosuj(self, dane):
        ok, bledy = waliduj(dane)
        for b in bledy:
            self.log(f"na_zywo.json odrzucone: {b}")
        for k in list(self.aktywne):
            if k not in ok:
                setattr(self.modul, k, self.domyslne[k])
                self.log(f"pokrętło {k}: powrót do domyślnej {self.domyslne[k]}")
                del self.aktywne[k]
        for k, v in ok.items():
            if k not in self.domyslne:
                self.log(f"pokrętło {k}: brak stałej w cavebot.py, pomijam")
                continue
            if self.aktywne.get(k) != v:
                setattr(self.modul, k, v)
                self.log(f"pokrętło {k}: {getattr(self.modul, k)} (domyślna {self.domyslne[k]})")
                self.aktywne[k] = v

    def _plik_dane(self):
        try:
            d = json.loads(self.plik.read_text())
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _zapisz(self, dane):
        self.plik.write_text(json.dumps(dane, ensure_ascii=False, indent=1))

    def zmien(self, zmiany, powod, metryki=None):
        """Wywołanie analityka: waliduje, zapisuje do pliku, loguje z uzasadnieniem.
        -> lista faktycznie zmienionych kluczy."""
        ok, bledy = waliduj(zmiany, self.domyslne)
        teraz = self.zegar()
        for b in bledy:
            self.log(f"zmiana pokręteł odrzucona: {b}")
        ok = {k: v for k, v in ok.items() if k in self.domyslne
              and self.zakazane.get(k, 0) <= teraz and self.aktywne.get(k, self.domyslne[k]) != v}
        if not ok or self.oczekuje:      # jedna zmiana naraz, ocena przed następną
            return []
        przed = self._plik_dane()
        nowe = {**{k: v for k, v in przed.items() if not k.startswith("_")}, **ok}
        self._zapisz(nowe)
        self.oczekuje = {"t": teraz, "przed": przed, "zmiany": ok, "metryki": metryki or {}, "powod": powod}
        self.log(f"ANALITYK zmienia pokrętła {ok}: {powod}")
        _powiadom("Analityk zmienił pokrętło", f"{ok}: {powod}", klucz="pokretlo")
        self.mtime = None
        self.odswiez()
        return list(ok)

    def ocen(self, metryki_po):
        """Po COFNIECIE_S od zmiany: porównaj z metrykami sprzed; gorzej -> cofnij. -> 'cofnieto'|'zostaje'|None."""
        o = self.oczekuje
        if not o or self.zegar() - o["t"] < COFNIECIE_S:
            return None
        przed, po = o["metryki"], metryki_po
        gorzej = (po.get("zabicia_na_min", 0) < przed.get("zabicia_na_min", 0) * 0.85
                  and przed.get("zabicia_na_min", 0) > 0) \
            or po.get("odpuszczenia_na_min", 0) > przed.get("odpuszczenia_na_min", 0) * 1.25 + 0.1
        self.oczekuje = None
        if gorzej:
            self._zapisz({k: v for k, v in o["przed"].items()})
            for k in o["zmiany"]:
                self.zakazane[k] = self.zegar() + 1800
            self.log(f"AUTO-COFNIĘCIE pokręteł {o['zmiany']}: zabicia/min {przed.get('zabicia_na_min')} -> "
                     f"{po.get('zabicia_na_min')}, odpuszczenia/min {przed.get('odpuszczenia_na_min')} -> "
                     f"{po.get('odpuszczenia_na_min')}")
            _powiadom("Auto-cofnięcie pokrętła", f"{o['zmiany']}: zabicia/min {przed.get('zabicia_na_min')} -> "
                      f"{po.get('zabicia_na_min')}, odpuszczenia/min {przed.get('odpuszczenia_na_min')} -> "
                      f"{po.get('odpuszczenia_na_min')}", klucz="cofniecie")
            self.mtime = None
            self.odswiez()
            return "cofnieto"
        self.log(f"pokrętła {o['zmiany']} zostają (zabicia/min {po.get('zabicia_na_min')})")
        return "zostaje"
