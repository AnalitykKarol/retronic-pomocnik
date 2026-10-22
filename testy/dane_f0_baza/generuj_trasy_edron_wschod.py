#!/usr/bin/env python3
"""Edron, jaskinia trolli: wschodnie skrzydło z9 i z10, z mapy klienta i spawnów CipSoft 7.4 (21.10).
Metoda jak generuj_trasy_rook_raty2.py (składowa, przystanki, pętla, obraz); nic nie wysyła do gry:

  python3 -I generuj_trasy_edron_wschod.py [--zapisz]        bez --zapisz tylko liczy i drukuje podsumowanie

Powstają (przy --zapisz), w trasy/ i dane_tibia/mapy/:
  trolle_edron_z9w_petla    pętla po wschodniej jaskini z9 (osobna składowa, ok. 313 pól, 15 trolli w 5 spawnach)
  trolle_edron_z9w_dojscie  edron_depo_trolle (depo -> z8 przy (33117,31775)) + z8 do schodów (33115,31744) i zejście na z9
  trolle_edron_z10w_petla   pętla po wschodniej jaskini z10 (ok. 283 pola: 7 trolli, 3 niedźwiedzie, 2 swamp trolle, frost troll)
  trolle_edron_z10w_dojscie to samo co z9w + z9 do przejścia (33127,31726) i zejście na z10
  trolle_edron_z9w.png, trolle_edron_z10w.png  podgląd trasy (czerwona), przystanki (różowe, numer = kolejność)

Przejścia pięter z mapy (flaga 2, kolor 210), sąsiedztwo składowych sprawdzone flood-fillem 21.10:
  z8 (33115,31744) i (33119,31740): pod nimi tylko wschodnia składowa z9; na z9 (33112,31742) są schody w górę do z8.
  z9 (33127,31726) i (33128,31729): pod nimi wschodnia składowa z10; na z10 (33124,31728) w górę do z9 wschód.
Typ (schody/dziura/drabina/lina) i dokładne lądowanie NIEZWERYFIKOWANE w grze; pierwszy przebieg dojścia sprawdza całość.
Na z8 na północ (33097,31686) są 2 smoki w osobnej składowej (wejście z powierzchni z7): te trasy tam nie prowadzą.
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generuj_trasy_rook as g  # noqa: E402
import generuj_trasy_rook_raty2 as r2  # noqa: E402
import mapa as _mapa  # noqa: E402
import trasa_io  # noqa: E402

DOJSCIE_Z8 = "edron_depo_trolle"   # nagrane 15.10, kończy na z8 przy (33117,31775)
T8 = (33115, 31744, 8)             # z8 -> z9 wschód
Z9W = (33124, 31746, 9)            # punkt we wschodniej składowej z9 (spawn trolli)
T9 = (33127, 31726, 9)             # z9 wschód -> z10 wschód
Z10W = (33129, 31727, 10)          # punkt we wschodniej składowej z10 (spawn trolli)
POTWORY = ("troll", "bear", "swamp troll", "frost troll")


def spawny(z):
    dane = json.loads(g.SPAWNY.read_text())["potwory"]
    return [s for mo in dane if mo["nazwa"] in POTWORY for s in mo.get("spawny", []) if s["z"] == z]


def najblizsze(comp, p):
    return min(comp, key=lambda c: (max(abs(c[0] - p[0]), abs(c[1] - p[1])), c))


def zbuduj():
    m = _mapa.Mapa()
    dz = [tuple(p) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])]
    sciana = lambda z: [p for p in dz if p[2] == z]   # noqa: E731
    for T in (T8, T9):
        if not m.flagi(*T) & _mapa.WIDZIANE:
            raise SystemExit(f"{T}: pole niewidziane w mapie")

    doj8, meta8 = trasa_io.wczytaj(DOJSCIE_Z8)
    S8 = doj8[-1]
    if S8[2] != 8:
        raise SystemExit(f"{DOJSCIE_Z8} nie kończy się na z8: {S8}")

    comp9 = g.skladowa(m, (*najblizsze(g.skladowa(m, Z9W, sciana(9)) or {Z9W[:2]}, Z9W[:2]), 9), sciana(9))
    comp10 = g.skladowa(m, Z10W, sciana(10))
    if len(comp9) < 100 or len(comp10) < 100:
        raise SystemExit(f"składowe za małe: z9 {len(comp9)}, z10 {len(comp10)}")

    # --- z8 -> z9 wschód ---
    _, d8 = r2.przed_przejsciem(m, S8, T8, sciana(8))
    L9 = r2.ladowanie(m, T8, comp9)
    # --- z9 wschód -> z10 wschód ---
    _, d9 = r2.przed_przejsciem(m, L9, T9, sciana(9))
    L10 = r2.ladowanie(m, T9, comp10)

    doj9 = list(doj8)
    meta9 = [dict(e) for e in meta8]
    doj9 += [(x, y, 8) for x, y in d8] + [T8, L9]
    meta9 += [{"idx": len(doj9) - 2, "typ": "przed_zmiana_pietra", "komentarz": "przejście z8 (33115,31744) do wschodniej jaskini z9 (kolor 210, flaga 2, z mapy 21.10); typ NIEZWERYFIKOWANY"},
              {"idx": len(doj9) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z9 {L9[:2]} we wschodniej składowej; po zejściu wejdź w pętlę trolle_edron_z9w_petla"}]
    doj10 = list(doj9) + [(x, y, 9) for x, y in d9] + [T9, L10]
    meta10 = [dict(e) for e in meta9]
    meta10[-1] = {"idx": len(doj9) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z9 {L9[:2]}; dalej A* po z9 do przejścia (33127,31726)"}
    meta10 += [{"idx": len(doj10) - 2, "typ": "przed_zmiana_pietra", "komentarz": "przejście z9 (33127,31726) do wschodniej jaskini z10 (kolor 210, flaga 2); typ NIEZWERYFIKOWANY"},
               {"idx": len(doj10) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z10 {L10[:2]}; po zejściu wejdź w pętlę trolle_edron_z10w_petla"}]

    wyniki = {}
    for nazwa, z, comp, start, doj, meta in (("trolle_edron_z9w", 9, comp9, L9, doj9, meta9),
                                             ("trolle_edron_z10w", 10, comp10, L10, doj10, meta10)):
        st = g.przystanki(spawny(z), comp)
        order, nodes, pelna = g.petla(m, z, start[:2], st, sciana(z))
        n = sum(t["n"] for t in st)
        print(f"{nazwa}: składowa {len(comp)} pól, przystanków {len(st)}, potworów {n}, pętla {len(pelna)} pól, "
              f"dojście {len(doj)} pkt (z8 od {S8[:2]}: {len(d8)} pól), lądowanie {start}, kolejność {order}")
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
    tytuly = {"trolle_edron_z9w": "trolle z9 wschod", "trolle_edron_z10w": "trolle z10 wschod"}
    for nazwa, (z, comp, st, order, nodes, pelna, doj, meta) in wyniki.items():
        trasa_io.zapisz(f"{nazwa}_petla", [(x, y, z) for x, y in pelna])
        g.obraz(m, z, pelna, order, nodes, st, g.OBRAZY / f"{nazwa}.png", tytuly[nazwa], jedn="potw.", opis_przyst="spawn(y) trolli")
        (g.OBRAZY / f"{nazwa}.json").write_text(json.dumps({
            "start": [*nodes[0], z], "dlugosc_petli": len(pelna),
            "przystanki": [{"kolejnosc": k, "x": nodes[o][0], "y": nodes[o][1], "z": z,
                            **({} if o == 0 else {"potworow": st[o - 1]["n"], "spawnow": st[o - 1]["spawny"]})}
                           for k, o in enumerate(order)]}, ensure_ascii=False, indent=1))
        trasa_io.zapisz(f"{nazwa}_dojscie", doj, meta)
    print("zapisano trasy/ i dane_tibia/mapy/ (wpisy mapy.json dodaj osobno)")


if __name__ == "__main__":
    main()
