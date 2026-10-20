"""zmien_uzytkownika: katalog i ścieżki rejestru przechodzą na nową nazwę, inne wpisy i skróty wewnątrz prefiksu zostają."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import zmien_uzytkownika as z  # noqa: E402

REG = (
    '"AppData"="C:\\\\users\\\\charlie\\\\AppData\\\\Roaming"\n'
    '"ProfileImagePath"="C:\\\\users\\\\Charlie"\n'
    '"InstallSource"="Z:\\\\home\\\\charlie\\\\.cache\\\\wine\\\\"\n'
    '"Inny"="C:\\\\users\\\\charliex\\\\cos"\n'
)


class TestZmienUzytkownika(unittest.TestCase):
    def test_podmiana_tylko_sciezek_profilu(self):
        w = z.podmien_rejestr(REG, "charlie", "Kamil")
        self.assertIn('"AppData"="C:\\\\users\\\\Kamil\\\\AppData\\\\Roaming"', w)
        self.assertIn('"ProfileImagePath"="C:\\\\users\\\\Kamil"', w)
        self.assertIn("Z:\\\\home\\\\charlie", w)  # ścieżka uniksowa zostaje
        self.assertIn("charliex", w)  # inna nazwa zaczynająca się tak samo zostaje

    def test_przenies_prefiks(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            u = p / "drive_c/users/charlie"
            (u / "AppData/Roaming/Retronic").mkdir(parents=True)
            (u / "AppData/Roaming/Retronic/config.otml").write_text("uuid: X\n")
            (u / "Documents").symlink_to(d)
            (p / "user.reg").write_text(REG)
            z.przenies(p, "Kamil")
            nowy = p / "drive_c/users/Kamil"
            self.assertTrue((nowy / "AppData/Roaming/Retronic/config.otml").exists())
            self.assertFalse((p / "drive_c/users/charlie").exists())
            self.assertTrue((nowy / "Documents").is_dir() and not (nowy / "Documents").is_symlink())
            self.assertIn("users\\\\Kamil", (p / "user.reg").read_text())
            self.assertTrue((p / "user.reg.przed-uzytkownikiem").exists())
            # drugie uruchomienie nic nie psuje
            z.przenies(p, "Kamil")
            self.assertTrue((nowy / "AppData/Roaming/Retronic/config.otml").exists())


if __name__ == "__main__":
    unittest.main()
