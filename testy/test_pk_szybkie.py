#!/usr/bin/env python3
"""16.10 (P6/R2): PK_SZYBKIE. Reakcja na PK nie czeka na dźwięk alarmu ani na model.
Odtwarza sekwencję 15:52:08-33 (logi/telemetria-20261016.jsonl, logi/mozg-20261016-1259.log; t=0 -> 15:52:08, Tojson z białą
czaszką rozpoznany o t=4, HP 100 -> 73 -> 45 -> 16 od t=8) na atrapach, bez gry, X11 i prawdziwego modelu (runy nie są używane).
Dowód przyczyny: w logu po każdym 'ALARM:' mija dokładnie +4 s (paplay timeout=4 w cavebot.alarm_dzwiekowy), a model wołany jest
w wątku (mozg._watek_modelu). Atrapy: alarm = sleep 4 s (jak zawieszony paplay), model = sleep 4 s."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import bot  # noqa: E402,F401
import cavebot  # noqa: E402
import mozg  # noqa: E402
import obrona_pk  # noqa: E402
import pokretla  # noqa: E402
import json  # noqa: E402

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
OPOZNIENIE_S = 4.0          # zawieszony paplay / wolny model (jak w logu: 4,0 s)


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


JA = (32500, 32280, 9)


def mob(nazwa, dx, dy, hp, gracz=False, id_=None, **kw):
    return dict({"id": id_ or (abs(hash(nazwa)) % 90000 + 10), "nazwa": nazwa, "gracz": gracz, "dx": dx, "dy": dy, "z": 9, "hp": hp}, **kw)


def klatki():
    """(t, hp%, mana, stwory względem postaci) wg telemetrii 15:52:08-33 (t = sekundy od 15:52:08)."""
    k = []
    orcs = lambda h: [mob("Orc", 0, -1, h, id_=8416), mob("Orc", 1, -1, 100, id_=8417)]
    k.append((0.0, 100, 57, orcs(59)))
    k.append((1.3, 100, 58, orcs(59) + [mob("Tojson", -4, 5, 87, True, id_=777)]))
    k.append((2.4, 100, 58, orcs(29) + [mob("Tojson", -4, 3, 87, True, id_=777)]))
    k.append((3.5, 100, 58, orcs(29) + [mob("Tojson", -4, 1, 87, True, id_=777)]))
    sk = dict(czaszka=True)             # 15:52:12 model rozpoznał białą czaszkę (czaszka_grozna)
    k.append((4.5, 100, 58, orcs(29) + [mob("Tojson", -4, 1, 87, True, id_=777, **sk)]))
    k.append((8.2, 73, 59, [mob("Orc", 1, 0, 100, id_=8416), mob("Tojson", -4, 0, 87, True, id_=777, **sk)]))
    k.append((9.3, 67, 59, [mob("Orc", 1, 0, 100, id_=8416), mob("Tojson", -4, 0, 87, True, id_=777, **sk)]))
    k.append((12.0, 53, 35, [mob("Orc", 1, 0, 100, id_=8416), mob("Tojson", -4, 0, 87, True, id_=777, **sk)]))
    k.append((14.0, 45, 35, [mob("Orc", 1, 1, 45, id_=8416), mob("Tojson", -4, 1, 87, True, id_=777, **sk)]))
    k.append((25.0, 16, 10, [mob("Orc", 1, -1, 28, id_=8416), mob("Tojson", -4, 1, 87, True, id_=777, **sk)]))
    return k


class Swiat:
    def __init__(s, kl):
        s.t = 0.0
        s.kl = kl
        s.poz = list(JA)
        s.klawisze, s.alarmy, s.ataki = [], [], []
        s.alarm_start = []

    def klatka(s):
        k = s.kl[0]
        for x in s.kl:
            if x[0] <= s.t:
                k = x
        return k

    def zegar(s):
        return s.t

    def spij(s, d):
        pass

    def zapytaj(s, z):
        _, hp, mana, st = s.klatka()
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": hp, "max_hp": 100, "mana": mana, "max_mana": 245}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Mastafian", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            out = []
            for m in st:
                m = dict(m)
                m["x"], m["y"] = s.poz[0] + m.pop("dx"), s.poz[1] + m.pop("dy")
                out.append(m)
            return {"stwory": [ja] + out}
        return {}


class P:
    nazwa = "Mastafian"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        return tuple(p.s.poz)

    def klawisz(p, k):
        p.s.klawisze.append((k, p.s.t))

    def krok(p, k):
        return tuple(p.s.poz)


class FakeWyprawa:
    def __init__(f, ref):
        f.cb, f.w, f.zablokowany, f.wywolania = ref, None, False, []

    def start_pk(f, rodzaj, teraz, baza=None):
        f.wywolania.append((rodzaj, teraz))
        f.w = {"potrzeby": {"depo": True, "pk": rodzaj}}
        f.cb[0].wypad_aktywny = True
        return True

    def tick(f):
        return False

    def przerwij(f, powod):
        f.w = None

    def uciekaj(f, poz):
        return True


def zrob(s, knob, wolny_alarm=True):
    cavebot.PK_SZYBKIE = knob

    def alarm(w):
        s.alarm_start.append(time.monotonic())
        if wolny_alarm:
            time.sleep(OPOZNIENIE_S)            # zawieszony paplay (timeout=4 w alarm_dzwiekowy)
        s.alarmy.append(w)

    def atak(m, g):
        s.ataki.append((m["id"], s.t))

    loot = types.SimpleNamespace(zbierz=lambda zw, g: "ok")
    punkty = [(JA[0] + i, JA[1], 9) for i in range(1, 11)]
    b = mozg.CavebotMozgu(P(s), punkty, okrazenia=999, zapytaj=s.zapytaj, atak=atak, alarm=alarm,
                          spij=s.spij, zegar=s.zegar, loot=loot)
    b._pk_dane()
    b.pk_wrogowie = obrona_pk.Wrogowie(TMP / f"wrogowie-{len(ok)}-{knob}.json", czas=s.zegar, log=lambda t: None)
    b.powiadomienia = []
    b._pk_powiadom = lambda tytul, tresc, klucz: b.powiadomienia.append((tytul, tresc, klucz))
    b.fw = FakeWyprawa([b])
    b.wyprawa = b.fw
    return b


class Model:
    """Atrapa Haiku: odpowiada po OPOZNIENIE_S s i zawsze chce pauzy (jak w logu 15:52:16)."""

    def __init__(m, opoznienie=OPOZNIENIE_S):
        m.n, m.opoznienie = 0, opoznienie

    def __call__(m, prompt, obraz=None):
        m.n += 1
        time.sleep(m.opoznienie)
        return '{"mysl":"gracz z czaszką, wstrzymuję","akcje":[{"typ":"pauza_bota","sekundy":60}]}', {"duration_ms": 1}


def zrob_mozg(s, b, model):
    logi = []
    mz = mozg.Mozg("hybryda", zapytaj=s.zapytaj, nazwa="Mastafian", model=model, cb=b,
                   pamiec=mozg.Pamiec(TMP / f"pamiec-{len(ok)}.json"), log=lambda *a: logi.append(" ".join(map(str, a))),
                   zegar=s.zegar, czat_wyslij=lambda t: None, trasy=lambda: ["x"], losuj=lambda a, c: a,
                   alarm=lambda w: None, czytnik_czaszki=None)
    mz.logi = logi
    return mz


def odtworz(s, b, mz, do=26.0, krok=0.5):
    """Ticki bota i obiegi mózgu co `krok` s zegara atrapy; -> (pierwsze t PK, najdłuższy czas jednego obiegu w s rzeczywistych)."""
    pierwsze, maks, t = None, 0.0, 0.0
    while t <= do + 1e-9:
        s.t = t
        r0 = time.monotonic()
        b.tick()
        if mz is not None:
            mz.obieg_hybrydy()
        maks = max(maks, time.monotonic() - r0)
        if pierwsze is None and b.pk_stan is not None:
            pierwsze = t
        t += krok
    return pierwsze, maks


def czekaj_na_watki(mz, limit=OPOZNIENIE_S + 3):
    t0 = time.monotonic()
    while mz.watek is not None and mz.watek.is_alive() and time.monotonic() - t0 < limit:
        time.sleep(0.05)


# --- 0. pokrętło: domyślnie 0, w ZAKRESY, w przykładzie, tylko w dół ---
przyklad = json.loads((Path(__file__).resolve().parent.parent / "na_zywo.przyklad.json").read_text())
src = (Path(__file__).resolve().parent.parent / "cavebot.py").read_text()
sprawdz("0 pokrętło PK_SZYBKIE: w kodzie domyślnie 0, w ZAKRESY, w przykładzie 0, nie_wyzej",
        "\nPK_SZYBKIE = 0 " in src and "PK_SZYBKIE" in pokretla.ZAKRESY and przyklad.get("PK_SZYBKIE") == 0
        and pokretla.KIERUNEK.get("PK_SZYBKIE") == "nie_wyzej")

# --- 1. PK_SZYBKIE=0 (kontrola, zachowanie jak dziś): alarm blokuje obieg o czas dźwięku ---
s = Swiat(klatki())
b = zrob(s, 0)
t0 = time.monotonic()
s.t = 4.5
b.tick()                                   # pierwszy obieg z rozpoznaną czaszką
blok0 = time.monotonic() - t0
sprawdz("1 PK_SZYBKIE=0: obieg startu PK trwa tyle co alarm (>= 3,5 s) - odtworzony martwy czas 15:52:12-16",
        blok0 >= OPOZNIENIE_S - 0.5 and b.pk_stan == "UCIECZKA", f"{blok0:.2f} s stan={b.pk_stan}")
sprawdz("1a PK_SZYBKIE=0: brak exury w obiegu startu (leczenie dopiero w następnym)", not s.klawisze, f"{s.klawisze}")

# --- 2. PK_SZYBKIE=1: ten sam start PK w < 0,3 s, ucieczka + leczenie + nick do wrogów w tym samym obiegu ---
s = Swiat(klatki())
b = zrob(s, 1)
s.t = 3.5
b.tick()                                   # Tojson 4 pola, jeszcze bez odczytu czaszki
sprawdz("2a przed rozpoznaniem czaszki (t=3,5), HP 100%: bez PK", b.pk_stan is None)
s.t = 8.2                                  # HP 73% w klatce z czaszką (pierwsza próbka po zacięciu w logu)
t0 = time.monotonic()
b.tick()
czas = time.monotonic() - t0
nicki = {v["nick"] for v in b.pk_wrogowie.dane.values()}
sprawdz("2 PK_SZYBKIE=1: obieg startu PK < 0,3 s mimo zawieszonego alarmu (4 s)", czas < 0.3 and b.pk_stan == "UCIECZKA", f"{czas:.2f} s")
sprawdz("2b w tym samym obiegu: start_pk('ucieczka') + nick do wrogów + exura (HP 73%)",
        b.fw.wywolania[:1] == [("ucieczka", 8.2)] and "Tojson" in nicki and [k for k, _ in s.klawisze] == ["F2"],
        f"{b.fw.wywolania} {nicki} {s.klawisze}")
sprawdz("2c alarm PK poszedł (w wątku, bez czekania na koniec)", s.alarm_start and not s.alarmy, f"{s.alarm_start} {s.alarmy}")
time.sleep(OPOZNIENIE_S + 0.3)
sprawdz("2d alarm w wątku kończy się sam (dźwięk zagrany do końca)", len(s.alarmy) == 1, f"{s.alarmy}")

# --- 3. pełna sekwencja 15:52:08-33 z atrapą modelu 4 s: pętla nie blokowana > 0,3 s w stanie PK ---
s = Swiat(klatki())
b = zrob(s, 1)
mdl = Model()
mz = zrob_mozg(s, b, mdl)
mz.zdarzenia.gracze(["Tojson"])            # zdarzenie obcy_gracz (nowy gracz w widoku, t=0)
pierwsze, maks = odtworz(s, b, mz)
czekaj_na_watki(mz)
sprawdz("3 pełna sekwencja, PK_SZYBKIE=1: żaden obieg (tick + mózg) nie trwa > 0,3 s", maks < 0.3, f"maks={maks:.2f} s")
sprawdz("3a start PK w pierwszym obiegu po rozpoznaniu czaszki (t=4,5), nie o 4 s później", pierwsze == 4.5, f"pierwsze={pierwsze}")
s.t = 26.5
mz.obieg_hybrydy()                         # odbiór spóźnionej decyzji modelu (pauza_bota na 60 s, 4 s po fakcie)
sprawdz("3b zdarzenie z t=0 (przed PK) poszło do modelu w WĄTKU (pętla > 0,3 s nie stanęła), a spóźnione pauza_bota odrzucone: bot nie wstrzymany",
        mdl.n == 1 and b.wstrzymany_do is None and any("ignoruję pauza_bota" in l for l in mz.logi)
        and any("Decyzja [obcy_gracz]" in l for l in mz.logi), f"n={mdl.n} wstrz={b.wstrzymany_do} {mz.logi[-4:]}")

# --- 3c. obcy_gracz zgłoszony już w PK-alarmie (zdarzenie po starcie ucieczki): bez wywołania modelu, bez pauzy ---
s = Swiat(klatki())
b = zrob(s, 1, wolny_alarm=False)
mdl = Model()
mz = zrob_mozg(s, b, mdl)
odtworz(s, b, None, do=8.5)
mz.zdarzenia.gracze(["Inny Gracz"])
s.t = 9.0
mz.obieg_hybrydy()
czekaj_na_watki(mz)
sprawdz("3c obcy_gracz po starcie PK: zero wywołań modelu, bot nie wstrzymany", mdl.n == 0 and b.wstrzymany_do is None
        and any("pomijam pytanie modelu o obcego gracza" in l for l in mz.logi), f"n={mdl.n} {mz.logi[-3:]}")

# --- 3d. HP < 50% bez PK-alarmu: też bez modelu ---
s = Swiat([(0.0, 40, 50, [mob("Orc", 1, 0, 100, id_=8416)])])
b = zrob(s, 1, wolny_alarm=False)
b.gracz()                                  # odczyt HP do ostatni_gracz
mdl = Model()
mz = zrob_mozg(s, b, mdl)
mz.zdarzenia.gracze(["Ktos"])
s.t = 1.0
mz.obieg_hybrydy()
czekaj_na_watki(mz)
sprawdz("3d obcy_gracz przy HP 40% (bez PK-alarmu): zero wywołań modelu", mdl.n == 0 and b.pk_stan is None, f"n={mdl.n}")

# --- 3e. kontrola PK_SZYBKIE=0: model jest wołany (w wątku), a pauza_bota wykonana ---
s = Swiat([(0.0, 40, 50, [mob("Orc", 1, 0, 100, id_=8416)])])
b = zrob(s, 0, wolny_alarm=False)
b.gracz()
mdl = Model(opoznienie=0.2)
mz = zrob_mozg(s, b, mdl)
mz.zdarzenia.gracze(["Ktos"])
s.t = 1.0
mz.obieg_hybrydy()
czekaj_na_watki(mz)
mz.obieg_hybrydy()
sprawdz("3e PK_SZYBKIE=0 (jak dotąd): model wołany, pauza_bota wykonana", mdl.n == 1 and b.wstrzymany_do is not None,
        f"n={mdl.n} wstrz={b.wstrzymany_do}")

# --- 4. filtr akcji: pauza_bota i kontynuuj przy HP < 50% albo w PK-alarmie odrzucone z wpisem w logu ---
for opis, hp, pk in (("HP 40% bez PK-alarmu", 40, None), ("HP 100% w PK-alarmie", 100, "UCIECZKA")):
    s = Swiat([(0.0, hp, 50, [mob("Orc", 3, 0, 100, id_=8416)])])
    b = zrob(s, 1, wolny_alarm=False)
    b.gracz()
    b.pk_stan = pk
    mz = zrob_mozg(s, b, Model())
    mz.wykonaj([{"typ": "pauza_bota", "sekundy": 60}, {"typ": "kontynuuj"}], {"czas": s.t})
    sprawdz(f"4 {opis}: pauza_bota odrzucona, wpis w logu", b.wstrzymany_do is None
            and any("ignoruję pauza_bota" in l for l in mz.logi) and any("ignoruję kontynuuj" in l for l in mz.logi), f"{mz.logi}")
s = Swiat([(0.0, 90, 50, [mob("Orc", 3, 0, 100, id_=8416)])])
b = zrob(s, 1, wolny_alarm=False)
b.gracz()
mz = zrob_mozg(s, b, Model())
mz.wykonaj([{"typ": "pauza_bota", "sekundy": 60}], {"czas": s.t})
sprawdz("4c HP 90% bez PK-alarmu: pauza_bota nadal przechodzi (filtr nie rusza zwykłej gry)", b.wstrzymany_do is not None)
s = Swiat([(0.0, 40, 50, [mob("Orc", 3, 0, 100, id_=8416)])])
b = zrob(s, 0, wolny_alarm=False)
b.gracz()
mz = zrob_mozg(s, b, Model())
mz.wykonaj([{"typ": "pauza_bota", "sekundy": 60}], {"czas": s.t})
sprawdz("4d PK_SZYBKIE=0, HP 40%: pauza_bota przechodzi jak dotąd", b.wstrzymany_do is not None)

# --- 5. dane na żywo: czas od czaszki w widoku do startu PK (atrapa, PK_SZYBKIE=1) ---
s = Swiat(klatki())
b = zrob(s, 1)
pierwsze, maks = odtworz(s, b, None, do=9.0)
sprawdz("5 od pierwszej próbki z czaszką (t=4,5) do pk_ucieczka 0,0 s zegara atrapy, start_pk raz",
        pierwsze == 4.5 and [w[1] for w in b.fw.wywolania] == [4.5], f"{pierwsze} {b.fw.wywolania}")

cavebot.PK_SZYBKIE = 0
time.sleep(0.1)
print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
