import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""Testy nagrywania tras: symulowane pozycje, STOP, odwrócenie, przycięcie, walidacja, dojście."""
import json, sys, tempfile
from pathlib import Path
sys.dont_write_bytecode = True
P = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(P))
import nagraj_trase as N, trasa_io, przytnij_trase, odwroc_trase, waliduj_trase, mozg, mapa as M

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
def nagraj_liste(pozycje, krok=4, dt=0.25):
    r = N.Rejestrator(krok); t = 0.0
    for p in pozycje:
        r.probka(t, p); t += dt
    r.zakoncz()
    return r

# 1. prosta 20 pól na wschód: punkty co ~krok, bez dziur
prosta = [(100 + i, 100, 7) for i in range(21)]
r = nagraj_liste(prosta, 4)
odstepy = [cheb(a, b) for a, b in zip(r.punkty, r.punkty[1:])]
sprawdz("1a punkty na prostej co 4 pola", r.punkty[0] == (100, 100, 7) and r.punkty[-1] == (120, 100, 7)
        and all(o == 4 for o in odstepy), odstepy)
sprawdz("1b liczba punktów rozsądna", len(r.punkty) == 6, len(r.punkty))

# 2. zakręt: 6 w prawo, 6 w dół - narożnik zapisany, odcinki proste
L = [(100 + i, 100, 7) for i in range(7)] + [(106, 100 + i, 7) for i in range(1, 7)]
r = nagraj_liste(L, 5)
sprawdz("2a narożnik w trasie (±1 pole)", any(cheb(p, (106, 100, 7)) <= 1 for p in r.punkty[1:-1]), r.punkty)
sprawdz("2b odstępy <= krok", all(cheb(a, b) <= 5 for a, b in zip(r.punkty, r.punkty[1:])), r.punkty)
sprawdz("2c koniec zapisany", r.punkty[-1] == (106, 106, 7))

# 3. powrót tą samą drogą (zawracanie) zapisuje punkt zwrotu
tam_i_z_powrotem = [(100 + i, 100, 7) for i in range(3)] + [(100 + i, 100, 7) for i in range(1, -1, -1)] + [(100 - i, 100, 7) for i in range(1, 4)]
r = nagraj_liste(tam_i_z_powrotem, 4)
sprawdz("3 zawrócenie: punkt zwrotu (102,100)", (102, 100, 7) in r.punkty, r.punkty)

# 4. zmiana piętra: punkt przed + po, typ specjalny
Z = [(200 + i, 300, 7) for i in range(3)] + [(202, 299, 6), (203, 299, 6), (204, 299, 6)]
r = nagraj_liste(Z, 4)
typy = [s["typ"] for s in r.specjalne]
sprawdz("4a zmiana piętra oznaczona", "schody_w_gore" in typy and "przed_zmiana_pietra" in typy, typy)
i = [s["idx"] for s in r.specjalne if s["typ"] == "schody_w_gore"][0]
sprawdz("4b punkt po zmianie na piętrze 6, poprzedni na 7", r.punkty[i][2] == 6 and r.punkty[i-1] == (202, 300, 7), r.punkty)
sprawdz("4c komentarz niepusty", all(s["komentarz"] for s in r.specjalne))

# 5. teleport na tym samym piętrze (skok > 2 pól w < 1 s)
T = [(300, 300, 7), (301, 300, 7), (340, 310, 7), (341, 310, 7)]
r = nagraj_liste(T, 4)
sprawdz("5a teleport wykryty", any(s["typ"] == "teleport" for s in r.specjalne), r.specjalne)
sprawdz("5b ten sam skok powoli (3 s) to nie teleport", not any(
    s["typ"] == "teleport" for s in nagraj_liste([(300, 300, 7), (303, 300, 7)], 4, dt=3.0).specjalne))

# 6. stanie w miejscu nie dodaje punktów
r = nagraj_liste([(1, 1, 7)] * 50, 4)
sprawdz("6 bezruch = 1 punkt", len(r.punkty) == 1, r.punkty)

# 7. pętla nagrywania: plik STOP_NAGRYWANIA, zapis przyrostowy, powiadomienie
tmp = Path(tempfile.mkdtemp())
stop = tmp / "STOP_NAGRYWANIA"
poz = iter(prosta + [(120, 100, 7)] * 100)
licznik = {"n": 0, "t": 0.0, "wid": []}
def czytaj():
    licznik["n"] += 1
    if licznik["n"] == 40:
        stop.write_text("")
    if licznik["n"] == 10:   # w trakcie: plik trasy już istnieje i ma punkty
        licznik["wid"] = json.loads((tmp / "t1.json").read_text())
    return next(poz)
def zegar(): return licznik["t"]
def spij(s): licznik["t"] += s
pow_ = []
r = N.nagrywaj("t1", krok=4, czytaj=czytaj, zegar=zegar, spij=spij, stop_plik=stop, katalog=tmp,
               wypisz=lambda *a: None, powiadomienie=lambda t, s: pow_.append((t, s)))
dane = json.loads((tmp / "t1.json").read_text())
sprawdz("7a trasa zapisana po STOP", dane[0] == [100, 100, 7] and dane[-1] == [120, 100, 7], dane)
sprawdz("7b zapis przyrostowy w trakcie", len(licznik["wid"]) >= 2, licznik["wid"])
sprawdz("7c STOP usunięty, brak .partial", not stop.exists() and not (tmp / "t1.json.partial").exists())
sprawdz("7d powiadomienie 'Trasa zapisana'", pow_ and pow_[0][0] == "Trasa zapisana", pow_)
try:
    N.nagrywaj("t1", czytaj=lambda: (1, 1, 7), stop_plik=stop, katalog=tmp, wypisz=lambda *a: None)
    sprawdz("7e nie nadpisuje bez --nadpisz", False)
except FileExistsError:
    sprawdz("7e nie nadpisuje bez --nadpisz", True)

# 8. bezczynność > 10 min kończy nagranie; kopia .partial powstaje co 30 s
licznik.update(n=0, t=0.0)
czas_partial = []
def czytaj2():
    if (tmp / "t2.json.partial").exists(): czas_partial.append(licznik["t"])
    return (5, 5, 7) if licznik["t"] < 5 else (10, 5, 7)
r = N.nagrywaj("t2", krok=4, czytaj=czytaj2, zegar=zegar, spij=spij, stop_plik=stop, katalog=tmp,
               wypisz=lambda *a: None, powiadomienie=lambda *a: None, bezczynnosc_min=10)
sprawdz("8a koniec po bezczynności ~10 min", 600 < licznik["t"] < 620, licznik["t"])
sprawdz("8b kopia .partial powstawała w trakcie", len(czas_partial) > 10 and min(czas_partial) >= 30, czas_partial[:1])

# 9. przycięcie i odwrócenie (z meta)
punkty = [(1, 1, 7), (2, 1, 7), (3, 1, 7), (3, 1, 6), (4, 1, 6), (5, 1, 6)]
meta = [{"idx": 3, "typ": "schody_w_gore", "komentarz": "x"}]
tp, tm = przytnij_trase.przytnij(punkty, meta, 2, 4)
sprawdz("9a przycięcie od..do włącznie", tp == punkty[2:5] and tm[0]["idx"] == 1, (tp, tm))
sprawdz("9b meta poza zakresem znika", przytnij_trase.przytnij(punkty, meta, 4, 5)[1] == [])
try:
    przytnij_trase.przytnij(punkty, meta, 4, 2); sprawdz("9c zły zakres odrzucony", False)
except ValueError:
    sprawdz("9c zły zakres odrzucony", True)
op, om = odwroc_trase.odwroc(punkty, meta)
sprawdz("9d odwrócenie: kolejność i piętra przy punktach", op == punkty[::-1] and [p[2] for p in op] == [6, 6, 6, 7, 7, 7], op)
sprawdz("9e meta: idx i kierunek schodów", om[0]["idx"] == 2 and om[0]["typ"] == "schody_w_dol", om)
sprawdz("9f podwójne odwrócenie = oryginał", odwroc_trase.odwroc(op, om)[0] == punkty)
trasa_io.zapisz("a", punkty, meta, tmp)
sprawdz("9g zapis/odczyt round-trip", trasa_io.wczytaj("a", tmp) == (punkty, meta))
sprawdz("9h .meta nie jest trasą (glob *.json)", [p.name for p in tmp.glob("*.json")].count("a.meta") == 0)

# 10. walidacja na prawdziwej mapie
m = M.mapa()
if m is None:
    print("SKIP 10 (brak mapy)")
else:
    kan = [tuple(p) for p in json.loads((P / "trasy/kanaly2.json").read_text())]
    sprawdz("10a kanaly2 bez błędów", [w for w in waliduj_trase.waliduj(kan, m) if w[0] == "BLAD"] == [])
    sciana = (32033, 32150, 11)   # ściana wg test_mapa
    w = waliduj_trase.waliduj([kan[0], sciana], m)
    sprawdz("10b punkt na ścianie = BLAD", any(x[0] == "BLAD" and "ścianie" in x[2] for x in w), w)
    w = waliduj_trase.waliduj([kan[0], (kan[0][0] + 20, kan[0][1], 11)], m)
    sprawdz("10c skok > 12 ostrzeżenie", any("skok" in x[2] for x in w), w)
    w = waliduj_trase.waliduj([kan[0], (kan[0][0], kan[0][1], 10)], m)
    sprawdz("10d zmiana piętra bez błędu drogi", not any("BRAK DROGI" in x[2] for x in w), w)

# 11. dojście: zwykły Cavebot przechodzi punkty dojścia, True przy ostatnim punkcie
class FakeCB:
    def __init__(s, postac, punkty, okr, czas, hp, jedz, potw, gracze, **kw):
        s.postac, s.punkty, s.okr, s.kw = postac, punkty, okr, kw
        FakeCB.ostatni = s
    def uruchom(s): s.postac.poz = s.punkty[-1]
class FakePostac:
    poz = (0, 0, 7)
    def pozycja(s): return s.poz
fp = FakePostac()
sprawdz("11a dojście dotarło", mozg.przejdz_dojscie(fp, [[1, 1, 7], [5, 5, 7]], fabryka=FakeCB) is True)
sprawdz("11b jedno okrążenie", FakeCB.ostatni.okr == 1 and FakeCB.ostatni.punkty[-1] == (5, 5, 7))
class FakeCB2(FakeCB):
    def uruchom(s): s.postac.poz = (1, 1, 7)   # przerwane w pół drogi
sprawdz("11c nieukończone = False", mozg.przejdz_dojscie(FakePostac(), [[1, 1, 7], [50, 5, 7]], fabryka=FakeCB2) is False)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
