#!/usr/bin/env python3
"""Rodziny spotów (26.10): trasy POWROTU do depo z nowych pięter z10 Edronu (generuj_rodziny_pietra.py): trolle_edron_z10w oraz trzy kieszenie goblinów.

  python3 -I generuj_powroty_rodziny.py [--zapisz]        bez --zapisz tylko liczy i drukuje podsumowanie

Schemat jak generuj_powroty_edron_z9.py: dojście schodzi na z10 DZIURĄ z z9 (kolor 210 + flaga 2 nad polem 210 bez flagi, ten sam wzorzec co dziury
z8 -> z9 Edronu przebyte na żywo 21.10), więc powrót = LINA na polu lądowania na z10 (pole liny = (x, y, z10), stoimy obok, lądowanie (x, y+1, z9)).
Wpis dla wyprawa.PLANY_PK (`wyjscie`): (pole liny z10, lądowanie z9, plik trasy dalej, (stanie obok,)). Plik trasy dalej `<plik>_do_depo` składa się z:
  1. marszu po z9 od lądowania do pola stania obok liny z9 -> z8 (z9w: (33119,31739); goblinów: (33092,31836)), omijającego ogień z buforem 1,
  2. przejścia liną z9 -> z8: [stanie z9, lądowanie z8] (te same pola, których używają już istniejące wyjścia planu),
  3. dalszej drogi istniejącego powrotu: z9w -> trolle_edron_z9w_do_depo (od lądowania z8), gobliny -> A* po z8 do początku gobliny_edron_do_depo i ta trasa.
Nic nie wysyła do gry. NIEZWERYFIKOWANE NA ŻYWO: lina z10 -> z9 na tych polach (z9w i gobliny z9: lina z9 -> z8 jest sprawdzona dla z9w 21.10 i gobliny 17.10).
"""
import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generuj_rodziny_pietra as GP  # noqa: E402
import mapa as _mapa  # noqa: E402
import trasa_io  # noqa: E402
from spot_lib import chodliwe, skladowa  # noqa: E402

DEPO = (33173, 31796, 8)
# mapa -> (plan PLANY_PK, stanie z9 przed liną z9 -> z8, lądowanie z8 tej liny, istniejąca trasa dalej, czy po lądowaniu z8 potrzebny A* do jej początku)
EXITY = {
    "trolle_edron_z10w": ("edron", (33119, 31739, 9), (33119, 31741, 8), "trolle_edron_z9w_do_depo", False),
    "gobliny_edron_z10_zachod": ("gobliny_edron", (33092, 31836, 9), (33092, 31838, 8), "gobliny_edron_do_depo", True),
    "gobliny_edron_z10_wschod": ("gobliny_edron", (33092, 31836, 9), (33092, 31838, 8), "gobliny_edron_do_depo", True),
    "gobliny_edron_z10_poludnie": ("gobliny_edron", (33092, 31836, 9), (33092, 31838, 8), "gobliny_edron_do_depo", True),
}


def pole_liny(spec):
    """Pole liny na z10 = lądowanie dojścia pod dziurą (x, y, z10); lądowanie po linie = (x, y+1, z9)."""
    T = spec["hops"][-1][0]
    return (T[0], T[1], T[2] + 1), (T[0], T[1] + 1, T[2])


def stoiska(m, comp, pole):
    """Pola obok pola liny w składowej z10 (chodliwe, nie samo pole), północ pierwsza (jak domyślne stanie w wyprawa.droga_do_depo)."""
    kol = [(0, -1), (1, 0), (-1, 0), (1, -1), (-1, -1), (0, 1), (1, 1), (-1, 1)]
    return [(pole[0] + dx, pole[1] + dy, pole[2]) for dx, dy in kol if (pole[0] + dx, pole[1] + dy) in comp and chodliwe(m, (pole[0] + dx, pole[1] + dy, pole[2]))]


def zbuduj(nazwa, m=None):
    spec = GP.SPECY[nazwa]
    plan, stoi9, lad8, kont, a_gwiazdka = EXITY[nazwa]
    m = m or _mapa.Mapa()
    import json  # noqa: PLC0415
    dz = [tuple(p) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])]
    ogien = GP.ogien_pola()
    sciana = lambda z: [p for p in dz if p[2] == z] + sorted(p for p in ogien if p[2] == z)   # noqa: E731
    pole, lad9 = pole_liny(spec)
    comp10 = skladowa(m, (pole[0], pole[1], pole[2]), sciana(10))
    st10 = stoiska(m, comp10, pole)
    if not st10:
        raise SystemExit(f"{nazwa}: brak pola stania obok pola liny {pole}")
    if not chodliwe(m, lad9):
        raise SystemExit(f"{nazwa}: lądowanie po linie {lad9} niechodliwe")
    if lad9 in ogien or stoi9 in ogien:
        raise SystemExit(f"{nazwa}: lądowanie {lad9} albo stanie {stoi9} w ogniu/buforze")
    d9 = [] if lad9[:2] == stoi9[:2] else m.droga(lad9, stoi9, zajete=sorted(sciana(9)), dlugosc=0, limit=800000)
    if d9 is None:
        raise SystemExit(f"{nazwa}: brak drogi z9 {lad9[:2]} -> stanie {stoi9[:2]} z omijaniem ognia")
    pts = [lad9] + [(p[0], p[1], 9) for p in d9]
    if pts[-1] != stoi9:
        pts.append(stoi9)
    pts.append(lad8)
    kont_pts, kont_meta = trasa_io.wczytaj(kont)
    przes = 0
    if a_gwiazdka:
        d8 = m.droga(lad8, kont_pts[0], zajete=sorted(sciana(8)), dlugosc=0, limit=800000)
        if d8 is None:
            raise SystemExit(f"{nazwa}: brak drogi z8 {lad8[:2]} -> początek {kont} {kont_pts[0][:2]} z omijaniem ognia")
        pts += [(p[0], p[1], 8) for p in d8]
        if pts[-1] != kont_pts[0]:
            pts.append(kont_pts[0])
        przes = len(pts) - 1
        pts += kont_pts[1:]
    else:
        przes = len(pts)
        pts += kont_pts
    i_stoi = pts.index(stoi9)
    meta = [{"idx": 0, "typ": "start", "komentarz": f"lądowanie po linie z z10 ({pole[0]},{pole[1]}), z9"},
            {"idx": i_stoi, "typ": "przed_zmiana_pietra", "komentarz": f"stoję {stoi9[:2]} obok pola liny z9 -> z8, potem piętro 8"},
            {"idx": i_stoi + 1, "typ": "schody_w_gore",
             "komentarz": f"LINA: z9 {stoi9[:2]} -> z8 {lad8[:2]} (jak istniejące wyjście planu {plan}); lina z10 -> z9 z pola {pole[:2]} NIEZWERYFIKOWANA na żywo"}]
    meta += [dict(e, idx=e["idx"] + przes) for e in kont_meta if e["idx"] >= 1 or e["typ"] != "start"]
    return {"spec": spec, "plan": plan, "pole": pole, "lad9": lad9, "stoi10": st10, "stoi9": stoi9, "lad8": lad8, "pts": pts, "meta": meta, "kont": kont,
            "d9": len(d9)}


def wyjscie(nazwa, w):
    """Wpis do wyprawa.PLANY_PK[plan]["wyjscia"]: (pole liny z10, lądowanie z9, plik trasy dalej, (stanie, ...))."""
    return (w["pole"], w["lad9"], f"{w['spec']['plik']}_do_depo.json", tuple(w["stoi10"][:3]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m = _mapa.Mapa()
    for nazwa in EXITY:
        try:
            w = zbuduj(nazwa, m)
        except SystemExit as e:
            print(f"{nazwa}: NIE DA SIĘ: {e}")
            continue
        pts = w["pts"]
        print(f"{nazwa}_do_depo: {len(pts)} pkt (z9 {w['d9']} pól do stania {w['stoi9'][:2]}), start {pts[0]}, koniec {pts[-1]}, "
              f"piętra {sorted({q[2] for q in pts})}, plan {w['plan']}, wyjście {wyjscie(nazwa, w)}")
        if pts[-1] != DEPO:
            print("   UWAGA koniec nie w depo", pts[-1])
        if a.zapisz:
            print("   zapisano", trasa_io.zapisz(f"{w['spec']['plik']}_do_depo", pts, w["meta"]))


if __name__ == "__main__":
    main()
