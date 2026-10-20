"""Skan orbit (SPEC_orbity_straznik_1020 C): narzedzia/orbity.py na wycinku telemetrii K1 (Kutangen 20.10, orbita na z9 po upadku
w dziurę w pościgu) i na odcinku normalnego patrolu z tego samego pliku, plus syntetyczne przypadki brzegowe. Czysty Python."""
import json, subprocess, sys, tempfile
sys.dont_write_bytecode = True
from pathlib import Path
R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "narzedzia"))
import orbity

DANE = R / "testy" / "dane" / "orbity_k1.jsonl"
ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

class A:  # domyślne progi narzędzia
    min_s, pol, min_ruchow, min_cykl, powt, przed_s = 45, 6, 8, 4, 3, 60

# rozdziel wycinek: K1 (16:37:30-16:45:00) i patrol (17:30-17:40) — luka w czasie > 1 h
rek = [json.loads(l) for l in DANE.read_text().splitlines()]
t_luka = max(r["t"] for r in rek if r["t"] < rek[0]["t"] + 3600)
k1 = [r for r in rek if r["t"] <= t_luka]; patrol = [r for r in rek if r["t"] > t_luka]
sprawdz("wycinek: K1 i patrol niepuste", len(k1) > 300 and len(patrol) > 100, f"{len(k1)}/{len(patrol)}")

tmp = Path(tempfile.mkdtemp())
def zapisz(nazwa, rekordy):
    p = tmp / nazwa; p.write_text("".join(json.dumps(r) + "\n" for r in rekordy)); return p

# (a) K1 = 1 epizod, z9, wahadło, pościg i zmiana piętra tuż przed
ep = orbity.skanuj_plik(zapisz("telemetria-20261020.jsonl", k1), tmp, A)
sprawdz("K1: dokładnie 1 epizod", len(ep) == 1, str(len(ep)))
e = ep[0] if ep else {}
sprawdz("K1: piętro 9, <= 6 pól, >= 45 s, >= 8 ruchów", e.get("pietro") == 9 and e.get("pola", 99) <= 6 and e.get("czas_s", 0) >= 45 and e.get("ruchy", 0) >= 8,
        f"z{e.get('pietro')} pól {e.get('pola')} {e.get('czas_s')}s ruchów {e.get('ruchy')}")
sprawdz("K1: róg obszaru (32085,32196)", e.get("rog") == [32085, 32196], str(e.get("rog")))
sprawdz("K1: flaga wahadła, cykl >= 4 i >= 3 powtórzenia", e.get("wahadlo") and e.get("cykl", 0) >= 4 and e.get("powtorzen", 0) >= 3, f"{e.get('cykl')} x{e.get('powtorzen')}")
typy = {x["typ"] for x in e.get("przed", [])}
sprawdz("K1: przed epizodem poscig_start + poscig_koniec + zmiana_pietra", {"poscig_start", "poscig_koniec", "zmiana_pietra"} <= typy, str(sorted(typy)))
zm = [x for x in e.get("przed", []) if x["typ"] == "zmiana_pietra"]
sprawdz("K1: zmiana piętra z8->z9", zm and zm[0]["szczegol"].startswith("z8->z9"), str(zm))
sprawdz("K1: stany bez WALKA/LOOT", e and not ({"WALKA", "LOOT"} & set(e["stany"])), str(e.get("stany")))

# (b) normalny patrol = 0 epizodów
sprawdz("patrol: 0 epizodów", orbity.skanuj_plik(zapisz("telemetria-20261020.jsonl", patrol), tmp, A) == [])

# (c) CLI: --json, etykieta instancji z ścieżki względnej, wejście przez --katalog
(tmp / "instancje" / "kutangen" / "logi").mkdir(parents=True)
(tmp / "instancje" / "kutangen" / "logi" / "telemetria-20261020.jsonl").write_text(DANE.read_text())
(tmp / "logi").mkdir()
zapisz("x", [])
(tmp / "logi" / "telemetria-20261019.jsonl").write_text("".join(json.dumps(r) + "\n" for r in patrol))
wy = subprocess.run([sys.executable, "-I", str(R / "narzedzia" / "orbity.py"), "--katalog", str(tmp), "--json"], capture_output=True, text=True)
js = json.loads(wy.stdout) if wy.returncode == 0 else []
sprawdz("CLI --katalog --json: 1 epizod, instancja kutangen", len(js) == 1 and js[0]["instancja"] == "kutangen" and js[0]["wahadlo"], wy.stderr[-200:])
wy = subprocess.run([sys.executable, "-I", str(R / "narzedzia" / "orbity.py"), "--katalog", str(tmp), "--instancja", "glowna"], capture_output=True, text=True)
sprawdz("CLI --instancja glowna: brak epizodów", wy.returncode == 0 and "Brak epizodów" in wy.stdout, wy.stdout[:100])
wy = subprocess.run([sys.executable, "-I", str(R / "narzedzia" / "orbity.py"), "--katalog", str(tmp)], capture_output=True, text=True)
sprawdz("CLI tabela: WAHADŁO i 'tuż przed'", wy.returncode == 0 and "WAHADŁO" in wy.stdout and "tuż przed" in wy.stdout and "zmiana_pietra" in wy.stdout)
stary = Path(tempfile.mkdtemp()); (stary / "logi").mkdir()
(stary / "logi" / "telemetria-20200101.jsonl").write_text(DANE.read_text())
wy = subprocess.run([sys.executable, "-I", str(R / "narzedzia" / "orbity.py"), "--katalog", str(stary), "--dni", "30"], capture_output=True, text=True)
wy2 = subprocess.run([sys.executable, "-I", str(R / "narzedzia" / "orbity.py"), "--katalog", str(stary), "--dni", "99999"], capture_output=True, text=True)
sprawdz("CLI --dni: stary plik pominięty przy 30, wzięty przy 99999", "Brak epizodów" in wy.stdout and "WAHADŁO" in wy2.stdout)

# (d) syntetyki: kółko 5 pól bez wahadła-cyklu>=4? (cykl 5 jest cyklem) / stanie / walka w środku / za mało ruchów
def seria(pozycje, t0=1000.0, dt=1.0, stan="IDZ", sesja=1):
    return [{"typ": "probka", "t": t0 + k * dt, "poz": list(p), "stan": stan, "sesja": sesja} for k, p in enumerate(pozycje)]
kolo = [(10, 10, 8), (11, 10, 8), (12, 10, 8), (12, 11, 8), (11, 11, 8)] * 20
s = orbity.skanuj_plik(zapisz("telemetria-20261001.jsonl", seria(kolo)), tmp, A)
sprawdz("kółko 5 pól x20: epizod z wahadłem, cykl 5", len(s) == 1 and s[0]["wahadlo"] and s[0]["cykl"] == 5, str([(x["cykl"], x["powtorzen"]) for x in s]))
ab = [(10, 10, 8), (11, 10, 8)] * 60
s = orbity.skanuj_plik(zapisz("telemetria-20261002.jsonl", seria(ab)), tmp, A)
sprawdz("ping-pong 2 pola: epizod, ale bez wahadła (cykl < 4)", len(s) == 1 and not s[0]["wahadlo"])
stoi = seria([(10, 10, 8)] * 200)
sprawdz("stanie w miejscu: 0 epizodów", orbity.skanuj_plik(zapisz("telemetria-20261003.jsonl", stoi), tmp, A) == [])
walka = seria(kolo[:50]) + seria(kolo[:50], t0=1050.0, stan="WALKA")
sprawdz("walka przerywa epizod (50 s IDZ + 50 s WALKA): 1 epizod 49 s", len(orbity.skanuj_plik(zapisz("telemetria-20261004.jsonl", walka), tmp, A)) == 1)
spacer = seria([(10 + k, 10, 8) for k in range(100)])
sprawdz("marsz po prostej: 0 epizodów", orbity.skanuj_plik(zapisz("telemetria-20261005.jsonl", spacer), tmp, A) == [])
przerwa = seria(kolo[:30]) + seria(kolo[:30], t0=1100.0)
sprawdz("przerwa >= 20 s dzieli (2x30 s < 45 s): 0 epizodów", orbity.skanuj_plik(zapisz("telemetria-20261006.jsonl", przerwa), tmp, A) == [])
duzy = seria([(10 + (k // 3) % 100, 10, 8) for k in range(60000)], dt=0.5) + seria([(5, 5, 8)] * 50000, t0=40000.0)
import time; t = time.time(); orbity.skanuj_plik(zapisz("telemetria-20261007.jsonl", duzy), tmp, A)
sprawdz("110 tys. próbek skanuje się < 10 s (bez O(n^2))", time.time() - t < 10, f"{time.time() - t:.1f}s")

print(f"{sum(ok)}/{len(ok)}")
sys.exit(0 if all(ok) else 1)
