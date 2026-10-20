import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""Dane schodów jaskini trolli (trasy/miejsca_troll.json, trasy/dziury_nauczone.json) kontra mapa i doświadczenie (20.10).

Regresja po błędzie z 20.10: przejście schody_32498_32270 miało lądowania liczone jak dla "dziura + drabina"
((32498,32270,9) = samo pole schodów z9 bez drogi A* i (32498,32271,8) = zwykła podłoga), a (32498,32271,8) siedziało w
nauczonych dziurach (fałszywa dziura zamykała patrolowi kieszeń, a droga patrolu prowadziła przez nią). Dowód lądowań:
telemetria pietra_krok (zejście 154x w (32498,32271,9), wejście 166x w (32498,32269,8)), MAPA_DOSWIADCZENIA.md 4.1.

Sprawdza: (1) lądowania i pola wejścia każdego przejścia są zwykłymi podłogami (widziane, bez flagi 2 i 4) i zgodne z
regułą generatora (generuj_miejsca_troll.ladowania: schody vs dziura + drabina); (2) nauczone dziury w okolicy jaskini to
pola z flagą 2 na mapie i nie są polami przejść; (3) żadna droga patrolu m1-m8 (i ze startu) nie wchodzi na dziurę, ścianę,
pole zmiany piętra ani pole ognia z HP (narzedzia_jednorazowe/sprawdz_sciezki_troll_1020.py).
Opcja --trasy KATALOG: te same kontrole na innej wersji danych (np. po `git show 2395bef:trasy/...` = stan przed poprawką).
"""
import contextlib, io, json, sys
from pathlib import Path
sys.dont_write_bytecode = True
_R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_R))
sys.path.insert(0, str(_R / "narzedzia_jednorazowe"))
import mapa as _mapa
import generuj_miejsca_troll as G
import sprawdz_sciezki_troll_1020 as S

ok = []
def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek); ok.append(warunek); print(("OK  " if warunek else "FAIL"), nazwa, info)

kat = Path(sys.argv[sys.argv.index("--trasy") + 1]) if "--trasy" in sys.argv else _R / "trasy"
M = _mapa.mapa()
dane = json.loads((kat / "miejsca_troll.json").read_text())
dziury = [tuple(p) for p in json.loads((kat / "dziury_nauczone.json").read_text()).get("dziury", [])]

def podloga(p):
    f = M.flagi(*p)
    return bool(f & 1) and not f & 2 and not f & 4

# 1. lądowania i wejścia
zle_pola, zle_regula = [], []
for e in dane["przejscia"]:
    for k in ("wejscie_gora", "wejscie_dol", "wyjscie_dol", "wyjscie_gora"):
        if not podloga(tuple(e[k])):
            zle_pola.append((e["id"], k, e[k], M.flagi(*e[k])))
    T = e["pole"]
    dol, gora = G.ladowania(M, T, T[2])
    if (e["wyjscie_dol"], e["wyjscie_gora"]) != (dol, gora):
        zle_regula.append((e["id"], e["wyjscie_dol"], e["wyjscie_gora"], "powinno być", dol, gora))
sprawdz("1 pola wejścia i lądowania przejść to zwykłe podłogi (bez flagi 2/4)", not zle_pola, zle_pola)
sprawdz("1 lądowania zgodne z regułą (schody vs dziura + drabina)", not zle_regula, zle_regula)
s = next(e for e in dane["przejscia"] if e["id"] == "schody_32498_32270")
sprawdz("1 schody (32498,32270): zejście ląduje w (32498,32271,9), wejście w (32498,32269,8) (telemetria)",
        (s["wyjscie_dol"], s["wyjscie_gora"]) == ([32498, 32271, 9], [32498, 32269, 8]), f"{s['wyjscie_dol']} {s['wyjscie_gora']}")

# 2. nauczone dziury w okolicy jaskini
pola_przejsc = {tuple(e[k]) for e in dane["przejscia"] for k in ("wejscie_gora", "wejscie_dol", "wyjscie_dol", "wyjscie_gora")}
okolica = [d for d in dziury if 32465 <= d[0] <= 32515 and 32250 <= d[1] <= 32305]
bez_flagi = [d for d in okolica if not (M.flagi(*d) & 2)]
sprawdz("2 nauczone dziury w okolicy jaskini mają flagę 2 na mapie (prawdziwa dziura/schody)", not bez_flagi, bez_flagi)
kolizje = [d for d in okolica if d in pola_przejsc]
sprawdz("2 żadna nauczona dziura nie jest polem wejścia/lądowania przejścia", not kolizje, kolizje)
sprawdz("2 fałszywa dziura (32498,32271,8) usunięta", (32498, 32271, 8) not in dziury)

# 3. drogi patrolu
bufor = io.StringIO()
with contextlib.redirect_stdout(bufor):
    kod = S.main(["--trasy", str(kat)])
wyj = bufor.getvalue()
sprawdz("3 drogi patrolu m1-m8 i ze startu: brak dziur, ścian, pól zmiany piętra i ognia z HP; każda para ma drogę",
        kod == 0, wyj.strip().splitlines()[-4:] if kod else "")

print(f"\nOK={sum(ok)} FAIL={len(ok) - sum(ok)}")
sys.exit(0 if all(ok) else 1)
