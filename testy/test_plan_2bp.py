#!/usr/bin/env python3
"""„2 bp UH, potem depo i wylogowanie” (24.10, Karol: „invincible i dawajkesh mają zrobić po 2 bp UH-ów, zakończyć i wylogować się w depo”).
Mechanizm: pola planu `zostan_w_depo_po_refillach: N` (flaga działa dopiero po N refillach od `zostan_w_depo_od`), `wyloguj_w_depo: true`
(nadzorca wylogowuje postać stojącą w depo ze STOP) i licznik refilli `instancje/<id>/refille.json` (zapisuje refill_auto.czekaj).
Offline: katalogi tymczasowe i atrapy z testy/test_nadzor.py / test_plan_postaci.py; nic nie dotyka gry, botów, sesji ani timera.
Dowodzi: (a) przy pierwszym depo (0 refilli) refill idzie normalnie, a nadzorca zachowuje się jak bez flagi; refill liczy się dopiero po przyjęciu przez
refill.sh; w trakcie samego refillu (bot jeszcze nie wystartował po nim) postać NIE jest uznana za „zostaje” i nie jest wylogowywana; (b) po 2. depo: brak
refillu i decyzja wyloguj (kod plan-wyloguj-depo, na żywo także bez NADZOR_ZYWO); (c) wyloguj szanuje bramki (STOP_RECZNY, pauza, walka, odstęp logowań,
jedna postać naraz, serwis, hold, 3 porażki = eskalacja); (d) po wylogowaniu brak relogu i startu sesji; (e) stare `zostan_w_depo` bez nowych pól działa jak przedtem.
Uruchomienie: python3 -I testy/test_plan_2bp.py"""
import json
import os
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["RETRONIC_TESTY"] = "1"
os.environ["RETRONIC_ID"] = "tst2bp"
KORZEN = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
sys.path.insert(0, str(KORZEN / "testy"))
import nadzor as N  # noqa: E402
import test_nadzor as TN  # noqa: E402
import test_plan_postaci as TP  # noqa: E402
import plan_postaci as P  # noqa: E402
import refill_auto as RA  # noqa: E402

OD = "2026-10-21 09:30:00"
NOWE = {"zostan_w_depo_po_refillach": 1, "zostan_w_depo_od": OD, "wyloguj_w_depo": True,
        "zostan_w_depo_powod": "Karol 24.10: 2 bp UH, potem depo i wylogowanie"}


def ep(s, minut_temu):
    return (s.zegar.t - timedelta(minutes=minut_temu)).timestamp()


def refille(s, id_, *minut_temu):
    """Zapis licznika refilli (format refille.json: {"t": [epoch, ...]}) bez użycia kodu pod testem."""
    p = s.plik(id_, "refille.json")
    stare = json.loads(p.read_text())["t"] if p.exists() else []
    p.write_text(json.dumps({"t": sorted(stare + [ep(s, m) for m in minut_temu])}))


def log_startu(s, id_, hhmm):
    """Nazwa najnowszego logu bota = godzina jego startu (uruchom.sh: mozg-stdout-MMDD-GGMM.log); przemianowuje istniejący log."""
    logi = s.plik(id_, "logi")
    nowy = logi / f"mozg-stdout-1021-{hhmm}.log"
    for stary in sorted(logi.glob("mozg-stdout-*.log")):
        if stary != nowy:
            stary.rename(nowy)
    os.utime(nowy, (time.time() + 5, time.time() + 5))


def swiat(ids=("a",), plan_dod=None, tryb="zywo", stop_od_start=("1000",)):
    """Postacie w grze, bez bota, STOP, dowód depo; log bota wystartował o `stop_od_start` (domyślnie 10:00)."""
    pc = {"kroki": [], **(plan_dod or {})}
    s = TP.SwiatP(ids, {i: dict(pc) for i in ids})
    t = s.zegar.t
    s.grafik([TN.zmiana(j, od="2026-10-21 11:00", koniec="2026-10-21 13:30", wylog="2026-10-21 13:45") for j in ids])
    for i in ids:
        s.tryb_log(i, "trolle_edron_z9z", "ostrozny,runy,uh", t.replace(hour=10, minute=0))
        s.online(i, bot=False, w_depo=True, w_miescie="edron", wroc_refill="brak_planu", level=15)
        s.plik(i, "STOP").touch()
        s.log(i, [(t - timedelta(minutes=40), "Mózg: tryb skrypt, postać A, trasa edron_trolle_petla (90 pkt, start 3), próg HP 30.0%, bez modelu."),
                  (t - timedelta(minutes=30), "Wyprawa: DEPO osiągnięte"), (t - timedelta(minutes=29), "Zatrzymano (plik STOP).")])
        log_startu(s, i, stop_od_start[0])
    n, at = TP.nadzorca(s, tryb)
    for i in ids:
        n.stan["postacie"][i] = {"faza": "EXP", "bot_widziany": ep(s, 40), "bot_start": ep(s, 40), "zmiana_od": "2026-10-21 11:00",
                                 "login_ts": ep(s, 120), "sesja_nasza": True}
    return s, n, at


def kody(n, id_="a"):
    return [x for x in n.dziennik.ostatnie if x["id"] == id_]


# ============================================================ (a) pierwsze depo: wszystko jak bez flagi
def test_a_pierwsze_depo_zero_refilli_nadzorca_jak_bez_flagi_a_refill_idzie():
    for tryb in ("zywo", "naprawy"):
        s, n, at = swiat(plan_dod=NOWE, tryb=tryb)
        s0, n0, at0 = swiat(plan_dod=None, tryb=tryb)
        for _ in range(4):
            n.tick(); n0.tick()
            s.zegar.dalej(minutes=5); s0.zegar.dalej(minutes=5)
        assert at.nazwy() == at0.nazwy(), (tryb, at.wywolania, at0.wywolania)
        assert "wyloguj" not in at.nazwy() and not n.post("a").get("zostan_depo_od"), at.wywolania
        assert not [x for x in kody(n) if x["akcja"] == "wyloguj"], kody(n)
        assert [x["akcja"] for x in kody(n)] == [x["akcja"] for x in kody(n0)], (kody(n), kody(n0))


def test_a_refill_auto_pierwsze_depo_czeka_potem_licznik_i_drugie_depo_pominiety():
    with tempfile.TemporaryDirectory() as tmp:
        inst = Path(tmp) / "instancje"
        (inst / "_wspolne").mkdir(parents=True)
        (inst / "x").mkdir()
        (inst / "_wspolne" / "plan_postaci.json").write_text(json.dumps({"postacie": {"x": {
            "kroki": [], "zostan_w_depo_po_refillach": 1, "zostan_w_depo_od": "2000-01-01 00:00:00", "wyloguj_w_depo": True,
            "zostan_w_depo_powod": "Karol 24.10"}}}))
        st = inst / "x"
        starty = []
        nic = lambda *a, **k: []                         # noqa: E731
        edron = (33170, 31810, 7)
        assert RA.zostaje_w_depo(st) is None
        r = RA.zlec(edron, st, start=lambda: starty.append(1), procesy=nic)
        assert r[0] in ("czeka", "brak_planu", "pominiety") and "zostan_w_depo" not in r[1], r      # pierwsze depo: bez blokady flagi
        assert r[0] != "pominiety" or "cooldown" in r[1] or "nie stoi" in r[1], r
        wyw = []
        # 24.10 (przegląd 2bp): licznik rośnie tylko po wyprawie z powodem blanki; bot zapisuje powody w wyprawa_stan.json przy starcie wyprawy
        (st / "wyprawa_stan.json").write_text(json.dumps({"aktywna": False, "wynik": "depo", "depo_start_powody": ["blanki"], "zapis_wall": time.time() - 5}))

        class Rc:
            returncode, stdout, stderr = 0, "refill ruszył", ""
        t = [0.0]
        kod = RA.czekaj(st, procesy=lambda *a, **k: [], uruchom=lambda *a, **k: (wyw.append(a[0]), Rc())[1],
                        spij=lambda s_: t.__setitem__(0, t[0] + s_), zegar=lambda: t[0])
        assert kod == 0 and any("refill.sh" in str(x) for x in wyw), (kod, wyw)
        assert RA.czytaj_stan(st)["stan"] == "uruchomiony"
        zapis = json.loads((st / "refille.json").read_text())
        assert len(zapis["t"]) == 1, zapis
        assert RA.zostaje_w_depo(st) == "Karol 24.10"                              # drugie depo: flaga uzbrojona
        r = RA.zlec(edron, st, start=lambda: starty.append(2), procesy=nic)
        assert r[0] == "pominiety" and "zostan_w_depo" in r[1] and starty == [], (r, starty)
        wyw.clear()
        kod = RA.czekaj(st, procesy=lambda *a, **k: [], uruchom=lambda *a, **k: (wyw.append(a[0]), Rc())[1],
                        spij=lambda s_: None, zegar=lambda: 0.0)
        assert kod == 0 and not any("refill.sh" in str(x) for x in wyw), wyw        # czekacz zlecony wcześniej też nie robi refillu
        assert len(json.loads((st / "refille.json").read_text())["t"]) == 1


def test_a_refill_odrzucony_przez_refill_sh_nie_liczy_sie():
    with tempfile.TemporaryDirectory() as tmp:
        st = Path(tmp) / "instancje" / "x"
        st.mkdir(parents=True)

        class Rc:
            returncode, stdout, stderr = 1, "", "bot działa"
        kod = RA.czekaj(st, procesy=lambda *a, **k: [], uruchom=lambda *a, **k: Rc(), spij=lambda s_: None, zegar=lambda: 0.0)
        assert kod == 1 and not (st / "refille.json").exists()


def test_a_refille_sprzed_wpisu_nie_licza_sie_i_zly_licznik_to_zero():
    import zostan_depo as ZD
    with tempfile.TemporaryDirectory() as tmp:
        st = Path(tmp)
        z = ZD.parsuj({"zostan_w_depo_po_refillach": 1, "zostan_w_depo_od": "2026-10-24 09:50:00"})
        ZD.zapisz_refill(st, time.mktime((2026, 10, 24, 9, 0, 0, 0, 0, -1)))
        assert not ZD.uzbrojona(z, st)
        ZD.zapisz_refill(st, time.mktime((2026, 10, 24, 10, 5, 0, 0, 0, -1)))
        assert ZD.uzbrojona(z, st)
        (st / "refille.json").write_text("{zepsute")
        assert ZD.czytaj_refille(st) == [] and not ZD.uzbrojona(z, st)


def test_a_zle_pola_planu_to_blad_planu_i_brak_flagi():
    for zle in (0, -1, "1", True, 1.5):
        s = TP.SwiatP(("a",), {"a": {"kroki": [], "zostan_w_depo": True, "zostan_w_depo_po_refillach": zle}})
        p = P.wczytaj(s.k)
        assert p.bledy and not p.postacie["a"].zostan_w_depo, (zle, p.bledy)
    s = TP.SwiatP(("a",), {"a": {"kroki": [], "zostan_w_depo_po_refillach": 1, "zostan_w_depo_od": "wczoraj"}})
    p = P.wczytaj(s.k)
    assert p.bledy and not p.postacie["a"].zostan_w_depo, p.bledy


# ============================================================ w trakcie refillu: nie wylogowuj
def test_a_w_trakcie_pierwszego_refillu_bot_jeszcze_nie_wystartowal_po_nim_zero_wylogowania():
    for tryb in ("zywo", "naprawy"):
        s, n, at = swiat(plan_dod=NOWE, tryb=tryb, stop_od_start=("1000",))      # bot z 10:00, refill zlecony 10:55 (po nim bot jeszcze nie ruszył)
        refille(s, "a", 25)
        s.inst["a"]["panel"]["serwis_dziala"] = True
        for _ in range(4):
            n.tick()
            s.zegar.dalej(minutes=5)
        assert "wyloguj" not in at.nazwy(), at.wywolania
        assert not n.post("a").get("zostan_depo_od")


# ============================================================ (b) drugie depo: wyloguj
def test_b_po_drugim_depo_wyloguj_bez_refillu_serwisu_i_wznowienia():
    for tryb in ("zywo", "naprawy"):
        s, n, at = swiat(plan_dod=NOWE, tryb=tryb, stop_od_start=("1100",))      # bot wystartował 11:00, po refillu z 10:55
        refille(s, "a", 25)
        n.tick()
        assert at.nazwy() == ["wyloguj"], (tryb, at.wywolania)
        d = [x for x in kody(n) if x["akcja"] == "wyloguj"]
        assert d and d[0]["wynik"] == "ok" and "zostan_w_depo" in d[0]["powod"] and "Karol 24.10" in d[0]["powod"], kody(n)
        assert n.post("a").get("zostan_depo_od")


def test_b_cien_bez_naprawy_tylko_zapis_zrobilbym():
    s, n, at = swiat(plan_dod=NOWE, tryb="cien", stop_od_start=("1100",))
    refille(s, "a", 25)
    n.tick()
    assert at.wywolania == [], at.wywolania
    assert [x for x in n.dziennik.ostatnie if x.get("akcja") == "wyloguj" and x.get("wynik") == "cień"], n.dziennik.ostatnie


def test_b_refill_przed_wpisem_nie_liczy_sie():
    s, n, at = swiat(plan_dod={**NOWE, "zostan_w_depo_od": "2026-10-21 11:10:00"}, stop_od_start=("1100",))
    refille(s, "a", 25)                                     # 10:55 < wpis 11:10
    n.tick()
    assert "wyloguj" not in at.nazwy(), at.wywolania


# ============================================================ (c) bramki
def test_c_stop_reczny_pauza_hold_nadzor_false_zero_wylogowania():
    s, n, at = swiat(plan_dod=NOWE, stop_od_start=("1100",))
    refille(s, "a", 25)
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


def test_c_walka_serwis_i_brak_dowodu_depo_odkladaja_wylogowanie():
    s, n, at = swiat(plan_dod=NOWE, stop_od_start=("1100",))
    refille(s, "a", 25)
    s.log("a", [(s.zegar.t - timedelta(seconds=5), "Cel Troll: atak")], nazwa="mozg-stdout-1021-1100.log")
    n.tick()
    assert "wyloguj" not in at.nazwy() and any("spok" in x["powod"] for x in kody(n)), (at.wywolania, kody(n))
    s.zegar.dalej(minutes=5)
    s.inst["a"]["panel"]["serwis_dziala"] = True
    n.tick()
    assert "wyloguj" not in at.nazwy(), at.wywolania
    s.inst["a"]["panel"].pop("serwis_dziala")
    s.zegar.dalej(minutes=5)
    n.tick()
    assert at.nazwy() == ["wyloguj"], at.wywolania


def test_c_odstep_od_poprzedniego_logowania_i_jedna_postac_naraz():
    s, n, at = swiat(("a", "b"), plan_dod=NOWE, stop_od_start=("1100",))
    for i in ("a", "b"):
        refille(s, i, 25)
    n.stan["globalne"]["ostatnie_zdarzenie"] = ep(s, 2)          # ktoś się właśnie logował/wylogował
    n.tick()
    assert at.wywolania == [] and any(x["akcja"] == "odroczone" for x in n.dziennik.ostatnie), (at.wywolania, n.dziennik.ostatnie)
    s.zegar.dalej(minutes=6)
    n.tick()
    assert at.nazwy() == ["wyloguj"], at.wywolania                # jedna na przebieg (a); b czeka
    s.zegar.dalej(minutes=5)
    n.tick()
    assert at.nazwy() == ["wyloguj"], ("b przed upływem 7 min", at.wywolania)
    s.zegar.dalej(minutes=3)
    n.tick()
    assert at.nazwy() == ["wyloguj", "wyloguj"] and [w[1] for w in at.wywolania] == ["a", "b"], at.wywolania
    t = [c[0] for c in at.czasy if c[1] == "wyloguj"]
    assert (t[1] - t[0]) >= timedelta(minutes=7), t


def test_c_trzy_nieudane_wylogowania_to_eskalacja_nie_petla():
    s, n, at = swiat(plan_dod=NOWE, stop_od_start=("1100",))
    refille(s, "a", 25)
    at.wyniki["wyloguj"] = (False, "kod 5: brak spokoju")
    for _ in range(6):
        n.tick()
        s.zegar.dalej(minutes=8)
    assert at.nazwy().count("wyloguj") == 3, at.wywolania
    assert any(x["akcja"] == "eskaluj" for x in n.dziennik.ostatnie) or n.post("a").get("hold"), n.dziennik.ostatnie


def test_c_zagrozenie_zycia_eskaluje_zamiast_wylogowac():
    s, n, at = swiat(plan_dod=NOWE, stop_od_start=("1100",))
    refille(s, "a", 25)
    s.log("a", [(s.zegar.t - timedelta(seconds=30), "ALARM: PK: gracz atakuje: X (czaszka), uciekam do depo")], nazwa="mozg-stdout-1021-1100.log")
    n.tick()
    assert "wyloguj" not in at.nazwy() and n.post("a").get("hold"), at.wywolania


# ============================================================ (d) po wylogowaniu brak relogu
def test_d_po_wylogowaniu_brak_startu_sesji_logowania_relogu_przez_godziny():
    for tryb in ("zywo", "naprawy"):
        s, n, at = swiat(plan_dod=NOWE, tryb=tryb, stop_od_start=("1100",))
        refille(s, "a", 25)
        n.tick()
        assert at.nazwy() == ["wyloguj"], at.wywolania
        assert not s.inst["a"]["sesja"]
        for _ in range(40):                                   # ~3,5 h: przerwa po wylogowaniu minęła, grafik ma zmianę, nowa doba
            s.zegar.dalej(minutes=5)
            n.tick()
        assert at.nazwy() == ["wyloguj"], (tryb, at.wywolania)
        assert kody(n)[-1]["powod"].startswith("offline, ostatnio w depo ze STOP"), kody(n)[-1]
        s.inst["a"].update(sesja=True)                       # sesja w trakcie zamykania: klient poza grą
        s.ekran_map["a"] = "logowanie"
        s.inst["a"].update(gracz=None, panel={})
        n.tick()
        assert at.nazwy() == ["wyloguj"], at.wywolania


# ============================================================ (e) stare zostan_w_depo bez nowych pól
def test_e_stare_zostan_w_depo_zostaje_stoi_bez_wylogowania():
    s, n, at = swiat(plan_dod={"zostan_w_depo": True, "zostan_w_depo_powod": "Karol 23.10"}, stop_od_start=("0900",))
    for _ in range(14):
        n.tick()
        s.zegar.dalej(minutes=5)
    assert at.wywolania == [], at.wywolania
    assert kody(n) and all(x["akcja"] == "czekaj" for x in kody(n)) and "Karol 23.10" in kody(n)[0]["powod"], kody(n)


def test_e_wyloguj_w_depo_dziala_tez_ze_starym_zostan_w_depo_bez_licznika():
    s, n, at = swiat(plan_dod={"zostan_w_depo": True, "wyloguj_w_depo": True}, stop_od_start=("0900",))
    n.tick()
    assert at.nazwy() == ["wyloguj"], at.wywolania


def test_e_refill_auto_stara_flaga_blokuje_jak_przedtem_a_bez_flagi_nie():
    with tempfile.TemporaryDirectory() as tmp:
        inst = Path(tmp) / "instancje"
        (inst / "_wspolne").mkdir(parents=True)
        for i in ("x", "y"):
            (inst / i).mkdir()
        (inst / "_wspolne" / "plan_postaci.json").write_text(json.dumps({"postacie": {
            "x": {"zostan_w_depo": True, "zostan_w_depo_powod": "Karol 23.10"}, "y": {"kroki": []}}}))
        assert RA.zostaje_w_depo(inst / "x") == "Karol 23.10" and RA.zostaje_w_depo(inst / "y") is None
        (inst / "_wspolne" / "plan_postaci.json").write_text("{zepsute")
        assert RA.zostaje_w_depo(inst / "x") is None


def test_stan_i_pokaz_pokazuja_nowe_pola():
    s, n, at = swiat(plan_dod=NOWE, stop_od_start=("1000",))
    pod = n.podsumowanie()["postacie"]["a"]["plan"]
    assert pod["zostan_w_depo_po_refillach"] == 1 and pod["wyloguj_w_depo"] is True and pod["zostan_uzbrojone"] is False and pod["refille_od_wpisu"] == 0, pod
    refille(s, "a", 25)
    pod = n.podsumowanie()["postacie"]["a"]["plan"]
    assert pod["refille_od_wpisu"] == 1 and pod["zostan_uzbrojone"] is False, pod        # refill był, ale bot jeszcze nie wystartował po nim
    log_startu(s, "a", "1100")
    pod = n.podsumowanie()["postacie"]["a"]["plan"]
    assert pod["zostan_uzbrojone"] is True, pod


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
