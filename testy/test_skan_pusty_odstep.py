"""Pętla pełnych skanów przy pustym wyniku (24.10): regiony_stworow=None => _potrzebny_pelny=True => pełny skan co 0,01 s.
Sztuczny zegar i atrapa pamięci (bez gry, bez strażnika, bez wątków): symuluje skaner_krok jak wątek w tle.
Użycie: python3 testy/test_skan_pusty_odstep.py [plik_rdzen.py]   (domyślnie rdzen.py repo; kopia .nowy / .bak da się przetestować jawnie)
Na wersji sprzed zmiany sprawdzenia 'pusty wynik' mają FAIL (RED), reszta (niepusty, błąd odczytu, rytm) przechodzi 1:1."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, struct, types, importlib.util, importlib.machinery
sys.dont_write_bytecode = True
R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, R)
plik = _os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else _os.path.join(R, "rdzen.py")
spec = importlib.util.spec_from_loader("rdzen_pod_test", importlib.machinery.SourceFileLoader("rdzen_pod_test", plik))
rdzen = importlib.util.module_from_spec(spec); sys.modules["rdzen_pod_test"] = rdzen; spec.loader.exec_module(rdzen)
NOWY = hasattr(rdzen.Pamiec, "SKAN_PUSTY_ODSTEP_S")
print(f"rdzeń pod testem: {plik} ({'z odstępem pustego skanu' if NOWY else 'WERSJA SPRZED ZMIANY'})")

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

class Zegar:
    t = 1000.0
    def monotonic(s): return s.t
    def __getattr__(s, n): return getattr(__import__("time"), n)
zegar = Zegar()
rdzen.time = zegar                          # rdzeń widzi sztuczny czas; reszta modułu bez zmian

def wpisz(bufor, idx, ident, nazwa, x, y, z=7, hp=100):
    n = (idx + 5) * 4
    bufor[idx * 4: idx * 4 + 16] = struct.pack("<4f", 1, 1, 1, 1)
    bufor[idx * 4 + 16: idx * 4 + 20] = struct.pack("<I", ident)
    nb = nazwa.encode() + b"\0"
    bufor[n: n + len(nb)] = nb
    bufor[n + 0x10: n + 0x18] = struct.pack("<II", len(nazwa), 15)
    bufor[n + rdzen.POZYCJA_STWORA: n + rdzen.POZYCJA_STWORA + 9] = struct.pack("<IIB", x, y, z)
    bufor[n + rdzen.HP_STWORA] = hp

KOSZT_SKANU = 0.2                           # s symulowanego czasu na jeden skan (jak w reprodukcji 24.10)

class Atrapa(rdzen.Pamiec):
    def __init__(s, regionow=4, blad=False):
        super().__init__()
        s.reg = [(0x100000 * (i + 1), 0x100000 * (i + 1) + 0x10000) for i in range(regionow)]
        s.dane = {r: bytearray(0x10000) for r in s.reg}
        s.mem = object()
        s.blad = blad
        s.skany = []                        # (t_start, pelny)
        s._tryb = None
        s._ostatnie_zapytanie = zegar.t
    def regiony(s): return list(s.reg)
    def czytaj(s, adres, dl):
        if not s._koszt:
            s._koszt = True
            zegar.t += KOSZT_SKANU          # czas skanu płynie wewnątrz skanu (t0 < teraz, jak na żywo)
        if s.blad:
            return b""                      # błąd odczytu (np. ESRCH/EIO)
        for (a, b), d in s.dane.items():
            if a == adres:
                return bytes(d[:dl])
        return b""
    def _skanuj_stwory(s, pelny):
        s.skany.append((zegar.t, pelny))
        s._koszt = False
        wynik = super()._skanuj_stwory(pelny)
        return wynik

def symuluj(p, obiegi=None, sekundy=None, zapytania_co=None, przed=None):
    """Pętla wątku skanera: skaner_krok + sen. Opcjonalnie zapytania bota co `zapytania_co` s i hak `przed(t)`."""
    start, n, nast_zap = zegar.t, 0, zegar.t
    while (obiegi is None or n < obiegi) and (sekundy is None or zegar.t - start < sekundy):
        if przed: przed(zegar.t - start)
        p._ostatnie_zapytanie = zegar.t
        if zapytania_co and zegar.t >= nast_zap:
            p.stwory_info(); nast_zap = zegar.t + zapytania_co
        sen = p.skaner_krok()
        zegar.t += sen
        n += 1
    return n

def pelne(p): return sum(1 for _, pe in p.skany if pe)

# 1. reprodukcja 24.10: pusta pamięć, 12 obiegów
p = Atrapa(); symuluj(p, obiegi=12)
if NOWY:
    sprawdz("pusty wynik: 12 obiegów to <= 3 pełne skany (dawniej 12)", pelne(p) <= 3, pelne(p))
else:
    print(f"INFO przed zmianą: pusty wynik, 12 obiegów = {pelne(p)} pełnych skanów")
    sprawdz("(baza) pętla odtworzona: 12 obiegów = 12 pełnych skanów", pelne(p) == 12, pelne(p))

# 2. pusta pamięć przez 60 s symulowanego czasu: <= ~1 pełny skan na sekundę
p = Atrapa(); symuluj(p, sekundy=60)
pe = [t for t, pel in p.skany if pel]
odstepy = [b - a for a, b in zip(pe, pe[1:])]
sprawdz("pusty wynik 60 s: <= 61 pełnych skanów (1/s)", pelne(p) <= 61, f"{pelne(p)} pełnych")
if NOWY:
    sprawdz("pusty wynik: odstęp między pełnymi skanami >= 1,0 s (początek do początku)", min(odstepy) >= 1.0 - 1e-6, min(odstepy))
    sprawdz("pusty wynik: pełne skany nie wymierają (>= 40 w 60 s: wykrycie wraca w <= ~1,5 s)", pelne(p) >= 40, pelne(p))
    sprawdz("pusty wynik: skany bez regionów tanie i rzadkie (<= 3 wszystkich skanów na sekundę)", len(p.skany) <= 3 * 61, len(p.skany))
    sprawdz("pusty wynik: średni czas szybkiego skanu nie zaniżony skanami bez regionów", p._czas_skanu >= 0.09, p._czas_skanu)

# 3. zapytania bota (stwory_info co 0,1 s) też nie wywołują pełnych skanów częściej niż 1/s
p = Atrapa(); symuluj(p, sekundy=30, zapytania_co=0.1)
sprawdz("pusty wynik + zapytania bota co 0,1 s: <= 31 pełnych skanów w 30 s", pelne(p) <= 31, pelne(p))

# 4. wynik niepusty (gracz w pamięci): rytm skanów 1:1 jak przed zmianą (ślad zmierzony na wersji bazowej tą samą atrapą)
SLAD_BAZY = [(0.0, True), (0.55, False), (1.08, False), (1.59, False), (2.1, False), (2.31, True), (2.8, False), (3.28, False),
             (3.76, False), (4.23, False), (4.69, True), (5.16, False), (5.62, False), (6.08, False), (6.54, False), (7.0, True),
             (7.46, False), (7.91, False), (8.37, False), (8.82, False), (9.27, True), (9.73, False), (10.18, False), (10.63, False),
             (11.08, False), (11.53, True), (11.98, False)]
p = Atrapa(); wpisz(p.dane[p.reg[2]], 100, 0x10000001, "Karol", 32000, 32000)
t0 = zegar.t; symuluj(p, sekundy=12)
slad = [(round(t - t0, 2), pe) for t, pe in p.skany]
sprawdz("niepusty wynik 12 s: ślad skanów (czas, pełny) identyczny z wersją bazową", slad == SLAD_BAZY, slad)
sprawdz("niepusty wynik: znacznik pustego skanu wyczyszczony", getattr(p, "_pusty_pelny_t", None) is None)
p = Atrapa(); wpisz(p.dane[p.reg[2]], 100, 0x10000001, "Karol", 32000, 32000); symuluj(p, sekundy=30)
sprawdz("niepusty wynik 30 s: pełne skany co OKRES_PELNEGO_PUSTO (2 s) jak dotąd", 13 <= pelne(p) <= 16, pelne(p))

# 5. błąd odczytu (puste bufory): zachowanie jak dziś (pełny skan co obieg), bo wynik pusty nie jest wiarygodny
p = Atrapa(blad=True); symuluj(p, obiegi=12)
sprawdz("błąd odczytu: 12 obiegów = 12 pełnych skanów (jak dotąd)", pelne(p) == 12, pelne(p))
sprawdz("błąd odczytu: brak znacznika pustego skanu", getattr(p, "_pusty_pelny_t", None) is None)

# 6. krótki odczyt jednego regionu (niepełny) = też jak dotąd
class Krotki(Atrapa):
    def czytaj(s, adres, dl):
        b = super().czytaj(adres, dl)
        return b[:len(b) // 2] if adres == s.reg[1][0] else b
p = Krotki(); symuluj(p, obiegi=12)
sprawdz("niepełny odczyt regionu: 12 obiegów = 12 pełnych skanów (jak dotąd)", pelne(p) == 12, pelne(p))

# 7. pusto, potem w 10. s pojawia się postać: wykryta po <= ~1,5 s, a potem rytm jak przy niepustym wyniku
p = Atrapa(); moment = {}
def hak(t):
    if t >= 10 and "wpisano" not in moment:
        wpisz(p.dane[p.reg[2]], 100, 0x10000001, "Karol", 32000, 32000); moment["wpisano"] = t
    if "wpisano" in moment and "wykryto" not in moment and p._cache and p._cache[0]:
        moment["wykryto"] = t
symuluj(p, sekundy=20, zapytania_co=0.1, przed=hak)
if NOWY:
    sprawdz("postać pojawia się po pustym okresie: wykryta w <= 1,6 s", "wykryto" in moment and moment["wykryto"] - moment["wpisano"] <= 1.6, moment)
else:
    sprawdz("(baza) postać wykryta szybko", "wykryto" in moment and moment["wykryto"] - moment["wpisano"] <= 0.8, moment)
sprawdz("po wykryciu znacznik pustego skanu wyczyszczony, regiony zapamiętane", getattr(p, "_pusty_pelny_t", None) is None and p.regiony_stworow)

# 8. nowy proces gry (podlacz z innym pid) kasuje znacznik: pierwszy skan znów pełny bez czekania
if NOWY:
    p = Atrapa(); symuluj(p, sekundy=3)
    p.pid = 1; p._cache = None; p.regiony_stworow = None
    skany_przed = len(p.skany); symuluj(p, obiegi=1)
    sprawdz("cache wyzerowany (nowy proces gry): następny skan jest pełny od razu", p.skany[skany_przed][1] is True)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
