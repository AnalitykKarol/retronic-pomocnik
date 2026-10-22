"""Drzwi na nagranej trasie (22.10): dojście Edron `edron_depo_trolle` omijało zamknięte drzwi (33166,31817,z7) leżące MIĘDZY punktami trasy
(invincible 10:52: 10x „krok Down nie ruszył”, potem RATUNEK S4), a Use na drzwiach jaskini (32505,32270,z8) szedł w trakcie ruchu i klient go gubił
(wydra, Thais). Poprawka: cavebot.DRZWI_TRASA (stop przed drzwiami, czekanie na stojącą pozycję, Use, krok, max DRZWI_TRASA_PROB prób, potem po staremu),
DRZWI_SPOKOJ (czekanie na stojącą pozycję także w _drzwi_hak), wypad.DRZWI_POMIEDZY (etap DRZWI także dla drzwi między punktami).
Atrapy z test_patrol_troll.py (prawdziwa mapa i trasy), bez gry (RETRONIC_TESTY=1)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
from pathlib import Path

KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
_src = (KAT / "testy" / "test_patrol_troll.py").read_text()
_src = _src[:_src.index("# 2. patrol wizytuje")]
_g = {"__file__": str(KAT / "testy" / "test_patrol_troll.py"), "__name__": "atrapy_patrol_troll"}
exec(compile(_src, "test_patrol_troll(atrapy)", "exec"), _g)
globals().update({k: v for k, v in _g.items() if not k.startswith("__")})
ok.clear()
import json as _json
import trasa_io, wypad, pokretla

HAS_NOWE = hasattr(cavebot, "DRZWI_TRASA")          # na starym kodzie testy zachowania i tak mają się wywrócić, nie testy importu
EDRON = (33166, 31817, 7)
DR = (32505, 32270, 8)
STAN = {"otwarte": False}
KROK_ANIM_S = 0.45        # MODEL (do potwierdzenia na żywo): Use wysłany < KROK_ANIM_S s po zmianie pozycji (postać jeszcze idzie) klient gubi


def f2(x, y, z):
    v = M.flagi(x, y, z)
    if (x, y, z) in LADOWANIA:
        v &= ~2
    if (x, y, z) in (DR, EDRON):
        return (v | 1) & ~4 if STAN["otwarte"] else (v | 1 | 4)
    return v


_g["f"] = f2


class P3(P):
    def krok(p, k):
        r = P.krok(p, k)
        p.s.ostatni_klawisz = p.s.t        # koniec kroku (klawisz puszczony); Use zaraz po nim trafia w animację
        return r

    def klawisz(p, k):
        p.krok(k)


class Swiat3(Swiat):
    def __init__(s, poz, drzwi_dzialaja=True, model_animacji=True, **kw):
        super().__init__(poz, **kw)
        s.drzwi_dzialaja = drzwi_dzialaja
        s.model_animacji = model_animacji
        s.ostatni_klawisz = -99.0
        s.ostatni_ruch = -99.0
        s.zgubione = 0
        s.uz_poz = []
        STAN["otwarte"] = False

    def ruch(s, dx, dy):
        przed = tuple(s.poz)
        Swiat.ruch(s, dx, dy)
        if tuple(s.poz) != przed:
            s.ostatni_ruch = s.t

    def uzyj(s, pole):
        s.uzycia.append(tuple(pole))
        s.uz_poz.append(tuple(s.poz))
        if _os.environ.get("DBG"):
            print("   Use", pole, "z", s.poz, "t", round(s.t, 2), "od klawisza", round(s.t - s.ostatni_klawisz, 2), "od ruchu", round(s.t - s.ostatni_ruch, 2))
        if s.model_animacji and s.t - s.ostatni_ruch < KROK_ANIM_S:
            s.zgubione += 1                       # klient gubi Use w trakcie kroku
            return
        if tuple(pole) in (DR, EDRON) and s.drzwi_dzialaja:
            STAN["otwarte"] = True


def zrob3(s, punkty, fabryka=None, **kw):
    fabryka = fabryka or cavebot.CavebotDojscie
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
    extra = {"tolerancja": 2} if fabryka is cavebot.CavebotDojscie else {}
    b = fabryka(P3(s), punkty, okrazenia=1, zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij,
                zegar=s.zegar, loot=loot, mapa=M, klik=s.klik, **extra, **kw)
    b.pietra_ops = Ops(s)
    b.zapis_znanych = False
    return b


DOJ = [tuple(p) for p in _json.loads((KAT / "trasy" / "edron_depo_trolle.json").read_text())]
# odcinek z drzwiami; za drzwiami dopełniony punktami co pole (korytarz x=33166), bo krótka trasa (< 10 pkt) zalicza w _idz_trasa punkt "do tyłu"
DOJ_Z7 = DOJ[10:16] + [(33166, y, 7) for y in range(31821, 31827)] + [DOJ[17]]
START_D = DOJ_Z7[0]
KONIEC_D = DOJ_Z7[-1]


def dojscie(drzwi_dzialaja=True, otwarte=False, maks=1500, limit_s=50.0, **kw):
    LOG.clear()
    s = Swiat3(START_D, drzwi_dzialaja=drzwi_dzialaja, **kw)
    STAN["otwarte"] = otwarte
    b = zrob3(s, list(DOJ_Z7))
    n = 0
    while n < maks and s.t < limit_s and b.tick():
        n += 1
        s.t += 0.05
        if _os.environ.get("DBG"):
            print("   tick", n, s.poz, "idx", b.idx, "przebyte", b.przebyte)
    return s, b, n


def niezdrowe(s):
    return sum("nie ruszył" in l for l in LOG)


# --- 1. wykrywanie drzwi na trasie ---
if HAS_NOWE:
    dr = trasa_io.drzwi_na_trasie(DOJ, M)
    sprawdz("1a drzwi_na_trasie: dojście Edron ma drzwi (33166,31817,z7) między punktami 14 i 15",
            [d["pole"] for d in dr] == [EDRON] and dr[0]["kier"] == (0, 1) and dr[0]["wejscie"] == (33166, 31816, 7)
            and dr[0]["wyjscie"] == (33166, 31818, 7) and dr[0]["po"] == 15, f"{dr}")
    sprawdz("1b trasa bez ścian (edron_trolle_petla): brak drzwi",
            trasa_io.drzwi_na_trasie([tuple(p) for p in _json.loads((KAT / "trasy" / "edron_trolle_petla.json").read_text())], M) == [])
    sprawdz("1c bez mapy: brak drzwi, bez wyjątku", trasa_io.drzwi_na_trasie(DOJ, None) == [])
    sprawdz("1d skosy nie są drzwiami", trasa_io.drzwi_na_trasie([(33160, 31810, 7), (33166, 31820, 7)], M) == [])
else:
    sprawdz("1 trasa_io.drzwi_na_trasie istnieje", hasattr(trasa_io, "drzwi_na_trasie"))

# --- 2. dojście przez zamknięte drzwi: Use, potem przejście ---
cavebot.DRZWI_TRASA = 1 if HAS_NOWE else None
s, b, n = dojscie()
if _os.environ.get("DBG"):
    print(n, s.poz, b.idx, len(b.punkty), "\n".join(LOG))
dosz = s.poz[1] >= 31820
sprawdz("2a zamknięte drzwi na dojściu: Use i przejście", dosz and EDRON in s.uzycia and STAN["otwarte"], f"poz={s.poz} uz={s.uzycia} n={n}")
if _os.environ.get("DBG"):
    print("\n".join(l for l in LOG if "nie ruszył" in l))
sprawdz("2b bez serii nieudanych kroków w ścianę (starzy: 10x)", niezdrowe(s) <= 1, f"{niezdrowe(s)}")
sprawdz("2c Use tylko z pola przed drzwiami (33166,31816)", set(s.uz_poz) == {(33166, 31816, 7)} and s.zgubione == 0, f"zgubione={s.zgubione}")
sprawdz("2d bez odpuszczenia drzwi", not any("odpuszczam" in l for l in LOG))

s, b, n = dojscie(otwarte=True)
sprawdz("3a drzwi otwarte: przejście bez Use", s.poz[1] >= 31820 and not s.uzycia, f"poz={s.poz} uz={s.uzycia}")

LOG.clear()
s, b, n = dojscie(drzwi_dzialaja=False)
uz = s.uzycia.count(EDRON)
sprawdz("4a drzwi niedziałające: max 3 Use", 1 <= uz <= 3, f"uz={uz}")
sprawdz("4b jedna notatka o odpuszczeniu", sum("odpuszczam" in l for l in LOG) == 1, f"{[l for l in LOG if 'odpuszczam' in l]}")

if HAS_NOWE:
    odc = [(32503, 32270, 8), (32507, 32270, 8)]     # drzwi jaskini (PLIK_DRZWI) między punktami
    s = Swiat3((32503, 32270, 8)); b = zrob3(s, odc, fabryka=cavebot.Cavebot)
    sprawdz("3b drzwi z PLIK_DRZWI zostają przy _drzwi_hak: _drzwi_trasy ich nie dubluje (test_drzwi_ponow 2 tego wymaga)",
            [e["pole"] for e in trasa_io.drzwi_na_trasie(odc, M)] == [DR] and b._drzwi_trasy() == [],
            f"{[e['pole'] for e in trasa_io.drzwi_na_trasie(odc, M)]} -> {[e['pole'] for e in b._drzwi_trasy()]}")

# --- 5. pokrętło: DRZWI_TRASA=0 = stare zachowanie (nie otwiera) ---
if HAS_NOWE:
    cavebot.DRZWI_TRASA = 0
    s, b, n = dojscie()
    sprawdz("5a DRZWI_TRASA=0: bez Use, postać nie przechodzi (jak przed poprawką)", not s.uzycia and s.poz[1] < 31817, f"poz={s.poz} uz={s.uzycia}")
    cavebot.DRZWI_TRASA = 1

# --- 6. wydra: Use w trakcie ruchu (drzwi jaskini, _drzwi_hak) ---
def hak_po_ruchu(spokoj):
    """Postać właśnie dokończyła krok pod drzwi (32504 -> drzwi 32505), epizod drzwi jest już stary (> DRZWI_KROK_S): hak wysyła Use."""
    cavebot.DRZWI_SPOKOJ = spokoj
    cavebot.PATROL_DRZWI = 1
    LOG.clear()
    s = Swiat3((32503, 32270, 8))
    b = zrob3(s, list(troll), fabryka=cavebot.Cavebot)
    b.postac = P3(s)
    b.drzwi_stan[DR] = {"poz": (32503, 32270, 8), "t0": s.t, "proby": 0, "zle_do": float("-inf"), "nota": False, "otw": False}
    s.t += cavebot.DRZWI_KROK_S + 0.2
    s.ruch(1, 0)                                   # krok na 32504 w tej chwili
    s.t += 0.1
    poz = tuple(s.poz)
    kolej = [DR, (32506, 32270, 8)]
    for _ in range(4):                             # kilka obiegów, jak w patrolu/pościgu
        w = b._drzwi_hak(poz, kolej, False)
        s.t += 0.25
        if STAN["otwarte"] or w is not True:
            break
    return s, b


pd0, sp0 = cavebot.PATROL_DRZWI, getattr(cavebot, "DRZWI_SPOKOJ", None)
s, b = hak_po_ruchu(1 if HAS_NOWE else 0)
if HAS_NOWE:
    sprawdz("6a DRZWI_SPOKOJ=1: Use dopiero po stojącej pozycji, drzwi się otwierają", s.zgubione == 0 and STAN["otwarte"] and len(s.uzycia) == 1,
            f"uz={len(s.uzycia)} zgubione={s.zgubione}")
    s, b = hak_po_ruchu(0)
    sprawdz("6b DRZWI_SPOKOJ=0 (jak dotąd): Use zaraz po kroku zgubiony", s.zgubione >= 1 and not STAN["otwarte"], f"uz={len(s.uzycia)} zgubione={s.zgubione}")
else:
    sprawdz("6a Use dopiero po stojącej pozycji, drzwi się otwierają", s.zgubione == 0 and STAN["otwarte"] and len(s.uzycia) == 1,
            f"uz={len(s.uzycia)} zgubione={s.zgubione}")
cavebot.PATROL_DRZWI = pd0
if sp0 is not None:
    cavebot.DRZWI_SPOKOJ = sp0

# pełny przebieg pościgu przez drzwi jaskini nadal działa (test_poscig_skosy_drzwi 3a)
cavebot.PATROL_DRZWI = 1
LOG.clear()
s = Swiat3((32503, 32270, 8))
b = zrob3(s, list(troll), fabryka=cavebot.Cavebot)
b.postac = P3(s)
cel = (32508, 32270)
w = False
for i in range(160):
    poz = tuple(s.poz)
    if max(abs(poz[0] - cel[0]), abs(poz[1] - cel[1])) <= 1:
        w = True
        break
    r = b.podejdz(cel, poz, pilne=True, natychmiast=True, poscig=True, objazd=True)
    s.t += 0.25
    if r is None:
        w = None
        break
sprawdz("6c pościg przez drzwi jaskini: Use i dojście do celu", w is True and STAN["otwarte"] and s.zgubione == 0, f"{w} uz={len(s.uzycia)} zgubione={s.zgubione}")
cavebot.PATROL_DRZWI = pd0

# --- 7. wypad: etap DRZWI także dla drzwi między punktami ---
tr = [tuple(p) for p in _json.loads((KAT / "trasy" / "edron_depo_trolle.json").read_text())]
dz = wypad.drzwi_z_mapy(tr, M)
sprawdz("7a wypad.drzwi_z_mapy znajduje drzwi pośrednie (33166,31817,z7)", EDRON in dz, f"{dz}")
et = wypad.zbuduj_etapy(tr, M, dz)
dr_et = [e for e in et if e["typ"] == "DRZWI"]
sprawdz("7b zbuduj_etapy: etap DRZWI z pola (33166,31816,z7) na drzwi", len(dr_et) == 1 and tuple(dr_et[0]["drzwi"]) == EDRON and tuple(dr_et[0]["stoi"]) == (33166, 31816, 7), f"{dr_et}")
if hasattr(wypad, "DRZWI_POMIEDZY"):
    wypad.DRZWI_POMIEDZY = 0
    sprawdz("7c DRZWI_POMIEDZY=0: drzwi pośrednie niewidoczne (jak dotąd)", EDRON not in wypad.drzwi_z_mapy(tr, M))
    wypad.DRZWI_POMIEDZY = 1

# --- 8. pokrętła ---
nowe = ("DRZWI_TRASA", "DRZWI_SPOKOJ")
sprawdz("8a pokrętła w ZAKRESY i KIERUNEK", all(k in pokretla.ZAKRESY and k in pokretla.KIERUNEK for k in nowe))
przyklad = _json.loads((KAT / "na_zywo.przyklad.json").read_text())
sprawdz("8b na_zywo.przyklad.json: DRZWI_TRASA=1 i DRZWI_SPOKOJ=1", all(przyklad.get(k) == 1 for k in nowe))

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
