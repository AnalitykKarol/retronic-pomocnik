import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, types, json, tempfile
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import ratunek

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

def konf(**k):
    return types.SimpleNamespace(**dict(ratunek.DOMYSLNE, RATUNEK_HAIKU=1, **k))

def kody(syg):
    return [s["kod"] for s in syg]

def przebieg(det, kroki, t0=0.0, dt=1.0):
    """kroki: lista (poz, stan, exp); zwraca wszystkie sygnały."""
    out = []
    for i, (poz, stan, exp) in enumerate(kroki):
        out += det.tick(t0 + i * dt, poz, stan, exp)
    return out

# --- R1 (19.10 20:25, Mastafian): dojście 1 pkt na z8, postać na z6, kolejne instancje CavebotDojscie ---
R1_POZ, R1_CEL = (33106, 31849, 6), (33106, 31849, 8)
d = ratunek.Detektor(konf())
syg = []
t = 0.0
for proba in range(5):                       # 5 prób dojścia po ~5 s, każda = nowy cavebot (ustaw_trase od nowa)
    d.ustaw_trase([R1_CEL])
    for _ in range(5):
        syg += d.tick(t, R1_POZ, "IDZ", 81000); t += 1.0
    syg += d.zdarzenie("okrazenie", t, None)  # „Okrążenie 1 gotowe” na końcu każdej próby
syg += d.zdarzenie("porazka_trasy", t, R1_POZ, co="dojscie", trasa="gobliny_edron_z_depo")
k = kody(syg)
sprawdz("R1: S2 złe piętro (z6, trasa z8) przez kolejne próby dojścia", "S2" in k, k)
s2 = next((s for s in syg if s["kod"] == "S2"), {})
sprawdz("R1: S2 po >= 10 s, nie wcześniej", s2.get("trwa_s", 0) >= 10 and s2.get("t", 0) >= 10, s2)
sprawdz("R1: S7 pusta pętla trasy (3+ okrążenia w 60 s w miejscu)", "S7" in k, k)
sprawdz("R1: S1 porażka dojścia", "S1" in k, k)
sprawdz("R1: każdy sygnał raz (debounce)", len(k) == len(set(k)), k)
sprawdz("R1: sygnał ma pozycję postaci", s2.get("poz") == list(R1_POZ), s2)

# --- detektor procesu przeżywa instancje cavebota ---
ratunek._DET = None
a1 = ratunek.detektor(konf()); a2 = ratunek.detektor()
sprawdz("detektor() = jeden na proces", a1 is a2)
a1.pietro_t = 7.0; a1.ustaw_trase([(1, 1, 8)])
sprawdz("ustaw_trase nie zeruje licznika piętra", a1.pietro_t == 7.0)
ratunek._DET = None

# --- walka i stany zamierzone nie są sygnałem ---
d = ratunek.Detektor(konf()); d.ustaw_trase([R1_CEL])
syg = przebieg(d, [(R1_POZ, "WALKA", 81000)] * 40)
sprawdz("walka na złym piętrze 40 s: brak sygnału", syg == [], kody(syg))
d = ratunek.Detektor(konf()); d.ustaw_trase([(10, 10, 7)])
syg = przebieg(d, [((10, 10, 7), "PRZERWA", 5)] * 90)
sprawdz("PRZERWA 90 s w miejscu: brak S3", syg == [], kody(syg))
d = ratunek.Detektor(konf()); d.ustaw_trase([(10, 10, 7)])
syg = przebieg(d, [((10, 10, 7), "POGON", 5), ((11, 10, 7), "POGON", 5)] * 30)
sprawdz("pościg tam i z powrotem: brak S4", syg == [], kody(syg))

# --- S3 stoi ---
d = ratunek.Detektor(konf()); d.ustaw_trase([(10, 10, 7)])
syg = przebieg(d, [((10, 10, 7), "IDZ", 5)] * 31)
sprawdz("S3: 31 s w miejscu poza walką", kody(syg) == ["S3"], kody(syg))
d = ratunek.Detektor(konf()); d.ustaw_trase([(10, 10, 7)])
syg = przebieg(d, [((10, 10, 7), "IDZ", 5 + i) for i in range(40)])
sprawdz("S3: w miejscu, ale exp rośnie = brak", "S3" not in kody(syg), kody(syg))
d = ratunek.Detektor(konf()); d.ustaw_trase([(10, 10, 7)])
syg = przebieg(d, [((10, 10, 7), "IDZ", 5)] * 25)
sprawdz("S3: 25 s (< progu 30) = brak", syg == [], kody(syg))

# --- S4 kręci się ---
d = ratunek.Detektor(konf()); d.ustaw_trase([(10, 10, 7)])
osc = [((10, 10, 7), "IDZ", 5), ((11, 10, 7), "IDZ", 5)] * 3
syg = przebieg(d, osc)
sprawdz("S4: oscylacja A-B-A-B-A-B", "S4" in kody(syg), kody(syg))
d = ratunek.Detektor(konf()); d.ustaw_trase([(10, 10, 7)])
krag = [((10 + dx, 10 + dy, 7), "IDZ", 5) for dx, dy in [(0, 0), (1, 0), (1, 1), (0, 1)]] * 4
syg = przebieg(d, krag)
sprawdz("S4: kółko 4 pól 4 razy w 16 s", "S4" in kody(syg), kody(syg))
d = ratunek.Detektor(konf()); d.ustaw_trase([(10, 10, 7)])
prosto = [((10 + i, 10, 7), "IDZ", 5) for i in range(60)]
syg = przebieg(d, prosto)
sprawdz("prosty marsz 60 pól: brak sygnału", syg == [], kody(syg))
d = ratunek.Detektor(konf()); d.ustaw_trase([(10, 10, 7)])
tam_i_z = [((10 + i, 10, 7), "IDZ", 5) for i in range(25)] + [((34 - i, 10, 7), "IDZ", 5) for i in range(25)]
syg = przebieg(d, tam_i_z)
sprawdz("patrol tam i z powrotem po 25 polach raz: brak S4", "S4" not in kody(syg), kody(syg))

d = ratunek.Detektor(konf()); d.ustaw_trase([(10, 10, 7)])
syg = przebieg(d, [((10, 10, 7), "IDZ", 5), ((11, 10, 7), "IDZ", 5)] * 2 + [((12 + i, 10, 7), "IDZ", 5) for i in range(20)])
sprawdz("S4: krótka oscylacja (2 powroty), potem marsz: brak sygnału na dalszych polach", "S4" not in kody(syg), syg)
d = ratunek.Detektor(konf()); d.ustaw_trase([(10, 10, 7)])
syg = przebieg(d, [((10, 10, 7), "IDZ", 5), ((11, 10, 7), "IDZ", 5)] * 3 + [((12 + i, 10, 7), "IDZ", 5) for i in range(20)])
sprawdz("S4: oscylacja daje JEDEN sygnał, marsz po niej żadnego", kody(syg) == ["S4"], [(s["kod"], s["poz"]) for s in syg])

# --- S5 kroki bez skutku (serwis 19.10 20:12: 6 nieudanych z rzędu) ---
d = ratunek.Detektor(konf()); d.tick(0, (33176, 31828, 6), "IDZ")
syg = []
for i in range(6):
    syg += d.zdarzenie("krok_nieudany", 1 + i, (33176, 31828, 6))
sprawdz("S5: 6 nieudanych kroków z rzędu", kody(syg) == ["S5"], kody(syg))
d = ratunek.Detektor(konf()); d.tick(0, (5, 5, 7), "IDZ")
syg = []
for i in range(5):
    syg += d.zdarzenie("krok_nieudany", 1 + i, (5, 5, 7))
d.tick(7, (6, 5, 7), "IDZ")
for i in range(5):
    syg += d.zdarzenie("krok_nieudany", 8 + i, (6, 5, 7))
sprawdz("S5: ruch zeruje licznik (5 + ruch + 5 = brak)", syg == [], kody(syg))

# --- S6 klik bez skutku ---
d = ratunek.Detektor(konf()); d.tick(0, (5, 5, 7), "WALKA")
sprawdz("S6: 5 klików bez efektu", kody(d.zdarzenie("klik_bez_efektu", 1, None, n=5, cel="Goblin")) == ["S6"])
d = ratunek.Detektor(konf()); d.tick(0, (5, 5, 7), "WALKA")
sprawdz("S6: 4 kliki = brak", d.zdarzenie("klik_bez_efektu", 1, None, n=4) == [])

# --- S7: okrążenia z ruchem to normalna praca ---
d = ratunek.Detektor(konf())
syg = []
for i in range(4):
    d.tick(i * 10, (10 + i * 10, 10, 7), "IDZ")
    syg += d.zdarzenie("okrazenie", i * 10 + 1, None)
sprawdz("S7: okrążenia w różnych miejscach = brak", syg == [], kody(syg))

# --- debounce, limit, luka ---
d = ratunek.Detektor(konf()); d.ustaw_trase([(10, 10, 7)])
syg = przebieg(d, [((10, 10, 7), "IDZ", 5)] * 100)
sprawdz("debounce: S3 raz przez 100 s w tym samym miejscu", kody(syg) == ["S3"], kody(syg))
syg = przebieg(d, [((30, 30, 7), "IDZ", 5)] * 35, t0=100)
sprawdz("debounce: nowe miejsce (> 5 pól) = nowy S3", kody(syg) == ["S3"], kody(syg))
d = ratunek.Detektor(konf(RATUNEK_LIMIT_H=3, RATUNEK_PRZERWA_S=30.0))
lim = [d.zdarzenie("porazka_trasy", i * 40.0, (i * 10, 0, 7), co="dojscie") for i in range(4)]
sprawdz("limit/h: czwarty sygnał przy limicie 3 ma ponad_limit", lim[3] and lim[3][0]["ponad_limit"] and not lim[2][0]["ponad_limit"], lim)
d = ratunek.Detektor(konf()); d.ustaw_trase([(10, 10, 7)])
syg = przebieg(d, [((10, 10, 7), "IDZ", 5)] * 20) + przebieg(d, [((10, 10, 7), "IDZ", 5)] * 20, t0=100)
sprawdz("luka > 30 s między obiegami zeruje liczniki (20 + 20 s = brak S3)", syg == [], kody(syg))

# --- zastrzeżone klucze i zegar ---
d = ratunek.Detektor(konf())
s = d.zdarzenie("porazka_trasy", 5.0, (1, 1, 7), co="wyprawa", opis="szczegół", t=99, kod="X")
sprawdz("zastrzeżone klucze z wywołującego nie wywracają i nie nadpisują sygnału",
        s and s[0]["kod"] == "S1" and s[0]["opis"] == "porażka trasy" and s[0]["x_opis"] == "szczegół" and s[0]["t"] == 5.0, s)
d = ratunek.Detektor(konf()); d.ustaw_trase([(10, 10, 7)])
syg = przebieg(d, [((10, 10, 7), "JEDZENIE", 5)] * 20 + [((10, 10, 7), "ML", 5)] * 20)
sprawdz("JEDZENIE i ML w miejscu 40 s: brak S3", syg == [], kody(syg))

# --- zglos: log, telemetria, jsonl ---
logi, tele_rek = [], []
tele = types.SimpleNamespace(zdarzenie=lambda typ, **dd: tele_rek.append((typ, dd)))
with tempfile.TemporaryDirectory() as tmp:
    plik = ratunek.plik_logu(tmp)
    d = ratunek.Detektor(konf())
    ratunek.zglos(d.zdarzenie("porazka_trasy", 5.0, R1_POZ, co="dojscie"), log=logi.append, tele=tele, plik_logu=plik, stan="IDZ")
    wiersze = [json.loads(l) for l in open(plik)]
sprawdz("zglos: log „cień … wołałbym Haiku”", logi and "[RATUNEK] cień: S1" in logi[0] and "wołałbym Haiku" in logi[0], logi)
sprawdz("zglos: telemetria `ratunek` tryb cien", tele_rek and tele_rek[0][0] == "ratunek" and tele_rek[0][1]["tryb"] == "cien", tele_rek)
sprawdz("zglos: wiersz jsonl z kodem i pozycją", wiersze and wiersze[0]["kod"] == "S1" and wiersze[0]["poz"] == list(R1_POZ), wiersze)
import time as _tm
sprawdz("zglos: czas ścienny = teraz, nie t detektora (t=5.0 dałoby 1970)", wiersze and wiersze[0]["czas"][:4] == _tm.strftime("%Y"), wiersze)
sprawdz("zglos: zepsuty log/tele nie wywraca", ratunek.zglos(d.zdarzenie("porazka_trasy", 500.0, (1, 1, 1), co="x"),
        log=lambda m: 1 / 0, tele=types.SimpleNamespace(zdarzenie=lambda *a, **k: 1 / 0), plik_logu="/nonexistent/x/y.jsonl") is None)

# --- cavebot: pokrętło 0 = nic, wypad = bez S2, zdarzenia ---
import cavebot
def atrapa(**k):
    ns = types.SimpleNamespace(punkty=[R1_CEL], wypad_aktywny=False, stan="IDZ", exp_teraz=1, tele=None,
                               zegar=lambda: ns.t, t=0.0, **k)
    for m in ("_ratunek_det", "_ratunek_zglos", "_ratunek_tick", "_ratunek_zdarzenie"):
        setattr(ns, m, types.MethodType(getattr(cavebot.Cavebot, m), ns))
    return ns
stare = cavebot.RATUNEK_HAIKU, cavebot.log
zlog = []
cavebot.log = zlog.append
try:
    ratunek._DET = None
    cavebot.RATUNEK_HAIKU = 0
    cb = atrapa()
    for i in range(20):
        cb.t = float(i); cb._ratunek_tick(R1_POZ, cb.t)
    sprawdz("cavebot: RATUNEK_HAIKU=0 -> brak detektora i logu", ratunek._DET is None and not any("RATUNEK" in l for l in zlog), zlog)
    cavebot.RATUNEK_HAIKU = 1
    cb = atrapa()
    for i in range(12):
        cb.t = float(i); cb._ratunek_tick(R1_POZ, cb.t)
    sprawdz("cavebot: RATUNEK_HAIKU=1, R1 -> log S2", any("[RATUNEK] cień: S2" in l for l in zlog), zlog)
    ratunek._DET = None; zlog.clear()
    cb = atrapa(); cb.wypad_aktywny = True
    for i in range(30):
        cb.t = float(i); cb._ratunek_tick((10 + i, 10, 6), cb.t)
    sprawdz("cavebot: w wypadzie złe piętro nie jest sygnałem", not any("S2" in l for l in zlog), zlog)
    sprawdz("cavebot: po wypadzie trasa piętra wraca", ratunek._DET.trasa_pietra == {8}, ratunek._DET.trasa_pietra)
    ratunek._DET = None; zlog.clear()
    cb = atrapa(); cb._ratunek_tick((5, 5, 8), 0.0)
    for i in range(6):
        cb.t = 1.0 + i; cb._ratunek_zdarzenie("krok_nieudany", (5, 5, 8))
    sprawdz("cavebot: zdarzenie krok_nieudany x6 -> S5", any("[RATUNEK] cień: S5" in l for l in zlog), zlog)
    # haki: wywołanie zaraz po linii logu, która dziś oznacza dane zdarzenie (miejsce, nie sama obecność w pliku)
    src = open(cavebot.__file__).read().splitlines()
    def po(znacznik, hak, okno):
        i = [n for n, l in enumerate(src) if znacznik in l]
        return len(i) == 1 and any(hak in l for l in src[i[0] + 1:i[0] + 1 + okno])
    sprawdz("cavebot: hak krok_nieudany zaraz po logu „nie ruszył”", po('nie ruszył (cel kroku', '_ratunek_zdarzenie("krok_nieudany"', 6))
    sprawdz("cavebot: hak klik_bez_efektu zaraz po logu „klików bez efektu”", po('klików bez efektu w', '_ratunek_zdarzenie("klik_bez_efektu"', 3))
    sprawdz("cavebot: hak okrążenia zaraz po logu „Okrążenie … gotowe”", po('log(f"Okrążenie {self.okrazenie} gotowe.")', '_ratunek_zdarzenie("okrazenie"', 1))
    sprawdz("cavebot: tick ratunku zaraz po ticku D3", po('self._d3_tick(g, poz, teraz)', 'self._ratunek_tick(poz, teraz)', 1))
    # S1 z wyprawy: prawdziwe Wypad._awaria (przegląd 19.10: opis= wywracał sygnał po cichu)
    import wypad
    ratunek._DET = None; zlog.clear()
    cb = atrapa(); cb._ratunek_tick((33100, 31800, 7), 0.0)
    w = wypad.Wypad.__new__(wypad.Wypad)
    w.cb, w.log, w.faza, w.wynik, w.dojscie = cb, (lambda m: None), "z", None, None
    try:
        w._awaria("utkniecie", "brak postępu na etapie 3")
    except Exception:
        pass                                  # dalsza część _awaria potrzebuje pełnego wypadu; liczy się sygnał przed nią
    s1 = [l for l in zlog if "[RATUNEK] cień: S1" in l]
    sprawdz("wypad._awaria -> S1 w logu z typem i powodem", s1 and "co=wyprawa" in s1[0] and "brak postępu" in s1[0], zlog)
    # S1 z serwisu: prawdziwe serwis._ratunek_porazka, pokrętło z na_zywo.json instancji, jsonl z dzisiejszym czasem
    import serwis, instancja, bot, io, contextlib, time as _t
    stare_s = instancja.S.na_zywo, instancja.S.logi
    with tempfile.TemporaryDirectory() as tmp:
        try:
            instancja.S.na_zywo, instancja.S.logi = Path(tmp) / "na_zywo.json", Path(tmp)
            pos = types.SimpleNamespace(pozycja=lambda: (33176, 31828, 6))
            out = io.StringIO()
            instancja.S.na_zywo.write_text('{"RATUNEK_HAIKU": 0}')
            ratunek._DET = None
            with contextlib.redirect_stdout(out):
                serwis._ratunek_porazka(pos, "marsz", "6 nieudanych kroków z rzędu", serwis.SerwisBlad("marsz", "x"), bot)
            sprawdz("serwis: pokrętło 0 = cisza", out.getvalue() == "", out.getvalue())
            instancja.S.na_zywo.write_text('{"RATUNEK_HAIKU": 1}')
            ratunek._DET = None
            with contextlib.redirect_stdout(out):
                serwis._ratunek_porazka(pos, "marsz", "6 nieudanych kroków z rzędu", serwis.SerwisBlad("marsz", "x"), bot)
            ratunek._DET = None                   # świeży detektor: STOP nie może zniknąć tylko przez debounce
            with contextlib.redirect_stdout(out):
                serwis._ratunek_porazka(pos, "start", "STOP", bot.Zatrzymano("plik STOP"), bot)
            linie = out.getvalue().splitlines()
            sprawdz("serwis: porażka -> S1 z krokiem i powodem; ręczny STOP nie jest sygnałem",
                    len(linie) == 1 and "S1 porażka trasy" in linie[0] and "co=serwis" in linie[0] and "6 nieudanych" in linie[0], linie)
            w_ = [json.loads(l) for f in Path(tmp).glob("ratunek-*.jsonl") for l in open(f)]
            sprawdz("serwis: jsonl ma dzisiejszy czas ścienny (nie 1970)", w_ and w_[0]["czas"][:4] == _t.strftime("%Y"), w_)
        finally:
            instancja.S.na_zywo, instancja.S.logi = stare_s
    import mozg
    ratunek._DET = None; mlog = []
    pos = types.SimpleNamespace(pozycja=lambda: R1_POZ)
    cavebot.RATUNEK_HAIKU = 0; mozg.ratunek_porazka(pos, "dojscie", log=mlog.append)
    sprawdz("mozg: porażka dojścia przy 0 = cisza", mlog == [], mlog)
    cavebot.RATUNEK_HAIKU = 1; mozg.ratunek_porazka(pos, "dojscie", log=mlog.append, trasa="gobliny_edron_z_depo")
    sprawdz("mozg: porażka dojścia przy 1 = S1 w logu", mlog and "S1 porażka trasy" in mlog[0] and "dojscie" in mlog[0], mlog)
finally:
    cavebot.RATUNEK_HAIKU, cavebot.log = stare
    ratunek._DET = None

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
