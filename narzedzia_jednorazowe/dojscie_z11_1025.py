#!/usr/bin/env python3
"""25.10 (Karol: Hammburger na z11, test drzwi w Ab'Dendriel): trasy/abdendriel_depo_do_z11 = prefiks abdendriel_depo_do_z12 (idx 0..89, koniec = pole liny z11
(32668,31625,z11) = start pętli abdendriel_trolle_z11_petla) + wpis mapy abdendriel_trolle_z11_z9. Jedna geometria z dojściem do z12 (bez dublowania).
Cofnięcie: usuń trasy/abdendriel_depo_do_z11.*, przywróć mapy.json.bak-20261025-z11-z9."""
import json
import sys
from pathlib import Path
sys.dont_write_bytecode = True
R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R))
import trasa_io

pts, meta = trasa_io.wczytaj("abdendriel_depo_do_z12")
K = 89                                   # idx lądowania z11 (32668,31625,11)
assert tuple(pts[K]) == (32668, 31625, 11), pts[K]
nowe = pts[:K + 1]
m2 = [dict(s) for s in meta if s["idx"] <= K and s["typ"] != "koniec"]
m2.append({"idx": K, "typ": "koniec", "komentarz": "start pętli abdendriel_trolle_z11_petla (lądowanie z11 = pole liny, zejść z niego); 25.10: prefiks abdendriel_depo_do_z12"})
print("zapisano", trasa_io.zapisz("abdendriel_depo_do_z11", nowe, m2))
plik = R / "mapy.json"
m = json.loads(plik.read_text())
m["abdendriel_trolle_z11_z9"] = {
    "opis": "25.10 (Karol: Hammburger na z11, test drzwi na klucz w Ab'Dendriel): pętla z11 jak abdendriel_trolle_z11, dojście abdendriel_depo_do_z11 (90 pkt: z depo/z8/z9 przez dwoje drzwi i dziury z9->z10->z11, prefiks dojścia do z12), dojscie_z_dowolnego_pietra. Powrót: plan abdendriel_trolle_z12 (ma punkty 'do' na z11).",
    "trasa": "abdendriel_trolle_z11_petla", "potwory": "Troll", "prog_hp": 30,
    "dojscie": "abdendriel_depo_do_z11", "dojscie_z_dowolnego_pietra": True}
plik.write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n")
print("mapy.json: dodano abdendriel_trolle_z11_z9")
