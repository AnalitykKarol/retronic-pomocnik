"""24.10: cap postaci przy serwisie (invincible/gebelish/dawajkesh kupili tyle ham, że po wyprawie zabrakło miejsca na łup;
odchyd wracał po cap z 0 ham). Zakres: rezerwa capa na łup przy zakupie ham, minimum ham gdy brak jedzenia, krok wirtualny `cap`
(korekta Karola 24.10: ham NIE idzie do depo; opcjonalnie ciężki łup-sprzęt, domyślnie wyłączone), pokrętła SERWIS_* (0 = dawne zachowanie), akcje depo_nadmiar/stan_cap na symulacji.
Bez gry: RETRONIC_TESTY=1, atrapy akcji, symulacja kontenerów jak w test_serwis_akcje."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import pokretla
import serwis as S
import serwis_akcje as A
from serwis_blad import SerwisBlad

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


DANE = json.load(open(KAT / "trasy" / "serwis_edron.json"))
HAM, PLAT, BAG = 3582, 3035, 2869
ZBROJA, TARCZA = 1001, 1002                       # sztuczne ID łupu-sprzętu w testach (wagi 60 i 40 oz)
WAGI = {ZBROJA: 60.0, TARCZA: 40.0}
A.SKUTEK_CZEKAJ_S = 0

# --- 1. plan_nadmiaru (czysta funkcja) --------------------------------------------------------------------------------

sprawdz("1a cap już >= cel: nic do odłożenia", A.plan_nadmiaru(80, 50, [{"slot": 0, "id": ZBROJA}], WAGI) == [])
sprawdz("1b cel 0 (pokrętło wyłączone): nic", A.plan_nadmiaru(0, 0, [{"slot": 0, "id": ZBROJA}], WAGI) == [])
sprawdz("1c brakuje 49 oz: jedna sztuka najcięższego łupu (60 oz)", A.plan_nadmiaru(1, 50, [{"slot": 0, "id": TARCZA}, {"slot": 1, "id": ZBROJA}], WAGI) == [ZBROJA])
sprawdz("1d deficyt 100 oz: zbroja 60 + tarcza 40", A.plan_nadmiaru(0, 100, [{"slot": 0, "id": TARCZA}, {"slot": 1, "id": ZBROJA}], WAGI) == [ZBROJA, TARCZA])
sprawdz("1e ham NIE jest planowany do depo: przy samym hamie plan pusty",
        A.plan_nadmiaru(0, 100, [{"slot": 0, "id": HAM, "ilosc": 5}], WAGI) == [])
sprawdz("1g przedmioty spoza listy wag (ham, platinum, runy) nie są łupem",
        A.plan_nadmiaru(0, 50, [{"slot": 0, "id": HAM, "ilosc": 3}, {"slot": 1, "id": PLAT, "ilosc": 9}], WAGI) == [])
sprawdz("1h maks. sztuk łupu ogranicza składanie", len(A.plan_nadmiaru(0, 1000, [{"slot": i, "id": TARCZA} for i in range(9)], WAGI, maks_sztuk=4)) == 4)
sprawdz("1i stos łupu liczony per sztuka", A.plan_nadmiaru(0, 70, [{"slot": 0, "id": TARCZA, "ilosc": 2}], WAGI) == [TARCZA, TARCZA])
A._SPRZET_WAGI = None
rzecz = A.wagi_sprzetu()
sprawdz("1j prawdziwy przedmioty.json: są wagi, wszystkie >= próg, bez chronionych tarcz (UH/steel shield)",
        len(rzecz) > 20 and all(w >= A.SPRZET_MIN_WAGA_OZ for w in rzecz.values()) and not (set(rzecz) & A.SPRZET_CHRONIONE), len(rzecz))
sprawdz("1j2 ham (3582), platinum, blank rune nie są w wagach sprzętu", not ({HAM, PLAT, 3147} & set(rzecz)))
A._SPRZET_WAGI = dict(WAGI)          # dalej deterministyczne wagi

# --- 2. pokrętła ---------------------------------------------------------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "na_zywo.json"
    sprawdz("2a brak pliku: domyślne 50/2/0 (łup do depo wyłączony do potwierdzenia Karola)", S.pokretla_serwisu(p) == {"cap_na_loot": 50, "ham_min": 2, "cap_depo_loot": 0}, S.pokretla_serwisu(p))
    p.write_text(json.dumps({"SERWIS_CAP_NA_LOOT": 0, "SERWIS_HAM_MIN": 0}))
    r = S.pokretla_serwisu(p)
    sprawdz("2b 0 w pliku = 0 (dawne zachowanie), reszta domyślna", r["cap_na_loot"] == 0 and r["ham_min"] == 0 and r["cap_depo_loot"] == 0, r)
    p.write_text(json.dumps({"SERWIS_CAP_NA_LOOT": "abc", "SERWIS_HAM_MIN": None, "SERWIS_CAP_DEPO_LOOT": -4}))
    r = S.pokretla_serwisu(p)
    sprawdz("2c śmieć w polu = domyślna, ujemne = 0", r == {"cap_na_loot": 50, "ham_min": 2, "cap_depo_loot": 0}, r)
    p.write_text("{nie json")
    sprawdz("2d uszkodzony plik = domyślne, bez wyjątku", S.pokretla_serwisu(p)["cap_na_loot"] == 50)
sprawdz("2e domyślne konstruktora Serwis = dawne zachowanie (wszystko 0)",
        all(v == 0 for v in S._CELE_STARE.values()) and set(S._CELE_STARE) == set(S._KLUCZE_CELE.values()))
sprawdz("2f pokrętła w ZAKRESY, zgodne z domyślnymi serwisu i z przykładem",
        all(k in pokretla.ZAKRESY and pokretla.ZAKRESY[k][0] <= S.POKRETLA_SERWISU[k] <= pokretla.ZAKRESY[k][1] for k in S.POKRETLA_SERWISU)
        and all(json.load(open(KAT / "na_zywo.przyklad.json")).get(k) == v for k, v in S.POKRETLA_SERWISU.items()))
ok_w, bledy_w = pokretla.waliduj({"SERWIS_CAP_NA_LOOT": 50, "SERWIS_HAM_MIN": 9})
sprawdz("2g waliduj: zakres egzekwowany (HAM_MIN 9 poza 0-5)", ok_w == {"SERWIS_CAP_NA_LOOT": 50} and len(bledy_w) == 1, (ok_w, bledy_w))
logi = []
modul = types.SimpleNamespace()
pk = pokretla.Pokretla(modul, plik=Path("/nieistnieje/na_zywo.json"), log=logi.append)
pk.zastosuj({"SERWIS_CAP_NA_LOOT": 70})
sprawdz("2h Pokretla.zastosuj pomija klucze serwisu bez logu o braku stałej i bez ustawiania ich w cavebocie",
        not logi and not hasattr(modul, "SERWIS_CAP_NA_LOOT") and "SERWIS_CAP_NA_LOOT" not in pk.aktywne, (logi, pk.aktywne))

# --- 3. orkiestrator na atrapie ------------------------------------------------------------------------------------------


class Atrapa:
    """Atrapa akcji ze stanem capa: ham waży 20 oz, łup z WAGI; kup/depo_nadmiar zmieniają stan."""

    def __init__(self, cap=200.0, ham=0, przedmioty=(), blanki_rezerwa=42.0):
        self.log, self.poz = [], [0, 0, 7]
        self.cap, self.ham, self.przedm, self.rez_blanki = cap, ham, [dict(q) for q in przedmioty], blanki_rezerwa
        self.rezerwy = []

    def sprawdz_start(self): self.log.append("start")
    def przygotuj_okna(self): self.log.append("okna")
    def majatek(self, tylko_glowny=False): return 100000
    def wolne_w_bagu(self): return 20
    def brakuje(self, co, cel): return max(0, cel - (self.ham if co == "ham" else 0))
    def bank_zmien(self, npc): self.log.append(("bank", npc))
    def pole_zajete(self, pole): return False
    def potrzeba_baga(self): return False
    def przenies_blanki(self): self.log.append("przenies_blanki")
    def depo_zloz(self, zostaw_platinum, odejdz=None): self.log.append(("depo", zostaw_platinum)); return True
    def rezerwa_na_blanki(self, blanki): return self.rez_blanki

    def cel_ham(self, cel, rezerwa_oz):
        self.rezerwy.append(rezerwa_oz)
        return self.ham + max(0, min(cel - self.ham, int((self.cap - rezerwa_oz) // 20)))

    def kup(self, npc, co, ile):
        self.log.append(("kup", npc, co, ile))
        if co == "ham":
            self.cap -= 20 * max(0, ile - self.ham)
            self.ham = max(self.ham, ile)

    def stan_cap(self):
        return self.cap, self.ham, [dict(q) for q in self.przedm]

    def depo_nadmiar(self, loot=(), odejdz=None):
        self.log.append(("nadmiar", tuple(loot)))
        for i in loot:
            q = next(q for q in self.przedm if q["id"] == i)
            self.przedm.remove(q)
            self.cap += WAGI[i]
        return True


class Planer0:
    def droga(self, od, do):
        return [tuple(od), tuple(do)]


def zbuduj(akcje, cele=None, start=(0, 0, 7), dane=DANE):
    stoi = {"poz": tuple(start)}

    def chodz(punkty, tol=0):
        stoi["poz"] = punkty[-1]
        akcje.poz = list(stoi["poz"])
        return True

    return S.Serwis(dane, akcje, Planer0(), lambda: stoi["poz"], chodz, log=lambda *_: None, cele=cele), stoi


def kupna(a):
    return [x for x in a.log if isinstance(x, tuple) and x[0] == "kup"]


# 3a. invincible 24.10: 139 oz wolne, bag z blankami 42 oz. Dawniej cel 4 ham (zostaje 17 oz), teraz rezerwa na łup 50 oz.
a = Atrapa(cap=139.0)
s, _ = zbuduj(a, cele={"cap_na_loot": 50})
s.uruchom(["jedzenie", "blanki"])
sprawdz("3a rezerwa łupu doliczona do rezerwy bagu z blankami (42 + 50 = 92 oz): kupuje 2 ham, nie 4",
        a.rezerwy == [92.0] and ("kup", "Mirabell", "ham", 2) in a.log, (a.rezerwy, a.log))
a = Atrapa(cap=139.0)
s, _ = zbuduj(a)
s.uruchom(["jedzenie", "blanki"])
sprawdz("3b pokrętła 0 (domyślne Serwis): rezerwa 42 oz jak dotąd, 4 ham", a.rezerwy == [42.0] and ("kup", "Mirabell", "ham", 4) in a.log, (a.rezerwy, a.log))
a = Atrapa(cap=300.0)
s, _ = zbuduj(a, cele={"cap_na_loot": 50})
s.uruchom(["jedzenie"])
sprawdz("3c sam krok jedzenie (bez blanków): rezerwa tylko łup (50 oz), cap wystarcza: 5 ham", a.rezerwy == [50] and ("kup", "Mirabell", "ham", 5) in a.log, (a.rezerwy, a.log))
a = Atrapa(cap=300.0)
s, _ = zbuduj(a)
s.uruchom(["jedzenie"])
sprawdz("3d pokrętła 0: jedzenie bez cel_ham, 5 ham (jak 5e3)", a.rezerwy == [] and ("kup", "Mirabell", "ham", 5) in a.log, (a.rezerwy, a.log))
# 3e. rezerwa każe 0 ham, postać bez jedzenia: minimum ograniczone realnym capem
a = Atrapa(cap=60.0, ham=0)
s, _ = zbuduj(a, cele={"cap_na_loot": 50, "ham_min": 2})
s.uruchom(["jedzenie"])
sprawdz("3e cap 60 oz, rezerwa 50: rezerwa pozwala 0 ham, ale ham_min=2 kupuje 2 (cap pozwala na 3)", ("kup", "Mirabell", "ham", 2) in a.log, a.log)
a = Atrapa(cap=30.0, ham=0)
s, _ = zbuduj(a, cele={"cap_na_loot": 50, "ham_min": 2})
s.uruchom(["jedzenie"])
sprawdz("3f cap 30 oz: minimum ograniczone capem (1 ham = 20 oz), nie 2", ("kup", "Mirabell", "ham", 1) in a.log, a.log)
a = Atrapa(cap=30.0, ham=0)
s, _ = zbuduj(a, cele={"cap_na_loot": 50, "ham_min": 0})
s.uruchom(["jedzenie"])
sprawdz("3g ham_min=0: rezerwa wygrywa, kupuje 0 (stare zachowanie przy rezerwie)", ("kup", "Mirabell", "ham", 0) in a.log, a.log)
a = Atrapa(cap=300.0, ham=4)
s, _ = zbuduj(a, cele={"cap_na_loot": 50, "ham_min": 2})
s.uruchom(["jedzenie"])
sprawdz("3h ham_min nie zwiększa zakupu ponad cel (ma 4, cel 5): 5", ("kup", "Mirabell", "ham", 5) in a.log, a.log)

# 3i. krok `cap` (korekta Karola: ham NIE idzie do depo; ciężki łup-sprzęt tylko za pokrętłem, domyślnie wyłączonym)
CELE = {"cap_na_loot": 50, "ham_min": 2, "cap_depo_loot": 0}
CELE_LOOT = {**CELE, "cap_depo_loot": 1}
LOOT = [{"slot": 0, "id": ZBROJA}, {"slot": 1, "id": TARCZA}, {"slot": 2, "id": PLAT, "ilosc": 5}]


def tup(a):
    return [x for x in a.log if isinstance(x, tuple)]


a = Atrapa(cap=0.0, ham=5, przedmioty=LOOT)
s, st = zbuduj(a, cele=CELE)
wynik = s.uruchom(["bank", "cap", "wyjscie"])
sprawdz("3i invincible: cap 0, 5 ham, domyślnie: krok cap NIE odkłada ham ani łupu i niczego nie kupuje (ma 5 >= minimum 2); wyjście na końcu",
        tup(a) == [("bank", "Ebenizer")] and a.ham == 5 and st["poz"] == tuple(DANE["wyjscie"]), (a.log, st))
sprawdz("3j wynik uruchom: cap zaliczony, bez błędu nieznanego kroku", wynik.get("cap") == "ok" and wynik.get("bank") == "ok", wynik)
sprawdz("3j2 ham zostaje w plecaku (5), cap bez zmian (0): jedzenie zjada/wyrzuca wyprawa.py na łowisku", a.ham == 5 and a.cap == 0.0, (a.ham, a.cap))
sprawdz("3j3 żaden wywołany depo_nadmiar z hamem: brak argumentu ile_ham w API", "ile_ham" not in A.AkcjeZywe.depo_nadmiar.__code__.co_varnames)

a = Atrapa(cap=0.0, ham=5, przedmioty=LOOT)
s, st = zbuduj(a, cele=CELE_LOOT)
s.uruchom(["bank", "cap", "wyjscie"])
sprawdz("3i2 SERWIS_CAP_DEPO_LOOT=1: odkłada najcięższy łup (zbroja 60 oz >= 50), ham zostaje",
        tup(a) == [("bank", "Ebenizer"), ("nadmiar", (ZBROJA,))] and a.ham == 5 and a.cap == 60.0, (a.log, a.cap))

a = Atrapa(cap=120.0, ham=3, przedmioty=LOOT)
s, _ = zbuduj(a, cele=CELE_LOOT)
s.uruchom(["bank", "cap", "wyjscie"])
sprawdz("3k cap 120 >= 50 i ham 3 >= 2: krok cap nic nie robi", tup(a) == [("bank", "Ebenizer")], a.log)

# odchyd: 0 ham, cap 9, dwa ciężkie przedmioty
a = Atrapa(cap=9.0, ham=0, przedmioty=LOOT)
s, _ = zbuduj(a, cele=CELE_LOOT)
s.uruchom(["bank", "cap", "wyjscie"])
sprawdz("3l odchyd (łup włączony): 0 ham, cap 9: odkłada najcięższy łup (60 oz), potem kupuje minimum 2 ham",
        tup(a) == [("bank", "Ebenizer"), ("nadmiar", (ZBROJA,)), ("kup", "Mirabell", "ham", 2)], a.log)
a = Atrapa(cap=69.0, ham=0, przedmioty=LOOT)
s, _ = zbuduj(a, cele=CELE)
s.uruchom(["bank", "cap", "wyjscie"])
sprawdz("3l2 odchyd (domyślnie bez łupu): 0 ham, cap 69: kupuje minimum 2 ham, nic nie odkłada",
        tup(a) == [("bank", "Ebenizer"), ("kup", "Mirabell", "ham", 2)], a.log)

# 0 ham, cap wysoki: tylko zakup
a = Atrapa(cap=150.0, ham=0, przedmioty=[])
s, _ = zbuduj(a, cele=CELE)
s.uruchom(["bank", "cap", "wyjscie"])
sprawdz("3m 0 ham, cap 150, nic do odłożenia: bez depo, kupuje 2 ham", tup(a) == [("bank", "Ebenizer"), ("kup", "Mirabell", "ham", 2)], a.log)

# 0 ham i brak capa na jedzenie: nie kupuje
a = Atrapa(cap=0.0, ham=0, przedmioty=[{"slot": 0, "id": PLAT, "ilosc": 5}])
s, _ = zbuduj(a, cele=CELE)
s.uruchom(["bank", "cap", "wyjscie"])
sprawdz("3n cap 0, nic do odłożenia: nie kupuje (cap nie pozwala), serwis nie pada", kupna(a) == [], a.log)

# pokrętła 0 (domyślne Serwis): krok cap nic nie robi
a = Atrapa(cap=0.0, ham=5, przedmioty=LOOT)
s, st = zbuduj(a)
s.uruchom(["bank", "cap", "wyjscie"])
sprawdz("3q pokrętła 0: krok cap wyłączony = dawne bank+wyjście", tup(a) == [("bank", "Ebenizer")]
        and st["poz"] == tuple(DANE["wyjscie"]), a.log)

# krok cap w mieście bez depo: pomija odkładanie, nie pada
dane_bez = {**DANE, "przystanki": {k: v for k, v in DANE["przystanki"].items() if k != "depo"}}
a = Atrapa(cap=0.0, ham=5, przedmioty=LOOT)
s, _ = zbuduj(a, cele=CELE_LOOT, dane=dane_bez)
s.uruchom(["bank", "cap", "wyjscie"])
sprawdz("3r miasto bez kroku depo: cap nie odkłada (log), serwis nie pada", not any(isinstance(x, tuple) and x[0] == "nadmiar" for x in a.log), a.log)

# atrapa bez stan_cap (stare atrapy testów): krok cap nic nie robi
class Stara(Atrapa):
    stan_cap = None


a = Stara()
s, _ = zbuduj(a, cele=CELE)
s.uruchom(["bank", "cap", "wyjscie"])
sprawdz("3s akcje bez stan_cap: krok cap pomija", tup(a) == [("bank", "Ebenizer")], a.log)

# plan na sucho i koszt
a = Atrapa()
s, _ = zbuduj(a, cele=CELE)
pl = s.plan(["bank", "cap", "wyjscie"])
sprawdz("3t plan na sucho zna krok cap (dojście do depo)", [k for k, _c, _n in pl] == ["bank", "cap", "wyjscie"] and all(n is not None for _k, _c, n in pl), pl)
sprawdz("3u koszt kroku cap = minimum jedzenia (2 ham x 10 gp), nie 0", s._koszt(["bank", "cap"]) == 20, s._koszt(["bank", "cap"]))
sprawdz("3v koszt bez pokrętła = 0 (jak dotąd)", zbuduj(Atrapa())[0]._koszt(["bank", "cap"]) == 0)
e = zglasza(lambda: zbuduj(Atrapa(), cele=CELE)[0].uruchom(["bank", "nieistniejacy"]))
sprawdz("3w nieznany krok nadal jest błędem startu", e and "nieznane kroki" in e.powod, e)

# --- 4. akcje na symulacji kontenerów (depo_nadmiar, stan_cap, cel_ham) -----------------------------------------------------


class Slot:
    def __init__(self, i):
        self.srodek = (100 + 37 * (i % 4), 100 + 37 * (i // 4))


class Okno:
    def __init__(self, widoczne, gora):
        self.sloty = [Slot(i) for i in range(widoczne)]
        self.gora, self.lewo, self.prawo = gora, 760, 936


class Symulacja:
    def __init__(self, glowny, depo=None, widoczne=20):
        self.kon = {0: {"nazwa": "backpack", "poj": 20, "widoczne": widoczne, "p": [dict(x) for x in glowny]}}
        if depo is not None:
            self.kon[1] = {"nazwa": "depot chest", "poj": 30, "widoczne": 16, "p": [dict(x) for x in depo]}
        self.oczekuje, self.spada, self.zamkniete = None, False, {}

    def pamiec(self):
        return [{"numer": n, "nazwa": k["nazwa"], "pojemnosc": k["poj"],
                 "przedmioty": [dict(slot=i, id=q["id"], ilosc=q["ilosc"]) for i, q in enumerate(k["p"])]}
                for n, k in sorted(self.kon.items())]

    def ile(self, ids):
        return sum(q["ilosc"] for k in self.kon.values() if k["nazwa"] not in ("locker", "depot chest") for q in k["p"] if q["id"] in ids)

    def glowny(self):
        return next(k for k in self.kon.values() if k["nazwa"] in ("backpack", "bag"))

    def depo(self):
        return next(k for k in list(self.kon.values()) + list(self.zamkniete.values()) if k["nazwa"] == "depot chest")


class MyszAtrapa:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def klik(self, *a, **k): pass
    def przeciagnij(self, *a, **k): pass


class Testowe(A.AkcjeZywe):
    def __init__(self, sym, cap=200.0):
        self.sym, self.log, self.nick = sym, (lambda *_: None), "Test"
        self.sprawdz_bota = False
        self.postac = types.SimpleNamespace(pozycja=lambda: (33170, 31813, 7))
        self._gracz_dane = {"hp": 240, "max_hp": 240, "cap": cap}
        self._bot = types.SimpleNamespace(Zatrzymano=RuntimeError, _zapytaj_surowe=self._zapytaj)
        self.zamkniete, self.depo_otwarte, self.mysz = [], True, MyszAtrapa()

    def _zapytaj(self, z):
        if z["cmd"] == "kontenery":
            return {"ekwipunek": None}
        return {"gracz": self._gracz_dane} if z["cmd"] == "gracz" else {"stwory": []}

    def kontenery(self): return self.sym.pamiec()
    def ilosc(self, ids, bez=("locker", "depot chest")): return self.sym.ile(ids)
    def _mysz(self): return self.mysz
    def _zrzut(self, mysz): return None

    def _zamknij(self, numer):
        self.zamkniete.append(numer)
        k = self.sym.kon.pop(numer, None)
        if k is not None:
            self.sym.zamkniete[numer] = k

    def _otworz_depo(self, m): return self.depo_otwarte

    def _okna_numery(self, obraz):
        return [(Okno(k["widoczne"], 100 * i), kon) for i, ((n, k), kon) in enumerate(zip(sorted(self.sym.kon.items()), self.kontenery()))]

    def _przeciagnij(self, m, okno_z, i_z, okno_do, i_do):
        numery = sorted(self.sym.kon)
        kz, kd = self.sym.kon[numery[okno_z.gora // 100]], self.sym.kon[numery[okno_do.gora // 100]]
        przedmiot = kz["p"][i_z]
        if przedmiot["ilosc"] > 1:
            self.sym.oczekuje = (kz, kd, i_z, i_do)
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
            cel["ilosc"] += ile
        else:
            kd["p"].append({"id": przedmiot["id"], "ilosc": ile})
        return True


GL = [{"id": HAM, "ilosc": 5}, {"id": ZBROJA, "ilosc": 1}, {"id": PLAT, "ilosc": 3}]
sym = Symulacja(GL, depo=[])
a = Testowe(sym, cap=12.5)
cap, ham, przedm = a.stan_cap()
sprawdz("4a stan_cap: wolny cap, ham i przedmioty głównego plecaka ze slotami", cap == 12.5 and ham == 5 and [q["id"] for q in przedm] == [HAM, ZBROJA, PLAT]
        and przedm[1]["slot"] == 1, (cap, ham, przedm))
sprawdz("4a2 stan_cap: cap w setnych częściach oz (> 5000) przeliczony", Testowe(sym, cap=13900).stan_cap()[0] == 139.0)

sym = Symulacja(GL, depo=[])
a = Testowe(sym)
wynik = a.depo_nadmiar([ZBROJA])
sprawdz("4b depo_nadmiar: zbroja w depo, ham (5) i platinum nietknięte; depo zamknięte",
        wynik is True and sym.ile({HAM}) == 5 and sym.ile({ZBROJA}) == 0 and sym.ile({PLAT}) == 3
        and any(q["id"] == ZBROJA for q in sym.depo()["p"]) and not any(q["id"] == HAM for q in sym.depo()["p"])
        and 1 in a.zamkniete, (sym.glowny()["p"], sym.depo()["p"]))

sym = Symulacja(GL, depo=[{"id": ZBROJA, "ilosc": 2}])
Testowe(sym).depo_nadmiar([ZBROJA])
sprawdz("4c zbroja bez stosowania: trafia do depo jako osobna sztuka, ham zostaje", sym.ile({ZBROJA}) == 0 and sym.ile({HAM}) == 5, sym.depo()["p"])

sym = Symulacja(GL, depo=[])
a = Testowe(sym)
a.depo_otwarte = False
sprawdz("4d skrzynia się nie otworzyła: False, nic nie ruszone", a.depo_nadmiar([ZBROJA]) is False and sym.ile({HAM}) == 5 and sym.ile({ZBROJA}) == 1)

sym = Symulacja(GL, depo=[])
sym.spada = True
wynik_e = Testowe(sym).depo_nadmiar([ZBROJA])
sprawdz("4e zbroja spadła na podłogę: odkładanie łupu kończy się bez błędu serwisu (łup jest dodatkiem), ham nietknięty",
        wynik_e is True and sym.ile({HAM}) == 5, wynik_e)

sym = Symulacja(GL, depo=[])
Testowe(sym).depo_nadmiar([])
sprawdz("4f brak łupu: nic nie rusza", sym.ile({HAM}) == 5 and sym.ile({ZBROJA}) == 1)

# łup poza widocznym oknem plecaka (slot >= widoczne): nie rzuca błędu, ham odłożony
glowny_dlugi = [{"id": HAM, "ilosc": 5}] + [{"id": PLAT, "ilosc": 3}] + [{"id": 3198, "ilosc": 1}] * 18 + [{"id": ZBROJA, "ilosc": 1}]
sym = Symulacja(glowny_dlugi, depo=[], widoczne=20)
wynik = Testowe(sym).depo_nadmiar([ZBROJA])
sprawdz("4g łup w slocie poza oknem plecaka zostaje (bez błędu), ham nietknięty", wynik is True and sym.ile({HAM}) == 5 and sym.ile({ZBROJA}) == 1, wynik)

sym = Symulacja(GL, depo=[])
sprawdz("4h łup już zabrany przez kogoś/nieobecny: pomijany bez błędu", Testowe(sym).depo_nadmiar([9999]) is True)

# cel_ham: scenariusz z logów (invincible 11:57: 139 oz wolne, bag z blankami 42 oz)
sym = Symulacja([{"id": 3198, "ilosc": 1}], depo=None)
a = Testowe(sym, cap=139.0)
sprawdz("4i cel_ham z samą rezerwą bagu (42): 4 ham, zostaje 17 oz (przyczyna braku capa)", a.cel_ham(5, 42.0) == 4)
sprawdz("4j cel_ham z rezerwą bagu + łup (92): 2 ham, zostaje 57 oz na łup", a.cel_ham(5, 92.0) == 2)
sprawdz("4k wolne 139 oz, 5 ham = 100 oz (przypadek 12:25 invincible): po 5 ham w plecaku zostaje 39 oz BEZ bagu i blanków", 139 - 5 * A.WAGA_HAM_OZ == 39)

# --- wynik ---------------------------------------------------------------------------------------------------------------------

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
