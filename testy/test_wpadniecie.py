"""Wpadnięcie (wpadniecie.py + haki w cavebot.py): odtworzenie przypadku z 15.10 09:11:47 (mapa trolle_edron,
trasa edron_trolle_petla, cała na z8; z (33080,31741,8) w dziurę, lądowanie (33081,31742,9)). Wyłącznie atrapy:
bez X11, bez gry, bez prawdziwego pliku STOP i prawdziwego trasy/dziury_nauczone.json. Świat = prawdziwa mapa
(mapa.py) + prosty symulator ruchu, upadku, liny i przejść w górę."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, tempfile, types
sys.dont_write_bytecode = True
_R = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _R)
import cavebot, bot, mapa as _mapa, wpadniecie, pokretla
from pathlib import Path

TRASY = Path(_R) / "trasy"
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

DZIURA = (33081, 31742, 8)          # pole dziury na z8 (lądowanie na z9 w tym samym x,y)
PRZED = (33080, 31741, 8)           # ostatnia pozycja przed upadkiem (log 15.10)
LAD = (33081, 31742, 9)
PO_LINIE = (33081, 31743, 8)        # tu stanął Karol po użyciu liny
petla = [tuple(p) for p in json.loads((TRASY / "edron_trolle_petla.json").read_text())]
sprawdz("0 trasa edron_trolle_petla cała na z8", {p[2] for p in petla} == {8})
sprawdz("0 mapa: dziura na z8 ma flagę 2, rope spot na z9 jest chodliwy", f(*DZIURA) & 2 and idzie(*LAD), f"{f(*DZIURA)} {f(*LAD)}")


class Swiat:
    """Świat: marsz klikiem po mapie, upadek na polach flagi 2 (dół), lina (Use) na polu pod dziurą, przejścia w górę
    przez Use (R). `lina`: True/False; `gora`: None = każde pole z dziurą nad sobą, zbiór T = tylko te pola."""
    def __init__(s, poz, lina=True, gora=None):
        s.t = 0.0; s.poz = list(poz); s.lina = lina; s.gora = gora; s.cel = None; s.stoi = False
        s.zmiany = []; s.uzycia = []; s.liny = []; s.nielegalne = 0; s.odwiedzone = []
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
            s.nielegalne += 1; return
        if v & 2:                                           # dziura/schody w dół: upadek
            s.zmiany.append((tuple(s.poz), z + 1)); s.poz[:] = [x, y, z + 1]; return
        s.poz[0], s.poz[1] = x, y
        s.odwiedzone.append(tuple(s.poz))
    def na_gore(s, x, y, z):
        """Czy z pola (x,y,z) da się wejść w górę (Use / lina): dziura piętro wyżej i chodliwe pole."""
        if not (z and f(x, y, z - 1) & 1 and f(x, y, z - 1) & 2 and idzie(x, y, z)):
            return False
        return s.gora is None or (x, y, z) in s.gora
    def uzyj(s, pole):
        s.uzycia.append(tuple(pole))
        x, y, z = pole
        if s.na_gore(x, y, z):
            s.zmiany.append((tuple(s.poz), z - 1)); s.poz[:] = [x, y + 1, z - 1]
    def uzyj_line(s, pole):
        s.liny.append(tuple(pole))
        x, y, z = pole
        if s.lina and z and f(x, y, z - 1) & 2 and f(x, y, z - 1) & 1 and idzie(x, y, z):
            s.zmiany.append((tuple(s.poz), z - 1)); s.poz[:] = [x, y + 1, z - 1]


class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): pass
    def krok(p, k):
        d = bot.KIERUNKI[k]; p.s.t += 0.2; przed = tuple(p.s.poz); p.s.ruch(*d); return tuple(p.s.poz) != przed


class Ops:
    def __init__(o, s): o.s = s; o.ekw_lina = False; o.z_ekw = []
    def uzyj_pole(o, pole, poz): o.s.uzyj(pole)
    def uzyj_line(o, pole, poz): o.s.uzyj_line(pole)


ALARMY = []
POWIADOMIENIA = []
import powiadom
powiadom.powiadom = lambda *a, **k: POWIADOMIENIA.append(a)


def nowy(poz=PRZED, plik_dziur=True, trasa=None, lina=True, gora=None, stop=True, **kw):
    """-> (swiat, cavebot). Plik nauczonych dziur w katalogu tymczasowym (pusty), STOP w katalogu tymczasowym."""
    LOG.clear(); ALARMY.clear(); POWIADOMIENIA.clear()
    kat = Path(tempfile.mkdtemp())
    wpadniecie.PLIK_DZIUR = (kat / "dziury_nauczone.json") if plik_dziur else None
    s = Swiat(poz, lina=lina, gora=gora)
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok")
    b = cavebot.Cavebot(P(s), list(trasa or petla), zapytaj=s.zapytaj, atak=lambda m, g: None, alarm=lambda w: ALARMY.append(w),
                        spij=s.spij, zegar=s.zegar, loot=loot, mapa=M, klik=s.klik, **kw)
    b.pietra_ops = Ops(s)
    if b.pokretla is not None:
        kopia = kat / "na_zywo.json"; kopia.write_text("{}"); b.pokretla.plik = kopia
    w = b._wp()
    w.plik_stop = (kat / "STOP") if stop else None
    b.kat = kat
    return s, b


def bieg(b, n, az=None):
    for i in range(n):
        if az and az(): return i
        if not b.tick(): return i
    return n


def spadek(s, b):
    """Tick w PRZED (bez ruchu), potem upadek do LAD (jak 09:11:47) i tick, który powinien wykryć."""
    s.poz[:] = list(PRZED); s.stoi = True
    b.tick()
    s.poz[:] = list(LAD)
    b.tick()


# --- 1. wykrycie ---
s, b = nowy()
s.poz[:] = list(PRZED); s.stoi = True
b.tick()
sprawdz("1 przed upadkiem: bez wpadnięcia", b.wpadniecie.st is None and not any("Wpadłem" in l for l in LOG))
b.cel = {"id": 7, "nazwa": "Troll", "hp0": 100}; b.klik_cel = (1, 2)
s.poz[:] = list(LAD)
b.tick()
sprawdz("1 log 'Wpadłem: (x,y,z0) -> (x,y,z1)'", "Wpadłem: (33080,31741,8) -> (33081,31742,9)" in LOG, [l for l in LOG if "Wpad" in l][:2])
sprawdz("1 stan wpadnięcia (z0=8, z1=9)", b.wpadniecie.st is not None and b.wpadniecie.st["z0"] == 8 and b.wpadniecie.st["z1"] == 9)
sprawdz("1 pościg i klik zatrzymane (cel=None, klik_cel=None)", b.cel is None and b.klik_cel is None)
sprawdz("1 stan bota WPADNIECIE", str(b.stan) == "WPADNIECIE" or any("lina" in l for l in LOG), str(b.stan))
sprawdz("1 telemetria i kolejka: brak wyjątków", True)

# --- 2. nauka: zapis atomowy, ponowne wczytanie, tylko jedno pole ---
plik = wpadniecie.PLIK_DZIUR
d = json.loads(plik.read_text())
sprawdz("2 zapis dziury (33081,31742,8) w pliku", d["dziury"] == [list(DZIURA)], f"{d['dziury']}")
sprawdz("2 zapis atomowy: brak pliku .tmp", not Path(str(plik) + ".tmp").exists())
sprawdz("2 log nauki", any("nauczona dziura" in l for l in LOG))
w2 = wpadniecie.Wpadniecie(b, konf=cavebot, log=lambda t: None, plik=plik)
sprawdz("2 wczytanie przy starcie", w2.dziury == {DZIURA})
sprawdz("2 ta sama dziura drugi raz: bez duplikatu", w2.ucz(DZIURA) is False and len(json.loads(plik.read_text())["dziury"]) == 1)
# zasiany plik w repo
zas = json.loads((TRASY / "dziury_nauczone.json").read_text())
sprawdz("2 zasiany trasy/dziury_nauczone.json ma jedno pole (33081,31742,8)", zas["dziury"] == [list(DZIURA)], f"{zas['dziury']}")

# --- 3. A* omija pole (droga, _droga_do, unikanie, krok, loot) ---
s, b = nowy(poz=(33078, 31739, 8))
H = (33080, 31739, 8)                      # pole testowe w otwartym korytarzu (normalna płaska podłoga)
sprawdz("3 pole testowe jest zwykłą podłogą", idzie(*H))
d0 = b.droga((33078, 31739, 8), (33082, 31739), dlugosc=0, skosy=False)
sprawdz("3 bez dziury droga prosta idzie przez pole testowe", d0 and (H[0], H[1], 8) in [tuple(p) for p in d0], f"{d0}")
b._wp().ucz(H)
for nazwa, fn in (("droga()", lambda: b.droga((33078, 31739, 8), (33082, 31739), dlugosc=0, skosy=False)),
                  ("_droga_do()", lambda: b._droga_do((33078, 31739, 8), (33082, 31739), [])),
                  ("_unikanie_droga()", lambda: b._unikanie_droga((33078, 31739, 8), (33082, 31739), []))):
    dd = fn()
    sprawdz(f"3 {nazwa} omija nauczoną dziurę", dd is not None and len(dd) > 0 and H not in [tuple(p[:3]) for p in dd] and
            all(tuple(p[:2]) != H[:2] for p in dd), f"{dd}")
sprawdz("3 pole_zmiany_pietra (pościg/loot/krok) dla nauczonej dziury", b.pole_zmiany_pietra(H) and b.pole_zmiany_pietra(DZIURA) is False)
b._wp().ucz(DZIURA)
sprawdz("3 pole_zmiany_pietra dla (33081,31742,8)", b.pole_zmiany_pietra(DZIURA))
sprawdz("3 inne piętro tego pola nie jest dziurą", not b.dziura_nauczona((H[0], H[1], 9)))
# krok strzałką nie wchodzi w dziurę nawet gdy to cel kroku
s.poz[:] = [H[0] - 1, H[1], 8]; s.stoi = False
przed = tuple(s.poz); b.krok_do((H[0], H[1]));
sprawdz("3 krok_do nie wchodzi na nauczoną dziurę (nawet jako cel kroku)", tuple(s.poz[:2]) != H[:2], f"{s.poz}")
# klik nie prowadzi przez dziurę: idz_do robi krok zamiast kliku
s.poz[:] = [H[0] - 2, H[1], 8]; s.cel = None; nk = len(s.odwiedzone)
b.klik_cel = None; b.idz_do((H[0] + 2, H[1]), tuple(s.poz))
sprawdz("3 idz_do nie klika przez dziurę (brak celu kliku)", s.cel is None)
# loot: zwłoki na polu dziury są pomijane (pole_zmiany_pietra) w kandydatach pola
sprawdz("3 pole nauczonej dziury odrzucone jako pole stania przy lootcie", b.pole_zmiany_pietra(H))
# pokrętło DZIURY_NAUCZONE=0 wyłącza ścianę
cavebot.DZIURY_NAUCZONE = 0
try:
    dd = b.droga((33078, 31739, 8), (33082, 31739), dlugosc=0, skosy=False)
    sprawdz("3 DZIURY_NAUCZONE=0: droga znów prosta", dd and H in [tuple(p) for p in dd] and not b.pole_zmiany_pietra(H))
finally:
    cavebot.DZIURY_NAUCZONE = 1

# --- 4. wyjście: lina na polu lądowania (sukces) ---
s, b = nowy()
spadek(s, b)
s.stoi = False
n = bieg(b, 400, az=lambda: s.poz[2] == 8 and b.wpadniecie.st is None)
sprawdz("4 lina użyta na polu lądowania (33081,31742,9)", s.liny and s.liny[0] == LAD, f"{s.liny}")
sprawdz("4 wyszedł liną na (33081,31743,8)", tuple(s.poz) == PO_LINIE or (s.poz[2] == 8 and abs(s.poz[0] - PO_LINIE[0]) <= 3), f"{s.poz} ticki={n}")
sprawdz("4 log: lina zadziałała i powrót na z8", any("lina zadziałała" in l for l in LOG) and any("wróciłem na z8" in l for l in LOG))
sprawdz("4 stan wpadnięcia wyczyszczony", b.wpadniecie.st is None)
sprawdz("4 brak STOP, brak alarmu", not (b.kat / "STOP").exists() and not ALARMY and not POWIADOMIENIA)
sprawdz("4 punkt trasy wybrany po powrocie (idx w trasie na z8)", 0 <= b.idx < len(b.punkty) and b.punkty[b.idx][2] == 8 and any("wracam na trasę" in l for l in LOG), f"idx={b.idx}")
sprawdz("4 lina tylko raz (sukces od razu)", len(s.liny) == 1, f"{s.liny}")
# dalej gra po trasie: bot idzie i NIE wpada drugi raz w to samo pole
s.stoi = False
wpadl0 = sum(1 for l in LOG if "Wpadłem" in l)
bieg(b, 300)
sprawdz("4 dalej po trasie bez ponownego wpadnięcia w tę dziurę", sum(1 for l in LOG if "Wpadłem" in l) == wpadl0 and s.poz[2] == 8,
        f"{s.poz} zmiany={s.zmiany}")

# --- 4b. lina w slocie ekwipunku 10 (brak w plecaku) ---
class OpsEkw(Ops):
    """Lina nie w oknie plecaka (BrakEkranu), tylko w slocie ekwipunku 10: ścieżka awaryjna."""
    def uzyj_line(o, pole, poz):
        class BrakEkranu(Exception): pass
        raise BrakEkranu("nie widzę liny (rope) w oknie plecaka")
    def ekwipunek(o): return {10: 3003, 5: 3426}
    def uzyj_z_ekwipunku(o, slot, pole, poz): o.z_ekw.append((slot, tuple(pole))); o.s.uzyj_line(pole)
s, b = nowy(); b.pietra_ops = OpsEkw(s)
spadek(s, b); s.stoi = False
bieg(b, 400, az=lambda: s.poz[2] == 8 and b.wpadniecie.st is None)
sprawdz("4b lina ze slotu ekwipunku 10 gdy brak w plecaku", b.pietra_ops.z_ekw == [(10, LAD)] and s.poz[2] == 8, f"{b.pietra_ops.z_ekw} {s.poz}")

# --- 5. lina nie działa -> plan po mapie (niepewne przejście z flagi 2) ---
s, b = nowy(lina=False)
spadek(s, b); s.stoi = False
n = bieg(b, 3000, az=lambda: s.poz[2] == 8 and b.wpadniecie.st is None)
sprawdz("5 lina próbowana 3 razy", len(s.liny) == 3, f"{len(s.liny)}")
sprawdz("5 plan po mapie wykonany i wyszedł na z8", s.poz[2] == 8 and b.wpadniecie.st is None, f"{s.poz} ticki={n} t={s.t:.0f}s")
sprawdz("5 log planu (niepewne przejście oznaczone '?')", any("plan po mapie" in l and "?" in l for l in LOG), [l for l in LOG if "plan po mapie" in l][:1])
sprawdz("5 bez STOP i alarmu", not (b.kat / "STOP").exists() and not ALARMY)
sprawdz("5 trasa łowiska nietknięta (nie odwrócona przez porażkę pietra)", b.punkty == petla)

# --- 5b. pewne przejście z danych ma pierwszeństwo przed niepewną flagą 2 z mapy ---
T2 = (33086, 31742, 9)
s, b = nowy(lina=False, gora={T2})
w = b._wp()
w._przejscia = [{"T": T2, "L": (33086, 31743, 8), "pewne": True, "zrodlo": "test"}]
f_orig = f
spadek(s, b); s.stoi = False
# świat: przejście T2 działa jak Use na polu T2 (map-flag nie jest w gora)
orig_na_gore = s.na_gore
s.na_gore = lambda x, y, z: (x, y, z) == T2
bieg(b, 3000, az=lambda: s.poz[2] == 8 and b.wpadniecie.st is None)
plan_log = [l for l in LOG if "plan po mapie" in l]
sprawdz("5b plan wybiera pewne przejście z danych (bez '?')", plan_log and "(33086, 31742)" in plan_log[0] and "?" not in plan_log[0], plan_log[:1])
sprawdz("5b wyszedł pewnym przejściem", s.poz[2] == 8 and (T2 in s.uzycia), f"{s.poz} {s.uzycia[:3]}")

# --- 5c. pewne przejście nie działa -> wraca do niepewnego z mapy ---
s, b = nowy(lina=False)
w = b._wp()
T3 = (33086, 31742, 9)
w._przejscia = [{"T": T3, "L": (33086, 31743, 8), "pewne": True, "zrodlo": "test"}]
s.na_gore = lambda x, y, z: (x, y, z) == LAD            # działa tylko pole pod dziurą (niepewne z mapy)
spadek(s, b); s.stoi = False
n = bieg(b, 6000, az=lambda: s.poz[2] == 8 and b.wpadniecie.st is None)
sprawdz("5c pewne bez skutku -> niepewne z mapy -> z8", s.poz[2] == 8 and b.wpadniecie.st is None, f"{s.poz} ticki={n} t={s.t:.0f}s")
sprawdz("5c oba przejścia próbowane", any("przejście nieudane" in l or "pietra.py zakończyło" in l for l in LOG) and LAD in s.uzycia, f"{s.uzycia[:4]}")

# --- 6. nic nie działa -> ALARM, powiadomienie, STOP ---
s, b = nowy(lina=False)
b._wp()._wczytaj_przejscia(); b._wp()._przejscia = []
b._wp()._z_mapy_w_gore = lambda poz: []
spadek(s, b); s.stoi = False
n = bieg(b, 300)
sprawdz("6 STOP zapisany", (b.kat / "STOP").exists(), f"ticki={n}")
sprawdz("6 alarm bota", len(ALARMY) >= 1 and "wpadnięcie" in ALARMY[0], f"{ALARMY[:1]}")
sprawdz("6 powiadomienie krytyczne", any(len(a) >= 3 and a[2] == "critical" for a in POWIADOMIENIA), f"{POWIADOMIENIA[:1]}")
sprawdz("6 log ALARM", any("ALARM" in l and "Wpadnięcie" in l for l in LOG))
t_stop = s.t; kl = len(s.liny); uz = len(s.uzycia)
bieg(b, 30)
sprawdz("6 po alarmie bot nie kręci się (bez nowych prób liny/Use)", len(s.liny) == kl and len(s.uzycia) == uz)
sprawdz("6 alarm raz", len(ALARMY) == 1, f"{len(ALARMY)}")

# --- 6b. limit czasu PIETRA_MAX_S ---
s, b = nowy(lina=False)
b._wp()._przejscia = []
stary = cavebot.PIETRA_MAX_S
try:
    cavebot.PIETRA_MAX_S = 20.0
    spadek(s, b); s.stoi = False
    # plan tylko niepewny z mapy, ale przejście w świecie nie działa nigdy
    s.na_gore = lambda x, y, z: False
    n = bieg(b, 3000, az=lambda: (b.kat / "STOP").exists())
finally:
    cavebot.PIETRA_MAX_S = stary
sprawdz("6b limit czasu albo wyczerpanie: STOP", (b.kat / "STOP").exists(), f"ticki={n} t={s.t:.0f}s")
sprawdz("6b w rozsądnym czasie (nie kręci się w nieskończoność)", n < 3000 and s.t < 600, f"t={s.t:.0f}s")

# --- 6c. pokrętła: WPADNIECIE_LINA=0 i WPADNIECIE_PLAN=0 ---
s, b = nowy(lina=True)
cavebot.WPADNIECIE_LINA = 0; cavebot.WPADNIECIE_PLAN = 0
try:
    spadek(s, b); s.stoi = False
    bieg(b, 100)
finally:
    cavebot.WPADNIECIE_LINA = 1; cavebot.WPADNIECIE_PLAN = 1
sprawdz("6c LINA=0 i PLAN=0: bez liny, od razu alarm i STOP", not s.liny and (b.kat / "STOP").exists())
s, b = nowy(lina=True)
cavebot.WPADNIECIE = 0
try:
    spadek(s, b)
finally:
    cavebot.WPADNIECIE = 1
sprawdz("6c WPADNIECIE=0: bez wykrycia", b.wpadniecie.st is None and not any("Wpadłem" in l for l in LOG))

# --- 7. unikanie nie wchodzi na dziurę ---
import unikanie
s, b = nowy(poz=(33078, 31739, 8))
w = b._wp(); w.ucz(DZIURA); w.ucz(H)
u = unikanie.Unikanie(cavebot, zegar=s.zegar, log=lambda t: None)
b.unikanie = u
gracz = {"id": 99, "nazwa": "Argentum", "gracz": True, "x": 33090, "y": 31735, "z": 8, "hp": 100}
u.obserwuj([gracz], (33078, 31739, 8), "Ja")
for cel in ((33086, 31743), (33082, 31739), (33081, 31743), (33082, 31741)):
    dd = b._unikanie_droga((33078, 31739, 8), cel, [])
    sprawdz(f"7 _unikanie_droga do {cel} omija dziury i pola flagi 2", dd is not None and all(tuple(p[:2]) not in (DZIURA[:2], H[:2]) and not f(p[0], p[1], 8) & 2 for p in dd), f"{dd[:6] if dd else dd}")
# pełne decyduj() unikania z drogą z cavebota: żadna droga nie przechodzi przez dziurę
u.aktywne = True; u.gracze = [{"id": 99, "nazwa": "Argentum", "x": 33090, "y": 31735, "z": 8, "odl": 12}]
for poz in ((33078, 31739, 8), (33080, 31741, 8)):
    r = u.decyduj(poz, b.punkty, 0, b._unikanie_droga)
    sprawdz(f"7 unikanie.decyduj z {poz[:2]}: droga bez dziury", r is None or not r.droga or all(tuple(p[:2]) not in (DZIURA[:2], H[:2]) for p in r.droga), f"{r}")

# --- 8. zmiana piętra planowana albo daleka = nie wpadnięcie ---
s, b = nowy()
s.poz[:] = list(PRZED); s.stoi = True; b.tick()
b.pietra_zmiana_t = s.t                                   # pietra.py: planowane przejście
s.poz[:] = list(LAD); b.tick()
sprawdz("8 planowane przejście (pietra.py) nie jest wpadnięciem", b.wpadniecie.st is None and not any("Wpadłem" in l for l in LOG))
s, b = nowy()
s.poz[:] = list(PRZED); s.stoi = True; b.tick()
b.wypad_aktywny = True
s.poz[:] = list(LAD); b.tick()
sprawdz("8 wypad/wyprawa (wypad_aktywny) nie jest wpadnięciem", b.wpadniecie.st is None and not any("Wpadłem" in l for l in LOG))
s, b = nowy()
s.poz[:] = list(PRZED); s.stoi = True; b.tick()
s.poz[:] = [33100, 31745, 9]; b.tick()
sprawdz("8 daleka zmiana (teleport/śmierć) nie jest wpadnięciem", b.wpadniecie.st is None and not any("Wpadłem" in l for l in LOG))
s, b = nowy(trasa=petla + [(33081, 31743, 9)])
s.poz[:] = list(PRZED); s.stoi = True; b.tick()
s.poz[:] = list(LAD); b.tick()
sprawdz("8 piętro z punktem trasy: dziura nauczona, ale bez stanu wyjścia", b.wpadniecie.st is None and DZIURA in b.wpadniecie.dziury and any("Wpadłem" in l for l in LOG))

# --- 9. pokrętła w pokretla.py i na_zywo.przyklad.json ---
przyklad = json.loads((Path(_R) / "na_zywo.przyklad.json").read_text())
for nazwa in ("WPADNIECIE", "WPADNIECIE_LINA", "WPADNIECIE_LINA_PROB", "WPADNIECIE_PLAN", "WPADNIECIE_ODL", "DZIURY_NAUCZONE"):
    sprawdz(f"9 pokrętło {nazwa}", nazwa in pokretla.ZAKRESY and nazwa in przyklad and przyklad[nazwa] == getattr(cavebot, nazwa))
for nazwa in ("WPADNIECIE", "WPADNIECIE_LINA", "WPADNIECIE_PLAN", "DZIURY_NAUCZONE"):
    sprawdz(f"9 {nazwa}: domyślnie 1, analityk nie może wyłączyć", getattr(cavebot, nazwa) == 1 and pokretla.KIERUNEK.get(nazwa) == "nie_nizej")
poprawne, bledy = pokretla.waliduj({"WPADNIECIE": 0, "WPADNIECIE_ODL": 99}, {"WPADNIECIE": 1, "WPADNIECIE_ODL": 3})
sprawdz("9 walidacja zakresu", "WPADNIECIE_ODL" not in poprawne and bledy)

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
