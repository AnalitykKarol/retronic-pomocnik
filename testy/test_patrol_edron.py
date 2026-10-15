"""Patrol po spawnach jaskini trolli w Edronie (trasy/miejsca_edron.json, z8): ładowanie pliku, osiągalność miejsc,
runda (każde miejsce raz), omijanie nauczonej dziury, wybór pliku w mozg.rozwiaz_patrol. Wyłącznie atrapy, bez gry."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, types, random
sys.dont_write_bytecode = True
_R = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _R)
import cavebot, bot, mapa as _mapa, wpadniecie
from pathlib import Path

TRASY = Path(_R) / "trasy"
LOG = []
cavebot.log = lambda *a: LOG.append(" ".join(map(str, a)))
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ATAK_TYLKO_PRZY_CELU = False
cavebot.PATROL_POSTOJ = (0.2, 0.4)
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

M = _mapa.Mapa()
MI = json.loads((TRASY / "miejsca_edron.json").read_text())
DZIURY = {tuple(d) for d in json.loads((TRASY / "dziury_nauczone.json").read_text())["dziury"]}
PETLA = [tuple(p) for p in json.loads((TRASY / f"{MI['trasa']}.json").read_text())]
START = tuple(MI["start"])
def idzie(x, y, z):
    v = M.flagi(x, y, z)
    return bool(v & 1) and not v & 4 and not v & 2 and (x, y, z) not in DZIURY


class Swiat:
    def __init__(s, poz):
        s.t = 0.0; s.poz = list(poz); s.nielegalne = 0; s.odwiedzone = []; s.dziura = 0
    def zegar(s): return s.t
    def klik(s, dx, dy):
        s.cel = (s.poz[0] + dx, s.poz[1] + dy, s.poz[2])
    def spij(s, d):
        s.t += d
        c = getattr(s, "cel", None)
        if c is None or d < 0.08 or tuple(s.poz) == c:
            return
        start = tuple(s.poz); skad = {start: None}; q = [start]
        for a in q:
            if a == c or len(skad) > 6000: break
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
            s.ruch(n[0] - s.poz[0], n[1] - s.poz[1])
    def zapytaj(s, z):
        s.t += 0.05
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 195, "max_hp": 195, "mana": 95, "max_mana": 95}}
        if z["cmd"] == "stwory":
            return {"stwory": [{"id": 1, "nazwa": "Ja", "gracz": True, "x": s.poz[0], "y": s.poz[1], "z": s.poz[2], "hp": 100}]}
    def ruch(s, dx, dy):
        x, y, z = s.poz[0] + dx, s.poz[1] + dy, s.poz[2]
        if (x, y, z) in DZIURY:
            s.dziura += 1; return
        if not idzie(x, y, z):
            s.nielegalne += 1; return
        s.poz[0], s.poz[1] = x, y; s.odwiedzone.append((x, y, z))
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
    def uzyj_line(o, pole, poz): pass

for _h in ("_hak_telemetrii", "_hak_pochodni", "_hak_wypadu"):
    setattr(cavebot.Cavebot, _h, lambda self: None)
def zrob(s, punkty, **kw):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
    b = cavebot.Cavebot(P(s), punkty, zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: None, spij=s.spij,
                        zegar=s.zegar, loot=loot, mapa=M, klik=s.klik, **kw)
    b.pietra_ops = Ops(s)
    b.zapis_znanych = False
    w = wpadniecie.Wpadniecie(b, konf=cavebot, log=lambda t: None)
    w.dziury = set(DZIURY)                   # w testach bot nie wczytuje dziury_nauczone.json sam
    b.wpadniecie = w
    return b

cavebot.TRYB_PATROL = 1
cavebot.PATROL_PLIK = "miejsca_edron.json"
cavebot.PATROL_RUNDA = 1
miejsca = MI["miejsca"]
poz = {m["id"]: (m["x"], m["y"], m["z"]) for m in miejsca}

# 1. plik miejsc
sprawdz("1 plik miejsc: graf, bez przejść, wszystko na z8, wagi > 0",
        len(miejsca) >= 6 and MI.get("graf") and not MI["przejscia"] and not MI["laczniki"]
        and all(m["z"] == 8 and m["waga"] > 0 for m in miejsca), f"{len(miejsca)} miejsc")
sprawdz("1 miejsca nie stoją na nauczonej dziurze", all(p not in DZIURY for p in poz.values()))
sprawdz("1 wszystkie miejsca w jednej składowej grafu", len({m["komp"] for m in miejsca}) == 1)

# 2. osiągalność: A* bota (z dziurami) z początku pętli i między parami; żadna droga przez dziurę
s0 = Swiat(START)
b0 = zrob(s0, list(PETLA), okrazenia=999)
b0._patrol_wczytaj()
sprawdz("2 plik wczytany przez cavebot", len(b0.miejsca) == len(miejsca), f"{len(b0.miejsca)}")
bez_drogi, przez_dziure = [], []
for m in b0.miejsca:
    d = b0._patrol_droga(START, m, [])
    if d is None:
        bez_drogi.append(m["nazwa"]); continue
    if any((q[0], q[1], 8) in DZIURY for q in d):
        przez_dziure.append(("START", m["nazwa"]))
    for n in b0.miejsca:
        if n["id"] == m["id"]:
            continue
        d = b0._patrol_droga((m["x"], m["y"], m["z"]), n, [])
        if d is None:
            bez_drogi.append((m["nazwa"], n["nazwa"]))
        elif any((q[0], q[1], 8) in DZIURY for q in d):
            przez_dziure.append((m["nazwa"], n["nazwa"]))
sprawdz("2 wszystkie miejsca osiągalne (start i każda para)", not bez_drogi, f"{bez_drogi[:3]}")
sprawdz("2 żadna droga A* nie przechodzi przez nauczoną dziurę", not przez_dziure, f"{przez_dziure[:3]}")
sprawdz("2 dziura jest w ogóle ścianą dla A* (kontrola testu)", b0.dziura_nauczona((33081, 31742, 8)))
zapisane = [(m["id"], n["id"], n["droga"]) for m in miejsca for n in m["sasiedzi"]]
sprawdz("2 pole sasiedzi: pełny graf, drogi zapisane", len(zapisane) == len(miejsca) * (len(miejsca) - 1))
sprawdz("2 zapisana pętla awaryjna nie wchodzi w dziurę", not any(p in DZIURY for p in PETLA))

# 3. runda: patrol odwiedza każde miejsce raz, potem nowa runda
random.seed(11); LOG.clear()
s = Swiat(START)
b = zrob(s, list(PETLA), okrazenia=999)
b._patrol_wczytaj()
wizyty = []
nz = len(miejsca)
for i in range(60000):
    if not b.tick(): break
    h = list(b.patrol_historia)
    if len(h) > len(wizyty):
        wizyty = h
    if len(wizyty) >= nz + 3: break
pierwsza = wizyty[:nz]
sprawdz("3 patrol aktywny", b._patrol_aktywny(), f"ticki={i} t={s.t:.0f}s wizyt={len(wizyty)}")
sprawdz("3 runda: pierwsze N wizyt = każde miejsce dokładnie raz", len(pierwsza) == nz and set(pierwsza) == set(poz),
        f"{pierwsza}")
sprawdz("3 po rundzie reset (log nowej rundy)", any("runda 1 zakończona" in l for l in LOG), "")
sprawdz("3 bez kroków w dziurę i bez nielegalnych ruchów", s.dziura == 0 and s.nielegalne <= 3, f"dziura={s.dziura} nielegalne={s.nielegalne}")
odw = {i for i, p in poz.items() if any(abs(q[0] - p[0]) <= 2 and abs(q[1] - p[1]) <= 2 for q in s.odwiedzone)}
sprawdz("3 fizycznie dotarto do wszystkich miejsc", odw == set(poz), f"{sorted(odw)}")

# 4. wybór pliku w mozg
import mozg
st = (cavebot.TRYB_PATROL, cavebot.PATROL_PLIK)
try:
    cavebot.PATROL_PLIK = "miejsca.json"
    r = mozg.rozwiaz_patrol("patrol:edron")
    sprawdz("4 patrol:edron -> miejsca_edron.json, trasa awaryjna edron_trolle_petla",
            r and r[0] == "edron_trolle_petla" and cavebot.PATROL_PLIK == "miejsca_edron.json" and cavebot.TRYB_PATROL == 1, f"{r} {cavebot.PATROL_PLIK}")
finally:
    cavebot.TRYB_PATROL, cavebot.PATROL_PLIK = st
mp = json.loads((Path(_R) / "mapy.json").read_text())
e = mp.get("trolle_edron_patrol", {})
sprawdz("4 mapy.json: trolle_edron_patrol (patrol:edron, dojście edron_depo_trolle)",
        e.get("trasa") == "patrol:edron" and e.get("dojscie") == "edron_depo_trolle" and e.get("potwory") == mp["trolle_edron"]["potwory"])
sprawdz("4 pliki tras istnieją", (TRASY / "edron_depo_trolle.json").is_file() and (TRASY / "edron_trolle_petla.json").is_file())

print(f"\nOK={sum(ok)} FAIL={len(ok) - sum(ok)}")
sys.exit(0 if all(ok) else 1)
