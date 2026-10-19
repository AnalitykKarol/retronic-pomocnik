"""Wpisy-widma na liście stworów/graczy (widma.py, STWORY_WIDMA). Offline: bez gry, bota, sesji i gniazd.

Fixture to WIERSZE z logu logi/mozg-20261019-1806.log (linie `debug: stwory: <nazwa> <dx>,<dy> hp<N>; ...`, względem pozycji
bota, pierwszy wpis = sam bot), z 19.10, Edron, z7: ten sam układ co w raporcie (Ucho/Patriko/Antysemita na (0,0) = polu bota,
Harleyqueen+Ucho+Prolvldeus na jednym polu). ID i piętro (z7) doklejone, bo log ich nie ma.

Czego dowodzi: (a) wpis obcego gracza na polu bota nie liczy się do zajętości ani do oceny graczy, (b) kilku graczy na jednym
polu = jeden reprezentant, reszta `widmo` (nic nie jest usuwane), (c) inne piętro nigdy nie wchodzi do ocen, (d) PK/czaszki/GM
i stan dla modelu dostają listę w całości, (e) pokrętło STWORY_WIDMA=0 = stare zachowanie, (f) rdzeń zostawia ślad
dla zdublowanego ID (`kopie`). Na starym kodzie (bez widma.py) testy a/b/e/f padają, c/d zielone (to straż, nie poprawka)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import itertools
import random
import struct
import sys
import types
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(_os.path.dirname(_os.path.abspath(__file__))).parent))
import bot  # noqa: E402,F401
import cavebot  # noqa: E402
import mozg  # noqa: E402
import pokretla  # noqa: E402
import rdzen  # noqa: E402
import serwis as S  # noqa: E402
import serwis_akcje  # noqa: E402
import unikanie  # noqa: E402
try:
    import widma  # noqa: E402
except ImportError:          # stary kod: testy mają paść na asercjach, nie na imporcie
    widma = None

ok = []
LOGI = []
cavebot.log = lambda *a: LOGI.append(" ".join(map(str, a)))


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


POZ = (33167, 31811, 7)
WIERSZE = {
    # 3 graczy na jednym polu (Harleyqueen, Ucho, Prolvldeus) 5 pól na północ; reszta tłumu obok
    "19:33:36": "Mastafian 0,0 hp100; Harleyqueen 2,-5 hp100; Ucho 2,-5 hp100; Milfhunter 3,-5 hp100; Prolvldeus 2,-5 hp100; Tocuyona 3,-5 hp100; Aixhia 5,-6 hp100",
    # Ucho na polu bota (0,0) + dwie pary na jednym polu ((1,0) i (2,0))
    "19:42:23": "Mastafian 0,0 hp100; Ucho 0,0 hp100; Harleyqueen 1,0 hp100; Prolvldeus 1,0 hp100; Milfhunter 2,0 hp100; Tocuyona 2,0 hp100; Aixhia 4,-1 hp100",
    # Patriko i Ucho oboje na polu bota
    "19:47:32": "Mastafian 0,0 hp100; Patriko 0,0 hp100; Ucho 0,0 hp100; Prolvldeus 1,0 hp100; Deetasea 1,0 hp100; Milfhunter 2,0 hp100; Tocuyona 2,0 hp100; Aixhia 4,-1 hp100",
    # Antysemita na polu bota
    "19:49:13": "Mastafian 0,0 hp100; Ucho 0,0 hp100; Antysemita 0,0 hp100; Prolvldeus 1,0 hp100; Deetasea 1,0 hp100; Milfhunter 2,0 hp100; Aixhia 4,-1 hp100",
}
_IDY = {}


def id_gracza(nazwa):
    if nazwa == "Mastafian":
        return 0x10000001
    return _IDY.setdefault(nazwa, 0x10000100 + len(_IDY))


def wiersz(klucz, poz=POZ, z=None):
    """Lista jak z komendy `stwory` z linii logu: pierwszy wpis = bot; pozycje = poz + (dx, dy)."""
    wynik = []
    for wpis in WIERSZE[klucz].split("; "):
        nazwa, xy, hp = wpis.rsplit(" ", 2)
        dx, dy = (int(v) for v in xy.split(","))
        wynik.append({"id": id_gracza(nazwa), "nazwa": nazwa, "gracz": True, "x": poz[0] + dx, "y": poz[1] + dy,
                      "z": poz[2] if z is None else z, "hp": int(hp[2:]), "kierunek": 2, "adres": hex(0x1000 + len(wynik))})
    return wynik


def nazwy(lista):
    return sorted(s["nazwa"] for s in lista)


def oznaczone(lista):
    return {s["nazwa"]: s["widmo"] for s in lista if s.get("widmo")}


# id: Harleyqueen < Ucho < Milfhunter < Prolvldeus < Tocuyona < Aixhia < Patriko < Deetasea < Antysemita (kolejność pierwszego użycia)
for k in WIERSZE:
    wiersz(k)

# =========================================================================================================
# A. widma.oznacz na wierszach z logu
# =========================================================================================================
if widma is None:
    sprawdz("A0 widma.py istnieje", False, "brak modułu widma (stary kod)")
else:
    l = wiersz("19:42:23")
    n0 = len(l)
    wyn = widma.oznacz(l, "Mastafian")
    sprawdz("A1 19:42:23: Ucho na polu bota = widmo na_polu_bota", oznaczone(l).get("Ucho") == widma.NA_POLU_BOTA, oznaczone(l))
    sprawdz("A2 19:42:23: z pary na (1,0) i pary na (2,0) zostaje po jednym (niższe id), drugi duplikat_pola",
            oznaczone(l) == {"Ucho": "na_polu_bota", "Prolvldeus": "duplikat_pola", "Tocuyona": "duplikat_pola"}, oznaczone(l))
    sprawdz("A3 reprezentanci i Aixhia bez znacznika, sam bot nigdy", all("widmo" not in s for s in l if s["nazwa"] in (
        "Mastafian", "Harleyqueen", "Milfhunter", "Aixhia")))
    sprawdz("A4 nic nie usunięte (diagnostyka zachowuje wszystkie wpisy) i zwrócono dokładnie oznaczone",
            len(l) == n0 == 7 and len(wyn) == 3 and {s["nazwa"] for s in wyn} == {"Ucho", "Prolvldeus", "Tocuyona"})
    sprawdz("A5 bez_widm: 4 wpisy (bot, Harleyqueen, Milfhunter, Aixhia), oryginał nietknięty",
            nazwy(widma.bez_widm(l)) == ["Aixhia", "Harleyqueen", "Mastafian", "Milfhunter"] and len(l) == 7)
    ten = [{"id": 1, "nazwa": "X", "gracz": True, "x": 1, "y": 1, "z": 7}]
    sprawdz("A5b bez_widm bez widm zwraca tę samą listę (bez kopii)", widma.bez_widm(ten) is ten)

    l = wiersz("19:33:36")
    widma.oznacz(l, "Mastafian")
    sprawdz("A6 19:33:36: trzech graczy na jednym polu (2,-5) = reprezentant Harleyqueen, Ucho i Prolvldeus duplikat_pola "
            "(+ Tocuyona z pary (3,-5))",
            oznaczone(l) == {"Ucho": "duplikat_pola", "Prolvldeus": "duplikat_pola", "Tocuyona": "duplikat_pola"}
            and "widmo" not in l[1], oznaczone(l))
    sprawdz("A7 para (3,-5) Milfhunter+Tocuyona: reprezentant Milfhunter (niższe id), Tocuyona duplikat_pola",
            oznaczone(l).get("Tocuyona") == "duplikat_pola" and "Milfhunter" not in oznaczone(l), oznaczone(l))

    # stabilność wyboru: ta sama grupa w dowolnej kolejności wpisów daje tego samego reprezentanta
    wynik_perm = set()
    for perm in itertools.permutations(range(len(wiersz("19:33:36")))):
        base = wiersz("19:33:36")
        lp = [base[i] for i in perm]
        widma.oznacz(lp, "Mastafian")
        wynik_perm.add(tuple(sorted(oznaczone(lp).items())))
        if len(wynik_perm) > 1:
            break
    sprawdz("A8 stabilny wybór: 5040 kolejności wpisów -> zawsze te same wpisy oznaczone", len(wynik_perm) == 1, wynik_perm)

    l = wiersz("19:47:32")
    widma.oznacz(l, "Mastafian")
    sprawdz("A9 19:47:32: Patriko i Ucho oboje na polu bota = oboje na_polu_bota (a nie jedno z nich reprezentantem)",
            oznaczone(l).get("Patriko") == "na_polu_bota" and oznaczone(l).get("Ucho") == "na_polu_bota", oznaczone(l))
    l = wiersz("19:49:13")
    widma.oznacz(l, "Mastafian")
    sprawdz("A10 19:49:13: Antysemita na polu bota", oznaczone(l).get("Antysemita") == "na_polu_bota", oznaczone(l))

    l = wiersz("19:42:23")
    widma.oznacz(l, "Mastafian")
    pierwsze = oznaczone(l)
    widma.oznacz(l, "Mastafian")
    sprawdz("A11 oznacz jest idempotentne (drugie wołanie na tej samej liście nie zmienia wyniku)", oznaczone(l) == pierwsze)
    l[1]["x"] += 5      # Ucho odchodzi z pola bota: znacznik znika przy kolejnym oznaczeniu
    widma.oznacz(l, "Mastafian")
    sprawdz("A12 gdy Ucho zejdzie z pola bota, traci znacznik (nic nie zostaje na stałe)", "Ucho" not in oznaczone(l), oznaczone(l))

    # reprezentant: groźny przed zwykłym, niezależnie od id
    l = wiersz("19:33:36")
    groznym = next(s for s in l if s["nazwa"] == "Prolvldeus")
    widma.oznacz(l, "Mastafian", wazny=lambda s: s is groznym)
    sprawdz("A13 groźny gracz w grupie jest reprezentantem (nie znika z ocen graczy)",
            "widmo" not in groznym and oznaczone(l).get("Harleyqueen") == "duplikat_pola", oznaczone(l))

    # (c) piętra
    l = wiersz("19:42:23")
    l[1]["z"] = 6                                  # Ucho na piętrze wyżej, ten sam x,y co bot
    widma.oznacz(l, "Mastafian")
    sprawdz("A14 piętra: gracz na innym z niż bot, choć ten sam x,y, NIE jest widmem na_polu_bota", "Ucho" not in oznaczone(l), oznaczone(l))
    l = [dict(s) for s in wiersz("19:33:36")]
    l[2]["z"] = 8                                  # Ucho na tym samym x,y co Harleyqueen, ale na z8
    widma.oznacz(l, "Mastafian")
    sprawdz("A15 piętra: ten sam x,y na różnych z to nie duplikat pola (Ucho z z8 bez znacznika; Prolvldeus i Tocuyona jak wyżej)",
            oznaczone(l) == {"Prolvldeus": "duplikat_pola", "Tocuyona": "duplikat_pola"}, oznaczone(l))
    l = [{"id": 1, "nazwa": "Mastafian", "gracz": True, "x": 10, "y": 10, "z": 7},
         {"id": 0x40000001, "nazwa": "Rat", "gracz": False, "x": 10, "y": 10, "z": 7, "hp": 100},
         {"id": 0x40000002, "nazwa": "Rat", "gracz": False, "x": 10, "y": 10, "z": 7, "hp": 100}]
    sprawdz("A16 potwory nigdy nie są widmami (tylko obcy gracze)", widma.oznacz(l, "Mastafian") == [] and not oznaczone(l))
    # bez własnego wpisu w liście: pole bota z `poz`; duplikat własnej nazwy (relog) bez zgodnej pozycji: kryterium (a) wyłączone
    l = wiersz("19:42:23")[1:]
    widma.oznacz(l, "Mastafian", poz=POZ)
    sprawdz("A17 brak własnego wpisu: pole bota z poz (Ucho na poz = widmo)", oznaczone(l).get("Ucho") == "na_polu_bota", oznaczone(l))
    l = wiersz("19:42:23")
    duch = dict(l[0], id=0x10000099, x=POZ[0] + 9, adres="0x9")
    l.append(duch)
    widma.oznacz(l, "Mastafian")
    sprawdz("A18 dwa wpisy własnej nazwy (widmo po relogu) i brak poz: nie zgadujemy pola bota (Ucho bez znacznika na_polu_bota)",
            oznaczone(l).get("Ucho") != "na_polu_bota", oznaczone(l))
    widma.oznacz(l, "Mastafian", poz=POZ)
    sprawdz("A19 ten sam przypadek z poz zgodną z jednym z nich: pole bota z poz", oznaczone(l).get("Ucho") == "na_polu_bota", oznaczone(l))

# =========================================================================================================
# B. Cavebot: stwory() zwraca listę w całości (PK/GM), konsumenci zajętości/ocen pomijają widma
# =========================================================================================================


class Swiat:
    def __init__(s, lista, poz=POZ):
        s.lista, s.poz, s.t = lista, list(poz), 0.0
        s.alarmy, s.klawisze = [], []

    def zegar(s):
        return s.t

    def spij(s, d):
        s.t += d

    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            return {"stwory": [dict(m) for m in s.lista]}
        raise AssertionError(z)


class P:
    nazwa = "Mastafian"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        return tuple(p.s.poz)

    def klawisz(p, k):
        p.s.klawisze.append(k)

    def krok(p, k):
        return tuple(p.s.poz)


def zrob(s, klasa=cavebot.Cavebot):
    punkty = [(POZ[0] + i, POZ[1], POZ[2]) for i in range(1, 11)]
    return klasa(P(s), punkty, okrazenia=999, zapytaj=s.zapytaj, atak=lambda m, g: None,
                 alarm=lambda w: s.alarmy.append(w), spij=s.spij, zegar=s.zegar,
                 loot=types.SimpleNamespace(zbierz=lambda zw, g: "ok"))


cavebot.UNIKANIE_TYLKO_SPOT = 0       # Edron to miasto (z7), test sprawdza ocenę graczy, nie wyłączenie w mieście
for k in ("REAKCJA",):
    setattr(cavebot, k, (0.0, 0.0))
cavebot.DRUGI_CEL = 0.0
cavebot.ROZRZUT_PROGU = 0.0
cavebot.STRAZNIK_CEL = 0
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5)
cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)

# B1. pokrętło
sprawdz("B0 pokrętło STWORY_WIDMA: w cavebot.py domyślnie 1, w ZAKRESY (0,1), analityk nie wyłącza (nie_nizej)",
        getattr(cavebot, "STWORY_WIDMA", None) == 1 and pokretla.ZAKRESY.get("STWORY_WIDMA") == (0, 1)
        and pokretla.KIERUNEK.get("STWORY_WIDMA") == "nie_nizej")

s = Swiat(wiersz("19:42:23"))
b = zrob(s)
lista = b.stwory()
sprawdz("B1 stwory() zwraca WSZYSTKIE 7 wpisów (PK/GM/czaszki czytają to samo co dotąd)", len(lista) == 7 and nazwy(lista) == nazwy(wiersz("19:42:23")), nazwy(lista))
sprawdz("B2 wpisy-widma w stwory() mają znacznik `widmo` (Ucho, Prolvldeus, Tocuyona)",
        set(oznaczone(lista)) == {"Ucho", "Prolvldeus", "Tocuyona"}, oznaczone(lista))
b.ostatnie_stwory = lista
zywe = getattr(b, "bez_widm", lambda l: l)(b.ostatnie_stwory)
sprawdz("B3 bez_widm(ostatnie_stwory): 4 wpisy bez widm; ostatnie_stwory nadal 7",
        len(zywe) == 4 and len(b.ostatnie_stwory) == 7 and "Ucho" not in nazwy(zywe), nazwy(zywe))
sprawdz("B4 rzadki log: wpis 'Widmo: gracz Ucho' raz, nie przy każdym odczycie",
        sum("Widmo: gracz Ucho" in l for l in LOGI) == 1, [l for l in LOGI if "Widmo" in l])
LOGI.clear()
b.stwory()
b.stwory()
sprawdz("B4b powtórny odczyt w oknie LOG_CO_S nie spamuje logu", not any("Widmo" in l for l in LOGI), LOGI)

# (a) zajętość: wpis na polu bota nie blokuje pola, na którym bot stoi wg SWOJEGO wpisu w liście, gdy poz jest o krok z tyłu
s = Swiat(wiersz("19:42:23"), poz=(POZ[0] - 1, POZ[1], POZ[2]))      # poz odczytane przed krokiem: bot już stoi na POZ
b = zrob(s)
b.ostatnie_stwory = b.stwory()
zaj = set(b.zajete_bez_nas((POZ[0] - 1, POZ[1], POZ[2])))
sprawdz("B5 pole, na którym bot faktycznie stoi (własny wpis), nie jest 'zajęte' przez Ucho (poz o krok z tyłu)",
        (POZ[0], POZ[1]) not in zaj, sorted(zaj))
sprawdz("B6 reprezentanci tłumu dalej blokują ich pola ((x+1,y) Harleyqueen, (x+2,y) Milfhunter, Aixhia)",
        {(POZ[0] + 1, POZ[1]), (POZ[0] + 2, POZ[1]), (POZ[0] + 4, POZ[1] - 1)} <= zaj, sorted(zaj))

# (c) piętra w zajętości
l = wiersz("19:42:23")
l[2]["z"] = 6                      # Harleyqueen na piętrze wyżej, pole (x+1,y)
l[3]["z"] = 6                      # Prolvldeus też (x+1,y,z6)
s = Swiat(l)
b = zrob(s)
b.ostatnie_stwory = b.stwory()
zaj = set(b.zajete_bez_nas(POZ))
sprawdz("B7 piętra: gracze z innego z nie zajmują pól na tym piętrze", (POZ[0] + 1, POZ[1]) not in zaj, sorted(zaj))
sprawdz("B7b piętra: inni_gracze liczy tylko to samo z", all(g["z"] == POZ[2] for g in b.inni_gracze(b.ostatnie_stwory, POZ)))

# (b)(a) ocena graczy w unikaniu/mijaniu
KONF = dict(UNIKANIE=1, UNIKANIE_PROMIEN=9, UNIKANIE_PROMIEN_MAX=14, UNIKANIE_DEBOUNCE=1.5, UNIKANIE_ZNIKL_S=10.0,
            UNIKANIE_MOB_PROMIEN=4, UNIKANIE_PUNKT_D=6, UNIKANIE_DROGA_MIN=4, UNIKANIE_BLOK_S=45.0,
            UNIKANIE_SPOT_S=180.0, UNIKANIE_POWIADOM_S=300.0)


def z_unikaniem(lista):
    s = Swiat(lista)
    b = zrob(s)
    b.zatrzymaj_przy_graczu = True
    b.unikanie = unikanie.Unikanie(types.SimpleNamespace(**KONF), zegar=s.zegar, log=lambda *a: None,
                                   zdarzenie=lambda typ, **d: None, powiadom=lambda *a, **kw: None)
    lst = b.stwory()
    b._unikanie_obserwuj(lst, tuple(s.poz))
    return b, [g["nazwa"] for g in b.unikanie.gracze]


b, gr = z_unikaniem(wiersz("19:42:23"))
sprawdz("B8 ocena graczy (unikanie/mijanie) na wierszu 19:42:23: bez Ucha na polu bota, po jednym z pary = 3 gracze (było 6)",
        sorted(gr) == ["Aixhia", "Harleyqueen", "Milfhunter"], gr)
b, gr = z_unikaniem([wiersz("19:42:23")[0], dict(wiersz("19:47:32")[1])])
sprawdz("B9 sam Patriko na polu bota (reszta wiersza 19:47:32 pominięta): unikanie się NIE włącza (było: start przy odl 0)",
        not b.unikanie.aktywne and gr == [], (b.unikanie.aktywne, gr))
b, gr = z_unikaniem(wiersz("19:33:36"))
sprawdz("B10 19:33:36: trzech na jednym polu liczy się raz (Harleyqueen), Milfhunter/Tocuyona raz, Aixhia = 3 gracze (było 6)",
        sorted(gr) == ["Aixhia", "Harleyqueen", "Milfhunter"], gr)

# (e) pokrętło 0 = stare zachowanie
cavebot.STWORY_WIDMA = 0
b, gr = z_unikaniem(wiersz("19:42:23"))
sprawdz("B11 STWORY_WIDMA=0: stare zachowanie (6 graczy, bez znaczników, bez_widm to ta sama lista)",
        len(gr) == 6 and "Ucho" in gr and not oznaczone(b.stwory()) and getattr(b, "bez_widm", lambda l: l)(b.stwory()) is not None, gr)
s = Swiat(wiersz("19:42:23"), poz=(POZ[0] - 1, POZ[1], POZ[2]))
b = zrob(s)
b.ostatnie_stwory = b.stwory()
sprawdz("B12 STWORY_WIDMA=0: pole bota znów 'zajęte' przez Ucho (poz o krok z tyłu)",
        (POZ[0], POZ[1]) in set(b.zajete_bez_nas((POZ[0] - 1, POZ[1], POZ[2]))))
cavebot.STWORY_WIDMA = 1

# (d) PK/GM/czaszki dostają listę w całości
# GM na polu bota: tick zatrzymuje się w stanie GRACZ i alarmuje, mimo że wpis jest widmem na_polu_bota
l = wiersz("19:42:23")
l[1]["nazwa"] = "GM Wilk"
s = Swiat(l)
b = zrob(s)
b.tick()
sprawdz("C1 GM na polu bota: tick alarmuje i staje w GRACZ (filtr nie ukrył GM)", b.stan == "GRACZ" and s.alarmy, (b.stan, s.alarmy))
sprawdz("C1b GM na polu bota ma znacznik widmo, a inni_gracze(lista) go zawiera",
        b.stwory_surowe and next(m for m in b.ostatnie_stwory if m["nazwa"] == "GM Wilk").get("widmo") == "na_polu_bota"
        and "GM Wilk" in nazwy(b.inni_gracze(b.ostatnie_stwory, POZ)), nazwy(b.ostatnie_stwory))

# gracz z czaszką na polu bota albo jako duplikat w grupie: PK-owe predykaty i _grozni_w_zasiegu go widzą
l = wiersz("19:42:23")
l[1]["czaszka"] = "biala"                      # Ucho (na polu bota, widmo) ma białą czaszkę
l[3]["czaszka"] = "czerwona"                    # Prolvldeus (para (1,0) z Harleyqueen)
s = Swiat(l)
b = zrob(s)
lst = b.stwory()
b.ostatnie_stwory = lst
czasz = sorted(m["nazwa"] for m in lst if b._pk_czaszka(m))
sprawdz("C2 _pk_czaszka (PK_OBRONA) widzi obie czaszki: i na polu bota, i w parze", czasz == ["Prolvldeus", "Ucho"], czasz)
groz = sorted(m["nazwa"] for m in b._grozni_w_zasiegu(lst, POZ))
sprawdz("C3 _grozni_w_zasiegu (GRACZ/pościg/loot) widzi oboje groźnych", groz == ["Prolvldeus", "Ucho"], groz)
sprawdz("C4 groźny z pary jest reprezentantem i zostaje w ocenie graczy (Prolvldeus), Harleyqueen = duplikat",
        oznaczone(lst).get("Harleyqueen") == "duplikat_pola" and "Prolvldeus" not in oznaczone(lst), oznaczone(lst))
s = Swiat(l)
b = zrob(s)
b.tick()
sprawdz("C5 tick z czaszkami na polu bota/w parze: PK albo GRACZ (reakcja jest), nie 'gramy dalej'",
        b.pk_stan is not None or b.stan == "GRACZ", (b.pk_stan, b.stan))

# stan dla modelu (mozg): odczyt_stworow trzyma listę w całości
s = Swiat(wiersz("19:42:23"))
bm = zrob(s, mozg.CavebotMozgu)
lm = bm.stwory()
sprawdz("C6 CavebotMozgu.stwory/odczyt_stworow (czaszki, GM, zbuduj_stan) = 7 wpisów, nic nie usunięte",
        len(lm) == 7 and len(bm.odczyt_stworow[1]) == 7 and "Ucho" in nazwy(bm.odczyt_stworow[1]), nazwy(bm.odczyt_stworow[1]))
src = Path(cavebot.__file__).read_text()
pk_zrodlo = src[src.index("    def _pk_tick_u"):src.index("    def _pk_czaszka") if src.index("    def _pk_czaszka") > src.index("    def _pk_tick_u") else None]
sprawdz("C7 ścieżka PK (_pk_tick_u) nie używa bez_widm", "bez_widm" not in pk_zrodlo)
mz_zrodlo = Path(mozg.__file__).read_text()
sprawdz("C8 mozg.py (GM, czaszki, stan modelu) nie filtruje widm", "bez_widm" not in mz_zrodlo)

# =========================================================================================================
# D. serwis (AkcjeZywe._stwory / pole_zajete / idz_pewnie)
# =========================================================================================================


class FakeBot:
    def __init__(self, lista):
        self.lista = lista

    def _zapytaj_surowe(self, z):
        assert z == {"cmd": "stwory"}, z
        return {"stwory": [dict(m) for m in self.lista]}


def akcje_zywe(lista):
    a = serwis_akcje.AkcjeZywe.__new__(serwis_akcje.AkcjeZywe)
    a.nick, a.log, a._bot = "Mastafian", LOGI.append, FakeBot(lista)
    return a


a = akcje_zywe(wiersz("19:42:23"))
sprawdz("D1 serwis: pole bota nie jest 'zajęte' przez Ucho (stoisko = pole, na którym stoimy)", not a.pole_zajete(POZ), a._stwory())
sprawdz("D2 serwis: pole reprezentanta tłumu (x+1,y) nadal zajęte", a.pole_zajete((POZ[0] + 1, POZ[1], POZ[2])))
sprawdz("D3 serwis: _stwory() zwraca wszystkie 7 wpisów (znacznik, nie usunięcie)", len(a._stwory()) == 7)
l = wiersz("19:42:23")
l[1]["z"] = 6
a = akcje_zywe(l)
sprawdz("D4 piętra: gracz z z6 na polu bota nie zajmuje pola z7", not a.pole_zajete(POZ))
l = wiersz("19:42:23")
l[1]["z"] = 7
l[2]["z"] = 6
a = akcje_zywe([l[0], l[2]])
sprawdz("D5 piętra: sam gracz z innego z na polu (x+1,y) nie zajmuje go na tym piętrze", not a.pole_zajete((POZ[0] + 1, POZ[1], POZ[2])))
os_ = _os.environ.get("RETRONIC_STWORY_WIDMA")
_os.environ["RETRONIC_STWORY_WIDMA"] = "0"
a = akcje_zywe(wiersz("19:42:23"))
sprawdz("D6 RETRONIC_STWORY_WIDMA=0: serwis ma stare zachowanie (pole bota 'zajęte' przez Ucho, bez znaczników)",
        a.pole_zajete(POZ) and not oznaczone(a._stwory()))
if os_ is None:
    del _os.environ["RETRONIC_STWORY_WIDMA"]
else:
    _os.environ["RETRONIC_STWORY_WIDMA"] = os_


class Zegar:
    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
        return self.t

    def time(self):
        return self.t

    def sleep(self, x):
        self.t += x


ZEGAR = Zegar()
S.time = ZEGAR


class Plac:
    def flagi(self, x, y, z):
        return 1 if 0 <= x < 40 and 0 <= y < 30 else 0

    def pole(self, x, y, z):
        return (self.flagi(x, y, z), 0, 10) if self.flagi(x, y, z) else None


class Chodzik:
    """Atrapa Postac: krok = przesunięcie o pole, bez blokad (do sprawdzenia, które pola omija plan)."""
    def __init__(self, poz):
        self.p = list(poz)
        self.trasa = [tuple(poz[:2])]

    def pozycja(self):
        ZEGAR.t += 0.004
        return tuple(self.p)

    def krok(self, klawisz):
        d = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}[klawisz]
        self.p[0] += d[0]
        self.p[1] += d[1]
        self.trasa.append((self.p[0], self.p[1]))
        ZEGAR.t += 0.6
        return tuple(self.p)


# trzech graczy na jednym polu (22,10) na prostej drodze (20,10) -> (25,10): plan omija to pole (reprezentant dalej blokuje)
stos = [{"id": 0x10000200 + i, "nazwa": n, "gracz": True, "x": 22, "y": 10, "z": 7, "hp": 100}
        for i, n in enumerate(("Ucho", "Patriko", "Harleyqueen"))]
ja = {"id": 0x10000001, "nazwa": "Mastafian", "gracz": True, "x": 20, "y": 10, "z": 7, "hp": 100}
a = akcje_zywe([ja] + stos)
ch = Chodzik((20, 10, 7))
random_state = random.getstate()
random.seed(3)
wynik = S.idz_pewnie(ch, Plac(), a, (25, 10, 7), 0, maks_s=60.0, log=lambda *x: None, stan={})
random.setstate(random_state)
sprawdz("D7 stos trzech graczy na (22,10): marsz dochodzi do celu i nie wchodzi na to pole (reprezentant blokuje)",
        wynik is True and (22, 10) not in ch.trasa and ch.trasa[-1] == (25, 10), (wynik, ch.trasa))

# =========================================================================================================
# E. rdzeń: zdublowane ID zostawia ślad (diagnostyka widm), zachowanie wyboru bez zmian
# =========================================================================================================


def wpisz(bufor, idx, ident, nazwa, x, y, z=7, hp=100):
    n = (idx + 5) * 4
    bufor[idx * 4: idx * 4 + 16] = struct.pack("<4f", 1, 1, 1, 1)
    bufor[idx * 4 + 16: idx * 4 + 20] = struct.pack("<I", ident)
    nb = nazwa.encode() + b"\0"
    bufor[n: n + len(nb)] = nb
    bufor[n + 0x10: n + 0x18] = struct.pack("<II", len(nazwa), 15)
    bufor[n + rdzen.POZYCJA_STWORA: n + rdzen.POZYCJA_STWORA + 9] = struct.pack("<IIB", x, y, z)
    bufor[n + rdzen.HP_STWORA] = hp


class Atrapa(rdzen.Pamiec):
    def __init__(s, regionow=4):
        super().__init__()
        s.reg = [(0x100000 * (i + 1), 0x100000 * (i + 1) + 0x10000) for i in range(regionow)]
        s.dane = {r: bytearray(0x10000) for r in s.reg}
        s.mem = object()

    def regiony(s):
        return list(s.reg)

    def czytaj(s, adres, dl):
        for (a_, b_), d in s.dane.items():
            if a_ == adres:
                return bytes(d[:dl])
        return b""


p = Atrapa()
wpisz(p.dane[p.reg[0]], 100, 0x10000042, "Ucho", 33167, 31811)          # zwolniony, nieprzepisany obiekt (stare miejsce)
wpisz(p.dane[p.reg[2]], 100, 0x10000042, "Ucho", 33168, 31811)          # żywy obiekt tego samego ID
wpisz(p.dane[p.reg[1]], 50, 0x10000043, "Patriko", 33170, 31811)
lst, _info = p.stwory_info(maks_wiek=0)
ucho = [s for s in lst if s["nazwa"] == "Ucho"]
sprawdz("E1 rdzeń: to samo ID w dwóch miejscach pamięci = jeden wpis (jak dotąd), wygrywa ostatni skan",
        len(lst) == 2 and len(ucho) == 1 and (ucho[0]["x"], ucho[0]["y"]) == (33168, 31811), lst)
sprawdz("E2 rdzeń: wpis ma opcjonalne pole `kopie` z pozycją i adresem pominiętej kopii",
        ucho and ucho[0].get("kopie") and ucho[0]["kopie"][0][:3] == [33167, 31811, 7], ucho)
sprawdz("E3 rdzeń: wpis bez zdublowanego ID nie ma pola `kopie` (kontrakt gniazda bez zmian)",
        all("kopie" not in s for s in lst if s["nazwa"] == "Patriko"))

# =========================================================================================================
# F. własny wpis przy duplikacie nazwy (relog): 19.10 20:14 serwis planował z fałszywego piętra
# =========================================================================================================
import contextlib  # noqa: E402
import io  # noqa: E402

STARY = {"id": 268555116, "nazwa": "Mastafian", "gracz": True, "x": 33165, "y": 31826, "z": 6, "hp": 100, "kierunek": 3,
         "adres": "0xdce51b8"}
NOWY = {"id": 268653019, "nazwa": "Mastafian", "gracz": True, "x": 33165, "y": 31826, "z": 7, "hp": 100, "kierunek": 2,
        "adres": "0x645bd80"}
# rdzeń podał blok statystyk przy STARYM wpisie (blok też bywa widmem), HP równe: stary kod brał najbliższy adres = widmo
G_STARY_BLOK = {"hp": 200, "max_hp": 200, "adres": hex(int(STARY["adres"], 16) + 0x470)}
sprawdz("F1 20:14: dwa wpisy Mastafian, HP równe, blok przy starym: wybrany wpis o wyższym id (z7), nie widmo z6",
        (bot.wybierz_wlasny([STARY, NOWY], G_STARY_BLOK) or {}).get("id") == NOWY["id"],
        bot.wybierz_wlasny([STARY, NOWY], G_STARY_BLOK))
sprawdz("F1b ta sama kolejność odwrócona daje ten sam wybór", (bot.wybierz_wlasny([NOWY, STARY], G_STARY_BLOK) or {}).get("id") == NOWY["id"])
STARY2 = dict(STARY, id=268479676, adres="0xd6cf6a0", z=8)
sprawdz("F2 14:57: id 268479676 (blok) kontra 268555116 (ruch potwierdził) -> wyższe id",
        (bot.wybierz_wlasny([STARY2, dict(STARY, z=8)], {"hp": 200, "max_hp": 200, "adres": "0xd6cf9a0"}) or {}).get("id") == 268555116)
ruch = {}
t0 = 100.0
bot.sledz_ruch(ruch, [STARY, NOWY], t0)
bot.sledz_ruch(ruch, [dict(STARY, x=STARY["x"] + 1), NOWY], t0 + 2)
sprawdz("F3 dowód ruchu wygrywa z id (wpis, który się ruszył, jest żywy)",
        (bot.wybierz_wlasny([dict(STARY, x=STARY["x"] + 1), NOWY], G_STARY_BLOK, ruch, t0 + 2) or {}).get("id") == STARY["id"])
sprawdz("F4 HP zgodne z blokiem zawęża pulę przed id (jak dotąd)",
        (bot.wybierz_wlasny([dict(NOWY, hp=100), dict(STARY, hp=60)], {"hp": 60, "max_hp": 100, "adres": "0x1"}) or {}).get("id") == STARY["id"])
sprawdz("F5 bez id i bez zgodnego HP: najbliższy adres bloku (jak dotąd)",
        (bot.wybierz_wlasny([dict(STARY, id=None), dict(NOWY, id=None)], G_STARY_BLOK) or {}).get("adres") == STARY["adres"])

# end-to-end: bot.wlasny_wpis/_pozycja_wlasna z atrapą gniazda
_zap0 = bot._zapytaj_surowe


def gniazdo(z):
    if z["cmd"] == "stwory":
        return {"stwory": [dict(STARY), dict(NOWY)]}
    if z["cmd"] == "gracz":
        return {"gracz": dict(G_STARY_BLOK)}
    if z["cmd"] == "stwor":
        w = STARY if z["id"] == STARY["id"] else NOWY
        return {"stwor": {"id": w["id"], "x": w["x"], "y": w["y"], "z": w["z"], "hp": w["hp"]}}
    raise AssertionError(z)


bot._zapytaj_surowe = gniazdo
bot._wlasny.update(nazwa=None, t=float("-inf"), wpis=None, duplikat=None)
bot._ruch.clear()
blad = io.StringIO()
with contextlib.redirect_stderr(blad):
    poz = bot._pozycja_wlasna("Mastafian")
bot._zapytaj_surowe = _zap0
bot._wlasny.update(nazwa=None, t=float("-inf"), wpis=None, duplikat=None)
bot._ruch.clear()
sprawdz("F6 end-to-end: pozycja własna z wpisu o wyższym id (z7), nie z widma (z6)", poz == {"x": 33165, "y": 31826, "z": 7}, poz)
sprawdz("F7 ostrzeżenie w logu: wpisy na różnych piętrach, wybór bez dowodu ruchu", "UWAGA" in blad.getvalue() and "z6" in blad.getvalue()
        and "z7" in blad.getvalue(), blad.getvalue())

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
