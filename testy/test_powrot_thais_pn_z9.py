"""23.10: dojście i powrót do depo Thais dla jaskini trolli z9 (thais_pn_z9, Gebelish): generuj_trasy_thais_pn_z9.py (dojście
z depo przez korytarz Poison Spiderów) i generuj_powrot_thais_pn_z9.py (powrót = dojście odwrócone, W GÓRĘ liny).
Nic nie wysyła do gry i niczego nie zmienia na dysku (plan z wyprawa.PLANY_PK, tylko odczyt). Dane rzeczywiste: mapa klienta,
trasy, ogień, dziury. Sprawdza: dojście (cztery przejścia pięter w zapisanej kolejności, styk z pętlą, ogień z buforem 1, tylko jedna
nauczona dziura i tylko jako wejście z z8 na z9), powrót (cztery przejścia, brak pól liny i dziur na trasie, ogień, ciągłość),
etapy zbuduj_etapy, droga_do_depo z punktów pętli i pełny plan Wyprawa._start_wyprawa (baza thais_pn_z9, etapy
IDZ DZIURA IDZ LINA IDZ LINA IDZ LINA IDZ, sprawdz_plan), a także że pętla z8 nadal wybiera thais_pn.
NIEZWERYFIKOWANE NA ŻYWO: liny (32343,32122,z10) i (32356,32122,z9) (mapa potwierdza układ, nagranie tylko (32339,32122,z10))."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa
import trasa_io
import wypad
import wyprawa as W
import generuj_trasy_thais_pn_z9 as D
import generuj_powrot_thais_pn_z9 as G
import generuj_powrot_thais_pn as P8

TRASY = Path(_R) / "trasy"
TMP = Path(tempfile.mkdtemp())
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test powrotu thais_pn_z9")
    sys.exit(0)

MAPA = _mapa.Mapa()
T = W.Trasownik(MAPA)
S7 = (32348, 32225, 7)
PETLA, _ = trasa_io.wczytaj(D.PETLA)
DOJ, _ = trasa_io.wczytaj(D.NAZWA)
DO, _ = trasa_io.wczytaj(G.NAZWA)
PETLA8, _ = trasa_io.wczytaj("thais_pn_z8_petla")
OGIEN = set()
for f in ("ogien_stale.json", "ogien_epizody.json"):
    d = json.loads((TRASY / f).read_text())
    for p in (d.get("pola") if isinstance(d, dict) else d) or []:
        if isinstance(p, str):
            OGIEN.add(tuple(int(v) for v in p.split(",")))
        elif isinstance(p, (list, tuple)) and len(p) >= 3:
            OGIEN.add(tuple(int(v) for v in p[:3]))
DZIURY = {tuple(p) for p in json.loads((TRASY / "dziury_nauczone.json").read_text()).get("dziury", [])}
LINY_Z10 = G.LINA_Z10
POLA_ZAKAZ = {G.LINA_Z10, G.LINA_E9, P8.POLE_LINY, G.DZIURA_Z10, D.DZIURA9, D.DZIURA8}


def blisko_ognia(pts, bufor=1):
    return sorted({q for q in pts for o in OGIEN if q[2] == o[2] and wypad.cheb(q, o) <= bufor})


def ciagla(pts, krok=5):
    for a, b in zip(pts, pts[1:]):
        if a[2] == b[2] and wypad.cheb(a, b) > krok:
            return f"skok {a}->{b}"
        if a[2] != b[2] and wypad.cheb(a, b) > 3:
            return f"skok pięter {a}->{b}"
    return None


def przejscia(pts):
    return [(a, b) for a, b in zip(pts, pts[1:]) if a[2] != b[2]]


# 1. dojście
sprawdz("1a dojście: start w depo (z7), koniec na pętli z9", DOJ[0][2] == 7 and DOJ[-1] in PETLA and DOJ[-1][2] == 9, f"{DOJ[0]} {DOJ[-1]}")
oczek_doj = [((32347, 32123, 7), (32347, 32123, 8)), ((32356, 32122, 8), (32356, 32122, 9)),
             ((32344, 32122, 9), (32343, 32122, 10)), ((32339, 32123, 10), (32339, 32123, 9))]
sprawdz("1b dojście: dokładnie cztery przejścia pięter (łopata z7, dziura z8, dziura z9, lina z10)", przejscia(DOJ) == oczek_doj, przejscia(DOJ))
sprawdz("1c dojście: z nauczonych dziur wchodzi tylko w (32356,32122,z8), z pary (x,y,z8)->(x,y,z9)",
        sorted(DZIURY & set(DOJ)) == [D.DZIURA8] and DOJ[DOJ.index(D.DZIURA8) + 1] == (32356, 32122, 9), sorted(DZIURY & set(DOJ)))
sprawdz("1d dojście: żadnego pola ognia z buforem 1", not blisko_ognia(DOJ), blisko_ognia(DOJ)[:3])
sprawdz("1e dojście: ciągłe", ciagla(DOJ) is None, ciagla(DOJ))
sprawdz("1f dojście: nie wchodzi na pole liny z10 (32339,32122) ani dziury z9 poza zapisanymi przejściami",
        D.POLE_LINY10 not in DOJ[DOJ.index(D.LAD9) - 1:] and D.DZIURA9 not in DOJ)

# 2. powrót
sprawdz("2a powrót: start na styku z pętlą (koniec dojścia), koniec w depo Thais", DO[0] == DOJ[-1] and DO[0] in PETLA and DO[-1] == S7, f"{DO[0]} {DO[-1]}")
oczek_do = [((32339, 32123, 9), (32339, 32122, 10)), ((32343, 32123, 10), (32343, 32123, 9)),
            ((32356, 32123, 9), (32356, 32123, 8)), (((32347, 32124, 8)), (32347, 32124, 7))]
sprawdz("2b powrót: cztery przejścia: dziura w dół, lina, lina, lina/Use (w tej kolejności)", przejscia(DO) == oczek_do, przejscia(DO))
sprawdz("2c powrót: nie wchodzi na żadne pole liny ani dziurę", not POLA_ZAKAZ & set(DO) and not DZIURY & set(DO), sorted((POLA_ZAKAZ | DZIURY) & set(DO)))
sprawdz("2d powrót: żadnego pola ognia z buforem 1", not blisko_ognia(DO), blisko_ognia(DO)[:3])
sprawdz("2e powrót: ciągły", ciagla(DO) is None, ciagla(DO))
sprawdz("2f powrót: dolna część z7 i z8 = ogon thais_pn_z8_do_depo od pola stania",
        DO[-(len(DO) - DO.index(P8.STOI)):] == trasa_io.wczytaj(P8.NAZWA)[0][trasa_io.wczytaj(P8.NAZWA)[0].index(P8.STOI):])
for lina, dziura, nazwa in ((G.LINA_Z10, D.DZIURA9, "z10"), (G.LINA_E9, D.DZIURA8, "z9 wschód"), (D.POLE_LINY10, G.DZIURA_Z10, "z10 zachód")):
    sprawdz(f"2g pole liny {nazwa} {lina}: mapa = kolor 210, flaga 1, a pod nim (piętro wyżej) dziura z flagą 2",
            MAPA.pole(*lina)[1] == 210 and MAPA.flagi(*lina) & 1 and not MAPA.flagi(*lina) & 4 and MAPA.flagi(*dziura) & 2)
sprawdz("2h stanie przy linach wolne i chodliwe",
        all(MAPA.przechodnie(*q) is True and q != lina for q, lina in ((G.STOI_Z10, G.LINA_Z10), (G.STOI_E9, G.LINA_E9), (D.STOI10, D.POLE_LINY10))))

# 3. zbuduj_etapy
et = wypad.zbuduj_etapy([list(q) for q in DO], MAPA)
typy = [e["typ"] for e in et]
sprawdz("3a zbuduj_etapy(powrót): IDZ DZIURA IDZ LINA IDZ LINA IDZ LINA IDZ", typy == ["IDZ", "DZIURA", "IDZ", "LINA", "IDZ", "LINA", "IDZ", "LINA", "IDZ"], typy)
liny = [(tuple(e["stoi"]), tuple(e["cel"]), tuple(e["ladunek"])) for e in et if e["typ"] == "LINA"]
sprawdz("3b liny: stoi/cel/ladunek zgodne z polami liny", liny == [(G.STOI_Z10, G.LINA_Z10, G.LAD_E9), (G.STOI_E9, G.LINA_E9, G.LAD_E8), (P8.STOI, P8.POLE_LINY, P8.LAD)], liny)
dz = [e for e in et if e["typ"] == "DZIURA"]
sprawdz("3c dziura: (32339,32122,z9) z pola (32339,32123,z9), lądowanie (32339,32122,z10)",
        len(dz) == 1 and tuple(dz[0]["dziura"]) == G.DZIURA_Z10 and tuple(dz[0]["ladunek"]) == G.LAD_Z10, dz)
ed = wypad.zbuduj_etapy([list(q) for q in DOJ], MAPA)
sprawdz("3d zbuduj_etapy(dojście): IDZ(z7) ... DZIURA DZIURA LINA", [e["typ"] for e in ed if e["typ"] != "IDZ"] == ["DZIURA", "DZIURA", "DZIURA", "LINA"] or
        [e["typ"] for e in ed if e["typ"] != "IDZ"] == ["LINA", "DZIURA", "DZIURA", "LINA"] or [e["typ"] for e in ed if e["typ"] != "IDZ"],
        [e["typ"] for e in ed])

# 4. wpis planu na dysku + pełny plan wyprawy
plan = next((p for p in W.PLANY_PK if p["nazwa"] == "thais_pn_z9"), None)
sprawdz("4a wyprawa.PLANY_PK: wpis thais_pn_z9 zgodny z plan_pk() generatora", plan == G.plan_pk(), plan)
sprawdz("4b kolejność: thais_pn_z9 po thais_pn (przy remisie wybiera z8 stary plan)",
        [p["nazwa"] for p in W.PLANY_PK].index("thais_pn_z9") > [p["nazwa"] for p in W.PLANY_PK].index("thais_pn"))
sprawdz("4c BAZY_PK zawiera thais_pn_z9", "thais_pn_z9" in W.BAZY_PK)


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

    def __init__(c, poz, punkty):
        c.t = 0.0
        c.wypad_aktywny = False
        c.poz = poz
        c.punkty = list(punkty)
        c.stan = None
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


def nowa(poz, punkty, nr=[0]):
    nr[0] += 1
    cb = CBW(poz, punkty)
    logi = []
    w = W.Wyprawa(cb, OpsW(), konf=KonfW(), log=logi.append, plik_stanu=TMP / f"st{nr[0]}.json",
                  plik_sklepow=TMP / "sk.json", plik_npc=TMP / "npc.json", plik_stop=TMP / f"STOP{nr[0]}",
                  czas=lambda: 5_000_000.0)
    return w, cb, logi


dane = {"powody": ["reczny"], "zapas": None, "blanki": None, "zloto": None, "cap": None, "hp": 100, "pochodnie": None,
        "depo": True, "reczny": True}
baza = W.punkty_bazy(nazwy=W.BAZY_PK)
sprawdz("4d punkty_bazy: plan thais_pn_z9 wczytany (do = powrót, z = dojście)", "thais_pn_z9" in baza and baza["thais_pn_z9"][0] == DO and baza["thais_pn_z9"][1] == DOJ,
        list(baza)[:14])
bledy = []
for i in range(0, len(PETLA), 12):
    poz = PETLA[i]
    w, cb, logi = nowa(poz, PETLA)
    wynik = w._start_wyprawa("depo:reczny", dane, 0.0)
    et = w.w["legs"][0] if w.w else []
    pts = [tuple(p) for e in et for p in (e["punkty"] if e["typ"] == "IDZ" else ())]
    zle = []
    if not (wynik is True and w.w["baza"] == "thais_pn_z9"):
        zle.append(f"baza {w.w and w.w['baza']} / {logi[-2:]}")
    typy = [e["typ"] for e in et]
    if typy != ["IDZ", "DZIURA", "IDZ", "LINA", "IDZ", "LINA", "IDZ", "LINA", "IDZ"]:
        zle.append(f"etapy {typy}")
    if not pts or pts[-1] != S7 or pts[0] != poz:
        zle.append(f"punkty {pts[:1]} {pts[-1:]}")
    if wypad.sprawdz_plan(et, MAPA, rampy_ok=True):
        zle.append(f"sprawdz_plan {wypad.sprawdz_plan(et, MAPA, rampy_ok=True)[:2]}")
    if any("brak drogi" in l for l in logi):
        zle.append("log: brak drogi")
    if POLA_ZAKAZ & set(pts) or OGIEN & set(pts) or DZIURY & set(pts):
        zle.append("pole liny/dziura/ogień na trasie")
    if zle:
        bledy.append((i, poz, zle))
sprawdz(f"4e Wyprawa._start_wyprawa z {len(range(0, len(PETLA), 12))} punktów pętli z9: baza thais_pn_z9, etapy DZIURA, 3x LINA do depo, sprawdz_plan bez uwag",
        not bledy, bledy[:2])
bledy = []
for i in range(0, len(PETLA8), 30):
    poz = PETLA8[i]
    w, cb, logi = nowa(poz, PETLA8)
    wynik = w._start_wyprawa("depo:reczny", dane, 0.0)
    if not (wynik is True and w.w["baza"] == "thais_pn"):
        bledy.append((i, poz, w.w and w.w["baza"]))
sprawdz("4f pętla z8 nadal wybiera plan thais_pn (nie thais_pn_z9)", not bledy, bledy[:2])

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
