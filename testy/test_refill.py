"""Guziki paska „Wróć do miasta” i „Refill” (19.10): pola panel.py --json oraz refill.sh.
Offline: refill.sh chodzi w atrapie katalogu (stuby serwis.sh/zatrzymaj.sh/notify-send, własne RETRONIC_ID),
nic nie dotyka gry, bota ani żywych instancji. Wymaga bash, setsid, ps."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
_os.environ["RETRONIC_ID"] = "tstrefill"              # unikalne ID: pidy/ubijanie nie dotykają prawdziwych instancji
import json, shutil, socket, subprocess, sys, tempfile, threading, time
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import instancja
import panel

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

# ---------------------------------------------------------------- 1. strefa miasta i plan depo
EDRON_DEPO, EDRON_ULICA, GOBLINY, THAIS, ROOK, DALEKO = (33173, 31796, 8), (33170, 31810, 7), (33053, 31844, 8), \
    (32366, 32215, 7), (32097, 32219, 7), (33300, 31800, 7)
sprawdz("1a depo Edron: w mieście i w depo", panel.miasto_pozycji(EDRON_DEPO) == ("edron", True))
sprawdz("1b ulica Edron: w mieście, nie w depo", panel.miasto_pozycji(EDRON_ULICA) == ("edron", False))
sprawdz("1c spot goblinów, Rook, daleko od miasta: nie w mieście",
        all(panel.miasto_pozycji(p) == (None, False) for p in (GOBLINY, ROOK, DALEKO)))
sprawdz("1c2 Thais (serwis_thais.json, 21.10 K3): ulica w mieście, depo w depo",
        panel.miasto_pozycji(THAIS) == ("thais", False) and panel.miasto_pozycji((32348, 32225, 7)) == ("thais", True))
sprawdz("1d brak pozycji = nie w mieście", panel.miasto_pozycji(None) == (None, False))
sprawdz("1e plan depo: gobliny -> gobliny_edron, depo Edron -> edron", panel.plan_depo(GOBLINY) == "gobliny_edron"
        and panel.plan_depo(EDRON_DEPO) == "edron")
sprawdz("1f plan depo: Rookgaard bez planu, brak pozycji = None", panel.plan_depo(ROOK) is None and panel.plan_depo(None) is None)

# ---------------------------------------------------------------- 2. stan WROC / serwis z plików
tmp = Path(tempfile.mkdtemp(prefix="test_refill_"))
stan = tmp / "stan"; stan.mkdir()
w = panel.stan_wroc(stan, bot_dziala=True)
sprawdz("2a bez plików: nic nie czeka, nie w marszu", w == {"wroc_oczekuje": False, "wroc_w_marszu": False})
(stan / "WROC").touch()
sprawdz("2b plik WROC = oczekuje", panel.stan_wroc(stan, True)["wroc_oczekuje"] is True)
(stan / "wyprawa_stan.json").write_text(json.dumps({"aktywna": True, "powod": "depo:reczny"}))
sprawdz("2c wyprawa ręczna aktywna + bot działa = w marszu", panel.stan_wroc(stan, True)["wroc_w_marszu"] is True)
sprawdz("2d ta sama wyprawa, bot nie działa (zerwany stan) = nie w marszu", panel.stan_wroc(stan, False)["wroc_w_marszu"] is False)
(stan / "wyprawa_stan.json").write_text(json.dumps({"aktywna": True, "powod": "jedzenie"}))
sprawdz("2e wyprawa automatyczna nie jest „Wróć do miasta”", panel.stan_wroc(stan, True)["wroc_w_marszu"] is False)
(stan / "wyprawa_stan.json").write_text(json.dumps({"aktywna": False, "powod": "depo:reczny", "wynik": "depo"}))
sprawdz("2f zakończona ręczna wyprawa: już nie w marszu", panel.stan_wroc(stan, True)["wroc_w_marszu"] is False)
(stan / "wyprawa_stan.json").write_text("{zepsute")
sprawdz("2g zepsuty plik stanu nie psuje odczytu", panel.stan_wroc(stan, True)["wroc_w_marszu"] is False)

LOG = stan / "refill.log"
S = lambda **k: panel.stan_serwisu(stan, teraz=time.time(), **k)
sprawdz("2h bez logu: nic nie trwa, brak wyniku", S(dziala=False)["serwis_wynik"] is None and S(dziala=False)["serwis_dziala"] is False)
LOG.write_text("REFILL: START 1\nserwis: krok jedzenie\nserwis[jedzenie]: idę\nserwis: krok backpack\n")
r = S(dziala=True)
sprawdz("2i0 stary znacznik bez trybu: serwis_tryb None", S(dziala=True)["serwis_tryb"] is None)
LOG.write_text("REFILL: START 1 spot\nserwis: krok wyjscie\n")
sprawdz("2i1 START z trybem spot, krok wyjscie", S(dziala=True)["serwis_tryb"] == "spot" and S(dziala=True)["serwis_krok"] == "wyjscie"
        and S(dziala=False)["serwis_tryb"] is None)
LOG.write_text("REFILL: START 1\nserwis: krok jedzenie\nserwis[jedzenie]: idę\nserwis: krok backpack\n")
r = S(dziala=True)
sprawdz("2i trwa: ostatni krok z logu, bez wyniku", r["serwis_dziala"] and r["serwis_krok"] == "backpack" and r["serwis_wynik"] is None)
r = S(dziala=False)
sprawdz("2j log bez znacznika końca i bez procesu = przerwano", r["serwis_wynik"] == "przerwano" and r["serwis_krok"] is None)
LOG.write_text("REFILL: START 1\nserwis: krok jedzenie\nREFILL: OK\n")
sprawdz("2k OK", S(dziala=False)["serwis_wynik"] == "ok")
LOG.write_text("REFILL: START 1\nserwis: krok blanki\nSERWIS: PORAŻKA w kroku blanki: brak miejsca\nREFILL: BLAD blanki: brak miejsca\n")
r = S(dziala=False)
sprawdz("2l błąd: powód z ostatniej linii znacznika", r["serwis_wynik"] == "blad" and r["serwis_komunikat"] == "blanki: brak miejsca")
LOG.write_text("REFILL: START 1\nREFILL: BLAD x\nREFILL: START 2\nserwis: krok jedzenie\n")
sprawdz("2m nowy START po starym błędzie: stary wynik nie wraca", S(dziala=True)["serwis_wynik"] is None
        and S(dziala=True)["serwis_krok"] == "jedzenie")
LOG.write_text("REFILL: START 1\nREFILL: PRZERWANO\n")
sprawdz("2n przerwano", S(dziala=False)["serwis_wynik"] == "przerwano")
# błąd -> start bota -> stop bota: błąd NIE wraca (log stdout bota nowszy niż refill.log)
LOG.write_text("REFILL: START 1\nREFILL: BLAD blanki: brak miejsca\n")
(stan / "logi").mkdir(exist_ok=True)
sprawdz("2n2 bez startu bota błąd widoczny", S(dziala=False)["serwis_wynik"] == "blad")
bl = stan / "logi" / "mozg-stdout-1019-1800.log"; bl.write_text("bot\n")
tl = LOG.stat().st_mtime
_os.utime(bl, (tl + 60, tl + 60))
r = S(dziala=False)
sprawdz("2n3 po starcie bota (i jego Stopie) błąd nie wraca", r["serwis_wynik"] is None and r["serwis_komunikat"] == "")
_os.utime(bl, (tl - 60, tl - 60))
sprawdz("2n4 log bota starszy niż refill.log (bot sprzed refillu): błąd widoczny", S(dziala=False)["serwis_wynik"] == "blad")
bl.unlink()
LOG.write_text("REFILL: START 1\n")
sprawdz("2n5 START bez linii kroku: nie zgadujemy kroku ze stanu", S(dziala=True, kolejnosc=["bank", "depo"])["serwis_krok"] is None)
LOG.unlink()
(stan / "serwis_stan.json").write_text(json.dumps({"ukonczone": ["jedzenie"], "koniec": False, "t": 1}))
r = S(dziala=True, kolejnosc=["bank", "depo", "jedzenie", "backpack", "blanki", "wyjscie"])
sprawdz("2o serwis z terminala (bez logu): krok z serwis_stan.json", r["serwis_krok"] == "bank", r["serwis_krok"])
(stan / "serwis_stan.json").write_text(json.dumps({"ukonczone": ["jedzenie", "backpack", "blanki"], "koniec": True, "t": 1}))
sprawdz("2p zakończony przebieg: ukończone puste", S(dziala=False)["serwis_ukonczone"] == [])

# ---------------------------------------------------------------- 3. refill.sh w atrapie
SAND = tmp / "pomocnik"; SAND.mkdir()
for f in ("refill.sh", "instancja.py", "w_scope.sh"):
    shutil.copy(KAT / f, SAND / f)
BIN = tmp / "bin"; BIN.mkdir()
(BIN / "notify-send").write_text("#!/bin/bash\necho \"$@\" >> \"%s/powiadomienia.txt\"\n" % tmp)
(BIN / "notify-send").chmod(0o755)
(SAND / "zatrzymaj.sh").write_text("#!/bin/bash\neval \"$(python3 -I \"$(dirname \"$0\")/instancja.py\" powloka)\"\nmkdir -p \"$INST_STAN\"; touch \"$INST_STOP\"\n"
                                   "echo zatrzymaj >> \"%s/wywolania.txt\"\n" % tmp)
# serwis.sh: zapisuje argumenty i STARTUJ; STUB_TRYB: ok | porazka | wisi (uruchamia serwis.py, który śpi)
(SAND / "serwis.sh").write_text("""#!/bin/bash
echo "serwis.sh STARTUJ=$STARTUJ $*" >> "%s/wywolania.txt"
case "$STUB_TRYB" in
  porazka) echo "SERWIS: PORAŻKA w kroku blanki: brak miejsca w plecaku"; exit 2 ;;
  wisi) cd "$(dirname "$0")"; python3 -I -u serwis.py edron --kroki "$2"; exit $? ;;
  odmowa) echo "bot działa (pid 1), zatrzymaj: ./zatrzymaj.sh" >&2; exit 1 ;;
esac
exit 0
""" % tmp)
# serwis.py: jak prawdziwy wychodzi sam po pliku STOP (sprawdz_stop -> Zatrzymano -> finally); STUB_IGNORUJ_STOP=1 = nie reaguje
# na STOP (musi go ubić TERM). Zapisuje do wywolania.txt, kto i w jakiej kolejności go zakończył.
(SAND / "serwis.py").write_text("""import os, signal, sys, time
from pathlib import Path
W = Path(%r) / "wywolania.txt"
STOP = Path(os.environ["INST_STOP_STUB"])
def zapisz(s):
    with open(W, "a") as f: f.write(s + "\\n")
signal.signal(signal.SIGTERM, lambda *_: (zapisz("serwis.py: TERM"), os._exit(143)))
print('serwis: krok jedzenie', flush=True)
for _ in range(1200):
    if STOP.exists() and not os.environ.get("STUB_IGNORUJ_STOP"):
        zapisz("serwis.py: wyszedł sam po STOP"); sys.exit(2)
    time.sleep(0.1)
""" % str(tmp))
(SAND / "zwolnij_wejscie.py").write_text("from pathlib import Path\nopen(%r, 'a').write('zwolnij_wejscie\\n')\n" % str(tmp / "wywolania.txt"))
(SAND / "mozg.py").write_text("import time\ntime.sleep(120)\n")
(SAND / "serwis.sh").chmod(0o755); (SAND / "zatrzymaj.sh").chmod(0o755); (SAND / "refill.sh").chmod(0o755)
RT = tmp / "rt"; RT.mkdir()
SOCK = RT / "retronic-tstrefill.sock"
INST = SAND / "instancje" / "tstrefill"
srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
def ENV(**extra):
    e = {k: v for k, v in _os.environ.items() if k not in ("STUB_TRYB", "REFILL_KROKI", "REFILL_LOG_PRACY", "STUB_IGNORUJ_STOP")}
    e.update(RETRONIC_ID="tstrefill", XDG_RUNTIME_DIR=str(RT), PATH=f"{BIN}:{_os.environ['PATH']}",
             INST_STOP_STUB=str(INST / "STOP"), REFILL_CZEKAJ_STOP_S="1")
    e.update(extra)
    return e
def refill(*arg, **env):
    return subprocess.run(["bash", str(SAND / "refill.sh"), *arg], env=ENV(**env), capture_output=True, text=True, timeout=30)
def czekaj(warunek, s=8.0):
    koniec = time.time() + s
    while time.time() < koniec:
        if warunek():
            return True
        time.sleep(0.05)
    return warunek()
def log():
    try:
        return (INST / "refill.log").read_text()
    except OSError:
        return ""
def pidy(wzor, skrypt=False):
    return subprocess.run([sys.executable, "-I", str(SAND / "instancja.py"), "pidy-skrypt" if skrypt else "pidy", wzor],
                          env=ENV(), capture_output=True, text=True).stdout.split()
def posprzataj():
    for p in pidy(r"(^|[ /])serwis\.py ") + pidy(r"mozg\.py"):
        subprocess.run(["kill", "-KILL", p], capture_output=True)
    for p in pidy(r"^(\S*/)?bash (\S*/)?refill\.sh *$", skrypt=True):
        subprocess.run(["kill", "-KILL", "--", "-" + p], capture_output=True)

try:
    sprawdz("3a bash -n refill.sh", subprocess.run(["bash", "-n", str(KAT / "refill.sh")]).returncode == 0)
    sprawdz("3b skrypt wykonywalny", _os.access(KAT / "refill.sh", _os.X_OK))
    r = refill("--tlo")
    sprawdz("3c --tlo bez gry (brak socketu): odmowa, nic nie ruszyło", r.returncode == 1 and "brak socketu" in r.stderr
            and not (INST / "refill.log").exists())
    srv.bind(str(SOCK)); srv.listen(1)
    r = refill("--nieznane")
    sprawdz("3d nieznany argument: kod 2", r.returncode == 2)

    # sukces
    INST.mkdir(parents=True, exist_ok=True)
    (INST / "serwis_stan.json").write_text("{}")
    r = refill("--tlo", STUB_TRYB="ok")
    sprawdz("3e --tlo wraca od razu z kodem 0", r.returncode == 0 and "refill ruszył" in r.stdout, r.stderr[-200:])
    sprawdz("3f sukces: znacznik OK w logu", czekaj(lambda: "REFILL: OK" in log()), log())
    wyw = (tmp / "wywolania.txt").read_text()
    sprawdz("3g serwis.sh dostaje STARTUJ=1 i pełny serwis z bankiem i depo (Karol 22.10)",
            "serwis.sh STARTUJ=1 --kroki bank,depo,jedzenie,backpack,blanki,wyjscie" in wyw, wyw)
    sprawdz("3h sukces kasuje serwis_stan.json (następny refill nie pomija zakupów)", not (INST / "serwis_stan.json").exists())
    sprawdz("3i po sukcesie nic nie trwa", czekaj(lambda: not pidy(r"^(\S*/)?bash (\S*/)?refill\.sh *$", skrypt=True)))

    # porażka
    (INST / "serwis_stan.json").write_text('{"ukonczone": ["jedzenie"]}')
    r = refill("--tlo", STUB_TRYB="porazka")
    sprawdz("3j porażka: BLAD z powodem w logu", czekaj(lambda: "REFILL: BLAD blanki: brak miejsca w plecaku" in log()), log())
    sprawdz("3k porażka zostawia serwis_stan.json (wznowienie)", (INST / "serwis_stan.json").exists())
    sprawdz("3l porażka: dymek", "Błąd: blanki: brak miejsca" in (tmp / "powiadomienia.txt").read_text())
    sprawdz("3l2 porażka: dymek krytyczny (-u critical, przebija DND)", "-u critical" in (tmp / "powiadomienia.txt").read_text())
    st = panel.stan_serwisu(INST, dziala=False)
    sprawdz("3m panel czyta ten log: wynik blad + komunikat", st["serwis_wynik"] == "blad" and st["serwis_komunikat"].startswith("blanki:"), st)

    # trwa -> druga próba odmowa -> przerwij
    (tmp / "wywolania.txt").unlink()
    (INST / "STOP").unlink(missing_ok=True)
    r = refill("--tlo", STUB_TRYB="wisi")
    sprawdz("3n start serwisu, który wisi", r.returncode == 0 and czekaj(lambda: pidy(r"(^|[ /])serwis\.py ")))
    praca = pidy(r"^(\S*/)?bash (\S*/)?refill\.sh *$", skrypt=True)
    sprawdz("3o praca refill.sh widoczna dla wzoru panelu (tej instancji)", len(praca) == 1, praca)
    st = panel.stan_serwisu(INST)
    sprawdz("3p panel: serwis_dziala + krok z logu", st["serwis_dziala"] is True and czekaj(lambda: panel.stan_serwisu(INST)["serwis_krok"] == "jedzenie"))
    r2 = refill("--tlo", STUB_TRYB="wisi")
    sprawdz("3q druga próba w trakcie: odmowa", r2.returncode == 1 and "już działa" in r2.stderr)
    r3 = refill("--przerwij")
    sprawdz("3r --przerwij: kod 0", r3.returncode == 0, r3.stderr[-200:])
    sprawdz("3s po przerwaniu nic nie trwa (praca i serwis.py zabite)",
            czekaj(lambda: not pidy(r"(^|[ /])serwis\.py ") and not pidy(r"^(\S*/)?bash (\S*/)?refill\.sh *$", skrypt=True)))
    sprawdz("3t przerwanie: znacznik PRZERWANO i STOP", czekaj(lambda: "REFILL: PRZERWANO" in log()) and (INST / "STOP").exists(), log())
    wyw = (tmp / "wywolania.txt").read_text()
    sprawdz("3u kolejność: STOP -> serwis.py wychodzi SAM (bez TERM) -> zatrzymaj.sh -> zwolnienie wejścia",
            "serwis.py: wyszedł sam po STOP" in wyw and "TERM" not in wyw
            and wyw.index("wyszedł sam") < wyw.index("zatrzymaj") < wyw.index("zwolnij_wejscie"), wyw)
    sprawdz("3v po przerwaniu serwis.sh nie dostał kolejnego startu", wyw.count("serwis.sh") == 1)

    # serwis.py, który nie reaguje na STOP: dopiero po czekaniu TERM, zwolnienie wejścia nadal na końcu
    (tmp / "wywolania.txt").unlink(); (INST / "STOP").unlink(missing_ok=True)
    refill("--tlo", STUB_TRYB="wisi", STUB_IGNORUJ_STOP="1")
    czekaj(lambda: pidy(r"(^|[ /])serwis\.py "))
    t0 = time.time()
    refill("--przerwij", STUB_IGNORUJ_STOP="1")
    wyw = (tmp / "wywolania.txt").read_text()
    sprawdz("3w serwis ignorujący STOP: TERM dopiero po czekaniu, potem zatrzymaj.sh i zwolnienie wejścia",
            time.time() - t0 >= 0.9 and "serwis.py: TERM" in wyw and wyw.index("TERM") < wyw.index("zatrzymaj") < wyw.index("zwolnij_wejscie")
            and not pidy(r"(^|[ /])serwis\.py "), wyw)

    # bot działa, nic z refillu nie biegnie (klik w nieodświeżone „Przerwij” po udanym Refillu)
    (tmp / "wywolania.txt").unlink(); (INST / "STOP").unlink(missing_ok=True)
    bot = subprocess.Popen(["python3", "-I", str(SAND / "mozg.py")], env=ENV(), start_new_session=True)
    try:
        r = refill("--tlo", STUB_TRYB="ok")
        sprawdz("3x bot działa: --tlo odmawia", czekaj(lambda: pidy(r"mozg\.py")) and refill("--tlo", STUB_TRYB="ok").returncode == 1)
        r = refill("--przerwij")
        sprawdz("3y nic nie biegło: „nic do przerwania”, bot żyje, BEZ STOP, zatrzymaj.sh i zwolnienia nie wołano",
                r.returncode == 0 and "nic do przerwania" in r.stdout and bot.poll() is None and not (INST / "STOP").exists()
                and not (tmp / "wywolania.txt").exists(), r.stdout + str((tmp / "wywolania.txt").exists()))
    finally:
        bot.kill(); bot.wait()

    r = refill("--przerwij")
    sprawdz("3z --przerwij bez serwisu i bota: kod 0, bez STOP i bez zatrzymaj.sh",
            r.returncode == 0 and "nic do przerwania" in r.stdout and not (INST / "STOP").exists() and not (tmp / "wywolania.txt").exists())

    # stan przerwanego serwisu: świeży wznawia, starszy niż 15 min jest kasowany przy starcie --tlo
    for wiek_min, zostaje in ((3, True), (20, False)):
        (INST / "serwis_stan.json").write_text('{"ukonczone": ["jedzenie"]}')
        tt = time.time() - wiek_min * 60
        _os.utime(INST / "serwis_stan.json", (tt, tt))
        refill("--tlo", STUB_TRYB="porazka")
        czekaj(lambda: "REFILL: BLAD" in log())
        sprawdz(f"3za stan serwisu sprzed {wiek_min} min: {'zostaje (wznowienie)' if zostaje else 'kasowany (zakupy nie są po cichu pomijane)'}",
                (INST / "serwis_stan.json").exists() == zostaje)
        czekaj(lambda: not pidy(r"^(\S*/)?bash (\S*/)?refill\.sh *$", skrypt=True))
    # --spot: ta sama odłączona praca, tylko krok wyjscie (bez zakupów), znacznik START ze spot
    (tmp / "wywolania.txt").unlink(missing_ok=True); (INST / "STOP").unlink(missing_ok=True)
    r = refill("--spot", STUB_TRYB="ok")
    sprawdz("3zc --spot: kod 0 i OK w logu", r.returncode == 0 and czekaj(lambda: "REFILL: OK" in log()), log())
    wyw = (tmp / "wywolania.txt").read_text()
    sprawdz("3zd --spot: serwis.sh dostaje STARTUJ=1 i wyłącznie krok wyjscie", "serwis.sh STARTUJ=1 --kroki wyjscie --pomin-brakujace\n" in wyw
            and "jedzenie" not in wyw and "bank" not in wyw, wyw)
    sprawdz("3ze --spot: znacznik START z trybem spot", "REFILL: START" in log() and log().split("\n")[0].endswith(" spot"), log())
    (INST / "STOP").unlink(missing_ok=True)
    refill("--spot", STUB_TRYB="wisi")
    czekaj(lambda: pidy(r"(^|[ /])serwis\.py "))
    sprawdz("3zf panel w trakcie --spot: serwis_tryb spot, krok z logu", czekaj(lambda: panel.stan_serwisu(INST)["serwis_tryb"] == "spot"
            and panel.stan_serwisu(INST)["serwis_krok"] == "jedzenie"))   # krok z atrapy serwis.py, nie z REFILL_KROKI
    r = refill("--przerwij")
    sprawdz("3zg --przerwij przerywa także --spot", r.returncode == 0 and czekaj(lambda: not pidy(r"(^|[ /])serwis\.py ")))
    czekaj(lambda: not pidy(r"^(\S*/)?bash (\S*/)?refill\.sh *$", skrypt=True) and not pidy(r"(^|[ /])serwis\.py "))   # poprzednie przerwanie dogasa
    (INST / "STOP").unlink(missing_ok=True)
    refill("--tlo", STUB_TRYB="wisi")
    sprawdz("3zh zwykły refill: serwis_tryb refill", czekaj(lambda: panel.stan_serwisu(INST)["serwis_tryb"] == "refill"))
    refill("--przerwij")
    czekaj(lambda: not pidy(r"(^|[ /])serwis\.py "))
    # zwolnij_wejscie.py bez gry: cicho, kod 0
    rz = subprocess.run([sys.executable, "-I", str(KAT / "zwolnij_wejscie.py")], env=ENV(), capture_output=True, text=True, timeout=30)
    sprawdz("3zb zwolnij_wejscie.py bez gry: kod 0, bez wyjątku", rz.returncode == 0 and "Traceback" not in rz.stderr, rz.stderr[-200:])

    # ------------------------------------------------------------ 4. panel.py --json na atrapie gry
    def serwer(poz):
        def obsluga():
            while True:
                try:
                    c, _ = srv.accept()
                except OSError:
                    return
                with c:
                    try:
                        zad = json.loads(c.makefile("rb").readline())
                    except Exception:
                        continue
                    if zad.get("cmd") == "pozycja":
                        odp = {"ok": True, "pozycja": dict(zip("xyz", poz))}
                    elif zad.get("cmd") == "stwory":
                        odp = {"ok": True, "stwory": []}
                    else:
                        odp = {"ok": False, "blad": "?"}
                    c.sendall((json.dumps(odp) + "\n").encode())
        threading.Thread(target=obsluga, daemon=True).start()
    def panel_json(poz):
        env = ENV(RETRONIC_POSTAC="Test", PYTHONDONTWRITEBYTECODE="1")
        return json.loads(subprocess.run([sys.executable, "-I", str(KAT / "panel.py"), "--json"], env=env, capture_output=True,
                                         text=True, timeout=30).stdout.strip().splitlines()[0])
    serwer(EDRON_DEPO)
    j = panel_json(EDRON_DEPO)
    sprawdz("4a dotychczasowy kontrakt: text/tooltip/class/alt, gra jest, bot stoi", all(k in j for k in ("text", "tooltip", "class", "alt"))
            and j["class"] == "stop", j.get("class"))
    sprawdz("4b nowe pola: pozycja, w_miescie=edron, w_depo, plan_depo_dostepny",
            j["pozycja"] == list(EDRON_DEPO) and j["w_miescie"] == "edron" and j["w_depo"] is True and j["plan_depo_dostepny"] is True, j)
    sprawdz("4c nowe pola: wroc i serwis", j["wroc_oczekuje"] is False and j["wroc_w_marszu"] is False and j["serwis_dziala"] is False
            and "serwis_wynik" in j and "serwis_ukonczone" in j)
    srv.close(); SOCK.unlink()
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); srv.bind(str(SOCK)); srv.listen(1)
    serwer(GOBLINY)
    j = panel_json(GOBLINY)
    sprawdz("4d spot goblinów: poza miastem, plan depo jest", j["w_miescie"] is None and j["w_depo"] is False
            and j["plan_depo_dostepny"] is True)
    srv.close(); SOCK.unlink()
    j = panel_json(None)
    sprawdz("4e brak gry: klasa brak, pozycja i plan nieznane (None), kontrakt zachowany", j["class"] == "brak" and j["pozycja"] is None
            and j["plan_depo_dostepny"] is None and j["w_miescie"] is None)

    # 5. limit czasu pozycji jest TWARDY: wyjątek limitu nie może zostać połknięty przez `except Exception` w bot.wlasny_wpis
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); srv.bind(str(SOCK)); srv.listen(5)
    def wolny():                                            # "pozycja" odpowiada, "stwory" (rozstrzyganie widma) wisi
        while True:
            try:
                c, _ = srv.accept()
            except OSError:
                return
            try:
                zad = json.loads(c.makefile("rb").readline())
            except Exception:
                c.close(); continue
            if zad.get("cmd") == "pozycja":
                c.sendall((json.dumps({"ok": True, "pozycja": {"x": 1, "y": 2, "z": 7}}) + "\n").encode()); c.close()
            else:
                threading.Timer(4.0, c.close).start()
    threading.Thread(target=wolny, daemon=True).start()
    kod = ("import sys, time; sys.path.insert(0, %r); import panel; t = time.time(); r = panel.pozycja_postaci(limit_s=0.3); "
           "print(r, round(time.time() - t, 2))" % str(KAT))
    rp = subprocess.run([sys.executable, "-I", "-c", kod], env=ENV(RETRONIC_POSTAC="Test"), capture_output=True, text=True, timeout=30)
    wynik_p = rp.stdout.strip().split()
    sprawdz("5a wolne rozstrzyganie widma: limit 0,3 s twardy (None, nie wynik po połkniętym wyjątku)",
            wynik_p[:1] == ["None"] and float(wynik_p[-1]) < 0.9, rp.stdout + rp.stderr[-300:])
    srv.close(); SOCK.unlink()
finally:
    posprzataj()
    try:
        srv.close()
    except OSError:
        pass
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
