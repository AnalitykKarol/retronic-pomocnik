import os as _os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import kalibracja_krokow as kal
import sonda_skosu as s

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


class Gra:
    """Wirtualny zegar i postać: krok prosty trwa S, skos D; wciśnięcie w trakcie kroku jest kolejkowane
    (kolejka 1) albo odrzucane (kolejkuj=False); skos zepsuty: klawisz bez efektu."""
    def __init__(s_, S=0.33, D=0.66, kolejkuj=True, zepsute=(), potwor_po=None):
        s_.t = 0.0; s_.S, s_.D, s_.kolejkuj, s_.zepsute = S, D, kolejkuj, set(zepsute)
        s_.poz = [100, 100, 7]; s_.zdarzenia = []     # (t_zmiany, (dx,dy))
        s_.zajety_do = 0.0; s_.wyslane = []; s_.potwor_po = potwor_po
    def _stan(s_):
        p = [100, 100, 7]
        for t, (dx, dy) in s_.zdarzenia:
            if t <= s_.t:
                p[0] += dx; p[1] += dy
        return tuple(p)
    def zegar(s_): return s_.t
    def spij(s_, d): s_.t += d
    def pozycja(s_): return s_._stan()
    def _ruch(s_, nazwa, ms):
        s_.t += ms / 1000; s_.wyslane.append(nazwa)
        if nazwa in s_.zepsute: return
        dx, dy = s.WEKTOR[nazwa]
        if s_.t < s_.zajety_do and not s_.kolejkuj: return
        start = max(s_.t + 0.05, s_.zajety_do)
        s_.zdarzenia.append((start, (dx, dy)))
        s_.zajety_do = start + (s_.D if dx and dy else s_.S)
    def wcisnij(s_, nazwa, ms): s_._ruch(nazwa, ms)
    def skos(s_, nazwa, ms, tryb): s_._ruch(nazwa, ms)
    def stwory(s_):
        return [{"nazwa": "Rat"}] if s_.potwor_po is not None and s_.t > s_.potwor_po else []
    def env(s_):
        e = kal.Srodowisko(zegar=s_.zegar, spij=s_.spij, pozycja=s_.pozycja, wcisnij=s_.wcisnij,
                           stwory=s_.stwory, hp=lambda: 100.0, przechodnie=lambda x, y, z: True)
        e.skos = s_.skos
        return e

g = Gra()
zap, tr, prz = s.uruchom(g.env(), "numpad", 3)
w = s.analiza(zap, tr, "numpad")
sprawdz("bez przerwania, wrócił na start", prz is None and g.pozycja()[:2] == (100, 100), (prz, g.pozycja()))
sprawdz("krok prosty ~0.33 s", w["krok_prosty_s"] and abs(w["krok_prosty_s"] - 0.33) < 0.05, w["krok_prosty_s"])
sprawdz("krok po skosie ~0.66 s, mnożnik ~2", w["mnoznik"] and abs(w["mnoznik"] - 2.0) < 0.2, w["mnoznik"])
sprawdz("skos dwa razy wolniejszy: nie opłaca się", w["rekomendacja"]["skos_oplaca_sie"] is False, w["rekomendacja"])
sprawdz("klawisze działają", w["rekomendacja"]["klawisze_dzialaja"] is True)

g = Gra(S=0.33, D=0.40)
zap, tr, prz = s.uruchom(g.env(), "numpad", 3)
w = s.analiza(zap, tr, "numpad")
sprawdz("skos 1.2x prostego: opłaca się", w["rekomendacja"]["skos_oplaca_sie"] is True and 1.0 < w["mnoznik"] < 1.4, w)

g = Gra(zepsute={"UpRight"})
zap, tr, prz = s.uruchom(g.env(), "numpad", 2)
sprawdz("zepsuty klawisz: przerwanie z komunikatem i powrót na start", prz and "UpRight" in prz and g.pozycja()[:2] == (100, 100), (prz, g.pozycja()))
w = s.analiza(zap, tr, "numpad")
sprawdz("analiza po przerwaniu: klawisze nie działają", w["rekomendacja"]["klawisze_dzialaja"] is False)

g = Gra(potwor_po=2.0)
zap, tr, prz = s.uruchom(g.env(), "numpad", 2)
sprawdz("potwór w widoku przerywa", prz and "potwór" in prz and g.pozycja()[:2] == (100, 100), (prz, g.pozycja()))

g = Gra(kolejkuj=False)
zap, tr, prz = s.uruchom(g.env(), "numpad", 2)
w = s.analiza(zap, tr, "numpad")
sprawdz("odrzucane wciśnięcia w trakcie kroku: zlicza się, pomiar kończy się bez wyjścia poza 3x3",
        max(abs(g.pozycja()[0] - 100), abs(g.pozycja()[1] - 100)) <= 1 and w["lancuch_odrzucone"] is not None)
print(f"\n{sum(ok)}/{len(ok)} OK"); sys.exit(0 if all(ok) else 1)
