"""Wpadnięcie bez STOP (WPADNIECIE_BEZ_STOP=1, dane_tibia/SPEC_wpadniecie_bez_stop_1021.md, pkt 1.1 AUDYTU 21.10).
Odtwarza dwa przypadki z telemetrii 21.10 na prawdziwej mapie (atrapy: bez X11, gry, prawdziwego STOP):
  K  kolanoth 13:37:41: upadek (32369,32212,8) -> (32370,32214,7), jedyne przejście z danych T=(32370,32213,7) (kratka), krok na
     T nic nie daje (postać stoi na T) -> dziś 3x "brak planu" i ALARM+STOP po ~9 s,
  R  Rook (dawajkesh/wydra): upadek (32049,32155,11) -> (32050,32156,10), plan zaczyna od T=(32049,32155,10), po porażce postać
     stoi na T.
Na starym wpadniecie.py (kopia .bak-20261021-bez-stop) sekcje K i R MUSZĄ dać FAIL (ALARM+STOP po kilku sekundach)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import re, sys, tempfile, types
sys.dont_write_bytecode = True
_R = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _R)
import cavebot, bot, mapa as _mapa, wpadniecie
cavebot.WPADNIECIE_DRABINA = 0   # 23.10: atrapa świata zna Use tylko jako drabinę na każdym polu z dziurą nad nim, co zlewa linę z drabiną; te testy mierzą ścieżkę liny (Use/drabinę mierzy test_odchyd_wpadniecie_ucieczka.py)
from pathlib import Path

LOG = []
cavebot.log = lambda *a: LOG.append(" ".join(map(str, a)))
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

M = _mapa.Mapa()
def f(x, y, z): return M.flagi(x, y, z)
def idzie(x, y, z):
    v = f(x, y, z); return bool(v & 1) and not v & 4 and not v & 2


class Swiat:
    """Marsz klikiem po mapie, upadek na polach flagi 2 (chyba że `nie_spada`), a pole `T` zmienia piętro dopiero przy
    `wejscie_nr`-tym wejściu NA nie (0 = nigdy): tak działa kratka/schody, które pierwszy krok zostawia bez skutku."""
    def __init__(s, poz, T=None, T_cel=None, wejscie_nr=0, nie_spada=(), lina_od=0):
        s.t = 0.0; s.poz = list(poz); s.cel = None; s.stoi = False
        s.T = T; s.T_cel = T_cel; s.wejscie_nr = wejscie_nr; s.wejscia = 0; s.nie_spada = set(nie_spada); s.lina_od = lina_od; s.liny = []
        s.zmiany = []; s.wejscia_log = []
    def zegar(s): return s.t
    def klik(s, dx, dy): s.cel = (s.poz[0] + dx, s.poz[1] + dy, s.poz[2])
    def spij(s, d):
        s.t += d
        c = s.cel
        if s.stoi or c is None or d < 0.08 or tuple(s.poz) == c:
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
            return
        if v & 2 and (x, y, z) not in s.nie_spada:
            s.zmiany.append((tuple(s.poz), z + 1)); s.poz[:] = [x, y, z + 1]; return
        s.poz[0], s.poz[1] = x, y
        if s.T is not None and (x, y, z) == s.T:
            s.wejscia += 1; s.wejscia_log.append(round(s.t, 1))
            if s.wejscie_nr and s.wejscia >= s.wejscie_nr:
                s.zmiany.append((tuple(s.poz), s.T_cel[2])); s.poz[:] = list(s.T_cel)


class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): pass
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2; przed = tuple(p.s.poz); p.s.ruch(*d); return tuple(p.s.poz) != przed


class Ops:
    def __init__(o, s): o.s = s
    def uzyj_pole(o, pole, poz): pass
    def uzyj_line(o, pole, poz):
        o.s.liny.append(tuple(pole))
        if o.s.lina_od and o.s.t >= o.s.lina_od and sys._getframe(1).f_code.co_filename.endswith("wpadniecie.py"):   # lina z wpadniecie.py (nie z kroku pietra.py) działa dopiero po czasie świata lina_od (s)
            x, y, z = pole; o.s.zmiany.append((tuple(o.s.poz), z - 1)); o.s.poz[:] = [x, y + 1, z - 1]


ALARMY = []; POWIADOMIENIA = []; TELE = []
import powiadom
powiadom.powiadom = lambda *a, **k: POWIADOMIENIA.append(a)


def nowy(poz, trasa, bez_stop=1, max_s=None, **kw):
    LOG.clear(); ALARMY.clear(); POWIADOMIENIA.clear(); TELE.clear()
    kat = Path(tempfile.mkdtemp())
    wpadniecie.PLIK_DZIUR = kat / "dziury_nauczone.json"
    s = Swiat(poz, **kw)
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
    b = cavebot.Cavebot(P(s), list(trasa), zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: ALARMY.append(w),
                        spij=s.spij, zegar=s.zegar, loot=loot, mapa=M, klik=s.klik)
    b.pietra_ops = Ops(s)
    if b.pokretla is not None:
        kopia = kat / "na_zywo.json"; kopia.write_text("{}"); b.pokretla.plik = kopia
    w = b._wp()
    w.plik_stop = kat / "STOP"
    w._tele = lambda typ, **d: TELE.append((typ, d))
    b.kat = kat
    cavebot.WPADNIECIE_BEZ_STOP = bez_stop
    cavebot.PIETRA_MAX_S = 150.0 if max_s is None else max_s
    return s, b


def upadek(s, b, przed, po):
    s.poz[:] = list(przed); s.stoi = True
    b.tick()
    s.poz[:] = list(po)
    b.tick()
    s.stoi = False


def bieg(b, s, do_s, az=None):
    """Ticki do czasu świata `do_s` (s), aż spełni się `az` albo powstanie STOP."""
    n = 0
    while s.t < do_s and n < 20000:
        n += 1
        if az and az(): break
        if (b.kat / "STOP").exists(): break
        if not b.tick(): break
    return n


def cykle():
    return [d for t, d in TELE if t == "wpadniecie_cykl"]


def plany():
    """[(poz, T, z)] z logów 'plan po mapie z (x, y, z): (tx, ty)zN>zM'."""
    wyn = []
    for l in LOG:
        m = re.search(r"plan po mapie z \((\d+), (\d+), (\d+)\): \((\d+), (\d+)\)z(\d+)", l)
        if m:
            wyn.append(tuple(int(v) for v in m.groups()))
    return wyn


# ======================= K: kolanoth 13:37:41 =======================
K_PRZED = (32369, 32212, 8); K_PO = (32370, 32214, 7); K_T = (32370, 32213, 7); K_L = (32370, 32213, 8)
trasa_k = [(32368, 32214, 8), (32372, 32214, 8), (32369, 32210, 8)]
sprawdz("0 mapa: kratka T i lądowanie L chodliwe, bot spada z z8 na z7", idzie(*K_T) and idzie(*K_L) and idzie(*K_PO) and idzie(*K_PRZED))

# K1: krok na T nie daje nic nigdy -> dziś ALARM po ~9 s; z pokrętłem: cykle, bez STOP
s, b = nowy(K_PRZED, trasa_k, T=K_T, T_cel=K_L, wejscie_nr=0)
upadek(s, b, K_PRZED, K_PO)
sprawdz("K1 wpadnięcie wykryte (z8 -> z7)", b.wpadniecie.st is not None and b.wpadniecie.st["z0"] == 8 and b.wpadniecie.st["z1"] == 7, str(b.wpadniecie.st and b.wpadniecie.st["z1"]))
bieg(b, s, 100.0)
sprawdz("K1 po 100 s: bez STOP", not (b.kat / "STOP").exists(), f"t={s.t:.0f}s")
sprawdz("K1 po 100 s: bez ALARM bota i bez powiadomienia critical", not ALARMY and not any(len(a) >= 3 and a[2] == "critical" for a in POWIADOMIENIA), f"{ALARMY[:1]} {POWIADOMIENIA[:1]}")
sprawdz("K1 po 100 s: wpadnięcie dalej trwa", b.wpadniecie.st is not None)
c = cykle()
sprawdz("K1 telemetria wpadniecie_cykl: co najmniej 2 cykle po 100 s", len(c) >= 2, f"{len(c)}")
sprawdz("K1 log cyklu 'Wpadnięcie: cykl N'", sum(1 for l in LOG if re.search(r"Wpadnięcie: cykl \d+", l)) >= 2, [l for l in LOG if "cykl" in l][:1])
sprawdz("K1 czekanie między cyklami 10-20 s", c and all(10.0 <= d.get("czekaj_s", 0) <= 20.0 for d in c), [d.get("czekaj_s") for d in c])
sprawdz("K1 cykle numerowane 1,2,...", [d.get("cykl") for d in c] == list(range(1, len(c) + 1)), [d.get("cykl") for d in c])
sprawdz("K1 po cyklu 1 postać zeszła z T i weszła na nie ponownie (>=2 wejścia)", s.wejscia >= 2, f"wejścia={s.wejscia_log}")
# nigdy plan z T pod stopami po porażce na tym T: pozycja liczona == T (xy), T już zawiodło
zle_plany = [p for p in plany() if (p[0], p[1]) == (p[3], p[4]) and (p[3], p[4]) == K_T[:2]]
sprawdz("K1 po porażce na T brak planu z T == pozycja postaci", not zle_plany, f"{zle_plany[:2]}")
# dalej: STOP dopiero po budżecie 150 s I >= 3 cyklach
bieg(b, s, 400.0)
stop_t = s.t
sprawdz("K1 STOP wreszcie zapisany (budżet minął, cykle >= 3)", (b.kat / "STOP").exists(), f"t={s.t:.0f}s cykli={len(cykle())}")
al = [d for t, d in TELE if t == "wpadniecie_alarm"]
sprawdz("K1 wpadniecie_alarm dopiero po >= 150 s i >= 3 cyklach", al and al[0]["czas_s"] >= 150.0 and len(cykle()) >= 3, f"{al[:1]} cykli={len(cykle())}")
sprawdz("K1 critical + alarm bota dopiero teraz (1 raz)", len(ALARMY) == 1 and sum(1 for a in POWIADOMIENIA if len(a) >= 3 and a[2] == "critical") == 1)

# K2: za drugim wejściem na T przejście działa (np. wyłączony przycisk kratki) -> wyjście, bez STOP i bez alarmu
s, b = nowy(K_PRZED, trasa_k, T=K_T, T_cel=K_L, wejscie_nr=2)
upadek(s, b, K_PRZED, K_PO)
bieg(b, s, 400.0, az=lambda: s.poz[2] == 8 and b.wpadniecie.st is None)
sprawdz("K2 wyszedł na z8 po ponownym wejściu na T", s.poz[2] == 8 and b.wpadniecie.st is None, f"{s.poz} t={s.t:.0f}s wejścia={s.wejscia_log}")
sprawdz("K2 bez STOP, bez ALARM, bez critical", not (b.kat / "STOP").exists() and not ALARMY and not any(len(a) >= 3 and a[2] == "critical" for a in POWIADOMIENIA))
sprawdz("K2 przeszedł przez co najmniej jeden cykl", len(cykle()) >= 1, f"{len(cykle())}")
sprawdz("K2 po 10-20 s przerwy (nie ponawia natychmiast)", s.t >= 10.0, f"t={s.t:.0f}s")

# K3: pokrętło 0 = jak dziś: ALARM + STOP po kilku sekundach, bez cykli
s, b = nowy(K_PRZED, trasa_k, bez_stop=0, T=K_T, T_cel=K_L, wejscie_nr=0)
upadek(s, b, K_PRZED, K_PO)
bieg(b, s, 100.0)
sprawdz("K3 pokrętło 0: STOP po < 30 s (jak dziś, na żywo ~9 s)", (b.kat / "STOP").exists() and s.t < 30.0, f"t={s.t:.1f}s")
sprawdz("K3 pokrętło 0: ALARM raz, critical, bez wpadniecie_cykl", len(ALARMY) == 1 and any(len(a) >= 3 and a[2] == "critical" for a in POWIADOMIENIA) and not cykle())
sprawdz("K3 pokrętło 0: log ALARM 'lina i plan po mapie nie działają'", any("ALARM" in l and "lina i plan po mapie nie działają" in l for l in LOG))

# K4: twardy bezpiecznik BEZ_STOP_TWARDY_S, gdy budżet bardzo mały: >= 3 cykle też wymagane
s, b = nowy(K_PRZED, trasa_k, max_s=5.0, T=K_T, T_cel=K_L, wejscie_nr=0)
upadek(s, b, K_PRZED, K_PO)
bieg(b, s, 400.0)
sprawdz("K4 budżet 5 s: STOP dopiero po >= 3 cyklach", (b.kat / "STOP").exists() and len(cykle()) >= 3, f"t={s.t:.0f}s cykli={len(cykle())}")

# K5: postać nie może zejść z T (odsun wyłączony): ani jeden plan nie bierze T == pole pod stopami, cykle idą dalej bez STOP
s, b = nowy(K_PRZED, trasa_k, T=K_T, T_cel=K_L, wejscie_nr=0)
b._wp()._odsun = lambda p: False
upadek(s, b, K_PRZED, K_PO)
bieg(b, s, 80.0)
pod_stopami = [p for p in plany() if (p[0], p[1]) == (p[3], p[4])]
sprawdz("K5 bez zejścia z T: żaden plan nie ma T == pole postaci (krok na siebie)", not pod_stopami and not (b.kat / "STOP").exists(), f"{pod_stopami[:2]}")
sprawdz("K5 cykle trwają mimo braku planu", len(cykle()) >= 2, f"{len(cykle())}")

# ======================= R: Rook =======================
R_PRZED = (32049, 32155, 11); R_PO = (32050, 32156, 10); R_DZIURA = (32050, 32155, 10)
trasa_r = [(32046, 32155, 11), (32050, 32155, 11), (32046, 32153, 11)]
sprawdz("0 mapa Rook: (32050,32155,10) to dziura w dół, (32049,32155,10) zwykłe pole", f(*R_DZIURA) & 2 and idzie(32049, 32155, 10))

# R1: prawdziwa dziura działa (jak na żywo): wyjście bez STOP, w rozsądnym czasie (regresja, to samo na starym kodzie)
s, b = nowy(R_PRZED, trasa_r)
upadek(s, b, R_PRZED, R_PO)
bieg(b, s, 200.0, az=lambda: s.poz[2] == 11 and b.wpadniecie.st is None)
sprawdz("R1 dziura działa: wyszedł na z11 bez STOP", s.poz[2] == 11 and not (b.kat / "STOP").exists() and not ALARMY, f"{s.poz} t={s.t:.0f}s")

# R2: żadne przejście nie działa (dziura zasypana): dziś ALARM po kilkunastu sekundach, teraz cykle bez planu z T pod stopami
s, b = nowy(R_PRZED, trasa_r, nie_spada={R_DZIURA})
upadek(s, b, R_PRZED, R_PO)
bieg(b, s, 120.0)
sprawdz("R2 po 120 s: bez STOP i bez alarmu", not (b.kat / "STOP").exists() and not ALARMY, f"t={s.t:.0f}s {s.poz}")
sprawdz("R2 co najmniej 2 cykle", len(cykle()) >= 2, f"{len(cykle())}")
# pozycja postaci po każdej porażce = T, który zawiódł; żaden późniejszy plan nie zaczyna od T o tym samym (x, y) co pozycja liczona
zawiodlo = {tuple(d["pole"][:2]) for t, d in TELE if t == "wpadniecie_plan_porazka"}
pl = plany()
pierwsza_porazka = next((i for i, l in enumerate(LOG) if "przejście nieudane" in l or "zakończyło próby" in l or "limit czasu przejścia" in l), None)
po_porazkach = [p for p in pl[1:] if (p[3], p[4]) in zawiodlo and (p[0], p[1]) == (p[3], p[4])]
sprawdz("R2 żaden plan nie bierze przejścia T == pole, na którym postać stoi, po jego porażce", pierwsza_porazka is not None and not po_porazkach, f"{po_porazkach[:2]} porażki={zawiodlo}")
sprawdz("R2 plany w kolejnych cyklach ponawiają kandydatów (te same T wracają)", len(pl) > len(zawiodlo), f"plany={len(pl)} T={zawiodlo}")
bieg(b, s, 500.0)
sprawdz("R2 STOP dopiero po budżecie i 3 cyklach", (b.kat / "STOP").exists() and len(cykle()) >= 3 and s.t >= 150.0, f"t={s.t:.0f}s cykli={len(cykle())}")

# R3: pokrętło 0 = jak dziś: ALARM+STOP po krótkim czasie
s, b = nowy(R_PRZED, trasa_r, bez_stop=0, nie_spada={R_DZIURA})
upadek(s, b, R_PRZED, R_PO)
bieg(b, s, 120.0)
sprawdz("R3 pokrętło 0: STOP po < 40 s (jak dziś)", (b.kat / "STOP").exists() and s.t < 40.0, f"t={s.t:.1f}s")

# ======================= L: lina działa dopiero w drugim cyklu (Edron, upadek 15.10) =======================
import json
petla = [tuple(q) for q in json.loads((Path(_R) / "trasy" / "edron_trolle_petla.json").read_text())]
E_PRZED = (33080, 31741, 8); E_LAD = (33081, 31742, 9)
cavebot.WPADNIECIE_PLAN = 0                                   # tylko lina: plan po mapie wyłączony
try:
    s, b = nowy(E_PRZED, petla, lina_od=15.0)
    upadek(s, b, E_PRZED, E_LAD)
    bieg(b, s, 300.0, az=lambda: s.poz[2] == 8 and b.wpadniecie.st is None)
    sprawdz("L1 lina działa dopiero po 15 s (po cyklu 1): wyszedł na z8 bez STOP", s.poz[2] == 8 and not (b.kat / "STOP").exists() and not ALARMY, f"{s.poz} liny={len(s.liny)} t={s.t:.0f}s")
    sprawdz("L1 3 próby liny w cyklu 1 i ponowienie po cyklu (licznik prób od zera)", len(cykle()) == 1 and len(s.liny) >= 4, f"cykli={len(cykle())} liny={len(s.liny)}")
    s, b = nowy(E_PRZED, petla, bez_stop=0, lina_od=15.0)
    upadek(s, b, E_PRZED, E_LAD)
    bieg(b, s, 300.0, az=lambda: s.poz[2] == 8 and b.wpadniecie.st is None)
    sprawdz("L2 pokrętło 0: ta sama lina = ALARM+STOP po 3 próbach (jak dziś)", (b.kat / "STOP").exists() and len(ALARMY) == 1 and len(s.liny) == 3, f"{s.poz} liny={len(s.liny)}")
finally:
    cavebot.WPADNIECIE_PLAN = 1

cavebot.WPADNIECIE_BEZ_STOP = 0
print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
