#!/usr/bin/env python3
"""Wspólne klocki generatorów tras (SPEC_generator_spotow_1021.md, F0; 21.10): bez zmiany zachowania.
Do 21.10 te funkcje siedziały w generuj_trasy_rook.py (składowa, przystanki, pętla, obraz) i generuj_trasy_rook_raty2.py
(chodliwe, lądowanie, przed_przejściem), a strefa zakazana i wykrywanie zejść tylko w generuj_trasy_thais_pn.py. Generatory
importują stąd; generuj_trasy_rook / _raty2 dalej eksportują stare nazwy (reeksport), bo importują je inne skrypty.
Algorytmy, kolejność iteracji, rozstrzyganie remisów i format plików są BAJT W BAJT jak w oryginałach (testy/test_spot_lib_regresja.py,
zamrożone kopie w testy/dane_f0_baza/). Nic nie wysyła do gry; moduł nie jest uruchamiany, tylko importowany.

Klocki (m = mapa.Mapa(), z = numer piętra, pole = (x, y) albo (x, y, z), `ściana` = lista (x, y, z) pól wyłączonych):
  sasiedzi, skladowa           pola przechodnie piętra osiągalne od startu (bez schodów/dziur i bez ściany)
  przystanki, petla            spawny -> przystanki (scalone <= SCAL pól), pętla: najbliższy sąsiad + 2-opt po długości A*
  chodliwe, chodliwe_z         pole chodliwe w mapie (z flagą 2 / bez flagi 2)
  ladowanie, przed_przejsciem  pole lądowania pod przejściem i droga A* do pola obok przejścia
  strefa_zakazana              pola w promieniu `promien` (Chebyshev) od środków spawnów, na jednym piętrze
  zejscia                      pola przejść W DÓŁ na piętrze z (reguła kierunku: nic chodliwego 3x3 piętro wyżej)
  dojscie_do_petli             A* z lądowania do najbliższego punktu pętli, omijający strefę
  spawny                       spawny wskazanych potworów z potwory_pelne.json (opcjonalnie w prostokącie)
  obraz                        podgląd PNG pętli (opcjonalnie strefa zakazana na fiolet)
  zapis_spotu                  trasy/<nazwa>_petla (+ _dojscie), dane_tibia/mapy/<nazwa>.png i .json
  wynik                        wiersz podsumowania składowej
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import mapa as _mapa  # noqa: E402
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


def chodliwe(m, p):
    """Pole (x, y, z) widziane w mapie, bez ściany i bez flagi 2 (schody/dziury)."""
    f = m.flagi(p[0], p[1], p[2])
    return bool(f & _mapa.WIDZIANE and not f & (_mapa.SCIANA | _mapa.BEZ_DROGI))


def chodliwe_z(m, x, y, z):
    """Pole widziane w mapie i bez ściany; flaga 2 (schody/dziury) NIE przeszkadza (do wykrywania, co leży nad przejściem)."""
    f = m.flagi(x, y, z)
    return bool(f & _mapa.WIDZIANE and not f & _mapa.SCIANA)


def ladowanie(m, T, comp=None):
    """Pole lądowania na piętrze T[2]+1: chodliwe, najbliższe (T.x, T.y) potem (T.x, T.y+1); gdy `comp` podano, tylko z niej."""
    z = T[2] + 1
    kand = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            x, y = T[0] + dx, T[1] + dy
            if chodliwe(m, (x, y, z)) and (comp is None or (x, y) in comp):
                kand.append((x, y))
    if not kand:
        raise SystemExit(f"brak pola lądowania pod przejściem {T}")
    x, y = min(kand, key=lambda c: ((c[0] - T[0], c[1] - T[1]) != (0, 0), (c[0] - T[0], c[1] - T[1]) != (0, 1),
                                    max(abs(c[0] - T[0]), abs(c[1] - T[1])), c))
    return (x, y, z)


def przed_przejsciem(m, start, T, ściana=()):
    """(pole obok T, droga A* ze `start` (bez startu, z polem obok)) - najkrótsza po sąsiadach T na piętrze T[2]."""
    zle = {(p[0], p[1]) for p in ściana if p[2] == T[2]}
    best = None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            c = (T[0] + dx, T[1] + dy)
            if (dx or dy) and chodliwe(m, (c[0], c[1], T[2])) and c not in zle:
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


def strefa_zakazana(spawny_z, z, promien):
    """Zbiór (x, y, z): pola w promieniu `promien` (Chebyshev) od środka każdego spawnu z listy `spawny_z` (piętro z)."""
    out = set()
    for s in spawny_z:
        for dx in range(-promien, promien + 1):
            for dy in range(-promien, promien + 1):
                out.add((s["x"] + dx, s["y"] + dy, z))
    return out


KOLOR_ZMIANY_PIETRA = 210


def przeszkoda_na_podlodze(m, x, y, z):
    """21.10 (invincible w ogniu na (33115,31744,z8)): flaga 2 znaczy „autowalk nie idzie”, więc ma ją też OGIEŃ i inne
    przeszkody. Pole flagi 2 w kolorze podłogi wokół (nie 210) to przeszkoda — poza z7, gdzie tak wyglądają zasypane dziury
    (Thais (32347,32123), (32493,32259): kolor trawy 24, łopata). Zwraca True dla przeszkody (nie przejścia)."""
    kolor = m.pole(x, y, z)[1]
    if kolor == KOLOR_ZMIANY_PIETRA or z == 7:
        return False
    obok = [m.pole(x + a, y + b, z) for a in (-1, 0, 1) for b in (-1, 0, 1) if a or b]
    podloga = [p[1] for p in obok if p and p[0] & _mapa.WIDZIANE and not p[0] & (_mapa.SCIANA | _mapa.BEZ_DROGI)]
    return bool(podloga) and kolor == max(set(podloga), key=podloga.count)


def zejscia(m, z, obszar, comp, ogien=()):
    """Pola przejść W DÓŁ na piętrze z -> z+1 w prostokącie `obszar` (x0, y0, x1, y1): flaga 2 (BEZ_DROGI), nad nimi (3x3 na z-1)
    nic chodliwego (inaczej to schody W GÓRĘ), a w 3x3 na z+1 jest pole składowej `comp`. Kolejność: x rosnąco, y rosnąco.
    Odrzucone (21.10): przeszkoda w kolorze podłogi poza z7 (`przeszkoda_na_podlodze`, np. ogień) i pola z `ogien` ((x,y,z))."""
    x0, y0, x1, y1 = obszar
    ogien = set(ogien)
    out = []
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            if not m.flagi(x, y, z) & _mapa.WIDZIANE or not m.flagi(x, y, z) & _mapa.BEZ_DROGI:
                continue
            if (x, y, z) in ogien or przeszkoda_na_podlodze(m, x, y, z):
                continue
            otoczenie = [(x + a, y + b) for a in (-1, 0, 1) for b in (-1, 0, 1)]
            if any(chodliwe_z(m, a, b, z - 1) for a, b in otoczenie):
                continue
            if any(c in comp for c in otoczenie):
                out.append((x, y, z))
    return out


def dojscie_do_petli(m, L, pelna, zle):
    """Droga A* [(x,y)...] po piętrze L[2] z lądowania `L` do najbliższego (Chebyshev, pierwszy z listy) punktu `pelna`, omijająca
    strefę `zle` (zbiór (x,y,z); A* bota strefy nie zna). Puste [], gdy lądowanie jest już na pętli; None, gdy brak drogi."""
    cel = min(pelna, key=lambda q: max(abs(q[0] - L[0]), abs(q[1] - L[1])))
    d = [] if cel == L[:2] else m.droga(L, cel, zajete=sorted(zle), dlugosc=0, limit=400000)
    if d is None:
        return None
    return [(q[0], q[1]) for q in d]


def spawny(z, nazwy, obszar=None):
    """Spawny z potwory_pelne.json: potwory o nazwach z `nazwy` (krotka/lista) na piętrze z; opcjonalnie tylko w prostokącie
    `obszar` = (x1, x2, y1, y2) włącznie. Kolejność jak w pliku."""
    dane = json.loads(SPAWNY.read_text())["potwory"]
    out = [s for mo in dane if mo["nazwa"] in nazwy for s in mo.get("spawny", []) if s["z"] == z]
    if obszar is not None:
        x1, x2, y1, y2 = obszar
        out = [s for s in out if x1 <= s["x"] <= x2 and y1 <= s["y"] <= y2]
    return out


def obraz(m, z, pelna, order, nodes, stops, plik, tytul, wejscie=None, jedn="szcz.", opis_przyst="spawn(y) szczurow", strefa=None):
    """Podgląd PNG: trasa (czerwona), przystanki (różowe, numer = kolejność), start (zielony); `strefa` (zbiór (x,y,z)) na wierzchu fioletem."""
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
        d.text((x + 13, y - 8), f"{stops[o - 1]['n']} {jedn}", fill=(255, 200, 240), font=Fs)
    leg = [((235, 30, 30), f"{tytul}: petla {len(pelna)} pol (z{z})"), ((255, 60, 200), f"przystanek = {opis_przyst}, numer = kolejnosc"),
           ((255, 220, 0), "schody / dziury / wejscia"), ((60, 220, 60), "start petli")]
    d.rectangle([4, 4, 430, 24 * len(leg) + 8], fill=(15, 15, 15), outline=(200, 200, 200))
    for i, (k, t) in enumerate(leg):
        d.rectangle([10, 10 + i * 24, 24, 24 + i * 24], fill=k)
        d.text((32, 10 + i * 24), t, fill=(240, 240, 240), font=Fs)
    if strefa:
        # strefa zakazana na wierzchu (fiolet), w tym samym układzie co reszta obrazu (jak thais_pn do 21.10: zapis, odczyt, nałożenie)
        nak = Image.new("RGBA", img.size, (0, 0, 0, 0))
        dn = ImageDraw.Draw(nak)
        for (x, y, _) in strefa:
            if m.flagi(x, y, z) & _mapa.WIDZIANE and not m.flagi(x, y, z) & _mapa.SCIANA:
                dn.rectangle([(x - X0) * S, (y - Y0) * S, (x - X0) * S + S - 1, (y - Y0) * S + S - 1], fill=(150, 40, 220, 120))
        img = Image.alpha_composite(img.convert("RGBA"), nak).convert("RGB")
    img.save(plik)


def zapis_spotu(m, nazwa, z, pelna, order, nodes, stops, tytul, *, klucz="potworow", ekstra=None, doj=None, meta=(), strefa=None,
                jedn="szcz.", opis_przyst="spawn(y) szczurow"):
    """Zapisuje trasy/<nazwa>_petla (+ <nazwa>_dojscie z meta, gdy `doj`), dane_tibia/mapy/<nazwa>.png i <nazwa>.json.
    `klucz` = nazwa liczby potworów przy przystanku w .json ("szczurow" / "potworow"), `ekstra` = dodatkowe pola .json (po dlugosc_petli)."""
    trasa_io.zapisz(f"{nazwa}_petla", [(x, y, z) for x, y in pelna])
    obraz(m, z, pelna, order, nodes, stops, OBRAZY / f"{nazwa}.png", tytul, jedn=jedn, opis_przyst=opis_przyst, strefa=strefa)
    (OBRAZY / f"{nazwa}.json").write_text(json.dumps({
        "start": [*nodes[0], z], "dlugosc_petli": len(pelna), **(ekstra or {}),
        "przystanki": [{"kolejnosc": k, "x": nodes[o][0], "y": nodes[o][1], "z": z,
                        **({} if o == 0 else {klucz: stops[o - 1]["n"], "spawnow": stops[o - 1]["spawny"]})}
                       for k, o in enumerate(order)]}, ensure_ascii=False, indent=1))
    if doj is not None:
        trasa_io.zapisz(f"{nazwa}_dojscie", doj, meta)


def wynik(nazwa, z, comp, stops, order, nodes, pelna):
    szcz = sum(t["n"] for t in stops)
    print(f"{nazwa}: składowa {len(comp)} pól, przystanków {len(stops)}, szczurów {szcz}, pętla {len(pelna)} pól, kolejność {order}")
