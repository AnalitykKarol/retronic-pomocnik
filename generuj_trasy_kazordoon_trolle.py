#!/usr/bin/env python3
"""Kazordoon, jaskinie trolli pod miastem (trolle_kazordoon_z8, trolle_kazordoon_z9), z mapy klienta i spawnów CipSoft 7.4 (22.10).
Metoda jak generuj_trasy_thais_pn.py i generuj_trasy_edron_z9z.py (spot_lib: składowa, przystanki, pętla, zapis_spotu); nic nie wysyła do gry:

  python3 -I generuj_trasy_kazordoon_trolle.py [--zapisz]        bez --zapisz tylko liczy i drukuje podsumowanie

Powstają (przy --zapisz), w trasy/ i dane_tibia/mapy/:
  trolle_kazordoon_z8_petla, trolle_kazordoon_z8_dojscie   pętla z8 (tylko trolle) + dojście = WSPÓLNY odcinek
  trolle_kazordoon_z9_petla, trolle_kazordoon_z9_dojscie   pętla z9 (trolle, strefy zakazane) + dojście = WSPÓLNY odcinek + schody + lądowanie
  trolle_kazordoon_z8_do_depo, trolle_kazordoon_z9_do_depo powrót do depo (odcinek powrotny jest jawny, NIE odwrócone dojście)
  trolle_kazordoon_z8.png, trolle_kazordoon_z9.png (+ .json)

Zasada Karola (22.10): trasy składamy ze wspólnych odcinków, nie utrzymujemy dwóch takich samych dróg. Bot nie składa tras w trakcie
działania (jeden wpis `dojscie` na spot), więc generator trzyma JEDNĄ listę punktów kontrolnych wspólnego odcinka (WSPOLNA) i
odgałęzienie z9 (ODGALEZIENIE_Z9); `dojscie` każdego spotu to sklejenie tych samych punktów. Test: testy/test_kazordoon_trolle.py
(oba dojścia mają identyczny prefiks).

Wspólny odcinek (22.10 ~20:30, korekta Karola "chciałem na trolle trochę pod", NIE przez miasto Kazordoon): z depo THAIS (32348,32225,z7)
drogą (A* z preferencją szarej drogi, kolor 129) przez bramę północną, MOST nad wodą (pomost z6 (32549..32553,32076)), wschodni brzeg z7 ->
drzwi (32659,31966,z7) -> dziura (32663,31962,z7) -> z8, kieszeń z trollami -> drzwi (32657,31965,z8) -> rozwidlenie (32647,32003,z8) =
start pętli z8 i początek odgałęzienia na z9 (schody (32648,32003,z8) w dół). Grobla z6 z dwarfami (32616..32624,31964..31974) i miasto
Kazordoon NIE leżą na tej drodze. Punkty kontrolne i A* z kosztem terenu żyją w generuj_trase_thais_kazordoon.py (THAIS_DO_TROLLI,
THAIS_Z_TROLLI, astar_droga), tu są importowane: jedno źródło prawdy. Wcześniejsze dojście z depo Kazordoonu (z11) przez miasto i groblę
odpadło (kopia `.bak-20261022-kazo-z-thais`); trasa Thais -> miasto Kazordoon zostaje osobno (thais_kazordoon_tam/_powrot).
Odcinki między punktami kontrolnymi liczy A* po mapie piętra (m.droga), a KAŻDE przejście pięter jest sprawdzane przez
pietra.kandydaci (musi dać „pewne” z polem przejścia = nasze T). Drzwi = pola, które mapa uważa za ścianę (kolor 186) i które
trasa przekracza prostopadle (w trasie jako zwykły punkt; bot otwiera je jak nagrane drzwi).
Ogień: znane pola z trasy/ogien_stale.json i ogien_epizody.json + bufor 1 pole = ściana (jak w generuj_trasy_edron_z9z.py).
Strefy zakazane z9: promień 6 (Chebyshev) wokół spawnów innych potworów niż troll, które leżą w jaskini (<= SNAP od składowej), a
także każdego, do którego pętla zbliżyłaby się na <= 6 pól (iteracja, patrz zbuduj_z9).
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import mapa as _mapa  # noqa: E402
import generuj_trase_thais_kazordoon as _thais  # noqa: E402
import pietra  # noqa: E402
import spot_lib  # noqa: E402
import trasa_io  # noqa: E402
from generuj_trasy_edron_z9z import ogien_pola  # noqa: E402
from spot_lib import chodliwe, petla, przystanki, skladowa  # noqa: E402

N8, N9 = "trolle_kazordoon_z8", "trolle_kazordoon_z9"
STREFA = 6                              # promień strefy zakazanej wokół spawnu groźnego potwora (jak Thais północ)
CEL = ("troll",)
DEPO = _thais.DEPO_THAIS                # depo Thais (32348,32225,z7): start dojść i koniec powrotów (22.10: serwis Thais obsługuje te spoty)
ROZWIDLENIE = _thais.ROZWIDLENIE        # koniec wspólnego odcinka = start pętli z8 = początek odgałęzienia na z9
SCHODY_Z9 = (32648, 32003, 8)           # schody z8 -> z9 (pietra.kandydaci: pewne)
LAD_Z9 = (32648, 32004, 9)             # spot_lib.ladowanie: pole schodów z9 (32648,32003) ma flagę 2, więc stoimy pole na południe
DRZWI = ((32659, 31966, 7), (32657, 31965, 8))   # zamknięte drzwi na wspólnej trasie

# Punkty kontrolne wspólnego odcinka (jedyne źródło prawdy dla obu dojść). Kroki:
#   ("start", P)                       punkt startu
#   ("przejscie", T, L)                dojdź do pola obok T (prostopadle), wejdź na T (schody/dziura), L = pierwszy punkt na nowym piętrze
#   ("do", P)                          idź A* dokładnie do P
#   ("drzwi", D, kier)                 dojdź do pola przed D, przekrocz D prostopadle w kierunku kier, wyjdź na pole za nim
WSPOLNA = _thais.THAIS_DO_TROLLI           # depo Thais -> brama -> droga -> most -> z7 -> drzwi -> dziura -> z8 -> drzwi -> rozwidlenie
ODGALEZIENIE_Z9 = (("przejscie", SCHODY_Z9, LAD_Z9),)

# Powrót (jawnie, nie odwrócone dojście): z rozwidlenia z8 do depo Thais. JEDNO wejście liną: z dziury z8 (32663,31962) lina w górę, stoimy
# obok pola liny (pole liny wolne), lądowanie (32663,31963,z7); dalej drzwi, powierzchnia z7 -> most -> brama -> depo Thais.
POWROT_Z8 = _thais.THAIS_Z_TROLLI
# Powrót z z9: schody w górę z9 -> z8 w rozwidleniu, potem dokładnie ten sam powrót z8 (wspólny sufiks).
POWROT_Z9_PREFIKS = (
    ("start", LAD_Z9),
    ("przejscie", (32648, 32003, 9), (32648, 32004, 8)),
)


# ---------------------------------------------------------------------------------------------------------------------------------
def drzwi_ok(m, d):
    """Drzwi = pole, które mapa uważa za ścianę, z chodliwymi polami po obu stronach w jednej osi."""
    f = m.flagi(*d)
    if not f & _mapa.SCIANA:
        return False
    x, y, z = d
    return (chodliwe(m, (x, y - 1, z)) and chodliwe(m, (x, y + 1, z))) or (chodliwe(m, (x - 1, y, z)) and chodliwe(m, (x + 1, y, z)))


def klucze_drzwi(drzwi):
    return {d[0] * _mapa._K + d[1] for d in drzwi}


class Planista:
    """Buduje listę punktów (x, y, z) z kroków; A* po mapie piętra, ogień i dziury naznaczone jako ściana."""

    def __init__(self, m, zajete):
        self.m, self.zajete = m, zajete
        self.pts = []
        self.meta = []
        self.przejscia = []                # (indeks ostatniego punktu na starym piętrze, T, L, rodzaj)

    def _a(self, start, cel, dlugosc=0):
        z = start[2]
        przepusc = klucze_drzwi([d for d in DRZWI if d[2] == z])
        d = _thais.astar_droga(self.m, start, cel, self.zajete, przepusc)      # A* z kosztem terenu: droga (kolor 129) tania, trawa droga
        if d is None:
            raise SystemExit(f"brak drogi {start} -> {cel}")
        return d

    def idz(self, cel):
        if self.pts[-1] == cel:
            return
        if self.pts[-1][2] != cel[2]:
            raise SystemExit(f"idz: zmiana piętra bez przejścia {self.pts[-1]} -> {cel}")
        self.pts += self._a(self.pts[-1], cel)

    def obok(self, T, bez=()):
        """Najkrótsza droga do pola PROSTOPADLE obok T (chodliwego, nie na ścianie/dziurze), potem T."""
        best = None
        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            c = (T[0] + dx, T[1] + dy, T[2])
            if not chodliwe(self.m, c) or c in self.zajete or c in bez:
                continue
            if c == self.pts[-1]:
                d = []
            else:
                try:
                    d = self._a(self.pts[-1], c)
                except SystemExit:
                    continue
            if best is None or len(d) < len(best[1]):
                best = (c, d)
        if best is None:
            raise SystemExit(f"brak drogi do pola obok {T}")
        self.pts += best[1]

    def krok(self, k):
        t = k[0]
        if t == "start":
            self.pts = [k[1]]
        elif t == "do":
            self.idz(k[1])
        elif t == "drzwi":
            d = k[1]
            if not drzwi_ok(self.m, d):
                raise SystemExit(f"{d}: to nie są drzwi w mapie")
            if self.pts[-1][2] != d[2]:
                raise SystemExit(f"drzwi {d} na innym piętrze niż pozycja {self.pts[-1]}")
            kier = k[2]
            pre = (d[0] - kier[0], d[1] - kier[1], d[2])
            po = (d[0] + kier[0], d[1] + kier[1], d[2])
            if not chodliwe(self.m, pre) or not chodliwe(self.m, po):
                raise SystemExit(f"drzwi {d}: pole przed {pre} albo za {po} niechodliwe")
            self.idz(pre)
            self.pts += [d, po]
        elif t == "przejscie":
            T, L = k[1], k[2]
            self.obok(T)
            self.pts += [T, L]
            self.przejscia.append((len(self.pts) - 2, T, L, "schody/dziura"))
        elif t == "lina":
            R, stoi, L = k[1], k[2], k[3]
            if abs(stoi[0] - R[0]) + abs(stoi[1] - R[1]) != 1:
                raise SystemExit(f"lina: stanie {stoi} nie jest obok {R}")
            self.idz(stoi)
            self.pts += [L]
            self.przejscia.append((len(self.pts) - 2, R, L, "lina"))
        else:
            raise SystemExit(f"nieznany krok {k}")

    def zbuduj(self, kroki):
        for k in kroki:
            self.krok(k)
        return list(self.pts)


def sprawdz(m, pts, przejscia, ogien):
    """Asercje na gotowej trasie: ciągłość, drzwi prostopadle, przejścia przez pietra.kandydaci, ogień."""
    for a, b in zip(pts, pts[1:]):
        if a[2] == b[2] and max(abs(a[0] - b[0]), abs(a[1] - b[1])) != 1:
            raise SystemExit(f"nieciągłość {a} -> {b}")
    for p in pts:
        if p in ogien:
            raise SystemExit(f"punkt w ogniu/buforze: {p}")
    for i in range(1, len(pts) - 1):
        a, p, b = pts[i - 1], pts[i], pts[i + 1]
        if p in DRZWI and (a[0] != b[0] and a[1] != b[1]):
            raise SystemExit(f"drzwi {p} przekraczane po skosie {a} -> {b}")
    for i, T, L, rodzaj in przejscia:
        a, b = pts[i], pts[i + 1]
        kand = [c for c in pietra.kandydaci(m, a, b) if c["pewne"]]
        pola = [c["pole"] for c in kand]
        if T not in pola:
            raise SystemExit(f"przejście {rodzaj} {T} -> {L}: pietra.kandydaci nie daje go jako pewnego (daje {pola}) dla {a} -> {b}")


def meta_z_przejsc(przejscia, pts, komentarze):
    meta = []
    for i, T, L, rodzaj in przejscia:
        dol = L[2] > T[2]
        meta.append({"idx": i, "typ": "przed_zmiana_pietra", "komentarz": f"{rodzaj} {T[:2]} z{T[2]} -> z{L[2]}; {komentarze.get((T, L), '')}".rstrip("; ")})
        meta.append({"idx": i + 1, "typ": "schody_w_dol" if dol else "schody_w_gore", "komentarz": f"lądowanie z{L[2]} {L[:2]}"})
    return meta


KOMENTARZE = {
    ((32548, 32076, 7), (32549, 32076, 6)): "MOST Thais: rampa z7 w górę na pomost z6 (32549..32553); lądowanie NIEZMIERZONE w grze (założenie jak schody 210/210)",
    ((32554, 32076, 6), (32555, 32076, 7)): "MOST Thais: rampa z pomostu w dół na z7; lądowanie NIEZMIERZONE w grze",
    ((32663, 31962, 7), (32663, 31962, 8)): "dziura z7: może być ZASYPANA (wtedy ŁOPATA; do pietra.ZASYPANE dopiszesz po dowodzie z gry); powrót LINĄ",
    (SCHODY_Z9, LAD_Z9): "schody z8 <-> z9 w rozwidleniu",
}


def potwory_obok(z, trasa, nazwy_poza=("troll",)):
    """Spawny innych potworów niż trolle na piętrze z w prostokącie trasy +8 -> [(nazwa, x, y, ilosc, min_odl_od_trasy)]."""
    dane = json.loads(spot_lib.SPAWNY.read_text())["potwory"]
    xs, ys = [p[0] for p in trasa], [p[1] for p in trasa]
    out = []
    for mo in dane:
        if mo["nazwa"] in nazwy_poza:
            continue
        for s in mo.get("spawny", []):
            if s["z"] == z and min(xs) - 8 <= s["x"] <= max(xs) + 8 and min(ys) - 8 <= s["y"] <= max(ys) + 8:
                od = min(max(abs(s["x"] - p[0]), abs(s["y"] - p[1])) for p in trasa)
                out.append((mo["nazwa"], s["x"], s["y"], s["ilosc"], od))
    return sorted(out, key=lambda t: t[4])


def potwory_przy_trasie(trasa, promien=4):
    """Wszystkie spawny (też trolle) w promieniu `promien` od punktów trasy, na tym samym piętrze -> [(z, nazwa, x, y, ilość, odl)]."""
    dane = json.loads(spot_lib.SPAWNY.read_text())["potwory"]
    out = []
    for mo in dane:
        for s in mo.get("spawny", []):
            od = min((max(abs(s["x"] - p[0]), abs(s["y"] - p[1])) for p in trasa if p[2] == s["z"]), default=99)
            if od <= promien:
                out.append((s["z"], mo["nazwa"], s["x"], s["y"], s["ilosc"], od))
    return sorted(out)


def zbuduj():
    m = _mapa.Mapa()
    dz = [tuple(p) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])]
    ogien = ogien_pola()
    zajete = set(dz) | ogien
    # strefy zakazane z7 (promień 6 wokół spawnów groźniejszych niż troll) jak w trasie Thais -> Kazordoon; punkty kontrolne zwolnione
    strefy = _thais.strefy_zakazane(m, ogien, dz)
    ok_pkt = {k[1] for k in WSPOLNA + POWROT_Z8 if k[0] in ("start", "do")} | {(32663, 31961, 8), (32663, 31963, 7), _thais.DZIURA_TROLLE}
    zajete |= {p for p in strefy if p not in ok_pkt}
    for d in DRZWI:
        if not drzwi_ok(m, d):
            raise SystemExit(f"{d}: to nie są drzwi w mapie")
    # --- wspólny odcinek (jedna lista, dwa dojścia) ---
    pl = Planista(m, zajete)
    wsp = pl.zbuduj(WSPOLNA)
    sprawdz(m, wsp, pl.przejscia, ogien)
    przej_wsp = list(pl.przejscia)
    print(f"wspólny odcinek (Thais -> rozwidlenie z8): {len(wsp)} pkt, {DEPO} -> {wsp[-1]}, piętra {sorted({p[2] for p in wsp})}, przejść {len(przej_wsp)}")
    print("   spawny potworów <= 4 pola od wspólnego odcinka (z, nazwa, x, y, ilość, odl):", potwory_przy_trasie(wsp))
    # --- z8 ---
    wyn = {}
    sc8 = [p for p in zajete if p[2] == 8]
    comp8 = skladowa(m, ROZWIDLENIE, sc8)
    sp8 = spot_lib.spawny(8, CEL)
    st8 = przystanki(sp8, comp8)
    order8, nodes8, pelna8 = petla(m, 8, ROZWIDLENIE[:2], st8, sc8)
    print(f"{N8}: składowa {len(comp8)} pól, przystanków {len(st8)}, trolli {sum(t['n'] for t in st8)}, pętla {len(pelna8)} pól, kolejność {order8}")
    meta8 = [{"idx": 0, "typ": "start", "komentarz": "depo Thais (z7), wygenerowane z mapy 22.10 (jedno wspólne dojście z drogi przez most)"}] \
        + meta_z_przejsc(przej_wsp, wsp, KOMENTARZE)
    wyn[N8] = dict(z=8, comp=comp8, st=st8, order=order8, nodes=nodes8, pelna=pelna8, strefa=None, doj=list(wsp), meta=meta8)
    # --- z9 ---
    odg = Planista(m, zajete)
    odg.pts = list(wsp)
    odg.przejscia = []
    odg.zbuduj(ODGALEZIENIE_Z9)
    doj9 = list(odg.pts)
    przej9 = przej_wsp + [(i, T, L, r) for i, T, L, r in odg.przejscia]
    sprawdz(m, doj9, przej9, ogien)
    L9 = doj9[-1]
    assert doj9[:len(wsp)] == wsp and L9 == LAD_Z9
    sc9 = [p for p in zajete if p[2] == 9]
    dane = json.loads(spot_lib.SPAWNY.read_text())["potwory"]
    inne = [(mo["nazwa"], s) for mo in dane if mo["nazwa"] not in CEL for s in mo.get("spawny", [])
            if s["z"] == 9 and 32600 <= s["x"] <= 32760 and 31900 <= s["y"] <= 32080]
    comp_pelna = skladowa(m, L9, sc9)
    zakazane = [(n, s) for n, s in inne if any(max(abs(c[0] - s["x"]), abs(c[1] - s["y"])) <= spot_lib.SNAP for c in comp_pelna)]
    print(f"z9: składowa {len(comp_pelna)} pól; potwory inne niż troll w jaskini (strefa {STREFA}): "
          f"{[(n, s['x'], s['y']) for n, s in zakazane]}")
    for _ in range(8):
        zle = spot_lib.strefa_zakazana([s for _, s in zakazane], 9, STREFA)
        sciana9 = sc9 + sorted(zle)
        if LAD_Z9 in zle:
            raise SystemExit("lądowanie z9 w strefie zakazanej")
        comp9 = skladowa(m, L9, sciana9)
        sp9 = spot_lib.spawny(9, CEL)
        jady = [(s["x"], s["y"]) for _, s in zakazane]
        st9 = [t for t in przystanki(sp9, comp9) if not any(max(abs(t["pt"][0] - p[0]), abs(t["pt"][1] - p[1])) <= STREFA + 2 for p in jady)]
        order9, nodes9, pelna9 = petla(m, 9, L9[:2], st9, sciana9)
        w_strefie = [p for p in pelna9 if (p[0], p[1], 9) in zle]
        if w_strefie:
            raise SystemExit(f"z9: pętla wchodzi w strefę zakazaną: {w_strefie[:5]}")
        bliskie = [(n, s) for n, s in inne if (n, s) not in zakazane
                   and any(max(abs(p[0] - s["x"]), abs(p[1] - s["y"])) <= STREFA for p in pelna9)]
        if not bliskie:
            break
        print(f"z9: pętla przechodzi <= {STREFA} pól od: {[(n, s['x'], s['y']) for n, s in bliskie]} - dodaję do stref, liczę ponownie")
        zakazane += bliskie
    else:
        raise SystemExit("z9: strefy nie ustabilizowały się w 8 iteracjach")
    odl = potwory_obok(9, pelna9)[:6]
    print(f"{N9}: składowa {len(comp9)} pól (bez stref; z nimi {len(comp_pelna)}), przystanków {len(st9)}, trolli {sum(t['n'] for t in st9)} "
          f"(spawnów {sum(t['spawny'] for t in st9)} z {len(sp9)}), pętla {len(pelna9)} pól, kolejność {order9}")
    print("   najbliższe inne potwory od pętli z9 (nazwa, x, y, ilość, odl):", odl)
    odl8 = potwory_obok(8, pelna8)[:4]
    print("   najbliższe inne potwory od pętli z8:", odl8)
    meta9 = [{"idx": 0, "typ": "start", "komentarz": "depo Thais (z7), wygenerowane z mapy 22.10 (jedno wspólne dojście z drogi przez most)"}] \
        + meta_z_przejsc(przej9, doj9, KOMENTARZE)
    wyn[N9] = dict(z=9, comp=comp9, st=st9, order=order9, nodes=nodes9, pelna=pelna9, strefa=zle, doj=doj9, meta=meta9,
                   zakazane=[(n, s["x"], s["y"]) for n, s in zakazane])
    # --- powrót ---
    # --- powrót do depo ---
    pr = Planista(m, zajete)
    pow8 = pr.zbuduj(POWROT_Z8)
    przej_pow8 = list(pr.przejscia)
    sprawdz(m, pow8, przej_pow8, ogien)
    pr9 = Planista(m, zajete)
    pr9.zbuduj(POWROT_Z9_PREFIKS)
    n_pref = len(pr9.pts)
    pr9.pts.append(ROZWIDLENIE)          # z (32648,32004,z8) krok na rozwidlenie, potem wspólny sufiks
    pow9 = pr9.pts + pow8[1:]
    przej_pow9 = list(pr9.przejscia) + [(i + n_pref, T, L, r) for i, T, L, r in przej_pow8]
    sprawdz(m, pow9, przej_pow9, ogien)
    kom_pow = {((32663, 31962, 8), (32663, 31963, 7)): "LINA na (32663,31962,z8): stoimy obok (pole liny wolne), lądowanie (x, y+1) na z7"}
    meta_pow8 = [{"idx": 0, "typ": "start", "komentarz": "rozwidlenie z8 (koniec dojścia, start pętli)"}] + meta_z_przejsc(przej_pow8, pow8, kom_pow) \
        + [{"idx": len(pow8) - 1, "typ": "koniec", "komentarz": "depo Thais (z7), pole przybycia wyprawy"}]
    meta_pow9 = [{"idx": 0, "typ": "start", "komentarz": "lądowanie z9 (start pętli z9)"}] + meta_z_przejsc(przej_pow9, pow9, kom_pow) \
        + [{"idx": len(pow9) - 1, "typ": "koniec", "komentarz": "depo Thais (z7), pole przybycia wyprawy"}]
    print(f"powrót z8: {len(pow8)} pkt (liny: {sum(1 for q in przej_pow8 if q[3] == 'lina')}); powrót z9: {len(pow9)} pkt; piętra {sorted({p[2] for p in pow8})}")
    powroty = {f"{N8}_do_depo": (pow8, meta_pow8), f"{N9}_do_depo": (pow9, meta_pow9)}
    return m, wyn, wsp, ogien, powroty


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m, wyn, wsp, ogien, powroty = zbuduj()
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    for nazwa, w in wyn.items():
        spot_lib.zapis_spotu(m, nazwa, w["z"], w["pelna"], w["order"], w["nodes"], w["st"], f"Kazordoon trolle z{w['z']}", jedn="potw.",
                             opis_przyst="spawn(y) trolli", doj=w["doj"], meta=w["meta"], strefa=w["strefa"],
                             ekstra={"strefa_zakazana": STREFA, "zakazane": w.get("zakazane", [])})
    for nazwa, (pkt, meta) in powroty.items():
        print("zapisano", trasa_io.zapisz(nazwa, pkt, meta))
    print("zapisano trasy/ i dane_tibia/mapy/ (wpisy mapy.json i spoty_nadzorca.json dodaj osobno)")


if __name__ == "__main__":
    main()
