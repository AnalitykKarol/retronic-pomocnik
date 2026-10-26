#!/usr/bin/env python3
"""Dymek „obcy gracz obok” (powiadom_obcy.py, 26.10): offline, bez notify-send i bez gry. Fixture w katalogu tymczasowym: syntetyczna
telemetria (epizody, granica przerwy 299/300 s, filtry, poza spotem, dojście, północ, restart i podmiana pliku, niedopisana linia),
atrapa notify (skrypt zapisujący argumenty), zgodność z raportem spotkań (R.licz) na losowych danych.
Uruchomienie: RETRONIC_TESTY=1 python3 -I testy/test_powiadom_obcy.py"""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import contextlib
import io
import json
import pathlib
import random
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from datetime import datetime

sys.dont_write_bytecode = True
tmp = pathlib.Path(tempfile.mkdtemp(prefix="po"))
_os.environ["XDG_RUNTIME_DIR"] = str(tmp / "rt")
(tmp / "rt").mkdir()
_os.environ["RETRONIC_POWIADOM_OBCY_ODSWIEZ_S"] = "0.05"
KAT0 = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KAT0))
sys.path.insert(0, str(KAT0 / "narzedzia"))
import instancja  # noqa: E402
import powiadom  # noqa: E402
import powiadom_obcy as po  # noqa: E402
import spot_gracz as SG  # noqa: E402
import spotkania_graczy_raport as R  # noqa: E402

ok = []


def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


def czekaj(warunek, limit=6.0):
    k = time.time() + limit
    while time.time() < k:
        if warunek():
            return True
        time.sleep(0.03)
    return False


def swiat(nazwa, postac="Hero", **profil):
    """Katalog bota z instancją `nazwa`; -> (korzen, ścieżka instancji, logi)."""
    korzen = tmp / nazwa
    inst = korzen / "instancje" / "tst"
    (inst / "logi").mkdir(parents=True)
    (inst / "profil.json").write_text(json.dumps({"postac": postac, **profil}))
    return korzen, inst, inst / "logi"


def g(n, odl=3, **kw):
    return {"n": n, "dx": odl, "dy": 0, "odl": odl, "hp": 100, "gracz": True, **kw}


def pr(t, stwory, stan="WALKA", **kw):
    return {"t": float(t), "typ": "probka", "stan": stan, "poz": [32000, 32000, 8], "hp": 100, "stwory": stwory, "src": "mozg", **kw}


def zapisz(plik, rekordy, tryb="a"):
    with open(plik, tryb, encoding="utf-8") as f:
        for r in rekordy:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


BAZA = datetime(2026, 10, 26, 12, 0, 0).timestamp()


def detektor(logi, nasze=(), wlasny="Hero"):
    return po.Detektor(po.LeniweOkna(logi, ttl=None), {SG.klucz(n) for n in nasze}, wlasny)


def zdarzenia(det, probki):
    return [(e["nick"], e["t"], e["odl"]) for r in probki for e in det.przetworz(r)]


# ---- 1. drobiazgi
sprawdz("1a pola(): 1 pole, 2 pola, 5 pól, 12 pól, 22 pola", [po.pola(n) for n in (1, 2, 5, 12, 22, 0)] ==
        ["1 pole", "2 pola", "5 pól", "12 pól", "22 pola", "0 pól"], [po.pola(n) for n in (1, 2, 5, 12, 22, 0)])
sprawdz("1b tytuł jak w specyfikacji", po.tytul_dymka("Geblish", "Vados", 3, "ph_raty_z8") == "Geblish: Vados obok (3 pola) · ph_raty_z8",
        po.tytul_dymka("Geblish", "Vados", 3, "ph_raty_z8"))
sprawdz("1c tytuł bez odległości i mapy", po.tytul_dymka("Geblish", " Va  dos ", None, None) == "Geblish: Va dos obok")
sprawdz("1d odleglosc(): najmniejsza z wpisów tego nicku", po.odleglosc(pr(0, [g("Vados", 7), g("vados", 2), g("Inny", 1)]), "Vados") == 2)

# ---- 2. granica przerwy 299/300 s i epizody
_, _, logi = swiat("s2")
d = detektor(logi)
sprawdz("2a pierwszy widok = dymek (z odległością)", zdarzenia(d, [pr(BAZA, [g("Vados", 4)])]) == [("Vados", BAZA, 4)])
sprawdz("2b kolejne próbki w epizodzie bez dymku", zdarzenia(d, [pr(BAZA + i, [g("Vados", 2)]) for i in range(1, 60)]) == [])
d = detektor(logi)
zdarzenia(d, [pr(BAZA, [g("A")])])
sprawdz("2c przerwa 299 s: ten sam epizod", zdarzenia(d, [pr(BAZA + 299, [g("A")])]) == [])
d = detektor(logi)
zdarzenia(d, [pr(BAZA, [g("A")])])
sprawdz("2d przerwa 300 s: nowy epizod, dymek", [e[0] for e in zdarzenia(d, [pr(BAZA + 300, [g("A")])])] == ["A"])
d = detektor(logi)
w = zdarzenia(d, [pr(BAZA, [g("A")]), pr(BAZA + 299, [g("A")]), pr(BAZA + 598, [g("A")]), pr(BAZA + 897, [g("A")]), pr(BAZA + 1196, [g("A")])])
sprawdz("2e epizod trwa, dopóki każda przerwa < 300 s (łańcuch co 299 s = jeden dymek)", len(w) == 1, w)
d = detektor(logi)
w = zdarzenia(d, [pr(BAZA, [g("A")]), pr(BAZA + 1, [g("B")]), pr(BAZA + 500, [g("A"), g("B")])])
sprawdz("2f dwa nicki liczone osobno: A, B, potem oba nowe po 500 s", [e[0] for e in w] == ["A", "B", "A", "B"], w)
d = detektor(logi)
w = zdarzenia(d, [pr(BAZA, [g("Vados", 5), g("vados", 2)])])
sprawdz("2g ten sam nick dwa razy w próbce = jeden dymek, mniejsza odległość", w == [("Vados", BAZA, 2)], w)
d = detektor(logi)
w = zdarzenia(d, [pr(BAZA, [g("Vados", 1)]), pr(BAZA + 1, [g("Vados", 12)])])
sprawdz("2h bez progu odległości: także 1 pole i 12 pól (jeden epizod)", len(w) == 1 and w[0][2] == 1, w)
d = detektor(logi)
sprawdz("2i bez progu czasu widoku: jedna próbka wystarcza", len(zdarzenia(d, [pr(BAZA, [g("Mignal")])])) == 1)

# ---- 3. filtry (te same co licznik spotkań: R._widoczni_obcy)
korzen3, inst3, logi3 = swiat("s3", postac="Hero")
(korzen3 / "instancje" / "inna").mkdir()
(korzen3 / "instancje" / "inna" / "profil.json").write_text(json.dumps({"postac": "Nasza Druga"}))
nasze3 = R.nasze_nicki_instancji(korzen3)
d = po.Detektor(po.LeniweOkna(logi3, ttl=None), nasze3, "Hero")
proba = pr(BAZA, [g("Hero"), g("hero"), g("Nasza  Druga"), g("Kolanosh"), g("GM Czarek"), g("CM Ktos"), g("Z Czaszka", czaszka=1), g("Skull", skull=1),
                  g("Pk", pk=1), g("Martwy", hp=0), g("Ujemny", hp=-3), {"n": "Szczur", "dx": 1, "dy": 1, "odl": 1, "hp": 100, "gracz": False},
                  g("Zwykly", 6)])
sprawdz("3a filtry: zostaje tylko „Zwykly” (własny, nasze z profili i NASZE_ZNANE, GM/CM, czaszka/skull/pk, hp<=0, potwór odpadają)",
        zdarzenia(d, [proba]) == [("Zwykly", BAZA, 6)], zdarzenia(detektor(logi3), [proba]))
w = [zdarzenia(po.Detektor(po.LeniweOkna(logi3, ttl=None), nasze3, "Hero"), [pr(BAZA, [g("Obcy")], stan=s)]) for s in
     ("WYPAD", "WPADNIECIE", "PAUZA_STOJ", "STOJ_POWROT", "WYLOGUJ_OBCY", None)]
sprawdz("3b poza spotem (WYPAD/WPADNIECIE/PAUZA_STOJ/STOJ_POWROT/WYLOGUJ_OBCY/brak stanu) żadnego dymka", all(x == [] for x in w), w)
sprawdz("3c na spocie stany WALKA/PETLA/JEDZENIE dają dymek", all(len(zdarzenia(po.Detektor(po.LeniweOkna(logi3, ttl=None), nasze3, "Hero"),
        [pr(BAZA, [g("Obcy")], stan=s)])) == 1 for s in ("WALKA", "PETLA", "JEDZENIE")))
d = po.Detektor(po.LeniweOkna(logi3, ttl=None), nasze3, "Hero")
w = zdarzenia(d, [pr(BAZA, [g("Obcy")]), pr(BAZA + 250, [g("Obcy")], stan="WYPAD"), pr(BAZA + 310, [g("Obcy")])])
sprawdz("3d widok poza spotem nie przedłuża epizodu (jak w raporcie): 0 s i 310 s = 2 dymki", len(w) == 2, w)
d = po.Detektor(po.LeniweOkna(logi3, ttl=None), nasze3, "Hero")
w = zdarzenia(d, [pr(BAZA, [g("Hero")]), pr(BAZA + 1, [])])
sprawdz("3e sama postać / pusta próbka = nic", w == [])

# ---- 4. dojście na spot (logi bota)
korzen4, inst4, logi4 = swiat("s4")
(logi4 / "mozg-stdout-1026-1200.log").write_text("12:00:01 Start: trasa 100 pkt\n12:00:05 Dojście: trasa 300 pkt\n12:10:00 Dojście zakończone\n12:10:05 petla\n")
d = detektor(logi4)
w = zdarzenia(d, [pr(BAZA + 60, [g("Obcy")]), pr(BAZA + 599, [g("Obcy")]), pr(BAZA + 601, [g("Obcy")])])
sprawdz("4a w dojściu (do 12:10:00) nic; po „Dojście zakończone” pierwszy widok to dymek", len(w) == 1 and w[0][1] == BAZA + 601, w)
(logi4 / "mozg-stdout-1026-1300.log").write_text("13:00:01 Start: trasa 100 pkt\n13:00:05 Dojście: trasa 300 pkt\n")
d = detektor(logi4)
sprawdz("4b dojście bez zakończenia = cała reszta sesji to dojście", zdarzenia(d, [pr(BAZA + 3600 + 600, [g("Obcy")])]) == [])

# ---- 5. mapa z tryb.log, fallback ostatnie.json
(logi4 / "tryb.log").write_text("2026-10-26 11:00:00 [TRYB] mapa trolle_edron: trasa x\n2026-10-26 11:30:00 [TRYB] tryb ostrozny\n"
                                "2026-10-26 12:30:00 [TRYB] mapa ph_raty_z8: trasa y\n")
m = po.MapaZLogu(inst4)
sprawdz("5a mapa w chwili t z tryb.log", (m.mapa(BAZA), m.mapa(BAZA + 3600)) == ("trolle_edron", "ph_raty_z8"), (m.mapa(BAZA), m.mapa(BAZA + 3600)))
(inst4 / "ostatnie.json").write_text(json.dumps({"mapa": "z_ostatnie"}))
sprawdz("5b przed pierwszym wpisem: fallback ostatnie.json", m.mapa(BAZA - 86400) == "z_ostatnie")
(logi4 / "tryb.log").unlink()
sprawdz("5c brak tryb.log: fallback ostatnie.json", po.MapaZLogu(inst4).mapa(BAZA) == "z_ostatnie")
(inst4 / "ostatnie.json").unlink()
sprawdz("5d brak wszystkiego: None", po.MapaZLogu(inst4).mapa(BAZA) is None)

# ---- 6. ogon plików: niedopisana linia, restart bota, północ, podmiana
_, _, logi6 = swiat("s6")
pl = logi6 / "telemetria-20261026.jsonl"
zapisz(pl, [pr(100, [g("A")]), pr(101, [])], "w")
o = po.Ogon(logi6)
sprawdz("6a rozgrzewka czyta tylko t >= granicy i ustawia offset na koniec", [r["t"] for r in o.rozgrzewka(101)] == [101.0] and o.nowe() == [])
l = json.dumps(pr(102, [g("B")])) + "\n"
with open(pl, "a") as f:
    f.write(l[:20])
sprawdz("6b niedopisana linia zostaje na później", o.nowe() == [])
with open(pl, "a") as f:
    f.write(l[20:])
sprawdz("6c po dopisaniu reszty linia przychodzi raz", [r["t"] for r in o.nowe()] == [102.0] and o.nowe() == [])
with open(pl, "a") as f:
    f.write("to nie json\n" + json.dumps({"t": 5, "typ": "zabicie"}) + "\n" + json.dumps(pr(103, [], src="inne")) + "\n")
zapisz(pl, [pr(104, [])])
sprawdz("6d śmieci, inne typy i src≠mozg pomijane", [r["t"] for r in o.nowe()] == [104.0])
zapisz(pl, [pr(200, [g("A")])])
sprawdz("6e restart bota = dalsze dopisywanie do tego samego pliku (nowa sesja/pid)", [(r["t"], r.get("pid")) for r in o.nowe()] == [(200.0, None)])
zapisz(pl, [pr(300, [g("A")], pid=7, sesja=300)])
sprawdz("6f próbki nowego procesu przychodzą", [r["t"] for r in o.nowe()] == [300.0])
# północ: stary plik dostaje jeszcze dopisek, nowy plik od początku
zapisz(pl, [pr(86399, [g("A")])])
nowy = logi6 / "telemetria-20261027.jsonl"
zapisz(nowy, [pr(86401, [g("A")]), pr(86402, [g("A")])], "w")
w = o.nowe()
sprawdz("6g północ: dopisek starego pliku i nowy plik, po t", [r["t"] for r in w] == [86399.0, 86401.0, 86402.0], [r["t"] for r in w])
zapisz(pl, [pr(86400, [g("A")])])           # spóźniony zapis do starego pliku po północy
zapisz(nowy, [pr(86403, [])])
sprawdz("6h spóźniony zapis do starego pliku po północy nie ginie", [r["t"] for r in o.nowe()] == [86400.0, 86403.0])
# obcięcie / podmiana
zapisz(pl, [pr(1, [g("Z")])], "w")
sprawdz("6i obcięty plik czytany od początku", [r["t"] for r in o.nowe()] == [1.0])
pl.unlink()
zapisz(pl, [pr(2, [g("Z")]), pr(3, [g("Z")])], "w")
sprawdz("6j podmieniony plik (nowy i-węzeł) czytany od początku", [r["t"] for r in o.nowe()] == [2.0, 3.0])
sprawdz("6k brak plików: pusto, bez wyjątku", po.Ogon(tmp / "nie_ma").nowe() == [] and po.Ogon(tmp / "nie_ma").rozgrzewka(0) == [])
# duży plik: rozgrzewka z końca, pierwsza linia przycięta nie psuje wyniku
_, _, logi6b = swiat("s6b")
duzy = logi6b / "telemetria-20261026.jsonl"
zapisz(duzy, [pr(i, [g("Pad" * 20)] * 3) for i in range(0, 400)], "w")
stare_b = po.ROZGRZEWKA_BAJTY
po.ROZGRZEWKA_BAJTY = 5000
rr = po.Ogon(logi6b).rozgrzewka(0)
po.ROZGRZEWKA_BAJTY = stare_b
sprawdz("6l rozgrzewka z końca dużego pliku: tylko kompletne linie, kończy się na ostatniej próbce", 0 < len(rr) < 400 and rr[-1]["t"] == 399.0, (len(rr), rr[-1]["t"] if rr else None))

# ---- 7. zgodność z raportem spotkań na losowych danych (R.licz)
korzen7, inst7, logi7 = swiat("s7")
(korzen7 / "instancje" / "inna").mkdir()
(korzen7 / "instancje" / "inna" / "profil.json").write_text(json.dumps({"postac": "Kumpel"}))
(logi7 / "mozg-stdout-1026-1200.log").write_text("12:00:01 Start\n12:00:05 Dojście: trasa 300 pkt\n12:40:00 Dojście zakończone\n")
rng = random.Random(26)
pula = ["Vados", "Usio", "Kumpel", "Hero", "GM Bob", "Zgon", "Czaszka", "Ciagly"]
t = BAZA - 600
lista = []
for _ in range(4000):
    t += rng.choice([1, 1, 1, 2, 5, 20, 60, 120, 299, 300, 301, 400, 900])
    st = []
    for n in pula:
        if rng.random() < (0.08 if n != "Ciagly" else 0.5):
            kw = {"czaszka": 1} if n == "Czaszka" and rng.random() < 0.7 else {}
            st.append(g(n, rng.randint(0, 8), **({"hp": 0} if n == "Zgon" and rng.random() < 0.5 else {}), **kw))
    lista.append(pr(t, st, stan=rng.choice(["WALKA", "WALKA", "WALKA", "PETLA", "WYPAD", "PAUZA_STOJ", "JEDZENIE", None])))
nasze7 = R.nasze_nicki_instancji(korzen7)
okna7 = R.okna_dojscia(logi7, 2026)
rap = R.licz(lista, okna7, nasze7, "Hero")
d7 = po.Detektor(po.LeniweOkna(logi7, ttl=None), nasze7, "Hero")
ev7 = Counter(SG.klucz(n) for n, _, _ in zdarzenia(d7, lista))
oczek = {SG.klucz(n): c for n, c in rap["nicki"]}
sprawdz("7a liczba dymków per nick == `nicki` raportu (R.licz), 4000 losowych próbek", dict(ev7) == oczek and sum(oczek.values()) > 50, (dict(ev7), oczek))
sprawdz("7b suma dymków == `spotkan` raportu", sum(ev7.values()) == rap["spotkan"], (sum(ev7.values()), rap["spotkan"]))
zapisz(inst7 / "logi" / "telemetria-20261026.jsonl", lista, "w")
with contextlib.redirect_stdout(io.StringIO()) as buf:
    n_sucho = po.sucho(str(korzen7), "tst", "20261026")
sprawdz("7c --sucho == raport (`zgodne`) i wypisuje czas, nick, odległość, mapę", n_sucho == rap["spotkan"] and "zgodne" in buf.getvalue()
        and "Hero: " in buf.getvalue() and any(x in buf.getvalue() for x in ("pól", "pola", "pole")), buf.getvalue()[:300])
with contextlib.redirect_stdout(io.StringIO()) as buf2:
    po.sucho(str(korzen7), "tst", "20250101")
sprawdz("7d --sucho dla dnia bez telemetrii: komunikat, 0", "brak telemetrii" in buf2.getvalue())

# ---- 8. ustaw_flage: edycja tekstowa
def flaga(tekst, wartosc=True):
    p = tmp / "profil_x.json"
    p.write_text(tekst)
    po.ustaw_flage(p, wartosc)
    return p.read_text()
a = '{\n "proxy": {\n  "port": 80\n },\n "postac": "X",\n "nadzor": true\n}\n'
w = flaga(a)
sprawdz("8a wpis dopisany na końcu obiektu, reszta bez zmian", json.loads(w)["powiadom_obcy"] is True and w.startswith(a[:a.rindex("true") + 4]) and json.loads(w)["proxy"] == {"port": 80}, w)
sprawdz("8b kolejne włączenie nie dubluje klucza", w.count("powiadom_obcy") == 1 and flaga(w).count("powiadom_obcy") == 1)
sprawdz("8c wyłączenie: false", json.loads(flaga(w, False))["powiadom_obcy"] is False)
sprawdz("8d JSON w jednej linii", json.loads(flaga('{"postac": "X"}')) == {"postac": "X", "powiadom_obcy": True})
sprawdz("8e pusty obiekt", json.loads(flaga("{}")) == {"powiadom_obcy": True})
try:
    flaga("[1]")
    sprawdz("8f nie-obiekt odrzucony", False)
except (ValueError, TypeError):
    sprawdz("8f nie-obiekt odrzucony", True)

# ---- 9. start automatyczny (--uruchom) i procesy
korzen9, inst9, logi9 = swiat("s9")
rt9 = tmp / "rt"
wywolania = []
class Proc:
    pid = 4242
def popen(cmd, **kw):
    wywolania.append((cmd, kw))
    return Proc()
proc = tmp / "proc"
proc.mkdir()
sprawdz("9a flaga wyłączona: nie startuje", "wyłączony" in po.uruchom("tst", korzen9, rt9, str(proc), popen) and not wywolania)
sprawdz("9b brak RETRONIC_ID: komunikat, bez wyjątku", "brak RETRONIC_ID" in po.uruchom("", korzen9, rt9, str(proc), popen))
po.ustaw_flage(inst9 / "profil.json", True)
sprawdz("9c flaga włączona: startuje odłączony (setsid, python3 -I)", "wystartowany (pid 4242)" in po.uruchom("tst", korzen9, rt9, str(proc), popen)
        and wywolania[0][0][1] == "-I" and wywolania[0][1]["start_new_session"] and wywolania[0][1]["env"]["RETRONIC_ID"] == "tst"
        and wywolania[0][1]["env"]["RETRONIC_POWIADOM_OBCY_AUTO"] == "1", wywolania)
for pid, cmd, rid in ((111, "python3 -I /x/powiadom_obcy.py", "tst"), (112, "python3 -I /x/powiadom_obcy.py --uruchom", "tst"),
                      (113, "python3 -I /x/testy/test_powiadom_obcy.py", "tst"), (114, "python3 -I /x/powiadom_obcy.py", "inna")):
    (proc / str(pid)).mkdir()
    (proc / str(pid) / "comm").write_text("python3\n")
    (proc / str(pid) / "cmdline").write_bytes(cmd.replace(" ", "\0").encode())
    (proc / str(pid) / "environ").write_bytes(f"RETRONIC_ID={rid}\0".encode())
sprawdz("9d czytniki(): tylko czytnik tej instancji (nie starter, nie plik testowy, nie inna instancja)", po.czytniki("tst", str(proc)) == [111], po.czytniki("tst", str(proc)))
wywolania.clear()
sprawdz("9e drugi start = „już działa”, bez nowego procesu", "już działa (pid 111)" in po.uruchom("tst", korzen9, rt9, str(proc), popen) and not wywolania)

# ---- 10. powiadom.py: limit godzinowy własny
t_ = [1000.0]
wys = []
def nowy_pw(**kw):
    return powiadom.Powiadamiacz(uruchom=lambda a: wys.append(a), zegar=lambda: t_[0], cisza=tmp / "nie_ma_ciszy", watek=False, **kw)
pw = nowy_pw()
n_dom = sum(pw.powiadom(f"t{i}", "", "low", klucz=f"obcy:tst:{i}") for i in range(30))
pw2 = nowy_pw(limit_h=po.LIMIT_H)
n_wl = sum(pw2.powiadom(f"t{i}", "", "low", klucz=f"obcy:tst:{i}") for i in range(30))
sprawdz("10a domyślny Powiadamiacz nadal 20/h; z limit_h=60 przechodzi 30 dymków", (n_dom, n_wl) == (20, 30), (n_dom, n_wl))
sprawdz("10b klucz instancja+nick: drugi dymek tego samego nicku w 60 s odrzucony, po 60 s przechodzi", not pw2.powiadom("x", "", "low", klucz="obcy:tst:5")
        and (t_.__setitem__(0, 1061.0) or pw2.powiadom("x", "", "low", klucz="obcy:tst:5")))
sprawdz("10c dymek low z -a Retronic", any(a[:5] == ["-a", "Retronic", "-u", "low", "-t"] for a in wys), wys[:1])

# ---- 11. pętla czytnika na żywo (wątek, atrapa notify, prawdziwy zegar)
korzen11, inst11, logi11 = swiat("s11", postac="Geblish", powiadom_obcy=True)
(inst11 / "logi" / "tryb.log").write_text(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 3600)) + " [TRYB] mapa ph_raty_z8: trasa x\n")
s11 = instancja.sciezki("tst", tmp / "rt", korzen11)
dymki = []
pw11 = powiadom.Powiadamiacz(uruchom=lambda a: dymki.append(a), cisza=tmp / "nie_ma_ciszy", watek=False, limit_h=po.LIMIT_H)
dzis = time.strftime("%Y%m%d")
plik11 = logi11 / f"telemetria-{dzis}.jsonl"
now = time.time()
# przed startem czytnika: Vados widziany 60 s temu (rozgrzewka ma go zapamiętać), Stary 1000 s temu
zapisz(plik11, [pr(now - 1000, [g("Stary", 2)]), pr(now - 60, [g("Vados", 3)])], "w")
po.SPRAWDZ_FLAGE_S = 0.2
wynik11 = []
w11 = threading.Thread(target=lambda: wynik11.append(po.petla(s11, "Geblish", powiadamiacz=pw11, auto=True)), daemon=True)
w11.start()
time.sleep(0.4)
zapisz(plik11, [pr(time.time(), [g("Vados", 2)]), pr(time.time(), [g("Stary", 4)]), pr(time.time(), [g("Nowy", 6)])])
czekaj(lambda: len(dymki) >= 2)
time.sleep(0.4)
tytuly = [a[-2] for a in dymki]
sprawdz("11a po starcie: Vados (widziany 60 s przed startem) bez dymka; Stary (1000 s) i Nowy dostają", sorted(tytuly) == sorted([
    "Geblish: Stary obok (4 pola) · ph_raty_z8", "Geblish: Nowy obok (6 pól) · ph_raty_z8"]), tytuly)
zapisz(plik11, [pr(time.time(), [g("Nowy", 1), g("Vados", 3)], stan="WYPAD")])
zapisz(plik11, [pr(time.time() - 600, [g("Zaleg", 1)])])           # próbka z przeszłości (>STARE_S) nie daje dymka
time.sleep(0.5)
sprawdz("11b WYPAD i stara próbka: bez nowych dymków", len(dymki) == 2, [a[-2] for a in dymki])
log11 = pathlib.Path(logi11 / f"powiadom-obcy-{dzis}.log").read_text()
sprawdz("11c log: każdy epizod z czasem, nickiem, odl, mapą i werdyktem", "Nowy odl=6 mapa=ph_raty_z8 dymek=tak" in log11 and "Zaleg" in log11 and "[stara próbka]" in log11, log11)
po.ustaw_flage(inst11 / "profil.json", False)
w11.join(5)
sprawdz("11d zdjęcie flagi kończy czytnik (auto)", not w11.is_alive() and wynik11 == ["flaga"], wynik11)

# ---- 12. start z sesja.sh i domyślnie wyłączone
sesja = KAT0 / "sesja.sh"
tekst = sesja.read_text()
sprawdz("12a sesja.sh: składnia", subprocess.run(["bash", "-n", str(sesja)]).returncode == 0)
sprawdz("12b sesja.sh woła powiadom_obcy.py --uruchom (raz) obok czytnika czatu", tekst.count('powiadom_obcy.py" --uruchom') == 1 and 'powiadom_czat.py" --uruchom' in tekst)
wlaczone = [p.parent.name for p in (KAT0 / "instancje").glob("*/profil.json") if po.profil_wlaczony(p.parent)]
sprawdz("12c domyślnie wyłączone: żaden profil.json instancji nie ma powiadom_obcy=true", wlaczone == [], wlaczone)

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
