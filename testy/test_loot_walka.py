"""LOOT_DYNAMICZNY: loot w walce dynamiczniej (zwłoki obok od razu, brak_okna bez powtórek, inne piętro, okno otwarte).
Atrapy (RETRONIC_TESTY=1), bez gry."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types, tempfile
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot, pokretla

cavebot.REAKCJA = (0.0, 0.0); cavebot.ML_CZAR_AKTYWNY = 0; cavebot.UH_AKTYWNY = 0
cavebot.UH_STAN_PLIK = Path(tempfile.mkdtemp()) / "uh.json"
cavebot.log = lambda *a: None
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Swiat:
    def __init__(s): s.t = 0.0; s.poz = [100, 100, 7]; s.stwory = []; s.hp = 100
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def gracz(s): return {"hp": s.hp * 1.9, "max_hp": 190, "mana": 50, "max_mana": 125, "proc": float(s.hp)}
    def zapytaj(s, z):
        s.t += 0.01
        if z["cmd"] == "gracz": return {"gracz": s.gracz()}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}
            return {"stwory": [ja] + [dict(m) for m in s.stwory]}
        return {}
class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): pass

def mob(x, y=100, id=9, hp=100, z=7, nazwa="Troll"):
    return {"id": id, "nazwa": nazwa, "gracz": False, "x": x, "y": y, "z": z, "hp": hp}

def nowy(dyn=1):
    cavebot.LOOT_DYNAMICZNY = dyn
    cavebot.LOOT_SZYBKI_STYKAJACE = 0      # 23.10: te testy opisują dawną regułę (przylegający mob = loot odłożony); nową pokrywa test_loot_styk.py
    s = Swiat()
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: [], ile_jedzenia=lambda: 10)
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj, atak=lambda m, g: None,
                        alarm=lambda w: None, spij=s.spij, zegar=s.zegar, loot=loot, okrazenia=1, jedzenie="F5")
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    b.REC = []
    b.zbierz_loot = lambda zw: (b.REC.append(tuple(zw)), "ok")[1]
    return s, b

def zabij(s, b, zwloki_xyz, zywe):
    """Zabicie celu na zwloki_xyz; zywe = lista świeżych mobów w ostatnie_stwory."""
    s.stwory = list(zywe)
    b.ostatnie_stwory = [dict(m) for m in s.stwory]
    b.cel = {"id": 5, "nazwa": "Troll", "poz": zwloki_xyz, "hp": 0, "odl": 1}
    b.zgon_celu(s.gracz(), tuple(s.poz), pewny=True)

# kontrakt
sprawdz("0 pokrętło w pokretla", pokretla.ZAKRESY["LOOT_DYNAMICZNY"] == (0, 1)
        and pokretla.waliduj({"LOOT_DYNAMICZNY": 0})[0] == {"LOOT_DYNAMICZNY": 0})

# 1. zwłoki obok, żywy mob w odl 3
s, b = nowy(0); zabij(s, b, (101, 100, 7), [mob(103)])
sprawdz("1a LOOT_DYNAMICZNY=0: odłożone jak dotąd", b.REC == [] and any(tuple(z) == (101, 100, 7) for z, _ in b.zwloki_czekajace))
s, b = nowy(1); zabij(s, b, (101, 100, 7), [mob(103)])
sprawdz("1b =1: zbierane od razu", b.REC == [(101, 100, 7)], b.REC)
s, b = nowy(1); zabij(s, b, (100, 100, 7), [mob(103)])
sprawdz("1c =1: zwłoki pod nogami też od razu", b.REC == [(100, 100, 7)], b.REC)
# 2. blokady
s, b = nowy(1); zabij(s, b, (101, 100, 7), [mob(100, 101)])
sprawdz("2a mob przylegający: odłożone", b.REC == [] and b.zwloki_czekajace)
s, b = nowy(1); s.hp = 40; b.prog_aktualny = 30.0; zabij(s, b, (101, 100, 7), [mob(103)])
sprawdz("2b HP 40% (<= próg+15): odłożone", b.REC == [] and b.zwloki_czekajace)
s, b = nowy(1); b.ucieczka = True; zabij(s, b, (101, 100, 7), [mob(103)])
sprawdz("2c ucieczka: odłożone", b.REC == [] and b.zwloki_czekajace)
s, b = nowy(1); zabij(s, b, (104, 100, 7), [mob(106)])
sprawdz("2d zwłoki w odl 4: odłożone (nie biegniemy w walce)", b.REC == [] and b.zwloki_czekajace)
# 3. inne piętro
s, b = nowy(1); s.poz = [100, 100, 8]; zabij(s, b, (101, 100, 7), [])
sprawdz("3a inne piętro: bez próby lootu, odłożone", b.REC == [] and any(z[2] == 7 for z, _ in b.zwloki_czekajace))
sprawdz("3b inne piętro nie jest 'do zebrania' na z8", b.zwloki_do_zebrania((100, 100, 8)) is None and b.zwloki_czekajace)
b.zwloki_do_zebrania((100, 100, 7))   # po powrocie na z7 nadal jest na liście
s, b = nowy(0); b.zwloki_czekajace = [((101, 100, 7), s.t)]; b.zwloki_do_zebrania((100, 100, 8))
sprawdz("3c =0: stare zachowanie (inne piętro kasowane)", b.zwloki_czekajace == [])
# 4. brak_okna: bez powtórek w walce, jedna po walce, potem porzucone
s, b = nowy(1); zw = (101, 100, 7); b.zwloki_czekajace = [(zw, s.t)]; b.zwloki_wiek[zw] = s.t
b._zw_oznacz_brak_okna(zw)
sprawdz("4a po 1x brak_okna: lww_wybierz pomija", b._lww_wybierz((100, 100, 7), [], s.t) is None)
lista = [mob(104)]
b.cel = None; b.loot_chlod_do = 0
sprawdz("4b przed celem pomija", b._zwloki_przed_celem(None, lista, s.gracz(), (100, 100, 7), lista, s.t) is False and b.REC == [])
sprawdz("4c po walce: jedna próba", b.zwloki_do_zebrania((100, 100, 7)) == zw)
b.zwloki_czekajace = [(zw, s.t)]; b._zw_oznacz_brak_okna(zw)
sprawdz("4d po 2x brak_okna: porzucone", b.zwloki_do_zebrania((100, 100, 7)) is None and b.zwloki_czekajace == [])
s, b = nowy(0); b._zw_oznacz_brak_okna(zw)
sprawdz("4e =0: bez zmian", b._zw_brak_okna_n(zw) == 0)
# nowe zwłoki na tym samym polu: licznik od zera
s, b = nowy(1); b._zw_oznacz_brak_okna(zw); b.odloz_zwloki(zw, nowe=True)
sprawdz("4f nowe zabicie resetuje licznik", b._zw_brak_okna_n(zw) == 0)
# 5. przed celem: zwłoki obok, mob w odl 2
s, b = nowy(1); zw = (101, 100, 7); b.zwloki_czekajace = [(zw, s.t)]; b.loot_chlod_do = 0
lista = [mob(102, 101)]
r = b._zwloki_przed_celem(None, lista, s.gracz(), (100, 100, 7), lista, s.t)
sprawdz("5a =1: zwłoki obok zbierane przy mobie w odl 2", r is True and b.REC == [zw], b.REC)
s, b = nowy(0); b.zwloki_czekajace = [(zw, s.t)]; b.loot_chlod_do = 0
r = b._zwloki_przed_celem(None, lista, s.gracz(), (100, 100, 7), lista, s.t)
sprawdz("5b =0: dawne (mob w odl 2 blokuje)", r is False and b.REC == [])
s, b = nowy(1); zw2 = (104, 100, 7); b.zwloki_czekajace = [(zw2, s.t)]; b.loot_chlod_do = 0
lista = [mob(102, 101)]
r = b._zwloki_przed_celem(None, lista, s.gracz(), (100, 100, 7), lista, s.t)
sprawdz("5c =1: dalsze zwłoki (odl 4) przy mobie w odl 2: nie", r is False and b.REC == [])
lista = [mob(107)]
r = b._zwloki_przed_celem(None, lista, s.gracz(), (100, 100, 7), lista, s.t)
sprawdz("5d =1: dalsze zwłoki gdy mob >= 3: zbierane", r is True and b.REC == [zw2], b.REC)
# 6. okno otwarte: cel_daleko nie przerywa
s, b = nowy(1); zw = (101, 100, 7)
cel = mob(104); cel["atakowany"] = True
b.lww = {"zw": zw, "stan": {"faza": "przenies"}, "t0": s.t, "t_ost": s.t, "klik_t": None, "kroki": 1}
b.zwloki_czekajace = [(zw, s.t)]; b.hp_gracza_spadek = -1e9; b.hp_wzrost = s.t; b.pamiec = None; b.w_poscigu = False
pw = b._lww_powod_licz(cel, s.gracz(), (100, 100, 7), [cel], s.t)
sprawdz("6a okno otwarte, cel w odl 3: nie 'cel_daleko'", pw != "cel_daleko", pw)
b.lww["stan"]["faza"] = "czekaj"
pw = b._lww_powod_licz(cel, s.gracz(), (100, 100, 7), [cel], s.t)
sprawdz("6b okno nieotwarte: 'cel_daleko' jak dotąd", pw == "cel_daleko", pw)
b.lww["stan"]["faza"] = "przenies"; cel = mob(108); cel["atakowany"] = True
pw = b._lww_powod_licz(cel, s.gracz(), (100, 100, 7), [cel], s.t)
sprawdz("6c okno otwarte, cel w odl 8: 'cel_daleko'", pw == "cel_daleko", pw)
s, b = nowy(0); b.lww = {"zw": zw, "stan": {"faza": "przenies"}, "t0": 0, "t_ost": 0, "klik_t": None, "kroki": 1}
cel = mob(104); cel["atakowany"] = True
sprawdz("6d =0: 'cel_daleko' jak dotąd", b._lww_powod_licz(cel, s.gracz(), (100, 100, 7), [cel], s.t) == "cel_daleko")
# 7. UH nie gubi zwłok (zwloki_do_zebrania zdejmowało wpis)
s, b = nowy(1); cavebot.UH_W_WALCE = 0; b.zwloki_czekajace = [((102, 100, 7), s.t)]
bl = b._uh_blokada(s.gracz(), (100, 100, 7), s.t, [])
sprawdz("7 _uh_blokada: 'zwloki', lista nietknięta", bl == "zwloki" and len(b.zwloki_czekajace) == 1, (bl, b.zwloki_czekajace))

# 8. zwłoki na ostatnio widzianym polu (nie ekstrapolacja), od razu w tym samym ticku zabicia
def zabij2(s, b, ostatnie, krok, slad, zywe):
    s.stwory = list(zywe); b.ostatnie_stwory = [dict(m) for m in s.stwory]
    b.cel = {"id": 5, "nazwa": "Troll", "poz": ostatnie, "hp": 0, "odl": 1, "krok": krok, "krok_czas": s.t, "slad": list(slad)}
    b.zgon_celu(s.gracz(), tuple(s.poz), pewny=True)
s, b = nowy(1); zabij2(s, b, (100, 101, 7), (1, 0), [(99, 101), (100, 101)], [mob(103)])
sprawdz("8a zabity na (0,1): pierwszy klik w (0,1) w tym samym ticku, nie w ekstrapolowane (1,1)",
        b.REC and b.REC[0] == (100, 101, 7) and (101, 101, 7) not in b.REC[:1], b.REC)
s, b = nowy(0); zabij2(s, b, (100, 101, 7), (1, 0), [(99, 101), (100, 101)], [])
sprawdz("8b =0: dawne zachowanie (ekstrapolacja najpierw)", b.REC and b.REC[0] == (101, 101, 7), b.REC)
s, b = nowy(1); zabij2(s, b, (100, 101, 7), (1, 0), [(99, 101), (100, 101)], [])
sprawdz("8c kandydaci: ostatnie, skok celu (-1,1), ekstrapolacja",
        b.pola_zwlok({"poz": (100, 101, 7), "krok": (1, 0), "krok_czas": s.t, "slad": [(99, 101), (100, 101)]})
        == [(100, 101, 7), (99, 101, 7), (101, 101, 7)])
# 8d. mob przylega: odłożone wszystkie kandydaty przy nas, po udanym lootcie jednego grupa znika
s, b = nowy(1); zabij2(s, b, (100, 101, 7), (1, 0), [(99, 101), (100, 101)], [mob(101, 101, id=11)])
pola = sorted(z for z, _ in b.zwloki_czekajace)
sprawdz("8d mob przylega: odłożone (ostatnie + skok + ekstrapolacja przy nas)", b.REC == [] and (100, 101, 7) in pola and (99, 101, 7) in pola, pola)
b._zw_usun_grupe((99, 101, 7))
sprawdz("8e po udanym lootcie grupa znika z listy", b.zwloki_czekajace == [], b.zwloki_czekajace)
# 8f. zwłoki w odl 3, żaden mob nie przylega: od razu (podejście), nie czekamy do końca walki
s, b = nowy(1); zabij2(s, b, (103, 100, 7), None, [(103, 100)], [mob(106, id=12)])
sprawdz("8f zwłoki w odl 3 i brak przylegających: zbierane od razu", b.REC == [(103, 100, 7)], b.REC)
s, b = nowy(1); zabij2(s, b, (103, 100, 7), None, [(103, 100)], [mob(101, 99, id=12)])
sprawdz("8g zwłoki w odl 3, mob przylega: po walce", b.REC == [] and b.zwloki_czekajace)
# 9. przegląd: mob w odl 3 nie przerywa podejścia (przeglad_odl = 1)
s, b = nowy(1); b.przeglad_odl = 1; b.przeglad_loot_ost = -9; b.hp_gracza_spadek = -1e9
s.stwory = [mob(103)]
sprawdz("9a mob w odl 3 nie przerywa loot.zbierz", b._przerwij_loot() is False)
s.stwory = [mob(101)]; b.przeglad_loot_ost = -9
sprawdz("9b mob przylegający przerywa", b._przerwij_loot() is True)

cavebot.LOOT_DYNAMICZNY = 1
print(f"\n{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
