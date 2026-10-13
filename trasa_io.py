"""Wspólne wczytywanie/zapis tras dla narzędzi nagrywania (nagraj_trase, przytnij, odwroc, waliduj).

Trasa: trasy/<nazwa>.json = lista [x, y, z] (format cavebota).
Opisy punktów specjalnych (schody, teleport) leżą obok: trasy/<nazwa>.meta
(osobne rozszerzenie, żeby cavebot i mozg.py nie brały ich za trasy):
  {"specjalne": [{"idx": 12, "typ": "schody_w_gore", "komentarz": "..."}]}
"""
import json
import os
from pathlib import Path

KATALOG = Path(__file__).resolve().parent
TRASY = KATALOG / "trasy"


def sciezka(nazwa, katalog=None):
    nazwa = str(nazwa)
    if nazwa.endswith(".json"):
        nazwa = nazwa[:-5]
    if not nazwa or "/" in nazwa or nazwa.startswith("."):
        raise ValueError(f"zła nazwa trasy: {nazwa!r}")
    return Path(katalog or TRASY) / f"{nazwa}.json"


def meta_sciezka(plik):
    return Path(plik).with_suffix(".meta")


def zapisz_atomowo(plik, tekst):
    plik = Path(plik)
    tmp = plik.with_name(plik.name + ".tmp")
    tmp.write_text(tekst)
    os.replace(tmp, plik)


def wczytaj(nazwa, katalog=None):
    plik = sciezka(nazwa, katalog)
    punkty = [tuple(int(v) for v in p) for p in json.loads(plik.read_text())]
    meta = []
    try:
        meta = json.loads(meta_sciezka(plik).read_text()).get("specjalne", [])
    except (OSError, ValueError):
        pass
    return punkty, meta


def zapisz(nazwa, punkty, meta=(), katalog=None):
    plik = sciezka(nazwa, katalog)
    plik.parent.mkdir(exist_ok=True)
    zapisz_atomowo(plik, json.dumps([list(p) for p in punkty]))
    mp = meta_sciezka(plik)
    if meta:
        zapisz_atomowo(mp, json.dumps({"specjalne": list(meta)}, ensure_ascii=False, indent=1))
    elif mp.exists():
        mp.unlink()
    return plik


def dlugosc(punkty):
    """Długość trasy w polach (krok = max(|dx|,|dy|), skoki między piętrami liczone 0)."""
    return sum(max(abs(a[0] - b[0]), abs(a[1] - b[1]))
               for a, b in zip(punkty, punkty[1:]) if a[2] == b[2])


def podsumowanie(punkty):
    if not punkty:
        return "pusta trasa"
    xs, ys, zs = [p[0] for p in punkty], [p[1] for p in punkty], sorted({p[2] for p in punkty})
    return (f"{len(punkty)} punktów, długość {dlugosc(punkty)} pól, piętra {zs}, "
            f"x {min(xs)}..{max(xs)}, y {min(ys)}..{max(ys)}")
