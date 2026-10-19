"""Watchdog ślepoty (slepota.py, SLEPOTA_DIAG_S / SLEPOTA_RESTART_S). Offline: bez gry, bota, sesji i gniazd.

Odtwarza 19.10 (Jointoramix, gobliny z9): 21:32:56-21:36:40 i 21:39:41-21:45:47 lista stworów miała tylko postać, exp stał,
stan IDZ. Czego dowodzi: (a) takie okno daje "diag" po 120 s i "restart" po 240 s, (b) normalna łowiecka przerwa
(exp rośnie co 20-80 s) nic nie wywołuje, (c) wypad/przerwa/UH resetują okno, (d) bez wcześniejszego expa (dojście na łowisko)
nic nie wywołuje, (e) widziany potwór odsuwa alarm, (f) diagnostyka najwyżej raz na 10 min, restart najwyżej raz na 15 min,
(g) pokrętło 0 = wyłączone, (h) zrzuc() nigdy nie rzuca i zapisuje JSON z surową listą ze strażnika, (i) pokrętła są w
cavebot.py i w pokretla.ZAKRESY."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(_os.path.dirname(_os.path.abspath(__file__))).parent))
import bot  # noqa: E402
import cavebot  # noqa: E402
import pokretla  # noqa: E402
import slepota  # noqa: E402

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


def przebieg(det, zdarzenia, t0=0.0, krok=5.0):
    """zdarzenia: lista (od_s, do_s, exp, stan, n_potworow); zwraca [(t, wynik)] niepuste."""
    wyniki = []
    t = t0
    for od, do, exp, stan, n in zdarzenia:
        t = t0 + od
        while t < t0 + do:
            w = det.probka(t, exp, stan, n)
            if w:
                wyniki.append((round(t - t0), w))
            t += krok
    return wyniki


# (a) scenariusz 19.10: bot poluje 20 s (ostatni przyrost expa w t=20), potem ślepota 440 s
det = slepota.Detektor(120, 240)
zd = [(0, 5, 1000, "IDZ", 1), (5, 20, 1025, "WALKA", 1), (20, 60, 1050, "IDZ", 0)]
zd += [(60, 460, 1050, "IDZ", 0)]
w = przebieg(det, zd)
sprawdz("a1 diag po ok. 120 s ślepoty", any(x[1] == "diag" and 135 <= x[0] <= 150 for x in w), w)
sprawdz("a2 restart po ok. 240 s ślepoty", any(x[1] == "restart" and 255 <= x[0] <= 270 for x in w), w)
sprawdz("a3 dokładnie jeden diag i jeden restart", [x[1] for x in w] == ["diag", "restart"], w)

# (b) normalne łowienie: exp co 20-80 s, 0 potworów między zabiciami
det = slepota.Detektor(120, 240)
zd, exp, t = [], 1000, 0
for dl in (30, 80, 20, 60, 70, 40, 90, 50):
    zd.append((t, t + dl, exp, "IDZ", 0))
    t += dl
    exp += 25
    zd.append((t, t + 5, exp, "WALKA", 1))
    t += 5
sprawdz("b normalne łowienie nic nie wywołuje", przebieg(det, zd) == [], przebieg(slepota.Detektor(120, 240), zd))

# (c) wypad / przerwa / UH resetują okno
for stan in ("WYPAD", "PRZERWA", "UH", "WPADNIECIE"):
    det = slepota.Detektor(120, 240)
    zd = [(0, 10, 1000, "IDZ", 1), (10, 20, 1025, "IDZ", 0), (20, 700, 1025, stan, 0)]
    sprawdz(f"c {stan}: długi brak expa bez alarmu", przebieg(det, zd) == [])

# (d) dojście na łowisko: exp nie rósł jeszcze ani razu w tym procesie
det = slepota.Detektor(120, 240)
sprawdz("d brak wcześniejszego expa: bez alarmu", przebieg(det, [(0, 600, 1000, "IDZ", 0)]) == [])

# (e) potwór widziany co 100 s odsuwa alarm (exp stoi, ale to nie ślepota)
det = slepota.Detektor(120, 240)
zd = [(0, 10, 1000, "IDZ", 1), (10, 20, 1025, "IDZ", 0)]
for k in range(8):
    zd.append((20 + k * 100, 20 + k * 100 + 5, 1025, "WALKA", 1))
    zd.append((25 + k * 100, 120 + k * 100, 1025, "IDZ", 0))
sprawdz("e widziany potwór odsuwa alarm", przebieg(det, zd) == [], przebieg(slepota.Detektor(120, 240), zd))

# (f) limity: długa ślepota (1500 s) = najwyżej jeden diag/restart w oknie, drugi restart dopiero po 15 min
det = slepota.Detektor(120, 240)
zd = [(0, 10, 1000, "IDZ", 1), (10, 20, 1025, "IDZ", 0), (20, 2000, 1025, "IDZ", 0)]
w = przebieg(det, zd)
restarty = [x[0] for x in w if x[1] == "restart"]
sprawdz("f restart najwyżej co 15 min", len(restarty) >= 2 and restarty[1] - restarty[0] >= 900, w)
diagi = [x[0] for x in w if x[1] == "diag"]
sprawdz("f diag najwyżej co 10 min", all(b - a >= 600 for a, b in zip(diagi, diagi[1:])), w)

# (g) pokrętła 0 = wyłączone
det = slepota.Detektor(0, 0)
sprawdz("g SLEPOTA_DIAG_S=0: nic", przebieg(det, [(0, 10, 1000, "IDZ", 1), (10, 20, 1025, "IDZ", 0), (20, 900, 1025, "IDZ", 0)]) == [])
det = slepota.Detektor(120, 0)
w = przebieg(det, [(0, 10, 1000, "IDZ", 1), (10, 20, 1025, "IDZ", 0), (20, 900, 1025, "IDZ", 0)])
sprawdz("g SLEPOTA_RESTART_S=0: tylko diag, bez restartu", w and all(x[1] == "diag" for x in w), w)

# (h) zrzuc(): nie rzuca, zapisuje surową listę ze strażnika
surowa = [{"id": 1, "nazwa": "Jointoramix", "x": 1, "y": 2, "z": 9, "hp": 100, "gracz": True, "adres": "0x1"},
          {"id": 2, "nazwa": "Goblin", "x": 3, "y": 2, "z": 9, "hp": 100, "gracz": False, "adres": "0x2", "kopie": [[3, 2, 9, "0x9"]]}]
_zap0 = bot._zapytaj_surowe


def zap(z):
    if z["cmd"] == "stwory":
        return {"stwory": surowa}
    if z["cmd"] == "gracz":
        return {"gracz": {"hp": 245, "max_hp": 245, "exp": 1025}}
    raise RuntimeError("brak komendy")


class CB:
    stan, exp_teraz, idx = "IDZ", 1025, 126
    stwory_surowe = [surowa[0]]


bot._zapytaj_surowe = zap
komunikaty = []
with tempfile.TemporaryDirectory() as tmp:
    plik = slepota.zrzuc(Path(tmp) / "slepota", "diag", CB(), 130, log=komunikaty.append)
    d = json.loads(plik.read_text()) if plik else {}
bot._zapytaj_surowe = _zap0
sprawdz("h1 zrzuc zapisuje JSON", plik is not None and d.get("powod") == "diag")
sprawdz("h2 cb widzi 0 potworów, strażnik 1 (to jest dowód ślepoty)",
        d.get("cb_stwory", {}).get("poza_graczem") == 0 and d.get("straznik_stwory", {}).get("poza_graczem") == 1, d)
sprawdz("h3 kopie wpisu zachowane w zrzucie", d.get("straznik_stwory", {}).get("wpisy", [{}, {}])[1].get("kopie") == [[3, 2, 9, "0x9"]], d)
sprawdz("h4 brak komendy w strażniku = zapis błędu, nie wyjątek", str(d.get("straznik_pozycja", "")).startswith("błąd"), d.get("straznik_pozycja"))
sprawdz("h5 log zawiera ŚLEPOTA", any("ŚLEPOTA" in m for m in komunikaty), komunikaty)
sprawdz("h6 zrzuc z niepoprawnym katalogiem nie rzuca", slepota.zrzuc("/proc/nie/ma", "diag", CB(), 1, log=lambda *_: None) is None)

# (i) pokrętła
sprawdz("i1 stałe w cavebot.py", cavebot.SLEPOTA_DIAG_S == 120 and cavebot.SLEPOTA_RESTART_S == 0,
        (cavebot.SLEPOTA_DIAG_S, cavebot.SLEPOTA_RESTART_S))
sprawdz("i2 pokrętła w ZAKRESY", "SLEPOTA_DIAG_S" in pokretla.ZAKRESY and "SLEPOTA_RESTART_S" in pokretla.ZAKRESY)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
