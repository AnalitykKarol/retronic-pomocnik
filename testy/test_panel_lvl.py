"""panel.py --json: pola level / level_procent / podglad i wiersz HP z lvl w tooltipie (20.10, spec
wtyczka-paska/specs/2026-10-20-retronic-lvl-i-podglad.md), czytanie `gracz` także przy zatrzymanym bocie (Q3).
Wyłącznie atrapy: tymczasowy XDG_RUNTIME_DIR, fałszywy /proc (RETRONIC_PANEL_PROC), własne RETRONIC_ID. Nic nie dotyka gry ani bota.
Uruchomienie: python3 -I testy/test_panel_lvl.py"""
import os as _os
import tempfile
_TMP = tempfile.mkdtemp(prefix="test_panel_lvl_")
_os.environ.update(RETRONIC_TESTY="1", RETRONIC_ID="tstlvl", XDG_RUNTIME_DIR=_TMP)    # przed importem panel/instancja
import json, shutil, subprocess, sys
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
SESJA = Path(instancja.S.sesja)
PROC = TMP / "proc"
PUSTY = {"port": None, "otwarty": False, "pid": None}

def proces(pid, argv):
    d = PROC / str(pid); d.mkdir(parents=True)
    (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")

def reset():
    shutil.rmtree(PROC, ignore_errors=True)
    shutil.rmtree(SESJA, ignore_errors=True)
    PROC.mkdir(parents=True)
    for p in TMP.glob("*.sock"):
        p.unlink()

def port(n):
    SESJA.mkdir(parents=True, exist_ok=True)
    (SESJA / "vnc_port").write_text(str(n))

_os.environ["RETRONIC_PANEL_PROC"] = str(PROC)

# ---------------------------------------------------------------- 1. podglad_instancji
reset()
sprawdz("1a ścieżka sesji z instancji testowej (tmp), nie z prawdziwego runtime", str(SESJA).startswith(_TMP) and SESJA.name == "retronic-sesja-tstlvl", SESJA)
sprawdz("1b brak pliku portu: pusty podgląd", panel.podglad_instancji() == PUSTY, panel.podglad_instancji())
port("abc")
sprawdz("1c plik portu ze śmieciem: pusty podgląd", panel.podglad_instancji() == PUSTY)
port(5950)
sprawdz("1d port znany, brak vncviewera: otwarty False, pid None", panel.podglad_instancji() == {"port": 5950, "otwarty": False, "pid": None}, panel.podglad_instancji())
proces(300, ["vncviewer", "-RemoteResize=0", "127.0.0.1::5951"])
proces(301, ["vncviewer", "-RemoteResize=0", "127.0.0.1::59500"])
proces(302, ["/usr/bin/tail", "-f", "127.0.0.1::5950"])
sprawdz("1e viewer na innym porcie (też 59500 z tym samym prefiksem) i obcy proces z tym argumentem nie liczą się",
        panel.podglad_instancji() == {"port": 5950, "otwarty": False, "pid": None}, panel.podglad_instancji())
proces(310, ["/usr/bin/vncviewer", "-RemoteResize=0", "-ReconnectOnError=0", "127.0.0.1::5950"])
sprawdz("1f otwarty: pid vncviewera na porcie (basename argv[0], pełna ścieżka)", panel.podglad_instancji() == {"port": 5950, "otwarty": True, "pid": 310},
        panel.podglad_instancji())
proces(305, ["vncviewer", "127.0.0.1::5950"])
sprawdz("1g dwa viewery na jednym porcie: najniższy pid", panel.podglad_instancji()["pid"] == 305)
sprawdz("1h podmiana /proc argumentem (bez zmiennej)", panel.podglad_instancji(proc=str(TMP / "nie_ma")) == {"port": 5950, "otwarty": False, "pid": None})
sprawdz("1i podmiana katalogu sesji argumentem", panel.podglad_instancji(sesja=TMP / "inna") == PUSTY)

# ---------------------------------------------------------------- 2. poziom_gracza
sprawdz("2a level i procent", panel.poziom_gracza({"level": 37, "procent": 12.5}) == (37, 12.5))
sprawdz("2b level jako float z JSON -> int", panel.poziom_gracza({"level": 37.0, "procent": 0}) == (37, 0))
sprawdz("2c brak gracza / brak pól / śmieci -> (None, None)", panel.poziom_gracza(None) == (None, None) and panel.poziom_gracza({"hp": 1}) == (None, None)
        and panel.poziom_gracza({"level": "x", "procent": 3}) == (None, None) and panel.poziom_gracza({"level": True}) == (None, None))

# ---------------------------------------------------------------- 3. json_paska (stan podmieniony, bez gry)
STAN0 = lambda g: {"gra": True, "procesy": [], "log": None, "alarm": None, "tryb": None, "czas": None, "gracz": g, "ostatnie": [],
                   "zabicia": {}, "loot": {}, "czat": [], "decyzje": [], "dziala": False, "klasa": "stop"}
GRACZ = {"hp": 150, "max_hp": 200, "mana": 30, "max_mana": 60, "cap": 100.0, "exp": 5000, "level": 37, "procent": 42.5}
STARE = ("text", "tooltip", "class", "alt")

STAN_ORYG = panel.stan

def json_z(g, guziki=lambda s: {"pozycja": None}):
    panel.stan = lambda z_graczem=True: STAN0(g)
    panel.pola_guzikow = guziki
    return panel.json_paska()

reset(); port(5950); proces(310, ["vncviewer", "127.0.0.1::5950"])
j = json_z(GRACZ)
sprawdz("3a level, level_procent, podglad w JSON", j["level"] == 37 and j["level_procent"] == 42.5
        and j["podglad"] == {"port": 5950, "otwarty": True, "pid": 310}, j)
sprawdz("3b tooltip: HP a/b  mana c/d  lvl N (P%)", "HP 150/200  mana 30/60  lvl 37 (42.5%)" in j["tooltip"].splitlines(), j["tooltip"])
sprawdz("3c dotychczasowe pola bez zmian", all(k in j for k in STARE) and j["class"] == "stop" and j["text"].endswith("RT") and j["pozycja"] is None, j)
j = json_z(dict(GRACZ, procent=7.0))
sprawdz("3d procent jak w TUI ({:g}): 7.0 -> 7", "lvl 37 (7%)" in j["tooltip"], j["tooltip"])
j = json_z({k: v for k, v in GRACZ.items() if k not in ("level", "procent")})
sprawdz("3e gracz bez levelu: tooltip jak dawniej, level null", j["level"] is None and j["level_procent"] is None
        and "HP 150/200  mana 30/60" in j["tooltip"].splitlines() and "lvl" not in j["tooltip"], j["tooltip"])
j = json_z(None)
sprawdz("3f brak gracza: level null, brak wiersza HP", j["level"] is None and j["level_procent"] is None and "HP " not in j["tooltip"], j["tooltip"])
reset()
j = json_z(GRACZ)
sprawdz("3g brak sesji/portu: podglad pusty", j["podglad"] == PUSTY, j["podglad"])

def zepsuty(*a, **k):
    raise RuntimeError("kaboom")
ORYG = panel.podglad_instancji
panel.podglad_instancji = zepsuty
j = json_z(GRACZ)
sprawdz("3h awaria podglądu: pusty podgląd, reszta kontraktu (level, tooltip, stare pola) bez zmian",
        j["podglad"] == PUSTY and j["level"] == 37 and all(k in j for k in STARE) and "lvl 37 (42.5%)" in j["tooltip"], j)
panel.podglad_instancji = ORYG
j = json_z(GRACZ, guziki=zepsuty)
sprawdz("3i awaria pól guzików nie zabiera pól level/podglad", j["level"] == 37 and "podglad" in j and all(k in j for k in STARE), j)

# 2x: Remmina (20.10) — bez procesu vncviewer, otwarty = nawiązane połączenie z wayvnc (/proc/net/tcp, port lokalny, stan 01)
reset(); port(5950)
(PROC / "net").mkdir()
(PROC / "net" / "tcp").write_text("  sl  local_address rem_address   st\n   0: 0100007F:173E 00000000:0000 0A 0\n")
sprawdz("2x1 samo nasłuchiwanie wayvnc (stan 0A): podgląd zamknięty", panel.podglad_instancji(proc=str(PROC)) == {"port": 5950, "otwarty": False, "pid": None})
(PROC / "net" / "tcp").write_text("  sl  local_address rem_address   st\n   0: 0100007F:173E 00000000:0000 0A 0\n"
                                  "   1: 0100007F:173E 0100007F:B2C4 01 0\n   2: 0100007F:B2C4 0100007F:173E 01 0\n")
sprawdz("2x2 połączenie z portem wayvnc (Remmina): otwarty, bez pid", panel.podglad_instancji(proc=str(PROC)) == {"port": 5950, "otwarty": True, "pid": None})
(PROC / "net" / "tcp").write_text("  sl  local_address rem_address   st\n   1: 0100007F:173F 0100007F:B2C4 01 0\n")
sprawdz("2x3 połączenie z innym portem: zamknięty", panel.podglad_instancji(proc=str(PROC))["otwarty"] is False)

# ---------------------------------------------------------------- 4. stan(): gracz przy gnieździe gry także bez bota (Q3)
reset()
WYWOLANIA = []
panel.stan = STAN_ORYG
panel.gracz = lambda timeout=0.5: (WYWOLANIA.append(timeout), dict(GRACZ))[1]
panel.procesy_bota = lambda: []
sprawdz("4a pomocnicze: gniazdo tej instancji leży w tmp", str(panel.GNIAZDO).startswith(_TMP), panel.GNIAZDO)
panel.GNIAZDO.write_text("")
s = panel.stan(True)
sprawdz("4b gniazdo jest, bot nie działa: gracz odczytany, timeout 0.3 s", s["gra"] and not s["dziala"] and s["gracz"] == GRACZ and WYWOLANIA == [0.3], (s["gracz"], WYWOLANIA))
WYWOLANIA.clear()
s = panel.stan(False)
sprawdz("4c z_graczem=False: bez odczytu", s["gracz"] is None and not WYWOLANIA)
panel.GNIAZDO.unlink()
s = panel.stan(True)
sprawdz("4d brak gniazda: bez odczytu gracza", not s["gra"] and s["gracz"] is None and not WYWOLANIA)

# 4e-4i: nieudany odczyt przy zatrzymanym bocie wstrzymuje kolejne na GRACZ_BRAK_S (strażnik nie skanuje w kółko)
BRAK = TMP / "gracz_brak"
panel._plik_gracz_brak = lambda: BRAK
panel.GNIAZDO.write_text("")
WYNIK = [None]
panel.gracz = lambda timeout=0.5: (WYWOLANIA.append(timeout), WYNIK[0])[1]
WYWOLANIA.clear()
s = panel.stan(True)
sprawdz("4e bot stoi, odczyt nieudany: zapisany znacznik", s["gracz"] is None and WYWOLANIA == [0.3] and BRAK.exists())
s = panel.stan(True)
sprawdz("4f zaraz potem: bez odpytywania strażnika", WYWOLANIA == [0.3], WYWOLANIA)
panel.procesy_bota = lambda: [(123, "mozg.py")]
panel.czas_dzialania = lambda pid: 5
s = panel.stan(True)
sprawdz("4g bot działa: odczyt mimo znacznika (jak przed Q3)", WYWOLANIA == [0.3, 0.3], WYWOLANIA)
panel.procesy_bota = lambda: []
_os.utime(BRAK, (0, 0))                       # znacznik starszy niż GRACZ_BRAK_S
WYNIK[0] = dict(GRACZ)
s = panel.stan(True)
sprawdz("4h po GRACZ_BRAK_S: nowa próba, udana kasuje znacznik", WYWOLANIA == [0.3, 0.3, 0.3] and s["gracz"] == GRACZ and not BRAK.exists(), (WYWOLANIA, BRAK.exists()))
panel.GNIAZDO.unlink()

# ---------------------------------------------------------------- 5. panel.py --json jako proces (pełna ścieżka, atrapa /proc, bez gry)
reset(); port(5950); proces(310, ["vncviewer", "-RemoteResize=0", "127.0.0.1::5950"])
env = dict(_os.environ, RETRONIC_PANEL_PROC=str(PROC))
p = subprocess.run([sys.executable, "-I", str(KAT / "panel.py"), "--json"], capture_output=True, env=env, timeout=60, cwd=str(KAT))
try:
    d = json.loads(p.stdout)
except ValueError:
    d = {"surowe": p.stdout.decode(errors="replace"), "stderr": p.stderr.decode(errors="replace")}
sprawdz("5a panel.py --json: podglad z RETRONIC_PANEL_PROC, level null (brak gry), stare pola", p.returncode == 0
        and d.get("podglad") == {"port": 5950, "otwarty": True, "pid": 310} and d.get("level") is None and d.get("level_procent") is None
        and all(k in d for k in STARE) and d["class"] == "brak", d)

shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
