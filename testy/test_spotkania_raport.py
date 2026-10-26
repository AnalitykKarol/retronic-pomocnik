#!/usr/bin/env python3
"""26.10 (Karol): narzedzia/spotkania_graczy_raport.py — raport spotkań z graczami z telemetrii (tylko odczyt). Offline: fixture z prawdziwej telemetrii 25.10
(testy/dane/spotkania_graczy/, zbudowany jednorazowo przez narzedzia_jednorazowe/zbuduj_fixture_spotkania.py) i syntetyczne instancje w katalogu tymczasowym.
Uruchomienie: RETRONIC_TESTY=1 python3 -I testy/test_spotkania_raport.py

Regresja z ręcznego liczenia Karola dla 25.10 (Hammburger/gerbor Stekt 10, Geblish Flower Power 7 + Hansi 3, Pomszta Apock 4, Wydra = patrol z niezerowym czasem):
oficjalne reguły bota (15 s w widoku, 300 s przerwy) dają na tych samych danych Stekt 10 (zgodnie), Flower Power 5, Hansi 0, Apock 3; z progiem 5 s (`--min-widok 5`)
Stekt 10, Flower Power 7, Hansi 4, Apock 3 — ręczne liczenie odpowiada więc mniej więcej progowi ~5 s (nie dokładnie: Hansi 3, Apock 4). Test pilnuje obu zestawów."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import contextlib
import io
import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KAT))
sys.path.insert(0, str(KAT / "narzedzia"))
import spot_gracz as SG  # noqa: E402
import spotkania_graczy_raport as R  # noqa: E402

FIX = KAT / "testy" / "dane" / "spotkania_graczy"
ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


def wiersz(id_, dzien="20261025", korzen=FIX, **extra):
    s0 = (SG.MIN_WIDOK_S, SG.PRZERWA_S)
    try:
        if "min_widok" in extra:
            SG.MIN_WIDOK_S = extra["min_widok"]
        return R.raport_instancji(korzen, id_, dzien)
    finally:
        SG.MIN_WIDOK_S, SG.PRZERWA_S = s0


# ---- regresja na fixture z prawdziwej telemetrii
nick = lambda w, n: dict(w["nicki_prog15"]).get(n, 0)      # noqa: E731  (reguły bota: >= 15 s w widoku; regresja R1-R3 i S1 testuje ten licznik)
nick0 = lambda w, n: dict(w["nicki"]).get(n, 0)            # noqa: E731  (26.10: spotkania BEZ progu widoku, to pokazuje okno)
g, ge, po, wy = (wiersz(i) for i in ("gerbor", "gebelish", "pomszta", "wydra"))
sprawdz("R1 oficjalne reguły (15 s / 300 s): Hammburger/gerbor Stekt 10 (zgodnie z ręcznym liczeniem Karola)", nick(g, "Stekt") == 10, g["nicki"])
sprawdz("R2 oficjalne reguły: Geblish Flower Power 5, Hansi 0; Pomszta Apock 3", nick(ge, "Flower Power") == 5 and nick(ge, "Hansi") == 0 and nick(po, "Apock") == 3,
        (ge["nicki"], po["nicki"]))
g5, ge5, po5 = (wiersz(i, min_widok=5) for i in ("gerbor", "gebelish", "pomszta"))
sprawdz("R3 próg widoku 5 s: Stekt 10, Flower Power 7 (zgodnie z Karolem), Hansi 4 (Karol 3), Apock 3 (Karol 4) — różnica najwyżej 1",
        nick(g5, "Stekt") == 10 and nick(ge5, "Flower Power") == 7 and nick(ge5, "Hansi") == 4 and nick(po5, "Apock") == 3
        and abs(nick(ge5, "Hansi") - 3) <= 1 and abs(nick(po5, "Apock") - 4) <= 1, (g5["nicki"], ge5["nicki"], po5["nicki"]))
sprawdz("R4 Wydra 25.10 (patrol `trolle_patrol`, bez pliku pętli): NIEZEROWY czas na spocie (okno 2 h w fixture), brak „brak pętli”", wy["czas_na_spocie_h"] > 1.0
        and wy["probek_na_spocie"] > 500 and "blad" not in wy, wy)
sprawdz("R5 Pomszta: raport nie opiera się na trasie z tryb.log (jej pętla `rook_raty_z8_petla` leży ~36 pól od miejsca expienia w kieszeni): czas na spocie > 0",
        po["probek_na_spocie"] > 0, po)

# ---- syntetyczne instancje
T = datetime(2026, 10, 25, 12, 0, 0).timestamp()


def swiat(probki, logi=None, nasze=None, postac="Bot"):
    tmp = tempfile.TemporaryDirectory()
    k = Path(tmp.name)
    (k / "instancje" / "a" / "logi").mkdir(parents=True)
    (k / "instancje" / "a" / "profil.json").write_text(json.dumps({"postac": postac}))
    for nazwa, p in (nasze or {}).items():
        (k / "instancje" / nazwa).mkdir(parents=True, exist_ok=True)
        (k / "instancje" / nazwa / "profil.json").write_text(json.dumps({"postac": p}))
    with open(k / "instancje" / "a" / "logi" / "telemetria-20261025.jsonl", "w") as f:
        for r in probki:
            f.write(json.dumps(r) + "\n")
    for nazwa, linie in (logi or {}).items():
        (k / "instancje" / "a" / "logi" / nazwa).write_text("\n".join(linie) + "\n")
    return tmp, k


def pr(t, gracze=(), stan="IDZ", sesja=1.0, hp=100, poz=(100, 100, 8), wlasny="Bot", **kw):
    st = [{"n": wlasny, "dx": 0, "dy": 0, "odl": 0, "hp": 100, "gracz": True}]
    for n in gracze:
        st.append({"n": n, "dx": 2, "dy": 0, "odl": 2, "hp": kw.get("hp_gracza", 80), "gracz": True})
    return {"t": t, "typ": "probka", "stan": stan, "poz": list(poz), "hp": hp, "stwory": st, "sesja": sesja, "src": "mozg"}


def seria(od, do, gracze, **kw):
    return [pr(T + x, gracze, **kw) for x in range(od, do + 1)]


# trzy osobne spotkania vs jeden gracz kręcący się 10 min — te same reguły co w bocie
trzy = seria(0, 20, ["Obcy"]) + seria(400, 420, ["Obcy"]) + seria(800, 820, ["Obcy"])
dlugo = seria(0, 600, ["Obcy"])
tmp1, k1 = swiat(trzy)
tmp2, k2 = swiat(dlugo)
sprawdz("S1 trzy osobne spotkania (przerwy > 5 min) = 3; ten sam nick przez 10 min = 1", nick(wiersz("a", korzen=k1), "Obcy") == 3 and nick(wiersz("a", korzen=k2), "Obcy") == 1,
        (wiersz("a", korzen=k1)["nicki"], wiersz("a", korzen=k2)["nicki"]))
w2 = wiersz("a", korzen=k2)
sprawdz("S2 czas na spocie ~10 min, 1 gracz, 1 spotkanie, spotkań/h ~6", abs(w2["czas_na_spocie_h"] - 600 / 3600) < 0.01 and w2["graczy"] == 1 and w2["spotkan"] == 1
        and 5.5 < w2["spotkan_na_h"] < 6.5, w2)

# nie liczą się: nasze (profil.json + lista), własny, martwi, GM, stany poza spotem
tmp3, k3 = swiat(seria(0, 30, ["Kolanosh", "Ela Druid", "Martwy", "GM Foo"], hp_gracza=80), nasze={"b": "Ela Druid"})
# Martwy: hp 0
for r in R.probki(k3 / "instancje" / "a" / "logi" / "telemetria-20261025.jsonl"):
    break
w3 = wiersz("a", korzen=k3)
sprawdz("S3 nasze postacie (lista Karola + profil.json innej instancji) i GM nie liczą się (zostaje tylko „Martwy” z hp>0)", w3["nicki"] == [("Martwy", 1)], w3["nicki"])
pr_m = seria(0, 30, ["Obcy"])
for r in pr_m:
    r["stwory"][1]["hp"] = 0
tmp4, k4 = swiat(pr_m)
sprawdz("S4 gracz z HP 0 nie liczy się", wiersz("a", korzen=k4)["spotkan"] == 0)
for stan in ("WYPAD", "WPADNIECIE", "PAUZA_STOJ", None):
    tmp5, k5 = swiat(seria(0, 30, ["Obcy"], stan=stan))
    w5 = wiersz("a", korzen=k5)
    sprawdz(f"S5 stan {stan}: próbki nie liczą się jako „na spocie” (0 spotkań, 0 h)", w5["spotkan"] == 0 and w5["czas_na_spocie_h"] == 0, w5)
for stan in ("IDZ", "WALKA", "LOOT", "POGON", "PRZERWA", "ORBITA"):
    tmp5, k5 = swiat(seria(0, 30, ["Obcy"], stan=stan))
    sprawdz(f"S5b stan {stan}: liczy się jako expienie (spotkanie 1)", wiersz("a", korzen=k5)["spotkan"] == 1)

# dojście: log sesji z „Dojście: trasa” bez zakończenia = wszystko dojście; po „Dojście zakończone” liczy się
log_start = datetime.fromtimestamp(T - 60)
nazwa_logu = f"mozg-stdout-{log_start:%m%d-%H%M}.log"
godz = lambda sek: (datetime.fromtimestamp(T) + timedelta(seconds=sek)).strftime("%H:%M:%S")      # noqa: E731
dojscie_bez_konca = {nazwa_logu: [f"{log_start:%H:%M:%S} Mózg: tryb skrypt", f"{log_start:%H:%M:%S} Dojście: trasa x (10 pkt), potem y."]}
tmp6, k6 = swiat(seria(0, 40, ["Obcy"]), logi=dojscie_bez_konca)
sprawdz("D1 dojście bez zakończenia: próbki nie liczą się", wiersz("a", korzen=k6)["spotkan"] == 0 and wiersz("a", korzen=k6)["czas_na_spocie_h"] == 0)
z_koncem = {nazwa_logu: dojscie_bez_konca[nazwa_logu] + [f"{godz(20)} Dojście zakończone, zaczynam główną trasę."]}
tmp7, k7 = swiat(seria(0, 60, ["Obcy"]), logi=z_koncem)
w7 = wiersz("a", korzen=k7)
sprawdz("D2 po „Dojście zakończone” (od +20 s) próbki liczą się: czas ~40 s, spotkanie 1 (20 s widoku po dojściu >= 15 s)", 35 <= w7["czas_na_spocie_h"] * 3600 <= 41 and w7["spotkan"] == 1, w7)
bez_doj = {nazwa_logu: [f"{log_start:%H:%M:%S} Mózg: tryb skrypt, postać Bot"]}
tmp8, k8 = swiat(seria(0, 40, ["Obcy"]), logi=bez_doj)
sprawdz("D3 sesja bez dojścia (bot od razu na spocie, np. Pomszta): liczy od początku", wiersz("a", korzen=k8)["spotkan"] == 1)

# --od-startu: ostatnia `sesja`; --dzien: cały dzień
dwie = seria(0, 30, ["Stary"], sesja=1.0) + seria(2000, 2030, ["Nowy"], sesja=2.0)
tmp9, k9 = swiat(dwie)
wd = R.raport_instancji(k9, "a", "20261025")
wo = R.raport_instancji(k9, "a", None)
sprawdz("O1 --dzien liczy obie sesje, domyślnie (od ostatniego startu) tylko ostatnią `sesję`", nick(wd, "Stary") == 1 and nick(wd, "Nowy") == 1 and nick(wo, "Nowy") == 1 and nick(wo, "Stary") == 0,
        (wd["nicki"], wo["nicki"]))

# CLI: tabela i --json, tylko odczyt
przed = {str(p): p.stat().st_mtime_ns for p in k9.rglob("*") if p.is_file()}
bufor = io.StringIO()
with contextlib.redirect_stdout(bufor):
    kod = R.main(["--korzen", str(k9), "--dzien", "20261025"])
txt = bufor.getvalue()
sprawdz("C1 CLI: tabela z nagłówkiem, instancją i nickami", kod == 0 and "instancja" in txt and "Stary 1" in txt and "Nowy 1" in txt, txt)
bufor = io.StringIO()
with contextlib.redirect_stdout(bufor):
    R.main(["--korzen", str(k9), "--json"])
dj = json.loads(bufor.getvalue())
sprawdz("C2 --json: lista obiektów z polami czas_na_spocie_h, graczy, spotkan, spotkan_na_h, nicki", isinstance(dj, list) and dj[0]["instancja"] == "a"
        and all(k in dj[0] for k in ("czas_na_spocie_h", "graczy", "spotkan", "spotkan_na_h", "nicki")), dj)
po = {str(p): p.stat().st_mtime_ns for p in k9.rglob("*") if p.is_file()}
sprawdz("C3 tylko odczyt: żaden plik nie zmieniony ani nie dopisany", przed == po)
bufor = io.StringIO()
with contextlib.redirect_stdout(bufor):
    R.main(["--korzen", str(k9), "--dzien", "20260101"])
sprawdz("C4 dzień bez telemetrii: wiersz z komunikatem, bez wyjątku", "brak telemetrii" in bufor.getvalue())
sprawdz("C5 skrypt nie importuje trasy ani tryb.log (kryterium bez geometrii)", "tryb.log" not in (KAT / "narzedzia" / "spotkania_graczy_raport.py").read_text().split('"""')[2])
# te same reguły co bot: licznik bota na tym samym przebiegu daje ten sam wynik
l = SG.Licznik(None, 0.0)
zd = []
for r in trzy:
    zd += l.obserwuj(r["t"], ["Obcy"], True)
sprawdz("C6 zgodność z botem: Licznik(None) na tych samych próbkach daje 3 spotkania jak raport", len(zd) == 3)

# ---- 26.10: „widziani” (różni obcy w zasięgu wzroku, >= 1 próbka, od wejścia na spot = ostatnie.json `na_spocie_od`)
def ostatnie(k, od, id_="a"):
    (k / "instancje" / id_ / "ostatnie.json").write_text(json.dumps({"v": 1, "na_spocie_od": od, "mapa": "x"}))


# W1: jedna próbka wystarczy (spotkań 0, widziani 1); bez progu 15 s i przerwy 5 min
tmpw1, kw1 = swiat([pr(T, ["Mignal"]), pr(T + 1, [])] + seria(2, 30, ["Obcy"]))
ostatnie(kw1, T - 5)
ww1 = R.raport_instancji(kw1, "a")
lw1 = {e["nick"]: e for e in ww1["widziani_lista"]}
sprawdz("W1 jedna próbka = widziany: widziani 2 (Mignal 1 próbka, Obcy 29); spotkań wg bota tylko Obcy", ww1["widziani"] == 2 and lw1["Mignal"]["probek"] == 1
        and lw1["Obcy"]["probek"] == 29 and nick(ww1, "Mignal") == 0 and nick(ww1, "Obcy") == 1, ww1)
sprawdz("W1b lista: najczęściej widziani pierwsi, z pierwszym i ostatnim czasem; widziani_od = na_spocie_od; bez powodu (uwaga o niesprawdzonym dojściu jak w reszcie raportu: fixture bez logów sesji)",
        ww1["widziani_lista"][0]["nick"] == "Obcy" and lw1["Mignal"]["pierwszy_t"] == T and lw1["Obcy"]["ostatnio_t"] == T + 30 and ww1["widziani_od"] == T - 5
        and ww1["widziani_powod"] is None and "dojście niesprawdzone" in ww1["widziani_uwaga"], ww1)
# W2: tylko od wejścia na spot — wcześniejsze próbki nie liczą się
tmpw2, kw2 = swiat(seria(0, 10, ["Stary"]) + seria(100, 110, ["Nowy"]))
ostatnie(kw2, T + 50)
ww2 = R.raport_instancji(kw2, "a")
sprawdz("W2 tylko próbki od na_spocie_od: Stary (przed wejściem na spot) nie liczy się, Nowy tak", [e["nick"] for e in ww2["widziani_lista"]] == ["Nowy"] and ww2["widziani"] == 1, ww2)
ostatnie(kw2, T - 5)
sprawdz("W2b cofnięty początek huntu obejmuje obu", R.raport_instancji(kw2, "a")["widziani"] == 2)
# W3: te same filtry co licznik bota (własny, nasze, GM, hp 0, czaszka/pk) + kryterium „na spocie”
wp = seria(0, 10, ["Kolanosh", "Ela Druid", "GM Foo", "Zmarly", "Czaszkowiec", "Pekacz", "Zwykly"], hp_gracza=80)
for r in wp:
    for st in r["stwory"]:
        if st["n"] == "Zmarly":
            st["hp"] = 0
        if st["n"] == "Czaszkowiec":
            st["czaszka"] = True
        if st["n"] == "Pekacz":
            st["pk"] = True
wp.append(pr(T + 11, ["Bot", "Bot"]))                                     # własny nick jako „gracz”
tmpw3, kw3 = swiat(wp, nasze={"b": "Ela Druid"})
ostatnie(kw3, T - 1)
ww3 = R.raport_instancji(kw3, "a")
sprawdz("W3 filtry jak „graczy”: zostaje tylko Zwykly (bez własnego, naszych, GM, hp 0, czaszki, pk)", [e["nick"] for e in ww3["widziani_lista"]] == ["Zwykly"] and ww3["graczy"] == 1, ww3)
sprawdz("W3b widziani <= zawsze zgodne z „graczy” na tym samym zakresie (jedna sesja od początku huntu): równe", ww3["widziani"] == ww3["graczy"])
for stan in ("WYPAD", "WPADNIECIE", "PAUZA_STOJ", "STOJ_POWROT", "WYLOGUJ_OBCY", None):
    tmpw4, kw4 = swiat(seria(0, 10, ["Obcy"], stan=stan))
    ostatnie(kw4, T - 1)
    sprawdz(f"W4 stan {stan}: widziani 0 (poza spotem), ale to prawdziwe zero, nie brak", R.raport_instancji(kw4, "a")["widziani"] == 0)
tmpw5, kw5 = swiat(seria(0, 40, ["Obcy"]), logi=dojscie_bez_konca)
ostatnie(kw5, T - 1)
sprawdz("W5 dojście bez zakończenia: widziani 0", R.raport_instancji(kw5, "a")["widziani"] == 0)
tmpw6, kw6 = swiat(seria(0, 5, ["Przed"]) + seria(20, 60, ["Po"]), logi=z_koncem)
ostatnie(kw6, T - 1)
ww6 = R.raport_instancji(kw6, "a")
sprawdz("W5b dojście zakończone w +20 s: widziany tylko Po (Przed w dojściu)", [e["nick"] for e in ww6["widziani_lista"]] == ["Po"], ww6)
# W7: obejmuje wszystkie sesje od na_spocie_od (restart bota na tym samym spocie), „graczy” tylko ostatnią sesję
tmpw7, kw7 = swiat(seria(0, 30, ["Przed"], sesja=1.0) + seria(2000, 2030, ["Po"], sesja=2.0))
ostatnie(kw7, T - 5)
ww7 = R.raport_instancji(kw7, "a")
sprawdz("W7 restart bota na tym samym spocie: widziani 2 (obie sesje), graczy 1 (tylko ostatnia sesja), spotkań Po 1", ww7["widziani"] == 2 and ww7["graczy"] == 1 and nick(ww7, "Po") == 1, ww7)
# W8: brak początku huntu / zły plik / --dzien
tmpw8, kw8 = swiat(seria(0, 10, ["Obcy"]))
ww8 = R.raport_instancji(kw8, "a")
sprawdz("W8 brak ostatnie.json: widziani None + powód, reszta raportu jak dotąd", ww8["widziani"] is None and "na_spocie_od" in ww8["widziani_powod"] and ww8["graczy"] == 1 and ww8["widziani_lista"] == [], ww8)
(kw8 / "instancje" / "a" / "ostatnie.json").write_text("{zepsute")
sprawdz("W8b uszkodzone ostatnie.json = None z powodem, bez wyjątku", R.raport_instancji(kw8, "a")["widziani"] is None)
for zly in (None, "abc", True, 0, -5):
    (kw8 / "instancje" / "a" / "ostatnie.json").write_text(json.dumps({"na_spocie_od": zly}))
    sprawdz(f"W8c na_spocie_od={zly!r}: None, nigdy zero", R.raport_instancji(kw8, "a")["widziani"] is None)
ostatnie(kw8, T + 99999)
sprawdz("W8d początek huntu w przyszłości: None z powodem", R.raport_instancji(kw8, "a")["widziani"] is None and "przyszłości" in R.raport_instancji(kw8, "a")["widziani_powod"])
ostatnie(kw8, T - 1)
sprawdz("W8e --dzien: widziani None (hunt to nie dzień)", R.raport_instancji(kw8, "a", "20261025")["widziani"] is None)
# W9: początek huntu przed telemetrią -> uwaga
ostatnie(kw8, T - 5000)
sprawdz("W9 telemetria zaczyna się po wejściu na spot: wynik z uwagą", "po wejściu na spot" in (R.raport_instancji(kw8, "a")["widziani_uwaga"] or ""), R.raport_instancji(kw8, "a"))
# W10: CLI — kolumna „widziani” w tabeli i w --json; tylko odczyt
ostatnie(kw1, T - 5)
przed = {str(p): p.stat().st_mtime_ns for p in kw1.rglob("*") if p.is_file()}
bufor = io.StringIO()
with contextlib.redirect_stdout(bufor):
    R.main(["--korzen", str(kw1)])
naglowek = bufor.getvalue().splitlines()[0].split()
sprawdz("W10 tabela ma kolumnę „widziani” między „graczy” a „spotkań”", naglowek[naglowek.index("graczy") + 1] == "widziani" and naglowek[naglowek.index("widziani") + 1] == "spotkań", naglowek)
bufor = io.StringIO()
with contextlib.redirect_stdout(bufor):
    R.main(["--korzen", str(kw1), "--json"])
sprawdz("W10b --json niesie widziani i widziani_lista", json.loads(bufor.getvalue())[0]["widziani"] == 2)
sprawdz("W10c tylko odczyt", przed == {str(p): p.stat().st_mtime_ns for p in kw1.rglob("*") if p.is_file()})
# W11: bot nie zmieniony: Licznik i stałe progowe nietknięte (15 s / 5 min), raport nie zmienia stałych globalnych
sprawdz("W11 progi bota bez zmian (MIN_WIDOK_S 15, PRZERWA_S 300)", SG.MIN_WIDOK_S == 15 and SG.PRZERWA_S == 300, (SG.MIN_WIDOK_S, SG.PRZERWA_S))
# W12: licz_widzianych bezpośrednio — pierwszy raz widziany czas i liczba próbek
lw = R.licz_widzianych(seria(0, 4, ["A"]) + seria(5, 6, ["A", "B"]), [], set(), "Bot", T)
sprawdz("W12 licz_widzianych: A 7 próbek, B 2", [(e["nick"], e["probek"]) for e in lw["lista"]] == [("A", 7), ("B", 2)] and lw["widziani"] == 2 and lw["probek_na_spocie"] == 7, lw)

# ---- 26.10 (Karol): „spotkań” BEZ minimalnego czasu widoku (tylko wyświetlanie; licznik bota bez zmian)
# B1: nick widoczny 3 s trzy razy w odstępach > 300 s = 3 spotkania (wg bota 0)
mij3 = seria(0, 2, ["Mijajacy"]) + seria(400, 402, ["Mijajacy"]) + seria(800, 802, ["Mijajacy"])
tmpb1, kb1 = swiat(mij3)
wb1 = wiersz("a", korzen=kb1)
sprawdz("B1 trzy mijania po 3 s w odstępach > 5 min = 3 spotkania bez progu, 0 wg reguł bota (15 s)", nick0(wb1, "Mijajacy") == 3 and wb1["spotkan"] == 3
        and wb1["spotkan_prog15"] == 0 and wb1["nicki_prog15"] == [], wb1)
# B2: dwa mijania w odstępie < 300 s = jedno spotkanie
tmpb2, kb2 = swiat(seria(0, 2, ["Mijajacy"]) + seria(200, 202, ["Mijajacy"]))
wb2 = wiersz("a", korzen=kb2)
sprawdz("B2 dwa mijania w odstępie 200 s (< 300 s) = 1 spotkanie", wb2["spotkan"] == 1 and nick0(wb2, "Mijajacy") == 1, wb2)
# B2b: granica: przerwa równa PRZERWA_S otwiera nowy epizod (jak w Licznik), 299 s nie
tmpb2b, kb2b = swiat([pr(T, ["G"]), pr(T + 299, ["G"]), pr(T + 598, ["G"]), pr(T + 898, ["G"])])
sprawdz("B2b przerwa 299 s = ten sam epizod, 300 s = nowy: próbki 0/299/598/898 s dają 2 spotkania", wiersz("a", korzen=kb2b)["spotkan"] == 2, wiersz("a", korzen=kb2b))
# B3: jedna próbka wystarczy; spotkań/h z tego licznika
tmpb3, kb3 = swiat([pr(T, ["Raz"])] + seria(1, 600, []))
wb3 = wiersz("a", korzen=kb3)
sprawdz("B3 jedna próbka = 1 spotkanie, spotkań/h liczone od niego (~6/h przy 10 min)", wb3["spotkan"] == 1 and 5.5 < wb3["spotkan_na_h"] < 6.5, wb3)
# B4: filtry i kryterium „na spocie” bez zmian (nasze, własny, GM, hp 0, czaszka/pk, stany poza spotem, dojście)
sprawdz("B4 filtry jak dotąd: nasze/GM/hp 0/czaszka/pk/własny nie liczą się także bez progu", R.raport_instancji(kw3, "a")["nicki"] == [("Zwykly", 1)], R.raport_instancji(kw3, "a")["nicki"])
for stan in ("WYPAD", "WPADNIECIE", "PAUZA_STOJ", "STOJ_POWROT", "WYLOGUJ_OBCY", None):
    tmpb5, kb5 = swiat(seria(0, 2, ["Obcy"], stan=stan))
    sprawdz(f"B5 stan {stan}: mijanie poza spotem nie liczy się", wiersz("a", korzen=kb5)["spotkan"] == 0)
tmpb6, kb6 = swiat(seria(0, 2, ["Obcy"]), logi=dojscie_bez_konca)
sprawdz("B6 mijanie w dojściu na spot nie liczy się", wiersz("a", korzen=kb6)["spotkan"] == 0)
# B7: zakres jak dotąd: domyślnie tylko ostatnia sesja, --dzien cały dzień
tmpb7, kb7 = swiat(seria(0, 2, ["Stary"], sesja=1.0) + seria(2000, 2002, ["Nowy"], sesja=2.0))
sprawdz("B7 domyślnie tylko ostatnia sesja (Nowy 1, Stary 0), --dzien obie", nick0(R.raport_instancji(kb7, "a"), "Nowy") == 1 and nick0(R.raport_instancji(kb7, "a"), "Stary") == 0
        and R.raport_instancji(kb7, "a", "20261025")["spotkan"] == 2)
# B8: licznik bota nietknięty: Licznik na tych samych próbkach daje 0 (próg 15 s), a raport ma oba liczniki
l = SG.Licznik(None, 0.0)
zd = []
for r in mij3:
    zd += l.obserwuj(r["t"], ["Mijajacy"], True)
sprawdz("B8 spot_gracz.Licznik na krótkich mijaniach nadal 0 spotkań (bot bez zmian); progi 15/300", zd == [] and SG.MIN_WIDOK_S == 15 and SG.PRZERWA_S == 300)
# B9: tabela CLI ma kolumnę „≥15 s”
bufor = io.StringIO()
with contextlib.redirect_stdout(bufor):
    R.main(["--korzen", str(kb1)])
sprawdz("B9 tabela: kolumna „≥15 s” (reguły bota) obok „spotkań”; najczęstsi z licznika bez progu", "≥15 s" in bufor.getvalue() and "Mijajacy 3" in bufor.getvalue(), bufor.getvalue())
# B10: --min-widok zmienia tylko licznik bota, nie „spotkań” bez progu
sprawdz("B10 --min-widok 1 daje spotkan_prog15 3, a spotkan bez progu bez zmian (3)", (lambda w: (w["spotkan"], w["spotkan_prog15"]))(wiersz("a", korzen=kb1, min_widok=1)) == (3, 3))

print()
print(f"{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
