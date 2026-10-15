#!/usr/bin/env python3
"""15.10: zawrót patrolu z miejsca spawnu, które jest w widoku i puste (Cavebot._patrol_zawrot)."""
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


def bot(stwory, potwory=("troll",)):
    return SimpleNamespace(ostatnie_stwory=stwory, potwory=set(potwory))


def zawrot(b, p, poz, tgt, teraz):
    odl = max(abs(poz[0] - tgt[0]), abs(poz[1] - tgt[1]))
    return cavebot.Cavebot._patrol_zawrot(b, p, poz, tgt, odl, teraz)


poz, tgt = (100, 100, 8), (104, 101, 8)          # miejsce 4 pola dalej: w widoku z zapasem PROMIEN
pusto = bot([{"nazwa": "Mastafian", "x": 100, "y": 100, "z": 8, "gracz": True, "hp": 100}])
p = {}
sprawdz("1a pierwszy obieg pustki: jeszcze nie zawracamy", not zawrot(pusto, p, poz, tgt, 10.0))
sprawdz("1b po czasie < ZAWROT_S: nie", not zawrot(pusto, p, poz, tgt, 10.0 + cavebot.PATROL_ZAWROT_S - 0.1))
sprawdz("1c po czasie >= ZAWROT_S: zawracamy", zawrot(pusto, p, poz, tgt, 10.0 + cavebot.PATROL_ZAWROT_S))

troll = bot([{"nazwa": "Troll", "x": 105, "y": 102, "z": 8, "hp": 100}])
p = {}
zawrot(troll, p, poz, tgt, 10.0)
sprawdz("2 troll przy miejscu: nigdy nie zawracamy", not zawrot(troll, p, poz, tgt, 20.0))

inny = bot([{"nazwa": "Rat", "x": 104, "y": 101, "z": 8, "hp": 100}])
p = {}
zawrot(inny, p, poz, tgt, 10.0)
sprawdz("3 stwór spoza listy celów nie wstrzymuje zawrotu", zawrot(inny, p, poz, tgt, 12.0))

pietro = bot([{"nazwa": "Troll", "x": 104, "y": 101, "z": 9, "hp": 100}])
p = {}
zawrot(pietro, p, poz, tgt, 10.0)
sprawdz("4 troll na innym piętrze nie wstrzymuje zawrotu", zawrot(pietro, p, poz, tgt, 12.0))

p = {}
daleko = (100 + cavebot.WIDOK_X, 101, 8)          # miejsce na krawędzi widoku: okolica (PROMIEN) poza ekranem
zawrot(pusto, p, poz, daleko, 10.0)
sprawdz("5 miejsce za daleko (okolica poza widokiem): nie zawracamy", not zawrot(pusto, p, poz, daleko, 20.0))

p = {}
zawrot(pusto, p, poz, (104, 101, 9), 10.0)
sprawdz("6 miejsce na innym piętrze: nie zawracamy", not zawrot(pusto, p, poz, (104, 101, 9), 20.0))

p = {"sweep": {"nast": 0}}
zawrot(pusto, p, poz, tgt, 10.0)
sprawdz("7 sweep: bez zawrotu", not zawrot(pusto, p, poz, tgt, 20.0))

stary = cavebot.PATROL_ZAWROT
cavebot.PATROL_ZAWROT = 0
p = {}
zawrot(pusto, p, poz, tgt, 10.0)
sprawdz("8 pokrętło 0: bez zawrotu", not zawrot(pusto, p, poz, tgt, 20.0))
cavebot.PATROL_ZAWROT = stary

p = {}
zawrot(pusto, p, poz, tgt, 10.0)
zawrot(troll, p, poz, tgt, 11.0)                  # cel pojawił się: licznik pustki od nowa
sprawdz("9 cel w międzyczasie zeruje licznik", not zawrot(pusto, p, poz, tgt, 12.0)
        and zawrot(pusto, p, poz, tgt, 12.0 + cavebot.PATROL_ZAWROT_S))

print(f"WYNIK: {sum(wyniki)} / {len(wyniki)}")
sys.exit(0 if all(wyniki) else 1)
