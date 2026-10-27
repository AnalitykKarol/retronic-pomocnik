"""Rookgaard nie ma PK (Karol 25.10): ucieczka PK, karencja po restarcie i pauza GRACZ z czaszki nie dotyczą Rooka.
Regresja: Makumba (Rook, lvl 7) po restarcie uciekała do depo i stała 30 min przez wpis „Le Soku” (czaszka)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import sys
import types

sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import cavebot

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


C = cavebot.Cavebot if hasattr(cavebot, "Cavebot") else None
if C is None:
    C = next(v for v in vars(cavebot).values() if isinstance(v, type) and hasattr(v, "_pk_tick_u"))

sprawdz("1 depo Rooka (32061,32180,7) = Rook", cavebot.na_rooku((32061, 32180, 7)))
sprawdz("2 jaskinia z11 (31979,32152,11) = Rook", cavebot.na_rooku((31979, 32152, 11)))
sprawdz("3 Thais (32369,32241,7) to nie Rook", not cavebot.na_rooku((32369, 32241, 7)))
sprawdz("4 Ab'Dendriel (32669,31659,6) to nie Rook", not cavebot.na_rooku((32669, 31659, 6)))
sprawdz("5 Edron (33117,31774,8) to nie Rook", not cavebot.na_rooku((33117, 31774, 8)))

# karencja po restarcie, stan DEPO z start_wait na Rooku: pauza kończy się, tick nie zużywa obiegu
b = types.SimpleNamespace(pk_stan="DEPO", pk_start_wait=True, pk_start_sprawdzony=False)
r = C._pk_tick_u(b, {"proc": 100}, (32061, 32180, 7), 0.0)
sprawdz("6 Rook, DEPO po restarcie: koniec pauzy, brak reakcji", r is False and b.pk_stan is None and not b.pk_start_wait, vars(b))

# stan None na Rooku: żadnego skanu, żadnej karencji
b = types.SimpleNamespace(pk_stan=None, pk_start_wait=False, pk_start_sprawdzony=False)
r = C._pk_tick_u(b, {"proc": 100}, (32061, 32180, 7), 0.0)
sprawdz("7 Rook, brak stanu: bez reakcji PK", r is False and b.pk_stan is None and b.pk_start_sprawdzony, vars(b))

# czaszka nie robi z gracza groźnego na Rooku, GM nadal tak
cavebot.czaszka.czaszka_grozna = lambda n, *a, **k: True
s = {"nazwa": "Le Soku", "gracz": True}
sprawdz("8 Rook: gracz z czaszką nie jest groźny", C._gracz_grozny_tu(types.SimpleNamespace(gracz_grozny=C.gracz_grozny), s, (32061, 32180, 7)) is False)
sprawdz("9 poza Rookiem: gracz z czaszką groźny jak dotąd", C._gracz_grozny_tu(types.SimpleNamespace(gracz_grozny=C.gracz_grozny), s, (33117, 31774, 8)) is True)
sprawdz("10 Rook: GM nadal groźny", C._gracz_grozny_tu(types.SimpleNamespace(gracz_grozny=C.gracz_grozny), {"nazwa": "GM Test"}, (32061, 32180, 7)) is True)

print("WYNIK:", "PASS" if all(ok) else "FAIL", f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
