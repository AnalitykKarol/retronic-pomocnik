"""CUDZY_MOB: po zobaczeniu obcego gracza nie bierzemy poranionego moba, którego sami nie zaczęliśmy (bez X11)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cavebot, pokretla

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

LOGI = []
cavebot.log = lambda *a: LOGI.append(" ".join(map(str, a)))
f = cavebot.Cavebot._cudzy_mob_filtr

def cb(t=1000.0, gracz_t=None, moje=(), spadek=-1e9):
    s = types.SimpleNamespace(
        zegar=lambda: t, patrol_gracze_pam={}, moje_cele={i: t for i in moje}, cudzy_log={}, hp_gracza_spadek=spadek)
    if gracz_t is not None:
        s.patrol_gracze_pam["Thanos"] = (0, 0, 8, gracz_t)
    return s

POZ = (100, 100, 8)
def mob(i, hp, dx=3, dy=0): return {"id": i, "nazwa": "Troll", "x": POZ[0] + dx, "y": POZ[1] + dy, "z": 8, "hp": hp}
KAND = [mob(1, 100), mob(2, 78), mob(3, 20)]
ids = lambda l: [s["id"] for s in l]

cavebot.CUDZY_MOB, cavebot.CUDZY_MOB_S = 1, 60.0
sprawdz("1 bez gracza: wszystkie moby", ids(f(cb(), KAND, POZ)) == [1, 2, 3])
sprawdz("2 gracz widziany 10 s temu: tylko pełne HP", ids(f(cb(gracz_t=990.0), KAND, POZ)) == [1])
sprawdz("3 gracz widziany 61 s temu: wszystkie", ids(f(cb(gracz_t=939.0), KAND, POZ)) == [1, 2, 3])
sprawdz("4 ranny mob, ale nasz (moje_cele): wolno", ids(f(cb(gracz_t=990.0, moje=(2,)), KAND, POZ)) == [1, 2])
sprawdz("5 ranny mob gryzie nas w odl <= 2: wolno", ids(f(cb(gracz_t=990.0, spadek=999.0), [mob(2, 78, 2, 0)], POZ)) == [2])
sprawdz("6 ranny mob gryzie, ale odl 3: nadal cudzy", ids(f(cb(gracz_t=990.0, spadek=999.0), [mob(2, 78, 3, 0)], POZ)) == [])
sprawdz("7 log o pominięciu jest", any("cudzego moba" in l for l in LOGI), LOGI[-1:] )
c = cb(gracz_t=990.0); LOGI.clear(); f(c, KAND, POZ); f(c, KAND, POZ)
sprawdz("8 log bez spamu (2 wpisy na 2 moby, nie 4)", len(LOGI) == 2, LOGI)
sprawdz("11 ranny mob tuż obok (odl 1), bez gryzienia: wolno (bije nas słabo; przy graczu rozstrzyga unikanie)",
        ids(f(cb(gracz_t=990.0), [mob(2, 78, 1, 0), mob(3, 20, 1, 1)], POZ)) == [2, 3])
sprawdz("12 ranny mob w odl 2 bez gryzienia: nadal cudzy", ids(f(cb(gracz_t=990.0), [mob(2, 78, 2, 0)], POZ)) == [])
cavebot.CUDZY_MOB = 0
sprawdz("9 pokrętło 0: bez filtra", ids(f(cb(gracz_t=990.0), KAND, POZ)) == [1, 2, 3])
sprawdz("10 pokrętła zarejestrowane, domyślnie 0", "CUDZY_MOB" in pokretla.ZAKRESY and "CUDZY_MOB_S" in pokretla.ZAKRESY)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
