"""Marsz serwisu po kafelkach (serwis.idz_pewnie, serwis.marsz) na atrapie świata z zegarem wirtualnym.

Regresja z 19.10 (Mastafian, Edron, krok `backpack`): postać przez ok. 2 minuty krążyła w 4 polach zamiast iść do celu.
Przyczyna (najlepsze wyjaśnienie, dowód z kodu i symulacji; pomiar na żywo czeka): Postac.krok wraca zaraz po zmianie pozycji,
czyli w trakcie trwającego kroku (ok. 0,5 s), a idz_pewnie wysyłał następną strzałkę natychmiast; klawisz w trakcie kroku bywa
odrzucany, więc co drugi krok zawodził, pole szło na 5 s do zablokowanych, plan szedł bokiem, blokada wygasała i tak w kółko.
Stary kod nic nie logował i nie miał bezpiecznika (150 s krążenia). Tu: świat z odrzucaniem klawiszy w trakcie kroku, z polem,
na które nie da się wejść, z cofnięciem pozycji po kroku i z postacią, która w ogóle nie rusza. Bez gry, bez gniazd."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import random
import sys
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import serwis as S
from serwis_blad import SerwisBlad

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


class Zegar:
    """Czas wirtualny: sleep tylko przesuwa wskazówkę, więc testy marszu na 150 s trwają ułamek sekundy."""
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


class MapaOtwarta:
    """Plac 40 x 30 pól, wszystkie chodliwe, prędkość pola 10 (krok ok. 0,47 s)."""
    def flagi(self, x, y, z):
        return 1 if 0 <= x < 40 and 0 <= y < 30 else 0

    def pole(self, x, y, z):
        return (self.flagi(x, y, z), 0, 10) if self.flagi(x, y, z) else None


class Akcje:
    nick = "Ja"

    def __init__(self, zajete=()):
        self.zajete = list(zajete)

    def _stwory(self):
        return [{"x": x, "y": y, "z": 7, "nazwa": "Inny"} for x, y in self.zajete]


KIER = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}


class Swiat:
    """Atrapa Postac: krok jak bot.Postac.krok (wraca po zmianie pozycji albo po 1,5 s z None).
    tryb "kolejka": klawisz w trakcie kroku czeka na jego koniec; "odrzuca": klawisz w trakcie kroku przepada.
    slepe: pola, na które nie da się wejść mimo wolnej mapy. cofa: po kroku pozycja wraca na stare pole (krok zgłoszony
    jako udany). skrypt: lista 0/1 dla kolejnych wywołań krok (0 = bez skutku), potem świat działa normalnie."""
    K = 0.55

    def __init__(self, poz, tryb="kolejka", slepe=(), cofa=False, skrypt=None, nie_rusza=False, z=7):
        self.p = [poz[0], poz[1], z]
        self.tryb, self.slepe, self.cofa, self.skrypt, self.nie_rusza = tryb, set(slepe), cofa, list(skrypt or []), nie_rusza
        self.koniec = 0.0
        self.wywolania = []             # (czas, klawisz, pozycja przed, czy w trakcie kroku)
        self.trasa = [tuple(self.p[:2])]

    def pozycja(self):
        ZEGAR.t += 0.004
        return tuple(self.p)

    def krok(self, klawisz):
        d = KIER[klawisz]
        start = tuple(self.p[:2])
        cel = (start[0] + d[0], start[1] + d[1])
        w_trakcie = ZEGAR.t < self.koniec
        self.wywolania.append((round(ZEGAR.t - 1000.0, 3), klawisz, start, w_trakcie))
        ZEGAR.t += 0.01
        if self.skrypt:
            if not self.skrypt.pop(0):
                ZEGAR.t += 1.5
                return None
        if self.nie_rusza or cel in self.slepe:
            ZEGAR.t += 1.5
            return None
        if ZEGAR.t < self.koniec:
            if self.tryb == "odrzuca":
                ZEGAR.t += 1.5
                return None
            ZEGAR.t = self.koniec
        self.p[0], self.p[1] = cel
        self.koniec = ZEGAR.t + self.K
        ZEGAR.t += random.uniform(0.07, 0.17)           # wykrycie zmiany (poll 0,05 s) + losowa pauza po kroku
        nowa = (cel[0], cel[1], self.p[2])
        if self.cofa:
            self.p[0], self.p[1] = start
        else:
            self.trasa.append(cel)
        return nowa


def nowy_marsz():
    ZEGAR.t = 1000.0
    getattr(S, "_RUCH", {}).update(koniec=0.0, skala=1.0)
    random.seed(7)


def idz(swiat, cel, tol=0, mp=None, akcje=None, maks_s=150.0, **kw):
    logi = []
    stan = {}
    cel = tuple(cel) if len(cel) == 3 else tuple(cel) + (swiat.p[2],)
    try:
        r = S.idz_pewnie(swiat, mp or MapaOtwarta(), akcje or Akcje(), cel, tol, maks_s=maks_s, log=logi.append, stan=stan, **kw)
    except TypeError:                                   # stary kod nie zna `stan`
        r = S.idz_pewnie(swiat, mp or MapaOtwarta(), akcje or Akcje(), cel, tol, maks_s=maks_s, log=logi.append, **kw)
    return r, logi, stan


def zmiany_kierunku(trasa):
    k = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(trasa, trasa[1:])]
    return sum(1 for a, b in zip(k, k[1:]) if a != b), sum(1 for a, b in zip(k, k[1:]) if (a[0], a[1]) == (-b[0], -b[1]))


# --- 1. zwykły marsz: prosta linia, bez zawrotów, bez zbędnych pauz -------------------------------------

nowy_marsz()
sw = Swiat((5, 5))
r, logi, st = idz(sw, (20, 12))
sprawdz("1a marsz bez przeszkód dochodzi do celu", r is True and tuple(sw.p[:2]) == (20, 12), (r, sw.p))
sprawdz("1b liczba kroków = odległość Manhattan (bez cofania i zbędnych kroków)", len(sw.trasa) - 1 == 15 + 7, len(sw.trasa) - 1)
zm, zaw = zmiany_kierunku(sw.trasa)
sprawdz("1c jedna kierunkowa ścieżka: najwyżej 2 zmiany kierunku (zygzak schodkowy odpada), zero zawrotów", zm <= 2 and zaw == 0, (zm, zaw))
sprawdz("1d marsz bez przeszkód nic nie loguje o nieudanych krokach", not any("bez skutku" in l for l in logi), logi)

# --- 2. tempo: klawisz nie idzie w trakcie trwającego kroku ----------------------------------------------

nowy_marsz()
sw = Swiat((5, 5), tryb="odrzuca")
r, logi, st = idz(sw, (20, 12))
w_trakcie = [w for w in sw.wywolania if w[3]]
sprawdz("2a świat odrzuca klawisze w trakcie kroku: marsz mimo to dochodzi do celu (stary kod krążył)", r is True, (r, tuple(sw.p[:2])))
sprawdz("2b strzałki idą po końcu kroku: co najwyżej jedna w trakcie kroku (skala czasu kroku się dostroiła)",
        len(w_trakcie) <= 1, w_trakcie)
odstepy = [b[0] - a[0] for a, b in zip(sw.wywolania, sw.wywolania[1:])]
sprawdz("2c odstępy między strzałkami >= ok. czasu kroku (marsz ciągły, ale nie szybszy od postaci)",
        min(odstepy) >= 0.40, round(min(odstepy), 3))
sprawdz("2d marsz ciągły: średni odstęp < 0,8 s (bez zbędnych pauz)", sum(odstepy) / len(odstepy) < 0.8,
        round(sum(odstepy) / len(odstepy), 3))
nowy_marsz()
sw = Swiat((5, 5), tryb="odrzuca")
getattr(S, "_RUCH", {})["koniec"] = ZEGAR.t + 0.5                      # poprzedni odcinek zostawił krok w toku
idz(sw, (8, 5))
sprawdz("2e kolejny odcinek zaczeka na koniec kroku z poprzedniego (stan wspólny między wywołaniami)",
        sw.wywolania and sw.wywolania[0][0] >= 0.5, sw.wywolania[:1])

# --- 3. nieudany krok jest logowany, pole na które nie da się wejść jest omijane -------------------------

nowy_marsz()
sw = Swiat((5, 5), slepe={(6, 5)})
r, logi, st = idz(sw, (12, 5))
zle = [l for l in logi if "bez skutku" in l]
sprawdz("3a pole, na które nie da się wejść, jest obejście i marsz dochodzi", r is True and tuple(sw.p[:2]) == (12, 5), (r, sw.p))
sprawdz("3b każdy nieudany krok ma wiersz w logu", len(zle) == 2, logi)
sprawdz("3c wiersz zawiera klawisz, pozycję przed, pole docelowe, licznik z rzędu i na polu",
        zle and "Right" in zle[0] and "(5, 5)" in zle[0] and "(6, 5)" in zle[0] and "1/" in zle[0] and "1x" in zle[0], zle[:1])
sprawdz("3d pierwszy zawód = ponowienie, drugi = blokada pola", len(zle) > 1 and "ponowię" in zle[0] and "blokuję" in zle[1], zle)
sprawdz("3e na polu, które zawiodło dwa razy, nie ma więcej prób (3 razy Right z (5,5) nie ma)",
        sum(1 for w in sw.wywolania if w[2] == (5, 5) and w[1] == "Right") == 2, sw.wywolania)
sprawdz("3f po udanym kroku licznik z rzędu wraca do zera (kolejny zawód ma 1/)",
        all("1/" in l for l in zle[::2]), zle)

# --- 4. bezpiecznik: nieudane kroki z rzędu przerywają marsz ---------------------------------------------

nowy_marsz()
sw = Swiat((5, 5), nie_rusza=True)
r, logi, st = idz(sw, (20, 12))
sprawdz("4a postać, która nie rusza: marsz kończy się False", r is False, r)
sprawdz("4b dokładnie MAKS_ZLYCH_Z_RZEDU prób, a nie krążenie do końca limitu czasu",
        len(sw.wywolania) == getattr(S, "MAKS_ZLYCH_Z_RZEDU", -1) == 6, (len(sw.wywolania), getattr(S, "MAKS_ZLYCH_Z_RZEDU", None)))
sprawdz("4c przerwanie jest w logu i w stan[utkniecie]", any("przerywam marsz" in l for l in logi) and st.get("utkniecie"), (logi[-2:], st))
sprawdz("4d marsz przerwany bezpiecznikiem trwa krótko (< 30 s wirtualnych, nie 150)", ZEGAR.t - 1000.0 < 30.0, round(ZEGAR.t - 1000.0, 1))

# --- 5. licznik zerowany po udanym kroku -----------------------------------------------------------------

nowy_marsz()
sw = Swiat((5, 5), skrypt=[0] * 5 + [1] + [0] * 5)
r, logi, st = idz(sw, (12, 5))
sprawdz("5a pięć nieudanych, udany, pięć nieudanych (nigdy 6 z rzędu): marsz nie jest przerwany i dochodzi",
        r is True and not st.get("utkniecie"), (r, st, logi[-3:]))
nowy_marsz()
sw = Swiat((5, 5), skrypt=[0] * 6)
r, logi, st = idz(sw, (12, 5))
sprawdz("5b sześć nieudanych z rzędu przerywa nawet gdy potem świat działa", r is False and st.get("utkniecie"), (r, st))

# --- 6. brak pętli A-B-A-B -------------------------------------------------------------------------------

nowy_marsz()
sw = Swiat((5, 5), cofa=True)                           # serwer cofa pozycję po udanym kroku: krok w kółko na to samo pole
r, logi, st = idz(sw, (12, 5))
sprawdz("6a krążenie na tych samych polach przerywa marsz zamiast kręcić się 150 s",
        r is False and st.get("utkniecie") and len(sw.wywolania) <= 12, (r, st, len(sw.wywolania)))
sprawdz("6b krążenie jest nazwane w logu", any("krążę" in l for l in logi), logi[-2:])

nowy_marsz()
sw = Swiat((5, 5), tryb="odrzuca", slepe={(6, 5), (5, 6)})
r, logi, st = idz(sw, (12, 5))
pola = sw.trasa
najwiecej = max(pola.count(p) for p in set(pola))
sprawdz("6c marsz z odrzucanymi klawiszami i dwoma ślepymi polami: żadne pole odwiedzone więcej niż 2 razy, cel osiągnięty",
        r is True and najwiecej <= 2, (r, najwiecej, pola[:20]))

# --- 7. marsz(): porażka zamiast chodzika, gdy postać utknęła -------------------------------------------

nowy_marsz()
zap = []
sw = Swiat((5, 5), nie_rusza=True)
try:
    S.marsz(sw, MapaOtwarta(), Akcje(), [], [(5, 5, 7), (20, 12, 7)], 0, log=lambda *_: None, zapasowy=lambda p, t: zap.append(p) or True)
    blad = None
except SerwisBlad as e:
    blad = e
except Exception as e:                                  # stary kod: brak S.marsz
    blad = e
sprawdz("7a utknięcie = SerwisBlad (porażka + STOP serwisu), zapasowy chodzik nie rusza", isinstance(blad, SerwisBlad) and not zap, (blad, zap))

nowy_marsz()
zap = []
sw = Swiat((5, 5), z=6)                                 # inne piętro niż cel: brak planu, zostaje chodzik zapasowy
try:
    r = S.marsz(sw, MapaOtwarta(), Akcje(), [], [(5, 5, 6), (20, 12, 7)], 0, log=lambda *_: None, zapasowy=lambda p, t: zap.append(p) or True)
except Exception as e:
    r = e
sprawdz("7b brak planu (inne piętro) nadal oddaje marsz zapasowemu chodzikowi", r is True and len(zap) == 1, (r, zap))

nowy_marsz()
sw = Swiat((5, 5))
try:
    r = S.marsz(sw, MapaOtwarta(), Akcje(), [], [(5, 5, 7), (9, 5, 7)], 0, log=lambda *_: None, zapasowy=lambda p, t: False)
except Exception as e:
    r = e
sprawdz("7c udany marsz zwraca True", r is True and tuple(sw.p[:2]) == (9, 5), (r, sw.p))

# --- 8. ludzie na drodze: omijani, bez błędów ------------------------------------------------------------

nowy_marsz()
sw = Swiat((5, 5))
r, logi, st = idz(sw, (12, 5), akcje=Akcje(zajete=[(8, 5), (8, 4), (8, 6)]))
sprawdz("8a gracze na drodze: obejście i dojście, bez nieudanych kroków",
        r is True and not any("bez skutku" in l for l in logi) and not any(p in {(8, 5), (8, 4), (8, 6)} for p in sw.trasa), (r, sw.trasa))

# --- 9. prawdziwa mapa Edronu: krok backpack z 19.10 ---------------------------------------------------

import mapa as _mapa
if _mapa.PLIK_MAPY.is_file():
    mp = _mapa.mapa()
    dane = json.load(open(KAT / "trasy" / "serwis_edron.json"))
    unik = [tuple(p) for l in dane["laczniki"] for p in (l["z"], l["do"])]
    cel = (33173, 31817, 6)
    nowy_marsz()
    sw = Swiat((33173, 31803), tryb="odrzuca", z=6)
    r, logi, st = idz(sw, cel, 3, mp=mp, unik=unik)
    zm, zaw = zmiany_kierunku(sw.trasa)
    sprawdz("9a Edron, z (33173,31803) do schodów z6 przy odrzucaniu klawiszy w trakcie kroku: dojście w < 30 s i bez krążenia",
            r is True and ZEGAR.t - 1000.0 < 30.0 and zaw == 0, (r, round(ZEGAR.t - 1000.0, 1), sw.trasa[-6:]))
    sprawdz("9b Edron: trasa nie wraca na pola już odwiedzone",
            len(set(sw.trasa)) == len(sw.trasa), [p for p in sw.trasa if sw.trasa.count(p) > 1])
    nowy_marsz()
    sw = Swiat((33173, 31803), tryb="odrzuca", z=6, slepe={(33173, 31806), (33174, 31805)})
    r, logi, st = idz(sw, cel, 3, mp=mp, unik=unik)
    sprawdz("9c Edron: dwa pola w wyjściu z sali nie przepuszczają: obejście albo przerwanie z powodem, nigdy 150 s krążenia",
            (r is True or st.get("utkniecie")) and ZEGAR.t - 1000.0 < 60.0, (r, st, round(ZEGAR.t - 1000.0, 1)))
else:
    print("pominięto: brak pliku mapy (9*)")

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
