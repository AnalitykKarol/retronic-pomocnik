#!/usr/bin/env python3
"""Statystyka dobijania z telemetrii (bez uruchamiania bota): python3 -I statystyki.py [--godz N]
Okna: 5 min, 1 h, ostatnie N godz (domyślnie 24). Tabela + 10 najgorszych porzuconych epizodów."""
import argparse
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import telemetria  # noqa: E402


def _f(x, suf=""):
    return "-" if x is None else f"{x:g}{suf}"


def tabela(rek, teraz, godz):
    ref = telemetria.exp_ref(rek)
    okna = [("5 min", 300), ("1 h", 3600), (f"{godz:g} h", godz * 3600)]
    kol = ["okno", "epiz.", "zabite", "porz.", "zgub.", "dobicie", "med s", "p90 s", "med<30% s", "p90<30% s",
           "exp zdob.", "exp strac.", "% utr."]
    w = [kol]
    for nazwa, s in okna:
        d = telemetria.dobicie([r for r in rek if r["t"] >= teraz - s], ref_exp=ref)
        w.append([nazwa, d["epizody"], d["zabite"], d["porzucone"], d["zgubione"],
                  "-" if d["wskaznik"] is None else f"{d['wskaznik']}%", _f(d["med_do_zab_s"]), _f(d["p90_do_zab_s"]),
                  _f(d["med_od30_s"]), _f(d["p90_od30_s"]), d["exp_zdobyty"] or "-",
                  d["exp_stracony"] or ("-" if d["exp_bez_danych"] else 0),
                  "-" if d["exp_utracony_proc"] is None else f"{d['exp_utracony_proc']}%"])
    sz = [max(len(str(r[i])) for r in w) for i in range(len(kol))]
    return "\n".join("  ".join(str(c).rjust(sz[i]) for i, c in enumerate(r)) for r in w)


def najgorsze(rek, teraz, godz, ile=10):
    """Porzucone/zgubione z trafieniem; najgorsze = zostawione z najniższym HP% (prawie martwe)."""
    lista = [r for r in telemetria.scal_epizody(rek) if r["typ"] == "epizod_celu" and r.get("trafiony") and r["wynik"] != "zabity"
             and r["t"] >= teraz - godz * 3600]
    lista.sort(key=lambda r: (r.get("hp_porz") if r.get("hp_porz") is not None else 101, -r["t"]))
    return lista[:ile]


def raport(rek, teraz, godz):
    out = [tabela(rek, teraz, godz), ""]
    ep = [r for r in telemetria.scal_epizody(rek) if r["typ"] == "epizod_celu" and r.get("trafiony")
          and r["wynik"] != "zabity" and r["t"] >= teraz - godz * 3600]
    if ep:
        pw = Counter(r.get("powod") or "?" for r in ep)
        out.append("Powody utraty: " + ", ".join(f"{k} x{v}" for k, v in pw.most_common()))
        out.append("")
    out.append("10 najgorszych porzuconych (najniższe HP% przy porzuceniu):")
    ng = najgorsze(rek, teraz, godz)
    if not ng:
        out.append("  brak")
    for r in ng:
        out.append(f"  {time.strftime('%H:%M:%S', time.localtime(r['t']))}  {r['n']:<14} HP {_f(r.get('hp_porz'), '%'):>5}  "
                   f"{r['wynik']}: {(r.get('powod') or '?'):<26} poz {r.get('pos')}  kroki {r.get('kroki')}  "
                   f"uciekl {r.get('uciekl')}x")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--godz", type=float, default=24, help="okno raportu w godzinach (domyślnie 24)")
    a = ap.parse_args(argv)
    teraz = time.time()
    rek = telemetria.wczytaj_rekordy(od_t=teraz - a.godz * 3600)
    if not any(r["typ"] == "epizod_celu" for r in rek):
        # telemetria sprzed nowego kodu: odtwarzamy epizody ze zdarzeń nowy_cel/odpuszczenie/zabicie
        surowe = telemetria.wczytaj_rekordy(od_t=teraz - a.godz * 3600 - 600, wszystko=True)
        surowe += telemetria.zdarzenia_z_logow(od_t=teraz - a.godz * 3600 - 600)
        rek = telemetria.odtworz_epizody(surowe)
        if not rek:
            print("Brak epizodów celu w telemetrii.")
            return 0
        print("(epizody odtworzone ze starszej telemetrii; exp niedostępny, zmiany celu i zniknięcia z logów bota)\n")
    print(raport(rek, teraz, a.godz))
    return 0


if __name__ == "__main__":
    sys.exit(main())
