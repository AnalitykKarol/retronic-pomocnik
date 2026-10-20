#!/usr/bin/env python3
"""kopiuj_ustawienia: ustawienia klienta z jednego prefiksu do drugiego BEZ identyfikatorów i konta
(SPEC dane_tibia/SPEC_tozsamosc_sprzetu_1020.md, rozszerzenie (b)).

config.otml: bloki najwyższego poziomu ("klucz:" od kolumny 0 + wcięte linie pod nim) ze źródła zastępują te w celu,
poza POMIJANE (uuid klienta, konto, hasło, auto-logowanie, motd), które zostają takie, jakie cel ma (uuid wygenerowany
przez klienta przy pierwszym starcie). Do tego pliki: hotkeys_*.otml, mapa map74.otmm. Nie kopiuje plików postaci
("... of <postać>"), recentAccounts.otml, zrzutów, exe/dll/data.zip.
Cel musi mieć już config.otml (klient raz uruchomiony i zamknięty), inaczej nie ma własnego uuid.
Klient nadpisuje config.otml przy wyjściu: uruchamiaj przy ZAMKNIĘTEJ grze celu.

  python3 -I kopiuj_ustawienia.py <prefiks źródłowy> <prefiks docelowy>
"""
import re
import shutil
import sys
from pathlib import Path

POMIJANE = {"uuid", "account", "password", "autoReconnect", "motd"}
PLIKI = ("hotkeys_*.otml", "map74.otmm")
_KLUCZ = re.compile(r"^([A-Za-z0-9_]+):")


def bloki(tekst):
    """Lista (klucz albo None, tekst bloku); None = linie przed pierwszym kluczem."""
    wynik, klucz, linie = [], None, []
    for linia in tekst.splitlines(keepends=True):
        m = _KLUCZ.match(linia)
        if m:
            if linie or klucz is not None:
                wynik.append((klucz, "".join(linie)))
            klucz, linie = m.group(1), [linia]
        else:
            linie.append(linia)
    if linie or klucz is not None:
        wynik.append((klucz, "".join(linie)))
    return wynik


def scal(zrodlo, cel):
    zr = {k: t for k, t in bloki(zrodlo) if k is not None and k not in POMIJANE}
    wynik, uzyte = [], set()
    for k, t in bloki(cel):
        if k in zr:
            t = zr[k]
            uzyte.add(k)
        wynik.append(t)
    for k, t in zr.items():
        if k not in uzyte:
            wynik.append(t if t.endswith("\n") else t + "\n")
    return "".join(x if x.endswith("\n") or i == len(wynik) - 1 else x + "\n" for i, x in enumerate(wynik))


def katalog_klienta(prefiks):
    k = sorted(Path(prefiks).glob("drive_c/users/*/AppData/Roaming/Retronic/Retronic"))
    if not k:
        raise SystemExit(f"brak katalogu klienta w {prefiks} (uruchom klienta raz)")
    return k[0]


def main(zr_prefiks, cel_prefiks):
    zr, cel = katalog_klienta(zr_prefiks), katalog_klienta(cel_prefiks)
    zr_cfg, cel_cfg = zr / "config.otml", cel / "config.otml"
    if not cel_cfg.exists():
        raise SystemExit(f"brak {cel_cfg}: uruchom i zamknij klienta celu raz (własny uuid)")
    kopia = cel_cfg.with_name("config.otml.przed-kopiowaniem")
    if not kopia.exists():
        shutil.copy2(cel_cfg, kopia)
    cel_cfg.write_text(scal(zr_cfg.read_text(), cel_cfg.read_text()))
    skopiowane = ["config.otml (bez: " + ", ".join(sorted(POMIJANE)) + ")"]
    for wzor in PLIKI:
        for f in sorted(zr.glob(wzor)):
            shutil.copy2(f, cel / f.name)
            skopiowane.append(f.name)
    print("skopiowane:", "; ".join(skopiowane))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
