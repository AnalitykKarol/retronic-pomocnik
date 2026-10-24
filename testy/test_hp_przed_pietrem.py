#!/usr/bin/env python3
"""23.10 (Karol: "Dobrze by było, jakby miał dużo HP"): w dojściu/wypadzie przed przejściem pięter (dziura, lina, schody, drabina, łopata)
postać czeka w miejscu, aż HP >= HP_PRZED_PIETREM (domyślnie 90%), lecząc się (exura), najdłużej HP_PRZED_PIETREM_MAX_S s (potem idzie dalej
z wpisem w logu, bez STOP). Poza dojściem/wypadem i przy gryzącym stworze obok - bez czekania. Atrapy, bez gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
import types

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import cavebot
import pietra
import pokretla
import wypad

logi = []
cavebot.log = lambda *a: logi.append(" ".join(str(x) for x in a))
ok = []


def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not hasattr(cavebot.Cavebot, "_hp_przed_pietrem"):
    print("FAIL brak Cavebot._hp_przed_pietrem (stary kod)")
    print("WYNIK: 0 / 1")
    sys.exit(1)

POZ = (100, 100, 7)


class Zegar:
    t = 1000.0


def cb_(proc=50, mana=100, dojscie=True, wypad_=False, gryzie=False, stwor_blisko=False):
    z = Zegar()
    cb = cavebot.Cavebot.__new__(cavebot.Cavebot)
    cb.__dict__.update(dojscie_aktywne=dojscie, wypad_aktywny=wypad_, stan="IDZ", aktywnosc_ts=0.0,
                       hp_gracza_spadek=(z.t - 0.5) if gryzie else float("-inf"),
                       ostatnie_stwory=[{"nazwa": "Troll", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 100}] if stwor_blisko else [],
                       g_tick={"proc": proc, "mana": mana}, zegar=lambda: z.t, _z=z)
    cb.pauza = lambda a, b=None: setattr(z, "t", z.t + (a if b is None else (a + b) / 2))
    cb.dystans = lambda a, b: max(abs(a[0] - b[0]), abs(a[1] - b[1]))
    return cb


def idz(cb, ile, klucz=(8,), dt=1.0):
    wyn = []
    for _ in range(ile):
        wyn.append(cb._hp_przed_pietrem(POZ, cb._z.t, klucz))
        cb._z.t += dt
    return wyn


# 1. HP 50% w dojściu: czeka; po podniesieniu HP >= 90 kończy z logiem
logi.clear()
cb = cb_(50)
w = idz(cb, 5)
sprawdz("1a HP 50%: czeka (True)", all(w), w)
sprawdz("1b log 'czekam w miejscu przed przejściem pięter'", any("czekam w miejscu przed przejściem pięter" in l for l in logi), logi)
sprawdz("1c stan PAUZA_HP", str(cb.stan) == "PAUZA_HP", cb.stan)
cb.g_tick["proc"] = 92
w = idz(cb, 1)
sprawdz("1d HP 92%: koniec czekania (False)", w == [False], w)
sprawdz("1e log 'koniec czekania'", any("koniec czekania" in l for l in logi), logi)
sprawdz("1f stan wraca z PAUZA_HP", str(cb.stan) == "IDZ", cb.stan)

# 2. wypad też czeka
cb = cb_(50, dojscie=False, wypad_=True)
sprawdz("2 wypad: czeka", idz(cb, 3) == [True] * 3)

# 3. poza dojściem/wypadem: bez czekania
cb = cb_(50, dojscie=False, wypad_=False)
sprawdz("3 zwykła trasa: bez czekania", idz(cb, 3) == [False] * 3)

# 4. limit: po HP_PRZED_PIETREM_MAX_S czeka koniec z logiem 'idę dalej mimo to', nie czeka drugi raz to samo przejście
logi.clear()
cb = cb_(50)
t0 = cb._z.t
n = 0
while cb._hp_przed_pietrem(POZ, cb._z.t, (8,)) and n < 1000:
    cb._z.t += 1.0; n += 1
sprawdz("4a limit ~120 s", 119 <= cb._z.t - t0 <= 124, cb._z.t - t0)
sprawdz("4b log 'idę dalej mimo to'", any("idę dalej mimo to" in l for l in logi), logi[-3:])
sprawdz("4c to samo przejście nie czeka drugi raz", idz(cb, 3) == [False] * 3)
sprawdz("4d inne przejście znów czeka", idz(cb, 1, klucz=(9,)) == [True])
cb.g_tick["proc"] = 95
idz(cb, 1)
cb.g_tick["proc"] = 40
sprawdz("4e po powrocie HP w normę to samo przejście czeka znów", idz(cb, 1) == [True])

# 5. gryzie i stwór obok: walka/ucieczka mają pierwszeństwo - bez czekania
cb = cb_(50, gryzie=True, stwor_blisko=True)
sprawdz("5a gryzie + stwór <= 2 pola: bez czekania", idz(cb, 2, dt=0.1) == [False, False])
cb = cb_(50, gryzie=False, stwor_blisko=True)
sprawdz("5b stwór obok, HP nie spada: czeka", idz(cb, 2) == [True, True])
cb = cb_(50, gryzie=True, stwor_blisko=False)
sprawdz("5c HP spada, brak stworów: czeka", idz(cb, 2, dt=0.1) == [True, True])

# 6. pokrętło 0 = wyłączone; brak odczytu HP = bez czekania
cavebot.HP_PRZED_PIETREM = 0
sprawdz("6a HP_PRZED_PIETREM=0: bez czekania", idz(cb_(50), 2) == [False, False])
cavebot.HP_PRZED_PIETREM = 90
cb = cb_(50); cb.g_tick = {}
sprawdz("6b brak HP w odczycie: bez czekania", idz(cb, 2) == [False, False])

# 7. leczenie w czasie czekania: próg leczenia podniesiony do progu czekania, blokada 'wypad' ominięta; progów ucieczki nie ruszamy
src = open(cavebot.__file__, encoding="utf-8").read()
sprawdz("7a _zdrowie_gotowy zna próg czekania", "HP_PRZED_PIETREM" in src.split("def _zdrowie_gotowy")[1].split("\n    def ")[0])
sprawdz("7b _czar_blokada pomija 'wypad' w czekaniu", "hp_czeka_ts" in src.split("def _czar_blokada")[1].split("\n    def ")[0])
sprawdz("7c _watchdog_wyjatek zna czekanie", "hp_czeka_ts" in src.split("def _watchdog_wyjatek")[1].split("\n    def ")[0])

# 8. pokrętła w ZAKRESY, kierunek bezpieczeństwa, przykład
sprawdz("8a ZAKRESY", all(k in pokretla.ZAKRESY for k in ("HP_PRZED_PIETREM", "HP_PRZED_PIETREM_MAX_S", "BLOKADA_BIJ_KAZDEGO")))
sprawdz("8b kierunek: wyższy próg HP i dłuższe czekanie = bezpieczniej (nie_nizej)",
        pokretla.KIERUNEK.get("HP_PRZED_PIETREM") == "nie_nizej" and pokretla.KIERUNEK.get("HP_PRZED_PIETREM_MAX_S") == "nie_nizej",
        (pokretla.KIERUNEK.get("HP_PRZED_PIETREM"), pokretla.KIERUNEK.get("HP_PRZED_PIETREM_MAX_S")))
import json
pr = json.load(open(_os.path.join(_os.path.dirname(cavebot.__file__), "na_zywo.przyklad.json"), encoding="utf-8"))
sprawdz("8c na_zywo.przyklad.json ma nowe pokrętła", all(k in pr for k in ("HP_PRZED_PIETREM", "HP_PRZED_PIETREM_MAX_S", "BLOKADA_BIJ_KAZDEGO")))

# 9. pietra.Pietra.tick: czekanie przed próbą i przesunięcie zegara (czekanie nie liczy się do PIETRA_MAX_S)
class CbP:
    def __init__(s):
        s.t = 500.0; s.punkty = [(100, 100, 7), (100, 99, 6)]; s.idx = 1; s.mapa = None; s.hp_czekal_s = 0.0
        s.postac = types.SimpleNamespace(nazwa="Ja", pozycja=lambda: POZ); s.wywolania = []; s.czeka = True
        s.pietra_ops = types.SimpleNamespace()

    def zegar(s): return s.t
    def pauza(s, a, b=None): s.t += a

    def _hp_przed_pietrem(s, poz, teraz, klucz):
        s.wywolania.append(klucz)
        if s.czeka:
            s.hp_czekal_s += 5.0
        return s.czeka


pietra.kandydaci = lambda *a, **k: [{"pole": (100, 99, 7), "pewne": True}]
LP = []
cp = CbP()
pt = pietra.Pietra(cp, konf=types.SimpleNamespace(), log=lambda t: LP.append(t))
r = pt.tick(POZ, (100, 99, 6))
sprawdz("9a Pietra.tick: czekanie na HP zużywa obieg (True)", r is True, r)
sprawdz("9b klucz przejścia (z7 -> z6)", cp.wywolania == [(7, 6)], cp.wywolania)
od0 = pt.st["od"]
cp.t += 10
pt.tick(POZ, (100, 99, 6))
sprawdz("9c czas czekania przesuwa początek przejścia (nie liczy się do limitu 150 s)", abs(pt.st["od"] - (od0 + 5.0)) < 0.01, (od0, pt.st["od"]))
sprawdz("9d to samo dla nast (odstęp między próbami)", pt.st["nast"] >= pt.st["od"])

# 10. wypad: _hp_czekaj resetuje pj/postep (bezpiecznik przejścia nie liczy czekania) i przekazuje klucz
st = types.SimpleNamespace(pj=("x",), postep=("y",), cb=types.SimpleNamespace(zegar=lambda: 5.0, _hp_przed_pietrem=lambda p, t, k: True))
r = wypad.Wypad._hp_czekaj(st, POZ, ("dziura", 7, 6))
sprawdz("10a wypad._hp_czekaj: True i reset pj/postep", r is True and st.pj is None and st.postep is None, (r, st.pj, st.postep))
st = types.SimpleNamespace(pj=("x",), postep=("y",), cb=types.SimpleNamespace(zegar=lambda: 5.0, _hp_przed_pietrem=lambda p, t, k: False))
r = wypad.Wypad._hp_czekaj(st, POZ, ("dziura", 7, 6))
sprawdz("10b wypad._hp_czekaj: False nie rusza pj/postep", r is False and st.pj == ("x",) and st.postep == ("y",))
wsrc = open(wypad.__file__, encoding="utf-8").read()
sprawdz("10c haki w _lina, _dziura i schodach", all(k in wsrc for k in ('("lina",', '("dziura",', '("schody",')) and wsrc.count("self._hp_czekaj(") == 3)

print(f"WYNIK: {sum(ok)} / {len(ok)}")
sys.exit(0 if all(ok) else 1)
