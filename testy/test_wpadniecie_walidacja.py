"""WPADNIECIE_WALIDACJA (domyślnie 0): fałszywa dziura po zejściu schodami (audyt 16.10). Atrapy, bez gry."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, types
sys.dont_write_bytecode = True
_R = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _R)
import cavebot, mapa as _mapa, wpadniecie, pokretla
from pathlib import Path

ok = []
def sprawdz(n, w, i=""):
    w = bool(w); ok.append(w); print(("OK  " if w else "FAIL"), n, i)

M = _mapa.Mapa()
TELE = []
class Cb:
    mapa = M; cel = None; stan = None
    tele = types.SimpleNamespace(zdarzenie=lambda t, **d: TELE.append((t, d)))
    def zatrzymaj_klik(s, p): pass
    def _wypad_reset_klik(s): pass
    def _trasa_na_pietrze(s, z): return True

def wpadnij(p0, p, wal):
    """-> (zbiór dziur po wykryciu, telemetria)."""
    TELE.clear()
    w = wpadniecie.Wpadniecie(Cb(), konf=types.SimpleNamespace(WPADNIECIE_WALIDACJA=wal), log=lambda t: None, plik=None)
    w._trasa_osiagalna = lambda p: True
    w._wykryto(p0, p, 0.0)
    return w.dziury, [t for t in TELE]

SCHODY = ((32500, 32271, 8), (32498, 32271, 9)); FALSZ = (32498, 32271, 8)
PRAWDA = ((33080, 31741, 8), (33081, 31742, 9)); DZIURA = (33081, 31742, 8)
SCH2 = ((32483, 32295, 8), (32482, 32296, 9)); SCH2_POLE = (32482, 32296, 8)

d, _ = wpadnij(*SCHODY, 0); sprawdz("1 schody, walidacja 0: odtworzony błąd, fałszywa dziura", FALSZ in d, d)
d, t = wpadnij(*SCHODY, 1); sprawdz("2 schody, walidacja 1: bez nauki", not d, d)
sprawdz("2b telemetria 'wpadniecie bez dziury na mapie'", any(x[0] == "wpadniecie_bez_dziury" for x in t))
d, _ = wpadnij(*PRAWDA, 0); sprawdz("3 prawdziwa dziura, 0: uczy się", DZIURA in d, d)
d, t = wpadnij(*PRAWDA, 1); sprawdz("4 prawdziwa dziura, 1: uczy się", DZIURA in d, d)
d, _ = wpadnij(*SCH2, 1); sprawdz("5 schody (32482,32296), 1: bez nauki", not d, d)
d, _ = wpadnij(*SCH2, 0); sprawdz("5b te same schody, 0: uczy (jak dziś)", SCH2_POLE in d, d)
_, t0 = wpadnij(*PRAWDA, 0); _, t1 = wpadnij(*PRAWDA, 1)
sprawdz("6 telemetria domyślna bez klucza 'znana'; przy 1 jest", "znana" not in t0[-1][1] and t1[-1][1].get("znana") is False, (t0[-1][1], t1[-1][1]))
w = wpadniecie.Wpadniecie(Cb(), konf=types.SimpleNamespace(WPADNIECIE_WALIDACJA=1), log=lambda t: None, plik=None)
w.dziury.add(DZIURA); w._trasa_osiagalna = lambda p: True; TELE.clear(); w._wykryto(*PRAWDA, 0.0)
sprawdz("6b duplikat przy 1: znana=True", TELE[-1][1].get("znana") is True)

przyklad = json.loads((Path(_R) / "na_zywo.przyklad.json").read_text())
sprawdz("7 pokrętło domyślnie 0, w ZAKRESY, w przykładzie, nie_wyzej",
        cavebot.WPADNIECIE_WALIDACJA == 0 and "WPADNIECIE_WALIDACJA" in pokretla.ZAKRESY
        and przyklad.get("WPADNIECIE_WALIDACJA") == 0 and pokretla.KIERUNEK.get("WPADNIECIE_WALIDACJA") == "nie_wyzej")
print(f"{sum(ok)}/{len(ok)} OK"); sys.exit(0 if all(ok) else 1)
