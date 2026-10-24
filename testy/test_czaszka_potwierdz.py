#!/usr/bin/env python3
"""23.10: CZASZKA_POTWIERDZ. Fałszywa czerwona czaszka (invincible 09:33, „Rpg Cygan”: 09:20 none, 09:33 red -> ucieczka
do depo, choć gracz nie miał skulla) nie wystarcza do ucieczki: pierwszy odczyt groźnej czaszki musi potwierdzić DRUGI,
na świeżym zrzucie, wycinku wokół tej jednej postaci i z pytaniem tylko o nią. Niezgodność / postać znikła / za późno /
błąd modelu = brak ucieczki, wpis „czaszka niepotwierdzona” w logu i oba wycinki PNG w katalogu diagnostycznym.
Wyjątek: atak gracza (spadek HP, istniejąca detekcja PK) ucieka od razu, bez czaszki.
Atrapy modelu, zrzutu i pozycji; zero prawdziwych wywołań `claude`, zero gry. Pokrętło domyślnie 0 (zachowanie jak dotąd)."""
import json
import os
import sys
import tempfile
import time
import types
from pathlib import Path

os.environ["RETRONIC_TESTY"] = "1"
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

import bot  # noqa: E402
import cavebot  # noqa: E402
import czaszka  # noqa: E402
import mozg  # noqa: E402
import nadzor  # noqa: E402
import obrona_pk  # noqa: E402
import pokretla  # noqa: E402

cavelog = []
_log0 = cavebot.log
cavebot.log = lambda *a: (cavelog.append(" ".join(map(str, a))), _log0(*a))
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

wyniki = []
tmp = Path(tempfile.mkdtemp())


def sprawdz(nazwa, warunek, info=""):
    wyniki.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + (f"  [{info}]" if not warunek and info else ""))


class Zegar:
    def __init__(s, t=1000.0):
        s.t = t

    def __call__(s):
        return s.t


class Haiku:
    """Atrapa modelu: kolejne odpowiedzi (ostatnia powtarza się), zapis promptów/systemów/obrazów, `dt` = ile trwa wywołanie."""
    def __init__(s, *odp, zegar=None, dt=0.0):
        s.odp, s.zegar, s.dt = list(odp), zegar, dt
        s.prompty, s.systemy, s.obrazy = [], [], []

    @property
    def wywolania(s):
        return len(s.prompty)

    def __call__(s, prompt, system=None, obraz=None):
        s.prompty.append(prompt)
        s.systemy.append(system)
        s.obrazy.append(obraz and Path(obraz).exists())
        if s.zegar is not None:
            s.zegar.t += s.dt
        o = s.odp.pop(0) if len(s.odp) > 1 else s.odp[0]
        if isinstance(o, Exception):
            raise o
        return o, {"total_cost_usd": 0.002}


class Ekran:
    """Atrapa zrzutu: każde wywołanie = NOWY obraz (inny kolor), żeby test odróżnił „świeży zrzut” od tego samego."""
    def __init__(s):
        s.n = 0

    def __call__(s):
        s.n += 1
        return Image.new("RGB", (1536, 960), (s.n % 256, 5, 5))


class Pozycje:
    """Atrapa pozycji postaci względem nas: sekwencja odpowiedzi (None = nie ma w widoku); ostatnia się powtarza."""
    def __init__(s, *p):
        s.p, s.pytano = list(p), []

    def __call__(s, nick):
        s.pytano.append(nick)
        return s.p.pop(0) if len(s.p) > 1 else s.p[0]


def czytnik(model, zeg=None, potwierdz=True, pozycja=None, ekran=None, katalog=None, **kw):
    """Czytnik z wstrzykniętymi atrapami. Nowe pola ustawiane PO konstruktorze: na starym kodzie są ignorowane,
    więc test pokazuje różnicę zachowania, nie wyjątek składni."""
    logi, wyc1, wyc2 = [], [], []
    r = czaszka.CzytnikCzaszki(model, zrzut=ekran or Ekran(), katalog=tmp / "k", log=logi.append,
                               zegar=zeg or Zegar(), **kw,
                               wytnij=lambda o, dx, dy: (wyc1.append((dx, dy, o.getpixel((0, 0))[0])), Image.new("RGB", (30, 20), (1, 2, 3)))[1])
    r.potwierdz = potwierdz
    r.pozycja = pozycja
    r.wytnij_postac = lambda o, dx, dy: (wyc2.append((dx, dy, o.getpixel((0, 0))[0])), Image.new("RGB", (60, 40), (9, 8, 7)))[1]
    r.katalog_niepotw = katalog or (tmp / "niepotw")
    r.spij = (lambda s: setattr(zeg, "t", zeg.t + s)) if zeg is not None else (lambda s: None)
    r.logi, r.wyc1, r.wyc2 = logi, wyc1, wyc2
    return r


def pngi(katalog):
    return sorted(Path(katalog).glob("*.png")) if Path(katalog).exists() else []


# --- A: czytnik, pojedyncze scenariusze ---
# A1 pokrętło 0 (domyślne): zachowanie jak dotąd, jedno wywołanie, czerwona od razu
czaszka.wyczysc(); z = Zegar(); h = Haiku("red")
r = czytnik(h, z, potwierdz=False, pozycja=Pozycje((1, 0)))
sprawdz("A1 pokrętło 0: pierwszy odczyt red = czerwona, 1 wywołanie, bez drugiego zrzutu",
        r.odczytaj("Rpg Cygan", 1, 0) == "czerwona" and czaszka.czaszka_grozna("Rpg Cygan", z) and h.wywolania == 1, h.wywolania)

# A2 scenariusz z logu: 09:20 none, 09:33 red -> drugi odczyt none = brak ucieczki
czaszka.wyczysc(); z = Zegar(); h = Haiku("none")
r = czytnik(h, z)
r.odczytaj("Rpg Cygan", -6, 4)                                   # 09:20:00 brak
sprawdz("A2a 09:20 none -> brak", czaszka.czaszka_gracza("Rpg Cygan", z) == "brak")
z.t += 800                                                       # TTL "brak" wygasł
poz = Pozycje((-5, 4)); ekr = Ekran(); h = Haiku("red", "none", zegar=z, dt=1.0)
r = czytnik(h, z, pozycja=poz, ekran=ekr)
wyn = r.odczytaj("Rpg Cygan", -6, 4)                             # 09:33:42 red, potwierdzenie none
sprawdz("A2b red bez potwierdzenia (drugi odczyt none): NIE jest groźna, model dostaje 'nieznana'",
        wyn == "niepotwierdzona" and not czaszka.czaszka_grozna("Rpg Cygan", z)
        and czaszka.dla_modelu("Rpg Cygan", z) == "nieznana", f"{wyn} {czaszka.czaszka_gracza('Rpg Cygan', z)}")
sprawdz("A2c dwa wywołania modelu i DWA różne zrzuty ekranu", h.wywolania == 2 and ekr.n == 2, (h.wywolania, ekr.n))
sprawdz("A2d wycinek potwierdzenia z ŚWIEŻEJ pozycji (-5,4), z drugiego zrzutu; pierwszy z pozycji zlecenia (-6,4)",
        r.wyc1 == [(-6, 4, 1)] and r.wyc2 == [(-5, 4, 2)], (r.wyc1, r.wyc2))
sprawdz("A2e oba wywołania miały istniejący plik obrazu", h.obrazy == [True, True], h.obrazy)
sprawdz("A2f prompt potwierdzenia inny niż pierwszy i pyta o JEDNĄ postać w środku",
        h.prompty[1] != h.prompty[0] and h.systemy[1] != h.systemy[0] and "ONE character" in h.systemy[1]
        and "NOT skulls" in h.systemy[1], (h.prompty, h.systemy[1][:120]))
log_n = [l for l in r.logi if "niepotwierdzona" in l]
sprawdz("A2g log „czaszka niepotwierdzona” z oboma odczytami", len(log_n) == 1 and "'red'" in log_n[0] and "'none'" in log_n[0], r.logi)
sprawdz("A2h log niepotwierdzonej czaszki NIE jest alarmem PK nadzorcy (RE_PK), a surowy „= czerwona” byłby",
        not any(nadzor.RE_PK.search(l) for l in r.logi)
        and nadzor.RE_PK.search("09:33:42 Czaszka: Rpg Cygan = czerwona (model: 'red')"), r.logi)
pl = pngi(tmp / "niepotw")
sprawdz("A2i oba wycinki PNG zapisane do diagnostyki (1. i 2. odczyt, w nazwie nick i odpowiedzi)",
        len(pl) == 2 and any("-1-" in p.name for p in pl) and any("-2-" in p.name for p in pl)
        and all("Rpg_Cygan" in p.name for p in pl), [p.name for p in pl])
n = h.wywolania
r.odczytaj("Rpg Cygan", -6, 4); r.odczytaj("RPG CYGAN", -6, 4)
sprawdz("A2j niepotwierdzona pamiętana per nick (bez ponawiania co tick)", h.wywolania == n, (n, h.wywolania))
z.t += czaszka.TTL_NIEPOTW_S + 1
h2 = Haiku("none"); r.model = h2
sprawdz("A2k po TTL niepotwierdzonej ponowny odczyt (nowy pierwszy odczyt none = brak)",
        r.odczytaj("Rpg Cygan", -6, 4) == "brak" and h2.wywolania == 1)

# A3/A4 potwierdzona biała i czerwona = groźna
for pierwszy, drugi, oczek in (("white", "white", "biala"), ("red", "red", "czerwona")):
    czaszka.wyczysc(); z = Zegar(); h = Haiku(pierwszy, drugi, zegar=z, dt=1.0)
    r = czytnik(h, z, pozycja=Pozycje((2, -1)))
    wyn = r.odczytaj("Skuller", 2, -1)
    sprawdz(f"A3 {pierwszy}+{drugi}: potwierdzona {oczek}, groźna, 2 wywołania", wyn == oczek and czaszka.czaszka_grozna("Skuller", z)
            and czaszka.czaszka_gracza("Skuller", z) == oczek and h.wywolania == 2, (wyn, h.wywolania))
    sprawdz(f"A3b {pierwszy}+{drugi}: log „Czaszka: … = {oczek}” (alarm PK nadzorcy) i adnotacja o potwierdzeniu",
            any(nadzor.RE_PK.search(l) and "potwierdz" in l for l in r.logi), r.logi)
czaszka.wyczysc(); z = Zegar(); h = Haiku("white", "red", zegar=z, dt=1.0)
r = czytnik(h, z, pozycja=Pozycje((0, 1)))
sprawdz("A5 white wtedy red: oba groźne, zapis wartości z bliskiego potwierdzenia (czerwona)",
        r.odczytaj("Mieszany", 0, 1) == "czerwona" and czaszka.czaszka_gracza("Mieszany", z) == "czerwona")

# A6 postać zniknęła z widoku przed potwierdzeniem: bez drugiego wywołania, bez groźnej, log z powodem
czaszka.wyczysc(); z = Zegar(); h = Haiku("red", zegar=z, dt=1.0)
poz = Pozycje(None); ekr = Ekran()
r = czytnik(h, z, pozycja=poz, ekran=ekr, katalog=tmp / "niepotw6")
wyn = r.odczytaj("Znikacz", 3, 2)
sprawdz("A6 postać znikła: niepotwierdzona, 1 wywołanie modelu, 1 zrzut, nie groźna",
        wyn == "niepotwierdzona" and h.wywolania == 1 and ekr.n == 1 and not czaszka.czaszka_grozna("Znikacz", z), (wyn, h.wywolania, ekr.n))
sprawdz("A6b log mówi, że postać zniknęła z widoku; tylko pierwszy wycinek w diagnostyce",
        any("niepotwierdzona" in l and "widoku" in l for l in r.logi) and len(pngi(tmp / "niepotw6")) == 1, r.logi)
sprawdz("A6c czekanie na świeżą pozycję jest ograniczone (nie pętla nieskończona)", 1 < len(poz.pytano) <= 20, len(poz.pytano))

# A7 pozycja pojawia się po krótkim czekaniu (odczyt stworów jeszcze nie odświeżony)
czaszka.wyczysc(); z = Zegar(); h = Haiku("red", "red", zegar=z, dt=1.0)
poz = Pozycje(None, None, (4, 0))
r = czytnik(h, z, pozycja=poz)
sprawdz("A7 pozycja po chwili czekania: potwierdzenie z niej korzysta", r.odczytaj("Spozniony", 3, 0) == "czerwona"
        and r.wyc2 and r.wyc2[0][:2] == (4, 0), r.wyc2)

# A8 drugi odczyt nieczytelny / błąd modelu / pozycja poza widokiem: niepotwierdzona
for nazwa, drugi, poz in (("unreadable", "unreadable", (1, 0)), ("błąd modelu", RuntimeError("timeout"), (1, 0)),
                          ("odpowiedź rozwlekła", "I think maybe a red skull", (1, 0))):
    czaszka.wyczysc(); z = Zegar(); h = Haiku("red", drugi, zegar=z, dt=1.0)
    r = czytnik(h, z, pozycja=Pozycje(poz))
    wyn = r.odczytaj("X", 1, 0)
    sprawdz(f"A8 drugi odczyt {nazwa}: niepotwierdzona, nie groźna", wyn == "niepotwierdzona" and not czaszka.czaszka_grozna("X", z), wyn)

# A9 za późno (limit czasu potwierdzenia)
czaszka.wyczysc(); z = Zegar(); h = Haiku("red", "red", zegar=z, dt=1.0)
r = czytnik(h, z, pozycja=Pozycje((1, 0)))
r.potw_s = 0.5
wyn = r.odczytaj("Spozniony2", 1, 0)
sprawdz("A9 potwierdzenie po limicie czasu (POTWIERDZ_S): niepotwierdzona, log o czasie",
        wyn == "niepotwierdzona" and any("niepotwierdzona" in l and "czas" in l for l in r.logi), (wyn, r.logi))
sprawdz("A9b domyślny limit czasu potwierdzenia rozsądny (kilka–kilkadziesiąt s, nie 3 s: sam Haiku to ~5-6 s)",
        10 <= czaszka.POTWIERDZ_S <= 60, czaszka.POTWIERDZ_S)

# A10 pierwszy odczyt none / nieczytelne nie uruchamia potwierdzenia (tylko groźna)
for odp in ("none", "unreadable"):
    czaszka.wyczysc(); z = Zegar(); h = Haiku(odp); ekr = Ekran()
    r = czytnik(h, z, pozycja=Pozycje((1, 0)), ekran=ekr)
    r.odczytaj("Czysty", 1, 0)
    sprawdz(f"A10 pierwszy odczyt {odp}: bez potwierdzania (1 wywołanie, 1 zrzut)", h.wywolania == 1 and ekr.n == 1)

# A11 pokrętło jako funkcja (hot-reload na żywo)
czaszka.wyczysc(); z = Zegar(); stan = {"p": 0}; h = Haiku("red", "red", "none", zegar=z, dt=1.0)
r = czytnik(h, z, potwierdz=lambda: stan["p"], pozycja=Pozycje((1, 0)))
sprawdz("A11 pokrętło jako funkcja: 0 -> czerwona od razu", r.odczytaj("Zywy", 1, 0) == "czerwona" and h.wywolania == 1)
czaszka.wyczysc(); stan["p"] = 1
sprawdz("A11b to samo po przełączeniu na 1 (bez nowego czytnika): potwierdzenie wymagane", r.odczytaj("Zywy", 1, 0) == "niepotwierdzona"
        and h.wywolania == 3, h.wywolania)

# A12 pokrętło: domyślnie 0 w kodzie, w env nadpisanie
os.environ.pop("CZASZKA_POTWIERDZ", None)
r = czaszka.CzytnikCzaszki(Haiku("none"), zrzut=Ekran(), log=lambda *a: None)
sprawdz("A12 domyślnie potwierdzanie wyłączone (stała 0, bez env)", czaszka.CZASZKA_POTWIERDZ == 0 and not r._potwierdzaj())
os.environ["CZASZKA_POTWIERDZ"] = "1"
sprawdz("A12b env CZASZKA_POTWIERDZ=1 włącza (czytnik tworzony po zmianie)", czaszka.CzytnikCzaszki(Haiku("none"), log=lambda *a: None)._potwierdzaj())
del os.environ["CZASZKA_POTWIERDZ"]

# A13 limit potwierdzeń na godzinę (koszt)
czaszka.wyczysc(); z = Zegar(); h = Haiku("red", "red", zegar=z, dt=1.0)
r = czytnik(h, z, pozycja=Pozycje((1, 0)))
r.potw_limit_h = 1
w1 = r.odczytaj("L1", 1, 0); w2 = r.odczytaj("L2", 1, 0)
sprawdz("A13 limit potwierdzeń/h: pierwszy potwierdzony, drugi niepotwierdzony (brak budżetu), log o limicie",
        w1 == "czerwona" and w2 == "niepotwierdzona" and any("limit" in l and "niepotwierdzona" in l for l in r.logi), (w1, w2, r.logi))

# A14 prawdziwy wycinek postaci (ekran.py): rozmiar, powiększenie, krawędzie
obraz = Image.new("RGB", (1536, 960), (10, 10, 10))
wyc = czaszka.wytnij_postac(obraz, 1, 0, prostokat=(127, 38, 1227, 845))
sprawdz("A14 wytnij_postac: ~5x2.5 pola, powiększony >= 4x względem wycinka nicku", wyc.size[0] >= 5 * 73 * 4 - 8 and wyc.size[1] > 150, wyc.size)
n1 = czaszka.wytnij_nick(obraz, 1, 0, prostokat=(127, 38, 1227, 845))
sprawdz("A14b wycinek postaci większy (w pikselach) niż stary wycinek nicku", wyc.size[0] * wyc.size[1] > n1.size[0] * n1.size[1])
sprawdz("A14c przy krawędzi mapy nie wychodzi poza obraz", czaszka.wytnij_postac(obraz, -7, -5, prostokat=(0, 0, 1100, 807)).size[0] > 0)

# --- B: cały przepływ do ucieczki (cavebot z prawdziwym magazynem czaszki) ---
JA = (100, 100, 8)


def gr(nick, dx, dy, hp=100):
    return {"id": hash(nick) % 100000 + 10, "nazwa": nick, "gracz": True, "dx": dx, "dy": dy, "z": 8, "hp": hp}


class Swiat:
    def __init__(s, klatki):
        s.t = 0.0
        s.klatki = sorted(klatki, key=lambda k: k[0])
        s.poz = list(JA)
        s.alarmy = []

    def klatka(s):
        k = s.klatki[0]
        for x in s.klatki:
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
            return {"gracz": {"hp": hp, "max_hp": 100, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            out = []
            for m in st:
                m = dict(m)
                m["x"], m["y"] = s.poz[0] + m.pop("dx"), s.poz[1] + m.pop("dy")
                out.append(m)
            return {"stwory": [ja] + out}
        return {}


class P:
    nazwa = "Ja"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        return tuple(p.s.poz)

    def klawisz(p, k):
        pass

    def krok(p, k):
        d = bot.KIERUNKI[k] if hasattr(bot, "KIERUNKI") else bot.KIERUNEKI[k]
        p.s.poz[0] += d[0]
        p.s.poz[1] += d[1]
        return tuple(p.s.poz)


class FakeWyprawa:
    def __init__(f, cb_ref):
        f.cb, f.w, f.ok, f.zablokowany, f.wywolania, f.depo = cb_ref, None, True, False, [], JA

    def _pole_depo(f):
        return f.depo

    def start_pk(f, rodzaj, teraz, baza=None):
        f.wywolania.append((rodzaj, teraz))
        f.w = {"potrzeby": {"depo": True, "pk": rodzaj}}
        f.cb[0].wypad_aktywny = True
        return True

    def tick(f):
        return False

    def przerwij(f, powod):
        f.w = None
        f.cb[0].wypad_aktywny = False

    def uciekaj(f, poz):
        return True


def zrob(s, nazwa):
    loot = types.SimpleNamespace(zbierz=lambda zw, g: "ok")
    punkty = [(100 + i, 100, 8) for i in range(1, 11)]
    b = cavebot.Cavebot(P(s), punkty, okrazenia=999, zapytaj=s.zapytaj, atak=lambda m, g: None,
                        alarm=lambda w: s.alarmy.append(w), spij=s.spij, zegar=s.zegar, loot=loot)
    b.pk_det, b.pk_wrogowie = None, None
    b._pk_dane()
    b.pk_wrogowie = obrona_pk.Wrogowie(tmp / f"wr-{nazwa}.json", czas=s.zegar, log=lambda t: None)
    b.powiadomienia = []
    b._pk_powiadom = lambda tytul, tresc, klucz: b.powiadomienia.append((tytul, tresc, klucz))
    b.fw = FakeWyprawa([b])
    b.wyprawa = b.fw
    return b


def tickuj(b, s, od, do):
    pierwsze, t = None, od
    while t <= do + 1e-9:
        s.t = t
        b.tick()
        if pierwsze is None and b.pk_stan is not None:
            pierwsze = t
        t += 1.0
    return pierwsze


def odczyt_na_zywo(pierwszy, drugi, pozycja=(-4, 2), nick="Rpg Cygan"):
    """Czytnik na prawdziwym zegarze (magazyn modułu liczy TTL wg time.time) i atrapie modelu; potwierdzenie włączone."""
    czaszka.wyczysc()
    h = Haiku(pierwszy, drugi)
    r = czytnik(h, zeg=None, pozycja=Pozycje(pozycja), ekran=Ekran(), katalog=tmp / "niepotw-b")
    r.zegar = time.time
    r.spij = lambda s: time.sleep(0.01)
    r.pozycja_czeka_s = 0.05
    return r, h


# B1 scenariusz z logu: red bez potwierdzenia, gracz w widoku, HP 100%: BRAK ucieczki i brak wpisu wroga
r, h = odczyt_na_zywo("red", "none")
r.odczytaj("Rpg Cygan", -4, 2)
s = Swiat([(0, 100, [gr("Rpg Cygan", -4, 2)]), (1, 100, [gr("Rpg Cygan", -3, 2)]), (2, 100, [gr("Rpg Cygan", -2, 2)]),
           (3, 100, [gr("Rpg Cygan", -1, 1)]), (4, 100, [gr("Rpg Cygan", -1, 1)])])
b = zrob(s, "B1")
pierwsze = tickuj(b, s, 0, 4)
sprawdz("B1 red→none: brak ucieczki PK, brak wpisu w wrogowie.json, brak wyprawy do depo",
        pierwsze is None and b.pk_stan is None and not b.pk_wrogowie.dane and not b.fw.wywolania,
        (pierwsze, b.pk_stan, b.pk_wrogowie.dane, b.fw.wywolania))
sprawdz("B1b brak komunikatu „uciekam zanim zaatakuje” w logu bota", not any("z groźną czaszką" in l for l in cavelog))

# B2 potwierdzona biała i czerwona = ucieczka jak dotąd
for kol, ang in (("biala", "white"), ("czerwona", "red")):
    r, h = odczyt_na_zywo(ang, ang)
    r.odczytaj("Rpg Cygan", -4, 2)
    s = Swiat([(0, 100, [gr("Rpg Cygan", -4, 2)]), (1, 100, [gr("Rpg Cygan", -3, 2)])])
    b = zrob(s, f"B2{kol}")
    pierwsze = tickuj(b, s, 0, 1)
    sprawdz(f"B2 potwierdzona {kol}: ucieczka PK w pierwszym obiegu, wróg z powodem 'czaszka', wyprawa do depo",
            pierwsze == 0 and b.pk_wrogowie.dane.get("rpg cygan", {}).get("powod") == "czaszka"
            and b.fw.wywolania[:1] == [("ucieczka", 0.0)], (pierwsze, b.pk_wrogowie.dane, b.fw.wywolania))

# B3 postać znikła z widoku przed potwierdzeniem: brak ucieczki (nawet gdy potem wraca w to samo miejsce)
r, h = odczyt_na_zywo("red", "red", pozycja=None)
r.odczytaj("Rpg Cygan", -4, 2)
s = Swiat([(0, 100, [gr("Rpg Cygan", -4, 2)]), (1, 100, []), (2, 100, [gr("Rpg Cygan", -3, 2)]), (3, 100, [gr("Rpg Cygan", -2, 2)])])
b = zrob(s, "B3")
sprawdz("B3 postać znikła przed potwierdzeniem: brak ucieczki, brak wpisu wroga",
        tickuj(b, s, 0, 3) is None and not b.pk_wrogowie.dane and h.wywolania == 1, (b.pk_stan, b.pk_wrogowie.dane, h.wywolania))

# B4 wyjątek: gracz z niepotwierdzoną czaszką faktycznie atakuje (spadek HP, bez potwora) -> ucieczka od razu
r, h = odczyt_na_zywo("red", "none")
r.odczytaj("Rpg Cygan", -4, 2)
s = Swiat([(0, 100, [gr("Rpg Cygan", -3, 1)]), (1, 100, [gr("Rpg Cygan", -2, 1)]), (2, 100, [gr("Rpg Cygan", -1, 0)]),
           (3, 70, [gr("Rpg Cygan", 1, 0)])])
b = zrob(s, "B4")
pierwsze = tickuj(b, s, 0, 3)
sprawdz("B4 atak gracza (HP 100→70, gracz obok) z niepotwierdzoną czaszką: ucieczka dokładnie w obiegu ataku (t=3), bez potwierdzania",
        pierwsze == 3 and b.pk_stan == "UCIECZKA" and "rpg cygan" in b.pk_wrogowie.dane
        and b.pk_wrogowie.dane["rpg cygan"]["powod"].startswith("atak") and h.wywolania == 2, (pierwsze, b.pk_stan, b.pk_wrogowie.dane))

# B5 pokrętło 0 (domyślne): to samo red bez potwierdzenia ucieka jak dotąd (zachowanie nie zmienione)
czaszka.wyczysc()
h = Haiku("red")
r = czytnik(h, None, potwierdz=False, pozycja=Pozycje((-4, 2)), katalog=tmp / "niepotw-b5")
r.zegar = time.time
r.odczytaj("Rpg Cygan", -4, 2)
s = Swiat([(0, 100, [gr("Rpg Cygan", -4, 2)]), (1, 100, [gr("Rpg Cygan", -3, 2)])])
b = zrob(s, "B5")
sprawdz("B5 pokrętło 0: pojedynczy odczyt red nadal uruchamia ucieczkę (stare zachowanie, bit w bit)",
        tickuj(b, s, 0, 1) == 0 and h.wywolania == 1)
czaszka.wyczysc()

# --- C: pokrętło w cavebot/pokretla/przykładzie, okablowanie w mozg ---
przyklad = json.load(open(Path(__file__).resolve().parent.parent / "na_zywo.przyklad.json"))
sprawdz("C1 cavebot.CZASZKA_POTWIERDZ domyślnie 0", getattr(cavebot, "CZASZKA_POTWIERDZ", None) == 0)
sprawdz("C2 na_zywo.przyklad.json opisuje pokrętło, domyślnie 0", przyklad.get("CZASZKA_POTWIERDZ") == 0)
sprawdz("C3 pokretla.ZAKRESY: 0/1; analityk nie może go wyłączyć/włączyć (tylko Karol, kierunek nie_wyzej)",
        pokretla.ZAKRESY.get("CZASZKA_POTWIERDZ") == (0, 1) and pokretla.KIERUNEK.get("CZASZKA_POTWIERDZ") == "nie_wyzej")
ok_, bl_ = pokretla.waliduj({"CZASZKA_POTWIERDZ": 1})
sprawdz("C4 ręczny na_zywo.json: wartość 1 przyjęta, 2 odrzucona", ok_ == {"CZASZKA_POTWIERDZ": 1}
        and pokretla.waliduj({"CZASZKA_POTWIERDZ": 2})[1])
sprawdz("C5 analityk (z domyślnymi) nie włączy: 1 > domyślne 0 = zły kierunek", pokretla.waliduj({"CZASZKA_POTWIERDZ": 1}, {"CZASZKA_POTWIERDZ": 0})[1])


def mozg_z_cb(odczyt, czyt=None):
    cb = types.SimpleNamespace(odczyt_stworow=odczyt, inni_gracze=lambda l, poz: [])
    return mozg.Mozg("doradca", zapytaj=lambda z: {}, nazwa="Ja", model=Haiku("x"), pamiec=mozg.Pamiec(tmp / "p.json"),
                     log=lambda *a: None, zegar=lambda: 100.0, trasy=lambda: ["t"], losuj=lambda a, b: a, cb=cb,
                     czytnik_czaszki=czyt)


lista = [{"id": 1, "nazwa": "Ja", "gracz": True, "x": 100, "y": 100, "z": 8},
         {"id": 2, "nazwa": "Rpg Cygan", "gracz": True, "x": 96, "y": 103, "z": 8},
         {"id": 3, "nazwa": "Daleko", "gracz": True, "x": 100, "y": 110, "z": 8},
         {"id": 4, "nazwa": "Pietro", "gracz": True, "x": 100, "y": 101, "z": 7}]
m = mozg_z_cb((99.5, lista))
sprawdz("C6 Mozg._pozycja_czaszki: świeży odczyt stworów -> pozycja względna (dx,dy), nick bez wielkości liter",
        m._pozycja_czaszki("rpg  cygan") == (-4, 3), m._pozycja_czaszki("rpg  cygan"))
sprawdz("C7 poza widokiem (dy=10) / inne piętro / nieznany nick -> None",
        m._pozycja_czaszki("Daleko") is None and m._pozycja_czaszki("Pietro") is None and m._pozycja_czaszki("Nikt") is None)
m = mozg_z_cb((90.0, lista))
sprawdz("C8 stary odczyt stworów (10 s) -> None (nie klikamy w pozycję z przeszłości)", m._pozycja_czaszki("Rpg Cygan") is None)
m = mozg_z_cb(None)
sprawdz("C8b brak odczytu stworów -> None", m._pozycja_czaszki("Rpg Cygan") is None)
cz = czaszka.CzytnikCzaszki(Haiku("none"), log=lambda *a: None)
m = mozg_z_cb((99.5, lista), czyt=cz)
sprawdz("C9 Mozg podpina czytnikowi pozycję i pokrętło z cavebot.CZASZKA_POTWIERDZ (hot-reload)",
        cz.pozycja is not None and cz.pozycja("Rpg Cygan") == (-4, 3) and not cz._potwierdzaj())
cavebot.CZASZKA_POTWIERDZ = 1
sprawdz("C9b po zmianie cavebot.CZASZKA_POTWIERDZ=1 (jak hot-reload na_zywo.json) czytnik potwierdza", cz._potwierdzaj())
cavebot.CZASZKA_POTWIERDZ = 0

print()
print(f"WYNIK: {sum(wyniki)} / {len(wyniki)}")
sys.exit(0 if all(wyniki) else 1)
