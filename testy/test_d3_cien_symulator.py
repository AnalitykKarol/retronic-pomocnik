#!/usr/bin/env python3
"""17.10 F3 (SYSTEM_RETRONIC): D3_REAKCJA>=1 = cień; rekord `d3_reakcja` ma dodatkowo pole `symulator` = co wybrałaby polityka
Z1-Z8 z narzedzia/symulator_zawieszek.py (klasa, opcja, plan, powód, zgodność z regułą, czas obliczeń). Nic się nie wykonuje.
Atrapy: mapa tekstowa, bez gry, X11 i runy. Domyślnie (D3_REAKCJA=0): telemetria bez zmian."""
import os
import sys
import tempfile
import time
import types
from pathlib import Path

os.environ.setdefault("RETRONIC_TESTY", "1")
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bot  # noqa: E402
import cavebot  # noqa: E402
import d3_zawieszka  # noqa: E402
import telemetria  # noqa: E402

wyniki = []


def sprawdz(nazwa, warunek, info=""):
    wyniki.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + (f"  {info}" if not warunek and info else ""))


cavebot.REAKCJA = (0.0, 0.0)
cavebot.DRUGI_CEL = 0.0
cavebot.STRAZNIK_CEL = 0
cavebot.D3_LOG, cavebot.D3_PROG_S, cavebot.D3_ASTAR_MAX = 1, 30.0, 6
DOMYSLNE = (cavebot.D3_REAKCJA, cavebot.D3_ALARM_S)


class Mapa:
    """Piętro 7: kieszeń 7x7 (x 98..104, y 98..104) w murze; piętro 8: wielka otwarta hala. Schody: flaga na (101,101,7)."""
    def __init__(s, schody=True, kieszen=True):
        s.schody, s.kieszen = schody, kieszen

    def przechodnie(s, x, y, z):
        if z == 8:
            return 0 <= x <= 300 and 0 <= y <= 300
        if z != 7:
            return False
        if s.kieszen:
            return 98 <= x <= 104 and 98 <= y <= 104
        return 0 <= x <= 300 and 0 <= y <= 300

    def schody_lub_dziura(s, x, y, z):
        return False


class Swiat:
    def __init__(s):
        s.t, s.poz, s.stwory, s.klawisze = 0.0, [100, 100, 7], [], []

    def zegar(s):
        return s.t

    def spij(s, d):
        s.t += d

    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0, "exp": 1000}}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}]}


class P:
    nazwa = "Ja"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        return tuple(p.s.poz)

    def klawisz(p, k):
        p.s.klawisze.append(k)

    def krok(p, k):
        p.s.klawisze.append(k)
        return False


def scena(mapa=None, przejscia=None, punkty=None, tele_klasa=telemetria.Telemetria):
    s = Swiat()
    b = cavebot.Cavebot(P(s), punkty or [(120, 100, 7), (130, 100, 7)], zapytaj=s.zapytaj, atak=lambda m, g: None,
                        alarm=lambda w: None, spij=s.spij, zegar=s.zegar, okrazenia=1,
                        loot=types.SimpleNamespace(zbierz=lambda zw, g: "ok"))
    tele = tele_klasa(Path(tempfile.mkdtemp()), zegar=s.zegar, zapis=False)
    tele.nazwa_postaci = "Ja"
    b.tele = tele
    b.mapa = mapa
    b.przejscia = przejscia or []
    return s, b, tele


def rek(tele, typ):
    return [r for r in tele.rek if r["typ"] == typ]


def ticki(b, s, od, do, poz=(100, 100, 7), krok=1.0):
    t = od
    while t <= do + 1e-9:
        s.t = t
        b.stan = "IDZ"
        b._d3_tick({"hp": 100, "max_hp": 100, "proc": 100.0, "exp": 1000}, poz, t)
        t += krok


SCHODY = [{"id": "s1:w_dol", "z": 7, "wej": (101, 101, 7), "kroki": [(101, 101, 8)], "wyj": (101, 101, 8),
           "koszt": 4, "gniazdo": False, "pieta": True}]

# --- 1. domyślnie 0: brak d3_reakcja, rekord decyzja bez zmian ---
cavebot.D3_REAKCJA = 0
s, b, tele = scena(Mapa(), SCHODY)
ticki(b, s, 0, 35)
sprawdz("1a D3_REAKCJA=0: rekord decyzja jest, d3_reakcja brak (telemetria bez zmian)",
        len(rek(tele, "decyzja")) == 1 and rek(tele, "d3_reakcja") == [], [r["typ"] for r in tele.rek])
sprawdz("1b domyślne pokrętła 0", DOMYSLNE == (0, 0.0), DOMYSLNE)

# --- 2. =1, zamknięta kieszeń z schodami -> przejscie_pietra zgodnie z symulatorem ---
cavebot.D3_REAKCJA = 1
s, b, tele = scena(Mapa(), SCHODY)
ticki(b, s, 0, 35)
d = rek(tele, "d3_reakcja")
sprawdz("2a jeden rekord d3_reakcja z polem symulator", len(d) == 1 and "symulator" in d[0], d)
r = d[0] if d else {}
y = r.get("symulator") or {}
sprawdz("2b zamknięta kieszeń: klasa zamkniety, opcja przejscie_pietra, w OPCJE", y.get("klasa") == "zamkniety"
        and y.get("opcja") == "przejscie_pietra" and y.get("w_OPCJE") is True and y.get("opcja") in d3_zawieszka.OPCJE, y)
sprawdz("2c plan wyjścia: wejście schodów i piętro docelowe 8", (y.get("plan") or {}).get("wej") == [101, 101, 7]
        and (y.get("plan") or {}).get("pietro_docelowe") == 8, y.get("plan"))
sprawdz("2d powód, zgodność z regułą (reguła: pierwsza dopuszczalna = ?), wykonano False wszędzie",
        y.get("powod") and "zgodna_z_regula" in y and y.get("wykonano") is False and r.get("wykonano") is False, y)
sprawdz("2e prog_zamkniety_s 15 tylko informacyjnie; realny próg 30 bez zmian",
        y.get("prog_zamkniety_s") == 15.0 and y.get("prog_realny_s") == 30.0 and cavebot.D3_PROG_S == 30.0, y)
sprawdz("2f symulacja pełna: wyszedl, stop False", (y.get("symulacja") or {}).get("wynik") == "wyszedl"
        and (y.get("symulacja") or {}).get("stop") is False, y.get("symulacja"))
sprawdz("2g czas obliczeń zmierzony < 50 ms", isinstance(y.get("czas_ms"), float) and y["czas_ms"] < 50, y.get("czas_ms"))
sprawdz("2h nic nie wykonano: zero klawiszy, pozycja bez zmian", s.klawisze == [] and s.poz == [100, 100, 7], s.klawisze)

# --- 3. zamknięta kieszeń bez wyjścia -> alarm ---
s, b, tele = scena(Mapa(), [])
ticki(b, s, 0, 35)
y = (rek(tele, "d3_reakcja") or [{}])[0].get("symulator") or {}
sprawdz("3 kieszeń bez wyjścia: opcja alarm, powód brak_wyjscia", y.get("klasa") == "zamkniety" and y.get("opcja") == "alarm"
        and y.get("powod") == "brak_wyjscia", y)

# --- 4. otwarty obszar (duża hala, wolna droga do celu): klasa otwarty, bez progu 15 s, szybko ---
s, b, tele = scena(Mapa(kieszen=False), [])
ticki(b, s, 0, 35)
y = (rek(tele, "d3_reakcja") or [{}])[0].get("symulator") or {}
sprawdz("4a obszar otwarty: klasa otwarty, opcja z OPCJE, brak prog_zamkniety_s", y.get("klasa") == "otwarty"
        and y.get("opcja") in d3_zawieszka.OPCJE and y.get("prog_zamkniety_s") is None, y)
sprawdz("4b otwarty obszar < 50 ms", isinstance(y.get("czas_ms"), float) and y["czas_ms"] < 50, y.get("czas_ms"))

# --- 5. brak mapy = UNKNOWN, nie zgadywanie; tick się nie wywraca ---
s, b, tele = scena(None, [])
ticki(b, s, 0, 35)
y = (rek(tele, "d3_reakcja") or [{}])[0].get("symulator") or {}
sprawdz("5 brak mapy: wynik brak_danych, wykonano False", y.get("wynik") == "brak_danych" and y.get("wykonano") is False, y)

# --- 6. błąd symulatora nie wywraca ticka; reguła F1 dalej zapisana ---
orig = d3_zawieszka.Zawieszka._cien_licz
d3_zawieszka.Zawieszka._cien_licz = lambda self, *a: (_ for _ in ()).throw(RuntimeError("zepsuty symulator"))
s, b, tele = scena(Mapa(), SCHODY)
try:
    ticki(b, s, 0, 35)
    ok = True
except Exception as e:
    ok = False
    print(e)
d = rek(tele, "d3_reakcja")
sprawdz("6 błąd symulatora: tick idzie dalej, d3_reakcja bez pola symulator", ok and len(d) == 1 and "symulator" not in d[0], d)
d3_zawieszka.Zawieszka._cien_licz = orig

# --- 7. wydajność: średnio < 50 ms na wielu zawieszkach w kieszeni i w hali; budżet przełącza tryb ---
czasy = []
for mapa, prz in ((Mapa(), SCHODY), (Mapa(kieszen=False), []), (Mapa(), [])):
    for _ in range(10):
        s, b, tele = scena(mapa, prz)
        ticki(b, s, 0, 35)
        c = (rek(tele, "d3_reakcja") or [{}])[0].get("symulator", {}).get("czas_ms")
        if c is not None:
            czasy.append(c)
sr = sum(czasy) / len(czasy) if czasy else 999
sprawdz("7a średni czas obliczeń < 50 ms (30 zawieszek)", len(czasy) == 30 and sr < 50, (len(czasy), sr))
zl = d3_zawieszka.Zawieszka(types.SimpleNamespace(), cavebot)
zl.cien_czasy = [80.0, 90.0]
zl._cien_licz = lambda *a: (time.sleep(0.06), {})[1]
zl._cien_symulator((1, 1, 7), None)
sprawdz("7b średnio > 50 ms: tryb skrócony, potem wyłączony", zl.cien_tryb == "skrocony", zl.cien_tryb)
zl.cien_czasy = [80.0, 90.0]
zl._cien_symulator((1, 1, 7), None)
sprawdz("7c po drugim przekroczeniu cień symulatora wyłączony (None)", zl.cien_tryb == "wylaczony"
        and zl._cien_symulator((1, 1, 7), None) is None, zl.cien_tryb)

# --- 8. D3_REAKCJA=2 nadal odrzucone, domyślne 0 ---
import pokretla  # noqa: E402
ok_, bl = pokretla.waliduj({"D3_REAKCJA": 2})
sprawdz("8 D3_REAKCJA=2 odrzucone", not ok_ and bl)

cavebot.D3_REAKCJA, cavebot.D3_ALARM_S = DOMYSLNE
print(f"\n{sum(wyniki)}/{len(wyniki)} OK")
sys.exit(0 if all(wyniki) else 1)
