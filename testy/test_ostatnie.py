#!/usr/bin/env python3
"""ostatnie.py (Przegląd, F1): zapis atomowy i scalanie, wyzwalacze zapisu (bot co 60 s, poziom, alarm, STOP, logowanie),
odporność na uszkodzony plik, backfill na atrapach, kontrakt `okno_api.py stan` (pola `ostatnie` i `przeglad`, online i offline)
i `ml-ustaw`. Wyłącznie atrapy w katalogu tymczasowym: bez gry, bez procesów, bez prawdziwych instancji.
Uruchomienie: python3 -I testy/test_ostatnie.py
Zmienna RETRONIC_TEST_OKNO_API=<ścieżka okno_api.py> uruchamia część `stan`/`ml-ustaw` na innej (np. starej) wersji skryptu."""
import os
os.environ["RETRONIC_TESTY"] = "1"
import fcntl
import json
import subprocess
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

sys.dont_write_bytecode = True
KORZEN = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
import ostatnie  # noqa: E402

OKNO_API = Path(os.environ.get("RETRONIC_TEST_OKNO_API") or KORZEN / "okno_api.py")
TERAZ = time.mktime((2026, 10, 22, 12, 0, 0, 0, 0, -1))      # „teraz” atrap: 2026-10-22 12:00 (czas lokalny)


def tmpdir():
    return Path(tempfile.mkdtemp(prefix="ostatnie-test-"))


def stan_dir(tmp, id_="x"):
    p = tmp / "instancje" / id_
    (p / "logi").mkdir(parents=True)
    return p


def wczytaj(p):
    return json.loads((Path(p) / "ostatnie.json").read_text(encoding="utf-8"))


G = {"hp": 150, "max_hp": 188, "mana": 40, "max_mana": 95, "exp": 9769, "level": 10, "procent": 12.7}


# ---------- zapis atomowy, scalanie, blokada ----------
def test_zapis_scala_i_nie_zostawia_smieci():
    s = stan_dir(tmpdir())
    ostatnie.zapisz(s, "bot", {"postac": "Wydra", "level": 12, "sesja": {"start": 1.0, "zab": 3}}, t=100.0)
    w = ostatnie.zapisz(s, "logowanie", {"w_grze_t": 200.0, "sesja": {"koniec": 200.0}}, t=200.0, scalaj=("sesja",))
    assert w["postac"] == "Wydra" and w["level"] == 12, w                       # pola nieruszone przez drugiego pisarza
    assert w["sesja"] == {"start": 1.0, "zab": 3, "koniec": 200.0}, w["sesja"]    # scalanie płytkie słownika
    assert w["zrodlo"] == "logowanie" and w["zapisano"] == 200.0 and w["v"] == 1
    assert wczytaj(s) == w
    assert sorted(p.name for p in s.iterdir() if p.is_file()) == ["ostatnie.json", "ostatnie.lock"], list(s.iterdir())


def test_zapis_bez_scalaj_podmienia_slownik():
    s = stan_dir(tmpdir())
    ostatnie.zapisz(s, "bot", {"sesja": {"start": 1.0, "zab": 3}}, t=1.0)
    w = ostatnie.zapisz(s, "bot", {"sesja": {"start": 5.0}}, t=2.0)
    assert w["sesja"] == {"start": 5.0}, w["sesja"]


def test_czytelnik_nigdy_nie_widzi_polowy_pliku():
    s = stan_dir(tmpdir())
    ostatnie.zapisz(s, "bot", {"postac": "A" * 2000, "level": 1}, t=1.0)
    stop = threading.Event()
    bledy = []

    def pisarz():
        n = 0
        while not stop.is_set():
            n += 1
            ostatnie.zapisz(s, "bot", {"postac": ("B" if n % 2 else "C") * 2000, "level": n}, t=float(n))

    def czytelnik():
        for _ in range(400):
            d, blad = ostatnie.czytaj(s)
            if d is None:
                bledy.append(blad)
            elif d["postac"][0] * 2000 != d["postac"]:
                bledy.append("rozdarte pole")
    w = threading.Thread(target=pisarz)
    w.start()
    czytelnik()
    stop.set()
    w.join()
    assert not bledy, bledy[:3]


def test_uszkodzony_plik_nie_wywraca_i_jest_zastapiony():
    s = stan_dir(tmpdir())
    (s / "ostatnie.json").write_text('{"v":1,"level":', encoding="utf-8")
    d, blad = ostatnie.czytaj(s)
    assert d is None and "JSON" in blad, (d, blad)
    api = ostatnie.dla_api(s, teraz=10.0)
    assert api["blad"] and api["level"] is None and api["wiek_s"] is None and set(ostatnie.KLUCZE) <= set(api), api
    w = ostatnie.zapisz(s, "bot", {"level": 7}, t=5.0)
    assert w and w["level"] == 7 and ostatnie.czytaj(s)[0]["level"] == 7
    (s / "ostatnie.json").write_text("[1,2]", encoding="utf-8")
    assert "obiektu" in ostatnie.czytaj(s)[1]
    (s / "ostatnie.json").write_text('{"v":99}', encoding="utf-8")
    assert "wersja" in ostatnie.czytaj(s)[1]
    assert ostatnie.dla_api(tmpdir()) is None                                  # brak pliku = None, nie błąd


def test_zajeta_blokada_nie_blokuje_bota():
    s = stan_dir(tmpdir())
    fd = os.open(s / "ostatnie.lock", os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        t0 = time.monotonic()
        w = ostatnie.zapisz(s, "bot", {"level": 3}, t=1.0, czekaj_s=ostatnie.BLOKADA_BOT_S)
        assert w is None and time.monotonic() - t0 < 0.5, (w, time.monotonic() - t0)
        assert not (s / "ostatnie.json").exists()
    finally:
        os.close(fd)
    assert ostatnie.zapisz(s, "bot", {"level": 3}, t=1.0) is not None


def test_zapis_do_nieistniejacego_lub_zablokowanego_miejsca_nie_rzuca():
    tmp = tmpdir()
    (tmp / "plik").write_text("x")
    assert ostatnie.zapisz(tmp / "plik" / "pod", "bot", {"level": 1}) is None          # katalog nie do utworzenia


# ---------- obliczenia ----------
def test_level_z_exp_zgodny_z_wzorem_tibii():
    for lv in (1, 5, 10, 12, 13, 25, 80):
        e = ostatnie.exp_na_level(lv)
        assert ostatnie.level_z_exp(e)[0] == lv, lv
        assert ostatnie.level_z_exp(e - 1)[0] == lv - 1 or lv == 1, lv
    assert ostatnie.level_z_exp(9769) == (10, 12.7)
    assert ostatnie.level_z_exp(None) == (None, None) and ostatnie.level_z_exp(-3) == (None, None) \
        and ostatnie.level_z_exp(True) == (None, None)


def test_kod_alarmu():
    assert ostatnie.kod_alarmu("ALARM: wyprawa: utkniecie: x") == "wyprawa"
    assert ostatnie.kod_alarmu("ALARM: niskie HP 33%") == "niskie HP 33%"
    assert ostatnie.kod_alarmu("ALARM_GM: ktoś") == "ALARM_GM"
    assert ostatnie.kod_alarmu("ALARM") == "ALARM"


# ---------- Pisarz (bot) ----------
class Zegar:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def pisarz(s, zegar, **kw):
    return ostatnie.Pisarz(s, zegar=zegar, miasto=kw.pop("miasto", lambda poz: (None, False)), **kw)


def sesja(zab=0):
    return {"start": 900.0, "zab": zab, "gold": 5, "uh": 1}


def test_tik_zapisuje_co_60_s_a_nie_czesciej():
    s = stan_dir(tmpdir())
    z = Zegar()
    p = pisarz(s, z)
    assert p.tik(1000.0, G, (33121, 31756, 9), "WYPAD", "Kolanosh", sesja()) is True
    d = wczytaj(s)
    assert (d["postac"], d["exp"], d["level"], d["level_proc"], d["hp"], d["max_hp"], d["mana"], d["max_mana"]) == \
        ("Kolanosh", 9769, 10, 12.7, 150, 188, 40, 95), d
    assert d["poz"] == [33121, 31756, 9] and d["pietro"] == 9 and d["stan_bota"] == "WYPAD" and d["zrodlo"] == "bot"
    assert d["sesja"]["exp_start"] == 9769 and d["sesja"]["start"] == 900.0 and d["sesja"]["koniec"] is None
    assert d["dane_t"] == 1000.0 and d["w_grze_t"] == 1000.0 and d["koniec_sesji"] is None
    zapisano = d["zapisano"]
    for t in (1001.0, 1030.0, 1059.9):                       # w ciągu 60 s: ani jednego zapisu
        assert p.tik(t, G, (1, 2, 3), "WYPAD", "Kolanosh", sesja()) is False
    assert wczytaj(s)["zapisano"] == zapisano
    g2 = dict(G, exp=9800)
    assert p.tik(1060.0, g2, (1, 2, 3), "WALKA", "Kolanosh", sesja(4)) is True
    d = wczytaj(s)
    assert d["exp"] == 9800 and d["sesja"]["exp_start"] == 9769 and d["sesja"]["zab"] == 4, d["sesja"]    # exp_start stały w sesji


def test_zmiana_levelu_zapisuje_od_razu():
    s = stan_dir(tmpdir())
    p = pisarz(s, Zegar())
    p.tik(1000.0, G, (1, 2, 7), "WYPAD", "A", sesja())
    assert p.tik(1010.0, dict(G), (1, 2, 7), "WYPAD", "A", sesja()) is False
    g11 = dict(G, level=11, procent=0.4, exp=int(ostatnie.exp_na_level(11)) + 1)
    assert p.tik(1020.0, g11, (1, 2, 7), "WYPAD", "A", sesja()) is True              # 20 s po zapisie, ale nowy level
    assert wczytaj(s)["level"] == 11 and wczytaj(s)["level_proc"] == 0.4
    g12 = dict(g11, level=12)
    assert p.tik(1022.0, g12, (1, 2, 7), "WYPAD", "A", sesja()) is False              # flapanie: nie częściej niż co 5 s
    assert p.tik(1026.0, g12, (1, 2, 7), "WYPAD", "A", sesja()) is True


def test_brakujace_dane_to_null_a_nie_zero():
    s = stan_dir(tmpdir())
    p = pisarz(s, Zegar())
    p.tik(1000.0, {"exp": 9769}, None, None, None, sesja())              # sam exp: level i % liczone, reszta nieznana
    d = wczytaj(s)
    assert d["level"] == 10 and d["level_proc"] == 12.7
    for k in ("hp", "max_hp", "mana", "max_mana", "poz", "pietro", "stan_bota", "postac"):
        assert d[k] is None, (k, d[k])
    p2 = pisarz(stan_dir(tmpdir(), "y"), Zegar())
    p2.tik(1000.0, {}, (1, 2, 3), "IDZ", "B", sesja())
    d2 = ostatnie.czytaj(p2.katalog)[0]
    assert d2["exp"] is None and d2["level"] is None and d2["sesja"]["exp_start"] is None and d2["poz"] == [1, 2, 3]


def test_tik_nie_rzuca_na_zlych_danych():
    s = stan_dir(tmpdir())
    p = pisarz(s, Zegar())
    for g in (None, "x", [], {"level": "a", "exp": "b"}, {"level": 10 ** 9}):
        assert p.tik(1000.0 + p.co_s, g, (1, 2), "X", "A", {}) in (True, False)


def test_miasto_i_mapa_przy_zapisie():
    s = stan_dir(tmpdir())
    (s.parent.parent / "ostatni_start.x.env").write_text("MAPA=trolle_edron\nTRYB=ostrozny\\,ml\n")
    p = pisarz(s, Zegar(), miasto=lambda poz: ("edron", True))
    p.tik(1000.0, G, (33173, 31796, 8), "WYPAD", "A", sesja())
    d = wczytaj(s)
    assert (d["miasto"], d["w_depo"], d["mapa"], d["tryb"]) == ("edron", True, "trolle_edron", ["ostrozny", "ml"]), d
    assert d["na_spocie_od"] == 1000.0
    p.tik(1100.0, G, (33173, 31796, 8), "WYPAD", "A", sesja())
    assert wczytaj(s)["na_spocie_od"] == 1000.0                          # ta sama mapa: „na spocie od” nie rusza


def test_zmiana_mapy_resetuje_na_spocie_od():
    s = stan_dir(tmpdir())
    env = s.parent.parent / "ostatni_start.x.env"
    env.write_text("MAPA=a\nTRYB=x\n")
    p = pisarz(s, Zegar())
    p.tik(1000.0, G, (1, 2, 3), "WYPAD", "A", sesja())
    env.write_text("MAPA=b\nTRYB=x\n")
    p.tik(1070.0, G, (1, 2, 3), "WYPAD", "A", sesja())
    d = wczytaj(s)
    assert d["mapa"] == "b" and d["na_spocie_od"] == 1070.0, d


def test_nowe_wejscie_do_gry_nie_przejmuje_wczorajszego_na_spocie_od():
    """27.10: `w_grze` odświeża `w_grze_t` i `sesja.start`, ale zostawiało stare `na_spocie_od`; nowy bot na tej samej mapie je przejmował."""
    s = stan_dir(tmpdir())
    (s.parent.parent / "ostatni_start.x.env").write_text("MAPA=a\nTRYB=x\n")
    p = pisarz(s, Zegar())
    p.tik(1000.0, G, (1, 2, 3), "WYPAD", "A", sesja())
    assert wczytaj(s)["na_spocie_od"] == 1000.0
    ostatnie.zdarzenie_logowania(s.parent / "logi", "zaloguj", "w_grze", {"zalogowany": "A", "oczekiwany": "A"}, t=90000.0)   # następny dzień
    p2 = pisarz(s, Zegar())                                               # nowy proces bota, ta sama mapa, w_grze_t świeże (< 180 s)
    p2.tik(90030.0, G, (1, 2, 3), "WYPAD", "A", sesja())
    assert wczytaj(s)["na_spocie_od"] == 90030.0, wczytaj(s)


def test_restart_bota_w_tej_samej_sesji_zachowuje_na_spocie_od():
    s = stan_dir(tmpdir())
    (s.parent.parent / "ostatni_start.x.env").write_text("MAPA=a\nTRYB=x\n")
    ostatnie.zdarzenie_logowania(s.parent / "logi", "zaloguj", "w_grze", {"zalogowany": "A", "oczekiwany": "A"}, t=900.0)
    p = pisarz(s, Zegar())
    p.tik(1000.0, G, (1, 2, 3), "WYPAD", "A", sesja())
    p2 = pisarz(s, Zegar())                                               # restart samego bota: sesja gry ta sama
    p2.tik(1060.0, G, (1, 2, 3), "WYPAD", "A", sesja())
    assert wczytaj(s)["na_spocie_od"] == 1000.0, wczytaj(s)


def test_alarm_zapisuje_natychmiast_i_trwale():
    s = stan_dir(tmpdir())
    z = Zegar(5000.0)
    p = pisarz(s, z)
    p.tik(5000.0, G, (1, 2, 3), "WYPAD", "A", sesja())
    z.t = 5003.0
    assert p.alarm("ALARM: wyprawa: utkniecie: " + "x" * 400) is True
    d = wczytaj(s)
    assert d["alarm"]["kod"] == "wyprawa" and len(d["alarm"]["tekst"]) == 200 and d["alarm"]["t"] == 5003.0, d["alarm"]
    assert d["level"] == 10 and d["postac"] == "A"                           # reszta pliku nietknięta
    assert p.alarm("ALARM: wyprawa: utkniecie: " + "x" * 400) is False        # ten sam tekst < 30 s: bez zapisu
    z.t = 5040.0
    assert p.alarm("ALARM: wyprawa: utkniecie: " + "x" * 400) is True


def test_stop_auto_z_trescia_pliku_i_koniec_sesji():
    s = stan_dir(tmpdir())
    z = Zegar(7000.0)
    p = pisarz(s, z)
    p.tik(7000.0, G, (1, 2, 3), "WYPAD", "A", sesja(9))
    (s / "STOP").write_text("wyprawa: utkniecie: brak postępu na etapie 6\n")
    z.t = 7010.0
    assert p.stop("Zatrzymano (plik STOP)") is True
    d = wczytaj(s)
    assert d["stop"] == {"t": 7010.0, "powod": "wyprawa: utkniecie: brak postępu na etapie 6", "reczny": False}, d["stop"]
    assert d["koniec_sesji"] == "alarm_stop" and d["zrodlo"] == "stop"
    assert d["sesja"]["koniec"] == 7010.0 and d["sesja"]["zab"] == 9 and d["sesja"]["start"] == 900.0, d["sesja"]    # scalone, nie podmienione


def test_stop_reczny_nie_jest_alarmem():
    s = stan_dir(tmpdir())
    z = Zegar(7000.0)
    p = pisarz(s, z)
    p.tik(7000.0, G, (1, 2, 3), "WYPAD", "A", sesja())
    (s / "STOP_RECZNY").write_text("")
    z.t = 7005.0
    p.stop("Przerwano (Ctrl+C / SIGTERM)")
    d = wczytaj(s)
    assert d["stop"]["reczny"] is True and d["stop"]["powod"] == "Przerwano (Ctrl+C / SIGTERM)" and d["koniec_sesji"] is None, d


def test_nowa_sesja_bota_po_stopie_czysci_koniec():
    s = stan_dir(tmpdir())
    z = Zegar(7000.0)
    p = pisarz(s, z)
    p.tik(7000.0, G, (1, 2, 3), "WYPAD", "A", sesja())
    p.stop("x")
    assert wczytaj(s)["koniec_sesji"] == "alarm_stop"
    p2 = pisarz(s, Zegar(8000.0))
    p2.tik(8000.0, G, (1, 2, 3), "WYPAD", "A", {"start": 7990.0, "zab": 0, "gold": 0, "uh": 0})
    d = wczytaj(s)
    assert d["koniec_sesji"] is None and d["sesja"]["koniec"] is None and d["sesja"]["start"] == 7990.0, d


# ---------- logowanie ----------
def test_zdarzenia_logowania_pisza_tylko_swoje_pola():
    tmp = tmpdir()
    s = stan_dir(tmp)
    logi = s / "logi"
    p = pisarz(s, Zegar(100.0))
    p.tik(100.0, G, (1, 2, 3), "WYPAD", "A", sesja(5))
    w = ostatnie.zdarzenie_logowania(logi, "wyloguj", "wylogowano", {"proby": 1}, t=300.0)
    d = wczytaj(s)
    assert d["koniec_sesji"] == "wylogowanie" and d["w_grze_t"] == 300.0 and d["sesja"]["koniec"] == 300.0 and d["zrodlo"] == "logowanie"
    assert d["level"] == 10 and d["sesja"]["zab"] == 5 and d["dane_t"] == 100.0, d       # dane bota nietknięte, dane_t się nie rusza
    ostatnie.zdarzenie_logowania(logi, "zaloguj", "w_grze", {"zalogowany": "A", "oczekiwany": "A", "hp": 188}, t=400.0)
    d = wczytaj(s)
    assert d["koniec_sesji"] is None and d["w_grze_t"] == 400.0 and d["sesja"] == {
        "start": 400.0, "koniec": None, "zab": None, "exp_start": None, "gold": None, "uh": None}, d
    assert d["level"] == 10 and w is not None


def test_logowanie_inna_postac_lub_inny_katalog_lub_inne_zdarzenie_nie_pisze():
    tmp = tmpdir()
    s = stan_dir(tmp)
    assert ostatnie.zdarzenie_logowania(s / "logi", "zaloguj", "w_grze", {"zalogowany": "Inna", "oczekiwany": "A"}) is None
    assert ostatnie.zdarzenie_logowania(tmp / "cokolwiek", "zaloguj", "w_grze", {}) is None
    assert ostatnie.zdarzenie_logowania(s / "logi", "zaloguj", "start", {}) is None
    assert ostatnie.zdarzenie_logowania(s / "logi", "zaloguj", "koniec", {"kod": 6}) is None
    assert not (s / "ostatnie.json").exists() and not (tmp / "cokolwiek").exists()
    ostatnie.zdarzenie_logowania(s / "logi", "zaloguj", "koniec", {"kod": 0}, t=50.0)        # już w grze: tylko w_grze_t
    assert wczytaj(s)["w_grze_t"] == 50.0


def test_dziennik_logowania_hakuje_ostatnie_tylko_poza_testami():
    import logowanie
    tmp = tmpdir()
    s = stan_dir(tmp)
    dz = logowanie.Dziennik(s / "logi", "x", "wyloguj", wypisz=False)
    dz.zdarzenie("wylogowano", proby=1)                                            # RETRONIC_TESTY=1: bez zapisu ostatnie.json
    assert not (s / "ostatnie.json").exists()
    del os.environ["RETRONIC_TESTY"]
    try:
        dz.zdarzenie("wylogowano", proby=1)
        dz.zdarzenie("start", opcje={})
    finally:
        os.environ["RETRONIC_TESTY"] = "1"
    assert wczytaj(s)["koniec_sesji"] == "wylogowanie"
    assert (s / "logi" / "logowanie.jsonl").read_text().count("\n") == 3             # dziennik jsonl działa jak dotąd
    logowanie.Dziennik(None, "x", "wyloguj", wypisz=False).zdarzenie("wylogowano")   # katalog None: nie rzuca


# ---------- telemetria: podpięcie Pisarza ----------
def tele(logi, **kw):
    import telemetria
    tt = telemetria.Telemetria(logi, zegar=kw.pop("zegar", Zegar(1000.0)), zapis=kw.pop("zapis", True))
    tt.ostatnie = tt.ostatnie and ostatnie.Pisarz(tt.ostatnie.katalog, zegar=tt.zegar, miasto=lambda poz: (None, False))
    return tt


def cb_atrapa():
    return types.SimpleNamespace(stan="WYPAD", cel=None, ignorowane={}, zegar=lambda: 1000.0, droga_bez_blokad=0,
                                 droga=lambda *a, **k: [1], postac=types.SimpleNamespace(nazwa="Wydra"))


def test_telemetria_podpina_pisarza_tylko_dla_prawdziwego_zapisu():
    tmp = tmpdir()
    s = stan_dir(tmp)
    assert tele(s / "logi").ostatnie is not None
    assert tele(s / "logi", zapis=False).ostatnie is None                       # zapis wyłączony (testy, skrypty pomocnicze)
    assert tele(tmp / "inny_katalog", zapis=True).ostatnie is None              # katalog nie jest logi/


def test_telemetria_probka_zapisuje_i_atrapa_ja_nie():
    tmp = tmpdir()
    s = stan_dir(tmp)
    z = Zegar(1000.0)
    t = tele(s / "logi", zegar=z)
    cb = cb_atrapa()
    t.probka(cb, dict(G, proc=80), (100, 100, 7), [])
    d = wczytaj(s)
    assert d["postac"] == "Wydra" and d["level"] == 10 and d["poz"] == [100, 100, 7] and d["stan_bota"] == "WYPAD", d
    assert d["sesja"]["start"] == t.sesja and d["sesja"]["zab"] == 0
    s2 = stan_dir(tmp, "ja")
    t2 = tele(s2 / "logi", zegar=Zegar(1000.0))
    cb2 = cb_atrapa()
    cb2.postac = types.SimpleNamespace(nazwa="Ja")
    t2.nazwa_postaci = "Ja"
    t2.probka(cb2, dict(G, proc=80), (100, 100, 7), [])
    assert not (s2 / "ostatnie.json").exists()                                  # R0a: atrapa „Ja” nie pisze na dysk


def test_telemetria_linia_alarm_i_ostatnie_stop():
    tmp = tmpdir()
    s = stan_dir(tmp)
    z = Zegar(1000.0)
    t = tele(s / "logi", zegar=z)
    t.probka(cb_atrapa(), dict(G, proc=80), (100, 100, 7), [])
    z.t = 1010.0
    t.linia("[WALKA] atakuję Rat")                                              # zwykła linia: bez zapisu alarmu
    assert wczytaj(s).get("alarm") is None
    t.linia("ALARM: niskie HP 21%")
    assert wczytaj(s)["alarm"]["kod"] == "niskie HP 21%" and wczytaj(s)["alarm"]["t"] == 1010.0
    (s / "STOP").write_text("niskie HP 21%")
    z.t = 1012.0
    assert t.ostatnie_stop("Zatrzymano") is True
    d = wczytaj(s)
    assert d["stop"]["powod"] == "niskie HP 21%" and d["koniec_sesji"] == "alarm_stop", d
    assert tele(s / "logi", zapis=False).ostatnie_stop("x") is False


def test_telemetria_nie_przenosi_bledu_zapisu_do_petli_bota():
    tmp = tmpdir()
    s = stan_dir(tmp)
    t = tele(s / "logi")

    def bum(*a, **k):
        raise RuntimeError("bum")
    t.ostatnie.tik = bum
    t.ostatnie.alarm = bum
    t.ostatnie.stop = bum
    assert t.probka(cb_atrapa(), dict(G, proc=80), (100, 100, 7), []) is not None
    t.linia("ALARM: x")
    assert t.ostatnie_stop("x") is False


# ---------- backfill ----------
def dopisz(p, rek):
    with open(p, "a", encoding="utf-8") as f:
        for r in rek:
            f.write((json.dumps(r) if isinstance(r, dict) else r) + "\n")


def atrapa_instancji(korzen, id_, *, exp=9769, sesja_ep=1000.0, hp_login=188, wylogowanie=False, bez_telemetrii=False):
    s = korzen / "instancje" / id_
    (s / "logi").mkdir(parents=True)
    (s / "profil.json").write_text(json.dumps({"postac": "Kolanosh", "nadzor": True}))
    (korzen / f"ostatni_start.{id_}.env").write_text("MAPA=trolle_edron\nTRYB=ostrozny\\,ml\n")
    logi = s / "logi"
    if not bez_telemetrii:
        dopisz(logi / "telemetria-20261021.jsonl", [
            {"t": sesja_ep + 5, "typ": "probka", "stan": "IDZ", "poz": [33121, 31756, 9], "hp": 90, "mana": 30, "max_mana": 95,
             "exp": exp - 50, "sesja": sesja_ep},
            {"t": sesja_ep + 300, "typ": "probka", "stan": "WYPAD", "poz": [33121, 31756, 9], "hp": 80, "mana": 32, "max_mana": 95,
             "exp": exp, "sesja": sesja_ep},
            {"t": sesja_ep + 301, "typ": "zdarzenie_bez_exp", "sesja": sesja_ep}])
        dopisz(logi / "ekonomia-20261021.jsonl", [
            {"t": sesja_ep, "typ": "start", "postac": "Kolanosh", "sesja": sesja_ep},
            {"t": sesja_ep + 5, "typ": "tik", "exp": exp - 50, "sesja": sesja_ep, "gold_razem": 0, "uh_razem": 0, "zab_razem": 0},
            {"t": sesja_ep + 300, "typ": "tik", "exp": exp, "sesja": sesja_ep, "gold_razem": 13, "uh_razem": 2, "zab_razem": 9}])
    dopisz(logi / "logowanie.jsonl", [
        {"t": sesja_ep - 60, "zdarzenie": "w_grze", "akcja": "zaloguj", "hp": hp_login},
        *([{"t": sesja_ep + 400, "zdarzenie": "wylogowano", "akcja": "wyloguj"}] if wylogowanie else [])])
    (logi / "tryb.log").write_text(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(sesja_ep - 50)) + " [TRYB] mapa trolle_edron: x\n")
    return s


def test_backfill_odtwarza_dane_i_oznacza_przyblizenia():
    korzen = tmpdir()
    atrapa_instancji(korzen, "a")
    pola, uwagi = ostatnie.zbierz(korzen, "a", teraz=5000.0, miasto=lambda poz: ("edron", False))
    assert (pola["postac"], pola["exp"], pola["level"], pola["level_proc"]) == ("Kolanosh", 9769, 10, 12.7), pola
    assert pola["poz"] == [33121, 31756, 9] and pola["mana"] == 32 and pola["max_mana"] == 95 and pola["stan_bota"] == "WYPAD"
    assert pola["hp"] is None and pola["max_hp"] == 188 and pola["przyblizone"] == ["max_hp"] and uwagi, (pola["hp"], uwagi)
    assert pola["sesja"] == {"start": 1000.0, "koniec": 1300.0, "zab": 9, "exp_start": 9719, "gold": 13, "uh": 2}, pola["sesja"]
    assert pola["mapa"] == "trolle_edron" and pola["tryb"] == ["ostrozny", "ml"] and pola["na_spocie_od"] is not None
    assert pola["dane_t"] == 1300.0 and pola["w_grze_t"] == 1300.0 and pola["koniec_sesji"] == "znikniecie"
    assert pola["miasto"] == "edron" and pola["ml"] is None and pola["alarm"] is None and pola["stop"] is None


def test_backfill_wylogowanie_stop_i_alarm():
    korzen = tmpdir()
    s = atrapa_instancji(korzen, "a", wylogowanie=True)
    pola, _ = ostatnie.zbierz(korzen, "a", teraz=5000.0, miasto=lambda poz: (None, False))
    assert pola["koniec_sesji"] == "wylogowanie" and pola["w_grze_t"] == 1400.0, pola
    korzen2 = tmpdir()
    s2 = atrapa_instancji(korzen2, "b")
    (s2 / "STOP").write_text("wyprawa: utkniecie: brak postępu\n")
    os.utime(s2 / "STOP", (1310.0, 1310.0))
    dopisz(s2 / "logi" / "mozg-20261021-1000.log", ["10:00:01 start", "10:05:00 ALARM: wyprawa: utkniecie: brak postępu"])
    pola2, _ = ostatnie.zbierz(korzen2, "b", teraz=5000.0, miasto=lambda poz: (None, False))
    assert pola2["koniec_sesji"] == "alarm_stop" and pola2["stop"]["powod"] == "wyprawa: utkniecie: brak postępu" and \
        pola2["stop"]["reczny"] is False, pola2["stop"]
    assert pola2["alarm"]["kod"] == "wyprawa" and pola2["alarm"]["t"] > 1e9, pola2["alarm"]
    os.utime(s2 / "STOP", (500.0, 500.0))                                          # STOP starszy niż ostatnie wejście: nie ta sesja
    assert ostatnie.zbierz(korzen2, "b", teraz=5000.0, miasto=lambda poz: (None, False))[0]["koniec_sesji"] == "znikniecie"


def test_backfill_bez_telemetrii_zostawia_null():
    korzen = tmpdir()
    atrapa_instancji(korzen, "a", bez_telemetrii=True)
    pola, uwagi = ostatnie.zbierz(korzen, "a", teraz=5000.0, miasto=lambda poz: (None, False))
    for k in ("exp", "level", "level_proc", "poz", "pietro", "hp", "mana", "sesja", "dane_t"):
        assert pola[k] is None, (k, pola[k])
    assert pola["w_grze_t"] == 940.0 and pola["max_hp"] == 188 and any("telemetrii" in u for u in uwagi)


def test_backfill_sucho_nic_nie_zapisuje_i_tylko_offline():
    korzen = tmpdir()
    atrapa_instancji(korzen, "off")
    atrapa_instancji(korzen, "on")
    (korzen / "instancje" / "_wspolne").mkdir()
    (korzen / "instancje" / "pusta" / "logi").mkdir(parents=True)

    def czy_offline(id_):
        return (False, "działa bot") if id_ == "on" else (True, "")
    suche = ostatnie.uzupelnij(korzen, sucho=True, czy_offline=czy_offline, teraz=5000.0, miasto=lambda p: (None, False))
    assert {w["id"]: w["decyzja"] for w in suche} == {"off": "sucho", "on": "pomijam", "pusta": "pomijam"}, suche
    assert not list(korzen.glob("instancje/*/ostatnie.json")), "tryb --sucho nie może pisać"
    real = ostatnie.uzupelnij(korzen, sucho=False, czy_offline=czy_offline, teraz=5000.0, miasto=lambda p: (None, False))
    assert {w["id"]: w["decyzja"] for w in real} == {"off": "zapis", "on": "pomijam", "pusta": "pomijam"}, real
    d = wczytaj(korzen / "instancje" / "off")
    assert d["zrodlo"] == "backfill" and d["level"] == 10 and d["zapisano"] == 5000.0 and d["przyblizone"] == ["max_hp"]
    assert not (korzen / "instancje" / "on" / "ostatnie.json").exists()          # online nie ruszamy


def test_backfill_sprawdza_offline_tuz_przed_zapisem_i_nie_cofa_danych_bota():
    korzen = tmpdir()
    atrapa_instancji(korzen, "a")
    wywolania = []

    def czy_offline(id_):
        wywolania.append(id_)
        return (len(wywolania) == 1, "ruszył bot")           # pierwsze sprawdzenie: offline, drugie (tuż przed zapisem): już online
    w = ostatnie.uzupelnij(korzen, ["a"], sucho=False, czy_offline=czy_offline, teraz=5000.0, miasto=lambda p: (None, False))
    assert w[0]["decyzja"] == "pomijam" and "tuż przed zapisem" in w[0]["powod"] and len(wywolania) == 2, w
    assert not (korzen / "instancje" / "a" / "ostatnie.json").exists()
    ostatnie.zapisz(korzen / "instancje" / "a", "bot", {"dane_t": 99999.0, "level": 20}, t=99999.0)    # świeższy zapis bota
    w = ostatnie.uzupelnij(korzen, ["a"], sucho=False, czy_offline=lambda i: (True, ""), teraz=5000.0, miasto=lambda p: (None, False))
    assert w[0]["decyzja"] == "pomijam" and "świeższy" in w[0]["powod"], w
    assert wczytaj(korzen / "instancje" / "a")["level"] == 20


def test_backfill_nie_rusza_ml():
    korzen = tmpdir()
    s = atrapa_instancji(korzen, "a")
    ostatnie.ml_ustaw(s, 17, t=10.0)
    ostatnie.uzupelnij(korzen, ["a"], sucho=False, czy_offline=lambda i: (True, ""), teraz=5000.0, miasto=lambda p: (None, False))
    d = wczytaj(s)
    assert d["ml"] == 17 and d["ml_zrodlo"] == "reczny" and d["level"] == 10, d


def test_ml_ustaw_waliduje_i_pisze_tylko_pola_ml():
    s = stan_dir(tmpdir())
    ostatnie.zapisz(s, "bot", {"level": 12, "postac": "A", "sesja": {"zab": 3}}, t=1.0)
    w = ostatnie.ml_ustaw(s, 21, t=50.0)
    assert (w["ml"], w["ml_proc"], w["ml_t"], w["ml_zrodlo"], w["zrodlo"]) == (21, None, 50.0, "reczny", "reczny"), w
    assert w["level"] == 12 and w["postac"] == "A" and w["sesja"] == {"zab": 3}
    for zle in (-1, 1000, 3.5, "5", None, True):
        try:
            ostatnie.ml_ustaw(s, zle)
        except ValueError:
            continue
        raise AssertionError(f"przyjęto {zle!r}")
    assert wczytaj(s)["ml"] == 21


# ---------- kontrakt `okno_api.py stan` i `ml-ustaw` ----------
FAKE_PANEL = '''import json, os
i = os.environ.get("RETRONIC_ID", "")
d = os.path.dirname(os.path.abspath(__file__))
w = {"text": "RT", "tooltip": "Retronic: działa\\nHP 100/200  mana 30/60", "class": "dziala", "alt": "dziala", "id": i}
p = os.path.join(d, "panel_dodatek." + (i or "glowna"))
if os.path.exists(p):
    w.update(json.load(open(p)))
print(json.dumps(w))
'''
KLUCZE_PRZEGLADU = {"stan", "w_grze", "test", "zab_h", "exp_h", "dane_wiek_s", "na_spocie_od", "ostatni_alarm", "alarm_24h",
                    "koniec_sesji", "nadzor", "stop", "stracony", "rola"}      # stracony (24.10 13:45), rola (24.10: np. "bank")
KLUCZE_OSTATNIE = set(ostatnie.KLUCZE) | {"wiek_s", "blad"}


def korzen_okna(instancje):
    """instancje: {id: {"klasa": ..., "gra": bool, "sway": bool, "bot": bool, "profil": dict|None, "stop": [..], "ostatnie": dict|None}}"""
    tmp = tmpdir()
    r = tmp / "pomocnik"
    (r / "instancje" / "_wspolne").mkdir(parents=True)
    (r / "panel.py").write_text(FAKE_PANEL)
    (r / "logi").mkdir()
    (tmp / "proc").mkdir()
    (tmp / "rt").mkdir()
    pid = 100
    for id_, k in instancje.items():
        s = r / "instancje" / id_
        (s / "logi").mkdir(parents=True)
        if k.get("profil") is not None:
            (s / "profil.json").write_text(json.dumps(k["profil"]))
        for nazwa in k.get("stop", []):
            (s / nazwa).write_text("")
        klasa = k.get("klasa") or ("stop" if k.get("gra") else "brak")          # jak prawdziwy panel.py: bez gry „brak”
        (r / f"panel_dodatek.{id_}").write_text(json.dumps({"class": klasa}))
        if k.get("ostatnie") is not None:
            (s / "ostatnie.json").write_text(json.dumps(k["ostatnie"]))
        if k.get("gra"):
            # gniazdo gry: ścieżka z instancja.sciezki (runtime w tmp/rt)
            import instancja
            sc = instancja.sciezki(id_, str(tmp / "rt"), katalog=r, gra=r.parent)       # jawny katalog w tmp: NIGDY prawdziwy XDG_RUNTIME_DIR
            assert str(tmp) in str(sc.gniazdo), sc.gniazdo
            Path(sc.gniazdo).parent.mkdir(parents=True, exist_ok=True)
            Path(sc.gniazdo).write_text("")
        if k.get("bot"):
            pid += 1
            d = tmp / "proc" / str(pid)
            d.mkdir()
            (d / "cmdline").write_bytes(b"\0".join([b"python3", b"mozg.py"]) + b"\0")
            (d / "environ").write_bytes(f"RETRONIC_ID={id_}\0RETRONIC_POSTAC=Nick\0".encode())
    return tmp


def okno(tmp, *args, teraz=TERAZ):
    env = dict(os.environ, RETRONIC_OKNO_KATALOG=str(tmp / "pomocnik"), RETRONIC_OKNO_PROC=str(tmp / "proc"),
               RETRONIC_OKNO_TERAZ=str(teraz), XDG_RUNTIME_DIR=str(tmp / "rt"))
    env.pop("RETRONIC_ID", None)
    p = subprocess.run([sys.executable, "-I", str(OKNO_API), *args], capture_output=True, env=env, timeout=30)
    try:
        return p.returncode, json.loads(p.stdout)
    except ValueError:
        return p.returncode, {"ok": None, "surowe": p.stdout.decode(errors="replace"), "stderr": p.stderr.decode(errors="replace")}


def pliki_ostatnie(**nad):
    d = {"v": 1, "zapisano": TERAZ - 20, "zrodlo": "bot", "dane_t": TERAZ - 20, "postac": "Nick", "exp": 12000, "level": 11,
         "level_proc": 40.0, "hp": 150, "max_hp": 200, "mana": 40, "max_mana": 95, "poz": [1, 2, 7], "pietro": 7, "mapa": "raty",
         "tryb": ["ostrozny"], "stan_bota": "WYPAD", "na_spocie_od": TERAZ - 1800, "w_grze_t": TERAZ - 20,
         "sesja": {"start": TERAZ - 3620, "koniec": None, "zab": 60, "exp_start": 6000, "gold": 10, "uh": 1},
         "alarm": None, "stop": None, "koniec_sesji": None}
    d.update(nad)
    return d


def inst(kod_dict, id_):
    return next(i for i in kod_dict["instancje"] if i["id"] == id_)


def test_stan_online_ma_kontrakt_i_liczy_zab_h_exp_h():
    tmp = korzen_okna({"on": {"gra": True, "bot": True, "klasa": "dziala", "profil": {"postac": "Nick"}, "ostatnie": pliki_ostatnie()}})
    kod, d = okno(tmp, "stan")
    assert kod == 0 and d["ok"] is True, d
    w = inst(d, "on")
    assert w["blad"] is None, w["blad"]
    assert set(w["ostatnie"]) == KLUCZE_OSTATNIE, set(w["ostatnie"]) ^ KLUCZE_OSTATNIE
    assert w["ostatnie"]["wiek_s"] == 20.0 and w["ostatnie"]["level"] == 11 and w["ostatnie"]["blad"] is None
    p = w["przeglad"]
    assert set(p) == KLUCZE_PRZEGLADU, set(p) ^ KLUCZE_PRZEGLADU
    assert p["stan"] == "bot_dziala" and p["w_grze"] is True and p["test"] is False
    # (dane_t − start) = 3600 s: 60 zabić -> 60/h; (12000 − 6000) exp -> 6000/h
    assert p["zab_h"] == 60.0 and p["exp_h"] == 6000, (p["zab_h"], p["exp_h"])
    assert p["na_spocie_od"] == TERAZ - 1800 and p["ostatni_alarm"] is None and p["alarm_24h"] is False
    assert p["nadzor"] == {"aktywny": True, "powod": None, "do": None, "zrodlo": None}, p["nadzor"]
    assert p["stop"] == {"auto": False, "reczny": False} and p["dane_wiek_s"] == 20.0
    assert w["gracz"] and w["klasa"] == "dziala"                                  # dotychczasowe pola bez zmian


def test_stan_stracony_i_rola_z_profilu():
    """24.10 (Karol): `stracony` (bool) i `rola` (tekst małymi literami albo null) z profil.json dla okna Przeglądu."""
    tmp = korzen_okna({
        "zwykla": {"profil": {"postac": "A", "nadzor": False}},
        "bank": {"profil": {"postac": "B", "nadzor": False, "rola": "bank"}},
        "bank2": {"profil": {"postac": "C", "nadzor": False, "rola": " Bank "}},
        "stracona": {"profil": {"postac": "D", "nadzor": False, "stracony": "2026-10-24 14:11:00: wyeliminowana"}},
        "pusta": {"profil": {"postac": "E", "rola": "", "stracony": ""}},
        "zla": {"profil": {"postac": "F", "rola": 5}}})
    kod, d = okno(tmp, "stan")
    assert kod == 0 and d["ok"] is True, d
    pole = {i: (inst(d, i)["przeglad"]["stracony"], inst(d, i)["przeglad"]["rola"])
            for i in ("zwykla", "bank", "bank2", "stracona", "pusta", "zla")}
    assert pole == {"zwykla": (False, None), "bank": (False, "bank"), "bank2": (False, "bank"), "stracona": (True, None),
                    "pusta": (False, None), "zla": (False, None)}, pole


def test_stan_nieaktualne_dane_nie_daja_zab_h_exp_h():
    stare = pliki_ostatnie(dane_t=TERAZ - 600, zapisano=TERAZ - 600)
    tmp = korzen_okna({"on": {"gra": True, "bot": True, "klasa": "dziala", "profil": {}, "ostatnie": stare}})
    p = inst(okno(tmp, "stan")[1], "on")["przeglad"]
    assert p["stan"] == "bot_dziala" and p["zab_h"] is None and p["exp_h"] is None and p["dane_wiek_s"] == 600.0, p
    tmp = korzen_okna({"on": {"gra": True, "bot": True, "klasa": "dziala", "profil": {},
                              "ostatnie": pliki_ostatnie(sesja={"start": TERAZ - 20, "zab": 1, "exp_start": 11990})}})
    p = inst(okno(tmp, "stan")[1], "on")["przeglad"]
    assert p["zab_h"] is None and p["exp_h"] is None, p                            # sesja krótsza niż 60 s: bez sztucznej średniej
    tmp = korzen_okna({"on": {"gra": True, "bot": True, "klasa": "dziala", "profil": {},
                              "ostatnie": pliki_ostatnie(sesja={"start": TERAZ - 3620, "zab": None, "exp_start": None})}})
    p = inst(okno(tmp, "stan")[1], "on")["przeglad"]
    assert p["zab_h"] is None and p["exp_h"] is None, p                            # nieznane liczniki = null, nie 0


def test_stan_offline_ostatnie_wyszarzone_bez_zab_h():
    ost = pliki_ostatnie(zapisano=TERAZ - 7200, dane_t=TERAZ - 7200, w_grze_t=TERAZ - 7200, koniec_sesji="znikniecie",
                         alarm={"t": TERAZ - 7300, "tekst": "ALARM: x", "kod": "x"})
    tmp = korzen_okna({"off": {"profil": {"postac": "N"}, "ostatnie": ost}})
    w = inst(okno(tmp, "stan")[1], "off")
    p = w["przeglad"]
    assert p["stan"] == "offline" and p["w_grze"] is False and p["zab_h"] is None and p["exp_h"] is None, p
    assert p["ostatni_alarm"]["kod"] == "x" and p["alarm_24h"] is True and p["koniec_sesji"] == "znikniecie"
    assert w["ostatnie"]["wiek_s"] == 7200.0 and w["ostatnie"]["level"] == 11


def test_stan_bez_ostatnie_json_i_z_uszkodzonym():
    tmp = korzen_okna({"brak": {"profil": {}}, "zepsuty": {"profil": {}}})
    (tmp / "pomocnik" / "instancje" / "zepsuty" / "ostatnie.json").write_text("{nie json")
    d = okno(tmp, "stan")[1]
    w = inst(d, "brak")
    assert w["ostatnie"] is None and w["przeglad"]["stan"] == "offline" and w["przeglad"]["zab_h"] is None and w["blad"] is None, w
    z = inst(d, "zepsuty")
    assert z["ostatnie"]["blad"] and z["ostatnie"]["level"] is None and set(z["ostatnie"]) == KLUCZE_OSTATNIE, z["ostatnie"]
    assert z["przeglad"]["stan"] == "offline"


def test_stan_reguly_przegladu_stan():
    tmp = korzen_okna({
        "alarm": {"gra": True, "bot": True, "klasa": "alarm", "profil": {}},
        "karol": {"gra": True, "klasa": "stop", "profil": {}, "stop": ["STOP_RECZNY"]},
        "dziala": {"gra": True, "bot": True, "klasa": "dziala", "profil": {}, "stop": ["STOP_RECZNY"]},
        "zatrz": {"gra": True, "klasa": "stop", "profil": {}, "stop": ["STOP"]},
        "zatrz2": {"gra": True, "klasa": "stop", "profil": {}},
        "zaw": {"profil": {"nadzor": False, "nadzor_do": "2026-10-24 08:30"}},
        "zaw2": {"profil": {"nadzor": False}},
        "off": {"profil": {}},
        "test1": {"profil": {}},
    })
    d = okno(tmp, "stan")[1]
    stany = {i["id"]: i["przeglad"]["stan"] for i in d["instancje"] if i["id"]}
    assert stany == {"alarm": "alarm", "karol": "karol_gra", "dziala": "bot_dziala", "zatrz": "zatrzymany", "zatrz2": "zatrzymany",
                     "zaw": "zawieszony", "zaw2": "zawieszony", "off": "offline", "test1": "offline"}, stany
    assert inst(d, "test1")["przeglad"]["test"] is True and inst(d, "test1")["przeglad"]["nadzor"]["zrodlo"] == "test"
    assert inst(d, "off")["przeglad"]["test"] is False
    assert inst(d, "karol")["przeglad"]["stop"] == {"auto": False, "reczny": True}
    assert inst(d, "zatrz")["przeglad"]["stop"] == {"auto": True, "reczny": False}


def test_stan_nadzor_zgodny_z_grafik_poza_nadzorem_profil_kolanosha():
    import grafik
    from datetime import datetime
    profil = {"postac": "Kolanosh", "nadzor": False, "nadzor_do": "2026-10-24 08:30"}
    tmp = korzen_okna({"kolanoth": {"profil": profil}, "zwykly": {"profil": {"nadzor": False}}, "wraca": {"profil": {
        "nadzor": False, "nadzor_do": "2026-10-20 08:30"}}, "konf": {"profil": {}}})
    (tmp / "pomocnik" / "instancje" / "_wspolne" / "nadzor_konfig.json").write_text(
        json.dumps({"postacie": {"konf": {"nadzor_do": "2026-11-01 00:00"}}}))
    d = okno(tmp, "stan")[1]
    teraz_dt = datetime.fromtimestamp(TERAZ)
    for id_, pr, wpis in (("kolanoth", profil, None), ("zwykly", {"nadzor": False}, None),
                          ("wraca", {"nadzor": False, "nadzor_do": "2026-10-20 08:30"}, None),
                          ("konf", {}, {"nadzor_do": "2026-11-01 00:00"})):
        oczekiwany = grafik.poza_nadzorem(pr, wpis, teraz_dt)
        n = inst(d, id_)["przeglad"]["nadzor"]
        assert n["powod"] == oczekiwany and n["aktywny"] == (oczekiwany is None), (id_, n, oczekiwany)
    assert inst(d, "kolanoth")["przeglad"]["nadzor"] == {"aktywny": False, "do": "2026-10-24 08:30", "zrodlo": "profil",
                                                         "powod": "postać tymczasowo poza nadzorem do 2026-10-24 08:30 (nadzor_do)"}
    assert inst(d, "wraca")["przeglad"]["nadzor"]["aktywny"] is True                # data minęła: wraca do nadzoru
    assert inst(d, "zwykly")["przeglad"]["nadzor"] == {"aktywny": False, "do": None, "zrodlo": "profil",
                                                       "powod": "postać poza nadzorem (nadzor: false)"}
    assert inst(d, "konf")["przeglad"]["nadzor"]["zrodlo"] == "konfiguracja"


def test_stan_instancja_glowna_nie_psuje():
    tmp = korzen_okna({"a": {"profil": {}}})
    d = okno(tmp, "stan")[1]
    g = inst(d, "")
    assert g["przeglad"]["nadzor"]["zrodlo"] == "glowna" and g["przeglad"]["nadzor"]["aktywny"] is False
    assert g["ostatnie"] is None


def test_ml_ustaw_cli_pisze_tylko_ml_i_pojawia_sie_w_stanie():
    ost = pliki_ostatnie()
    tmp = korzen_okna({"a": {"profil": {}, "ostatnie": ost}})
    plik = tmp / "pomocnik" / "instancje" / "a" / "ostatnie.json"
    przed = json.loads(plik.read_text())
    kod, d = okno(tmp, "ml-ustaw", "--instancja", "a", "23")
    assert kod == 0 and d["ok"] is True and d["ml"] == 23 and d["ml_zrodlo"] == "reczny" and d["instancja"] == "a", (kod, d)
    po = json.loads(plik.read_text())
    zmienione = {k for k in set(przed) | set(po) if przed.get(k) != po.get(k)}
    assert zmienione <= {"ml", "ml_proc", "ml_t", "ml_zrodlo", "zapisano", "zrodlo"} and {"ml", "ml_t", "ml_zrodlo"} <= zmienione, zmienione     # nic poza polami ML i znacznikiem zapisu
    assert po["zrodlo"] == "reczny" and po["ml_t"] == TERAZ
    w = inst(okno(tmp, "stan")[1], "a")
    assert w["ostatnie"]["ml"] == 23 and w["ostatnie"]["ml_zrodlo"] == "reczny"


def test_ml_ustaw_cli_bledy_nie_pisza():
    tmp = korzen_okna({"a": {"profil": {}}})
    plik = tmp / "pomocnik" / "instancje" / "a" / "ostatnie.json"
    for args in (["--instancja", "a", "-5"], ["--instancja", "a", "1000"], ["--instancja", "a", "abc"], ["--instancja", "", "5"],
                 ["--instancja", "nie_ma", "5"], ["5"]):
        kod, d = okno(tmp, "ml-ustaw", *args)
        assert kod in (1, 2) and d["ok"] is False, (args, kod, d)
    assert not plik.exists()
    kod, d = okno(tmp, "ml-ustaw", "--instancja", "a", "0")                        # 0 to poprawny ML (nie „brak”)
    assert kod == 0 and wczytaj(plik.parent)["ml"] == 0


def test_stan_czas_odczytu_z_dziesiecioma_instancjami_miesci_sie_w_budzecie():
    ids = {f"p{i}": {"gra": i % 2 == 0, "bot": i % 2 == 0, "klasa": "dziala" if i % 2 == 0 else None, "profil": {},
                     "ostatnie": pliki_ostatnie()} for i in range(10)}
    tmp = korzen_okna(ids)
    kod, d = okno(tmp, "stan")
    assert kod == 0 and len(d["instancje"]) == 11 and d["czas_odczytu_s"] < 1.9, d["czas_odczytu_s"]
    assert all(i["blad"] is None for i in d["instancje"]), [i["blad"] for i in d["instancje"] if i["blad"]]
    print(f"     10 instancji: czas_odczytu_s = {d['czas_odczytu_s']}")


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
                print("BŁĄD", nazwa, repr(e)[:600])
                traceback.print_exc()
    print(f"{ok}/{ok + zle} testów zielonych")
    sys.exit(1 if zle else 0)
