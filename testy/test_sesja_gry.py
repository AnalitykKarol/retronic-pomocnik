"""Sesja gry z okna (F4a): `okno_api.py sesja` i `sesja_gry.py start|zamknij|podglad`. Wyłącznie atrapy: katalog
tymczasowy z instancjami i profilami, fałszywe /proc, procesy i polecenia podmienione. Nic nie startuje ani nie zabija
prawdziwych procesów (RETRONIC_TESTY=1). Uruchomienie: python3 -I testy/test_sesja_gry.py"""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, shutil, signal, subprocess, sys, tempfile
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
import okno_api, sesja_gry
ORYG_URUCHOM, ORYG_ODLACZ = sesja_gry.uruchom, sesja_gry.odlacz

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

TMP = Path(tempfile.mkdtemp(prefix="test-sesja-gry-"))
R, PROC, RT = TMP / "pomocnik", TMP / "proc", TMP / "rt"
_os.environ.update(RETRONIC_OKNO_KATALOG=str(R), RETRONIC_OKNO_PROC=str(PROC), XDG_RUNTIME_DIR=str(RT))
_os.environ.pop("RETRONIC_POSTAC", None)

def profil(user, ip, postac="Postac", konto=""):
    return {"proxy": {"host": "p.example", "port": 80, "user": user}, "ip_oczekiwane": [ip], "konto": konto, "postac": postac}

def reset(profile=None):
    for p in (R, PROC, RT):
        shutil.rmtree(p, ignore_errors=True)
    for i in ("dwa", "dwa2", "trzy", "bez"):
        (R / "instancje" / i / "logi").mkdir(parents=True)
    (R / "instancje" / "_wspolne").mkdir()
    profile = profile if profile is not None else {"dwa": dict(profil("u-2", "1.1.1.2", "Dwojka"), haslo="TAJNE-HASLO"),
                                                   "trzy": profil("u-3", "1.1.1.3"), "dwa2": profil("u-22", "1.1.1.22")}
    for i, p in profile.items():
        (R / "instancje" / i / "profil.json").write_text(json.dumps(p))
    PROC.mkdir(); RT.mkdir()
    (R / "panel.py").write_text("print('{}')\n")

def proces(pid, argv, env=None):
    d = PROC / str(pid); d.mkdir()
    (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    (d / "environ").write_bytes(b"\0".join(f"{k}={v}".encode() for k, v in (env or {}).items()) + b"\0")

def usun(*pidy):
    for p in pidy:
        shutil.rmtree(PROC / str(p), ignore_errors=True)

def sock_sway(id_, pid):
    return str(RT / f"sway-ipc.1000.{pid}.sock")

def sesja_dzialajaca(id_, baza, port, bot=True, podglad=False):
    """sway (po ścieżce sway.conf), strażnik i bot (po RETRONIC_ID), siec_proxy.sh, opcjonalnie vncviewer. id_ "" = główna."""
    s = RT / (f"retronic-sesja-{id_}" if id_ else "retronic-sesja"); s.mkdir(parents=True, exist_ok=True)
    (s / "sway.conf").write_text("#"); (s / "vnc_port").write_text(str(port)); (s / "swaysock").write_text(sock_sway(id_, baza))
    (RT / (f"retronic-{id_}.sock" if id_ else "retronic-pomocnik.sock")).write_text("")
    proces(baza, ["sway", "--unsupported-gpu", "-c", str(s / "sway.conf")])
    proces(baza + 1, ["/bin/bash", str(R / "siec_proxy.sh"), "python3"], {"RETRONIC_ID": id_})
    proces(baza + 2, ["python3", "-I", str(R / "straznik.py"), "wine", "RetronicGL.exe"], {"RETRONIC_ID": id_})
    if bot:
        proces(baza + 3, ["python3", "-I", str(R / "mozg.py")], {"RETRONIC_ID": id_})
    if podglad:
        proces(baza + 4, ["vncviewer", "-RemoteResize=0", f"127.0.0.1::{port}"])

def cli(*args):
    env = dict(_os.environ); env.pop("RETRONIC_ID", None)
    p = subprocess.run([sys.executable, "-I", str(KAT / "okno_api.py"), *args], capture_output=True, env=env, timeout=30)
    try:
        return p.returncode, json.loads(p.stdout)
    except ValueError:
        return p.returncode, {"surowe": p.stdout.decode(errors="replace"), "stderr": p.stderr.decode(errors="replace")}

# ================= okno_api.py sesja =================
reset()
kod, d = cli("sesja", "--instancja", "bez")
sprawdz("S1 bez profilu: brak startu, powód w profilu", kod == 0 and d["profil"]["jest"] is False and not d["mozna_uruchomic"]
        and "profil.json" in (d["profil"]["blad"] or ""), d)
kod, d = cli("sesja", "--instancja", "dwa")
sprawdz("S2 profil ok, nic nie działa: start możliwy, zamknięcie nie", kod == 0 and d["mozna_uruchomic"] and not d["mozna_zamknac"]
        and d["profil"]["proxy"] == "p.example:80" and d["profil"]["postac"] == "Dwojka", d)
sprawdz("S2b dodatkowe pole z hasłem w profil.json nie wychodzi z `sesja`", "TAJNE-HASLO" not in json.dumps(d), d["profil"])
(R / "instancje" / "bez" / "profil.json").write_text("[1, 2]")
kod, d = cli("sesja", "--instancja", "bez")
sprawdz("S2c profil.json w złym kształcie: czysty błąd, nie traceback", kod == 0 and d["profil"]["blad"] and not d["mozna_uruchomic"], d)
reset({"dwa": profil("u-2", "1.1.1.2"), "trzy": profil("u-3", "1.1.1.2")})
kod, d = cli("sesja", "--instancja", "dwa")
sprawdz("S3 wspólne IP z inną instancją: start wstrzymany z nazwą instancji", not d["profil"]["start_mozliwy"] and not d["mozna_uruchomic"]
        and "trzy" in (d["profil"]["blad"] or ""), d["profil"])
reset()
sesja_dzialajaca("dwa", 100, 5950, podglad=True)
sesja_dzialajaca("trzy", 200, 5960)
kod, d = cli("sesja", "--instancja", "dwa")
sprawdz("S4 działająca sesja: sway/strażnik/bot/proxy tej instancji", d["sesja"] and d["sway_pids"] == [100] and d["klient_pids"] == [102]
        and d["bot"] and d["proxy"] and d["gra"], d)
sprawdz("S4b podgląd otwarty po porcie, zamknięcie możliwe, start nie", d["podglad"] == {"port": 5950, "otwarty": True, "pid": 104}
        and d["mozna_zamknac"] and not d["mozna_uruchomic"], d)
kod, d = cli("sesja", "--instancja", "trzy")
sprawdz("S4c druga instancja: swoje pidy, podgląd zamknięty", d["sway_pids"] == [200] and d["klient_pids"] == [202]
        and d["podglad"] == {"port": 5960, "otwarty": False, "pid": None}, d)
(RT / "retronic-sesja-trzy" / "sway.log").write_text(
    "00:00:01.000 [sway/main.c] Sway version 1.11\nprofil: UWAGA puste `konto`\n"
    "siec_proxy: IP wyjściowe \"9.9.9.9\" spoza profilu (1.1.1.3), NIE startuję\nErrors from xkbcomp are not fatal\n")
kod, d = cli("sesja", "--instancja", "trzy")
sprawdz("S5 IP spoza profilu z logu startu", d["ip"] == {"adres": "9.9.9.9", "zgodne": False}, d["ip"])
sprawdz("S5b log startu bez szumu sway/Xwayland", len(d["log_startu"]) == 2 and d["log_startu"][0].startswith("profil:"), d["log_startu"])
(RT / "retronic-sesja-trzy" / "sway.log").write_text("siec_proxy: IP wyjściowe 1.1.1.3 (zgodne z profilem)\n")
kod, d = cli("sesja", "--instancja", "trzy")
sprawdz("S5c IP zgodne", d["ip"] == {"adres": "1.1.1.3", "zgodne": True}, d["ip"])
(RT / "retronic-sesja-trzy" / "sway.log").write_text("siec_proxy: IP wyjściowe 1.1.1.3 (zgodne z profilem)\n" + "szum sway\n" * 20000)
kod, d = cli("sesja", "--instancja", "trzy")
sprawdz("S5d długi sway.log (linie startu na początku): IP nadal odczytane", d["ip"] == {"adres": "1.1.1.3", "zgodne": True}, d["ip"])
kod, d = cli("sesja", "--instancja", "")
sprawdz("S6 główna: bez profilu i bez akcji", kod == 0 and d["glowna"] and d["profil"] is None and not d["mozna_uruchomic"]
        and not d["mozna_zamknac"], d)
kod, d = cli("sesja")
sprawdz("S7 bez --instancja: błąd użycia", kod == 2 and d.get("ok") is False, d)

# ================= sesja_gry.py (podmienione procesy) =================
WYWOLANIA, ZABITE = [], []
sesja_gry.sleep = lambda s: None
sesja_gry.CZEKAJ_START_S = sesja_gry.CZEKAJ_ZAMKNIECIE_S = sesja_gry.CZEKAJ_TERM_S = 0.3

class Proc:
    def __init__(self, kod=None): self.kod = kod
    def poll(self): return self.kod

def odlacz_stub(efekt=None, kod=None):
    def f(argv, log, env=None):
        WYWOLANIA.append(("odlacz", [str(a) for a in argv], dict(env or sesja_gry.srodowisko())))
        if efekt: efekt()
        return Proc(kod)
    return f

def uruchom_stub(efekty=None):
    def f(argv, limit):
        argv = [str(a) for a in argv]
        WYWOLANIA.append(("uruchom", argv, sesja_gry.srodowisko()))
        for klucz, efekt in (efekty or {}).items():
            if klucz in " ".join(argv):
                efekt()
        return 0, ""
    return f

def zabij_stub(pid, sig):
    ZABITE.append((pid, sig)); usun(pid)

def akcja(id_, nazwa, **podmiany):
    WYWOLANIA.clear(); ZABITE.clear()
    sesja_gry.ID = id_
    sesja_gry.odlacz = podmiany.get("odlacz", odlacz_stub())
    sesja_gry.uruchom = podmiany.get("uruchom", uruchom_stub())
    sesja_gry.zabij = zabij_stub
    import io, contextlib
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        kod = sesja_gry.main([nazwa])
    return kod, b.getvalue()

reset()
kod, out = akcja("", "start")
sprawdz("G1 główna: odmowa, bez wywołań", kod == 1 and not WYWOLANIA, (kod, out))
kod, out = akcja("dwa", "restart")
sprawdz("G1b złe użycie = 2", kod == 2)

sesja_dzialajaca("dwa", 100, 5950)
kod, out = akcja("dwa", "start")
sprawdz("G2 start przy działającej sesji: odmowa, sesja.sh nie wołany", kod == 1 and "już działa" in out and not WYWOLANIA, (kod, out))

reset()
kod, out = akcja("bez", "start")
sprawdz("G3 start bez profilu: odmowa z powodem", kod == 1 and "profil" in out and not WYWOLANIA, (kod, out))

reset()
kod, out = akcja("dwa", "start", odlacz=odlacz_stub(efekt=lambda: sesja_dzialajaca("dwa", 100, 5950, bot=False)))
w = WYWOLANIA[0] if WYWOLANIA else ("", [], {})
sprawdz("G4 start: sesja.sh odłączony, kod 0", kod == 0 and w[1] == [str(R / "sesja.sh")] and "wystartowała" in out, (kod, out, WYWOLANIA))
sprawdz("G4b środowisko: RETRONIC_ID, WINEPREFIX instancji, RETRONIC_POSTAC z profilu",
        w[2].get("RETRONIC_ID") == "dwa" and w[2].get("WINEPREFIX") == str(R / "instancje" / "dwa" / "prefix")
        and w[2].get("RETRONIC_POSTAC") == "Dwojka", {k: w[2].get(k) for k in ("RETRONIC_ID", "WINEPREFIX", "RETRONIC_POSTAC")})
logi = list((R / "instancje" / "dwa" / "logi").glob("sesja-*.log"))
sprawdz("G4c nagłówek w logu akcji", len(logi) == 1 and "start z okna: dwa (postać Dwojka" in logi[0].read_text(), logi)

reset()
kod, out = akcja("dwa", "start", odlacz=odlacz_stub(kod=1))
sprawdz("G5 sesja.sh padł od razu: kod 1 z komunikatem", kod == 1 and "zakończył się od razu" in out, (kod, out))

reset()
sesja_dzialajaca("dwa", 100, 5950)
sesja_dzialajaca("trzy", 200, 5960)
kolejnosc = []
kod, out = akcja("dwa", "zamknij", uruchom=uruchom_stub({
    "zatrzymaj.sh": lambda: (kolejnosc.append("bot"), usun(103)),
    "swaymsg": lambda: (kolejnosc.append("sway"), usun(100, 101, 102))}))
sprawdz("G6 zamknij: bot przed sway, kod 0", kod == 0 and kolejnosc == ["bot", "sway"] and "zamknięta" in out, (kod, out, kolejnosc))
sw = [x for x in WYWOLANIA if x[1][:1] == ["swaymsg"]]
sprawdz("G6b swaymsg na gnieździe TEJ sesji", sw and sw[0][1] == ["swaymsg", "-s", sock_sway("dwa", 100), "exit"], sw)
ws = [x for x in WYWOLANIA if x[1][:1] == ["wineserver"]]
sprawdz("G6c wineserver -k z WINEPREFIX tej instancji", ws and ws[0][2].get("WINEPREFIX") == str(R / "instancje" / "dwa" / "prefix"),
        [(x[1], x[2].get("WINEPREFIX")) for x in ws])
sprawdz("G6d druga instancja nietknięta (procesy i brak TERM)", all((PROC / str(p)).exists() for p in (200, 201, 202, 203)) and not ZABITE, ZABITE)
sprawdz("G6e zatrzymaj.sh z RETRONIC_ID instancji", [x for x in WYWOLANIA if x[1][0].endswith("zatrzymaj.sh")][0][2].get("RETRONIC_ID") == "dwa")

reset()
sesja_dzialajaca("dwa", 100, 5950, bot=False)
sesja_dzialajaca("trzy", 200, 5960)
kod, out = akcja("dwa", "zamknij")                      # swaymsg nic nie daje -> awaryjny TERM
sprawdz("G7 awaryjnie TERM tylko strażnika, siec_proxy.sh i sway tej instancji", kod == 0 and sorted(p for p, _ in ZABITE) == [100, 101, 102]
        and all(s == signal.SIGTERM for _, s in ZABITE), (kod, out, ZABITE))
sprawdz("G7b bez bota: zatrzymaj.sh nie wołany", not [x for x in WYWOLANIA if x[1][0].endswith("zatrzymaj.sh")])
sprawdz("G7c druga instancja żyje", all((PROC / str(p)).exists() for p in (200, 202)))

# id z prefiksem (dwa vs dwa2) i główna: zamknięcie "dwa" nie może ich ruszyć
reset()
sesja_dzialajaca("dwa", 100, 5950, bot=False)
sesja_dzialajaca("dwa2", 300, 5970)
sesja_dzialajaca("", 400, 5901)
kod, out = akcja("dwa", "zamknij")                      # swaymsg nieskuteczny -> TERM
sprawdz("G10 dwa vs dwa2 i główna: TERM tylko procesów dwa", kod == 0 and sorted(p for p, _ in ZABITE) == [100, 101, 102], (kod, out, ZABITE))
sprawdz("G10b dwa2 i główna żyją", all((PROC / str(p)).exists() for p in (300, 301, 302, 303, 400, 401, 402, 403)))

# zostaje sam siec_proxy.sh po wyjściu sway: też musi zostać domknięty
reset()
sesja_dzialajaca("dwa", 100, 5950, bot=False)
kod, out = akcja("dwa", "zamknij", uruchom=uruchom_stub({"swaymsg": lambda: usun(100, 102)}))
sprawdz("G11 osierocony siec_proxy.sh tej instancji: TERM i sukces", kod == 0 and [p for p, _ in ZABITE] == [101], (kod, out, ZABITE))

# nic nie chce się zamknąć: kod 1 z listą
reset()
sesja_dzialajaca("dwa", 100, 5950, bot=False)
zabij_stub_oryg = zabij_stub
zabij_stub = lambda pid, sig: ZABITE.append((pid, sig))      # TERM bez skutku
kod, out = akcja("dwa", "zamknij")
zabij_stub = zabij_stub_oryg
sprawdz("G12 gra się nie zamyka: kod 1 i komunikat", kod == 1 and "nie zamknęła się" in out, (kod, out))

# stary plik swaysock (sway z innym pidem): bez swaymsg, od razu TERM
reset()
sesja_dzialajaca("dwa", 100, 5950, bot=False)
(RT / "retronic-sesja-dwa" / "swaysock").write_text(sock_sway("dwa", 999))
kod, out = akcja("dwa", "zamknij")
sprawdz("G13 swaysock nie należy do żywego sway: swaymsg nie wołany", kod == 0 and not [x for x in WYWOLANIA if x[1][0] == "swaymsg"], WYWOLANIA)

reset()
kod, out = akcja("główna", "start")
sprawdz("G14 RETRONIC_ID=główna: odmowa jak dla głównej", kod == 1 and "główna instancja" in out and not WYWOLANIA, (kod, out))

_os.environ["RETRONIC_POSTAC"] = "Obcy"
kod, out = akcja("dwa", "start", odlacz=odlacz_stub(efekt=lambda: sesja_dzialajaca("dwa", 100, 5950, bot=False)))
_os.environ.pop("RETRONIC_POSTAC")
sprawdz("G15 RETRONIC_POSTAC ze środowiska okna nie nadpisuje profilu", WYWOLANIA and WYWOLANIA[0][2].get("RETRONIC_POSTAC") == "Dwojka",
        WYWOLANIA[0][2].get("RETRONIC_POSTAC") if WYWOLANIA else None)

reset()
kod, out = akcja("dwa", "start")                        # sesja.sh żyje, sway nie wstaje w limicie
sprawdz("G16 sway nie wstał w limicie, sesja.sh żyje: kod 0 i informacja", kod == 0 and "jeszcze nie wstał" in out, (kod, out))

reset()
import fcntl as _f
(R / "instancje" / "dwa").mkdir(parents=True, exist_ok=True)
with open(R / "instancje" / "dwa" / "sesja_start.lock", "a") as _z:
    _f.flock(_z, _f.LOCK_EX)
    kod, out = akcja("dwa", "start")
sprawdz("G17 start w trakcie innego startu: odmowa bez sesja.sh", kod == 1 and "już trwa" in out and not WYWOLANIA, (kod, out))

reset()
sesja_dzialajaca("dwa", 100, 5950)
usun(100, 102, 103)                                     # został sam sesja.sh/siec_proxy? tu: siec_proxy.sh
kod, out = akcja("dwa", "start")
sprawdz("G18 start przy żywym siec_proxy.sh tej instancji: odmowa", kod == 1 and "już działa" in out and not WYWOLANIA, (kod, out))

# prawdziwe uruchom/odlacz na nieszkodliwym poleceniu: środowisko i osobna sesja
sesja_gry.ID = "dwa"
kod, wyj = ORYG_URUCHOM(["/bin/sh", "-c", 'echo "$RETRONIC_ID|$WINEPREFIX"'], 10)
sprawdz("R1 uruchom: RETRONIC_ID i WINEPREFIX instancji docierają do procesu", kod == 0 and wyj == f"dwa|{R / 'instancje' / 'dwa' / 'prefix'}", wyj)
kod, wyj = ORYG_URUCHOM(["/bin/sleep", "5"], 0.3)
sprawdz("R2 uruchom: limit czasu = kod 124", kod == 124, (kod, wyj))
with open(TMP / "odlacz.log", "w") as _l:
    pr = ORYG_ODLACZ(["/bin/sh", "-c", 'echo "$RETRONIC_ID"'], _l)
    pr.wait(10)
sprawdz("R3 odlacz: osobna sesja (setsid) i wyjście do logu", _os.getsid(pr.pid) == pr.pid if pr.poll() is None else
        (TMP / "odlacz.log").read_text().strip() == "dwa", (TMP / "odlacz.log").read_text())
pr2 = ORYG_ODLACZ(["/bin/sleep", "2"], subprocess.DEVNULL)
sprawdz("R3b odlacz: proces jest liderem nowej sesji", _os.getsid(pr2.pid) == pr2.pid)
pr2.kill(); pr2.wait()

reset()
kod, out = akcja("dwa", "zamknij")
sprawdz("G8 zamknij bez sesji: kod 0, bez wywołań", kod == 0 and not WYWOLANIA and not ZABITE, (kod, out))

kod, out = akcja("dwa", "podglad")
sprawdz("G9 podgląd bez sesji: odmowa", kod == 1 and not WYWOLANIA, (kod, out))
# --- podgląd w Remminie (decyzja Karola 20.10 ~19:00: „tak jak było na invincible”) ---
REM = TMP / "remmina"
_os.environ["RETRONIC_REMMINA_KATALOG"] = str(REM)
KLIENCI = []
sesja_gry.klienci_hyprland = lambda: list(KLIENCI)
LIMITY = []
def uruchom_z_limitem(kod_wyj):
    def f(argv, limit):
        LIMITY.append(limit); WYWOLANIA.append(("uruchom", [str(a) for a in argv], {})); return kod_wyj
    return f

shutil.rmtree(REM, ignore_errors=True)
sesja_dzialajaca("dwa", 100, 5950)                     # sesja, podgląd zamknięty, brak profilu Remminy
kod, out = akcja("dwa", "podglad")
prof = REM / "retronic-dwa.remmina"
sprawdz("G9b zamknięty: remmina --disable-toolbar -c profil, odłączona, z RETRONIC_ID", kod == 0 and "Remminie" in out and WYWOLANIA
        and WYWOLANIA[0][0] == "odlacz" and WYWOLANIA[0][1] == ["remmina", "--disable-toolbar", "-c", str(prof)]
        and WYWOLANIA[0][2].get("RETRONIC_ID") == "dwa", (kod, out, WYWOLANIA))
tekst = prof.read_text() if prof.exists() else ""
sprawdz("G9c brak profilu: utworzony z wzoru (port sesji, nazwa = tytuł okna, skalowanie, bez paska)",
        "server=127.0.0.1:5950" in tekst and "name=Retronic dwa" in tekst and "scale=1" in tekst and "disabletoolbar=1" in tekst and "keymap=Retronic Alt" in tekst, tekst)
prof.write_text(tekst.replace("name=Retronic dwa", "name=Moja Dwójka"))
kod, out = akcja("dwa", "podglad")
sprawdz("G9d istniejący profil Karola nie jest nadpisywany", "name=Moja Dwójka" in prof.read_text())

(PROC / "net").mkdir(exist_ok=True)
(PROC / "net" / "tcp").write_text("  sl  local_address rem_address   st\n   0: 0100007F:173E 0100007F:A1B2 01 0\n")   # 0x173E = 5950
KLIENCI[:] = [{"title": "Moja Dwójka", "class": "org.remmina.Remmina", "address": "0xabc", "pid": 900},
              {"title": "Moja Dwójka", "class": "chromium", "address": "0xzzz", "pid": 901}]
kod, out = akcja("dwa", "podglad", uruchom=uruchom_z_limitem((0, "ok")))
sprawdz("G9e otwarty (połączenie z wayvnc, okno Remminy z tytułem profilu): fokus po adresie, bez nowej Remminy",
        kod == 0 and "fokus na okno" in out and [w[0] for w in WYWOLANIA] == ["uruchom"]
        and WYWOLANIA[0][1] == ["hyprctl", "dispatch", 'hl.dsp.focus({ window = "address:0xabc" })'] and LIMITY == [5], (kod, out, WYWOLANIA))
kod, out = akcja("dwa", "podglad", uruchom=uruchom_z_limitem((0, "warning: =[C]:-1: hl.focus: window not found")))
sprawdz("G9f Hyprland 0.56 (kod 0 + warning, zmierzone 20.10): nieudany fokus = komunikat, kod 0", kod == 0 and "nie udał" in out, (kod, out))
kod, out = akcja("dwa", "podglad", uruchom=uruchom_z_limitem((127, "[Errno 2] No such file or directory: 'hyprctl'")))
sprawdz("G9g hyprctl nie działa: komunikat z kodem, bez nowej Remminy", kod == 0 and "kod 127" in out and [w[0] for w in WYWOLANIA] == ["uruchom"], (kod, out))
KLIENCI[:] = []
kod, out = akcja("dwa", "podglad")
sprawdz("G9h połączenie jest, ale okna Remminy nie ma (np. inna przeglądarka): otwiera Remminę", kod == 0 and WYWOLANIA and WYWOLANIA[0][0] == "odlacz", (kod, out, WYWOLANIA))
(PROC / "net" / "tcp").unlink()
proces(104, ["vncviewer", "-RemoteResize=0", "127.0.0.1::5950"])
KLIENCI[:] = [{"title": "WayVNC - TigerVNC", "class": "Vncviewer", "address": "0xvnc", "pid": 104}]
kod, out = akcja("dwa", "podglad", uruchom=uruchom_z_limitem((0, "ok")))
sprawdz("G9i stary podgląd vncviewer tej instancji: fokus na jego okno", WYWOLANIA and WYWOLANIA[0][1][-1] == 'hl.dsp.focus({ window = "address:0xvnc" })', WYWOLANIA)
KLIENCI[:] = []
(RT / "retronic-sesja-dwa" / "vnc_port").unlink()
kod, out = akcja("dwa", "podglad")
sprawdz("G9j sesja bez portu (wayvnc wstaje): odmowa bez Remminy", kod == 1 and "portu" in out and not WYWOLANIA, (kod, out))

shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
