"""Serwis: rozmowa z NPC z miejsca, w którym postać stoi, gdy nie da się wejść na pole stania (decyzja Karola 23.10 ~11:00:
„niech on próbuje pisać, jeśli nie ma przejścia”). Przypadek z żywa: wydra, Thais, krok `jedzenie`, Frodo. Przebieg 1: doszła na
pole stania, Frodo odszedł, „nie odpowiada na hi” -> porażka. Przebieg 2: pole stania (32358,32210) zajęte, `idz_pewnie` czekał
do 150 s („brak drogi … czekam”) zamiast rozmawiać z NPC stojącym 2 pola dalej.

Wszystko offline na atrapach (zegar wirtualny, atrapa postaci, atrapa listy stworów; ekran podmieniony na atrapę, żeby marsz
nie klikał): RETRONIC_TESTY=1, żadnego inputu do gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import random
import sys
import types
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import serwis as S
import serwis_akcje as A
from serwis_blad import SerwisBlad, cheb

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


def blad_z(f):
    try:
        f()
    except SerwisBlad as e:
        return e
    return None


class Zegar:
    """Czas wirtualny: sleep tylko przesuwa wskazówkę, więc czekanie 150 s trwa ułamek sekundy."""
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
_ekran_atrapa = types.ModuleType("ekran")


def _bez_klikania(*_a, **_k):
    raise ValueError("test: bez klików w mapę")        # idz_pewnie przechodzi wtedy na kroki strzałkami


_ekran_atrapa.klik_pola = _bez_klikania
sys.modules["ekran"] = _ekran_atrapa


class MapaOtwarta:
    """Plac 40 x 30 pól, wszystkie chodliwe."""
    def flagi(self, x, y, z):
        return 1 if 0 <= x < 40 and 0 <= y < 30 else 0

    def pole(self, x, y, z):
        return (self.flagi(x, y, z), 0, 10) if self.flagi(x, y, z) else None


KIER = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}


class Swiat:
    """Atrapa Postac: krok zawsze się udaje (poza polami `slepe`), pozycja zmienia się od razu."""
    def __init__(self, poz, slepe=()):
        self.p = [poz[0], poz[1], poz[2] if len(poz) > 2 else 7]
        self.slepe = set(slepe)
        self.kroki = 0

    def pozycja(self):
        ZEGAR.t += 0.004
        return tuple(self.p)

    def krok(self, klawisz):
        d = KIER[klawisz]
        cel = (self.p[0] + d[0], self.p[1] + d[1])
        ZEGAR.t += 0.6
        if cel in self.slepe:
            ZEGAR.t += 1.0
            return None
        self.p[0], self.p[1] = cel
        self.kroki += 1
        return (cel[0], cel[1], self.p[2])


class Akcje:
    """Atrapa AkcjeZywe: lista stworów (NPC i obcy) z pozycjami; kup/bank_zmien zapisują wywołania."""
    nick = "Ja"

    def __init__(self, stwory=(), brak_hi=0, swiat=None, npc_po_hi=None):
        self.st = [dict(x=x, y=y, z=7, nazwa=n) for n, (x, y) in stwory]
        self.brak_hi, self.swiat, self.npc_po_hi = brak_hi, swiat, npc_po_hi
        self.wywolania = []

    def _stwory(self):
        return [dict(q) for q in self.st]

    def pole_zajete(self, pole):
        return any((q["x"], q["y"], q["z"]) == tuple(pole) for q in self.st)

    def _rozmowa(self, rodzaj, npc, *a):
        self.wywolania.append((rodzaj, npc, tuple(self.swiat.pozycja()) if self.swiat else None) + a)
        if self.brak_hi > 0:
            self.brak_hi -= 1
            if self.npc_po_hi is not None:          # NPC odszedł w trakcie: jego nowa pozycja jest już na liście stworów
                for q in self.st:
                    if q["nazwa"] == npc:
                        q["x"], q["y"] = self.npc_po_hi
            raise getattr(A, "BrakOdpowiedziNpc", SerwisBlad)("rozmowa", f"{npc} nie odpowiada na hi (nie stoi obok?)")

    def kup(self, npc, co, docelowo, prefiks=""):
        self._rozmowa("kup", npc, co, docelowo)
        return docelowo

    def bank_zmien(self, npc):
        self._rozmowa("bank", npc)
        return 1

    def cel_ham(self, cel, rezerwa):
        return cel

    def rezerwa_na_blanki(self, blanki):
        return 0.0

    def potrzeba_baga(self):
        return True

    def przygotuj_okna(self):
        pass

    def brakuje(self, co, cel):
        return cel

    def wolne_w_bagu(self):
        return 99

    def przenies_blanki(self):
        pass


class Planer0:
    """Droga = [od, do] (bez mapy); `brak` = pola, do których nie ma drogi."""
    def __init__(self, brak=()):
        self.brak = {tuple(b) for b in brak}
        self.pytane = []

    def droga(self, od, do):
        self.pytane.append(tuple(do))
        return None if tuple(do) in self.brak else [tuple(od), tuple(do)]


def dane(stoi=(20, 12, 7), npc="Frodo", npc_poz=(18, 11, 7), z_npc_poz=True):
    p = {"rodzaj": "kup", "npc": npc, "stoi": list(stoi)}
    if z_npc_poz:
        p["npc_poz"] = list(npc_poz)
    return {"przystanki": {"jedzenie": dict(p), "bank": dict(p, rodzaj="bank"), "backpack": dict(p), "blanki": dict(p)},
            "kolejnosc": ["jedzenie"], "wyjscie": [0, 0, 7], "laczniki": []}


def nowy(start, stwory, stoi=(20, 12, 7), npc_poz=(18, 11, 7), slepe=(), brak_hi=0, npc_po_hi=None, z_npc_poz=True, chodz=None,
         planer=None, npc="Frodo"):
    """Serwis z prawdziwym marszem (S.marsz -> idz_pewnie) na atrapie świata. Zwraca (serwis, akcje, swiat, log)."""
    ZEGAR.t = 1000.0
    getattr(S, "_RUCH", {}).update(koniec=0.0, skala=1.0)
    random.seed(7)
    sw = Swiat(start, slepe)
    ak = Akcje(stwory, brak_hi=brak_hi, swiat=sw, npc_po_hi=npc_po_hi)
    mp = MapaOtwarta()
    log = []

    def chodz_marsz(punkty, tol=0):
        log.append(("chodz", tuple(punkty[-1]), tol))
        return S.marsz(sw, mp, ak, [], punkty, tol, log=lambda m: log.append(("log", m)))

    s = S.Serwis(dane(stoi, npc, npc_poz, z_npc_poz), ak, planer or Planer0(), sw.pozycja, chodz or chodz_marsz,
                 log=lambda m: log.append(("log", m)), spij=ZEGAR.sleep)
    return s, ak, sw, log


def chodzenia(log):
    return [c[1] for c in log if c[0] == "chodz"]


def teksty(log):
    return " | ".join(c[1] for c in log if c[0] == "log")


# --- 1. stała zasięgu rozmowy -------------------------------------------------------------------------------

sprawdz("1a stała ZASIEG_ROZMOWY (odl. Czebyszewa, to samo piętro) = 3, z komentarzem w kodzie",
        getattr(S, "ZASIEG_ROZMOWY", None) == 3, getattr(S, "ZASIEG_ROZMOWY", None))

# --- 2. (d) zwykły przypadek: pole stania wolne, nic się nie zmienia -------------------------------------------

s, ak, sw, log = nowy((30, 12, 7), [("Frodo", (18, 11))])
blad_z(s._krok_jedzenie)
sprawdz("2a pole stania wolne: postać staje dokładnie na polu stania i kupuje raz",
        tuple(sw.p[:2]) == (20, 12) and [w[:2] for w in ak.wywolania] == [("kup", "Frodo")], (sw.p, ak.wywolania))
sprawdz("2b zwykły przypadek: jedno dojście (do pola stania), bez szukania innego pola",
        chodzenia(log) == [(20, 12, 7)], chodzenia(log))

# --- 3. (a) pole stania zajęte, NPC w zasięgu z obecnego miejsca: rozmowa od razu, bez czekania 150 s ----------

s, ak, sw, log = nowy((20, 11, 7), [("Frodo", (18, 11)), ("Obcy", (20, 12))])
blad_z(s._krok_jedzenie)
sprawdz("3a pole stania zajęte przez gracza, Frodo 2 pola dalej: kupuje z obecnego miejsca", [w[:3] for w in ak.wywolania] == [("kup", "Frodo", (20, 11, 7))], ak.wywolania)
sprawdz("3b bez czekania pełnych 150 s (czas wirtualny < 20 s)", ZEGAR.t - 1000.0 < 20.0, round(ZEGAR.t - 1000.0, 1))
sprawdz("3c nie wchodzi na pole stania i nie szuka innego pola (stoi tam, gdzie stał)", tuple(sw.p[:2]) == (20, 11) and sw.kroki == 0, sw.p)
sprawdz("3d w logu jest powód i odwołanie do zasięgu", "zasięg" in teksty(log) or "zasieg" in teksty(log), teksty(log))

# pole stania zablokowane po dwóch nieudanych krokach (przebieg 2 z żywa: Down na (32358,32210) 2x bez skutku)
s, ak, sw, log = nowy((20, 11, 7), [("Frodo", (18, 11))], slepe=[(20, 12)])
blad_z(s._krok_jedzenie)
sprawdz("3e pole stania nie do wejścia (kroki bez skutku, blokada pola): kupuje z miejsca, nie czeka",
        [w[:3] for w in ak.wywolania] == [("kup", "Frodo", (20, 11, 7))] and ZEGAR.t - 1000.0 < 40.0, (ak.wywolania, round(ZEGAR.t - 1000.0, 1)))

# NPC dokładnie 3 pola (granica zasięgu)
s, ak, sw, log = nowy((21, 11, 7), [("Frodo", (18, 11)), ("Obcy", (20, 12))])
blad_z(s._krok_jedzenie)
sprawdz("3f NPC w odległości 3 (granica zasięgu): rozmowa z miejsca", [w[:3] for w in ak.wywolania] == [("kup", "Frodo", (21, 11, 7))], ak.wywolania)

# --- 4. (b) NPC poza zasięgiem z obecnego miejsca, ale znany: najbliższe wolne pole w zasięgu NPC ------------

s, ak, sw, log = nowy((30, 12, 7), [("Frodo", (18, 11)), ("Obcy", (20, 12))])
blad_z(s._krok_jedzenie)
poz_kupna = ak.wywolania[0][2] if ak.wywolania else None
sprawdz("4a pole stania zajęte, NPC daleko: idzie na inne wolne pole w zasięgu NPC i tam rozmawia",
        poz_kupna and poz_kupna[:2] != (20, 12) and cheb(poz_kupna, (18, 11, 7)) <= S.ZASIEG_ROZMOWY and poz_kupna[2] == 7, ak.wywolania)
sprawdz("4b pole jest najbliższe postaci (z preferencją pól blisko NPC): (20,11) albo (20,13), nie daleki róg",
        poz_kupna and poz_kupna[:2] in ((20, 11), (20, 13)), poz_kupna)
sprawdz("4c czas krótki: bez czekania 150 s na zajęte pole", ZEGAR.t - 1000.0 < 60.0, round(ZEGAR.t - 1000.0, 1))

# kandydat nie może być polem zajętym ani polem NPC; brak drogi do pierwszego kandydata -> następny
s, ak, sw, log = nowy((30, 12, 7), [("Frodo", (18, 11)), ("Obcy", (20, 12)), ("Obcy2", (20, 11))],
                      planer=Planer0(brak=[(20, 13, 7)]))
blad_z(s._krok_jedzenie)
poz_kupna = ak.wywolania[0][2] if ak.wywolania else None
sprawdz("4d zajęte pola i pola bez drogi są pomijane (żaden nie jest kandydatem)",
        poz_kupna and poz_kupna[:2] not in ((20, 12), (20, 11), (20, 13), (18, 11)) and cheb(poz_kupna, (18, 11, 7)) <= 3, poz_kupna)

# NPC widoczny tylko z dala (poza widokiem): lista stworów go nie ma; bierzemy pozycję z danych (npc_poz)
s, ak, sw, log = nowy((35, 12, 7), [("Obcy", (20, 12))])
blad_z(s._krok_jedzenie)
poz_kupna = ak.wywolania[0][2] if ak.wywolania else None
sprawdz("4e NPC niewidoczny z daleka, pole stania zajęte: pozycja NPC z danych (npc_poz), pole w jego zasięgu",
        poz_kupna and cheb(poz_kupna, (18, 11, 7)) <= 3 and poz_kupna[:2] != (20, 12), ak.wywolania)

# --- 5. (c) NPC nie odpowiada na hi i odszedł: jedna ponowna próba, potem błąd --------------------------------

s, ak, sw, log = nowy((20, 12, 7), [("Frodo", (18, 11))], brak_hi=1, npc_po_hi=(26, 12))
blad_z(s._krok_jedzenie)
sprawdz("5a Frodo odszedł (nie odpowiada na hi, jest 6 pól dalej): podchodzi i rozmawia drugi raz",
        len(ak.wywolania) == 2 and ak.wywolania[1][2] is not None and cheb(ak.wywolania[1][2], (26, 12, 7)) <= 3, ak.wywolania)
sprawdz("5b druga rozmowa z innego pola niż pierwsza", len(ak.wywolania) > 1 and ak.wywolania[0][2] != ak.wywolania[1][2], ak.wywolania)

s, ak, sw, log = nowy((20, 12, 7), [("Frodo", (18, 11))], brak_hi=5, npc_po_hi=(26, 12))
e = blad_z(s._krok_jedzenie)
sprawdz("5c NPC dalej nie odpowiada: dokładnie jedna ponowna próba (2 rozmowy), potem SerwisBlad, bez pętli",
        e and len(ak.wywolania) == 2 and "nie odpowiada na hi" in e.powod, (e, ak.wywolania))

s, ak, sw, log = nowy((20, 12, 7), [("Frodo", (18, 11))], brak_hi=5)
e = blad_z(s._krok_jedzenie)
sprawdz("5d Frodo stoi na miejscu w zasięgu i nie odpowiada: bez ponowienia, błąd jak dotąd (1 rozmowa)",
        e and len(ak.wywolania) == 1 and "nie odpowiada na hi" in e.powod, (e, ak.wywolania))

s, ak, sw, log = nowy((20, 12, 7), [], brak_hi=5)
e = blad_z(s._krok_jedzenie)
sprawdz("5e NPC niewidoczny i brak odpowiedzi: błąd jak dotąd (1 rozmowa), bez szukania po danych",
        e and len(ak.wywolania) == 1 and "nie odpowiada na hi" in e.powod, (e, ak.wywolania))

s, ak, sw, log = nowy((20, 12, 7), [("Frodo", (18, 11))], brak_hi=1, npc_po_hi=(26, 12))
s.akcje.nick = "Ja"
s._krok_bank = S.Serwis._krok_bank.__get__(s)
s.d["przystanki"]["bank"]["npc"] = "Frodo"
blad_z(s._krok_bank)
sprawdz("5f to samo dla kroku bank (bank_zmien): ponowna próba po podejściu", [w[0] for w in ak.wywolania] == ["bank", "bank"], ak.wywolania)

# --- 6. (e) NPC w ogóle niewidoczny: zachowanie jak dotąd ---------------------------------------------------------

s, ak, sw, log = nowy((30, 12, 7), [("Obcy", (20, 12))], z_npc_poz=False, chodz=lambda p, t=0: False)
e = blad_z(s._krok_jedzenie)
sprawdz("6a NPC niewidoczny i bez npc_poz w danych, marsz do pola stania zawiódł: SerwisBlad z czytelnym powodem (kroki, cel)",
        e and "nie doszedłem" in e.powod and not ak.wywolania, (e, ak.wywolania))

s, ak, sw, log = nowy((30, 12, 7), [("Obcy", (20, 12))], z_npc_poz=False)
t0 = ZEGAR.t
s.planer = Planer0()
e = blad_z(s._krok_jedzenie)
sprawdz("6b NPC niewidoczny, pole stania zajęte, nie wiadomo gdzie NPC: czeka jak dotąd (do limitu marszu) i kończy porażką",
        e is not None and ZEGAR.t - t0 >= 100.0 and not ak.wywolania, (e, round(ZEGAR.t - t0, 1)))

s, ak, sw, log = nowy((21, 12, 7), [("Obcy", (20, 12))], z_npc_poz=True)
t0 = ZEGAR.t
e = blad_z(s._krok_jedzenie)
sprawdz("6c NPC niewidoczny z bliska (w widoku, a go nie ma): nie zgadujemy z danych, czeka/kończy jak dotąd",
        e is not None and ZEGAR.t - t0 >= 100.0 and not ak.wywolania, (e, round(ZEGAR.t - t0, 1)))

# --- 7. nie połykamy innych porażek ------------------------------------------------------------------------

def chodz_drzwi(punkty, tol=0):
    raise SerwisBlad("drzwi", "drzwi się nie otworzyły")


s, ak, sw, log = nowy((20, 11, 7), [("Frodo", (18, 11))], chodz=chodz_drzwi)
e = blad_z(s._krok_jedzenie)
sprawdz("7a porażka drzwi (inna niż marsz) nie jest zamieniana w rozmowę z miejsca", e and e.krok == "drzwi" and not ak.wywolania, (e, ak.wywolania))


def chodz_zatrzymany(punkty, tol=0):
    raise RuntimeError("STOP")


s, ak, sw, log = nowy((20, 11, 7), [("Frodo", (18, 11))], chodz=chodz_zatrzymany)
try:
    s._krok_jedzenie()
    zlapano = False
except RuntimeError:
    zlapano = True
sprawdz("7b wyjątek spoza SerwisBlad (np. STOP) przechodzi bez zmian", zlapano and not ak.wywolania)

# marsz zgłasza porażkę (utknięcie), NPC w zasięgu: rozmowa z miejsca; NPC poza zasięgiem i brak kandydata: oryginalny błąd


def chodz_utknal(punkty, tol=0):
    raise SerwisBlad("marsz", "6 nieudanych kroków z rzędu (stoję w (20, 11), cel (20, 12))")


s, ak, sw, log = nowy((20, 11, 7), [("Frodo", (18, 11))], chodz=chodz_utknal)
blad_z(s._krok_jedzenie)
sprawdz("7c marsz utknął 1 pole od pola stania, NPC w zasięgu: rozmowa z miejsca", len(ak.wywolania) == 1 and ak.wywolania[0][2] == (20, 11, 7), ak.wywolania)

s, ak, sw, log = nowy((30, 12, 7), [("Frodo", (18, 11))], chodz=chodz_utknal,
                      planer=Planer0(brak=[(x, y, 7) for x in range(10, 30) for y in range(0, 30) if (x, y) != (20, 12)]))
e = blad_z(s._krok_jedzenie)
sprawdz("7d NPC znany, ale do żadnego pola w jego zasięgu nie ma drogi: oryginalny błąd marszu, nic nie kupione",
        e and e.krok == "marsz" and not ak.wywolania, (e, ak.wywolania))

# --- 8. idz_pewnie: skrót „zajęte pole stania” tylko przy aktywnym haku, haki nie wyciekają ------------------------

def idz(swiat, cel, akcje, hak=None, tol=0, maks_s=150.0):
    ZEGAR.t = 1000.0
    stan, logi = {}, []
    cel = tuple(cel)
    if hak is None or not hasattr(S, "dosc_marszu"):
        r = S.idz_pewnie(swiat, MapaOtwarta(), akcje, cel, tol, maks_s=maks_s, log=logi.append, stan=stan)
    else:
        with S.dosc_marszu(cel, hak):
            r = S.idz_pewnie(swiat, MapaOtwarta(), akcje, cel, tol, maks_s=maks_s, log=logi.append, stan=stan)
    return r, logi, stan


akc = Akcje([("Frodo", (18, 11)), ("Obcy", (20, 12))])
r, logi, st = idz(Swiat((20, 11, 7)), (20, 12, 7), akc, hak=lambda poz: True)
sprawdz("8a zajęte pole stania + hak „w zasięgu”: True od razu (zero kroków, < 5 s wirtualnych)", r is True and ZEGAR.t - 1000.0 < 5.0, (r, ZEGAR.t - 1000.0))
r, logi, st = idz(Swiat((30, 12, 7)), (20, 12, 7), akc, hak=lambda poz: False)
sprawdz("8b zajęte pole stania + hak „poza zasięgiem”: False od razu, powód w stan[utkniecie] (SerwisBlad w marsz)",
        r is False and ZEGAR.t - 1000.0 < 5.0 and st.get("utkniecie"), (r, st, ZEGAR.t - 1000.0))
r, logi, st = idz(Swiat((30, 12, 7)), (20, 12, 7), akc, hak=lambda poz: None, maks_s=40.0)
sprawdz("8c zajęte pole stania + hak „nie wiem” (NPC niewidoczny): czeka do limitu jak dotąd", r is False and ZEGAR.t - 1000.0 >= 39.0, (r, ZEGAR.t - 1000.0))
r, logi, st = idz(Swiat((30, 12, 7)), (20, 12, 7), akc, maks_s=40.0)
sprawdz("8d bez haka (inne użycia idz_pewnie): czeka do limitu jak dotąd", r is False and ZEGAR.t - 1000.0 >= 39.0 and not st.get("utkniecie"), (r, st))
ZEGAR.t = 1000.0
akc2 = Akcje([("Obcy", (15, 15))])
import contextlib
with (S.dosc_marszu((20, 12, 7), lambda poz: True) if hasattr(S, "dosc_marszu") else contextlib.nullcontext()):
    r3 = S.idz_pewnie(Swiat((30, 12, 7)), MapaOtwarta(), akc2, (15, 15, 7), 0, maks_s=40.0, log=lambda *_: None, stan={})
sprawdz("8e hak z innym celem nie skraca czekania na zajęte pole (czeka do limitu)", r3 is False and ZEGAR.t - 1000.0 >= 39.0, (r3, ZEGAR.t - 1000.0))
sprawdz("8f po wyjściu z kontekstu hak jest zdjęty (brak wycieku do kolejnych marszów)", not getattr(S, "_DOSC", {}).get("fn") and hasattr(S, "_DOSC"), getattr(S, "_DOSC", None))

# --- 9. rozmowa: porażka „nie odpowiada na hi” ma osobny typ (wyjątek podklasa SerwisBlad) ------------------------

BO = getattr(A, "BrakOdpowiedziNpc", None)
sprawdz("9a A.BrakOdpowiedziNpc to SerwisBlad z krokiem „rozmowa” (stare łapanie SerwisBlad dalej działa)",
        BO is not None and issubclass(BO, SerwisBlad) and BO("rozmowa", "x").krok == "rozmowa")


class CzatBezOdpowiedzi:
    def __init__(self):
        self.t, self.wyslane = 0.0, []

    def czas(self):
        return self.t

    def spij(self, s):
        self.t += s

    def czat(self, tekst):
        self.wyslane.append(tekst)

    def wiadomosci(self):
        return []


cz = CzatBezOdpowiedzi()
roz = A.Rozmowa(cz.czat, cz.wiadomosci, "Ja", log=lambda *_: None, czas=cz.czas, spij=cz.spij, pomin_zakladki=True)
roz.powiedz = lambda tekst, czekaj_echo_s=4.0: cz.wyslane.append(tekst)           # echo czatu nie jest tu przedmiotem testu
e = blad_z(lambda: roz.powitaj("Frodo"))
sprawdz("9b powitaj bez odpowiedzi: BrakOdpowiedziNpc (3 próby hi, jak dotąd)",
        BO is not None and isinstance(e, BO) and cz.wyslane == ["hi", "hi", "hi"], (type(e), cz.wyslane))

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
