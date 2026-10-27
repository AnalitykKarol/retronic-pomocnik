"""Edron, główna jaskinia trolli z8 (mapa `trolle_edron`): pętla i dojście po z8 nie wchodzą na zejścia na z9 ani w ich sąsiedztwo (26.10).

Przypadek: 26.10 08:24:07 Odchyd (trasa `edron_trolle_petla`) w walce z uciekającym trollem wszedł z (33081,31741,z8) w zejście
(33081,31742,z8) i zszedł na z9 (zachodnia jaskinia); punkt 98 pętli (33082,31741) leżał o jedno pole od zejścia.
Wyłącznie odczyt: mapa klienta, trasy/*.json, brak gry i botów. Uruchomienie: RETRONIC_TESTY=1 python3 -I testy/test_edron_z8_bez_zejscia.py
(RETRONIC_Z8_PETLA=<plik.json> podmienia sprawdzaną pętlę, np. na kopię sprzed poprawki: test wtedy ma być CZERWONY).
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ["RETRONIC_TESTY"] = "1"
sys.dont_write_bytecode = True
_R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_R))
import mapa as _mapa  # noqa: E402
import trasa_io  # noqa: E402
import wpadniecie  # noqa: E402
import generuj_petle_edron_z8_bez_zejscia as gen  # noqa: E402

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK  " if warunek else "FAIL"), nazwa, info)


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


M = _mapa.Mapa()
Z = 8
TRASY = _R / "trasy"
ZEJSCIA_ZNANE = {(33071, 31752), (33081, 31742), (33119, 31740)}        # kolor 210 + flaga 2, nic chodliwego nad nimi (przejscia_pieter.py)
MAPY = json.loads((_R / "mapy.json").read_text())
SPOT = MAPY["trolle_edron"]


def pts(nazwa):
    return [tuple(p) for p in json.loads((TRASY / f"{nazwa}.json").read_text())]


PETLA_PLIK = os.environ.get("RETRONIC_Z8_PETLA")
PETLA = [tuple(p) for p in json.loads(Path(PETLA_PLIK).read_text())] if PETLA_PLIK else pts(SPOT["trasa"])
DOJSCIE = pts(SPOT["dojscie"])

# --- 1. zejścia z8: z mapy klienta, nauczone i ręczne dziury
zej = set(gen.zejscia(M))
sprawdz("1a zejścia z8 z mapy+dziur zawierają trzy znane (33071,31752), (33081,31742), (33119,31740)",
        ZEJSCIA_ZNANE <= zej, sorted(zej))
for (x, y) in sorted(ZEJSCIA_ZNANE):
    f = M.flagi(x, y, Z)
    sprawdz(f"1b ({x},{y},z8): mapa flaga 2 (BEZ_DROGI) i kolor 210",
            f & _mapa.BEZ_DROGI and M.pole(x, y, Z)[1] == _mapa.KOLOR_SCHODOW, f"flaga {f}")
nauczone = {tuple(p) for p in json.loads((TRASY / "dziury_nauczone.json").read_text())["dziury"]}
omijaj = {tuple(p) for p in json.loads((TRASY / "dziury_omijaj.json").read_text())["dziury"]}
sprawdz("1c (33081,31742,8) w dziury_nauczone.json (wpadnięcie 15.10)", (33081, 31742, 8) in nauczone)
sprawdz("1d (33071,31752,8) w dziury_omijaj.json (ręczna lista, 26.10 prewencyjnie)", (33071, 31752, 8) in omijaj)
w = wpadniecie.Wpadniecie(None, log=lambda *a: None, plik=TRASY / "dziury_nauczone.json", plik_omijaj=TRASY / "dziury_omijaj.json")
w.wczytaj()
sprawdz("1e wpadniecie.Wpadniecie.dziury (to czyta bot: A*, krok_do, klik marszu, loot) zawiera oba zejścia z8",
        {(33081, 31742, 8), (33071, 31752, 8)} <= w.dziury)
sprawdz("1f nauczone nie są kasowane przez ręczną listę (zapis nauczonych = dziury - omijaj)",
        (33071, 31752, 8) in w.omijaj and (33081, 31742, 8) not in w.omijaj)

# --- 2. punkty pętli i dojścia po z8
bufor = gen.strefa(zej, 1)
sprawdz("2a pętla ma punkty (>= 100) i leży w całości na z8", len(PETLA) >= 100 and all(p[2] == Z for p in PETLA), len(PETLA))
zle_na = [(i, p) for i, p in enumerate(PETLA) if p[2] == Z and (M.flagi(p[0], p[1], Z) & _mapa.BEZ_DROGI)]
sprawdz("2b żaden punkt pętli nie leży na polu flagi 2 (zejście, dziura, przeszkoda)", not zle_na, zle_na)
zle_buf = [(i, p, min(cheb(p, z) for z in zej)) for i, p in enumerate(PETLA) if p[2] == Z and p[:2] in bufor]
sprawdz("2c żaden punkt pętli nie leży w Chebyshevie <= 1 od zejścia z8", not zle_buf, zle_buf)
sprawdz("2d (33082,31741) (dawny punkt 98, o 1 pole od (33081,31742)) nie jest już punktem pętli", (33082, 31741, 8) not in PETLA)
niechodliwe = [(i, p) for i, p in enumerate(PETLA) if not (M.flagi(p[0], p[1], Z) & _mapa.WIDZIANE) or M.flagi(p[0], p[1], Z) & _mapa.SCIANA]
sprawdz("2e każdy punkt pętli jest chodliwy wg mapy (nowy punkt nie wszedł w ścianę)", not niechodliwe, niechodliwe)

doj8 = [(i, p) for i, p in enumerate(DOJSCIE) if p[2] == Z]
sprawdz("2f dojście edron_depo_trolle ma odcinek po z8", len(doj8) > 10, len(doj8))
sprawdz("2g żaden punkt dojścia po z8 nie leży na polu flagi 2 ani w Chebyshevie <= 1 od zejścia",
        not [(i, p) for i, p in doj8 if p[:2] in bufor or M.flagi(p[0], p[1], Z) & _mapa.BEZ_DROGI],
        [(i, p) for i, p in doj8 if p[:2] in bufor][:5])

# --- 3. droga A* bota między kolejnymi punktami (strzałki i skosy) nie wchodzi w bufor
n_zle = []
for i, a in enumerate(PETLA):
    b = PETLA[(i + 1) % len(PETLA)]
    for skosy in (False, True):
        d = M.droga(a, b[:2], [], 0, skosy, limit=20000)
        if d is None:
            n_zle.append((i, a, b, skosy, "brak drogi"))
            continue
        w_buf = [c for c in d if c[:2] in bufor and c[:2] not in (a[:2], b[:2])]
        if w_buf:
            n_zle.append((i, a, b, skosy, w_buf[0]))
sprawdz("3a droga A* (mapa.droga, bez/ze skosami) między kolejnymi punktami pętli, z zawinięciem, nie wchodzi w bufor zejść", not n_zle, n_zle[:3])
n_zle = []
for (i, a), (j, b) in zip(doj8, doj8[1:]):
    if j != i + 1:
        continue
    for skosy in (False, True):
        d = M.droga(a, b[:2], [], 0, skosy, limit=20000)
        if d and [c for c in d if c[:2] in bufor and c[:2] not in (a[:2], b[:2])]:
            n_zle.append((i, a, b, skosy))
sprawdz("3b to samo dla odcinka dojścia po z8", not n_zle, n_zle[:3])

# --- 4. start: dojście kończy się na z8 w pętli, meta pętli (start idx 0) nietknięte
sprawdz("4a pętla zaczyna się w (33117,31775,8) (lądowanie z dojścia), start meta idx 0",
        PETLA[0] == (33117, 31775, 8) and trasa_io.wczytaj(SPOT["trasa"])[1] and trasa_io.wczytaj(SPOT["trasa"])[1][0]["idx"] == 0)
sprawdz("4b mapa trolle_edron: trasa edron_trolle_petla, dojście edron_depo_trolle, bez zmiany nazw",
        SPOT["trasa"] == "edron_trolle_petla" and SPOT["dojscie"] == "edron_depo_trolle")

# --- 5. generator: idempotentny na poprawionej pętli, a na starej (punkt 98 przy zejściu) daje dokładnie poprawioną
nowe, usuniete, wstaw = gen.poprawiona(M, list(PETLA), log=lambda *a: None)
sprawdz("5a generator na poprawionej pętli nic nie zmienia (idempotentny)", nowe == list(PETLA) and not usuniete and not wstaw,
        (len(usuniete), len(wstaw)))
if len(PETLA) > 99 and not PETLA_PLIK:
    stara = list(PETLA)
    stara[98] = (33082, 31741, 8)
    nowe2, us2, ws2 = gen.poprawiona(M, stara, log=lambda *a: None)
    sprawdz("5b na starej pętli (punkt 98 = (33082,31741)) generator usuwa dokładnie ten punkt i daje obecną pętlę",
            us2 == [98] and nowe2 == list(PETLA), (us2, ws2))

# --- 6. planowane zejście dojścia na z9 zachód zostaje (to inna mapa, trolle_edron_z9z): schodzi (33081,31742,8)->(33081,31742,9)
z9z = pts("trolle_edron_z9z_dojscie")
sprawdz("6a trolle_edron_z9z_dojscie nadal schodzi zaplanowanym zejściem (33081,31742,8)->(33081,31742,9)",
        any(a == (33081, 31742, 8) and b == (33081, 31742, 9) for a, b in zip(z9z, z9z[1:])))

# --- 7. tryb.py --sucho: mapa trolle_edron składa się poprawnie
with tempfile.TemporaryDirectory() as tmp:
    nz = Path(tmp) / "nz.json"
    r = subprocess.run([sys.executable, "-I", str(_R / "tryb.py"), "--mapa", "trolle_edron", "--sucho", "--log", str(Path(tmp) / "t.log"),
                        "--na-zywo", str(nz)], capture_output=True, text=True, timeout=120, cwd=str(_R))
    sprawdz("7a tryb.py --mapa trolle_edron --sucho kończy się 0 i podaje MAPA_TRASA=edron_trolle_petla, MAPA_DOJSCIE=edron_depo_trolle",
            r.returncode == 0 and "MAPA_TRASA=edron_trolle_petla" in r.stdout and "MAPA_DOJSCIE=edron_depo_trolle" in r.stdout,
            (r.returncode, r.stderr[-200:]))

print(f"\nWYNIK {sum(ok)} / {len(ok)}")
sys.exit(0 if all(ok) else 1)
