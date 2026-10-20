"""Trasy szczurów w Rookgaard, drugi spot (20.10, generuj_trasy_rook_raty2.py): rook_raty_z9 i rook_raty_z10 (dwa piętra tego samego spota).
Pętle muszą być spójne z mapą klienta (kroki sąsiednie, pola chodliwe, bez schodów/dziur i dziur nauczonych), zamknięte i obejmować
spawny szczurów (z10 także jaskiniowych); dojścia to przejścia z7 -> z8 -> z9 (szyb 32046,32188) i z9 -> z10 (32038,32212):
każde przejście stoi na polu z kolorem 210 i flagą 2, a lądowanie jest chodliwe i w składowej pętli. Przejścia NIEZWERYFIKOWANE w grze."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import itertools
import json, sys
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KAT))
import mapa, trasa_io

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

m = mapa.Mapa()
T = lambda n: trasa_io.wczytaj(n)[0]
dziury = {tuple(p) for p in json.load(open(KAT / "trasy/dziury_nauczone.json"))["dziury"]}
potwory = [s for mo in json.load(open(KAT / "dane_tibia/serwer74/potwory_pelne.json"))["potwory"] if mo["nazwa"] in ("rat", "cave rat")
           for s in mo.get("spawny", [])]

def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

def chodliwe(q):
    return m.flagi(*q) & mapa.WIDZIANE and not m.flagi(*q) & (mapa.SCIANA | mapa.BEZ_DROGI)

def petla_ok(nazwa, z, min_potworow):
    p = T(nazwa)
    zle_kroki = [(a, b) for a, b in zip(p, p[1:]) if cheb(a, b) > 1 or a[2] != z or b[2] != z]
    sprawdz(f"{nazwa}: wszystkie punkty na z{z}, każdy krok to sąsiednie pole", p and not zle_kroki, zle_kroki[:3])
    zle_pola = [q for q in p if not chodliwe(q)]
    sprawdz(f"{nazwa}: pola chodliwe w mapie, bez schodów/dziur (flaga 2) i niewidzianych", not zle_pola, zle_pola[:3])
    sprawdz(f"{nazwa}: bez dziur nauczonych (upadek)", not [q for q in p if q in dziury], [q for q in p if q in dziury][:3])
    sprawdz(f"{nazwa}: pętla zamknięta (koniec przy początku)", cheb(p[0], p[-1]) <= 1, (p[0], p[-1]))
    pola = {(q[0], q[1]) for q in p}
    zasieg = [s for s in potwory if s["z"] == z and any(cheb((s["x"], s["y"]), q) <= 3 for q in pola)]
    n = sum(s["ilosc"] for s in zasieg)
    sprawdz(f"{nazwa}: pętla przechodzi w odległości <= 3 pól od spawnów >= {min_potworow} szczurów (jest {n})", n >= min_potworow, n)
    return p

p9 = petla_ok("rook_raty_z9_petla", 9, 27)
p10 = petla_ok("rook_raty_z10_petla", 10, 22)

def przejscia(d):
    return [(a, b) for a, b in zip(d, d[1:]) if a[2] != b[2]]

def dojscie_ok(nazwa, d, oczekiwane_pietra):
    sprawdz(f"{nazwa}: zaczyna się przy depo w mieście (32061,32180,z7)", d[0] == (32061, 32180, 7), d[0])
    sprawdz(f"{nazwa}: piętra w kolejności {oczekiwane_pietra}", [z for z, _ in itertools.groupby(q[2] for q in d)] == oczekiwane_pietra)
    zle = [(a, b) for a, b in zip(d, d[1:]) if a[2] == b[2] and (cheb(a, b) > 1 or not chodliwe(b) and b not in przej_pola(d))]
    sprawdz(f"{nazwa}: na jednym piętrze kroki sąsiednie, pola chodliwe (poza polami przejść)", not zle, zle[:3])

def przej_pola(d):
    return {a for a, b in przejscia(d)}

def przejscie_ok(nazwa, a, b):
    sprawdz(f"{nazwa}: przejście {a} -> {b}: pole {a[:2]} ma kolor 210 i flagę 2 na piętrze {a[2]}",
            m.pole(*a) is not None and m.pole(*a)[0] & 2 and m.pole(*a)[1] == 210, m.pole(*a))
    sprawdz(f"{nazwa}: lądowanie {b} chodliwe i blisko pola przejścia (cheb <= 1)", chodliwe(b) and cheb(a, b) <= 1, (a, b))

d9 = T("rook_raty_z9_dojscie")
dojscie_ok("rook_raty_z9_dojscie", d9, [7, 8, 9])
pr9 = przejscia(d9)
sprawdz("D9 rook_raty_z9_dojscie: dokładnie dwa przejścia, z7 na z8 i z8 na z9, w tym samym polu (32046,32188)",
        len(pr9) == 2 and [(a[2], b[2]) for a, b in pr9] == [(7, 8), (8, 9)] and pr9[0][0][:2] == pr9[1][0][:2] == (32046, 32188), pr9)
for a, b in pr9:
    przejscie_ok("rook_raty_z9_dojscie", a, b)
sprawdz("D9 koniec dojścia leży przy początku pętli z9 (<= 1 pole)", cheb(d9[-1], p9[0]) <= 1, (d9[-1], p9[0]))
pola9 = {(q[0], q[1]) for q in p9}
sprawdz("D9 lądowanie z9 leży w składowej pętli (pole pętli lub pole sąsiednie)", d9[-1][2] == 9 and any(cheb(d9[-1], q) <= 1 for q in p9))

d10 = T("rook_raty_z10_dojscie")
dojscie_ok("rook_raty_z10_dojscie", d10, [7, 8, 9, 10])
pr10 = przejscia(d10)
sprawdz("D10 rook_raty_z10_dojscie: trzy przejścia z7>z8, z8>z9, z9>z10, ostatnie z (32038,32212,9)",
        [(a[2], b[2]) for a, b in pr10] == [(7, 8), (8, 9), (9, 10)] and pr10[2][0] == (32038, 32212, 9), pr10)
for a, b in pr10:
    przejscie_ok("rook_raty_z10_dojscie", a, b)
sprawdz("D10 pierwsze dwa przejścia jak w dojściu z9 (wspólny szyb), reszta dopisana po z9",
        pr10[:2] == pr9 and d10[:len(d9)] == d9, (pr10[:2], pr9))
sprawdz("D10 koniec dojścia leży przy początku pętli z10 (<= 1 pole)", cheb(d10[-1], p10[0]) <= 1, (d10[-1], p10[0]))

# --- meta dojść: typ każdego przejścia opisany (przed_zmiana_pietra + schody_w_dol), liczba wpisów = 2 * liczba przejść ---
for nazwa, d, n in (("rook_raty_z9_dojscie", d9, 2), ("rook_raty_z10_dojscie", d10, 3)):
    _, meta = trasa_io.wczytaj(nazwa)
    typy = [e.get("typ") for e in meta if e.get("typ") in ("przed_zmiana_pietra", "schody_w_dol")]
    sprawdz(f"META {nazwa}: {n} par przed_zmiana_pietra/schody_w_dol", typy == ["przed_zmiana_pietra", "schody_w_dol"] * n, typy)

# --- mapy.json ---
mp = json.load(open(KAT / "mapy.json"))
for k, trasa, doj, pot in (("rook_raty_z9", "rook_raty_z9_petla", "rook_raty_z9_dojscie", "Rat"),
                           ("rook_raty_z10", "rook_raty_z10_petla", "rook_raty_z10_dojscie", "Rat,Cave Rat")):
    e = mp.get(k, {})
    sprawdz(f"M {k}: trasa, dojście, potwory {pot}, prog_hp, opis; pliki tras istnieją",
            e.get("trasa") == trasa and e.get("dojscie") == doj and e.get("potwory") == pot and e.get("prog_hp") and e.get("opis")
            and (KAT / "trasy" / f"{trasa}.json").is_file() and (KAT / "trasy" / f"{doj}.json").is_file(), e)

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
