"""Sklep na postaci-magazynie (trade_start.sh / trade_stop.sh): włączanie i wyłączanie pokręteł Trade w na_zywo.json instancji.

Pokrętła TRADE_OGLOSZENIA i TRADE_PRIV_ODPOWIEDZI mają domyślnie 0 (cavebot.py), a mozg.py --bez-ruchu czyta je z na_zywo.json
(hot reload co 2 s). Bez wpisu 1 sklep po starcie nic nie robił. Użycie (instancja z RETRONIC_ID):
  python3 -I trade_sklep.py wlacz     # TRADE_OGLOSZENIA=1, TRADE_PRIV_ODPOWIEDZI=1 (kopia na_zywo.json.bak-RRRRMMDD-sklep przy pierwszej zmianie)
  python3 -I trade_sklep.py wylacz    # usuwa oba wpisy (powrót do domyślnych 0), reszta pliku bez zmian
  python3 -I trade_sklep.py stan      # JSON z bieżącymi wartościami
Zapis atomowy (plik tymczasowy + rename); plik z błędnym JSON-em NIE jest ruszany (kod 1)."""
import json
import os
import shutil
import sys
import time
from pathlib import Path

KLUCZE = ("TRADE_OGLOSZENIA", "TRADE_PRIV_ODPOWIEDZI")


def _wczytaj(plik):
    plik = Path(plik)
    if not plik.exists():
        return {}
    dane = json.loads(plik.read_text())
    if not isinstance(dane, dict):
        raise ValueError("na_zywo.json nie jest obiektem JSON")
    return dane


def _zapisz(plik, dane):
    plik = Path(plik)
    if plik.exists():
        kopia = plik.with_name(f"{plik.name}.bak-{time.strftime('%Y%m%d')}-sklep")
        if not kopia.exists():
            shutil.copy2(plik, kopia)
    tmp = plik.with_name(plik.name + ".tmp-sklep")
    tmp.write_text(json.dumps(dane, indent=1, ensure_ascii=False))
    os.replace(tmp, plik)


def ustaw(plik, wlacz):
    """-> True, gdy plik się zmienił. wlacz=True: oba klucze = 1; False: oba usunięte."""
    dane = _wczytaj(plik)
    nowe = dict(dane)
    for k in KLUCZE:
        if wlacz:
            nowe[k] = 1
        else:
            nowe.pop(k, None)
    if nowe == dane:
        return False
    _zapisz(plik, nowe)
    return True


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) != 1 or a[0] not in ("wlacz", "wylacz", "stan"):
        print(__doc__, file=sys.stderr)
        return 2
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import instancja  # noqa: PLC0415
    plik = instancja.S.na_zywo
    try:
        if a[0] == "stan":
            d = _wczytaj(plik)
            print(json.dumps({k: d.get(k, 0) for k in KLUCZE}))
            return 0
        zmieniono = ustaw(plik, a[0] == "wlacz")
    except (OSError, ValueError) as e:
        print(f"trade_sklep: {plik}: {e} (plik nietknięty)", file=sys.stderr)
        return 1
    print(f"{plik}: {'zmieniono' if zmieniono else 'bez zmian'} ({a[0]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
