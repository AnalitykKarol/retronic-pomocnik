"""Serwis Thais (K3, 21.10; drzwi sklepów 22.10): generator danych (generuj_serwis_thais.py), trasa po mieście na prawdziwej
mapie klienta, wybór miasta w serwis.py (z pozycji; Edron bez zmian), przechodzenie przez zamknięte drzwi Frodo i Xodeta
w marszu serwisu (przejdz_drzwi, atrapa świata), bank Suzy zmierzony na żywo 22.10 (pierwszy krok, drzwi), pełny serwis Thais
z bankiem, jedzeniem i blankami, refill, panel i refill_auto dla Thais. Offline: RETRONIC_TESTY=1, żadnego inputu do gry, żadnych procesów."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
_os.environ["RETRONIC_ID"] = "tstthais"               # jak test_wroc_refill_auto: pidy/stan nie dotykają prawdziwych instancji
import copy
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
for krok in ("bank", "jedzenie", "backpack", "blanki"):
    p = DANE["przystanki"][krok]
    n = npc[p["npc"]]
    np_ = (n["pozycja"]["x"], n["pozycja"]["y"], n["pozycja"]["z"])
    ok_npc &= tuple(p["npc_poz"]) == np_ and p["stoi"][2] == np_[2] and cheb(p["stoi"], np_) <= 2
sprawdz("2f NPC (z Suzy): pozycja z npc_pelne.json, pole stania na tym samym piętrze, najwyżej 2 pola od NPC", ok_npc)
ceny = {k: DANE["przystanki"][k]["cena"] for k in ("jedzenie", "backpack", "blanki")}
sprawdz("2g ceny z danych serwera mieszczą się w limitach kupna (serwis_akcje.LIMITY_CENY)",
        ceny == {"jedzenie": 8, "backpack": 20, "blanki": 10} and ceny["jedzenie"] <= A.LIMITY_CENY["ham"]
        and ceny["blanki"] <= A.LIMITY_CENY["blank rune"] and ceny["backpack"] <= A.LIMITY_CENY["backpack"], ceny)
sprawdz("2h NPC Thais są znane detektorowi NPC serwisu (nie liczą się jako gracze/stwory)", {"frodo", "gorn", "xodet", "suzy"} <= A.NPC_NAZWY)
BANK_STOI, BANK_DRZWI = (32319, 32256, 7), (32319, 32253, 7)       # zmierzone na żywo 22.10 13:32 (wydra, Karol prowadził)
bk = DANE["przystanki"]["bank"]
sprawdz("2i bank Suzy ZMIERZONY (22.10): w przystankach z polem stania (32319,32256,7), drzwiami (32319,32253,7), rodzaj bank; poza do_pomiaru",
        bk["rodzaj"] == "bank" and bk["npc"] == "Suzy" and tuple(bk["stoi"]) == BANK_STOI == tuple(G.BANK["stoi"])
        and [tuple(d) for d in bk["drzwi"]] == [BANK_DRZWI] and "bank" not in DANE["do_pomiaru"] and "zmierzone" in bk["status"], bk)
sprawdz("2j układ zgodny z serwis_edron.json: te same wymagane klucze", {"przystanki", "laczniki", "kolejnosc", "wyjscie", "depo_stoiska", "miasto"} <= set(DANE)
        and set(json.loads((KAT / "trasy" / "serwis_edron.json").read_text())) - {"_opis", "depo_sala", "depo_obszar"} <= set(DANE))   # 24.10: depo_sala/depo_obszar = tylko Edron (losowe pole dojścia do depo)
sprawdz("2k Thais w jednym piętrze: łączniki puste, wszystkie punkty na z7",
        DANE["laczniki"] == [] and {tuple(v["stoi"])[2] for v in DANE["przystanki"].values()} == {7})

# --- 3. drzwi: sklepy Frodo i Xodeta są za drzwiami, reszta na ulicy -------------------------------------------------

P = {k: tuple(v["stoi"]) for k, v in DANE["przystanki"].items()}
drzwi = {k: [tuple(d) for d in v.get("drzwi", [])] for k, v in DANE["przystanki"].items()}
sprawdz("3a drzwi są tylko tam, gdzie trzeba: jedzenie (32365,32208), blanki (32400,32217) i bank (32319,32253); depo i backpack bez", drzwi == {
    "depo": [], "jedzenie": [(32365, 32208, 7)], "backpack": [], "blanki": [(32400, 32217, 7)], "bank": [(32319, 32253, 7)]}, drzwi)
sprawdz("3b drzwi to ściana na mapie (stąd brak drogi A*)", all(MP.przechodnie(*d) is False for ds in drzwi.values() for d in ds))
bez = {k: bool(G.osiagalne(MP, PRZYB, [P[k]])) for k in P}
z_dr = {k: bool(G.osiagalne(MP, PRZYB, [P[k]], otwarte=drzwi[k])) for k in P}
sprawdz("3c bez drzwi osiągalne tylko depo i backpack; z drzwiami wszystkie (też bank)", bez == {"depo": True, "jedzenie": False, "backpack": True, "blanki": False, "bank": False}
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

ED_KOLEJNOSC = json.loads((KAT / "trasy" / "serwis_edron.json").read_text())["kolejnosc"]

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

    def depo_zloz(self, zostaw_platinum, odejdz=None):
        self.log.append(("depo", tuple(self.poz), zostaw_platinum))
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


class Planer0:
    def droga(self, od, do):
        return [tuple(od), tuple(do)]


def serwis_atrapa(start=PRZYB, drzwi=False):
    a = AkcjeAtrapa()
    stoi = {"poz": tuple(start), "tol": []}

    def chodz(punkty, tol=0):
        stoi["poz"] = tuple(punkty[-1])
        stoi["tol"].append(tol)
        a.poz = list(stoi["poz"])
        return True

    return S.Serwis(DANE, a, Planer0(), lambda: stoi["poz"], chodz, log=lambda *_: None, obsluga_drzwi=drzwi or None), a, stoi


s, a, stn = serwis_atrapa(drzwi=True)
s.uruchom()
najblizsze = min((tuple(x) for x in DANE["depo_stoiska"]), key=lambda x: (cheb(P["bank"], x), x))        # Planer0: koszt = Chebyshev, remis -> mniejsza współrzędna (jak sorted w _krok_depo); do depo idziemy z banku
sprawdz("5a domyślna kolejność Thais (22.10): bank Suzy (pierwszy), depo (najbliższe stanowisko od banku, 3 platinum), Frodo (5 ham, „buy ”), "
        "Gorn (backpack), Xodet (20 blank rune, „buy ”), wyjście na przybycie",
        a.log == ["start", "okna", ("bank", "Suzy"), ("depo", najblizsze, 3), ("kup", "Frodo", "ham", 5, "buy "), ("kup", "Gorn", "backpack", 1), "okna", "okna",
                  ("kup", "Xodet", "blank rune", 20, "buy "), "przenies_blanki", "okna"] and stn["poz"] == PRZYB, (a.log, stn))
sprawdz("5b kupuje u Gorna dokładnie jeden backpack; dojście do NPC (bank, depo, Frodo, Gorn, Xodet) z tolerancją 0, do wyjścia 2", ("kup", "Gorn", "backpack", 1) in a.log
        and stn["tol"] == [0, 0, 0, 0, 0, 2], stn["tol"])
for krok in ("jedzenie", "blanki"):
    s, a, stn = serwis_atrapa()
    e = zglasza(lambda: s.uruchom([krok]))
    sprawdz(f"5c krok {krok} (za drzwiami) przy planerze BEZ drzwi odrzucony przed pierwszym inputem i ruchem", e and e.krok == "start" and "drzwi" in e.powod and a.log == [] and stn["tol"] == [], (e, a.log))
s, a, stn = serwis_atrapa()
e = zglasza(lambda: s.uruchom(["depo", "jedzenie", "backpack"]))
sprawdz("5d planer bez drzwi, mieszana lista z krokiem za drzwiami: odrzucona w całości, depo nie ruszone", e and a.log == [], (e, a.log))
s, a, stn = serwis_atrapa()
plan = s.plan(["depo", "jedzenie", "backpack", "blanki", "wyjscie"])
sprawdz("5e plan na sucho planerem bez drzwi: kroki za drzwiami = None (brak drogi) bez liczenia A*, reszta ma liczbę punktów",
        [(k, n is None) for k, _c, n in plan] == [("depo", False), ("jedzenie", True), ("backpack", False), ("blanki", True), ("wyjscie", False)], plan)
s, a, stn = serwis_atrapa()
s.obsluga_drzwi = True
sprawdz("5f flaga obsluga_drzwi=True zdejmuje blokadę: lista kroków przechodzi walidację", zglasza(lambda: s.uruchom(["jedzenie"])) is None)
sprawdz("5g domyślna kolejność w danych to pełna lista z bankiem na początku (jak Edron), bez pola kolejnosc_po_drzwiach; Frodo i Xodet mają zakup_prefiks „buy ”",
        DANE["kolejnosc"] == ["bank", "depo", "jedzenie", "backpack", "blanki", "wyjscie"] == ED_KOLEJNOSC and "kolejnosc_po_drzwiach" not in DANE
        and DANE["przystanki"]["jedzenie"].get("zakup_prefiks") == "buy " and DANE["przystanki"]["blanki"].get("zakup_prefiks") == "buy "
        and "zakup_prefiks" not in DANE["przystanki"]["backpack"])

# --- 6. wybór miasta w serwis.py: Edron domyślnie bez zmian --------------------------------------------------------------

sprawdz("6a plany serwisu: abdendriel (24.10), edron, port_hope (25.10) i thais", S.miasta() == ["abdendriel", "edron", "port_hope", "thais"], S.miasta())
sprawdz("6b bez argumentu i bez pozycji = edron (zachowanie sprzed K3)", S.wybierz_miasto(None) == "edron" and S.wybierz_miasto("edron") == "edron")
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
sprawdz("6i serwis.sh: miasto z SERWIS_MIASTO, a bez niego serwis.py wybiera po pozycji (brak sztywnego edron)",
        'serwis.py ${SERWIS_MIASTO:+"$SERWIS_MIASTO"} "$@"' in sh and ":-edron" not in sh)
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
sprawdz("8e refill_auto zna Thais (MIASTA_SERWISU = edron, thais, abdendriel, port_hope): przybycie wyprawy = (thais, przy depo)",
        refill_auto.MIASTA_SERWISU == ("edron", "thais", "abdendriel", "port_hope") and refill_auto.miasto_serwisu(PRZYB) == ("thais", True))
tmp = tempfile.mkdtemp(prefix="k3_thais_")
wywolania = []
st1 = refill_auto.zlec(PRZYB, tmp, start=lambda: wywolania.append(1), procesy=lambda *a, **k: [])
sprawdz("8f zlec: Thais = czeka i startuje czekacza (atrapa) raz", st1[0] == "czeka" and "thais" in st1[1] and wywolania == [1], st1)
tmp3 = tempfile.mkdtemp(prefix="k3_thais_")
st2 = refill_auto.zlec((32366, 32215, 7), tmp3, start=lambda: wywolania.append(2), procesy=lambda *a, **k: [])
sprawdz("8g ulica Thais daleko od depo = pominięty (nie przy depo), bez startu", st2[0] == "pominiety" and "nie stoi przy depo" in st2[1] and 2 not in wywolania, st2)
tmp4 = tempfile.mkdtemp(prefix="k3_thais_")
st3 = refill_auto.zlec((32061, 32180, 7), tmp4, start=lambda: wywolania.append(3), procesy=lambda *a, **k: [])
sprawdz("8h Rook: nadal brak_planu, komunikat wymienia edron, thais i abdendriel", st3[0] == "brak_planu" and "edron" in st3[1] and "thais" in st3[1] and "abdendriel" in st3[1] and 3 not in wywolania, st3)

# --- 9. drzwi w marszu serwisu: atrapa świata z zamkniętymi drzwiami (22.10) --------------------------------------------------

import time as _time
S._czekaj_koniec_kroku = lambda: None          # bez realnych pauz między krokami
S._po_kroku = lambda *a, **k: None
BEZ_SPANIA = lambda _s: None
S_OTW = S._DRZWI_OTWARTE                       # pamięć „te drzwi już otwarte”; testy czyszczą ją przed każdym przejściem
FRODO, XODET, BANKD = (32365, 32208, 7), (32400, 32217, 7), BANK_DRZWI


class SwiatDrzwi:
    """Postać na polach; kafelek drzwi blokuje krok, dopóki drzwi zamknięte. Use (otworz) PRZEŁĄCZA drzwi (Use na otwartych je zamyka,
    jak w grze). `otwieraja=False`: drzwi nie reagują na Use (zablokowane). `ruch`: tyle pierwszych odczytów pozycji zmienia się sama."""

    KIER = {"Up": (0, -1), "Down": (0, 1), "Left": (-1, 0), "Right": (1, 0)}

    def __init__(self, poz, drzwi, otwarte=False, otwieraja=True, ruch=0):
        self.poz, self.h, self.otwarte, self.otwieraja = tuple(poz), tuple(drzwi), otwarte, otwieraja
        self.uzycia, self.kroki, self.ruch, self.odczyty = [], [], ruch, 0

    def pozycja(self):
        self.odczyty += 1
        if self.ruch > 0:
            self.ruch -= 1
            return (self.poz[0], self.poz[1] + (self.ruch % 2), self.poz[2])      # „chodzi”: pole zmienia się między odczytami
        return self.poz

    def krok(self, klawisz):
        dx, dy = self.KIER[klawisz]
        n = (self.poz[0] + dx, self.poz[1] + dy, self.poz[2])
        self.kroki.append(klawisz)
        if n == self.h and not self.otwarte:
            return None
        self.poz = n
        return n

    def otworz(self, dx, dy):
        self.uzycia.append((self.poz[0] + dx, self.poz[1] + dy, self.poz[2]))
        if self.otwieraja:
            self.otwarte = not self.otwarte


PL = S.Planer(wyprawa.Trasownik(MP), DANE["laczniki"], drzwi=S.drzwi_miasta(DANE), mapa=MP)
sprawdz("9a drzwi miasta z danych: Frodo, Xodet i bank Suzy; Planer zna ich dwa boki (oś x dla Froda, oś y dla Xodeta i banku)",
        S.drzwi_miasta(DANE) == [FRODO, XODET, BANKD] and PL.drzwi == {FRODO: ((32364, 32208, 7), (32366, 32208, 7)),
                                                                     XODET: ((32400, 32216, 7), (32400, 32218, 7)),
                                                                     BANKD: ((32319, 32252, 7), (32319, 32254, 7))}, PL.drzwi)
t0 = _time.monotonic()
d_jedz = PL.droga(PRZYB, P["jedzenie"])
d_blan = PL.droga(PRZYB, P["blanki"])
d_wyj = PL.droga(P["blanki"], PRZYB)
czas = _time.monotonic() - t0
sprawdz("9b Planer z drzwiami: droga do Frodo i Xodeta (i z powrotem) istnieje, zawiera kafelek drzwi dokładnie raz, kończy się na polu stania",
        d_jedz and d_blan and d_wyj and d_jedz.count(FRODO) == 1 and d_blan.count(XODET) == 1 and d_wyj.count(XODET) == 1
        and tuple(d_jedz[-1]) == P["jedzenie"] and tuple(d_blan[-1]) == P["blanki"] and tuple(d_wyj[-1]) == PRZYB, (d_jedz, d_blan))
sprawdz("9c ten sam cel BEZ drzwi w planerze = brak drogi (dlatego stary serwis odmawiał)",
        S.Planer(wyprawa.Trasownik(MP), DANE["laczniki"]).droga(PRZYB, P["jedzenie"]) is None)
sprawdz("9d koszt planowania z drzwiami: 3 trasy w mniej niż 5 s (zalew spójności odrzuca pary odcięte drzwiami; bez niego 13-16 s na trasę)",
        czas < 5.0, round(czas, 1))
d_bank = PL.droga(PRZYB, P["bank"])
d_bank_wr = PL.droga(P["bank"], PRZYB)
sprawdz("9p plan z przybycia w depo do banku Suzy przechodzi przez drzwi (32319,32253,7) dokładnie raz, od północy, i kończy się na polu stania (32319,32256,7); "
        "w drugą stronę też; bez drzwi w planerze brak drogi",
        d_bank and d_bank_wr and tuple(d_bank[0]) == PRZYB and tuple(d_bank[-1]) == BANK_STOI and d_bank.count(BANKD) == 1
        and d_bank[d_bank.index(BANKD) - 1] == (32319, 32252, 7) and d_bank_wr.count(BANKD) == 1 and tuple(d_bank_wr[-1]) == PRZYB
        and S.Planer(wyprawa.Trasownik(MP), DANE["laczniki"]).droga(PRZYB, P["bank"]) is None, (d_bank, d_bank_wr))
cz_b = S.podziel_na_drzwiach(d_bank, PL.drzwi)
sprawdz("9q podział trasy do banku: marsz do pola przed drzwiami (32319,32252), drzwi, marsz do Suzy; kafelek drzwi tylko w odcinku „drzwi”",
        [c[0] for c in cz_b] == ["idz", "drzwi", "idz"] and cz_b[0][1][-1] == (32319, 32252, 7) and cz_b[1][1:] == ((32319, 32252, 7), BANKD, (32319, 32254, 7))
        and all(BANKD not in c[1] for c in cz_b if c[0] == "idz"), cz_b)
czesci = S.podziel_na_drzwiach(d_jedz, PL.drzwi)
sprawdz("9e podział trasy na drzwiach: marsz do pola przed drzwiami (32366,32208), drzwi, marsz do Frodo; żaden odcinek marszu nie zawiera drzwi",
        [c[0] for c in czesci] == ["idz", "drzwi", "idz"] and czesci[0][1][-1] == (32366, 32208, 7)
        and czesci[1][1:] == ((32366, 32208, 7), FRODO, (32364, 32208, 7)) and czesci[2][1][0] == (32364, 32208, 7)
        and all(FRODO not in c[1] for c in czesci if c[0] == "idz"), czesci)

# przejdz_drzwi
S_OTW.clear()
w = SwiatDrzwi((32366, 32208, 7), FRODO)
r = S.przejdz_drzwi(w, (32366, 32208, 7), FRODO, (32364, 32208, 7), log=lambda *_: None, otworz=w.otworz, spij=BEZ_SPANIA)
sprawdz("9f zamknięte drzwi (24.10: najpierw 2 kroki bez skutku, potem jedno Use, krok na kafelek, krok za nie), postać stoi za drzwiami",
        r is True and w.uzycia == [FRODO] and w.kroki == ["Left"] * 4 and w.poz == (32364, 32208, 7) and w.otwarte, (r, w.uzycia, w.kroki, w.poz))
S_OTW.clear()
w = SwiatDrzwi((32366, 32208, 7), FRODO, otwarte=True)
r = S.przejdz_drzwi(w, (32366, 32208, 7), FRODO, (32364, 32208, 7), log=lambda *_: None, otworz=w.otworz, spij=BEZ_SPANIA)
sprawdz("9g drzwi już otwarte: przechodzimy i drzwi zostają otwarte (Use na otwartych by je zamknęło)",
        r is True and w.otwarte and w.poz == (32364, 32208, 7), (r, w.uzycia, w.kroki, w.otwarte))
S_OTW.clear()
w = SwiatDrzwi((32400, 32216, 7), XODET)
r = S.przejdz_drzwi(w, (32400, 32216, 7), XODET, (32400, 32218, 7), log=lambda *_: None, otworz=w.otworz, spij=BEZ_SPANIA)
sprawdz("9h drzwi Xodeta (oś y): 2 kroki bez skutku, Use, krok w dół, krok w dół", r is True and w.kroki == ["Down"] * 4 and w.poz == (32400, 32218, 7), (r, w.kroki))
S_OTW.clear()
w = SwiatDrzwi((32364, 32208, 7), FRODO)
r = S.przejdz_drzwi(w, (32364, 32208, 7), FRODO, (32366, 32208, 7), log=lambda *_: None, otworz=w.otworz, spij=BEZ_SPANIA)
sprawdz("9i przejście w drugą stronę (wyjście ze sklepu): 2 kroki bez skutku, Use dokładnie na drzwiach, krok w prawo dwa razy",
        r is True and w.uzycia == [FRODO] and w.kroki == ["Right"] * 4 and w.poz == (32366, 32208, 7), (r, w.uzycia, w.kroki))
S_OTW.clear()
w = SwiatDrzwi((32366, 32208, 7), FRODO, otwieraja=False)
e = zglasza(lambda: S.przejdz_drzwi(w, (32366, 32208, 7), FRODO, (32364, 32208, 7), log=lambda *_: None, otworz=w.otworz, spij=BEZ_SPANIA))
sprawdz("9j drzwi, które się nie otwierają: SerwisBlad('drzwi') po co najwyżej DRZWI_PROB próbach, nie pętla bez końca, postać nie weszła w ścianę",
        e and e.krok == "drzwi" and len(w.uzycia) <= S.DRZWI_PROB and len(w.kroki) <= S.DRZWI_PROB and w.poz == (32366, 32208, 7), (e, w.uzycia, w.kroki))
S_OTW.clear()
w = SwiatDrzwi((32366, 32208, 7), FRODO, ruch=3)
r = S.przejdz_drzwi(w, (32366, 32208, 7), FRODO, (32364, 32208, 7), log=lambda *_: None, otworz=w.otworz, spij=BEZ_SPANIA)
sprawdz("9k postać jeszcze się porusza: Use dopiero, gdy pozycja przestała się zmieniać (dwa takie same odczyty); potem przejście",
        r is True and w.odczyty > 3 and w.poz == (32364, 32208, 7) and len(w.uzycia) == 1, (r, w.odczyty, w.uzycia))
S_OTW.clear()
S_OTW.clear(); S_OTW.add(FRODO)
w = SwiatDrzwi((32366, 32208, 7), FRODO, otwarte=False)
r = S.przejdz_drzwi(w, (32366, 32208, 7), FRODO, (32364, 32208, 7), log=lambda *_: None, otworz=w.otworz, spij=BEZ_SPANIA)
sprawdz("9n drzwi znane jako otwarte, ale ktoś je zamknął: sam krok nie wchodzi, więc Use (jedno), potem przejście",
        r is True and w.uzycia == [FRODO] and w.poz == (32364, 32208, 7) and w.kroki[0] == "Left" and len(w.kroki) == 4, (r, w.uzycia, w.kroki))
S_OTW.clear()
w = SwiatDrzwi((32366, 32208, 7), FRODO, otwarte=True)
r = S.przejdz_drzwi(w, (32366, 32208, 7), FRODO, (32364, 32208, 7), log=lambda *_: None, otworz=w.otworz, spij=BEZ_SPANIA)
sprawdz("9r (24.10, wydra) NIEZNANE drzwi, które są otwarte: ZERO Use (najpierw krok; dawniej Use na starcie je zamykało)",
        r is True and w.uzycia == [] and w.otwarte and w.poz == (32364, 32208, 7), (r, w.uzycia, w.kroki))
S_OTW.clear(); S_OTW.add(FRODO)
w = SwiatDrzwi((32366, 32208, 7), FRODO, otwarte=True)
r = S.przejdz_drzwi(w, (32366, 32208, 7), FRODO, (32364, 32208, 7), log=lambda *_: None, otworz=w.otworz, spij=BEZ_SPANIA)
sprawdz("9o drzwi znane jako otwarte i otwarte: ZERO Use (nie zamykamy ich), przejście od razu", r is True and w.uzycia == [] and w.otwarte, (r, w.uzycia))
w = SwiatDrzwi((32360, 32208, 7), FRODO)
e = zglasza(lambda: S.przejdz_drzwi(w, (32366, 32208, 7), FRODO, (32364, 32208, 7), log=lambda *_: None, otworz=w.otworz, spij=BEZ_SPANIA))
sprawdz("9l postać nie stoi przed drzwiami: SerwisBlad bez Use i bez kroku", e and e.krok == "drzwi" and w.uzycia == [] and w.kroki == [], (e, w.uzycia))


class ChodzAtrapa:
    """Marsz po odcinku bez drzwi = teleport na ostatni punkt (kafelek drzwi w odcinku to błąd podziału trasy)."""

    def __init__(self, swiat):
        self.sw, self.odcinki, self.tol = swiat, [], []

    def __call__(self, punkty, tol=0):
        assert not any(tuple(q) in (FRODO, XODET, BANKD) for q in punkty), "kafelek drzwi w odcinku marszu"
        self.odcinki.append((tuple(punkty[0]), tuple(punkty[-1])))
        self.tol.append(tol)
        self.sw.poz = tuple(punkty[-1])
        return True


S_OTW.clear()
w = SwiatDrzwi(PRZYB, FRODO)
ch = ChodzAtrapa(w)
ok_ = S.idz_z_drzwiami(w, d_jedz, PL.drzwi, ch, 0, log=lambda *_: None, otworz=w.otworz, spij=BEZ_SPANIA)
sprawdz("9m marsz do Frodo przez zamknięte drzwi: dwa odcinki marszu (przed drzwiami dokładnie na polu), Use raz, stoimy na polu stania",
        ok_ is True and w.poz == P["jedzenie"] and len(ch.odcinki) == 2 and ch.tol[0] == 0 and w.uzycia == [FRODO], (ok_, ch.odcinki, w.uzycia, w.poz))

# --- 10. pełny serwis Thais na prawdziwym planerze i atrapie świata -----------------------------------------------------------


class SwiatMiasta:
    """Troje drzwi (Frodo, Xodet, bank Suzy), wszystkie zamknięte na starcie; pozycja = pole postaci; zlicza Use i przejścia."""

    def __init__(self, start):
        self.poz, self.drzwi, self.uzycia, self.przejscia = tuple(start), {FRODO: False, XODET: False, BANKD: False}, [], []

    def pozycja(self):
        return self.poz

    def krok(self, klawisz):
        dx, dy = SwiatDrzwi.KIER[klawisz]
        n = (self.poz[0] + dx, self.poz[1] + dy, self.poz[2])
        if n in self.drzwi and not self.drzwi[n]:
            return None
        if n in self.drzwi:
            self.przejscia.append(n)
        self.poz = n
        return n

    def otworz(self, dx, dy):
        h = (self.poz[0] + dx, self.poz[1] + dy, self.poz[2])
        self.uzycia.append(h)
        if h in self.drzwi:
            self.drzwi[h] = not self.drzwi[h]


def pelny_serwis(dane=DANE):
    sw = SwiatMiasta(PRZYB)
    a = AkcjeAtrapa()
    ch = ChodzAtrapa(sw)

    def chodz(punkty, tol=0):
        return S.idz_z_drzwiami(sw, punkty, PL.drzwi, ch, tol, log=lambda *_: None, otworz=sw.otworz, spij=BEZ_SPANIA)

    sr = S.Serwis(dane, a, PL, lambda: sw.poz, chodz, log=lambda *_: None, spij=BEZ_SPANIA)
    return sr, a, sw, ch


S_OTW.clear()
sr, a, sw, ch = pelny_serwis()
e = zglasza(lambda: sr.uruchom())
kupno = [x for x in a.log if isinstance(x, tuple) and x[0] == "kup"]
sprawdz("10a pełny serwis Thais z bankiem i przez oba sklepy: zakupy Frodo (ham) -> Gorn -> Xodet (blanki), „buy ” u Frodo i Xodeta, bez błędu",
        e is None and kupno == [("kup", "Frodo", "ham", 5, "buy "), ("kup", "Gorn", "backpack", 1), ("kup", "Xodet", "blank rune", 20, "buy ")], (e, a.log))
sprawdz("10b trzy pary drzwi (bank, Frodo, Xodet): każde przekroczone dwa razy (wejście i wyjście), każde otwarte jednym Use, bank pierwszy; "
        "bank Suzy wywołany raz, przed depo; koniec na przybyciu w depo",
        sw.przejscia.count(BANKD) == 2 and sw.przejscia.count(FRODO) == 2 and sw.przejscia.count(XODET) == 2 and len(sw.przejscia) == 6
        and sw.uzycia == [BANKD, FRODO, XODET] and sw.poz == PRZYB and a.log.count(("bank", "Suzy")) == 1
        and [x[0] for x in a.log if isinstance(x, tuple)][:2] == ["bank", "depo"],
        (sw.przejscia, sw.uzycia, sw.poz))
sprawdz("10c wynik: wszystkie kroki ok (bank, depo, jedzenie, backpack, blanki, wyjscie)",
        sr.wynik == {"bank": "ok", "depo": "ok", "jedzenie": "ok", "backpack": "ok", "blanki": "ok", "wyjscie": "ok"}, sr.wynik)

# Mechanizm „miasto nie ma kroku” zostaje sprawdzony na kopii danych Thais bez banku (Thais bank MA od 22.10; to samo dotyczy każdego
# miasta bez wpisu banku, np. dane sprzed pomiaru).
DANE_BEZ_BANKU = copy.deepcopy(DANE)
del DANE_BEZ_BANKU["przystanki"]["bank"]
DANE_BEZ_BANKU["kolejnosc"] = [k for k in DANE["kolejnosc"] if k != "bank"]
S_OTW.clear()
sr, a, sw, ch = pelny_serwis()
e = zglasza(lambda: sr.uruchom(["bank", "depo", "jedzenie", "backpack", "blanki", "wyjscie"]))
sprawdz("10d refill z bankiem (domyślne kroki refill.sh) w Thais: bez błędu, bank zrobiony pierwszy, wszystkie kroki ok",
        e is None and sr.wynik.get("bank") == "ok" and ("bank", "Suzy") in a.log and sr.wynik.get("blanki") == "ok", (e, sr.wynik, a.log))
S_OTW.clear()
sr, a, sw, ch = pelny_serwis(DANE_BEZ_BANKU)
e = zglasza(lambda: sr.uruchom(["bank", "depo", "jedzenie", "backpack", "blanki", "wyjscie"]))
sprawdz("10d2 dane bez kroku bank, refill bez --pomin-brakujace: czytelny błąd startu, zero inputu i ruchu", e and e.krok == "start" and "bank" in e.powod
        and a.log == [] and sw.uzycia == [], (e, a.log))
S_OTW.clear()
sr, a, sw, ch = pelny_serwis(DANE_BEZ_BANKU)
e = zglasza(lambda: sr.uruchom(["bank", "depo", "jedzenie", "backpack", "blanki", "wyjscie"], pomin_brakujace=True))
sprawdz("10e dane bez kroku bank, pomin_brakujace: bank pominięty (nie ma go w wyniku), reszta zrobiona, bez wywołania banku",
        e is None and "bank" not in sr.wynik and sr.wynik.get("blanki") == "ok" and not any(isinstance(x, tuple) and x[0] == "bank" for x in a.log),
        (e, sr.wynik, a.log))
S_OTW.clear()
sr, a, sw, ch = pelny_serwis()
e = zglasza(lambda: sr.uruchom(["bank", "wyjscie"], pomin_brakujace=True))
sprawdz("10d3 24.10 powrót po samym cap (REFILL_KROKI=bank,wyjscie) w Thais: bank zrobiony, bez depo, jedzenia, backpacka i blanków",
        e is None and sr.wynik.get("bank") == "ok" and ("bank", "Suzy") in a.log and "depo" not in sr.wynik and "blanki" not in sr.wynik
        and not any(isinstance(x, tuple) and x[0] in ("depo", "kup") for x in a.log), (e, sr.wynik, a.log))
ED_ = json.loads((KAT / "trasy" / "serwis_edron.json").read_text())
sed2 = S.Serwis(ED_, AkcjeAtrapa(), Planer0(), lambda: (0, 0, 7), lambda *a_, **k: True, log=lambda *_: None)
sed2.uruchom(["bank", "depo"], pomin_brakujace=True)
sprawdz("10f Edron z pomin_brakujace: bank nadal wykonany (flaga pomija tylko kroki, których miasto nie ma)",
        "bank" in sed2.wynik and any(isinstance(x, tuple) and x[0] == "bank" for x in sed2.akcje.log), (sed2.wynik, sed2.akcje.log))

sprawdz("10g wybierz_miasto(None, pozycja): przybycie Thais -> thais, depo Edron -> edron, Rook -> dawny domyślny edron",
        S.wybierz_miasto(None, PRZYB) == "thais" and S.wybierz_miasto(None, edron_depo) == "edron" and S.wybierz_miasto(None, (32061, 32180, 7)) == "edron")
sprawdz("10h jawne miasto w innym mieście nadal błąd (edron w Thais), jawne thais w Thais ok",
        zglasza(lambda: S.wybierz_miasto("edron", PRZYB)) is not None and S.wybierz_miasto("thais", PRZYB) == "thais")
sh_ref = (KAT / "refill.sh").read_text()
sprawdz("10i refill.sh: domyślnie pełna lista kroków i --pomin-brakujace do serwis.sh",
        'KROKI="${REFILL_KROKI:-bank,depo,jedzenie,backpack,blanki,wyjscie}"' in sh_ref and '--kroki "$KROKI" --pomin-brakujace' in sh_ref)

# --- wynik -------------------------------------------------------------------------------------------------------------------

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
