#!/usr/bin/env python3
"""Ab'Dendriel zachód z9: PODGLĄD południowej pętli v3 (27.10, pytanie Karola: czy południowa nie powinna iść dalej w lewo/w górę przez zachodnie pokoje i wracać inną drogą).
Tylko podgląd: pisze WYŁĄCZNIE trasy/abdendriel_zachod_z9_poludnie_v3_petla.json i dane_tibia/mapy/abdendriel_zachod_z9_poludnie_v3.{png,json}; BEZ wpisu w mapy.json;
generatory ns/ns2, pętle v2, stare N/S i pełna NIE są ruszane (importujemy funkcje).

JEDYNY wyjątek od polityki (ns2): `BUFOR_WYJATKI_OGIEN` = {pole ognia: bufor}; dla pola z buforem 0 samo pole zostaje ścianą (trasa nie wchodzi na nie), ale jego 8 sąsiadów
przestaje być ścianą (o ile nie obejmuje ich bufor innego pola ognia, dziury, przeszkody, strefy). Dziś: (32437,31695,z9) -> 0 (stały ogień dodany 27.10 11:45 zamykał buforem 1 korytarz do
zachodnich pokoi (32427,31696), (32398,31707), (32406,31727)). Wszystkie inne pola ognia i wszystkie dziury: bufor 1 jak dotąd. Przystanki: te same co południowa v2 + osiągalne zachodnie
(y >= PROG_Y albo PRZYPISANIE z ns2). Held-Karp + reguła kosztu jak w ns/ns2.

  python3 -I generuj_trasy_abdendriel_zachod_ns3.py [--zapisz]   bez --zapisz tylko liczy i drukuje: tabelę v2/v3, kształt (odcinki tam-i-z-powrotem, pola przy polu ognia),
                                                                 wspólne pola z północną v2 (plik), graf pokoi zachodnich (rozłączne drogi, wąskie przejścia)
"""
import argparse
import json
import sys
from collections import deque
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generuj_trasy_abdendriel_zachod as Z  # noqa: E402
import generuj_trasy_abdendriel_zachod_ns as NS  # noqa: E402
import generuj_trasy_abdendriel_zachod_ns2 as V2  # noqa: E402
import mapa as _mapa  # noqa: E402
import spot_lib  # noqa: E402
from spot_lib import ladowanie, przystanki  # noqa: E402

NAZWA3 = "abdendriel_zachod_z9_poludnie_v3"
BUFOR_WYJATKI_OGIEN = {(32437, 31695, 9): 0}     # pole ognia -> bufor (0 = samo pole ścianą, sąsiedzi wolni)
POKOJE_ZACH = ((32427, 31696), (32398, 31707), (32406, 31727))     # zachodnie pokoje odcięte buforem 1 (informacyjnie, do grafu)


def ogien_z_wyjatkami():
    """(ogień ze ścianą dla A*, wyjątkowe pola) : bufor 1 dla wszystkich pól ognia poza wyjątkami z buforem 0 (te: samo pole)."""
    surowy = Z.ogien_surowy()
    wyj = {p for p, b in BUFOR_WYJATKI_OGIEN.items() if b == 0 and p in surowy}
    return Z.z_buforem(surowy - wyj) | wyj, wyj


def przygotuj3(m):
    """Jak NS.przygotuj (składowa z9, ściany, przystanki), ale z ogniem ogien_z_wyjatkami()."""
    dz_n = Z.dziury_nauczone()
    om = Z.dziury_omijaj()
    dz = dz_n | om
    ogien, wyj = ogien_z_wyjatkami()
    strefa = set()
    for z in Z.PIETRA:
        for n in Z.ZAKAZANE:
            for s in spot_lib.spawny(z, (n,), (32380, 32640, 31560, 31800)):
                strefa |= spot_lib.strefa_zakazana([dict(s, nazwa=n)], z, Z.STREFA[n])
    L9 = ladowanie(m, Z.H8[0])
    if tuple(L9) != NS.LAD9:
        raise SystemExit(f"lądowanie z9 {L9} != {NS.LAD9}")
    stale9 = {p for p in ogien | strefa | dz_n if p[2] == 9}
    comp9, _prz, sciana9_set, _obszar = Z.skladowa_ze_skanem(m, 9, L9, stale9, {p for p in om if p[2] == 9})
    sciana9 = sorted(sciana9_set | {p for p in dz if p[2] == 9})
    obsz = (min(c[0] for c in comp9) - 5, max(c[0] for c in comp9) + 5, min(c[1] for c in comp9) - 5, max(c[1] for c in comp9) + 5)
    st = przystanki(spot_lib.spawny(9, Z.CEL9, obsz), comp9)
    return L9, comp9, sciana9, set(sciana9_set), st, wyj


def zbuduj_v3(m=None):
    m = m or _mapa.Mapa()
    L9, comp9, sciana9, zle9, wszystkie, wyj = przygotuj3(m)
    cele = [t for t in wszystkie if t["pt"] not in NS.WYKLUCZONE_NS]
    gr = V2.grupa("poludnie", cele)
    print(f"v3: wyjątki ognia (bufor 0): {sorted(wyj)}; składowa {len(comp9)} pól; przystanki celowane {len(wszystkie)} ({sum(t['n'] for t in wszystkie)} trolli), południe {len(gr)} ({sum(t['n'] for t in gr)})")
    st, pomin = NS.dobierz(m, L9, sciana9, gr)
    for pt, n, g, proc in pomin:
        print(f"{NAZWA3}: POMINIĘTY przystanek {pt} ({n} potw.): skraca cykl o {g} pól = {proc}%")
    st, odp, order, nodes, pelna = Z.petla_opt(m, 9, L9[:2], st, sciana9, 10 ** 9)
    dz = Z.dziury_nauczone() | Z.dziury_omijaj()
    bad = [p for p in pelna if (p[0], p[1], 9) in zle9 or (p[0], p[1], 9) in dz]
    if bad:
        raise SystemExit(f"{NAZWA3}: pętla wchodzi w ogień/przeszkodę/dziurę/strefę: {bad[:5]}")
    if pelna[0] != tuple(L9[:2]) or pelna[-1] != tuple(L9[:2]):
        raise SystemExit("pętla nie zaczyna i nie kończy się w lądowaniu")
    gardla = Z.waskie_gardla(m, comp9, zle9, pelna, 9)
    return {"L": L9, "comp": comp9, "st": st, "pomin": pomin, "order": order, "nodes": nodes, "pelna": pelna, "gardla": gardla, "zle": zle9, "sciana": sciana9, "wyj": wyj}


def ksztalt(pelna, ogien_pole):
    """Kształt pętli: krawędzie przebyte w OBU kierunkach (tam i z powrotem), pola odwiedzone >= 2 razy (bez startu/końca), punkty przy polu ognia (Chebyshev <= 1)."""
    p = [(a[0], a[1]) for a in pelna]
    kr = {}
    for a, b in zip(p, p[1:]):
        kr.setdefault((a, b), 0)
        kr[(a, b)] += 1
    dwa = {frozenset(k) for k in kr if (k[1], k[0]) in kr}
    ile = {}
    for q in p[1:-1]:
        ile[q] = ile.get(q, 0) + 1
    podw = {q for q, n in ile.items() if n >= 2}
    of = (ogien_pole[0], ogien_pole[1])
    przy = [q for q in p if V2.cheb(q, of) <= 1]
    return {"krawedzie_obu_kierunkow": len(dwa), "pola_wielokrotne": len(podw), "punkty_przy_ogniu": len(przy), "unikalne_pola_przy_ogniu": sorted(set(przy)), "dlugosc": len(p) - 1}


def disjoint(comp, s, targets, zablokowane=()):
    """Liczba ROZŁĄCZNYCH WIERZCHOŁKOWO dróg (pola, 8 sąsiadów) z `s` do zbioru `targets` w `comp` minus `zablokowane` (Edmonds-Karp na grafie z rozszczepionymi wierzchołkami)
    oraz minimalny zbiór pól przecinający (przesmyk), gdy liczba > 0."""
    pola = [c for c in comp if c not in zablokowane]
    idx = {c: i for i, c in enumerate(pola)}
    n = len(pola)
    S, T = 2 * idx[s] + 1, 2 * n          # wejście i = 2i, wyjście i = 2i+1 ; źródło = wyjście s ; ujście = T
    cap = {}
    adj = [[] for _ in range(2 * n + 1)]

    def add(a, b, c):
        for u, v, w in ((a, b, c), (b, a, 0)):
            if (u, v) not in cap:
                adj[u].append(v)
                cap[(u, v)] = 0
            cap[(u, v)] += w
    cele = set(targets)
    for c, i in idx.items():
        add(2 * i, 2 * i + 1, 8 if (len(cele) == 1 and c in cele) else 1)      # pojedynczy cel: jego własna pojemność nie ogranicza liczby dróg (sąsiedzi celu)
        for nb in spot_lib.sasiedzi(c[0], c[1]):
            if nb in idx:
                add(2 * i + 1, 2 * idx[nb], 1)
    for t in targets:
        if t in idx:
            add(2 * idx[t] + 1, T, 8 if len(cele) == 1 else 1)
    flow = 0
    while True:
        par = {S: None}
        q = deque([S])
        while q and T not in par:
            u = q.popleft()
            for v in adj[u]:
                if v not in par and cap[(u, v)] > 0:
                    par[v] = u
                    q.append(v)
        if T not in par:
            break
        v = T
        while par[v] is not None:
            cap[(par[v], v)] -= 1
            cap[(v, par[v])] += 1
            v = par[v]
        flow += 1
    odw = set(par)
    ciecie = sorted(c for c, i in idx.items() if 2 * i in odw and 2 * i + 1 not in odw)
    return flow, ciecie


def analiza_grafu(m, o):
    comp, L = set(o["comp"]), tuple(o["L"][:2])
    of = [(p[0], p[1]) for p in BUFOR_WYJATKI_OGIEN][0]
    pokoje = [p for p in POKOJE_ZACH if p in comp]
    print(f"graf: pokoje zachodnie w składowej v3: {pokoje} (poza nią: {[p for p in POKOJE_ZACH if p not in comp]})")
    for p in pokoje:
        f, cut = disjoint(comp, L, [p])
        print(f"  lądowanie -> {p}: dróg rozłącznych wierzchołkowo (z wyjątkiem końców) = {f}; najmniejszy przesmyk (pola): {cut[:12]}")
    if pokoje:
        f, cut = disjoint(comp, L, pokoje)
        print(f"  lądowanie -> wszystkie pokoje zachodnie naraz: dróg rozłącznych = {f}; przesmyk: {cut[:12]}")
    bez = {c for c in comp if V2.cheb(c, of) <= 1}
    f2, cut2 = disjoint(comp, L, pokoje, zablokowane=bez - {L}) if pokoje else (0, [])
    print(f"  BEZ 3x3 wokół ognia {of} (czyli jak bufor 1): dróg do pokoi = {f2} (0 = pokoje odcięte; ten przesmyk to jedyny dostęp)")
    print(f"  pola składowej v3 w 3x3 wokół ognia: {sorted(bez)}")


def tabela(v2, v3):
    print(f"{'wariant':16s} {'pola':>6s} {'przyst.':>8s} {'potwory':>8s} {'pola/potw.':>11s} {'waskie gardla':>14s}")
    for nm, d in (("poludnie_v2", v2), ("poludnie_v3", v3)):
        n = sum(t["n"] for t in d["st"])
        print(f"{nm:16s} {len(d['pelna']):6d} {len(d['st']):8d} {n:8d} {len(d['pelna']) / n:11.1f} {len(d['gardla']):14d}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    ap.add_argument("--wyjatki", default="", help="TYLKO informacyjnie: zamiast BUFOR_WYJATKI_OGIEN pola ognia 'x,y,z;x,y,z' z buforem 0 (nie łączy się z --zapisz)")
    a = ap.parse_args(argv)
    if a.wyjatki:
        if a.zapisz:
            raise SystemExit("--wyjatki jest tylko informacyjne: nie łączy się z --zapisz")
        BUFOR_WYJATKI_OGIEN.clear()
        BUFOR_WYJATKI_OGIEN.update({tuple(int(v) for v in t.split(",")): 0 for t in a.wyjatki.split(";") if t.strip()})
        print(f"INFO: wyjątki ognia (bufor 0) zastąpione: {sorted(BUFOR_WYJATKI_OGIEN)} (TYLKO informacyjnie)")
    print(f"pliki ognia/dziur (sha1, 12 znaków): {V2.sha1_ognia()}")
    m = _mapa.Mapa()
    o3 = zbuduj_v3(m)
    out2 = V2.zbuduj_v2(m)
    print(f"v3: przystanki w kolejności: {[(t['pt'], t['n']) for t in o3['st']]}; kolejność węzłów {o3['order']}")
    tabela(out2["poludnie"], o3)
    print(f"v3: wąskie gardła {len(o3['gardla'])}: {o3['gardla']}")
    for nm, pel in (("v2", out2["poludnie"]["pelna"]), ("v3", o3["pelna"])):
        k = ksztalt(pel, list(BUFOR_WYJATKI_OGIEN)[0])
        print(f"kształt {nm}: długość {k['dlugosc']}, krawędzie przebyte w OBU kierunkach (tam i z powrotem) {k['krawedzie_obu_kierunkow']}, pola odwiedzone >= 2 razy {k['pola_wielokrotne']}")
        for pf in sorted(BUFOR_WYJATKI_OGIEN):
            kk = ksztalt(pel, pf)
            print(f"  punkty trasy w Chebyshev <= 1 od pola ognia {pf}: {kk['punkty_przy_ogniu']} (unikalnych {len(kk['unikalne_pola_przy_ogniu'])}: {kk['unikalne_pola_przy_ogniu']})")
    pn = [tuple(p) for p in json.loads((ROOT / "trasy" / f"{NS.NAZWA}_polnoc{V2.SUFIKS}_petla.json").read_text())]
    pom = V2.pomiar(pn, o3["pelna"])
    V2.drukuj_pomiar("v3 vs północna v2 (plik)", pom)
    ok, opis = V2.kryterium(pom)
    print(("KRYTERIUM ROZŁĄCZNOŚCI (v3 z północną v2) SPEŁNIONE: " if ok else "KRYTERIUM NIESPEŁNIONE: ") + opis)
    analiza_grafu(m, o3)
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    if not ok:
        raise SystemExit("kryterium rozłączności niespełnione: nic nie zapisano")
    spot_lib.zapis_spotu(m, NAZWA3, 9, o3["pelna"], o3["order"], o3["nodes"], o3["st"], "Ab'Dendriel zachod z9 poludnie v3 (PODGLAD)", jedn="potw.", opis_przyst="spawn(y) trolli")
    print("zapisano trasy/abdendriel_zachod_z9_poludnie_v3_petla.json i dane_tibia/mapy/abdendriel_zachod_z9_poludnie_v3.{png,json} (BEZ wpisu mapy.json)")


if __name__ == "__main__":
    main()
