"""Kieszeń z dziury (15.10, 21:33:59): Troll (32509,32273,8) przy dziurze (32508,32273,8); klient szedł za celem i wpadł na z9
w zamkniętą kieszeń (32506..32510, 32267..32273, 9), z której wychodzą tylko drabiny/schody (flaga 2 na z9).
Testy: (a) upadek do kieszeni = NIE "na trasie" (punkty trasy na z9 są nieosiągalne), plan wychodzi drabiną; (b) upadek na
piętro z osiągalnym punktem trasy = dawne zachowanie; (c) start bota w kieszeni bez upadku (patrol: brak osiągalnego miejsca)
= to samo wyjście; (d) cel przy dziurze: pominięty / bezpieczna droga. Atrapy + PRAWDZIWA mapa serwera (mapa.py)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, tempfile, types
sys.dont_write_bytecode = True
_R = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _R)
import cavebot, bot, mapa as _mapa, wpadniecie, pokretla
from pathlib import Path

TRASY = Path(_R) / "trasy"
LOG = []
cavebot.log = lambda *a: LOG.append(" ".join(map(str, a)))
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

M = _mapa.Mapa()
def f(x, y, z): return M.flagi(x, y, z)
def idzie(x, y, z):
    v = f(x, y, z); return bool(v & 1) and not v & 4 and not v & 2

DZIURA = (32508, 32273, 8)
PRZED = (32507, 32270, 8)
LAD = (32508, 32273, 9)              # lądowanie z logu 21:33:59
KIESZEN_POZ = (32508, 32272, 9)
# drabiny/schody w górę z kieszeni (flaga 2 na z9) -> pole na z8, na które wychodzimy (założenie symulatora)
GORA = {(32506, 32269, 9): (32506, 32270, 8), (32506, 32270, 9): (32506, 32269, 8)}
sprawdz("0 mapa: dziura (32508,32273,8) ma flagę 2, lądowanie na z9 chodliwe", f(*DZIURA) & 2 and idzie(*LAD), f"{f(*DZIURA)} {f(*LAD)}")
sprawdz("0 mapa: drabiny kieszeni mają flagę 2 na z9", all(f(*t) & 2 for t in GORA), [f(*t) for t in GORA])

nowa = [tuple(p) for p in json.loads((TRASY / "troll_nowa_czesc.json").read_text())]
sprawdz("0 trasa troll_nowa_czesc ma punkty na z8 i z9", {p[2] for p in nowa} == {8, 9})


class Swiat:
    """Marsz klikiem/krokiem po mapie; upadek na dziurze w dół (flaga 2, nie z listy GORA); drabiny GORA (krok na pole albo Use)."""
    def __init__(s, poz, gora=GORA):
        s.t = 0.0; s.poz = list(poz); s.gora = dict(gora); s.cel = None; s.stoi = False
        s.zmiany = []; s.uzycia = []; s.liny = []; s.nielegalne = 0; s.klikniecia = []; s.stwory = []
    def zegar(s): return s.t
    def klik(s, dx, dy): s.cel = (s.poz[0] + dx, s.poz[1] + dy, s.poz[2]); s.klikniecia.append((dx, dy))
    def spij(s, d):
        s.t += d
        c = s.cel
        if s.stoi or c is None or d < 0.08 or tuple(s.poz) == c:
            return
        start = tuple(s.poz); skad = {start: None}; q = [start]
        for a in q:
            if a == c or len(skad) > 4000: break
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (a[0] + dx, a[1] + dy, a[2])
                    if (dx or dy) and n not in skad and idzie(*n):
                        skad[n] = a; q.append(n)
        if c not in skad:
            s.cel = None; return
        sciezka = []; a = c
        while a != start: sciezka.append(a); a = skad[a]
        for n in sciezka[::-1][:max(1, int(d / 0.2))]:
            z0 = s.poz[2]
            s.ruch(n[0] - s.poz[0], n[1] - s.poz[1])
            if s.poz[2] != z0:
                s.cel = None
                break
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}] + s.stwory}
    def ruch(s, dx, dy):
        x, y, z = s.poz[0] + dx, s.poz[1] + dy, s.poz[2]
        v = f(x, y, z)
        if not v & 1 or v & 4:
            s.nielegalne += 1; return
        if (x, y, z) in s.gora:                              # drabina/schody w górę
            s.zmiany.append((tuple(s.poz), z - 1)); s.poz[:] = list(s.gora[(x, y, z)]); return
        if v & 2:                                            # dziura w dół
            s.zmiany.append((tuple(s.poz), z + 1)); s.poz[:] = [x, y, z + 1]; return
        s.poz[0], s.poz[1] = x, y
    def uzyj(s, pole):
        s.uzycia.append(tuple(pole))
        if tuple(pole) in s.gora and max(abs(pole[0] - s.poz[0]), abs(pole[1] - s.poz[1])) <= 1:
            s.zmiany.append((tuple(s.poz), pole[2] - 1)); s.poz[:] = list(s.gora[tuple(pole)])
    def uzyj_line(s, pole): s.liny.append(tuple(pole))


class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k):
        if k in bot.KIERUNKI and not p.s.stoi:
            p.s.t += 0.2; p.s.ruch(*bot.KIERUNKI[k])
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2; przed = tuple(p.s.poz); p.s.ruch(*d); return tuple(p.s.poz) != przed


class Ops:
    def __init__(o, s): o.s = s
    def uzyj_pole(o, pole, poz): o.s.uzyj(pole)
    def uzyj_line(o, pole, poz): o.s.uzyj_line(pole)


ALARMY = []
import powiadom
powiadom.powiadom = lambda *a, **k: None


def nowy(poz, trasa, atak=None, **kw):
    LOG.clear(); ALARMY.clear()
    kat = Path(tempfile.mkdtemp())
    wpadniecie.PLIK_DZIUR = kat / "dziury_nauczone.json"
    s = Swiat(poz)
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
    b = cavebot.Cavebot(P(s), list(trasa), zapytaj=s.zapytaj, atak=atak or (lambda m, g: None), alarm=lambda w: ALARMY.append(w),
                        spij=s.spij, zegar=s.zegar, loot=loot, mapa=M, klik=s.klik, **kw)
    b.pietra_ops = Ops(s)
    if b.pokretla is not None:
        kopia = kat / "na_zywo.json"; kopia.write_text("{}"); b.pokretla.plik = kopia
    w = b._wp()
    w.plik_stop = kat / "STOP"
    b.kat = kat
    return s, b


def bieg(b, n, az=None):
    for i in range(n):
        if az and az(): return i
        if not b.tick(): return i
    return n


# --- (a) upadek do kieszeni: punkty trasy na z9 są nieosiągalne -> NIE "na trasie", wyjście drabiną ---
s, b = nowy(PRZED, nowa)
w = b._wp()
sprawdz("a0 z9 ma punkty trasy (stara reguła 'piętro na trasie' dałaby: dalej normalnie)", w._trasa_na_pietrze(9))
sprawdz("a0 z kieszeni żaden punkt trasy nie jest osiągalny A*", not w._trasa_osiagalna(KIESZEN_POZ))
s.poz[:] = list(PRZED); s.stoi = True
b.tick()
s.poz[:] = list(LAD)
b.tick()
sprawdz("a1 log 'Wpadłem' z (32507,32270,8) -> (32508,32273,9)", "Wpadłem: (32507,32270,8) -> (32508,32273,9)" in LOG, [l for l in LOG if "Wpad" in l][:2])
sprawdz("a1 NIE 'dalej normalnie'", not any("dalej normalnie" in l for l in LOG))
sprawdz("a1 log o kieszeni (brak osiągalnego punktu)", any("kieszeń" in l for l in LOG))
sprawdz("a1 stan WPADNIECIE (z0=8, z1=9)", w.st is not None and w.st["z0"] == 8 and w.st["z1"] == 9, str(w.st))
s.stoi = False
n = bieg(b, 1500, az=lambda: s.poz[2] == 8 and w.st is None)
sprawdz("a2 wyszedł na z8", s.poz[2] == 8 and w.st is None, f"{s.poz} ticki={n} t={s.t:.0f}s")
sprawdz("a2 wyjście drabiną z kieszeni (zmiana z9 -> z8)", any(z == 8 and p[2] == 9 for p, z in s.zmiany), f"{s.zmiany}")
sprawdz("a2 log planu z niepewnym przejściem '?' na z9", any("plan po mapie" in l and "z9>z8?" in l for l in LOG), [l for l in LOG if "plan po mapie" in l][:2])
sprawdz("a2 bez STOP i alarmu", not (b.kat / "STOP").exists() and not ALARMY)
sprawdz("a2 nauczona dziura (32508,32273,8)", DZIURA in wpadniecie.Wpadniecie(b, konf=cavebot, log=lambda t: None, plik=wpadniecie.PLIK_DZIUR).dziury)

# plan na prawdziwej mapie: z (32508,32272,9) istnieje plan do z8 przez drabinę kieszeni
s, b = nowy(KIESZEN_POZ, nowa)
w = b._wp(); w.st = {"z0": 8, "z1": 9, "od": 0.0, "p0": PRZED, "lad": LAD, "lina": 3, "dojscie": 0, "nast": 0.0, "zle": set(),
                     "krok": None, "brak_planu": 0, "alarm": False, "osiag": (0.0, False)}
plan = w._znajdz_plan(KIESZEN_POZ, set())
sprawdz("a3 _znajdz_plan: plan z kieszeni na z8 istnieje", plan is not None and plan[-1]["L"][2] == 8, f"{plan}")
plan2 = w._znajdz_plan(KIESZEN_POZ, {(32508, 32273, 9)})          # rope spot pod dziurą odpadł (np. brak liny)
sprawdz("a3 bez rope spotu plan idzie drabiną z flagą 2 na z9 (niepewne przejście na własnym piętrze)",
        plan2 is not None and plan2[0]["T"] in GORA and not plan2[0]["pewne"] and plan2[0]["zrodlo"] == "mapa_flaga2_tu", f"{plan2}")

# --- (b) upadek na piętro z osiągalnym punktem trasy: dawne zachowanie ---
trasa_b = [(32508, 32271, 9), (32509, 32270, 9), (32507, 32269, 9)]    # w tej samej kieszeni, osiągalne
s, b = nowy(PRZED, trasa_b)
w = b._wp()
sprawdz("b0 z kieszeni punkt trasy jest osiągalny", w._trasa_osiagalna(KIESZEN_POZ))
s.poz[:] = list(PRZED); s.stoi = True
b.tick()
s.poz[:] = list(LAD)
b.tick()
sprawdz("b1 'Wpadłem' + 'dalej normalnie', brak stanu WPADNIECIE", any("Wpadłem" in l for l in LOG) and any("dalej normalnie" in l for l in LOG) and w.st is None,
        [l for l in LOG if "Wpad" in l][:3])
sprawdz("b1 bez wyjścia: brak planu/liny", not any("plan po mapie" in l or "lina" in l.lower() for l in LOG))

# --- (c) start w kieszeni bez wykrytego upadku: patrol bez osiągalnego miejsca -> to samo wyjście ---
s, b = nowy(KIESZEN_POZ, nowa)
w = b._wp()
sprawdz("c0 brak stanu na starcie", w.st is None)
sprawdz("c1 z_kieszeni uruchamia wyjście (z0=8)", w.z_kieszeni(KIESZEN_POZ, 0.0) is True and w.st and w.st["z0"] == 8 and w.st["z1"] == 9, str(w.st))
sprawdz("c1 ponowne wywołanie w stanie: False", w.z_kieszeni(KIESZEN_POZ, 0.0) is False)
s.stoi = False
n = bieg(b, 1500, az=lambda: s.poz[2] == 8 and w.st is None)
sprawdz("c2 wyszedł na z8 drabiną", s.poz[2] == 8 and w.st is None and not ALARMY, f"{s.poz} ticki={n}")
# nie-kieszeń: pole z osiągalnym punktem trasy nie wchodzi w stan
s, b = nowy(KIESZEN_POZ, trasa_b)
sprawdz("c3 piętro z osiągalnym punktem: z_kieszeni = False", b._wp().z_kieszeni(KIESZEN_POZ, 0.0) is False)
# hak w cavebot: patrol bez osiągalnego miejsca woła z_kieszeni
wywolane = []
s, b = nowy(KIESZEN_POZ, nowa)
b._patrol_wybierz = lambda poz: None
b._patrol_sync_idx = lambda poz: None
b.patrol_fallback_do = float("-inf"); b.patrol = None
wp_ = b._wp(); oryg = wp_.z_kieszeni
wp_.z_kieszeni = lambda poz, teraz: (wywolane.append(tuple(poz)), oryg(poz, teraz))[1]
wynik = b._idz_patrol()
sprawdz("c4 _idz_patrol: 'brak osiągalnego miejsca' -> z_kieszeni -> obieg zużyty, stan WPADNIECIE",
        wynik is True and wywolane == [KIESZEN_POZ] and wp_.st is not None, f"{wynik} {wywolane}")

# --- (d) cel przy dziurze ---
def troll(x, y, z=8, i=7): return {"id": i, "nazwa": "Troll", "x": x, "y": y, "z": z, "hp": 28, "gracz": False}
s, b = nowy(PRZED, [(32507, 32267, 8), (32507, 32270, 8)])
poz = PRZED
sprawdz("d0 dziura (32508,32273,8) wg mapy w pobliżu trolla (32509,32273)", b._dziury_przy((32509, 32273), 8) == {(32508, 32273)}, b._dziury_przy((32509, 32273), 8))
# incydent: troll (32509,32273) z (32507,32270): bezpieczna droga (32508,32271)->(32509,32272) istnieje, więc "idz" (sami, bez kliku)
sprawdz("d1 incydent: bezpieczna droga obok celu -> 'idz'", b._cel_przez_dziure(troll(32509, 32273), poz) == "idz", b._cel_przez_dziure(troll(32509, 32273), poz))
# zablokuj bezpieczną drogę (stwory/ściana): troll za dziurą bez drogi -> skip
b.sciany = set()
s2, b2 = nowy((32508, 32271, 8), [(32507, 32267, 8)])
b2._wp().ucz((32509, 32272, 8)); b2._wp().ucz((32508, 32272, 8))     # nauczone dziury (ściany) zamykają dojście
sprawdz("d2 troll (32509,32273) z (32508,32271), dojście zamknięte nauczonymi dziurami -> skip",
        b2._cel_przez_dziure(troll(32509, 32273), (32508, 32271, 8)) == "skip", b2._cel_przez_dziure(troll(32509, 32273), (32508, 32271, 8)))
# cel obok nas: bez zastrzeżeń
sprawdz("d3 cel obok nas (odl 1): None", b._cel_przez_dziure(troll(32508, 32271), (32507, 32270, 8)) is None)
# dziura poza prostokątem między nami a celem: None
sprawdz("d4 dziura za celem (nie w prostokącie): None", b._cel_przez_dziure(troll(32509, 32273), (32511, 32275, 8)) is None)
sprawdz("d4b cel daleko od dziur: None", b._cel_przez_dziure(troll(32507, 32267), poz) is None)
cavebot.DZIURA_PRZY_CELU = 0
try:
    sprawdz("d5 pokrętło DZIURA_PRZY_CELU=0: None", b2._cel_przez_dziure(troll(32509, 32273), (32508, 32271, 8)) is None)
finally:
    cavebot.DZIURA_PRZY_CELU = 1

# tick: troll przy dziurze, droga zamknięta -> brak ataku i kliku, log [DZIURA]
ATAKI = []
s, b = nowy((32508, 32271, 8), [(32507, 32267, 8), (32507, 32270, 8)], atak=lambda m, g: ATAKI.append(m["id"]))
b._wp().ucz((32509, 32272, 8)); b._wp().ucz((32508, 32272, 8))
s.stwory = [troll(32509, 32273)]; s.stoi = True
for _ in range(4): b.tick()
sprawdz("d6 tick: brak ataku na trolla przy dziurze", not ATAKI, ATAKI)
sprawdz("d6 tick: log [DZIURA] odpuszczam", any("[DZIURA]" in l and "odpuszczam" in l for l in LOG), [l for l in LOG if "DZIURA" in l][:2])
# tick: troll przy dziurze, bezpieczna droga -> idziemy sami (bez ataku), po dojściu obok atak
ATAKI.clear()
s, b = nowy(PRZED, [(32507, 32267, 8), (32507, 32270, 8)], atak=lambda m, g: ATAKI.append((m["id"], tuple(s.poz))))
s.stwory = [troll(32509, 32273)]
for _ in range(12):
    b.tick()
    if ATAKI: break
sprawdz("d7 tick: najpierw 'idę sam', atak dopiero z pola obok celu", any("idę sam" in l for l in LOG) and (not ATAKI or max(abs(ATAKI[0][1][0] - 32509), abs(ATAKI[0][1][1] - 32273)) <= 1),
        f"{ATAKI[:1]} {[l for l in LOG if 'DZIURA' in l][:1]}")
sprawdz("d7 tick: nie wpadł (z8)", s.poz[2] == 8 and not s.zmiany, f"{s.poz} {s.zmiany}")

print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
