"""22.10: start z paska (RETRONIC_ID bez RETRONIC_POSTAC) po cichu pomijał dojście na spot (odchyd 17:41, kutangen 21.10).
uruchom.sh bierze nick z instancje/<id>/profil.json, a gdy piętra nadal nie zna, a mapa ma dojście, odmawia głośno.
Atrapy: strażnik (gniazdo unix, odpowiada tylko na znany nick), mozg.py, notify-send, obserwator. Bez gry i bez bota.
  python3 testy/test_uruchom_nick.py [ścieżka uruchom.sh]   (domyślnie uruchom.sh z repo; do dowodu na starej kopii)"""
import json, os, shutil, socket, subprocess, sys, tempfile, threading
from pathlib import Path
sys.dont_write_bytecode = True
R = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else R / "uruchom.sh"
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

NICK = "Testowanix"

def strazaq(sciezka, nick, z):
    """Atrapa strażnika: pozycja tylko dla znanego nicka (jak prawdziwy: dla obcego nicka brak pola `pozycja`)."""
    srv = socket.socket(socket.AF_UNIX); srv.bind(str(sciezka)); srv.listen(5); srv.settimeout(0.2)
    stop = threading.Event()
    def petla():
        while not stop.is_set():
            try:
                c, _ = srv.accept()
            except OSError:
                continue
            try:
                zad = json.loads(c.recv(400).decode())
                c.sendall((json.dumps({"pozycja": {"x": 1, "y": 2, "z": z}} if zad.get("nazwa") == nick else {"blad": "brak postaci"}) + "\n").encode())
            except Exception:
                pass
            c.close()
    t = threading.Thread(target=petla, daemon=True); t.start()
    return lambda: (stop.set(), t.join(2), srv.close())

def przebieg(mapa, z=7, id_="tst", postac_env=None, profil_postac=NICK, strazak_nick=NICK, tryb=""):
    with tempfile.TemporaryDirectory(prefix="uruchom_nick_") as td:
        T = Path(td) / "pom"; T.mkdir(); rt = Path(td) / "rt"; rt.mkdir(); bin_ = Path(td) / "bin"; bin_.mkdir()
        for f in ("instancja.py", "profil.py", "tryb.py", "pokretla.py", "mapy.json", "tryby.json", "w_scope.sh"):
            shutil.copy(R / f, T / f)
        shutil.copy(SRC, T / "uruchom.sh"); os.chmod(T / "uruchom.sh", 0o755)
        (T / "mozg.py").write_text("import sys,os\nopen(os.environ['ATRAPA_ARGS'],'w').write(' '.join(sys.argv[1:]))\n")
        (T / "obserwator_z_botem.sh").write_text("#!/bin/bash\nexit 0\n"); os.chmod(T / "obserwator_z_botem.sh", 0o755)
        (bin_ / "notify-send").write_text("#!/bin/bash\necho \"$@\" >> \"$ATRAPA_NOTIFY\"\n"); os.chmod(bin_ / "notify-send", 0o755)
        if id_:
            st = T / "instancje" / id_; st.mkdir(parents=True)
            prof = {"proxy": {"host": "h", "port": 80, "user": "u"}, "ip_oczekiwane": ["1.2.3.4"]}
            if profil_postac is not None:
                prof["postac"] = profil_postac
            (st / "profil.json").write_text(json.dumps(prof))
            gniazdo = rt / f"retronic-{id_}.sock"
        else:
            st = T; gniazdo = rt / "retronic-pomocnik.sock"
        (st / "STOP").write_text("")
        zamknij = strazaq(gniazdo, strazak_nick, z)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("RETRONIC_", "MAPA", "TRYB", "MOZG_"))}
        env["RETRONIC_TESTY"] = "1"  # w_scope.sh: atrapa bota nie trafia do prawdziwych jednostek systemd
        env.update(XDG_RUNTIME_DIR=str(rt), PATH=f"{bin_}:{os.environ['PATH']}", ATRAPA_ARGS=str(Path(td) / "args"),
                   ATRAPA_NOTIFY=str(Path(td) / "notify"), MAPA=mapa, TRYB=tryb, RETRONIC_CZEKAJ_POSTAC_S="2")   # 23.10: uruchom.sh czeka na strażnika (domyślnie 60 s)
        if id_:
            env["RETRONIC_ID"] = id_
        if postac_env:
            env["RETRONIC_POSTAC"] = postac_env
        try:
            r = subprocess.run(["bash", str(T / "uruchom.sh")], env=env, capture_output=True, text=True, timeout=60, cwd=str(T))
            import time; time.sleep(0.5)                # mozg.py-atrapa startuje odłączony
        finally:
            zamknij()
        args = Path(td, "args").read_text() if Path(td, "args").exists() else None
        notify = Path(td, "notify").read_text() if Path(td, "notify").exists() else ""
        return r.returncode, r.stdout, r.stderr, args, notify, (st / "STOP").exists()

M = "rook_raty_z8"                 # mapa z dojściem rook_raty_z8_dojscie (tylko ze z7)
kod, out, err, args, nt, stop = przebieg(M)
sprawdz("bez RETRONIC_POSTAC, z ID: nick z profilu -> dojście dodane", args and "--dojscie rook_raty_z8_dojscie" in args and "dojście" in out, (kod, args, err.strip()[-120:]))
kod, out, err, args, nt, stop = przebieg(M, postac_env=NICK)
sprawdz("jawny RETRONIC_POSTAC: dojście dodane jak dotąd", args and "--dojscie rook_raty_z8_dojscie" in args, (kod, args))
kod, out, err, args, nt, stop = przebieg(M, z=8)
sprawdz("postać na z8: start bez dojścia (to nie błąd)", kod == 0 and args and "--dojscie" not in args, (kod, args))
kod, out, err, args, nt, stop = przebieg(M, profil_postac=None)
sprawdz("profil bez nicka, mapa z dojściem: odmowa (kod != 0), bot nie startuje", kod != 0 and args is None, (kod, args))
sprawdz("odmowa: komunikat na stderr i notify-send z tytułem instancji", err.strip() and "[tst]" in nt, (err.strip()[-100:], nt.strip()))
sprawdz("odmowa nie kasuje pliku STOP", stop)
kod, out, err, args, nt, stop = przebieg(M, strazak_nick="Ktos Inny")
sprawdz("strażnik nie zna postaci (piętro puste): odmowa, bot nie startuje", kod != 0 and args is None and "[tst]" in nt, (kod, args))
kod, out, err, args, nt, stop = przebieg("rook_bugi_z8", profil_postac=None)
sprawdz("mapa BEZ dojścia i puste piętro (strażnik nie widzi postaci): 23.10 głośna odmowa po czekaniu, bot nie startuje (mozg.py i tak by odmówił)",
        kod == 3 and args is None and "[tst]" in nt and "ODMOWA STARTU" in err, (kod, args, err.strip()[-100:]))
kod, out, err, args, nt, stop = przebieg("rook_bugi_z10", profil_postac=None)
sprawdz("mapa z dojściem z dowolnego piętra i puste piętro (strażnik nie widzi postaci): 23.10 odmowa jak wyżej", kod == 3 and args is None, (kod, args))
kod, out, err, args, nt, stop = przebieg(M, id_="", strazak_nick="Jointoramix")
sprawdz("bez ID: domyślny Jointoramix zostaje", args and "--dojscie rook_raty_z8_dojscie" in args, (kod, args))
print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
