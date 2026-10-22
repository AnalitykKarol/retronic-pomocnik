"""22.10 (Karol): okna depo, których nie da się zamknąć po składaniu, zamyka odejście od skrzyni. Offline, atrapy."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import serwis_akcje as SA

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)


def akcje(okna):
    a = object.__new__(SA.AkcjeZywe)
    stan = {"okna": list(okna)}
    a.kontenery = lambda: [{"nazwa": n, "numer": i} for i, n in enumerate(stan["okna"])]
    a._zamknij = lambda numer: None                 # klient „nie zamyka” okien
    a.log = lambda *x: None
    return a, stan


SA.time.sleep = lambda s: None
a, stan = akcje(["backpack", "blue backpack", "depot chest"])
odejscia = []
def odejdz():
    odejscia.append(1); stan["okna"] = ["backpack"]
a._zamknij_poza_plecakiem(odejdz)
sprawdz("1 okna zostały, odejście je zamyka: bez błędu, jedno odejście", odejscia == [1])

a, stan = akcje(["backpack", "depot chest"])
try:
    a._zamknij_poza_plecakiem(lambda: None); sprawdz("2 odejście nie pomogło: błąd depo", False)
except SA.SerwisBlad as e:
    sprawdz("2 odejście nie pomogło: błąd depo", "zostały otwarte okna" in str(e))

a, stan = akcje(["backpack", "depot chest"])
try:
    a._zamknij_poza_plecakiem(); sprawdz("3 bez odejścia: błąd jak dawniej", False)
except SA.SerwisBlad:
    sprawdz("3 bez odejścia: błąd jak dawniej", True)

a, stan = akcje(["backpack"])
odejscia = []
a._zamknij_poza_plecakiem(lambda: odejscia.append(1))
sprawdz("4 wszystko zamknięte: nie odchodzi", odejscia == [])

print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
