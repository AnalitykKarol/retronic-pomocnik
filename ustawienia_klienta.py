#!/usr/bin/env python3
"""ustawienia_klienta: wymusza wybrane opcje OTClienta w config.otml prefiksu PRZED startem gry.

Klient nadpisuje config.otml przy wyjściu, więc zmiana w trakcie gry nie działa; dlatego wołają to skrypty
startu (klient/retronic.sh, uruchom_gre.sh) dla swojego WINEPREFIX. Zmienia tylko klucze z USTAWIENIA
(linie najwyższego poziomu "klucz: wartość"); resztę pliku zostawia bajt w bajt. Brak pliku (świeży prefiks,
klient jeszcze nie startował) = nic nie robi; ustawi przy kolejnym starcie.

  python3 -I ustawienia_klienta.py <WINEPREFIX>       # kod 0 zawsze, poza złym argumentem
"""
import re
import sys
from pathlib import Path

# 19.10 (Karol): prywatne wiadomości nie lądują na Default, tylko każdy rozmówca dostaje własną zakładkę
# (Options -> Console -> "Show private messages in console"); na Default ginęły w gwarze NPC i graczy.
USTAWIENIA = {
    "showPrivateMessagesInConsole": "false",
}


def pliki_konfiguracji(prefiks):
    return sorted(Path(prefiks).glob("drive_c/users/*/AppData/Roaming/Retronic/Retronic/config.otml"))


def ustaw(tekst, ustawienia=USTAWIENIA):
    """(nowy tekst, lista zmienionych kluczy). Brakujący klucz dopisywany na końcu."""
    zmienione = []
    for klucz, wartosc in ustawienia.items():
        rx = re.compile(rf"^{re.escape(klucz)}:[^\n]*$", re.M)
        nowa = f"{klucz}: {wartosc}"
        m = rx.search(tekst)
        if m:
            if m.group(0) != nowa:
                tekst = tekst[:m.start()] + nowa + tekst[m.end():]
                zmienione.append(klucz)
        else:
            tekst = tekst + ("" if tekst.endswith("\n") or not tekst else "\n") + nowa + "\n"
            zmienione.append(klucz)
    return tekst, zmienione


def main(argv):
    if len(argv) != 2:
        print("użycie: ustawienia_klienta.py <WINEPREFIX>", file=sys.stderr)
        return 2
    pliki = pliki_konfiguracji(argv[1])
    if not pliki:
        print(f"ustawienia_klienta: brak config.otml w {argv[1]} (pierwszy start klienta), pomijam")
        return 0
    for plik in pliki:
        try:
            stary = plik.read_text(encoding="utf-8")
            nowy, zmienione = ustaw(stary)
            if zmienione:
                tmp = plik.with_suffix(".otml.tmp")
                tmp.write_text(nowy, encoding="utf-8")
                tmp.replace(plik)
                print(f"ustawienia_klienta: {plik}: {', '.join(zmienione)}")
        except OSError as e:
            print(f"ustawienia_klienta: {plik}: {e} (gra startuje bez zmiany)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
