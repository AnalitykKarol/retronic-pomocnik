#!/usr/bin/env python3
"""15.10 (SPEC_patrol_respawn_1015, krok 2): tryb cienia patrolu według respawnu. Bot liczy mapę obecności (obecnosc.py)
z tego, co ma w ticku, i dopisuje do rekordu patrol_cel pola cel_respawn / wartosci / zgodny oraz rekord "decyzja" D4;
idzie do celu wybranego dzisiejszą metodą. Sprawdzamy: pola cienia, D4, ten sam wybór bota z PATROL_RESPAWN_CIEN 0 i 1
(też ten sam los, te same zapytania do gry i te same wywołania A*), błąd w obecnosc nie przerywa ticka, zapis stanu.
Wyłącznie atrapy, bez gry."""
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
    """Pokrętła cienia na czas jednego przebiegu."""
    cavebot.PATROL_RESPAWN_CIEN = kw.get("cien", 1)


# =====================================================================================================
# A. lekka scena (jak test_decyzje_log): tick z trollami w widoku, zabicia, błędy modułu
# =====================================================================================================
class Swiat:
    def __init__(s, poz=(100, 100, 7)):
        s.t = 0.0
        s.poz = list(poz)
        s.stwory = []
        s.klawisze = []
        s.ataki = []
        s.zapytan = 0

    def zegar(s):
        return s.t

    def spij(s, d):
        s.t += d

    def zapytaj(s, z):
        s.t += 0.05
        s.zapytan += 1
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}


class P:
    nazwa = "Ja"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        return tuple(p.s.poz)

    def klawisz(p, k):
        p.s.klawisze.append(k)

    def krok(p, k):
        d = bot.KIERUNKI[k]
        p.s.t += 0.2
        p.s.poz[0] += d[0]
        p.s.poz[1] += d[1]
        return tuple(p.s.poz)


def troll(i, x, y=100, hp=100, z=7, nazwa="Troll"):
    return {"id": i, "nazwa": nazwa, "gracz": False, "x": x, "y": y, "z": z, "hp": hp}


MIEJSCA_A = [{"id": i, "x": 96 + 6 * i, "y": 98 + 3 * i, "z": 7, "udzial": 0.1, "zrodlo": None, "waga": None,
              "mobow": None, "nazwa": f"a{i}"} for i in range(4)]


def scena(stwory):
    s = Swiat()
    s.stwory = stwory

    def atak(m, g):
        s.ataki.append(m["id"])
        for x in s.stwory:
            if x["id"] == m["id"]:
                x["hp"] -= 50
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], potwory=["Troll", "Rat"], zapytaj=s.zapytaj, atak=atak,
                        alarm=lambda w: None, spij=s.spij, zegar=s.zegar, okrazenia=1,
                        loot=types.SimpleNamespace(zbierz=lambda zw, g: "ok"))
    tele = telemetria.Telemetria(Path(tempfile.mkdtemp()), zegar=s.zegar, zapis=False)
    tele.nazwa_postaci = "Ja"
    b.tele = tele
    b.miejsca = [dict(m) for m in MIEJSCA_A]       # obszar mapy obecności (bbox miejsc + margines)
    return s, b, tele


def przebieg_a(ticki=25, przed=None):
    random.seed(7)
    s, b, tele = scena([troll(5, 103), troll(6, 106, hp=40)])
    if przed:
        przed(b)
    for _ in range(ticki):
        b.tick()
        s.stwory[:] = [m for m in s.stwory if m["hp"] > 0]
    return s, b, tele


ustaw(cien=1)
s1, b1, t1 = przebieg_a()
mo = b1._obecnosc
sprawdz("A1 mapa obecności tworzona leniwie w ticku z miejsc patrolu", isinstance(mo, obecnosc.MapaObecnosci),
        type(mo).__name__)
komorka = mo.k.get(mo.klucz(100, 100, 7)) if mo else None
sprawdz("A2 komórka pod graczem była w widoku", komorka is not None and komorka.t_widok is not None)
sprawdz("A3 komórka z trollem ma t_mob i gęstość > domyślnej",
        mo and mo.k.get(mo.klucz(103, 100, 7)) is not None and mo.k[mo.klucz(103, 100, 7)].t_mob is not None
        and mo.gestosc(mo.klucz(103, 100, 7)) > mo.gest_domyslna)
zab = sum(c.zabicia for c in mo.k.values()) if mo else -1
sprawdz("A4 zabicie celu trafia do mapy (oba trolle zabite)", zab == 2 and len(s1.ataki) >= 2, f"zabicia={zab} ataki={s1.ataki}")

# szczur (spoza CEL_NAZWY) nie wchodzi do mapy: ani obserwacja, ani zabicie
random.seed(7)
sr, br, tr = scena([troll(5, 103, nazwa="Rat")])
for _ in range(15):
    br.tick()
    sr.stwory[:] = [m for m in sr.stwory if m["hp"] > 0]
mr = br._obecnosc
sprawdz("A5 inna nazwa niż cel (szczur) nie jest liczona w mapie",
        mr and all(c.zabicia == 0 and c.t_mob is None for c in mr.k.values()) and len(sr.ataki) >= 1,
        f"ataki={sr.ataki}")

# CIEN=0 i RESPAWN=0: żadnej mapy
ustaw(cien=0, resp=0)
s0, b0, t0 = przebieg_a()
sprawdz("A6 oba pokrętła 0: mapa nie powstaje, bot robi to samo",
        b0._obecnosc is None and s0.ataki == s1.ataki and s0.klawisze == s1.klawisze and s0.poz == s1.poz
        and abs(s0.t - s1.t) < 1e-9 and s0.zapytan == s1.zapytan,
        f"ataki {s0.ataki} vs {s1.ataki}; poz {s0.poz} vs {s1.poz}; t {s0.t} vs {s1.t}; zapytan {s0.zapytan} vs {s1.zapytan}")
# błąd w obecnosc.obserwuj / zabicie nie przerywa ticka i nie zmienia ruchu
ustaw(cien=1)
stare_obs, stare_zab = obecnosc.MapaObecnosci.obserwuj, obecnosc.MapaObecnosci.zabicie


def _rzuc(*a, **k):
    raise RuntimeError("zepsuta mapa")


obecnosc.MapaObecnosci.obserwuj = _rzuc
obecnosc.MapaObecnosci.zabicie = _rzuc
LOG.clear()
try:
    sB, bB, tB = przebieg_a()
    wyj = None
except Exception as e:  # noqa: BLE001
    wyj, sB = e, s0
obecnosc.MapaObecnosci.obserwuj, obecnosc.MapaObecnosci.zabicie = stare_obs, stare_zab
sprawdz("A8 błąd obserwuj/zabicie: tick idzie dalej, ruch ten sam co bez cienia",
        wyj is None and sB.ataki == s0.ataki and sB.klawisze == s0.klawisze and sB.poz == s0.poz
        and abs(sB.t - s0.t) < 1e-9, f"wyjątek={wyj!r}")
sprawdz("A9 błąd trafia tylko do logu, a nie co tick (kilka wpisów)",
        0 < sum("obecność: błąd" in l for l in LOG) <= 6, f"wpisów={sum('obecność: błąd' in l for l in LOG)}")

# błąd przy tworzeniu mapy (dla_miejsc): obecność wyłączona, bot idzie dalej
stare_dm = obecnosc.MapaObecnosci.__dict__["dla_miejsc"]
obecnosc.MapaObecnosci.dla_miejsc = classmethod(lambda cls, *a, **k: _rzuc())
LOG.clear()
try:
    sC, bC, tC = przebieg_a()
    wyj = None
except Exception as e:  # noqa: BLE001
    wyj, sC = e, s0
obecnosc.MapaObecnosci.dla_miejsc = stare_dm
sprawdz("A10 błąd tworzenia mapy: _obecnosc=False, tick idzie dalej, ruch ten sam",
        wyj is None and bC._obecnosc is False and sC.ataki == s0.ataki and sC.poz == s0.poz,
        f"wyjątek={wyj!r} obecnosc={bC._obecnosc!r}")

# koszt obserwacji w ticku
ustaw(cien=1)
sK, bK, tK = scena([])
bK.miejsca = [dict(m) for m in MIEJSCA_A]
lista = [{"id": 1, "nazwa": "Ja", "gracz": True, "x": 100, "y": 100, "z": 7, "hp": 100}] + \
        [troll(10 + i, 99 + i, 98 + i % 5) for i in range(8)]
bK._obecnosc_obserwuj(lista, (100, 100, 7))           # rozgrzewka (tworzy mapę)
t0_ = time.perf_counter()
N = 2000
for i in range(N):
    sK.t += 0.5
    bK._obecnosc_obserwuj(lista, (100 + i % 3, 100, 7))
koszt_ms = (time.perf_counter() - t0_) / N * 1000
sprawdz("A11 koszt obserwacji w ticku < 1 ms (8 trolli w widoku)", koszt_ms < 1.0, f"{koszt_ms:.3f} ms")

# =====================================================================================================
# B. zapis i odczyt stanu (co OBECNOSC_ZAPIS_S, na koniec, uszkodzony plik, inny obszar)
# =====================================================================================================
katalog = Path(tempfile.mkdtemp())
plik = katalog / "obecnosc_stan.json"
stary_plik = cavebot.OBECNOSC_STAN_PLIK
cavebot.OBECNOSC_STAN_PLIK = plik
ustaw(cien=1)
try:
    sS, bS, tS = scena([])
    bS._obecnosc_obserwuj(lista, (100, 100, 7))
    sprawdz("B1 pierwsza obserwacja: stanu jeszcze nie zapisujemy (zapis dopiero po OBECNOSC_ZAPIS_S)", not plik.exists())
    sS.t += cavebot.OBECNOSC_ZAPIS_S + 1
    bS._obecnosc_obserwuj(lista, (100, 100, 7))
    sprawdz("B2 po OBECNOSC_ZAPIS_S stan zapisany do pliku", plik.exists())
    m1 = plik.stat().st_mtime_ns
    sS.t += 5
    bS._obecnosc_obserwuj(lista, (100, 100, 7))
    sprawdz("B3 kolejna obserwacja po 5 s nie zapisuje ponownie", plik.stat().st_mtime_ns == m1)
    n0 = len(bS._obecnosc.k)
    bS._obecnosc_zapisz(wymus=True)
    sprawdz("B4 zapis wymuszony (koniec pracy) działa mimo odstępu", plik.stat().st_mtime_ns != m1)
    # nowy proces: stan wczytany (świeży: z t_*)
    sS2, bS2, tS2 = scena([])
    bS2._obecnosc_obserwuj([{"id": 1, "nazwa": "Ja", "gracz": True, "x": 100, "y": 100, "z": 7, "hp": 100}],
                           (100, 100, 7))
    mo2 = bS2._obecnosc
    sprawdz("B5 nowy bot wczytuje stan (komórki z poprzedniej sesji)",
            isinstance(mo2, obecnosc.MapaObecnosci) and len(mo2.k) >= n0
            and mo2.k[mo2.klucz(103, 100, 7)].czas_widoku > 0, f"n0={n0} n={len(mo2.k) if mo2 else None}")
    # uszkodzony plik: mapa od zera, bez wyjątku
    plik.write_text("{ to nie jest json")
    sS3, bS3, tS3 = scena([])
    bS3._obecnosc_obserwuj(lista, (100, 100, 7))
    sprawdz("B6 uszkodzony plik stanu: mapa od zera, bez wyjątku",
            isinstance(bS3._obecnosc, obecnosc.MapaObecnosci))
    # stan z innego obszaru (inne miejsca): od zera
    bS._obecnosc_zapisz(wymus=True)
    sS4, bS4, tS4 = scena([])
    bS4.miejsca = [{"id": 1, "x": 5000, "y": 5000, "z": 7, "udzial": 0.1, "zrodlo": None, "waga": None,
                    "mobow": None, "nazwa": "inny"}]
    bS4._obecnosc_obserwuj(lista, (5000, 5000, 7))
    sprawdz("B7 stan z innego obszaru (bbox) nie jest używany",
            isinstance(bS4._obecnosc, obecnosc.MapaObecnosci) and bS4._obecnosc.bbox[0] > 4000)
    # błąd zapisu (katalog = plik): tylko log, bez wyjątku
    cavebot.OBECNOSC_STAN_PLIK = plik / "podkatalog" / "x.json"      # rodzic jest plikiem
    LOG.clear()
    try:
        bS._obecnosc_zapisz(wymus=True)
        wyj = None
    except Exception as e:  # noqa: BLE001
        wyj = e
    sprawdz("B8 błąd zapisu stanu: wyjątku nie ma, wpis w logu", wyj is None and any("zapisie stanu" in l for l in LOG),
            f"{wyj!r} {LOG[-1:]}")
finally:
    cavebot.OBECNOSC_STAN_PLIK = stary_plik

# =====================================================================================================
# C. wybór celu patrolu na prawdziwej mapie jaskini (miejsca_troll.json): pola cienia, D4, ten sam wybór bota
# =====================================================================================================
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


ustaw(cien=1)
random.seed(11)
sC1, bC1 = zrob_c()
nasyc(bC1, sC1)
pC1 = bC1._patrol_wybierz(START)
cel_id = pC1["m"]["id"] if pC1 else None
pcs = rek(bC1.tele, "patrol_cel")
rc = pcs[-1] if pcs else {}
sprawdz("C1 patrol wybrał cel i zapisał patrol_cel", pC1 is not None and len(pcs) == 1 and rc.get("id") == cel_id, rc)
sprawdz("C2 patrol_cel ma pola cienia: cel_respawn, wartosci, zgodny",
        all(k in rc for k in ("cel_respawn", "wartosci", "zgodny")), sorted(rc))
ids_kand = {m["id"] for m in bC1.miejsca if m["id"] != cel_id or True}
sprawdz("C3 wartosci: słownik id -> liczba (zaokrąglona) dla kandydatów",
        isinstance(rc.get("wartosci"), dict) and len(rc["wartosci"]) >= 3
        and all(isinstance(v, (int, float)) and abs(v - round(v, 4)) < 1e-12 for v in rc["wartosci"].values())
        and set(int(k) if isinstance(k, str) else k for k in rc["wartosci"]) <= ids_kand, rc.get("wartosci"))
cr = rc.get("cel_respawn")
sprawdz("C4 cel_respawn: id kandydata albo None (za mała pewność); zgodny = bool, a None gdy cel_respawn None",
        (cr is None or cr in ids_kand) and (rc.get("zgodny") is None if cr is None else isinstance(rc.get("zgodny"), bool))
        and rc["zgodny"] == (None if cr is None else cr == cel_id), f"cel_respawn={cr} cel={cel_id} zgodny={rc.get('zgodny')}")
dec = [r for r in rek(bC1.tele, "decyzja") if r["rodzaj"] == "D4"]
d4 = dec[0] if dec else {}
sprawdz("C5 jest rekord decyzja D4", len(dec) == 1, [r["rodzaj"] for r in rek(bC1.tele, "decyzja")])
sprawdz("C6 D4: wybrana = regula = wybór bota, cien = cel_respawn, poz bota",
        d4.get("wybrana") == cel_id and d4.get("regula") == cel_id and d4.get("cien") == cr
        and d4.get("poz") == list(START), d4 and {k: d4.get(k) for k in ("wybrana", "regula", "cien", "poz")})
op = {o["id"]: o for o in d4.get("opcje", [])}
cechy = ("id", "odl", "dojscie", "droga", "oczekiwane", "od_wyczyszczenia_s", "gracz_przy", "wartosc")
sprawdz("C7 D4: opcje to kandydaci z cechami (dojście, droga, oczekiwane moby, czas od wyczyszczenia, gracz przy)",
        len(op) >= 3 and cel_id in op and all(all(k in o for k in cechy) for o in op.values()),
        [k for o in op.values() for k in cechy if k not in o])
sprawdz("C8 D4: wartości w opcjach zgodne z wartosci z patrol_cel",
        all(abs(op[i]["wartosc"] - rc["wartosci"][i if i in rc["wartosci"] else str(i)]) < 1e-9 for i in op))
sprawdz("C9 patrol_cel łączy się z D4 przez d4_id", rc.get("d4_id") == d4.get("id") and d4.get("id") is not None,
        f"{rc.get('d4_id')} vs {d4.get('id')}")
sprawdz("C10 rekord zapisuje się jako JSON (klucze, liczby)", bool(json.dumps(rc)) and bool(json.dumps(d4)))
sprawdz("C11 stash cienia nie przeżywa wywołania _patrol_wybierz", bC1._cien_wybor is None)

# gracz przy miejscu: cecha gracz_przy i niższa wartość
sCg, bCg = zrob_c()
nasyc(bCg, sCg)
m_cel = next(m for m in bCg.miejsca if m["id"] == 3)
bCg.unikanie = types.SimpleNamespace(aktywne=True, gracze=[{"id": 99, "nazwa": "Obcy", "x": m_cel["x"], "y": m_cel["y"],
                                                              "z": m_cel["z"]}])
random.seed(2)
bCg._patrol_wybierz(START)
d4g = [r for r in rek(bCg.tele, "decyzja") if r["rodzaj"] == "D4"]
opg = {o["id"]: o for o in d4g[0]["opcje"]} if d4g else {}
sprawdz("C12 obcy gracz przy miejscu 3 (samo 3 odpada z kandydatów): gracz_przy=True tylko przy bliskich, nie przy dalekich",
        3 not in opg and any(o["gracz_przy"] for o in opg.values()) and any(not o["gracz_przy"] for o in opg.values()),
        {i: o["gracz_przy"] for i, o in opg.items()})

# =====================================================================================================
# D. wybór bota się nie zmienia: ten sam cel i droga z cieniem 0 i 1, ten sam los, te same zapytania i A*
# =====================================================================================================
def seria(cien, pierwszy=False, n=12):
    """n kolejnych wyborów z tej samej pozycji z ustalonym losem; zwraca (id-y, drogi, los po, zapytania, A*)."""
    ustaw(cien=cien)
    random.seed(1234)
    s, b = zrob_c()
    nasyc(b, s) if cien else None
    ids, drogi = [], []
    for i in range(n):
        b.patrol_pierwszy = pierwszy and i == 0
        b.patrol_historia = ids[-3:]
        p = b._patrol_wybierz(START)
        ids.append(p["m"]["id"] if p else None)
        drogi.append(tuple(p["seg"]) if p else None)
    return ids, drogi, random.random(), s.zapytan, b._licznik_astar, b


i1, d1, los1, z1, a1, b_c1 = seria(1)
i0, d0, los0, z0, a0, b_c0 = seria(0)
sprawdz("D1 ten sam cel patrolu z PATROL_RESPAWN_CIEN 0 i 1 (12 wyborów)", i1 == i0 and len(set(i1)) >= 3, f"{i1} vs {i0}")
sprawdz("D2 te same drogi (pola) do wybranych celów", d1 == d0)
sprawdz("D3 ten sam stan generatora losowego po serii (cień nie losuje)", los1 == los0, f"{los1} vs {los0}")
sprawdz("D4 te same zapytania do gry (cień niczego nie pyta)", z1 == z0, f"{z1} vs {z0}")
sprawdz("D5 te same wywołania A* (cień ich nie dokłada)", a1 == a0 and a0 > 0, f"{a1} vs {a0}")
ip1, dp1, lp1, _, _, _ = seria(1, pierwszy=True)
ip0, dp0, lp0, _, _, _ = seria(0, pierwszy=True)
sprawdz("D7 pierwszy wybór (najbliższe miejsce) też bez zmian", ip1 == ip0 and dp1 == dp0 and lp1 == lp0, f"{ip1[:3]} vs {ip0[:3]}")
sprawdz("D8 cień 0: żadnych pól cienia ani D4, mapa nie powstała",
        all("cel_respawn" not in r for r in rek(b_c0.tele, "patrol_cel")) and rek(b_c0.tele, "patrol_cel")
        and not [r for r in rek(b_c0.tele, "decyzja") if r["rodzaj"] == "D4"] and b_c0._obecnosc is None)
sprawdz("D9 cień 1: każdy patrol_cel ma pola cienia i D4 (12 wyborów)",
        len(rek(b_c1.tele, "patrol_cel")) == 12 and all("cel_respawn" in r and "zgodny" in r for r in rek(b_c1.tele, "patrol_cel"))
        and len([r for r in rek(b_c1.tele, "decyzja") if r["rodzaj"] == "D4"]) == 12)
# DECYZJE_LOG=0: pola cienia w patrol_cel są, D4 nie
cavebot.DECYZJE_LOG = 0
ustaw(cien=1)
random.seed(5)
sL, bL = zrob_c()
nasyc(bL, sL)
bL._patrol_wybierz(START)
rL = rek(bL.tele, "patrol_cel")[-1]
sprawdz("D10 DECYZJE_LOG=0: patrol_cel ma pola cienia, brak rekordu D4 (d4_id None)",
        "cel_respawn" in rL and rL.get("d4_id") is None and not rek(bL.tele, "decyzja"), rL)
cavebot.DECYZJE_LOG = 1

# błąd w obecnosc.wybierz: patrol_cel bez pól cienia, wybór bota ten sam
ustaw(cien=1)
stare_w = obecnosc.MapaObecnosci.wybierz
obecnosc.MapaObecnosci.wybierz = _rzuc
LOG.clear()
try:
    ie, de, losE, ze, ae, bE = seria(1)
    wyj = None
except Exception as e:  # noqa: BLE001
    wyj, ie, de, losE, bE = e, None, None, None, None
obecnosc.MapaObecnosci.wybierz = stare_w
sprawdz("D11 błąd obecnosc.wybierz: wyjątku nie ma, wybór bota ten sam, patrol_cel bez pól cienia",
        wyj is None and ie == i0 and de == d0 and losE == los0
        and all("cel_respawn" not in r for r in rek(bE.tele, "patrol_cel")) and len(rek(bE.tele, "patrol_cel")) == 12,
        f"{wyj!r}")
sprawdz("D12 błąd cienia zalogowany (nie co wybór)", 0 < sum("obecność: błąd" in l for l in LOG) <= 6)

# błąd telemetrii przy D4 (zepsuty zapis decyzji) nie psuje wyboru
class TeleBlad(telemetria.Telemetria):
    def zdarzenie(self, typ, **d):
        if typ == "decyzja":
            raise RuntimeError("zepsuty zapis")
        return super().zdarzenie(typ, **d)


ustaw(cien=1)
random.seed(1234)
sT, bT = zrob_c()
bT.tele = TeleBlad(Path(tempfile.mkdtemp()), zegar=sT.zegar, zapis=False)
bT.tele.nazwa_postaci = "Ja"
nasyc(bT, sT)
idT = []
for i in range(12):
    bT.patrol_historia = idT[-3:]
    p = bT._patrol_wybierz(START)
    idT.append(p["m"]["id"] if p else None)
sprawdz("D13 zepsuty zapis D4: wybór bota ten sam, patrol_cel zapisany z polami cienia",
        idT == i0 and len([r for r in rek(bT.tele, "patrol_cel") if "cel_respawn" in r]) == 12, f"{idT} vs {i0}")

# inne wywołania _patrol_nowy (np. po walce, tuż obok) nie mają wyniku cienia: pola nie powstają, błąd się nie rzuca
ustaw(cien=1)
sN, bN = zrob_c()
nasyc(bN, sN)
mN = bN.miejsca[2]
pN = bN._patrol_nowy(START, mN, "test", waga=1.0)
rN = rek(bN.tele, "patrol_cel")[-1]
sprawdz("D14 _patrol_nowy poza _patrol_wybierz: patrol_cel bez pól cienia", pN is not None and "cel_respawn" not in rN, rN)

# =====================================================================================================
# E. przybliżenie drogi bez A*: linia prosta, inne piętro = okolica miejsca
# =====================================================================================================
sE, bE2 = zrob_c()
mz = {m["id"]: m for m in bE2.miejsca}
dr, dojs, rodzaj = bE2._patrol_cien_przyblizenie((100, 100, 8), {"id": 9, "x": 104, "y": 103, "z": 8}, 7)
sprawdz("E1 to samo piętro: linia prosta od sąsiada startu do celu, kończy w celu",
        rodzaj == "linia" and dr[-1] == (104, 103, 8) and len(dr) == 4 and all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1
        for a, b in zip([(100, 100, 8)] + dr, dr)), dr)
sprawdz("E2 czas dojścia = odległość kandydata x KROK_S", abs(dojs - 7 * obecnosc.KROK_S) < 1e-9, dojs)
dr, dojs, rodzaj = bE2._patrol_cien_przyblizenie((100, 100, 8), {"id": 9, "x": 104, "y": 103, "z": 9}, 7 + 14)
sprawdz("E3 inne piętro: bez drogi (tylko okolica miejsca), czas = pola x KROK_S + SCHODY_S",
        rodzaj == "cel" and dr == [] and abs(dojs - (7 * obecnosc.KROK_S + obecnosc.SCHODY_S)) < 1e-9, (rodzaj, dr, dojs))
dr, dojs, rodzaj = bE2._patrol_cien_przyblizenie((104, 103, 8), {"id": 9, "x": 104, "y": 103, "z": 8}, 0)
sprawdz("E4 stoimy na miejscu: pusta droga, czas 0", dr == [] and dojs == 0.0)

print(f"WYNIK: {sum(wyniki)} / {len(wyniki)}")
sys.exit(0 if all(wyniki) else 1)
