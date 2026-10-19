"""dopasuj_okno.py (SPEC okno gry 15.10): rozmiar docelowy, hyprctl, debounce, RFB SetDesktopSize na atrapie serwera,
ekran._zauwaz_rozmiar, a opcjonalnie wayvnc w headless sway (pomijane bez sway/wayvnc)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, shutil, socket, struct, subprocess, sys, tempfile, threading, time
sys.dont_write_bytecode = True
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import dopasuj_okno as d

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

# --- 1. rozmiar docelowy i próg ---
sprawdz("1a min 800x600", d.ogranicz(500, 300) == (800, 600))
sprawdz("1b parzyste w dół", d.ogranicz(941, 1031) == (940, 1030), str(d.ogranicz(941, 1031)))
sprawdz("1c bez zmian dla poprawnych", d.ogranicz(1175, 910) == (1175 - 1, 910) and d.ogranicz(1176, 910) == (1176, 910))
sprawdz("1d tylko jeden wymiar poniżej minimum", d.ogranicz(1000, 400) == (1000, 600))
sprawdz("1e próg 8 px", not d.roznia_sie((1000, 900), (1007, 907)) and d.roznia_sie((1000, 900), (1008, 900)) and d.roznia_sie((1000, 900), (1000, 892)))
sprawdz("1f env: domyślnie włączone, 0 wyłącza", d.wlaczone({}) and d.wlaczone({"RETRONIC_DOPASUJ_OKNO": "1"}) and not d.wlaczone({"RETRONIC_DOPASUJ_OKNO": "0"}))

# --- 2. hyprctl ---
KL = [{"class": "com.mitchellh.ghostty", "title": "x", "pid": 10, "size": [941, 508]},
      {"class": "Vncviewer", "title": "TigerVNC: 127.0.0.1::5903", "pid": 21, "size": [700, 500]},
      {"class": "Vncviewer", "title": "TigerVNC: 127.0.0.1::5901", "pid": 22, "size": [941, 1030]}]
sprawdz("2a po pid", d.rozmiar_okna(KL, pid=22, port=5903) == (941, 1030))
sprawdz("2b zapas: klasa + port w tytule", d.rozmiar_okna(KL, pid=999, port=5903) == (700, 500))
sprawdz("2c brak okna", d.rozmiar_okna(KL, pid=999, port=5999) is None and d.rozmiar_okna([], pid=1, port=1) is None)
sprawdz("2d śmieci w size", d.rozmiar_okna([{"class": "Vncviewer", "pid": 5, "size": "x"}], pid=5) is None)
atrapa_ok = lambda cmd, **kw: type("R", (), {"stdout": json.dumps(KL)})()
def atrapa_brak(cmd, **kw): raise FileNotFoundError("hyprctl")
sprawdz("2e hyprctl_klienci: JSON", d.hyprctl_klienci(atrapa_ok) == KL)
sprawdz("2f hyprctl_klienci: brak programu", d.hyprctl_klienci(atrapa_brak) == [])
sprawdz("2g hyprctl_klienci: zły JSON", d.hyprctl_klienci(lambda cmd, **kw: type("R", (), {"stdout": "nie json"})()) == [])

# --- 3. bajty SetDesktopSize ---
w, h = 1000, 950
oczek = struct.pack('>BxHHBx', 251, w, h, 1) + struct.pack('>IHHHHI', 0, 0, 0, w, h, 0)
sprawdz("3a komunikat 251 = sprawdzona sekwencja", d.komunikat_set_desktop_size(w, h) == oczek and len(oczek) == 24 and oczek[0] == 251)

# --- 4. atrapa serwera RFB w procesie ---
class SerwerRFB(threading.Thread):
    """Mówi RFB 3.8, security None; zapisuje to, co klient wysłał po ServerInit; na 251 odpowiada ExtendedDesktopSize."""
    def __init__(s, szer=800, wys=910, security=(1,), odpowiada=True, kod=0):
        super().__init__(daemon=True)
        s.sock = socket.socket(); s.sock.bind(("127.0.0.1", 0)); s.sock.listen(5)
        s.port = s.sock.getsockname()[1]
        s.szer, s.wys, s.security, s.odpowiada, s.kod = szer, wys, security, odpowiada, kod
        s.odebrane, s.polaczen, s.client_init = [], 0, []
    def _czytaj(s, c, n):
        b = b""
        while len(b) < n:
            k = c.recv(n - len(b))
            if not k: raise ConnectionError
            b += k
        return b
    def run(s):
        while True:
            try: c, _ = s.sock.accept()
            except OSError: return
            s.polaczen += 1
            try: s._obsluz(c)
            except (OSError, ConnectionError): pass
            finally: c.close()
    def _obsluz(s, c):
        c.settimeout(3)
        c.sendall(b"RFB 003.008\n"); s._czytaj(c, 12)
        c.sendall(bytes([len(s.security)]) + bytes(s.security))
        if 1 not in s.security: return
        s._czytaj(c, 1); c.sendall(struct.pack(">I", 0))
        s.client_init.append(s._czytaj(c, 1))
        c.sendall(struct.pack(">HH", s.szer, s.wys) + bytes(16) + struct.pack(">I", 4) + b"test")
        # SetEncodings (8 bajtów dla jednego kodowania), potem opcjonalnie SetDesktopSize (24 bajty)
        try:
            se = s._czytaj(c, 8); s.odebrane.append(se)
            if se[0] != 2: return
            m = s._czytaj(c, 24); s.odebrane.append(m)
        except socket.timeout:
            return
        except ConnectionError:
            return
        _, w, h, _ = struct.unpack(">BxHHBx", m[:8])
        if s.kod == 0:
            s.szer, s.wys = w, h
        if s.odpowiada:
            rekord = struct.pack(">HHHHi", 1, s.kod, s.szer, s.wys, d.ENC_EXTENDED_DESKTOP_SIZE) + bytes([1, 0, 0, 0]) \
                + struct.pack(">IHHHHI", 0, 0, 0, s.szer, s.wys, 0)
            c.sendall(struct.pack(">BxH", 0, 1) + rekord)
    def zamknij(s):
        s.sock.close()

srv = SerwerRFB(800, 910); srv.start()
sprawdz("4a odczytaj_rozmiar z ServerInit", d.odczytaj_rozmiar(srv.port) == (800, 910))
sprawdz("4b ClientInit shared=1", srv.client_init and srv.client_init[0] == b"\x01")
kod, po, przed = d.ustaw_rozmiar(srv.port, 1000, 950)
time.sleep(0.1)
sprawdz("4c ustaw_rozmiar: wynik 0, nowy rozmiar, stary rozmiar", (kod, po, przed) == (0, (1000, 950), (800, 910)), str((kod, po, przed)))
sprawdz("4d serwer dostał SetEncodings(-308) + dokładnie bajty 251",
        len(srv.odebrane) >= 2 and srv.odebrane[-2] == struct.pack(">BxHi", 2, 1, -308) and srv.odebrane[-1] == oczek,
        repr(srv.odebrane[-1:]))
srv.zamknij()

srv2 = SerwerRFB(800, 910, odpowiada=False); srv2.start()
sprawdz("4e brak odpowiedzi: kod None, bez wyjątku", d.ustaw_rozmiar(srv2.port, 1000, 950)[0] is None)
srv2.zamknij()
srv3 = SerwerRFB(800, 910, kod=3); srv3.start()
k3 = d.ustaw_rozmiar(srv3.port, 1000, 950)
sprawdz("4f odmowa serwera (kod 3): rozmiar bez zmiany", k3[0] == 3 and k3[1] == (800, 910), str(k3))
srv3.zamknij()
srv4 = SerwerRFB(800, 910, security=(2,)); srv4.start()
try:
    d.odczytaj_rozmiar(srv4.port); sprawdz("4g security bez None: błąd", False)
except ConnectionError as e:
    sprawdz("4g security bez None: błąd połączenia", "security None" in str(e), str(e))
srv4.zamknij()

# --- 5. Dopasowywacz: debounce, próg, powtórki ---
class Swiat:
    def __init__(s):
        s.t = 0.0; s.okno = (1000, 910); s.wyjscie = (1000, 910); s.wyslane = []; s.odczyty = 0; s.logi = []
        s.ogranicza_do = None; s.pada = False
    def zegar(s): return s.t
    def czytaj_okno(s): return s.okno
    def odczytaj(s): s.odczyty += 1; return s.wyjscie
    def ustaw(s, w, h):
        if s.pada: raise ConnectionError("pada")
        s.wyslane.append((w, h)); przed = s.wyjscie
        s.wyjscie = s.ogranicza_do or (w, h)
        return 0, s.wyjscie, przed
    def log(s, t): s.logi.append(t)
def nowy(sw): return d.Dopasowywacz(sw.czytaj_okno, sw.odczytaj, sw.ustaw, sw.zegar, sw.log)
def tiki(dp, sw, n, krok=1.0):
    for _ in range(n): dp.tik(); sw.t += krok

sw = Swiat(); dp = nowy(sw)
tiki(dp, sw, 5)
sprawdz("5a okno = wyjście: nic nie wysyła", sw.wyslane == [] and sw.odczyty == 1)
sw.okno = (1004, 914)   # różnica < 8
tiki(dp, sw, 5)
sprawdz("5b różnica < 8 px: nic nie wysyła", sw.wyslane == [])
sw.okno = (941, 1030)
dp.tik(); sw.t += 0.5
sprawdz("5c pierwszy odczyt nowego rozmiaru: jeszcze nie wysyła", sw.wyslane == [])
dp.tik(); sw.t += 0.4   # 0.5 s od pierwszego widzenia
sprawdz("5d po 0.5 s nadal czeka (debounce 1 s)", sw.wyslane == [])
dp.tik(); sw.t += 1.0   # 0.9 s
sprawdz("5e po 0.9 s nadal czeka", sw.wyslane == [])
dp.tik(); sw.t += 1.0   # 1.4 s
sprawdz("5f po >= 1 s wysyła parzysty rozmiar", sw.wyslane == [(940, 1030)], str(sw.wyslane))
tiki(dp, sw, 5)
sprawdz("5g potem nie powtarza", sw.wyslane == [(940, 1030)])
sprawdz("5h log ma okno i wynik", any("941x1030" in l and "940x1030" in l for l in sw.logi), str(sw.logi))

sw = Swiat(); dp = nowy(sw)
dp.tik(); sw.t += 1.0
for okno in [(1100, 910), (1120, 910), (1130, 910)]:   # przeciąganie ramki: rozmiar ciągle się zmienia
    sw.okno = okno; dp.tik(); sw.t += 0.6
sprawdz("5i przeciąganie okna resetuje debounce", sw.wyslane == [])
tiki(dp, sw, 3)
sprawdz("5j po ustaniu zmian wysyła ostatni rozmiar", sw.wyslane == [(1130, 910)], str(sw.wyslane))

sw = Swiat(); sw.okno = (500, 400); dp = nowy(sw)
tiki(dp, sw, 5)
sprawdz("5k okno małe: clamp do 800x600", sw.wyslane == [(800, 600)], str(sw.wyslane))
tiki(dp, sw, 5)
sprawdz("5l małe okno nie powoduje pętli wysyłania", sw.wyslane == [(800, 600)])

sw = Swiat(); sw.okno = (1400, 900); sw.ogranicza_do = (1200, 900); dp = nowy(sw)
tiki(dp, sw, 6)
sprawdz("5m serwer ograniczył rozmiar: nie męczymy go co sekundę", len(sw.wyslane) == 1, str(sw.wyslane))
sw.okno = (1500, 900); tiki(dp, sw, 3)
sprawdz("5n nowy rozmiar okna po ograniczeniu: wysyła znowu", len(sw.wyslane) == 2, str(sw.wyslane))

sw = Swiat(); sw.okno = None; dp = nowy(sw)
tiki(dp, sw, 3)
sprawdz("5o brak okna (hyprctl pusty): nic nie robi, nie czyta RFB", sw.wyslane == [] and sw.odczyty == 0)

sw = Swiat(); sw.okno = (1200, 800); sw.pada = True; dp = nowy(sw)
tiki(dp, sw, 4)
sw.pada = False; tiki(dp, sw, 4)
sprawdz("5p błąd połączenia: po powrocie serwera próbuje ponownie", sw.wyslane == [(1200, 800)], str(sw.wyslane))

sw = Swiat(); dp = nowy(sw)
dp.tik(); sw.t += d.ODSWIEZ_S + 1; sw.wyjscie = (1300, 910); sw.okno = (1000, 910)
dp.tik(); sw.t += 1.0; dp.tik(); sw.t += 1.5; dp.tik()
sprawdz("5q okresowy odczyt wyjścia wykrywa cudzą zmianę i koryguje", sw.wyslane == [(1000, 910)], str(sw.wyslane))

# --- 6. całość na atrapie RFB (port, z Dopasowywaczem) ---
srv = SerwerRFB(800, 910); srv.start()
sw = Swiat(); sw.okno = (1175, 910)
dp = d.Dopasowywacz(sw.czytaj_okno, lambda: d.odczytaj_rozmiar(srv.port), lambda w, h: d.ustaw_rozmiar(srv.port, w, h), sw.zegar, sw.log)
tiki(dp, sw, 4)
sprawdz("6a Dopasowywacz + atrapa RFB: wyjście 1174x910", (srv.szer, srv.wys) == (1174, 910), f"{srv.szer}x{srv.wys}")
sprawdz("6b każde połączenie shared (nie rozłącza podglądu)", all(c == b"\x01" for c in srv.client_init))
srv.zamknij()

# --- 7. main z wyłączeniem ---
env0 = _os.environ.get("RETRONIC_DOPASUJ_OKNO")
_os.environ["RETRONIC_DOPASUJ_OKNO"] = "0"
sprawdz("7a main przy RETRONIC_DOPASUJ_OKNO=0 kończy od razu (kod 0)", d.main(["--port", "1", "--pid", str(_os.getpid())]) == 0)
if env0 is None: del _os.environ["RETRONIC_DOPASUJ_OKNO"]
else: _os.environ["RETRONIC_DOPASUJ_OKNO"] = env0
sprawdz("7b zyje(): własny proces tak, nieistniejący nie", d.zyje(_os.getpid()) and not d.zyje(2 ** 22 + 12345))
sp = subprocess.Popen(["sleep", "30"]); pid_sp = sp.pid
sp.terminate(); sp.wait()
sprawdz("7c zyje(): zakończony proces nie", not d.zyje(pid_sp))

# --- 8. podglad.sh / sesja.sh (statycznie) ---
KAT = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
pod = open(KAT + "/podglad.sh").read(); ses = open(KAT + "/sesja.sh").read()
sprawdz("8a podglad.sh: bash -n", subprocess.run(["bash", "-n", KAT + "/podglad.sh"]).returncode == 0)
sprawdz("8b sesja.sh: bash -n", subprocess.run(["bash", "-n", KAT + "/sesja.sh"]).returncode == 0)
sprawdz("8c podglad.sh: helper z pid vncviewera, RETRONIC_DOPASUJ_OKNO, -RemoteResize=0, bez exec vncviewer",
        "dopasuj_okno.py" in pod and '--pid "$VPID"' in pod and "RETRONIC_DOPASUJ_OKNO" in pod
        and "-RemoteResize=0" in pod and "exec vncviewer" not in pod)
sprawdz("8d sesja.sh: domyślnie 1175x910 z nadpisaniem env", 'RETRONIC_BEZ_OKNA_ROZ:-1175x910' in ses)

# --- 9. ekran: log zmiany rozmiaru (atrapy, bez X) ---
import io, contextlib
import ekran
from PIL import Image
ekran._ostatni_rozmiar = None
wyj = io.StringIO()
with contextlib.redirect_stdout(wyj):
    ekran._zauwaz_rozmiar((800, 910)); ekran._zauwaz_rozmiar((800, 910)); ekran._zauwaz_rozmiar((1174, 910)); ekran._zauwaz_rozmiar((1174, 910))
linie = wyj.getvalue().strip().splitlines()
sprawdz("9a pierwszy rozmiar bez logu, zmiana = jedna linia", len(linie) == 1 and linie[0].endswith("ekran: nowy rozmiar 1174x910, wykrywam mapę od nowa"), str(linie))

# aktualny_prostokat: niezgodność zrzut/X nie trafia do cache pod rozmiarem X
ekran._cache_mapy.clear(); ekran._ostatni_rozmiar = None; ekran._rozmiar_od = 0.0
def plansza(sz, wy):
    im = Image.new("RGB", (sz, wy), (24, 24, 24))
    mapa_szer = sz - 185; mapa_wys = round(mapa_szer * 11 / 15)
    for x in range(0, mapa_szer):
        for y in range(0, mapa_wys, 1):
            im.putpixel((x, 5 + y), (60 + (x * 7) % 90, 90 + (y * 5) % 100, 40 + (x + y) % 80))
    return im
org = (ekran._rozmiar_ekranu, ekran.zrzut)
try:
    ekran._rozmiar_ekranu = lambda e=None: (1000, 910)
    ekran.zrzut = lambda: plansza(800, 910)
    with contextlib.redirect_stdout(io.StringIO()):
        p = ekran.aktualny_prostokat()
    sprawdz("9b niezgodny rozmiar zrzutu i X: wynik zwrócony, ale nie zapamiętany", p and (1000, 910) not in ekran._cache_mapy, str(p))
    ekran.zrzut = lambda: plansza(1000, 910)
    with contextlib.redirect_stdout(io.StringIO()):
        p2 = ekran.aktualny_prostokat()
    sprawdz("9c zgodny rozmiar: wykrycie i cache", (1000, 910) in ekran._cache_mapy and p2 == ekran._cache_mapy[(1000, 910)])
    # 9d: świeżo po zmianie rozmiaru (< ROZMIAR_STABILNY_S) prostokąt bez zapamiętania; po czasie - cache
    ekran._rozmiar_ekranu = lambda e=None: (1174, 910)
    ekran.zrzut = lambda: plansza(1174, 910)
    with contextlib.redirect_stdout(io.StringIO()):
        p3 = ekran.aktualny_prostokat()
    sprawdz("9d tuż po zmianie rozmiaru: wynik bez cache (klient może rysować stary kadr)", p3 and (1174, 910) not in ekran._cache_mapy, str(p3))
    ekran._rozmiar_od -= ekran.ROZMIAR_STABILNY_S + 0.1
    with contextlib.redirect_stdout(io.StringIO()):
        p4 = ekran.aktualny_prostokat()
    sprawdz("9e po ROZMIAR_STABILNY_S: wykrycie trafia do cache", (1174, 910) in ekran._cache_mapy and p4 == ekran._cache_mapy[(1174, 910)])
finally:
    ekran._rozmiar_ekranu, ekran.zrzut = org

# --- 10. integracja: headless sway + wayvnc (pomijana bez narzędzi) ---
def integracja():
    if not (shutil.which("sway") and shutil.which("wayvnc") and shutil.which("swaymsg")):
        print("SKIP integracja (brak sway/wayvnc)"); return
    kat = tempfile.mkdtemp(prefix="dopasuj-okno-")
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    port = max(port, 5990) if port < 5990 else port
    conf = f"""default_border none
output * resolution 800x910
exec sh -c 'printf "%s" "$SWAYSOCK" > {kat}/swaysock'
exec wayvnc -S {kat}/ctl.sock 127.0.0.1 {port}
"""
    open(kat + "/sway.conf", "w").write(conf)
    env = dict(_os.environ, WLR_BACKENDS="headless", WLR_LIBINPUT_NO_DEVICES="1", WLR_RENDERER="pixman", WLR_HEADLESS_OUTPUTS="1")
    env.pop("SWAYSOCK", None); env.pop("WAYLAND_DISPLAY", None)
    sway = subprocess.Popen(["sway", "--unsupported-gpu", "-c", kat + "/sway.conf"], env=env,
                            stdout=open(kat + "/sway.log", "w"), stderr=subprocess.STDOUT)
    swaysock = None
    try:
        for _ in range(100):
            time.sleep(0.2)
            try:
                swaysock = open(kat + "/swaysock").read().strip()
                if swaysock: 
                    try:
                        socket.create_connection(("127.0.0.1", port), timeout=0.3).close(); break
                    except OSError: pass
            except OSError: pass
        else:
            sprawdz("10 integracja: sway+wayvnc wystartowały", False, open(kat + "/sway.log").read()[-300:]); return
        def wyjscie():
            o = json.loads(subprocess.run(["swaymsg", "-s", swaysock, "-t", "get_outputs", "-r"], capture_output=True, text=True).stdout)[0]
            return o["current_mode"]["width"], o["current_mode"]["height"]
        sprawdz("10a wyjście startowe 800x910", wyjscie() == (800, 910), str(wyjscie()))
        kod, po, przed = d.ustaw_rozmiar(port, 1174, 910)
        time.sleep(0.5)
        sprawdz("10b SetDesktopSize zmienia wyjście sway na 1174x910", wyjscie() == (1174, 910) and przed == (800, 910), f"{wyjscie()} kod={kod} po={po}")
        sw = Swiat(); sw.okno = (900, 700)
        dp = d.Dopasowywacz(sw.czytaj_okno, lambda: d.odczytaj_rozmiar(port), lambda w, h: d.ustaw_rozmiar(port, w, h), sw.zegar, sw.log)
        tiki(dp, sw, 4); time.sleep(0.5)
        sprawdz("10c Dopasowywacz na prawdziwym wayvnc: 900x700", wyjscie() == (900, 700), str(wyjscie()))
        sw.okno = (300, 200); tiki(dp, sw, 4); time.sleep(0.5)
        sprawdz("10d okno poniżej minimum: wyjście 800x600", wyjscie() == (800, 600), str(wyjscie()))
    finally:
        if swaysock:
            subprocess.run(["swaymsg", "-s", swaysock, "exit"], capture_output=True)
        try: sway.wait(timeout=5)
        except subprocess.TimeoutExpired: sway.terminate(); sway.wait(timeout=5)
        shutil.rmtree(kat, ignore_errors=True)
integracja()

# 19.10: z botem ekran sesji się nie rusza (zmiana kształtu okna chowa panele klienta i bot traci odczyt)
sprawdz("20a bot działa: rozmiar_docelowy = None (bez zmiany ekranu)", d.rozmiar_docelowy((1030, 1030), True) is None)
sprawdz("20b brak bota: ekran = okno podglądu", d.rozmiar_docelowy((941, 1030), False) == (941, 1030))

# 19.10: bot_dziala() liczy tylko bota TEJ instancji (bot `test` blokował serwis Mastafiana i zatrzymywał helper)
_tmp = tempfile.mkdtemp(prefix="proc-")
def _proces(pid, rid):
    _os.makedirs(f"{_tmp}/{pid}")
    open(f"{_tmp}/{pid}/cmdline", "wb").write(b"python3\0-I\0-u\0mozg.py\0--trasa\0x\0")
    open(f"{_tmp}/{pid}/environ", "wb").write(b"PATH=/usr/bin\0" + (b"RETRONIC_ID=" + rid.encode() + b"\0" if rid is not None else b""))
_proces("111", "test")
sprawdz("BD1 bot instancji `test` NIE blokuje głównej (instancja='')", d.bot_dziala(proc=_tmp, instancja="") is False)
sprawdz("BD2 ten sam bot blokuje instancję `test`", d.bot_dziala(proc=_tmp, instancja="test") is True)
_proces("222", None)
sprawdz("BD3 bot głównej (bez RETRONIC_ID) blokuje główną", d.bot_dziala(proc=_tmp, instancja="") is True)
sprawdz("BD4 ...ale nie instancję `inna`", d.bot_dziala(proc=_tmp, instancja="inna") is False)
_os.makedirs(f"{_tmp}/333"); open(f"{_tmp}/333/cmdline", "wb").write(b"python3\0mozg.py\0")
sprawdz("BD5 proces bez czytelnego environ liczy się ostrożnie jak dawniej (blokuje)", d.bot_dziala(proc=_tmp, instancja="inna") is True)
shutil.rmtree(_tmp, ignore_errors=True)

print("WYNIK", "OK" if all(ok) else "FAIL", f"{sum(ok)}/{len(ok)}"); sys.exit(0 if all(ok) else 1)
