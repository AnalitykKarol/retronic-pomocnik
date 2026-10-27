#!/usr/bin/env python3
"""Edron, główna jaskinia trolli z8: pętla `edron_trolle_petla` bez pól w sąsiedztwie zejść na z9 (26.10).

  python3 -I generuj_petle_edron_z8_bez_zejscia.py [--zapisz]     bez --zapisz tylko liczy i drukuje

PRZYCZYNA (26.10 08:24:07, Odchyd): pętla nagrana 15.10 mijała zejście (33081,31742,z8) o jedno pole (punkt 98 = (33082,31741)),
walka z uciekającym trollem toczyła się tuż przy nim, a klient w trybie ataku sam poszedł za celem i wszedł w zejście
(na z9 zachodnia jaskinia). Pętla nie leży NA zejściu, więc nic się nie waliło w walidacji; zabrakło bufora.

CO ROBI: zejścia z8 = pola flagi 2 w kolorze 210 w obszarze jaskini + nauczone dziury (trasy/dziury_nauczone.json) i ręczne
(trasy/dziury_omijaj.json) z piętra 8. Punkt pętli w Chebyshevie <= BUFOR od zejścia wylatuje, a luka jest łatana drogą A*
(zejścia z buforem i znany ogień z buforem 1 = ściany). Potem każda para sąsiednich punktów, której droga A* bota (strzałki
i skosy) wchodzi w bufor, dostaje punkt pośredni z drogi omijającej. Reszta pętli (przystanki przy spawnach) zostaje bit w bit.
Idempotentne: na pętli bez naruszeń nic nie zmienia. Nic nie wysyła do gry.

Zapis (--zapisz): kopia `trasy/edron_trolle_petla.{json,meta}.bak-20261026-edron-z8-zejscie` (tylko gdy jeszcze jej nie ma),
potem zapis atomowy (trasa_io.zapisz); meta (`specjalne.idx`) przenumerowane o usunięte punkty.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import mapa as _mapa  # noqa: E402
import trasa_io  # noqa: E402

NAZWA = "edron_trolle_petla"
TAG = "bak-20261026-edron-z8-zejscie"
Z = 8
OBSZAR = (33040, 31700, 33135, 31790)   # jaskinia trolli z8 (składowa z8#1); smoki na północy (y < 31700) poza obszarem
BUFOR = 1                               # pole zejścia i jego sąsiedzi (Chebyshev <= 1) = zakaz dla punktów pętli
OGIEN_BUFOR = 1                         # znany ogień + sąsiedzi = ściana dla NOWYCH punktów (istniejące zostają)
KOPIA = TAG


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def w_obszarze(x, y):
    return OBSZAR[0] <= x <= OBSZAR[2] and OBSZAR[1] <= y <= OBSZAR[3]


def zejscia(m):
    """Zejścia z8 -> z9 w obszarze jaskini: (kolor 210 + flaga 2 + nie ściana) + nauczone i ręczne dziury z piętra 8."""
    wyn = set()
    for x in range(OBSZAR[0], OBSZAR[2] + 1):
        for y in range(OBSZAR[1], OBSZAR[3] + 1):
            f = m.flagi(x, y, Z)
            if f & _mapa.WIDZIANE and f & _mapa.BEZ_DROGI and not f & _mapa.SCIANA and m.pole(x, y, Z)[1] == _mapa.KOLOR_SCHODOW:
                wyn.add((x, y))
    for plik in ("dziury_nauczone.json", "dziury_omijaj.json"):
        try:
            d = json.loads((ROOT / "trasy" / plik).read_text()).get("dziury", [])
        except (OSError, ValueError):
            continue
        wyn |= {(int(e[0]), int(e[1])) for e in d if int(e[2]) == Z and w_obszarze(int(e[0]), int(e[1]))}
    return sorted(wyn)


def ogien_z8():
    """Znane pola ognia z8 (ogien_stale + epizody z potwierdzonym parzeniem) jako zbiór (x, y)."""
    wyn = set()
    try:
        wyn |= {(p[0], p[1]) for p in json.loads((ROOT / "trasy" / "ogien_stale.json").read_text()).get("pola", []) if p[2] == Z}
    except (OSError, ValueError):
        pass
    try:
        for k in json.loads((ROOT / "trasy" / "ogien_epizody.json").read_text()):
            if isinstance(k, str) and k.count(",") == 2:
                x, y, z = (int(v) for v in k.split(","))
                if z == Z:
                    wyn.add((x, y))
    except (OSError, ValueError):
        pass
    return wyn


def strefa(pola, bufor):
    return {(x + dx, y + dy) for x, y in pola for dx in range(-bufor, bufor + 1) for dy in range(-bufor, bufor + 1)}


def poprawiona(m, punkty, log=print):
    """(nowe punkty, indeksy usuniętych, wstawione punkty pośrednie). Punkty spoza z8 i spoza obszaru nietknięte."""
    zej = zejscia(m)
    zakaz = strefa(zej, BUFOR)
    sciany = [(x, y, Z) for (x, y) in zakaz | strefa(ogien_z8(), OGIEN_BUFOR)]
    bad = [i for i, p in enumerate(punkty) if p[2] == Z and (p[0], p[1]) in zakaz]
    log(f"zejścia z8: {zej}")
    log(f"punkty pętli w buforze {BUFOR} od zejścia: {[(i, punkty[i][:2]) for i in bad]}")
    usuniete = set(bad)

    def droga(a, b, skosy):
        blok = [s for s in sciany if s[:2] not in (tuple(a[:2]), tuple(b[:2]))]
        return m.droga((a[0], a[1], Z), (b[0], b[1]), blok, 0, skosy, limit=20000)

    # luki po usuniętych punktach łatamy drogą A* po osiach (zejścia z buforem i ogień z buforem = ściany): punkt pośredni
    # w osi zamyka remis skosu, w którym bot mógłby wybrać pole przy zejściu (np. gdy inne pole zajmie potwór)
    kept, wstaw = [], []
    i = 0
    while i < len(punkty):
        if i not in usuniete:
            kept.append(punkty[i])
            i += 1
            continue
        j = i
        while j in usuniete:
            j += 1
        prev = kept[-1] if kept else None
        nxt = punkty[j] if j < len(punkty) else None
        if prev is not None and nxt is not None and prev[2] == Z and nxt[2] == Z:
            obj = droga(prev, nxt, False)
            if obj is None:
                raise SystemExit(f"brak drogi omijającej bufor między {prev} i {nxt}")
            pos = [tuple(c[:3]) for c in obj if tuple(c[:2]) != tuple(nxt[:2])]
            kept.extend(pos)
            wstaw.extend(pos)
            log(f"luka {prev[:2]} -> {nxt[:2]} po usuniętych {sorted(usuniete & set(range(i, j)))}: droga omijająca, +{len(pos)} pkt {[p[:2] for p in pos]}")
        i = j

    # pary sąsiednich punktów (z zawinięciem): droga A* bota nie może wchodzić w bufor
    wynik = []
    n = len(kept)
    for i, a in enumerate(kept):
        wynik.append(a)
        b = kept[(i + 1) % n]
        if a[2] != Z or b[2] != Z:
            continue
        zle = False
        for skosy in (False, True):
            d = m.droga((a[0], a[1], Z), (b[0], b[1]), [], 0, skosy, limit=20000)
            if d is None:
                continue
            if any((c[0], c[1]) in zakaz and (c[0], c[1]) not in (tuple(a[:2]), tuple(b[:2])) for c in d):
                zle = True
        if not zle:
            continue
        obj = droga(a, b, False)
        if obj is None:
            raise SystemExit(f"brak drogi omijającej bufor między {a} i {b}")
        pos = [tuple(c[:3]) for c in obj if tuple(c[:2]) != tuple(b[:2])]
        wynik.extend(pos)
        wstaw.extend(pos)
        log(f"para {a[:2]} -> {b[:2]}: droga A* wchodziła w bufor, dodano {len(pos)} pkt pośrednich: {[p[:2] for p in pos]}")
    return wynik, sorted(usuniete), wstaw


def przenumeruj_meta(meta, usuniete):
    wyn = []
    us = sorted(usuniete)
    for e in meta:
        e = dict(e)
        i = int(e["idx"])
        e["idx"] = max(0, i - sum(1 for u in us if u < i))
        wyn.append(e)
    return wyn


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true", help="zapisz trasy/edron_trolle_petla.json (+ kopia)")
    a = ap.parse_args(argv)
    m = _mapa.Mapa()
    punkty, meta = trasa_io.wczytaj(NAZWA)
    nowe, usuniete, wstaw = poprawiona(m, punkty)
    print(f"pętla {NAZWA}: {len(punkty)} -> {len(nowe)} pkt (usunięte {len(usuniete)}, dodane {len(wstaw)})")
    if not usuniete and not wstaw:
        print("bez zmian: pętla nie ma punktów ani dróg w buforze zejść")
        return 0
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return 0
    plik = trasa_io.sciezka(NAZWA)
    for p in (plik, trasa_io.meta_sciezka(plik)):
        kopia = p.with_name(p.name + "." + KOPIA)
        if p.exists() and not kopia.exists():
            shutil.copy2(p, kopia)
            print(f"kopia {kopia.name}")
    trasa_io.zapisz(NAZWA, nowe, przenumeruj_meta(meta, usuniete))
    print(f"zapisano {plik}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
