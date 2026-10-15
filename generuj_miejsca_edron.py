#!/usr/bin/env python3
"""Buduje trasy/miejsca_edron.json: patrol po spawnach jaskini trolli w Edronie (wszystko na z8, bez przejść pięter).
Ten sam format i planer co generuj_miejsca_troll.py (miejsca z wagą, sasiedzi z drogą A*, graf). Uruchamiane offline.

  python3 -I generuj_miejsca_edron.py [--zapisz] [--spawny SCIEZKA_spawns.xml] [--telemetria plik.jsonl ...] [--logi plik.log ...]

Skąd co:
  - spawny: Tibia 7.4 spawns.xml (środki spawnów z8 w okolicy pętli edron_trolle_petla); spawn dalej niż MAX_OD_PETLI
    od nagranej pętli jest pomijany (pętla Karola tam nie dochodziła, droga nieprzetestowana).
  - punkt miejsca: najbliższe środkowi spawnu pole nagranej pętli (dowód przechodniości, <= PROMIEN_PUNKTU), a gdy
    pętla jest dalej, sam środek spawnu, jeśli mapa go zna jako przechodni.
  - nauczone dziury (trasy/dziury_nauczone.json) są ścianą dla A*, punktów i dróg (w testach RETRONIC_TESTY bot sam
    ich nie wczytuje, więc generator wstrzykuje je do cavebot.wpadniecie).
  - waga: udział zabić w spawnie (telemetria epizod_celu, bez duplikatów między katalogami), gdy zabić jest
    >= MIN_ZABIC; mieszana z liczbą potworów w spawnie (WAGA_DANYCH), żeby trasa pętli nie premiowała tylko
    tego, gdzie bot akurat chodził. Za mało danych: sama liczba potworów w spawnie.
"""
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

os.environ.setdefault("RETRONIC_TESTY", "1")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import cavebot  # noqa: E402
import mapa as _mapa  # noqa: E402
import wpadniecie  # noqa: E402
import generuj_miejsca_troll as gt  # noqa: E402

TRASY = ROOT / "trasy"
WYJSCIE = TRASY / "miejsca_edron.json"
TRASA = "edron_trolle_petla"
Z = 8
OBSZAR = (33040, 31700, 33140, 31800)     # x0, y0, x1, y1: okolica pętli
MAX_OD_PETLI = 6                          # spawn dalej od nagranej pętli (Chebyshev) jest pomijany
PROMIEN_PUNKTU = 4                        # punkt miejsca na pętli, gdy leży tak blisko środka spawnu
PROMIEN_ZABIC = 6                         # zabicie przypisane do najbliższego spawnu w tym promieniu
MIN_ZABIC = 40                            # tyle przypisanych zabić = dość danych do wag
WAGA_DANYCH = 0.5                         # udział zabić w wadze (reszta: liczba potworów w spawnie)
SPAWNY_XML = "/tmp/claude-1000/-home-charlie/a82b116a-5d12-4f24-a10d-d408ab792454/scratchpad/spawny_dl/spawns.xml"
TELEMETRIA = [str(ROOT / "logi" / "telemetria-20261015.jsonl"),
              str(ROOT.parent / "pomocnik-stabilny" / "logi" / "telemetria-20261015.jsonl")]
cheb = gt.cheb


def wczytaj_spawny(plik):
    out = []
    for s in ET.parse(plik).getroot().iter("spawn"):
        x, y, z = int(s.get("centerx")), int(s.get("centery")), int(s.get("centerz"))
        if z == Z and OBSZAR[0] <= x <= OBSZAR[2] and OBSZAR[1] <= y <= OBSZAR[3]:
            ms = {}
            for mo in s:
                ms[mo.get("name").title()] = ms.get(mo.get("name").title(), 0) + 1
            out.append({"x": x, "y": y, "z": z, "potwory": ms, "ile": sum(ms.values())})
    return sorted(out, key=lambda e: (e["y"], e["x"]))


def zabicia(pliki):
    """-> lista (x, y, nazwa) zabić z epizodow celu (bez duplikatow po id, z wielu katalogow)."""
    widziane, out = set(), []
    for p in pliki:
        if not os.path.isfile(p):
            continue
        for l in open(p):
            if '"epizod_celu"' not in l:
                continue
            try:
                d = json.loads(l)
            except ValueError:
                continue
            if d.get("typ") == "epizod_celu" and d.get("wynik") == "zabity" and d.get("pos") and d.get("id") not in widziane:
                widziane.add(d.get("id"))
                out.append((d["pos"][0], d["pos"][1], d.get("n")))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true", help=f"zapisz {WYJSCIE.name} (bez tego tylko raport)")
    ap.add_argument("--spawny", default=SPAWNY_XML)
    ap.add_argument("--telemetria", nargs="*", default=TELEMETRIA)
    a = ap.parse_args(argv)
    cavebot.log = lambda *x: None
    m = _mapa.mapa()
    petla = [tuple(p) for p in json.loads((TRASY / f"{TRASA}.json").read_text())]
    pset = set(petla)
    start = petla[0]
    dz = json.loads((TRASY / "dziury_nauczone.json").read_text())["dziury"]
    dziury = {tuple(d) for d in dz}
    cb = gt.zrob_cb(m, [petla[0], petla[1]])
    cb.przejscia, cb.laczniki = [], []
    w = wpadniecie.Wpadniecie(cb, konf=cavebot, log=lambda t: None)
    w.dziury = set(dziury)
    cb.wpadniecie = w
    cb.miejsca = []
    zle = [p for p in petla if p in dziury]
    if zle:
        print("UWAGA: pętla przechodzi przez dziurę:", zle, file=sys.stderr)

    spawny = wczytaj_spawny(a.spawny)
    zab = zabicia(a.telemetria)
    pominiete, wybrane = [], []
    for sp in spawny:
        c = (sp["x"], sp["y"])
        najb = min(petla, key=lambda p: cheb(c, p))
        od = cheb(c, najb)
        sp["od_petli"] = od
        opis = f"{sp['ile']}x " + ", ".join(f"{k} {v}" for k, v in sorted(sp["potwory"].items()))
        if od > MAX_OD_PETLI:
            pominiete.append((sp, f"{od} pól od nagranej pętli (> {MAX_OD_PETLI}), droga nieprzetestowana"))
            continue
        if od <= PROMIEN_PUNKTU:
            pole, skad = najb, "na pętli"
        elif m.przechodnie(c[0], c[1], Z) is True:
            pole, skad = (c[0], c[1], Z), "środek spawnu (mapa)"
        else:
            pominiete.append((sp, "brak przechodniego pola przy środku"))
            continue
        if pole in dziury:
            pominiete.append((sp, "punkt na nauczonej dziurze"))
            continue
        d = cb.droga(start, pole[:2], dlugosc=0) if pole != start else []
        if d is None:
            pominiete.append((sp, "A* nie widzi drogi z początku pętli"))
            continue
        if any((q[0], q[1], Z) in dziury for q in d):
            pominiete.append((sp, "droga przez nauczoną dziurę"))
            continue
        sp["pole"], sp["skad"], sp["opis"] = pole, skad, opis
        wybrane.append(sp)

    # zabicia -> najbliższy spawn (także pominięty) w promieniu PROMIEN_ZABIC
    for sp in spawny:
        sp["zabicia"] = 0
    przyp = 0
    for x, y, _n in zab:
        k = [s for s in spawny if cheb((s["x"], s["y"]), (x, y)) <= PROMIEN_ZABIC]
        if k:
            min(k, key=lambda s: cheb((s["x"], s["y"]), (x, y)))["zabicia"] += 1
            przyp += 1
    dosc = przyp >= MIN_ZABIC and sum(s["zabicia"] for s in wybrane) > 0
    suma_ile = sum(s["ile"] for s in wybrane)
    suma_zab = sum(s["zabicia"] for s in wybrane)
    # mobow naraz: próbki telemetrii z tych samych plików (Troll z8)
    pliki_tel = [p for p in a.telemetria if os.path.isfile(p)]
    _zab, ob = gt.telemetria(pliki_tel)
    miejsca = []
    for i, sp in enumerate(wybrane, start=1):
        x, y, z = sp["pole"]
        kp = gt.komponent(m, (x, y, z), pset, {}, r=14)
        mob = 0
        for _t, px, py, pz, tr in ob:
            if pz == z:
                mob = max(mob, sum(1 for t in tr if cheb(t, (sp["x"], sp["y"])) <= gt.PROMIEN + 1 and t in kp))
        wl = sp["ile"] / suma_ile
        wz = sp["zabicia"] / suma_zab if suma_zab else 0.0
        waga = round(WAGA_DANYCH * wz + (1 - WAGA_DANYCH) * wl, 3) if dosc else round(wl, 3)
        miejsca.append({"id": i, "nazwa": f"z8_spawn_{sp['x']}_{sp['y']}", "x": x, "y": y, "z": z,
                        "opis": f"spawn {sp['opis']}, środek ({sp['x']},{sp['y']}), punkt: {sp['skad']}",
                        "zabicia": sp["zabicia"], "udzial_zabic": round(wz, 3), "mobow": mob, "zrodlo": "troll",
                        "waga": waga, "gniazdo": mob >= cavebot.PATROL_GNIAZDO_MOBOW})

    plik = {"przejscia": [], "laczniki": [], "miejsca": [dict(mm) for mm in miejsca]}
    graf = gt.buduj_graf(cb, plik)
    plik["graf"] = graf
    cb.patrol_graf = cb._patrol_graf(graf)
    cb.miejsca = [dict(mm, mobow=None) for mm in miejsca]
    brak = []
    for mm in miejsca:
        mm["sasiedzi"] = []
        for nn in miejsca:
            if nn["id"] == mm["id"]:
                continue
            uz = []
            d = cb._patrol_droga((mm["x"], mm["y"], mm["z"]), nn, uz)
            if d is None:
                brak.append((mm["nazwa"], nn["nazwa"]))
                continue
            if any((q[0], q[1], Z) in dziury for q in d):
                brak.append((mm["nazwa"], nn["nazwa"], "dziura"))
            mm["sasiedzi"].append({"id": nn["id"], "droga": len(d), "przez": [u.split(":")[0] for u in uz]})
        d0 = cb._patrol_droga(start, mm, [])
        mm["od_startu"] = len(d0) if d0 is not None else None
        if d0 is None:
            brak.append(("START", mm["nazwa"]))
    for mm in miejsca:
        mm["komp"] = next(n["komp"] for n in graf["wezly"] if n["pole"] == [mm["x"], mm["y"], mm["z"]])
    out = {
        "opis": ("mapa spotu trolli w Edronie (z8) jako graf: miejsca = spawny trolli z Tibia 7.4 spawns.xml leżące przy "
                 "nagranej pętli edron_trolle_petla, waga = mieszanka udziału zabić (telemetria 15.10) i liczby potworów "
                 "w spawnie. Bez przejść pięter. Nauczona dziura (33081,31742,8) jest ścianą dla punktów i dróg. "
                 "Patrz generuj_miejsca_edron.py. Zachowanie wg cavebot.PATROL_*."),
        "trasa": TRASA,
        "promien": gt.PROMIEN,
        "start": list(start),
        "telemetria": [os.path.basename(os.path.dirname(os.path.dirname(p))) + "/" + os.path.basename(p) for p in pliki_tel],
        "zabicia_przypisane": przyp,
        "przejscia": [],
        "laczniki": [],
        "graf": graf,
        "dziury_omijane": [list(d) for d in sorted(dziury)],
        "pominiete_spawny": [{"x": s["x"], "y": s["y"], "ile": s["ile"], "powod": p} for s, p in pominiete],
        "miejsca": miejsca,
    }
    print(f"spawnów w okolicy: {len(spawny)}, wybranych: {len(miejsca)}, zabić przypisanych: {przyp}/{len(zab)}, "
          f"wagi z zabić: {'tak' if dosc else 'nie'}")
    for mm in miejsca:
        print(f"m{mm['id']:<2} {mm['nazwa']:<22} ({mm['x']},{mm['y']},z{mm['z']}) zab {mm['zabicia']:>3} "
              f"udział {mm['udzial_zabic']:.3f} mobów {mm['mobow']} waga {mm['waga']} od startu {mm['od_startu']}")
    for s, p in pominiete:
        print(f"POMINIĘTY ({s['x']},{s['y']}) {s['ile']}x: {p} (zabić w pobliżu: {s['zabicia']})")
    print("bez drogi:", brak or "brak")
    if a.zapisz:
        WYJSCIE.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
        print("zapisano", WYJSCIE)
    return 1 if brak else 0


if __name__ == "__main__":
    sys.exit(main())
