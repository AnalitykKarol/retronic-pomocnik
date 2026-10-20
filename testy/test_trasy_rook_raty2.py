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

# --- mapy.json ---
mp = json.load(open(KAT / "mapy.json"))
for k, trasa, pot in (("rook_raty_z9", "rook_raty_z9_petla", "Rat"),
                      ("rook_raty_z10", "rook_raty_z10_petla", "Rat,Cave Rat")):
    e = mp.get(k, {})
    sprawdz(f"M {k}: trasa, potwory {pot}, prog_hp, opis z ostrzeżeniem, BEZ dojścia (wejście nieznane); plik trasy istnieje",
            e.get("trasa") == trasa and "dojscie" not in e and e.get("potwory") == pot and e.get("prog_hp")
            and str(e.get("opis", "")).startswith("UWAGA") and (KAT / "trasy" / f"{trasa}.json").is_file(), e)

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
