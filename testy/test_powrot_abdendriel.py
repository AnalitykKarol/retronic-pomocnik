"""24.10: powrot do depo Ab'Dendriel z jaskini trolli z10/z9 (abdendriel_trolle_z10_z9, Marinarra): generuj_powrot_abdendriel.py -> trasy/abdendriel_trolle_do_depo
+ wpis abdendriel_trolle_z10 w wyprawa.PLANY_PK. Nic nie wysyla do gry i niczego nie zmienia na dysku (poza katalogiem tymczasowym).
Sprawdza: plik trasy rowny wynikowi generatora, ciaglosc i dokladnie dwa przejscia pieter (lina z10->z9, schody z9->z8), pola liny/schodow/dziur poza trasa,
brak ognia i trucizny, dwoje drzwi na prostych odcinkach, etapy zbuduj_etapy (IDZ LINA IDZ LINA IDZ), nowa galaz wypad.zbuduj_etapy (schody ze
ladowaniem przed polem stania), punkty_bazy, panel.plan_depo, pelny plan Wyprawa._start_wyprawa z petli z10 i z9 (sprawdz_plan bez uwag) oraz ze plany
innych miast nie zmienily wyboru.
NIEZWERYFIKOWANE NA ZYWO: lina z10 (32668,31624), schody w gore z9 (32654,31670), oba drzwi, polozenie depo (32679,31687,z8), lina w plecaku."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
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
import generuj_powrot_abdendriel as G

TMP = Path(tempfile.mkdtemp())
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test powrotu abdendriel")
    sys.exit(0)

MAPA = _mapa.Mapa()
DO, META = trasa_io.wczytaj(G.NAZWA)
DO = [tuple(p) for p in DO]
PLAN = next((p for p in W.PLANY_PK if p["nazwa"] == "abdendriel_trolle_z10"), None)

# 1. plik == generator, struktura
pts, _meta = G.zbuduj()
sprawdz("1a plik trasy abdendriel_trolle_do_depo == wynik generatora (zbuduj)", DO == [tuple(p) for p in pts], (len(DO), len(pts)))
sprawdz("1b start (32668,31623,z10), koniec = DEPO_STOI", DO[0] == G.STOI10 and DO[-1] == G.DEPO_STOI, (DO[0], DO[-1]))
przej = [(a, b) for a, b in zip(DO, DO[1:]) if a[2] != b[2]]
sprawdz("1c dokladnie dwa przejscia pieter: lina z10->z9 i schody z9->z8", przej == [(G.STOI10, G.LAD9), (G.STOI_SCHODY9, G.LAD8)], przej)
skoki = [(a, b) for a, b in zip(DO, DO[1:]) if a[2] == b[2] and max(abs(a[0] - b[0]), abs(a[1] - b[1])) > 4]
sprawdz("1d ciaglosc: zadnego skoku > 4 pol na jednym pietrze", not skoki, skoki[:2])
zakaz = {G.LINA10, G.SCHODY9, G.SCHODY8_W_DOL, G.SCHODY8_W_GORE, (32668, 31625, 10), (32668, 31624, 9)}
sprawdz("1e pola liny, schodow i dziur poza trasa", not (zakaz & set(DO)), sorted(zakaz & set(DO)))
sprawdz("1f drzwi z nagrania na trasie rozpoznane (trasa_io.drzwi_na_trasie)", sorted(d["pole"] for d in trasa_io.drzwi_na_trasie(DO, MAPA)) == sorted(G.DRZWI9))
sprawdz("1g kontrole generatora przechodza dla pliku (ogien, trucizna, nauczone dziury, ukl. liny i schodow)", G.kontrole(DO) is None)
sprawdz("1h .meta ma start, dwa przejscia pieter (oba kierunki) i koniec", {m["typ"] for m in META} >= {"start", "przed_zmiana_pietra", "schody_w_gore", "drzwi", "koniec"}, META[:1])

# 2. etapy zbuduj_etapy
DRZWI = wypad.drzwi_z_mapy(DO, MAPA)
et = wypad.zbuduj_etapy(DO, MAPA, DRZWI)
typy = [e["typ"] for e in et]
PELNE = ["IDZ", "LINA", "IDZ", "DRZWI", "IDZ", "DRZWI", "IDZ", "LINA", "IDZ"]
sprawdz("2a etapy z pliku z drzwiami: IDZ LINA IDZ DRZWI IDZ DRZWI IDZ LINA IDZ; drzwi = dwa pola z9", typy == PELNE and set(DRZWI) == set(G.DRZWI9), (typy, DRZWI))
lina = [e for e in et if e["typ"] == "LINA"]
dr = [e for e in et if e["typ"] == "DRZWI"]
sprawdz("2a2 etapy DRZWI: stoi na polu przed drzwiami, kolejnosc (32658,31645) potem (32655,31655)",
        [tuple(e["drzwi"]) for e in dr] == G.DRZWI9 and [tuple(e["stoi"]) for e in dr] == [(32658, 31644, 9), (32655, 31654, 9)], dr)
sprawdz("2b lina z10: pole liny (32668,31624,z10) bez flagi schodow, ladowanie (32668,31625,z9)",
        lina[0]["cel"] == G.LINA10 and not lina[0].get("schody") and tuple(lina[0]["ladunek"]) == G.LAD9, lina[0])
sprawdz("2c schody z9: cel = pole schodow (32654,31670,z9), schody=True, stoi (32654,31671,z9), ladunek (32654,31669,z8)",
        lina[1]["cel"] == G.SCHODY9 and lina[1].get("schody") is True and tuple(lina[1]["stoi"]) == G.STOI_SCHODY9
        and tuple(lina[1]["ladunek"]) == G.LAD8, lina[1])
sprawdz("2d sprawdz_plan (z drzwiami) bez uwag", not wypad.sprawdz_plan(et, MAPA, DRZWI, rampy_ok=True), wypad.sprawdz_plan(et, MAPA, DRZWI, rampy_ok=True)[:2])
# nowa galaz zbuduj_etapy (schody z ladowaniem przed polem stania, pole liny > 2 pola od stania) jest wlaczona tylko dla pewnych schodow z pietra.py
et2 = wypad.zbuduj_etapy([(32654, 31672, 9), (32654, 31671, 9), (32654, 31669, 8), (32655, 31670, 8)], MAPA)
sprawdz("2e zbuduj_etapy: schody z ladowaniem przed polem stania rozpoznane", [e["typ"] for e in et2] == ["IDZ", "LINA", "IDZ"] and et2[1]["cel"] == (32654, 31670, 9) and et2[1].get("schody"), et2)
et3 = wypad.zbuduj_etapy([(32654, 31672, 9), (32654, 31671, 9), (32654, 31660, 8), (32655, 31660, 8)], MAPA)
sprawdz("2f zbuduj_etapy: ladowanie niepewne (nie ten kandydat pietra.py) nie dostaje schodow", not any(e.get("schody") for e in et3), et3)

# 3. plan w PLANY_PK, punkty_bazy, wybor planu
sprawdz("3a wpis PLANY_PK abdendriel_trolle_z10 istnieje, do/z = pliki, bez npc i prefiksu, drzwi=True", PLAN == G.plan_pk(), PLAN)
sprawdz("3a2 tylko ten plan ma etapy DRZWI (opt-in): _plan_z_drzwiami", W.Wyprawa._plan_z_drzwiami("abdendriel_trolle_z10")
        and not any(W.Wyprawa._plan_z_drzwiami(p["nazwa"]) for p in W.PLANY_PK if p["nazwa"] not in ("abdendriel_trolle_z10", "abdendriel_trolle_z12")))   # 25.10: plan z12 tez z drzwiami
sprawdz("3a3 24.10 drzwi na klucz: PLANY_PK[klucze] == generator (oba drzwi, klucz 2970), a .meta ma klucz przy obu wpisach drzwi",
        PLAN and tuple(PLAN.get("klucze") or ()) == G.KLUCZE_DRZWI and sorted(d for d, _ in G.KLUCZE_DRZWI) == sorted(G.DRZWI9)
        and [m.get("klucz") for m in META if m["typ"] == "drzwi"] == [2970, 2970], (PLAN and PLAN.get("klucze"), [m for m in META if m["typ"] == "drzwi"]))
baza = W.punkty_bazy(nazwy=W.BAZY_PK)
sprawdz("3b punkty_bazy wczytuje plan (do = trasa powrotu, z = nagranie depo->trolle)",
        "abdendriel_trolle_z10" in baza and [tuple(p) for p in baza["abdendriel_trolle_z10"][0]] == DO and len(baza["abdendriel_trolle_z10"][1]) == 60,
        list(baza)[-4:])
PETLA10, _ = trasa_io.wczytaj("abdendriel_trolle_z10_petla")
PETLA9, _ = trasa_io.wczytaj("abdendriel_trolle_z9_petla")
poz_m = (32661, 31608, 10)
wsz = [tuple(p) for p in PETLA10[::10]] + [tuple(p) for p in PETLA9[::10]] + [poz_m]
sprawdz("3c panel.plan_depo = abdendriel_trolle_z10 z petli z10, z9 i z pozycji Marinarry", all(panel.plan_depo(p) in ("abdendriel_trolle_z10", "abdendriel_trolle_z12") for p in wsz),
        [p for p in wsz if panel.plan_depo(p) not in ("abdendriel_trolle_z10", "abdendriel_trolle_z12")][:3])
inne = [(n, tuple(d[0][i])) for n, d in baza.items() if n not in ("abdendriel_trolle_z10", "abdendriel_trolle_z12") for i in range(0, len(d[0]), 15)]   # 25.10: plan z12 ma ten sam koniec "do" (remis -> plan z10)
zmien = [(n, p) for n, p in inne if W.wybierz_baze(baza, p, W.PK_PLAN_ZASIEG) == "abdendriel_trolle_z10"]
sprawdz("3d punkty 'do' innych planow (Edron, Kazordoon, Thais, Rook...) nie wybieraja planu Ab'Dendriel", not zmien, zmien[:3])


# 4. pelny plan wyprawy
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


def plan_z(poz, punkty):
    w, cb, logi = nowa(poz, punkty)
    wynik = w._start_wyprawa("depo:reczny", dane, 0.0)
    return wynik, w, logi


bledy = []
for i in list(range(0, len(PETLA10), 25)) + [len(PETLA10) - 1]:
    poz = tuple(PETLA10[i])
    wynik, w, logi = plan_z(poz, PETLA10)
    et = w.w["legs"][0] if w.w else []
    ts = [e["typ"] for e in et]
    zle = []
    if not (wynik is True and w.w["baza"] in ("abdendriel_trolle_z10", "abdendriel_trolle_z12")):      # 25.10: z pol z10 przy obejsciu dziury bywa blizej plan z12 (ta sama droga)
        zle.append(f"baza {w.w and w.w['baza']} / {logi[-2:]}")
    if ts != PELNE:
        zle.append(f"etapy {ts}")
    if et and wypad.sprawdz_plan(et, MAPA, DRZWI, rampy_ok=True):
        zle.append(f"sprawdz_plan {wypad.sprawdz_plan(et, MAPA, DRZWI, rampy_ok=True)[:2]}")
    pp = [tuple(p) for e in et for p in (e["punkty"] if e["typ"] == "IDZ" else ())]
    if pp and pp[-1] != G.DEPO_STOI:
        zle.append(f"koniec {pp[-1]}")
    if zle:
        bledy.append((i, poz, zle))
sprawdz(f"4a Wyprawa._start_wyprawa z {len(range(0, len(PETLA10), 25)) + 1} punktow petli z10: baza abdendriel_trolle_z10, IDZ LINA IDZ DRZWI IDZ DRZWI IDZ LINA IDZ, koniec w depo, sprawdz_plan bez uwag",
        not bledy, bledy[:2])
wynik, w, logi = plan_z(tuple(PETLA10[0]), PETLA10)
dr_et = [e for e in (w.w["legs"][0] if w.w else []) if e["typ"] == "DRZWI"]
sprawdz("4a2 24.10 pelny plan z petli z10: oba etapy DRZWI maja klucz 2970 (wypad._drzwi uzyje klucza z plecaka)",
        len(dr_et) == 2 and all(e.get("klucz") == 2970 for e in dr_et), dr_et)
bledy = []
for i in range(0, len(PETLA9), 12):
    poz = tuple(PETLA9[i])
    wynik, w, logi = plan_z(poz, PETLA9)
    et = w.w["legs"][0] if w.w else []
    ts = [e["typ"] for e in et]
    zle = []
    if not (wynik is True and w.w["baza"] == "abdendriel_trolle_z10"):
        zle.append(f"baza {w.w and w.w['baza']} / {logi[-2:]}")
    if not ts or ts != PELNE[len(PELNE) - len(ts):] or ts[0] != "IDZ" or not et[-2].get("schody"):
        zle.append(f"etapy {ts}")
    if et and wypad.sprawdz_plan(et, MAPA, DRZWI, rampy_ok=True):
        zle.append(f"sprawdz_plan {wypad.sprawdz_plan(et, MAPA, DRZWI, rampy_ok=True)[:2]}")
    if zle:
        bledy.append((i, poz, zle))
sprawdz("4b petla z9 (jaskinia): baza abdendriel_trolle_z10, koncowka IDZ [DRZWI IDZ [DRZWI IDZ]] LINA(schody) IDZ, bez liny z10 (pomija ja), sprawdz_plan bez uwag", not bledy, bledy[:2])
wynik, w, logi = plan_z(poz_m, PETLA10)
sprawdz("4c pozycja Marinarry (32661,31608,z10): plan startuje, droga do pola stania bez wchodzenia na pole liny",
        wynik is True and w.w["baza"] == "abdendriel_trolle_z10" and G.LINA10 not in {tuple(p) for e in w.w["legs"][0] if e["typ"] == "IDZ" for p in e["punkty"]},
        (wynik, logi[-2:]))
# z11/z12: 25.10 plan abdendriel_trolle_z12 (lina z12/z11 -> z10, testy/test_powrot_abdendriel_z12.py); wczesniej (24.10) start konczyl sie bezpiecznym bledem bez ruchu
PETLA11, _ = trasa_io.wczytaj("abdendriel_trolle_z11_petla")
wynik, w, logi = plan_z(tuple(PETLA11[0]), PETLA11)
sprawdz("4d z11 (25.10): start_wyprawa wybiera plan abdendriel_trolle_z12 z liniami w gore (pierwszy etap po IDZ to LINA), nie ma planu z10 bez drogi",
        wynik is True and w.w and w.w["baza"] == "abdendriel_trolle_z12" and [e["typ"] for e in w.w["legs"][0]][:2] == ["IDZ", "LINA"], (wynik, logi[-1:]))

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
