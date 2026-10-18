"""Podsumowanie peta z logów: czas życia, HP, odległość, zabicia obok peta, exp i mana w czasie życia.

  python3 -I pet_staty.py [--pet ID] [--plik logi/pet-....jsonl]

Czyta wszystkie logi/pet-*.jsonl (bez pet-nadzor.jsonl). Bez --pet bierze pierwszy pet z zapisanym przywołaniem.
Zabicia z kilku plików (po restarcie bota) są liczone raz: ten sam potwór na tej samej pozycji = jedno zabicie.
Tylko odczyt logów, nic nie wysyła do gry.
"""
import argparse
import glob
import json
import os
import statistics
from collections import Counter

KATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logi")


def wczytaj(katalog):
    """Wszystkie zdarzenia z plików peta, z nazwą pliku."""
    wynik = []
    for plik in sorted(glob.glob(os.path.join(katalog, "pet-*.jsonl"))):
        if os.path.basename(plik) == "pet-nadzor.jsonl":
            continue
        with open(plik, encoding="utf-8") as f:
            for linia in f:
                try:
                    w = json.loads(linia)
                except ValueError:
                    continue
                w["_plik"] = os.path.basename(plik)
                wynik.append(w)
    return sorted(wynik, key=lambda w: w["t"])


def podsumuj(zdarzenia, pet_id=None):
    prz = next((w for w in zdarzenia if w["zdarzenie"] == "przywolany" and (pet_id is None or w["pet_id"] == pet_id)), None)
    if prz is None:
        return None
    pet_id = prz["pet_id"]
    t0 = prz["t"]
    mine = [w for w in zdarzenia if w.get("pet_id") == pet_id or w["zdarzenie"] == "zabicie_obok_peta"]
    probki = [w for w in mine if w["zdarzenie"] == "probka" and w["pet_id"] == pet_id]
    # zniknal liczy się jako koniec tylko wtedy, gdy po nim pet nie wrócił (wznowiony/wrocil/probka)
    ostatni_zniknal = max((w["t"] for w in mine if w["zdarzenie"] == "zniknal" and w.get("pet_id") == pet_id), default=None)
    ostatni_zywy = max((w["t"] for w in mine if w["zdarzenie"] in ("probka", "wrocil", "wznowiony")
                        and w.get("pet_id") == pet_id), default=None)
    zniknal = ostatni_zniknal is not None and (ostatni_zywy is None or ostatni_zywy < ostatni_zniknal)
    t_koniec = ostatni_zniknal if zniknal else (ostatni_zywy or t0)
    # zabicia: unikalne po (potwor, x, y), bo po restarcie bota ten sam kill mógł być w dwóch plikach
    zab = {}
    for w in zdarzenia:
        if w["zdarzenie"] == "zabicie_obok_peta" and t0 <= w["t"] <= t_koniec + 1:
            zab.setdefault((w["potwor"], w["x"], w["y"]), w)
    hp = [w["pet"]["hp"] for w in probki]
    odl = [max(abs(w["pet"]["x"] - w["gracz"]["x"]), abs(w["pet"]["y"] - w["gracz"]["y"])) for w in probki]
    # spadki HP między kolejnymi próbkami: potwór obok peta, który stracił HP, dostał cios od kogoś (pet albo my)
    nie_cel = Counter()
    cel_obok = 0
    pet_dostal = 0
    pet_stracil_hp = 0
    for a, b in zip(probki, probki[1:]):
        if b["pet"]["hp"] < a["pet"]["hp"]:
            pet_dostal += 1
            pet_stracil_hp += a["pet"]["hp"] - b["pet"]["hp"]
        hp_b = {o["id"]: o["hp"] for o in b.get("obok", [])}
        for o in a.get("obok", []):
            if o["id"] in hp_b and hp_b[o["id"]] < o["hp"]:
                if o.get("cel"):
                    cel_obok += 1
                else:
                    nie_cel[o["nazwa"]] += 1
    obok_sr = statistics.mean(len(w.get("obok", [])) for w in probki) if probki else 0
    exp_start = prz["gracz"]["exp"]
    exp_koniec = probki[-1]["gracz"]["exp"] if probki else exp_start
    zyc = t_koniec - t0
    return {
        "pet_id": pet_id,
        "przywolany_t": t0,
        "zycie_s": round(zyc),
        "stan": "zniknal" if zniknal else "zyje",
        "probki": len(probki),
        "hp_min": min(hp) if hp else None,
        "hp_ostatnie": hp[-1] if hp else None,
        "hp_sr": round(statistics.mean(hp), 1) if hp else None,
        "odl_sr": round(statistics.mean(odl), 1) if odl else None,
        "odl_max": max(odl) if odl else None,
        "zabicia": len(zab),
        "zabicia_na_min": round(len(zab) / (zyc / 60), 2) if zyc > 0 else None,
        "zabicia_potwory": dict(Counter(k[0] for k in zab)),
        "exp_zycie": exp_koniec - exp_start,
        "obok_srednio_potworow": round(obok_sr, 1),
        "trafienia_nie_cel": sum(nie_cel.values()),
        "trafienia_nie_cel_potwory": dict(nie_cel),
        "trafienia_cel_bota_obok_peta": cel_obok,
        "pet_stracil_hp_razy": pet_dostal,
        "pet_stracil_hp_suma": pet_stracil_hp,
        "mana_po_przywolaniu": prz["gracz"]["mana"],
        "zdarzenia": dict(Counter(w["zdarzenie"] for w in zdarzenia if w.get("pet_id") == pet_id)),
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--pet", type=int, default=None, help="id peta (domyślnie pierwszy przywołany)")
    p.add_argument("--katalog", default=KATALOG)
    a = p.parse_args(argv)
    wynik = podsumuj(wczytaj(a.katalog), a.pet)
    if wynik is None:
        print("Brak przywołania peta w logach.")
        return 1
    for k, v in wynik.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
