#!/usr/bin/env python3
"""26.10 (decyzja Karola po zgonie Odchyda 07:33, gracz „Ogr”, Kazordoon): PK_RESET_PO_ZGONIE. Po zgonie postaci stan obrony PK
ma się ZAWSZE zerować: `karencja_do` w wrogowie.json, stan ucieczki w pamięci (pk_stan, pk_fallback, pk_start_wait) i zapisana wyprawa
PK (potrzeby.pk w wyprawa_stan.json); LISTA wrogów (nicki) zostaje. Atrapy bez gry, X11 i modelu; telemetria z przypadku Odchyda
(07:33:01 HP 0 na (32657,31967,8), 07:45:57 start w Edronie (33126,31811,7) z HP 100).
Uruchomienie: RETRONIC_TESTY=1 python3 -I testy/test_pk_reset_po_zgonie.py

Scenariusze: (a) zgon w grze, (b) restart po zgonie z karencją w przyszłości i wyprawą PK, (c) restart BEZ zgonu z aktywną karencją
(karencja nadal działa), (d) pokrętło 0 = stare zachowanie, (e) pk_zgon.py: heurystyka i jej granice, (f) pokrętło w ZAKRESY/przykładzie,
(g) SMIERC_STOP=1, (h) zwykła wyprawa nietknięta."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
import tempfile
import time
import types
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KAT))
import bot  # noqa: E402,F401
import cavebot  # noqa: E402
import mozg  # noqa: E402
import obrona_pk  # noqa: E402
import pk_zgon  # noqa: E402
import pokretla  # noqa: E402
import wyprawa as wyprawa_mod  # noqa: E402
import wznow_start  # noqa: E402

cavelog = []
_log0 = cavebot.log


def _log(*a):
    cavelog.append(" ".join(map(str, a)))


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
cavebot.PK_KONTRATAK = 0
cavebot.SMIERC_STOP = 0
TMP = Path(tempfile.mkdtemp())
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


SPOT = (32657, 31967, 8)        # tu zginął Odchyd (07:33:01)
EDRON = (33126, 31811, 7)       # tu odrodził się i wystartował bot (07:45:57)
NOW = time.time()
licznik = [0]


def gr(nazwa, dx, dy, id_=777):
    return {"id": id_, "nazwa": nazwa, "gracz": True, "dx": dx, "dy": dy, "z": 8, "hp": 85}


class Swiat:
    def __init__(s, poz=SPOT, hp=100, stwory=()):
        s.t, s.poz, s.hp, s.stwory, s.nick = 1000.0, list(poz), hp, list(stwory), "Odchyd"
        s.wall = NOW
        s.klawisze, s.starty = [], []

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
                m["x"], m["y"], m["z"] = s.poz[0] + m.pop("dx"), s.poz[1] + m.pop("dy"), s.poz[2]
                out.append(m)
            return {"stwory": [ja] + out}
        return {}


class P:
    def __init__(p, s):
        p.s, p.nazwa = s, s.nick

    def pozycja(p):
        return tuple(p.s.poz)

    def klawisz(p, k):
        p.s.klawisze.append(k)

    def krok(p, k):
        return tuple(p.s.poz)


class FakeWyprawa:
    """Atrapa Wyprawy: prawdziwe `odrzuc_pk_po_zgonie` i `_stan_*` (na pliku w TMP), reszta zliczana."""

    def __init__(f, cb, s, plik, stan=None):
        f.cb, f.s, f.w, f.zablokowany, f.plik_stanu = cb, s, None, False, plik
        f._plan_wyprawy, f.stan, f.faza, f.etapy, f.sklep, f.wynik = None, "SPOKOJ", None, None, None, None
        f.wznowien, f.logi = 0, []
        if stan is not None:
            plik.write_text(json.dumps(stan))

    log = lambda f, t: f.logi.append(t)           # noqa: E731
    czas = lambda f: f.s.wall                     # noqa: E731
    odrzuc_pk_po_zgonie = wyprawa_mod.Wyprawa.odrzuc_pk_po_zgonie

    def _stan_czytaj(f):
        try:
            return json.loads(f.plik_stanu.read_text())
        except (OSError, ValueError):
            return {}

    def _stan_zapisz(f, **zm):
        d = f._stan_czytaj()
        d.update(zm)
        f.plik_stanu.write_text(json.dumps(d))

    def _stan_koniec(f, **extra):
        f._stan_zapisz(aktywna=False, przerwana=False, faza=None, zapis_wall=f.s.wall, **extra)

    def _wznow(f, teraz):
        f.wznowien += 1
        f.w = {"potrzeby": f._stan_czytaj().get("potrzeby")}
        return True

    def start_pk(f, rodzaj, teraz, baza=None):
        f.s.starty.append(rodzaj)
        f.w = {"potrzeby": {"depo": True, "pk": rodzaj}}
        f.cb.wypad_aktywny = True
        f._stan_zapisz(aktywna=True, potrzeby={"depo": True, "pk": rodzaj}, powod=f"depo:pk_{rodzaj}", baza="edron",
                       zapis_wall=f.s.wall)
        return True

    def tick(f):
        return False

    def przerwij(f, powod):
        f.w = None

    def uciekaj(f, poz):
        return True


WROGOWIE = {
    "nieznajoma": {"nick": "Nieznajoma", "od": 100.0, "ile": 1, "ost": 200.0, "powod": "reczny: Karol 24.10", "miejsce": None},
    "ogr": {"nick": "Ogr", "od": 300.0, "ile": 1, "ost": 900.0, "powod": "atak: HP -9 pp, odl 1", "miejsce": [32661, 31961, 8]},
}


def zrob(s, *, karencja_min=30, knob=1, stan_wyprawy=None, telemetria=None, ostatnie=None, smierc_stop=0):
    """Cavebot po „restarcie”: plik wrogów z karencją w przyszłości, wyprawa z pliku stanu, telemetria na dysku."""
    licznik[0] += 1
    kat = TMP / f"t{licznik[0]}"
    (kat / "logi").mkdir(parents=True)
    cavebot.PK_RESET_PO_ZGONIE = knob
    cavebot.SMIERC_STOP = smierc_stop
    pk_zgon.reset_pamieci()
    if telemetria is not None:
        (kat / "logi" / "telemetria-20261026.jsonl").write_text("".join(json.dumps(r) + "\n" for r in telemetria))
    if ostatnie is not None:
        (kat / "ostatnie.json").write_text(json.dumps(ostatnie))
    pw = kat / "wrogowie.json"
    pw.write_text(json.dumps({"wrogowie": WROGOWIE, "karencja_do": s.t + karencja_min * 60.0}))

    def atak(m, g):
        pass

    punkty = [(s.poz[0] + i, s.poz[1], s.poz[2]) for i in range(1, 11)]
    b = mozg.CavebotMozgu(P(s), punkty, okrazenia=999, zapytaj=s.zapytaj, atak=atak, alarm=lambda w: None,
                          spij=s.spij, zegar=s.zegar, loot=type("L", (), {"zbierz": staticmethod(lambda zw, g: "ok")})())
    b._pk_dane()
    b.pk_wrogowie = obrona_pk.Wrogowie(pw, czas=s.zegar, log=lambda t: None)
    b.powiadomienia, b.stopy = [], []
    b._pk_powiadom = lambda tytul, tresc, klucz: b.powiadomienia.append((tytul, tresc, klucz))
    b._pk_stop = lambda opis: b.stopy.append(opis)
    b.tele = None
    b.pk_zgon_logi = kat / "logi"
    b.pk_zgon_ostatnie = kat / "ostatnie.json"
    b.fw = FakeWyprawa(b, s, kat / "wyprawa_stan.json", stan_wyprawy)
    b.wyprawa = b.fw
    b.plik_wr = pw
    return b


def tick(s, b, n=1, krok=1.0):
    for _ in range(n):
        s.t += krok
        s.wall += krok
        b.tick()


def na_dysku(b):
    return json.loads(b.plik_wr.read_text())


def tele_zgon(hp_serii=(0,) * 6, dt=4.0, poz=SPOT, konc=NOW - 700):
    """Telemetria jak 07:32-07:33 Odchyda: kilka żywych próbek (HP spada) i seria HP 0 w jednym miejscu."""
    rek, t = [], konc - dt * (len(hp_serii) + 3)
    for hp in (100, 48, 11):
        rek.append({"t": t, "typ": "probka", "stan": "WALKA", "poz": list(poz), "hp": hp, "pid": 146385})
        t += dt
    for hp in hp_serii:
        rek.append({"t": t, "typ": "probka", "stan": "WYPAD", "poz": list(poz), "hp": hp, "pid": 146385})
        t += dt
    return rek


STAN_PK = {"aktywna": True, "przerwana": False, "powod": "depo:pk_powrot", "baza": "edron", "k": 0, "faza": "do",
           "potrzeby": {"depo": True, "pk": "powrot"}, "t_wall": NOW - 600, "zapis_wall": NOW - 60,
           "depo_start_powody": ["pk"], "wynik": "pk_depo"}
STAN_BLANKI = {"aktywna": True, "przerwana": False, "powod": "depo:blanki", "baza": "edron", "k": 0, "faza": "do",
               "potrzeby": {"depo": True}, "t_wall": NOW - 600, "zapis_wall": NOW - 60}

# --- (f) pokrętło: kod, ZAKRESY, KIERUNEK, przykład ---------------------------------------------------------------
src = (KAT / "cavebot.py").read_text()
przyklad = json.loads((KAT / "na_zywo.przyklad.json").read_text())
sprawdz("f1 PK_RESET_PO_ZGONIE: w kodzie domyślnie 1, ZAKRESY (0,1), nie_nizej, w przykładzie 1",
        "\nPK_RESET_PO_ZGONIE = 1 " in src and pokretla.ZAKRESY.get("PK_RESET_PO_ZGONIE") == (0, 1)
        and pokretla.KIERUNEK.get("PK_RESET_PO_ZGONIE") == "nie_nizej" and przyklad.get("PK_RESET_PO_ZGONIE") == 1)
ok_, bl = pokretla.waliduj({"PK_RESET_PO_ZGONIE": 0}, {"PK_RESET_PO_ZGONIE": 1})
sprawdz("f2 analityk nie może wyłączyć resetu (walidacja z domyślnymi odrzuca 0), ręczny plik tak",
        "PK_RESET_PO_ZGONIE" not in ok_ and pokretla.waliduj({"PK_RESET_PO_ZGONIE": 0})[0] == {"PK_RESET_PO_ZGONIE": 0}, f"{ok_} {bl}")

# --- (a) zgon w grze ----------------------------------------------------------------------------------------------
cavelog.clear()
s = Swiat(stwory=[gr("Ogr", 3, 0)])
b = zrob(s, stan_wyprawy=STAN_PK, telemetria=[])
tick(s, b, 3)
sprawdz("a0 przed zgonem: Ogr (znany wróg) w widoku = ucieczka PK, karencja przedłużona, wyprawa PK wystartowała",
        b.pk_stan == "UCIECZKA" and s.starty == ["ucieczka"] and b.pk_wrogowie.karencja_aktywna(), (b.pk_stan, s.starty))
s.hp = 11
tick(s, b, 1)
s.hp = 0
tick(s, b, 3)                                   # 3 odczyty HP 0 (3 s) < PK_RESET_ZGON_S: jeszcze brak potwierdzenia
sprawdz("a1 3 odczyty HP 0 w 3 s (< 8 s) = jeszcze nie zgon dla resetu (karencja trwa)",
        b.pk_wrogowie.karencja_aktywna() and na_dysku(b)["karencja_do"] > 0 and not b._zgon_martwy, na_dysku(b))
tick(s, b, 6)                                   # łącznie 9 s HP 0
d = na_dysku(b)
sprawdz("a2 zgon w grze (HP 0 przez >= 8 s i 3 odczyty): karencja_do = 0 w pliku i w pamięci",
        d["karencja_do"] == 0.0 and not b.pk_wrogowie.karencja_aktywna(), d.get("karencja_do"))
sprawdz("a3 lista wrogów bez zmian (nicki, ręczny wpis, ost, ile, powód)",
        set(d["wrogowie"]) == {"nieznajoma", "ogr"} and d["wrogowie"]["nieznajoma"] == WROGOWIE["nieznajoma"]
        and {k: v for k, v in d["wrogowie"]["ogr"].items() if k != "ost"} == {k: v for k, v in WROGOWIE["ogr"].items() if k != "ost"}
        and WROGOWIE["ogr"]["ost"] <= d["wrogowie"]["ogr"]["ost"] <= s.t, d["wrogowie"])      # `ost` odświeża zwykłe widziany(), nie reset
sprawdz("a4 stan PK w pamięci wyzerowany (pk_stan, pk_fallback, pk_start_wait), wyprawa PK odrzucona w pliku stanu",
        b.pk_stan is None and not b.pk_fallback and not b.pk_start_wait and b.fw.w is None
        and b.fw._stan_czytaj().get("aktywna") is False and b.fw._stan_czytaj().get("wynik") == "pk_zgon", (b.pk_stan, b.fw._stan_czytaj()))
n_start = len(s.starty)
tick(s, b, 10)                                  # Ogr nadal w widoku, postać nadal martwa (HP 0)
sprawdz("a5 martwa postać dalej: Ogr w widoku NIE przedłuża karencji, NIE wszczyna ucieczki, plik karencja_do nadal 0",
        na_dysku(b)["karencja_do"] == 0.0 and b.pk_stan is None and len(s.starty) == n_start, (na_dysku(b)["karencja_do"], b.pk_stan, s.starty))
s.poz, s.hp, s.stwory = list(EDRON), 100, []
tick(s, b, 3)                                   # respawn w Edronie
sprawdz("a6 po respawnie: brak karencji, brak pk_stan, zgon-martwy zdjęty, żadna ucieczka do depo",
        not b._zgon_martwy and b.pk_stan is None and na_dysku(b)["karencja_do"] == 0.0 and len(s.starty) == n_start
        and not any("karencja po restarcie" in l for l in cavelog), (b._zgon_martwy, b.pk_stan, s.starty))
sprawdz("a7 w logu jedna linia 'RESET PO ZGONIE' z powodem", sum("RESET PO ZGONIE" in l for l in cavelog) == 1, [l for l in cavelog if "RESET" in l])

# a8: skok pozycji przy HP 0 (respawn w świątyni, telemetria jeszcze daje HP 0) = zgon po 2 odczytach
s = Swiat(stwory=[gr("Ogr", 3, 0)])
b = zrob(s, stan_wyprawy=STAN_PK, telemetria=[])
tick(s, b, 3)
s.poz, s.hp, s.stwory = list(EDRON), 0, []
tick(s, b, 1)
sprawdz("a8 HP 0 ze skokiem pozycji, pierwszy odczyt: jeszcze bez resetu (min. 2 odczyty)", not b._zgon_martwy and na_dysku(b)["karencja_do"] > 0)
tick(s, b, 1)
sprawdz("a9 drugi odczyt HP 0 ze skokiem pozycji = zgon potwierdzony, karencja 0", b._zgon_martwy and na_dysku(b)["karencja_do"] == 0.0)

# a10: krótki zły odczyt HP 0 (2 odczyty, bez skoku, potem HP wraca) NIE resetuje (fałszywy reset gorszy niż brak)
s = Swiat(stwory=[gr("Ogr", 3, 0)])
b = zrob(s, stan_wyprawy=STAN_PK, telemetria=[])
tick(s, b, 3)
s.hp = 0
tick(s, b, 2)
s.hp = 60
tick(s, b, 5)
sprawdz("a10 2 odczyty HP 0 bez skoku, potem HP wraca = BEZ resetu (karencja i ucieczka nadal)",
        na_dysku(b)["karencja_do"] > 0 and b.pk_stan == "UCIECZKA" and b.fw._stan_czytaj().get("aktywna") is True, (na_dysku(b)["karencja_do"], b.pk_stan))

# --- (b) restart po zgonie: karencja w przyszłości zapisana przed zgonem + wyprawa PK w pliku stanu --------------------
cavelog.clear()
wznow_start.WLACZONE = True
s = Swiat(poz=EDRON, hp=100)
b = zrob(s, stan_wyprawy=STAN_PK, telemetria=tele_zgon())
dane0 = json.dumps(na_dysku(b)["wrogowie"], sort_keys=True)
sprawdz("b0 stan wyjściowy: karencja w przyszłości (30 min) i aktywna wyprawa PK = kandydat do wznowienia",
        b.pk_wrogowie.karencja_aktywna() and wznow_start.kandydat(b.fw._stan_czytaj(), NOW)[0] == "aktywna")
wynik = wznow_start.sprobuj(b.fw, cavebot.log, teraz_wall=NOW)
sprawdz("b1 mozg.main: wznow_start.sprobuj NIE wznawia wyprawy PK po zgonie (dojście od bieżącej pozycji), _wznow nie wołane",
        wynik is False and b.fw.wznowien == 0 and any("RESET PO ZGONIE" in l and "wyprawa PK odrzucona" in l for l in cavelog)
        and any("odrzucona po zgonie" in l for l in b.fw.logi), (wynik, b.fw.wznowien, cavelog[-2:]))
sprawdz("b2 zapis wyprawy zamknięty (aktywna False, wynik pk_zgon), karencja 0 na dysku, nicki bez zmian",
        b.fw._stan_czytaj()["aktywna"] is False and b.fw._stan_czytaj()["wynik"] == "pk_zgon"
        and na_dysku(b)["karencja_do"] == 0.0 and json.dumps(na_dysku(b)["wrogowie"], sort_keys=True) == dane0, b.fw._stan_czytaj())
tick(s, b, 5)
sprawdz("b3 pierwsze obiegi po starcie: brak 'karencja po restarcie', brak ucieczki do depo (start_pk nie wołane), pk_stan None",
        not any("karencja po restarcie" in l or "start w karencji" in l for l in cavelog) and s.starty == [] and b.pk_stan is None
        and not b.powiadomienia, (cavelog[-4:], s.starty, b.pk_stan))
sprawdz("b4 log zawiera powód resetu (seria HP 0) i granice: 'RESET PO ZGONIE'",
        any("RESET PO ZGONIE" in l and "seria HP 0" in l for l in cavelog), [l for l in cavelog if "RESET" in l])

# b5: sam tick bez wznow_start (brak wyprawy do wznowienia): ten sam efekt
cavelog.clear()
s = Swiat(poz=EDRON, hp=100)
b = zrob(s, stan_wyprawy=None, telemetria=tele_zgon())
tick(s, b, 4)
sprawdz("b5 bez wznow_start (tylko tick): karencja 0, brak ucieczki do depo",
        na_dysku(b)["karencja_do"] == 0.0 and s.starty == [] and b.pk_stan is None, (na_dysku(b)["karencja_do"], s.starty))

# b6: zgon z poprzednim procesem, który zdążył zapisać zdarzenie 'smierc' (SMIERC_STOP=1)
cavelog.clear()
s = Swiat(poz=EDRON, hp=100)
rek = tele_zgon(hp_serii=(0,))                  # za krótka seria, ale potem zdarzenie smierc
rek.append({"t": NOW - 650, "typ": "smierc", "poz": list(SPOT), "przyczyna": "HP 0 w 3 odczytach"})
b = zrob(s, stan_wyprawy=STAN_PK, telemetria=rek)
tick(s, b, 3)
sprawdz("b6 ostatnie zdarzenie telemetrii 'smierc' + żywa postać = zgon rozpoznany przy starcie", na_dysku(b)["karencja_do"] == 0.0 and s.starty == [])

# b7: zgon wykryty tylko z ostatnie.json (hp 0 sprzed startu procesu), telemetrii brak
cavelog.clear()
s = Swiat(poz=EDRON, hp=100)
ost = {"hp": 0, "max_hp": 210, "poz": list(SPOT), "zapisano": NOW - 800}
b = zrob(s, stan_wyprawy=None, telemetria=None, ostatnie=ost)
tick(s, b, 3)
sprawdz("b7 zapasowo ostatnie.json (hp 0, skok pozycji, zapis sprzed startu) = zgon", na_dysku(b)["karencja_do"] == 0.0)

# --- (c) restart BEZ zgonu z aktywną karencją: karencja nadal działa (przypadek, który musi zostać) ---------------------
casy = {
    "c1 ostatnia próbka poprzedniego procesu żywa (HP 100), po prostu restart bota": tele_zgon(hp_serii=(100, 100, 100, 100)),
    "c2 HP 0 w telemetrii, ale postać stoi w TYM SAMYM miejscu (brak respawnu = nie zginęła)": tele_zgon(poz=EDRON),
    "c3 seria HP 0 za krótka (2 próbki w 4 s): zły odczyt, nie zgon": tele_zgon(hp_serii=(0, 0)),
    "c4 brak telemetrii z poprzedniego procesu (nie wiemy)": [],
    "c5 ostatnia próbka sprzed 20 h (poza oknem pewności)": tele_zgon(konc=NOW - 20 * 3600),
}
for nazwa, tel in casy.items():
    cavelog.clear()
    s = Swiat(poz=EDRON, hp=100)
    b = zrob(s, stan_wyprawy=STAN_PK, telemetria=tel)
    wynik = wznow_start.sprobuj(b.fw, cavebot.log, teraz_wall=NOW)
    tick(s, b, 3)
    sprawdz(f"{nazwa}: karencja zostaje, wyprawa PK wznowiona, 'karencja po restarcie' = ucieczka do depo jak dotąd",
            wynik is True and b.fw.wznowien == 1 and na_dysku(b)["karencja_do"] > 0 and b.pk_wrogowie.karencja_aktywna()
            and any("karencja po restarcie" in l or "start w karencji" in l for l in cavelog) and s.starty == ["ucieczka"]
            and not any("RESET PO ZGONIE" in l for l in cavelog), (wynik, b.fw.wznowien, na_dysku(b)["karencja_do"], cavelog[-3:], s.starty))
# c6: brak zapisu wyprawy PK, tylko karencja (restart w karencji bez zgonu) = ucieczka do depo jak dotąd
cavelog.clear()
s = Swiat(poz=EDRON, hp=100)
b = zrob(s, stan_wyprawy=None, telemetria=tele_zgon(hp_serii=(100,) * 4))
tick(s, b, 3)
sprawdz("c6 sam restart w karencji (bez zgonu, bez wyprawy) = jak dotąd: 'karencja po restarcie' i ucieczka", s.starty == ["ucieczka"]
        and any("karencja po restarcie" in l for l in cavelog), (s.starty, cavelog[-3:]))
# c7: postać po restarcie nadal martwa (HP 0 teraz) nie resetuje przy starcie
s = Swiat(poz=SPOT, hp=0)
b = zrob(s, stan_wyprawy=STAN_PK, telemetria=tele_zgon())
tick(s, b, 2)
sprawdz("c7 po restarcie HP nadal 0 w miejscu zgonu = przy starcie bez resetu (reset zrobi pętla po 8 s)", na_dysku(b)["karencja_do"] > 0)

# --- (h) zwykła wyprawa nietknięta ----------------------------------------------------------------------------------
cavelog.clear()
s = Swiat(poz=EDRON, hp=100)
b = zrob(s, stan_wyprawy=STAN_BLANKI, telemetria=tele_zgon())
wynik = wznow_start.sprobuj(b.fw, cavebot.log, teraz_wall=NOW)
sprawdz("h1 zgon + zwykła wyprawa po blanki (potrzeby bez pk): zapis nietknięty i nadal wznawiana; karencja zerowana",
        wynik is True and b.fw.wznowien == 1 and b.fw._stan_czytaj()["aktywna"] is True and b.fw._stan_czytaj().get("wynik") != "pk_zgon"
        and na_dysku(b)["karencja_do"] == 0.0, (wynik, b.fw._stan_czytaj()))

# --- (d) pokrętło 0 = stare zachowanie bit w bit --------------------------------------------------------------------
cavelog.clear()
s = Swiat(poz=EDRON, hp=100)
b = zrob(s, knob=0, stan_wyprawy=STAN_PK, telemetria=tele_zgon())
wywolania = []
_orig = pk_zgon.zgon_przed_startem
pk_zgon.zgon_przed_startem = lambda *a, **k: wywolania.append(a) or _orig(*a, **k)
wynik = wznow_start.sprobuj(b.fw, cavebot.log, teraz_wall=NOW)
tick(s, b, 3)
pk_zgon.zgon_przed_startem = _orig
sprawdz("d1 PK_RESET_PO_ZGONIE=0, restart po zgonie: wyprawa PK wznowiona, karencja zostaje, 'karencja po restarcie' = stare zachowanie",
        wynik is True and b.fw.wznowien == 1 and na_dysku(b)["karencja_do"] > 0 and s.starty == ["ucieczka"]
        and any("karencja po restarcie" in l for l in cavelog), (wynik, na_dysku(b)["karencja_do"], s.starty))
sprawdz("d2 pokrętło 0: nowy kod nie czyta dysku ani nie loguje resetu, brak stanu 'martwy'",
        not wywolania and not any("RESET" in l for l in cavelog) and not b._zgon_martwy and b._zgon_start_wynik is None, wywolania)
cavelog.clear()
s = Swiat(stwory=[gr("Ogr", 3, 0)])
b = zrob(s, knob=0, stan_wyprawy=STAN_PK, telemetria=[])
tick(s, b, 3)
s.hp = 0
tick(s, b, 12)
sprawdz("d3 pokrętło 0, zgon w grze: karencja przedłużana, stan PK i wyprawa bez zmian (jak przed zmianą)",
        na_dysku(b)["karencja_do"] > 0 and not b._zgon_martwy and b.fw._stan_czytaj().get("aktywna") is True
        and not any("RESET" in l for l in cavelog), (na_dysku(b)["karencja_do"], b.pk_stan))

# --- (g) SMIERC_STOP=1: zgon potwierdzony starym detektorem też resetuje -----------------------------------------------
cavelog.clear()
s = Swiat(stwory=[gr("Ogr", 3, 0)])
b = zrob(s, stan_wyprawy=STAN_PK, telemetria=[], smierc_stop=1)
tick(s, b, 3)
s.hp = 0
tick(s, b, 4)
sprawdz("g1 SMIERC_STOP=1: zgon (3 odczyty HP 0) = stan MARTWY, STOP i reset PK (karencja 0, pk_stan None, wyprawa PK odrzucona)",
        b.martwy and b.stopy and na_dysku(b)["karencja_do"] == 0.0 and b.pk_stan is None
        and b.fw._stan_czytaj().get("wynik") == "pk_zgon", (b.martwy, b.stopy, na_dysku(b)["karencja_do"]))
cavebot.SMIERC_STOP = 0

# --- (e) pk_zgon.py: heurystyka i granice ----------------------------------------------------------------------------
t0 = pk_zgon.zgon_z_telemetrii(tele_zgon(), EDRON, 210, NOW)
sprawdz("e1 seria HP 0 na (32657,31967,8) + żywa w Edronie = zgon", t0[0] and "seria HP 0" in t0[1], t0)
sprawdz("e2 martwa teraz (HP 0) albo HP nieodczytane = nie rozstrzygamy",
        not pk_zgon.zgon_z_telemetrii(tele_zgon(), EDRON, 0, NOW)[0] and not pk_zgon.zgon_z_telemetrii(tele_zgon(), EDRON, None, NOW)[0])
sprawdz("e3 ten sam teren (skok 5 pól na tym piętrze) = nie respawn; inne piętro o 1 = skok",
        not pk_zgon.zgon_z_telemetrii(tele_zgon(), (SPOT[0] + 5, SPOT[1], 8), 210, NOW)[0]
        and pk_zgon.zgon_z_telemetrii(tele_zgon(), (SPOT[0], SPOT[1], 7), 210, NOW)[0])
sprawdz("e4 seria HP 0 przerwana żywą próbką (potem żył) = nie zgon",
        not pk_zgon.zgon_z_telemetrii(tele_zgon() + [{"t": NOW - 100, "typ": "probka", "poz": list(EDRON), "hp": 100}], EDRON, 210, NOW)[0])
sprawdz("e5 próbki bez HP (None) w końcówce = nie zgon", not pk_zgon.zgon_z_telemetrii(
    [{"t": NOW - 100 + i, "typ": "probka", "poz": list(SPOT), "hp": None} for i in range(6)], EDRON, 210, NOW)[0])
# rekordy_ogon: ucięta pierwsza linia, wiele typów, poprzedni dzień
kat = TMP / "ogon"
kat.mkdir()
(kat / "telemetria-20261025.jsonl").write_text("".join(json.dumps(r) + "\n" for r in tele_zgon()[:3]))
(kat / "telemetria-20261026.jsonl").write_text('{"t": 1, "typ": "probka", "hp"' + "\n"
                                               + json.dumps({"t": NOW - 5, "typ": "decyzja"}) + "\n"
                                               + json.dumps({"t": NOW - 4, "typ": "probka", "poz": list(EDRON), "hp": 100}) + "\n" + "{złamana linia\n")
r = pk_zgon.rekordy_ogon(kat, tail_bajtow=100)
sprawdz("e6 rekordy_ogon: pomija uciętą/złamaną linię i zdarzenia inne niż probka/smierc; rosnąco po t",
        [x["typ"] for x in r] == ["probka"] and r[0]["t"] == NOW - 4, r)
r = pk_zgon.rekordy_ogon(kat)
sprawdz("e7 rekordy_ogon: dochodzi po nowszym pliku także poprzedni dzień, gdy nowszy nie ma żywej próbki", len(r) >= 1, r)
(kat / "telemetria-20261026.jsonl").write_text("")
r = pk_zgon.rekordy_ogon(kat)
sprawdz("e8 pusty nowszy plik = rekordy z poprzedniego dnia", len(r) == 3, r)
def plik_json(nazwa, dane):
    f = TMP / nazwa
    f.write_text(json.dumps(dane))
    return f


zo = lambda f, poz=EDRON, hp=210: pk_zgon.zgon_z_ostatnie(f, poz, hp, NOW, przed=NOW)[0]   # noqa: E731
bazowy = {"hp": 0, "max_hp": 210, "poz": list(SPOT), "zapisano": NOW - 800}
sprawdz("e9 ostatnie.json: hp 0 + skok + zapis sprzed startu = zgon", zo(plik_json("o0.json", bazowy)))
sprawdz("e10 ostatnie.json: brak pliku / hp > 0 / zapis po starcie procesu / bez skoku / za stary / martwa teraz = nie zgon",
        not zo(TMP / "brak.json") and not zo(plik_json("o1.json", dict(bazowy, hp=50)))
        and not zo(plik_json("o2.json", dict(bazowy, zapisano=NOW + 1))) and not zo(plik_json("o3.json", bazowy), poz=SPOT)
        and not zo(plik_json("o4.json", dict(bazowy, zapisano=NOW - 20 * 3600))) and not zo(plik_json("o5.json", bazowy), hp=0))


print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
