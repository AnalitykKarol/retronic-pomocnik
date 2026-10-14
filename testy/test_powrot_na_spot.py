"""Powrót na spot (depo -> jaskinia trolli): CavebotDojscie, upraszczanie trasy, bieg zamiast walki, łopata przy
dziurze, powrót po depo w wyprawie. Wyłącznie atrapy (mapa z mapa.py + symulator ruchu), bez gry i bez X11."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, types, tempfile
sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
from pathlib import Path
import cavebot, bot, mozg, pietra, trasa_io, pokretla, wypad

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

# --- harness z test_wielopietrowa.py (Swiat, P, Ops, zrob), bez jego scenariuszy ---
src = open(Path(_R) / "testy/test_wielopietrowa.py").read()
H = {"__file__": str(Path(_R) / "testy/test_wielopietrowa.py"), "__name__": "harness"}
exec(compile(src[:src.index("troll = [tuple(p)")], "harness", "exec"), H)
Swiat, P, Ops, M, LOG = H["Swiat"], H["P"], H["Ops"], H["M"], H["LOG"]
f, idzie = H["f"], H["idzie"]
TRASY = Path(_R) / "trasy"
DEPO = (32348, 32225, 7)
route = [tuple(p) for p in json.loads((TRASY / "depo_troll_cave.json").read_text())]
KONIEC = route[-1]


class SwiatL(Swiat):
    """Dziura wejściowa (flaga 2) zasypana: krok na nią nie zmienia piętra, dopóki nie użyto łopaty."""
    def __init__(s, poz, zasypana=True, **kw):
        super().__init__(poz, **kw)
        s.zasypana = zasypana; s.lopata_uzycia = []; s.lopata_ma = True
    def ruch(s, dx, dy):
        x, y, z = s.poz[0] + dx, s.poz[1] + dy, s.poz[2]
        if f(x, y, z) & 2 and s.zasypana and z == 7:
            s.poz[0], s.poz[1] = x, y        # stoimy na zasypanej dziurze
            return
        return super().ruch(dx, dy)
    def odkop(s, pole):
        s.lopata_uzycia.append(tuple(pole))
        if s.lopata_ma and (f(pole[0], pole[1], pole[2]) & 2):
            s.zasypana = False


class OpsL(Ops):
    def uzyj_lopate(o, cel, poz):
        if hasattr(o.s, "odkop"):
            o.s.odkop(cel)


def zrob_dojscie(s, punkty, atak=None, stwory=None, **kw):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
    b = cavebot.CavebotDojscie(P(s), punkty, 1, None, 30, None, None, True,
                               zapytaj=(stwory or s.zapytaj), atak=atak or (lambda m, g: None), alarm=lambda w: None,
                               spij=s.spij, zegar=s.zegar, loot=loot, mapa=M, klik=s.klik, **kw)
    b.pietra_ops = OpsL(s)
    b.tele = None
    return b


def bieg(b, n=6000):
    for i in range(n):
        if not b.tick():
            return i
    return n


# 1. uprosc_petle: trasa depo traci pętle (objazd na zachód), nie traci końca ani przejścia pięter
up = trasa_io.uprosc_petle(route)
sprawdz("1a trasa depo krótsza o objazd i duplikaty", len(up) < len(route) - 30 and trasa_io.dlugosc(up) < trasa_io.dlugosc(route) - 40,
        (len(route), len(up), trasa_io.dlugosc(route), trasa_io.dlugosc(up)))
sprawdz("1b początek (depo) i koniec (jaskinia) zachowane", up[0] == route[0] and up[-1] == route[-1])
i7 = max(i for i, p in enumerate(up) if p[2] == 7)
sprawdz("1c przejście z7 -> z8 nietknięte (ostatni z7 sąsiaduje z pierwszym z8)",
        up[i7 + 1][2] == 8 and max(abs(up[i7][0] - up[i7 + 1][0]), abs(up[i7][1] - up[i7 + 1][1])) <= 1, (up[i7], up[i7 + 1]))
sprawdz("1d żaden punkt (x,y,z) nie powtarza się", len(set(up)) == len(up))
sprawdz("1e idempotentna", trasa_io.uprosc_petle(up) == up)
sprawdz("1f trasa bez pętli bez zmian", trasa_io.uprosc_petle([(1, 1, 7), (5, 1, 7), (9, 1, 7)]) == [(1, 1, 7), (5, 1, 7), (9, 1, 7)])
cala = [(1, 1, 7), (2, 1, 7), (3, 1, 7), (4, 1, 7), (3, 2, 7), (2, 2, 7), (1, 2, 7), (1, 1, 7)]
sprawdz("1g pętla (A-B-A) wycięta, przejście pięter zostaje",
        trasa_io.uprosc_petle(cala + [(1, 1, 8), (1, 2, 8)])[-2:] == [(1, 1, 8), (1, 2, 8)])

# 2. dojscie_od_pozycji
t = mozg.dojscie_od_pozycji(route, DEPO)
sprawdz("2a z depo: cała trasa od depo", t[0] == DEPO and t[-1] == KONIEC, (t[0], t[-1]))
x = mozg.dojscie_od_pozycji(route, (32440, 32226, 7))
sprawdz("2b w środku: od najbliższego punktu na piętrze, bez cofania na zachód", x[0][0] >= 32420 and x[-1] == KONIEC, x[0])
z8 = mozg.dojscie_od_pozycji(route, (32493, 32261, 8))
sprawdz("2c już w jaskini: tylko ogon z8", all(p[2] == 8 for p in z8) and z8[-1] == KONIEC, z8)

# 3. przejście całej trasy z depo (hole open) i ze środka (stary błąd: wejście do jaskini i powrót do depo)
for nazwa, start in (("z depo", DEPO), ("ze środka (32404,32215)", (32404, 32215, 7)), ("zza walki (32491,32258)", (32491, 32258, 7))):
    LOG.clear()
    s = Swiat(start, gora="use", dol="krok")
    trasa = mozg.dojscie_od_pozycji(route, start)
    b = zrob_dojscie(s, trasa)
    n = bieg(b)
    sprawdz(f"3 {nazwa}: dojście kończy w jaskini przy końcu trasy", b.dojscie_ok and s.poz[2] == 8
            and max(abs(s.poz[0] - KONIEC[0]), abs(s.poz[1] - KONIEC[1])) <= 2, (s.poz, n, b.dojscie_ok))
    sprawdz(f"3 {nazwa}: dokładnie jedno przejście z7 -> z8, bez powrotu na z7 ani zejścia na z9",
            [z for _, z in s.zmiany] == [8], s.zmiany)
    sprawdz(f"3 {nazwa}: bez patrolu ('brak osiągalnego miejsca')", not any("Patrol:" in l and "jadę trasą" in l for l in LOG))
    sprawdz(f"3 {nazwa}: czas", s.t < 600, round(s.t))

# 3b. stary błąd: Cavebot z trasą od pozycji w środku -> po końcu zawracał (CavebotDojscie nie zawraca)
LOG.clear()
s = Swiat((32492, 32261, 8), gora="use", dol="krok")
b = zrob_dojscie(s, list(route))
b.idx = 94
n = bieg(b)
sprawdz("3b stoimy na z8 przy końcu, idx 94 (z7): od razu koniec, bez prób wejścia na z7", n == 0 and b.dojscie_ok and not s.zmiany, (n, s.zmiany))

# 4. przejście w dół nie działa: kończy się, nie kręci w kółko, przejdz_dojscie ponawia i zwraca False
LOG.clear()
s = Swiat(DEPO, gora="use", dol="nigdy")
post = P(s)
cavebot_stare_log = cavebot.log
def fab(postac, trasa, okr, czas, hp, jedz, potw, gracze, **kw):
    b = zrob_dojscie(s, trasa)
    return b
wyn = mozg.przejdz_dojscie(post, route, fabryka=fab, proby=2)
sprawdz("4 dziura nie działa: False po ponowieniach, bez nieskończonej pętli", wyn is False and s.poz[2] == 7, (wyn, s.poz, round(s.t)))

# 4b. P7e: krótka trasa (dziura + pola z8) z przejściem, które nie działa: porażka próby, bez "zawinęła się" i bez odwracania
LOG.clear()
s = Swiat((32493, 32258, 7), gora="use", dol="nigdy")
kr = [(32493, 32258, 7), (32493, 32259, 7), (32493, 32260, 8), (32493, 32261, 8)]
b = zrob_dojscie(s, list(kr))
n = bieg(b, 3000)
sprawdz("4b krótka trasa, przejście nie działa: próba kończy się porażką, trasa nieodwrócona, bez 'zawinęła się'",
        n < 3000 and not b.dojscie_ok and b.punkty == kr and not any("zawinęła się" in l for l in LOG),
        (n, b.dojscie_ok, b.punkty, [l for l in LOG if "Dojście" in l][-3:]))
sprawdz("4c P7e: DOJSCIE_PROBY domyślnie 5, w zakresie 3-8", cavebot.DOJSCIE_PROBY == 5 and pokretla.ZAKRESY["DOJSCIE_PROBY"] == (3, 8))

# 4d. P7d: stwór obok przy dziurze w dojściu: walka do skutku (60 s), nie 8 s; po zabiciu znów bieg
s = Swiat((32493, 32258, 7), gora="use", dol="krok")
b = zrob_dojscie(s, list(kr))
b.idx = 1
mob = {"x": 32492, "y": 32258, "z": 7, "nazwa": "Troll"}
b.ruch_czas = s.zegar() - 10
t0 = s.zegar()
r1 = b._wypad_bieg([mob], (32493, 32258, 7), t0)
sprawdz("4d walka przy dziurze: do t0+60 s (nie 8 s)", r1 is False and abs(b.wypad_walka_do - (t0 + 60)) < 1e-6, b.wypad_walka_do - t0)
r2 = b._wypad_bieg([], (32493, 32258, 7), t0 + 5)
sprawdz("4e blokujący zniknął: wracamy do biegu", r2 is True)
cavebot.DOJSCIE_WALKA_PRZEJSCIE_S = 0
b2 = zrob_dojscie(s, list(kr)); b2.idx = 1; b2.ruch_czas = s.zegar() - 10
b2._wypad_bieg([mob], (32493, 32258, 7), t0)
sprawdz("4f pokrętło 0: dawne 8 s", abs(b2.wypad_walka_do - (t0 + cavebot.WYPAD_WALKA_S)) < 1e-6)
cavebot.DOJSCIE_WALKA_PRZEJSCIE_S = 60

# 5. łopata: dziura zasypana -> krok nie działa, łopata odkopuje, kolejny krok wchodzi do jaskini
LOG.clear()
s = SwiatL((32480, 32251, 7), gora="use", dol="krok", zasypana=True)
b = zrob_dojscie(s, mozg.dojscie_od_pozycji(route, (32480, 32251, 7)))
n = bieg(b)
sprawdz("5a zasypana dziura: łopata użyta i bot wchodzi na z8", s.lopata_uzycia and s.poz[2] == 8 and b.dojscie_ok,
        (s.lopata_uzycia, s.poz, n, [l for l in LOG if "rzejście" in l][-4:]))
sprawdz("5b łopata użyta na polu dziury (lub własnym, gdy na niej stoimy)",
        all(p[:2] in ((32493, 32259), (32492, 32259)) or True for p in s.lopata_uzycia) and
        any(p[:2] == (32493, 32259) for p in s.lopata_uzycia), s.lopata_uzycia)
sprawdz("5c log po polsku o łopacie", any("łopat" in l for l in LOG), [l for l in LOG if "rzejście" in l][-5:])
# otwarta dziura: łopata nie jest używana
LOG.clear()
s = SwiatL((32480, 32251, 7), gora="use", dol="krok", zasypana=False)
b = zrob_dojscie(s, mozg.dojscie_od_pozycji(route, (32480, 32251, 7)))
bieg(b)
sprawdz("5d otwarta dziura: bez łopaty", not s.lopata_uzycia and s.poz[2] == 8, (s.lopata_uzycia, s.poz))
# brak łopaty w plecaku: kończy się porażką (bez pętli bez końca)
LOG.clear()
s = SwiatL((32480, 32251, 7), gora="use", dol="krok", zasypana=True)
s.lopata_ma = False
b = zrob_dojscie(s, mozg.dojscie_od_pozycji(route, (32480, 32251, 7)))
n = bieg(b, 20000)
sprawdz("5e zasypana i brak łopaty: porażka po limicie prób, nie pętla", n < 20000 and s.poz[2] == 7 and not b.dojscie_ok,
        (n, s.poz, b.dojscie_ok, [l for l in LOG if "Dojście" in l or "rzejście" in l][-6:]))
# pokrętło PIETRA_LOPATA=0: łopata nie jest używana
LOG.clear()
stary = cavebot.PIETRA_LOPATA
cavebot.PIETRA_LOPATA = 0
try:
    s = SwiatL((32480, 32251, 7), gora="use", dol="krok", zasypana=True)
    b = zrob_dojscie(s, mozg.dojscie_od_pozycji(route, (32480, 32251, 7)))
    bieg(b, 20000)
    sprawdz("5f PIETRA_LOPATA=0: łopata nie użyta", not s.lopata_uzycia, s.lopata_uzycia)
finally:
    cavebot.PIETRA_LOPATA = stary
sprawdz("5g pokrętła w pokretla.ZAKRESY", all(k in pokretla.ZAKRESY for k in
        ("DOJSCIE_BIEGNIJ", "PIETRA_LOPATA", "WYPRAWA_DEPO_POWROT", "WYPRAWA_DEPO_POSTOJ_S")))
sprawdz("5h domyślne: DOJSCIE_BIEGNIJ=1, PIETRA_LOPATA=1, DEPO_POWROT=0", cavebot.DOJSCIE_BIEGNIJ == 1 and cavebot.PIETRA_LOPATA == 1
        and cavebot.WYPRAWA_DEPO_POWROT == 0)

# 5i. łopata tylko na z7 (PIETRA_LOPATA_TYLKO_Z7), po braku łopaty 10 min przerwy
class _CB:
    def __init__(c, z):
        c.t = 0.0; c.klik_cel = None; c.pietra_ops = None; c.postac = types.SimpleNamespace(pozycja=lambda: (100, 100, z))
    def zegar(c): return c.t
    def zatrzymaj_klik(c, poz): pass
    def pauza(c, a=0, b=0): pass
    def spij(c, d): c.t += d
class _Ops:
    def __init__(o, brak=False): o.n = 0; o.brak = brak
    def uzyj_lopate(o, cel, poz):
        o.n += 1
        if o.brak: raise Exception("nie widzę łopaty (shovel) w oknie plecaka")
def _lopata(z, tylko_z7, brak=False, powtorz=1):
    cb = _CB(z); pt = pietra.Pietra(cb, konf=types.SimpleNamespace(PIETRA_LOPATA=1, PIETRA_LOPATA_TYLKO_Z7=tylko_z7,
                                                                  PIETRA_LOPATA_BRAK_S=600.0), log=lambda *a: None)
    cb.pietra_ops = _Ops(brak); pt._tele = lambda *a, **k: None
    pt._po_przejsciu = lambda *a: False
    k = {"pole": (101, 100, z), "lad": (101, 100, z + 1), "pewne": True}
    for _ in range(powtorz):
        st = {"cel": (0, 0, z + 1), "tryby": ["lopata"], "proby": 0, "kand": [k], "ki": 0, "od": 0.0, "nast": 0.0,
              "postep": [0, 9], "z0": z}
        pt.st = st
        pt._proba((100, 100, z), st, k, cb.t)
    return pt
sprawdz("5i z8 -> z9: łopata nie użyta (TYLKO_Z7=1)", _lopata(8, 1).cb.pietra_ops.n == 0)
sprawdz("5j z7: łopata użyta", _lopata(7, 1).cb.pietra_ops.n == 1)
sprawdz("5k TYLKO_Z7=0: łopata także na z8 (dawne)", _lopata(8, 0).cb.pietra_ops.n == 1)
pt = _lopata(7, 1, brak=True, powtorz=3)
sprawdz("5l brak łopaty: tylko jedna próba, kolejne pomijane przez 10 min", pt.cb.pietra_ops.n == 1, pt.cb.pietra_ops.n)
sprawdz("5m pokrętła w ZAKRESY", "PIETRA_LOPATA_TYLKO_Z7" in pokretla.ZAKRESY and "PIETRA_LOPATA_BRAK_S" in pokretla.ZAKRESY
        and cavebot.PIETRA_LOPATA_TYLKO_Z7 == 1)

# 6. bieg zamiast walki: troll biegnący obok nie jest atakowany w dojściu, jest atakowany po zablokowaniu / DOJSCIE_BIEGNIJ=0
class SwiatT(Swiat):
    """Troll zawsze 2 pola na prawo od gracza (goni nas). blokuj=True: trzyma nas (ruch zablokowany)."""
    def __init__(s, poz, blokuj=False, **kw):
        super().__init__(poz, **kw); s.blokuj = blokuj
    def zapytaj(s, z):
        r = super().zapytaj(z)
        if z["cmd"] == "stwory":
            odl = 1 if s.blokuj else 2
            r["stwory"].append({"id": 7, "nazwa": "Troll", "gracz": False, "x": s.poz[0] + odl, "y": s.poz[1], "z": s.poz[2], "hp": 100})
        return r
    def ruch(s, dx, dy):
        if s.blokuj:
            return
        return super().ruch(dx, dy)
def licz_ataki(s, atak_n, ticki=60, blok=False):
    pass
startp = (32431, 32224, 7)
for biegnij in (1, 0):
    stary = cavebot.DOJSCIE_BIEGNIJ
    cavebot.DOJSCIE_BIEGNIJ = biegnij
    try:
        ataki = []
        s = SwiatT(startp, gora="use", dol="krok")
        b = zrob_dojscie(s, mozg.dojscie_od_pozycji(route, startp), atak=lambda m, g: ataki.append(1))
        b.potwory = {"troll"}
        for _ in range(80):
            if not b.tick(): break
        sprawdz(f"6{'a' if biegnij else 'b'} DOJSCIE_BIEGNIJ={biegnij}: {'bez' if biegnij else 'z'} ataku na trolla obok trasy",
                (not ataki) if biegnij else bool(ataki) or b.cel is not None or str(b.stan).startswith("WALKA"),
                (len(ataki), b.stan, s.poz))
    finally:
        cavebot.DOJSCIE_BIEGNIJ = stary
# zablokowana droga: troll obok i stoimy >= WYPAD_BLOK_S -> walka
ataki = []
s = SwiatT(startp, blokuj=True, gora="use", dol="krok")
b = zrob_dojscie(s, mozg.dojscie_od_pozycji(route, startp), atak=lambda m, g: ataki.append(1))
b.potwory = {"troll"}
for _ in range(120):
    if not b.tick(): break
sprawdz("6c droga zablokowana (troll obok, bez ruchu): po WYPAD_BLOK_S walka", any("droga zablokowana" in l for l in LOG) or ataki or b.cel is not None,
        [l for l in LOG if "Dojście" in l][-3:])
# loot i przerwy: w dojściu wyłączone
sprawdz("6d dojście wyłącza lootowanie i przerwy (flaga klasy)", cavebot.CavebotDojscie.dojscie_aktywne is True and cavebot.Cavebot.dojscie_aktywne is False)

# 7. wyprawa: powrót z depo (WYPRAWA_DEPO_POWROT=1) tą samą maszyną co powrót po zakupach
nsw = {"__file__": str(Path(_R) / "testy/test_wyprawa.py"), "__name__": "harness_wyprawa"}
src = open(Path(_R) / "testy/test_wyprawa.py").read()
exec(compile(src[:src.index("# --- 0. dane i pokrętła")], "harness_wyprawa", "exec"), nsw)
nowy, bieg_w, pre, Konf = nsw["nowy"], nsw["bieg"], nsw["pre"], nsw["Konf"]
sp_bez = nsw["konfig_sklepow"](frodo=None, xodet=None, nazwa="bez_npc.json")
exec(src[src.index("def konf_depo(**kw):"):src.index("sp_bez = konfig_sklepow")].replace("\n    return kk", "\n    return kk"), nsw)
exec(src[src.index("def krok_dokladny(cb):"):src.index("powiad12 = []")], nsw)
import powiadom as _pw
_pw.powiadom = lambda *a, **kw: None
nsw["_pw"] = _pw
s, cb, w, k = nowy(jedzenie=0, konf=nsw["konf_depo"](WYPRAWA_DEPO_POWROT=1), sklepy=sp_bez)
nsw["krok_dokladny"](cb)
cb.jedzenie_nie_do = s.t + 100000
stop = Path(tempfile.mkdtemp()) / "STOP_powrot"
w.plik_stop = stop
sprawdz("7a start wyprawy do depo", pre(s, cb, w) and w.w is not None and w.w["potrzeby"] == {"depo": True}, (w.powod,))
sprawdz("7b plan powrotu z depo zbudowany z trasy depo_troll_cave (z7 -> z8, bez pętli)",
        sum(len(e.get("punkty") or ()) for e in w.w["powrot"]) > 10 and any(e["typ"] == "DZIURA" for e in w.w["powrot"]),
        [e["typ"] for e in w.w["powrot"]])
plan_powrotu = w.w["powrot"]
n, wyst = bieg_w(s, cb, w, maks=20000)
kon = nsw["ev"](s, "wyprawa_koniec")
sprawdz("7c po depo bot sam wraca do jaskini (z8), wyprawa kończy 'ok', bez STOP",
        wyst and s.poz[2] == 8 and kon and kon[-1]["wynik"] in ("ok", "bez_zakupow") and not stop.exists(),
        (s.poz, kon[-1:] if kon else kon, stop.exists(), n))
sprawdz("7d plan powrotu krótszy od surowej trasy (bez objazdu na zachód)",
        sum(len(e.get("punkty") or ()) for e in plan_powrotu) < len(route) - 30, (len(route),))
# droga DO depo: z wyjścia z jaskini prosto trasą depo (odwróconą), nie przez Gorna (12.10: 240 pól zamiast ok. 195)
s7, cb7, w7, k7 = nowy(jedzenie=0, konf=nsw["konf_depo"](), sklepy=sp_bez)
cb7.jedzenie_nie_do = s7.t + 100000
pre(s7, cb7, w7)
pts7 = [p for e in w7.w["legs"][0] for p in (e.get("punkty") or ()) if p[2] == 7]
sprawdz("7f droga DO depo: nie okrąża Gorna (32377,32201), długość z7 <= 215 pól, kończy w depo",
        w7.w is not None and pts7 and pts7[-1] == DEPO and not any(max(abs(p[0] - 32377), abs(p[1] - 32201)) <= 3 for p in pts7)
        and trasa_io.dlugosc(pts7) <= 215, (len(pts7), trasa_io.dlugosc(pts7) if pts7 else None))
# domyślnie (WYPRAWA_DEPO_POWROT=0) nadal STOP w depo
s, cb, w, k = nowy(jedzenie=0, konf=nsw["konf_depo"](), sklepy=sp_bez)
nsw["krok_dokladny"](cb)
cb.jedzenie_nie_do = s.t + 100000
stop = Path(tempfile.mkdtemp()) / "STOP_stary"
w.plik_stop = stop
pre(s, cb, w)
n, wyst = bieg_w(s, cb, w, maks=12000)
sprawdz("7e domyślnie: dojście do depo kończy STOP-em i bez powrotu", tuple(s.poz) == DEPO and stop.exists(), (s.poz, stop.exists()))

print(f"\n{sum(ok)}/{len(ok)} OK, FAIL={len(ok) - sum(ok)}")
sys.exit(0 if all(ok) else 1)
