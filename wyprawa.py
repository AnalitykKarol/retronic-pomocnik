"""Wyprawa po zapasy (13.10): bot sam wraca do Thais, kupuje jedzenie u Frodo (jedzenie na miejscu do "full",
dokup ponad cel), opcjonalnie blank runy u Xodeta i pochodnie u Gorna, po czym wraca na spot i patrol rusza dalej.

To ta sama maszyna co wypad po pochodnie (wypad.Wypad): trasa jako etapy IDZ/LINA/DZIURA, chodzenie przez
Cavebot._idz_odcinek, dialog z NPC przez ops.czat/ops.wiadomosci (hi / buy N x / yes), ucieczka, STOP, ALARM_GM.
Klasa Wyprawa dziedziczy po Wypad i dokłada tylko to, czego wypad nie ma:
  * wyzwalacz zapasu: jedzenie w plecaku < próg (JEDZENIE_ZAPAS_MIN albo WYPRAWA_ZAPAS_PROG), głód bez jedzenia,
    opcjonalnie blank runy < WYPRAWA_BLANKI_PROG; poza walką/lootem/UH, HP ok, cooldown WYPRAWA_CO_MIN;
  * wiele przystanków (Gorn -> Frodo -> Xodet) i odcinki między nimi z A* po mapie (generuj_trase_miasta.Graf)
    albo z nagrania (trasy/wyprawa_sklepy.json);
  * zakupy z kontrolą capacity, złota i kosztu (ceny z ofert NPC "Do you want to buy N x for G gold?");
  * jedzenie u NPC aż klient przestanie zjadać ("You are full" / liczba sztuk nie spada), potem dokup;
  * kolejka u NPC ("I am talking to ...", "wait a moment"): czekamy, nie liczymy jako porażkę;
  * trwały stan (wyprawa_stan.json): restart bota w środku wyprawy wznawia ją od najbliższego odcinka;
  * twarde limity czasu i obiegów, wykrycie teleportu/śmierci, alarm + plik STOP przy utknięciu w mieście.

Tryb "wyprawa_depo" (WYPRAWA_TYLKO_DEPO = 1): ta sama maszyna, ale cel to samo depo w Thais. Start po potwierdzonym
głodzie (bez pozycji Frodo), marsz nagraną trasą do Gorna i dalej A* do pola depo; na miejscu log, powiadomienie,
czyszczenie stanu i plik STOP. Bez zakupów i bez powrotu na spot; utknięcie/teleport/limit = alarm + STOP.

Wyłączona domyślnie (WYPRAWA_AKTYWNA = 0). Włącza tryb "wyprawa" z tryby.json (albo pokrętło w na_zywo.json).
Pozycje NPC: trasy/wyprawa_sklepy.json (ręcznie) albo uczone z widoku (wyprawa_npc.json: gdy Frodo/Xodet pojawią
się w liście stworów, bot zapisuje ich pole). Bez znanej pozycji Frodo wyprawa nie startuje (log + powiadomienie).

CLI (tylko odczyt plików i mapy, nic nie rusza gry):  python3 -I wyprawa.py [plan|stan]
"""

import heapq
import json
import math
import os
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bot
import instancja
import wypad
from wypad import Wypad, cheb, drzwi_z_mapy, sprawdz_plan, zbuduj_etapy

KATALOG = Path(__file__).resolve().parent
TRASY = KATALOG / "trasy"
PLIK_SKLEPOW = TRASY / "wyprawa_sklepy.json"
PLIK_STANU = instancja.S.stan / "wyprawa_stan.json"
PLIK_NPC = instancja.S.stan / "wyprawa_npc.json"
PLIK_DEPO = "depo_troll_cave.json"          # początek tej trasy = pole depo
DEPO_POLE = (32366, 32215, 7)               # gdy pliku brak
PLIK_SERWIS_EDRON = "serwis_edron.json"     # 24.10: tu `depo_stoiska`, `depo_sala` i `depo_obszar` Edronu (jedno źródło dla serwisu, panelu i wyprawy)


def obszar_depo(katalog, cel):
    """24.10 (Karol: „punkt dojścia do depo w Edron na jakiś neutralny na środku albo obręb, żeby za każdym razem w to samo miejsce nie
    przychodził, bo może być zajęte”): ({pola obszaru}, sala) dla celu depo `cel`, gdy `cel` jest stanowiskiem przy skrzyni depo Edronu
    (koniec nagranych tras "do" Edronu to (33173, 31796, 8)). `sala` = (x0, y0, x1, y1, z). None, gdy `cel` nie jest takim stanowiskiem,
    plik/klucze nie istnieją albo są zepsute (wtedy dawne zachowanie: dojście na samo stanowisko `cel`)."""
    try:
        d = json.loads((Path(katalog) / PLIK_SERWIS_EDRON).read_text())
        stoiska = {tuple(int(v) for v in p) for p in d.get("depo_stoiska") or ()}
        pola = [tuple(int(v) for v in p) for p in d.get("depo_obszar") or ()]
        sala = tuple(int(v) for v in d.get("depo_sala") or ())
    except (OSError, ValueError, TypeError):
        return None
    cel = tuple(int(v) for v in cel)
    if cel not in stoiska or not pola or len(sala) != 5 or any(len(p) != 3 for p in pola):
        return None
    if not all(sala[0] <= p[0] <= sala[2] and sala[1] <= p[1] <= sala[3] and p[2] == sala[4] for p in pola):
        return None                          # obszar poza salą = zepsute dane, nie ryzykujemy
    return pola, sala


def w_sali(poz, sala):
    return int(poz[2]) == sala[4] and sala[0] <= poz[0] <= sala[2] and sala[1] <= poz[1] <= sala[3]


def wybierz_pole_obszaru(pola, zajete=(), los=random):
    """Losowe pole `pola` bez `zajete` ((x, y) albo (x, y, z)); gdy wszystkie zajęte, None (wołający zostaje przy stanowisku)."""
    zaj = {(int(q[0]), int(q[1])) for q in zajete}
    wolne = [p for p in pola if (p[0], p[1]) not in zaj]
    return los.choice(wolne) if wolne else None

BAZY = ("troll", "thais_kanaly")       # plany wypadu (wypad.PLANY) kończące się u Gorna w Thais; rook ma inne miasto
# 15.10 obrona PK: plany WYŁĄCZNIE do ucieczki do depo i powrotu z niego (nie biorą udziału w zwykłej wyprawie po zapasy:
# BAZY ich nie zawiera). "do" = z łowiska do depo, "z" = z depo na łowisko (oba nagrane, edron_*.json)
ZASIEG_KAZORDOON = 400                 # pola (Chebyshev) od depo Thais; spot Kazordoon ~305 (klucz "zasieg" planu, patrz zasieg_planu)
PLANY_PK = (
    {"nazwa": "edron", "do": "edron_do_depo.json", "z": "edron_depo_trolle.json", "npc": None, "prefix": False,
     "wyjscia": (((33092, 31837, 9), (33092, 31838, 8), "gobliny_edron_do_depo.json"),      # 19.10: _baza_dojscie wybiera "edron" także z goblinów z9
                 # 21.10: jaskinie trolli z9 wschód/zachód (trolle_edron_z9w/z9z): lina w dziurze, którą dojście schodzi
                 # z z8, stoimy obok (pole liny wolne); bez tego powrót = "brak drogi" i utknięcie (Kolanosh 20:14).
                 # Trasy: generuj_powroty_edron_z9.py
                 ((33119, 31740, 9), (33119, 31741, 8), "trolle_edron_z9w_do_depo.json", ((33119, 31739, 9),)),
                 ((33081, 31742, 9), (33081, 31743, 8), "trolle_edron_z9z_do_depo.json", ((33081, 31741, 9),)),
                 # 26.10 (rodziny spotów, generuj_powroty_rodziny.py): z10 wschód pod z9w - lina z10 -> z9 z pola (33128,31729,z10) (dziura (33128,31729,z9)),
                 # stoimy obok, lądowanie (33128,31730,z9), marsz po z9w do stania (33119,31739,z9), lina z9 -> z8 jak wyjście z9w. NIEZWERYFIKOWANE na żywo (lina z10).
                 ((33128, 31729, 10), (33128, 31730, 9), "trolle_edron_z10w_pelna_do_depo.json", ((33128, 31728, 10), (33129, 31729, 10), (33127, 31729, 10))))},
    # 17.10: jaskinia goblinów Edron z8 (trasy wygenerowane z mapy klienta; lina na (33107,31847,z8), stanie (33107,31846,z8), lądowanie (33107,31848,z7): sprawdzone w grze 17.10 23:15)
    # 19.10: pętla goblinów jest cała na z9 (bez przejścia pięter), więc "wyjscia" = [pole liny na z9, lądowanie na z8]:
    # lina w górę pod dziurą z8 (33092,31837) (mapa: "pewne"); z8 dalej A* do nagranej trasy "do" (start (33106,31849,z8))
    {"nazwa": "gobliny_edron", "do": "gobliny_edron_do_depo.json", "z": "gobliny_edron_z_depo.json", "npc": None, "prefix": False,
     "wyjscia": (((33092, 31837, 9), (33092, 31838, 8), "gobliny_edron_do_depo.json"),
                 # 26.10 (rodziny spotów, generuj_powroty_rodziny.py): trzy kieszenie goblinów na z10 pod jaskinią z9: lina z10 -> z9 z pola lądowania pod dziurą,
                 # marsz po z9 do stania (33092,31836,z9), lina z9 -> z8 jak wyżej, dalej gobliny_edron_do_depo. NIEZWERYFIKOWANE na żywo (lina z10).
                 ((33063, 31822, 10), (33063, 31823, 9), "gobliny_edron_z10_zachod_do_depo.json", ((33063, 31821, 10), (33064, 31821, 10), (33062, 31821, 10))),
                 ((33102, 31822, 10), (33102, 31823, 9), "gobliny_edron_z10_wschod_do_depo.json", ((33103, 31822, 10), (33101, 31822, 10), (33101, 31821, 10))),
                 ((33069, 31848, 10), (33069, 31849, 9), "gobliny_edron_z10_poludnie_do_depo.json", ((33069, 31847, 10), (33068, 31847, 10), (33069, 31849, 10))))},
    # 25.10: Port Hope, depo (32632,32743,z7) (Karol), trasy z mapy A* (generuj_powrot_port_hope.py), NIEPRZETESTOWANE na żywo.
    # ph_raty_z8 (Geblish): dojście zeszło dziurą z7 (32662,32741); powrót = LINA z8 na polu (32662,32741), stoimy (32662,32740), lądowanie (32662,32742,z7).
    {"nazwa": "ph_raty_z8", "do": "ph_raty_z8_do_depo.json", "z": "ph_raty_z8_dojscie.json", "npc": None, "prefix": False,
     "wyjscia": (((32662, 32741, 8), (32662, 32742, 7), "ph_raty_z8_do_depo.json", ((32662, 32740, 8),)),)},
    # swamp trolle Port Hope: tylko powierzchnia z7 (bez pięter jaskini), od wejścia (32678,32612) do depo
    {"nazwa": "port_hope_swamp", "do": "port_hope_swamp_do_depo.json", "z": "port_hope_swamp_do_depo.json", "npc": None, "prefix": False},
    # 22.10: Thais północ, jaskinia trolli z8 (thais_pn_z8) — powrót do depo odwróconym dojściem (generuj_powrot_thais_pn.py):
    # z8 -> pole stania (32347,32124,z8) obok pola liny/drabiny (32347,32123,z8), przejście w górę, lądowanie (32347,32124,z7), z7 do depo.
    # WYŁĄCZONY od 21.10 (zgon kutangena w dziurze (32356,32122,z8)); przejście w górę NIEPRZETESTOWANE na żywo: włączyć dopiero po teście
    # jedną postacią (dane_tibia/ruch/DIAGNOZA_kutangen_zgon_dziura_thais_pn_1021.md). Test: testy/test_powrot_thais_pn.py
    {"nazwa": "thais_pn", "do": "thais_pn_z8_do_depo.json", "z": "thais_pn_z8_dojscie.json", "npc": None, "prefix": False,
     "wyjscia": (((32347, 32123, 8), (32347, 32124, 7), "thais_pn_z8_do_depo.json", ((32347, 32124, 8),)),)},
    # 23.10: Thais północ, jaskinia trolli z9 (thais_pn_z9, Gebelish) — zachodnia sala z9 jest zamknięta: wyjście = dojście odwrócone
    # (generuj_powrot_thais_pn_z9.py): dziura (32339,32122,z9) w dół, kieszeń z10, LINA z10 -> z9 wschód (pole liny (32343,32122,z10),
    # stoimy (32343,32123)), korytarz Poison Spiderów y=32123 (3 szt.), LINA z9 -> z8 (pole liny (32356,32122,z9), stoimy (32356,32123)),
    # z8 na zachód do (32347,32124,z8), dalej "do" thais_pn_z8 (przejście z8 -> z7 PRZESZŁO w przejscia_nauczone).
    # NIEZWERYFIKOWANE NA ŻYWO: dwie liny (z10 i z9 wschód) i cały powrót; potrzebne lina i łopata w plecaku; powrót wiedzie przez korytarz jadu
    # (tu zginął kutangen 21.10). Mapa potwierdza układ lina+dziura, nagranie 23.10 tylko lina (32339,32122,z10). Wyłączenie planu = usunięcie
    # tej krotki (wtedy postać z z9 dostaje "pozycja poza planami", jak przed 23.10). Test: testy/test_powrot_thais_pn_z9.py
    {"nazwa": "thais_pn_z9", "do": "thais_pn_z9_do_depo.json", "z": "thais_pn_z9_dojscie.json", "npc": None, "prefix": False},
    # 21.10: Rookgaard — powrót do miasta przez drabiny/schody (SPEC_powrot_rook_1020). Trasy odwrócone z dojść.
    # Cel: (32061,32180,7) Al Dee, STOP. "z" = nagrane dojście (miasto->spot) na wypadek powrotu po PK.
    # NIEZWERYFIKOWANE botem: przejście w górę (drabina/schody z8->z7 itd.) — ryzyko zapisane w specu.
    {"nazwa": "rook_raty_z8",    "do": "rook_raty_z8_dojscie_odwrocona.json",    "z": "rook_raty_z8_dojscie.json",    "npc": None, "prefix": False},
    {"nazwa": "rook_raty_z9",    "do": "rook_raty_z9_dojscie_odwrocona.json",    "z": "rook_raty_z9_dojscie.json",    "npc": None, "prefix": False},
    {"nazwa": "rook_raty_z10",   "do": "rook_raty_z10_dojscie_odwrocona.json",   "z": "rook_raty_z10_dojscie.json",   "npc": None, "prefix": False},
    {"nazwa": "rook_kanaly_z11", "do": "rook_kanaly_z11_dojscie_odwrocona.json", "z": "rook_kanaly_z11_dojscie.json", "npc": None, "prefix": False},
    {"nazwa": "rook_bugi_z10",   "do": "rook_bugi_z10_dojscie_odwrocona.json",   "z": "rook_bugi_z10_dojscie.json",   "npc": None, "prefix": False},
    # 23.10: trolle pod Kazordoonem (generuj_trasy_kazordoon_trolle.py; dojście z depo Thais drogą, powrót liną do depo Thais).
    # "do" = jawna trasa powrotu spot -> depo Thais (z8: rozwidlenie (32647,32003,z8) -> lina z dziury (32663,31962,z8), stoimy
    # OBOK pola liny (32663,31961,z8) -> lądowanie (32663,31963,z7) -> drzwi -> most -> brama -> depo; z9 dokłada schody w górę
    # (32648,32003,z9) -> (32648,32004,z8)), "z" = dojście z depo (dla powrotu po karencji PK). Bez "wyjscia": oba pliki "do" zawierają
    # przejścia pięter, a pętla z8/z9 leży na tym samym piętrze co ich początek (A* po piętrze do trasy "do").
    # "zasieg": spot leży ~300 pól od depo Thais (DEPO_DOJSCIE_ZASIEG = 200 odrzucał drogę: "brak drogi" -> stara trasa od rozwidlenia).
    # Przejście liną/dziura (32663,31962,z8): może być zasypana, wtedy łopata (patrz CLAUDE.md, pietra.ZASYPANE); NIE wpisana bez dowodu z gry.
    {"nazwa": "trolle_kazordoon_z8", "do": "trolle_kazordoon_z8_do_depo.json", "z": "trolle_kazordoon_z8_dojscie.json",
     "npc": None, "prefix": False, "zasieg": ZASIEG_KAZORDOON},
    {"nazwa": "trolle_kazordoon_z9", "do": "trolle_kazordoon_z9_do_depo.json", "z": "trolle_kazordoon_z9_dojscie.json",
     "npc": None, "prefix": False, "zasieg": ZASIEG_KAZORDOON},
    # 24.10: Kazordoon, powierzchnia z7 (generuj_trasy_kazordoon_powierzchnia.py): pętla i start powrotu w (32660,31985,z7), "do" = z pętli tą samą drogą po z7
    # przez most Thais do depo (bez liny i dziury), "z" = dojście = prefiks dojść z8/z9. Bez "wyjscia": pętla i początek "do" leżą na jednym piętrze (A* po z7).
    {"nazwa": "trolle_kazordoon_z7", "do": "trolle_kazordoon_z7_do_depo.json", "z": "trolle_kazordoon_z7_dojscie.json",
     "npc": None, "prefix": False, "zasieg": ZASIEG_KAZORDOON},
    # 24.10 (generuj_powrot_abdendriel.py, Marinarra, abdendriel_trolle_z10_z9): "do" = lina z10 -> z9, jaskinia z9 (A*), dwoje drzwi, schody w gore z9 -> z8,
    # korytarz z8 do poczatku nagrania depo -> trolle; "z" = to nagranie (konczy sie w jaskini z9, nie na z10: tylko powrot po karencji PK, a WROC go nie uzywa).
    # SUBSTITUTE DECISION (be-dev): cel depo = (32679,31687,z8), pierwszy punkt nagrania, NIEPOMIERZONY; poprawka = stala DEPO_STOI w generatorze + --zapisz.
    # Bez "wyjscia" (oba konce na jednym pietrze z "do"). Plan jest tez w BAZY_PK (ucieczka PK): z pozycji w jaskini z9/z10 zaprowadzi do tego samego depo.
    {"nazwa": "abdendriel_trolle_z10", "do": "abdendriel_trolle_do_depo.json", "z": "abdendriel_depo_trolle_nagranie.json",
     "npc": None, "prefix": False, "drzwi": True,      # "drzwi": dwoje zamknietych drzwi z9 w "do" -> etapy DRZWI (Wyprawa._zbuduj_depo)
     # 24.10 (Karol: Marinarra „nie umie uzyc klucza na drzwiach”): drzwi na klucz = etap DRZWI z "klucz": <id> (wypad._drzwi: krok, potem Use klucza z plecaka na
     # kafelku drzwi, krok). 2970 = a copper key (Elathriel, 5000 gp). NIEPOTWIERDZONE: czy klucz z plecaka Marinarry pasuje do OBU drzwi (numer klucza nie jest w danych).
     # Jedno zrodlo prawdy: generuj_powrot_abdendriel.KLUCZE_DRZWI (test_powrot_abdendriel sprawdza zgodnosc).
     "klucze": (((32658, 31645, 9), 2970), ((32655, 31655, 9), 2970))},
    # 25.10 (generuj_powrot_abdendriel.py zbuduj_z12, Marinarra/Marianni stoi na z12 w jaskini trolli, plan abdendriel_trolle_z10 nie mial punktow "do" na z11/z12):
    # "do" = korytarz z12 x=32668 -> LINA z12 -> z11 (pole liny (32668,31624,z12), lad. (32668,31625,z11)) -> krok na zachod -> LINA z11 -> z10 (pole liny (32668,31625,z11),
    # lad. (32668,31626,z10) POLUDNIE od dziury z10) -> obejscie dziury A* -> (32668,31623,z10) i dalej BAJT W BAJT trasa abdendriel_trolle_do_depo (lina z10, jaskinia z9,
    # dwoje drzwi na klucz, schody z9 -> z8, depo). Wybor planu: wybierz_baze bierze plan z najblizszym punktem "do" NA TYM PIETRZE (z12/z11: tylko ten plan ma tam punkty;
    # z9/z10: remis -> wygrywa wczesniejszy wpis abdendriel_trolle_z10, kolejnosc w krotce ma znaczenie), z dalszych pol piętra dojscie robi droga_do_depo (zalew A* do punktow "do").
    # SUBSTITUTE DECISION (be-dev, do przegladu): "z" = to samo nagranie depo -> trolle co w planie z10 (po karencji PK i tak konczy sie w jaskini z9, nie na z12);
    # cel depo = ta sama ZASTEPCZA pozycja (32679,31687,z8). NIEPOTWIERDZONE NA ZYWO: lina z12 -> z11 (dziura z11 -> z12 nigdy nie przeszla w gre), lina z11 -> z10.
    {"nazwa": "abdendriel_trolle_z12", "do": "abdendriel_trolle_z12_do_depo.json", "z": "abdendriel_depo_trolle_nagranie.json",
     "npc": None, "prefix": False, "drzwi": True,
     "klucze": (((32658, 31645, 9), 2970), ((32655, 31655, 9), 2970))},
    # 25.10 gobliny pod Ab z6: powrot = dojscie odwrocone (schody z6 -> z7 -> z8, bez drzwi); depo ZASTEPCZE jak w planach trolli.
    {"nazwa": "abdendriel_gobliny_z6", "do": "abdendriel_gobliny_do_depo.json", "z": "abdendriel_gobliny_dojscie.json", "npc": None, "prefix": False},
    # 27.10 (generuj_trasy_abdendriel_zachod.py, Karol: „dopisz dojście z miasta i powrót do miasta”) daleka jaskinia na zachód od Ab'Dendriel: z8 wilki/węże i z9 trolle.
    # "do" = z8: stanie (32490,31696,z8) obok pola liny (32490,31697,z8) -> LINA -> z7 (32490,31698), z7 A* do schodów w dół (32654,31674,z7), z8 korytarz x=32655, nagranie
    # odwrócone do depo; z9: LINA z9 (32480,31721) (stanie (32480,31720,z9)) -> z8 (32480,31722), A* po z8 do (32490,31696,z8), dalej jak z8. "z" = dojście z depo (nagranie z8, schody w górę,
    # z7 A*, zasypana dziura z7 (32490,31697) -> z8, dla z9 jeszcze dziura z8 (32480,31721)). Bez drzwi (nagranie z8 nie ma drzwi). Bez "wyjscia": plik "do" zawiera całą drogę
    # z przejściami pięter. Depo ZASTĘPCZE (32679,31687,z8) jak w planach trolli. NIEZWERYFIKOWANE NA ŻYWO: obie liny, schody w dół z7, depo; ŁOPATA na (32490,31697,z7).
    # "zasieg": 320 (jak 400 u Kazordoonu, patrz zasieg_planu): pętle leżą 150..283 pól od depo (pętla z9 x od 32396, depo x 32679), a domyślne 200 dawało "depo: brak drogi"
    # i start planu od początku pliku "do" (z9) dla pozycji na z8 daleko na zachodzie.
    {"nazwa": "abdendriel_zachod_z8", "do": "abdendriel_zachod_z8_do_depo.json", "z": "abdendriel_zachod_z8_dojscie.json", "npc": None, "prefix": False,
     "zasieg": 320},
    {"nazwa": "abdendriel_zachod_z9", "do": "abdendriel_zachod_z9_do_depo.json", "z": "abdendriel_zachod_z9_dojscie.json", "npc": None, "prefix": False,
     "zasieg": 320},
)
BAZY_PK = BAZY + tuple(p["nazwa"] for p in PLANY_PK)     # plany dostępne dla ucieczki PK (troll: istniejące depo Thais)
PK_PLAN_ZASIEG = 80                    # pola: ucieczka PK startuje z dalszej okolicy trasy niż zwykły wypad (zasięg 40)
# 21.10 K2 (SPEC_powroty_k2_1021): kanały Thais -> depo najbliższą PEWNĄ drabiną pod kratką (F1), nie zgadniętym wyjściem
# (32360,32242,z8) z thais_kanaly_do_miasta (nikt nigdy nim nie przeszedł; kutangen 15:37 ALARM). Pola drabin = ostatni punkt z8
# plików zejść kratką (jedno źródło prawdy); użycie drabiny R ląduje w (R.x, R.y+1, z7).
KANALY_THAIS = "thais_kanaly"
KANALY_THAIS_PROSTOKAT = (32320, 32170, 32440, 32285)      # x0, y0, x1, y1 na z8: okolica trasy thais_szczury_opt (32335..32422 x 32183..32272)
KANALY_THAIS_DRABINY = ("thais_dojscie_kratka.json", "thais_kratka_32422_32214.json", "thais_kratka_32339_32183.json")
WYJSCIA_BAZ = (KANALY_THAIS,)          # plany bazowe (nie PLANY_PK) liczone droga_do_depo z bieżącej pozycji przez wyjścia z z8
_WAGI_ZAPAS = {                        # oz; wartości z dane_tibia/przedmioty.json, gdy pliku brak (torch: niezweryfikowane)
    "ham": 20.0, "dragon ham": 30.0, "meat": 13.0, "cheese": 4.0, "bread": 5.0, "fish": 5.2,
    "blank": 1.2, "torch": 5.0,
}


def _wagi_domyslne():
    """Wagi po nazwie z dane_tibia/przedmioty.json (P5, 13.10); brak/uszkodzony plik albo pozycji = _WAGI_ZAPAS.
    Bot poprawia je z delty cap po zakupie (nauczone wagi w wyprawa_stan.json mają pierwszeństwo)."""
    wagi = dict(_WAGI_ZAPAS)
    try:
        with open(Path(__file__).resolve().parent / "dane_tibia" / "przedmioty.json", encoding="utf-8") as f:
            dane = json.load(f)
        po_nazwie = {}
        for lista in (dane.get("kategorie") or {}).values():
            for it in lista:
                if isinstance(it.get("waga_oz"), (int, float)) and it.get("nazwa"):
                    po_nazwie[str(it["nazwa"]).lower()] = float(it["waga_oz"])
        for klucz, nazwa in (("ham", "ham"), ("dragon ham", "dragon ham"), ("meat", "meat"), ("cheese", "cheese"),
                             ("bread", "bread"), ("fish", "fish"), ("blank", "blank rune")):
            if nazwa in po_nazwie:
                wagi[klucz] = po_nazwie[nazwa]
    except Exception:
        pass
    return wagi


WAGI_DOMYSLNE = _wagi_domyslne()
ID_BLANK = {3147}
SKRZYNIA_DEPO = (32343, 32225, 7)    # skrzynia w boksie depo (13.10): korytarz x=32343, y=32226..32227, skrzynia na jego końcu
POLE_ZLOZ_DEPO = (32343, 32226, 7)   # pole przy skrzyni (Use na północ)
ID_DEPO_ZLOZ = {3160}                                    # UH (adura vita): to, co bot odkłada do depo w wyprawie
WARTOSC_ID_ZLOTA = {3031: 1, 3035: 100, 3043: 10000}    # gold / platinum / crystal coin
GOLD_WAGA = 0.1                                          # oz za monetę (poprawka delty cap po zakupie)
SLOWA_DOMYSLNE = {"blank": "blank rune"}                 # klucz -> słowo w "buy N ..." (nadpisuje config "slowa")
NPC_DOMYSLNE = {"gorn": "Gorn", "frodo": "Frodo", "xodet": "Xodet"}

DOMYSLNE = {                                             # gdy konf (cavebot) nie ma stałej
    "WYPRAWA_AKTYWNA": 0, "WYPRAWA_ZAPAS_PROG": 0, "WYPRAWA_JEDZENIE_CEL": 20, "WYPRAWA_JEDZENIE_DOKUP": 5,
    "WYPRAWA_JEDZ_NA_MIEJSCU": 1, "WYPRAWA_JEDZ_MAKS": 12, "WYPRAWA_BLANKI": 0, "WYPRAWA_BLANKI_PROG": 2,
    "WYPRAWA_BLANKI_MAX_KOSZT": 500, "WYPRAWA_POCHODNIE": 1, "WYPRAWA_CAP_REZERWA": 8, "WYPRAWA_CAP_MIN": 10, "WYPRAWA_ZLOTO_MIN": 30,
    "WYPRAWA_MIN_HP": 70, "WYPRAWA_CO_MIN": 20, "WYPRAWA_MAX_CZAS_S": 1800, "WYPRAWA_MAX_KROKOW": 6000,
    "WYPRAWA_STOP_PRZY_UTKNIECIU": 1, "WYPRAWA_ROTACJA_NAPRAW": 3, "WYPRAWA_CZEKAJ_NA_GLOD": 0, "WYPRAWA_JEDZENIE": 1, "GLOD_ZAPAS_WAZNY_S": 120, "WYPRAWA_WZNOW_WALIDUJ": 1, "WYPRAWA_DEPO_W_WALCE": 1, "WYPRAWA_DEPO_ZLOZ": 0, "WYPRAWA_DOJSCIE_PATROLEM": 1, "WYPRAWA_TYLKO_DEPO": 0, "WYPRAWA_DEPO_POWROT": 0, "DEPO_EDRON_OBSZAR": 1, "WYPRAWA_DEPO_POSTOJ_S": 0, "WYPRAWA_DEPO_BLANKI": 1, "WYPRAWA_PO_DEPO_S": 900, "WYPRAWA_PO_DOJSCIU_S": 300, "BLANKI_AUTO_BAG": 1, "BLANKI_AUTO_BAG_MIN": 10, "JEDZENIE_ZAPAS_MIN": 5, "WYPAD_ILE_TORCHY": 5,
    "CAP_JEDZ_I_WYRZUC": 1, "CAP_JEDZ_ZOSTAW": 0, "CAP_JEDZ_ODSTEP_S": 8,
    "CAP_WALKA_CZEKAJ_S": 0,
}

POTWIERDZ = 2                  # kolejne odczyty z warunkiem = start
CAP_JEDZ_MAKS_SZTUK = 40       # 24.10: tyle sztuk jedzenia najwyżej wyrzuci jedno podejście (bezpiecznik pętli)
CAP_WALKA_LUKA_S = 90.0        # 25.10: przerwa w ocenie powodu cap dłuższa niż to = licznik czekania w walce liczony od nowa
CAP_JEDZ_PELNY_S = 60.0        # 24.10: po "You are full" przez tyle s nie próbujemy jeść ponownie (nie mielimy Use na pełnej postaci)
CAP_POPRAWA_OZ = 1.0           # 23.10 WYPRAWA_CAP_MIN: o tyle oz musi wzrosnąć cap od poprzedniego depo "z powodu cap", by wyprawa ruszyła znowu
WROC_BLOKADA_MAX_S = 180.0     # s: ręczne "Wróć do miasta" (plik WROC) czeka na spokojną chwilę najwyżej tyle, potem rezygnuje z komunikatem
GLOD_WAZNY_S = 600.0           # s: jak długo pamiętamy potwierdzony głód (cb.jedzenie_nie_do trwa tylko JEDZENIE_PONOW = 240 s)
WZNOW_MAX_S = 2400.0           # s (zegar ścienny): starszy zapis stanu = nie wznawiamy
WZNOW_ODL = 15                 # pola od najbliższego punktu odcinka, by wznowić po restarcie
SKOK_POZ = 25                  # pola na jednym piętrze między obiegami = teleport/śmierć
KOLEJKA_MAKS = 12              # tyle odpowiedzi "zajęty" resetuje czas oczekiwania na NPC (~6 s każda)
KOLEJKA_PAUZA_S = 5.0
LIMIT_DIJKSTRY = 80000
STOP_STANY = ("WALKA", "LOOT", "JEDZENIE", "POCHODNIA", "GRACZ", "UCIECZKA", "UH", "PAUZA", "MOZG", "PRZERWA",
              "WYPAD", "ML", "ZDROWIE")

ODP_PELNY = re.compile(r"you are full|you are not hungry|you cannot eat more|too full", re.I)
ODP_OFERTA = re.compile(r"buy\s+(\d+)\s+(.+?)\s+for\s+(\d+)\s+gold", re.I)
ODP_ZAJETY = re.compile(r"talking to|is talking|i am busy|i'm busy|\bbusy\b|wait a moment|please wait|"
                        r"in a moment|one at a time|in line|queue|be with you", re.I)


# --- konfiguracja i dane o sklepach -------------------------------------------

def _json(plik):
    try:
        d = json.loads(Path(plik).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _punkt(p):
    try:
        x, y, z = p
        return (int(x), int(y), int(z))
    except (TypeError, ValueError):
        return None


def wczytaj_sklepy(plik=PLIK_SKLEPOW):
    """{"frodo": {...}, "xodet": {...}} z trasy/wyprawa_sklepy.json (ręczne dane; puste pola = brak)."""
    d = _json(plik).get("przystanki", {})
    return d if isinstance(d, dict) else {}


def wczytaj_npc(plik=PLIK_NPC):
    """{"Frodo": (x, y, z)} pozycje NPC uczone z widoku."""
    wynik = {}
    for nazwa, v in _json(plik).items():
        p = _punkt(v.get("poz")) if isinstance(v, dict) else None
        if p:
            wynik[nazwa] = p
    return wynik


def drzwi_przystankow(cfg, mapa=None):
    """Zbiór pól drzwi z konfiguracji przystanków ("drzwi": [[x,y,z],...]) plus pola nagranych odcinków
    "dojscie"/"powrot", które mapa uważa za nieprzechodnie (zamknięte drzwi nagrane przez gracza)."""
    wynik = set()
    for c in (cfg or {}).values():
        if not isinstance(c, dict):
            continue
        for p in c.get("drzwi") or []:
            q = _punkt(p)
            if q:
                wynik.add(q)
        for klucz in ("dojscie", "powrot"):
            pts = [q for q in (_punkt(p) for p in c.get(klucz) or []) if q]
            wynik |= drzwi_z_mapy(pts, mapa)
    return wynik


class Trasownik:
    """Odcinki trasy po mapie (A* z generuj_trase_miasta.Graf) i wybór pola stania obok NPC."""

    def __init__(self, mapa):
        import generuj_trase_miasta as g  # noqa: PLC0415
        self.g = g
        self.graf = g.Graf(mapa)
        self._pusty = {}

    def odcinek(self, od, do):
        """Punkty [(x,y,z)] od `od` do `do` (rzadkie, z przejściami pięter) albo None."""
        od, do = tuple(od), tuple(do)
        if od == do:
            return [od]
        droga = self.graf.astar(od, do)
        if droga is None:
            return None
        return self.g.scal(self.g.rzadko(droga))

    def zalew(self, start, cele, limit=12000, promien=100):
        """Jeden Dijkstra po jednym piętrze od `start` do wielu celów naraz: {cel: punkty start..cel (rzadko)}. Cel liczy się,
        gdy sięgniemy jego pola albo pola obok (pola nagrane w kanałach bywają nieznane mapie). Nic poza piętrem startu,
        bez przejść pięter; limit węzłów i promień chronią przed zalewaniem całej mapy."""
        start = tuple(start)
        z = start[2]
        cele = {tuple(c) for c in cele if c[2] == z}
        klucz = (z, frozenset(cele))
        pusty = self._pusty.setdefault(klucz, set())
        if start in pusty:                  # wcześniejsze przeszukanie z pobliskiego pola nie dotarło do żadnego celu
            return {}
        wokol = {}
        for c in cele:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    wokol.setdefault((c[0] + dx, c[1] + dy, z), []).append(c)
        znalezione, d, skad = {}, {start: 0.0}, {start: None}
        pq = [(0.0, start)]
        n = 0
        while pq and len(znalezione) < len(cele):
            c, p = heapq.heappop(pq)
            if c > d.get(p, 1 << 60):
                continue
            for t in wokol.get(p, ()):
                if t not in znalezione:
                    sc, q = [], p
                    while q is not None:
                        sc.append(q)
                        q = skad[q]
                    sc.reverse()
                    if sc[-1] != t:
                        sc.append(t)
                    znalezione[t] = sc
            n += 1
            if n > limit:
                break
            for dx, dy, _c in self.g.RUCHY:
                q = (p[0] + dx, p[1] + dy, z)
                if max(abs(q[0] - start[0]), abs(q[1] - start[1])) > promien or not self.graf.idzie(*q):
                    continue
                nc = c + (1.0 if dx == 0 or dy == 0 else 1.001)
                if nc < d.get(q, 1 << 60):
                    d[q] = nc
                    skad[q] = p
                    heapq.heappush(pq, (nc, q))
        if not znalezione:
            pusty.update(d)                 # (przy limicie węzłów to heurystyka: wynik tylko "bez drogi", nigdy zła droga)
        return {t: self.g.scal(self.g.rzadko([(q, "idz") for q in sc])) for t, sc in znalezione.items()}

    def stoisko(self, od, npc, promien=2):
        """(pole stania, punkty drogi) najtańsze z pól w promieniu `promien` od NPC (nie samo pole NPC)."""
        npc = tuple(npc)
        kand = {(npc[0] + dx, npc[1] + dy, npc[2]) for dx in range(-promien, promien + 1)
                for dy in range(-promien, promien + 1) if (dx, dy) != (0, 0)}
        kand = {q for q in kand if self.graf.idzie(*q)}
        if not kand:
            return None
        od = tuple(od)
        d = {od: 0}
        pq = [(0, od)]
        n = 0
        while pq:
            c, p = heapq.heappop(pq)
            if c > d.get(p, 1 << 60):
                continue
            if p in kand:
                return p, self.odcinek(od, p)
            n += 1
            if n > LIMIT_DIJKSTRY:
                return None
            for q, cc, _t in self.graf.sasiedzi(p):
                nc = c + cc
                if nc < d.get(q, 1 << 60):
                    d[q] = nc
                    heapq.heappush(pq, (nc, q))
        return None


def punkty_bazy(katalog=TRASY, plany=wypad.PLANY + PLANY_PK, nazwy=BAZY):
    """{nazwa: (do_miasta, z_miasta, npc)} z plików planów wypadu (listy punktów)."""
    wynik = {}
    for p in plany:
        if p["nazwa"] not in nazwy:
            continue
        try:
            do = [_punkt(q) for q in json.loads((Path(katalog) / p["do"]).read_text())]
            z = [_punkt(q) for q in json.loads((Path(katalog) / p["z"]).read_text())]
        except (OSError, ValueError, TypeError):
            continue
        if None in do or None in z or not do or not z:
            continue
        wynik[p["nazwa"]] = (do, z, p.get("npc") or "Gorn")
    return wynik


# 23.10: plan, który wybierany po najbliższym punkcie "do" tylko z podanych pięter. thais_pn_z9 ma w pliku "do" siedem punktów z8
# (korytarz y=32123 do liny), bliżej wschodniego końca pętli thais_pn_z8 niż "do" planu thais_pn: bez tego postać z pętli z8 dostawała
# plan z9 i szła A* pod dziurę (32356,32122,z8), w której zginął kutangen (test: testy/test_powrot_thais_pn_z9.py 4f).
# 24.10 (trolle_kazordoon_z7, generuj_trasy_kazordoon_powierzchnia.py): "do" planów z8/z9 zawiera całą drogę z7 (+ most z6), a pętla spotu z7
# leży przy niej; bez ograniczenia postać z pętli z7 dostawała plan z8 (bliższy punkt "do" = lądowanie liny) i szła obok dziury
# (32663,31962,z7). Z8/z9 wybierane więc tylko z pięter jaskini; z7/z6 obsługuje plan trolle_kazordoon_z7 (to samo "do" na drodze).
# SUBSTITUTE DECISION (be-dev, do przeglądu leada): zmiana wyboru bazy dla postaci na z7/z6 po wyjściu liną z jaskini z8.
PLAN_PIETRA_WYBOR = {"thais_pn_z9": (9, 10), "trolle_kazordoon_z8": (8, 9, 10), "trolle_kazordoon_z9": (8, 9, 10, 11),
                     # 27.10 (abdendriel_zachod_z9): "do" z9 ma 74 punkty z8 (A* od lądowania liny do liny z8), bliżej wielu pól pętli z8 niż jedyny punkt z8 planu
                     # abdendriel_zachod_z8; bez ograniczenia postać z pętli z8 dostawała plan z9 (554 z 683 punktów), a jego "z" (powrót po karencji PK) kończy się na z9.
                     "abdendriel_zachod_z9": (9,)}


def wybierz_baze(baza, poz, zasieg=wypad.PLAN_ZASIEG):
    """Nazwa planu bazowego z punktem do_miasta najbliżej `poz` na tym piętrze (<= zasieg pól) albo None."""
    najl = None
    for nazwa, (do, _z, _n) in baza.items():
        if nazwa in PLAN_PIETRA_WYBOR and poz[2] not in PLAN_PIETRA_WYBOR[nazwa]:
            continue
        d = min((cheb(poz, q) for q in do if q[2] == poz[2]), default=None)
        if d is not None and d <= zasieg and (najl is None or d < najl[0]):
            najl = (d, nazwa)
    return najl[1] if najl else None


# --- optymalna droga do depo z dowolnego miejsca spotu (16.10) --------------------------------------------------
# Plan z PLANY_PK (Edron) nie startuje już od początku nagrania "do" ani nie wymaga stania przy nim: z bieżącej pozycji
# szukamy najkrótszej drogi do depo spośród: (1) marsz po piętrze (A* po mapie) do punktu wejścia w nagraną trasę "do"
# i dalej jej końcówką, (2) dojście do pętli łowiska (cb.punkty), marsz po niej do przodu albo wstecz (przejścia pięter
# wstecz tylko z pietra.kandydaci "pewne", czyli mapa potwierdza dziurę/linę/schody) i zejście z pętli A* do trasy "do".
DEPO_DOJSCIE_ZASIEG = 200      # pola (Chebyshev): dalej od depo planu nie ruszamy tą drogą (inne miasto/serwer)


def zasieg_planu(nazwa):
    """Zasięg (pola od depo) drogi do depo dla planu `nazwa` z PLANY_PK: klucz "zasieg" planu, domyślnie DEPO_DOJSCIE_ZASIEG.
    23.10: trolle Kazordoon leżą ~305 pól od depo Thais, więc plan ma zasięg 400; reszta planów bez zmian."""
    for p in PLANY_PK:
        if p["nazwa"] == nazwa:
            return int(p.get("zasieg") or DEPO_DOJSCIE_ZASIEG)
    return DEPO_DOJSCIE_ZASIEG
DEPO_KOSZT_DOL = 4             # koszt (w "polach") zejścia o piętro (dziura/schody w dół)
DEPO_KOSZT_GORA = 8            # wejścia o piętro (lina/drabina/schody w górę)
DEPO_KOSZT_ODWROT = 10         # kara za przejście pięter w odwrotną stronę niż nagranie (nie było przećwiczone przez bota)
DEPO_WEJSCIA = 6               # ile (x4) najtańszych wejść z pozycji na pętlę łowiska rozważamy
DEPO_LIMIT_S = 8.0             # s: po tym czasie liczenia bierzemy najlepszą dotąd drogę (plan powstaje raz, na starcie wyprawy)
DEPO_ZALEW_LIMIT = 12000       # węzłów jednego przeszukania piętra (Trasownik.zalew); poza tym "brak drogi"
PLIK_PETLA_EDRON = "edron_nowy_spot.json"    # gdy cb.punkty jest puste


def koszt_punktow(pts):
    """Koszt marszu po liście punktów: Chebyshev na piętrze, stała za zmianę piętra (dół tańszy niż góra)."""
    k = 0
    for a, b in zip(pts, pts[1:]):
        if a[2] == b[2]:
            k += cheb(a, b)
        else:
            k += DEPO_KOSZT_DOL if b[2] > a[2] else DEPO_KOSZT_GORA
    return k


def _przejscie_odwrotne(mapa, a, b):
    """Punkty [pole stania, lądowanie, ...] przejścia z `a` na `b` (inne piętro) w kierunku, w którym trasa nie była
    nagrana, albo None. Tylko kandydat "pewny" z pietra.kandydaci (mapa potwierdza dziurę/schody/linę); w górę tylko
    taki, który zbuduj_etapy odtworzy jako LINA (lądowanie = pole stania + (0, 1))."""
    if mapa is None:
        return None
    try:
        import pietra  # noqa: PLC0415
        kand = pietra.kandydaci(mapa, a, b)
    except Exception:
        return None
    for k in kand:
        if not k.get("pewne"):
            continue
        pole, lad = tuple(k["pole"]), tuple(k["lad"])
        if pole[2] != a[2] or lad[2] != b[2] or cheb(pole, a) > 3:
            continue
        if b[2] < a[2] and lad != (pole[0], pole[1] + 1, pole[2] - 1):
            continue
        if b[2] > a[2] and lad[:2] != pole[:2]:
            continue
        if lad[2] == b[2] and cheb(lad, b) > 3:
            continue
        pts = [pole] if pole != tuple(a) else []
        pts.append(lad)
        if lad != tuple(b):
            pts.append(tuple(b))
        return pts
    return None


def _droga_do_depo(poz, petla, do, zalew, mapa=None, limit_s=None, zasieg=None):
    """Najkrótsza droga z `poz` do końca nagranej trasy `do` (depo). `petla` = zamknięta trasa łowiska (cb.punkty)
    albo []. `zalew(a, cele)` -> {cel: punkty a..cel na jednym piętrze} dla osiągalnych celów (jedno przeszukanie na
    wielu celów). -> (punkty, koszt, opis) albo None. Wynik jest ciągły: kolejne punkty to kroki nagranej trasy, marsz
    po piętrze, nagrane przejście albo przejście z pietra.kandydaci.
"""
    t_koniec = time.monotonic() + (DEPO_LIMIT_S if limit_s is None else limit_s)
    poz = (int(poz[0]), int(poz[1]), int(poz[2]))
    do = [tuple(q) for q in do]
    petla = [tuple(q) for q in (petla or [])]
    if not do or cheb(poz, do[-1]) > (DEPO_DOJSCIE_ZASIEG if zasieg is None else zasieg):
        return None
    n, nd = len(petla), len(do)
    rem = [0] * nd                       # koszt końcówki do[j:]
    for j in range(nd - 2, -1, -1):
        rem[j] = rem[j + 1] + koszt_punktow([do[j], do[j + 1]])
    cache = {}
    odwr = {}

    def odwrotne(a, b):
        if (a, b) not in odwr:
            odwr[(a, b)] = _przejscie_odwrotne(mapa, a, b)
        return odwr[(a, b)]

    def marsze(a, cele):
        """{cel: punkty} z `a` po jego piętrze (cache na pole startu)."""
        if a not in cache:
            try:
                cache[a] = {t: p for t, p in (zalew(a, cele) or {}).items() if all(q[2] == a[2] for q in p)}
            except bot.Zatrzymano:
                raise
            except Exception:
                cache[a] = {}
        return cache[a]

    cele_z_poz = [q for q in do + petla if q[2] == poz[2]]
    z_poz = marsze(poz, cele_z_poz)
    wejscia = []                         # (koszt, punkty poz -> petla[i], i)
    najl = None

    def zglos(pts, opis):
        nonlocal najl
        k = koszt_punktow(pts)
        if najl is None or k < najl[0]:
            najl = (k, pts, opis)

    for j, q in enumerate(do):
        if q in z_poz:
            zglos(z_poz[q] + do[j + 1:], f"marsz do trasy 'do' (punkt {j})")
    for i, q in enumerate(petla):
        if q in z_poz:
            wejscia.append((koszt_punktow(z_poz[q]), z_poz[q], i))
    wejscia.sort(key=lambda w: w[0])
    def dolna(cur):
        """Dolna granica kosztu reszty drogi z pola pętli `cur` (linia prosta do trasy 'do' + jej końcówka)."""
        if cur not in dolna_cache:
            dolna_cache[cur] = min((cheb(cur, do[j]) + rem[j] for j in range(nd) if do[j][2] == cur[2]), default=None)
        return dolna_cache[cur]

    dolna_cache = {}

    def bieg(i, kier, kroki, m0):
        """Punkty i koszt marszu po pętli od węzła i o `kroki` kroków w kierunku `kier` (None: odwrotne przejście niemożliwe)."""
        pts, acc, m = list(m0), koszt_punktow(m0), i
        for _ in range(kroki):
            nm = (m + kier) % n
            cur, nxt = petla[m], petla[nm]
            ex = [nxt] if (cur[2] == nxt[2] or kier > 0) else odwrotne(cur, nxt)
            if ex is None:
                return None
            for q in ex:
                if pts[-1] != q:
                    acc += koszt_punktow([pts[-1], q])
                    pts.append(q)
            if kier < 0 and cur[2] != nxt[2]:
                acc += DEPO_KOSZT_ODWROT
            m = nm
        return pts, acc, m

    kand = []                            # (dolna granica kosztu, kolejność, wejście i, kierunek, kroków, koszt dojścia)
    uzyte = set()
    for k0, m0, i in wejscia[:DEPO_WEJSCIA * 4]:
        if petla[i] in uzyte:
            continue
        uzyte.add(petla[i])
        for kier in (1, -1):
            pts, acc, m = list(m0), k0, i
            for kroki in range(n):
                cur = petla[m]
                lb = dolna(cur)
                if lb is not None:
                    kand.append((acc + lb, len(kand), i, kier, kroki, m0))
                nm = (m + kier) % n
                nxt = petla[nm]
                if cur[2] == nxt[2] or kier > 0:
                    ex = [nxt]
                else:
                    ex = odwrotne(cur, nxt)
                    if ex is None:
                        break
                for q in ex:
                    if pts[-1] != q:
                        acc += koszt_punktow([pts[-1], q])
                        pts.append(q)
                if kier < 0 and cur[2] != nxt[2]:
                    acc += DEPO_KOSZT_ODWROT
                m = nm
                if najl is not None and acc >= najl[0]:
                    break
    kand.sort(key=lambda c: (c[0], c[1]))
    for lb, _, i, kier, kroki, m0 in kand:
        if najl is not None and (lb >= najl[0] or time.monotonic() > t_koniec):
            break
        r = bieg(i, kier, kroki, m0)
        if r is None:
            continue
        pts, acc, m = r
        cur = petla[m]
        osiag = marsze(cur, [q for q in do if q[2] == cur[2]])
        for j in range(nd):
            wy = osiag.get(do[j])
            if wy is None and do[j][2] == cur[2] and cheb(cur, do[j]) <= 1:
                wy = [cur, do[j]]
            if wy:
                zglos(pts + wy[1:] + do[j + 1:],
                      f"pętla od {i} {'do przodu' if kier > 0 else 'wstecz'} do {m}, wyjście na punkt {j}")
    if najl is None:
        return None
    k, pts, opis = najl
    wyn = []
    for q in pts:
        q = (int(q[0]), int(q[1]), int(q[2]))
        if not wyn or wyn[-1] != q:
            wyn.append(q)
    return wyn, k, opis

def _po_petli_do_liny(poz, petla, pole, ext):
    """Gdy `poz` leży na pętli łowiska (jedno piętro, bez przejść), dojście do pola liny `pole` (<= 1 pole od punktu
    pętli) krótszym kierunkiem po pętli, potem `ext` (lina i dalej). (punkty, koszt, opis) albo None."""
    p = [tuple(q) for q in (petla or [])]
    if len(p) < 3 or poz[2] != pole[2] or any(q[2] != pole[2] for q in p):
        return None
    blisko = min(cheb(q, poz) for q in p)
    if blisko > 4:                         # za daleko od pętli: zwykłe szukanie po mapie
        return None
    n = len(p)
    cele = [t for t, q in enumerate(p) if cheb(q, pole) <= 1]
    if not cele:
        return None
    najl = None
    for i in [i for i, q in enumerate(p) if cheb(q, poz) == blisko]:
        for t in cele:
            for kier in (1, -1):
                d = ((t - i) * kier) % n
                if najl is None or d < najl[0]:
                    najl = (d, i, kier)
    d, i, kier = najl
    pts = ([poz] if p[i] != poz else []) + [p[(i + kier * m) % n] for m in range(d + 1)]
    if pts[-1] != pole and cheb(pts[-1], pole) > 1:
        return None
    pts = pts + [q for q in ext if q != pts[-1]]
    return pts, koszt_punktow(pts), f"po pętli {d} pól do liny {pole}"


def droga_do_depo(poz, petla, do, zalew, mapa=None, limit_s=None, wyjscia=(), zasieg=None):
    """Jak _droga_do_depo, a gdy pętla łowiska nie ma przejścia pięter (Edron gobliny z9), `wyjscia` =
    ((pole liny na piętrze poz, lądowanie piętro wyżej), ...) dodaje wariant: nagrana trasa "do" poprzedzona liną
    pole -> lądowanie i marszem po górnym piętrze (zalew) do niej. Wygrywa tańszy wariant."""
    wyn = None
    do_t = [tuple(q) for q in do]
    szybko = False
    do_baza = do_t
    for wyj in wyjscia:
        pole, lad = wyj[0], wyj[1]
        pole = (int(pole[0]), int(pole[1]), int(pole[2]))
        lad = (int(lad[0]), int(lad[1]), int(lad[2]))
        do_t = do_baza
        if len(wyj) > 2 and wyj[2]:         # wyjście ma własną trasę dalszą (plan "edron" startuje daleko od liny)
            try:
                do_t = [tuple(int(v) for v in q) for q in json.loads((TRASY / wyj[2]).read_text())]
            except (OSError, ValueError, TypeError):
                continue
        if pole[2] != int(poz[2]) or lad[2] >= pole[2]:
            continue
        try:
            gora = {t: p for t, p in (zalew(lad, [q for q in do_t if q[2] == lad[2]]) or {}).items()
                    if all(q[2] == lad[2] for q in p)}
        except bot.Zatrzymano:
            raise
        except Exception:
            continue
        # 21.10 K2: wyj[3] = pola stania obok pola przejścia (drabiny Thais: północ bywa ścianą); domyślnie pole na północ od liny
        stoiska = [(pole[0], pole[1] - 1, pole[2])]      # lina: stoimy pole na północ od pola liny (jak z8 -> z7 17.10)
        if len(wyj) > 3 and wyj[3]:
            stoiska = [(int(s[0]), int(s[1]), int(s[2])) for s in wyj[3]]
        for j, q in enumerate(do_t):
            wy = gora.get(q)
            if wy is None and q[2] == lad[2] and cheb(lad, q) <= 1:
                wy = [lad, q]
            if wy:
                for stoi in stoiska:
                    ext = [stoi, lad] + [tuple(r) for r in wy[1:]] + do_t[j + 1:]
                    alt = _po_petli_do_liny(tuple(int(v) for v in poz), petla, stoi, ext)     # szybko: stoimy na pętli
                    if alt is not None:
                        szybko = True
                    else:
                        alt = _droga_do_depo(poz, petla, ext, zalew, mapa, limit_s, zasieg)
                    if alt is not None and (wyn is None or alt[1] < wyn[1]):
                        wyn = (alt[0], alt[1], alt[2] if szybko else f"wyjście liną {pole} -> {lad}; {alt[2]}")
                break
    if wyn is None or not szybko:          # stoimy poza pętlą albo brak wyjść: zwykłe szukanie (pętla/trasa "do"), tańszy wygrywa
        baza = _droga_do_depo(poz, petla, do, zalew, mapa, limit_s, zasieg)
        if baza is not None and (wyn is None or baza[1] < wyn[1]):
            wyn = baza
    return wyn


# --- operacje na żywo ----------------------------------------------------------

class OperacjeZywe(wypad.OperacjeZywe):
    """Operacje wypadu + jedzenie przy NPC i plecak z pojemnikami na runy (blank runy)."""

    def plecak(self):
        import loot  # noqa: PLC0415
        odp = self.zapytaj({"cmd": "kontenery"})
        kont = [k for k in (odp.get("kontenery") or []) if loot.czy_plecak(k) or loot.czy_runy(k)]
        if not any(loot.czy_plecak(k) for k in kont):
            return None
        ids = {}
        for k in kont:
            for p in k.get("przedmioty", []):
                ids[p["id"]] = ids.get(p["id"], 0) + max(1, p.get("ilosc", 1))
        return {"id": ids}

    def zloz_w_depo(self, pozycja, ids=None):
        """Otwiera skrzynię depo obok postaci (Use na sąsiednich polach, aż pojawi się nowy kontener), przenosi
        przedmioty z `ids` (domyślnie UH) z plecaków do skrzyni i zamyka ją. Zwraca {"otwarte","przeniesione","powod"}."""
        import loot  # noqa: PLC0415
        import ekran  # noqa: PLC0415
        ids = set(ids or ID_DEPO_ZLOZ)
        wynik = {"otwarte": False, "przeniesione": 0, "powod": None}
        kon0, powod = loot.kontenery_z_pamieci()
        if kon0 is None:
            wynik["powod"] = f"pamięć: {powod}"
            return wynik
        if not any(q["id"] in ids for k in kon0 for q in k.get("przedmioty", [])):
            wynik["powod"] = "nic do złożenia"
            return wynik
        numery0 = {k.get("numer") for k in kon0}
        poz0 = tuple(pozycja())
        skrzynia = None
        kolejnosc = [(0, -1), (1, 0), (0, 1), (-1, 0), (1, -1), (1, 1), (-1, 1), (-1, -1)]
        if poz0[2] == SKRZYNIA_DEPO[2]:
            d = (SKRZYNIA_DEPO[0] - poz0[0], SKRZYNIA_DEPO[1] - poz0[1])
            if d in kolejnosc:                      # znana skrzynia obok: najpierw ona
                kolejnosc.remove(d)
                kolejnosc.insert(0, d)
        self.log(f"Wyprawa: składanie w depo z {poz0}, skrzynia {SKRZYNIA_DEPO}, kolejność Use {kolejnosc[:3]}...")
        for dx, dy in kolejnosc:
            ekran.otworz(dx, dy)
            time.sleep(0.9)
            if tuple(pozycja()) != poz0:
                wynik["powod"] = f"pozycja zmieniła się przy otwieraniu ({poz0} -> {tuple(pozycja())}), przerywam"
                return wynik
            kon, _ = loot.kontenery_z_pamieci()
            nowe = [k for k in kon or [] if k.get("numer") not in numery0]
            if nowe:
                skrzynia = nowe[0]
                break
        if skrzynia is None:
            wynik["powod"] = "nie otworzyłem skrzyni depo (brak nowego kontenera przy 8 sąsiednich polach)"
            return wynik
        wynik["otwarte"] = True
        n = skrzynia.get("numer")
        self.log(f"Wyprawa: skrzynia depo otwarta: {skrzynia.get('nazwa')!r}, pojemność {skrzynia.get('pojemnosc')}")
        ile, powod = loot.przenies_miedzy(
            ids, lambda k: k.get("numer") != n and any(q["id"] in ids for q in k.get("przedmioty", [])),
            lambda k: k.get("numer") == n, log=self.log)
        wynik["przeniesione"], wynik["powod"] = ile, powod
        try:
            loot.zamknij_kontener(n, log=self.log)
        except bot.Zatrzymano:
            raise
        except Exception as ex:
            self.log(f"Wyprawa: nie zamknąłem skrzyni depo ({ex!r})")
        return wynik

    def przenies_runy(self):
        """Blanki/runy z plecaka do pojemnika na runy (loot.przenies_do_runow); liczba przeniesionych."""
        import loot  # noqa: PLC0415
        return loot.przenies_do_runow(log=self.log)

    def blanki_i_miejsce(self):
        """(blanki w głównym plecaku, wolne pola w bagu na runy albo None); None = odczyt nie działa."""
        import loot  # noqa: PLC0415
        return loot.blanki_i_miejsce()

    def zjedz(self):
        """Jeden Use na jedzeniu z plecaka (loot.zjedz): lista zjedzonych nazw; [] = nic nie ubyło (najedzony)."""
        import loot  # noqa: PLC0415
        return loot.zjedz(1, log=self.log)

    def wyrzuc_jedzenie(self):
        """Jedna sztuka jedzenia z plecaka na ziemię pod postacią (loot.wyrzuc_jedzenie): (wyrzucono 0/1, zostało albo None, powód)."""
        import loot  # noqa: PLC0415
        return loot.wyrzuc_jedzenie(log=self.log)


def kup_u_npc(npc, przedmiot, n, limit_gp, ops=None, log=print, ja=None, czekaj_s=9.0, spij=time.sleep):
    """Zakup poza wyprawą u NPC stojącego obok: hi -> buy N przedmiot -> yes (tylko gdy oferta mieści się w n i limit_gp).
    limit_gp None = bez limitu. Nic nie robi poza czatem. Zwraca {"ok", "powod", "oferta": (ile, gp) albo None}.
    powod: None | "brak_powitania" | "brak_oferty" | "za_drogo" | "zla_zakladka" (ja = nazwa postaci na innym kanale)."""
    if ops is None:
        import mozg  # noqa: PLC0415
        ops = wypad.OperacjeZywe(log=log, wyslij=lambda t: mozg.wpisz_na_czacie(t))

    def czekaj(wzor, s):
        t0 = time.time()
        while time.time() - t0 < s:
            for w in ops.wiadomosci():
                log(f"  [{w['autor']}/{w['kanal']}] {w['tekst']}")
                if ja and w["autor"] == ja:
                    if w["kanal"] not in ("Default", ""):
                        return "zla_zakladka"
                    continue
                if re.search(wzor, w["tekst"]) if isinstance(wzor, str) else wzor.search(w["tekst"]):
                    return w["tekst"]
            spij(0.6)
        return None

    ops.wiadomosci()
    ops.czat("hi")
    r = czekaj(wypad.ODP_POWITANIE, czekaj_s)
    if r == "zla_zakladka":
        return {"ok": False, "powod": "zla_zakladka", "oferta": None}
    if r is None:
        log(f"kup_u_npc: {npc} nie odpowiada na hi (nie stoi obok?)")
        return {"ok": False, "powod": "brak_powitania", "oferta": None}
    ops.czat(f"buy {n} {przedmiot}")
    r = czekaj(ODP_OFERTA, czekaj_s)
    if r == "zla_zakladka":
        return {"ok": False, "powod": "zla_zakladka", "oferta": None}
    m = ODP_OFERTA.search(r) if r else None
    if m is None:
        log(f"kup_u_npc: brak oferty od {npc}")
        return {"ok": False, "powod": "brak_oferty", "oferta": None}
    oferta = (int(m[1]), int(m[3]))
    log(f"kup_u_npc: oferta {oferta[0]} za {oferta[1]} gp")
    if oferta[0] <= 0 or oferta[0] > n or (limit_gp is not None and oferta[1] > limit_gp):
        ops.czat("no")
        return {"ok": False, "powod": "za_drogo", "oferta": oferta}
    ops.czat("yes")
    czekaj(re.compile(r"here you are|bought|thank", re.I), 8.0)
    return {"ok": True, "powod": None, "oferta": oferta}


# --- wyprawa ---------------------------------------------------------------------

class Wyprawa(Wypad):
    """Wypad do Thais po zapasy. Wołany tak jak Wypad (Cavebot._wypad_tick); torch-trip z wypad.py zostaje."""

    def __init__(self, cb, ops, konf=None, log=print, katalog=TRASY, plik_stanu=None, plik_sklepow=None,
                 plik_npc=None, plik_stop=None, czas=time.time, trasownik=None, **kw):
        super().__init__(cb, ops, konf=konf, log=log, katalog=katalog, **kw)
        self.plik_stanu = Path(plik_stanu or PLIK_STANU)
        self.plik_sklepow = Path(plik_sklepow or PLIK_SKLEPOW)
        self.plik_npc = Path(plik_npc or PLIK_NPC)
        self.plik_stop = Path(plik_stop) if plik_stop else None     # None = bot.STOP
        self.czas = czas
        self._trasownik = trasownik
        self.w = None                    # bieżąca wyprawa: {"stops","legs","k","powod","baza",...}
        self._plan_wyprawy = None
        self._wznowiono = False
        self.potw_w = 0
        self.glod_potw_do = float("-inf")   # do kiedy ważny potwierdzony głód (WYPRAWA_CZEKAJ_NA_GLOD)
        self.zapas_wiarygodny_t = float("-inf")   # kiedy ostatnio odczytano zapas z widocznego plecaka
        self.sprawdzono_w = float("-inf")
        self._blanki_auto_t = None          # N9: czas ostatniej próby przeniesienia blanków do bagu (None = jeszcze nie)
        self.nast_wyprawa = float("-inf")
        self._wroc_od = None                # kiedy zobaczyliśmy plik WROC (ręczne "Wróć do miasta"); None = brak zlecenia
        self._wroc_powod = None             # ostatni powód, dla którego jeszcze nie ruszyliśmy (do logu i komunikatu)
        self._ost_poz_w = None
        self._npc_zapis = float("-inf")
        self._brak_pozycji_log = set()
        dane = _json(self.plik_stanu)
        self.wagi = {k: float(v) for k, v in (dane.get("wagi") or {}).items() if isinstance(v, (int, float))}
        self.ceny = {k: float(v) for k, v in (dane.get("ceny") or {}).items() if isinstance(v, (int, float))}
        self.npc_widziane = wczytaj_npc(self.plik_npc)

    # --- konfiguracja ---

    def _k(self, nazwa, domyslna):
        if nazwa == "WYPAD_JEDZENIE" and self._wyprawa_wlaczona():
            return False              # jedzenie: wyprawa (Frodo), nie wypad u Al Dee
        return super()._k(nazwa, domyslna)

    def _wyprawa_wlaczona(self):
        return bool(self.konf is not None and getattr(self.konf, "WYPRAWA_AKTYWNA", 0))

    def _kw(self, nazwa):
        return self._k(nazwa, DOMYSLNE.get(nazwa))

    _cap_jedz_nast = float("-inf")     # 24.10: najwcześniejsza chwila kolejnego podejścia "zjedz i wyrzuć" (krótki odstęp ochronny)
    _cap_walka_od = None               # 25.10: od kiedy czekamy w walce na spokój z samym powodem cap (None = nie czekamy)
    _cap_walka_ost = None              # 25.10: chwila ostatniej oceny tego czekania (wykrywa przerwę > CAP_WALKA_LUKA_S)
    _cap_jedz_pelny = float("-inf")    # chwila ostatniego "You are full" / jedzenie nie ubyło
    _cap_jedz_bledy = 0                # kolejne nieudane wyrzucenia (2 = wracamy do dawnej wyprawy po cap)

    def _tryb_depo(self):
        """Pokrętło: nowe wyprawy idą tylko do depo."""
        return bool(int(self._kw("WYPRAWA_TYLKO_DEPO")))

    def _w_depo(self):
        """Trwająca wyprawa jest wyprawą do depo (flaga w zapisanych potrzebach, przeżywa restart)."""
        return bool(self.w is not None and (self.w.get("potrzeby") or {}).get("depo"))

    def _pole_depo(self):
        try:
            d = json.loads((Path(self.katalog) / PLIK_DEPO).read_text())
            p = _punkt(d[0])
            if p:
                return p
        except (OSError, ValueError, TypeError, IndexError):
            pass
        return DEPO_POLE

    def _max_czas(self):
        if self.w is not None:
            return float(self._kw("WYPRAWA_MAX_CZAS_S"))
        return super()._max_czas()

    # --- trwały stan ---

    def _stan_czytaj(self):
        return _json(self.plik_stanu)

    def _stan_zapisz(self, **zmiany):
        d = self._stan_czytaj()
        d["wagi"], d["ceny"] = dict(self.wagi), dict(self.ceny)
        d.update(zmiany)
        try:
            self.plik_stanu.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.plik_stanu.with_name(self.plik_stanu.name + ".tmp")
            tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1))
            os.replace(tmp, self.plik_stanu)
        except OSError as e:
            self.log(f"Wyprawa: nie zapisałem stanu ({e})")

    def _stan_trasy(self, **extra):
        w = self.w
        if w is None:
            return
        self._stan_zapisz(aktywna=True, przerwana=False, powod=w["powod"], baza=w["baza"], k=w["k"],
                          faza=self.faza, potrzeby=w["potrzeby"], t_wall=w["t_wall"],
                          kupione=dict(self.kupione), zapis_wall=self.czas(), **extra)

    def _stan_koniec(self, **extra):
        self._stan_zapisz(aktywna=False, przerwana=False, faza=None, zapis_wall=self.czas(), **extra)

    # --- pomocnicze odczyty ---

    def _tele_w(self, typ, **d):
        self._tele(typ, **d)

    def _cap(self):
        try:
            g = self.cb.gracz()
        except bot.Zatrzymano:
            raise
        except Exception:
            return None
        cap = g.get("cap")                # wolne oz; max_cap nie służy do decyzji (13.10: protokół 7.4 daje max_cap == cap)
        if cap is None:
            return None
        if cap > 5000:                  # cap w setnych oz (niezweryfikowane)
            cap = cap / 100.0
        return float(cap)

    def _zloto(self, plecak=None):
        if plecak is None:
            try:
                plecak = self.ops.plecak()
            except bot.Zatrzymano:
                raise
            except Exception:
                return None
        if plecak is None:
            return None
        return sum(n * WARTOSC_ID_ZLOTA[i] for i, n in plecak.get("id", {}).items() if i in WARTOSC_ID_ZLOTA)

    def _waga(self, klucz):
        return self.wagi.get(klucz, WAGI_DOMYSLNE.get(klucz))

    def _ids(self, klucz):
        ids = super()._ids(klucz)
        if ids:
            return ids
        if klucz in ("blank", "blank rune"):
            return set(ID_BLANK)
        try:
            import loot  # noqa: PLC0415
            if klucz in loot.JEDZENIE_ID:
                return {loot.JEDZENIE_ID[klucz]}
        except Exception:
            pass
        return set()

    def _slowo(self, klucz):
        if self.w is not None:
            for st in self.w["stops"]:
                if klucz in (st.get("slowa") or {}):
                    return st["slowa"][klucz]
        return SLOWA_DOMYSLNE.get(klucz) or super()._slowo(klucz)

    def _uh_blokuje(self):
        cb = self.cb
        if getattr(cb, "uh_restore", None):
            return True
        plik = getattr(self.konf, "UH_STAN_PLIK", None)
        if plik:
            return bool(_json(plik).get("tarcza_id"))
        return False

    # --- uczenie pozycji NPC ---

    def _ucz_npc(self, lista, teraz):
        nazwy = {n.casefold(): n for n in NPC_DOMYSLNE.values()}
        zmiana = False
        for s in lista or []:
            n = (s.get("nazwa") or "").casefold()
            if n not in nazwy or s.get("hp", 100) <= 0 or s.get("x") is None:
                continue
            p = (int(s["x"]), int(s["y"]), int(s.get("z", 0)))
            if self.npc_widziane.get(nazwy[n]) != p:
                self.npc_widziane[nazwy[n]] = p
                zmiana = True
        if zmiana and teraz - self._npc_zapis > 30.0:
            self._npc_zapis = teraz
            try:
                self.plik_npc.write_text(json.dumps(
                    {n: {"poz": list(p), "wall": self.czas()} for n, p in self.npc_widziane.items()},
                    ensure_ascii=False, indent=1))
                self.log(f"Wyprawa: zapisałem pozycje NPC {self.npc_widziane}")
            except OSError:
                pass

    # --- wyzwalacz ---

    def _blokada_startu(self, teraz, poz, lista, w_walce=False, reczny=False):
        """Dlaczego wyprawa jeszcze nie może ruszyć (None = może). `reczny` (24.10, plik WROC): w dojściu na spot ręczne
        "Wróć do miasta" przerywa dojście zamiast czekać na jego koniec, a potwory w pobliżu go nie blokują (dojście i tak
        biegnie przez nie, wyprawa też); walka, ucieczka, loot, czar, GM, gracz i HP blokują jak zawsze."""
        cb = self.cb
        if getattr(cb, "wypad_aktywny", False):
            return "wypad"
        w_dojsciu = bool(getattr(cb, "dojscie_aktywne", False))
        if w_dojsciu and not reczny:      # P7a: dojście z depo na spot nie startuje AUTOMATYCZNEJ wyprawy (blanki, cap, jedzenie)
            return "dojscie"
        if w_walce:
            # wyprawa do depo po potwierdzonym głodzie startuje także w walce (potem biegnie, bije tylko zablokowana):
            # blokują tylko ucieczka/ostrożność, czar w toku i alarm GM
            if getattr(cb, "ucieczka", False) or getattr(cb, "ostrozny", False):
                return "ucieczka"
            for atr in ("zd_oczekuje", "jc_oczekuje", "jz_oczekuje", "ml_oczekuje"):
                if getattr(cb, atr, None) is not None:
                    return "czar_w_toku"
            czat = getattr(cb, "wypad_czat", None)
            if czat is not None and getattr(czat, "zablokowany", False):
                return "alarm_gm"
            return None
        if cb.cel is not None or getattr(cb, "ucieczka", False) or getattr(cb, "ostrozny", False) \
                or getattr(cb, "w_poscigu", False) or getattr(cb, "pamiec", None) is not None:
            return "walka"
        if getattr(cb, "w_lootcie", False) or getattr(cb, "lww", None) is not None \
                or getattr(cb, "lww_zalegle", None) is not None or getattr(cb, "zwloki_czekajace", None):
            return "loot"
        if str(getattr(cb, "stan", "")).startswith(STOP_STANY):
            return "stan"
        for atr in ("zd_oczekuje", "jc_oczekuje", "jz_oczekuje", "ml_oczekuje"):
            if getattr(cb, atr, None) is not None:
                return "czar_w_toku"
        fn = getattr(cb, "_czar_blokada", None)
        if callable(fn) and fn() is not None:
            return "czar_blokada"
        if self._uh_blokuje():
            return "uh"
        czat = getattr(cb, "wypad_czat", None)
        if czat is not None and getattr(czat, "zablokowany", False):
            return "alarm_gm"
        moby = cb._zywe_w_promieniu(lista, poz, wypad.MOBY_ODL)
        if moby and not (reczny and w_dojsciu):
            return "moby"
        ja = getattr(getattr(cb, "postac", None), "nazwa", None)
        if getattr(cb, "stanowisko", None) is not None:
            return None                                # 22.10 stoj w mieście: obcy gracze są zawsze w pobliżu, nie blokują serwisu
        for s in lista or []:
            if s.get("gracz") and s.get("nazwa") != ja and s.get("z") == poz[2] and s.get("hp", 100) > 0 \
                    and cheb((s["x"], s["y"]), poz) <= 14:
                return "gracz"
        return None

    def _okazja(self, teraz):
        if not self._wznowiono:
            self._wznowiono = True
            try:
                if self._wznow(teraz):
                    return True
            except bot.Zatrzymano:
                raise
            except Exception as e:
                self._blad("wznowienie", opis=repr(e))
        try:
            self._blanki_auto(teraz)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            self._blad("blanki_auto", opis=repr(e))
        try:
            lista = getattr(self.cb, "ostatnie_stwory", [])
            self._ucz_npc(lista, teraz)
            if self._okazja_wyprawa(teraz):
                return True
        except bot.Zatrzymano:
            raise
        except Exception as e:
            self._blad("wyprawa_okazja", opis=repr(e))
        return super()._okazja(teraz)

    def _blanki_auto(self, teraz):
        """N9: blanki z głównego plecaka do bagu na runy poza wyprawą: raz zaraz po starcie, potem co
        BLANKI_AUTO_BAG_MIN min, tylko w spokoju (bez walki/lootu/UH/potworów). Bez wolnego pola nie rusza myszy."""
        if not int(self._kw("BLANKI_AUTO_BAG")) or self.zablokowany or teraz < self.blokada_do:
            return False
        if self._blanki_auto_t is not None and \
                teraz - self._blanki_auto_t < float(self._kw("BLANKI_AUTO_BAG_MIN")) * 60.0:
            return False
        cb = self.cb
        poz = cb.ruch_poz if getattr(cb, "ruch_poz", None) else None
        if poz is None:
            return False
        if self._blokada_startu(teraz, poz, getattr(cb, "ostatnie_stwory", [])) is not None:
            return False                     # nie w spokoju: próbujemy w następnym obiegu (bez zużycia terminu)
        self._blanki_auto_t = teraz
        fn = getattr(self.ops, "blanki_i_miejsce", None)
        if not callable(fn):
            return False
        st = fn()
        if st is None:
            return False
        ile, wolne = st
        if not ile:
            return False
        if wolne is None:
            self.log("Blanki: w plecaku są blanki, ale bag na runy nie jest otwarty, nie przenoszę")
            return False
        if wolne <= 0:
            self.log("Blanki: brak wolnego widocznego pola w bagu na runy, nie przenoszę")
            return False
        n = self.ops.przenies_runy()
        self.log(f"Blanki: przeniesiono {n} do bagu na runy (poza wyprawą)")
        self._tele("blanki_auto_bag", przeniesiono=n, w_plecaku=ile, wolne=wolne)
        return bool(n)

    def okazja_w_walce(self, teraz):
        """Wołane z Cavebot.tick w walce: True, gdy wyprawa (po ham/blanki/do depo) właśnie wystartowała mimo potworów."""
        if self.stan != "SPOKOJ" or not int(self._kw("WYPRAWA_DEPO_W_WALCE")):
            return False                 # (13.10: także zwykła wyprawa po ham/blanki; w jaskini zawsze są potwory)
        try:
            return bool(self._okazja_wyprawa(teraz, w_walce=True))
        except bot.Zatrzymano:
            raise
        except Exception as e:
            self._blad("wyprawa_w_walce", opis=repr(e))
            return False

    # --- ręczne "Wróć do miasta" (19.10): plik WROC w katalogu stanu (wroc.sh, guzik paska) ---

    def _plik_wroc(self):
        return Path(self.plik_stop or bot.STOP).with_name("WROC")

    def _wroc_zdejmij(self):
        self._wroc_od = self._wroc_powod = None
        try:
            self._plik_wroc().unlink()
        except OSError:
            pass

    def _wroc_porazka(self, powod):
        """Zlecenie nie wyjdzie (brak planu, blokada trwa za długo): komunikat i plik WROC znika, bez cichych ponowień."""
        self.log(f"Wróć do miasta: nie mogę ruszyć ({powod}), zlecenie anulowane")
        self._powiadom("Wróć do miasta", f"Wróć do miasta: nie mogę ruszyć ({powod}).", "normal", "wroc_odmowa")
        self._tele("wroc_odmowa", powod=powod)
        self._wroc_zdejmij()

    def _wroc_blok(self, teraz, poz):
        """Dlaczego ręczna wyprawa jeszcze nie może ruszyć (None = może): te same bezpieczniki co automatyczna."""
        cb = self.cb
        if self.zablokowany:
            return "wyprawa zablokowana po STOP, alarmie lub dojściu do depo"
        if teraz < self.blokada_do:
            return "blokada po nieudanym wypadzie"
        if poz is None:
            return "nieznana pozycja postaci"
        blok = self._blokada_startu(teraz, poz, getattr(cb, "ostatnie_stwory", []), reczny=True)
        if blok is not None:
            return f"postać nie jest w spokoju ({blok})"
        proc = cb.gracz().get("proc", 100.0)
        if proc < float(self._kw("WYPRAWA_MIN_HP")) or proc <= getattr(cb, "prog_aktualny", 40) + 10:
            return f"za niskie HP ({round(proc)}%)"
        return None

    def _okazja_wroc(self, teraz):
        """Jest plik WROC: wyprawa do depo na jedną wyprawę (semantyka WYPRAWA_TYLKO_DEPO, bez zakupów i powrotu na spot),
        bez POTWIERDZ, cooldownu i bez WYPRAWA_AKTYWNA. Rusza w najbliższej spokojnej chwili; plik znika PO ruszeniu.
        -> True, gdy wyprawa właśnie wystartowała."""
        cb = self.cb
        poz = cb.ruch_poz if getattr(cb, "ruch_poz", None) else None
        powod = self._wroc_blok(teraz, poz)
        if powod is None:
            dane = {"powody": ["reczny"], "zapas": None, "blanki": None, "zloto": None, "cap": None,
                    "hp": round(cb.gracz().get("proc", 100.0)), "pochodnie": None, "depo": True, "reczny": True}
            stare = (self.nast_wyprawa, self.potw_w, self.glod_potw_do)
            try:
                if self._start_wyprawa("depo:reczny", dane, teraz):
                    if getattr(cb, "dojscie_aktywne", False):
                        # 24.10: WROC w trakcie dojścia na spot; po wyprawie CavebotDojscie kończy dojście (nie wraca do niego)
                        cb.dojscie_wroc = True
                        self.log("Wróć do miasta: przerywam dojście na spot, idę do depo od bieżącej pozycji")
                    self._wroc_zdejmij()              # dopiero po ruszeniu: nieudany start nie gubi zlecenia po cichu
                    return True
            except bot.Zatrzymano:
                raise
            except Exception as e:                    # wyjątek nie zostawia zlecenia do ponawiania w każdym obiegu
                self.nast_wyprawa, self.potw_w, self.glod_potw_do = stare
                self._wroc_porazka(repr(e))
                return False
            # nieudane ręczne wywołanie nie odkłada automatycznych wypraw ani nie kasuje potwierdzonego głodu
            self.nast_wyprawa, self.potw_w, self.glod_potw_do = stare
            self._wroc_porazka(f"brak planu albo trasy do depo dla pozycji {tuple(poz)}, szczegóły w logu")
            return False
        self._wroc_czeka(teraz, powod)
        return False

    def _wroc_czeka(self, teraz, powod):
        """Zlecenie czeka z powodu `powod` (także w walce, bez startu): liczy limit WROC_BLOKADA_MAX_S, po nim rezygnuje."""
        if self._wroc_od is None:
            self._wroc_od = teraz
            self.log("Wróć do miasta: zlecenie przyjęte (plik WROC), ruszam w najbliższej spokojnej chwili")
        if powod != self._wroc_powod:
            self._wroc_powod = powod
            self.log(f"Wróć do miasta: czekam ({powod})")
        if teraz - self._wroc_od > float(self._k("WROC_BLOKADA_MAX_S", WROC_BLOKADA_MAX_S)):
            self._wroc_porazka(powod)

    def _okazja_wyprawa(self, teraz, w_walce=False):
        cb = self.cb
        if self._plik_wroc().exists():
            # ręczne wywołanie celowo ma pierwszeństwo przed automatycznymi wyzwalaczami (do WROC_BLOKADA_MAX_S, potem
            # zlecenie znika z komunikatem); omija pokrętła, nie bezpieczniki. W walce nie ruszamy, ale limit płynie.
            if w_walce:
                self._wroc_czeka(teraz, "postać w walce")
                return False
            return self._okazja_wroc(teraz)
        if self._wroc_od is not None:
            self._wroc_od = self._wroc_powod = None        # plik zniknął (wroc.sh --anuluj) albo zlecenie obsłużone
        if not self._wyprawa_wlaczona():
            self.potw_w = 0
            return False
        if self.zablokowany or teraz < self.blokada_do or teraz < self.nast_wyprawa:
            return False
        if self._stan_czytaj().get("nast_wall", 0) > self.czas():
            return False
        poz = cb.ruch_poz if getattr(cb, "ruch_poz", None) else None
        if poz is None:
            return False
        if teraz - self.sprawdzono_w < self._k("WYPAD_SPRAWDZ_S", wypad.SPRAWDZ_S):
            return False
        lista = getattr(cb, "ostatnie_stwory", [])
        blok = self._blokada_startu(teraz, poz, lista, w_walce)
        if blok is not None:
            self.potw_w = 0
            return False
        self.sprawdzono_w = teraz
        g = cb.gracz()
        proc = g.get("proc", 100.0)
        if proc < float(self._kw("WYPRAWA_MIN_HP")) or proc <= getattr(cb, "prog_aktualny", 40) + 10:
            self.potw_w = 0
            return False
        plecak = self.ops.plecak()
        if plecak is None:
            if "w_plecak" not in self.ostrzezenia:
                self.ostrzezenia.add("w_plecak")
                self.log("Wyprawa: nie widzę otwartego plecaka w pamięci, nie sprawdzę zapasu")
            self.potw_w = 0
            if teraz - self.zapas_wiarygodny_t > float(self._kw("GLOD_ZAPAS_WAZNY_S")):
                self.glod_potw_do = float("-inf")   # zapas nieczytelny za długo: dawny "głód" nie jest już ważny
            return False
        self.ostrzezenia.discard("w_plecak")
        zapas = self._jedzenie_ile(plecak)
        if zapas is not None:
            self.zapas_wiarygodny_t = teraz
        prog = int(self._kw("WYPRAWA_ZAPAS_PROG")) or int(self._kw("JEDZENIE_ZAPAS_MIN"))
        glod = bool(getattr(cb, "jedzenie_znane_brak", lambda t: False)(teraz))
        czar = getattr(cb, "jedzenie_czar_zastepuje_wypad", None)
        czar_ok = bool(czar is not None and czar(g, teraz))
        powody = []
        # WYPRAWA_CZEKAJ_NA_GLOD=1: "zapas"/"glod" liczą się dopiero po potwierdzonym głodzie (nieudana próba jedzenia
        # w trybie głodu = cb.jedzenie_nie_do w przyszłości; pamiętamy to GLOD_WAZNY_S), samo zapas 0 w plecaku nie wystarcza
        glod_ok = True
        if not int(self._kw("WYPRAWA_JEDZENIE")):
            glod_ok = False     # 15.10: WYPRAWA_JEDZENIE=0 - jedzenie nie jest powodem wyprawy (tylko blanki)
        elif int(self._kw("WYPRAWA_CZEKAJ_NA_GLOD")) or self._tryb_depo():    # do depo zawsze po potwierdzonym głodzie
            watpliwy = getattr(cb, "jedzenie_odczyt_watpliwy", None)
            if teraz < getattr(cb, "jedzenie_nie_do", float("-inf")) and zapas is not None \
                    and not (callable(watpliwy) and watpliwy(teraz)):
                self.glod_potw_do = teraz + GLOD_WAZNY_S
            glod_ok = teraz < self.glod_potw_do
        if glod_ok and zapas is not None and zapas < prog and not czar_ok:
            powody.append("zapas")
        if glod_ok and (zapas == 0 or glod) and not czar_ok and "zapas" not in powody:
            powody.append("glod")
        blanki = self._ile(plecak, "blank")
        cel_blank = int(self._kw("WYPRAWA_BLANKI"))
        if blanki is not None and blanki > 0:
            # 14.10: pamięć P7c ("ostatnie depo po blanki nic nie dało") ważna tylko, dopóki blanków nie przybyło;
            # inaczej po zakupie i zużyciu blanków bot czekał na człowieka zamiast iść do depo
            st_p = self._stan_czytaj()
            if "blanki" in (st_p.get("depo_powody") or ()) and blanki > int(st_p.get("depo_blanki") or 0):
                self._stan_zapisz(depo_powody=[p for p in st_p.get("depo_powody") or () if p != "blanki"])
                self.ostrzezenia.discard("blanki_pamiec")
                self.log(f"Wyprawa: blanków przybyło ({blanki}), kasuję pamięć ostatniego depo po blanki")
        if cel_blank > 0 and blanki is not None and blanki < int(self._kw("WYPRAWA_BLANKI_PROG")):
            if self._tryb_depo() and not int(self._kw("WYPRAWA_DEPO_BLANKI")):
                # P7b: do depo nie kupujemy blanków, sam brak nie jest powodem marszu (jednorazowa notatka)
                if "blanki_depo" not in self.ostrzezenia:
                    self.ostrzezenia.add("blanki_depo")
                    self.log("Wyprawa: brak blanków, UH wyłączone do uzupełnienia (tryb depo, bez wyprawy po blanki)")
                    self._powiadom("Brak blanków", "Brak blanków w plecaku, UH wyłączone do uzupełnienia "
                                   "(wyprawa po same blanki nie startuje w trybie depo).", "normal", "wyprawa_blanki")
            else:
                st = self._stan_czytaj()
                if self._tryb_depo() and "blanki" in (st.get("depo_powody") or ()) \
                        and st.get("depo_blanki") == blanki:
                    # P7c: ostatnie depo było z tego powodu i plecak się nie zmienił, czekamy na człowieka
                    if "blanki_pamiec" not in self.ostrzezenia:
                        self.ostrzezenia.add("blanki_pamiec")
                        self.log("Wyprawa: brak blanków jak przy ostatnim depo, czekam na uzupełnienie")
                else:
                    self.ostrzezenia.discard("blanki_pamiec")
                    powody.append("blanki")
        if self._powod_cap(powody):
            powody.append("cap")
        self.potw_w = self.potw_w + 1 if powody else 0
        if powody != ["cap"]:
            self._cap_walka_reset()                          # inny powód albo cap w normie: czekanie w walce od nowa
        if self.potw_w < POTWIERDZ:
            return False
        if powody == ["cap"] and self._tryb_depo() and w_walce and int(self._kw("CAP_JEDZ_I_WYRZUC") or 0):
            ma_w_walce = self._jedzenie_ile(plecak)
            if ma_w_walce is None or ma_w_walce > 0:
                # 25.10 (zgon Odchyda, potem Wydra 15:42-16:00): w jaskini trolle są bez przerwy, więc spokój nie nadchodzi, a wyprawa
                # do depo przez trolle mimo jedzenia w plecaku jest tym, czego Karol nie chce ("wróciła się do depo zamiast wyrzucić
                # mięso"). Jedz+wyrzuć idzie więc OD RAZU w walce (niżej, `_cap_jedz_i_wyrzuc(..., w_walce=True)`); wyprawa zostaje
                # ostatecznością (jedzenia brak albo wyrzucanie zawiodło 2 razy). Tu tylko bramka bezpieczeństwa przed pierwszą próbą:
                # gracz w pobliżu / spadek HP / alarm = czekamy (jak dotąd), z limitem CAP_WALKA_CZEKAJ_S (domyślnie 0 = bez limitu).
                blok_w = self._cap_spokoj(poz, proc, w_walce=True)
                if blok_w is not None:
                    limit = float(self._kw("CAP_WALKA_CZEKAJ_S") or 0)
                    if self._cap_walka_od is not None and teraz - (self._cap_walka_ost or teraz) > CAP_WALKA_LUKA_S:
                        self._cap_walka_reset()              # ocena przerwana na długo: to nowy epizod, nie ciągłe czekanie
                    if self._cap_walka_od is None:
                        self._cap_walka_od = teraz
                        cap_w = self._cap()
                        self.ostrzezenia.add("cap_walka")
                        self.log(f"Wyprawa: cap {'?' if cap_w is None else format(cap_w, '.1f')} oz < "
                                 f"{float(self._kw('WYPRAWA_CAP_MIN') or 0):.0f} w walce, jedzenie w plecaku, ale jedzenie/wyrzucanie zablokowane "
                                 f"({blok_w}): czekam " + (f"do {limit:.0f} s, potem wyprawa" if limit > 0 else "bez limitu (CAP_WALKA_CZEKAJ_S=0)"))
                    self._cap_walka_ost = teraz
                    if limit <= 0 or teraz - self._cap_walka_od < limit:
                        self.potw_w = 0
                        return False
                    if "cap_walka_limit" not in self.ostrzezenia:
                        self.ostrzezenia.add("cap_walka_limit")
                        cap_l = self._cap()
                        self.log(f"Wyprawa: cap {'?' if cap_l is None else format(cap_l, '.1f')} oz nadal za mały po {teraz - self._cap_walka_od:.0f} s "
                                 f"(limit {limit:.0f} s, blokada: {blok_w}): ruszam do depo mimo jedzenia w plecaku")
                else:
                    self._cap_walka_reset()
                    try:
                        if self._cap_jedz_i_wyrzuc(teraz, plecak, poz, proc, w_walce=True):
                            self.potw_w = 0
                            return False                     # w walce nic nie wystartowało (cel walki zostaje; True kasuje cb.cel)
                    except bot.Zatrzymano:
                        raise
                    except Exception as ex:
                        self._blad("cap_jedz", opis=repr(ex))
        if powody == ["cap"] and self._tryb_depo() and not w_walce:
            try:
                if self._cap_jedz_i_wyrzuc(teraz, plecak, poz, proc):
                    self.potw_w = 0
                    self._cap_walka_reset()
                    return True
            except bot.Zatrzymano:
                raise
            except Exception as ex:
                self._blad("cap_jedz", opis=repr(ex))
        # warunki sensu: złoto i miejsce w capie (bez nich wyprawa byłaby marszem na darmo); do depo nic nie kupujemy
        zloto = self._zloto(plecak)
        if self._tryb_depo():
            cap = self._cap()
            dane = {"powody": powody, "zapas": zapas, "blanki": blanki, "zloto": zloto, "cap": cap, "hp": round(proc),
                    "pochodnie": None, "depo": True}
            ruszyla = self._start_wyprawa("depo:" + "+".join(powody), dane, teraz)
            if ruszyla:
                self._cap_walka_reset()
            return ruszyla
        if zloto is not None and zloto < int(self._kw("WYPRAWA_ZLOTO_MIN")):
            self._odloz(teraz, f"za mało złota ({zloto})", 1800.0)
            return False
        cap = self._cap()
        waga_min = self._waga("ham") or 1.0
        if cap is not None and cap < waga_min + float(self._kw("WYPRAWA_CAP_REZERWA")) and "blanki" not in powody:
            self._odloz(teraz, f"za mało capa ({cap:.0f} oz) na jedzenie", 900.0)
            return False
        dane = {"powody": powody, "zapas": zapas, "blanki": blanki, "zloto": zloto, "cap": cap, "hp": round(proc),
                "pochodnie": self._ile(plecak, "torch")}
        return self._start_wyprawa("+".join(powody), dane, teraz)

    def _cap_walka_reset(self):
        """25.10: koniec czekania w walce na spokój z powodu cap (cap w normie, inny powód, start wyprawy, jedz/wyrzuć w spokoju)."""
        self._cap_walka_od = self._cap_walka_ost = None
        self.ostrzezenia.discard("cap_walka")
        self.ostrzezenia.discard("cap_walka_limit")

    def _powod_cap(self, powody):
        """23.10 WYPRAWA_CAP_MIN (oz, 0 = wyłączone): wolny cap poniżej progu w TRYBIE DEPO = powód "cap" (invincible miał cap 0.0:
        loot "za_ciezki", a bot nie wracał). Refill po wyprawie (bank gold->platinum, depo) zwalnia wagę złota. W trybie zwykłym
        powód nie istnieje: wyprawa po zakupy złota nie odkłada, a zakupy tylko dokładają wagi (osobna kontrola "za mało capa").
        Pamięć jak P7c dla blanków: ostatnie depo było z powodu cap, a cap od tamtej pory nie wzrósł (> CAP_POPRAWA_OZ) = ciężki
        sprzęt, więc ŻADNEJ kolejnej wyprawy w kółko: jedno ostrzeżenie w logu i jedno zwykłe powiadomienie, dalej gra jak dotąd.
        Cap wzrósł albo wrócił ponad próg = pamięć kasowana. -> True, gdy "cap" ma wejść do powodów."""
        cap_min = float(self._kw("WYPRAWA_CAP_MIN") or 0)
        if cap_min <= 0 or not self._tryb_depo():
            return False
        cap = self._cap()
        if cap is None:
            return False
        st = self._stan_czytaj()
        w_pamieci = "cap" in (st.get("depo_powody") or ())
        if cap >= cap_min:
            if w_pamieci:                                    # cap w normie: stara pamięć nie może zablokować następnego razu
                self._stan_zapisz(depo_powody=[p for p in st.get("depo_powody") or () if p != "cap"])
            self.ostrzezenia.discard("cap_pamiec")
            return False
        if w_pamieci:
            if cap <= float(st.get("depo_cap") or 0.0) + CAP_POPRAWA_OZ:
                if "cap_pamiec" not in self.ostrzezenia:
                    self.ostrzezenia.add("cap_pamiec")
                    self.log(f"Wyprawa: wolny cap {cap:.1f} oz < {cap_min:.0f}, ale po ostatnim depo z tego powodu się nie poprawił "
                             f"(było {float(st.get('depo_cap') or 0.0):.1f}), czekam na wzrost capa (ciężki sprzęt?), bez kolejnej wyprawy")
                    self._powiadom("Za mały cap", f"Wolny cap {cap:.1f} oz (próg {cap_min:.0f}), a depo i bank go nie poprawiły. "
                                   "Wyprawa po cap nie powtarza się; sprawdź ekwipunek.", "normal", "wyprawa_cap")
                return False
            self.ostrzezenia.discard("cap_pamiec")
            self._stan_zapisz(depo_powody=[p for p in st.get("depo_powody") or () if p != "cap"])
            self.log(f"Wyprawa: cap wzrósł ({float(st.get('depo_cap') or 0.0):.1f} -> {cap:.1f} oz), kasuję pamięć ostatniego depo po cap")
        return True

    def _cap_spokoj(self, poz, proc0, w_walce=False):
        """Powód przerwania jedzenia/wyrzucania (None = spokój): świeża lista stworów (w pętli synchronicznej `ostatnie_stwory` jest
        nieaktualne) przez te same bezpieczniki co start wyprawy (walka, potwór w MOBY_ODL, loot, czar, gracz) oraz spadek HP.
        `w_walce` (25.10, Wydra): jedzenie/wyrzucanie w trwającej walce z trollami. Walka i potwory nie blokują (inaczej nigdy nie
        ruszy), blokują: ucieczka/ostrożność, czar w toku, alarm GM (`_blokada_startu(w_walce=True)`), obcy GRACZ w 14 polach,
        HP poniżej WYPRAWA_MIN_HP / progu ucieczki + 10 albo spadek o > 10 pkt od startu."""
        cb = self.cb
        lista = cb.stwory()
        blok = self._blokada_startu(cb.zegar(), poz, lista, w_walce)
        if blok is not None:
            return blok
        if w_walce and getattr(cb, "stanowisko", None) is None:
            ja = getattr(getattr(cb, "postac", None), "nazwa", None)
            for s in lista or []:
                if s.get("gracz") and s.get("nazwa") != ja and s.get("z") == poz[2] and s.get("hp", 100) > 0 \
                        and cheb((s["x"], s["y"]), poz) <= 14:
                    return "gracz"
        proc = cb.gracz().get("proc", 100.0)
        if proc < float(self._kw("WYPRAWA_MIN_HP")) or proc < proc0 - 10:
            return f"hp {proc:.0f}%"
        if w_walce and proc <= getattr(cb, "prog_aktualny", 40) + 10:
            return f"hp {proc:.0f}% blisko progu ucieczki"
        return None

    def _cap_jedz_i_wyrzuc(self, teraz, plecak, poz, proc0, w_walce=False):
        """24.10 (Karol: "brakuje capa, bo postać kupiła za dużo hama"): zamiast wyprawy do depo po cap najpierw jedzenie.
        (1) zjada ile się da (Use w kółko do "You are full" albo do braku ubytku; po "full" przez CAP_JEDZ_PELNY_S nie próbuje),
        (2) cap >= WYPRAWA_CAP_MIN = koniec, gra dalej; (3) inaczej wyrzuca PO JEDNEJ SZTUCE jedzenie na ziemię pod postacią i po
        KAŻDEJ czyta cap: ponad progiem = koniec (reszta jedzenia zostaje), inaczej kolejna sztuka aż jedzenie <= CAP_JEDZ_ZOSTAW
        (domyślnie 0). Walka/potwór/gracz/spadek HP przerywa w każdej chwili. Cykl może się powtarzać bez limitu na minutę
        (cap znów 0 = znów zjedz / wyrzuć 1 sztukę); między podejściami tylko CAP_JEDZ_ODSTEP_S.
        -> True = obsłużone albo odłożone, BEZ wyprawy; None = nie dotyczy / jedzenia nie ma, a cap nadal za mały / wyrzucanie
        nie działa (2 porażki z rzędu) = idzie dawna wyprawa po cap. CAP_JEDZ_I_WYRZUC=0 = None od razu (dawne zachowanie).
        `w_walce` (25.10): to samo w trwającej walce (okazja_w_walce); przerwania wg `_cap_spokoj(w_walce=True)`."""
        if not int(self._kw("CAP_JEDZ_I_WYRZUC") or 0):
            return None
        wyrzuc = getattr(self.ops, "wyrzuc_jedzenie", None)
        if wyrzuc is None:
            return None
        cb = self.cb
        cap_min = float(self._kw("WYPRAWA_CAP_MIN") or 0)
        zostaw = max(0, int(self._kw("CAP_JEDZ_ZOSTAW") or 0))
        ma = self._jedzenie_ile(plecak)
        if ma is not None and ma <= 0:
            return None                                       # jedzenia już nie ma, cap nadal za mały: wyprawa do miasta
        if teraz < self._cap_jedz_nast:
            return True
        cap0 = self._cap()
        self.log(f"Wyprawa: cap {'?' if cap0 is None else format(cap0, '.1f')} oz < {cap_min:.0f}, jedzenia {ma if ma is not None else '?'}: najpierw jem i wyrzucam "
                 f"(po jednej sztuce, zostawiam {zostaw}), bez wyprawy do miasta")
        zjedzone, wyrzucone, powod_konca = 0, 0, None
        if cb.zegar() - self._cap_jedz_pelny >= CAP_JEDZ_PELNY_S and ma != 0:
            for _ in range(int(self._kw("WYPRAWA_JEDZ_MAKS"))):
                if self._cap_spokoj(poz, proc0, w_walce) is not None:
                    powod_konca = "przerwa_jedzenie"
                    break
                zj = self.ops.zjedz()
                pelny = any(ODP_PELNY.search(w["tekst"]) for w in (self.ops.wiadomosci() or ()))
                zjedzone += len(zj)
                if pelny or not zj:
                    self._cap_jedz_pelny = cb.zegar()
                    break
                cb.pauza(0.1, 0.3)
            if ma is not None:
                ma = max(0, ma - zjedzone)
        cap = self._cap()
        wynik = None
        if powod_konca is None and cap is not None and cap >= cap_min:
            wynik = True
        while wynik is None and powod_konca is None:
            if ma is not None and ma <= zostaw:
                break
            if wyrzucone >= CAP_JEDZ_MAKS_SZTUK:
                powod_konca = "limit"
                break
            blok = self._cap_spokoj(poz, proc0, w_walce)
            if blok is not None:
                powod_konca = f"przerwa ({blok})"
                break
            ok, zostalo, blad = wyrzuc()
            if not ok:
                if zostalo == 0:                              # jedzenia nie ma
                    ma = 0
                    break
                self._cap_jedz_bledy += 1
                self.log(f"Wyprawa: wyrzucenie jedzenia nie wyszło ({blad}), próba {self._cap_jedz_bledy}")
                self._tele("wyprawa_krok", rodzaj="cap_jedz_blad", powod=blad)
                self._cap_jedz_nast = cb.zegar() + 60.0
                return None if self._cap_jedz_bledy >= 2 else True
            self._cap_jedz_bledy = 0
            wyrzucone += 1
            ma = zostalo
            cb.pauza(0.3, 0.6)
            cap = self._cap()
            if cap is None:
                powod_konca = "brak odczytu capa"
            elif cap >= cap_min:
                wynik = True
        self._cap_jedz_nast = cb.zegar() + float(self._kw("CAP_JEDZ_ODSTEP_S") or 0)
        self._tele("wyprawa_krok", rodzaj="cap_jedz", zjedzone=zjedzone, wyrzucone=wyrzucone, cap=cap, zostalo=ma, powod=powod_konca)
        if wynik:
            self.log(f"Wyprawa: cap {'?' if cap is None else format(cap, '.1f')} oz po jedzeniu: zjedzone {zjedzone}, wyrzucone {wyrzucone} szt. (zostało {ma if ma is not None else '?'}), "
                     "gram dalej")
            return True
        if powod_konca is not None:
            self.log(f"Wyprawa: jedzenie/wyrzucanie przerwane ({powod_konca}), zjedzone {zjedzone}, wyrzucone {wyrzucone}; cap {cap}, bez wyprawy")
            return True
        self.log(f"Wyprawa: jedzenia nie ma (zjedzone {zjedzone}, wyrzucone {wyrzucone}), a cap {'?' if cap is None else format(cap, '.1f')} oz nadal < {cap_min:.0f}: wyprawa do miasta")
        return None

    def _depo_z_capa(self):
        """Trwająca wyprawa do depo wystartowała wyłącznie z powodu cap (tekst powiadomienia o dotarciu)."""
        p = set(self._stan_czytaj().get("depo_start_powody") or ())
        return "cap" in p and not ({"zapas", "glod"} & p)

    def _odloz(self, teraz, powod, s):
        self.potw_w = 0
        self.nast_wyprawa = teraz + s
        self.log(f"Wyprawa: nie ruszam, {powod}; kolejna próba za {s / 60:.0f} min")
        self._tele("wyprawa_odlozona", powod=powod, na_s=s)

    # --- budowa trasy ---

    def _trasownik_get(self):
        if self._trasownik is None:
            mapa = getattr(self.cb, "mapa", None)
            if mapa is None:
                raise RuntimeError("brak mapy (cb.mapa), nie zbuduję trasy po mapie")
            self._trasownik = Trasownik(mapa)
        return self._trasownik

    def _odc(self, od, do, nagranie=None):
        """Punkty od `od` do `do`: nagranie (lista z JSON) albo A*; None = brak drogi."""
        od = tuple(od)
        if nagranie:
            pts = [q for q in (_punkt(p) for p in nagranie) if q]
            if pts:
                if pts[0][2] == od[2] and cheb(od, pts[0]) > 3:      # 13.10: start daleko od nagrania (np. z depo)
                    seg = self._trasownik_get().odcinek(od, pts[0])
                    if seg:
                        return list(seg) + pts[1:]
                return ([od] if pts[0] != od else []) + pts
        return self._trasownik_get().odcinek(od, do)

    def _stoisko(self, nazwa_klucza, cfg, npc, od):
        """(pole stania, punkty drogi od `od`) dla przystanku albo (None, powód)."""
        stoi = _punkt(cfg.get("stoi")) if cfg.get("stoi") else None
        if stoi is not None:
            pts = self._odc(od, stoi, cfg.get("dojscie"))
            return (stoi, pts) if pts else (None, f"{nazwa_klucza}: brak drogi do {stoi}")
        npc_poz = _punkt(cfg.get("npc_poz")) if cfg.get("npc_poz") else self.npc_widziane.get(npc)
        if npc_poz is None:
            return None, f"{nazwa_klucza}: nie znam pozycji {npc} (wpisz stoi/npc_poz w wyprawa_sklepy.json albo podejdź do NPC)"
        wynik = self._trasownik_get().stoisko(od, npc_poz)
        if not wynik or not wynik[1]:
            return None, f"{nazwa_klucza}: brak drogi do pola obok {npc} {npc_poz}"
        return wynik

    def _zbuduj(self, baza_nazwa, potrzeby):
        """-> (wyprawa dict, None) albo (None, powód). Nic nie rusza w grze."""
        baza = punkty_bazy(self.katalog, nazwy=BAZY_PK if (potrzeby.get("pk") or potrzeby.get("depo")) else BAZY)
        if baza_nazwa not in baza:
            return None, f"brak planu bazowego {baza_nazwa}"
        do, z, npc_gorn = baza[baza_nazwa]
        if potrzeby.get("depo"):
            return self._zbuduj_depo(baza_nazwa, do, potrzeby, z=z)
        cfg = wczytaj_sklepy(self.plik_sklepow)
        stops = []
        if potrzeby.get("depo_zloz"):
            stops.append({"id": "depo_zloz", "npc": "", "stoi": POLE_ZLOZ_DEPO, "zakupy": [], "depo_zloz": True})
        cel_torch = max(int(self._kw("WYPAD_ILE_TORCHY")), int(dict(wypad.Wypad.zakupy(self)).get("torch", 0)))
        if potrzeby.get("gorn"):
            stops.append({"id": "gorn", "npc": npc_gorn, "stoi": do[-1], "dojscie": None,
                          "zakupy": [("torch", cel_torch)]})
        if potrzeby.get("frodo", True):
            c = cfg.get("frodo", {})
            food = str(c.get("jedzenie") or "ham")
            cel = int(self._kw("WYPRAWA_JEDZENIE_CEL"))
            dok = int(self._kw("WYPRAWA_JEDZENIE_DOKUP"))
            lista = [(food, cel)]
            if int(self._kw("WYPRAWA_JEDZ_NA_MIEJSCU")):
                lista.append(("@jedz", None))
            if dok > 0 or int(self._kw("WYPRAWA_JEDZ_NA_MIEJSCU")):
                lista.append((food, cel + dok))
            stops.append({"id": "frodo", "npc": c.get("npc") or "Frodo", "cfg": c, "jedzenie": food,
                          "zakupy": lista, "slowa": c.get("slowa") or {}})
        if potrzeby.get("xodet"):
            c = cfg.get("xodet", {})
            stops.append({"id": "xodet", "npc": c.get("npc") or "Xodet", "cfg": c, "opcjonalny": True,
                          "zakupy": [("blank", int(self._kw("WYPRAWA_BLANKI")))],
                          "slowa": {**SLOWA_DOMYSLNE, **(c.get("slowa") or {})}})
        biez = do[-1]
        legs, kept = [], []    # legs[i] = punkty odcinka "do" przystanku kept[i]
        for st in stops:
            if st["id"] == "gorn":
                stoi, pts = do[-1], list(do)
            elif st.get("depo_zloz"):
                stoi = tuple(st["stoi"])
                pts = self._do_depo_odwrocona(do, stoi) if not legs else None
                if pts is None:
                    seg = self._odc(biez, stoi)
                    if not seg:
                        return None, f"depo: brak drogi od {biez} do {stoi}"
                    pts = (list(do) if not legs else []) + [q for q in seg if tuple(q) != tuple(biez)]
                if tuple(pts[-1]) != stoi:
                    pts.append(stoi)
            else:
                stoi, pts = self._stoisko(st["id"], st["cfg"], st["npc"], biez)
                if stoi is None:
                    if st.get("opcjonalny"):
                        self.log(f"Wyprawa: pomijam przystanek {st['id']}: {pts}")
                        continue
                    return None, pts
                if not legs:
                    pts = list(do) + [q for q in pts[1:]]     # pierwszy odcinek: cała trasa do Gorna + dojście
            st["stoi"] = stoi
            legs.append(pts)
            kept.append(st)
            biez = stoi
        stops = kept
        if not stops:
            return None, "brak przystanków"
        ost = stops[-1]
        if tuple(ost["stoi"]) == tuple(z[0]):
            powrot = list(z)
        else:
            seg = self._odc(ost["stoi"], z[0], (ost.get("cfg") or {}).get("powrot"))
            if not seg:
                return None, f"brak drogi powrotnej z {ost['id']} do {tuple(z[0])}"
            if tuple(seg[-1]) != tuple(z[0]):
                seg = list(seg) + [tuple(z[0])]
            powrot = list(seg) + list(z[1:])
        mapa = getattr(self.cb, "mapa", None)
        drzwi = drzwi_przystankow({st["id"]: st.get("cfg") or {} for st in stops}, mapa)
        legs_etapy = [zbuduj_etapy([_punkt(q) for q in l], mapa, drzwi) for l in legs]
        etapy_z = zbuduj_etapy([_punkt(q) for q in powrot], mapa, drzwi)
        for nazwa, et in [(f"leg{i}", e) for i, e in enumerate(legs_etapy)] + [("powrot", etapy_z)]:
            for b in sprawdz_plan(et, mapa, drzwi, rampy_ok=True):
                self.log(f"Wyprawa: plan {nazwa}: {b}")
        return {"stops": stops, "legs": legs_etapy, "powrot": etapy_z, "k": 0, "baza": baza_nazwa,
                "wyniki": {}, "kroki": 0, "sukces": False, "potrzeby": dict(potrzeby)}, None

    @staticmethod
    def _oznacz_klucze(baza_nazwa, etapy):
        """24.10: etapom DRZWI planu z PLANY_PK["klucze"] dopisuje "klucz": <id> (drzwi zamkniete na klucz). Pozostale etapy i plany bez zmian."""
        klucze = {tuple(d): int(k) for p in PLANY_PK if p["nazwa"] == baza_nazwa for d, k in (p.get("klucze") or ())}
        if klucze:
            for e in etapy:
                if e.get("typ") == "DRZWI" and tuple(e["drzwi"]) in klucze:
                    e["klucz"] = klucze[tuple(e["drzwi"])]
        return etapy

    @staticmethod
    def _plan_z_drzwiami(baza_nazwa):
        """24.10: plan z PLANY_PK z kluczem "drzwi": True (jego "do" przechodzi przez drzwi, ktore mapa zna jako sciane)."""
        return any(p["nazwa"] == baza_nazwa and p.get("drzwi") for p in PLANY_PK)

    @staticmethod
    def _plan_tylko_pk(baza_nazwa):
        """Plan z PLANY_PK (np. edron): cel depo = koniec nagranej trasy "do", bez Gorna/Frodo i bez depo Thais."""
        return baza_nazwa in {p["nazwa"] for p in PLANY_PK}

    def _zbuduj_pk_powrot(self, baza_nazwa, z, potrzeby):
        """Powrót z depo na łowisko po karencji PK: nagrana trasa depo -> łowisko (edron: PLANY_PK["z"],
        troll: depo_troll_cave bez pętli). Jeden przystanek 'depo' (w znaczeniu: ostatni punkt trasy), bez zakupów."""
        mapa = getattr(self.cb, "mapa", None)
        if self._plan_tylko_pk(baza_nazwa):
            pts = [_punkt(q) for q in z]
            etapy = zbuduj_etapy(pts, mapa) if pts and None not in pts else []
            cel = tuple(pts[-1]) if etapy else None
        else:
            etapy = self._powrot_z_depo(self._pole_depo(), mapa)
            cel = None
            if etapy:
                e = next((e for e in reversed(etapy) if e.get("punkty")), None)
                cel = tuple(e["punkty"][-1]) if e else None
        if not etapy or cel is None:
            return None, f"brak trasy powrotnej z depo ({baza_nazwa})"
        for b in sprawdz_plan(etapy, mapa, rampy_ok=True):
            self.log(f"Wyprawa: plan powrotu PK: {b}")
        st = {"id": "depo", "npc": "", "stoi": cel, "zakupy": [], "depo": True}
        return {"stops": [st], "legs": [etapy], "powrot": zbuduj_etapy([cel], mapa), "k": 0, "baza": baza_nazwa,
                "wyniki": {}, "kroki": 0, "sukces": False, "potrzeby": dict(potrzeby)}, None

    def _zbuduj_depo(self, baza_nazwa, do, potrzeby, z=None):
        """Wyprawa do depo: nagrana trasa do Gorna + A* po mapie do pola depo. Jeden przystanek bez zakupów."""
        if potrzeby.get("pk") == "powrot":
            return self._zbuduj_pk_powrot(baza_nazwa, z or [], potrzeby)
        cel = tuple(do[-1]) if self._plan_tylko_pk(baza_nazwa) else self._pole_depo()
        biez = tuple(do[-1])
        pts = None
        if self._z_poz is not None and self._plan_tylko_pk(baza_nazwa):
            pts = self._droga_z_pozycji(self._z_poz, do, baza_nazwa)       # 16.10: najkrótsza droga z bieżącego miejsca, nie od początku "do"
        elif self._z_poz is not None and baza_nazwa in WYJSCIA_BAZ:
            pts, blad = self._droga_kanaly(self._z_poz, cel)               # 21.10 K2: kanały Thais -> najbliższa pewna drabina
            if pts is None and blad:
                return None, blad
        if pts is None:
            pts = self._do_depo_odwrocona(do, cel)       # z jaskini prosto do depo (nie przez Gorna)
        if pts is None:
            if biez == cel:
                seg = [biez]
            else:
                seg = self._odc(biez, cel)
                if not seg:
                    return None, f"depo: brak drogi po mapie od {biez} do {cel}"
            pts = list(do) + [q for q in seg if tuple(q) != biez]
        if tuple(pts[-1]) != cel:
            pts.append(cel)
        obszar = None
        if self._plan_tylko_pk(baza_nazwa) and int(self._kw("DEPO_EDRON_OBSZAR")):
            pts, obszar = self._dojscie_do_obszaru(pts, cel)          # 24.10: pole dojścia losowane z obszaru hali, nie jedno stałe
            if obszar:
                cel = tuple(pts[-1])
        mapa = getattr(self.cb, "mapa", None)
        # 24.10 (abdendriel_trolle_z10): plan z kluczem "drzwi" ma w "do" zamkniete drzwi nagrane przez gracza (mapa widzi je jako sciane); etapy DRZWI
        # (Use + krok, wypad.DRZWI_PROB prob) zamiast marszu w sciane. Opt-in: pozostale plany PLANY_PK buduja sie dokladnie jak dotad.
        drzwi = drzwi_z_mapy([_punkt(q) for q in pts], mapa) if self._plan_z_drzwiami(baza_nazwa) and mapa is not None else ()
        etapy = self._oznacz_klucze(baza_nazwa, zbuduj_etapy([_punkt(q) for q in pts], mapa, drzwi))
        powrot = zbuduj_etapy([cel], mapa)           # bez WYPRAWA_DEPO_POWROT nieużywany: po dojściu STOP
        if int(self._kw("WYPRAWA_DEPO_POWROT")) and not potrzeby.get("reczny"):
            if self._plan_tylko_pk(baza_nazwa):          # depo spotu z PLANY_PK (Edron): powrót nagraną trasą depo -> łowisko
                pz = [_punkt(q) for q in (z or [])]
                pw = zbuduj_etapy(pz, mapa) if pz and None not in pz else []
            else:
                pw = self._powrot_z_depo(cel, mapa)
            if pw:
                powrot = pw
            else:
                self.log("Wyprawa: brak trasy powrotnej z depo (depo_troll_cave), po dojściu będzie STOP")
        for b in sprawdz_plan(etapy, mapa, drzwi, rampy_ok=True):
            self.log(f"Wyprawa: plan depo: {b}")
        st = {"id": "depo", "npc": "", "stoi": cel, "zakupy": [], "depo": True}
        if obszar:
            st["obszar"] = obszar                    # pola, z których dowolne = "depo osiągnięte" (patrz _cel_dokroku); po restarcie plan buduje się od nowa (_wznow -> _zbuduj), więc obszar wraca z danych
        return {"stops": [st], "legs": [etapy], "powrot": powrot, "k": 0, "baza": baza_nazwa,
                "wyniki": {}, "kroki": 0, "sukces": False, "potrzeby": dict(potrzeby)}, None

    def _dojscie_do_obszaru(self, pts, cel):
        """24.10 (Karol: „punkt dojścia do depo w Edron na jakiś neutralny na środku albo obręb, żeby za każdym razem w to samo miejsce
        nie przychodził, bo może być zajęte”): trasa `pts` (kończy się na stanowisku depo `cel`) zostaje do pierwszego punktu w sali depo,
        stamtąd A* do losowego wolnego pola obszaru hali (`depo_obszar` w serwis_edron.json). -> (nowe punkty, lista pól obszaru) albo
        (pts, None) = dawne dojście na stanowisko `cel` (pokrętło/dane/droga niedostępne, wszystkie pola zajęte, trasa nie wchodzi do sali)."""
        o = obszar_depo(self.katalog, cel)
        if o is None:
            return pts, None
        pola, sala = o
        try:
            zaj = self._zajete_pola(tuple(self.cb.postac.pozycja()))
        except bot.Zatrzymano:
            raise
        except Exception:
            zaj = set()
        wybrane = wybierz_pole_obszaru(pola, zaj)
        if wybrane is None:
            self.log("Wyprawa: depo: wszystkie pola obszaru zajęte, idę na stanowisko jak dawniej")
            return pts, None
        pts = [tuple(q) for q in pts]
        i = next((k for k, q in enumerate(pts) if w_sali(q, sala)), None)
        if i is None:
            return pts, None
        nowe = pts[:i + 1]
        if nowe[-1] != wybrane:
            seg = self._odc(nowe[-1], wybrane)
            if not seg:
                self.log(f"Wyprawa: depo: brak drogi w sali do pola obszaru {wybrane}, idę na stanowisko jak dawniej")
                return pts, None
            nowe += [tuple(q) for q in seg if tuple(q) != nowe[-1]]
        if nowe[-1] != wybrane:
            nowe.append(wybrane)
        self.log(f"Wyprawa: depo Edron: pole dojścia {wybrane} z obszaru ({len(pola)} pól) zamiast stanowiska {tuple(cel)}")
        return nowe, [list(p) for p in pola]

    def _cel_dokroku(self, poz, st):
        """Pole, na które w `_sklep` (depo) dokładamy krok po dojściu, albo None (nic nie dokładamy). Bez obszaru: stanowisko `stoi`
        (jak dotąd). Z obszarem (24.10): stoimy w obszarze = depo osiągnięte (None); inaczej `stoi`, a gdy zajęte przez gracza/stwora,
        najbliższe wolne pole obszaru; wszystkie zajęte = None (zostajemy tam, gdzie etap nas zostawił, byle w sali)."""
        stoi = tuple(st["stoi"])
        obszar = [tuple(p) for p in st.get("obszar") or ()]
        if not obszar:
            return stoi
        poz = tuple(poz)
        if poz in obszar:
            return None
        zaj = self._zajete_pola(poz)
        wolne = [p for p in obszar if p[2] == poz[2] and (p[0], p[1]) not in zaj]
        if not wolne:
            return None
        if stoi in wolne:
            return stoi
        najb = min(cheb(poz, p) for p in wolne)
        return random.choice([p for p in wolne if cheb(poz, p) == najb])

    _z_poz = None          # pozycja startu wyprawy do depo (plan PLANY_PK): z niej liczymy najkrótszą drogę

    def _zalew_pietra(self, a, cele):
        return self._trasownik_get().zalew(a, cele, limit=DEPO_ZALEW_LIMIT)

    def _petla_lowiska(self, edron=True):
        """Zamknięta trasa łowiska bota (cb.punkty) albo, gdy pusta, nagranie PLIK_PETLA_EDRON (`edron`); [] gdy brak."""
        pts = [_punkt(q) for q in (getattr(self.cb, "punkty", None) or ())] if isinstance(
            getattr(self.cb, "punkty", None), (list, tuple)) else []
        if len(pts) < 3 or None in pts:
            if not edron:
                return []
            try:
                pts = [_punkt(q) for q in json.loads((Path(self.katalog) / PLIK_PETLA_EDRON).read_text())]
            except (OSError, ValueError, TypeError):
                return []
            if None in pts:
                return []
        return pts

    @staticmethod
    def _wyjscia_planu(baza_nazwa):
        return next((p.get("wyjscia", ()) for p in PLANY_PK if p["nazwa"] == baza_nazwa), ())

    _droga_memo = None     # {(baza, poz): wynik droga_do_depo}: wybór bazy (_baza_osiagalna) i budowa planu liczą to samo raz

    def _droga_z_pozycji(self, poz, do, baza_nazwa=None, cicho=False):
        """Punkty najkrótszej drogi z `poz` do depo (koniec `do`) albo None (wtedy stara droga: cała trasa "do").
        `cicho`: tylko sondowanie bazy (bez logu o "starej trasie")."""
        mapa = getattr(self.cb, "mapa", None)
        if mapa is None:
            return None
        klucz = (baza_nazwa, tuple(int(v) for v in poz))
        if self._droga_memo is None:
            self._droga_memo = {}
        try:
            if klucz not in self._droga_memo:
                self._droga_memo[klucz] = droga_do_depo(poz, self._petla_lowiska(), [_punkt(q) for q in do],
                                                        self._zalew_pietra, mapa, wyjscia=self._wyjscia_planu(baza_nazwa),
                                                        zasieg=zasieg_planu(baza_nazwa))
            wyn = self._droga_memo[klucz]
        except bot.Zatrzymano:
            raise
        except Exception as e:
            if not cicho:
                self.log(f"Wyprawa: depo: nie wyznaczyłem drogi z {tuple(poz)} ({e!r}), idę starą trasą")
            return None
        if wyn is None:
            if not cicho:
                self.log(f"Wyprawa: depo: brak drogi z {tuple(poz)}, idę starą trasą")
            return None
        pts, koszt, opis = wyn
        if not cicho:
            self.log(f"Wyprawa: depo: droga z {tuple(poz)}: {len(pts)} punktów, koszt {koszt} ({opis})")
        return pts

    def _baza_osiagalna(self, baza, poz, nazwa):
        """22.10 (Geblish, Rook z8): `nazwa` = plan z PLANY_PK o najbliższym (Chebyshev) punkcie "do" na piętrze `poz`, a to nie
        znaczy "da się stamtąd dojść": rook_bugi_z10 ma na z8 korytarz tuż obok jaskini szczurów, od której oddziela go ściana
        ("brak drogi", kroki w ścianę, ALARM). Bierzemy więc pierwszy plan z PLANY_PK (najbliższy najpierw), dla którego
        droga_do_depo z `poz` istnieje. Gdy `nazwa` ma drogę (Edron i reszta, jak dotąd) albo żaden jej nie ma, zostaje `nazwa`
        (brak drogi = stara trasa jak wcześniej). Nie dotyka planów spoza PLANY_PK ani WYJSCIA_BAZ."""
        if nazwa is None or not self._plan_tylko_pk(nazwa):
            return nazwa
        poz = tuple(int(v) for v in poz)
        if self._droga_z_pozycji(poz, baza[nazwa][0], nazwa, cicho=True) is not None:
            return nazwa

        def odl(n):
            do = baza[n][0]
            return min((cheb(poz, q) for q in do if q[2] == poz[2]), default=cheb(poz, do[-1]) + 1000)

        inne = sorted((p["nazwa"] for p in PLANY_PK if p["nazwa"] in baza and p["nazwa"] != nazwa), key=odl)
        for n in inne:
            if cheb(poz, baza[n][0][-1]) > zasieg_planu(n):
                continue
            if self._droga_z_pozycji(poz, baza[n][0], n, cicho=True) is not None:
                self.log(f"Wyprawa: baza {nazwa} nie ma drogi z {poz} (najbliższy punkt za ścianą), biorę {n}")
                return n
        return nazwa

    @staticmethod
    def _w_kanalach_thais(poz):
        """Pozycja na z8 w okolicy kanałów Thais (trasa thais_szczury_opt), a nie np. w jaskini trolli Thais (x >= 32470)."""
        x0, y0, x1, y1 = KANALY_THAIS_PROSTOKAT
        return int(poz[2]) == 8 and x0 <= int(poz[0]) <= x1 and y0 <= int(poz[1]) <= y1

    def _wyjscia_kanalow(self, poz, mapa):
        """Wyjścia z kanałów Thais w formacie droga_do_depo: (pole drabiny R z8, lądowanie (R.x, R.y+1, z7), None, pola stania).
        R = ostatni punkt z8 pliku zejścia kratką (KANALY_THAIS_DRABINY). Pola stania: sąsiedzi R na z8 bez ściany i bez flagi 2,
        najpierw prostopadli i bez pola pod lądowaniem (stanie na nim to „własne” pole); północ od R bywa ścianą."""
        wynik = []
        for plik in KANALY_THAIS_DRABINY:
            try:
                pts = [_punkt(q) for q in json.loads((Path(self.katalog) / plik).read_text())]
            except (OSError, ValueError, TypeError):
                continue
            z8 = [q for q in pts if q and q[2] == int(poz[2])]
            if not z8:
                continue
            r = z8[-1]
            lad = (r[0], r[1] + 1, r[2] - 1)
            stoiska = []
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (r[0] + dx, r[1] + dy, r[2])
                    if (dx, dy) == (0, 0):
                        continue
                    try:
                        if mapa.przechodnie(*q) is not True or int(mapa.flagi(*q)) & 2:
                            continue
                    except Exception:
                        continue
                    stoiska.append(q)
            stoiska.sort(key=lambda q: (q[:2] == lad[:2], bool(q[0] != r[0] and q[1] != r[1]), cheb(q, poz), q))
            if stoiska:
                wynik.append((r, lad, None, stoiska[:4]))
        return tuple(wynik)

    def _droga_kanaly(self, poz, cel):
        """21.10 K2: droga z kanałów Thais (z8) do depo `cel` (z7) najbliższą znaną drabiną pod kratką; z innego piętra prosty A*
        do depo. -> (punkty, None) albo (None, powód porażki z z8 / None, gdy inna sytuacja: wtedy stara droga). Nie wraca nigdy do
        zgadniętego wyjścia (32360,32242,z8): `do` dla droga_do_depo to samo depo."""
        mapa = getattr(self.cb, "mapa", None)
        poz = tuple(int(v) for v in poz)
        z_kanalow = poz[2] == 8
        if mapa is None:
            return None, ("depo: brak mapy, nie wyznaczę drogi z kanałów Thais (zgadnięte wyjście (32360,32242,z8) pomijam)"
                          if z_kanalow else None)
        petla = self._petla_lowiska(edron=False)
        try:
            if z_kanalow:
                # NAJBLIŻSZA drabina = najmniej marszu po z8 (kanały: szczury, ciemno); dopiero przy remisie krótsza całość
                wyn, klucz = None, None
                for wyj in self._wyjscia_kanalow(poz, mapa):
                    r = droga_do_depo(poz, petla, [tuple(cel)], self._zalew_pietra, mapa, wyjscia=(wyj,))
                    if r is None:
                        continue
                    na_z8 = []
                    for q in r[0]:
                        if q[2] != poz[2]:
                            break
                        na_z8.append(q)
                    k = (koszt_punktow(na_z8), r[1])
                    if klucz is None or k < klucz:
                        wyn, klucz = (r[0], r[1], f"drabina {wyj[0]} -> {wyj[1]}, {len(na_z8)} pól po z8; {r[2]}"), k
            else:
                wyn = droga_do_depo(poz, petla, [tuple(cel)], self._zalew_pietra, mapa)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            wyn = None
            self.log(f"Wyprawa: depo: nie wyznaczyłem drogi z {poz} ({e!r})")
        if wyn is None:
            self.log(f"Wyprawa: depo: brak drogi z {poz}")
            return None, (f"depo: brak drogi z kanałów Thais z {poz} przez znane drabiny pod kratkami (mapa/wyjścia)"
                          if z_kanalow else None)
        pts, koszt, opis = wyn
        self.log(f"Wyprawa: depo: droga z {poz}: {len(pts)} punktów, koszt {koszt} ({opis})")
        return pts, None

    def _baza_dojscie(self, baza, poz):
        """Plan z PLANY_PK, do którego depo da się dojść z `poz` z dowolnego piętra (nie dalej niż DEPO_DOJSCIE_ZASIEG
        w linii prostej od jego depo). Najbliższe depo wygrywa; None, gdy żadne."""
        najl = None
        for p in PLANY_PK:
            if p["nazwa"] not in baza:
                continue
            d = cheb(poz, baza[p["nazwa"]][0][-1])
            if d <= zasieg_planu(p["nazwa"]) and (najl is None or d < najl[0]):
                najl = (d, p["nazwa"])
        return najl[1] if najl else None

    def _do_depo_odwrocona(self, do, cel):
        """Droga do depo: nagrana trasa wyjścia z jaskini (`do`, do pierwszego punktu na piętrze depo = pole po drabinie)
        + trasa PLIK_DEPO (depo -> jaskinia) przejęta od końca bez pętli (to samo, co bot przeszedł w powrocie).
        Omija objazd przez Gorna (12.10: 240 pól zamiast ok. 190). None, gdy brak pliku/niezgodność (wtedy stara droga)."""
        try:
            import trasa_io  # noqa: PLC0415
            plik = [q for q in (_punkt(p) for p in json.loads((Path(self.katalog) / PLIK_DEPO).read_text())) if q]
            plik = trasa_io.uprosc_petle(plik)
            z = cel[2]
            i7 = max((i for i, q in enumerate(plik) if q[2] == z), default=None)
            if i7 is None or tuple(plik[0]) != tuple(cel):
                return None
            rev = list(reversed(plik[:i7 + 1]))          # od dziury w jaskinię do depo
            i0 = next((i for i, q in enumerate(do) if q[2] == z), None)
            if i0 is None:
                return None
            wej = tuple(do[i0])
            if cheb(wej, rev[0]) > 3 or len(rev) < 2:
                return None
            pts = list(do[:i0 + 1]) + [q for q in rev if tuple(q) != wej]
            return pts
        except Exception as e:
            self.log(f"Wyprawa: depo: nie użyję trasy odwróconej ({e!r})")
            return None

    def _powrot_z_depo(self, cel, mapa):
        """Etapy powrotu z pola depo na początek trasy łowiska: nagrana trasa PLIK_DEPO (depo -> jaskinia) bez pętli
        i cofnięć (trasa_io.uprosc_petle). [] gdy pliku brak albo trasa nie zaczyna się przy depo."""
        try:
            import trasa_io  # noqa: PLC0415
            pts = [q for q in (_punkt(p) for p in json.loads((Path(self.katalog) / PLIK_DEPO).read_text())) if q]
        except (OSError, ValueError, TypeError):
            return []
        pts = trasa_io.uprosc_petle(pts) if pts else []
        if len(pts) < 2 or cheb(pts[0], cel) > 3 or pts[-1][2] == pts[0][2]:
            return []
        if tuple(pts[0]) != tuple(cel):
            pts = [tuple(cel)] + pts
        drzwi = wypad.drzwi_z_mapy(pts, mapa)
        return zbuduj_etapy([_punkt(q) for q in pts], mapa, drzwi)

    # --- start / wznowienie ---

    def _start_wyprawa(self, powod, dane, teraz, baza_nazwa=None, pk=None):
        cb = self.cb
        st = getattr(cb, "stanowisko", None)
        if st is not None:                             # 22.10 tryb stoj: serwis (marsz do depo i refill) robi stanowisko.py, nie plan wyprawy
            self.glod_potw_do = float("-inf")
            if st.zlec_serwis(powod, dane, teraz):
                return True
            self._odloz(teraz, "stanowisko: serwis trwa albo odroczony", 120.0)
            return False
        self.glod_potw_do = float("-inf")
        poz = tuple(cb.postac.pozycja())
        depo_spota = bool(dane.get("depo"))      # 16.10: depo każdego spotu ma swój plan (Edron: PLANY_PK), nie tylko ucieczka PK
        baza = punkty_bazy(self.katalog, nazwy=BAZY_PK if (pk or depo_spota) else BAZY)
        z_pk = bool(pk and baza_nazwa in baza)
        nazwa = baza_nazwa if z_pk else wybierz_baze(
            baza, poz, PK_PLAN_ZASIEG if (pk or depo_spota) else wypad.PLAN_ZASIEG)
        if nazwa is None and (pk or depo_spota):       # 16.10: plan depo spotu z dowolnego miejsca (piętra), nie tylko przy trasie
            nazwa = self._baza_dojscie(baza, poz)
        if depo_spota and not z_pk and KANALY_THAIS in baza and self._w_kanalach_thais(poz):
            nazwa = KANALY_THAIS           # 21.10 K2: w kanałach Thais (także przy trasie planu "troll", x ~ 32422) zawsze najbliższa drabina
        self._droga_memo = {}
        if depo_spota and not z_pk:        # 22.10: najbliższy punkt "do" bywa za ścianą (Rook z8 -> rook_bugi_z10): wybór po osiągalności
            nazwa = self._baza_osiagalna(baza, poz, nazwa)
        self._z_poz = poz if (depo_spota and nazwa is not None
                              and (self._plan_tylko_pk(nazwa) or nazwa in WYJSCIA_BAZ)) else None
        if nazwa is None:
            if pk:
                self.log(f"Wyprawa: PK: pozycja {poz} poza planami {BAZY_PK}")
                return False
            self._odloz(teraz, f"pozycja {poz} poza planami {BAZY}", 900.0)
            return False
        if dane.get("depo"):
            potrzeby = {"depo": True}
            if pk:
                potrzeby["pk"] = pk
            if dane.get("reczny"):           # 19.10 "Wróć do miasta": tylko depo, nigdy powrót na spot (także przy WYPRAWA_DEPO_POWROT=1)
                potrzeby["reczny"] = True
        else:
            potrzeby = {"frodo": True, "depo_zloz": bool(int(self._kw("WYPRAWA_DEPO_ZLOZ"))),
                    "gorn": bool(self._kw("WYPRAWA_POCHODNIE") and dane.get("pochodnie") is not None
                                 and dane["pochodnie"] < int(self._kw("WYPAD_ILE_TORCHY"))),
                    "xodet": bool(int(self._kw("WYPRAWA_BLANKI")) > 0 and dane.get("blanki") is not None
                                  and dane["blanki"] < int(self._kw("WYPRAWA_BLANKI")))}
        try:
            w, blad = self._zbuduj(nazwa, potrzeby)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            w, blad = None, f"wyjątek {e!r}"
        if w is None:
            if pk:                           # ucieczka PK: wołający przechodzi na ucieczkę awaryjną, bez karencji wypraw
                self.log(f"Wyprawa: PK: nie startuję: {blad}")
                self._tele("wyprawa_odrzucona", powod=blad)
                return False
            if blad not in self._brak_pozycji_log:
                self._brak_pozycji_log.add(blad)
                self._powiadom("Wyprawa: nie mogę zacząć", blad, "normal", "wyprawa_brak")
            self.log(f"Wyprawa: nie startuję: {blad}")
            self._tele("wyprawa_odrzucona", powod=blad)
            self.potw_w = 0
            self.nast_wyprawa = teraz + 1800.0
            return False
        w["powod"], w["t_wall"] = powod, self.czas()
        self.w = w
        self._plan_wyprawy = (w["legs"][0], w["powrot"])
        self.npc = w["stops"][0]["npc"]
        if not super()._start("wyprawa:" + powod, dane):
            self.w = None
            self._plan_wyprawy = None
            self.potw_w = 0
            if not pk:                       # ucieczka PK nie odkłada zwykłych wypraw (decyzja po stronie cavebota)
                self.nast_wyprawa = teraz + 900.0
            return False
        self._ost_poz_w = poz
        self._stan_trasy()
        if self._z_poz is not None:
            self._stan_zapisz(z_poz=list(self._z_poz))     # wznowienie po restarcie buduje ten sam plan
        if dane.get("depo"):                 # P7c: z jakiego powodu i przy jakim plecaku idziemy do depo
            self._stan_zapisz(depo_start_powody=list(dane.get("powody") or []), depo_start_blanki=dane.get("blanki"),
                              depo_start_cap=dane.get("cap"))
        self.log(f"Wyprawa: start ({powod}), baza {nazwa}, przystanki {[st['id'] for st in w['stops']]}")
        if dane.get("reczny"):
            self._powiadom("Wróć do miasta: ruszam", f"Ręczne wywołanie, idę do depo ({nazwa}).", "normal", "wyprawa_depo_start")
        elif dane.get("depo") and not pk:
            self._powiadom("Wyprawa do depo: ruszam",
                           (f"Za mały wolny cap ({dane.get('cap')} oz), idę do depo ({powod}); bank i depo zwolnią wagę." if "cap" in (dane.get("powody") or ())
                            and not ({"zapas", "glod"} & set(dane.get("powody") or ()))
                            else f"Brak jedzenia i głód ({powod}), idę do depo Thais."),
                           "normal", "wyprawa_depo_start")
        return True

    # --- obrona PK (obrona_pk.py): ucieczka do depo i powrót po karencji ---

    def start_pk(self, rodzaj, teraz, baza=None):
        """Start wyprawy PK z bieżącej pozycji. rodzaj: "ucieczka" (do depo) albo "powrot" (z depo na łowisko).
        Trwająca wyprawa jest cicho porzucana (bez blokady samoczynnych wypraw). -> True, gdy ruszyła."""
        if self.w is not None or self.stan != "SPOKOJ":
            self.w = None
            self._plan_wyprawy = None
            self.stan, self.faza, self.etapy, self.sklep, self.wynik = "SPOKOJ", None, None, None, None
            self.cb.wypad_aktywny = False
        stare = (self.zablokowany, self.blokada_do)
        self.zablokowany = False
        self.blokada_do = float("-inf")
        baza_nazwa = (baza or getattr(self, "pk_baza", None)) if rodzaj == "powrot" else baza
        dane = {"powody": ["pk"], "zapas": None, "blanki": None, "zloto": None, "cap": None,
                "hp": round(self.cb.gracz().get("proc", 100.0)), "pochodnie": None, "depo": True}
        try:
            ok = self._start_wyprawa(f"depo:pk_{rodzaj}", dane, teraz, baza_nazwa=baza_nazwa, pk=rodzaj)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            self.log(f"Wyprawa: PK: wyjątek przy starcie {e!r}")
            self.w = None
            self._plan_wyprawy = None
            self.stan = "SPOKOJ"
            self.zablokowany, self.blokada_do = stare
            return False
        if ok and self.w is not None:
            self.pk_baza = self.w.get("baza") or getattr(self, "pk_baza", None)
        else:
            self.zablokowany, self.blokada_do = stare      # nieudany start PK nie zmienia stanu zwykłych wypraw
        return bool(ok)

    def odrzuc_pk_po_zgonie(self, powod):
        """26.10 (PK_RESET_PO_ZGONIE): po zgonie postaci wyprawa PK (ucieczka do depo / powrót na spot: potrzeby.pk) jest nieaktualna:
        porzucamy trwającą (cicho, jak start_pk) i zamykamy zapis stanu (`wynik: pk_zgon`), żeby restart jej nie wznawiał
        (wznow_start). Zwykłe wyprawy (blanki/cap/refill/serwis/WROC) nietknięte. -> True, gdy coś odrzucono."""
        st = self._stan_czytaj()
        zapis_pk = bool((st.get("potrzeby") or {}).get("pk")) and bool(st.get("aktywna") or st.get("przerwana"))
        trwa_pk = self.w is not None and bool((self.w.get("potrzeby") or {}).get("pk"))
        if trwa_pk:
            self.w = None
            self._plan_wyprawy = None
            self.stan, self.faza, self.etapy, self.sklep, self.wynik = "SPOKOJ", None, None, None, None
            self.cb.wypad_aktywny = False
            try:
                self.cb._wypad_reset_klik()
            except Exception:
                pass
        if trwa_pk or zapis_pk:
            self._stan_koniec(wynik="pk_zgon", opis=f"wyprawa PK odrzucona po zgonie: {str(powod)[:120]}")
            self.log("Wyprawa: wyprawa PK odrzucona po zgonie postaci (nie wznawiam).")
            return True
        return False

    def _zakoncz_pk(self, wynik, opis):
        """Koniec wyprawy PK (dotarcie albo awaria): bez pliku STOP i bez blokady wypraw; decyzję co dalej
        podejmuje Cavebot._pk_wyprawa_koniec (czekanie w depo / powrót / ucieczka awaryjna)."""
        cb = self.cb
        w = self.w
        teraz = cb.zegar()
        poz = tuple(cb.postac.pozycja())
        rodzaj = (w.get("potrzeby") or {}).get("pk") if w else None
        self.log(f"Wyprawa: PK {rodzaj} zakończona ({wynik}) w {poz}: {opis}")
        self._tele("wyprawa_koniec", wynik=wynik, opis=opis, kupione={}, depo=True, pk=rodzaj, poz=list(poz),
                   czas_s=round(teraz - self.t_start))
        self._stan_koniec(wynik=f"pk_{wynik}", opis=opis, kupione={}, wyniki=(w or {}).get("wyniki"))
        self.nast_wyprawa = max(self.nast_wyprawa, teraz + 120.0)
        self.w = None
        self._plan_wyprawy = None
        self.stan = "SPOKOJ"
        self.faza = self.etapy = None
        self.sklep = None
        self.wynik = None
        cb.wypad_aktywny = False
        try:
            cb._wypad_reset_klik()
            cb.ustaw_stan("IDZ", "wyprawa PK zakończona")
        except Exception:
            pass
        fn = getattr(cb, "_pk_wyprawa_koniec", None)
        if callable(fn):
            fn(rodzaj, wynik, opis, poz)
        return True

    def _wybierz_plan(self, poz):
        if self._plan_wyprawy is not None:
            self.plan, self.plan_nazwa = self._plan_wyprawy, "wyprawa"
            return self.plan
        return super()._wybierz_plan(poz)

    def _powod_ustal(self, st):
        """Po restarcie: wyprawa wystartowana tylko z powodu jedzenia (zapas/glod), jeszcze nic nie kupiła,
        a plecak jest widoczny i zapas >= próg => powód nieaktualny (fałszywy głód), nie wznawiamy."""
        try:
            if st.get("faza") not in (None, "do") or st.get("kupione"):
                return False
            powody = {t for t in re.split(r"[:+]", str(st.get("powod") or "")) if t} - {"wyprawa", "depo"}
            if not powody or not powody <= {"zapas", "glod"}:
                return False                      # inny powód (blanki, pochodnie, nieznany): wznawiamy jak dawniej
            plecak = self.ops.plecak()
            if plecak is None:
                return False                      # kontenery niewidoczne: nie umiemy zweryfikować
            zapas = self._jedzenie_ile(plecak)
            if zapas is None:
                return False
            prog = int(self._kw("WYPRAWA_ZAPAS_PROG")) or int(self._kw("JEDZENIE_ZAPAS_MIN"))
            if zapas >= prog or (zapas > 0 and "zapas" not in powody):
                self.log(f"Wyprawa: powód '{st.get('powod')}' nieaktualny po restarcie (zapas {zapas}, próg {prog}), "
                         "nie wznawiam")
                return True
        except bot.Zatrzymano:
            raise
        except Exception as e:
            self.log(f"Wyprawa: walidacja powodu nie powiodła się ({e!r}), wznawiam")
        return False

    def _wznow(self, teraz):
        """Po restarcie bota: kontynuacja wyprawy z pliku stanu (tylko gdy postać jest przy planie)."""
        st = self._stan_czytaj()
        if not st.get("aktywna"):
            return False
        wiek = self.czas() - float(st.get("t_wall", 0))
        if wiek > WZNOW_MAX_S:
            self.log(f"Wyprawa: stary zapis stanu ({wiek:.0f} s), nie wznawiam")
            self._stan_koniec(wynik="przestarzaly")
            return False
        if int(self._kw("WYPRAWA_WZNOW_WALIDUJ")) and self._powod_ustal(st):
            self._stan_koniec(wynik="powod_ustal")
            return False
        poz = tuple(self.cb.postac.pozycja())
        potrzeby = st.get("potrzeby") or {"frodo": True}
        self._z_poz = _punkt(st["z_poz"]) if potrzeby.get("depo") and st.get("z_poz") else None
        w, blad = self._zbuduj(st.get("baza", "troll"), potrzeby)
        if w is None:
            self.log(f"Wyprawa: nie wznowię ({blad})")
            self._stan_koniec(wynik="nie_wznowiona", powod=blad)
            self._alarm_utknieciu(f"nie wznowię wyprawy po restarcie: {blad}", stop=False)
            return False
        k0 = min(int(st.get("k", 0)), len(w["stops"]) - 1)
        # kandydaci: odcinek "do" k.., potem powrót; wybór po odległości od `poz`
        kand = []
        for j in range(k0, len(w["legs"])):
            kand.append(("do", j, w["legs"][j]))
        if not potrzeby.get("depo") or (int(self._kw("WYPRAWA_DEPO_POWROT")) and not potrzeby.get("reczny")):
            kand.append(("z", len(w["legs"]), w["powrot"]))
        najl = None
        najl_z = None
        for faza, j, etapy in kand:
            for ei, e in enumerate(etapy):
                if e["typ"] != "IDZ" or e["punkty"][0][2] != poz[2]:
                    continue
                for p in e["punkty"]:
                    d = cheb(poz, p)
                    if najl is None or d < najl[0]:
                        najl = (d, faza, j)
                    if faza == "z" and (najl_z is None or d < najl_z[0]):
                        najl_z = (d, faza, j)
        # trasa tam i z powrotem biegnie przez te same pola (chata Frodo, drzwi): zapisany powrót wygrywa remis
        if st.get("faza") == "z" and najl_z is not None and najl_z[0] <= WZNOW_ODL:
            najl = najl_z
        if najl is None or najl[0] > WZNOW_ODL:
            self.log(f"Wyprawa: pozycja {poz} poza planem wyprawy, nie wznawiam")
            self._stan_koniec(wynik="poza_planem")
            self._alarm_utknieciu(f"po restarcie postać {poz} jest poza planem wyprawy", stop=False)
            return False
        _d, faza, j = najl
        w["powod"], w["t_wall"] = st.get("powod", "wznowiona"), self.czas()
        w["k"] = min(j, len(w["stops"]) - 1)
        self.w = w
        self.kupione = dict(st.get("kupione") or {})
        self._plan_wyprawy = (w["legs"][min(j, len(w["legs"]) - 1)], w["powrot"])
        cb = self.cb
        self.plan, self.plan_nazwa = self._plan_wyprawy, "wyprawa"
        teraz = cb.zegar()
        self.stan = "WYPAD"
        self.t_start = teraz
        self.sklep = None
        self.utk = 0
        self.postep = None
        self.dojscie, self.dojscie_plany, self.dojscie_t0 = None, 0, None
        self.dojscie_sprawdz = True          # po restarcie postać bywa w części jaskini odciętej od planu
        self.wyjatki = 0
        self.wynik = None
        self.npc = w["stops"][w["k"]]["npc"]
        if faza == "z":
            self.faza, self.etapy = "z", w["powrot"]
        else:
            self.etapy = w["legs"][j]
            stoi = w["stops"][w["k"]]["stoi"]
            self.faza = "sklep" if cheb(poz, stoi) <= 2 and poz[2] == stoi[2] else "do"
        if self.faza != "sklep" and not self._resync_globalny(poz):
            self.stan, self.faza = "SPOKOJ", None
            self.w = None
            self._plan_wyprawy = None
            return False
        # drzwi na odcinkach, które postać już przeszła, są otwarte: pierwsza próba to sam krok (Use na otwartych
        # drzwiach mógłby je zamknąć)
        przeszle = w["legs"][:w["k"] + 1] if self.faza in ("sklep", "z") else w["legs"][:w["k"]]
        for et in przeszle:
            for e in et:
                if e["typ"] == "DRZWI":
                    self.drzwi_otwarte.add(tuple(e["drzwi"]))
        cb.wypad_aktywny = True
        cb._wypad_reset_klik()
        try:
            self.ops.wiadomosci()
        except Exception:
            pass
        self._ost_poz_w = poz
        self.log(f"Wyprawa: WZNOWIONA po restarcie ({st.get('powod')}), faza {self.faza}, przystanek "
                 f"{w['stops'][w['k']]['id']}, poz {poz}")
        self._tele("wyprawa_wznowiona", faza=self.faza, poz=list(poz), przystanek=w["stops"][w["k"]]["id"])
        self._stan_trasy()
        return True

    # --- obieg ---

    def _obieg(self, teraz):
        if self.w is not None:
            self.w["kroki"] += 1
            if self.w["kroki"] > int(self._kw("WYPRAWA_MAX_KROKOW")):
                self.w["kroki"] = 0
                return self._awaria("limit_krokow", f"ponad {self._kw('WYPRAWA_MAX_KROKOW')} obiegów wyprawy")
            poz = tuple(self.cb.postac.pozycja())
            ost = self._ost_poz_w
            self._ost_poz_w = poz
            if ost is not None and ost[2] == poz[2] and cheb(ost, poz) > SKOK_POZ:
                return self._teleport(ost, poz)
        return super()._obieg(teraz)

    def _teleport(self, ost, poz):
        self.log(f"Wyprawa: skok pozycji {ost} -> {poz}: teleport albo śmierć")
        self._alarm_utknieciu(f"skok pozycji {ost} -> {poz} (śmierć/teleport?), wyprawa przerwana", stop=True)
        self.zablokowany = True
        return self._koniec("blad", "teleport")

    def _etap_gotowy(self, e, poz, teraz):
        r = super()._etap_gotowy(e, poz, teraz)
        if self.w is not None:
            self._stan_trasy()
        return r

    def zakupy(self):
        if self.w is None:
            return super().zakupy()
        return [(k, c) for k, c in self.w["stops"][min(self.w["k"], len(self.w["stops"]) - 1)]["zakupy"]]

    # --- zakupy: limity ---

    def _max_koszt(self, klucz):
        if klucz == "blank":
            return int(self._kw("WYPRAWA_BLANKI_MAX_KOSZT"))
        return 0

    def _ile_zakupu(self, s, klucz, cel, ma):
        if self.w is None:
            return super()._ile_zakupu(s, klucz, cel, ma)
        ile = max(0, cel - (ma or 0))
        lim = s.get("limit_ile")
        if lim is not None:
            ile = min(ile, int(lim))
        cap = self._cap()
        s["cap_przed"] = cap
        waga = self._waga(klucz)
        if waga and cap is not None:
            wolne = cap - float(self._kw("WYPRAWA_CAP_REZERWA"))
            ile = min(ile, int(max(0.0, math.floor(wolne / waga))))
        cena = self.ceny.get(klucz)
        if cena:
            zloto = self._zloto()
            if zloto is not None:
                ile = min(ile, int(zloto // cena))
            mk = self._max_koszt(klucz)
            if mk > 0:
                ile = min(ile, int(mk // cena))
        return ile

    def _kontrola_oferty(self, s, klucz, teraz):
        if self.w is None:
            return None
        oferta = None
        for t in reversed(s["odpowiedzi"]):
            m = ODP_OFERTA.search(t)
            if m:
                oferta = (int(m[1]), int(m[3]))
                break
        if oferta is None or oferta[0] <= 0:
            return None
        n, koszt = oferta
        cena = koszt / n
        self.ceny[klucz] = cena
        zloto = self._zloto()
        limit, powod = n, None
        if zloto is not None and koszt > zloto:
            limit, powod = int(zloto // cena), "brak_zlota"
        mk = self._max_koszt(klucz)
        if mk > 0 and koszt > mk and int(mk // cena) < limit:
            limit, powod = int(mk // cena), "za_drogo"
        if limit >= n:
            return None
        self.log(f"Wyprawa: oferta {n} {klucz} za {koszt} gp ({cena:.1f}/szt.) ponad limit, schodzę do {limit}")
        if limit <= 0 or s.get("zmniejszen", 0) >= 3:
            return ("odmowa", powod or "za_drogo")
        s["zmniejszen"] = s.get("zmniejszen", 0) + 1
        return ("zmniejsz", limit)

    def _po_zakupie(self, s, klucz, kupiono):
        if self.w is None or not kupiono:
            return
        przed, po = s.get("cap_przed"), self._cap()
        if przed is not None and po is not None:
            cena = self.ceny.get(klucz, 0.0)
            w = (przed - po) / kupiono + cena * GOLD_WAGA     # zapłata złotem też coś waży
            if 0.2 <= w <= 60.0:
                if abs(w - (self._waga(klucz) or 0)) > 0.3:
                    self.log(f"Wyprawa: waga {klucz} z delty cap: {w:.2f} oz (było {self._waga(klucz)})")
                self.wagi[klucz] = round(w, 2)
        self._stan_zapisz()

    def _nastepny_przedmiot(self, s, teraz):
        s.pop("cap_proby", None)
        return super()._nastepny_przedmiot(s, teraz)

    def _odmowa(self, s, klucz, powod, teraz):
        if self.w is None:
            return super()._odmowa(s, klucz, powod, teraz)
        if powod == "brak_miejsca" and s.get("ile", 0) > 1 and s.get("cap_proby", 0) < 3:
            # serwer odrzucił za duży zakup (waga/cap inne niż zakładamy): połowa i jeszcze raz
            s["cap_proby"] = s.get("cap_proby", 0) + 1
            s["limit_ile"] = max(1, int(s["ile"]) // 2)
            self.log(f"Wyprawa: NPC odrzucił {s['ile']} {klucz} (miejsce/cap), próbuję {s['limit_ile']}")
            self._tele("wyprawa_krok", rodzaj="cap_odmowa", przedmiot=klucz, ile=s["ile"], nowe=s["limit_ile"])
            s["krok"] = "buy"
            s["nast"] = teraz + 1.0
            s["odpowiedzi"] = []
            return True
        self.log(f"Wyprawa: nie kupiłem {klucz}: {powod}")
        self._tele("wypad_zakup_odmowa", przedmiot=klucz, powod=powod, odpowiedzi=s["odpowiedzi"][-3:])
        s["wynik"][klucz] = "odmowa"
        if powod in ("brak_zlota", "brak_miejsca"):
            # kolejnych zakupów nie próbujemy, ale jedzenie na miejscu ("@jedz") nadal wykonujemy
            s["lista"] = s["lista"][:s["i"] + 1] + [(k, c) for k, c in s["lista"][s["i"] + 1:] if k == "@jedz"]
        return self._nastepny_przedmiot(s, teraz)

    # --- sklep: jedzenie na miejscu, kolejka ---

    def _sklep(self, poz, teraz):
        if self._w_depo():
            st0 = self.w["stops"][0]
            stoi = self._cel_dokroku(poz, st0)       # bez obszaru = stanowisko depo (jak dotąd); z obszarem patrz _cel_dokroku
            zasieg_dok = 3 if st0.get("obszar") else 1
            # tolerancja dojścia kończy etap już o pole przed celem: dokładamy krok na pole depo (do 3 prób)
            if stoi is not None and tuple(poz) != stoi and poz[2] == stoi[2] and cheb(poz, stoi) <= zasieg_dok \
                    and self.w.get("dokroki", 0) < 3:
                self.w["dokroki"] = self.w.get("dokroki", 0) + 1
                try:
                    self.cb.krok_do(stoi)
                except bot.Zatrzymano:
                    raise
                except Exception as e:
                    self._blad("depo_dokrok", opis=repr(e))
                self.cb.pauza(0.2, 0.4)
                return True
            # 13.10 14:37: jednorazowy odczyt pozycji z depo, gdy gracz stał 140 pól dalej (fałszywe "dotarłem", STOP):
            # koniec wyprawy dopiero po drugim, niezależnym odczycie tego samego pola
            try:
                self.cb.pauza(0.4, 0.6)
                poz2 = tuple(self.cb.postac.pozycja())
            except bot.Zatrzymano:
                raise
            except Exception:
                poz2 = None
            if poz2 != tuple(poz):
                self.log(f"Wyprawa: odczyt pozycji w depo {tuple(poz)} niepotwierdzony ({poz2}), ignoruję")
                self._blad("depo_odczyt", poz=list(poz), poz2=list(poz2) if poz2 else None)
                return True
            return self._zakoncz_depo("depo", f"jestem w depo {tuple(poz)}")
        if self.w is None:
            return super()._sklep(poz, teraz)
        st = self.w["stops"][min(self.w["k"], len(self.w["stops"]) - 1)]
        if st.get("depo_zloz"):
            return self._krok_depo_zloz(st, poz, teraz)
        s = self.sklep
        if s is not None and s["i"] < len(s["lista"]) and s["lista"][s["i"]][0] == "@jedz":
            return self._krok_jedz(s, teraz)
        wynik = super()._sklep(poz, teraz)
        s = self.sklep
        if s is not None:
            self._kolejka(s, teraz)
        return wynik

    def _krok_depo_zloz(self, st, poz, teraz):
        """Przystanek w depo: dostawiamy się na pole depo, składamy UH do skrzyni, dalej wyprawa (Frodo, Xodet)."""
        cb = self.cb
        stoi = tuple(st["stoi"])
        if tuple(poz) != stoi and poz[2] == stoi[2] and cheb(poz, stoi) <= 1 and self.w.get("dokroki_zloz", 0) < 3:
            self.w["dokroki_zloz"] = self.w.get("dokroki_zloz", 0) + 1
            try:
                cb.krok_do(stoi)
            except bot.Zatrzymano:
                raise
            except Exception as e:
                self._blad("depo_dokrok", opis=repr(e))
            cb.pauza(0.2, 0.4)
            return True
        try:
            wynik = self.ops.zloz_w_depo(cb.postac.pozycja)
        except bot.Zatrzymano:
            raise
        except Exception as ex:
            wynik = {"otwarte": False, "przeniesione": 0, "powod": f"wyjątek {ex!r}"}
        self.log(f"Wyprawa: składanie w depo: {wynik}")
        self._tele("wypad_krok", rodzaj="depo_zloz", **{k: v for k, v in wynik.items()})
        self.sklep = None
        return self._koniec_sklepu(teraz)

    def _kolejka(self, s, teraz):
        """NPC rozmawia z kimś innym: nie liczymy tego jako brak odpowiedzi (do KOLEJKA_MAKS razy)."""
        zajete = [t for t in s["odpowiedzi"] if ODP_ZAJETY.search(t)]
        if not zajete or s["krok"] not in ("hi", "hi_czeka"):
            return
        s["odpowiedzi"] = [t for t in s["odpowiedzi"] if not ODP_ZAJETY.search(t)]
        s["kolejka"] = s.get("kolejka", 0) + 1
        if s["kolejka"] > KOLEJKA_MAKS:
            return
        self.log(f"Wyprawa: NPC zajęty ({zajete[-1]!r}), czekam ({s['kolejka']}/{KOLEJKA_MAKS})")
        self._tele("wyprawa_kolejka", n=s["kolejka"])
        s["hi_proby"] = max(0, s["hi_proby"] - 1)
        s["od"] = teraz
        s["krok"] = "hi"                             # po pauzie powitanie od nowa (bez błędu "brak odpowiedzi")
        s["nast"] = max(s["nast"], teraz + KOLEJKA_PAUZA_S)

    def _krok_jedz(self, s, teraz):
        cb = self.cb
        j = s.setdefault("jedz", {"n": 0, "nast": teraz, "pusty": 0, "bledy": 0})
        if not int(self._kw("WYPRAWA_JEDZ_NA_MIEJSCU")):
            return self._jedz_koniec(s, j, "wylaczone", teraz)
        if teraz < j["nast"]:
            cb.pauza(0.2, 0.5)
            return True
        if j["n"] >= int(self._kw("WYPRAWA_JEDZ_MAKS")):
            return self._jedz_koniec(s, j, "limit", teraz)
        try:
            plecak = self.ops.plecak()
        except bot.Zatrzymano:
            raise
        except Exception as ex:
            self._blad("jedz_plecak", opis=repr(ex))
            return self._jedz_koniec(s, j, "blad_odczytu", teraz)
        if not self._jedzenie_ile(plecak):
            return self._jedz_koniec(s, j, "brak_jedzenia", teraz)
        try:
            zjedzone = self.ops.zjedz()
        except bot.Zatrzymano:
            raise
        except Exception as ex:
            j["bledy"] += 1
            self._blad("jedz_wyjatek", opis=repr(ex), n=j["bledy"])
            if j["bledy"] >= 3:
                return self._jedz_koniec(s, j, "blad", teraz)
            j["nast"] = teraz + 1.5
            return True
        pelny = False
        try:
            for w in self.ops.wiadomosci():
                if ODP_PELNY.search(w["tekst"]):
                    pelny = True
        except bot.Zatrzymano:
            raise
        except Exception:
            pass
        if zjedzone:
            j["n"] += len(zjedzone)
            j["pusty"] = 0
            self._tele("wyprawa_krok", rodzaj="jedzenie", zjedzone=list(zjedzone), n=j["n"])
        else:
            j["pusty"] += 1
        if pelny:
            return self._jedz_koniec(s, j, "full", teraz)
        if j["pusty"] >= 2:
            return self._jedz_koniec(s, j, "najedzony", teraz)
        j["nast"] = teraz + random.uniform(0.6, 1.2)
        cb.pauza(0.1, 0.3)
        return True

    def _jedz_koniec(self, s, j, powod, teraz):
        self.log(f"Wyprawa: jedzenie na miejscu: {j['n']} szt., koniec ({powod})")
        self._tele("wyprawa_krok", rodzaj="jedzenie_koniec", n=j["n"], powod=powod)
        s["wynik"]["@jedz"] = f"{powod}:{j['n']}"
        return self._nastepny_przedmiot(s, teraz)

    # --- koniec sklepu / wyprawy ---

    def _koniec_sklepu(self, teraz):
        if self.w is None:
            return super()._koniec_sklepu(teraz)
        s = self.sklep
        wynik = dict(s["wynik"]) if s else {}
        w = self.w
        st = w["stops"][w["k"]]
        w["wyniki"][st["id"]] = wynik
        if any(v in ("kupione", "mam") for k, v in wynik.items() if k != "@jedz"):
            w["sukces"] = True
        self.log(f"Wyprawa: przystanek {st['id']} zakończony: {wynik}")
        if st["id"] == "xodet" and wynik.get("blank") == "kupione":
            self._runy_do_pojemnika()
        self._tele("wypad_krok", rodzaj="sklep_koniec", przystanek=st["id"], wynik=wynik,
                   kupione=dict(self.kupione), czas_s=round(teraz - self.t_start))
        self.sklep = None
        self.wynik = None            # wynik wyprawy liczy _sukces()
        w["k"] += 1
        if w["k"] < len(w["stops"]):
            self.faza, self.etapy = "do", w["legs"][w["k"]]
            self.npc = w["stops"][w["k"]]["npc"]
        else:
            self.faza, self.etapy = "z", w["powrot"]
        poz = self.cb.postac.pozycja()
        self.ei = self.pi = 0
        if not self._resync_globalny(poz):
            return self._awaria("zgubiona_pozycja", f"po sklepie poz {poz}")
        self.postep = None
        self.przystanek_od = None
        self.cb._wypad_reset_klik()
        self._stan_trasy()
        return True

    def _runy_do_pojemnika(self):
        """Po zakupie blanków: z głównego plecaka do pojemnika na runy (drugi bag). Błąd nie psuje wyprawy."""
        fn = getattr(self.ops, "przenies_runy", None)
        if fn is None:
            return
        try:
            n = fn()
            self.log(f"Wyprawa: przeniosłem {n} run do pojemnika na runy")
            self._tele("wypad_krok", rodzaj="runy_do_pojemnika", n=n)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            self.log(f"Wyprawa: przenoszenie run do pojemnika nie wyszło ({e!r})")

    def _sukces(self):
        if self.w is not None:
            return bool(self.w.get("sukces"))
        return super()._sukces()

    def _zapisz_stop(self, opis):
        try:
            plik = self.plik_stop or bot.STOP
            Path(plik).write_text(f"wyprawa: {opis}\n")
            self.log(f"Wyprawa: zapisałem {plik} (zatrzymanie bota)")
        except OSError as e:
            self.log(f"Wyprawa: nie zapisałem STOP ({e})")

    def _alarm_utknieciu(self, opis, stop=True, wymus_stop=False):
        self._powiadom("Wyprawa: UTKNĘŁA", opis + (" Bot zatrzymany, potrzebny człowiek." if stop else ""),
                       "critical", "wyprawa_utknela")
        al = getattr(self.cb, "alarm", None)
        if callable(al):
            try:
                al(f"wyprawa: {opis}")
            except Exception:
                pass
        if stop and (wymus_stop or int(self._kw("WYPRAWA_STOP_PRZY_UTKNIECIU"))):
            self._zapisz_stop(opis)

    def _depo_powrot(self, poz):
        """WYPRAWA_DEPO_POWROT=1: po dojściu do depo (opcjonalny postój WYPRAWA_DEPO_POSTOJ_S na ręczne rzeczy)
        wracamy na spot fazą "z" po zapisanej trasie depo -> jaskinia, bez STOP. Kończy się jak zwykły powrót."""
        cb = self.cb
        w = self.w
        postoj = float(self._kw("WYPRAWA_DEPO_POSTOJ_S") or 0)
        self.log(f"Wyprawa: DEPO osiągnięte w {tuple(poz)}, postój {postoj:.0f} s, potem powrót na spot")
        self._powiadom("Wyprawa: jestem w depo", f"Bot stoi w depo {tuple(poz)}, za {postoj:.0f} s wraca na spot.",
                       "normal", "wyprawa_depo")
        if postoj > 0:
            cb.pauza(postoj, postoj + 0.5)
        w["sukces"] = True
        w["wyniki"]["depo"] = {"depo": "jestem"}
        self.sklep = None
        self.wynik = None
        self.faza, self.etapy = "z", w["powrot"]
        self.ei = self.pi = 0
        poz = tuple(cb.postac.pozycja())
        if not self._resync_globalny(poz):
            return self._awaria("zgubiona_pozycja", f"po depo poz {poz}")
        self.postep = None
        self.przystanek_od = None
        self.utk = 0
        cb._wypad_reset_klik()
        self._stan_trasy()
        return True

    # --- auto-refill po dojściu do depo (WROC_REFILL, 20.10; refill_auto.py) ---

    refill_start = None            # testy: podmieniają start czekacza (None = refill_auto.start_czekacza, prawdziwy proces)
    refill_procesy = None          # testy: podmieniają listę procesów (None = instancja.procesy, /proc tej instancji)

    def _auto_refill(self, poz):
        """Decyzja o auto-refillu przy STOP w depo: (stan, powód) z refill_auto.zlec albo None przy błędzie. Czekacz rusza dopiero
        po zapisie STOP (`_auto_refill_start`), bo bot musi wyjść z procesu, zanim refill.sh pozwoli startować."""
        stan_dir = Path(self.plik_stop or bot.STOP).parent
        try:
            import refill_auto  # noqa: PLC0415
            return refill_auto.zlec(tuple(poz), stan_dir, katalog=TRASY, start=lambda: None, procesy=self.refill_procesy)
        except Exception as e:                    # noqa: BLE001  (błąd pomocnika nie może zepsuć zatrzymania w depo)
            self.log(f"Wyprawa: auto-refill: błąd decyzji {e!r}, bot staje jak dotąd")
            return None

    def _auto_refill_start(self, refill):
        stan, powod = refill
        self._tele("wroc_refill", stan=stan, powod=powod)
        if stan != "czeka":
            self.log(f"Wyprawa: auto-refill pominięty: {powod}")
            self._powiadom("Wróć do miasta: bez auto-refillu", powod, "normal", "wroc_refill")
            return
        import refill_auto  # noqa: PLC0415
        try:
            (self.refill_start or refill_auto.start_czekacza)()
        except Exception as e:                    # noqa: BLE001
            stan_dir = Path(self.plik_stop or bot.STOP).parent
            refill_auto.zapisz_stan(stan_dir, "pominiety", f"nie udało się uruchomić czekacza: {e!r}")
            self.log(f"Wyprawa: auto-refill: czekacz nie wystartował ({e!r}), bot staje jak dotąd")
            return
        self.log(f"Wyprawa: auto-refill: {powod}")

    def _zakoncz_depo(self, wynik, opis):
        """Koniec wyprawy do depo: sukces (dotarcie) albo awaria. Zawsze plik STOP, stan wyczyszczony, bez
        powrotu na trasę łowiska i bez zakupów."""
        cb = self.cb
        w = self.w
        teraz = cb.zegar()
        poz = tuple(cb.postac.pozycja())
        if w is not None and (w.get("potrzeby") or {}).get("pk"):
            return self._zakoncz_pk(wynik, opis)
        reczny = bool(w is not None and (w.get("potrzeby") or {}).get("reczny"))
        if wynik == "depo" and int(self._kw("WYPRAWA_DEPO_POWROT")) and not reczny and w is not None \
                and sum(len(e.get("punkty") or ()) for e in w["powrot"]) > 1:
            return self._depo_powrot(poz)
        if wynik == "depo":
            self.log(f"Wyprawa: DEPO osiągnięte w {poz}, koniec wyprawy, zatrzymuję bota")
            refill = self._auto_refill(poz) if int(self._k("WROC_REFILL", 0)) else None     # 20.10: tylko przy WROC_REFILL=1
            self._powiadom("Wyprawa: jestem w depo", f"Bot stoi w depo {poz}{'' if reczny else (' (za mały cap)' if self._depo_z_capa() else ' (brak jedzenia)')}. "
                           + ("Bot zatrzymany, refill startuje sam." if refill and refill[0] == "czeka"
                              else "Bot zatrzymany, potrzebny człowiek."), "critical", "wyprawa_depo")
            self._zapisz_stop(f"dotarłem do depo {poz}")
            if refill is not None:
                self._auto_refill_start(refill)
        else:
            if opis != "teleport":          # teleport: alarm i STOP poszły już z _teleport
                self._alarm_utknieciu(f"{opis} (poz {poz})", stop=True, wymus_stop=True)
            else:
                self._zapisz_stop(f"teleport/śmierć w {poz}")
        co_min = max(float(self._kw("WYPRAWA_CO_MIN")) * 60.0, float(self._kw("WYPRAWA_PO_DEPO_S")))
        self.nast_wyprawa = teraz + co_min
        pam = {}
        if wynik == "depo":                  # P7c: pamięć "depo z powodu X" (przeżywa restart)
            st0 = self._stan_czytaj()
            pam = {"depo_powody": st0.get("depo_start_powody") or [], "depo_blanki": st0.get("depo_start_blanki"),
                   "depo_cap": st0.get("depo_start_cap"),
                   "depo_wall": self.czas()}
        self._stan_koniec(wynik=wynik, opis=opis, kupione={}, nast_wall=self.czas() + co_min,
                          wyniki=(w or {}).get("wyniki"), **pam)
        self._tele("wyprawa_koniec", wynik=wynik, opis=opis, kupione={}, depo=True, poz=list(poz),
                   czas_s=round(teraz - self.t_start))
        self.w = None
        self._plan_wyprawy = None
        self.zablokowany = True             # bot ma zostać w depo, żadnych samoczynnych wypraw
        self.stan = "SPOKOJ"
        self.faza = self.etapy = None
        self.sklep = None
        self.wynik = None
        cb.wypad_aktywny = False
        try:
            cb._wypad_reset_klik()
            cb.ustaw_stan("IDZ", "wyprawa do depo zakończona")
        except Exception:
            pass
        return True

    # --- rotacja napraw zamiast STOP (22.10, Karol: „naprawiaj, nie zatrzymuj”; dawajkesh z11 -> z10) ---

    _rot = None                    # {"klucz": (faza, ei), "n": kolejna seria nieudanych prób tego przejścia}
    _rot_alarm = float("-inf")     # kiedy ostatnio poszedł alarm „rotacja wyczerpana” (bez STOP)

    def _rot_odejdz(self, poz, etap, ile):
        """Odejście o `ile` pól na INNE wolne pole (nie pole przejścia ani lądowania, nie zajęte, przechodnie wg mapy)."""
        cb = self.cb
        poz = tuple(poz)
        mapa = getattr(cb, "mapa", None)
        zakaz = {tuple(etap[k][:2]) for k in ("cel", "ladunek", "dziura") if etap.get(k)}
        for _ in range(ile):
            zaj = self._zajete_pola(poz)
            kand = []
            for kier, dx, dy in (("Up", 0, -1), ("Left", -1, 0), ("Right", 1, 0), ("Down", 0, 1)):
                q = (poz[0] + dx, poz[1] + dy)
                if q in zaj or q in zakaz:
                    continue
                f = wypad._flaga(mapa, (q[0], q[1], poz[2])) if mapa is not None else 1
                if f & (4 | 2) or not f & 1:
                    continue
                kand.append((kier, q))
            if not kand:
                break
            kier, q = random.choice(kand)
            self.log(f"Wyprawa: rotacja napraw, odchodzę {kier} na pole {q} (inne pole, potem ponowię przejście)")
            try:
                cb.postac.krok(kier)
            except bot.Zatrzymano:
                raise
            except Exception:
                break
            cb.pauza(0.3, 0.5)
            poz = tuple(cb.postac.pozycja())
        return poz

    def _rotacja_naprawy(self, typ, opis, etap):
        """Nieudane przejście (LINA/DZIURA/DRZWI) w wyprawie do depo: zamiast ALARM + STOP kolejne naprawy.
        1) odejście na inne pole i ponowienie, 2) zdjęcie rzeczy z pola liny (+ zejście ze skosu) i ponowienie,
        3) odejście o 2 pola, lista sposobów przebudowana od zera (pamięć przejść), ponowienie,
        4) po wyczerpaniu: sam alarm (bez STOP) i powrót na spot (faza "do": wracamy bez depo, następna wyprawa po
        WYPRAWA_CO_MIN) albo ponawianie co AWARIA_PO_S w fazie powrotnej. Zagrożenie życia (PK, zgon) tej ścieżki nie dotyczy."""
        cb = self.cb
        teraz = cb.zegar()
        poz = tuple(cb.postac.pozycja())
        klucz = (self.faza, self.ei)
        if self._rot is None or self._rot["klucz"] != klucz:
            self._rot = {"klucz": klucz, "n": 0}
        self._rot["n"] += 1
        n = self._rot["n"]
        limit = int(self._kw("WYPRAWA_ROTACJA_NAPRAW"))
        self._blad(typ, opis=opis, rotacja=n)
        self.dojscie = None
        self.postep = None
        self.utk = 0
        self.pj = None
        if n <= limit:
            self.log(f"Wyprawa: rotacja napraw {n}/{limit} po '{typ}' ({opis}); STOP nie zapisuję")
            self._powiadom("Wyprawa: naprawiam przejście", f"{typ}: {opis}. Próba naprawy {n}/{limit}, bot nie staje.",
                           "normal", "wyprawa_rotacja")
            if n == 2 and etap["typ"] == "LINA" and cheb(poz, etap["cel"]) == 1 and poz[2] == etap["cel"][2]:
                poz = wypad._lina_powtorka(self, poz, etap["cel"])
            else:
                poz = self._rot_odejdz(poz, etap, 2 if n >= 3 else 1)
            etap["proby"] = 0
            etap.pop("trzy_lista", None)
            etap["nast"] = teraz + random.uniform(15.0, 40.0)
            cb._wypad_reset_klik()
            return True
        if teraz - self._rot_alarm > 600:
            self._rot_alarm = teraz
            self._alarm_utknieciu(f"{typ}: {opis} (rotacja napraw wyczerpana, poz {poz}; bot nie staje, ponawia)", stop=False)
        self.log(f"Wyprawa: rotacja napraw wyczerpana ({typ}); bez STOP")
        if self.faza in ("do", "sklep"):
            # wracamy na łowisko (faza "z" po planie powrotnym); koniec powrotu = zwykły _koniec, następna wyprawa po
            # WYPRAWA_CO_MIN. Gdy plan powrotny nie obejmuje tego piętra (resync nie wychodzi): zostajemy i ponawiamy, bez STOP.
            stare = (self.faza, self.etapy, self.ei, self.pi, self.wynik)
            try:
                powrot = self._plan()[1]
            except Exception:
                powrot = None
            if powrot:
                self.faza, self.etapy, self.sklep, self.wynik = "z", powrot, None, "porazka_sklepu"
                if self._resync_globalny(poz):
                    self._rot = None
                    self.log("Wyprawa: rotacja napraw wyczerpana, wracam na spot; wyprawę ponowię po przerwie")
                    self.postep = None
                    self.utk = 0
                    cb._wypad_reset_klik()
                    return True
                self.faza, self.etapy, self.ei, self.pi, self.wynik = stare
        etap["proby"] = 0
        etap["nast"] = teraz + wypad.AWARIA_PO_S              # faza powrotna: ponawiamy cały etap po przerwie
        return True

    def _awaria(self, typ, opis, etap=None):
        if self._w_depo():
            if etap is not None and etap.get("typ") in ("LINA", "DZIURA", "DRZWI") \
                    and not ((self.w.get("potrzeby") or {}).get("pk")) and int(self._kw("WYPRAWA_ROTACJA_NAPRAW")) > 0:
                return self._rotacja_naprawy(typ, opis, etap)
            self._blad(typ, opis=opis)
            return self._koniec("blad", f"{typ}: {opis}")
        return super()._awaria(typ, opis, etap)

    def _koniec(self, wynik, opis):
        self.dojscie = None
        if self._w_depo() and not (self.faza == "z" and wynik in ("ok", "bez_zakupow")):
            return self._zakoncz_depo(wynik if wynik == "depo" else "blad", opis)
        w = self.w
        if w is not None:
            teraz = self.cb.zegar()
            if wynik == "blad" and self.faza == "z" and opis != "teleport":
                self._alarm_utknieciu(f"{opis or 'utknięcie w drodze powrotnej'} (poz {tuple(self.cb.postac.pozycja())})")
            self.nast_wyprawa = teraz + float(self._kw("WYPRAWA_CO_MIN")) * 60.0
            self._stan_koniec(wynik=wynik, opis=opis, kupione=dict(self.kupione),
                              nast_wall=self.czas() + float(self._kw("WYPRAWA_CO_MIN")) * 60.0,
                              wyniki=w.get("wyniki"))
            self._tele("wyprawa_koniec", wynik=wynik, opis=opis, kupione=dict(self.kupione),
                       wyniki=w.get("wyniki"), czas_s=round(teraz - self.t_start))
            self.w = None
            self._plan_wyprawy = None
        return super()._koniec(wynik, opis)

    def przerwij(self, powod):
        if self.w is not None:
            if str(powod).upper().startswith("ALARM"):
                self._stan_koniec(wynik="przerwana", powod=str(powod))
            else:
                # STOP: zapis zostaje (przerwana=True), kolejny start bota wznowi wyprawę od najbliższego odcinka
                self._stan_zapisz(przerwana=True, zapis_wall=self.czas())
            self.w = None
            self._plan_wyprawy = None
        return super().przerwij(powod)


# --- CLI: sprawdzenie danych bez ruszania gry -----------------------------------

def raport(katalog=TRASY, plik_sklepow=PLIK_SKLEPOW, plik_npc=PLIK_NPC, mapa=None, log=print):
    """Czego brakuje do uruchomienia wyprawy; zwraca listę problemów (puste = gotowe do prób)."""
    problemy = []
    baza = punkty_bazy(katalog)
    for n in BAZY:
        if n not in baza:
            problemy.append(f"brak plików trasy bazowej {n} (generuj_trase_miasta.py)")
        else:
            do, z, npc = baza[n]
            log(f"baza {n}: do_miasta {len(do)} pkt -> {do[-1]} (NPC {npc}), z_miasta {len(z)} pkt od {z[0]}")
    cfg = wczytaj_sklepy(plik_sklepow)
    npc = wczytaj_npc(plik_npc)
    for klucz, domyslny in (("frodo", "Frodo"), ("xodet", "Xodet")):
        c = cfg.get(klucz, {})
        nazwa = c.get("npc") or domyslny
        if c.get("stoi") or c.get("npc_poz") or nazwa in npc:
            zr = "stoi" if c.get("stoi") else ("npc_poz" if c.get("npc_poz") else "uczone z widoku")
            log(f"{klucz}: pozycja znana ({zr}), zweryfikowana={c.get('zweryfikowane', False)}")
        else:
            problemy.append(f"{klucz}: brak pozycji (wpisz 'stoi' albo 'npc_poz' w {Path(plik_sklepow).name} "
                            f"albo przejdź obok NPC {nazwa} z działającym botem)")
    if mapa is not None and baza:
        t = Trasownik(mapa)
        for klucz, domyslny in (("frodo", "Frodo"), ("xodet", "Xodet")):
            c = cfg.get(klucz, {})
            nazwa = c.get("npc") or domyslny
            n0 = next(iter(baza.values()))
            do = n0[0]
            if c.get("stoi") and c.get("dojscie"):
                # nagrany marsz (z drzwiami, które mapa zna jako ścianę): A* po mapie nie ma tu sensu
                pts = [q for q in (_punkt(p) for p in c["dojscie"]) if q]
                dz = sorted(drzwi_przystankow({klucz: c}, mapa))
                if dz:
                    log(f"{klucz}: drzwi na trasie (przechodnie w planie): {dz}")
            elif c.get("stoi"):
                pts = t.odcinek(do[-1], tuple(c["stoi"]))
            elif c.get("npc_poz") or nazwa in npc:
                r = t.stoisko(do[-1], tuple(c.get("npc_poz") or npc[nazwa]))
                pts = r[1] if r else None
            else:
                continue
            log(f"{klucz}: A* od {do[-1]}: " + (f"{len(pts)} pkt, koniec {pts[-1]}" if pts else "BRAK DROGI"))
            if not pts:
                problemy.append(f"{klucz}: brak drogi po mapie od Gorna")
    return problemy


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "plan"
    if cmd == "stan":
        print(json.dumps(_json(PLIK_STANU), ensure_ascii=False, indent=1))
        return 0
    if cmd == "plan":
        mapa = None
        try:
            import mapa as _m  # noqa: PLC0415
            mapa = _m.Mapa()
        except Exception as e:
            print(f"mapa niedostępna ({e!r}), sprawdzam tylko pliki")
        problemy = raport(mapa=mapa)
        for p in problemy:
            print("DO ZROBIENIA:", p)
        print("gotowe do prób" if not problemy else f"{len(problemy)} rzeczy do uzupełnienia")
        return 0 if not problemy else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
