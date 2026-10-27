#!/usr/bin/env python3
"""Ab'Dendriel zachód z9: dwie pętle ROZŁĄCZNE `_v2` (27.10, decyzja Karola: „tych tras nie zmieniajmy, tylko zróbmy ich KOPIE, bo te już dobrze wychodzą”).

Istniejące `abdendriel_zachod_z9` (pełna), `abdendriel_zachod_z9_polnoc` i `abdendriel_zachod_z9_poludnie` (generuj_trasy_abdendriel_zachod[_ns].py) NIE są ruszane:
ten skrypt pisze WYŁĄCZNIE nowe nazwy

  abdendriel_zachod_z9_polnoc_v2    pętla PÓŁNOCNA bez wschodniego ramienia
  abdendriel_zachod_z9_poludnie_v2  pętla POŁUDNIOWA z wschodnim przystankiem (32531,31691)

Powód (pomiar 27.10 na starych N/S): północna szła wschodnim ramieniem do przystanku (32531,31691) (2 trolle, ok. 175 z 709 punktów) TYM SAMYM korytarzem od lądowania
(32480,31721), co południowa do swoich przystanków (32505,31713) i (32499,31731): 87 wspólnych pól (19%/20%), 170 punktów północnej na polach południowej. Dwie postacie naraz
(jedna na północy, druga na południu) wchodziłyby sobie w drogę. Tu przystanek wschodni należy do POŁUDNIOWEJ (`PRZYPISANIE`), reszta podziału jak w ns.py (północ y < PROG_Y).

Cała polityka jak w pełnej pętli i ns.py (funkcje i stałe z generuj_trasy_abdendriel_zachod[_ns]): ogień = ogien_stale + epizody hp (bufor 1), dziury z dziury_omijaj
(ściana + bufor 1, odstęp >= 2), pełny skan przeszkód w obszarze składowej, strefy rotworm/poison spider, DOKŁADNY najkrótszy cykl (Held-Karp), reguła kosztu
(przystanek <= 2 potwory skracający cykl o > 25% jest pomijany), waskie_gardla(). Pętle startują i kończą w lądowaniu (32480,31721,z9) (jedyne wejście: pole liny).

KRYTERIUM ROZŁĄCZNOŚCI (sprawdzane przy --zapisz i w testach/test_zachod_abdendriel_v2.py): pola wspólne obu pętli poza lądowaniem (Chebyshev <= LAD_PROMIEN od (32480,31721)) = 0,
wspólnych w ogóle <= WSPOLNE_MAX (5). Przy --zapisz naruszenie kryterium kończy się SystemExit i NIC nie jest zapisywane (ogień rośnie w czasie gry: przepiszą się pliki,
gdy kryterium znów będzie spełnione). Pomiar: wspólne pola, wspólne odcinki, liczba punktów jednej pętli w odległości Chebysheva <= 1/<= 2/<= 3 od drugiej (poza strefą lądowania).

  python3 -I generuj_trasy_abdendriel_zachod_ns2.py [--zapisz]          bez --zapisz tylko liczy i drukuje pomiar + tabelę (stare N/S z plików vs v2)
  python3 -I generuj_trasy_abdendriel_zachod_ns2.py --bez-ognia 32437,31695,9;...   TYLKO INFORMACYJNIE: licz bez wskazanych pól ognia (nie łączy się z --zapisz)

Z --zapisz powstają WYŁĄCZNIE: trasy/abdendriel_zachod_z9_{polnoc,poludnie}_v2_petla.json i dane_tibia/mapy/abdendriel_zachod_z9_{polnoc,poludnie}_v2.{png,json}.
Wpisy mapy.json: ręcznie (kopia mapy.json.bak-20261027-z9-v2). Plan ucieczki PK/powrót: plan PLANY_PK `abdendriel_zachod_z9`, wybierany po POZYCJI (wyprawa.wybierz_baze).
Test: testy/test_zachod_abdendriel_v2.py."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generuj_trasy_abdendriel_zachod as Z  # noqa: E402  (jedno źródło polityki)
import generuj_trasy_abdendriel_zachod_ns as NS  # noqa: E402  (przygotuj, dobierz, PROG_Y, WYKLUCZONE_NS, reguła kosztu)
import mapa as _mapa  # noqa: E402
import spot_lib  # noqa: E402

WARIANTY = ("polnoc", "poludnie")
SUFIKS = "_v2"
PRZYPISANIE = {(32531, 31691): "poludnie"}      # przystanek -> pętla, niezależnie od progu y (wschodnie ramię = korytarz południowej)
LAD9 = NS.LAD9                                   # (32480,31721,9)
LAD_PROMIEN = 2                                  # „lądowanie”: pole liny i najbliższe sąsiedztwo = Chebyshev <= tyle
LAD_PROMIEN_BLISKO = 6                           # pomiar bliskości punktów: pomijamy punkty obu pętli w tym promieniu od lądowania (wspólny dojazd do liny)
WSPOLNE_MAX = 5                                  # wspólnych pól w ogóle (unikalnych) co najwyżej tyle
FLAGI_OGIEN = ("ogien_stale.json", "ogien_epizody.json", "dziury_omijaj.json", "dziury_nauczone.json")


def nazwa_wariantu(w):
    return f"{NS.NAZWA}_{w}{SUFIKS}"


def sha1_ognia():
    """sha1 (12 znaków) plików ognia/dziur, z których liczy generator (do raportu i opisu: ogień rośnie w czasie gry)."""
    h = {f: hashlib.sha1((ROOT / "trasy" / f).read_bytes()).hexdigest()[:12] for f in FLAGI_OGIEN}
    h["ogien_efektywny(stale+epizody hp)"] = hashlib.sha1(json.dumps(sorted(Z.ogien_surowy())).encode()).hexdigest()[:12]   # to liczy się do ściany: epizody bez hp go nie zmieniają
    return h


def grupa(w, cele):
    """Przystanki wariantu: przypisanie ręczne, reszta wg progu y (północ y < PROG_Y)."""
    return [t for t in cele if (PRZYPISANIE.get(t["pt"]) == w if t["pt"] in PRZYPISANIE else (t["pt"][1] < NS.PROG_Y) == (w == "polnoc"))]


def zbuduj_v2(m=None):
    """Słownik wariant -> dane pętli (jak NS.zbuduj_ns). Nic nie zapisuje."""
    m = m or _mapa.Mapa()
    L9, comp9, sciana9, zle9, wszystkie = NS.przygotuj(m)
    cele = [t for t in wszystkie if t["pt"] not in NS.WYKLUCZONE_NS]
    print(f"z9: przystanki celowane w składowej {len(wszystkie)} ({sum(t['n'] for t in wszystkie)} trolli); do podziału {len(cele)} ({sum(t['n'] for t in cele)}); "
          f"przypisane ręcznie: {PRZYPISANIE}; reszta wg y < {NS.PROG_Y} północ")
    dz = Z.dziury_nauczone() | Z.dziury_omijaj()
    out = {}
    for w in WARIANTY:
        st, pomin = NS.dobierz(m, L9, sciana9, grupa(w, cele))
        for pt, n, g, proc in pomin:
            print(f"{nazwa_wariantu(w)}: POMINIĘTY przystanek {pt} ({n} potw.): skraca cykl o {g} pól = {proc}% (> {int(NS.KOSZT_PROG * 100)}% dla <= {NS.KOSZT_MAX_POTW} potworów)")
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
        out[w] = {"L": L9, "comp": comp9, "st": st, "pomin": pomin, "order": order, "nodes": nodes, "pelna": pelna, "gardla": gardla, "zle": zle9, "sciana": sciana9}
    return out


def odcinki(pola_sciezka, wspolne):
    """Wspólne odcinki: maksymalne ciągi kolejnych punktów ścieżki (w kolejności przejścia) leżących w zbiorze `wspolne`; [(pierwszy, ostatni, długość)]."""
    wyn, cur = [], []
    for p in pola_sciezka:
        if p in wspolne:
            cur.append(p)
        elif cur:
            wyn.append((cur[0], cur[-1], len(cur)))
            cur = []
    if cur:
        wyn.append((cur[0], cur[-1], len(cur)))
    return wyn


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def pomiar(pn, ps):
    """Pomiar styku dwóch pętli (listy (x, y) lub (x, y, z)): wspólne pola, wspólne odcinki (w kolejności północnej), wspólne poza lądowaniem
    (Chebyshev > LAD_PROMIEN), punkty jednej pętli w odległości Chebysheva <= 1/2/3 od punktu drugiej (bez punktów w promieniu LAD_PROMIEN_BLISKO od lądowania)."""
    A = [(p[0], p[1]) for p in pn]
    B = [(p[0], p[1]) for p in ps]
    sa, sb = set(A), set(B)
    wsp = sa & sb
    lad = LAD9[:2]
    poza = sorted(p for p in wsp if cheb(p, lad) > LAD_PROMIEN)
    wynik = {"wspolne": sorted(wsp), "wspolne_poza": poza, "odcinki": odcinki(A, wsp), "udzial_polnoc": len(wsp) / len(sa), "udzial_poludnie": len(wsp) / len(sb)}
    daleko_b = [q for q in sb if cheb(q, lad) > LAD_PROMIEN_BLISKO]
    daleko_a = [q for q in sa if cheb(q, lad) > LAD_PROMIEN_BLISKO]
    for r in (1, 2, 3):
        wynik[f"polnoc_blisko_{r}"] = sum(1 for p in daleko_a if any(cheb(p, q) <= r for q in daleko_b))
        wynik[f"poludnie_blisko_{r}"] = sum(1 for q in daleko_b if any(cheb(p, q) <= r for p in daleko_a))
    return wynik


def kryterium(pom):
    """(ok, opis): wspólnych poza lądowaniem 0 i wspólnych ogółem <= WSPOLNE_MAX."""
    ok = not pom["wspolne_poza"] and len(pom["wspolne"]) <= WSPOLNE_MAX
    return ok, f"wspólne {len(pom['wspolne'])} (limit {WSPOLNE_MAX}), poza lądowaniem (Chebyshev > {LAD_PROMIEN}) {len(pom['wspolne_poza'])}: {pom['wspolne_poza'][:6]}"


def drukuj_pomiar(nazwa, pom):
    print(f"[{nazwa}] wspólne pola {len(pom['wspolne'])} ({100 * pom['udzial_polnoc']:.0f}% północnej, {100 * pom['udzial_poludnie']:.0f}% południowej): {pom['wspolne'][:12]}"
          f"{' ...' if len(pom['wspolne']) > 12 else ''}")
    print(f"[{nazwa}] wspólne odcinki (pierwszy, ostatni, długość): {pom['odcinki'][:8]}{' ...' if len(pom['odcinki']) > 8 else ''}")
    print(f"[{nazwa}] poza lądowaniem: wspólne {len(pom['wspolne_poza'])}; punkty północnej w Chebyshev <=1/<=2/<=3 od południowej: "
          f"{pom['polnoc_blisko_1']}/{pom['polnoc_blisko_2']}/{pom['polnoc_blisko_3']}; punkty południowej od północnej: "
          f"{pom['poludnie_blisko_1']}/{pom['poludnie_blisko_2']}/{pom['poludnie_blisko_3']} (bez punktów w promieniu {LAD_PROMIEN_BLISKO} od lądowania)")


def wczytaj_stare(m, comp9, zle9):
    """Stare N/S z PLIKÓW (trasy/*_petla.json i dane_tibia/mapy/*.json): {w: {pelna, przyst, potw, gardla}}; wąskie gardła liczone dziś na bieżącej składowej/ścianach."""
    stare = {}
    for w in WARIANTY:
        n = f"{NS.NAZWA}_{w}"
        pelna = [(p[0], p[1]) for p in json.loads((ROOT / "trasy" / f"{n}_petla.json").read_text())]
        pr = [t for t in json.loads((ROOT / "dane_tibia" / "mapy" / f"{n}.json").read_text())["przystanki"] if "potworow" in t]
        stare[w] = {"pelna": pelna, "przyst": len(pr), "potw": sum(t["potworow"] for t in pr), "gardla": Z.waskie_gardla(m, comp9, zle9, pelna, 9)}
    return stare


def tabela(m, out, stare):
    print(f"{'wariant':22s} {'pola':>6s} {'przyst.':>8s} {'potwory':>8s} {'pola/potw.':>11s} {'waskie gardla':>14s}")
    for w in WARIANTY:
        s = stare[w]
        print(f"{'stara ' + w:22s} {len(s['pelna']):6d} {s['przyst']:8d} {s['potw']:8d} {len(s['pelna']) / s['potw']:11.1f} {len(s['gardla']):14d}")
    for w in WARIANTY:
        o = out[w]
        n = sum(t["n"] for t in o["st"])
        print(f"{nazwa_wariantu(w)[len(NS.NAZWA) + 1:]:22s} {len(o['pelna']):6d} {len(o['st']):8d} {n:8d} {len(o['pelna']) / n:11.1f} {len(o['gardla']):14d}")


def koszty_przystankow(m, out):
    """Informacyjnie: o ile pól skraca cykl pominięcie każdego przystanku (reguła kosztu: > 25% i <= 2 potwory = pomijany)."""
    for w in WARIANTY:
        o = out[w]
        wez = [tuple(o["L"][:2])] + [t["pt"] for t in o["st"]]
        D = Z.macierz_drog(m, 9, wez, o["sciana"])
        pelny = NS._cykl(D, range(1, len(wez)))
        zysk = [(t["pt"], t["n"], pelny - NS._cykl(D, [j for j in range(1, len(wez)) if j != i]), round(100.0 * (pelny - NS._cykl(D, [j for j in range(1, len(wez)) if j != i])) / pelny))
                for i, t in enumerate(o["st"], 1)]
        print(f"{nazwa_wariantu(w)}: koszt przystanków (pt, potw., pól cyklu, % cyklu {pelny}): {zysk}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    ap.add_argument("--bez-ognia", default="", help="TYLKO informacyjnie: pola ognia 'x,y,z;x,y,z' pomijane w obliczeniu (nie łączy się z --zapisz)")
    a = ap.parse_args(argv)
    if a.bez_ognia and a.zapisz:
        raise SystemExit("--bez-ognia jest tylko informacyjne: nie łączy się z --zapisz")
    if a.bez_ognia:
        bez = {tuple(int(v) for v in s.split(",")) for s in a.bez_ognia.split(";") if s.strip()}
        orig = Z.ogien_surowy
        Z.ogien_surowy = lambda: orig() - bez
        print(f"INFO: ogień bez pól {sorted(bez)} (TYLKO informacyjnie)")
    print(f"pliki ognia/dziur (sha1, 12 znaków): {sha1_ognia()}")
    m = _mapa.Mapa()
    out = zbuduj_v2(m)
    pom = pomiar(out["polnoc"]["pelna"], out["poludnie"]["pelna"])
    drukuj_pomiar("v2", pom)
    koszty_przystankow(m, out)
    stare = wczytaj_stare(m, out["polnoc"]["comp"], out["polnoc"]["zle"])
    pom_s = pomiar(stare["polnoc"]["pelna"], stare["poludnie"]["pelna"])
    drukuj_pomiar("stare N/S z plików", pom_s)
    tabela(m, out, stare)
    ok, opis = kryterium(pom)
    print(("KRYTERIUM ROZŁĄCZNOŚCI SPEŁNIONE: " if ok else "KRYTERIUM ROZŁĄCZNOŚCI NIESPEŁNIONE: ") + opis)
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    if not ok:
        raise SystemExit("kryterium rozłączności niespełnione: nic nie zapisano")
    for w, o in out.items():
        spot_lib.zapis_spotu(m, nazwa_wariantu(w), 9, o["pelna"], o["order"], o["nodes"], o["st"], f"Ab'Dendriel zachod z9 {w} v2",
                             jedn="potw.", opis_przyst="spawn(y) trolli")
    print("zapisano trasy/abdendriel_zachod_z9_{polnoc,poludnie}_v2_petla.json i dane_tibia/mapy/abdendriel_zachod_z9_{polnoc,poludnie}_v2.{png,json}; mapy.json osobno")


if __name__ == "__main__":
    main()
