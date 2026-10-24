"""24.10 (przegląd): uruchom.sh czyści zmienne jednego refillu (REFILL_KROKI/TRYB/BEZ_WYJSCIA) przed startem bota, żeby cap (bank,wyjscie)
nie wyciekał do bota i jego następnych refilli. Atrapa mozg.py zapisuje, co dostała w środowisku; obca zmienna ma zostać.
Atrapy jak w test_uruchom_nick.py (strażnik, notify-send, obserwator). Bez gry i bez bota.
  python3 testy/test_uruchom_refill_env.py [ścieżka uruchom.sh]   (domyślnie uruchom.sh z repo; do dowodu na starej kopii)"""
import json, os, shutil, socket, subprocess, sys, tempfile, threading, time
from pathlib import Path
sys.dont_write_bytecode = True
R = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else R / "uruchom.sh"
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, "" if warunek else info)

NICK, ID = "Testowanix", "tstenv"

def straznik(sciezka, nick, z):
    srv = socket.socket(socket.AF_UNIX); srv.bind(str(sciezka)); srv.listen(5); srv.settimeout(0.2)
    stop = threading.Event()
    def petla():
        while not stop.is_set():
            try: c, _ = srv.accept()
            except OSError: continue
            try:
                zad = json.loads(c.recv(400).decode())
                c.sendall((json.dumps({"pozycja": {"x": 1, "y": 2, "z": z}} if zad.get("nazwa") == nick else {"blad": "brak postaci"}) + "\n").encode())
            except Exception: pass
            c.close()
    t = threading.Thread(target=petla, daemon=True); t.start()
    return lambda: (stop.set(), t.join(2), srv.close())

def przebieg(dodatkowe):
    """-> (kod, słownik zmiennych widzianych przez atrapę mozg.py albo None, gdy bot nie wystartował)."""
    with tempfile.TemporaryDirectory(prefix="uruchom_env_") as td:
        T = Path(td) / "pom"; T.mkdir(); rt = Path(td) / "rt"; rt.mkdir(); bin_ = Path(td) / "bin"; bin_.mkdir()
        for f in ("instancja.py", "profil.py", "tryb.py", "pokretla.py", "mapy.json", "tryby.json"):
            shutil.copy(R / f, T / f)
        shutil.copy(SRC, T / "uruchom.sh"); os.chmod(T / "uruchom.sh", 0o755)
        (T / "mozg.py").write_text("import os, json\nopen(os.environ['ATRAPA_ENV'], 'w').write(json.dumps({k: v for k, v in os.environ.items() "
                                   "if k.startswith(('REFILL_', 'OBCA_'))}))\n")
        (T / "obserwator_z_botem.sh").write_text("#!/bin/bash\nexit 0\n"); os.chmod(T / "obserwator_z_botem.sh", 0o755)
        (bin_ / "notify-send").write_text("#!/bin/bash\nexit 0\n"); os.chmod(bin_ / "notify-send", 0o755)
        st = T / "instancje" / ID; st.mkdir(parents=True)
        (st / "profil.json").write_text(json.dumps({"proxy": {"host": "h", "port": 80, "user": "u"}, "ip_oczekiwane": ["1.2.3.4"], "postac": NICK}))
        (st / "STOP").write_text("")
        zamknij = straznik(rt / f"retronic-{ID}.sock", NICK, 7)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("RETRONIC_", "MAPA", "TRYB", "MOZG_", "REFILL_", "OBCA_"))}
        env.update(XDG_RUNTIME_DIR=str(rt), PATH=f"{bin_}:{os.environ['PATH']}", ATRAPA_ENV=str(Path(td) / "env.json"),
                   MAPA="rook_raty_z8", RETRONIC_ID=ID, RETRONIC_CZEKAJ_POSTAC_S="2")
        env.update(dodatkowe)
        try:
            r = subprocess.run(["bash", str(T / "uruchom.sh")], env=env, capture_output=True, text=True, timeout=60, cwd=str(T))
            time.sleep(0.5)                                    # atrapa mozg.py startuje odłączona
        finally:
            zamknij()
        p = Path(td) / "env.json"
        return r.returncode, (json.loads(p.read_text()) if p.exists() else None), r.stderr.strip()[-120:]

kod, e, err = przebieg({"REFILL_KROKI": "bank,wyjscie", "REFILL_TRYB": "cap", "REFILL_BEZ_WYJSCIA": "1", "OBCA_ZMIENNA_TESTU": "zostaje"})
sprawdz("bot wystartował (atrapa mozg.py dostała środowisko)", kod == 0 and e is not None, (kod, err))
sprawdz("REFILL_KROKI/TRYB/BEZ_WYJSCIA odziedziczone z otoczenia nie trafiają do bota", e is not None and not any(k in e for k in ("REFILL_KROKI", "REFILL_TRYB", "REFILL_BEZ_WYJSCIA")), e)
sprawdz("obca zmienna zostaje (unset tylko trzech zmiennych refillu)", e is not None and e.get("OBCA_ZMIENNA_TESTU") == "zostaje", e)
kod, e, err = przebieg({"OBCA_ZMIENNA_TESTU": "zostaje"})
sprawdz("bez wycieku: bot startuje jak dotąd, obca zmienna zostaje", kod == 0 and e == {"OBCA_ZMIENNA_TESTU": "zostaje"}, (kod, e))
print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
