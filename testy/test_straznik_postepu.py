"""Strażnik postępu (13.10, P2b/P2c wg zadania) i blokujący wyjście (P1b): jednostkowo na atrapach. Atrapy, bez X11."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import cavebot, bot

cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.RUNA_AKTYWNA = 0
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Swiat:
    def __init__(s):
        s.t = 0.0; s.poz = [100, 100, 7]; s.flaga = False; s.w_grze = 99; s.klik = []; s.klawisze = []; s.hp_m = 100
    def zegar(s): return s.t
    def spij(s, d): s.t += d
    def zapytaj(s, z):
        s.t += 0.01
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 190, "max_hp": 190, "mana": 100, "max_mana": 100}}
        if z["cmd"] == "cel_ataku":
            return {"id": s.w_grze}
        if z["cmd"] == "stwory":
            ja = {"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": 7, "hp": 100}
            m = {"id": 1234510, "nazwa": "Troll", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": s.hp_m}
            if s.flaga is not None:
                m["atakowany"] = s.flaga
            return {"stwory": [ja, m]}

class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
    def krok(p, *a, **k): p.s.klawisze.append('krok')
    def kliknij(p, *a, **k): return True

def zrob(s):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: [])
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: s.klik.append(s.t), alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=loot, okrazenia=1, jedzenie="F5", czy_atakowany=lambda m, g: m.get("atakowany"))
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    return b

def tick(s, b, dt=0.1):
    s.t += dt; b.tick()




cavebot.STRAZNIK_POSTEP = 1
s = Swiat(); b = zrob(s)
b.stan = "IDZ"
G = {"exp": 100}
poz = (100, 100, 7)
b.cel = {"id": 5, "nazwa": "Troll", "hp": 80}
b.zwloki_czekajace = [((101, 100, 7), 0.0)]
for t in (0.0, 30.0, 89.0):
    b._straznik_postepu(G, poz, t)
sprawdz("1 przed 90 s: bez resetu", b.cel is not None)
b._straznik_postepu(G, poz, 91.0)
sprawdz("2 po 90 s: reset stanu walki (cel, zwłoki, Escape)", b.cel is None and not b.zwloki_czekajace and "Escape" in s.klawisze)
b._straznik_postepu({"exp": 150}, poz, 100.0)
sprawdz("3 przyrost exp zeruje odliczanie", b.straznik_post["s"] == 0 and b.straznik_post["t"] == 100.0)
b.stan = "PRZERWA"
b._straznik_postepu(G, poz, 500.0)
sprawdz("4 PRZERWA: brak odpaleń", b.straznik_post["t"] is None)
b.stan = "IDZ"; s.klawisze.clear()
b._straznik_postepu(G, poz, 600.0)
b._straznik_postepu(G, poz, 700.0)
sprawdz("5 S1 raz na stagnację", s.klawisze.count("Escape") == 1)
b._straznik_postepu(G, poz, 781.0)
sprawdz("6 S2 (180 s): skok na trasę (idx ustawiony)", b.straznik_post["s"] == 2, str(b.straznik_post))
cavebot.STRAZNIK_POSTEP = 0
b.straznik_post.update(t=None, s=0)
b._straznik_postepu(G, poz, 1000.0); b._straznik_postepu(G, poz, 2000.0)
sprawdz("7 STRAZNIK_POSTEP=0: nic", b.straznik_post["s"] == 0 and b.straznik_post["t"] is None)

# P1b: blokujący na wyjściu, BLOK_WYJSCIE=1 i 0
b.ostatni_blokujacy = ((101, 100), 77)
cel = {"id": 5, "nazwa": "Troll", "x": 110, "y": 100, "z": 7, "hp": 40}
m = {"id": 77, "nazwa": "Troll", "x": 101, "y": 100, "z": 7, "hp": 100, "gracz": False}
cavebot.BLOK_WYJSCIE = 0
sprawdz("8 BLOK_WYJSCIE=0: bez rozprawy", b._blokujacy_wyjscia(cel, [m], poz, 1.0) is None and b.rozprawa is None)
cavebot.BLOK_WYJSCIE = 1
r = b._blokujacy_wyjscia(cel, [m], poz, 1.0)
sprawdz("9 BLOK_WYJSCIE=1: rozprawa z blokującym, powrót do celu",
        r is not None and b.rozprawa and b.rozprawa["id"] == 77 and b.rozprawa["wroc"] == 5)
b.ostatni_blokujacy = ((105, 100), 77)
sprawdz("10 blokujący dalej niż 1: brak rozprawy", b._blokujacy_wyjscia(cel, [dict(m, x=105)], poz, 1.0) is None)
print("WYNIK", "OK" if all(ok) else "FAIL"); sys.exit(0 if all(ok) else 1)
