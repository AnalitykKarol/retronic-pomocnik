"""Tożsamość sprzętu instancji: format, stałość między startami, odrzucanie zepsutego pliku."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tozsamosc  # noqa: E402


class TestTozsamosc(unittest.TestCase):
    def test_nowa_ma_poprawny_format_i_prefiks_producenta(self):
        for _ in range(50):
            t = tozsamosc.nowa()
            self.assertTrue(tozsamosc.poprawna(t), t)
            self.assertIn(t["mac"][:8], tozsamosc.PREFIKSY_MAC)
            self.assertEqual(t["machine_id"][12], "4")
            self.assertIn(t["machine_id"][16], "89ab")

    def test_stala_miedzy_startami(self):
        with tempfile.TemporaryDirectory() as d:
            a = tozsamosc.wczytaj_lub_utworz(d)
            b = tozsamosc.wczytaj_lub_utworz(d)
            self.assertEqual(a, b)
            self.assertEqual(json.loads((Path(d) / "tozsamosc.json").read_text()), a)

    def test_rozne_instancje_rozne_wartosci(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            a = tozsamosc.wczytaj_lub_utworz(d1)
            b = tozsamosc.wczytaj_lub_utworz(d2)
            for k in ("volume_serial", "mac", "machine_id"):
                self.assertNotEqual(a[k], b[k])

    def test_zepsuty_plik_nie_jest_nadpisywany(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tozsamosc.json"
            p.write_text('{"volume_serial": "xyz", "mac": "00:e0:4c:00:00:01", "machine_id": "0"}')
            with self.assertRaises(ValueError):
                tozsamosc.wczytaj_lub_utworz(d)
            self.assertIn("xyz", p.read_text())

    def test_powloka_eksportuje_zmienne(self):
        t = {"volume_serial": "6d2e91a7", "mac": "00:e0:4c:12:34:56", "machine_id": "a" * 32,
             "uzytkownik": "Kamil", "komputer": "DESKTOP-K7Q2M4R"}
        out = tozsamosc.powloka(t)
        self.assertIn("export TOZ_VOLUME=6d2e91a7", out)
        self.assertIn("export TOZ_MAC=00:e0:4c:12:34:56", out)
        self.assertIn("export TOZ_MACHINE_ID=" + "a" * 32, out)
        self.assertIn("export TOZ_USER=Kamil", out)
        self.assertIn("export TOZ_HOST=DESKTOP-K7Q2M4R", out)

    def test_stary_plik_uzupelniony_bez_zmiany_reszty(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tozsamosc.json"
            stare = {"volume_serial": "6d2e91a7", "mac": "00:e0:4c:12:34:56", "machine_id": "b" * 32}
            p.write_text(json.dumps(stare))
            t = tozsamosc.wczytaj_lub_utworz(d)
            for k, v in stare.items():
                self.assertEqual(t[k], v)
            self.assertTrue(tozsamosc.poprawna(t))
            self.assertEqual(json.loads(p.read_text()), t)
            self.assertNotEqual(t["uzytkownik"].lower(), "charlie")

    def test_instancje_obok_siebie_maja_rozne_nazwy_uzytkownika(self):
        with tempfile.TemporaryDirectory() as k:
            nazwy = []
            for i in range(len(tozsamosc.UZYTKOWNICY)):
                nazwy.append(tozsamosc.wczytaj_lub_utworz(Path(k) / f"i{i}")["uzytkownik"].lower())
            self.assertEqual(len(nazwy), len(set(nazwy)))

    def test_zla_nazwa_komputera_odrzucona(self):
        t = tozsamosc.nowa()
        t["komputer"] = "charlie"
        self.assertFalse(tozsamosc.poprawna(t))


if __name__ == "__main__":
    unittest.main()
