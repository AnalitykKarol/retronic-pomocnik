"""24.10: loot.wyrzuc_jedzenie (jedna sztuka jedzenia z plecaka na ziemię pod postacią) na atrapach myszy i pamięci.
Logika decyzji (jedz -> wyrzucaj po 1 sztuce -> cap -> wyprawa) jest w testy/test_wyprawa.py sekcja 22.
Bez gry: RETRONIC_TESTY=1, atrapa myszy i zrzutu, brak XTEST/DISPLAY."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
import types
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))))
import ekran
import loot

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


class Mysz:
    ekran = None

    def __init__(self, sw):
        self.sw, self.ruchy = sw, []

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def przeciagnij(self, *a, **k): self.ruchy.append(("drag", a[:4])); self.sw.po_drag()
    def lewy(self, x, y, **k): self.ruchy.append(("lewy", x, y)); self.sw.po_klik((x, y))
    def _cel_poza_ekwipunkiem(self, x, y, co): return self.sw.cel_ok


class Sw:
    """Świat: stos jedzenia w slocie, okno ilości po przeciągnięciu stosu > 1."""

    def __init__(self, stos=5, cel_ok=True, okno=True, dziala=True):
        self.stos, self.cel_ok, self.okno_jest, self.dziala = stos, cel_ok, okno, dziala
        self.okno, self.ilosc = False, stos
        self.ok_klik = 0
        self.mysz = Mysz(self)

    def po_drag(self):
        if self.stos > 1:
            self.okno, self.ilosc = self.okno_jest, self.stos
        elif self.dziala:
            self.stos = 0

    def po_klik(self, xy):
        if not self.okno:
            return
        if xy[0] < 400 + 60 + loot.OK_DX - 20 and xy[0] < 400 + 60:       # strzałka w lewo
            self.ilosc = max(1, self.ilosc - 1)
        else:                                                                 # Ok
            self.okno = False
            self.ok_klik += 1
            if self.dziala:
                self.stos -= self.ilosc


def zaladuj(sw):
    loot.ekran = types.SimpleNamespace(Mysz=lambda: sw.mysz, pole_na_ekran=lambda dx, dy, p=None: (300, 300),
                                       aktualny_prostokat=lambda e=None: (0, 0, 480, 352))
    loot._zrzut = lambda mysz: None
    loot._jedzenie_z_pamieci = lambda obraz: (types.SimpleNamespace(srodek=(900, 500)), "ham", 3582, 7) if sw.stos > 0 else None
    loot._ile_w_kontenerze = lambda numer, ident: sw.stos
    loot._ilosc_stosu = lambda numer, ident: sw.stos if sw.stos > 0 else None
    loot.znajdz_okno_ilosci = lambda obraz: (400, 300) if sw.okno else None
    loot._pauza = lambda a=0, b=0: None
    loot._straznik = lambda log: types.SimpleNamespace(przed=lambda: None, po=lambda co: [])
    loot.bot = types.SimpleNamespace(sprawdz_stop=lambda: None)


_czas = [0.0]
loot.time = types.SimpleNamespace(monotonic=lambda: (_czas.__setitem__(0, _czas[0] + 0.5), _czas[0])[1], sleep=lambda s: None)

sw = Sw(stos=5)
zaladuj(sw)
w = loot.wyrzuc_jedzenie(log=lambda *_: None)
strzalki = [r for r in sw.mysz.ruchy if r[0] == "lewy"][:-1]
sprawdz("1a stos 5: przeciągnięcie na własne pole, 4 kliknięcia strzałki w lewo (ilość 1), Ok; zostaje 4",
        w == (1, 4, None) and sw.stos == 4 and len(strzalki) == 4 and sw.ok_klik == 1 and sw.mysz.ruchy[0] == ("drag", (900, 500, 300, 300)), (w, sw.mysz.ruchy))
sw = Sw(stos=1)
zaladuj(sw)
w = loot.wyrzuc_jedzenie(log=lambda *_: None)
sprawdz("1b stos 1: bez okna ilości (zero kliknięć), zostaje 0", w == (1, 0, None) and [r for r in sw.mysz.ruchy if r[0] == "lewy"] == [], (w, sw.mysz.ruchy))
sw = Sw(stos=0)
zaladuj(sw)
w = loot.wyrzuc_jedzenie(log=lambda *_: None)
sprawdz("1c brak jedzenia: (0, 0, powód), bez ruchu myszy", w[0] == 0 and w[1] == 0 and w[2] and not sw.mysz.ruchy, w)
sw = Sw(stos=3, cel_ok=False)
zaladuj(sw)
w = loot.wyrzuc_jedzenie(log=lambda *_: None)
sprawdz("1d cel upuszczenia na slocie ekwipunku: odmowa, nic nie przeciągnięte", w[0] == 0 and "ekwipunku" in w[2] and not sw.mysz.ruchy and sw.stos == 3, (w, sw.mysz.ruchy))
sw = Sw(stos=3, okno=False)
zaladuj(sw)
w = loot.wyrzuc_jedzenie(log=lambda *_: None)
sprawdz("1e okno ilości nie pojawiło się po przeciągnięciu stosu: porażka z powodem, stos bez zmian", w[0] == 0 and "okna ilości" in w[2] and sw.stos == 3, w)
sw = Sw(stos=4, dziala=False)
zaladuj(sw)
w = loot.wyrzuc_jedzenie(log=lambda *_: None)
sprawdz("1f po ruchu liczba sztuk się nie zmieniła (np. brak miejsca na ziemi): porażka, nie 'wyrzucono'", w[0] == 0 and "nie ubyło" in w[2], w)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
