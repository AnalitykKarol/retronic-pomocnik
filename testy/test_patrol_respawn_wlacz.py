#!/usr/bin/env python3
"""20.10 (SPEC_patrol_respawn_1015, krok 3): pokrętło PATROL_RESPAWN. Przy 1 patrol IDZIE do celu wybranego metodą respawnu
(mapa obecności), gdy metoda ma zdanie; inaczej dzisiejsze losowanie wg wag. Sprawdzamy: przy 0 nic się nie zmienia, świeżo
wyczyszczone miejsce przegrywa z dawno niewidzianym, brak danych = dzisiejszy wybór (ten sam los), blokady miejsc (gracz,
pamięć gracza, rezerwacja KOORD, patrol_blok, historia, runda) są respektowane, brak drogi = następny kandydat, telemetria
patrol_cel ma pole `metoda`, log ma wartość, działa też przy PATROL_RESPAWN_CIEN=0. Wyłącznie atrapy, bez gry."""
import json
import os
import random
import sys
import tempfile
import time
import types
from pathlib import Path

os.environ["RETRONIC_TESTY"] = "1"
sys.dont_write_bytecode = True
_R = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, _R)

import bot  # noqa: E402
import cavebot  # noqa: E402
import mapa as _mapa  # noqa: E402
import obecnosc  # noqa: E402
import telemetria  # noqa: E402

wyniki = []
LOG = []
cavebot.log = lambda *a: LOG.append(" ".join(map(str, a)))


def sprawdz(nazwa, warunek, info=""):
    wyniki.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + (f"  {info}" if not warunek and info else ""))


# deterministycznie: bez losowych dodatków i pauz (jak test_decyzje_log.py)
cavebot.REAKCJA = (0.0, 0.0)
cavebot.DRUGI_CEL = 0.0
cavebot.ROZRZUT_PROGU = 0.0
cavebot.STRAZNIK_CEL = 0
cavebot.ODWROCENIE_TRASY = 0.0
cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5)
cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False
cavebot.DECYZJE_LOG = 1
for _h in ("_hak_telemetrii", "_hak_pochodni", "_hak_wypadu"):
    setattr(cavebot.Cavebot, _h, lambda self: None)


def ustaw(**kw):
    """Pokrętła na czas jednego przebiegu (domyślnie: cień 1, respawn 0, runda 1)."""
    cavebot.PATROL_RESPAWN_CIEN = kw.get("cien", 1)
    cavebot.PATROL_RESPAWN = kw.get("resp", 0)
    cavebot.PATROL_RUNDA = kw.get("runda", 1)



TRASY = Path(_R) / "trasy"
MI = json.loads((TRASY / "miejsca_troll.json").read_text())
START = tuple(MI["start"])
TROLL_TRASA = [tuple(p) for p in json.loads((TRASY / f"{MI['trasa']}.json").read_text())]
cavebot.TRYB_PATROL = 1
cavebot.PATROL_PLIK = "miejsca_troll.json"
M = _mapa.Mapa()


class SwiatC:
    def __init__(s, poz):
        s.t = 1000.0
        s.poz = list(poz)
        s.zapytan = 0

    def zegar(s):
        return s.t

    def spij(s, d):
        s.t += d

    def zapytaj(s, z):
        s.zapytan += 1
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 195, "max_hp": 195, "mana": 95, "max_mana": 95}}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2],
                                "hp": 100}]}


class PC:
    nazwa = "Ja"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        return tuple(p.s.poz)

    def klawisz(p, k):
        pass


def zrob_c(poz=START):
    s = SwiatC(poz)
    b = cavebot.Cavebot(PC(s), list(TROLL_TRASA), potwory=["Troll"], zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None,
                        spij=s.spij, zegar=s.zegar, loot=types.SimpleNamespace(zbierz=lambda z, g: "ok"), mapa=M,
                        okrazenia=999)
    b.zapis_znanych = False
    b.tele = telemetria.Telemetria(Path(tempfile.mkdtemp()), zegar=s.zegar, zapis=False)
    b.tele.nazwa_postaci = "Ja"
    b._patrol_wczytaj()
    b.patrol_pierwszy = False
    # licznik wywołań A*
    b._licznik_astar = 0
    stara = b.droga

    def droga(*a, **k):
        b._licznik_astar += 1
        return stara(*a, **k)
    b.droga = droga
    return s, b


def nasyc(b, s):
    """Mapa obecności z danymi: część komórek świeżo wyczyszczona, część dawno niewidziana, trochę mobów."""
    b._obecnosc_mapa()
    mo = b._obecnosc
    t = b._obecnosc_t()
    for i, m in enumerate(b.miejsca):
        mo.obserwuj(t - 1200 - 60 * i, (m["x"], m["y"], m["z"]),
                    [{"nazwa": "Troll", "x": m["x"] + 1, "y": m["y"], "z": m["z"]}] * (1 + i % 3), {"troll"})
        if i % 2:
            mo.obserwuj(t - 30, (m["x"], m["y"], m["z"]), [], {"troll"})         # wyczyszczone przed chwilą


def rek(tele, typ):
    return [r for r in tele.rek if r["typ"] == typ]




def dane(b, X=None, ile=3):
    """Mapa obecności z danymi: każde miejsce widziane dawno (t-3000 s) z trollami i potem puste (wyczyszczone dawno temu);
    miejsce X dodatkowo wyczyszczone przed chwilą (t-40 s)."""
    b._obecnosc_mapa()
    mo = b._obecnosc
    t = b._obecnosc_t()
    for m in b.miejsca:
        poz = (m["x"], m["y"], m["z"])
        tr = [{"nazwa": "Troll", "x": m["x"] + 1, "y": m["y"], "z": m["z"]}] * ile
        for i in range(10):
            mo.obserwuj(t - 3000 + 2 * i, poz, tr, {"troll"})
        for i in range(10):
            mo.obserwuj(t - 2970 + 2 * i, poz, [], {"troll"})
    if X is not None:
        m = next(m for m in b.miejsca if m["id"] == X)
        poz = (m["x"], m["y"], m["z"])
        tr = [{"nazwa": "Troll", "x": m["x"] + 1, "y": m["y"], "z": m["z"]}] * ile
        for i in range(10):
            mo.obserwuj(t - 80 + 2 * i, poz, tr, {"troll"})
        for i in range(10):
            mo.obserwuj(t - 40 + 2 * i, poz, [], {"troll"})
    return mo


def jeden(resp=1, cien=1, runda=1, X=None, seed=1, przed=None, bez_danych=False, pierwszy=False):
    """Jeden wybór patrolu z START; zwraca (wizyta, ostatni rekord patrol_cel, bot, scena)."""
    ustaw(resp=resp, cien=cien, runda=runda)
    random.seed(seed)
    s, b = zrob_c()
    if not bez_danych:
        dane(b, X)
    b.patrol_pierwszy = pierwszy
    if przed:
        przed(b)
    LOG.clear()
    p = b._patrol_wybierz(START)
    pcs = rek(b.tele, "patrol_cel")
    return p, (pcs[-1] if pcs else {}), b, s


# --- 1. pokrętło: domyślnie 0, w ZAKRESY i w przykładzie -----------------------------------------------------------------
import pokretla  # noqa: E402
przyklad = json.loads((Path(_R) / "na_zywo.przyklad.json").read_text())
sprawdz("1a PATROL_RESPAWN domyślnie 0 w cavebot.py, w ZAKRESY (0,1) i w na_zywo.przyklad.json",
        cavebot.PATROL_RESPAWN == 0 and pokretla.ZAKRESY.get("PATROL_RESPAWN") == (0, 1) and przyklad.get("PATROL_RESPAWN") == 0)
sprawdz("1b waliduj(PATROL_RESPAWN=1) przyjmuje, 2 odrzuca",
        pokretla.waliduj({"PATROL_RESPAWN": 1})[0] == {"PATROL_RESPAWN": 1} and "PATROL_RESPAWN" not in pokretla.waliduj({"PATROL_RESPAWN": 2})[0])

# --- 2. przy 0 nic się nie zmienia ---------------------------------------------------------------------------------------
def seria(resp, cien, n=12, runda=1, dane_b=True):
    ustaw(resp=resp, cien=cien, runda=runda)
    random.seed(1234)
    s, b = zrob_c()
    if cien and dane_b:
        dane(b, 4)
    ids, drogi = [], []
    for i in range(n):
        b.patrol_historia = ids[-3:]
        p = b._patrol_wybierz(START)
        ids.append(p["m"]["id"] if p else None)
        drogi.append(tuple(p["seg"]) if p else None)
    return ids, drogi, random.random(), s.zapytan, b._licznik_astar, b


i00, d00, l00, z00, a00, b00 = seria(0, 0)
i01, d01, l01, z01, a01, b01 = seria(0, 1)
sprawdz("2a RESPAWN=0: ten sam wybór, drogi, los, zapytania i A* z cieniem 0 i 1 (12 wyborów)",
        i00 == i01 and d00 == d01 and l00 == l01 and z00 == z01 and a00 == a01 and len(set(i00)) >= 3, f"{i00} vs {i01}")
mt = [r.get("metoda") for r in rek(b01.tele, "patrol_cel")]
sprawdz("2b RESPAWN=0: metoda każdego patrol_cel = waga (nigdy respawn), stare pola są", set(mt) == {"waga"}
        and all(k in rek(b01.tele, "patrol_cel")[0] for k in ("id", "x", "y", "powod", "droga", "waga", "poz", "cel_respawn", "wartosci", "zgodny")),
        sorted(rek(b01.tele, "patrol_cel")[0]))
sprawdz("2c RESPAWN=0: powód każdego wyboru = losowo, w logu nie ma wyboru respawnem",
        all(r["powod"].startswith("losowo") for r in rek(b01.tele, "patrol_cel")))

# --- 3. RESPAWN=1: świeżo wyczyszczone miejsce przegrywa z dawno niewidzianym ----------------------------------------------
p0, r0, b_, s_ = jeden(resp=1, X=None)
top = r0.get("cel_respawn")
sprawdz("3a RESPAWN=1, dane są: patrol idzie do cel_respawn (metoda respawn), powód respawn",
        p0 is not None and r0.get("metoda") == "respawn" and top is not None and p0["m"]["id"] == top
        and r0["powod"].startswith("respawn") and r0.get("zgodny") is True, r0)
w0 = r0["wartosci"]
sprawdz("3b cel ma najwyższą wartość ze wszystkich kandydatów", all(w0[top] >= v for v in w0.values()), w0)
pt, rt, _, _ = jeden(resp=1, X=top)
sprawdz("3c cel z 3a świeżo wyczyszczony (40 s): jego wartość spada >30%, patrol idzie gdzie indziej (metoda może się wstrzymać: niska pewność)",
        pt is not None and rt["wartosci"][top] < w0[top] * 0.7 and pt["m"]["id"] != top, (top, pt and pt["m"]["id"], rt))
drugi = sorted(w0, key=lambda i: -w0[i])[1]
p1, r1, b1_, s1_ = jeden(resp=1, X=drugi)
w1 = r1["wartosci"]
sprawdz("3c2 drugie miejsce świeżo wyczyszczone: jego wartość spada, a patrol dalej idzie do dawno niewidzianego najlepszego respawnem",
        p1 is not None and w1[drugi] < w0[drugi] * 0.7 and p1["m"]["id"] == top and r1["metoda"] == "respawn"
        and w1[top] == max(w1.values()), (top, drugi, p1 and p1["m"]["id"], r1))
sprawdz("3d log: cel wybrany respawnem z wartością i pewnością",
        any(l.startswith(f"Patrol: cel m{p1['m']['id']} ") and " respawn," in l and "wartość " in l and "pewność " in l for l in LOG),
        [l for l in LOG if "Patrol: cel" in l])
sprawdz("3e telemetria: metoda respawn + stare pola (waga None, droga, poz) + pola cienia",
        r1["metoda"] == "respawn" and r1["waga"] is None and r1["droga"] > 0 and r1["poz"] == list(START)
        and r1["cel_respawn"] == r1["id"] and "wartosci" in r1 and "d4_id" in r1, r1)
d4r = [r for r in rek(b1_.tele, "decyzja") if r["rodzaj"] == "D4"]
sprawdz("3e2 rekord decyzja D4 ma metodę wyboru (respawn), wybrana = cel_respawn", len(d4r) == 1 and d4r[0].get("metoda") == "respawn"
        and d4r[0].get("wybrana") == r1["id"] and d4r[0].get("cien") == r1["id"], d4r)
sprawdz("3f stash nie przeżywa wywołania (cień i metoda)", b1_._cien_wybor is None and b1_._wybor_meta == {})
sprawdz("3g RESPAWN=1 i RESPAWN_CIEN=0: mapa też się liczy i respawn wybiera tak samo",
        jeden(resp=1, cien=0, X=drugi)[0]["m"]["id"] == p1["m"]["id"])

# --- 4. brak danych = dzisiejszy wybór (ten sam los) ---------------------------------------------------------------------
def seria_bez_danych(resp):
    ustaw(resp=resp, cien=1)
    random.seed(99)
    s, b = zrob_c()
    ids = []
    for i in range(10):
        b.patrol_historia = ids[-3:]
        p = b._patrol_wybierz(START)
        ids.append(p["m"]["id"] if p else None)
    return ids, random.random(), b


ib1, lb1, bb1 = seria_bez_danych(1)
ib0, lb0, bb0 = seria_bez_danych(0)
sprawdz("4a brak danych w mapie: RESPAWN=1 wybiera i losuje dokładnie jak RESPAWN=0", ib1 == ib0 and lb1 == lb0 and len(set(ib1)) >= 3, f"{ib1} vs {ib0}")
sprawdz("4b brak danych: metoda waga, cel_respawn None, zgodny None",
        {r["metoda"] for r in rek(bb1.tele, "patrol_cel")} == {"waga"} and all(r["cel_respawn"] is None and r["zgodny"] is None for r in rek(bb1.tele, "patrol_cel")))
pP, rP, bP, sP = jeden(resp=1, pierwszy=True)
sprawdz("4c pierwszy wybór po starcie/wypadzie = najbliższe miejsce także przy RESPAWN=1", pP is not None and rP["metoda"] == "najblizsze" and rP["powod"].startswith("najbliższe"), rP)
# spot bez trolli (Edron): mapa nie powstaje, wybór jak dziś
ustaw(resp=1, cien=0)
random.seed(5)
sE, bE = zrob_c()
bE.potwory = ["szczur"]
pE = bE._patrol_wybierz(START)
sprawdz("4d spot bez trolli: mapa nie powstaje, wybór wagą", pE is not None and bE._obecnosc is False and rek(bE.tele, "patrol_cel")[-1]["metoda"] == "waga")

# --- 5. blokady miejsc są respektowane (wybór respawnem ich nie omija) ----------------------------------------------------
def m_po_id(b, i):
    return next(m for m in b.miejsca if m["id"] == i)


def czy_nie(przed, nazwa, runda=1, kontr=True):
    """Najlepsze miejsce `top` jest zablokowane na dany sposób: wybór (respawn) go nie wybiera; bez blokady - wybiera."""
    p, r, b, s = jeden(resp=1, runda=runda, przed=lambda bb: przed(bb, m_po_id(bb, top)))
    ok = p is not None and p["m"]["id"] != top
    sprawdz(nazwa, ok, (top, p and p["m"]["id"], r.get("metoda")))
    return p, r, b


def gracz(b, m):
    b.unikanie = types.SimpleNamespace(aktywne=True, gracze=[{"id": 99, "nazwa": "Obcy", "x": m["x"] + 2, "y": m["y"], "z": m["z"]}])


p5, r5, _ = czy_nie(gracz, "5a gracz przy najlepszym miejscu: miejsce odpada z kandydatów, wybór innego")
sprawdz("5a2 ...i wartości (jeśli metoda je policzyła) zawierają tylko kandydatów bez tego miejsca",
        top not in r5.get("wartosci", {}), r5.get("wartosci"))
czy_nie(lambda b, m: b.patrol_blok.__setitem__(m["id"], b.zegar() + 240.0), "5b patrol_blok (np. zmiana respa przy graczu, PATROL_GRACZ_ZMIEN): miejsce zablokowane")
czy_nie(lambda b, m: setattr(b, "_patrol_koord_zajete", lambda: {m["nazwa"]: {"x": m["x"], "y": m["y"], "z": m["z"], "promien": 0}}),
        "5c rezerwacja innej instancji (PATROL_KOORD): miejsce zajęte, wybór innego")
czy_nie(lambda b, m: b.patrol_gracze_pam.__setitem__("Obcy", (m["x"], m["y"], m["z"], b.zegar() - 10.0)),
        "5d pamięć gracza (PATROL_GRACZ_PAM): miejsce, w którym niedawno widziano obcego, nie jest celem respawnu")
czy_nie(lambda b, m: setattr(b, "patrol_historia", [m["id"]]), "5e miejsce odwiedzone w ostatnich PATROL_BYLO_WYKLUCZ wizytach odpada")
p5f, r5f, _ = czy_nie(lambda b, m: b.patrol_runda.add(m["id"]) if hasattr(b, "patrol_runda") else b.__dict__.setdefault("patrol_runda", set()).add(m["id"]),
                      "5f PATROL_RUNDA=1: miejsce już odwiedzone w tej rundzie odpada")
p5g, r5g, _, _ = jeden(resp=1, runda=0, przed=lambda bb: bb.__dict__.setdefault("patrol_runda", set()).add(top))
sprawdz("5g PATROL_RUNDA=0: runda nie ogranicza (to samo miejsce, jest wybrane)", p5g is not None and p5g["m"]["id"] == top, p5g and p5g["m"]["id"])
# brak drogi do najlepszego: następne najlepsze, a najlepsze dostaje blokadę (jak w dzisiejszym wyborze)
stara_droga = cavebot.Cavebot._patrol_droga
cavebot.Cavebot._patrol_droga = lambda self, poz, m, uzyte=None: None if m["id"] == top else stara_droga(self, poz, m, uzyte)
p5h, r5h, b5h, _ = jeden(resp=1)
cavebot.Cavebot._patrol_droga = stara_droga
sprawdz("5h brak drogi do najlepszego: patrol idzie do innego kandydata (respawn albo waga), najlepsze zablokowane na PATROL_BLOK_S",
        p5h is not None and p5h["m"]["id"] != top and r5h["metoda"] in ("respawn", "waga") and top in b5h.patrol_blok
        and top not in r5h.get("wartosci", {}), (p5h and p5h["m"]["id"], r5h.get("metoda")))

# --- 6. PATROL_RUNDA 1 i 0: jak się składa -------------------------------------------------------------------------------
def kolejnosc(runda, n=16):
    ustaw(resp=1, runda=runda)
    random.seed(3)
    s, b = zrob_c()
    dane(b, None)
    ids, met = [], []
    for _ in range(n):
        b.patrol_historia = b.patrol_historia
        p = b._patrol_wybierz(START)
        if p is None:
            ids.append(None)
            continue
        ids.append(p["m"]["id"])
        met.append(rek(b.tele, "patrol_cel")[-1]["metoda"])
        b._patrol_dotarl(p, START, s.t)
    return ids, met


k1, met1 = kolejnosc(1)
k0, met0 = kolejnosc(0)
sprawdz("6a RUNDA=1: respawn wybiera w obrębie rundy (kolejne N miejsc różne, każde raz na rundę)",
        None not in k1 and len(set(k1[:7])) == len(k1[:7]) and len(met1) == len(k1), k1)
sprawdz("6b RUNDA=0: bez rundy, ale ostatnie PATROL_BYLO_WYKLUCZ wizyt odpada (każde okno 4 różne)",
        None not in k0 and all(len(set(k0[i:i + 4])) == 4 for i in range(len(k0) - 3)), k0)
sprawdz("6c metoda respawn (przy danych) dominuje w obu trybach", met1.count("respawn") >= 3 and met0.count("respawn") >= 3, (met1, met0))

# --- 7. wyniki nie zależą od A* w tle: respawn dokłada tylko A* wybranej drogi (jak waga) ----------------------------------
_, _, bA1, _ = jeden(resp=1)
_, _, bA0, _ = jeden(resp=0)
sprawdz("7 respawn nie liczy A* dla kandydatów: tyle samo wywołań A* co waga (droga tylko do wybranego celu)",
        bA1._licznik_astar == bA0._licznik_astar, f"{bA1._licznik_astar} vs {bA0._licznik_astar}")

# --- 8. błąd mapy = brak zdania, wybór po staremu ------------------------------------------------------------------------
stare_w = obecnosc.MapaObecnosci.wybierz


def _rzuc(*a, **k):
    raise RuntimeError("zepsuta mapa")


obecnosc.MapaObecnosci.wybierz = _rzuc
try:
    pB, rB, bB, _ = jeden(resp=1)
finally:
    obecnosc.MapaObecnosci.wybierz = stare_w
sprawdz("8 błąd obecnosc.wybierz przy RESPAWN=1: wyjątku nie ma, patrol idzie wagą", pB is not None and rB["metoda"] == "waga" and "cel_respawn" not in rB, rB)

print(f"WYNIK: {sum(wyniki)} / {len(wyniki)}")
sys.exit(0 if all(wyniki) else 1)
