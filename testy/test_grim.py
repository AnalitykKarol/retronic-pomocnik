"""Zrzut ekranu z timeoutem i ponowieniem (13.10, P2d): ekran.grim, ogien.zrzut_ppm, UH bez porażki. Atrapy, bez X11."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import io, subprocess, sys, tempfile, types
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import ekran, ogien
from PIL import Image

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

class Sesja:                       # atrapa pliku gniazda
    def read_text(self): return "wayland-test"
ekran.SESJA = Sesja()
ekran.GRIM_PAUZA = 0.0
bufor = io.BytesIO(); Image.new("RGB", (4, 3), (10, 20, 30)).save(bufor, "PPM")
PPM = bufor.getvalue()

wywolania = []
def atrapa(wyniki):
    def run(cmd, **kw):
        wywolania.append((cmd, kw.get("timeout")))
        w = wyniki.pop(0)
        if isinstance(w, Exception):
            raise w
        return types.SimpleNamespace(stdout=w)
    return run

org = subprocess.run
try:
    # 1. raz timeout, druga próba udana
    wywolania.clear()
    subprocess.run = atrapa([subprocess.TimeoutExpired(["grim"], 2), PPM])
    obraz = ogien.zrzut_ppm("wayland-test")
    sprawdz("1 druga próba udana", obraz.size == (4, 3) and len(wywolania) == 2, str(wywolania))
    sprawdz("1b timeout ppm 2 s", wywolania[0][1] == 2.0)
    # 2. dwa razy: ZrzutNiedostepny (podklasa TimeoutExpired, cmd grim)
    wywolania.clear(); b0 = ekran.GRIM_BLEDY
    subprocess.run = atrapa([subprocess.TimeoutExpired(["grim"], 4), subprocess.TimeoutExpired(["grim"], 4)])
    try:
        ekran.zrzut()
        wyj = None
    except Exception as e:
        wyj = e
    sprawdz("2 ZrzutNiedostepny po 2 próbach", isinstance(wyj, ekran.ZrzutNiedostepny) and len(wywolania) == 2, repr(wyj))
    sprawdz("2b timeout png 4 s", wywolania[0][1] == 4.0)
    sprawdz("2c podklasa TimeoutExpired z cmd grim", isinstance(wyj, subprocess.TimeoutExpired)
            and str(wyj.cmd).startswith("['grim'"))
    sprawdz("2d licznik błędów", ekran.GRIM_BLEDY == b0 + 1)
finally:
    subprocess.run = org

# 3. UH: ZrzutNiedostepny w trakcie = powód brak_zrzutu, bez wyjątku
import uh
class Env:
    stan = {}
    def zegar(self): return 0.0
    def spij(self, d): pass
    def alarm(self, t): pass
    def przerwanie(self): return None
    def log(self, t): pass
    def odczyt(self): raise ekran.ZrzutNiedostepny(["grim"], 4, czas=8.0, proby=2)
p = uh._Przebieg(Env(), 5, None, None)
orig = uh._przebieg
uh._przebieg = lambda p_, tylko_naprawa=False: (_ for _ in ()).throw(ekran.ZrzutNiedostepny(["grim"], 4, czas=8.0, proby=2))
try:
    w = uh.zrob_runa(Env())
finally:
    uh._przebieg = orig
sprawdz("3 UH: przerwane z powodem brak_zrzutu", w["wynik"] == "przerwane" and str(w["powod"]).startswith("brak_zrzutu"), str(w["powod"]))
print("WYNIK", "OK" if all(ok) else "FAIL"); sys.exit(0 if all(ok) else 1)
