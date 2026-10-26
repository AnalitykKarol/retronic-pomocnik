#!/usr/bin/env python3
"""Jednorazowo (26.10): buduje testy/dane/spotkania_graczy/ z PRAWDZIWEJ telemetrii 25.10 (tylko ODCZYT instancje/*) dla testu narzedzia/spotkania_graczy_raport.py.
Przypadki Karola (ręczne liczenie): gerbor/Hammburger Stekt, gebelish/Geblish Flower Power i Hansi, pomszta Apock, wydra (patrol) — niezerowy czas expienia.
Zachowuje próbki z obecnością wskazanych nicków + po jednej sąsiedniej z każdej strony (wynik licznika dla tych nicków jest identyczny jak na pełnych danych),
stwory ograniczone do tych nicków (+ wpis własny); dla wydry: okno 2 h cieniowane co ~8,5 s (czas na spocie). Logi sesji: tylko linie Mózg:/Dojście."""
import json
import re
import sys
from pathlib import Path

KAT = Path(__file__).resolve().parent.parent
CELE = {"gerbor": ["Stekt"], "gebelish": ["Flower Power", "Hansi"], "pomszta": ["Apock"], "wydra": []}
DZIEN = "20261025"
WYJ = KAT / "testy" / "dane" / "spotkania_graczy" / "instancje"


def main():
    for inst, nicki in CELE.items():
        src = KAT / "instancje" / inst / "logi"
        out = WYJ / inst / "logi"
        out.mkdir(parents=True, exist_ok=True)
        post = json.loads((KAT / "instancje" / inst / "profil.json").read_text())["postac"]
        (WYJ / inst / "profil.json").write_text(json.dumps({"postac": post}))
        probki = []
        for l in open(src / f"telemetria-{DZIEN}.jsonl", encoding="utf-8", errors="replace"):
            if '"probka"' not in l:
                continue
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if r.get("typ") == "probka":
                probki.append(r)
        probki.sort(key=lambda r: r["t"])
        keep = set()
        lk = {n.casefold() for n in nicki}
        for i, r in enumerate(probki):
            if any(s.get("gracz") and str(s.get("n")).casefold() in lk for s in r.get("stwory") or ()):
                keep.update((i - 1, i, i + 1))
        if inst == "wydra":
            t0 = probki[len(probki) // 3]["t"]
            ost = None
            for i, r in enumerate(probki):
                if t0 <= r["t"] <= t0 + 7200 and (ost is None or r["t"] - ost >= 8.5):
                    keep.add(i)
                    ost = r["t"]
        wyj = []
        for i in sorted(k for k in keep if 0 <= k < len(probki)):
            r = probki[i]
            st = [s for s in r.get("stwory") or () if s.get("gracz") and (str(s.get("n")).casefold() in lk or str(s.get("n")) == post)]
            wyj.append({"t": r["t"], "typ": "probka", "stan": r.get("stan"), "poz": r["poz"], "hp": r.get("hp"), "sesja": r.get("sesja"), "src": r.get("src"), "stwory": st})
        with open(out / f"telemetria-{DZIEN}.jsonl", "w", encoding="utf-8") as f:
            for r in wyj:
                f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
        # logi sesji: tylko linie istotne dla dojścia (czas zachowany)
        for p in sorted(src.glob("mozg-stdout-10[12][56]-*.log")):
            linie = [l.rstrip("\n") for l in open(p, encoding="utf-8", errors="replace")
                     if re.match(r"^\d\d:\d\d:\d\d (Mózg:|Dojście: trasa|Dojście zakończone)", l)]
            if linie:
                (out / p.name).write_text("\n".join(linie) + "\n", encoding="utf-8")
        print(inst, len(probki), "->", len(wyj))


if __name__ == "__main__":
    sys.exit(main())
