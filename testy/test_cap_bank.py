#!/usr/bin/env python3
"""Wyprawa do depo WYŁĄCZNIE z powodu cap = bank (gold -> platinum) + powrót na spot, bez depo i bez zakupów (24.10, Karol ~10:00:
„powrót przy braku capa: zamiana na pc i powrót, aż do pełnego bp run”; „wystarczy, że zamieni hajs, nie musi go odkładać”) oraz licznik
refilli „2 bp” rosnący TYLKO po wyprawie z powodem `blanki` (przegląd 2bp, 24.10). Offline: katalogi tymczasowe i atrapy; nic nie dotyka gry,
botów ani sesji. Uruchomienie: python3 -I testy/test_cap_bank.py
Dowodzi: (a) sam cap -> refill.sh z REFILL_KROKI=bank,cap,wyjscie; (b) cap+blanki albo inny powód -> pełny refill (bez nadpisania kroków);
(c) cap przy `zostan_w_depo` (stara flaga) -> czeka i wraca, bez zatrzymania w depo; (d) cap nie zwiększa refille.json i nie uzbraja 2bp,
a nadzorca nie wylogowuje; (e) blanki przy fladze -> jak dotąd; (f) licznik: tylko `blanki` (także cap+blanki), nie cap/jedzenie/WROC/PK/brak stanu;
(g) nieświeży stan wyprawy nie udaje cap."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["RETRONIC_TESTY"] = "1"
os.environ["RETRONIC_ID"] = "tstcap"
KORZEN = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
sys.path.insert(0, str(KORZEN / "testy"))
import refill_auto as RA  # noqa: E402
import zostan_depo as ZD  # noqa: E402

EDRON_DEPO = (33173, 31796, 8)
THAIS_DEPO = (32348, 32225, 7)
nic = lambda *a, **k: []          # noqa: E731


class Rc:
    returncode, stdout, stderr = 0, "refill ruszył", ""


def swiat(plan_pc, powody=None, **stan):
    """Katalog instancji `x` z planem postaci i (opcjonalnie) wyprawa_stan.json po zakończonej wyprawie do depo."""
    tmp = tempfile.TemporaryDirectory()
    inst = Path(tmp.name) / "instancje"
    (inst / "_wspolne").mkdir(parents=True)
    st = inst / "x"
    st.mkdir()
    (inst / "_wspolne" / "plan_postaci.json").write_text(json.dumps({"postacie": {"x": {"kroki": [], **plan_pc}}}))
    if powody is not None:
        d = {"aktywna": False, "wynik": "depo", "depo_start_powody": powody, "zapis_wall": time.time() - 5}
        d.update(stan)
        (st / "wyprawa_stan.json").write_text(json.dumps(d))
    return tmp, st


def czekaj(st):
    """-> (kod, lista wywołań (polecenie, env))."""
    wyw = []

    def uruchom(cmd, *a, **k):
        wyw.append((cmd, k.get("env")))
        return Rc()
    kod = RA.czekaj(st, procesy=nic, uruchom=uruchom, spij=lambda s: None, zegar=lambda: 0.0)
    return kod, [w for w in wyw if any("refill.sh" in str(x) for x in w[0])]


def kroki_refillu(wyw):
    """REFILL_KROKI przekazane do refill.sh (None = bez nadpisania, czyli pełna lista domyślna)."""
    return (wyw[0][1] or {}).get("REFILL_KROKI")


def liczba_refilli(st):
    return len(ZD.czytaj_refille(st))


STARA = {"zostan_w_depo": True, "zostan_w_depo_powod": "Karol 23.10"}
DWA_BP = {"zostan_w_depo_po_refillach": 1, "zostan_w_depo_od": "2000-01-01 00:00:00", "wyloguj_w_depo": True, "zostan_w_depo_powod": "Karol 24.10"}


# ===================================================== (a) sam cap -> bank + wyjście
def test_a_sam_cap_refill_tylko_bank_i_wyjscie():
    tmp, st = swiat({}, ["cap"])
    with tmp:
        kod, wyw = czekaj(st)
        assert kod == 0 and len(wyw) == 1, (kod, wyw)
        assert kroki_refillu(wyw) == "bank,cap,wyjscie", wyw
        s = RA.czytaj_stan(st)
        assert s["stan"] == "uruchomiony" and "cap" in s["powod"], s


def test_a_zlec_sam_cap_czeka_w_edron_i_thais():
    for poz in (EDRON_DEPO, THAIS_DEPO):
        tmp, st = swiat({}, ["cap"], aktywna=True)
        with tmp:
            starty = []
            r = RA.zlec(poz, st, start=lambda: starty.append(1), procesy=nic)
            assert r[0] == "czeka" and starty == [1], (poz, r)


# ===================================================== (b) inne powody -> pełny refill
def test_b_cap_z_blankami_albo_jedzeniem_albo_wroc_to_pelny_refill():
    for powody in (["cap", "blanki"], ["blanki"], ["cap", "zapas"], ["cap", "glod"], ["zapas"], ["reczny"], ["pk"], ["cap", "blanki", "zapas"]):
        tmp, st = swiat({}, powody)
        with tmp:
            kod, wyw = czekaj(st)
            assert kod == 0 and len(wyw) == 1 and kroki_refillu(wyw) is None, (powody, wyw)


def test_b_brak_stanu_wyprawy_pelny_refill_jak_dotad():
    tmp, st = swiat({}, None)
    with tmp:
        kod, wyw = czekaj(st)
        assert kod == 0 and kroki_refillu(wyw) is None, wyw


# ===================================================== (c) cap przy starej fladze zostan_w_depo (wydra)
def test_c_cap_przy_starej_fladze_nie_zatrzymuje_w_depo():
    tmp, st = swiat(STARA, ["cap"], aktywna=True)
    with tmp:
        assert RA.zostaje_w_depo(st) is None
        starty = []
        r = RA.zlec(THAIS_DEPO, st, start=lambda: starty.append(1), procesy=nic)
        assert r[0] == "czeka" and starty == [1], r
    tmp, st = swiat(STARA, ["cap"])
    with tmp:
        kod, wyw = czekaj(st)
        assert kod == 0 and kroki_refillu(wyw) == "bank,cap,wyjscie", (kod, wyw)
        assert liczba_refilli(st) == 0


# ===================================================== (d) cap nie liczy się do 2 bp i nie uzbraja flagi
def test_d_cap_nie_zwieksza_licznika_i_nie_uzbraja_2bp():
    tmp, st = swiat(DWA_BP, ["cap"])
    with tmp:
        assert liczba_refilli(st) == 0
        kod, wyw = czekaj(st)
        assert kod == 0 and kroki_refillu(wyw) == "bank,cap,wyjscie", wyw
        assert liczba_refilli(st) == 0 and not (st / "refille.json").exists()
        z = ZD.parsuj({"kroki": [], **DWA_BP})
        assert not ZD.uzbrojona(z, st)


def test_d_cap_po_uzbrojeniu_flagi_tez_wraca_na_spot_licznik_bez_zmian():
    tmp, st = swiat(DWA_BP, ["cap"], aktywna=True)
    with tmp:
        ZD.zapisz_refill(st, time.time() - 3600)              # jeden prawdziwy refill (blanki) już był: flaga uzbrojona
        assert RA.zostaje_w_depo(st) is None                  # ale to depo jest z powodu cap: nie zatrzymuje
        starty = []
        r = RA.zlec(EDRON_DEPO, st, start=lambda: starty.append(1), procesy=nic)
        assert r[0] == "czeka" and starty == [1], r
        (st / "wyprawa_stan.json").write_text(json.dumps({"aktywna": False, "wynik": "depo", "depo_start_powody": ["cap"], "zapis_wall": time.time()}))
        kod, wyw = czekaj(st)
        assert kod == 0 and kroki_refillu(wyw) == "bank,cap,wyjscie" and liczba_refilli(st) == 1, (kod, wyw, liczba_refilli(st))


def test_d_nadzorca_nie_wylogowuje_uzbrojonej_postaci_po_depo_z_powodu_cap():
    import test_plan_2bp as T2
    for powody, oczekiwane in ((["cap"], []), (["blanki"], ["wyloguj"]), (["cap", "blanki"], ["wyloguj"])):
        s, n, at = T2.swiat(plan_dod=T2.NOWE, stop_od_start=("1100",))
        T2.refille(s, "a", 25)
        s.plik("a", "wyprawa_stan.json").write_text(json.dumps({"aktywna": False, "wynik": "depo", "depo_start_powody": powody,
                                                                "zapis_wall": s.zegar.t.timestamp() - 600}))
        n.tick()
        assert at.nazwy() == oczekiwane, (powody, at.wywolania)
        assert bool(n.post("a").get("zostan_depo_od")) == bool(oczekiwane), (powody, n.post("a"))


def test_d_nadzorca_stara_flaga_wydry_po_cap_nie_trzyma_w_depo_a_po_blankach_trzyma():
    import test_plan_2bp as T2
    for powody, zostaje in ((["cap"], False), (["blanki"], True)):
        s, n, at = T2.swiat(plan_dod={"zostan_w_depo": True, "zostan_w_depo_powod": "Karol 23.10"}, stop_od_start=("0900",))
        s.plik("a", "wyprawa_stan.json").write_text(json.dumps({"aktywna": False, "wynik": "depo", "depo_start_powody": powody,
                                                                "zapis_wall": s.zegar.t.timestamp() - 600}))
        n.tick()
        d = [x for x in T2.kody(n)]
        assert bool(d and "zostan_w_depo" in d[0]["powod"]) == zostaje, (powody, d)


# ===================================================== (e) blanki przy fladze: jak dotąd
def test_e_blanki_przy_starej_fladze_zostaje_w_depo_bez_refillu():
    tmp, st = swiat(STARA, ["blanki"], aktywna=True)
    with tmp:
        starty = []
        r = RA.zlec(THAIS_DEPO, st, start=lambda: starty.append(1), procesy=nic)
        assert r[0] == "pominiety" and "zostan_w_depo" in r[1] and starty == [], r
    tmp, st = swiat(STARA, ["cap", "blanki"], aktywna=True)
    with tmp:
        r = RA.zlec(THAIS_DEPO, st, start=lambda: None, procesy=nic)
        assert r[0] == "pominiety" and "zostan_w_depo" in r[1], r


# ===================================================== (f) licznik 2 bp: tylko blanki
def test_f_licznik_rosnie_tylko_przy_blankach():
    for powody, rosnie in ((["blanki"], True), (["cap", "blanki"], True), (["cap"], False), (["zapas"], False), (["glod"], False),
                           (["cap", "zapas"], False), (["reczny"], False), (["pk"], False), ([], False)):
        tmp, st = swiat(DWA_BP, powody)
        with tmp:
            kod, _ = czekaj(st)
            assert kod == 0 and liczba_refilli(st) == (1 if rosnie else 0), (powody, liczba_refilli(st))


def test_f_bez_stanu_wyprawy_licznik_nie_rosnie():
    tmp, st = swiat(DWA_BP, None)
    with tmp:
        kod, _ = czekaj(st)
        assert kod == 0 and liczba_refilli(st) == 0


def test_f_powrot_po_samym_cap_kolejne_blanki_dopiero_uzbrajaja():
    tmp, st = swiat(DWA_BP, ["cap"])
    with tmp:
        czekaj(st)
        z = ZD.parsuj({"kroki": [], **DWA_BP})
        assert not ZD.uzbrojona(z, st) and RA.zostaje_w_depo(st) is None
        (st / "wyprawa_stan.json").write_text(json.dumps({"aktywna": False, "wynik": "depo", "depo_start_powody": ["blanki"], "zapis_wall": time.time()}))
        kod, wyw = czekaj(st)
        assert kroki_refillu(wyw) is None and liczba_refilli(st) == 1
        assert ZD.uzbrojona(z, st) and RA.zostaje_w_depo(st) == "Karol 24.10"


# ===================================================== (g) świeżość stanu wyprawy
def test_g_nieswiezy_stan_cap_nie_udaje_powrotu_po_cap():
    tmp, st = swiat(STARA, ["cap"], zapis_wall=time.time() - 2 * 3600)
    with tmp:
        assert not ZD.tylko_cap(st)
        assert RA.zostaje_w_depo(st) == "Karol 23.10"
    tmp, st = swiat({}, ["cap"], zapis_wall=time.time() - 2 * 3600)
    with tmp:
        kod, wyw = czekaj(st)
        assert kroki_refillu(wyw) is None, wyw


def test_g_zepsuty_stan_wyprawy_to_pelny_refill():
    tmp, st = swiat({}, None)
    with tmp:
        (st / "wyprawa_stan.json").write_text("{zepsute")
        assert ZD.powody_depo(st) is None and not ZD.tylko_cap(st)


# ===================================================== refill.sh: REFILL_KROKI z env wygrywa z domyślną listą
def test_refill_sh_bierze_kroki_ze_zmiennej():
    src = (KORZEN / "refill.sh").read_text()
    assert 'KROKI="${REFILL_KROKI:-bank,depo,jedzenie,backpack,blanki,wyjscie}"' in src


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
