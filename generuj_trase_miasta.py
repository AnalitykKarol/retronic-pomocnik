#!/usr/bin/env python3
"""Generator tras wypadu do miasta (do_miasta / z_miasta) z pełnej mapy (mapa.py) i nagranych tras łowiska.

  generuj_trase_miasta.py troll    [--zapisz]   troll_cave (z8/z9) -> Thais, sklep Gorna (z7) i z powrotem
  generuj_trase_miasta.py troll_v2 [--zapisz]   25.10: KRÓTSZE do_miasta z jaskini trolli (patrz niżej); zapis tylko trasy/troll_do_miasta_v2.json/.meta
  generuj_trase_miasta.py kanaly   [--zapisz]   kanały Thais (z8, lądowanie dziury (32360,32242)) -> Gorn i z powrotem
  generuj_trase_miasta.py thais_pn [--zapisz]   Thais północ, jaskinia trolli z8 (odwrócone thais_pn_z8_dojscie) -> Gorn i z powrotem

Bez --zapisz tylko raport (długości, przejścia). Zapisuje trasy/<prefiks>_do_miasta.json, <prefiks>_z_miasta.json
(listy punktów x,y,z jak każda trasa) i .meta z przejściami pięter.

Model przejść (potwierdzony na nagraniach do_miasta/z_miasta/troll_cave i w pietra.py):
  w dół:  krok na pole T (flaga mapy 2 = "bez drogi") na piętrze z, lądowanie (T.x, T.y, z+1);
  w górę: z pola obok R (albo z samego R) na piętrze z, gdzie nad R (piętro z-1) jest dziura (flaga 2):
          drabina/lina na R, lądowanie (R.x, R.y+1, z-1).
Trasa troll_do_miasta zaczyna się od ODWRÓCONEJ trasy troll_cave (z poprawionymi przejściami), więc działa z każdego
pola jaskini (z8 i z9), a kończy się przy Gornie (sprzedaje torch). UWAGA: pozycja Gorna (Home z danych Tibiantis)
i przejścia po minimapie są niezweryfikowane na żywo; pierwszy wypad obserwować.

troll_v2 (25.10, Wydra: wyprawa z jaskini szła okrężnie, ok. 43 pkt kręcenia po z9, trzy zbędne zejścia w dziury z8 -> z9 i z powrotem drabinami,
wyjście z z9 na z7 dopiero po ok. 2:40): odwrócone nagranie troll_cave zawiera pętle polowania (kieszenie z9 pod (32482,32296), (32474,32286),
(32476,32272)), a wypad idzie planem od najbliższego punktu do końca, więc każdą z nich przechodził. v2 = droga A* z mapy pełnej, BEZ nagrania:
  1. kieszeń z9 "gniazdo" (32471,32270,z9) (najwięcej zabić wg miejsca troll) -> drabina (32476,32272,z9) -> z8 (32476,32273);
  2. z8 do dziury (32478,32269) (JEDYNE zejście w dół na trasie, nie do ominięcia: z8 pod jaskinią jest rozcięte na dwie części, północna
     z wyjściem i południowa z halą łączą się tylko przez z9) -> korytarz z9 -> drabina (32484,32265,z9) -> z8 (32484,32266) -> pole (32493,32260,z8);
  3. dalej bez zmian droga do Gorna (to samo wyjście liną (32493,32260,z8) -> z7 i ta sama droga po z7 co w troll_do_miasta).
Drabiny w górę: zawsze z pola drabiny (stoimy na R, "wlasne"), tak jak w nagraniu i w zbuduj_etapy/log wypadu (GrafDrabiny).
Plan zaczyna się w kieszeni z9 "gniazdo" (pole z najwyższym udziałem zabić), więc stamtąd idzie bez dojścia; pozostałe części jaskini
(hala z8 na południe, kieszenie z9 (32482,32296) / (32474,32286), część wschodnia) łączą się z planem tak, jak wcześniej wschodnia część:
wypad.py bierze najbliższy osiągalny punkt planu na piętrze postaci, a gdy takiego nie ma (kieszeń z9), dojście drogą patrolu (_dojscie_start,
WYPRAWA_DOJSCIE_PATROLEM=1). Pierwszy punkt z7 = (32493,32260,7) jak dotąd (wyprawa._do_depo_odwrocona bierze go jako wejście na z7).
"""
import heapq
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
KATALOG = Path(__file__).resolve().parent
sys.path.insert(0, str(KATALOG))
import mapa as _mapa  # noqa: E402

TRASY = KATALOG / "trasy"
TROLL_STUB_START = (32471, 32270, 9)   # troll_v2: początek planu = gniazdo z9 pod schodami (32476,32272) (miejsca_troll #5, 42% zabić)
GORN_HOME = (32377, 32200, 7)          # NPC Gorn (Tibiantis: Home, promień 3); sprzedaje torch
KOSZT_W_DOL, KOSZT_W_GORE = 6, 8
RUCHY = ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 3), (1, -1, 3), (-1, 1, 3), (-1, -1, 3))


class Graf:
    def __init__(self, m):
        self.m = m

    def idzie(self, x, y, z):
        f = self.m.flagi(x, y, z)
        return bool(f & 1) and not f & 4 and not f & 2

    def sasiedzi(self, p):
        """(q, koszt, typ) z pola p: chodzenie, w dół (krok na dziurę), w górę (R obok albo własne)."""
        x, y, z = p
        for dx, dy, c in RUCHY:
            q = (x + dx, y + dy, z)
            if self.idzie(*q):
                yield q, c, "idz"
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            t = (x + dx, y + dy, z)
            f = self.m.flagi(*t)
            if f & 1 and f & 2 and not f & 4:
                l = (t[0], t[1], z + 1)
                if self.idzie(*l):
                    yield l, KOSZT_W_DOL, "dol"
        if z > 0:
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                r = (x + dx, y + dy, z)
                if not self.idzie(*r):
                    continue
                g = self.m.flagi(r[0], r[1], z - 1)
                if g & 1 and g & 2:
                    l = (r[0], r[1] + 1, z - 1)
                    if self.idzie(*l):
                        yield l, KOSZT_W_GORE, "gora"

    def astar(self, start, cel, limit=400000):
        """Najkrótsza droga start -> cel (dokładnie to pole); [(pole, typ_wejscia)] z pierwszym (start, None)."""
        start, cel = tuple(start), tuple(cel)
        d = {start: 0}
        skad = {start: None}
        pq = [(0, 0, start)]
        n = 0
        while pq:
            _, c, p = heapq.heappop(pq)
            if c > d[p]:
                continue
            if p == cel:
                wyn = []
                while p is not None:
                    prev = skad[p]
                    wyn.append((p, prev[1] if prev else None))
                    p = prev[0] if prev else None
                return wyn[::-1]
            n += 1
            if n > limit:
                return None
            for q, cc, t in self.sasiedzi(p):
                nc = c + cc
                if nc < d.get(q, 1 << 60):
                    d[q] = nc
                    skad[q] = (p, t)
                    h = max(abs(q[0] - cel[0]), abs(q[1] - cel[1])) + (0 if q[2] == cel[2] else 0)
                    heapq.heappush(pq, (nc + h, nc, q))
        return None


class GrafDrabiny(Graf):
    """Jak Graf, ale w górę tylko z pola drabiny R (stoimy NA R i robimy Use na własnym polu: "wlasne" w wypad.zbuduj_etapy),
    nie z pola obok. Tak przechodzi to nagranie troll_cave i tak wykonuje wypad drabinę z9 -> z8 w jaskini trolli
    (log 25.10: "drabina próba 1/6 (wlasne) z (32484, 32265, 9)")."""

    def sasiedzi(self, p):
        x, y, z = p
        for q, c, t in super().sasiedzi(p):
            if t == "gora":
                # lądowanie (R.x, R.y+1, z-1): R = (q.x, q.y-1, z) musi być polem p (stoimy na R)
                if (q[0], q[1] - 1) != (x, y):
                    continue
            yield q, c, t


def rzadko(sciezka, co=3):
    """Przerzedza drogę z A* (co `co`-te pole + zakręty + końce piętra); [(x,y,z)]. Pola przy przejściach zostają."""
    pts = [p for p, _ in sciezka]
    typy = [t for _, t in sciezka]
    n = len(pts)
    zostaw = {0, n - 1}
    for i in range(1, n):
        if typy[i] in ("dol", "gora"):
            zostaw.update({i - 1, i, min(n - 1, i + 1)})
    ost = 0
    for i in range(1, n - 1):
        kier = (pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) != (pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
        if pts[i][2] != pts[i - 1][2] or pts[i][2] != pts[i + 1][2]:
            zostaw.add(i)
        elif i - ost >= co or (kier and i - ost >= 2):
            zostaw.add(i)
        if i in zostaw:
            ost = i
    return [pts[i] for i in sorted(zostaw)]


def scal(*listy):
    wyn = []
    for l in listy:
        for p in l:
            p = (int(p[0]), int(p[1]), int(p[2]))
            if not wyn or wyn[-1] != p:
                wyn.append(p)
    return wyn


def napraw_przejscia(g, punkty):
    """Między sąsiednimi punktami na różnych piętrach wstawia drogę z grafu (poprawne pole przejścia).
    -> (lista, ostrzezenia)."""
    wyn, ost = [], []
    for p in punkty:
        p = tuple(p)
        if wyn and wyn[-1][2] != p[2]:
            a = wyn[-1]
            s = g.astar(a, p, limit=60000)
            if s is None:
                ost.append(f"brak przejścia {a} -> {p} w grafie, zostaje bezpośrednie")
            else:
                for q, _ in s[1:-1]:
                    wyn.append(q)
        wyn.append(p)
    return wyn, ost


def opisz_przejscia(punkty):
    spec = [{"idx": 0, "typ": "start", "komentarz": "początek trasy"}]
    for i in range(len(punkty) - 1):
        a, b = punkty[i], punkty[i + 1]
        if a[2] != b[2]:
            spec.append({"idx": i, "typ": "przed_zmiana_pietra", "komentarz": f"ostatnie pole na piętrze {a[2]}, potem piętro {b[2]}"})
            spec.append({"idx": i + 1, "typ": "schody_w_dol" if b[2] > a[2] else "schody_w_gore",
                         "komentarz": f"zmiana piętra {a[2]} -> {b[2]}, z ({a[0]},{a[1]})"})
    return {"specjalne": spec}


def stoisko(g, home, od):
    """Pole przy NPC: osiągalne z `od`, Chebyshev 1 od Home (potem 2), najtańsze. -> (pole, droga)."""
    kand = []
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            q = (home[0] + dx, home[1] + dy, home[2])
            c = max(abs(dx), abs(dy))
            if c >= 1 and g.idzie(*q):
                kand.append((c, abs(q[0] - od[0]) + abs(q[1] - od[1]), q))
    kand.sort()
    for _, _, q in kand:
        s = g.astar(od, q)
        if s is not None:
            return q, s
    return None, None


def zbuduj(nazwa, m):
    g = Graf(m)
    ostrz = []
    if nazwa == "troll":
        troll = [tuple(p) for p in json.loads((TRASY / "troll_cave.json").read_text())]
        wejscie = troll[0]
        rev, ow = napraw_przejscia(g, list(reversed(troll)))
        ostrz += ow
        cel, droga = stoisko(g, GORN_HOME, wejscie)
        if droga is None:
            raise SystemExit("brak drogi z troll_cave do Gorna")
        do = scal(rev, rzadko(droga))
        powrot = g.astar(cel, wejscie)
        if powrot is None:
            raise SystemExit("brak drogi powrotnej z Gorna do troll_cave")
        z = scal(rzadko(powrot))
        prefiks = "troll"
    elif nazwa == "troll_v2":
        troll = [tuple(p) for p in json.loads((TRASY / "troll_cave.json").read_text())]
        wejscie = troll[0]                       # (32493,32260,z8): pole pod liną wyjścia na z7, jak w troll_do_miasta
        jaskinia = GrafDrabiny(m).astar(TROLL_STUB_START, wejscie)
        if jaskinia is None:
            raise SystemExit(f"brak drogi z {TROLL_STUB_START} do {wejscie} w jaskini trolli")
        cel, droga = stoisko(g, GORN_HOME, wejscie)
        if droga is None:
            raise SystemExit("brak drogi z troll_cave do Gorna")
        do = scal(rzadko(jaskinia), rzadko(droga))
        z = None                                 # powrót (troll_z_miasta) bez zmian, zostaje plik żywy
        prefiks = "troll"
    elif nazwa == "kanaly":
        wejscie = (32360, 32242, 8)
        cel, droga = stoisko(g, GORN_HOME, wejscie)
        if droga is None:
            raise SystemExit("brak drogi z kanałów do Gorna")
        do = scal(rzadko(droga))
        powrot = g.astar(cel, wejscie)
        if powrot is None:
            raise SystemExit("brak drogi powrotnej z Gorna do kanałów")
        z = scal(rzadko(powrot))
        prefiks = "thais_kanaly"
    elif nazwa == "thais_pn":
        # 21.10 (kutangen na thais_pn_z8 nie miał planu powrotu): do_miasta = droga A* z jaskini (koniec dojścia) do Gorna;
        # odwrócone dojście odpada (zasypana dziura (32347,32123,z7) otwiera się tylko łopatą od góry), A* wychodzi liną
        # przez otwartą dziurę nad jaskinią (R na z8 pod (32339,32135,z7)). z_miasta = dojście (łopata w dół).
        doj = [tuple(p) for p in json.loads((TRASY / "thais_pn_z8_dojscie.json").read_text())]
        wejscie = doj[-1]
        # lina pod otworem (32339,32135,z8) nie działa w grze (kutangen 19:01, 4 próby); wychodzimy SCHODAMI w górę:
        # pole z8 z flagą 2, nad którym (z7) jest chodliwe lądowanie (wypad.zbuduj_etapy: "schody leżą pod lądowaniem")
        najl = None
        for x in range(32270, 32370):
            for y in range(32100, 32170):
                f = m.flagi(x, y, 8)
                if not (f & 1 and f & 2 and not f & 4) or not g.idzie(x, y, 7):
                    continue
                for ax, ay in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if not g.idzie(ax, ay, 8):
                        continue
                    d1 = g.astar(wejscie, (ax, ay, 8))
                    if d1 is None:
                        continue
                    cel, d2 = stoisko(g, GORN_HOME, (x, y, 7))
                    if d2 is None:
                        continue
                    koszt = len(d1) + len(d2)
                    if najl is None or koszt < najl[0]:
                        najl = (koszt, d1, d2, (x, y))
        if najl is None:
            raise SystemExit("brak schodów w górę z jaskini thais_pn do Gorna")
        _, d1, d2, schody = najl
        ostrz.append(f"wyjście z jaskini schodami (z8) {schody}")
        droga = d1 + d2
        do = scal(rzadko(droga))
        powrot = g.astar(cel, doj[0])
        if powrot is None:
            raise SystemExit("brak drogi powrotnej z Gorna na początek dojścia thais_pn")
        z = scal(rzadko(powrot), doj)
        prefiks = "thais_pn"
    else:
        raise SystemExit(f"nieznana trasa {nazwa}")
    return prefiks, do, z, cel, ostrz


def main(argv):
    if not argv or argv[0] not in ("troll", "troll_v2", "kanaly", "thais_pn"):
        print(__doc__)
        return 1
    m = _mapa.Mapa()
    prefiks, do, z, cel, ostrz = zbuduj(argv[0], m)
    print(f"{prefiks}: do_miasta {len(do)} pkt (z{do[0][2]} -> z{do[-1][2]}), z_miasta "
          + (f"{len(z)} pkt" if z else "bez zmian") + f", stoisko {cel}")
    for o in ostrz:
        print("UWAGA:", o)
    v2 = argv[0] == "troll_v2"
    for nazwa, pts in (("do_miasta", do), ("z_miasta", z or [])):
        zm = [(i, pts[i], pts[i + 1]) for i in range(len(pts) - 1) if pts[i][2] != pts[i + 1][2]]
        print(f"  {nazwa}: przejścia pięter {[(i, a, b) for i, a, b in zm]}")
    if "--zapisz" in argv:
        # troll_v2 zapisuje WYŁĄCZNIE troll_do_miasta_v2.*: plików żywych (troll_do_miasta.*, troll_z_miasta.*) nie rusza
        for sufiks, pts in ((("do_miasta_v2", do),) if v2 else (("do_miasta", do), ("z_miasta", z))):
            plik = TRASY / f"{prefiks}_{sufiks}.json"
            plik.write_text(json.dumps([list(p) for p in pts]))
            (TRASY / f"{prefiks}_{sufiks}.meta").write_text(json.dumps(opisz_przejscia(pts), ensure_ascii=False, indent=1))
            print("zapisano", plik)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
