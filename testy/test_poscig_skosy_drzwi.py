"""R1c: pościg i patrol w korytarzu skośnym z8 (POSCIG_SKOSY_ZAPAS) i przez drzwi (32505,32270,8) (PATROL_DRZWI).
Atrapy z test_patrol_troll.py (prawdziwa mapa i miejsca_troll.json), bez gry (RETRONIC_TESTY=1)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
from pathlib import Path

KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_src = (KAT / "testy" / "test_patrol_troll.py").read_text()
_src = _src[:_src.index("# 2. patrol wizytuje")]
_g = {"__file__": str(KAT / "testy" / "test_patrol_troll.py"), "__name__": "atrapy_patrol_troll"}
exec(compile(_src, "test_patrol_troll(atrapy)", "exec"), _g)
globals().update({k: v for k, v in _g.items() if not k.startswith("__")})
ok.clear()

DR = (32505, 32270, 8)
STAN = {"otwarte": False}


def f2(x, y, z):                     # drzwi: ściana w mapie, przechodnie tylko gdy otwarte
    v = M.flagi(x, y, z)
    if (x, y, z) in LADOWANIA:
        v &= ~2
    if (x, y, z) == DR:
        return (v | 1) & ~4 if STAN["otwarte"] else (v | 1 | 4)
    return v


_g["f"] = f2


class P2(P):
    def klawisz(p, k):
        p.krok(k)

    def skos(p, nx, ny):
        p.s.t += 0.5
        p.s.ruch(nx, ny)

    def krok_skos(p, nx, ny):
        przed = tuple(p.s.poz)
        p.skos(nx, ny)
        return tuple(p.s.poz) != przed


class Swiat2(Swiat):
    def __init__(s, poz, drzwi_dzialaja=True, **kw):
        super().__init__(poz, **kw)
        s.drzwi_dzialaja = drzwi_dzialaja
        STAN["otwarte"] = False

    def uzyj(s, pole):
        s.uzycia.append(tuple(pole))
        if tuple(pole) == DR and s.drzwi_dzialaja:
            STAN["otwarte"] = True


def zrob2(s, punkty, **kw):
    b = zrob(s, punkty, **kw)
    b.postac = P2(s)
    b.klik = None if kw.get("bez_klik") else s.klik
    return b


def poscig(b, s, cel, n=60):
    """Wołaj podejdz jak pościg (strzałka/skos po jednym kroku), aż postać stanie obok celu albo zwróci None."""
    wynik = True
    for i in range(n):
        poz = tuple(s.poz)
        if max(abs(poz[0] - cel[0]), abs(poz[1] - cel[1])) <= 1:
            return True, i
        wynik = b.podejdz(cel, poz, pilne=True, natychmiast=True, poscig=True, objazd=True)
        s.t += 0.25
        if wynik is None:
            return None, i
    return False, n


LOGR = LOG
sk0 = (cavebot.POSCIG_SKOSY_ZAPAS, cavebot.POSCIG_SKOS_AWARYJNY, cavebot.PATROL_DRZWI)
CEL_SK = (32500, 32303)
START_SK = (32492, 32295, 8)

# --- 1. korytarz skośny ---
cavebot.POSCIG_SKOS_AWARYJNY = 0
cavebot.POSCIG_SKOSY_ZAPAS = 0
s = Swiat2(START_SK); b = zrob2(s, list(troll))
d0 = b.droga(START_SK, CEL_SK, [], 1, skosy=False)
sprawdz("1a bez skosów drogi do korytarza nie ma", d0 is None, f"{d0}")
w, n = poscig(b, s, CEL_SK)
sprawdz("1b ZAPAS=0, AWARYJNY=0: pościg odpuszcza (None)", w is None, f"{w} kroki={n}")

cavebot.POSCIG_SKOSY_ZAPAS = 1
LOG.clear()
s = Swiat2(START_SK); b = zrob2(s, list(troll))
w, n = poscig(b, s, CEL_SK)
sprawdz("1c ZAPAS=1: troll w korytarzu skośnym osiągalny", w is True and max(abs(s.poz[0] - CEL_SK[0]), abs(s.poz[1] - CEL_SK[1])) <= 1,
        f"{w} poz={s.poz} kroki={n}")
sprawdz("1d droga skosem bez nielegalnych ruchów", s.nielegalne == 0, f"{s.nielegalne}")

s = Swiat2(START_SK); b = zrob2(s, list(troll))
sprawdz("1e _droga_do: ZAPAS=1 daje drogę ze skosami w limicie",
        (lambda d: d is not None and len(d) <= cavebot.POSCIG_SKOSY_MAX_DL)(b._droga_do(START_SK, CEL_SK, [])))
cavebot.POSCIG_SKOSY_ZAPAS = 0
sprawdz("1f _droga_do: ZAPAS=0 brak drogi", b._droga_do(START_SK, CEL_SK, []) is None)
cavebot.POSCIG_SKOSY_ZAPAS = 1
lim0 = cavebot.POSCIG_SKOSY_MAX_DL
cavebot.POSCIG_SKOSY_MAX_DL = 3
sprawdz("1g limit długości: za krótki limit = brak drogi", b._droga_do(START_SK, CEL_SK, []) is None)
cavebot.POSCIG_SKOSY_MAX_DL = lim0

# linia "Odpuszczam ... za ścianą": ignorowany troll odzyskany, gdy droga skośna istnieje
mob = {"id": 77, "nazwa": "Troll", "x": CEL_SK[0], "y": CEL_SK[1], "z": 8, "hp": 100, "gracz": False}
for zap, oczek in ((0, False), (1, True)):
    cavebot.POSCIG_SKOSY_ZAPAS = zap
    b.ignor_droga_cache.clear()
    odl = max(abs(START_SK[0] - CEL_SK[0]), abs(START_SK[1] - CEL_SK[1]))
    w = b._ignor_droga_otwarta(mob, START_SK, odl, 0.0)
    sprawdz(f"1h _ignor_droga_otwarta ZAPAS={zap} -> {oczek}", w is oczek, f"{w}")
cavebot.POSCIG_SKOSY_ZAPAS = 1

# --- 2. drzwi: droga ---
cavebot.PATROL_DRZWI = 0
s = Swiat2((32504, 32270, 8)); b = zrob2(s, list(troll))
sprawdz("2a PATROL_DRZWI=0: drzwi to ściana (brak drogi za drzwi)", b.droga((32503, 32270, 8), (32507, 32270), [], 1, skosy=False) is None)
cavebot.PATROL_DRZWI = 1
b = zrob2(s, list(troll))
dd = b.droga((32503, 32270, 8), (32507, 32270), [], 1, skosy=False)
sprawdz("2b PATROL_DRZWI=1: droga przez pole drzwi", dd is not None and (32505, 32270, 8) in [tuple(q) for q in dd], f"{dd}")
b.sciany[(32505, 32270, 8)] = 0.0
sprawdz("2c nauczona ściana na drzwiach nie zamyka drogi", b.droga((32503, 32270, 8), (32507, 32270), [], 1, skosy=False) is not None)

# --- 3. drzwi w pościgu ---
CEL_D = (32508, 32270)
LOG.clear()
s = Swiat2((32503, 32270, 8)); b = zrob2(s, list(troll))
w, n = poscig(b, s, CEL_D, 80)
sprawdz("3a zamknięte drzwi: Use, potem dojście do celu", w is True and s.uzycia.count(DR) >= 1 and STAN["otwarte"], f"{w} uz={s.uzycia} poz={s.poz}")
sprawdz("3b Use tylko z pola obok drzwi", all(True for _ in s.uzycia) and s.poz[0] >= 32505, f"{s.poz}")
sprawdz("3c udane drzwi: bez notatki o odpuszczeniu", not any("nie otwierają" in l for l in LOG))

LOG.clear()
s = Swiat2((32503, 32270, 8), drzwi_dzialaja=False); b = zrob2(s, list(troll))
w, n = poscig(b, s, CEL_D, 200)
sprawdz("3d drzwi niedziałające: max 3 Use, potem odpuszczenie (None)", w is None and s.uzycia.count(DR) == 3, f"{w} uz={len(s.uzycia)}")
for _ in range(10):
    b.podejdz(CEL_D, tuple(s.poz), pilne=True, natychmiast=True, poscig=True, objazd=True)
    s.t += 0.5
sprawdz("3e jedna notatka i brak kolejnych Use", sum("nie otwierają" in l for l in LOG) == 1 and s.uzycia.count(DR) == 3,
        f"notatki={sum('nie otwierają' in l for l in LOG)} uz={len(s.uzycia)}")
s.t += cavebot.DRZWI_ODPUSC_S + 1
w, n = poscig(b, s, CEL_D, 200)
sprawdz("3f po DRZWI_ODPUSC_S s drzwi próbowane znów (znów max 3 Use)", s.uzycia.count(DR) == 6, f"uz={len(s.uzycia)}")

# drzwi otwarte od początku: żadnego Use
STAN["otwarte"] = False
s = Swiat2((32503, 32270, 8)); b = zrob2(s, list(troll)); STAN["otwarte"] = True
w, n = poscig(b, s, CEL_D, 80)
sprawdz("3g drzwi otwarte: dojście bez Use", w is True and not s.uzycia, f"{w} uz={s.uzycia}")

# --- 4. drzwi w patrolu (łącznik z miejsca_troll.json przez pole drzwi) ---
def patrol_do_pokoju(dzialaja):
    random.seed(1); LOG.clear()
    s = Swiat2(START, gora="use", drzwi_dzialaja=dzialaja)
    s.poz[:] = [32502, 32270, 8]
    b = zrob2(s, list(troll), okrazenia=999)
    b._patrol_wczytaj()
    m = next(x for x in b.miejsca if x["nazwa"] == "z8_spawn_32507_32268")
    b.patrol = b._patrol_nowy(tuple(s.poz), m, "test", waga=1.0); b.patrol_pierwszy = False
    for i in range(4000):
        if not b.tick():
            break
        if any(q[:2] == (m["x"], m["y"]) and q[2] == 8 for q in s.odwiedzone):
            break
    return s, b, m

cavebot.PATROL_DRZWI = 1
s, b, m = patrol_do_pokoju(True)
dosz = any(q[:2] == (m["x"], m["y"]) and q[2] == 8 for q in s.odwiedzone)
sprawdz("4a patrol: zamknięte drzwi -> Use, dojście do pokoju", dosz and s.uzycia.count(DR) >= 1, f"uz={s.uzycia} poz={s.poz} t={s.t:.0f}")
s, b, m = patrol_do_pokoju(False)
sprawdz("4b patrol: drzwi niedziałające = max 3 Use", s.uzycia.count(DR) <= 3 and s.uzycia.count(DR) >= 1, f"uz={len(s.uzycia)}")
sprawdz("4c patrol: jedna notatka o odpuszczeniu drzwi", sum("nie otwierają" in l for l in LOG) == 1,
        f"{sum('nie otwierają' in l for l in LOG)}")

# --- 5. pokrętła ---
import json as _json
import pokretla
sprawdz("5a pokrętła w ZAKRESY i KIERUNEK", all(k in pokretla.ZAKRESY and k in pokretla.KIERUNEK for k in ("POSCIG_SKOSY_ZAPAS", "PATROL_DRZWI")))
przyklad = _json.loads((KAT / "na_zywo.przyklad.json").read_text())
sprawdz("5b na_zywo.przyklad.json: oba pokrętła = 1", przyklad.get("POSCIG_SKOSY_ZAPAS") == 1 and przyklad.get("PATROL_DRZWI") == 1)
sprawdz("5c domyślne w kodzie = 1 (stan sprzed testu)", sk0[0] == 1 and sk0[2] == 1, f"{sk0}")
dj = _json.loads((KAT / "trasy" / "drzwi_jaskinia.json").read_text())
sprawdz("5d trasy/drzwi_jaskinia.json: drzwi (32505,32270,8)", dj["drzwi"][0]["pole"] == [32505, 32270, 8])

cavebot.POSCIG_SKOSY_ZAPAS, cavebot.POSCIG_SKOS_AWARYJNY, cavebot.PATROL_DRZWI = sk0
print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
