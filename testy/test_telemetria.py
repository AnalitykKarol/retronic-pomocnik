import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, os, sys, tempfile, types
from pathlib import Path
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import telemetria, pokretla, analityk
# P4 (13.10): domyślnie (zapis=None) zapis zależy od środowiska (RETRONIC_TELEMETRIA=1, bez RETRONIC_TESTY);
# testy poniżej piszą do własnych katalogów tmp, więc jawnie zapis=True
os.environ.pop("RETRONIC_TELEMETRIA", None)
_Tele = telemetria.Telemetria
class _TeleZapis(_Tele):
    def __init__(self, *a, **k):
        k.setdefault("zapis", True)
        super().__init__(*a, **k)
telemetria.Telemetria = _TeleZapis

ok = True
def sprawdz(opis, war):
    global ok
    print(("OK   " if war else "BŁĄD ") + opis); ok = ok and bool(war)

T = [1000.0]
zegar = lambda: T[0]
tmp = Path(tempfile.mkdtemp())

# --- telemetria: zdarzenia z linii logu ---
t = telemetria.Telemetria(tmp, zegar=zegar)
T[0] = 1000; t.linia("Nowy cel: Rat (100,100) HP 100%")
T[0] = 1010; t.linia("Cel Rat zabity na (100, 100).")
t.linia("[LOOT] zwłoki"); T[0] = 1013; t.linia("Loot: brak_okna")
t.linia("Odpuszczam Rat: za ścianą (droga naokoło: x).")
ev = {r["typ"]: r for r in t.rek}
sprawdz("zabicie z czasem walki 10 s", ev["zabicie"]["walka_s"] == 10.0)
sprawdz("loot brak_okna z czasem", ev["loot"]["wynik"] == "brak_okna")
sprawdz("odpuszczenie z powodem", "za ścianą" in ev["odpuszczenie"]["powod"])
sprawdz("plik jsonl zapisany", any(tmp.glob("telemetria-*.jsonl")))

# --- próbka z atrapą cavebota, loot przy żywym celu, droga_bez_blokad nietknięte ---
cb = types.SimpleNamespace(stan="WALKA", cel={"id": 1, "nazwa": "Rat", "poz": (103, 100), "hp": 80, "odl": 3},
                           ignorowane={}, zegar=zegar, droga_bez_blokad=7,
                           droga=lambda a, b, z, d, skosy=True: [1, 2])
lista = [{"id": 1, "nazwa": "Rat", "x": 103, "y": 100, "z": 7, "hp": 80},
         {"id": 2, "nazwa": "Bat", "x": 90, "y": 100, "z": 7, "hp": 100}]
T[0] = 1100
r = t.probka(cb, {"proc": 90, "mana": 5}, (100, 100, 7), lista)
sprawdz("próbka: tylko stwór w zasięgu, dbb zachowane", len(r["stwory"]) == 1 and cb.droga_bez_blokad == 7 and r["stwory"][0]["osiagalny"])
# droga w próbce liczona jak w decyzji bota: zajęte (zajete_bez_nas) i skosy wg klik
wywolania = []
cb2 = types.SimpleNamespace(stan="WALKA", cel=None, ignorowane={}, zegar=zegar, droga_bez_blokad=0, klik=lambda *a: None,
                            zajete_bez_nas=lambda poz: [(101, 100), (103, 100)],
                            droga=lambda a, b, z, d, skosy=True: wywolania.append((tuple(z), skosy)) or [1])
T[0] = 1050
telemetria.Telemetria(tmp, zegar=zegar).probka(cb2, {"proc": 90}, (100, 100, 7), lista)
sprawdz("próbka: droga z zajętymi polami i skosami jak w bocie", wywolania == [(((101, 100), (103, 100)), True)])
sprawdz("próbka max 1/s", t.probka(cb, {"proc": 90}, (100, 100, 7), lista) is None)
sprawdz("linia stworów", "Rat 3,0 hp80 cel" in telemetria.linia_stworow(r))
T[0] = 1101; t.probka(cb, {"proc": 90}, (100, 100, 7), lista)
t.linia("[WALKA] a"); t.linia("[LOOT] x")
sprawdz("loot_przy_zywym wykryty", any(x["typ"] == "loot_przy_zywym" for x in t.rek))
sprawdz("anomalia: loot przy żywym", any("żywym" in a for a in telemetria.anomalie(list(t.rek), 1102)))

# --- agregaty ---
rek = [{"t": 1000 + i, "typ": "zabicie", "n": "Rat", "walka_s": 10} for i in range(0, 120, 20)] + \
      [{"t": 1000, "typ": "odpuszczenie", "n": "Rat", "powod": "x", "odl": 3, "hp": 100}] * 2 + \
      [{"t": 1000 + i, "typ": "nowy_cel", "n": "Rat", "hp": 100} for i in range(3)] + \
      [{"t": 1001, "typ": "loot", "wynik": "brak_okna", "s": 2}]
ag = telemetria.agreguj(rek, 120)
sprawdz("agregaty: zabicia/min 3, odpuszczenia/min 1", ag["zabicia_na_min"] == 3.0 and ag["odpuszczenia_na_min"] == 1.0)
sprawdz("agregaty: powtórzony cel, brak_okna", ag["powtorzone_cele"] == 1 and ag["loot"] == {"brak_okna": 1})
sprawdz("najgorsze zawiera odpuszczenia", any(x["typ"] == "odpuszczenie" for x in telemetria.najgorsze(rek)))

# --- rotacja ---
t2 = telemetria.Telemetria(tmp / "rot", zegar=zegar, max_bajtow=200)
for i in range(20):
    T[0] = 2000 + i; t2.zdarzenie("x", dane="y" * 50)
sprawdz("rotacja do .1", any(p.name.endswith(".jsonl.1") for p in (tmp / "rot").iterdir()))

# --- pokrętła: walidacja ---
sprawdz("waliduj: zakres", pokretla.waliduj({"POGON_ZASIEG": 99})[0] == {})
sprawdz("waliduj: nieznany klucz", pokretla.waliduj({"EVAL": 1})[1] and not pokretla.waliduj({"EVAL": 1})[0])
sprawdz("waliduj: typ", not pokretla.waliduj({"POGON_ZASIEG": "10"})[0] and not pokretla.waliduj({"POGON_ZASIEG": True})[0])
sprawdz("waliduj: ok", pokretla.waliduj({"POGON_ZASIEG": 12})[0] == {"POGON_ZASIEG": 12})

mod = types.SimpleNamespace(**{k: v[0] + 1 for k, v in pokretla.ZAKRESY.items()})
logi = []
pk = pokretla.Pokretla(mod, plik=tmp / "na_zywo.json", log=logi.append, zegar=zegar)
pk.odswiez()
(tmp / "na_zywo.json").write_text(json.dumps({"POGON_ZASIEG": 12, "LOOT_PO_WALCE": 99}))
pk.odswiez()
sprawdz("hot-reload: poprawne wchodzi, błędne nie", mod.POGON_ZASIEG == 12 and mod.LOOT_PO_WALCE == pk.domyslne["LOOT_PO_WALCE"])
(tmp / "na_zywo.json").unlink(); pk.odswiez()
sprawdz("usunięcie pliku = domyślne", mod.POGON_ZASIEG == pk.domyslne["POGON_ZASIEG"])

# --- kierunek pokręteł dobijania ---
sprawdz("kierunek: POGON_LIMIT poniżej domyślnej odrzucone", pokretla.waliduj({"POGON_LIMIT": 12.0}, {"POGON_LIMIT": 14.0})[0] == {})
sprawdz("kierunek: POGON_LIMIT powyżej domyślnej ok", pokretla.waliduj({"POGON_LIMIT": 20.0}, {"POGON_LIMIT": 14.0})[0] == {"POGON_LIMIT": 20.0})
sprawdz("kierunek: CZEKAJ_BLISKO powyżej domyślnej odrzucone", pokretla.waliduj({"CZEKAJ_BLISKO": 5}, {"CZEKAJ_BLISKO": 4})[0] == {})
sprawdz("zakres: POGON_LIMIT min 12", pokretla.waliduj({"POGON_LIMIT": 8.0})[0] == {} and pokretla.ZAKRESY["POGON_LIMIT"][0] == 12.0)
sprawdz("zakres: POSCIG_OKNO min 3", pokretla.ZAKRESY["POSCIG_OKNO"][0] == 3.0)
mod0 = types.SimpleNamespace(POGON_LIMIT=14.0)
pk0 = pokretla.Pokretla(mod0, plik=tmp / "k.json", log=lambda *a: None, zegar=zegar)
sprawdz("zmien: skrócenie pościgu odrzucone", pk0.zmien({"POGON_LIMIT": 12.0}, "t") == [] and mod0.POGON_LIMIT == 14.0)

# --- auto-cofanie ---
pk.zmien({"POGON_LIMIT": 20.0}, "test", metryki={"zabicia_na_min": 2.0, "odpuszczenia_na_min": 0.5})
sprawdz("zmiana zastosowana i zalogowana", mod.POGON_LIMIT == 20.0 and any("ANALITYK zmienia" in l for l in logi))
sprawdz("druga zmiana w trakcie oceny odrzucona", pk.zmien({"LIMIT_WALKI": 60}, "x") == [])
sprawdz("przed upływem czasu brak oceny", pk.ocen({"zabicia_na_min": 0, "odpuszczenia_na_min": 9}) is None)
T[0] += 301
sprawdz("gorzej -> cofnięcie", pk.ocen({"zabicia_na_min": 1.0, "odpuszczenia_na_min": 0.5}) == "cofnieto"
        and mod.POGON_LIMIT == pk.domyslne["POGON_LIMIT"])
sprawdz("cofnięty klucz zakazany na 30 min", pk.zmien({"POGON_LIMIT": 20.0}, "x") == [])
T[0] += 2000
pk.zmien({"LIMIT_WALKI": 60}, "t2", metryki={"zabicia_na_min": 2.0, "odpuszczenia_na_min": 0.5})
T[0] += 301
sprawdz("lepiej -> zostaje", pk.ocen({"zabicia_na_min": 2.5, "odpuszczenia_na_min": 0.4}) == "zostaje" and mod.LIMIT_WALKI == 60)

# --- analityk z atrapą modelu ---
parsed = analityk.parsuj('```json\n{"problemy":[{"opis":"Loot przy żywym szczurze","dowod":"3x","priorytet":1,"wymaga_kodu":true,"propozycja":"p"}],"pokretla":{"LOOT_PO_WALCE":6},"uzasadnienie_pokretel":"u"}\n```')
sprawdz("parsuj JSON w bloku", parsed and parsed["pokretla"] == {"LOOT_PO_WALCE": 6})
sprawdz("parsuj śmieci", analityk.parsuj("nie json") is None)
wywolania = []
def model(prompt, system):
    wywolania.append(prompt)
    return json.dumps({"problemy": [{"opis": "Loot przy żywym szczurze", "dowod": "d", "priorytet": 1, "wymaga_kodu": True,
                                     "propozycja": "popraw"}], "pokretla": {"LOOT_PO_WALCE": 6}, "uzasadnienie_pokretel": "u"}), {"total_cost_usd": 0.002}
T[0] = 5000
t3 = telemetria.Telemetria(tmp / "a", zegar=zegar)
t3.zdarzenie("loot_przy_zywym", zywe=[["Rat", 2]])
pk2 = pokretla.Pokretla(mod, plik=tmp / "a" / "na_zywo.json", log=logi.append, zegar=zegar)
(tmp / "a").mkdir(exist_ok=True)
an = analityk.Analityk(t3, pk2, model, log=logi.append, zegar=zegar, losuj=lambda a, b: a, logi=tmp / "a")
w = an.obieg()
sprawdz("anomalia -> natychmiastowe wywołanie", w and len(wywolania) == 1 and mod.LOOT_PO_WALCE == 6)
sprawdz("debounce 60 s", an.obieg() is None and len(wywolania) == 1)
sprawdz("do_poprawy.md + wniosek", "żywym szczurze" in (tmp / "a" / "do_poprawy.md").read_text()
        and "żywym" in (tmp / "a" / "wniosek-ostatni.txt").read_text())
sprawdz("deduplikacja do_poprawy", analityk.dopisz_do_poprawy(w["problemy"], tmp / "a") == [])
sprawdz("koszt w logu", any("$0.0020" in l for l in logi))
an.wywolania = [T[0]] * analityk.LIMIT_H; T[0] += 100
sprawdz("limit 15/h", not an.moze(T[0]))

# --- A* w próbce: tylko 3 najbliższe, nie częściej niż co ASTAR_CO s (narzut ticka) ---
wyw = []
cb3 = types.SimpleNamespace(stan="WALKA", cel=None, ignorowane={}, zegar=zegar, droga_bez_blokad=0,
                            droga=lambda a, b, z, d, skosy=True: wyw.append(b) or [1])
mnogo = [{"id": 10 + i, "nazwa": "Rat", "x": 100 + i, "y": 100, "z": 7, "hp": 100} for i in range(1, 7)]
t3 = telemetria.Telemetria(tmp, zegar=zegar)
T[0] = 2000; r1 = t3.probka(cb3, {"proc": 90}, (100, 100, 7), mnogo)
sprawdz("A* tylko dla 3 najbliższych", len(wyw) == 3 and sum(1 for w in r1["stwory"] if "osiagalny" in w) == 3)
T[0] = 2001; r2 = t3.probka(cb3, {"proc": 90}, (100, 100, 7), mnogo)
sprawdz("A* nie częściej niż co 2 s, wynik z pamięci podręcznej", len(wyw) == 3 and
        sum(1 for w in r2["stwory"] if "osiagalny" in w) == 3)
T[0] = 2002.5; t3.probka(cb3, {"proc": 90}, (100, 100, 7), mnogo)
sprawdz("A* po 2 s liczony ponownie", len(wyw) == 6)

# --- epizody celu / dobijanie / exp ---
def cb_cel(hp, odl=1, ign=False, stan="WALKA", nazwa="Rat"):
    return types.SimpleNamespace(stan=stan, cel={"id": 7, "nazwa": nazwa, "poz": (101, 100, 7), "hp": hp, "odl": odl},
                                 ignorowane={}, zegar=zegar, droga_bez_blokad=0, droga=lambda *a, **k: [1])
def pr(te, hp, odl=1, poz=(100, 100, 7), exp=None, stan="WALKA", cel=True):
    c = cb_cel(hp, odl, stan=stan) if cel else types.SimpleNamespace(stan=stan, cel=None, ignorowane={}, zegar=zegar,
                                                                    droga_bez_blokad=0, droga=lambda *a, **k: [1])
    g = {"proc": 90}
    if exp is not None:
        g["exp"] = exp
    return te.probka(c, g, poz, [{"id": 7, "nazwa": "Rat", "x": 101, "y": 100, "z": 7, "hp": hp}])
def ep_typy(te):
    return [r for r in te.rek if r["typ"] == "epizod_celu"]

te = telemetria.Telemetria(tmp / "ep1", zegar=zegar)
T[0] = 3000; te.linia("Nowy cel: Rat (101,100) HP 100%")
T[0] = 3001; pr(te, 100, exp=1000)
T[0] = 3003; pr(te, 80, exp=1000)
T[0] = 3006; pr(te, 25, exp=1000)
T[0] = 3010; te.linia("Cel Rat zabity na (101, 100).")
T[0] = 3011; pr(te, 100, exp=1000, cel=False); T[0] = 3012; pr(te, 100, exp=1005, cel=False)
e = ep_typy(te)
sprawdz("epizod zabity: wynik, czasy", len(e) == 1 and e[0]["wynik"] == "zabity" and e[0]["do_zab_s"] == 7.0
        and e[0]["od30_s"] == 4.0 and e[0]["trafiony"])
ex = [r for r in te.rek if r["typ"] == "exp_zabicie"]
sprawdz("exp na zabicie z przyrostu exp gracza", len(ex) == 1 and ex[0]["n"] == "Rat" and ex[0]["exp"] == 5)

T[0] = 3100; te.linia("Nowy cel: Rat (101,100) HP 100%")
T[0] = 3102; pr(te, 60, exp=1005)
T[0] = 3105; pr(te, 20, exp=1005)
T[0] = 3106; te.linia("Odpuszczam Rat: za ścianą (droga naokoło: x).")
e = ep_typy(te)[-1]
sprawdz("epizod porzucony za ścianą, HP% przy porzuceniu", e["wynik"] == "porzucony" and e["powod"] == "odpuszczony za ścianą"
        and e["hp_porz"] == 20 and e["trafiony"])

T[0] = 3200; te.linia("Nowy cel: Rat (101,100) HP 100%")
T[0] = 3202; pr(te, 50, exp=1005)
T[0] = 3204; te.linia("Cel Rat wyszedł z widoku (130,100), odpuszczam.")
sprawdz("epizod zgubiony (zniknął z widoku żywy)", ep_typy(te)[-1]["wynik"] == "zgubiony")

T[0] = 3300; te.linia("Nowy cel: Rat (101,100) HP 100%")
T[0] = 3302; pr(te, 70, exp=1005)
T[0] = 3303; te.linia("Zmiana celu: Rat stoi obok, Rat jest 3 pól dalej.")
sprawdz("zmiana celu na świeżego = porzucony", ep_typy(te)[-1]["powod"] == "zmiana celu na świeżego")

T[0] = 3400; te.linia("Nowy cel: Rat (101,100) HP 100%")
T[0] = 3402; pr(te, 70, odl=1, exp=1005); T[0] = 3403; pr(te, 65, odl=4, poz=(100, 101, 7), exp=1005)
T[0] = 3404; pr(te, 65, odl=2, poz=(100, 102, 7), exp=1005); T[0] = 3405; pr(te, 65, odl=5, poz=(100, 103, 7), exp=1005)
T[0] = 3406; pr(te, 65, odl=5, stan="UCIECZKA", poz=(100, 104, 7), exp=1005)
T[0] = 3407; te.linia("Nowy cel: Rat (101,100) HP 100%")
e = ep_typy(te)[-1]
sprawdz("uciekł z <=2 pól 2x, kroki pościgu, ucieczka bota", e["uciekl"] == 2 and e["kroki"] == 4
        and e["powod"] == "ucieczka bota z walki" and e["wynik"] == "porzucony")
T[0] = 3408; te.linia("Cel Rat zabity na (101, 100).")
sprawdz("zabity bez trafienia nie liczy się do wskaźnika (zabity = trafiony)", ep_typy(te)[-1]["wynik"] == "zabity")

d = te.dobicie(None)
# trafione: zabity(1) + porzucony(2: ściana, zmiana) + zgubiony(1) + ucieczka(1) + zabity(1) -> 2/6
sprawdz("agregat: liczby i wskaźnik", d["zabite"] == 2 and d["porzucone"] == 3 and d["zgubione"] == 1
        and d["wskaznik"] == 33 and d["epizody"] == 6)
sprawdz("agregat: mediana/p90 czasu do zabicia", d["med_do_zab_s"] is not None and d["p90_do_zab_s"] >= d["med_do_zab_s"])
sprawdz("agregat: exp zdobyty 5, stracony 4x5=20 (mediana per gatunek)", d["exp_zdobyty"] == 5 and d["exp_stracony"] == 20
        and d["exp_utracony_proc"] == 80)
sprawdz("agregat: powód top", d["powod_top"] in ("odpuszczony za ścianą", "zmiana celu na świeżego",
                                                  "zniknął z widoku żywy", "ucieczka bota z walki"))
sprawdz("okno 5 min tylko świeże epizody", te.dobicie(60)["epizody"] <= d["epizody"])
sprawdz("bez trafienia epizod nie wchodzi do wskaźnika",
        telemetria.dobicie([{"typ": "epizod_celu", "n": "Rat", "wynik": "porzucony", "powod": "x", "trafiony": False, "t": 1}])["epizody"] == 0)
sprawdz("linia dobicia", telemetria.linia_dobicia(
    {"epizody": 12, "zabite": 11, "wskaznik": 92, "med_do_zab_s": 14.0, "exp_stracony": 0}) == "dobicie 92% (11/12), mediana 14 s")
sprawdz("linia dobicia: exp stracony", "stracone ~20 exp = 80% potencjału" in telemetria.linia_dobicia(d))
sprawdz("mediana parzysta i p90", telemetria._mediana([1, 2, 3, 4]) == 2.5 and telemetria._p90(list(range(1, 11))) == 9)
sprawdz("brak exp w danych: brak oszacowania", telemetria.dobicie([{"typ": "epizod_celu", "n": "Bat", "wynik": "zgubiony",
        "powod": None, "trafiony": True, "t": 1}])["exp_stracony"] == 0)

# porzucony cel zabity w ciągu 45 s (to samo id) to nie strata: scalanie epizodów
def _ep(t, w, i, powod=None, hp0=100):
    return {"typ": "epizod_celu", "n": "Rat", "id": i, "wynik": w, "powod": powod, "trafiony": True, "t": t,
            "hp0": hp0, "hp_porz": None if w == "zabity" else 25, "do_zab_s": 5.0 if w == "zabity" else None}
flap = [_ep(100, "porzucony", 7, "zmiana celu na świeżego"), _ep(101, "porzucony", 7, "zmiana celu na świeżego", 25),
        _ep(102, "porzucony", 7, "zmiana celu na świeżego", 25), _ep(130, "zabity", 7, hp0=25)]
sc = telemetria.scal_epizody(flap)
sprawdz("scal: 3 porzucone + zabity tego id = 1 zabity z adnotacją",
        len(sc) == 1 and sc[0]["wynik"] == "zabity" and sc[0].get("po_zmianie_celu") is True and "po_zmianie_celu" not in flap[3])
dd = telemetria.dobicie(flap)
sprawdz("scal: wskaźnik 100% (1/1), porzucone 0", dd["epizody"] == 1 and dd["zabite"] == 1 and dd["porzucone"] == 0
        and dd["wskaznik"] == 100)
sprawdz("scal: zabity po oknie 45 s zostaje stratą",
        telemetria.dobicie([_ep(100, "porzucony", 8, "x"), _ep(160, "zabity", 8)])["porzucone"] == 1)
sprawdz("scal: inne id nie scala",
        telemetria.dobicie([_ep(100, "porzucony", 8, "x"), _ep(110, "zabity", 9)])["porzucone"] == 1)
sprawdz("scal: zgubiony zabity później też nie jest stratą",
        telemetria.dobicie([_ep(100, "zgubiony", 8), _ep(110, "zabity", 8)])["zgubione"] == 0)
sprawdz("scal: bez id (None) nie scala",
        telemetria.dobicie([_ep(100, "porzucony", None, "x"), _ep(110, "zabity", None)])["porzucone"] == 1)

# odtwarzanie ze starej telemetrii
rec = [{"t": 10, "typ": "nowy_cel", "n": "Rat", "hp": 100, "pos": [1, 1]},
       {"t": 11, "typ": "probka", "stan": "WALKA", "poz": [0, 0, 7], "cel": {"id": 1, "nazwa": "Rat", "hp": 50, "odl": 1, "poz": [1, 1, 7]}},
       {"t": 15, "typ": "zabicie", "n": "Rat"}]
oe = telemetria.odtworz_epizody(rec)
sprawdz("odtworzenie epizodu ze starych zdarzeń", len(oe) == 1 and oe[0]["wynik"] == "zabity" and oe[0]["do_zab_s"] == 4.0)

# progi obserwatora
mk = lambda w, n: {"epizody": n, "wskaznik": w}
sprawdz("próg: 84% przy 6 epizodach = uwaga", analityk.ocena_dobicia(mk(84, 6)) == "uwaga")
sprawdz("próg: 69% = problem", analityk.ocena_dobicia(mk(69, 8)) == "problem")
sprawdz("próg: 85% = ok", analityk.ocena_dobicia(mk(85, 10)) == "ok")
sprawdz("próg: poniżej 6 epizodów = brak oceny", analityk.ocena_dobicia(mk(40, 5)) is None)
sprawdz("prompt obserwatora ma regułę dobijania", "85%" in analityk.SYSTEM_OBS and "70%" in analityk.SYSTEM_OBS)

# podsumowanie 5 min i dane obserwatora z epizodami
T[0] = 3500
import powiadom
pod = powiadom.Podsumowanie(zegar=zegar, wyslij=lambda a, b: None)
sprawdz("podsumowanie zawiera dobicie", "dobicie 33% (2/6)" in pod.tekst(te, None, T[0]) or "dobicie" in pod.tekst(te, None, T[0]))
fake = types.SimpleNamespace(dobicie=lambda s=None: {"epizody": 10, "zabite": 6, "porzucone": 3, "zgubione": 1,
    "wskaznik": 60, "med_do_zab_s": 12.0, "p90_do_zab_s": 20.0, "med_od30_s": 4.0, "powod_top": "nie zbliżam się",
    "exp_zdobyty": 30, "exp_stracony": 20, "exp_utracony_proc": 40})
db = analityk.dobicie_dla_modelu(fake)
sprawdz("dane obserwatora: dobicie 5min + ocena + stracone", db and db["powod_top"] == "nie zbliżam się"
        and db["ocena"] == "problem" and "sesja" in db and "20 exp = 40%" in db["stracone"])

# plik na dysku: wczytaj_rekordy i statystyki.py
te2 = telemetria.Telemetria(tmp / "ep2", zegar=zegar)
T[0] = 4000; te2.linia("Nowy cel: Rat (101,100) HP 100%"); T[0] = 4002; pr(te2, 40); T[0] = 4005; te2.linia("Cel Rat zabity na (1, 1).")
wr = telemetria.wczytaj_rekordy(tmp / "ep2")
sprawdz("wczytaj_rekordy czyta epizody z jsonl", [r["typ"] for r in wr] == ["epizod_celu"])
import statystyki
txt = statystyki.raport(wr, 4010, 1)
sprawdz("statystyki: tabela i lista", "dobicie" in txt and "najgorszych" in txt)

# --- pościg na pamięć: epizod, pokrętła, scalanie zgubiony -> zabity ---
sprawdz("pokrętła pościgu na pamięć: zakresy i kierunek (tylko wydłużać)",
        pokretla.ZAKRESY["POSCIG_PAMIEC_S"] == (3.0, 12.0) and pokretla.ZAKRESY["POSCIG_PAMIEC_POL"] == (4, 14)
        and pokretla.ZAKRESY["POSCIG_PAMIEC"] == (0, 1)
        and pokretla.waliduj({"POSCIG_PAMIEC_S": 5.0}, {"POSCIG_PAMIEC_S": 7.0})[0] == {}
        and pokretla.waliduj({"POSCIG_PAMIEC_S": 9.0}, {"POSCIG_PAMIEC_S": 7.0})[0] == {"POSCIG_PAMIEC_S": 9.0}
        and pokretla.waliduj({"POSCIG_PAMIEC_POL": 6}, {"POSCIG_PAMIEC_POL": 9})[0] == {}
        and pokretla.waliduj({"POSCIG_PAMIEC": 0}, {"POSCIG_PAMIEC": True})[0] == {}
        and pokretla.waliduj({"POSCIG_PAMIEC": 0})[0] == {"POSCIG_PAMIEC": 0}
        and pokretla.waliduj({"POSCIG_PAMIEC_S": 20.0})[0] == {})

tp = telemetria.Telemetria(tmp / "pam1", zegar=zegar)
T[0] = 5000; tp.linia("Nowy cel: Rat (101,100) HP 100%")
T[0] = 5002; pr(tp, 60, exp=1000)
T[0] = 5005; pr(tp, 25, exp=1000)
T[0] = 5006; tp.linia("Cel Rat zniknął z widoku żywy (108,100) HP 25%, wektor +2,+0: ścigam na pamięć do (112,100), do 7 s.")
sprawdz("zniknięcie żywego z pościgiem na pamięć nie zamyka epizodu (brak wpisu zgubiony)", not ep_typy(tp) and tp.ep is not None)
T[0] = 5008; tp.zdarzenie("poscig_pamiec_koniec", cel="Rat", id=7, wynik="odnaleziony", powod="w_widoku", czas=2.0, kroki=5, odl=2)
T[0] = 5008; tp.linia("Nowy cel: Rat (110,100) HP 25%")
sprawdz("odnaleziony: ten sam epizod trwa dalej (bez wpisu zgubiony)", not ep_typy(tp) and tp.ep is not None and tp.ep["n"] == "Rat")
T[0] = 5012; tp.linia("Cel Rat zabity na (110, 100).")
e = ep_typy(tp)
sprawdz("epizod zabity z odnaleziony_po_zniknieciu, czas do zabicia liczony od 1. trafienia",
        len(e) == 1 and e[0]["wynik"] == "zabity" and e[0]["odnaleziony_po_zniknieciu"] is True and e[0]["do_zab_s"] == 10.0)
dp = telemetria.dobicie(tp.rek)
sprawdz("dobicie: odnalezione po zniknięciu liczone, wskaźnik 100%", dp["odnalezione"] == 1 and dp["wskaznik"] == 100 and dp["zgubione"] == 0)

tl = telemetria.Telemetria(tmp / "pam2", zegar=zegar)
T[0] = 5100; tl.linia("Nowy cel: Rat (101,100) HP 100%")
T[0] = 5102; pr(tl, 30, exp=1000)
T[0] = 5103; tl.linia("Cel Rat zniknął z widoku żywy (108,100) HP 30%, wektor +2,+0: ścigam na pamięć do (112,100), do 7 s.")
T[0] = 5110; tl.zdarzenie("poscig_pamiec_koniec", cel="Rat", id=7, wynik="limit", powod="czas", czas=7.0, kroki=9, odl=6)
e = ep_typy(tl)
sprawdz("limit pościgu na pamięć: epizod zgubiony (cel nie wrócił)", len(e) == 1 and e[0]["wynik"] == "zgubiony"
        and "odnaleziony_po_zniknieciu" not in e[0])
zab = {"typ": "epizod_celu", "n": "Rat", "id": e[0]["id"], "wynik": "zabity", "trafiony": True, "t": e[0]["t"] + 30,
       "hp0": 30, "hp_porz": None, "do_zab_s": 5.0}
sc = telemetria.scal_epizody([e[0], zab])
sprawdz("scal: zgubiony po pościgu na pamięć + zabity tego id w 45 s = 1 zabity", len(sc) == 1 and sc[0]["wynik"] == "zabity")
sprawdz("zdarzenia poscig_pamiec_* zapisane w rekordach", any(r["typ"] == "poscig_pamiec_koniec" for r in tl.rek))

# --- loot w walce: zdarzenia i pokrętła ---
tw = telemetria.Telemetria(tmp, zegar=zegar)
tw.zdarzenie("loot_w_walce_krok", krok="otwarcie", poz=[1, 2], kroki=1, czas=0.1, hp=100)
tw.zdarzenie("loot_w_walce_krok", krok="koniec", opis="ok", poz=[1, 2], kroki=3, czas=2.0)
tw.zdarzenie("loot_w_walce_przerwany", powod="stykajace", poz=[1, 2], kroki=1, czas=0.5)
tw.zdarzenie("loot_w_walce_przerwany", powod="atak_wylaczony", poz=[1, 2], kroki=1, czas=0.5)
lw = telemetria.loot_w_walce(list(tw.rek))
sprawdz("loot_w_walce: agregacja kroków, ukończonych i przerwań z powodem",
        lw == {"kroki": 1, "ukonczone": 1, "przerwane": {"stykajace": 1, "atak_wylaczony": 1}, "atak_wylaczony": 1})
dom = {"LOOT_W_WALCE": 1, "LOOT_W_WALCE_HP": 70, "LOOT_W_WALCE_STYKAJACE": 2}
okp, bl = pokretla.waliduj({"LOOT_W_WALCE": 0, "LOOT_W_WALCE_HP": 60, "LOOT_W_WALCE_STYKAJACE": 3}, dom)
sprawdz("pokrętła lootu w walce: analityk nie wyłączy ani nie poluzuje (kierunek)", okp == {} and len(bl) == 3)
okp, bl = pokretla.waliduj({"LOOT_W_WALCE_HP": 80, "LOOT_W_WALCE_STYKAJACE": 1}, dom)
sprawdz("pokrętła lootu w walce: zaostrzenie dozwolone", okp == {"LOOT_W_WALCE_HP": 80, "LOOT_W_WALCE_STYKAJACE": 1})
okp, bl = pokretla.waliduj({"LOOT_W_WALCE": 0})
sprawdz("pokrętła lootu w walce: ręczny plik może wyłączyć (tylko ZAKRESY)", okp == {"LOOT_W_WALCE": 0})
# 11.10: POSCIG_PAMIEC_MAKS_ODL (pokrętło, kierunek jak sąsiednie POSCIG_PAMIEC*) i liczniki puszczeń z poscig_koniec
sprawdz("pokrętło POSCIG_PAMIEC_MAKS_ODL: zakres 2-10, analityk nie obniży, może podnieść, ręczny plik tylko ZAKRESY",
        pokretla.ZAKRESY["POSCIG_PAMIEC_MAKS_ODL"] == (2, 10) and pokretla.KIERUNEK["POSCIG_PAMIEC_MAKS_ODL"] == "nie_nizej"
        and pokretla.waliduj({"POSCIG_PAMIEC_MAKS_ODL": 3}, {"POSCIG_PAMIEC_MAKS_ODL": 5})[0] == {}
        and pokretla.waliduj({"POSCIG_PAMIEC_MAKS_ODL": 7}, {"POSCIG_PAMIEC_MAKS_ODL": 5})[0] == {"POSCIG_PAMIEC_MAKS_ODL": 7}
        and pokretla.waliduj({"POSCIG_PAMIEC_MAKS_ODL": 3})[0] == {"POSCIG_PAMIEC_MAKS_ODL": 3}
        and pokretla.waliduj({"POSCIG_PAMIEC_MAKS_ODL": 30})[0] == {})
tp = telemetria.Telemetria(Path(tempfile.mkdtemp()), zegar=zegar)
tp.zdarzenie("poscig_koniec", puszczenia={"ostatni": 2, "strazni": 1}, t_pierwszy_krok=0.31, kliki_ataku=1)
tp.zdarzenie("poscig_koniec", puszczenia={"ostatni": 1}, t_pierwszy_krok=None, kliki_ataku=0)
sprawdz("telemetria: licznik puszczeń per powód i t_pierwszy_krok z poscig_koniec (pola zdarzenia bez zmian)",
        tp.puszczenia_sesja == {"ostatni": 3, "strazni": 1} and list(tp.pierwszy_krok_sesja) == [0.31]
        and tp.rek[-2]["puszczenia"] == {"ostatni": 2, "strazni": 1} and tp.rek[-2]["kliki_ataku"] == 1)


# --- P4: zapis tylko na żywo, blokada pisarza, pid/sesja, ścisły RE_LOOT ---
def _pliki(k): return list(Path(k).glob("telemetria-*.jsonl"))
_env0 = {k: os.environ.get(k) for k in ("RETRONIC_TELEMETRIA", "RETRONIC_TESTY")}
_src0 = telemetria._src
telemetria._src = lambda: "mozg"            # R0a: zapis domyślny tylko w procesie mozg.py; test udaje mozg
try:
    # 1. przy RETRONIC_TESTY (nawet z RETRONIC_TELEMETRIA=1) i bez zmiennej: brak pliku
    k1 = Path(tempfile.mkdtemp())
    os.environ["RETRONIC_TELEMETRIA"] = "1"; os.environ["RETRONIC_TESTY"] = "1"
    te = _Tele(k1, zegar=zegar); te.zdarzenie("info", tekst="x")
    sprawdz("P4-1a RETRONIC_TESTY: brak zapisu i brak pliku", te.zapis is False and not _pliki(k1) and not (k1 / "telemetria.lock").exists())
    del os.environ["RETRONIC_TESTY"]; del os.environ["RETRONIC_TELEMETRIA"]
    te = _Tele(k1, zegar=zegar); te.zdarzenie("info", tekst="x")
    sprawdz("P4-1b bez RETRONIC_TELEMETRIA: brak zapisu", te.zapis is False and not _pliki(k1))
    sprawdz("P4-1c zapis=False jawnie nie pisze mimo środowiska", _Tele(k1, zegar=zegar, zapis=False).zapis is False)
    # 2. dwa obiekty z RETRONIC_TELEMETRIA=1 w tym samym katalogu: pisze tylko pierwszy (inny deskryptor = inny "proces")
    os.environ["RETRONIC_TELEMETRIA"] = "1"
    k2 = Path(tempfile.mkdtemp())
    t1 = _Tele(k2, zegar=zegar)
    sprawdz("P4-2a pierwszy pisze", t1.zapis is True and k2.as_posix() in [str(k) for k in telemetria._BLOKADY])
    telemetria._BLOKADY.clear()          # symulacja: drugi proces nie ma wpisu w słowniku, ma własny deskryptor
    t2 = _Tele(k2, zegar=zegar)
    sprawdz("P4-2b drugi nie pisze (blokada zajęta)", t2.zapis is False)
    t1.zdarzenie("info", tekst="a"); t2.zdarzenie("info", tekst="b")
    wiersze = [json.loads(l) for f in _pliki(k2) for l in f.read_text().splitlines()]
    sprawdz("P4-2c w pliku tylko rekordy pierwszego, z pid/sesja/src",
            len(wiersze) == 1 and wiersze[0]["tekst"] == "a" and wiersze[0]["pid"] == os.getpid()
            and "sesja" in wiersze[0] and wiersze[0]["src"] in ("mozg", "cavebot", "test"))
    # drugi obiekt w tym samym procesie (słownik _BLOKADY znany) nie jest odrzucany
    telemetria._BLOKADY.clear()
    k3 = Path(tempfile.mkdtemp())
    ta = _Tele(k3, zegar=zegar); tb = _Tele(k3, zegar=zegar)
    sprawdz("P4-2d ten sam proces: oba obiekty mogą pisać", ta.zapis and tb.zapis)
    for f in telemetria._BLOKADY.values():
        os.close(f)
    telemetria._BLOKADY.clear()
    # R0a: ten sam proces, ale nie mozg.py (skrypt pomocniczy, test bez RETRONIC_TESTY): brak zapisu mimo RETRONIC_TELEMETRIA=1
    telemetria._src = lambda: "cavebot"
    k4 = Path(tempfile.mkdtemp())
    te = _Tele(k4, zegar=zegar); te.zdarzenie("info", tekst="x")
    sprawdz("R0a-1 proces inny niż mozg.py: brak zapisu, pliku i blokady",
            te.zapis is False and not _pliki(k4) and not (k4 / "telemetria.lock").exists())
    telemetria._src = lambda: "mozg"
    k5 = Path(tempfile.mkdtemp())
    te = _Tele(k5, zegar=zegar); te.zdarzenie("info", tekst="x")
    sprawdz("R0a-2 mozg.py z RETRONIC_TELEMETRIA=1 nadal zapisuje (produkcja bez zmian)", te.zapis is True and len(_pliki(k5)) == 1)
    for f in telemetria._BLOKADY.values():
        os.close(f)
    telemetria._BLOKADY.clear()
finally:
    telemetria._src = _src0
    for k, v in _env0.items():
        if v is None: os.environ.pop(k, None)
        else: os.environ[k] = v
# 3. RE_LOOT
R = telemetria.RE_LOOT
sprawdz("P4-3a RE_LOOT nie łapie komunikatów pośrednich",
        not any(R.match(x) for x in ("Loot: 4 pola puste, szukam dalej wśród pozostałych (runda 2).",
                                     "Loot: zwłoki (1, 2) bez okna (1x): wstrzymane do końca walki, jedna próba po walce.",
                                     "Loot: stoję na zwłokach, schodzę na sąsiednie pole i próbuję ponownie.",
                                     "Loot: puste pola, nic żywego w widoku, ponawiam od razu na pozostałych polach.")))
sprawdz("P4-3b RE_LOOT łapie wyniki", all(R.match(f"Loot: {w}") for w in
        ("ok", "pelny_plecak", "brak_okna", "okno_niewidoczne", "daleko", "brak_plecaka", "przerwany")))
tl_ = _Tele(Path(tempfile.mkdtemp()), zegar=zegar, zapis=False)
tl_.linia("Loot: 4 pola puste, szukam dalej wśród pozostałych (runda 2)."); tl_.linia("Loot: stoję na zwłokach, schodzę.")
sprawdz("P4-3c komunikaty pośrednie nie tworzą zdarzenia loot", not [r for r in tl_.rek if r["typ"] == "loot"])
tl_.linia("Loot: zwłoki (1, 2) bez okna (2x): wstrzymane do końca walki, porzucone.")
sprawdz("P4-3d loot_wstrzymany z polem zwloki i n",
        [(r["zwloki"], r["n"]) for r in tl_.rek if r["typ"] == "loot_wstrzymany"] == [([1, 2], 2)])
tl_.linia("Loot: pelny_plecak")
sprawdz("P4-3e Loot: pelny_plecak jest lootem", [r["wynik"] for r in tl_.rek if r["typ"] == "loot"] == ["pelny_plecak"])


# --- R0a: postać "Ja" nie zapisuje nic (nawet przy jawnym zapis=True) ---
kj = Path(tempfile.mkdtemp())
tj = _Tele(kj, zegar=zegar, zapis=True)
tj.nazwa_postaci = "Ja"
tj.zdarzenie("pietra_krok", z_od=8, z_do=9)
sprawdz("R0a-3 nazwa Ja: zdarzenie w pamięci, brak pliku", len(tj.rek) == 1 and not _pliki(kj))
kj2 = Path(tempfile.mkdtemp())
tj2 = _Tele(kj2, zegar=zegar, zapis=True)
cbj = types.SimpleNamespace(cel=None, stan="IDZ", ignorowane={}, zegar=zegar, droga_bez_blokad=0,
                            postac=types.SimpleNamespace(nazwa="Ja"))
tj2.probka(cbj, {"proc": 90}, (100, 100, 7), [])
tj2.zdarzenie("pietra_start", z_od=8, z_do=9)
sprawdz("R0a-4 cb.postac.nazwa Ja: brak pliku", not _pliki(kj2))
kj3 = Path(tempfile.mkdtemp())
tj3 = _Tele(kj3, zegar=zegar, zapis=True)
cbj.postac = types.SimpleNamespace(nazwa="Karol")
tj3.probka(cbj, {"proc": 90}, (100, 100, 7), [{"nazwa": "Ja", "gracz": True, "x": 100, "y": 100, "z": 7, "id": 1, "hp": 90}])
tj3.zdarzenie("pietra_start", z_od=8, z_do=9)
sprawdz("R0a-5 własny wpis Ja w stworach: brak pliku", not _pliki(kj3))
kj4 = Path(tempfile.mkdtemp())
tj4 = _Tele(kj4, zegar=zegar, zapis=True)
tj4.probka(cbj, {"proc": 90}, (100, 100, 7), [])
sprawdz("R0a-6 zwykła postać zapisuje", len(_pliki(kj4)) == 1)

# --- R0b: ruch_okno ---
T0 = [1000.0]
tr = _Tele(Path(tempfile.mkdtemp()), zegar=lambda: T0[0], zapis=False)
def _tik(t, poz, stan="IDZ", powod="inne", kl=0, st=0):
    T0[0] = t
    return tr.ruch_tick(t, poz, stan, powod, kl, st)
_tik(1000.0, (100, 100, 8))
_tik(1001.0, (101, 100, 8), kl=1)                       # marsz 1 s, 1 pole
_tik(1002.0, (101, 100, 8), powod="schody")             # stoi 1 s (schody)
_tik(1004.5, (101, 100, 8), powod="patrol_postoj")      # stoi 2,5 s + luka 2,5 s
_tik(1005.5, (102, 101, 8), kl=2, st=3)                 # marsz 1 s, 1 pole (skos)
_tik(1006.5, (102, 101, 9))                             # zmiana piętra
_tik(1007.0, (102, 101, 9), stan="WALKA", powod="walka")
r_ = _tik(1031.0, (102, 101, 9), stan="WALKA", powod="walka", kl=5, st=3)   # >= 30 s od początku: zamknięcie okna
sprawdz("R0b-1 okno zamknięte po 30 s i zapisane jako ruch_okno", r_ is not None and r_["typ"] == "ruch_okno" and r_["okno_s"] == 31.0)
sprawdz("R0b-2 czas marszu i stania w IDZ", r_["stany"]["IDZ"] == [3.0, 3.5])
sprawdz("R0b-3 przyczyny stania", r_["powody_s"].get("schody") == 1.0 and r_["powody_idz_s"].get("patrol_postoj") == 2.5
        and r_["powody_s"].get("walka") == 24.5 and "walka" not in r_["powody_idz_s"])
sprawdz("R0b-4 luki ticka > 1,5 s (2,5 s i 24 s)", r_["luki"] == 2 and r_["luka_max"] == 24.0 and r_["luki_s"] == 26.5)
sprawdz("R0b-5 kroki, zmiany pięter, kliki, strzałki", r_["kroki"] == 2 and r_["zmiany_pietra"] == 1
        and r_["kliki"] == 5 and r_["strzalki"] == 3)
r2_ = _tik(1032.0, (102, 101, 9), stan="WALKA", powod="walka", kl=5, st=3)
sprawdz("R0b-6 po zamknięciu liczniki od zera", r2_ is None and tr._ruch["ticki"] == 1 and tr._ruch["kroki"] == 0)
_tik(1100.0, (50, 50, 8), kl=5, st=3)                   # teleport: pola nie liczone
sprawdz("R0b-7 skok > RUCH_SKOK_MAX nie dolicza pól", tr._ruch["kroki"] == 0)

# próbka wczesna: bez A*, z polem wczesna, nie zasila epizodów
tw_ = _Tele(Path(tempfile.mkdtemp()), zegar=zegar, zapis=False)
cbw = types.SimpleNamespace(cel=None, stan="IDZ", ignorowane={}, zegar=zegar, droga_bez_blokad=0,
                            droga=lambda *a, **k: (_ for _ in ()).throw(AssertionError("A* w próbce wczesnej")),
                            postac=types.SimpleNamespace(nazwa="Karol"))
rw = tw_.probka(cbw, {"proc": 90}, (100, 100, 7), [{"nazwa": "Rat", "gracz": False, "x": 101, "y": 100, "z": 7, "id": 5, "hp": 80}],
                wczesna="ogien_wyjdz")
sprawdz("R0b-8 próbka wczesna: pole wczesna, bez A*", rw is not None and rw["wczesna"] == "ogien_wyjdz" and "droga" not in rw["stwory"][0])

print("WYNIK:", "OK" if ok else "BŁĄD")
sys.exit(0 if ok else 1)
