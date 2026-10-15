"""Model lokalny (krok B 15.10): numpy-owy model, metryki, budowa zbiorów D1/D2 z telemetrii. Dane syntetyczne, bez bota i gry."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import json, os, sys, tempfile, time
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import numpy as np
from model_lokalny import model as M, zbior as Z, trenuj as T

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK  " if warunek else "FAIL"), nazwa, info)

# --- metryki ---
sprawdz("auc: idealny porządek = 1", M.auc([0, 0, 1, 1], [.1, .2, .8, .9]) == 1.0)
sprawdz("auc: odwrócony = 0", M.auc([0, 0, 1, 1], [.9, .8, .2, .1]) == 0.0)
sprawdz("auc: znany przykład = 0.75", abs(M.auc([0, 0, 1, 1], [.1, .4, .35, .8]) - 0.75) < 1e-12)
sprawdz("auc: remisy = 0.5", M.auc([0, 1, 0, 1], [.5, .5, .5, .5]) == 0.5)
sprawdz("auc: jedna klasa = None", M.auc([1, 1, 1], [.1, .2, .3]) is None)
sprawdz("log-loss p=0.5 = ln2", abs(M.log_loss(np.array([0., 1.]), np.array([.5, .5])) - np.log(2)) < 1e-12)
sprawdz("trafność", M.trafnosc(np.array([0., 1., 1.]), np.array([.2, .9, .4])) == 2 / 3)

# --- model odzyskuje znaną zależność ---
rng = np.random.default_rng(7)
X = rng.normal(size=(3000, 4))
y = (rng.random(3000) < M.sigmoid(2.0 * X[:, 0] - 1.0 * X[:, 1] + 0.3)).astype(float)
lr = M.RegresjaLogistyczna(l2=1.0).fit(X, y)
sprawdz("LR: znak i kolejność wag (x0 dodatnia największa, x1 ujemna, x2/x3 ~0)",
        lr.w[0] > 1.0 and lr.w[1] < -0.4 and abs(lr.w[2]) < 0.2 and abs(lr.w[3]) < 0.2 and lr.w[0] > abs(lr.w[1]), str(np.round(lr.w, 2)))
Xt = rng.normal(size=(2000, 4)); yt = (rng.random(2000) < M.sigmoid(2.0 * Xt[:, 0] - 1.0 * Xt[:, 1] + 0.3)).astype(float)
a_lr = M.auc(yt, lr.predict_proba(Xt))
sprawdz("LR: AUC na świeżych danych > 0.8", a_lr > 0.8, "%.3f" % a_lr)
# interakcja (XOR-podobna): LR nie umie, MLP tak
Xx = rng.normal(size=(3000, 2)); yx = ((Xx[:, 0] * Xx[:, 1]) > 0).astype(float)
Xxt = rng.normal(size=(1500, 2)); yxt = ((Xxt[:, 0] * Xxt[:, 1]) > 0).astype(float)
mlp = M.MLP(ukryte=(16, 16), l2=1.0, epoki=80).fit(Xx, yx)
a_m, a_l = M.auc(yxt, mlp.predict_proba(Xxt)), M.auc(yxt, M.RegresjaLogistyczna().fit(Xx, yx).predict_proba(Xxt))
sprawdz("MLP uczy interakcji (AUC > 0.9), LR ~0.5", a_m > 0.9 and abs(a_l - 0.5) < 0.1, "mlp %.3f lr %.3f" % (a_m, a_l))

# --- determinizm i zapis/odczyt JSON ---
m1 = M.MLP(ukryte=(8,), epoki=20, ziarno=3).fit(Xx, yx); m2 = M.MLP(ukryte=(8,), epoki=20, ziarno=3).fit(Xx, yx)
sprawdz("determinizm: to samo ziarno = te same wagi", all(np.array_equal(a, b) for a, b in zip(m1.W, m2.W)))
m3 = M.MLP(ukryte=(8,), epoki=20, ziarno=4).fit(Xx, yx)
sprawdz("inne ziarno = inne wagi", not np.array_equal(m1.W[0], m3.W[0]))
with tempfile.TemporaryDirectory() as tmp:
    for m, nazwa in ((lr, "lr"), (mlp, "mlp")):
        p = os.path.join(tmp, nazwa + ".json")
        M.zapisz_json(p, m.do_slownika())
        m_wczyt = M.z_slownika(M.wczytaj_json(p))
        Xp = Xt[:200, :m.std.sr.shape[0]] if nazwa == "lr" else Xxt[:200]
        sprawdz("JSON %s: identyczne predykcje po odczycie" % nazwa, np.array_equal(m.predict_proba(Xp), m_wczyt.predict_proba(Xp)))
        sprawdz("JSON %s: predykcja jednej próbki identyczna" % nazwa, m.predict_proba(Xp[0]) == m_wczyt.predict_proba(Xp[0]))
        sprawdz("JSON %s: rozmiar < 100 KB" % nazwa, os.path.getsize(p) < 100 * 1024, str(os.path.getsize(p)))
sprawdz("jedna próbka = ten sam wynik co wiersz z paczki", abs(mlp.predict_proba(Xxt[0]) - mlp.predict_proba(Xxt[:5])[0]) < 1e-12)
Xs = Xxt[0]; t0 = time.perf_counter()
for _ in range(2000): mlp.predict_proba(Xs)
ms = (time.perf_counter() - t0) / 2000 * 1000
sprawdz("inferencja jednej próbki MLP < 0.1 ms", ms < 0.1, "%.4f ms" % ms)

# --- podział po sesjach ---
ses = ["a"] * 10 + ["b"] * 10 + ["c"] * 10 + ["d"] * 10
tt = list(range(40))
mt = T.podzial_sesji(ses, tt, 0.25)
sprawdz("podział: test = ostatnia sesja, bez mieszania sesji", set(np.array(ses)[mt]) == {"d"} and mt.sum() == 10)
mt = T.podzial_sesji(["x"] * 5 + ["y"] * 5, list(range(10)), 0.9)
sprawdz("podział: pierwsza sesja zawsze zostaje w treningu", set(np.array(["x"] * 5 + ["y"] * 5)[mt]) == {"y"})

# --- budowa D1 na małej sztucznej telemetrii ---
def probka(t, ses, stwory, poz=(100, 100, 7)):
    return {"t": t, "typ": "probka", "poz": list(poz), "stwory": stwory, "sesja": ses}
ja = {"n": "Ja", "dx": 0, "dy": 0, "odl": 0, "hp": 100, "gracz": True}
def mob(n, dx, dy, hp=100, **k):
    d = {"n": n, "dx": dx, "dy": dy, "odl": max(abs(dx), abs(dy)), "hp": hp, "gracz": False}; d.update(k); return d
inny_gracz = {"n": "Obcy", "dx": 4, "dy": 0, "odl": 4, "hp": 100, "gracz": True}
R = [
    # sesja 1: dwa trolle, wybrany drugi (pos = 100+3, 100+1), obcy gracz obok, epizod dokładny: zabity w 10 s -> 1
    probka(100.0, 1, [ja, mob("Troll", 1, 0, osiagalny=True, cel=1), mob("Troll", 3, 1, hp=50, osiagalny=False), mob("Rat", 4, 1), inny_gracz]),
    {"t": 101.0, "typ": "nowy_cel", "n": "Troll", "pos": [103, 101], "hp": 50, "sesja": 1},
    {"t": 111.0, "typ": "epizod_celu", "n": "Troll", "id": 5, "wynik": "zabity", "t0": 101.0, "do_zab_s": 10.0, "sesja": 1},
    # ten sam wybór, ale zabity w 20 s -> etykieta 0 (epizod z t0 przesuniętym o 1 s: dopasowanie po nazwie)
    probka(200.0, 1, [ja, mob("Troll", 2, 0)]),
    {"t": 200.5, "typ": "nowy_cel", "n": "Troll", "pos": [102, 100], "hp": 100, "sesja": 1},
    {"t": 220.0, "typ": "epizod_celu", "n": "Troll", "id": 6, "wynik": "zabity", "t0": 201.5, "do_zab_s": 20.0, "sesja": 1},
    # sesja 2: brak próbki w ogóle
    {"t": 300.0, "typ": "nowy_cel", "n": "Rat", "pos": [100, 100], "hp": 100, "sesja": 2},
    # sesja 3: próbka za stara (5 s)
    probka(400.0, 3, [ja, mob("Rat", 1, 0)]),
    {"t": 405.0, "typ": "nowy_cel", "n": "Rat", "pos": [101, 100], "hp": 100, "sesja": 3},
    # sesja 4: próbka bez moba (sam gracz)
    probka(500.0, 4, [ja]),
    {"t": 501.0, "typ": "nowy_cel", "n": "Rat", "pos": [101, 100], "hp": 100, "sesja": 4},
    # sesja 5: pozycja za daleko od każdego kandydata (przesunięcie > MAKS_PRZESUNIECIE)
    probka(600.0, 5, [ja, mob("Rat", 1, 0)]),
    {"t": 601.0, "typ": "nowy_cel", "n": "Rat", "pos": [120, 120], "hp": 100, "sesja": 5},
    # sesja 6: dobre dopasowanie, ale bez epizodu
    probka(700.0, 6, [ja, mob("Rat", 1, 0)]),
    {"t": 701.0, "typ": "nowy_cel", "n": "Rat", "pos": [101, 100], "hp": 100, "sesja": 6},
    # sesja 7: zgubiony -> etykieta 0
    probka(800.0, 7, [ja, mob("Rat", 2, 0, osiagalny=True)]),
    {"t": 801.0, "typ": "nowy_cel", "n": "Rat", "pos": [102, 100], "hp": 100, "sesja": 7},
    {"t": 805.0, "typ": "epizod_celu", "n": "Rat", "id": 9, "wynik": "zgubiony", "t0": 801.0, "do_zab_s": None, "sesja": 7},
]
R.sort(key=lambda r: r["t"])
zb, st = Z.zbuduj_d1(R)
sprawdz("D1: liczby dopasowań (nowy_cel 8)", st["nowy_cel"] == 8 and st["uzyte"] == 3 and st["brak_probki"] == 1
        and st["probka_za_stara"] == 1 and st["brak_kandydatow"] == 1 and st["brak_dopasowania_pozycji"] == 1
        and st["bez_epizodu"] == 1 and st["epizod_dokladny"] == 2 and st["epizod_po_nazwie"] == 1, str(st))
sprawdz("D1: każde nowy_cel policzone dokładnie raz (suma = 8)", sum(st[k] for k in ("brak_probki", "probka_za_stara", "brak_kandydatow",
        "brak_dopasowania_pozycji", "bez_epizodu", "uzyte")) == st["nowy_cel"])
sprawdz("D1: etykiety 1/0/0", zb.y == [1, 0, 0], str(zb.y))
sprawdz("D1: wybrany = drugi troll (kandydaci: 2 trolle + szczur, bez gracza)", zb.wybrany[0] == 1 and len(zb.kandydaci[0]) == 3)
x = dict(zip(zb.nazwy, zb.X[0]))
sprawdz("D1: cechy wybranego (odl 3, |dx| 3, |dy| 1, hp 50, nieosiągalny)",
        (x["odl"], x["adx"], x["ady"], x["hp"], x["osiag_tak"], x["osiag_nie"]) == (3, 3, 1, 50, 0, 1), str(x))
sprawdz("D1: tłum w odl<=2 (szczur dx4,dy1 jest 1 od wybranego; troll dx1 jest 2) = 2", x["inne_w2"] == 2, str(x["inne_w2"]))
sprawdz("D1: odl do innego gracza (dx4,dy0 od trolla dx3,dy1) = 1; nasz wpis (0,0) pomijany", x["odl_gracza"] == 1.0, str(x["odl_gracza"]))
k0 = dict(zip(zb.nazwy, zb.kandydaci[0][0]))
sprawdz("D1: pierwszy kandydat był celem w próbce, osiągalny", k0["byl_celem"] == 1 and k0["osiag_tak"] == 1)
sprawdz("D1: brak innego gracza -> duża odległość", dict(zip(zb.nazwy, zb.X[1]))["odl_gracza"] == Z.DUZA_ODL)
sprawdz("D1: brak osiagalny (None) = obie flagi 0", (dict(zip(zb.nazwy, zb.X[1]))["osiag_tak"], dict(zip(zb.nazwy, zb.X[1]))["osiag_nie"]) == (0, 0))
sprawdz("D1: najbliższy kandydat i flaga wyboru", zb.najblizszy[0] == 0 and st["wybrany_najblizszy"] == 2, str(st["wybrany_najblizszy"]))
sprawdz("D1: sesje w zbiorze", zb.sesja == [1, 1, 7])

# --- budowa D2 ---
R2 = [
    probka(10.0, 1, [ja, mob("Rat", 2, 0, osiagalny=True), mob("Rat", 3, 0), inny_gracz]),
    {"t": 11.0, "typ": "poscig_start", "cel": "Rat", "odl": 2, "hp_celu": 80, "sesja": 1},
    {"t": 15.0, "typ": "poscig_koniec", "cel": "Rat", "powod": "odl<=1", "sesja": 1},
    probka(20.0, 1, [ja, mob("Rat", 6, 0)]),
    {"t": 21.0, "typ": "poscig_start", "cel": "Rat", "odl": 6, "hp_celu": 30, "sesja": 1},
    {"t": 30.0, "typ": "poscig_koniec", "cel": "Rat", "powod": "zawracanie", "sesja": 1},
    probka(40.0, 1, [ja, mob("Rat", 2, 0)]),
    {"t": 41.0, "typ": "poscig_start", "cel": "Rat", "odl": 2, "hp_celu": 90, "sesja": 1},
    {"t": 45.0, "typ": "poscig_koniec", "cel": "Rat", "powod": "gryzacy", "sesja": 1},          # powód pominięty
    {"t": 50.0, "typ": "poscig_start", "cel": "Rat", "odl": 2, "hp_celu": 90, "sesja": 2},       # brak próbki w sesji 2
    {"t": 55.0, "typ": "poscig_koniec", "cel": "Rat", "powod": "cel_martwy", "sesja": 2},
    probka(60.0, 3, [ja, mob("Troll", 2, 0)]),
    {"t": 61.0, "typ": "poscig_start", "cel": "Rat", "odl": 2, "hp_celu": 90, "sesja": 3},       # cel nie jest w próbce
    {"t": 65.0, "typ": "poscig_koniec", "cel": "Rat", "powod": "cel_martwy", "sesja": 3},
    probka(70.0, 4, [ja, mob("Rat", 2, 0)]),
    {"t": 71.0, "typ": "poscig_start", "cel": "Rat", "odl": 2, "hp_celu": 90, "sesja": 4},       # start bez końca
]
R2.sort(key=lambda r: r["t"])
z2, s2 = Z.zbuduj_d2(R2)
sprawdz("D2: liczby (6 startów: 2 użyte, 1 powód pominięty, 1 brak próbki, 1 bez celu, 1 bez końca)",
        s2["poscig_start"] == 6 and s2["uzyte"] == 2 and s2["powod_pominiety"] == 1 and s2["brak_probki"] == 1
        and s2["bez_celu_w_probce"] == 1 and s2["bez_konca"] == 1, str(s2))
sprawdz("D2: etykiety 1 (odl<=1) i 0 (zawracanie)", z2.y == [1, 0], str(z2.y))
y0 = dict(zip(z2.nazwy, z2.X[0]))
sprawdz("D2: cechy pościgu 1 (odl 2, hp 80, tłum 1, obcy gracz 2 od celu, osiągalny)",
        (y0["odl"], y0["hp_celu"], y0["inne_w2"], y0["odl_gracza"], y0["osiag_tak"]) == (2, 80, 1, 2.0, 1), str(y0))
sprawdz("D2: pominięte powody policzone", s2["pominiete_powody"] == {"gryzacy": 1}, str(s2["pominiete_powody"]))
sprawdz("D2: etykieta z powodu", Z.etykieta_d2("brak_ruchu") == 0 and Z.etykieta_d2("cel_martwy") == 1 and Z.etykieta_d2("hp_spadek") is None)

# --- wczytanie telemetrii: filtr --od, złe linie liczone ---
with tempfile.TemporaryDirectory() as tmp:
    for d, lin in (("20261014", [{"t": 2, "typ": "a"}, {"t": 1, "typ": "b"}]), ("20261015", [{"t": 3, "typ": "c"}])):
        with open(os.path.join(tmp, "telemetria-%s.jsonl" % d), "w") as f:
            for r in lin: f.write(json.dumps(r) + "\n")
            if d == "20261014": f.write("{uciety\n")
    rek, s = Z.wczytaj_telemetrie(tmp)
    sprawdz("wczytaj: posortowane po t, zła linia policzona", [r["typ"] for r in rek] == ["b", "a", "c"] and s["zle_linie"] == 1, str(s))
    rek, s = Z.wczytaj_telemetrie(tmp, od="20261015")
    sprawdz("wczytaj: --od pomija starsze pliki", [r["typ"] for r in rek] == ["c"] and s["pliki"] == 1)

# --- cały przebieg na syntetycznym D2 (znana zależność: im większa odl, tym gorzej) ---
rg = np.random.default_rng(1); Rs = []; t = 1000.0
for s_ in range(8):
    for _ in range(80):
        odl = int(rg.integers(2, 9)); t += 10
        Rs.append(probka(t, s_, [ja, mob("Rat", odl, 0)]))
        Rs.append({"t": t + 1, "typ": "poscig_start", "cel": "Rat", "odl": odl, "hp_celu": 100, "sesja": s_})
        Rs.append({"t": t + 5, "typ": "poscig_koniec", "cel": "Rat", "powod": "odl<=1" if rg.random() > odl / 10 else "brak_ruchu", "sesja": s_})
with tempfile.TemporaryDirectory() as tmp:
    wynik, rap = T.trenuj("D2", Rs, tmp)
sprawdz("trenuj D2 syntetyczny: model pobija stałą częstość (AUC > 0.65)", wynik["metryki_test"][wynik["wybrany"]]["auc"] > 0.65
        and wynik["metryki_test"][wynik["wybrany"]]["log_loss"] < wynik["baseline_test"]["stala_czestosc"]["log_loss"],
        str(wynik["metryki_test"][wynik["wybrany"]]))
sprawdz("trenuj: raport zawiera sekcje metryk i czasu", "## Metryki na teście" in rap and "## Czas inferencji" in rap)
sprawdz("trenuj: wynik serializuje się do JSON", len(json.dumps(wynik)) < 100 * 1024 * 2)
# --- D3 (zawieszka): para decyzja D3 + d3_wynik, etykieta, pomijane przypadki ---
def d3dec(i, ses, t, **kw):
    r = {"t": t, "typ": "decyzja", "id": i, "rodzaj": "D3", "sesja": ses, "poz": [1, 2, 7], "wybrana": None, "stoi_s": 31.0,
         "wokol": {"+1+0": ".", "-1+0": "#", "+0+1": "o", "+0-1": "."}, "odl_cel": 5, "cel_droga": 7, "cel_droga_policzona": True,
         "gracze_odl": [4, 9], "moby_odl": [], "hp_gracza": 90.0, "poprzednie_tu": 1, "zamierzony": False,
         "opcje": [{"akcja": "krok_skos", "mozliwa": True}, {"akcja": "cofnij", "mozliwa": True, "kroki": 3},
                   {"akcja": "inny_punkt", "mozliwa": True, "osiagalnych": 2, "droga": 6}, {"akcja": "przejscie_pietra", "mozliwa": False}]}
    r.update(kw)
    return r
def d3wyn(i, ses, t, **kw):
    r = {"t": t, "typ": "d3_wynik", "decyzja_id": i, "sesja": ses, "ruszyl": True, "czas_s": 8.0, "koniec": "ruch"}
    r.update(kw)
    return r
R3 = [d3dec(1, 1, 10), d3wyn(1, 1, 20),                                   # ruszył w 8 s -> 1
      d3dec(2, 1, 100), d3wyn(2, 1, 190, czas_s=90.0),                    # ruszył po 90 s -> 0
      d3dec(3, 1, 300), d3wyn(3, 1, 305, ruszyl=False, czas_s=5.0, koniec="exp"),   # ucięta
      d3dec(4, 1, 400, zamierzony=True), d3wyn(4, 1, 450, czas_s=50.0),   # zamierzona
      d3dec(5, 1, 500),                                                   # bez wyniku
      d3dec(1, 2, 600), d3wyn(1, 2, 640, ruszyl=False, czas_s=40.0, koniec="stop"),   # stop po 40 s -> 0; id 1 w innej sesji
      probka(700, 1, [ja])]
z3, s3 = Z.zbuduj_d3(R3)
sprawdz("D3: liczby (6 decyzji: 3 użyte, 1 ucięta, 1 zamierzona, 1 bez wyniku)",
        s3["decyzje_d3"] == 6 and s3["uzyte"] == 3 and s3["obserwacja_ucieta"] == 1 and s3["zamierzone"] == 1 and s3["bez_wyniku"] == 1, str(s3))
sprawdz("D3: etykiety 1/0/0 (id parowane po sesji, nie samym id)", z3.y == [1, 0, 0], str(z3.y))
x3 = dict(zip(z3.nazwy, z3.X[0]))
sprawdz("D3: cechy (stoi 31, wolne 2, ogień/dziura 1, odl_cel 5, droga 7, gracz 4, moby brak=duża odl, skos/cofnij tak, kroki 3, punkt 2/6, piętro nie)",
        (x3["stoi_s"], x3["wolne_wokol"], x3["ogien_dziura_wokol"], x3["odl_cel"], x3["cel_droga"], x3["gracz_odl"], x3["mob_odl"],
         x3["skos_mozliwa"], x3["cofnij_kroki"], x3["punkt_osiagalnych"], x3["punkt_droga"], x3["pietro_mozliwe"], x3["pietro_odl"])
        == (31.0, 2.0, 1.0, 5.0, 7.0, 4.0, Z.DUZA_ODL, 1.0, 3.0, 2.0, 6.0, 0.0, -1.0), str(x3))
sprawdz("D3: etykieta: ruch w 20 s=1, dłużej=0, ucięte=None", Z.etykieta_d3({"ruszyl": True, "czas_s": 20.0}) == 1
        and Z.etykieta_d3({"ruszyl": True, "czas_s": 21.0}) == 0 and Z.etykieta_d3({"ruszyl": False, "czas_s": 3.0}) is None)
try:
    T.trenuj("D3", R3, tempfile.gettempdir())
    za_malo = False
except SystemExit as e:
    za_malo = "za mało danych" in str(e)
sprawdz("trenuj D3 na 3 wierszach: komunikat 'za mało danych' (trening dopiero po zebraniu zawieszek)", za_malo)

print("WYNIK:", sum(ok), "/", len(ok)); sys.exit(0 if all(ok) else 1)
