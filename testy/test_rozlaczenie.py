#!/usr/bin/env python3
"""21.10 (ROZLACZENIE_STOP, spec dane_tibia/SPEC_rozlaczenie_1021.md): serwer wylogował postać (10:00:01), klient pokazuje
ekran logowania, a pamięć gry stoi, więc bot przez 9-17 min wysyłał strzałki w próżnię. Offline: bez gry, X11 i sesji.

Odtwarza sekwencję bobra z 10:00:02: żywy świat (moby, HP rośnie), potem WSZYSTKO stoi, a zrzut pokazuje „Character List”.
Czego dowodzi:
  (A) detektor: alarm raz, 25-31 s po zamrożeniu; zdrowa gra (pamięć stoi, zrzut = gra) i brak zrzutu = 0 alarmów;
      zdrowa gra ze zmieniającą się pamięcią nie robi ani jednego zrzutu; wznowienie po 2 zrzutach gry albo 3 zmianach pamięci;
  (B) klasyfikator: tapeta logowania (także przeskalowana) -> True, klatki gry z repo -> False, brak wzorca -> None;
  (C) cavebot: po alarmie ZERO klawiszy/ataków przez 5 minut, jedno powiadomienie z nazwą postaci, jeden rekord 'rozlaczenie';
      po powrocie do gry praca wraca; pokrętło 0 = bot wysyła klawisze jak dziś (brak zrzutów, powiadomień, telemetrii);
      pokrętło 1 w zdrowym postoju = sekwencja klawiszy IDENTYCZNA jak przy 0;
  (D) mozg: w rozłączeniu nie wykonuje akcji modelu ani czatu, przy pokrętle 0 blokada nieaktywna;
  (E) pokrętło: w kodzie domyślnie 0; wpis do pokretla.ZAKRESY/przykładu sprawdzany, gdy lead go doda (INFO, gdy jeszcze brak)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import random
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
KORZEN = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
import bot  # noqa: E402
import cavebot  # noqa: E402
import mozg  # noqa: E402
import pokretla  # noqa: E402
try:
    import rozlaczenie  # noqa: E402
except ImportError:          # stary kod (przed zmianą): testy poniżej mają wtedy dać FAIL, nie wyjątek
    rozlaczenie = None

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


KROK = 1.2          # s między obiegami (jak próbki telemetrii)


# ---------------------------------------------------------------------------------------------------- (A) detektor
def odcisk_zywy(i):
    return ((100, 100, 20, 20, 50, 1000 + i, 6), (32037, 32226, 9), ((1, 32037, 32226, 9, 99, 2),))


ODCISK_STOI = ((98, 175, 25, 25, 151, 2409, 6), (32037, 32226, 9), ((1, 32037, 32226, 9, 99, 2),))

if rozlaczenie is None:
    sprawdz("A0 moduł rozlaczenie.py istnieje", False, "brak modułu (stary kod)")
else:
    def przebieg(det, zywe_s, stoi_s, zrzut, t0=0.0, krok=KROK, odciski=None):
        """zywe_s: odcisk zmienia się co obieg; potem stoi stoi_s. Zwraca [(t, wynik)], liczbę zrzutów, t zamrożenia."""
        zdarzenia, zrzuty = [], [0]

        def z():
            zrzuty[0] += 1
            return zrzut(t) if callable(zrzut) else zrzut
        t, i = t0, 0
        while t < t0 + zywe_s:
            w = det.krok(t, odcisk_zywy(i), z)
            if w:
                zdarzenia.append((t, w))
            t += krok
            i += 1
        t_zam = t
        while t < t_zam + stoi_s:
            w = det.krok(t, ODCISK_STOI, z)
            if w:
                zdarzenia.append((t, w))
            t += krok
        return zdarzenia, zrzuty[0], t_zam

    det = rozlaczenie.Detektor()
    zd, nz, t_zam = przebieg(det, 60, 300, True)
    al = [t for t, w in zd if w == "rozlaczenie"]
    sprawdz("A1 wylogowanie (pamięć stoi, zrzut = logowanie): jeden alarm", len(al) == 1 and len(zd) == 1, f"{zd}")
    sprawdz("A2 alarm 25-31 s po zamrożeniu (nie wcześniej)", al and 25.0 <= al[0] - t_zam <= 31.0, f"{al} t_zam={t_zam}")
    sprawdz("A3 po alarmie stan 'rozlaczony' i zamrożone_s zapisane", det.rozlaczony and det.zamrozone_s >= 25.0)

    det = rozlaczenie.Detektor()
    zd, nz, t_zam = przebieg(det, 60, 600, False)
    sprawdz("A4 zdrowa gra: pamięć stoi 10 min, zrzut = gra: 0 alarmów i bez wznowień", not zd, f"{zd}")
    sprawdz("A5 koszt: zrzut co ~5 s po 10 s zamrożenia (80-120 w 10 min, nie co obieg)", 80 <= nz <= 120, f"{nz}")

    det = rozlaczenie.Detektor()
    zd, nz, _ = przebieg(det, 60, 600, None)
    sprawdz("A6 zrzut niedostępny (None): 0 alarmów", not zd, f"{zd}")

    det = rozlaczenie.Detektor()
    zd, nz, _ = przebieg(det, 600, 0, True)
    sprawdz("A7 pamięć cały czas się zmienia (zdrowa gra): ANI JEDNEGO zrzutu i 0 alarmów", nz == 0 and not zd, f"zrzutów {nz}")

    det = rozlaczenie.Detektor()
    zd, nz, _ = przebieg(det, 10, 300, lambda t: (int(t // 5) % 2 == 0))      # zrzuty na zmianę: logowanie / gra
    sprawdz("A8 pojedyncze zrzuty z logowaniem nie wystarczą (potrzebne 2 z rzędu)", not zd, f"{zd}")

    det = rozlaczenie.Detektor()
    zd, nz, t_zam = przebieg(det, 10, 20, True)          # tylko 20 s zamrożenia < 25 s
    sprawdz("A9 zamrożenie 20 s z logowaniem: jeszcze bez alarmu", not zd, f"{zd}")

    # wznowienie: po alarmie zrzuty gry
    det = rozlaczenie.Detektor()
    ekr = {"v": True}
    zd, nz, t_zam = przebieg(det, 10, 60, lambda t: ekr["v"])
    sprawdz("A10 (przygotowanie) alarm poszedł", det.rozlaczony and len(zd) == 1, f"{zd}")
    t = t_zam + 60
    wyniki = []
    ekr["v"] = False
    for _ in range(12):
        t += KROK
        w = det.krok(t, ODCISK_STOI, lambda: ekr["v"])
        if w:
            wyniki.append((round(t - t_zam - 60, 1), w))
    sprawdz("A11 po powrocie do gry (2 zrzuty bez logowania, co 3 s): jedno wznowienie w <= 8 s",
            len(wyniki) == 1 and wyniki[0][1] == "wznowienie" and wyniki[0][0] <= 8.0 and not det.rozlaczony, f"{wyniki}")
    sprawdz("A12 po wznowieniu detektor czysty (nie ogłasza od razu ponownie)", det.t_rozl is None and det.pozytywne == 0)

    # w pauzie pamięć „migocze”, ale zrzut dalej pokazuje logowanie: pauza trwa
    det = rozlaczenie.Detektor()
    zd, nz, t_zam = przebieg(det, 10, 60, True)
    t = t_zam + 60
    w_ost = []
    for i in range(40):
        t += KROK
        w = det.krok(t, odcisk_zywy(1000 + i), lambda: True)
        if w:
            w_ost.append(w)
    sprawdz("A13 pauza: zmieniająca się pamięć przy zrzucie 'logowanie' nie wznawia", not w_ost and det.rozlaczony, f"{w_ost}")

    # wznowienie bez zrzutu (grim niedostępny): 3 zmiany pamięci z rzędu
    det = rozlaczenie.Detektor()
    zd, nz, t_zam = przebieg(det, 10, 60, True)
    t = t_zam + 60
    wz = []
    for i in range(6):
        t += KROK
        w = det.krok(t, odcisk_zywy(2000 + i), lambda: None)
        wz.append(w)
    sprawdz("A14 brak zrzutu, ale pamięć wyraźnie się rusza (3 zmiany z rzędu): wznowienie", "wznowienie" in wz and not det.rozlaczony, f"{wz}")
    det = rozlaczenie.Detektor()
    zd, nz, t_zam = przebieg(det, 10, 60, True)
    t = t_zam + 60
    wz = []
    for i in range(6):
        t += KROK
        wz.append(det.krok(t, odcisk_zywy(3000 + i // 2), lambda: None))      # zmiana, stoi, zmiana, stoi...
    sprawdz("A15 brak zrzutu, pamięć drga co drugi obieg (zmiana, stoi, zmiana, stoi...): bez wznowienia", "wznowienie" not in wz and det.rozlaczony, f"{wz}")

    o1 = rozlaczenie.odcisk({"hp": 1, "max_hp": 2, "exp": 3}, (1, 2, 3), [{"id": 2, "x": 1, "y": 1, "z": 1, "hp": 5}, {"id": 1, "x": 0, "y": 0, "z": 1, "hp": 100}])
    o2 = rozlaczenie.odcisk({"hp": 1, "max_hp": 2, "exp": 3}, [1, 2, 3], [{"id": 1, "x": 0, "y": 0, "z": 1, "hp": 100}, {"id": 2, "x": 1, "y": 1, "z": 1, "hp": 5}])
    o3 = rozlaczenie.odcisk({"hp": 1, "max_hp": 2, "exp": 3}, (1, 2, 3), [{"id": 1, "x": 0, "y": 0, "z": 1, "hp": 100, "kierunek": 3}, {"id": 2, "x": 1, "y": 1, "z": 1, "hp": 5}])
    sprawdz("A16 odcisk: hashowalny, niezależny od kolejności stworów i typu pozycji, wrażliwy na kierunek",
            hash(o1) == hash(o2) and o1 == o2 and o1 != o3)

# ------------------------------------------------------------------------------------------------ (B) klasyfikator
if rozlaczenie is None:
    sprawdz("B0 klasyfikator", False, "brak modułu")
else:
    from PIL import Image  # noqa: E402
    import numpy as np  # noqa: E402
    wz = rozlaczenie.wzorzec()
    sprawdz("B1 wzorzec wczytany (dane_tibia/ekran_logowania_wzorzec.json)", wz is not None and wz.shape == (24, 32, 3))
    if wz is not None:
        from PIL import Image as _I
        # tapeta z wzorca rozciągnięta na 1175x910 i 600x465: klasyfikator rozpoznaje niezależnie od rozmiaru okna
        tapeta = _I.fromarray(np.uint8(np.clip(wz, 0, 255))).resize((1175, 910), _I.BILINEAR)
        sprawdz("B2 tapeta logowania 1175x910 -> True", rozlaczenie.ekran_logowania(tapeta) is True)
        sprawdz("B3 tapeta po przeskalowaniu okna do 600x465 -> True", rozlaczenie.ekran_logowania(tapeta.resize((600, 465))) is True)
        # okno dialogowe w środku (Character List) i pasek FPS u góry nie psują wyniku
        z_oknem = tapeta.copy()
        z_oknem.paste((64, 64, 64), (414, 255, 762, 655))
        z_oknem.paste((0, 0, 0), (0, 0, 1175, 36))
        sprawdz("B4 tapeta z oknem dialogowym i czarnym paskiem u góry -> True", rozlaczenie.ekran_logowania(z_oknem) is True,
                rozlaczenie.zgodnosc(z_oknem))
        prawdziwe = [KORZEN / "instancje/_archiwum/bober-20261021/logi/slepota/20261021-100201.png",
                     KORZEN / "instancje/dawajkesh/logi/slepota/20261021-100159.png",
                     KORZEN / "instancje/kolanoth/logi/slepota/20261021-100200.png"]
        prawdziwe = [p for p in prawdziwe if p.exists()]
        sprawdz("B5 prawdziwe zrzuty logowania z 21.10 10:00 (gdy są na dysku) -> True",
                all(rozlaczenie.ekran_logowania(Image.open(p)) is True for p in prawdziwe), f"{len(prawdziwe)} plików")
        gra = sorted((KORZEN / "testy" / "dane").glob("ogien_*.png")) + sorted((KORZEN / "testy" / "dane").glob("uh_zrzut.png"))
        gra += [p for p in [KORZEN / "instancje/kolanoth/logi/slepota/20261021-145207.png"] if p.exists()]
        wyn = [rozlaczenie.zgodnosc(Image.open(p)) for p in gra]
        sprawdz(f"B6 {len(gra)} klatek gry z repo -> False (zgodność < 0,9, najwyżej {max(wyn) if wyn else 0:.2f})",
                gra and all(w < 0.5 for w in wyn), wyn)
        sprawdz("B7 czarny i biały ekran -> False", rozlaczenie.ekran_logowania(Image.new("RGB", (1175, 910), (0, 0, 0))) is False
                and rozlaczenie.ekran_logowania(Image.new("RGB", (1175, 910), (255, 255, 255))) is False)
        stary = rozlaczenie.PLIK_WZORCA
        rozlaczenie.PLIK_WZORCA, rozlaczenie._wzorzec = Path("/nie/ma/takiego.json"), None
        sprawdz("B8 brak pliku wzorca -> None (nie alarm)", rozlaczenie.ekran_logowania(tapeta) is None)
        rozlaczenie.PLIK_WZORCA, rozlaczenie._wzorzec = stary, None
        sprawdz("B9 zrzut_logowania() nigdy nie rzuca (brak sesji grim -> None)", rozlaczenie.zrzut_logowania() in (None, False, True))


# ------------------------------------------------------------------------------------------------- (C) cavebot
class Swiat:
    """Świat jak u bobra o 10:00:02: żywy do `t_stop`, potem wszystko stoi. Klawisze nic nie zmieniają (postać stoi)."""

    def __init__(s, t_stop=48.0):
        s.t = 0.0
        s.t_stop = t_stop
        s.poz = [32500, 32279, 9]
        s.ekran = True               # co pokazuje zrzut po zamrożeniu: True = ekran logowania
        s.klawisze, s.ataki, s.zapytania, s.zrzuty = [], [], [], 0
        s.blad_gracza = False
        s.zmiana = 0

    def zegar(s):
        return s.t

    def spij(s, d):
        pass

    def zywy(s):
        return s.t < s.t_stop

    def zapytaj(s, z):
        s.zapytania.append(z["cmd"])
        if z["cmd"] == "gracz":
            if s.blad_gracza:
                raise RuntimeError("nie znalazłem statystyk gracza (zalogowany?)")
            n = int(s.t) if s.zywy() else int(s.t_stop)
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 20 + (s.zmiana or 0), "max_mana": 25, "exp": 1000 + n, "level": 6, "cap": 151}}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            if s.zywy():
                szczur = {"id": 8416, "nazwa": "Cave Rat", "gracz": False, "x": s.poz[0] + 6 - int(s.t) % 4, "y": s.poz[1] + 2, "z": s.poz[2], "hp": 100}
                return {"stwory": [ja, szczur]}
            return {"stwory": [ja]}
        return {}


class P:
    nazwa = "Bober Qrwa"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        if p.s.blad_gracza:
            raise RuntimeError("nie widzę postaci Bober Qrwa (zalogowana?)")
        return tuple(p.s.poz)

    def klawisz(p, k):
        p.s.klawisze.append(k)

    def krok(p, k):
        p.s.klawisze.append(k)
        return None


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
    cavebot.ROZLACZENIE_STOP = knob
    cavebot.ROZLACZENIE_WYJSCIE = 0          # 23.10: te testy dotyczą trybu pauzy w żywym procesie; koniec procesu ma testy/test_wylogowanie.py
    cavebot.SMIERC_STOP = 0

    def atak(m, g):
        s.ataki.append(m["id"])
    loot = types.SimpleNamespace(zbierz=lambda zw, g: "ok")
    punkty = [(32500 + i, 32279, 9) for i in range(1, 11)]
    b = cavebot.Cavebot(P(s), punkty, okrazenia=999, zapytaj=s.zapytaj, atak=atak, alarm=lambda w: None,
                        spij=s.spij, zegar=s.zegar, loot=loot)
    b.stopy, b.pow = [], []
    b._pk_stop = lambda opis: b.stopy.append(opis)
    b._pk_powiadom = lambda tytul, tresc, klucz: b.pow.append((tytul, tresc, klucz))
    b.tele = Tele()

    def zrzut():
        s.zrzuty += 1
        return s.ekran
    b._rozl_zrzut = zrzut          # wstrzyknięcie zrzutu (domyślnie rozlaczenie.zrzut_logowania)
    return b


def obiegi(b, s, n, krok=KROK):
    """n obiegów; zwraca listę (t, liczba akcji gry narastająco)."""
    wynik = []
    for _ in range(n):
        s.t += krok
        b.tick()
        wynik.append((s.t, len(s.klawisze) + len(s.ataki), bool(getattr(b, "rozlaczony", False))))
    return wynik


def akcje(s):
    return len(s.klawisze) + len(s.ataki)


# C1: pokrętło 1, wylogowanie: po alarmie zero klawiszy przez 5 minut
random.seed(7)
s = Swiat()
b = zrob(s, 1)
przed = obiegi(b, s, 40)                      # 48 s żywej gry
sprawdz("C0 (przygotowanie) żywa gra: bot chodzi (klawisze/ataki), bez alarmu", akcje(s) > 0 and not b.pow, f"{akcje(s)} {b.pow}")
a0 = akcje(s)
po = obiegi(b, s, 300)                        # 6 min zamrożenia, zrzut = ekran logowania
t_alarm = next((t for t, _, r in po if r), None)
sprawdz("C1 alarm: pokrętło 1, bot wie, że jest rozłączony (b.rozlaczony)", getattr(b, "rozlaczony", False) is True, f"{getattr(b, 'rozlaczony', None)}")
sprawdz("C2 jedno powiadomienie, critical-klucz 'rozlaczenie', z nazwą postaci i czasem",
        len(b.pow) == 1 and b.pow[0][2] == "rozlaczenie" and "Bober Qrwa" in b.pow[0][1] and b.pow[0][1].count("\n") <= 2, f"{b.pow}")
rz = [d for t, d in b.tele.zd if t == "rozlaczenie"]
sprawdz("C3 telemetria: jeden rekord 'rozlaczenie' (poz, zamrożone_s)", len(rz) == 1 and rz[0].get("poz") == [32500, 32279, 9]
        and rz[0].get("zamrozone_s", 0) >= 25, f"{rz}")
sprawdz("C4 w logu wpis ROZŁĄCZENIE", any("ROZŁĄCZENIE" in l for l in cavelog), cavelog[-3:])
a_przy_alarmie = next((a for t, a, _ in po if t >= 48.0 + 31.0), None)
sprawdz("C5 po alarmie ZERO klawiszy, ataków i kliknięć do końca 5 minut (akcje po t=48+31 s nie rosną)",
        a_przy_alarmie is not None and akcje(s) == a_przy_alarmie, f"po alarmie {a_przy_alarmie}, na końcu {akcje(s)}")
sprawdz("C6 alarm 25-33 s po zamrożeniu świata (t=48 s), nie 5 min", t_alarm is not None and 25.0 <= t_alarm - 48.0 <= 33.0, f"t_alarm={t_alarm}")
sprawdz("C7 bez STOP i bez kończenia (tick dalej zwraca True, nie wyjątek)", not b.stopy)
sprawdz("C8 zrzuty rzadko: pauza co 3 s przez 5 min <= 150 zrzutów", s.zrzuty <= 150, s.zrzuty)

# C9: powrót do gry: zrzut bez ekranu logowania -> wznowienie, klawisze wracają
s.t_stop = 1e9      # świat znów żywy: pamięć się rusza
s.ekran = False
a_pauza = akcje(s)
po = obiegi(b, s, 60)
koniec = [d for t, d in b.tele.zd if t == "rozlaczenie_koniec"]
sprawdz("C9 powrót do gry: wznowienie (b.rozlaczony False), rekord 'rozlaczenie_koniec' z czasem trwania",
        getattr(b, "rozlaczony", True) is False and len(koniec) == 1 and koniec[0].get("czas_s", 0) > 100, f"{koniec}")
sprawdz("C10 po wznowieniu bot znów chodzi (klawisze/ataki rosną), bez drugiego powiadomienia", akcje(s) > a_pauza and len(b.pow) == 1,
        f"{akcje(s) - a_pauza} {len(b.pow)}")

# C11: pokrętło 0: dokładnie jak dziś (brak zrzutów, powiadomień, rekordów, pauzy)
random.seed(7)
s0 = Swiat()
b0 = zrob(s0, 0)
obiegi(b0, s0, 40)
a0 = akcje(s0)
obiegi(b0, s0, 300)
rz0 = [t for t, _ in b0.tele.zd if t in ("rozlaczenie", "rozlaczenie_koniec")]
sprawdz("C11 pokrętło 0: bot nadal wysyła klawisze w zamrożonym świecie (zachowanie jak dziś)", akcje(s0) - a0 > 30, f"{akcje(s0) - a0}")
sprawdz("C12 pokrętło 0: brak zrzutów, powiadomień, telemetrii i stanu rozlaczony", s0.zrzuty == 0 and not b0.pow and not rz0
        and not getattr(b0, "rozlaczony", False), f"{s0.zrzuty} {b0.pow} {rz0}")
seq0 = list(s0.klawisze)
import hashlib  # noqa: E402
print("INFO C11 skrót sekwencji klawiszy przy pokrętle 0 (do porównania ze starym kodem): "
      + hashlib.md5(json.dumps([list(map(str, s0.klawisze)), len(s0.ataki)]).encode()).hexdigest()[:12])

# C13: pokrętło 1, zdrowy postój (pamięć stoi, ale zrzut = gra): sekwencja klawiszy bit w bit jak przy 0
random.seed(7)
s1 = Swiat()
s1.ekran = False
b1 = zrob(s1, 1)
obiegi(b1, s1, 40)
obiegi(b1, s1, 300)
rz1 = [t for t, _ in b1.tele.zd if t in ("rozlaczenie", "rozlaczenie_koniec")]
sprawdz("C13 pokrętło 1, zdrowa gra z postojem: bez alarmu, powiadomień i rekordów", not b1.pow and not rz1
        and not getattr(b1, "rozlaczony", False), f"{b1.pow} {rz1}")
sprawdz("C14 pokrętło 1, zdrowa gra: sekwencja klawiszy IDENTYCZNA jak przy pokrętle 0", s1.klawisze == seq0 and s1.zrzuty > 0 and s1.zrzuty <= 80,
        f"{len(s1.klawisze)} vs {len(seq0)}, zrzutów {s1.zrzuty}")

# C15: pokrętło 1, zrzut niedostępny (None): bot nie jest pauzowany
random.seed(7)
s2 = Swiat()
s2.ekran = None
b2 = zrob(s2, 1)
obiegi(b2, s2, 40)
a0 = akcje(s2)
obiegi(b2, s2, 300)
sprawdz("C15 zrzut niedostępny: brak alarmu, bot pracuje jak dziś", not b2.pow and akcje(s2) - a0 > 30, f"{b2.pow} {akcje(s2) - a0}")

# C16: pauza odporna na brak statystyk gracza (trwa logowanie); wznowienie, gdy zrzut znika
random.seed(7)
s3 = Swiat()
b3 = zrob(s3, 1)
obiegi(b3, s3, 40)
obiegi(b3, s3, 60)
sprawdz("C16a (przygotowanie) rozłączony", getattr(b3, "rozlaczony", False) is True)
s3.blad_gracza = True
blad = None
try:
    a0 = akcje(s3)
    obiegi(b3, s3, 30)
except Exception as e:      # noqa: BLE001
    blad = e
sprawdz("C16 pauza: błąd odczytu gracza w trakcie rozłączenia nie wywraca ticka i nie wysyła klawiszy", blad is None and akcje(s3) == a0, f"{blad!r}")
s3.blad_gracza = False
s3.t_stop = 1e9
s3.ekran = None            # zrzut niedostępny, ale pamięć wyraźnie się rusza (nowy świat)
obiegi(b3, s3, 30)
sprawdz("C17 brak zrzutu, ale pamięć się rusza: wznowienie", getattr(b3, "rozlaczony", True) is False, f"{getattr(b3, 'rozlaczony', None)}")

# C18: ręczne cofnięcie w trakcie pauzy (ROZLACZENIE_STOP 1 -> 0) zwalnia bota od razu
random.seed(7)
s4 = Swiat()
b4 = zrob(s4, 1)
obiegi(b4, s4, 100)
a0 = akcje(s4)
sprawdz("C18a (przygotowanie) rozłączony i cisza", getattr(b4, "rozlaczony", False) is True)
cavebot.ROZLACZENIE_STOP = 0
obiegi(b4, s4, 30)
sprawdz("C18 pokrętło 1 -> 0 w pauzie: bot wraca do pracy natychmiast (klawisze rosną)", akcje(s4) > a0, f"{akcje(s4) - a0}")

# ---------------------------------------------------------------------------------------------------- (D) mozg
cavebot.ROZLACZENIE_STOP = 1
s5 = Swiat()
b5 = zrob(s5, 1)
obiegi(b5, s5, 120)


class Model:
    def __init__(m):
        m.n = 0

    def __call__(m, prompt):
        m.n += 1
        return '{"akcje": [{"typ": "kontynuuj"}]}', {"duration_ms": 1}


mdl = Model()
wysl = []
mz = mozg.Mozg("hybryda", zapytaj=s5.zapytaj, nazwa="Bober Qrwa", model=mdl, cb=b5,
               pamiec=mozg.Pamiec(Path(tempfile.mkdtemp()) / "pamiec.json"), log=lambda *a: None,
               zegar=s5.zegar, czat_wyslij=wysl.append, trasy=lambda: ["x"], losuj=lambda a, c: a, alarm=lambda w: None)
sprawdz("D0 (przygotowanie) cavebot rozłączony", getattr(b5, "rozlaczony", False) is True)
mz.decyzje.append({"akcje": [{"typ": "idz_do", "x": 32503, "y": 32279, "z": 9}], "czas": s5.t})
k0 = akcje(s5)
blad = None
try:
    mz.obieg_hybrydy()
    mz.wykonaj([{"typ": "idz_do", "x": 32503, "y": 32279, "z": 9}, {"typ": "napisz_na_czacie", "tekst": "hej"}], {"czas": s5.t})
except Exception as e:      # noqa: BLE001  stary kod: model dostaje akcje i pada na atrapie
    blad = e
sprawdz("D1 mozg w rozłączeniu: zero wywołań modelu, decyzje wyczyszczone, brak ruchu i czatu",
        blad is None and mdl.n == 0 and not mz.decyzje and akcje(s5) == k0 and not wysl,
        f"n={mdl.n} dec={len(mz.decyzje)} wysl={wysl} blad={blad!r}")
cavebot.ROZLACZENIE_STOP = 0
sprawdz("D2 mozg przy pokrętle 0: blokada nieaktywna", getattr(mz, "_rozlaczony", lambda: True)() is False)
cavebot.ROZLACZENIE_STOP = 1
b5.rozlaczony = False
sprawdz("D3 mozg po wznowieniu (rozlaczony False): blokada zdjęta", getattr(mz, "_rozlaczony", lambda: True)() is False)

# ------------------------------------------------------------------------------------------------ (E) pokrętło
src = (KORZEN / "cavebot.py").read_text()
sprawdz("E1 pokrętło w cavebot.py, domyślnie 1 (23.10: było 0; gebelish/odchyd bez klucza w na_zywo.json)", "\nROZLACZENIE_STOP = 1 " in src)
przyklad = json.loads((KORZEN / "na_zywo.przyklad.json").read_text())
if "ROZLACZENIE_STOP" in pokretla.ZAKRESY or "ROZLACZENIE_STOP" in przyklad:
    sprawdz("E2 pokrętło w pokretla.ZAKRESY (0,1), przykład 1, analityk nie obniży (nie_nizej; 23.10)",
            pokretla.ZAKRESY.get("ROZLACZENIE_STOP") == (0, 1) and przyklad.get("ROZLACZENIE_STOP") == 1
            and pokretla.KIERUNEK.get("ROZLACZENIE_STOP") == "nie_nizej")
else:
    print("INFO E2 wpisy pokretla.ZAKRESY/KIERUNEK i na_zywo.przyklad.json doda lead (poza zakresem plików tej zmiany)")

print(f"\nWYNIK: {sum(ok)} / {len(ok)}")
sys.exit(0 if all(ok) else 1)
