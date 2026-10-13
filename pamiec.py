#!/usr/bin/env python3
"""Zapytania do strażnika (straznik.py), który uruchomił grę.

  pamiec.py status
  pamiec.py szukaj <wartość> [typ]         nowe skanowanie (typ: i32 u32 u16 u8 f32 f64)
  pamiec.py zakres <od> <do> [typ]         nowe skanowanie wartości z zakresu
  pamiec.py zawez <wartość>                zostaw adresy, które mają teraz tę wartość
  pamiec.py zawez zmienione|niezmienione|wieksze|mniejsze
  pamiec.py sledz [sekundy] [odstęp]       zostaw adresy, które w tym czasie były i zerem, i niezerem
  pamiec.py pokaz [ile]                    kandydaci z bieżącymi wartościami
  pamiec.py czytaj <typ> <adres> [adres...]
  pamiec.py hexdump <adres> [długość]
  pamiec.py stwory                         stwory i gracze na mapie (nazwa, % HP, pozycja)
  pamiec.py gracz                          HP, mana, cap, exp, level (sam znajduje strukturę)
  pamiec.py obserwuj [sekundy]             to samo co sekundę
"""

import json
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import instancja  # noqa: E402

GNIAZDO = str(instancja.gniazdo())
WARUNKI = {"zmienione", "niezmienione", "wieksze", "mniejsze"}


def zapytaj(zadanie):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        try:
            s.connect(GNIAZDO)
        except OSError:
            sys.exit("Strażnik nie działa. Uruchom grę przez retronic.sh.")
        s.sendall((json.dumps(zadanie) + "\n").encode())
        odpowiedz = json.loads(s.makefile("rb").readline())
    if not odpowiedz.pop("ok"):
        sys.exit("Błąd: " + odpowiedz["blad"])
    return odpowiedz


def opis_gracza(g):
    return (f"HP {g['hp']}/{g['max_hp']}  mana {g['mana']}/{g['max_mana']}  "
            f"cap {g['cap']}/{g['max_cap']}  lvl {g['level']} ({g['procent']}%)  exp {g['exp']}  [{g['adres']}]")


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd, args = argv[0], argv[1:]
    if cmd == "status":
        print(zapytaj({"cmd": "status"}))
    elif cmd == "szukaj":
        print(zapytaj({"cmd": "szukaj", "wartosc": args[0], "typ": args[1] if len(args) > 1 else "i32"}))
    elif cmd == "sledz":
        print(zapytaj({"cmd": "sledz", "sekundy": args[0] if args else 30, "odstep": args[1] if len(args) > 1 else 0.1}))
    elif cmd == "zakres":
        print(zapytaj({"cmd": "szukaj", "wartosc": args[0], "do": args[1], "typ": args[2] if len(args) > 2 else "i32"}))
    elif cmd == "zawez":
        if args[0] in WARUNKI:
            print(zapytaj({"cmd": "zawez", "warunek": args[0]}))
        else:
            print(zapytaj({"cmd": "zawez", "warunek": "rowne", "wartosc": args[0]}))
    elif cmd == "pokaz":
        for adres, wartosc in zapytaj({"cmd": "pokaz", "ile": args[0] if args else 20})["lista"]:
            print(adres, wartosc)
    elif cmd == "czytaj":
        wynik = zapytaj({"cmd": "czytaj", "typ": args[0], "adresy": args[1:]})["wartosci"]
        for adres, wartosc in zip(args[1:], wynik):
            print(adres, wartosc)
    elif cmd == "hexdump":
        dane = bytes.fromhex(zapytaj({"cmd": "hexdump", "adres": args[0],
                                      "dlugosc": args[1] if len(args) > 1 else 64})["hex"])
        start = int(args[0], 16)
        for i in range(0, len(dane), 16):
            print(f"{start + i:08x}  {dane[i:i + 16].hex(' ')}")
    elif cmd == "stwory":
        for s in zapytaj({"cmd": "stwory"})["stwory"]:
            print(f"{'GRACZ ' if s['gracz'] else ''}{s['nazwa']:<20} hp {s['hp']:>3}%  "
                  f"({s['x']}, {s['y']}, {s['z']})  id {s['id']:#x}")
    elif cmd == "gracz":
        print(opis_gracza(zapytaj({"cmd": "gracz"})["gracz"]))
    elif cmd == "obserwuj":
        koniec = time.time() + float(args[0] if args else 60)
        while time.time() < koniec:
            print(opis_gracza(zapytaj({"cmd": "gracz"})["gracz"]), flush=True)
            time.sleep(1)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
