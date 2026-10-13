import os as _os
import json, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import obserwator_reczny as O

ok = True
def sprawdz(opis, war):
    global ok
    print(("OK   " if war else "BŁĄD ") + opis); ok = ok and bool(war)

T0 = 1_800_000_000.0

def mob(i, dx, dy, hp=100, atak=False, bije=False, poz=(100, 100)):
    return {"id": i, "nazwa": "Rat", "x": poz[0] + dx, "y": poz[1] + dy, "z": 7, "hp": hp,
            "atakowany": atak, "bije_nas": bije}

def mig(poz=(100, 100), mobs=(), hp=100, exp=1000, cap=200):
    return {"poz": (poz[0], poz[1], 7), "hp_proc": hp, "hp": hp, "max_hp": 100, "exp": exp,
            "cap": cap, "mana": 0, "mobs": list(mobs), "inni_gracze": 0}

def bot(tryb="aktywny", stan="WALKA", cel=None, stop_r=False, poscig=False, zd=()):
    return {"tryb": tryb, "stan": stan if tryb in ("aktywny", "cichy") else None, "cel": cel,
            "akcja": None, "stop": False, "stop_reczny": stop_r, "poscig": poscig,
            "wiek_probki": 0.5, "zdarzenia": list(zd)}

def cel(i, hp=100, odl=1):
    return {"id": i, "nazwa": "Rat", "hp": hp, "odl": odl}

# 1) bot sam bije cel: zero epizodów
o = O.Obserwator()
for k in range(30):
    o.probka(T0 + k, mig(mobs=[mob(1, 1, 0, 100, True), mob(2, 3, 0)]), bot(cel=cel(1)))
sprawdz("bot bije swój cel: brak epizodu", o.ep is None and not o.gotowe)

# 2) Karol przełącza cel na inny stwór (bot dalej "ma" cel 1)
o = O.Obserwator()
for k in range(5):
    o.probka(T0 + k, mig(mobs=[mob(1, 1, 0, 100, True), mob(2, 0, 1, 40), mob(3, -1, 0, 100)]), bot(cel=cel(1)))
sprawdz("brak epizodu przy zgodnym celu", o.ep is None)
for k in range(5, 10):
    o.probka(T0 + k, mig(mobs=[mob(1, 1, 0, 100), mob(2, 0, 1, 40, True), mob(3, -1, 0, 100)], hp=90, exp=1005),
             bot(cel=cel(1)))
sprawdz("zmiana celu otwiera epizod", o.ep is not None and "zmiana_celu" in o.ep.powody)
for k in range(10, 30):
    o.probka(T0 + k, mig(mobs=[mob(1, 1, 0, 100, True)], exp=1005, hp=90), bot(cel=cel(1)))
sprawdz("epizod zamknięty po ciszy", o.ep is None and len(o.gotowe) == 1)
rec, tekst = o.gotowe[0]
sprawdz("tryb bot_aktywny", rec["tryb"] == "bot_aktywny")
sprawdz("2 cele, 1 zmiana", len(rec["cele"]) >= 2 and rec["zmian_celu"] >= 1)
sprawdz("najsłabszy stykający wykryty", any(c.get("najslabszy_stykajacy") and c["hp_start"] == 40 for c in rec["cele"]))
sprawdz("podsumowanie: zmiana celu na najsłabszego", "zmienił cel" in tekst and "najsłabszego stykającego" in tekst)
sprawdz("hp min zapisane", rec["hp"]["min"] == 90 and rec["exp_przyrost"] == 5)

# 3) ruch nie zlecony: stoi przy stykającym celu, a pozycja się zmienia (cofnięcie), 3 stykających
o = O.Obserwator()
poz = [100, 100]
def m3(p, bije=True):
    return mig(tuple(p), [mob(1, 1, 0, 100, True, bije, p), mob(2, 1, 1, 100, False, bije, p),
                          mob(3, 0, 1, 100, False, bije, p)], hp=70)
# mobs fixed in absolute coords: build from original position
def abs_mobs(p):
    return [dict(mob(1, 1, 0, 100, True, True), x=101, y=100),
            dict(mob(2, 1, 1), x=101, y=101, bije_nas=True),
            dict(mob(3, 0, 1), x=100, y=101, bije_nas=True)]
t = T0
o.probka(t, mig((100, 100), abs_mobs(None), hp=70), bot(cel=cel(1)))
for p in [(99, 100), (98, 100), (97, 100)]:
    t += 0.8
    o.probka(t, mig(p, abs_mobs(None), hp=65), bot(cel=cel(1, odl=2)))
sprawdz("ruch nie zlecony wykryty", o.ep is not None and "ruch_nie_zlecony" in o.ep.powody)
for k in range(15):
    t += 1
    o.probka(t, mig((97, 100), abs_mobs(None), hp=65), bot(cel=cel(1, odl=3)))
sprawdz("epizod zamknięty", len(o.gotowe) == 1)
rec, tekst = o.gotowe[0]
sprawdz("cofanie wykryte", rec["cofal_sie"] and rec["cofniecie_pol"] >= 2)
sprawdz("stykające maks 3", rec["moby"]["stykajace_max"] == 3 or rec["moby"]["stykajace_start"] == 3)
sprawdz("podsumowanie o cofnięciu", "cofnął się" in tekst or "uciekał" in tekst)

# 4) ruch zlecony (IDZ / pościg / dochodzenie do celu) nie jest pomocą
o = O.Obserwator()
for k in range(10):
    o.probka(T0 + k, mig((100 + k, 100)), bot(stan="IDZ"))
sprawdz("IDZ: brak epizodu", o.ep is None)
o = O.Obserwator()
for k in range(10):
    o.probka(T0 + k, mig((100 + k, 100), [mob(1, 5, 0, 30, True, poz=(100 + k, 100))]),
             bot(stan="WALKA", cel=cel(1, 30, 5), poscig=True))
sprawdz("pościg: brak epizodu", o.ep is None)

# 5) STOP_RECZNY + ruch przy zatrzymanym bocie
o = O.Obserwator()
o.probka(T0, mig(), bot())
o.probka(T0 + 1, mig(), bot(tryb="zatrzymany", stop_r=True))
sprawdz("STOP_RECZNY otwiera epizod", o.ep is not None and "stop_reczny" in o.ep.powody)
sprawdz("zdarzenie stop_reczny", any(z["zdarzenie"] == "stop_reczny_pojawil_sie" for z in o.zdarzenia))
for k in range(2, 12):
    o.probka(T0 + k, mig((100 + k, 100), hp=80), bot(tryb="zatrzymany", stop_r=True))
for k in range(12, 40):
    o.probka(T0 + k, mig((112, 100), hp=85), bot(tryb="zatrzymany", stop_r=True))
sprawdz("epizod przy zatrzymanym bocie zapisany", len(o.gotowe) == 1 and o.gotowe[0][0]["tryb"] == "bot_zatrzymany")
sprawdz("przeszedł 11 pól", o.gotowe[0][0]["przeszedl_pol"] == 11)

# 6) brak bota: gra ręczna, jedzenie (cap w górę), kolejność celów
o = O.Obserwator()
t = T0
for k in range(6):
    t += 1
    o.probka(t, mig((100 + k, 100), [mob(1, 1, 0, 100, True, poz=(100 + k, 100))], exp=1000), bot(tryb="brak"))
sprawdz("gra ręczna otwiera epizod", o.ep is not None and o.ep.tryb == "brak_bota")
t += 1
o.probka(t, mig((105, 100), [mob(2, 1, 0, 60, True, poz=(105, 100))], exp=1005, cap=190), bot(tryb="brak"))
t += 1
o.probka(t, mig((105, 100), [mob(2, 1, 0, 40, True, poz=(105, 100))], exp=1005, cap=195), bot(tryb="brak"))
for k in range(20):
    t += 1
    o.probka(t, mig((105, 100), exp=1010, cap=195), bot(tryb="brak"))
sprawdz("gra ręczna zapisana", len(o.gotowe) == 1)
rec, tekst = o.gotowe[0]
sprawdz("tryb brak_bota", rec["tryb"] == "brak_bota")
sprawdz("jadł (cap)", rec["jadl"])
sprawdz("kolejność celów 2", len(rec["cele"]) == 2 and rec["cele"][1]["hp_koniec"] == 40)
sprawdz("exp przyrost 10", rec["exp_przyrost"] == 10)

# 7) bot cichy: proces jest, telemetria milczy
b = O.Bot(katalog="/nonexistent", logi="/nonexistent", zegar=lambda: T0)
s = b.opisz(T0, {"t": T0 - 60, "stan": "WALKA"}, 60, True, False, False)
sprawdz("telemetria stara: bot_cichy", s["tryb"] == "cichy")
s = b.opisz(T0, {"t": T0 - 1, "stan": "WALKA", "cel": {"id": 5}}, 1, True, False, False)
sprawdz("telemetria świeża: aktywny", s["tryb"] == "aktywny" and s["cel"]["id"] == 5)
s = b.opisz(T0, None, None, False, False, False)
sprawdz("brak procesu: brak", s["tryb"] == "brak")

# 8) czytelnik telemetrii z pliku: ogon, niepełna linia, whitelist akcji bez nicków
tmp = Path(tempfile.mkdtemp())
dzien = time.strftime("%Y%m%d", time.localtime(T0))
plik = tmp / f"telemetria-{dzien}.jsonl"
l1 = json.dumps({"t": T0, "typ": "probka", "stan": "WALKA", "cel": {"id": 9},
                 "akcja": {"co": "Gracz w pobliżu: Ktos Obcy (3 pól), gram dalej.", "wynik": ""}})
l2 = json.dumps({"t": T0, "typ": "poscig_start", "cel": "Rat", "odl": 3, "hp_celu": 20})
plik.write_text(l1 + "\n" + l2[:20])
b = O.Bot(katalog=tmp, logi=tmp, zegar=lambda: T0 + 1)
b.proces, b.t_proces = True, T0 + 1
s = b.stan(T0 + 1)
sprawdz("odczyt próbki z pliku", s["tryb"] == "aktywny" and s["cel"]["id"] == 9)
sprawdz("akcja z nickiem odfiltrowana", s["akcja"] is None)
sprawdz("niepełna linia czeka", not b.poscig)
with open(plik, "a") as f:
    f.write(l2[20:] + "\n")
s = b.stan(T0 + 1)
sprawdz("dopisana linia doczytana", b.poscig and s["poscig"])

# 9) zapis jsonl/md bez nicków
z = O.Zapis(tmp)
z.epizod(rec, tekst)
tr = (tmp / "pomoc-karola.jsonl").read_text()
sprawdz("jsonl zapisany", json.loads(tr.splitlines()[0])["tryb"] == "brak_bota")
sprawdz("md zapisany po polsku", "Gra ręczna" in (tmp / "pomoc-karola.md").read_text())
sprawdz("brak nicka w zapisie", "Ktos Obcy" not in tr)

print("WSZYSTKO OK" if ok else "SĄ BŁĘDY")
sys.exit(0 if ok else 1)
