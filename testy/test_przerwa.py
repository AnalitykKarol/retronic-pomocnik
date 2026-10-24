#!/usr/bin/env python3
"""Przerwa postaci (24.10, Karol: „nadzorca ma sam robić przerwy postaci i ewentualnie zmieniać spot”; SPEC_przerwa_postaci_1024.md).
Offline: katalogi tymczasowe, atrapy źródeł i wykonawcy z testy/test_nadzor.py / test_plan_postaci.py; refill.sh tylko w piaskownicy z atrapą serwis.sh.
Nic nie dotyka gry, botów, sesji ani timera.
Dowodzi: (a) walidacja pola `przerwa` (zły wpis = błąd planu, nie przerwa); CLI `przerwa` i `pokaz`; (b) łańcuch po_refillu: refill bez wyjścia -> znacznik ->
wylogowanie (kod plan-przerwa-wyloguj, zapis do planu PRZED wylogowaniem, bez końca zmiany z grafiku) -> czekanie do `do_t` -> start sesji (plan-przerwa-powrot)
-> logowanie (plan-przerwa-zaloguj) -> `refill.sh --spot` (plan-przerwa-spot) -> `zrobione_t`; (c) bramki wylogowania i powrotu (STOP_RECZNY, walka, serwis, odstęp,
3 porażki, cisza nocna, nieudane wylogowanie = cofnięty zapis, nieudany zapis = brak wylogowania); (d) `--teraz`: online (WROC, potem wylogowanie), w mieście
(od razu), offline (odliczanie od razu); (e) zmiana spotu: gracz z pola albo z logu bota (próg, własne postacie pominięte), brak alternatywy, spot przypięty, zajęta
jaskinia; (f) wyłącznik (env i nadzor_konfig.json) gasi nowe przerwy, trwająca się kończy; (g) cień i `--raz` niczego nie zapisują; (h) BEZ wpisu `przerwa`
zachowanie identyczne jak dotąd; (i) refill_auto.py i refill.sh: tryb bez wyjścia i znacznik.
Uruchomienie: python3 -I testy/test_przerwa.py"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["RETRONIC_TESTY"] = "1"
os.environ.pop("NADZOR_PRZERWY", None)
KORZEN = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
sys.path.insert(0, str(KORZEN / "testy"))
import nadzor as N  # noqa: E402
import test_nadzor as TN  # noqa: E402
import test_plan_postaci as TP  # noqa: E402
import plan_postaci as P  # noqa: E402
import przerwa as PR  # noqa: E402
import refill_auto as RA  # noqa: E402

FMT = "%Y-%m-%d %H:%M:%S"
PR60 = {"min": 60, "rozrzut_min": 0, "kiedy": "po_refillu", "zmien_spot": "nie", "powod": "gracz Tuhandryt ciągnie moby"}
POZ_ED = [33110, 31742, 7]


class AtrapaP(TN.Atrapa):
    """Atrapa z `refill_spot`: jak refill.sh --spot (bot rusza, STOP znika, [TRYB] w tryb.log)."""

    def refill_spot(self, id_, mapa=None, tryb=None):
        r = self._pre("refill_spot", id_, mapa, tryb)
        if r is not None:
            return r
        self.s.inst[id_]["bot"] = True
        self.s.plik(id_, "STOP").unlink(missing_ok=True)
        if mapa:
            self.s.tryb_log(id_, mapa, tryb or "ostrozny", self.s.zegar.t)
        return self._w("refill_spot", id_, mapa, tryb)


def _opisz(n):
    """Zapis (id, akcja, kod) każdej decyzji przekazanej do `wykonaj` (rekordy dziennika kodu nie mają)."""
    n.kody = []
    orig = n.wykonaj

    def w(teraz, id_, d, o=None):
        n.kody.append((id_, d["akcja"], d["kod"]))
        return orig(teraz, id_, d, o)
    n.wykonaj = w
    return n


def kody(n, id_="a"):
    return [k for i, _, k in n.kody if i == id_]


def nadz(s, tryb="naprawy", zapis=True):
    n, at = _nadz(s, tryb, zapis)
    return _opisz(n), at


def _nadz(s, tryb="naprawy", zapis=True):
    """naprawy = timer z NADZOR_NAPRAWY (plan-* na żywo, reszta w cieniu); zywo = NADZOR_ZYWO; cien = nic na żywo."""
    at = AtrapaP(s)
    if tryb == "zywo":
        return N.Nadzorca(s.k, s.zegar, s, at, True, zapis), at
    if tryb == "cien":
        return N.Nadzorca(s.k, s.zegar, s, N.WykonawcaCien(), False, zapis), at
    return N.Nadzorca(s.k, s.zegar, s, N.WykonawcaCien(), False, zapis, naprawy_poziom=True, wykonawca_poziom=at), at


def swiat(przerwa=None, ids=("a",), plan_dod=None, bot=False, stop=True, w_miescie=True, spoty=False, offline=False, log_depo=True):
    """Postać `a` w mieście (depo, STOP, bez bota) z grafikiem 10:00-15:00 (T0 = 11:20); przerwa = wpis planu."""
    plan = {i: {"kroki": [], **(plan_dod or {})} for i in ids}
    if przerwa is not None:
        plan["a"]["przerwa"] = dict(przerwa)
    s = TP.SwiatP(ids, plan)
    if spoty:
        TN.tabela_q5(s)
    s.grafik([TN.zmiana(i, od="2026-10-21 10:00", koniec="2026-10-21 15:00", wylog="2026-10-21 15:15") for i in ids])
    for i in ids:
        s.tryb_log(i, "ed_a" if spoty else "trolle_edron_z9z", "ostrozny,runy", s.zegar.t.replace(hour=10, minute=0))
        if offline:
            continue
        panel = {"w_depo": True, "w_miescie": "edron", "wroc_refill": "brak_planu", "pozycja": list(POZ_ED)} if w_miescie else {}
        s.online(i, bot=bot, level=12, **panel)
        s.inst[i]["panel"]["level"] = 12
        if stop and not bot:
            s.plik(i, "STOP").touch()
            starosc(s, i, 10)
        if log_depo:
            s.log(i, [(s.zegar.t - timedelta(minutes=30), "Wyprawa: DEPO osiągnięte"), (s.zegar.t - timedelta(minutes=29), "Zatrzymano (plik STOP).")])
    return s


def starosc(s, id_, minut):
    """STOP/znaczniki starzeją się według ZEGARA TESTU (nadzorca porównuje mtime z teraz)."""
    t = (s.zegar.t - timedelta(minutes=minut)).timestamp()
    for nazwa in ("STOP", "WROC"):
        p = s.plik(id_, nazwa)
        if p.exists():
            os.utime(p, (t, t))


def marker(s, id_="a", minut_temu=1):
    p = s.plik(id_, PR.MARKER_REFILL)
    p.write_text(str(int((s.zegar.t - timedelta(minutes=minut_temu)).timestamp())) + "\n")
    return p


def pr_plan(s, id_="a"):
    return s.plan_odczyt()[id_].get("przerwa") or {}


def stan_bajty(s):
    """Wszystko, co cień (--raz) mógłby zmienić: plan i stan nadzorcy."""
    wynik = {}
    for p in sorted((s.k / "instancje").rglob("*")):
        if p.is_file() and "logi" not in p.parts[-3:-1] and not p.name.endswith(".lock"):
            try:
                wynik[str(p.relative_to(s.k))] = p.read_bytes()
            except OSError:
                pass
    return wynik


def akcje(n, id_="a"):
    return [(x["akcja"], x["wynik"]) for x in n.dziennik.ostatnie if x["id"] == id_]


def kody_dz(n, id_="a"):
    return [x for x in n.dziennik.ostatnie if x["id"] == id_]


def tik(s, n, min_=0):
    n.tick()
    if min_:
        s.zegar.dalej(minutes=min_)


def do_wylogowania(s, n):
    """Znacznik refillu bez wyjścia + jeden tick: wylogowanie na przerwę."""
    marker(s)
    n.tick()


# ============================================================ (a) walidacja, plan, CLI
def test_parsuj_poprawny_wpis_i_domyslne():
    p = PR.parsuj({"min": 60})
    assert (p.min, p.rozrzut_min, p.kiedy, p.zmien_spot, p.gracz) == (60, 10, "po_refillu", "nie", "") and not p.wylogowano_t
    p = PR.parsuj({"min": 45, "rozrzut_min": 5, "kiedy": "teraz", "zmien_spot": "jesli_gracz", "gracz": "Tuhandryt", "powod": "x",
                   "wylogowano_t": "2026-10-21 11:00:00", "do_t": "2026-10-21 11:50:00", "gracz_wykryty": "Ktos"})
    assert p.kiedy == "teraz" and p.gracz == "Tuhandryt" and p.do_ts() == datetime(2026, 10, 21, 11, 50).timestamp() and p.gracz_wykryty == "Ktos"
    assert PR.parsuj({"min": 1, "rozrzut_min": 1}).rozrzut_min == 1


def test_parsuj_zle_wpisy_to_valueerror():
    zle = [None, [], "60", {}, {"min": 0}, {"min": -5}, {"min": 721}, {"min": "60"}, {"min": True}, {"min": 60.5}, {"min": 60, "rozrzut_min": 61},
           {"min": 60, "rozrzut_min": -1}, {"min": 60, "rozrzut_min": "10"}, {"min": 60, "kiedy": "jutro"}, {"min": 60, "zmien_spot": "tak"},
           {"min": 60, "gracz": "a b c d e f"}, {"min": 60, "gracz": 5}, {"min": 60, "do_t": "wczoraj"}, {"min": 60, "zrobione_t": "2026-10-21"},
           {"min": 60, "wylogowano_t": "2026-10-21 11:00:00"}]
    for w in zle:
        try:
            PR.parsuj(w)
        except ValueError:
            continue
        raise AssertionError(f"przeszło: {w!r}")


def test_plan_zly_wpis_przerwy_to_blad_planu_a_postac_zyje_bez_przerwy():
    s = TP.SwiatP(("a", "b"), {"a": {"kroki": [], "przerwa": {"min": 0}}, "b": {"kroki": [], "przerwa": dict(PR60)}})
    p = P.wczytaj(s.k)
    assert p.bledy and any("postać a" in b and "przerwa" in b for b in p.bledy), p.bledy
    assert p.postacie["a"].przerwa is None and p.postacie["b"].przerwa is not None and p.postacie["b"].przerwa.min == 60
    assert not p.nieczytelny


def test_opis_i_pokaz():
    s = swiat({**PR60, "zmien_spot": "jesli_gracz"})
    o = P.opis_planu(s.k, "a", None, s.zegar.t, P.wczytaj(s.k))
    assert "po refillu" in o["przerwa"] and "czeka na refill" in o["przerwa"] and "zmiana spotu" in o["przerwa"], o["przerwa"]
    assert P.opis_planu(TP.SwiatP(("a",), {"a": {"kroki": []}}).k, "a", None, s.zegar.t, None)["przerwa"] == ""
    p = PR.parsuj({**PR60, "wylogowano_t": "2026-10-21 11:00:00", "do_t": "2026-10-21 12:00:00"})
    assert "wylogowana 11:00, powrót 12:00" in PR.opis(p)
    p = PR.parsuj({**PR60, "zrobione_t": "2026-10-21 12:05:00"})
    assert "zrobiona 10-21 12:05" in PR.opis(p)


def _cli(korzen, *argv):
    stare = os.environ.get("RETRONIC_NADZOR_KORZEN")
    os.environ["RETRONIC_NADZOR_KORZEN"] = str(korzen)
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            kod = P.main(list(argv))
    finally:
        if stare is None:
            os.environ.pop("RETRONIC_NADZOR_KORZEN", None)
        else:
            os.environ["RETRONIC_NADZOR_KORZEN"] = stare
    return kod, out.getvalue(), err.getvalue()


def test_cli_przerwa_ustaw_pokaz_nadpisz_anuluj():
    s = TP.SwiatP(("a", "b"), {"a": {"kroki": [], "spot_przypiety": True}})
    kod, out, err = _cli(s.k, "przerwa", "a", "60")
    assert kod == 0 and "przerwa 60±10 min, po refillu" in out and "zmiana spotu jeśli gracz" in out, (kod, out, err)
    w = s.plan_odczyt()["a"]
    assert w["spot_przypiety"] is True and w["przerwa"]["min"] == 60 and w["przerwa"]["kiedy"] == "po_refillu" and w["przerwa"]["zmien_spot"] == "jesli_gracz", w
    kod, out, err = _cli(s.k, "przerwa", "a", "30")
    assert kod == 1 and "już jest niezakończona" in err and s.plan_odczyt()["a"]["przerwa"]["min"] == 60
    kod, out, err = _cli(s.k, "przerwa", "a", "30", "--teraz", "--nadpisz", "--rozrzut", "0", "--zmien-spot", "nie", "--powod", "test", "--gracz", "Tuhandryt")
    w = s.plan_odczyt()["a"]["przerwa"]
    assert kod == 0 and (w["min"], w["kiedy"], w["rozrzut_min"], w["zmien_spot"], w["powod"], w["gracz"]) == (30, "teraz", 0, "nie", "test", "Tuhandryt"), w
    kod, out, err = _cli(s.k, "pokaz", "a")
    assert kod == 0 and "od razu (wróć do miasta)" in out and "czeka na powrót do miasta" in out, out
    kod, out, err = _cli(s.k, "przerwa", "b", "60")             # postać bez wpisu w planie: powstaje wpis (instancja istnieje)
    assert kod == 0 and "przerwa" in s.plan_odczyt()["b"], (kod, err)
    kod, out, err = _cli(s.k, "przerwa", "a", "--anuluj")
    assert kod == 0 and "przerwa" not in s.plan_odczyt()["a"] and s.plan_odczyt()["a"]["spot_przypiety"] is True
    kod, out, err = _cli(s.k, "przerwa", "a", "--anuluj")
    assert kod == 1


def test_cli_przerwa_bledy_nieznana_instancja_zla_dlugosc_brak_dlugosci_i_wylacznik():
    s = TP.SwiatP(("a",), {"a": {"kroki": []}})
    before = s.plan_bajty()
    assert _cli(s.k, "przerwa", "nie_ma", "60")[0] == 2
    assert _cli(s.k, "przerwa", "a", "0")[0] == 2
    assert _cli(s.k, "przerwa", "a", "9999")[0] == 2
    assert _cli(s.k, "przerwa", "a")[0] == 2
    assert _cli(s.k, "przerwa", "a", "60", "--rozrzut", "61")[0] == 2
    assert _cli(s.k, "przerwa", "a", "60", "--gracz", "a b c d e f")[0] == 2
    assert s.plan_bajty() == before
    os.environ["NADZOR_PRZERWY"] = "0"
    try:
        kod, out, err = _cli(s.k, "przerwa", "a", "60")
    finally:
        os.environ.pop("NADZOR_PRZERWY")
    assert kod == 0 and "UWAGA: przerwy wyłączone" in out, out


def test_cli_przerwa_nie_rusza_trwajacej_przerwy_przy_anuluj():
    s = TP.SwiatP(("a",), {"a": {"kroki": [], "przerwa": {**PR60, "wylogowano_t": "2026-10-21 11:00:00", "do_t": "2026-10-21 12:00:00"}}})
    kod, out, err = _cli(s.k, "przerwa", "a", "--anuluj")
    assert kod == 1 and s.plan_odczyt()["a"]["przerwa"]["do_t"] == "2026-10-21 12:00:00"
    kod, out, err = _cli(s.k, "przerwa", "a", "30")
    assert kod == 1                                        # niezakończona (trwa) = bez --nadpisz nie zastąpisz


# ============================================================ (b) łańcuch po_refillu
def _lancuch(tryb):
    s = swiat(PR60)
    n, at = nadz(s, tryb)
    n.stan["postacie"]["a"] = {"faza": "EXP", "bot_widziany": 0, "bot_start": s.zegar.t.timestamp() - 3000, "zmiana_od": "2026-10-21 10:00:00",
                               "login_ts": s.zegar.t.timestamp() - 7000, "sesja_nasza": True}
    # 1. refill jeszcze trwa / nie zostawił znacznika: żadnego wylogowania i żadnych decyzji przerwy
    for _ in range(3):
        n.tick()
        s.zegar.dalej(minutes=1)
    assert "wyloguj" not in at.nazwy() and not [k for k in kody(n) if k.startswith("plan-przerwa")], (at.wywolania, n.kody)
    assert "wylogowano_t" not in pr_plan(s)
    # 2. refill bez wyjścia skończony (znacznik): wylogowanie na żywo, zapis w planie PRZED wylogowaniem
    t_wyl = s.zegar.t
    plik = marker(s)
    n.tick()
    assert at.nazwy() == ["wyloguj", "powiadom_info"], (tryb, at.wywolania)
    p = pr_plan(s)
    assert p["wylogowano_t"] == t_wyl.strftime(FMT) and p["do_t"] == (t_wyl + timedelta(minutes=60)).strftime(FMT), p
    assert not plik.exists() and "zakonczone" not in n.stan["postacie"]["a"] or not n.stan["postacie"]["a"].get("zakonczone"), n.stan["postacie"]["a"]
    assert n.stan["postacie"]["a"]["faza"] == "OFFLINE" and s.plik("a", "STOP").exists() and not s.plik("a", "STOP_RECZNY").exists()
    assert f"przerwa do {t_wyl + timedelta(minutes=60):%H:%M}" in str(at.wywolania), at.wywolania
    # 3. offline do `do_t`: czeka (nie startuje sesji), plan bez zmian
    for m in (1, 14, 30, 14):
        s.zegar.dalej(minutes=m)
        n.tick()
    assert "sesja_start" not in at.nazwy() and s.zegar.t < t_wyl + timedelta(minutes=60), at.wywolania
    assert "plan-przerwa-czeka" in kody(n), n.kody
    # 4. po `do_t`: start sesji (kod plan-*, na żywo także w trybie naprawy), potem logowanie, potem refill.sh --spot
    s.zegar.dalej(minutes=2)
    n.tick()
    assert at.nazwy().count("sesja_start") == 1, at.wywolania
    assert n.stan["postacie"]["a"]["faza"] == "LOGOWANIE" and n.stan["postacie"]["a"]["sesja_nasza"] and not n.stan["postacie"]["a"].get("zmiana_od")
    s.inst["a"]["gra"] = True                              # klient wstał, ekran logowania
    s.zegar.dalej(minutes=2)
    n.tick()
    assert at.nazwy()[-1] == "zaloguj", at.wywolania
    s.inst["a"].update(panel={"pozycja": list(POZ_ED), "level": 12, "w_miescie": "edron", "w_depo": True, "wroc_refill": "brak_planu"})
    s.zegar.dalej(minutes=1)
    n.tick()
    assert at.wywolania[-2:][0][0] == "refill_spot" or "refill_spot" in at.nazwy(), at.wywolania
    rs = [w for w in at.wywolania if w[0] == "refill_spot"]
    assert len(rs) == 1 and rs[0][1:] == ("a", None, None), rs                      # ten sam spot: bez MAPA/TRYB
    p = pr_plan(s)
    assert p["zrobione_t"] and n.stan["postacie"]["a"]["faza"] == "POWROT", (p, n.stan["postacie"]["a"])
    assert s.inst["a"]["bot"] and not s.plik("a", "STOP").exists()
    # 5. po przerwie: jednorazowa, nic więcej, żadnej eskalacji
    n_wyw = len(at.wywolania)
    for _ in range(5):
        s.zegar.dalej(minutes=3)
        n.tick()
    assert [w for w in at.wywolania[n_wyw:] if w[0] in ("wyloguj", "sesja_start", "refill_spot", "wroc")] == [], at.wywolania[n_wyw:]
    assert not [x for x in kody_dz(n) if x["akcja"] == "eskaluj"], kody_dz(n)
    return s, n, at


def test_po_refillu_caly_lancuch_w_trybie_naprawy():
    _lancuch("naprawy")


def test_po_refillu_caly_lancuch_w_trybie_zywo():
    _lancuch("zywo")


def test_po_refillu_bez_znacznika_refill_w_toku_lub_stary_znacznik_nie_wylogowuje():
    s = swiat(PR60)
    n, at = nadz(s, "zywo")
    for m in (1, 1):
        n.tick()
        s.zegar.dalej(minutes=m)
    p = marker(s, minut_temu=4 * 60)                       # znacznik starszy niż 3 h = nieważny
    n.tick()
    assert "wyloguj" not in at.nazwy(), at.wywolania
    assert "wylogowano_t" not in pr_plan(s)
    p.write_text("nie liczba\n")
    s.zegar.dalej(minutes=3)
    n.tick()
    assert "wyloguj" not in at.nazwy()


def test_wylogowanie_na_przerwe_nie_konczy_zmiany_z_grafiku_i_nie_blokuje_zmiany_po_powrocie():
    s, n, at = _lancuch("zywo")
    st = n.stan["postacie"]["a"]
    assert not st.get("zakonczone"), st
    assert "sesja-po-wylogowaniu" not in str(kody_dz(n))


def test_rozrzut_powrotu_i_pelne_minuty():
    import random
    p = PR.parsuj({"min": 60, "rozrzut_min": 10})
    t = datetime(2026, 10, 21, 11, 0, 0)
    ws = {int((PR.losuj_do(p, t, random.Random(i)) - t).total_seconds() // 60) for i in range(200)}
    assert min(ws) >= 50 and max(ws) <= 70 and len(ws) > 10, sorted(ws)
    p0 = PR.parsuj({"min": 1, "rozrzut_min": 1})
    assert all((PR.losuj_do(p0, t, random.Random(i)) - t).total_seconds() >= 60 for i in range(50))


# ============================================================ (c) bramki
def test_wylogowanie_szanuje_stop_reczny_pauze_walke_serwis_i_odstep():
    # STOP_RECZNY: zero akcji
    s = swiat(PR60)
    s.plik("a", "STOP_RECZNY").touch()
    n, at = nadz(s, "zywo")
    marker(s)
    n.tick()
    assert at.wywolania == [] and "wylogowano_t" not in pr_plan(s)
    # walka: czeka na spokój
    s = swiat(PR60)
    n, at = nadz(s, "zywo")
    s.log("a", [(s.zegar.t - timedelta(seconds=5), "Cel Troll: atak")])
    marker(s)
    n.tick()
    assert "wyloguj" not in at.nazwy() and "plan-przerwa-spokoj" in kody(n), (at.wywolania, kody_dz(n))
    s.zegar.dalej(minutes=2)
    n.tick()
    assert at.nazwy().count("wyloguj") == 1, at.wywolania                         # po spokoju (log starszy niż 20 s)
    # serwis w toku
    s = swiat(PR60)
    s.inst["a"]["panel"]["serwis_dziala"] = True
    n, at = nadz(s, "zywo")
    marker(s)
    n.tick()
    assert "wyloguj" not in at.nazwy() and "plan-przerwa-serwis" in kody(n), kody_dz(n)
    # odstęp od poprzedniego zdarzenia logowania: odroczone, potem wylogowanie
    s = swiat(PR60)
    n, at = nadz(s, "zywo")
    n.stan["globalne"]["ostatnie_zdarzenie"] = s.zegar.t.timestamp() - 60
    marker(s)
    n.tick()
    assert "wyloguj" not in at.nazwy() and "wylogowano_t" not in pr_plan(s), at.wywolania
    s.zegar.dalej(minutes=30)
    n.tick()
    assert at.nazwy().count("wyloguj") == 1 and pr_plan(s)["wylogowano_t"]


def test_jedna_akcja_logowania_na_przebieg_dwie_postacie_na_przerwie():
    s = swiat(PR60, ids=("a", "b"), plan_dod=None)
    s.plan({"a": {"kroki": [], "przerwa": dict(PR60)}, "b": {"kroki": [], "przerwa": dict(PR60)}})
    n, at = nadz(s, "zywo")
    marker(s, "a")
    marker(s, "b")
    n.tick()
    assert at.nazwy().count("wyloguj") == 1, at.wywolania                           # druga czeka (jedna naraz + odstęp)
    pierwsza = [w for w in at.wywolania if w[0] == "wyloguj"][0][1]
    druga = "b" if pierwsza == "a" else "a"
    assert "wylogowano_t" not in pr_plan(s, druga)
    s.zegar.dalej(minutes=30)
    n.tick()
    assert at.nazwy().count("wyloguj") == 2 and pr_plan(s, druga)["wylogowano_t"]


def test_trzy_porazki_wylogowania_eskalacja_i_zapis_planu_cofniety_przy_kazdej():
    s = swiat(PR60)
    n, at = nadz(s, "zywo")
    at.wyniki["wyloguj"] = (False, "wyloguj.sh kod 3")
    marker(s)
    for i in range(3):
        n.tick()
        assert "wylogowano_t" not in pr_plan(s) and "do_t" not in pr_plan(s), (i, pr_plan(s))      # nieudane wylogowanie = zapis cofnięty
        s.zegar.dalej(minutes=10)
    assert n.stan["postacie"]["a"].get("wylog_bl", 0) >= 3, n.stan["postacie"]["a"]
    n.tick()
    assert any(x["akcja"] == "eskaluj" for x in kody_dz(n)), kody_dz(n)
    assert at.nazwy().count("wyloguj") == 3


def test_nieudany_zapis_do_planu_oznacza_brak_wylogowania():
    s = swiat(PR60)
    n, at = nadz(s, "zywo")
    marker(s)
    stare = N.PP.przerwa_zapisz
    N.PP.przerwa_zapisz = lambda *a, **k: False
    try:
        n.tick()
    finally:
        N.PP.przerwa_zapisz = stare
    assert "wyloguj" not in at.nazwy() and s.inst["a"]["sesja"], at.wywolania          # postać zostaje w grze, nic nie zapamiętane do połowy


def test_powrot_czeka_przez_cisze_nocna_i_odstep_potem_startuje():
    s = swiat({**PR60, "wylogowano_t": "2026-10-21 00:20:00", "do_t": "2026-10-21 00:50:00"}, offline=True)
    s.zegar.t = datetime(2026, 10, 21, 1, 10, 0)             # po `do_t`, ale w ciszy nocnej (01:00-08:00)
    n, at = nadz(s, "zywo")
    n.tick()
    assert at.wywolania == [] and "plan-przerwa-cisza" in kody(n), n.kody
    s.zegar.t = datetime(2026, 10, 21, 7, 59, 0)
    n.tick()
    assert at.wywolania == []
    s.zegar.t = datetime(2026, 10, 21, 8, 1, 0)
    n.tick()
    assert at.nazwy() == ["sesja_start"], at.wywolania
    # odstęp od poprzedniego zdarzenia: odroczone
    s2 = swiat({**PR60, "wylogowano_t": "2026-10-21 10:00:00", "do_t": "2026-10-21 11:00:00"}, offline=True)
    n2, at2 = nadz(s2, "zywo")
    n2.stan["globalne"]["ostatnie_zdarzenie"] = s2.zegar.t.timestamp() - 120
    n2.tick()
    assert at2.wywolania == [], at2.wywolania
    s2.zegar.dalej(minutes=30)
    n2.tick()
    assert at2.nazwy() == ["sesja_start"]


def test_komplet_online_odracza_powrot():
    s = swiat({**PR60, "wylogowano_t": "2026-10-21 10:00:00", "do_t": "2026-10-21 11:00:00"}, ids=("a", "b", "c", "d", "e", "f"), offline=True)
    s.plan({"a": {"kroki": [], "przerwa": {**PR60, "wylogowano_t": "2026-10-21 10:00:00", "do_t": "2026-10-21 11:00:00"}}})
    for i in "bcdef":
        s.online(i, bot=True)
    n, at = nadz(s, "zywo")
    n.tick()
    assert "sesja_start" not in [w[0] for w in at.wywolania if w[1] == "a"], at.wywolania


def test_trzy_nieudane_starty_po_przerwie_eskaluja():
    s = swiat({**PR60, "wylogowano_t": "2026-10-21 10:00:00", "do_t": "2026-10-21 11:00:00"}, offline=True)
    n, at = nadz(s, "zywo")
    at.wyniki["sesja_start"] = (False, "start sesji nieudany")
    for _ in range(3):
        n.tick()
        s.zegar.dalej(minutes=10)
    assert n.stan["postacie"]["a"]["start_bl"] == 3
    n.tick()
    assert any(x["akcja"] == "eskaluj" for x in kody_dz(n)), kody_dz(n)


def test_zalogowana_przez_czlowieka_przed_do_t_albo_obca_sesja_nie_dostaje_bota():
    s = swiat({**PR60, "wylogowano_t": "2026-10-21 11:00:00", "do_t": "2026-10-21 12:00:00"}, bot=False, stop=False)
    n, at = nadz(s, "zywo")
    n.stan["postacie"]["a"] = {"faza": "EXP", "login_ts": s.zegar.t.timestamp() - 100}
    n.tick()                                                  # przed do_t, ktoś jest w grze (Karol): nie ruszam
    assert at.wywolania == [] and "plan-przerwa-wygasa" in kody(n), (at.wywolania, kody_dz(n))
    s.zegar.t = datetime(2026, 10, 21, 12, 5, 0)
    s.zegar.dalej(minutes=0)
    n.tick()                                                  # po do_t, ale to nie nasza sesja (brak sesja_nasza): ręczna gra
    assert "refill_spot" not in at.nazwy() and "plan-przerwa-obca" in kody(n), (at.wywolania, kody_dz(n))


def test_bot_juz_dziala_po_powrocie_konczy_przerwe_bez_refill_spot():
    s = swiat({**PR60, "wylogowano_t": "2026-10-21 10:00:00", "do_t": "2026-10-21 11:00:00"}, bot=True)
    n, at = nadz(s, "zywo")
    n.stan["postacie"]["a"] = {"faza": "EXP", "login_ts": s.zegar.t.timestamp() - 100, "sesja_nasza": True, "bot_widziany": s.zegar.t.timestamp() - 5}
    n.tick()
    assert "refill_spot" not in at.nazwy() and pr_plan(s).get("zrobione_t"), (at.wywolania, pr_plan(s))


# ============================================================ (d) --teraz
def test_teraz_online_z_botem_wroc_potem_wyloguj_w_miescie():
    for tryb in ("naprawy", "zywo"):
        s = swiat({**PR60, "kiedy": "teraz"}, bot=True)
        n, at = nadz(s, tryb)
        n.stan["postacie"]["a"] = {"faza": "EXP", "bot_widziany": s.zegar.t.timestamp(), "bot_start": s.zegar.t.timestamp() - 3000,
                                   "zmiana_od": "2026-10-21 10:00:00", "login_ts": s.zegar.t.timestamp() - 7000, "sesja_nasza": True}
        s.log("a", [(s.zegar.t - timedelta(seconds=90), "Cel Troll zabity na (1, 2, 8).")])
        n.tick()
        assert at.nazwy() == ["wroc"], (tryb, at.wywolania)
        assert not n.stan["postacie"]["a"].get("naprawy"), "WROC przerwy nie liczy się do drabiny napraw"
        assert s.plik("a", "WROC").exists()
        s.zegar.dalej(minutes=2)
        n.tick()
        assert at.nazwy() == ["wroc"], "WROC w toku: bez drugiego zlecenia"
        # bot dotarł do depo: WROC zniknął, STOP, bez bota; za świeży STOP (< 120 s) i auto-refill czeka: jeszcze nie wylogowuję
        s.plik("a", "WROC").unlink()
        TN.w_miescie(s, "a")
        s.inst["a"]["panel"].update(wroc_refill="czeka")
        n.tick()
        assert "wyloguj" not in at.nazwy(), at.wywolania
        s.inst["a"]["panel"].update(wroc_refill="brak_planu")
        n.tick()
        assert "wyloguj" not in at.nazwy(), "STOP młodszy niż 120 s"
        starosc(s, "a", 5)
        s.zegar.dalej(minutes=8)          # 7 min odstępu od (cieniowego) końca zmiany z grafiku, który zwykły przepływ zapisał w międzyczasie
        starosc(s, "a", 5)
        n.tick()
        assert at.nazwy().count("wyloguj") == 1, (tryb, at.wywolania, n.kody)
        assert "serwis" not in at.nazwy() and "plan-przerwa-stop-swiezy" in kody(n) and "plan-przerwa-refill" in kody(n), n.kody    # zwykły „koniec zmiany” nie przejął postaci
        p = pr_plan(s)
        assert p["wylogowano_t"] and p["do_t"], p


def test_teraz_w_walce_bot_czeka_na_spokoj_przed_wroc():
    s = swiat({**PR60, "kiedy": "teraz"}, bot=True)
    n, at = nadz(s, "zywo")
    n.stan["postacie"]["a"] = {"faza": "EXP", "bot_widziany": s.zegar.t.timestamp(), "bot_start": s.zegar.t.timestamp() - 3000,
                               "zmiana_od": "2026-10-21 10:00:00", "login_ts": s.zegar.t.timestamp() - 7000, "sesja_nasza": True}
    s.log("a", [(s.zegar.t - timedelta(seconds=4), "Cel Troll: atak")])
    n.tick()
    assert "wroc" not in at.nazwy() and "plan-przerwa-walka" in kody(n), (at.wywolania, kody_dz(n))


def test_teraz_wroc_bez_efektu_trzy_razy_to_eskalacja():
    s = swiat({**PR60, "kiedy": "teraz"}, bot=True)
    n, at = nadz(s, "zywo")
    n.stan["postacie"]["a"] = {"faza": "EXP", "bot_widziany": s.zegar.t.timestamp(), "bot_start": s.zegar.t.timestamp() - 3000,
                               "zmiana_od": "2026-10-21 10:00:00", "login_ts": s.zegar.t.timestamp() - 7000, "sesja_nasza": True}
    s.log("a", [(s.zegar.t - timedelta(seconds=90), "Cel Troll zabity na (1, 2, 8).")])
    for _ in range(3):
        n.tick()
        s.plik("a", "WROC").unlink(missing_ok=True)           # WROC „nie złapał”: bot dalej chodzi
        s.zegar.dalej(minutes=21)
        s.log("a", [(s.zegar.t - timedelta(seconds=60), "Cel Troll zabity na (1, 2, 8).")])
    assert at.nazwy().count("wroc") == 3, at.wywolania
    n.tick()
    assert any(x["akcja"] == "eskaluj" and "przerwa" in x["powod"] for x in kody_dz(n)), kody_dz(n)
    assert at.nazwy().count("wroc") == 3


def test_teraz_postac_juz_w_miescie_wylogowuje_od_razu_bez_refillu():
    s = swiat({**PR60, "kiedy": "teraz"})                    # w depo, STOP sprzed 10 min, auto-refill nie czeka
    n, at = nadz(s, "naprawy")
    n.tick()
    assert at.nazwy().count("wyloguj") == 1, at.wywolania
    p = pr_plan(s)
    assert p["do_t"] == (s.zegar.t + timedelta(minutes=60)).strftime(FMT), p
    # to samo bez dowodu miasta: nie wylogowuje (WROC wymaga bota, a nie wiadomo gdzie stoi)
    s2 = swiat({**PR60, "kiedy": "teraz"}, w_miescie=False, log_depo=False)
    n2, at2 = nadz(s2, "naprawy")
    n2.tick()
    assert "wyloguj" not in at2.nazwy() and "wylogowano_t" not in pr_plan(s2), at2.wywolania


def test_teraz_offline_zaczyna_odliczanie_od_razu_i_wraca_po_czasie():
    s = swiat({**PR60, "kiedy": "teraz"}, offline=True)
    n, at = nadz(s, "naprawy")
    n.tick()
    p = pr_plan(s)
    assert p["wylogowano_t"] == s.zegar.t.strftime(FMT) and p["do_t"] == (s.zegar.t + timedelta(minutes=60)).strftime(FMT), p
    assert at.wywolania == [] or all(w[0] != "sesja_start" for w in at.wywolania)
    s.zegar.dalej(minutes=30)
    n.tick()
    assert "sesja_start" not in at.nazwy()
    s.zegar.dalej(minutes=31)
    n.tick()
    assert at.nazwy().count("sesja_start") == 1, at.wywolania


def test_po_refillu_offline_czeka_na_refill_i_niczego_nie_zmienia():
    s = swiat(PR60, offline=True)
    n, at = nadz(s, "zywo")
    n0, at0 = nadz(swiat(None, offline=True), "zywo")
    n.tick()
    n0.tick()
    assert at.wywolania == at0.wywolania and "wylogowano_t" not in pr_plan(s)


# ============================================================ (e) zmiana spotu
def _swiat_spot(przerwa, b_na="ed_b", lina=True, plan_dod=None, log_gracza=None, mapa_a="ed_a"):
    s = swiat(przerwa, ids=("a", "b"), spoty=True)
    s.plan({"a": {"kroki": [], **(plan_dod or {}), "przerwa": dict(przerwa)}, "b": {"kroki": []}})
    s.tryb_log("a", mapa_a, "ostrozny", s.zegar.t.replace(hour=10, minute=0))
    s.online("b", bot=True, level=12, pozycja=[33110, 31742, 8])
    s.tryb_log("b", b_na, "ostrozny")
    s.ekw["a"] = {"lina": lina, "lopata": False}
    for (min_temu, nick) in (log_gracza or []):
        s.log("a", [(s.zegar.t - timedelta(minutes=min_temu), f"Gracz w pobliżu: {nick} (3 pól), gram dalej.")], nazwa="mozg-stdout-1021-1000.log")
    return s


def _przerwa_do_powrotu(s, tryb="zywo"):
    """Wylogowanie (znacznik), 61 min przerwy, start sesji, logowanie; zwraca (n, at) tuż przed decyzją przerwa_spot."""
    n, at = nadz(s, tryb)
    n.stan["postacie"]["a"] = {"faza": "EXP", "bot_widziany": 0, "bot_start": s.zegar.t.timestamp() - 3000, "zmiana_od": "2026-10-21 10:00:00",
                               "login_ts": s.zegar.t.timestamp() - 7000, "sesja_nasza": True}
    do_wylogowania(s, n)
    assert at.nazwy()[:1] == ["wyloguj"], at.wywolania
    s.zegar.dalej(minutes=61)
    n.tick()
    assert at.nazwy().count("sesja_start") == 1, at.wywolania
    s.inst["a"]["gra"] = True
    s.zegar.dalej(minutes=2)
    n.tick()
    assert at.nazwy().count("zaloguj") == 1, at.wywolania
    s.inst["a"].update(gracz={"hp": 100, "max_hp": 100, "level": 12}, panel={"pozycja": list(POZ_ED), "level": 12, "w_miescie": "edron", "w_depo": True,
                                                                            "wroc_refill": "brak_planu"})
    s.zegar.dalej(minutes=1)
    return n, at


def _spot_wywolania(at):
    return [w for w in at.wywolania if w[0] == "refill_spot"]


def test_spot_gracz_z_logu_bota_zmienia_spot_na_wolny():
    s = _swiat_spot({**PR60, "zmien_spot": "jesli_gracz"}, log_gracza=[(50, "Tuhandryt"), (45, "Tuhandryt"), (40, "Tuhandryt"), (35, "Tuhandryt"),
                                                                       (20, "B"), (19, "B"), (18, "B"), (17, "B"), (16, "B")])
    s.profil_b = None
    (s.k / "instancje" / "b" / "profil.json").write_text(json.dumps({"postac": "B"}))        # nasza postać: pomijana jako „gracz”
    n, at = _przerwa_do_powrotu(s)
    assert pr_plan(s)["gracz_wykryty"] == "Tuhandryt", pr_plan(s)
    n.tick()
    rs = _spot_wywolania(at)
    assert len(rs) == 1 and rs[0][1] == "a" and rs[0][2] == "ed_c" and rs[0][3] == "ostrozny", at.wywolania       # ed_a własny, ed_b zajęty przez b
    p = pr_plan(s)
    assert p["zrobione_t"] and p["nowy_spot"] == "ed_c", p
    assert n.stan["postacie"]["a"]["spot"]["mapa"] == "ed_c" and n.stan["postacie"]["a"]["faza"] == "POWROT"
    assert "gracz Tuhandryt" in [x for x in kody_dz(n) if x["akcja"] == "przerwa_spot"][0]["powod"]


def test_spot_gracz_ponizej_progu_albo_stary_albo_zmien_spot_nie_zostaje_na_miejscu():
    przypadki = [
        ({**PR60, "zmien_spot": "jesli_gracz"}, [(50, "Tuhandryt"), (40, "Tuhandryt"), (30, "Tuhandryt")]),            # 3 < próg 4
        ({**PR60, "zmien_spot": "jesli_gracz"}, [(130, "Tuhandryt"), (125, "Tuhandryt"), (120, "Tuhandryt"), (110, "Tuhandryt")]),   # starsze niż 60 min
        ({**PR60, "zmien_spot": "nie"}, [(50, "Tuhandryt"), (45, "Tuhandryt"), (40, "Tuhandryt"), (35, "Tuhandryt")]),   # gracz jest, ale zmien_spot: nie
    ]
    for przerwa, log in przypadki:
        s = _swiat_spot(przerwa, log_gracza=log)
        n, at = _przerwa_do_powrotu(s)
        n.tick()
        rs = _spot_wywolania(at)
        assert len(rs) == 1 and rs[0][2] is None and rs[0][3] is None, (przerwa, log, at.wywolania)         # bez MAPA/TRYB = ostatnia mapa i tryb
        assert pr_plan(s)["zrobione_t"] and "nowy_spot" not in pr_plan(s)


def test_spot_gracz_z_pola_planu_wystarcza_bez_logu():
    s = _swiat_spot({**PR60, "zmien_spot": "jesli_gracz", "gracz": "Tuhandryt"})
    n, at = _przerwa_do_powrotu(s)
    n.tick()
    rs = _spot_wywolania(at)
    assert rs and rs[0][2] == "ed_c", at.wywolania


def test_spot_brak_alternatywy_zostaje_na_starym_i_mowi_dlaczego():
    s = _swiat_spot({**PR60, "zmien_spot": "jesli_gracz", "gracz": "Tuhandryt"}, lina=False)     # ed_c wymaga liny, ed_b zajęty
    n, at = _przerwa_do_powrotu(s)
    n.tick()
    rs = _spot_wywolania(at)
    assert len(rs) == 1 and rs[0][2] is None, at.wywolania
    assert "brak wolnego spotu" in [x for x in kody_dz(n) if x["akcja"] == "przerwa_spot"][0]["powod"]
    assert pr_plan(s)["zrobione_t"]


def test_spot_przypiety_nigdy_sie_nie_zmienia():
    s = _swiat_spot({**PR60, "zmien_spot": "jesli_gracz", "gracz": "Tuhandryt"}, plan_dod={"spot_przypiety": True, "spot_przypiety_powod": "Karol 23.10"})
    n, at = _przerwa_do_powrotu(s)
    n.tick()
    rs = _spot_wywolania(at)
    assert len(rs) == 1 and rs[0][2] is None and "przypięty" in [x for x in kody_dz(n) if x["akcja"] == "przerwa_spot"][0]["powod"], at.wywolania


def test_spot_zajeta_jaskinia_przez_innego_bota_przenosi_nawet_bez_gracza():
    s = _swiat_spot({**PR60, "zmien_spot": "nie"}, b_na="ed_a")          # b zajął jaskinię a podczas przerwy
    n, at = _przerwa_do_powrotu(s)
    n.tick()
    rs = _spot_wywolania(at)
    assert len(rs) == 1 and rs[0][2] in ("ed_b", "ed_c"), at.wywolania
    assert "zajęta przez innego bota" in [x for x in kody_dz(n) if x["akcja"] == "przerwa_spot"][0]["powod"]


def test_refill_spot_nieudany_ponawia_i_po_trzech_razach_eskaluje():
    s = _swiat_spot({**PR60, "zmien_spot": "nie"})
    n, at = _przerwa_do_powrotu(s)
    at.wyniki["refill_spot"] = (False, "refill.sh: bot działa")
    for _ in range(3):
        n.tick()
        s.zegar.dalej(minutes=3)
    assert at.nazwy().count("refill_spot") == 3 and not pr_plan(s).get("zrobione_t"), at.wywolania
    n.tick()
    assert any(x["akcja"] == "eskaluj" and "refill.sh --spot nieudany" in x["powod"] for x in kody_dz(n)), kody_dz(n)


# ============================================================ (f) wyłącznik
def test_wylacznik_env_i_konfig_gasza_nowe_przerwy_ale_nie_trwajaca():
    for jak in ("env", "konfig"):
        s = swiat(PR60)
        if jak == "konfig":
            (s.k / "instancje" / "_wspolne" / "nadzor_konfig.json").write_text(json.dumps({"przerwy": False}))
        else:
            os.environ["NADZOR_PRZERWY"] = "0"
        try:
            n, at = nadz(s, "zywo")
            marker(s)
            n.tick()
            assert "wyloguj" not in at.nazwy() and "wylogowano_t" not in pr_plan(s), (jak, at.wywolania)
            assert not PR.wlaczone(korzen=s.k)
            # przerwa już trwająca kończy się powrotem mimo wyłącznika (postać nie zostaje offline na zawsze)
            s2 = swiat({**PR60, "wylogowano_t": "2026-10-21 10:00:00", "do_t": "2026-10-21 11:00:00"}, offline=True)
            if jak == "konfig":
                (s2.k / "instancje" / "_wspolne" / "nadzor_konfig.json").write_text(json.dumps({"przerwy": False}))
            n2, at2 = nadz(s2, "zywo")
            n2.tick()
            assert at2.nazwy() == ["sesja_start"], (jak, at2.wywolania)
            # przerwa `teraz` offline także wyłączona
            s3 = swiat({**PR60, "kiedy": "teraz"}, offline=True)
            if jak == "konfig":
                (s3.k / "instancje" / "_wspolne" / "nadzor_konfig.json").write_text(json.dumps({"przerwy": False}))
            n3, at3 = nadz(s3, "zywo")
            n3.tick()
            assert "wylogowano_t" not in pr_plan(s3)
        finally:
            os.environ.pop("NADZOR_PRZERWY", None)
    assert PR.wlaczone(korzen=swiat(None).k) and PR.wlaczone({"przerwy": True}) and not PR.wlaczone({"przerwy": False})


# ============================================================ (g) cień nic nie zapisuje
def test_cien_i_raz_nie_zapisuja_planu_ani_stanu_i_nic_nie_uruchamiaja():
    for przerwa, offline, bot in ((PR60, False, False), ({**PR60, "kiedy": "teraz"}, True, False), ({**PR60, "kiedy": "teraz"}, False, True),
                                  ({**PR60, "wylogowano_t": "2026-10-21 10:00:00", "do_t": "2026-10-21 11:00:00"}, True, False)):
        s = swiat(przerwa, offline=offline, bot=bot)
        marker(s) if not offline and not bot else None
        przed = stan_bajty(s)
        n, at = nadz(s, "cien", zapis=False)                    # jak `nadzor.py cien --raz`
        n.tick()
        assert at.wywolania == [] and n.wykonawca.wywolania == [], (przerwa, at.wywolania, n.wykonawca.wywolania)
        assert stan_bajty(s) == przed, (przerwa, [k for k in przed if stan_bajty(s).get(k) != przed[k]])
        # cień z zapisem dziennika: plan nadal nietknięty
        n2, at2 = nadz(s, "cien", zapis=True)
        n2.tick()
        assert s.plan_bajty() == przed["instancje/_wspolne/plan_postaci.json"] and at2.wywolania == [] and n2.wykonawca.wywolania == [], przerwa


def test_kod_decyzji_przerwy_zaczyna_sie_od_plan_czyli_zywo_tylko_przy_naprawach():
    s = swiat(PR60)
    n, at = nadz(s, "naprawy")
    marker(s)
    n.tick()
    d = [x for x in kody_dz(n) if x["akcja"] == "wyloguj"]
    assert d and d[0]["wynik"] == "ok", kody_dz(n)
    sk = [x for x in n.dziennik.ostatnie if x.get("akcja") == "wyloguj"]
    assert at.nazwy().count("wyloguj") == 1 and n.wykonawca.wywolania == [], (at.wywolania, n.wykonawca.wywolania)
    assert N.D("a", "wyloguj", "x", "plan-przerwa-wyloguj")["kod"].startswith("plan-")


# ============================================================ (h) bez wpisu `przerwa` jak dotąd
def _jak_dotad(n, s, at, kroki=8):
    """Kilka ticków w zmiennych stanach; zwraca (wywołania, dziennik (akcja, wynik, powód))."""
    wyn = []
    for _ in range(kroki):
        n.tick()
        s.zegar.dalej(minutes=4)
    return list(at.wywolania), [(x["akcja"], x["wynik"], x["powod"]) for x in n.dziennik.ostatnie]


def _stany_porownawcze():
    """Fabryki światów: w mieście ze STOP i znacznikiem refillu, w mieście bez znacznika, bot w grze, offline z zadaniem z grafiku."""
    def miasto_znacznik(pr):
        s = swiat(pr)
        marker(s)
        return s

    def miasto(pr):
        return swiat(pr)

    def gra(pr):
        s = swiat(pr, bot=True)
        s.log("a", [(s.zegar.t - timedelta(seconds=90), "Cel Troll zabity na (1, 2, 8).")])
        return s

    def offline(pr):
        s = swiat(pr, offline=True)
        s.zegar.t = datetime(2026, 10, 21, 10, 5, 0)
        return s

    def zostaje(pr):
        return swiat(pr, plan_dod={"zostan_w_depo": True, "zostan_w_depo_powod": "t"})
    return {"miasto+znacznik": miasto_znacznik, "miasto": miasto, "gra": gra, "offline": offline, "zostaje_w_depo": zostaje}


def test_bez_wpisu_przerwa_zachowanie_identyczne_jak_dotad_wszystkie_tryby():
    """Porównanie: świat BEZ pola `przerwa` kontra świat z polem `przerwa` w stanach, w których nie powinno działać (zrobiona, wyłącznik) oraz kontra świat bez pola
    (ten sam scenariusz, znacznik refillu leży w katalogu, ale plan go nie obejmuje)."""
    for tryb in ("cien", "naprawy", "zywo"):
        for nazwa, fab in _stany_porownawcze().items():
            sa = fab(None)
            na, ata = nadz(sa, tryb)
            ref = _jak_dotad(na, sa, ata)
            # (1) przerwa zrobiona = jak bez przerwy
            sb = fab({**PR60, "zrobione_t": "2026-10-20 10:00:00"})
            nb, atb = nadz(sb, tryb)
            assert _jak_dotad(nb, sb, atb) == ref, (tryb, nazwa, "zrobiona")
            # (2) przerwa uzbrojona, ale wyłącznik: jak bez przerwy
            os.environ["NADZOR_PRZERWY"] = "0"
            try:
                sc = fab(PR60)
                nc, atc = nadz(sc, tryb)
                assert _jak_dotad(nc, sc, atc) == ref, (tryb, nazwa, "wyłącznik")
            finally:
                os.environ.pop("NADZOR_PRZERWY", None)
            # (3) plan z błędnym wpisem przerwy: błąd planu, ale postać jak bez przerwy
            sd = fab({"min": 0})
            nd, atd = nadz(sd, tryb)
            wd = _jak_dotad(nd, sd, atd)
            assert wd[0] == ref[0], (tryb, nazwa, "zły wpis", wd[0], ref[0])
            # (4) nic z tego nie ma kodu plan-przerwa
            assert not [k for k in kody(nd) + kody(na) if k.startswith("plan-przerwa")], nazwa


def test_bez_wpisu_zero_decyzji_plan_przerwa_i_zero_zapisow_do_planu():
    for nazwa, fab in _stany_porownawcze().items():
        s = fab(None)
        przed = s.plan_bajty()
        n, at = nadz(s, "zywo")
        for _ in range(6):
            n.tick()
            s.zegar.dalej(minutes=5)
        assert s.plan_bajty() == przed, nazwa
        assert not [x for x in at.wywolania if x[0] in ("refill_spot",)], (nazwa, at.wywolania)
        assert "przerwa" not in n.podsumowanie()["postacie"]["a"]["plan"] or n.podsumowanie()["postacie"]["a"]["plan"]["przerwa"] == ""


# ============================================================ (i) refill_auto.py i refill.sh
class _Rc:
    returncode, stdout, stderr = 0, "refill ruszył", ""


def _czekaj(stan_dir, **kw):
    wyw = []
    t = [0.0]
    stare = {}
    kod = RA.czekaj(stan_dir, procesy=lambda *a, **k: [], uruchom=lambda *a, **k: (wyw.append((a, k)), _Rc())[1],
                    spij=lambda s_: t.__setitem__(0, t[0] + s_), zegar=lambda: t[0], **kw)
    return kod, [x for x in wyw if "refill.sh" in str(x[0])]


def _inst(tmp, plan):
    inst = Path(tmp) / "instancje"
    (inst / "_wspolne").mkdir(parents=True)
    (inst / "x").mkdir()
    (inst / "_wspolne" / "plan_postaci.json").write_text(json.dumps({"postacie": {"x": plan}}))
    return inst / "x"


def test_refill_auto_z_przerwa_ustawia_refill_bez_wyjscia_a_bez_przerwy_nie():
    with tempfile.TemporaryDirectory() as tmp:
        st = _inst(tmp, {"kroki": [], "przerwa": dict(PR60)})
        kod, w = _czekaj(st)
        assert kod == 0 and len(w) == 1 and w[0][1]["env"]["REFILL_BEZ_WYJSCIA"] == "1", w
        assert "przerwa postaci" in RA.czytaj_stan(st)["powod"], RA.czytaj_stan(st)
    with tempfile.TemporaryDirectory() as tmp:
        st = _inst(tmp, {"kroki": []})
        kod, w = _czekaj(st)
        assert kod == 0 and len(w) == 1 and "env" not in w[0][1], w                      # dokładnie jak dotąd
    with tempfile.TemporaryDirectory() as tmp:
        st = _inst(tmp, {"kroki": [], "przerwa": {**PR60, "zrobione_t": "2026-10-20 10:00:00"}})
        assert "env" not in _czekaj(st)[1][0][1]
    with tempfile.TemporaryDirectory() as tmp:
        st = _inst(tmp, {"kroki": [], "przerwa": {**PR60, "wylogowano_t": "2026-10-21 10:00:00", "do_t": "2026-10-21 11:00:00"}})
        assert "env" not in _czekaj(st)[1][0][1]                                          # już wylogowana: zwykły refill
    with tempfile.TemporaryDirectory() as tmp:
        st = _inst(tmp, {"kroki": [], "przerwa": {"min": 0}})
        assert "env" not in _czekaj(st)[1][0][1]                                          # zły wpis = brak przerwy
    with tempfile.TemporaryDirectory() as tmp:
        st = _inst(tmp, {"kroki": [], "przerwa": dict(PR60)})
        os.environ["NADZOR_PRZERWY"] = "0"
        try:
            assert "env" not in _czekaj(st)[1][0][1]
        finally:
            os.environ.pop("NADZOR_PRZERWY")
        (st.parent / "_wspolne" / "nadzor_konfig.json").write_text(json.dumps({"przerwy": False}))
        assert "env" not in _czekaj(st)[1][0][1]


def test_refill_auto_zostan_w_depo_ma_pierwszenstwo_przed_przerwa_i_cap_laczy_sie():
    with tempfile.TemporaryDirectory() as tmp:
        st = _inst(tmp, {"kroki": [], "zostan_w_depo": True, "zostan_w_depo_powod": "t", "przerwa": dict(PR60)})
        kod, w = _czekaj(st)
        assert kod == 0 and w == [] and RA.czytaj_stan(st)["stan"] == "pominiety"
    with tempfile.TemporaryDirectory() as tmp:
        st = _inst(tmp, {"kroki": [], "przerwa": dict(PR60)})
        (st / "wyprawa_stan.json").write_text(json.dumps({"aktywna": False, "wynik": "depo", "depo_start_powody": ["cap"], "zapis_wall": time.time() - 5}))
        kod, w = _czekaj(st)
        assert w and w[0][1]["env"]["REFILL_KROKI"] == RA.KROKI_CAP and w[0][1]["env"]["REFILL_BEZ_WYJSCIA"] == "1", w


def _piaskownica_refill(tmp, serwis_kod=0):
    """Katalog z refill.sh, instancja.py i atrapą serwis.sh (zapisuje STARTUJ i argumenty); praca refill.sh bez --tlo (bez gry, bez socketu)."""
    sand = Path(tmp) / "pomocnik"
    sand.mkdir()
    for f in ("refill.sh", "instancja.py"):
        shutil.copy(KORZEN / f, sand / f)
    (sand / "serwis.sh").write_text('#!/bin/bash\necho "STARTUJ=${STARTUJ:-} $*" >> "%s/wywolania.txt"\nexit %d\n' % (tmp, serwis_kod))
    (sand / "serwis.sh").chmod(0o755)
    bin_ = Path(tmp) / "bin"
    bin_.mkdir()
    (bin_ / "notify-send").write_text('#!/bin/bash\necho "$@" >> "%s/powiadomienia.txt"\n' % tmp)
    (bin_ / "notify-send").chmod(0o755)
    return sand, bin_


def _refill_sh(tmp, sand, bin_, **env):
    e = dict(os.environ, RETRONIC_ID="tstprz", PATH=f"{bin_}:{os.environ['PATH']}")
    for k in ("REFILL_KROKI", "REFILL_BEZ_WYJSCIA", "REFILL_TRYB"):
        e.pop(k, None)
    e.update(env)
    inst = sand / "instancje" / "tstprz"
    inst.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["bash", str(sand / "refill.sh")], env=e, capture_output=True, text=True, timeout=60, cwd=str(sand))
    w = Path(tmp) / "wywolania.txt"
    return r, (w.read_text() if w.exists() else ""), inst


def test_refill_sh_bez_wyjscia_kroki_startuja_znacznik_i_stop():
    with tempfile.TemporaryDirectory() as tmp:
        sand, bin_ = _piaskownica_refill(tmp)
        r, wyw, inst = _refill_sh(tmp, sand, bin_, REFILL_BEZ_WYJSCIA="1")
        assert r.returncode == 0 and "REFILL: OK" in r.stdout, (r.stdout, r.stderr)
        assert wyw.strip() == "STARTUJ=0 --kroki bank,depo,jedzenie,backpack,blanki --pomin-brakujace", wyw           # bez wyjścia, bez startu bota
        assert (inst / "STOP").exists() and float((inst / PR.MARKER_REFILL).read_text().split()[0]) > time.time() - 60
        assert PR.marker_refill(inst, time.time()) is not None
    with tempfile.TemporaryDirectory() as tmp:
        sand, bin_ = _piaskownica_refill(tmp)
        r, wyw, inst = _refill_sh(tmp, sand, bin_, REFILL_BEZ_WYJSCIA="1", REFILL_KROKI="bank,cap,wyjscie")         # powrót po samym cap
        assert wyw.strip() == "STARTUJ=0 --kroki bank,cap --pomin-brakujace" and (inst / PR.MARKER_REFILL).exists(), wyw
    with tempfile.TemporaryDirectory() as tmp:
        sand, bin_ = _piaskownica_refill(tmp)
        r, wyw, inst = _refill_sh(tmp, sand, bin_, REFILL_BEZ_WYJSCIA="1", REFILL_KROKI="wyjscie")                   # nic do kupienia: serwis NIE wołany
        assert r.returncode == 0 and wyw == "" and (inst / PR.MARKER_REFILL).exists() and (inst / "STOP").exists(), (r.stdout, wyw)


def test_refill_sh_bez_zmiennej_dziala_jak_dotad_i_porazka_nie_zostawia_znacznika():
    with tempfile.TemporaryDirectory() as tmp:
        sand, bin_ = _piaskownica_refill(tmp)
        r, wyw, inst = _refill_sh(tmp, sand, bin_)
        assert r.returncode == 0 and wyw.strip() == "STARTUJ=1 --kroki bank,depo,jedzenie,backpack,blanki,wyjscie --pomin-brakujace", wyw
        assert not (inst / "STOP").exists() and not (inst / PR.MARKER_REFILL).exists()
    with tempfile.TemporaryDirectory() as tmp:
        sand, bin_ = _piaskownica_refill(tmp, serwis_kod=3)
        inst = sand / "instancje" / "tstprz"
        inst.mkdir(parents=True)
        (inst / PR.MARKER_REFILL).write_text("1\n")                                 # stary znacznik znika na starcie nowego refillu
        r, wyw, inst = _refill_sh(tmp, sand, bin_, REFILL_BEZ_WYJSCIA="1")
        assert r.returncode == 3 and "REFILL: BLAD" in r.stdout and not (inst / PR.MARKER_REFILL).exists(), (r.stdout, r.returncode)


def test_refill_sh_skladnia_bash():
    assert subprocess.run(["bash", "-n", str(KORZEN / "refill.sh")]).returncode == 0


def test_marker_refill_wiek_i_format():
    with tempfile.TemporaryDirectory() as tmp:
        st = Path(tmp)
        assert PR.marker_refill(st, 1000.0) is None
        (st / PR.MARKER_REFILL).write_text("900\n")
        assert PR.marker_refill(st, 1000.0) == 900.0
        assert PR.marker_refill(st, 900.0 + PR.MARKER_WAZNY_S + 1) is None
        assert PR.marker_refill(st, 800.0) is None                                  # z przyszłości = nieważny
        (st / PR.MARKER_REFILL).write_text("abc\n")
        assert PR.marker_refill(st, 1000.0) is None


def test_gracze_w_logu_prog_okno_i_wlasne_nicki():
    with tempfile.TemporaryDirectory() as tmp:
        st = Path(tmp) / "x"
        (st / "logi").mkdir(parents=True)
        ref = datetime(2026, 10, 21, 12, 0, 0)

        def linie(*pary):
            return "".join(f"{(ref - timedelta(minutes=m)):%H:%M:%S} Gracz w pobliżu: {n} ({d} pól), gram dalej.\n" for m, n, d in pary) + "12:00:00 inna linia\n"
        (st / "logi" / "mozg-stdout-1021-1000.log").write_text(linie((55, "Tuhandryt", 3), (40, "Tuhandryt", 5), (30, "Tuhandryt", 2), (10, "Tuhandryt", 7), (5, "Kto Inny", 3)))
        assert PR.gracze_w_logu(st, ref) == "Tuhandryt"
        assert PR.gracze_w_logu(st, ref, wlasne={"tuhandryt"}) == ""                    # własna postać nie liczy się jako gracz
        assert PR.gracze_w_logu(st, ref, prog=5) == ""
        assert PR.gracze_w_logu(st, ref, okno_min=20) == ""                             # w oknie 20 min tylko 1 wpis
        (st / "logi" / "mozg-stdout-1021-1100.log").write_text(linie((5, "Nowy", 3)))   # liczy się najnowszy log bota
        os.utime(st / "logi" / "mozg-stdout-1021-1100.log", (time.time() + 10, time.time() + 10))
        assert PR.gracze_w_logu(st, ref) == ""
        assert PR.gracze_w_logu(Path(tmp) / "brak", ref) == ""


def test_odczyt_lekki_dla_refill_auto():
    with tempfile.TemporaryDirectory() as tmp:
        st = _inst(tmp, {"kroki": [], "przerwa": dict(PR60)})
        assert PR.odczyt(st).min == 60
        (st.parent / "_wspolne" / "plan_postaci.json").write_text("{zepsute")
        assert PR.odczyt(st) is None
        (st.parent / "_wspolne" / "plan_postaci.json").write_text(json.dumps({"postacie": {"x": {"przerwa": "tak"}}}))
        assert PR.odczyt(st) is None


def test_plan_przerwa_zapisz_atomowo_warunek_i_usuniecie_klucza():
    s = TP.SwiatP(("a",), {"a": {"kroki": [], "spot_przypiety": True, "przerwa": dict(PR60)}})
    assert P.przerwa_zapisz(s.k, "a", {"wylogowano_t": "2026-10-21 11:00:00", "do_t": "2026-10-21 12:00:00"}, warunek=lambda w: not w.get("zrobione_t"))
    assert not P.przerwa_zapisz(s.k, "a", {"x": 1}, warunek=lambda w: False)
    assert P.przerwa_zapisz(s.k, "a", {"wylogowano_t": None, "do_t": None})
    w = s.plan_odczyt()["a"]
    assert "wylogowano_t" not in w["przerwa"] and w["spot_przypiety"] is True and w["przerwa"]["min"] == 60
    assert not P.przerwa_zapisz(s.k, "nie_ma", {"x": 1})
    assert not list((s.k / "instancje" / "_wspolne").glob("*.tmp"))


if __name__ == "__main__":
    ok = zle = 0
    t0 = time.time()
    for nazwa, f in list(globals().items()):
        if nazwa.startswith("test_") and callable(f):
            t1 = time.time()
            try:
                f()
                ok += 1
                print("ok  ", nazwa, f"({time.time() - t1:.1f}s)")
            except Exception as e:      # noqa: BLE001
                import traceback
                zle += 1
                print("BŁĄD", nazwa, repr(e)[:700])
                traceback.print_exc()
    print(f"{ok}/{ok + zle} testów zielonych ({time.time() - t0:.0f}s)")
    sys.exit(1 if zle else 0)
