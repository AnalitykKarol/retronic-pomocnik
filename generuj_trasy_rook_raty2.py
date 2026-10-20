#!/usr/bin/env python3
"""Rookgaard, drugi spot szczurów: dwa piętra (z9 i z10) pod środkiem miasta, z mapy klienta i spawnów CipSoft 7.4 (20.10).
Metoda jak generuj_trasy_rook.py (jego funkcje: składowa, przystanki, pętla, obraz); nic nie wysyła do gry:

  python3 -I generuj_trasy_rook_raty2.py [--zapisz]        bez --zapisz tylko liczy i drukuje podsumowanie

Powstają (przy --zapisz), w trasy/ i dane_tibia/mapy/:
  rook_raty_z9_petla    pętla po jaskini z9 (432 pola, 27 szczurów)
  rook_raty_z9_dojscie  z depo w mieście (z7) szybem (32046,188): z7 -> z8 -> z9
  rook_raty_z10_petla   pętla po jaskini z10 (332 pola, 19 szczurów + 3 jaskiniowe)
  rook_raty_z10_dojscie to samo co z9 + zejście z z9 przez (32038,32212) na z10
  rook_raty_z9.png, rook_raty_z10.png  podgląd trasy (czerwona), przystanki (różowe, numer = kolejność)

WSZYSTKIE PRZEJŚCIA PIĘTER SĄ WYWNIOSKOWANE Z MAPY (kolor 210 + flaga 2) i NIEZWERYFIKOWANE W GRZE; lądowanie = pole składowej
najbliższe (T.x, T.y+1), jak w rook_raty_z8_dojscie. Pierwsze zejście sprawdzić na żywo z Karolem (jedno wywołanie).
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generuj_trasy_rook as g  # noqa: E402
import mapa as _mapa  # noqa: E402
import trasa_io  # noqa: E402

S7 = (32061, 32180, 7)            # okolica depo w mieście, jak w rook_raty_z8_dojscie
T7 = (32046, 32188, 7)            # szyb w mieście: z7 -> z8
T8 = (32046, 32188, 8)            # ten sam szyb: z8 -> z9
T9 = (32038, 32212, 9)            # z9 -> z10 (środek jaskini szczurów)
POTWORY = ("rat", "cave rat")


def przejsciowe(m, p):
    """Pole zmiany piętra: kolor 210 i flaga 2 (schody/dziura/lina/drabina)."""
    pole = m.pole(*p)
    return bool(pole and pole[0] & 2 and pole[1] == 210)


def ladowanie(m, T, comp=None):
    """Pole lądowania na piętrze T[2]+1: chodliwe, najbliższe (T.x, T.y+1); gdy `comp` podano, tylko z niej."""
    z = T[2] + 1
    cel = (T[0], T[1] + 1)
    kand = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            x, y = T[0] + dx, T[1] + dy
            f = m.flagi(x, y, z)
            if f & _mapa.WIDZIANE and not f & (_mapa.SCIANA | _mapa.BEZ_DROGI) and (comp is None or (x, y) in comp):
                kand.append((x, y))
    if not kand:
        raise SystemExit(f"brak pola lądowania pod przejściem {T}")
    x, y = min(kand, key=lambda c: (max(abs(c[0] - cel[0]), abs(c[1] - cel[1])), abs(c[0] - cel[0]) + abs(c[1] - cel[1]), c))
    return (x, y, z)


def przed_przejsciem(m, start, T, ściana=()):
    """(pole obok T, droga A* ze `start` (bez startu, z polem obok)) - najkrótsze po sąsiadach T na piętrze T[2]."""
    zle = {(p[0], p[1]) for p in ściana if p[2] == T[2]}
    best = None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            c = (T[0] + dx, T[1] + dy)
            f = m.flagi(c[0], c[1], T[2])
            if (dx or dy) and f & _mapa.WIDZIANE and not f & (_mapa.SCIANA | _mapa.BEZ_DROGI) and c not in zle:
                if (c[0], c[1]) == (start[0], start[1]):
                    d = []
                else:
                    d = m.droga(start, c, dlugosc=0, limit=400000)
                    if d is None:
                        continue
                    d = [(p[0], p[1]) for p in d]
                if best is None or len(d) < len(best[1]):
                    best = (c, d)
    if best is None:
        raise SystemExit(f"brak drogi {start} -> sąsiad przejścia {T}")
    return best


def spawny(z):
    dane = json.loads(g.SPAWNY.read_text())["potwory"]
    return [s for mo in dane if mo["nazwa"] in POTWORY for s in mo.get("spawny", []) if s["z"] == z]


def zbuduj():
    m = _mapa.Mapa()
    dz = [tuple(p) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])]
    sciana = lambda z: [p for p in dz if p[2] == z]   # noqa: E731
    for T in (T7, T8, T9):
        if not przejsciowe(m, T):
            raise SystemExit(f"{T}: to nie jest pole zmiany piętra (kolor 210 + flaga 2)")

    # --- z7 -> z8 -> z9: szyb w mieście ---
    przed7, d7 = przed_przejsciem(m, S7, T7)
    L8 = ladowanie(m, T7)
    przed8 = (L8[0], L8[1])
    if max(abs(przed8[0] - T8[0]), abs(przed8[1] - T8[1])) > 1:
        przed8, d8 = przed_przejsciem(m, L8, T8, sciana(8))
    else:
        d8 = []
    L9 = ladowanie(m, T8)
    comp9 = g.skladowa(m, L9, sciana(9))
    L9 = ladowanie(m, T8, comp9)
    # --- z9 -> z10 ---
    przed9, d9 = przed_przejsciem(m, L9, T9, sciana(9))
    L10 = ladowanie(m, T9)
    comp10 = g.skladowa(m, L10, sciana(10))
    L10 = ladowanie(m, T9, comp10)

    def tr(p):
        return (p[0], p[1], 7)

    doj9, meta9 = [S7] + [(x, y, 7) for x, y in d7] + [T7, L8], []
    meta9 += [{"idx": len(doj9) - 2, "typ": "przed_zmiana_pietra", "komentarz": "szyb w mieście z7 (kolor 210, flaga 2), typ przejścia NIEZWERYFIKOWANY w grze"},
              {"idx": len(doj9) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z8 {L8[:2]} z mapy"}]
    if d8:
        doj9 += [(x, y, 8) for x, y in d8]
    doj9 += [T8, L9]
    meta9 += [{"idx": len(doj9) - 2, "typ": "przed_zmiana_pietra", "komentarz": "ten sam szyb z8 (kolor 210, flaga 2), NIEZWERYFIKOWANY w grze"},
              {"idx": len(doj9) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z9 {L9[:2]} z mapy; po zejściu wejdź w pętlę rook_raty_z9_petla"}]
    # dojście z10 = dojście z9 bez końcowego "wejdź w pętlę", dalej A* po z9 do T9 i zejście
    doj10 = list(doj9) + [(x, y, 9) for x, y in d9] + [T9, L10]
    meta10 = list(meta9)
    meta10[-1] = {"idx": len(doj9) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z9 {L9[:2]} z mapy; dalej A* po z9 do przejścia (32038,32212)"}
    meta10 += [{"idx": len(doj10) - 2, "typ": "przed_zmiana_pietra", "komentarz": "przejście z9 -> z10 (kolor 210, flaga 2), NIEZWERYFIKOWANE w grze"},
               {"idx": len(doj10) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z10 {L10[:2]} z mapy; po zejściu wejdź w pętlę rook_raty_z10_petla"}]

    wyniki = {}
    for nazwa, z, comp, start, doj, meta in (("rook_raty_z9", 9, comp9, L9, doj9, meta9), ("rook_raty_z10", 10, comp10, L10, doj10, meta10)):
        st = g.przystanki(spawny(z), comp)
        order, nodes, pelna = g.petla(m, z, start[:2], st, sciana(z))
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
        trasa_io.zapisz(f"{nazwa}_petla", [(x, y, z) for x, y in pelna])
        g.obraz(m, z, pelna, order, nodes, st, g.OBRAZY / f"{nazwa}.png", tytuly[nazwa])
        (g.OBRAZY / f"{nazwa}.json").write_text(json.dumps({
            "start": [*nodes[0], z], "dlugosc_petli": len(pelna),
            "przystanki": [{"kolejnosc": k, "x": nodes[o][0], "y": nodes[o][1], "z": z,
                            **({} if o == 0 else {"potworow": st[o - 1]["n"], "spawnow": st[o - 1]["spawny"]})}
                           for k, o in enumerate(order)]}, ensure_ascii=False, indent=1))
        trasa_io.zapisz(f"{nazwa}_dojscie", doj, meta)
    print("zapisano trasy/ i dane_tibia/mapy/ (wpisy mapy.json dodaj osobno)")


if __name__ == "__main__":
    main()
