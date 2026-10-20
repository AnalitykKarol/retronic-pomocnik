#!/usr/bin/env python3
"""Spoty expowe przy Rookgaardzie i miastach z danych serwera 7.4 (monster.db z serwer74/potwory_pelne.json).

Spot = skupisko spawnów na jednym piętrze (punkty spawnu bliżej niż SKLEJ pól łączą się w jeden spot).
Dla spotu liczone:
  sufit_exp_h  suma (ilosc * exp * 3600 / respawn_s): exp/h przy natychmiastowym zabijaniu wszystkiego, co się odradza.
               To GÓRNA GRANICA z respawnu, nie pomiar; realnie ogranicza szybkość zabijania i inni gracze.
  potworow     suma `ilosc` (ile potworów stoi na spocie naraz po pełnym respawnie)
  cios_max     najgroźniejszy potwór spotu: atak_max_szac z potwory.json (zawyżony = bezpieczny), brak -> CipSoft atak x 3,5
  exp_na_hp    średnia ważona exp/hp: jak „opłaca się” bić (wysoko = szybki exp na zadane obrażenia)
Przedziały: rook (wyspa), 8-15 (cios_max <= 45), 15-30 (<= 110); groźniejsze spoty pominięte.
Odległość do świątyni: linia prosta po x,y (bez pięter i ścieżki). Świątynie: standardowe współrzędne 7.4 (do sprawdzenia w kliencie).

  python3 -I dane_tibia/spoty_poczatkowe.py   -> dane_tibia/spoty_poczatkowe.json i ANALIZA_spoty_poczatkowe_1020.md
"""
import json
import math
from collections import defaultdict
from pathlib import Path

KAT = Path(__file__).resolve().parent
SKLEJ = 14
MIASTA = {   # świątynia, promień szukania spotów (pola)
    "Rookgaard": ((32097, 32219, 7), 130),
    "Thais": ((32369, 32241, 7), 130),
    "Carlin": ((32360, 31782, 7), 130),
    "Ab'Dendriel": ((32732, 31634, 7), 130),
    "Kazordoon": ((32649, 31925, 11), 110),
    "Venore": ((32957, 32076, 7), 130),
    "Edron": ((33217, 31814, 8), 130),
    "Darashia": ((33213, 32454, 1), 130),
}
ROOK = lambda x, y: 31890 <= x <= 32170 and 32030 <= y <= 32310   # wyspa Rookgaard (prostokąt przybliżony)
POMIN = {"Rabbit", "Deer", "Chicken", "Sheep", "Black Sheep", "Butterfly", "Flamingo", "Pig", "Parrot", "Squirrel",
         "Cat", "Dog", "Seagull", "Bat"}            # tło bez expa wartego trasy
PRZEDZIALY = (("8-15", 45), ("15-30", 110))          # cios_max najgroźniejszego potwora


def wczytaj():
    potwory = json.loads((KAT / "serwer74" / "potwory_pelne.json").read_text())["potwory"]
    szac = {p["nazwa"].lower(): p.get("atak_max_szac") for p in json.loads((KAT / "potwory.json").read_text())["potwory"]}
    punkty = []
    for p in potwory:
        if p["nazwa"] in POMIN or p.get("exp", 0) <= 0 or p.get("hp", 0) <= 0:
            continue
        if p["exp"] > 600 or p["hp"] > 1300:          # bossy i ciężkie potwory poza zakresem
            continue
        for s in p.get("spawny", []):
            if s.get("respawn_s", 0) > 0 and s.get("ilosc", 0) > 0:
                cios = szac.get(p["nazwa"].lower()) or round(p.get("atak", 0) * 3.5)
                punkty.append({**s, "nazwa": p["nazwa"], "exp": p["exp"], "hp": p["hp"], "atak": cios})
    return punkty


def skupiska(punkty):
    """Sklejanie pojedynczym łączem (union-find) w obrębie piętra."""
    rodzic = list(range(len(punkty)))

    def f(i):
        while rodzic[i] != i:
            rodzic[i] = rodzic[rodzic[i]]
            i = rodzic[i]
        return i
    po_z = defaultdict(list)
    for i, p in enumerate(punkty):
        po_z[p["z"]].append(i)
    for idx in po_z.values():
        idx.sort(key=lambda i: punkty[i]["x"])
        for a_pos, a in enumerate(idx):
            for b in idx[a_pos + 1:]:
                if punkty[b]["x"] - punkty[a]["x"] > SKLEJ:
                    break
                if abs(punkty[b]["y"] - punkty[a]["y"]) <= SKLEJ:
                    rodzic[f(a)] = f(b)
    grupy = defaultdict(list)
    for i in range(len(punkty)):
        grupy[f(i)].append(punkty[i])
    return list(grupy.values())


def opis(grupa):
    potw = defaultdict(int)
    sufit = 0.0
    exp_suma = hp_suma = 0
    for p in grupa:
        potw[p["nazwa"]] += p["ilosc"]
        sufit += p["ilosc"] * p["exp"] * 3600 / p["respawn_s"]
        exp_suma += p["ilosc"] * p["exp"]
        hp_suma += p["ilosc"] * p["hp"]
    n = sum(potw.values())
    xs = [p["x"] for p in grupa]
    ys = [p["y"] for p in grupa]
    return {
        "srodek": {"x": round(sum(p["x"] * p["ilosc"] for p in grupa) / n), "y": round(sum(p["y"] * p["ilosc"] for p in grupa) / n),
                   "z": grupa[0]["z"]},
        "obszar": {"x1": min(xs), "y1": min(ys), "x2": max(xs), "y2": max(ys)},
        "potwory": dict(sorted(potw.items(), key=lambda kv: -kv[1])),
        "potworow": n,
        "sufit_exp_h": round(sufit),
        "exp_na_hp": round(exp_suma / hp_suma, 2),
        "cios_max": max(p["atak"] for p in grupa),
        "najgrozniejszy": max(grupa, key=lambda p: p["atak"])["nazwa"],
    }


def przedzial(s, rook):
    if rook:
        return "rook"
    for nazwa, prog in PRZEDZIALY:
        if s["cios_max"] <= prog:
            return nazwa
    return None


def main():
    spoty = [opis(g) for g in skupiska(wczytaj())]
    wynik = {"meta": __doc__.strip().splitlines()[0] + " sufit_exp_h = górna granica z respawnu, nie pomiar.", "miasta": {}}
    for miasto, ((tx, ty, tz), promien) in MIASTA.items():
        lista = []
        for s in spoty:
            x, y = s["srodek"]["x"], s["srodek"]["y"]
            rook = ROOK(x, y)
            if (miasto == "Rookgaard") != rook:
                continue
            odl = math.hypot(x - tx, y - ty)
            if odl > promien or s["potworow"] < 4:
                continue
            p = przedzial(s, rook)
            if p is None:
                continue
            lista.append({**s, "przedzial": p, "odl_od_swiatyni": round(odl)})
        lista.sort(key=lambda s: -s["sufit_exp_h"])
        wynik["miasta"][miasto] = {"swiatynia": {"x": tx, "y": ty, "z": tz}, "spoty": lista}
    (KAT / "spoty_poczatkowe.json").write_text(json.dumps(wynik, ensure_ascii=False, indent=1) + "\n")
    return wynik


if __name__ == "__main__":
    w = main()
    for miasto, d in w["miasta"].items():
        print(f"== {miasto}: {len(d['spoty'])} spotów")
        for prz in ("rook", "8-15", "15-30"):
            top = [s for s in d["spoty"] if s["przedzial"] == prz][:6]
            for s in top:
                c = s["srodek"]
                mix = ", ".join(f"{k} {v}" for k, v in list(s["potwory"].items())[:4])
                print(f"  [{prz:5}] sufit {s['sufit_exp_h']:6} exp/h  {s['potworow']:3} potw.  exp/hp {s['exp_na_hp']:.2f}  "
                      f"cios {s['cios_max']:3}  ({c['x']},{c['y']},{c['z']}) {s['odl_od_swiatyni']:3} pól  {mix}")
