#!/usr/bin/env python3
"""P7: narzedzia/zbierz_czaszki.py (inwentarz próbek) i zapis próbek w czaszka.py (CZASZKA_ZAPIS_PROBEK, domyślnie 0).
Zero modelu, zero gry. Ucieka runom: nic nie klika."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("RETRONIC_TESTY", "1")
sys.dont_write_bytecode = True
RDZEN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RDZEN))
sys.path.insert(0, str(RDZEN / "narzedzia"))

from PIL import Image  # noqa: E402

import czaszka  # noqa: E402
import zbierz_czaszki as zb  # noqa: E402

wyniki = []


def sprawdz(nazwa, warunek, info=""):
    wyniki.append(bool(warunek))
    print(("OK   " if warunek else "FAIL ") + nazwa + (f"  {info}" if not warunek and info else ""))


tmp = Path(tempfile.mkdtemp())
logi = tmp / "logi"
logi.mkdir()
(logi / "mozg-1.log").write_text(
    "09:34:34 Czaszka: Star Prince = brak (model: 'none', $0.0028).\n"
    "15:52:12 Czaszka: Tojson = biala (model: 'white', $0.0005).\n"
    "15:53:00 Czaszka: Tojson = biala (model: 'white').\n"
    "16:00:00 Czaszka: X = nieczytelne (model: 'unreadable').\n"
    "16:00:01 Czaszka: limit 20 odczytów / h, nie czytam Y (zostaje 'nieznana').\n"
    "debug: Czaszka bez formatu\n", encoding="utf-8")
r = zb.raport(str(logi))
sprawdz("odczyty per klasa z logu", r["odczyty_log"] == {"biala": 2, "czerwona": 0, "zolta": 0, "brak": 1, "nieczytelne": 1},
        r["odczyty_log"])
sprawdz("nick ze spacją i unikalność", r["unikalne_nicki_log"]["biala"] == 1 and r["unikalne_nicki_log"]["brak"] == 1)
sprawdz("brak obrazów = za mało, brakuje po 30", not r["wystarczy"] and r["brakuje_obrazow"] == {"biala": 30, "czerwona": 30, "brak": 30})
for k, n in (("biala", 3), ("czerwona", 3), ("brak", 3)):
    (logi / "czaszki" / k).mkdir(parents=True)
    for i in range(n):
        Image.new("RGB", (4, 4)).save(logi / "czaszki" / k / f"a{i}.png")
sprawdz("min=3 wystarcza", zb.raport(str(logi), 3)["wystarczy"])
sprawdz("min=4 nie wystarcza", not zb.raport(str(logi), 4)["wystarczy"])
sprawdz("brak katalogu logów = zera, bez wyjątku", zb.raport(str(tmp / "nie_ma"))["odczyty_log"]["biala"] == 0)
sprawdz("main drukuje i zwraca 0", zb.main(["--logi", str(logi), "--min", "3"]) == 0)

# zapis próbek w czytniku: domyślnie 0
sprawdz("domyślnie zapis próbek wyłączony", czaszka.CZASZKA_ZAPIS_PROBEK == 0)


def czytnik(**kw):
    c = czaszka.CzytnikCzaszki(lambda p, system=None, obraz=None: ("white", {}), zrzut=lambda: Image.new("RGB", (50, 50)),
                               katalog=tmp / "k", wytnij=lambda o, dx, dy: Image.new("RGB", (30, 20)), **kw)
    c.katalog_probek = str(tmp / "probki")
    return c


czaszka.wyczysc()
c = czytnik()
c.odczytaj("Tojson", 1, 1)
sprawdz("domyślnie nic nie zapisuje", not (tmp / "probki").exists())
czaszka.wyczysc()
os.environ["CZASZKA_ZAPIS_PROBEK"] = "1"
c = czytnik()
c.odczytaj("To/json", 1, 1)
zapisane = list((tmp / "probki" / "biala").glob("*.png"))
sprawdz("pokrętło 1 zapisuje wycinek do <wynik>/", len(zapisane) == 1 and "/" not in zapisane[0].name[:-4], zapisane)
os.environ.pop("CZASZKA_ZAPIS_PROBEK")
czaszka.wyczysc()

print(f"\n{sum(wyniki)}/{len(wyniki)} OK")
sys.exit(0 if all(wyniki) else 1)
