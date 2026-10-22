#!/usr/bin/env python3
"""grafik.py (SPEC_nadzor_wykonawca_1021, F1): reguły odstępów, limitu naraz, limitu dziennego i ciszy na 1000 losowych dób,
determinizm, przesunięcie dzienne, ręczna edycja wygrywa, pula postaci. Offline: katalog tymczasowy, bez gry i procesów.
Uruchomienie: python3 -I testy/test_grafik.py"""
import json
import os
import random
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True
KORZEN = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
import grafik as g  # noqa: E402

FMT = g.FMT


def _dt(t):
    return datetime.strptime(t, FMT)


def niezalezna_kontrola(plan, konf, teraz=None):
    """Własna, niezależna od grafik.waliduj kontrola reguł z decyzji Karola. -> lista naruszeń."""
    bl = []
    d = datetime.strptime(plan["data"], "%Y%m%d")
    start = d + timedelta(hours=8)
    cisza_od = d + timedelta(days=1, hours=1)            # 01:00 następnego dnia
    zd, per = [], {}
    for z in plan["zmiany"]:
        od, wy = _dt(z["od"]), _dt(z["wylog"])
        if not z.get("adoptowana"):
            if od < start:
                bl.append(f"logowanie w ciszy {z}")
            zd.append(od)
        if wy > cisza_od:
            bl.append(f"wylogowanie w ciszy {z}")
        zd.append(wy)
        per.setdefault(z["id"], []).append((max(od, start), wy))
        if teraz is not None and not z.get("adoptowana") and od < teraz:
            bl.append(f"zmiana w przeszłości {z}")
    zd.sort()
    for a, b in zip(zd, zd[1:]):
        if (b - a) < timedelta(minutes=7):
            bl.append(f"odstęp {b - a} między {a} i {b}")
    N = konf["max_online"]
    for z in plan["zmiany"]:
        p = _dt(z["od"])
        ile = sum(1 for y in plan["zmiany"] if _dt(y["od"]) <= p < _dt(y["wylog"]))
        if ile > N:
            bl.append(f"{ile} online > {N} o {p}")
    for id_, l in per.items():
        if sum((w - o).total_seconds() / 60 for o, w in l) > konf["limit_dzienny_min"]:
            bl.append(f"limit dzienny {id_}")
        l.sort()
        for (o1, w1), (o2, w2) in zip(l, l[1:]):
            if o2 - w1 < timedelta(minutes=konf["przerwa_min"][0]) and not (o1 < start):
                bl.append(f"przerwa {id_} {o2 - w1}")
    return bl


def losowa_konfiguracja(rng):
    k = json.loads(json.dumps(g.DOMYSLNE))
    k["max_online"] = rng.randint(1, 5)
    if rng.random() < 0.3:
        k["zmiana_min"] = [rng.randint(60, 120), rng.randint(121, 240)]
    if rng.random() < 0.3:
        k["odstep_min"] = [7, rng.randint(8, 40)]
    if rng.random() < 0.3:
        k["przerwa_min"] = [rng.randint(30, 60), rng.randint(61, 180)]
    if rng.random() < 0.2:
        k["limit_dzienny_min"] = rng.choice([240, 360, 480])
    return k


def test_1000_losowych_dob():
    t0 = time.time()
    bledy, plany_puste, razem_zmian = [], 0, 0
    for i in range(1000):
        rng = random.Random(i)
        konf = losowa_konfiguracja(rng)
        data = date(2026, 10, 21) + timedelta(days=rng.randint(-100, 600))
        ids = [f"p{n}" for n in range(rng.randint(1, 9))]
        teraz, online = None, None
        if i % 3 == 0 and ids:      # co trzecia doba: generowanie "od teraz" z postaciami już online
            start = g.poczatek_doby(data, konf)
            teraz = start + timedelta(minutes=rng.randint(0, 900))
            online = {x: {"od": teraz - timedelta(minutes=rng.randint(5, 200))} for x in rng.sample(ids, rng.randint(0, min(len(ids), konf['max_online'])))}
        plan = g.generuj(data, ids, konf, teraz=teraz, online=online)
        razem_zmian += len(plan["zmiany"])
        plany_puste += not plan["zmiany"]
        bl = niezalezna_kontrola(plan, konf, teraz)
        bl2 = g.waliduj(plan, konf)
        if bl or bl2:
            bledy.append((i, bl[:2], bl2[:2]))
    assert not bledy, f"{len(bledy)} dób łamie reguły, np. {bledy[:3]}"
    assert razem_zmian > 3000, razem_zmian
    print(f"   1000 dób: {razem_zmian} zmian, puste doby {plany_puste}, {time.time() - t0:.1f} s")


def test_piec_postaci_pelna_doba():
    konf = g.DOMYSLNE
    ids = ["a", "b", "c", "d", "e"]
    plan = g.generuj(date(2026, 10, 22), ids, konf)
    per = {i: [z for z in plan["zmiany"] if z["id"] == i] for i in ids}
    assert all(len(v) >= 2 for v in per.values()), {i: len(v) for i, v in per.items()}
    assert not niezalezna_kontrola(plan, konf)
    for z in plan["zmiany"]:
        h = (_dt(z["koniec"]) - _dt(z["od"])).total_seconds() / 60
        assert 120 <= h <= 180, z
        assert (_dt(z["wylog"]) - _dt(z["koniec"])).total_seconds() / 60 == konf["miasto_min"]


def test_determinizm_i_inne_dni():
    ids = ["a", "b", "c"]
    p1 = g.generuj(date(2026, 11, 3), ids, g.DOMYSLNE)
    p2 = g.generuj(date(2026, 11, 3), ids, g.DOMYSLNE)
    assert p1 == p2
    assert g.generuj(date(2026, 11, 4), ids, g.DOMYSLNE)["zmiany"][0]["od"][:10] != p1["zmiany"][0]["od"][:10] or True
    ts1 = [z["od"][11:] for z in p1["zmiany"]]
    ts2 = [z["od"][11:] for z in g.generuj(date(2026, 11, 4), ids, g.DOMYSLNE)["zmiany"]]
    assert ts1 != ts2


def test_przesuniecie_dzienne():
    konf = g.DOMYSLNE
    d0 = date(2026, 10, 1)
    for id_ in ("invincible", "wydra", "x"):
        off = [g.przesuniecie_startu(id_, d0 + timedelta(days=n), konf) for n in range(90)]
        assert all(0 <= o <= konf["start_okno_min"] for o in off)
        assert all(abs(b - a) <= konf["przesuniecie_dzienne_min"] + 1e-9 for a, b in zip(off, off[1:])), id_
        assert sum(1 for a, b in zip(off, off[1:]) if abs(a - b) > 1) >= 85, "pory mają się przesuwać z dnia na dzień"
    # pierwsze zdarzenia doby nie wypadają codziennie o tej samej godzinie
    pierwsze = []
    for n in range(20):
        p = g.generuj(d0 + timedelta(days=n), ["a", "b"], konf)
        pierwsze.append(p["zmiany"][0]["od"][11:])
    assert len(set(pierwsze)) >= 15, pierwsze


def test_reczna_edycja_wygrywa():
    with tempfile.TemporaryDirectory() as tmp:
        k = Path(tmp)
        for n in ("a", "b"):
            (k / "instancje" / n).mkdir(parents=True)
            (k / "instancje" / n / "profil.json").write_text("{}")
        (k / "instancje" / "_wspolne").mkdir()
        teraz = datetime(2026, 10, 21, 9, 0)
        plan, nowy = g.plan_dla(teraz, k)
        assert nowy and g.sciezka(date(2026, 10, 21), k).exists()
        plan["zmiany"] = [{"id": "a", "od": "2026-10-21 12:00", "koniec": "2026-10-21 13:00", "wylog": "2026-10-21 13:15",
                           "mapa": "raty", "tryb": "ostrozny"}]
        g.zapisz(plan, k, kopia=False)
        plan2, nowy2 = g.plan_dla(teraz + timedelta(hours=2), k)
        assert not nowy2 and plan2["zmiany"] == plan["zmiany"] and plan2["zmiany"][0]["mapa"] == "raty"
        # godzina przed 08:00 należy jeszcze do poprzedniej doby
        assert g.doba_dla(datetime(2026, 10, 22, 7, 59)) == date(2026, 10, 21)
        assert g.doba_dla(datetime(2026, 10, 22, 8, 0)) == date(2026, 10, 22)
        # nowy zapis nie gubi starego pliku
        g.zapisz(g.generuj(date(2026, 10, 21), ["a"], g.DOMYSLNE), k)
        assert list((k / "instancje" / "_wspolne").glob("grafik-20261021.json.bak-*")), "brak kopii starego grafiku"
        assert g.aktywna_zmiana(plan2, "a", datetime(2026, 10, 21, 12, 30)) is not None
        assert g.aktywna_zmiana(plan2, "a", datetime(2026, 10, 21, 14, 0)) is None
        assert g.aktywna_zmiana(plan2, "b", datetime(2026, 10, 21, 12, 30)) is None


def test_pula_postaci():
    with tempfile.TemporaryDirectory() as tmp:
        k = Path(tmp)
        for n, profil in (("a", {}), ("b", {"nadzor": True}), ("c", {"nadzor": False}), ("test-x", {}), ("_archiwum", {}),
                          ("_wspolne", {}), ("e", {}), ("f", {})):
            (k / "instancje" / n).mkdir(parents=True)
            (k / "instancje" / n / "profil.json").write_text(json.dumps(profil))
        (k / "instancje" / "bez_profilu").mkdir()
        (k / "instancje" / "_wspolne" / "nadzor_konfig.json").write_text(json.dumps({"postacie": {"f": {"nadzor": False}}}))
        assert g.pula(k) == ["a", "b", "e"], g.pula(k)


def test_pula_nadzor_do():
    """`nadzor_do`: postać poza pulą do podanej chwili, potem wraca; zła data = poza pulą; to samo z konfiguracji."""
    with tempfile.TemporaryDirectory() as tmp:
        k = Path(tmp)
        for n, profil in (("a", {}), ("b", {"nadzor_do": "2026-10-24 08:30"}), ("c", {"nadzor_do": "kiedyś"}), ("d", {})):
            (k / "instancje" / n).mkdir(parents=True)
            (k / "instancje" / n / "profil.json").write_text(json.dumps(profil))
        (k / "instancje" / "_wspolne").mkdir()
        (k / "instancje" / "_wspolne" / "nadzor_konfig.json").write_text(json.dumps({"postacie": {"d": {"nadzor_do": "2026-10-23 12:00"}}}))
        assert g.pula(k, teraz=datetime(2026, 10, 22, 9, 0)) == ["a"], g.pula(k, teraz=datetime(2026, 10, 22, 9, 0))
        assert g.pula(k, teraz=datetime(2026, 10, 23, 12, 0)) == ["a", "d"]       # konfiguracja wygasa jako pierwsza
        assert g.pula(k, teraz=datetime(2026, 10, 24, 8, 29)) == ["a", "d"]
        assert g.pula(k, teraz=datetime(2026, 10, 24, 8, 30)) == ["a", "b", "d"]    # dokładnie w chwili nadzor_do wraca
        assert "tymczasowo" in g.poza_nadzorem({"nadzor_do": "2026-10-24 08:30"}, None, datetime(2026, 10, 22, 9, 0))
        assert g.poza_nadzorem({"nadzor_do": "2026-10-24 08:30"}, None, datetime(2026, 10, 25)) is None


def test_nadzor_do_wygrywa_z_nadzor_false():
    """Q-N (Karol 22.10): przyszłe `nadzor_do` obok `nadzor: false` = poza nadzorem DO tej daty, potem postać wraca sama
    (profil Kolanosha: nadzor:false + nadzor_do 24.10 08:30). Bez daty `nadzor: false` zostaje bezterminowe."""
    kolanosh = {"nadzor": False, "nadzor_do": "2026-10-24 08:30"}
    przed = g.poza_nadzorem(kolanosh, None, datetime(2026, 10, 22, 9, 0))
    assert przed and "nadzor_do" in przed and "2026-10-24 08:30" in przed, przed
    assert g.poza_nadzorem(kolanosh, None, datetime(2026, 10, 24, 8, 29)) is not None
    assert g.poza_nadzorem(kolanosh, None, datetime(2026, 10, 24, 8, 30)) is None      # w chwili nadzor_do wraca
    assert g.poza_nadzorem(kolanosh, None, datetime(2026, 10, 25)) is None
    assert "nadzor: false" in g.poza_nadzorem({"nadzor": False}, None, datetime(2026, 10, 25))      # bez daty: bezterminowo
    assert g.poza_nadzorem({"nadzor": False, "nadzor_do": "kiedyś"}, None, datetime(2026, 10, 25))   # zła data: poza
    # konfiguracja nadzorcy ma własną blokadę niezależną od profilu
    assert g.poza_nadzorem(kolanosh, {"nadzor": False}, datetime(2026, 10, 25))
    with tempfile.TemporaryDirectory() as tmp:
        k = Path(tmp)
        (k / "instancje" / "kolanoth").mkdir(parents=True)
        (k / "instancje" / "kolanoth" / "profil.json").write_text(json.dumps(kolanosh))
        assert g.pula(k, teraz=datetime(2026, 10, 22, 9, 0)) == []
        assert g.pula(k, teraz=datetime(2026, 10, 24, 8, 30)) == ["kolanoth"]


def test_waliduj_lapie_naruszenia():
    konf = g.DOMYSLNE
    plan = {"data": "20261021", "zmiany": [
        {"id": "a", "od": "2026-10-21 09:00", "koniec": "2026-10-21 11:00", "wylog": "2026-10-21 11:15"},
        {"id": "b", "od": "2026-10-21 09:30", "koniec": "2026-10-21 11:05", "wylog": "2026-10-21 11:18"},   # wylogowania co 3 min
        {"id": "c", "od": "2026-10-21 07:00", "koniec": "2026-10-21 09:00", "wylog": "2026-10-21 09:15"},   # logowanie w ciszy
        {"id": "d", "od": "2026-10-21 23:00", "koniec": "2026-10-22 01:00", "wylog": "2026-10-22 01:20"}]}   # wylogowanie w ciszy
    tekst = " | ".join(g.waliduj(plan, konf))
    assert "odstęp 3 min" in tekst and "logowanie w ciszy" in tekst and "wylogowanie w ciszy" in tekst, tekst
    plan6 = {"data": "20261021", "zmiany": [
        {"id": f"p{n}", "od": f"2026-10-21 {9 + n // 3:02d}:{(n % 3) * 20:02d}", "koniec": "2026-10-21 22:00", "wylog": f"2026-10-21 22:{n * 10:02d}"}
        for n in range(6)]}
    assert "online > 5" in " | ".join(g.waliduj(plan6, konf))


def test_cli_nowy_pokaz_waliduj():
    import subprocess
    with tempfile.TemporaryDirectory() as tmp:
        k = Path(tmp)
        for n in ("a", "b", "c"):
            (k / "instancje" / n).mkdir(parents=True)
            (k / "instancje" / n / "profil.json").write_text("{}")
        env = dict(os.environ, RETRONIC_NADZOR_KORZEN=str(k))
        r = subprocess.run([sys.executable, "-I", str(KORZEN / "grafik.py"), "nowy", "--data", "20261021"], env=env,
                           capture_output=True, text=True)
        assert r.returncode == 0 and "walidacja: OK" in r.stdout, r.stdout + r.stderr
        r = subprocess.run([sys.executable, "-I", str(KORZEN / "grafik.py"), "pokaz", "--data", "20261021"], env=env,
                           capture_output=True, text=True)
        assert r.returncode == 0 and "login" in r.stdout and "razem:" in r.stdout, r.stdout
        r = subprocess.run([sys.executable, "-I", str(KORZEN / "grafik.py"), "nowy", "--od-teraz", "--online", "a,c"], env=env,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr


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
