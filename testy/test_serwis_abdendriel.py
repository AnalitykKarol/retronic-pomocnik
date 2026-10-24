"""Serwis Ab'Dendriel (24.10, Marinarra, runy HMM): dane z generatora (generuj_serwis_abdendriel.py), trasa po mieście i przez DWOJE drzwi z9
zamkniętych na klucz 2970 (serwis.przejdz_drzwi: krok, KLUCZ, krok jak wypad._drzwi), pełny serwis na atrapie świata (bank Briasol, depo,
backpack Bashira, blanki Shiriel, wyjście; BEZ jedzenia), panel i refill_auto dla Ab'Dendriel. Offline: RETRONIC_TESTY=1, żadnego inputu do gry,
żadnych procesów (poza generatorem z --sprawdz). NIEZWERYFIKOWANE NA ŻYWO: czy klucz 2970 pasuje do obojga drzwi, dialogi NPC, położenie depo."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
_os.environ["RETRONIC_ID"] = "tstabd"
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import generuj_powrot_abdendriel as GP
import generuj_serwis_abdendriel as G
import mapa as _mapa
import panel
import serwis as S
import wyprawa
import wypad
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


PLIK = KAT / "trasy" / "serwis_abdendriel.json"
META = KAT / "trasy" / "serwis_abdendriel.meta"
if not _mapa.PLIK_MAPY.is_file() or not PLIK.is_file():
    print("SKIP: brak mapy albo danych")
    sys.exit(0)
DANE = json.loads(PLIK.read_text())
MP = _mapa.mapa()
DEPO = tuple(GP.DEPO_STOI)
DRZWI_A, DRZWI_B = (32658, 31645, 9), (32655, 31655, 9)
KLUCZ = 2970
WYJSCIE = (32675, 31633, 9)

# --- 1. generator ---------------------------------------------------------------------------------------------------------

d1 = G.zbuduj(MP)
sprawdz("1a generator deterministyczny", G.tekst(d1) == G.tekst(G.zbuduj(MP)))
sprawdz("1b plik trasy/serwis_abdendriel.json = wynik generatora", PLIK.read_text() == G.tekst(d1))
sprawdz("1c plik .meta = wynik generatora", META.read_text() == G.tekst(G.meta(d1)))
r = subprocess.run([sys.executable, "-I", str(KAT / "generuj_serwis_abdendriel.py"), "--sprawdz"], capture_output=True, text=True, timeout=120)
sprawdz("1d CLI --sprawdz: kod 0", r.returncode == 0 and "zgodne" in r.stdout, r.stdout + r.stderr)
meta = json.loads(META.read_text())
sprawdz("1e .meta: 'specjalne' puste, źródła i lista niezmierzonego (klucz 2970, Briasol, depo)",
        meta["specjalne"] == [] and "zrodla" in meta and any("2970" in x for x in meta["niezmierzone_na_zywo"])
        and any("Briasol" in x for x in meta["niezmierzone_na_zywo"]) and any("depo" in x for x in meta["niezmierzone_na_zywo"]))

# --- 2. dane --------------------------------------------------------------------------------------------------------------

P = DANE["przystanki"]
sprawdz("2a kolejność: bank, depo, backpack, blanki, wyjście; BEZ jedzenia (Karol 24.10), też w przystankach",
        DANE["kolejnosc"] == ["bank", "depo", "backpack", "blanki", "wyjscie"] and "jedzenie" not in P and "jedzenie" not in DANE["kolejnosc"], DANE["kolejnosc"])
sprawdz("2b NPC: Briasol (bank, z8), Bashira (backpack 20 gp, z8), Shiriel (blank rune 10 gp, z6); pola stania z pomiaru 24.10",
        P["bank"]["npc"] == "Briasol" and tuple(P["bank"]["stoi"]) == (32637, 31667, 8)
        and P["backpack"]["npc"] == "Bashira" and tuple(P["backpack"]["stoi"]) == (32667, 31655, 8) and P["backpack"]["cena"] == 20
        and P["blanki"]["npc"] == "Shiriel" and tuple(P["blanki"]["stoi"]) == (32669, 31659, 6) and P["blanki"]["cena"] == 10)
sprawdz("2c NPC w zasięgu rozmowy z pola stania (<= ZASIEG_ROZMOWY, to samo piętro)",
        all(P[k]["stoi"][2] == P[k]["npc_poz"][2] and max(abs(P[k]["stoi"][0] - P[k]["npc_poz"][0]), abs(P[k]["stoi"][1] - P[k]["npc_poz"][1])) <= S.ZASIEG_ROZMOWY
            for k in ("bank", "backpack", "blanki")))
sprawdz("2d depo.stoi = GP.DEPO_STOI (jedno źródło, ZASTĘPCZE), pierwsze w depo_stoiska, wszystkie chodliwe, w sali depo",
        tuple(P["depo"]["stoi"]) == DEPO == tuple(DANE["depo_stoiska"][0]) and all(G.chodliwe(MP, tuple(s)) for s in DANE["depo_stoiska"])
        and all(DANE["depo_sala"][0] <= s[0] <= DANE["depo_sala"][2] and DANE["depo_sala"][1] <= s[1] <= DANE["depo_sala"][3] and s[2] == DANE["depo_sala"][4]
                for s in DANE["depo_stoiska"]))
sprawdz("2e wyjście = pierwszy punkt dojścia abdendriel_z9_do_z10, ZA obojgiem drzwi (z9)",
        tuple(DANE["wyjscie"]) == WYJSCIE == tuple(json.loads((KAT / "trasy" / "abdendriel_z9_do_z10.json").read_text())[0]))
zrodlo = {tuple(d): int(k) for p in wyprawa.PLANY_PK for d, k in (p.get("klucze") or ())}
sprawdz("2f drzwi_klucz: jedno źródło kluczy (GP.KLUCZE_DRZWI = wyprawa.PLANY_PK['klucze']), dwoje drzwi, klucz 2970",
        S.klucze_drzwi(DANE) == zrodlo == {DRZWI_A: KLUCZ, DRZWI_B: KLUCZ} == {tuple(d): int(k) for d, k in GP.KLUCZE_DRZWI}, S.klucze_drzwi(DANE))
sprawdz("2g drzwi na klucz to ściana w mapie (stąd brak drogi A*), a pola po obu stronach chodliwe",
        all(not G.chodliwe(MP, d) for d in (DRZWI_A, DRZWI_B)) and all(S.boki_drzwi(MP, d) for d in (DRZWI_A, DRZWI_B)))
sprawdz("2h drzwi_miasta zawiera drzwi na klucz; Edron i Thais bez drzwi_klucz: klucze_drzwi == {}",
        set(S.drzwi_miasta(DANE)) == {DRZWI_A, DRZWI_B} and S.klucze_drzwi(S.wczytaj("edron")) == {} and S.klucze_drzwi(S.wczytaj("thais")) == {})
LA = [(tuple(l["z"]), tuple(l["do"])) for l in DANE["laczniki"]]
sprawdz("2i łączniki: z8->z7->z6 (zmierzone) i z6->z7->z8 (powrót), z8->z9 (zmierzone) i z9->z8 (powrót)",
        ((32682, 31685, 8), (32682, 31686, 7)) in LA and ((32682, 31686, 7), (32682, 31688, 6)) in LA and ((32655, 31670, 8), (32654, 31671, 9)) in LA
        and ((32682, 31688, 6), (32682, 31686, 7)) in LA and ((32682, 31686, 7), (32682, 31685, 8)) in LA and ((32654, 31671, 9), (32654, 31669, 8)) in LA, LA)

# --- 3. Planer: trasy po mieście i przez drzwi na klucz ---------------------------------------------------------------------

PL = S.Planer(wyprawa.Trasownik(MP), DANE["laczniki"], drzwi=S.drzwi_miasta(DANE), mapa=MP, klucze=S.klucze_drzwi(DANE))
sprawdz("3a Planer.klucze = {drzwi: 2970}, drzwi znane z dwoma bokami", PL.klucze == {DRZWI_A: KLUCZ, DRZWI_B: KLUCZ} and set(PL.drzwi) == {DRZWI_A, DRZWI_B})
STOI = {k: tuple(P[k]["stoi"]) for k in ("bank", "backpack", "blanki")}
cele = [("depo", STOI["bank"]), ("bank", STOI["backpack"]), ("backpack", STOI["blanki"]), ("blanki", WYJSCIE), ("wyjscie", DEPO)]
brak = []
trasy = {}
for nazwa, (a, b) in zip(("depo>bank", "bank>backpack", "backpack>blanki", "blanki>wyjscie", "wyjscie>depo"), [(DEPO, STOI["bank"]), (STOI["bank"], STOI["backpack"]), (STOI["backpack"], STOI["blanki"]), (STOI["blanki"], WYJSCIE), (WYJSCIE, DEPO)]):
    d = PL.droga(a, b)
    trasy[nazwa] = d
    if d is None:
        brak.append(nazwa)
sprawdz("3b droga istnieje między wszystkimi kolejnymi przystankami (depo, bank, backpack, blanki, wyjście i z powrotem do depo)", not brak, brak)
t = trasy["blanki>wyjscie"] or []
poz_b = t.index(DRZWI_B) if DRZWI_B in t else None
poz_a = t.index(DRZWI_A) if DRZWI_A in t else None
sprawdz("3c droga blanki -> wyjście: każde drzwi dokładnie raz, B (32655,31655) przed A (32658,31645), po przejściu z8->z9",
        t.count(DRZWI_A) == 1 and t.count(DRZWI_B) == 1 and poz_b is not None and poz_a is not None and poz_b < poz_a
        and any(t[i][2] == 8 and t[i + 1][2] == 9 for i in range(len(t) - 1)) and t[-1] == WYJSCIE, (poz_b, poz_a))
t2 = trasy["wyjscie>depo"] or []
sprawdz("3d droga wyjście -> depo (powrót): drzwi A potem B, raz każde", t2.count(DRZWI_A) == 1 and t2.count(DRZWI_B) == 1 and t2.index(DRZWI_A) < t2.index(DRZWI_B))
sprawdz("3e droga bez drzwi do banku/backpacka/depo: nie dotyka drzwi na klucz", all(DRZWI_A not in trasy[k] and DRZWI_B not in trasy[k] for k in ("depo>bank", "bank>backpack", "backpack>blanki")))
sprawdz("3f żadna droga dłuższa niż 140 punktów (brak objazdów przez pół mapy)", all(len(v) <= 140 for v in trasy.values()), {k: len(v) for k, v in trasy.items()})

# --- 4. przejdz_drzwi z kluczem (atrapa świata) -----------------------------------------------------------------------------

S._czekaj_koniec_kroku = lambda: None
S._po_kroku = lambda *a, **k: None
BEZ_SPANIA = lambda _s: None
KIER = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}


class SwiatKlucz:
    """Drzwi zamknięte na klucz: otwiera je TYLKO uzyj_klucz (klucz 2970, z pola obok), zwykłe Use nic nie robi, krok w zamknięte drzwi nie rusza postaci.
    `klucz_w_plecaku=False`: BrakPrzedmiotu. `pasuje=False`: klucz nic nie otwiera. `zdarzenia`: kolejność kroków i kluczy."""

    def __init__(self, poz, drzwi, otwarte=None, klucz_w_plecaku=True, pasuje=True):
        self.poz = tuple(poz)
        self.drzwi = {tuple(d): False for d in drzwi}
        for d in otwarte or ():
            self.drzwi[tuple(d)] = True
        self.klucz_w_plecaku, self.pasuje = klucz_w_plecaku, pasuje
        self.zdarzenia, self.klucze, self.przejscia = [], [], []

    def pozycja(self):
        return self.poz

    def krok(self, klawisz):
        dx, dy = KIER[klawisz]
        n = (self.poz[0] + dx, self.poz[1] + dy, self.poz[2])
        self.zdarzenia.append(("krok", klawisz))
        if n in self.drzwi and not self.drzwi[n]:
            return None
        if n in self.drzwi:
            self.przejscia.append(n)
        self.poz = n
        return n

    def uzyj_klucz(self, id_klucza, cel, poz):
        self.zdarzenia.append(("klucz", int(id_klucza), tuple(cel), tuple(poz)))
        if not self.klucz_w_plecaku:
            raise wypad.BrakPrzedmiotu("brak klucza w otwartych pojemnikach")
        self.klucze.append((int(id_klucza), tuple(cel), tuple(poz)))
        c = tuple(cel)
        if self.pasuje and int(id_klucza) == KLUCZ and c in self.drzwi and max(abs(c[0] - poz[0]), abs(c[1] - poz[1])) <= 1 and tuple(poz) == self.poz:
            self.drzwi[c] = True


PRZED_B, ZA_B = (32655, 31656, 9), (32655, 31654, 9)          # B idziemy z korytarza z9 na północ, do sali
PRZED_A, ZA_A = (32658, 31646, 9), (32658, 31644, 9)          # A z sali do jaskini
sprawdz("4a boki drzwi z mapy zgadzają się z kierunkiem marszu (B: y 31656|31654, A: y 31646|31644)",
        set(PL.drzwi[DRZWI_B]) == {PRZED_B, ZA_B} and set(PL.drzwi[DRZWI_A]) == {PRZED_A, ZA_A}, PL.drzwi)


def przejdz(sw, przed, h, za, klucz=KLUCZ, uzyj=True):
    S._DRZWI_OTWARTE.clear()
    return S.przejdz_drzwi(sw, przed, h, za, log=lambda *_: None, spij=BEZ_SPANIA, klucz=klucz, uzyj_klucz=sw.uzyj_klucz if uzyj else None)


sw = SwiatKlucz(PRZED_B, [DRZWI_B])
r = przejdz(sw, PRZED_B, DRZWI_B, ZA_B)
sprawdz("4b drzwi zamknięte: krok (bez skutku), KLUCZ 2970 na drzwiach z pola przed, krok na drzwi, krok za nie; stoimy za drzwiami",
        r is True and sw.poz == ZA_B and sw.zdarzenia == [("krok", "Up"), ("klucz", KLUCZ, DRZWI_B, PRZED_B), ("krok", "Up"), ("krok", "Up")], (r, sw.zdarzenia))
uzyte = []
sw = SwiatKlucz(PRZED_B, [DRZWI_B])
S._DRZWI_OTWARTE.clear()
S.przejdz_drzwi(sw, PRZED_B, DRZWI_B, ZA_B, log=lambda *_: None, spij=BEZ_SPANIA, otworz=lambda dx, dy: uzyte.append((dx, dy)), klucz=KLUCZ, uzyj_klucz=sw.uzyj_klucz)
sprawdz("4c przy drzwiach na klucz zwykłe Use (otworz) nie jest wołane nigdy (Use nic nie otwiera, a na otwartych by zamknęło)", uzyte == [] and sw.poz == ZA_B, uzyte)
sw = SwiatKlucz(PRZED_B, [DRZWI_B], otwarte=[DRZWI_B])
r = przejdz(sw, PRZED_B, DRZWI_B, ZA_B)
sprawdz("4d drzwi już otwarte: ZERO użyć klucza (sam krok, krok), stoimy za drzwiami", r is True and sw.poz == ZA_B and sw.klucze == [], (r, sw.zdarzenia))
sw = SwiatKlucz(PRZED_A, [DRZWI_A])
r = przejdz(sw, PRZED_A, DRZWI_A, ZA_A)
sprawdz("4e drzwi A (32658,31645) zamknięte: ten sam wzór, klucz raz na drzwiach A", r is True and sw.poz == ZA_A and [k[1] for k in sw.klucze] == [DRZWI_A], (r, sw.zdarzenia))
sw = SwiatKlucz(ZA_B, [DRZWI_B])
r = przejdz(sw, ZA_B, DRZWI_B, PRZED_B)
sprawdz("4f przejście w drugą stronę (z sali do korytarza): klucz z pola ZA, stoimy w korytarzu", r is True and sw.poz == PRZED_B and sw.klucze == [(KLUCZ, DRZWI_B, ZA_B)], (r, sw.zdarzenia))
sw = SwiatKlucz(PRZED_B, [DRZWI_B], klucz_w_plecaku=False)
e = zglasza(lambda: przejdz(sw, PRZED_B, DRZWI_B, ZA_B))
sprawdz("4g brak klucza w plecaku: SerwisBlad('drzwi') z napisem o kluczu, bez wchodzenia w ścianę (jeden krok przed kluczem)",
        e and e.krok == "drzwi" and "klucz" in e.powod and "2970" in e.powod and sw.zdarzenia[:1] == [("krok", "Up")] and len(sw.zdarzenia) == 2, (e, sw.zdarzenia))
sw = SwiatKlucz(PRZED_B, [DRZWI_B], pasuje=False)
e = zglasza(lambda: przejdz(sw, PRZED_B, DRZWI_B, ZA_B))
sprawdz("4h klucz nie pasuje: SerwisBlad('drzwi') po skończonej liczbie prób (nie pętla), co najwyżej 2 użycia klucza, postać nie weszła w ścianę",
        e and e.krok == "drzwi" and len(sw.klucze) <= 3 and len(sw.zdarzenia) <= 12 and sw.poz == PRZED_B and not sw.przejscia, (e, sw.zdarzenia))
sw = SwiatKlucz(PRZED_B, [DRZWI_B])
e = zglasza(lambda: przejdz(sw, PRZED_B, DRZWI_B, ZA_B, uzyj=False))
sprawdz("4i drzwi na klucz, a brak funkcji użycia klucza: SerwisBlad bez kroku w ścianę", e and e.krok == "drzwi" and sw.zdarzenia == [], (e, sw.zdarzenia))
sw = SwiatKlucz((32655, 31660, 9), [DRZWI_B])
e = zglasza(lambda: przejdz(sw, PRZED_B, DRZWI_B, ZA_B))
sprawdz("4j postać nie stoi przed drzwiami: SerwisBlad bez kroku i bez klucza", e and e.krok == "drzwi" and sw.zdarzenia == [], (e, sw.zdarzenia))

# --- 5. idz_z_drzwiami po trasie z Planera (blanki -> wyjście i z powrotem) ----------------------------------------------------


class ChodzAtrapa:
    def __init__(self, swiat):
        self.sw, self.odcinki = swiat, []

    def __call__(self, punkty, tol=0):
        assert not any(tuple(q) in (DRZWI_A, DRZWI_B) for q in punkty), "kafelek drzwi w odcinku marszu"
        self.odcinki.append((tuple(punkty[0]), tuple(punkty[-1])))
        self.sw.poz = tuple(punkty[-1])
        return True


sw = SwiatKlucz(STOI["blanki"], [DRZWI_A, DRZWI_B])
ch = ChodzAtrapa(sw)
S._DRZWI_OTWARTE.clear()
r = S.idz_z_drzwiami(sw, trasy["blanki>wyjscie"], PL.drzwi, ch, 2, log=lambda *_: None, spij=BEZ_SPANIA, klucze=PL.klucze, uzyj_klucz=sw.uzyj_klucz)
sprawdz("5a trasa do wyjścia przez oba drzwi: klucz 2970 użyty raz na B, potem raz na A; przejścia B, A; kończymy na wyjściu (tolerancja 2)",
        r is True and [k[1] for k in sw.klucze] == [DRZWI_B, DRZWI_A] and sw.przejscia == [DRZWI_B, DRZWI_A]
        and max(abs(sw.poz[0] - WYJSCIE[0]), abs(sw.poz[1] - WYJSCIE[1])) <= 2 and sw.poz[2] == 9, (r, sw.klucze, sw.przejscia, sw.poz))
sprawdz("5b klucz używany z pola obok drzwi, w osi (jak wypad._drzwi)", all(max(abs(c[1][0] - c[2][0]), abs(c[1][1] - c[2][1])) == 1 for c in sw.klucze), sw.klucze)
sw = SwiatKlucz(WYJSCIE, [DRZWI_A, DRZWI_B])
ch = ChodzAtrapa(sw)
S._DRZWI_OTWARTE.clear()
r = S.idz_z_drzwiami(sw, trasy["wyjscie>depo"], PL.drzwi, ch, 0, log=lambda *_: None, spij=BEZ_SPANIA, klucze=PL.klucze, uzyj_klucz=sw.uzyj_klucz)
sprawdz("5c trasa wyjście -> depo: najpierw A, potem B, klucz po razie, koniec w depo", r is True and [k[1] for k in sw.klucze] == [DRZWI_A, DRZWI_B] and sw.poz == DEPO, (r, sw.klucze, sw.poz))
e = None
try:
    sw2 = SwiatKlucz(STOI["blanki"], [DRZWI_A, DRZWI_B])
    S._DRZWI_OTWARTE.clear()
    S.idz_z_drzwiami(sw2, trasy["blanki>wyjscie"], PL.drzwi, ChodzAtrapa(sw2), 2, log=lambda *_: None, spij=BEZ_SPANIA, otworz=lambda dx, dy: None)
except SerwisBlad as ex:
    e = ex
sprawdz("5d bez `klucze` (stary sposób wołania) drzwi zostają zamknięte: SerwisBlad('drzwi'), nigdy wejście w ścianę", e and e.krok == "drzwi" and not sw2.przejscia, (e,))

# --- 6. pełny serwis na atrapie świata -----------------------------------------------------------------------------------------


class AkcjeAtrapa:
    def __init__(self, sw):
        self.log, self.sw = [], sw

    def sprawdz_start(self):
        self.log.append("start")

    def przygotuj_okna(self):
        self.log.append("okna")

    def majatek(self, tylko_glowny=False):
        return 1000

    def wolne_w_bagu(self):
        return 20

    def brakuje(self, co, cel):
        return {"ham": cel, "blank rune": cel, "backpack": 1}[co]

    def bank_zmien(self, npc):
        self.log.append(("bank", npc))

    def pole_zajete(self, pole):
        return False

    def depo_zloz(self, zostaw_platinum, odejdz=None):
        self.log.append(("depo", tuple(self.sw.poz), zostaw_platinum))
        return True

    def kup(self, npc, co, ile, prefiks=""):
        self.log.append(("kup", npc, co, ile) + ((prefiks,) if prefiks else ()))

    def rezerwa_na_blanki(self, blanki):
        return 0.0

    def cel_ham(self, cel, rezerwa_oz):
        return cel

    def potrzeba_baga(self):
        return True

    def przenies_blanki(self):
        self.log.append("przenies_blanki")

    def uzyj_klucz(self, id_klucza, cel, poz):
        self.sw.uzyj_klucz(id_klucza, cel, poz)


def pelny_serwis(**kw):
    sw = SwiatKlucz(DEPO, [DRZWI_A, DRZWI_B], **kw)
    a = AkcjeAtrapa(sw)
    ch = ChodzAtrapa(sw)

    def chodz(punkty, tol=0):
        return S.idz_z_drzwiami(sw, punkty, PL.drzwi, ch, tol, log=lambda *_: None, spij=BEZ_SPANIA, klucze=PL.klucze, uzyj_klucz=a.uzyj_klucz)

    return S.Serwis(DANE, a, PL, lambda: sw.poz, chodz, log=lambda *_: None, spij=BEZ_SPANIA), a, sw


S._DRZWI_OTWARTE.clear()
sr, a, sw = pelny_serwis()
e = zglasza(lambda: sr.uruchom())
kupno = [x for x in a.log if isinstance(x, tuple) and x[0] == "kup"]
sprawdz("6a pełny serwis (domyślna kolejność): bank Briasol, depo, backpack u Bashiry, blanki u Shiriel, bez błędu, BEZ zakupu jedzenia",
        e is None and ("bank", "Briasol") in a.log and kupno == [("kup", "Bashira", "backpack", 1), ("kup", "Shiriel", "blank rune", 20)]
        and not any(x[2] == "ham" for x in kupno), (e, a.log))
sprawdz("6b wynik: bank, depo, backpack, blanki, wyjscie = ok", sr.wynik == {"bank": "ok", "depo": "ok", "backpack": "ok", "blanki": "ok", "wyjscie": "ok"}, sr.wynik)
sprawdz("6c wyjście przez oba drzwi kluczem 2970 (B potem A), po jednym użyciu klucza na drzwiach, koniec za drzwiami na z9",
        [k[1] for k in sw.klucze] == [DRZWI_B, DRZWI_A] and sw.przejscia == [DRZWI_B, DRZWI_A]
        and sw.poz[2] == 9 and max(abs(sw.poz[0] - WYJSCIE[0]), abs(sw.poz[1] - WYJSCIE[1])) <= 2, (sw.klucze, sw.przejscia, sw.poz))
S._DRZWI_OTWARTE.clear()
sr, a, sw = pelny_serwis()
e = zglasza(lambda: sr.uruchom(["bank", "depo", "jedzenie", "backpack", "blanki", "wyjscie"], pomin_brakujace=True))
sprawdz("6d refill.sh (pełna lista kroków + pomin_brakujace): jedzenie pominięte, reszta ok, zero zakupu ham",
        e is None and "jedzenie" not in sr.wynik and sr.wynik.get("blanki") == "ok" and sr.wynik.get("wyjscie") == "ok"
        and not any(isinstance(x, tuple) and x[0] == "kup" and x[2] == "ham" for x in a.log), (e, sr.wynik, a.log))
S._DRZWI_OTWARTE.clear()
sr, a, sw = pelny_serwis()
e = zglasza(lambda: sr.uruchom(["bank", "depo", "jedzenie", "backpack", "blanki", "wyjscie"]))
sprawdz("6e bez pomin_brakujace brak kroku jedzenie to czytelny błąd startu, zero ruchu", e and e.krok == "start" and "jedzenie" in e.powod and a.log == [] and sw.zdarzenia == [], (e, a.log))
S._DRZWI_OTWARTE.clear()
sr, a, sw = pelny_serwis(klucz_w_plecaku=False)
e = zglasza(lambda: sr.uruchom())
sprawdz("6f brak klucza w plecaku: serwis kończy się SerwisBlad('drzwi') PO blankach (nic nie zgadujemy), bez wejścia w ścianę",
        e and e.krok == "drzwi" and "klucz" in e.powod and sr.wynik.get("blanki") == "ok" and not sw.przejscia, (e, sr.wynik))

# --- 7. wybór miasta, panel, refill_auto, akcje ----------------------------------------------------------------------------------

sprawdz("7a serwis.miasta() zna abdendriel; wybierz_miasto('abdendriel') i auto z depo", "abdendriel" in S.miasta() and S.wybierz_miasto("abdendriel") == "abdendriel"
        and S.wybierz_miasto("auto", DEPO) == "abdendriel")
DS = panel.dane_serwisu()
sprawdz("7b panel.miasto_pozycji: depo = (abdendriel, przy depo); stanowisko z listy też; bank i korytarz z9 = miasto, nie depo",
        panel.miasto_pozycji(DEPO, DS) == ("abdendriel", True) and panel.miasto_pozycji((32680, 31683, 8), DS) == ("abdendriel", True)
        and panel.miasto_pozycji(STOI["bank"], DS) == ("abdendriel", False) and panel.miasto_pozycji((32654, 31671, 9), DS) == ("abdendriel", False))
sprawdz("7c panel: wyjście serwisu (32675,31633,z9), spot z10 i jaskinia z9 NIE są miastem (obszar_miasta)",
        panel.miasto_pozycji(WYJSCIE, DS) == (None, False) and panel.miasto_pozycji((32668, 31624, 10), DS) == (None, False)
        and panel.miasto_pozycji((32658, 31640, 9), DS) == (None, False), [panel.miasto_pozycji(p, DS) for p in (WYJSCIE, (32668, 31624, 10), (32658, 31640, 9))])
sprawdz("7d inne miasta bez zmian: depo Edron i przybycie Thais", panel.miasto_pozycji(tuple(S.wczytaj("edron")["przystanki"]["depo"]["stoi"]), DS) == ("edron", True)
        and panel.miasto_pozycji(tuple(S.wczytaj("thais")["wyjscie"]), DS) == ("thais", True))
import refill_auto
sprawdz("7e refill_auto zna Ab'Dendriel: depo = (abdendriel, przy depo)", "abdendriel" in refill_auto.MIASTA_SERWISU and refill_auto.miasto_serwisu(DEPO) == ("abdendriel", True))
tmp = tempfile.mkdtemp(prefix="abd_serwis_")
wywolania = []
st1 = refill_auto.zlec(DEPO, tmp, start=lambda: wywolania.append(1), procesy=lambda *a, **k: [])
sprawdz("7f zlec: stop w depo Ab'Dendriel = czeka i startuje czekacza (atrapa) raz", st1[0] == "czeka" and "abdendriel" in st1[1] and wywolania == [1], st1)
tmp2 = tempfile.mkdtemp(prefix="abd_serwis_")
st2 = refill_auto.zlec(WYJSCIE, tmp2, start=lambda: wywolania.append(2), procesy=lambda *a, **k: [])
sprawdz("7g stop w jaskini z9 (wyjście serwisu) to nie miasto: brak_planu, bez startu", st2[0] == "brak_planu" and 2 not in wywolania, st2)
import serwis_akcje as A
wywolane = []


class OpsAtrapa:
    def uzyj_klucz(self, id_klucza, cel, poz):
        wywolane.append((id_klucza, tuple(cel), tuple(poz)))


az = object.__new__(A.AkcjeZywe)
az._ops = OpsAtrapa()
az.uzyj_klucz(KLUCZ, DRZWI_B, PRZED_B)
sprawdz("7h AkcjeZywe.uzyj_klucz deleguje do wypad.OperacjeZywe.uzyj_klucz (Ctrl+klik na kluczu, klik na drzwiach)", wywolane == [(KLUCZ, DRZWI_B, PRZED_B)], wywolane)
sprawdz("7i main(): Planer dostaje klucze z danych, a chodz przekazuje je do idz_z_drzwiami",
        "klucze=klucze_drzwi(dane)" in (KAT / "serwis.py").read_text() and "klucze=planer.klucze, uzyj_klucz=akcje.uzyj_klucz" in (KAT / "serwis.py").read_text())

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
