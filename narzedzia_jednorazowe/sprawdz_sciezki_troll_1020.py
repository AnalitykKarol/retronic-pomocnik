#!/usr/bin/env python3
"""Offline (bez gry): ścieżki patrolu między miejscami m1-m8 (i ze startu) kodem bota, z kontrolą pól blokujących.

  python3 -I narzedzia_jednorazowe/sprawdz_sciezki_troll_1020.py [--trasy KATALOG | --rev REWIZJA] [--pary]

Źródło danych: --trasy (domyślnie trasy/ obok skryptu) albo --rev (pliki trasy/ z `git show REWIZJA:...`, np. 2395bef
= stan przed poprawką 20.10). Droga = cavebot._patrol_droga (A* po mapie + graf przejść i łączników z miejsca_troll.json),
z blokadami jak na żywo: nauczone dziury (dziury_nauczone.json tej samej wersji), schody/dziury z mapy, pola ognia z
potwierdzonym spadkiem HP (ogien_epizody.json). Dla każdej drogi liczy pola, które w grze blokują albo których bot
ma nie wchodzić:
  dziura   - pole z nauczonych dziur (wchodzenie = ściana dla kroków i A*; dla fałszywej dziury droga ją mija albo się łamie)
  sciana   - flaga 4 mapy (poza drzwiami z drzwi_jaskinia.json)
  przejscie- pole zmiany piętra (flaga 2 mapy) na drodze (A* ich nie używa; pola wejścia i lądowania przejść to zwykłe podłogi)
  ogien    - pole ognia z potwierdzonym spadkiem HP
  statua   - pola znane z doświadczenia jako zablokowane w grze mimo chodliwej mapy (BLOKADY_ZNANE)
Kod wyjścia 1, gdy którakolwiek droga ma pole z klas dziura/sciana/przejscie/ogien albo brak drogi.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path

os.environ.setdefault("RETRONIC_TESTY", "1")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import cavebot  # noqa: E402
import mapa as _mapa  # noqa: E402

# pola chodliwe wg mapy, a blokujące w grze (dowód: dane_tibia/ruch/MAPA_DOSWIADCZENIA.md 3.4, trasy/pietra_zle.json);
# tylko raportowane (nie są w żadnym pliku, który omija A*), nie liczą się do kodu wyjścia
BLOKADY_ZNANE = {(32483, 32296, 9): "statua/przedmiot (297 prób 'krok Up', 1 udana)"}


def wczytaj_z_gita(rev, katalog):
    for nazwa in ("miejsca_troll.json", "dziury_nauczone.json", "ogien_epizody.json", "drzwi_jaskinia.json"):
        try:
            txt = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{rev}:trasy/{nazwa}"], text=True)
        except subprocess.CalledProcessError:
            continue
        (katalog / nazwa).write_text(txt)


class Swiat:
    def __init__(s):
        s.t = 0.0

    def zegar(s):
        return s.t

    def zapytaj(s, z):
        if z["cmd"] == "gracz":
            return {"gracz": {"hp": 100, "max_hp": 100, "mana": 95, "max_mana": 95}}
        return {"stwory": []}


class P:
    nazwa = "Ja"

    def __init__(p, s):
        p.s = s

    def pozycja(p):
        return (32493, 32260, 8)


def zrob(kat):
    cavebot.log = lambda *a: None
    for h in ("_hak_telemetrii", "_hak_pochodni", "_hak_wypadu"):
        setattr(cavebot.Cavebot, h, lambda self: None)
    cavebot.KATALOG_TRAS = Path(kat)
    cavebot.PATROL_PLIK = "miejsca_troll.json"
    cavebot.TRYB_PATROL = 1
    cavebot.PLIK_DRZWI = Path(kat) / "drzwi_jaskinia.json"
    s = Swiat()
    cb = cavebot.Cavebot(P(s), [(32493, 32260, 8), (32492, 32260, 8)], zapytaj=s.zapytaj, atak=lambda a, b: None,
                         alarm=lambda w: None, spij=lambda d: None, zegar=s.zegar,
                         loot=types.SimpleNamespace(zbierz=lambda z, g: "ok"), mapa=_mapa.mapa(), czas_s=10 ** 7)
    cb.zapis_znanych = False
    w = cb._wp()
    pd = Path(kat) / "dziury_nauczone.json"
    w.dziury = {tuple(int(v) for v in e) for e in json.loads(pd.read_text()).get("dziury", [])} if pd.is_file() else set()
    pe = Path(kat) / "ogien_epizody.json"
    cb.ogien_epizody = json.loads(pe.read_text()).get("pola", {}) if pe.is_file() else {}
    return cb


def klasy(cb, droga, wyjatki):
    """Pola drogi (x, y, z) w klasach 'blokujących'. wyjatki: pola przejść (pole wejścia/lądowania), dozwolone mimo flagi 2."""
    m = cb.mapa
    dz = cb._wp().dziury
    ogien = {z: cb._ogien_parzy_dane(z) for z in (8, 9)}
    wynik = {"dziura": [], "sciana": [], "przejscie": [], "ogien": [], "statua": []}
    for p in droga:
        x, y, z = p
        if p in dz:
            wynik["dziura"].append(p)
        f = m.flagi(x, y, z)
        if f & 4 and (x, y) not in cb._drzwi_xy(z):
            wynik["sciana"].append(p)
        if f & 2 and p not in wyjatki:
            wynik["przejscie"].append(p)
        if (x, y) in ogien.get(z, ()):
            wynik["ogien"].append(p)
        if p in BLOKADY_ZNANE:
            wynik["statua"].append(p)
    return wynik


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trasy", default=str(ROOT / "trasy"))
    ap.add_argument("--rev")
    ap.add_argument("--pary", action="store_true", help="wypisz każdą parę osobno")
    a = ap.parse_args(argv)
    tmp = None
    kat = a.trasy
    if a.rev:
        tmp = tempfile.TemporaryDirectory()
        kat = tmp.name
        wczytaj_z_gita(a.rev, Path(kat))
    cb = zrob(kat)
    cb._patrol_wczytaj()
    miejsca = cb.miejsca
    wyjatki = set()   # pola lądowania i wejścia przejść to zwykłe podłogi: flaga 2 na drodze jest zawsze błędem
    start = tuple(json.loads((Path(kat) / "miejsca_troll.json").read_text())["start"])
    zrodla = [("START", start)] + [(f"m{m['id']}", (m["x"], m["y"], m["z"])) for m in miejsca]
    suma = {"dziura": 0, "sciana": 0, "przejscie": 0, "ogien": 0, "statua": 0}
    brak, zle_drogi, n = [], [], 0
    print(f"dane: {kat} | dziur nauczonych: {len(cb._wp().dziury)} | ognia z HP: {sum(len(cb._ogien_parzy_dane(z)) for z in (8, 9))}")
    for nm, poz in zrodla:
        for m in miejsca:
            cel = (m["x"], m["y"], m["z"])
            if poz == cel:
                continue
            uz = []
            d = cb._patrol_droga(poz, m, uz)
            n += 1
            if d is None:
                brak.append(f"{nm}->m{m['id']}")
                continue
            kl = klasy(cb, [tuple(p) for p in d], wyjatki)
            for k, v in kl.items():
                suma[k] += len(v)
            zl = {k: v for k, v in kl.items() if v}
            if zl and any(k != "statua" for k in zl):
                zle_drogi.append((f"{nm}->m{m['id']}", zl))
            if a.pary:
                print(f"  {nm}->m{m['id']}: {len(d)} pól, przez {[u.split(':')[0] + ':' + u.split(':')[1] for u in uz]}"
                      + (f"  BLOKUJĄCE: {zl}" if zl else ""))
    print(f"dróg: {n}, bez drogi: {brak or 'brak'}")
    print("pola blokujące na drogach (suma po wszystkich drogach):", suma)
    for nm, zl in zle_drogi[:12]:
        print("  ", nm, {k: v[:3] for k, v in zl.items()})
    bl = sum(suma[k] for k in ("dziura", "sciana", "przejscie", "ogien"))
    if tmp:
        tmp.cleanup()
    return 1 if (bl or brak) else 0


if __name__ == "__main__":
    sys.exit(main())
