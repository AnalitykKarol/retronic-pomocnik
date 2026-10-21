"""K2 (21.10, SPEC_powroty_k2_1021): pewne powroty do miasta.
1. Kanały Thais -> depo: z dowolnego pola trasy thais_szczury_opt plan idzie najbliższą znaną drabiną pod kratką (F1), nigdy przez
   zgadnięte wyjście (32360,32242,z8) (kutangen 15:37 ALARM). 2. Edron trolle -> depo i 3. Rook: żaden plan do depo/miasta (ani
   dojście z miasta) nie zgłasza uwag sprawdz_plan; rzadkie nagranie (stoi 2 pola od przejścia) daje pole obok przejścia.
Dane rzeczywiste (trasy/*.json, mapa.py), atrapa wyprawy bez gry."""
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
    print("brak pliku mapy, pomijam test powrotów K2")
    sys.exit(0)

MAPA = _mapa.Mapa()


def wczytaj(plik):
    return [tuple(int(v) for v in p) for p in json.loads((TRASY / f"{plik}.json").read_text())]


def ciagla(pts, krok=6):
    for a, b in zip(pts, pts[1:]):
        if a[2] == b[2] and wypad.cheb(a, b) > krok:
            return f"skok {a}->{b}"
        if a[2] != b[2] and wypad.cheb(a, b) > 3:
            return f"skok pięter {a}->{b}"
    return None


# --- atrapa wyprawy ---------------------------------------------------------------------------------------------
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
    def __init__(c, poz, punkty, mapa=MAPA):
        c.mapa = mapa
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


_n = [0]


def nowa(poz, punkty, mapa=MAPA):
    _n[0] += 1
    cb = CBW(poz, punkty, mapa)
    logi = []
    w = W.Wyprawa(cb, OpsW(), konf=KonfW(), log=logi.append, plik_stanu=TMP / f"st{_n[0]}.json",
                  plik_sklepow=TMP / "sk.json", plik_npc=TMP / "npc.json", plik_stop=TMP / f"STOP{_n[0]}",
                  czas=lambda: 5_000_000.0)
    return w, cb, logi


DANE = {"powody": ["reczny"], "zapas": None, "blanki": None, "zloto": None, "cap": None, "hp": 100, "pochodnie": None,
        "depo": True, "reczny": True}
DEPO = (32348, 32225, 7)
DRABINY = {(32370, 32213, 8), (32422, 32214, 8), (32339, 32183, 8)}        # pola drabin pod kratkami (F1)
ZGADNIETE = {(32360, 32242), (32360, 32241), (32361, 32241), (32361, 32242)}

# 1. kanały Thais: wyjście najbliższą drabiną ------------------------------------------------------------------------
P = wczytaj("thais_szczury_opt")
pozycje = P[::6] + [P[-1], (32388, 32214, 8), (32422, 32214, 8), (32422, 32222, 8)]
for poz in pozycje:
    w, cb, logi = nowa(poz, P)
    r = w._start_wyprawa("depo:reczny", dict(DANE), 0.0)
    legs = w.w["legs"][0] if w.w else []
    liny = [e for e in legs if e["typ"] == "LINA"]
    punkty = [tuple(q) for e in legs if e["typ"] == "IDZ" for q in e["punkty"]]
    sprawdz(f"1a {poz}: plan depo z kanałów startuje (baza thais_kanaly)", r is True and w.w["baza"] == "thais_kanaly",
            f"{r} {logi[-2:]}")
    sprawdz(f"1b {poz}: jedno przejście w górę, drabina pod kratką, lądowanie (x, y+1, z7)",
            len(liny) == 1 and tuple(liny[0]["cel"]) in DRABINY
            and tuple(liny[0]["ladunek"]) == (liny[0]["cel"][0], liny[0]["cel"][1] + 1, 7)
            and wypad.cheb(liny[0]["stoi"], liny[0]["cel"]) <= 1, liny)
    sprawdz(f"1c {poz}: plan nie dotyka zgadniętego wyjścia (32360,32242)", not [q for q in punkty if q[:2] in ZGADNIETE],
            [q for q in punkty if q[:2] in ZGADNIETE][:3])
    sprawdz(f"1d {poz}: sprawdz_plan puste, od pozycji do depo, ciągły",
            not wypad.sprawdz_plan(legs, MAPA) and punkty and punkty[0] == poz and punkty[-1] == DEPO and ciagla(punkty) is None,
            (wypad.sprawdz_plan(legs, MAPA), punkty[:1], punkty[-1:], ciagla(punkty)))
    sprawdz(f"1e {poz}: opis drogi w logu", any("Wyprawa: depo: droga z" in l for l in logi), logi[-3:])

# 2. najbliższa drabina wygrywa
for opis, poz, oczekiwana in [("drabina (32370,32213)", (32374, 32214, 8), (32370, 32213, 8)),
                              ("drabina (32422,32214)", (32422, 32222, 8), (32422, 32214, 8)),
                              ("drabina (32339,32183)", (32341, 32190, 8), (32339, 32183, 8))]:
    w, cb, logi = nowa(poz, P)
    w._start_wyprawa("depo:reczny", dict(DANE), 0.0)
    liny = [e for e in (w.w["legs"][0] if w.w else []) if e["typ"] == "LINA"]
    sprawdz(f"2 {opis}: z {poz} wybrana najbliższa", liny and tuple(liny[0]["cel"]) == oczekiwana, liny)

# 3. bez mapy nie wolno iść do zgadniętych schodów: wyprawa nie startuje z komunikatem
w, cb, logi = nowa((32388, 32214, 8), P, mapa=None)
r = w._start_wyprawa("depo:reczny", dict(DANE), 0.0)
sprawdz("3 bez mapy z kanałów: wyprawa nie startuje (zamiast schodów (32360,32242))",
        r is False and w.w is None and any("nie startuję" in l for l in logi), (r, logi[-2:]))

# 4. z innego miejsca z8 (jaskinia trolli) plan dalej wybiera 'troll' (bez zmian)
w, cb, logi = nowa((32482, 32294, 8), P)
w._start_wyprawa("depo:reczny", dict(DANE), 0.0)
sprawdz("4 poza kanałami (jaskinia trolli Thais): baza troll jak dotąd", w.w and w.w["baza"] == "troll", w.w and w.w["baza"])

# 5. Edron: rzadkie nagranie -> przejście z polem stania obok
for plik in ("edron_do_depo", "gobliny_edron_do_depo"):
    et = wypad.zbuduj_etapy(wczytaj(plik), MAPA)
    sprawdz(f"5a {plik}: sprawdz_plan(rampy_ok) bez uwag", wypad.sprawdz_plan(et, MAPA, rampy_ok=True) == [],
            wypad.sprawdz_plan(et, MAPA, rampy_ok=True))
    dz = [e for e in et if e["typ"] == "DZIURA" and e["ladunek"] == (33167, 31813, 8)]
    sprawdz(f"5b {plik}: zejście w (33167,31813,z8): rampa (33167,31812,z7) z flagą 2 obok pola stania, wykonanie próbuje jej samo",
            dz and wypad.cheb(dz[0]["stoi"], dz[0]["dziura"]) == 2 and MAPA.flagi(33167, 31812, 7) & 2
            and wypad._rampa_obok(MAPA, dz[0]["stoi"], dz[0]["dziura"]), dz)
    sprawdz(f"5b2 {plik}: ścisły sprawdz_plan nadal pokazuje rzadkie nagranie (domyślnie rampy_ok=False)",
            bool(wypad.sprawdz_plan(et, MAPA)))
et0 = wypad.zbuduj_etapy(wczytaj("edron_do_depo"))
dz0 = [e for e in et0 if e["typ"] == "DZIURA" and e["ladunek"] == (33167, 31813, 8)]
sprawdz("5c bez mapy zachowanie jak dotąd (dziura = lądowanie, bez poprawki)", dz0 and tuple(dz0[0]["dziura"]) == (33167, 31813, 7), dz0)
et = wypad.zbuduj_etapy(wczytaj("edron_depo_trolle"), MAPA)
sprawdz("5d edron_depo_trolle (powrót): lina z polem stania obok liny", wypad.sprawdz_plan(et, MAPA) == [], wypad.sprawdz_plan(et, MAPA))
# 5e. plan wyprawy Edron nie loguje „plan depo: etap …” (ucieczka PK z trolli z8 jak 21.10 16:12)
PE = wczytaj("edron_nowy_spot")
w, cb, logi = nowa(PE[0], PE)
r = w._start_wyprawa("depo:pk_ucieczka", dict(DANE, powody=["pk"]), 0.0, pk="ucieczka")
sprawdz("5e Edron z8: wyprawa PK startuje, w logu zero uwag planu", r is True and w.w["baza"] in ("edron", "gobliny_edron")
        and not [l for l in logi if "plan depo:" in l], (r, [l for l in logi if "plan" in l]))

# 6. przegląd wszystkich planów do depo/miasta (do) i dojść z miasta (z): zero uwag
wszystkie = []
for p in wypad.PLANY + W.PLANY_PK:
    do, z = json.loads((TRASY / p["do"]).read_text()), json.loads((TRASY / p["z"]).read_text())
    if p.get("prefix"):
        e_do, e_z = wypad.zbuduj_plan(do, z, MAPA)
    else:
        e_do, e_z = wypad.zbuduj_etapy([tuple(q) for q in do], MAPA), wypad.zbuduj_etapy([tuple(q) for q in z], MAPA)
    for kier, et in (("do", e_do), ("z", e_z)):
        bl = wypad.sprawdz_plan(et, MAPA, rampy_ok=True)
        wszystkie.append((p["nazwa"], kier, bl))
        sprawdz(f"6 plan {p['nazwa']} ({kier}): sprawdz_plan bez uwag", not bl, bl)

# 7. Rook: schody (32027,32198,z8) i (32046,32222,z8) to krok, dojście z miasta przez właz (32060,32173,z7) pod ścianą
for nazwa in ("rook_raty_z9", "rook_raty_z8"):
    pl = next(p for p in W.PLANY_PK if p["nazwa"] == nazwa)
    et = wypad.zbuduj_etapy(wczytaj(pl["do"][:-5]), MAPA)
    liny = {e["stoi"]: e for e in et if e["typ"] == "LINA"}
    pole = (32027, 32198, 8) if nazwa == "rook_raty_z9" else (32046, 32222, 8)
    sprawdz(f"7a {nazwa}: schody {pole[:2]} = krok, cel obok pola stania", liny.get(pole) and liny[pole].get("schody")
            and wypad.cheb(pole, liny[pole]["cel"]) == 1, liny.get(pole))
et = wypad.zbuduj_etapy(wczytaj("rook_kanaly_z11_dojscie"), MAPA)
dz = [e for e in et if e["typ"] == "DZIURA"]
sprawdz("7b rook_kanaly_z11 dojście z miasta: zejścia z polem stania obok przejścia albo rampą obok pola stania",
        dz and all(wypad.cheb(e["stoi"], e["dziura"]) <= 1 or wypad._rampa_obok(MAPA, e["stoi"], e["dziura"]) for e in dz), dz)
sprawdz("7c właz (32060,32173,z7) pod ścianą (32060,32172,z7): dziura = właz, niepewna (Use najpierw)",
        dz and tuple(dz[0]["dziura"]) == (32060, 32173, 7) and not dz[0]["pewna"], dz[:1])

# 8. ucieczka PK z kanałów Thais i odtworzenie planu po restarcie (z_poz w stanie)
w, cb, logi = nowa((32388, 32214, 8), P)
r = w._start_wyprawa("depo:pk_ucieczka", dict(DANE, powody=["pk"], reczny=False), 0.0, pk="ucieczka")
liny = [e for e in (w.w["legs"][0] if w.w else []) if e["typ"] == "LINA"]
sprawdz("8a ucieczka PK z kanałów: plan przez drabinę (nie przez (32360,32242))",
        r is True and w.w["baza"] == "thais_kanaly" and len(liny) == 1 and tuple(liny[0]["cel"]) in DRABINY, (r, logi[-2:]))
sprawdz("8b stan zapisuje z_poz (wznowienie po restarcie buduje ten sam plan)", w._stan_czytaj().get("z_poz") == [32388, 32214, 8])
w2, cb2, logi2 = nowa((32388, 32214, 8), P)
w2._z_poz = (32388, 32214, 8)
plan2, blad2 = w2._zbuduj("thais_kanaly", {"depo": True, "pk": "ucieczka"})
sprawdz("8c _zbuduj z zapisanym z_poz = ten sam plan", plan2 is not None and plan2["legs"] == w.w["legs"], blad2)

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
