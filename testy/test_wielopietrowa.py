"""Trasa wielopiętrowa (pietra.py + Cavebot._idz_trasa) i plany wypadu po położeniu. Wyłącznie atrapy: bez X11,
bez gry. Świat = prawdziwa mapa (mapa.py) + prosty symulator ruchu i przejść pięter."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, types
sys.dont_write_bytecode = True
_R = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _R)
import cavebot, bot, mapa as _mapa, wypad, pietra
from pathlib import Path

TRASY = Path(_R) / "trasy"
LOG = []
_l0 = cavebot.log
cavebot.log = lambda *a: LOG.append(" ".join(map(str, a)))
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.PRZERWA_CO_MIX = ((1e9, 1e9, 1.0),) if hasattr(cavebot, "PRZERWA_CO_MIX") else None
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

M = _mapa.Mapa()
def f(x, y, z): return M.flagi(x, y, z)
def idzie(x, y, z):
    v = f(x, y, z); return bool(v & 1) and not v & 4 and not v & 2


class Swiat:
    """gora: 'use' (drabina: Ctrl+klik na R), 'krok' (schody: krok na R), 'nigdy' (przejście nie działa)."""
    def __init__(s, poz, gora="use", dol="krok"):
        s.t = 0.0; s.poz = list(poz); s.gora = gora; s.dol = dol
        s.zmiany = []; s.uzycia = []; s.nielegalne = 0; s.odwiedzone = set()
    def zegar(s): return s.t
    def klik(s, dx, dy):                                   # klient: klik w pole = marsz po najkrótszej drodze (8 kierunków)
        s.cel = (s.poz[0] + dx, s.poz[1] + dy, s.poz[2])
    def spij(s, d):
        s.t += d
        c = getattr(s, "cel", None)
        if c is None or d < 0.08 or tuple(s.poz) == c:
            return
        start = tuple(s.poz); skad = {start: None}; q = [start]
        for a in q:
            if a == c or len(skad) > 4000: break
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (a[0] + dx, a[1] + dy, a[2])
                    if (dx or dy) and n not in skad and idzie(*n):
                        skad[n] = a; q.append(n)
        if c not in skad:
            s.cel = None; return
        sciezka = []; a = c
        while a != start: sciezka.append(a); a = skad[a]
        for n in sciezka[::-1][:max(1, int(d / 0.2))]:
            z0 = s.poz[2]
            s.ruch(n[0] - s.poz[0], n[1] - s.poz[1])
            if s.poz[2] != z0:
                s.cel = None
                break
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 0, "max_mana": 0}}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}]}
    def ruch(s, dx, dy):
        x, y, z = s.poz[0] + dx, s.poz[1] + dy, s.poz[2]
        v = f(x, y, z)
        if not v & 1 or v & 4:
            s.nielegalne += 1; return
        if v & 2:                                           # dziura/schody w dół
            if s.dol == "nigdy":
                return
            s.zmiany.append((tuple(s.poz), z + 1)); s.poz[:] = [x, y, z + 1]; s.odwiedzone.add(tuple(s.poz)); return
        g = f(x, y, z - 1) if z else 0
        if s.gora == "krok" and g & 1 and g & 2 and idzie(x, y, z):    # schody w górę: sam krok na R
            s.zmiany.append((tuple(s.poz), z - 1)); s.poz[:] = [x, y + 1, z - 1]; s.odwiedzone.add(tuple(s.poz)); return
        s.poz[0], s.poz[1] = x, y; s.odwiedzone.add(tuple(s.poz))
    def uzyj(s, pole):
        s.uzycia.append(tuple(pole))
        x, y, z = pole
        if s.gora == "use" and z and f(x, y, z - 1) & 2 and f(x, y, z - 1) & 1 and idzie(x, y, z):
            s.zmiany.append((tuple(s.poz), z - 1)); s.poz[:] = [x, y + 1, z - 1]; s.odwiedzone.add(tuple(s.poz))
class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): pass
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2; przed = tuple(p.s.poz); p.s.ruch(*d); return tuple(p.s.poz) != przed
class Ops:
    def __init__(o, s): o.s = s
    def uzyj_pole(o, pole, poz): o.s.uzyj(pole)
    def uzyj_line(o, pole, poz): pass
class Gracz: pass

def zrob(s, punkty, **kw):
    atak = lambda m, g: None
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
    b = cavebot.Cavebot(P(s), punkty, zapytaj=s.zapytaj, atak=atak, alarm=lambda w: None, spij=s.spij,
                        zegar=s.zegar, loot=loot, mapa=M, klik=s.klik, **kw)
    b.pietra_ops = Ops(s)
    return b

def bieg(b, s, n):
    for i in range(n):
        if not b.tick(): return i
    return n

troll = [tuple(p) for p in json.loads((TRASY / "troll_cave.json").read_text())]
pietra_tras = sorted({p[2] for p in troll})
sprawdz("0 trasa troll_cave ma >1 piętro", len(pietra_tras) > 1, f"{pietra_tras}")

# 1. pełne okrążenie, drabina (Use) w górę, krok w dół
for tryb in ("use", "krok"):
    LOG.clear()
    s = Swiat(troll[0], gora=tryb)
    b = zrob(s, list(troll), okrazenia=1)
    n = bieg(b, s, 6000)
    z_ok = {p[2] for p in s.odwiedzone}
    sprawdz(f"1 okrążenie ({tryb}): przejścia wykonane", len(s.zmiany) >= 8, f"zmian={len(s.zmiany)} ticki={n}")
    sprawdz(f"1 okrążenie ({tryb}): oba piętra odwiedzone, co najwyżej kilka obić o ścianę", z_ok >= {8, 9} and s.nielegalne <= 3,
            f"z={z_ok} nielegalne={s.nielegalne}")
    sprawdz(f"1 okrążenie ({tryb}): bez porażek przejść", b.pietra_porazki == 0 and not any("NIEUDANE" in l for l in LOG))

# 2. przejście nigdy nie działa (w górę): porażki 3x -> bot się zatrzymuje, nie kręci w nieskończoność
LOG.clear()
s = Swiat(troll[0], gora="nigdy")
b = zrob(s, list(troll), okrazenia=1)
n = bieg(b, s, 20000)
sprawdz("2 przejście w górę nie działa: bot sam kończy po porażkach", n < 20000 and b.pietra_porazki >= 1,
        f"ticki={n} porazki={b.pietra_porazki} t={s.t:.0f}s")
sprawdz("2 logi po polsku o porażce", any("Przejście pięter" in l for l in LOG))

# 3. przejście w dół nie działa
LOG.clear()
s = Swiat(troll[0], dol="nigdy")
b = zrob(s, list(troll), okrazenia=1)
n = bieg(b, s, 20000)
sprawdz("3 przejście w dół nie działa: koniec bez pętli", n < 20000, f"ticki={n} porazki={b.pietra_porazki}")

# 4. pokrętło: TRASA_PIETRA=0 = stare zachowanie (moduł nie wołany)
s = Swiat(troll[0]); b = zrob(s, list(troll), okrazenia=1)
stary = cavebot.TRASA_PIETRA
try:
    cavebot.TRASA_PIETRA = 0
    sprawdz("4 TRASA_PIETRA=0: wyłączone", not b._pietra_wlaczone())
    cavebot.TRASA_PIETRA = 2
    sprawdz("4 TRASA_PIETRA=2: włączone dla trasy wielopiętrowej", b._pietra_wlaczone())
    b1 = zrob(Swiat((100, 100, 7)), [(100 + i, 100, 7) for i in range(1, 11)], okrazenia=1)
    sprawdz("4 TRASA_PIETRA=2: wyłączone dla trasy jednopiętrowej", not b1._pietra_wlaczone())
    cavebot.TRASA_PIETRA = 1
    sprawdz("4 TRASA_PIETRA=1: zawsze", b1._pietra_wlaczone())
finally:
    cavebot.TRASA_PIETRA = stary
sprawdz("4 pokrętło w pokretla.py", "TRASA_PIETRA" in __import__("pokretla").ZAKRESY)

# 5. pościg nie wchodzi na schody: pola zmiany piętra są zakazane (poza wypadem)
b = zrob(Swiat(troll[0]), list(troll), okrazenia=1)
dz = [(a, c) for a, c in zip(troll, troll[1:]) if c[2] > a[2]]
a, c = dz[0]
sprawdz("5 pole dziury zakazane w pościgu", b.pole_zmiany_pietra((c[0], c[1], a[2])) or b.pole_zmiany_pietra((a[0], a[1], a[2])) or
        any(b.pole_zmiany_pietra((x, y, a[2])) for x in range(a[0] - 2, a[0] + 3) for y in range(a[1] - 2, a[1] + 3)))
b.wypad_aktywny = True
sprawdz("5 w wypadzie zakaz zdjęty, a pętla pięter wyłączona", not b._pietra_wlaczone())

# 6. plany wypadu: pliki istnieją, są spójne, wybór po położeniu
pl = wypad.wczytaj_plany(TRASY, M)
sprawdz("6 wczytano plany rook/troll/kanały", {"rook", "troll", "thais_kanaly"} <= set(pl), f"{sorted(pl)}")
for nazwa in ("troll", "thais_kanaly"):
    p = pl[nazwa]
    bl = [b_ for et in p["etapy"] for b_ in wypad.sprawdz_plan(et, M)]
    sprawdz(f"6 plan {nazwa}: sprawdz_plan bez błędów", not bl, f"{bl[:3]}")
sprawdz("6 troll z z8 (jaskinia) -> plan troll", wypad.wybierz_plan(pl, troll[0]) == "troll")
sprawdz("6 troll z z9 -> plan troll", wypad.wybierz_plan(pl, next(p for p in troll if p[2] == 9)) == "troll")
sprawdz("6 kanały -> plan thais_kanaly", wypad.wybierz_plan(pl, (32360, 32242, 8)) == "thais_kanaly")
sprawdz("6 daleko od wszystkiego -> brak planu (stary plan)", wypad.wybierz_plan(pl, (100, 100, 7)) is None)
sprawdz("6 plan troll: NPC Gorn, rook: domyślny", pl["troll"]["npc"] == "Gorn" and pl["rook"]["npc"] is None)

# 7. trasa do_miasta troll: A* po grafie zgodnym z symulatorem (przejścia wykonalne)
do = json.loads((TRASY / "troll_do_miasta.json").read_text())
z_ = json.loads((TRASY / "troll_z_miasta.json").read_text())
s = Swiat(tuple(do[0]), gora="use")
b = zrob(s, [tuple(p) for p in do], okrazenia=1)
n = bieg(b, s, 6000)
sprawdz("7 troll_do_miasta przechodzi przejścia pięter w symulatorze", len(s.zmiany) >= 2 and s.nielegalne <= 3,
        f"zmian={len(s.zmiany)} nielegalne={s.nielegalne}")
sprawdz("7 kończy na z7 przy sklepie", s.poz[2] == 7, f"{s.poz}")
s = Swiat(tuple(z_[0]), gora="use")
b = zrob(s, [tuple(p) for p in z_], okrazenia=1)
n = bieg(b, s, 6000)
sprawdz("7 troll_z_miasta wraca do jaskini", s.poz[2] in (8,) and s.nielegalne <= 3, f"{s.poz}")

# 8. pole startowe przy schodach (13.10): przed próbą stajemy ortogonalnie ze schodami, po nieudanym Ctrl+klik
# zmieniamy pole zamiast krokować po skosie, a pole, z którego się udało, zapamiętujemy per schody
import tempfile
class SwiatS(Swiat):
    """Ctrl+klik działa tylko z pola `dobre` (None = z każdego); zapisuje pozycje, z których użyto."""
    def __init__(s, *a, dobre=None, **kw):
        super().__init__(*a, **kw); s.dobre = dobre; s.z_pol = []
    def uzyj(s, pole):
        s.z_pol.append((s.poz[0], s.poz[1]))
        if s.dobre is None or (s.poz[0], s.poz[1]) == s.dobre:
            super().uzyj(pole)
        else:
            s.uzycia.append(tuple(pole))
def _orto(R): return [(R[0] + dx, R[1] + dy) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)) if idzie(R[0] + dx, R[1] + dy, R[2])]
def _dobre(i):
    k = pietra.kandydaci(M, troll[i - 1], troll[i])[0]
    return troll[i][2] < troll[i - 1][2] and k["pewne"] and len(_orto(k["pole"])) >= 2
i8 = next(i for i in range(1, len(troll)) if _dobre(i))
R8 = pietra.kandydaci(M, troll[i8 - 1], troll[i8])[0]["pole"]
orto = _orto(R8)
sprawdz("8 schody w teście mają >=2 pola ortogonalne", len(orto) >= 2, f"R={R8[:2]} orto={orto}")
poz0 = next((R8[0] + dx, R8[1] + dy, R8[2]) for dx in (-1, 1) for dy in (-1, 1) if idzie(R8[0] + dx, R8[1] + dy, R8[2]))
def ortog(p): return max(abs(p[0] - R8[0]), abs(p[1] - R8[1])) == 1 and (p[0] == R8[0] or p[1] == R8[1])
def przejscie(s):
    LOG.clear()
    tr = list(troll); tr[i8 - 1] = poz0          # punkt przed schodami po skosie od schodów (jak (32483,32297) przy (32482,32296))
    b = zrob(s, tr, okrazenia=1)
    b.idx = i8
    for _ in range(400):
        if s.zmiany or not b.tick(): break
    return b
plik = Path(tempfile.mkdtemp()) / "pietra_start.json"
pietra.PLIK_STARTOW = plik
try:
    # a) start po skosie, Ctrl+klik działa wszędzie: pierwsza próba z pola ortogonalnego, brak kroków po skosie
    s = SwiatS(poz0, gora="use"); przejscie(s)
    sprawdz("8a przejście wyszło", len(s.zmiany) == 1 and s.poz[2] == 8, f"{s.zmiany}")
    sprawdz("8a pierwsza próba z pola ortogonalnego", s.z_pol and ortog(s.z_pol[0]), f"{s.z_pol}")
    sprawdz("8a bez 'po skosie' w logu", not any("po skosie" in l for l in LOG))
    zap = json.loads(plik.read_text()) if plik.exists() else {}
    sprawdz("8a zapamiętane pole startowe", zap.get(f"{R8[0]},{R8[1]},{R8[2]}") == list(s.z_pol[0]), f"{zap}")
    # b) pamięć: zapamiętane pole (nie to, które wybrałby bez pamięci) jest pierwsze
    daleko = [c for c in orto if max(abs(c[0] - poz0[0]), abs(c[1] - poz0[1])) == 1][-1]   # sąsiad poz0, ostatni w kolejności
    plik.write_text(json.dumps({f"{R8[0]},{R8[1]},{R8[2]}": list(daleko)}))
    s = SwiatS(poz0, gora="use"); przejscie(s)
    sprawdz("8b zapamiętane pole użyte jako pierwsze", s.z_pol and s.z_pol[0] == daleko, f"{s.z_pol} oczekiwane {daleko}")
    # c) Ctrl+klik działa tylko z jednego pola: zmieniamy pole ortogonalne (bez kroków po skosie), próby <= 8
    plik.write_text("{}")
    dobre = daleko
    s = SwiatS(poz0, gora="use", dobre=dobre); przejscie(s)
    sprawdz("8c po nieudanym Ctrl+klik przejście z innego pola", len(s.zmiany) == 1 and len(s.z_pol) >= 2 and s.z_pol[-1] == dobre,
            f"{s.z_pol} zmiany={s.zmiany}")
    sprawdz("8c bez serii kroków po skosie", not any("po skosie" in l for l in LOG), f"{[l for l in LOG if 'skosie' in l][:2]}")
    sprawdz("8c limit prób 8 zachowany", not any("próba 9/" in l for l in LOG))
    sprawdz("8c po sukcesie zapamiętane dobre pole", json.loads(plik.read_text()).get(f"{R8[0]},{R8[1]},{R8[2]}") == list(dobre))
finally:
    pietra.PLIK_STARTOW = None

print(f"\nOK={sum(ok)} FAIL={len(ok) - sum(ok)}")
sys.exit(0 if all(ok) else 1)
