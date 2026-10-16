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
    if b.pokretla is not None:         # kopia żywego na_zywo.json z PIETRA_TRYBY_Z_DANYCH=1 (na żywo bywa 0 i zmieniało ścieżkę prób w testach)
        try:
            d = json.loads((Path(_R) / "na_zywo.json").read_text())
        except Exception:
            d = {}
        d["PIETRA_TRYBY_Z_DANYCH"] = getattr(cavebot, "PIETRA_TRYBY_Z_DANYCH", 1)
        kopia = Path(__import__("tempfile").mkdtemp()) / "na_zywo.json"; kopia.write_text(json.dumps(d))
        b.pokretla.plik = kopia
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
# 8 (R1b). R ze skosu bez pre-kroków: dziura w górę (drabina) = Ctrl+klik z pola, na którym stoimy
plik = Path(tempfile.mkdtemp()) / "pietra_start.json"
pietra.PLIK_STARTOW = plik
try:
    s = SwiatS(poz0, gora="use"); przejscie(s)
    sprawdz("8a przejście wyszło", len(s.zmiany) == 1 and s.poz[2] == 8, f"{s.zmiany}")
    sprawdz("8a pierwsza próba R ze skosu (z pola, na którym stoimy)", s.z_pol and s.z_pol[0] == (poz0[0], poz0[1]), f"{s.z_pol} poz0={poz0}")
    sprawdz("8a bez pre-kroków i bez kroków po skosie", not any(("ortogonalnie" in l or "po skosie" in l) for l in LOG),
            f"{[l for l in LOG if 'ortog' in l or 'skosie' in l][:2]}")
    sprawdz("8a próba 1/3 (R, krok, R)", any("próba 1/3 (R" in l for l in LOG), f"{[l for l in LOG if 'próba' in l][:2]}")
    sprawdz("8a R nie zapisuje pola startowego (pamięć tylko dla kroku)", not plik.exists() or json.loads(plik.read_text()) == {})
    # b) zapamiętane pole startowe nie wyciąga postaci z miejsca przed R
    daleko = [c for c in orto if max(abs(c[0] - poz0[0]), abs(c[1] - poz0[1])) == 1][-1]
    plik.write_text(json.dumps({f"{R8[0]},{R8[1]},{R8[2]}": list(daleko)}))
    s = SwiatS(poz0, gora="use"); przejscie(s)
    sprawdz("8b pamięć startu nie przestawia postaci przed R", s.z_pol and s.z_pol[0] == (poz0[0], poz0[1]), f"{s.z_pol}")
    # c) R nie działa nigdzie: tryby R, krok, R; krok dopiero z pola ortogonalnego, bez kroków po skosie i bez lina/E/W/N
    plik.write_text("{}")
    s = SwiatS(poz0, gora="nigdy"); przejscie(s)
    ostatnie = " ".join(LOG)
    sprawdz("8c bez trybów lina/wlasne/E/W/N/use", not any(t in ostatnie for t in ("(lina", "(wlasne", "(E)", "(W)", "(N)", "(use")),
            f"{[l for l in LOG if 'próba' in l][:6]}")
    sprawdz("8c najwyżej 3 próby na pole", not any("próba 4/" in l for l in LOG))
finally:
    pietra.PLIK_STARTOW = None

# 8s. dawne zasady (pokrętła R1b = 0): pierwsza próba z pola ortogonalnego, jak przed 14.10
cavebot.PIETRA_TRYBY_Z_DANYCH = 0; cavebot.PIETRA_PRE_MAX = 0; cavebot.PIETRA_CZEKAJ_KROK_S = 0.0
try:
    plik = Path(tempfile.mkdtemp()) / "pietra_start.json"
    pietra.PLIK_STARTOW = plik
    try:
        # a) start po skosie, Ctrl+klik działa wszędzie: pierwsza próba z pola ortogonalnego, brak kroków po skosie
        s = SwiatS(poz0, gora="use"); przejscie(s)
        sprawdz("8s-a przejście wyszło", len(s.zmiany) == 1 and s.poz[2] == 8, f"{s.zmiany}")
        sprawdz("8s-a pierwsza próba z pola ortogonalnego", s.z_pol and ortog(s.z_pol[0]), f"{s.z_pol}")
        sprawdz("8s-a bez 'po skosie' w logu", not any("po skosie" in l for l in LOG))
        zap = json.loads(plik.read_text()) if plik.exists() else {}
        sprawdz("8s-a zapamiętane pole startowe", zap.get(f"{R8[0]},{R8[1]},{R8[2]}") == list(s.z_pol[0]), f"{zap}")
        # b) pamięć: zapamiętane pole (nie to, które wybrałby bez pamięci) jest pierwsze
        daleko = [c for c in orto if max(abs(c[0] - poz0[0]), abs(c[1] - poz0[1])) == 1][-1]   # sąsiad poz0, ostatni w kolejności
        plik.write_text(json.dumps({f"{R8[0]},{R8[1]},{R8[2]}": list(daleko)}))
        s = SwiatS(poz0, gora="use"); przejscie(s)
        sprawdz("8s-b zapamiętane pole użyte jako pierwsze", s.z_pol and s.z_pol[0] == daleko, f"{s.z_pol} oczekiwane {daleko}")
        # c) Ctrl+klik działa tylko z jednego pola: zmieniamy pole ortogonalne (bez kroków po skosie), próby <= 8
        plik.write_text("{}")
        dobre = daleko
        s = SwiatS(poz0, gora="use", dobre=dobre); przejscie(s)
        sprawdz("8s-c po nieudanym Ctrl+klik przejście z innego pola", len(s.zmiany) == 1 and len(s.z_pol) >= 2 and s.z_pol[-1] == dobre,
                f"{s.z_pol} zmiany={s.zmiany}")
        sprawdz("8s-c bez serii kroków po skosie", not any("po skosie" in l for l in LOG), f"{[l for l in LOG if 'skosie' in l][:2]}")
        sprawdz("8s-c limit prób 8 zachowany", not any("próba 9/" in l for l in LOG))
        sprawdz("8s-c po sukcesie zapamiętane dobre pole", json.loads(plik.read_text()).get(f"{R8[0]},{R8[1]},{R8[2]}") == list(dobre))
    finally:
        pietra.PLIK_STARTOW = None

finally:
    cavebot.PIETRA_TRYBY_Z_DANYCH = 1; cavebot.PIETRA_PRE_MAX = 1; cavebot.PIETRA_CZEKAJ_KROK_S = 1.2

# 9. schody (32498,32270): krok w obie strony jako pierwsza próba (R na tych schodach prawie nigdy nie działa)
SCH = (32498, 32270)
class SwiatSch(Swiat):
    def ruch(s, dx, dy):
        x, y, z = s.poz[0] + dx, s.poz[1] + dy, s.poz[2]
        if (x, y) == SCH and z in (8, 9):
            nz = 8 if z == 9 else 9
            ny = y + 1 if z == 9 else y            # w górę ląduje o pole niżej na ekranie, w dół na tym samym polu
            s.zmiany.append((tuple(s.poz), nz)); s.poz[:] = [x, ny, nz]; s.odwiedzone.add(tuple(s.poz)); return
        super().ruch(dx, dy)
    def uzyj(s, pole):
        s.uzycia.append(tuple(pole))               # Ctrl+klik na schodach nie działa
def schody(poz, a, b, c):
    LOG.clear()
    s = SwiatSch(poz, gora="krok")
    # trasa dopełniona kopiami c: _idz_trasa szuka pozycji postaci w min(10, n) punktach do przodu (cyklicznie), więc przy
    # 3 punktach stojąc na a z idx=1 zaliczyłby a jako osiągnięty (zawinięcie) i kończył okrążenie bez przejścia pięter
    bb = zrob(s, [a, b, c] + [c] * 10, okrazenia=1); bb.idx = 1
    for _ in range(300):
        if s.zmiany or not bb.tick(): break
    return s, bb
kg = pietra.kandydaci(M, (32498, 32272, 9), (32498, 32271, 8), (32498, 32272, 9), 3)[0]
sprawdz("9 schody wykryte (flaga 2 na obu piętrach)", pietra._schody(M, kg["pole"], kg["lad"]) and kg["pole"][:2] == SCH, f"{kg}")
s, bb = schody((32498, 32272, 9), (32498, 32272, 9), (32498, 32271, 8), (32498, 32272, 8))
sprawdz("9a schody w górę: przejście krokiem", len(s.zmiany) == 1 and s.poz[2] == 8, f"{s.zmiany}")
sprawdz("9a pierwsza próba to krok, bez Ctrl+klik", any("próba 1/3 (krok" in l for l in LOG) and not s.uzycia, f"{s.uzycia} {[l for l in LOG if 'próba' in l]}")
s, bb = schody((32500, 32270, 8), (32500, 32270, 8), (32498, 32270, 9), (32498, 32272, 9))
sprawdz("9b schody w dół: przejście krokiem z (32499,32270)", len(s.zmiany) == 1 and s.zmiany[0][0] == (32499, 32270, 8) and not s.uzycia,
        f"{s.zmiany} {s.uzycia}")
sprawdz("9c drabina nie jest typem schody", not pietra._schody(M, R8, (R8[0], R8[1] + 1, R8[2] - 1)))

# 10. łopata: tylko zasypana dziura i z pola sąsiedniego; slot bez zastosowania nie zużywa próby
class OpsL(Ops):
    def __init__(o, s): super().__init__(s); o.kopal = []
    def uzyj_lopate(o, cel, poz): o.kopal.append((tuple(cel), tuple(poz)))
def z_lopata(poz, trasa, idx, **kw):
    LOG.clear()
    s = Swiat(poz, dol="nigdy"); bb = zrob(s, trasa, okrazenia=1); bb.pietra_ops = OpsL(s); bb.idx = idx
    for _ in range(120):
        if not bb.tick(): break
    return s, bb
stary_t7 = cavebot.PIETRA_LOPATA_TYLKO_Z7
try:
    cavebot.PIETRA_LOPATA_TYLKO_Z7 = 0
    # dziura otwarta na z8 (troll i=8): nowe zasady nie kopią, dawne tak
    s, bb = z_lopata(tuple(troll[7]), list(troll), 8)
    sprawdz("10a otwarta dziura: bez łopaty", not bb.pietra_ops.kopal and not any("łopata" in l for l in LOG), f"{bb.pietra_ops.kopal}")
    sprawdz("10a numery prób bez dziur (1/3, 2/3, 3/3)", any("próba 3/3" in l for l in LOG) and not any("próba 4/" in l for l in LOG))
    cavebot.PIETRA_TRYBY_Z_DANYCH = 0
    s, bb = z_lopata(tuple(troll[7]), list(troll), 8)
    sprawdz("10a dawne zasady (pokrętło 0): łopata na otwartej dziurze jak dawniej", bool(bb.pietra_ops.kopal), f"{bb.pietra_ops.kopal}")
    cavebot.PIETRA_TRYBY_Z_DANYCH = 1
finally:
    cavebot.PIETRA_TRYBY_Z_DANYCH = 1; cavebot.PIETRA_LOPATA_TYLKO_Z7 = stary_t7
# zasypana (32493,32259,z7): łopata z pola sąsiedniego, nie z własnego
tr7 = [(32492, 32258, 7), (32493, 32259, 8), (32493, 32260, 8)]
s, bb = z_lopata((32492, 32258, 7), tr7 + [tr7[-1]] * 10, 1)   # dopełnienie: jak w schody() (bez zawinięcia podglądu do punktu 0)
kop = bb.pietra_ops.kopal
sprawdz("10b zasypana dziura: łopata użyta", bool(kop) and kop[0][0] == (32493, 32259, 7), f"{kop}")
sprawdz("10b łopata z pola sąsiedniego, nie z własnego", all(max(abs(c[0] - p[0]), abs(c[1] - p[1])) == 1 for c, p in kop), f"{kop}")
sprawdz("10b lista prób: krok, łopata, krok, łopata, krok", any("próba 1/5 (krok" in l for l in LOG), f"{[l for l in LOG if 'próba' in l][:3]}")

# 11. kandydat "domysł": tylko w promieniu 3 od gracza i z flagą mapy; kotwica na graczu
a11, b11 = (32483, 32297, 9), (32482, 32295, 8)
sprawdz("11a domysł ze ścianą (32482,32294,z9) odrzucony", pietra.kandydaci(M, a11, b11, a11, 3) == [])
sprawdz("11a pokrętło 0: dawny domysł jest", [k["pole"] for k in pietra.kandydaci(M, a11, b11, a11, 0)] == [(32482, 32294, 9)])
sprawdz("11b daleki domysł (144 pola od gracza) odrzucony", pietra.kandydaci(None, (32348, 32224, 8), (32348, 32224, 7), (32492, 32258, 8), 3) == [])
sprawdz("11b domysł blisko gracza bez mapy zostaje", len(pietra.kandydaci(None, (100, 100, 8), (102, 100, 9), (101, 99, 8), 3)) == 1)
sprawdz("11b ten sam domysł z promieniem 0 (dawne) zostaje także daleko", len(pietra.kandydaci(None, (100, 100, 8), (102, 100, 9), (190, 99, 8), 0)) == 1)
# w trasie: brak kandydata = porażka z logiem "wyczerpane", bez błądzenia 26 s po ścianie
s = Swiat((32483, 32297, 9)); tr11 = [(32483, 32297, 9), (32482, 32295, 8), (32482, 32297, 8)]
LOG.clear(); bb = zrob(s, tr11, okrazenia=1); bb.idx = 1
for _ in range(60):
    if not bb.tick(): break
    if s.zmiany: break
sprawdz("11c brak pewnego przejścia: żadna próba w ścianę (32482,32294)", not any("(32482, 32294)" in l and "próba" in l for l in LOG), f"{[l for l in LOG if 'próba' in l][:2]}")

# 12. pole startowe stuknięte 2 razy trafia do pietra_zle.json także przy migotaniu pozycji (krok "udany", postać stoi)
class PM(P):
    def krok(p, k):
        p.s.t += 0.2; return True                           # migotanie: krok zgłasza ruch, pozycja bez zmian
class SwiatM(Swiat):
    def ruch(s, dx, dy):
        if (s.poz[0] + dx, s.poz[1] + dy) in s.blok:
            return                                           # pole startowe zablokowane mimo mapy
        super().ruch(dx, dy)
T12 = (32476, 32272, 8)
def stukaj(pre_max, rund):
    LOG.clear()
    plz = Path(tempfile.mkdtemp()) / "pietra_zle.json"
    pietra.PLIK_ZLYCH = plz
    cavebot.PIETRA_PRE_MAX = pre_max
    try:
        s = SwiatM((32477, 32273, 8), dol="nigdy"); s.blok = {(T12[0] + dx, T12[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}
        tr = list(troll); tr[16] = (32477, 32273, 8)             # punkt przed dziurą (32476,32272), po skosie od niej
        bb = zrob(s, tr, okrazenia=1); bb.postac = PM(s)
        for r in range(rund):
            s.poz[:] = [32477, 32273, 8]; bb.punkty[:] = list(tr); bb.idx = 17; bb.pietra_porazki = 0; 
            if bb.pietra: bb.pietra.st = None
            for _ in range(80):
                if not bb.tick(): break
        return json.loads(plz.read_text()) if plz.exists() else {}, bb
    finally:
        pietra.PLIK_ZLYCH = None; cavebot.PIETRA_PRE_MAX = 1
z1, _ = stukaj(1, 1)
pre = [l.split(" na ")[-1] for l in LOG if "ustawiam się ortogonalnie" in l]
sprawdz("12d najwyżej 1 pre-krok na pole startowe w jednym przejściu", pre and len(pre) == len(set(pre)), f"{pre}")
sprawdz("12a po 1 nieudanym dojściu jeszcze nie do złych", not z1, f"{z1}")
z2, bb12 = stukaj(1, 2)
sprawdz("12b po 2 nieudanych dojściach pole do złych mimo migotania", any(v for v in z2.values()), f"{z2}")
LOG.clear(); z0, _ = stukaj(0, 1)
sprawdz("12c dawne zasady (PRE_MAX=0): pre-kroki w kółko, więcej niż jeden na pole", sum(1 for l in LOG if "ustawiam się ortogonalnie" in l) > 4,
        f"{sum(1 for l in LOG if 'ustawiam się ortogonalnie' in l)}")

# 13. czekanie na zmianę piętra: krok 1,2 s, R 2,0 s; opóźnione przejście wykryte przed kolejną próbą
pp = pietra.Pietra(types.SimpleNamespace(), konf=cavebot)
sprawdz("13a czekanie: krok 1,2 s, R 2,0 s, łopata 0,4 s", (pp._czekaj("krok"), pp._czekaj("R"), pp._czekaj("lopata")) == (1.2, 2.0, 0.4))
cavebot.PIETRA_CZEKAJ_KROK_S = 0.0
sprawdz("13a pokrętło 0 = dawne 2,0 s", pp._czekaj("krok") == 2.0 and pp._odstep(0) == 1.0)
cavebot.PIETRA_CZEKAJ_KROK_S = 1.2
sprawdz("13a odstęp po skróceniu czekania", pp._odstep(0) == 0.2)
class SwiatO(Swiat):
    """Przejście w dół zgłasza się dopiero 1,6 s po kroku (dłużej niż czekanie 1,2 s)."""
    def ruch(s, dx, dy):
        x, y, z = s.poz[0] + dx, s.poz[1] + dy, s.poz[2]
        if f(x, y, z) & 2 and f(x, y, z) & 1 and getattr(s, "op", None) is None:
            s.op = (s.t + 1.6, [x, y, z + 1]); s.poz[:] = [x, y, z]; return
        super().ruch(dx, dy)
class PO(P):
    def pozycja(p):
        o = getattr(p.s, "op", None)
        if o and p.s.t >= o[0]:
            p.s.zmiany.append((tuple(p.s.poz), o[1][2])); p.s.poz[:] = o[1]; p.s.op = None
        return tuple(p.s.poz)
LOG.clear()
s = SwiatO(troll[7]); bb = zrob(s, list(troll), okrazenia=1); bb.postac = PO(s); bb.idx = 8
for _ in range(80):
    if s.zmiany or not bb.tick(): break
sprawdz("13b opóźnione przejście wykryte, bez drugiej próby", len(s.zmiany) == 1 and not any("próba 2/" in l for l in LOG),
        f"{s.zmiany} {[l for l in LOG if 'próba' in l]}")

# 14. zasiane dobre pola startowe: dane domyślne (osobny plik), nigdy nie trafiają do pietra_start.json
dom = json.loads((TRASY / "pietra_starty_domyslne.json").read_text())
oczek = {(32499, 32270), (32477, 32272), (32494, 32290), (32495, 32289), (32482, 32295), (32483, 32297)}
sprawdz("14a plik zawiera 6 pól ze specu", {tuple(v) for k, v in dom.items() if not k.startswith("_")} == oczek, f"{dom}")
pietra.PLIK_STARTOW_DOMYSLNE = TRASY / "pietra_starty_domyslne.json"
plik14 = Path(tempfile.mkdtemp()) / "pietra_start.json"; pietra.PLIK_STARTOW = plik14
try:
    ppp = pietra.Pietra(types.SimpleNamespace(), konf=cavebot)
    sprawdz("14b wczytane jako domyślne", ppp._wczytaj_domyslne().get("32498,32270,8") == [32499, 32270])
    sprawdz("14b pamięć bota (pietra_start) pusta, domyślne osobno", ppp._wczytaj_starty() == {})
    ppp._zapamietaj_start((32498, 32270, 8), (32498, 32269, 8))
    zapis = json.loads(plik14.read_text())
    sprawdz("14c zapis pamięci bota nie zawiera zasianych pól", zapis == {"32498,32270,8": [32498, 32269]}, f"{zapis}")
    cavebot.PIETRA_STARTY_DOMYSLNE = 0
    sprawdz("14d pokrętło 0 = bez zasiewu", pietra.Pietra(types.SimpleNamespace(), konf=cavebot)._wczytaj_domyslne() == {})
finally:
    cavebot.PIETRA_STARTY_DOMYSLNE = 1; pietra.PLIK_STARTOW = None; pietra.PLIK_STARTOW_DOMYSLNE = None

# 15. pokrętła R1b w pokretla.py i w na_zywo.przyklad.json
import pokretla
przyklad = json.loads((Path(_R) / "na_zywo.przyklad.json").read_text())
for nazwa in ("PIETRA_TRYBY_Z_DANYCH", "PIETRA_CZEKAJ_KROK_S", "PIETRA_CZEKAJ_R_S", "PIETRA_DOMYSL_PROMIEN", "PIETRA_PRE_MAX", "PIETRA_STARTY_DOMYSLNE"):
    sprawdz(f"15 pokrętło {nazwa}", nazwa in pokretla.ZAKRESY and nazwa in przyklad and przyklad[nazwa] == getattr(cavebot, nazwa))


# 16. R1b-fix (14.10 18:33): drabina (32483,32285,z9) w górę ze skosu (32484,32284,z9). Pierwszy R bez skutku, strzałki
# Left/Down nie ruszają postaci (odrzucone przez serwer: pozycja chwilę migocze). Dawniej bot stał 150 s w pętli "krok Left
# ... po skosie" i nie wracał do R; teraz: R pierwsze, najwyżej 2 pre-kroki i 2 kroki po skosie, potem R.
class SwiatD(Swiat):
    """Drabina: R działa dopiero od `od_proby`-tego użycia (1 = od razu); kroki strzałką zablokowane (blok=True)."""
    def __init__(s, *a, od_proby=1, blok=True, **kw):
        super().__init__(*a, **kw); s.od = od_proby; s.blok = blok; s.flick = False
    def ruch(s, dx, dy):
        if s.blok and s.poz[2] == 9:
            return
        super().ruch(dx, dy)
    def uzyj(s, pole):
        if len(s.uzycia) + 1 >= s.od:
            super().uzyj(pole)
        else:
            s.uzycia.append(tuple(pole))
class PD(P):
    def krok(p, k):
        p.s.t += 0.2; p.s.flick = p.s.blok; return True        # klient "idzie", serwer cofa: pozycja migocze jeden odczyt
    def pozycja(p):
        if p.s.flick:
            p.s.flick = False
            return (p.s.poz[0] - 1, p.s.poz[1], p.s.poz[2])
        return tuple(p.s.poz)
P16 = (32484, 32284, 9)
def drabina16(od_proby, blok=True, flicker=True, **kw):
    LOG.clear()
    s = SwiatD(P16, od_proby=od_proby, blok=blok, **kw)
    tr = [P16, (32483, 32286, 8)] + [p for p in troll if p[2] == 8][:14]       # długa trasa: start nie leży w podglądzie 10 punktów
    bb = zrob(s, tr, okrazenia=1); bb.idx = 1
    if flicker:
        bb.postac = PD(s)
    for _ in range(300):
        if s.zmiany or not bb.tick(): break
    return s, bb
def kroki16(): return sum(1 for l in LOG if "ustawiam się ortogonalnie" in l), sum(1 for l in LOG if "po skosie" in l and "krok" in l)
s, bb = drabina16(1)
sprawdz("16a drabina ze skosu: pierwsza próba R z bieżącego pola, sukces", len(s.zmiany) == 1 and s.poz[2] == 8 and s.uzycia == [(32483, 32285, 9)] and kroki16() == (0, 0),
        f"{s.zmiany} {s.uzycia} {kroki16()}")
sprawdz("16a log: próba 1/3 (R", any("próba 1/3 (R" in l for l in LOG))
s, bb = drabina16(2)
pre, skos = kroki16()
sprawdz("16b pierwszy R bez skutku, kroki zablokowane (migotanie): potem R i sukces", len(s.zmiany) == 1 and s.poz[2] == 8 and len(s.uzycia) == 2,
        f"{s.zmiany} {s.uzycia} t={s.t:.0f}s")
sprawdz("16b pre-kroki najwyżej 2, kroki po skosie najwyżej 2 na tryb", pre <= 2 and skos <= 2 + 2, f"pre={pre} skos={skos} {[l for l in LOG if 'Przejście' in l][:12]}")
sprawdz("16b bez limitu czasu i bez porażki", not any("NIEUDANE" in l for l in LOG) and bb.pietra_porazki == 0 and s.t < 60, f"t={s.t:.0f}s")
s, bb = drabina16(2, flicker=False)
pre, skos = kroki16()
sprawdz("16c to samo bez migotania pozycji", len(s.zmiany) == 1 and pre <= 2 and skos <= 4 and s.t < 60, f"pre={pre} skos={skos} t={s.t:.0f}s")
s, bb = drabina16(99)
sprawdz("16d nic nie działa: kończy porażką po trzech próbach, nie stoi do limitu czasu", s.t < 100 and not s.zmiany and len(s.uzycia) >= 2 and not any("próba 4/" in l for l in LOG),
        f"t={s.t:.0f}s uzycia={len(s.uzycia)} {[l for l in LOG if 'Przejście' in l][-3:]}")

# 17. typ przejścia z danych (pietra_statystyki_przejsc.json): R działał w górę -> drabina, mimo flag
sprawdz("17a (32483,32285) z9: dane mówią R", pietra.tryb_z_danych((32483, 32285, 9)) == "R", f"{pietra.tryb_z_danych((32483, 32285, 9))}")
sprawdz("17b (32498,32270) z9: dane mówią krok", pietra.tryb_z_danych((32498, 32270, 9)) == "krok", f"{pietra.tryb_z_danych((32498, 32270, 9))}")
sprawdz("17c nieznane schody: brak danych", pietra.tryb_z_danych((1, 2, 9)) is None)
pp17 = pietra.Pietra(types.SimpleNamespace(mapa=M), konf=cavebot)
k17 = {"pole": (32498, 32270, 9), "lad": (32498, 32271, 8)}
sprawdz("17d schody z danych: krok, krok, R", pp17._tryby(k17, {"z0": 9}) == ["krok", "krok", "R"])
k17b = {"pole": (32483, 32285, 9), "lad": (32483, 32286, 8)}
sprawdz("17e drabina z danych: R, krok, R", pp17._tryby(k17b, {"z0": 9}) == ["R", "krok", "R"])
# dane wygrywają z flagami: schody z flagą 2 na obu piętrach, ale w danych R = drabina
orig_t = pietra.tryb_z_danych
pietra.tryb_z_danych = lambda pole: "R"
sprawdz("17f dane R wygrywają z flagami schodów", pp17._tryby(k17, {"z0": 9}) == ["R", "krok", "R"])
pietra.tryb_z_danych = orig_t

print(f"\nOK={sum(ok)} FAIL={len(ok) - sum(ok)}")
sys.exit(0 if all(ok) else 1)
