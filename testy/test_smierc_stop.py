#!/usr/bin/env python3
"""16.10 (R5/P5, decyzja Karola): SMIERC_STOP. Po zgonie bot nic nie robi: stan MARTWY, jeden STOP, jedno powiadomienie
(nick, czas, miejsce), zero kliknięć i zero modelu. Atrapy bez gry i X11. Odtwarza sekwencję telemetrii 15:52:33
(HP 16 -> 0 bez zmiany pozycji, Orc obok) i 16:02:12 (HP 0 po respawnie w świątyni, pełne HP chwilę wcześniej)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import bot  # noqa: E402
import cavebot  # noqa: E402
import mozg  # noqa: E402

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
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


class Swiat:
    def __init__(s):
        s.t = 0.0
        s.poz = [32500, 32279, 9]
        s.hp = 100
        s.max_hp = 100
        s.orc = True
        s.klawisze, s.ataki, s.zapytania = [], [], []

    def zegar(s):
        return s.t

    def spij(s, d):
        pass

    def zapytaj(s, z):
        s.zapytania.append(z["cmd"])
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp, "max_hp": s.max_hp, "mana": 100, "max_mana": 200, "exp": 1, "level": 8}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            orc = {"id": 8416, "nazwa": "Orc", "gracz": False, "x": s.poz[0] + 1, "y": s.poz[1], "z": s.poz[2], "hp": 28}
            return {"stwory": [ja] + ([orc] if s.orc else [])}
        return {}


class P:
    nazwa = "Mastafian"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        return tuple(p.s.poz)

    def klawisz(p, k):
        p.s.klawisze.append(k)

    def krok(p, k):
        p.s.klawisze.append(k)
        return tuple(p.s.poz)


class Tele:
    def __init__(t):
        t.zd = []

    def zdarzenie(t, typ, **d):
        t.zd.append((typ, d))

    def probka(t, *a, **k):
        return None

    def ruch_tick(t, *a, **k):
        pass


def zrob(s, knob):
    cavebot.SMIERC_STOP = knob
    def atak(m, g):
        s.ataki.append(m["id"])
    loot = types.SimpleNamespace(zbierz=lambda zw, g: "ok")
    punkty = [(32500 + i, 32279, 9) for i in range(1, 11)]
    b = cavebot.Cavebot(P(s), punkty, okrazenia=999, zapytaj=s.zapytaj, atak=atak, alarm=lambda w: None,
                        spij=s.spij, zegar=s.zegar, loot=loot)
    b.stopy, b.pow = [], []
    b._pk_stop = lambda opis: b.stopy.append(opis)             # nie piszemy prawdziwego pliku STOP
    b._pk_powiadom = lambda tytul, tresc, klucz: b.pow.append((tytul, tresc, klucz))
    b.tele = Tele()
    return b


def obiegi(b, s, hps, poz=None):
    """Jeden tick na odczyt HP; zwraca liczbę kliknięć/ataków dodanych w tej serii."""
    k0, a0 = len(s.klawisze), len(s.ataki)
    for hp in hps:
        s.t += 1.0
        s.hp = hp
        if poz and hp in poz:
            s.poz = list(poz[hp])
        b.tick()
    return (len(s.klawisze) - k0) + (len(s.ataki) - a0)


# (a) SMIERC_STOP=0: zachowanie jak dziś, żadnego STOP ani powiadomienia, stan nie jest MARTWY
s = Swiat()
b = zrob(s, 0)
obiegi(b, s, [100, 100, 16, 0, 0, 0, 0])
sprawdz("a0 SMIERC_STOP=0: brak STOP i powiadomienia", not b.stopy and not b.pow and not b.martwy and str(b.stan) != "MARTWY",
        f"{b.stopy} {b.pow} {b.stan}")
sprawdz("a1 SMIERC_STOP=0: brak rekordu 'smierc'", not any(t == "smierc" for t, _ in b.tele.zd))
import json  # noqa: E402
import pokretla  # noqa: E402
przyklad = json.loads((Path(__file__).resolve().parent.parent / "na_zywo.przyklad.json").read_text())
src = (Path(__file__).resolve().parent.parent / "cavebot.py").read_text()
sprawdz("a2 pokrętło: w kodzie domyślnie 0, w ZAKRESY, w przykładzie 0, tylko w dół (nie_wyzej)",
        "\nSMIERC_STOP = 0 " in src and "SMIERC_STOP" in pokretla.ZAKRESY and przyklad.get("SMIERC_STOP") == 0
        and pokretla.KIERUNEK.get("SMIERC_STOP") == "nie_wyzej")

# (b) sekwencja 15:52:33: HP 100 -> ... -> 16 -> 0 bez zmiany pozycji
s = Swiat()
b = zrob(s, 1)
obiegi(b, s, [100, 100, 52, 45, 31, 16])
sprawdz("b0 żywy: bez STOP i powiadomienia", not b.stopy and not b.pow and not b.martwy)
obiegi(b, s, [0])
sprawdz("b1 pierwszy odczyt HP 0 bez przesłanki: jeszcze nie zgon (podejrzenie)", not b.martwy and not b.stopy, f"{b.martwy}")
obiegi(b, s, [0])
sprawdz("b2 drugi odczyt: nadal podejrzenie", not b.martwy and not b.stopy)
obiegi(b, s, [0])
sprawdz("b3 trzeci odczyt: MARTWY, jeden STOP i jedno powiadomienie", b.martwy and str(b.stan) == "MARTWY"
        and len(b.stopy) == 1 and len(b.pow) == 1, f"{b.martwy} {b.stan} {b.stopy} {b.pow}")
sprawdz("b4 powiadomienie: tytuł, nick, czas i miejsce, max 3 linie",
        b.pow[0][0] == "Bot zginął" and "Mastafian" in b.pow[0][1] and "32500,32279,9" in b.pow[0][1]
        and b.pow[0][1].count("\n") <= 2 and b.pow[0][2] == "smierc", b.pow)
sm = [d for t, d in b.tele.zd if t == "smierc"]
sprawdz("b5 telemetria 'smierc': poz, czas, ostatni stan, stwory (Orc obok)", len(sm) == 1
        and sm[0]["poz"] == [32500, 32279, 9] and sm[0]["czas"] and "ostatni_stan" in sm[0]
        and any(m["n"] == "Orc" for m in sm[0]["stwory"]), sm)
zap0, k0 = len(s.zapytania), len(s.klawisze) + len(s.ataki)
obiegi(b, s, [0] * 10)
sprawdz("b6 kolejne obiegi: brak kliknięć, ataków i zapytań do gry", len(s.klawisze) + len(s.ataki) == k0
        and len(s.zapytania) == zap0, f"{len(s.zapytania) - zap0} zapytań")
obiegi(b, s, [100] * 5)
sprawdz("b7 MARTWY jest trwały (także gdy HP wraca): nadal jeden STOP i jedno powiadomienie",
        b.martwy and len(b.stopy) == 1 and len(b.pow) == 1)
sprawdz("b8 nie ma pętli PAUZA_PK / powrotu: stan MARTWY, pk_stan pusty", str(b.stan) == "MARTWY" and b.pk_stan is None, f"{b.stan} {b.pk_stan}")

# model (mozg.py): w stanie MARTWY nie wykonuje akcji gry i nie jest pytany
class Model:
    def __init__(m):
        m.n = 0

    def __call__(m, prompt):
        m.n += 1
        return '{"akcje": [{"typ": "kontynuuj"}]}', {"duration_ms": 1}


mdl = Model()
logi = []
wysl = []
mz = mozg.Mozg("hybryda", zapytaj=s.zapytaj, nazwa="Mastafian", model=mdl, cb=b,
               pamiec=mozg.Pamiec(Path(tempfile.mkdtemp()) / "pamiec.json"), log=lambda *a: logi.append(" ".join(map(str, a))),
               zegar=s.zegar, czat_wyslij=wysl.append, trasy=lambda: ["x"], losuj=lambda a, c: a, alarm=lambda w: None)
mz.decyzje.append({"akcje": [{"typ": "idz_do", "x": 32503, "y": 32279, "z": 9}], "czas": s.t})
k0 = len(s.klawisze)
mz.obieg_hybrydy()
mz.wykonaj([{"typ": "idz_do", "x": 32503, "y": 32279, "z": 9}, {"typ": "napisz_na_czacie", "tekst": "hej"}], {"czas": s.t})
sprawdz("b9 mozg w MARTWY: zero wywołań modelu, decyzje wyczyszczone, brak ruchu i czatu",
        mdl.n == 0 and not mz.decyzje and len(s.klawisze) == k0 and not wysl and (mz.watek is None or not mz.watek.is_alive()),
        f"n={mdl.n} dec={len(mz.decyzje)} wysl={wysl}")
cavebot.SMIERC_STOP = 0
mz.decyzje.append({"akcje": [{"typ": "kontynuuj"}], "czas": s.t})
sprawdz("b10 mozg: przy SMIERC_STOP=0 blokada nieaktywna", mz._martwy() is False)
cavebot.SMIERC_STOP = 1

# (c) pojedynczy fałszywy odczyt HP 0 bez przesłanki nie zabija sesji; dwa też nie
s = Swiat()
b = zrob(s, 1)
obiegi(b, s, [100, 100, 0, 100, 100, 0, 0, 100, 100])
sprawdz("c0 pojedynczy i podwójny glitch HP 0 między odczytami 100: bez STOP, bez MARTWY", not b.martwy and not b.stopy
        and not b.pow, f"{b.martwy} {b.stopy}")
sprawdz("c1 po glitchu bot znów działa (są kliknięcia/ruch)", len(s.klawisze) + len(s.ataki) > 0)
# HP 0 + skok pozycji do świątyni (przesłanka): zgon od razu, w pierwszym odczycie
s = Swiat()
b = zrob(s, 1)
obiegi(b, s, [100, 100])
obiegi(b, s, [0], poz={0: (32351, 32228, 7)})
sprawdz("c2 HP 0 + skok pozycji do świątyni (z7): zgon potwierdzony od razu, miejsce zgonu = ostatnia żywa poz",
        b.martwy and len(b.stopy) == 1 and "32500,32279,9" in b.pow[0][1], f"{b.martwy} {b.pow}")
# brak wiarygodnego odczytu (max_hp 0) nie liczy się jako zgon
s = Swiat()
b = zrob(s, 1)
s.max_hp = 0
obiegi(b, s, [0] * 6)
sprawdz("c3 max_hp 0 (brak odczytu): nie zgon", not b.martwy and not b.stopy)

# (d) respawn z HP 0 (telemetria 16:02:12): po zgonie 100 kolejnych obiegów HP 0 w świątyni, bez pętli powiadomień
s = Swiat()
b = zrob(s, 1)
obiegi(b, s, [100, 100, 16])
obiegi(b, s, [0, 0, 0])
s.poz = [32352, 32230, 7]
obiegi(b, s, [0] * 100)
sprawdz("d0 respawn z HP 0 przez 100 obiegów: nadal jeden STOP i jedno powiadomienie", len(b.stopy) == 1 and len(b.pow) == 1
        and len([t for t, _ in b.tele.zd if t == "smierc"]) == 1, f"{len(b.stopy)} {len(b.pow)}")
sprawdz("d1 po respawnie nie ma kliknięć ani wypraw", not b.pow[1:] and str(b.stan) == "MARTWY")

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
