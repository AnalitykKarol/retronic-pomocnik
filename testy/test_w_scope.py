"""w_scope.sh (26.10): sesje gry i boty w WŁASNEJ jednostce systemd, nie w cgroupie okna/nadzoru/powłoki.
Incydent 26.10: `quickshell -p okno kill` zabił retronic-okno.service i razem z nim wszystkie sesje gry oraz boty (były jego potomkami).

Wyłącznie atrapy: `sleep` i fałszywy sesja.sh w katalogu tymczasowym, rodzic = przejściowa usługa testowa `retronic-test-rodzic-*`
(NIE prawdziwe okno). Instancja testowa `tscope<pid>`: nie istnieje w grze. Nic nie dotyka żywych sesji ani botów.
Bez menedżera usług użytkownika (systemd --user) część systemowa jest pomijana (SKIP), reszta idzie.
Uruchomienie: python3 -I testy/test_w_scope.py"""
import os, re, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path
sys.dont_write_bytecode = True
KAT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(KAT))
os.environ.pop("RETRONIC_TESTY", None)           # ten test sam sprawdza oba tryby; w procesie testu nie może ich maskować
os.environ.pop("RETRONIC_BEZ_SCOPE", None)
import instancja, sesja_gry                       # noqa: E402

WR = KAT / "w_scope.sh"
ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)

# ---------------------------------------------------------------- 1. czysta logika (bez systemd)
sprawdz("w_scope.sh wykonywalny, bash -n", os.access(WR, os.X_OK) and sh("bash", "-n", str(WR)).returncode == 0)
r = sh(str(WR))
sprawdz("bez argumentów: użycie, kod 2", r.returncode == 2 and "użycie" in r.stderr, (r.returncode, r.stderr))
r = sh(str(WR), "sesja")
sprawdz("sam rodzaj bez polecenia: kod 2", r.returncode == 2, r.returncode)
a = instancja.w_scope("sesja", ["/x/sesja.sh", 5], env={})
sprawdz("instancja.w_scope: [wrapper, rodzaj, polecenie...]", a == [str(KAT / "w_scope.sh"), "sesja", "/x/sesja.sh", "5"], a)
sprawdz("instancja.w_scope: RETRONIC_TESTY=1 -> bez owijania", instancja.w_scope("bot", ["a", "b"], env={"RETRONIC_TESTY": "1"}) == ["a", "b"])
sprawdz("instancja.w_scope: RETRONIC_BEZ_SCOPE=1 -> bez owijania", instancja.w_scope("bot", ["a"], env={"RETRONIC_BEZ_SCOPE": "1"}) == ["a"])

# sesja_gry.odlacz owija sesja.sh (rodzaj sesja) i Remminę (rodzaj podglad); w testach (RETRONIC_TESTY=1) nie
wyw = []
class _P:                                        # atrapa Popen: tylko zapamiętuje argv
    def __init__(self, argv, **k): wyw.append((argv, k.get("env"), k.get("start_new_session")))
oryg_popen = sesja_gry.subprocess.Popen
sesja_gry.subprocess.Popen = _P
try:
    sesja_gry.ID = "tscope"
    sesja_gry.odlacz(["/x/sesja.sh"], None, env={"RETRONIC_ID": "tscope"})
    sesja_gry.odlacz(["remmina", "-c", "p"], None, env={"RETRONIC_ID": "tscope"})
    sesja_gry.odlacz(["/x/sesja.sh"], None, env={"RETRONIC_ID": "tscope", "RETRONIC_TESTY": "1"})
finally:
    sesja_gry.subprocess.Popen = oryg_popen
sprawdz("sesja_gry.odlacz: sesja.sh w scope'ie rodzaju sesja (nowa sesja systemowa zostaje)",
        wyw[0][0] == [str(WR), "sesja", "/x/sesja.sh"] and wyw[0][2] is True, wyw[0])
sprawdz("sesja_gry.odlacz: Remmina w scope'ie rodzaju podglad", wyw[1][0] == [str(WR), "podglad", "remmina", "-c", "p"], wyw[1])
sprawdz("sesja_gry.odlacz: RETRONIC_TESTY=1 -> polecenie bez zmian", wyw[2][0] == ["/x/sesja.sh"], wyw[2])
for sk, wz in (("uruchom.sh", r'setsid nohup "\$DIR/w_scope\.sh" bot python3 -I -u mozg\.py'),
               ("uruchom_trolle.sh", r'setsid nohup "\$DIR/w_scope\.sh" bot python3 -I -u mozg\.py'),
               ("trade_start.sh", r'setsid nohup "\$DIR/w_scope\.sh" bot python3 -I -u mozg\.py'),
               ("obserwator_reczny.sh", r'setsid nohup "\$DIR/w_scope\.sh" obserwator python3'),
               ("refill.sh", r'setsid -f "\$DIR/w_scope\.sh" refill bash "\$DIR/refill\.sh"')):
    sprawdz(f"{sk}: proces odłączony przez wrapper", re.search(wz, (KAT / sk).read_text()) is not None)
sprawdz("relog_wylogowanych.py: kolejka przez instancja.w_scope", 'instancja.w_scope("kolejka"' in (KAT / "relog_wylogowanych.py").read_text())

# ---------------------------------------------------------------- 2. systemd --user: scope przeżywa stop rodzica
def jest_systemd():
    if not shutil.which("systemd-run"):
        return False
    r = sh("systemctl", "--user", "show", "-p", "Version", "--value")
    return r.returncode == 0 and r.stdout.strip() != ""

def cgroup(pid):
    try:
        return Path(f"/proc/{pid}/cgroup").read_text().strip().split("::", 1)[-1]
    except OSError:
        return ""

def zywy(pid):
    try:
        os.kill(pid, 0)
        return Path(f"/proc/{pid}/stat").read_text().split(")")[-1].split()[0] != "Z"
    except OSError:
        return False

def czekaj(warunek, limit=8.0):
    t = time.monotonic() + limit
    while time.monotonic() < t:
        w = warunek()
        if w:
            return w
        time.sleep(0.1)
    return None

if not jest_systemd():
    print("SKIP część systemd: brak systemd-run albo menedżera usług użytkownika")
else:
    TMP = Path(tempfile.mkdtemp(prefix="test-w-scope-"))
    ID = f"tscope{os.getpid()}"
    pidy, rodzice = [], []

    def start_rodzica(nazwa, env_dod, wnetrze):
        """Rodzic = przejściowa usługa testowa (jak okno): wnętrze (bash) startuje w tle polecenie przez wrapper i zapisuje $! do plików."""
        jedn = f"retronic-test-rodzic-{nazwa}-{os.getpid()}"
        rodzice.append(jedn)
        env = [f"--setenv={k}={v}" for k, v in {"RETRONIC_ID": ID, **env_dod}.items()]
        r = sh("systemd-run", "--user", "--quiet", "--collect", f"--unit={jedn}", *env, "--", "bash", "-c", wnetrze)
        return jedn, r

    def pid_z(plik):
        def f():
            try:
                t = (TMP / plik).read_text().strip()
                return int(t) if t else None
            except (OSError, ValueError):
                return None
        return czekaj(f)

    def stop(jedn):
        sh("systemctl", "--user", "stop", f"{jedn}.service")

    try:
        # --- A. wrapper: proces w osobnym scope'ie, cmdline/PID/środowisko jak bez wrappera, przeżywa stop rodzica
        jA, r = start_rodzica("a", {}, f'setsid nohup "{WR}" sesja sleep 300 > /dev/null 2>&1 < /dev/null & echo $! > "{TMP}/a.pid"; sleep 600')
        sprawdz("A0 rodzic testowy wystartował", r.returncode == 0, r.stderr)
        pa = pid_z("a.pid"); pidy.append(pa)
        sprawdz("A1 PID zapisany", pa is not None)
        if pa:
            cg = czekaj(lambda: (lambda c: c if re.search(r"/retronic-sesja-" + ID + r"-\d{6}\.scope$", c) else None)(cgroup(pa)))
            sprawdz("A2 cgroup procesu to retronic-sesja-<id>-<GGMMSS>.scope", cg is not None, cgroup(pa))
            sprawdz("A3 NIE w cgroupie rodzica", jA not in cgroup(pa), cgroup(pa))
            cmd = Path(f"/proc/{pa}/cmdline").read_bytes().split(b"\0")[:-1]
            sprawdz("A4 cmdline po exec = samo polecenie (pgrep -f i okno_api widzą jak dotąd), PID bez zmian", cmd == [b"sleep", b"300"], cmd)
            sprawdz("A5 środowisko zachowane (RETRONIC_ID dla skanu /proc)", instancja.id_procesu(pa) == ID, instancja.id_procesu(pa))
            sprawdz("A6 systemctl --user: scope aktywny", sh("systemctl", "--user", "is-active", Path(cgroup(pa)).name).stdout.strip() == "active")
            stop(jA)
            czekaj(lambda: not sh("systemctl", "--user", "is-active", f"{jA}.service").stdout.strip() == "active")
            time.sleep(0.5)
            sprawdz("A7 stop rodzica (jak restart okna) NIE zabił procesu", zywy(pa))
            sprawdz("A8 po stopie rodzica proces nadal w swoim scope'ie", re.search(r"retronic-sesja-" + ID, cgroup(pa)) is not None, cgroup(pa))

        # --- B. kontrola: ten sam rodzic z RETRONIC_BEZ_SCOPE=1 zostaje w cgroupie rodzica i ginie ze stopem (dowód, że A coś mierzy)
        jB, r = start_rodzica("b", {"RETRONIC_BEZ_SCOPE": "1"}, f'setsid nohup "{WR}" sesja sleep 300 > /dev/null 2>&1 < /dev/null & echo $! > "{TMP}/b.pid"; sleep 600')
        pb = pid_z("b.pid"); pidy.append(pb)
        if pb:
            time.sleep(0.4)
            sprawdz("B1 RETRONIC_BEZ_SCOPE=1: proces w cgroupie rodzica", jB in cgroup(pb), cgroup(pb))
            stop(jB)
            sprawdz("B2 ...i ginie ze stopem rodzica (tak było w incydencie)", czekaj(lambda: not zywy(pb), 6) is not None)

        # --- C. RETRONIC_TESTY=1: bez scope'a (atrapy testów nie wchodzą w prawdziwe jednostki)
        jC, r = start_rodzica("c", {"RETRONIC_TESTY": "1"}, f'"{WR}" sesja sleep 300 > /dev/null 2>&1 < /dev/null & echo $! > "{TMP}/c.pid"; sleep 600')
        pc = pid_z("c.pid"); pidy.append(pc)
        if pc:
            time.sleep(0.4)
            sprawdz("C1 RETRONIC_TESTY=1: proces zostaje w cgroupie rodzica", jC in cgroup(pc), cgroup(pc))
            stop(jC)

        # --- D. bez zagnieżdżania: wrapper wołany z wnętrza scope'a tego samego rodzaju i instancji nie tworzy kolejnego
        jD, r = start_rodzica("d", {}, f'setsid nohup "{WR}" sesja bash -c \'echo $$ > "{TMP}/d1.pid"; "{WR}" sesja sleep 300 & echo $! > "{TMP}/d2.pid"; wait\' > /dev/null 2>&1 < /dev/null & sleep 600')
        p1, p2 = pid_z("d1.pid"), pid_z("d2.pid"); pidy.extend([p1, p2])
        if p1 and p2:
            time.sleep(0.6)
            sprawdz("D1 powtórny wrapper w scope'ie tego samego rodzaju: ten sam scope (bez zagnieżdżania)", cgroup(p1) == cgroup(p2) and ".scope" in cgroup(p1), (cgroup(p1), cgroup(p2)))
        stop(jD)

        # --- E. okno_api.skan_sesji (odczyt /proc: cmdline + RETRONIC_ID) widzi sesja.sh w scope'ie; zamknięcie nie zależy od cgroupa
        # prawdziwy kształt: `bash <ścieżka>/sesja.sh` ze snem w pętli bash (bash zostaje, jak prawdziwy sesja.sh czekający na sway)
        d = TMP / "k"; d.mkdir()
        (d / "sesja.sh").write_text('#!/bin/bash\necho $$ > "' + str(TMP) + '/e.pid"\nsleep 300 &\nwait\n')
        (d / "sesja.sh").chmod(0o755)
        jE, r = start_rodzica("e", {}, f'setsid nohup "{WR}" sesja "{d}/sesja.sh" > /dev/null 2>&1 < /dev/null & sleep 600')
        pe = pid_z("e.pid"); pidy.append(pe)
        if pe:
            time.sleep(0.5)
            import okno_api
            _, _, skrypty = okno_api.skan_sesji(ID, proc="/proc")
            sprawdz("E1 okno_api.skan_sesji znajduje sesja.sh w scope'ie po cmdline+RETRONIC_ID", pe in skrypty, (pe, skrypty))
            sprawdz("E2 dziecko sesji (np. sway/Xwayland) dziedziczy ten sam scope",
                    any(cgroup(int(p)) == cgroup(pe) for p in os.listdir("/proc") if p.isdigit() and p != str(pe)
                        and Path(f"/proc/{p}/stat").exists() and Path(f"/proc/{p}/stat").read_text().split(")")[-1].split()[1] == str(pe)),
                    cgroup(pe))
            stop(jE)
            time.sleep(0.4)
            sprawdz("E3 po stopie rodzica sesja.sh dalej znajdowana", pe in okno_api.skan_sesji(ID, proc="/proc")[2])
            # zamknięcie jak sesja_gry/zamknij_sesje.sh: kill po PID z /proc, bez udziału jednostki
            os.kill(pe, signal.SIGTERM)
            sprawdz("E4 zamknięcie po PID (kill) działa na proces w scope'ie", czekaj(lambda: not zywy(pe), 6) is not None)
    finally:
        for jedn in rodzice:
            stop(jedn)
        for p in pidy:
            if p and zywy(p):
                try:
                    os.kill(p, signal.SIGKILL)
                except OSError:
                    pass
        # posprzątaj ewentualne sieroty-sleep po test-scope'ach (tylko nasze: RETRONIC_ID testowy)
        for p in os.listdir("/proc"):
            if p.isdigit() and instancja.id_procesu(int(p)) == ID:
                try:
                    os.kill(int(p), signal.SIGKILL)
                except OSError:
                    pass
        time.sleep(0.3)
        sprawdz("Z1 sprzątanie: brak jednostek testowych", sh("systemctl", "--user", "list-units", "--all", "--no-legend", f"retronic-*-{ID}*", f"retronic-test-rodzic-*-{os.getpid()}*").stdout.strip() == "",
                sh("systemctl", "--user", "list-units", "--all", "--no-legend", f"retronic-*{ID}*").stdout)
        shutil.rmtree(TMP, ignore_errors=True)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
