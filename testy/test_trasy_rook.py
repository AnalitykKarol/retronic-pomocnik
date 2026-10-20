"""Trasy szczurów w Rookgaard z mapy (20.10, generuj_trasy_rook.py): rook_raty_z8 (jaskinia pod miastem, z8) i rook_kanaly_z11.
Pętle muszą być spójne z mapą klienta (kroki sąsiednie, pola chodliwe, bez schodów/dziur i dziur nauczonych), zamknięte i obejmować
spawny szczurów; dojście z8 ma jedno przejście z7 (32046,32221) na z8 (wejście wywnioskowane z mapy, NIEZWERYFIKOWANE w grze);
dojście z11 to odwrócone nagranie do_miasta (przejścia sprawdzone w grze); wpisy mapy.json wskazują istniejące trasy."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KAT))
import mapa, odwroc_trase, trasa_io

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

m = mapa.Mapa()
T = lambda n: trasa_io.wczytaj(n)[0]
dziury = {tuple(p) for p in json.load(open(KAT / "trasy/dziury_nauczone.json"))["dziury"]}
szczury = [s for mo in json.load(open(KAT / "dane_tibia/serwer74/potwory_pelne.json"))["potwory"] if mo["nazwa"] == "rat"
           for s in mo.get("spawny", [])]

def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

def petla_ok(nazwa, z, min_szczurow):
    p = T(nazwa)
    zle_kroki = [(a, b) for a, b in zip(p, p[1:]) if cheb(a, b) > 1 or a[2] != z or b[2] != z]
    sprawdz(f"{nazwa}: wszystkie punkty na z{z}, każdy krok to sąsiednie pole", p and not zle_kroki, zle_kroki[:3])
    zle_pola = [q for q in p if m.flagi(*q) & (mapa.SCIANA | mapa.BEZ_DROGI) or not m.flagi(*q) & mapa.WIDZIANE]
    sprawdz(f"{nazwa}: pola chodliwe w mapie, bez schodów/dziur (flaga 2) i niewidzianych", not zle_pola, zle_pola[:3])
    sprawdz(f"{nazwa}: bez dziur nauczonych (upadek)", not [q for q in p if q in dziury], [q for q in p if q in dziury][:3])
    sprawdz(f"{nazwa}: pętla zamknięta (koniec przy początku)", cheb(p[0], p[-1]) <= 1, (p[0], p[-1]))
    pola = {(q[0], q[1]) for q in p}
    zasieg = [s for s in szczury if s["z"] == z and any(cheb((s["x"], s["y"]), q) <= 3 for q in pola)]
    n = sum(s["ilosc"] for s in zasieg)
    sprawdz(f"{nazwa}: pętla przechodzi w odległości <= 3 pól od spawnów >= {min_szczurow} szczurów (jest {n})", n >= min_szczurow, n)
    return p

p8 = petla_ok("rook_raty_z8_petla", 8, 34)
p11 = petla_ok("rook_kanaly_z11_petla", 11, 33)

# --- dojście z8: jedno przejście z7 -> z8, wejście (32046,32221,7) to pole zmiany piętra po obu stronach ---
d8 = T("rook_raty_z8_dojscie")
przej = [(a, b) for a, b in zip(d8, d8[1:]) if a[2] != b[2]]
sprawdz("D1 rook_raty_z8_dojscie: dokładnie jedno przejście i to z (32046,32221,7) na (32046,32222,8)",
        przej == [((32046, 32221, 7), (32046, 32222, 8))], przej)
sprawdz("D2 wejście (32046,32221): flaga 2 i kolor 210 na z7 oraz na z8 (zmiana piętra w tym polu)",
        all(m.pole(32046, 32221, z)[0] & 2 and m.pole(32046, 32221, z)[1] == 210 for z in (7, 8)),
        [m.pole(32046, 32221, z) for z in (7, 8)])
z7 = [q for q in d8 if q[2] == 7][:-1]       # bez pola wejścia
sprawdz("D3 część z7 dojścia: pola chodliwe, kroki sąsiednie", all(m.flagi(*q) & 1 and not m.flagi(*q) & (4 | 2) for q in z7)
        and all(cheb(a, b) <= 1 for a, b in zip(z7, z7[1:])))
sprawdz("D4 lądowanie (32046,32222,8) należy do składowej pętli z8 (pętla zaczyna się przy nim)", p8[0][:2] == (32046, 32222), p8[0])

# --- dojście z11 = odwrócone do_miasta, kończy się w składowej pętli z11 ---
d11 = T("rook_kanaly_z11_dojscie")
odw, _ = odwroc_trase.odwroc(*trasa_io.wczytaj("do_miasta"))
sprawdz("K1 rook_kanaly_z11_dojscie == odwrócone do_miasta (nagranie sprawdzone w grze)", d11 == odw)
sprawdz("K2 dojście z11 przechodzi pietra 7,8,9,10,11 w tej kolejności", [z for z, _ in __import__("itertools").groupby(q[2] for q in d11)] == [7, 8, 9, 10, 11])
sprawdz("K3 koniec dojścia (32021,32159,11) leży przy pętli z11 (<= 1 pole)", any(cheb(d11[-1], q) <= 1 for q in p11), d11[-1])

# --- mapy.json ---
mp = json.load(open(KAT / "mapy.json"))
for k, trasa, doj in (("rook_raty_z8", "rook_raty_z8_petla", "rook_raty_z8_dojscie"),
                      ("rook_kanaly_z11", "rook_kanaly_z11_petla", "rook_kanaly_z11_dojscie")):
    e = mp.get(k, {})
    sprawdz(f"M {k}: trasa, dojście, potwory Rat, prog_hp, opis; pliki tras istnieją",
            e.get("trasa") == trasa and e.get("dojscie") == doj and e.get("potwory") == "Rat" and e.get("prog_hp") and e.get("opis")
            and (KAT / "trasy" / f"{trasa}.json").is_file() and (KAT / "trasy" / f"{doj}.json").is_file(), e)

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
