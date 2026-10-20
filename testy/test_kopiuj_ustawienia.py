"""kopiuj_ustawienia: ustawienia przechodzą, identyfikatory i konto celu zostają nietknięte."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import kopiuj_ustawienia as k  # noqa: E402

ZRODLO = """uuid: ZRODLO-UUID
autoReconnect: true
motd: 87
MiniWindows:
  battle:
    open: true
showFps: true
proxy: EUR - France
account: konto-mastafiana
password: haslo-mastafiana
"""
CEL = """uuid: NOWY-UUID
autoReconnect: false
showFps: false
MiniWindows:
  skills:
    open: false
account:
password:
"""


class TestScal(unittest.TestCase):
    def setUp(self):
        self.w = k.scal(ZRODLO, CEL)

    def test_identyfikatory_i_konto_celu_zostaja(self):
        self.assertIn("uuid: NOWY-UUID", self.w)
        self.assertNotIn("ZRODLO-UUID", self.w)
        self.assertIn("autoReconnect: false", self.w)
        self.assertNotIn("konto-mastafiana", self.w)
        self.assertNotIn("haslo-mastafiana", self.w)
        self.assertNotIn("motd", self.w)

    def test_ustawienia_ze_zrodla(self):
        self.assertIn("showFps: true", self.w)
        self.assertIn("proxy: EUR - France", self.w)
        self.assertIn("  battle:\n    open: true", self.w)
        self.assertNotIn("skills", self.w)  # cały blok MiniWindows zastąpiony

    def test_kazdy_klucz_raz(self):
        klucze = [kl for kl, _ in k.bloki(self.w) if kl]
        self.assertEqual(len(klucze), len(set(klucze)))


if __name__ == "__main__":
    unittest.main()
