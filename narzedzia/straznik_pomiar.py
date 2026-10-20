#!/usr/bin/env python3
"""Strażnik orbit (SPEC_orbity_straznik_1020, B(e)): ile wyzwoleń dałby strażnik na zapisanej telemetrii (offline, tylko odczyt).

  python3 -I narzedzia/straznik_pomiar.py                      # domyślne pliki z głównego checkoutu (logi/ i instancje/*/logi/)
  python3 -I narzedzia/straznik_pomiar.py --baza /ścieżka/do/pomocnik --pol 6 --okno 60
  python3 -I narzedzia/straznik_pomiar.py logi/telemetria-20261020.jsonl ...

Puszcza SAM detektor (straznik_orbity.Detektor, bez reakcji) po próbkach `typ == "probka"` (t, poz, stan, exp), osobno dla każdej
sesji (plik, sesja, pid). Wyzwolenie `orbita` = >= 8 zmian pozycji w oknie, wszystkie na jednym piętrze w <= --pol polach, poza walką.
Kryterium S2 (złe piętro) wymaga trasy bieżącej instancji, której telemetria nie zapisuje: NIE jest tu liczone.
Debounce detektora (300 s, 5 pól) jest ten sam co na żywo; kolejne wyzwolenia tego samego miejsca w odstępie <= 330 s
scalamy w jeden epizod (kolumna `x`). Wynik: tabela epizodów (plik, czas lokalny, piętro, pola, zmiany, stany, przyrost expa) + podsumowanie."""
import argparse
import collections
import glob
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import straznik_orbity  # noqa: E402

BAZA = Path("/home/charlie/Games/Retronic/pomocnik")
SCAL_S = 330.0


def pliki_domyslne(baza):
    p = sorted(glob.glob(str(baza / "logi" / "telemetria-2026101*.jsonl")))
    p += sorted(glob.glob(str(baza / "logi" / "telemetria-20261020.jsonl")))
    p += sorted(glob.glob(str(baza / "instancje" / "*" / "logi" / "telemetria-*.jsonl")))
    return p


def czytaj(plik):
    sesje = collections.defaultdict(list)
    with open(plik) as f:
        for linia in f:
            if '"probka"' not in linia:
                continue
            try:
                r = json.loads(linia)
            except ValueError:
                continue
            if r.get("typ") == "probka" and r.get("t") is not None and r.get("poz"):
                sesje[(r.get("sesja"), r.get("pid"))].append(r)
    return sesje


def mierz(pliki, konf, baza):
    epizody, godz_lacznie, probek = [], 0.0, 0
    for plik in pliki:
        nazwa = str(Path(plik).relative_to(baza)) if str(plik).startswith(str(baza)) else str(plik)
        for klucz, rek in czytaj(plik).items():
            rek.sort(key=lambda r: r["t"])
            det = straznik_orbity.Detektor(konf)
            ost_t = None
            for r in rek:
                t = r["t"]
                probek += 1
                if ost_t is not None and 0 < t - ost_t < straznik_orbity.MAX_PRZERWA_S:
                    godz_lacznie += (t - ost_t) / 3600
                ost_t = t
                for zd in det.tick(t, r["poz"], r.get("stan") or "IDZ", False, r.get("exp")):
                    ep = epizody[-1] if epizody else None
                    if ep and ep["plik"] == nazwa and ep["sesja"] == klucz and ep["poz"][2] == zd["poz"][2] \
                            and zd["t"] - ep["t_ost"] <= SCAL_S and max(abs(ep["poz"][0] - zd["poz"][0]), abs(ep["poz"][1] - zd["poz"][1])) <= 8:
                        ep["x"] += 1
                        ep["t_ost"] = zd["t"]
                        continue
                    epizody.append(dict(zd, plik=nazwa, sesja=klucz, x=1, t_ost=zd["t"]))
    return epizody, godz_lacznie, probek


def czas(t):
    return time.strftime("%m-%d %H:%M:%S", time.localtime(t))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pliki", nargs="*")
    ap.add_argument("--baza", default=str(BAZA), help="katalog główny (domyślnie główny checkout, tylko odczyt)")
    ap.add_argument("--okno", type=float, default=straznik_orbity.DOMYSLNE["STRAZNIK_ORBITA_S"])
    ap.add_argument("--pol", type=int, default=straznik_orbity.DOMYSLNE["STRAZNIK_ORBITA_POL"])
    ap.add_argument("--zmian", type=int, default=straznik_orbity.DOMYSLNE["STRAZNIK_ORBITA_ZMIAN"], help="minimalna liczba zmian pozycji w oknie (Karol 20.10: 15)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    baza = Path(a.baza)
    pliki = a.pliki or pliki_domyslne(baza)
    konf = SimpleNamespace(**dict(straznik_orbity.DOMYSLNE, STRAZNIK_ORBITA_S=a.okno, STRAZNIK_ORBITA_POL=a.pol, STRAZNIK_ORBITA_ZMIAN=a.zmian))
    epizody, godz, probek = mierz(pliki, konf, baza)
    if a.json:
        print(json.dumps([{k: v for k, v in e.items() if k != "sesja"} for e in epizody], ensure_ascii=False, indent=1))
        return
    print(f"# plików {len(pliki)}, próbek {probek}, ~{godz:.1f} h pracy bota, okno {a.okno:.0f} s, pól <= {a.pol}, zmian >= {a.zmian}")
    print(f"{'plik':46} {'czas':15} {'z':>2} {'pola':>4} {'zm':>3} {'x':>2} {'trwa s':>6} {'exp+':>6}  środek / stany")
    for e in epizody:
        ps = e["pola"]
        sr = (round(sum(p[0] for p in ps) / len(ps)), round(sum(p[1] for p in ps) / len(ps)))
        print(f"{e['plik'][-46:]:46} {czas(e['t']):15} {e['poz'][2]:>2} {len(ps):>4} {e['zmian']:>3} {e['x']:>2} "
              f"{e['czas_s']:>6.0f} {str(e['exp_przyrost']):>6}  {sr} {e['stany']}")
    print(f"# epizodów: {len(epizody)} (wyzwoleń po debounce: {sum(e['x'] for e in epizody)}); "
          f"na godzinę pracy: {len(epizody) / godz if godz else 0:.2f}")


if __name__ == "__main__":
    main()
