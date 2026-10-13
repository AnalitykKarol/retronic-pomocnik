import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import telemetria, analityk_poscigu as ap

ok = True
def sprawdz(opis, war, info=""):
    global ok
    print(("OK   " if war else "BŁĄD ") + opis); ok = ok and bool(war)

T = [1_700_000_000.0]
zegar = lambda: T[0]
tmp = Path(tempfile.mkdtemp())
logi = tmp / "logi"
tele = telemetria.Telemetria(tmp / "t", zegar=zegar, zapis=False)
powiadomione = []
ap.powiadom.powiadom = lambda *a, **k: powiadomione.append(a)
wywolania = []
odp = [json.dumps({"ocena": "ok", "wnioski": [], "hipotezy_do_zmierzenia": []})]
def model(prompt, system):
    wywolania.append(prompt)
    return odp[0], {"total_cost_usd": 0.002}
an = ap.AnalitykPoscigu(tele, model, log=lambda *a: None, zegar=zegar, logi=logi, cykl_s=120)

def poscig(t, cel="Rat", kroki=5, czas=4.0, powod="okno", o0=4, o1=4, tryb="stuk", odrz=0, hp=20):
    tele.rek.append({"t": t - czas - 0.1, "typ": "poscig_start", "cel": cel, "odl": o0, "hp_celu": hp})
    tele.rek.append({"t": t, "typ": "poscig_koniec", "cel": cel, "kroki": kroki, "czas": czas, "powod": powod,
                     "odl_start": o0, "odl_koniec": o1, "kroki_na_s": round(kroki / czas, 2), "wyslane": kroki + odrz,
                     "zmiany_pozycji": kroki, "ponowione": 0, "odrzucone": odrz, "ponow_brak": 0, "tryb": tryb,
                     "trzymane_s": czas if tryb == "trzymaj" else 0.0, "zmiany_kierunku": 3 if tryb == "trzymaj" else 0,
                     "dec_med": 0.1, "dec_max": 0.2, "lat_med": 0.4, "lat_max": 0.5})
def probka(t, poz, stan="WALKA"):
    tele.rek.append({"t": t, "typ": "probka", "stan": stan, "poz": list(poz), "hp": 100, "mana": 10, "stwory": []})

# --- cykl i konfiguracja ---
sprawdz("cykl min 60 s", ap.AnalitykPoscigu(tele, model, zegar=zegar, logi=logi, cykl_s=5).cykl_s == 60)
sprawdz("cykl domyślnie 120 s", an.cykl_s == 120)

# --- parowanie i statystyki ---
t0 = T[0]
poscig(t0 + 10, tryb="stuk", kroki=6, czas=4.0, o0=4, o1=2, powod="odl<=1")
poscig(t0 + 20, tryb="trzymaj", kroki=10, czas=5.0, o0=5, o1=7, odrz=0)
poscig(t0 + 30, tryb="stuk", kroki=4, czas=4.0, o0=3, o1=4, odrz=2)
ps = ap.poscigi(list(tele.rek))
sprawdz("parowanie start/koniec", len(ps) == 3 and all(p["start"] is not None for p in ps) and ps[0]["start"]["hp_celu"] == 20)
T[0] = t0 + 40
s = ap.stat_okna(list(tele.rek))
sprawdz("statystyki: liczba, tryby, powody", s["poscigow"] == 3 and set(s["tryby"]) == {"stuk", "trzymaj"}
        and s["powody_wyjsc"] == {"odl<=1": 1, "okno": 2})
sprawdz("statystyki: odrzucone stuk", s["tryby"]["stuk"]["odrzucone"] == 2 and s["tryby"]["stuk"]["n"] == 2)
sprawdz("statystyki: trzymane i zmiany kierunku", s["tryby"]["trzymaj"]["trzymane_s"] == 5.0
        and s["tryby"]["trzymaj"]["zmiany_kierunku"] == 3 and s["puszczanie_klawisza"]["naciski_z_postoju"] == 7)
sprawdz("statystyki: dobicie vs inne, bez postępu", s["koniec"]["dobicie"] == 1 and s["koniec"]["bez_dojscia_okno_lub_brak_ruchu"] == 2
        and s["bez_postepu"]["poscigow"] == 2 and s["bez_postepu"]["kroki"] == 14)
r = ap.roznice_trybow(s)
sprawdz("różnice trzymaj vs stuk", r and r["n"] == {"trzymaj": 1, "stuk": 2} and r["odrzucone_proc"]["stuk"] == 17)
sprawdz("różnice: brak gdy jeden tryb", ap.roznice_trybow(ap.stat_okna([x for x in tele.rek if x.get("tryb") != "trzymaj"])) is None)
gor = ap.najgorsze(list(tele.rek), None, 5)
sprawdz("najgorsze: bez postępu na górze", gor and gor[0]["odl"] in ([5, 7], [3, 4]) and len(gor) <= 5)

# --- oscylacje ---
base = T[0]
for i, p in enumerate([(10, 10, 7), (11, 10, 7), (10, 10, 7), (11, 10, 7)]):
    probka(base + i * 1.0, p)
o = ap.oscylacje([r for r in tele.rek if r["typ"] == "probka"])
sprawdz("oscylacja A-B-A-B w 3 s wykryta", len(o) == 1 and o[0]["poz"] == [[10, 10], [11, 10]], o)
chodzi = [{"t": base + i, "typ": "probka", "poz": [10 + i, 10, 7]} for i in range(6)]
sprawdz("marsz prosty to nie oscylacja", ap.oscylacje(chodzi) == [])
wolne = [{"t": base + i * 3, "typ": "probka", "poz": p} for i, p in enumerate([(1, 1, 7), (2, 1, 7), (1, 1, 7), (2, 1, 7)])]
sprawdz("A-B-A-B rozciągnięte na 9 s: nie", ap.oscylacje(wolne) == [])
dlugi = [{"t": base + i, "typ": "probka", "poz": (1 + i % 2, 1, 7)} for i in range(8)]
sprawdz("seria A-B-A-B-A-B... to jedna oscylacja", len(ap.oscylacje(dlugi)) == 1)

# --- okno / warunek wywołania ---
an2 = ap.AnalitykPoscigu(telemetria.Telemetria(tmp / "t2", zegar=zegar, zapis=False), model, log=lambda *a: None,
                         zegar=zegar, logi=tmp / "l2")
t = T[0]
def zdarz(an_, **kw):
    r = {"t": T[0], "typ": "poscig_koniec", "cel": "Rat", "kroki": 3, "czas": 3, "powod": "okno", "odl_start": 3,
         "odl_koniec": 3, "kroki_na_s": 1.0, "tryb": "stuk", **kw}
    an_.tele.rek.append(r)
kr = lambda an_: [r for r in an_.tele.rek if r["t"] >= T[0] - 300]
zdarz(an2); T[0] += 10; zdarz(an2)
sprawdz("2 pościgi w 5 min: bez modelu", an2.wymaga_modelu(kr(an2)) == (False, "za_malo"))
T[0] += 10; zdarz(an2)
sprawdz("3 pościgi w 5 min: model", an2.wymaga_modelu(kr(an2))[0] is True)
an3 = ap.AnalitykPoscigu(telemetria.Telemetria(tmp / "t3", zegar=zegar, zapis=False), model, log=lambda *a: None,
                         zegar=zegar, logi=tmp / "l3")
zdarz(an3, powod="obcy_gracz")
sprawdz("nowe zdarzenie (obcy gracz) mimo 1 pościgu: model", an3.wymaga_modelu(kr(an3)) == (True, "zdarzenie"))
an4 = ap.AnalitykPoscigu(telemetria.Telemetria(tmp / "t4", zegar=zegar, zapis=False), model, log=lambda *a: None,
                         zegar=zegar, logi=tmp / "l4")
an4.tele.rek.append({"t": T[0], "typ": "utkniecie", "stan": "WALKA", "poz": [1, 1, 7], "s": 20, "stwory": []})
sprawdz("utknięcie: model", an4.wymaga_modelu(kr(an4))[0] is True)
sprawdz("okno 5 min: stare pościgi nie liczą się", an2.wymaga_modelu([r for r in an2.tele.rek if r["t"] >= T[0] + 400])[0] is False)

# --- hash/pomijanie ---
odp[0] = json.dumps({"ocena": "uwaga", "wnioski": [{"co": "Pościg stukiem gubi kroki: 25% odrzuconych",
                     "dowod": "odrzucone 2/6", "skutek": "dłuższy pościg", "propozycja": "POSCIG_BRAK_ZMIANY w górę",
                     "pewnosc": 0.6}], "hipotezy_do_zmierzenia": ["zmierzyć lat przy tym polu"]})
T[0] += 10; an.tele.rek.append({"t": T[0], "typ": "poscig_koniec", "cel": "Rat", "kroki": 3, "czas": 3, "powod": "okno",
                                "odl_start": 3, "odl_koniec": 3, "kroki_na_s": 1.0, "tryb": "stuk"})
w1 = an.cykl(T[0])
sprawdz("pierwszy cykl woła model i zapisuje", w1["status"] == "ok" and len(wywolania) == 1 and w1["ocena"] == "uwaga")
n = len(wywolania)
w2 = an.cykl(T[0] + 10)
sprawdz("bez nowych zdarzeń: model nie wołany", w2["status"] == "pominiete" and len(wywolania) == n and an.pominiete == 1)
an.znak = float("-inf")     # nowe zdarzenie bez zmiany danych = ten sam hash
w3 = an.cykl(T[0] + 10)
sprawdz("ten sam hash wejścia: pominięte", w3["status"] == "pominiete" and w3["powod"] == "ten_sam_hash")
sprawdz("koszt zliczany", abs(an.koszt - 0.002) < 1e-9)

# --- zapis, dedup, md/jsonl ---
md = (logi / "poscig-wnioski.md").read_text()
jl = [json.loads(l) for l in (logi / "poscig-wnioski.jsonl").read_text().splitlines()]
sprawdz("md ma nagłówek czasu i wniosek", md.startswith("\n## ") and "POSCIG_BRAK_ZMIANY" in md and "do zmierzenia" in md)
sprawdz("jsonl: 1 wiersz z wnioskami i kosztem", len(jl) == 1 and jl[0]["wnioski"][0]["pewnosc"] == 0.6 and jl[0]["koszt"] == 0.002)
T[0] += 130
an.tele.rek.append({"t": T[0], "typ": "poscig_koniec", "cel": "Rat", "kroki": 9, "czas": 7, "powod": "brak_ruchu",
                    "odl_start": 3, "odl_koniec": 5, "kroki_na_s": 1.2, "tryb": "stuk"})
odp[0] = json.dumps({"ocena": "uwaga", "wnioski": [
    {"co": "Pościg stukiem gubi kroki: 30% odrzuconych", "dowod": "x", "skutek": "y", "propozycja": "z", "pewnosc": 0.5},
    {"co": "Pościg kończy się bez postępu przy odległości 5", "dowod": "a", "skutek": "b", "propozycja": "c", "pewnosc": 0.4}],
    "hipotezy_do_zmierzenia": ["zmierzyć lat przy tym polu"]})
w4 = an.cykl(T[0])
sprawdz("deduplikacja: podobny wniosek pominięty, nowy zapisany",
        w4["powtorzone"] == 1 and [x["co"][:12] for x in w4["wnioski"]] == ["Pościg kończ"] and w4["hipotezy"] == [])
md2 = (logi / "poscig-wnioski.md").read_text()
sprawdz("md: duplikat nie dopisany", md2.count("gubi kroki") == 1 and md2.count("bez postępu przy odległości 5") == 1)
sprawdz("podobne(): różne wnioski nie są podobne", not ap.podobne("Oscylacje na polu 20", "Zgubienie celu przy ścianie"))

# --- alerty: problem -> alert + powiadomienie, dedup 10 min ---
odp[0] = json.dumps({"ocena": "problem", "wnioski": [{"co": "Oscylacja A-B-A-B kasuje 40% pościgów", "dowod": "6 oscylacji",
                     "skutek": "utrata dobić", "propozycja": "POSCIG_ANTYCYP_PO", "pewnosc": 0.8}], "hipotezy_do_zmierzenia": []})
T[0] += 130
an.tele.rek.append({"t": T[0], "typ": "poscig_koniec", "cel": "Rat", "kroki": 2, "czas": 3, "powod": "okno",
                    "odl_start": 3, "odl_koniec": 4, "kroki_na_s": 0.7, "tryb": "trzymaj"})
an.cykl(T[0])
al = (logi / "obserwator-alerty.log").read_text().splitlines()
sprawdz("problem: linia w alertach (format jak Obserwatora)", len(al) == 1 and "[problem] Pościg: Oscylacja" in al[0]
        and al[0][2] == ":" and "| 6 oscylacji" in al[0])
sprawdz("problem: powiadomienie normal", len(powiadomione) == 1 and powiadomione[0][2] == "normal")
T[0] += 130
an.tele.rek.append({"t": T[0], "typ": "poscig_koniec", "cel": "Rat", "kroki": 2, "czas": 3, "powod": "okno",
                    "odl_start": 3, "odl_koniec": 4, "kroki_na_s": 0.7, "tryb": "trzymaj"})
odp[0] = odp[0].replace("40%", "41%")
an.cykl(T[0])
sprawdz("dedup alertu i powiadomienia 10 min", len((logi / "obserwator-alerty.log").read_text().splitlines()) == 1
        and len(powiadomione) == 1)
T[0] += 700
for k in range(3):
    an.tele.rek.append({"t": T[0] + k, "typ": "poscig_koniec", "cel": "Rat", "kroki": 2, "czas": 3, "powod": "okno",
                        "odl_start": 3, "odl_koniec": 4, "kroki_na_s": 0.7, "tryb": "trzymaj"})
T[0] += 3
odp[0] = odp[0].replace("41%", "43%")
an.cykl(T[0])
sprawdz("po 10 min alert i powiadomienie znowu", len((logi / "obserwator-alerty.log").read_text().splitlines()) == 2
        and len(powiadomione) == 2)

# --- walidacja JSON ---
w = ap.waliduj('```json\n{"ocena":"Uwaga","wnioski":[{"co":"a","dowod":"b","skutek":"c","propozycja":"d","pewnosc":1.7},'
               '{"co":"","pewnosc":0.5},"zly",{"co":"e","pewnosc":"x"}],"hipotezy_do_zmierzenia":["h",""]}\n```')
sprawdz("walidacja: ocena normalizowana, pewność ścięta, puste odrzucone",
        w and w["ocena"] == "uwaga" and [x["pewnosc"] for x in w["wnioski"]] == [1.0, 0.0] and w["hipotezy"] == ["h"])
sprawdz("walidacja: zła ocena", ap.waliduj('{"ocena":"zle","wnioski":[]}') is None)
sprawdz("walidacja: nie-JSON", ap.waliduj("bla bla") is None)
sprawdz("walidacja: wnioski nie lista", ap.waliduj('{"ocena":"ok","wnioski":"x"}') is None)
sprawdz("walidacja: limit 5 wniosków", len(ap.waliduj(json.dumps({"ocena": "ok", "wnioski": [{"co": f"w{i}"} for i in range(9)]}))["wnioski"]) == 5)
an5 = ap.AnalitykPoscigu(an.tele, lambda p, s: ("nie json", {}), log=lambda *a: None, zegar=zegar, logi=tmp / "l5")
T[0] += 10; an5.tele.rek.append({"t": T[0], "typ": "utkniecie", "stan": "WALKA", "poz": [1, 1, 7], "s": 20, "stwory": []})
sprawdz("nie-JSON z modelu: blad_json, nic nie zapisane", an5.cykl(T[0])["status"] == "blad_json"
        and not (tmp / "l5" / "poscig-wnioski.md").exists())

# --- limit/h i rotacja ---
an6 = ap.AnalitykPoscigu(telemetria.Telemetria(tmp / "t6", zegar=zegar, zapis=False), model, log=lambda *a: None,
                         zegar=zegar, logi=tmp / "l6", limit_h=2)
st = []
for i in range(4):
    T[0] += 5
    an6.tele.rek.append({"t": T[0], "typ": "utkniecie", "stan": "WALKA", "poz": [i, 1, 7], "s": 20, "stwory": []})
    st.append(an6.cykl(T[0])["status"])
sprawdz("limit wywołań/h", st == ["ok", "ok", "limit_h", "limit_h"], st)
plik = tmp / "duzy.md"
plik.write_text("".join(f"\n## wpis {i}\n- " + "x" * 1000 + "\n" for i in range(400)))
ap._przytnij_plik(plik)
sprawdz("rotacja md do <= 200 KB, zaczyna od nagłówka", plik.stat().st_size <= ap.MD_MAX and plik.read_text().startswith("## wpis"))


# --- okna różne przy danych z 40 min (pamięć sięga tylko 4 min; reszta z pliku dnia) ---
import time as _t
katf = tmp / "tf"; katf.mkdir()
tf = telemetria.Telemetria(katf, zegar=zegar, zapis=False)
T[0] += 4000
stare = []
def _p(t, powod="okno", cel="Rat"):
    return {"t": t, "typ": "poscig_koniec", "cel": cel, "kroki": 5, "czas": 4.0, "powod": powod, "odl_start": 4,
            "odl_koniec": 4, "kroki_na_s": 1.2, "wyslane": 5, "odrzucone": 0, "tryb": "stuk"}
for k in range(40):                       # co minutę przez 40 min (wstecz od T)
    stare.append(_p(T[0] - 2400 + 60 * k))
stare.append(_p(T[0] - 700, "oscylacja"))
with tf._plik(T[0]).open("w") as f:
    for r in stare:
        f.write(json.dumps(r) + "\n")
tf.rek.extend(r for r in stare if r["t"] >= T[0] - 240)      # pamięć nowego procesu: tylko ostatnie 4 min
akf = ap.AnalitykPoscigu(tf, model, log=lambda *a: None, zegar=zegar, logi=tmp / "lf")
df, krf = akf.wejscie(T[0])
k5, k30 = df["okno_krotkie"]["poscigow"], df["okno_dlugie"]["poscigow"]
sprawdz("okna różne: 30 min czyta też plik dnia", k30 > k5 + 10 and k5 <= 5, (k5, k30))
sprawdz("okno długie ma pokrycie ~30 min", df["okno_dlugie"]["pokrycie_s"] >= 1700)
sprawdz("oscylacja z powodu wyjścia liczy się (ze źródłem)", df["okno_dlugie"]["oscylacje"]["liczba"] == 1
        and df["okno_dlugie"]["oscylacje"]["z_wyjscia_pocigu"] == 1 and df["okno_krotkie"]["oscylacje"]["liczba"] == 0)
sprawdz("spójne dane: brak niespójności", df["niespojnosci"] == [])
# --- niespójność danych: problem -> uwaga z adnotacją ---
ident = {"okno_krotkie": {"poscigow": 15, "tryby": {"x": 1}, "powody_wyjsc": {"oscylacja": 2}, "oscylacje": {"liczba": 0}},
         "okno_dlugie": {"poscigow": 15, "tryby": {"x": 1}, "powody_wyjsc": {"oscylacja": 2}, "oscylacje": {"liczba": 0},
                         "pokrycie_s": 1700}}
sprawdz("niespojnosci(): wykrywa identyczne okna i oscylacje", len(ap.niespojnosci(ident)) >= 2)
odp[0] = json.dumps({"ocena": "problem", "wnioski": [{"co": "Błąd agregacji: okna identyczne", "dowod": "oba 15",
                     "skutek": "x", "propozycja": "y", "pewnosc": 0.9}], "hipotezy_do_zmierzenia": []})
akf.znak = float("-inf")
wf = akf.cykl(T[0], wymus=True)
sprawdz("własna niespójność modelu: problem obniżony do uwaga, bez alertu",
        wf["ocena"] == "uwaga" and "[dane niespójne]" in wf["wnioski"][0]["co"] and not (tmp / "lf" / "obserwator-alerty.log").exists())

# --- --raz nie pisze do logi/ ---
sprawdz("moduł nie tworzy plików STOP", not list(tmp.glob("STOP*")))
print("\nWSZYSTKO OK" if ok else "\nSĄ BŁĘDY")
sys.exit(0 if ok else 1)
