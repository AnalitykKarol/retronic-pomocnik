#!/usr/bin/env python3
"""22.10: pusty consoleBuffer (świeża zakładka Default, 0 wiadomości) musi być uznany za poprawny bufor.

Pomiar na żywo (dawajkesh, gebelish): deque dzieci pustego bufora = cztery zera (mapa=0, rozmiar mapy=0,
przesunięcie=0, liczba=0). Wcześniej `_deque()` dawał None, bufor był odrzucany, `stan_zakladek()` zwracał
`aktywny_bufor: None`, a serwis (bank) padał na "nie potwierdzono aktywnej zakładki Default".
Fałszywa pamięć procesu, zero dostępu do gry."""
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("RETRONIC_TESTY", "1")
sys.dont_write_bytecode = True
sys.path.insert(0, os.environ.get("RETRONIC_KOD") or str(Path(__file__).resolve().parent.parent))

import wiadomosci as W  # noqa: E402

wyniki = []


def sprawdz(nazwa, warunek, info=""):
    wyniki.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + (f"  {info}" if not warunek and info else ""))


ROZM = 0x30000
VT = 0x500000
PANEL, BUFOR, ETYK, MAPA, BLOK = 0x12000, 0x13000, 0x14000, 0x15000, 0x16000


class FalszywyProces:
    def __init__(self):
        self.m = bytearray(ROZM)

    def czytaj(self, adres, dlugosc):
        if adres < 0 or adres >= ROZM:
            return b""
        return bytes(self.m[adres:adres + dlugosc])

    def regiony(self):
        return [(0, ROZM)]

    def u32(self, adres, *v):
        struct.pack_into("<%dI" % len(v), self.m, adres, *v)

    def napis(self, adres, tekst):
        b = tekst.encode()
        self.m[adres:adres + len(b)] = b
        self.u32(adres + 0x10, len(b), 15)


def swiat(deque, z_wiadomoscia=False):
    p = FalszywyProces()
    p.u32(PANEL, VT)
    p.napis(PANEL + W.ID, "tabPanel")
    p.u32(BUFOR, VT)
    p.napis(BUFOR + W.ID, "consoleBuffer")
    p.u32(BUFOR + W.RODZIC, PANEL)
    p.u32(BUFOR + W.DZIECI, *deque)
    if z_wiadomoscia:
        p.u32(ETYK, VT)
        p.napis(ETYK + W.ID, "consoleLabel1")
        p.u32(ETYK + W.RODZIC, BUFOR)
        p.u32(ETYK + W.CZAS_MS, 1234)
        struct.pack_into("<3f", p.m, ETYK + W.KOLOR, 1.0, 1.0, 1.0)
        b = b"12:34 Ala: hi"
        p.m[ETYK + W.TEKST:ETYK + W.TEKST + len(b)] = b
        p.u32(ETYK + W.TEKST + 0x10, len(b), 15)
        p.u32(MAPA, BLOK, 0, 0, 0, 0, 0, 0, 0)
        p.u32(BLOK, ETYK, 0, 0, 0)
    return p


# 1) pusty bufor (cztery zera) = poprawny; lista dzieci pusta
p = swiat((0, 0, 0, 0))
sprawdz("pusty bufor (0,0,0,0) uznany za poprawny", W._poprawny_bufor(p, BUFOR))
sprawdz("pusty bufor: _odczytaj_bufor = [] (nie None)", W._odczytaj_bufor(p, BUFOR) == [])
sprawdz("pusty bufor: _deque bez puste_zero nadal None (ogólna kontrola bez zmian)", W._deque(p, BUFOR) is None)
bufory, paski, _ = W._skan(p)
sprawdz("skan znajduje pusty bufor", bufory == [BUFOR], bufory)

# 2) śmieci nie przechodzą: zera tylko w komplecie
for nazwa, d in (("liczba=5 przy mapie 0", (0, 0, 0, 5)), ("przesunięcie 7 przy mapie 0", (0, 0, 7, 0)),
                 ("rozmiar mapy 8 przy mapie 0", (0, 8, 0, 0)), ("mapa wskazuje, rozmiar 0", (MAPA, 0, 0, 0)),
                 ("rozmiar mapy nie jest potęgą 2", (MAPA, 6, 0, 1))):
    sprawdz("odrzucone: " + nazwa, not W._poprawny_bufor(swiat(d), BUFOR))

# 3) pusty bufor tylko z vtable gry, id i rodzicem
p = swiat((0, 0, 0, 0))
p.u32(BUFOR, 0x1234)
sprawdz("obcy vtable: odrzucony", not W._poprawny_bufor(p, BUFOR))
p = swiat((0, 0, 0, 0))
p.napis(BUFOR + W.ID, "consoleBuffeX")
sprawdz("inne id: odrzucone", not W._poprawny_bufor(p, BUFOR))
p = swiat((0, 0, 0, 0))
p.napis(PANEL + W.ID, "inny_panel")
sprawdz("inny rodzic: odrzucony", not W._poprawny_bufor(p, BUFOR))
p = swiat((0, 0, 0, 0))
p.m[BUFOR:BUFOR + 0x90] = bytes(0x90)
sprawdz("wyzerowana pamięć (zwolniony widget): odrzucona", not W._poprawny_bufor(p, BUFOR))

# 4) bufor z wiadomością czyta się jak dotąd
p = swiat((MAPA, 8, 0, 1), z_wiadomoscia=True)
sprawdz("bufor z 1 wiadomością poprawny", W._poprawny_bufor(p, BUFOR))
el = W._odczytaj_bufor(p, BUFOR)
sprawdz("bufor z 1 wiadomością: odczyt", el is not None and len(el) == 1 and el[0][1] == b"12:34 Ala: hi", el)

print("\n%d/%d OK" % (sum(wyniki), len(wyniki)))
sys.exit(0 if all(wyniki) else 1)
