#!/usr/bin/env python3
"""Jednorazowy zasiew trasy/ogien_epizody.json z logów bota (linie "[OGIEN] pola" i "stoję na ogniu") i telemetrii (hp).

Wykrycie pola = pole w linii "pola" albo pole z linii "stoję na ogniu". Epizod = wykrycie po przerwie > 60 s od
poprzedniego wykrycia tego pola. Spadek HP > 3 pp w oknie +-3 s od wykrycia, gdy próbka telemetrii stała na tym polu,
ustawia hp=True (pole nie kwalifikuje się do maski). Ta sama reguła kwalifikacji co w cavebot._ogien_dane_przelicz.
Pola bez żadnej próbki telemetrii na nich (brak dowodu, że nie parzą) dostają n = 2, chyba że --bez-dowodu.
Użycie: python3 narzedzia/zasiej_ogien_epizody.py [--sucho] [--bez-dowodu]  (domyślnie scala z istniejącym plikiem; wynik atomowo)."""
import bisect
from collections import Counter
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

KAT = Path(__file__).resolve().parent.parent
PLIK = KAT / "trasy" / "ogien_epizody.json"
PRZERWA_S, SPADEK_PP, OKNO_S, MIN_N, MIN_GODZ = 60.0, 3.0, 3.0, 3, 2

RE_CZAS = re.compile(r"^(\d\d):(\d\d):(\d\d) (.*)$")
RE_POLA = re.compile(r"\[OGIEN\] pola: (.*) \(piętro (\d+), \d+\)")
RE_POLE = re.compile(r"\((\d+),(\d+)\)")
RE_STOJE = re.compile(r"\[OGIEN\] stoję na ogniu \((\d+),(\d+)\)")


def data_pliku(nazwa):
    m = re.match(r"mozg-(\d{4})(\d\d)(\d\d)-\d{4}\.log$", nazwa)
    if m:
        return datetime(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r"mozg-stdout-(\d\d)(\d\d)-\d{4}\.log$", nazwa)
    if m:
        return datetime(2026, int(m[1]), int(m[2]))
    return None


def wykrycia():
    """Zwraca posortowaną listę (epoch, (x,y,z), czy_stoimy)."""
    wynik, widziane = [], set()
    z_ost = None
    for f in sorted((KAT / "logi").glob("mozg-*.log")):
        d0 = data_pliku(f.name)
        if d0 is None:
            continue
        dzien, poprz = d0, -1
        for l in f.read_text(errors="replace").splitlines():
            m = RE_CZAS.match(l)
            if not m:
                continue
            sek = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
            if sek < poprz:
                dzien = datetime.fromtimestamp(dzien.timestamp() + 86400)
            poprz = sek
            t = dzien.replace(hour=int(m[1]), minute=int(m[2]), second=int(m[3])).timestamp()
            tresc = m[4]
            mp = RE_POLA.search(tresc)
            if mp:
                z_ost = int(mp[2])
                for x, y in RE_POLE.findall(mp[1]):
                    k = (round(t), int(x), int(y), z_ost, False)
                    if k not in widziane:
                        widziane.add(k); wynik.append((t, (int(x), int(y), z_ost), False))
                continue
            ms = RE_STOJE.search(tresc)
            if ms and z_ost is not None:
                k = (round(t), int(ms[1]), int(ms[2]), z_ost, True)
                if k not in widziane:
                    widziane.add(k); wynik.append((t, (int(ms[1]), int(ms[2]), z_ost), True))
    return sorted(wynik)


def telemetria():
    t_, dane = [], []
    for f in sorted((KAT / "logi").glob("telemetria-*.jsonl")):
        for l in f.open(errors="replace"):
            if '"probka"' not in l:
                continue
            try:
                d = json.loads(l)
            except ValueError:
                continue
            if d.get("typ") == "probka" and d.get("poz") and d.get("hp") is not None:
                t_.append(d["t"]); dane.append((tuple(d["poz"]), float(d["hp"])))
    idx = sorted(range(len(t_)), key=t_.__getitem__)
    return [t_[i] for i in idx], [dane[i] for i in idx]


def spadek_na_polu(tt, dd, t, p):
    """Czy w oknie +-OKNO_S wokół t próbki stojące na polu p pokazują spadek HP > SPADEK_PP (od wcześniejszego do późniejszego)."""
    i0, i1 = bisect.bisect_left(tt, t - OKNO_S), bisect.bisect_right(tt, t + OKNO_S)
    maks = None
    for poz, hp in dd[i0:i1]:
        if tuple(poz) != p:
            continue
        maks = hp if maks is None else max(maks, hp)
        if maks - hp > SPADEK_PP:
            return True
    return False


def main():
    sucho = "--sucho" in sys.argv
    z_dowodem_tylko = "--bez-dowodu" not in sys.argv
    det = wykrycia()
    tt, dd = telemetria()
    stalismy = Counter(tuple(poz) for poz, _ in dd)       # próbki telemetrii na danym polu (dowód, że postać tam stała)
    pola = {}
    ost = {}
    for t, p, _ in det:
        k = f"{p[0]},{p[1]},{p[2]}"
        e = pola.setdefault(k, {"n": 0, "godz": [], "hp": False, "ost": 0.0})
        if t - ost.get(k, float("-inf")) > PRZERWA_S:
            e["n"] += 1
            h = time.localtime(t).tm_hour
            if h not in e["godz"]:
                e["godz"] = sorted(e["godz"] + [h])
        ost[k] = t
        e["ost"] = max(e["ost"], t)
        if not e["hp"] and spadek_na_polu(tt, dd, t, p):
            e["hp"] = True
    if z_dowodem_tylko:       # pole, na którym postać nigdy nie stała (brak próbki hp): bez dowodu "nie parzy", n ograniczone do MIN_N-1
        for k, e in pola.items():
            if stalismy[tuple(int(v) for v in k.split(","))] == 0 and e["n"] >= MIN_N:
                e["n"] = MIN_N - 1
    maska = sorted(k for k, e in pola.items() if e["n"] >= MIN_N and len(e["godz"]) >= MIN_GODZ and not e["hp"])
    print(f"wykryć: {len(det)}, pól: {len(pola)}, z hp: {sum(e['hp'] for e in pola.values())}, do maski danych: {len(maska)}")
    for k in maska:
        print("  ", k, pola[k]["n"], pola[k]["godz"])
    if sucho:
        return
    try:
        stare = json.loads(PLIK.read_text()).get("pola", {})
    except (FileNotFoundError, ValueError):
        stare = {}
    for k, e in stare.items():          # scalenie: zostaje większe n, suma godzin, hp jeśli którekolwiek
        if k in pola:
            n = pola[k]
            n["n"] = max(n["n"], e.get("n", 0)); n["godz"] = sorted(set(n["godz"]) | set(e.get("godz", [])))
            n["hp"] = n["hp"] or bool(e.get("hp")); n["ost"] = max(n["ost"], e.get("ost", 0.0))
        else:
            pola[k] = e
    tmp = PLIK.with_suffix(".tmp")
    tmp.write_text(json.dumps({"opis": "epizody wykryc ognia na polach (n po przerwie > 60 s, godziny doby, hp = spadek HP na polu); zasiew z logow",
                               "pola": {k: pola[k] for k in sorted(pola)}}, indent=0))
    tmp.replace(PLIK)
    print("zapisano", PLIK)


if __name__ == "__main__":
    main()
