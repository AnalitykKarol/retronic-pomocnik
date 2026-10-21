"""Serwis Thais (K3, 21.10): generator danych (generuj_serwis_thais.py), trasa po mieście na prawdziwej mapie klienta,
wybór miasta w serwis.py (edron domyślnie bez zmian), odrzucanie kroków za drzwiami, panel i refill_auto dla Thais.
Offline: RETRONIC_TESTY=1, żadnego inputu do gry, żadnych procesów."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
_os.environ["RETRONIC_ID"] = "tstthais"               # jak test_wroc_refill_auto: pidy/stan nie dotykają prawdziwych instancji
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import generuj_serwis_edron as GE
import generuj_serwis_thais as G
import mapa as _mapa
import panel
import serwis as S
import serwis_akcje as A
from serwis_blad import SerwisBlad, cheb

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


PLIK = KAT / "trasy" / "serwis_thais.json"
META = KAT / "trasy" / "serwis_thais.meta"
DANE = json.loads(PLIK.read_text())
if not _mapa.PLIK_MAPY.is_file():
    print("SKIP: brak mapa/map74.otmm")
    sys.exit(0)
MP = _mapa.mapa()
PRZYB = tuple(DANE["wyjscie"])

# --- 1. generator: deterministyczny i zgodny z plikami -------------------------------------------------------------

d1, d2 = G.zbuduj(MP), G.zbuduj(MP)
sprawdz("1a generator deterministyczny: dwa przebiegi dają te same bajty", G.tekst(d1) == G.tekst(d2))
sprawdz("1b plik trasy/serwis_thais.json = wynik generatora (nikt nie edytował ręcznie)", PLIK.read_text() == G.tekst(d1))
sprawdz("1c plik .meta = wynik generatora", META.read_text() == G.tekst(G.meta(d1, MP)))
r = subprocess.run([sys.executable, "-I", str(KAT / "generuj_serwis_thais.py"), "--sprawdz"], capture_output=True, text=True, timeout=120)
sprawdz("1d CLI --sprawdz: kod 0 (zgodne)", r.returncode == 0 and "zgodne" in r.stdout, r.stdout + r.stderr)
meta = json.loads(META.read_text())
sprawdz("1e .meta jest bezpieczne dla narzędzi tras: lista 'specjalne' pusta, są źródła i lista niezmierzonego",
        meta["specjalne"] == [] and "zrodla" in meta and meta["niezmierzone_na_zywo"], meta.keys())

# --- 2. współrzędne: źródło każdej i spójność z resztą repo ---------------------------------------------------------

depo_cave = json.loads((KAT / "trasy" / "depo_troll_cave.json").read_text())
sprawdz("2a przybycie wyprawy = start depo_troll_cave = depo.stoi = wyjscie", tuple(depo_cave[0]) == PRZYB == tuple(DANE["przystanki"]["depo"]["stoi"]) == G.PRZYBYCIE, depo_cave[0])
import wyprawa
sprawdz("2b wnęka zmierzona na żywo = wyprawa.POLE_ZLOZ_DEPO, skrzynia na północy = SKRZYNIA_DEPO",
        G.DEPO_ZMIERZONE == tuple(wyprawa.POLE_ZLOZ_DEPO) and (G.DEPO_ZMIERZONE[0], G.DEPO_ZMIERZONE[1] - 1, 7) == tuple(wyprawa.SKRZYNIA_DEPO))
st = [tuple(s) for s in DANE["depo_stoiska"]]
sprawdz("2c depo_stoiska: zmierzona pierwsza, bez duplikatów, wszystkie w sali depo", st[0] == G.DEPO_ZMIERZONE and len(set(st)) == len(st)
        and all(G.DEPO_X[0] <= x <= G.DEPO_X[1] and G.DEPO_Y[0] <= y <= G.DEPO_Y[1] and z == 7 for x, y, z in st), st)
sprawdz("2d wnęki: stanowisko chodliwe, północ/zachód/wschód to ściana (skrzynia na końcu), południe wolne",
        all(G.chodliwe(MP, x, y, z) and not G.chodliwe(MP, x, y - 1, z) and not G.chodliwe(MP, x - 1, y, z)
            and not G.chodliwe(MP, x + 1, y, z) and G.chodliwe(MP, x, y + 1, z) for x, y, z in st))
sprawdz("2e wnęki: cztery (dwie pary w dwóch rzędach), dwa razy po dwie jak w mapie klienta", st == [(32343, 32226, 7), (32341, 32226, 7), (32352, 32226, 7), (32354, 32226, 7)], st)
npc = G.wczytaj_npc()
ok_npc = True
for krok in ("jedzenie", "backpack", "blanki"):
    p = DANE["przystanki"][krok]
    n = npc[p["npc"]]
    np_ = (n["pozycja"]["x"], n["pozycja"]["y"], n["pozycja"]["z"])
    ok_npc &= tuple(p["npc_poz"]) == np_ and p["stoi"][2] == np_[2] and cheb(p["stoi"], np_) <= 2
sprawdz("2f NPC: pozycja z npc_pelne.json, pole stania na tym samym piętrze, najwyżej 2 pola od NPC", ok_npc)
ceny = {k: DANE["przystanki"][k]["cena"] for k in ("jedzenie", "backpack", "blanki")}
sprawdz("2g ceny z danych serwera mieszczą się w limitach kupna (serwis_akcje.LIMITY_CENY)",
        ceny == {"jedzenie": 8, "backpack": 20, "blanki": 10} and ceny["jedzenie"] <= A.LIMITY_CENY["ham"]
        and ceny["blanki"] <= A.LIMITY_CENY["blank rune"] and ceny["backpack"] <= A.LIMITY_CENY["backpack"], ceny)
sprawdz("2h NPC Thais są znane detektorowi NPC serwisu (nie liczą się jako gracze/stwory)", {"frodo", "gorn", "xodet", "suzy"} <= A.NPC_NAZWY)
sprawdz("2i bank Suzy w do_pomiaru, NIE w przystankach (brak pola stania = nic do zgadywania)",
        "bank" not in DANE["przystanki"] and DANE["do_pomiaru"]["bank"]["npc"] == "Suzy" and "pole stania" in DANE["do_pomiaru"]["bank"]["brak"])
sprawdz("2j układ zgodny z serwis_edron.json: te same wymagane klucze", {"przystanki", "laczniki", "kolejnosc", "wyjscie", "depo_stoiska", "miasto"} <= set(DANE)
        and set(json.loads((KAT / "trasy" / "serwis_edron.json").read_text())) - {"_opis"} <= set(DANE))
sprawdz("2k Thais w jednym piętrze: łączniki puste, wszystkie punkty na z7",
        DANE["laczniki"] == [] and {tuple(v["stoi"])[2] for v in DANE["przystanki"].values()} == {7})

# --- 3. drzwi: sklepy Frodo i Xodeta są za drzwiami, reszta na ulicy -------------------------------------------------

P = {k: tuple(v["stoi"]) for k, v in DANE["przystanki"].items()}
drzwi = {k: [tuple(d) for d in v.get("drzwi", [])] for k, v in DANE["przystanki"].items()}
sprawdz("3a drzwi są tylko tam, gdzie trzeba: jedzenie (32365,32208) i blanki (32400,32217); depo i backpack bez", drzwi == {
    "depo": [], "jedzenie": [(32365, 32208, 7)], "backpack": [], "blanki": [(32400, 32217, 7)]}, drzwi)
sprawdz("3b drzwi to ściana na mapie (stąd brak drogi A*)", all(MP.przechodnie(*d) is False for ds in drzwi.values() for d in ds))
bez = {k: bool(G.osiagalne(MP, PRZYB, [P[k]])) for k in P}
z_dr = {k: bool(G.osiagalne(MP, PRZYB, [P[k]], otwarte=drzwi[k])) for k in P}
sprawdz("3c bez drzwi osiągalne tylko depo i backpack; z drzwiami wszystkie", bez == {"depo": True, "jedzenie": False, "backpack": True, "blanki": False}
        and all(z_dr.values()), (bez, z_dr))
sprawdz("3d dokładnie te przystanki, do których A* nie dojdzie, mają 'drzwi' (spójność danych z mapą)",
        all(bool(drzwi[k]) == (not bez[k]) for k in P))

# --- 4. trasa po mieście: A* serwisu (Planer) na prawdziwej mapie, od przybycia wyprawy do każdego przystanku ------------

planer = S.Planer(wyprawa.Trasownik(MP), DANE["laczniki"])
cele = {"wnęka%d" % i: tuple(s) for i, s in enumerate(DANE["depo_stoiska"])}
cele.update({"backpack": P["backpack"], "wyjscie": PRZYB})
brak, krzywe, dlugie = [], [], []
for a in [PRZYB] + list(cele.values()):
    for nazwa, b in cele.items():
        if a == b:
            continue
        d = planer.droga(a, b)
        if d is None:
            brak.append((a, nazwa))
            continue
        if tuple(d[0]) != a or tuple(d[-1]) != b or any(not G.chodliwe(MP, p[0], p[1], p[2]) or p[2] != 7 for p in d):
            krzywe.append((a, nazwa))
        if sum(cheb(p, q) for p, q in zip(d, d[1:])) > 120:
            dlugie.append((a, nazwa))
sprawdz("4a droga A* od przybycia i między wszystkimi przystankami bez drzwi (4 wnęki, Gorn, wyjście): brak dziur", not brak, brak)
sprawdz("4b każda droga: zaczyna i kończy na zadanych polach, same chodliwe pola na z7", not krzywe, krzywe)
sprawdz("4c żadna droga dłuższa niż 120 pól (miasto jest małe: brak objazdów przez pół mapy)", not dlugie, dlugie)
dp = planer.droga(PRZYB, P["backpack"])
sprawdz("4d przybycie -> Gorn to 40-60 pól (zmierzone 50; nagrana trasa wyprawy do Gorna kończy się w tym samym polu)",
        dp and 40 <= sum(cheb(p, q) for p, q in zip(dp, dp[1:])) <= 60, dp and sum(cheb(p, q) for p, q in zip(dp, dp[1:])))

# --- 5. orkiestrator na danych Thais (atrapy) -----------------------------------------------------------------------


class AkcjeAtrapa:
    def __init__(self):
        self.log, self.poz = [], [0, 0, 7]

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

    def depo_zloz(self, zostaw_platinum):
        self.log.append(("depo", tuple(self.poz), zostaw_platinum))
        return True

    def kup(self, npc, co, ile):
        self.log.append(("kup", npc, co, ile))

    def potrzeba_baga(self):
        return True

    def przenies_blanki(self):
        self.log.append("przenies_blanki")


class Planer0:
    def droga(self, od, do):
        return [tuple(od), tuple(do)]


def serwis_atrapa(start=PRZYB):
    a = AkcjeAtrapa()
    stoi = {"poz": tuple(start), "tol": []}

    def chodz(punkty, tol=0):
        stoi["poz"] = tuple(punkty[-1])
        stoi["tol"].append(tol)
        a.poz = list(stoi["poz"])
        return True

    return S.Serwis(DANE, a, Planer0(), lambda: stoi["poz"], chodz, log=lambda *_: None), a, stoi


s, a, stn = serwis_atrapa()
s.uruchom()
najblizsze = min((tuple(x) for x in DANE["depo_stoiska"]), key=lambda x: cheb(PRZYB, x))        # Planer0: koszt = Chebyshev
sprawdz("5a domyślna kolejność Thais: depo (najbliższe stanowisko, 3 platinum), Gorn (backpack), wyjście na przybycie",
        a.log == ["start", "okna", ("depo", najblizsze, 3), ("kup", "Gorn", "backpack", 1), "okna"] and stn["poz"] == PRZYB, (a.log, stn))
sprawdz("5b kupuje u Gorna dokładnie jeden backpack, dojście do NPC z tolerancją 0, do wyjścia 2", ("kup", "Gorn", "backpack", 1) in a.log and stn["tol"] == [0, 0, 2], stn["tol"])
for krok in ("jedzenie", "blanki"):
    s, a, stn = serwis_atrapa()
    e = zglasza(lambda: s.uruchom([krok]))
    sprawdz(f"5c krok {krok} (za drzwiami) odrzucony przed pierwszym inputem i ruchem", e and e.krok == "start" and "drzwi" in e.powod and a.log == [] and stn["tol"] == [], (e, a.log))
s, a, stn = serwis_atrapa()
e = zglasza(lambda: s.uruchom(["depo", "jedzenie", "backpack"]))
sprawdz("5d mieszana lista z krokiem za drzwiami: odrzucona w całości, depo nie ruszone", e and a.log == [], (e, a.log))
s, a, stn = serwis_atrapa()
plan = s.plan(["depo", "jedzenie", "backpack", "blanki", "wyjscie"])
sprawdz("5e plan na sucho: kroki za drzwiami = None (brak drogi) bez liczenia A*, reszta ma liczbę punktów",
        [(k, n is None) for k, _c, n in plan] == [("depo", False), ("jedzenie", True), ("backpack", False), ("blanki", True), ("wyjscie", False)], plan)
s, a, stn = serwis_atrapa()
s.obsluga_drzwi = True
sprawdz("5f flaga obsluga_drzwi=True (przyszła obsługa) zdejmuje blokadę: lista kroków przechodzi walidację", zglasza(lambda: s.uruchom(["jedzenie"])) is None)
sprawdz("5g pełna lista po drzwiach istnieje w danych i zawiera wszystkie przystanki + wyjście",
        DANE["kolejnosc_po_drzwiach"] == ["depo", "jedzenie", "backpack", "blanki", "wyjscie"])

# --- 6. wybór miasta w serwis.py: Edron domyślnie bez zmian --------------------------------------------------------------

sprawdz("6a plany serwisu: edron i thais", S.miasta() == ["edron", "thais"], S.miasta())
sprawdz("6b bez argumentu = edron (zachowanie sprzed K3)", S.wybierz_miasto(None) == "edron" and S.wybierz_miasto("edron") == "edron")
sprawdz("6c thais jawnie", S.wybierz_miasto("thais") == "thais")
e = zglasza(lambda: S.wybierz_miasto("rook"))
sprawdz("6d miasto bez planu (rook) = czytelny błąd z listą planów", e and "rook" in e.powod and "thais" in e.powod, e)
sprawdz("6e auto: pozycja przybycia w Thais -> thais", S.wybierz_miasto("auto", PRZYB) == "thais")
edron_depo = tuple(json.loads((KAT / "trasy" / "serwis_edron.json").read_text())["przystanki"]["depo"]["stoi"])
sprawdz("6f auto: depo Edron -> edron", S.wybierz_miasto("auto", edron_depo) == "edron", edron_depo)
for nazwa, poz in (("Rook (32061,32180,7)", (32061, 32180, 7)), ("jaskinia trolli z8 (32492,32261,8)", (32492, 32261, 8))):
    e = zglasza(lambda: S.wybierz_miasto("auto", poz))
    sprawdz(f"6g auto: {nazwa} poza planami = błąd, nie zgadujemy", e and e.krok == "start", e)
sprawdz("6h auto bez pozycji = błąd", zglasza(lambda: S.wybierz_miasto("auto", None)) is not None)
sh = (KAT / "serwis.sh").read_text()
sprawdz("6i serwis.sh: miasto z SERWIS_MIASTO, domyślnie edron", 'serwis.py "${SERWIS_MIASTO:-edron}" "$@"' in sh)
r = subprocess.run(["bash", "-n", str(KAT / "serwis.sh")], capture_output=True, text=True)
sprawdz("6j serwis.sh: składnia bash ok", r.returncode == 0, r.stderr)

# --- 7. Edron bez zmian ---------------------------------------------------------------------------------------------------

ED = json.loads((KAT / "trasy" / "serwis_edron.json").read_text())
sprawdz("7a dane Edron: kolejność i brak pól 'drzwi' (blokada drzwi ich nie dotyka)",
        ED["kolejnosc"] == ["bank", "depo", "jedzenie", "backpack", "blanki", "wyjscie"] and not any("drzwi" in v for v in ED["przystanki"].values()))
sed = S.Serwis(ED, AkcjeAtrapa(), Planer0(), lambda: (0, 0, 7), lambda *a, **k: True, log=lambda *_: None)
sprawdz("7b Edron: żaden krok nie jest 'za drzwiami'", all(not sed._za_drzwiami(k) for k in ED["kolejnosc"]))
sprawdz("7c generator Edron nietknięty: stanowiska depo jak w teście Edron", GE.stanowiska_depo()[0] == [33175, 31796, 8] and len(GE.stanowiska_depo()) == 8)
sprawdz("7d serwis.wczytaj('edron') czyta ten sam plik", S.wczytaj("edron") == ED)
sprawdz("7e serwis.wczytaj('thais') czyta plik Thais", S.wczytaj("thais") == DANE)

# --- 8. panel i refill_auto widzą Thais ------------------------------------------------------------------------------------

sprawdz("8a panel.miasto_pozycji: przybycie wyprawy = (thais, przy depo)", panel.miasto_pozycji(PRZYB, panel.dane_serwisu()) == ("thais", True))
sprawdz("8b panel: depo Edron nadal (edron, przy depo)", panel.miasto_pozycji(edron_depo, panel.dane_serwisu()) == ("edron", True))
sprawdz("8c panel: jaskinia trolli z8 i Rook poza miastem", panel.miasto_pozycji((32492, 32261, 8), panel.dane_serwisu()) == (None, False)
        and panel.miasto_pozycji((32061, 32180, 7), panel.dane_serwisu())[0] is None)
sprawdz("8d panel: sklep Xodeta (32400,32220,7) to Thais, ale nie przy depo", panel.miasto_pozycji((32400, 32220, 7), panel.dane_serwisu()) == ("thais", False))
import refill_auto
sprawdz("8e dziś refill_auto nie zna Thais (MIASTA_SERWISU = edron): brak planu, jak w logu invincible 16:13",
        refill_auto.MIASTA_SERWISU == ("edron",) and refill_auto.miasto_serwisu(PRZYB) == (None, False))
tmp = tempfile.mkdtemp(prefix="k3_thais_")
st0 = refill_auto.zlec(PRZYB, tmp, start=lambda: None, procesy=lambda *a, **k: [])
sprawdz("8f zlec dziś: Thais = brak_planu z komunikatem z logu", st0[0] == "brak_planu" and "serwis ma: edron" in st0[1], st0)
stare = refill_auto.MIASTA_SERWISU
refill_auto.MIASTA_SERWISU = ("edron", "thais")           # zmiana, którą ma zrobić lead (diff w raporcie)
try:
    sprawdz("8g po dopisaniu thais do MIASTA_SERWISU: przybycie wyprawy = (thais, przy depo)", refill_auto.miasto_serwisu(PRZYB) == ("thais", True))
    tmp2 = tempfile.mkdtemp(prefix="k3_thais_")
    wywolania = []
    st1 = refill_auto.zlec(PRZYB, tmp2, start=lambda: wywolania.append(1), procesy=lambda *a, **k: [])
    sprawdz("8h po dopisaniu: zlec = czeka i startuje czekacza (atrapa) dla Thais", st1[0] == "czeka" and "thais" in st1[1] and wywolania == [1], st1)
    tmp3 = tempfile.mkdtemp(prefix="k3_thais_")
    st2 = refill_auto.zlec((32366, 32215, 7), tmp3, start=lambda: wywolania.append(2), procesy=lambda *a, **k: [])
    sprawdz("8i po dopisaniu: ulica Thais daleko od depo = pominięty (nie przy depo), bez startu", st2[0] == "pominiety" and "nie stoi przy depo" in st2[1] and 2 not in wywolania, st2)
finally:
    refill_auto.MIASTA_SERWISU = stare

# --- wynik -------------------------------------------------------------------------------------------------------------------

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
