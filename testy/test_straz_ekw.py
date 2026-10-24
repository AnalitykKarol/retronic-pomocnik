import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""23.10 (lina invincible, gold na slocie 10 wydry): przeciągnięcie lootu NIE może skończyć na slocie ekwipunku
ani poza oknem kontenera, a po przeciągnięciu sprawdzamy, że ekwipunek się nie zmienił ([EKW]).
Syntetyczne zrzuty + atrapy myszy i pamięci, bez gry. Uruchom: python3 -I testy/test_straz_ekw.py"""
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from PIL import Image, ImageDraw
import ekran, loot
PRAWDZIWA_MYSZ = ekran.Mysz
try:
    import straz_ekw
except ImportError:          # przed poprawką: moduł nie istnieje, a asercje poniżej mają być czerwone, nie test w całości
    straz_ekw = None

ok = True
def sprawdz(opis, warunek, info=""):
    global ok
    print(("OK    " if warunek else "BŁĄD "), opis, "" if warunek else info)
    ok &= bool(warunek)


def okno_syn(im, x, y, wiersze, zajete=()):
    d = ImageDraw.Draw(im)
    for r in range(wiersze):
        for c in range(4):
            x0, y0 = x + c * 37, y + r * 37
            d.rectangle((x0, y0, x0 + 33, y0 + 33), outline=loot.RAMKA)
            if r * 4 + c in zajete:
                d.rectangle((x0 + 8, y0 + 8, x0 + 24, y0 + 24), fill=(200, 60, 160))


def panel_ekw(im, xs, y0):
    """Panel Inventory (10 slotów) o głowie w (xs, y0); slot 10 ma lewy-górny róg (xs+36, y0+85)."""
    d = ImageDraw.Draw(im)
    for dx, dy in [(0, 0), (-37, 13), (36, 13), (0, 36), (-37, 49), (36, 49), (0, 72), (-37, 85), (36, 85), (0, 108)]:
        d.rectangle((xs + dx, y0 + dy, xs + dx + 33, y0 + dy + 33), outline=loot.RAMKA)


def kont(numer, nazwa, ident, poj, *przedm):
    return {"numer": numer, "nazwa": nazwa, "id": ident, "pojemnosc": poj,
            "przedmioty": [{"slot": i, "id": a, "ilosc": b} for i, (a, b) in enumerate(przedm)]}


zdarzenia, logi, powiadomienia = [], [], []
stan = {"obraz": None, "pamiec": [], "ekw": {}, "ekw_po": None}


class FMysz:
    ekran = ":99"
    def __enter__(s): return s
    def __exit__(s, *a): pass
    def przeciagnij(s, *a, **k):
        zdarzenia.append(("drag", a))
        if stan["ekw_po"] is not None:
            stan["ekw"] = stan["ekw_po"]          # gra zmieniła ekwipunek w wyniku przeciągnięcia
    def lewy(s, *a, **k): zdarzenia.append(("lewy", a))
    def klik(s, *a, **k):
        zdarzenia.append(("klik", a))
        if stan["ekw_po"] is not None:
            stan["ekw"] = stan["ekw_po"]


def atrapa_pamieci(z):
    odp = {"kontenery": stan["pamiec"]}
    if z.get("ekwipunek"):
        odp["ekwipunek"] = stan["ekw"]
    return odp


ekran.Mysz = FMysz
ekran._rozmiar_ekranu = lambda e=None: (734, 910)
ekran.zrzut = lambda: stan["obraz"]
loot._pauza = lambda a=0, b=0: None
loot._zapytaj = atrapa_pamieci
loot._czekaj_na_postoj = lambda g: ((100, 100, 7), True)
loot._okno_ilosci_ok = lambda *a, **k: False
loot._sprzatnij_okno_ilosci = lambda *a, **k: None
loot._zamknij_zwloki = lambda *a, **k: True
loot._scal_stosy = lambda mysz, p, lista, log: p
loot.zapisz_nieznany = lambda *a, **k: None
if straz_ekw is not None:
    straz_ekw.POWIADOM = lambda tytul, tresc="", pilnosc="normal", klucz=None: powiadomienia.append((tytul, pilnosc, klucz))
log = lambda s: (logi.append(s), print("   log:", s))

zwloki_przed = kont(2, "dead troll", 3994, 8, (3031, 7), (3457, 1))
zwloki_po = kont(2, "dead troll", 3994, 8, (3457, 1))
bag = kont(1, "backpack", 2854, 8, (3031, 24))

# plan (stary zrzut): panel Inventory u góry, plecak (580,360), zwłoki (580,560)
A = Image.new("RGB", (734, 910), (20, 20, 20))
panel_ekw(A, 596, 114)
okno_syn(A, 580, 360, 2, zajete=(0,))
okno_syn(A, 580, 560, 2, zajete=(0, 1))
stan["pamiec"] = [bag, zwloki_przed]
P_PRZED = loot.plan(A)
stan["pamiec"] = [kont(1, "backpack", 2854, 8, (3031, 31)), zwloki_po]
P_PO = loot.plan(A)
stan["pamiec"] = [bag, zwloki_przed]
sprawdz("0 plan: gold ze zwłok idzie na slot 0 plecaka", P_PRZED["zrodlo"] == "pamiec" and P_PRZED["cel"] is not None
        and P_PRZED["cel"].srodek == (597, 377), (P_PRZED["pamiec"], P_PRZED["cel"]))

loot._odczyt_kontenerow = lambda: [bag]
loot._otworz_z_pamiecia = lambda *a, **k: ((1, 0), zwloki_przed)
loot._plan_z_oknem = lambda *a, **k: (P_PRZED, True)
loot._plan_teraz = lambda mysz, lista, log: (None, P_PO)


def zbierz(obraz_przy_przeciaganiu, ekw=None, ekw_po=None):
    zdarzenia.clear(); logi.clear(); powiadomienia.clear()
    if straz_ekw is not None:
        straz_ekw._ostatnie_powiadomienie.clear()
    stan.update(obraz=obraz_przy_przeciaganiu, ekw=ekw if ekw is not None else {}, ekw_po=ekw_po)
    loot._zrzut = lambda mysz: obraz_przy_przeciaganiu
    return loot.zbierz_szczegoly((101, 100, 7), (100, 100, 7), ("gold coin",), log=log)


# 1. okno plecaka z planu zniknęło ze zrzutu, a pod celem jest slot 10 ekwipunku: nie wolno upuścić
B = Image.new("RGB", (734, 910), (20, 20, 20))
panel_ekw(B, 544, 275)                       # slot 10 dokładnie pod celem (597, 377)
sprawdz("1-pre panel: slot 10 pod celem planu", loot.__dict__.get("_ekw_test") is None
        and __import__("pochodnia").pozycje_ekwipunku(B).get(10) == (597, 377), __import__("pochodnia").pozycje_ekwipunku(B))
w = zbierz(B)
drag = [z for z in zdarzenia if z[0] == "drag"]
sprawdz("1a przeciągnięcie na slot ekwipunku NIE wychodzi", not drag, drag)
sprawdz("1b log [EKW] z powodem odmowy", any("[EKW]" in l and "slocie ekwipunku 10" in l for l in logi), logi)
sprawdz("1c status nie jest 'ok' z fałszywym łupem", not w["zebrano"], w)
sprawdz("1d zwykłe powiadomienie o odmowie", bool(powiadomienia) and all(p[1] == "normal" for p in powiadomienia), powiadomienia)

# 2. cel poza oknem kontenera (zrzut bez żadnego okna plecaka i bez panelu): też odmowa
C = Image.new("RGB", (734, 910), (20, 20, 20))
w = zbierz(C)
drag = [z for z in zdarzenia if z[0] == "drag"]
sprawdz("2a cel poza oknem kontenera: bez przeciągnięcia", not drag, drag)
sprawdz("2b log [EKW] z powodem 'okno'", any("[EKW]" in l and "okn" in l for l in logi), logi)

# 3. normalny układ (zrzut = plan): przeciągnięcie wychodzi, ekwipunek bez zmian = zero [EKW]
w = zbierz(A, ekw={10: {"id": 3003, "ilosc": 1}, 5: {"id": 3409, "ilosc": 1}})
drag = [z for z in zdarzenia if z[0] == "drag"]
sprawdz("3a zwykły układ: jedno przeciągnięcie na slot 0 plecaka (597, 377)",
        len(drag) == 1 and abs(drag[0][1][2] - 597) <= 1 and abs(drag[0][1][3] - 377) <= 1, drag)
sprawdz("3b łup zebrany", w["zebrano"] == ["gold coin"], w)
sprawdz("3c ekwipunek bez zmian: bez [EKW] i bez powiadomienia", not any("[EKW]" in l for l in logi) and not powiadomienia, (logi, powiadomienia))

# 4. przeciągnięcie wyszło poprawnie według ekranu, ale gra zmieniła slot 10 (lina znikła / wpadł gold): [EKW] + powiadomienie
w = zbierz(A, ekw={10: {"id": 3003, "ilosc": 1}}, ekw_po={})
sprawdz("4a lina zniknęła ze slotu 10: log [EKW] ze slotem i ID", any("[EKW]" in l and "10" in l and "3003" in l for l in logi), logi)
sprawdz("4b zwykłe powiadomienie", len(powiadomienia) == 1 and powiadomienia[0][1] == "normal", powiadomienia)
w = zbierz(A, ekw={}, ekw_po={10: {"id": 3031, "ilosc": 12}})
sprawdz("4c gold wpadł na pusty slot 10: log [EKW]", any("[EKW]" in l and "10" in l and "3031" in l for l in logi), logi)

# 5. brak odczytu ekwipunku (None): loot działa jak dotąd, bez [EKW]
atrapa = atrapa_pamieci
loot._zapytaj = lambda z: {"kontenery": stan["pamiec"], "ekwipunek": None} if z.get("ekwipunek") else {"kontenery": stan["pamiec"]}
w = zbierz(A)
sprawdz("5 bez odczytu ekwipunku: przeciągnięcie wychodzi, zero [EKW]",
        len([z for z in zdarzenia if z[0] == "drag"]) == 1 and not any("[EKW]" in l for l in logi), (zdarzenia, logi))
loot._zapytaj = atrapa

# 6. wypad.uzyj_line: lina leży w slocie 10 (poza oknami) - Use działa ze slotu 10, a zniknięcie liny po Use = [EKW]
import wypad, pochodnia
ekran.pole_na_ekran = lambda dx, dy, pr=None: (597 + 10 * dx, 377 + 10 * dy)
ekran.aktualny_prostokat = lambda e=None: None
loot._zrzut = lambda mysz: B
stan["pamiec"] = []
for ekw_po, oczek in (({"10": None}, False), (None, True)):
    zdarzenia.clear(); logi.clear(); powiadomienia.clear(); straz_ekw._ostatnie_powiadomienie.clear()
    stan.update(ekw={10: {"id": 3003, "ilosc": 1}}, ekw_po=({} if ekw_po else None))
    ops = wypad.OperacjeZywe(zapytaj=atrapa_pamieci, log=logi.append)
    ops.uzyj_line((100, 100, 9), (100, 101, 9))
    kliki = [z for z in zdarzenia if z[0] == "klik"]
    sprawdz("6a Use liny ze slotu 10: Ctrl+klik na panelu, potem klik na polu", len(kliki) == 2 and kliki[0][1][:2] == (597, 377), kliki)
    ekw_log = [l for l in logi if "[EKW]" in l]
    if ekw_po:
        sprawdz("6b lina znikła po Use: [EKW] ze slotem 10 i ID 3003 + powiadomienie", ekw_log and "3003" in ekw_log[0] and "slot 10" in ekw_log[0] and powiadomienia, (logi, powiadomienia))
    else:
        sprawdz("6c lina na miejscu: zero [EKW], log mówi, że Use idzie ze slotu 10", not ekw_log and any("ze slotu 10" in l and "Ctrl+klik (597, 377)" in l and "klik na polu (597, 367)" in l for l in logi), logi)

# 7. ekran.Mysz.przeciagnij_pola: upuszczenie na slot ekwipunku (zły prostokąt mapy) jest odmówione, normalne przechodzi
class Prawdziwa(PRAWDZIWA_MYSZ):
    def __init__(s): s.ekran = ":99"; s.log = []
    def przeciagnij(s, *a, **k): zdarzenia.append(("drag", a))
for obraz, oczek in ((B, 0), (C, 1)):
    zdarzenia.clear(); logi.clear(); powiadomienia.clear(); straz_ekw._ostatnie_powiadomienie.clear()
    ekran.zrzut = lambda o=obraz: o
    import io, contextlib
    wyj = io.StringIO()
    with contextlib.redirect_stdout(wyj):
        Prawdziwa().przeciagnij_pola(1, 0, 0, 0)
    ile = len([z for z in zdarzenia if z[0] == "drag"])
    if oczek:
        sprawdz("7a cel poza panelem: przeciągnięcie wychodzi", ile == 1, zdarzenia)
    else:
        sprawdz("7b cel na slocie 10: bez przeciągnięcia, [EKW] w wyjściu, powiadomienie",
                ile == 0 and "[EKW]" in wyj.getvalue() and "slocie ekwipunku 10" in wyj.getvalue() and bool(powiadomienia), (zdarzenia, wyj.getvalue()))

print("WYNIK:", "OK" if ok else "BŁĄD")
sys.exit(0 if ok else 1)
