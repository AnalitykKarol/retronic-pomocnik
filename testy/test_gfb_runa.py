"""27.10 (SPEC_gfb_1027.md, A): wybór robionej runy (UH_RUNA_WYBOR) w cavebot._uh na atrapach: domyślnie bez zmian, wybór GFB, brak klawisza,
progi many, praca w walce, pauza po nieudanym rzucie, pokrętła (zakresy, kierunki, tryby, przykład, okno), rozpoznanie runy w serwisie/wyprawie.
Bez X11, bez gry (RETRONIC_TESTY=1)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, tempfile, types
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot, pokretla, uh

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.ZDROWIE_CZAR_OPOZNIENIE = (0.0, 0.0)
cavebot.ML_CZAR_OPOZNIENIE = (0.0, 0.0); cavebot.ML_CZAR_DLUGA_SZANSA = 0.0
cavebot.ML_CZAR_ZAPAS_MANY = (0, 0); cavebot.ML_CZAR_EXTRA_PRZERWA = (0.0, 0.0)
TMP = Path(tempfile.mkdtemp())
KAT = Path(cavebot.__file__).resolve().parent
cavebot.UH_STAN_PLIK = TMP / "uh_stan.json"
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Swiat:
    def __init__(s):
        s.t = 0.0; s.poz = [100, 100, 7]; s.stwory = []; s.klawisze = []; s.mana = 125; s.hp = 100
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp * 1.9, "max_hp": 190, "mana": s.mana, "max_mana": 125}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}
        return {}

class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2
        p.s.poz[0] += d[0]; p.s.poz[1] += d[1]
        return tuple(p.s.poz)

ALARMY = []
def zrob(s):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: ["mięso"], ile_jedzenia=lambda: 10)
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: None, alarm=lambda w: ALARMY.append(w), spij=s.spij, zegar=s.zegar,
                        loot=loot, okrazenia=1, jedzenie="F5")
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    b.jz_odczyt = (0.0, 10)
    return b

def tick(s, b, n=1):
    for _ in range(n):
        s.t += 0.1
        b.tick()

WYWOLANIA = []
WYNIKI = []
def fake_zrob(env, *a, **k):
    WYWOLANIA.append(("zrob", uh.UH_KLAWISZ, uh.UH_KOSZT, uh.UH_CZAR))
    r = WYNIKI.pop(0) if WYNIKI else {"wynik": "ok", "powod": "ok", "alarm": False, "czas_s": 5.0, "rzuty": 1}
    return r
def fake_przywroc(env, *a, **k):
    WYWOLANIA.append(("przywroc",))
    env.stan.pop("tarcza_id", None)
    return {"wynik": "ok", "powod": "ok", "alarm": False, "czas_s": 1.0, "rzuty": 0}
uh.zrob_runa = fake_zrob; uh.przywroc = fake_przywroc
NAPRAWY = []
uh.naprawa = lambda env, *a, **k: (NAPRAWY.append(1), {"wynik": "ok", "powod": "nic do naprawy", "alarm": False, "kroki": []})[1]
def reset():
    WYWOLANIA.clear(); WYNIKI.clear(); ALARMY.clear()
    if cavebot.UH_STAN_PLIK.exists(): cavebot.UH_STAN_PLIK.unlink()
    cavebot.UH_AKTYWNY = 0; cavebot.ML_CZAR_AKTYWNY = 0
    cavebot.UH_RUNA_WYBOR = 'domyslna'; cavebot.UH_GFB_KLAWISZ = ''; cavebot.UH_GFB_KOSZT = 120; cavebot.UH_GFB_PRZERWA_S = 0
    cavebot.UH_KLAWISZ = 'F6'; cavebot.UH_CZAR = 'adori gran'; cavebot.UH_KOSZT = 70; cavebot.UH_MANA_MIN = 95; cavebot.UH_W_WALCE = 0


G0 = lambda s: dict(s.zapytaj({"cmd": "gracz"})["gracz"], proc=100.0)
RA = {"wynik": "przerwane", "powod": "nieudany_cast (mana nie spadła, slot bez zmiany)", "alarm": False, "czas_s": 5.0, "rzuty": 2}

# 0. kontrakt: nowe stałe i pokrętła, domyślnie jak dotąd
sprawdz("0a domyślne stałe", getattr(cavebot, "UH_RUNA_WYBOR", None) == "domyslna" and getattr(cavebot, "UH_GFB_KLAWISZ", None) == ""
        and getattr(cavebot, "UH_GFB_KOSZT", None) == 120 and getattr(cavebot, "UH_GFB_PRZERWA_S", None) == 0
        and getattr(cavebot, "UH_GFB_CZAR", None) == "adori gran flam")
sprawdz("0b UH_RUNA_WYBOR: tekst domyslna|gfb, tylko Karol",
        pokretla.TEKSTY.get("UH_RUNA_WYBOR") == ("domyslna", "gfb")
        and pokretla.waliduj({"UH_RUNA_WYBOR": "gfb"})[0] == {"UH_RUNA_WYBOR": "gfb"}
        and pokretla.waliduj({"UH_RUNA_WYBOR": "hmm"})[0] == {}
        and pokretla.waliduj({"UH_RUNA_WYBOR": "gfb"}, {"UH_RUNA_WYBOR": "domyslna"})[0] == {})
sprawdz("0c UH_GFB_KLAWISZ: '' lub F1..F12, tylko Karol",
        "" in pokretla.TEKSTY.get("UH_GFB_KLAWISZ", ()) and "F8" in pokretla.TEKSTY.get("UH_GFB_KLAWISZ", ())
        and pokretla.waliduj({"UH_GFB_KLAWISZ": "F8"})[0] == {"UH_GFB_KLAWISZ": "F8"}
        and pokretla.waliduj({"UH_GFB_KLAWISZ": "F13"})[0] == {}
        and pokretla.waliduj({"UH_GFB_KLAWISZ": "F8"}, {"UH_GFB_KLAWISZ": ""})[0] == {})
sprawdz("0d UH_GFB_KOSZT 1..500, nie_nizej", pokretla.ZAKRESY.get("UH_GFB_KOSZT") == (1, 500)
        and pokretla.KIERUNEK.get("UH_GFB_KOSZT") == "nie_nizej"
        and pokretla.waliduj({"UH_GFB_KOSZT": 0})[0] == {} and pokretla.waliduj({"UH_GFB_KOSZT": 501})[0] == {}
        and pokretla.waliduj({"UH_GFB_KOSZT": 100}, {"UH_GFB_KOSZT": 120})[0] == {}
        and pokretla.waliduj({"UH_GFB_KOSZT": 130}, {"UH_GFB_KOSZT": 120})[0] == {"UH_GFB_KOSZT": 130})
sprawdz("0e UH_GFB_PRZERWA_S 0..7200, nie_nizej", pokretla.ZAKRESY.get("UH_GFB_PRZERWA_S") == (0, 7200)
        and pokretla.KIERUNEK.get("UH_GFB_PRZERWA_S") == "nie_nizej"
        and pokretla.waliduj({"UH_GFB_PRZERWA_S": 7201})[0] == {}
        and pokretla.waliduj({"UH_GFB_PRZERWA_S": 60}, {"UH_GFB_PRZERWA_S": 0})[0] == {"UH_GFB_PRZERWA_S": 60})
sprawdz("0f Pokretla widzi nowe klucze (domyślne = stałe cavebota)",
        all(k in pokretla.Pokretla(cavebot, plik="/nie/ma").domyslne for k in ("UH_RUNA_WYBOR", "UH_GFB_KLAWISZ", "UH_GFB_KOSZT", "UH_GFB_PRZERWA_S")))
pk = pokretla.Pokretla(cavebot, plik=TMP / "nz.json", log=lambda t: None)
(TMP / "nz.json").write_text(json.dumps({"UH_RUNA_WYBOR": "gfb", "UH_GFB_KLAWISZ": "F8"})); pk.odswiez()
sprawdz("0g na_zywo włącza GFB, skasowanie klucza cofa", getattr(cavebot, "UH_RUNA_WYBOR", None) == "gfb" and cavebot.UH_GFB_KLAWISZ == "F8")
(TMP / "nz.json").write_text("{}"); pk.mtime = None; pk.odswiez()
sprawdz("0h powrót do domyślnej", getattr(cavebot, "UH_RUNA_WYBOR", None) == "domyslna" and cavebot.UH_GFB_KLAWISZ == "")
reset()

# 1. DOMYŚLNIE BEZ ZMIAN: tryb runy (HMM, F6, 70), tryb uh (UH, F7, 100), progi many jak przed zmianą
reset(); cavebot.UH_AKTYWNY = 1; s = Swiat(); b = zrob(s); tick(s, b, 3)
sprawdz("1a domyślnie: dokładnie HMM F6 70 'adori gran'", WYWOLANIA == [("zrob", "F6", 70, "adori gran")], WYWOLANIA)
sprawdz("1b _uh_runa() = (UH_CZAR, UH_KLAWISZ, UH_KOSZT)", getattr(cavebot, "_uh_runa", lambda: None)() == ("adori gran", "F6", 70))
reset(); cavebot.UH_AKTYWNY = 1; cavebot.UH_KLAWISZ = "F7"; cavebot.UH_CZAR = "adura vita"; cavebot.UH_KOSZT = 100; cavebot.UH_MANA_MIN = 100
s = Swiat(); b = zrob(s); tick(s, b, 3)
sprawdz("1c domyślnie tryb uh: UH F7 100 'adura vita'", WYWOLANIA == [("zrob", "F7", 100, "adura vita")], WYWOLANIA)
reset(); cavebot.UH_AKTYWNY = 1; s = Swiat(); s.mana = 90; b = zrob(s); tick(s, b, 3)
sprawdz("1d domyślnie mana 90 < UH_MANA_MIN 95: bez rzutu (próg bez zmian)", not WYWOLANIA, WYWOLANIA)
reset(); cavebot.UH_AKTYWNY = 1; s = Swiat(); s.mana = 96; b = zrob(s); tick(s, b, 3)
sprawdz("1e domyślnie mana 96 >= 95: rzut", len(WYWOLANIA) == 1, WYWOLANIA)
# pokrętła GFB bez wyboru nic nie zmieniają
reset(); cavebot.UH_AKTYWNY = 1; cavebot.UH_GFB_KLAWISZ = "F8"; cavebot.UH_GFB_KOSZT = 130; cavebot.UH_GFB_PRZERWA_S = 600
s = Swiat(); b = zrob(s); tick(s, b, 3)
sprawdz("1f UH_GFB_* przy wyborze domyslna nie działają", WYWOLANIA == [("zrob", "F6", 70, "adori gran")], WYWOLANIA)
WYNIKI.append(dict(RA)); s.t += 30; b.uh_ostatni = float("-inf"); b.czar_ostatni = float("-inf"); tick(s, b, 1)
sprawdz("1g nieudany_cast przy domyslna: pauza GFB nie działa (brak wydłużenia)", b.uh_wylaczony_do - b.zegar() < 100, b.uh_wylaczony_do - b.zegar())

# 2. WYBÓR GFB: czar, klawisz, koszt; UH_CZAR/UH_KLAWISZ/UH_KOSZT nietknięte
reset(); cavebot.UH_AKTYWNY = 1; cavebot.UH_RUNA_WYBOR = "gfb"; cavebot.UH_GFB_KLAWISZ = "F8"
s = Swiat(); b = zrob(s); tick(s, b, 3)
sprawdz("2a GFB: rzut F8, 120 many, 'adori gran flam'", WYWOLANIA == [("zrob", "F8", 120, "adori gran flam")], WYWOLANIA)
sprawdz("2b stałe trybu nietknięte", (cavebot.UH_CZAR, cavebot.UH_KLAWISZ, cavebot.UH_KOSZT) == ("adori gran", "F6", 70))
sprawdz("2c log: robię runę adori gran flam", any("robię runę adori gran flam" in l for l in LOGI))
# mana: koszt 120 podnosi próg ponad UH_MANA_MIN=95
reset(); cavebot.UH_AKTYWNY = 1; cavebot.UH_RUNA_WYBOR = "gfb"; cavebot.UH_GFB_KLAWISZ = "F8"
s = Swiat(); s.mana = 119; b = zrob(s); tick(s, b, 3)
sprawdz("2d GFB mana 119 < 120: bez rzutu", not WYWOLANIA, WYWOLANIA)
s.mana = 120; b.uh_czeka_ts = -1e9; tick(s, b, 3)
sprawdz("2e GFB mana 120: rzut", len(WYWOLANIA) == 1 and WYWOLANIA[0][2] == 120, WYWOLANIA)
# UH_GFB_KOSZT jako pokrętło
reset(); cavebot.UH_AKTYWNY = 1; cavebot.UH_RUNA_WYBOR = "gfb"; cavebot.UH_GFB_KLAWISZ = "F9"; cavebot.UH_GFB_KOSZT = 100
s = Swiat(); s.mana = 110; b = zrob(s); tick(s, b, 3)
sprawdz("2f UH_GFB_KOSZT=100, mana 110 >= max(100, min(95,125)): rzut z kosztem 100", WYWOLANIA == [("zrob", "F9", 100, "adori gran flam")], WYWOLANIA)
# UH_MANA_MIN (istniejące pokrętło) nadal podnosi próg GFB (zapas na exurę)
reset(); cavebot.UH_AKTYWNY = 1; cavebot.UH_RUNA_WYBOR = "gfb"; cavebot.UH_GFB_KLAWISZ = "F8"; cavebot.UH_MANA_MIN = 145
s = Swiat(); s.mana = 125; b = zrob(s); tick(s, b, 3)
sprawdz("2g UH_MANA_MIN 145, max_mana 125: próg = max(120, min(145,125)) = 125, mana 125 rzuca", len(WYWOLANIA) == 1, WYWOLANIA)

# 3. GFB bez klawisza: nie rzuca (nigdy innym klawiszem), jedna linia w logu; restore tarczy działa
reset(); cavebot.UH_AKTYWNY = 1; cavebot.UH_RUNA_WYBOR = "gfb"; s = Swiat(); b = zrob(s); n0 = len(LOGI); tick(s, b, 5)
sprawdz("3a GFB bez UH_GFB_KLAWISZ: zero rzutów, zero kliknięć F6", not WYWOLANIA and "F6" not in s.klawisze, (WYWOLANIA, s.klawisze))
sprawdz("3b dokładnie jedna linia o braku klawisza", sum("UH_GFB_KLAWISZ jest pusty" in l for l in LOGI[n0:]) == 1, LOGI[n0:])
reset(); cavebot.UH_AKTYWNY = 0; cavebot.UH_RUNA_WYBOR = "gfb"
cavebot.UH_STAN_PLIK.write_text(json.dumps({"tarcza_id": 3426}))
s = Swiat(); b = zrob(s); tick(s, b, 4)
sprawdz("3c restore tarczy działa mimo GFB bez klawisza", ("przywroc",) in WYWOLANIA and not any(w[0] == "zrob" for w in WYWOLANIA), WYWOLANIA)

# 4. UH_W_WALCE: próg many w walce liczy koszt wybranej runy
reset(); cavebot.UH_W_WALCE = 1; cavebot.UH_W_WALCE_MANA_MARGINES = 60
s = Swiat(); s.mana = 100; b = zrob(s); g = G0(s)
sprawdz("4a domyślnie: walka ok przy mana 100 (próg max(70, 125-60))", b._uh_walka_ok(g) is True)
cavebot.UH_RUNA_WYBOR = "gfb"; cavebot.UH_GFB_KLAWISZ = "F8"
sprawdz("4b GFB: walka NIE przy mana 100 (próg 120)", b._uh_walka_ok(g) is False)
g["mana"] = 120
sprawdz("4c GFB: walka ok przy mana 120", b._uh_walka_ok(g) is True)
cavebot.UH_W_WALCE = 0

# 5. nieudany rzut GFB (podejrzenie braku soul): pauza UH_GFB_PRZERWA_S
reset(); cavebot.UH_AKTYWNY = 1; cavebot.UH_RUNA_WYBOR = "gfb"; cavebot.UH_GFB_KLAWISZ = "F8"; cavebot.UH_GFB_PRZERWA_S = 0
s = Swiat(); b = zrob(s); WYNIKI.append(dict(RA)); tick(s, b, 3)
sprawdz("5a PRZERWA_S=0: tylko dotychczasowy limit (1/3 porażek, bez pauzy)", b.uh_porazki == 1 and b.uh_wylaczony_do - b.zegar() < 100, (b.uh_porazki, b.uh_wylaczony_do - b.zegar()))
reset(); cavebot.UH_AKTYWNY = 1; cavebot.UH_RUNA_WYBOR = "gfb"; cavebot.UH_GFB_KLAWISZ = "F8"; cavebot.UH_GFB_PRZERWA_S = 300
s = Swiat(); b = zrob(s); WYNIKI.append(dict(RA)); tick(s, b, 3)
sprawdz("5b PRZERWA_S=300: pauza ok. 300 s po nieudanym rzucie", 250 < b.uh_wylaczony_do - b.zegar() <= 300, b.uh_wylaczony_do - b.zegar())
sprawdz("5c log o podejrzeniu braku soul", any("GFB bez efektu" in l for l in LOGI), LOGI[-4:])
n = len(WYWOLANIA); tick(s, b, 20)
sprawdz("5d w pauzie bez kolejnych rzutów", len(WYWOLANIA) == n, WYWOLANIA)
reset(); cavebot.UH_AKTYWNY = 1; cavebot.UH_RUNA_WYBOR = "gfb"; cavebot.UH_GFB_KLAWISZ = "F8"; cavebot.UH_GFB_PRZERWA_S = 300
s = Swiat(); b = zrob(s); WYNIKI.append({"wynik": "przerwane", "powod": "brak_miejsca na gotową runę", "alarm": False, "czas_s": 3.0, "rzuty": 1}); tick(s, b, 3)
sprawdz("5e inna porażka (nie nieudany_cast): bez pauzy GFB", b.uh_wylaczony_do - b.zegar() < 100, b.uh_wylaczony_do - b.zegar())
reset(); cavebot.UH_AKTYWNY = 1; cavebot.UH_RUNA_WYBOR = "gfb"; cavebot.UH_GFB_KLAWISZ = "F8"; cavebot.UH_GFB_PRZERWA_S = 300
s = Swiat(); b = zrob(s); tick(s, b, 3)
sprawdz("5f udany rzut GFB: zero porażek, bez pauzy", b.uh_porazki == 0 and b.uh_wylaczony_do - b.zegar() < 100)

# 6. tryby, przykład, okno
TR = json.loads((KAT / "tryby.json").read_text())
sprawdz("6a tryby runy/uh/stoj nie ustawiają wyboru runy ani GFB",
        not any(k.startswith(("UH_RUNA_WYBOR", "UH_GFB")) for t in TR.values() if isinstance(t, dict) for k in t.get("pokretla", {})))
PRZ = json.loads((KAT / "na_zywo.przyklad.json").read_text())
sprawdz("6b na_zywo.przyklad.json: GFB z wartościami domyślnymi",
        PRZ.get("UH_RUNA_WYBOR") == "domyslna" and PRZ.get("UH_GFB_KLAWISZ") == "" and PRZ.get("UH_GFB_KOSZT") == 120
        and PRZ.get("UH_GFB_PRZERWA_S") == 0 and PRZ.get("SERWIS_JEDZENIE_DOWOLNE") == 0, {k: PRZ.get(k) for k in ("UH_RUNA_WYBOR", "UH_GFB_KOSZT")})
ok6, bl6 = pokretla.waliduj({k: PRZ[k] for k in ("UH_RUNA_WYBOR", "UH_GFB_KLAWISZ", "UH_GFB_KOSZT", "UH_GFB_PRZERWA_S", "SERWIS_JEDZENIE_DOWOLNE") if k in PRZ})
sprawdz("6c wpisy przykładu przechodzą walidację", len(ok6) == 5 and not bl6, (ok6, bl6))
import okno_api
def _okno6d():
    try:
        return (okno_api.grupa_pokretla("UH_RUNA_WYBOR") == "Leczenie i runy" and okno_api.grupa_pokretla("UH_GFB_KLAWISZ") == "Leczenie i runy"
                and okno_api.grupa_pokretla("UH_GFB_KOSZT") == "Leczenie i runy" and okno_api.grupa_pokretla("SERWIS_JEDZENIE_DOWOLNE") == "Wyprawa i serwis"
                and okno_api.typ_pokretla("UH_RUNA_WYBOR", {}) == "tekst" and okno_api.typ_pokretla("SERWIS_JEDZENIE_DOWOLNE", {"SERWIS_JEDZENIE_DOWOLNE": 0}) == "przelacznik"
                and all(okno_api.opisy_pokretel().get(k) for k in ("UH_RUNA_WYBOR", "UH_GFB_KLAWISZ", "UH_GFB_KOSZT", "UH_GFB_PRZERWA_S", "SERWIS_JEDZENIE_DOWOLNE")))
    except Exception:  # noqa: BLE001
        return False
sprawdz("6d okno: nowe pokrętła w grupie 'Leczenie i runy' / 'Wyprawa i serwis', typ i opis", _okno6d())
sprawdz("6e okno zna runę GFB w statusie (3191)", okno_api.RUNY_NAZWY.get(3191) == "GFB")

# 7. rozpoznanie runy GFB (3191) w serwisie i wyprawie; UH/HMM bez zmian
import serwis_akcje as SA, wyprawa as W
sprawdz("7a ID_RUNY_BAGU zawiera GFB oraz dotychczasowe blank/UH/HMM", getattr(SA, "ID_GFB", None) == 3191 and {3147, 3160, 3198, 3191} <= set(SA.ID_RUNY_BAGU))
sprawdz("7b worek z przewagą GFB jest runowy, bez GFB i bez run nie",
        SA._runowy({"przedmioty": [{"id": 3191, "ilosc": 1}] * 3 + [{"id": 3147, "ilosc": 1}]}) is True
        and SA._runowy({"przedmioty": [{"id": 3582, "ilosc": 4}] * 3}) is False)
sprawdz("7c wyprawa: ID_DEPO_ZLOZ = UH + GFB", set(W.ID_DEPO_ZLOZ) == {3160, 3191})

print(f"\n{sum(ok)}/{len(ok)} OK" if all(ok) else f"\n{sum(ok)}/{len(ok)} FAIL")
sys.exit(0 if all(ok) else 1)
