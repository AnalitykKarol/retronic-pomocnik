#!/usr/bin/env python3
"""Ab'Dendriel, gobliny na z6 SW/S od miasta (mapa abdendriel_gobliny; 25.10, Karol: „gobliny pod ab na z6”). Nic nie wysyła do gry:

  python3 -I generuj_trasy_abdendriel_gobliny.py [--zapisz]     bez --zapisz tylko liczy, sprawdza i drukuje podsumowanie

Powstają (z --zapisz): trasy/abdendriel_gobliny_petla.json, abdendriel_gobliny_dojscie (+ .meta), abdendriel_gobliny_do_depo (+ .meta),
dane_tibia/mapy/abdendriel_gobliny.png/.json i abdendriel_gobliny_dojscie.png. Wpis mapy.json i PLANY_PK: osobno (patrz STAN.md).

SKĄD SPOT: składowa mapy klienta na z6 (map74.otmm) z 7 spawnami goblinów (21 sztuk wg potwory_pelne.json), 100-175 pól na SW/S od depo; druga
kieszeń z6 (228 pól, 7 goblinów) jest odcięta od powierzchni, więc NIE jest kandydatem. Gobliny są też na z7/z8/z9 (jaskinia pod masywem) - Karol
powiedział z6, więc z6; inne piętra to inna decyzja.

DOJŚCIE (jedno źródło geometrii, bez dublowania dróg): z8 nagranie Karola „depo -> trolle” do (32655,31677,z8), A* do pola POD schodami w górę (32654,31675,z8), SCHODY W GÓRĘ
(32654,31674,z8) (krok na północ; nagranie przeszło tędy, lądowanie (32654,31673,z7)), z7 A* po mapie (omija ogień i nauczone dziury) do pola obok schodów
(32622,31790,z7) (z7 flaga 2, kolor 210, ściana od zachodu, wejście od wschodu), SCHODY W GÓRĘ (32622,31790,z7) -> lądowanie z6 (32621,31790) = start pętli.
POWRÓT = ta sama droga odwrócona: z6 pole (32621,31790) -> SCHODY W DÓŁ (32622,31790,z6) -> lądowanie z7 (32623,31790) -> z7 A* -> pole (32654,31673,z7)
-> SCHODY W DÓŁ (32654,31674,z7) -> lądowanie z8 (32654,31675) -> korytarz x=32655 -> odwrócone nagranie do depo.
DEPO = ZASTĘPCZA DECYZJA (be-dev, do przeglądu) jak w generuj_powrot_abdendriel.py: pierwszy punkt nagrania, niepomierzone na żywo.
NIEZWERYFIKOWANE NA ŻYWO: kierunki i lądowania obu przejść (32622,31790) (wnioski z mapy: flaga 2 + kolor 210 na z6 i z7, reguła „lądowanie po stronie
chodliwej”), schody w dół z7 (32654,31674,z7) w drugą stronę, przejezdność z7 (drzewa, woda, wilki, trolle przy (32680,31800)), przejezdność pętli z6.
Test: testy/test_gobliny_abdendriel.py.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generuj_powrot_abdendriel as PW  # noqa: E402  (DEPO_STOI, NAGRANIE, _astar)
import generuj_trasy_abdendriel_trolle as AB  # noqa: E402
import generuj_trasy_edron_wschod as _ogn  # noqa: E402
import mapa as _mapa  # noqa: E402
import spot_lib  # noqa: E402
import trasa_io  # noqa: E402

NAZWA = "abdendriel_gobliny"
NAZWA_DOJSCIA = NAZWA + "_dojscie"
NAZWA_POWROTU = NAZWA + "_do_depo"
Z = 6
STOI8 = (32654, 31675, 8)              # pole stania POD schodami w górę (32654,31674,z8) (na południe od nich; to samo pole to lądowanie po zejściu, pkt 27 nagrania):
                                       # 25.10 wypad.zbuduj_etapy rozpoznaje schody z lądowaniem (x, y-1) tylko, gdy pole liny (b.x, b.y-1) leży > 2 pola od pola stania
NAGRANIE_Z8_DO = (32655, 31677, 8)     # ostatni punkt nagrania z8 przed korytarzem x=32655 (pkt 22); dalej A* do STOI8
SCHODY8 = (32654, 31674, 8)            # schody z8 -> z7 (flaga 2, kolor 210); NIE stoimy na nich poza przejściem
LAD7 = (32654, 31673, 7)               # lądowanie z7 = (x, y-1) schodów; nagranie Karola
SCHODY7_DOL = (32654, 31674, 7)        # schody z7 -> z8 (flaga 2 na z7 i z8), stoimy na LAD7 i idziemy na południe
LAD8 = (32654, 31675, 8)               # lądowanie z8 po zejściu = (x, y+1); nagranie Karola (pkt 27)
STOI7 = (32623, 31790, 7)              # pole stania obok schodów (32622,31790,z7), prosto od wschodu (nie po skosie)
SCHODY7 = (32622, 31790, 7)            # schody z7 -> z6 (flaga 2, kolor 210, ściana od zachodu)
SCHODY6 = (32622, 31790, 6)            # schody z6 -> z7 (flaga 2 na z6 i z7)
START6 = (32621, 31790, 6)             # lądowanie z6 = (x-1, y) schodów (po stronie chodliwej) = start pętli
LAD7_Z6 = (32623, 31790, 7)            # lądowanie z7 po zejściu ze schodów z6 = STOI7
CEL = ("goblin",)
BUFOR = AB.BUFOR


def kandydaci_z6(m, comp_szeroka):
    """Pola flagi 2 w kolorze podłogi na z6 (przeszkoda: ogień/trucizna), jak AB.kandydaci_trucizny, ale w prostokącie składowej + 3."""
    xs = [p[0] for p in comp_szeroka]
    ys = [p[1] for p in comp_szeroka]
    out = []
    for x in range(min(xs) - 3, max(xs) + 4):
        for y in range(min(ys) - 3, max(ys) + 4):
            f = m.flagi(x, y, Z)
            if f & _mapa.WIDZIANE and not f & _mapa.SCIANA and f & _mapa.BEZ_DROGI and spot_lib.przeszkoda_na_podlodze(m, x, y, Z):
                out.append((x, y, Z, m.pole(x, y, Z)[1]))
    return out


def zbuduj():
    m = _mapa.Mapa()
    ogien = _ogn.ogien_pola()
    dz = AB.dziury_nauczone()
    szeroka = spot_lib.skladowa(m, START6)                 # bez stref zakazanych: tylko do prostokąta skanu
    kand = kandydaci_z6(m, szeroka)
    zle = AB.z_buforem({(x, y, z) for x, y, z, _ in kand}) | ogien
    if START6 in zle:
        raise SystemExit(f"start pętli {START6} w strefie zakazanej")
    sciana6 = sorted(p for p in zle if p[2] == Z)
    comp = spot_lib.skladowa(m, START6, sciana6)
    xs = [p[0] for p in comp]
    ys = [p[1] for p in comp]
    obszar = (min(xs) - 3, max(xs) + 3, min(ys) - 3, max(ys) + 3)
    sp = spot_lib.spawny(Z, CEL, obszar)
    st = spot_lib.przystanki(sp, comp)
    if not st:
        raise SystemExit("brak przystanków goblinów w składowej")
    order, nodes, pelna = spot_lib.petla(m, Z, START6[:2], st, sciana6)
    w_strefie = [p for p in pelna if (p[0], p[1], Z) in zle]
    if w_strefie:
        raise SystemExit(f"pętla wchodzi w strefę zakazaną: {w_strefie[:5]}")
    # --- dojście: nagranie z8 do STOI8, schody w górę, z7 A*, schody w górę, lądowanie z6 ---
    nagr, _ = trasa_io.wczytaj(PW.NAGRANIE)
    if tuple(nagr[0]) != PW.DEPO_STOI:
        raise SystemExit(f"nagranie zaczyna się w {nagr[0]}, a DEPO_STOI to {PW.DEPO_STOI}")
    i7 = next(i for i, q in enumerate(nagr) if q[2] == 7)
    nagr8 = nagr[:i7 - 1]                                  # od depo do (32655,31677,z8); punkt (32655,31674) pomijamy (obok schodów, stoimy POD nimi)
    if nagr8[-1] != NAGRANIE_Z8_DO or any(q[2] != 8 for q in nagr8) or nagr[i7] != LAD7:
        raise SystemExit("odcinek z8 nagrania niespójny")
    z8_k = PW._astar(m, NAGRANIE_Z8_DO, STOI8, [p for p in zle if p[2] == 8], dz)
    d7 = PW._astar(m, LAD7, STOI7, [p for p in zle if p[2] == 7], dz)
    pts = list(nagr8) + z8_k
    meta = [{"idx": 0, "typ": "start", "komentarz": f"depo Ab'Dendriel {PW.DEPO_STOI[:2]} z8 (ZASTĘPCZE, NIEPOMIERZONE), początek nagrania „depo -> trolle”; z dowolnego punktu tej drogi dojście bierze najbliższy punkt"},
            {"idx": len(pts) - 1, "typ": "przed_zmiana_pietra",
             "komentarz": f"SCHODY W GÓRĘ {SCHODY8[:2]} z8 (flaga 2, kolor 210) na południe od pola stania {STOI8[:2]} (krok na północ); lądowanie (x, y-1) = {LAD7[:2]} z7. Nagranie Karola 24.10 11:05 przeszło tędy"}]
    pts.append(LAD7)
    meta.append({"idx": len(pts) - 1, "typ": "schody_w_gore", "komentarz": f"lądowanie z7 {LAD7[:2]} tuż nad schodami w dół {SCHODY7_DOL[:2]} z7: NIE schodzić z powrotem"})
    pts += d7
    meta.append({"idx": len(pts) - 1, "typ": "przed_zmiana_pietra",
                 "komentarz": f"SCHODY W GÓRĘ {SCHODY7[:2]} z7 (flaga 2, kolor 210; od zachodu ściana, wejście od wschodu) na zachód od pola stania {STOI7[:2]}; lądowanie z6 po stronie chodliwej = {START6[:2]}. NIEZWERYFIKOWANE na żywo"})
    pts.append(START6)
    meta.append({"idx": len(pts) - 1, "typ": "schody_w_gore", "komentarz": f"lądowanie z6 {START6[:2]} = start pętli abdendriel_gobliny_petla (składowa {len(comp)} pól)"})
    meta.append({"idx": len(pts) - 1, "typ": "koniec", "komentarz": "start pętli abdendriel_gobliny (pętla zaczyna się w punkcie lądowania)"})
    # --- powrót: z6 start, schody w dół, z7 A* (od lądowania do pola nad schodami w dół), schody w dół, z8 korytarz, nagranie odwrócone ---
    r7 = PW._astar(m, LAD7_Z6, LAD7, [p for p in zle if p[2] == 7], dz)
    pw = [START6]
    mp = [{"idx": 0, "typ": "start", "komentarz": f"z6 pole {START6[:2]} obok schodów w dół {SCHODY6[:2]} (lądowanie dojścia; pętla zaczyna się tu, bot dojdzie z dowolnego punktu pętli po z6)"},
          {"idx": 0, "typ": "przed_zmiana_pietra",
           "komentarz": f"SCHODY W DÓŁ {SCHODY6[:2]} z6 (flaga 2, kolor 210) na wschód od pola stania; lądowanie z7 {LAD7_Z6[:2]} (x+1). NIEZWERYFIKOWANE na żywo"}]
    pw.append(LAD7_Z6)
    mp.append({"idx": 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z7 {LAD7_Z6[:2]} obok schodów w górę {SCHODY7[:2]} z7: NIE wchodzić z powrotem"})
    pw += r7
    mp.append({"idx": len(pw) - 1, "typ": "przed_zmiana_pietra",
               "komentarz": f"SCHODY W DÓŁ {SCHODY7_DOL[:2]} z7 (flaga 2 na z7 i z8) na południe od pola stania; lądowanie z8 (x, y+1) = {LAD8[:2]}. Nagranie Karola (pkt 26 -> 27) zeszło tędy"})
    pw.append(LAD8)
    mp.append({"idx": len(pw) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z8 {LAD8[:2]}; obok schody w górę {SCHODY8[:2]}: NIE wchodzić, idź korytarzem x=32655"})
    pw += list(reversed(z8_k[:-1])) + [NAGRANIE_Z8_DO]
    pw += list(reversed(nagr8[:-1]))
    mp.append({"idx": len(pw) - 1, "typ": "koniec", "komentarz": f"{PW.DEPO_STOI[:2]} z8 = początek nagrania „depo -> trolle”; położenie depo NIEPOMIERZONE (zastępcza decyzja)"})
    kontrole(m, pts, zle, dz)
    kontrole(m, pw, zle, dz)
    kontrole(m, [(x, y, Z) for x, y in pelna], zle, dz)
    return m, kand, zle, comp, st, order, nodes, pelna, (pts, meta), (pw, mp)


PRZEJSCIA = {SCHODY7, SCHODY6, SCHODY8, SCHODY7_DOL}


def kontrole(m, pts, zle, dz):
    """Twarde warunki: ciągłość (poza zmianą piętra), brak ścian/niewidzianych, flaga 2 tylko na z7 (schody) lub nigdzie, zero punktów w strefie zakazanej i w nauczonych dziurach."""
    bl = []
    for a, b in zip(pts, pts[1:]):
        if a[2] == b[2] and max(abs(a[0] - b[0]), abs(a[1] - b[1])) > 1 and not (a[2] == 8 and max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 4):
            bl.append(f"skok {a}->{b}")
    for q in pts:
        f = m.flagi(*q)
        if not f & _mapa.WIDZIANE or f & _mapa.SCIANA:
            bl.append(f"ściana/niewidziane {q}")
        elif f & _mapa.BEZ_DROGI:
            bl.append(f"flaga 2 (przejście/dziura) w trasie {q}")
        if q in zle:
            bl.append(f"strefa zakazana {q}")
        if q in dz:
            bl.append(f"nauczona dziura {q}")
    if bl:
        raise SystemExit("trasa niepoprawna: " + "; ".join(bl[:6]))
    print(f"kontrole: {len(pts)} pkt, zero ścian/flagi 2/stref zakazanych/nauczonych dziur, skoki > 1 tylko w nagraniu z8")


def potwory_w(comp):
    dane = json.loads(spot_lib.SPAWNY.read_text())["potwory"]
    res = Counter()
    for mo in dane:
        for s in mo.get("spawny", []):
            if s["z"] == Z and any(max(abs(s["x"] - c[0]), abs(s["y"] - c[1])) <= 3 for c in comp if abs(c[0] - s["x"]) <= 3):
                res[mo["nazwa"]] += s["ilosc"]
    return res


def plan_pk():
    """PROPOZYCJA wpisu do wyprawa.PLANY_PK (wyprawa.py NIE edytowany: pracuje tam inny agent). Bez "drzwi"/"klucze": na tej drodze nie ma drzwi."""
    return {"nazwa": "abdendriel_gobliny_z6", "do": NAZWA_POWROTU + ".json", "z": NAZWA_DOJSCIA + ".json", "npc": None, "prefix": False}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m, kand, zle, comp, st, order, nodes, pelna, (pts, meta), (pw, mp) = zbuduj()
    print(f"{NAZWA}: składowa z6 {len(comp)} pól, przystanków {len(st)}, goblinów {sum(t['n'] for t in st)}, pętla {len(pelna)} pól, kolejność {order}")
    print(f"potwory ze spawnów w składowej z6: {dict(potwory_w(comp))}")
    print(f"kandydatów ognia/trucizny na z6 (przeszkody w kolorze podłogi): {len(kand)}")
    print(f"dojście: {len(pts)} pkt, długość {trasa_io.dlugosc(pts)} pól; powrót: {len(pw)} pkt, długość {trasa_io.dlugosc(pw)} pól")
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    spot_lib.zapis_spotu(m, NAZWA, Z, pelna, order, nodes, st, "Ab'Dendriel gobliny z6", klucz="goblinow", jedn="goblinow", opis_przyst="spawn(y) goblinow",
                         ekstra={"kandydatow_ognia_trucizny_z6": len(kand)}, strefa={p for p in zle if p[2] == Z})
    trasa_io.zapisz(NAZWA_DOJSCIA, pts, meta)
    trasa_io.zapisz(NAZWA_POWROTU, pw, mp)
    wyniki = {Z: (comp, st, order, nodes, pelna)}
    AB.obrazy(m, kand, zle, wyniki, pts, spot_lib.OBRAZY / f"{NAZWA_DOJSCIA}.png",
              [(8, 32650, 32690, 31665, 31695, "z8: depo (zast.) -> schody w gore (32654,31674)"),
               (7, 32615, 32662, 31665, 31800, "z7: dojscie od (32654,31673) do schodow (32622,31790)"),
               (6, 32585, 32640, 31760, 31820, "z6: ladowanie (32621,31790); petla niebieska")],
              [[0, 2], [1]])
    print("zapisano trasy/ (pętla, dojście i powrót z .meta) i dane_tibia/mapy/ (PNG+JSON pętli, PNG dojścia); mapy.json, STAN.md i PLANY_PK osobno")


if __name__ == "__main__":
    main()
