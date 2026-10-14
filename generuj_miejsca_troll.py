#!/usr/bin/env python3
"""Buduje trasy/miejsca_troll.json: jedna wielka mapa spotu trolli (z8+z9) z kilkoma miejscami zainteresowania
(tam, gdzie faktycznie stoją trolle), przejściami pięter i ręcznymi łącznikami. Uruchamiane offline.

  python3 -I generuj_miejsca_troll.py [--zapisz] [--telemetria logi/telemetria-20261012.jsonl ...]

Skąd co:
  - przejścia pięter: z nagranych tras (troll_pelny, troll_nowa_czesc, troll_cave): każda zmiana piętra między
    kolejnymi punktami; pole schodów T (z flagą 2 na górnym piętrze) wyznacza pietra.kandydaci (ta sama logika,
    której używa bot). Wejście w dół = pole obok T na górnym piętrze (nagrane `a`), lądowanie = (T.x, T.y, z+1);
    wejście w górę = pole (T.x, T.y, z+1), lądowanie = (T.x, T.y+1, z). Każde przejście jest dwukierunkowe.
  - łączniki: odcinki nagranych tras, na których mapa (A*) nie widzi drogi, mimo że oba końce są przechodnie
    (punkty nagrane przez Karola są dowodem przejścia): zapisane jako jawne kroki, planowanie nie zależy od błędu mapy.
  - miejsca: ręcznie wybrane punkty na polach nagranych tras (pewnie przechodnie); statystyki (zabicia, najwięcej
    trolli naraz) z telemetrii: epizod_celu (Troll, zabity) + próbki (pozycja gracza + dx, dy stworów).
"""
import argparse
import bisect
import json
import os
import sys
import types
from pathlib import Path

os.environ.setdefault("RETRONIC_TESTY", "1")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import cavebot  # noqa: E402
import bot  # noqa: E402
import mapa as _mapa  # noqa: E402
import pietra  # noqa: E402

TRASY = ROOT / "trasy"
WYJSCIE = TRASY / "miejsca_troll.json"
TRASY_ZRODLO = ("troll_pelny", "troll_nowa_czesc", "troll_cave")
PROMIEN = 4          # kill/mob przypisany do miejsca w tym promieniu (Chebyshev)
START = (32493, 32260, 8)   # start bota (uruchom_trolle.sh)

# (nazwa, x, y, z, opis); pola leżą na nagranych trasach albo na polach znanych (znane_pola.json)
# 14.10: miejsca = spawny z Tibia74-spawns.xml (środek spawnu, radius 1), waga = liczba potworów w spawnie / suma
# 14.10: z9_spawn_32485_32274 (1 troll) usunięty: niecka za dziurą (32483,32285), bot nie umiał wyjść
SPAWNY = [
    ("z8_spawn_32478_32290", 32478, 32290, 8, 2, "spawn 2x troll, główna sala z8"),
    ("z8_spawn_32491_32294", 32491, 32294, 8, 2, "spawn 2x troll, wschodni kraniec sali z8"),
    ("z8_spawn_32500_32270", 32500, 32270, 8, 2, "spawn 2x troll, korytarz przy schodach (32498,32270)"),
    ("z8_spawn_32507_32268", 32507, 32268, 8, 2, "spawn 2x troll, pokój za drzwiami (32505,32270)"),
    ("z9_spawn_32471_32270", 32471, 32270, 9, 4, "spawn 4x troll, gniazdo pod schodami (32476,32272)"),
    ("z9_spawn_32503_32284", 32503, 32284, 9, 4, "spawn 4x troll, nowa część z9"),
    ("z9_spawn_32508_32278", 32508, 32278, 9, 2, "spawn 2x orc"),
    ("z9_spawn_32488_32299", 32488, 32299, 9, 3, "spawn 3x troll, komora z9 południe"),
]
MIEJSCA = [(n, x, y, z, o) for n, x, y, z, _, o in SPAWNY]
_SUMA = sum(k for *_, k, _o in SPAWNY)
WAGA_RECZNA = {n: round(k / _SUMA, 3) for n, _x, _y, _z, k, _o in SPAWNY}


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def wczytaj_trasy():
    return {n: [tuple(p) for p in json.loads((TRASY / f"{n}.json").read_text())] for n in TRASY_ZRODLO}


def pole_ok(m, x, y, z, pts, znane):
    """Pole, po którym da się chodzić: widziane i nie ściana na mapie (albo punkt nagranej trasy / znane pole),
    bez flagi 2 (schody/dziura)."""
    f = m.flagi(x, y, z)
    if f & 2:
        return False
    if (x, y, z) in pts:
        return True
    return bool(f & 1 or (x * (1 << 17) + y) in znane.get(z, ())) and not f & 4


def komponent(m, start, pts, znane, r=24):
    """Zbiór pól (x,y) piętra start[2] połączonych ze start (8 kierunków, bez ścinania rogów), w kwadracie +-r."""
    z = start[2]
    wid = {(start[0], start[1])}
    st = [(start[0], start[1])]
    while st:
        a, b = st.pop()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (a + dx, b + dy)
                if (dx or dy) and n not in wid and abs(n[0] - start[0]) <= r and abs(n[1] - start[1]) <= r \
                        and pole_ok(m, n[0], n[1], z, pts, znane):
                    if dx and dy and not (pole_ok(m, a + dx, b, z, pts, znane) and pole_ok(m, a, b + dy, z, pts, znane)):
                        continue
                    wid.add(n)
                    st.append(n)
    return wid


def przejscia_z_tras(m, trasy, pts=frozenset(), znane=None):
    """-> lista przejść. Dedup po (x, y, piętro górne) pola schodów T."""
    znane = znane or {}
    wyn = {}
    for nazwa, t in trasy.items():
        for i in range(len(t) - 1):
            a, b = t[i], t[i + 1]
            if a[2] == b[2]:
                continue
            k = pietra.kandydaci(m, a, b)
            if not k or not k[0]["pewne"]:
                print(f"UWAGA: {nazwa} #{i}: brak pewnego pola schodów dla {a} -> {b}", file=sys.stderr)
                continue
            T = k[0]["pole"]
            z_g = min(a[2], b[2])
            klucz = (T[0], T[1], z_g)
            e = wyn.setdefault(klucz, {"T": (T[0], T[1]), "z_gora": z_g, "z_dol": z_g + 1,
                                       "zrodla": [], "a_gora": None})
            e["zrodla"].append(f"{nazwa}#{i}")
            if b[2] > a[2]:                               # nagrane zejście: a = pole na górnym piętrze przed T
                if cheb(a, T) == 1 and (a[0] == T[0] or a[1] == T[1]):
                    e["a_gora"] = a
            else:                                         # nagrane wejście w górę: a = pole na dolnym piętrze przy R
                if cheb(a, T) <= 1 and (a[0], a[1]) != (T[0], T[1]):
                    e["a_dol"] = a
    wyn_l = []
    for (x, y, z_g), e in sorted(wyn.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        T = e["T"]
        a = e["a_gora"] or (T[0], T[1] + 1, z_g)
        # wejście w górę: pole OBOK R (samo R jest w zakazie A* bota, bo to pole zmiany piętra); pietra.py sam dojdzie na R
        ad = e.get("a_dol")
        if ad is None:
            nb = [(T[0] + dx, T[1] + dy, z_g + 1) for dx, dy in
                  ((0, 1), (1, 0), (-1, 0), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1))]
            nb = [q for q in nb if pole_ok(m, q[0], q[1], q[2], pts, znane)]
            nb.sort(key=lambda q: (q not in pts,))
            ad = nb[0] if nb else (T[0], T[1], z_g + 1)
        wyn_l.append({
            "id": f"schody_{T[0]}_{T[1]}",
            "pole": [T[0], T[1], z_g],
            "wejscie_gora": list(a),
            "wyjscie_dol": [T[0], T[1], z_g + 1],
            "wejscie_dol": list(ad),
            "wyjscie_gora": [T[0], T[1] + 1, z_g],
            "zrodla": e["zrodla"],
        })
    return wyn_l


def laczniki_z_tras(m, trasy, znane):
    """Kolejne punkty na tym samym piętrze, między którymi A* (z schodami) nie widzi drogi, choć oba są przechodnie."""
    K = 1 << 17
    wyn, widziane = [], set()
    for nazwa, t in trasy.items():
        for i in range(len(t) - 1):
            a, b = t[i], t[i + 1]
            if a[2] != b[2] or a == b or (a, b) in widziane:
                continue
            if m.przechodnie(*a) is not True or m.przechodnie(*b) is not True:
                continue                                  # punkt na polu "ściany" (przedmiot): nie łącznik, błąd mapy
            kz = znane.get(a[2])
            if m.droga(a, b, [], 0, True, limit=20000, schody=True, znane=kz) is not None:
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            if dx and dy and abs(dx) != abs(dy):
                print(f"UWAGA: {nazwa} #{i}: {a} -> {b} nie na jednej linii, łącznik wymaga ręcznych kroków",
                      file=sys.stderr)
                continue
            n = max(abs(dx), abs(dy))
            kroki = [[a[0] + round(dx * j / n), a[1] + round(dy * j / n), a[2]] for j in range(1, n + 1)]
            widziane.add((a, b))
            sciana = [k[:2] for k in kroki if (m.flagi(k[0], k[1], k[2]) & 4)]
            wyn.append({"id": f"lacznik_{a[0]}_{a[1]}_{b[0]}_{b[1]}", "typ": "reczne", "dwa_kierunki": True,
                        "od": list(a), "do": list(b), "kroki": kroki, "zrodlo": f"{nazwa}#{i}->#{i + 1}",
                        "pola_oznaczone_jako_sciana": sciana,
                        "uwaga": "mapa: A* nie widzi drogi; punkty nagrane przez Karola przechodzą linią prostą"})
    return wyn


def telemetria(pliki):
    """-> (zabicia [(x,y,z)], obecnosc [(czas, x, y, z, [(x,y)... trolle])])."""
    pr, ep = [], []
    for plik in pliki:
        for l in open(plik):
            if '"probka"' not in l and '"epizod_celu"' not in l:
                continue
            try:
                d = json.loads(l)
            except ValueError:
                continue
            if d["typ"] == "probka":
                pr.append(d)
            elif d["typ"] == "epizod_celu" and d.get("n") == "Troll" and d.get("wynik") == "zabity":
                ep.append(d)
    pr.sort(key=lambda d: d["t"])
    ts = [d["t"] for d in pr]
    zab = []
    for e in ep:
        i = bisect.bisect(ts, e["t"]) - 1
        if i >= 0 and e["t"] - ts[i] < 10 and pr[i]["poz"][2] in (8, 9) and e.get("pos"):
            zab.append((e["pos"][0], e["pos"][1], pr[i]["poz"][2]))
    ob = []
    for d in pr:
        x, y, z = d["poz"]
        if z not in (8, 9):
            continue
        tr = [(x + s["dx"], y + s["dy"]) for s in d.get("stwory", []) if s.get("n") == "Troll" and not s.get("gracz")]
        if tr:
            ob.append((d["t"], x, y, z, tr))
    return zab, ob


class Swiat:
    def __init__(s, poz):
        s.t = 0.0
        s.poz = list(poz)

    def zegar(s):
        return s.t

    def zapytaj(s, z):
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 95, "max_mana": 95}}
        return {"stwory": []}


class P:
    nazwa = "Ja"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        return tuple(p.s.poz)


def zrob_cb(m, punkty):
    s = Swiat(START)
    cb = cavebot.Cavebot(P(s), punkty, zapytaj=s.zapytaj, atak=lambda a, b: None, alarm=lambda w: None,
                         spij=lambda d: None, zegar=s.zegar, loot=types.SimpleNamespace(zbierz=lambda z, g: "ok"),
                         mapa=m, czas_s=10 ** 7)
    return cb


def buduj_graf(cb, plik):
    """Węzły = końce przejść/łączników + miejsca; komp = spójna składowa po A* (cb.droga: to samo, co w grze);
    odl = długość A* dla każdej pary węzłów w jednej składowej (ta sama kolejność co w czasie gry)."""
    wezly = []

    def dodaj(p):
        p = tuple(p)
        if p not in wezly:
            wezly.append(p)
    for e in cb.przejscia + cb.laczniki:
        dodaj(e["wej"])
        dodaj(e["wyj"])
    for mm in plik["miejsca"]:
        dodaj((mm["x"], mm["y"], mm["z"]))
    rodzic = list(range(len(wezly)))

    def szukaj(i):
        while rodzic[i] != i:
            rodzic[i] = rodzic[rodzic[i]]
            i = rodzic[i]
        return i
    odl = []
    for i, a in enumerate(wezly):
        for j in range(i + 1, len(wezly)):
            b = wezly[j]
            if a[2] != b[2]:
                continue
            if a[:2] == b[:2]:
                d = []
            else:
                d = cb.droga(a, b[:2], dlugosc=0)
            if d is not None:
                odl.append([i, j, len(d)])
                rodzic[szukaj(j)] = szukaj(i)
    korzen = {}
    out = []
    for i, w in enumerate(wezly):
        out.append({"pole": list(w), "komp": korzen.setdefault(szukaj(i), len(korzen) + 1)})
    return {"opis": "wezly = konce przejsc/laczników i miejsca; komp = skladowa spojnosci (A* bota na mapie); "
                    "odl = [i, j, dlugosc A*] dla par w jednej skladowej (liczone offline, patrz buduj_graf)",
            "wezly": out, "odl": odl}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true", help=f"zapisz {WYJSCIE.name} (bez tego tylko raport)")
    ap.add_argument("--telemetria", nargs="*", default=[str(ROOT / "logi" / "telemetria-20261012.jsonl")])
    a = ap.parse_args(argv)
    cavebot.log = lambda *x: None
    m = _mapa.mapa()
    trasy = wczytaj_trasy()
    znane = {}
    for x, y, z in json.loads((ROOT / "znane_pola.json").read_text()):
        znane.setdefault(z, set()).add(x * (1 << 17) + y)

    pts = {p for t in trasy.values() for p in t}
    przej = przejscia_z_tras(m, trasy, pts, znane)
    lacz = laczniki_z_tras(m, trasy, znane)
    zab, ob = telemetria(a.telemetria)
    print(f"przejść pięter: {len(przej)}, łączników: {len(lacz)}, zabić trolli (z8/z9): {len(zab)}, próbek z trollami: {len(ob)}")

    def szczyt(pole, z):
        """Najwięcej trolli naraz w promieniu PROMIEN+1 od pola, liczone tylko w jego spójnym obszarze (trolle
        widziane przez ścianę z innego pomieszczenia nie liczą się)."""
        kp = komponent(m, (pole[0], pole[1], z), pts, znane)
        n = 0
        for _, x, y, zz, tr in ob:
            if zz != z:
                continue
            k = sum(1 for tx, ty in tr if cheb((tx, ty), pole) <= PROMIEN + 1 and (tx, ty) in kp)
            n = max(n, k)
        return n

    for e in przej:
        e["mobow_przy_ladowaniu"] = szczyt(e["wyjscie_dol"][:2], e["wyjscie_dol"][2])
        e["gniazdo"] = e["mobow_przy_ladowaniu"] >= cavebot.PATROL_GNIAZDO_MOBOW

    # zabicia przypisane do najbliższego miejsca w promieniu PROMIEN
    miejsca = []
    for i, (nazwa, x, y, z, opis) in enumerate(MIEJSCA, start=1):
        if m.przechodnie(x, y, z) is not True:
            print(f"UWAGA: miejsce {nazwa} ({x},{y},{z}) nie jest przechodnie na mapie", file=sys.stderr)
        miejsca.append({"id": i, "nazwa": nazwa, "x": x, "y": y, "z": z, "opis": opis, "zabicia": 0})
    przypisane = 0
    for zx, zy, zz in zab:
        k = [mm for mm in miejsca if mm["z"] == zz and cheb((mm["x"], mm["y"]), (zx, zy)) <= PROMIEN]
        if k:
            min(k, key=lambda mm: cheb((mm["x"], mm["y"]), (zx, zy)))["zabicia"] += 1
            przypisane += 1
    for mm in miejsca:
        mm["udzial_zabic"] = round(mm["zabicia"] / przypisane, 3) if przypisane else 0.0
        mm["mobow"] = szczyt((mm["x"], mm["y"]), mm["z"])
        mm["zrodlo"] = "troll"
        if mm["nazwa"] in WAGA_RECZNA:
            mm["waga"] = WAGA_RECZNA[mm["nazwa"]]
        mm["gniazdo"] = mm["mobow"] >= cavebot.PATROL_GNIAZDO_MOBOW

    # graf: droga między wszystkimi parami miejsc planerem bota (A* + przejścia + łączniki)
    plik = {"przejscia": przej, "laczniki": lacz,
            "miejsca": [{k: v for k, v in mm.items()} for mm in miejsca]}
    cb = zrob_cb(m, [(32493, 32260, 8), (32492, 32260, 8)])
    cb.przejscia, cb.laczniki = cb._patrol_przejscia(plik)
    graf = buduj_graf(cb, plik)
    plik["graf"] = graf
    cb.patrol_graf = cb._patrol_graf(graf)
    cb.miejsca = []
    for mm in miejsca:
        mm2 = dict(mm)
        mm2["mobow"] = None
        cb.miejsca.append(mm2)
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
            mm["sasiedzi"].append({"id": nn["id"], "droga": len(d), "przez": [u.split(":")[0] for u in uz]})
        d0 = cb._patrol_droga(START, mm, [])
        mm["od_startu"] = len(d0) if d0 is not None else None
        if d0 is None:
            brak.append(("START", mm["nazwa"]))
    print("bez drogi:", brak or "brak")
    for mm in miejsca:
        mm["komp"] = next(n["komp"] for n in graf["wezly"] if n["pole"] == [mm["x"], mm["y"], mm["z"]])
    out = {
        "opis": ("mapa spotu trolli (z8+z9) jako graf: miejsca = gdzie stoją trolle (zabicia i próbki z "
                 "telemetria-20261012), przejscia = schody/dziury z nagranych tras (dwukierunkowe), laczniki = jawne "
                 "kroki tam, gdzie mapa (A*) nie widzi drogi, a nagranie ją przeszło. Patrz generuj_miejsca_troll.py. "
                 "mobow = najwięcej trolli naraz w pobliżu (>= PATROL_GNIAZDO_MOBOW: gniazdo, wymaga HP/many). "
                 "waga (opcjonalne) zastępuje udział zabić; zachowanie wg cavebot.PATROL_*"),
        "trasa": "troll_cave",
        "promien": PROMIEN,
        "start": list(START),
        "telemetria": [os.path.basename(p) for p in a.telemetria],
        "zabicia_przypisane": przypisane,
        "przejscia": przej,
        "laczniki": lacz,
        "graf": graf,
        "znane_bledy_mapy": [
            {"pole": [32473, 32273, 9], "opis": "flaga 5 mimo koloru podłogi; stoją tu trasy troll_cave/troll_do_miasta/"
                                                "troll_pelny (32474,32273,9); A* omija, nieszkodliwe (gniazdo)"},
        ],
        "miejsca": miejsca,
    }
    txt = json.dumps(out, ensure_ascii=False, indent=1)
    for mm in miejsca:
        print(f"m{mm['id']:<2} {mm['nazwa']:<20} ({mm['x']},{mm['y']},z{mm['z']}) zab {mm['zabicia']:>3} "
              f"udział {mm['udzial_zabic']:.3f} mobów {mm['mobow']} od startu {mm['od_startu']}"
              + (f" waga {mm['waga']}" if "waga" in mm else ""))
    for e in przej:
        print(f"  {e['id']}: wejście {e['wejscie_gora']} -> {e['wyjscie_dol']}, w górę -> {e['wyjscie_gora']}; "
              f"mobów {e['mobow_przy_ladowaniu']}{' GNIAZDO' if e['gniazdo'] else ''}; {e['zrodla']}")
    for e in lacz:
        print(f"  {e['id']}: {e['od']} -> {e['do']} ({e['zrodlo']}), pola-ściany: {e['pola_oznaczone_jako_sciana']}")
    if a.zapisz:
        WYJSCIE.write_text(txt + "\n")
        print("zapisano", WYJSCIE)
    return 1 if brak else 0


if __name__ == "__main__":
    sys.exit(main())
