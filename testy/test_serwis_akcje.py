"""Akcje serwisu (serwis_akcje.AkcjeZywe) na symulacji plecaka/depo/NPC i na zrzutach panelu z 19.10:
arytmetyka platinum przy składaniu w depo, weryfikacja na obu końcach przeciągnięcia, zakupy z górną granicą ilości i ceny,
wymiana gold, blanki do baga, kontrola startu (bot, HP, potwory), układ okien. Bez gry: myszka, zrzut, pamięć kontenerów
i rozmowa są podmienione symulacją. Każda uwaga z przeglądu (19.10, checker) ma tu osobny test."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
import types
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import serwis_akcje as A
from serwis_blad import SerwisBlad
from PIL import Image

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


def zglasza(f):
    try:
        f()
    except SerwisBlad as e:
        return e
    return None


GOLD, PLAT, BLANK, HAM, BAG, UH = 3031, 3035, 3147, 3582, 2869, 3160
A.SKUTEK_CZEKAJ_S = 0           # 22.10: bez czekania na skutek przeciągnięcia (atrapa pamięci zmienia się natychmiast)


class Slot:
    def __init__(self, i):
        self.srodek = (100 + 37 * (i % 4), 100 + 37 * (i // 4))


class Okno:
    def __init__(self, widoczne, gora):
        self.sloty = [Slot(i) for i in range(widoczne)]
        self.gora, self.lewo, self.prawo = gora, 760, 936


class Symulacja:
    """Pamięć kontenerów: {numer: {"nazwa", "poj", "widoczne", "p": [ {id, ilosc} ]}}; numer rosnący = okno od góry w dół.
    `spada`: przeciągnięcie nie trafia w cel (przedmiot ląduje na podłodze); `ceny`: ile gp zabiera NPC przy zakupie."""

    def __init__(self, glowny, depo=None, bag=None, widoczne_depo=16, nazwa_bagu="blue backpack"):
        self.kon, n = {}, 0
        if bag is not None:
            self.kon[n] = {"nazwa": nazwa_bagu, "poj": 20, "widoczne": 20, "p": [dict(x) for x in bag]}
            n += 1
        self.kon[n] = {"nazwa": "backpack", "poj": 20, "widoczne": 20, "p": [dict(x) for x in glowny]}
        n += 1
        if depo is not None:
            self.kon[n] = {"nazwa": "depot chest", "poj": 30, "widoczne": widoczne_depo, "p": [dict(x) for x in depo]}
        self.oczekuje = None
        self.spada = False
        self.zamkniete = {}                     # numer -> kontener zamknięty przez akcje (do oglądania w asercjach)

    def pamiec(self):
        return [{"numer": n, "nazwa": k["nazwa"], "pojemnosc": k["poj"],
                 "przedmioty": [dict(slot=i, id=q["id"], ilosc=q["ilosc"]) for i, q in enumerate(k["p"])]}
                for n, k in sorted(self.kon.items())]

    def ile(self, ids):
        return sum(q["ilosc"] for k in self.kon.values() if k["nazwa"] not in ("locker", "depot chest")
                   for q in k["p"] if q["id"] in ids)

    def glowny(self):
        return next(k for k in self.kon.values() if k["nazwa"] in ("backpack", "bag"))

    def depo(self):
        return next(k for k in list(self.kon.values()) + list(self.zamkniete.values()) if k["nazwa"] == "depot chest")


class MyszAtrapa:
    def __init__(self):
        self.akcje = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def klik(self, x, y, przycisk=1, modyfikator=None, drganie=3):
        self.akcje.append(("klik", x, y, modyfikator))

    def przeciagnij(self, x1, y1, x2, y2, drganie=3):
        self.akcje.append(("przeciagnij", x1, y1, x2, y2))


class Testowe(A.AkcjeZywe):
    """AkcjeZywe bez gry: wszystko, co dotyka ekranu i pamięci klienta, idzie przez symulację."""

    def __init__(self, sym, rozmowa=None, gracz=None, stwory=None, poz=(33170, 31813, 7)):
        self.sym, self.log, self.nick = sym, (lambda *_: None), "Mastafian"
        self.rozmowa = rozmowa
        self.sprawdz_bota = False
        self.postac = types.SimpleNamespace(pozycja=lambda: poz)
        self._gracz_dane = gracz or {"hp": 240, "max_hp": 240}
        self._stwory_dane = stwory if stwory is not None else []
        self._bot = types.SimpleNamespace(Zatrzymano=RuntimeError, _zapytaj_surowe=self._zapytaj)
        self.zamkniete, self.depo_otwarte, self.mysz = [], True, MyszAtrapa()

    def _zapytaj(self, z):
        if self._stwory_dane == "BLAD":
            raise OSError("brak gniazda")
        if z["cmd"] == "kontenery":
            ekw = getattr(self.sym, "ekw", None)
            return {"ekwipunek": None if ekw is None else {str(k): v for k, v in ekw.items()}}
        return {"gracz": self._gracz_dane} if z["cmd"] == "gracz" else {"stwory": self._stwory_dane}

    def kontenery(self):
        return self.sym.pamiec()

    def ilosc(self, ids, bez=("locker", "depot chest")):
        return self.sym.ile(ids)

    def _mysz(self):
        return self.mysz

    def _zrzut(self, mysz):
        return None

    def _zamknij(self, numer):
        self.zamkniete.append(numer)
        k = self.sym.kon.pop(numer, None)
        if k is not None:
            self.sym.zamkniete[numer] = k

    def _otworz_depo(self, m):
        return self.depo_otwarte

    def _okna_numery(self, obraz):
        return [(Okno(k["widoczne"], 100 * i), kon) for i, ((n, k), kon) in enumerate(zip(sorted(self.sym.kon.items()), self.kontenery()))]

    def _przeciagnij(self, m, okno_z, i_z, okno_do, i_do):
        numery = sorted(self.sym.kon)
        kz = self.sym.kon[numery[okno_z.gora // 100]]
        kd = self.sym.kon[numery[okno_do.gora // 100]]
        przedmiot = kz["p"][i_z]
        if przedmiot["ilosc"] > 1:
            self.sym.oczekuje = (kz, kd, i_z, i_do)              # okno ilości zdecyduje, ile przejdzie
            return
        kz["p"].pop(i_z)
        if self.sym.spada:
            return
        kd["p"].insert(min(i_do, len(kd["p"])), przedmiot)

    def _okno_ilosci(self, m, zostaw_w_zrodle, razem):
        kz, kd, i_z, i_do = self.sym.oczekuje
        self.sym.oczekuje = None
        przedmiot = kz["p"][i_z]
        ile = przedmiot["ilosc"] - zostaw_w_zrodle
        if ile <= 0:
            return True
        przedmiot["ilosc"] -= ile
        if przedmiot["ilosc"] == 0:
            kz["p"].pop(i_z)
        if self.sym.spada:
            return True
        cel = kd["p"][i_do] if i_do < len(kd["p"]) else None
        if cel is not None and cel["id"] == przedmiot["id"]:
            cel["ilosc"] += ile                                    # scalenie ze stosem w skrzynce
        else:
            kd["p"].append({"id": przedmiot["id"], "ilosc": ile})
        return True


# --- depo: bag + platinum ponad 3 --------------------------------------------------------------------------------

G = [{"id": BAG, "ilosc": 1}, {"id": PLAT, "ilosc": 13}, {"id": GOLD, "ilosc": 8}, {"id": 3198, "ilosc": 1}]
sym = Symulacja(G, depo=[{"id": GOLD, "ilosc": 83}, {"id": PLAT, "ilosc": 36}])
a = Testowe(sym)
wynik = a.depo_zloz(3)
sprawdz("1a depo: bag odłożony, 13 platinum -> w plecaku 3", wynik is True and sym.ile({PLAT}) == 3
        and not any(q["id"] == BAG for q in sym.glowny()["p"]), (sym.glowny()["p"], sym.depo()))
sprawdz("1b depo: 10 platinum zeszło na istniejący stos (36 -> 46), bez nowego stosu; bag w skrzynce",
        [q["ilosc"] for q in sym.depo()["p"] if q["id"] == PLAT] == [46] and any(q["id"] == BAG for q in sym.depo()["p"]), sym.depo()["p"])
sprawdz("1c depo: depot chest zamknięty po składaniu, w pamięci tylko plecak", 1 in a.zamkniete and len(sym.kon) == 1, (a.zamkniete, sym.kon.keys()))
sprawdz("1d depo: gold nietknięty", sym.ile({GOLD}) == 8)

sym = Symulacja([{"id": BAG, "ilosc": 1}, {"id": PLAT, "ilosc": 100}, {"id": PLAT, "ilosc": 100}, {"id": PLAT, "ilosc": 50}], depo=[])
Testowe(sym).depo_zloz(3)
sprawdz("1e depo: trzy stosy platinum (250) -> w plecaku 3", sym.ile({PLAT}) == 3, sym.glowny()["p"])

sym = Symulacja([{"id": BAG, "ilosc": 1}, {"id": PLAT, "ilosc": 2}], depo=[])
Testowe(sym).depo_zloz(3)
sprawdz("1f depo: platinum 2 (mniej niż 3) zostaje w plecaku, bag odłożony", sym.ile({PLAT}) == 2 and not any(q["id"] == BAG for q in sym.glowny()["p"]))

sym = Symulacja([{"id": PLAT, "ilosc": 3}], depo=[])
Testowe(sym).depo_zloz(3)
sprawdz("1g depo: dokładnie 3 platinum, brak baga: nic nie rusza", sym.ile({PLAT}) == 3 and sym.depo()["p"] == [])

sym = Symulacja([{"id": BAG, "ilosc": 1}, {"id": 2868, "ilosc": 1}, {"id": PLAT, "ilosc": 9}], depo=[])
e = zglasza(lambda: Testowe(sym).depo_zloz(3))
sprawdz("1h depo: dwa bagi w plecaku = błąd (nie zgadujemy, który jest na runy)", e and "bagi" in e.powod and sym.depo()["p"] == [], e)

sym = Symulacja([{"id": BAG, "ilosc": 1}, {"id": PLAT, "ilosc": 9}], depo=[{"id": GOLD, "ilosc": 1}] * 16, widoczne_depo=16)
e = zglasza(lambda: Testowe(sym).depo_zloz(3))
sprawdz("1i depo: skrzynka bez wolnego widocznego pola = błąd", e and "wolnego" in e.powod, e)

sym = Symulacja([{"id": BAG, "ilosc": 1}, {"id": PLAT, "ilosc": 9}], depo=[])
a = Testowe(sym)
a.depo_otwarte = False
sprawdz("1j depo: skrzynia się nie otworzyła -> False, nic nie ruszone", a.depo_zloz(3) is False and sym.ile({PLAT}) == 9)

sym = Symulacja([{"id": PLAT, "ilosc": 1}], depo=[])
Testowe(sym).depo_zloz(0)
sprawdz("1k depo: pojedyncza sztuka nie wymaga okna ilości (zostaw 0)", sym.ile({PLAT}) == 0 and sym.depo()["p"] == [{"id": PLAT, "ilosc": 1}], sym.depo()["p"])

# uwaga #1 przeglądu: przedmiot spada na podłogę (ubytek w plecaku się zgadza, w skrzynce nie przybywa)
sym = Symulacja([{"id": BAG, "ilosc": 1}], depo=[])
sym.spada = True
e = zglasza(lambda: Testowe(sym).depo_zloz(3))
sprawdz("1l depo (#1): bag spadł na podłogę -> błąd, bo skrzynka nie zyskała przedmiotu", e and "obu końcach" in e.powod, e)
sym = Symulacja([{"id": PLAT, "ilosc": 13}], depo=[])
sym.spada = True
e = zglasza(lambda: Testowe(sym).depo_zloz(3))
sprawdz("1m depo (#1): platinum spadło na podłogę -> błąd (oba końce)", e and "obu końcach" in e.powod, e)

# uwaga #2: okno przeniesionego baga zostaje otwarte -> musi zostać zamknięte; nowy bag z blankami nie jest odkładany
sym = Symulacja([{"id": BAG, "ilosc": 1}, {"id": PLAT, "ilosc": 13}], depo=[], bag=[{"id": UH, "ilosc": 1}] * 20)
a = Testowe(sym)
a.depo_zloz(3)
sprawdz("1n depo (#2): okno baga z UH zostało otwarte po przeniesieniu -> zamknięte, w pamięci tylko plecak", len(sym.kon) == 1
        and sym.glowny()["nazwa"] == "backpack", sym.kon.keys())
sym = Symulacja([{"id": BAG, "ilosc": 1}, {"id": PLAT, "ilosc": 13}], depo=[], bag=[{"id": BLANK, "ilosc": 1}] * 20)
e = zglasza(lambda: Testowe(sym).depo_zloz(3))
sprawdz("1o depo (#2): otwarty bag z samymi blankami = nowy bag, nie odkładamy (idempotencja po awarii), nic nie ruszone",
        e and "nowy bag" in e.powod and sym.depo()["p"] == [] and sym.ile({PLAT}) == 13, e)

# 22.10 (wydra, Thais): worek na runy to zwykły backpack (2854), więc OBA okna nazywają się "backpack" (dawniej: błąd "dwa kontenery")
WOREK, HMM, LOPATA, LINA = 2854, 3198, 3457, 3003
WYDRA_G = [{"id": GOLD, "ilosc": 100}] * 9 + [{"id": WOREK, "ilosc": 1}, {"id": LOPATA, "ilosc": 1}, {"id": LINA, "ilosc": 1}, {"id": PLAT, "ilosc": 13}]
WYDRA_W = [{"id": HMM, "ilosc": 20}]


def wydra(depo=None):
    return Symulacja(WYDRA_G, depo=depo, bag=WYDRA_W, nazwa_bagu="backpack")      # numer 0 = worek (wyżej), 1 = plecak


sym = wydra(depo=[])
a = Testowe(sym)
g = a._glowny()
sprawdz("1p dwa okna \"backpack\" (worek z HMM, plecak z workiem w środku): główny = plecak z workiem", g and g["numer"] == 1, g)
sprawdz("1p2 dwa okna: majątek tylko z głównego = złoto plecaka (900 + 1300 z platinum), bez worka", a.majatek(tylko_glowny=True) == 900 + 1300, a.majatek(True))
# 22.10 wydra (Thais): bank zamienił złoto w slocie 10 ekwipunku na 6 platinum; majątek z samych kontenerów widział 13 gp
sym_e = wydra(depo=[])
a_e = Testowe(sym_e)
bez = a_e.majatek()
sym_e.ekw = {10: {"id": PLAT, "ilosc": 6}}
sprawdz("1p5 majątek liczy też monety ze slotu 10 ekwipunku (6 platinum = 600 gp więcej), także tylko_glowny",
        a_e.majatek() == bez + 600 and a_e.majatek(tylko_glowny=True) == 2200 + 600, (bez, a_e.majatek(), a_e.majatek(True)))
sym_e.ekw = {10: {"id": GOLD, "ilosc": 45}, 3: {"id": PLAT, "ilosc": 9}}
sprawdz("1p6 slot 10 ze złotem liczy się 1:1, inne sloty ekwipunku nie", a_e.majatek() == bez + 45, a_e.majatek())
sym_e.ekw = {10: {"id": 3446, "ilosc": 50}}
sprawdz("1p7 amunicja (nie moneta) w slocie 10 nie wlicza się do majątku", a_e.majatek() == bez, a_e.majatek())
sym_e.ekw = None
sprawdz("1p8 brak odczytu ekwipunku = majątek jak dotąd (tylko kontenery)", a_e.majatek() == bez, a_e.majatek())
a_e._stwory_dane = "BLAD"
sprawdz("1p9 błąd gniazda przy odczycie ekwipunku nie wywala majątku", a_e.majatek() == bez, a_e.majatek())
sym_e.ekw = {10: {"id": PLAT, "ilosc": 6}}
a_e._stwory_dane = []
sprawdz("1pa blanki luzem w plecaku liczone osobno od baga: ilosc_w_plecaku(blank) = 0 w tym układzie", a_e.ilosc_w_plecaku({3147}) == 0)
sprawdz("1p3 dwa okna: worek jest bagiem na runy (wolne sloty = 20 - 1), bag nie jest potrzebny", a.wolne_w_bagu() == 19 and not a.potrzeba_baga(),
        (a.wolne_w_bagu(), a.potrzeba_baga()))
sprawdz("1p4 dwa okna: _czy_glowny/_czy_bag wskazują rozłączne role", [A._czy_glowny(k, a.kontenery()) for k in a.kontenery()] == [False, True, False]
        and [A._czy_bag(k, a.kontenery()) for k in a.kontenery()] == [True, False, False], a.kontenery())
sprawdz("1p5 dwa okna: depo_zloz odkłada worek z plecaka (slot 9) i platinum, zostaje 1 okno plecaka",
        a.depo_zloz(3) is True and not any(q["id"] == WOREK for q in sym.glowny()["p"]) and sym.ile({PLAT}) == 3
        and any(q["id"] == WOREK for q in sym.depo()["p"]) and len(sym.kon) == 1, (sym.kon, sym.depo()))

# po przeniesieniu worka do depo jego okno zostaje: główny to jedyny bez przewagi run (nie ma już bagu w środku)
sym = wydra(depo=[])
sym.kon[1]["p"] = [q for q in sym.kon[1]["p"] if q["id"] != WOREK]
g = Testowe(sym)._glowny()
sprawdz("1p6 dwa okna bez bagu w żadnym: główny = ten bez przewagi run", g and g["numer"] == 1, g)
sym = wydra()
sym.kon[0]["p"], sym.kon[1]["p"] = [], [{"id": GOLD, "ilosc": 5}]
g = Testowe(sym)._glowny()
sprawdz("1p7 dwa okna bez bagu, pusty worek: główny = jedyny niepusty", g and g["numer"] == 1, g)

# nie zgadujemy: brak jednoznacznego rozstrzygnięcia = ten sam błąd co dawniej
sym = wydra()
sym.kon[0]["p"] = [{"id": WOREK, "ilosc": 1}] + sym.kon[0]["p"]               # w obu oknach leży bag
e = zglasza(lambda: Testowe(sym)._glowny())
sprawdz("1p8 dwa okna, bag w obu = błąd (nie odróżnię)", e and "dwa kontenery" in e.powod, e)
sym = wydra()
sym.kon[1]["p"] = [{"id": HMM, "ilosc": 20}, {"id": UH, "ilosc": 1}]          # bez bagu, oba z runami
e = zglasza(lambda: Testowe(sym)._glowny())
sprawdz("1p9 dwa okna bez bagu, oba z przewagą run = błąd", e and "dwa kontenery" in e.powod, e)
sym = wydra()
sym.kon[0]["p"], sym.kon[1]["p"] = [], [{"id": GOLD, "ilosc": 1}]
sym.kon[2] = {"nazwa": "backpack", "poj": 20, "widoczne": 20, "p": [{"id": GOLD, "ilosc": 1}]}
e = zglasza(lambda: Testowe(sym)._glowny())
sprawdz("1p10 trzy okna \"backpack\" = błąd", e and "dwa kontenery" in e.powod, e)
sym = wydra()
sym.kon[0]["p"] = []
sym.kon[1]["p"] = []
e = zglasza(lambda: Testowe(sym)._glowny())
sprawdz("1p11 dwa puste okna bez bagu = błąd", e and "dwa kontenery" in e.powod, e)

# blanki z plecaka do worka-backpacka (Thais); okna rozróżnione po zawartości
sym = Symulacja([{"id": WOREK, "ilosc": 1}] + [{"id": BLANK, "ilosc": 1}] * 15 + [{"id": GOLD, "ilosc": 48}], bag=[{"id": BLANK, "ilosc": 1}] * 5, nazwa_bagu="backpack")
Testowe(sym).przenies_blanki()
sprawdz("1p12 blanki do worka o nazwie \"backpack\": 5 + 15 = 20, plecak bez blanków, gold i worek-przedmiot zostają",
        len([q for q in sym.kon[0]["p"] if q["id"] == BLANK]) == 20 and not any(q["id"] == BLANK for q in sym.kon[1]["p"])
        and any(q["id"] == WOREK for q in sym.kon[1]["p"]) and sym.ile({GOLD}) == 48, (sym.kon[0]["p"], sym.kon[1]["p"]))
# stary worek "blue backpack" (Edron) nadal działa jak dotąd: jedna nazwa "backpack" = główny
sym = Symulacja([{"id": BAG, "ilosc": 1}, {"id": PLAT, "ilosc": 9}], depo=[], bag=[{"id": UH, "ilosc": 1}] * 3)
a = Testowe(sym)
sprawdz("1p13 Edron: \"blue backpack\" + \"backpack\": główny = backpack, bag = blue", a._glowny()["nazwa"] == "backpack"
        and [A._czy_bag(k, a.kontenery()) for k in a.kontenery()] == [True, False, False], a.kontenery())


# R5: nie scalamy ze stosem, gdy suma przekroczyłaby 100
sym = Symulacja([{"id": BAG, "ilosc": 1}, {"id": PLAT, "ilosc": 13}], depo=[{"id": PLAT, "ilosc": 95}])
Testowe(sym).depo_zloz(3)
stosy = sorted(q["ilosc"] for q in sym.depo()["p"] if q["id"] == PLAT)
sprawdz("1q depo (R5): stos 95 + 10 przekroczyłby 100 -> osobny stos (95 i 10), nic nie przepada", stosy == [10, 95], stosy)
sym = Symulacja([{"id": BAG, "ilosc": 1}, {"id": PLAT, "ilosc": 13}], depo=[{"id": PLAT, "ilosc": 90}])
Testowe(sym).depo_zloz(3)
sprawdz("1r depo (R5): stos 90 + 10 = 100 mieści się -> scalone", [q["ilosc"] for q in sym.depo()["p"] if q["id"] == PLAT] == [100])

# R7: zamknięcie okien się nie udaje
sym = Symulacja([{"id": BAG, "ilosc": 1}, {"id": PLAT, "ilosc": 13}], depo=[])
a = Testowe(sym)
a._zamknij = lambda numer: False                       # klik w X nic nie zamyka
e = zglasza(lambda: a.depo_zloz(3))
sprawdz("1s depo (R7): okna nie dają się zamknąć = błąd po trzech próbach (STOP), nie ciche „ok”", e and "otwarte okna" in e.powod, e)

# prawdziwe _okna_numery (dotąd nietestowane): okna z loot.znajdz_okna, kontenery z pamięci
import loot as _loot


class _Dla(Testowe):
    def __init__(self, sym, okna):
        super().__init__(sym)
        self.okna = okna

    def _okna_numery(self, obraz):
        return A.AkcjeZywe._okna_numery(self, obraz)


def okna_numery(okna, sym):
    stare, stare_dopasuj = _loot.znajdz_okna, _loot.dopasuj_okna
    _loot.znajdz_okna = lambda obraz: okna
    _loot.dopasuj_okna = lambda obraz, o, k: (None, "atrapa: bez zrzutu")     # 22.10: bez obrazu rezerwa po numerze (atrapa Slot nie ma wnetrze())
    try:
        try:
            return _Dla(sym, okna)._okna_numery(None), None
        except SerwisBlad as e:
            return None, e
    finally:
        _loot.znajdz_okna, _loot.dopasuj_okna = stare, stare_dopasuj


sym = Symulacja([{"id": GOLD, "ilosc": 1}], depo=[], bag=[{"id": BLANK, "ilosc": 1}])
wynik, blad = okna_numery([Okno(8, 300), Okno(20, 100), Okno(16, 200)], sym)
sprawdz("1t _okna_numery: okna od góry w dół dopasowane do kontenerów po numerze (bag, plecak, depot)", blad is None
        and [k["nazwa"] for _o, k in wynik] == ["blue backpack", "backpack", "depot chest"], (wynik, blad))
wynik, blad = okna_numery([Okno(20, 100)], sym)
sprawdz("1u _okna_numery: jedno okno na ekranie, trzy kontenery w pamięci = błąd", blad and "okien na ekranie" in blad.powod, blad)
wynik, blad = okna_numery([Okno(20, 100), Okno(20, 200), Okno(40, 300)], sym)
sprawdz("1v _okna_numery: okno z 40 slotami dla kontenera o pojemności 30 = błąd (zła zgodność okno/kontener)",
        blad and "pojemność" in blad.powod, blad)

# 22.10 invincible (Edron, depo): okno depot chest na dole panelu ma ucięty piąty rząd; 4 sloty „zajęte" wg czy_pusty unieważniały
# dopasowanie po zawartości, a przypisanie po numerze kontenera zamieniało okna plecaka i baga (bot chwytał HMM zamiast baga).
# Zrzut inv3 z tej chwili + pamięć kontenerów z logu (numer 0 = backpack, 1 = blue backpack: numer NIE jest położeniem okna).
INV3 = Image.open(KAT / "testy" / "dane" / "inv3_edron_depo_ucięte_1022.png").convert("RGB")


def kon_invincible(hmm=20):
    return [{"numer": 0, "nazwa": "backpack", "pojemnosc": 20,
             "przedmioty": [{"slot": i, "id": x, "ilosc": 1} for i, x in enumerate([3035, 3577, 3031, 2869, 3457])]},
            {"numer": 1, "nazwa": "blue backpack", "pojemnosc": 20, "przedmioty": [{"slot": i, "id": 3198, "ilosc": 1} for i in range(hmm)]},
            {"numer": 2, "nazwa": "depot chest", "pojemnosc": 30, "przedmioty": []}]


class _Zywe(Testowe):
    def __init__(self, kon):
        super().__init__(Symulacja([]))
        self.kon_pamiec = kon

    def kontenery(self):
        return self.kon_pamiec

    def pary(self, obraz=INV3):
        return A.AkcjeZywe._okna_numery(self, obraz)


a = _Zywe(kon_invincible())
pary = a.pary()
sprawdz("1w okna (invincible): ucięty rząd depot chest nie psuje dopasowania; od góry blue backpack, backpack, depot chest (a nie po numerze)",
        [k["nazwa"] for _o, k in pary] == ["blue backpack", "backpack", "depot chest"], [k["nazwa"] for _o, k in pary])
sprawdz("1w2 okna: po udanym dopasowaniu zapamiętana kolejność okien (numery 1, 0, 2)", a._kolejnosc_okien == [1, 0, 2], a._kolejnosc_okien)

stare_dop = _loot.dopasuj_okna
_loot.dopasuj_okna = lambda obraz, o, k: (None, "niezgodne z ekranem (atrapa)")
try:
    a = _Zywe(kon_invincible())
    e = zglasza(lambda: a.pary())
    sprawdz("1x okna: dopasowanie zawodzi, brak historii = SerwisBlad PRZED ruchem (nie po numerze, który zamieniłby okna)",
            e and "nie przypiszę" in e.powod and a.mysz.akcje == [], (e, a.mysz.akcje))
    a._kolejnosc_okien = [1, 0, 2]
    pary = a.pary()
    sprawdz("1y okna: dopasowanie zawodzi, ale kolejność z poprzedniego odczytu zgadza się z ekranem = bez zamiany",
            [k["nazwa"] for _o, k in pary] == ["blue backpack", "backpack", "depot chest"], [k["nazwa"] for _o, k in pary])
    a.kon_pamiec = kon_invincible(hmm=19)                    # pamięć o jedną sztukę za ekranem
    pary = a.pary()
    sprawdz("1y2 okna: pamięć o 1 slot za ekranem, historia nadal najlepsza = bez zamiany",
            [k["nazwa"] for _o, k in pary] == ["blue backpack", "backpack", "depot chest"], [k["nazwa"] for _o, k in pary])
    a._kolejnosc_okien = [0, 1, 2]                           # historia sprzeczna z ekranem (okna zamienione)
    e = zglasza(lambda: a.pary())
    sprawdz("1y3 okna: historia sprzeczna z ekranem = SerwisBlad, nie zgadujemy", e and "nie przypiszę" in e.powod, e)
    a._kolejnosc_okien = [7, 8, 9]
    e = zglasza(lambda: a.pary())
    sprawdz("1y4 okna: historia o innych numerach kontenerów (okna otwarte na nowo) nie obowiązuje", e and "nie przypiszę" in e.powod, e)
finally:
    _loot.dopasuj_okna = stare_dop

# --- start: bot, HP, potwory, odczyt stworów --------------------------------------------------------------------------

sym = Symulacja([{"id": GOLD, "ilosc": 5}])
sprawdz("2a start: zdrowy, bez potworów = ok", zglasza(lambda: Testowe(sym).sprawdz_start()) is None)
e = zglasza(lambda: Testowe(sym, gracz={"hp": 100, "max_hp": 240}).sprawdz_start())
sprawdz("2b start: HP 42% = błąd", e and "HP" in e.powod, e)
mob = {"nazwa": "Goblin", "gracz": False, "x": 33172, "y": 31813, "z": 7, "hp": 100}
e = zglasza(lambda: Testowe(sym, stwory=[mob]).sprawdz_start())
sprawdz("2c start: goblin 2 pola obok = błąd", e and "potwór" in e.powod, e)
sprawdz("2d start: goblin 20 pól dalej nie przeszkadza", zglasza(lambda: Testowe(sym, stwory=[dict(mob, x=33190)]).sprawdz_start()) is None)
sprawdz("2e start: gracz obok to nie potwór", zglasza(lambda: Testowe(sym, stwory=[dict(mob, gracz=True, nazwa="Zufik")]).sprawdz_start()) is None)
for imie in ("Ebenizer", "Mirabell", "Beatrice", "Alexander"):
    sprawdz(f"2e' start (R1): NPC {imie} 2 pola obok to nie potwór (wznawianie po porażce przy NPC)",
            zglasza(lambda: Testowe(sym, stwory=[dict(mob, nazwa=imie)]).sprawdz_start()) is None)
sprawdz("2e'' start (R1): martwy potwór (hp 0) obok nie blokuje", zglasza(lambda: Testowe(sym, stwory=[dict(mob, hp=0)]).sprawdz_start()) is None)
e = zglasza(lambda: Testowe(sym, stwory="BLAD").sprawdz_start())
sprawdz("2f start: brak odczytu = błąd (nie zakładamy, że czysto)", e and "nie odczytam" in e.powod, e)
e = zglasza(lambda: Testowe(sym, stwory="BLAD").pole_zajete((1, 2, 3)))
sprawdz("2g pole_zajete: brak odczytu stworów = błąd, nie „wolne” (fail-closed)", e is not None, e)
sprawdz("2h pole_zajete: gracz na polu = zajęte, ja sam = wolne", Testowe(sym, stwory=[dict(mob, gracz=True, nazwa="Zufik", x=1, y=2, z=3)]).pole_zajete((1, 2, 3))
        and not Testowe(sym, stwory=[dict(mob, gracz=True, nazwa="Mastafian", x=1, y=2, z=3)]).pole_zajete((1, 2, 3)))


# --- zakupy i bank ---------------------------------------------------------------------------------------------------

class RozmowaAtrapa:
    """Podmienia Rozmowa: zakup zmienia plecak w symulacji tak jak NPC."""

    def __init__(self, sym, efekt=None, blad=None):
        self.sym, self.efekt, self.blad, self.log = sym, efekt, blad, []

    def powitaj(self, npc):
        self.log.append(("hi", npc))

    def zamow(self, npc, tekst, limit, ile=None, slepy_yes=False):
        self.log.append(("zamow", npc, tekst, limit, ile, slepy_yes))
        if self.blad:
            raise SerwisBlad("rozmowa", self.blad)
        if self.efekt:
            self.efekt(self.sym)
        return (ile or 1), 10

    def zmien_gold(self, npc, n):
        self.log.append(("zmien_gold", npc, n))
        if self.efekt:
            self.efekt(self.sym)
        return True


def kupno(id_, n, koszt, zrodlo=0):
    """Efekt zakupu: +n sztuk id_ w plecaku, -koszt gold z pierwszego stosu gold."""
    def f(sym):
        g = sym.glowny()["p"]
        g.append({"id": id_, "ilosc": n})
        st = next(q for q in g if q["id"] == GOLD)
        st["ilosc"] -= koszt
    return f


sym = Symulacja([{"id": GOLD, "ilosc": 148}])
r = RozmowaAtrapa(sym, efekt=kupno(HAM, 5, 40))
a = Testowe(sym, r)
sprawdz("3a ham: kupuje brakujące 5 (cel 5, mam 0), ślepe yes dozwolone, wydano 40", a.kup("Mirabell", "ham", 5) == 5
        and r.log[-1] == ("zamow", "Mirabell", "5 ham", 12, 5, True), r.log)
sym = Symulacja([{"id": HAM, "ilosc": 3}, {"id": GOLD, "ilosc": 100}])
r = RozmowaAtrapa(sym, efekt=kupno(HAM, 2, 16))
sprawdz("3b ham: mam 3, cel 5 -> zamawia 2", Testowe(sym, r).kup("Mirabell", "ham", 5) == 2 and r.log[-1][2] == "2 ham", r.log)
sym = Symulacja([{"id": HAM, "ilosc": 5}])
r = RozmowaAtrapa(sym)
sprawdz("3c ham: już mam cel -> nie rozmawia (idempotentnie)", Testowe(sym, r).kup("Mirabell", "ham", 5) == 0 and r.log == [])
sym = Symulacja([{"id": GOLD, "ilosc": 148}])
r = RozmowaAtrapa(sym, efekt=kupno(HAM, 5, 40))
sprawdz("3c2 prefiks zamówienia (Thais: Frodo/Xodet „buy ”): „buy 5 ham”, reszta jak w 3a; bez prefiksu bez zmian (3a)",
        Testowe(sym, r).kup("Frodo", "ham", 5, prefiks="buy ") == 5 and r.log[-1] == ("zamow", "Frodo", "buy 5 ham", 12, 5, True), r.log)
sym = Symulacja([{"id": GOLD, "ilosc": 148}])
e = zglasza(lambda: Testowe(sym, RozmowaAtrapa(sym)).kup("Mirabell", "ham", 5))
sprawdz("3d zakup bez skutku w plecaku = błąd (nie wierzymy samemu tekstowi NPC)", e and "oczekiwano dokładnie +5" in e.powod, e)
sym = Symulacja([{"id": GOLD, "ilosc": 148}])
e = zglasza(lambda: Testowe(sym, RozmowaAtrapa(sym, blad="oferta za droga")).kup("Mirabell", "ham", 5))
sprawdz("3e błąd rozmowy propaguje się jako SerwisBlad", e and "za droga" in e.powod, e)
sym = Symulacja([{"id": GOLD, "ilosc": 1000}])
e = zglasza(lambda: Testowe(sym, RozmowaAtrapa(sym, efekt=kupno(HAM, 6, 48))).kup("Mirabell", "ham", 5))
sprawdz("3f ham (#4): kupiono 6 zamiast 5 = błąd (górna granica ilości)", e and "dokładnie +5" in e.powod, e)
sym = Symulacja([{"id": GOLD, "ilosc": 1000}])
e = zglasza(lambda: Testowe(sym, RozmowaAtrapa(sym, efekt=kupno(HAM, 5, 400))).kup("Mirabell", "ham", 5))
sprawdz("3g ham (#4): 5 sztuk, ale zapłacono 400 gp (limit 12/szt.) = błąd po fakcie", e and "wydano 400" in e.powod, e)

sym = Symulacja([{"id": GOLD, "ilosc": 148}])
r = RozmowaAtrapa(sym, efekt=kupno(BAG, 1, 20))
a = Testowe(sym, r)
sprawdz("3h backpack: brak baga -> kupuje jeden", a.potrzeba_baga() and a.kup("Beatrice", "backpack", 1) == 1 and r.log[-1][2] == "backpack", r.log)
sym = Symulacja([{"id": GOLD, "ilosc": 48}, {"id": BAG, "ilosc": 1}])
r = RozmowaAtrapa(sym)
a = Testowe(sym, r)
sprawdz("3i backpack: bag leży w plecaku -> nie kupuje", not a.potrzeba_baga() and a.kup("Beatrice", "backpack", 1) == 0 and r.log == [])
sym = Symulacja([{"id": GOLD, "ilosc": 48}], bag=[{"id": BLANK, "ilosc": 1}] * 3)
sprawdz("3j backpack: otwarty bag na runy -> nie kupuje", not Testowe(sym, RozmowaAtrapa(sym)).potrzeba_baga())
sym = Symulacja([{"id": GOLD, "ilosc": 48}], bag=[{"id": 1, "ilosc": 1}])
sym.kon[0]["nazwa"] = "dead goblin"
sprawdz("3k backpack (#2): otwarte zwłoki to nie bag na runy -> bag nadal potrzebny", Testowe(sym, RozmowaAtrapa(sym)).potrzeba_baga())

sym = Symulacja([{"id": GOLD, "ilosc": 1350}, {"id": PLAT, "ilosc": 2}])


def wymiana(sym):
    g = sym.glowny()["p"]
    g[0]["ilosc"] -= 1300
    g[1]["ilosc"] += 13


r = RozmowaAtrapa(sym, efekt=wymiana)
a = Testowe(sym, r)
sprawdz("4a bank: 1350 gold -> 13 platinum (reszta 50 gold zostaje)", a.bank_zmien("Ebenizer") == 13 and r.log == [("zmien_gold", "Ebenizer", 13)]
        and sym.ile({PLAT}) == 15 and sym.ile({GOLD}) == 50, r.log)
sym = Symulacja([{"id": GOLD, "ilosc": 60}])
r = RozmowaAtrapa(sym)
sprawdz("4b bank: poniżej 100 gold nie ma czego wymieniać", Testowe(sym, r).bank_zmien("Ebenizer") == 0 and r.log == [])
sym = Symulacja([{"id": GOLD, "ilosc": 500}, {"id": PLAT, "ilosc": 0}])
e = zglasza(lambda: Testowe(sym, RozmowaAtrapa(sym)).bank_zmien("Ebenizer"))
sprawdz("4c bank: NPC „wymienił”, ale plecak się nie zmienił = błąd", e and e.krok == "bank", e)


def tylko_platinum(sym):
    sym.glowny()["p"][1]["ilosc"] += 5               # platinum przybyło, gold nie spadło


sym = Symulacja([{"id": GOLD, "ilosc": 500}, {"id": PLAT, "ilosc": 0}])
e = zglasza(lambda: Testowe(sym, RozmowaAtrapa(sym, efekt=tylko_platinum)).bank_zmien("Ebenizer"))
sprawdz("4d bank (#7): platinum przybyło, ale gold nie spadł = błąd (sprawdzamy oba końce)", e and e.krok == "bank", e)

# 23.10 (wydra, bank Suzy w Thais): złoto w slocie 10 ekwipunku (amunicja) też idzie do wymiany, a platinum ląduje w tym slocie;
# kontrola po wymianie porównuje SUMY (kontenery + slot 10), nie same kontenery.
def probuj(f):
    """Wynik albo wyjątek SerwisBlad (czerwony test zamiast przerwanego pliku)."""
    try:
        return f()
    except SerwisBlad as e:
        return e


def wymiana_slot(ile_plat, zabierz_z_plecaka):
    """Serwer zabiera `zabierz_z_plecaka` gold z plecaka, resztę z baku slotu 10, i wkłada platinum do slotu 10 (stack)."""
    def f(sym):
        sym.glowny()["p"][0]["ilosc"] -= zabierz_z_plecaka
        e = sym.ekw.get(10)
        if e and e["id"] == GOLD:                              # złoto ze slotu 10 zeszło w całości (wyjmowane wcześniej)
            sym.ekw[10] = {"id": PLAT, "ilosc": ile_plat}
        elif e and e["id"] == PLAT:
            e["ilosc"] += ile_plat
        else:
            sym.ekw[10] = {"id": PLAT, "ilosc": ile_plat}
    return f


sym = Symulacja([{"id": GOLD, "ilosc": 595}])
sym.ekw = {10: {"id": GOLD, "ilosc": 88}}
r = RozmowaAtrapa(sym, efekt=wymiana_slot(6, 512))           # 683 - 600 = 83: 512 z plecaka, 88 ze slotu -> w plecaku zostaje 83
a = Testowe(sym, r)
sprawdz("4e bank (23.10): 595 gp w plecaku + 88 w slocie 10 -> prosi o 6 platinum, platinum w slocie 10, 83 gp zostaje",
        probuj(lambda: a.bank_zmien("Suzy")) == 6 and r.log == [("zmien_gold", "Suzy", 6)] and sym.ekw[10] == {"id": PLAT, "ilosc": 6}
        and sym.ile({GOLD}) == 83, (r.log, sym.ekw, sym.ile({GOLD})))
sym = Symulacja([{"id": GOLD, "ilosc": 183}])
sym.ekw = {10: {"id": PLAT, "ilosc": 5}}
r = RozmowaAtrapa(sym, efekt=wymiana_slot(1, 100))
sprawdz("4f bank (23.10): stan po porażce, 183 gp + 5 platinum w slocie 10 -> prosi o 1 platinum, slot 10 = 6 (stack), plecak 83",
        probuj(lambda: Testowe(sym, r).bank_zmien("Suzy")) == 1 and r.log == [("zmien_gold", "Suzy", 1)] and sym.ekw[10] == {"id": PLAT, "ilosc": 6}
        and sym.ile({GOLD}) == 83, (r.log, sym.ekw))
sym = Symulacja([{"id": GOLD, "ilosc": 595}])
sym.ekw = {10: {"id": 3446, "ilosc": 50}}                     # w slocie 10 strzały, nie monety
sym.glowny()["p"].append({"id": PLAT, "ilosc": 0})


def wymiana5(sym):
    sym.glowny()["p"][0]["ilosc"] -= 500
    sym.glowny()["p"][1]["ilosc"] += 5
r = RozmowaAtrapa(sym, efekt=wymiana5)
sprawdz("4g bank (23.10): w slocie 10 amunicja (nie monety) -> jak dotąd 5 platinum z plecaka",
        probuj(lambda: Testowe(sym, r).bank_zmien("Suzy")) == 5 and r.log == [("zmien_gold", "Suzy", 5)] and sym.ile({PLAT}) == 5, r.log)
sym = Symulacja([{"id": GOLD, "ilosc": 595}])
sym.ekw = {10: {"id": GOLD, "ilosc": 88}}
e = zglasza(lambda: Testowe(sym, RozmowaAtrapa(sym)).bank_zmien("Suzy"))
sprawdz("4h bank (23.10): nic się nie zmieniło mimo złota w slocie 10 = nadal błąd", e and e.krok == "bank", e)

# depo po takiej wymianie: platinum w slocie 10 nie jest ruszane, w plecaku nie ma czego odkładać (nie błąd)
sym = Symulacja([{"id": BAG, "ilosc": 1}, {"id": GOLD, "ilosc": 83}], depo=[])
sym.ekw = {10: {"id": PLAT, "ilosc": 6}}
a = Testowe(sym)
sprawdz("4i depo (23.10): platinum tylko w slocie 10 -> depo składa bag i nie rzuca błędu, slot 10 nietknięty",
        probuj(lambda: a.depo_zloz(3)) is True and sym.ekw[10] == {"id": PLAT, "ilosc": 6} and any(q["id"] == BAG for q in sym.depo()["p"]), sym.ekw)

# --- blanki do baga na runy -------------------------------------------------------------------------------------------

sym = Symulacja([{"id": BLANK, "ilosc": 1}] * 15 + [{"id": GOLD, "ilosc": 48}], bag=[{"id": BLANK, "ilosc": 1}] * 5)
Testowe(sym).przenies_blanki()
bag = sym.kon[0]["p"]
sprawdz("5a blanki: 15 z plecaka do baga (5 + 15 = 20), gold zostaje", len([q for q in bag if q["id"] == BLANK]) == 20
        and not any(q["id"] == BLANK for q in sym.glowny()["p"]) and sym.ile({GOLD}) == 48, (len(bag), sym.glowny()["p"]))
sym = Symulacja([{"id": BLANK, "ilosc": 1}] * 3, bag=[{"id": BLANK, "ilosc": 1}] * 20)
e = zglasza(lambda: Testowe(sym).przenies_blanki())
sprawdz("5b blanki: pełny bag = błąd", e and e.krok == "blanki", e)
sym = Symulacja([{"id": BLANK, "ilosc": 1}] * 3)
e = zglasza(lambda: Testowe(sym).przenies_blanki())
sprawdz("5c blanki: brak okna baga = błąd", e and "jednego plecaka i jednego bagu" in e.powod, e)
sym = Symulacja([{"id": BLANK, "ilosc": 1}] * 3, bag=[{"id": 1, "ilosc": 1}])
sym.kon[0]["nazwa"] = "dead goblin"
e = zglasza(lambda: Testowe(sym).przenies_blanki())
sprawdz("5d blanki (#2): otwarte zwłoki nie są bagiem na runy = błąd, blanki nie lecą do cudzego kontenera",
        e and "bagów" in e.powod and sum(1 for q in sym.glowny()["p"] if q["id"] == BLANK) == 3, e)
sym = Symulacja([{"id": BLANK, "ilosc": 1}] * 3, bag=[])
sym.spada = True
e = zglasza(lambda: Testowe(sym).przenies_blanki())
sprawdz("5e blanki (#1): blank spadł na podłogę = błąd (oba końce)", e and "obu końcach" in e.powod, e)

# 23.10 14:06 (wydra, Thais, Xodet): po zakupie 20 blank run plecak (20 slotów, pełny) trzyma 15 blanków, worek 5; przeniesienie
# stanęło na "przeciągnięcie blanku do bagu nie dało skutku na obu końcach" (w worku 9, w plecaku 11), choć wolnych pól było 11.
# `przenies_blanki` czytało pamięć raz, po stałych 0,9 s, i każdy brak skutku (opóźniony odczyt, chwilowo pusta lista kontenerów,
# połknięte przeciągnięcie) kończył krokiem SerwisBlad + STOP; depo od 22.10 czeka na skutek (`_poczekaj_na_skutek`).
PERELKI = 3033


def thais_po_zakupie():
    """Układ z ekranu 14:07: główny plecak pełny (gold, 15 blanków, worek, perełki x2, mięso x5, łopata), worek z 5 blankami."""
    glowny = [{"id": GOLD, "ilosc": 89}] + [{"id": BLANK, "ilosc": 1}] * 15 + [{"id": WOREK, "ilosc": 1}, {"id": PERELKI, "ilosc": 2},
                                                                              {"id": 3577, "ilosc": 5}, {"id": LOPATA, "ilosc": 1}]
    return Symulacja(glowny, bag=[{"id": BLANK, "ilosc": 1}] * 5, nazwa_bagu="backpack")


class Opozniony(Testowe):
    """Pamięć klienta zalega: po kazdym przeciągnięciu `zalega` kolejnych odczytów kontenerów oddaje stan sprzed ruchu
    (`pusto`: oddaje pustą listę, jak `kontenery()` przy odczycie w trakcie zmiany deque), ruch `polykaj` razy w ogóle nie dochodzi do gry."""

    def __init__(self, sym, zalega=0, pusto=False, polykaj=0, **kw):
        super().__init__(sym, **kw)
        self.zalega, self.pusto, self.polykaj = zalega, pusto, polykaj
        self._stary, self._ile = None, 0
        self.ruchy = []

    def kontenery(self):
        if self._ile > 0:
            self._ile -= 1
            return [] if self.pusto else self._stary
        return self.sym.pamiec()

    def _przeciagnij(self, m, okno_z, i_z, okno_do, i_do):
        self.ruchy.append((i_z, i_do))
        if self.polykaj > 0:
            self.polykaj -= 1
            return
        self._stary = self.sym.pamiec()
        Testowe._przeciagnij(self, m, okno_z, i_z, okno_do, i_do)
        self._ile = self.zalega


def blanki_w(k):
    return sum(1 for q in k["p"] if q["id"] == BLANK)


_stare = (A.SKUTEK_CZEKAJ_S, A.SKUTEK_KROK_S, getattr(A, "PRZERWA_PONOWIENIA_S", None))
A.SKUTEK_CZEKAJ_S, A.SKUTEK_KROK_S, A.PRZERWA_PONOWIENIA_S = 1.0, 0.01, 0.0

sym = thais_po_zakupie()
Testowe(sym).przenies_blanki()
sprawdz("5f blanki (Thais 23.10): układ z ekranu, pełny plecak 15 + worek 5 -> worek 20, w plecaku zostaje reszta bez blanków",
        blanki_w(sym.kon[0]) == 20 and blanki_w(sym.kon[1]) == 0 and len(sym.kon[1]["p"]) == 5, (sym.kon[0]["p"], sym.kon[1]["p"]))

for zalega in (1, 2, 5):
    sym = thais_po_zakupie()
    a = Opozniony(sym, zalega=zalega)
    e = zglasza(a.przenies_blanki)
    sprawdz(f"5g blanki (23.10): pamięć zalega o {zalega} odczytów po każdym przeciągnięciu, a ruch się udał -> czekamy, nie błąd, "
            "bez zbędnych przeciągnięć", e is None and blanki_w(sym.kon[0]) == 20 and len(a.ruchy) == 15, (e, len(a.ruchy)))

sym = thais_po_zakupie()
a = Opozniony(sym, zalega=2, pusto=True)
e = zglasza(a.przenies_blanki)
sprawdz("5h blanki (23.10): chwilowo pusta lista kontenerów po przeciągnięciu (odczyt w trakcie zmiany) nie przerywa kroku",
        e is None and blanki_w(sym.kon[0]) == 20 and len(a.ruchy) == 15, (e, len(a.ruchy)))

A.SKUTEK_CZEKAJ_S = 0.05
sym = thais_po_zakupie()
a = Opozniony(sym, polykaj=1)
e = zglasza(a.przenies_blanki)
sprawdz("5i blanki (23.10): jedno przeciągnięcie nie doszło do gry -> ponowione (16 ruchów), kończy 20 w worku",
        e is None and blanki_w(sym.kon[0]) == 20 and len(a.ruchy) == 16, (e, a.ruchy))
sprawdz("5i2 blanki (23.10): ponowienie celuje w inne wolne pole worka niż nieudana próba (rotacja, nie ten sam klik)",
        len(a.ruchy) > 1 and a.ruchy[0][1] != a.ruchy[1][1], a.ruchy[:3])
sprawdz("5i3 blanki (23.10): nic poza blankami nie ruszone (gold, worek, perełki, mięso, łopata zostają w plecaku)",
        [q["id"] for q in sym.kon[1]["p"]] == [GOLD, WOREK, PERELKI, 3577, LOPATA], sym.kon[1]["p"])

sym = thais_po_zakupie()
a = Opozniony(sym, polykaj=99)
e = zglasza(a.przenies_blanki)
sprawdz("5j blanki (23.10): przeciągnięcie nigdy nie działa -> po 3 próbach błąd (nie pętla), z opisem prób i pól",
        e and e.krok == "blanki" and "obu końcach" in e.powod and len(a.ruchy) == 3 and blanki_w(sym.kon[1]) == 15, (e, a.ruchy))

sym = thais_po_zakupie()
sym.spada = True
a = Opozniony(sym)
e = zglasza(a.przenies_blanki)
sprawdz("5k blanki (23.10): blank zniknął z plecaka, a w worku nie przybył -> błąd od razu, bez ponawiania (nie ruszamy dalej na ślepo)",
        e and "obu końcach" in e.powod and len(a.ruchy) == 1, (e, a.ruchy))
A.SKUTEK_CZEKAJ_S, A.SKUTEK_KROK_S = _stare[0], _stare[1]
if _stare[2] is None:
    del A.PRZERWA_PONOWIENIA_S
else:
    A.PRZERWA_PONOWIENIA_S = _stare[2]

# --- układ okien na prawdziwych zrzutach z 19.10 ------------------------------------------------------------------------

D = KAT / "testy" / "dane"


def plotno(nazwa):
    c = Image.new("RGB", (940, 1030))
    c.paste(Image.open(D / nazwa), (756, 0))
    return c


class Okna(Testowe):
    def __init__(self, sym, obrazy):
        super().__init__(sym)
        self.obrazy = list(obrazy)
        self.wywolania = []

    def _zrzut(self, mysz):
        return plotno(self.obrazy.pop(0) if len(self.obrazy) > 1 else self.obrazy[0])

    def _okna_numery(self, obraz):
        return Testowe._okna_numery(self, obraz)

    def _otworz_plecak_z_ekwipunku(self, m, u):
        self.wywolania.append(("plecak_z_ekwipunku", u["plecak_ekw"]))


WOREK_Z, HMM_Z = 2854, 3198
two = Symulacja([{"id": GOLD, "ilosc": 48}], bag=[{"id": BLANK, "ilosc": 1}] * 20)
a = Okna(two, ["panel_zwinieta.png"])
a.przygotuj_okna()
sprawdz("6a okna: zwinięta minimapa i oba okna po 5 rzędów = zero kliknięć (idempotentnie)", a.mysz.akcje == [], a.mysz.akcje)

# 22.10 wydra (Thais): oba okna to "backpack"; dawniej przygotuj_okna padało na "dwa kontenery o nazwie plecaka"
wy = Symulacja([{"id": GOLD, "ilosc": 48}, {"id": WOREK_Z, "ilosc": 1}], bag=[{"id": HMM_Z, "ilosc": 20}], nazwa_bagu="backpack")
a = Okna(wy, ["panel_zwinieta.png"])
a.przygotuj_okna()
sprawdz("6a2 okna (wydra): worek i plecak oba \"backpack\" -> rozpoznane po zawartości, zero kliknięć, bez otwierania plecaka",
        a.mysz.akcje == [] and a.wywolania == [], (a.mysz.akcje, a.wywolania))

a = Okna(two, ["panel_rozwinieta.png", "panel_zwinieta.png"])
a.przygotuj_okna()
sprawdz("6b okna: minimapa rozwinięta -> klika „–” w (909, 42), potem nic więcej", a.mysz.akcje[0] == ("klik", 909, 42, None)
        and len(a.mysz.akcje) == 1, a.mysz.akcje)

a = Okna(two, ["panel_zwinieta_krotki.png", "panel_zwinieta_krotki.png", "panel_zwinieta.png"])
a.przygotuj_okna()
dr = [x for x in a.mysz.akcje if x[0] == "przeciagnij"]
sprawdz("6c okna: plecak 2 rzędy -> jedno przeciągnięcie dolnej krawędzi o 3 rzędy (111 px)", len(dr) == 1
        and dr[0][4] - dr[0][2] == 3 * 37 and dr[0][1] == dr[0][3], a.mysz.akcje)

a = Okna(two, ["panel_zwinieta.png"])
a._zrzut = lambda m: Image.new("RGB", (940, 1030))
e = zglasza(lambda: a.przygotuj_okna())
sprawdz("6d okna: nierozpoznany układ panelu = błąd, żadnych kliknięć", e and "układu panelu" in e.powod and a.mysz.akcje == [], (e, a.mysz.akcje))

# gałąź „bag leży w plecaku, brak drugiego okna”: Ctrl+klik na slocie baga, potem plecak z ekwipunku
sym1 = Symulacja([{"id": BAG, "ilosc": 1}, {"id": GOLD, "ilosc": 48}])
a = Okna(sym1, ["panel_zwinieta.png"])
a.przygotuj_okna()
kl = [x for x in a.mysz.akcje if x[0] == "klik"]
sprawdz("6e okna (#5): bag w plecaku -> Ctrl+klik na jego slocie, potem otwarcie plecaka z ekwipunku", len(kl) == 1 and kl[0][3] == "Control_L"
        and kl[0][1:3] == Slot(0).srodek and a.wywolania and a.wywolania[0][0] == "plecak_z_ekwipunku", (a.mysz.akcje, a.wywolania))
sym2 = Symulacja([{"id": GOLD, "ilosc": 1}] * 9 + [{"id": BAG, "ilosc": 1}])
sym2.kon[0]["widoczne"] = 8
a = Okna(sym2, ["panel_zwinieta.png"])
e = zglasza(lambda: a.przygotuj_okna())
sprawdz("6f okna (#5): bag w slocie 9, a okno pokazuje 8 slotów = SerwisBlad (nie IndexError), zero kliknięć", e and "slotów" in e.powod
        and a.mysz.akcje == [], (e, a.mysz.akcje))
sym3 = Symulacja([{"id": BAG, "ilosc": 1}, {"id": 2868, "ilosc": 1}])
a = Okna(sym3, ["panel_zwinieta.png"])
e = zglasza(lambda: a.przygotuj_okna())
sprawdz("6g okna: dwa bagi w plecaku = błąd (nie wiem, który otworzyć)", e and "bagi" in e.powod, e)

# --- 7. zakładka czatu: tekst idzie do AKTYWNEJ zakładki (22.10 invincible/Wrex: "hi" poszło do prywatnej rozmowy) ---------------

class KlientCzatu:
    """Atrapa klienta: pasek zakładek z rectami, aktywna zakładka, bufory. czat() wpisuje do aktywnego bufora (echo),
    przelacz() klika kartę. `nie_przelacza`: klik nic nie daje; `kanal_nieznany`: wiadomości bez nazwy kanału (jak u invincible)."""
    NAZWY = ["Default", "Server Log", "Trade", "Wrex"]

    def __init__(self, aktywna="Default", nie_przelacza=False, nick="Invincible", bez_odczytu_bufora=False, brak_default=False):
        self.nazwy = [n for n in self.NAZWY if not (brak_default and n == "Default")]
        self.aktywna, self.nie_przelacza, self.nick = aktywna, nie_przelacza, nick
        self.bez_odczytu_bufora = bez_odczytu_bufora
        self.rect = {n: [40 + 70 * i, 763, 104 + 70 * i, 780] for i, n in enumerate(self.nazwy)}
        self.wyslane, self.klikniecia, self.kolejka, self.t, self.nr = [], [], [], 0.0, 0

    def bufor_adres(self, nazwa):
        return "0x%x" % (0x1000 + 0x100 * self.NAZWY.index(nazwa))

    def stan(self):
        return {"zakladki": [{"nazwa": n, "rect": self.rect[n], "stan": 0 if n == self.aktywna else 2,
                              "kolor": [0.87] * 3 if n == self.aktywna else [0.97, 0.37, 0.37], "aktywna": n == self.aktywna}
                             for n in self.nazwy],
                "aktywny_bufor": None if self.bez_odczytu_bufora else self.bufor_adres(self.aktywna)}

    def czat(self, tekst):
        self.wyslane.append((self.aktywna, tekst))
        self.nr += 1
        self.kolejka.append({"autor": self.nick, "tekst": tekst, "kanal": "", "czas": "", "nr": self.nr,
                             "bufor": self.bufor_adres(self.aktywna)})

    def wiad(self):
        w, self.kolejka = self.kolejka, []
        return w

    def przelacz(self, x, y):
        self.klikniecia.append((x, y))
        if self.nie_przelacza:
            return
        for n, (x1, y1, x2, y2) in self.rect.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                self.aktywna = n

    def czas(self):
        return self.t

    def spij(self, s):
        self.t += s

    def rozmowa(self, **kw):
        return A.Rozmowa(self.czat, self.wiad, self.nick, log=lambda *_: None, czas=self.czas, spij=self.spij,
                         stan_zakladek=self.stan, przelacz=self.przelacz, **kw)


k = KlientCzatu()
sprawdz("7a zakładka Default aktywna: wysyła od razu, bez kliku", k.rozmowa().powiedz("hi") and k.wyslane == [("Default", "hi")]
        and k.klikniecia == [], (k.wyslane, k.klikniecia))

k = KlientCzatu(aktywna="Wrex")
ok7b = k.rozmowa().powiedz("hi")
sprawdz("7b aktywna prywatna zakładka (Wrex): najpierw klik w kartę Default, potem wiadomość na Default",
        ok7b and k.wyslane == [("Default", "hi")] and len(k.klikniecia) == 1 and k.rect["Default"][0] <= k.klikniecia[0][0] <= k.rect["Default"][2],
        (k.wyslane, k.klikniecia))

k = KlientCzatu(aktywna="Wrex", nie_przelacza=True)
e = zglasza(lambda: k.rozmowa().powiedz("hi"))
sprawdz("7c przełączenie nie działa: SerwisBlad i ZERO wysłanych wiadomości (nic do gracza)", e and k.wyslane == [] and len(k.klikniecia) == 1, (e, k.wyslane, k.klikniecia))

k = KlientCzatu(aktywna="Wrex")
e = zglasza(lambda: A.Rozmowa(k.czat, k.wiad, k.nick, log=lambda *_: None, czas=k.czas, spij=k.spij, stan_zakladek=k.stan).powiedz("hi"))
sprawdz("7d brak funkcji klikającej: SerwisBlad bez wysłania i bez kliku", e and k.wyslane == [] and k.klikniecia == [], (e, k.wyslane))

k = KlientCzatu()
e = zglasza(lambda: A.Rozmowa(k.czat, k.wiad, k.nick, log=lambda *_: None, czas=k.czas, spij=k.spij).powiedz("hi"))
sprawdz("7e Rozmowa bez odczytu zakładek niczego nie wysyła (fail-closed)", e and k.wyslane == [], (e, k.wyslane))

k = KlientCzatu(bez_odczytu_bufora=True)
e = zglasza(lambda: k.rozmowa().powiedz("hi"))
sprawdz("7f pamięć nie wskazuje aktywnego bufora: brak pewności = SerwisBlad bez wysłania", e and k.wyslane == [], (e, k.wyslane))

k = KlientCzatu(brak_default=True)
e = zglasza(lambda: k.rozmowa().powiedz("hi"))
sprawdz("7g brak karty Default na pasku: SerwisBlad bez wysłania", e and k.wyslane == [], (e, k.wyslane))


class KlientZlyBufor(KlientCzatu):
    """Odczyt mówi, że aktywna jest Default, ale tekst ląduje w buforze Wrexa (stan rozjechał się z rzeczywistością)."""
    def czat(self, tekst):
        self.aktywna = "Wrex"
        super().czat(tekst)
        self.aktywna = "Default"


k = KlientZlyBufor()
e = zglasza(lambda: k.rozmowa().powiedz("hi"))
sprawdz("7h echo w złym buforze (kanał nieznany): przerwanie po 1. próbie, nie 3x", e and len(k.wyslane) == 1 and "bufor" in e.powod, (e, k.wyslane))

k = KlientCzatu()
r = k.rozmowa()
r.powiedz("hi")
k.aktywna = "Wrex"                                       # Karol (albo klient) przełączył zakładkę między wypowiedziami
r.powiedz("trade")
sprawdz("7i kolejna wypowiedź znów sprawdza zakładkę: przełącza na Default przed wysłaniem",
        [w[0] for w in k.wyslane] == ["Default", "Default"] and len(k.klikniecia) == 1, (k.wyslane, k.klikniecia))


print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
