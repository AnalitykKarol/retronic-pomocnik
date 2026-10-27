#!/usr/bin/env python3
"""Rodziny spotów, dojście z DOWOLNEGO piętra jaskini (26.10, Karol: zmiana spotu w jaskini nie może wymagać wyjścia na z7).
Biblioteka offline (tylko odczyt mapy klienta i plików repo; nic nie idzie do gry): ocena dojść (ta sama logika co mozg.dojscie_od_pozycji,
`spoty.dojscie_dziala_z`) dla każdej pary map jednej rodziny oraz planer łączników (drabina: dziura w dół, lina w górę) dla jaskiń z dziurami i linami.

  python3 -I rodziny_dojscie.py [rodzina ...]       macierz: z każdej pętli rodziny do dojścia każdej innej mapy (próbki punktów pętli)

Definicje:
  źródło  = pętla mapy A rodziny (postać stoi w jej punkcie, bo tam gra);
  cel     = mapa B tej samej rodziny z dojściem; dojście B zadziała z punktu `poz`, gdy `spoty.dojscie_dziala_z(B, poz)`: postać już przy pętli B
            (<= 10 pól, mozg pomija dojście), albo punkt dojścia B na jej piętrze w <= 60 polach drogi i reszta dojścia bez z7;
  łącznik = trasa od źródła (stanie przy dziurze/linie) po przejściach pięter do miejsca, z którego dojście B działa, doklejona do dojścia B (wariant mapy).
"""
import collections
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import mapa as _mapa  # noqa: E402
import spot_lib  # noqa: E402
import spoty as SP  # noqa: E402
import trasa_io  # noqa: E402
import generuj_rodziny_pietra as GP  # noqa: E402

PROBKA_PETLI = 8              # co ile punktów pętli źródła sprawdzamy (+ pierwszy i ostatni)
POKRYCIE_START = 55           # pole pętli źródła musi leżeć w tylu polach DROGI od pierwszego odcinka łącznika (mozg: 60)
GLEBOKOSC = 3                 # najwyżej tyle lin w górę w jednym łączniku

# rodziny z dziurami i linami (łączniki liczone planerem): prostokąt jaskini (x0, x1, y0, y1) i zakres pięter, z których bierzemy przejścia z tras
JASKINIE = {
    "edron_trolle": {"bbox": (33040, 33150, 31690, 31790), "z": (8, 10)},
    "edron_gobliny": {"bbox": (33040, 33115, 31795, 31880), "z": (8, 10)},
    "abdendriel_trolle": {"bbox": (32600, 32740, 31570, 31700), "z": (9, 12)},
}
# cele, dla których liczymy dojście z innych pięter (reszta map rodziny to aliasy tej samej pętli albo mapy bez własnej roli w zmianie spotu)
CELE = {
    "edron_trolle": ["trolle_edron", "trolle_edron_patrol", "trolle_edron_z9w", "trolle_edron_z9z", "trolle_edron_z10w"],
    "edron_gobliny": ["gobliny_edron", "gobliny_edron_z9", "gobliny_edron_z10_zachod", "gobliny_edron_z10_wschod", "gobliny_edron_z10_poludnie"],
    "abdendriel_trolle": ["abdendriel_trolle_z9", "abdendriel_trolle_z10_z9", "abdendriel_trolle_z11_z9", "abdendriel_trolle_z12_z9"],
}


def swiat(korzen=ROOT):
    return SP.wczytaj(korzen)


def petla_mapy(t, nazwa):
    return [tuple(p) for p in (SP.punkty_trasy(ROOT, t.spoty[nazwa].trasa) or [])]


def rodzina(t, fam):
    return sorted(n for n, s in t.spoty.items() if s.rodzina == fam)


def zrodla_rodziny(t, fam):
    """{etykieta źródła: (pętla [(x,y,z)], [nazwy map z tą pętlą])}. Etykieta = pierwsza alfabetycznie mapa z tą pętlą (nie wariant-łącznik)."""
    wyn = {}
    for n in rodzina(t, fam):
        if t.spoty[n].baza:
            continue
        p = tuple(petla_mapy(t, n))
        if p:
            wyn.setdefault(p, []).append(n)
    return {sorted(v)[0]: (list(k), sorted(v)) for k, v in wyn.items()}


def probki(petla):
    return petla[::PROBKA_PETLI] + [petla[-1]]


def ocena_zrodla(t, fam, zrodlo, cel, m=None):
    """Wyniki dojście_dziala_z celu `cel` (Spot) z próbek pętli źródła: {'ok': n, 'brak': n, 'z7': n, 'zle': [pozycje]}."""
    petla, _ = zrodla_rodziny(t, fam)[zrodlo]
    wyn = {"ok": 0, "brak": 0, "zle": []}
    for poz in probki(petla):
        if poz[2] == SP.LEKKIE_Z:
            wyn["ok"] += 1
            continue
        ok, _ = SP.dojscie_dziala_z(cel, poz, m)
        if ok is False or (ok is None and not cel.z_dowolnego_pietra):
            wyn["brak"] += 1
            wyn["zle"].append(poz)
        else:
            wyn["ok"] += 1
    return wyn


def dziala_z(t, B, poz, m=None):
    """True/False/None: dojście mapy B z pozycji `poz` (zwykłe albo któregokolwiek wariantu-łącznika B; None = nie da się ocenić, zostaje flaga)."""
    if poz[2] == SP.LEKKIE_Z:
        return True
    wyn = []
    for s in [t.spoty[B]] + sorted((v for v in t.spoty.values() if v.baza == B), key=lambda v: v.mapa):
        ok, _ = SP.dojscie_dziala_z(s, poz, m)
        if ok is True:
            return True
        wyn.append(ok)
    return None if None in wyn else False


def luki(t, fam, m=None):
    """[(źródło, cel, [pozycje bez dojścia])]: pary pętla źródłowa -> mapa docelowa rodziny (cel bez wariantów, z dojściem i inną pętlą), dla których z próbek
    pętli źródła nie działa ani dojście celu, ani żaden jego wariant-łącznik (to są te pary, o których test_rodziny musi wiedzieć świadomie)."""
    wyn = []
    zr = zrodla_rodziny(t, fam)
    for A, (petla, nazwy) in sorted(zr.items()):
        for B in rodzina(t, fam):
            sb = t.spoty[B]
            if sb.baza or not sb.dojscie or B in nazwy or tuple(petla_mapy(t, B)) == tuple(petla):
                continue
            zle = [poz for poz in probki(petla) if dziala_z(t, B, poz, m) is False or (dziala_z(t, B, poz, m) is None and not sb.z_dowolnego_pietra)]
            if zle:
                wyn.append((A, B, zle))
    return wyn


def macierz(t, fam, m=None):
    """[(źródło, cel, wynik)] dla wszystkich par rodziny (źródła = różne pętle, cele = mapy z dojściem i inną pętlą niż źródło)."""
    wyn = []
    zr = zrodla_rodziny(t, fam)
    for A, (petla, nazwy) in sorted(zr.items()):
        for B in rodzina(t, fam):
            sb = t.spoty[B]
            if sb.baza or not sb.dojscie or B in nazwy or tuple(petla_mapy(t, B)) == tuple(petla):
                continue
            wyn.append((A, B, ocena_zrodla(t, fam, A, sb, m)))
    return wyn


# ---------------------------------------------------------------- planer łączników (dziura w dół, lina w górę)
def sciany(m, scisle=True):
    """Ściany A*: dziury nauczone i ręczne + ogień z buforem 1 (jak w generatorach). scisle=False: ogień tylko stały i epizody n >= 2, BEZ bufora
    (pojedyncze epizody n=1 leżą na sprawdzonej na żywo drodze Edron z8 do schodów z9w: strefa pewnego ognia nadal omijana). -> funkcja piętra -> lista (x,y,z)."""
    dz = {tuple(p[:3]) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])}
    try:
        dz |= {tuple(p[:3]) for p in json.loads((ROOT / "trasy" / "dziury_omijaj.json").read_text()).get("dziury", [])}
    except (OSError, ValueError):
        pass
    if scisle:
        og = GP.ogien_pola()
    else:
        og = {tuple(p[:3]) for p in json.loads((ROOT / "trasy" / "ogien_stale.json").read_text()).get("pola", [])}
        ep = json.loads((ROOT / "trasy" / "ogien_epizody.json").read_text()).get("pola", {})
        og |= {tuple(int(a) for a in k.split(",")) for k, v in ep.items() if isinstance(v, dict) and v.get("n", 0) >= 2}
    return lambda z: sorted([p for p in dz if p[2] == z] + [p for p in og if p[2] == z])


def dziury_jaskini(t, fam):
    """[(T, L)]: przejścia W DÓŁ (z -> z+1) z tras dojścia/powrotu w prostokącie jaskini; L = lądowanie = pole liny na dolnym piętrze."""
    cfg = JASKINIE[fam]
    x0, x1, y0, y1 = cfg["bbox"]
    z0, z1 = cfg["z"]
    pliki = {s.dojscie for s in t.spoty.values() if s.dojscie and s.rodzina == fam}
    pliki |= {p.name[:-5] for p in (ROOT / "trasy").glob("*.json") if "do_depo" in p.name or "odwrocona" in p.name or p.name.startswith("abdendriel_depo_do")}
    wyn = {}

    def w(p):
        return x0 <= p[0] <= x1 and y0 <= p[1] <= y1 and z0 <= p[2] <= z1
    for f in sorted(pliki):
        pts = SP.punkty_trasy(ROOT, f) or []
        for a, b in zip(pts, pts[1:]):
            if b[2] == a[2] + 1 and w(a) and w(b) and max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 1:
                wyn[(a, (a[0], a[1], a[2] + 1))] = f      # pole liny = pole dziury piętro niżej (np. gobliny z8 (33092,31837) -> z9 lina (33092,31837))
    return sorted(wyn)


def _chodliwe(m, p, zle):
    return spot_lib.chodliwe(m, p) and (p[0], p[1]) not in zle


def wyjscia_w_gore(m, t, fam, comp, z, sc):
    """[(stanie, pole_liny, ladowanie)] liną w górę z komponentu `comp` (zbiór (x,y)) piętra z: dla każdej dziury (T, L) z L w komponencie
    (lina = pole L, stanie = chodliwy sąsiad L w komponencie, lądowanie = (L.x, L.y+1, z-1) chodliwe)."""
    zle9 = {(p[0], p[1]) for p in sc(z)}
    zle8 = {(p[0], p[1]) for p in sc(z - 1)}
    wyn = []
    for T, L in dziury_jaskini(t, fam):
        if L[2] != z or (L[0], L[1]) not in comp:
            continue
        U = (L[0], L[1] + 1, z - 1)
        if not _chodliwe(m, U, zle8):
            continue
        for dx, dy in ((0, -1), (1, 0), (-1, 0), (1, -1), (-1, -1), (0, 1), (1, 1), (-1, 1)):
            S = (L[0] + dx, L[1] + dy, z)
            if (S[0], S[1]) in comp and _chodliwe(m, S, zle9):
                wyn.append((S, L, U))
                break
    return wyn


def _droga(m, a, b, sc, sc_slabe=None):
    """Droga A* a -> b (bez a) po piętrze; omija `sc`, a gdy się nie da i podano `sc_slabe`, ponawia z nimi (pewny ogień zostaje ścianą)."""
    if a[:2] == b[:2] and a[2] == b[2]:
        return []
    d = m.droga(a, b, zajete=sc(a[2]), dlugosc=0, limit=800000)
    if d is None and sc_slabe is not None:
        d = m.droga(a, b, zajete=sc_slabe(a[2]), dlugosc=0, limit=800000)
    return None if d is None else [(p[0], p[1], a[2]) for p in d]


def tail_dojscia(sb, U, m):
    """(indeks, tail) dojścia celu od lądowania U albo None."""
    import trasa_io as _t  # noqa: PLC0415
    p = sb._doj_up or _t.uprosc_petle(sb._doj_pts)
    sb._doj_up = p
    i = SP.start_dojscia(p, U, m)
    if i is None or any(q[2] == SP.LEKKIE_Z for q in p[i:]):
        return None
    return i, p[i:]


def zbuduj_lacznik(t, fam, A, B, m=None, ostrz=None):
    """Łącznik źródło A (etykieta pętli) -> cel B (nazwa mapy): (punkty, meta, opis) albo None. Plan: stanie przy linie w komponencie pętli A -> lina w górę ->
    (ewentualnie kolejne liny) -> tam, gdzie dojście B zadziała (`tail_dojscia`) -> dojście B. Pierwszy odcinek na piętrze źródła dostaje przystanki-podajniki,
    gdy któryś punkt pętli leży dalej niż POKRYCIE_START pól drogi od niego (mozg: DOJSCIE_START_DROGA = 60)."""
    m = m or _mapa.mapa()
    sc = sciany(m)
    petla, _ = zrodla_rodziny(t, fam)[A]
    sb = t.spoty[B]
    if sb._doj_pts is None:
        return None
    z = petla[0][2]
    comp = skladowa_xy(m, petla[0], sc(z))
    # głębokość 0: dojście celu działa z części pętli źródła (nie z każdego jej punktu): łącznik = podajniki + dojście od wybranego punktu pętli
    scs0 = sciany(m, False)
    ok0 = [p for p in petla[::3] if p[2] == z and tail_dojscia(sb, p, m) is not None]
    if ok0:
        zr = [p for p in petla if p[2] == z]
        kand0 = ok0[::max(1, len(ok0) // 10)]
        P0 = min(kand0, key=lambda p: max(_bfs(m, [p], scs0(z)).get((q[0], q[1]), 9999) for q in zr))
        return _z_pokryciem(m, t, sc, petla, [], sb, tail_dojscia(sb, P0, m), scs0, P0)
    poziom = [(comp, z, [], petla[0])]          # (komponent, piętro, kroki dotąd, punkt startu odcinka)
    for _ in range(GLEBOKOSC):
        nast = []
        for comp, z, kroki, start in poziom:
            for S, L, U in wyjscia_w_gore(m, t, fam, comp, z, sc):
                kr = kroki + [(S, L, U)]
                td = tail_dojscia(sb, U, m) or koniec_na_petli(m, t, B, U, sciany(m, False))
                if td is not None:
                    return _z_pokryciem(m, t, sc, petla, kr, sb, td, sciany(m, False))
                comp2 = skladowa_xy(m, U, sc(U[2]))
                nast.append((comp2, U[2], kr, U))
        poziom = nast
    return None


def koniec_na_petli(m, t, B, U, scs):
    """Gdy dojście celu nie ma odcinka osiągalnego z lądowania U, ale pętla celu leży na piętrze U: koniec łącznika = najbliższy PO DRODZE punkt pętli B
    (postać stoi wtedy przy własnej pętli i startuje patrol od najbliższego punktu). -> (None, [punkt]) albo None."""
    petla = [p for p in (SP.punkty_trasy(ROOT, t.spoty[B].trasa) or []) if p[2] == U[2]]
    if not petla:
        return None
    dist = _bfs(m, [U], scs(U[2]))
    cel = min(petla, key=lambda p: (dist.get((p[0], p[1]), 9999), p))
    if dist.get((cel[0], cel[1]), 9999) > 150:
        return None
    return None, [tuple(cel)]


def skladowa_xy(m, p, zle):
    return spot_lib.skladowa(m, (p[0], p[1], p[2]), zle)


def _z_pokryciem(m, t, sc, petla, kroki, sb, td, scs, kotwica=None):
    """_zloz + podajniki: dopóki któryś punkt pętli źródła nie ma punktu łącznika na swoim piętrze w <= 60 polach DROGI (dokładnie jak mozg: start_dojscia na
    uproszczonym łączniku), dopisuje na początku najdalszy taki punkt z drogą A* do dotychczasowego początku. Punkty bez drogi (kieszeń odcięta) pomija."""
    import trasa_io as _t  # noqa: PLC0415
    z0 = petla[0][2]
    S0 = kroki[0][0] if kroki else kotwica
    pref, pomin = [], set()
    for _ in range(10):
        r = _zloz(m, t, sc, petla, kroki, sb, td, scs, kotwica, pref)
        if r is None:
            return None
        up = _t.uprosc_petle(r[0])
        zle = [p for p in petla[::2] if p[2] == z0 and p not in pomin and SP.start_dojscia(up, p, m) is None]
        if not zle:
            return r
        wejscie = pref[0] if pref else S0
        pf = max(zle, key=lambda p: (max(abs(p[0] - wejscie[0]), abs(p[1] - wejscie[1])), p))
        d = _droga(m, pf, wejscie, sc, scs)
        if d is None:
            pomin.add(pf)
            continue
        pref = [pf] + d[:-1] + pref
    return r


def _zloz(m, t, sc, petla, kroki, sb, td, scs, kotwica=None, pref=()):
    pts, meta = [], []
    z0 = petla[0][2]
    # podajniki: pierwszy odcinek (piętro źródła) = [ewentualny prefiks z najdalszego punktu pętli] + stanie
    S0 = kroki[0][0] if kroki else kotwica
    if pref:
        pts += list(pref)
    meta.append({"idx": 0, "typ": "start", "komentarz": "łącznik z innego piętra rodziny: start przy pętli źródła (podajnik) albo przy stoisku liny"})
    opisy = []
    cur = S0 if not kroki else None
    if not kroki:
        pts.append(S0)
    for k, (S, L, U) in enumerate(kroki):
        if k > 0:
            d = _droga(m, cur, S, sc, scs)
            if d is None:
                return None
            pts += d
        if not pts or pts[-1] != S:
            pts.append(S)
        meta.append({"idx": len(pts) - 1, "typ": "przed_zmiana_pietra", "komentarz": f"stoję {S[:3]} obok pola liny {L[:3]}, potem piętro {U[2]}"})
        pts.append(U)
        meta.append({"idx": len(pts) - 1, "typ": "schody_w_gore",
                     "komentarz": f"LINA: z{S[2]} {S[:2]} -> z{U[2]} {U[:2]}, pole liny {L[:2]} (NIEZWERYFIKOWANA na żywo, wzorzec jak istniejące wyjścia liną z dziur)"})
        opisy.append(f"lina z{S[2]} -> z{U[2]} przy {L[:2]}")
        cur = U
    i, tail = td
    d = _droga(m, cur, tail[0], sc, scs)
    if d is None:
        return None
    pts += d
    if pts[-1] != tail[0]:
        pts.append(tail[0])
    od = len(pts) - 1
    pts += tail[1:]
    meta.append({"idx": od, "typ": "opis", "komentarz": (f"od tego punktu: dojście spotu docelowego (od jego punktu {i}, {len(tail)} pkt)" if i is not None
                                                           else "koniec łącznika: punkt pętli spotu docelowego (postać już w jego jaskini)")})
    return pts, meta, opisy


def _bfs(m, starty, zle):
    zle = {(p[0], p[1]) for p in zle}
    d, q = {}, collections.deque()
    for s in starty:
        d[(s[0], s[1])] = 0
        q.append((s[0], s[1], s[2]))
    while q:
        x, y, z = q.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy)
                if (dx or dy) and n not in d and n not in zle:
                    f = m.flagi(n[0], n[1], z)
                    if f & _mapa.WIDZIANE and not f & (_mapa.SCIANA | _mapa.BEZ_DROGI):
                        d[n] = d[(x, y)] + 1
                        q.append((n[0], n[1], z))
    return d


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    os.environ.setdefault("RETRONIC_TESTY", "1")
    t = swiat()
    m = _mapa.mapa()
    for fam in sorted({s.rodzina for s in t.spoty.values()}):
        if argv and fam not in argv:
            continue
        mac = macierz(t, fam, m)
        if not mac:
            continue
        print("==", fam)
        for A, B, w in mac:
            print(f"  {A:30} -> {B:30} ok {w['ok']:3} brak {w['brak']:3} {w['zle'][:1] if w['brak'] else ''}")


if __name__ == "__main__":
    main()


def sztuczny_spot(t, B, pts, nazwa="lacznik"):
    """Spot-atrapa o dojściu `pts` i pętli celu B (do `dojscie_dziala_z` przed zapisem plików)."""
    sb = t.spoty[B]
    s = SP.Spot(nazwa)
    s.dojscie, s.trasa, s.z_dowolnego_pietra = nazwa, sb.trasa, True
    s._doj_pts = [tuple(p) for p in pts]
    s._trasa_pts = sb._trasa_pts
    return s


def weryfikuj_lacznik(t, fam, A, B, pts, m=None, krok=3):
    """(ok, uwagi): z KAŻDEGO (co `krok`.) punktu pętli źródła A dojście = łącznik działa (dojscie_dziala_z), kończy się tam, gdzie dojście celu B,
    a trasa jest ciągła (krok <= 1 na piętrze) i bez ognia/dziur nauczonych w nowej części."""
    m = m or _mapa.mapa()
    sb = t.spoty[B]
    s = sztuczny_spot(t, B, pts)
    petla, _ = zrodla_rodziny(t, fam)[A]
    uw = []
    for poz in petla[::krok] + [petla[-1]]:
        if poz[2] == SP.LEKKIE_Z:
            continue
        ok, pw = SP.dojscie_dziala_z(s, poz, m)
        if ok is not True:
            uw.append(f"z {poz}: {pw}")
            if len(uw) > 3:
                break
    if tuple(pts[-1]) != tuple(sb._doj_pts[-1]) and tuple(pts[-1]) not in {tuple(p) for p in (sb._trasa_pts or [])}:
        uw.append(f"koniec łącznika {pts[-1]} nie jest ani końcem dojścia celu {sb._doj_pts[-1]}, ani punktem jego pętli")
    sc = sciany(m)
    for a, b in zip(pts, pts[1:]):
        if a[2] == b[2] and max(abs(a[0] - b[0]), abs(a[1] - b[1])) > 1:
            uw.append(f"skok {a}->{b}")
            break
    return not uw, uw
