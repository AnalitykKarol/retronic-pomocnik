"""Marsz klikiem (marsz_klik.py) i auto-refill po dojściu do depo (refill_auto.py), 20.10: jednostki, pole panelu i skrypty
(refill.sh --przerwij, wroc.sh --anuluj) w atrapie katalogu. Nic nie dotyka gry, bota ani żywych instancji (własne RETRONIC_ID).
Wymaga bash, setsid. Część „Wyprawa → decyzja” jest w test_wyprawa.py (sekcja 20)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
_os.environ["RETRONIC_ID"] = "tstwroc"                # unikalne ID: pidy/ubijanie nie dotykają prawdziwych instancji
import json, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import instancja
import marsz_klik
import panel
import refill_auto

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, "" if warunek else info)

# ---------------------------------------------------------------- 1. marsz_klik: koszt pola, najdalsze pole, klik i czekanie
class Mapa:
    def __init__(self, nad=None): self.nad = nad or {}
    def flagi(self, x, y, z): return self.nad.get((x, y, z), 1 if z in (6, 7, 8) else 0)
M = Mapa({(5, 5, 7): 1 | 4, (6, 5, 7): 0, (7, 5, 7): 3, (7, 5, 6): 2, (9, 5, 7): 3, (20, 20, 7): 3})   # (7,5) schody, (9,5) i (20,20) krzesła
k = lambda x, y, z=7: marsz_klik.koszt_pola(M, x, y, z)
sprawdz("1a zwykłe pole = 1.0", k(1, 1) == 1.0)
sprawdz("1b flaga blokady (4) i brak flagi chodliwości = None", k(5, 5) is None and k(6, 5) is None)
sprawdz("1c schody (flaga 2 z odpowiednikiem flagi 2 na piętrze obok) = None", k(7, 5) is None)
sprawdz("1d pole z flagą 2 bez odpowiednika (krzesło) = 6.0 (nie zwykłe: marsz klikiem go nie klika)", k(20, 20) == 6.0 and k(9, 5) == 6.0)
sprawdz("1e pole docelowe zawsze 1.0, pole z listy unik = None",
        marsz_klik.koszt_pola(M, 5, 5, 7, cel=(5, 5)) == 1.0 and marsz_klik.koszt_pola(M, 1, 1, 7, unik={(1, 1)}) is None)
sc = [(1 + i, 1, 7) for i in range(10)]
sprawdz("1f dalej_klik: zwykła ścieżka = KLIK_MAKS_POL", marsz_klik.dalej_klik(sc, lambda x, y, z: 1.0, 7) == marsz_klik.KLIK_MAKS_POL == 5)
sprawdz("1g dalej_klik: krótka ścieżka kończy się na ostatnim polu", marsz_klik.dalej_klik(sc[:3], lambda x, y, z: 1.0, 7) == 2)
sprawdz("1h dalej_klik: niezwykłe pole nr 3 skraca do 2", marsz_klik.dalej_klik(sc, lambda x, y, z: None if x == 4 else 1.0, 7) == 2)
sprawdz("1i dalej_klik: pole nr 1 niezwykłe — serwis (domyślnie) je pomija, wyprawa (pierwsze_zwykle) nie klika",
        marsz_klik.dalej_klik(sc, lambda x, y, z: 6.0 if x == 2 else 1.0, 7) == 5
        and marsz_klik.dalej_klik(sc, lambda x, y, z: 6.0 if x == 2 else 1.0, 7, pierwsze_zwykle=True) == 1)

class Sw:
    """Czas wirtualny i postać: lista pozycji zwracanych kolejnym odczytom (ostatnia się powtarza)."""
    def __init__(self, pozycje, przerwij_na=None):
        self.t, self.p, self.i = 0.0, list(pozycje), 0
    def monotonic(self): return self.t
    def time(self): return self.t
    def sleep(self, s): self.t += s
    def pozycja(self):
        v = self.p[min(self.i, len(self.p) - 1)]; self.i += 1; return v
P0, CEL = (10, 10, 7), (15, 10, 7)
def kc(pozycje, **kw):
    sw = Sw(pozycje); logi = []
    r = marsz_klik.klik_i_czekaj(sw, P0, CEL, 5, zegar=sw, log=logi.append, **kw)
    return r, logi
sprawdz("1j dojście do pola kliku = ruch", kc([(11, 10, 7), (13, 10, 7), (15, 10, 7), (15, 10, 7)])[0] == "ruch")
r, lg = kc([(10, 10, 7), (10, 10, 6)])
sprawdz("1k zmiana piętra po kliku = pietro (z logiem z prefiksem)", r == "pietro" and lg and lg[0].startswith("marsz klikiem:"), (r, lg))
sprawdz("1l postać stoi cały czas = bez_ruchu", kc([P0])[0] == "bez_ruchu")
sprawdz("1m ruszyła i stanęła (4 odczyty bez zmiany) = ruch", kc([(11, 10, 7)])[0] == "ruch")
r, lg = kc([(11, 10, 7), (12, 10, 7), (12, 10, 7), (13, 10, 7), (14, 10, 7)], przerwij=lambda p: p[0] >= 13)
sprawdz("1n przerwij() zwraca True = przerwano (sprawdzane co 3. odczyt)", r == "przerwano", (r, lg))
r, lg = kc([(11, 10, 7), (12, 10, 7), (13, 10, 7), (14, 10, 7), (15, 10, 7)], przerwij=lambda p: False)
sprawdz("1o przerwij() zwraca False = marsz trwa do pola kliku", r == "ruch")

# ---------------------------------------------------------------- 2. refill_auto: decyzja, czekacz, anulowanie
EDRON_DEPO, EDRON_ULICA, THAIS, ROOK = (33173, 31796, 8), (33170, 31810, 7), (32366, 32215, 7), (32097, 32219, 7)
tmp = Path(tempfile.mkdtemp(prefix="test_wroc_refill_auto_"))
stan = tmp / "stan"; stan.mkdir()
def cz(): return refill_auto.czytaj_stan(stan)
def czysc():
    for f in stan.iterdir(): f.unlink()
nic = lambda wzor, **kw: []
starty = []
sprawdz("2a miasto_serwisu: depo Edron = (edron, w depo)", refill_auto.miasto_serwisu(EDRON_DEPO) == ("edron", True))
sprawdz("2b ulica Edron = (edron, nie w depo); Thais, Rook, brak = (None, False)",
        refill_auto.miasto_serwisu(EDRON_ULICA) == ("edron", False)
        and all(refill_auto.miasto_serwisu(p) == (None, False) for p in (THAIS, ROOK, (0, 0, 7))))
r = refill_auto.zlec(EDRON_DEPO, stan, start=lambda: starty.append(1), procesy=nic)
sprawdz("2c depo Edron, nic nie trwa: start czekacza raz, decyzja czeka", r[0] == "czeka" and starty == [1] and cz()["stan"] == "czeka", (r, starty))
czysc(); starty.clear()
r = refill_auto.zlec(THAIS, stan, start=lambda: starty.append(1), procesy=nic)
sprawdz("2d Thais: brak_planu, czytelny powód (miasto, pozycja, które miasta mają plan), start NIE rusza",
        r[0] == "brak_planu" and starty == [] and "brak planu serwisu" in cz()["powod"] and "edron" in cz()["powod"]
        and "32366" in cz()["powod"], (r, cz()))
czysc()
r = refill_auto.zlec(EDRON_ULICA, stan, start=lambda: starty.append(1), procesy=nic)
sprawdz("2e Edron, ale poza depo: pominiety, start nie rusza", r[0] == "pominiety" and starty == [] and "depo" in cz()["powod"], r)
czysc()
(stan / "STOP_RECZNY").touch()
r = refill_auto.zlec(EDRON_DEPO, stan, start=lambda: starty.append(1), procesy=nic)
sprawdz("2f STOP_RECZNY: pominiety (pierwszeństwo człowieka), start nie rusza", r[0] == "pominiety" and starty == [] and "ręczny" in cz()["powod"], r)
czysc()
for nazwa, wzor_ok in (("serwis.py", lambda w: "serwis" in w), ("refill.sh", lambda w: "refill" in w), ("czekacz", lambda w: "czekaj" in w)):
    r = refill_auto.zlec(EDRON_DEPO, stan, start=lambda: starty.append(1), procesy=lambda w, **kw: [99] if wzor_ok(w) else [])
    sprawdz(f"2g {nazwa} już trwa: pominiety, drugi nie rusza", r[0] == "pominiety" and starty == [], r)
    czysc()
r = refill_auto.zlec(EDRON_DEPO, stan, start=lambda: (_ for _ in ()).throw(OSError("x")), procesy=nic)
sprawdz("2h błąd startu czekacza: pominiety z powodem, bez wyjątku", r[0] == "pominiety" and "nie udało się" in r[1], r)
czysc()

# czekacz z atrapami
class Proc:
    """procesy(): bot „żyje” przez n wywołań, serwis/refill wg flag; zapisuje kolejność wywołań uruchom()."""
    def __init__(self, bot_n=2, serwis=False): self.n, self.serwis, self.wyw = bot_n, serwis, []
    def __call__(self, wzor, **kw):
        if "mozg" in wzor:
            self.n -= 1; return [7] if self.n >= 0 else []
        return [8] if self.serwis and ("serwis" in wzor or "refill" in wzor) else []
def uruchom_atrapa(wyw, rc=0, out=""):
    def u(cmd, **kw):
        wyw.append(cmd)
        return subprocess.CompletedProcess(cmd, rc if "refill.sh" in " ".join(map(str, cmd)) else 0, out, out)
    return u
def czekaj_t(proc, rc=0, out="", czekaj_s=60.0, przed=None, **kw):
    czysc(); wyw = []; t = [0.0]
    if przed: przed()
    kod = refill_auto.czekaj(stan, procesy=proc, uruchom=uruchom_atrapa(wyw, rc, out), spij=lambda s: t.__setitem__(0, t[0] + s),
                             zegar=lambda: t[0], czekaj_s=czekaj_s, **kw)
    return kod, wyw
kod, wyw = czekaj_t(Proc(bot_n=3))
kom = [" ".join(map(str, c)) for c in wyw]
sprawdz("2i czekacz: po zniknięciu bota zwalnia wejście, potem refill.sh --tlo; decyzja uruchomiony",
        kod == 0 and len(kom) == 2 and "zwolnij_wejscie.py" in kom[0] and kom[1].endswith("refill.sh --tlo") and cz()["stan"] == "uruchomiony", (kod, kom, cz()))
kod, wyw = czekaj_t(Proc(bot_n=3), przed=lambda: (stan / "STOP_RECZNY").touch())
sprawdz("2j STOP_RECZNY pojawił się w trakcie czekania: refill nie rusza, pominiety", kod == 0 and wyw == [] and cz()["stan"] == "pominiety", (kod, wyw, cz()))
kod, wyw = czekaj_t(Proc(bot_n=3, serwis=True))
sprawdz("2k serwis wystartował w międzyczasie: refill nie rusza", wyw == [] and cz()["stan"] == "pominiety", (wyw, cz()))
kod, wyw = czekaj_t(Proc(bot_n=10 ** 6), czekaj_s=5.0)
sprawdz("2l bot nie zatrzymał się w limicie: rezygnacja (kod 1), nic nie ubijamy ani nie startujemy", kod == 1 and wyw == [] and cz()["stan"] == "pominiety", (kod, wyw, cz()))
kod, wyw = czekaj_t(Proc(bot_n=1), rc=1, out="bot działa (pid 5), zatrzymaj: ./zatrzymaj.sh")
sprawdz("2m refill.sh odmówił: pominiety z jego komunikatem, kod odmowy", kod == 1 and cz()["stan"] == "pominiety" and "bot działa" in cz()["powod"], (kod, cz()))

# anuluj
czysc(); ubite = []
n = refill_auto.anuluj(stan, procesy=lambda w, **kw: [31, 32] if "czekaj" in w else [], zabij=lambda p, s: ubite.append(p))
sprawdz("2n anuluj: ubija czekaczy tej instancji i zapisuje powód", n == 2 and ubite == [31, 32] and cz()["stan"] == "pominiety" and "anulowane" in cz()["powod"], (n, ubite, cz()))
czysc()
n = refill_auto.anuluj(stan, procesy=nic, zabij=lambda p, s: ubite.append(p))
sprawdz("2o anuluj bez czekacza: 0 i brak pliku decyzji", n == 0 and cz() == {})

# ---------------------------------------------------------------- 3. panel: pole wroc_refill
logi = stan / "logi"; logi.mkdir()
A = lambda **k: panel.stan_auto_refill(stan, **k)
czysc() if False else None
for f in list(stan.iterdir()):
    if f.is_file(): f.unlink()
sprawdz("3a bez pliku decyzji: None i pusty komunikat", A(serwis_dziala=False, czeka=False) == {"wroc_refill": None, "wroc_refill_komunikat": ""})
refill_auto.zapisz_stan(stan, "czeka", "refill edron ruszy po zatrzymaniu bota")
sprawdz("3b czeka + czekacz żyje = czeka", A(serwis_dziala=False, czeka=True)["wroc_refill"] == "czeka")
sprawdz("3c czeka, czekacza już nie ma, serwis trwa = trwa", A(serwis_dziala=True, czeka=False)["wroc_refill"] == "trwa")
sprawdz("3d czeka, ale nic nie żyje (zerwany) = None", A(serwis_dziala=False, czeka=False)["wroc_refill"] is None)
refill_auto.zapisz_stan(stan, "uruchomiony", "refill.sh --tlo")
sprawdz("3e uruchomiony: trwa tylko dopóki serwis działa (wynik w serwis_wynik)", A(serwis_dziala=True, czeka=False)["wroc_refill"] == "trwa"
        and A(serwis_dziala=False, czeka=False)["wroc_refill"] is None)
refill_auto.zapisz_stan(stan, "brak_planu", "brak planu serwisu dla tego miasta (pozycja (32366, 32215, 7)); serwis ma: edron")
r = A(serwis_dziala=False, czeka=False)
sprawdz("3f brak_planu: pole i komunikat widoczne w panelu", r["wroc_refill"] == "brak_planu" and "brak planu" in r["wroc_refill_komunikat"], r)
refill_auto.zapisz_stan(stan, "pominiety", "ręczny stop (STOP_RECZNY) ma pierwszeństwo")
sprawdz("3g pominiety: widoczny z powodem", A(serwis_dziala=False, czeka=False)["wroc_refill"] == "pominiety")
plik = stan / refill_auto.PLIK
bl = logi / "mozg-stdout-1020-1200.log"; bl.write_text("bot\n")
t0 = plik.stat().st_mtime; _os.utime(bl, (t0 + 60, t0 + 60))
sprawdz("3h bot wystartował po decyzji: pominięcie/brak planu przestają obowiązywać", A(serwis_dziala=False, czeka=False)["wroc_refill"] is None)
(stan / refill_auto.PLIK).write_text("{zepsute")
sprawdz("3i zepsuty plik decyzji nie psuje panelu", A(serwis_dziala=False, czeka=False)["wroc_refill"] is None)
sprawdz("3j panel.py --json zawiera pola wroc_refill i wroc_refill_komunikat obok dotychczasowych (addytywnie)",
        all(k_ in json.loads(subprocess.run([sys.executable, "-I", str(KAT / "panel.py"), "--json"], capture_output=True, text=True,
                                            env=dict(_os.environ, RETRONIC_ID="tstwroc"), timeout=30).stdout)
            for k_ in ("wroc_refill", "wroc_refill_komunikat", "wroc_oczekuje", "wroc_w_marszu", "serwis_dziala", "w_miescie", "text")))

# ---------------------------------------------------------------- 4. skrypty w atrapie katalogu: czekacz → refill.sh --tlo, --przerwij, wroc.sh --anuluj
SAND = tmp / "pomocnik"; SAND.mkdir()
for f in ("refill.sh", "wroc.sh", "instancja.py", "refill_auto.py"):
    shutil.copy(KAT / f, SAND / f)
BIN = tmp / "bin"; BIN.mkdir()
(BIN / "notify-send").write_text("#!/bin/bash\necho \"$@\" >> \"%s/powiadomienia.txt\"\n" % tmp); (BIN / "notify-send").chmod(0o755)
(SAND / "zatrzymaj.sh").write_text("#!/bin/bash\neval \"$(python3 -I \"$(dirname \"$0\")/instancja.py\" powloka)\"\nmkdir -p \"$INST_STAN\"; touch \"$INST_STOP\"\n"
                                   "echo zatrzymaj >> \"%s/wywolania.txt\"\n" % tmp)
(SAND / "serwis.sh").write_text("#!/bin/bash\necho \"serwis.sh STARTUJ=$STARTUJ $*\" >> \"%s/wywolania.txt\"\nexit 0\n" % tmp)
(SAND / "zwolnij_wejscie.py").write_text("from pathlib import Path\nopen(%r, 'a').write('zwolnij_wejscie\\n')\n" % str(tmp / "wywolania.txt"))
(SAND / "mozg.py").write_text("import time\ntime.sleep(120)\n")
for f in ("zatrzymaj.sh", "serwis.sh", "refill.sh", "wroc.sh"): (SAND / f).chmod(0o755)
RT = tmp / "rt"; RT.mkdir()
INST = SAND / "instancje" / "tstwroc"
srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
def ENV(**extra):
    e = {k_: v for k_, v in _os.environ.items()}
    e.update(RETRONIC_ID="tstwroc", XDG_RUNTIME_DIR=str(RT), PATH=f"{BIN}:{_os.environ['PATH']}", REFILL_CZEKAJ_STOP_S="1")
    e.update(extra); return e
def czekaj_na(warunek, s=12.0):
    koniec = time.time() + s
    while time.time() < koniec:
        if warunek(): return True
        time.sleep(0.05)
    return warunek()
def pidy(wzor): return subprocess.run([sys.executable, "-I", str(SAND / "instancja.py"), "pidy", wzor], env=ENV(), capture_output=True, text=True).stdout.split()
def start_bota(): return subprocess.Popen(["python3", "-I", str(SAND / "mozg.py")], env=ENV(), start_new_session=True)
def start_czekacza(): return subprocess.Popen([sys.executable, "-I", str(SAND / "refill_auto.py"), "czekaj"], cwd=str(SAND), env=ENV(),
                                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
def stan_pliku():
    try: return json.loads((INST / refill_auto.PLIK).read_text())
    except (OSError, ValueError): return {}
def wyw():
    try: return (tmp / "wywolania.txt").read_text()
    except OSError: return ""
def posprzataj():
    for p in pidy(r"mozg\.py") + pidy(r"refill_auto\.py czekaj"):
        subprocess.run(["kill", "-KILL", p], capture_output=True)
    for f in list(INST.glob("*")):
        if f.is_file(): f.unlink()
    (tmp / "wywolania.txt").unlink(missing_ok=True)
try:
    INST.mkdir(parents=True, exist_ok=True)
    srv.bind(str(RT / "retronic-tstwroc.sock")); srv.listen(1)
    sprawdz("4a bash -n refill.sh i wroc.sh", all(subprocess.run(["bash", "-n", str(KAT / f)]).returncode == 0 for f in ("refill.sh", "wroc.sh")))

    # a. pełny łańcuch: bot stoi → czekacz czeka → bot znika → zwolnienie wejścia → refill.sh --tlo → serwis.sh STARTUJ=1
    bot = start_bota(); time.sleep(0.4)
    cz_ = start_czekacza()
    sprawdz("4b czekacz widoczny dla wzoru pidy (tej instancji), decyzja 'czeka'", czekaj_na(lambda: pidy(r"(^|[ /])refill_auto\.py czekaj") and stan_pliku().get("stan") == "czeka"), stan_pliku())
    time.sleep(1.2)
    sprawdz("4c dopóki bot żyje: refill nie ruszył", "serwis.sh" not in wyw() and cz_.poll() is None)
    bot.kill(); bot.wait()
    sprawdz("4d po zniknięciu bota: zwolnienie wejścia, potem serwis.sh STARTUJ=1 z krokami refillu (bez banku i depo)",
            czekaj_na(lambda: "serwis.sh STARTUJ=1 --kroki jedzenie,backpack,blanki,wyjscie" in wyw())
            and "zwolnij_wejscie" in wyw() and wyw().index("zwolnij_wejscie") < wyw().index("serwis.sh"), wyw())
    sprawdz("4e refill.log ma START i OK, decyzja uruchomiony, czekacz zakończył się sam",
            czekaj_na(lambda: "REFILL: OK" in (INST / "refill.log").read_text() if (INST / "refill.log").exists() else False)
            and czekaj_na(lambda: stan_pliku().get("stan") == "uruchomiony") and czekaj_na(lambda: cz_.poll() == 0), stan_pliku())
    posprzataj()

    # b. STOP_RECZNY w trakcie czekania
    bot = start_bota(); time.sleep(0.4); cz_ = start_czekacza()
    czekaj_na(lambda: stan_pliku().get("stan") == "czeka")
    (INST / "STOP_RECZNY").touch()
    bot.kill(); bot.wait()
    sprawdz("4f STOP_RECZNY: czekacz kończy bez refillu, decyzja 'ręczny stop'",
            czekaj_na(lambda: cz_.poll() == 0) and "serwis.sh" not in wyw() and "ręczny" in stan_pliku().get("powod", ""), (wyw(), stan_pliku()))
    posprzataj()

    # c. refill.sh --przerwij w trakcie czekania zabija czekacza
    bot = start_bota(); time.sleep(0.4); cz_ = start_czekacza()
    czekaj_na(lambda: stan_pliku().get("stan") == "czeka")
    r = subprocess.run(["bash", str(SAND / "refill.sh"), "--przerwij"], env=ENV(), capture_output=True, text=True, timeout=30)
    sprawdz("4g refill.sh --przerwij: czekacz ubity (nie 'nic do przerwania'), decyzja anulowana, STOP ustawiony",
            r.returncode == 0 and "nic do przerwania" not in r.stdout and czekaj_na(lambda: cz_.poll() is not None) and "anulowane" in stan_pliku().get("powod", "")
            and (INST / "STOP").exists(), (r.returncode, r.stdout, r.stderr, stan_pliku()))
    bot.kill(); bot.wait(); posprzataj()

    # d. wroc.sh --anuluj anuluje oczekujący auto-refill
    bot = start_bota(); time.sleep(0.4); cz_ = start_czekacza()
    czekaj_na(lambda: stan_pliku().get("stan") == "czeka")
    r = subprocess.run(["bash", str(SAND / "wroc.sh"), "--anuluj"], env=ENV(), capture_output=True, text=True, timeout=30)
    sprawdz("4h wroc.sh --anuluj z oczekującym auto-refillem: czekacz ubity, komunikat 'auto-refill anulowany', bez 'brak zlecenia'",
            r.returncode == 0 and "auto-refill anulowany" in r.stdout and "brak zlecenia" not in r.stdout
            and czekaj_na(lambda: cz_.poll() is not None), (r.stdout, r.stderr))
    bot.kill(); bot.wait(); posprzataj()
    r = subprocess.run(["bash", str(SAND / "wroc.sh"), "--anuluj"], env=ENV(), capture_output=True, text=True, timeout=30)
    sprawdz("4i wroc.sh --anuluj bez niczego: jak dotąd 'brak zlecenia', kod 0", r.returncode == 0 and "brak zlecenia" in r.stdout and "auto-refill" not in r.stdout, r.stdout)
    r = subprocess.run(["bash", str(SAND / "refill.sh"), "--przerwij"], env=ENV(), capture_output=True, text=True, timeout=30)
    sprawdz("4j refill.sh --przerwij bez niczego: 'nic do przerwania', bez STOP", r.returncode == 0 and "nic do przerwania" in r.stdout and not (INST / "STOP").exists(), r.stdout)
finally:
    try: posprzataj()
    except Exception: pass
    srv.close()
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
