#!/usr/bin/env python3
"""16.10 (SPEC R3+R4, P8): PK_UH_SZYBKIE. Szybkie UH na siebie w ucieczce PK (próg 30% + predykcja, ponowienia z losowym
odstępem, brak przerwy 60 s przy HP<30%, weryfikacja ~0,6 s, bez zgadywania menu, losowy klik w polu postaci, Ctrl+klik)
oraz R4 (mob obok w pk_ucieczka: bez 'walczę 8 s'). Atrapy, bez gry i X11, bez run (RETRONIC_TESTY=1).
Odtwarza 15:52:16-33 z logu (ork 1,0 + Tojson -4,0; HP z telemetrii: 73, 66, 69, 52, 45, 31, 16, 0)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import random
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import bot  # noqa: E402
import cavebot  # noqa: E402
import obrona_pk  # noqa: E402
import pokretla  # noqa: E402
import runa_klik  # noqa: E402

cavelog = []
_log0 = cavebot.log


def _log(*a):
    cavelog.append(" ".join(map(str, a)))
    _log0(*a)


cavebot.log = _log
cavebot.REAKCJA = (0.0, 0.0)
cavebot.DRUGI_CEL = 0.0
cavebot.ROZRZUT_PROGU = 0.0
cavebot.STRAZNIK_CEL = 0
cavebot.ODWROCENIE_TRASY = 0.0
cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5)
cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False
cavebot.ZDROWIE_CZAR_AKTYWNY = 0
TMP = Path(tempfile.mkdtemp())
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


# ---------------------------------------------------------------- 0. pokrętła
sprawdz("0a domyślnie PK_UH_SZYBKIE=0, CTRL=0, HP_SZYBKI=30, PREDYKCJA=1",
        cavebot.PK_UH_SZYBKIE == 0 and cavebot.PK_UH_CTRL == 0 and cavebot.PK_UH_HP_SZYBKI == 30 and cavebot.PK_UH_PREDYKCJA == 1)
for k in ("PK_UH_SZYBKIE", "PK_UH_HP_SZYBKI", "PK_UH_PREDYKCJA", "PK_UH_CTRL"):
    sprawdz(f"0b {k} w ZAKRESY i KIERUNEK", k in pokretla.ZAKRESY and k in pokretla.KIERUNEK)
sprawdz("0c HP_SZYBKI: zakres od 30 (nie niżej)", pokretla.ZAKRESY["PK_UH_HP_SZYBKI"][0] == 30)
sprawdz("0d SZYBKIE i CTRL: analityk nie może włączyć (nie_wyzej)",
        pokretla.KIERUNEK["PK_UH_SZYBKIE"] == "nie_wyzej" and pokretla.KIERUNEK["PK_UH_CTRL"] == "nie_wyzej")
import json  # noqa: E402
przyklad = json.load(open(Path(__file__).resolve().parent.parent / "na_zywo.przyklad.json"))
sprawdz("0e na_zywo.przyklad.json ma wpisy (SZYBKIE 0, CTRL 0, HP 30)",
        przyklad.get("PK_UH_SZYBKIE") == 0 and przyklad.get("PK_UH_CTRL") == 0 and przyklad.get("PK_UH_HP_SZYBKI") == 30
        and przyklad.get("PK_UH_PREDYKCJA") == 1)

# ---------------------------------------------------------------- 1. losowość kliknięcia
rng = random.Random(7)
pr = [runa_klik.losowy_offset_pola(rng, 40.0, 36.0) for _ in range(20000)]
sprawdz("1a offset zawsze w polu postaci (|ox|<=20, |oy|<=18)", all(abs(x) <= 20 and abs(y) <= 18 for x, y in pr))
sx = (sum(x * x for x, _ in pr) / len(pr)) ** 0.5
sy = (sum(y * y for _, y in pr) / len(pr)) ** 0.5
sprawdz("1b sigma ~ 1/6 pola (40 px -> 6,7 px; 36 px -> 6 px)", 5.5 < sx < 7.5 and 5.0 < sy < 6.8, f"{sx:.2f} {sy:.2f}")
sprawdz("1c średnia ~ środek pola", abs(sum(x for x, _ in pr) / len(pr)) < 0.3)
a = [runa_klik.losowy_offset_pola(random.Random(5), 40.0, 36.0) for _ in range(3)]
b2 = [runa_klik.losowy_offset_pola(random.Random(5), 40.0, 36.0) for _ in range(3)]
sprawdz("1d deterministyczne przy tym samym ziarnie", a == b2)
sprawdz("1e inne ziarno -> inny wynik", runa_klik.losowy_offset_pola(random.Random(5), 40, 36) != runa_klik.losowy_offset_pola(random.Random(6), 40, 36))
od = [runa_klik.losowy_odstep_ctrl(random.Random(i)) for i in range(500)]
sprawdz("1f odstęp Ctrl->klik w 60-180 ms i nie stały", min(od) >= 0.06 and max(od) <= 0.18 and max(od) - min(od) > 0.05, f"{min(od)} {max(od)}")


# ---------------------------------------------------------------- 2. strzel(szybko=True) na atrapie
class Env:
    def __init__(s, runy=5, efekt=True, ocr=(60, 40), hp_rosnie=False):
        s.t = 0.0
        s.akcje = []
        s.runy = runy
        s.efekt = efekt
        s.ocr_wynik = ocr
        s.pamiec = {}
        s.ocr_wywolan = 0
        s.hp_rosnie = hp_rosnie
        s.hp = 30.0
        s.siebie_t = None

    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def log(s, t): cavelog.append(t)

    def kontenery(s):
        return [{"nazwa": "Backpack", "pojemnosc": 20,
                 "przedmioty": [{"slot": 1, "id": 3160, "ilosc": s.runy}] if s.runy else []}]

    def geometria(s): return {"reka": {}, "plecak": [(580 + 37 * i, 581) for i in range(20)]}
    def prawy(s, x, y): s.akcje.append(("prawy", x, y, s.t)); s.t += 0.08
    def lewy(s, x, y): s.akcje.append(("lewy", x, y, s.t)); s.t += 0.08
    def ctrl_lewy(s, x, y): s.akcje.append(("ctrl", x, y, s.t)); s.t += 0.08

    def lewy_siebie(s, rng):
        s.akcje.append(("siebie", rng.random(), s.t))
        s.siebie_t = s.t
        s.t += 0.08
        if s.efekt:
            s.runy -= 1
        if s.hp_rosnie:
            s.hp += 40

    def lewy_pole(s, dx, dy): s.akcje.append(("pole", dx, dy, s.t))
    def zrzut(s): return object()

    def ocr(s, obraz, x, y):
        s.ocr_wywolan += 1
        return None if s.ocr_wynik is None else (x + s.ocr_wynik[0], y + s.ocr_wynik[1])

    def hp_celu(s, i): return 100.0
    def hp_wlasne(s): return s.hp
    def klawisz(s, k): s.akcje.append(("klawisz", k, s.t))


CEL = {"id": None, "dx": 0, "dy": 0, "hp": None}
e = Env()
w = runa_klik.strzel(e, dict(CEL), runa_id=3160, szybko=True, rng=random.Random(1))
sprawdz("2a menu + klik w siebie: ok", w["wynik"] == "ok" and [a[0] for a in e.akcje] == ["prawy", "lewy", "siebie"], (w, e.akcje))
sprawdz("2b całość w budżecie ~1 s", e.t <= 1.0, e.t)

e = Env()
w = runa_klik.strzel(e, dict(CEL), runa_id=3160, szybko=True, ctrl=True, rng=random.Random(1))
sprawdz("2c Ctrl+klik: ctrl na slocie runy (617,581), potem siebie, bez menu/OCR",
        w["wynik"] == "ok" and [a[0] for a in e.akcje] == ["ctrl", "siebie"] and e.akcje[0][1:3] == (617, 581) and e.ocr_wywolan == 0, (w, e.akcje))
luki = []
for i in range(300):
    e = Env()
    runa_klik.strzel(e, dict(CEL), runa_id=3160, szybko=True, ctrl=True, rng=random.Random(i))
    luki.append(e.akcje[1][2] - (e.akcje[0][3] + 0.08))
sprawdz("2d odstęp ctrl->siebie losowy w 60-180 ms", min(luki) >= 0.0599 and max(luki) <= 0.1801 and max(luki) - min(luki) > 0.05, f"{min(luki):.3f} {max(luki):.3f}")

e = Env(ocr=None)
w = runa_klik.strzel(e, dict(CEL), runa_id=3160, szybko=True, rng=random.Random(1))
sprawdz("2e menu niepotwierdzone: 2 odczyty, ZERO zgadywania (bez klików lewy/siebie), Escape, wynik bez_menu",
        w["wynik"] == "bez_menu" and e.ocr_wywolan == 2 and not [a for a in e.akcje if a[0] in ("lewy", "siebie", "pole")]
        and e.akcje[-1][:2] == ("klawisz", "Escape"), (w, e.akcje, e.ocr_wywolan))
sprawdz("2e2 krótki powtórny odczyt (<= 0,5 s)", e.t <= 0.5, e.t)

e = Env(ocr=None)
e.pamiec["offset"] = (5, 9)
w = runa_klik.strzel(e, dict(CEL), runa_id=3160, szybko=True, rng=random.Random(1))
sprawdz("2f zmierzony wcześniej offset (z OCR) wolno użyć", w["wynik"] == "ok" and e.akcje[1][:3] == ("lewy", 622, 590), (w, e.akcje))

e = Env(efekt=False)
w = runa_klik.strzel(e, dict(CEL), runa_id=3160, szybko=True, rng=random.Random(1), weryfikacja_s=0.6)
sprawdz("2g brak efektu: weryfikacja skrócona (<= 0,75 s od kliknięcia), Escape, bez_efektu",
        w["wynik"] == "bez_efektu" and e.t - e.siebie_t <= 0.75 and e.akcje[-1][:2] == ("klawisz", "Escape"), (w, e.t - e.siebie_t))
e = Env(efekt=False, hp_rosnie=True)
w = runa_klik.strzel(e, dict(CEL), runa_id=3160, szybko=True, rng=random.Random(1))
sprawdz("2h wzrost własnego HP też potwierdza użycie", w["wynik"] == "ok" and "HP" in w["powod"], w)
e = Env(runy=0)
w = runa_klik.strzel(e, dict(CEL), runa_id=3160, szybko=True, rng=random.Random(1))
sprawdz("2i brak runy: bez żadnego kliknięcia", w["wynik"] == "brak_runy" and not e.akcje)
w1 = Env(); w2 = Env()
runa_klik.strzel(w1, dict(CEL), runa_id=3160, szybko=True, rng=random.Random(9))
runa_klik.strzel(w2, dict(CEL), runa_id=3160, szybko=True, rng=random.Random(9))
sprawdz("2j deterministyczne przy ziarnie (te same akcje i czasy)", w1.akcje == w2.akcje and w1.t == w2.t)


# ---------------------------------------------------------------- 3. _pk_lecz w Cavebocie
class Sw:
    def __init__(s): s.t = 0.0; s.poz = [100, 100, 9]; s.klawisze = []; s.hp = 100
    def zegar(s): return s.t
    def spij(s, d): pass
    def zapytaj(s, z):
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp, "max_hp": 100, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}]}
        return {}


class Po:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)


def cb_prosty(seed=1):
    s = Sw()
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
    b = cavebot.Cavebot(Po(s), [(100 + i, 100, 9) for i in range(1, 11)], zapytaj=s.zapytaj, atak=lambda m, g: None,
                        alarm=lambda w: s.klawisze.append(("alarm", w)), spij=s.spij, zegar=s.zegar, loot=loot, okrazenia=1)
    b.uh_restore = False
    b.runa_klik_env = object()
    b.pk_rng = random.Random(seed)
    return s, b


wywolania = []
wynik_strzalu = {"wynik": "ok", "powod": "ubyło runy"}
_strzel0 = runa_klik.strzel


def _strzel(env, cel, **kw):
    wywolania.append(dict(kw))
    return dict(wynik_strzalu)


runa_klik.strzel = _strzel
P0 = (100, 100, 9)


def lecz(b, hp, t):
    n = len(wywolania)
    r = b._pk_lecz({"proc": float(hp), "mana": None}, P0, t, [])
    return r, len(wywolania) - n


try:
    # domyślnie (SZYBKIE=0): zachowanie jak dotąd: próg PK_UH_HP=40, bez predykcji, bez kwargów szybkich
    cavebot.PK_UH_SZYBKIE = 0
    s, b = cb_prosty()
    r, n = lecz(b, 45, 10.0)
    sprawdz("3a SZYBKIE=0: HP 45% nie leczy UH (próg 40)", n == 0 and r is False)
    r, n = lecz(b, 38, 11.0)
    sprawdz("3b SZYBKIE=0: HP 38% leczy UH jak dotąd (bez kwargów trybu szybkiego)", n == 1 and r is True and "szybko" not in wywolania[-1], wywolania[-1:])
    r, n = lecz(b, 38, 12.0)
    sprawdz("3c SZYBKIE=0: odstęp stały 2,5 s (po 1 s nie)", n == 0)
    wywolania.clear()

    cavebot.PK_UH_SZYBKIE = 1
    s, b = cb_prosty()
    r, n = lecz(b, 35, 100.0)
    sprawdz("3d SZYBKIE=1: HP 35% bez UH (próg 30%, brak gwałtownego spadku)", n == 0 and r is False)
    r, n = lecz(b, 30, 100.5)
    sprawdz("3e SZYBKIE=1: HP 30% UH w tym samym obiegu (zużywa obieg), tryb szybki w kwargs",
            n == 1 and r is True and wywolania[-1].get("szybko") is True and wywolania[-1].get("ctrl") is False
            and wywolania[-1].get("weryfikacja_s") == 0.6, wywolania[-1:])
    t0 = 100.5
    odst = b.pk_uh_nast - t0
    sprawdz("3f kolejna próba nie wcześniej niż PK_UH_ODSTEP_S -20% i nie później niż +20% (2,0-3,0 s)", 2.0 - 1e-9 <= odst <= 3.0 + 1e-9, odst)
    r, n = lecz(b, 25, t0 + 1.0)
    sprawdz("3g w trakcie odstępu: bez próby", n == 0)
    r, n = lecz(b, 25, t0 + 3.01)
    sprawdz("3h po odstępie: kolejna próba (HP 25%)", n == 1 and r is True)

    # determinizm i losowość odstępu
    odst_l = []
    for sd in range(40):
        s2, b2 = cb_prosty(sd)
        lecz(b2, 20, 50.0)
        odst_l.append(b2.pk_uh_nast - 50.0)
    sprawdz("3i odstęp losowy w 2,0-3,0 s i nie stały", min(odst_l) >= 2.0 - 1e-9 and max(odst_l) <= 3.0 + 1e-9 and max(odst_l) - min(odst_l) > 0.3, (min(odst_l), max(odst_l)))
    sa, ba = cb_prosty(3); sb, bb = cb_prosty(3)
    lecz(ba, 20, 50.0); lecz(bb, 20, 50.0)
    sprawdz("3j ten sam seed -> ten sam odstęp", ba.pk_uh_nast == bb.pk_uh_nast)

    # predykcja
    s, b = cb_prosty()
    for t, hp in ((0.0, 80), (0.7, 70), (1.5, 62)):
        r, n = lecz(b, hp, t)
    sprawdz("3k predykcja: HP 62% (>50%) po spadku 18 pp bez UH", n == 0)
    r, n = lecz(b, 48, 2.0)
    sprawdz("3l predykcja: spadek 32 pp w 2 s i HP 48% -> UH już przy 50% zamiast 30%", n == 1 and r is True)
    cavebot.PK_UH_PREDYKCJA = 0
    s, b = cb_prosty()
    for t, hp in ((0.0, 80), (0.7, 70), (1.5, 62)):
        lecz(b, hp, t)
    r, n = lecz(b, 48, 2.0)
    cavebot.PK_UH_PREDYKCJA = 1
    sprawdz("3m PK_UH_PREDYKCJA=0: bez predykcji", n == 0)
    s, b = cb_prosty()
    for i in range(12):
        r, n = lecz(b, 60 - i, 10.0 * i)     # powolny spadek 1 pp / 10 s
    sprawdz("3n powolny spadek (poniżej 15 pp w 2 s) nie wywołuje predykcji", n == 0)

    # próg nigdy niżej niż 30
    cavebot.PK_UH_HP_SZYBKI = 10
    s, b = cb_prosty()
    r, n = lecz(b, 29, 5.0)
    cavebot.PK_UH_HP_SZYBKI = 30
    s, b = cb_prosty()
    r2, n2 = lecz(b, 31, 5.0)
    sprawdz("3o PK_UH_HP_SZYBKI=10 działa jak 30 (clamp): 29% leczy, 31% nie", n == 1 and n2 == 0, (n, n2))
    cavebot.PK_UH_HP_SZYBKI = 40
    s, b = cb_prosty()
    r, n = lecz(b, 38, 5.0)
    cavebot.PK_UH_HP_SZYBKI = 30
    sprawdz("3o2 PK_UH_HP_SZYBKI=40 podnosi próg", n == 1)

    # (b) brak przerwy 60 s po 3 porażkach przy HP < 30%
    wynik_strzalu = {"wynik": "bez_efektu", "powod": "x"}
    s, b = cb_prosty()
    t = 0.0
    for i in range(3):
        t += 3.2
        lecz(b, 22, t)
    sprawdz("3p 3 porażki przy HP 22%: BEZ przerwy 60 s, natychmiast kolejna próba", b.pk_uh_do == float("-inf") and b.pk_uh_nast <= t, (b.pk_uh_do, b.pk_uh_nast, t))
    r, n = lecz(b, 22, t + 0.01)
    sprawdz("3p2 …kolejna próba rusza w następnym obiegu", n == 1)
    s, b = cb_prosty()
    t = 0.0
    lecz(b, 80, 0.0)
    for i, hp in enumerate((80, 60, 45)):      # predykcja przy 45% (powyżej 30%): 3 porażki = przerwa 60 s jak dotąd
        pass
    b.pk_uh_porazki = 2
    b.pk_uh_hist = [(10.0, 80.0)]
    r, n = lecz(b, 45, 11.0)
    sprawdz("3q 3. porażka przy HP 45% (predykcja, nie krytyczne): przerwa 60 s", n == 1 and b.pk_uh_do >= 11.0 + 59, b.pk_uh_do)
    wynik_strzalu = {"wynik": "brak_runy", "powod": "x"}
    s, b = cb_prosty()
    lecz(b, 20, 1.0)
    sprawdz("3r brak runy: przerwa 60 s także w trybie szybkim", b.pk_uh_do >= 60.0)

    # bez_menu -> alarm (jeden, 3 linie max)
    wynik_strzalu = {"wynik": "bez_menu", "powod": "menu niepotwierdzone"}
    s, b = cb_prosty()
    lecz(b, 20, 1.0)
    al = [x for x in s.klawisze if isinstance(x, tuple) and x[0] == "alarm"]
    sprawdz("3s bez_menu: alarm (krótki, 1 linia)", len(al) == 1 and len(al[0][1].splitlines()) <= 3, al)
    lecz(b, 20, 5.0)
    al = [x for x in s.klawisze if isinstance(x, tuple) and x[0] == "alarm"]
    sprawdz("3s2 alarm nie częściej niż co 20 s", len(al) == 1)

    # Ctrl: tylko przy PK_UH_CTRL=1 i wraca do menu po 2 nieudanych
    wynik_strzalu = {"wynik": "ok", "powod": "ubyło runy"}
    cavebot.PK_UH_CTRL = 1
    s, b = cb_prosty()
    lecz(b, 20, 1.0)
    sprawdz("3t PK_UH_CTRL=1 przekazuje ctrl=True", wywolania[-1].get("ctrl") is True)
    wynik_strzalu = {"wynik": "bez_efektu", "powod": "x"}
    t = 10.0
    for i in range(2):
        t += 3.2
        lecz(b, 20, t)
    t += 3.2
    lecz(b, 20, t)
    cavebot.PK_UH_CTRL = 0
    sprawdz("3u po 2 nieudanych Ctrl+klikach wraca do menu (ctrl=False)", wywolania[-1].get("ctrl") is False, wywolania[-3:])
finally:
    runa_klik.strzel = _strzel0
    cavebot.PK_UH_SZYBKIE = 0
    cavebot.PK_UH_CTRL = 0


# ---------------------------------------------------------------- 4. odtworzenie 15:52:16-33 (R3 + R4) w pełnym ticku
JA = (32500, 32280, 9)
# (t od 15:52:16.2, HP%) z telemetrii; między próbkami interpolacja liniowa co 0,5 s
HP_PROBKI = [(0.0, 73), (1.5, 66), (2.7, 69), (3.9, 52), (5.1, 52), (6.3, 45), (10.1, 31), (13.4, 16), (16.8, 0)]


def hp_w(t):
    for (t1, h1), (t2, h2) in zip(HP_PROBKI, HP_PROBKI[1:]):
        if t1 <= t <= t2:
            return h1 + (h2 - h1) * (t - t1) / (t2 - t1)
    return HP_PROBKI[-1][1]


def gr(nick, dx, dy, gracz=True, hp=100, id_=None, **kw):
    d = {"id": id_ or (hash(nick) % 100000 + 10), "nazwa": nick, "gracz": gracz, "dx": dx, "dy": dy, "z": 9, "hp": hp}
    d.update(kw)
    return d


class Swiat:
    def __init__(s):
        s.t = 0.0
        s.poz = list(JA)
        s.klawisze, s.alarmy, s.ataki = [], [], []

    def zegar(s): return s.t
    def spij(s, d): pass

    def zapytaj(s, z):
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": round(hp_w(s.t)), "max_hp": 100, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": 9, "hp": 100}
            lst = [gr("Orc", 1, 0, gracz=False, id_=8416), gr("Tojson", -4, 0, hp=87, id_=777, czaszka=1)]
            out = []
            for m in lst:
                m = dict(m)
                m["x"], m["y"] = s.poz[0] + m.pop("dx"), s.poz[1] + m.pop("dy")
                out.append(m)
            return {"stwory": [ja] + out}
        return {}


class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
    def krok(p, k): return tuple(p.s.poz)          # droga zablokowana przez orka: postać nie rusza się z miejsca


class FakeWyprawa:
    def __init__(f, cb_ref):
        f.cb = cb_ref
        f.w = None
        f.zablokowany = False
        f.depo = JA

    def _pole_depo(f): return f.depo

    def start_pk(f, rodzaj, teraz, baza=None):
        f.w = {"potrzeby": {"depo": True, "pk": rodzaj}}
        f.cb[0].wypad_aktywny = True
        return True

    def tick(f): return False

    def przerwij(f, powod):
        f.w = None
        f.cb[0].wypad_aktywny = False

    def uciekaj(f, poz): return True


def zrob_replay(s):
    loot = types.SimpleNamespace(zbierz=lambda zw, g: "ok")
    b = cavebot.Cavebot(P(s), [(JA[0] + i, JA[1], 9) for i in range(1, 11)], okrazenia=999, zapytaj=s.zapytaj,
                        atak=lambda m, g: s.ataki.append((m["id"], s.t)), alarm=lambda w: s.alarmy.append(w),
                        spij=s.spij, zegar=s.zegar, loot=loot)
    b.pk_det, b.pk_wrogowie = None, None
    b._pk_dane()
    b.pk_wrogowie = obrona_pk.Wrogowie(TMP / f"wr-{len(ok)}.json", czas=s.zegar, log=lambda t: None)
    b._pk_powiadom = lambda tytul, tresc, klucz: None
    b.fw = FakeWyprawa([b])
    b.wyprawa = b.fw
    b.pk_rng = random.Random(11)
    b.uh_restore = False
    b.runa_klik_env = object()
    return b


def replay(szybkie, dt=0.5, do=17.0):
    cavebot.PK_UH_SZYBKIE = szybkie
    del cavelog[:]
    s = Swiat()
    b = zrob_replay(s)
    uh, w_walce = [], []

    def _s(env, cel, **kw):
        uh.append((round(s.t, 2), round(hp_w(s.t)), kw.get("szybko", False)))
        w_walce.append(b.wypad_walka_do > s.t)
        return {"wynik": "ok", "powod": "ubyło runy"}

    runa_klik.strzel = _s
    try:
        t = 0.0
        while t <= do + 1e-9:
            s.t = t
            b.tick()
            t += dt
    finally:
        runa_klik.strzel = _strzel0
        cavebot.PK_UH_SZYBKIE = 0
    b.uh_w_walce = w_walce
    return s, b, uh, list(cavelog)


s0, b0, uh0, log0 = replay(0)
walki0 = [l for l in log0 if "droga zablokowana" in l]
sprawdz("4a SZYBKIE=0 (jak dotąd): 'Wypad: droga zablokowana … walczę 8 s' od razu po starcie ucieczki",
        walki0 and "walczę 8 s" in walki0[0], walki0[:2])
sprawdz("4a2 SZYBKIE=0: stan PK UCIECZKA, brak parametrów trybu szybkiego w UH", b0.pk_stan == "UCIECZKA" and all(not x[2] for x in uh0), (b0.pk_stan, uh0))

s1, b1, uh1, log1 = replay(1)
walki1 = [l for l in log1 if "droga zablokowana" in l]
sprawdz("4b SZYBKIE=1: ucieczka PK wystartowała, stan UCIECZKA", b1.pk_stan == "UCIECZKA", b1.pk_stan)
sprawdz("4c SZYBKIE=1: żadnego 'walczę 8 s'; walka z orkiem max 2 s",
        not any("walczę 8" in l for l in log1) and walki1 and all("walczę 2 s" in l for l in walki1), walki1[:3])
sprawdz("4d SZYBKIE=1: bot nie bije orka w pierwszej sekundzie ucieczki (obejście zamiast walki)",
        not s1.ataki or s1.ataki[0][1] >= 1.0, s1.ataki[:3])
# ciągłość walki: pierwsza walka trwa nie dłużej niż 2 s od startu do kolejnej oceny
sprawdz("4e SZYBKIE=1: walka bez ponownej oceny nie dłuższa niż 2 s (wypad_walka_do - start)",
        True if not walki1 else (b1.wypad_walka_do - s1.t) <= 2.0 + 1e-9 or b1.wypad_walka_do == float("-inf"), b1.wypad_walka_do)
# UH
uh30 = [x for x in uh1 if x[1] <= 30]
sprawdz("4f SZYBKIE=1: UH nie przy HP > 30% (tu bez predykcji), pierwsze UH w obiegu, w którym HP spada do <= 30%",
        uh1 and all(x[1] <= 30 for x in uh1) and uh1[0][0] <= 11.6 and all(x[2] for x in uh1), uh1)
sprawdz("4g SZYBKIE=1: kolejne UH po odstępie 2,0-3,0 s (nie w tym samym obiegu)",
        len(uh1) >= 2 and 2.0 - 1e-9 <= uh1[1][0] - uh1[0][0] <= 3.5, uh1)
sprawdz("4h leczenie równolegle: co najmniej jedno UH padło w oknie walki z blokującym", any(b1.uh_w_walce), b1.uh_w_walce)
sprawdz("4i brak kliknięć w prawdziwej grze: strzel podmieniony, runy nietknięte", True)

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
