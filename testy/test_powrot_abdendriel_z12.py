"""25.10: powrot do depo Ab'Dendriel z jaskini trolli z12 i z11 (Marinarra/Marianni): generuj_powrot_abdendriel.zbuduj_z12 -> trasy/abdendriel_trolle_z12_do_depo
+ wpis abdendriel_trolle_z12 w wyprawa.PLANY_PK. Nic nie wysyla do gry i niczego nie zmienia na dysku (poza katalogiem tymczasowym).
Sprawdza: plik == generator, cztery przejscia pieter (lina z12->z11, lina z11->z10, lina z10->z9, schody z9->z8), koncowka bajt w bajt = trasa powrotu z z10,
pola liny i dziur poza trasa, mapa potwierdza oba uklady lin, etapy zbuduj_etapy (3x LINA bez 'schody' i 'wlasne', cele = pola lin), wpis PLANY_PK (drzwi, klucze,
kolejnosc po planie z10), wybor planu z pol z12/z11 (w tym (32690,31601,z12)), plan z10/z9 bez zmian, pelny plan Wyprawa._start_wyprawa (sprawdz_plan bez uwag).
NIEPOTWIERDZONE NA ZYWO: lina z12 -> z11 (dziura z11 -> z12 nigdy nie przeszla), lina z11 -> z10, lina w plecaku, obie pary drzwi na klucz, polozenie depo."""
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
    print("brak pliku mapy, pomijam test powrotu z z12")
    sys.exit(0)

MAPA = _mapa.Mapa()
Z12, META = trasa_io.wczytaj(G.NAZWA_Z12)
Z12 = [tuple(p) for p in Z12]
Z10, _ = trasa_io.wczytaj(G.NAZWA)
Z10 = [tuple(p) for p in Z10]
PLAN = next((p for p in W.PLANY_PK if p["nazwa"] == G.PLAN_Z12), None)
PLAN10 = next((p for p in W.PLANY_PK if p["nazwa"] == "abdendriel_trolle_z10"), None)

# 1. plik == generator, struktura
pts, _m = G.zbuduj_z12()
sprawdz("1a plik abdendriel_trolle_z12_do_depo == wynik generatora (zbuduj_z12)", Z12 == [tuple(p) for p in pts], (len(Z12), len(pts)))
sprawdz("1b start na z12 w korytarzu x=32668, koniec = DEPO_STOI", Z12[0] == (32668, 31620, 12) and Z12[-1] == G.DEPO_STOI, (Z12[0], Z12[-1]))
przej = [(a, b) for a, b in zip(Z12, Z12[1:]) if a[2] != b[2]]
sprawdz("1c dokladnie cztery przejscia: lina z12->z11, lina z11->z10, lina z10->z9, schody z9->z8",
        przej == [(G.STOI12, G.LAD11), (G.STOI11, G.LAD10U), (G.STOI10, G.LAD9), (G.STOI_SCHODY9, G.LAD8)], przej)
sprawdz("1d koncowka od STOI10 == trasa powrotu z z10 bajt w bajt (jedna geometria)", Z12[Z12.index(G.STOI10):] == Z10, (len(Z12), len(Z10)))
skoki = [(a, b) for a, b in zip(Z12, Z12[1:]) if a[2] == b[2] and max(abs(a[0] - b[0]), abs(a[1] - b[1])) > 4]
sprawdz("1e ciaglosc: zadnego skoku > 4 pol na jednym pietrze", not skoki, skoki[:2])
zakaz = {G.ROPE12, G.H11, G.H10, G.LINA10, (32668, 31624, 9), G.SCHODY9, G.SCHODY8_W_DOL, G.SCHODY8_W_GORE}
sprawdz("1f pola lin (z12, z10), dziury z11/z10/z9 i schody poza trasa", not (zakaz & set(Z12)), sorted(zakaz & set(Z12)))
sprawdz("1g lad. z11 (32668,31625) to pole liny z11 i trasa schodzi z niego na zachod (32667,31625); stoi z11 prostopadle, nie pod lad. z10",
        G.LAD11 == (32668, 31625, 11) and Z12[Z12.index(G.LAD11) + 1] == (32667, 31625, 11) and G.STOI11[1] == G.LAD11[1] and G.STOI11[:2] != G.LAD10U[:2], (G.LAD11, G.STOI11))
sprawdz("1h obejscie dziury z10: z10 od (32668,31626) do STOI10 idzie zachodnia strona, bez (32668,31625) i (32668,31624)",
        all(q not in Z12 for q in (G.H10, G.LINA10)) and Z12[Z12.index(G.LAD10U):Z12.index(G.STOI10) + 1][1] [0] < 32668, Z12[Z12.index(G.LAD10U):Z12.index(G.STOI10) + 1])
sprawdz("1i kontrole generatora przechodza dla pliku", G.kontrole_z12(Z12) is None)
sprawdz("1j mapa potwierdza oba uklady lin (kolor 210 na polu liny, flaga 2 nad nim)",
        all(MAPA.pole(*R)[1] == 210 and MAPA.flagi(*R) & 1 and MAPA.flagi(Hh[0], Hh[1], Hh[2]) & 2 for R, Hh in ((G.ROPE12, G.H11), (G.LAD11, G.H10))))
sprawdz("1k .meta: start, 3x przed_zmiana_pietra z lin z12/z11/z10 + schody, drzwi z kluczem 2970, koniec; indeksy w zakresie",
        {m["typ"] for m in META} >= {"start", "przed_zmiana_pietra", "schody_w_gore", "drzwi", "koniec"} and all(0 <= m["idx"] < len(Z12) for m in META)
        and [m.get("klucz") for m in META if m["typ"] == "drzwi"] == [2970, 2970]
        and Z12[[m for m in META if m["typ"] == "koniec"][0]["idx"]] == G.DEPO_STOI, META[:2])
# 24.10 pliki nietkniete: powrot z z10 i dojscie z depo zapisuja sie tak jak wczesniej
sprawdz("1l generator nie zmienil trasy powrotu z z10 ani dojscia z depo (zbuduj/zbuduj_dojscie == pliki)",
        G.zbuduj()[0] == Z10 and G.zbuduj_dojscie()[0] == [tuple(p) for p in trasa_io.wczytaj(G.NAZWA_DOJSCIA)[0]])

# 2. etapy
DRZWI = wypad.drzwi_z_mapy(Z12, MAPA)
et = wypad.zbuduj_etapy(Z12, MAPA, DRZWI)
PELNE = ["IDZ", "LINA", "IDZ", "LINA", "IDZ", "LINA", "IDZ", "DRZWI", "IDZ", "DRZWI", "IDZ", "LINA", "IDZ"]
sprawdz("2a etapy: IDZ LINA IDZ LINA IDZ LINA IDZ DRZWI IDZ DRZWI IDZ LINA IDZ", [e["typ"] for e in et] == PELNE and set(DRZWI) == set(G.DRZWI9), ([e["typ"] for e in et], DRZWI))
lin = [e for e in et if e["typ"] == "LINA"]
sprawdz("2b lina z12: cel = pole liny (32668,31624,z12), lad. (32668,31625,z11), zwykla (bez schodow i 'wlasne')",
        lin[0]["cel"] == G.ROPE12 and tuple(lin[0]["ladunek"]) == G.LAD11 and not lin[0].get("schody") and not lin[0].get("wlasne"), lin[0])
sprawdz("2c lina z11: cel = pole liny (32668,31625,z11), stoi (32667,31625,z11), lad. (32668,31626,z10), zwykla",
        lin[1]["cel"] == G.LAD11 and tuple(lin[1]["stoi"]) == G.STOI11 and tuple(lin[1]["ladunek"]) == G.LAD10U and not lin[1].get("schody") and not lin[1].get("wlasne"), lin[1])
sprawdz("2d lina z10 i schody z9 jak w planie z10", lin[2]["cel"] == G.LINA10 and lin[3]["cel"] == G.SCHODY9 and lin[3].get("schody"), lin[2:])
sprawdz("2e sprawdz_plan (z drzwiami) bez uwag", not wypad.sprawdz_plan(et, MAPA, DRZWI, rampy_ok=True), wypad.sprawdz_plan(et, MAPA, DRZWI, rampy_ok=True)[:2])

# 3. wpis PLANY_PK, wybor planu
sprawdz("3a wpis PLANY_PK abdendriel_trolle_z12 == generator (plan_pk_z12), drzwi=True, te same klucze co plan z10", PLAN == G.plan_pk_z12() and PLAN["klucze"] == PLAN10["klucze"] and PLAN["drzwi"], PLAN)
nazwy = [p["nazwa"] for p in W.PLANY_PK]
sprawdz("3b kolejnosc: plan z12 PO planie z10 (remis przy wyborze rozstrzyga wczesniejszy wpis)", nazwy.index("abdendriel_trolle_z12") > nazwy.index("abdendriel_trolle_z10"), nazwy[-3:])
sprawdz("3c _plan_z_drzwiami i etapy kluczy tylko dla dwoch planow Ab'Dendriel", W.Wyprawa._plan_z_drzwiami("abdendriel_trolle_z12")
        and [p["nazwa"] for p in W.PLANY_PK if W.Wyprawa._plan_z_drzwiami(p["nazwa"])] == ["abdendriel_trolle_z10", "abdendriel_trolle_z12"])
baza = W.punkty_bazy(nazwy=W.BAZY_PK)
sprawdz("3d punkty_bazy wczytuje plan z12 (do = plik, z = nagranie depo->trolle)",
        "abdendriel_trolle_z12" in baza and [tuple(p) for p in baza["abdendriel_trolle_z12"][0]] == Z12 and len(baza["abdendriel_trolle_z12"][1]) == 60, list(baza)[-3:])
P12, _ = trasa_io.wczytaj("abdendriel_trolle_z12_petla")
P11, _ = trasa_io.wczytaj("abdendriel_trolle_z11_petla")
P10, _ = trasa_io.wczytaj("abdendriel_trolle_z10_petla")
P9, _ = trasa_io.wczytaj("abdendriel_trolle_z9_petla")
POZ_M12 = (32690, 31601, 12)
z12 = [tuple(p) for p in P12[::5]] + [tuple(P12[-1]), POZ_M12]
z11 = [tuple(p) for p in P11[::20]] + [tuple(P11[-1])]
zle = [p for p in z12 + z11 if W.wybierz_baze(baza, p, W.PK_PLAN_ZASIEG) != "abdendriel_trolle_z12"]
sprawdz("3e wybierz_baze (zasieg PK 80): kazdy punkt petli z12 i z11 oraz (32690,31601,z12) -> abdendriel_trolle_z12", not zle, zle[:4])
sprawdz("3f panel.plan_depo z pol z12/z11 = abdendriel_trolle_z12", all(panel.plan_depo(p) == "abdendriel_trolle_z12" for p in z12 + z11), [p for p in z12 + z11 if panel.plan_depo(p) != "abdendriel_trolle_z12"][:3])
zle = [p for p in [tuple(q) for q in P9[::10]] + [tuple(q) for q in P10[::10]] + [(32661, 31608, 10)] if W.wybierz_baze(baza, p, W.PK_PLAN_ZASIEG) not in ("abdendriel_trolle_z10", "abdendriel_trolle_z12")]
sprawdz("3g z petli z10/z9 wybierany zawsze plan Ab'Dendriel (z9: dokladnie plan z10)", not zle and all(W.wybierz_baze(baza, tuple(q), W.PK_PLAN_ZASIEG) == "abdendriel_trolle_z10" for q in P9[::10]), zle[:3])
inne = [(n, tuple(d[0][i])) for n, d in baza.items() if not n.startswith("abdendriel_trolle") for i in range(0, len(d[0]), 15)]
zmien = [(n, p) for n, p in inne if W.wybierz_baze(baza, p, W.PK_PLAN_ZASIEG) in ("abdendriel_trolle_z10", "abdendriel_trolle_z12")]
sprawdz("3h punkty 'do' innych planow (Edron, Kazordoon, Thais, Rook...) nie wybieraja planow Ab'Dendriel", not zmien, zmien[:3])


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


def sprawdz_start(poz, petla, oczekiwane):
    wynik, w, logi = plan_z(poz, petla)
    e = w.w["legs"][0] if w.w else []
    ts = [x["typ"] for x in e]
    zle = []
    if not (wynik is True and w.w["baza"] == "abdendriel_trolle_z12"):
        zle.append(f"baza {w.w and w.w['baza']} / {logi[-2:]}")
    if ts != oczekiwane:
        zle.append(f"etapy {ts}")
    if e and wypad.sprawdz_plan(e, MAPA, DRZWI, rampy_ok=True):
        zle.append(f"sprawdz_plan {wypad.sprawdz_plan(e, MAPA, DRZWI, rampy_ok=True)[:2]}")
    pp = [tuple(p) for x in e for p in (x["punkty"] if x["typ"] == "IDZ" else ())]
    if pp and pp[-1] != G.DEPO_STOI:
        zle.append(f"koniec {pp[-1]}")
    dr = [x for x in e if x["typ"] == "DRZWI"]
    if dr and not all(x.get("klucz") == 2970 for x in dr):
        zle.append("drzwi bez klucza")
    return zle, w, e


bledy = []
for i in list(range(0, len(P12), 25)) + [len(P12) - 1]:
    zle_, _w, _e = sprawdz_start(tuple(P12[i]), P12, PELNE)
    if zle_:
        bledy.append((i, tuple(P12[i]), zle_))
sprawdz(f"4a Wyprawa._start_wyprawa z {len(range(0, len(P12), 25)) + 1} punktow petli z12: baza z12, 13 etapow (3x LINA, 2x DRZWI z kluczem, LINA schody), koniec w depo, sprawdz_plan bez uwag",
        not bledy, bledy[:2])
zle_, w, e = sprawdz_start(POZ_M12, P12, PELNE)
sprawdz("4b pozycja Marianni (32690,31601,z12): plan startuje, 13 etapow, pierwszy IDZ idzie po z12 do korytarza x=32668 (nie wchodzi na pole liny ani dziury)",
        not zle_ and e[0]["punkty"][-1][:2] in {(32668, 31623), (32668, 31620), (32668, 31621), (32668, 31622)}
        and G.ROPE12 not in {tuple(p) for x in e if x["typ"] == "IDZ" for p in x["punkty"]}, (zle_, e[0]["punkty"][-3:]))
sprawdz("4b2 LINA z12 w planie dostaje cel = pole liny (32668,31624,z12)", e[1]["typ"] == "LINA" and e[1]["cel"] == G.ROPE12 and e[3]["cel"] == G.LAD11, (e[1], e[3]))
bledy = []
for i in list(range(0, len(P11), 60)) + [len(P11) - 1]:
    zle_, _w, _e = sprawdz_start(tuple(P11[i]), P11, PELNE[2:])
    if zle_:
        bledy.append((i, tuple(P11[i]), zle_))
sprawdz("4c petla z11 (26 trolli): baza z12, 11 etapow (LINA z11, LINA z10, drzwi, schody), pomija lina z12, bez wejscia na dziure z11 (32668,31624), sprawdz_plan bez uwag", not bledy, bledy[:2])
wszystkie = {tuple(p) for x in e for p in (x["punkty"] if x["typ"] == "IDZ" else ())}
sprawdz("4d plan z11 omija dziure z11 (32668,31624) i dziure z10 (32668,31625)", not ({G.H11, G.H10} & wszystkie))
# z10/z9: dotychczasowe zachowanie (plan z10) nie moze sie zmienic
bledy = []
for i in range(0, len(P10), 50):
    wynik, w2, logi = plan_z(tuple(P10[i]), P10)
    ts = [x["typ"] for x in (w2.w["legs"][0] if w2.w else [])]
    if not (wynik is True and w2.w["baza"] in ("abdendriel_trolle_z10", "abdendriel_trolle_z12") and ts == PELNE[4:]):
        bledy.append((i, w2.w and w2.w["baza"], ts))
sprawdz("4e z petli z10 plan Ab'Dendriel dalej IDZ LINA IDZ DRZWI IDZ DRZWI IDZ LINA IDZ (bez dodatkowej liny z11/z12)", not bledy, bledy[:2])

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
