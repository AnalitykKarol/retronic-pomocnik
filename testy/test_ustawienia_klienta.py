"""ustawienia_klienta: wymuszenie showPrivateMessagesInConsole: false w config.otml przed startem gry."""
import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
import sys, tempfile, pathlib
sys.dont_write_bytecode = True
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import ustawienia_klienta as uk

ok = []
def sprawdz(nazwa, warunek, info=""):
    ok.append(bool(warunek)); print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))

WZOR = ("game:\n  showPrivateMessagesInConsole: true\nshowPrivateMessagesOnScreen: true\n"
        "showPrivateMessagesInConsole: true\nnotifyOnPrivateMessage: false\n")
t, z = uk.ustaw(WZOR)
sprawdz("1a klucz najwyzszego poziomu zmieniony", "\nshowPrivateMessagesInConsole: false\n" in t and z == ["showPrivateMessagesInConsole"], t)
sprawdz("1b wciety klucz (inna sekcja) nietkniety", "  showPrivateMessagesInConsole: true\n" in t, t)
sprawdz("1c reszta bez zmian", t.replace("InConsole: false\nnotify", "InConsole: true\nnotify") == WZOR, t)
t2, z2 = uk.ustaw(t)
sprawdz("1d drugi raz: nic do zmiany", t2 == t and z2 == [])
t3, z3 = uk.ustaw("wsadWalking: true")
sprawdz("1e brak klucza: dopisany w nowej linii", t3 == "wsadWalking: true\nshowPrivateMessagesInConsole: false\n" and z3, t3)
sprawdz("1f showPrivateMessagesOnScreen nie mylony z InConsole", "showPrivateMessagesOnScreen: true" in t)

pref = pathlib.Path(tempfile.mkdtemp())
sprawdz("2a pusty prefiks: kod 0, bez plikow", uk.main(["x", str(pref)]) == 0 and not list(pref.rglob("*.otml")))
plik = pref / "drive_c/users/charlie/AppData/Roaming/Retronic/Retronic/config.otml"
plik.parent.mkdir(parents=True)
plik.write_text(WZOR, encoding="utf-8")
sprawdz("2b prawdziwy uklad katalogow: zmiana zapisana", uk.main(["x", str(pref)]) == 0
        and "\nshowPrivateMessagesInConsole: false\n" in plik.read_text(), plik.read_text())
sprawdz("2c bez plikow tymczasowych", not list(plik.parent.glob("*.tmp")))
sprawdz("2d zly argument: kod 2", uk.main(["x"]) == 2)

print("\nWYNIK:", sum(ok), "/", len(ok))
sys.exit(0 if all(ok) else 1)
