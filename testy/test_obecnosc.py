#!/usr/bin/env python3
"""15.10: mapa obecności mobów i wybór celu patrolu według respawnu (obecnosc.py), SPEC_patrol_respawn_1015 sekcja 4."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("RETRONIC_TESTY", "1")
sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KAT))

import obecnosc as ob  # noqa: E402

wyniki = []


def sprawdz(nazwa, warunek, info=""):
    wyniki.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + (f"  {info}" if not warunek and info else ""))


CELE = {"troll"}
MIEJSCA = [{"x": 100, "y": 100, "z": 8}, {"x": 140, "y": 100, "z": 8}]


def nowa():
    return ob.MapaObecnosci.dla_miejsc(MIEJSCA, margines=10)


def troll(x, y, z=8):
    return {"nazwa": "Troll", "x": x, "y": y, "z": z, "hp": 100}


# --- 1. geometria: obszar i widok ---
m = nowa()
sprawdz("1a bbox z miejsc + margines", m.bbox == (90, 90, 150, 110), m.bbox)
sprawdz("1b pole poza obszarem i inne piętro nie są w obszarze", not m.w_obszarze(80, 100, 8) and not m.w_obszarze(100, 100, 9))
w = m.komorki_w_widoku((100, 100, 8))
sprawdz("1c komórki w widoku leżą w całości w oknie 15x11 wokół gracza",
        w and all(93 <= cx * 4 and cx * 4 + 3 <= 107 and 95 <= cy * 4 and cy * 4 + 3 <= 105 for cx, cy, _ in w), w)
sprawdz("1d pełne komórki: 15 pól szerokości mieści 3 komórki, 11 pól wysokości 2", len(w) == 6, len(w))
sprawdz("1e gracz na skraju obszaru: tylko komórki w obszarze", all(m._klucz_w_obszarze(k) for k in m.komorki_w_widoku((92, 92, 8))))
sprawdz("1f piętro spoza obszaru: nic nie jest w widoku", m.komorki_w_widoku((100, 100, 12)) == [])

# --- 2. komórka w widoku i pusta = wyczyszczona ---
m = nowa()
m.obserwuj(10.0, (100, 100, 8), [], CELE)
k = m.klucz(100, 100, 8)
c = m.k[k]
sprawdz("2a w widoku i pusta: t_czyste = t, t_widok = t, t_mob brak", c.t_czyste == 10.0 and c.t_widok == 10.0 and c.t_mob is None)
m.obserwuj(11.0, (100, 100, 8), [troll(100, 100)], CELE)
sprawdz("2b mob w komórce: t_mob = t, t_czyste bez zmian", m.k[k].t_mob == 11.0 and m.k[k].t_czyste == 10.0)
m.obserwuj(12.0, (100, 100, 8), [{"nazwa": "Mastafian", "x": 100, "y": 100, "z": 8, "gracz": True}, troll(100, 100, 9),
                                  {"nazwa": "Rat", "x": 100, "y": 100, "z": 8}], CELE)
sprawdz("2c gracz, mob z innego piętra i stwór spoza celów nie liczą się jako mob", m.k[k].t_mob == 11.0 and m.k[k].t_czyste == 12.0)
m.obserwuj(20.0, (140, 100, 8), [], CELE)
sprawdz("2d komórka poza widokiem nie jest aktualizowana", m.k[k].t_widok == 12.0)
brzeg = nowa()
brzeg.obserwuj(5.0, (100, 100, 8), [troll(107, 100)], CELE)      # x=107: komórka 104..107 jest w widoku (<= 107)
brzeg.obserwuj(6.0, (100, 100, 8), [troll(108, 100)], CELE)      # x=108: komórka 108..111 tylko częściowo w widoku
kb = brzeg.klucz(108, 100, 8)
sprawdz("2e mob w komórce tylko częściowo w widoku: t_mob tak, t_czyste nie",
        brzeg.k[kb].t_mob == 6.0 and brzeg.k[kb].t_czyste is None and brzeg.k[kb].czas_widoku == 0.0)

# --- 3. po czasie respawnu wartość rośnie ---
m = nowa()
g = {}
for i in range(0, 600, 2):                                       # 10 minut: troll stoi w komórce (gęstość > domyślna)
    m.obserwuj(float(i), (100, 100, 8), [troll(100, 100), troll(101, 101)], CELE)
k = m.klucz(100, 100, 8)
sprawdz("3a gęstość historyczna rośnie nad domyślną", m.gestosc(k) > 5 * ob.GEST_DOMYSLNA, m.gestosc(k))
m.zabicie(600.0, 100, 100, 8)
m.obserwuj(601.0, (100, 100, 8), [], CELE)                       # troll zabity, komórka pusta
t0 = 601.0
v0, v1, v2, v3 = (m.oczekiwane(k, t0 + dt) for dt in (1.0, 120.0, 300.0, 3000.0))
sprawdz("3b tuż po wyczyszczeniu oczekiwane ~ 0", v0 < 0.05 * m.gestosc(k), v0)
sprawdz("3c oczekiwane rośnie z czasem (monotonicznie)", v0 < v1 < v2 < v3, (v0, v1, v2, v3))
sprawdz("3d długo po wyczyszczeniu zbliża się do gęstości", v3 > 0.95 * m.gestosc(k), (v3, m.gestosc(k)))
sprawdz("3e f: 0 w chwili wyczyszczenia, 1/2 po czasie respawnu, < 1", m.f(0, 300) == 0 and abs(m.f(300, 300) - 0.5) < 1e-9 and m.f(1e6, 300) <= 1.0)
sprawdz("3f komórka z mobem widzianym niedawno = wysoka", nowa().oczekiwane(k, 0) == ob.GEST_DOMYSLNA
        and (lambda mm: (mm.obserwuj(0.0, (100, 100, 8), [troll(100, 100)], CELE), mm.oczekiwane(mm.klucz(100, 100, 8), 5.0))[1])(nowa()) >= ob.MOB_SWIEZY_MIN)
sprawdz("3g brak danych = gęstość domyślna", nowa().oczekiwane((25, 25, 8), 100.0) == ob.GEST_DOMYSLNA)
sprawdz("3h komórka poza obszarem = 0", nowa().oczekiwane((0, 0, 8), 100.0) == 0.0)

# --- 4. zabicie aktualizuje ---
m = nowa()
m.obserwuj(10.0, (100, 100, 8), [troll(101, 101)], CELE)
k = m.klucz(101, 101, 8)
sprawdz("4a zabicie: licznik i czas", m.zabicie(20.0, 101, 101, 8) and m.k[k].zabicia == 1 and m.k[k].t_zab == 20.0)
sprawdz("4b po zabiciu (komórki jeszcze nie widziano pustej) odniesienie = czas zabicia", m.czas_odniesienia(k) == 20.0)
m.zabicie(25.0, 101, 101, 8)
sprawdz("4c drugie zabicie: licznik 2", m.k[k].zabicia == 2)
sprawdz("4d zabicie poza obszarem: ignorowane", m.zabicie(30.0, 5, 5, 8) is False)
m.obserwuj(40.0, (100, 100, 8), [troll(101, 101)], CELE)
sprawdz("4e mob widziany po zabiciu = komórka znów zaludniona (brak odniesienia)", m.czas_odniesienia(k) is None)

# --- 5. respawn z danych ---
m = nowa()
t = 0.0
for ile in (100.0, 200.0, 300.0, 400.0, 500.0):                  # 5 cykli: mob -> pustka trwa `ile` s -> mob wraca
    m.obserwuj(t, (100, 100, 8), [troll(100, 100)], CELE)
    t += 1.0
    m.obserwuj(t, (100, 100, 8), [], CELE)                       # pustka od tego momentu
    t += ile
    m.obserwuj(t, (100, 100, 8), [troll(100, 100)], CELE)        # mob wrócił
    t += 1.0
k = m.klucz(100, 100, 8)
sprawdz("5a 5 przypadków respawnu w komórce", len(m.k[k].przypadki) == 5, m.k[k].przypadki)
sprawdz("5b respawn komórki = mediana przypadków (300 s)", abs(m.respawn(k) - 300.0) < 5, m.respawn(k))
sprawdz("5c komórka bez przypadków: domyślny 300 (brak globalnego)", nowa().respawn((1, 1, 8)) == ob.RESPAWN_DOMYSLNY_S)
mm = nowa()
mm.obserwuj(0.0, (100, 100, 8), [troll(100, 100)], CELE)
mm.obserwuj(1.0, (100, 100, 8), [], CELE)
mm.obserwuj(10.0, (100, 100, 8), [troll(100, 100)], CELE)         # powrót po 9 s: sąsiad z grupy, nie respawn
sprawdz("5d zbyt szybki powrót (< PRZYPADEK_MIN_S) nie jest przypadkiem respawnu", mm.k[mm.klucz(100, 100, 8)].przypadki == [])
mn = nowa()
mn.obserwuj(0.0, (100, 100, 8), [], CELE)
mn.obserwuj(500.0, (100, 100, 8), [troll(100, 100)], CELE)
sprawdz("5e komórka, w której nigdy nie było moba przed pustką: to nie jest wyczyszczenie", mn.k[mn.klucz(100, 100, 8)].przypadki == [])
ma = nowa()
ma.obserwuj(0.0, (100, 100, 8), [troll(100, 100)], CELE)
ma.obserwuj(1.0, (100, 100, 8), [], CELE)
ma.obserwuj(400.0, (100, 100, 8), [troll(100, 100)], CELE)
p = ma.k[ma.klucz(100, 100, 8)].przypadki
sprawdz("5f powrót po przerwie w widoku: przypadek z flagą luki (0)", len(p) == 1 and p[0][1] == 0 and 395 < p[0][0] < 400, p)

# --- 6. zapis / odczyt stanu ---
m = nowa()
for i in range(50):
    m.obserwuj(float(i), (100, 100, 8), [troll(101, 101)] if i % 7 == 0 else [], CELE)
m.zabicie(60.0, 101, 101, 8)
with tempfile.TemporaryDirectory() as d:
    plik = Path(d) / "stan" / "obecnosc.json"
    m.zapisz(plik, 100.0)
    sprawdz("6a zapis: plik JSON istnieje i brak plików tymczasowych", plik.exists() and [f.name for f in plik.parent.iterdir()] == ["obecnosc.json"])
    r = ob.MapaObecnosci.wczytaj(plik, 200.0)
    k = m.klucz(101, 101, 8)
    sprawdz("6b odczyt świeżego stanu: komórki, licznik zabić, t_* i gęstość zachowane",
            r is not None and r.bbox == m.bbox and r.k[k].zabicia == 1 and r.k[k].t_zab == 60.0
            and r.k[k].t_mob == m.k[k].t_mob and abs(r.gestosc(k) - m.gestosc(k)) < 1e-6)
    sprawdz("6c ta sama oczekiwana po odczycie", abs(r.oczekiwane(k, 150.0) - m.oczekiwane(k, 150.0)) < 1e-9)
    st = ob.MapaObecnosci.wczytaj(plik, 100.0 + ob.STAN_STARY_S + 1)
    sprawdz("6d stary stan (> kilka godzin): gęstość zostaje, t_* znikają",
            st is not None and st.k[k].t_mob is None and st.k[k].t_czyste is None and st.k[k].t_zab is None
            and st.k[k].zabicia == 1 and abs(st.gestosc(k) - m.gestosc(k)) < 1e-6)
    sprawdz("6e po starym stanie oczekiwane = gęstość (bez zegara)", abs(st.oczekiwane(k, 1e9) - st.gestosc(k)) < 1e-9)
    plik.write_text("{nie json")
    sprawdz("6f uszkodzony plik: None, bez wyjątku", ob.MapaObecnosci.wczytaj(plik, 1.0) is None)
    sprawdz("6g brak pliku: None", ob.MapaObecnosci.wczytaj(Path(d) / "nie_ma.json", 1.0) is None)
    plik.write_text(json.dumps({"wersja": 99}))
    sprawdz("6h inna wersja stanu: None", ob.MapaObecnosci.wczytaj(plik, 1.0) is None)
    m.zapisz(plik, 1.0)
    m.zapisz(plik, 2.0)
    sprawdz("6i nadpisanie atomowe: nadal jeden plik", [f.name for f in plik.parent.iterdir()] == ["obecnosc.json"])


# --- 7. wybór celu ---
def sciezka(x0, y0, x1, y1, z=8):
    """Prosta lista pól od (x0,y0) do (x1,y1) (bez startu), po osi x potem y."""
    pola, x, y = [], x0, y0
    while x != x1:
        x += 1 if x1 > x else -1
        pola.append((x, y, z))
    while y != y1:
        y += 1 if y1 > y else -1
        pola.append((x, y, z))
    return pola


def ucz_gestosc(mm, poz, ile_s=400, mobow=((0, 0),)):
    """Bot stoi w poz i widzi trolle (gęstość komórek w widoku rośnie)."""
    for i in range(ile_s):
        mm.obserwuj(float(i), poz, [troll(poz[0] + dx, poz[1] + dy, poz[2]) for dx, dy in mobow], CELE)


# A = (100,100) i B = (140,100) w tej samej odległości od bota (120,100); oba z gęstością po 400 s obserwacji
m = nowa()
poz_a, poz_b = (100, 100, 8), (140, 100, 8)
for i in range(0, 400, 2):
    m.obserwuj(float(i), poz_a, [troll(100, 100), troll(102, 98)], CELE)
    m.obserwuj(float(i) + 1.0, poz_b, [troll(140, 100), troll(138, 98)], CELE)
cele = [{"id": "A", "droga": sciezka(120, 100, 101, 100), "dojscie_s": 8.0},
        {"id": "B", "droga": sciezka(120, 100, 139, 100), "dojscie_s": 8.0}]
t_wybor = 1000.0
# B wyczyszczone przed chwilą, A nie widziano 600 s (po zabiciu): dawno niewidziane wygrywa
for dx, dy in ((0, 0), (-2, -2)):
    m.zabicie(t_wybor - 60.0, 140 + dx, 100 + dy, 8)
m.obserwuj(t_wybor - 59.0, poz_b, [], CELE)
m.zabicie(t_wybor - 600.0, 100, 100, 8)
m.zabicie(t_wybor - 600.0, 102, 98, 8)
m.k[m.klucz(100, 100, 8)].t_czyste = t_wybor - 600.0
m.k[m.klucz(102, 98, 8)].t_czyste = t_wybor - 600.0
id_, wart, pew = m.wybierz(cele, t_wybor, prog=0.0)
sprawdz("7a świeżo wyczyszczone miejsce przegrywa z dawno niewidzianym przy podobnej drodze", id_ == "A" and wart["A"] > 2 * wart["B"], (id_, wart))
sprawdz("7b zwrot: (id, wartości wszystkich celów, pewność 0..1)", set(wart) == {"A", "B"} and 0.0 <= pew <= 1.0, (wart, pew))
# po długim czasie B ponownie ma wartość
_, wart2, _ = m.wybierz(cele, t_wybor + 5000.0, prog=0.0)
sprawdz("7c po czasie respawnu świeżo wyczyszczone miejsce odzyskuje wartość", wart2["B"] > 2.5 * wart["B"], (wart, wart2))

# dłuższa droga z mobami po drodze wygrywa z krótką pustą
m = nowa()
for i in range(0, 400, 2):
    m.obserwuj(float(i), (120, 100, 8), [troll(112, 100), troll(128, 100), troll(130, 98)], CELE)   # moby po drodze na wschód
    m.obserwuj(float(i) + 1.0, (100, 100, 8), [], CELE)                                               # zachód: widziany i pusty
# zachód wyczyszczony dawno, ale gęstość tam ~0 (pusta od zawsze); wschód stale zaludniony
cele = [{"id": "krotka_pusta", "droga": sciezka(120, 100, 110, 100), "dojscie_s": 4.0},
        {"id": "dluga_z_mobami", "droga": sciezka(120, 100, 135, 100), "dojscie_s": 7.0}]
id_, wart, pew = m.wybierz(cele, 450.0, prog=0.0)
sprawdz("7d dłuższa droga z mobami po drodze wygrywa z krótką pustą", id_ == "dluga_z_mobami" and wart["dluga_z_mobami"] > wart["krotka_pusta"], (id_, wart))

# brak danych = dzisiejszy wybór (None)
m = nowa()
cele = [{"id": "A", "droga": sciezka(120, 100, 101, 100), "dojscie_s": 8.0},
        {"id": "B", "droga": sciezka(120, 100, 139, 100), "dojscie_s": 8.0}]
id_, wart, pew = m.wybierz(cele, 100.0)
sprawdz("7e brak danych (mapa pusta): None, czyli decyduje dzisiejsza reguła", id_ is None and pew < ob.PEWNOSC_MIN, (id_, pew))
sprawdz("7f brak celów: (None, {}, 0)", nowa().wybierz([], 0.0) == (None, {}, 0.0))
# remis (identyczne miejsca): niska pewność = None
m = nowa()
for i in range(0, 400, 2):
    m.obserwuj(float(i), poz_a, [troll(100, 100)], CELE)
    m.obserwuj(float(i) + 1.0, poz_b, [troll(140, 100)], CELE)
cele_r = [{"id": "A", "droga": sciezka(120, 100, 101, 100), "dojscie_s": 8.0},
          {"id": "B", "droga": sciezka(120, 100, 139, 100), "dojscie_s": 8.0}]
m.obserwuj(500.0, (120, 100, 8), [], CELE)
id_, wart, pew = m.wybierz(cele_r, 500.0)
sprawdz("7g remis (symetria): niska pewność = None", id_ is None, (id_, wart, pew))
# gracz przy komórce obniża wartość
m = nowa()
for i in range(0, 400, 2):
    m.obserwuj(float(i), poz_a, [troll(100, 100)], CELE)
    m.obserwuj(float(i) + 1.0, poz_b, [troll(140, 100)], CELE)
_, w_bez, _ = m.wybierz(cele_r, 500.0, prog=0.0)
_, w_gracz, _ = m.wybierz(cele_r, 500.0, gracze=[(139, 100, 8)], prog=0.0)
sprawdz("7h obcy gracz przy celu B obniża jego wartość, A bez zmian",
        w_gracz["B"] < 0.5 * w_bez["B"] and abs(w_gracz["A"] - w_bez["A"]) < 1e-12, (w_bez, w_gracz))
_, w_inne, _ = m.wybierz(cele_r, 500.0, gracze=[(139, 100, 9)], prog=0.0)
sprawdz("7i gracz na innym piętrze nie obniża wartości", abs(w_inne["B"] - w_bez["B"]) < 1e-12)
# unikalne komórki: ta sama komórka na drodze nie liczy się dwa razy
m = nowa()
for i in range(0, 200, 2):
    m.obserwuj(float(i), poz_a, [troll(100, 100)], CELE)
k = m.klucz(100, 100, 8)
v1 = m.wartosc_celu([k], 20.0, 300.0)
v2 = m.wartosc_celu([k, k, k], 20.0, 300.0)
sprawdz("7j wartość liczy unikalne komórki", abs(v1 - v2) < 1e-12 and v1 > 0)
sprawdz("7k dzielnik ma dolną granicę (czas 0 nie daje nieskończoności)", m.wartosc_celu([k], 0.0, 300.0) == m.wartosc_celu([k], ob.MIN_CZAS_DOJSCIA_S, 300.0))
tylko_dane = nowa()
for i in range(0, 200, 2):
    tylko_dane.obserwuj(float(i), poz_a, [troll(100, 100)], CELE)
sprawdz("7l komórki celu: 4 pola wokół miejsca obejmują sąsiednie komórki", len(tylko_dane.komorki_celu((100, 100, 8))) >= 4)

# --- 8. wydajność: obserwacja w ticku jest tania ---
import time  # noqa: E402
m = nowa()
st = [troll(101, 101), troll(99, 103), troll(104, 98)]
t0 = time.perf_counter()
for i in range(2000):
    m.obserwuj(float(i), (100, 100, 8), st, CELE)
na_tick_ms = (time.perf_counter() - t0) / 2000 * 1000
sprawdz("8a obserwuj() < 0,5 ms na tick", na_tick_ms < 0.5, f"{na_tick_ms:.3f} ms")

# --- 9. CLI: raport z syntetycznej telemetrii, tryb izolowany ---
with tempfile.TemporaryDirectory() as d:
    logi = Path(d) / "logi"
    logi.mkdir()
    t = 1.0e9
    rek = []
    poz = [32493, 32260, 8]
    for i in range(60):
        rek.append({"t": t + i, "typ": "probka", "poz": poz, "stwory": [
            {"n": "Mastafian", "dx": 0, "dy": 0, "odl": 0, "hp": 100, "gracz": True},
            {"n": "Troll", "dx": 3, "dy": 2, "odl": 3, "hp": 100}]})
    rek.append({"t": t + 60.5, "typ": "epizod_celu", "wynik": "zabity", "pos": [32496, 32262]})
    rek.append({"t": t + 61, "typ": "patrol_cel", "id": 2, "x": 32491, "y": 32294, "poz": poz, "droga": 40})
    rek.append({"t": t + 120, "typ": "patrol_cel", "id": 1, "x": 32478, "y": 32290, "poz": poz, "droga": 30})
    rek.append({"t": t + 120, "typ": "patrol_wizyta", "id": 2, "dotarl": True, "dojscie_s": 50.0, "zabicia_miejsce": 0, "zabicia_droga": 2})
    (logi / "telemetria-20991231.jsonl").write_text("\n".join(json.dumps(e) for e in rek) + "\n")
    wyj = Path(d) / "raport.md"
    r = subprocess.run([sys.executable, "-I", str(KAT / "obecnosc.py"), "--raport", "--logi", str(logi), "--wyjscie", str(wyj)],
                       capture_output=True, text=True, timeout=120)
    sprawdz("9a CLI --raport (python -I) kończy się kodem 0", r.returncode == 0, r.stderr[-400:])
    md = wyj.read_text() if wyj.exists() else ""
    sprawdz("9b raport zawiera sekcje gęstość, respawn, symulacja", all(h in md for h in ("## 2. Gęstość", "## 3. Respawn", "## 4. Symulacja")), md[:200])
    sprawdz("9c telemetria tylko do odczytu: plik wejściowy bez zmian", (logi / "telemetria-20991231.jsonl").read_text().count("\n") == len(rek))
    r2 = subprocess.run([sys.executable, "-I", str(KAT / "obecnosc.py"), "--raport", "--logi", str(Path(d) / "pusty"), "--wyjscie", str(wyj)],
                        capture_output=True, text=True, timeout=60)
    sprawdz("9d brak telemetrii: kod 1 z komunikatem, bez wyjątku", r2.returncode == 1 and "Traceback" not in r2.stderr, r2.stderr[-300:])


# DrogiGraf (15.10): drogi po grafie pliku miejsc bez A* (tryb cienia w ticku)
_dg = {"graf": {"wezly": [{"pole": [10, 10, 8]}, {"pole": [20, 10, 8]}, {"pole": [20, 10, 9]}, {"pole": [30, 10, 9]}],
                "odl": [[0, 1, 12], [2, 3, 10]]},
       "przejscia": [{"wejscie_gora": [20, 10, 8], "wyjscie_dol": [20, 10, 9], "wejscie_dol": [20, 10, 9],
                      "wyjscie_gora": [20, 10, 8]}],
       "laczniki": [], "miejsca": [{"id": 1, "x": 20, "y": 10, "z": 8}, {"id": 2, "x": 30, "y": 10, "z": 9},
                                   {"id": 3, "x": 99, "y": 99, "z": 8}]}
_g = ob.DrogiGraf(_dg)
_d = _g.drogi_z((12, 10, 8))
sprawdz("DG1 miejsce na tym samym piętrze: droga i czas z grafu", 1 in _d and _d[1][0][-1] == (20, 10, 8)
        and abs(_d[1][1] - 8 * ob.KROK_S) < 1e-9, _d.get(1))
sprawdz("DG2 miejsce piętro niżej: przez schody (pola na z8 i z9), czas ze schodami",
        2 in _d and {p[2] for p in _d[2][0]} == {8, 9}
        and abs(_d[2][1] - ((8 + 10) * ob.KROK_S + ob.KROK_S + ob.SCHODY_S)) < 1e-9, _d.get(2))
sprawdz("DG3 miejsce spoza grafu: brak klucza", 3 not in _d)
sprawdz("DG4 start dalej niż PROMIEN_STARTU od węzłów: brak dróg", _g.drogi_z((80, 80, 8)) == {})

print(f"WYNIK: {sum(wyniki)} / {len(wyniki)}")
sys.exit(0 if all(wyniki) else 1)
