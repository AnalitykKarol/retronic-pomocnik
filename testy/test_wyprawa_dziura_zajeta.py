"""Wypad/wyprawa: przejście z7 -> z8 przy dziurze (rampie) o 1 pole od pola stania i zajętym otoczeniu.
Incydent 19.10 19:33-19:53 (Mastafian, wyprawa depo po ucieczce przed PK, Edron): plan z nagrania zakładał dziurę na
(33167,31813,7) = (x, y) lądowania, a rampa w dół leży na (33167,31812,7) (flaga 2 mapy), więc stoi (33167,31811,7) miało
cheb 2 do dziury: etap DZIURA cofał się do IDZ, IDZ uznawał ostatni punkt za osiągnięty i znów DZIURA: 20 min pętli bez
żadnego logu. Teraz: (1) sąsiednie pola z flagą 2 w promieniu 1 od nas są próbowane (tylko wolne od graczy), (2) bezpiecznik
WYPAD_ETAP_MAX_S kończy bezpostępowy etap przejścia awarią z logiem i powiadomieniem. Atrapy + prawdziwa mapa i prawdziwy
plik trasy gobliny_edron_do_depo.json; nic nie trafia do gry (RETRONIC_TESTY=1)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import copy
import json
import sys
import types
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import bot
import mapa as _mapa
import wypad

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test")
    sys.exit(0)
MAPA = _mapa.Mapa()

STOI = (33167, 31811, 7)
RAMPA = (33167, 31812, 7)        # flaga 3 w mapie; krok w dół => z8 (33167, 31813, 8)
LAND = (33167, 31813, 8)
TRASA = [tuple(p) for p in json.loads((KAT / "trasy" / "gobliny_edron_do_depo.json").read_text())]


class FlatMapa:
    """Mapa bez flag zmiany piętra: wszystko przechodnie."""
    def flagi(self, x, y, z): return 1
    def przechodnie(self, x, y, z): return True


class Swiat:
    def __init__(s, poz, zajete=(), mapa=MAPA):
        s.t = 0.0
        s.poz = list(poz)
        s.zajete = {tuple(p) for p in zajete}       # pola (x, y) zajęte przez graczy (jak w kolejce w poczcie)
        s.mapa = mapa
        s.kroki = []
        s.powiadomienia = []


class Postac:
    nazwa = "Mastafian"

    def __init__(p, s): p.s = s

    def pozycja(p): return tuple(p.s.poz)

    def krok(p, k):
        s = p.s
        d = bot.KIERUNKI[k]
        n = (s.poz[0] + d[0], s.poz[1] + d[1], s.poz[2])
        s.t += 0.2
        s.kroki.append((k, tuple(s.poz)))
        if (n[0], n[1]) in s.zajete:
            return tuple(s.poz)                     # pole zajęte: stoimy w miejscu
        if s.mapa.flagi(*n) & 2:
            s.poz[:] = [n[0], n[1] + 1, n[2] + 1]   # rampa/schody w dół: ląduje się o pole dalej, piętro niżej
        else:
            s.poz[:] = list(n)
        return tuple(s.poz)


class CB:
    def __init__(c, s):
        c.s = s
        c.mapa = s.mapa
        c.postac = Postac(s)
        c.sciany = set()
        c.zablokowane = set()
        c.wypad_aktywny = True

    def zegar(c): return c.s.t
    def spij(c, d): c.s.t += d
    def pauza(c, a=0.1, b=0.3): c.s.t += (a + b) / 2
    def ustaw_stan(c, *a): pass
    def _wypad_reset_klik(c): pass
    def krok_do(c, cel): c.s.t += 0.3

    def zajete_bez_nas(c, poz):
        return [p for p in c.s.zajete if p != tuple(poz[:2])]

    def droga(c, od, do, dlugosc=0): return []

    def _idz_odcinek(c, punkty, idx):
        c.s.t += 0.6
        idx = min(idx + 1, len(punkty) - 1)
        if punkty[idx][2] == c.s.poz[2]:
            c.s.poz[:] = list(punkty[idx])
        return True, idx


class Ops:
    def __init__(o, s): o.s = s
    def uzyj_pole(o, pole, poz): o.s.t += 0.5       # Use na zwykłym polu nic nie robi
    def uzyj_lopate(o, pole, poz): o.s.t += 0.5


class Konf:
    PIETRA_LOPATA = 1
    PIETRA_LOPATA_TYLKO_Z7 = 1


def wypad_z(etapy, ei, s, konf=None):
    etapy = copy.deepcopy(etapy)        # etapy niosą stan prób (proby, nast): każdy test od zera
    cb = CB(s)
    logi = []
    ops = Ops(s)
    w = wypad.Wypad(cb, ops, konf=konf, log=logi.append, plan=(etapy, etapy))
    w.logi = logi
    w._powiadom = lambda tytul, tresc, pilnosc="normal", klucz="wypad": s.powiadomienia.append((tytul, tresc, klucz))
    w.stan = "WYPAD"
    w.faza = "do"
    w.etapy = etapy
    w.ei = ei
    w.pi = max(0, len(etapy[ei].get("punkty") or ()) - 1) if etapy[ei]["typ"] == "IDZ" else 0
    w.t_start = 0.0
    w.ost_obieg = 0.0
    return w


def jedz(s, w, maks_s, stop=None):
    """Obiegi wypadu jak z Cavebot.idz() (co 0,3 s), do `maks_s` czasu świata albo warunku `stop`."""
    while s.t < maks_s:
        s.t += 0.3
        w._obieg(s.t)
        if stop and stop():
            return True
    return False


def plan_edron():
    """Prawdziwy plan depo: koniec nagrania gobliny_edron_do_depo (z7 -> dziura -> z8 -> depo); (etapy, indeks etapu DZIURA)."""
    et = wypad.zbuduj_etapy(TRASA[150:], MAPA)
    ei = next(i for i, e in enumerate(et) if e["typ"] == "DZIURA")
    return et, ei


# --- 0. dane: potwierdzenie przyczyny -------------------------------------------------------------
et, ei_d = plan_edron()
e_d = et[ei_d]
sprawdz("0a plan: DZIURA planowana na (33167,31813,7), stoi (33167,31811,7), cheb 2 (stąd ostrzeżenie planu)",
        e_d["dziura"] == (33167, 31813, 7) and e_d["stoi"] == STOI and wypad.cheb(e_d["stoi"], e_d["dziura"]) == 2
        and bool(wypad.sprawdz_plan(et, MAPA)), e_d)
sprawdz("0b mapa: planowane pole bez flagi 2, rampa (33167,31812,7) z flagą 2, ląduje się na (33167,31813,8)",
        not MAPA.flagi(*e_d["dziura"]) & 2 and MAPA.flagi(*RAMPA) & 2 and LAND == tuple(e_d["ladunek"]),
        (MAPA.flagi(*e_d["dziura"]), MAPA.flagi(*RAMPA)))
sprawdz("0c etap przed dziurą to IDZ kończący się dokładnie na stoi", et[ei_d - 1]["typ"] == "IDZ"
        and tuple(et[ei_d - 1]["punkty"][-1]) == STOI)

# --- 1. incydent 19.10: stoimy na (33167,31811), gracze obok, rampa (33167,31812) wolna -----------------------
GRACZE = {(33167, 31811), (33168, 31811), (33169, 31811), (33171, 31810)}        # w tym "Ucho" na naszym polu
s = Swiat(STOI, zajete=GRACZE)
w = wypad_z(et, ei_d - 1, s)
jedz(s, w, 200, stop=lambda: s.poz[2] == 8)
sprawdz("1a przechodzi z7 -> z8 w kilka sekund mimo zajętego otoczenia (stary kod: pętla bez końca)",
        tuple(s.poz) == LAND and s.t < 30, (s.poz, round(s.t, 1), s.kroki[:3]))
sprawdz("1b to był krok w dół na rampę (33167,31812), nie w zajęte pole", s.kroki and s.kroki[-1] == ("Down", STOI), s.kroki)
sprawdz("1c każda próba w logu (pole sąsiednie z flagą mapy)", any("dziura próba" in l and "33167, 31812" in l for l in w.logi), w.logi)
sprawdz("1d log przejścia 'dziura z7 -> z8' i brak awarii", any("dziura z7 -> z8" in l for l in w.logi)
        and not any("awaria" in l for l in w.logi), w.logi)

# --- 2. rampa pod nami zajęta przez gracza, druga rampa (33168,31812) wolna, a pole (33168,31811) wolne --------------------------
GRACZE2 = (GRACZE - {(33168, 31811)}) | {RAMPA[:2]}
s = Swiat(STOI, zajete=GRACZE2)
w = wypad_z(et, ei_d - 1, s)
jedz(s, w, 200, stop=lambda: s.poz[2] == 8)
sprawdz("2a rampa zajęta: nie wchodzimy w nią, idziemy w bok i drugą rampą (33168,31812)",
        tuple(s.poz) == (33168, 31813, 8) and s.kroki and s.kroki[-1][0] == "Down" and s.kroki[-1][1][:2] == (33168, 31811),
        (s.poz, s.kroki))
sprawdz("2b żaden krok w zajęte pole (33167,31812): bez 'Down' z (33167,31811)", ("Down", STOI) not in s.kroki, s.kroki)
# 2c. rampa po skosie (33168,31812), oba pola pośrednie zajęte: nieosiągalna jednym krokiem, czekamy zamiast kręcić 'Right' w ścianę graczy
s = Swiat(STOI, zajete=GRACZE | {RAMPA[:2]})
w = wypad_z(et, ei_d - 1, s)
jedz(s, w, 30)
sprawdz("2c rampa po skosie za graczami: bez prób kroku w zajęte pole, w logu 'czekam'",
        not s.kroki and any("czekam" in l for l in w.logi), (s.kroki[:3], w.logi))

# --- 3. wszystkie pola z flagą zajęte: czekamy, a po WYPAD_ETAP_MAX_S awaria (log + powiadomienie) -----------------------
s = Swiat(STOI, zajete=GRACZE | {(33167, 31812), (33168, 31812)})
w = wypad_z(et, ei_d - 1, s)
jedz(s, w, 200, stop=lambda: w.faza == "z")
sprawdz("3a zajęte rampy: awaria po ~WYPAD_ETAP_MAX_S (stary kod: milczał, w logu nic)",
        w.faza == "z" and 55 <= s.t <= 75, (w.faza, round(s.t, 1)))
sprawdz("3b awaria jest w logu z powodem i z poz", any("przejście DZIURA" in l and "awaria" in l and "33167" in l for l in w.logi), w.logi)
sprawdz("3c powiadomienie critical o przejściu bez postępu", any(p[2] == "wypad_przejscie" for p in s.powiadomienia), s.powiadomienia)
sprawdz("3d przez ten czas żadnego kroku w zajęte pole", not s.kroki, s.kroki)

# --- 4. brak jakiejkolwiek rampy w pobliżu (płaska mapa), stoimy 2 pola od dziury: bezpiecznik, nie cisza ---------------------
s = Swiat(STOI, mapa=FlatMapa())
w = wypad_z(et, ei_d - 1, s)
jedz(s, w, 200, stop=lambda: w.faza == "z")
sprawdz("4a bez rampy w pobliżu: awaria po ~60 s z logiem (stary kod: pętla bez końca)",
        w.faza == "z" and 55 <= s.t <= 75 and any("przejście DZIURA" in l for l in w.logi), (w.faza, round(s.t, 1), w.logi[-3:]))
k = Konf()
k.WYPAD_ETAP_MAX_S = 20.0
s = Swiat(STOI, mapa=FlatMapa())
w = wypad_z(et, ei_d - 1, s, konf=k)
jedz(s, w, 200, stop=lambda: w.faza == "z")
sprawdz("4b limit z pokrętła (konf.WYPAD_ETAP_MAX_S=20)", w.faza == "z" and 15 <= s.t <= 30, (w.faza, round(s.t, 1)))

# --- 5. to samo na linie (w górę): stoimy za daleko od pola liny i IDZ każe być 'na miejscu' --------------------------------
pts = [(100, 100, 8), (100, 98, 8), (100, 96, 7)]      # lina na (100,95,8), stoi (100,98,8): cheb 3
et_l = wypad.zbuduj_etapy(pts, FlatMapa())
sprawdz("5a plan: IDZ, LINA ze stoi 3 pola od liny", [e["typ"] for e in et_l] == ["IDZ", "LINA", "IDZ"]
        and wypad.cheb(et_l[1]["stoi"], et_l[1]["cel"]) == 3, et_l)
s = Swiat((100, 98, 8), mapa=FlatMapa())
w = wypad_z(et_l, 0, s)
jedz(s, w, 200, stop=lambda: w.faza == "z")
sprawdz("5b LINA bez postępu: awaria po ~60 s z logiem", w.faza == "z" and 55 <= s.t <= 75
        and any("przejście LINA" in l for l in w.logi), (w.faza, round(s.t, 1), w.logi[-3:]))

# --- 6. regresje: normalna dziura obok nas (flaga 2 na planowanym polu) i czekanie awarii w mieście nie ginie -----------------
# 6a. pewna dziura sąsiaduje ze stoi: jedna próba kroku i jesteśmy na dole
et_p = wypad.zbuduj_etapy([(33166, 31811, 7), (33167, 31811, 7), (33167, 31813, 8)], MAPA)
sprawdz("6a plan z niepewną dziurą cheb 2 jak w incydencie (kontrola konstrukcji)", et_p[1]["typ"] == "DZIURA" and not et_p[1]["pewna"], et_p)
et_ok = [{"typ": "IDZ", "punkty": [(0, 0, 7), (5, 5, 7)]},
         {"typ": "DZIURA", "stoi": (5, 5, 7), "dziura": (5, 6, 7), "ladunek": (5, 6, 8), "pewna": True},
         {"typ": "IDZ", "punkty": [(5, 6, 8), (7, 6, 8)]}]


class MapaDziura(FlatMapa):
    def flagi(self, x, y, z): return 3 if (x, y, z) == (5, 6, 7) else 1


s = Swiat((5, 5, 7), mapa=MapaDziura())
w = wypad_z(et_ok, 1, s)
jedz(s, w, 60, stop=lambda: s.poz[2] == 8)
sprawdz("6b pewna dziura obok stoi: krok i z8, bez logów prób 'sąsiednich'", s.poz[2] == 8 and s.kroki == [("Down", (5, 5, 7))]
        and not any("sąsiednie" in l for l in w.logi), (s.poz, s.kroki, w.logi))

# 6c. faza "z" (powrót w mieście): po awarii przejścia czekamy AWARIA_PO_S i ponawiamy, bezpiecznik nie kasuje tego czekania
s = Swiat(STOI, zajete=GRACZE | {(33167, 31812), (33168, 31812)})
w = wypad_z(et, ei_d - 1, s)
w.faza = "z"
jedz(s, w, 80)
n_pow = len(s.powiadomienia)
sprawdz("6c faza z: pierwsza awaria po ~60 s, potem czekanie (nast) zamiast kolejnych awarii co obieg",
        n_pow >= 1 and w.etapy[ei_d].get("nast", 0) > s.t - 1 and sum("; awaria" in l for l in w.logi) == 1,
        (n_pow, w.etapy[ei_d].get("nast"), w.logi[-4:]))

print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
