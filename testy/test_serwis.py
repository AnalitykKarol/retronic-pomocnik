"""Serwis miasta (serwis.py, serwis_akcje.py, generuj_serwis_edron.py) na atrapach i prawdziwych danych:
planer dróg na prawdziwej mapie, układ panelu na zrzutach z 19.10, rozmowy z NPC odtworzone z logów czatu Karola,
orkiestrator kroków. Nic nie trafia do gry (RETRONIC_TESTY=1, brak XTEST, brak gniazda)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
import types
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import generuj_serwis_edron as G
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


# --- 1. generator danych ------------------------------------------------------------------------------

pkt = [(1, 1, 7), (2, 1, 7), (2, 1, 8), (3, 1, 8), (3, 1, 7), (3, 2, 7), (3, 2, 7), (4, 4, 6)]
l = G.laczniki(pkt)
sprawdz("1a łączniki z nagrania: pary kolejnych punktów o różnym z", [(x["z"], x["do"]) for x in l] ==
        [([2, 1, 7], [2, 1, 8]), ([3, 1, 8], [3, 1, 7]), ([3, 2, 7], [4, 4, 6])], l)
sprawdz("1b depo: 8 stanowisk, wschodnie pierwsze", G.stanowiska_depo()[0] == [33175, 31796, 8] and len(G.stanowiska_depo()) == 8)
DANE = json.load(open(KAT / "trasy" / "serwis_edron.json"))
sprawdz("1c plik danych: 5 przystanków i kolejność z Karola (+ wyjście na końcu)", DANE["kolejnosc"] ==
        ["bank", "depo", "jedzenie", "backpack", "blanki", "wyjscie"] and set(DANE["przystanki"]) == set(DANE["kolejnosc"]) - {"wyjscie"})
sprawdz("1d każdy łącznik zmienia tylko piętro o 1 lub 2, blisko w poziomie",
        all(abs(l["z"][2] - l["do"][2]) == 1 and max(abs(l["z"][0] - l["do"][0]), abs(l["z"][1] - l["do"][1])) <= 3
            for l in DANE["laczniki"]), "łącznik")

# --- 2. planer na prawdziwej mapie ---------------------------------------------------------------------

import mapa as _mapa
if _mapa.PLIK_MAPY.is_file():
    import wyprawa
    planer = S.Planer(wyprawa.Trasownik(_mapa.mapa()), DANE["laczniki"])
    P = {n: tuple(v["stoi"]) for n, v in DANE["przystanki"].items()}
    P["wyjscie"] = tuple(DANE["wyjscie"])
    brak = []
    zle_z = []
    zmiany = {(tuple(x["z"]), tuple(x["do"])) for x in DANE["laczniki"]}
    for a in P:
        for b in P:
            if a == b:
                continue
            d = planer.droga(P[a], P[b])
            if d is None:
                brak.append((a, b))
                continue
            for p, q in zip(d, d[1:]):
                if p[2] != q[2] and (p, q) not in zmiany:
                    zle_z.append((a, b, p, q))
    sprawdz("2a planer: droga między każdą parą przystanków i wyjścia (30 par)", not brak, brak)
    sprawdz("2b planer: zmiana piętra tylko po łączniku z nagrania (nigdy po zgadniętych schodach)", not zle_z, zle_z[:2])
    d = planer.droga(P["blanki"], P["depo"])
    sprawdz("2c planer: z Alexandra (z3) do depo (z8) przez wszystkie piętra wieży", d and [p[2] for p in d][0] == 3
            and d[-1] == P["depo"] and {3, 4, 5, 6, 7, 8} <= {p[2] for p in d}, None if not d else sorted({p[2] for p in d}))
    sprawdz("2d planer: ta sama pozycja = jedna pozycja", planer.droga(P["bank"], P["bank"]) == [P["bank"]])
    sprawdz("2e planer: cel na nieznanym piętrze = None", planer.droga(P["bank"], (33175, 31796, 1)) is None)
    # wnęki depo: pole stania przechodnie, pole na północ (skrzynia) nieprzechodnie, a droga do nich istnieje z wyjścia
    m = _mapa.mapa()
    sprawdz("2f wnęki depo: pole stania przechodnie, północ (skrzynia) nieprzechodnia",
            all(m.przechodnie(x, y, z) and not m.przechodnie(x, y - 1, z) for x, y, z in DANE["depo_stoiska"]), DANE["depo_stoiska"])
else:
    sprawdz("2 plik mapy klienta dostępny (bez niego planera nie da się sprawdzić)", False, str(_mapa.PLIK_MAPY))

# --- 3. układ panelu na zrzutach z 19.10 --------------------------------------------------------------------

from PIL import Image
D = KAT / "testy" / "dane"
for nazwa, oczekiwany, y_ekw in (("panel_brak.png", "brak", 143), ("panel_zwinieta.png", "zwinieta", 163),
                                  ("panel_rozwinieta.png", "rozwinieta", 293)):
    u = A.uklad_panelu(Image.open(D / nazwa))
    sprawdz(f"3 {nazwa}: minimapa {oczekiwany}", u["minimapa"] == oczekiwany, u)
    # przycięcie ma 184 px szerokości: prawo = 180, plecak 81 px od prawej => 99 (= 855 - 756 w pełnym ekranie)
    sprawdz(f"3 {nazwa}: plecak w ekwipunku (99, {y_ekw})", u["plecak_ekw"] is not None and u["plecak_ekw"][0] == 99
            and abs(u["plecak_ekw"][1] - y_ekw) <= 2, u)
sprawdz("3d zrzut bez paska HP: układ nieznany", A.uklad_panelu(Image.new("RGB", (184, 760)))["minimapa"] is None)
sprawdz("3e przycisk zwijania minimapy: 27 px od prawej, y 42", A.przycisk_zwin_minimape(936) == (909, 42))

# --- 4. rozmowy z NPC odtworzone z logów czatu (19.10) ------------------------------------------------------


class Swiat:
    """Atrapa czatu: skrypt NPC reaguje na wysłane teksty; zegar jest wirtualny (spij przesuwa czas)."""

    def __init__(self, nick, npc, odpowiedzi, gubi_pierwsze=False, kanal=""):
        self.t, self.nick, self.npc, self.odp = 0.0, nick, npc, odpowiedzi
        self.kolejka, self.wyslane, self.gubi, self.kanal, self.nr = [], [], gubi_pierwsze, kanal, 0

    def czas(self):
        return self.t

    def spij(self, s):
        self.t += s

    def _dodaj(self, autor, tekst, kanal=""):
        self.nr += 1
        self.kolejka.append({"autor": autor, "tekst": tekst, "kanal": kanal, "czas": "", "nr": self.nr})

    def czat(self, tekst):
        self.wyslane.append(tekst)
        if self.gubi:
            self.gubi = False
            return                                # pierwsza wiadomość zginęła (19.10: `hi` bez echa)
        self._dodaj(self.nick, tekst, self.kanal)
        for wzor, odp in self.odp:
            if wzor == tekst.strip().lower():
                for o in odp if isinstance(odp, list) else [odp]:
                    self._dodaj(self.npc, o)

    def wiadomosci(self):
        w, self.kolejka = self.kolejka, []
        return w

    def rozmowa(self):
        return A.Rozmowa(self.czat, self.wiadomosci, self.nick, log=lambda *_: None, czas=self.czas, spij=self.spij,
                         pomin_zakladki=True)


bank = Swiat("Mastafian", "Ebenizer", [("hi", "Yes? What may I do for you, Mastafian."),
                                       ("change gold", "How many platinum coins do you want to get?"),
                                       ("13", []), ("yes", "Here you are.")])
sprawdz("4a bank (dialog z logu 12:29): hi, change gold, 13, yes", bank.rozmowa().zmien_gold("Ebenizer", 13)
        and bank.wyslane == ["hi", "change gold", "13", "yes"], bank.wyslane)

alex = Swiat("Mastafian", "Alexander", [("hi", "Hi there Mastafian."),
                                        ("20 blank rune", "Do you want to buy 20 blank runes for 200 gold?"),
                                        ("yes", ["Here you are.", "See you."])])
r = alex.rozmowa()
r.powitaj("Alexander")
sprawdz("4b blanki (log 12:50): oferta 20 szt. za 200 gp", r.zamow("Alexander", "20 blank rune", 12, ile=20) == (20, 200))

beat = Swiat("Mastafian", "Beatrice", [("hi", "Welcome Mastafian."),
                                       ("backpack", "Do you want to buy a blue backpack for 20 gold coins?"),
                                       ("yes", ["Here you are.", "See you later."])])
r = beat.rozmowa()
r.powitaj("Beatrice")
sprawdz("4c backpack (log 12:40): „a blue backpack for 20 gold coins” = 1 szt. za 20", r.zamow("Beatrice", "backpack", 25) == (1, 20))

mir = Swiat("Mastafian", "Mirabell", [("hi", "Welcome to the Horn of Plenty, Mastafian."), ("5 ham", []),
                                      ("yes", ["Here it is.", "Come back soon, traveller."])])
r = mir.rozmowa()
r.powitaj("Mirabell")
sprawdz("4d ham u Mirabell: brak linii oferty w logu = ślepe yes (jeśli dozwolone)",
        r.zamow("Mirabell", "5 ham", 12, ile=5, slepy_yes=True) == (5, None) and mir.wyslane[-1] == "yes", mir.wyslane)
mir2 = Swiat("Mastafian", "Mirabell", [("hi", "Welcome."), ("5 ham", [])])
r = mir2.rozmowa()
r.powitaj("Mirabell")
e = zglasza(lambda: r.zamow("Mirabell", "5 ham", 12, ile=5))
sprawdz("4e bez oferty i bez pozwolenia na ślepe yes: błąd, nic nie kupione", e and "brak oferty" in e.powod and "yes" not in mir2.wyslane, mir2.wyslane)

zgubione = Swiat("Mastafian", "Alexander", [("hi", "Hi there Mastafian.")], gubi_pierwsze=True)
sprawdz("4f zgubione `hi` (19.10 12:49): ponawia i dostaje powitanie", zgubione.rozmowa().powitaj("Alexander") is not None
        and zgubione.wyslane == ["hi", "hi"], zgubione.wyslane)
e = zglasza(lambda: Swiat("Mastafian", "Bob", [], kanal="Trade").rozmowa().powiedz("hi"))
sprawdz("4g wiadomość na kanale Trade: błąd (nie wysyłamy dalej)", e and "kanał" in e.powod, e)
glucha = Swiat("Mastafian", "Alexander", [("hi", [])])
e = zglasza(lambda: glucha.rozmowa().powitaj("Alexander"))
sprawdz("4h NPC milczy: błąd „nie odpowiada na hi”", e and "nie odpowiada" in e.powod, e)
zajety = Swiat("Mastafian", "Alexander", [("hi", ["I am talking to Rogerdodger, wait a moment."])])
e = zglasza(lambda: zajety.rozmowa().powitaj("Alexander"))
sprawdz("4i NPC zajęty: czeka i kończy błędem po trzech próbach, nie kupuje", e and zajety.wyslane == ["hi", "hi", "hi"], zajety.wyslane)
drogo = Swiat("Mastafian", "Alexander", [("hi", "Hi."), ("20 blank rune", "Do you want to buy 20 blank runes for 900 gold?")])
r = drogo.rozmowa()
r.powitaj("Alexander")
e = zglasza(lambda: r.zamow("Alexander", "20 blank rune", 12, ile=20))
sprawdz("4j za droga oferta: odmawia (no), nie mówi yes", e and "za droga" in e.powod and drogo.wyslane[-1] == "no", drogo.wyslane)
inna = Swiat("Mastafian", "Alexander", [("hi", "Hi."), ("20 blank rune", "Do you want to buy 7 blank runes for 70 gold?")])
r = inna.rozmowa()
r.powitaj("Alexander")
e = zglasza(lambda: r.zamow("Alexander", "20 blank rune", 12, ile=20))
sprawdz("4k oferta na inną liczbę sztuk: odmawia", e and "oferta na 7" in e.powod and inna.wyslane[-1] == "no", inna.wyslane)
brak_gold = Swiat("Mastafian", "Alexander", [("hi", "Hi."), ("20 blank rune", "Do you want to buy 20 blank runes for 200 gold?"),
                                            ("yes", "Sorry, you do not have enough gold.")])
r = brak_gold.rozmowa()
r.powitaj("Alexander")
e = zglasza(lambda: r.zamow("Alexander", "20 blank rune", 12, ile=20))
sprawdz("4l NPC odmawia sprzedaży (brak gold): błąd o braku potwierdzenia", e and "potwierdzenia" in e.powod and "enough" in e.powod, e)
podszyty = Swiat("Mastafian", "Alexander", [("hi", [])])
podszyty._dodaj("Rogerdodger", "Hi there Mastafian.")
e = zglasza(lambda: podszyty.rozmowa().powitaj("Alexander"))
sprawdz("4m cudza linia „Hi there Mastafian.” od gracza nie jest powitaniem NPC", e and "nie odpowiada" in e.powod, e)
stare = Swiat("Mastafian", "Alexander", [], gubi_pierwsze=True)
stare._dodaj("Mastafian", "yes")                              # echo wcześniejszego „yes”, jeszcze w buforze czatu
stare.rozmowa().powiedz("yes")
sprawdz("4n stare echo „yes” nie potwierdza nowego: pierwsze wysłanie zginęło, więc ponawia i potwierdza dopiero prawdziwe",
        stare.wyslane == ["yes", "yes"], stare.wyslane)

# --- 5. orkiestrator -----------------------------------------------------------------------------------------


class AkcjeAtrapa:
    def __init__(self, bagi_potrzebne=True, zajete=(), depo_nie_otwiera=(), majatek=1000, blad_depo=None, majatek_glowny=None, wolne=20):
        self.log, self.bagi, self.zajete, self.nie = [], bagi_potrzebne, set(map(tuple, zajete)), set(map(tuple, depo_nie_otwiera))
        self.poz, self._majatek, self.blad_depo = [0, 0, 7], majatek, blad_depo
        self._majatek_glowny, self._wolne = majatek_glowny, wolne

    def sprawdz_start(self):
        self.log.append("start")

    def przygotuj_okna(self):
        self.log.append("okna")

    def majatek(self, tylko_glowny=False):
        return self._majatek_glowny if tylko_glowny and self._majatek_glowny is not None else self._majatek

    def wolne_w_bagu(self):
        return self._wolne

    def brakuje(self, co, cel):
        return {"ham": cel, "blank rune": cel, "backpack": 1 if self.bagi else 0}[co]

    def bank_zmien(self, npc):
        self.log.append(("bank", npc))

    def pole_zajete(self, pole):
        return tuple(pole) in self.zajete

    def depo_zloz(self, zostaw_platinum, odejdz=None):
        self.log.append(("depo", tuple(self.poz), zostaw_platinum))
        if self.blad_depo:
            raise SerwisBlad("depo", self.blad_depo)
        return tuple(self.poz) not in self.nie

    def kup(self, npc, co, ile):
        self.log.append(("kup", npc, co, ile))

    def rezerwa_na_blanki(self, blanki):
        self.rezerwy = getattr(self, "rezerwy", []) + [blanki]
        return 42.0

    def cel_ham(self, cel, rezerwa_oz):
        self.rezerwa_ham = rezerwa_oz
        return min(cel, getattr(self, "limit_ham", cel))

    def potrzeba_baga(self):
        return self.bagi

    def przenies_blanki(self):
        self.log.append("przenies_blanki")


class Planer0:
    """Planer atrapa: droga = [od, do] (bez mapy), koszt = Chebyshev."""

    def droga(self, od, do):
        return [tuple(od), tuple(do)]


def zbuduj(akcje, dane=DANE, chodz_ok=True, start=(0, 0, 7), stan_plik=None, teraz=None):
    stoi = {"poz": tuple(start)}

    def pozycja():
        return stoi["poz"]

    def chodz(punkty, tol=0):
        stoi.setdefault("tol", []).append(tol)
        stoi["poz"] = punkty[-1] if chodz_ok else stoi["poz"]
        akcje.poz = list(stoi["poz"])
        return chodz_ok

    kw = {"stan_plik": stan_plik}
    if teraz:
        kw["teraz"] = teraz
    return S.Serwis(dane, akcje, Planer0(), pozycja, chodz, log=lambda *_: None, **kw), stoi


def nazwy_akcji(a):
    return [x if isinstance(x, str) else (x[2] if x[0] == "kup" else x[0]) for x in a.log]


a = AkcjeAtrapa()
s, st = zbuduj(a)
s.uruchom()
nazwy = nazwy_akcji(a)
sprawdz("5a kolejność wywołań akcji (start, okna, bank, depo, ham, backpack+okna, blanki+okna; wyjście bez akcji)",
        nazwy == ["start", "okna", "bank", "depo", "ham", "backpack", "okna", "okna", "blank rune", "przenies_blanki", "okna"], nazwy)
sprawdz("5b domyślnie kończy na wyjściu z depo (z7)", st["poz"] == tuple(DANE["wyjscie"]), st)
sprawdz("5c depo zostawia 3 platinum", any(isinstance(x, tuple) and x[0] == "depo" and x[2] == 3 for x in a.log), a.log)
sprawdz("5d cele zakupów: 5 ham, 20 blanków", ("kup", "Mirabell", "ham", 5) in a.log and ("kup", "Alexander", "blank rune", 20) in a.log)
sprawdz("5e dokładność: do depo tolerancja 0, do NPC tolerancja 0, wyjście 2", st["tol"][:-1] == [0] * (len(st["tol"]) - 1) and st["tol"][-1] == 2, st["tol"])

a = AkcjeAtrapa()
a.limit_ham = 2
s, st = zbuduj(a)
s.uruchom(["jedzenie", "blanki"])
sprawdz("5e2 cap: ham ograniczone do tyle, by zostało 42 oz na bag z blankami", ("kup", "Mirabell", "ham", 2) in a.log and a.rezerwa_ham == 42.0, a.log)
a = AkcjeAtrapa()
s, st = zbuduj(a)
s.uruchom(["jedzenie"])
sprawdz("5e3 cap: bez kroku blanki ham bez rezerwy", ("kup", "Mirabell", "ham", 5) in a.log and not hasattr(a, "rezerwa_ham"), a.log)

a = AkcjeAtrapa()
s, st = zbuduj(a)
s.uruchom(["blanki", "jedzenie"])
nazwy = nazwy_akcji(a)
sprawdz("5f kolejność edytowalna (--kroki): blanki przed jedzeniem", nazwy.index("blank rune") < nazwy.index("ham"), nazwy)

a = AkcjeAtrapa(bagi_potrzebne=False)
s, st = zbuduj(a)
s.uruchom(["backpack"])
sprawdz("5g bag już jest: backpack nie kupuje (idempotentnie)", not any(isinstance(x, tuple) and x[0] == "kup" for x in a.log), a.log)

# depo: najbliższe stanowisko według drogi od bieżącej pozycji
STOISKA = [tuple(x) for x in DANE["depo_stoiska"]]        # od wschodu na zachód
a = AkcjeAtrapa()
s, st = zbuduj(a, start=(33160, 31796, 8))
s.uruchom(["depo"])
sprawdz("5h depo: od zachodu bierze zachodnie stanowisko (najbliższe), nie stałą kolejność", ("depo", STOISKA[-1], 3) in a.log, a.log)
a = AkcjeAtrapa()
s, st = zbuduj(a, start=(33176, 31796, 8))
s.uruchom(["depo"])
sprawdz("5i depo: od wschodu bierze wschodnie stanowisko", ("depo", STOISKA[0], 3) in a.log, a.log)

a = AkcjeAtrapa(zajete=[STOISKA[0], STOISKA[1]])
s, st = zbuduj(a, start=(33176, 31796, 8))
s.uruchom(["depo"])
sprawdz("5j depo: zajęte stanowiska pomijane, bierze trzecie", ("depo", STOISKA[2], 3) in a.log, a.log)

a = AkcjeAtrapa(depo_nie_otwiera=[STOISKA[0]])
s, st = zbuduj(a, start=(33176, 31796, 8))
s.uruchom(["depo"])
sprawdz("5k depo: skrzynia się nie otworzyła -> próbuje następne stanowisko",
        [x for x in a.log if isinstance(x, tuple) and x[0] == "depo"][-1][1] == STOISKA[1], a.log)

a = AkcjeAtrapa(zajete=STOISKA)
s, st = zbuduj(a)
e = zglasza(lambda: s.uruchom(["depo"]))
sprawdz("5l depo: wszystkie zajęte = błąd, nic nie składa", e and e.krok == "depo" and not any(isinstance(x, tuple) for x in a.log), a.log)

a = AkcjeAtrapa(blad_depo="przeciągnięcie nie dało skutku")
s, st = zbuduj(a)
e = zglasza(lambda: s.uruchom(["depo"]))
sprawdz("5m depo: błąd składania kończy serwis, nie próbuje kolejnych stanowisk", e and "skutku" in e.powod
        and len([x for x in a.log if isinstance(x, tuple) and x[0] == "depo"]) == 1, a.log)

a = AkcjeAtrapa()
s, st = zbuduj(a, chodz_ok=False)
e = zglasza(lambda: s.uruchom(["depo"]))
sprawdz("5n depo: nie doszedł na stanowisko = błąd (nie szuka po cichu innych), zero prób składania", e and "nie doszedłem" in e.powod
        and not any(isinstance(x, tuple) for x in a.log), (e, a.log))
a = AkcjeAtrapa()
s, st = zbuduj(a, chodz_ok=False)
e = zglasza(lambda: s.uruchom(["bank", "depo"]))
sprawdz("5o nie doszedł do banku: błąd w kroku bank, dalsze kroki się nie wykonują", e and e.krok == "bank"
        and not any(isinstance(x, tuple) for x in a.log), (e, a.log))

a = AkcjeAtrapa()
s, st = zbuduj(a)
e = zglasza(lambda: s.uruchom(["bank", "kosmos"]))
sprawdz("5p nieznany krok: błąd przed jakąkolwiek akcją", e and "nieznane" in e.powod and a.log == [], (e, a.log))

class PlanerBrak:
    def droga(self, od, do):
        return None
a = AkcjeAtrapa()
s, st = zbuduj(a)
s.planer = PlanerBrak()
e = zglasza(lambda: s.uruchom(["bank"]))
sprawdz("5q brak drogi: czytelny błąd", e and "brak drogi" in e.powod, e)

# budżet
a = AkcjeAtrapa(majatek=100)
s, st = zbuduj(a)
e = zglasza(lambda: s.uruchom())
sprawdz("5r budżet: 100 gp na kolejkę za ~270 = błąd przed jakąkolwiek akcją w grze", e and "za mało pieniędzy" in e.powod
        and not any(isinstance(x, tuple) for x in a.log), (e, a.log))
a = AkcjeAtrapa(majatek=5000)
s, st = zbuduj(a)
s.uruchom()
sprawdz("5s budżet: 5000 gp (po depo zostaje 300) wystarcza", ("kup", "Alexander", "blank rune", 20) in a.log)
a = AkcjeAtrapa(majatek=200)
s, st = zbuduj(a)
e = zglasza(lambda: s.uruchom(["jedzenie", "blanki"]))
sprawdz("5t budżet: 200 gp na 5 ham + 20 blanków (szacunek 250) = błąd bez zakupów", e and "za mało" in e.powod
        and not any(isinstance(x, tuple) for x in a.log), (e, a.log))
a = AkcjeAtrapa(majatek=250)
s, st = zbuduj(a)
s.uruchom(["jedzenie", "blanki"])
sprawdz("5t' budżet: 250 gp (równo z szacunkiem) wystarcza", ("kup", "Alexander", "blank rune", 20) in a.log)

# wznawianie po awarii
import tempfile
plik = Path(tempfile.mkdtemp()) / "stan.json"
zegar = {"t": 1000.0}
a = AkcjeAtrapa(blad_depo=None)


def pada_na_blankach(*_):
    raise SerwisBlad("kup", "NPC nie sprzedał")


a.przenies_blanki = pada_na_blankach
s, st = zbuduj(a, stan_plik=plik, teraz=lambda: zegar["t"])
e = zglasza(lambda: s.uruchom())
sprawdz("6a przebieg przerwany na blankach: stan zapisany z ukończonymi krokami", e and set(json.load(open(plik))["ukonczone"]) ==
        {"bank", "depo", "jedzenie", "backpack"}, (e, open(plik).read()))
zegar["t"] += 600
a2 = AkcjeAtrapa(bagi_potrzebne=False)      # po pierwszym przebiegu bag na runy leży w plecaku
s2, st2 = zbuduj(a2, stan_plik=plik, teraz=lambda: zegar["t"])
s2.uruchom()
nazwy = nazwy_akcji(a2)
sprawdz("6b ponowne uruchomienie: bank, depo, ham, backpack pominięte (nie kupuje drugi raz, nie odkłada nowego baga)",
        "bank" not in nazwy and "depo" not in nazwy and "ham" not in nazwy and "backpack" not in nazwy and "blank rune" in nazwy, nazwy)
sprawdz("6c po pełnym przebiegu stan = koniec", json.load(open(plik))["koniec"] is True)
a3 = AkcjeAtrapa()
s3, st3 = zbuduj(a3, stan_plik=plik, teraz=lambda: zegar["t"] + 10)
s3.uruchom()
sprawdz("6d po zakończonym przebiegu nowy start robi wszystko od początku", "bank" in nazwy_akcji(a3) and "depo" in nazwy_akcji(a3))
a = AkcjeAtrapa()
a.przenies_blanki = pada_na_blankach
plik2 = Path(tempfile.mkdtemp()) / "stan.json"
s, st = zbuduj(a, stan_plik=plik2, teraz=lambda: zegar["t"])
zglasza(lambda: s.uruchom())
a4 = AkcjeAtrapa()
s4, st4 = zbuduj(a4, stan_plik=plik2, teraz=lambda: zegar["t"] + 4 * 3600)
s4.uruchom()
sprawdz("6e stan starszy niż 3 h jest ignorowany (nowy przebieg od początku)", "bank" in nazwy_akcji(a4), nazwy_akcji(a4))
a6 = AkcjeAtrapa()
a6.przenies_blanki = pada_na_blankach
plik3 = Path(tempfile.mkdtemp()) / "stan.json"
s6, st6 = zbuduj(a6, stan_plik=plik3, teraz=lambda: zegar["t"])
zglasza(lambda: s6.uruchom())
a7 = AkcjeAtrapa()
s7, st7 = zbuduj(a7, stan_plik=plik3, teraz=lambda: zegar["t"] + 5)
s7.uruchom(od_nowa=True)
sprawdz("6f --od-nowa ignoruje stan: robi wszystko", "bank" in nazwy_akcji(a7) and "depo" in nazwy_akcji(a7), nazwy_akcji(a7))
# R3: postęp przerwanego pełnego przebiegu nie ginie, gdy ktoś dokończy ręcznie innymi krokami
a8 = AkcjeAtrapa()
a8.przenies_blanki = pada_na_blankach
plik4 = Path(tempfile.mkdtemp()) / "stan.json"
s8, st8 = zbuduj(a8, stan_plik=plik4, teraz=lambda: zegar["t"])
zglasza(lambda: s8.uruchom())
a9 = AkcjeAtrapa()
s9, st9 = zbuduj(a9, stan_plik=plik4, teraz=lambda: zegar["t"] + 5)
s9.uruchom(["wyjscie"])                     # ręcznie wyszedł z depo, ale blanki nadal niezrobione
a10 = AkcjeAtrapa(bagi_potrzebne=False)     # bag kupiony w przerwanym przebiegu nadal jest
s10, st10 = zbuduj(a10, stan_plik=plik4, teraz=lambda: zegar["t"] + 10)
s10.uruchom()
sprawdz("6g postęp przerwanego pełnego przebiegu nie ginie po ręcznym `--kroki wyjscie`: następny pełny przebieg nie powtarza depo i zakupów",
        "depo" not in nazwy_akcji(a10) and "ham" not in nazwy_akcji(a10) and "bank" not in nazwy_akcji(a10)
        and "blank rune" in nazwy_akcji(a10), nazwy_akcji(a10))
sprawdz("6h po dokończeniu wszystkich kroków stan = koniec", json.load(open(plik4))["koniec"] is True)

# 22.10 invincible: backpack zaliczony BEZ zakupu (postać miała bag), kolejny przebieg: depo odkłada ten bag, a „krok backpack już
# wykonany, pomijam” zostawiało blanki bez miejsca (porażka w kroku blanki). Krok zależny od stanu ocenia się na nowo.
class AkcjeStanowa(AkcjeAtrapa):
    """Atrapa ze stanem baga: depo odkłada bag (miejsce 0), zakup backpacka go przywraca (miejsce 20)."""

    def __init__(self, bag=True, **kw):
        super().__init__(**kw)
        self.bag, self.blanki = bag, 0
        self.bagi = not bag
        self._wolne = 20 if bag else 0

    def depo_zloz(self, zostaw_platinum, odejdz=None):
        wynik = super().depo_zloz(zostaw_platinum, odejdz)
        self.bag, self.bagi, self._wolne, self.blanki = False, True, 0, 0       # bag z blankami poszedł do depo
        return wynik

    def kup(self, npc, co, ile):
        super().kup(npc, co, ile)
        if co == "backpack":
            self.bag, self.bagi, self._wolne = True, False, 20
        if co == "blank rune":
            self.blanki = ile

    def brakuje(self, co, cel):
        if co == "blank rune":
            return max(0, cel - self.blanki)
        return super().brakuje(co, cel)


plik5 = Path(tempfile.mkdtemp()) / "stan.json"
a11 = AkcjeStanowa(bag=True)                       # postać już ma bag (blue backpack): backpack bez zakupu
s11, st11 = zbuduj(a11, stan_plik=plik5, teraz=lambda: zegar["t"])
a11.przenies_blanki = pada_na_blankach             # przebieg 1 pada na blankach, jak 13:13
e = zglasza(lambda: s11.uruchom(["bank", "jedzenie", "backpack", "blanki"]))
sprawdz("6o przebieg 1: backpack zaliczony bez zakupu (bag już był), potem porażka; stan zapisany",
        e and json.load(open(plik5))["ukonczone"] == ["bank", "jedzenie", "backpack"]
        and not any(isinstance(x, tuple) and x[2:3] == ("backpack",) for x in a11.log), (e, nazwy_akcji(a11)))
a12 = AkcjeStanowa(bag=True)
a12.blanki = 0
json.dump({"ukonczone": ["bank", "jedzenie", "backpack"], "koniec": False, "t": zegar["t"]}, open(plik5, "w"))
s12, st12 = zbuduj(a12, stan_plik=plik5, teraz=lambda: zegar["t"] + 420)
e = zglasza(lambda: s12.uruchom(["depo", "backpack", "blanki", "wyjscie"]))
n12 = nazwy_akcji(a12)
sprawdz("6p przebieg 2 (depo odkłada bag): backpack NIE pominięty, kupiony po depo i przed blankami, blanki OK (bez błędu)",
        e is None and "backpack" in n12 and n12.index("depo") < n12.index("backpack") < n12.index("blank rune")
        and s12.wynik.get("backpack") == "ok" and s12.wynik.get("blanki") == "ok", (e, n12, s12.wynik))
sprawdz("6q przebieg 2: bank i jedzenie nadal pominięte (depo ich nie cofa), blanki po zakupie mają 20",
        "bank" not in n12 and "ham" not in n12 and a12.blanki == 20, n12)
a13 = AkcjeStanowa(bag=True)
json.dump({"ukonczone": ["bank", "jedzenie", "backpack"], "koniec": False, "t": zegar["t"]}, open(plik5, "w"))
s13, st13 = zbuduj(a13, stan_plik=plik5, teraz=lambda: zegar["t"] + 420)
s13.uruchom(["backpack", "blanki", "wyjscie"])           # bez depo bag nadal jest: backpack słusznie pominięty
sprawdz("6r bez depo w przebiegu bag dalej leży w plecaku: backpack pominięty (nie kupuje drugiego)",
        s13.wynik.get("backpack") == "pominięty" and ("kup", "Mirabell", "backpack", 1) not in a13.log
        and not any(isinstance(x, tuple) and x[2:3] == ("backpack",) for x in a13.log), (s13.wynik, nazwy_akcji(a13)))

# R1: NPC tuż przy stanowisku nie blokują startu (wznawianie po porażce przy NPC)
# (testy 2* w test_serwis_akcje.py: NPC obok, martwy potwór)

# R2: budżet liczy tylko plecak, gdy bag z pieniędzmi pójdzie do depo
a = AkcjeAtrapa(majatek=700, majatek_glowny=200)
s, st = zbuduj(a)
e = zglasza(lambda: s.uruchom())
sprawdz("6i budżet (R2): 700 gp w sumie, ale 500 gp w bagu na runy (odejdzie do depo), w plecaku 200 = błąd bez zakupów",
        e and "za mało pieniędzy" in e.powod and not any(isinstance(x, tuple) for x in a.log), (e, a.log))
a = AkcjeAtrapa(majatek=700, majatek_glowny=700)
s, st = zbuduj(a)
s.uruchom()
sprawdz("6j budżet (R2): 700 gp w plecaku wystarcza", ("kup", "Alexander", "blank rune", 20) in a.log)

# 22.10 wydra (Thais): "za mało pieniędzy: po depo zostanie 13 gp" mimo 6 platinum w slocie 10 ekwipunku; i budżet nie żąda pieniędzy
# na blanki, które postać ma luzem w plecaku (depo ich nie rusza)
class AkcjeBudzet(AkcjeAtrapa):
    def __init__(self, ekw=0, luzem=0, **kw):
        super().__init__(**kw)
        self.ekw, self.luzem = ekw, luzem

    def majatek_w_ekwipunku(self):
        return self.ekw

    def majatek(self, tylko_glowny=False):
        return super().majatek(tylko_glowny) + self.ekw

    def ilosc_w_plecaku(self, ids):
        return self.luzem


a = AkcjeBudzet(ekw=600, majatek=13, majatek_glowny=13)
s, st = zbuduj(a)
e = zglasza(lambda: s.uruchom())
sprawdz("6s budżet: 13 gp w kontenerach + 6 platinum w slocie ekwipunku (depo ich nie rusza) = wystarcza na kolejkę", e is None
        and ("kup", "Alexander", "blank rune", 20) in a.log, (e, a.log))
a = AkcjeBudzet(ekw=0, majatek=13, majatek_glowny=13)
s, st = zbuduj(a)
e = zglasza(lambda: s.uruchom())
sprawdz("6t budżet: bez monet w ekwipunku te same 13 gp = błąd bez zakupów (jak dotąd)", e and "za mało pieniędzy" in e.powod
        and not any(isinstance(x, tuple) for x in a.log), (e, a.log))
a = AkcjeBudzet(ekw=0, luzem=20, majatek=100, majatek_glowny=100)
s, st = zbuduj(a)
e = zglasza(lambda: s.uruchom())
sprawdz("6u budżet: 20 blanków luzem w plecaku nie wlicza się do kosztu (100 gp wystarcza na ham 50 + backpack 20)", e is None, e)
a = AkcjeBudzet(ekw=0, luzem=0, majatek=100, majatek_glowny=100)
s, st = zbuduj(a)
e = zglasza(lambda: s.uruchom())
sprawdz("6v budżet: bez blanków luzem ten sam majątek 100 gp nie wystarcza (blanki 200 gp)", e and "za mało pieniędzy" in e.powod, e)

# R6: brak miejsca w bagu przed zakupem blanków
a = AkcjeAtrapa(wolne=5)
s, st = zbuduj(a)
e = zglasza(lambda: s.uruchom(["blanki"]))
sprawdz("6k blanki (R6): w bagu miejsce na 5, brakuje 20 = błąd PRZED zakupem (zero kupna)", e and "miejsce na 5" in e.powod
        and not any(isinstance(x, tuple) and x[0] == "kup" for x in a.log), (e, a.log))
a = AkcjeAtrapa(wolne=0)
s, st = zbuduj(a)
e = zglasza(lambda: s.uruchom(["blanki"]))
sprawdz("6l blanki (R6): brak baga na runy = błąd przed zakupem", e and not any(isinstance(x, tuple) and x[0] == "kup" for x in a.log), (e, a.log))

# częściowy brak drogi do stanowisk depo
class PlanerCzesc:
    def droga(self, od, do):
        return None if do[0] in (33175, 33173, 33171) else [tuple(od), tuple(do)]
a = AkcjeAtrapa()
s, st = zbuduj(a, start=(33176, 31796, 8))
s.planer = PlanerCzesc()
s.uruchom(["depo"])
sprawdz("6m depo: stanowiska bez drogi pomijane, bierze pierwsze osiągalne", ("depo", (33169, 31796, 8), 3) in a.log, a.log)
a = AkcjeAtrapa()
s, st = zbuduj(a)
s.planer = PlanerBrak()
e = zglasza(lambda: s.uruchom(["depo"]))
sprawdz("6n depo: brak drogi do jakiegokolwiek stanowiska = czytelny błąd", e and "brak drogi do żadnego" in e.powod, e)

a = AkcjeAtrapa()
s, st = zbuduj(a)
s.uruchom(["wyjscie"])
sprawdz("5u wyjście: kończy na polu z7 przy depo", st["poz"] == tuple(DANE["wyjscie"]) and st["poz"][2] == 7, st)
sprawdz("5v plan na sucho bez inputu: kroki z liczbą punktów", [k for k, _c, _n in s.plan(["bank", "depo", "wyjscie"])] == ["bank", "depo", "wyjscie"])

# --- wynik ---------------------------------------------------------------------------------------------------

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
