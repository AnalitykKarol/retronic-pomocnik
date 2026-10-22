#!/usr/bin/env python3
"""22.10: kontrola okien po starcie (okna_start.py). Offline: zrzuty syntetyczne, atrapa myszy i pamięci, zero inputu do gry,
zero powiadomień (powiadom_fn to atrapa), stan powiadomień w katalogu tymczasowym."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["RETRONIC_TESTY"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image  # noqa: E402

import loot  # noqa: E402
import okna_start as O  # noqa: E402

SZER, WYS = 1280, 960
TMP = Path(tempfile.mkdtemp(prefix="okna_start_test_"))
O._plik_stanu = lambda: TMP / "okna_start_stan.json"


def obraz(y0=None):
    """Zrzut z czerwonym paskiem HP (kolumny szer-140..szer-110) od wiersza y0; y0 None = klient poza grą."""
    im = Image.new("RGB", (SZER, WYS), (30, 30, 30))
    if y0 is not None:
        for y in range(y0, y0 + 10):
            for x in range(SZER - 140, SZER - 110):
                im.putpixel((x, y), (220, 30, 30))
    return im


class Slot:
    def __init__(self, x, y, bok=34):
        self.x, self.y, self.bok = x, y, bok


class Okno:
    def __init__(self, gora, rzedy=3):
        self.sloty = [Slot(1005 + 37 * k, gora + 18 + 37 * w) for w in range(rzedy) for k in range(4)]
        self.tytul = None


def kon(nazwa, numer=0, przedmioty=()):
    return {"nazwa": nazwa, "numer": numer, "id": None, "pojemnosc": 12, "przedmioty": list(przedmioty)}


def role(*nazwy):
    return O.role_z_pamieci([kon(n, i) for i, n in enumerate(nazwy)])


UKL_OK = {"minimapa": "zwinieta", "plecak_ekw": (1195, 163), "prawo": 1276}


def kody(w):
    return [p["kod"] for p in w["problemy"]]


# --- ocena ---------------------------------------------------------------------------------------------

def test_ok_jeden_plecak_i_zwloki():
    w = O.ocen(UKL_OK, role("backpack", "dead rat"))
    assert w["stan"] == "ok" and w["plecaki"] == 1 and w["zwloki"] == 1 and w["problemy"] == []


def test_minimapa_rozwinieta_do_naprawy():
    w = O.ocen(dict(UKL_OK, minimapa="rozwinieta"), role("backpack"))
    assert kody(w) == ["minimapa_rozwinieta"] and w["problemy"][0]["naprawa"] == "zwin_minimape" and w["stan"] == "do_naprawy"


def test_brak_plecaka_z_pamieci_do_naprawy():
    w = O.ocen(UKL_OK, role("dead rat"))
    assert kody(w) == ["brak_plecaka"] and w["problemy"][0]["naprawa"] == "otworz_plecak" and w["stan"] == "do_naprawy"


def test_brak_plecaka_z_ekranu_tylko_powiadomienie():
    w = O.ocen(UKL_OK, role("dead rat"), zrodlo="ekran")
    assert kody(w) == ["brak_plecaka"] and w["problemy"][0]["naprawa"] is None and w["stan"] == "reczne"


def test_dwa_okna_backpack_wymagaja_czlowieka():
    w = O.ocen(UKL_OK, role("backpack", "backpack"))
    assert kody(w) == ["kilka_plecakow"] and w["problemy"][0]["naprawa"] is None and w["stan"] == "reczne"
    assert "zamknij" in w["problemy"][0]["reczne"]


def test_jedyny_plecak_z_samymi_runami_jest_niejednoznaczny():
    run = {"id": 3147, "slot": 0, "ilosc": 1}
    r = O.role_z_pamieci([kon("backpack", 0, [run, dict(run, slot=1), dict(run, slot=2)])])
    assert r[0]["rola"] == "runy"
    w = O.ocen(UKL_OK, r)
    assert kody(w) == ["plecak_niejednoznaczny"] and w["problemy"][0]["naprawa"] is None


def test_purple_backpack_plus_plecak_lupu_ok():
    w = O.ocen(UKL_OK, role("backpack", "purple backpack"), runy_potrzebne=True)
    assert w["stan"] == "ok" and w["runy"] == 1 and w["ostrzezenia"] == []


def test_depo_nie_liczy_sie_jako_plecak():
    w = O.ocen(UKL_OK, role("locker", "depot chest", "backpack"))
    assert w["stan"] == "ok" and w["depo"] == 2 and w["plecaki"] == 1


def test_poza_gra_nic_do_zrobienia():
    w = O.ocen({"minimapa": None, "plecak_ekw": None, "prawo": 1276}, [])
    assert w["stan"] == "poza_gra" and w["problemy"] == []


# --- okno ucięte dołem ---------------------------------------------------------------------------------

def test_okno_plecaka_uciete_dolem_to_ostrzezenie():
    im = obraz(78)
    gora = WYS - 60                      # sloty wystają poza zrzut
    o = Okno(gora)
    w = O.ostrzezenia_okien(im, [(o, "plecak")])
    assert [k for k, _ in w] == ["okno_uciete"]


def test_okno_depo_uciete_dolem_jest_pomijane():
    assert O.ostrzezenia_okien(obraz(78), [(Okno(WYS - 60), "depo"), (Okno(WYS - 60), "zwloki")]) == []


def test_okno_w_calosci_widoczne_bez_ostrzezenia():
    assert O.ostrzezenia_okien(obraz(78), [(Okno(300), "plecak")]) == []


# --- odczyt z syntetycznego zrzutu ---------------------------------------------------------------------

def _podmien(okna, przypisane):
    stare = (loot.znajdz_okna, loot.dopasuj_okna, loot._nazwa_tytulu)
    loot.znajdz_okna = lambda im: okna
    loot.dopasuj_okna = lambda im, o, k: (przypisane, None) if przypisane is not None else (None, "niezgodne z ekranem (4 slotów)")
    loot._nazwa_tytulu = lambda im, o: "backpack"
    return stare


def _przywroc(stare):
    loot.znajdz_okna, loot.dopasuj_okna, loot._nazwa_tytulu = stare


def test_odczyt_minimapa_rozwinieta_i_brak_plecaka():
    stare = _podmien([], None)
    try:
        w, im = O.odczyt(obraz(207), lambda: ([kon("dead rat")], None))
    finally:
        _przywroc(stare)
    assert w["minimapa"] == "rozwinieta" and set(kody(w)) == {"minimapa_rozwinieta", "brak_plecaka"}
    assert w["uklad"]["plecak_ekw"] == (1276 - 81, 207 + 85)


def test_odczyt_dwa_backpacki_z_zrzutu():
    ks = [kon("Backpack", 0), kon("Backpack", 1)]
    stare = _podmien([Okno(300), Okno(500)], ks)
    try:
        w, _ = O.odczyt(obraz(78), lambda: (ks, None))
    finally:
        _przywroc(stare)
    assert kody(w) == ["kilka_plecakow"] and w["plecaki"] == 2


def test_odczyt_ucieta_dolem_ramka_locker_nie_psuje_oceny():
    """dawajkesh w depo: dopasowanie okien nie przechodzi (niezgodne z ekranem), a bez plecaka w oknach ocena opiera się o pamięć."""
    ks = [kon("Locker", 0), kon("backpack", 1)]
    stare = _podmien([Okno(WYS - 70, 4), Okno(200)], None)
    try:
        w, _ = O.odczyt(obraz(78), lambda: (ks, None))
    finally:
        _przywroc(stare)
    assert w["zrodlo"] == "pamiec" and w["plecaki"] == 1 and w["depo"] == 1 and "brak_plecaka" not in kody(w)


def test_odczyt_pamiec_nie_widzi_kontenerow_to_pewne_zero():
    stare = _podmien([], None)
    try:
        w, _ = O.odczyt(obraz(78), lambda: (None, "pamięć nie widzi otwartych kontenerów"))
    finally:
        _przywroc(stare)
    assert kody(w) == ["brak_plecaka"] and w["problemy"][0]["naprawa"] == "otworz_plecak"


def test_odczyt_blad_pamieci_to_rezerwa_z_ekranu_bez_naprawy():
    stare = _podmien([Okno(300)], None)
    try:
        w, _ = O.odczyt(obraz(78), lambda: (None, "brak odczytu (TimeoutError: x)"))
    finally:
        _przywroc(stare)
    assert w["zrodlo"] == "ekran" and w["plecaki"] == 1 and w["problemy"] == []      # tytuł "backpack" z obrazu: plecak jest


def test_odczyt_poza_gra():
    w, _ = O.odczyt(obraz(None), lambda: (None, "nie powinno być wołane"))
    assert w["stan"] == "poza_gra"


# --- naprawa z atrapą myszy ------------------------------------------------------------------------------

class Mysz:
    def __init__(self):
        self.akcje = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def klik(self, x, y, przycisk=1, mod=None, drganie=3):
        self.akcje.append(("klik", x, y, przycisk, mod))


def sekwencja(*oceny):
    """odczyt_fn zwracający kolejne oceny (po każdym kliku jedna)."""
    kolejka = list(oceny)
    return lambda: (kolejka.pop(0), obraz(78))


def _ocena(minimapa="zwinieta", rzadzaj=(), plecaki=0, uklad=True):
    r = role(*(["backpack"] * plecaki))
    u = {"minimapa": minimapa, "plecak_ekw": (1195, 163 if minimapa != "rozwinieta" else 292), "prawo": 1276}
    w = O.ocen(u, r)
    w["uklad"] = {"prawo": 1276, "plecak_ekw": u["plecak_ekw"]}
    return w


def test_naprawa_zwija_minimape_potem_otwiera_plecak():
    start = _ocena("rozwinieta", plecaki=0)
    po_zwinieciu = _ocena("zwinieta", plecaki=0)
    po_otwarciu = _ocena("zwinieta", plecaki=1)
    m = Mysz()
    stare = loot.rozciagnij_plecak
    loot.rozciagnij_plecak = lambda mysz, im, log=print: True
    try:
        nowa, kroki = O.napraw(start, obraz(207), sekwencja(po_zwinieciu, po_otwarciu), lambda: m, pauza=lambda s: None, log=lambda *a: None)
    finally:
        loot.rozciagnij_plecak = stare
    assert m.akcje == [("klik", 1276 - 27, 42, 1, None), ("klik", 1195, 163, 1, "Control_L")], m.akcje
    assert nowa["problemy"] == [] and kroki[0] == "minimapa zwinięta" and "plecak otwarty" in kroki


def test_naprawa_nie_ponawia_gdy_plecak_sie_nie_otworzyl():
    start = _ocena("zwinieta", plecaki=0)
    m = Mysz()
    nowa, kroki = O.napraw(start, obraz(78), sekwencja(_ocena("zwinieta", plecaki=0)), lambda: m, pauza=lambda s: None, log=lambda *a: None)
    assert len(m.akcje) == 1 and kody(nowa) == ["brak_plecaka"] and "plecak z ekwipunku się nie otworzył" in kroki


def test_naprawa_nie_otwiera_plecaka_gdy_minimapa_dalej_rozwinieta():
    start = _ocena("rozwinieta", plecaki=0)
    m = Mysz()
    nowa, kroki = O.napraw(start, obraz(207), sekwencja(_ocena("rozwinieta", plecaki=0)), lambda: m, pauza=lambda s: None, log=lambda *a: None)
    assert len(m.akcje) == 1 and "minimapa NIE zwinęła się" in kroki


# --- uruchom: pokrętła, powiadomienia, odroczenie -----------------------------------------------------------

def _zrob(ocena):
    return lambda: (ocena, obraz(78))


def test_sprawdz_nie_klika_i_nie_powiadamia():
    wyslane, m = [], Mysz()
    kod, w = O.uruchom("sprawdz", "t1", naprawiaj=True, odczyt_fn=_zrob(_ocena("zwinieta", plecaki=0)), mysz_fn=lambda: m,
                       powiadom_fn=lambda *a, **k: wyslane.append(a), pauza=lambda s: None, log=lambda *a: None)
    assert kod == 1 and m.akcje == [] and wyslane == [] and "brak_plecaka" in w["opis"]


def test_naprawa_wylaczona_powiadamia_raz_i_nie_klika():
    wyslane, m = [], Mysz()
    pliki = lambda: dict(odczyt_fn=_zrob(_ocena("zwinieta", plecaki=0)), mysz_fn=lambda: m, pauza=lambda s: None, log=lambda *a: None,
                         powiadom_fn=lambda t, tr, p, klucz=None: wyslane.append((t, tr, p, klucz)) or True, naprawiaj=False)
    kod, w = O.uruchom("napraw", "t2", **pliki())
    assert kod == 1 and m.akcje == [] and len(wyslane) == 1 and wyslane[0][2] == "critical"
    assert "Ctrl+klik" in wyslane[0][1] and "wyłączona" in w["opis"]
    O.uruchom("napraw", "t2", **pliki())              # throttle: drugi raz w tym samym oknie czasu cisza
    assert len(wyslane) == 1


def test_dwa_okna_backpack_powiadomienie_z_konkretem_bez_klikania():
    wyslane, m = [], Mysz()
    kod, w = O.uruchom("napraw", "t3", naprawiaj=True, odczyt_fn=_zrob(_ocena("zwinieta", plecaki=2)), mysz_fn=lambda: m,
                       powiadom_fn=lambda t, tr, p, klucz=None: wyslane.append((t, tr, p, klucz)) or True, log=lambda *a: None)
    assert kod == 1 and m.akcje == [] and len(wyslane) == 1 and "zamknij nadmiarowe okno Backpack" in wyslane[0][1]


def test_odroczenie_w_walce_nie_klika():
    m = Mysz()
    kod, w = O.uruchom("napraw", "t4", naprawiaj=True, odczyt_fn=_zrob(_ocena("zwinieta", plecaki=0)), mysz_fn=lambda: m,
                       odroczenie_fn=lambda i: "bot w walce", powiadom_fn=lambda *a, **k: True, log=lambda *a: None)
    assert kod == 3 and m.akcje == [] and w["stan"] == "odroczone"


def test_pelna_naprawa_zwraca_zero_i_nie_powiadamia():
    wyslane, m = [], Mysz()
    stare = loot.rozciagnij_plecak
    loot.rozciagnij_plecak = lambda mysz, im, log=print: False
    kolejka = [_ocena("zwinieta", plecaki=0), _ocena("zwinieta", plecaki=1)]
    odczyty = [_ocena("rozwinieta", plecaki=0)] + kolejka
    try:
        kod, w = O.uruchom("napraw", "t5", naprawiaj=True, odczyt_fn=lambda: (odczyty.pop(0), obraz(78)), mysz_fn=lambda: m,
                           odroczenie_fn=lambda i: None, powiadom_fn=lambda *a, **k: wyslane.append(a) or True,
                           pauza=lambda s: None, log=lambda *a: None)
    finally:
        loot.rozciagnij_plecak = stare
    assert kod == 0 and wyslane == [] and len(m.akcje) == 2 and w["opis"].startswith("naprawione")


def test_ok_i_poza_gra_kod_zero():
    kod, _ = O.uruchom("napraw", "t6", odczyt_fn=_zrob(_ocena("zwinieta", plecaki=1)), log=lambda *a: None)
    assert kod == 0
    kod, w = O.uruchom("napraw", "t6", odczyt_fn=_zrob(O.ocen({"minimapa": None, "plecak_ekw": None, "prawo": 1276}, [])), log=lambda *a: None)
    assert kod == 0 and w["stan"] == "poza_gra"


def test_brak_odczytu_kod_cztery():
    kod, w = O.uruchom("napraw", "t7", odczyt_fn=lambda: (None, "zrzut nieudany"), log=lambda *a: None)
    assert kod == 4 and w["stan"] == "brak_odczytu"


def test_naprawa_wlaczona_env_i_pliki():
    d = Path(tempfile.mkdtemp(dir=TMP))
    w = d / "wspolne"
    s = d / "stan"
    w.mkdir()
    s.mkdir()
    assert O.naprawa_wlaczona(s, w, env={}) is False
    assert O.naprawa_wlaczona(s, w, env={"RETRONIC_OKNA_NAPRAWA": "1"}) is True
    (w / "OKNA_NAPRAWA").write_text("")
    assert O.naprawa_wlaczona(s, w, env={}) is True
    assert O.naprawa_wlaczona(s, w, env={"RETRONIC_OKNA_NAPRAWA": "0"}) is False
    (w / "OKNA_NAPRAWA").unlink()
    (s / "OKNA_NAPRAWA").write_text("")
    assert O.naprawa_wlaczona(s, w, env={}) is True


def test_przy_starcie_w_testach_nic_nie_robi():
    assert O.przy_starcie(lambda *a: None) is None


def test_throttle_powiadomien_po_czasie():
    plik = TMP / "throttle.json"
    wyslane = []
    p = [{"kod": "brak_plecaka", "opis": "x", "reczne": "y"}]
    f = lambda t, tr, pil, klucz=None: wyslane.append(klucz) or True
    t = [1000.0]
    assert O.powiadom_raz("a", p, f, lambda: t[0], plik) is True
    t[0] += 60
    assert O.powiadom_raz("a", p, f, lambda: t[0], plik) is False
    t[0] += O.POWIADOM_PONOW_S
    assert O.powiadom_raz("a", p, f, lambda: t[0], plik) is True
    assert len(wyslane) == 2


def test_stop_przechodzi_przez_kontrole_okien():
    class Zatrzymano(Exception):
        pass

    class Mz(Mysz):
        def klik(self, *a, **k):
            raise Zatrzymano()
    try:
        O.uruchom("napraw", "t8", naprawiaj=True, odczyt_fn=_zrob(_ocena("rozwinieta", plecaki=1)), mysz_fn=lambda: Mz(),
                  odroczenie_fn=lambda i: None, pauza=lambda s: None, log=lambda *a: None)
    except Zatrzymano:
        return
    raise AssertionError("STOP połknięty")


if __name__ == "__main__":
    nieudane = 0
    testy = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for nazwa, f in testy:
        try:
            f()
            print(f"PASS {nazwa}")
        except Exception as e:      # noqa: BLE001
            nieudane += 1
            import traceback
            print(f"FAIL {nazwa}: {type(e).__name__}: {e}")
            traceback.print_exc()
    print(f"{len(testy) - nieudane}/{len(testy)}")
    sys.exit(1 if nieudane else 0)
