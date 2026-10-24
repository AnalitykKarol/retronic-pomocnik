#!/usr/bin/env python3
"""plan_postaci.py + integracja z nadzor.py (23.10, Karol: „Wszystko powinien robić nadzorca, powinien mieć jakiś plan”).
Offline: katalogi tymczasowe, atrapy źródeł i wykonawcy z testy/test_nadzor.py (nic nie dotyka gry, botów, sesji ani timera).
Dowodzi: parsowanie warunków i akcji; krok wykonuje się RAZ i tylko poza walką, z bramkami wroc-poziom (STOP_RECZNY, pauza, hold,
nadzor:false, WROC/wyprawa w toku, cisza); w cieniu tylko dziennik (plik planu bez zmian); na żywo przy NADZOR_NAPRAWY; zrobione_t zapis
atomowy; zaplanowana mapa/tryb idzie na następny start (refill przez uruchom.sh, start/relog/restart nadzorcy) i NIE trafia do env z
wyprzedzeniem; reguła zajętego spotu (inny nasz bot na tej jaskini -> inny wolny spot w tych samych widełkach, brak -> bez wykonania,
dziennik + powiadomienie); blanki dla runów (brak/nieznane -> nie startuje na ślepo: WROC + refill); spot przypięty (dawajkesh);
plan w `stan`; zmiana planu nie jest na białej liście.
Uruchomienie: python3 -I testy/test_plan_postaci.py"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["RETRONIC_TESTY"] = "1"
KORZEN = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
sys.path.insert(0, str(KORZEN / "testy"))
import nadzor as N  # noqa: E402
import test_nadzor as TN  # noqa: E402
import plan_postaci as P  # noqa: E402

MIASTA = {"edron": {"x": [32900, 33400], "y": [31500, 32100]}, "thais": {"x": [32200, 32700], "y": [32000, 32450]},
          "rook": {"x": [31900, 32160], "y": [32050, 32300]}}
SPOTY = {
    "trolle_edron": {"miasto": "edron", "jaskinia": "edron_trolle_z8", "poziom": [8, 30], "poziom_zrodlo": "karol", "waga": 0.5, "auto": True},
    "trolle_edron_patrol": {"miasto": "edron", "jaskinia": "edron_trolle_z8", "poziom": [8, 30], "poziom_zrodlo": "karol", "waga": 0.5, "auto": True},
    "trolle_edron_z9z": {"miasto": "edron", "jaskinia": "edron_trolle_z9z", "poziom": [8, 30], "poziom_zrodlo": "karol", "waga": 1.0, "auto": True},
    "trolle_edron_z9w": {"miasto": "edron", "jaskinia": "edron_trolle_z9w", "poziom": [8, 30], "poziom_zrodlo": "karol", "waga": 1.0, "auto": True},
    "gobliny_edron": {"miasto": "edron", "jaskinia": "edron_gobliny_z8", "poziom": [6, 20], "poziom_zrodlo": "domyslne", "waga": 1.0, "auto": False},
    "thais_pn_z8": {"miasto": "thais", "jaskinia": "thais_pn", "poziom": [8, 30], "poziom_zrodlo": "domyslne", "waga": 1.0, "auto": True},
    "thais_pn_z9": {"miasto": "thais", "jaskinia": "thais_pn", "poziom": [8, 30], "poziom_zrodlo": "domyslne", "waga": 1.0, "auto": False},
    "rook_kanaly_z11": {"miasto": "rook", "jaskinia": "rook_kanaly_z11", "poziom": [1, 7], "poziom_zrodlo": "karol", "waga": 1.0, "auto": True},
}
T = TN.T0


class SwiatP(TN.Swiat):
    """Świat testu z tabelą spotów, planem i odczytem blanków (źródło `blanki`)."""

    def __init__(self, ids=("a",), plan=None, spoty=SPOTY):
        super().__init__(ids)
        (self.k / "mapy.json").write_text(json.dumps({"_opis": "x", **{m: {"trasa": "x", "potwory": "Troll"} for m in spoty}}))
        (self.k / "dane_tibia").mkdir(exist_ok=True)
        (self.k / "dane_tibia" / "spoty_nadzorca.json").write_text(json.dumps({"miasta": MIASTA, "spoty": spoty}))
        self.bl = {}                                     # id -> liczba blanków albo None (brak odczytu)
        if plan is not None:
            self.plan(plan)

    def plan(self, plan):
        (self.k / "instancje" / "_wspolne" / "plan_postaci.json").write_text(json.dumps({"postacie": plan}, ensure_ascii=False, indent=1))

    def plan_odczyt(self):
        return json.loads((self.k / "instancje" / "_wspolne" / "plan_postaci.json").read_text())["postacie"]

    def plan_bajty(self):
        return (self.k / "instancje" / "_wspolne" / "plan_postaci.json").read_bytes()

    def blanki(self, id_):
        return self.bl.get(id_)

    def gra(self, id_, mapa, tryb, level, bot=True, walka=False):
        self.tryb_log(id_, mapa, tryb)
        self.online(id_, bot=bot, level=level)
        self.log(id_, [(self.zegar.t - timedelta(seconds=5 if walka else 40), "Cel Troll: atak" if walka else "Cel Troll zabity na (1, 2, 8).")])


def krok(warunek, akcja, id_="k1", **kw):
    return {"id": id_, "warunek": warunek, "akcja": akcja, "powod": "test", "zrobione_t": None, **kw}


def nadzorca(s, tryb="naprawy"):
    """naprawy = tick timera z NADZOR_NAPRAWY (plan i wroc-poziom na żywo, reszta w cieniu); zywo = NADZOR_ZYWO; cien = nic na żywo."""
    at = TN.Atrapa(s)
    if tryb == "zywo":
        return N.Nadzorca(s.k, s.zegar, s, at, True, True), at
    if tryb == "cien":
        return N.Nadzorca(s.k, s.zegar, s, N.WykonawcaCien(), False, True), at
    return N.Nadzorca(s.k, s.zegar, s, N.WykonawcaCien(), False, True, naprawy_poziom=True, wykonawca_poziom=at), at


def aktywna_zmiana(s, id_="a"):
    s.grafik([TN.zmiana(id_, od="2026-10-21 10:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45")])


def zywy_start(s):
    """Plik NADZOR_NAPRAWY jak na produkcji (potrzebny CLI haka uruchom.sh)."""
    (s.k / "instancje" / "_wspolne" / "NADZOR_NAPRAWY").touch()


# ============================================================ parsowanie i plik planu
def test_parsuj_warunek_i_akcje():
    assert P.parsuj_warunek("poziom >= 9") == {"typ": "poziom", "n": 9}
    assert P.parsuj_warunek("poziom>=12") == {"typ": "poziom", "n": 12}
    assert P.parsuj_warunek("po_refillu") == {"typ": "po_refillu"}
    assert P.parsuj_warunek("przy_nastepnym_starcie") == {"typ": "przy_nastepnym_starcie"}
    assert P.parsuj_akcje("wroc") == {"typ": "wroc"}
    assert P.parsuj_akcje("tryb ostrozny,runy") == {"typ": "tryb", "tryb": "ostrozny,runy"}
    assert P.parsuj_akcje("mapa trolle_edron ostrozny,runy,uh") == {"typ": "mapa", "mapa": "trolle_edron", "tryb": "ostrozny,runy,uh"}
    assert P.parsuj_akcje("mapa trolle_edron") == {"typ": "mapa", "mapa": "trolle_edron", "tryb": None}
    for zle in ("poziom > 9", "poziom >= x", "kiedys", "", None):
        try:
            P.parsuj_warunek(zle)
            raise AssertionError(f"przeszło: {zle!r}")
        except ValueError:
            pass
    for zle in ("tryb", "mapa", "skocz", "wroc teraz", ""):
        try:
            P.parsuj_akcje(zle)
            raise AssertionError(f"przeszło: {zle!r}")
        except ValueError:
            pass


def test_wczytaj_zly_krok_nie_psuje_reszty_a_brak_pliku_to_pusty_plan():
    s = SwiatP(("a",))
    assert P.wczytaj(s.k).postacie == {} and P.wczytaj(s.k).bledy == []
    s.plan({"a": {"kroki": [krok("poziom >= 9", "wroc", "ok"), krok("kiedys", "wroc", "zly"), krok("po_refillu", "wroc", "nieoczywisty"),
                            krok("poziom >= 9", "wroc", "ok")]}})
    p = P.wczytaj(s.k)
    assert [k.id for k in p.postacie["a"].kroki] == ["ok"], p.postacie
    assert len(p.bledy) == 3, p.bledy              # zły warunek, wroc przy po_refillu, zdublowane id
    (s.k / "instancje" / "_wspolne" / "plan_postaci.json").write_text("{nie json")
    p = P.wczytaj(s.k)
    assert p.postacie == {} and p.bledy and "nieczytelny" in p.bledy[0], p.bledy


def test_plan_startowy_z_repo_zgodny_z_decyzjami_karola():
    p = P.wczytaj(KORZEN)
    assert p.bledy == [], p.bledy
    kr = lambda i: {k.id: k for k in p.postacie[i].kroki}          # noqa: E731
    od = p.postacie["odchyd"].kroki
    assert [k.id for k in od] == ["lvl8-wroc", "lvl10-wroc"], od          # 23.10 17:05 (Karol): + odchyd dobija 10 lvl na trolle_edron i wraca do depo
    assert od[0].warunek == {"typ": "poziom", "n": 8} and od[0].akcja == {"typ": "wroc"}
    assert od[1].warunek == {"typ": "poziom", "n": 10} and od[1].akcja == {"typ": "wroc"}
    ge = p.postacie["gebelish"].kroki
    assert len(ge) == 1 and ge[0].warunek == {"typ": "poziom", "n": 10} and ge[0].akcja == {"typ": "tryb", "tryb": "ostrozny,runy"}      # 23.10 Karol: runy HMM od lvl 10 (nie 9)
    inv = p.postacie["invincible"].kroki
    assert len(inv) == 1 and inv[0].warunek == {"typ": "po_refillu"} and inv[0].akcja == {"typ": "mapa", "mapa": "trolle_edron", "tryb": "ostrozny,runy,uh"}
    assert not p.postacie["dawajkesh"].kroki and p.postacie["dawajkesh"].spot_przypiety, "dawajkesh zostaje na swoim spocie (Karol 23.10)"
    # zrobione_t nie jest asercją: to żywy stan planu (nadzorca zapisuje go w trakcie dnia), a kształt kroków to decyzja Karola


def test_oznacz_zrobione_atomowo_raz_i_bez_uszkodzenia_pliku():
    s = SwiatP(("a",), {"a": {"kroki": [krok("poziom >= 9", "wroc", "k1"), krok("poziom >= 12", "wroc", "k2")]}})
    assert P.oznacz_zrobione(s.k, "a", "k1", T, "ok") is True
    assert P.oznacz_zrobione(s.k, "a", "k1", T + timedelta(hours=1), "drugi") is False        # raz
    d = s.plan_odczyt()["a"]["kroki"]
    assert d[0]["zrobione_t"] == T.strftime("%Y-%m-%d %H:%M:%S") and d[1]["zrobione_t"] is None, d
    assert not list((s.k / "instancje" / "_wspolne").glob("plan_postaci.json.*")) or all(not p.name.endswith(".tmp") for p in (s.k / "instancje" / "_wspolne").glob("*"))
    assert P.oznacz_zrobione(s.k, "a", "brak", T, "ok") is False and P.oznacz_zrobione(s.k, "zly", "k1", T, "ok") is False


# ============================================================ konsumowanie przy starcie (refill / nadzor)
def kons(s, id_, rodzaj, zajete=None, poziom=12, **kw):
    log, pow_ = [], []
    r = P.konsumuj_start(s.k, id_, rodzaj, T, zajete=zajete if zajete is not None else set(), poziom=poziom,
                         log=lambda a, w, p, **e: log.append((a, w, p)), powiadom=lambda i, t, tr: pow_.append((i, t, tr)), **kw)
    return r, log, pow_


def test_refill_po_refillu_mapa_zwraca_mape_i_tryb_oznacza_i_powiadamia_raz():
    s = SwiatP(("a",), {"a": {"kroki": [krok("po_refillu", "mapa trolle_edron ostrozny,runy,uh")]}})
    r, log, pow_ = kons(s, "a", "refill", bramki=False)
    assert r and r["mapa"] == "trolle_edron" and r["tryb"] == "ostrozny,runy,uh" and r["kroki"] == ["k1"], r
    assert len(pow_) == 1 and "trolle_edron" in pow_[0][2] and len(pow_[0][1]) <= 80, pow_
    assert s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"], "zrobione_t zapisane"
    r2, _, pow2 = kons(s, "a", "refill", bramki=False)
    assert r2 is None and pow2 == [], "krok raz"
    assert not (s.k / "ostatni_start.a.env").exists(), "env zapisuje dopiero uruchom.sh, nie plan"


def test_nadzor_start_nie_zjada_po_refillu_ale_zjada_przy_nastepnym_starcie_i_uzbrojone():
    s = SwiatP(("a",), {"a": {"kroki": [krok("po_refillu", "mapa trolle_edron ostrozny", "r"),
                                        krok("przy_nastepnym_starcie", "tryb ostrozny,uh", "n")]}})
    r, _, _ = kons(s, "a", "nadzor", bramki=False, biezaca=("trolle_edron_z9z", "ostrozny,runy"))
    assert r and r["kroki"] == ["n"] and r["mapa"] == "trolle_edron_z9z" and r["tryb"] == "ostrozny,uh", r
    d = {k["id"]: k["zrobione_t"] for k in s.plan_odczyt()["a"]["kroki"]}
    assert d["n"] and d["r"] is None, d
    r2, _, _ = kons(s, "a", "refill", bramki=False, biezaca=("x", "y"))
    assert r2 and r2["mapa"] == "trolle_edron" and r2["kroki"] == ["r"], r2


def test_tryb_bez_biezacej_mapy_nie_zgaduje():
    s = SwiatP(("a",), {"a": {"kroki": [krok("przy_nastepnym_starcie", "tryb ostrozny,uh")]}})
    r, log, _ = kons(s, "a", "nadzor", bramki=False, biezaca=(None, None))
    assert r is None and s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None and log, log


def test_bramki_hooka_nic_nie_zjadaja():
    s = SwiatP(("a",), {"a": {"kroki": [krok("po_refillu", "mapa trolle_edron ostrozny")]}})
    zywy_start(s)
    assert P.bramki(s.k, "a", T) is None, P.bramki(s.k, "a", T)
    s.plik("a", "STOP_RECZNY").touch()
    assert "STOP_RECZNY" in P.bramki(s.k, "a", T)
    r, _, _ = kons(s, "a", "refill")
    assert r is None and s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None
    s.plik("a", "STOP_RECZNY").unlink()
    (s.k / "instancje" / "_wspolne" / "NADZOR_PAUZA").touch()
    assert "NADZOR_PAUZA" in P.bramki(s.k, "a", T)
    (s.k / "instancje" / "_wspolne" / "NADZOR_PAUZA").unlink()
    (s.k / "instancje" / "a" / "profil.json").write_text(json.dumps({"postac": "A", "nadzor": False}))
    assert "nadzor" in P.bramki(s.k, "a", T)
    (s.k / "instancje" / "a" / "profil.json").write_text(json.dumps({"postac": "A"}))
    (s.k / "instancje" / "_wspolne" / "nadzor_stan.json").write_text(json.dumps({"postacie": {"a": {"hold": {"powod": "PK"}}}}))
    assert "wstrzymana" in P.bramki(s.k, "a", T)
    (s.k / "instancje" / "_wspolne" / "nadzor_stan.json").write_text("{}")
    (s.k / "cisza").touch()
    assert "cisza" in P.bramki(s.k, "a", T)
    (s.k / "cisza").unlink()
    (s.k / "instancje" / "_wspolne" / "NADZOR_NAPRAWY").unlink()
    assert "cieniu" in P.bramki(s.k, "a", T), "bez NADZOR_NAPRAWY/NADZOR_ZYWO plan działa tylko w cieniu"
    (s.k / "instancje" / "_wspolne" / "NADZOR_ZYWO").touch()
    assert P.bramki(s.k, "a", T) is None


# ============================================================ zajęty spot
def test_wolny_spot_idzie_na_cel_a_dawajkesh_na_z9z_nie_przeszkadza():
    s = SwiatP(("a",), {"a": {"kroki": [krok("po_refillu", "mapa trolle_edron ostrozny,runy,uh")]}})
    zaj = {"trolle_edron_z9z"}                            # dawajkesh (z9, osobna jaskinia)
    r, _, _ = kons(s, "a", "refill", zajete=zaj, bramki=False)
    assert r and r["mapa"] == "trolle_edron", r


def test_zajety_cel_inny_wolny_spot_w_tych_samych_widelkach_i_miescie():
    s = SwiatP(("a",), {"a": {"kroki": [krok("po_refillu", "mapa trolle_edron ostrozny,runy,uh")]}})
    zaj = {"trolle_edron_patrol"}                         # ta sama jaskinia co cel (edron_trolle_z8) zajęta
    r, log, pow_ = kons(s, "a", "refill", zajete=zaj, bramki=False)
    assert r and r["mapa"] in ("trolle_edron_z9z", "trolle_edron_z9w") and r["mapa"] != "trolle_edron", r
    assert r["tryb"] == "ostrozny,runy,uh"
    assert any("zajęt" in p for _, _, p in log) and pow_, (log, pow_)
    # kolejne: gdy zajęta też z9z, zostaje z9w; gobliny (auto false) i inne miasta/widełki nigdy
    s2 = SwiatP(("a",), {"a": {"kroki": [krok("po_refillu", "mapa trolle_edron ostrozny")]}})
    r2, _, _ = kons(s2, "a", "refill", zajete={"trolle_edron", "trolle_edron_z9z"}, bramki=False)
    assert r2 and r2["mapa"] == "trolle_edron_z9w", r2


def test_zajety_cel_brak_alternatywy_nie_wykonuje_dziennik_i_powiadomienie_raz():
    s = SwiatP(("a",), {"a": {"kroki": [krok("po_refillu", "mapa trolle_edron ostrozny")]}})
    zaj = {"trolle_edron", "trolle_edron_z9z", "trolle_edron_z9w"}
    r, log, pow_ = kons(s, "a", "refill", zajete=zaj, bramki=False)
    assert r is None and s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None, "krok czeka na następny start"
    assert log and "brak wolnego spotu" in log[-1][2] and len(pow_) == 1, (log, pow_)
    r, log, pow_ = kons(s, "a", "refill", zajete=zaj, bramki=False)      # ponowna próba tego samego dnia: dziennik tak, powiadomienie nie spamuje
    assert r is None and len(pow_) == 0 and log, (log, pow_)
    # zwolniło się: wykonuje
    r, _, _ = kons(s, "a", "refill", zajete=set(), bramki=False)
    assert r and r["mapa"] == "trolle_edron"


def test_poziom_poza_widelkami_celu_nie_wykonuje():
    s = SwiatP(("a",), {"a": {"kroki": [krok("po_refillu", "mapa rook_kanaly_z11 ostrozny")]}})
    r, log, _ = kons(s, "a", "refill", poziom=9, bramki=False)
    assert r is None and log and "poziom" in log[-1][2], log


def test_zajete_mapy_z_trybu_log_i_procesow_innych_botow():
    s = SwiatP(("a", "b", "c"))
    s.tryb_log("b", "trolle_edron", "ostrozny")
    s.tryb_log("c", "trolle_edron_z9z", "ostrozny")
    zaj = P.zajete_mapy(s.k, "a", procesy_bota=lambda i: [1] if i == "b" else [])
    assert zaj == {"trolle_edron"}, zaj               # c nie ma procesu bota: jego tryb.log to historia, nie zajętość
    assert P.zajete_mapy(s.k, "b", procesy_bota=lambda i: [1] if i == "b" else []) == set()


# ============================================================ CLI haka uruchom.sh
def test_cli_start_wypisuje_zmienne_tylko_przy_refillu_i_nic_gdy_brak_planu():
    s = SwiatP(("a",), {"a": {"kroki": [krok("po_refillu", "mapa trolle_edron ostrozny,runy,uh")]}})
    zywy_start(s)
    out = []
    os.environ["RETRONIC_NADZOR_KORZEN"] = str(s.k)
    try:
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            kod = P.main(["start", "a", "--refill", "--bez-procesow"])
        assert kod == 0
        wyj = buf.getvalue()
        import subprocess
        ev = subprocess.run(["bash", "-c", 'eval "$1"; echo "$MAPA|$TRYB"', "x", wyj], capture_output=True, text=True).stdout.strip()
        assert ev == "trolle_edron|ostrozny,runy,uh", (ev, wyj)
        assert "export" not in wyj and "$(" not in wyj and "`" not in wyj
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            P.main(["start", "a", "--refill", "--bez-procesow"])
        assert buf.getvalue() == "", "krok raz"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert P.main(["start", "nieistniejaca", "--refill", "--bez-procesow"]) == 0
        assert buf.getvalue() == ""
    finally:
        os.environ.pop("RETRONIC_NADZOR_KORZEN", None)
    assert not (s.k / "ostatni_start.a.env").exists()


def test_uruchom_sh_ma_hak_planu_przed_odczytem_env_i_jest_fail_safe():
    t = (KORZEN / "uruchom.sh").read_text(encoding="utf-8")
    assert "plan_postaci.py" in t, "uruchom.sh musi pytać plan przy starcie bez MAPA/TRYB"
    assert t.index("plan_postaci.py") < t.index('. "$OSTATNI"'), "plan przed odczytem env"
    linia = [l for l in t.splitlines() if "plan_postaci.py" in l][0]
    assert "2>/dev/null" in linia and "--refill" in t, linia
    assert 'STARTUJ' in t, "tylko start z refillu (STARTUJ=1) bierze po_refillu"


# ============================================================ tick: kroki natychmiastowe
def test_odchyd_poziom8_wroc_raz_na_zywo_powiadomienie_i_zrobione_t():
    s = SwiatP(("a",), {"a": {"kroki": [krok("poziom >= 8", "wroc")]}})
    aktywna_zmiana(s)
    s.gra("a", "rook_kanaly_z11", "ostrozny", 8)
    n, at = nadzorca(s)
    n.tick()
    assert at.nazwy().count("wroc") == 1 and at.nazwy().count("powiadom_info") == 1, at.wywolania
    assert s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"], s.plan_odczyt()
    assert "naprawy" not in n.post("a")
    for _ in range(3):
        s.zegar.dalej(minutes=5)
        s.plik("a", "WROC").unlink(missing_ok=True)
        s.log("a", [(s.zegar.t - timedelta(seconds=40), "Cel Troll zabity na (1, 2, 8).")])
        n.tick()
    assert at.nazwy().count("wroc") == 1 and at.nazwy().count("powiadom_info") == 1, "krok raz, jedno powiadomienie: " + str(at.wywolania)


def test_plan_podwojne_zlecenie_z_wroc_poziom_nie_wystepuje():
    """Rook max 7, plan `poziom >= 8 -> wroc`: jedno WROC, nie dwa (plan i wroc-poziom nie dublują)."""
    s = SwiatP(("a",), {"a": {"kroki": [krok("poziom >= 8", "wroc")]}})
    aktywna_zmiana(s)
    s.gra("a", "rook_kanaly_z11", "ostrozny", 8)
    n, at = nadzorca(s)
    n.tick()
    s.plik("a", "WROC").unlink(missing_ok=True)
    s.zegar.dalej(minutes=5)
    s.log("a", [(s.zegar.t - timedelta(seconds=40), "Cel Troll zabity na (1, 2, 8).")])
    n.tick()
    assert at.nazwy().count("wroc") == 1 and at.nazwy().count("powiadom_info") == 1, at.wywolania


def test_plan_poziom_nizszy_nic_nie_robi():
    s = SwiatP(("a",), {"a": {"kroki": [krok("poziom >= 9", "wroc")]}})
    aktywna_zmiana(s)
    s.gra("a", "thais_pn_z8", "ostrozny,ml", 8)
    n, at = nadzorca(s)
    n.tick()
    assert at.wywolania == [] and s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None


def test_plan_bez_biezacego_odczytu_poziomu_nie_zgaduje():
    s = SwiatP(("a",), {"a": {"kroki": [krok("poziom >= 9", "wroc")]}})
    aktywna_zmiana(s)
    s.gra("a", "thais_pn_z8", "ostrozny,ml", 12)
    s.inst["a"]["gracz"].pop("level")
    n, at = nadzorca(s)
    n.post("a")["poziom"] = {"wartosc": 12, "t": (T - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")}       # zapamiętany nie wystarczy
    n.tick()
    assert at.wywolania == [], at.wywolania


def test_plan_w_cieniu_tylko_dziennik_plik_planu_bez_zmian():
    s = SwiatP(("a",), {"a": {"kroki": [krok("poziom >= 8", "wroc")]}})
    aktywna_zmiana(s)
    s.gra("a", "rook_kanaly_z11", "ostrozny", 8)
    przed = s.plan_bajty()
    n, at = nadzorca(s, "cien")
    n.tick()
    assert s.plan_bajty() == przed and at.wywolania == [], at.wywolania
    assert any("plan" in x.get("powod", "").lower() or "zrobiłbym" in str(x.get("szczegol", "")) for x in n.dziennik.ostatnie
               if x.get("akcja") == "wroc"), n.dziennik.ostatnie
    assert N.WykonawcaCien().zywy is False


def test_plan_naprawy_przy_wyciszonych_powiadomieniach_zostaje_w_cieniu():
    s = SwiatP(("a",), {"a": {"kroki": [krok("poziom >= 8", "wroc")]}})
    aktywna_zmiana(s)
    s.gra("a", "rook_kanaly_z11", "ostrozny", 8)
    (s.k / "cisza").touch()
    n, at = nadzorca(s)
    n.tick()
    assert at.nazwy().count("wroc") == 0 and s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None, at.wywolania


def test_plan_bramki_stop_reczny_pauza_nadzor_false_hold_wroc_wyprawa():
    def swiat():
        s = SwiatP(("a",), {"a": {"kroki": [krok("poziom >= 8", "wroc")]}})
        aktywna_zmiana(s)
        s.gra("a", "rook_kanaly_z11", "ostrozny", 8)
        return s
    s = swiat()
    s.plik("a", "STOP_RECZNY").touch()
    n, at = nadzorca(s)
    n.tick()
    assert "wroc" not in at.nazwy()
    s = swiat()
    (s.k / "instancje" / "_wspolne" / "NADZOR_PAUZA").touch()
    n, at = nadzorca(s)
    n.tick()
    assert at.wywolania == []
    s = swiat()
    s.plik("a", "profil.json").write_text(json.dumps({"postac": "A", "nadzor": False}))
    n, at = nadzorca(s)
    n.tick()
    assert at.wywolania == []
    s = swiat()
    n, at = nadzorca(s)
    n.post("a")["hold"] = {"powod": "PK", "od": "x", "powiadomiono": True}
    n.tick()
    assert at.wywolania == []
    s = swiat()
    s.plik("a", "WROC").touch()                                     # powrót już trwa
    n, at = nadzorca(s)
    n.tick()
    assert at.nazwy().count("wroc") == 0 and s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None
    s = swiat()
    s.plik("a", "wyprawa_stan.json").write_text(json.dumps({"aktywna": True}))
    n, at = nadzorca(s)
    n.tick()
    assert at.nazwy().count("wroc") == 0 and s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None
    for s in (swiat(), ):
        assert s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None


def test_plan_w_walce_czeka_potem_wykonuje():
    s = SwiatP(("a",), {"a": {"kroki": [krok("poziom >= 8", "wroc")]}})
    aktywna_zmiana(s)
    s.gra("a", "rook_kanaly_z11", "ostrozny", 8, walka=True)
    n, at = nadzorca(s)
    n.tick()
    assert "wroc" not in at.nazwy() and s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None
    s.zegar.dalej(minutes=5)
    s.log("a", [(s.zegar.t - timedelta(seconds=60), "Cel Troll zabity na (1, 2, 8).")])
    n.tick()
    assert at.nazwy().count("wroc") == 1, at.wywolania


# ============================================================ gebelish: tryb runy i blanki
def gebelish(blanki, tryb_na_zywo="naprawy", level=9):
    s = SwiatP(("a",), {"a": {"kroki": [krok("poziom >= 9", "tryb ostrozny,runy")]}})
    aktywna_zmiana(s)
    s.gra("a", "thais_pn_z8", "ostrozny,ml", level)
    s.bl["a"] = blanki
    n, at = nadzorca(s, tryb_na_zywo)
    return s, n, at


def test_gebelish_z_blankami_restart_na_tej_samej_mapie_z_nowym_trybem():
    s, n, at = gebelish(12)
    n.tick()
    assert at.nazwy() == ["zatrzymaj_bota", "start_bota", "powiadom_info"], at.wywolania
    assert [w for w in at.wywolania if w[0] == "start_bota"][0][2:] == ("thais_pn_z8", "ostrozny,runy"), at.wywolania
    assert s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"]
    s.zegar.dalej(minutes=5)
    n.tick()
    assert at.nazwy().count("start_bota") == 1, "raz"


def test_gebelish_bez_blankow_nie_startuje_na_slepo_wroc_i_uzbrojenie():
    for bl in (0, None):
        s, n, at = gebelish(bl)
        n.tick()
        assert "start_bota" not in at.nazwy() and "zatrzymaj_bota" not in at.nazwy(), at.wywolania
        assert at.nazwy().count("wroc") == 1, at.wywolania
        k = s.plan_odczyt()["a"]["kroki"][0]
        assert k["zrobione_t"] is None and k.get("uzbrojone_t") and k.get("uzbrojone_mapa") == "thais_pn_z8" and k.get("tylko_refill") is True, k
        assert any("blank" in x.get("powod", "") for x in n.dziennik.ostatnie), n.dziennik.ostatnie
        assert not (s.k / "ostatni_start.a.env").exists(), "env nietknięty z wyprzedzeniem"
        s.zegar.dalej(minutes=5)
        s.plik("a", "WROC").unlink(missing_ok=True)
        s.log("a", [(s.zegar.t - timedelta(seconds=40), "Cel Troll zabity na (1, 2, 8).")])
        n.tick()
        assert at.nazwy().count("wroc") == 1, "WROC raz, potem czekamy na refill: " + str(at.wywolania)
        # refill startuje bota: uzbrojony krok daje mapę i tryb
        r, _, _ = kons(s, "a", "refill", bramki=False, biezaca=("thais_pn_z8", "ostrozny,ml"))
        assert r and r["mapa"] == "thais_pn_z8" and r["tryb"] == "ostrozny,runy", r
        assert s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"]


def test_uzbrojony_z_powodu_blankow_nie_zjada_start_nadzorcy_bez_refillu():
    s, n, at = gebelish(0)
    n.tick()
    r, _, _ = kons(s, "a", "nadzor", bramki=False, biezaca=("thais_pn_z8", "ostrozny,ml"))
    assert r is None and s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None


def test_gebelish_lvl8_nic():
    s, n, at = gebelish(12, level=8)
    n.tick()
    assert at.wywolania == [], at.wywolania


def test_gebelish_tryb_w_walce_czeka():
    s = SwiatP(("a",), {"a": {"kroki": [krok("poziom >= 9", "tryb ostrozny,runy")]}})
    aktywna_zmiana(s)
    s.gra("a", "thais_pn_z8", "ostrozny,ml", 9, walka=True)
    s.bl["a"] = 12
    n, at = nadzorca(s)
    n.tick()
    assert at.wywolania == [] and s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None


# ============================================================ mapa po poziomie i start nadzorcy
def test_mapa_z_warunkiem_poziomu_uzbraja_wroc_i_idzie_na_nastepny_start():
    s = SwiatP(("a",), {"a": {"kroki": [krok("poziom >= 9", "mapa trolle_edron ostrozny,uh")]}})
    aktywna_zmiana(s)
    s.gra("a", "trolle_edron_z9w", "ostrozny,ml", 9)
    n, at = nadzorca(s)
    n.tick()
    k = s.plan_odczyt()["a"]["kroki"][0]
    assert at.nazwy().count("wroc") == 1 and k["zrobione_t"] is None and k.get("uzbrojone_t"), (at.wywolania, k)
    assert not (s.k / "ostatni_start.a.env").exists()


def test_mapa_z_warunkiem_poziomu_zajety_cel_bez_alternatywy_nie_wysyla_do_miasta():
    s = SwiatP(("a", "b", "c", "d"), {"a": {"kroki": [krok("poziom >= 9", "mapa trolle_edron ostrozny,uh")]}})
    aktywna_zmiana(s)
    s.gra("a", "gobliny_edron", "ostrozny", 9)
    for i, m in (("b", "trolle_edron"), ("c", "trolle_edron_z9z"), ("d", "trolle_edron_z9w")):
        s.gra(i, m, "ostrozny", 12)
    n, at = nadzorca(s)
    n.tick()
    assert "wroc" not in [x for x in at.nazwy() if True] or [w for w in at.wywolania if w[0] == "wroc" and w[1] == "a"] == [], at.wywolania
    assert [w for w in at.wywolania if w[1:2] == ("a",) and w[0] in ("wroc", "zatrzymaj_bota", "start_bota")] == []
    assert any("brak wolnego spotu" in x.get("powod", "") for x in n.dziennik.ostatnie), n.dziennik.ostatnie
    assert s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None


def start_nowej_sesji(s, id_="a", poz=TN.THAIS if hasattr(TN, "THAIS") else [32370, 32214, 7], level=12, zm_od="2026-10-21 09:00"):
    s.zegar.t = datetime(2026, 10, 21, 9, 30, 0)
    s.inst[id_].update(sesja=True, gra=True, bot=False, gracz={"hp": 100, "max_hp": 100, "level": level},
                       panel={"pozycja": list(poz), "level": level})


def test_start_nadzorcy_przy_nastepnym_starcie_mapa_potem_znow_tryb_log():
    s = SwiatP(("a",), {"a": {"kroki": [krok("przy_nastepnym_starcie", "mapa trolle_edron ostrozny,uh")]}})
    s.grafik([TN.zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 11:00", wylog="2026-10-21 11:15")])
    s.tryb_log("a", "gobliny_edron", "ostrozny,runy,uh", datetime(2026, 10, 21, 8, 0))
    n, at = nadzorca(s, "zywo")
    at.zapisuj_tryb = True
    start_nowej_sesji(s, poz=TN.EDRON)
    n.post("a").update(faza="DOJSCIE", sesja_nasza=True, login_ts=s.zegar.t.timestamp(), zmiana_od="2026-10-21 09:00")
    n.tick()
    st = [w for w in at.wywolania if w[0] == "start_bota"]
    assert len(st) == 1 and st[0][2:] == ("trolle_edron", "ostrozny,uh"), at.wywolania
    ost = [x for x in n.dziennik.ostatnie if x["akcja"] == "start_bota"][-1]
    assert "plan" in ost["powod"], ost
    assert s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"]
    # po wykonaniu tryb.log (zapisany przez start) jest znów źródłem prawdy
    assert N.mapa_tryb_biezace(s.k, "a", s.zegar.t)[:2] == ("trolle_edron", "ostrozny,uh")


def test_start_nadzorcy_po_refillu_nie_jest_zjadany_przez_login():
    s = SwiatP(("a",), {"a": {"kroki": [krok("po_refillu", "mapa trolle_edron ostrozny,uh")]}})
    s.grafik([TN.zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 11:00", wylog="2026-10-21 11:15")])
    s.tryb_log("a", "gobliny_edron", "ostrozny,runy,uh", datetime(2026, 10, 21, 8, 0))
    n, at = nadzorca(s, "zywo")
    start_nowej_sesji(s, poz=TN.EDRON)
    n.post("a").update(faza="DOJSCIE", sesja_nasza=True, login_ts=s.zegar.t.timestamp(), zmiana_od="2026-10-21 09:00")
    n.tick()
    st = [w for w in at.wywolania if w[0] == "start_bota"]
    assert not any("plan" in x.get("powod", "") for x in n.dziennik.ostatnie if x["akcja"] == "start_bota"), n.dziennik.ostatnie
    assert s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None


def test_start_nadzorcy_zajety_cel_inna_wolna_jaskinia():
    s = SwiatP(("a", "b"), {"a": {"kroki": [krok("przy_nastepnym_starcie", "mapa trolle_edron ostrozny,uh")]}})
    s.grafik([TN.zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 11:00", wylog="2026-10-21 11:15")])
    s.tryb_log("a", "gobliny_edron", "ostrozny,runy,uh", datetime(2026, 10, 21, 8, 0))
    s.gra("b", "trolle_edron", "ostrozny", 12)                  # inny nasz bot stoi na celu
    n, at = nadzorca(s, "zywo")
    start_nowej_sesji(s, poz=TN.EDRON)
    n.post("a").update(faza="DOJSCIE", sesja_nasza=True, login_ts=s.zegar.t.timestamp(), zmiana_od="2026-10-21 09:00")
    n.tick()
    st = [w for w in at.wywolania if w[0] == "start_bota" and w[1] == "a"]
    assert len(st) == 1 and st[0][2] in ("trolle_edron_z9z", "trolle_edron_z9w"), at.wywolania
    assert st[0][3] == "ostrozny,uh"


def test_restart_nadzorcy_uzywa_przy_nastepnym_starcie():
    s = SwiatP(("a",), {"a": {"kroki": [krok("przy_nastepnym_starcie", "tryb ostrozny,uh")]}})
    aktywna_zmiana(s)
    s.gra("a", "trolle_edron_z9z", "ostrozny,runy", 12)
    n, at = nadzorca(s, "zywo")
    kod, txt = n.napraw("a", "restart")
    st = [w for w in at.wywolania if w[0] == "start_bota"]
    assert st and st[0][2:] == ("trolle_edron_z9z", "ostrozny,uh"), (kod, txt, at.wywolania)


# ============================================================ spot przypięty
def test_spot_przypiety_start_zmiany_zostaje_na_biezacej_mapie_a_bez_pinu_rotuje():
    plan = {"a": {"spot_przypiety": True, "kroki": []}}
    for przypiety in (True, False):
        s = SwiatP(("a",), plan if przypiety else {"a": {"kroki": []}})
        s.grafik([TN.zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 11:00", wylog="2026-10-21 11:15")])
        s.tryb_log("a", "trolle_edron_z9z", "ostrozny,runy,uh", datetime(2026, 10, 21, 8, 0))
        n, at = nadzorca(s, "zywo")
        start_nowej_sesji(s, poz=TN.EDRON)
        n.post("a").update(faza="DOJSCIE", sesja_nasza=True, login_ts=s.zegar.t.timestamp(), zmiana_od="2026-10-21 09:00")
        n.tick()
        st = [w for w in at.wywolania if w[0] == "start_bota"]
        assert st, at.wywolania
        if przypiety:
            assert st[0][2:] == ("trolle_edron_z9z", "ostrozny,runy,uh"), at.wywolania
        else:
            assert st[0][2] != "trolle_edron_z9z", "bez pinu mieszanie wybiera inną jaskinię niż poprzednio: " + str(at.wywolania)


def test_spot_przypiety_zmien_spot_odmowa_i_drabina_bez_zmiany_spotu():
    s = SwiatP(("a",), {"a": {"spot_przypiety": True, "kroki": []}})
    aktywna_zmiana(s)
    s.gra("a", "trolle_edron_z9z", "ostrozny,runy,uh", 12)
    n, at = nadzorca(s, "zywo")
    kod, txt = n.napraw("a", "zmien_spot")
    assert kod != 0 and "przypięt" in txt and "start_bota" not in at.nazwy(), (kod, txt, at.wywolania)
    o = n.obserwuj("a", s.stan()[0], s.zegar.t)
    for _ in range(6):
        d = n.drabina("a", s.zegar.t, "zaciecie", o)
        assert d["akcja"] != "zmien_spot", d
        n.post("a").setdefault("naprawy", []).append([s.zegar.t.timestamp() - 600, d["akcja"]])


def test_spot_przypiety_podglad_w_cieniu_nie_proponuje_innej_jaskini():
    s = SwiatP(("a",), {"a": {"spot_przypiety": True, "kroki": []}})
    aktywna_zmiana(s)
    s.gra("a", "trolle_edron_z9z", "ostrozny,runy,uh", 12)
    s.inst["a"]["panel"].update(pozycja=list(TN.EDRON), level=12)
    n, at = nadzorca(s, "cien")
    n.tick()
    pod = [x for x in n.dziennik.ostatnie if x["akcja"] == "spot_podglad"]
    assert pod and "przypięt" in pod[0]["powod"] and "wybrałbym" not in pod[0]["powod"], pod


# ============================================================ obchód
def test_stan_pokazuje_plan_nastepny_krok_warunek_i_stan():
    s = SwiatP(("a", "b"), {"a": {"kroki": [krok("poziom >= 9", "tryb ostrozny,runy"), krok("po_refillu", "mapa trolle_edron ostrozny", "k2")]},
                            "b": {"spot_przypiety": True, "spot_przypiety_powod": "Karol 23.10", "kroki": []}})
    aktywna_zmiana(s)
    s.gra("a", "thais_pn_z8", "ostrozny,ml", 8)
    n, at = nadzorca(s, "cien")
    pod = n.podsumowanie()
    pl = pod["postacie"]["a"]["plan"]
    assert pl["nastepny"]["id"] == "k1" and "poziom >= 9" in pl["nastepny"]["warunek"] and "tryb ostrozny,runy" in pl["nastepny"]["akcja"], pl
    assert "8" in pl["nastepny"]["stan"] and len(pl["kroki"]) == 2, pl
    assert pod["postacie"]["b"]["plan"]["spot_przypiety"] is True and pod["postacie"]["b"]["plan"]["nastepny"] is None
    zr = pod["postacie"]["a"]["plan"]["kroki"]
    assert [k["id"] for k in zr] == ["k1", "k2"]


def test_zmiana_planu_nie_jest_na_bialej_liscie_i_nie_ma_komendy_zapisu():
    assert not any("plan" in b for b in N.BIALA_LISTA), N.BIALA_LISTA
    assert not any("plan" in b for b in N.NAPRAWY_BEZ_ZYWO), N.NAPRAWY_BEZ_ZYWO
    s = SwiatP(("a",), {"a": {"kroki": [krok("poziom >= 8", "wroc")]}})
    n, at = nadzorca(s, "zywo")
    kod, txt = n.napraw("a", "plan")
    assert kod == 2 and "spoza białej listy" in txt, (kod, txt)
    assert not [f for f in dir(N.Nadzorca) if f.startswith(("zmien_plan", "edytuj_plan", "dodaj_krok"))]


def test_blad_pliku_planu_nie_wywraca_przebiegu_nadzorcy():
    s = SwiatP(("a",))
    (s.k / "instancje" / "_wspolne" / "plan_postaci.json").write_text("{zepsute")
    aktywna_zmiana(s)
    s.gra("a", "thais_pn_z8", "ostrozny,ml", 12)
    n, at = nadzorca(s)
    n.tick()
    assert at.wywolania == [], at.wywolania
    assert any("plan" in x.get("powod", "").lower() for x in n.dziennik.ostatnie), n.dziennik.ostatnie


# ============================================================ zostań w depo (23.10, Karol: invincible, dawajkesh, wydra)
def _swiat_depo(flaga, zmiana_kw=None, plan_dod=None):
    """Postać w grze, bez bota, STOP, dowód depo (log „DEPO osiągnięte” i panel w_depo), zmiana z grafiku trwa."""
    pc = {"kroki": [], **({"zostan_w_depo": True, "zostan_w_depo_powod": "Karol 23.10"} if flaga else {}), **(plan_dod or {})}
    s = SwiatP(("a",), {"a": pc})
    s.grafik([TN.zmiana("a", **(zmiana_kw or {"od": "2026-10-21 11:00", "koniec": "2026-10-21 13:30", "wylog": "2026-10-21 13:45"}))])
    s.tryb_log("a", "trolle_edron_z9z", "ostrozny,runy,uh", datetime(2026, 10, 21, 10, 0))
    s.online("a", bot=False, w_depo=True, w_miescie="edron", wroc_refill="brak_planu", level=15)
    s.plik("a", "STOP").touch()
    t = s.zegar.t
    s.log("a", [(t - timedelta(minutes=40), "Mózg: tryb skrypt, postać A, trasa edron_trolle_petla (90 pkt, start 3), próg HP 30.0%, bez modelu."),
                (t - timedelta(minutes=30), "Wyprawa: DEPO osiągnięte"), (t - timedelta(minutes=29), "Zatrzymano (plik STOP).")])
    n, at = nadzorca(s, "zywo")
    n.stan["postacie"]["a"] = {"faza": "POWROT", "bot_widziany": t.timestamp() - 2400, "bot_start": t.timestamp() - 2400, "zmiana_od": "2026-10-21 11:00",
                               "login_ts": t.timestamp() - 7200, "sesja_nasza": True, "powrot_od": t.timestamp() - 1800}
    return s, n, at


def _kody(n):
    return [x for x in n.dziennik.ostatnie if x["id"] == "a"]


def test_zostan_w_depo_stoi_ze_stop_dlugo_czekaj_bez_wznow_serwis_wylogowania():
    s, n, at = _swiat_depo(True)
    for _ in range(14):                         # 70 min: dużo więcej niż 10 min „depo-poza” i niż koniec zmiany
        n.tick()
        s.zegar.dalej(minutes=5)
    assert at.wywolania == [], at.wywolania      # zero akcji: ani start_bota (wznow), serwis, wyloguj, relog, powiadom
    kody = _kody(n)
    assert kody and all(x["akcja"] == "czekaj" for x in kody), kody
    assert "zostan_w_depo" in kody[0]["powod"] and "Karol 23.10" in kody[0]["powod"], kody[0]
    assert len(kody) <= 3, ("powtarzane wpisy dziennika", len(kody))      # dedup czekaj: nie co przebieg
    assert n.post("a").get("zostan_depo_od") and n.post("a")["faza"] == "MIASTO"
    assert not [x for x in n.dziennik.ostatnie if x["akcja"] in ("eskaluj", "zablokowane")]


def test_zostan_w_depo_po_koncu_zmiany_nie_wyloguje():
    s, n, at = _swiat_depo(True, {"od": "2026-10-21 09:00", "koniec": "2026-10-21 11:00", "wylog": "2026-10-21 11:15"})
    n.tick()
    s.zegar.dalej(minutes=30)
    n.tick()
    assert at.wywolania == [], at.wywolania


def test_bez_flagi_w_depo_ze_stop_dziala_jak_dotad_wznow_po_10_min_i_wylogowanie_po_koncu_zmiany():
    s, n, at = _swiat_depo(False)
    n.stan["postacie"]["a"]["faza"] = "EXP"
    n.tick()
    assert at.wywolania == [] and _kody(n)[0]["akcja"] == "czekaj", at.wywolania       # depo-poza: 10 min zwłoki
    s.zegar.dalej(minutes=11)
    n.tick()
    assert at.nazwy() == ["start_bota"], at.wywolania                                    # drabina „alarm” -> wznow
    s2, n2, at2 = _swiat_depo(False, {"od": "2026-10-21 09:00", "koniec": "2026-10-21 11:00", "wylog": "2026-10-21 11:15"})
    n2.tick()
    assert at2.nazwy() == ["wyloguj"], at2.wywolania                                     # koniec zmiany w depo -> wylogowanie


def test_zostan_w_depo_tylko_z_dowodem_depo_stop_w_polowie_drogi_naprawia_jak_dotad():
    s, n, at = _swiat_depo(True)
    s.inst["a"]["panel"] = {}                                    # brak dowodu depo w panelu
    for p in (s.plik("a", "logi")).glob("mozg-stdout-*.log"):
        p.write_text(f"{(s.zegar.t - timedelta(minutes=3)):%H:%M:%S} ALARM: wyprawa: utkniecie: brak postępu na etapie 2\n"
                     f"{(s.zegar.t - timedelta(minutes=2)):%H:%M:%S} Zatrzymano (plik STOP).\n")
    n.tick()
    assert at.nazwy() == ["start_bota"], at.wywolania           # poza depo: wznowienie jak dotąd


def test_zostan_w_depo_na_spocie_naprawy_jak_dotad():
    wyniki = []
    for flaga in (False, True):
        s = SwiatP(("a",), {"a": {"kroki": [], **({"zostan_w_depo": True} if flaga else {})}})
        s.grafik([TN.zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45")])
        s.tryb_log("a", "trolle_edron_z9z", "ostrozny,runy,uh", s.zegar.t - timedelta(hours=1))
        s.log("a", [(s.zegar.t - timedelta(minutes=50), "Mózg: tryb skrypt, postać A, trasa edron_trolle_petla (90 pkt, start 3), próg HP 30.0%, bez modelu.")])
        s.online("a", bot=True, level=15)
        s.tele["a"] = {"wiek_probki_s": 400, "stoi_poza_walka_s": 0}      # telemetria stara: bot zawieszony
        n, at = nadzorca(s, "zywo")
        n.stan["postacie"]["a"] = {"faza": "EXP", "bot_widziany": s.zegar.t.timestamp() - 600, "bot_start": s.zegar.t.timestamp() - 3000,
                                   "zmiana_od": "2026-10-21 09:00", "login_ts": s.zegar.t.timestamp() - 7200}
        n.tick()
        wyniki.append(at.nazwy())
    assert wyniki[0] == wyniki[1] and "zatrzymaj_bota" in wyniki[0] and "start_bota" in wyniki[0], wyniki


def test_zostan_w_depo_offline_po_depo_nie_loguje_a_bez_widzianego_depo_loguje_jak_dotad():
    s, n, at = _swiat_depo(True)
    n.tick()                                                     # nadzorca widzi: w depo ze STOP (znacznik)
    s.offline("a")                                               # reset serwera / wylogowanie z zewnątrz; STOP zostaje
    s.zegar.dalej(minutes=35)                                    # po 30 min przerwie: wstrzymuje flaga, nie przerwa
    for _ in range(3):
        n.tick()
        s.zegar.dalej(minutes=5)
    assert at.wywolania == [] and _kody(n)[-1]["powod"].startswith("offline, ostatnio w depo ze STOP"), (at.wywolania, _kody(n)[-1])
    # kontrola 1: bez flagi ta sama sytuacja = start sesji z grafiku
    s2, n2, at2 = _swiat_depo(False)
    s2.offline("a")
    n2.tick()                                                   # pierwszy przebieg offline zapisuje „ostatnie wylogowanie”
    s2.zegar.dalej(minutes=35)                                  # po 30 min przerwie od wylogowania
    n2.tick()
    assert "sesja_start" in at2.nazwy(), at2.wywolania
    # kontrola 2: z flagą, ale nadzorca nigdy nie widział jej w depo (znacznik pusty) = start sesji jak dotąd
    s3, n3, at3 = _swiat_depo(True)
    s3.offline("a")
    n3.tick()                                                   # pierwszy przebieg offline zapisuje „ostatnie wylogowanie”
    s3.zegar.dalej(minutes=35)                                  # po 30 min przerwie od wylogowania
    n3.tick()
    assert "sesja_start" in at3.nazwy(), at3.wywolania


def test_zostan_w_depo_rozlaczona_po_resecie_nie_jest_relogowana():
    for flaga in (True, False):
        s, n, at = _swiat_depo(flaga)
        n.tick()
        s.inst["a"].update(gracz=None, panel={})
        s.ekran_map["a"] = "logowanie"
        s.log("a", [(s.zegar.t - timedelta(minutes=1), "ROZŁĄCZENIE: pamięć gry: brak postaci")])
        s.zegar.dalej(minutes=12)
        n.tick()
        if flaga:
            assert at.wywolania == [] and _kody(n)[-1]["powod"].startswith("klient poza grą, ostatnio w depo"), (at.wywolania, _kody(n)[-1])
        else:
            assert at.wywolania, "bez flagi relog jak dotąd"


def test_zostan_w_depo_napraw_odmowa_dla_wznow_restart_relog_wyloguj_zmien_spot():
    s, n, at = _swiat_depo(True)
    for rodzaj in ("wznow", "restart", "relog", "wyloguj", "zmien_spot"):
        kod, txt = n.napraw("a", rodzaj)
        assert kod == 3 and "zostaje w depo" in txt, (rodzaj, kod, txt)
    assert at.wywolania == [], at.wywolania
    s2, n2, at2 = _swiat_depo(False)
    kod, txt = n2.napraw("a", "wznow")
    assert kod == 0 and "start_bota" in at2.nazwy(), (kod, txt)


def test_zostan_w_depo_zagrozenie_zycia_nadal_eskaluje():
    s, n, at = _swiat_depo(True)
    s.log("a", [(s.zegar.t - timedelta(seconds=30), "ALARM: PK: gracz atakuje: X (czaszka), uciekam do depo")])
    n.tick()
    assert "powiadom" in at.nazwy() and n.post("a").get("hold"), at.wywolania      # PK/GM/zgon: eskalacja jak dotąd (hold)
    assert "start_bota" not in at.nazwy() and "wyloguj" not in at.nazwy()


def test_zostan_w_depo_stan_pokazuje_flage_i_znacznik_a_plan_repo_ma_stan_z_24_10():
    s, n, at = _swiat_depo(True)
    n.tick()
    pod = n.podsumowanie()["postacie"]["a"]
    assert pod["zostan_w_depo"] is True and pod["plan"]["zostan_w_depo"] is True and pod["zostaje_w_depo_od"], pod
    assert "Karol 23.10" in pod["plan"]["zostan_w_depo_powod"]
    s2, n2, _ = _swiat_depo(False)
    pod2 = n2.podsumowanie()["postacie"]["a"]
    assert pod2["zostan_w_depo"] is False and pod2["plan"]["zostan_w_depo"] is False and not pod2["zostaje_w_depo_od"]
    plan = P.wczytaj(KORZEN)
    assert plan.postacie["wydra"].zostan_w_depo and plan.postacie["wydra"].zostan.po_refillach == 0       # wydra: od razu (Karol 23.10)
    for id_ in ("invincible", "dawajkesh"):       # Karol 24.10: 2 bp UH, potem depo i wylogowanie (flaga po 1. refillu + wyloguj_w_depo)
        pc = plan.postacie[id_]
        assert pc.zostan_w_depo and pc.zostan.po_refillach == 1 and pc.zostan.od_ts and pc.wyloguj_w_depo and pc.spot_przypiety, id_
    assert not plan.postacie["gebelish"].zostan_w_depo and not plan.postacie["odchyd"].zostan_w_depo     # gebelish: flaga zdjęta 24.10 ~09:45
    assert not plan.bledy, plan.bledy


def test_zostan_w_depo_plan_nieczytelny_nie_zmienia_zachowania_i_nie_wywraca():
    s, n, at = _swiat_depo(True)
    (s.k / "instancje" / "_wspolne" / "plan_postaci.json").write_text("{zepsute")
    n.tick()                                                     # flagi nieznane = jak przed flagą (ostrzeżenie plan-blad w dzienniku)
    assert any("plan" in x.get("powod", "").lower() for x in n.dziennik.ostatnie)


# ============================================================ po_zwolnieniu (23.10, Karol: odchyd wchodzi na spot gebelisha ~10 min po jego wyjściu)
ZWOLN = "po_zwolnieniu g thais_pn_z9 +10min"


def zwolnienie(g_bot=False, stop_min=11, g_mapa="thais_pn_z9", level=8, plan_kroki=None, tryb_nadzorcy="naprawy", stop_reczny=False, c=None):
    """a = odchyd (lvl 8, thais_pn_z8, ostrozny,ml), g = gebelish (online w depo, spot z9 jeszcze w stanie nadzorcy)."""
    s = SwiatP(("a", "g") + (("c",) if c else ()), {"a": {"kroki": plan_kroki or [krok(ZWOLN, "mapa thais_pn_z9 ostrozny,ml", "z9")]}})
    aktywna_zmiana(s)
    s.gra("a", "thais_pn_z8", "ostrozny,ml", level)
    s.tryb_log("g", g_mapa, "ostrozny,runy", s.zegar.t - timedelta(hours=2))
    s.online("g", bot=g_bot, level=11)
    if c:
        s.gra("c", c, "ostrozny", 12)
    if stop_min is not None:
        stop = s.plik("g", "STOP")
        stop.touch()
        t = (s.zegar.t - timedelta(minutes=stop_min)).timestamp()
        os.utime(stop, (t, t))
    if stop_reczny:
        s.plik("g", "STOP_RECZNY").touch()
    n, at = nadzorca(s, tryb_nadzorcy)
    n.post("g")["spot"] = {"mapa": "thais_pn_z9"}              # gebelish ma spot z9 w stanie nadzorcy nawet w depo (nie może blokować celu)
    return s, n, at


def _a(at, *nazwy):
    return [w for w in at.wywolania if w[1:2] == ("a",) and (not nazwy or w[0] in nazwy)]


def test_po_zwolnieniu_parsowanie_opis_i_walidacja():
    assert P.parsuj_warunek(ZWOLN) == {"typ": "po_zwolnieniu", "kto": "g", "mapa": "thais_pn_z9", "min": 10}
    assert P.parsuj_warunek("po_zwolnieniu gebelish thais_pn_z9 +10 min")["min"] == 10
    assert P.opis_warunku(P.parsuj_warunek(ZWOLN)) == ZWOLN
    for zle in ("po_zwolnieniu g thais_pn_z9", "po_zwolnieniu g +10min", "po_zwolnieniu g thais_pn_z9 10min", "po_zwolnieniu g thais_pn_z9 +x min"):
        try:
            P.parsuj_warunek(zle)
            raise AssertionError(f"przeszło: {zle!r}")
        except ValueError:
            pass
    s = SwiatP(("a", "g"), {"a": {"kroki": [krok(ZWOLN, "mapa thais_pn_z9 ostrozny,ml", "ok"), krok(ZWOLN, "wroc", "zly1"),
                                            krok(ZWOLN, "tryb ostrozny", "zly2"), krok(ZWOLN, "mapa thais_pn_z8", "zly3"),
                                            krok("po_zwolnieniu a thais_pn_z9 +1min", "mapa thais_pn_z9", "zly4")]}})
    p = P.wczytaj(s.k)
    assert [k.id for k in p.postacie["a"].kroki] == ["ok"] and len(p.bledy) == 4, p.bledy


def test_po_zwolnieniu_po_10_min_wroc_i_uzbrojenie_na_zywo_bez_nadzor_zywo():
    s, n, at = zwolnienie(stop_min=11)
    n.tick()
    assert [w[0] for w in _a(at)] == ["wroc", "powiadom_info"], at.wywolania
    k = s.plan_odczyt()["a"]["kroki"][0]
    assert k["zrobione_t"] is None and k.get("uzbrojone_t") and k.get("tylko_refill") is not True, k
    assert not (s.k / "ostatni_start.a.env").exists()
    s.zegar.dalej(minutes=5)
    s.plik("a", "WROC").unlink(missing_ok=True)
    n.tick()
    assert len(_a(at, "wroc")) == 1, "raz: " + str(at.wywolania)
    assert "plan-mapa" in str([x for x in n.dziennik.ostatnie]) or any("z9" in x.get("powod", "") for x in n.dziennik.ostatnie), n.dziennik.ostatnie


def test_po_zwolnieniu_przed_10_min_nic():
    s, n, at = zwolnienie(stop_min=5)
    n.tick()
    assert _a(at) == [] and not s.plan_odczyt()["a"]["kroki"][0].get("uzbrojone_t"), at.wywolania
    s.zegar.dalej(minutes=6)
    n.tick()
    assert _a(at, "wroc"), at.wywolania


def test_po_zwolnieniu_bez_dowodu_zwolnienia_nic_awaria_bot_dziala_stop_reczny():
    for nazwa, kw in (("bez STOP (awaria / restart w toku)", dict(stop_min=None)), ("bot gebelisha działa na z9", dict(g_bot=True, stop_min=30)),
                      ("STOP_RECZNY", dict(stop_reczny=True, stop_min=30))):
        s, n, at = zwolnienie(**kw)
        for _ in range(3):
            n.tick()
            s.zegar.dalej(minutes=30)
        assert _a(at) == [], (nazwa, at.wywolania)


def test_po_zwolnieniu_gebelish_dziala_na_innej_mapie_liczy_od_wpisu_mapy():
    s, n, at = zwolnienie(g_bot=True, stop_min=None, g_mapa="thais_pn_z8")
    s.tryb_log("g", "trolle_edron", "ostrozny", s.zegar.t - timedelta(minutes=12))
    s.inst["g"]["bot"] = True
    n.tick()
    assert _a(at, "wroc"), at.wywolania


def test_po_zwolnieniu_cel_scisly_zajeta_jaskinia_czeka_bez_zamiennika():
    s, n, at = zwolnienie(c="thais_pn_z8")
    n.tick()
    assert _a(at, "wroc", "zatrzymaj_bota", "start_bota") == [], at.wywolania
    assert any("zajęty" in x.get("powod", "") and "ścisły" in x.get("powod", "") for x in n.dziennik.ostatnie), n.dziennik.ostatnie
    assert s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None


def test_po_zwolnieniu_poziom_poza_widelkami_celu_nie_wykonuje():
    s, n, at = zwolnienie(level=7)
    n.tick()
    assert _a(at, "wroc", "zatrzymaj_bota", "start_bota") == [], at.wywolania
    assert s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None


def test_po_zwolnieniu_w_walce_czeka_a_w_cieniu_niczego_nie_zmienia():
    s, n, at = zwolnienie()
    s.log("a", [(s.zegar.t - timedelta(seconds=3), "Cel Troll: atak")])
    n.tick()
    assert _a(at) == [], at.wywolania
    s2, n2, at2 = zwolnienie(tryb_nadzorcy="cien")
    przed = s2.plan_bajty()
    n2.tick()
    assert s2.plan_bajty() == przed and at2.wywolania == [], at2.wywolania


def test_po_zwolnieniu_odchyd_juz_na_celu_oznacza_zrobione_bez_restartu():
    s, n, at = zwolnienie()
    s.tryb_log("a", "thais_pn_z9", "ostrozny,ml")
    n.tick()
    assert not _a(at, "wroc", "zatrzymaj_bota", "start_bota"), at.wywolania
    assert s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"], s.plan_odczyt()


def test_po_zwolnieniu_start_konsumuje_uzbrojony_krok_cel_scisly_i_stan_pokazuje_warunek():
    s = SwiatP(("a", "g"), {"a": {"kroki": [krok(ZWOLN, "mapa thais_pn_z9 ostrozny,ml", "z9", uzbrojone_t="2026-10-21 09:20:00")]}})
    r, log, _ = kons(s, "a", "nadzor", bramki=False, biezaca=("thais_pn_z8", "ostrozny,ml"), poziom=8, zajete=set(), zajete_bez=lambda kto: set())
    assert r and r["mapa"] == "thais_pn_z9" and r["tryb"] == "ostrozny,ml" and r["kroki"] == ["z9"], (r, log)
    s2 = SwiatP(("a", "g"), {"a": {"kroki": [krok(ZWOLN, "mapa thais_pn_z9 ostrozny,ml", "z9", uzbrojone_t="2026-10-21 09:20:00")]}})
    r2, log2, _ = kons(s2, "a", "nadzor", bramki=False, biezaca=("thais_pn_z8", "ostrozny,ml"), poziom=8, zajete=set(),
                       zajete_bez=lambda kto: {"thais_pn_z9"})          # gebelish znów na z9: nie ma zamiennika z8
    assert r2 is None and s2.plan_odczyt()["a"]["kroki"][0]["zrobione_t"] is None, (r2, log2)
    assert any("ścisły" in x[2] for x in log2), log2
    s3 = SwiatP(("a", "g"), {"a": {"kroki": [krok(ZWOLN, "mapa thais_pn_z9 ostrozny,ml", "z9")]}})
    assert kons(s3, "a", "nadzor", bramki=False, biezaca=("thais_pn_z8", "ostrozny,ml"), poziom=8)[0] is None, "nieuzbrojony krok nie startuje"
    n3, _ = nadzorca(s3, "cien")
    aktywna_zmiana(s3)
    s3.gra("a", "thais_pn_z8", "ostrozny,ml", 8)
    st = n3.podsumowanie()["postacie"]["a"]["plan"]["nastepny"]["stan"]
    assert "g zwolni thais_pn_z9" in st and "+10 min" in st, st


def test_po_zwolnieniu_start_nadzorcy_uzbrojonego_kroku_idzie_na_z9_mimo_spotu_gebelisha_w_stanie():
    s = SwiatP(("a", "g"), {"a": {"kroki": [krok(ZWOLN, "mapa thais_pn_z9 ostrozny,ml", "z9", uzbrojone_t="2026-10-21 09:20:00")]}})
    s.grafik([TN.zmiana("a", od="2026-10-21 09:00", koniec="2026-10-21 11:00", wylog="2026-10-21 11:15")])
    s.tryb_log("a", "thais_pn_z8", "ostrozny,ml", datetime(2026, 10, 21, 8, 0))
    s.tryb_log("g", "thais_pn_z9", "ostrozny,runy", datetime(2026, 10, 21, 8, 0))
    s.online("g", bot=False, level=11)
    n, at = nadzorca(s, "zywo")
    at.zapisuj_tryb = True
    n.post("g")["spot"] = {"mapa": "thais_pn_z9"}
    start_nowej_sesji(s, poz=TN.THAIS, level=8)
    n.post("a").update(faza="DOJSCIE", sesja_nasza=True, login_ts=s.zegar.t.timestamp(), zmiana_od="2026-10-21 09:00")
    n.tick()
    st = _a(at, "start_bota")
    assert len(st) == 1 and st[0][2:] == ("thais_pn_z9", "ostrozny,ml"), at.wywolania
    assert s.plan_odczyt()["a"]["kroki"][0]["zrobione_t"]


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
                print("BŁĄD", nazwa, repr(e)[:500])
                traceback.print_exc()
    print(f"{ok}/{ok + zle} testów zielonych")
    sys.exit(1 if zle else 0)
