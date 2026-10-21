"""nadzor_stan.py: klasyfikacja linii logu i ocena instancji (bez gry, bez procesów)."""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import nadzor_stan as n  # noqa: E402


def _log(linie):
    f = tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8")
    f.write("\n".join(linie) + "\n")
    f.close()
    return Path(f.name)


def _teraz_txt(przesuniecie_s=0):
    return time.strftime("%H:%M:%S", time.localtime(time.time() - przesuniecie_s))


def test_czaszka_nieczytelna_to_nie_pk():
    p = _log([f"{_teraz_txt()} Czaszka: Wydra = nieczytelne (model: 'unreadable', $0.0008)."])
    w = n.przejrzyj_log(p, time.time() - 600, time.time())
    os.unlink(p)
    assert w["krytyczne"] == {}


def test_alarm_gm_i_zgon_krytyczne():
    p = _log([f"{_teraz_txt(5)} ALARM: mozg: ALARM_GM", f"{_teraz_txt(1)} [UCIECZKA] HP 0% (próg 32%)"])
    w = n.przejrzyj_log(p, time.time() - 600, time.time())
    os.unlink(p)
    assert set(w["krytyczne"]) == {"gracz/GM pisze albo patrzy (ALARM_GM)", "możliwy zgon (HP 0%)"}
    assert "ucieczka" in w["uwagi"]


def test_stare_linie_poza_oknem():
    p = _log([f"{_teraz_txt(3600)} ALARM: mozg: ALARM_GM", f"{_teraz_txt(30)} Cel Rat zabity na (1, 2, 9)."])
    w = n.przejrzyj_log(p, time.time() - 600, time.time())
    os.unlink(p)
    assert w["krytyczne"] == {} and w["zabicia"] == 1 and w["ostatnie_zabicie_min"] < 1


def _inst(**k):
    d = {"gra": True, "bot": True, "gracz": {"hp": 100, "max_hp": 100}, "panel": {"tooltip": ""}}
    d.update(k)
    return d


LOG0 = {"krytyczne": {}, "uwagi": {}, "ostatnie_zabicie_min": 1.0}
TELE0 = {"stoi_poza_walka_s": 0, "wiek_probki_s": 1}


def test_reczna_gra_bez_uwag():
    _, kryt, uwagi = n.ocen(_inst(bot=False), LOG0, TELE0, stop_reczny=True, wyprawa=None)
    assert kryt == [] and uwagi == []


def test_bot_nie_dziala_bez_stop_recznego():
    _, _, uwagi = n.ocen(_inst(bot=False), LOG0, TELE0, stop_reczny=False, wyprawa=None)
    assert any("bot nie działa" in u for u in uwagi)


def test_niskie_hp_wyprawa_dobicie():
    i = _inst(gracz={"hp": 30, "max_hp": 100}, panel={"tooltip": "dobicie 47% | med 9 s"})
    hp, kryt, uwagi = n.ocen(i, LOG0, TELE0, stop_reczny=False, wyprawa="depo:blanki")
    assert hp == 30 and "HP 30%" in kryt
    assert any("wyprawa" in u for u in uwagi) and any("dobicie 47%" in u for u in uwagi)


if __name__ == "__main__":
    for nazwa, f in list(globals().items()):
        if nazwa.startswith("test_"):
            f()
            print("ok", nazwa)
