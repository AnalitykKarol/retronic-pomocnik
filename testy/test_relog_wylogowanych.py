#!/usr/bin/env python3
"""relog_wylogowanych.py (23.10, decyzja Karola: „Boty powinny być wyłączane po wylogowaniu od razu i włączane ponownie”).
Offline: katalog tymczasowy z instancjami, atrapa wykonawcy (nic nie uruchamia, nie dotyka gry), zegar i spanie wstrzykiwane.
Dowodzi: czekanie >= 10 min (po resecie 10:11); postacie POJEDYNCZO (kroki jednej nie przeplatają się z drugą), przerwa 3-6 min tylko MIĘDZY
postaciami; STOP_RECZNY Karola = pominięcie bez kasowania, a relog sam go nie tworzy (zatrzymaj.sh z RETRONIC_RELOG=1); porażka liczy próby,
po MAX_PROB nie jest już gotowa; singleton kolejki; Karol przejmujący postać w trakcie = zero uruchom.
Uruchomienie: RETRONIC_TESTY=1 python3 -I testy/test_relog_wylogowanych.py"""
import fcntl
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["RETRONIC_TESTY"] = "1"
R = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(R))
import relog_wylogowanych as RW  # noqa: E402
import wylogowanie  # noqa: E402

WYNIKI = []


def sprawdz(nazwa, warunek, szczegol=""):
    WYNIKI.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  <-- {str(szczegol)[:300]}"))


T0 = datetime(2026, 10, 23, 11, 0, 0).timestamp()      # poza oknem resetu


class Zegar:
    def __init__(self, t=T0):
        self.t = t
        self.spania = []

    def __call__(self):
        return self.t

    def spij(self, s):
        self.spania.append(s)
        self.t += s


def swiat(ids=("a", "b", "c"), wyl_ts=None, mapa="trolle_edron_z9z", tryb="ostrozny,runy"):
    tmp = tempfile.TemporaryDirectory()
    k = Path(tmp.name)
    (k / "instancje" / "_wspolne").mkdir(parents=True)
    for i in ids:
        (k / "instancje" / i / "logi").mkdir(parents=True)
        (k / "instancje" / i / "profil.json").write_text(json.dumps({"postac": i.capitalize()}))
        with open(k / "instancje" / i / "logi" / "tryb.log", "w") as f:
            f.write(f"2026-10-23 08:00:00 [TRYB] mapa {mapa}: trasa x\n2026-10-23 08:00:00 [TRYB] tryb {tryb.replace(',', '+')}: pokrętła {{}}\n")
        wylogowanie.zapisz(k / "instancje" / i, "ekran logowania", k / "instancje" / i / "logi" / "tryb.log", nick=i.capitalize(),
                           teraz=(wyl_ts or T0 - 1200) + ids.index(i))
    return tmp, k


class Atrapa:
    """Wykonawca bez skutków ubocznych; zapisuje (czas, id, krok). hak[krok] = funkcja(id) wołana na początku kroku; wyn[krok] = (ok, tekst)."""

    def __init__(self, zegar):
        self.z, self.zdarzenia, self.hak, self.wyn = zegar, [], {}, {}

    def _k(self, krok, id_, *a):
        self.zdarzenia.append((self.z.t, id_, krok))
        if krok in self.hak:
            self.hak[krok](id_)
        return self.wyn.get((krok, id_)) or self.wyn.get(krok) or (True, "ok")

    def zamknij(self, id_): return self._k("zamknij", id_)
    def start_klienta(self, id_): return self._k("start_klienta", id_)
    def zaloguj(self, id_): return self._k("zaloguj", id_)

    def czekaj_ekran(self, id_, wzor, limit):
        r = self._k("ekran:" + wzor, id_)
        return r[0], "gra" if r[0] else "nieznany"

    def uruchom(self, id_, nick, mapa, tryb):
        self.arg = getattr(self, "arg", {})
        self.arg[id_] = (nick, mapa, tryb)
        return self._k("uruchom", id_)

    def pierwsze_zabicie(self, id_, limit):
        self.z.spij(45)
        r = self.wyn.get("zabicie") or ("zabity", "Cel Rat zabity")
        self.zdarzenia.append((self.z.t, id_, "zabicie:" + r[0]))
        return r

    def kroki(self, id_):
        return [k for _, i, k in self.zdarzenia if i == id_]


def przebieg(k, W, z, **kw):
    log = []
    w = RW.kolejka(k, W, log.append, zegar=z, spij=z.spij, los=lambda a, b: (a + b) / 2, **kw)
    return w, log


# ---------------------------------------------------------------- najwczesniej
def ts(h, m):
    return datetime(2026, 10, 23, h, m, 0).timestamp()


sprawdz("N1 wylogowanie 08:00 -> relog nie wcześniej niż 08:10", RW.najwczesniej(ts(8, 0)) == ts(8, 10))
sprawdz("N2 wylogowanie 09:58 (reset serwera 10:00) -> 10:11, nie 10:08", RW.najwczesniej(ts(9, 58)) == ts(10, 11), datetime.fromtimestamp(RW.najwczesniej(ts(9, 58))))
sprawdz("N3 wylogowanie 10:05 (serwer jeszcze wstaje) -> 10:15 (dalej z dwóch: +10 min i reset+11)", RW.najwczesniej(ts(10, 5)) == ts(10, 15))
sprawdz("N4 wylogowanie 09:20 (przed oknem resetu) -> 09:30", RW.najwczesniej(ts(9, 20)) == ts(9, 30))
sprawdz("N5 wylogowanie 10:30 (po resecie) -> 10:40", RW.najwczesniej(ts(10, 30)) == ts(10, 40))

# ---------------------------------------------------------------- ocena / kandydaci
tmp, k = swiat(("a", "b", "c"), wyl_ts=T0 - 120)
c = RW.kandydaci(k, T0)
sprawdz("O1 wylogowane 2 min temu: żadna nie gotowa, powód z godziną", len(c) == 3 and not any(x["gotowa"] for x in c) and "nie wcześniej niż" in c[0]["powod"], c)
c = RW.kandydaci(k, T0 + 600)
sprawdz("O2 po 10 min wszystkie gotowe, w kolejności wylogowania", [x["id"] for x in c if x["gotowa"]] == ["a", "b", "c"], c)
(k / "instancje" / "b" / "STOP_RECZNY").touch()
c = {x["id"]: x for x in RW.kandydaci(k, T0 + 600)}
sprawdz("O3 STOP_RECZNY (Karol gra): postać nie gotowa", not c["b"]["gotowa"] and "STOP_RECZNY" in c["b"]["powod"] and c["a"]["gotowa"], c["b"])
(k / "instancje" / "b" / "STOP_RECZNY").unlink()
(k / "instancje" / "_wspolne" / "NADZOR_PAUZA").touch()
sprawdz("O4 NADZOR_PAUZA: nikt nie gotowy", not any(x["gotowa"] for x in RW.kandydaci(k, T0 + 600)))
(k / "instancje" / "_wspolne" / "NADZOR_PAUZA").unlink()
RW.zapisz_stan_prob(k / "instancje" / "a", {"proby": 3, "ost_ts": T0})
c = {x["id"]: x for x in RW.kandydaci(k, T0 + 3600)}
sprawdz("O5 po MAX_PROB nieudanych próbach nie gotowa (eskalacja po stronie nadzoru)", not c["a"]["gotowa"] and c["a"]["proby"] == 3, c["a"])
RW.zapisz_stan_prob(k / "instancje" / "a", {"proby": 1, "ost_ts": T0 + 600 - 60})
c = {x["id"]: x for x in RW.kandydaci(k, T0 + 600)}
sprawdz("O6 ponowienie dopiero po PONOW_MIN od nieudanej próby", not c["a"]["gotowa"], c["a"])
c = {x["id"]: x for x in RW.kandydaci(k, T0 + 600 + 400)}
sprawdz("O7 ... a po tym czasie znów gotowa", c["a"]["gotowa"], c["a"])
wylogowanie.zapisz(k / "instancje" / "c", "stary", teraz=T0 - 20 * 3600)
sprawdz("O8 znacznik starszy niż 12 h = nieaktualny (brak oceny)", RW.ocen(k, "c", T0) is None)
tmp.cleanup()

# ---------------------------------------------------------------- kolejka: pojedynczo, przerwy, bez STOP_RECZNY
tmp, k = swiat(("a", "b", "c"))
z = Zegar()
W = Atrapa(z)
w, log = przebieg(k, W, z)
sprawdz("K1 trzy postacie, wszystkie OK", [(i, r) for i, r, _ in w] == [("a", True), ("b", True), ("c", True)], w)
kolejnosc_krokow = [i for _, i, _k in W.zdarzenia if not _k.startswith("zabicie")]
bloki = [kolejnosc_krokow[0]] + [x for p, x in zip(kolejnosc_krokow, kolejnosc_krokow[1:]) if x != p]
sprawdz("K2 pojedynczo: kroki jednej postaci nie przeplatają się z drugą (a,b,c po jednym bloku)", bloki == ["a", "b", "c"], bloki)
sprawdz("K3 pełny relog każdej: zamknij, start klienta, ekran, zaloguj, ekran gra, uruchom, zabicie",
        [x.split(":")[0] for x in W.kroki("b")] == ["zamknij", "start_klienta", "ekran", "zaloguj", "ekran", "uruchom", "zabicie"], W.kroki("b"))
przerwy = [s for s in z.spania if RW.PRZERWA_S[0] <= s <= RW.PRZERWA_S[1]]
sprawdz("K4 dokładnie dwie przerwy z PRZERWA_S (między a-b i b-c), nie przed pierwszą ani po ostatniej", len(przerwy) == 2, z.spania)
t_b = [t for t, i, kk in W.zdarzenia if i == "b" and kk == "zamknij"][0]
t_a = [t for t, i, kk in W.zdarzenia if i == "a" and kk.startswith("zabicie")][0]
sprawdz("K5 start drugiej >= PRZERWA_S[0] po pierwszym zabiciu pierwszej", t_b - t_a >= RW.PRZERWA_S[0], t_b - t_a)
sprawdz("K6 bot startuje z zapamiętaną mapą i trybem z tryb.log oraz nickiem",
        W.arg["a"] == ("A", "trolle_edron_z9z", "ostrozny,runy"), W.arg)
sprawdz("K7 znaczniki skasowane po udanym relogu, stanu prób brak",
        not any((k / "instancje" / i / "wylogowany.json").exists() or (k / "instancje" / i / RW.STAN_NAZWA).exists() for i in "abc"))
sprawdz("K8 relog sam NIE tworzy STOP_RECZNY (żadna z postaci)", not any((k / "instancje" / i / "STOP_RECZNY").exists() for i in "abc"))
sprawdz("K9 drugie wywołanie niczego nie robi (brak znaczników)", przebieg(k, W, z)[0] == [])
tmp.cleanup()

# ---------------------------------------------------------------- Karol gra / przejmuje postać
tmp, k = swiat(("a", "b", "c"))
(k / "instancje" / "b" / "STOP_RECZNY").touch()
z = Zegar()
W = Atrapa(z)
w, log = przebieg(k, W, z)
sprawdz("L1 Karol gra na b (STOP_RECZNY): b pominięta bez ruchu, a i c zrobione", [i for i, r, _ in w] == ["a", "c"] and W.kroki("b") == [], (w, W.zdarzenia))
sprawdz("L2 STOP_RECZNY Karola nietknięty, znacznik b zostaje", (k / "instancje" / "b" / "STOP_RECZNY").exists() and (k / "instancje" / "b" / "wylogowany.json").exists())
tmp.cleanup()

tmp, k = swiat(("a", "b"))
z = Zegar()
W = Atrapa(z)
W.hak["zaloguj"] = lambda i: (k / "instancje" / i / "STOP_RECZNY").touch() if i == "a" else None      # Karol przejmuje a tuż po logowaniu
w, log = przebieg(k, W, z)
sprawdz("L3 Karol przejął postać w trakcie: uruchom.sh (kasuje STOP_RECZNY) NIE wołany dla a", "uruchom" not in W.kroki("a") and w[0][1] is None, (W.kroki("a"), w))
sprawdz("L4 przejęcie nie jest porażką (zero prób), STOP_RECZNY zostaje, b zrobiona", not (k / "instancje" / "a" / RW.STAN_NAZWA).exists()
        and (k / "instancje" / "a" / "STOP_RECZNY").exists() and w[1] == ("b", True, w[1][2]), w)
tmp.cleanup()

# ---------------------------------------------------------------- porażki
tmp, k = swiat(("a", "b"))
z = Zegar()
W = Atrapa(z)
W.wyn[("zaloguj", "a")] = (False, "kod 7")
w, log = przebieg(k, W, z)
sprawdz("P1 porażka a (zaloguj kod 7) nie zatrzymuje kolejki: b zrobiona", [(i, r) for i, r, _ in w] == [("a", False), ("b", True)], w)
sp = RW.stan_prob(k / "instancje" / "a")
sprawdz("P2 stan prób a: 1 próba, czas, powód; znacznik zostaje", sp.get("proby") == 1 and sp.get("ost_ts") and "zaloguj" in sp.get("ost_blad", "") and (k / "instancje" / "a" / "wylogowany.json").exists(), sp)
z.t += 600
W2 = Atrapa(z)
W2.wyn[("zaloguj", "a")] = (False, "kod 7")
przebieg(k, W2, z)
z.t += 600
przebieg(k, W2, z)
sp = RW.stan_prob(k / "instancje" / "a")
sprawdz("P3 po trzech porażkach 3 próby; czwarty przebieg nie rusza a", sp.get("proby") == 3 and (przebieg(k, Atrapa(z), z)[0] == []), sp)
tmp.cleanup()

tmp, k = swiat(("a",))
z = Zegar()
W = Atrapa(z)
W.wyn["zabicie"] = ("problem", "ROZŁĄCZENIE: ...")
w, _ = przebieg(k, W, z)
sprawdz("P4 bot wystartował i od razu ROZŁĄCZENIE/Traceback w logu: porażka (próba liczona)", w[0][1] is False and RW.stan_prob(k / "instancje" / "a").get("proby") == 1, w)
tmp.cleanup()

tmp, k = swiat(("a",))
(k / "instancje" / "a" / "wylogowany.json").unlink()
wylogowanie.zapisz(k / "instancje" / "a", "x", None, teraz=T0 - 1200)          # znacznik bez mapy
w, _ = przebieg(k, Atrapa(Zegar()), Zegar())
sprawdz("P5 znacznik bez mapy: porażka z powodem, bot nie startuje", w[0][1] is False and "mapy" in w[0][2], w)
tmp.cleanup()

# ---------------------------------------------------------------- singleton, nadzor_logowanie, wykonawca
tmp, k = swiat(("a",))
f = open(k / "instancje" / "_wspolne" / RW.SINGLETON, "a")
fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
z = Zegar()
W = Atrapa(z)
sprawdz("S1 kolejka_dziala widzi trzymaną blokadę", RW.kolejka_dziala(k))
w, log = przebieg(k, W, z)
sprawdz("S2 druga kolejka przy trzymanej blokadzie: nic nie robi", w == [] and W.zdarzenia == [] and any("trwa" in l for l in log), (w, log))
fcntl.flock(f, fcntl.LOCK_UN)
f.close()
sprawdz("S3 po zwolnieniu blokada wolna", not RW.kolejka_dziala(k))
g = open(k / "instancje" / "_wspolne" / RW.ZAMEK_LOGOWANIA, "a")
fcntl.flock(g, fcntl.LOCK_EX | fcntl.LOCK_NB)
z = Zegar()
W = Atrapa(z)
w, log = przebieg(k, W, z)
sprawdz("S4 inna akcja logowania trwa (zamek nadzoru): czeka ZAMEK_CZEKAJ_S, potem pomija bez ruchu i bez próby",
        w[0][1] is None and W.zdarzenia == [] and sum(z.spania) >= RW.ZAMEK_CZEKAJ_S and not (k / "instancje" / "a" / RW.STAN_NAZWA).exists(), (w, sum(z.spania)))
g.close()
tmp.cleanup()

wk = RW.WykonawcaRelog(R)
e = wk._env("a", RETRONIC_POSTAC="A")
sprawdz("W1 wykonawca: RETRONIC_ID, RETRONIC_RELOG=1 (zatrzymaj.sh nie tworzy STOP_RECZNY), RETRONIC_POSTAC", e["RETRONIC_ID"] == "a" and e["RETRONIC_RELOG"] == "1" and e["RETRONIC_POSTAC"] == "A", e)

tmp, k = swiat(("a",))
wk = RW.WykonawcaRelog(k, spij=lambda s: None)
(k / "instancje" / "a" / "logi" / "mozg-stdout-1.log").write_text("start\nCel Rat zabity na (1, 2, 8).\n")
sprawdz("W2 pierwsze_zabicie: widzi zabicie w najnowszym logu", wk.pierwsze_zabicie("a", 30)[0] == "zabity")
(k / "instancje" / "a" / "logi" / "mozg-stdout-2.log").write_text("start\nROZŁĄCZENIE: ekran logowania\n")
os.utime(k / "instancje" / "a" / "logi" / "mozg-stdout-2.log", (T0 + 100, T0 + 100))
sprawdz("W3 ... a ROZŁĄCZENIE w nowszym logu = problem", wk.pierwsze_zabicie("a", 30)[0] == "problem")
(k / "instancje" / "a" / "logi" / "mozg-stdout-2.log").write_text("start\nidę\n")
os.utime(k / "instancje" / "a" / "logi" / "mozg-stdout-2.log", (T0 + 200, T0 + 200))
sprawdz("W4 brak zabicia w limicie = czas (nie porażka kolejki)", wk.pierwsze_zabicie("a", 20)[0] == "czas")
tmp.cleanup()

# ---------------------------------------------------------------- zatrzymaj.sh: nie Karol = bez STOP_RECZNY
def zatrzymaj(relog):
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "p"
        (d / "instancje" / "x").mkdir(parents=True)
        for n in ("zatrzymaj.sh", "instancja.py"):
            shutil.copy(R / n, d / n)
        (Path(td) / "bin").mkdir()
        ns = Path(td) / "bin" / "notify-send"
        ns.write_text("#!/bin/sh\nexit 0\n")
        ns.chmod(ns.stat().st_mode | stat.S_IEXEC)
        env = {k_: v for k_, v in os.environ.items() if not k_.startswith("RETRONIC_")}
        env.update(RETRONIC_ID="x", PATH=f"{Path(td) / 'bin'}:{os.environ['PATH']}", XDG_RUNTIME_DIR=td)
        if relog:
            env["RETRONIC_RELOG"] = "1"
        subprocess.run(["bash", str(d / "zatrzymaj.sh")], cwd=str(d), env=env, capture_output=True, timeout=60)
        return [p.name for p in (d / "instancje" / "x").iterdir()] + [p.name for p in d.iterdir() if p.name.startswith("STOP")]


bez, z_relogiem = zatrzymaj(False), zatrzymaj(True)
sprawdz("Z1 zatrzymaj.sh (Karol): STOP i STOP_RECZNY powstają jak dotąd", "STOP_RECZNY" in bez and "STOP" in bez, bez)
sprawdz("Z2 zatrzymaj.sh z RETRONIC_RELOG=1: STOP tak, STOP_RECZNY NIE", "STOP_RECZNY" not in z_relogiem and "STOP" in z_relogiem, z_relogiem)

print(f"{sum(WYNIKI)}/{len(WYNIKI)}")
sys.exit(0 if all(WYNIKI) else 1)
