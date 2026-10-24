"""Płynny marsz serwisu (23.10, invincible, Edron, krok `jedzenie`: „chodzi po 1 kratce”). Offline: bez gry, X11 i gniazd.

Przyczyny z logu `instancje/invincible/serwis-1023-trolle.log` (dowód w STAN.md, wpis 23.10 „marsz płynny”):
 (1) z6, korytarz do Mirabell (33172,31817) -> (33173,31803): 17 kroków STRZAŁKĄ w 14,0 s (0,82 s/krok), ani jednego kliku. Mapa ma tam
     pola z flagą 2 w kolorze 129 (dekoracje, bez odpowiednika piętro obok), a `schody_w_prostokacie` traktowało KAŻDE takie pole jak
     schody i skracało klik aż do 1 (= strzałka) dla całego odcinka;
 (2) strzałka zaraz po kliku szła w trakcie ostatniego kroku kliku (pozycja zmienia się na STARCIE kroku, a `_RUCH["koniec"]` nie znał kliku):
     klient ją odrzucał, „krok Down … bez skutku (po kroku: None)” i 1,5 s stania, dwa razy w jednym przebiegu;
 (3) tempo strzałek 0,72-0,82 s/krok przy kroku ok. 0,4-0,5 s: martwy czas między krokami (patrz idz_pewnie, `_po_kroku`).
Klient modelowany jak w test_serwis_schody: klik w linii prostej idzie prosto, klik po skosie/zakręcie może przejść przez róg, więc prostokąt
z PRAWDZIWYMI schodami (odpowiednik piętro obok albo kolor 210) wciąga na inne piętro."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
_os.environ.setdefault("RETRONIC_ID", "tstplynny")
_os.environ.pop("DISPLAY", None)
_os.environ.pop("WAYLAND_DISPLAY", None)
import random
import sys
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import ekran
import mapa as _mapa
import marsz_klik
import serwis as S


class _ZakazMyszy:
    def __init__(self, *a, **k):
        raise RuntimeError("test nie klika w grę")


ekran.Mysz = _ZakazMyszy                          # zabezpieczenie: żaden klik nie dotrze do prawdziwej gry
ekran.klik_pola = lambda dx, dy, *a, **k: None

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


class Zegar:
    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
        return self.t

    def time(self):
        return self.t

    def sleep(self, x):
        self.t += x


ZEGAR = Zegar()
S.time = ZEGAR
KIER = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}


class Plac:
    """Plac 60 x 40, wszystko chodliwe, prędkość pola 10 (szacunek serwisu 0,47 s/krok). `schody` = {(x, y): (kolor, odpowiednik)},
    `dekor` = pola flagi 2 w kolorze 129 bez odpowiednika."""

    def __init__(self, schody=(), dekor=(), sciany=()):
        self.schody, self.dekor, self.sciany = set(schody), set(dekor), set(sciany)

    def flagi(self, x, y, z):
        if not (0 <= x < 60 and 0 <= y < 40) or (x, y) in self.sciany:
            return 0
        return 3 if z == 7 and ((x, y) in self.schody or (x, y) in self.dekor) else 1     # schody/dekor tylko na z7 (brak odpowiednika)

    def pole(self, x, y, z):
        f = self.flagi(x, y, z)
        if not f:
            return None
        return (f, 210 if (x, y) in self.schody else (129 if (x, y) in self.dekor else 24), 10)


class OdpowiednikPietro:
    """Mapa z odpowiednikiem schodów piętro wyżej (z-1): flaga 2 na tych samych polach (tak wygląda prawdziwe przejście)."""

    def __init__(self, baza):
        self.baza = baza

    def flagi(self, x, y, z):
        if z == 6:
            return 3 if (x, y) in self.baza.schody else 1
        return self.baza.flagi(x, y, z)

    def pole(self, x, y, z):
        return self.baza.pole(x, y, z)


class Akcje:
    nick = "Ja"

    def __init__(self, stwory=()):
        self.st = list(stwory)

    def _stwory(self):
        return [{"x": x, "y": y, "z": 7, "nazwa": "Inny"} for x, y in self.st]


class Swiat:
    """Atrapa postaci. Krok trwa `K` s. Klient przyjmuje klawisz najwcześniej `OKNO` s przed końcem trwającego kroku (kolejka na jeden krok:
    wtedy następny krok rusza w chwili końca poprzedniego); wcześniej klawisz jest odrzucany i kosztuje 1,5 s (jak w logu 12:03). To
    założenie o kliencie jest niezmierzone na żywo: serwis wyłącza płynny marsz przy pierwszym odrzuceniu (testy 4i-4j).
    Klik: ustawia pozycję na klikniętym polu (postać idzie ciągiem: koniec kroku w K s); prostokąt z marginesem 1 z prawdziwymi
    schodami przy kliku po skosie/zakręcie (nie w linii prostej) = zmiana piętra. Zlicza strzałki i kliki."""

    OKNO = 0.15

    def __init__(self, poz, mp, K=0.47, z=7, slepe=()):
        self.p = [poz[0], poz[1], z]
        self.mp, self.K, self.slepe = mp, K, set(slepe)
        self.koniec = 0.0
        self.strzalki, self.kliki, self.odrzucone, self.pietro = [], [], 0, 0

    def pozycja(self):
        ZEGAR.t += 0.004
        return tuple(self.p)

    def _schody(self, x, y):
        return (x, y) in getattr(self.mp, "schody", set()) or (x, y) in getattr(getattr(self.mp, "baza", None), "schody", set())

    def krok(self, klawisz):
        d = KIER[klawisz]
        start = tuple(self.p[:2])
        cel = (start[0] + d[0], start[1] + d[1])
        self.strzalki.append((round(ZEGAR.t - 1000.0, 3), klawisz, start))
        ZEGAR.t += 0.01
        if ZEGAR.t < self.koniec - self.OKNO:
            self.odrzucone += 1
            ZEGAR.t += 1.5
            return None
        if cel in self.slepe or not self.mp.flagi(cel[0], cel[1], 7) & 1:
            ZEGAR.t += 1.5
            return None
        ZEGAR.t = max(ZEGAR.t, self.koniec)                  # klawisz w kolejce: krok rusza w chwili końca poprzedniego
        if self._schody(*cel):
            self.p[2] = 6
            self.pietro += 1
            return tuple(self.p)
        self.p[0], self.p[1] = cel
        self.koniec = ZEGAR.t + self.K
        ZEGAR.t += random.uniform(0.07, 0.17)
        return (cel[0], cel[1], self.p[2])


def klik_model(sw):
    def klik(postac, poz, cel_kl, dalej, **kw):
        x0, x1 = sorted((poz[0], cel_kl[0]))
        y0, y1 = sorted((poz[1], cel_kl[1]))
        prosty = poz[0] == cel_kl[0] or poz[1] == cel_kl[1]
        m = 0 if prosty else 1
        schody = any(sw._schody(x, y) for x in range(x0 - m, x1 + m + 1) for y in range(y0 - m, y1 + m + 1))
        dekor = any((x, y) in getattr(sw.mp, "dekor", set()) for x in range(x0 - 1, x1 + 2) for y in range(y0 - 1, y1 + 2))
        sw.kliki.append((tuple(poz[:2]), tuple(cel_kl[:2]), schody, dekor))
        if schody and not prosty:
            sw.p[2] = 6
            sw.pietro += 1
            return "pietro"
        d = max(abs(cel_kl[0] - poz[0]), abs(cel_kl[1] - poz[1]))
        ZEGAR.t += 0.25 + 0.4 * d
        sw.p[0], sw.p[1] = cel_kl[0], cel_kl[1]
        sw.koniec = ZEGAR.t + sw.K                      # pozycja zmienia się na STARCIE ostatniego kroku
        return "ruch"
    return klik


def nowy():
    ZEGAR.t = 1000.0
    S._RUCH.update(koniec=0.0, skala=1.0)
    S._RUCH.pop("plynny_wyl", None)
    S._RUCH.pop("podejrzany", None)
    random.seed(7)


def marsz(sw, cel, tol=0, akcje=None, maks_s=120.0):
    marsz_klik.klik_i_czekaj = klik_model(sw)
    logi, stan = [], {}
    r = S.idz_pewnie(sw, sw.mp, akcje or Akcje(), cel, tol, maks_s=maks_s, log=logi.append, unik=[], stan=stan)
    return r, logi, stan


# --- 1. prawdziwa mapa Edronu: odcinki z logu --------------------------------------------------------------------------

if _mapa.PLIK_MAPY.is_file():
    MP = _mapa.mapa()
    nowy()
    sw = Swiat((33172, 31817), MP, z=6)
    sw._schody = lambda x, y: S.pole_schodow_lub_dziur(MP, x, y, 6) and marsz_klik.koszt_pola(MP, x, y, 6) is None
    r, logi, st = marsz(sw, (33173, 31803, 6))
    sprawdz("1a z6 korytarz do Mirabell (log 12:03: 17 strzałek, 0 klików): dochodzi do celu na z6", r is True and tuple(sw.p) == (33173, 31803, 6), (r, sw.p))
    sprawdz("1b korytarz z6: strzałki tylko przy schodach (<= 4), reszta klikiem (>= 3 kliki)", len(sw.strzalki) <= 4 and len(sw.kliki) >= 3,
            (len(sw.strzalki), len(sw.kliki)))
    sprawdz("1c żaden klik nie wciągnął na schody, brak nieudanych kroków", sw.pietro == 0 and sw.odrzucone == 0 and not any("bez skutku" in l for l in logi),
            (sw.pietro, sw.odrzucone, logi[-2:]))
    sprawdz("1d wiersz podsumowania marszu podaje liczbę klików (dowód w logu, ile szło klikiem)", any("klik" in l and "marsz do" in l for l in logi), logi[-1:])

    nowy()
    sw = Swiat((33168, 31811), MP, z=7)
    sw._schody = lambda x, y: S.pole_schodow_lub_dziur(MP, x, y, 7)
    r, logi, st = marsz(sw, (33171, 31818, 7))
    sprawdz("1e z7 od lądowania schodów z8 do schodów na z6: dochodzi, strzałki tylko tuż przy schodach (<= 6 z 10 pól), reszta klikiem",
            r is True and len(sw.strzalki) <= 6 and len(sw.kliki) >= 1 and sw.pietro == 0, (r, len(sw.strzalki), len(sw.kliki), sw.pietro))
else:
    print("pominięto: brak mapy klienta (1*)")

# --- 2. syntetyczny plac: schody i dekoracje obok prostej linii ---------------------------------------------------------

LINIA = [(x, 20) for x in range(5, 30)]                      # korytarz poziomy y=20
nowy()
sw = Swiat((5, 20), Plac(dekor={(x, 21) for x in range(8, 26, 2)}))
r, logi, st = marsz(sw, (28, 20, 7))
sprawdz("2a dekoracje (flaga 2 bez odpowiednika, kolor 129) tuż obok prostej linii nie wyłączają kliku: dojście klikami, <= 2 strzałki",
        r is True and tuple(sw.p[:2]) == (28, 20) and len(sw.strzalki) <= 2 and len(sw.kliki) >= 4, (r, sw.p, len(sw.strzalki), len(sw.kliki)))

nowy()
plac = OdpowiednikPietro(Plac(schody={(14, 21)}))
sw = Swiat((5, 20), plac)
r, logi, st = marsz(sw, (28, 20, 7))
blisko = [k for k in sw.kliki if k[2]]
sprawdz("2b PRAWDZIWE schody tuż obok linii (odpowiednik piętro obok, kolor 210): żaden klik nie ma ich w prostokącie z marginesem 1, marsz dochodzi",
        r is True and sw.pietro == 0 and not blisko and tuple(sw.p[:2]) == (28, 20), (r, sw.pietro, blisko, sw.p))
sprawdz("2c … a przy schodach idzie strzałkami, nie klikiem (strzałki w pobliżu x=14, 1-5 sztuk)",
        any(abs(a[2][0] - 14) <= 2 for a in sw.strzalki) and len(sw.strzalki) <= 8, [a[2] for a in sw.strzalki])

nowy()
sw = Swiat((5, 20), Plac(schody={(14, 21)}))                         # kolor 210 bez odpowiednika (dziura): też traktowane jako przejście
r, logi, st = marsz(sw, (28, 20, 7))
sprawdz("2d pole w kolorze 210 (dziura, bez odpowiednika) tuż obok linii: żaden klik go nie obejmuje, brak zmiany piętra",
        r is True and sw.pietro == 0 and not [k for k in sw.kliki if k[2]], (r, sw.pietro, [k for k in sw.kliki if k[2]]))

nowy()
sw = Swiat((5, 20), Plac(dekor={(x, 21) for x in range(8, 26, 2)}))
r, logi, st = marsz(sw, (28, 20, 7), akcje=Akcje(stwory=[(7, 22), (13, 22), (19, 22), (25, 22)]))
sprawdz("2e ktoś stoi 2 pola od linii: stara ostrożność (żaden klik z dekoracją w prostokącie z marginesem 1), dojście",
        r is True and tuple(sw.p[:2]) == (28, 20) and not [k for k in sw.kliki if k[3]], (r, [k for k in sw.kliki if k[3]], len(sw.strzalki)))

# --- 3. strzałka zaraz po kliku czeka na koniec ostatniego kroku -------------------------------------------------------

nowy()
sw = Swiat((5, 20), Plac())
r, logi, st = marsz(sw, (21, 20, 7))                                # 16 pól: kliki po 5 i końcówka strzałką tuż po kliku
sprawdz("3a po kliku strzałka czeka na koniec kroku: zero odrzuconych (log 12:03 miał 2x „bez skutku (po kroku: None)”)",
        r is True and tuple(sw.p[:2]) == (21, 20) and sw.odrzucone == 0 and not any("bez skutku" in l for l in logi),
        (r, sw.odrzucone, [l for l in logi if "bez skutku" in l]))

# --- 4. tempo strzałek: bez martwego czasu, z odrzuconym kluczem wraca do ostrożnego ------------------------------------

def tempo(env, K=0.45, slepe=(), cel=(40, 20, 7), mp=None):
    nowy()
    _os.environ["RETRONIC_MARSZ_PLYNNY"] = env
    try:
        sw = Swiat((5, 20), mp or Plac(sciany={(x, 19) for x in range(0, 60)} | {(x, 21) for x in range(0, 60)}), K=K, slepe=slepe)
        r, logi, st = marsz(sw, cel)
    finally:
        _os.environ.pop("RETRONIC_MARSZ_PLYNNY", None)
    odst = [b[0] - a[0] for a, b in zip(sw.strzalki, sw.strzalki[1:])]
    return r, sw, (sum(odst) / len(odst) if odst else 0.0), logi


# marsz tylko strzałkami: tempo mierzone na polach, gdzie klik jest niemożliwy (cel co 1 pole przy schodach po obu stronach)
SCHODY_OBOK = Plac(schody={(x, 21) for x in range(0, 60)} | {(x, 19) for x in range(0, 60)})
SCHODY_OBOK = OdpowiednikPietro(SCHODY_OBOK)
r0, sw0, sr0, l0 = tempo("0", mp=SCHODY_OBOK, cel=(30, 20, 7))
r1, sw1, sr1, l1 = tempo("1", mp=SCHODY_OBOK, cel=(30, 20, 7))
sprawdz("4f korytarz ze schodami po obu stronach: klik wykluczony, same strzałki (0 klików), dojście w obu trybach",
        r0 is True and r1 is True and len(sw0.kliki) == 0 and len(sw1.kliki) == 0 and sw1.pietro == 0, (r0, r1, len(sw0.kliki), len(sw1.kliki), sw1.pietro))
sprawdz("4g tempo strzałek: płynne szybsze od starego o >= 0,05 s/krok (stare %.3f, płynne %.3f)" % (sr0, sr1), sr0 - sr1 >= 0.05, (round(sr0, 3), round(sr1, 3)))
sprawdz("4h płynne strzałki nie schodzą poniżej czasu kroku (0,45 s) i nie są odrzucane", sr1 >= 0.45 and sw1.odrzucone == 0, (round(sr1, 3), sw1.odrzucone))

# klient odrzuca strzałki wysłane za wcześnie (krok 0,60 s dłuższy od szacunku): jedno odrzucenie, wyłączenie płynnego marszu, dojście
r2, sw2, sr2, l2 = tempo("1", K=0.60, mp=SCHODY_OBOK, cel=(30, 20, 7))
sprawdz("4i krok dłuższy od szacunku: marsz dochodzi, odrzuconych <= 2, płynny marsz sam się wyłącza (_RUCH[plynny_wyl])",
        r2 is True and sw2.odrzucone <= 2 and S._RUCH.get("plynny_wyl") is True, (r2, sw2.odrzucone, S._RUCH.get("plynny_wyl")))
sprawdz("4j wyłączenie jest w logu", any("płynn" in l for l in l2), l2[-3:])
nowy()
sw3 = Swiat((5, 20), OdpowiednikPietro(Plac(schody={(x, 21) for x in range(0, 60)} | {(x, 19) for x in range(0, 60)})), slepe={(12, 20)})
r3, l3, st3 = marsz(sw3, (30, 20, 7), maks_s=60.0)
sprawdz("4k pole, na które po prostu nie da się wejść, NIE wyłącza płynnego marszu (to nie odrzucony klawisz)", not S._RUCH.get("plynny_wyl"), S._RUCH.get("plynny_wyl"))

# --- 5. _po_kroku: pokrętło i skala ---------------------------------------------------------------------------------

nowy()
_os.environ["RETRONIC_MARSZ_PLYNNY"] = "0"
S._po_kroku(0.47)
stare = S._RUCH["koniec"] - ZEGAR.t
_os.environ.pop("RETRONIC_MARSZ_PLYNNY")
S._po_kroku(0.47)
nowe = S._RUCH["koniec"] - ZEGAR.t
sprawdz("5a RETRONIC_MARSZ_PLYNNY=0: koniec kroku jak dawniej (czas kroku - 0,06 s)", abs(stare - 0.41) < 1e-6, round(stare, 4))
sprawdz("5b płynny: koniec kroku wcześniejszy o PLYNNY_PRZED_S", abs((stare - nowe) - getattr(S, "PLYNNY_PRZED_S", -1)) < 1e-6 and 0.05 <= getattr(S, "PLYNNY_PRZED_S", 0) <= 0.15,
        (round(stare, 4), round(nowe, 4)))
S._RUCH["skala"] = 1.25
S._po_kroku(0.47)
sprawdz("5c po nieudanych krokach (skala > 1) bez wyprzedzenia: ostrożnie jak dawniej", abs((S._RUCH["koniec"] - ZEGAR.t) - 0.41) < 1e-6, round(S._RUCH["koniec"] - ZEGAR.t, 4))

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
