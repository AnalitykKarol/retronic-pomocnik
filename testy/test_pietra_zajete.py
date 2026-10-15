"""15.10: pole przejścia pięter (lina) zajęte przez stwora/gracza: bez zużywania prób, bicie dowolnego stwora, limit.
Wyłącznie atrapy (jak test_wielopietrowa.py). Odtwarza przypadek z 15.10 17:13 (Rat na polu liny, Edron z11)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
_R = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _R)
import bot, pietra, cavebot

LOG = []
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

T = (33133, 31805, 11)
POZ = (33133, 31806, 11)

class Cb:
    def __init__(s, kto, atak_zabija=True):
        s.t = 0.0; s.kto = kto; s.ataki = []; s.zabija = atak_zabija
        s.postac = types.SimpleNamespace(nazwa="Ja")
        s.zyje = kto is not None
    def zegar(s): return s.t
    def pauza(s, a, b): s.t += a
    def stwory(s, w=None):
        l = [{"id": 1, "nazwa": "Ja", "gracz": True, "x": POZ[0], "y": POZ[1], "z": POZ[2], "hp": 100}]
        if s.zyje:
            l.append({"id": 2, "nazwa": s.kto[0], "gracz": s.kto[1], "x": T[0], "y": T[1], "z": T[2], "hp": 100})
        return l
    def atak(s, m, g):
        s.ataki.append(m["nazwa"])
        if s.zabija: s.zyje = False

def nowy(cb, **konf):
    k = types.SimpleNamespace(**konf)
    return pietra.Pietra(cb, konf=k, log=lambda t: LOG.append(t)), {}

# 1. Rat na polu liny, atak zabija: True, atak raz, próby niezużyte, log
LOG.clear()
cb = Cb(("Rat", False)); p, st = nowy(cb)
r = p._zajete(POZ, T, st, cb.t)
sprawdz("1 rat na polu: obieg zużyty", r is True)
sprawdz("1 atak na Rata (bez listy łowiska)", cb.ataki == ["Rat"])
sprawdz("1 log 'atakuję'", any("Rat" in l and "atakuję" in l for l in LOG), f"{LOG}")
sprawdz("1 próby niezużyte", "proby" not in st)
r = p._zajete(POZ, T, st, cb.t)
sprawdz("1 rat zabity: pole wolne -> None (normalna próba)", r is None)

# 2. stwór nie ginie: ponawiamy atak co >= 2 s, po limicie None i brak dalszego czekania
LOG.clear()
cb = Cb(("Rat", False), atak_zabija=False); p, st = nowy(cb, PIETRA_ZAJETE_MAX_S=20.0)
n = 0
while p._zajete(POZ, T, st, cb.t) is True and n < 500: n += 1
sprawdz("2 limit 20 s: po nim zwykłe próby", cb.t >= 20.0 and n < 500, f"t={cb.t:.1f} n={n}")
sprawdz("2 atak ponawiany nie częściej niż co 2 s", 5 <= len(cb.ataki) <= 11, f"ataków={len(cb.ataki)}")
sprawdz("2 po limicie nie wraca do czekania", p._zajete(POZ, T, st, cb.t) is None)
sprawdz("2 log o limicie", any("zwykłe próby" in l for l in LOG))

# 3. gracz na polu: czekamy, nie atakujemy
LOG.clear()
cb = Cb(("Bob", True)); p, st = nowy(cb)
r = p._zajete(POZ, T, st, cb.t)
sprawdz("3 gracz na polu: czekamy", r is True and cb.ataki == [], f"ataki={cb.ataki}")
sprawdz("3 log o graczu", any("gracz Bob" in l for l in LOG))
n = 0
while p._zajete(POZ, T, st, cb.t) is True and n < 500: n += 1
sprawdz("3 gracz: ten sam limit", 20.0 <= cb.t < 22.0 and cb.ataki == [], f"t={cb.t:.1f}")

# 4. pokrętła: 0 = wyłączone; ATAK=0 = tylko czekanie
cb = Cb(("Rat", False)); p, st = nowy(cb, PIETRA_ZAJETE_MAX_S=0)
sprawdz("4 MAX_S=0: wyłączone", p._zajete(POZ, T, st, cb.t) is None and cb.ataki == [])
cb = Cb(("Rat", False)); p, st = nowy(cb, PIETRA_ZAJETE_ATAK=0)
sprawdz("4 ATAK=0: czeka bez ataku", p._zajete(POZ, T, st, cb.t) is True and cb.ataki == [])

# 5. stwór na innym polu / inne piętro / my sami: pole wolne
cb = Cb(("Rat", False)); cb.stwory = lambda w=None: [
    {"id": 1, "nazwa": "Ja", "gracz": True, "x": T[0], "y": T[1], "z": T[2], "hp": 100},
    {"id": 2, "nazwa": "Rat", "gracz": False, "x": T[0] + 1, "y": T[1], "z": T[2], "hp": 100},
    {"id": 3, "nazwa": "Rat", "gracz": False, "x": T[0], "y": T[1], "z": T[2] - 1, "hp": 100}]
p, st = nowy(cb)
sprawdz("5 my na T / stwór obok / inne piętro: wolne", p._zajete(T, T, st, cb.t) is None and cb.ataki == [])

# 6. pokrętła zarejestrowane
import pokretla, json
sprawdz("6 pokrętła w ZAKRESY i przykładzie", all(k in pokretla.ZAKRESY for k in ("PIETRA_ZAJETE_MAX_S", "PIETRA_ZAJETE_ATAK"))
        and all(k in json.load(open(_R + "/na_zywo.przyklad.json")) for k in ("PIETRA_ZAJETE_MAX_S", "PIETRA_ZAJETE_ATAK"))
        and cavebot.PIETRA_ZAJETE_MAX_S == 20.0)

print(f"\nOK={sum(ok)} FAIL={len(ok) - sum(ok)}")
sys.exit(0 if all(ok) else 1)
