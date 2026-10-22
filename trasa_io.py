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


def uprosc_petle(punkty, prog=1):
    """Trasa nagrana z cofaniem/objazdem (wyjście i powrót tą samą drogą, A* dopisany na początku): usuwa pętle.
    Dla każdego punktu skacze do ostatniego późniejszego punktu na TYM SAMYM piętrze (cały odcinek na jednym
    piętrze), który leży najwyżej `prog` pól od niego (Chebyshev). Punkty zmiany piętra i ich sąsiedzi nie znikają
    (skok nie przekracza zmiany piętra). Zwraca nową listę krotek (x, y, z)."""
    p = [tuple(int(v) for v in q) for q in punkty]
    wynik, i, n = [], 0, len(p)
    while i < n:
        wynik.append(p[i])
        j = i
        for k in range(i + 1, n):
            if p[k][2] != p[i][2]:
                break                      # dalej inne piętro: nic za tą granicą nie jest "tym samym odcinkiem"
            if max(abs(p[k][0] - p[i][0]), abs(p[k][1] - p[i][1])) <= prog:
                j = k
        i = j if j > i + 1 else i + 1      # j == i + 1: zwykły krok; j > i + 1: pętla do p[j] wycięta
    return wynik


def _sciana_mapy(mapa, p):
    """True, gdy mapa widziała pole i uważa je za nieprzechodnie (ściana/woda)."""
    try:
        return bool(mapa.flagi(*p) & 1) and mapa.przechodnie(*p) is False
    except Exception:
        return False


def drzwi_na_trasie(punkty, mapa):
    """22.10: zamknięte drzwi na nagranej trasie (kierunek marszu = kolejność punktów).
    Drzwi to pole trasy, które mapa uważa za ścianę: nagrany punkt (jak wypad.drzwi_z_mapy) ALBO pole pośrednie na prostym
    odcinku między dwoma kolejnymi punktami tego samego piętra (nagranie bywa rzadkie: Edron (33166,31817,z7) leży między
    punktami (33166,31816) i (33166,31820), więc dotąd żaden mechanizm drzwi o nim nie wiedział).
    Zwraca listę {"pole","wejscie","wyjscie","kier","po"} w kolejności trasy: `wejscie` = pole obok drzwi przed nimi,
    `wyjscie` po drugiej stronie, `kier` = (dx, dy) marszu, `po` = indeks pierwszego punktu trasy NA drzwiach albo za nimi.
    Odcinki po skosie i drzwi bez jednoznacznego kierunku w osi są pomijane. Brak mapy = pusta lista."""
    wynik = []
    if mapa is None:
        return wynik
    pts = [(int(p[0]), int(p[1]), int(p[2])) for p in punkty]
    widziane = set()

    def dodaj(pole, kier, po):
        if pole in widziane or not kier or (kier[0] and kier[1]):
            return
        widziane.add(pole)
        z = pole[2]
        wynik.append({"pole": pole, "kier": kier, "po": po,
                      "wejscie": (pole[0] - kier[0], pole[1] - kier[1], z),
                      "wyjscie": (pole[0] + kier[0], pole[1] + kier[1], z)})

    for i in range(1, len(pts)):
        a, b = pts[i - 1], pts[i]
        if a[2] != b[2] or a[:2] == b[:2]:
            continue
        dx, dy = (b[0] > a[0]) - (b[0] < a[0]), (b[1] > a[1]) - (b[1] < a[1])
        if dx and dy:
            continue                    # skos: kierunek wejścia w drzwi niejednoznaczny
        x, y = a[0], a[1]
        while (x, y) != (b[0], b[1]):
            x, y = x + dx, y + dy
            if _sciana_mapy(mapa, (x, y, a[2])):
                dodaj((x, y, a[2]), (dx, dy), i)
    return wynik
