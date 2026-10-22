"""22.10 (dawajkesh, serwis Edron, krok depo): bag z runami wpadł do blue backpacka leżącego w depot chest (upuszczenie na slot
z kontenerem wkłada przedmiot do środka), a serwis zgłosił „mógł spaść na podłogę”. Offline, atrapy: okna z geometrią,
pamięć kontenerów, mysz rozstrzygająca upuszczenie po współrzędnych (kontener pod kursorem = przedmiot idzie do środka,
inaczej na początek kontenera jak w serwerze), zegar sztuczny.

Stary kod: RETRONIC_STARY_KOD=serwis_akcje.py.bak-20261022-depo-drag python3 -I testy/test_depo_przeciagnij.py (ma padać).
"""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import importlib.util
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
_stary = _os.environ.get("RETRONIC_STARY_KOD")
if _stary:
    from importlib.machinery import SourceFileLoader
    _spec = importlib.util.spec_from_file_location("serwis_akcje", str(KAT / _stary), loader=SourceFileLoader("serwis_akcje", str(KAT / _stary)))
    SA = importlib.util.module_from_spec(_spec)
    sys.modules["serwis_akcje"] = SA
    _spec.loader.exec_module(SA)
else:
    import serwis_akcje as SA
print("kod:", SA.__file__)

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


GOLD, PLAT, HAM, BAG, UH = 3031, 3035, 3582, 2869, 3160


# --- sztuczny zegar -------------------------------------------------------------------------------------------------
class Zegar:
    t = 1000.0


time.sleep = lambda s: setattr(Zegar, "t", Zegar.t + s)
time.monotonic = lambda: Zegar.t
SA.SKUTEK_CZEKAJ_S = 3.0       # stary kod nie zna tej stałej (zignoruje)


# --- świat: okna z geometrią + pamięć + mysz ------------------------------------------------------------------------
class Slot:
    def __init__(self, nr, idx, x, y):
        self.nr, self.idx = nr, idx
        self.srodek = (x + 16, y + 16)


class Okno:
    def __init__(self, nr, y0, ile):
        self.nr = nr
        self.sloty = [Slot(nr, i, 800 + 37 * (i % 4), y0 + 37 * (i // 4)) for i in range(ile)]
        self.gora, self.lewo, self.prawo = y0 - 20, 790, 950


class Swiat:
    """kontenery: nr -> {"nazwa", "poj", "p": [ {id, ilosc} | None... ]}; okna: nr -> Okno. nr 1 bag (góra), 2 plecak, 3 depot chest."""

    def __init__(self, plecak, depo, bag=None, ile_depo=16, przesuniecie_px=0, opoznienie_pamieci=0.0, stara_pamiec_depo=None, stara_zawsze=False):
        self.k = {2: {"nazwa": "backpack", "poj": 20, "p": [dict(x) for x in plecak]},
                  3: {"nazwa": "depot chest", "poj": 30, "p": [dict(x) for x in depo]}}
        okna = {2: Okno(2, 300, 20), 3: Okno(3, 600, ile_depo)}
        if bag is not None:
            self.k[1] = {"nazwa": "blue backpack", "poj": 20, "p": [dict(x) for x in bag]}
            okna[1] = Okno(1, 100, 20)
        self.okna = okna
        self.w_srodku = []                       # przedmioty, które wpadły do kontenera w depo / na podłogę
        self.przesuniecie_px = przesuniecie_px   # o ile pikseli kursor ląduje obok celu (symulacja błędu geometrii)
        self.opoznienie = opoznienie_pamieci
        self.stara_pamiec_depo = stara_pamiec_depo   # pierwszy odczyt pamięci depo jest nieświeży
        self.stara_zawsze = stara_zawsze             # ... albo wszystkie
        self.t_ruchu, self.przed_ruchem = None, None
        self.odczyty = 0

    def pamiec_prawdziwa(self):
        return [{"numer": n, "nazwa": k["nazwa"], "pojemnosc": k["poj"],
                 "przedmioty": [dict(slot=i, id=q["id"], ilosc=q["ilosc"]) for i, q in enumerate(k["p"])]}
                for n, k in sorted(self.k.items())]

    def pamiec(self):
        self.odczyty += 1
        if self.t_ruchu is not None and Zegar.t - self.t_ruchu < self.opoznienie:
            wynik = self.przed_ruchem
        else:
            wynik = self.pamiec_prawdziwa()
        if self.stara_pamiec_depo is not None and (self.odczyty == 1 or self.stara_zawsze):
            wynik = [dict(x, przedmioty=[dict(slot=i, **q) for i, q in enumerate(self.stara_pamiec_depo)])
                     if x["nazwa"] == "depot chest" else x for x in wynik]
        return wynik

    def slot_pod(self, x, y):
        for nr, o in self.okna.items():
            for s in o.sloty:
                if abs(s.srodek[0] - x) <= 16 and abs(s.srodek[1] - y) <= 16:
                    return nr, s.idx
        return None, None

    def przeciagnij(self, x1, y1, x2, y2, drganie=3):
        nz, iz = self.slot_pod(x1, y1)
        nd, idd = self.slot_pod(x2 + self.przesuniecie_px, y2)
        if nz is None or nd is None or iz >= len(self.k[nz]["p"]):
            return
        self.t_ruchu, self.przed_ruchem = Zegar.t, self.pamiec_prawdziwa()
        przedmiot = self.k[nz]["p"].pop(iz)
        cel = self.k[nd]["p"]
        if idd < len(cel) and cel[idd]["id"] in SA.ID_BAGOW:
            self.w_srodku.append(przedmiot)         # upuszczone na kontener: wpada do środka, licznik w oknie się nie zmienia
        else:
            cel.insert(0, przedmiot)                # serwer wstawia na początek kontenera


class Mysz:
    def __init__(self, swiat):
        self.s = swiat

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def przeciagnij(self, *a, **kw):
        self.s.przeciagnij(*a, **kw)


def akcje(swiat):
    a = object.__new__(SA.AkcjeZywe)
    a.log = lambda *x: None
    a.kontenery = swiat.pamiec
    a._mysz = lambda: Mysz(swiat)
    a._zrzut = lambda m: "OBRAZ"
    a._zamknij = lambda numer: None

    def okna_numery(obraz):
        pamiec = a.kontenery()
        return [(swiat.okna[k["numer"]], k) for k in pamiec]       # okna i kontenery sparowane poprawnie (numer = klucz okna)
    a._okna_numery = okna_numery
    a._slot_pusty = lambda obraz, slot: slot.idx >= len(swiat.k[slot.nr]["p"]) or swiat.k[slot.nr]["p"][slot.idx] is None
    return a


def prob(a, slot_baga=0):
    try:
        a._przenies_do_depo(a._mysz(), slot_baga)
        return None
    except SA.SerwisBlad as e:
        return e


def ile(swiat, nr, ident):
    return sum(q["ilosc"] for q in swiat.k[nr]["p"] if q["id"] == ident)


PLECAK = [{"id": BAG, "ilosc": 1}, {"id": PLAT, "ilosc": 9}, {"id": GOLD, "ilosc": 4}]
BAG_RUN = [{"id": UH, "ilosc": 1}] * 20
DEPO_Z_BAGIEM = [{"id": BAG, "ilosc": 1}, {"id": PLAT, "ilosc": 36}]          # sytuacja z 22.10: blue backpack w slocie 0, platinum w 1

# 1. kontrola: pamięć spójna z ekranem, depo z bagiem w slocie 0 -> bag ląduje na wolnym slocie, nie w środku bagu
s = Swiat(PLECAK, DEPO_Z_BAGIEM, bag=BAG_RUN)
e = prob(akcje(s))
sprawdz("1 depo z bagiem w slocie 0 (pamięć = ekran): bag przeniesiony do skrzyni, nic nie wpadło do środka",
        e is None and ile(s, 3, BAG) == 2 and ile(s, 2, BAG) == 0 and not s.w_srodku, (e, s.k[3]["p"], s.w_srodku))

# 2. pamięć nie nadąża za ekranem (depo w pamięci puste, na ekranie bag@0 + platinum@1): stary kod mierzy w slot 0 = bag
s = Swiat(PLECAK, DEPO_Z_BAGIEM, bag=BAG_RUN, stara_pamiec_depo=[])
e = prob(akcje(s))
sprawdz("2 pamięć depo nieświeża (pusta), na ekranie bag w slocie 0: upuszczenie NIE na slot z kontenerem",
        e is None and not s.w_srodku and ile(s, 3, BAG) == 2, (e, s.w_srodku, s.k[3]["p"]))

# 2b. rozjazd pamięć/ekran trwa: błąd BEZ przeciągania (nic nie wpada do środka, bag zostaje w plecaku)
s = Swiat(PLECAK, DEPO_Z_BAGIEM, bag=BAG_RUN, stara_pamiec_depo=[], stara_zawsze=True)
e = prob(akcje(s))
sprawdz("2b trwały rozjazd pamięć/ekran: SerwisBlad „rozjeżdżają”, bag nietknięty w plecaku", e is not None and "rozjeżdżają" in str(e)
        and ile(s, 2, BAG) == 1 and not s.w_srodku, (e, s.k[2]["p"]))

# 3. pamięć mówi „slot 0 wolny”, ekran „zajęty” -> slot podejrzany; wybór nie sąsiaduje z bagiem
a = akcje(Swiat(PLECAK, DEPO_Z_BAGIEM))
sw = Swiat(PLECAK, DEPO_Z_BAGIEM)
try:
    wybor = SA.bezpieczny_wolny_slot(sw.okna[3], {"przedmioty": [{"slot": 0, "id": BAG}, {"slot": 1, "id": PLAT}]},
                                     lambda sl: a._slot_pusty(None, sl))
except AttributeError as ex:
    wybor = f"brak funkcji ({ex})"
sprawdz("3a bezpieczny_wolny_slot: bag@0, platinum@1 -> slot 2 (nie sąsiaduje z bagiem)", wybor == 2, wybor)
sw2 = Swiat(PLECAK, [{"id": GOLD, "ilosc": 1}, {"id": BAG, "ilosc": 1}])
try:
    wybor = SA.bezpieczny_wolny_slot(sw2.okna[3], {"przedmioty": [{"slot": 0, "id": GOLD}, {"slot": 1, "id": BAG}]})
except AttributeError as ex:
    wybor = f"brak funkcji ({ex})"
sprawdz("3b bezpieczny_wolny_slot: bag@1 -> pomija sąsiadów bagu (2, 4, 5, 6), bierze slot 3", wybor == 3, wybor)
try:
    wybor = SA.bezpieczny_wolny_slot(sw.okna[3], {"przedmioty": []}, lambda sl: sl.idx not in (0, 1))
except AttributeError as ex:
    wybor = f"brak funkcji ({ex})"
sprawdz("3c bezpieczny_wolny_slot: pamięć pusta, ekran zajęty na 0 i 1 -> slot 3 (2 sąsiaduje z zajętym 1)", wybor == 3, wybor)
pelne = Swiat(PLECAK, [{"id": GOLD, "ilosc": 1}] * 16)
try:
    wybor = SA.bezpieczny_wolny_slot(pelne.okna[3], {"przedmioty": [{"slot": i, "id": GOLD} for i in range(16)]})
except AttributeError as ex:
    wybor = f"brak funkcji ({ex})"
sprawdz("3d bezpieczny_wolny_slot: skrzynia pełna -> None", wybor is None, wybor)

# 4. pamięć klienta odpowiada z opóźnieniem 1,5 s (jeden odczyt po 0,9 s tego nie widzi): sukces, nie fałszywy błąd
s = Swiat(PLECAK, DEPO_Z_BAGIEM, bag=BAG_RUN, opoznienie_pamieci=1.5)
e = prob(akcje(s))
sprawdz("4 pamięć spóźniona o 1,5 s: weryfikacja czeka na skutek i uznaje sukces", e is None and ile(s, 3, BAG) == 2, e)

# 5. kursor ląduje dwa sloty obok celu (błąd geometrii okna) i bag wpada do blue backpacka: komunikat precyzyjny, nie „podłoga”
s = Swiat(PLECAK, DEPO_Z_BAGIEM, bag=BAG_RUN, przesuniecie_px=-74)
e = prob(akcje(s))
tekst = str(getattr(e, "powod", e))
sprawdz("5a przeciągnięcie wpadło do kontenera w depo: błąd (nie ciche „ok”)", e is not None and len(s.w_srodku) == 1, (e, s.w_srodku))
sprawdz("5b komunikat: bez „spaść na podłogę”, z informacją o zniknięciu z plecaka i kontenerze w depo",
        e is not None and "mógł spaść na podłogę" not in tekst and "zniknął z plecaka" in tekst and "kontenera" in tekst
        and "na obu końcach" in tekst, tekst)

# 6. nic się nie ruszyło (źródło poza oknem): komunikat „nie ruszył się”
s = Swiat(PLECAK, DEPO_Z_BAGIEM, bag=BAG_RUN, przesuniecie_px=0)
s.przeciagnij = lambda *a, **kw: None
e = prob(akcje(s))
tekst = str(getattr(e, "powod", e))
sprawdz("6 przeciągnięcie bez skutku: błąd „nie ruszył się z plecaka”, bez „podłogi”", e is not None and "nie ruszył się" in tekst
        and "podłog" not in tekst.split(":", 1)[-1].split(";")[0], tekst)

# 7. platinum nie wpada do baga w depo: po złożeniu baga skrzynka ma bag@0 (przesunięty), platinum idzie na wolny slot lub stos
s = Swiat([{"id": PLAT, "ilosc": 100}, {"id": PLAT, "ilosc": 10}], [{"id": BAG, "ilosc": 1}, {"id": GOLD, "ilosc": 5}])
a = akcje(s)
s_pt = s


def okno_ilosci_atrapa(m, zostaw, razem):
    return True


a._okno_ilosci = okno_ilosci_atrapa
# platinum stos 100 (źródło slot 0) bez okna ilości: przenosi cały stos (ile > 1 wymaga okna ilości, atrapa zatwierdza)
try:
    a._platinum_do_depo(a._mysz(), 10)
    blad = None
except SA.SerwisBlad as ex:
    blad = ex
sprawdz("7 platinum do depo z bagiem w slocie 0: nic nie wpadło do bagu", not s.w_srodku, (blad, s.w_srodku))

# 8. okno depot chest na dole panelu: piąty rząd (sloty 16-19) ucięty dołem zrzutu (13:13 invincible: fałszywy rozjazd)
from PIL import Image
import loot as _loot_mod


def okno_uciete(zajete_na_ekranie):
    obraz = Image.new("RGB", (1000, 890), (30, 30, 30))         # tło pustego slotu: szarość 30
    sloty = [_loot_mod.Slot(800 + 37 * (i % 4), 720 + 37 * (i // 4), 34) for i in range(20)]   # rząd 5 (y=868..901) wystaje poza 890
    for i in zajete_na_ekranie:
        sl = sloty[i]
        for x in range(sl.x + 2, sl.x + 32):
            for y in range(sl.y + 2, min(sl.y + 32, 890)):
                obraz.putpixel((x, y), (200, 120, 40) if (x + y) % 2 else (10, 10, 10))
    o = type("Okno", (), {})()
    o.sloty = sloty
    return obraz, o


a = object.__new__(SA.AkcjeZywe)
a.log = lambda *x: None
obraz, o = okno_uciete([])
try:
    rozjazd = a._sloty_rozjechane(obraz, o, {"przedmioty": []})
except Exception as ex:
    rozjazd = f"wyjątek {ex!r}"
sprawdz("8a depot chest pusty, piąty rząd ucięty dołem zrzutu: brak rozjazdu (sloty 16-19 pomijane)", rozjazd == [], rozjazd)
obraz, o = okno_uciete(range(16))
mem = {"przedmioty": [{"slot": i, "id": GOLD, "ilosc": 1} for i in range(16)]}
try:
    rozjazd = a._sloty_rozjechane(obraz, o, mem)
    wolny = a._wolny_w_depo(obraz, o, mem)
except Exception as ex:
    rozjazd, wolny = f"wyjątek {ex!r}", "?"
sprawdz("8b 16 widocznych slotów zajętych zgodnie z pamięcią: brak rozjazdu i brak celu w uciętym rzędzie (None)",
        rozjazd == [] and wolny is None, (rozjazd, wolny))
obraz, o = okno_uciete([0, 1])
mem2 = {"przedmioty": [{"slot": 0, "id": BAG, "ilosc": 1}]}                # pamięć nie widzi slotu 1 (zajęty na ekranie)
try:
    rozjazd = a._sloty_rozjechane(obraz, o, mem2)
except Exception as ex:
    rozjazd = f"wyjątek {ex!r}"
sprawdz("8c prawdziwy rozjazd w widocznym slocie nadal wykrywany (slot 1)", rozjazd == [1], rozjazd)
try:
    wolny = a._wolny_w_depo(okno_uciete([0])[0], okno_uciete([0])[1], {"przedmioty": [{"slot": 0, "id": BAG, "ilosc": 1}]})
except Exception as ex:
    wolny = f"wyjątek {ex!r}"
sprawdz("8d cel upuszczenia w oknie uciętym: widoczny, pusty, niesąsiadujący z bagiem (slot 2)", wolny == 2, wolny)

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
