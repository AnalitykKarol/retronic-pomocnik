#!/usr/bin/env python3
"""25.10 (Karol: „bot miał atakować gracza, klikając na postać w takich chwilach, i uciekać od razu do depo”): PK_KONTRATAK + PK_BEZ_PAUZY_HP.
Odtwarza na atrapach (bez gry, X11 i modelu) przypadek Odchyd lvl 13, trolle_kazordoon_z8, 25.10 18:25 (instancje/odchyd/logi/mozg-20261025-1713.log
linie ok. 4075-4175, telemetria-20261025.jsonl): gracz „Ogr” obok, HP 100 -> 96 -> 87 -> 78 bez potwora przy nas.
Sprawdza: (1) start ucieczki PK w tym samym obiegu co wykrycie ataku, (2) dokładnie jedno kliknięcie w napastnika (po starcie ucieczki,
ucieczka ma pierwszeństwo), limity klików, (3) brak ataku, gdy gracz tylko stoi obok albo przy potworze/widmie/GM, (4) pokrętło 0 = zero klików,
(5) bramka HP_PRZED_PIETREM (PAUZA_HP) nie wstrzymuje ucieczki PK."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KAT))
import bot  # noqa: E402,F401
import cavebot  # noqa: E402
import mozg  # noqa: E402
import obrona_pk  # noqa: E402
import pokretla  # noqa: E402

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
cavebot.PK_SZYBKIE = 0
TMP = Path(tempfile.mkdtemp())
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


JA = (32662, 31961, 8)          # pole z logu 18:25:28 (Odchyd, z8, obok dziury z ogniem)


def gr(nazwa, dx, dy, hp=100, id_=777, **kw):
    return dict({"id": id_, "nazwa": nazwa, "gracz": True, "dx": dx, "dy": dy, "z": 8, "hp": hp}, **kw)


def mob(nazwa, dx, dy, hp=100, id_=9001):
    return dict({"id": id_, "nazwa": nazwa, "gracz": False, "dx": dx, "dy": dy, "z": 8, "hp": hp})


def klatki_ogr():
    """(t, hp%, stwory względem postaci): HP wg telemetrii 18:25:15-30 (t=0 -> 18:25:15); Ogr obok od t=3, uderza od t=4."""
    obok = lambda: [gr("Ogr", -1, 0)]
    return [(0.0, 100, [gr("Ogr", 3, -6)]), (1.0, 100, [gr("Ogr", 2, -3)]), (2.0, 100, [gr("Ogr", 0, -1)]),
            (3.0, 96, obok()), (4.0, 87, obok()), (5.0, 78, obok()), (6.0, 67, obok()), (7.0, 57, obok()), (8.0, 44, obok())]


class Swiat:
    def __init__(s, kl, nick="Odchyd"):
        s.t, s.kl, s.nick, s.poz = 0.0, kl, nick, list(JA)
        s.klawisze, s.zdarzenia = [], []        # zdarzenia: ("start", t) / ("klik", t, id)

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
        _, hp, st = s.klatka()
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": hp, "max_hp": 100, "mana": 23, "max_mana": 215}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": s.nick, "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            out = []
            for m in st:
                m = dict(m)
                m["x"], m["y"] = s.poz[0] + m.pop("dx"), s.poz[1] + m.pop("dy")
                out.append(m)
            return {"stwory": [ja] + out}
        return {}


class P:
    def __init__(p, s):
        p.s, p.nazwa = s, s.nick

    def pozycja(p):
        return tuple(p.s.poz)

    def klawisz(p, k):
        p.s.klawisze.append((k, p.s.t))

    def krok(p, k):
        return tuple(p.s.poz)


class FakeWyprawa:
    def __init__(f, ref, s):
        f.cb, f.s, f.w, f.zablokowany, f.wywolania = ref, s, None, False, []

    def start_pk(f, rodzaj, teraz, baza=None):
        f.wywolania.append((rodzaj, teraz))
        f.s.zdarzenia.append(("start", teraz))
        f.w = {"potrzeby": {"depo": True, "pk": rodzaj}}
        f.cb[0].wypad_aktywny = True
        return True

    def tick(f):
        return False

    def przerwij(f, powod):
        f.w = None

    def uciekaj(f, poz):
        return True


def zrob(s, kontratak, atak_wyjatek=False):
    cavebot.PK_KONTRATAK = kontratak

    def atak(m, g):
        if atak_wyjatek:
            raise RuntimeError("klik poza widokiem")
        s.zdarzenia.append(("klik", s.t, m["id"]))

    punkty = [(JA[0] + i, JA[1], 8) for i in range(1, 11)]
    b = mozg.CavebotMozgu(P(s), punkty, okrazenia=999, zapytaj=s.zapytaj, atak=atak, alarm=lambda w: None,
                          spij=s.spij, zegar=s.zegar, loot=type("L", (), {"zbierz": staticmethod(lambda zw, g: "ok")})())
    b._pk_dane()
    b.pk_wrogowie = obrona_pk.Wrogowie(TMP / f"wrogowie-{len(ok)}.json", czas=s.zegar, log=lambda t: None)
    b.powiadomienia = []
    b._pk_powiadom = lambda tytul, tresc, klucz: b.powiadomienia.append((tytul, tresc, klucz))
    b.fw = FakeWyprawa([b], s)
    b.wyprawa = b.fw
    return b


def odtworz(s, b, do, krok=1.0):
    t = 0.0
    while t <= do + 1e-9:
        s.t = t
        b.tick()
        t += krok


def kliki(s, id_=None):
    """Kliki ataku; id_=777 -> tylko w gracza-napastnika (zwykła walka z potworem też klika, to nie jest przedmiot testu)."""
    return [z for z in s.zdarzenia if z[0] == "klik" and (id_ is None or z[2] == id_)]


def starty(s):
    return [z for z in s.zdarzenia if z[0] == "start"]


# --- 0. pokrętła: domyślnie, ZAKRESY, KIERUNEK, przykład ---
przyklad = json.loads((KAT / "na_zywo.przyklad.json").read_text())
src = (KAT / "cavebot.py").read_text()
sprawdz("0a PK_KONTRATAK: w kodzie domyślnie 0, w ZAKRESY (0,1), nie_wyzej, w przykładzie 0",
        "\nPK_KONTRATAK = 0 " in src and pokretla.ZAKRESY.get("PK_KONTRATAK") == (0, 1)
        and pokretla.KIERUNEK.get("PK_KONTRATAK") == "nie_wyzej" and przyklad.get("PK_KONTRATAK") == 0)
sprawdz("0b PK_BEZ_PAUZY_HP: w kodzie domyślnie 1, w ZAKRESY (0,1), nie_nizej, w przykładzie 1",
        "\nPK_BEZ_PAUZY_HP = 1 " in src and pokretla.ZAKRESY.get("PK_BEZ_PAUZY_HP") == (0, 1)
        and pokretla.KIERUNEK.get("PK_BEZ_PAUZY_HP") == "nie_nizej" and przyklad.get("PK_BEZ_PAUZY_HP") == 1)
ok_, bl = pokretla.waliduj({"PK_KONTRATAK": 1, "PK_BEZ_PAUZY_HP": 1}, {"PK_KONTRATAK": 0, "PK_BEZ_PAUZY_HP": 1})
sprawdz("0c analityk nie może włączyć PK_KONTRATAK (tylko Karol ręcznie): walidacja z domyślnymi odrzuca 1",
        "PK_KONTRATAK" not in ok_ and "PK_BEZ_PAUZY_HP" in ok_ and len(bl) == 1, f"{ok_} {bl}")
ok_, bl = pokretla.waliduj({"PK_KONTRATAK": 1, "PK_BEZ_PAUZY_HP": 0})
sprawdz("0d ręczny na_zywo.json: PK_KONTRATAK=1 i PK_BEZ_PAUZY_HP=0 przechodzą walidację", ok_ == {"PK_KONTRATAK": 1, "PK_BEZ_PAUZY_HP": 0} and not bl, f"{ok_} {bl}")

# --- 1. kontrola, PK_KONTRATAK=0: ucieczka startuje, ZERO klików (zachowanie jak dotąd) ---
cavelog.clear()
s = Swiat(klatki_ogr())
b = zrob(s, 0)
odtworz(s, b, 8.0)
sprawdz("1a PK_KONTRATAK=0: ucieczka PK wystartowała (pk_stan UCIECZKA, start_pk raz)", b.pk_stan == "UCIECZKA" and len(starty(s)) == 1, f"{b.pk_stan} {s.zdarzenia}")
sprawdz("1b PK_KONTRATAK=0: zero klików w napastnika, brak wpisu [ATAK] klik", not kliki(s) and not any("[ATAK] klik" in l for l in cavelog), f"{s.zdarzenia}")

# --- 2. PK_KONTRATAK=1: start ucieczki w obiegu wykrycia (t=4), potem jedno kliknięcie, w tej kolejności ---
cavelog.clear()
s = Swiat(klatki_ogr())
b = zrob(s, 1)
odtworz(s, b, 3.0)
sprawdz("2a t=3 (HP 96, spadek 4 pp < 8, Ogr obok): bez PK i bez kliku (gracz tylko stoi obok)", b.pk_stan is None and not s.zdarzenia, f"{b.pk_stan} {s.zdarzenia}")
s.t = 4.0
b.tick()
sprawdz("2b t=4 (HP 87, spadek 13 pp, bez potwora): ucieczka PK w TYM SAMYM obiegu co wykrycie", b.pk_stan == "UCIECZKA" and starty(s) == [("start", 4.0)], f"{b.pk_stan} {s.zdarzenia}")
sprawdz("2c w tym obiegu dokładnie jedno kliknięcie w Ogra (id 777)", kliki(s) == [("klik", 4.0, 777)], f"{s.zdarzenia}")
sprawdz("2d kolejność: najpierw start ucieczki, potem klik (ucieczka ma pierwszeństwo)", [z[0] for z in s.zdarzenia] == ["start", "klik"], f"{s.zdarzenia}")
sprawdz("2e wpis [ATAK] klik: Ogr ... powód pk_kontratak 1/3", any(l.startswith("[ATAK] klik: Ogr") and "pk_kontratak 1/3" in l for l in cavelog), cavelog[-5:])
sprawdz("2f w logu PK: ATAK gracza z danych + UCIEKAM do miasta przed klikiem",
        [i for i, l in enumerate(cavelog) if "PK: UCIEKAM do miasta" in l][:1] < [i for i, l in enumerate(cavelog) if l.startswith("[ATAK] klik")][:1])
nicki = {v["nick"] for v in b.pk_wrogowie.dane.values()}
sprawdz("2g napastnik trafił na listę wrogów (jak dotąd)", "Ogr" in nicki, nicki)
s.t = 5.0
b.tick()
s.t = 6.0
b.tick()
sprawdz("2h kolejne obiegi t=5, 6 (odstęp < 4 s): bez drugiego kliku, ucieczka bez ponownego startu", len(kliki(s)) == 1 and len(starty(s)) == 1, f"{s.zdarzenia}")
s.t = 8.0
b.tick()
sprawdz("2i t=8 (>= 4 s od kliku, nadal bije): drugi klik, nadal jedna ucieczka", len(kliki(s)) == 2 and len(starty(s)) == 1 and kliki(s)[1][1] == 8.0, f"{s.zdarzenia}")

# --- 3. limit PK_KONTRATAK_MAX na ucieczkę (długie bicie): 3 kliki, potem już tylko ucieczka ---
dl = [(0.0, 100, [gr("Ogr", 2, 0)])] + [(float(t), max(5, 100 - 6 * t), [gr("Ogr", -1, 0)]) for t in range(1, 41)]
s = Swiat(dl)
b = zrob(s, 1)
odtworz(s, b, 40.0)
sprawdz("3 bicie przez 40 s: dokładnie PK_KONTRATAK_MAX=3 kliki, jedna ucieczka", len(kliki(s)) == cavebot.PK_KONTRATAK_MAX == 3 and len(starty(s)) == 1, f"{len(kliki(s))} {len(starty(s))}")

# --- 4. gracz tylko stoi obok (bez obrażeń): nic, ani ucieczki, ani kliku ---
s = Swiat([(0.0, 100, [gr("Ogr", -1, 0)])])
b = zrob(s, 1)
odtworz(s, b, 30.0)
sprawdz("4 gracz obok 30 s, HP 100%: bez PK, bez kliku", b.pk_stan is None and not s.zdarzenia, f"{b.pk_stan} {s.zdarzenia}")

# --- 5. spadek HP, ale potwór przy nas: to nie atak gracza (zwykła walka): bez PK i kliku ---
s = Swiat([(0.0, 100, [gr("Ogr", -2, 0), mob("Troll", 1, 0)]), (1.0, 80, [gr("Ogr", -1, 0), mob("Troll", 1, 0)]),
           (2.0, 60, [gr("Ogr", -1, 0), mob("Troll", 1, 0)])])
b = zrob(s, 1)
odtworz(s, b, 3.0)
sprawdz("5 HP spada, troll obok: bez PK i bez kliku w gracza (klik w trolla to zwykła walka)", b.pk_stan is None and not kliki(s, 777), f"{b.pk_stan} {s.zdarzenia}")

# --- 6. napastnik to widmo (obcy gracz na NASZYM polu, widma.py): ucieczka tak (PK czyta wszystko), klik nie ---
s = Swiat([(0.0, 100, [gr("Duch", 0, 0)]), (1.0, 100, [gr("Duch", 0, 0)]), (2.0, 85, [gr("Duch", 0, 0)])])
b = zrob(s, 1)
odtworz(s, b, 3.0)
sprawdz("6 napastnik na polu bota (widmo): ucieczka PK tak, klik nie", b.pk_stan == "UCIECZKA" and not kliki(s, 777), f"{b.pk_stan} {s.zdarzenia}")
st_ = b.stwory(0.0)
sprawdz("6a atrapa naprawdę dała wpisowi znacznik widmo", any(x.get("nazwa") == "Duch" and x.get("widmo") for x in st_), st_)

# --- 7. wyjątek w kliku (np. poza widokiem) nie psuje ucieczki ---
s = Swiat(klatki_ogr())
b = zrob(s, 1, atak_wyjatek=True)
cavelog.clear()
odtworz(s, b, 5.0)
sprawdz("7 wyjątek w kliku: ucieczka trwa, wpis w logu, bez wywrotki", b.pk_stan == "UCIECZKA" and len(starty(s)) == 1
        and any("kontratak: błąd" in l for l in cavelog), f"{b.pk_stan} {cavelog[-3:]}")

# --- 8. czaszka bez uderzenia (wróg w widoku): ucieczka, ale NIE atakujemy ---
s = Swiat([(0.0, 100, [gr("Czaszkowy", -3, 0, czaszka=True)]), (1.0, 100, [gr("Czaszkowy", -3, 0, czaszka=True)])])
b = zrob(s, 1)
odtworz(s, b, 2.0)
sprawdz("8 gracz z czaszką bez ataku: ucieczka PK, ale zero klików (atakujemy tylko tego, kto nas uderzył)", b.pk_stan == "UCIECZKA" and not kliki(s), f"{b.pk_stan} {s.zdarzenia}")

# --- 9. PAUZA_HP / czekanie na HP przed przejściem pięter nie wstrzymuje ucieczki PK ---
class Zegar:
    t = 1000.0


def cb_(pk_stan, proc=78, bez_pauzy=1):
    z = Zegar()
    cb = cavebot.Cavebot.__new__(cavebot.Cavebot)
    cb.__dict__.update(dojscie_aktywne=False, wypad_aktywny=True, stan="IDZ", aktywnosc_ts=0.0, pk_stan=pk_stan,
                       hp_gracza_spadek=z.t - 0.5,       # gryzie: HP spadło przed chwilą (napastnik to GRACZ, nie potwór)
                       ostatnie_stwory=[{"nazwa": "Ogr", "gracz": True, "x": 100, "y": 100, "z": 8, "hp": 100}],
                       g_tick={"proc": proc, "mana": 23}, zegar=lambda: z.t, _z=z)
    cb.pauza = lambda a, b=None: setattr(z, "t", z.t + (a if b is None else (a + b) / 2))
    cb.dystans = lambda a, b: max(abs(a[0] - b[0]), abs(a[1] - b[1]))
    cavebot.PK_BEZ_PAUZY_HP = bez_pauzy
    return cb


POZ = (100, 100, 8)
KLUCZ = ("lina", 8, 7)
cb = cb_(None)
sprawdz("9a kontrola: zwykły wypad, HP 78%, gracz obok: czeka w miejscu (True), stan PAUZA_HP",
        cb._hp_przed_pietrem(POZ, cb._z.t, KLUCZ) is True and str(cb.stan) == "PAUZA_HP", cb.stan)
cb = cb_("UCIECZKA", bez_pauzy=0)
sprawdz("9b PK_BEZ_PAUZY_HP=0 (jak dotąd): w ucieczce PK czeka (True) - to jest przyczyna", cb._hp_przed_pietrem(POZ, cb._z.t, KLUCZ) is True)
cb = cb_("UCIECZKA")
sprawdz("9c PK_BEZ_PAUZY_HP=1: w ucieczce PK nie czeka (False), stan nie PAUZA_HP", cb._hp_przed_pietrem(POZ, cb._z.t, KLUCZ) is False and str(cb.stan) != "PAUZA_HP", cb.stan)
cb = cb_(None)
cb._hp_przed_pietrem(POZ, cb._z.t, KLUCZ)
cb.pk_stan = "UCIECZKA"                              # czekanie rozpoczęte PRZED startem ucieczki (18:25:28 -> PK 18:25:30)
cavelog.clear()
w = cb._hp_przed_pietrem(POZ, cb._z.t, KLUCZ)
sprawdz("9d czekanie rozpoczęte przed ucieczką kończy się natychmiast: False, stan IDZ, hp_czeka wyczyszczone, wpis w logu",
        w is False and str(cb.stan) == "IDZ" and cb.hp_czeka is None and any("ucieczka PK trwa" in l for l in cavelog), f"{w} {cb.stan} {cavelog[-2:]}")
cb = cb_("POWROT")
sprawdz("9e powrót na spot (POWROT) i zwykła gra: czekanie na HP działa jak dotąd", cb._hp_przed_pietrem(POZ, cb._z.t, KLUCZ) is True)
cavebot.PK_BEZ_PAUZY_HP = 1

# --- 10. opis przyczyny opóźnienia ~10 s (NIE naprawiane tu): okno 4 s i brak obiegów podczas drabiny/liny ---
s = Swiat([(0.0, 96, [gr("Ogr", -1, 0)]), (4.3, 87, [gr("Ogr", -1, 0)])])   # 18:25:24.3 (96%) -> 18:25:28.3 (87%), pomiędzy blokujące próby drabiny i liny
b = zrob(s, 0)
s.t = 0.0
b.tick()
s.t = 4.3
b.tick()
print(f"INFO 10 (nie liczone) obiegi co 4,3 s (blokująca drabina/lina): spadek 9 pp poza oknem 4 s -> pk_stan={b.pk_stan}")

cavebot.PK_KONTRATAK = 0
cavebot.PK_BEZ_PAUZY_HP = 1
time.sleep(0.05)
print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
