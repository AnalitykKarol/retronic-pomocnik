"""Instancje (instancja.py): ścieżki, identyfikacja procesów, zgodność wsteczna dla pustego RETRONIC_ID.
Offline, bez gry i X11 (RETRONIC_TESTY=1)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, subprocess, sys, tempfile
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import instancja

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

RT = Path("/run/user/1000")
# 1. puste ID = dzisiejsze ścieżki
s0 = instancja.sciezki("", RT, KAT, KAT.parent)
sprawdz("1a socket", s0.gniazdo == RT / "retronic-pomocnik.sock")
sprawdz("1b stan = katalog pomocnika, logi/", s0.stan == KAT and s0.logi == KAT / "logi")
sprawdz("1c na_zywo/uh_stan/STOP/STOP_RECZNY", s0.na_zywo == KAT / "na_zywo.json" and s0.uh_stan == KAT / "uh_stan.json"
        and s0.stop == KAT / "STOP" and s0.stop_reczny == KAT / "STOP_RECZNY")
sprawdz("1d tryb.log, straznik.log, mozg_pamiec, uciekanie", s0.tryb_log == KAT / "logi" / "tryb.log"
        and s0.straznik_log == KAT / "straznik.log" and s0.pamiec_mozgu == KAT / "mozg_pamiec.json"
        and s0.uciekanie == KAT / "uciekanie.json")
sprawdz("1e sesja, prefix, Retronic.log", s0.sesja == RT / "retronic-sesja" and s0.prefix == KAT.parent / "prefix"
        and s0.log_klienta == KAT.parent / "Retronic.log" and s0.gra == KAT.parent)
sprawdz("1f STOP_NAGRYWANIA i STOP_LECZENIE", s0.stop_nagrywania == KAT / "STOP_NAGRYWANIA" and s0.stop_leczenie == KAT / "STOP_LECZENIE")

# 2. niepuste ID
s2 = instancja.sciezki("dwa", RT, KAT, KAT.parent)
I = KAT / "instancje" / "dwa"
sprawdz("2a socket retronic-dwa.sock", s2.gniazdo == RT / "retronic-dwa.sock")
sprawdz("2b stan instancje/dwa, logi", s2.stan == I and s2.logi == I / "logi")
sprawdz("2c pliki stanu w katalogu instancji", s2.na_zywo == I / "na_zywo.json" and s2.uh_stan == I / "uh_stan.json"
        and s2.stop == I / "STOP" and s2.stop_reczny == I / "STOP_RECZNY" and s2.tryb_log == I / "logi" / "tryb.log")
sprawdz("2d prefix, gra, Retronic.log osobne", s2.prefix == I / "prefix" and s2.gra == I / "gra"
        and s2.log_klienta == I / "gra" / "Retronic.log")
sprawdz("2e sesja osobna", s2.sesja == RT / "retronic-sesja-dwa")
sprawdz("2f wspólne i zajete", s2.wspolne == KAT / "instancje" / "_wspolne" and s2.zajete == s2.wspolne / "zajete.json"
        and s0.zajete == s2.zajete)
s3 = instancja.sciezki("trzy", RT, KAT, KAT.parent)
sprawdz("2g dwie instancje nie dzielą żadnej ścieżki stanu", all(
    getattr(s2, k) != getattr(s3, k) for k in ("gniazdo", "stan", "logi", "na_zywo", "uh_stan", "stop", "stop_reczny",
                                                 "prefix", "gra", "sesja", "pamiec_mozgu", "uciekanie")))

# 3. walidacja ID
def zle(v):
    try:
        instancja.sprawdz_id(v); return False
    except ValueError:
        return True
sprawdz("3a złe ID odrzucone", all(zle(v) for v in ("../x", "a/b", "A", "x y", "_wspolne", "-a", "a" * 25, "ą")))
sprawdz("3b dobre ID", all(instancja.sprawdz_id(v) == v for v in ("a", "dwa", "k2", "a-b_c", "0")) and instancja.sprawdz_id("") == "")

# 4. identyfikacja procesów po environ
sprawdz("4a id_z_environ", instancja.id_z_environ(b"A=1\0RETRONIC_ID=dwa\0B=2\0") == "dwa"
        and instancja.id_z_environ(b"A=1\0B=2\0") == "" and instancja.id_z_environ(b"") == "")
tmp = Path(tempfile.mkdtemp())
def proces(pid, comm, cmd, env):
    d = tmp / str(pid); d.mkdir()
    (d / "comm").write_text(comm + "\n")
    (d / "cmdline").write_bytes(b"\0".join(c.encode() for c in cmd) + b"\0")
    (d / "environ").write_bytes(b"\0".join(e.encode() for e in env) + b"\0")
proces(101, "python3", ["python3", "-I", "-u", "mozg.py", "--tryb", "hybryda"], ["HOME=/x"])                       # domyślna
proces(102, "python3", ["python3", "-I", "-u", "mozg.py"], ["RETRONIC_ID=dwa", "HOME=/x"])                       # dwa
proces(103, "python3", ["python3", "cavebot.py", "troll_cave"], ["RETRONIC_ID=trzy"])
proces(104, "bash", ["bash", "-c", "echo mozg.py"], ["RETRONIC_ID=dwa"])                                        # nie python
proces(105, "python3", ["python3", "inny.py"], ["RETRONIC_ID=dwa"])
(tmp / "abc").mkdir()
sprawdz("4b domyślna widzi tylko swój bot", instancja.procesy(r"(mozg|cavebot)\.py", "", proc=str(tmp)) == [101])
sprawdz("4c dwa widzi tylko swój bot (nie powłokę z tekstem)", instancja.procesy(r"(mozg|cavebot)\.py", "dwa", proc=str(tmp)) == [102])
sprawdz("4d trzy", instancja.procesy(r"(mozg|cavebot)\.py", "trzy", proc=str(tmp)) == [103])
sprawdz("4e brak instancji = pusto", instancja.procesy(r"(mozg|cavebot)\.py", "cztery", proc=str(tmp)) == [])
# 4f. skrypty powłoki (refill.sh: comm to "bash" albo nazwa skryptu): comm=None, wzór kotwiczy interpreter
proces(106, "refill.sh", ["/bin/bash", "./refill.sh"], ["RETRONIC_ID=dwa"])
proces(107, "vim", ["vim", "refill.sh"], ["RETRONIC_ID=dwa"])
proces(108, "bash", ["bash", "/x/refill.sh", "--przerwij"], ["RETRONIC_ID=dwa"])
proces(109, "bash", ["bash", "/x/refill.sh"], ["RETRONIC_ID=trzy"])
RF = r"^(\S*/)?bash (\S*/)?refill\.sh *$"
sprawdz("4f praca refill.sh: tylko ta instancja, bez edytora i bez --przerwij",
        instancja.procesy(RF, "dwa", proc=str(tmp), comm=None) == [106] and instancja.procesy(RF, "trzy", proc=str(tmp), comm=None) == [109])
sprawdz("4g domyślny filtr comm bez zmian (powłoka dalej odpada)", instancja.procesy(r"refill\.sh", "dwa", proc=str(tmp)) == [])

# 5. moduły z RETRONIC_ID w podprocesie: ścieżki; bez ID: stare
KOD = r"""
import sys, json, os
sys.path.insert(0, %r)
import bot, pokretla, telemetria, cavebot, mozg, tryb, panel, instancja, obserwator_reczny, nagraj_trase, kalibracja_krokow
print(json.dumps({"stop": str(bot.STOP), "gniazdo": str(bot.GNIAZDO), "log_klienta": str(bot.LOG_KLIENTA),
  "na_zywo": str(pokretla.PLIK), "tele": str(telemetria.LOGI), "uh": str(cavebot.UH_STAN_PLIK),
  "ucieczka": str(cavebot.PLIK_UCIEKANIA), "znane": str(cavebot.PLIK_ZNANYCH), "mozg_logi": str(mozg.LOGI),
  "pamiec": str(mozg.PAMIEC), "panel_logi": str(panel.LOGI), "panel_sock": str(panel.GNIAZDO),
  "obs_logi": str(obserwator_reczny.LOGI), "obs_sock": str(obserwator_reczny.GNIAZDO),
  "nagr_stop": str(nagraj_trase.STOP_PLIK), "nagr_sock": str(nagraj_trase.GNIAZDO),
  "koord": cavebot.PATROL_KOORD}))
""" % str(KAT)
def import_w_podprocesie(id_):
    env = {k: v for k, v in _os.environ.items() if k != "RETRONIC_ID"}
    env["XDG_RUNTIME_DIR"] = "/run/user/1000"
    if id_:
        env["RETRONIC_ID"] = id_
    r = subprocess.run([sys.executable, "-I", "-c", KOD], env=env, capture_output=True, text=True, timeout=120)
    if r.returncode:
        print(r.stderr[-1500:])
        return None
    return json.loads(r.stdout.strip().splitlines()[-1])
d0 = import_w_podprocesie("")
sprawdz("5a import bez ID", d0 is not None)
if d0:
    sprawdz("5b bez ID: STOP, socket, log klienta jak dziś", d0["stop"] == str(KAT / "STOP")
            and d0["gniazdo"] == "/run/user/1000/retronic-pomocnik.sock" and d0["log_klienta"] == str(KAT.parent / "Retronic.log"))
    sprawdz("5c bez ID: na_zywo, telemetria, uh_stan, uciekanie, znane_pola", d0["na_zywo"] == str(KAT / "na_zywo.json")
            and d0["tele"] == str(KAT / "logi") and d0["uh"] == str(KAT / "uh_stan.json")
            and d0["ucieczka"] == str(KAT / "uciekanie.json") and d0["znane"] == str(KAT / "znane_pola.json"))
    sprawdz("5d bez ID: mozg, panel, obserwator, nagrywanie", d0["mozg_logi"] == str(KAT / "logi") and d0["pamiec"] == str(KAT / "mozg_pamiec.json")
            and d0["panel_logi"] == str(KAT / "logi") and d0["panel_sock"] == "/run/user/1000/retronic-pomocnik.sock"
            and d0["obs_logi"] == str(KAT / "logi") and d0["obs_sock"] == "/run/user/1000/retronic-pomocnik.sock"
            and d0["nagr_stop"] == str(KAT / "STOP_NAGRYWANIA") and d0["nagr_sock"] == "/run/user/1000/retronic-pomocnik.sock")
    sprawdz("5e koordynator domyślnie wyłączony", d0["koord"] == 0)
d2 = import_w_podprocesie("dwa")
sprawdz("5f import z ID", d2 is not None)
if d2:
    sprawdz("5g z ID: STOP, socket, log klienta", d2["stop"] == str(I / "STOP") and d2["gniazdo"] == "/run/user/1000/retronic-dwa.sock"
            and d2["log_klienta"] == str(I / "gra" / "Retronic.log"))
    sprawdz("5h z ID: na_zywo, telemetria, uh_stan, uciekanie", d2["na_zywo"] == str(I / "na_zywo.json") and d2["tele"] == str(I / "logi")
            and d2["uh"] == str(I / "uh_stan.json") and d2["ucieczka"] == str(I / "uciekanie.json"))
    sprawdz("5i z ID: znane_pola wspólne (wiedza o mapie)", d2["znane"] == str(KAT / "znane_pola.json"))
    sprawdz("5j z ID: mozg, panel, obserwator, nagrywanie", d2["mozg_logi"] == str(I / "logi") and d2["pamiec"] == str(I / "mozg_pamiec.json")
            and d2["panel_logi"] == str(I / "logi") and d2["panel_sock"] == "/run/user/1000/retronic-dwa.sock"
            and d2["obs_logi"] == str(I / "logi") and d2["nagr_stop"] == str(I / "STOP_NAGRYWANIA")
            and d2["nagr_sock"] == "/run/user/1000/retronic-dwa.sock")
bad = subprocess.run([sys.executable, "-I", str(KAT / "instancja.py"), "powloka"], env={"RETRONIC_ID": "../zle"}, capture_output=True, text=True)
sprawdz("5k zły RETRONIC_ID = błąd (kod != 0), nie ciche domyślne", bad.returncode != 0)
pw = subprocess.run([sys.executable, "-I", str(KAT / "instancja.py"), "powloka"], env={"RETRONIC_ID": "dwa", "XDG_RUNTIME_DIR": "/run/user/1000"},
                    capture_output=True, text=True)
sprawdz("5l powloka eksportuje INST_SOCK/INST_PREFIX", "export INST_SOCK=/run/user/1000/retronic-dwa.sock" in pw.stdout
        and f"export INST_PREFIX={I}/prefix" in pw.stdout and "export RETRONIC_ID=dwa" in pw.stdout)

# 6. środowisko dla procesów instancji
e = instancja.srodowisko("dwa", {"XDG_RUNTIME_DIR": "/run/user/1000", "PATH": "/bin"})
sprawdz("6 srodowisko: RETRONIC_ID i WINEPREFIX", e["RETRONIC_ID"] == "dwa" and e["WINEPREFIX"] == str(I / "prefix"))

# 7. port podglądu VNC: kolizja bazy z cksum (odchyd i dawajkesh oba 5952, 23.10) -> pierwszy wolny, deterministycznie
import shutil
def swiat():
    """Świeży atrapowy /proc i $XDG_RUNTIME_DIR."""
    w = Path(tempfile.mkdtemp(prefix="test-porty-"))
    (w / "proc" / "net").mkdir(parents=True); (w / "rt").mkdir()
    (w / "proc" / "net" / "tcp").write_text("  sl  local_address rem_address   st\n")
    return w
def slucha(w, port):
    with open(w / "proc" / "net" / "tcp", "a") as f:
        f.write(f"   0: 0100007F:{port:04X} 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1000        0 1 1 0\n")
def sesja_zapis(w, id_, port, sesja_sh=True, sway=False, pid=500):
    kat = w / "rt" / f"retronic-sesja-{id_}"; kat.mkdir(exist_ok=True)
    (kat / "vnc_port").write_text(str(port))
    d = w / "proc" / str(pid + len(list((w / "proc").iterdir())))
    d.mkdir()
    if sesja_sh:
        cmd, comm = ["/bin/bash", "./sesja.sh"], "sesja.sh"
    elif sway:
        cmd, comm = ["sway", "--unsupported-gpu", "-c", str(kat / "sway.conf")], "sway"
    else:
        return                                  # sesja martwa: został tylko vnc_port
    (d / "comm").write_text(comm + "\n")
    (d / "cmdline").write_bytes(b"\0".join(c.encode() for c in cmd) + b"\0")
    (d / "environ").write_bytes(f"RETRONIC_ID={id_}\0HOME=/x\0".encode())
def wolny(w, baza, ja):
    return instancja.wolny_port_podgladu(baza, ja, w / "rt", proc=str(w / "proc"))

w = swiat()
sprawdz("7a nic nie zajęte: baza", wolny(w, 5952, "odchyd") == 5952)
sesja_zapis(w, "dawajkesh", 5952)
sprawdz("7b port innej żywej sesji (sesja.sh + vnc_port, wayvnc jeszcze nie słucha) -> 5953", wolny(w, 5952, "odchyd") == 5953)
sprawdz("7c to samo wywołanie drugi raz daje to samo (deterministycznie)", wolny(w, 5952, "odchyd") == wolny(w, 5952, "odchyd") == 5953)
sprawdz("7d własny vnc_port nie liczy się jako zajęty (restart tej samej instancji)", wolny(w, 5952, "dawajkesh") == 5952)
slucha(w, 5953)
sprawdz("7e ktoś słucha na 5953 (obce wayvnc) -> 5954", wolny(w, 5952, "odchyd") == 5954)
sesja_zapis(w, "kutangen", 5954, sesja_sh=False, sway=True)
sprawdz("7f sesja rozpoznana po sway z jej sway.conf -> 5955", wolny(w, 5952, "odchyd") == 5955)
sesja_zapis(w, "martwa", 5955, sesja_sh=False)
sprawdz("7g stary vnc_port martwej sesji (brak procesów) nie blokuje portu", wolny(w, 5952, "odchyd") == 5955)
sprawdz("7h baza spoza zakresu wraca do początku zakresu", wolny(w, 1234, "odchyd") in range(5902, 5992) and wolny(w, 5901, "odchyd") >= 5902)
shutil.rmtree(w)

w = swiat(); sesja_zapis(w, "x", 5991)
sprawdz("7i zawijanie: zajęty koniec zakresu -> początek", wolny(w, 5991, "odchyd") == 5902)
shutil.rmtree(w)
w = swiat()
for pt in range(5902, 5992):
    slucha(w, pt)
sprawdz("7j zakres wyczerpany -> None (sesja.sh wraca do dawnej bazy)", wolny(w, 5952, "odchyd") is None)
shutil.rmtree(w)

# 7k. dwa starty jeden po drugim: rezerwacja zapisuje vnc_port, więc drugi widzi pierwszy mimo braku nasłuchu
w = swiat()
p1 = instancja.zarezerwuj_port_podgladu(5952, "dawajkesh", w / "rt" / "retronic-sesja-dawajkesh", w / "rt", proc=str(w / "proc"))
sesja_zapis(w, "dawajkesh", p1)                      # sesja.sh dawajkesha już żyje (vnc_port nadpisany tą samą wartością)
p2 = instancja.zarezerwuj_port_podgladu(5952, "odchyd", w / "rt" / "retronic-sesja-odchyd", w / "rt", proc=str(w / "proc"))
sprawdz("7k dwie instancje z tą samą bazą dostają różne porty, vnc_port zapisany",
        (p1, p2) == (5952, 5953) and (w / "rt" / "retronic-sesja-odchyd" / "vnc_port").read_text() == "5953", (p1, p2))
sesja_zapis(w, "odchyd", p2)
# 7l. CLI jak z sesja.sh: stdout = port, vnc_port zapisany, kod 0; wyczerpany zakres = kod 1
env = {"PATH": _os.environ.get("PATH", ""), "RETRONIC_ID": "trzy", "XDG_RUNTIME_DIR": str(w / "rt"), "RETRONIC_OKNO_PROC": str(w / "proc")}
r = subprocess.run([sys.executable, "-I", str(KAT / "instancja.py"), "port-podgladu", "5952", str(w / "rt" / "retronic-sesja-trzy")],
                   env=env, capture_output=True, text=True)
sprawdz("7l CLI port-podgladu: 5954 (5952, 5953 zajęte), vnc_port zapisany", r.returncode == 0 and r.stdout.strip() == "5954"
        and (w / "rt" / "retronic-sesja-trzy" / "vnc_port").read_text() == "5954", (r.returncode, r.stdout, r.stderr))
shutil.rmtree(w)
sprawdz("7m sesja.sh: składnia bash OK i woła port-podgladu tylko dla instancji bez RETRONIC_PODGLAD_PORT",
        subprocess.run(["bash", "-n", str(KAT / "sesja.sh")]).returncode == 0
        and 'port-podgladu "$PORT_DOM" "$STAN"' in (KAT / "sesja.sh").read_text()
        and '[ -n "${RETRONIC_PODGLAD_PORT:-}" ]' in (KAT / "sesja.sh").read_text())

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
