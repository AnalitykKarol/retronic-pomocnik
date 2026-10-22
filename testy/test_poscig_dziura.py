"""Pościg w trybie TRZYMANIA klawisza a nauczona dziura (22.10, dawajkesh, mapa trolle_edron_z9z, piętro 9).
Błąd: ~10:49:29 postać stała na (33068,31716,z9) i trzymała klawisz w dół; decyzja o kolejnym kroku była liczona względem pola Q
(po kroku w toku = (33068,31717)), a klient ruszał dopiero po zmianie klawisza, więc nowy kierunek (w lewo) szedł z POZ
w nauczoną dziurę (33067,31716,z9) -> wpadnięcie na z10. Test: atrapa klienta OTClient z opóźnieniem startu kroku
(po dojściu klient czyta trzymany klawisz dopiero po START_KROKU s), PRAWDZIWA mapa serwera (mapa.py), dziury (33067,31716,9)
i (33069,31717,9) nauczone jak w trasy/dziury_nauczone.json (plik tymczasowy, nie ruszamy danych). Czysty offline."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, tempfile, types
sys.dont_write_bytecode = True
_R = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _R)
import cavebot, bot, mapa as _mapa, wpadniecie
from pathlib import Path

cavebot.log = lambda *a: None
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

M = _mapa.Mapa()
DZIURY = [(33067, 31716, 9), (33069, 31717, 9)]
START = (33068, 31714, 9)
TROLL = (33066, 31718)
DZIURY_XY = {d[:2] for d in DZIURY}
sprawdz("0 mapa: dziury z logu mają flagę 2 (nie ścianę), pola wokół chodliwe",
        all(M.flagi(*d) & 2 and not M.flagi(*d) & 4 for d in DZIURY) and M.flagi(33068, 31716, 9) == 1, [M.flagi(*d) for d in DZIURY])


class Swiat:
    """Atrapa klienta z trzymanym klawiszem. Krok trwa DL s. Po dojściu (i na starcie z postoju) klient czeka START_KROKU s,
    po czym czyta TRZYMANY klawisz i rusza w jego kierunku (wejście na dziurę = upadek na z+1)."""
    DL = 0.45
    START_KROKU = 0.15
    def __init__(s, poz, dl=None, start_kroku=None):
        s.t = 0.0; s.poz = list(poz); s.trzym = None; s.krok = None; s.gotowy = s.t     # krok: (koniec, wektor)
        s.dl = s.DL if dl is None else dl; s.sk = s.START_KROKU if start_kroku is None else start_kroku
        s.upadki = []; s.zd = []; s.stwory = []; s.nielegalne = 0
        s.troll = [TROLL[0], TROLL[1], 9]
    def zegar(s): return s.t
    def idzie(s, x, y, z):
        v = M.flagi(x, y, z); return bool(v & 1) and not v & 4
    def advance(s):
        while True:
            if s.krok is not None:
                if s.t < s.krok[0]: return
                tk, v = s.krok; s.krok = None
                s.poz[0] += v[0]; s.poz[1] += v[1]
                s.gotowy = tk + s.sk                       # klient czyta klawisz dopiero po START_KROKU od dojścia
                continue
            if s.trzym is None: return
            if s.t < s.gotowy: return
            v = s.trzym; x, y = s.poz[0] + v[0], s.poz[1] + v[1]
            if not s.idzie(x, y, s.poz[2]):
                s.nielegalne += 1; s.trzym = None; return
            if (x, y) in DZIURY_XY:                        # krok w dziurę: upadek na z+1
                s.upadki.append((tuple(s.poz), (x, y, s.poz[2] + 1), round(s.t, 2), v))
                s.poz[:] = [x, y, s.poz[2] + 1]; s.trzym = None; return
            s.krok = (max(s.t, s.gotowy) + s.dl, v)
            if s.krok[0] > s.t and s.t < s.gotowy: pass
    def spij(s, d): s.t += d; s.advance()
    def pozycja(s): s.t += 0.035; s.advance(); return tuple(s.poz)
    def trzymaj_kierunek(s, dx, dy):
        s.advance(); s.zd.append((round(s.t, 2), "zmien" if s.trzym else "nacisnij", (dx, dy), tuple(s.poz)))
        if s.trzym is None and s.krok is None: s.gotowy = max(s.gotowy, s.t)
        s.trzym = (dx, dy); s.advance()
    def puszczaj(s):
        s.advance()
        if s.trzym is not None: s.zd.append((round(s.t, 2), "puść", s.trzym, tuple(s.poz)))
        s.trzym = None
    def zapytaj(s, z):
        s.t += 0.04; s.advance()
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0}}
        troll = {"id": 7, "nazwa": "Troll", "gracz": False, "x": s.troll[0], "y": s.troll[1], "z": s.troll[2], "hp": 80}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}, dict(troll)]}
        if z["cmd"] == "poscig":
            return {"pozycja": {"x": s.poz[0], "y": s.poz[1], "z": s.poz[2]},
                    "stwor": {**{k: troll[k] for k in ("id", "x", "y", "z", "hp")}, "atakowany": True, "bije_nas": False}}
        if z["cmd"] == "stwor":
            return {"stwor": {**{k: troll[k] for k in ("id", "x", "y", "z", "hp")}, "atakowany": True, "bije_nas": False}}
        return {}


class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return p.s.pozycja()
    def trzymaj_kierunek(p, dx, dy): p.s.trzymaj_kierunek(dx, dy)
    def puszczaj(p): p.s.puszczaj()
    def trzymany_kierunek(p): return p.s.trzym
    def puls(p): pass
    def klawisz(p, k): pass


def nowy(start=START, **kw):
    kat = Path(tempfile.mkdtemp())
    wpadniecie.PLIK_DZIUR = kat / "dziury_nauczone.json"
    s = Swiat(start, **kw)
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
    b = cavebot.Cavebot(P(s), [start], zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None,
                        spij=s.spij, zegar=s.zegar, loot=loot, mapa=M, klik=lambda dx, dy: None)
    b.spij = s.spij
    tele = []
    class Tele:
        def zdarzenie(self, typ, **d): tele.append((typ, d))
        def probka(self, *a): return None
        def linia(self, *a): pass
    class Pokr:
        def odswiez(self): pass
    b.tele = Tele(); b.pokretla = Pokr(); b.pokretla_ost = float("-inf")
    b.czy_atakowany = lambda stwor, gracz: True
    s.tele = tele
    w = b._wp(); w.plik_stop = kat / "STOP"
    for d in DZIURY: w.ucz(d)
    return s, b


def pos_cel(s):
    return {"id": 7, "nazwa": "Troll", "gracz": False, "x": s.troll[0], "y": s.troll[1], "z": 9, "hp": 80, "adres": "0x1000"}


def pościg(s, b):
    g = {"hp": 100, "max_hp": 100, "proc": 100.0}
    b.ostatnie_stwory = s.zapytaj({"cmd": "stwory"})["stwory"]
    return b.poscig_szybki(pos_cel(s), tuple(s.poz), g)


# --- 1. scenariusz z logu: Troll za dziurą, bot zbiega z północy po kolumnie 33068 i skręca przy dziurze (33067,31716)
for dl, sk in ((0.45, 0.15), (0.45, 0.25), (0.35, 0.10), (0.6, 0.2)):
    s, b = nowy(dl=dl, start_kroku=sk)
    b.postac.pozycja()
    pościg(s, b)
    sprawdz(f"1 pościg za Trollem przy dziurze (krok {dl} s, start {sk} s): bot nie wpada w nauczoną dziurę",
            not s.upadki and s.poz[2] == 9, f"upadki={s.upadki} poz={s.poz}")

# --- 2. wymuszenie: stoimy NA polu obok dziury, trzymamy klawisz w dół (krok w toku), cel po lewej -> kolejny klawisz nie w dziurę
s, b = nowy(start=(33068, 31716, 9), start_kroku=0.3)
s.troll[:] = [33065, 31716, 9]                                  # cel w tym samym rzędzie, dziura pomiędzy
s.trzym = (0, 1); s.krok = None; s.gotowy = s.t                 # klawisz w dół trzymany z poprzedniego kroku
pościg(s, b)
sprawdz("2 cel w rzędzie za dziurą: żaden krok nie kończy się w dziurze", not s.upadki and s.poz[2] == 9, f"upadki={s.upadki}")

# --- 3. filtr jest widoczny w telemetrii pościgu (dziura_krok) tylko tam, gdzie zakręt "na zapas" wszedłby w dziurę
s, b = nowy(start_kroku=0.15)
pościg(s, b)
kon = [d for t, d in s.tele if t == "poscig_koniec"]
sprawdz("3 poscig_koniec zapisane, filtry to słownik", len(kon) == 1 and isinstance(kon[0].get("filtry"), dict), kon)

# --- 4. funkcja pomocnicza: dziura nauczona i pole zmiany piętra z mapy to pola upadku, zwykłe pole nie
s, b = nowy()
sprawdz("4 _pole_upadku: nauczona dziura tak, zwykłe pole nie",
        b._pole_upadku((33067, 31716, 9)) and b._pole_upadku((33069, 31717, 9)) and not b._pole_upadku((33068, 31716, 9)))

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
