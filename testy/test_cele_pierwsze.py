"""CELE_PIERWSZE (24.10, polecenie Karola: "niech odchyd zabija waspy zawsze w pierwszej kolejności, bo one trują").
Potwór z listy (nazwy po przecinku) wygrywa wybór celu z każdym innym kandydatem i PRZEŁĄCZA bieżący cel w promieniu
CELE_PIERWSZE_ZMIANA_ODL; bezpieczniki (ucieczka, HP, ogień, dziura przy celu, --potwory) go nie omijają.
Pusta lista = dotychczasowy klucz. Atrapy, bez X11 i bez gry (RETRONIC_TESTY=1)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, tempfile, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot, pokretla
from pathlib import Path

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.RUNA_AKTYWNA = 0
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, "" if warunek else f" [{info}]")


class Swiat:
    def __init__(s, moby, hp=190):
        s.t = 0.0; s.poz = [100, 100, 7]; s.klik = []; s.hp = hp
        s.moby = moby          # lista (id, nazwa, dx, dy, hp%)
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.01
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp, "max_hp": 190, "mana": 100, "max_mana": 100}}
        if z["cmd"] == "cel_ataku":
            return {"id": None}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": 7, "hp": 100}
            return {"stwory": [ja] + [{"id": i, "nazwa": n, "gracz": False, "x": s.poz[0] + dx, "y": s.poz[1] + dy,
                                       "z": 7, "hp": hp} for i, n, dx, dy, hp in s.moby]}

class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): pass
    def krok(p, k, *a, **kw): return True      # świat stoi w miejscu

def zrob(s, potwory=("Troll", "Wasp", "Snake")):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: [])
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj, potwory=list(potwory),
                        atak=lambda m, g: s.klik.append((s.t, m["nazwa"])), alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=loot, okrazenia=1, jedzenie="F5")
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    return b

def tick(s, b, dt=0.1):
    s.t += dt; b.tick()

def cel_po_ticku(moby, lista="Wasp", **kw):
    cavebot.CELE_PIERWSZE = lista
    s = Swiat(moby); b = zrob(s, **kw)
    tick(s, b)
    return s, b, (b.cel or {}).get("nazwa")


TROLL_OBOK = (10, "Troll", 1, 0, 100)
WASP_3 = (20, "Wasp", 3, 0, 100)

# --- 1. pusta lista = dotychczasowa kolejność (klucz: odległość + HP/WAGA_HP - premia dobicia)
for nazwa, moby, oczek in [
        ("1a bliższy Troll przed Waspem", [TROLL_OBOK, WASP_3], "Troll"),
        ("1b Wasp bliżej niż Troll", [(10, "Troll", 4, 0, 100), (20, "Wasp", 2, 0, 100)], "Wasp"),
        ("1c ranny Troll dalej wygrywa z pełnym Waspem (WAGA_HP)", [(10, "Troll", 3, 0, 10), (20, "Wasp", 2, 0, 100)], "Troll")]:
    s, b, c = cel_po_ticku(moby, "")
    sprawdz(nazwa + " (CELE_PIERWSZE='')", c == oczek, c)
cavebot.CELE_PIERWSZE = ""
s = Swiat([TROLL_OBOK, WASP_3]); b = zrob(s); tick(s, b)
sprawdz("1d pusta lista: brak śladu mechanizmu w logu", not any("CELE_PIERWSZE" in l for l in LOGI))

# --- 2. wybór nowego celu: Wasp z listy wygrywa z bliższym / rannym Trollem
s, b, c = cel_po_ticku([TROLL_OBOK, WASP_3])
sprawdz("2a Wasp (3 pola) przed Trollem obok", c == "Wasp", c)
s, b, c = cel_po_ticku([(10, "Troll", 1, 0, 8), (20, "Wasp", 4, 1, 100)])
sprawdz("2b Wasp (4 pola, pełne HP) przed prawie martwym Trollem obok (premia dobicia)", c == "Wasp", c)
cavebot.DRUGI_CEL = 1.0
s, b, c = cel_po_ticku([TROLL_OBOK, WASP_3, (21, "Wasp", 5, 1, 100)])
cavebot.DRUGI_CEL = 0.0
sprawdz("2c DRUGI_CEL=1.0 nie wypycha celu z listy: dalej Wasp, nie Troll", c == "Wasp", c)
s, b, c = cel_po_ticku([TROLL_OBOK, (20, "Wasp", 5, 1, 100), (21, "Wasp", 2, 0, 100)])
sprawdz("2d dwa Waspy: bliższy pierwszy", b.cel["id"] == 21, b.cel)
s, b, c = cel_po_ticku([TROLL_OBOK, (20, "Snake", 4, 0, 100)], "wasp , SNAKE")
sprawdz("2e lista 'wasp , SNAKE': wielkość liter i spacje bez znaczenia, Snake pierwszy", c == "Snake", c)
s, b, c = cel_po_ticku([TROLL_OBOK, (20, "Snake", 2, 0, 100), (21, "Wasp", 4, 0, 100)], "Wasp,Snake")
sprawdz("2f Wasp,Snake: bliższy z listy (Snake 2 pola) przed Waspem 4 pola", c == "Snake", c)
s, b, c = cel_po_ticku([TROLL_OBOK, (20, "Snake", 4, 0, 100)], "Wasp")
sprawdz("2g Snake poza listą: zwykły klucz, Troll obok", c == "Troll", c)

# --- 3. przełączenie bieżącego celu
def przelaczenie(wasp, lista="Wasp", ile_ticków=2):
    cavebot.CELE_PIERWSZE = lista
    s = Swiat([TROLL_OBOK]); b = zrob(s)
    tick(s, b)
    assert b.cel["nazwa"] == "Troll"
    s.moby = [TROLL_OBOK, wasp]
    for _ in range(ile_ticków):
        tick(s, b)
    return s, b
s, b = przelaczenie((20, "Wasp", 2, 1, 100))
sprawdz("3a Wasp w odl 2 podszedł do bitego Trolla: przełączamy na Wasp", b.cel["nazwa"] == "Wasp", b.cel)
sprawdz("3b log przełączenia", any("CELE_PIERWSZE" in l and "Wasp" in l for l in LOGI), [l for l in LOGI if "Zmiana" in l])
s, b = przelaczenie((20, "Wasp", 1, 1, 100))
sprawdz("3c Wasp obok (po skosie): przełączenie + klik ataku na Wasp", b.cel["nazwa"] == "Wasp" and any(n == "Wasp" for _, n in s.klik), (b.cel, s.klik))
s, b = przelaczenie((20, "Wasp", 3, 0, 100))
sprawdz("3d Wasp w odl 3 (= CELE_PIERWSZE_ZMIANA_ODL): też przełączamy", b.cel["nazwa"] == "Wasp", b.cel)
s, b = przelaczenie((20, "Wasp", 5, 1, 100))
sprawdz("3e Wasp w odl 5 nie odrywa nas od Trolla (poza promieniem przełączenia)", b.cel["nazwa"] == "Troll", b.cel)
s.moby = [(21, "Wasp", 5, 1, 100)]          # Troll zginął
b.cel = None
tick(s, b)
sprawdz("3f ...ale po zabiciu Trolla ten Wasp jest celem", (b.cel or {}).get("nazwa") == "Wasp", b.cel)
s, b = przelaczenie((20, "Wasp", 2, 0, 100), "")
sprawdz("3g pusta lista: Wasp obok nie przełącza (dotychczasowe zachowanie)", b.cel["nazwa"] == "Troll", b.cel)
cavebot.CELE_PIERWSZE = "Wasp"
cavebot.CELE_PIERWSZE_ZMIANA_ODL = 1
s, b = przelaczenie((20, "Wasp", 2, 0, 100))
sprawdz("3h pokrętło ZMIANA_ODL=1: Wasp w odl 2 nie przełącza", b.cel["nazwa"] == "Troll", b.cel)
cavebot.CELE_PIERWSZE_ZMIANA_ODL = 3

# --- 4. brak migotania: Wasp -> Wasp bez zmian, Wasp bity do końca
cavebot.CELE_PIERWSZE = "Wasp"
s = Swiat([TROLL_OBOK, (20, "Wasp", 3, 0, 100)]); b = zrob(s); tick(s, b)
id0 = b.cel["id"]
s.moby = [TROLL_OBOK, (20, "Wasp", 3, 0, 100), (21, "Wasp", 2, 1, 100)]     # drugi Wasp bliżej, my bijemy pierwszego
LOGI.clear()
for _ in range(5):
    tick(s, b)
sprawdz("4a cel Wasp nie zmienia się na innego Waspa (bez migotania)", b.cel and b.cel["id"] == id0, b.cel)
sprawdz("4b żadnego 'Zmiana celu' w logu", not any("Zmiana celu" in l for l in LOGI), [l for l in LOGI if "Zmiana" in l])
# stary mechanizm "stoi obok" (świeży mob obok, cel dalej) nie odrywa Waspa od Trolla obok; Wasp obok to co innego
s.moby = [TROLL_OBOK, (20, "Wasp", 3, 0, 100), (21, "Wasp", 1, 1, 100)]
for _ in range(3):
    tick(s, b)
sprawdz("4d Wasp obok (inny Wasp) może przejąć cel od Wasp 3 pola dalej (dotychczasowa reguła 'stoi obok'), bez migotania",
        b.cel and b.cel["id"] == 21, b.cel)
s.moby = [TROLL_OBOK, (20, "Wasp", 3, 0, 100)]
b.cel = {"id": id0, "nazwa": "Wasp", "hp0": 100}
# Troll nie odbiera celu Waspowi, nawet gdy stoi obok, a Wasp dalej
s.moby = [TROLL_OBOK, (20, "Wasp", 3, 0, 100)]
for _ in range(3):
    tick(s, b)
sprawdz("4c Troll obok nie odbiera celu Waspowi", b.cel and b.cel["id"] == id0, b.cel)

# --- 5. bezpieczniki nie są omijane
cavebot.CELE_PIERWSZE = "Wasp"
# 5a --potwory bez Wasp: lista nie robi z Waspa celu
s, b, c = cel_po_ticku([TROLL_OBOK, (20, "Wasp", 2, 0, 100)], potwory=("Troll",))
sprawdz("5a Wasp spoza --potwory nie jest celem mimo listy", c == "Troll", c)
# 5b dziura przy celu: Wasp "skip" -> odpada, Troll zostaje
cavebot.CELE_PIERWSZE = "Wasp"
s = Swiat([TROLL_OBOK, (20, "Wasp", 2, 0, 100)]); b = zrob(s)
b.mapa = object()
b._cel_przez_dziure = lambda x, poz, teraz=None: "skip" if x["nazwa"] == "Wasp" else None
b._dziura_cel_odpusc = lambda *a, **k: None
tick(s, b)
sprawdz("5b Wasp przy dziurze (DZIURA_PRZY_CELU skip): nie jest celem, bijemy Trolla", (b.cel or {}).get("nazwa") == "Troll", b.cel)
# 5c to samo przy przełączaniu: bity Troll, Wasp podchodzi, ale stoi przy dziurze
s = Swiat([TROLL_OBOK]); b = zrob(s); b.mapa = object()
b._cel_przez_dziure = lambda x, poz, teraz=None: "skip" if x["nazwa"] == "Wasp" else None
b._dziura_cel_odpusc = lambda *a, **k: None
tick(s, b)
s.moby = [TROLL_OBOK, (20, "Wasp", 2, 0, 100)]
tick(s, b); tick(s, b)
sprawdz("5c Wasp przy dziurze nie przełącza celu", (b.cel or {}).get("nazwa") == "Troll", b.cel)
# 5d ogień: Wasp w odl 3 stoi przy parzącym polu
s = Swiat([TROLL_OBOK, (20, "Wasp", 3, 0, 100)]); b = zrob(s)
b._ogien_parzy_dane = lambda z: True
b._ogien_przy_parzacym = lambda p: p[0] == 103
tick(s, b)
sprawdz("5d Wasp przy parzącym ogniu: nie jest celem (Troll obok zostaje)", (b.cel or {}).get("nazwa") == "Troll", b.cel)
# 5e niskie HP: ucieczka/leczenie mają pierwszeństwo (nie zaczynamy walki z Waspem)
s = Swiat([TROLL_OBOK, WASP_3], hp=20); b = zrob(s)
tick(s, b)
sprawdz("5e HP 10%: bot nie wybiera Waspa jako celu (ucieczka przed walką)", (b.cel or {}).get("nazwa") != "Wasp", b.cel)

# --- 6. dojście/wypad: Wasp obok w biegu = walka od razu (lista pusta = dalej biegniemy)
def bieg(lista, mob):
    cavebot.CELE_PIERWSZE = lista
    s = Swiat([mob]); b = zrob(s)
    b.dojscie_aktywne = True; cavebot.DOJSCIE_BIEGNIJ = 1; b.ruch_czas = 5.0     # ruszamy się: droga nie jest zablokowana
    kand = b.kandydaci(s.zapytaj({"cmd": "stwory"})["stwory"][1:], tuple(s.poz))
    return b._wypad_bieg(kand, tuple(s.poz), 5.0)
b_ = bieg("Wasp", (20, "Wasp", 1, 0, 100))
sprawdz("6a dojście: Wasp obok z listy = walka, nie bieg", b_ is False, b_)
b_ = bieg("Wasp", (10, "Troll", 1, 0, 100))
sprawdz("6b dojście: Troll obok (poza listą) = dalej bieg (jak dotąd)", b_ is True, b_)
b_ = bieg("", (20, "Wasp", 1, 0, 100))
sprawdz("6c dojście: pusta lista, Wasp obok = dalej bieg (jak dotąd)", b_ is True, b_)
b_ = bieg("Wasp", (20, "Wasp", 3, 0, 100))
sprawdz("6d dojście: Wasp w odl 3 (nie obok) nie zatrzymuje biegu", b_ is True, b_)

# --- 7. pokrętło: pokretla.py (tekst wolny, tylko ręcznie w na_zywo.json)
ok_, bl = pokretla.waliduj({"CELE_PIERWSZE": "Wasp,Snake"})
sprawdz("7a waliduj przyjmuje tekst", ok_ == {"CELE_PIERWSZE": "Wasp,Snake"} and not bl, (ok_, bl))
ok_, bl = pokretla.waliduj({"CELE_PIERWSZE": 5})
sprawdz("7b liczba odrzucona", not ok_ and bl, (ok_, bl))
ok_, bl = pokretla.waliduj({"CELE_PIERWSZE": "x" * 500})
sprawdz("7c zbyt długi tekst odrzucony", not ok_ and bl, (ok_, bl))
ok_, bl = pokretla.waliduj({"CELE_PIERWSZE": "Wasp;rm -rf"})
sprawdz("7d znaki spoza liter/cyfr/spacji/przecinka/kreski odrzucone", not ok_ and bl, (ok_, bl))
ok_, bl = pokretla.waliduj({"CELE_PIERWSZE": "Wasp"}, {"CELE_PIERWSZE": ""})
sprawdz("7e analityk (z domyślnymi) nie zmienia listy", not ok_ and bl, (ok_, bl))
ok_, bl = pokretla.waliduj({"CELE_PIERWSZE_ZMIANA_ODL": 2})
sprawdz("7f ZMIANA_ODL liczbowe w zakresie", ok_ == {"CELE_PIERWSZE_ZMIANA_ODL": 2}, (ok_, bl))
ok_, bl = pokretla.waliduj({"CELE_PIERWSZE_ZMIANA_ODL": 20})
sprawdz("7g ZMIANA_ODL poza zakresem odrzucone", not ok_ and bl, (ok_, bl))
kat = Path(tempfile.mkdtemp())
plik = kat / "na_zywo.json"
plik.write_text(json.dumps({"CELE_PIERWSZE": "Wasp,Snake"}))
cavebot.CELE_PIERWSZE = ""
cavebot._POKRETLA_DOMYSLNE = {}
pk = pokretla.Pokretla(cavebot, plik=plik, log=lambda *a: None)
pk.odswiez()
sprawdz("7h hot-reload ustawia stałą w cavebot", cavebot.CELE_PIERWSZE == "Wasp,Snake", cavebot.CELE_PIERWSZE)
plik.write_text("{}"); pk.mtime = None; pk.odswiez()
sprawdz("7i usunięcie klucza przywraca domyślną (pusta lista)", cavebot.CELE_PIERWSZE == "", repr(cavebot.CELE_PIERWSZE))

# --- 8. dane: odchyd ma listę, a Wasp i Snake są w potworach mapy
R = Path(__file__).resolve().parent.parent
mapy = json.loads((R / "mapy.json").read_text())
pot = [p.strip().casefold() for p in mapy["trolle_kazordoon_z8"]["potwory"].split(",")]
sprawdz("8a mapy.json trolle_kazordoon_z8: Troll, Wasp, Snake", {"troll", "wasp", "snake"} <= set(pot), pot)
nz = json.loads((R / "instancje" / "odchyd" / "na_zywo.json").read_text())
sprawdz("8b odchyd na_zywo.json: CELE_PIERWSZE = Wasp,Snake", nz.get("CELE_PIERWSZE") == "Wasp,Snake", nz.get("CELE_PIERWSZE"))
inne = [p.name for p in (R / "instancje").glob("*/na_zywo.json") if p.parent.name != "odchyd" and "CELE_PIERWSZE" in p.read_text()]
sprawdz("8c inne postacie bez CELE_PIERWSZE", not inne, inne)
okp, blp = pokretla.waliduj(nz)
sprawdz("8d na_zywo.json odchyda przechodzi waliduj bez błędów", not blp, blp)

print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
