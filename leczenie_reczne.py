#!/usr/bin/env python3
"""Samo leczenie exurą (F2) na czas ręcznej gry / nagrywania trasy. Nie rusza postaci.

  python3 -I leczenie_reczne.py [--hp 60] [--mana 25] [--minuty 240]

Co 0,25 s czyta HP/manę z pamięci; gdy HP% < próg i mana >= koszt, wciska F2 (z losowym
opóźnieniem 0,2-0,8 s, min. 2,2 s między rzutami). Po 3 rzutach bez poprawy (ani HP w górę,
ani mana w dół) pauza 60 s. Koniec: plik STOP_LECZENIE albo upływ czasu (plik STOP bota NIE wyłącza).
"""
import argparse
import random
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bot  # noqa: E402
import instancja  # noqa: E402
import klawisz_x11  # noqa: E402

KAT = Path(__file__).resolve().parent
STOP_LECZENIE = instancja.S.stop_leczenie


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hp", type=float, default=60.0)
    p.add_argument("--mana", type=int, default=25)
    p.add_argument("--minuty", type=float, default=240.0)
    p.add_argument("--ml", action="store_true", help="dodatkowo F1 (utevo lux) na ML, gdy mana >= 20 i HP >= --ml-hp")
    p.add_argument("--ml-hp", type=float, default=70.0)
    p.add_argument("--ml-mana", type=int, default=20)
    a = p.parse_args()
    koniec = time.time() + a.minuty * 60
    ostatni = 0.0
    porazki = 0
    ml_rzuty = 0
    pauza_do = 0.0
    ekran = None
    print(f"leczenie_reczne: F2 HP<{a.hp}% mana>={a.mana}; ML(F1)={a.ml}; {a.minuty:.0f} min; stop: touch STOP_LECZENIE", flush=True)
    while time.time() < koniec:
        if STOP_LECZENIE.exists():
            print("leczenie_reczne: stop", flush=True)
            break
        try:
            g = bot.zapytaj({"cmd": "gracz"})["gracz"]
            hp, mhp, mana = g["hp"], g["max_hp"], g["mana"]
            teraz = time.time()
            if mhp and 100.0 * hp / mhp < a.hp and mana >= a.mana and teraz >= pauza_do and teraz - ostatni >= 2.2:
                time.sleep(random.uniform(0.2, 0.8))
                ekran = ekran or bot.ekran_gry()
                klawisz_x11.wyslij("F2", ekran=ekran)
                ostatni = time.time()
                time.sleep(1.2)
                g2 = bot.zapytaj({"cmd": "gracz"})["gracz"]
                if g2["hp"] > hp or g2["mana"] < mana:
                    porazki = 0
                    print(f"{time.strftime('%H:%M:%S')} exura: hp {hp}->{g2['hp']} mana {mana}->{g2['mana']}", flush=True)
                else:
                    porazki += 1
                    print(f"{time.strftime('%H:%M:%S')} exura bez efektu ({porazki}/3)", flush=True)
                    if porazki >= 3:
                        pauza_do = time.time() + 60
                        porazki = 0
            elif (a.ml and mhp and 100.0 * hp / mhp >= a.ml_hp and mana >= a.ml_mana
                  and teraz >= pauza_do and teraz - ostatni >= 2.4):
                time.sleep(random.uniform(0.3, 1.5))
                ekran = ekran or bot.ekran_gry()
                klawisz_x11.wyslij("F1", ekran=ekran)
                ostatni = time.time()
                time.sleep(1.2)
                g2 = bot.zapytaj({"cmd": "gracz"})["gracz"]
                if g2["mana"] < mana:
                    porazki = 0
                    ml_rzuty += 1
                    if ml_rzuty % 10 == 0:
                        print(f"{time.strftime('%H:%M:%S')} ML: {ml_rzuty} rzutów utevo lux", flush=True)
                else:
                    porazki += 1
                    print(f"{time.strftime('%H:%M:%S')} utevo lux bez spadku many ({porazki}/3)", flush=True)
                    if porazki >= 3:
                        pauza_do = time.time() + 60
                        porazki = 0
        except Exception as e:  # noqa: BLE001
            print("błąd:", e, flush=True)
            time.sleep(2)
        time.sleep(0.25)


if __name__ == "__main__":
    main()
