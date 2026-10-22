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
    # stanowisko (22.10): cavebot nie widzi wpisu mapy, więc opis stanowiska leży obok na_zywo.json; mapa bez wpisu = plik znika
    # (przełącznikiem jest też pokrętło STANOWISKO; bez pliku cavebot zachowuje się jak dotąd)
    plik_st = Path(a.na_zywo).parent / "stanowisko_mapa.json"
    if m.get("stanowisko"):
        st = m["stanowisko"]
        if not st.get("pz_zmierzone"):
            log(f"UWAGA: pola PZ mapy {a.mapa} niezmierzone, cele ucieczki to {st.get('pz')} (pomiar Karola: mapy.json stanowisko.pz)", a.log)
        if "STANOWISKO" not in ok and "stoj" not in nazwy:
            log("UWAGA: mapa ze stanowiskiem bez trybu stoj: STANOWISKO zostaje jak w na_zywo.json (domyślnie 0 = zwykła trasa)", a.log)
        if not a.sucho:
            try:
                plik_st.write_text(json.dumps(st, ensure_ascii=False, indent=1))
                log(f"stanowisko: zapisano {plik_st.name}", a.log)
            except OSError as e:
                log(f"stanowisko: nie zapisano {plik_st} ({e})", a.log)
    elif plik_st.exists() and not a.sucho:
        try:
            plik_st.unlink()
            log(f"stanowisko: usunięto {plik_st.name} (mapa {a.mapa} bez stanowiska)", a.log)
        except OSError:
            pass
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
                 ("MAPA_DOJSCIE", m.get("dojscie", "")),
                 ("MAPA_DOJSCIE_WSZEDZIE", "1" if m.get("dojscie_z_dowolnego_pietra") else ""), ("MAPA_OPIS", m.get("opis", ""))):
        print(f"{k}={shlex.quote(str(v))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
