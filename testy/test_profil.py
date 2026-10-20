"""Stały profil instancji: wymagany, poprawny, unikalny endpoint proxy i IP między instancjami."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import profil  # noqa: E402


def zapisz(kat, nazwa, user="u-1", host="p.example", port=80, ips=("1.2.3.4",), konto=""):
    d = Path(kat) / nazwa
    d.mkdir(parents=True, exist_ok=True)
    (d / "profil.json").write_text(json.dumps(
        {"proxy": {"host": host, "port": port, "user": user}, "ip_oczekiwane": list(ips), "konto": konto, "postac": ""}))
    return d


def klient(d, konto):
    c = d / "prefix/drive_c/users/x/AppData/Roaming/Retronic/Retronic"
    c.mkdir(parents=True, exist_ok=True)
    (c / "config.otml").write_text(f"uuid: ABC\naccount: {konto}\npassword: tajne\n")


class TestProfil(unittest.TestCase):
    def test_brak_profilu_blokuje_start(self):
        with tempfile.TemporaryDirectory() as k:
            d = Path(k) / "a"
            d.mkdir()
            with self.assertRaises(profil.BladProfilu):
                profil.sprawdz_unikalnosc(d)

    def test_poprawny_profil_daje_zmienne_proxy(self):
        with tempfile.TemporaryDirectory() as k:
            d = zapisz(k, "a", user="evitnvfx-5", host="p.webshare.io", ips=("84.247.60.125",))
            out = profil.powloka(profil.sprawdz_unikalnosc(d))
            self.assertIn("RETRONIC_PROXY_HOST=p.webshare.io", out)
            self.assertIn("RETRONIC_PROXY_PORT=80", out)
            self.assertIn("RETRONIC_PROXY_USER=evitnvfx-5", out)
            self.assertIn("SIEC_IP_OCZEKIWANE=84.247.60.125", out)

    def test_ten_sam_endpoint_w_dwoch_instancjach_blokuje(self):
        with tempfile.TemporaryDirectory() as k:
            zapisz(k, "a", user="x-5", ips=("1.1.1.1",))
            d = zapisz(k, "b", user="x-5", ips=("2.2.2.2",))
            with self.assertRaises(profil.BladProfilu):
                profil.sprawdz_unikalnosc(d)

    def test_wspolne_ip_blokuje(self):
        with tempfile.TemporaryDirectory() as k:
            zapisz(k, "a", user="x-1", ips=("1.1.1.1", "3.3.3.3"))
            d = zapisz(k, "b", user="x-2", ips=("3.3.3.3",))
            with self.assertRaises(profil.BladProfilu):
                profil.sprawdz_unikalnosc(d)

    def test_rozne_instancje_rozne_ip_przechodza(self):
        with tempfile.TemporaryDirectory() as k:
            zapisz(k, "a", user="x-1", ips=("1.1.1.1",))
            d = zapisz(k, "b", user="x-2", ips=("2.2.2.2",))
            self.assertEqual(profil.sprawdz_unikalnosc(d)["proxy"]["user"], "x-2")

    def test_zle_ip_odrzucone(self):
        with tempfile.TemporaryDirectory() as k:
            d = zapisz(k, "a", ips=("nie-ip",))
            with self.assertRaises(profil.BladProfilu):
                profil.sprawdz_unikalnosc(d)


class TestKonto(unittest.TestCase):
    def test_to_samo_konto_w_dwoch_profilach_blokuje(self):
        with tempfile.TemporaryDirectory() as k:
            zapisz(k, "a", user="x-1", ips=("1.1.1.1",), konto="Alfa")
            d = zapisz(k, "b", user="x-2", ips=("2.2.2.2",), konto="alfa")
            with self.assertRaises(profil.BladProfilu):
                profil.sprawdz_unikalnosc(d)

    def test_klient_z_innym_kontem_niz_profil_blokuje(self):
        with tempfile.TemporaryDirectory() as k:
            d = zapisz(k, "a", konto="alfa")
            klient(d, "beta")
            with self.assertRaises(profil.BladProfilu):
                profil.sprawdz_unikalnosc(d)

    def test_klient_z_kontem_innej_instancji_blokuje(self):
        with tempfile.TemporaryDirectory() as k:
            zapisz(k, "a", user="x-1", ips=("1.1.1.1",), konto="alfa")
            d = zapisz(k, "b", user="x-2", ips=("2.2.2.2",))
            klient(d, "alfa")
            with self.assertRaises(profil.BladProfilu):
                profil.sprawdz_unikalnosc(d)

    def test_zgodne_konto_przechodzi(self):
        with tempfile.TemporaryDirectory() as k:
            d = zapisz(k, "a", konto="alfa")
            klient(d, "alfa")
            self.assertEqual(profil.sprawdz_unikalnosc(d)["konto"], "alfa")

    def test_przypisz_bierze_login_z_klienta_bez_hasla(self):
        with tempfile.TemporaryDirectory() as k:
            d = zapisz(k, "a")
            klient(d, "gamma")
            profil.przypisz(d)
            tekst = (d / "profil.json").read_text()
            self.assertEqual(json.loads(tekst)["konto"], "gamma")
            self.assertNotIn("tajne", tekst)


if __name__ == "__main__":
    unittest.main()
