import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""Test offline lootu w walce (loot.krok_w_walce): atomowe kroki, brak klików poza Ctrl+klikiem w zwłoki
i przeciągnięciem, odmowy bez inputu. Atrapy myszy, pamięci i planu. Uruchom: python3 -I test_loot_w_walce.py"""
import os
import sys
import types
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ekran, loot

ok = []
def sprawdz(opis, warunek, info=""):
    print(("OK    " if warunek else "BŁĄD "), opis, info if not warunek else "")
    ok.append(bool(warunek))

zdarz = []            # kolejność zdarzeń inputu: ("otworz", dx, dy) / ("przeciagnij",) / ("zamknij",)
swiat = {"otwarte": False, "stwory": [], "zwloki_sztuk": 3, "plecak_sztuk": 0, "ser": 0, "najedzony": False}
Z = lambda sztuk: loot.kont(2, "dead rat", 3994, 5, *([(3031, sztuk)] if sztuk else []),
                            *([(3607, swiat["ser"])] if swiat["ser"] else []))
def kontenery():
    lista = [loot.kont(1, "bag", 2853, 8)]
    if swiat["otwarte"]:
        lista.append(Z(swiat["zwloki_sztuk"]))
    return lista
def zapytaj(z):
    if z["cmd"] == "kontenery":
        return {"kontenery": kontenery()}
    if z["cmd"] == "stwory":
        return {"stwory": swiat["stwory"]}
    raise AssertionError(z)

class Slot:
    def __init__(s, x, y): s.x, s.y = x, y
    def srodek(s): return (s.x, s.y)
Slot.srodek = property(lambda s: (s.x, s.y))
def plan_z_pamieci(*a, **k):
    zw = kontenery()[-1] if swiat["otwarte"] else None
    if zw is None:
        return None, {"zwloki": None}
    sztuk = swiat["zwloki_sztuk"]
    p = {"zwloki": types.SimpleNamespace(kontener=zw, przycisk_zamkniecia=(5, 5)), "zrodlo": "pamiec",
         "plecak": types.SimpleNamespace(kontener=None), "kontenery": kontenery(), "kontener_zwlok": zw,
         "przedmiot": (Slot(10, 10), "gold coin") if sztuk else None, "przedmiot_id": (3031, sztuk) if sztuk else None,
         "cel": Slot(50, 50), "cel_stos": None,
         "jedzenie": (Slot(20, 20), "cheese", 3607) if swiat["ser"] else None, "pamiec": None, "zostalo": [], "nieznane": 0,
         "ukryte": [], "nauczone": []}
    return None, p

class Mysz:
    ekran = None
    def __enter__(s): return s
    def __exit__(s, *a): pass
    def przeciagnij(s, *a, **k):
        zdarz.append(("przeciagnij",))
        swiat["zwloki_sztuk"] = 0
    def lewy(s, *a, **k):
        if k.get("modyfikator") == "Control_L":
            zdarz.append(("jedz",))
            if not swiat["najedzony"]:
                swiat["ser"] = max(0, swiat["ser"] - 1)
            return
        zdarz.append(("zamknij",))
        if not swiat.get("okno_uparte"):
            swiat["otwarte"] = False

def otworz(dx, dy):
    zdarz.append(("otworz", dx, dy))
    swiat["otwarte"] = True

def zamknij(mysz, p, pole, klucz, log):
    zdarz.append(("zamknij",)); swiat["otwarte"] = False
    return True

ekran.otworz = otworz
ekran.Mysz = Mysz
loot._zapytaj = zapytaj
loot._plan_teraz = lambda mysz, lista, log: plan_z_pamieci()
loot._zamknij_zwloki = zamknij
loot._okno_ilosci_ok = lambda *a, **kw: None
loot._pauza = lambda a=0, b=0: None
loot._pozycja_gracza = lambda: (100, 100, 7)
logi = []
t = [0.0]
zegar = lambda: t[0]

def reset(**kw):
    zdarz.clear(); logi.clear()
    swiat.update(otwarte=False, stwory=[], zwloki_sztuk=3, ser=0, najedzony=False)
    swiat.update(kw)
    t[0] = 0.0

def krok(stan, zw=(101, 100, 7), gracz=(100, 100, 7)):
    return loot.krok_w_walce(stan, zw, gracz, log=logi.append, zegar=zegar)

# 1. pełny cykl: otwarcie -> czekanie -> plan -> przenieś -> weryfikacja -> zamknij; po jednym wejściu na wywołanie
reset(); st = {}
wyniki = []
for _ in range(12):
    wyniki.append(krok(st))
    t[0] += 0.1
    if wyniki[-1][0] != "kontynuuj":
        break
wejscia = [z for z in zdarz]
sprawdz("1 cykl kończy się 'gotowe'", wyniki[-1] == ("gotowe", "ok"), wyniki)
sprawdz("1a dokładnie: Ctrl+klik w pole (1,0), jedno przeciągnięcie, zamknięcie",
        wejscia == [("otworz", 1, 0), ("przeciagnij",), ("zamknij",)], wejscia)
sprawdz("1b każde wywołanie to najwyżej jedno wejście (klik/przeciągnięcie/zamknięcie)", len(wyniki) >= 5, len(wyniki))
sprawdz("1c zebrano 3 gold coin w stanie", st["ilosci"].get("gold coin") == 3, st.get("ilosci"))

# 2. odmowy bez żadnego inputu
reset(); r = krok({}, zw=(105, 100, 7))
sprawdz("2a daleko: odmowa bez inputu", r == ("przerwane", "daleko") and zdarz == [], (r, zdarz))
reset(); r = krok({}, zw=(100, 100, 7))
sprawdz("2b stoimy na zwłokach: odmowa bez inputu", r == ("przerwane", "na_zwlokach") and zdarz == [], (r, zdarz))
# 2c. okno zwłok już otwarte (zostawione przez pilne przerwanie): zamykamy je X-em i ponawiamy w następnym kroku
reset(otwarte=True); st = {}; r = krok(st)
sprawdz("2c okno już otwarte: zamknięcie X-em zamiast odmowy (bez Ctrl+kliku w zwłoki)",
        r == ("kontynuuj", "zamkniecie_obcego") and zdarz == [("zamknij",)], (r, zdarz))
r = krok(st)
sprawdz("2c2 następny krok: okno zamknięte, normalne otwarcie zwłok", r == ("kontynuuj", "otwarcie") and zdarz[-1] == ("otworz", 1, 0), (r, zdarz))
reset(otwarte=True, okno_uparte=True); st = {}
r1 = krok(st); r2 = krok(st); r3 = krok(st)
sprawdz("2c3 okno nie chce się zamknąć: po W_WALCE_OBCE_PROB próbach 'obce_okno', bez Ctrl+kliku",
        r1[1] == "zamkniecie_obcego" and r2[1] == "zamkniecie_obcego" and r3 == ("przerwane", "obce_okno")
        and ("otworz", 1, 0) not in zdarz, (r1, r2, r3, zdarz))
swiat["okno_uparte"] = False
reset(otwarte=True); stary_plan = loot._plan_teraz
loot._plan_teraz = lambda mysz, lista, log: (None, {"zwloki": None})
r = krok({})
loot._plan_teraz = stary_plan
sprawdz("2c4 okna nie widać na ekranie (brak X): odmowa 'obce_okno' bez inputu", r == ("przerwane", "obce_okno") and zdarz == [], (r, zdarz))
reset(stwory=[{"x": 101, "y": 100, "z": 7, "hp": 50}]); r = krok({})
sprawdz("2d żywy stwór na polu zwłok: odmowa bez inputu", r == ("przerwane", "stwor_na_zwlokach") and zdarz == [], (r, zdarz))
reset(); loot._zapytaj = lambda z: {"blad": "x"}; r = krok({})
loot._zapytaj = zapytaj
sprawdz("2e pamięć kontenerów niedostępna: odmowa (nie da się potwierdzić otwarcia)", r == ("przerwane", "brak_pamieci") and zdarz == [], (r, zdarz))

# 3. klik nie otworzył okna: po limicie czasu "brak_okna", bez drugiego kliku
reset(); st = {}
ekran.otworz = lambda dx, dy: zdarz.append(("otworz", dx, dy))
r = krok(st); wyn = [r]
for _ in range(30):
    t[0] += 0.2; r = krok(st); wyn.append(r)
    if r[0] != "kontynuuj": break
ekran.otworz = otworz
sprawdz("3 brak okna po kliku: 'brak_okna' po limicie, jeden klik", r == ("przerwane", "brak_okna") and len(zdarz) == 1, (r, zdarz))

# 4. zamknij_w_walce: zamyka otwarte okno, przy pustym stanie nic nie robi
reset(); st = {}
krok(st); krok(st)       # otwarcie + wykrycie okna (faza plan)
zdarz.clear()
sprawdz("4 zamknij_w_walce zamyka okno zwłok", loot.zamknij_w_walce(st, log=logi.append) is True and zdarz == [("zamknij",)], zdarz)
zdarz.clear()
sprawdz("4b zamknij_w_walce bez otwartego okna: zero inputu", loot.zamknij_w_walce({}, log=logi.append) is True and zdarz == [])

# 5. zamknij_w_walce: faza "czekaj" (klik poszedł, okno już widać w pamięci) zamyka własne okno
reset(); st = {}
krok(st)                                   # otwarcie: faza czekaj, klucz jeszcze nieznany
zdarz.clear()
r = loot.zamknij_w_walce(st, log=logi.append)
sprawdz("5a przerwanie w fazie 'czekaj' z oknem już w pamięci: okno zamknięte", r is True and zdarz == [("zamknij",)], (r, zdarz))
reset(); st = {}
ekran.otworz = lambda dx, dy: zdarz.append(("otworz", dx, dy))     # klik nie otwiera okna (jeszcze)
krok(st); zdarz.clear()
r = loot.zamknij_w_walce(st, log=logi.append)
ekran.otworz = otworz
sprawdz("5b 'czekaj', okna jeszcze nie ma: None (do ponowienia), zero inputu", r is None and zdarz == [], (r, zdarz))
# 5c. zamykanie zaległe (swiezo): X z świeżego planu, bez Ctrl+kliku w zapamiętane pole
reset(); st = {}
krok(st); krok(st)                         # otwarcie + wykrycie okna (faza plan)
zdarz.clear()
r = loot.zamknij_w_walce(st, log=logi.append, swiezo=True)
sprawdz("5c zaległe okno: zamknięte X-em ze świeżego planu", r is True and zdarz == [("zamknij",)] and not swiat["otwarte"], (r, zdarz))
reset(otwarte=True, okno_uparte=True); st = {"faza": "plan", "klucz": (2, 3994)}
r = loot.zamknij_w_walce(st, log=logi.append, swiezo=True)
swiat["okno_uparte"] = False
sprawdz("5d okno nie znika: False (ponowienie przez wywołującego)", r is False, r)

# 6. jedzenie w zwłokach w trakcie walki: najpierw Use na serze, potem reszta do plecaka (wcześniej ser leżał
#    w zwłokach nieruszony, bo loot w walce obsługiwał tylko listę do zebrania)
def cykl(st, maks=30):
    w = []
    for _ in range(maks):
        w.append(krok(st)); t[0] += 0.1
        if w[-1][0] != "kontynuuj":
            break
    return w
reset(ser=2); st = {}
w = cykl(st)
wej = [z[0] for z in zdarz]
sprawdz("6a zjedzone 2 sery, potem przeniesienie, zamknięcie", w[-1] == ("gotowe", "ok")
        and wej == ["otworz", "jedz", "jedz", "przeciagnij", "zamknij"], (w[-1], zdarz))
sprawdz("6b log o zjedzeniu", sum("zjedzono ze zwłok: cheese" in l for l in logi) == 2, logi)
sprawdz("6c ilosci: gold nadal zebrane", st["ilosci"].get("gold coin") == 3, st.get("ilosci"))
reset(ser=1, najedzony=True); st = {}
w = cykl(st)
wej = [z[0] for z in zdarz]
sprawdz("6d najedzony: jeden Use, potem bez ponawiania, reszta zebrana",
        w[-1] == ("gotowe", "ok") and wej == ["otworz", "jedz", "przeciagnij", "zamknij"], (w[-1], zdarz))
reset(ser=0); st = {}
cykl(st)
sprawdz("6e bez jedzenia w zwłokach: zero Use", "jedz" not in [z[0] for z in zdarz], zdarz)
reset(ser=20, najedzony=False); st = {}
cykl(st)
sprawdz("6f limit jedzenia w walce", [z[0] for z in zdarz].count("jedz") == loot.W_WALCE_MAKS_ZJEDZENIA, zdarz)

# 7. plan z obrazka (pamięć nie działa/niejednoznaczna): jedzenie w zwłokach też jest planowane
okno_z = types.SimpleNamespace(rola="zwloki", sloty=[Slot(1, 1), Slot(2, 2), Slot(3, 3)])
_zaw = loot.zawartosc
loot.zawartosc = lambda obraz, okno: [(okno.sloty[0], "gold coin", 0), (okno.sloty[1], "cheese", 0),
                                      (okno.sloty[2], "meat", 0)]
w = {"okna": [okno_z], "plecak": None, "zwloki": None, "przedmiot": None, "cel": None, "nieznane": 0,
     "zostalo": [], "jedzenie": None}
loot._plan_z_obrazu(None, w, ["gold coin", "meat"])
loot.zawartosc = _zaw
sprawdz("7a plan z obrazka: jedzenie = pierwszy ser (slot 1), id 3607",
        w["jedzenie"] is not None and w["jedzenie"][0] is okno_z.sloty[1] and w["jedzenie"][1:] == ("cheese", 3607), w["jedzenie"])
sprawdz("7b plan z obrazka: przedmiot do zebrania nadal gold", w["przedmiot"][1] == "gold coin" and w["zostalo"] == ["cheese"], (w["przedmiot"], w["zostalo"]))

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
