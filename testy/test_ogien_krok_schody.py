#!/usr/bin/env python3
"""15.10: krok omijający ogień, gdy celem są schody (zakaz w A*): droga do pola obok celu, także skosem.
Zdarzenie: 15:03:01-15:05:43 postać stała 162 s w kieszeni (32491,32288) przy ogniu (32491,32289)."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("RETRONIC_TESTY", "1")
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cavebot  # noqa: E402

wyniki = []


def sprawdz(nazwa, warunek, info=""):
    wyniki.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + (f"  {info}" if not warunek and info else ""))


def bot(drogi):
    kroki = []
    b = SimpleNamespace(zegar=lambda: 100.0, klik_cel="x", ogien_czeka_od=None, ogien_ignoruj_do=0.0, kroki=kroki,
                        droga=lambda start, cel, dlugosc=1, **k: drogi.get(dlugosc),
                        krok_do=lambda c: (kroki.append(tuple(c)), True)[1])
    return b


POZ, SCHODY, OGIEN = (32491, 32288, 8), (32494, 32289), (32491, 32289)

b = bot({0: None, 1: [(32492, 32289, 8), (32493, 32289, 8)]})
cavebot.Cavebot._ogien_krok(b, POZ, SCHODY, krok=OGIEN + (8,))
sprawdz("1 cel = schody: krok skosem na pole obok (32492,32289), nie w ogień", b.kroki == [(32492, 32289)], b.kroki)
sprawdz("1b bez czekania na ogień", b.ogien_czeka_od is None)

b = bot({0: [(32492, 32289, 8)], 1: [(32490, 32290, 8)]})
cavebot.Cavebot._ogien_krok(b, POZ, (32492, 32289))
sprawdz("2 zwykły cel: droga dokładnie do celu (bez zmian)", b.kroki == [(32492, 32289)], b.kroki)

b = bot({0: None, 1: None})
cavebot.Cavebot._ogien_krok(b, POZ, SCHODY, krok=(32493, 32289, 8))
sprawdz("3 brak obu dróg: jak dotąd krok w stronę `krok`", b.kroki == [(32493, 32289)], b.kroki)

# 4. brak drogi (także skosem) przez OGIEN_CZEKAJ_MAX_S: nie ignorujemy ognia, krok nieudany (inny cel trasy)
b = bot({0: None, 1: None})
b.krok_do = lambda c: False
for t in (100.0, 100.0 + cavebot.OGIEN_CZEKAJ_MAX_S):
    b.zegar = lambda t=t: t
    wynik = cavebot.Cavebot._ogien_krok(b, POZ, SCHODY)
sprawdz("4a po czekaniu: ogień NIE jest ignorowany", b.ogien_ignoruj_do == 0.0, b.ogien_ignoruj_do)
sprawdz("4b krok zgłasza porażkę (utknięcie -> inny cel)", wynik is False)

print(f"WYNIK: {sum(wyniki)} / {len(wyniki)}")
sys.exit(0 if all(wyniki) else 1)
