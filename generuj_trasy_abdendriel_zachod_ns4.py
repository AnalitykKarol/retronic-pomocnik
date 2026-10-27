#!/usr/bin/env python3
"""Ab'Dendriel zachód z9: PODGLĄD południowej pętli v4 z WYMUSZONĄ kolejnością przystanków (27.10, Karol: „jedna czysta pętla”, bez wracania tym samym korytarzem).
Kolejność wg numerów z mapy v3 (pole `kolejnosc` w dane_tibia/mapy/abdendriel_zachod_z9_poludnie_v3.json): start -> 3 -> 1 -> 2 -> 4 -> 6 -> 7 -> 8 -> 5 -> start
  3 = (32427,31696) 5 pot., 1 = (32398,31707) 2, 2 = (32406,31727) 3, 4 = (32438,31729) 3, 6 = (32499,31731) 3, 7 = (32531,31691) 2, 8 = (32505,31713) 4, 5 = (32481,31720) 2.
Zamiast Held-Karp: ścieżki między KOLEJNYMI przystankami = najkrótsze (A*, ściany jak w ns/ns2/ns3). Jeśli odcinek nie ma ścieżki, generator kończy się SystemExit z nazwą odcinka (nic nie obchodzi).
Polityka jak v3 z jednym rozszerzeniem: bufor ognia 0 (samo pole ścianą, sąsiedzi wolni) dla DWÓCH pól: (32437,31695,z9) i (32408,31726,z9); wszystkie inne pola ognia i dziury: bufor 1.
Pisze WYŁĄCZNIE: trasy/abdendriel_zachod_z9_poludnie_v4_petla.json, dane_tibia/mapy/abdendriel_zachod_z9_poludnie_v4.{png,json} (BEZ wpisu w mapy.json). PNG: numer przystanku = numer z mapy v3,
mały numer obok = kolejność odwiedzin, strzałki kierunku trasy, pola ognia pomarańczowe (wyjątki z obwódką).

  python3 -I generuj_trasy_abdendriel_zachod_ns4.py [--zapisz]   bez --zapisz tylko liczy: odcinki, kształt, wspólne z północną v2, sąsiedztwo pól ognia
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generuj_trasy_abdendriel_zachod as Z  # noqa: E402
import generuj_trasy_abdendriel_zachod_ns as NS  # noqa: E402
import generuj_trasy_abdendriel_zachod_ns2 as V2  # noqa: E402
import generuj_trasy_abdendriel_zachod_ns3 as V3  # noqa: E402
import mapa as _mapa  # noqa: E402
import spot_lib  # noqa: E402
import trasa_io  # noqa: E402

NAZWA4 = "abdendriel_zachod_z9_poludnie_v4"
WYJATKI4 = {(32437, 31695, 9): 0, (32408, 31726, 9): 0}
NUMERY_V3 = {1: (32398, 31707), 2: (32406, 31727), 3: (32427, 31696), 4: (32438, 31729), 5: (32481, 31720), 6: (32499, 31731), 7: (32531, 31691), 8: (32505, 31713)}
KOLEJNOSC_V3 = (3, 1, 2, 4, 6, 7, 8, 5)


def sprawdz_numery_v3():
    """Numery z pliku mapy v3 muszą się zgadzać ze stałą (inaczej SystemExit: nie zgadujemy, o który przystanek chodzi)."""
    j = json.loads((ROOT / "dane_tibia" / "mapy" / "abdendriel_zachod_z9_poludnie_v3.json").read_text())
    f = {t["kolejnosc"]: (t["x"], t["y"]) for t in j["przystanki"] if "potworow" in t}
    if f != NUMERY_V3:
        raise SystemExit(f"numery przystanków w mapie v3 {f} != NUMERY_V3 {NUMERY_V3}")


def zbuduj_v4(m=None):
    m = m or _mapa.Mapa()
    sprawdz_numery_v3()
    stare = dict(V3.BUFOR_WYJATKI_OGIEN)
    V3.BUFOR_WYJATKI_OGIEN.clear()
    V3.BUFOR_WYJATKI_OGIEN.update(WYJATKI4)
    try:
        L9, comp9, sciana9, zle9, wszystkie, wyj = V3.przygotuj3(m)
    finally:
        V3.BUFOR_WYJATKI_OGIEN.clear()
        V3.BUFOR_WYJATKI_OGIEN.update(stare)
    por = {t["pt"]: t for t in wszystkie}
    brak = [NUMERY_V3[k] for k in KOLEJNOSC_V3 if NUMERY_V3[k] not in por]
    if brak:
        raise SystemExit(f"przystanki poza składową (ściany/bufory): {brak}")
    st = [por[NUMERY_V3[k]] for k in KOLEJNOSC_V3]
    nodes = [tuple(L9[:2])] + [t["pt"] for t in st]
    cele = [nodes[0]] + [t["pt"] for t in st] + [nodes[0]]
    nazwy = ["start"] + [str(k) for k in KOLEJNOSC_V3] + ["start"]
    pelna, odcinki = [nodes[0]], []
    for i in range(len(cele) - 1):
        d = m.droga((cele[i][0], cele[i][1], 9), cele[i + 1], zajete=sciana9, dlugosc=0, limit=400000)
        if d is None:
            raise SystemExit(f"BRAK ŚCIEŻKI na odcinku {nazwy[i]} {cele[i]} -> {nazwy[i + 1]} {cele[i + 1]} (ściany: ogień/dziury/przeszkody/strefy jak w v3 + wyjątki {sorted(WYJATKI4)})")
        seg = [(q[0], q[1]) for q in d]
        nowe = sum(1 for q in seg if q not in set(pelna))
        odcinki.append((nazwy[i], nazwy[i + 1], len(seg), nowe))
        pelna += seg
    dz = Z.dziury_nauczone() | Z.dziury_omijaj()
    bad = [p for p in pelna if (p[0], p[1], 9) in zle9 or (p[0], p[1], 9) in dz]
    if bad:
        raise SystemExit(f"{NAZWA4}: pętla wchodzi w ogień/przeszkodę/dziurę/strefę: {bad[:5]}")
    gardla = Z.waskie_gardla(m, comp9, zle9, pelna, 9)
    return {"L": L9, "comp": comp9, "st": st, "nodes": nodes, "pelna": pelna, "odcinki": odcinki, "gardla": gardla, "zle": zle9, "sciana": sciana9, "wyj": wyj}


def odcinki_tam_z_powrotem(pelna):
    """Maksymalne ciągi kolejnych krawędzi pętli, których krawędź odwrotna też jest gdzieś przebyta: [(od, do, liczba krawędzi, indeks pierwszej krawędzi)]."""
    p = [(a[0], a[1]) for a in pelna]
    kr = set(zip(p, p[1:]))
    dwa = [(b, a) in kr for a, b in zip(p, p[1:])]
    wyn, i = [], 0
    while i < len(dwa):
        if dwa[i]:
            j = i
            while j + 1 < len(dwa) and dwa[j + 1]:
                j += 1
            wyn.append((p[i], p[j + 1], j - i + 1, i))
            i = j + 1
        else:
            i += 1
    return wyn


def korytarze_tam_z_powrotem(pelna):
    """Korytarze przebyte tam i z powrotem: spójne składowe NIESKIEROWANYCH krawędzi użytych w obu kierunkach. Zwraca (liczba krawędzi nieskierowanych w sumie,
    lista [(krawędzi, końce stopnia 1 (ślepe końce lub styk z częścią jednokierunkową) )])."""
    p = [(a[0], a[1]) for a in pelna]
    kr = set(zip(p, p[1:]))
    dwa = {frozenset((a, b)) for a, b in kr if (b, a) in kr}
    sas = {}
    for e in dwa:
        a, b = tuple(e)
        sas.setdefault(a, set()).add(b)
        sas.setdefault(b, set()).add(a)
    widz, wyn = set(), []
    for c in sorted(sas):
        if c in widz:
            continue
        st, comp = [c], {c}
        while st:
            u = st.pop()
            for v in sas[u]:
                if v not in comp:
                    comp.add(v)
                    st.append(v)
        widz |= comp
        kon = sorted(q for q in comp if len(sas[q]) == 1)
        wyn.append((sum(len(sas[q]) for q in comp) // 2, kon))
    return len(dwa), sorted(wyn, reverse=True)


def ogien_przy_trasie(pelna, ogien):
    """{pole ognia: [unikalne pola trasy w Chebyshev <= 1]} (tylko pola ognia z sąsiadami na trasie)."""
    P = {(p[0], p[1]) for p in pelna}
    wyn = {}
    for f in sorted(ogien):
        if f[2] != 9:
            continue
        bl = sorted(q for q in P if V2.cheb(q, f) <= 1)
        if bl:
            wyn[(f[0], f[1])] = bl
    return wyn


def rysuj(m, o, plik):
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415
    pelna, nodes, st = o["pelna"], o["nodes"], o["st"]
    xs, ys = [p[0] for p in pelna], [p[1] for p in pelna]
    X0, X1, Y0, Y1 = min(xs) - 8, max(xs) + 8, min(ys) - 8, max(ys) + 8
    S = 11
    img = Image.new("RGB", ((X1 - X0 + 1) * S, (Y1 - Y0 + 1) * S), (0, 0, 0))
    d = ImageDraw.Draw(img)
    for y in range(Y0, Y1 + 1):
        for x in range(X0, X1 + 1):
            p = m.pole(x, y, 9)
            if p is None or not p[0] & 1:
                continue
            rgb = _mapa._kolor_tibii(p[1])
            if p[0] & 4:
                rgb = tuple(v // 3 for v in rgb)
            elif p[0] & 2:
                rgb = (255, 220, 0)
            d.rectangle([(x - X0) * S, (y - Y0) * S, (x - X0) * S + S - 1, (y - Y0) * S + S - 1], fill=rgb)
    for (x, y, z) in Z.ogien_surowy():
        if z == 9 and X0 <= x <= X1 and Y0 <= y <= Y1:
            wyj = (x, y, 9) in WYJATKI4
            d.rectangle([(x - X0) * S, (y - Y0) * S, (x - X0) * S + S - 1, (y - Y0) * S + S - 1], fill=(255, 120, 0), outline=(255, 255, 255) if wyj else None)

    def c(x, y):
        return ((x - X0) * S + S // 2, (y - Y0) * S + S // 2)
    pts = [c(x, y) for x, y in pelna]
    d.line(pts, fill=(255, 255, 255), width=5)
    d.line(pts, fill=(235, 30, 30), width=3)
    for i in range(12, len(pts) - 2, 24):                      # strzałki kierunku co 24 pola
        a, b = pts[i - 2], pts[i + 2]
        if a == b:
            continue
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        cx, cy = pts[i]
        tri = [(cx + 9 * math.cos(ang), cy + 9 * math.sin(ang)), (cx + 6 * math.cos(ang + 2.5), cy + 6 * math.sin(ang + 2.5)), (cx + 6 * math.cos(ang - 2.5), cy + 6 * math.sin(ang - 2.5))]
        d.polygon(tri, fill=(30, 200, 255), outline=(255, 255, 255))
    F, Fs = ImageFont.load_default(size=16), ImageFont.load_default(size=13)
    x, y = c(*nodes[0])
    d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=(60, 220, 60), outline=(255, 255, 255), width=2)
    d.text((x + 13, y - 9), "START", fill=(150, 255, 150), font=F)
    for k, (num, t) in enumerate(zip(KOLEJNOSC_V3, st), 1):
        x, y = c(*t["pt"])
        d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=(255, 60, 200), outline=(255, 255, 255), width=2)
        d.text((x - d.textlength(str(num), font=F) / 2, y - 9), str(num), fill=(255, 255, 255), font=F)
        d.text((x + 13, y - 8), f"#{k} {t['n']} potw.", fill=(255, 200, 240), font=Fs)
    leg = [((235, 30, 30), f"{NAZWA4} (PODGLAD): petla {len(pelna)} pol (z9)"), ((255, 60, 200), "numer = numer przystanku z mapy v3; #k = kolejnosc odwiedzin"),
           ((30, 200, 255), "strzalka = kierunek trasy"), ((255, 120, 0), "pole ognia (z obwodka = wyjatek: bufor 0)"), ((60, 220, 60), "start petli")]
    d.rectangle([4, 4, 470, 24 * len(leg) + 8], fill=(15, 15, 15), outline=(200, 200, 200))
    for i, (k, t) in enumerate(leg):
        d.rectangle([10, 10 + i * 24, 24, 24 + i * 24], fill=k)
        d.text((32, 10 + i * 24), t, fill=(240, 240, 240), font=Fs)
    img.save(plik)


def zapisz(m, o):
    trasa_io.zapisz(f"{NAZWA4}_petla", [(x, y, 9) for x, y in o["pelna"]])
    plik = ROOT / "dane_tibia" / "mapy"
    rysuj(m, o, plik / f"{NAZWA4}.png")
    (plik / f"{NAZWA4}.json").write_text(json.dumps({
        "start": [*o["nodes"][0], 9], "dlugosc_petli": len(o["pelna"]), "uwaga": "PODGLAD v4: wymuszona kolejnosc wg numerow v3 (numer_v3), kolejnosc = kolejnosc odwiedzin",
        "przystanki": [{"kolejnosc": 0, "x": o["nodes"][0][0], "y": o["nodes"][0][1], "z": 9}] +
                      [{"kolejnosc": k, "numer_v3": num, "x": t["pt"][0], "y": t["pt"][1], "z": 9, "potworow": t["n"], "spawnow": t["spawny"]}
                       for k, (num, t) in enumerate(zip(KOLEJNOSC_V3, o["st"]), 1)]}, ensure_ascii=False, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    ap.add_argument("--kolejnosc", default="", help="TYLKO informacyjnie: inna kolejność numerów v3, np. 3,1,2,4,8,7,6,5 (nie łączy się z --zapisz)")
    a = ap.parse_args(argv)
    global KOLEJNOSC_V3
    if a.kolejnosc:
        if a.zapisz:
            raise SystemExit("--kolejnosc jest tylko informacyjne: nie łączy się z --zapisz")
        KOLEJNOSC_V3 = tuple(int(v) for v in a.kolejnosc.split(","))
        print(f"INFO: kolejność zmieniona na {KOLEJNOSC_V3} (TYLKO informacyjnie)")
    print(f"pliki ognia/dziur (sha1, 12 znaków): {V2.sha1_ognia()}")
    m = _mapa.Mapa()
    o = zbuduj_v4(m)
    pel = o["pelna"]
    n = sum(t["n"] for t in o["st"])
    print(f"v4: kolejność {' -> '.join(['start'] + [str(k) for k in KOLEJNOSC_V3] + ['start'])}; wyjątki ognia (bufor 0) {sorted(o['wyj'])}")
    for od, do, dl, nowe in o["odcinki"]:
        print(f"  odcinek {od} -> {do}: {dl} pól, w tym {nowe} nowych")
    print(f"v4: pętla {len(pel)} pkt ({len(pel) - 1} pól), przystanków {len(o['st'])}, potworów {n}, {len(pel) / n:.1f} pola/potwora, wąskie gardła {len(o['gardla'])}: {o['gardla']}")
    tz = odcinki_tam_z_powrotem(pel)
    krawedzie = sum(x[2] for x in tz)
    nsk, kor = korytarze_tam_z_powrotem(pel)
    print(f"v4: przejazdy krawędzi w OBU kierunkach (kierunkowe): {krawedzie} z {len(pel) - 1} ({100 * krawedzie / (len(pel) - 1):.0f}%) = {nsk} krawędzi nieskierowanych przebytych dwa razy")
    for k, kon in kor:
        print(f"  korytarz tam-i-z-powrotem: {k} krawędzi, końce (stopień 1): {kon}")
    lad = [i for i in range(1, len(pel) - 1) if V2.cheb(pel[i], NS.LAD9) <= V2.LAD_PROMIEN]
    runy, i = [], 0
    while i < len(lad):
        j = i
        while j + 1 < len(lad) and lad[j + 1] == lad[j] + 1:
            j += 1
        runy.append((lad[i], lad[j], pel[lad[i]], pel[lad[j]]))
        i = j + 1
    print(f"v4: przejścia przez strefę lądowania (Chebyshev <= {V2.LAD_PROMIEN} od (32480,31721)) w ŚRODKU pętli (indeks od, do, pole od, pole do): {runy}; pole liny odwiedzone w środku {sum(1 for q in pel[1:-1] if q == tuple(NS.LAD9[:2]))} razy")
    sn = V3.ksztalt(pel, (32437, 31695, 9))
    print(f"v4: pola odwiedzone >= 2 razy {sn['pola_wielokrotne']}")
    pn = [tuple(p) for p in json.loads((ROOT / "trasy" / f"{NS.NAZWA}_polnoc{V2.SUFIKS}_petla.json").read_text())]
    pom = V2.pomiar(pn, pel)
    V2.drukuj_pomiar("v4 vs północna v2 (plik)", pom)
    ok, opis = V2.kryterium(pom)
    print(("KRYTERIUM ROZŁĄCZNOŚCI (v4 z północną v2) SPEŁNIONE: " if ok else "KRYTERIUM NIESPEŁNIONE: ") + opis)
    og = ogien_przy_trasie(pel, Z.ogien_surowy())
    print(f"v4: pola ognia z punktami trasy w Chebyshev <= 1: {len(og)}")
    for f, bl in og.items():
        wg = [q for q in bl if q in set(o['gardla'])]
        ile = sum(1 for p in pel if (p[0], p[1]) in set(bl))
        print(f"  ogień {f}{' (WYJĄTEK bufor 0)' if (f[0], f[1], 9) in WYJATKI4 else ''}: pola trasy {bl}, punktów trasy {ile}, z nich wąskie gardło (pas 1 pola przez zagrożenie): {wg}")
    comp = set(o["comp"])
    for f in og:
        w3 = sorted(q for q in comp if V2.cheb(q, f) <= 1)
        bez = {q for q in comp if V2.cheb(q, f) <= 1}
        zost, st_ = {tuple(o["L"][:2])}, [tuple(o["L"][:2])]
        while st_:
            u = st_.pop()
            for nb in spot_lib.sasiedzi(*u):
                if nb in comp and nb not in bez and nb not in zost:
                    zost.add(nb)
                    st_.append(nb)
        odciete = [t["pt"] for t in o["st"] if t["pt"] not in zost]
        w5 = sorted(q for q in comp if V2.cheb(q, f) == 2)
        print(f"  ogień {f}: wolne pola składowej w Chebyshev <= 1: {w3}; w Chebyshev == 2: {len(w5)} pól; bez pól w Chebyshev <= 1 (czyli jak bufor 1) odcięte przystanki: {odciete}")
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    if not ok:
        raise SystemExit("kryterium rozłączności niespełnione: nic nie zapisano")
    zapisz(m, o)
    print("zapisano trasy/abdendriel_zachod_z9_poludnie_v4_petla.json i dane_tibia/mapy/abdendriel_zachod_z9_poludnie_v4.{png,json} (BEZ wpisu mapy.json)")


if __name__ == "__main__":
    main()
