"""(Kopia atrap z test_wyprawa_dziura_zajeta.py) Wypad/wyprawa: przejście z7 -> z8 przy dziurze (rampie) o 1 pole od pola stania i zajętym otoczeniu.
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



# === 22.10 klik w schody (Karol: „kliknięcie myszką na pole schodów, gra sama go tam wyśle”) ===========================
# Incydent 22.10 11:24 (dawajkesh): gracz Deetasea na polu stania (33167,31811), bot 20 s klikał tam i z powrotem
# (33167,31810) <-> (33168,31807) („we dancing?” na czacie). Teraz: klik w wolne pole schodów, klient prowadzi sam.

def z_klikiem(s, ruszy=True):
    """Atrapa kliku klienta: postać idzie na kliknięte pole schodów (omijając graczy) i schodzi piętro niżej."""
    def klik(dx, dy):
        s.kliki.append((dx, dy))
        if not ruszy:
            return
        T = (s.poz[0] + dx, s.poz[1] + dy, s.poz[2])
        s.t += 0.5
        if s.mapa.flagi(*T) & 2 and (T[0], T[1]) not in s.zajete:
            s.poz[:] = [T[0], T[1] + 1, T[2] + 1]
    return klik

et, ei_d = plan_edron()
START = (33166, 31810, 7)

s = Swiat(START, zajete={(33167, 31811)}); s.kliki = []
w = wypad_z(et, ei_d - 1, s); w.cb.klik = z_klikiem(s)
jedz(s, w, 60, stop=lambda: s.poz[2] == 8)
sprawdz("K1 gracz na polu stania: klik w wolne schody i zejście na z8", s.poz[2] == 8 and len(s.kliki) == 1, (s.poz, s.kliki, w.logi[-3:]))
T1 = (START[0] + s.kliki[0][0], START[1] + s.kliki[0][1], 7) if s.kliki else None
sprawdz("K2 kliknięte pole to schody (flaga 2), nie pole przed schodami", T1 and MAPA.flagi(*T1) & 2, T1)
sprawdz("K3 bez kroków strzałkami i bez dreptania", not s.kroki, s.kroki)
sprawdz("K4 etap przesunięty za DZIURĘ (IDZ na z8)", w.ei == ei_d + 1 and w.etapy[w.ei]["typ"] == "IDZ", (w.ei, ei_d))
sprawdz("K5 log: klik w schody i zejście", any("klik w schody" in l for l in w.logi) and any("schody (klik) z7 -> z8" in l for l in w.logi), w.logi)

zaj_schody = {(x, y) for x in range(33164, 33172) for y in range(31809, 31815) if MAPA.flagi(x, y, 7) & 2}
s = Swiat(START, zajete={(33167, 31811)} | zaj_schody); s.kliki = []
w = wypad_z(et, ei_d - 1, s); w.cb.klik = z_klikiem(s)
jedz(s, w, 10)
sprawdz("K6 wszystkie schody zajęte: bez kliku, w logu 'zajęte ... czekam'", not s.kliki and any("zajęte przez graczy, czekam" in l for l in w.logi),
        (s.kliki, w.logi[-2:]))

s = Swiat(START, zajete={(33167, 31811)}); s.kliki = []
w = wypad_z(et, ei_d - 1, s); w.cb.klik = z_klikiem(s, ruszy=False)
jedz(s, w, 40, stop=lambda: w.faza != "do" or s.poz[2] == 8)     # atrapa _idz_odcinek „teleportuje”, dalej nie testujemy
sprawdz("K7 klik bez ruchu: najwyżej 3 kliki, potem dawna maszyneria", 1 <= len(s.kliki) <= 3, s.kliki)

s = Swiat(START, zajete={(33167, 31811)}); s.kliki = []
w = wypad_z(et, ei_d - 1, s, konf=types.SimpleNamespace(WYPAD_KLIK_SCHODY=0)); w.cb.klik = z_klikiem(s)
jedz(s, w, 10)
sprawdz("K8 pokrętło WYPAD_KLIK_SCHODY=0: bez kliku w schody", not s.kliki, s.kliki)

print(f"\nWYNIK {sum(ok)} / {len(ok)}")
sys.exit(0 if all(ok) else 1)
