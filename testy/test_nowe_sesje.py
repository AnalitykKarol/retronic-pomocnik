#!/usr/bin/env python3
"""Nowe sesje trafiają do nadzorcy i monitora SAME (22.10, wymaganie Karola: „każda aktywna sesja od razu powinna trafiać do nadzorcy
i monitora”). Offline: katalogi tymczasowe, atrapy źródeł i wykonawcy (nic nie startuje, nie dotyka gry ani procesów).
Dowodzi:
  monitor_wykrycia: nowa instancja pojawia się w monitorze bez restartu; nowy mozg-stdout-*.log przejmuje źródło, a ogon starego
    logu nie ginie; sesja gry bez bota jest w tabeli; zniknięta instancja odpada;
  grafik: poza_pula/powod_poza_pula mówią, DLACZEGO instancja nie jest pilnowana (nadzor:false, test*, brak profilu);
  nadzor: postać online z botem, której nie ma w istniejącym grafiku, jest brana pod nadzór (zacięty bot dostaje restart), ręczna gra
    bez bota nadal jest nietykalna, sesja online poza pulą daje ostrzeżenie zamiast ciszy.
Stary kod (kopie .bak-20261022-nowe-sesje) nie przechodzi: brak przebieg/synchronizuj w monitorze, brak poza_pula w grafiku,
zacięty bot spoza grafiku bez restartu.
Uruchomienie: python3 -I testy/test_nowe_sesje.py   (pytest nie jest zainstalowany w systemowym pythonie; `python3 -m pytest` działa tam, gdzie jest)"""
import json
import os
import re
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

sys.dont_write_bytecode = True
KORZEN = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
sys.path.insert(0, str(KORZEN / "testy"))
import grafik as G  # noqa: E402
import monitor_wykrycia as M  # noqa: E402
import nadzor as N  # noqa: E402
import test_nadzor as TN  # noqa: E402  (Swiat, nz, zmiana: fałszywy świat nadzorcy)


# ---------------------------------------------------------------- monitor
class Drzewo:
    """Katalog z instancjami dla monitora + atrapa instancja.procesy (id -> wzorce uruchomionych procesów)."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.k = Path(self.tmp.name)
        (self.k / "instancje" / "_wspolne").mkdir(parents=True)
        self.procesy = {}
        self._orig = M.instancja.procesy
        M.instancja.procesy = self._fake

    def _fake(self, wzor, id_=None):
        return [1] if any(re.search(wzor, w) for w in self.procesy.get(id_, ())) else []

    def dodaj(self, id_):
        (self.k / "instancje" / id_ / "logi").mkdir(parents=True, exist_ok=True)
        (self.k / "instancje" / id_ / "profil.json").write_text(json.dumps({"postac": id_}))

    def log(self, id_, nazwa, linie, mtime):
        p = self.k / "instancje" / id_ / "logi" / nazwa
        with open(p, "a", encoding="utf-8") as f:
            for l in linie:
                f.write(f"{time.strftime('%H:%M:%S')} {l}\n")
        os.utime(p, (mtime, mtime))
        return p

    def zamknij(self):
        M.instancja.procesy = self._orig
        self.tmp.cleanup()


def test_monitor_nowa_instancja_bez_restartu():
    d = Drzewo()
    try:
        d.dodaj("a")
        postacie = {}
        M.przebieg(postacie, d.k)
        assert set(postacie) == {"a"}, list(postacie)
        d.dodaj("nowa")                                     # nowa instancja w trakcie pracy monitora (uruchom_instancje.sh)
        d.procesy["nowa"] = ("mozg.py",)
        aktywne = M.przebieg(postacie, d.k)                 # kolejny przebieg tej samej pętli, bez restartu
        assert "nowa" in postacie and "nowa" in [p.id for p in aktywne], (list(postacie), [p.id for p in aktywne])
    finally:
        d.zamknij()


def test_monitor_sesja_gry_bez_bota_jest_na_liscie():
    d = Drzewo()
    try:
        d.dodaj("a")
        d.procesy["a"] = ("straznik.py",)                   # klient gry stoi, bota nie ma (ręczna gra, bot padł)
        postacie = {}
        aktywne = M.przebieg(postacie, d.k)
        assert [p.id for p in aktywne] == ["a"] and postacie["a"].sesja and not postacie["a"].bot
        assert " gra " in M.tabela(aktywne), M.tabela(aktywne)
        d.procesy["a"] = ()                                 # zero procesów: poza listą aktywnych
        assert M.przebieg(postacie, d.k) == []
    finally:
        d.zamknij()


def test_monitor_nowy_log_i_ogon_starego():
    d = Drzewo()
    try:
        d.dodaj("a")
        d.procesy["a"] = ("mozg.py",)
        t = time.time()
        stary = d.log("a", "mozg-stdout-1022-0900.log", ["Mózg: start"], t - 600)
        postacie = {}
        M.przebieg(postacie, d.k)
        assert postacie["a"].plik_logu == stary
        d.log("a", "mozg-stdout-1022-0900.log", ["D3 zawieszka 45 s"], t - 100)       # ogon starego logu tuż przed restartem bota
        nowy = d.log("a", "mozg-stdout-1022-1000.log", ["S4 kręci się"], t - 10)       # nowy start bota = nowy plik
        M.przebieg(postacie, d.k)
        assert postacie["a"].plik_logu == nowy, postacie["a"].plik_logu
        klucze = [z[1] for z in postacie["a"].zdarz]
        assert "zawieszka" in klucze and "kreci" in klucze, klucze   # nic nie zginęło przy zmianie pliku
    finally:
        d.zamknij()


def test_monitor_zniknieta_instancja_odpada():
    d = Drzewo()
    try:
        d.dodaj("a")
        d.dodaj("b")
        postacie = {}
        M.synchronizuj(postacie, d.k)
        assert set(postacie) == {"a", "b"}
        (d.k / "instancje" / "b" / "profil.json").unlink()   # zmiana id / archiwizacja
        dod, usu = M.synchronizuj(postacie, d.k)
        assert usu == ["b"] and set(postacie) == {"a"}, (dod, usu, list(postacie))
    finally:
        d.zamknij()


# ---------------------------------------------------------------- grafik
def test_grafik_poza_pula_podaje_powod():
    s = TN.Swiat(("a",))
    s.dodaj("gamma", {"postac": "G", "nadzor": False})
    s.dodaj("testowa", {"postac": "T"})
    (s.k / "instancje" / "bezprofilu" / "logi").mkdir(parents=True)
    poza = G.poza_pula(s.k, G.wczytaj_konfig(s.k))
    assert set(poza) == {"gamma", "testowa", "bezprofilu"}, poza
    assert "profil" in poza["bezprofilu"] and "test" in poza["testowa"], poza
    assert G.pula(s.k, G.wczytaj_konfig(s.k)) == ["a"]
    s.dodaj("nowa")                                           # nowa instancja z profil.json wchodzi do puli bez rejestracji
    assert G.pula(s.k, G.wczytaj_konfig(s.k)) == ["a", "nowa"]


# ---------------------------------------------------------------- nadzorca
def _swiat_z_grafikiem_dla_a():
    s = TN.Swiat(("a", "b"))
    s.grafik([TN.zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 14:30", wylog="2026-10-21 14:45")])   # b: brak zmiany
    s.tryb_log("b", "raty", "ostrozny")
    s.log("b", [(s.zegar.t - timedelta(minutes=50), "Mózg: tryb skrypt, postać B, trasa thais_szczury_opt (90 pkt, start 3), próg HP 30.0%, bez modelu.")])
    return s


def test_nadzor_bierze_zacieta_sesje_spoza_grafiku():
    """Instancja pojawiła się po wygenerowaniu grafiku doby: bot online, zacięty (telemetria stara). Stary kod: „nie ruszam”,
    do ręcznego `grafik.py nowy --od-teraz`. Nowy: nadzór od razu (restart), bez rejestracji."""
    s = _swiat_z_grafikiem_dla_a()
    s.online("b", bot=True)
    s.tele["b"] = {"wiek_probki_s": 400}
    n, at = TN.nz(s)
    n.tick()
    dla_b = [w[0] for w in at.wywolania if len(w) > 1 and w[1] == "b"]     # a ma zmianę w grafiku i startuje po swojemu
    assert dla_b == ["zatrzymaj_bota", "start_bota"], at.wywolania


def test_nadzor_reczna_gra_bez_bota_poza_grafikiem_nietykalna():
    s = _swiat_z_grafikiem_dla_a()
    s.online("b", bot=False)                                  # Karol gra ręcznie, brak bota i brak zmiany: zero akcji
    n, at = TN.nz(s)
    for _ in range(4):
        n.tick()
        s.zegar.dalej(minutes=5)
    assert [w for w in at.wywolania if len(w) > 1 and w[1] == "b"] == [], at.wywolania


def test_nadzor_ostrzega_o_sesji_poza_pula():
    s = TN.Swiat(("a",))
    s.dodaj("g", {"postac": "G", "nadzor": False})
    s.grafik([TN.zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 14:30", wylog="2026-10-21 14:45")])
    s.online("g", bot=True)
    n, at = TN.nz(s, zywo=False)
    rap = n.tick()
    ostrz = [r for r in rap if r.get("id") == "g" and r.get("akcja") == "ostrzezenie"]
    assert ostrz and "poza nadzorem" in ostrz[0]["powod"], rap
    assert at.wywolania == []
    assert "g" in n.podsumowanie()["poza_nadzorem"]


if __name__ == "__main__":
    ok = zle = 0
    for nazwa, f in list(globals().items()):
        if nazwa.startswith("test_") and callable(f):
            try:
                f()
                ok += 1
                print("ok  ", nazwa)
            except Exception as e:      # noqa: BLE001
                import traceback
                zle += 1
                print("BŁĄD", nazwa, repr(e)[:400])
                traceback.print_exc()
    print(f"{ok}/{ok + zle} testów zielonych")
    sys.exit(1 if zle else 0)
