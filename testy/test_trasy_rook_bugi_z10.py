"""Trasa bugów Rook z10 (20.10, generuj_trasy_rook_bugi_z10.py): pętla spójna z mapą, zamknięta, przy 9 bugach; dojście z7 przez
schody (32050,32187,z7), (32061,32197,z8), (32056,32199,z9) kończy się na z10; start z kieszeni z8 przycina się do 25 punktów.
Przejścia zweryfikowane na żywo 20.10 ~20:36 (Kutangen z kieszeni z8 zszedł na z10 w ok. 25 s i bił bugi)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KAT))
import mapa, trasa_io, mozg

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

m = mapa.Mapa()
dziury = {tuple(p) for p in json.load(open(KAT / "trasy/dziury_nauczone.json"))["dziury"]}
cheb = lambda a, b: max(abs(a[0] - b[0]), abs(a[1] - b[1]))
chodliwe = lambda q: m.flagi(*q) & mapa.WIDZIANE and not m.flagi(*q) & (mapa.SCIANA | mapa.BEZ_DROGI)

p = trasa_io.wczytaj("rook_bugi_z10_petla")[0]
sprawdz("pętla: wszystkie punkty na z10, kroki sąsiednie", all(q[2] == 10 for q in p) and all(cheb(a, b) <= 1 for a, b in zip(p, p[1:])))
sprawdz("pętla: pola chodliwe, bez dziur nauczonych", all(chodliwe(q) and q not in dziury for q in p))
sprawdz("pętla zamknięta", cheb(p[0], p[-1]) <= 1, (p[0], p[-1]))
bugi = [s for mo in json.load(open(KAT / "dane_tibia/serwer74/potwory_pelne.json"))["potwory"] if mo["nazwa"] == "bug"
        for s in mo.get("spawny", []) if s["z"] == 10 and any(cheb((s["x"], s["y"]), q) <= 3 for q in p)]
sprawdz("pętla przechodzi przy >= 9 bugach", sum(s["ilosc"] for s in bugi) >= 9, sum(s["ilosc"] for s in bugi))

d = trasa_io.wczytaj("rook_bugi_z10_dojscie")[0]
sprawdz("dojście: piętra 7,8,9,10 w tej kolejności", [z for i, z in enumerate(q[2] for q in d) if i == 0 or z != d[i - 1][2]] == [7, 8, 9, 10])
sprawdz("dojście kończy się na z10 przy pętli", d[-1][2] == 10 and min(cheb(d[-1], q) for q in p) <= 1, d[-1])
r = mozg.dojscie_od_pozycji(d, (32048, 32188, 8))
sprawdz("start z kieszeni z8 (32048,32188): dojście od schodów z7 lądowanie, nie od z7", r[0][2] == 8 and r[-1] == d[-1], r[0])
mapy = json.load(open(KAT / "mapy.json"))["rook_bugi_z10"]
sprawdz("mapy.json: dojście z dowolnego piętra", mapy.get("dojscie") == "rook_bugi_z10_dojscie" and mapy.get("dojscie_z_dowolnego_pietra") is True)

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
