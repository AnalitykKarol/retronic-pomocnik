#!/usr/bin/env python3
"""Edron, jaskinia trolli z9 zachód (x 33050-33100, y 31700-31752), z mapy klienta i spawnów CipSoft 7.4 (21.10).
Wskazówka: nagranie 17.10 trasy/edron_nowy_spot.json (223 pkt: z8 8, z9 203, z10 12); generator liczy z mapy, nie z nagrania.
Metoda jak generuj_trasy_edron_wschod.py i generuj_trasy_thais_pn.py (spot_lib: składowa, przystanki, pętla, obraz); nic nie wysyła do gry:

  python3 -I generuj_trasy_edron_z9z.py [--zapisz]        bez --zapisz tylko liczy i drukuje podsumowanie

Powstają (przy --zapisz), w trasy/ i dane_tibia/mapy/:
  trolle_edron_z9z_petla    pętla po zachodniej składowej z9 (ok. 870 pól; 34 trolle + 5 niedźwiedzi, żadnych innych potworów)
  trolle_edron_z9z_dojscie  edron_depo_trolle (depo -> z8 przy (33117,31775)) + z8 przez jaskinię trolli z8 do zejścia i lądowanie na z9
  trolle_edron_z9z.png, trolle_edron_z9z.json   podgląd trasy (czerwona), przystanki (różowe, numer = kolejność)

Składowa: z9 (33077,31728) to OSOBNA składowa od trolle_edron (pętla edron_trolle_petla jest na z8 x 33071-33119, y 31732-31779)
i od trolle_edron_z9w (z9 x 33112-33137, osobna składowa 313 pól). Wejście tylko z z8 składowej trolle_edron (zejścia 210):
(33081,31742,z8) i (33071,31752,z8); dojście więc prowadzi przez z8 trolle_edron (tam też trolle).
Ogień (21.10): znane pola z trasy/ogien_stale.json i trasy/ogien_epizody.json (format 21.10: słownik "x,y,z" w kluczu `pola`)
+ 1 pole bufora = ściana dla składowej, pętli i dojścia (też dla drogi dojścia, której spot_lib.przed_przejsciem nie omija).
Zejście z8 wybierane po kolorze 210 (spot_lib.zejscia odrzuca PRZESZKODY w kolorze podłogi); lądowanie pod nim.
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
from spot_lib import chodliwe, ladowanie, petla, przystanki, skladowa  # noqa: E402

NAZWA = "trolle_edron_z9z"
DOJSCIE_Z8 = "edron_depo_trolle"   # nagrane 15.10, kończy na z8 przy (33117,31775); wymaga liny (liny.py)
OGIEN_BUFOR = 1
POTWORY = ("troll", "bear")
OBSZAR_SPAWNOW = (33040, 33110, 31695, 31760)   # x1, x2, y1, y2: zachodnia składowa z9 (wschodnia, 313 pól, zaczyna się od x 33112)
KAND_Z8 = [(33081, 31742, 8), (33071, 31752, 8)]    # zejścia 210 z8 -> z9 (przejscia_pieter.py), oba w składowej trolle_edron z8
START_Z9 = (33081, 31742, 9)       # lądowanie nagrania (z8 (33080,31742) -> z9 (33081,31742)); sprawdzane z mapą


def ogien_pola():
    """Znany ogień (stały + epizody bota, oba formaty) z buforem OGIEN_BUFOR -> zbiór (x, y, z)."""
    pola = {tuple(p[:3]) for p in json.loads((ROOT / "trasy" / "ogien_stale.json").read_text()).get("pola", [])}
    try:
        ep = json.loads((ROOT / "trasy" / "ogien_epizody.json").read_text())
    except (OSError, ValueError):
        ep = {}
    ep = ep.get("pola", ep) if isinstance(ep, dict) else {}
    if isinstance(ep, dict):
        for k in ep:
            if isinstance(k, str) and k.count(",") == 2:
                pola.add(tuple(int(a) for a in k.split(",")))
    elif isinstance(ep, list):
        pola |= {tuple(x[:3]) for x in ep}
    b = OGIEN_BUFOR
    return {(x + dx, y + dy, z) for x, y, z in pola for dx in range(-b, b + 1) for dy in range(-b, b + 1)}


def droga_z_omijaniem(m, start, T, sciana):
    """(pole obok T, droga A* ze `start` bez startu, z polem obok) po piętrze T[2], omijająca `sciana` (inaczej niż spot_lib.przed_przejsciem)."""
    zle = {(p[0], p[1]) for p in sciana if p[2] == T[2]}
    best = None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            c = (T[0] + dx, T[1] + dy)
            if (dx or dy) and chodliwe(m, (c[0], c[1], T[2])) and c not in zle:
                d = [] if (c[0], c[1]) == (start[0], start[1]) else m.droga(start, c, zajete=sorted(sciana), dlugosc=0, limit=800000)
                if d is None:
                    continue
                d = [(p[0], p[1]) for p in d]
                if best is None or len(d) < len(best[1]):
                    best = (c, d)
    return best


def zbuduj():
    m = _mapa.Mapa()
    dz = [tuple(p) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])]
    ogien = ogien_pola()
    sciana = lambda z: [p for p in dz if p[2] == z] + sorted(p for p in ogien if p[2] == z)   # noqa: E731
    doj8, meta8 = trasa_io.wczytaj(DOJSCIE_Z8)
    S8 = doj8[-1]
    if S8[2] != 8:
        raise SystemExit(f"{DOJSCIE_Z8} nie kończy się na z8: {S8}")
    if S8 in ogien:
        raise SystemExit(f"koniec {DOJSCIE_Z8} {S8} w ogniu/buforze")

    best = None
    for T in KAND_Z8:
        if not m.flagi(*T) & _mapa.WIDZIANE or not m.flagi(*T) & _mapa.BEZ_DROGI or spot_lib.przeszkoda_na_podlodze(m, *T):
            print(f"zejście {T}: odpada (nie jest przejściem w mapie)")
            continue
        if T in ogien:
            print(f"zejście {T}: odpada (ogień/bufor)")
            continue
        try:
            L9 = ladowanie(m, T)
        except SystemExit as e:
            print(f"zejście {T}: {e}")
            continue
        if (L9[0], L9[1], 9) in ogien:
            print(f"zejście {T}: lądowanie {L9} w ogniu/buforze")
            continue
        r = droga_z_omijaniem(m, S8, T, sciana(8))
        if r is None:
            print(f"zejście {T}: brak drogi z {S8[:2]} z omijaniem ognia")
            continue
        print(f"zejście {T[:2]}: z8 {len(r[1])} pól, lądowanie {L9}")
        if best is None or len(r[1]) < len(best[2][1]):
            best = (T, L9, r)
    if best is None:
        raise SystemExit("brak drogi z końca edron_depo_trolle do żadnego zejścia")
    T, L9, (przed, d8) = best

    comp = skladowa(m, L9, sciana(9))
    spawny = [s for s in spot_lib.spawny(9, POTWORY, OBSZAR_SPAWNOW)]
    st = przystanki(spawny, comp)
    if len(comp) < 300 or not st:
        raise SystemExit(f"składowa za mała: {len(comp)} pól, przystanków {len(st)}")
    order, nodes, pelna = petla(m, 9, L9[:2], st, sciana(9))
    n = sum(t["n"] for t in st)
    print(f"{NAZWA}: składowa {len(comp)} pól, przystanków {len(st)}, potworów {n} (spawnów {sum(t['spawny'] for t in st)} z {len(spawny)}), "
          f"pętla {len(pelna)} pól, kolejność {order}")

    doj = list(doj8) + [(x, y, 8) for x, y in d8] + [T, L9]
    meta = [dict(e) for e in meta8]
    meta += [{"idx": len(doj) - 2, "typ": "przed_zmiana_pietra", "komentarz": f"zejście z8 {T[:2]} (kolor 210, flaga 2, z mapy 21.10; w nagraniu 17.10 z (33080,31742)) do zachodniej jaskini trolli z9; typ NIEZWERYFIKOWANY na żywo, droga z8 po jaskini trolli z8 omija znany ogień"},
             {"idx": len(doj) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z9 {L9[:2]}; po zejściu wejdź w pętlę {NAZWA}_petla"}]
    print(f"{NAZWA}_dojscie: {len(doj)} pkt (edron_depo_trolle {len(doj8)} + z8 {len(d8)} + zejście), zejście {T[:2]}")
    return m, (9, comp, st, order, nodes, pelna, doj, meta)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m, (z, comp, st, order, nodes, pelna, doj, meta) = zbuduj()
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    spot_lib.zapis_spotu(m, NAZWA, z, pelna, order, nodes, st, "trolle z9 zachod", jedn="potw.", opis_przyst="spawn(y) trolli/niedzwiedzi",
                         doj=doj, meta=meta)
    print("zapisano trasy/ i dane_tibia/mapy/ (wpisy mapy.json i spoty_nadzorca.json dodaj osobno)")


if __name__ == "__main__":
    main()
