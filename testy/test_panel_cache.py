"""panel.py --json: wspólny cache wyniku (24.10) — zgodność pól, jedno liczenie przy równoczesnych wywołaniach, stary i uszkodzony cache,
tryby bez cache, blokada z limitem czasu, linia PROXY=, odczyt cache w okno_api. Wyłącznie atrapy: tymczasowy XDG_RUNTIME_DIR,
RETRONIC_PANEL_CACHE_DIR w tmp, własne RETRONIC_ID. Nic nie dotyka gry, bota ani prawdziwego instancje/_wspolne.
Uruchomienie: python3 -I testy/test_panel_cache.py"""
import os as _os
import tempfile
_TMP = tempfile.mkdtemp(prefix="test_panel_cache_")
_os.environ.update(RETRONIC_TESTY="1", RETRONIC_ID="tstcache", XDG_RUNTIME_DIR=_TMP, RETRONIC_PANEL_CACHE_DIR=_TMP + "/wspolne")
for _z in ("RETRONIC_PANEL_PROC", "RETRONIC_PANEL_GRACZ_S", "RETRONIC_PANEL_GRACZ_BEZ_PAUZY", "RETRONIC_PANEL_CACHE_S", "RETRONIC_PANEL_PROXY"):
    _os.environ.pop(_z, None)
import fcntl, json, shutil, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import instancja
import panel

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

TMP = Path(_TMP)
WSP = TMP / "wspolne"
PLIK = panel.cache_plik()
WYNIK = {"text": "󰐊 RT", "tooltip": "Retronic: działa\nHP 10/20", "class": "dziala", "alt": "dziala", "pozycja": [1, 2, 7], "level": 12,
         "level_procent": 33.5, "podglad": {"port": None, "otwarty": False, "pid": None}, "w_miescie": None}

def reset():
    shutil.rmtree(WSP, ignore_errors=True)

class Licznik:
    def __init__(self, wynik=None):
        self.n, self.wynik = 0, WYNIK if wynik is None else wynik
    def __call__(self):
        self.n += 1
        return json.loads(json.dumps(self.wynik))

def wpis(t, wynik=None, proxy=None, v=1):
    PLIK.parent.mkdir(parents=True, exist_ok=True)
    PLIK.write_text(json.dumps({"v": v, "t": t, "proxy": proxy, "wynik": WYNIK if wynik is None else wynik}))

# ---------------------------------------------------------------- 1. ścieżki
sprawdz("1a plik cache per instancja, w katalogu z RETRONIC_PANEL_CACHE_DIR", PLIK == WSP / "panel_cache_tstcache.json", PLIK)
sprawdz("1b główna instancja ma osobny plik", panel.cache_plik("", WSP) == WSP / "panel_cache__glowna.json" and panel.cache_plik("x", WSP) != panel.cache_plik("y", WSP))
os_env = _os.environ.pop("RETRONIC_PANEL_CACHE_DIR")
sprawdz("1c bez zmiennej: instancje/_wspolne instancji", panel.cache_plik() == Path(instancja.S.wspolne) / "panel_cache_tstcache.json", panel.cache_plik())
_os.environ["RETRONIC_PANEL_CACHE_DIR"] = os_env

# ---------------------------------------------------------------- 2. trafienie i zgodność pól
reset()
l = Licznik()
w1, p1 = panel.wynik_json(licz=l)
w2, p2 = panel.wynik_json(licz=l)
sprawdz("2a pierwsze wywołanie liczy, drugie czyta cache (jedno liczenie)", l.n == 1, l.n)
sprawdz("2b wynik z cache identyczny co policzony (te same pola, wartości i kolejność kluczy)", json.dumps(w1, ensure_ascii=False) == json.dumps(w2, ensure_ascii=False), (w1, w2))
sprawdz("2c bez --proxy: proxy None; nic poza wpisem i blokadą w katalogu (brak śmieci .tmp)", p1 is None and p2 is None
        and sorted(x.name for x in WSP.iterdir()) == ["panel_cache_tstcache.json", "panel_cache_tstcache.json.lock"], sorted(x.name for x in WSP.iterdir()))
sprawdz("2d wpis ma wersję, czas i wynik", json.loads(PLIK.read_text()).keys() == {"v", "t", "proxy", "wynik"})

# ---------------------------------------------------------------- 3. stary / przyszły / uszkodzony
reset(); wpis(time.time() - 10)
l = Licznik(); panel.wynik_json(licz=l)
sprawdz("3a stary wpis (10 s > 2 s): przeliczenie", l.n == 1, l.n)
sprawdz("3b po przeliczeniu wpis jest świeży", panel.cache_odczyt(PLIK) is not None)
reset(); wpis(time.time() + 600)
l = Licznik(); panel.wynik_json(licz=l)
sprawdz("3c wpis z przyszłości (zegar cofnięty): przeliczenie", l.n == 1, l.n)
reset(); wpis(time.time() - 1.0)
l = Licznik(); panel.wynik_json(licz=l)
sprawdz("3d wpis sprzed 1 s (<= 2 s): bez liczenia", l.n == 0, l.n)
reset(); wpis(time.time() - 5)
_os.environ["RETRONIC_PANEL_CACHE_S"] = "10"
l = Licznik(); panel.wynik_json(licz=l)
sprawdz("3e RETRONIC_PANEL_CACHE_S=10 wydłuża ważność", l.n == 0, l.n)
_os.environ["RETRONIC_PANEL_CACHE_S"] = "bzdura"
sprawdz("3f zła wartość CACHE_S: domyślne 2 s", panel.cache_ttl() == 2.0)
_os.environ["RETRONIC_PANEL_CACHE_S"] = "999"
sprawdz("3g CACHE_S poza zakresem (999): domyślne 2 s", panel.cache_ttl() == 2.0)
_os.environ.pop("RETRONIC_PANEL_CACHE_S")
for nazwa, tresc in [("śmieci", "to nie jest json"), ("ucięty", '{"v": 1, "t": 17'), ("pusty plik", ""), ("tablica", "[1,2]"),
                     ("zła wersja", json.dumps({"v": 99, "t": time.time(), "proxy": None, "wynik": WYNIK})),
                     ("wynik nie jest słownikiem", json.dumps({"v": 1, "t": time.time(), "proxy": None, "wynik": [1]})),
                     ("czas jako tekst", json.dumps({"v": 1, "t": "teraz", "proxy": None, "wynik": WYNIK})),
                     ("czas jako bool", json.dumps({"v": 1, "t": True, "proxy": None, "wynik": WYNIK})),
                     ("brak pola wynik", json.dumps({"v": 1, "t": time.time()}))]:
    reset(); PLIK.parent.mkdir(parents=True); PLIK.write_text(tresc)
    l = Licznik(); w, _ = panel.wynik_json(licz=l)
    sprawdz(f"3h uszkodzony cache ({nazwa}): przeliczenie i naprawa wpisu", l.n == 1 and w == WYNIK and panel.cache_odczyt(PLIK) is not None, (l.n, w))
reset(); PLIK.parent.mkdir(parents=True); PLIK.mkdir()           # nazwa pliku zajęta przez katalog: zapis się nie uda
l = Licznik(); w, _ = panel.wynik_json(licz=l)
sprawdz("3i nie da się zapisać cache: wynik i tak zwrócony (zwykłe liczenie), bez wyjątku", l.n == 1 and w == WYNIK, (l.n, w))
shutil.rmtree(WSP, ignore_errors=True)
WSP.parent.mkdir(exist_ok=True)
WSP.write_text("plik zamiast katalogu")                         # katalogu nie da się utworzyć
l = Licznik(); w, _ = panel.wynik_json(licz=l)
sprawdz("3j katalog cache niedostępny: zwykłe liczenie, bez wyjątku", l.n == 1 and w == WYNIK, (l.n, w))
WSP.unlink()

# ---------------------------------------------------------------- 4. tryby bez cache
for zmienna, wartosc in [("RETRONIC_PANEL_GRACZ_S", "2.5"), ("RETRONIC_PANEL_GRACZ_BEZ_PAUZY", "1"), ("RETRONIC_PANEL_PROC", str(TMP / "proc")),
                         ("RETRONIC_PANEL_CACHE_S", "0")]:
    reset(); wpis(time.time())
    _os.environ[zmienna] = wartosc
    l = Licznik(); panel.wynik_json(licz=l); panel.wynik_json(licz=l)
    zapis = json.loads(PLIK.read_text())["t"]
    sprawdz(f"4a {zmienna}={wartosc}: zawsze liczy i nie dotyka cache", l.n == 2 and abs(zapis - time.time()) < 5 and panel.cache_pominiety(), l.n)
    _os.environ.pop(zmienna)
reset(); wpis(time.time()); _os.environ.pop("RETRONIC_PANEL_CACHE_DIR")
sprawdz("4d RETRONIC_TESTY bez RETRONIC_PANEL_CACHE_DIR: bez cache (testy nie piszą do prawdziwego _wspolne)", panel.cache_pominiety())
_os.environ["RETRONIC_PANEL_CACHE_DIR"] = os_env
sprawdz("4e RETRONIC_TESTY z jawnym RETRONIC_PANEL_CACHE_DIR: cache działa (ten test)", not panel.cache_pominiety())
sprawdz("4b BEZ_PAUZY=0 nie wyłącza cache", not (lambda: (_os.environ.update(RETRONIC_PANEL_GRACZ_BEZ_PAUZY="0"), panel.cache_pominiety())[1])())
_os.environ.pop("RETRONIC_PANEL_GRACZ_BEZ_PAUZY")
reset()
_os.environ["RETRONIC_PANEL_PROC"] = str(TMP / "proc")
l = Licznik(); panel.wynik_json(licz=l)
sprawdz("4c tryb bez cache nie zakłada pliku cache", not PLIK.exists())
_os.environ.pop("RETRONIC_PANEL_PROC")

# ---------------------------------------------------------------- 5. równoczesne wywołania: jeden liczy, reszta czyta
reset()
LICZ_PLIK = TMP / "liczenia.log"
RODZIC = f'''
import json, os, sys, time
sys.path.insert(0, {str(KAT)!r}); sys.dont_write_bytecode = True
import panel
def licz():
    open({str(LICZ_PLIK)!r}, "a").write(str(os.getpid()) + "\\n")
    time.sleep(0.4)
    return {WYNIK!r}
w, p = panel.wynik_json(licz=licz)
print(json.dumps(w, ensure_ascii=False))
'''
t0 = time.time()
procs = [subprocess.Popen([sys.executable, "-I", "-c", RODZIC], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dict(_os.environ)) for _ in range(8)]
wyj = [p.communicate(timeout=30) for p in procs]
czas = time.time() - t0
liczenia = LICZ_PLIK.read_text().split() if LICZ_PLIK.exists() else []
sprawdz("5a osiem równoczesnych wywołań: liczył jeden proces", len(liczenia) == 1, liczenia)
sprawdz("5b wszystkie dostały ten sam, poprawny wynik", all(o[0].decode().strip() == json.dumps(WYNIK, ensure_ascii=False) for o in wyj) and all(p.returncode == 0 for p in procs),
        [o[1].decode()[-200:] for o in wyj][:1])
sprawdz("5c reszta czekała na wynik jednego (nie na 8 liczeń po 0,4 s)", czas < 3.0, czas)
procs = [subprocess.Popen([sys.executable, "-I", "-c", RODZIC], stdout=subprocess.PIPE, env=dict(_os.environ)) for _ in range(4)]
for p in procs: p.communicate(timeout=30)
sprawdz("5d kolejna fala w oknie ważności nie liczy wcale", len(LICZ_PLIK.read_text().split()) == 1, LICZ_PLIK.read_text())

# ---------------------------------------------------------------- 6. blokada z limitem czasu
reset(); PLIK.parent.mkdir(parents=True)
fd = _os.open(str(PLIK) + ".lock", _os.O_RDWR | _os.O_CREAT)
fcntl.flock(fd, fcntl.LOCK_EX)
panel.CACHE_CZEKANIE_S = 0.3
l = Licznik(); t0 = time.time(); w, _ = panel.wynik_json(licz=l); dt = time.time() - t0
sprawdz("6a cudza blokada trwa dłużej niż limit: po ~0,3 s liczy sam (bez zawieszenia)", l.n == 1 and w == WYNIK and 0.25 <= dt < 1.5, (l.n, dt))
sprawdz("6b i zapisuje wynik", panel.cache_odczyt(PLIK) is not None)
fcntl.flock(fd, fcntl.LOCK_UN); _os.close(fd)
panel.CACHE_CZEKANIE_S = 1.0
reset()
def zepsute():
    raise RuntimeError("awaria liczenia")
try:
    panel.wynik_json(licz=zepsute); wyjatek = False
except RuntimeError:
    wyjatek = True
l = Licznik(); t0 = time.time(); panel.wynik_json(licz=l)
sprawdz("6c awaria liczenia: wyjątek jak dotąd, nic nie zapisane, blokada zwolniona (następne wywołanie liczy od razu)", wyjatek and l.n == 1 and time.time() - t0 < 0.5, (wyjatek, l.n))

# ---------------------------------------------------------------- 7. linia PROXY
reset(); wpis(time.time(), proxy=None)
l = Licznik(); w, p = panel.wynik_json(proxy=True, licz=l)
sprawdz("7a wpis bez stanu proxy, a proxy potrzebne: przeliczenie, proxy 0/1", l.n == 1 and p in (0, 1), (l.n, p))
l = Licznik(); w, p2 = panel.wynik_json(proxy=True, licz=l)
sprawdz("7b kolejne z proxy: z cache, ten sam stan proxy", l.n == 0 and p2 == p, (l.n, p2))
reset(); wpis(time.time(), proxy=1)
l = Licznik(); w, p = panel.wynik_json(licz=l)
sprawdz("7c bez proxy w zapytaniu: wpis z proxy też dobry, proxy w odpowiedzi tylko gdy proszono", l.n == 0 and p is None)
PROC = TMP / "proc"
def proces(pid, argv, id_, comm="bash"):
    d = PROC / str(pid); d.mkdir(parents=True)
    (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    (d / "comm").write_text(comm + "\n")
    (d / "environ").write_bytes(b"HOME=/x\0" + (f"RETRONIC_ID={id_}\0".encode() if id_ is not None else b""))
shutil.rmtree(PROC, ignore_errors=True); PROC.mkdir()
sprawdz("7d brak procesów: proxy wyłączone", panel.proxy_dziala(str(PROC)) is False)
proces(100, ["/bin/bash", "/h/pomocnik/siec_proxy.sh", "python3", "-I", "straznik.py"], "inna")
proces(101, ["/usr/bin/tail", "-f", "/h/pomocnik/siec_proxy.sh"], "tstcache", comm="tail")
proces(102, ["/bin/bash", "/h/pomocnik/uruchom.sh", "siec_proxy.sh"], "tstcache")
sprawdz("7e siec_proxy.sh cudzej instancji, obcy proces i skrypt z tą nazwą jako argument nie liczą się", panel.proxy_dziala(str(PROC)) is False)
proces(103, ["/bin/bash", "/h/pomocnik/siec_proxy.sh", "python3", "-I", "straznik.py", "wine", "RetronicGL.exe"], "tstcache")
sprawdz("7f żywy siec_proxy.sh tej instancji (jak pgrep + RETRONIC_ID): proxy włączone", panel.proxy_dziala(str(PROC)) is True)

# ---------------------------------------------------------------- 8. panel.py --json jako proces (zgodność z liczeniem na świeżo)
reset()
def uruchom(proxy=False, **dodatek):
    env = dict(_os.environ, **dodatek)
    if proxy:
        env["RETRONIC_PANEL_PROXY"] = "1"
    return subprocess.run([sys.executable, "-I", str(KAT / "panel.py"), "--json"], capture_output=True, env=env, timeout=60, cwd=str(KAT))
a = uruchom()
sprawdz("8a panel.py --json (bez cache): jedna linia JSON, kod 0", a.returncode == 0 and len(a.stdout.decode().splitlines()) == 1, a.stderr.decode()[-300:])
b = uruchom()
sprawdz("8b drugie wywołanie (z cache): bajt w bajt ten sam wynik", b.stdout == a.stdout and PLIK.exists(), (a.stdout[:80], b.stdout[:80]))
swieze = uruchom(RETRONIC_PANEL_CACHE_S="0")
da, ds = json.loads(a.stdout), json.loads(swieze.stdout)
sprawdz("8c cache vs liczenie na świeżo: te same klucze i wartości (pola panelu nietknięte)", list(da) == list(ds) and da == ds, (list(da), list(ds)))
sprawdz("8d kontrakt: dotychczasowe i dodane pola obecne", all(k in da for k in ("text", "tooltip", "class", "alt", "pozycja", "w_miescie", "w_depo", "plan_depo_dostepny",
        "wroc_oczekuje", "wroc_w_marszu", "serwis_dziala", "serwis_krok", "serwis_ukonczone", "serwis_tryb", "serwis_wynik", "serwis_komunikat", "serwis_wiek_s",
        "wroc_refill", "wroc_refill_komunikat", "level", "level_procent", "podglad")), list(da))
reset()
c = uruchom(proxy=True)
linie = c.stdout.decode().splitlines()
sprawdz("8e RETRONIC_PANEL_PROXY=1: JSON + linia PROXY=0|1", len(linie) == 2 and linie[1] in ("PROXY=0", "PROXY=1") and json.loads(linie[0]) == ds, linie[1:])
d = uruchom(proxy=True)
sprawdz("8f to samo z cache", d.stdout == c.stdout)
e = uruchom()
sprawdz("8g bez zmiennej proxy: jak dawniej, jedna linia", len(e.stdout.decode().splitlines()) == 1 and json.loads(e.stdout) == ds, (e.stdout[:300], e.stderr[-300:]))
sprawdz("8h nic nie trafiło do prawdziwego instancje/_wspolne", not (Path(instancja.S.wspolne) / "panel_cache_tstcache.json").exists())

# ---------------------------------------------------------------- 9. okno_api: odczyt cache bez procesu
_os.environ.pop("RETRONIC_ID", None)
sys.path.insert(0, str(KAT))
import okno_api
reset()
sprawdz("9a brak cache: None (okno uruchomi panel.py)", okno_api.panel_z_cache("tstcache") is None)
wpis(time.time())
sprawdz("9b świeży cache: wynik bez procesu", okno_api.panel_z_cache("tstcache") == WYNIK and okno_api.odczyt_panelu("tstcache") == WYNIK)
wpis(time.time() - 10)
sprawdz("9c stary cache: None", okno_api.panel_z_cache("tstcache") is None)
wpis(time.time())
_os.environ["RETRONIC_PANEL_GRACZ_S"] = "2.5"
sprawdz("9d tryb nadzoru (GRACZ_S): okno nie używa cache", okno_api.panel_z_cache("tstcache") is None)
_os.environ.pop("RETRONIC_PANEL_GRACZ_S")
PLIK.write_text("{")
sprawdz("9e uszkodzony cache: None", okno_api.panel_z_cache("tstcache") is None)
sprawdz("9f inna instancja ma osobny cache", (wpis(time.time()), okno_api.panel_z_cache("inna"))[1] is None)

shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
