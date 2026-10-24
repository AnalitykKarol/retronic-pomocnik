"""Cache prostokąta mapy (ekran.prostokat_mapy), 23.10 (wydra: start po serwisie, 136x ramka_false). Atrapy i syntetyczny zrzut, bez X11.
a) wykrycie z rozjazdem ("blok mapy X px zamiast Y px") NIE trafia do _cache_mapy; b) poprawne wykrycie dalej jest zapamiętane;
c) cavebot: seria ramka_false bez spadku HP unieważnia cache (ekran.zapomnij_prostokat), z logiem [EKRAN] i limitem co 60 s;
d) aktualny_prostokat nie robi zrzutu na każde wywołanie przy niepewnym wykryciu (krótki TTL), a unieważnienie wymusza nowe wykrycie."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import contextlib, io, sys, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import numpy as np
from PIL import Image
import ekran, cavebot, bot

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

# --- syntetyczny ekran 1175x910 jak wydra: mapa 980x720 na (5,38), panel po prawej, czat pod mapą, tło UI (24,24,28) ---
ROZ = (1175, 910)
MAPA = (5, 38, 985, 758)
def ekran_gry(zaslona_lewa=0, mapa=MAPA):
    """Mapa = szum jak podłoga jaskini; zaslona_lewa > 0: okno UI w kolorze tła UI zasłania tyle px od lewej krawędzi mapy."""
    rng = np.random.default_rng(7)
    a = np.empty((ROZ[1], ROZ[0], 3), np.uint8); a[:] = (24, 24, 28)
    L, T, R, B = mapa
    a[T:B, L:R] = rng.integers(60, 220, (B - T, R - L, 3), dtype=np.uint8)
    a[T:B, L:R, 0] = np.maximum(a[T:B, L:R, 0], 90)            # dominuje czerwień (podłoga), nigdy szarość tła
    a[45:50, 1000:1170] = (200, 40, 40)                           # kawałek panelu bocznego (krótszy niż 1/5 szerokości)
    if zaslona_lewa:
        a[T:B, L:L + zaslona_lewa] = (24, 24, 28)
    return Image.fromarray(a)

def czysto():
    ekran._cache_mapy.clear(); ekran._ostatni_rozmiar = None; ekran._rozmiar_od = 0.0
    for nazwa in ("_niepewny", "_zapomniany"):
        if hasattr(ekran, nazwa): getattr(ekran, nazwa).clear()

def wykryj(obraz):
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        r = ekran.prostokat_mapy(obraz)
    return r, err.getvalue()

# --- b) poprawne wykrycie jest zapamiętane ---
czysto()
dobry = ekran_gry()
r, ostrz = wykryj(dobry)
sprawdz("b1 poprawna mapa: bez ostrzeżenia, prostokąt = mapa (+-2 px)", "UWAGA" not in ostrz and all(abs(x - y) <= 2 for x, y in zip(r, MAPA)), f"{r} {ostrz!r}")
sprawdz("b2 poprawne wykrycie trafia do cache", ROZ in ekran._cache_mapy and ekran._cache_mapy[ROZ] == r)
podmieniony = ekran_gry(zaslona_lewa=161)
r2, _ = wykryj(podmieniony)
sprawdz("b3 z cache bez ponownego liczenia (inny zrzut tego samego rozmiaru daje ten sam wynik)", r2 == r, str(r2))

# --- a) rozjazd: wynik nie trafia do cache ---
czysto()
zly = ekran_gry(zaslona_lewa=161)                  # okno UI zasłania lewą część mapy: L=167, R-L=819 -> "720 zamiast 601" jak w logu 07:50
rz, ostrz = wykryj(zly)
sprawdz("a1 zasłonięta mapa: ostrzeżenie o rozjeździe (jak w logu 07:50: 720 zamiast 601)", "blok mapy 720 px zamiast 601 px" in ostrz, ostrz)
sprawdz("a2 wynik z rozjazdem NIE trafia do _cache_mapy", ROZ not in ekran._cache_mapy, str(ekran._cache_mapy))
r3, ostrz3 = wykryj(dobry)                         # okno zniknęło: następne wywołanie liczy od nowa
sprawdz("a3 następne wywołanie wykrywa od nowa i trafia w całą mapę", all(abs(x - y) <= 2 for x, y in zip(r3, MAPA)) and "UWAGA" not in ostrz3, f"{r3} {ostrz3!r}")
sprawdz("a4 dopiero poprawne wykrycie wchodzi do cache", ekran._cache_mapy.get(ROZ) == r3 and all(abs(x - y) <= 2 for x, y in zip(r3, MAPA)))

# --- d) aktualny_prostokat: TTL niepewnego wyniku i zapomnij_prostokat ---
zrzuty = []
class Zegar: t = 100.0
ekran.zrzut = lambda: (zrzuty.append(1), OBRAZ[0])[1]
ekran._rozmiar_ekranu = lambda e=None: ROZ
_m0 = ekran.time.monotonic
ekran.time = types.SimpleNamespace(monotonic=lambda: Zegar.t, strftime=ekran.time.strftime, time=ekran.time.time, sleep=ekran.time.sleep)
OBRAZ = [zly]
czysto()
with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
    p1 = ekran.aktualny_prostokat(); p2 = ekran.aktualny_prostokat()
sprawdz("d1 niepewny wynik: drugi odczyt w TTL bez nowego zrzutu (zrzutów=%d)" % len(zrzuty), len(zrzuty) == 1 and p1 == p2, str(zrzuty))
sprawdz("d2 niepewny wynik nie siedzi w _cache_mapy", ROZ not in ekran._cache_mapy)
Zegar.t += getattr(ekran, "NIEPEWNY_TTL_S", 3.0) + 0.5
OBRAZ[0] = dobry
with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
    p3 = ekran.aktualny_prostokat()
sprawdz("d3 po TTL nowy zrzut i poprawny prostokąt", len(zrzuty) == 2 and all(abs(x - y) <= 2 for x, y in zip(p3, MAPA)), f"{p3} zrzutów={len(zrzuty)}")
sprawdz("d4 poprawny wynik w cache", ekran._cache_mapy.get(ROZ) == p3)
zap = getattr(ekran, "zapomnij_prostokat", None)
sprawdz("d5 ekran.zapomnij_prostokat istnieje", callable(zap))
if callable(zap):
    OBRAZ[0] = zly
    stare = zap()
    sprawdz("d6 zapomnij_prostokat czyści cache (zwraca poprzedni prostokąt)", ROZ not in ekran._cache_mapy and stare == {ROZ: p3}, str(stare))
    out = io.StringIO()
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(out):
        pz = ekran.aktualny_prostokat()
    sprawdz("d7 po zapomnieniu nowe wykrycie (nowy zrzut)", len(zrzuty) == 3 and pz != p3, f"{pz}")
    Zegar.t += ekran.NIEPEWNY_TTL_S + 0.5
    OBRAZ[0] = ekran_gry(mapa=(183, 102, 992, 695))           # po zasłonie układ ze znaczną różnicą (jak inv3: lewa kolumna UI), pewne wykrycie
    out = io.StringIO()
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(out):
        pn = ekran.aktualny_prostokat()
    sprawdz("d8 log [EKRAN] z poprzednim i nowym prostokątem, gdy pewne wykrycie różni się od zapomnianego",
            "[EKRAN]" in out.getvalue() and str(p3) in out.getvalue() and ekran._cache_mapy.get(ROZ) == pn, out.getvalue())
ekran.time = types.SimpleNamespace(**{k: getattr(__import__("time"), k) for k in ("monotonic", "strftime", "time", "sleep")})

# --- c) cavebot: seria ramka_false bez spadku HP -> zapomnij_prostokat ---
cavebot.REAKCJA = (0.0, 0.0); cavebot.DRUGI_CEL = 0.0; cavebot.ROZRZUT_PROGU = 0.0
cavebot.ODWROCENIE_TRASY = 0.0; cavebot.SCINANIE = (0.0, 2)
cavebot.PAUZA_KROTKA = (0.0, 0.4, 1.5); cavebot.PAUZA_DLUGA = (0.0, 3.0, 8.0)
cavebot.ML_CZAR_AKTYWNY = 0; cavebot.RUNA_AKTYWNA = 0; cavebot.ATAK_INNY_CEL = False; cavebot.STRAZNIK_CEL = 0
LOGI = []
_l0 = cavebot.log
cavebot.log = lambda *a: (LOGI.append(" ".join(map(str, a))), _l0(*a))

WYWOLANIA = []
ekran.zapomnij_prostokat = lambda *a, **k: (WYWOLANIA.append(1), (0, 0, 1, 1))[1]

class Swiat:
    def __init__(s):
        s.t = 0.0; s.poz = [100, 100, 7]; s.flaga = False; s.w_grze = 99; s.klik = []; s.klawisze = []; s.hp = 100; s.id = 1234510
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
            m = {"id": s.id, "nazwa": "Troll", "gracz": False, "x": 101, "y": 100, "z": 7, "hp": s.hp}
            if s.flaga is not None:
                m["atakowany"] = s.flaga
            return {"stwory": [ja, m]}

class P:
    nazwa = "Ja"
    def __init__(p, s): p.s = s
    def pozycja(p): return tuple(p.s.poz)
    def klawisz(p, k): p.s.klawisze.append(k)
    def krok(p, k): return True

def zrob(s):
    loot = types.SimpleNamespace(zbierz=lambda z, g: "ok", zjedz=lambda log=None: [])
    b = cavebot.Cavebot(P(s), [(100 + i, 100, 7) for i in range(1, 11)], zapytaj=s.zapytaj,
                        atak=lambda m, g: s.klik.append(s.t), alarm=lambda w: None, spij=s.spij, zegar=s.zegar,
                        loot=loot, okrazenia=1, jedzenie="F5", czy_atakowany=lambda m, g: m.get("atakowany"))
    b.przerwa_od = float("inf"); b.prog_aktualny = 30.0
    return b

def tick(s, b, dt=0.5):
    s.t += dt; b.tick()

# c1: ramka_false na jednym celu bez spadku HP -> unieważnienie, zanim cel zostanie zignorowany po limicie
s = Swiat(); b = zrob(s); WYWOLANIA.clear(); LOGI.clear()
for _ in range(80):
    tick(s, b)
    if WYWOLANIA:
        break
sprawdz("c1 seria ramka_false -> ekran.zapomnij_prostokat", len(WYWOLANIA) == 1, f"wywołań={len(WYWOLANIA)} klików={len(s.klik)}")
sprawdz("c2 unieważnienie przed zignorowaniem celu (kliki <= ATAK_LIMIT_KLIKOW)", len(s.klik) <= cavebot.ATAK_LIMIT_KLIKOW and 1234510 not in b.ignorowane, f"kliki={len(s.klik)}")
ekr = [l for l in LOGI if l.startswith("[EKRAN]")]
sprawdz("c3 jeden wpis [EKRAN] z powodem", len(ekr) == 1 and "ramka_false" in ekr[0], str(ekr))

# c4: bez pętli - kolejne serie w ciągu 60 s nie unieważniają ponownie, po 60 s tak
t_pierwsze = s.t
while s.t - t_pierwsze < 50.0:                      # cel ignorowany po limicie wraca (zerujemy ignorowanie), kliki dalej bez efektu
    b.ignorowane.clear(); tick(s, b)
sprawdz("c4 w ciągu 60 s od unieważnienia najwyżej jedno (limit), mimo kolejnych serii", len(WYWOLANIA) == 1 and len(s.klik) > 8, f"wywołań={len(WYWOLANIA)} kliki={len(s.klik)}")
s.t += 120.0
for _ in range(80):
    b.ignorowane.clear(); tick(s, b)
    if len(WYWOLANIA) > 1:
        break
sprawdz("c5 po 60 s kolejna seria znów unieważnia", len(WYWOLANIA) == 2, f"wywołań={len(WYWOLANIA)}")

# c6: spadek HP celu zeruje serię (atak działa): bez unieważnienia
s = Swiat(); b = zrob(s); WYWOLANIA.clear(); LOGI.clear()
for i in range(40):
    s.hp = max(5, 100 - 3 * i)                      # HP spada co tick; flaga ramki fałszywa, ale cel traci HP
    tick(s, b)
sprawdz("c6 HP celu spada: brak unieważnienia", not WYWOLANIA, f"wywołań={len(WYWOLANIA)}")

# c7: ramka True (atak trwa) nie unieważnia
s = Swiat(); s.flaga = True; s.w_grze = 1234510; b = zrob(s); WYWOLANIA.clear()
for _ in range(60):
    tick(s, b)
sprawdz("c7 flaga True: brak unieważnienia", not WYWOLANIA)

print("WYNIK", "OK" if all(ok) else "FAIL"); sys.exit(0 if all(ok) else 1)
