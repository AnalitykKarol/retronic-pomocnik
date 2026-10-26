"""zaloguj_postac.sh (24.10, akcja „Zaloguj postać" w oknie): loguje postać instancji BEZ startu bota.
Prawdziwy skrypt w katalogu tymczasowym z atrapami okno_api.py, sesja_gry.py i zaloguj.sh (tylko dziennik wywołań) i prawdziwym
instancja.py; atrapa /proc dla wykrywania cudzego logowania. Nic nie trafia do gry, sesji ani botów."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
DOM = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


OKNO_API = '''import json, sys
from pathlib import Path
d = Path(__file__).resolve().parent
# stan atrapy: stan_sesji.json; po „starcie" (sesja_gry.py) sesja_wstala.json ma pierwszeństwo
p = d / ("sesja_wstala.json" if (d / "sesja_wstala.json").exists() else "stan_sesji.json")
print(p.read_text())
'''
SESJA_GRY = '''#!/usr/bin/env python3
import os, sys
from pathlib import Path
d = Path(__file__).resolve().parent
with open(d / "wywolania.log", "a") as f:
    f.write("sesja_gry.py ID=%s ARGS=%s\\n" % (os.environ.get("RETRONIC_ID"), sys.argv[1:]))
kod = int((d / "sesja_gry_kod").read_text()) if (d / "sesja_gry_kod").exists() else 0
if kod == 0 and (d / "po_starcie.json").exists():
    (d / "sesja_wstala.json").write_text((d / "po_starcie.json").read_text())
print("sesja wystartowała (atrapa)" if kod == 0 else "start wstrzymany: profil (atrapa)")
sys.exit(kod)
'''
ZALOGUJ = '''#!/bin/bash
d="$(cd "$(dirname "$0")" && pwd)"
echo "zaloguj.sh ID=${RETRONIC_ID-<brak>} ARGS=[$*] fd9=$([ -e /proc/self/fd/9 ] && echo otwarty || echo zamkniety)" >> "$d/wywolania.log"
echo "log: ekran: enter_game"
echo "log: koniec"
exit "$(cat "$d/zaloguj_kod" 2>/dev/null || echo 0)"
'''


def sesja_json(zyje, ip):
    return json.dumps({"sesja": zyje, "klient_pids": [1] if zyje else [], "proxy_pids": [], "sesja_sh_pids": [],
                       "ip": None if ip is None else {"adres": "10.0.0.1", "zgodne": ip}})


def przebieg(id_, *, stan, po_starcie=None, zaloguj_kod=0, sesja_kod=0, profil=None, proc=None, limit=2, arg_id=True):
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        shutil.copy(DOM / "zaloguj_postac.sh", t / "zaloguj_postac.sh")
        shutil.copy(DOM / "instancja.py", t / "instancja.py")
        (t / "okno_api.py").write_text(OKNO_API)
        (t / "sesja_gry.py").write_text(SESJA_GRY)
        (t / "zaloguj.sh").write_text(ZALOGUJ)
        for n in ("zaloguj.sh", "zaloguj_postac.sh"):
            (t / n).chmod(0o755)
        (t / "stan_sesji.json").write_text(stan)
        if po_starcie:
            (t / "po_starcie.json").write_text(po_starcie)
        (t / "zaloguj_kod").write_text(str(zaloguj_kod))
        (t / "sesja_gry_kod").write_text(str(sesja_kod))
        (t / "wywolania.log").write_text("")
        if profil is not None:
            (t / "instancje" / id_).mkdir(parents=True)
            (t / "instancje" / id_ / "profil.json").write_text(json.dumps(profil))
        run = t / "run"
        run.mkdir()
        procdir = t / "proc"
        procdir.mkdir()
        for pid, (argv, env) in (proc or {}).items():
            (procdir / str(pid)).mkdir()
            (procdir / str(pid) / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
            (procdir / str(pid) / "environ").write_bytes(b"".join(f"{k}={v}\0".encode() for k, v in env.items()))
        e = dict(os.environ, XDG_RUNTIME_DIR=str(run), RETRONIC_OKNO_PROC=str(procdir), RETRONIC_ZALOGUJ_IP_LIMIT_S=str(limit),
                 RETRONIC_ZALOGUJ_KROK_S="0.2")
        e.pop("RETRONIC_ID", None)
        argv = ["bash", str(t / "zaloguj_postac.sh")] + ([id_] if arg_id else [])
        if not arg_id:
            e["RETRONIC_ID"] = id_
        r = subprocess.run(argv, capture_output=True, text=True, env=e, timeout=60, stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "", (t / "wywolania.log").read_text()


GRA_OK = sesja_json(True, True)

# 1. sesja już stoi, IP zgodne: tylko zaloguj.sh --reczny-ok z właściwym ID, zero startu sesji, fd blokady zamknięty w dziecku
kod, ost, log = przebieg("odchyd", stan=GRA_OK)
sprawdz("1a sesja stoi + IP zgodne: kod 0", kod == 0, (kod, ost))
sprawdz("1b woła zaloguj.sh --reczny-ok z RETRONIC_ID=odchyd", "zaloguj.sh ID=odchyd ARGS=[--reczny-ok]" in log, log)
sprawdz("1c NIE startuje sesji (sesja działa)", "sesja_gry.py" not in log, log)
sprawdz("1d blokada (fd 9) nie dziedziczona przez zaloguj.sh", "fd9=zamkniety" in log, log)
sprawdz("1e NIE woła uruchom.sh/mozg.py (brak w wywołaniach)", "uruchom" not in log and "mozg" not in log, log)

# 1f. ID z RETRONIC_ID zamiast argumentu
kod, ost, log = przebieg("kolanoth", stan=GRA_OK, arg_id=False)
sprawdz("1f ID ze zmiennej RETRONIC_ID", kod == 0 and "zaloguj.sh ID=kolanoth" in log, (kod, log))

# 2. sesja nie działa: start sesji (sesja_gry.py start z RETRONIC_ID), czekanie na IP, potem logowanie
kod, ost, log = przebieg("odchyd", stan=sesja_json(False, None), po_starcie=GRA_OK)
sprawdz("2a sesja stoi martwa: kod 0", kod == 0, (kod, ost))
sprawdz("2b najpierw sesja_gry.py start z RETRONIC_ID=odchyd", "sesja_gry.py ID=odchyd ARGS=['start']" in log, log)
sprawdz("2c potem zaloguj.sh --reczny-ok", log.index("sesja_gry.py") < log.index("zaloguj.sh ID=odchyd ARGS=[--reczny-ok]"), log)

# 3. IP spoza profilu: bez logowania, kod 24
kod, ost, log = przebieg("odchyd", stan=sesja_json(True, False))
sprawdz("3a IP spoza profilu: kod 24, komunikat", kod == 24 and "SPOZA profilu" in ost, (kod, ost))
sprawdz("3b zaloguj.sh NIE wołany", "zaloguj.sh" not in log, log)

# 4. brak potwierdzenia IP w limicie (sesja stoi, w logu brak linii): kod 25
kod, ost, log = przebieg("odchyd", stan=sesja_json(True, None), limit=1)
sprawdz("4a brak IP w limicie: kod 25", kod == 25 and "Brak potwierdzenia IP" in ost, (kod, ost))
sprawdz("4b zaloguj.sh NIE wołany", "zaloguj.sh" not in log, log)

# 5. start sesji odmówiony (profil nie przechodzi): kod 23, bez logowania
kod, ost, log = przebieg("odchyd", stan=sesja_json(False, None), sesja_kod=1)
sprawdz("5a start odmówiony: kod 23 z komunikatem sesja_gry", kod == 23 and "start wstrzymany" in ost, (kod, ost))
sprawdz("5b zaloguj.sh NIE wołany", "zaloguj.sh" not in log, log)

# 6. postać stracona: kod 21, zero wywołań
kod, ost, log = przebieg("dawajkesh", stan=GRA_OK, profil={"stracony": True})
sprawdz("6a stracona: kod 21", kod == 21 and "stracona" in ost, (kod, ost))
sprawdz("6b zero wywołań (ani sesja_gry, ani zaloguj.sh)", log == "", log)
kod, ost, log = przebieg("odchyd", stan=GRA_OK, profil={"postac": "Odchyd"})
sprawdz("6c profil bez `stracony`: loguje", kod == 0 and "zaloguj.sh" in log, (kod, log))

# 7. inne logowanie trwa (logowanie.py zaloguj innej instancji w /proc): kod 22, zero wywołań; to samo ID nie liczy się jako „inne"
inne = {4321: (["python3", "-I", "/x/logowanie.py", "zaloguj", "--reczny-ok"], {"RETRONIC_ID": "gerbor"})}
kod, ost, log = przebieg("odchyd", stan=GRA_OK, proc=inne)
sprawdz("7a cudze logowanie: kod 22 z nazwą instancji", kod == 22 and "gerbor" in ost, (kod, ost))
sprawdz("7b zero wywołań", log == "", log)
wlasne = {4321: (["python3", "-I", "/x/logowanie.py", "zaloguj"], {"RETRONIC_ID": "odchyd"})}
kod, ost, log = przebieg("odchyd", stan=GRA_OK, proc=wlasne)
sprawdz("7c proces logowania TEJ SAMEJ instancji nie blokuje (blokadę własną robi logowanie.py)", kod == 0, (kod, ost))
nie_logowanie = {4321: (["python3", "-I", "/x/logowanie.py", "stan-ekranu"], {"RETRONIC_ID": "gerbor"})}
kod, ost, log = przebieg("odchyd", stan=GRA_OK, proc=nie_logowanie)
sprawdz("7d `logowanie.py stan-ekranu` (tylko odczyt) nie blokuje", kod == 0, (kod, ost))

# 8. kody zaloguj.sh idą dalej z ludzkim zdaniem
for k, fragment in ((4, "ręczna gra"), (6, "zgon"), (7, "nierozpoznany"), (9, "INNĄ"), (1, "limicie")):
    kod, ost, log = przebieg("odchyd", stan=GRA_OK, zaloguj_kod=k)
    sprawdz(f"8 zaloguj.sh kod {k}: ten sam kod + zdanie z „{fragment}\"", kod == k and fragment in ost, (kod, ost))

# 9. złe użycie
kod, ost, log = przebieg("Zle Id!", stan=GRA_OK)
sprawdz("9a niepoprawne ID: kod 20", kod == 20, (kod, ost))
with tempfile.TemporaryDirectory() as t:
    shutil.copy(DOM / "zaloguj_postac.sh", Path(t) / "zaloguj_postac.sh")
    e = {k: v for k, v in os.environ.items() if k != "RETRONIC_ID"}
    r = subprocess.run(["bash", str(Path(t) / "zaloguj_postac.sh")], capture_output=True, text=True, env=e, timeout=20)
    sprawdz("9b brak ID (główna instancja): kod 20", r.returncode == 20, (r.returncode, r.stdout))

# 10. blokada flock trzymana przez inny proces: kod 22 (jedno logowanie naraz z okna)
with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    shutil.copy(DOM / "zaloguj_postac.sh", t / "zaloguj_postac.sh")
    (t / "run").mkdir()
    trzyma = subprocess.Popen(["flock", "-n", str(t / "run" / "retronic-zaloguj.lock"), "sleep", "20"])
    import time
    time.sleep(0.5)
    e = dict(os.environ, XDG_RUNTIME_DIR=str(t / "run"), RETRONIC_OKNO_PROC=str(t / "proc"))
    r = subprocess.run(["bash", str(t / "zaloguj_postac.sh"), "odchyd"], capture_output=True, text=True, env=e, timeout=20)
    trzyma.terminate()
    trzyma.wait()
    sprawdz("10 blokada zajęta przez inny proces: kod 22", r.returncode == 22 and "inne logowanie" in r.stdout, (r.returncode, r.stdout))

# 11. skrypt nie dotyka STOP/STOP_RECZNY ani bota (kontrola źródła)
src = (DOM / "zaloguj_postac.sh").read_text()
kod_skryptu = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
sprawdz("11 skrypt nie woła uruchom.sh/mozg.py/zatrzymaj.sh i nie kasuje STOP",
        not any(x in kod_skryptu for x in ("uruchom.sh", "mozg.py", "zatrzymaj.sh", "rm ", "rm -")), kod_skryptu[:200])

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
