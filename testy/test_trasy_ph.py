"""Trasa cave ratów/bugów pod Port Hope z mapy (20.10, generuj_trasy_ph.py): ph_raty_z8_petla i ph_raty_z8_dojscie.
Pętla spójna z mapą klienta (kroki sąsiednie, pola chodliwe, bez schodów/dziur, w tym dziury w dół na z9 przy (32654,32706)),
zamknięta i obejmująca spawny; dojście po z7 bez zmian piętra aż do wejścia (32662,32741,z7) i lądowania na z8
(wejście wywnioskowane z mapy, NIEZWERYFIKOWANE w grze)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KAT))
import mapa, trasa_io

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

m = mapa.Mapa()
dziury = {tuple(p) for p in json.load(open(KAT / "trasy/dziury_nauczone.json"))["dziury"]}
spawny = [s for mo in json.load(open(KAT / "dane_tibia/serwer74/potwory_pelne.json"))["potwory"]
          if mo["nazwa"] in ("cave rat", "bug", "spider") for s in mo.get("spawny", [])
          if s["z"] == 8 and 32640 <= s["x"] <= 32685 and 32695 <= s["y"] <= 32755]

p = trasa_io.wczytaj("ph_raty_z8_petla")[0]
zle_kroki = [(a, b) for a, b in zip(p, p[1:]) if cheb(a, b) > 1 or a[2] != 8 or b[2] != 8]
sprawdz("pętla: wszystkie punkty na z8, każdy krok to sąsiednie pole", p and not zle_kroki, zle_kroki[:3])
zle_pola = [q for q in p if m.flagi(*q) & (mapa.SCIANA | mapa.BEZ_DROGI) or not m.flagi(*q) & mapa.WIDZIANE]
sprawdz("pętla: pola chodliwe, bez schodów/dziur (flaga 2) i niewidzianych", not zle_pola, zle_pola[:3])
sprawdz("pętla: nie wchodzi na dziurę w dół na z9 (32654,32706,8)", (32654, 32706, 8) not in p)
sprawdz("pętla: bez dziur nauczonych", not [q for q in p if q in dziury])
sprawdz("pętla: zamknięta (koniec przy początku)", cheb(p[0], p[-1]) <= 1, (p[0], p[-1]))
pola = {(q[0], q[1]) for q in p}
n = sum(s["ilosc"] for s in spawny if any(cheb((s["x"], s["y"]), q) <= 3 for q in pola))
sprawdz(f"pętla: przechodzi <= 3 pola od spawnów >= 30 potworów (jest {n})", n >= 30, n)

d, meta = trasa_io.wczytaj("ph_raty_z8_dojscie")
sprawdz("dojście: start w środku Port Hope (32623,32772,7)", tuple(d[0]) == (32623, 32772, 7), d[0])
sprawdz("dojście: kończy się wejściem z7 i lądowaniem z8 w (32662,32741)",
        [tuple(q) for q in d[-2:]] == [(32662, 32741, 7), (32662, 32741, 8)], d[-2:])
z7 = d[:-2]
sprawdz("dojście: przed wejściem tylko z7, kroki sąsiednie", all(q[2] == 7 for q in z7) and all(cheb(a, b) <= 1 for a, b in zip(z7, z7[1:])))
sprawdz("dojście: z7 bez schodów/dziur przed wejściem", not [q for q in z7 if m.schody_lub_dziura(*q)], [q for q in z7 if m.schody_lub_dziura(*q)][:3])
sprawdz("dojście: lądowanie na początku pętli", cheb(d[-1], p[0]) <= 1, (d[-1], p[0]))
sprawdz("dojście: meta oznacza przejście jako niezweryfikowane", any("NIEZWERYFIKOWANY" in x.get("komentarz", "") for x in meta), meta)

print(f"{sum(ok)}/{len(ok)} OK" if all(ok) else f"{sum(ok)}/{len(ok)} — BŁĘDY")
sys.exit(0 if all(ok) else 1)
