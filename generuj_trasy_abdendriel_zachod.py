#!/usr/bin/env python3
"""Ab'Dendriel, daleka jaskinia na zachód (wejście z7 (32490,31697), wskazał Karol 26.10 „(32491,31694,z7)”). Dwie mapy:

  abdendriel_zachod_z8   pętla po z8 (wilki 19, węże 5), start = lądowanie po zasypanej dziurze z7 (32490,31697) (ŁOPATA)
  abdendriel_zachod_z9   pętla po z9 (trolle ok. 16), start = lądowanie po dziurze z8 (32480,31721)
Omijane: rotwormy (Karol 26.10; spawny na północy y<31630 i (32553,31680,z8), strefa 12 pól) i
poison spidery z8 (spawn (32487,31655), strefa 6 pól, ostrożność jak Thais północ).

Nic nie wysyła do gry (metoda jak generuj_trasy_abdendriel_trolle.py i generuj_trasy_edron_z9z.py):

  python3 -I generuj_trasy_abdendriel_zachod.py [--zapisz]     bez --zapisz tylko liczy i drukuje podsumowanie

Z --zapisz powstają: trasy/abdendriel_zachod_z{8,9}_petla, _dojscie (+ .meta), _do_depo (+ .meta), dane_tibia/mapy/abdendriel_zachod_z{8,9}.png/.json
(pętle; zapis bajt w bajt taki sam, gdy nic się nie zmieniło) i abdendriel_zachod_z{8,9}_dojscie.png. Wpis PLANY_PK: wyprawa.py; mapy.json: ręcznie.

DOJŚCIE Z DEPO (27.10, Karol: „dopisz dojście z miasta i powrót do miasta”; z mapy klienta, NIEPRZEJŚTE NA ŻYWO). Start = DEPO Ab'Dendriel
(32679,31687,z8) = PW.DEPO_STOI, ZASTĘPCZE/NIEPOMIERZONE jak w abdendriel_trolle i abdendriel_gobliny. Metoda ta sama co gobliny
(generuj_trasy_abdendriel_gobliny.py zbuduj(), JEDNO źródło geometrii: stałe G.*, nagranie, PW._astar):
  1. z8 nagranie Karola „depo -> trolle” do (32655,31677,z8), A* do pola POD schodami w górę (32654,31675,z8);
  2. SCHODY W GÓRĘ (32654,31674,z8), lądowanie z7 (32654,31673) (nagranie Karola 24.10 11:05 przeszło tędy);
  3. z7 A* po mapie (omija ogień i nauczone dziury) do pola obok zasypanej dziury (32490,31697,z7) (kolor 24 flaga 2);
  4. ŁOPATA/krok w dziurę (32490,31697,z7), lądowanie z8 (32490,31697) = start pętli z8 (pole liny tej dziury);
  5. (tylko z9) z8 A* do pola obok dziury (32480,31721,z8), dziura, lądowanie z9 (32480,31721) = start pętli z9 (pole liny).
POWRÓT DO DEPO (<nazwa>_do_depo, plik „do” planu PLANY_PK; NIEZWERYFIKOWANY NA ŻYWO):
  z9: stoimy (32480,31720,z9) (SĄSIAD z północy pola liny (32480,31721,z9), nie ono; reguła Karola 21.10; północ jak w planach trolli/Kazordoonu/Port Hope,
      bo stanie na (x, y+1) = pod lądowaniem daje w wypad.zbuduj_etapy etap "wlasne"), LINA z9 -> z8 (lądowanie (x, y+1) = (32480,31722,z8)),
      z8 A* do (32490,31696,z8) (dojście do pola stania idzie po polu liny z8 (32490,31697): przejście po nim nie jest użyciem liny), potem jak z8;
  z8: stoimy (32490,31696,z8) (sąsiad z północy pola liny (32490,31697,z8)), LINA z8 -> z7 (lądowanie (32490,31698,z7), tuż pod zasypaną dziurą), z7 A* do
      (32654,31673,z7), SCHODY W DÓŁ (32654,31674,z7), lądowanie z8 (32654,31675), korytarz x=32655, nagranie odwrócone do depo.
Pole liny zajęte przez potwora/gracza/przedmiot (reguła Karola 21.10) rozwiązuje wykonanie (pietra/wypad), nie trasa; pętla zaczyna się NA polu liny.
NIEZWERYFIKOWANE NA ŻYWO: położenie depo; obie liny (czy pod zasypaną dziurą z7 (32490,31697) powstaje pole liny; lina z9 (32480,31721) pod dziurą
z8); schody w dół z7 (32654,31674,z7) w drugą stronę; przejezdność z7 (drzewa, wilki) na 160 polach; łopata na (32490,31697,z7) (brak w pietra.ZASYPANE,
patrz STAN.md: bez PIETRA_LOPATA_AUTO=1 lub pamięci przejść bot ŁOPATY tu nie użyje). Wpis do spoty_nadzorca.json: osobna decyzja Karola (nie dopisany).
Omija rotwormy i poison spidery jak pętle (strefy zakazane z A*), ogień i nauczone dziury. OSY TRUJĄ: w opisie mapy; pola flagi 2 w kolorze podłogi
traktowane jak kandydaci na truciznę/ogień (bufor 1 = ściana). Test: testy/test_zachod_abdendriel.py.

PRZELICZENIE PĘTLI Z9 (27.10, ogień, pełny skan, dziury, optymalność; OFFLINE, z8 zostaje jak było, bajt w bajt):
  1. OGIEŃ: ogien_surowy()/ogien_pola() = ogien_stale.json + epizody z ogien_epizody.json (format 21.10: słownik "x,y,z" w kluczu `pola`) z "hp": true
     albo (gdy OGIEN_EPIZODY_MIN_N ustawione) n >= OGIEN_EPIZODY_MIN_N, bufor 1; stan 27.10: tylko hp, bo n>=3 rozcina labirynt (zob. stała). generuj_trasy_edron_wschod.ogien_pola() epizodów w tym formacie NIE czytał
     (czyta tylko klucze "x,y,z" na wierzchu), więc dotąd generator widział sam ogień stały; z8 dalej liczy po staremu (jego pętla jest sprawdzona na żywo).
  2. SKAN: z9 skanuje przeszkody (flaga 2 w kolorze podłogi) w obszarze SKŁADOWEJ (bbox + MARGINES_SKANU, iteracja do stabilności: skladowa_ze_skanem),
     nie w stałym SKAN (tam leżało 24 z 57 pól; pętla z9 sięga x 32396..32531, y 31573..31733).
  3. DZIURY: trasy/dziury_omijaj.json (z9: 35 pól nad chodliwym z10, z8: (32513,31656)) = ściana A* pętli, dojścia i powrotu, a pola z9 dostają ZAWSZE bufor 1
     (upadek = smoki). Przeszkody bez podłoża pod spodem (22 pola) dostają bufor 1 jak dotąd, z wyjątkiem BUFOR_WYJATKI9 (bufor zamykał wąskie przejście).
  4. OPTYMALNOŚĆ: pętla z9 = DOKŁADNY najkrótszy cykl (held_karp), a gdy cykl przez wszystkie przystanki przekracza PETLA9_LIMIT * PETLA9_BAZA[0] pól,
     spośród wszystkich podzbiorów przystanków wybierany jest ten z największą liczbą potworów mieszczący się w limicie (przystanki za labiryntem, np. za polem ognia
     w wąskim korytarzu, kosztują setki pól za kilku potworów). Drukowane: cykl przez wszystkie, wybrany podzbiór, odpadłe przystanki.
  5. waskie_gardla(): lista punktów pętli, gdzie pas wolnych pól ma szerokość 1 PRZEZ zagrożenie (bufor/ogień/przeszkoda/dziura), do oceny orbit bota.
Z8 (pętla, dojście, powrót) liczy się dokładnie jak przed 27.10 (stały SKAN, ogień stały, spot_lib.petla); nowe ściany jej nie ruszają (test 1a-1c).
"""
import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generuj_powrot_abdendriel as PW  # noqa: E402  (DEPO_STOI, NAGRANIE, _astar)
import generuj_trasy_abdendriel_gobliny as G  # noqa: E402  (stałe odcinka depo -> schody -> z7: jedno źródło geometrii)
import generuj_trasy_abdendriel_trolle as AB  # noqa: E402  (obrazy)
import generuj_trasy_edron_wschod as _ogn  # noqa: E402
import mapa as _mapa  # noqa: E402
import spot_lib  # noqa: E402
import trasa_io  # noqa: E402
from spot_lib import chodliwe, ladowanie, petla, przystanki, skladowa  # noqa: E402

NAZWA = "abdendriel_zachod"
CEL8 = ("wolf", "snake")
CEL9 = ("troll",)
ZAKAZANE = ("rotworm", "poison spider")
STREFA = {"rotworm": 12, "poison spider": 6}
BUFOR = 1
SKAN = (32430, 31640, 32545, 31745)           # LEGACY prostokąt skanu przeszkód w kolorze podłogi (x0, y0, x1, y1), z8..z10: tylko z8 (jego pętla jest sprawdzona na żywo, bajt w bajt jak dotąd)
MARGINES_SKANU = 8                            # 27.10: z9 skanuje przeszkody w obszarze SKŁADOWEJ (bbox + tyle pól), nie w stałym prostokącie
OGIEN_EPIZODY_MIN_N = None                    # 27.10: epizody ognia (trasy/ogien_epizody.json) liczą się z "hp": true (jak w bocie: _ogien_parzy_dane) albo od tylu wykryć (None = tylko hp).
                                              #   n>=3 BEZ spadku HP dawało 21 pól na z9 przy samych przystankach walki ((32428,31694), (32433..32442,31731), (32505..32508,31711..31713)) i
                                              #   rozcinało labirynt (składowa 2343 -> 1212 pól, 11 przystanków/32 potwory); to szum wykrywania przy walce, a plik rośnie, gdy bot gra
BUFOR_WYJATKI9 = set()                        # 27.10: przeszkody z9 (flaga 2 w kolorze podłogi, nie z listy dziur) BEZ bufora (ściana, sąsiedzi wolni); PUSTE: przeszukanie pokazało, że wyjątki
                                              #   (np. (32410,31673,9): odblokowuje pokój (32406..32412,31671..31674) od południa) dają co najwyżej +1 potwora/-4 pola, a robią dokładnie
                                              #   wąskie przejście, w którym bot orbitował; dziury z dziury_omijaj mają ZAWSZE bufor 1
PETLA9_BAZA = (1163, 19, 50)                  # pętla z9 przed 27.10 (długość, przystanki, potwory): odniesienie dla limitu wydłużenia
PETLA9_LIMIT = 1.10                           # pętla z9 nie dłuższa niż 110% bazy: przystanek o najgorszym koszcie na potwora wylatuje (zob. petla_opt)
H7 = (32490, 31697, 7)                        # zasypana dziura z7 (kolor 24) -> z8
H8 = [(32480, 31721, 8), (32513, 31656, 8)]   # dziury z8 -> z9
PIETRA = (8, 9)


def dziury_nauczone():
    import json
    return {tuple(p) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])}


def dziury_omijaj():
    """27.10: ręczna lista trasy/dziury_omijaj.json (bot: ściana we wszystkich ścieżkach ruchu); z9: 35 pól nad chodliwym z10 (smoki) + (32513,31656,8)."""
    import json
    return {tuple(p[:3]) for p in json.loads((ROOT / "trasy" / "dziury_omijaj.json").read_text()).get("dziury", [])}


def ogien_surowy():
    """Pola ognia BEZ bufora: trasy/ogien_stale.json + epizody z ogien_epizody.json (format 21.10: słownik "x,y,z" w kluczu `pola`) z "hp": true
    albo (gdy ustawione) n >= OGIEN_EPIZODY_MIN_N. 27.10: generuj_trasy_edron_wschod.ogien_pola() czyta z epizodów tylko starszy format (klucze "x,y,z" na wierzchu),
    więc epizody w formacie 21.10 do tej pory NIE były uwzględniane przez ten generator; edron_wschod zostaje bez zmian (ma własne trasy)."""
    import json
    pola = {tuple(p[:3]) for p in json.loads((ROOT / "trasy" / "ogien_stale.json").read_text()).get("pola", [])}
    try:
        ep = json.loads((ROOT / "trasy" / "ogien_epizody.json").read_text())
    except (OSError, ValueError):
        ep = {}
    ep = ep.get("pola", ep) if isinstance(ep, dict) else {}
    for k, v in (ep.items() if isinstance(ep, dict) else ()):
        if isinstance(k, str) and k.count(",") == 2 and isinstance(v, dict) and (v.get("hp") or (OGIEN_EPIZODY_MIN_N is not None and v.get("n", 0) >= OGIEN_EPIZODY_MIN_N)):
            pola.add(tuple(int(a) for a in k.split(",")))
    return pola


def ogien_pola():
    """Ogień (stały + epizody) z buforem BUFOR = ściana dla A* i składowych."""
    return z_buforem(ogien_surowy())


def skan_przeszkod(m, z, obszar):
    """Pola (x, y, z) w prostokącie `obszar` (x0, y0, x1, y1) z flagą 2 w kolorze podłogi (przeszkody: ogień, trucizna itp., nie przejścia pięter)."""
    out = []
    x0, y0, x1, y1 = obszar
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            f = m.flagi(x, y, z)
            if f & _mapa.WIDZIANE and not f & _mapa.SCIANA and f & _mapa.BEZ_DROGI and spot_lib.przeszkoda_na_podlodze(m, x, y, z):
                out.append((x, y, z))
    return out


def przeszkody(m):
    """LEGACY (z8): skan w stałym prostokącie SKAN, piętra z PIETRA."""
    out = []
    for z in PIETRA:
        out += skan_przeszkod(m, z, SKAN)
    return out


def z_buforem(pola):
    return {(x + dx, y + dy, z) for x, y, z in pola for dx in range(-BUFOR, BUFOR + 1) for dy in range(-BUFOR, BUFOR + 1)}


def stoj_obok(m, start, T, zle):
    """(pole obok T, droga [(x,y,z)] od start bez startu, z polem obok): najkrótsza po chodliwych sąsiadach T poza `zle`."""
    z = T[2]
    best = None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            c = (T[0] + dx, T[1] + dy, z)
            if (dx or dy) and chodliwe(m, c) and c not in zle:
                d = [] if c == tuple(start) else m.droga(start, c, zajete=sorted(zle), dlugosc=0, limit=3000000)
                if d is None:
                    continue
                d = [(q[0], q[1], z) for q in d]
                if best is None or len(d) < len(best[1]):
                    best = (c, d)
    if best is None:
        raise SystemExit(f"brak drogi {start} -> sąsiad przejścia {T}")
    return best


def skladowa_ze_skanem(m, z, start, stale_sciany, hazard_dodatkowy):
    """27.10: składowa piętra z od `start` ze skanem przeszkód w jej własnym obszarze (bbox + MARGINES_SKANU), nie w stałym prostokącie.
    Iteracja: składowa bez przeszkód (nadzbiór) -> skan w jej bbox -> składowa ze ścianami przeszkód -> mniejszy bbox ... aż bbox się nie zmieni.
    `stale_sciany`: pola (x,y,z) ściany bez bufora i bez skanu (ogień z buforem, strefy, dziury nauczone), `hazard_dodatkowy`: pola zagrożeń
    (dziury z listy omijaj) dostające bufor jak przeszkody. Zwraca (comp, przeszkody_skan, sciana_piętra, obszar_skanu)."""
    def sciana(prz):
        zag = set(prz) | hazard_dodatkowy
        buf = (zag - BUFOR_WYJATKI9) if z == 9 else zag                      # wyjątki: ściana bez bufora
        return {p for p in stale_sciany if p[2] == z} | zag | {p for p in z_buforem(buf) if p[2] == z}
    comp = skladowa(m, start, sorted(sciana([])))
    obszar = None
    for _ in range(20):
        nowy = (min(c[0] for c in comp) - MARGINES_SKANU, min(c[1] for c in comp) - MARGINES_SKANU,
                max(c[0] for c in comp) + MARGINES_SKANU, max(c[1] for c in comp) + MARGINES_SKANU)
        if nowy == obszar:
            break
        obszar = nowy
        prz = skan_przeszkod(m, z, obszar)
        sc = sciana(prz)
        if tuple(start) in sc:
            raise SystemExit(f"start {start} w ścianie (ogień/przeszkoda/dziura z buforem)")
        comp = skladowa(m, start, sorted(sc))
    else:
        raise SystemExit("skan składowej nie ustabilizował się w 20 iteracjach")
    return comp, prz, sc, obszar


def macierz_drog(m, z, wezly, sciana):
    """Macierz długości A* (pola) między węzłami [(x, y)...] na piętrze z, po mapie z `sciana`; brak drogi = SystemExit."""
    n = len(wezly)
    D = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                d = m.droga((wezly[i][0], wezly[i][1], z), wezly[j], zajete=sciana, dlugosc=0, limit=400000)
                if d is None:
                    raise SystemExit(f"brak drogi {wezly[i]} -> {wezly[j]} (z{z})")
                D[i][j] = len(d)
    return D


def held_karp(D, ns=None, limit=None):
    """Najkrótszy cykl od węzła 0 (programowanie dynamiczne po podzbiorach, DOKŁADNIE; do 19 węzłów). Bez `limit`: cykl przez WSZYSTKIE węzły.
    Z `limit` (i wagami `ns` węzłów, ns[0] = 0): spośród wszystkich podzbiorów węzłów wybiera cykl o największej sumie wag (potwory) o długości <= limit;
    remis: krótszy, potem więcej węzłów. Zwraca (kolejność [0, ...], długość). Kierunek cyklu: ten z mniejszym numerem drugiego węzła (determinizm)."""
    n = len(D)
    if n == 1:
        return [0], 0
    if n > 19:
        raise SystemExit(f"held_karp: {n} węzłów to za dużo na dokładne rozwiązanie")
    INF = 10 ** 9
    pe = 1 << (n - 1)
    dp = [[INF] * (n - 1) for _ in range(pe)]
    par = [[-1] * (n - 1) for _ in range(pe)]
    for j in range(n - 1):
        dp[1 << j][j] = D[0][j + 1]
    for S in range(1, pe):
        dpS = dp[S]
        for j in range(n - 1):
            c = dpS[j]
            if c >= INF or not S >> j & 1:
                continue
            Dj = D[j + 1]
            for k in range(n - 1):
                if S >> k & 1:
                    continue
                v = c + Dj[k + 1]
                S2 = S | 1 << k
                if v < dp[S2][k]:
                    dp[S2][k], par[S2][k] = v, j
    wybor = None
    for S in range(1, pe):
        if limit is None and S != pe - 1:
            continue
        j = min((j for j in range(n - 1) if S >> j & 1), key=lambda j: (dp[S][j] + D[j + 1][0], j))
        dl = dp[S][j] + D[j + 1][0]
        if limit is not None and dl > limit:
            continue
        klucz = (-sum(ns[k + 1] for k in range(n - 1) if S >> k & 1), dl, -bin(S).count("1")) if limit is not None else (dl,)
        if wybor is None or klucz < wybor[0]:
            wybor = (klucz, S, j, dl)
    if wybor is None:
        return [0], 0
    _, S, j, dl = wybor
    kol = []
    while j != -1:
        kol.append(j + 1)
        pj = par[S][j]
        S ^= 1 << j
        j = pj
    kol = kol[::-1]
    if len(kol) > 1 and kol[-1] < kol[0]:
        kol = kol[::-1]
    return [0] + kol, dl


def petla_opt(m, z, start, stops, sciana, limit):
    """27.10 (z9): pętla po przystankach jako DOKŁADNY najkrótszy cykl (held_karp), nie najbliższy sąsiad + 2-opt. Gdy cykl przez wszystkie przystanki jest
    dłuższy niż `limit` pól, spośród WSZYSTKICH podzbiorów przystanków bierzemy ten z największą liczbą potworów, którego cykl mieści się w limicie
    (przystanek za labiryntem kosztuje setki pól za kilku potworów). Zwraca (przystanki w kolejności węzłów, odpadłe [(pt, n)], kolejność, węzły, pełna trasa)."""
    wezly = [tuple(start)] + [t["pt"] for t in stops]
    D = macierz_drog(m, z, wezly, sciana)
    _, dl_wszystkie = held_karp(D)
    ns = [0] + [t["n"] for t in stops]
    kol, dl = held_karp(D, ns, limit) if dl_wszystkie > limit else held_karp(D)
    zostaja = sorted(set(kol) - {0})
    odpadle = [(stops[i - 1]["pt"], stops[i - 1]["n"]) for i in range(1, len(wezly)) if i not in zostaja]
    print(f"z{z}: cykl przez wszystkie {len(stops)} przystanków = {dl_wszystkie} pól (limit {limit}); wybrany podzbiór {len(zostaja)} przystanków, cykl {dl}"
          + (f", odpadły: {odpadle}" if odpadle else ""))
    # przenumerowanie: węzły = start + zostające przystanki w kolejności wejścia
    nowe = [0] + zostaja
    st = [stops[i - 1] for i in zostaja]
    wezly2 = [wezly[i] for i in nowe]
    stary_na_nowy = {i: k for k, i in enumerate(nowe)}
    kol2 = [stary_na_nowy[i] for i in kol]
    pelna = [wezly2[0]]
    for i in range(len(wezly2)):
        a, b2 = kol2[i], kol2[(i + 1) % len(wezly2)]
        d = m.droga((wezly2[a][0], wezly2[a][1], z), wezly2[b2], zajete=sciana, dlugosc=0, limit=400000)
        pelna += [(q[0], q[1]) for q in d]
    if len(pelna) - 1 != dl:
        raise SystemExit(f"petla_opt: długość trasy {len(pelna) - 1} != cykl {dl}")
    return st, odpadle, kol2, wezly2, pelna


def waskie_gardla(m, comp, zle, pelna, z):
    """Punkty pętli, w których pas wolnych pól ma szerokość 1 PRZEZ ZAGROŻENIE: po obu stronach (jedna z czterech osi) pole niedostępne dla pętli,
    a co najmniej jedno z nich to chodliwe pole mapy zajęte przez bufor/ogień/przeszkodę/dziurę (`zle`), nie zwykła ściana jaskini. Zwraca posortowaną
    listę (x, y) bez powtórzeń. Korytarze jaskini między ścianami (szerokość 1 z natury) nie są tu liczone."""
    out = set()
    for x, y in set(pelna):
        for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
            a, b2 = (x + dx, y + dy), (x - dx, y - dy)
            if a in comp or b2 in comp:
                continue
            if any((q[0], q[1], z) in zle and spot_lib.chodliwe(m, (q[0], q[1], z)) for q in (a, b2)):
                out.add((x, y))
                break
    return sorted(out)


def zbuduj():
    m = _mapa.Mapa()
    dz_n = dziury_nauczone()
    om = dziury_omijaj()
    dz = dz_n | om                                   # 27.10: lista omijaj = ściana A* pętli i dojścia (jak w bocie), nie tylko nauczone
    ogien_s = ogien_surowy()
    ogien = z_buforem(ogien_s)
    prz_leg = przeszkody(m)                          # LEGACY (stały SKAN): tylko z8
    zakazane = {z: [s for n in ZAKAZANE for s in spot_lib.spawny(z, (n,), (32380, 32640, 31560, 31800))
                    for s in [dict(s, nazwa=n)]] for z in PIETRA}
    strefa = set()
    for z in PIETRA:
        for s in zakazane[z]:
            strefa |= spot_lib.strefa_zakazana([s], z, STREFA[s["nazwa"]])
    # z8: jak dotąd (stały skan, ogień stały bez epizodów, bufor 1) — pętla sprawdzona na żywo; nowe ściany (epizody ognia, dziura (32513,31656,8)) jej nie ruszają (sprawdza test)
    zle8 = {p for p in z_buforem(prz_leg) | _ogn.ogien_pola() | strefa if p[2] == 8}
    sciana8 = [p for p in dz if p[2] == 8] + sorted(zle8)
    print(f"przeszkody z8 w stałym skanie: {len([p for p in prz_leg if p[2] == 8])}; ogień surowy: {len(ogien_s)} pól (stały + epizody hp, próg n: {OGIEN_EPIZODY_MIN_N}), "
          f"z buforem {len(ogien)}; dziury z listy omijaj: {len(om)}; zakazane spawny: "
          f"{ {z: [(s['nazwa'], s['x'], s['y']) for s in zakazane[z]] for z in PIETRA} }")
    L8 = ladowanie(m, H7)
    comp8 = skladowa(m, L8, sciana8)
    best = None
    for T in H8:
        if T in dz:
            print(f"dziura {T}: na liście dziur (omijaj/nauczone), nie schodzimy tędy"); continue
        L9c = ladowanie(m, T)
        wsrod = any((T[0] + a, T[1] + b) in comp8 for a in (-1, 0, 1) for b in (-1, 0, 1))
        print(f"dziura z8 {T[:2]}: w składowej z8 {wsrod}, lądowanie z9 {L9c[:2]}")
        if wsrod and best is None:
            best = (T, L9c)
    T8, L9 = best
    # z9: skan przeszkód w obszarze składowej, ogień z epizodami, dziury z listy omijaj (bufor 1), strefy zakazane
    stale9 = {p for p in ogien | strefa | {p for p in dz_n} if p[2] == 9}
    comp9, prz9, sciana9_set, obszar9 = skladowa_ze_skanem(m, 9, L9, stale9, {p for p in om if p[2] == 9})
    sciana9 = sorted(sciana9_set | {p for p in dz if p[2] == 9})
    nprz9 = len(prz9)
    print(f"z9: skan przeszkód w obszarze składowej {obszar9} (stały SKAN był {SKAN}): {nprz9} pól flaga 2 w kolorze podłogi, w tym {len([p for p in prz9 if p in om])} z listy omijaj, "
          f"{len(BUFOR_WYJATKI9)} wyjątków bez bufora")
    zle9 = {p for p in sciana9_set}
    zle = {p for p in zle8} | {p for p in ogien if p[2] != 9} | {p for p in strefa if p[2] not in (8, 9)} | zle9
    prz = [p for p in prz_leg if p[2] == 8] + list(prz9)
    pet = {}
    for z, L, comp, cel, sciana_z in ((8, L8, comp8, CEL8, sciana8), (9, L9, comp9, CEL9, sciana9)):
        obsz = (min(c[0] for c in comp) - 5, max(c[0] for c in comp) + 5, min(c[1] for c in comp) - 5, max(c[1] for c in comp) + 5)
        for n in ZAKAZANE:
            w = [(p[0], p[1]) for p in strefa if p[2] == z and (p[0], p[1]) in comp]
            print(f"z{z}: pól składowej w strefach zakazanych (wycięte): {len(w)}")
        st = przystanki(spot_lib.spawny(z, cel, obsz), comp)
        if z == 8:
            order, nodes, pelna = petla(m, z, L[:2], st, sciana_z)
        else:
            n_wszystkie = (len(st), sum(t["n"] for t in st))
            limit = int(PETLA9_BAZA[0] * PETLA9_LIMIT)
            st, odpadle, order, nodes, pelna = petla_opt(m, z, L[:2], st, sciana_z, limit)
            print(f"z9: przystanki w składowej {n_wszystkie[0]} ({n_wszystkie[1]} potw.), po limicie {len(st)}; baza przed 27.10: {PETLA9_BAZA[1]} przystanków, {PETLA9_BAZA[2]} potworów, "
                  f"pętla {PETLA9_BAZA[0]} pól; limit długości {limit}")
        bad = [p for p in pelna if (p[0], p[1], z) in zle or (p[0], p[1], z) in dz]
        if bad:
            raise SystemExit(f"z{z}: pętla wchodzi w strefę zakazaną/ogień/przeszkodę/dziurę: {bad[:5]}")
        n = sum(t["n"] for t in st)
        print(f"{NAZWA}_z{z}: składowa {len(comp)} pól (z uwzględnieniem stref), przystanków {len(st)}, potworów {n}, pętla {len(pelna)} pól, start {L[:2]}, kolejność {order}")
        pet[z] = (L, comp, st, order, nodes, pelna, strefa if z == 8 else None)
    gardla = waskie_gardla(m, comp9, zle, pet[9][5], 9)
    print(f"z9: wąskie gardła pętli (pas szerokości 1 przez bufor/ogień/przeszkodę/dziurę): {len(gardla)} pól: {gardla}")
    # --- wspólny odcinek depo -> schody w górę (jak gobliny): nagranie z8, A* do pola pod schodami ---
    nagr, _ = trasa_io.wczytaj(PW.NAGRANIE)
    if tuple(nagr[0]) != PW.DEPO_STOI:
        raise SystemExit(f"nagranie zaczyna się w {nagr[0]}, a DEPO_STOI to {PW.DEPO_STOI}")
    i7 = next(i for i, q in enumerate(nagr) if q[2] == 7)
    nagr8 = nagr[:i7 - 1]
    if nagr8[-1] != G.NAGRANIE_Z8_DO or any(q[2] != 8 for q in nagr8) or nagr[i7] != G.LAD7:
        raise SystemExit("odcinek z8 nagrania niespójny")
    zz = set(zle)
    z8_k = PW._astar(m, G.NAGRANIE_Z8_DO, G.STOI8, [p for p in zz if p[2] == 8], dz)
    depo_doj = list(nagr8) + z8_k                          # kończy się G.STOI8 (pole pod schodami w górę)
    c7, d7 = stoj_obok(m, G.LAD7, H7, zz | dz)             # z7: lądowanie schodów -> pole obok zasypanej dziury (z polem obok)
    # --- pola lin powrotu: stoimy na SĄSIEDZIE pola liny (z północy), nie na nim (reguła Karola 21.10); lądowanie liny = (x, y+1) piętro wyżej ---
    STOI8R, LAD7R = (H7[0], H7[1] - 1, 8), (H7[0], H7[1] + 1, 7)             # lina z8 (32490,31697) -> z7 (x, y+1); stoimy N od pola liny
    STOI9R, LAD8R = (L9[0], L9[1] - 1, 9), (L9[0], L9[1] + 1, 8)             # lina z9 (32480,31721) -> z8 (x, y+1); stoimy N od pola liny
    for q in (STOI8R, LAD7R, STOI9R, LAD8R):
        if not chodliwe(m, q) or m.flagi(*q) & _mapa.BEZ_DROGI or q in zz or q in dz:
            raise SystemExit(f"pole liny powrotu {q}: niechodliwe, flaga 2, strefa zakazana albo nauczona dziura")
    r7 = PW._astar(m, LAD7R, G.LAD7, [p for p in zz if p[2] == 7], dz)       # z7 z lądowania liny do pola nad schodami w dół
    r8 = PW._astar(m, LAD8R, STOI8R, [p for p in zz if p[2] == 8], dz)       # z8 z lądowania liny z9 do pola stania liny z8

    # ---------------------------------------------------------------- DOJŚCIE ---------------------------------------------------------------
    opis_start = (f"depo Ab'Dendriel {PW.DEPO_STOI[:2]} z8 (ZASTĘPCZE, NIEPOMIERZONE), początek nagrania „depo -> trolle”; dojście z mapy klienta 27.10, "
                  "NIEPRZEJŚTE NA ŻYWO; z dowolnego punktu tej drogi dojście bierze najbliższy punkt")
    pts = list(depo_doj)
    meta = [{"idx": 0, "typ": "start", "komentarz": opis_start},
            {"idx": len(pts) - 1, "typ": "przed_zmiana_pietra",
             "komentarz": f"SCHODY W GÓRĘ {G.SCHODY8[:2]} z8 (flaga 2, kolor 210) na północ od pola stania {G.STOI8[:2]} (krok na północ); lądowanie (x, y-1) = {G.LAD7[:2]} z7. "
                          "Nagranie Karola 24.10 11:05 przeszło tędy"}]
    pts.append(G.LAD7)
    meta.append({"idx": len(pts) - 1, "typ": "schody_w_gore", "komentarz": f"lądowanie z7 {G.LAD7[:2]} tuż nad schodami w dół {G.SCHODY7_DOL[:2]} z7: NIE schodzić z powrotem"})

    def dodaj(lista):
        for q in lista:
            if q != pts[-1]:
                pts.append(q)

    def przejscie(T, L, opis_przed, opis_lad):
        pts.append(T)
        meta.append({"idx": len(pts) - 1, "typ": "przed_zmiana_pietra", "komentarz": opis_przed})
        pts.append(L)
        meta.append({"idx": len(pts) - 1, "typ": "schody_w_dol", "komentarz": opis_lad})

    dodaj(d7)
    przejscie(H7, L8, f"z7 {H7[:2]} kolor 24 flaga 2 = ZASYPANA DZIURA -> ŁOPATA (niepotwierdzone na żywo; po otwartej dziurze zwykły krok); wskazał Karol 26.10 (32491,31694). "
                      f"Dojście z7: A* od lądowania schodów {G.LAD7[:2]} ({len(d7)} pól) do pola obok dziury {c7[:2]}",
              f"lądowanie z8 {L8[:2]} (składowa {len(comp8)} pól, wilki/węże); to pole liny tej dziury, pętla zaczyna się na nim")
    dojscia = {8: (list(pts), [dict(e) for e in meta])}
    c8, d8 = stoj_obok(m, L8, T8, zz | dz)
    dodaj(d8)
    przejscie(T8, L9, f"DZIURA z8 {T8[:2]} (kolor 210, flaga 2; pod nią z9 ten sam (x,y) = pole liny) -> z9 trolle; niepotwierdzone na żywo",
              f"lądowanie z9 {L9[:2]} (składowa {len(comp9)} pól); pole liny tej dziury, zejść z niego")
    dojscia[9] = (list(pts), [dict(e) for e in meta])
    for z in PIETRA:
        print(f"{NAZWA}_z{z}_dojscie: {len(dojscia[z][0])} punktów, długość {trasa_io.dlugosc(dojscia[z][0])} pól")

    # ---------------------------------------------------------------- POWRÓT ----------------------------------------------------------------
    def lina_z8(pw, mp):
        """Dopisuje: stoi (STOI8R, ostatni punkt pw), LINA z8 -> z7, z7 A*, schody w dół, z8 korytarz, nagranie odwrócone do depo."""
        mp.append({"idx": len(pw) - 1, "typ": "przed_zmiana_pietra",
                   "komentarz": f"LINA na polu {H7[:2]} z8 (pole liny pod zasypaną dziurą z7 {H7[:2]}, lądowanie dojścia): stoimy OBOK na {STOI8R[:2]} (północ), pole liny wolne; "
                                f"lądowanie (x, y+1) = {LAD7R[:2]} z7, tuż pod dziurą. NIEZWERYFIKOWANE na żywo; potrzebna LINA w plecaku"})
        pw.append(LAD7R)
        mp.append({"idx": len(pw) - 1, "typ": "schody_w_gore", "komentarz": f"lądowanie z7 {LAD7R[:2]} tuż pod zasypaną dziurą z7 {H7[:2]}: NIE wchodzić na dziurę"})
        pw += list(r7)
        mp.append({"idx": len(pw) - 1, "typ": "przed_zmiana_pietra",
                   "komentarz": f"SCHODY W DÓŁ {G.SCHODY7_DOL[:2]} z7 (flaga 2 na z7 i z8) na południe od pola stania {G.LAD7[:2]}; lądowanie z8 (x, y+1) = {G.LAD8[:2]}. "
                                "Nagranie Karola (pkt 26 -> 27) zeszło tędy; NIEZWERYFIKOWANE w pętli powrotu"})
        pw.append(G.LAD8)
        mp.append({"idx": len(pw) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z8 {G.LAD8[:2]}; obok schody w górę {G.SCHODY8[:2]}: NIE wchodzić, idź korytarzem x=32655"})
        pw += list(reversed(z8_k[:-1])) + [G.NAGRANIE_Z8_DO]
        pw += list(reversed(nagr8[:-1]))
        mp.append({"idx": len(pw) - 1, "typ": "koniec", "komentarz": f"{PW.DEPO_STOI[:2]} z8 = początek nagrania „depo -> trolle”; położenie depo NIEPOMIERZONE (zastępcza decyzja)"})

    powroty = {}
    pw8, mp8 = [STOI8R], [{"idx": 0, "typ": "start", "komentarz": f"z8 pole stania {STOI8R[:2]} obok pola liny {H7[:2]} (start pętli z8; bot dojdzie tu z dowolnego punktu pętli po z8); "
                                                                f"powrót z mapy klienta 27.10, NIEZWERYFIKOWANY na żywo"}]
    lina_z8(pw8, mp8)
    powroty[8] = (pw8, mp8)
    pw9, mp9 = [STOI9R], [{"idx": 0, "typ": "start", "komentarz": f"z9 pole stania {STOI9R[:2]} obok pola liny {L9[:2]} (start pętli z9; bot dojdzie tu z dowolnego punktu pętli po z9); "
                                                                f"powrót z mapy klienta 27.10, NIEZWERYFIKOWANY na żywo"}]
    mp9.append({"idx": 0, "typ": "przed_zmiana_pietra",
                "komentarz": f"LINA na polu {L9[:2]} z9 (pole liny pod dziurą z8 {T8[:2]}, lądowanie dojścia): stoimy OBOK na {STOI9R[:2]} (północ), pole liny wolne; "
                             f"lądowanie (x, y+1) = {LAD8R[:2]} z8. NIEZWERYFIKOWANE na żywo; potrzebna LINA w plecaku"})
    pw9.append(LAD8R)
    mp9.append({"idx": 1, "typ": "schody_w_gore", "komentarz": f"lądowanie z8 {LAD8R[:2]} tuż pod dziurą z8 {T8[:2]}: NIE wchodzić na dziurę; dalej A* po z8 do {STOI8R[:2]}"})
    pw9 += list(r8)
    lina_z8(pw9, mp9)
    powroty[9] = (pw9, mp9)
    # powrót z8 = ogon powrotu z9 od STOI8R (jedna geometria)
    i_s = pw9.index(STOI8R)
    if pw9[i_s:] != pw8:
        raise SystemExit("powrót z8 nie jest ogonem powrotu z9")
    # --- kontrole ---
    przej_doj = {8: [(G.STOI8, G.LAD7), (H7, L8)], 9: [(G.STOI8, G.LAD7), (H7, L8), (T8, L9)]}
    przej_pow = {8: [(STOI8R, LAD7R), (G.LAD7, G.LAD8)], 9: [(STOI9R, LAD8R), (STOI8R, LAD7R), (G.LAD7, G.LAD8)]}
    for z in PIETRA:
        kontrole(m, dojscia[z][0], zz, dz, dozw={H7, T8}, przej=przej_doj[z], nazwa=f"{NAZWA}_z{z}_dojscie")
        kontrole(m, powroty[z][0], zz, dz, dozw=(), przej=przej_pow[z], nazwa=f"{NAZWA}_z{z}_do_depo")
        print(f"{NAZWA}_z{z}_do_depo: {len(powroty[z][0])} punktów, długość {trasa_io.dlugosc(powroty[z][0])} pól")
    return m, pet, dojscia, powroty, prz, zz, dz


def kontrole(m, pts, zle, dz, dozw=(), przej=(), nazwa=""):
    """Twarde warunki trasy: ciągłość (skok > 1 pole na jednym piętrze tylko w nagraniu z8, <= 4), brak ścian/niewidzianych, flaga 2 tylko w polach `dozw`
    (zasypana dziura/dziura jako pole przejścia), zero punktów w strefie zakazanej, ogniu i nauczonych dziurach, a zmiany pięter dokładnie jak `przej`
    ((z_pola, na_pole) w kolejności)."""
    bl = []
    for a, b in zip(pts, pts[1:]):
        if a[2] == b[2] and max(abs(a[0] - b[0]), abs(a[1] - b[1])) > 1 and not (a[2] == 8 and max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 4):
            bl.append(f"skok {a}->{b}")
    zm = [(a, b) for a, b in zip(pts, pts[1:]) if a[2] != b[2]]
    if zm != list(przej):
        bl.append(f"przejścia pięter {zm} != oczekiwane {list(przej)}")
    for q in pts:
        f = m.flagi(*q)
        if not f & _mapa.WIDZIANE or f & _mapa.SCIANA:
            bl.append(f"ściana/niewidziane {q}")
        elif f & _mapa.BEZ_DROGI and q not in dozw:
            bl.append(f"flaga 2 (przejście/dziura) w trasie {q}")
        if q in zle:
            bl.append(f"strefa zakazana/ogień/przeszkoda {q}")
        if q in dz:
            bl.append(f"nauczona dziura {q}")
    if bl:
        raise SystemExit(f"trasa {nazwa} niepoprawna: " + "; ".join(bl[:6]))
    print(f"kontrole {nazwa}: {len(pts)} pkt, zero ścian/flagi 2 poza przejściem/stref zakazanych/ognia/nauczonych dziur, zmiany pięter {len(zm)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m, pet, dojscia, powroty, prz, zle, dz = zbuduj()
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    for z in PIETRA:
        L, comp, st, order, nodes, pelna, str_ = pet[z]
        doj, meta = dojscia[z]
        spot_lib.zapis_spotu(m, f"{NAZWA}_z{z}", z, pelna, order, nodes, st, f"Ab'Dendriel zachod z{z}", jedn="potw.", opis_przyst="spawn(y) wilkow/wezy/trolli",
                             doj=doj, meta=meta, strefa=str_)
        pw, mp = powroty[z]
        trasa_io.zapisz(f"{NAZWA}_z{z}_do_depo", pw, mp)
        kand = [(x, y, zz, 0) for x, y, zz in prz]
        wyniki = {z: (comp, st, order, nodes, pelna)}
        panele = [(8, 32648, 32690, 31664, 31694, "z8: depo (zast.) -> schody w gore (32654,31674)"),
                  (7, 32484, 32660, 31666, 31720, "z7: od schodow (32654,31673) do zasypanej dziury (32490,31697)"),
                  (8, 32468, 32502, 31686, 31728, "z8: ladowanie (32490,31697); dziura (32480,31721)" + ("; petla niebieska" if z == 8 else ""))]
        uklad = [[0, 2], [1]]
        if z == 9:
            panele.append((9, 32468, 32502, 31710, 31728, "z9: ladowanie (32480,31721); petla niebieska"))
            uklad = [[0, 2, 3], [1]]
        AB.obrazy(m, kand, zle, wyniki, doj, spot_lib.OBRAZY / f"{NAZWA}_z{z}_dojscie.png", panele, uklad)
    print("zapisano trasy/ (pętle, dojścia i powroty z .meta) i dane_tibia/mapy/ (PNG+JSON pętli, PNG dojść); mapy.json, PLANY_PK i spoty_nadzorca.json osobno")


if __name__ == "__main__":
    main()
