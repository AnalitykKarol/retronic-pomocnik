#!/usr/bin/env python3
"""Thais północ, jaskinia trolli z8 (thais_pn_z8): trasa POWROTU do depo Thais (22.10), odwrócone dojście.

  python3 -I generuj_powrot_thais_pn.py [--zapisz]        bez --zapisz tylko liczy i drukuje podsumowanie

Powód: plan thais_pn jest od 21.10 WYŁĄCZONY (kutangen zginął w dziurze (32356,32122,z8) -> z9, trasa powrotu z flag mapy).
Postać w tej jaskini nie ma dziś żadnej drogi do depo ("pozycja poza planami"). Skoro dojście z depo umie zejść, trzeba umieć
wrócić tą samą drogą. Dojście (thais_pn_z8_dojscie) zeszło przez ZASYPANĄ DZIURĘ (32347,32123,z7) (łopata) na lądowanie
(32347,32123,z8); pole to jest nad nim w górę: lina albo drabina (typ do ustalenia na żywo, bot próbuje R, lina, krok).

Powstaje trasy/thais_pn_z8_do_depo (+ .meta) = trzy kawałki, wszystkie z dojścia, które bot już przeszedł (kutangen 21.10 16:36):
  1. z8: od końca dojścia (32340,32129), czyli styku z pętlą, korytarzem x=32347 do pola STOI (32347,32124,z8), bez pola liny
     i bez korytarza z dziurą (32356,32122) (ten leży na wschód od lądowania, trasa tam nie wchodzi);
  2. przejście z8 -> z7: pole STOI -> lądowanie (32347,32124,z7) (lina/drabina na polu (32347,32123,z8), stoimy obok, pole wolne);
  3. z7: dojście odwrócone od lądowania do depo Thais (32348,32225,z7).
Wpis do wyprawa.PLANY_PK: patrz wyjscie() i plan_pk(). Test: testy/test_powrot_thais_pn.py.
"""
import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import trasa_io  # noqa: E402

NAZWA = "thais_pn_z8_do_depo"
DOJSCIE = "thais_pn_z8_dojscie"
POLE_LINY = (32347, 32123, 8)        # lądowanie dojścia = pole pod zasypaną dziurą (32347,32123,z7)
STOI = (32347, 32124, 8)             # pole stania obok (na południe), wolne; dojście przeszło je 21.10
LAD = (32347, 32124, 7)              # lądowanie po wyjściu w górę: (x, y+1, z7)
DZIURA_Z9 = (32356, 32122, 8)        # NIGDY: dziura w dół na z9, wśród poison spiderów (dziury_nauczone.json)


def wyjscie():
    """Wpis do wyprawa.PLANY_PK["thais_pn"]["wyjscia"]: (pole liny z8, lądowanie z7, plik trasy dalej, (stanie,))."""
    return (POLE_LINY, LAD, NAZWA + ".json", (STOI,))


def plan_pk():
    """Cały wpis planu do wyprawa.PLANY_PK (propozycja; w wyprawa.py go NIE ma, plan jest wyłączony)."""
    return {"nazwa": "thais_pn", "do": NAZWA + ".json", "z": DOJSCIE + ".json", "npc": None, "prefix": False,
            "wyjscia": (wyjscie(),)}


def zbuduj():
    doj, _ = trasa_io.wczytaj(DOJSCIE)
    i_pole = doj.index(POLE_LINY)
    if doj[i_pole - 1] != (32347, 32123, 7) or doj[i_pole - 2] != LAD:
        raise SystemExit(f"{DOJSCIE}: przed lądowaniem oczekiwałem {LAD}, (32347,32123,7); jest {doj[i_pole - 2:i_pole]}")
    z7 = doj[:i_pole - 2 + 1]                      # S7 .. LAD (z7)
    z8 = doj[i_pole + 1:]                          # po polu liny: korytarz do styku z pętlą
    if any(q[2] != 8 for q in z8) or z8[0] != STOI:
        raise SystemExit(f"{DOJSCIE}: odcinek z8 po lądowaniu nie zaczyna się od {STOI} albo nie jest ciągły na z8")
    if POLE_LINY in z8 or DZIURA_Z9 in z8:
        raise SystemExit("odcinek z8 zawiera pole liny albo dziurę na z9")
    punkty = list(reversed(z8)) + list(reversed(z7))      # z8: styk .. STOI, potem LAD .. depo (z7)
    n8 = len(z8)
    meta = [{"idx": 0, "typ": "start", "komentarz": f"styk z pętlą {punkty[0][:2]} (koniec dojścia z8), korytarz x=32347 na północ"},
            {"idx": n8 - 1, "typ": "przed_zmiana_pietra",
             "komentarz": f"stanie {STOI[:2]} obok pola liny/drabiny {POLE_LINY[:2]} z8 (wolne, nie wchodzić na nie); "
                          f"przejście w górę niezweryfikowane botem: tryby R, lina, krok"},
            {"idx": n8, "typ": "schody_w_gore", "komentarz": f"lądowanie z7 {LAD[:2]} = (x, y+1) pola liny; dalej dojście odwrócone"},
            {"idx": len(punkty) - 1, "typ": "koniec", "komentarz": "depo Thais (start depo_troll_cave)"}]
    return punkty, meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    punkty, meta = zbuduj()
    przejscia = [(p, q) for p, q in zip(punkty, punkty[1:]) if p[2] != q[2]]
    print(f"{NAZWA}: {len(punkty)} pkt, start {punkty[0]}, koniec {punkty[-1]}, piętra {sorted({q[2] for q in punkty})}, "
          f"przejścia {przejscia}, meta {len(meta)}")
    if a.zapisz:
        print("zapisano", trasa_io.zapisz(NAZWA, punkty, meta))
    else:
        print("(bez --zapisz: nic nie zapisano)")


if __name__ == "__main__":
    main()
