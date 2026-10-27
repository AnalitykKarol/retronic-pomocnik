"""27.10: Ab'Dendriel zachod z9, dwie pętle ROZŁĄCZNE `_v2` (generuj_trasy_abdendriel_zachod_ns2.py; Karol: „tych tras nie zmieniajmy, tylko zróbmy ich KOPIE”).
Nic nie wysyla do gry i niczego nie zmienia na dysku (poza katalogiem tymczasowym). Wzor: sekcje 9a-9m testy/test_zachod_abdendriel.py.
Sprawdza: pliki petli == generator (ogien rosnie w czasie gry: rozjazd = FAIL 1a, nalezy przeliczyc generator), start = koniec = ladowanie (32480,31721,z9), ciaglosc,
zero ognia (pliki ognia czytane niezaleznie) / dziur / przeszkod z buforem / scian / flagi 2 / stref, odstep >= 2 od dziur z9, PRZYPISANIE przystanku wschodniego (32531,31691) do
poludniowej, ROZLACZNOSC (wspolne pola poza ladowaniem = 0, wspolnych <= 5, brak sasiedztwa Chebysheva <= 1 poza promieniem 6 od ladowania), dlugosc == niezalezny Held-Karp,
regula kosztu, optymalnosc wzgledem starych N/S, wpisy mapy.json, pelny start ucieczki PK z punktow obu petli (plan abdendriel_zachod_z9 wybierany po pozycji),
BRAK zmian plikow starych N/S i pelnej (sha256 z chwili rozpoczecia pracy 27.10).
NIEPOTWIERDZONE NA ZYWO: wszystko, co dotyczy gry (dojscie, liny, depo ZASTEPCZE, brak ognia na nowych trasach, rozlacznosc w ruchu dwoch postaci)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import hashlib
import json
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa
import panel
import trasa_io
import wypad
import wyprawa as W
import generuj_trasy_abdendriel_zachod as Z
import generuj_trasy_abdendriel_zachod_ns as NS
import generuj_trasy_abdendriel_zachod_ns2 as V2

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test zachod abdendriel v2")
    sys.exit(0)

MAPA = _mapa.Mapa()
ROOTP = Path(_R)
WAR = ("polnoc", "poludnie")
BAZA = "abdendriel_zachod_z9"
NW = {w: f"{BAZA}_{w}_v2" for w in WAR}
NSTARE = {w: f"{BAZA}_{w}" for w in WAR}
LAD9 = (32480, 31721, 9)                       # pole liny = start i koniec petli (wpisane niezaleznie od generatora)
EAST = (32531, 31691)
DEPO = Z.PW.DEPO_STOI
PW_ = {w: [tuple(p) for p in trasa_io.wczytaj(NW[w] + "_petla")[0]] for w in WAR}
DOJ9 = [tuple(p) for p in trasa_io.wczytaj(BAZA + "_dojscie")[0]]
POW9 = [tuple(p) for p in trasa_io.wczytaj(BAZA + "_do_depo")[0]]
MJ = json.loads((ROOTP / "mapy.json").read_text())
out = V2.zbuduj_v2(MAPA)
print("INFO sha1 plikow ognia/dziur przy tescie:", V2.sha1_ognia())

# niezalezny odczyt ognia (stale + epizody z hp, bufor 1), dziur (omijaj) i skanu przeszkod
_og_stale = {tuple(q[:3]) for q in json.loads((ROOTP / "trasy" / "ogien_stale.json").read_text()).get("pola", [])}
_og_ep = json.loads((ROOTP / "trasy" / "ogien_epizody.json").read_text()).get("pola", {})
_og_raw = _og_stale | {tuple(int(a) for a in k.split(",")) for k, v in _og_ep.items() if v.get("hp")}
_og_buf = {(x + dx, y + dy, zz) for x, y, zz in _og_raw for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
_omz = {tuple(q[:3]) for q in json.loads((ROOTP / "trasy" / "dziury_omijaj.json").read_text())["dziury"]}
_om9 = {q for q in _omz if q[2] == 9}
_dzn = {tuple(q) for q in json.loads((ROOTP / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])}
_comp = out["polnoc"]["comp"]
_xs, _ys = [c[0] for c in _comp], [c[1] for c in _comp]
_prz9 = set(Z.skan_przeszkod(MAPA, 9, (min(_xs) - Z.MARGINES_SKANU, min(_ys) - Z.MARGINES_SKANU, max(_xs) + Z.MARGINES_SKANU, max(_ys) + Z.MARGINES_SKANU)))
cheb = V2.cheb

# ---- 1. plik == generator, start/koniec, ciaglosc, zagrozenia
for w in WAR:
    P, o = PW_[w], out[w]
    sprawdz(f"a {w}: plik petli == generator v2 (ogien/dziury jak dzis), jedno pietro z9, cala w skladowej",
            P == [(x, y, 9) for x, y in o["pelna"]] and all(p[2] == 9 for p in P) and all((p[0], p[1]) in o["comp"] for p in P), (len(P), len(o["pelna"])))
    sprawdz(f"b {w}: start = koniec = ladowanie (32480,31721,z9) = ostatni punkt dojscia z9; ciaglosc: kroki <= 1 pole",
            P[0] == P[-1] == LAD9 == DOJ9[-1] and all(cheb(a, b) <= 1 for a, b in zip(P, P[1:])), (P[0], P[-1]))
    zly = [(n, p) for n, p in (("ogien", [q for q in P if q in _og_buf]), ("dziura", [q for q in P if q in _omz or q in _dzn]),
                              ("przeszkoda/bufor", [q for q in P if q in _prz9 or any(cheb(q, r) <= 1 for r in _prz9)]),
                              ("sciana/flaga2", [q for q in P if not MAPA.flagi(*q) & _mapa.WIDZIANE or MAPA.flagi(*q) & (_mapa.SCIANA | _mapa.BEZ_DROGI)]),
                              ("odstep<2 od dziury z9", [q for q in P if any(cheb(q, r) <= 1 for r in _om9)])) if p]
    sprawdz(f"c {w}: zero punktow w ogniu (pliki ognia, bufor 1), na polach dziur, w buforze przeszkod (pelny skan), na scianach/flagach 2, odstep >= 2 od dziur z9", not zly, zly[:3])
    zle_sp = []
    for nazwa, r in Z.STREFA.items():
        for s_ in Z.spot_lib.spawny(9, (nazwa,), (32380, 32640, 31560, 31800)):
            zle_sp += [(nazwa, (s_["x"], s_["y"]), p) for p in P if cheb(p, (s_["x"], s_["y"])) <= r]
    sprawdz(f"d {w}: zadna strefa zakazana (rotworm 12, poison spider 6) nie dotyka petli", not zle_sp, zle_sp[:3])
    jw = json.loads((ROOTP / "dane_tibia" / "mapy" / f"{NW[w]}.json").read_text())
    sprawdz(f"e {w}: opis .json: start = ladowanie, dlugosc_petli == punkty pliku, przystanki == generator",
            jw["start"] == list(LAD9) and jw["dlugosc_petli"] == len(P) and len(jw["przystanki"]) - 1 == len(o["st"])
            and sum(t.get("potworow", 0) for t in jw["przystanki"]) == sum(t["n"] for t in o["st"]), jw["dlugosc_petli"])
    gard = Z.waskie_gardla(MAPA, o["comp"], o["zle"], [(p[0], p[1]) for p in P], 9)
    print(f"INFO {w}: {len(P)} pkt, {len(o['st'])} przystankow, {sum(t['n'] for t in o['st'])} potworow, {len(P) / sum(t['n'] for t in o['st']):.1f} pola/potwora, "
          f"waskie gardla {len(gard)}: {gard}")
    sprawdz(f"e2 {w}: wasko gardla w pliku == generator (informacyjnie liczone na dzisiejszym ogniu)", gard == o["gardla"], (gard, o["gardla"]))

# ---- 2. podzial przystankow: wschodni do poludniowej, reszta wg y, razem = wszystkie osiagalne bez wykluczonych (minus pominiete regula kosztu)
_L, _c, _sc, _zle, _wszystkie = NS.przygotuj(MAPA)
sprawdz("f skladowa i sciany z9 v2 = skladowa i sciany ns.py (ta sama polityka: ogien, dziury, skan, strefy)", set(_c) == set(_comp) and _zle == out["polnoc"]["zle"], (len(_c), len(_comp)))
_cele = {t["pt"]: t["n"] for t in _wszystkie if t["pt"] not in NS.WYKLUCZONE_NS}
_st = {w: {t["pt"]: t["n"] for t in out[w]["st"]} for w in WAR}
_pom = {w: {pt for pt, *_ in out[w]["pomin"]} for w in WAR}
sprawdz("g podzial: przystanek wschodni (32531,31691) w POLUDNIOWEJ i nie w polnocnej (o ile jest osiagalny); reszta polnoc y < PROG_Y, poludnie y >= PROG_Y; rozlaczne; "
        "razem = wszystkie osiagalne bez wykluczonych i bez pominietych regula kosztu; polnocny pokoj (32436,31573) wykluczony",
        (EAST in _cele) and EAST in _st["poludnie"] and EAST not in _st["polnoc"]
        and all(pt[1] < NS.PROG_Y for pt in _st["polnoc"]) and all(pt[1] >= NS.PROG_Y or pt == EAST for pt in _st["poludnie"]) and not (set(_st["polnoc"]) & set(_st["poludnie"]))
        and set(_st["polnoc"]) | set(_st["poludnie"]) | _pom["polnoc"] | _pom["poludnie"] == set(_cele) and (32436, 31573) not in _cele
        and all(_cele[pt] == n for w in WAR for pt, n in _st[w].items()), (sorted(_cele), _st))

# ---- 3. ROZLACZNOSC: niezalezny pomiar na plikach
A, B = [(p[0], p[1]) for p in PW_["polnoc"]], [(p[0], p[1]) for p in PW_["poludnie"]]
wsp = set(A) & set(B)
poza = sorted(p for p in wsp if cheb(p, LAD9) > V2.LAD_PROMIEN)
sprawdz(f"h pola wspolne obu petli poza ladowaniem (Chebyshev > {V2.LAD_PROMIEN} od (32480,31721)) = 0 i wspolnych w ogole <= {V2.WSPOLNE_MAX} (stare N/S: 87 wspolnych, 83 poza ladowaniem)",
        not poza and len(wsp) <= V2.WSPOLNE_MAX, (len(wsp), poza[:5]))
da, db = [q for q in set(A) if cheb(q, LAD9) > V2.LAD_PROMIEN_BLISKO], [q for q in set(B) if cheb(q, LAD9) > V2.LAD_PROMIEN_BLISKO]
bl = {r: sum(1 for p in da if any(cheb(p, q) <= r for q in db)) for r in (1, 2, 3)}
sprawdz(f"h2 zadne dwa punkty roznych petli nie sasiaduja (Chebyshev <= 1) poza promieniem {V2.LAD_PROMIEN_BLISKO} od ladowania", bl[1] == 0, bl)
print(f"INFO punkty polnocnej w Chebyshev <=1/<=2/<=3 od poludniowej (poza promieniem {V2.LAD_PROMIEN_BLISKO} od ladowania): {bl[1]}/{bl[2]}/{bl[3]}; wspolne pola {sorted(wsp)}")
pom = V2.pomiar(PW_["polnoc"], PW_["poludnie"])
sprawdz("h3 pomiar generatora (V2.pomiar) == pomiar testu (wspolne, poza ladowaniem)", pom["wspolne"] == sorted(wsp) and pom["wspolne_poza"] == poza and V2.kryterium(pom)[0], pom["wspolne"])

# ---- 4. Held-Karp niezalezny, regula kosztu, optymalnosc
def _cykl(stops):
    wez = [tuple(LAD9[:2])] + list(stops)
    return Z.held_karp(Z.macierz_drog(MAPA, 9, wez, _sc))[1]


_zle_hk = []
for w in WAR:
    pts = [t["pt"] for t in out[w]["st"]]
    pelny = _cykl(pts)
    if pelny != len(out[w]["pelna"]) - 1 or pelny != len(PW_[w]) - 1:
        _zle_hk.append((w, "dlugosc", pelny, len(PW_[w]) - 1))
    for pt in pts:                                                   # zachowany przystanek <= 2 potwory nie moze kosztowac > 25% cyklu
        if _st[w][pt] <= NS.KOSZT_MAX_POTW and pelny - _cykl([q for q in pts if q != pt]) > NS.KOSZT_PROG * pelny:
            _zle_hk.append((w, "zachowany drogi", pt))
    for pt, n_, g, proc in out[w]["pomin"]:
        if not (n_ <= NS.KOSZT_MAX_POTW and g > NS.KOSZT_PROG * (pelny + g)):
            _zle_hk.append((w, "pominiety nie spelnia reguly", pt, g))
sprawdz("i dlugosc petli = DOKLADNY cykl Held-Karp (niezalezna macierz A*); regula kosztu: zaden zachowany przystanek <= 2 potwory nie skraca cyklu o > 25%, kazdy pominiety (n <= 2) skracal o > 25%",
        not _zle_hk, _zle_hk[:3])
_stare = {w: [tuple(p) for p in json.loads((ROOTP / "trasy" / f"{NSTARE[w]}_petla.json").read_text())] for w in WAR}
_nm = {w: sum(_st[w].values()) for w in WAR}
sprawdz("j optymalnosc: polnocna v2 KROTSZA niz stara polnocna (po wycieciu ramienia wschodniego, >= 100 pol mniej), pola/potwor v2 <= 45 obu petli, kazda ma >= 4 przystanki i >= 10 potworow",
        len(PW_["polnoc"]) <= len(_stare["polnoc"]) - 100 and all(len(PW_[w]) / _nm[w] <= 45 for w in WAR) and all(len(_st[w]) >= 4 and _nm[w] >= 10 for w in WAR),
        {w: (len(PW_[w]), _nm[w], len(_st[w])) for w in WAR})
print("INFO stare N/S (pliki): polnoc %d pkt, poludnie %d pkt; v2: polnoc %d pkt/%d potw./%d przyst., poludnie %d pkt/%d potw./%d przyst."
      % (len(_stare["polnoc"]), len(_stare["poludnie"]), len(PW_["polnoc"]), _nm["polnoc"], len(_st["polnoc"]), len(PW_["poludnie"]), _nm["poludnie"], len(_st["poludnie"])))

# ---- 5. wpisy mapy.json
for w in WAR:
    e = MJ.get(NW[w], {})
    sprawdz(f"k mapy.json {NW[w]}: trasa, potwory Troll,Wolf,Snake, prog_hp 35, dojscie = dojscie pelnej z9, dojscie_z_dowolnego_pietra, plik petli, opis z liczba pol i NIEPRZEJSTE NA ZYWO",
            e.get("trasa") == NW[w] + "_petla" and e.get("potwory") == "Troll,Wolf,Snake" and e.get("prog_hp") == 35 and e.get("dojscie") == BAZA + "_dojscie"
            and e.get("dojscie_z_dowolnego_pietra") is True and trasa_io.sciezka(NW[w] + "_petla").is_file() and f"pętla {len(PW_[w])} pól" in e.get("opis", "")
            and "NIEPRZEJŚTE NA ŻYWO" in e.get("opis", ""), e)
sprawdz("l nazwy v2 rozne od pelnej, starych N/S i z8; wszystkie wpisy v2 w mapy.json to dokladnie 2 nowe klucze (kopia mapy.json.bak-20261027-z9-v2: zmienione tylko nowe)",
        all(NW[w] not in (BAZA, NSTARE[w]) for w in WAR) and set(k for k in MJ if k.endswith("_v2")) >= set(NW.values()), [k for k in MJ if "z9" in k])
_bak = ROOTP / "mapy.json.bak-20261027-z9-v2"
if _bak.is_file():
    _b = json.loads(_bak.read_text())
    sprawdz("l2 wzgledem kopii mapy.json.bak-20261027-z9-v2: nic nie usuniete, nic nie zmienione, nowe klucze = dokladnie NW", not [k for k in _b if k not in MJ or _b[k] != MJ[k]] and set(MJ) - set(_b) == set(NW.values()),
            (set(MJ) - set(_b), [k for k in _b if k in MJ and _b[k] != MJ[k]][:3]))

# ---- 6. BRAK zmian plikow starych N/S i pelnej (sha256 z chwili rozpoczecia pracy 27.10 ~11:50)
SHA = {
    "trasy/abdendriel_zachod_z9_petla.json": "3f395e0f799ac623abbee61a66ea5d9d2b53f4f81c95f3148fb03c52f99887b3",
    "trasy/abdendriel_zachod_z9_polnoc_petla.json": "75dfcbb74ffdaa4b39321c7c0bc86fcbdcc57ddb6cda0febd24557b60302eef8",
    "trasy/abdendriel_zachod_z9_poludnie_petla.json": "dd45c6982c3fec92b36a19b7c66718bb020791b5e3a8d18d32687b6863284dd6",
    "dane_tibia/mapy/abdendriel_zachod_z9.json": "16584c185696a589f2432b42b1eedd99566f13fa3db3449451c3d2f7ef364f7e",
    "dane_tibia/mapy/abdendriel_zachod_z9.png": "4b79e2a6a51240a59f54e10b2ecc636607662681c36bb2052f0eeb90f4be3812",
    "dane_tibia/mapy/abdendriel_zachod_z9_polnoc.json": "681fb250d9d60b2993548ecbe7dd867ae9541f1bc70947a0d1ea47cd7dad31a1",
    "dane_tibia/mapy/abdendriel_zachod_z9_polnoc.png": "b409f7716d5101ba111f6d0522c6c04e3ed0709a6eb7ff9e93caeb145557d075",
    "dane_tibia/mapy/abdendriel_zachod_z9_poludnie.json": "75a2de671c56cb343b01eb2553904d41c29f28b2a015817dd3f43b82df089bea",
    "dane_tibia/mapy/abdendriel_zachod_z9_poludnie.png": "be6907d83694f49b5c931471161781804e3da6526d83f7fc39ff45ac1eacd22f",
    "dane_tibia/mapy/abdendriel_zachod_z9_dojscie.png": "a1d70e54c6fe154081e8009c2cbde58dcbbf8b3c60f82e1935cc0cfb39393d30",
}
SHA_MAPY = {"abdendriel_zachod_z9": "67b4cfdbdf5bf6b260742ae5954910979691bc2263f5f5e29f41b579e6800ab7",
            "abdendriel_zachod_z9_polnoc": "f8d5ab313291005c98cb3e23af0ddd2e1c91b32db17fbae5b9748dbf4af97ce1",
            "abdendriel_zachod_z9_poludnie": "727d8ccce29a00f4a0c12d8f25f7f99ea7cd83e8f5612ecfe70ac5e9199a4db8"}
zmienione = [f for f, h in SHA.items() if hashlib.sha256((ROOTP / f).read_bytes()).hexdigest() != h]
sprawdz("m pliki starych N/S i pelnej z9 (3 trasy, 6 png/json, png dojscia) bajt w bajt jak przed praca nad v2 (sha256)", not zmienione, zmienione)
zm_m = [k for k, h in SHA_MAPY.items() if hashlib.sha256(json.dumps(MJ[k], sort_keys=True, ensure_ascii=False).encode()).hexdigest() != h]
sprawdz("m2 wpisy mapy.json pelnej z9 i starych N/S bez zmian (sha256 wpisu)", not zm_m, zm_m)

# ---- 7. pelny start ucieczki PK z punktow obu petli: plan abdendriel_zachod_z9 (wybor po pozycji, nie po nazwie mapy)
TMP = Path(tempfile.mkdtemp())
baza = W.punkty_bazy(nazwy=W.BAZY_PK)


class KonfW:
    WYPRAWA_AKTYWNA = 1
    WYPRAWA_MAX_CZAS_S = 1800
    WYPRAWA_MAX_KROKOW = 6000
    WYPRAWA_STOP_PRZY_UTKNIECIU = 1
    WYPRAWA_CO_MIN = 20
    WYPRAWA_PO_DEPO_S = 900
    WYPRAWA_DEPO_POWROT = 0
    WYPRAWA_TYLKO_DEPO = 1


class OpsW:
    def wiadomosci(o):
        return []


def _cbw(poz, petla):
    class CBW:
        mapa = MAPA

        def __init__(c):
            c.t, c.wypad_aktywny, c.poz, c.punkty, c.stan = 0.0, False, poz, list(petla), None
            c.postac = types.SimpleNamespace(pozycja=lambda: c.poz)

        def zegar(c):
            return c.t

        def gracz(c):
            return {"proc": 60.0}

        def _wypad_reset_klik(c):
            pass

        def droga(c, *a, **k):
            return []

        def pauza(c, *a):
            pass
    return CBW()


dane = {"powody": ["pk"], "zapas": None, "blanki": None, "zloto": None, "cap": None, "hp": 60, "pochodnie": None, "depo": True}
OCZEK9 = ["IDZ", "LINA", "IDZ", "LINA", "IDZ", "DZIURA", "IDZ"]
for w in WAR:
    P = PW_[w]
    dal_lina = max(range(len(P)), key=lambda i: cheb(P[i], LAD9))
    dal_depo = max(range(len(P)), key=lambda i: cheb(P[i], DEPO))
    probki = sorted(set(list(range(0, len(P), 40)) + [dal_depo, dal_lina, len(P) - 1]))
    zle9l, ile_dal_lina, ile_poza = [], 0, 0
    for i in probki:
        poz = P[i]
        wy = W.Wyprawa(_cbw(poz, P), OpsW(), konf=KonfW(), log=lambda *_: None, plik_stanu=TMP / f"s{w}_{i}.json", plik_sklepow=TMP / "sk.json",
                       plik_npc=TMP / "npc.json", plik_stop=TMP / f"STOP{w}_{i}", czas=lambda: 5_000_000.0)
        wynik = wy._start_wyprawa("depo:pk_ucieczka", dane, 0.0, baza_nazwa=None, pk="ucieczka")
        et = wy.w["legs"][0] if wy.w else []
        ile_dal_lina += cheb(poz, LAD9) > W.PK_PLAN_ZASIEG
        ile_poza += cheb(poz, DEPO) > W.DEPO_DOJSCIE_ZASIEG
        if not (wynik is True and wy.w["baza"] == BAZA and [e["typ"] for e in et] == OCZEK9 and not wypad.sprawdz_plan(et, MAPA, {}, rampy_ok=True)
                and tuple(et[-1]["punkty"][-1]) == DEPO):
            zle9l.append((i, poz, wy.w and wy.w["baza"], [e["typ"] for e in et]))
    print(f"INFO n {w}: {len(probki)} punktow, najdalszy od pola liny {cheb(P[dal_lina], LAD9)} (zasieg PK {W.PK_PLAN_ZASIEG}), najdalszy od depo {cheb(P[dal_depo], DEPO)} (zasieg {W.DEPO_DOJSCIE_ZASIEG})")
    sprawdz(f"n {w}: ucieczka PK z {len(probki)} punktow petli (w tym {ile_dal_lina} dalszych niz {W.PK_PLAN_ZASIEG} od pola liny, {ile_poza} dalszych niz {W.DEPO_DOJSCIE_ZASIEG} od depo): "
            f"baza {BAZA}, etapy {' '.join(OCZEK9)}, koniec = depo, sprawdz_plan bez uwag; dalsze niz {W.PK_PLAN_ZASIEG} od liny wymagane tylko tam, gdzie petla tak daleko sieka (polnocna)",
            not zle9l and (ile_dal_lina > 0 or cheb(P[dal_lina], LAD9) <= W.PK_PLAN_ZASIEG), zle9l[:3])
    wb = {W.wybierz_baze(baza, p, W.PK_PLAN_ZASIEG) for p in P[::5]}
    sprawdz(f"o {w}: wybierz_baze (zasieg PK 80) z kazdego 5. punktu petli: plan {BAZA} albo None (None = dalej niz 80, wtedy _baza_dojscie); nigdy inny plan",
            wb <= {BAZA, None} and BAZA in wb, wb)
    dal = [p for p in P if W.wybierz_baze(baza, p, W.PK_PLAN_ZASIEG) is None]
    sprawdz(f"o2 {w}: punkty z wybierz_baze == None maja panel.plan_depo != None", all(panel.plan_depo(p) is not None for p in dal[::10]), len(dal))

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
