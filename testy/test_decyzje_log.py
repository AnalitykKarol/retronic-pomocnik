#!/usr/bin/env python3
"""15.10 (krok A SPEC_model_lokalny_1015): log decyzji D1 (wybór celu) i D2 (start pościgu) w telemetrii.
Rekord "decyzja" ma opcje z cechami i wybraną; id łączy go z nowy_cel / epizod_celu (D1) i poscig_start /
poscig_koniec (D2). DECYZJE_LOG=0 = brak rekordów; błąd logu nie przerywa ticka; decyzje bota się nie zmieniają."""
import os
import random
import sys
import tempfile
import types
from pathlib import Path

os.environ.setdefault("RETRONIC_TESTY", "1")
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bot  # noqa: E402
import cavebot  # noqa: E402
DOMYSLNE_DECYZJE_LOG = cavebot.DECYZJE_LOG   # przed testami, które je przełączają
import telemetria  # noqa: E402

wyniki = []


def sprawdz(nazwa, warunek, info=""):
    wyniki.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + (f"  {info}" if not warunek and info else ""))


# deterministycznie: bez losowych dodatków i pauz (jak test_cavebot.py)
cavebot.REAKCJA = (0.0, 0.0)
cavebot.DRUGI_CEL = 0.0
cavebot.ROZRZUT_PROGU = 0.0
cavebot.STRAZNIK_CEL = 0
cavebot.ODWROCENIE_TRASY = 0.0
cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5)
cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False


class Swiat:
    def __init__(s, poz=(100, 100, 7)):
        s.t = 0.0
        s.poz = list(poz)
        s.stwory = []
        s.klawisze = []
        s.ataki = []

    def zegar(s):
        return s.t

    def spij(s, d):
        s.t += d

    def zapytaj(s, z):
        s.t += 0.05
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


def mob(i, x, y=100, hp=100, nazwa="Rat", gracz=False):
    return {"id": i, "nazwa": nazwa, "gracz": gracz, "x": x, "y": y, "z": 7, "hp": hp}


class TeleBlad(telemetria.Telemetria):
    """Telemetria, której zapis decyzji zawsze rzuca (sprawdzamy, że tick tego nie odczuwa)."""
    def zdarzenie(self, typ, **d):
        if typ == "decyzja":
            raise RuntimeError("zepsuty zapis")
        return super().zdarzenie(typ, **d)


def scena(stwory, tele_klasa=telemetria.Telemetria, zabija=True):
    """Bot z prawdziwą Telemetria (bez zapisu na dysk), linie logu karmią telemetria.linia jak na żywo."""
    s = Swiat()
    s.stwory = stwory
    atak_log = []

    def atak(m, g):
        atak_log.append(m["id"])
        s.ataki.append(m["id"])
        for x in s.stwory:
            if x["id"] == m["id"] and zabija:
                x["hp"] -= 50
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj, atak=atak,
                        alarm=lambda w: None, spij=s.spij, zegar=s.zegar, okrazenia=1,
                        loot=types.SimpleNamespace(zbierz=lambda zw, g: "ok"))
    tele = tele_klasa(Path(tempfile.mkdtemp()), zegar=s.zegar, zapis=False)
    tele.nazwa_postaci = "Ja"
    b.tele = tele
    return s, b, tele, atak_log


def rek(tele, typ):
    return [r for r in tele.rek if r["typ"] == typ]


def przebieg(stwory, ticki=25, **kw):
    """Uruchamia scenę z hakiem logu -> telemetria.linia; zwraca (świat, bot, telemetria, ataki)."""
    random.seed(7)                  # reszta bota losuje (pauzy, drobne opóźnienia): ten sam los dla porównań
    s, b, tele, ataki = scena(stwory, **kw)
    cavebot.HAKI_LOGU.append(tele.linia)
    try:
        for _ in range(ticki):
            b.tick()
            s.stwory[:] = [m for m in s.stwory if m["hp"] > 0]     # zwłoki znikają z listy
    finally:
        cavebot.HAKI_LOGU.remove(tele.linia)
    return s, b, tele, ataki


def stwory_d1():
    # bliski szczur, daleki ranny szczur, obcy gracz tuż przy dalekim
    return [mob(5, 103), mob(6, 106, hp=40), mob(9, 107, gracz=True, nazwa="Obcy")]


# --- 1. D1: rekord decyzja ma pola i kandydatów, wybrana = cel, id łączy nowy_cel / epizod_celu ---
cavebot.DECYZJE_LOG = 1
s, b, tele, ataki = przebieg(stwory_d1())
dec = rek(tele, "decyzja")
d1 = [r for r in dec if r["rodzaj"] == "D1"]
sprawdz("1a jest rekord decyzja D1", len(d1) >= 1, f"decyzje={[r['rodzaj'] for r in dec]}")
r = d1[0] if d1 else {}
sprawdz("1b pola rekordu: id, rodzaj, poz, opcje, wybrana", all(k in r for k in ("id", "rodzaj", "poz", "opcje", "wybrana")), sorted(r))
sprawdz("1c poz = pozycja bota przy wyborze", r.get("poz") == [100, 100, 7], r.get("poz"))
op = {o["id"]: o for o in r.get("opcje", [])}
sprawdz("1d kandydaci to dwa szczury (gracz nie jest opcją)", set(op) == {5, 6}, sorted(op))
pola = ("id", "n", "dx", "dy", "odl", "droga", "hp", "przy_celu2", "odl_gracza", "ucieka", "klucz")
sprawdz("1e każda opcja ma komplet cech", all(all(k in o for k in pola) for o in op.values()),
        [k for o in op.values() for k in pola if k not in o])
sprawdz("1f cechy bliskiego szczura: dx 3, dy 0, odl 3, hp 100, droga null",
        op.get(5, {}).get("dx") == 3 and op[5]["dy"] == 0 and op[5]["odl"] == 3 and op[5]["hp"] == 100
        and op[5]["droga"] is None, op.get(5))
sprawdz("1g daleki szczur: odl 6, hp 40, gracz 1 pole od niego, brak innych mobów w 2 polach (gracz się nie liczy)",
        op.get(6, {}).get("odl") == 6 and op[6]["hp"] == 40 and op[6]["odl_gracza"] == 1 and op[6]["przy_celu2"] == 0,
        op.get(6))
sprawdz("1h wybrana = id celu bota (pierwszy atak)", r.get("wybrana") == (ataki[0] if ataki else None) and r.get("wybrana") in op,
        f"wybrana={r.get('wybrana')} ataki={ataki[:3]}")
sprawdz("1i regula (pierwszy wg klucza) zapisana i zgodna z wyborem bez losowania", r.get("regula") == r.get("wybrana"),
        f"regula={r.get('regula')} wybrana={r.get('wybrana')}")
nc = [x for x in rek(tele, "nowy_cel")]
sprawdz("1j nowy_cel niesie decyzja_id = id decyzji", nc and nc[0].get("decyzja_id") == r.get("id"), nc[:1])
ep = rek(tele, "epizod_celu")
sprawdz("1k epizod_celu (po zabiciu) niesie to samo decyzja_id", ep and ep[0].get("decyzja_id") == r.get("id"), ep[:1])
ids = [x["id"] for x in dec]
sprawdz("1l id decyzji unikalne w sesji", len(ids) == len(set(ids)), ids)
sprawdz("1m kolejna decyzja (drugi szczur) ma kolejny id i łączy się z własnym nowy_cel",
        len(d1) >= 2 and d1[1]["id"] != d1[0]["id"] and len(nc) >= 2 and nc[1].get("decyzja_id") == d1[1]["id"],
        f"d1={[x['id'] for x in d1]} nc={[x.get('decyzja_id') for x in nc]}")

# --- 2. DECYZJE_LOG=0: brak rekordów i pól ---
cavebot.DECYZJE_LOG = 0
s0, b0, tele0, ataki0 = przebieg(stwory_d1())
sprawdz("2a DECYZJE_LOG=0: brak rekordów decyzja", rek(tele0, "decyzja") == [])
sprawdz("2b DECYZJE_LOG=0: nowy_cel i epizod_celu bez decyzja_id",
        rek(tele0, "nowy_cel") and all("decyzja_id" not in x for x in rek(tele0, "nowy_cel") + rek(tele0, "epizod_celu")))

# --- 3. decyzje bota się nie zmieniają: te same ataki, klawisze, pozycja i cele z logiem i bez ---
sprawdz("3a te same ataki i ruch z DECYZJE_LOG=1 i 0",
        ataki == ataki0 and s.klawisze == s0.klawisze and s.poz == s0.poz and abs(s.t - s0.t) < 1e-9,
        f"ataki {ataki} vs {ataki0}; poz {s.poz} vs {s0.poz}; t {s.t} vs {s0.t}")
sprawdz("3b te same nowy_cel (nazwa, pozycja, hp) z logiem i bez",
        [(x["n"], x["pos"], x["hp"]) for x in nc] == [(x["n"], x["pos"], x["hp"]) for x in rek(tele0, "nowy_cel")])

# --- 4. błąd zapisu decyzji nie przerywa ticka ani nie zmienia wyboru ---
cavebot.DECYZJE_LOG = 1
s4, b4, tele4, ataki4 = przebieg(stwory_d1(), tele_klasa=TeleBlad)
sprawdz("4a zepsuty zapis decyzji: tick idzie dalej, te same ataki", ataki4 == ataki0 and s4.poz == s0.poz, f"{ataki4} vs {ataki0}")
sprawdz("4b zepsuty zapis: nowy_cel i epizod_celu bez decyzja_id, bez rekordu decyzja",
        rek(tele4, "decyzja") == [] and rek(tele4, "nowy_cel")
        and all("decyzja_id" not in x for x in rek(tele4, "nowy_cel") + rek(tele4, "epizod_celu")))

# --- 5. brak telemetrii (self.tele None): D1 nic nie robi i nie wywraca ---
s5, b5, tele5, _ = scena(stwory_d1())
b5.tele = None
for _ in range(10):
    b5.tick()
sprawdz("5 bez telemetrii: bot normalnie walczy", s5.ataki, s5.ataki)

# --- 6. D2: rekord decyzja D2 z cechami celu, id w poscig_start i poscig_koniec (atrapa jak sekcja 27 test_cavebot) ---
s6, b6, tele6, _ = scena([mob(7, 106, hp=60)])
cel = dict(s6.stwory[0])
b6._d1_id_cel = 41
b6.ostatnie_stwory = [dict(cel), mob(8, 107), mob(9, 108, gracz=True, nazwa="Obcy")]
cavebot.DECYZJE_LOG = 1
did = b6._decyzja_d2(cel, (100, 100, 7), {"proc": 87.0})
d2 = rek(tele6, "decyzja")
sprawdz("6a D2 zapisuje jeden rekord i zwraca jego id", len(d2) == 1 and d2[0]["rodzaj"] == "D2" and did == d2[0]["id"], d2)
o = d2[0]["opcje"][0] if d2 else {}
sprawdz("6b D2: opcja gonić z cechami celu (odl 6, hp 60, przy_celu2 1, odl_gracza 2, droga null)",
        o.get("akcja") == "gonic" and o.get("id") == 7 and o.get("odl") == 6 and o.get("hp") == 60
        and o.get("przy_celu2") == 1 and o.get("odl_gracza") == 2 and o.get("droga") is None, o)
sprawdz("6c D2: wybrana 'gonic', link do D1 i HP gracza", d2[0]["wybrana"] == "gonic" and d2[0]["d1_id"] == 41
        and d2[0]["hp_gracza"] == 87.0 and d2[0]["cel_id"] == 7, d2[0])
cavebot.DECYZJE_LOG = 0
sprawdz("6d DECYZJE_LOG=0: D2 nie zapisuje i zwraca None", b6._decyzja_d2(cel, (100, 100, 7), {"proc": 87.0}) is None
        and len(rek(tele6, "decyzja")) == 1)

# --- 7. pokrętło: wpis w ZAKRESY pokretla (0, 1) i domyślna 1 ---
import pokretla  # noqa: E402
sprawdz("7a pokrętło DECYZJE_LOG w ZAKRESY (0, 1)", pokretla.ZAKRESY.get("DECYZJE_LOG") == (0, 1))
cavebot.DECYZJE_LOG = 1
sprawdz("7b domyślnie DECYZJE_LOG = 1", DOMYSLNE_DECYZJE_LOG == 1, DOMYSLNE_DECYZJE_LOG)

print(f"\nWYNIK: {sum(wyniki)} / {len(wyniki)}")
sys.exit(0 if all(wyniki) else 1)
