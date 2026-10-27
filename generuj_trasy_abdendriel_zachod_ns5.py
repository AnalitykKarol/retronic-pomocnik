#!/usr/bin/env python3
"""Ab'Dendriel zachód z9: PODGLĄD południowej pętli v5 = v4 + otwarty korytarz do pokoju 6 (27.10; Karol: pola obok/nad/pod korytarzem nie mają znaczenia, ważne, żeby trasa NIE weszła
w dziurę (przejście między poziomami)). Kolejność wymuszona jak v4: start -> 3 -> 1 -> 2 -> 4 -> 6 -> 7 -> 8 -> 5 -> start (numery z mapy v3), A* między kolejnymi przystankami.
Powód: w v4 odcinek 4->6 szedł naokoło (242 pola), bo korytarz (32494..32497,31733,z9) leży w buforze 1 dziury (32496,31732,9) i pól ognia (32495..32496,31734..31735).
Zasada v5: bufor 0 (samo pole = ściana, sąsiedzi wolni) dla: dziury (32496,31732,9) (mechanizm Z.BUFOR_WYJATKI9), pól ognia (32495,31734), (32496,31734), (32495,31735), (32496,31735)
oraz dwóch wyjątków z v4: (32437,31695,9), (32408,31726,9). Same pola dziury i ognia zostają ŚCIANĄ (trasa na nie nie wchodzi: twarda asercja przy zapisie i w teście).
Wszystkie inne pola ognia, dziury i przeszkody: bufor 1 jak dotąd.
Pisze WYŁĄCZNIE: trasy/abdendriel_zachod_z9_poludnie_v5_petla.json, dane_tibia/mapy/abdendriel_zachod_z9_poludnie_v5.{png,json} (BEZ wpisu mapy.json). Importuje ns4 (nie zmienia go).

  python3 -I generuj_trasy_abdendriel_zachod_ns5.py [--zapisz]   bez --zapisz tylko liczy
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
import generuj_trasy_abdendriel_zachod_ns4 as V4  # noqa: E402
import mapa as _mapa  # noqa: E402
import spot_lib  # noqa: E402
import trasa_io  # noqa: E402

NAZWA5 = "abdendriel_zachod_z9_poludnie_v5"
WYJATKI_OGIEN5 = {(32437, 31695, 9): 0, (32408, 31726, 9): 0, (32495, 31734, 9): 0, (32496, 31734, 9): 0, (32495, 31735, 9): 0, (32496, 31735, 9): 0}
WYJATKI_DZIURY5 = {(32496, 31732, 9)}               # dziura z listy omijaj: samo pole ścianą, bez bufora
# ODCHYLENIE od polecenia (27.10): samo (32496,31732) + 6 pól ognia NIE otwiera korytarza (4->6 dalej 242 pola, identycznie jak v4). Droga 4->6 po y=31732 (x 32494..32498) leży
# w buforze 1 trzech przeszkód z pełnego skanu (flaga 2 w kolorze podłogi, pola niechodliwe jak dziura: (32495,31731), (32497,31731), (32496,31730)), które razem z dziurą tworzą krzyż.
# Zasada Karola (liczy się tylko, by NIE wejść w dziurę) rozszerzona na te 3 pola: bufor 0 (same pola zostają ścianą). Do oceny przez prowadzącego; `--tylko-wskazane` = bez nich.
WYJATKI_PRZESZKODY5 = {(32495, 31731, 9), (32497, 31731, 9), (32496, 31730, 9)}
KOLEJNOSC_V3 = V4.KOLEJNOSC_V3


def zbuduj_v5(m=None, tylko_wskazane=False):
    """Jak V4.zbuduj_v4 (kolejność wymuszona, A* między przystankami), ale z wyjątkami v5 (ogień: V3.BUFOR_WYJATKI_OGIEN; dziura i przeszkody flaga 2: Z.BUFOR_WYJATKI9).
    Przystanek 6: gdy wyjątki przesuwają przyciągnięcie spawnu do sąsiedniego pola (32498,31731), zostaje węzłem pole z mapy v3 (32499,31731) (ten sam spawn, jest w składowej).
    `tylko_wskazane`: TYLKO informacyjnie, bez DODATKOWYCH wyjątków przeszkód (WYJATKI_PRZESZKODY5). Po wyjściu stan modułów przywrócony."""
    m = m or _mapa.Mapa()
    V4.sprawdz_numery_v3()
    stare_og, stare9 = dict(V3.BUFOR_WYJATKI_OGIEN), set(Z.BUFOR_WYJATKI9)
    V3.BUFOR_WYJATKI_OGIEN.clear()
    V3.BUFOR_WYJATKI_OGIEN.update(WYJATKI_OGIEN5)
    Z.BUFOR_WYJATKI9.update(WYJATKI_DZIURY5 | (set() if tylko_wskazane else WYJATKI_PRZESZKODY5))
    try:
        L9, comp9, sciana9, zle9, wszystkie, wyj = V3.przygotuj3(m)
    finally:
        V3.BUFOR_WYJATKI_OGIEN.clear()
        V3.BUFOR_WYJATKI_OGIEN.update(stare_og)
        Z.BUFOR_WYJATKI9.clear()
        Z.BUFOR_WYJATKI9.update(stare9)
    por = {t["pt"]: t for t in wszystkie}
    st = []
    for k in KOLEJNOSC_V3:
        pt = V4.NUMERY_V3[k]
        if pt in por:
            st.append(por[pt])
            continue
        bl = [t for t in wszystkie if V2.cheb(t["pt"], pt) <= 1 and pt in comp9]
        if len(bl) != 1:
            raise SystemExit(f"przystanek {k} {pt} poza składową albo niejednoznaczny po przyciągnięciu: {[t['pt'] for t in bl]}")
        print(f"UWAGA: przystanek {k}: przyciągnięcie spawnu przesunęło się z {pt} na {bl[0]['pt']}; węzłem zostaje pole z mapy v3 {pt} (jest w składowej)")
        st.append(dict(bl[0], pt=pt))
    nodes = [tuple(L9[:2])] + [t["pt"] for t in st]
    cele = [nodes[0]] + [t["pt"] for t in st] + [nodes[0]]
    nazwy = ["start"] + [str(k) for k in KOLEJNOSC_V3] + ["start"]
    pelna, odcinki = [nodes[0]], []
    for i in range(len(cele) - 1):
        d = m.droga((cele[i][0], cele[i][1], 9), cele[i + 1], zajete=sciana9, dlugosc=0, limit=400000)
        if d is None:
            raise SystemExit(f"BRAK ŚCIEŻKI na odcinku {nazwy[i]} {cele[i]} -> {nazwy[i + 1]} {cele[i + 1]}")
        seg = [(q[0], q[1]) for q in d]
        odcinki.append((nazwy[i], nazwy[i + 1], len(seg), sum(1 for q in seg if q not in set(pelna))))
        pelna += seg
    zakaz = Z.ogien_surowy() | Z.dziury_omijaj() | Z.dziury_nauczone()
    na_polach = [p for p in pelna if (p[0], p[1], 9) in zakaz]
    if na_polach:
        raise SystemExit(f"{NAZWA5}: trasa wchodzi NA pole dziury/ognia: {na_polach[:5]}")
    gardla = Z.waskie_gardla(m, comp9, zle9, pelna, 9)
    return {"L": L9, "comp": comp9, "st": st, "nodes": nodes, "pelna": pelna, "odcinki": odcinki, "gardla": gardla, "zle": zle9, "sciana": sciana9, "wyj": wyj}


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
            d.rectangle([(x - X0) * S, (y - Y0) * S, (x - X0) * S + S - 1, (y - Y0) * S + S - 1], fill=(255, 120, 0), outline=(255, 255, 255) if (x, y, 9) in WYJATKI_OGIEN5 else None)
    for (x, y, z) in Z.dziury_omijaj() | Z.dziury_nauczone():
        if z == 9 and X0 <= x <= X1 and Y0 <= y <= Y1:
            d.rectangle([(x - X0) * S, (y - Y0) * S, (x - X0) * S + S - 1, (y - Y0) * S + S - 1], fill=(120, 60, 255), outline=(255, 255, 255) if (x, y, 9) in WYJATKI_DZIURY5 else None)

    def c(x, y):
        return ((x - X0) * S + S // 2, (y - Y0) * S + S // 2)
    pts = [c(x, y) for x, y in pelna]
    d.line(pts, fill=(255, 255, 255), width=5)
    d.line(pts, fill=(235, 30, 30), width=3)
    for i in range(12, len(pts) - 2, 24):
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
    leg = [((235, 30, 30), f"{NAZWA5} (PODGLAD): petla {len(pelna)} pol (z9)"), ((255, 60, 200), "numer = numer przystanku z mapy v3; #k = kolejnosc odwiedzin"),
           ((30, 200, 255), "strzalka = kierunek trasy"), ((255, 120, 0), "pole ognia (z obwodka = wyjatek: bufor 0)"),
           ((120, 60, 255), "dziura (z obwodka = wyjatek: bufor 0)"), ((60, 220, 60), "start petli")]
    d.rectangle([4, 4, 470, 24 * len(leg) + 8], fill=(15, 15, 15), outline=(200, 200, 200))
    for i, (k, t) in enumerate(leg):
        d.rectangle([10, 10 + i * 24, 24, 24 + i * 24], fill=k)
        d.text((32, 10 + i * 24), t, fill=(240, 240, 240), font=Fs)
    img.save(plik)


def zapisz(m, o):
    trasa_io.zapisz(f"{NAZWA5}_petla", [(x, y, 9) for x, y in o["pelna"]])
    plik = ROOT / "dane_tibia" / "mapy"
    rysuj(m, o, plik / f"{NAZWA5}.png")
    (plik / f"{NAZWA5}.json").write_text(json.dumps({
        "start": [*o["nodes"][0], 9], "dlugosc_petli": len(o["pelna"]), "uwaga": "PODGLAD v5: wymuszona kolejnosc wg numerow v3 (numer_v3), kolejnosc = kolejnosc odwiedzin; bufor 0 dla dziury (32496,31732) i 6 pol ognia",
        "przystanki": [{"kolejnosc": 0, "x": o["nodes"][0][0], "y": o["nodes"][0][1], "z": 9}] +
                      [{"kolejnosc": k, "numer_v3": num, "x": t["pt"][0], "y": t["pt"][1], "z": 9, "potworow": t["n"], "spawnow": t["spawny"]}
                       for k, (num, t) in enumerate(zip(KOLEJNOSC_V3, o["st"]), 1)]}, ensure_ascii=False, indent=1))


def _odcinek_indeksy(o):
    ofs = [0]
    for _od, _do, dl, _n in o["odcinki"]:
        ofs.append(ofs[-1] + dl)
    return ofs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    ap.add_argument("--tylko-wskazane", action="store_true", help="TYLKO informacyjnie: bez dodatkowych wyjątków przeszkód (WYJATKI_PRZESZKODY5); nie łączy się z --zapisz")
    a = ap.parse_args(argv)
    if a.tylko_wskazane and a.zapisz:
        raise SystemExit("--tylko-wskazane jest tylko informacyjne: nie łączy się z --zapisz")
    print(f"pliki ognia/dziur (sha1, 12 znaków): {V2.sha1_ognia()}")
    m = _mapa.Mapa()
    o = zbuduj_v5(m, a.tylko_wskazane)
    pel = o["pelna"]
    n = sum(t["n"] for t in o["st"])
    print(f"v5: kolejność start -> {' -> '.join(str(k) for k in KOLEJNOSC_V3)} -> start; wyjątki ognia (bufor 0) {sorted(WYJATKI_OGIEN5)}; wyjątki dziur (bufor 0) {sorted(WYJATKI_DZIURY5)}; wyjątki przeszkód flaga 2 (bufor 0){' [WYŁĄCZONE --tylko-wskazane]' if a.tylko_wskazane else ''} {sorted(WYJATKI_PRZESZKODY5)}")
    for od, do, dl, nowe in o["odcinki"]:
        print(f"  odcinek {od} -> {do}: {dl} pól, w tym {nowe} nowych")
    print(f"v5: pętla {len(pel)} pkt ({len(pel) - 1} pól), przystanków {len(o['st'])}, potworów {n}, {len(pel) / n:.1f} pola/potwora, wąskie gardła {len(o['gardla'])}: {o['gardla']}")
    tz = V4.odcinki_tam_z_powrotem(pel)
    krawedzie = sum(x[2] for x in tz)
    nsk, kor = V4.korytarze_tam_z_powrotem(pel)
    print(f"v5: przejazdy krawędzi w OBU kierunkach (kierunkowe): {krawedzie} z {len(pel) - 1} ({100 * krawedzie / (len(pel) - 1):.0f}%) = {nsk} krawędzi nieskierowanych przebytych dwa razy")
    for k, kon in kor:
        print(f"  korytarz tam-i-z-powrotem: {k} krawędzi, końce (stopień 1): {kon}")
    ofs = _odcinek_indeksy(o)
    P2 = [(q[0], q[1]) for q in pel]
    legi = {f"{od}->{do}": P2[ofs[k]:ofs[k + 1] + 1] for k, (od, do, _dl, _n) in enumerate(o["odcinki"])}
    for a_, b_ in (("4->6", "6->7"), ("6->7", "7->8"), ("7->8", "8->5"), ("6->7", "8->5")):
        wsp = set(legi[a_]) & set(legi[b_])
        print(f"  wspólne pola odcinków {a_} i {b_}: {len(wsp)} z {len(set(legi[b_]))} pól odcinka {b_}")
    lad = [i for i in range(1, len(pel) - 1) if V2.cheb(pel[i], NS.LAD9) <= V2.LAD_PROMIEN]
    runy, i = [], 0
    while i < len(lad):
        j = i
        while j + 1 < len(lad) and lad[j + 1] == lad[j] + 1:
            j += 1
        runy.append((lad[i], lad[j], pel[lad[i]], pel[lad[j]]))
        i = j + 1
    print(f"v5: przejścia przez strefę lądowania (Chebyshev <= {V2.LAD_PROMIEN} od (32480,31721)) w ŚRODKU pętli (indeks od, do, pole od, pole do): {runy}")
    pn = [tuple(p) for p in json.loads((ROOT / "trasy" / f"{NS.NAZWA}_polnoc{V2.SUFIKS}_petla.json").read_text())]
    pom = V2.pomiar(pn, pel)
    V2.drukuj_pomiar("v5 vs północna v2 (plik)", pom)
    ok, opis = V2.kryterium(pom)
    print(("KRYTERIUM ROZŁĄCZNOŚCI (v5 z północną v2) SPEŁNIONE: " if ok else "KRYTERIUM NIESPEŁNIONE: ") + opis)
    og = V4.ogien_przy_trasie(pel, Z.ogien_surowy())
    dz = V4.ogien_przy_trasie(pel, Z.dziury_omijaj() | Z.dziury_nauczone())
    P = set(P2)
    for nm, sl in (("ogień", og), ("dziura", dz)):
        print(f"v5: pola {nm} z punktami trasy w Chebyshev <= 1: {len(sl)}; punktów trasy łącznie {sum(sum(1 for p in P2 if p in set(bl)) for bl in sl.values())}")
        for f, bl in sl.items():
            wyj = (f[0], f[1], 9) in (WYJATKI_OGIEN5 if nm == "ogień" else WYJATKI_DZIURY5)
            print(f"  {nm} {f}{' (WYJĄTEK bufor 0)' if wyj else ''}: pola trasy {bl}")
    xs_, ys_ = [c[0] for c in o["comp"]], [c[1] for c in o["comp"]]
    prz = set(Z.skan_przeszkod(m, 9, (min(xs_) - Z.MARGINES_SKANU, min(ys_) - Z.MARGINES_SKANU, max(xs_) + Z.MARGINES_SKANU, max(ys_) + Z.MARGINES_SKANU)))
    pr = V4.ogien_przy_trasie(pel, prz)
    print(f"v5: przeszkody (flaga 2 w kolorze podłogi) z punktami trasy w Chebyshev <= 1: {len(pr)}; punktów trasy na samych przeszkodach: {sum(1 for p in P2 if (p[0], p[1], 9) in prz)} (musi być 0)")
    for f, bl in pr.items():
        print(f"  przeszkoda {f}{' (WYJĄTEK bufor 0)' if (f[0], f[1], 9) in (WYJATKI_PRZESZKODY5 | WYJATKI_DZIURY5) else ''}: pola trasy {bl}")
    zakaz = Z.ogien_surowy() | Z.dziury_omijaj() | Z.dziury_nauczone()
    print(f"v5: punktów trasy NA polu ognia/dziury (ogień surowy, dziury_omijaj, dziury nauczone): {sum(1 for p in P2 if (p[0], p[1], 9) in zakaz)} (musi być 0)")
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    if not ok:
        raise SystemExit("kryterium rozłączności niespełnione: nic nie zapisano")
    zapisz(m, o)
    print("zapisano trasy/abdendriel_zachod_z9_poludnie_v5_petla.json i dane_tibia/mapy/abdendriel_zachod_z9_poludnie_v5.{png,json} (BEZ wpisu mapy.json)")


if __name__ == "__main__":
    main()
