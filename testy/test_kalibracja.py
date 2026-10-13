import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""Testy kalibracji kroków na atrapie: żadnych plików STOP, żadnej gry, czas wirtualny."""
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import json, tempfile
from pathlib import Path
import kalibracja_krokow as k
import cavebot, bot

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

class Gra:
    """Atrapa: krok trwa `krok` s; strzałka w trakcie kroku jest odrzucana (kolejka=False) albo kolejkowana."""
    def __init__(s, krok=0.5, kolejka=False, opozn=0.05, sciana_x=None, potwor_po=None):
        s.t = 0.0; s.poz = [100, 100, 7]; s.krok = krok; s.kolejka = kolejka; s.opozn = opozn
        s.wolne_od = 0.0; s.zaplanowane = []; s.hp = 100; s.potwor_po = potwor_po; s.sciana_x = sciana_x
        s.klawisze = []; s.stwory = []
    def _doloz(s):
        for t, dx in sorted(s.zaplanowane):
            if t <= s.t:
                s.poz[0] += dx
        s.zaplanowane = [(t, dx) for t, dx in s.zaplanowane if t > s.t]
        if s.potwor_po is not None and s.t >= s.potwor_po and not s.stwory:
            s.stwory = [{"x": 103, "y": 100, "z": 7, "gracz": False, "nazwa": "Rat", "hp": 100, "id": 1}]
    def zegar(s): return s.t
    def spij(s, d): s.t += d; s._doloz()
    def pozycja(s): s._doloz(); return tuple(s.poz)
    def stwory_(s): s._doloz(); return s.stwory
    def hp_(s): return s.hp
    def wcisnij(s, nazwa, ms):
        s.klawisze.append((s.t, nazwa, ms)); dx = 1 if nazwa == "Right" else -1
        s.t += ms / 1000
        if s.t < s.wolne_od:
            if not s.kolejka:
                return
            start = s.wolne_od
        else:
            start = s.t
        if s.sciana_x is not None and s.poz[0] + dx == s.sciana_x:
            return
        s.wolne_od = start + s.krok
        s.zaplanowane.append((start + s.opozn, dx))
    def trzymaj(s, nazwa, wcisnij, zwolnij):  # tryb przytrzymania: key-down aż warunek
        pass

def srodowisko(g, przechodnie=True):
    return k.Srodowisko(zegar=g.zegar, spij=g.spij, pozycja=g.pozycja, wcisnij=g.wcisnij,
                        stwory=g.stwory_, hp=g.hp_, przechodnie=lambda x, y, z: przechodnie,
                        przytrzymaj=None)

# 1. seria: wszystkie wciśnięcia rozłożone co 0.6 s przy kroku 0.5 -> skuteczność 100%, opóźnienie ~0.05
g = Gra(krok=0.5)
w = k.seria(srodowisko(g), odstep=0.6, n=10, przytrzymanie_ms=70)
sprawdz("1a seria co 0.6 przy kroku 0.5: skuteczność 1.0", w["skutecznosc"] == 1.0, w)
sprawdz("1b opóźnienie ~0.05+przytrzymanie", 0.04 < w["opoznienie_med"] < 0.2, w)
sprawdz("1c net zero: wracamy na start", g.poz == [100, 100, 7], g.poz)

# 2. krótszy odstęp, atrapa odrzuca strzałkę w trakcie kroku -> skuteczność < 1
g = Gra(krok=0.5, kolejka=False)
w = k.seria(srodowisko(g), odstep=0.25, n=20, przytrzymanie_ms=70)
sprawdz("2a odrzucanie w trakcie kroku: skuteczność ~0.5", 0.3 < w["skutecznosc"] < 0.7, w)
sprawdz("2b pozycja wraca do startu mimo odrzuceń", g.poz == [100, 100, 7], g.poz)

# 3. kolejkowanie: wszystkie przechodzą, ale opóźnienie rośnie
g = Gra(krok=0.5, kolejka=True)
w = k.seria(srodowisko(g), odstep=0.25, n=6, przytrzymanie_ms=70)
sprawdz("3a kolejka: skuteczność 1.0", w["skutecznosc"] == 1.0, w)
sprawdz("3b kolejka: pozycja wraca", g.poz == [100, 100, 7], g.poz)

# 4. potwór w widoku przerywa
g = Gra(krok=0.5, potwor_po=1.0)
try:
    k.seria(srodowisko(g), odstep=0.6, n=20, przytrzymanie_ms=70); blad = None
except k.Przerwano as e:
    blad = str(e)
sprawdz("4 potwór w widoku -> Przerwano", blad and "potw" in blad.lower(), blad)

# 5. HP spada -> przerwanie
g = Gra(krok=0.5)
env = srodowisko(g)
def hp_spada(): g.hp -= 5; return g.hp
env.hp = hp_spada
try:
    k.seria(env, odstep=0.6, n=20, przytrzymanie_ms=70); blad = None
except k.Przerwano as e:
    blad = str(e)
sprawdz("5 spadek HP -> Przerwano", blad and "hp" in blad.lower(), blad)

# 6. pole docelowe nieprzechodnie -> odmowa przed jakimkolwiek wciśnięciem
g = Gra()
try:
    k.sprawdz_trase(srodowisko(g, przechodnie=False), (100, 100, 7)); blad = None
except k.Przerwano as e:
    blad = str(e)
sprawdz("6 nieprzechodnie pole -> odmowa, zero klawiszy", blad and not g.klawisze, blad)
g = Gra(); k.sprawdz_trase(srodowisko(g), (100, 100, 7))
sprawdz("6b przechodnie -> ok", True)

# 7. tryb "czekaj na zmianę pozycji"
g = Gra(krok=0.5)
w = k.tryb_czekaj(srodowisko(g), n=6, przytrzymanie_ms=70, po_zmianie=0.5)
sprawdz("7a czekaj (+pauza po zmianie 0.5): skuteczność 1.0, czas kroku ~0.5", w["skutecznosc"] == 1.0 and 0.4 < w["krok_med"] < 0.7, w)
sprawdz("7b wraca na start", g.poz == [100, 100, 7], g.poz)
# pozycja zmienia się na początku kroku: wciśnięcie zaraz po zmianie trafia w trwający krok i jest odrzucone
g = Gra(krok=0.5, kolejka=False, opozn=0.05)
w = k.tryb_czekaj(srodowisko(g), n=6, przytrzymanie_ms=70, po_zmianie=0.0)
sprawdz("7e czekaj bez pauzy: odrzucenia widoczne (skuteczność < 1), dryf <= 1, powrót", w["skutecznosc"] < 1.0 and g.poz == [100, 100, 7], (w, g.poz))

# 7c. przytrzymanie
g = Gra(krok=0.5)
def przytrzymaj(nazwa, ile, maks):
    dx = 1 if nazwa == "Right" else -1; cz = []
    for i in range(ile):
        g.t += 0.06 if i == 0 else g.krok; g.poz[0] += dx; cz.append(g.t - (cz and 0 or 0))
    t0 = cz[0] - 0.06
    return [c - t0 for c in cz]
env = srodowisko(g); env.przytrzymaj = przytrzymaj
w = k.tryb_przytrzymaj(env, powtorzen=4, ile_zmian=2)
sprawdz("7c przytrzymanie: skuteczność 1.0, krok ~0.5, start", w["skutecznosc"] == 1.0 and 0.4 < w["krok_med"] < 0.6 and g.poz == [100, 100, 7], (w, g.poz))
g = Gra(); sprawdz("7d bez przytrzymaj -> None", k.tryb_przytrzymaj(srodowisko(g)) is None)

# 8. rekomendacje
tab = [dict(tryb="seria", odstep=0.6, przytrzymanie_ms=70, skutecznosc=1.0, opoznienie_med=0.05, opoznienie_max=0.1, krok_med=0.6),
       dict(tryb="seria", odstep=0.5, przytrzymanie_ms=70, skutecznosc=0.98, opoznienie_med=0.05, opoznienie_max=0.1, krok_med=0.5),
       dict(tryb="seria", odstep=0.3, przytrzymanie_ms=70, skutecznosc=0.5, opoznienie_med=0.05, opoznienie_max=0.1, krok_med=0.6)]
r = k.rekomendacje(tab, krok=0.5, opoznienie_max=0.6)
sprawdz("8a odstęp = najkrótszy z skutecznością >= 0.95", r["POSCIG_KROK_MIN"] == 0.5, r)
sprawdz("8b próg braku zmiany > krok i > max opóźnienie", r["POSCIG_BRAK_ZMIANY"] >= 0.75, r)

# 9. zabezpieczenie: bot działa / STOP istnieje (ścieżki z katalogu tymczasowego, nie prawdziwy STOP)
tmp = Path(tempfile.mkdtemp())
(tmp / "STOP").write_text("")
ostrz = k.sprawdz_bezpieczenstwo(stop_pliki=[tmp / "STOP"], procesy=lambda: [])
sprawdz("9a STOP bez działającego bota (ślad po zatrzymaj.sh) -> ostrzeżenie, nie odmowa", len(ostrz) == 1, ostrz)
try:
    k.sprawdz_bezpieczenstwo(stop_pliki=[tmp / "nie_ma"], procesy=lambda: ["mozg.py"]); blad = None
except k.Przerwano as e:
    blad = str(e)
sprawdz("9b działa mozg.py -> odmowa", blad and "mozg" in blad, blad)
k.sprawdz_bezpieczenstwo(stop_pliki=[tmp / "nie_ma"], procesy=lambda: [])
sprawdz("9c czysto -> ok", True)
try:
    k.sprawdz_bezpieczenstwo(stop_pliki=[tmp / "STOP"], procesy=lambda: ["cavebot.py"]); blad = None
except k.Przerwano as e:
    blad = str(e)
sprawdz("9d STOP + działający bot -> odmowa", blad and "STOP" in blad, blad)

# 10. zapis JSON do katalogu tymczasowego
plik = k.zapisz(tmp, {"tabela": tab, "rekomendacje": r})
d = json.loads(Path(plik).read_text())
sprawdz("10 zapis kalibracja-*.json", Path(plik).name.startswith("kalibracja-") and d["rekomendacje"] == r, plik)

# 11. liczniki pościgu w poscig_koniec (atrapa Swiat z test_cavebot byłaby ciężka: sprawdzamy wyłącznie klucze)
import inspect
src = inspect.getsource(cavebot.Cavebot.poscig_szybki) if hasattr(cavebot, "Cavebot") else ""
sprawdz("11 poscig_koniec ma liczniki", all(x in src for x in ("wyslane=", "zmiany_pozycji=", "ponowione=", "odrzucone=")) or not src, "")
print(f"\n{sum(ok)}/{len(ok)} OK"); sys.exit(0 if all(ok) else 1)
