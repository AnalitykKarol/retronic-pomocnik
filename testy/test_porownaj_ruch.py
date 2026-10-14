"""R0c: narzedzia/porownaj_ruch.py na syntetycznej telemetrii (filtr szumu, metryki, okna, ruch_okno)."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import datetime, json, subprocess, sys, tempfile
sys.dont_write_bytecode = True
_katalog = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, _katalog + "/narzedzia")
from pathlib import Path
import porownaj_ruch as pr

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

T0 = datetime.datetime(2026, 10, 14, 12, 0).timestamp()
rek = []
def probka(t, x, stan="IDZ", z=8, ja=False, **kw):
    r = {"t": T0 + t, "typ": "probka", "stan": stan, "poz": [x, 100, z], "hp": 90, "stwory": [], **kw}
    if ja:
        r["stwory"] = [{"n": "Ja", "dx": 0, "dy": 0, "odl": 0, "hp": 90, "gracz": True}]
    rek.append(r)
def ev(t, typ, **d): rek.append({"t": T0 + t, "typ": typ, **d})

ev(0.5, "patrol_cel", id=1, x=110, y=100, droga=10, poz=[100, 100, 8])
for i in range(11):                         # 10 pól w 6 s: 0,6 s na pole (bez mapy krok_s = 0,6 -> pełny marsz)
    probka(i * 0.6, 100 + i)
ev(10.6, "patrol_wizyta", id=1, x=110, y=100, dotarl=True, powod="ok", dojscie_s=6.0, na_miejscu_s=4.0, zabicia_miejsce=0, zabicia_droga=0)
for i in range(5):                          # postój na miejscu: 4 s bez ruchu
    probka(6.6 + i, 110)
ev(20.0, "patrol_cel", id=2, x=120, y=100, droga=10, poz=[110, 100, 8])
ev(21.0, "pietra_start", z_od=8, z_do=9, idx=1, poz=[112, 100, 8])
probka(21.0, 112, z=8); probka(22.0, 112, z=8); probka(24.0, 112, z=9); probka(26.0, 112, z=8)
ev(23.0, "pietra_krok", z_od=8, z_do=9, poz=[112, 101, 9], proba=1, tryb="krok", czas_s=0.0)
ev(24.0, "pietra_start", z_od=9, z_do=8, idx=2, poz=[112, 101, 9])
ev(26.0, "pietra_krok", z_od=9, z_do=8, poz=[112, 100, 8], proba=2, tryb="R", czas_s=1.0)
ev(60.0, "patrol_wizyta", id=2, x=120, y=100, dotarl=True, powod="ok", dojscie_s=40.0, na_miejscu_s=1.0, zabicia_miejsce=0, zabicia_droga=0)
ev(30.0, "odpuszczenie", n="Troll", powod="za ścianą (droga naokoło: brak drogi)", odl=2, hp=10)
ev(31.0, "odpuszczenie", n="Troll", powod="zbyt daleko", odl=9, hp=10)
# szum: gracz Ja, src test, pietra_* bez próbki w +-3 s
probka(40.0, 5, ja=True)
rek.append({"t": T0 + 41.0, "typ": "info", "src": "test"})
ev(500.0, "pietra_krok", z_od=8, z_do=9, poz=[1, 1, 9], proba=1, tryb="krok", czas_s=0.0)
ev(70.0, "ruch_okno", okno_s=30.0, ticki=40, stany={"IDZ": [15.0, 10.0]}, powody_s={"schody": 6.0, "inne": 4.0},
   powody_idz_s={"schody": 6.0, "inne": 4.0}, luki=2, luki_s=5.0, luka_max=3.0, kroki=20, zmiany_pietra=1, kliki=7, strzalki=3)
rek.sort(key=lambda r: r["t"])

czyste, odrz = pr.filtruj_szum(rek)
sprawdz("1a filtr: odrzuca Ja, src=test i pietra bez próbki", odrz == {"src_test": 1, "gracz_Ja": 1, "pietra_bez_probki": 1}, odrz)
sprawdz("1b czyste nie zawierają szumu", not any(r.get("src") == "test" for r in czyste) and not any(
    r.get("typ") == "pietra_krok" and r["t"] == T0 + 500.0 for r in czyste))

m = pr.policz(czyste, T0, T0 + 600, [], None)
sprawdz("2a efektywny marsz (pełna prędkość na odcinku, reszta stoi)", m["marsz_efektywny"] is not None and 0.3 < m["marsz_efektywny"] < 1.0,
        m["marsz_efektywny"])
sprawdz("2b przejścia: 2 udane, 1 z pierwszej próby", m["przejscia"] == 2 and m["przejscia_pierwsza"] == 1
        and abs(m["przejscia_pierwsza_proc"] - 0.5) < 1e-9)
sprawdz("2c czas przejścia: (2 s + 2 s) / 2", m["przejscie_czas_sr"] == 2.0 and m["przejscie_czas_n"] == 2, m["przejscie_czas_sr"])
sprawdz("2d s na pole: bez schodów 0,6, ze schodami 4,0", abs(m["s_na_pole_zwykle"]["mediana"] - 0.6) < 1e-6
        and abs(m["s_na_pole_schody"]["mediana"] - 4.0) < 1e-6, (m["s_na_pole_zwykle"], m["s_na_pole_schody"]))
sprawdz("2e odpuszczenia za ścianą 1 z 2", m["odpuszczenia_za_sciana"] == 1 and m["odpuszczenia"] == 2)
sprawdz("2f postój na miejscu > 0", m["postoj_patrolu"] and m["postoj_patrolu"] > 0.1, m["postoj_patrolu"])
ro = m["ruch_okno"]
sprawdz("2g ruch_okno zagregowany", ro["okien"] == 1 and abs(ro["marsz_idz"] - 0.6) < 1e-9 and ro["luki"] == 2 and ro["kliki"] == 7
        and ro["stoi_idz_powody_s"] == {"inne": 4.0, "schody": 6.0}, ro)

# ogień: pole ognia 2 pola od odcinka, wpis z logu tuż przed oknem
og = [(T0 - 1, 8, {(103, 101)})]
mo = pr.policz(czyste, T0, T0 + 600, og, None)
sprawdz("3a ogień z logu daje liczbę (nie None), nie ujemną", mo["ogien_strata"] is not None and mo["ogien_strata"] >= 0 and mo["ogien_logi"])
sprawdz("3b bez logów ogień = 0 i flaga", m["ogien_strata"] == 0.0 and not m["ogien_logi"])

# okna i CLI
a, b = pr.parsuj_okno("2026-10-14T12:55-2026-10-14T13:55")
sprawdz("4a parsowanie okna", b - a == 3600.0)
try:
    pr.parsuj_okno("12:55-13:55"); zle = False
except ValueError:
    zle = True
sprawdz("4b zły format okna: błąd", zle)
kat = Path(tempfile.mkdtemp())
(kat / "telemetria-20261014.jsonl").write_text("\n".join(json.dumps(r) for r in rek) + "\nśmieci\n")
cmd = [sys.executable, "-I", _katalog + "/narzedzia/porownaj_ruch.py", "2026-10-14T12:00-2026-10-14T12:10",
       "2026-10-14T12:10-2026-10-14T12:20", "--logi", str(kat)]
w = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
sprawdz("4c CLI dwa okna: tabela z kolumnami A i B", w.returncode == 0 and "| Metryka | A | B | Cel po R1 |" in w.stdout, w.stderr[-300:])
w = subprocess.run(cmd[:-3] + ["--json", "--logi", str(kat)], capture_output=True, text=True, timeout=120)
try:
    dj = json.loads(w.stdout); okj = len(dj) == 1 and "przejscia" in dj[0]["metryki"]
except ValueError:
    okj = False
sprawdz("4d CLI --json", okj, w.stdout[:200])
w = subprocess.run([sys.executable, "-I", _katalog + "/narzedzia/porownaj_ruch.py"], capture_output=True, text=True, timeout=60)
sprawdz("4e brak argumentów: kod 2", w.returncode == 2)

print("WYNIK:", "OK" if all(ok) else "BŁĄD")
sys.exit(0 if all(ok) else 1)
