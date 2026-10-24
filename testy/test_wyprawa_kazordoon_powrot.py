"""23.10: powrót do depo Thais ze spotów trolle_kazordoon_z8 / trolle_kazordoon_z9 (wpisy w wyprawa.PLANY_PK).
Przyczyna: spoty leżą ~305 pól od depo Thais, a DEPO_DOJSCIE_ZASIEG = 200 odrzucał drogę ("brak drogi" -> stara trasa od rozwidlenia,
ALARM/STOP); plany mają teraz klucz "zasieg" (wyprawa.zasieg_planu). Dane rzeczywiste: pętle, trasy *_do_depo, prawdziwa mapa.
Nic nie trafia do gry."""
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
    print("brak pliku mapy, pomijam test powrotu z Kazordoonu")
    sys.exit(0)


def wczytaj(nazwa):
    return [tuple(int(v) for v in p) for p in json.loads((TRASY / nazwa).read_text())]


MAPA = _mapa.Mapa()
T = W.Trasownik(MAPA)
DEPO = (32348, 32225, 7)                 # depo Thais
LINA = (32663, 31962, 8)                 # pole liny (dziura z8 -> z7), stoimy OBOK
STOI = (32663, 31961, 8)
LAD7 = (32663, 31963, 7)
DZIURA_PN = (32356, 32122, 8)            # zakaz: dziura w jaskini Thais północ (CLAUDE.md 21.10)
SCHODY9 = ((32648, 32003, 9), (32648, 32004, 8))
OGIEN = set()
for f in ("ogien_stale.json", "ogien_epizody.json"):
    d = json.loads((TRASY / f).read_text())
    for p in (d.get("pola") if isinstance(d, dict) else d) or []:
        if isinstance(p, (list, tuple)) and len(p) >= 3:
            OGIEN.add(tuple(int(v) for v in p[:3]))
try:
    NAUCZONE = {tuple(p[:3]) for p in json.loads((Path(_R) / "trasy" / "dziury_nauczone.json").read_text())}
except (OSError, ValueError, TypeError):
    NAUCZONE = set()

SPOTY = {"z8": "trolle_kazordoon_z8", "z9": "trolle_kazordoon_z9"}
PETLA = {n: wczytaj(f"{s}_petla.json") for n, s in SPOTY.items()}


def zalew(a, cele):
    return T.zalew(a, cele, limit=W.DEPO_ZALEW_LIMIT)


def ciagla(pts):
    for a, b in zip(pts, pts[1:]):
        if a[2] == b[2] and wypad.cheb(a, b) > 5:
            return f"skok {a}->{b}"
        if a[2] != b[2] and wypad.cheb(a, b) > 3:
            return f"skok pięter {a}->{b}"
    return None


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


def punkty_planu(w):
    return [tuple(p) for e in w.w["legs"][0] if e["typ"] == "IDZ" for p in e["punkty"]]


# --- 1. wpisy planu
for n, s in SPOTY.items():
    plan = next((p for p in W.PLANY_PK if p["nazwa"] == s), None)
    sprawdz(f"{s}: wpis w PLANY_PK", plan is not None)
    if plan is None:
        continue
    do, z = wczytaj(plan["do"]), wczytaj(plan["z"])
    sprawdz(f"{s}: do = {s}_do_depo.json, z = {s}_dojscie.json", plan["do"] == f"{s}_do_depo.json" and plan["z"] == f"{s}_dojscie.json")
    sprawdz(f"{s}: 'do' kończy w depo Thais, 'z' zaczyna w depo Thais", do[-1] == DEPO and z[0] == DEPO, (do[-1], z[0]))
    sprawdz(f"{s}: w BAZY_PK i w punkty_bazy", s in W.BAZY_PK and s in W.punkty_bazy(nazwy=W.BAZY_PK))
    sprawdz(f"{s}: zasięg planu >= odległość spotu od depo",
            W.zasieg_planu(s) >= max(wypad.cheb(q, DEPO) for q in PETLA[n]), (W.zasieg_planu(s), max(wypad.cheb(q, DEPO) for q in PETLA[n])))
sprawdz("inne plany bez zmian: zasieg_planu(edron) = DEPO_DOJSCIE_ZASIEG, nieznany plan też",
        W.zasieg_planu("edron") == W.DEPO_DOJSCIE_ZASIEG == W.zasieg_planu("nie_ma"))

# --- 2. przejścia pięter w plikach 'do' tylko potwierdzone (pietra.kandydaci: pewne, pole przejścia = nasze)
for n, s in SPOTY.items():
    do = wczytaj(f"{s}_do_depo.json")
    for a, b in zip(do, do[1:]):
        if a[2] == b[2]:
            continue
        pewne = [k for k in pietra.kandydaci(MAPA, a, b) if k.get("pewne")]
        sprawdz(f"{s}: przejście {a}->{b}: pole przejścia {a[:2]} to pewny kandydat pietra.kandydaci",
                any(tuple(k["pole"])[:2] == a[:2] or (tuple(k["pole"]) == (a[0], a[1] + 1, a[2])) for k in pewne), pewne[:2])
    j = do.index(STOI) if STOI in do else -1
    sprawdz(f"{s}: lina z pola OBOK pola liny {LINA[:2]} (stoi {STOI[:2]}), następny punkt = lądowanie {LAD7[:2]}",
            j >= 0 and do[j + 1] == LAD7 and LINA not in do, (j, do[j + 1] if j >= 0 else None))

# --- 3. regresja: bez zasięgu planu (stary kod) z pętli "brak drogi"; z zasięgiem planu droga jest
for n, s in SPOTY.items():
    plan = next(p for p in W.PLANY_PK if p["nazwa"] == s)
    do = wczytaj(plan["do"])
    sprawdz(f"{s}: STARY KOD (zasięg 200) z {PETLA[n][0]}: brak drogi",
            W.droga_do_depo(PETLA[n][0], PETLA[n], do, zalew, MAPA) is None)

# --- 4. droga z punktów pętli (co 5., plus ostatni; pełne 191+207 punktów: 7 min, sprawdzone 23.10 41/41) do depo: ciągła, bez ognia, bez dziury Thais pn, lina z pola obok
for n, s in SPOTY.items():
    plan = next(p for p in W.PLANY_PK if p["nazwa"] == s)
    do = wczytaj(plan["do"])
    zle = {"brak": [], "koniec": [], "ciaglosc": [], "ogien": [], "dziura": [], "lina": [], "przej": []}
    for poz in PETLA[n][::5] + [PETLA[n][-1]]:
        wyn = W.droga_do_depo(poz, PETLA[n], do, zalew, MAPA, wyjscia=plan.get("wyjscia", ()), zasieg=W.zasieg_planu(s))
        if wyn is None:
            zle["brak"].append(poz)
            continue
        pts = [tuple(q) for q in wyn[0]]
        if pts[-1] != DEPO:
            zle["koniec"].append((poz, pts[-1]))
        if ciagla(pts):
            zle["ciaglosc"].append((poz, ciagla(pts)))
        if OGIEN & set(pts):
            zle["ogien"].append((poz, sorted(OGIEN & set(pts))[:2]))
        if DZIURA_PN in pts or NAUCZONE & set(pts):
            zle["dziura"].append(poz)
        zm = [(a, b) for a, b in zip(pts, pts[1:]) if a[2] != b[2]]
        if LINA in pts or (LINA[0], LINA[1], 8) in [a for a, _ in zm]:
            zle["lina"].append((poz, zm[:2]))
        dozw = {(STOI, LAD7)} | ({SCHODY9} if n == "z9" else set()) | {(a, b) for a, b in zip(do, do[1:]) if a[2] != b[2]}
        if any(p not in dozw for p in zm):
            zle["przej"].append((poz, [p for p in zm if p not in dozw][:2]))
    for k, v in zle.items():
        sprawdz(f"{s}: droga z {len(PETLA[n][::5]) + 1} punktów pętli, kategoria '{k}' czysta", not v, v[:2])

# --- 5. cała ścieżka wyprawy (Wyprawa._start_wyprawa, "Wróć do miasta"): baza, plan kompletny, ciągły, bez uwag planu
dane = {"powody": ["reczny"], "zapas": None, "blanki": None, "zloto": None, "cap": None, "hp": 100, "pochodnie": None,
        "depo": True, "reczny": True}
for n, s in SPOTY.items():
    bledy = []
    wybrane = PETLA[n][::15] + [PETLA[n][-1]]
    for poz in wybrane:
        w, cb, logi = nowa(poz, PETLA[n])
        wynik = w._start_wyprawa("depo:reczny", dane, 0.0)
        pts = punkty_planu(w) if w.w else []
        et = w.w["legs"][0] if w.w else []
        dobry = (wynik is True and w.w["baza"].startswith("trolle_kazordoon_") and pts and pts[0] == poz and pts[-1] == DEPO
                 and ciagla(pts) is None and not wypad.sprawdz_plan(et, MAPA, rampy_ok=True)
                 and not any("brak drogi" in l for l in logi) and any("Wyprawa: depo: droga z" in l for l in logi)
                 and LINA not in pts and sum(1 for e in et if e["typ"] == "LINA") >= 2)
        if not dobry:
            bledy.append((poz, wynik, w.w and w.w["baza"], pts[:1], pts[-1:], logi[-2:]))
    sprawdz(f"{s}: _start_wyprawa z {len(wybrane)} punktów pętli: baza trolle_kazordoon_*, plan od pozycji do depo", not bledy, bledy[:2])
    # lina w planie: etap LINA z pola obok pola liny
    w, cb, logi = nowa(PETLA[n][0], PETLA[n])
    w._start_wyprawa("depo:reczny", dane, 0.0)
    liny = [e for e in w.w["legs"][0] if e["typ"] == "LINA"] if w.w else []
    sprawdz(f"{s}: etap LINA z pola {STOI[:2]} (obok pola liny)", any(tuple(e["stoi"]) == STOI and tuple(e["ladunek"]) == LAD7 for e in liny), liny[:2])

# --- 6. z pętli z9 plan zaczyna się od schodów w górę z9 -> z8 (pierwsze przejście), dopiero potem lina z8 -> z7
w, cb, logi = nowa(PETLA["z9"][0], PETLA["z9"])
w._start_wyprawa("depo:reczny", dane, 0.0)
liny = [e for e in w.w["legs"][0] if e["typ"] == "LINA"] if w.w else []
sprawdz("z9 start pętli: baza z9, pierwsze przejście = schody w górę (32648,32003,z9), drugie = lina z8",
        w.w and w.w["baza"] == "trolle_kazordoon_z9" and len(liny) >= 2 and tuple(liny[0]["stoi"]) == SCHODY9[0]
        and tuple(liny[1]["stoi"]) == STOI, liny[:2])

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
