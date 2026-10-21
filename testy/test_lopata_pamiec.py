"""F4 SPEC_generator_spotow_1021: zasypana dziura zapisuje się w pamięci jako "lopata", pamięć "lopata" i pokrętło
PIETRA_LOPATA_AUTO włączają łopatę poza listą ZASYPANE. Przypadek: kutangen 21.10, Thais północ (32347,32123,z7):
16:35 Use stojąc na polu bez skutku; 16:36 zejście Left, łopata, krok Right -> z8; pamięć zapisała wtedy "krok".
Atrapa: prawdziwa mapa, dziura zasypana, dopóki ktoś nie użyje na niej łopaty; potem krok w nią = z8."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, tempfile, types
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import cavebot, bot, mapa as _mapa, wypad, pietra
from pathlib import Path

LOG = []
cavebot.log = lambda *a: LOG.append(" ".join(map(str, a)))
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

M = _mapa.Mapa()
DZIURA = (32347, 32123, 7)
def idzie(x, y, z):
    v = M.flagi(x, y, z); return bool(v & 1) and not v & 4 and not v & 2


class Swiat:
    def __init__(s, poz):
        s.t = 0.0; s.poz = list(poz); s.zmiany = []; s.odkopana = False; s.kopal = []
    def zegar(s): return s.t
    def klik(s, dx, dy): pass
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}]}
    def ruch(s, dx, dy):
        x, y, z = s.poz[0] + dx, s.poz[1] + dy, s.poz[2]
        if (x, y, z) == DZIURA:
            if s.odkopana:
                s.zmiany.append((tuple(s.poz), 8)); s.poz[:] = [x, y, 8]; return
            s.poz[0], s.poz[1] = x, y; return              # zasypana: stoi na niej, nie spada
        v = M.flagi(x, y, z)
        if not v & 1 or v & 4 or v & 2:
            return
        s.poz[0], s.poz[1] = x, y


class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): pass
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2; przed = tuple(p.s.poz); p.s.ruch(*d); return tuple(p.s.poz) != przed


class Ops:
    def __init__(o, s): o.s = s
    def uzyj_pole(o, pole, poz): pass                       # Use na zasypanej dziurze nic nie robi
    def uzyj_line(o, pole, poz): pass
    def uzyj_lopate(o, cel, poz):
        o.s.kopal.append((tuple(cel), tuple(poz)))
        if tuple(cel) == DZIURA and max(abs(cel[0] - poz[0]), abs(cel[1] - poz[1])) == 1:
            o.s.odkopana = True


TRASA = [(32347, 32125, 7), (32347, 32124, 7), DZIURA, (32347, 32123, 8), (32347, 32124, 8)]


def bieg(pam, zasypane, auto=0, start=(32347, 32125, 7)):
    LOG.clear()
    wypad.PLIK_PRZEJSC = pam
    stare = pietra.ZASYPANE
    pietra.ZASYPANE = set(zasypane)
    try:
        s = Swiat(start)
        b = cavebot.Cavebot(P(s), TRASA + [TRASA[-1]] * 10, zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None,
                            spij=s.spij, zegar=s.zegar, loot=types.SimpleNamespace(zbierz=lambda z, g: "ok"), mapa=M,
                            klik=s.klik, okrazenia=1)
        b.pietra_ops = Ops(s)
        if b.pokretla is not None:
            try:
                d = json.loads((Path(_R) / "na_zywo.json").read_text())
            except Exception:
                d = {}
            d.update({"PIETRA_TRYBY_Z_DANYCH": 1, "PRZEJSCIE_TRZY_SPOSOBY": 1, "PIETRA_LOPATA": 1, "PIETRA_LOPATA_AUTO": auto})
            kopia = Path(tempfile.mkdtemp()) / "na_zywo.json"; kopia.write_text(json.dumps(d))
            b.pokretla.plik = kopia
        cavebot.PRZEJSCIE_TRZY_SPOSOBY = 1; cavebot.PIETRA_LOPATA_AUTO = auto; cavebot.PIETRA_TRYBY_Z_DANYCH = 1
        b.idx = 1
        for _ in range(200):
            if s.zmiany or not b.tick():
                break
        return s
    finally:
        pietra.ZASYPANE = stare


def pamiec(pam):
    return wypad.przejscia_nauczone(pam).get("32347,32123,7>8", {}).get("tryb")


# A. pole w ZASYPANE, pusta pamięć (jak 21.10 16:36): przejście + zapis "lopata", nie "krok"
pamA = _os.path.join(tempfile.mkdtemp(), "p.json")
s = bieg(pamA, {DZIURA})
sprawdz("A zasypana w ZASYPANE: zejście na z8", s.poz[2] == 8, f"{s.poz} {[l for l in LOG if 'Przejście' in l][-3:]}")
sprawdz("A łopata użyta z pola obok", s.kopal and s.kopal[0][0] == DZIURA, f"{s.kopal}")
sprawdz("A pamięć = lopata (dawniej krok)", pamiec(pamA) == "lopata", f"{wypad.przejscia_nauczone(pamA)}")

# B. pole NIE w ZASYPANE, pamięć "lopata" (z A): łopata dalej działa
s = bieg(pamA, set())
sprawdz("B poza ZASYPANE, pamięć lopata: zejście na z8", s.poz[2] == 8 and s.kopal, f"{s.poz} {s.kopal}")
sprawdz("B pamięć zostaje lopata (licznik 2)", wypad.przejscia_nauczone(pamA)["32347,32123,7>8"] .get("n") == 2 and pamiec(pamA) == "lopata",
        f"{wypad.przejscia_nauczone(pamA)}")

# C. poza ZASYPANE, pusta pamięć, AUTO=0: bez łopaty (dawne zachowanie), nie schodzi
pamC = _os.path.join(tempfile.mkdtemp(), "p.json")
s = bieg(pamC, set(), auto=0)
sprawdz("C bez wpisu, bez pamięci, AUTO=0: łopata nieużyta", not s.kopal and s.poz[2] == 7, f"{s.poz} {s.kopal}")

# D. poza ZASYPANE, pusta pamięć, AUTO=1: łopata sama, zejście, pamięć lopata
pamD = _os.path.join(tempfile.mkdtemp(), "p.json")
s = bieg(pamD, set(), auto=1)
sprawdz("D AUTO=1: łopata bez wpisu w ZASYPANE, zejście na z8", s.poz[2] == 8 and s.kopal, f"{s.poz} {s.kopal}")
sprawdz("D AUTO=1: pamięć = lopata", pamiec(pamD) == "lopata", f"{wypad.przejscia_nauczone(pamD)}")

# E. zwykła otwarta dziura: krok bez łopaty zapisuje się jako krok (bez regresji)
p = pietra.Pietra.__new__(pietra.Pietra); p.log = lambda *a: None
pamE = _os.path.join(tempfile.mkdtemp(), "p.json"); wypad.PLIK_PRZEJSC = pamE
pietra.Pietra._naucz(p, "krok Right", (10, 10, 7), (9, 10, 7), 8)
sprawdz("E krok bez łopaty = krok", wypad.przejscia_nauczone(pamE).get("10,10,7>8", {}).get("tryb") == "krok")
pietra.Pietra._naucz(p, "krok Right", (11, 10, 7), (10, 10, 7), 8, lopata=True)
sprawdz("E krok po łopacie = lopata", wypad.przejscia_nauczone(pamE).get("11,10,7>8", {}).get("tryb") == "lopata")

print(f"{sum(ok)}/{len(ok)} OK" if all(ok) else f"FAIL {len(ok) - sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
