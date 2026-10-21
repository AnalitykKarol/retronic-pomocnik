#!/usr/bin/env python3
"""Generuje trasy szczurów w Rookgaard z mapy klienta (mapa/map74.otmm) i spawnów CipSoft 7.4 (20.10).
Metoda jak patrol_gobliny_z8 (dane_tibia/mapy/README.md): składowa pól przechodnich piętra -> spawny szczurów w niej ->
przystanki (spawny <= 3 pola scalone) -> kolejność najbliższy sąsiad + 2-opt po odległościach A* -> pętla.
Uruchamiane offline, niczego nie wysyła do gry:

  python3 -I generuj_trasy_rook.py [--zapisz]        bez --zapisz tylko liczy i drukuje podsumowanie

Powstają (przy --zapisz), w trasy/ i dane_tibia/mapy/:
  rook_raty_z8_petla      pętla po jaskini szczurów z8 tuż pod miastem (872 pola)
  rook_raty_z8_dojscie    z miasta (z7) do wejścia (32046,32221,z7) i na z8; WEJŚCIE WYWNIOSKOWANE Z MAPY, niezweryfikowane w grze
  rook_kanaly_z11_petla   pętla po kanałach z11 (774 pola)
  rook_kanaly_z11_dojscie z depo w mieście (z7) do kanałów: odwrócone nagranie do_miasta (przejścia sprawdzone w grze)
  rook_raty_z8.png, rook_kanaly_z11.png  podgląd trasy (czerwona), przystanki (różowe, numer = kolejność)
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import mapa as _mapa  # noqa: E402
import odwroc_trase  # noqa: E402
import spot_lib  # noqa: E402
import trasa_io  # noqa: E402
# Klocki mieszkają w spot_lib.py (F0, 21.10); stare nazwy dalej tu, bo importują je inne skrypty (`import generuj_trasy_rook as g`).
from spot_lib import OBRAZY, SCAL, SNAP, SPAWNY, obraz, petla, przystanki, sasiedzi, skladowa, wynik  # noqa: E402,F401


def spawny_szczurow(z):
    return spot_lib.spawny(z, ("rat",))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m = _mapa.Mapa()
    dziury = json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])
    dz = [tuple(p) for p in dziury]
    sciana = lambda z: [p for p in dz if p[2] == z]   # noqa: E731  nauczone dziury = ściana dla A* i składowej

    # --- z8 pod miastem: wejście z7 (32046,32221) (kolor 210 na z7 i z8 w tym samym polu), lądowanie w składowej z8 ---
    Z8, WEJ7, LAD8 = 8, (32046, 32221, 7), (32046, 32222, 8)
    comp8 = skladowa(m, LAD8, sciana(Z8))
    st8 = przystanki(spawny_szczurow(Z8), comp8)
    ord8, nod8, p8 = petla(m, Z8, LAD8[:2], st8, sciana(Z8))
    wynik("rook_raty_z8", Z8, comp8, st8, ord8, nod8, p8)
    # dojście z7: od okolicy depo/świątyni (32061,32180) po A* do pola przed wejściem, wejście, lądowanie
    S7 = (32061, 32180, 7)
    przed = (WEJ7[0], WEJ7[1] - 1)
    d7 = m.droga(S7, przed, dlugosc=0, limit=400000)
    if d7 is None:
        raise SystemExit(f"brak drogi z7 {S7} -> {przed}")
    doj8 = [S7] + [tuple(p) for p in d7] + [WEJ7, LAD8]
    meta8 = [{"idx": len(doj8) - 2, "typ": "przed_zmiana_pietra", "komentarz": "pole przejścia z7 (kolor 210, flaga 2), typ przejścia (dziura/schody/kratka) NIEZWERYFIKOWANY w grze"},
             {"idx": len(doj8) - 1, "typ": "schody_w_dol", "komentarz": "lądowanie z8 (32046,32222) z mapy; po zejściu wejdź w pętlę rook_raty_z8_petla"}]
    print(f"rook_raty_z8_dojscie: {len(doj8)} pkt, z7 {len(d7)} pól do wejścia")

    # --- z11 kanały: dojście = odwrócone do_miasta (nagranie sprawdzone w grze), pętla po składowej z11 ---
    Z11, START11 = 11, (32021, 32159, 11)
    comp11 = skladowa(m, START11, sciana(Z11))
    st11 = przystanki(spawny_szczurow(Z11), comp11)
    ord11, nod11, p11 = petla(m, Z11, START11[:2], st11, sciana(Z11))
    wynik("rook_kanaly_z11", Z11, comp11, st11, ord11, nod11, p11)
    pkt, meta = trasa_io.wczytaj("do_miasta")
    doj11, meta11 = odwroc_trase.odwroc(pkt, meta)
    print(f"rook_kanaly_z11_dojscie: {len(doj11)} pkt (odwrócone do_miasta), start {doj11[0]}, koniec {doj11[-1]}")

    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    for nazwa, z, pelna, order, nodes, stops, tytul in (("rook_raty_z8", Z8, p8, ord8, nod8, st8, "szczury pod miastem"),
                                                         ("rook_kanaly_z11", Z11, p11, ord11, nod11, st11, "szczury w kanalach")):
        spot_lib.zapis_spotu(m, nazwa, z, pelna, order, nodes, stops, tytul, klucz="szczurow")
    trasa_io.zapisz("rook_raty_z8_dojscie", doj8, meta8)
    trasa_io.zapisz("rook_kanaly_z11_dojscie", doj11, meta11)
    print("zapisano trasy/ i dane_tibia/mapy/")


if __name__ == "__main__":
    main()
