"""Bramka F0 generatora spotów (dane_tibia/SPEC_generator_spotow_1021.md): 7 generatorów tras po przełączeniu na
spot_lib.py daje pliki IDENTYCZNE BAJTOWO ze starymi (zamrożone kopie w testy/dane_f0_baza/).

Jak to działa (offline, nic nie dotyka katalogu roboczego ani trasy/ bota):
  kopia A = drzewo repo z 7 generatorami podmienionymi na zamrożone stare (testy/dane_f0_baza/),
  kopia B = drzewo repo tak jak jest (nowe generatory na spot_lib); bez .git, klient/, testy/ i innych katalogów
  niepotrzebnych do generowania.
  W każdej kopii: `python3 -I -B <generator>.py --zapisz` (cwd = kopia), po kolei, z migawką plików (stat + sha256)
  przed i po każdym uruchomieniu -> zbiór i bajty plików, które generator FAKTYCZNIE zapisał (też skasowanych).
  Porównanie A z B osobno dla każdego generatora: kod wyjścia, stdout+stderr, zbiór zapisanych plików, ich bajty.
  Drugi przebieg w obu kopiach wykrywa niedeterminizm (kolejność set/dict przy losowym PYTHONHASHSEED, znaczniki czasu).

Uruchomienie:  python3 -I testy/test_spot_lib_regresja.py
Tryby pomocnicze (dowód, że sam sprzęt działa):
  F0_SAMOKONTROLA=1   kopia B też dostaje zamrożone pliki -> MUSI przejść (sprzęt jest deterministyczny)
  F0_SABOTAZ=1        (razem z samokontrolą) psuje w B dwa generatory -> MUSI dać FAIL na tych dwóch (bugi: bajty PNG,
                      ph: stdout); reszta OK
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
RAJT = Path(__file__).resolve().parent.parent
BAZA = RAJT / "testy" / "dane_f0_baza"
GENERATORY = [
    "generuj_trasy_rook",
    "generuj_trasy_rook_raty2",
    "generuj_trasy_rook_bugi",
    "generuj_trasy_rook_bugi_z10",
    "generuj_trasy_ph",
    "generuj_trasy_edron_wschod",
    "generuj_trasy_thais_pn",
]
LIMIT_S = 600
SAMOKONTROLA = os.environ.get("F0_SAMOKONTROLA") == "1"
SABOTAZ = SAMOKONTROLA and os.environ.get("F0_SABOTAZ") == "1"
# nie kopiujemy: historia git, dane klienta gry (78 MB, generatory ich nie czytają), testy (poza zamrożoną bazą), cache
POMIN_KATALOGI = {".git", "klient", "testy", "__pycache__", "instancje", "logi", "node_modules"}
PRZEBIEGI = 2

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK  " if warunek else "FAIL"), nazwa, info)


def kopiuj_drzewo(cel):
    def ignoruj(katalog, nazwy):
        return [n for n in nazwy if n in POMIN_KATALOGI or n.endswith(".tmp")]
    shutil.copytree(RAJT, cel, ignore=ignoruj, symlinks=True)
    # stałe, dawne mtime: każdy późniejszy zapis zmienia stat, nawet gdyby bajty wyszły te same
    for rodzic, _katalogi, pliki in os.walk(cel):
        for n in pliki:
            p = os.path.join(rodzic, n)
            if not os.path.islink(p):
                os.utime(p, (1_000_000_000, 1_000_000_000))


def stat_drzewa(korzen):
    wynik = {}
    for rodzic, katalogi, pliki in os.walk(korzen):
        katalogi[:] = [d for d in katalogi if d != "__pycache__"]
        for n in pliki:
            p = Path(rodzic) / n
            try:
                s = p.lstat()
            except OSError:
                continue
            wynik[p.relative_to(korzen).as_posix()] = (s.st_mtime_ns, s.st_size, s.st_ino)
    return wynik


def sha(korzen, rel):
    h = hashlib.sha256()
    with open(Path(korzen) / rel, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def uruchom(kopia, generator):
    """Jedno uruchomienie generatora w kopii. Zwraca słownik: rc, wyjscie, pliki {rel: sha256 | None (skasowany)}."""
    przed = stat_drzewa(kopia)
    try:
        p = subprocess.run([sys.executable, "-I", "-B", f"{generator}.py", "--zapisz"], cwd=kopia,
                           capture_output=True, text=True, timeout=LIMIT_S)
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        rc, out, err = -1, "", f"TIMEOUT po {LIMIT_S} s"
    po = stat_drzewa(kopia)
    pliki = {}
    for rel, st in po.items():
        if przed.get(rel) != st:
            pliki[rel] = sha(kopia, rel)
    for rel in przed:
        if rel not in po:
            pliki[rel] = None
    return {"rc": rc, "out": out, "err": err, "pliki": pliki}


def ostatnie(tekst, n=6):
    return " | ".join(tekst.strip().splitlines()[-n:])


def roznice_plikow(a, b, kopia_a, kopia_b):
    """Opis różnic dwóch słowników {rel: sha}; pusty tekst = identyczne."""
    opis = []
    tylko_a = sorted(set(a) - set(b))
    tylko_b = sorted(set(b) - set(a))
    if tylko_a:
        opis.append("tylko stary: " + ", ".join(tylko_a))
    if tylko_b:
        opis.append("tylko nowy: " + ", ".join(tylko_b))
    for rel in sorted(set(a) & set(b)):
        if a[rel] != b[rel]:
            if a[rel] is None or b[rel] is None:
                opis.append(f"{rel}: skasowany tylko w {'starym' if a[rel] is None else 'nowym'}")
                continue
            if kopia_a is None:        # porównanie dwóch przebiegów tego samego pliku: bajtów pierwszego już nie ma
                opis.append(f"{rel}: bajty różne między przebiegami")
                continue
            da = (Path(kopia_a) / rel).read_bytes()
            db = (Path(kopia_b) / rel).read_bytes()
            poz = next((i for i, (x, y) in enumerate(zip(da, db)) if x != y), min(len(da), len(db)))
            opis.append(f"{rel}: bajty różne (stary {len(da)} B, nowy {len(db)} B, pierwsza różnica @ {poz})")
    return "; ".join(opis)


def sabotuj(kopia):
    """Tylko F0_SABOTAZ: celowo psuje dwa nowe generatory (dowód, że bramka potrafi zaświecić na czerwono)."""
    g = Path(kopia) / "generuj_trasy_rook_bugi.py"
    t = g.read_text()
    assert "Rook jaskinia bugów z8" in t
    g.write_text(t.replace("Rook jaskinia bugów z8", "Rook jaskinia bugów z8 (sabotaż)"))   # inny napis w PNG
    g = Path(kopia) / "generuj_trasy_ph.py"
    t = g.read_text()
    assert 'print("zapisano trasy/ph_raty_z8_*' in t
    g.write_text(t.replace('print("zapisano trasy/ph_raty_z8_*', 'print("zapisano (sabotaż) trasy/ph_raty_z8_*'))   # inny stdout


tmp = Path(tempfile.mkdtemp(prefix="f0_regresja_"))
try:
    A, B = tmp / "A_stare", tmp / "B_nowe"
    kopiuj_drzewo(A)
    kopiuj_drzewo(B)
    for g in GENERATORY:
        shutil.copy2(BAZA / f"{g}.py", A / f"{g}.py")          # A: zamrożone stare
        if SAMOKONTROLA:
            shutil.copy2(BAZA / f"{g}.py", B / f"{g}.py")      # B w samokontroli: te same stare
    if SABOTAZ:
        sabotuj(B)
    print(f"tryb: {'SAMOKONTROLA' + (' + SABOTAŻ' if SABOTAZ else '')} (B = zamrożone)" if SAMOKONTROLA
          else "tryb: bramka F0 (B = bieżące generatory w drzewie)")

    wyniki = {"A": [], "B": []}      # lista przebiegów; przebieg = {generator: wynik}
    for nr in range(PRZEBIEGI):
        for nazwa, kopia in (("A", A), ("B", B)):
            przebieg = {}
            for g in GENERATORY:
                przebieg[g] = uruchom(kopia, g)
            wyniki[nazwa].append(przebieg)

    for g in GENERATORY:
        a1, b1 = wyniki["A"][0][g], wyniki["B"][0][g]
        # F0-<gen>-0: generator jest NAPRAWDĘ przełączony (inaczej porównanie starego ze starym przechodzi bez niczego)
        if not SAMOKONTROLA:
            tekst_b = (B / f"{g}.py").read_text()
            sprawdz(f"F0 {g} 0 nowy generator używa spot_lib i różni się od zamrożonego",
                    "spot_lib" in tekst_b and tekst_b != (BAZA / f"{g}.py").read_text(),
                    f"spot_lib w tekście: {'tak' if 'spot_lib' in tekst_b else 'NIE'}; "
                    f"identyczny z zamrożonym: {'tak' if tekst_b == (BAZA / f'{g}.py').read_text() else 'nie'}")
        # F0-<gen>-1: oba uruchomienia kończą się kodem 0 (błąd importu nowego generatora widać tutaj, z treścią)
        sprawdz(f"F0 {g} 1 kod wyjścia 0 w obu", a1["rc"] == 0 and b1["rc"] == 0,
                f"stary={a1['rc']} nowy={b1['rc']}"
                + ("" if b1["rc"] == 0 else f" | stderr nowego: {ostatnie(b1['err'])}")
                + ("" if a1["rc"] == 0 else f" | stderr starego: {ostatnie(a1['err'])}"))
        # F0-<gen>-2: stary zapisał coś do trasy/ i do dane_tibia/mapy/ (porównanie pustych zbiorów nic nie dowodzi)
        zapisane = list(a1["pliki"])
        sprawdz(f"F0 {g} 2 stary generator zapisał pliki w trasy/ i dane_tibia/mapy/",
                any(r.startswith("trasy/") for r in zapisane) and any(r.startswith("dane_tibia/mapy/") for r in zapisane),
                f"{len(zapisane)} plików")
        # F0-<gen>-3: ten sam zbiór plików
        sprawdz(f"F0 {g} 3 ten sam zbiór zapisanych plików", set(a1["pliki"]) == set(b1["pliki"]),
                roznice_plikow({k: "x" for k in a1["pliki"]}, {k: "x" for k in b1["pliki"]}, A, B))
        # F0-<gen>-4: te same bajty
        sprawdz(f"F0 {g} 4 bajty plików identyczne", a1["pliki"] == b1["pliki"],
                roznice_plikow(a1["pliki"], b1["pliki"], A, B))
        # F0-<gen>-5: to samo na stdout i stderr
        sprawdz(f"F0 {g} 5 stdout i stderr identyczne", a1["out"] == b1["out"] and a1["err"] == b1["err"],
                "" if a1["out"] == b1["out"] and a1["err"] == b1["err"]
                else f"stary: {ostatnie(a1['out'] + a1['err'], 3)} || nowy: {ostatnie(b1['out'] + b1['err'], 3)}")
        # F0-<gen>-6: determinizm — drugi przebieg w obu kopiach daje to samo co pierwszy (zapisy i wyjście)
        for nazwa, opis in (("A", "stary"), ("B", "nowy")):
            r1, r2 = wyniki[nazwa][0][g], wyniki[nazwa][1][g]
            # w 2. przebiegu pliki bajtowo te same -> zmienione tylko, jeśli generator je znów zapisał; porównujemy hashe
            sprawdz(f"F0 {g} 6{nazwa} determinizm ({opis}): 2. przebieg = 1.",
                    r1["pliki"] == r2["pliki"] and r1["out"] == r2["out"] and r1["rc"] == r2["rc"],
                    roznice_plikow(r1["pliki"], r2["pliki"], None, None) or ("stdout inny" if r1["out"] != r2["out"] else ""))

    # F0-reszta: poza generatorami i spot_lib.py drzewa A i B są identyczne po wszystkich przebiegach
    # (nowy generator nie zostawił śmieci/.tmp, nie dotknął cudzych plików)
    wyjatki = {f"{g}.py" for g in GENERATORY} | {"spot_lib.py"}
    sa, sb = stat_drzewa(A), stat_drzewa(B)
    ra = {r: sha(A, r) for r in sa if r not in wyjatki}
    rb = {r: sha(B, r) for r in sb if r not in wyjatki}
    sprawdz("F0 reszta drzewa (poza generatorami i spot_lib.py) identyczna w A i B", ra == rb,
            roznice_plikow(ra, rb, A, B))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
