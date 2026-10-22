"""22.10 invincible, Edron z9->z8 (33131,31806): pierwsza lina z pola obok bez skutku, postać wylądowała NA polu liny,
slot „lina” wypadał z listy (_stosuje), zostawały dwa R (Ctrl+klik) z pola -> „bez skutku po 3 próbach”.
Reguła Karola 21.10: liny nie użyjesz na polu, na którym stoisz. Oczekiwane: lina zostaje w liście, a _proba schodzi
krokiem na wolne pole obok i dopiero stamtąd używa liny. Atrapy, bez gry."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import pietra

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

T = (33131, 31806, 9)
LAD = (33131, 31807, 8)
KIER = {"Down": (0, 1), "Left": (-1, 0), "Right": (1, 0), "Up": (0, -1)}

class Postac:
    def __init__(p, poz, blok=()):
        p.poz, p.kroki, p.blok = list(poz), [], set(blok)
    def pozycja(p): return tuple(p.poz)
    def krok(p, k):
        p.kroki.append(k)
        d = KIER[k]; n = (p.poz[0] + d[0], p.poz[1] + d[1])
        if n not in p.blok:
            p.poz[0], p.poz[1] = n

class Mapa:
    def __init__(m, sciany=()): m.sciany = set(sciany)
    def flagi(m, x, y, z): return 4 if (x, y) in m.sciany else 1

def scena(poz, sciany=(), blok=()):
    postac, liny = Postac(poz, blok), []
    cb = types.SimpleNamespace(mapa=Mapa(sciany), postac=postac, klik_cel=None, idx=0, zegar=lambda: 0.0,
                               zatrzymaj_klik=lambda p: None, pauza=lambda a, b: None, spij=lambda s: None,
                               _wypad_reset_klik=lambda: None, stwory_pola=set(), pietra_porazki=0)
    def uzyj_line(cel, p):
        liny.append((tuple(cel), tuple(p)))
        if tuple(p[:2]) != tuple(cel[:2]):           # lina działa tylko z pola obok
            postac.poz[:] = list(LAD)
    cb.pietra_ops = types.SimpleNamespace(uzyj_line=uzyj_line, uzyj_pole=lambda c, p: None)
    P = pietra.Pietra(cb, konf=None, log=lambda *a: None)
    P._tele = lambda *a, **k: None
    st = {"z0": 9, "tryby": ["lina"], "proby": 0, "cel": LAD, "od": 0.0, "nast": 0.0, "ki": 0}
    k = {"pole": T, "pewne": True, "lad": LAD}
    return P, st, k, postac, liny

# 1. stoimy na polu liny: lina nadal na liście (nie wypada), schodzimy krokiem, lina z pola obok
P, st, k, postac, liny = scena(T)
sprawdz("lina na własnym polu zostaje w liście (krok obok to część próby)", pietra.Pietra._stosuje(P, "lina", T, T, 0.0))
P._proba(T, st, k, 0.0)
sprawdz("zszedł z pola liny krokiem", postac.kroki and liny and liny[0][1][:2] != T[:2], (postac.kroki, liny))
sprawdz("lina użyta dokładnie raz i nigdy z własnego pola", len(liny) == 1 and liny[0][1][:2] != T[:2], liny)
sprawdz("po linie jest z8", postac.poz[2] == 8 if len(postac.poz) > 2 else False, postac.poz)

# 2. przypadek z logu: [lina, R, lina]; lina 1 z pola obok bez skutku i postać ląduje na polu liny
P, st, k, postac, liny = scena(T)
st["tryby"] = ["R", "lina"]; st["proby"] = 0
P._proba(T, st, k, 0.0)                        # R z pola liny: nic
sprawdz("R z pola: lina nie wypadła z listy", st["tryby"] == ["R", "lina"], st["tryby"])
P._proba(T, st, k, 1.0)
sprawdz("lina po R: użyta z pola obok", len(liny) == 1 and liny[0][1][:2] != T[:2], liny)

# 3. wszystkie sąsiednie pola zablokowane (ściany): liny z własnego pola NIE używamy
sciany = {(T[0] + dx, T[1] + dy) for dx, dy in KIER.values()}
P, st, k, postac, liny = scena(T, sciany=sciany)
P._proba(T, st, k, 0.0)
sprawdz("brak wolnego pola obok: lina nie jest używana z własnego pola", liny == [], liny)

# 4. krok nie wyszedł (pozycja stoi mimo strzałki): też bez liny z pola
P, st, k, postac, liny = scena(T, blok={(T[0] + dx, T[1] + dy) for dx, dy in KIER.values()})
P._proba(T, st, k, 0.0)
sprawdz("krok bez skutku: lina nie jest używana z własnego pola", liny == [], liny)

# 5. stoimy obok: bez kroku, lina od razu
P, st, k, postac, liny = scena((T[0] - 1, T[1], 9))
P._proba(postac.pozycja(), st, k, 0.0)
sprawdz("z pola obok: bez zbędnego kroku, lina raz", postac.kroki == [] and len(liny) == 1, (postac.kroki, liny))

print(); print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
