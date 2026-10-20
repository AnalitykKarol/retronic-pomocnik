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
import trasa_io  # noqa: E402

SPAWNY = ROOT / "dane_tibia" / "serwer74" / "potwory_pelne.json"
OBRAZY = ROOT / "dane_tibia" / "mapy"
SCAL = 3                     # spawny bliższe niż tyle pól (Chebyshev) = jeden przystanek
SNAP = 3                     # środek spawnu poza składową: bierzemy go, gdy najbliższe pole składowej jest <= tyle pól


def sasiedzi(x, y):
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                yield x + dx, y + dy


def skladowa(m, start, ściany=()):
    """Pola przechodnie piętra osiągalne od `start` (x, y, z) bez schodów/dziur (flaga 2) i bez `ściany` ((x,y,z))."""
    x0, y0, z = start
    zle = {(p[0], p[1]) for p in ściany if p[2] == z}
    widziane, stos = {(x0, y0)}, [(x0, y0)]
    while stos:
        x, y = stos.pop()
        for n in sasiedzi(x, y):
            if n in widziane or n in zle:
                continue
            f = m.flagi(n[0], n[1], z)
            if f & _mapa.WIDZIANE and not f & (_mapa.SCIANA | _mapa.BEZ_DROGI):
                widziane.add(n)
                stos.append(n)
    return widziane


def przystanki(spawny_z, comp):
    """Spawny szczurów -> przystanki: środek snapowany do najbliższego pola składowej, bliskie scalone."""
    out = []
    for s in sorted(spawny_z, key=lambda s: (s["x"], s["y"])):
        p = (s["x"], s["y"])
        if p not in comp:
            bl = min(comp, key=lambda c: (max(abs(c[0] - p[0]), abs(c[1] - p[1])), abs(c[0] - p[0]) + abs(c[1] - p[1])))
            if max(abs(bl[0] - p[0]), abs(bl[1] - p[1])) > SNAP:
                continue
            p = bl
        for t in out:
            if max(abs(t["pt"][0] - p[0]), abs(t["pt"][1] - p[1])) <= SCAL:
                t["n"] += s["ilosc"]
                t["spawny"] += 1
                break
        else:
            out.append({"pt": p, "n": s["ilosc"], "spawny": 1})
    return out


def petla(m, z, start, stops, zajete):
    """(kolejność, trasa [(x,y)...]): pętla od `start` po przystankach; najbliższy sąsiad + 2-opt po długości A*."""
    nodes = [tuple(start)] + [t["pt"] for t in stops]
    N = len(nodes)
    cache = {}

    def droga(i, j):
        if (i, j) not in cache:
            d = m.droga((nodes[i][0], nodes[i][1], z), (nodes[j][0], nodes[j][1]), zajete=zajete, dlugosc=0, limit=400000)
            if d is None:
                raise SystemExit(f"brak drogi {nodes[i]} -> {nodes[j]} (z{z})")
            cache[(i, j)] = [(p[0], p[1]) for p in d]
        return cache[(i, j)]

    dist = [[0 if i == j else len(droga(i, j)) for j in range(N)] for i in range(N)]
    order, left = [0], set(range(1, N))
    while left:
        k = min(left, key=lambda j: dist[order[-1]][j])
        order.append(k)
        left.remove(k)

    def dl(o):
        return sum(dist[o[i]][o[(i + 1) % len(o)]] for i in range(len(o)))

    popr = True
    while popr:
        popr = False
        for i in range(1, N - 1):
            for j in range(i + 1, N):
                o = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                if dl(o) < dl(order):
                    order, popr = o, True
    pelna = [nodes[0]]
    for i in range(N):
        pelna += droga(order[i], order[(i + 1) % N])
    return order, nodes, pelna


def obraz(m, z, pelna, order, nodes, stops, plik, tytul, wejscie=None):
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415
    xs, ys = [p[0] for p in pelna], [p[1] for p in pelna]
    X0, X1, Y0, Y1 = min(xs) - 8, max(xs) + 8, min(ys) - 8, max(ys) + 8
    S = 11
    img = Image.new("RGB", ((X1 - X0 + 1) * S, (Y1 - Y0 + 1) * S), (0, 0, 0))
    d = ImageDraw.Draw(img)
    for y in range(Y0, Y1 + 1):
        for x in range(X0, X1 + 1):
            p = m.pole(x, y, z)
            if p is None or not p[0] & 1:
                continue
            rgb = _mapa._kolor_tibii(p[1])
            if p[0] & 4:
                rgb = tuple(v // 3 for v in rgb)
            elif p[0] & 2:
                rgb = (255, 220, 0)
            d.rectangle([(x - X0) * S, (y - Y0) * S, (x - X0) * S + S - 1, (y - Y0) * S + S - 1], fill=rgb)

    def c(x, y):
        return ((x - X0) * S + S // 2, (y - Y0) * S + S // 2)

    pts = [c(x, y) for x, y in pelna]
    d.line(pts, fill=(255, 255, 255), width=5)
    d.line(pts, fill=(235, 30, 30), width=3)
    F, Fs = ImageFont.load_default(size=16), ImageFont.load_default(size=13)
    for k, o in enumerate(order):
        x, y = c(*nodes[o])
        if o == 0:
            d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=(60, 220, 60), outline=(255, 255, 255), width=2)
            d.text((x + 13, y - 9), "START", fill=(150, 255, 150), font=F)
            continue
        d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=(255, 60, 200), outline=(255, 255, 255), width=2)
        t = str(k)
        d.text((x - d.textlength(t, font=F) / 2, y - 9), t, fill=(255, 255, 255), font=F)
        d.text((x + 13, y - 8), f"{stops[o - 1]['n']} szcz.", fill=(255, 200, 240), font=Fs)
    leg = [((235, 30, 30), f"{tytul}: petla {len(pelna)} pol (z{z})"), ((255, 60, 200), "przystanek = spawn(y) szczurow, numer = kolejnosc"),
           ((255, 220, 0), "schody / dziury / wejscia"), ((60, 220, 60), "start petli")]
    d.rectangle([4, 4, 430, 24 * len(leg) + 8], fill=(15, 15, 15), outline=(200, 200, 200))
    for i, (k, t) in enumerate(leg):
        d.rectangle([10, 10 + i * 24, 24, 24 + i * 24], fill=k)
        d.text((32, 10 + i * 24), t, fill=(240, 240, 240), font=Fs)
    img.save(plik)


def spawny_szczurow(z):
    dane = json.loads(SPAWNY.read_text())["potwory"]
    return [s for mo in dane if mo["nazwa"] == "rat" for s in mo.get("spawny", []) if s["z"] == z]


def wynik(nazwa, z, comp, stops, order, nodes, pelna):
    szcz = sum(t["n"] for t in stops)
    print(f"{nazwa}: składowa {len(comp)} pól, przystanków {len(stops)}, szczurów {szcz}, pętla {len(pelna)} pól, kolejność {order}")


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
        trasa_io.zapisz(f"{nazwa}_petla", [(x, y, z) for x, y in pelna])
        obraz(m, z, pelna, order, nodes, stops, OBRAZY / f"{nazwa}.png", tytul)
        (OBRAZY / f"{nazwa}.json").write_text(json.dumps({
            "start": [*nodes[0], z], "dlugosc_petli": len(pelna),
            "przystanki": [{"kolejnosc": k, "x": nodes[o][0], "y": nodes[o][1], "z": z,
                            **({} if o == 0 else {"szczurow": stops[o - 1]["n"], "spawnow": stops[o - 1]["spawny"]})}
                           for k, o in enumerate(order)]}, ensure_ascii=False, indent=1))
    trasa_io.zapisz("rook_raty_z8_dojscie", doj8, meta8)
    trasa_io.zapisz("rook_kanaly_z11_dojscie", doj11, meta11)
    print("zapisano trasy/ i dane_tibia/mapy/")


if __name__ == "__main__":
    main()
