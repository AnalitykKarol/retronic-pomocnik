import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""Test zbierz_szczegoly() offline: atrapy myszy, zrzutu, otwierania i odczytu pamięci (komenda "kontenery").
Nic nie trafia do gry. Uruchom: python3 -I test_loot_zbierz.py"""
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from PIL import Image
import ekran, loot, klawisz_x11

import os
SCR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dane") + os.sep

_BRAK = [n for n in ("zwloki.png", "atrapa_zwloki.png", "z6.png") if not os.path.exists(SCR + n)]
if _BRAK:
    print("POMINIĘTO: brak zrzutów testowych w", SCR, _BRAK)
    sys.exit(2)
zdarzenia = []
stan = {"krok": 0, "obrazy": [], "pamiec": []}


class FMysz:
    ekran = ":99"
    def __enter__(s): return s
    def __exit__(s, *a): pass
    def przeciagnij(s, *a, **k):
        zdarzenia.append(("drag", a))
        stan["krok"] += 1          # po przeciągnięciu gra pokazuje następny stan
    def lewy(s, *a, **k): zdarzenia.append(("lewy", a))


def biezacy(lista):
    return lista[min(stan["krok"], len(lista) - 1)]


def atrapa_pamieci(z):
    p = biezacy(stan["pamiec"])
    if isinstance(p, Exception):
        raise p
    return {"kontenery": p}


ekran.otworz = lambda dx, dy: zdarzenia.append(("otworz", dx, dy))
ekran.Mysz = FMysz
ekran.zrzut = lambda: biezacy(stan["obrazy"])
ekran._rozmiar_ekranu = lambda e=None: stan["obrazy"][0].size
klawisz_x11.wyslij = lambda *a, **k: zdarzenia.append(("klawisz", a))
loot._pauza = lambda a=0, b=0: None
loot.zapisz_nieznany = lambda *a, **k: None
loot._zapytaj = atrapa_pamieci
logi = []
log = lambda s: (logi.append(s), print("   log:", s))

ok = True


def sprawdz(opis, warunek):
    global ok
    print(("OK    " if warunek else "BŁĄD "), opis)
    ok &= bool(warunek)


def scenariusz(obrazy, pamiec, lista=loot.DO_ZEBRANIA):
    zdarzenia.clear(); logi.clear()
    stan.update(krok=0, obrazy=obrazy, pamiec=pamiec)
    loot._plan_teraz.ostatni_powod = None
    return loot.zbierz_szczegoly((101, 100, 7), (100, 100, 7), lista, log=log)


# --- 1. dawny scenariusz: atrapa z obrazka, pamięć nie działa (fallback) ------------------
atrapa = Image.open(SCR + "atrapa_zwloki.png").convert("RGB")
w = scenariusz([atrapa], [ConnectionRefusedError("brak gniazda")])
print(w, zdarzenia)
sprawdz("fallback: otwarcie, przeciągnięcie, zamknięcie okna",
        zdarzenia[0] == ("otworz", 1, 0) and zdarzenia[1][0] == "drag" and zdarzenia[-1][0] == "lewy")
sprawdz("fallback: plan z obrazka i log powodu", w["zrodlo"] == "obraz" and any("rozpoznaję obrazkiem" in l for l in logi))
sprawdz("fallback: bez klawiszy", not any(z[0] == "klawisz" for z in zdarzenia))

# --- 2. pamięć: zwłoki [gold 3, cheese], Bag [gold 85, rope] -> gold na stos, ser na wolny slot -----
A = Image.open(SCR + "zwloki.png").convert("RGB")
okna = loot.znajdz_okna(A)
bag_o, zw_o = okna
pusty = A.crop(zw_o.sloty[3].wnetrze())


def ikona(o, s):
    return A.crop(s.wnetrze())


B = A.copy()                                               # gold zniknął ze zwłok, ser przesunął się na slot 0
B.paste(ikona(zw_o, zw_o.sloty[1]), zw_o.sloty[0].wnetrze()[:2])
B.paste(pusty, zw_o.sloty[1].wnetrze()[:2])
C = B.copy()                                               # ser przeszedł na slot 2 plecaka
C.paste(ikona(zw_o, zw_o.sloty[1]), bag_o.sloty[2].wnetrze()[:2])
C.paste(pusty, zw_o.sloty[0].wnetrze()[:2])
k = loot.kont
pA = [k(0, "dead rat", 3994, 5, (3031, 3), (3607, 1)), k(1, "bag", 2853, 8, (3031, 85), (3003, 1))]
pB = [k(0, "dead rat", 3994, 5, (3607, 1)), k(1, "bag", 2853, 8, (3031, 88), (3003, 1))]
pC = [k(0, "dead rat", 3994, 5), k(1, "bag", 2853, 8, (3031, 88), (3003, 1), (3607, 1))]
w = scenariusz([A, B, C], [pA, pB, pC])
print(w, zdarzenia)
dragi = [z[1] for z in zdarzenia if z[0] == "drag"]
sprawdz("pamięć: dwa przeciągnięcia", len(dragi) == 2)
sprawdz("pamięć: gold ze slotu 0 zwłok na stos w slocie 0 plecaka",
        dragi and dragi[0] == (*zw_o.sloty[0].srodek, *bag_o.sloty[0].srodek))
sprawdz("pamięć: ser ze slotu 0 zwłok (po przesunięciu) na wolny slot 2 plecaka",
        len(dragi) > 1 and dragi[1] == (*zw_o.sloty[0].srodek, *bag_o.sloty[2].srodek))
sprawdz(f"pamięć: ilości {w['ilosci']}", w["ilosci"] == {"gold coin": 3, "cheese": 1} and w["zrodlo"] == "pamiec")
sprawdz("pamięć: log 'zebrano gold coin +3' i podsumowanie łupu",
        "loot: zebrano gold coin +3" in logi and any(l.startswith("loot: łup gold coin +3, cheese +1") for l in logi))
sprawdz("pamięć: okno zwłok zamknięte na końcu", zdarzenia[-1][0] == "lewy" and w["status"] == "ok")

# --- 3. pamięć bez zmian po przeciągnięciu -> "nie przeszedł", jedno przeciągnięcie ----------
w = scenariusz([A], [pA])
sprawdz("nie przeszedł: przerwa po jednym ruchu",
        sum(z[0] == "drag" for z in zdarzenia) == 1 and any("nie przeszedł" in l for l in logi) and not w["ilosci"])

# --- 4. pełny plecak według pamięci (8/8, stos gold 100) -----------------------------------
D = A.copy()
for s in bag_o.sloty[2:]:
    D.paste(ikona(bag_o, bag_o.sloty[1]), s.wnetrze()[:2])
pD = [pA[0], k(1, "bag", 2853, 8, (3031, 100), *[(3003, 1)] * 7)]
w = scenariusz([D], [pD])
sprawdz(f"pełny plecak: status {w['status']}, bez przeciągania",
        w["status"] == "pelny_plecak" and not any(z[0] == "drag" for z in zdarzenia))

# --- 5. lista po ID: tylko ser ---------------------------------------------------------------
E = A.copy()                                               # ser przeszedł na slot 2, gold został w zwłokach
E.paste(ikona(zw_o, zw_o.sloty[1]), bag_o.sloty[2].wnetrze()[:2])
E.paste(pusty, zw_o.sloty[1].wnetrze()[:2])
w = scenariusz([A, E], [pA, [k(0, "dead rat", 3994, 5, (3031, 3)), pC[1]]], lista=(3607,))
dragi = [z[1] for z in zdarzenia if z[0] == "drag"]
sprawdz(f"lista po ID: tylko ser, {w['ilosci']}, zostało {w['zostalo']}",
        len(dragi) == 1 and dragi[0][:2] == zw_o.sloty[1].srodek and w["ilosci"] == {"cheese": 1}
        and w["zostalo"] == ["gold coin"] and w["zrodlo"] == "pamiec" and not any("obrazkiem" in l for l in logi))

# --- 6. daleko -------------------------------------------------------------------------------
zdarzenia.clear()
sprawdz("daleko: bez akcji", loot.zbierz((103, 100, 7), (100, 100, 7)) == "daleko" and not zdarzenia)
sprawdz("nigdzie klawiszy", not any(z[0] == "klawisz" for z in zdarzenia))

print("WYNIK:", "OK" if ok else "BŁĄD")
sys.exit(0 if ok else 1)
