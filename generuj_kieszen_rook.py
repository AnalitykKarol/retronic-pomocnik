#!/usr/bin/env python3
"""Pętla po kieszeni z dziurami na Rook z8 (Pomszta 22:02-22:49, 25.10; Karol: „ten spot był zajebisty, chcę go zapisać”).
Źródło: pola, na których postać faktycznie stała (telemetria) i miejsca zabójstw z logu bota; to dane sprawdzone w grze, bo mapa klienta
nie zna dziur, które zamknęły tę kieszeń. Dozwolone pola = odwiedzone + ich sąsiedzi (8), widziane w mapie, bez ściany/flagi 2 i bez
nauczonych dziur; A* omija resztę. Uruchamiane offline, niczego nie wysyła do gry:

  python3 -I generuj_kieszen_rook.py [--zapisz]      bez --zapisz tylko liczy i drukuje

Zapis: trasy/rook_raty_z8_kieszen_petla.json, dane_tibia/mapy/rook_raty_z8_kieszen.{png,json}, wpis `rook_raty_z8_kieszen` w mapy.json
(kopia mapy.json.bak-20261025-kieszen). BEZ dojścia: wejście do kieszeni nie jest znane (postać wpadła; start bota tylko gdy stoi w kieszeni)."""
import argparse, collections, json, re, shutil, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import mapa as _mapa  # noqa: E402
import spot_lib  # noqa: E402

INST = ROOT / "instancje" / "pomszta" / "logi"
Z = 8
OD_T = 1792960900                 # 25.10 ~21:41 (epoch)
OD_LOG = "22:02"


def wizyty():
    v = collections.Counter()
    for l in (INST / "telemetria-20261025.jsonl").open():
        if '"poz"' not in l:
            continue
        try:
            r = json.loads(l)
        except ValueError:
            continue
        p = r.get("poz")
        if isinstance(p, list) and len(p) == 3 and p[2] == Z and r.get("t", 0) >= OD_T:
            v[(p[0], p[1])] += 1
    return v


def zabicia():
    out = []
    for l in (INST / "mozg-stdout-1025-2004.log").open(errors="replace"):
        m = re.match(r"(\d\d:\d\d):\d\d Cel (.+?) zabity na \((\d+), (\d+), (\d+)\)", l)
        if m and m[1] >= OD_LOG and int(m[5]) == Z:
            out.append((int(m[3]), int(m[4])))
    return out


def klastry(punkty, r=3):
    kl = []
    for p in punkty:
        for k in kl:
            if max(abs(p[0] - k["c"][0]), abs(p[1] - k["c"][1])) <= r:
                k["p"].append(p)
                k["c"] = (round(sum(q[0] for q in k["p"]) / len(k["p"])), round(sum(q[1] for q in k["p"]) / len(k["p"])))
                break
        else:
            kl.append({"c": p, "p": [p]})
    return kl


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m = _mapa.Mapa()
    dz = {(p[0], p[1]) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", []) if p[2] == Z}
    vis = wizyty()
    kill = zabicia()
    dozw = set()
    for (x, y) in vis:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                q = (x + dx, y + dy)
                if q in dz or q in dozw:
                    continue
                if (q in vis) or spot_lib.chodliwe(m, (q[0], q[1], Z)):
                    dozw.add(q)
    xs = [p[0] for p in dozw]; ys = [p[1] for p in dozw]
    zajete = [(x, y, Z) for x in range(min(xs) - 2, max(xs) + 3) for y in range(min(ys) - 2, max(ys) + 3) if (x, y) not in dozw]
    def snap(p):
        return min(dozw, key=lambda c: (max(abs(c[0] - p[0]), abs(c[1] - p[1])), abs(c[0] - p[0]) + abs(c[1] - p[1])))
    kl = [k for k in klastry(kill) if len(k["p"]) >= 2]
    kl.sort(key=lambda k: -len(k["p"]))
    stops = []
    for k in kl[:8]:
        pt = snap(k["c"])
        if all(pt != s["pt"] for s in stops):
            stops.append({"pt": pt, "n": len(k["p"]), "spawny": 1})
    start = snap(max(vis, key=vis.get))
    print(f"pól odwiedzonych {len(vis)}, dozwolonych {len(dozw)}, zabić {len(kill)}, przystanków {len(stops)}, start {start}")
    for s in stops:
        print("  przystanek", s["pt"], "zabić", s["n"])
    order, nodes, pelna = spot_lib.petla(m, Z, start, stops, zajete)
    print(f"pętla {len(pelna)} pól, kolejność {order}")
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    spot_lib.zapis_spotu(m, "rook_raty_z8_kieszen", Z, pelna, order, nodes, stops, "szczury z8, kieszeń z dziurami (Pomszta 25.10)",
                         klucz="zabic", jedn="zab.", opis_przyst="zabić z sesji 25.10",
                         ekstra={"zrodlo": "telemetria + log Pomszta 25.10 22:02-22:49", "dojscie": None})
    mp = ROOT / "mapy.json"
    shutil.copy2(mp, ROOT / "mapy.json.bak-20261025-kieszen")
    d = json.loads(mp.read_text())
    d["rook_raty_z8_kieszen"] = {
        "opis": ("Rookgaard, kieszeń z dziurami w jaskini szczurów z8 (25.10, Pomszta: Karol uznał spot za bardzo dobry). Pętla z faktycznie przejść"
                 " i zabójstw (telemetria + log), BEZ dojścia: wejście nieznane, postać wpadła. Start bota tylko gdy postać już stoi w kieszeni."),
        "trasa": "rook_raty_z8_kieszen_petla", "potwory": "Rat,Cave Rat", "prog_hp": "30"}
    tmp = mp.with_name("mapy.json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    tmp.replace(mp)
    print("zapisano trasy/, dane_tibia/mapy/ i mapy.json")


if __name__ == "__main__":
    main()
