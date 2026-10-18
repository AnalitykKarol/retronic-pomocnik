#!/usr/bin/env python3
"""18.10: otwieranie i rozciąganie plecaka (loot.otworz_plecak, loot.rozciagnij_plecak).
Offline: atrapa myszy zapisuje akcje, zrzut i wykrycie okien podmienione. Zero inputu do gry."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import loot  # noqa: E402


class Slot:
    def __init__(self, x, y, bok=34):
        self.x, self.y, self.bok = x, y, bok


class Okno:
    def __init__(self, rzedy, gora=484):
        self.lewo, self.prawo, self.gora = 995, 1171, gora
        self.sloty = [Slot(1005 + 37 * k, gora + 18 + 37 * w) for w in range(rzedy) for k in range(4)]


class Atrapa:
    ekran = "test"

    def __init__(self):
        self.akcje = []

    def przeciagnij(self, *a, **k):
        self.akcje.append(("przeciagnij", a, k))

    def lewy(self, *a, **k):
        self.akcje.append(("lewy", a, k))


def test_dolna_krawedz_za_dolnym_rzedem():
    okno = Okno(5)
    assert loot.dolna_krawedz(okno) == max(s.y + s.bok for s in okno.sloty) + 10


def test_rozciagnij_do_piec_rzedow():
    loot._nazwa_tytulu = lambda obraz, o: "backpack"
    loot.znajdz_okna = lambda obraz: [Okno(3)]
    m = Atrapa()
    assert loot.rozciagnij_plecak(m, None, log=lambda *a: None) is True
    (nazwa, (x, y1, x2, y2), k), = m.akcje
    assert nazwa == "przeciagnij" and k == {"drganie": 0}
    assert x == x2 and y2 - y1 == 2 * 37


def test_rozciagnij_pomija_juz_rozciagniete():
    loot._nazwa_tytulu = lambda obraz, o: "backpack"
    loot.znajdz_okna = lambda obraz: [Okno(5)]
    m = Atrapa()
    assert loot.rozciagnij_plecak(m, None, log=lambda *a: None) is False
    assert m.akcje == []


def test_otworz_bez_plecaka_klika_ctrl_i_weryfikuje():
    stan = {"otwarty": False}
    loot._zrzut = lambda mysz: None
    loot.plecak_otwarty = lambda obraz: stan["otwarty"]
    loot._pauza = lambda *a: None
    loot._okno_plecaka = lambda obraz: None
    loot.rozciagnij_plecak = lambda *a, **k: False
    loot._ostatnia_proba_otwarcia[0] = None

    class MyszKlik(Atrapa):
        def lewy(self, x, y, modyfikator=None, drganie=3):
            super().lewy(x, y, modyfikator=modyfikator, drganie=drganie)
            stan["otwarty"] = True

    m = MyszKlik()
    assert loot.otworz_plecak(m, log=lambda *a: None) is True
    assert m.akcje[0][1][:2] == loot.SLOT_PLECAKA_EKWIPUNEK
    assert m.akcje[0][2]["modyfikator"] == "Control_L"


def test_otworz_z_cooldownem():
    loot._zrzut = lambda mysz: None
    loot.plecak_otwarty = lambda obraz: False
    loot._pauza = lambda *a: None
    loot._ostatnia_proba_otwarcia[0] = loot.time.monotonic()
    m = Atrapa()
    assert loot.otworz_plecak(m, log=lambda *a: None) is False
    assert m.akcje == []


if __name__ == "__main__":
    for nazwa, f in list(globals().items()):
        if nazwa.startswith("test_"):
            f()
            print("ok", nazwa)
