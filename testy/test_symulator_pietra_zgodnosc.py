import os as _os; _os.environ["RETRONIC_TESTY"] = "1"
"""Zgodność symulatora zawieszek (narzedzia/symulator_zawieszek.py: Swiat.wejscia_pola) z regułami pięter bota
(pietra.py: kandydaci, pewni kandydaci z mapy) na PRAWDZIWEJ mapie (map74.otmm), piętra 7-10, okolica miejsc_troll.json.

Co porównujemy dla każdego pola p z próbki (wszystkie pola z flagą 2 na z7..z10 w ramce wokół miejsc_troll.json + 8 sąsiadów):
  symulator: wejscia_pola(p) -> zbiór (kierunek, lądowanie), kierunek: "dol" (rodzaj dziura) / "gora" (rodzaj drabina);
  pietra   : pietra.kandydaci(mapa, a=p, b=<punkt na innym piętrze>) -> pewni kandydaci (pewne=True, z mapy) o polu == p:
             w dół b=(x,y,z+1) (T z flagami 1+2, bez 4, lądowanie (x,y,z+1));
             w górę b=(x,y+1,z-1) (R z flagą 1 bez 4, nad nim (x,y,z-1) flagi 1+2, lądowanie (x,y+1,z-1)).
Zgodne = oba zbiory równe. Rozbieżne są klasyfikowane (raport na końcu); test PADA, gdy pojawi się klasa spoza listy znanych
(OCZEKIWANE) albo gdy któraś z klas "bledy" jest niepusta. Deterministyczny: stała ramka, posortowana próbka, brak losowości.

Uruchomienie (z katalogu pomocnika): RETRONIC_TESTY=1 python3 testy/test_symulator_pietra_zgodnosc.py
"""
import collections, json, sys
from pathlib import Path
sys.dont_write_bytecode = True
P = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(P))
sys.path.insert(0, str(P / "narzedzia"))
import mapa as M
import pietra
import symulator_zawieszek as SYM

ok = bledy = 0
def sprawdz(warunek, opis):
    global ok, bledy
    if warunek: ok += 1
    else: bledy += 1; print("BŁĄD:", opis)

PIETRA_Z = (7, 8, 9, 10)
MARGINES = 40
MIN_PROBKA = 200

# Klasy rozbieżności, które są ZNANĄ, zgłoszoną różnicą reguł (nie błędem symulatora) - patrz raport w docstringu modułu.
# Wszystko spoza tej listy = nowa, niezbadana rozbieżność -> test pada.
OCZEKIWANE = {
    # pietra.kandydaci w dół NIE sprawdza lądowania (T z flagami 1+2 wystarczy); symulator wymaga przechodniego (x,y,z+1)
    # (Swiat._ladowanie_ok). Pole z flagą 2, pod którym jest ściana/pole niewidziane, to dla bota "pewny" kandydat w dół,
    # a dla symulatora brak wyjścia: symulator jest ostrożniejszy. Zgłoszone, bez zmiany symulatora (dowodu z gry brak = UNKNOWN).
    "dol_tylko_pietra_ladowanie_sciana",
    "dol_tylko_pietra_ladowanie_niewidziane",
    # pietra w górę wymaga flag 1+2 NAD polem R (z-1) i flagi 1 na R; symulator wyprowadza "drabinę" z flagi 2 na samym polu.
    # Znana drabina (32497,32267,z8) ma flagę 1 (bez 2, nad nią też 1): żadna z reguł nie wyprowadza jej z mapy, bot bierze ją
    # jako "domysł". Która reguła jest prawdziwa dla pozostałych pól = UNKNOWN (brak naziemnego dowodu), więc nie ruszam symulatora.
    "gora_tylko_pietra_flaga_nad_R",
    "gora_tylko_symulator_flaga_na_polu",
}

m = M.Mapa()
dane = json.loads((P / "trasy/miejsca_troll.json").read_text())
pkt = [tuple(pr[k]) for pr in dane["przejscia"] for k in ("pole", "wejscie_gora", "wyjscie_dol")]
x0, x1 = min(p[0] for p in pkt) - MARGINES, max(p[0] for p in pkt) + MARGINES
y0, y1 = min(p[1] for p in pkt) - MARGINES, max(p[1] for p in pkt) + MARGINES

flaga2 = []                                        # pola z flagą 2 (T w dół)
for z in PIETRA_Z:
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            if m.flagi(x, y, z) & 2:
                flaga2.append((x, y, z))
flaga2.sort()
sprawdz(len(flaga2) >= MIN_PROBKA, f"próbka pól z flagą 2: {len(flaga2)} < {MIN_PROBKA}")

# próbka = pola z flagą 2 + ich sąsiedzi (8) na tym samym piętrze + pola R pod dziurą nad nimi (x, y, z+1, gdy z+1 w 7..10)
probka = set(flaga2)
for (x, y, z) in flaga2:
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            probka.add((x + dx, y + dy, z))
    if z + 1 in PIETRA_Z:
        probka.add((x, y, z + 1))                   # R pod flagą 2 piętro wyżej (kandydat "w górę" w pietra.py)
probka = sorted(probka)


def wg_pietra(p):
    """Pewni kandydaci pietra.kandydaci o polu == p: zbiór (kierunek, lądowanie)."""
    wyn = set()
    x, y, z = p
    for kier, b in (("dol", (x, y, z + 1)), ("gora", (x, y + 1, z - 1))):
        for k in pietra.kandydaci(m, p, b):
            if k["pewne"] and tuple(k["pole"]) == p:
                wyn.add((kier, tuple(k["lad"])))
    return wyn


def wg_symulatora(sw, p):
    wyn = set()
    for e in sw.wejscia_pola(p):
        wyn.add(({"dziura": "dol", "drabina": "gora"}[e["rodzaj"]], tuple(e["do"])))
    return wyn


def klasa(p, a, b):
    """Klasy rozbieżności jako lista etykiet (pusta = zgodne)."""
    wyn = []
    for kier in ("dol", "gora"):
        sa = {l for k, l in a if k == kier}           # symulator
        sb = {l for k, l in b if k == kier}           # pietra
        if sa == sb:
            continue
        if sa and sb:
            wyn.append(f"{kier}_inne_ladowanie")
        elif kier == "dol":
            if sb:
                lad = next(iter(sb))
                pr = m.przechodnie(*lad)               # pietra.kandydaci nie sprawdza lądowania; symulator wymaga przechodniego
                wyn.append("dol_tylko_pietra_ladowanie_" + {True: "przechodnie", False: "sciana", None: "niewidziane"}[pr])
            else:
                wyn.append("dol_tylko_symulator")
        else:
            x, y, z = p
            if sb:
                wyn.append("gora_tylko_pietra_flaga_nad_R")
            else:
                wyn.append("gora_tylko_symulator_flaga_na_polu")
    return wyn


def porownaj():
    sw = SYM.Swiat(mapa=m)
    zgodne, rozbiezne = 0, collections.defaultdict(list)
    z_flaga2 = z_flaga2_zgodne = 0
    for p in probka:
        a, b = wg_symulatora(sw, p), wg_pietra(p)
        kl = klasa(p, a, b)
        if m.flagi(*p) & 2:
            z_flaga2 += 1
        if not kl:
            zgodne += 1
            if m.flagi(*p) & 2:
                z_flaga2_zgodne += 1
        else:
            for k in kl:
                rozbiezne[k].append((p, sorted(a), sorted(b)))
    return zgodne, rozbiezne, z_flaga2, z_flaga2_zgodne


zgodne, rozb, n2, n2z = porownaj()
zgodne2, rozb2, _, _ = porownaj()
sprawdz((zgodne, {k: len(v) for k, v in rozb.items()}) == (zgodne2, {k: len(v) for k, v in rozb2.items()}), "deterministyczność: dwa przebiegi dają ten sam wynik")

pol_rozb = len({p for v in rozb.values() for p, _, _ in v})
print(f"próbka: {len(probka)} pól (w tym {n2} z flagą 2; ramka x {x0}..{x1}, y {y0}..{y1}, z {PIETRA_Z})")
print(f"zgodne: {zgodne}, rozbieżne: {pol_rozb} (z flagą 2: zgodne {n2z} / {n2})")
for k in sorted(rozb):
    print(f"  klasa {k}: {len(rozb[k])} pól, np. {rozb[k][0]}")
for k in rozb:
    sprawdz(k in OCZEKIWANE, f"nieznana klasa rozbieżności: {k} ({len(rozb[k])} pól, np. {rozb[k][0]})")

# --- inwarianty niezależne od klas: zakazane pola i kierunek
sw = SYM.Swiat(mapa=m)
for p in flaga2:
    if wg_symulatora(sw, p):
        sw2 = SYM.Swiat(mapa=m, dziury=[p])
        sprawdz(not sw2.wejscia_pola(p), f"nauczona dziura na {p} nie zdejmuje przejścia (zakazane pole)")
        sw3 = SYM.Swiat(mapa=m, ogien=[p])
        sprawdz(not sw3.wejscia_pola(p), f"ogień na {p} nie zdejmuje przejścia")
        break
for (x, y, z) in flaga2:
    for e in sw.wejscia_pola((x, y, z)):
        sprawdz(e["do"] == ((x, y, z + 1) if e["rodzaj"] == "dziura" else (x, y + 1, z - 1)), f"lądowanie symulatora {e['id']}")
sprawdz(all(not e["pewne"] for p in flaga2 for e in sw.wejscia_pola(p)), "przejścia z mapy mają pewne=False")

# schody z flagą 2 na obu piętrach (32498,32270,z8/z9, sprawdzone na żywo): oba modele dają przejście w dół z lądowaniem (x,y,9)
sprawdz(("dol", (32498, 32270, 9)) in wg_symulatora(sw, (32498, 32270, 8)), "symulator: schody 32498,32270 z8 w dół")
sprawdz(("dol", (32498, 32270, 9)) in wg_pietra((32498, 32270, 8)), "pietra: schody 32498,32270 z8 w dół")

print(f"ok={ok} bledy={bledy}")
sys.exit(1 if bledy else 0)
