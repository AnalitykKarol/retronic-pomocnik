#!/usr/bin/env python3
"""Domyślne „zostań w depo i wyloguj” (25.10, Karol: „ma być jako default, że postacie wracają do miasta do depo i robią loga i czekają na mnie”).
Mechanizm: klucz NAJWYŻSZEGO poziomu planu `domyslne: {"wlaczone": true}` (zostan_depo.domyslne) daje wszystkim postaciom (także bez wpisu) pola
`zostan_w_depo` i `wyloguj_w_depo`, gdy wpis postaci ich nie ma; pole postaci wygrywa. WŁĄCZNIK domyślnie WYŁĄCZONY (brak klucza = zachowanie sprzed 25.10).
Offline: katalogi tymczasowe i atrapy z testy/test_plan_2bp.py / test_plan_postaci.py / test_nadzor.py; nic nie dotyka gry, botów, sesji ani timera.
Dowodzi: (a) wyłączone / brak klucza / zły kształt = jak dziś; (b) włączone: postać w depo ze STOP jest wylogowana, także bez wpisu w planie, a drugą
wylogowuje dopiero kolejny przebieg po odstępie; (c) nadpisanie per postać (zostan_w_depo false, wyloguj_w_depo false, po_refillach); (d) bramki: STOP_RECZNY,
brak dowodu depo, serwis, refill (nowe `refill_trwa`), powrót po samym cap; (e) refill_auto honoruje domyślne; (f) walidacja, `opis_planu`, `pokaz`, zapis planu
zachowuje klucz `domyslne`.
Uruchomienie: python3 -I testy/test_domyslnie_depo.py"""
import contextlib
import io
import json
import os
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["RETRONIC_TESTY"] = "1"
os.environ["RETRONIC_ID"] = "tstdomdepo"
KORZEN = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
sys.path.insert(0, str(KORZEN / "testy"))
import nadzor as N  # noqa: E402,F401
import plan_postaci as P  # noqa: E402
import refill_auto as RA  # noqa: E402
import test_plan_2bp as B  # noqa: E402
import test_plan_postaci as TP  # noqa: E402
import zostan_depo as ZD  # noqa: E402

DOM = {"wlaczone": True}


def zapisz_plan(s, postacie, domyslne=None, jako_tekst=None):
    """Nadpisuje plik planu świata testu (pełny kształt, z kluczem najwyższego poziomu `domyslne`)."""
    d = {"postacie": postacie}
    if domyslne is not None:
        d["domyslne"] = domyslne
    p = s.k / "instancje" / "_wspolne" / "plan_postaci.json"
    p.write_text(jako_tekst if jako_tekst is not None else json.dumps(d, ensure_ascii=False, indent=1))


def swiat(ids=("a",), domyslne=DOM, plan_dod=None, tryb="zywo", stop_od_start=("1100",), wpisy=None):
    """Świat jak w test_plan_2bp.swiat (postać w depo, STOP, bez bota, dowód depo), plan z `domyslne`; `wpisy` = pełny słownik „postacie” zamiast domyślnego."""
    s, n, at = B.swiat(ids, plan_dod=plan_dod, tryb=tryb, stop_od_start=stop_od_start)
    s.refill_proc = {}
    s.procesy_refillu = lambda id_: s.refill_proc.get(id_, [])          # atrapa Zrodla.procesy_refillu (refill.sh / czekacz / serwis.sh)
    zapisz_plan(s, wpisy if wpisy is not None else {i: {"kroki": [], **(plan_dod or {})} for i in ids}, domyslne)
    return s, n, at


def kody(n, id_="a"):
    return B.kody(n, id_)


def akcje(n, id_="a"):
    return [x["akcja"] for x in kody(n, id_)]


# ============================================================ (a) wyłączone = jak dziś
def test_a_brak_klucza_wylaczone_i_zly_ksztalt_to_zachowanie_jak_dzis():
    for domyslne in (None, {"wlaczone": False}, {"zostan_w_depo": True, "wyloguj_w_depo": True}, "tak", {"wlaczone": "tak"}, {"wlaczone": 1}):
        for tryb in ("zywo", "naprawy"):
            s, n, at = swiat(domyslne=domyslne, tryb=tryb)
            s0, n0, at0 = B.swiat(plan_dod=None, tryb=tryb, stop_od_start=("1100",))        # świat bez klucza, kopia „sprzed zmiany”
            for _ in range(4):
                n.tick(); n0.tick()
                s.zegar.dalej(minutes=5); s0.zegar.dalej(minutes=5)
            assert at.nazwy() == at0.nazwy(), (domyslne, tryb, at.wywolania, at0.wywolania)
            assert "wyloguj" not in at.nazwy() and not n.post("a").get("zostan_depo_od"), (domyslne, at.wywolania)
            # zły kształt = co najwyżej dodatkowy wpis „plan” (błąd planu) w dzienniku, reszta bez zmian
            assert [a for a in akcje(n) if a != "plan"] == akcje(n0), (domyslne, kody(n), kody(n0))


def test_a_wylaczone_refill_auto_dziala_jak_dzis():
    with tempfile.TemporaryDirectory() as tmp:
        inst = Path(tmp) / "instancje"
        (inst / "_wspolne").mkdir(parents=True)
        (inst / "x").mkdir()
        for dom in (None, {"wlaczone": False}):
            (inst / "_wspolne" / "plan_postaci.json").write_text(json.dumps({"postacie": {"x": {"kroki": []}}, **({"domyslne": dom} if dom else {})}))
            assert RA.zostaje_w_depo(inst / "x") is None, dom


# ============================================================ (b) włączone: zostaje i jest wylogowana, pojedynczo
def test_b_wlaczone_postac_w_depo_ze_stop_jest_wylogowana_na_zywo_i_w_naprawach():
    for tryb in ("zywo", "naprawy"):
        s, n, at = swiat(tryb=tryb)
        n.tick()
        assert at.nazwy() == ["wyloguj"], (tryb, at.wywolania)
        d = [x for x in kody(n) if x["akcja"] == "wyloguj"]
        assert d and d[0]["wynik"] == "ok" and "domyślnie" in d[0]["powod"], kody(n)
        assert n.post("a").get("zostan_depo_od")


def test_b_cien_tylko_zapis_zrobilbym():
    s, n, at = swiat(tryb="cien")
    n.tick()
    assert at.wywolania == [], at.wywolania
    assert [x for x in n.dziennik.ostatnie if x.get("akcja") == "wyloguj" and x.get("wynik") == "cień"], n.dziennik.ostatnie


def test_b_postac_bez_wpisu_w_planie_tez_dostaje_domyslne():
    s, n, at = swiat(wpisy={"inna": {"kroki": []}})
    assert "a" not in P.wczytaj(s.k).postacie
    n.tick()
    assert at.nazwy() == ["wyloguj"], at.wywolania


def test_b_po_wylogowaniu_brak_relogu_i_startu_sesji_przez_godziny():
    s, n, at = swiat()
    n.tick()
    assert at.nazwy() == ["wyloguj"], at.wywolania
    assert not s.inst["a"]["sesja"]
    for _ in range(40):
        s.zegar.dalej(minutes=5)
        n.tick()
    assert at.nazwy() == ["wyloguj"], at.wywolania
    assert kody(n)[-1]["powod"].startswith("offline, ostatnio w depo ze STOP"), kody(n)[-1]


def test_b_wylogowania_pojedynczo_z_odstepem_miedzy_postaciami():
    s, n, at = swiat(("a", "b"))
    n.tick()
    assert at.nazwy() == ["wyloguj"] and at.wywolania[0][1] == "a", at.wywolania          # jedna na przebieg
    s.zegar.dalej(minutes=5)
    n.tick()
    assert at.nazwy() == ["wyloguj"], ("b przed upływem odstępu", at.wywolania)
    s.zegar.dalej(minutes=3)
    n.tick()
    assert [w[1] for w in at.wywolania if w[0] == "wyloguj"] == ["a", "b"], at.wywolania
    t = [c[0] for c in at.czasy if c[1] == "wyloguj"]
    assert (t[1] - t[0]) >= timedelta(minutes=7), t


def test_b_stan_w_podsumowaniu_to_domyslne_i_uzbrojone():
    s, n, at = swiat()
    pod = n.podsumowanie()["postacie"]["a"]["plan"]
    assert pod["zostan_w_depo"] is True and pod["wyloguj_w_depo"] is True and pod["zostan_domyslne"] is True, pod


# ============================================================ (c) nadpisanie per postać
def test_c_wpis_postaci_zostan_w_depo_false_wygrywa_z_domyslnym():
    s, n, at = swiat(plan_dod={"zostan_w_depo": False})
    s0, n0, at0 = B.swiat(plan_dod=None, stop_od_start=("1100",))
    for _ in range(4):
        n.tick(); n0.tick()
        s.zegar.dalej(minutes=5); s0.zegar.dalej(minutes=5)
    assert "wyloguj" not in at.nazwy() and at.nazwy() == at0.nazwy(), at.wywolania
    assert akcje(n) == akcje(n0), (kody(n), kody(n0))


def test_c_wyloguj_w_depo_false_postac_zostaje_ale_nie_jest_wylogowana():
    s, n, at = swiat(plan_dod={"wyloguj_w_depo": False})
    for _ in range(14):
        n.tick()
        s.zegar.dalej(minutes=5)
    assert at.wywolania == [], at.wywolania
    assert kody(n) and all(x["akcja"] == "czekaj" for x in kody(n)), kody(n)


def test_c_po_refillach_we_wpisie_wygrywa_i_przed_refillem_nic_sie_nie_dzieje():
    nowe = {"zostan_w_depo_po_refillach": 1, "zostan_w_depo_od": B.OD, "zostan_w_depo_powod": "Karol 24.10"}
    s, n, at = swiat(plan_dod=nowe, stop_od_start=("1000",))
    s0, n0, at0 = B.swiat(plan_dod=nowe, stop_od_start=("1000",))                     # ten sam wpis bez „domyslne”
    for _ in range(4):
        n.tick(); n0.tick()
        s.zegar.dalej(minutes=5); s0.zegar.dalej(minutes=5)
    assert "wyloguj" not in at.nazwy() and not n.post("a").get("zostan_depo_od"), at.wywolania
    assert at.nazwy() == at0.nazwy(), (at.wywolania, at0.wywolania)                    # przed pierwszym refillem: dokładnie jak dziś
    s, n, at = swiat(plan_dod=nowe, stop_od_start=("1100",))
    B.refille(s, "a", 25)
    n.tick()
    assert at.nazwy() == ["wyloguj"], at.wywolania                                       # po refillu: wyloguj_w_depo także z wpisu


def test_c_wlasny_powod_z_domyslnych_trafia_do_dziennika():
    s, n, at = swiat(domyslne={"wlaczone": True, "zostan_w_depo_powod": "Karol 25.10: czekam na niego"})
    n.tick()
    assert at.nazwy() == ["wyloguj"] and "Karol 25.10" in [x for x in kody(n) if x["akcja"] == "wyloguj"][0]["powod"], kody(n)


def test_c_domyslne_zostan_false_wyloguj_true_nic_nie_robi_bez_wpisu():
    s, n, at = swiat(domyslne={"wlaczone": True, "zostan_w_depo": False})
    s0, n0, at0 = B.swiat(plan_dod=None, stop_od_start=("1100",))
    for _ in range(3):
        n.tick(); n0.tick()
        s.zegar.dalej(minutes=5); s0.zegar.dalej(minutes=5)
    assert "wyloguj" not in at.nazwy() and at.nazwy() == at0.nazwy(), at.wywolania


# ============================================================ (d) bramki Karola
def test_d_stop_reczny_pauza_hold_nadzor_false_zero_wylogowania():
    s, n, at = swiat()
    s.plik("a", "STOP_RECZNY").touch()
    n.tick()
    s.plik("a", "STOP_RECZNY").unlink()
    (s.k / "instancje" / "_wspolne" / "NADZOR_PAUZA").touch()
    s.zegar.dalej(minutes=5)
    n.tick()
    (s.k / "instancje" / "_wspolne" / "NADZOR_PAUZA").unlink()
    n.post("a")["hold"] = {"powod": "PK", "powiadomiono": True}
    s.zegar.dalej(minutes=5)
    n.tick()
    n.post("a").pop("hold")
    (s.k / "instancje" / "a" / "profil.json").write_text(json.dumps({"postac": "A", "nadzor": False}))
    s.zegar.dalej(minutes=5)
    n.tick()
    assert at.wywolania == [], at.wywolania


def test_d_stop_reczny_zostaje_nietkniety_przy_innej_postaci_wylogowanej():
    s, n, at = swiat(("a", "b"))
    s.plik("a", "STOP_RECZNY").touch()
    for _ in range(4):
        n.tick()
        s.zegar.dalej(minutes=8)
    assert [w[1] for w in at.wywolania if w[0] == "wyloguj"] == ["b"], at.wywolania


def _bez_dowodu_w_logu(s):
    (s.plik("a", "logi") / "mozg-stdout-1021-1100.log").unlink()
    s.log("a", [(s.zegar.t - timedelta(minutes=40), "Mózg: tryb skrypt, postać A, trasa x"), (s.zegar.t - timedelta(minutes=29), "Zatrzymano (plik STOP).")],
          nazwa="mozg-stdout-1021-1100.log")                                # log bez „DEPO osiągnięte”


def test_d_brak_dowodu_depo_zero_wylogowania():
    s, n, at = swiat()
    s.inst["a"]["panel"]["w_depo"] = False
    _bez_dowodu_w_logu(s)
    s0, n0, at0 = B.swiat(plan_dod=None, stop_od_start=("1100",))
    s0.inst["a"]["panel"]["w_depo"] = False
    _bez_dowodu_w_logu(s0)
    for _ in range(4):
        n.tick(); n0.tick()
        s.zegar.dalej(minutes=5); s0.zegar.dalej(minutes=5)
    assert "wyloguj" not in at.nazwy() and at.nazwy() == at0.nazwy(), at.wywolania        # bez dowodu depo: dokładnie jak bez domyślnych
    assert not n.post("a").get("zostan_depo_od")


def test_d_dowod_depo_z_panelu_wystarcza_bez_linii_w_logu():
    s, n, at = swiat()
    s.inst["a"]["panel"]["w_depo"] = True
    _bez_dowodu_w_logu(s)
    n.tick()
    assert at.nazwy() == ["wyloguj"], at.wywolania


def test_d_serwis_odklada_wylogowanie_do_konca():
    s, n, at = swiat()
    s.inst["a"]["panel"]["serwis_dziala"] = True
    for _ in range(3):
        n.tick()
        s.zegar.dalej(minutes=5)
    assert "wyloguj" not in at.nazwy(), at.wywolania
    s.inst["a"]["panel"].pop("serwis_dziala")
    n.tick()
    assert at.nazwy() == ["wyloguj"], at.wywolania


def test_d_refill_w_toku_odklada_wylogowanie_do_konca_refillu():
    for jaki in ("refill.sh", "czekacz auto-refillu", "serwis.sh"):
        s, n, at = swiat()
        s.refill_proc["a"] = [4242]                                          # procesy_refillu: refill.sh / refill_auto.py czekaj / serwis.sh tej instancji
        for _ in range(3):
            n.tick()
            s.zegar.dalej(minutes=5)
        assert "wyloguj" not in at.nazwy(), (jaki, at.wywolania)
        assert any(x["akcja"] == "czekaj" and "refill" in x["powod"].lower() or "serwis" in x["powod"].lower() for x in kody(n)), kody(n)
        s.refill_proc["a"] = []
        n.tick()
        assert at.nazwy() == ["wyloguj"], (jaki, at.wywolania)


def test_d_brak_metody_procesy_refillu_w_zrodle_nie_psuje_nadzorcy():
    s, n, at = swiat()
    del s.procesy_refillu                                                    # atrapa starego kształtu (bez metody) -> refill_trwa = False
    n.tick()
    assert at.nazwy() == ["wyloguj"], at.wywolania


def test_d_wyprawa_tylko_po_cap_nie_zatrzymuje_w_depo_i_nie_wylogowuje():
    def wyprawa(s, powody):
        s.plik("a", "wyprawa_stan.json").write_text(json.dumps({"depo_start_powody": powody, "aktywna": False, "zapis_wall": s.zegar.t.timestamp() - 600}))
    s, n, at = swiat()
    wyprawa(s, ["cap"])
    s0, n0, at0 = B.swiat(plan_dod=None, stop_od_start=("1100",))
    for _ in range(3):
        n.tick(); n0.tick()
        s.zegar.dalej(minutes=5); s0.zegar.dalej(minutes=5)
    assert "wyloguj" not in at.nazwy() and at.nazwy() == at0.nazwy(), at.wywolania        # sam cap = bank + powrót na spot, jak dziś
    s, n, at = swiat()
    wyprawa(s, ["cap", "blanki"])
    n.tick()
    assert at.nazwy() == ["wyloguj"], at.wywolania                                          # cap+blanki = zostaje


def test_d_zagrozenie_zycia_eskaluje_zamiast_wylogowac():
    s, n, at = swiat()
    s.log("a", [(s.zegar.t - timedelta(seconds=30), "ALARM: PK: gracz atakuje: X (czaszka), uciekam do depo")], nazwa="mozg-stdout-1021-1100.log")
    n.tick()
    assert "wyloguj" not in at.nazwy() and n.post("a").get("hold"), at.wywolania


# ============================================================ (e) refill_auto (strona bota)
def test_e_refill_auto_domyslne_wlaczone_zlec_i_czekaj_pomijaja_refill():
    with tempfile.TemporaryDirectory() as tmp:
        inst = Path(tmp) / "instancje"
        (inst / "_wspolne").mkdir(parents=True)
        for i in ("x", "y", "z"):
            (inst / i).mkdir()
        plan = {"postacie": {"x": {"kroki": []}, "y": {"zostan_w_depo": False}}, "domyslne": DOM}
        (inst / "_wspolne" / "plan_postaci.json").write_text(json.dumps(plan))
        assert RA.zostaje_w_depo(inst / "x") and RA.zostaje_w_depo(inst / "z")            # x: wpis bez flagi, z: bez wpisu
        assert RA.zostaje_w_depo(inst / "y") is None                                       # nadpisanie per postać
        stan, powod = RA.zlec((32347, 32226, 7), inst / "x", start=lambda: (_ for _ in ()).throw(AssertionError("start")), procesy=lambda *a, **k: [])
        assert stan == "pominiety" and "zostan_w_depo" in powod, (stan, powod)

        class Rc:
            returncode, stdout, stderr = 0, "", ""
        wywolania = []
        kod = RA.czekaj(inst / "z", procesy=lambda *a, **k: [], uruchom=lambda *a, **k: wywolania.append(a) or Rc(), spij=lambda s_: None, zegar=lambda: 0.0)
        assert kod == 0 and not wywolania, (kod, wywolania)
        (inst / "z" / "STOP_RECZNY").touch()
        assert RA.zlec((0, 0, 7), inst / "z", procesy=lambda *a, **k: [])[0] == "pominiety"


def test_e_refill_auto_zepsuty_plan_to_brak_flagi():
    with tempfile.TemporaryDirectory() as tmp:
        inst = Path(tmp) / "instancje"
        (inst / "_wspolne").mkdir(parents=True)
        (inst / "x").mkdir()
        (inst / "_wspolne" / "plan_postaci.json").write_text("{zepsute")
        assert RA.zostaje_w_depo(inst / "x") is None


# ============================================================ (f) walidacja, opis, zapis planu
def test_f_domyslne_walidacja():
    assert ZD.domyslne({}) == (None, None) and ZD.domyslne(None) == (None, None) and ZD.domyslne({"domyslne": None}) == (None, None)
    assert ZD.domyslne({"domyslne": {"wlaczone": False}}) == (None, None) and ZD.domyslne({"domyslne": {}}) == (None, None)
    dom, blad = ZD.domyslne({"domyslne": {"wlaczone": True}})
    assert blad is None and dom["zostan_w_depo"] is True and dom["wyloguj_w_depo"] is True and dom["zostan_w_depo_powod"], dom
    dom, _ = ZD.domyslne({"domyslne": {"wlaczone": True, "wyloguj_w_depo": False}})
    assert dom["wyloguj_w_depo"] is False
    for zle in ("tak", [], 3, {"wlaczone": "true"}, {"wlaczone": 1}, {"wlaczone": True, "zostan_w_depo": "tak"}, {"wlaczone": True, "wyloguj_w_depo": 1}):
        dom, blad = ZD.domyslne({"domyslne": zle})
        assert dom is None and blad, (zle, dom, blad)


def test_f_parsuj_domyslne_i_nadpisanie():
    dom, _ = ZD.domyslne({"domyslne": DOM})
    assert not ZD.parsuj(None).flaga and not ZD.parsuj({}, None).flaga
    z = ZD.parsuj(None, dom)
    assert z.flaga and z.wyloguj and z.z_domyslnych and not z.po_refillach, vars(z)
    z = ZD.parsuj({"kroki": []}, dom)
    assert z.flaga and z.wyloguj and z.z_domyslnych
    z = ZD.parsuj({"zostan_w_depo": False}, dom)
    assert not z.flaga and z.wyloguj and not z.z_domyslnych
    z = ZD.parsuj({"zostan_w_depo": True}, dom)
    assert z.flaga and not z.z_domyslnych
    z = ZD.parsuj({"zostan_w_depo_po_refillach": 2}, dom)
    assert z.flaga and z.po_refillach == 2 and z.wyloguj
    z = ZD.parsuj({"zostan_w_depo_po_refillach": 0}, dom)
    assert z.blad and not z.flaga


def test_f_plan_zly_ksztalt_domyslne_to_blad_planu_i_wylaczone():
    s = TP.SwiatP(("a",), {"a": {"kroki": []}})
    zapisz_plan(s, {"a": {"kroki": []}}, "tak")
    p = P.wczytaj(s.k)
    assert p.bledy and any("domyslne" in b for b in p.bledy) and not p.postacie["a"].zostan_w_depo and not p.zostan_domyslny.flaga, p.bledy
    zapisz_plan(s, {"a": {"kroki": []}}, DOM)
    p = P.wczytaj(s.k)
    assert not p.bledy and p.postacie["a"].zostan_w_depo and p.postacie["a"].wyloguj_w_depo and p.zostan_domyslny.flaga, p.bledy


def test_f_opis_planu_postaci_bez_wpisu():
    s = TP.SwiatP(("a",), {"a": {"kroki": []}})
    zapisz_plan(s, {"a": {"kroki": []}}, DOM)
    o = P.opis_planu(s.k, "nieznana")
    assert o["zostan_w_depo"] is True and o["wyloguj_w_depo"] is True and o["zostan_domyslne"] is True and o["kroki"] == [], o
    zapisz_plan(s, {"a": {"kroki": []}}, None)
    o = P.opis_planu(s.k, "nieznana")
    assert o["zostan_w_depo"] is False and o["wyloguj_w_depo"] is False and o["zostan_domyslne"] is False, o


def _pokaz(s):
    bufor = io.StringIO()
    stare = os.environ.get("RETRONIC_NADZOR_KORZEN")
    os.environ["RETRONIC_NADZOR_KORZEN"] = str(s.k)
    try:
        with contextlib.redirect_stdout(bufor):
            P.main(["pokaz"])
    finally:
        if stare is None:
            os.environ.pop("RETRONIC_NADZOR_KORZEN", None)
        else:
            os.environ["RETRONIC_NADZOR_KORZEN"] = stare
    return bufor.getvalue()


def test_f_pokaz_wylaczone_bez_zmian_wlaczone_pokazuje_domyslne():
    s = TP.SwiatP(("a",), {"a": {"kroki": []}})
    zapisz_plan(s, {"a": {"kroki": []}}, None)
    bez = _pokaz(s)
    zapisz_plan(s, {"a": {"kroki": []}}, {"wlaczone": False})
    assert _pokaz(s) == bez and "domyślne" not in bez
    zapisz_plan(s, {"a": {"kroki": []}}, DOM)
    z = _pokaz(s)
    assert "domyślne: WŁĄCZONE" in z and "(domyślnie)" in z, z


def test_f_zapis_planu_przez_nadzorce_zachowuje_klucz_domyslne():
    s = TP.SwiatP(("a",), {"a": {"kroki": [TP.krok("poziom >= 9", "wroc")]}})
    zapisz_plan(s, {"a": {"kroki": [TP.krok("poziom >= 9", "wroc")]}}, DOM)
    p = P.wczytaj(s.k)
    assert p.postacie["a"].kroki, p.bledy
    P.oznacz_zrobione(s.k, "a", "k1", s.zegar.t)
    d = json.loads((s.k / "instancje" / "_wspolne" / "plan_postaci.json").read_text())
    assert d.get("domyslne") == DOM, d
    assert d["postacie"]["a"]["kroki"][0]["zrobione_t"], d


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
