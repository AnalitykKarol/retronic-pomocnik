import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""Test offline: jedzenie ze zwłok, stosy po ID (sprawdzenie w pamięci), scalanie stosów, zjedz() z pamięci.
Atrapy myszy, zrzutu, otwierania i komendy "kontenery". Nic nie trafia do gry.
Uruchom: python3 -I test_loot_jedzenie.py"""
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
stan = {"krok": 0, "obrazy": [], "pamiec": [], "ctrl_zmienia": True}


class FMysz:
    """Przeciągnięcie zawsze zmienia stan gry; Ctrl+klik (Use) tylko gdy ctrl_zmienia (nie najedzony)."""
    ekran = ":99"
    def __enter__(s): return s
    def __exit__(s, *a): pass
    def przeciagnij(s, *a, **k):
        zdarzenia.append(("drag", a))
        stan["krok"] += 1
    def lewy(s, *a, **k):
        ctrl = k.get("modyfikator") == "Control_L"
        zdarzenia.append(("use" if ctrl else "lewy", a))
        if ctrl and stan["ctrl_zmienia"]:
            stan["krok"] += 1


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


def ustaw(obrazy, pamiec, ctrl_zmienia=True):
    zdarzenia.clear(); logi.clear()
    stan.update(krok=0, obrazy=obrazy, pamiec=pamiec, ctrl_zmienia=ctrl_zmienia)
    loot._plan_teraz.ostatni_powod = None
    loot.zjedz.ostatni_powod = None


def scenariusz(obrazy, pamiec, lista=("gold coin", "cheese", "meat", "ham"), ctrl_zmienia=True):
    ustaw(obrazy, pamiec, ctrl_zmienia)
    return loot.zbierz_szczegoly((101, 100, 7), (100, 100, 7), lista, log=log)


def rodzaje(*r):
    return [z for z in zdarzenia if z[0] in r]


# zwloki.png: Bag (sloty 0-1 zajęte), Dead rat (sloty 0-1 zajęte). Warianty z przeniesionymi ikonami.
A = Image.open(SCR + "zwloki.png").convert("RGB")
bag_o, zw_o = loot.znajdz_okna(A)
pusty = A.crop(zw_o.sloty[3].wnetrze())
ikona = A.crop(zw_o.sloty[1].wnetrze())


def wariant(puste=(), pelne=()):
    o = A.copy()
    for s in puste:
        o.paste(pusty, s.wnetrze()[:2])
    for s in pelne:
        o.paste(ikona, s.wnetrze()[:2])
    return o


F = wariant(puste=[zw_o.sloty[1]])                          # zwłoki: tylko slot 0
G = wariant(puste=zw_o.sloty[:2])                           # zwłoki puste
E = wariant(puste=[zw_o.sloty[1]], pelne=[bag_o.sloty[2]])  # zwłoki slot 0, plecak 0-2
H = wariant(puste=[bag_o.sloty[1]])                         # plecak tylko slot 0
k = loot.kont
bag = k(1, "bag", 2853, 8, (3031, 85), (3003, 1))

# --- J1: nie najedzony: ser x2 zjedzony ze zwłok (dwa Use), potem gold na stos -----------------------
w = scenariusz([A, A, F, G],
               [[k(0, "dead rat", 3994, 5, (3031, 3), (3607, 2)), bag],
                [k(0, "dead rat", 3994, 5, (3031, 3), (3607, 1)), bag],
                [k(0, "dead rat", 3994, 5, (3031, 3)), bag],
                [k(0, "dead rat", 3994, 5), k(1, "bag", 2853, 8, (3031, 88), (3003, 1))]])
uzycia = rodzaje("use")
sprawdz(f"J1: dwa Use na serze w zwłokach (slot 1) {uzycia}",
        len(uzycia) == 2 and all(u[1] == zw_o.sloty[1].srodek for u in uzycia))
sprawdz(f"J1: zjedzono {w['zjedzono']}, log 'zjedzono ze zwłok: cheese'",
        w["zjedzono"] == ["cheese", "cheese"] and logi.count("loot: zjedzono ze zwłok: cheese") == 2)
dragi = [z[1] for z in rodzaje("drag")]
sprawdz(f"J1: potem gold na stos w plecaku {dragi}",
        dragi == [(*zw_o.sloty[0].srodek, *bag_o.sloty[0].srodek)] and w["ilosci"] == {"gold coin": 3})
sprawdz("J1: kolejność: Use, Use, przeciągnięcie, zamknięcie",
        [z[0] for z in zdarzenia] == ["otworz", "use", "use", "drag", "lewy"])

# --- J2: najedzony: Use nic nie zmienia -> ser idzie na stos sera w plecaku -----------------------
w = scenariusz([A, F],
               [[k(0, "dead rat", 3994, 5, (3031, 3), (3607, 1)), k(1, "bag", 2853, 8, (3607, 2), (3003, 1))],
                [k(0, "dead rat", 3994, 5, (3031, 3)), k(1, "bag", 2853, 8, (3607, 3), (3003, 1))]],
               lista=("cheese",), ctrl_zmienia=False)
dragi = [z[1] for z in rodzaje("drag")]
sprawdz(f"J2: jeden Use, log 'najedzony' {len(rodzaje('use'))}",
        len(rodzaje("use")) == 1 and any("najedzony" in l for l in logi) and w["zjedzono"] == [])
sprawdz(f"J2: ser ze zwłok na stos sera (slot 0 plecaka) {dragi}",
        dragi == [(*zw_o.sloty[1].srodek, *bag_o.sloty[0].srodek)] and w["ilosci"] == {"cheese": 1})
sprawdz("J2: w pamięci się zgadza (bez 'niezgodne' i 'nie łączy się')",
        not any("niezgodne" in l or "nie łączy" in l for l in logi))

# --- J3: przedmiot nieznany (ID 9001) upuszczony na swój "stos" robi osobny slot -> niestosowy -----
w = scenariusz([A, E],
               [[k(0, "dead rat", 3994, 5, (3031, 3), (9001, 1)), k(1, "bag", 2853, 8, (9001, 1), (3003, 1))],
                [k(0, "dead rat", 3994, 5, (3031, 3)), k(1, "bag", 2853, 8, (9001, 1), (3003, 1), (9001, 1))]],
               lista=(9001,))
sprawdz(f"J3: na stos (slot 0), potem nauka: 9001 w NIESTOSOWE_ID",
        [z[1] for z in rodzaje("drag")] == [(*zw_o.sloty[1].srodek, *bag_o.sloty[0].srodek)]
        and 9001 in loot.NIESTOSOWE_ID and any("nie łączy się" in l for l in logi))
p = loot.plan(A, (9001,))
sprawdz(f"J3: następnym razem 9001 na wolny slot {p['cel']}", p["cel"] is p["okna"][0].sloty[2])
loot.NIESTOSOWE_ID.discard(9001)

# --- J4: ilość w plecaku nie zgadza się z tym, co ubyło ze zwłok -> log ---------------------------
w = scenariusz([A, F],
               [[k(0, "dead rat", 3994, 5, (3031, 3), (3607, 1)), bag],
                [k(0, "dead rat", 3994, 5, (3031, 3)), bag]],
               lista=("cheese",), ctrl_zmienia=False)
sprawdz("J4: log 'niezgodne' (ser zniknął ze zwłok, w plecaku nie przybyło)",
        any("cheese: ze zwłok -1, w plecaku +0 (niezgodne)" in l for l in logi))

# --- J5: scalanie: dwa sery po 1 w plecaku -> slot 1 na slot 0 --------------------------------------
w = scenariusz([A, H],
               [[k(0, "dead rat", 3994, 5, (3031, 3), (3003, 1)), k(1, "bag", 2853, 8, (3607, 1), (3607, 1))],
                [k(0, "dead rat", 3994, 5, (3031, 3), (3003, 1)), k(1, "bag", 2853, 8, (3607, 2))]],
               lista=("meat",))
dragi = [z[1] for z in rodzaje("drag")]
sprawdz(f"J5: scalenie sera w plecaku {dragi}",
        dragi == [(*bag_o.sloty[1].srodek, *bag_o.sloty[0].srodek)] and "loot: scalono stos cheese w plecaku" in logi)
# scalenie nie wychodzi -> jedna próba, potem ID pomijane
w = scenariusz([A], [[k(0, "dead rat", 3994, 5, (3031, 3), (3003, 1)), k(1, "bag", 2853, 8, (3607, 1), (3607, 1))]],
               lista=("meat",))
w = scenariusz([A], [[k(0, "dead rat", 3994, 5, (3031, 3), (3003, 1)), k(1, "bag", 2853, 8, (3607, 1), (3607, 1))]],
               lista=("meat",))
sprawdz("J5: nieudane scalenie nie jest powtarzane przy kolejnych zwłokach", not rodzaje("drag"))
loot.NIEUDANE_SCALENIA.clear()

# --- Z1: zjedz() z pamięci: meat przed cheese, sprawdzenie ubytku ----------------------------------
zw = k(0, "dead rat", 3994, 5, (3031, 3), (3607, 1))
ustaw([A, H, H], [[zw, k(1, "bag", 2853, 8, (3607, 3), (3577, 1))],
                  [zw, k(1, "bag", 2853, 8, (3607, 3))],
                  [zw, k(1, "bag", 2853, 8, (3607, 2))]])
z = loot.zjedz(ile=2, log=log)
uzycia = [u[1] for u in rodzaje("use")]
sprawdz(f"Z1: zjedzone {z}, Use na meat (slot 1), potem cheese (slot 0)",
        z == ["meat", "cheese"] and uzycia == [bag_o.sloty[1].srodek, bag_o.sloty[0].srodek])
# --- Z2: najedzony
ustaw([A], [[zw, k(1, "bag", 2853, 8, (3607, 3), (3577, 1))]], ctrl_zmienia=False)
z = loot.zjedz(ile=2, log=log)
sprawdz(f"Z2: najedzony: jedno Use, nic nie zjedzone {z}",
        z == [] and len(rodzaje("use")) == 1 and any("najedzony" in l for l in logi))
# --- Z3: brak jedzenia w plecaku
ustaw([A], [[zw, bag]])
z = loot.zjedz(ile=2, log=log)
sprawdz("Z3: brak jedzenia: bez kliknięć", z == [] and not zdarzenia and "jedzenie: brak jedzenia w plecaku" in logi)
# --- Z4: pamięć nie działa -> obrazek (z6.png: gold, torch, cheese, meat)
Z6 = Image.open(SCR + "z6.png").convert("RGB")
ustaw([Z6], [ConnectionRefusedError("brak gniazda")])
z = loot.zjedz(ile=2, log=log)
o6 = loot.znajdz_okna(Z6)[0]
sprawdz(f"Z4: fallback obrazkowy: {z}, Use na meat (slot 3)",
        z == ["meat", "meat"] and [u[1] for u in rodzaje("use")] == [o6.sloty[3].srodek] * 2
        and sum("szukam obrazkiem" in l for l in logi) == 1)
sprawdz("nigdzie klawiszy", not any(z[0] == "klawisz" for z in zdarzenia))

print("WYNIK:", "OK" if ok else "BŁĄD")
sys.exit(0 if ok else 1)
