"""27.10 (SPEC_gfb_1027.md, B): stanowisko je DOWOLNE jedzenie z bagu (banan bez hama), ham zostaje pierwszym wyborem; serwis/refill nie uznaje
braku hama za brak jedzenia, gdy w plecaku jest inne jedzenie (SERWIS_JEDZENIE_DOWOLNE, domyślnie 0 = dawne liczenie hama, tryb stoj ustawia 1).
Bez gry i bez X11 (RETRONIC_TESTY=1): atrapy okien/pamięci kontenerów i atrapa akcji serwisu."""
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
import loot
import pokretla
import serwis as S
import serwis_akcje as A

ok = []


def probuj(f, domyslna=None):
    """Wynik f() albo domyślna przy wyjątku (kod sprzed zmiany nie ma nowego API: test ma być czerwony, nie przerwany)."""
    try:
        return f()
    except Exception as e:  # noqa: BLE001
        return domyslna if domyslna is not None else repr(e)


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


HAM, BANAN, SER, MIESO, ZLOTO = 3582, 3587, 3607, 3577, 3031

# --- 1. jedzenie z bagu (loot._jedzenie_z_pamieci): dowolne jedzenie, ham pierwszy ---------------------------------------------------


class Slot:
    def __init__(self, i):
        self.srodek = (100 + 37 * (i % 4), 100 + 37 * (i // 4))


def pod_pamiec(przedmioty):
    """Podstawia okno plecaka i pamięć kontenerów z `przedmioty` [(id, ilosc)]; zwraca funkcję przywracającą."""
    okno = types.SimpleNamespace(sloty=[Slot(i) for i in range(20)], rola="plecak")
    kont = {"numer": 0, "nazwa": "backpack", "id": 2854, "pojemnosc": 20,
            "przedmioty": [{"slot": i, "id": ident, "ilosc": n} for i, (ident, n) in enumerate(przedmioty)]}
    stare = (loot.znajdz_okna, loot.kontenery_z_pamieci, loot.dopasuj_okna)
    loot.znajdz_okna = lambda obraz: [okno]
    loot.kontenery_z_pamieci = lambda: ([kont], None)
    loot.dopasuj_okna = lambda obraz, okna, kontenery: ([kont], None)

    def przywroc():
        loot.znajdz_okna, loot.kontenery_z_pamieci, loot.dopasuj_okna = stare
    return przywroc


def wybor(przedmioty):
    przywroc = pod_pamiec(przedmioty)
    try:
        return loot._jedzenie_z_pamieci(None)
    finally:
        przywroc()


w = wybor([(ZLOTO, 30), (BANAN, 4)])
sprawdz("1a plecak z samymi bananami (bez hama): jedzenie = banan", w is not None and w[2] == BANAN and w[1] == "banana", w)
w = wybor([(BANAN, 4), (HAM, 1)])
sprawdz("1b ham i banan: ham pierwszy (preferencja), mimo że banan leży wcześniej w plecaku", w is not None and w[2] == HAM, w)
w = wybor([(SER, 2), (BANAN, 4)])
sprawdz("1c ser i banan: wg KOLEJNOSC_JEDZENIA (ser przed bananem), żadne nie blokuje drugiego", w is not None and w[2] in (SER, BANAN), w)
sprawdz("1d brak jedzenia w plecaku: None", wybor([(ZLOTO, 30)]) is None)
sprawdz("1e banan jest na liście jedzenia i w przedmioty.json (typ jedzenie)", BANAN in loot.KOLEJNOSC_JEDZENIA and loot.JEDZENIE_ID["banana"] == BANAN
        and any(it.get("id_klienta") == BANAN and it.get("odzywianie") for lst in json.load(open(KAT / "dane_tibia" / "przedmioty.json"))["kategorie"].values() for it in lst))
sprawdz("1f ham pierwszym wyborem listy", loot.KOLEJNOSC_JEDZENIA[0] == HAM)

# zjedz() end-to-end na atrapie myszy: banan ubywa po Use => zjedzone ["banana"]
class Mysz:
    def __init__(self): self.kliki = []
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def lewy(self, x, y, modyfikator=None, drganie=0): self.kliki.append((x, y, modyfikator))


przedm = [[(ZLOTO, 30), (BANAN, 2)]]
okno = types.SimpleNamespace(sloty=[Slot(i) for i in range(20)], rola="plecak")
def kont():
    return {"numer": 0, "nazwa": "backpack", "id": 2854, "pojemnosc": 20,
            "przedmioty": [{"slot": i, "id": ident, "ilosc": n} for i, (ident, n) in enumerate(przedm[0])]}
mysz = Mysz()
stare = (loot.znajdz_okna, loot.kontenery_z_pamieci, loot.dopasuj_okna, loot.ekran.Mysz, loot._zrzut, loot._pauza, loot.bot.sprawdz_stop)
def lewy(x, y, modyfikator=None, drganie=0):
    mysz.kliki.append((x, y, modyfikator))
    przedm[0] = [(i, n - 1 if i == BANAN else n) for i, n in przedm[0]]
    przedm[0] = [(i, n) for i, n in przedm[0] if n > 0]
mysz.lewy = lewy
loot.znajdz_okna = lambda obraz: [okno]
loot.kontenery_z_pamieci = lambda: ([kont()], None)
loot.dopasuj_okna = lambda obraz, okna, kontenery: ([kont()], None)
loot.ekran.Mysz = lambda: mysz
loot._zrzut = lambda m: None
loot._pauza = lambda a, b=None: None
loot.bot.sprawdz_stop = lambda: None
try:
    zj = loot.zjedz(ile=1, log=lambda *a, **k: None)
finally:
    (loot.znajdz_okna, loot.kontenery_z_pamieci, loot.dopasuj_okna, loot.ekran.Mysz, loot._zrzut, loot._pauza, loot.bot.sprawdz_stop) = stare
sprawdz("1g loot.zjedz: postać z samymi bananami zjada banana (Ctrl+klik w slot banana)", zj == ["banana"] and len(mysz.kliki) == 1 and mysz.kliki[0][2] == "Control_L", (zj, mysz.kliki))

# --- 2. serwis: liczenie jedzenia ----------------------------------------------------------------------------------------------------


class Symulacja:
    def __init__(self, glowny, widoczne=20):
        self.p = [dict(x) for x in glowny]

    def pamiec(self):
        return [{"numer": 0, "nazwa": "backpack", "pojemnosc": 20,
                 "przedmioty": [dict(slot=i, id=q["id"], ilosc=q["ilosc"]) for i, q in enumerate(self.p)]}]

    def ile(self, ids):
        return sum(q["ilosc"] for q in self.p if q["id"] in ids)


class Testowe(A.AkcjeZywe):
    def __init__(self, sym, cap=200.0):
        self.sym, self.log, self.nick = sym, (lambda *_: None), "Test"
        self.sprawdz_bota = False
        self._gracz_dane = {"hp": 240, "max_hp": 240, "cap": cap}
        self._bot = types.SimpleNamespace(Zatrzymano=RuntimeError, _zapytaj_surowe=self._zapytaj)

    def _zapytaj(self, z):
        if z["cmd"] == "kontenery":
            return {"ekwipunek": None}
        return {"gracz": self._gracz_dane}

    def kontenery(self): return self.sym.pamiec()
    def ilosc(self, ids, bez=("locker", "depot chest")): return self.sym.ile(ids)


a = Testowe(Symulacja([{"id": BANAN, "ilosc": 3}, {"id": SER, "ilosc": 1}, {"id": ZLOTO, "ilosc": 50}]))
cap, ham, _ = a.stan_cap()
sprawdz("2a stan_cap domyślnie: tylko ham (dawne liczenie) = 0 przy bananach", ham == 0, ham)
jedz = probuj(lambda: a.stan_cap(jedzenie_dowolne=True)[1])
sprawdz("2b stan_cap(jedzenie_dowolne=True): banany i ser liczone = 4", jedz == 4, jedz)
sprawdz("2c brakuje_jedzenia: cel 5, ma 4 => 1; brakuje('ham') nadal 5 (ham to osobne liczenie)", probuj(lambda: a.brakuje_jedzenia(5)) == 1 and a.brakuje("ham", 5) == 5,
        (probuj(lambda: a.brakuje_jedzenia(5)), a.brakuje("ham", 5)))
a2 = Testowe(Symulacja([{"id": HAM, "ilosc": 2}, {"id": BANAN, "ilosc": 3}]))
sprawdz("2d ham + banany: stan_cap (dowolne) = 5, domyślnie = 2", probuj(lambda: a2.stan_cap(jedzenie_dowolne=True)[1]) == 5 and a2.stan_cap()[1] == 2)

# --- 3. serwis: krok cap (SERWIS_HAM_MIN) i koszt -------------------------------------------------------------------------------------

DANE = json.load(open(KAT / "trasy" / "serwis_edron.json"))
S_CELE = {"cap_na_loot": 50, "ham_min": 2, "cap_depo_loot": 0}


class Atrapa:
    """Atrapa akcji: ham waży 20 oz, banany są jedzeniem (waga pomijalna), stan_cap zna tylko `jedzenie_dowolne` gdy zadeklarowane."""

    def __init__(self, cap=200.0, ham=0, banany=0, nowe_api=True):
        self.log, self.poz = [], [0, 0, 7]
        self.cap, self.ham, self.banany = cap, ham, banany
        if nowe_api:
            self.brakuje_jedzenia = lambda cel: max(0, cel - self.ham - self.banany)

    def sprawdz_start(self): self.log.append("start")
    def przygotuj_okna(self): self.log.append("okna")
    def majatek(self, tylko_glowny=False): return 100000
    def wolne_w_bagu(self): return 20
    def brakuje(self, co, cel): return max(0, cel - (self.ham if co == "ham" else 0))
    def bank_zmien(self, npc): self.log.append(("bank", npc))
    def pole_zajete(self, pole): return False
    def potrzeba_baga(self): return False
    def rezerwa_na_blanki(self, blanki): return 0.0

    def cel_ham(self, cel, rezerwa_oz):
        return self.ham + max(0, min(cel - self.ham, int((self.cap - rezerwa_oz) // 20)))

    def kup(self, npc, co, ile):
        self.log.append(("kup", npc, co, ile))

    def stan_cap(self, jedzenie_dowolne=False):
        return self.cap, self.ham + (self.banany if jedzenie_dowolne else 0), []


class Planer0:
    def droga(self, od, do):
        return [tuple(od), tuple(do)]


def zbuduj(akcje, cele):
    stoi = {"poz": (0, 0, 7)}

    def chodz(punkty, tol=0):
        stoi["poz"] = punkty[-1]
        akcje.poz = list(stoi["poz"])
        return True

    return S.Serwis(DANE, akcje, Planer0(), lambda: stoi["poz"], chodz, log=lambda *_: None, cele=cele)


def kupna(a):
    return [x for x in a.log if isinstance(x, tuple) and x[0] == "kup"]


a = Atrapa(banany=3)
zbuduj(a, S_CELE).uruchom(["cap"])
sprawdz("3a DOMYŚLNIE (pokrętło 0): postać z 3 bananami bez hama dostaje minimum ham (dawne zachowanie, bez zmian)", kupna(a) == [("kup", "Mirabell", "ham", 2)], a.log)
a = Atrapa(banany=3)
zbuduj(a, {**S_CELE, "jedzenie_dowolne": 1}).uruchom(["cap"])
sprawdz("3b SERWIS_JEDZENIE_DOWOLNE=1: 3 banany = jedzenie jest, ham nie kupowany", kupna(a) == [], a.log)
a = Atrapa(banany=1)
zbuduj(a, {**S_CELE, "jedzenie_dowolne": 1}).uruchom(["cap"])
sprawdz("3c =1 i tylko 1 banan (< minimum 2): kupuje minimum ham", kupna(a) == [("kup", "Mirabell", "ham", 2)], a.log)
a = Atrapa(banany=0)
zbuduj(a, {**S_CELE, "jedzenie_dowolne": 1}).uruchom(["cap"])
sprawdz("3d =1 i zero jedzenia: kupuje minimum ham (ham nadal preferowany zakup)", kupna(a) == [("kup", "Mirabell", "ham", 2)], a.log)
a = Atrapa(ham=2, banany=0)
zbuduj(a, {**S_CELE, "jedzenie_dowolne": 1}).uruchom(["cap"])
sprawdz("3e =1 i 2 ham: nic do kupienia (bez regresji dla samego hama)", kupna(a) == [], a.log)
a = Atrapa(banany=3, nowe_api=False)
zbuduj(a, {**S_CELE, "jedzenie_dowolne": 1}).uruchom(["cap"])
sprawdz("3f =1 i stara atrapa bez brakuje_jedzenia: bez wyjątku", True)
s_ = zbuduj(Atrapa(banany=3), S_CELE)
s2_ = zbuduj(Atrapa(banany=3), {**S_CELE, "jedzenie_dowolne": 1})
sprawdz("3g koszt kroku cap: domyślnie 20 gp (2 ham), przy =1 z bananami 0 gp", s_._koszt(["cap"]) == 20 and s2_._koszt(["cap"]) == 0, (s_._koszt(["cap"]), s2_._koszt(["cap"])))
sprawdz("3h krok jedzenie nie zależy od pokrętła (ham = preferowany zapas): cel 5 ham w obu wariantach",
        ("kup", "Mirabell", "ham", 5) in (lambda a: (zbuduj(a, {**S_CELE, "jedzenie_dowolne": 1}).uruchom(["jedzenie"]), a.log)[1])(Atrapa(cap=300.0, banany=3))
        and ("kup", "Mirabell", "ham", 5) in (lambda a: (zbuduj(a, S_CELE).uruchom(["jedzenie"]), a.log)[1])(Atrapa(cap=300.0, banany=3)))

# --- 4. pokrętło: odczyt z na_zywo, zakres, kierunek, tryb stoj --------------------------------------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "na_zywo.json"
    sprawdz("4a brak pliku: wynik jak przed zmianą (bez klucza jedzenie_dowolne)", S.pokretla_serwisu(p) == {"cap_na_loot": 50, "ham_min": 2, "cap_depo_loot": 0}, S.pokretla_serwisu(p))
    p.write_text(json.dumps({"SERWIS_JEDZENIE_DOWOLNE": 1}))
    sprawdz("4b =1 w na_zywo.json: jedzenie_dowolne = 1", S.pokretla_serwisu(p).get("jedzenie_dowolne") == 1, S.pokretla_serwisu(p))
    p.write_text(json.dumps({"SERWIS_JEDZENIE_DOWOLNE": "xx"}))
    sprawdz("4c śmieć: domyślnie 0 (klucz nieobecny)", "jedzenie_dowolne" not in S.pokretla_serwisu(p))
sprawdz("4d ZAKRESY (0,1), nie_wyzej: analityk nie włączy, Karol może",
        pokretla.ZAKRESY.get("SERWIS_JEDZENIE_DOWOLNE") == (0, 1) and pokretla.KIERUNEK.get("SERWIS_JEDZENIE_DOWOLNE") == "nie_wyzej"
        and pokretla.waliduj({"SERWIS_JEDZENIE_DOWOLNE": 1}, {"SERWIS_JEDZENIE_DOWOLNE": 0})[0] == {}
        and pokretla.waliduj({"SERWIS_JEDZENIE_DOWOLNE": 1})[0] == {"SERWIS_JEDZENIE_DOWOLNE": 1})
sprawdz("4e domyślna serwisu 0 = przykład = ZAKRESY", S.POKRETLA_SERWISU.get("SERWIS_JEDZENIE_DOWOLNE") == 0
        and json.load(open(KAT / "na_zywo.przyklad.json")).get("SERWIS_JEDZENIE_DOWOLNE") == 0)
TR = json.loads((KAT / "tryby.json").read_text())
sprawdz("4f tryb stoj ustawia 1, pozostałe tryby nie ruszają pokrętła",
        TR["stoj"]["pokretla"].get("SERWIS_JEDZENIE_DOWOLNE") == 1
        and not any("SERWIS_JEDZENIE_DOWOLNE" in t.get("pokretla", {}) for n, t in TR.items() if isinstance(t, dict) and n != "stoj"))
sprawdz("4g pokrętła z trybu stoj przechodzą walidację", pokretla.waliduj(TR["stoj"]["pokretla"])[1] == [], pokretla.waliduj(TR["stoj"]["pokretla"])[1])

print(f"\n{sum(ok)}/{len(ok)} OK" if all(ok) else f"\n{sum(ok)}/{len(ok)} FAIL")
sys.exit(0 if all(ok) else 1)
