#!/usr/bin/env python3
"""Thais północ, jaskinia trolli z8 i z9 (ok. 107 pól na N od świątyni), z mapy klienta i spawnów CipSoft 7.4 (21.10).
Metoda jak generuj_trasy_rook.py (składowa, przystanki, pętla, obraz; od 21.10 w spot_lib.py); nic nie wysyła do gry:

  python3 -I generuj_trasy_thais_pn.py [--zapisz]        bez --zapisz tylko liczy i drukuje podsumowanie

Powstają (przy --zapisz), w trasy/ i dane_tibia/mapy/:
  thais_pn_z8_petla   pętla po z8 (składowa ok. 1000 pól): trolle, szczury, cave raty, pająki, bugi
  thais_pn_z9_petla   pętla po z9 (składowa ok. 257 pól): 16 trolli
  thais_pn_z8.png, thais_pn_z9.png  podgląd: trasa (czerwona), przystanki (różowe), strefa zakazana (fiolet)

Decyzja Karola 21.10: trasa omija POISON SPIDERY. Strefa zakazana = pola w promieniu STREFA (Chebyshev) od środka
spawnu poison spidera na tym samym piętrze; ani przystanek, ani droga A* przez nią nie przechodzi. Na z8 spawn
(32326,32155): 2 szt., tuż przy nim pająki (32322,32156), które też odpadają. Na z9 poison spidery (32352,32122) są
w osobnej kieszeni za ścianą. Przejścia pięter (flaga 2) A* omija sam, więc pętla z8 nie wejdzie w zejścia do cyklopów
na z9 ((32368,32112), (32374,32100), (32376,32128)).

Dojście z8 (thais_pn_z8_dojscie): z depo Thais (32348,32225,z7; start depo_troll_cave) A* po z7 do najbliższego ZEJŚCIA:
pole z7 z flagą 2, nad którym (3x3 na z6) nie ma nic chodliwego, a obok na z8 jest pole składowej pętli bez strefy
poison spiderów. Żółte bloki (kolor 210) nad jaskinią to schody W GÓRĘ: nad nimi chodliwe z6 (sprawdzone na żywo 21.10
16:29: kutangen z (32345,32146,z7) wszedł na z6). Zejścia z mapy: (32347,32123) i (32335,32174) (kolor 24); drugie ląduje
w korytarzu za strefą poison spiderów, więc odpada samo.
ZEJŚCIE (32347,32123,z7) TO ZASYPANA DZIURA: trzeba ŁOPATY (sprawdzone na żywo 21.10 16:36, kutangen: łopata z pola obok,
krok, lądowanie (32347,32123,z8)). Pole jest w pietra.ZASYPANE; postać musi mieć shovel w plecaku.
Dojścia na z9 BRAK: mapa nie mówi, jak zejść z z8 na trolle z9 (z9 (32339,32122) to drabina w górę, nad nią na z8
ściana; drugie przejście (32326,32158) jest 3 pola od poison spiderów).
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
from spot_lib import ladowanie, petla, przed_przejsciem, przystanki, skladowa  # noqa: E402

STREFA = 6                                   # promień strefy zakazanej wokół spawnu poison spidera
CEL = {8: ("troll", "rat", "cave rat", "spider", "bug"), 9: ("troll",)}
START = {8: (32356, 32131), 9: (32325, 32143)}   # spawny trolli wewnątrz składowych
ZAKAZANE = ("poison spider",)
S7 = (32348, 32225, 7)                       # depo Thais, start nagranego depo_troll_cave
MIN_ODL_DOJSCIA = 15                         # dojście z8 woli drogi >= tyle pól od spawnu poison spidera (21.10: 23 vs 11 pól)
OBSZAR = (32260, 32085, 32390, 32185)        # x0, y0, x1, y1: gdzie szukać zejść z z7 nad jaskinią


def spawny(z, nazwy):
    return spot_lib.spawny(z, nazwy)


def strefa(z):
    return spot_lib.strefa_zakazana(spawny(z, ZAKAZANE), z, STREFA)


def zbuduj():
    m = _mapa.Mapa()
    dz = [tuple(p) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])]
    wyniki = {}
    for z in (8, 9):
        zle = strefa(z)
        sciana = [p for p in dz if p[2] == z] + sorted(zle)
        comp = skladowa(m, (*START[z], z), sciana)
        caly = skladowa(m, (*START[z], z), [p for p in dz if p[2] == z])
        jady = [(s["x"], s["y"]) for s in spawny(z, ZAKAZANE)]
        st = [t for t in przystanki(spawny(z, CEL[z]), comp)   # przystanek nie bliżej niż STREFA + 2 od spawnu poison spidera
              if not any(max(abs(t["pt"][0] - p[0]), abs(t["pt"][1] - p[1])) <= STREFA + 2 for p in jady)]
        order, nodes, pelna = petla(m, z, START[z], st, sciana)
        w_strefie = [p for p in pelna if (p[0], p[1], z) in zle]
        if w_strefie:
            raise SystemExit(f"z{z}: pętla wchodzi w strefę poison spiderów: {w_strefie[:5]}")
        n = sum(t["n"] for t in st)
        print(f"thais_pn_z{z}: składowa {len(caly)} pól (bez strefy {len(comp)}), przystanków {len(st)}, potworów {n}, "
              f"pętla {len(pelna)} pól, strefa zakazana {len({(p[0], p[1]) for p in zle} & caly)} pól składowej, kolejność {order}")
        wyniki[f"thais_pn_z{z}"] = (z, comp, st, order, nodes, pelna, zle)
    # --- dojście z8: depo Thais (z7) -> najkrótsze zejście z ZEJSCIA_Z7 -> lądowanie w składowej z8 ---
    comp8, zle8 = wyniki["thais_pn_z8"][1], wyniki["thais_pn_z8"][6]
    best = None
    kandydaci = spot_lib.zejscia(m, 7, OBSZAR, comp8)
    print(f"zejścia z7 do jaskini (bez schodów w górę): {[t[:2] for t in kandydaci]}")
    for T in kandydaci:
        try:
            _, d7 = przed_przejsciem(m, S7, T)
            L8 = ladowanie(m, T, comp8)
        except SystemExit as e:
            print(f"zejście {T[:2]}: pomijam ({e})")
            continue
        if (L8[0], L8[1], 8) in zle8:
            continue
        # z8: od lądowania do najbliższego punktu pętli drogą omijającą strefę (A* bota strefy nie zna)
        d8 = spot_lib.dojscie_do_petli(m, L8, wyniki["thais_pn_z8"][5], zle8)
        if d8 is None:
            print(f"zejście {T[:2]}: brak drogi z lądowania do pętli poza strefą")
            continue
        jady = [(sp["x"], sp["y"]) for sp in spawny(8, ZAKAZANE)]
        odl = min((max(abs(q[0] - j[0]), abs(q[1] - j[1])) for q in [L8[:2]] + d8 for j in jady), default=99)
        klucz = (odl < MIN_ODL_DOJSCIA, len(d7) + len(d8))
        print(f"zejście {T[:2]}: z7 {len(d7)} + z8 {len(d8)} pól, najbliżej poison spidera {odl} pól")
        if best is None or klucz < best[4]:
            best = (T, d7, L8, d8, klucz)
    if best is None:
        raise SystemExit("brak drogi z depo Thais do żadnego zejścia")
    T, d7, L8, d8, _ = best
    print(f"wybrane zejście {T[:2]}: z7 {len(d7)} pól, z8 do pętli {len(d8)} pól")
    doj = [S7] + [(x, y, 7) for x, y in d7] + [T, L8]
    meta = [{"idx": 0, "typ": "start", "komentarz": "depo Thais (start depo_troll_cave), wygenerowane z mapy 21.10"},
            {"idx": len(doj) - 2, "typ": "przed_zmiana_pietra", "komentarz": f"zejście z7 {T[:2]} do jaskini Thais północ (flaga 2, bez z6 nad nim); (32347,32123) = zasypana dziura, ŁOPATA (pietra.ZASYPANE, sprawdzone 21.10)"},
            {"idx": len(doj) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z8 {L8[:2]}; dalej po z8 do pętli drogą omijającą strefę poison spiderów"}]
    doj += [(x, y, 8) for x, y in d8]
    print(f"thais_pn_z8_dojscie: {len(doj)} pkt, zejście {T[:2]}, lądowanie {L8}")
    wyniki["_dojscie"] = (doj, meta)
    return m, wyniki


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m, wyniki = zbuduj()
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    doj, meta = wyniki.pop("_dojscie")
    trasa_io.zapisz("thais_pn_z8_dojscie", doj, meta)
    for nazwa, (z, comp, st, order, nodes, pelna, zle) in wyniki.items():
        spot_lib.zapis_spotu(m, nazwa, z, pelna, order, nodes, st, f"Thais polnoc z{z}", jedn="potw.", opis_przyst="spawn(y) celow",
                             ekstra={"strefa_poison_spider": STREFA}, strefa=zle)
    print("zapisano trasy/ i dane_tibia/mapy/ (z8 z dojściem, z9 bez; wpisy mapy.json dodaj osobno)")


if __name__ == "__main__":
    main()
