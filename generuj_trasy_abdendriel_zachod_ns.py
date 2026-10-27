#!/usr/bin/env python3
"""Ab'Dendriel zachód z9: dwa warianty pętli do porównania na żywo (27.10, decyzja Karola: pełna pętla jest tak duża, że 49% czasu to marsz, 43% walka,
99 zabić/h, ok. 1880 exp/h). Obok pełnej `abdendriel_zachod_z9` (generuj_trasy_abdendriel_zachod.py, NIE ruszana):

  abdendriel_zachod_z9_polnoc    pętla PÓŁNOCNA: przystanki celowane (troll) z y <  PROG_Y
  abdendriel_zachod_z9_poludnie  pętla POŁUDNIOWA: przystanki celowane (troll) z y >= PROG_Y

Start i koniec każdej = lądowanie (32480,31721,z9) (pole liny; leży na południu), dojście `abdendriel_zachod_z9_dojscie` i powrót (plan PLANY_PK
`abdendriel_zachod_z9`) są wspólne z pełną pętlą. Wszystko liczone TĄ SAMĄ polityką co pełna pętla (funkcje i stałe z generuj_trasy_abdendriel_zachod):
ogień = ogien_stale + epizody hp (bufor 1), dziury z trasy/dziury_omijaj.json jako ściana + bufor 1 (odstęp >= 2), pełny skan przeszkód w obszarze składowej
(bufor 1), strefy rotwormów i poison spiderów, składowa od lądowania, DOKŁADNY najkrótszy cykl (Held-Karp), waskie_gardla(). Zmienia się tylko dobór przystanków:

  1. przystanki = WSZYSTKIE osiągalne przystanki celowane w składowej (16 wg raportu 27.10, 46 trolli) bez WYKLUCZONE_NS: północny pokój (32436,31573)
     (5 trolli, 4 dziury i pola ognia, odpadł już w pełnej pętli) zostaje wykluczony;
  2. podział wg y: północ y < PROG_Y, południe y >= PROG_Y (próg tak, by liczby potworów były możliwie zbliżone; patrz niżej);
  3. BEZ limitu +10% względem pełnej pętli (limit dotyczył pełnej); każda połowa bierze wszystkie swoje przystanki, z JEDNYM wyjątkiem: przystanek o <= KOSZT_MAX_POTW
     potworach, którego pominięcie skraca cykl o więcej niż KOSZT_PROG (25%), jest pomijany (powtarzane, najpierw najdroższy); każdy taki przystanek jest wypisany z kosztem.

Ocena progu (stan plików ognia/dziur 27.10; przystanki bez północnego pokoju: 15, 41 trolli; wiersz = prog y<X: północ/południe, potwory, cykl):
  y<31633 1/14 przyst. 2/39 378/1378 | y<31645 3/12 8/33 504/1312 | y<31672 5/10 12/29 924/1014 | y<31685 6/9 13/28 924/908 | y<31691 7/8 17/24 930/824
  y<31696 8/7 19/22 1102/822 (WYBRANY: najbliższe sobie liczby potworów 19/22, różnica 3) | y<31707 9/6 24/17 1104/820 | y<31720 11/4 30/11 1116/778.
Próg ok. y 31672 z opisu zadania (28/31 potworów) liczył też spawny poza składową (59 potworów); wśród osiągalnych 41 daje 12/29, więc nie jest wybrany.
Przystanek (32410,31671) (2 trolle, pokój (32406..32412,31671..31674) z wąskim przejściem przez przeszkody) wydłuża północ o 394 pola z 1102 (36%): pomijany regułą.

  python3 -I generuj_trasy_abdendriel_zachod_ns.py [--zapisz]     bez --zapisz tylko liczy i drukuje podsumowanie (tabela trzech wariantów)

Z --zapisz powstają WYŁĄCZNIE: trasy/abdendriel_zachod_z9_{polnoc,poludnie}_petla.json i dane_tibia/mapy/abdendriel_zachod_z9_{polnoc,poludnie}.{png,json}.
Wpisy mapy.json: ręcznie. Plany ucieczki PK/powrotu: plan PLANY_PK `abdendriel_zachod_z9` wybierany po POZYCJI (wyprawa.wybierz_baze), nie po nazwie mapy
(test: testy/test_zachod_abdendriel.py sekcja 9). Test: testy/test_zachod_abdendriel.py.
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generuj_trasy_abdendriel_zachod as Z  # noqa: E402  (jedno źródło polityki: ogień, bufor, strefy, skan, Held-Karp, wąskie gardła)
import mapa as _mapa  # noqa: E402
import spot_lib  # noqa: E402
from spot_lib import ladowanie, przystanki  # noqa: E402

NAZWA = "abdendriel_zachod_z9"
WARIANTY = ("polnoc", "poludnie")
PROG_Y = 31696                                    # północ: przystanki z y < PROG_Y, południe: y >= PROG_Y (patrz docstring: ocena progów)
WYKLUCZONE_NS = {(32436, 31573): "północny pokój: 4 dziury i pola ognia, 5 trolli, +312 pól cyklu (odpadł też w pełnej pętli)"}
KOSZT_PROG = 0.25                                 # pomiń przystanek, którego pominięcie skraca cykl o więcej niż 25% ...
KOSZT_MAX_POTW = 2                                # ... gdy ma nie więcej niż tyle potworów
LAD9 = (32480, 31721, 9)                          # lądowanie = start i koniec obu pętli (niezależnie od generatora sprawdza test)


def nazwa_wariantu(w):
    return f"{NAZWA}_{w}"


def przygotuj(m):
    """Składowa z9 i ściany DOKŁADNIE jak w Z.zbuduj() dla z9 (test 9a sprawdza zgodność ze składową generatora).
    Zwraca (lądowanie, comp9, sciana9 [lista], zle9 [zbiór], wszystkie przystanki celowane w składowej)."""
    dz_n = Z.dziury_nauczone()
    om = Z.dziury_omijaj()
    dz = dz_n | om
    ogien = Z.z_buforem(Z.ogien_surowy())
    strefa = set()
    for z in Z.PIETRA:
        for n in Z.ZAKAZANE:
            for s in spot_lib.spawny(z, (n,), (32380, 32640, 31560, 31800)):
                strefa |= spot_lib.strefa_zakazana([dict(s, nazwa=n)], z, Z.STREFA[n])
    L9 = ladowanie(m, Z.H8[0])
    if tuple(L9) != LAD9:
        raise SystemExit(f"lądowanie z9 {L9} != {LAD9}")
    stale9 = {p for p in ogien | strefa | dz_n if p[2] == 9}
    comp9, _prz, sciana9_set, _obszar = Z.skladowa_ze_skanem(m, 9, L9, stale9, {p for p in om if p[2] == 9})
    sciana9 = sorted(sciana9_set | {p for p in dz if p[2] == 9})
    obsz = (min(c[0] for c in comp9) - 5, max(c[0] for c in comp9) + 5, min(c[1] for c in comp9) - 5, max(c[1] for c in comp9) + 5)
    st = przystanki(spot_lib.spawny(9, Z.CEL9, obsz), comp9)
    return L9, comp9, sciana9, set(sciana9_set), st


def _cykl(D, idx):
    """Długość najkrótszego cyklu od węzła 0 przez węzły `idx` (indeksy w D, bez 0)."""
    w = [0] + list(idx)
    sub = [[D[a][b] for b in w] for a in w]
    return Z.held_karp(sub)[1]


def dobierz(m, L9, sciana9, st):
    """(wybrane, pominięte_kosztowne [(pt, n, zysk, % cyklu)]): cały podzbiór `st`, z którego regułą kosztu wypadają przystanki <= KOSZT_MAX_POTW potworów
    skracające cykl o > KOSZT_PROG (najdroższy najpierw, powtarzane do skutku)."""
    wezly = [tuple(L9[:2])] + [t["pt"] for t in st]
    D = Z.macierz_drog(m, 9, wezly, sciana9)
    zostaja = list(range(1, len(wezly)))
    pominiete = []
    while len(zostaja) > 1:
        pelny = _cykl(D, zostaja)
        zyski = [(pelny - _cykl(D, [j for j in zostaja if j != i]), i) for i in zostaja if st[i - 1]["n"] <= KOSZT_MAX_POTW]
        zyski = [(g, i) for g, i in zyski if g > KOSZT_PROG * pelny]
        if not zyski:
            break
        g, i = max(zyski)
        pominiete.append((st[i - 1]["pt"], st[i - 1]["n"], g, round(100.0 * g / pelny)))
        zostaja.remove(i)
    return [st[i - 1] for i in zostaja], pominiete


def zbuduj_ns(m=None):
    """Słownik wariant -> dane pętli. Nic nie zapisuje."""
    m = m or _mapa.Mapa()
    L9, comp9, sciana9, zle9, wszystkie = przygotuj(m)
    wyklucz = [t for t in wszystkie if t["pt"] in WYKLUCZONE_NS]
    cele = [t for t in wszystkie if t["pt"] not in WYKLUCZONE_NS]
    print(f"z9: przystanki celowane w składowej {len(wszystkie)} ({sum(t['n'] for t in wszystkie)} trolli); wykluczone: "
          f"{[(t['pt'], t['n'], WYKLUCZONE_NS[t['pt']]) for t in wyklucz]}; do podziału {len(cele)} ({sum(t['n'] for t in cele)} trolli), próg y < {PROG_Y} północ")
    dz = Z.dziury_nauczone() | Z.dziury_omijaj()
    out = {}
    for w in WARIANTY:
        grupa = [t for t in cele if (t["pt"][1] < PROG_Y) == (w == "polnoc")]
        st, pomin = dobierz(m, L9, sciana9, grupa)
        for pt, n, g, proc in pomin:
            print(f"{nazwa_wariantu(w)}: POMINIĘTY przystanek {pt} ({n} potw.): skraca cykl o {g} pól = {proc}% (> {int(KOSZT_PROG * 100)}% dla <= {KOSZT_MAX_POTW} potworów)")
        st, odp, order, nodes, pelna = Z.petla_opt(m, 9, L9[:2], st, sciana9, 10 ** 9)
        bad = [p for p in pelna if (p[0], p[1], 9) in zle9 or (p[0], p[1], 9) in dz]
        if bad:
            raise SystemExit(f"{nazwa_wariantu(w)}: pętla wchodzi w ogień/przeszkodę/dziurę/strefę: {bad[:5]}")
        if pelna[0] != tuple(L9[:2]) or pelna[-1] != tuple(L9[:2]):
            raise SystemExit(f"{nazwa_wariantu(w)}: pętla nie zaczyna i nie kończy się w lądowaniu: {pelna[0]} .. {pelna[-1]}")
        gardla = Z.waskie_gardla(m, comp9, zle9, pelna, 9)
        n = sum(t["n"] for t in st)
        print(f"{nazwa_wariantu(w)}: przystanków {len(st)}, trolli {n}, pętla {len(pelna)} pól ({len(pelna) / n:.1f} pola/potwora), kolejność {order}; "
              f"wąskie gardła {len(gardla)} pól: {gardla}")
        out[w] = {"L": L9, "comp": comp9, "st": st, "pomin": pomin, "order": order, "nodes": nodes, "pelna": pelna, "gardla": gardla, "zle": zle9}
    return out


def tabela(out):
    """Tabela pełna / północ / południe (pełna z dane_tibia/mapy/abdendriel_zachod_z9.json = to, co jest w pliku trasy)."""
    j = json.loads((ROOT / "dane_tibia" / "mapy" / f"{NAZWA}.json").read_text())
    pel = [t for t in j["przystanki"] if "potworow" in t]
    wiersze = [("pełna", j["dlugosc_petli"], len(pel), sum(t["potworow"] for t in pel))]
    wiersze += [(w, len(o["pelna"]), len(o["st"]), sum(t["n"] for t in o["st"])) for w, o in out.items()]
    print(f"{'wariant':10s} {'pola':>6s} {'przyst.':>8s} {'potwory':>8s} {'pola/potw.':>11s}")
    for nm, dl, ps, pw in wiersze:
        print(f"{nm:10s} {dl:6d} {ps:8d} {pw:8d} {dl / pw:11.1f}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m = _mapa.Mapa()
    out = zbuduj_ns(m)
    tabela(out)
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    for w, o in out.items():
        spot_lib.zapis_spotu(m, nazwa_wariantu(w), 9, o["pelna"], o["order"], o["nodes"], o["st"], f"Ab'Dendriel zachod z9 {w}",
                             jedn="potw.", opis_przyst="spawn(y) trolli")
    print("zapisano trasy/abdendriel_zachod_z9_{polnoc,poludnie}_petla.json i dane_tibia/mapy/abdendriel_zachod_z9_{polnoc,poludnie}.{png,json}; mapy.json osobno")


if __name__ == "__main__":
    main()
