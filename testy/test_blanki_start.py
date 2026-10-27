import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""27.10: blanki do pojemnika na runy na starcie bota (blanki_start.py, spec N9a). Offline: atrapy planu/pamięci/widoku/przeciągania,
zero inputu do gry, zero plików instancji (wyłączniki w katalogu tymczasowym). Uruchom: python3 -I testy/test_blanki_start.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from PIL import Image, ImageDraw  # noqa: E402

import blanki_start as B  # noqa: E402
import loot  # noqa: E402

ok = True
LOG = []


def sprawdz(opis, warunek, info=""):
    global ok
    print(("OK    " if warunek else "BŁĄD "), opis, "" if warunek else info)
    ok &= bool(warunek)


def log(*a):
    LOG.append(" ".join(str(x) for x in a))


class Sl:
    def __init__(self, i):
        self.i, self.srodek = i, (10 + i, 10)


class Okno:
    def __init__(self, kontener, widoczne):
        self.kontener, self.sloty = kontener, [Sl(i) for i in range(widoczne)]


def kon(numer, nazwa, ident, poj, przedm):
    return {"numer": numer, "nazwa": nazwa, "id": ident, "pojemnosc": poj,
            "przedmioty": [{"slot": s, "id": i, "ilosc": 1} for s, i in przedm]}


BLANK, UH, ROPE = 3147, 3160, 3003


def plan(plecak_przedm=((0, BLANK), (1, BLANK), (2, ROPE)), runy_przedm=((0, UH),), poj_runy=8, wid_runy=8, wid_plecak=8,
         bez_plecaka=False, bez_runow=False):
    return {"plecak": None if bez_plecaka else Okno(kon(1, "backpack", 2854, 8, plecak_przedm), wid_plecak),
            "runy": None if bez_runow else Okno(kon(0, "purple backpack", 2868, poj_runy, runy_przedm), wid_runy)}


class Atrapy:
    """Licznik wywołań: przeciąganie (przenies_fn) i odczytów widoku; nic nie dotyka gry."""
    def __init__(self, wynik=2, stwory=None):
        self.przenies, self.widok, self.pauzy, self.wynik = [], 0, [], wynik
        self.stwory = stwory if stwory is not None else []

    def przenies_fn(self, ids=None, maks=None, log=print):
        self.przenies.append((ids, maks))
        return self.wynik

    def stwory_fn(self):
        self.widok += 1
        s = self.stwory(self.widok) if callable(self.stwory) else self.stwory
        return s, (100, 100, 7), "Gracz"


def start(at, plan_=None, **kw):
    LOG.clear()
    k = dict(plan_fn=lambda: plan_ if plan_ is not None else plan(), stwory_fn=at.stwory_fn, przenies_fn=at.przenies_fn,
             pauza=lambda s: at.pauzy.append(s), stop_fn=lambda: False, stop_reczny_fn=lambda: False, uh_fn=lambda: True)
    k.update(kw)
    return B.uruchom(None, log, **k)


# 1. blanki w plecaku + wolne pole -> jedno wywołanie przenies_do_runow z limitem 30 i ID z ID_RUN_W_POJEMNIKU
at = Atrapy(wynik=2)
st, opis, n = start(at)
sprawdz("1a blanki + wolne pole: przeniesiono, jedno wywołanie", st == "przeniesiono" and n == 2 and len(at.przenies) == 1, (st, opis, at.przenies))
sprawdz("1b limit 30 i ID run z loot.ID_RUN_W_POJEMNIKU", at.przenies[0] == (tuple(sorted(loot.ID_RUN_W_POJEMNIKU)), 30), at.przenies)
sprawdz("1c log: Blanki na starcie: przeniesiono 2", any(l.startswith("Blanki na starcie: przeniesiono 2") for l in LOG), LOG)

# 2. brak blanków -> bez wywołania, linia powodu
at = Atrapy()
st, opis, n = start(at, plan(plecak_przedm=((0, ROPE), (1, 3031))))
sprawdz("2a brak blanków: bez wywołania, pominięto", st == "pominieto" and not at.przenies and n == 0, (st, at.przenies))
sprawdz("2b brak blanków: jedna linia powodu", len(LOG) == 1 and "Blanki na starcie: pominięto" in LOG[0] and "nie ma blanków" in LOG[0], LOG)
at = Atrapy()
st, _, _ = start(at, plan(plecak_przedm=((9, BLANK),), wid_plecak=8))
sprawdz("2c blank poza widocznymi polami plecaka: bez wywołania", st == "pominieto" and not at.przenies and "poza widocznymi" in LOG[0], LOG)

# 3. brak wolnego pola (pojemnik pełny 8/8; 20/20) -> jedna linia, bez prób, bez wywołania i bez czekania na widok
at = Atrapy()
pelny = tuple((i, UH) for i in range(8))
st, opis, n = start(at, plan(runy_przedm=pelny))
sprawdz("3a pełny pojemnik: bez prób", st == "pominieto" and not at.przenies and at.widok == 0, (st, at.przenies, at.widok))
sprawdz("3b pełny pojemnik: jedna czytelna linia z (N/M)", len(LOG) == 1 and
        LOG[0] == "przenoszenie blanków na starcie: brak wolnego pola w pojemniku na runy (8/8), zostawiam", LOG)
at = Atrapy()
start(at, plan(runy_przedm=tuple((i, UH) for i in range(20)), poj_runy=20, wid_runy=20))
sprawdz("3c pojemnik 20/20: (20/20), bez wywołania", not at.przenies and "(20/20), zostawiam" in LOG[0], LOG)
# wolne pole jest, ale poza widocznymi (okno ucięte oknem zwłok/panelem: widoczne 4 pola, wszystkie zajęte, pojemność 8)
at = Atrapy()
start(at, plan(runy_przedm=tuple((i, UH) for i in range(4)), poj_runy=8, wid_runy=4))
sprawdz("3d wolne pole tylko poza widokiem okna: traktowane jak brak (4/8)", not at.przenies and "(4/8), zostawiam" in LOG[0], LOG)

# 4. brak jednego z okien -> bez klików (przenies_fn nie wołane), jedna linia
for opis_t, kw in (("plecaka", dict(bez_plecaka=True)), ("pojemnika na runy", dict(bez_runow=True))):
    at = Atrapy()
    st, _, _ = start(at, plan(**kw))
    sprawdz(f"4 brak okna {opis_t}: pominięto bez klików", st == "pominieto" and not at.przenies and at.widok == 0 and len(LOG) == 1, (st, LOG))
at = Atrapy()
st, _, _ = start(at, {"plecak": Okno(None, 8), "runy": Okno(None, 8)})
sprawdz("4c okna rozpoznane tylko z obrazu (bez kontenera z pamięci): bez klików", st == "pominieto" and not at.przenies, LOG)
at = Atrapy()
st, _, _ = start(at, {})
sprawdz("4d pusty plan: bez klików", st == "pominieto" and not at.przenies, LOG)

# 5. tryb bez run -> pomijane (UH_AKTYWNY != 1), nawet bez odczytu planu
at = Atrapy()
odczyty = []
st, _, _ = start(at, uh_fn=lambda: False, plan_fn=lambda: odczyty.append(1) or plan())
sprawdz("5a UH_AKTYWNY=0: pominięto, ani odczytu, ani wywołania", st == "pominieto" and not at.przenies and not odczyty and "nie robi run" in LOG[0], LOG)
tmp = Path(tempfile.mkdtemp(prefix="blanki_start_test_"))
for tekst, oczek in (('{"UH_AKTYWNY": 1}', True), ('{"UH_AKTYWNY": 0}', False), ('{}', False), ('{"UH_AKTYWNY": "1"}', False),
                     ('{"UH_AKTYWNY": true}', False), ('{"UH_AKTYWNY": 7}', False), ('nie json', False)):
    (tmp / "na_zywo.json").write_text(tekst)
    sprawdz(f"5b pokrętło {tekst!r} -> {oczek}", B.robi_runy(tmp / "na_zywo.json") is oczek)
sprawdz("5c brak pliku na_zywo.json -> False", B.robi_runy(tmp / "nie_ma.json") is False)

# 6. STOP / STOP_RECZNY / --bez-ruchu -> pomijane
at = Atrapy()
st, _, _ = start(at, stop_fn=lambda: True)
sprawdz("6a STOP: pominięto", st == "pominieto" and not at.przenies and "STOP" in LOG[0], LOG)
at = Atrapy()
st, _, _ = start(at, stop_reczny_fn=lambda: True)
sprawdz("6b STOP_RECZNY: pominięto", st == "pominieto" and not at.przenies and "STOP_RECZNY" in LOG[0], LOG)
at = Atrapy()
st, _, _ = start(at, bez_ruchu=True)
sprawdz("6c --bez-ruchu: pominięto", st == "pominieto" and not at.przenies, LOG)
stopy = iter([False, True])           # STOP pojawia się tuż przed przeciąganiem (po czekaniu na spokój)
at = Atrapy()
st, _, _ = start(at, stop_fn=lambda: next(stopy))
sprawdz("6d STOP tuż przed przeciąganiem: bez wywołania", st == "pominieto" and not at.przenies, (st, LOG))

# 7. zagrożenie w widoku
mob = {"nazwa": "Troll", "x": 103, "y": 100, "z": 7, "hp": 100, "gracz": False}
at = Atrapy(stwory=[mob])
zegar = iter(range(0, 100, 2))        # fałszywy zegar: co wywołanie +2 s
st, _, _ = start(at, zegar=lambda: float(next(zegar)))
sprawdz("7a żywy potwór w widoku przez cały czas: rezygnacja, bez przeciągania", st == "pominieto" and not at.przenies and "Troll" in LOG[0], (st, LOG))
sprawdz("7b czekał krótko (<= ~5 s), nie w nieskończoność", 1 <= at.widok <= 5 and all(p <= 2 for p in at.pauzy), (at.widok, at.pauzy))
at = Atrapy(stwory=lambda n: [mob] if n < 3 else [])
st, _, _ = start(at)
sprawdz("7c potwór odchodzi po 2 odczytach: przenosi", st == "przeniesiono" and len(at.przenies) == 1 and at.widok == 3, (st, at.widok, LOG))
inny = {"nazwa": "Obcy", "x": 100, "y": 105, "z": 7, "hp": 100, "gracz": True}
at = Atrapy(stwory=[inny])
st, _, _ = start(at, zegar=lambda: 1e9 if at.widok else 0.0)
sprawdz("7d cudzy gracz w widoku: rezygnacja", st == "pominieto" and not at.przenies and "gracz Obcy" in LOG[0], LOG)
swoj = {"nazwa": "Gracz", "x": 100, "y": 100, "z": 7, "hp": 100, "gracz": True}
dalekie = [{"nazwa": "Troll", "x": 130, "y": 100, "z": 7, "hp": 100, "gracz": False},        # poza widokiem
           {"nazwa": "Troll", "x": 101, "y": 100, "z": 8, "hp": 100, "gracz": False},         # inne piętro
           {"nazwa": "Troll", "x": 101, "y": 100, "z": 7, "hp": 0, "gracz": False}]           # martwy
sprawdz("7e zagrozenia: własna postać, dalekie, inne piętro, martwy = spokój", B.zagrozenia([swoj] + dalekie, (100, 100, 7), "Gracz") == [])
sprawdz("7f zagrozenia: potwór na granicy widoku liczy się", len(B.zagrozenia([dict(mob, x=108, y=106)], (100, 100, 7), "Gracz")) == 1
        and B.zagrozenia([dict(mob, x=109)], (100, 100, 7), "Gracz") == [])
sprawdz("7g zagrozenia: uszkodzony wpis nie wywraca", B.zagrozenia([{"nazwa": "X"}, None.__class__], (1, 1, 1), "G") == [])
at = Atrapy()
at.stwory_fn = lambda: (_ for _ in ()).throw(OSError("brak gniazda"))
st, _, _ = start(at)
sprawdz("7h brak odczytu widoku: nie ruszamy myszą", st == "pominieto" and not at.przenies and "nie znam widoku" in LOG[0], LOG)

# 8. wyjątki w środku nie przerywają startu
def zly_plan():
    raise RuntimeError("pamięć padła")
at = Atrapy()
st, _, _ = start(at, plan_fn=zly_plan)
sprawdz("8a wyjątek odczytu planu: pominięto, nie rzuca", st == "pominieto" and not at.przenies and "pamięć padła" in LOG[0], LOG)
at = Atrapy()
at.przenies_fn = lambda **k: (_ for _ in ()).throw(RuntimeError("drag padł"))
st, _, _ = start(at)
sprawdz("8b wyjątek przeciągania: stan blad, nie rzuca", st == "blad" and any("nie wyszło" in l for l in LOG), (st, LOG))


class Zatrzymano(Exception):          # nazwa jak bot.Zatrzymano: STOP ma przejść
    pass


def stop_w_planie():
    raise Zatrzymano("plik STOP")


at = Atrapy()
try:
    start(at, plan_fn=stop_w_planie)
    przeszlo = False
except Zatrzymano:
    przeszlo = True
sprawdz("8c Zatrzymano (STOP) w środku przechodzi wyżej", przeszlo)
B._URUCHOMIONO = False
try:
    B.przy_starcie(None, log, plan_fn=stop_w_planie, uh_fn=lambda: True, stop_fn=lambda: False, stop_reczny_fn=lambda: False, _wymus=True)
    przeszlo = False
except Zatrzymano:
    przeszlo = True
sprawdz("8d Zatrzymano przechodzi także przez przy_starcie", przeszlo)

# 9. przy_starcie: najwyżej raz, wyłączniki, testy
bazowe = dict(plan_fn=lambda: plan(), przenies_fn=None, uh_fn=lambda: True, stop_fn=lambda: False, stop_reczny_fn=lambda: False,
              pauza=lambda s: None, _wymus=True)
B._URUCHOMIONO = False
LOG.clear()
at = Atrapy()
bazowe.update(przenies_fn=at.przenies_fn, stwory_fn=at.stwory_fn)
w1 = B.przy_starcie(None, log, **dict(bazowe))
w2 = B.przy_starcie(None, log, **dict(bazowe))
w3 = B.przy_starcie(None, log, **dict(bazowe))
sprawdz("9a najwyżej raz na proces: jedno przeniesienie, kolejne wywołania None", w1 and w1[0] == "przeniesiono" and w2 is None and w3 is None
        and len(at.przenies) == 1, (w1, w2, at.przenies))
B._URUCHOMIONO = False
sprawdz("9b RETRONIC_TESTY bez _wymus: hook nic nie robi", B.przy_starcie(None, log, **{k: v for k, v in bazowe.items() if k != "_wymus"}) is None
        and len(at.przenies) == 1 and B._URUCHOMIONO is False)

# 10. wyłączniki: env i pliki (katalogi tymczasowe, żadnej instancji)
stan, wsp = Path(tempfile.mkdtemp(prefix="bs_stan_")), Path(tempfile.mkdtemp(prefix="bs_wsp_"))
sprawdz("10a domyślnie włączone", B.wylaczony(env={}, stan=stan, wspolne=wsp) is None)
sprawdz("10b RETRONIC_BLANKI_START=0 wyłącza", "RETRONIC_BLANKI_START=0" == B.wylaczony(env={"RETRONIC_BLANKI_START": "0"}, stan=stan, wspolne=wsp))
sprawdz("10c RETRONIC_BLANKI_START=1 nie wyłącza", B.wylaczony(env={"RETRONIC_BLANKI_START": "1"}, stan=stan, wspolne=wsp) is None)
(stan / "BLANKI_START_OFF").write_text("")
sprawdz("10d plik w katalogu instancji wyłącza", (B.wylaczony(env={}, stan=stan, wspolne=wsp) or "").startswith("plik "))
(stan / "BLANKI_START_OFF").unlink()
(wsp / "BLANKI_START_OFF").write_text("")
sprawdz("10e plik wspólny wyłącza", (B.wylaczony(env={}, stan=stan, wspolne=wsp) or "").startswith("plik "))
sprawdz("10f plik w innej instancji nie wyłącza tej", B.wylaczony(env={}, stan=Path(tempfile.mkdtemp()), wspolne=Path(tempfile.mkdtemp())) is None)
# przy_starcie z plikiem wyłącznika (podmiana instancja.S na katalogi tymczasowe): zero odczytów i zero przeciągania
import instancja  # noqa: E402
stare = instancja.S
instancja.S = type("S", (), {"stan": stan, "wspolne": wsp, "stop_reczny": stan / "STOP_RECZNY"})()
B._URUCHOMIONO = False
LOG.clear()
at = Atrapy()
odczyty = []
w = B.przy_starcie(None, log, **dict(bazowe, przenies_fn=at.przenies_fn, stwory_fn=at.stwory_fn, plan_fn=lambda: odczyty.append(1) or plan()))
sprawdz("10g przy_starcie z plikiem wyłącznika: wyłączone, jedna linia, bez odczytu i przeciągania",
        w is None and not at.przenies and not odczyty and len(LOG) == 1 and "wyłączone" in LOG[0], (w, LOG))
(wsp / "BLANKI_START_OFF").unlink()
sprawdz("10h _stop_reczny czyta plik instancji", B._stop_reczny() is False)
(stan / "STOP_RECZNY").write_text("")
sprawdz("10i _stop_reczny widzi plik STOP_RECZNY", B._stop_reczny() is True)
instancja.S = stare

# 11. prawdziwy loot.plan na syntetycznym zrzucie + atrapa pamięci (jak test_loot_runy): ocena() czyta pola prawdziwego planu
def okno_syn(im, x, y, wiersze, zajete=()):
    d = ImageDraw.Draw(im)
    for r in range(wiersze):
        for c in range(4):
            x0, y0 = x + c * 37, y + r * 37
            d.rectangle((x0, y0, x0 + 33, y0 + 33), outline=loot.RAMKA)
            if r * 4 + c in zajete:
                d.rectangle((x0 + 8, y0 + 8, x0 + 24, y0 + 24), fill=(200, 60, 160))
                d.rectangle((x0 + 12, y0 + 12, x0 + 20, y0 + 20), fill=(60, 200, 120))


def kont(numer, nazwa, ident, poj, *przedm):
    return {"numer": numer, "nazwa": nazwa, "id": ident, "pojemnosc": poj,
            "przedmioty": [{"slot": i, "id": a, "ilosc": b} for i, (a, b) in enumerate(przedm)]}


im = Image.new("RGB", (734, 910), (20, 20, 20))
okno_syn(im, 580, 360, 2, zajete=(0, 1, 2))
okno_syn(im, 580, 560, 2, zajete=(0, 1))
PAMIEC = [kont(0, "purple backpack", 2868, 8, (UH, 1), (UH, 1)), kont(1, "backpack", 2854, 8, (BLANK, 40), (BLANK, 40), (ROPE, 1))]
loot._zapytaj = lambda z: {"kontenery": PAMIEC}
p = loot.plan(im, [])
kod, opis, dane = B.ocena(p, set(loot.ID_RUN_W_POJEMNIKU))
sprawdz("11a prawdziwy plan: ruszaj, 2 blanki widoczne, 6 wolnych pól", kod == "ruszaj" and dane["widoczne_blanki"] == 2 and dane["wolne"] == 6, (kod, opis, dane))
PAMIEC[0] = kont(0, "purple backpack", 2868, 8, *[(UH, 1)] * 8)
im = Image.new("RGB", (734, 910), (20, 20, 20))
okno_syn(im, 580, 360, 2, zajete=(0, 1, 2))
okno_syn(im, 580, 560, 2, zajete=tuple(range(8)))
p = loot.plan(im, [])
kod, opis, dane = B.ocena(p, set(loot.ID_RUN_W_POJEMNIKU))
sprawdz("11b prawdziwy plan, pojemnik pełny 8/8: brak_pola", kod == "brak_pola" and "(8/8)" in opis, (kod, opis, dane))
PAMIEC[:] = [PAMIEC[1]]
p = loot.plan(im, [])
kod, opis, _ = B.ocena(p, set(loot.ID_RUN_W_POJEMNIKU))
sprawdz("11c prawdziwy plan, pamięć bez pojemnika na runy: nie ruszaj", kod in ("brak_pojemnika", "brak_plecaka"), (kod, opis))

# 12. spięcie w mozg.main: hook po okna_start, przed wznowieniem wyprawy; opakowany tak, że błąd nie przerywa startu
zrodlo = (Path(__file__).resolve().parent.parent / "mozg.py").read_text()
i_okna, i_bl, i_wznow = (zrodlo.find(s) for s in ("okna_start.przy_starcie(log)", "blanki_start.przy_starcie(postac, log, bez_ruchu=a.bez_ruchu)",
                                                  "if wznow_start.WLACZONE and not _stoj_wlaczony()"))
sprawdz("12a mozg.main: okna_start -> blanki_start -> wznowienie wyprawy", 0 < i_okna < i_bl < i_wznow, (i_okna, i_bl, i_wznow))
fragment = zrodlo[i_bl - 120:i_bl + 400]
sprawdz("12b hook w try, Zatrzymano przechodzi, inny wyjątek tylko do logu", "except bot.Zatrzymano:\n        raise" in fragment
        and "except Exception as e:" in fragment and "Blanki na starcie: pominięto" in fragment, fragment)


# 13. układ z odchyd 27.10: dwa okna „Blue backpack” uznane za runy, plecaków 0 (okno A: 5 blanków + puste, okno B: 16 blanków + 4 inne)
GOLD, BAG, CZERWONE1, CZERWONE2, LOPATA = 3031, 1987, 2300, 2301, 3457


def okno_runy(numer, nazwa, ident, poj, przedm, wid=None):
    o = Okno(kon(numer, nazwa, ident, poj, przedm), wid or poj)
    o.rola = "runy"
    return o


def plan_dwa(a, b):
    """Plan jak z loot.plan w układzie odchyd: plecak None, runy = pierwsze okno runy, oba okna na liście."""
    return {"plecak": None, "runy": a, "okna": [a, b]}


A5 = okno_runy(0, "Blue backpack", 2868 + 1, 20, [(i, BLANK) for i in range(5)])
B16 = okno_runy(1, "Blue backpack", 2868 + 1, 20, [(i, BLANK) for i in range(16)] + [(16, GOLD), (17, BAG), (18, CZERWONE1), (19, LOPATA)])
kod, opis, _ = B.ocena(plan_dwa(A5, B16), set(loot.ID_RUN_W_POJEMNIKU))
sprawdz("13a bez rozstrzygnięcia ten układ to brak_plecaka (stan dzisiejszy klasyfikatora)", kod == "brak_plecaka", (kod, opis))
r = B.rozstrzygnij_dwa_runy(plan_dwa(A5, B16))
sprawdz("13b rozstrzygnięcie: plecak łupu = okno B (z przedmiotami innymi niż runy), pojemnik = okno A",
        r["plecak"] is B16 and r["runy"] is A5 and "plecak łupu = kontener 1" in r["rozstrzygniecie"] and "kontener 0" in r["rozstrzygniecie"], r)
sprawdz("13c rozstrzygnięcie nie zmienia planu wejściowego (kopia)", plan_dwa(A5, B16)["plecak"] is None)
r2 = B.rozstrzygnij_dwa_runy(plan_dwa(B16, A5))
sprawdz("13d kolejność okien nie ma znaczenia", r2["plecak"] is B16 and r2["runy"] is A5)
kod, opis, dane = B.ocena(r, set(loot.ID_RUN_W_POJEMNIKU))
sprawdz("13e ocena po rozstrzygnięciu: ruszaj, 16 blanków, 15 wolnych pól", kod == "ruszaj" and dane["widoczne_blanki"] == 16 and dane["wolne"] == 15, (kod, opis, dane))
at = Atrapy(wynik=15)
st, opis, n = start(at, plan_dwa(A5, B16))
sprawdz("13f start na układzie odchyd: jedno przeniesienie, log o rozstrzygnięciu", st == "przeniesiono" and n == 15 and len(at.przenies) == 1
        and any("plecak łupu = kontener 1" in l for l in LOG), (st, LOG))
# niejednoznaczne: oba tylko z runami / oba z innymi / okno z nazwy runowe / trzy okna
A_run = okno_runy(0, "Blue backpack", 2870, 20, [(i, BLANK) for i in range(5)])
B_run = okno_runy(1, "Blue backpack", 2870, 20, [(i, BLANK) for i in range(18)])
at = Atrapy()
st, opis, _ = start(at, plan_dwa(A_run, B_run))
sprawdz("13g oba okna tylko z blankami: nic nie robi, dokładny powód", st == "pominieto" and not at.przenies and "tylko runy" in LOG[-1], LOG)
A_inne = okno_runy(0, "Blue backpack", 2870, 20, [(0, BLANK), (1, BLANK), (2, BLANK), (3, BAG)])
at = Atrapy()
st, opis, _ = start(at, plan_dwa(A_inne, B16))
sprawdz("13h oba okna z przedmiotami innymi niż runy: nic nie robi, powód", st == "pominieto" and not at.przenies and "oba okna mają przedmioty inne" in LOG[-1], LOG)
A_zloto = okno_runy(0, "Blue backpack", 2870, 20, [(i, BLANK) for i in range(5)] + [(5, GOLD)])
B_zloto = okno_runy(1, "Blue backpack", 2870, 20, [(i, BLANK) for i in range(16)] + [(16, GOLD)])
at = Atrapy()
st, _, _ = start(at, plan_dwa(A_zloto, B_zloto))
sprawdz("13i samo złoto/tarcza nie czyni okna plecakiem łupu: nic nie robi", st == "pominieto" and not at.przenies, LOG)
purple = okno_runy(0, "Purple backpack", 2868, 20, [(i, BLANK) for i in range(5)] + [(5, BAG)])
at = Atrapy(wynik=3)
st, _, _ = start(at, plan_dwa(purple, B16))
sprawdz("13j Purple backpack z nazwy z obcym przedmiotem nigdy nie jest plecakiem łupu: łup = B", st == "przeniesiono" and
        B.rozstrzygnij_dwa_runy(plan_dwa(purple, B16))["plecak"] is B16)
purple2 = okno_runy(1, "Purple backpack", 2868, 20, [(0, BLANK), (1, BAG)])
at = Atrapy()
st, _, _ = start(at, plan_dwa(purple, purple2))
sprawdz("13k dwa Purple z nazwy: brak plecaka łupu, nic nie robi", st == "pominieto" and not at.przenies, LOG)
C = okno_runy(2, "Blue backpack", 2870, 20, [(0, BLANK), (1, BLANK), (2, BLANK), (3, BAG)])
at = Atrapy()
st, _, _ = start(at, {"plecak": None, "runy": A5, "okna": [A5, B16, C]})
sprawdz("13l trzy okna runy bez plecaka: nic nie robi, powód", st == "pominieto" and not at.przenies and "3 okna" in LOG[-1], LOG)
sprawdz("13m plan z plecakiem i plan z jednym oknem runy: bez zmian", B.rozstrzygnij_dwa_runy(plan())["plecak"] is not None
        and "rozstrzygniecie" not in B.rozstrzygnij_dwa_runy(plan()) and B.rozstrzygnij_dwa_runy({"plecak": None, "runy": A5, "okna": [A5]}).get("plecak") is None)

# 13n. prawdziwy loot.plan na zrzucie z dwoma oknami: klasyfikator ogólny zostaje (plecak None), rozstrzygnięcie robi swoje
import inspect  # noqa: E402
sprawdz("13n loot.przenies_do_runow: nowy argument plan_fn opcjonalny, domyślnie None (zachowanie bez zmian)",
        inspect.signature(loot.przenies_do_runow).parameters["plan_fn"].default is None)
im2 = Image.new("RGB", (734, 910), (20, 20, 20))
okno_syn(im2, 580, 100, 5, zajete=range(5))
okno_syn(im2, 580, 400, 5, zajete=range(20))
PAMIEC[:] = [kont(0, "Blue backpack", 2870, 20, *[(BLANK, 1)] * 5),
             kont(1, "Blue backpack", 2870, 20, *([(BLANK, 1)] * 16 + [(GOLD, 50), (BAG, 1), (CZERWONE1, 1), (LOPATA, 1)]))]
pr = loot.plan(im2, [])
sprawdz("13o prawdziwy klasyfikator: oba okna to runy, plecaka brak (powód: reguła 75% z 15.10)", pr["plecak"] is None
        and [o.rola for o in pr["okna"]] == ["runy", "runy"], (pr["plecak"], [o.rola for o in pr["okna"]], pr["pamiec"]))
rr = B._plan_rozstrzygniety(im2, [])
sprawdz("13p _plan_rozstrzygniety na prawdziwym planie: plecak = okno z 20 przedmiotami, runy = okno z 5", rr["plecak"] is not None
        and len(rr["plecak"].kontener["przedmioty"]) == 20 and len(rr["runy"].kontener["przedmioty"]) == 5, rr.get("niejednoznaczne"))
kod, opis, dane = B.ocena(rr, set(loot.ID_RUN_W_POJEMNIKU))
sprawdz("13q ocena prawdziwego planu: ruszaj, 16 blanków, 15 wolnych", kod == "ruszaj" and dane["widoczne_blanki"] == 16 and dane["wolne"] == 15, (kod, opis, dane))

# 14. drugi wyzwalacz: naprawa W TRAKCIE pracy (UH/loot zgłaszają brak_plecaka)
B._reset_naprawy()
T0 = 1000.0
zglos_ok = dict(uh_fn=lambda: True, wylaczony_fn=lambda: None, _wymus=True)
sprawdz("14a zglos w testach bez _wymus: odrzucone (cavebot w testach nie naprawia układu)", B.zglos("x", T0) is False and not B.oczekuje())
sprawdz("14b zglos: przyjęte, oczekuje; drugie zgłoszenie przy czekającym odrzucone", B.zglos("UH: brak_plecaka", T0, **zglos_ok) is True
        and B.oczekuje() and B.zglos("loot", T0, **zglos_ok) is False)
sprawdz("14c postać bez run: zgłoszenie odrzucone", (B._reset_naprawy() or B.zglos("x", T0, uh_fn=lambda: False, wylaczony_fn=lambda: None, _wymus=True)) is False)
sprawdz("14d wyłącznik (env/plik): zgłoszenie odrzucone", B.zglos("x", T0, uh_fn=lambda: True, wylaczony_fn=lambda: "RETRONIC_BLANKI_START=0", _wymus=True) is False)

inj_ok = lambda at_: dict(plan_fn=lambda: plan_dwa(A5, B16), stwory_fn=at_.stwory_fn, przenies_fn=at_.przenies_fn, pauza=lambda s: None,
                          stop_fn=lambda: False, stop_reczny_fn=lambda: False, uh_fn=lambda: True)
POWIADOMIENIA = []
pow_fn = lambda *a, **k: POWIADOMIENIA.append((a, k)) or True
LOG.clear()
at = Atrapy(wynik=15)
B.zglos("UH: brak_plecaka (zero lub kilka okien plecaka)", T0, **zglos_ok)
w = B.naprawa_w_trakcie(None, log, T0, pow_fn, **inj_ok(at))
sprawdz("14e naprawa po zgłoszeniu: jedno przeniesienie, bez czekania na widok", w.stan == "przeniesiono" and w.n == 15 and len(at.przenies) == 1
        and not B.oczekuje() and any("Blanki w trakcie pracy: przeniesiono 15" in l for l in LOG), (w, LOG))
sprawdz("14f po udanej naprawie: limit 10 min (zgłoszenie po 100 s odrzucone, po 601 s przyjęte)",
        B.zglos("x", T0 + 100, **zglos_ok) is False and B.zglos("x", T0 + 601, **zglos_ok) is True)
B.naprawa_w_trakcie(None, log, T0 + 601, pow_fn, **{**inj_ok(Atrapy()), "plan_fn": lambda: plan(plecak_przedm=((0, ROPE),))})   # pominięte, próba 1
sprawdz("14g nieudana próba liczy się (1/3), cisza w powiadomieniach", B._NAPRAWA["proby"] == 1 and not POWIADOMIENIA)
t = T0 + 601
for k in range(2):
    t += 601
    B.zglos("x", t, **zglos_ok)
    LOG.clear()
    B.naprawa_w_trakcie(None, log, t, pow_fn, **{**inj_ok(Atrapy()), "plan_fn": lambda: plan(plecak_przedm=((0, ROPE),))})
sprawdz("14h po 3 nieudanych próbach: jedna linia 'naprawa układu nieudana', jedno powiadomienie", sum("naprawa układu nieudana:" in l for l in LOG) == 1
        and len(POWIADOMIENIA) == 1 and "nie ma blanków" in LOG[-1], (LOG, POWIADOMIENIA))
sprawdz("14i dalsze zgłoszenia odrzucone (limit 3 prób na proces): bez pętli", B.zglos("x", t + 10 ** 6, **zglos_ok) is False and not B.oczekuje())

# mob/gracz w widoku: bez naprawy, bez zużycia próby, ponowna próba najwcześniej za 30 s
B._reset_naprawy()
POWIADOMIENIA.clear()
at = Atrapy(stwory=[mob])
B.zglos("UH", T0, **zglos_ok)
LOG.clear()
w = B.naprawa_w_trakcie(None, log, T0, pow_fn, **inj_ok(at))
sprawdz("14j potwór w widoku: brak naprawy i brak czekania, próba nie zużyta", w.stan == "pominieto" and w.przejsciowe and not at.przenies
        and B._NAPRAWA["proby"] == 0 and at.widok == 1, (w, B._NAPRAWA))
sprawdz("14k po rezygnacji ponowna próba dopiero po 30 s", B.zglos("UH", T0 + 10, **zglos_ok) is False and B.zglos("UH", T0 + 31, **zglos_ok) is True)
at = Atrapy(stwory=[inny])
w = B.naprawa_w_trakcie(None, log, T0 + 31, pow_fn, **inj_ok(at))
sprawdz("14l cudzy gracz w widoku: brak naprawy", not at.przenies and w.przejsciowe)
B.zglos("UH", T0 + 70, **zglos_ok)
w = B.naprawa_w_trakcie(None, log, T0 + 70, pow_fn, **{**inj_ok(Atrapy()), "stop_reczny_fn": lambda: True})
sprawdz("14m STOP_RECZNY: brak naprawy, próba nie zużyta", w.przejsciowe and B._NAPRAWA["proby"] == 0)
sprawdz("14n bez zgłoszenia naprawa_w_trakcie nic nie robi (None)", B.naprawa_w_trakcie(None, log, T0, pow_fn, **inj_ok(Atrapy())) is None)

# 15. spięcie z cavebotem: prawdziwe metody Cavebot na atrapie (UH porażka brak_plecaka -> naprawa raz -> UH wznowione)
import cavebot  # noqa: E402


class CB:
    """Atrapa z polami używanymi przez Cavebot._blanki_naprawa_tick / _blanki_zglos."""
    cel = None
    ucieczka = ostrozny = w_poscigu = dojscie_aktywne = False
    pamiec = None
    zwloki_czekajace = []
    wyprawa = None
    postac = None
    aktywnosc_ts = 0

    def __init__(self):
        self.uh_porazki, self.uh_wylaczony_do, self.uh_wyl_porazki_do, self.t = 3, 5000.0, 5000.0, T0
        self.blokada = None

    def zegar(self):
        return self.t

    def _uh_blokada(self, g, poz, teraz, lista=None):
        return self.blokada

    _blanki_zglos = cavebot.Cavebot._blanki_zglos
    _blanki_naprawa_tick = cavebot.Cavebot._blanki_naprawa_tick


B._reset_naprawy()
zglos_orig, uruchom_orig = B.zglos, B.uruchom
B.zglos = lambda powod, teraz, **k: zglos_orig(powod, teraz, **{**zglos_ok, **k})
WOLANIA = []


def uruchom_stub(postac=None, log=print, **kw):
    WOLANIA.append(kw)
    return Wynik_stub.pop(0)


Wynik_stub = []
B.uruchom = uruchom_stub
cb = CB()
cb._blanki_zglos("UH: brak_plecaka (zero lub kilka okien plecaka)")
Wynik_stub.append(B.Wynik("przeniesiono", "przeniesiono 15", 15))
zuzyty = cb._blanki_naprawa_tick({}, (1, 1, 7), [], T0)
sprawdz("15a UH porażka brak_plecaka -> naprawa raz -> licznik porażek 0, pauza po porażkach zdjęta, UH wznowione",
        zuzyty is True and cb.uh_porazki == 0 and cb.uh_wylaczony_do == float("-inf") and len(WOLANIA) == 1, (zuzyty, cb.uh_porazki, cb.uh_wylaczony_do))
sprawdz("15b naprawa w trakcie: czekaj_s=0 i etykieta 'w trakcie pracy'", WOLANIA[0].get("czekaj_s") == 0.0 and WOLANIA[0].get("kiedy") == "w trakcie pracy")
cb._blanki_zglos("UH: brak_plecaka (zero lub kilka okien plecaka)")
sprawdz("15c ponowny brak_plecaka po 0 s: limit 10 min, bez zgłoszenia (nie ma pętli)", not B.oczekuje())
cb.t = T0 + 700
cb.uh_wylaczony_do, cb.uh_wyl_porazki_do = 9999.0, None      # pauza z innego powodu (alarm/brak blank) NIE jest zdejmowana
cb._blanki_zglos("loot: brak_plecaka")
Wynik_stub.append(B.Wynik("przeniesiono", "przeniesiono 2", 2))
cb._blanki_naprawa_tick({}, (1, 1, 7), [], T0 + 700)
sprawdz("15d pauza UH z innego powodu zostaje (tylko pauza po porażkach jest zdejmowana)", cb.uh_wylaczony_do == 9999.0)
cb.t = T0 + 1400
cb._blanki_zglos("loot: brak_plecaka")
for nazwa, ustaw in (("cel w walce", lambda: setattr(cb, "cel", {"id": 1})), ("ucieczka", lambda: setattr(cb, "ucieczka", True)),
                     ("zwłoki czekają", lambda: setattr(cb, "zwloki_czekajace", [(1, 1, 7)])), ("dojście", lambda: setattr(cb, "dojscie_aktywne", True)),
                     ("blokada UH (loot/czar/stan)", lambda: setattr(cb, "blokada", "stan"))):
    cb.cel, cb.ucieczka, cb.zwloki_czekajace, cb.dojscie_aktywne, cb.blokada = None, False, [], False, None
    ustaw()
    ile = len(WOLANIA)
    r = cb._blanki_naprawa_tick({}, (1, 1, 7), [], T0 + 1400)
    sprawdz(f"15e nie w spokoju ({nazwa}): naprawa czeka, zero wywołań", r is False and len(WOLANIA) == ile and B.oczekuje())
cb.cel, cb.ucieczka, cb.zwloki_czekajace, cb.dojscie_aktywne, cb.blokada = None, False, [], False, None


class Wyp:
    def __init__(self, powod):
        self.powod = powod

    def _blokada_startu(self, teraz, poz, lista, **k):
        return self.powod


cb.wyprawa = Wyp("gracz")
ile = len(WOLANIA)
sprawdz("15f wyprawa mówi 'gracz'/'moby' (obcy w pobliżu): naprawa czeka", cb._blanki_naprawa_tick({}, (1, 1, 7), [], T0 + 1400) is False and len(WOLANIA) == ile)
cb.wyprawa = Wyp(None)
Wynik_stub.append(B.Wynik("pominieto", "powód", 0))
r = cb._blanki_naprawa_tick({}, (1, 1, 7), [], T0 + 1400)
sprawdz("15g spokój: naprawa wykonana raz, pominięcie nie zużywa obiegu (UH liczy swoje)", len(WOLANIA) == ile + 1 and r is False and not B.oczekuje())
B.zglos, B.uruchom = zglos_orig, uruchom_orig
B._reset_naprawy()

# 16. spięcie źródłowe w cavebot.py: porażka UH i loot zgłaszają, tick naprawy przed _uh, rozpoznanie pauzy po porażkach
zr_cb = (Path(__file__).resolve().parent.parent / "cavebot.py").read_text()
sprawdz("16a UH: zgłoszenie po wyniku brak_plecaka", 'if str(pw).startswith("brak_plecaka"):\n            self._blanki_zglos(' in zr_cb)
sprawdz("16b loot: zgłoszenie po wyniku brak_plecaka w _zbierz_loot", 'if wynik == "brak_plecaka":\n                    self._blanki_zglos(' in zr_cb)
sprawdz("16c _uh_tick woła naprawę przed _uh", zr_cb.find("if self._blanki_naprawa_tick(g, poz, lista, teraz):") < zr_cb.find("return self._uh(g, poz, lista, teraz)"))
sprawdz("16d pauza po porażkach zapamiętana", "self.uh_wyl_porazki_do = self.uh_wylaczony_do" in zr_cb)


# 17. decyzje z PAMIĘCI (Karol: „dane o ilości wolnych pól ma bezpośrednio”): zero zrzutów i zero myszy, gdy nie ma czego przenosić
import okna_start  # noqa: E402

okna_start._zrzut = lambda: (_ for _ in ()).throw(AssertionError("zrzut ekranu w decyzji z pamięci"))
EKW3 = {"typ": "ekwipunek", "slot": 3}
W3 = {"typ": "kontener", "numer": 1, "w_ekwipunku": 3}


def kont_r(numer, nazwa, ident, przedm, rodzic=None, poj=20):
    k = kon(numer, nazwa, ident, poj, przedm)
    if rodzic:
        k["rodzic"] = rodzic
    return k


def z_pamieci(kontenery):
    loot.kontenery_z_pamieci = lambda: (kontenery, None)


stare_kz = loot.kontenery_z_pamieci
odczyty_ekranu = []
loot._zrzut = lambda mysz: odczyty_ekranu.append(1) or (_ for _ in ()).throw(AssertionError("zrzut w loot"))
loot.ekran.Mysz = lambda *a, **k: (_ for _ in ()).throw(AssertionError("mysz w decyzji z pamięci"))
ZEWN17 = [(i, BLANK) for i in range(13)] + [(13, GOLD), (14, BAG), (15, LOPATA), (16, CZERWONE1)]
plecak_k = kont_r(1, "blue backpack", 2869, ZEWN17, EKW3)
runy_k = kont_r(0, "blue backpack", 2869, [(i, BLANK) for i in range(5)] + [(5, UH)], W3)

# 17a-c. loot.przenies_do_runow: pojemnik pełny / brak blanków -> 0 bez zrzutu i myszy; jedna linia
LOG.clear()
z_pamieci([plecak_k, kont_r(0, "blue backpack", 2869, [(i, UH) for i in range(20)], W3)])
n = loot.przenies_do_runow(log=log)
sprawdz("17a pojemnik na runy 20/20 (pamięć): 0, bez zrzutu i myszy, jedna linia (20/20)", n == 0 and not odczyty_ekranu and len(LOG) == 1
        and "(20/20)" in LOG[0], LOG)
LOG.clear()
z_pamieci([kont_r(1, "blue backpack", 2869, [(0, GOLD), (1, BAG)], EKW3), runy_k])
n = loot.przenies_do_runow(log=log)
sprawdz("17b w plecaku brak blanków (pamięć): 0, bez zrzutu i myszy", n == 0 and not odczyty_ekranu and "nie ma blanków" in LOG[0], LOG)
sprawdz("17c powod_braku_przenoszenia_runow: kontenery None/puste = nie wiadomo (None); są blanki i miejsce = None",
        loot.powod_braku_przenoszenia_runow(set(loot.ID_RUN_W_POJEMNIKU), []) is None
        and loot.powod_braku_przenoszenia_runow(set(loot.ID_RUN_W_POJEMNIKU), [plecak_k, runy_k]) is None)

# 17d. blanki_start.uruchom z domyślnym odczytem (pamięć): zero zrzutów; układ odchyd rozpoznany po położeniu; wywołanie przeniesienia raz
for opis_t, kontenery_t, oczek in (("układ odchyd z rodzicami", [runy_k, plecak_k], "przeniesiono"),
                                   ("pojemnik pełny", [plecak_k, kont_r(0, "blue backpack", 2869, [(i, UH) for i in range(20)], W3)], "pominieto"),
                                   ("brak blanków", [kont_r(1, "blue backpack", 2869, [(0, GOLD)], EKW3), runy_k], "pominieto")):
    z_pamieci(kontenery_t)
    at = Atrapy(wynik=5)
    LOG.clear()
    r = B.uruchom(None, log, stwory_fn=at.stwory_fn, przenies_fn=at.przenies_fn, pauza=lambda s: None, stop_fn=lambda: False,
                  stop_reczny_fn=lambda: False, uh_fn=lambda: True)
    sprawdz(f"17d {opis_t}: {oczek}, bez zrzutu ekranu", r.stan == oczek and not odczyty_ekranu and len(at.przenies) == (1 if oczek == "przeniesiono" else 0), (r, LOG))
# 17e. bez rodziców (stary rdzeń): fallback = rozstrzygnięcie po zawartości dalej działa także z pamięci
z_pamieci([kont_r(0, "blue backpack", 2869, [(i, BLANK) for i in range(5)]), kont_r(1, "blue backpack", 2869, ZEWN17[:13] + [(13, GOLD), (14, BAG), (15, LOPATA), (16, CZERWONE1)])])
at = Atrapy(wynik=5)
LOG.clear()
r = B.uruchom(None, log, stwory_fn=at.stwory_fn, przenies_fn=at.przenies_fn, pauza=lambda s: None, stop_fn=lambda: False,
              stop_reczny_fn=lambda: False, uh_fn=lambda: True)
sprawdz("17e bez pola rodzic: rozstrzygnięcie po zawartości (fallback) z pamięci, bez zrzutu", r.stan == "przeniesiono" and not odczyty_ekranu
        and any("plecak łupu = kontener 1" in l for l in LOG), (r, LOG))
# 17f. brak odczytu pamięci: powód, bez klików
loot.kontenery_z_pamieci = lambda: (None, "pamięć nie widzi otwartych kontenerów")
at = Atrapy()
r = B.uruchom(None, log, stwory_fn=at.stwory_fn, przenies_fn=at.przenies_fn, stop_fn=lambda: False, stop_reczny_fn=lambda: False, uh_fn=lambda: True)
sprawdz("17f brak odczytu pamięci: pominięto, bez klików", r.stan == "pominieto" and not at.przenies and "odczyt nieudany" in r.opis, r)
loot.kontenery_z_pamieci = stare_kz


# 18. cała pętla loot.przenies_do_runow na atrapach (zrzut, mysz, przeciąganie): decyzja z pamięci, weryfikacja po każdym ruchu z pamięci
class MyszAtrapa:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    ekran = None


class Straz:
    def po(self, *a, **k):
        pass


def uruchom_petle(plecak_przedm, runy_przedm, poj_runy=8, wid_runy=8, maks=30):
    pk = kont_r(1, "blue backpack", 2869, plecak_przedm, EKW3)
    rk = kont_r(0, "blue backpack", 2869, runy_przedm, W3, poj=poj_runy)
    stan = {"kontenery": [rk, pk], "dragi": [], "zrzuty": 0}
    z_pamieci_f = lambda: ([dict(k, przedmioty=[dict(q) for q in k["przedmioty"]]) for k in stan["kontenery"]], None)
    stare = (loot.kontenery_z_pamieci, loot._zrzut, loot.plan, loot._przeciagnij_pewnie, loot._straznik, loot._pauza, loot._okno_ilosci_ok, loot.ekran.Mysz)

    def zrzut(mysz):
        stan["zrzuty"] += 1
        return object()

    def plan_f(obraz, lista):
        pk_, rk_ = stan["kontenery"][1], stan["kontenery"][0]
        return {"plecak": Okno(pk_, 8), "runy": Okno(rk_, wid_runy)}

    def drag(mysz, z, do, obraz, log, straz, nazwa):
        pk_, rk_ = stan["kontenery"][1], stan["kontenery"][0]
        ib = next(q for q in pk_["przedmioty"] if q["id"] == BLANK)
        pk_["przedmioty"].remove(ib)
        wolny = next(i for i in range(rk_["pojemnosc"]) if i not in {q["slot"] for q in rk_["przedmioty"]})
        rk_["przedmioty"].append({"slot": wolny, "id": BLANK, "ilosc": 1})
        stan["dragi"].append((z, do))
        return True

    loot.kontenery_z_pamieci, loot._zrzut, loot.plan, loot._przeciagnij_pewnie = z_pamieci_f, zrzut, plan_f, drag
    loot._straznik, loot._pauza, loot._okno_ilosci_ok, loot.ekran.Mysz = lambda log: Straz(), lambda *a: None, lambda *a, **k: True, MyszAtrapa
    LOG.clear()
    try:
        n = loot.przenies_do_runow(maks=maks, log=log)
    finally:
        loot.kontenery_z_pamieci, loot._zrzut, loot.plan, loot._przeciagnij_pewnie, loot._straznik, loot._pauza, loot._okno_ilosci_ok, loot.ekran.Mysz = stare
    return n, stan


n, st_ = uruchom_petle([(i, BLANK) for i in range(4)] + [(4, GOLD)], [(0, UH)])
sprawdz("18a pętla: 4 blanki przeniesione, każdy ruch na pierwszy wolny slot z pamięci (1,2,3,4)", n == 4 and [d[1] for d in st_["dragi"]] == [(10 + k, 10) for k in (1, 2, 3, 4)], (n, st_["dragi"], LOG))
sprawdz("18b zrzut tylko do współrzędnych: po jednym na ruch + jeden końcowy NIE (decyzja z pamięci kończy pętlę po ostatnim blanku)", st_["zrzuty"] <= 5, st_["zrzuty"])
n, st_ = uruchom_petle([(i, BLANK) for i in range(6)], [(i, UH) for i in range(6)], poj_runy=8)
sprawdz("18c wolne 2 pola, 6 blanków: przeniesiono 2, potem jedna linia o braku miejsca, bez ruchu myszy na zapas", n == 2 and len(st_["dragi"]) == 2
        and sum("brak wolnego" in l for l in LOG) == 1, (n, LOG))
n, st_ = uruchom_petle([(i, BLANK) for i in range(6)], [(i, UH) for i in range(8)], poj_runy=8)
sprawdz("18d pojemnik pełny 8/8: 0 ruchów i 0 zrzutów", n == 0 and not st_["dragi"] and st_["zrzuty"] == 0 and "(8/8)" in LOG[0], (n, st_, LOG))
n, st_ = uruchom_petle([(i, BLANK) for i in range(6)], [(0, UH)], poj_runy=8, wid_runy=1)
sprawdz("18e wolne pola w pamięci, ale poza widocznym oknem (widoczne 1): 0 ruchów, linia 'widocznego pola'", n == 0 and not st_["dragi"] and any("widocznego pola" in l for l in LOG), (n, LOG))
n, st_ = uruchom_petle([(i, BLANK) for i in range(3)], [(0, UH)], maks=2)
sprawdz("18f limit przeciągnięć (maks) szanowany", n == 2 and len(st_["dragi"]) == 2, (n, st_["dragi"]))

print("\nWYNIK:", "OK" if ok else "BŁĘDY")
sys.exit(0 if ok else 1)
