#!/usr/bin/env python3
"""16.10 (krok A SPEC_model_D3_utkniecia_1015): detektor zawieszki poza walką + rekord `decyzja` D3 i `d3_wynik`.
Atrapy bez gry i X11. Zawieszka = pozycja w promieniu 2 pól >= D3_PROG_S s poza walką, exp bez zmian. Tylko log:
D3_LOG=0 daje rekordów 0, a ruch bota jest taki sam z logiem i bez."""
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
import telemetria  # noqa: E402

wyniki = []


def sprawdz(nazwa, warunek, info=""):
    wyniki.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + (f"  {info}" if not warunek and info else ""))


cavebot.REAKCJA = (0.0, 0.0)
cavebot.DRUGI_CEL = 0.0
cavebot.ROZRZUT_PROGU = 0.0
cavebot.STRAZNIK_CEL = 0
cavebot.ODWROCENIE_TRASY = 0.0
cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5)
cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False
DOMYSLNE = (cavebot.D3_LOG, cavebot.D3_PROG_S, cavebot.D3_ASTAR_MAX)


class Swiat:
    def __init__(s, poz=(100, 100, 7), rusza=True):
        s.t = 0.0
        s.poz = list(poz)
        s.stwory = []
        s.klawisze = []
        s.exp = 1000
        s.rusza = rusza

    def zegar(s):
        return s.t

    def spij(s, d):
        s.t += d

    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0, "exp": s.exp}}
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
        p.s.klawisze.append(k)
        if not p.s.rusza:
            p.s.t += 0.2
            return False                       # postać się nie rusza (zawieszka)
        d = bot.KIERUNKI[k]
        p.s.t += 0.2
        p.s.poz[0] += d[0]
        p.s.poz[1] += d[1]
        return tuple(p.s.poz)


class TeleBlad(telemetria.Telemetria):
    def zdarzenie(self, typ, **d):
        if typ in ("decyzja", "d3_wynik"):
            raise RuntimeError("zepsuty zapis")
        return super().zdarzenie(typ, **d)


def scena(rusza=True, tele_klasa=telemetria.Telemetria, punkty=None):
    s = Swiat(rusza=rusza)
    b = cavebot.Cavebot(P(s), punkty or [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij, zegar=s.zegar, okrazenia=1,
                        loot=types.SimpleNamespace(zbierz=lambda zw, g: "ok"))
    tele = tele_klasa(Path(tempfile.mkdtemp()), zegar=s.zegar, zapis=False)
    tele.nazwa_postaci = "Ja"
    b.tele = tele
    return s, b, tele


def rek(tele, typ, rodzaj=None):
    return [r for r in tele.rek if r["typ"] == typ and (rodzaj is None or r.get("rodzaj") == rodzaj)]


def g_(exp=1000):
    return {"hp": 100, "max_hp": 100, "proc": 100.0, "exp": exp}


def ticki(b, s, od, do, poz=None, stan="IDZ", exp=1000, krok=1.0):
    """Wołamy detektor wprost co `krok` s zegara (bez reszty ticka): pozycja stała albo funkcja t -> poz."""
    t = od
    while t <= do + 1e-9:
        s.t = t
        b.stan = stan
        p = poz(t) if callable(poz) else (poz or (100, 100, 7))
        b._d3_tick(g_(exp), p, t)
        t += krok


cavebot.D3_LOG, cavebot.D3_PROG_S, cavebot.D3_ASTAR_MAX = 1, 30.0, 6

# --- 1. stoimy 31 s poza walką -> jeden rekord D3 z opcjami; dalsze sekundy go nie powielają ---
s, b, tele = scena()
b.ostatnie_stwory = [{"id": 1, "nazwa": "Ja", "gracz": True, "x": 100, "y": 100, "z": 7, "hp": 100},
                     {"id": 5, "nazwa": "Obcy", "gracz": True, "x": 103, "y": 100, "z": 7, "hp": 100},
                     {"id": 6, "nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": 50}]
ticki(b, s, 0, 29)
sprawdz("1a po 29 s jeszcze bez rekordu", rek(tele, "decyzja", "D3") == [])
ticki(b, s, 30, 31)
d3 = rek(tele, "decyzja", "D3")
sprawdz("1b po 31 s jest jeden rekord decyzja D3", len(d3) == 1, [r.get("rodzaj") for r in tele.rek])
r = d3[0] if d3 else {}
sprawdz("1c pola jak D1/D2: id, rodzaj, poz, opcje, wybrana (null = reguła jeszcze nie wybrała)",
        all(k in r for k in ("id", "rodzaj", "poz", "opcje", "wybrana")) and r.get("wybrana") is None, sorted(r))
op = {o["akcja"]: o for o in r.get("opcje", [])}
sprawdz("1d komplet opcji z sekcji 2 specyfikacji", set(op) == {"krok_skos", "cofnij", "inny_punkt", "przejscie_pietra", "czekaj", "alarm"}, sorted(op))
sprawdz("1e cechy: stan, stoi_s>=30, cel (punkt trasy), kierunek do celu, pola wokół z kodami, gracze/moby",
        r.get("stan") == "IDZ" and r.get("stoi_s", 0) >= 30 and r.get("cel") == [101, 100, 7] and r.get("kier_cel") == [1, 0]
        and set(r.get("wokol", {}).values()) <= set(".#odsmg?") and len(r.get("wokol", {})) == 8
        and r.get("gracze_odl") == [3] and r.get("moby_odl") == [1] and r.get("zamierzony") is False, r)
sprawdz("1f mob obok na polu +1+0 -> kod m; opcje czekaj/alarm zawsze możliwe",
        r.get("wokol", {}).get("+1+0") == "m" and op["czekaj"]["mozliwa"] and op["alarm"]["mozliwa"], r.get("wokol"))
sprawdz("1g krok_skos: cel w osi -> skos na boku kierunku (wolny)", op["krok_skos"]["mozliwa"] and op["krok_skos"]["kierunek"][0] == 1
        and op["krok_skos"]["kierunek"][1] in (-1, 1), op["krok_skos"])
sprawdz("1h cofnij bez historii niemożliwe (stoimy od startu)", not op["cofnij"]["mozliwa"], op["cofnij"])
sprawdz("1i inny_punkt: A* do punktów trasy, osiągalne >= 1", op["inny_punkt"]["osiagalnych"] >= 1
        and op["inny_punkt"]["sprawdzono"] >= 1, op["inny_punkt"])
ticki(b, s, 32, 70)
sprawdz("1j dalsze stanie nie powiela rekordu", len(rek(tele, "decyzja", "D3")) == 1)
sprawdz("1k bez wyniku, póki stoimy", rek(tele, "d3_wynik") == [])

# --- 2. ruch kończy zawieszkę: d3_wynik z decyzja_id, ruszyl, czasem i exp ---
ticki(b, s, 71, 71, poz=(104, 100, 7))
w = rek(tele, "d3_wynik")
sprawdz("2a jeden wynik po ruchu poza promień 2", len(w) == 1, w)
w = w[0] if w else {}
sprawdz("2b wynik: decyzja_id, ruszyl True, koniec ruch, czas_s ~ 71-30, exp_zmiana 0",
        w.get("decyzja_id") == r.get("id") and w.get("ruszyl") is True and w.get("koniec") == "ruch"
        and abs(w.get("czas_s", 0) - 41.0) < 1.5 and w.get("exp_zmiana") == 0 and w.get("ruszyl_20s") is False, w)
sprawdz("2c wynik niesie poz_start i poz_koniec", w.get("poz_start") == [100, 100, 7] and w.get("poz_koniec") == [104, 100, 7], w)
ticki(b, s, 72, 102, poz=(104, 100, 7))
sprawdz("2d po ruchu kolejna kotwica; po 30 s w nowym miejscu kolejna zawieszka", len(rek(tele, "decyzja", "D3")) == 2)

# --- 2e. ruch w ciągu 20 s od startu = ruszyl_20s ---
s, b, tele = scena()
ticki(b, s, 0, 35)
ticki(b, s, 36, 40, poz=(110, 100, 7))
w = rek(tele, "d3_wynik")
sprawdz("2e ruch 10 s po starcie: ruszyl_20s True", len(w) == 1 and w[0]["ruszyl_20s"] is True and w[0]["czas_s"] <= 11, w)

# --- 2f. akcje istniejącej reguły trafiają do d3_wynik.regula (wybrana w rekordzie decyzji zostaje null) ---
s, b, tele = scena()
ticki(b, s, 0, 35)
b._d3_nota("inny_punkt")
b._d3_nota("inny_punkt")
b._d3_nota("krok_skos")
ticki(b, s, 36, 36, poz=(110, 100, 7))
w = rek(tele, "d3_wynik")
sprawdz("2f regula zapisana bez powtórzeń, w kolejności", len(w) == 1 and w[0]["regula"] == ["inny_punkt", "krok_skos"], w)
b2 = scena()[1]
b2._d3_nota("alarm")
sprawdz("2g nota bez trwającej zawieszki nic nie robi", True)

# --- 3. walka: stoimy w stanach walki -> brak rekordu ---
for stan in ("WALKA", "POGON", "LOOT", "WALKA_PVP"):
    s, b, tele = scena()
    ticki(b, s, 0, 120, stan=stan)
    sprawdz(f"3 stan {stan} 120 s: brak rekordu D3", rek(tele, "decyzja", "D3") == [])
s, b, tele = scena()
b.pk_stan = "WALKA"
ticki(b, s, 0, 120)
sprawdz("3e pk_stan WALKA: brak rekordu", rek(tele, "decyzja", "D3") == [])
# walka 40% okna -> to nie zawieszka; walka 10% -> zawieszka
s, b, tele = scena()
for t in range(0, 61):
    s.t = float(t)
    b.stan = "WALKA" if (t % 10) < 4 else "IDZ"
    b._d3_tick(g_(), (100, 100, 7), float(t))
sprawdz("3f 40% czasu w walce: brak rekordu", rek(tele, "decyzja", "D3") == [])
s, b, tele = scena()
for t in range(0, 61):
    s.t = float(t)
    b.stan = "WALKA" if (t % 10) == 0 else "IDZ"
    b._d3_tick(g_(), (100, 100, 7), float(t))
sprawdz("3g ~10% czasu w walce: jest zawieszka", len(rek(tele, "decyzja", "D3")) == 1, len(rek(tele, "decyzja", "D3")))

# --- 4. ruch: idziemy 1 pole na 5 s -> brak rekordu; exp rośnie -> brak ---
s, b, tele = scena()
ticki(b, s, 0, 200, poz=lambda t: (100 + int(t // 5), 100, 7))
sprawdz("4a postać idzie: brak rekordu", rek(tele, "decyzja", "D3") == [])
s, b, tele = scena()
ticki(b, s, 0, 200, exp=0, poz=(100, 100, 7))
n0 = len(rek(tele, "decyzja", "D3"))
s, b, tele = scena()
for t in range(0, 200):
    s.t = float(t)
    b.stan = "IDZ"
    b._d3_tick(g_(1000 + 5 * (t // 10)), (100, 100, 7), float(t))   # co 10 s przyrost exp (zabicia z miejsca)
sprawdz("4b stoimy, ale exp rośnie co 10 s: brak zawieszki", rek(tele, "decyzja", "D3") == [] and n0 == 1)
# exp kończy trwającą zawieszkę
s, b, tele = scena()
ticki(b, s, 0, 40)
ticki(b, s, 41, 41, exp=1010)
w = rek(tele, "d3_wynik")
sprawdz("4c przyrost exp w trakcie zawieszki: wynik koniec=exp, ruszyl False, exp_zmiana 10",
        len(w) == 1 and w[0]["koniec"] == "exp" and w[0]["ruszyl"] is False and w[0]["exp_zmiana"] == 10, w)
# zmiana piętra = ruch
s, b, tele = scena()
ticki(b, s, 0, 40)
ticki(b, s, 41, 41, poz=(100, 100, 8))
w = rek(tele, "d3_wynik")
sprawdz("4d zmiana piętra kończy zawieszkę (ruszyl True, koniec pietro)", len(w) == 1 and w[0]["koniec"] == "pietro" and w[0]["ruszyl"], w)
# wejście w walkę kończy trwającą zawieszkę
s, b, tele = scena()
ticki(b, s, 0, 40)
ticki(b, s, 41, 100, stan="WALKA")
w = rek(tele, "d3_wynik")
sprawdz("4e walka w trakcie zawieszki: koniec=walka, ruszyl False", len(w) == 1 and w[0]["koniec"] == "walka" and not w[0]["ruszyl"], w)
# koniec pracy bota
s, b, tele = scena()
ticki(b, s, 0, 40)
b._d3_zamknij()
w = rek(tele, "d3_wynik")
sprawdz("4f zamknięcie bota w trakcie zawieszki: wynik koniec=stop", len(w) == 1 and w[0]["koniec"] == "stop", w)
b._d3_zamknij()
sprawdz("4g drugie zamknięcie nie dubluje", len(rek(tele, "d3_wynik")) == 1)
# luka między obiegami (proces wisiał) nie jest zawieszką
s, b, tele = scena()
ticki(b, s, 0, 1)
ticki(b, s, 500, 501)
sprawdz("4h luka 500 s między obiegami: brak rekordu", rek(tele, "decyzja", "D3") == [])
# stan zamierzony: rekord jest, z flagą
s, b, tele = scena()
ticki(b, s, 0, 40, stan="PRZERWA")
d = rek(tele, "decyzja", "D3")
sprawdz("4i PRZERWA: rekord z zamierzony=True", len(d) == 1 and d[0]["zamierzony"] is True and d[0]["stan"] == "PRZERWA", d)

# --- 5. D3_LOG=0 / brak telemetrii ---
cavebot.D3_LOG = 0
s, b, tele = scena()
ticki(b, s, 0, 120)
sprawdz("5a D3_LOG=0: brak rekordów D3 i d3_wynik", rek(tele, "decyzja", "D3") == [] and rek(tele, "d3_wynik") == [] and b._d3 is None)
cavebot.D3_LOG = 1
s, b, tele = scena()
b.tele = None
ticki(b, s, 0, 120)
sprawdz("5b bez telemetrii: nic nie zapisuje i nie wywraca", True)
# wyłączenie w trakcie zawieszki: bez wiszącego stanu
s, b, tele = scena()
ticki(b, s, 0, 40)
cavebot.D3_LOG = 0
ticki(b, s, 41, 45)
cavebot.D3_LOG = 1
ticki(b, s, 46, 50)
sprawdz("5c wyłączenie i włączenie: bez wyjątku, stan zaczyna od nowa (brak wyniku z urwanej zawieszki)", rek(tele, "d3_wynik") == [])

# --- 6. koszt: A* najwyżej D3_ASTAR_MAX razy na zawieszkę, także z grafem przejść i dużą trasą ---
def liczy_astar(max_a, przejscia=False, punkty=None):
    cavebot.D3_ASTAR_MAX = max_a
    s, b, tele = scena(punkty=punkty)
    wywolan = []
    b.droga = lambda start, cel, zajete=(), dlugosc=1, skosy=True: (wywolan.append(cel), [(start[0] + 1, start[1], start[2])])[1]
    if przejscia:
        b.przejscia = [{"id": f"p{i}:w_dol", "z": 7, "wej": (100 + i, 105, 7), "kroki": [(100 + i, 105, 8)],
                        "wyj": (100 + i, 105, 8), "pieta": True} for i in range(5)]
    ticki(b, s, 0, 40)
    return wywolan, rek(tele, "decyzja", "D3")
dluga = [(100 + i, 100 + (i % 3), 7) for i in range(1, 60)]
for mx in (6, 2, 0, 12):
    wyw, d = liczy_astar(mx, przejscia=True, punkty=dluga)
    sprawdz(f"6 D3_ASTAR_MAX={mx}: wywołań A* {len(wyw)} <= {mx}, rekord jest, licznik w rekordzie zgodny",
            len(wyw) <= mx and len(d) == 1 and d[0]["astar_wywolan"] == len(wyw), (len(wyw), d[0].get("astar_wywolan") if d else None))
wyw, d = liczy_astar(6, przejscia=True, punkty=dluga)
op = {o["akcja"]: o for o in d[0]["opcje"]} if d else {}
sprawdz("6e z budżetem 6: cel, punkty trasy i przejście pięter dostały A* (przejście niezagłodzone)",
        len(wyw) == 6 and op["przejscie_pietra"].get("droga_policzona") is True and op["przejscie_pietra"].get("pietro_docelowe") == 8
        and op["inny_punkt"]["sprawdzono"] == 4, (len(wyw), op.get("przejscie_pietra"), op.get("inny_punkt")))
cavebot.D3_ASTAR_MAX = 6

# stan A* bota po liczeniu opcji nietknięty (statystyki)
s, b, tele = scena()
b.droga_bez_blokad, b.ostatni_blokujacy = 7, ("x", 1)
def droga_psuje(*a, **k):
    b.droga_bez_blokad += 1
    b.ostatni_blokujacy = ("y", 2)
    return [(101, 100, 7)]
b.droga = droga_psuje
ticki(b, s, 0, 40)
sprawdz("6f statystyki A* bota (droga_bez_blokad, ostatni_blokujacy) nietknięte", b.droga_bez_blokad == 7 and b.ostatni_blokujacy == ("x", 1))

# --- 7. cały tick(): stojąca postać (krok nie rusza) -> dokładnie jedna zawieszka; ruch taki sam z logiem i bez ---
def przebieg(d3_log):
    cavebot.D3_LOG = d3_log
    random.seed(11)
    s, b, tele = scena(rusza=False)
    cavebot.HAKI_LOGU.append(tele.linia)
    try:
        for _ in range(4000):
            b.tick()
            if s.t > 75:
                break
    finally:
        cavebot.HAKI_LOGU.remove(tele.linia)
    return s, b, tele
s1, b1, t1 = przebieg(1)
s0, b0, t0 = przebieg(0)
d1 = rek(t1, "decyzja", "D3")
sprawdz("7a pełny tick: postać stoi > 75 s -> zawieszka zapisana", len(d1) >= 1, [(r["typ"], r.get("rodzaj")) for r in t1.rek][:10])
sprawdz("7b D3_LOG=0: brak rekordu", rek(t0, "decyzja", "D3") == [])
sprawdz("7c ruch bota identyczny z logiem i bez (klawisze, pozycja, zegar)",
        s1.klawisze == s0.klawisze and s1.poz == s0.poz and abs(s1.t - s0.t) < 1e-9, (len(s1.klawisze), len(s0.klawisze)))
cavebot.D3_LOG = 1

# --- 8. zepsuty zapis telemetrii nie wywraca ticka ---
random.seed(11)
s, b, tele = scena(rusza=False, tele_klasa=TeleBlad)
ok_ = True
try:
    for _ in range(4000):
        b.tick()
        if s.t > 75:
            break
except Exception as e:
    ok_ = False
    print(e)
sprawdz("8 zepsuty zapis: tick idzie dalej", ok_ and s.t > 75)

cavebot.D3_LOG, cavebot.D3_PROG_S, cavebot.D3_ASTAR_MAX = DOMYSLNE

# --- 9. pokrętła: zakres, domyślne, przykład ---
import json  # noqa: E402
import pokretla  # noqa: E402
przyklad = json.loads((Path(__file__).resolve().parent.parent / "na_zywo.przyklad.json").read_text())
sprawdz("9a pokrętła D3 w ZAKRESY i w na_zywo.przyklad.json z domyślną",
        all(k in pokretla.ZAKRESY and k in przyklad and przyklad[k] == getattr(cavebot, k) for k in ("D3_LOG", "D3_PROG_S", "D3_ASTAR_MAX")))
sprawdz("9b domyślne: D3_LOG 1, D3_PROG_S 30, D3_ASTAR_MAX 6", DOMYSLNE == (1, 30.0, 6), DOMYSLNE)
ok, bl = pokretla.waliduj({"D3_PROG_S": 45.0, "D3_LOG": 0})
sprawdz("9c walidacja przyjmuje 45 s i 0", ok == {"D3_PROG_S": 45.0, "D3_LOG": 0} and not bl, (ok, bl))
ok, bl = pokretla.waliduj({"D3_PROG_S": 1.0})
sprawdz("9d D3_PROG_S poza zakresem odrzucony", not ok and bl)

print(f"\n{sum(wyniki)}/{len(wyniki)} OK")
sys.exit(0 if all(wyniki) else 1)
