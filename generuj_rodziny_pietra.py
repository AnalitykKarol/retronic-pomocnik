#!/usr/bin/env python3
"""Rodziny spotów (26.10, Karol: „stworzyć wszystkie możliwe mapy tej samej jaskini na różnych piętrach”): mapy BRAKUJĄCYCH pięter
jaskiń, w których już mamy spot. Jeden generator na kilka map (specyfikacje w SPECY), metoda jak generuj_trasy_edron_z9z.py:
składowa mapy -> przystanki ze spawnów celu -> pętla (NN + 2-opt po A*) -> dojście = ISTNIEJĄCA trasa bazowa + przejścia pięter
omijające ogień i nauczone dziury. Nic nie wysyła do gry (tylko odczyt mapy klienta i zapis plików w repo):

  python3 -I generuj_rodziny_pietra.py [--zapisz] [mapa ...]        bez --zapisz tylko liczy i drukuje podsumowanie

Powstają (przy --zapisz), w trasy/ i dane_tibia/mapy/ (nazwa pliku = pole `plik` specyfikacji):
  <plik>_petla, <plik>_dojscie(.meta), <plik>.png, <plik>.json

Progi (wartości robocze do oceny Karola, NIE jego ustalenia): spot = składowa z >= PROG_CEL potworów celu i pętlą >= PROG_PETLA pól;
mniejsza = doczepka do sąsiedniego spotu (reguła z procedury, krok 1). Pokrycie: w małych składowych (potwory skupione w kącie)
pętla po samych spawnach ma kilkadziesiąt pól, więc generator dodaje przystanki pokrycia (n = 0), aż każde pole składowej leży
w <= `pokrycie` polach (Chebyshev) od jakiegoś przystanku.

Dlaczego nowe pliki `trolle_edron_z10w_pelna_*`, a nie nadpisanie `trolle_edron_z10w_*` z generuj_trasy_edron_wschod.py: ten generator ma
zamrożoną kopię w testy/dane_f0_baza/ (test_spot_lib_regresja, bajt w bajt), więc go nie ruszamy; jego dojście z10w schodziło
przez (33127,31726,z9), czyli PRZESZKODĘ (kolor podłogi, flaga 2; zejście to (33128,31729) kolor 210), a pętla miała 35 pól.
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import mapa as _mapa  # noqa: E402
import spot_lib  # noqa: E402
import trasa_io  # noqa: E402
from spot_lib import chodliwe, ladowanie, petla, przystanki, skladowa  # noqa: E402

PROG_CEL = 10          # minimum potworów celu w składowej (Karol 26.10: „>= ~10”)
PROG_PETLA = 60        # minimum pól pętli (Karol 26.10: „>= ~60”)
OGIEN_BUFOR = 1
GROZNY_CIOS = 50       # potwór z atak_max_szac powyżej tego w pobliżu pętli = ostrzeżenie (jak --max-cios w spoty_skladowe)
GROZNY_ODL = 12        # „w pobliżu” = w tylu polach (Chebyshev) od któregoś punktu pętli, to samo piętro

TROLLE = ("troll", "bear", "swamp troll", "frost troll")

# plik = rdzeń nazwy plików; mapa = klucz w mapy.json; baza = istniejąca trasa dojścia, od której zaczynamy (jej koniec = piętro startu);
# hops = [(pole przejścia T (x, y, z) na piętrze z, pole wewnątrz składowej piętra z+1)] po kolei; cel = pole składowej docelowej
# (ostatni hop); potwory = nazwy spawnów celu (potwory_pelne.json); obszar = (x1, x2, y1, y2) spawnów albo None.
SPECY = {
    "trolle_edron_z10w": {
        "plik": "trolle_edron_z10w_pelna", "z": 10, "baza": "trolle_edron_z9w_dojscie", "potwory": TROLLE,
        "hops": [((33128, 31729, 9), (33129, 31727, 10))],
        "obszar": None, "pokrycie": 5, "tytul": "trolle z10 wschod"},
    "gobliny_edron_z10_zachod": {
        "plik": "gobliny_edron_z10_zachod", "z": 10, "baza": "gobliny_edron_z9_dojscie", "potwory": ("goblin", "wasp"),
        "hops": [((33063, 31822, 9), (33064, 31816, 10))],
        "obszar": None, "pokrycie": 5, "tytul": "gobliny z10 zachod"},
    "gobliny_edron_z10_wschod": {
        "plik": "gobliny_edron_z10_wschod", "z": 10, "baza": "gobliny_edron_z9_dojscie", "potwory": ("goblin", "wasp"),
        "hops": [((33102, 31822, 9), (33105, 31808, 10))],
        "obszar": None, "pokrycie": 5, "tytul": "gobliny z10 wschod"},
    "gobliny_edron_z10_poludnie": {
        "plik": "gobliny_edron_z10_poludnie", "z": 10, "baza": "gobliny_edron_z9_dojscie", "potwory": ("goblin", "wasp"),
        "hops": [((33069, 31848, 9), (33070, 31850, 10))],
        "obszar": None, "pokrycie": 5, "tytul": "gobliny z10 poludnie"},
    "rook_raty_z10_zachod": {
        "plik": "rook_raty_z10_zachod", "z": 10, "baza": "rook_raty_z9_dojscie", "potwory": ("rat", "cave rat"),
        "hops": [((32021, 32180, 9), (32020, 32178, 10))],
        "obszar": None, "pokrycie": 5, "tytul": "szczury z10 zachod"},
}


def ogien_pola():
    """Znany ogień (stały + epizody bota, oba formaty) z buforem OGIEN_BUFOR -> zbiór (x, y, z)."""
    pola = {tuple(p[:3]) for p in json.loads((ROOT / "trasy" / "ogien_stale.json").read_text()).get("pola", [])}
    try:
        ep = json.loads((ROOT / "trasy" / "ogien_epizody.json").read_text())
    except (OSError, ValueError):
        ep = {}
    ep = ep.get("pola", ep) if isinstance(ep, dict) else {}
    if isinstance(ep, dict):
        for k in ep:
            if isinstance(k, str) and k.count(",") == 2:
                pola.add(tuple(int(a) for a in k.split(",")))
    elif isinstance(ep, list):
        pola |= {tuple(x[:3]) for x in ep}
    b = OGIEN_BUFOR
    return {(x + dx, y + dy, z) for x, y, z in pola for dx in range(-b, b + 1) for dy in range(-b, b + 1)}


def droga_z_omijaniem(m, start, T, sciana):
    """(pole obok T, droga A* ze `start` bez startu, z polem obok) po piętrze T[2], omijająca `sciana` (jak w generuj_trasy_edron_z9z.py)."""
    zle = {(p[0], p[1]) for p in sciana if p[2] == T[2]}
    best = None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            c = (T[0] + dx, T[1] + dy)
            if (dx or dy) and chodliwe(m, (c[0], c[1], T[2])) and c not in zle:
                d = [] if (c[0], c[1]) == (start[0], start[1]) else m.droga(start, c, zajete=sorted(sciana), dlugosc=0, limit=800000)
                if d is None:
                    continue
                d = [(p[0], p[1]) for p in d]
                if best is None or len(d) < len(best[1]):
                    best = (c, d)
    return best


def dopisz_pokrycie(m, comp, stops, start, promien, zajete):
    """Dopisuje przystanki pokrycia (n = 0): kolejno najdalsze pole składowej od wszystkich dotychczasowych punktów (start + przystanki), dopóki
    któreś pole jest dalej niż `promien` (Chebyshev). Pole musi mieć drogę A* (zajete = ściana) z startu. Zwraca nową listę przystanków."""
    pts = [tuple(start)] + [t["pt"] for t in stops]
    out = list(stops)
    pol = sorted(comp)
    for _ in range(40):
        daleko = max(pol, key=lambda c: (min(max(abs(c[0] - p[0]), abs(c[1] - p[1])) for p in pts), c))
        if min(max(abs(daleko[0] - p[0]), abs(daleko[1] - p[1])) for p in pts) <= promien:
            break
        out.append({"pt": daleko, "n": 0, "spawny": 0})
        pts.append(daleko)
    return out


def groznicy(z, pelna, obszar_szukania=GROZNY_ODL):
    """Groźni (atak_max_szac > GROZNY_CIOS) potwory ze spawnów na piętrze z w <= GROZNY_ODL polach od punktu pętli -> [(nazwa, x, y, odl)]."""
    cios = {v["nazwa"]: v.get("atak_max_szac") or 0 for v in json.loads((ROOT / "dane_tibia" / "potwory.json").read_text())["potwory"]}
    wyn = []
    for mo in json.loads(spot_lib.SPAWNY.read_text())["potwory"]:
        if cios.get(mo["nazwa"], 0) <= GROZNY_CIOS:
            continue
        for s in mo.get("spawny", []):
            if s["z"] != z:
                continue
            odl = min(max(abs(s["x"] - p[0]), abs(s["y"] - p[1])) for p in pelna)
            if odl <= obszar_szukania:
                wyn.append((mo["nazwa"], s["x"], s["y"], odl))
    return sorted(wyn, key=lambda t: t[3])


def zbuduj(nazwa_mapy, spec, m=None):
    """-> dict z wynikiem (pętla, dojście, meta, liczby, ostrzeżenia). Rzuca SystemExit z powodem, gdy spot nie da się zbudować."""
    m = m or _mapa.Mapa()
    dz = [tuple(p) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])]
    ogien = ogien_pola()
    sciana = lambda z: [p for p in dz if p[2] == z] + sorted(p for p in ogien if p[2] == z)   # noqa: E731
    z_cel = spec["z"]
    baza, meta_baza = trasa_io.wczytaj(spec["baza"])
    S = baza[-1]
    if S in ogien:
        raise SystemExit(f"{nazwa_mapy}: koniec trasy bazowej {spec['baza']} {S} w ogniu/buforze")
    doj, meta = list(baza), [dict(e) for e in meta_baza]
    ostrz, opisy = [], []
    L = S
    for i, (T, seed) in enumerate(spec["hops"]):
        if T[2] != L[2]:
            raise SystemExit(f"{nazwa_mapy}: hop {T} jest na z{T[2]}, a trasa jest na z{L[2]}")
        f = m.flagi(*T)
        if not f & _mapa.WIDZIANE or not f & _mapa.BEZ_DROGI:
            raise SystemExit(f"{nazwa_mapy}: {T} nie jest przejściem w mapie")
        if spot_lib.przeszkoda_na_podlodze(m, *T):
            raise SystemExit(f"{nazwa_mapy}: {T} to PRZESZKODA (kolor podłogi), nie przejście")
        if T in ogien:
            raise SystemExit(f"{nazwa_mapy}: przejście {T} w ogniu/buforze")
        kolor = m.pole(*T)[1]
        nastepne = T[2] + 1
        comp = skladowa(m, (seed[0], seed[1], nastepne), sciana(nastepne))
        if (seed[0], seed[1]) not in comp:
            raise SystemExit(f"{nazwa_mapy}: punkt {seed} nie leży w chodliwej składowej piętra z{nastepne}")
        wyj = ladowanie(m, T, comp)
        if (wyj[0], wyj[1], wyj[2]) in ogien:
            raise SystemExit(f"{nazwa_mapy}: lądowanie {wyj} w ogniu/buforze")
        r = droga_z_omijaniem(m, L, T, sciana(T[2]))
        if r is None:
            raise SystemExit(f"{nazwa_mapy}: brak drogi z {L[:2]} do przejścia {T[:2]} z omijaniem ognia (z{T[2]})")
        przed, d = r
        doj += [(x, y, T[2]) for x, y in d] + [T, wyj]
        meta += [{"idx": len(doj) - 2, "typ": "przed_zmiana_pietra",
                  "komentarz": f"przejście z{T[2]} {T[:2]} (kolor {kolor}, flaga 2, z mapy 26.10; rodzina pięter) do składowej z{nastepne} ({len(comp)} pól); "
                               f"typ NIEZWERYFIKOWANY na żywo, droga omija znany ogień (bufor {OGIEN_BUFOR})"},
                 {"idx": len(doj) - 1, "typ": "schody_w_dol",
                  "komentarz": f"lądowanie z{nastepne} {wyj[:2]}" + (f"; dalej A* po z{nastepne} do przejścia" if i + 1 < len(spec["hops"]) else
                                                                    f"; po zejściu wejdź w pętlę {spec['plik']}_petla")}]
        opisy.append(f"z{T[2]}->z{nastepne} {T[:2]} kolor {kolor}: {len(d)} pól dojścia, lądowanie {wyj[:2]}, składowa {len(comp)} pól")
        L = wyj
    comp_cel = skladowa(m, (L[0], L[1], z_cel), sciana(z_cel))
    spawny = spot_lib.spawny(z_cel, spec["potwory"], spec.get("obszar"))
    st = przystanki(spawny, comp_cel)
    cel_n = sum(t["n"] for t in st)
    if not st:
        raise SystemExit(f"{nazwa_mapy}: brak przystanków (spawnów celu) w składowej {len(comp_cel)} pól")
    if spec.get("pokrycie"):
        st = dopisz_pokrycie(m, comp_cel, st, L[:2], spec["pokrycie"], sciana(z_cel))
    order, nodes, pelna = petla(m, z_cel, L[:2], st, sciana(z_cel))
    for p in pelna:
        if (p[0], p[1], z_cel) in ogien:
            raise SystemExit(f"{nazwa_mapy}: punkt pętli {p} w ogniu/buforze")
    gr = groznicy(z_cel, pelna)
    if cel_n < PROG_CEL:
        ostrz.append(f"potworów celu {cel_n} < {PROG_CEL}: doczepka, nie osobny spot")
    if len(pelna) < PROG_PETLA:
        ostrz.append(f"pętla {len(pelna)} pól < {PROG_PETLA}")
    if gr:
        ostrz.append("groźni w pobliżu pętli: " + "; ".join(f"{n} ({x},{y}) odl {o}" for n, x, y, o in gr[:5]))
    return {"m": m, "z": z_cel, "comp": comp_cel, "stops": st, "order": order, "nodes": nodes, "pelna": pelna, "doj": doj, "meta": meta,
            "cel_n": cel_n, "przystankow_celu": sum(1 for t in st if t["n"]), "pokrycia": sum(1 for t in st if not t["n"]),
            "opisy": opisy, "ostrz": ostrz, "ladowanie": L}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    ap.add_argument("mapy", nargs="*", help=f"które z: {', '.join(SPECY)} (domyślnie wszystkie)")
    a = ap.parse_args(argv)
    wybrane = a.mapy or list(SPECY)
    bledne = [n for n in wybrane if n not in SPECY]
    if bledne:
        ap.error(f"nieznane mapy: {bledne}")
    m = _mapa.Mapa()
    wyniki = {}
    for nazwa in wybrane:
        try:
            w = zbuduj(nazwa, SPECY[nazwa], m)
        except SystemExit as e:
            print(f"{nazwa}: NIE DA SIĘ: {e}")
            continue
        wyniki[nazwa] = w
        print(f"{nazwa}: składowa {len(w['comp'])} pól, potworów celu {w['cel_n']} w {w['przystankow_celu']} przystankach (+{w['pokrycia']} pokrycia), "
              f"pętla {len(w['pelna'])} pól, dojście {len(w['doj'])} pkt (baza {SPECY[nazwa]['baza']}), lądowanie {w['ladowanie']}")
        for o in w["opisy"]:
            print("   przejście", o)
        for o in w["ostrz"]:
            print("   UWAGA", o)
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    for nazwa, w in wyniki.items():
        spec = SPECY[nazwa]
        spot_lib.zapis_spotu(w["m"], spec["plik"], w["z"], w["pelna"], w["order"], w["nodes"], w["stops"], spec["tytul"], jedn="potw.",
                             opis_przyst="spawn(y) celu / pokrycie (0)", doj=w["doj"], meta=w["meta"])
    print("zapisano trasy/ i dane_tibia/mapy/ (wpisy mapy.json i spoty_nadzorca.json dodaj osobno)")


if __name__ == "__main__":
    main()
