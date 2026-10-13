import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, tempfile, types
from pathlib import Path
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import telemetria, pokretla, analityk

ok = True
def sprawdz(opis, war):
    global ok
    print(("OK   " if war else "BŁĄD ") + opis); ok = ok and bool(war)

T = [1_700_000_000.0]
zegar = lambda: T[0]
tmp = Path(tempfile.mkdtemp())
mod = types.SimpleNamespace(POGON_LIMIT=14.0, LOOT_PO_WALCE=5)
pk = pokretla.Pokretla(mod, plik=tmp / "na_zywo.json", log=lambda *a: None, zegar=zegar)
tele = telemetria.Telemetria(tmp / "t", zegar=zegar, zapis=False)
logi = tmp / "logi"
wywolania = []
odp = [json.dumps({"status": "ok", "wniosek": "Wszystko gra.", "dowod": "3 zabicia/min", "akcje": [], "do_kodu": []})]
def model(prompt, system):
    wywolania.append(prompt)
    return odp[0], {"total_cost_usd": 0.001}
powiadomione = []
analityk.powiadom.powiadom = lambda *a, **k: powiadomione.append(a)
ob = analityk.Obserwator(tele, pk, model, log=lambda *a: None, zegar=zegar, logi=logi, cykl_s=60)
sprawdz("cykl min 30 s", analityk.Obserwator(tele, pk, model, zegar=zegar, logi=logi, cykl_s=5).cykl_s == 30)

def wiersze():
    p = logi / "obserwator.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

# --- walidacja JSON ---
w = analityk.waliduj_obserwacje('```json\n{"status":"uwaga","wniosek":"Dużo odpuszczeń","dowod":"4/min","akcje":[{"pokretlo":"POGON_LIMIT","wartosc":20.0}],"do_kodu":["x"]}\n```')
sprawdz("walidacja: poprawny JSON", w and w["status"] == "uwaga" and w["akcje"] == {"POGON_LIMIT": 20.0} and w["do_kodu"] == ["x"])
sprawdz("walidacja: zły status", analityk.waliduj_obserwacje('{"status":"zle","wniosek":"a"}') is None)
sprawdz("walidacja: brak wniosku", analityk.waliduj_obserwacje('{"status":"ok","wniosek":""}') is None)
sprawdz("walidacja: nie-JSON", analityk.waliduj_obserwacje("bla") is None)
w = analityk.waliduj_obserwacje('{"status":"ok","wniosek":"a","akcje":[{"pokretlo":"POGON_LIMIT","wartosc":99},{"pokretlo":"NIEZNANE","wartosc":1}]}')
sprawdz("zakresy pokręteł: poza zakresem i nieznane odrzucone", w["akcje"] == {} and len(w["bledy"]) == 2)
w = analityk.waliduj_obserwacje('{"status":"ok","wniosek":"a","akcje":{"POGON_LIMIT":20,"LOOT_PO_WALCE":4}}')
sprawdz("tylko jedna zmiana naraz", len(w["akcje"]) == 1)

# --- pierwszy cykl: wywołanie modelu; powtórka bez zmian: pominięcie ---
T[0] += 60; tele.zdarzenie("zabicie", n="Rat", walka_s=5)
ob.obieg()
sprawdz("pierwszy cykl woła model", len(wywolania) == 1 and wiersze()[-1]["status"] == "ok")
T[0] += 120
ob.obieg()   # okno 60 s puste, inny podpis niż z zabiciem -> model
n1 = len(wywolania)
T[0] += 60
ob.obieg()   # nic nowego
sprawdz("brak zmian: model nie wołany, wiersz bez_zmian", len(wywolania) == n1 and wiersze()[-1]["status"] == "bez_zmian")
T[0] += 30; ob.obieg()
sprawdz("przed upływem cyklu nic się nie dzieje", wiersze()[-1]["status"] == "bez_zmian")
sprawdz("koszt w wierszu i suma", wiersze()[0]["koszt"] == 0.001 and abs(ob.koszt - 0.002) < 1e-9)

# --- zmiana: nowe zdarzenie -> model; uwaga -> alert, dedup 10 min ---
odp[0] = json.dumps({"status": "uwaga", "wniosek": "Utknięcie w WALKA", "dowod": "18 s", "akcje": [],
                     "do_kodu": ["Utknięcie przy ścianie w WALKA"]})
alerty = logi / "obserwator-alerty.log"
def nowe_zdarzenie():
    T[0] += 60
    tele.zdarzenie("utkniecie", stan="WALKA", poz=[1, 2], s=18, stwory=[])
    ob.obieg()
nowe_zdarzenie()
tresc = alerty.read_text().splitlines()
sprawdz("alert zapisany w formacie HH:MM:SS [uwaga] wniosek | dowod",
        len(tresc) == 1 and tresc[0][2] == ":" and "[uwaga] Utknięcie w WALKA | 18 s" in tresc[0])
sprawdz("uwaga nie powiadamia", powiadomione == [])
nowe_zdarzenie()
sprawdz("ten sam alert w <10 min: dedup", len(alerty.read_text().splitlines()) == 1)
T[0] += 600; nowe_zdarzenie()
sprawdz("po 10 min alert wraca", len(alerty.read_text().splitlines()) == 2)
sprawdz("do_poprawy dedup", (logi / "do_poprawy.md").read_text().count("Utknięcie przy ścianie") == 1)
sprawdz("pliki ostatni zgodne", (logi / "obserwator-ostatni.txt").read_text() == (logi / "wniosek-ostatni.txt").read_text()
        and "[uwaga]" in (logi / "obserwator-ostatni.txt").read_text())

# --- ok nie trafia do alertów; problem powiadamia ---
odp[0] = json.dumps({"status": "problem", "wniosek": "Bot stoi", "dowod": "0 zabić 5 min", "akcje": []})
nowe_zdarzenie()
sprawdz("problem: powiadomienie", len(powiadomione) == 1 and "[problem] Bot stoi" in alerty.read_text())
odp[0] = json.dumps({"status": "ok", "wniosek": "Znów dobrze", "dowod": "", "akcje": []})
nowe_zdarzenie()
sprawdz("ok nie dopisuje do alertów", "Znów dobrze" not in alerty.read_text())
sprawdz("ostatnie 3 wnioski w wejściu", len(ob.wnioski) == 3 and "Znów dobrze" in ob.wnioski[-1])

# --- akcja: pokrętło w zakresie zastosowane, poza zakresem nie ---
odp[0] = json.dumps({"status": "uwaga", "wniosek": "Za długi pościg", "dowod": "d",
                     "akcje": [{"pokretlo": "POGON_LIMIT", "wartosc": 20.0}]})
nowe_zdarzenie()
sprawdz("pokrętło zmienione", mod.POGON_LIMIT == 20.0)
odp[0] = json.dumps({"status": "uwaga", "wniosek": "Inny", "dowod": "d",
                     "akcje": [{"pokretlo": "LOOT_PO_WALCE", "wartosc": 99}]})
nowe_zdarzenie()
sprawdz("poza zakresem: bez zmiany", mod.LOOT_PO_WALCE == 5)

# --- limit na godzinę ---
n = len(wywolania)
ob.limit_h = len(ob.wywolania)
nowe_zdarzenie()
sprawdz("limit/h: model nie wołany, wiersz limit_h", len(wywolania) == n and wiersze()[-1]["status"] == "limit_h")
ob.limit_h = 100
ob.wywolania = []
nowe_zdarzenie()
sprawdz("po zdjęciu limitu znów woła", len(wywolania) == n + 1)

# --- błędy modelu ---
odp[0] = "nie json"
nowe_zdarzenie()
sprawdz("zły JSON: wiersz blad_json, bez wyjątku", wiersze()[-1]["status"] == "blad_json")
def pada(p, s): raise RuntimeError("x")
ob.model = pada
nowe_zdarzenie()
sprawdz("wyjątek modelu: wiersz blad_modelu", wiersze()[-1]["status"] == "blad_modelu")

# --- ogon logu cavebota ---
logi.mkdir(exist_ok=True); (logi / "ostatni").write_text("logi/c.log\n")
lt = __import__("time").localtime(T[0]); hh = __import__("time").strftime("%H:%M:%S", lt)
(logi / "c.log").write_text(f"{hh} ALARM: gracz GM\n{hh} Zjedzono: nic\n{hh} debug: ALARM nie\n{hh} pochodnia zgasła\n")
g = analityk.ogon_cavebota(logi, T[0])
sprawdz("ogon logu: alarm, jedzenie, pochodnia, bez debug", len(g["alarmy"]) == 1 and g["jedzenie"] == {"brak": 1}
        and len(g["pochodnia"]) == 1)

# --- świeżość stanu: przypadek 12:59 (stary snapshot IDZ vs telemetria LOOT) ---
logi2 = tmp / "logi2"
tele2 = telemetria.Telemetria(tmp / "t2", zegar=zegar, zapis=False)
stary = {"wiek_s": 25, "cavebot": "IDZ", "gracz": {"hp_proc": 90}, "gracze": []}
wej = []
odp2 = [json.dumps({"status": "problem", "wniosek": "Rat odl 1 20% HP, cavebot w stanie IDZ, 0 zabić",
                    "dowod": "stoi Rat odl 1, stan IDZ", "akcje": [], "do_kodu": ["regresja walki"]})]
def model2(prompt, system):
    wej.append(json.loads(prompt)); return odp2[0], {"total_cost_usd": 0.001}
ob2 = analityk.Obserwator(tele2, pk, model2, log=lambda *a: None, zegar=zegar, logi=logi2, cykl_s=60,
                          zrodlo=lambda: dict(stary))
sprawdz("prompt zawiera regułę o wieku stanu", "wiek_stanu_s" in analityk.SYSTEM_OBS and "15 s" in analityk.SYSTEM_OBS)
n_pow = len(powiadomione)
T[0] += 100
tele2.rek.append({"t": T[0] - 1, "typ": "probka", "stan": "LOOT", "poz": [1, 2, 7], "hp": 100, "mana": 50,
                  "stwory": [], "dbb": 0})
ob2.cykl(T[0])
sprawdz("świeża telemetria: stan z próbki, nie ze starego snapshotu",
        wej[-1]["cavebot"] == "LOOT" and wej[-1]["zrodlo_stanu"] == "telemetria" and wej[-1]["wiek_stanu_s"] == 1.0)
sprawdz("12:59: sprzeczny wniosek -> brak alertu i powiadomienia",
        not (logi2 / "obserwator-alerty.log").exists() and len(powiadomione) == n_pow
        and not (logi2 / "obserwator-ostatni.txt").exists())
sprawdz("12:59: wiersz nieaktualne, bez do_poprawy",
        (logi2 / "obserwator.jsonl").read_text().splitlines()[-1].count('"status":"nieaktualne"') == 1
        and not (logi2 / "do_poprawy.md").exists() and ob2.wnioski == [])
# bez świeżej telemetrii: stary stan, oznaczony wiekiem
T[0] += 200
odp2[0] = json.dumps({"status": "ok", "wniosek": "Nic", "dowod": "", "akcje": []})
ob2.cykl(T[0])
sprawdz("brak świeżej telemetrii: stary stan z wiekiem i oznaczeniem",
        wej[-1]["cavebot"] == "IDZ" and wej[-1]["wiek_stanu_s"] == 25 and "STARY" in wej[-1]["zrodlo_stanu"])
# zgodny z telemetrią wniosek przechodzi
T[0] += 10
tele2.rek.append({"t": T[0] - 1, "typ": "probka", "stan": "WALKA", "poz": [1, 2, 7], "hp": 40, "mana": 50,
                  "stwory": [{"n": "Rat", "dx": 1, "dy": 0, "odl": 1, "hp": 20, "gracz": False}], "dbb": 0})
odp2[0] = json.dumps({"status": "uwaga", "wniosek": "Rat odl 1 20% HP w stanie WALKA, HP 40%",
                      "dowod": "stoi Rat odl 1", "akcje": []})
ob2.cykl(T[0])
sprawdz("zgodny z telemetrią wniosek zostaje (alert)", (logi2 / "obserwator-alerty.log").exists()
        and wej[-1]["cavebot"] == "WALKA" and wej[-1]["postac"]["hp_proc"] == 40)
# twierdzenia_sprzeczne: jednostkowo
ost = {"t": T[0], "stan": "LOOT", "stwory": [{"n": "Rat", "odl": 3, "gracz": False}]}
sprawdz("sprzeczne: stan", analityk.twierdzenia_sprzeczne({"wniosek": "cavebot w stanie IDZ"}, ost, T[0] + 1))
sprawdz("sprzeczne: odl moba", analityk.twierdzenia_sprzeczne({"wniosek": "stoi Rat odl 1"}, ost, T[0] + 1))
sprawdz("niesprzeczne: trwanie historyczne", not analityk.twierdzenia_sprzeczne(
    {"wniosek": "przez 40 s w stanie IDZ"}, ost, T[0] + 1))
sprawdz("niesprzeczne: stara próbka nie waliduje", not analityk.twierdzenia_sprzeczne(
    {"wniosek": "w stanie IDZ"}, ost, T[0] + 60))

# brak jedzenia: status nie rośnie ponad ok, dopóki HP > próg + 15
w = {"status": "problem", "wniosek": "Brak jedzenia, brak regeneracji HP", "dowod": "jedzenie.brak=3", "do_kodu": ["x"], "akcje": {}}
sprawdz("brak jedzenia HP 80%: status ok, info", analityk.wygas_jedzenie(w, {"postac": {"hp_proc": 80}, "minuta": {"hp_min": 78}})
        and w["status"] == "ok" and w["wniosek"].startswith("[info]") and w["do_kodu"] == [])
w = {"status": "uwaga", "wniosek": "Brak jedzenia", "dowod": "", "do_kodu": [], "akcje": {}}
sprawdz("brak jedzenia HP 40% (<= prog+15): status zostaje", not analityk.wygas_jedzenie(w, {"postac": {"hp_proc": 40}}) and w["status"] == "uwaga")
w = {"status": "problem", "wniosek": "Bot stoi w miejscu", "dowod": "", "do_kodu": [], "akcje": {}}
sprawdz("inny problem przy HP 90%: bez zmian", not analityk.wygas_jedzenie(w, {"postac": {"hp_proc": 90}}) and w["status"] == "problem")
w = {"status": "problem", "wniosek": "Brak jedzenia", "dowod": "", "do_kodu": [], "akcje": {}}
sprawdz("HP nieznane: bez zmian", not analityk.wygas_jedzenie(w, {"postac": None, "minuta": {}}) and w["status"] == "problem")

print("WSZYSTKO OK" if ok else "SĄ BŁĘDY")
sys.exit(0 if ok else 1)
