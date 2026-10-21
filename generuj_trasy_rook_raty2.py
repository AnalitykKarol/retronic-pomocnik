#!/usr/bin/env python3
"""Rookgaard, drugi spot szczurów: dwa piętra (z9 i z10) pod środkiem miasta, z mapy klienta i spawnów CipSoft 7.4 (20.10).
Metoda jak generuj_trasy_rook.py (jego funkcje, od 21.10 w spot_lib.py: składowa, przystanki, pętla, obraz); nic nie wysyła do gry:

  python3 -I generuj_trasy_rook_raty2.py [--zapisz]        bez --zapisz tylko liczy i drukuje podsumowanie

Powstają (przy --zapisz), w trasy/ i dane_tibia/mapy/:
  rook_raty_z9_petla    pętla po jaskini z9 (432 pola, 27 szczurów)
  rook_raty_z9_dojscie  z depo w mieście (z7) przez schody w depo (32027,32197,z7), kieszeń z8 i kratkę (32029,32195,z8) na z9
  rook_raty_z10_petla   pętla po jaskini z10 (332 pola, 19 szczurów + 3 jaskiniowe)
  rook_raty_z10_dojscie to samo co z9 + zejście z z9 przez (32038,32212) na z10
  rook_raty_z9.png, rook_raty_z10.png  podgląd trasy (czerwona), przystanki (różowe, numer = kolejność)

Przejścia pięter wskazał Karol 20.10 (zszedł ręcznie "przez depo i kratkę", potem stał w jaskini z9) i potwierdza je mapa:
  z7 (32027,32197): flaga 2, kolor 210 (schody w depo); na z8 to samo pole jest schodami w górę, lądowanie obok, w kieszeni 33 pola;
  z8 (32029,32195): KRATKA, w mapie zwykłe pole (kolor 129, bez flagi 2), pod nim na z9 pole 210; bot używa jej jak kratek kanałów (Ctrl+klik),
                    lądowanie = dokładnie (32029,32195,z9);
  z9 (32038,32212): flaga 2, kolor 210; lądowanie (32038,32212,z10).
NIE uzywać szybu (32046,32188): to jedne schody z7-z8 (pierwsza wersja z 20.10 była błędna).
Typ i lądowanie dalej NIEZWERYFIKOWANE przez bota; pierwszy przebieg dojścia na żywo sprawdza całość.
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import mapa as _mapa  # noqa: E402
import spot_lib  # noqa: E402
import trasa_io  # noqa: E402
# Klocki mieszkają w spot_lib.py (F0, 21.10); stare nazwy dalej tu, bo importują je inne skrypty (`import generuj_trasy_rook_raty2 as r2`).
from spot_lib import chodliwe, ladowanie, przed_przejsciem, petla, przystanki, skladowa  # noqa: E402,F401

S7 = (32061, 32180, 7)            # okolica depo w mieście, jak w rook_raty_z8_dojscie
T7 = (32027, 32197, 7)            # schody w depo: z7 -> z8
T8 = (32029, 32195, 8)            # kratka w kieszeni z8: z8 -> z9 (pole chodliwe, bez flagi 2)
T9 = (32038, 32212, 9)            # z9 -> z10 (środek jaskini szczurów)
POTWORY = ("rat", "cave rat")


def spawny(z):
    return spot_lib.spawny(z, POTWORY)


def zbuduj():
    m = _mapa.Mapa()
    dz = [tuple(p) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])]
    sciana = lambda z: [p for p in dz if p[2] == z]   # noqa: E731
    for T in (T7, T8, T9):
        if not m.flagi(*T) & _mapa.WIDZIANE:
            raise SystemExit(f"{T}: pole niewidziane w mapie")

    # --- z7 -> z8: schody w depo; kieszeń z8 to składowa, w której leży kratka T8 ---
    przed7, d7 = przed_przejsciem(m, S7, T7)
    L8 = None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            c = (T7[0] + dx, T7[1] + dy, 8)
            if chodliwe(m, c):
                comp8 = skladowa(m, c, sciana(8))
                if (T8[0], T8[1]) in comp8:
                    L8 = ladowanie(m, T7, comp8)
    if L8 is None:
        raise SystemExit("kieszeń z8 pod schodami w depo nie zawiera kratki (32029,32195)")
    przed8, d8 = przed_przejsciem(m, L8, T8, sciana(8))
    # --- z8 -> z9: kratka, lądowanie dokładnie pod nią ---
    L9 = (T8[0], T8[1], 9)
    if not chodliwe(m, L9):
        raise SystemExit(f"lądowanie {L9} niechodliwe")
    comp9 = skladowa(m, L9, sciana(9))
    # --- z9 -> z10 ---
    przed9, d9 = przed_przejsciem(m, L9, T9, sciana(9))
    L10 = ladowanie(m, T9)
    comp10 = skladowa(m, L10, sciana(10))
    L10 = ladowanie(m, T9, comp10)

    doj9 = [S7] + [(x, y, 7) for x, y in d7] + [T7, L8]
    meta9 = [{"idx": len(doj9) - 2, "typ": "przed_zmiana_pietra", "komentarz": "schody w depo z7 (kolor 210, flaga 2), wskazane przez Karola 20.10; typ NIEZWERYFIKOWANY przez bota"},
             {"idx": len(doj9) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z8 {L8[:2]} w kieszeni z kratką (z mapy)"}]
    doj9 += [(x, y, 8) for x, y in d8] + [T8, L9]
    meta9 += [{"idx": len(doj9) - 2, "typ": "przed_zmiana_pietra", "komentarz": "KRATKA z8 (32029,32195): w mapie zwykłe pole bez flagi 2, bot używa jej jak kratki kanału (Ctrl+klik)"},
              {"idx": len(doj9) - 1, "typ": "kratka_w_dol", "komentarz": f"lądowanie z9 {L9[:2]} dokładnie pod kratką; po zejściu wejdź w pętlę rook_raty_z9_petla"}]
    doj10 = list(doj9) + [(x, y, 9) for x, y in d9] + [T9, L10]
    meta10 = [dict(e) for e in meta9]
    meta10[-1] = {"idx": len(doj9) - 1, "typ": "kratka_w_dol", "komentarz": f"lądowanie z9 {L9[:2]} pod kratką; dalej A* po z9 do przejścia (32038,32212)"}
    meta10 += [{"idx": len(doj10) - 2, "typ": "przed_zmiana_pietra", "komentarz": "przejście z9 -> z10 (kolor 210, flaga 2)"},
               {"idx": len(doj10) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z10 {L10[:2]}; po zejściu wejdź w pętlę rook_raty_z10_petla"}]

    wyniki = {}
    for nazwa, z, comp, start, doj, meta in (("rook_raty_z9", 9, comp9, L9, doj9, meta9), ("rook_raty_z10", 10, comp10, L10, doj10, meta10)):
        st = przystanki(spawny(z), comp)
        order, nodes, pelna = petla(m, z, start[:2], st, sciana(z))
        szcz = sum(t["n"] for t in st)
        print(f"{nazwa}: składowa {len(comp)} pól, przystanków {len(st)}, potworów {szcz}, pętla {len(pelna)} pól, dojście {len(doj)} pkt, kolejność {order}")
        wyniki[nazwa] = (z, comp, st, order, nodes, pelna, doj, meta)
    return m, wyniki


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m, wyniki = zbuduj()
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    tytuly = {"rook_raty_z9": "szczury z9", "rook_raty_z10": "szczury i jaskiniowe z10"}
    for nazwa, (z, comp, st, order, nodes, pelna, doj, meta) in wyniki.items():
        spot_lib.zapis_spotu(m, nazwa, z, pelna, order, nodes, st, tytuly[nazwa], doj=doj, meta=meta)
    print("zapisano trasy/ i dane_tibia/mapy/ (wpisy mapy.json dodaj osobno)")


if __name__ == "__main__":
    main()
