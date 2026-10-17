"""Lina i dziura w jaskini goblinów Edron (17.10): plan trasy (gobliny_edron_do_depo / z_depo) musi zgadzać się z przejściem
nagranym na żywo (dane_tibia/nagrania/gobliny_edron_lina_potw.json, 23:15): lina z (33107,31846,z8) na polu (33107,31847,z8)
-> lądowanie (33107,31848,z7); zejście z (33107,31848,z7) przez otwór (33107,31847,z7) -> (33107,31847,z8)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KAT))
import wypad, mapa

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

m = mapa.Mapa()
T = lambda p: [tuple(x) for x in json.load(open(KAT / p))]
do_depo, z_depo = T("trasy/gobliny_edron_do_depo.json"), T("trasy/gobliny_edron_z_depo.json")
nagranie = T("dane_tibia/nagrania/gobliny_edron_lina_potw.json")

def przejscia(punkty):
    """(a, b) kolejnych punktów na różnych piętrach."""
    return [(a, b) for a, b in zip(punkty, punkty[1:]) if a[2] != b[2]]

# --- co nagrała gra: w górę z (33107,31846,8) ląduje (33107,31848,7); w dół z (33107,31848,7) ląduje (33107,31847,8) ---
gora = [(a, b) for a, b in przejscia(nagranie) if b[2] < a[2]]
dol = [(a, b) for a, b in przejscia(nagranie) if b[2] > a[2]]
sprawdz("N1 nagranie: każde wejście liną z (33107,31846,8) ląduje w (33107,31848,7) (2 próby)",
        len(gora) == 2 and all(a == (33107, 31846, 8) and b == (33107, 31848, 7) for a, b in gora), gora)
sprawdz("N2 nagranie: zejście z (33107,31848,7) ląduje w (33107,31847,8) (2 próby)",
        len(dol) == 2 and all(a == (33107, 31848, 7) and b == (33107, 31847, 8) for a, b in dol), dol)

# --- plan: etapy zbudowane regułami wypad.zbuduj_etapy mają dać te same współrzędne ---
e = wypad.zbuduj_etapy(do_depo, m)
lina = [x for x in e if x["typ"] == "LINA"][0]
sprawdz("P1 do_depo: pierwsze przejście to LINA ze stania (33107,31846,8) na polu (33107,31847,8), lądowanie (33107,31848,7)",
        (tuple(lina["stoi"]), tuple(lina["cel"]), tuple(lina["ladunek"])) == ((33107, 31846, 8), (33107, 31847, 8), (33107, 31848, 7)), lina)
sprawdz("P2 do_depo: stanie sąsiaduje z polem liny (bot użyje liny z odległości 1)",
        max(abs(lina["stoi"][0] - lina["cel"][0]), abs(lina["stoi"][1] - lina["cel"][1])) <= 1)
sprawdz("P3 do_depo: pole liny (33107,31847,8) jest chodliwe w mapie (flaga 2 nie ustawiona), a (33107,31847,7) to otwór (flaga 2)",
        m.pole(33107, 31847, 8)[0] & 2 == 0 and m.pole(33107, 31847, 7)[0] & 2 == 2, (m.pole(33107, 31847, 8), m.pole(33107, 31847, 7)))
e2 = wypad.zbuduj_etapy(z_depo, m)
dz = [x for x in e2 if x["typ"] == "DZIURA"][-1]
sprawdz("P4 z_depo: ostatnie przejście to DZIURA (33107,31847,7) ze stania (33107,31848,7), lądowanie (33107,31847,8), pewna",
        (tuple(dz["stoi"]), tuple(dz["dziura"]), tuple(dz["ladunek"]), dz["pewna"]) == ((33107, 31848, 7), (33107, 31847, 7), (33107, 31847, 8), True), dz)
sprawdz("P5 z_depo: dziura sąsiaduje ze staniem", max(abs(dz["stoi"][0] - dz["dziura"][0]), abs(dz["stoi"][1] - dz["dziura"][1])) <= 1)

# --- dawne błędne założenie nie wraca ---
sprawdz("P6 żadna trasa nie zawiera już (33107,31845,8) ani (33107,31846,8) jako lądowania ani hipotezy (33107,31847,7)->(33107,31846,8)",
        (33107, 31845, 8) not in do_depo and not any(a == (33107, 31847, 7) and b[2] == 8 and b[:2] == (33107, 31846)
                                                      for a, b in zip(z_depo, z_depo[1:])),
        [p for p in do_depo[:8]])
sprawdz("P7 meta do_depo: indeks opisu przesunięty o usunięte 2 punkty i wskazuje punkt trasy nagranej",
        any(s["typ"] == "opis" and s["idx"] == 91 for s in json.load(open(KAT / "trasy/gobliny_edron_do_depo.meta"))["specjalne"]))

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
