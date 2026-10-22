"""22.10: spoty trolle_kazordoon_z8 / z9: jedno wspólne dojście z depo THAIS (korekta Karola 22.10: "na trolle pod", nie przez miasto Kazordoon) (reguła Karola: trasy ze wspólnych odcinków,
bez dublowania dróg). Repo nie składa tras w locie, więc każdy spot ma własne `_dojscie` = wspólny odcinek + własna odnoga;
test pilnuje identycznego prefiksu, ciągłości, ognia, drzwi i kroków liną w powrocie. Dane rzeczywiste; nic nie trafia do gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa
import trasa_io

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test Kazordoonu")
    sys.exit(0)


def wczytaj(nazwa):
    return [tuple(int(v) for v in p) for p in trasa_io.wczytaj(nazwa)[0]]


DEPO = (32348, 32225, 7)          # depo Thais
FORK = (32647, 32003, 8)
LAD9 = (32648, 32004, 9)
D8, D9 = wczytaj("trolle_kazordoon_z8_dojscie"), wczytaj("trolle_kazordoon_z9_dojscie")
P8, P9 = wczytaj("trolle_kazordoon_z8_petla"), wczytaj("trolle_kazordoon_z9_petla")
R8, R9 = wczytaj("trolle_kazordoon_z8_do_depo"), wczytaj("trolle_kazordoon_z9_do_depo")
MAPA = _mapa.Mapa()

# --- wspólny prefiks dojść
sprawdz("dojścia zaczynają w depo Thais", D8[0] == DEPO and D9[0] == DEPO, (D8[0], D9[0]))
sprawdz("dojście z8 kończy na rozwidleniu", D8[-1] == FORK, D8[-1])
i = D8.index(FORK)
sprawdz("wspólny prefiks dojść identyczny (z8 = wspólny odcinek, z9 = ten sam + odnoga)", D9[:len(D8)] == D8, "prefiksy różne")
sprawdz("odnoga z9 = schody z8 + lądowanie z9", D9[len(D8):] == [(32648, 32003, 8), LAD9], D9[len(D8):])
sprawdz("wspólny odcinek >= 300 pól", len(D8) >= 300, len(D8))

# --- pętle zaczynają tam, gdzie kończy dojście
sprawdz("pętla z8 startuje na rozwidleniu", P8[0] == FORK or P8[0][2] == 8 and max(abs(P8[0][0] - FORK[0]), abs(P8[0][1] - FORK[1])) <= 3, P8[0])
sprawdz("pętla z9 startuje przy lądowaniu", P9[0][2] == 9 and max(abs(P9[0][0] - LAD9[0]), abs(P9[0][1] - LAD9[1])) <= 3, P9[0])
sprawdz("pętle zamknięte na jednym piętrze", {p[2] for p in P8} == {8} and {p[2] for p in P9} == {9})


def ciagla(trasa):
    """Kolejne punkty tego samego piętra są w odległości <= 1 (Chebyshev); zmiana piętra o <= 2 pola."""
    for a, b in zip(trasa, trasa[1:]):
        d = max(abs(a[0] - b[0]), abs(a[1] - b[1]))
        if d > (2 if a[2] != b[2] else 1):
            return (a, b)
    return None


for n, t in (("dojście z8", D8), ("dojście z9", D9), ("pętla z8", P8), ("pętla z9", P9), ("powrót z8", R8), ("powrót z9", R9)):
    sprawdz(f"{n}: ciągłość", ciagla(t) is None, ciagla(t))

# --- ogień: żaden punkt nowych tras nie leży na znanym ogniu ani obok
OGIEN = set()
for f in ("ogien_stale.json", "ogien_epizody.json"):
    d = json.loads((Path(_R) / "trasy" / f).read_text())
    for p in (d.get("pola") if isinstance(d, dict) else d) or []:
        if isinstance(p, (list, tuple)) and len(p) >= 3:
            OGIEN.add(tuple(int(v) for v in p[:3]))
for n, t in (("dojście", D9), ("pętla z8", P8), ("pętla z9", P9), ("powrót z8", R8), ("powrót z9", R9)):
    zle = [p for p in t if any((p[0] + dx, p[1] + dy, p[2]) in OGIEN for dx in (-1, 0, 1) for dy in (-1, 0, 1))]
    sprawdz(f"{n}: bez ognia (bufor 1)", not zle, zle[:3])

# --- drzwi: dokładnie 2 w dojściu, rozpoznane przez mechanizm trasy (DRZWI_TRASA)
DRZWI = {(32659, 31966, 7), (32657, 31965, 8)}
for n, t in (("dojście z8", D8), ("dojście z9", D9)):
    got = {x["pole"] for x in trasa_io.drzwi_na_trasie(t, MAPA)}
    sprawdz(f"{n}: drzwi rozpoznane = 2 znane", got == DRZWI, got)
for n, t in (("powrót z8", R8), ("powrót z9", R9)):
    got = {x["pole"] for x in trasa_io.drzwi_na_trasie(t, MAPA)}
    sprawdz(f"{n}: drzwi powrotu to podzbiór znanych", got <= DRZWI and len(got) == 2, got)

# --- 22.10: droga z Thais: bez grobli z6 z dwarfami i bez miasta Kazordoon, głównie po szarej drodze, jedna lina w powrocie
for n, t in (("dojście z8", D8), ("dojście z9", D9), ("powrót z8", R8), ("powrót z9", R9)):
    grobla = [p for p in t if p[2] == 6 and 32610 <= p[0] <= 32625 and 31960 <= p[1] <= 31975]
    sprawdz(f"{n}: nie wchodzi na groblę z6 (dwarfy) i do miasta Kazordoon (z9+ poza jaskinią)", not grobla, grobla[:3])
    pow_ = [p for p in t if p[2] in (6, 7)]
    dr = sum(1 for p in pow_ if MAPA.pole(*p)[1] == 129)
    sprawdz(f"{n}: >= 60% pól powierzchni po szarej drodze", dr * 100 >= 60 * len(pow_), f"{dr}/{len(pow_)}")
MOST = [(32548, 32076, 7), (32549, 32076, 6), (32553, 32076, 6), (32554, 32076, 6), (32555, 32076, 7)]
sprawdz("dojście: przechodzi przez most Thais (pomost z6 32549..32553)", all(p in D8 for p in MOST), [p for p in MOST if p not in D8])
sprawdz("dojście z8: przejścia pięter to 3 (rampa, rampa, dziura z7)", sum(1 for a, b in zip(D8, D8[1:]) if a[2] != b[2]) == 3)

# --- powrót: jedna lina (z8->z7), start/koniec, wspólny sufiks
sprawdz("powrót z8 kończy w depo", R8[-1] == DEPO, R8[-1])
sprawdz("powrót z9 kończy w depo", R9[-1] == DEPO, R9[-1])
sprawdz("powrót z8 startuje na rozwidleniu", R8[0] == FORK, R8[0])
sprawdz("powrót z9 startuje na lądowaniu z9", R9[0] == LAD9, R9[0])
k = R9.index((32648, 32004, 8)) if (32648, 32004, 8) in R9 else -1
sprawdz("powrót z9 wchodzi na z8 schodami", k > 0, k)
sprawdz("wspólny sufiks powrotów (z9 po wyjściu na z8 = powrót z8)", k > 0 and R9[k + 1:][-len(R8) + 1:] == R8[1:] if k > 0 else False, "sufiksy różne")
for lina, stoi, ladowanie in (((32663, 31962, 8), (32663, 31961, 8), (32663, 31963, 7)),):
    j = R8.index(stoi) if stoi in R8 else -1
    sprawdz(f"lina {lina[:2]}: stoi obok pola liny, następny punkt = lądowanie",
            j >= 0 and R8[j + 1] == ladowanie and stoi != lina and lina not in R8, (stoi, R8[j + 1] if j >= 0 else None))

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
