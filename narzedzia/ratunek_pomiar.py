#!/usr/bin/env python3
"""Ratunek F1 (SPEC_ratunek_haiku_1019): ile sygnałów „jak bot” dałby detektor na zapisanej telemetrii (offline, nic nie rusza).

  python3 -I narzedzia/ratunek_pomiar.py logi/telemetria-20261017.jsonl logi/telemetria-20261018.jsonl ...
  python3 -I narzedzia/ratunek_pomiar.py --stdout logi/mozg-stdout-1019-*.log logi/telemetria-20261019.jsonl

Wejście: rekordy `probka` (t, poz, stan, exp, akcja.co ~1/s) -> tick(); „Okrążenie N gotowe” i „[ATAK] N klików bez efektu”
z akcja.co -> zdarzenia S7/S6; `wypad_blad` z typem awarii -> S1. S5 (kroki bez skutku) jest tylko w liniach `debug:` logu
mozg-stdout (telemetria ich nie trzyma), więc liczony z plików --stdout osobno. S2 (złe piętro) wymaga trasy bieżącej
instancji, której telemetria nie zapisuje: pomiar go NIE liczy (zostaje do cienia na żywo).
Ograniczenie: próbka co ~1 s gubi pola pośrednie marszu, więc S4 (kręci się) jest tu raczej NIEDOSZACOWANY.
Wynik: sygnały na godzinę pracy bota (godziny = suma odcinków między próbkami z przerwą < 30 s), osobno na sesję i łącznie.
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ratunek  # noqa: E402

RE_OKR = re.compile(r"Okrążenie \d+ gotowe")
RE_KLIK = re.compile(r"\[ATAK\] (\d+) klików bez efektu w (\S+)")
AWARIE = {"limit_czasu", "zgubiona_pozycja", "dojscie_trasy", "utkniecie", "przejscie_bez_postepu", "lina_daleko",
          "przejscie", "przejscie_pietra", "drzwi"}
RE_KROK = re.compile(r"^(\d\d):(\d\d):(\d\d) debug: krok \S+ z \((\d+), (\d+), (\d+)\) nie ruszył")
RE_CZAS = re.compile(r"^(\d\d):(\d\d):(\d\d) ")


def z_telemetrii(pliki, konf):
    sesje = collections.defaultdict(list)
    for p in pliki:
        with open(p) as f:
            for linia in f:
                try:
                    r = json.loads(linia)
                except ValueError:
                    continue
                if r.get("typ") in ("probka", "wypad_blad"):
                    sesje[(Path(p).name, r.get("sesja"), r.get("pid"))].append(r)
    wynik = []
    for klucz, rek in sesje.items():
        rek.sort(key=lambda r: r.get("t", 0))
        det = ratunek.Detektor(konf)
        syg, godz, ost_t, ost_akcja = [], 0.0, None, None
        for r in rek:
            t = r.get("t")
            if t is None:
                continue
            if ost_t is not None and 0 < t - ost_t < ratunek.MAX_PRZERWA_S:
                godz += (t - ost_t) / 3600
            ost_t = t
            if r["typ"] == "wypad_blad":
                if r.get("rodzaj") in AWARIE or str(r.get("rodzaj", "")).startswith("przejscie"):
                    syg += det.zdarzenie("porazka_trasy", t, None, co="wyprawa", typ=r.get("rodzaj"))
                continue
            poz = r.get("poz")
            if not poz:
                continue
            syg += det.tick(t, poz, r.get("stan") or "IDZ", r.get("exp"))
            co = (r.get("akcja") or {}).get("co")
            if co and co != ost_akcja:
                if RE_OKR.search(co):
                    syg += det.zdarzenie("okrazenie", t, poz)
                m = RE_KLIK.search(co)
                if m:
                    syg += det.zdarzenie("klik_bez_efektu", t, poz, n=int(m[1]), cel=m[2])
            ost_akcja = co
        wynik.append((klucz, godz, syg))
    return wynik


def z_stdout(pliki, konf):
    """S5 z linii `debug: krok … nie ruszył` (czas z HH:MM:SS, doba z kolejności linii)."""
    wynik = []
    for p in pliki:
        det = ratunek.Detektor(konf)
        syg, godz, ost, doba, ost_s = [], 0.0, None, 0, None
        with open(p, errors="replace") as f:
            for linia in f:
                m = RE_CZAS.match(linia)
                if not m:
                    continue
                s = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
                if ost_s is not None and s < ost_s - 3600:
                    doba += 86400
                t = doba + s
                if ost is not None and 0 < t - ost < ratunek.MAX_PRZERWA_S:
                    godz += (t - ost) / 3600
                ost, ost_s = t, s
                k = RE_KROK.match(linia)
                if k:
                    poz = (int(k[4]), int(k[5]), int(k[6]))
                    if det.ost_poz != poz:              # offline nie ma tick(): zmiana pozycji zeruje serię tutaj
                        det.kroki_zle, det.ost_poz = 0, poz
                    syg += det.zdarzenie("krok_nieudany", t, poz)
                elif " Nowy cel" in linia or "zabity" in linia or "[IDZ]" in linia:
                    det.kroki_zle = 0           # bot zrobił coś innego: seria nieudanych kroków przerwana
        wynik.append(((Path(p).name,), godz, syg))
    return wynik


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("pliki", nargs="+", help="telemetria-*.jsonl i/lub (po --stdout) mozg-stdout-*.log")
    ap.add_argument("--stdout", action="store_true", help="pliki *.log traktuj jako mozg-stdout (S5)")
    ap.add_argument("--szczegoly", action="store_true", help="wypisz każdy sygnał")
    a = ap.parse_args(argv)
    konf = type("K", (), dict(ratunek.DOMYSLNE, RATUNEK_HAIKU=1))
    tele = [p for p in a.pliki if p.endswith(".jsonl")]
    logi = [p for p in a.pliki if p.endswith(".log")] if a.stdout else []
    wyniki = z_telemetrii(tele, konf) + (z_stdout(logi, konf) if logi else [])
    razem_h, razem = 0.0, collections.Counter()
    print(f"{'źródło':60s} {'godz':>6s}  sygnały")
    for klucz, godz, syg in wyniki:
        if godz < 0.05 and not syg:
            continue
        c = collections.Counter(s["kod"] for s in syg)
        if not klucz[0].endswith(".log"):
            razem_h += godz
        razem.update(c)
        print(f"{' '.join(str(k) for k in klucz)[:60]:60s} {godz:6.2f}  {dict(sorted(c.items()))}")
        if a.szczegoly:
            for s in syg:
                print(f"      {s['kod']} {s['poz']} " + ", ".join(f"{k}={v}" for k, v in s.items()
                                                            if k not in ("kod", "opis", "t", "poz", "ponad_limit")))
    n = sum(razem.values())
    print(f"\nRAZEM telemetria: {razem_h:.1f} h pracy bota; sygnały {dict(sorted(razem.items()))} = {n}"
          f" ({n / razem_h:.1f}/h)" if razem_h else "\nbrak godzin pracy w telemetrii")
    return 0


if __name__ == "__main__":
    sys.exit(main())
