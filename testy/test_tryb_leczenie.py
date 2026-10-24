#!/usr/bin/env python3
"""23.10 zgon odchyda: tryb `ml` (i `ostrozny`) zostawiał ZDROWIE_CZAR_AKTYWNY=0 z szablonu nowej postaci (22.10), więc ML 1 trenował bez exura.
Sprawdza: (1) tryby ostrozny i ml w tryby.json ustawiają ZDROWIE_CZAR_AKTYWNY=1, (2) scalenie do na_zywo.json z 0 daje 1,
(3) tryb.ostrzezenia ostrzega przy ML=1 bez leczenia i milczy po poprawce."""
import os
os.environ["RETRONIC_TESTY"] = "1"
import json, sys, tempfile
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KAT))
import tryb
ok = []
def sprawdz(n, w, i=""):
    ok.append(bool(w)); print(("OK   " if w else "FAIL ") + n + ("" if w else f"  [{i}]"))
T = json.loads((KAT / "tryby.json").read_text())
for n in ("ostrozny", "ml"):
    sprawdz(f"1 tryby.json {n}: ZDROWIE_CZAR_AKTYWNY=1", T[n]["pokretla"].get("ZDROWIE_CZAR_AKTYWNY") == 1, T[n]["pokretla"])
kat = Path(tempfile.mkdtemp())
for tr in ("ml", "ostrozny", "ostrozny,ml"):
    f = kat / "na_zywo.json"; f.write_text(json.dumps({"ZDROWIE_CZAR_AKTYWNY": 0, "ML_CZAR_AKTYWNY": 1, "ZDROWIE_CZAR_HP": 80}))
    rc = tryb.main(["--mapa", "trolle_edron", "--tryb", tr, "--na-zywo", str(f), "--log", str(kat / "tryb.log")])
    po = json.loads(f.read_text())
    sprawdz(f"2 tryb {tr}: na_zywo ZDROWIE_CZAR_AKTYWNY 0 -> 1", rc == 0 and po["ZDROWIE_CZAR_AKTYWNY"] == 1, (rc, po))
    sprawdz(f"2 tryb {tr}: ZDROWIE_CZAR_HP nietknięte", po["ZDROWIE_CZAR_HP"] == 80, po)
sprawdz("3 ML=1 bez leczenia: ostrzeżenie", len(tryb.ostrzezenia({"ML_CZAR_AKTYWNY": 1, "ZDROWIE_CZAR_AKTYWNY": 0})) == 1)
sprawdz("3 ML=1 z leczeniem: cisza", tryb.ostrzezenia({"ML_CZAR_AKTYWNY": 1, "ZDROWIE_CZAR_AKTYWNY": 1}) == [])
sprawdz("3 ML=0, leczenie 0: cisza", tryb.ostrzezenia({"ML_CZAR_AKTYWNY": 0, "ZDROWIE_CZAR_AKTYWNY": 0}) == [])
print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
