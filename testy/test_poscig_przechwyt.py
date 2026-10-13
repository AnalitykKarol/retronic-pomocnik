import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import poscig_przechwyt as P

ok = True
def sprawdz(opis, war):
    global ok
    print(("OK   " if war else "BŁĄD ") + opis); ok = ok and bool(war)

otwarte = lambda x, y: True
def sciany(zbior):
    return lambda x, y: False if (x, y) in zbior else True

# --- czas kroku: ceil(10000*v/230/50)*50 ms ---
sprawdz("czas kroku v12 = 0,55 s", abs(P.czas_kroku(12) - 0.55) < 1e-9)
sprawdz("czas kroku v14 = 0,65 s", abs(P.czas_kroku(14) - 0.65) < 1e-9)
sprawdz("czas kroku v16 = 0,70 s", abs(P.czas_kroku(16) - 0.70) < 1e-9)
sprawdz("czas kroku v20 = 0,90 s", abs(P.czas_kroku(20) - 0.90) < 1e-9)
sprawdz("brak prędkości = jak v12", P.czas_kroku(None) == P.czas_kroku(12))

# --- cel ucieka prosto w dół (y rośnie), 1 pole / 1,2 s ---
h = [(10, 0, 0.0), (10, 1, 1.2), (10, 2, 2.4)]
r = P.wybierz((6, 2), h, 2.5, otwarte)
sprawdz("ucieka prosto: przechwyt", r["powod"] == "przechwyt" and r["kierunek"] is not None)
sprawdz("przechwyt: cel przewidziany dalej niż bieżący", r["cel"][1] > 2 and r["cel"][0] == 10)
sprawdz("przechwyt: kierunek ku celowi (+x)", r["kierunek"] == (1, 0))
sprawdz("przechwyt: kierunek to krok prosty", r["kierunek"] in P.KOSTKI)
sprawdz("przechwyt: czas i kroki dodatnie", r["t"] > 0 and r["kroki"] >= 1)

# --- cel stoi (po ruchu minęło >2 jego kroki) ---
r = P.wybierz((6, 2), h, 20.0, otwarte)
sprawdz("cel stoi: powód cel_stoi, cel = ostatnia pozycja", r["powod"] == "cel_stoi" and r["cel"] == (10, 2))
sprawdz("cel stoi: kierunek ku niemu", r["kierunek"] == (1, 0))

# --- brak historii / jedna próbka ---
r = P.wybierz((6, 2), [], 1.0, otwarte)
sprawdz("pusta historia: fallback bez kierunku", r["kierunek"] is None and r["cel"] is None and r["powod"] == "brak_historii")
r = P.wybierz((6, 2), [(10, 2, 1.0)], 1.1, otwarte)
sprawdz("jedna próbka: fallback, cel = bieżący", r["kierunek"] is None and r["cel"] == (10, 2) and r["powod"] == "brak_historii")
r = P.wybierz((6, 2), [(10, 2, 1.0), (10, 2, 1.5), (10, 2, 2.0)], 2.1, otwarte)
sprawdz("powtórzenia tej samej pozycji = jedna próbka", r["powod"] == "brak_historii")

# --- zawraca / oscyluje ---
r = P.wybierz((6, 2), [(10, 0, 0.0), (10, 1, 1.2), (10, 0, 2.4)], 2.5, otwarte)
sprawdz("A-B-A: zawraca, fallback do dojścia", r["powod"] == "zawraca" and r["kierunek"] is None and r["cel"] == (10, 0))
r = P.wybierz((6, 2), [(10, 0, 0.0), (10, 1, 1.2), (10, 2, 2.4), (10, 1, 3.6)], 3.7, otwarte)
sprawdz("odwrócenie kierunku po marszu: zawraca", r["powod"] == "zawraca" and r["kierunek"] is None)

# --- obok ---
r = P.wybierz((9, 2), h, 2.5, otwarte)
sprawdz("już obok: powód obok, brak kierunku", r["powod"] == "obok" and r["kierunek"] is None)

# --- ściana na drodze celu: przewidywanie klamrowane do ostatniego wolnego pola ---
s = sciany({(10, y) for y in range(4, 20)})
r = P.wybierz((4, 3), h, 2.5, s)
sprawdz("ściana przed celem: przewidziany cel nie wchodzi w ścianę", r["powod"] in ("przechwyt", "poza_horyzontem")
        and (r["cel"] if r["powod"] == "przechwyt" else r["cel_prowadzenia"])[1] <= 3)
nm, ost, poz_w, w = P.model_celu(h, 2.5, s)
sprawdz("model: stan idzie, prędkość ok. 0,83 pola/s", nm == "idzie" and abs(w - 1 / 1.2) < 0.01)
sprawdz("model: pozycja po 10 s zatrzymana ścianą na y=3", poz_w(10.0) == (10, 3))

# --- skosy: tylko gdy skos_koszt < 2 ---
r = P.wybierz((9, 0), [(12, 0, 0.0), (12, 1, 1.2), (12, 2, 2.4)], 2.5, otwarte, skos_koszt=3.0)
sprawdz("skos_koszt 3.0: żaden skos", r["kierunek"] is not None and r["kierunek"] in P.KOSTKI)
r = P.wybierz((9, 0), [(12, 0, 0.0), (12, 1, 1.2), (12, 2, 2.4)], 2.5, otwarte, skos_koszt=1.5)
sprawdz("skos_koszt 1.5: dozwolone skosy (kierunek poprawny)", r["kierunek"] is not None and r["kierunek"][0] >= 0)
sprawdz("skos_koszt 1.5 nie jest wolniejszy niż 3.0", r["t"] <= P.wybierz((9, 0), [(12, 0, 0.0), (12, 1, 1.2), (12, 2, 2.4)],
        2.5, otwarte, skos_koszt=3.0)["t"] + 1e-9)

# --- zajęte pole nie jest wybierane na pierwszy krok ---
r = P.wybierz((6, 2), h, 2.5, otwarte, zajete=[(7, 2)])
sprawdz("zajęte (7,2): obchodzimy", r["kierunek"] != (1, 0) and r["kierunek"] is not None)

# --- daleko: poza horyzontem; cel_prowadzenia leży na przedłużeniu ruchu ---
r = P.wybierz((0, 0), [(10, 0, 0.0), (10, 1, 1.2), (10, 2, 2.4)], 2.5, otwarte)
sprawdz("daleko: poza_horyzontem, kierunek None", r["powod"] == "poza_horyzontem" and r["kierunek"] is None)
sprawdz("daleko: cel_prowadzenia o max `horyzont` pól za ostatnią pozycją", r["cel_prowadzenia"] is not None
        and 2 < r["cel_prowadzenia"][1] <= 2 + P.HORYZONT)
r5 = P.wybierz((0, 0), [(10, 0, 0.0), (10, 1, 1.2), (10, 2, 2.4)], 2.5, otwarte, horyzont=5)
sprawdz("większy horyzont: dalszy cel_prowadzenia", r5["cel_prowadzenia"][1] >= r["cel_prowadzenia"][1])

# --- mnożnik wolniejszego biegu wydłuża czas ---
a = P.wybierz((6, 2), h, 2.5, otwarte, mnoznik=1.0)
b = P.wybierz((6, 2), h, 2.5, otwarte, mnoznik=1.3)
sprawdz("mnożnik 1,3: czas przechwytu nie krótszy", b["powod"] != "przechwyt" or b["t"] >= a["t"])

# --- reszta kroku w toku (wolny_za) opóźnia przechwyt ---
c = P.wybierz((6, 2), h, 2.5, otwarte, wolny_za=0.4)
sprawdz("wolny_za 0,4 s: czas przechwytu +0,4", abs(c["t"] - a["t"] - 0.4) < 1e-6)

# --- wolniejsze pole (v20) wydłuża czas ---
d = P.wybierz((6, 2), h, 2.5, otwarte, predkosc=lambda x, y: 20)
sprawdz("pola v20: czas dłuższy niż v12", d["powod"] != "przechwyt" or d["t"] >= a["t"])

# --- nieznane pola = ściana ---
nz = lambda x, y: None if x == 7 else True
r = P.wybierz((6, 2), h, 2.5, nz)
sprawdz("nieznane pole (x=7) traktowane jak ściana: brak drogi", r["kierunek"] is None)

# --- czystość: ta sama odpowiedź dla tych samych danych, historia nie jest zmieniana ---
hh = list(h)
x1 = P.wybierz((6, 2), hh, 2.5, otwarte); x2 = P.wybierz((6, 2), hh, 2.5, otwarte)
sprawdz("deterministyczna i nie modyfikuje historii", x1 == x2 and hh == h)
sprawdz("moduł nie importuje cavebota/mapy", not any(m in sys.modules for m in ("cavebot", "mapa")))

print("\nWSZYSTKO OK" if ok else "\nSĄ BŁĘDY")
sys.exit(0 if ok else 1)
