"""Lina przed startem (21.10, Karol „tak”): trasa albo dojście, które przechodzi liną, nie rusza bez liny.

Przypadek: 21.10 17:12 Kolanosh na `trolle_edron_z9w` (dojście wchodzi liną z11 -> z7) bez liny utknął na (33134,31806,z11),
Karol go wylogował. Bot nie sprawdzał ekwipunku przed startem.

- znane_liny(): pola lin (x, y, z piętra startu) z `dane_tibia/ruch/liny_znane.json` (generowane z logów botów: udane przejścia
  „lina”, lądowanie (x, y+1, z-1)) i z pamięci przejść (`wypad.PLIK_PRZEJSC`, tryb "lina").
- wymaga_liny(punkty): przejścia w górę na trasie, które wypadają przy znanym polu liny.
- ma_line(): czy w otwartych pojemnikach albo w ekwipunku jest lina (pamięć gry, bez ekranu): True / False / None (brak odczytu).

CLI: `python3 -I liny.py generuj` (przebudowa pliku z logów), `python3 -I liny.py trasa <nazwa> [<nazwa>...]`."""
import glob
import json
import os
import re
import sys
from pathlib import Path

KATALOG = Path(__file__).resolve().parent
PLIK = KATALOG / "dane_tibia" / "ruch" / "liny_znane.json"
ID_LINA = 3003
RE_SUKCES = re.compile(r"Przejście pięter: z(\d+) -> z(\d+) w \((\d+), (\d+), (\d+)\) \(próba \d+, lina"
                       r"|Wypad: lina z(\d+) -> z(\d+) w \((\d+), (\d+), (\d+)\)")


def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def z_logow(pliki):
    """Pola lin z udanych przejść „lina” w logach: lądowanie L na z-1 -> pole liny (L.x, L.y-1, z)."""
    wyn = {}
    for f in pliki:
        try:
            tekst = Path(f).read_text(errors="replace")
        except OSError:
            continue
        for linia in tekst.splitlines():
            if "lina" not in linia:
                continue
            m = RE_SUKCES.search(linia)
            if not m:
                continue
            z_od, z_do, x, y, z = (int(v) for v in m.groups() if v is not None)
            if z_do != z_od - 1 or z != z_do:
                continue
            pole = (x, y - 1, z_od)
            wyn[pole] = wyn.get(pole, 0) + 1
    return wyn


def generuj(plik=PLIK):
    pliki = glob.glob(str(KATALOG / "instancje" / "*" / "logi" / "mozg-stdout-*.log")) + \
        glob.glob(str(KATALOG / "instancje" / "_archiwum" / "*" / "logi" / "mozg-stdout-*.log"))
    liny = z_logow(pliki)
    dane = {"opis": "pola lin (x, y, z piętra startu) z udanych przejść liną w logach botów; liny.py generuj",
            "liny": [[*p, n] for p, n in sorted(liny.items())]}
    plik = Path(plik)
    tmp = plik.with_name(f".{plik.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(dane, ensure_ascii=False, indent=1) + "\n")
    os.replace(tmp, plik)
    return liny


def znane_liny(plik=PLIK, plik_przejsc=None):
    wyn = set()
    try:
        for e in json.loads(Path(plik).read_text()).get("liny", []):
            wyn.add((int(e[0]), int(e[1]), int(e[2])))
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    try:
        import wypad  # noqa: PLC0415
        for k, v in wypad.przejscia_nauczone(plik_przejsc).items():
            if isinstance(v, dict) and v.get("tryb") == "lina":
                pole, z_do = k.split(">")
                x, y, z = (int(c) for c in pole.split(","))
                if int(z_do) == z - 1:
                    wyn.add((x, y, z))
    except Exception:
        pass
    return wyn


def wymaga_liny(punkty, liny=None):
    """Lista (a, b, pole_liny) przejść w górę a -> b (z o 1 niżej), przy których leży znane pole liny (<= 1 pole od a i od b)."""
    liny = znane_liny() if liny is None else liny
    wyn = []
    for a, b in zip(punkty, punkty[1:]):
        a, b = tuple(a[:3]), tuple(b[:3])
        if b[2] != a[2] - 1:
            continue
        for s in liny:
            if s[2] == a[2] and _cheb(s, a) <= 1 and _cheb(s, b) <= 1:
                wyn.append((a, b, s))
                break
    return wyn


def ma_line(zapytaj=None):
    """True/False: lina w otwartych pojemnikach albo w ekwipunku (pamięć gry); None: brak odczytu."""
    try:
        if zapytaj is None:
            import loot  # noqa: PLC0415
            zapytaj = loot._zapytaj
        odp = zapytaj({"cmd": "kontenery", "ekwipunek": True})
    except Exception:
        return None
    if not isinstance(odp, dict) or odp.get("blad"):
        return None
    for k in odp.get("kontenery") or []:
        if any(int(p.get("id", -1)) == ID_LINA for p in k.get("przedmioty", [])):
            return True
    eq = odp.get("ekwipunek")
    if isinstance(eq, dict) and any(int((v or {}).get("id", -1)) == ID_LINA for v in eq.values()):
        return True
    if eq is None and not odp.get("kontenery"):
        return None
    return False


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    if len(sys.argv) > 1 and sys.argv[1] == "generuj":
        liny = generuj()
        print(f"{len(liny)} pól lin -> {PLIK}")
        for p, n in sorted(liny.items()):
            print(" ", p, n)
    elif len(sys.argv) > 2 and sys.argv[1] == "trasa":
        for nazwa in sys.argv[2:]:
            pts = json.loads((KATALOG / "trasy" / f"{nazwa}.json").read_text())
            w = wymaga_liny(pts)
            print(f"{nazwa}: {'wymaga liny' if w else 'bez liny'}", *(f"\n  {a} -> {b} (lina {s})" for a, b, s in w))
    else:
        print(__doc__)
