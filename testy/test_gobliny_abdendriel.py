"""25.10: gobliny Ab'Dendriel na z6 (mapa abdendriel_gobliny): generuj_trasy_abdendriel_gobliny.py -> trasy/abdendriel_gobliny_{petla,dojscie,do_depo}.
Nic nie wysyla do gry i niczego nie zmienia na dysku. Sprawdza: pliki == wynik generatora, ciaglosc i dokladnie dwa przejscia pieter w kazdej z dwoch tras
(dojscie z8->z7->z6, powrot z6->z7->z8), pola schodow i dziur poza trasami, zero scian / ognia / trucizny / nauczonych dziur, petla w jednym piatrze i na
skladowej z6, wpis mapy.json, etapy wypad.zbuduj_etapy (IDZ LINA IDZ LINA IDZ) i sprawdz_plan, oraz PROPONOWANY wpis PLANY_PK (dolozony tylko w pamieci testu):
baza wybierana z petli z6 i niewybierana z punktow innych planow.
NIEZWERYFIKOWANE NA ZYWO: obie pary schodow, polozenie depo (32679,31687,z8), przejezdnosc z7."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa
import trasa_io
import wypad
import wyprawa as W
import generuj_trasy_abdendriel_gobliny as G

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test gobliny abdendriel")
    sys.exit(0)

MAPA = _mapa.Mapa()
PETLA = [tuple(p) for p in trasa_io.wczytaj(G.NAZWA + "_petla")[0]]
DOJ, META_D = trasa_io.wczytaj(G.NAZWA_DOJSCIA)
POW, META_P = trasa_io.wczytaj(G.NAZWA_POWROTU)
DOJ, POW = [tuple(p) for p in DOJ], [tuple(p) for p in POW]
m, kand, zle, comp, st, order, nodes, pelna, (pts, meta), (pw, mp) = G.zbuduj()

# 1. pliki == generator
sprawdz("1a petla == generator", PETLA == [(x, y, 6) for x, y in pelna], (len(PETLA), len(pelna)))
sprawdz("1b dojscie == generator (punkty i meta)", DOJ == [tuple(p) for p in pts] and META_D == meta, (len(DOJ), len(pts)))
sprawdz("1c powrot == generator (punkty i meta)", POW == [tuple(p) for p in pw] and META_P == mp, (len(POW), len(pw)))
sprawdz("1d petla: jedno pietro (z6), caly w skladowej, start = lad. dojscia, 7 przystankow / 21 goblinow",
        {p[2] for p in PETLA} == {6} and all((p[0], p[1]) in comp for p in PETLA) and PETLA[0] == G.START6 and len(st) == 7 and sum(t["n"] for t in st) == 21,
        (PETLA[0], len(st)))
sprawdz("1e petla zamyka sie (ostatni punkt sasiaduje ze startem)", max(abs(PETLA[-1][0] - PETLA[0][0]), abs(PETLA[-1][1] - PETLA[0][1])) <= 1, PETLA[-1])

# 2. przejscia pieter
pr_d = [(a, b) for a, b in zip(DOJ, DOJ[1:]) if a[2] != b[2]]
pr_p = [(a, b) for a, b in zip(POW, POW[1:]) if a[2] != b[2]]
sprawdz("2a dojscie: dokladnie dwa przejscia z8->z7 (nagranie) i z7->z6 (schody (32622,31790,z7))", pr_d == [(G.STOI8, G.LAD7), (G.STOI7, G.START6)], pr_d)
sprawdz("2b powrot: dokladnie dwa przejscia z6->z7 i z7->z8", pr_p == [(G.START6, G.LAD7_Z6), (G.LAD7, G.LAD8)], pr_p)
sprawdz("2c dojscie konczy sie startem petli, powrot zaczyna sie nim; oba maja depo na drugim koncu", DOJ[-1] == G.START6 == POW[0] and DOJ[0] == POW[-1] == G.PW.DEPO_STOI, (DOJ[0], DOJ[-1]))
zakaz = set(G.PRZEJSCIA)
sprawdz("2d pola schodow poza wszystkimi trasami", not (zakaz & (set(DOJ) | set(POW) | set(PETLA))), sorted(zakaz & (set(DOJ) | set(POW) | set(PETLA))))
sprawdz("2e schody (32622,31790) maja flage 2 i kolor 210 na z6 i z7; obok po stronie chodliwej pola lad. i stania sa chodliwe",
        all(MAPA.flagi(*s) & _mapa.BEZ_DROGI and MAPA.pole(*s)[1] == 210 for s in (G.SCHODY6, G.SCHODY7))
        and not MAPA.flagi(*G.START6) & (_mapa.SCIANA | _mapa.BEZ_DROGI) and not MAPA.flagi(*G.STOI7) & (_mapa.SCIANA | _mapa.BEZ_DROGI), "")
sprawdz("2f schody z8/z7 (32654,31674): flaga 2 na obu pietrach", all(MAPA.flagi(*s) & _mapa.BEZ_DROGI for s in (G.SCHODY8, G.SCHODY7_DOL)), "")

# 3. brak scian / ognia / trucizny / dziur
skoki = [(a, b) for t in (DOJ, POW) for a, b in zip(t, t[1:]) if a[2] == b[2] and max(abs(a[0] - b[0]), abs(a[1] - b[1])) > 4]
sprawdz("3a ciaglosc: zaden skok > 4 pol na jednym pietrze (dluzsze tylko w nagraniu z8)", not skoki, skoki[:2])
skoki7 = [(a, b) for t in (DOJ, POW) for a, b in zip(t, t[1:]) if a[2] in (6, 7) and a[2] == b[2] and max(abs(a[0] - b[0]), abs(a[1] - b[1])) > 1]
sprawdz("3b z7 i z6: krok zawsze o 1 pole (A* po mapie, bez skokow)", not skoki7, skoki7[:2])
sciany = [p for t in (DOJ, POW, PETLA) for p in t if not MAPA.flagi(*p) & _mapa.WIDZIANE or MAPA.flagi(*p) & (_mapa.SCIANA | _mapa.BEZ_DROGI)]
sprawdz("3c zero scian, niewidzianych i flagi 2 na punktach tras", not sciany, sciany[:3])
ogien = G._ogn.ogien_pola()
sprawdz("3d zero punktow w znanym ogniu (z buforem) i w strefie zakazanej generatora", not [p for t in (DOJ, POW, PETLA) for p in t if p in ogien or p in zle], "")
sprawdz("3e zero nauczonych dziur na trasach", not [p for t in (DOJ, POW, PETLA) for p in t if p in G.AB.dziury_nauczone()], "")
sprawdz("3f kontrole generatora przechodza dla plikow", G.kontrole(MAPA, DOJ, zle, set()) is None and G.kontrole(MAPA, POW, zle, set()) is None, "")

# 4. wpis mapy.json
MJ = json.loads((Path(_R) / "mapy.json").read_text())
w = MJ.get("abdendriel_gobliny", {})
sprawdz("4a mapy.json: trasa/dojscie/potwory/prog_hp/dojscie_z_dowolnego_pietra", w.get("trasa") == G.NAZWA + "_petla" and w.get("dojscie") == G.NAZWA_DOJSCIA
        and w.get("potwory") == "Goblin" and w.get("prog_hp") == 30 and w.get("dojscie_z_dowolnego_pietra") is True, w)
sprawdz("4b nazwa potwora 'Goblin' jak w innych mapach goblinow", MJ["gobliny_edron"]["potwory"] == w.get("potwory"), "")

# 5. etapy
et = wypad.zbuduj_etapy(DOJ, MAPA)
sprawdz("5a dojscie: etapy IDZ LINA IDZ LINA IDZ", [e["typ"] for e in et] == ["IDZ", "LINA", "IDZ", "LINA", "IDZ"], [e["typ"] for e in et])
sprawdz("5a2 dojscie, schody z8 (32654,31674): cel = pole schodow, schody=True, stoi (32654,31675,z8) pod nimi, ladunek (32654,31673,z7)",
        et[1]["cel"] == G.SCHODY8 and et[1].get("schody") is True and tuple(et[1]["stoi"]) == G.STOI8 and tuple(et[1]["ladunek"]) == G.LAD7, et[1])
# 25.10 luka usunieta (wypad._schody_poziome): schody z7 (32622,31790) wychodza na zachod (lad. (x-1, y)), druga LINA ma cel na schodach, nie na scianie (32621,31789)
sprawdz("5a3 dojscie, schody z7 (32622,31790): cel = pole schodow, schody=True, stoi (32623,31790,z7) przed nimi, ladunek (32621,31790,z6) (nie sciana (32621,31789))",
        tuple(et[3]["cel"]) == (32622, 31790, 7) and et[3].get("schody") is True and tuple(et[3]["stoi"]) == (32623, 31790, 7) and tuple(et[3]["ladunek"]) == (32621, 31790, 6), et[3])
sprawdz("5b sprawdz_plan dojscia bez uwag", not wypad.sprawdz_plan(et, MAPA, {}, rampy_ok=True), wypad.sprawdz_plan(et, MAPA, {}, rampy_ok=True)[:2])
ep = wypad.zbuduj_etapy(POW, MAPA)
sprawdz("5c powrot (w dol): etapy IDZ DZIURA IDZ DZIURA IDZ, stoi/ladunek = (START6 -> lad. z7 (32623,31790)), (LAD7 -> LAD8)", [e["typ"] for e in ep] == ["IDZ", "DZIURA", "IDZ", "DZIURA", "IDZ"]
        and [(tuple(e["stoi"]), tuple(e["ladunek"])) for e in ep if e["typ"] == "DZIURA"] == [(G.START6, G.LAD7_Z6), (G.LAD7, G.LAD8)], ep)
sprawdz("5d sprawdz_plan powrotu bez uwag", not wypad.sprawdz_plan(ep, MAPA, {}, rampy_ok=True), wypad.sprawdz_plan(ep, MAPA, {}, rampy_ok=True)[:2])

# 6. PROPONOWANY wpis PLANY_PK (tylko w pamieci testu; wyprawa.py nie jest edytowany)
PLAN = G.plan_pk()
sprawdz("6a plan_pk: pliki istnieja, bez npc/prefiksu/drzwi", trasa_io.sciezka(PLAN["do"]).is_file() and trasa_io.sciezka(PLAN["z"]).is_file() and not PLAN["npc"] and not PLAN["prefix"] and "drzwi" not in PLAN, PLAN)
_STARE = W.PLANY_PK
W.PLANY_PK = tuple(_STARE) + (() if any(q["nazwa"] == PLAN["nazwa"] for q in _STARE) else (PLAN,))      # gdy wpis juz jest w wyprawa.py, nie dublujemy
try:
    baza = W.punkty_bazy(plany=W.wypad.PLANY + W.PLANY_PK, nazwy=tuple(p["nazwa"] for p in W.PLANY_PK))
    sprawdz("6b punkty_bazy wczytuje plan (do == powrot, z == dojscie)", G.NAZWA_DOJSCIA and PLAN["nazwa"] in baza and [tuple(p) for p in baza[PLAN["nazwa"]][0]] == POW, list(baza)[-3:])
    zle6 = [p for p in PETLA[::7] if W.wybierz_baze(baza, p, W.zasieg_planu(PLAN["nazwa"])) != PLAN["nazwa"]]
    sprawdz("6c z kazdego punktu petli z6 (zasieg planu = domyslny 200) wybierana jest baza abdendriel_gobliny_z6", not zle6, zle6[:3])
    inne = [(n, tuple(d[0][i])) for n, d in baza.items() if n != PLAN["nazwa"] and not n.startswith("abdendriel") for i in range(0, len(d[0]), 15)]
    zmien = [(n, p) for n, p in inne if W.wybierz_baze(baza, p, W.PK_PLAN_ZASIEG) == PLAN["nazwa"]]
    sprawdz("6d punkty 'do' planow Edron/Kazordoon/Thais/Rook... nie wybieraja planu goblinow", not zmien, zmien[:3])
    # 6e 25.10: pelny start ucieczki PK (Wyprawa._start_wyprawa pk="ucieczka") z punktow petli, takze z 43 punktow dalszych niz PK_PLAN_ZASIEG=80 od startu petli
    # (tam wybierz_baze daje None, remis depo w _baza_dojscie wygrywa abdendriel_trolle_z10, a _baza_osiagalna przelacza na plan goblinow, bo trolli nie ma drogi z z6)
    import tempfile
    import types
    TMP = Path(tempfile.mkdtemp())
    _pb = W.punkty_bazy
    W.punkty_bazy = lambda katalog=W.TRASY, plany=None, nazwy=W.BAZY: _pb(katalog, W.wypad.PLANY + W.PLANY_PK, nazwy)
    _bpk = W.BAZY_PK
    W.BAZY_PK = W.BAZY + tuple(q["nazwa"] for q in W.PLANY_PK)

    class KonfW:
        WYPRAWA_AKTYWNA = 1
        WYPRAWA_MAX_CZAS_S = 1800
        WYPRAWA_MAX_KROKOW = 6000
        WYPRAWA_STOP_PRZY_UTKNIECIU = 1
        WYPRAWA_CO_MIN = 20
        WYPRAWA_PO_DEPO_S = 900
        WYPRAWA_DEPO_POWROT = 0
        WYPRAWA_TYLKO_DEPO = 1

    class CBW:
        mapa = MAPA

        def __init__(c, poz):
            c.t, c.wypad_aktywny, c.poz, c.punkty, c.stan = 0.0, False, poz, list(PETLA), None
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

    class OpsW:
        def wiadomosci(o):
            return []

    dane = {"powody": ["pk"], "zapas": None, "blanki": None, "zloto": None, "cap": None, "hp": 60, "pochodnie": None, "depo": True}
    daleko = [i for i, q in enumerate(PETLA) if wypad.cheb(q, PETLA[0]) > W.PK_PLAN_ZASIEG]
    probki = sorted(set(list(range(0, len(PETLA), 40)) + daleko[::6]))
    zle6e, ile_daleko = [], 0
    try:
        for i in probki:
            poz = PETLA[i]
            w = W.Wyprawa(CBW(poz), OpsW(), konf=KonfW(), log=lambda *_: None, plik_stanu=TMP / f"s{i}.json", plik_sklepow=TMP / "sk.json",
                          plik_npc=TMP / "npc.json", plik_stop=TMP / f"STOP{i}", czas=lambda: 5_000_000.0)
            wynik = w._start_wyprawa("depo:pk_ucieczka", dane, 0.0, baza_nazwa=None, pk="ucieczka")
            et = w.w["legs"][0] if w.w else []
            ile_daleko += i in daleko
            if not (wynik is True and w.w["baza"] == PLAN["nazwa"] and [e["typ"] for e in et] == ["IDZ", "DZIURA", "IDZ", "DZIURA", "IDZ"]
                    and not wypad.sprawdz_plan(et, MAPA, {}, rampy_ok=True)):
                zle6e.append((i, poz, w.w and w.w["baza"], [e["typ"] for e in et]))
    finally:
        W.punkty_bazy, W.BAZY_PK = _pb, _bpk
    sprawdz(f"6e ucieczka PK z {len(probki)} punktow petli (w tym {ile_daleko} dalszych niz {W.PK_PLAN_ZASIEG} od startu): baza goblinow, IDZ DZIURA IDZ DZIURA IDZ, sprawdz_plan bez uwag",
            not zle6e and ile_daleko > 0, zle6e[:3])
finally:
    W.PLANY_PK = _STARE

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
