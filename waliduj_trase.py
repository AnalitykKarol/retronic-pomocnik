#!/usr/bin/env python3
"""Sprawdza trasę względem mapy (map74.otmm): czy między kolejnymi punktami jest droga (A*),
czy punkty nie leżą na ścianach i czy nie ma skoków > 12 pól.

  python3 -I waliduj_trase.py <nazwa> [--skok 12]
  python3 -I waliduj_trase.py --miejsca troll      # trasy/miejsca_troll.json: mapa spotu (patrol:troll), patrz waliduj_miejsca
Kod wyjścia: 0 = brak błędów, 1 = są odcinki bez drogi / punkty w ścianie.
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import trasa_io  # noqa: E402

SKOK_MAX = 12


def waliduj(punkty, m, skok_max=SKOK_MAX):
    """Zwraca listę (poziom, indeks, tekst); poziom: 'BLAD' albo 'OSTRZEZENIE'."""
    wynik = []
    for i, p in enumerate(punkty):
        pr = m.przechodnie(*p)
        if pr is False:
            wynik.append(("BLAD", i, f"punkt {p} leży na ścianie/wodzie"))
        elif pr is None:
            wynik.append(("OSTRZEZENIE", i, f"punkt {p} na polu niewidzianym na mapie"))
    for i, (a, b) in enumerate(zip(punkty, punkty[1:])):
        j = i + 1
        d = max(abs(a[0] - b[0]), abs(a[1] - b[1]))
        if a[2] != b[2]:
            if d > 2:
                wynik.append(("OSTRZEZENIE", j, f"zmiana piętra {a[2]}->{b[2]} z odległością {d} pól "
                                                 f"({a} -> {b}): teleport/zgubiony punkt?"))
            continue
        if d > skok_max:
            wynik.append(("OSTRZEZENIE", j, f"skok {d} pól między {a} a {b} (> {skok_max})"))
        if a == b:
            continue
        # schody=True: trasa może prowadzić przez pola schodów/dziur
        droga = m.droga(a, b, dlugosc=0, schody=True)
        if droga is None:
            if m.droga(a, b, dlugosc=0, schody=True, nieznane=True) is not None:
                wynik.append(("OSTRZEZENIE", j, f"droga {a} -> {b} tylko przez pola niewidziane na mapie"))
            else:
                wynik.append(("BLAD", j, f"BRAK DROGI {a} -> {b} (odcinek {i}->{j}, {d} pól)"))
    return wynik


def waliduj_miejsca(d, m):
    """Plik miejsc patrolu (trasy/miejsca_*.json): miejsca nie w ścianie, schody/łączniki zgodne z mapą,
    wszystkie miejsca osiągalne ze startu po grafie ("graf": odl, komp). Zwraca listę (poziom, id, tekst)."""
    w = []
    mi = d.get("miejsca", [])
    for x in mi:
        p = (x["x"], x["y"], x["z"])
        pr = m.przechodnie(*p)
        if pr is False:
            w.append(("BLAD", x["id"], f"miejsce {x.get('nazwa')} {p} leży na ścianie/wodzie"))
        elif pr is None:
            w.append(("OSTRZEZENIE", x["id"], f"miejsce {x.get('nazwa')} {p} na polu niewidzianym na mapie"))
    ids = {x["id"] for x in mi}
    for x in mi:
        if not x.get("sasiedzi"):
            w.append(("BLAD", x["id"], f"miejsce {x.get('nazwa')} bez sąsiadów w grafie (nieosiągalne)"))
        for n in x.get("sasiedzi", []):
            if n["id"] not in ids:
                w.append(("BLAD", x["id"], f"sąsiad {n['id']} nie istnieje"))
    sid = {p["id"] for p in d.get("przejscia", [])}
    for p in d.get("przejscia", []):
        x, y, z = p["pole"]
        if not m.flagi(x, y, z) & 2:
            w.append(("OSTRZEZENIE", p["id"], f"pole schodów {p['pole']} bez flagi 2 na mapie"))
        for k in ("wejscie_gora", "wyjscie_dol", "wejscie_dol", "wyjscie_gora"):
            if m.przechodnie(*p[k]) is False:
                w.append(("BLAD", p["id"], f"{k} {p[k]} leży na ścianie"))
    for l in d.get("laczniki", []):
        for k in ("od", "do"):
            if k in l and m.przechodnie(*l[k]) is False:
                w.append(("BLAD", l.get("id"), f"łącznik {l.get('id')}: {k} {l[k]} na ścianie"))
        sid.add(l.get("id"))
    for x in mi:
        for n in x.get("sasiedzi", []):
            for przez in n.get("przez", []):
                if przez not in sid:
                    w.append(("BLAD", x["id"], f"droga przez nieznane przejście {przez}"))
    # osiągalność po grafie ze startu: pierwszy sąsiad każdego miejsca, BFS po "sasiedzi"
    if mi:
        wid = {mi[0]["id"]}; st = [mi[0]["id"]]; po_id = {x["id"]: x for x in mi}
        while st:
            for n in po_id[st.pop()].get("sasiedzi", []):
                if n["id"] in po_id and n["id"] not in wid:
                    wid.add(n["id"]); st.append(n["id"])
        for x in mi:
            if x["id"] not in wid:
                w.append(("BLAD", x["id"], f"miejsce {x.get('nazwa')} nieosiągalne z miejsca {mi[0].get('nazwa')} po grafie"))
    for e in d.get("znane_bledy_mapy", []):
        w.append(("OSTRZEZENIE", "-", f"znany błąd mapy: {e}" if isinstance(e, str) else f"znany błąd mapy: {json.dumps(e, ensure_ascii=False)}"))
    return w


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("nazwa", nargs="?")
    p.add_argument("--skok", type=int, default=SKOK_MAX)
    p.add_argument("--miejsca", help="NAZWA z trasy/miejsca_NAZWA.json zamiast trasy")
    a = p.parse_args(argv)
    import mapa
    if a.miejsca:
        m = mapa.mapa()
        if m is None:
            sys.exit("Brak pliku mapy (map74.otmm).")
        d = json.loads((Path(__file__).resolve().parent / "trasy" / f"miejsca_{a.miejsca}.json").read_text())
        wynik = waliduj_miejsca(d, m)
        print(f"miejsca_{a.miejsca}: {len(d.get('miejsca', []))} miejsc, {len(d.get('przejscia', []))} schodów, "
              f"{len(d.get('laczniki', []))} łączników")
        for poziom, idx, tekst in wynik:
            print(f"  {poziom:11} {idx}: {tekst}")
        bledy = sum(1 for x in wynik if x[0] == "BLAD")
        print(f"Wynik: {bledy} błędów, {len(wynik) - bledy} ostrzeżeń" if wynik else "Wynik: OK")
        sys.exit(1 if bledy else 0)
    if not a.nazwa:
        p.error("podaj nazwę trasy albo --miejsca NAZWA")
    punkty, _ = trasa_io.wczytaj(a.nazwa)
    m = mapa.mapa()
    if m is None:
        sys.exit("Brak pliku mapy (map74.otmm).")
    wynik = waliduj(punkty, m, a.skok)
    print(f"{a.nazwa}: {trasa_io.podsumowanie(punkty)}")
    for poziom, idx, tekst in wynik:
        print(f"  {poziom:11} #{idx}: {tekst}")
    bledy = sum(1 for w in wynik if w[0] == "BLAD")
    print(f"Wynik: {bledy} błędów, {len(wynik) - bledy} ostrzeżeń" if wynik else "Wynik: trasa OK")
    sys.exit(1 if bledy else 0)


if __name__ == "__main__":
    main()
