"""22.10 (Geblish, Rookgaard): "Wróć do miasta" / depo z jaskini szczurów rook_raty_z8 wybierało bazę rook_bugi_z10 (jej korytarz
z8 leży bliżej, ale za ścianą): "brak drogi", kroki w ścianę, ALARM. Wybór bazy ma być po osiągalności z pozycji
(Wyprawa._baza_osiagalna). Dane rzeczywiste: prawdziwa mapa, trasy/rook_raty_z8_petla.json, rook_*_dojscie_odwrocona.json."""
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
import wypad
import wyprawa as W

TRASY = Path(_R) / "trasy"
TMP = Path(tempfile.mkdtemp())
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test powrotu z Rook z8")
    sys.exit(0)

MAPA = _mapa.Mapa()
PETLA_Z8 = [tuple(int(v) for v in p) for p in json.loads((TRASY / "rook_raty_z8_petla.json").read_text())]
PETLA_BUGI = [tuple(int(v) for v in p) for p in json.loads((TRASY / "rook_bugi_z10_petla.json").read_text())]
CEL = (32061, 32180, 7)               # SPEC_powrot_rook_1020: cel powrotu (koniec odwróconych dojść), STOP
WEJSCIE_Z8 = (32046, 32222, 8)        # lądowanie z7 -> z8 = jedyne pole z8 odwróconego dojścia rook_raty_z8
POZYCJE = [(32102, 32231, 8), (32069, 32202, 8), (32095, 32210, 8), (32101, 32233, 8)]   # 13:05 i 12:13 z logów + dwie obok


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


def nowa(poz, punkty=PETLA_Z8, nr=[0]):
    nr[0] += 1
    cb = CBW(poz, punkty)
    logi = []
    w = W.Wyprawa(cb, OpsW(), konf=KonfW(), log=logi.append, plik_stanu=TMP / f"st{nr[0]}.json",
                  plik_sklepow=TMP / "sk.json", plik_npc=TMP / "npc.json", plik_stop=TMP / f"STOP{nr[0]}",
                  czas=lambda: 5_000_000.0)
    return w, cb, logi


def ciagla(pts, krok=5):
    for a, b in zip(pts, pts[1:]):
        if a[2] == b[2] and wypad.cheb(a, b) > krok:
            return f"skok {a}->{b}"
        if a[2] != b[2] and wypad.cheb(a, b) > 3:
            return f"skok pięter {a}->{b}"
    return None


def punkty_planu(w):
    return [tuple(p) for e in w.w["legs"][0] if e["typ"] == "IDZ" for p in e["punkty"]]


dane = {"powody": ["reczny"], "zapas": None, "blanki": None, "zloto": None, "cap": None, "hp": 100, "pochodnie": None,
        "depo": True, "reczny": True}
baza = W.punkty_bazy(nazwy=W.BAZY_PK)
nowa_metoda = W.Wyprawa._baza_osiagalna

# 1. odtworzenie błędu: najbliższy punkt "do" (stara reguła wybierz_baze) to rook_bugi_z10, a z niej nie ma drogi z jaskini z8
for poz in POZYCJE:
    sprawdz(f"1a {poz}: stara reguła (najbliższy punkt) wybiera rook_bugi_z10",
            W.wybierz_baze(baza, poz, W.PK_PLAN_ZASIEG) == "rook_bugi_z10")
W.Wyprawa._baza_osiagalna = lambda self, b, p, n: n         # stary kod
for poz in POZYCJE:
    w, cb, logi = nowa(poz)
    w._start_wyprawa("depo:reczny", dane, 0.0)
    sprawdz(f"1b {poz}: STARY KOD: baza rook_bugi_z10 i 'brak drogi' (idzie starą trasą)",
            w.w and w.w["baza"] == "rook_bugi_z10" and any("brak drogi z" in l for l in logi), f"{w.w and w.w['baza']} {logi[-2:]}")
W.Wyprawa._baza_osiagalna = nowa_metoda

# 2. nowy kod: baza rook_raty_z8, plan kompletny: od pozycji, po z8 do lądowania, schody w górę, z7 do celu, bez uwag planu
for poz in POZYCJE:
    w, cb, logi = nowa(poz)
    wynik = w._start_wyprawa("depo:reczny", dane, 0.0)
    pts = punkty_planu(w) if w.w else []
    sprawdz(f"2a {poz}: wyprawa startuje z bazą rook_raty_z8", wynik is True and w.w["baza"] == "rook_raty_z8", f"{wynik} {logi[-3:]}")
    sprawdz(f"2b {poz}: log wyboru bazy i drogi (bez 'brak drogi')",
            any("biorę rook_raty_z8" in l for l in logi) and any("Wyprawa: depo: droga z" in l for l in logi)
            and not any("brak drogi" in l for l in logi), f"{logi[-4:]}")
    sprawdz(f"2c {poz}: plan od pozycji do celu {CEL}, przez lądowanie {WEJSCIE_Z8}, ciągły",
            pts and pts[0] == poz and pts[-1] == CEL and WEJSCIE_Z8 in pts and ciagla(pts) is None, f"{pts[:1]} {pts[-1:]} {ciagla(pts)}")
    et = w.w["legs"][0] if w.w else []
    typy = [e["typ"] for e in et]
    sprawdz(f"2d {poz}: etapy IDZ(z8) -> LINA/schody w górę z7 -> IDZ(z7)",
            typy == ["IDZ", "LINA", "IDZ"] and et[1].get("schody") and tuple(et[1]["stoi"]) == WEJSCIE_Z8
            and et[0]["punkty"][-1] == list(WEJSCIE_Z8) or (typy == ["IDZ", "LINA", "IDZ"] and tuple(et[0]["punkty"][-1]) == WEJSCIE_Z8),
            f"{typy} {et[1:2]}")
    sprawdz(f"2e {poz}: sprawdz_plan bez uwag (brak etapów nieosiągalnych)",
            not wypad.sprawdz_plan(et, MAPA, rampy_ok=True), f"{wypad.sprawdz_plan(et, MAPA, rampy_ok=True)[:3]}")
    sprawdz(f"2f {poz}: pierwszy etap zostaje na z8, ostatni na z7",
            all(p[2] == 8 for p in et[0]["punkty"]) and all(p[2] == 7 for p in et[-1]["punkty"]))

# 3. z dowolnego punktu pętli z8 (co 60.)
bledy = []
for i in range(0, len(PETLA_Z8), 60):
    poz = PETLA_Z8[i]
    w, cb, logi = nowa(poz)
    wynik = w._start_wyprawa("depo:reczny", dane, 0.0)
    pts = punkty_planu(w) if w.w else []
    if not (wynik is True and w.w["baza"] == "rook_raty_z8" and pts and pts[-1] == CEL and ciagla(pts) is None
            and not wypad.sprawdz_plan(w.w["legs"][0], MAPA, rampy_ok=True)):
        bledy.append((i, poz, wynik, w.w and w.w["baza"], logi[-2:]))
sprawdz(f"3 pętla z8: plan do celu z {len(range(0, len(PETLA_Z8), 60))} punktów pętli, baza rook_raty_z8", not bledy, f"{bledy[:2]}")

# 4. nie psuje innych: z pętli rook_bugi_z10 nadal rook_bugi_z10 (przy [40] najbliższe rook_raty_z10 nie ma drogi: pomijane)
for i in (0, 20, 40):
    poz = PETLA_BUGI[i]
    w, cb, logi = nowa(poz, PETLA_BUGI)
    wynik = w._start_wyprawa("depo:reczny", dane, 0.0)
    sprawdz(f"4a z pętli rook_bugi_z10 [{i}] {poz}: baza bez zmian (rook_bugi_z10), plan do celu",
            wynik is True and w.w["baza"] == "rook_bugi_z10" and punkty_planu(w)[-1] == CEL, f"{wynik} {w.w and w.w['baza']} {logi[-3:]}")

# 5. pozycja bez drogi do żadnej bazy: zostaje najbliższa (stara trasa), bez wyjątku
w, cb, logi = nowa((32102, 32231, 8), [])
r = W.Wyprawa._baza_osiagalna(w, baza, (32102, 32231, 8), "rook_bugi_z10")
sprawdz("5a pętla pusta: z pozycji z8 pod miastem nadal znajduje drogę (rook_raty_z8)", r == "rook_raty_z8", r)
r = W.Wyprawa._baza_osiagalna(w, baza, (32500, 32500, 8), "rook_bugi_z10")
sprawdz("5b pozycja bez drogi do żadnej bazy: zostaje wskazana (stara trasa)", r == "rook_bugi_z10", r)
sprawdz("5c baza spoza PLANY_PK (troll) i None nietknięte",
        W.Wyprawa._baza_osiagalna(w, baza, (32102, 32231, 8), "troll") == "troll"
        and W.Wyprawa._baza_osiagalna(w, baza, (32102, 32231, 8), None) is None)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
