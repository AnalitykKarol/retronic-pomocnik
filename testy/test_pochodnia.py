import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, tempfile, pathlib
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import pochodnia
from pochodnia import Pochodnia, BrakEkranu, SLOT_POCHODNI as S

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

NOWA, LIT, BURNT = 2920, 7001, 7002
tmp = pathlib.Path(tempfile.mkdtemp())

class Swiat:
    """Atrapa gry: slot pochodni + liczba zapasowych w plecaku; zachowanie konfigurowalne."""
    def __init__(s, slot=None, zapas=1, zapas_widoczny=True, ekwip=True):
        s.slot, s.zapas, s.widoczny, s.ekwip = slot, zapas, zapas_widoczny, ekwip
        s.zdarzenia = []
        s.nie_wyrzuca = s.nie_zapala = s.nie_wklada = False
        s.brak_ekranu = False
    def ekwipunek(s):
        if not s.ekwip:
            return None
        e = {1: 3355, 3: 2853}
        if s.slot is not None:
            e[S] = s.slot
        return e
    def zapas_(s): return s.zapas if s.widoczny else None
    def przeciagnij_do_podlogi(s):
        s.zdarzenia.append("wyrzut")
        if s.brak_ekranu: raise BrakEkranu("nie widzę panelu Inventory")
        if not s.nie_wyrzuca: s.slot = None
    def przeniesc_zapas_do_slotu(s):
        s.zdarzenia.append("wloz")
        if s.brak_ekranu: raise BrakEkranu("nie widzę okna plecaka")
        if not s.nie_wklada and s.zapas:
            s.zapas -= 1; s.slot = NOWA
    def uzyj_slot(s):
        s.zdarzenia.append("use")
        if s.slot == NOWA and not s.nie_zapala: s.slot = LIT

class Ops:
    def __init__(s, sw): s.sw = sw
    def ekwipunek(s): return s.sw.ekwipunek()
    def zapas(s): return s.sw.zapas_()
    def przeciagnij_do_podlogi(s): s.sw.przeciagnij_do_podlogi()
    def przeniesc_zapas_do_slotu(s): s.sw.przeniesc_zapas_do_slotu()
    def uzyj_slot(s): s.sw.uzyj_slot()

class Zegar:
    t = 1000.0
    def __call__(s): return s.t

def nowy(sw, plik=None, **k):
    z, logi = Zegar(), []
    p = Pochodnia(Ops(sw), zegar=z, spij=lambda t: None, log=logi.append,
                  plik=plik or (tmp / f"ids{len(ok)}.json"), **k)
    return p, z, logi

# 1 niezapalona w slocie: tylko Use, uczymy się ID zapalonej
sw = Swiat(slot=NOWA)
p, z, l = nowy(sw)
sprawdz("1a niezapalona: akcja", p.tick() is True)
sprawdz("1b tylko Use", sw.zdarzenia == ["use"], sw.zdarzenia)
sprawdz("1c nauczone ID zapalonej + zapisane", p.zapalona == {LIT} and LIT in __import__("json").loads(p.plik.read_text())["zapalona"])

# 2 zapalona: nic nie robi, interwał 30 s
sw = Swiat(slot=LIT)
p, z, l = nowy(sw)
p.zapalona = {LIT}
sprawdz("2a zapalona: brak akcji", p.tick() is False and sw.zdarzenia == [])
sw.slot = BURNT
sprawdz("2b interwał: przed 30 s nie czyta", p.tick() is False and p.ostatni == LIT)
z.t += 31
sprawdz("2c po 30 s: zmiana ZAPALONA->inne = nauka wypalonej i wymiana", p.tick() is True and BURNT in p.wypalona or p.wypalona == {BURNT})
sprawdz("2d kolejność wyrzut, włóż, use", sw.zdarzenia == ["wyrzut", "wloz", "use"], sw.zdarzenia)
sprawdz("2e na końcu zapalona w slocie", sw.slot == LIT and sw.zapas == 0)

# 3 pusty slot z zapasem
sw = Swiat(slot=None, zapas=2)
p, z, l = nowy(sw)
p.zapalona = {LIT}
p.tick()
sprawdz("3 pusty: włóż + use (bez wyrzutu)", sw.zdarzenia == ["wloz", "use"] and sw.slot == LIT, sw.zdarzenia)

# 4 brak zapasu: log raz, brak akcji
sw = Swiat(slot=None, zapas=0)
p, z, l = nowy(sw)
for _ in range(3):
    p.tick(); z.t += 31
sprawdz("4a brak pochodni: bez akcji", sw.zdarzenia == [])
sprawdz("4b log 'brak pochodni' dokładnie raz", sum("brak pochodni" in x for x in l) == 1, l)
sw.zapas = 1; z.t += 31
p.tick()
sprawdz("4c po uzupełnieniu zapasu wymiana działa", sw.slot == LIT, sw.slot)

# 5 nieznane ID w slocie (np. strzały): nie ruszamy, log raz
sw = Swiat(slot=9999)
p, z, l = nowy(sw)
for _ in range(3):
    p.tick(); z.t += 31
sprawdz("5 nieznane ID: brak akcji, log raz", sw.zdarzenia == [] and sum("nieznane ID" in x for x in l) == 1, l)

# 6 dwie nieudane próby -> blokada 10 min
sw = Swiat(slot=None, zapas=5)
sw.nie_zapala = True
p, z, l = nowy(sw)
p.tick(); n1 = len(sw.zdarzenia)
z.t += 31; p.tick()
sprawdz("6a dwie próby", sw.zdarzenia.count("use") == 2, sw.zdarzenia)
z.t += 31
sprawdz("6b blokada 10 min: brak trzeciej", p.tick() is False and sw.zdarzenia.count("use") == 2)
z.t += 600
sw.nie_zapala = False
sprawdz("6c po blokadzie próbuje znów", p.tick() is True and sw.slot == LIT, sw.slot)
sprawdz("6d log o przerwie", any("przerwa" in x for x in l), l)

# 7 wyrzut się nie udał: nie wkładamy nowej na starą
sw = Swiat(slot=BURNT, zapas=1); sw.nie_wyrzuca = True
p, z, l = nowy(sw); p.wypalona = {BURNT}
p.tick()
sprawdz("7 nieudany wyrzut: bez włożenia", sw.zdarzenia == ["wyrzut"], sw.zdarzenia)

# 8 brak ekranu: nie liczy się jako próba
sw = Swiat(slot=BURNT, zapas=1); sw.brak_ekranu = True
p, z, l = nowy(sw); p.wypalona = {BURNT}
for _ in range(4):
    p.tick(); z.t += 31
sprawdz("8 brak ekranu: nie blokuje na 10 min", p.blokada_do == float("-inf") and p.proby == 0)

# 9 brak odczytu pamięci: bez akcji, log raz
sw = Swiat(slot=BURNT, ekwip=False)
p, z, l = nowy(sw); p.wypalona = {BURNT}
for _ in range(3):
    p.tick(); z.t += 31
sprawdz("9 brak odczytu: bez akcji, log raz", sw.zdarzenia == [] and sum("nie widzę ekwipunku" in x for x in l) == 1, l)

# 10 niebezpiecznie (walka): nic, a po wejściu w bezpieczne stan jest sprawdzany
sw = Swiat(slot=None, zapas=1)
p, z, l = nowy(sw)
sprawdz("10a walka: bez akcji", p.tick(bezpiecznie=False) is False and sw.zdarzenia == [])
sprawdz("10b po walce od razu", p.tick() is True and sw.slot == LIT)

# 11 ID zapisane w pliku wczytywane przy starcie
f = tmp / "z_pliku.json"; f.write_text('{"zapalona":[5],"wypalona":[6]}')
sw = Swiat(slot=6, zapas=1)
p, z, l = nowy(sw, plik=f)
sprawdz("11a wczytanie ID z pliku", p.zapalona == {5} and p.wypalona == {6})
p.tick()
sprawdz("11b wypalona z pliku wymieniona", sw.zdarzenia == ["wyrzut", "wloz", "use"], sw.zdarzenia)

# 12 wypalona znika sama (slot pusty po zapalonej) -> wymiana bez wyrzutu
sw = Swiat(slot=LIT, zapas=1)
p, z, l = nowy(sw); p.zapalona = {LIT}
p.tick(); sw.slot = None; z.t += 31
p.tick()
sprawdz("12 zniknięcie zapalonej: włóż + use", sw.zdarzenia == ["wloz", "use"], sw.zdarzenia)

# 13 wyjątek zatrzymania przepuszczany
class Stop(Exception): pass
sw = Swiat(slot=None, zapas=1)
sw.uzyj_slot = lambda: (_ for _ in ()).throw(Stop())
p, z, l = nowy(sw, nie_lap=(Stop,))
try:
    p.tick(); przepuszczony = False
except Stop:
    przepuszczony = True
sprawdz("13 Zatrzymano przepuszczone", przepuszczony)

# 14 układ slotów panelu Inventory z syntetycznego zrzutu
from PIL import Image, ImageDraw
im = Image.new("RGB", (734, 910), (20, 20, 20)); d = ImageDraw.Draw(im)
def ramka(x, y):
    d.rectangle((x, y, x + 33, y + 33), outline=(50, 52, 48))
for x, y in [(596, 114), (559, 127), (632, 127), (596, 150), (559, 163), (632, 163), (596, 186), (559, 199), (632, 199), (596, 222)]:
    ramka(x, y)
poz = pochodnia.pozycje_ekwipunku(im)
sprawdz("14a slot 10 = prawy dolny", poz.get(10) == (649, 216), poz)
sprawdz("14b głowa i plecak", poz.get(1) == (613, 131) and poz.get(3) == (649, 144), poz)
# okno kontenera (bez bocznych sąsiadów +13) nie jest ekwipunkiem
im2 = Image.new("RGB", (734, 910), (20, 20, 20)); d = ImageDraw.Draw(im2)
for i in range(4):
    for j in range(2):
        d.rectangle((560 + 37 * i, 720 + 36 * j, 593 + 37 * i, 753 + 36 * j), outline=(50, 52, 48))
sprawdz("14c kontener nie jest ekwipunkiem", pochodnia.pozycje_ekwipunku(im2) == {})

# 15 odczyt ekwipunku z atrapą gniazda: klucze tekstowe -> int, błąd gniazda
o = pochodnia.OperacjeZywe(zapytaj=lambda z: {"ekwipunek": {"10": {"id": 2920, "ilosc": 1}, "1": {"id": 3355, "ilosc": 1}}})
sprawdz("15a ekwipunek -> {slot:int: id}", o.ekwipunek() == {10: 2920, 1: 3355})
o = pochodnia.OperacjeZywe(zapytaj=lambda z: {"kontenery": [
    {"numer": 1, "nazwa": "bag", "id": 2853, "pojemnosc": 8, "przedmioty": [{"slot": 1, "id": 2920, "ilosc": 1}, {"slot": 2, "id": 2920, "ilosc": 1}]}]})
sprawdz("15b zapas = liczba pochodni w plecaku", o.zapas() == 2)
o = pochodnia.OperacjeZywe(zapytaj=lambda z: {"kontenery": []})
sprawdz("15c brak plecaka -> None", o.zapas() is None)

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
