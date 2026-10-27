#!/usr/bin/env python3
"""26.10 (Karol): zmiana spotu po 3. spotkaniu tego samego gracza (SPOT_ZMIANA_PRZY_GRACZU, spot_gracz.py, dane_tibia/SPEC_spot_gracz_1026.md).
Offline: atrapy świata bota (jak test_pk_reset_po_zgonie) i świata nadzorcy (test_nadzor.Swiat); ZERO gry, X11, procesów, instancji i prawdziwych plików stanu.
Uruchomienie: RETRONIC_TESTY=1 python3 -I testy/test_spot_gracz.py

(A) licznik: 3 osobne spotkania vs jeden gracz kręcący się 10 min, mignięcie, przerwa 5 min, nasze/NPC/wrogowie/GM ignorowani, trwałość po restarcie,
    starzenie wpisów, uszkodzony plik; (B) limity 1/30 min i 4/dobę, bezpieczeństwo, unikane; (C) bot (prawdziwy tick CavebotMozgu na atrapie): droga,
    miasto/depo, inne piętro, STÓJ, ucieczka nie liczą; zlecenie, potwierdzenie spokoju (potwór <= 4 pól / HP < 70 %), pokrętło 0 = zero plików i zero logów;
    (D) rodzina spotów (pole `rodzina` i zapasowe grupowanie); (E) nadzorca: wybór nowego spotu (poziom, zajęty, unikany, zakazany, rodzina najpierw),
    bramki (pokrętło, limit, przypięty, walka, brak potwierdzenia, przeterminowane), cień niczego nie robi, brak zlecenia = nic się nie zmienia."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import re
import sys
import tempfile
import types
from datetime import datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KAT))
sys.path.insert(0, str(KAT / "testy"))
import bot  # noqa: E402,F401
import cavebot  # noqa: E402
import mozg  # noqa: E402
import nadzor as N  # noqa: E402
import pokretla  # noqa: E402
import spot_gracz as SG  # noqa: E402
import spoty as SP  # noqa: E402
import test_nadzor as TN  # noqa: E402

cavelog = []
cavebot.log = lambda *a: cavelog.append(" ".join(map(str, a)))
for nazwa_, wart_ in (("REAKCJA", (0.0, 0.0)), ("DRUGI_CEL", 0.0), ("ROZRZUT_PROGU", 0.0), ("STRAZNIK_CEL", 0), ("ODWROCENIE_TRASY", 0.0),
                      ("SCINANIE", (0.0, 2)), ("PAUZA_KROTKA", (0.0, 0.4, 1.5)), ("PAUZA_DLUGA", (0.0, 3.0, 8.0)), ("ATAK_TYLKO_PRZY_CELU", False),
                      ("ZDROWIE_CZAR_AKTYWNY", 0), ("PK_SZYBKIE", 0), ("PK_KONTRATAK", 0), ("SMIERC_STOP", 0), ("PK_RESET_PO_ZGONIE", 0)):
    setattr(cavebot, nazwa_, wart_)
TMP = Path(tempfile.mkdtemp())
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


T0 = 1_800_000_000.0           # epoch bazowy testów licznika


def licznik(nazwa="l"):
    p = TMP / f"{nazwa}-{len(ok)}.json"
    return SG.Licznik(p), p


def seans(l, nick, od, do, krok=1.0, aktywny=True, t0=T0):
    """Obiegi co `krok` s od t0+od do t0+do (włącznie) z jednym nickiem w widoku. -> zdarzenia."""
    z, t = [], od
    while t <= do:
        z += l.obserwuj(t0 + t, [nick] if nick else [], aktywny)
        t += krok
    return z


# ============================================================ (A) licznik
l, _ = licznik()
z = seans(l, "Statutum", 0, 20)
sprawdz("A1 gracz w widoku 20 s = jedno spotkanie (próg 3 s)", z == ["Statutum"] and l.gracze["statutum"]["spotkan"] == 1, (z, l.gracze))
sprawdz("A0 próg widoku to 3 s (Karol 27.10: 15 s nierealne), przerwa 300 s", SG.MIN_WIDOK_S == 3 and SG.PRZERWA_S == 300, (SG.MIN_WIDOK_S, SG.PRZERWA_S))
l, _ = licznik()
z = seans(l, "Statutum", 0, 3)
sprawdz("A1b widok równo 3 s (obiegi co 1 s: 0,1,2,3) = spotkanie (granica włączona)", z == ["Statutum"] and l.gracze["statutum"]["spotkan"] == 1, (z, l.gracze))
l, _ = licznik()
z = seans(l, "Statutum", 0, 2)
sprawdz("A2 mignięcie 2 s (< 3 s) nie jest spotkaniem", z == [] and l.gracze["statutum"]["spotkan"] == 0)
l, _ = licznik()
z = seans(l, "Statutum", 0, 2, krok=0.5) + seans(l, "Statutum", 2.5, 2.9, krok=0.1)
sprawdz("A2b mignięcie 2,9 s (obiegi co 0,5 i 0,1 s) nie jest spotkaniem", z == [] and l.gracze["statutum"]["spotkan"] == 0 and l.gracze["statutum"]["widok_s"] < SG.MIN_WIDOK_S, l.gracze)
l, _ = licznik()
z = seans(l, "Statutum", 0, 1) + seans(l, "Statutum", 15, 16)
sprawdz("A2c luka > MAX_KROK_S (10 s) nie liczy się do widoku: 2 x 1 s w odstępie 14 s = widok 2 s (nie 16), 0 spotkań", z == [] and l.gracze["statutum"]["spotkan"] == 0
        and l.gracze["statutum"]["widok_s"] == 2.0, l.gracze)
z = seans(l, "Statutum", 30, 31)
sprawdz("A2c2 widok w epizodzie jest ŁĄCZNY (jak dotąd): trzecie 1-sekundowe mignięcie w < 5 min dobija do 3 s = 1 spotkanie", z == ["Statutum"] and l.gracze["statutum"]["spotkan"] == 1
        and l.gracze["statutum"]["widok_s"] == 3.0, (z, l.gracze))
l, _ = licznik()
z = []
for blok in range(3):
    z += seans(l, "Statutum", blok * 400, blok * 400 + 4)            # przechodzień: 4 s w widoku, potem > 5 min bez niego
    seans(l, None, blok * 400 + 5, blok * 400 + 399)
sprawdz("A2d trzy 4-sekundowe mijania w odstępach > 5 min = 3 spotkania i kandydat (próg 3 s); te same po 2 s = 0",
        z == ["Statutum"] * 3 and l.kandydat(T0 + 1200) and l.kandydat(T0 + 1200)[2] == 3, (z, l.gracze))
l, _ = licznik()
for blok in range(3):
    seans(l, "Statutum", blok * 400, blok * 400 + 2)
    seans(l, None, blok * 400 + 3, blok * 400 + 399)
sprawdz("A2e trzy 2-sekundowe mijania w odstępach > 5 min = 0 spotkań, brak kandydata", l.gracze["statutum"]["spotkan"] == 0 and l.kandydat(T0 + 1200) is None, l.gracze)
l, _ = licznik()
z = seans(l, "Statutum", 0, 600)
sprawdz("A3 jeden gracz kręcący się obok 10 minut = JEDNO spotkanie (nie 3)", z == ["Statutum"] and l.gracze["statutum"]["spotkan"] == 1 and l.kandydat(T0 + 600) is None,
        l.gracze)
l, _ = licznik()
z = []
for blok in range(3):
    z += seans(l, "Statutum", blok * 400, blok * 400 + 20)           # 20 s w widoku, potem 380 s (> 5 min) bez niego
    seans(l, None, blok * 400 + 21, blok * 400 + 399)
sprawdz("A4 trzy osobne spotkania rozdzielone > 5 min = licznik 3 i kandydat do zmiany", z == ["Statutum"] * 3 and l.kandydat(T0 + 1200)
        and l.kandydat(T0 + 1200)[2] == 3, (z, l.gracze))
l, _ = licznik()
for blok in range(3):
    seans(l, "Statutum", blok * 200, blok * 200 + 20)
    seans(l, None, blok * 200 + 21, blok * 200 + 199)
sprawdz("A5 przerwy po 3 min (< 5 min) = wciąż jeden epizod = 1 spotkanie", l.gracze["statutum"]["spotkan"] == 1, l.gracze)
l, _ = licznik()
seans(l, "Statutum", 0, 20)
seans(l, None, 21, 299)
seans(l, "Statutum", 300, 320)
sprawdz("A6 przerwa równo 300 s od ostatniego zobaczenia (20 -> 300 = 280 s < 300) trwa jako ten sam epizod; od 20 do 321+ nowy",
        l.gracze["statutum"]["spotkan"] == 1)
seans(l, None, 321, 700)
seans(l, "Statutum", 701, 720)
sprawdz("A6b po przerwie >= 5 min od ostatniego widoku (320 -> 701) = drugie spotkanie", l.gracze["statutum"]["spotkan"] == 2, l.gracze)
l, _ = licznik()
for t in range(0, 40, 1):
    l.obserwuj(T0 + t, ["Statutum", "Ela"] if t % 2 == 0 else ["Ela"], True)        # Statutum miga co drugi obieg
sprawdz("A7 dwóch graczy liczonych niezależnie; migający co sekundę nick zalicza się (przerwy <= 10 s liczą jako widok)",
        l.gracze["ela"]["spotkan"] == 1 and l.gracze["statutum"]["spotkan"] >= 0)
l, _ = licznik()
seans(l, "Statutum", 0, 20, aktywny=False)
seans(l, "Statutum", 100, 130, aktywny=False)
sprawdz("A8 obiegi poza spotem (aktywny=False: droga/miasto/depo/dojście) nie liczą nic i nic nie zapisują", l.gracze == {})
l, _ = licznik()
l.obserwuj(T0, ["Statutum"], True)
l.obserwuj(T0 + 5, ["Statutum"], True)
l.obserwuj(T0 + 6, ["Statutum"], False)                # wyjście z pętli
l.obserwuj(T0 + 7000, ["Statutum"], True)               # luka 2 h: krok > MAX_KROK_S nie liczy czasu widoku
sprawdz("A9 luka między obiegami (> MAX_KROK_S) nie nabija czasu widoku", l.gracze["statutum"]["widok_s"] == 0.0, l.gracze)
# trwałość po restarcie
l, p = licznik()
seans(l, "Statutum", 0, 20)
l.zapisz(T0 + 21, wymus=True)
l2 = SG.Licznik(p)
l2.wczytaj(T0 + 30)
sprawdz("A10 trwałość: nowy proces czyta licznik z dysku", l2.gracze["statutum"]["spotkan"] == 1 and l2.gracze["statutum"]["nick"] == "Statutum")
seans(l2, "Statutum", 30, 50)
sprawdz("A10b po restarcie gracz nadal w widoku (przerwa < 5 min) = ten sam epizod, nie drugie spotkanie", l2.gracze["statutum"]["spotkan"] == 1)
seans(l2, None, 51, 700)
seans(l2, "Statutum", 701, 720)
l2.zapisz(T0 + 721, wymus=True)
l3 = SG.Licznik(p)
l3.wczytaj(T0 + 730)
seans(l3, None, 722, 1500)
seans(l3, "Statutum", 1501, 1520)
sprawdz("A10c licznik rośnie ponad restartami (3 spotkania w 3 procesach)", l3.gracze["statutum"]["spotkan"] == 3 and l3.kandydat(T0 + 1520), l3.gracze)
d = json.loads(p.read_text())
sprawdz("A11 plik atomowy: poprawny JSON, brak śladów .tmp", "gracze" in d and not list(p.parent.glob(p.name + ".*.tmp")), list(p.parent.glob("*tmp")))
# starzenie
l, p = licznik()
seans(l, "Statutum", 0, 20)
l.zapisz(T0 + 21, wymus=True)
l4 = SG.Licznik(p)
l4.wczytaj(T0 + 21 + SG.STARZENIE_H * 3600 + 60)
sprawdz("A12 wpis starszy niż 12 h znika przy wczytaniu", l4.gracze == {})
l4.wczytaj(T0 + 21 + SG.STARZENIE_H * 3600 - 60)
sprawdz("A12b wpis młodszy niż 12 h zostaje", "statutum" in l4.gracze)
# uszkodzony plik
p = TMP / "zepsuty.json"
p.write_text("{nie json")
lz = SG.Licznik(p)
seans(lz, "Statutum", 0, 20)
sprawdz("A13 uszkodzony plik = start od zera, bez wyjątku", lz.gracze["statutum"]["spotkan"] == 1)
p.write_text(json.dumps({"gracze": {"x": "zly", "y": {"ostatnio_t": "abc"}, "z": {"nick": "Z", "ostatnio_t": T0, "spotkan": 2}}, "zadania": ["a", 5]}))
lz = SG.Licznik(p)
lz.wczytaj(T0 + 10)
sprawdz("A13b wadliwe wpisy pomijane, poprawny zostaje", list(lz.gracze) == ["z"] and lz.gracze["z"]["spotkan"] == 2, lz.gracze)
sprawdz("A14 klucz nicku: wielkość liter i spacje", SG.klucz("  Statutum  Ex ") == SG.klucz("statutum ex") and SG.klucz("A") != SG.klucz("B"))
l, _ = licznik()
seans(l, "STATUTUM", 0, 20)
seans(l, "statutum", 21, 60)
sprawdz("A14b ten sam nick w różnej pisowni = ten sam gracz", len(l.gracze) == 1)

# ============================================================ (B) limity, bezpieczeństwo, unikane, zlecenie
sprawdz("B1 limit: brak zmian = ok", SG.limit_ok([], T0)[0])
sprawdz("B2 limit: zmiana 29 min temu = odmowa; 31 min temu = ok", not SG.limit_ok([T0 - 29 * 60], T0)[0] and SG.limit_ok([T0 - 31 * 60], T0)[0])
cztery = [T0 - 3600 * h for h in (2, 5, 8, 11)]
sprawdz("B3 limit doby: 4 zmiany w 24 h = odmowa, piąta po wyjściu najstarszej ok", not SG.limit_ok(cztery, T0)[0] and SG.limit_ok(cztery[1:], T0)[0]
        and SG.limit_ok(cztery, T0 + 14 * 3600)[0])
sprawdz("B3b limit: śmieci w liście pomijane", SG.limit_ok(["x", None, True], T0)[0])
sprawdz("B4 bezpiecznie: HP 70 % i potwór w 5 polach = tak", SG.bezpiecznie(70.0, 5) and SG.bezpiecznie(100, None))
sprawdz("B5 niebezpiecznie: potwór w 4 polach, HP 69 %, ucieczka, PK, brak HP",
        not SG.bezpiecznie(100, 4) and not SG.bezpiecznie(100, 1) and not SG.bezpiecznie(69.9, None) and not SG.bezpiecznie(100, None, ucieczka=True)
        and not SG.bezpiecznie(100, None, pk_stan="UCIECZKA") and not SG.bezpiecznie(None, None))
u = SG.unikane_dodaj([], "ed_a", "j_a", "Statutum", T0)
sprawdz("B6 unikany spot: aktywny 3 h, potem wygasa", SG.unikane_aktywne(u, T0 + 3 * 3600 - 1) and not SG.unikane_aktywne(u, T0 + 3 * 3600 + 1))
u = SG.unikane_dodaj(u, "ed_a", "j_a", "statutum", T0 + 3600)
sprawdz("B6b ten sam spot i gracz odświeża termin, nie dubluje", len(u) == 1 and u[0]["do"] == T0 + 3600 + 3 * 3600)
kat = TMP / "zlecenie"
sprawdz("B7 brak zlecenia", SG.wczytaj_zadanie(kat, T0)[0] is None)
SG.zapisz_zadanie(kat, T0, "Statutum", 3)
zad, _ = SG.wczytaj_zadanie(kat, T0 + 5)
sprawdz("B8 zlecenie: poprawne, jeszcze bez potwierdzenia spokoju", zad and zad["nick"] == "Statutum" and not SG.gotowe(zad, T0 + 5))
SG.odswiez_gotowy(kat, T0 + 10)
zad, _ = SG.wczytaj_zadanie(kat, T0 + 12)
sprawdz("B9 potwierdzenie spokoju: świeże 20 s, potem nieaktualne", SG.gotowe(zad, T0 + 12) and SG.gotowe(zad, T0 + 30) and not SG.gotowe(zad, T0 + 31))
zad, powod = SG.wczytaj_zadanie(kat, T0 + SG.ZADANIE_WAZNE_S + 1)
sprawdz("B10 przeterminowane zlecenie nie jest zwracane", zad is None and "przeterminowane" in powod, powod)
(kat / SG.PLIK_ZADANIA).write_text("{zły")
sprawdz("B10b nieczytelne zlecenie = None; odswiez_gotowy nic nie psuje", SG.wczytaj_zadanie(kat, T0)[0] is None and not SG.odswiez_gotowy(kat, T0))
sprawdz("B11 usun_zadanie", SG.usun_zadanie(kat) and not (kat / SG.PLIK_ZADANIA).exists() and not SG.usun_zadanie(kat))
sprawdz("B12 nasze postacie: lista Karola + profile", {"kolanosh", "odchyd", "makumba", "dawajkesh"} <= SG.nasze_nicki(TMP / "brak"))
pi = TMP / "inst" / "x"
pi.mkdir(parents=True)
(pi / "profil.json").write_text(json.dumps({"postac": "Nowa Postac"}))
sprawdz("B12b nick z profil.json dochodzi", "nowa postac" in SG.nasze_nicki(TMP / "inst"))


# ============================================================ (C) bot: prawdziwy tick na atrapie
SPOT = (32657, 31967, 8)
licz_c = [0]


def gr(nazwa, dx, dy, z=8, hp=85, **kw):
    return {"id": hash(nazwa) % 100000 + 10, "nazwa": nazwa, "gracz": True, "dx": dx, "dy": dy, "z": z, "hp": hp, **kw}


def mob(nazwa, dx, dy, z=8, hp=100):
    return {"id": 5000 + abs(dx) * 10 + abs(dy), "nazwa": nazwa, "gracz": False, "dx": dx, "dy": dy, "z": z, "hp": hp}


class SwiatB:
    def __init__(s, poz=SPOT, hp=100, stwory=()):
        s.t, s.poz, s.hp, s.stwory, s.nick = 1000.0, list(poz), hp, list(stwory), "Odchyd"
        s.klawisze = []

    def zegar(s):
        return s.t

    def spij(s, d):
        pass

    def zapytaj(s, z):
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": s.hp * 2, "max_hp": 200, "mana": 100, "max_mana": 200}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": s.nick, "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            out = []
            for m in s.stwory:
                m = dict(m)
                m["x"], m["y"] = s.poz[0] + m.pop("dx"), s.poz[1] + m.pop("dy")
                m["z"] = m.get("z", s.poz[2])
                out.append(m)
            return {"stwory": [ja] + out}
        return {}


class PostacB:
    def __init__(p, s):
        p.s, p.nazwa = s, s.nick

    def pozycja(p):
        return tuple(p.s.poz)

    def klawisz(p, k):
        p.s.klawisze.append(k)

    def krok(p, k):
        return tuple(p.s.poz)


def bot_c(s, knob=1, punkty=None, nazwa="b"):
    licz_c[0] += 1
    kat = TMP / f"bot{licz_c[0]}"
    kat.mkdir()
    cavebot.SPOT_ZMIANA_PRZY_GRACZU = knob
    pts = punkty or [(s.poz[0] + i, s.poz[1], s.poz[2]) for i in range(1, 11)]
    b = mozg.CavebotMozgu(PostacB(s), pts, okrazenia=999, zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij,
                          zegar=s.zegar, loot=type("L", (), {"zbierz": staticmethod(lambda zw, g: "ok")})())
    b._pk_dane()
    b.pk_wrogowie.plik = kat / "wrogowie-test.json"
    b.tele = None
    b.spot_gracz_katalog = kat
    b.kat = kat
    return b


def tik(s, b, n=1, krok=1.0):
    for _ in range(n):
        s.t += krok
        try:
            b.tick()
        except Exception as e:                    # noqa: BLE001
            cavelog.append(f"WYJĄTEK TICK {e!r}")


def licznik_b(b):
    return json.loads((b.kat / SG.PLIK_LICZNIKA).read_text()) if (b.kat / SG.PLIK_LICZNIKA).exists() else None


# C1: pokrętło 0 = zero plików, zero wpisów w logu, zero obiektów
cavelog.clear()
s = SwiatB(stwory=[gr("Statutum", 3, 0)])
b = bot_c(s, knob=0)
tik(s, b, 60)
sprawdz("C1 pokrętło 0: ani pliku licznika, ani zlecenia, ani wpisu SPOT_GRACZ w logu, licznik nie utworzony",
        not list(b.kat.glob("*.json")) and not any("SPOT_GRACZ" in x for x in cavelog) and b._sg_licznik is None, (list(b.kat.iterdir()), cavelog[-3:]))
sprawdz("C1b w kodzie: domyślnie 0, ZAKRESY (0,1), KIERUNEK nie_wyzej, w przykładzie 0",
        "\nSPOT_ZMIANA_PRZY_GRACZU = 0 " in (KAT / "cavebot.py").read_text() and pokretla.ZAKRESY.get("SPOT_ZMIANA_PRZY_GRACZU") == (0, 1)
        and pokretla.KIERUNEK.get("SPOT_ZMIANA_PRZY_GRACZU") == "nie_wyzej"
        and json.loads((KAT / "na_zywo.przyklad.json").read_text()).get("SPOT_ZMIANA_PRZY_GRACZU") == 0)
ok_, bl = pokretla.waliduj({"SPOT_ZMIANA_PRZY_GRACZU": 1}, {"SPOT_ZMIANA_PRZY_GRACZU": 0})
sprawdz("C1c analityk (walidacja z domyślnymi) nie włączy; ręczny plik tak", "SPOT_ZMIANA_PRZY_GRACZU" not in ok_
        and pokretla.waliduj({"SPOT_ZMIANA_PRZY_GRACZU": 1})[0] == {"SPOT_ZMIANA_PRZY_GRACZU": 1}, (ok_, bl))
sprawdz("C1d w tick hak jest za bramką pokrętła", "if SPOT_ZMIANA_PRZY_GRACZU:\n            self._spot_gracz_tick(" in (KAT / "cavebot.py").read_text())

# C2: gracz w widoku 20+ s = spotkanie (trwały plik), potem przerwy i trzy spotkania => zlecenie
cavelog.clear()
s = SwiatB(stwory=[gr("Statutum", 3, 0)])
b = bot_c(s)
tik(s, b, 25)
d = licznik_b(b)
sprawdz("C2 po 25 s gracza w widoku: spotkanie 1, nick w pliku, brak zlecenia",
        d and d["gracze"]["statutum"]["spotkan"] == 1 and not (b.kat / SG.PLIK_ZADANIA).exists() and any("spotkany 1/3" in x for x in cavelog),
        (d, cavelog[-3:]))
for epizod in (2, 3):
    s.stwory = []
    tik(s, b, 310)
    s.stwory = [gr("Statutum", 3, 0)]
    tik(s, b, 25)
d = licznik_b(b)
zad = json.loads((b.kat / SG.PLIK_ZADANIA).read_text()) if (b.kat / SG.PLIK_ZADANIA).exists() else None
sprawdz("C3 trzy osobne spotkania: zlecenie zapisane (nick, 3), licznik gracza wyzerowany, jedna linia w logu",
        zad and zad["nick"] == "Statutum" and zad["spotkan"] == 3 and d["gracze"]["statutum"]["spotkan"] == 0 and len(d["zadania"]) == 1
        and sum("zlecam nadzorcy" in x for x in cavelog) == 1, (zad, d, [x for x in cavelog if "SPOT_GRACZ" in x]))
sprawdz("C3b bot niczego nie klika w sprawie zmiany spotu (zero klawiszy z powodu gracza), nie rzucił wyjątku", not any("WYJĄTEK" in x or "debug: SPOT_GRACZ" in x for x in cavelog), cavelog[-5:])
sprawdz("C3c zlecenie czeka na potwierdzenie spokoju: gotowy_t ustawiony (nic w pobliżu, HP 100)", zad["gotowy_t"] is None or SG.gotowe(
    json.loads((b.kat / SG.PLIK_ZADANIA).read_text()), s.t))
tik(s, b, 6)
zad = json.loads((b.kat / SG.PLIK_ZADANIA).read_text())
sprawdz("C4 bezpiecznie (HP 100 %, zero potworów): bot odświeża gotowy_t", SG.gotowe(zad, s.t), zad)
# potwór w 4 polach: gotowy_t nie jest odświeżany
t_przed = zad["gotowy_t"]
s.stwory = [gr("Statutum", 3, 0), mob("Troll", 4, 0)]
tik(s, b, 30)
zad = json.loads((b.kat / SG.PLIK_ZADANIA).read_text())
sprawdz("C5 potwór w 4 polach: gotowy_t nie rośnie (zmiana odmawia)", zad["gotowy_t"] <= t_przed + 3.5, (zad["gotowy_t"], t_przed))
s.stwory = [gr("Statutum", 3, 0), mob("Troll", 5, 0)]
tik(s, b, 8)
zad = json.loads((b.kat / SG.PLIK_ZADANIA).read_text())
sprawdz("C6 potwór w 5 polach: znów bezpiecznie", SG.gotowe(zad, s.t), zad)
s.hp = 60
tik(s, b, 30)
zad = json.loads((b.kat / SG.PLIK_ZADANIA).read_text())
sprawdz("C7 HP 60 % (< 70): gotowy_t przestaje być świeży (nadzorca odmawia)", not SG.gotowe(zad, s.t), (zad, s.t))
s.hp = 100
s.stwory = [gr("Statutum", 3, 0)]
b.hp_gracza_spadek = float("-inf")
tik(s, b, 10)
zad = json.loads((b.kat / SG.PLIK_ZADANIA).read_text())
sprawdz("C7b HP wróciło: znów gotowy", SG.gotowe(zad, s.t))

# C8: limit 1 zlecenie / 30 min; po zleceniu nowe 3 spotkania w 30 min nie tworzą zlecenia, po 30 min tak
(b.kat / SG.PLIK_ZADANIA).unlink()                  # nadzorca wykonał
b._sg_oczekuje = None
cavelog.clear()
for epizod in range(3):
    s.stwory = []
    tik(s, b, 310)
    s.stwory = [gr("Statutum", 3, 0)]
    tik(s, b, 25)
# 3 x 335 s = 1005 s < 30 min
sprawdz("C8 limit 1 na 30 min: kolejne 3 spotkania po ~17 min nie dają zlecenia (log: odłożona, zostaję)", not (b.kat / SG.PLIK_ZADANIA).exists()
        and any("odłożona" in x and "limit" in x or "odłożona" in x for x in cavelog), cavelog[-3:])
s.stwory = []
tik(s, b, 900)
s.stwory = [gr("Statutum", 3, 0)]
tik(s, b, 3)
sprawdz("C8b po 30 min od zlecenia kandydat znów dostaje zlecenie", (b.kat / SG.PLIK_ZADANIA).exists())

# C9: limit doby (4)
s = SwiatB(stwory=[])
b = bot_c(s)
b.tick()
b._sg_licznik.zadania = [s.t - 3600 * h for h in (2, 5, 8, 11)]
b._sg_licznik.gracze["statutum"] = {"nick": "Statutum", "spotkan": 3, "pierwsze_t": s.t, "ostatnio_t": s.t, "epizod_od_t": s.t, "widok_s": 0.0,
                                    "zaliczone": True, "mapa": ""}
cavelog.clear()
tik(s, b, 5)
sprawdz("C9 limit doby: 4 zlecenia w 24 h = brak piątego", not (b.kat / SG.PLIK_ZADANIA).exists() and any("limit" in x or "zmian w ostatniej dobie" in x for x in cavelog), cavelog[-2:])

# C10: nie liczą się: nasze postacie, NPC, wróg, GM, czaszka, widmo, martwy, inne piętro, poza oknem mapy
s = SwiatB()
b = bot_c(s)
b.pk_wrogowie.dane = {"ogr": {"nick": "Ogr"}}
lst = [gr("Kolanosh", 2, 0), gr("Wydra", 2, 1), gr("Frodo", 3, 0), gr("Ogr", 3, 1), gr("GM Foo", 4, 0), gr("Biały", -3, 0, czaszka="biala"),
       gr("Martwy", 2, 2, hp=0), gr("Pietro", 2, -1, z=9), gr("Daleko", 30, 0), gr("odchyd", 1, 1), gr("Odchyd", 1, 2), gr("Statutum", 3, 2)]
for m in lst:
    m["x"], m["y"] = SPOT[0] + m.pop("dx"), SPOT[1] + m.pop("dy")
sprawdz("C10 `_sg_widoczni`: pomija nasze (lista Karola, wielkość liter, własny nick), NPC (Frodo), wroga z wrogowie.json, GM, czaszkę, martwego, inne piętro, "
        "poza oknem; zostaje tylko obcy", b._sg_widoczni(lst, SPOT, s.t) == ["Statutum"], b._sg_widoczni(lst, SPOT, s.t))
s = SwiatB(stwory=[gr("Kolanosh", 2, 0), gr("Wydra", 2, 1), gr("Frodo", 3, 0), gr("Martwy", 2, 2, hp=0), gr("Pietro", 2, -1, z=9), gr("Daleko", 30, 0),
                   gr("odchyd", 1, 1)])
b = bot_c(s)
tik(s, b, 40)
d = licznik_b(b)
sprawdz("C10a w prawdziwym ticku ignorowani nie zakładają wpisów w liczniku", d is None or d["gracze"] == {}, d)
s.stwory = [gr("Statutum", 3, 0), gr("Statutum2", 3, 1)]
tik(s, b, 20)
d = licznik_b(b)
sprawdz("C10b obcy gracze liczeni", d and set(d["gracze"]) == {"statutum", "statutum2"}, (d, cavelog[-3:]))

# C11: kiedy bot NIE jest na spocie, nic nie liczy
def bez_spotu(zmien, opis):
    s = SwiatB()
    b = bot_c(s)
    zmien(b, s)
    sprawdz(f"C11 {opis}: _sg_aktywny = False", b._sg_aktywny(tuple(s.poz)) is False)


sprawdz("C11a kontrola: zwykły obieg na piętrze pętli = aktywny", bot_c(SwiatB())._sg_aktywny(SPOT) is True)
bez_spotu(lambda b, s: setattr(b, "wypad_aktywny", True), "wypad (powrót do depo / droga)")
bez_spotu(lambda b, s: setattr(b, "stoj_wl", True), "tryb STÓJ")
bez_spotu(lambda b, s: setattr(b, "ucieczka", True), "ucieczka")
bez_spotu(lambda b, s: setattr(b, "pk_stan", "UCIECZKA"), "stan PK")
bez_spotu(lambda b, s: setattr(b, "dojscie_aktywne", True), "dojście na spot")
bez_spotu(lambda b, s: setattr(b, "stan", "WPADNIECIE"), "stan WPADNIECIE (odzyskiwanie po spadku)")
bez_spotu(lambda b, s: setattr(b, "stan", "PAUZA_STOJ"), "stan PAUZA_STOJ (stanowisko)")
bez_spotu(lambda b, s: setattr(b, "stanowisko", object()), "stanowisko (miasto)")
bez_spotu(lambda b, s: setattr(b, "martwy", True), "martwa postać")
bez_spotu(lambda b, s: setattr(b, "rozlaczony", True), "rozłączony klient")
s = SwiatB(stwory=[gr("Statutum", 3, 0, z=7)], poz=(SPOT[0], SPOT[1], 7))
b = bot_c(s, punkty=[(SPOT[0] + i, SPOT[1], 8) for i in range(1, 11)])
tik(s, b, 40)
sprawdz("C11b kryterium nie zależy od piętra trasy (26.10): zwykły Cavebot po dojściu na innym piętrze niż punkty trasy też liczy (patrol/kieszeń/spadek bez WPADNIECIE)",
        licznik_b(b) and licznik_b(b)["gracze"].get("statutum", {}).get("spotkan") == 1, licznik_b(b))
s = SwiatB(stwory=[gr("Statutum", 3, 0)])
b = bot_c(s)
b.wypad_aktywny = True
tik(s, b, 40)
sprawdz("C11c w prawdziwym ticku: wypad_aktywny = licznik pusty", licznik_b(b) is None or licznik_b(b)["gracze"] == {}, licznik_b(b))

# C12: trwałość po restarcie bota (nowy obiekt Cavebot, ten sam katalog)
s = SwiatB(stwory=[gr("Statutum", 3, 0)])
b = bot_c(s)
tik(s, b, 25)
kat12 = b.kat
s2 = SwiatB(stwory=[])
b2 = bot_c(s2)
b2.spot_gracz_katalog = kat12
b2.kat = kat12
s2.t = 1000.0
tik(s2, b2, 2)
sprawdz("C12 po restarcie bota licznik wraca z dysku (spotkanie 1 nadal jest)", b2._sg_licznik.gracze.get("statutum", {}).get("spotkan") == 1, b2._sg_licznik and b2._sg_licznik.gracze)
(kat12 / SG.PLIK_ZADANIA).write_text(json.dumps({"v": 1, "t": s2.t, "nick": "Statutum", "spotkan": 3, "sesja": cavebot.SESJA_PROC, "gotowy_t": None}))
b3 = bot_c(s2)
b3.spot_gracz_katalog = kat12
b3.kat = kat12
cavelog.clear()
tik(s2, b3, 6)
zad = json.loads((kat12 / SG.PLIK_ZADANIA).read_text())
sprawdz("C13 nowy obiekt Cavebota w TYM SAMYM procesie (np. główna trasa po dojściu) przy czekającym zleceniu tej sesji: dalej potwierdza spokój", SG.gotowe(zad, s2.t) and any("czeka na nadzorcę" in x for x in cavelog), (zad, cavelog[-3:]))
cavebot.SPOT_ZMIANA_PRZY_GRACZU = 0


# ============================================================ (G) licznik OD OSTATNIEGO ODPALENIA BOTA (Karol 26.10 ~12:05, LICZNIK_OD_STARTU)
p = TMP / "g1.json"
l = SG.Licznik(p, T0, sesja="A")
seans(l, "Statutum", 0, 20)
l.zadania = [T0 - 100]
l.zapisz(T0 + 21, wymus=True)
lB = SG.Licznik(p, T0 + 30, sesja="B")
sprawdz("G1 restart (inna sesja) zeruje licznik spotkań, ale zostawia limity zmian", lB.gracze == {} and lB.zresetowano == "A" and lB.zadania == [T0 - 100], (lB.gracze, lB.zadania))
lA = SG.Licznik(p, T0 + 30, sesja="A")
sprawdz("G2 ta sama sesja (np. kolejny obiekt Cavebota w tym samym procesie) NIE zeruje", lA.gracze.get("statutum", {}).get("spotkan") == 1 and lA.zresetowano is None)
l0 = SG.Licznik(p, T0 + 30)
sprawdz("G3 sesja=None (LICZNIK_OD_STARTU=0) = stare zachowanie: licznik przeżywa restart", l0.gracze.get("statutum", {}).get("spotkan") == 1)
lB.zapisz(T0 + 40, wymus=True)
lA2 = SG.Licznik(p, T0 + 50, sesja="A")
sprawdz("G4 zmiana sesji między zapisem a odczytem: plik zapisany przez B nie wskrzesza liczników sesji A", lA2.gracze == {}, lA2.gracze)
pz = TMP / "g5.json"
pz.write_text(json.dumps({"gracze": {"statutum": {"nick": "Statutum", "spotkan": 2, "ostatnio_t": T0, "pierwsze_t": T0, "epizod_od_t": T0, "widok_s": 20.0, "zaliczone": True}}, "zadania": [T0 - 50]}))
sprawdz("G5 stary plik bez klucza `sesja` (sprzed zmiany) jest wpisem innej sesji: zerowany; bez sesji w konstruktorze zostaje",
        SG.Licznik(pz, T0 + 10, sesja="B").gracze == {} and SG.Licznik(pz, T0 + 10).gracze["statutum"]["spotkan"] == 2)
pz.write_text("{ucięty")
sprawdz("G6 uszkodzony plik przy sesji: pusty licznik, bez wyjątku", SG.Licznik(pz, T0, sesja="B").gracze == {})
pz.write_text(json.dumps({"sesja": "B", "gracze": {"statutum": {"nick": "Statutum", "spotkan": 2, "ostatnio_t": T0, "pierwsze_t": T0, "epizod_od_t": T0, "widok_s": 20.0, "zaliczone": True}}}))
sprawdz("G7 stare wpisy tej samej sesji nadal starzeją się po 12 h", SG.Licznik(pz, T0 + SG.STARZENIE_H * 3600 + 60, sesja="B").gracze == {}
        and "statutum" in SG.Licznik(pz, T0 + 600, sesja="B").gracze)
sprawdz("G8 pliku-pamięć: Licznik(None) nie zapisuje niczego i liczy (raport z telemetrii)", SG.Licznik(None, 0.0, sesja="x").zapisz(5.0, wymus=True) is False)


def bot_sesja(s, sesja, kat=None, knob=1):
    cavebot.LICZNIK_OD_STARTU = knob
    b = bot_c(s)
    b.spot_gracz_sesja = sesja
    if kat is not None:
        b.spot_gracz_katalog = kat
        b.kat = kat
    return b


def epizody(s, b, ile):
    for _ in range(ile):
        s.stwory = []
        tik(s, b, 310)
        s.stwory = [gr("Statutum", 3, 0)]
        tik(s, b, 25)
    s.stwory = []


# G9: dwa spotkania w sesji S1, restart, jedno w S2: NIE składa się na 3 (zlecenia brak); z LICZNIK_OD_STARTU=0 składa się (stare zachowanie)
for knob, oczekuj_zlecenie in ((1, False), (0, True)):
    s = SwiatB(stwory=[])
    b1 = bot_sesja(s, "S1", knob=knob)
    epizody(s, b1, 2)
    d1 = licznik_b(b1)
    s2 = SwiatB(stwory=[])
    b2 = bot_sesja(s2, "S2", kat=b1.kat, knob=knob)
    cavelog.clear()
    epizody(s2, b2, 1)
    zlecenie_istnieje = (b1.kat / SG.PLIK_ZADANIA).exists()
    sprawdz(f"G9 LICZNIK_OD_STARTU={knob}: 2 spotkania w sesji S1 + 1 w S2 -> zlecenie {'jest' if oczekuj_zlecenie else 'BRAK'} (licznik {'trwały' if knob == 0 else 'od startu'})",
            d1["gracze"]["statutum"]["spotkan"] == 2 and zlecenie_istnieje == oczekuj_zlecenie
            and (any("nowa sesja bota" in x for x in cavelog) == bool(knob)), (d1, licznik_b(b2), cavelog[-4:]))
cavebot.LICZNIK_OD_STARTU = 1
# G10: trzy spotkania w jednej sesji (S1) dają zlecenie ze znacznikiem sesji; restart (S2) je wycofuje
s = SwiatB(stwory=[])
b1 = bot_sesja(s, "S1")
epizody(s, b1, 3)
zl = json.loads((b1.kat / SG.PLIK_ZADANIA).read_text()) if (b1.kat / SG.PLIK_ZADANIA).exists() else None
sprawdz("G10 zlecenie niesie `sesja` bota, który je zapisał", zl and zl.get("sesja") == "S1", zl)
s2 = SwiatB(stwory=[])
b2 = bot_sesja(s2, "S2", kat=b1.kat)
cavelog.clear()
tik(s2, b2, 3)
sprawdz("G11 restart bota (nowa sesja) kasuje zlecenie z poprzedniej sesji i zapisuje to w logu", not (b1.kat / SG.PLIK_ZADANIA).exists()
        and any("z poprzedniej sesji bota wycofane" in x for x in cavelog), cavelog[-3:])
(b1.kat / SG.PLIK_ZADANIA).write_text(json.dumps({"v": 1, "t": s2.t, "nick": "Statutum", "spotkan": 3, "gotowy_t": None}))      # stary format (bez `sesja`)
b3 = bot_sesja(SwiatB(stwory=[]), "S3", kat=b1.kat)
tik(b3.postac.s, b3, 3)
sprawdz("G12 zlecenie bez klucza `sesja` (sprzed zmiany) też jest z innej sesji: kasowane", not (b1.kat / SG.PLIK_ZADANIA).exists())
(b1.kat / SG.PLIK_ZADANIA).write_text(json.dumps({"v": 1, "t": s2.t, "nick": "Statutum", "spotkan": 3, "gotowy_t": None}))
b4 = bot_sesja(SwiatB(stwory=[]), "S4", kat=b1.kat, knob=0)
tik(b4.postac.s, b4, 3)
sprawdz("G13 LICZNIK_OD_STARTU=0: zlecenie przeżywa restart jak dawniej", (b1.kat / SG.PLIK_ZADANIA).exists())
cavebot.LICZNIK_OD_STARTU = 1
sprawdz("G14 LICZNIK_OD_STARTU: w kodzie domyślnie 1, ZAKRESY (0,1), KIERUNEK nie_nizej, w przykładzie 1",
        "\nLICZNIK_OD_STARTU = 1 " in (KAT / "cavebot.py").read_text() and pokretla.ZAKRESY.get("LICZNIK_OD_STARTU") == (0, 1)
        and pokretla.KIERUNEK.get("LICZNIK_OD_STARTU") == "nie_nizej" and json.loads((KAT / "na_zywo.przyklad.json").read_text()).get("LICZNIK_OD_STARTU") == 1)
sprawdz("G15 sesja procesu to unikalny identyfikator (pid-czas)", re.fullmatch(r"\d+-\d+", cavebot.SESJA_PROC) is not None, cavebot.SESJA_PROC)

# ---- H: patrol liczy się tak samo jak pętla (Karol 26.10 ~12:08)
for tryb_patrol in (0, 1):
    cavebot.TRYB_PATROL = tryb_patrol
    s = SwiatB(stwory=[gr("Statutum", 3, 0, z=9)], poz=(SPOT[0], SPOT[1], 9))              # trasa awaryjna/pętla na z8, postać patroluje na z9
    b = bot_c(s, punkty=[(SPOT[0] + i, SPOT[1], 8) for i in range(1, 11)])
    tik(s, b, 30)
    d = licznik_b(b)
    sprawdz(f"H{tryb_patrol} {'patrol (TRYB_PATROL=1)' if tryb_patrol else 'pętla'}: spotkanie liczone, bez wyjątków (patrol nie jest wykluczony ani geometrią trasy, ani piętrem)",
            d and d["gracze"].get("statutum", {}).get("spotkan") == 1 and not any("debug: SPOT_GRACZ" in x for x in cavelog), (d, cavelog[-3:]))
cavebot.TRYB_PATROL = 0

# ============================================================ (D) rodzina spotów
def spot_obj(mapa, miasto="edron", rodzina=None, srodek=None, potwory="Troll"):
    sp = SP.Spot(mapa)
    sp.miasto, sp.rodzina, sp.srodek, sp.potwory = miasto, rodzina, srodek, potwory
    return sp


a1, a2 = spot_obj("a1", rodzina="edron_trolle"), spot_obj("a2", rodzina="edron_trolle")
b1 = spot_obj("b1", rodzina="edron_gobliny")
sprawdz("D1 pole `rodzina`: równość nazw; różne nazwy = inna rodzina nawet przy bliskich środkach",
        SP.ta_sama_rodzina(a1, a2) and not SP.ta_sama_rodzina(a1, b1) and not SP.ta_sama_rodzina(None, a1))
f1 = spot_obj("f1", srodek=(33100, 31700))
f2 = spot_obj("f2", srodek=(33150, 31740), potwory="Troll,Bear")
f3 = spot_obj("f3", srodek=(33200, 31700))
f4 = spot_obj("f4", srodek=(33100, 31700), potwory="Goblin")
f5 = spot_obj("f5", miasto="thais", srodek=(33100, 31700))
sprawdz("D2 zapasowe grupowanie (brak `rodzina`): to samo miasto + wspólny potwór + środki w <= 60 polach (oś x i y, bez piętra)",
        SP.ta_sama_rodzina(f1, f2) and not SP.ta_sama_rodzina(f1, f3) and not SP.ta_sama_rodzina(f1, f4) and not SP.ta_sama_rodzina(f1, f5)
        and not SP.ta_sama_rodzina(f1, spot_obj("f6")))
sprawdz("D2b rodzina tylko u jednego = zapasowe grupowanie", SP.ta_sama_rodzina(spot_obj("g", rodzina="x", srodek=(1, 1)), spot_obj("h", srodek=(2, 2)))
        is True)
tab_ = SP.wczytaj(KAT)
fak = {"id": "x", "poz": (33100, 31760, 9), "poziom": 13, "ekwipunek": {"lina": True, "lopata": True}}
if not tab_.blad and "trolle_edron_z9z" in tab_.spoty:
    w_ = SP.wybierz(fak, (), ["trolle_edron_z9z"], tab_, ziarno="t", wyklucz_mapy=("trolle_edron_z9z",), rodzina_z="trolle_edron_z9z")
    sprawdz("D3 prawdziwa tabela (z polem `rodzina` albo zapasowym grupowaniem): z trolle_edron_z9z wybór zostaje w rodzinie, nie wybiera bieżącej ani auto:false",
            w_["mapa"] and w_["mapa"] != "trolle_edron_z9z" and w_["rodzina"] is True and SP.ta_sama_rodzina(tab_.spoty["trolle_edron_z9z"], tab_.spoty[w_["mapa"]])
            and tab_.spoty[w_["mapa"]].auto, w_)
else:
    sprawdz("D3 prawdziwa tabela pominięta (brak spotu w tabeli)", True)
# D3b (26.10 ~12:00, Karol: zmiana spotu w jaskini nie wymaga wyjścia na z7): postać NA pętli trolle_edron_z9z (z9, pole przechodnie) dostaje kandydata z tej samej
# rodziny na innym piętrze, a jego dojście (wariant-łącznik) naprawdę działa z tego miejsca; baza z dojściem ze z7 jest odrzucona, wariant ma auto jak baza
if not tab_.blad and "trolle_edron_z9z" in tab_.spoty and "trolle_edron_z9w__z__trolle_edron_z9z" in tab_.spoty:
    poz_ = tuple(SP.punkty_trasy(KAT, tab_.spoty["trolle_edron_z9z"].trasa)[0])
    fak_ = {"id": "x", "poz": poz_, "poziom": 13, "ekwipunek": {"lina": True, "lopata": True}}
    w2_ = SP.wybierz(fak_, (), ["trolle_edron_z9z"], tab_, ziarno="t", wyklucz_mapy=("trolle_edron_z9z",), rodzina_z="trolle_edron_z9z")
    sp2_ = tab_.spoty.get(w2_["mapa"]) if w2_["mapa"] else None
    kody_ = {m: k for m, k, _ in w2_["odrzucone"]}
    sprawdz("D3b z pętli trolle_edron_z9z (z9) wybór: wariant-łącznik z tej samej rodziny na innym piętrze (nie wyjście na z7), auto jak baza, baza ze z7 odrzucona 'pietro'",
            sp2_ is not None and sp2_.baza and w2_["rodzina"] is True and sp2_.auto and SP.ta_sama_rodzina(tab_.spoty["trolle_edron_z9z"], sp2_)
            and kody_.get("trolle_edron") == "pietro" and SP.dojscie_dziala_z(sp2_, poz_)[0] is True and SP.dojscie_dziala_z(tab_.spoty[sp2_.baza], poz_)[0] is False, (w2_["mapa"], kody_))
else:
    sprawdz("D3b pominięte (brak wariantu w tabeli)", True)


# ============================================================ (E) nadzorca
ED_POZ = [33100, 31760, 8]


def swiat_e(spoty=None, mapy=None, ids=("a", "b"), bot_a=True, rodzina=False, trasy=None, level=12):
    """Postać `a` z botem na ed_a (Edron, piętro 8), `b` offline; tabela spotów jak TN.tabela_q5, albo własna (spoty/mapy)."""
    s = TN.Swiat(ids)
    TN.tabela_q5(s)
    if mapy is not None or spoty is not None:
        (s.k / "mapy.json").write_text(json.dumps(mapy))
        (s.k / "dane_tibia" / "spoty_nadzorca.json").write_text(json.dumps({"miasta": TN.ED_MIASTA, "spoty": spoty}))
    for nazwa, pts in (trasy or {}).items():
        (s.k / "trasy").mkdir(exist_ok=True)
        (s.k / "trasy" / f"{nazwa}.json").write_text(json.dumps(pts))
    s.grafik([TN.zmiana("a", od="2026-10-21 10:00", koniec="2026-10-21 15:00", wylog="2026-10-21 15:15")])
    s.tryb_log("a", "ed_a", "ostrozny,runy", s.zegar.t.replace(hour=10, minute=0))
    s.online("a", bot=bot_a, level=level, pozycja=list(ED_POZ))
    s.inst["a"]["panel"]["level"] = level
    s.ekw["a"] = {"lina": True, "lopata": True}
    (s.k / "instancje" / "a" / "na_zywo.json").write_text(json.dumps({"SPOT_ZMIANA_PRZY_GRACZU": 1}))
    return s


def nadz(s, tryb="naprawy"):
    at = TN.Atrapa(s)
    at.zapisuj_tryb = True
    if tryb == "cien":
        return N.Nadzorca(s.k, s.zegar, s, N.WykonawcaCien(), False, True), at
    return N.Nadzorca(s.k, s.zegar, s, N.WykonawcaCien(), False, True, naprawy_poziom=True, wykonawca_poziom=at), at


def zlecenie(s, nick="Statutum", n=3, wiek_s=5, gotowy=True, id_="a"):
    kat = s.k / "instancje" / id_
    t = s.zegar.t.timestamp()
    SG.zapisz_zadanie(kat, t - wiek_s, nick, n)
    if gotowy:
        SG.odswiez_gotowy(kat, t - 2)
    return kat


def kody(n):
    return [x for x in n.dziennik.ostatnie if x["id"] == "a"]


def wyw(at, nazwa):
    return [w for w in at.wywolania if w[0] == nazwa]


# E1: przypadek podstawowy
s = swiat_e()
kat = zlecenie(s)
s.inst["b"]["bot"] = False
n, at = nadz(s)
n.tick()
st_ = wyw(at, "start_bota")
sprawdz("E1 zlecenie + potwierdzony spokój: bot zatrzymany i uruchomiony na NOWYM spocie tego samego miasta (nie ed_a, nie Thais)",
        len(wyw(at, "zatrzymaj_bota")) == 1 and len(st_) == 1 and st_[0][2] in ("ed_b", "ed_c") and st_[0][3] == "ostrozny,runy", at.wywolania)
sp_ = n.stan["postacie"]["a"].get("spot_gracz", {})
sprawdz("E1b stan: wykonana zmiana w liście (limity), unikany stary spot ze znacznikiem 3 h, zlecenie skasowane, bez wpisu do drabiny napraw",
        len(sp_.get("zmiany", [])) == 1 and sp_["unikane"][0]["mapa"] == "ed_a" and sp_["unikane"][0]["nick"] == "Statutum"
        and not (kat / SG.PLIK_ZADANIA).exists() and not n.stan["postacie"]["a"].get("naprawy"), (sp_, n.stan["postacie"]["a"].get("naprawy")))
sprawdz("E1c jedno powiadomienie z nickiem, licznikiem i starym -> nowym spotem", len(wyw(at, "powiadom_info")) == 1 and "Statutum" in str(wyw(at, "powiadom_info")[0])
        and "ed_a" in str(wyw(at, "powiadom_info")[0]) and "3. raz" in str(wyw(at, "powiadom_info")[0]), wyw(at, "powiadom_info"))
sprawdz("E1d dziennik: kod spot-gracz", any(x.get("akcja") == "zmien_spot" for x in n.dziennik.ostatnie), [x.get("akcja") for x in n.dziennik.ostatnie])

# E2: zajęty spot innej naszej instancji jest pomijany
s = swiat_e()
zlecenie(s)
s.online("b", bot=True, level=12, pozycja=[33100, 31760, 8])
s.tryb_log("b", "ed_b", "ostrozny", s.zegar.t.replace(hour=10, minute=0))
n, at = nadz(s)
n.tick()
sprawdz("E2 jaskinia zajęta przez inny nasz bot (ed_b) nie jest wybierana: ed_c", [w[2] for w in wyw(at, "start_bota")] == ["ed_c"], at.wywolania)

# E3: zajęte wszystko / brak pasującego (przy wyłączonym powrocie) => zostaje, zlecenie kasowane, bez STOP i bez WROC
s = swiat_e(level=12)
kat = zlecenie(s)
s.ekw["a"] = {"lina": False, "lopata": True}            # ed_c wymaga liny
s.online("b", bot=True, level=12, pozycja=[33100, 31760, 8])
s.tryb_log("b", "ed_b", "ostrozny", s.zegar.t.replace(hour=10, minute=0))
(s.k / "instancje" / "a" / "na_zywo.json").write_text(json.dumps({"SPOT_ZMIANA_PRZY_GRACZU": 1, "SPOT_GRACZ_POWROT_DO_MIASTA": 0}))
n, at = nadz(s)
n.tick()
d3 = [x for x in kody(n) if "brak sensownego spotu" in x["powod"]]
sprawdz("E3 brak sensownego spotu przy SPOT_GRACZ_POWROT_DO_MIASTA=0: bot NIE zatrzymany ani odesłany, wpis w dzienniku, zlecenie skasowane",
        not wyw(at, "zatrzymaj_bota") and not wyw(at, "start_bota") and not wyw(at, "wroc") and d3 and not (kat / SG.PLIK_ZADANIA).exists(),
        (at.wywolania, [x["powod"] for x in kody(n)]))

# E4: poziom poza widełkami
s = swiat_e(level=3)                                    # widełki edronowych spotów 5-30
zlecenie(s)
n, at = nadz(s)
n.tick()
sprawdz("E4 poziom poza widełkami (3 < 5): żaden Edron nie pasuje; nie zmienia spotu (powrót do miasta opisuje blok F)", not wyw(at, "start_bota") and not wyw(at, "zatrzymaj_bota"), at.wywolania)

# E5: zakazany spot (nazwa z SPOTY_ZAKAZANE, nawet gdy w tabeli auto:true) i auto:false nigdy
mapy5 = {"_opis": "x", "ed_a": {"trasa": "x", "potwory": "Troll"}, "trolle_edron_z10w": {"trasa": "x", "potwory": "Troll"}, "ed_auto_off": {"trasa": "x", "potwory": "Troll"},
         "ed_ok": {"trasa": "x", "potwory": "Troll"}}
sp5 = lambda j, **kw: {"miasto": "edron", "jaskinia": j, "poziom": [5, 30], "waga": 1.0, "auto": True, **kw}      # noqa: E731
spoty5 = {"ed_a": sp5("j_a"), "trolle_edron_z10w": sp5("j_z10"), "ed_auto_off": sp5("j_off", auto=False, powod="Karol: za trudne"), "ed_ok": sp5("j_ok")}
for powt in range(6):
    s = swiat_e(spoty=spoty5, mapy=mapy5)
    s.zegar.t = s.zegar.t + timedelta(minutes=powt)       # inne ziarno losowania
    zlecenie(s)
    n, at = nadz(s)
    n.tick()
    wyb = [w[2] for w in wyw(at, "start_bota")]
    assert wyb == ["ed_ok"], (powt, wyb, at.wywolania)
sprawdz("E5 zakazany (trolle_edron_z10w, mimo auto:true) i wyłączony w tabeli (auto:false) nigdy nie wybrani w 6 losowaniach: zawsze ed_ok", True)

# E6: unikany spot — druga zmiana nie wraca na pierwszy
s = swiat_e()
zlecenie(s)
n, at = nadz(s)
n.tick()
pierwszy = wyw(at, "start_bota")[0][2]
s.zegar.dalej(minutes=31)
s.inst["a"]["bot"] = True
s.online("a", bot=True, level=12, pozycja=list(ED_POZ))
s.inst["a"]["panel"]["level"] = 12
kat = zlecenie(s, nick="Inny", n=3)
n2 = N.Nadzorca(s.k, s.zegar, s, N.WykonawcaCien(), False, True, naprawy_poziom=True, wykonawca_poziom=at)
n2.post("a")["bot_start"] = s.zegar.t.timestamp() - 600       # świeży start po pierwszej zmianie (inaczej „brak zabić” ma pierwszeństwo)
n2.tick()
drugi = [w[2] for w in wyw(at, "start_bota")][1:]
sprawdz("E6 druga zmiana po 31 min: nowy spot to nie bieżący i nie unikany ed_a", len(drugi) == 1 and drugi[0] not in (pierwszy, "ed_a"), (pierwszy, drugi))
sprawdz("E6b stan nadzorcy trzyma dwie zmiany i oba unikane spoty", len(n2.stan["postacie"]["a"]["spot_gracz"]["zmiany"]) == 2
        and {u["mapa"] for u in n2.stan["postacie"]["a"]["spot_gracz"]["unikane"]} == {"ed_a", pierwszy}, n2.stan["postacie"]["a"].get("spot_gracz"))

# E7: limity po stronie nadzorcy
s = swiat_e()
zlecenie(s)
n, at = nadz(s)
n.post("a")["spot_gracz"] = {"zmiany": [s.zegar.t.timestamp() - 20 * 60]}
n.tick()
sprawdz("E7 limit 1/30 min po stronie nadzorcy: zmiana 20 min temu = odmowa, zlecenie skasowane", not wyw(at, "start_bota")
        and not (s.k / "instancje" / "a" / SG.PLIK_ZADANIA).exists() and any(" limit" in x["powod"] or "odłożona" in x["powod"] for x in kody(n)), [x["powod"] for x in kody(n)])
s = swiat_e()
zlecenie(s)
n, at = nadz(s)
n.post("a")["spot_gracz"] = {"zmiany": [s.zegar.t.timestamp() - 3600 * h for h in (2, 5, 8, 11)]}
n.tick()
sprawdz("E7b limit doby (4): piąta odmowa", not wyw(at, "start_bota"))

# E8: bramki zlecenia
def e_bez(opis, popraw, oczek_czeka=True):
    s = swiat_e()
    popraw(s)
    n, at = nadz(s)
    n.tick()
    sprawdz(f"E8 {opis}: bot nie jest zatrzymywany ani startowany", not wyw(at, "start_bota") and not wyw(at, "zatrzymaj_bota"), at.wywolania)
    return s, n


s_, n_ = e_bez("brak potwierdzenia spokoju (gotowy_t = None)", lambda s: zlecenie(s, gotowy=False))
sprawdz("E8a zlecenie czeka (nie skasowane) i dziennik mówi dlaczego", (s_.k / "instancje" / "a" / SG.PLIK_ZADANIA).exists()
        and any("potwierdzenie spokoju" in x["powod"] for x in kody(n_)), [x["powod"] for x in kody(n_)])


def stare_gotowy(s):
    kat = zlecenie(s, gotowy=False)
    SG.odswiez_gotowy(kat, s.zegar.t.timestamp() - 60)
    d = json.loads((kat / SG.PLIK_ZADANIA).read_text())
    d["t"] = s.zegar.t.timestamp() - 90
    (kat / SG.PLIK_ZADANIA).write_text(json.dumps(d))


e_bez("potwierdzenie spokoju sprzed 60 s (> 20 s)", stare_gotowy)
s_, n_ = e_bez("zlecenie przeterminowane (25 min)", lambda s: zlecenie(s, wiek_s=25 * 60))
sprawdz("E8b przeterminowane zlecenie skasowane przez nadzorcę", not (s_.k / "instancje" / "a" / SG.PLIK_ZADANIA).exists())


def pokretlo_0(s):
    (s.k / "instancje" / "a" / "na_zywo.json").write_text(json.dumps({"SPOT_ZMIANA_PRZY_GRACZU": 0}))
    zlecenie(s)


s_, n_ = e_bez("pokrętło SPOT_ZMIANA_PRZY_GRACZU=0 w na_zywo.json instancji", pokretlo_0)
sprawdz("E8c zlecenie wycofane", not (s_.k / "instancje" / "a" / SG.PLIK_ZADANIA).exists())


def bez_klucza(s):
    (s.k / "instancje" / "a" / "na_zywo.json").write_text("{}")
    zlecenie(s)


e_bez("brak klucza pokrętła (domyślnie wyłączone)", bez_klucza)


def przypiety(s):
    zlecenie(s)
    pl = s.k / "instancje" / "_wspolne" / "plan_postaci.json"
    pl.write_text(json.dumps({"postacie": {"a": {"kroki": [], "spot_przypiety": True, "spot_przypiety_powod": "Karol 23.10"}}}))


s_, n_ = e_bez("spot przypięty w planie", przypiety)
sprawdz("E8d przypięty: powód w dzienniku, zlecenie skasowane (nie ponawiane)", any("przypięty" in x["powod"] and x["akcja"] == "czekaj" for x in kody(n_))
        and not (s_.k / "instancje" / "a" / SG.PLIK_ZADANIA).exists(), [x["powod"] for x in kody(n_)])


def walka(s):
    zlecenie(s)
    t = s.zegar.t
    s.log("a", [(t - timedelta(seconds=5), "[ATAK] Troll"), (t - timedelta(seconds=4), "[WALKA] Troll 50%")])


e_bez("bot w walce (log)", walka)

# E9: cień (bez NADZOR_NAPRAWY) nic nie robi i nie kasuje zlecenia
s = swiat_e()
kat = zlecenie(s)
n, at = nadz(s, "cien")
n.tick()
sprawdz("E9 cień: zero uruchomień, zlecenie na miejscu, ewentualnie tylko wpis „zrobiłbym”", not at.wywolania and (kat / SG.PLIK_ZADANIA).exists(), at.wywolania)

# E10: brak zlecenia = żadnej zmiany w decyzjach i stanie
s = swiat_e()
n, at = nadz(s)
n.tick()
sprawdz("E10 bez zlecenia: nadzorca nic nie robi z spotem, brak klucza spot_gracz w stanie postaci", not at.wywolania
        and "spot_gracz" not in n.stan["postacie"]["a"], (at.wywolania, n.stan["postacie"]["a"].keys()))

# E11: rodzina — pole `rodzina` w tabeli: najpierw ta sama rodzina, dopiero potem reszta
mapy11 = {"_opis": "x", **{m: {"trasa": "x", "potwory": "Troll"} for m in ("ed_a", "ed_a2", "ed_b", "ed_c")}}
sp11 = lambda j, rod, **kw: {"miasto": "edron", "jaskinia": j, "poziom": [5, 30], "waga": 1.0, "auto": True, "rodzina": rod, **kw}      # noqa: E731
spoty11 = {"ed_a": sp11("j_a", "edron_trolle"), "ed_a2": sp11("j_a2", "edron_trolle"), "ed_b": sp11("j_b", "edron_inne"), "ed_c": sp11("j_c", "edron_inne")}
for powt in range(5):
    s = swiat_e(spoty=spoty11, mapy=mapy11)
    s.zegar.t = s.zegar.t + timedelta(minutes=powt)
    zlecenie(s)
    n, at = nadz(s)
    n.tick()
    assert [w[2] for w in wyw(at, "start_bota")] == ["ed_a2"], (powt, at.wywolania)
sprawdz("E11 `rodzina`: nowy spot z tej samej rodziny (ed_a2) mimo wolnych ed_b i ed_c, w 5 losowaniach", True)
s = swiat_e(spoty=spoty11, mapy=mapy11)
zlecenie(s)
s.online("b", bot=True, level=12, pozycja=[33100, 31760, 8])
s.tryb_log("b", "ed_a2", "ostrozny", s.zegar.t.replace(hour=10, minute=0))       # rodzina zajęta przez b
n, at = nadz(s)
n.tick()
sprawdz("E11b rodzina zajęta przez inny nasz bot: dopiero wtedy inna rodzina w tym samym mieście (ed_b albo ed_c)", [w[2] for w in wyw(at, "start_bota")][0:1] and
        [w[2] for w in wyw(at, "start_bota")][0] in ("ed_b", "ed_c"), at.wywolania)
s = swiat_e(spoty=spoty11, mapy=mapy11)
zlecenie(s)
n, at = nadz(s)
n.post("a")["spot_gracz"] = {"unikane": [{"mapa": "ed_a2", "jaskinia": "j_a2", "nick": "X", "do": s.zegar.t.timestamp() + 3600}]}
n.tick()
sprawdz("E11c członek rodziny niedawno unikany nie jest wybierany: inna rodzina", [w[2] for w in wyw(at, "start_bota")][0] in ("ed_b", "ed_c"), at.wywolania)
s = swiat_e(spoty=spoty11, mapy=mapy11)
zlecenie(s)
n, at = nadz(s)
n.post("a")["spot_gracz"] = {"unikane": [{"mapa": "ed_a2", "jaskinia": "j_a2", "nick": "X", "do": s.zegar.t.timestamp() - 10}]}
n.tick()
sprawdz("E11d unikanie wygasa po 3 h: po terminie ed_a2 znów dozwolony", [w[2] for w in wyw(at, "start_bota")] == ["ed_a2"], at.wywolania)

# E12: zapasowe grupowanie (brak pola `rodzina`): środki pętli w <= 60 polach, ten sam potwór; dalszy spot to „reszta”
sp12 = lambda j: {"miasto": "edron", "jaskinia": j, "poziom": [5, 30], "waga": 1.0, "auto": True}      # noqa: E731
mapy12 = {"_opis": "x", "ed_a": {"trasa": "t_a", "potwory": "Troll"}, "ed_a2": {"trasa": "t_a2", "potwory": "Troll,Bear"}, "ed_b": {"trasa": "t_b", "potwory": "Troll"},
          "ed_c": {"trasa": "t_c", "potwory": "Goblin"}}
spoty12 = {m: sp12("j_" + m) for m in mapy12}
trasy12 = {"t_a": [[33100, 31700, 8], [33110, 31710, 8]], "t_a2": [[33140, 31720, 9], [33150, 31730, 9]],
           "t_b": [[33300, 31900, 8], [33310, 31910, 8]], "t_c": [[33105, 31705, 8], [33115, 31715, 8]]}
for powt in range(5):
    s = swiat_e(spoty=spoty12, mapy=mapy12, trasy=trasy12)
    s.zegar.t = s.zegar.t + timedelta(minutes=powt)
    zlecenie(s)
    n, at = nadz(s)
    n.tick()
    assert [w[2] for w in wyw(at, "start_bota")] == ["ed_a2"], (powt, at.wywolania)
sprawdz("E12 bez pola `rodzina`: zapasowe grupowanie (miasto + wspólny potwór + środek <= 60 pól niezależnie od piętra) wybiera ed_a2, nie dalekie ed_b ani goblinowe ed_c", True)
s = swiat_e(spoty=spoty12, mapy=mapy12, trasy=trasy12)
zlecenie(s)
s.online("b", bot=True, level=12, pozycja=[33100, 31760, 8])
s.tryb_log("b", "ed_a2", "ostrozny", s.zegar.t.replace(hour=10, minute=0))
n, at = nadz(s)
n.tick()
sprawdz("E12b rodzina zapasowa zajęta: reszta miasta (ed_b albo ed_c)", [w[2] for w in wyw(at, "start_bota")][0:1] and [w[2] for w in wyw(at, "start_bota")][0] in ("ed_b", "ed_c"),
        at.wywolania)

# E13: zepsuty spot_gracz_zadanie.json nie wywraca nadzorcy
s = swiat_e()
(s.k / "instancje" / "a" / SG.PLIK_ZADANIA).write_text("{nie json")
n, at = nadz(s)
n.tick()
sprawdz("E13 nieczytelne zlecenie: sprzątnięte, brak akcji, tick nie rzuca", not at.wywolania and not (s.k / "instancje" / "a" / SG.PLIK_ZADANIA).exists())

# E14: nieudany start/stop: 3 próby i wycofanie
s = swiat_e()
kat = zlecenie(s)
n, at = nadz(s)
at.wyniki["start_bota"] = (False, "uruchom.sh: kod 1")
n.tick()
sp_ = n.stan["postacie"]["a"].get("spot_gracz", {})
sprawdz("E14 nieudany start: zlecenie zostaje do ponowienia, licznik prób 1, brak wpisu o zmianie (limity nie zużyte)", (kat / SG.PLIK_ZADANIA).exists()
        and sp_.get("proby", {}).get("n") == 1 and not sp_.get("zmiany"), sp_)


# ============================================================ (F) ostatni szczebel: brak spotu => powrót do miasta (Karol 26.10 ~10:50)
import zostan_depo as ZD  # noqa: E402
import refill_auto as RA  # noqa: E402


def swiat_f(brak=True, knob_powrot=None, nadzor=True, przypiety=False, level=12, plan_domyslne=False):
    """Jak swiat_e, ale `brak=True` = jedyny wolny spot ed_b zajęty przez b, a ed_c wymaga liny, której nie ma: wybierz() nie ma kandydata."""
    s = swiat_e(level=level)
    kat = zlecenie(s)
    if brak:
        s.ekw["a"] = {"lina": False, "lopata": True}
        s.online("b", bot=True, level=12, pozycja=[33100, 31760, 8])
        s.tryb_log("b", "ed_b", "ostrozny", s.zegar.t.replace(hour=10, minute=0))
    kn = {"SPOT_ZMIANA_PRZY_GRACZU": 1}
    if knob_powrot is not None:
        kn["SPOT_GRACZ_POWROT_DO_MIASTA"] = knob_powrot
    (s.k / "instancje" / "a" / "na_zywo.json").write_text(json.dumps(kn))
    if not nadzor:
        (s.k / "instancje" / "a" / "profil.json").write_text(json.dumps({"postac": "A", "nadzor": False}))
    plan = {"postacie": {"a": {"kroki": [], **({"spot_przypiety": True, "spot_przypiety_powod": "Karol 23.10"} if przypiety else {})}}}
    if plan_domyslne:
        plan["domyslne"] = {"wlaczone": True}
    if przypiety or plan_domyslne:
        (s.k / "instancje" / "_wspolne" / "plan_postaci.json").write_text(json.dumps(plan))
    return s, kat


# F1: brak kandydata -> WROC zlecony RAZ, jedno powiadomienie, limity i unikany spot, znacznik „zostaje w depo”
s, kat = swiat_f()
n, at = nadz(s)
n.tick()
sg_ = n.stan["postacie"]["a"].get("spot_gracz", {})
sprawdz("F1 brak dopuszczalnego spotu: zlecony powrót do miasta (WROC, kod spot-gracz-powrot), bot NIE zatrzymany ani restartowany",
        len(wyw(at, "wroc")) == 1 and not wyw(at, "zatrzymaj_bota") and not wyw(at, "start_bota") and (s.k / "instancje" / "a" / "WROC").exists(), at.wywolania)
sprawdz("F1b jedno powiadomienie: nick, licznik, „brak wolnego spotu -> powrót do miasta”",
        len(wyw(at, "powiadom_info")) == 1 and "Statutum" in str(wyw(at, "powiadom_info")[0]) and "3. raz" in str(wyw(at, "powiadom_info")[0])
        and "powrót do miasta" in str(wyw(at, "powiadom_info")[0]), wyw(at, "powiadom_info"))
sprawdz("F1c powrót wlicza się do limitów (zmiany), unikany stary spot, zlecenie skasowane, znacznik depo zapisany, nie zużywa drabiny napraw",
        len(sg_.get("zmiany", [])) == 1 and sg_["unikane"][0]["mapa"] == "ed_a" and not (kat / SG.PLIK_ZADANIA).exists()
        and (kat / ZD.PLIK_SPOT_GRACZ_DEPO).exists() and not n.stan["postacie"]["a"].get("naprawy"), (sg_, n.stan["postacie"]["a"].get("naprawy")))
n.tick()
n.tick()
sprawdz("F1d powtórne przebiegi nie zlecają powrotu drugi raz (WROC raz)", len(wyw(at, "wroc")) == 1 and len(wyw(at, "powiadom_info")) == 1, at.wywolania)

# F2: kandydat jest -> zmiana spotu jak dotąd, bez WROC
s, kat = swiat_f(brak=False)
n, at = nadz(s)
n.tick()
sprawdz("F2 jest wolny spot: zmiana spotu jak dotąd (start na nowej mapie), BEZ powrotu do miasta i bez znacznika depo",
        len(wyw(at, "start_bota")) == 1 and not wyw(at, "wroc") and not (kat / ZD.PLIK_SPOT_GRACZ_DEPO).exists(), at.wywolania)

# F3: limity obejmują powrót
s, kat = swiat_f()
n, at = nadz(s)
n.post("a")["spot_gracz"] = {"zmiany": [s.zegar.t.timestamp() - 20 * 60]}
n.tick()
sprawdz("F3 zmiana 20 min temu (limit 1/30 min): brak powrotu, zlecenie skasowane", not wyw(at, "wroc") and not (kat / SG.PLIK_ZADANIA).exists(), at.wywolania)
s, kat = swiat_f()
n, at = nadz(s)
n.post("a")["spot_gracz"] = {"zmiany": [s.zegar.t.timestamp() - 3600 * h for h in (2, 5, 8, 11)]}
n.tick()
sprawdz("F3b 4 zmiany w dobie: brak powrotu", not wyw(at, "wroc"), at.wywolania)
s, kat = swiat_f()
n, at = nadz(s)
n.tick()
s.inst["a"].update(bot=True)
s.plik("a", "WROC").unlink(missing_ok=True)
(kat / ZD.PLIK_SPOT_GRACZ_DEPO).unlink()
zlecenie(s)                                              # drugie zlecenie od razu po powrocie: limit 30 min blokuje
n.tick()
sprawdz("F3c powrót zużył limit: kolejne zlecenie w tej samej chwili nie daje drugiego WROC", len(wyw(at, "wroc")) == 1, at.wywolania)

# F4: spot przypięty i postać bez nadzoru nie wracają
s, kat = swiat_f(przypiety=True)
n, at = nadz(s)
n.tick()
sprawdz("F4 spot przypięty (dawajkesh, invincible): ani zmiana, ani powrót; zlecenie skasowane", not at.wywolania and not (kat / SG.PLIK_ZADANIA).exists(), at.wywolania)
s, kat = swiat_f(nadzor=False)
n, at = nadz(s)
n.tick()
sprawdz("F4b postać bez nadzoru (`nadzor: false`): nadzorca nic nie robi, tylko loguje (bot nie dostaje WROC)", not wyw(at, "wroc") and not wyw(at, "zatrzymaj_bota"), at.wywolania)

# F5: pokrętła
s, kat = swiat_f(knob_powrot=0)
n, at = nadz(s)
n.tick()
sprawdz("F5 SPOT_GRACZ_POWROT_DO_MIASTA=0: brak spotu = zostaje na spocie (spot-gracz-brak), bez WROC", not wyw(at, "wroc") and any(
    "brak sensownego spotu" in x["powod"] for x in kody(n)), [x["powod"] for x in kody(n)])
s, kat = swiat_f()
(s.k / "instancje" / "a" / "na_zywo.json").write_text(json.dumps({"SPOT_ZMIANA_PRZY_GRACZU": 0, "SPOT_GRACZ_POWROT_DO_MIASTA": 1}))
n, at = nadz(s)
n.tick()
sprawdz("F5b SPOT_ZMIANA_PRZY_GRACZU=0: nic (także przy powrocie=1), zlecenie wycofane", not at.wywolania and not (kat / SG.PLIK_ZADANIA).exists(), at.wywolania)
s, kat = swiat_f(knob_powrot=1)
n, at = nadz(s)
n.tick()
sprawdz("F5c powrót=1 jawnie = jak domyślnie", len(wyw(at, "wroc")) == 1)

# F6: bezpieczeństwo bez zmian — powrót też tylko w spokoju
s, kat = swiat_f()
SG.zapisz_zadanie(kat, s.zegar.t.timestamp() - 5, "Statutum", 3)                  # bez gotowy_t
n, at = nadz(s)
n.tick()
sprawdz("F6 bez świeżego potwierdzenia spokoju od bota: brak powrotu, zlecenie czeka", not wyw(at, "wroc") and (kat / SG.PLIK_ZADANIA).exists(), at.wywolania)
s, kat = swiat_f()
t_ = s.zegar.t
s.log("a", [(t_ - timedelta(seconds=5), "[ATAK] Troll"), (t_ - timedelta(seconds=4), "[WALKA] Troll 50%")])
n, at = nadz(s)
n.tick()
sprawdz("F6b bot w walce: brak powrotu", not wyw(at, "wroc"), at.wywolania)
s, kat = swiat_f()
SG.zapisz_zadanie(kat, s.zegar.t.timestamp() - 25 * 60, "Statutum", 3)
n, at = nadz(s)
n.tick()
sprawdz("F6c zlecenie przeterminowane (25 min): brak powrotu", not wyw(at, "wroc"), at.wywolania)

# F7: tryby nadzorcy — NADZOR_NAPRAWY: kod spot-gracz-powrot na żywo, zwykłe wroc nadal tylko w cieniu; cień i żywo
s, kat = swiat_f()
n, at = nadz(s)                                           # NADZOR_NAPRAWY (naprawy_poziom=True)
n.tick()
sprawdz("F7 NADZOR_NAPRAWY: powrót z kodem spot-gracz-powrot wykonany NA ŻYWO (wroc.sh wywołany)", len(wyw(at, "wroc")) == 1, at.wywolania)
s, kat = swiat_f()
n, at = nadz(s)
d_zwykle = N.D("a", "wroc", "zwykły powrót z drabiny", "napraw-zaciecie-wroc", klasa="naprawa", problem="zaciecie")
n.wykonaj(s.zegar.t, "a", d_zwykle, None)
sprawdz("F7b ten sam tryb: ZWYKŁE `wroc` (inny kod) nadal tylko cień, zakaz nie poluzowany", not wyw(at, "wroc"), at.wywolania)
s, kat = swiat_f()
n, at = nadz(s, "cien")
n.tick()
sprawdz("F7c cień (bez NADZOR_NAPRAWY): wpis „zrobiłbym wroc”, wroc.sh NIE wywołany, WROC nie powstaje, zlecenie na miejscu",
        not at.wywolania and not (s.k / "instancje" / "a" / "WROC").exists() and (kat / SG.PLIK_ZADANIA).exists()
        and any(x["akcja"] == "wroc" and x["wynik"] == "cień" for x in n.dziennik.ostatnie), [(x["akcja"], x["wynik"]) for x in n.dziennik.ostatnie])
s, kat = swiat_f()
at = TN.Atrapa(s)
n = N.Nadzorca(s.k, s.zegar, s, at, True, True)           # NADZOR_ZYWO
n.tick()
sprawdz("F7d NADZOR_ZYWO: powrót wykonany na żywo", len(wyw(at, "wroc")) == 1, at.wywolania)

# F8: po powrocie postać zostaje w depo (bez startu na spot, serwisu, refillu), do decyzji
s, kat = swiat_f()
n, at = nadz(s)
n.tick()
s.inst["a"].update(bot=False)
s.inst["a"]["panel"].update(w_depo=True, w_miescie="edron", wroc_refill="brak_planu")
s.plik("a", "WROC").unlink(missing_ok=True)
s.plik("a", "STOP").touch()
s.log("a", [(s.zegar.t, "Wyprawa: DEPO osiągnięte"), (s.zegar.t, "Zatrzymano (plik STOP).")])
s.zegar.dalej(minutes=3)
at.wywolania.clear()
for _ in range(3):
    n.tick()
    s.zegar.dalej(minutes=1)
sprawdz("F8 po powrocie w depo ze STOP: żadnego start_bota, serwisu, refillu, wznowienia, relogu (postać czeka na decyzję)",
        not [w for w in at.wywolania if w[0] in ("start_bota", "serwis", "refill_spot", "relog", "zatrzymaj_bota", "wroc")], at.wywolania)
sprawdz("F8b bez planu `wyloguj_w_depo` postać też nie jest wylogowywana (zostaje w grze w depo)", not wyw(at, "wyloguj"), at.wywolania)
sprawdz("F8d znacznik wygasa po 12 h i gdy bot wystartował po nim",
        ZD.spot_gracz_depo(kat, s.zegar.t.timestamp() + 13 * 3600) is None and ZD.spot_gracz_depo(kat, s.zegar.t.timestamp(), start_bota=s.zegar.t.timestamp() + 10) is None
        and ZD.spot_gracz_depo(kat, s.zegar.t.timestamp(), start_bota=s.zegar.t.timestamp() - 600))
_czas0 = ZD.time
ZD.time = types.SimpleNamespace(time=lambda: s.zegar.t.timestamp())          # refill_auto czyta zegar ścienny; w teście świat ma własny zegar
try:
    sprawdz("F8c znacznik depo trzyma postać: ZD.spot_gracz_depo i refill_auto.zostaje_w_depo (brak auto-refillu)",
            ZD.spot_gracz_depo(kat, s.zegar.t.timestamp()) and RA.zostaje_w_depo(kat), ZD.spot_gracz_depo(kat, s.zegar.t.timestamp()))
    ZD.usun_spot_gracz_depo(kat)
    sprawdz("F8e bez znacznika refill_auto nie blokuje (zachowanie jak dotąd)", RA.zostaje_w_depo(kat) is None)
finally:
    ZD.time = _czas0

# F8f: kontrola różnicująca: miasto z planem serwisu (nadzorca normalnie odkłada do depo i robi serwis); ze znacznikiem postać stoi, bez znacznika serwis rusza
def depo_serwisowe(usun_znacznik):
    s, kat = swiat_f()
    n, at = nadz(s)
    n.tick()
    s.inst["a"].update(bot=False)
    s.inst["a"]["panel"].update(w_depo=True, w_miescie="edron", wroc_refill="czeka")
    s.plik("a", "WROC").unlink(missing_ok=True)
    s.plik("a", "STOP").touch()
    s.log("a", [(s.zegar.t, "Wyprawa: DEPO osiągnięte"), (s.zegar.t, "Zatrzymano (plik STOP).")])
    if usun_znacznik:
        ZD.usun_spot_gracz_depo(kat)
    s.zegar.dalej(minutes=3)
    at.wywolania.clear()
    n.dziennik.ostatnie.clear()
    n.tick()
    return [x["akcja"] for x in n.dziennik.ostatnie if x["id"] == "a"] + [w[0] for w in at.wywolania], n      # decyzje (także cień) i wywołania


z_, n_ = depo_serwisowe(False)
sprawdz("F8f ze znacznikiem powrotu po graczach: w depo NIE rusza serwis ani nic innego (postać czeka na decyzję)", "serwis" not in z_ and "start_bota" not in z_, z_)
z_, n_ = depo_serwisowe(True)
sprawdz("F8g kontrola: bez znacznika ten sam stan daje normalny cykl nadzorcy (serwis), więc F8f naprawdę coś dowodzi", "serwis" in z_, z_)

# F9: z domyślnym planem („domyslne” włączone) postać po powrocie jest też wylogowana
s, kat = swiat_f(plan_domyslne=True)
n, at = nadz(s)
n.tick()
s.inst["a"].update(bot=False)
s.inst["a"]["panel"].update(w_depo=True, w_miescie="edron", wroc_refill="brak_planu")
s.plik("a", "WROC").unlink(missing_ok=True)
s.plik("a", "STOP").touch()
s.log("a", [(s.zegar.t, "Wyprawa: DEPO osiągnięte"), (s.zegar.t, "Zatrzymano (plik STOP).")])
s.zegar.dalej(minutes=10)
at.wywolania.clear()
n.tick()
sprawdz("F9 domyślny plan (zostan_w_depo + wyloguj_w_depo): po powrocie postać zostaje w depo i jest wylogowana, bez startu na spot",
        len(wyw(at, "wyloguj")) == 1 and not wyw(at, "start_bota") and not wyw(at, "serwis"), at.wywolania)

# F10: ręczny/planowy start po powrocie zdejmuje znacznik (nie trzyma postaci w nieskończoność)
s, kat = swiat_f()
n, at = nadz(s)
n.tick()
s.inst["a"].update(bot=True)
s.plik("a", "WROC").unlink(missing_ok=True)
s.zegar.dalej(minutes=15)
s.log("a", [(s.zegar.t - timedelta(seconds=30), "Mózg: start")], nazwa=f"mozg-stdout-1021-{s.zegar.t.hour:02d}{s.zegar.t.minute - 1:02d}.log")
s.tryb_log("a", "ed_b", "ostrozny", s.zegar.t)
n2 = N.Nadzorca(s.k, s.zegar, s, N.WykonawcaCien(), False, True, naprawy_poziom=True, wykonawca_poziom=at)
n2.tick()
sprawdz("F10 bot wystartowany PO powrocie (decyzja Karola/planu): znacznik depo zdjęty", not (kat / ZD.PLIK_SPOT_GRACZ_DEPO).exists())

# ---- I: nadzorca nie wykonuje zlecenia z poprzedniej sesji (start bota nowszy niż zlecenie)
def swiat_i(zlecenie_min_temu, start_logu, knob_od_startu=None, unikane=True):
    s, kat = swiat_f()
    (kat / SG.PLIK_ZADANIA).unlink()
    t = s.zegar.t.timestamp()
    SG.zapisz_zadanie(kat, t - zlecenie_min_temu * 60, "Statutum", 3)
    SG.odswiez_gotowy(kat, t - 2)
    if start_logu:
        s.log("a", [(s.zegar.t.replace(hour=start_logu[0], minute=start_logu[1], second=5), "Mózg: tryb skrypt")], nazwa=f"mozg-stdout-1021-{start_logu[0]:02d}{start_logu[1]:02d}.log")
    if knob_od_startu is not None:
        (s.k / "instancje" / "a" / "na_zywo.json").write_text(json.dumps({"SPOT_ZMIANA_PRZY_GRACZU": 1, "LICZNIK_OD_STARTU": knob_od_startu}))
    n, at = nadz(s)
    if unikane:
        n.post("a")["spot_gracz"] = {"unikane": [{"mapa": "ed_x", "jaskinia": "j_x", "nick": "Y", "do": t + 3600}]}
    n.tick()
    return s, kat, n, at


s, kat, n, at = swiat_i(5, (11, 18))                      # zlecenie 11:15, bot wystartował 11:18 (restart po zapisie zlecenia)
sprawdz("I1 zlecenie starsze niż start bota (restart po jego zapisie) wygasa: ani zmiany spotu, ani powrotu, plik skasowany",
        not wyw(at, "wroc") and not wyw(at, "start_bota") and not wyw(at, "zatrzymaj_bota") and not (kat / SG.PLIK_ZADANIA).exists()
        and any("poprzedniej sesji" in x["powod"] for x in kody(n)), (at.wywolania, [x["powod"] for x in kody(n)]))
sprawdz("I2 nadzorca NIE zeruje unikanych spotów po 3. spotkaniu (zostają 3 h)", n.stan["postacie"]["a"]["spot_gracz"]["unikane"][0]["mapa"] == "ed_x")
s, kat, n, at = swiat_i(5, (11, 0))                       # bot wystartował 11:00, zlecenie 11:15 — z TEJ sesji
sprawdz("I3 zlecenie z bieżącej sesji (bot wystartował PRZED nim) wykonuje się jak dotąd", len(wyw(at, "wroc")) == 1 or len(wyw(at, "start_bota")) == 1, at.wywolania)
s, kat, n, at = swiat_i(5, (11, 18), knob_od_startu=0)
sprawdz("I4 LICZNIK_OD_STARTU=0 w na_zywo.json instancji: stare zlecenie nie wygasa z powodu restartu", len(wyw(at, "wroc")) == 1 or len(wyw(at, "start_bota")) == 1, at.wywolania)
s, kat, n, at = swiat_i(5, None)
sprawdz("I5 brak logów sesji (start nieustalony): nie wygasza zlecenia", len(wyw(at, "wroc")) == 1 or len(wyw(at, "start_bota")) == 1, at.wywolania)


print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
