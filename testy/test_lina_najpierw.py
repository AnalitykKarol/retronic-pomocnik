"""Lina od pierwszej próby, gdy pole liny w mapie wygląda jak lina (żółte, bez flagi 2): 17.10 bot marnował ~60 s na próby "drabiny"."""
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
POZ, CEL = (33107, 31846, 8), (33107, 31847, 8)

e = [x for x in wypad.zbuduj_etapy(T("trasy/gobliny_edron_do_depo.json"), m) if x["typ"] == "LINA"]
sprawdz("L1 jaskinia goblinów: pierwsza LINA ma lina_pierwsza=True (pole żółte, bez flagi 2)", e[0]["lina_pierwsza"] is True, e[0])
sprawdz("L2 wszystkie liny trasy do depo są rozpoznane z mapy jako liny", all(x["lina_pierwsza"] for x in e), [x.get("lina_pierwsza") for x in e])
sprawdz("L3 liny z do_miasta (sprawdzone w grze jako liny) też",
        all(x["lina_pierwsza"] for x in wypad.zbuduj_etapy(T("trasy/do_miasta.json"), m) if x["typ"] == "LINA"))
k = wypad.zbuduj_etapy(T("trasy/thais_kanaly_do_miasta.json"), m)
kl = [x for x in k if x["typ"] == "LINA"]
sprawdz("L4 przejście o zwykłej podłodze (kolor 121, np. drabina w kanałach Thais): bez lina_pierwsza, stara kolejność",
        kl and not any(x["lina_pierwsza"] for x in kl), [x.get("lina_pierwsza") for x in kl])
sprawdz("L5 bez mapy: brak klucza lina_pierwsza (stare zachowanie)", all("lina_pierwsza" not in x for x in wypad.zbuduj_etapy(T("trasy/gobliny_edron_do_depo.json"), None) if x["typ"] == "LINA"))

stare = wypad.Wypad._proby_drabiny(POZ, CEL)
nowe = wypad.Wypad._proby_drabiny(POZ, CEL, True)
sprawdz("L6 domyślnie dawna kolejność: drabina, drabina, własne, E, W, N, lina (7 prób, lina ostatnia)",
        [t for t, _ in stare] == ["drabina", "drabina", "wlasne", "E", "W", "N", "lina"], stare)
sprawdz("L7 lina_pierwsza: pierwsze dwie próby to lina, dalej dawna kolejność jako zapas",
        [t for t, _ in nowe][:2] == ["lina", "lina"] and [t for t, _ in nowe][2:] == [t for t, _ in stare][:-1], nowe)
sprawdz("L8 próby liną celują w pole liny (33107,31847,8)", all(c == CEL for t, c in nowe if t == "lina"))

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
