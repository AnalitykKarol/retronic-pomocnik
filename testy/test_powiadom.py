import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, tempfile, pathlib
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import powiadom, telemetria

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

class Zegar:
    t = 1000.0
    def __call__(s): return s.t
tmp = pathlib.Path(tempfile.mkdtemp())
def nowy(**k):
    z = Zegar(); wys = []
    return powiadom.Powiadamiacz(uruchom=wys.append, zegar=z, cisza=tmp / "cisza", watek=False, **k), z, wys

_os.environ.pop("RETRONIC_POWIADOMIENIA", None)
p, z, w = nowy()
sprawdz("1a pierwsze powiadomienie idzie z app-name Retronic", p.powiadom("A", "tresc") and w[0][:2] == ["-a", "Retronic"], w)
sprawdz("1b ten sam klucz w 60 s odrzucony", not p.powiadom("A", "x") and len(w) == 1)
z.t += 61
sprawdz("1c po 60 s znów przechodzi", p.powiadom("A", "x") and len(w) == 2)
sprawdz("1d inny klucz od razu", p.powiadom("B", "x", klucz="inny") and len(w) == 3)

p, z, w = nowy()
wyslane = 0
for i in range(30):
    z.t += 61
    wyslane += p.powiadom("T", "x", klucz=f"k{i}")
sprawdz("2a limit 20/h dla normal", wyslane == 20, wyslane)
sprawdz("2b critical poza limitem godzinowym", p.powiadom("C", "x", "critical", klucz="c1"))
z.t += 3600
sprawdz("2c po godzinie limit się zeruje", p.powiadom("T", "x", klucz="nowy"))
sprawdz("2d critical ma -u critical", any(a[a.index("-u") + 1] == "critical" for a in w))

p, z, w = nowy()
_os.environ["RETRONIC_POWIADOMIENIA"] = "0"
sprawdz("3a RETRONIC_POWIADOMIENIA=0 wycisza (także critical)", not p.powiadom("A", "x", "critical") and not w)
del _os.environ["RETRONIC_POWIADOMIENIA"]
(tmp / "cisza").write_text("")
sprawdz("3b plik cisza wycisza", not p.powiadom("A", "x") and not w)
(tmp / "cisza").unlink()
sprawdz("3c po usunięciu ciszy działa", p.powiadom("A", "x") and len(w) == 1)

def wywal(arg): raise OSError("brak notify-send")
p = powiadom.Powiadamiacz(uruchom=wywal, zegar=Zegar(), cisza=tmp / "cisza", watek=False)
try:
    r = p.powiadom("A", "x"); sprawdz("4a błąd notify-send nie wywraca", True)
except Exception as e:
    sprawdz("4a błąd notify-send nie wywraca", False, e)
try:
    r = p.powiadom(None, object(), "dziwna", None); sprawdz("4b dziwne argumenty nie wywracają", True)
except Exception as e:
    sprawdz("4b dziwne argumenty nie wywracają", False, e)
sprawdz("4c funkcja modułowa w testach nic nie wysyła", powiadom.powiadom("A", "x") is False)

p, z, w = nowy()
p.powiadom("D" * 500, "x\n" * 500)
sprawdz("5 tytuł i treść przycięte", len(w[0][-2]) <= 80 and len(w[0][-1]) <= 400 and "\n" not in w[0][-1])

# z_logu na atrapie modułu (obchodzimy guard testowy)
wys = []
orig = powiadom.powiadom
powiadom.powiadom = lambda t, c="", pil="normal", klucz=None: wys.append((t, c, pil, klucz)) or True
try:
    t = [5000.0]; zg = lambda: t[0]
    powiadom._obcy.clear(); powiadom._ostatnie.clear(); powiadom._brak_jedzenia[0] = False
    powiadom.z_logu("ALARM: gracz na ekranie: Bob, Ala", zg)
    powiadom.z_logu("ALARM: gracz na ekranie: Bob", zg)
    sprawdz("6a obcy gracz raz na 5 min na gracza", [x[1] for x in wys] == ["Bob", "Ala"], wys)
    t[0] += 301; powiadom.z_logu("ALARM: gracz na ekranie: Bob", zg)
    sprawdz("6b po 5 min znów", len(wys) == 3)
    wys.clear()
    powiadom.z_logu("ALARM: niskie HP 22%", zg)
    sprawdz("6c niskie HP = critical", wys and wys[0][2] == "critical", wys)
    wys.clear()
    powiadom.z_logu("Zjedzono: nic (brak jedzenia)", zg); powiadom.z_logu("Zjedzono: nic (brak jedzenia)", zg)
    sprawdz("6d brak jedzenia raz, bez critical", len(wys) == 1 and wys[0][2] == "normal", wys)
    wys.clear()
    t[0] += 1800; powiadom.z_logu("Zjedzono: nic (brak jedzenia)", zg)
    sprawdz("6d2 brak jedzenia: nie częściej niż raz na godzinę", not wys, wys)
    t[0] += 1900; powiadom.z_logu("Zjedzono: nic (brak jedzenia)", zg)
    sprawdz("6d3 po godzinie znów jedno", len(wys) == 1, wys)
    wys.clear()
    powiadom.z_logu("ALARM: niskie HP 21%", zg); t[0] += 15; powiadom.z_logu("ALARM: niskie HP 20%", zg)
    sprawdz("6d4 niskie HP: jedno powiadomienie na 5 min (bez pętli co 15 s)", len(wys) == 1, wys)
    wys.clear()
    powiadom.z_logu("Start: trasa 40 pkt, najbliższy 3, próg HP 40%, jedzenie=F1, potwory=['Rat']")
    sprawdz("6e start", wys and wys[0][0] == "Bot ruszył" and "Rat" in wys[0][1], wys)
    wys.clear()
    for l in ("Zatrzymano (plik STOP).", "Za dużo błędów z rzędu, przerywam.", "Koniec."):
        powiadom.z_logu(l)
    sprawdz("6f stop = critical, powód", len(wys) == 3 and all(x[2] == "critical" for x in wys) and "STOP" in wys[0][1], wys)
    wys.clear()
    powiadom.z_logu("Nowy cel: Rat (1,2) HP 100%"); powiadom.z_logu("")
    sprawdz("6g zwykłe linie ignorowane", not wys)

    # podsumowanie
    tele = telemetria.Telemetria(katalog=tmp, zegar=zg, zapis=False)
    pod = powiadom.Podsumowanie(zegar=zg, wyslij=lambda a, b: wys.append((a, b)))
    t[0] += 10
    tele.zdarzenie("zabicie", n="Rat", walka_s=3); tele.zdarzenie("loot", wynik="ok"); tele.zdarzenie("loot", wynik="brak_okna")
    tele.zdarzenie("odpuszczenie", n="Rat", powod="x", odl=1, hp=2)
    tele._zapisz({"t": t[0], "typ": "probka", "stan": "IDZ", "hp": 80, "stwory": [], "dbb": 0})
    tele._zapisz({"t": t[0] + 1, "typ": "probka", "stan": "JEDZENIE", "hp": 55, "stwory": [], "dbb": 0})
    wys.clear()
    sprawdz("7a przed 5 min cisza", not pod.tick(tele, {"exp": 100}) and not wys)
    t[0] += 300
    sprawdz("7b po 5 min podsumowanie", pod.tick(tele, {"exp": 400}) and len(wys) == 1, wys)
    tekst = wys[0][1] if wys else ""
    sprawdz("7c treść: zabicia, loot, odpuszczenia, HP min, jedzenie, exp/h",
            all(s in tekst for s in ("zabicia 1", "loot ok 1/brak_okna 1", "odpuszczenia 1", "HP min 55%", "jedzenie 1x", "exp/h")), tekst)
finally:
    powiadom.powiadom = orig

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
