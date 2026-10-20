#!/usr/bin/env python3
"""zmien_uzytkownika: przenosi prefiks wine instancji na nazwę użytkownika z tozsamosc.json (SPEC_tozsamosc_sprzetu_1020.md, D5).

Prefiks zrobiony pod kontem `charlie` ma C:\\users\\charlie i te ścieżki w rejestrze. Skrypt:
  - zmienia nazwę katalogu drive_c/users/<stara> na drive_c/users/<nowa>,
  - w user.reg, system.reg, userdef.reg podmienia C:\\users\\<stara> na C:\\users\\<nowa> (bez względu na wielkość liter),
  - skróty Desktop/Documents/Downloads/Music/Pictures/Videos/Templates prowadzące poza prefiks (do katalogu domowego)
    zamienia na zwykłe puste katalogi (gra nie widzi plików z /home).
Kopie rejestru: *.reg.przed-uzytkownikiem. Uruchamiaj przy ZAMKNIĘTEJ grze instancji (wineserver zapisuje rejestr przy wyjściu).
  python3 -I zmien_uzytkownika.py <prefiks> <nowa nazwa> [stara nazwa, domyślnie charlie]
"""
import re
import shutil
import sys
from pathlib import Path

SKROTY = ("Desktop", "Documents", "Downloads", "Music", "Pictures", "Videos", "Templates")
REJESTR = ("user.reg", "system.reg", "userdef.reg")


def podmien_rejestr(tekst, stara, nowa):
    # w plikach .reg ukośnik wsteczny jest podwojony: C:\\users\\charlie
    wzor = re.compile(r"(\\\\users\\\\)" + re.escape(stara) + r"(?=\\\\|\")", re.IGNORECASE)
    return wzor.sub(lambda m: m.group(1) + nowa, tekst)


def odepnij_skroty(katalog_uzytkownika):
    zmienione = []
    for nazwa in SKROTY:
        p = katalog_uzytkownika / nazwa
        if p.is_symlink():
            p.unlink()
            p.mkdir()
            zmienione.append(nazwa)
    return zmienione


def przenies(prefiks, nowa, stara="charlie"):
    prefiks = Path(prefiks)
    users = prefiks / "drive_c" / "users"
    zrodlo, cel = users / stara, users / nowa
    if cel.exists() and not zrodlo.exists():
        opis = [f"katalog {nowa} już jest"]
    elif cel.exists():
        raise SystemExit(f"są oba katalogi: {zrodlo} i {cel}; rozstrzygnij ręcznie")
    elif not zrodlo.exists():
        raise SystemExit(f"brak {zrodlo}")
    else:
        zrodlo.rename(cel)
        opis = [f"users/{stara} -> users/{nowa}"]
    for nazwa in REJESTR:
        f = prefiks / nazwa
        if not f.exists():
            continue
        stary_tekst = f.read_text(encoding="utf-8", errors="surrogateescape")
        nowy_tekst = podmien_rejestr(stary_tekst, stara, nowa)
        if nowy_tekst != stary_tekst:
            kopia = f.with_name(nazwa + ".przed-uzytkownikiem")
            if not kopia.exists():
                shutil.copy2(f, kopia)
            f.write_text(nowy_tekst, encoding="utf-8", errors="surrogateescape")
            opis.append(f"{nazwa}: ścieżki profilu podmienione")
    skroty = odepnij_skroty(cel)
    if skroty:
        opis.append("skróty do /home -> puste katalogi: " + ", ".join(skroty))
    return opis


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
        sys.exit(2)
    for linia in przenies(*sys.argv[1:]):
        print(linia)
