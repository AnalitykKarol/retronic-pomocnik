"""Mapa + tryb (mapy.json, tryby.json) dla uruchom.sh. Nie uruchamia bota.

  python3 -I tryb.py --mapa raty --tryb sredni,runy [--na-zywo PLIK] [--sucho]
Wypisuje na stdout przypisania dla basha (MAPA_TRASA, MAPA_POTWORY, MAPA_PROG_HP, MAPA_DOJSCIE, MAPA_OPIS),
loguje "[TRYB] ..." na stderr i do logi/tryb.log, a pokrętła trybów scala (od lewej do prawej) do na_zywo.json
z kopią poprzedniego pliku (na_zywo.json.bak-<czas>). Kod wyjścia 2 = błąd (nieznana mapa/tryb, niepoprawne pokrętło)."""
import argparse
import json
import shlex
import sys
import time
from pathlib import Path

KAT = Path(__file__).resolve().parent
sys.path.insert(0, str(KAT))
import instancja  # noqa: E402


def log(t, plik_logu):
    linia = f"{time.strftime('%Y-%m-%d %H:%M:%S')} [TRYB] {t}"
    print(linia, file=sys.stderr)
    try:
        Path(plik_logu).parent.mkdir(parents=True, exist_ok=True)
        with open(plik_logu, "a") as f:
            f.write(linia + "\n")
    except OSError:
        pass


def wczytaj(nazwa):
    d = json.loads((KAT / nazwa).read_text())
    return {k: v for k, v in d.items() if not k.startswith("_")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mapa", default="raty")
    ap.add_argument("--tryb", default="")
    ap.add_argument("--na-zywo", default=str(instancja.S.na_zywo))
    ap.add_argument("--log", default=str(instancja.S.tryb_log))
    ap.add_argument("--sucho", action="store_true", help="nic nie zapisuj")
    a = ap.parse_args(argv)
    import pokretla  # noqa: PLC0415
    mapy, tryby = wczytaj("mapy.json"), wczytaj("tryby.json")
    if a.mapa not in mapy:
        log(f"nieznana mapa {a.mapa!r}, dostępne: {', '.join(mapy)}", a.log)
        return 2
    nazwy = [n.strip() for n in a.tryb.split(",") if n.strip()]
    for n in nazwy:
        if n not in tryby:
            log(f"nieznany tryb {n!r}, dostępne: {', '.join(tryby)}", a.log)
            return 2
    scalone = {}
    for n in nazwy:
        scalone.update(tryby[n].get("pokretla", {}))
    ok, bledy = pokretla.waliduj(scalone)
    if bledy:
        for b in bledy:
            log(f"niepoprawne pokrętło trybu: {b}", a.log)
        return 2
    m = mapy[a.mapa]
    log(f"mapa {a.mapa}: trasa {m['trasa']}, potwory {m['potwory']}, prog-hp {m['prog_hp']}"
        + (f", dojście {m['dojscie']}" if m.get("dojscie") else ""), a.log)
    if nazwy:
        plik = Path(a.na_zywo)
        try:
            przed = json.loads(plik.read_text())
            if not isinstance(przed, dict):
                przed = {}
        except (OSError, ValueError):
            przed = {}
        po = {**przed, **ok}
        zmiany = {k: (przed.get(k, "(brak)"), v) for k, v in ok.items() if przed.get(k, "\0") != v}
        log(f"tryb {'+'.join(nazwy)}: pokrętła {json.dumps(ok, ensure_ascii=False)}", a.log)
        if not zmiany:
            log("na_zywo.json bez zmian", a.log)
        elif a.sucho:
            for k, (s, n) in zmiany.items():
                log(f"(sucho) {k}: {s} -> {n}", a.log)
        else:
            if plik.exists():
                kopia = plik.with_name(plik.name + time.strftime(".bak-%Y%m%d-%H%M%S"))
                kopia.write_text(plik.read_text())
                log(f"kopia poprzedniego pliku: {kopia.name}", a.log)
            plik.write_text(json.dumps(po, ensure_ascii=False, indent=1))
            for k, (s, n) in zmiany.items():
                log(f"na_zywo.json: {k}: {s} -> {n}", a.log)
    for k, v in (("MAPA_TRASA", m["trasa"]), ("MAPA_POTWORY", m["potwory"]), ("MAPA_PROG_HP", m["prog_hp"]),
                 ("MAPA_DOJSCIE", m.get("dojscie", "")), ("MAPA_OPIS", m.get("opis", ""))):
        print(f"{k}={shlex.quote(str(v))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
