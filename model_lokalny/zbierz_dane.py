"""Wszystkie dostępne dane telemetrii w jednym katalogu do treningu (15.10, decyzja Karola: brać wszystko).

Źródła: logi/telemetria-*.jsonl (ten komputer) + dane_ai/telemetria/<źródło>/telemetria-*.jsonl.gz (paczki z gita,
np. drugi komputer). Pliki z tą samą datą są sklejane w jeden telemetria-RRRRMMDD.jsonl (rekordy mają pid/sesja,
więc to różne procesy, nie duplikaty; zbior.py sortuje po czasie). Dokładne duplikaty linii (ta sama paczka
wgrana dwa razy) są pomijane.

Użycie: python3 -I model_lokalny/zbierz_dane.py WYJSCIE [--bez-lokalnych]
potem:  python3 -I model_lokalny/trenuj.py D1 --logi WYJSCIE --wyjscie DIR"""
import argparse
import glob
import gzip
import hashlib
import os
import re
import sys

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WZOR = re.compile(r"telemetria-(\d{8})\.jsonl(\.gz)?$")


def zrodla(korzen=KORZEN, lokalne=True):
    """[(źródło, ścieżka, data)] wszystkich plików telemetrii."""
    wynik = []
    if lokalne:
        for p in sorted(glob.glob(os.path.join(korzen, "logi", "telemetria-*.jsonl"))):
            m = WZOR.search(os.path.basename(p))
            if m:
                wynik.append(("lokalne", p, m.group(1)))
    for p in sorted(glob.glob(os.path.join(korzen, "dane_ai", "telemetria", "*", "telemetria-*.jsonl*"))):
        m = WZOR.search(os.path.basename(p))
        if m:
            wynik.append((os.path.basename(os.path.dirname(p)), p, m.group(1)))
    return wynik


def zbierz(wyjscie, korzen=KORZEN, lokalne=True, log=print):
    os.makedirs(wyjscie, exist_ok=True)
    for p in glob.glob(os.path.join(wyjscie, "telemetria-*.jsonl")):
        os.remove(p)
    widziane = set()
    staty = {}
    for zrodlo, sciezka, data in zrodla(korzen, lokalne):
        otworz = gzip.open if sciezka.endswith(".gz") else open
        n = dup = 0
        with otworz(sciezka, "rt", encoding="utf-8", errors="replace") as we, \
                open(os.path.join(wyjscie, f"telemetria-{data}.jsonl"), "a", encoding="utf-8") as wy:
            for linia in we:
                if not linia.strip():
                    continue
                h = hashlib.blake2b(linia.encode("utf-8", "replace"), digest_size=12).digest()
                if h in widziane:
                    dup += 1
                    continue
                widziane.add(h)
                wy.write(linia if linia.endswith("\n") else linia + "\n")
                n += 1
        s = staty.setdefault(zrodlo, [0, 0])
        s[0] += n
        s[1] += dup
    for zrodlo, (n, dup) in sorted(staty.items()):
        log(f"{zrodlo}: {n} rekordów, pominięte duplikaty {dup}")
    return staty


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sklejenie całej dostępnej telemetrii do treningu.")
    ap.add_argument("wyjscie")
    ap.add_argument("--bez-lokalnych", action="store_true", help="tylko paczki z dane_ai/telemetria")
    a = ap.parse_args(argv)
    zbierz(a.wyjscie, lokalne=not a.bez_lokalnych)
    return 0


if __name__ == "__main__":
    sys.exit(main())
