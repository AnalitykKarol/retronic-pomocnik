"""Serwis Thais, depo (22.10, wydra, `refill.sh --tlo`): droga do stanowiska depo (32352,32226,7) i pole schodów (32350,32226,7).

Awaria: marsz do niszy depo skończył na piętrze wyżej („nie doszedłem do (32352, 32226, 7) (stoję w (32349, 32225, 6))”).
Plan A* nie zawiera pola schodów (Graf.idzie pomija flagę 2), ale (1) rzadkie punkty planu mogą ciąć róg ściany (odcinek
(32350,32227)->(32352,32228) idzie przez ścianę (32351,32227)), (2) idz_pewnie klika w mapę po 5 pól, a klient prowadzi klik własną
drogą (8 kierunków), więc pole schodów w prostokącie poz-klik, choć poza naszą ścieżką, wciąga postać na inne piętro (S: wynik „pietro”
-> marsz oddaje zapasowemu chodzikowi), (3) zapasowy chodzik (CavebotDojscie) chronił schody tylko na trasie wielopiętrowej.
Test: prawdziwa mapa klienta (map74.otmm), atrapy postaci i kliku (klient modelowany: klik przez prostokąt ze schodami = zmiana piętra),
stary kod z `serwis.py.bak-20261022-schody-planer` (jeśli jest) musi tu paść, nowy przejść. Bez gry, bez X11, bez gniazd."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
_os.environ["RETRONIC_ID"] = "tstschody"
import importlib.util
import sys
import types
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import mapa as _mapa
import marsz_klik
import serwis as S
import wyprawa
from serwis_blad import SerwisBlad

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("SKIP: brak mapa/map74.otmm")
    sys.exit(0)
MP = _mapa.mapa()
SCHODY = (32350, 32226, 7)
CEL = (32352, 32226, 7)
STARTY = [(32347, 32225, 7), (32350, 32227, 7), (32349, 32225, 7)]

STARY = None
bak = KAT / "serwis.py.bak-20261022-schody-planer"
if bak.is_file():
    from importlib.machinery import SourceFileLoader
    spec = importlib.util.spec_from_loader("serwis_stary", SourceFileLoader("serwis_stary", str(bak)))
    STARY = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(STARY)


if STARY is not None and _os.environ.get("RETRONIC_TEST_STARY"):
    S = STARY            # sprawdzenie „stary kod na nowym teście”: asercje nowego zachowania muszą paść (5a-d, 2a, 3a, 1b-c)


def schody(p):
    f = int(MP.flagi(*p))
    return bool(f & 1 and f & 2 and not f & 4)


def idzie(x, y, z):
    f = int(MP.flagi(x, y, z))
    return bool(f & 1 and not f & 4 and not f & 2)


def pola_odcinka(p, q):
    """Pola, po których marsz idzie wprost między punktami p i q (zaokrąglona linia, jak marsz_klik.gesta_sciezka)."""
    d = max(abs(q[0] - p[0]), abs(q[1] - p[1]))
    return [(p[0] + round(i * (q[0] - p[0]) / d), p[1] + round(i * (q[1] - p[1]) / d), p[2]) for i in range(1, d + 1)]


def droga_czysta(droga):
    """Każdy odcinek między kolejnymi punktami przechodzi tylko po zwykłych polach (bez ścian i schodów)."""
    return all(idzie(*q) for p, q in zip(droga, droga[1:]) for q in pola_odcinka(p, q))


def planer(modul):
    dane = modul.wczytaj("thais")
    return modul.Planer(wyprawa.Trasownik(MP), dane["laczniki"], drzwi=modul.drzwi_miasta(dane), mapa=MP)


# --- 1. planer: droga do niszy depo ------------------------------------------------------------------------------

sprawdz("1a mapa: (32350,32226,7) to schody (chodliwe + flaga 2), kolumna x=32351 to ściana, nisza dostępna od południa",
        schody(SCHODY) and not idzie(32351, 32226, 7) and not idzie(32351, 32227, 7) and idzie(32352, 32228, 7) and idzie(*CEL))
for modul, nazwa in ((S, "nowy"), (STARY, "stary")):
    if modul is None:
        continue
    pl = planer(modul)
    drogi = {st: pl.droga(st, CEL) for st in STARTY}
    bez_schodow = all(d is not None and SCHODY not in d for d in drogi.values())
    czyste = all(d is not None and droga_czysta(d) for d in drogi.values())
    if nazwa == "nowy":
        sprawdz("1b nowy planer: droga ze wszystkich startów do niszy bez pola schodów", bez_schodow, drogi)
        sprawdz("1c nowy planer: każdy odcinek drogi idzie po zwykłych polach (bez cięcia rogu ściany)", czyste,
                {st: d for st, d in drogi.items() if d is not None and not droga_czysta(d)})
        sprawdz("1d nowy planer: dojazd kończy na polu niszy", all(d[-1] == CEL for d in drogi.values()))
    else:
        sprawdz("1b' STARY planer: też bez pola schodów na planie (plan nie był przyczyną „wejścia na schody”)", bez_schodow)
        sprawdz("1c' STARY planer: rzadkie punkty tną róg ściany (to ma paść w starym kodzie)", not czyste)

# --- 2. depo: stanowisko, do którego droga idzie przez schody, jest pomijane -----------------------------------------


class TRZSchodami(wyprawa.Trasownik):
    """Trasownik, który do niszy (32352,32226) daje drogę wprost przez pole schodów (jedyna droga = przez schody)."""

    def odcinek(self, od, do):
        if tuple(do) == CEL:
            return [tuple(od), SCHODY, CEL]
        return super().odcinek(od, do)


def depo_wynik(modul):
    dane = {"depo_stoiska": [list(CEL), [32354, 32226, 7]], "przystanki": {"depo": {"stoi": list(CEL)}}, "laczniki": [],
            "wyjscie": [32347, 32225, 7], "kolejnosc": ["depo"]}
    pl = modul.Planer(TRZSchodami(MP), [])
    chodzone, zlozone = [], []

    class Akcje:
        nick = "Ja"

        def pole_zajete(self, p):
            return False

        def depo_zloz(self, zostaw_platinum=3, odejdz=None):
            zlozone.append(1)
            return True

    s = modul.Serwis(dane, Akcje(), pl, lambda: (32349, 32226, 7), lambda pts, tol=0: chodzone.append(list(pts)) or True,
                     log=lambda *a: None)
    s._odejdz_od_depo = lambda st: None
    try:
        s._krok_depo()
    except SerwisBlad as e:
        return chodzone, zlozone, e
    return chodzone, zlozone, None


ch, zl, blad = depo_wynik(S)
sprawdz("2a nowy: stanowisko z drogą przez schody pominięte, depo robione na następnym (32354,32226)",
        blad is None and zl == [1] and len(ch) == 1 and ch[0][-1] == (32354, 32226, 7) and SCHODY not in ch[0], (ch, zl, blad))
if STARY is not None:
    ch, zl, blad = depo_wynik(STARY)
    sprawdz("2b STARY: idzie na stanowisko przez schody (to ma paść w starym kodzie)",
            bool(ch) and SCHODY in ch[0], (ch, zl, blad))

# --- 3. idz_pewnie: klik nie może prowadzić przez prostokąt ze schodami -----------------------------------------------

import ekran  # noqa: E402

KLIKI = []


class Swiat:
    """Atrapa postaci: strzałka rusza po zwykłym polu, klik przenosi na klikane pole, a gdy w prostokącie poz-klik (+1) leży pole
    schodów (klient prowadzi klik własną drogą, 8 kierunków, skos przez róg), klient wchodzi na schody: piętro 6."""

    def __init__(self, poz):
        self.p = list(poz)

    def pozycja(self):
        return tuple(self.p)

    def krok(self, klawisz):
        d = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}[klawisz]
        n = (self.p[0] + d[0], self.p[1] + d[1], self.p[2])
        if schody(n):
            self.p[:] = [n[0] - 1, n[1] - 1, 6]
            return tuple(self.p)
        if idzie(*n):
            self.p[0], self.p[1] = n[0], n[1]
            return tuple(self.p)
        return None


class Akcje:
    nick = "Ja"

    def _stwory(self):
        return []


def klik_i_czekaj_atrapa(postac, poz, cel_kl, dalej, **kw):
    x0, x1 = sorted((poz[0], cel_kl[0]))
    y0, y1 = sorted((poz[1], cel_kl[1]))
    ze_schodami = any(schody((x, y, poz[2])) for x in range(x0 - 1, x1 + 2) for y in range(y0 - 1, y1 + 2))
    KLIKI.append((tuple(poz), tuple(cel_kl), ze_schodami))
    if ze_schodami:
        postac.p[:] = [32349, 32225, 6]
        return "pietro"
    postac.p[0], postac.p[1] = cel_kl[0], cel_kl[1]
    return "ruch"


marsz_klik.klik_i_czekaj = klik_i_czekaj_atrapa
ekran.klik_pola = lambda dx, dy, *a, **k: None
S.time.sleep = lambda s: None if False else None            # nie dotykamy zegara globalnie (atrapy nie czekają)


def marsz(modul, start):
    KLIKI.clear()
    sw = Swiat(start)
    logi = []
    r = modul.idz_pewnie(sw, MP, Akcje(), CEL, 0, maks_s=20.0, log=logi.append, unik=[], stan={})
    return r, tuple(sw.p), list(KLIKI), logi


wynik = {}
for modul, nazwa in ((S, "nowy"), (STARY, "stary")):
    if modul is None:
        continue
    wynik[nazwa] = {st: marsz(modul, st) for st in STARTY}
nowy = wynik["nowy"]
sprawdz("3a nowy idz_pewnie: żaden klik nie przechodzi przez prostokąt ze schodami, marsz dochodzi do niszy na z7",
        all(r is True and p == CEL and not any(k[2] for k in kl) for r, p, kl, _ in nowy.values()),
        {st: (r, p, [k for k in kl if k[2]]) for st, (r, p, kl, _) in nowy.items()})
if STARY is not None:
    st_ = wynik["stary"]
    sprawdz("3b STARY idz_pewnie: klik przez prostokąt ze schodami, postać na piętrze 6 (to ma paść w starym kodzie)",
            any(p[2] == 6 and any(k[2] for k in kl) for r, p, kl, _ in st_.values()),
            {st: (r, p, [k for k in kl if k[2]]) for st, (r, p, kl, _) in st_.items()})

# --- 4. marsz: po wyjściu na inne piętro idz_pewnie oddaje zapasowemu chodzikowi (opis awarii, stary kod) -----------------

if STARY is not None:
    wolane = []
    KLIKI.clear()
    sw = Swiat((32349, 32225, 7))
    STARY.marsz(sw, MP, Akcje(), [], [(32349, 32225, 7), CEL], 0, log=lambda m: None,
                zapasowy=lambda pts, tol: wolane.append(sw.pozycja()) or False)
    sprawdz("4a STARY marsz: po kliku ze schodami zapasowy chodzik woła się już na piętrze 6 (log awarii: „koniec trasy w (…, 6)”)",
            wolane and wolane[0][2] == 6, wolane)

# --- 5. zapasowy chodzik: CavebotDojscie bez schodów ----------------------------------------------------------------

import cavebot  # noqa: E402

F = getattr(S, "fabryka_dojscia_bez_schodow", lambda mp: cavebot.CavebotDojscie)(MP)
loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")


def zrob(klasa, start):
    class Sw:
        t = 0.0

        def zegar(self):
            return self.t

        def spij(self, d):
            self.t += d

        def zapytaj(self, z):
            if z["cmd"] == "gracz":
                return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0}}
            return {"stwory": []}

    sw = Sw()
    droga = planer(S).droga(start, CEL)
    b = klasa(Swiat(start), droga, 1, None, 30, None, None, True, zapytaj=sw.zapytaj, atak=lambda m, g: None, alarm=lambda w: None,
              spij=sw.spij, zegar=sw.zegar, loot=loot, mapa=MP, klik=lambda dx, dy: None, tolerancja=0)
    return b


b_stary, b_nowy = zrob(cavebot.CavebotDojscie, STARTY[0]), zrob(F, STARTY[0])
sprawdz("5a zapasowy chodzik (nowa klasa): schody to „nauczona dziura” (ściana kroku i drogi), zwykłe pole nie",
        b_nowy.dziura_nauczona(SCHODY) and b_nowy.pole_zmiany_pietra(SCHODY) and not b_nowy.dziura_nauczona((32349, 32226, 7)))
sprawdz("5b STARY CavebotDojscie nie zna tych schodów (to ma paść w starym kodzie)", not b_stary.dziura_nauczona(SCHODY))
sprawdz("5c klik w rogu schodów: nowa klasa uznaje prostokąt za niebezpieczny (krok strzałką), stara nie",
        b_nowy._dziura_na_drodze((32349, 32225, 7), (32350, 32228)) and not b_stary._dziura_na_drodze((32349, 32225, 7), (32350, 32228)))
sprawdz("5d pole punktu trasy (cel dojścia) jest dozwolone, nawet gdyby było schodami",
        not b_nowy.dziura_nauczona((CEL[0], CEL[1], 7)))

# --- 6. Edron: z3/z4/z5 -> z6 -> z7 (22.10 13:24, invincible, krok „wyjscie” ze sklepu z blankami; regresja po zmianie planera) -----------------

import io  # noqa: E402
import contextlib  # noqa: E402

DE = S.wczytaj("edron")
LACZ = DE["laczniki"]
LACZP = [(tuple(l["z"]), tuple(l["do"])) for l in LACZ]       # jak Planer.lacz
WYJ = tuple(DE["wyjscie"])
BLANKI = tuple(DE["przystanki"]["blanki"]["stoi"])          # (33255,31841,3): sklep z blankami
PRZYJSCIE5 = (33257, 31843, 5)                              # lądowanie ze schodów z4 -> z5
WEJSCIE6 = (33258, 31841, 5)                                # pole wejścia przed schodami (33258,31840) na z6
SCHODY5 = (33257, 31842, 5)                                 # schody z4/z5 obok lądowania: nie na planie, krok na nie zmienia piętro


def planer_e(modul):
    return modul.Planer(wyprawa.Trasownik(MP), LACZ, drzwi=modul.drzwi_miasta(DE), mapa=MP)


sprawdz("6a mapa: lądowanie z5 (33257,31843) jest zwykłe, (33257,31842) to schody, (33258,31843) ściana, wejście (33258,31841) zwykłe",
        idzie(*PRZYJSCIE5) and schody(SCHODY5) and not idzie(33258, 31843, 5) and idzie(*WEJSCIE6) and schody((33258, 31840, 5)))
for modul, nazwa in ((S, "nowy"), (STARY, "stary")):
    if modul is None:
        continue
    pe = planer_e(modul)
    wyj = {st: pe.droga(st, WYJ) for st in (BLANKI, (33255, 31843, 4), (33256, 31842, 4), PRZYJSCIE5, (33258, 31841, 6))}
    do_wejscia = pe.droga(PRZYJSCIE5, WEJSCIE6)
    sprawdz(f"6b {nazwa} planer Edron: z każdego piętra (z3/z4/z5/z6) droga do wyjścia (33167,31815,7) istnieje",
            all(d is not None for d in wyj.values()), wyj)
    sprawdz(f"6c {nazwa} planer Edron: droga z lądowania z5 do wejścia przed schodami na z6 istnieje", do_wejscia is not None, do_wejscia)
    if nazwa == "nowy":
        pietra = [p[2] for p in wyj[BLANKI]]
        sprawdz("6d nowy planer Edron: plan ze sklepu przechodzi z3,4,5,6,7 w tej kolejności i kończy na wyjściu",
                [z for i, z in enumerate(pietra) if i == 0 or z != pietra[i - 1]] == [3, 4, 5, 6, 7] and wyj[BLANKI][-1] == WYJ, pietra)
        # żaden punkt planu na z5 nie jest polem schodów poza łącznikami (pola łączników i pola obok zmiany piętra są dozwolone)
        sprawdz("6e nowy planer Edron: plan ze sklepu nie wchodzi na schody (33257,31842,5) „przy okazji”", SCHODY5 not in wyj[BLANKI])

# 6f: żaden z 1190 odcinków węzeł-węzeł Edron nie traci drogi po zmianie planera (stary miał drogę -> nowy ma drogę)
wezly = {tuple(p) for l in LACZ for p in (l["z"], l["do"])} | {tuple(v["stoi"]) for v in DE["przystanki"].values()}
wezly |= {WYJ} | {tuple(v) for v in DE["depo_stoiska"]}
strata = []
if STARY is not None:
    ps, pn = planer_e(STARY), planer_e(S)
    for a_ in sorted(wezly):
        for b_ in sorted(wezly):
            if a_ != b_ and ps.droga(a_, b_) is not None and pn.droga(a_, b_) is None:
                strata.append((a_, b_))
    sprawdz("6f nowy planer Edron: każda para węzłów, między którymi stary planer miał drogę, ma drogę także w nowym", not strata, strata[:5])

# 6g: idz_pewnie z lądowania z5 do wejścia: ortogonalnej drogi nie ma (końce łączników (33257,31840/31841) zamykają kieszeń), więc
#     False BEZ utknięcia, bez klika i bez kroku na schody (marsz oddaje wtedy zapasowemu chodzikowi, jak rano u dawajkesha)
unik_e = [p for l in LACZP for p in l]


class Swiat5(Swiat):
    """Atrapa postaci z5: krok na pole schodów = zmiana piętra (z99), strzałki zapisywane."""

    def __init__(self, poz):
        super().__init__(poz)
        self.klawisze = []

    def krok(self, klawisz):
        self.klawisze.append(klawisz)
        d = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}[klawisz]
        n = (self.p[0] + d[0], self.p[1] + d[1], self.p[2])
        if schody(n):
            self.p[2] = 99
            return tuple(self.p)
        if idzie(*n):
            self.p[0], self.p[1] = n[0], n[1]
            return tuple(self.p)
        return None


KLIKI.clear()
sw5, stan5, logi5 = Swiat5(PRZYJSCIE5), {}, []
r5 = S.idz_pewnie(sw5, MP, Akcje(), WEJSCIE6, 0, maks_s=5.0, log=logi5.append, unik=unik_e, stan=stan5)
sprawdz("6g idz_pewnie lądowanie -> wejście: False bez utknięcia, bez klika i bez strzałki (zapasowy chodzik ma ostatnie słowo)",
        r5 is False and not stan5 and not KLIKI and not sw5.klawisze and tuple(sw5.p) == PRZYJSCIE5, (r5, stan5, KLIKI, sw5.klawisze, logi5))
wolane5 = []
S.marsz(sw5, MP, Akcje(), LACZP, [PRZYJSCIE5, WEJSCIE6], 0, log=lambda m: None, zapasowy=lambda pts, tol: wolane5.append((pts, tol)) or True)
sprawdz("6h marsz: brak drogi ortogonalnej => zapasowy chodzik woła się na z5 z punktami do wejścia", len(wolane5) == 1
        and tuple(sw5.p)[2] == 5 and wolane5[0][0][-1] == WEJSCIE6, wolane5)

# 6i-6l: zapasowy chodzik z łącznikami planu: klik do wejścia dozwolony (jak przed zmianą, klient obchodzi skosem), strzałka na schody nie
FAB = getattr(S, "fabryka_dojscia_bez_schodow", lambda mp, laczniki=(): cavebot.CavebotDojscie)
Fe = FAB(MP, LACZP)
Fth = FAB(MP)


def zrob_e(klasa, start, cel):
    class Sw:
        t = 0.0

        def zegar(self):
            return self.t

        def spij(self, d):
            self.t += d

        def zapytaj(self, z):
            if z["cmd"] == "gracz":
                return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0}}
            return {"stwory": []}

    sw = Sw()
    return klasa(Swiat5(start), [cel], 1, None, 30, None, None, True, zapytaj=sw.zapytaj, atak=lambda m, g: None, alarm=lambda w: None,
                 spij=sw.spij, zegar=sw.zegar, loot=loot, mapa=MP, klik=lambda dx, dy: None, tolerancja=0)


be = zrob_e(Fe, PRZYJSCIE5, WEJSCIE6)
sprawdz("6i zapasowy chodzik Edron: klik z lądowania do wejścia przed schodami NIE jest uznany za niebezpieczny (stary kod też klikał)",
        not be._dziura_na_drodze(PRZYJSCIE5, WEJSCIE6[:2]) and not zrob_e(cavebot.CavebotDojscie, PRZYJSCIE5, WEJSCIE6)._dziura_na_drodze(
            PRZYJSCIE5, WEJSCIE6[:2]))
sprawdz("6j zapasowy chodzik Edron: strzałka na pola schodów (33257,31842,5) i (33258,31840,5) nadal zakazana, pola łączników planu i punktu trasy dozwolone",
        be.dziura_nauczona(SCHODY5) and be.dziura_nauczona((33258, 31840, 5))
        and not be.dziura_nauczona(WEJSCIE6) and not be.dziura_nauczona((33257, 31841, 5)) and not be.dziura_nauczona((33257, 31840, 5)),
        (be.dziura_nauczona(SCHODY5), be.dziura_nauczona((33258, 31840, 5)), be.dziura_nauczona((33257, 31841, 5))))
sprawdz("6k Thais bez łączników i bez sąsiedztwa punktu trasy: klik przez prostokąt ze schodami nadal odrzucony (5c się nie cofa)",
        zrob(Fth, STARTY[0])._dziura_na_drodze((32349, 32225, 7), (32350, 32228)))

# 6l: AttributeError „'DojscieBezSchodow' object has no attribute 'mapa'” (cavebot.py: pierwszy _ogien_stale_wczytaj przed self.mapa)
import json as _json  # noqa: E402
import tempfile  # noqa: E402

tmp = Path(tempfile.mkdtemp()) / "ogien_stale.json"
tmp.write_text(_json.dumps({"pola": [[33258, 31843, 5]]}))
stare_plik, stare_tylko, stare_log = cavebot.PLIK_OGIEN_STALE, cavebot.OGIEN_MASKA_TYLKO_SCIANY, cavebot.log
cavebot.PLIK_OGIEN_STALE, cavebot.OGIEN_MASKA_TYLKO_SCIANY = tmp, True
komunikaty = []
cavebot.log = lambda m, *a, **k: komunikaty.append(str(m))
try:
    zrob_e(cavebot.CavebotDojscie, PRZYJSCIE5, WEJSCIE6)
    bledy_stary = [m for m in komunikaty if "nie wczytam maski" in m]
    komunikaty.clear()
    zrob_e(Fe, PRZYJSCIE5, WEJSCIE6)
    bledy_nowy = [m for m in komunikaty if "nie wczytam maski" in m]
finally:
    cavebot.PLIK_OGIEN_STALE, cavebot.OGIEN_MASKA_TYLKO_SCIANY, cavebot.log = stare_plik, stare_tylko, stare_log
sprawdz("6l DojscieBezSchodow: brak AttributeError 'mapa' przy tworzeniu (zwykły CavebotDojscie go loguje)",
        not bledy_nowy and (not bledy_stary or "mapa" in bledy_stary[0]), (bledy_stary, bledy_nowy))

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
