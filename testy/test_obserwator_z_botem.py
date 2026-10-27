#!/usr/bin/env python3
"""15.10 (SPEC D3 Q4): obserwator ręcznych przejęć startuje z botem (uruchom.sh) ; zatrzymaj.sh go NIE zatrzymuje (po STOP zapisuje grę Karola, recenzja 15.10).
Nic nie uruchamia naprawdę: podmieniony skrypt obserwatora (RETRONIC_OBSERWATOR_SKRYPT) tylko dopisuje argumenty do pliku."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
R = Path(__file__).resolve().parent.parent
wyniki = []


def sprawdz(nazwa, warunek, info=""):
    wyniki.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + (f"  {info}" if not warunek and info else ""))


tmp = Path(tempfile.mkdtemp())
slad = tmp / "slad.txt"
fake = tmp / "fake_obserwator.sh"
fake.write_text(f'#!/bin/bash\necho "$1" >> {slad}\necho "fake $1"\n')
fake.chmod(0o755)
psuty = tmp / "psuty.sh"
psuty.write_text('#!/bin/bash\necho boom >&2\nexit 7\n')
psuty.chmod(0o755)


def uruchom(arg, env_extra=None, usun=("RETRONIC_OBSERWATOR",)):
    env = {k: v for k, v in os.environ.items() if k not in usun}
    env["RETRONIC_OBSERWATOR_SKRYPT"] = str(fake)
    env.update(env_extra or {})
    return subprocess.run(["bash", str(R / "obserwator_z_botem.sh"), arg], env=env, capture_output=True, text=True, timeout=20)


def wywolania():
    return slad.read_text().split() if slad.exists() else []


# składnia skryptów
for sk in ("uruchom.sh", "zatrzymaj.sh", "obserwator_z_botem.sh", "obserwator_reczny.sh"):
    r = subprocess.run(["bash", "-n", str(R / sk)], capture_output=True, text=True)
    sprawdz(f"bash -n {sk}", r.returncode == 0, r.stderr)

# domyślnie włączony
r = uruchom("start")
sprawdz("start bez zmiennej: woła obserwatora z 'start'", wywolania() == ["start"] and r.returncode == 0, (wywolania(), r.stdout, r.stderr))
r = uruchom("stop")
sprawdz("stop: woła obserwatora z 'stop'", wywolania() == ["start", "stop"] and r.returncode == 0, wywolania())
# idempotencja po stronie wrappera: drugi start też woła skrypt (a ten sam sprawdza, czy działa) i kończy się 0
r = uruchom("start")
r = uruchom("start")
sprawdz("powtórny start: bez błędu (idempotencję zapewnia obserwator_reczny.sh: 'już działa')", r.returncode == 0)
# wyłączony
slad.unlink()
r = uruchom("start", {"RETRONIC_OBSERWATOR": "0"})
r2 = uruchom("stop", {"RETRONIC_OBSERWATOR": "0"})
sprawdz("RETRONIC_OBSERWATOR=0: ani start, ani stop nie ruszają obserwatora", wywolania() == [] and r.returncode == 0 and r2.returncode == 0)
r = uruchom("start", {"RETRONIC_OBSERWATOR": "1"})
sprawdz("RETRONIC_OBSERWATOR=1: start", wywolania() == ["start"])
# błąd obserwatora nie psuje bota
r = uruchom("start", {"RETRONIC_OBSERWATOR_SKRYPT": str(psuty)})
sprawdz("obserwator kończy się błędem: wrapper i tak zwraca 0", r.returncode == 0, r.returncode)
r = uruchom("start", {"RETRONIC_OBSERWATOR_SKRYPT": str(tmp / "nie_ma.sh")})
sprawdz("brak skryptu obserwatora: wrapper zwraca 0", r.returncode == 0)
r = uruchom("coś")
sprawdz("zły argument: zwraca 0, nie woła obserwatora", r.returncode == 0 and wywolania() == ["start"], wywolania())

# uruchom.sh / zatrzymaj.sh: wołają wrapper, po starcie bota / po zatrzymaniu
u = (R / "uruchom.sh").read_text().splitlines()
iu = [i for i, l in enumerate(u) if "obserwator_z_botem.sh" in l and not l.lstrip().startswith("#")]
ib = [i for i, l in enumerate(u) if "setsid nohup" in l and "mozg.py" in l]
sprawdz("uruchom.sh: 'obserwator_z_botem.sh start' po wystartowaniu bota", len(iu) == 1 and ib and iu[0] > ib[0] and u[iu[0]].strip().endswith("start"), (iu, ib))
z = (R / "zatrzymaj.sh").read_text()
sprawdz("zatrzymaj.sh: NIE zatrzymuje obserwatora (po STOP nagrywa przejęcia Karola)",
        "obserwator_z_botem.sh" not in "\n".join(l for l in z.splitlines() if not l.lstrip().startswith("#")))
sprawdz("wrapper wykonywalny", os.access(R / "obserwator_z_botem.sh", os.X_OK))

print(f"\n{sum(wyniki)}/{len(wyniki)} OK")
sys.exit(0 if all(wyniki) else 1)
