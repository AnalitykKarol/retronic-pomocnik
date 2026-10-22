"""22.10: powrót do depo Thais z jaskini trolli thais_pn_z8 (generuj_powrot_thais_pn.py). Plan thais_pn jest WYŁĄCZONY (21.10, zgon
kutangena w dziurze (32356,32122,z8)); ten test symuluje JEGO WŁĄCZENIE w pamięci (podmiana wyprawa.PLANY_PK/BAZY_PK), nic nie
zmienia na dysku i niczego nie wysyła do gry. Dane rzeczywiste: mapa klienta, thais_pn_z8_petla/dojscie/do_depo, ogień, dziury.
Sprawdza: trasę (z7 = odwrócone dojście, jedno przejście STOI -> LAD, bez pola liny i dziury na z9, bufor 1 od ognia, strefa
poison spiderów >= 6 pól), droga_do_depo z punktów pętli i z całej składowej z8, pełny plan Wyprawa._start_wyprawa (etapy, sprawdz_plan)."""
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
import pietra
import spot_lib
import trasa_io
import wypad
import wyprawa as W
import generuj_powrot_thais_pn as G

TRASY = Path(_R) / "trasy"
TMP = Path(tempfile.mkdtemp())
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test powrotu thais_pn")
    sys.exit(0)

MAPA = _mapa.Mapa()
T = W.Trasownik(MAPA)
PLAN = G.plan_pk()
S7 = (32348, 32225, 7)
PETLA, _ = trasa_io.wczytaj("thais_pn_z8_petla")
DOJSCIE, _ = trasa_io.wczytaj("thais_pn_z8_dojscie")
DO, _ = trasa_io.wczytaj(G.NAZWA)
JADY = [(s["x"], s["y"]) for s in spot_lib.spawny(8, ("poison spider",))]
STREFA = spot_lib.strefa_zakazana(spot_lib.spawny(8, ("poison spider",)), 8, 6)
OGIEN = set()
for f in ("ogien_stale.json", "ogien_epizody.json"):
    d = json.loads((TRASY / f).read_text())
    for p in (d.get("pola") if isinstance(d, dict) else d) or []:
        if isinstance(p, str):
            OGIEN.add(tuple(int(v) for v in p.split(",")))
        elif isinstance(p, (list, tuple)) and len(p) >= 3:
            OGIEN.add(tuple(int(v) for v in p[:3]))
DZIURY = {tuple(p) for p in json.loads((TRASY / "dziury_nauczone.json").read_text()).get("dziury", [])}


def blisko_ognia(pts, bufor=1):
    return sorted({q for q in pts for o in OGIEN if q[2] == o[2] and wypad.cheb(q, o) <= bufor})


def ciagla(pts, krok=5):
    for a, b in zip(pts, pts[1:]):
        if a[2] == b[2] and wypad.cheb(a, b) > krok:
            return f"skok {a}->{b}"
        if a[2] != b[2] and wypad.cheb(a, b) > 3:
            return f"skok pięter {a}->{b}"
    return None


def najblizej_jadu(pts):
    return min((wypad.cheb(q, j) for q in pts if q[2] == 8 for j in JADY), default=99)


# 1. plik trasy
sprawdz("1a plik: start na styku z pętlą (koniec dojścia z8), koniec w depo Thais",
        DO[0] == DOJSCIE[-1] and DO[0] in PETLA and DO[-1] == S7, f"{DO[0]} {DO[-1]}")
zm = [(a, b) for a, b in zip(DO, DO[1:]) if a[2] != b[2]]
sprawdz(f"1b plik: jedno przejście pięter {G.STOI} -> {G.LAD}", zm == [(G.STOI, G.LAD)], zm)
sprawdz("1c plik: nie wchodzi na pole liny, dziurę na z9 ani żadną znaną dziurę", G.POLE_LINY not in DO and G.DZIURA_Z9 not in DO
        and not DZIURY & set(DO), sorted(DZIURY & set(DO))[:3])
sprawdz("1d plik: z7 = dojście odwrócone (od lądowania do depo)", [q for q in DO if q[2] == 7] == list(reversed(DOJSCIE[:DOJSCIE.index(G.POLE_LINY) - 1])))
sprawdz("1e plik: z8 = końcówka dojścia odwrócona", [q for q in DO if q[2] == 8] == list(reversed(DOJSCIE[DOJSCIE.index(G.POLE_LINY) + 1:])))
sprawdz("1f plik: żadnego pola ognia z buforem 1", not blisko_ognia(DO), blisko_ognia(DO)[:3])
sprawdz("1g plik: poza strefą poison spiderów i >= 6 pól od ich spawnu", not STREFA & set(DO) and najblizej_jadu(DO) >= 6, najblizej_jadu(DO))
sprawdz("1h plik: trasa ciągła", ciagla(DO) is None, ciagla(DO))
sprawdz("1i pole liny: mapa = zmiana piętra (kolor 210), nad nim flaga 2 (dziura z7), lądowanie z7 chodliwe",
        MAPA.pole(*G.POLE_LINY)[1] == 210 and MAPA.flagi(G.POLE_LINY[0], G.POLE_LINY[1], 7) & 2 and MAPA.przechodnie(*G.LAD) is True)
kand = pietra.kandydaci(MAPA, G.STOI, G.LAD)
sprawdz("1j pietra.kandydaci(STOI, LAD): pewne pole liny = (32347,32123,8), lądowanie (32347,32124,7)",
        kand and tuple(kand[0]["pole"]) == G.POLE_LINY and kand[0]["pewne"] and tuple(kand[0]["lad"]) == G.LAD, kand[:1])
sprawdz("1k pole stania: wolne, chodliwe, sąsiad pola liny, nie pole liny", wypad.cheb(G.STOI, G.POLE_LINY) == 1 and G.STOI != G.POLE_LINY
        and MAPA.przechodnie(*G.STOI) is True and not MAPA.flagi(*G.STOI) & 2)

# 2. droga_do_depo z punktów pętli i z całej składowej z8 (poza pętlą)
zal = lambda a, cele: T.zalew(a, cele, limit=W.DEPO_ZALEW_LIMIT)       # noqa: E731
sk = sorted(spot_lib.skladowa(MAPA, (32356, 32131, 8), [p for p in DZIURY if p[2] == 8]))
pozycje = [("pętla", q) for q in PETLA[::6]] + [("składowa", (p[0], p[1], 8)) for p in sk[::17] if (p[0], p[1], 8) not in STREFA]
bledy = []
for rodzaj, poz in pozycje:
    r = W.droga_do_depo(poz, PETLA, DO, zal, MAPA, wyjscia=PLAN["wyjscia"])
    if r is None:
        bledy.append((rodzaj, poz, "brak drogi"))
        continue
    pts = [tuple(q) for q in r[0]]
    z8 = [q for q in pts if q[2] == 8]
    zmp = [(a, b) for a, b in zip(pts, pts[1:]) if a[2] != b[2]]
    usterki = []
    if pts[-1] != S7:
        usterki.append(f"koniec {pts[-1]}")
    if zmp != [(G.STOI, G.LAD)]:
        usterki.append(f"przejścia {zmp}")
    if G.POLE_LINY in pts[:pts.index(G.LAD)] and poz != G.POLE_LINY:
        usterki.append("wchodzi na pole liny")
    if G.DZIURA_Z9 in pts or DZIURY & set(pts):
        usterki.append("dziura")
    if STREFA & set(z8):
        usterki.append(f"strefa {sorted(STREFA & set(z8))[:2]}")
    if OGIEN & set(pts):
        usterki.append(f"ogień {sorted(OGIEN & set(pts))[:2]}")
    if ciagla(pts):
        usterki.append(ciagla(pts))
    if usterki:
        bledy.append((rodzaj, poz, usterki))
sprawdz(f"2 droga_do_depo z {len(pozycje)} pozycji (pętla co 6., składowa z8 co 17. pole): depo, jedno przejście STOI->LAD, "
        f"bez pola liny, dziur, strefy, ognia", not bledy, bledy[:3])

# 3. pełny plan wyprawy przy WŁĄCZONYM planie (podmiana w pamięci)
_stare = (W.PLANY_PK, W.BAZY_PK, W.punkty_bazy.__defaults__)
W.PLANY_PK = W.PLANY_PK + (PLAN,)
W.BAZY_PK = W.BAZY_PK + ("thais_pn",)
W.punkty_bazy.__defaults__ = (W.punkty_bazy.__defaults__[0], wypad.PLANY + W.PLANY_PK, W.punkty_bazy.__defaults__[2])


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


def nowa(poz, nr=[0]):
    nr[0] += 1
    cb = CBW(poz, PETLA)
    logi = []
    w = W.Wyprawa(cb, OpsW(), konf=KonfW(), log=logi.append, plik_stanu=TMP / f"st{nr[0]}.json",
                  plik_sklepow=TMP / "sk.json", plik_npc=TMP / "npc.json", plik_stop=TMP / f"STOP{nr[0]}",
                  czas=lambda: 5_000_000.0)
    return w, cb, logi


dane = {"powody": ["reczny"], "zapas": None, "blanki": None, "zloto": None, "cap": None, "hp": 100, "pochodnie": None,
        "depo": True, "reczny": True}
try:
    baza = W.punkty_bazy(nazwy=W.BAZY_PK)
    sprawdz("3a punkty_bazy: plan thais_pn wczytany (do = trasa powrotu, z = dojście)", "thais_pn" in baza and baza["thais_pn"][0] == DO
            and baza["thais_pn"][1] == DOJSCIE, list(baza)[:12])
    bledy = []
    for i in range(0, len(PETLA), 30):
        poz = PETLA[i]
        w, cb, logi = nowa(poz)
        wynik = w._start_wyprawa("depo:reczny", dane, 0.0)
        pts = [tuple(p) for e in (w.w["legs"][0] if w.w else []) for p in (e["punkty"] if e["typ"] == "IDZ" else ())]
        et = w.w["legs"][0] if w.w else []
        typy = [e["typ"] for e in et]
        lina = next((e for e in et if e["typ"] == "LINA"), {})
        zle = []
        if not (wynik is True and w.w["baza"] == "thais_pn"):
            zle.append(f"baza {w.w and w.w['baza']} / {logi[-2:]}")
        if typy != ["IDZ", "LINA", "IDZ"]:
            zle.append(f"etapy {typy}")
        elif not (tuple(lina["stoi"]) == G.STOI and tuple(lina["cel"]) == G.POLE_LINY and tuple(lina["ladunek"]) == G.LAD):
            zle.append(f"LINA {lina}")
        if not pts or pts[-1] != S7 or pts[0] != poz:
            zle.append(f"punkty {pts[:1]} {pts[-1:]}")
        if wypad.sprawdz_plan(et, MAPA, rampy_ok=True):
            zle.append(f"sprawdz_plan {wypad.sprawdz_plan(et, MAPA, rampy_ok=True)[:2]}")
        if any("brak drogi" in l for l in logi):
            zle.append("log: brak drogi")
        if STREFA & set(pts) or G.DZIURA_Z9 in pts or OGIEN & set(pts):
            zle.append("strefa/dziura/ogień")
        if zle:
            bledy.append((i, poz, zle))
    sprawdz(f"3b Wyprawa._start_wyprawa z {len(range(0, len(PETLA), 30))} punktów pętli: baza thais_pn, etapy IDZ(z8) -> LINA({G.STOI} -> "
            f"{G.POLE_LINY}) -> IDZ(z7) do depo, sprawdz_plan bez uwag", not bledy, bledy[:2])
    # 4. pozycja na z7 przy dojściu NIE wybiera tego planu do wyjścia liną (z7 nie ma wyjścia; plan z7 jak dotąd)
    w, cb, logi = nowa((32347, 32140, 7))
    sprawdz("4 pozycja z7 przy dojściu: nie zgłasza błędu wyboru planu (wyjątek niedopuszczalny)",
            w._start_wyprawa("depo:reczny", dane, 0.0) in (True, False))
finally:
    W.PLANY_PK, W.BAZY_PK, W.punkty_bazy.__defaults__ = _stare

# 5. plan jest domyślnie WYŁĄCZONY (przełącznik = obecność w wyprawa.PLANY_PK); informacja, nie warunek
print("INFO plan thais_pn w wyprawa.PLANY_PK na dysku:", any(p["nazwa"] == "thais_pn" for p in W.PLANY_PK))
try:
    nauczone = json.loads((Path(_R) / "dane_tibia" / "ruch" / "przejscia_nauczone.json").read_text())
    print("INFO przejscia_nauczone 32347,32123,8>7:", nauczone.get("32347,32123,8>7", "BRAK (przejście w górę jeszcze nie przeszedł żaden bot)"))
except (OSError, ValueError):
    pass

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
