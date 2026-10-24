#!/usr/bin/env python3
"""ml_zywo.py: magic level i procent z pamięci klienta (blok statystyk gracza, +0x48 ML, +0x50 ML%, +0x58 bazowy ML), parser z walidacją,
odczyt przez `hexdump` strażnika, zapis do ostatnie.json (ml, ml_proc, ml_t, ml_zrodlo="pamiec") z bota (ostatnie.Pisarz / telemetria)
i z odczytu jednorazowego (CLI). Wyłącznie atrapy w katalogu tymczasowym: bez gry, bez strażnika, bez prawdziwych instancji.
Uruchomienie: python3 -I testy/test_ml_zywo.py"""
import os
os.environ["RETRONIC_TESTY"] = "1"
import json
import math
import struct
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True
KORZEN = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(KORZEN))
import ostatnie  # noqa: E402
import ml_zywo  # noqa: E402

# Blok z prawdziwego odczytu odchyda 23.10 (tylko odczyt strażnika): hp 185/185, cap 117, exp 4581, lvl 8 (17%), mana 7/35, ML 1 (31%), baza 1
BLOK_ODCHYD = [185.0, 185.0, 117.0, 117.0, 4581.0, 8.0, 17.0, 7.0, 35.0, 1.0, 31.0, 1.0]
G_ODCHYD = {"hp": 185, "max_hp": 185, "cap": 117, "max_cap": 117, "exp": 4581, "level": 8, "procent": 17, "mana": 7, "max_mana": 35,
            "adres": "0xdc0adf8"}


def bajty(v):
    return struct.pack(f"<{len(v)}d", *v)


def blok(**zmiany):
    v = list(BLOK_ODCHYD)
    for k, x in zmiany.items():
        v[{"ml": 9, "ml_proc": 10, "baza": 11, "level": 5, "hp": 0, "max_hp": 1}[k]] = x
    return v


def tmpdir():
    return Path(tempfile.mkdtemp(prefix="ml-zywo-test-"))


def stan_dir(tmp, id_="x"):
    p = tmp / "instancje" / id_
    (p / "logi").mkdir(parents=True)
    return p


def wczytaj(p):
    return json.loads((Path(p) / "ostatnie.json").read_text(encoding="utf-8"))


class Strazniczka:
    """Atrapa gniazda strażnika: `gracz` i `hexdump` z jednego bloku; liczy wywołania."""

    def __init__(self, v=None, g=None, blad=None):
        self.v = list(BLOK_ODCHYD if v is None else v)
        self.g = dict(G_ODCHYD if g is None else g)
        self.wywolania = []
        self.blad = blad

    def __call__(self, z):
        self.wywolania.append(dict(z))
        if self.blad:
            raise self.blad
        if z["cmd"] == "gracz":
            return {"gracz": dict(self.g)}
        if z["cmd"] == "hexdump":
            assert int(z["adres"], 16) == int(self.g["adres"], 16), z
            return {"hex": bajty(self.v)[:int(z["dlugosc"])].hex()}
        raise AssertionError(f"nieoczekiwane polecenie {z}")


# ---------- parser ----------
def test_parsuj_prawdziwy_blok_odchyda():
    w = ml_zywo.parsuj(bajty(BLOK_ODCHYD))
    assert w == {"ml": 1, "ml_proc": 31.0, "ml_baza": 1}, w
    assert all(isinstance(w[k], (int, float)) and not isinstance(w[k], bool) for k in w)


def test_parsuj_dluzszy_bufor_i_ml_zero():
    w = ml_zywo.parsuj(bajty(blok(ml=0, ml_proc=0.0, baza=0) + [100.0, 0.0, 960.0]))
    assert w == {"ml": 0, "ml_proc": 0.0, "ml_baza": 0}, w            # zero to prawdziwy odczyt (Marinarra), nie „brak”


def test_parsuj_odrzuca_zle_dane():
    zle = {
        "za_krotki": bajty(BLOK_ODCHYD)[:0x58],
        "pusty": b"",
        "ml_ulamek": bajty(blok(ml=3.5)),
        "ml_ujemny": bajty(blok(ml=-1.0)),
        "ml_za_duzy": bajty(blok(ml=1000.0)),
        "proc_ponad_100": bajty(blok(ml_proc=101.0)),
        "proc_ujemny": bajty(blok(ml_proc=-1.0)),
        "baza_ulamek": bajty(blok(baza=0.5)),
        "nan": bajty(blok(ml=float("nan"))),
        "inf": bajty(blok(ml_proc=float("inf"))),
        "level_zero": bajty(blok(level=0.0)),
        "level_ulamek": bajty(blok(level=8.5)),
        "hp_ponad_max": bajty(blok(hp=200.0)),
        "to_nie_blok_gracza": bytes(range(256)) * 2,
    }
    for nazwa, b in zle.items():
        assert ml_zywo.parsuj(b) is None, (nazwa, ml_zywo.parsuj(b))


def test_parsuj_level_zgodny_z_gracz():
    assert ml_zywo.parsuj(bajty(BLOK_ODCHYD), G_ODCHYD) is not None
    assert ml_zywo.parsuj(bajty(blok(level=9.0)), G_ODCHYD) is None       # blok przeskoczył na inną sesję / inny level
    assert ml_zywo.parsuj(bajty(BLOK_ODCHYD), {"adres": "0x1"}) is not None   # g bez levelu: nie ma z czym porównać


# ---------- odczyt przez strażnika ----------
def test_odczytaj_uzywa_hexdump_pod_adresem_bloku():
    s = Strazniczka()
    w = ml_zywo.odczytaj(s, G_ODCHYD)
    assert w == {"ml": 1, "ml_proc": 31.0, "ml_baza": 1}, w
    assert s.wywolania == [{"cmd": "hexdump", "adres": "0xdc0adf8", "dlugosc": ml_zywo.DLUGOSC}], s.wywolania
    assert ml_zywo.DLUGOSC == 0x60 and ml_zywo.OFFSET_ML == 0x48 and ml_zywo.OFFSET_ML_PROC == 0x50 and ml_zywo.OFFSET_ML_BAZA == 0x58


def test_odczytaj_nie_rzuca():
    for g in (None, {}, {"adres": None}, {"adres": "nie-adres"}):
        assert ml_zywo.odczytaj(Strazniczka(), g) is None, g
    assert ml_zywo.odczytaj(Strazniczka(blad=OSError("brak gniazda")), G_ODCHYD) is None
    assert ml_zywo.odczytaj(Strazniczka(v=[0.0] * 12), G_ODCHYD) is None          # nie blok gracza


def test_odczytaj_z_gracza_pyta_o_gracza_potem_o_blok():
    s = Strazniczka()
    g, w = ml_zywo.odczytaj_z_gracza(s)
    assert g["level"] == 8 and w["ml"] == 1, (g, w)
    assert [z["cmd"] for z in s.wywolania] == ["gracz", "hexdump"], s.wywolania


# ---------- zapis ----------
def test_zapisz_nowy_plik_i_pola():
    s = stan_dir(tmpdir())
    w = ml_zywo.zapisz(s, {"ml": 1, "ml_proc": 31.0, "ml_baza": 1}, t=1000.0)
    assert w["ml"] == 1 and w["ml_proc"] == 31.0 and w["ml_t"] == 1000.0 and w["ml_zrodlo"] == "pamiec", w
    assert "ml_baza" not in w                                      # kontrakt F1 zamrożony: cztery pola ML
    assert wczytaj(s)["ml_zrodlo"] == "pamiec"


def test_zapisz_nie_rusza_reszty_ani_znacznika_zapisu():
    s = stan_dir(tmpdir())
    ostatnie.zapisz(s, "bot", {"postac": "Odchyd", "level": 8, "hp": 185, "ml": 0, "ml_proc": None, "ml_t": 5.0, "ml_zrodlo": "reczny"},
                    t=500.0)
    w = ml_zywo.zapisz(s, {"ml": 1, "ml_proc": 31.0, "ml_baza": 1}, t=900.0)
    assert (w["ml"], w["ml_proc"], w["ml_t"], w["ml_zrodlo"]) == (1, 31.0, 900.0, "pamiec"), w
    assert w["postac"] == "Odchyd" and w["level"] == 8 and w["hp"] == 185, w
    assert w["zapisano"] == 500.0 and w["zrodlo"] == "bot", w     # odczyt zewnętrzny nie udaje świeżych danych bota (wiek_s, „ostatnio”)


def test_zapisz_odrzuca_zle_wejscie_bez_zapisu():
    s = stan_dir(tmpdir())
    for zle in (None, {}, {"ml": "1", "ml_proc": 1.0}, {"ml": True, "ml_proc": 1.0}, {"ml": 1000, "ml_proc": 1.0}):
        assert ml_zywo.zapisz(s, zle, t=1.0) is None, zle
    assert not (s / "ostatnie.json").exists()


def test_odswiez_instancje_pisze_tylko_przy_dobrym_odczycie():
    tmp = tmpdir()
    s = stan_dir(tmp, "odchyd")
    ostatnie.zapisz(s, "bot", {"ml": 0, "ml_proc": None, "ml_t": 5.0, "ml_zrodlo": "reczny"}, t=500.0)
    w = ml_zywo.odswiez_instancje(s, Strazniczka(), t=900.0)
    assert w["ml"] == 1 and w["ml_proc"] == 31.0, w
    assert wczytaj(s)["ml_zrodlo"] == "pamiec"
    przed = (s / "ostatnie.json").read_bytes()
    assert ml_zywo.odswiez_instancje(s, Strazniczka(blad=OSError("x")), t=950.0) is None
    assert ml_zywo.odswiez_instancje(s, Strazniczka(v=[0.0] * 12), t=950.0) is None
    assert (s / "ostatnie.json").read_bytes() == przed             # zły odczyt nie nadpisuje dobrej wartości zerem


# ---------- bot: ostatnie.Pisarz ----------
POZ = (32296, 32126, 8)
SESJA = {"start": 1.0, "zab": 2, "gold": 3, "uh": 4}


def pisarz(s, **kw):
    return ostatnie.Pisarz(s, zegar=lambda: 0.0, miasto=lambda poz: (None, False), **kw)


def test_pisarz_zapisuje_ml_z_zapytaj():
    s = stan_dir(tmpdir())
    p = pisarz(s)
    assert p.tik(1000.0, dict(G_ODCHYD), POZ, "IDZ", "Odchyd", SESJA, zapytaj=Strazniczka()) is True
    w = wczytaj(s)
    assert (w["ml"], w["ml_proc"], w["ml_zrodlo"], w["ml_t"]) == (1, 31.0, "pamiec", 1000.0), w
    assert w["level"] == 8 and w["zrodlo"] == "bot", w


def test_pisarz_bez_zapytaj_nie_rusza_pol_ml():
    s = stan_dir(tmpdir())
    ostatnie.zapisz(s, "reczny", {"ml": 3, "ml_proc": None, "ml_t": 7.0, "ml_zrodlo": "reczny"}, t=7.0)
    p = pisarz(s)
    assert p.tik(1000.0, dict(G_ODCHYD), POZ, "IDZ", "Odchyd", SESJA) is True            # stare wywołanie, 6 argumentów
    w = wczytaj(s)
    assert (w["ml"], w["ml_zrodlo"], w["ml_t"]) == (3, "reczny", 7.0), w


def test_pisarz_blad_odczytu_zostawia_stara_wartosc_i_nie_przerywa_zapisu():
    s = stan_dir(tmpdir())
    ostatnie.zapisz(s, "reczny", {"ml": 3, "ml_proc": None, "ml_t": 7.0, "ml_zrodlo": "reczny"}, t=7.0)
    p = pisarz(s)
    assert p.tik(1000.0, dict(G_ODCHYD), POZ, "IDZ", "Odchyd", SESJA, zapytaj=Strazniczka(blad=OSError("x"))) is True
    w = wczytaj(s)
    assert (w["ml"], w["ml_zrodlo"]) == (3, "reczny") and w["level"] == 8, w


def test_pisarz_zmiana_ml_zapisuje_od_razu_a_odczyt_jest_rzadki():
    s = stan_dir(tmpdir())
    sk = Strazniczka()
    p = pisarz(s)
    assert p.tik(1000.0, dict(G_ODCHYD), POZ, "IDZ", "Odchyd", SESJA, zapytaj=sk) is True
    n0 = len(sk.wywolania)
    # kolejne próbki co sekundę: odczyt ML najwyżej co ML_CO_S, bez zapisu, gdy nic się nie zmieniło
    for i in range(1, 10):
        assert p.tik(1000.0 + i, dict(G_ODCHYD), POZ, "IDZ", "Odchyd", SESJA, zapytaj=sk) is False
    assert len(sk.wywolania) == n0, sk.wywolania
    # po ML_CO_S odczyt; procent urósł -> zapis natychmiast (przed 60 s okresowymi)
    sk.v = blok(ml_proc=40.0)
    t = 1000.0 + ostatnie.ML_CO_S + 1
    assert p.tik(t, dict(G_ODCHYD), POZ, "IDZ", "Odchyd", SESJA, zapytaj=sk) is True
    assert wczytaj(s)["ml_proc"] == 40.0 and wczytaj(s)["ml_t"] == round(t, 1)
    # ten sam odczyt po kolejnych ML_CO_S: bez zapisu (wartość bez zmiany)
    assert p.tik(t + ostatnie.ML_CO_S + 1, dict(G_ODCHYD), POZ, "IDZ", "Odchyd", SESJA, zapytaj=sk) is False


def test_pisarz_awans_ml_zapisuje_od_razu():
    s = stan_dir(tmpdir())
    sk = Strazniczka()
    p = pisarz(s)
    p.tik(1000.0, dict(G_ODCHYD), POZ, "IDZ", "Odchyd", SESJA, zapytaj=sk)
    sk.v = blok(ml=2.0, ml_proc=0.0, baza=2.0)
    assert p.tik(1000.0 + ostatnie.ML_CO_S + 1, dict(G_ODCHYD), POZ, "IDZ", "Odchyd", SESJA, zapytaj=sk) is True
    w = wczytaj(s)
    assert (w["ml"], w["ml_proc"]) == (2, 0.0), w


# ---------- telemetria przekazuje zapytaj bota ----------
def test_telemetria_przekazuje_zapytaj_do_pisarza():
    import telemetria  # noqa: PLC0415
    s = stan_dir(tmpdir())
    t = telemetria.Telemetria(s / "logi", zapis=True)
    assert t.ostatnie is not None
    t.nazwa_postaci = "Odchyd"
    t._ostatnie_tik(time.time(), dict(G_ODCHYD), POZ, "IDZ", Strazniczka())
    w = wczytaj(s)
    assert w["ml"] == 1 and w["ml_zrodlo"] == "pamiec", w
    t._ostatnie_tik(time.time(), dict(G_ODCHYD), POZ, "IDZ")                                  # bez zapytaj: stare wołanie nadal działa


# ---------- CLI: prawdziwe gniazdo Unix (atrapa strażnika w wątku) ----------
def test_przebieg_przez_gniazdo_unix():
    import socket  # noqa: PLC0415
    import threading  # noqa: PLC0415
    tmp = tmpdir()
    rt = Path(tempfile.mkdtemp(prefix="ml-rt-", dir="/tmp"))     # ścieżka gniazda Unix <= 107 znaków
    s = stan_dir(tmp, "odchyd")
    stan_dir(tmp, "bezgry")
    sk = Strazniczka()
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(str(rt / "retronic-odchyd.sock"))
    srv.listen(4)
    srv.settimeout(5)

    def obsluz():
        try:
            for _ in range(2):
                c, _a = srv.accept()
                with c:
                    z = json.loads(c.makefile("rb").readline())
                    c.sendall((json.dumps({"ok": True, **sk(z)}) + "\n").encode())
        except OSError:
            pass
    th = threading.Thread(target=obsluz, daemon=True)
    th.start()
    wypisane = []
    try:
        wyn = ml_zywo.przebieg(["odchyd", "bezgry"], korzen=tmp, runtime=str(rt), wypisz=wypisane.append)
    finally:
        th.join(5)
        srv.close()
        for f in rt.iterdir():
            f.unlink()
        rt.rmdir()
    assert wyn == {"odchyd": {"ml": 1, "ml_proc": 31.0, "ml_baza": 1}}, wyn
    assert wczytaj(s)["ml_zrodlo"] == "pamiec" and not (tmp / "instancje" / "bezgry" / "ostatnie.json").exists()
    assert any("brak strażnika" in w for w in wypisane) and any("ML 1 (31.0%)" in w for w in wypisane), wypisane


TESTY = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]

if __name__ == "__main__":
    padlo = 0
    for nazwa, f in TESTY:
        try:
            f()
            print("ok  ", nazwa)
        except Exception as e:      # noqa: BLE001
            padlo += 1
            print("FAIL", nazwa, repr(e))
    print(f"{len(TESTY) - padlo}/{len(TESTY)} OK")
    sys.exit(1 if padlo else 0)
