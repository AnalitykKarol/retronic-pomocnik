#!/usr/bin/env python3
"""Ab'Dendriel, trolle na czterech piętrach (23.10): cztery mapy tego samego spotu, wybrał Karol:

  abdendriel_trolle_z9    pętla po z9 (składowa 686 pól, ok. 27 trolli, start = lądowanie po linie (32668,31625))
  abdendriel_trolle_z10   pętla po z10 (składowa ok. 1244 pól, ok. 34 trolli, start = lądowanie po dziurze (32713,31585))
  abdendriel_trolle_z11   pętla po z11 (składowa 1509 pól, ok. 26 trolli, start = lądowanie po dziurze z10 (32668,31625,z11))
  abdendriel_trolle_z12   pętla po z12 (składowa 359 pól, ok. 11 trolli, start = lądowanie po dziurze z11 (32668,31624,z12))

Nic nie wysyła do gry:

  python3 -I generuj_trasy_abdendriel_trolle.py [--zapisz]      bez --zapisz tylko liczy, sprawdza i drukuje podsumowanie

DOJŚCIE (z mapy klienta, NIEPRZEJŚTE NA ŻYWO; lista łańcucha w STAN.md pomocnika, 23.10 Ab'Dendriel). Start = ŚWIĄTYNIA (32732,31634,z7),
bo pozycji depo Ab'Dendriel nie ma w danych (SPEC_generator_spotow_1021.md, Q2). Łańcuch przejść (wzorzec „dziura + lina” jak na Edron z8/z9:
pole flagi 2 w kolorze 210 na piętrze z = DZIURA w dół, to samo (x,y) na z+1 = POLE LINY; liną staje się OBOK pola, lądowanie (x, y+1)):
  1. z7 trójka pól (32695..32697,31621) kolor 24 flaga 2 = zasypane dziury (ŁOPATA?) -> z8 (składowa 748 pól);
  2. z8 DZIURA (32706,31587) albo (32709,31593) -> z9 kieszeń (80 pól);
  3. z9 kieszeń: LINA na polu liny (32700,31580,z9) -> lądowanie z8 (32700,31581) w małej składowej (55 pól);
  4. z8 DZIURA (32711,31577) -> z9 (37 pól); 5. z9 DZIURA (32713,31585) -> z10 spot (1244 pól) [start pętli z10];
  6. (tylko mapa z9) z10 LINA na polu liny (32668,31624,z10), stanie obok (NIE na (32668,31625,z10) - tam flaga 2) -> lądowanie z9 (32668,31625).
  7. (mapy z11, z12) z10 DZIURA (32668,31625) -> z11 (32668,31625) [pole liny tej dziury, zejść z niego] = start pętli z11;
  8. (mapa z12) z11 DZIURA (32668,31624) -> z12 (32668,31624) [pole liny] = start pętli z12.
Para dziura + pole liny pod nią powtarza się na z9, z10, z11 (dziura na y=31624 / 31625 na przemian); kierunek W DÓŁ wg wzorca pietra.py
(zejście = pole flagi 2, lądowanie (x,y,z+1); lina w górę = (x,y+1,z-1)). `narzedzia/przejscia_pieter.py` pisze dla (32668,31625,z10) i
(32668,31624,z11) „W GÓRĘ” (heurystyka: coś chodliwego wyżej), ale komponent z12 (359 pól) nie ma żadnego pola flagi 2 i jest osiągalny
tylko spadając z (32668,31624,z11), więc to dziury; NIEPOTWIERDZONE NA ŻYWO.
Potrzebne: LINA (kroki 3 i 6), ŁOPATA (krok 1, jeśli to zasypana dziura; niepotwierdzone).

TRUCIZNA: stałych pól trucizny NIE MA w żadnych danych (OTMM nie zawiera przedmiotów, repo ma tylko zatrucie.py = wnioskowanie z HP). Jedyny ślad:
pola flagi 2 w kolorze podłogi poza z7 (spot_lib.przeszkoda_na_podlodze) = „autowalk nie idzie”, tak wyglądają ogień, trucizna i inne blokady.
Generator zapisuje je do trasy/trucizna_stale.json jako KANDYDATÓW (tożsamość NIEPOTWIERDZONA) i traktuje jak znany ogień: bufor 1 pole, ściana dla A*.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generuj_trasy_edron_wschod as _ogn  # noqa: E402  (ogien_pola z buforem 1)
import mapa as _mapa  # noqa: E402
import spot_lib  # noqa: E402
import trasa_io  # noqa: E402
from spot_lib import chodliwe, petla, przystanki, skladowa  # noqa: E402

NAZWA = "abdendriel_trolle"
TEMPLE = (32732, 31634, 7)                 # świątynia Ab'Dendriel (dane_tibia/spoty_poczatkowe.py:27); depo: UNKNOWN
BUFOR = 1                                  # bufor wokół kandydata trucizny = jak OGIEN_BUFOR
SKAN = (32600, 31560, 32760, 31650)        # prostokąt skanu kandydatów trucizny (x0, y0, x1, y1), piętra 8..10
SKAN_B = (32600, 31580, 32760, 31680)      # z11, z12: obejmuje całe składowe (z11 x 32617..32741, y 31597..31672; z12 x 32640..32705, y 31588..31630)
SKAN_PIETRA = {8: SKAN, 9: SKAN, 10: SKAN, 11: SKAN_B, 12: SKAN_B}
PLIK_TRUCIZNY = ROOT / "trasy" / "trucizna_stale.json"
H7 = [(32695, 31621, 7), (32696, 31621, 7), (32697, 31621, 7)]      # trójka z7 (kolor 24) - zasypane dziury?
HA = [(32706, 31587, 8), (32709, 31593, 8)]                         # dziury z8 -> kieszeń z9 (jednoznaczne w przejscia_pieter)
ROPE_A = (32700, 31580, 9)                                          # pole liny (z9) w kieszeni; lądowanie z8 (x, y+1)
HB = (32711, 31577, 8)                                              # dziura z8 -> z9 (37 pól)
HC = (32713, 31585, 9)                                              # dziura z9 -> z10 spot
ROPE_B = (32668, 31624, 10)                                         # pole liny (z10) pod dziurą z9; lądowanie z9 (32668,31625)
NIE_STAWAJ = {(32668, 31625, 10)}                                   # flaga 2 tuż obok pola liny B
H10 = (32668, 31625, 10)                                            # dziura z10 -> z11 (pole liny tej dziury = lądowanie z11)
H11 = (32668, 31624, 11)                                            # dziura z11 -> z12 (pole liny = lądowanie z12)
START9 = (32668, 31625, 9)
START10 = (32713, 31585, 10)
START11 = (32668, 31625, 11)
START12 = (32668, 31624, 12)
STARTY = {9: START9, 10: START10, 11: START11, 12: START12}
SEED8 = (32696, 31622, 8)                                           # w składowej z8 (748 pól)
CEL = ("troll",)


def dziury_nauczone():
    return {tuple(p) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])}


def kandydaci_trucizny(m):
    """Pola flagi 2 w kolorze podłogi (przeszkoda, nie przejście) na z8..z12 w prostokącie SKAN_PIETRA[z]: [(x, y, z, kolor)]."""
    out = []
    for z in (8, 9, 10, 11, 12):
        x0, y0, x1, y1 = SKAN_PIETRA[z]
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                f = m.flagi(x, y, z)
                if f & _mapa.WIDZIANE and not f & _mapa.SCIANA and f & _mapa.BEZ_DROGI and spot_lib.przeszkoda_na_podlodze(m, x, y, z):
                    out.append((x, y, z, m.pole(x, y, z)[1]))
    return out


def z_buforem(pola):
    return {(x + dx, y + dy, z) for x, y, z in pola for dx in range(-BUFOR, BUFOR + 1) for dy in range(-BUFOR, BUFOR + 1)}


def zapisz_trucizne(kand):
    PLIK_TRUCIZNY.write_text(json.dumps({
        "opis": "KANDYDACI na stale pola trucizny Ab'Dendriel (trolle) - NIEPOTWIERDZONE; format jak ogien_stale.json (pola = [x, y, z])",
        "zrodlo": "mapa klienta mapa/map74.otmm: pole flagi 2 (BEZ_DROGI) w kolorze podlogi poza z7 (spot_lib.przeszkoda_na_podlodze), "
                  f"skan z8..z12, prostokaty {list(SKAN)} (z8..z10) i {list(SKAN_B)} (z11, z12); generuj_trasy_abdendriel_trolle.py 23.10",
        "skan_pietra": {str(z): {"prostokat": list(SKAN_PIETRA[z]), "kandydatow": sum(1 for k in kand if k[2] == z)} for z in sorted(SKAN_PIETRA)},
        "uwaga": "Mapa klienta nie ma przedmiotow, wiec pole trucizny nie jest odroznialne od ognia ani innej blokady autowalku. "
                 "Trasy traktuja te pola jak znany ogien (bufor 1 = sciana dla A*). Bot w locie tego pliku nie czyta (czyta tylko ogien_stale.json), "
                 "ale pola maja flage 2 w mapie, wiec jego A* ich i tak nie uzywa.",
        "pola": [[x, y, z] for x, y, z, _ in kand],
        "kolory": {f"{x},{y},{z}": k for x, y, z, k in kand},
    }, indent=1))


def stoj_obok(m, start, T, zle, zakaz=()):
    """(pole obok T, droga [(x,y,z)...] od start bez startu, z polem obok): najkrótsza po chodliwych sąsiadach T poza `zle` i `zakaz`."""
    z = T[2]
    best = None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            c = (T[0] + dx, T[1] + dy, z)
            if (dx or dy) and chodliwe(m, c) and c not in zle and c not in zakaz:
                if c == tuple(start):
                    d = []
                else:
                    d = m.droga(start, c, zajete=sorted(zle), dlugosc=0, limit=400000)
                    if d is None:
                        continue
                    d = [(q[0], q[1], z) for q in d]
                if best is None or len(d) < len(best[1]):
                    best = (c, d)
    return best


def pole_ok(m, p, zle, comp=None):
    return chodliwe(m, p) and p not in zle and (comp is None or (p[0], p[1]) in comp)


def zbuduj():
    m = _mapa.Mapa()
    dz = dziury_nauczone()
    kand = kandydaci_trucizny(m)
    pola_tr = {(x, y, z) for x, y, z, _ in kand}
    ogien = _ogn.ogien_pola()
    zle = z_buforem(pola_tr) | ogien                                  # (x, y, z): ściana dla A*, pętli i dojścia
    sciana = lambda z: [p for p in dz if p[2] == z] + [p for p in zle if p[2] == z]   # noqa: E731
    print(f"kandydaci trucizny: {len(kand)} pól {dict(Counter(k[2] for k in kand))}; znany ogień z buforem w tym rejonie: "
          f"{sum(1 for p in ogien if p[2] in SKAN_PIETRA and SKAN_PIETRA[p[2]][0] <= p[0] <= SKAN_PIETRA[p[2]][2] and SKAN_PIETRA[p[2]][1] <= p[1] <= SKAN_PIETRA[p[2]][3])} pól")
    # --- pętle ---
    wyniki = {}
    for z, start in STARTY.items():
        if (start in zle) or not chodliwe(m, start):
            raise SystemExit(f"start pętli z{z} {start} na polu zakazanym albo nieprzechodnim")
        comp = skladowa(m, start, sciana(z))
        caly = skladowa(m, start, [p for p in dz if p[2] == z])
        st = przystanki(spot_lib.spawny(z, CEL, (min(c[0] for c in comp) - 5, max(c[0] for c in comp) + 5,
                                                 min(c[1] for c in comp) - 5, max(c[1] for c in comp) + 5)), comp)
        order, nodes, pelna = petla(m, z, start[:2], st, sciana(z))
        w_strefie = [p for p in pelna if (p[0], p[1], z) in zle]
        if w_strefie:
            raise SystemExit(f"z{z}: pętla wchodzi w strefę zakazaną: {w_strefie[:5]}")
        n = sum(t["n"] for t in st)
        print(f"{NAZWA}_z{z}: składowa {len(caly)} pól (bez stref zakazanych {len(comp)}), przystanków {len(st)}, trolli {n}, pętla {len(pelna)} pól, kolejność {order}")
        wyniki[z] = (comp, st, order, nodes, pelna)
    # --- dojście ---
    comp8 = skladowa(m, SEED8, sciana(8))
    pts, meta = [TEMPLE], [{"idx": 0, "typ": "start", "komentarz": "świątynia Ab'Dendriel (depo UNKNOWN, brak w danych); start dojścia wygenerowany z mapy 23.10"}]

    def dodaj(lista):
        for q in lista:
            if q != pts[-1]:
                pts.append(q)

    # 1. z7 -> zasypana dziura (trójka kolor 24), wybór najkrótszej
    najl = None
    for H in H7:
        s = stoj_obok(m, TEMPLE, H, zle)
        if s and (najl is None or len(s[1]) < len(najl[1][1])):
            najl = (H, s)
    H, (c7, d7) = najl
    L8 = (H[0], H[1], 8)
    if not pole_ok(m, L8, zle, comp8):
        raise SystemExit(f"lądowanie {L8} poza składową z8")
    dodaj(d7)
    pts.append(H)
    meta.append({"idx": len(pts) - 1, "typ": "przed_zmiana_pietra",
                 "komentarz": f"z7 {H[:2]} kolor 24 flaga 2 (trójka (32695..32697,31621)): zasypana dziura -> ŁOPATA (niepotwierdzone na żywo; po otwartej dziurze zwykły krok); nad nią z6 ściana"})
    pts.append(L8)
    meta.append({"idx": len(pts) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z8 {L8[:2]} w składowej 748 pól (jaskinia, wejście na ścieżkę do dziur w dół)"})
    # 2. z8 -> dziura -> z9 kieszeń
    najl = None
    for T in HA:
        s = stoj_obok(m, L8, T, zle)
        if s and (najl is None or len(s[1]) < len(najl[1][1])):
            najl = (T, s)
    TA, (cA, dA) = najl
    dodaj(dA)
    pts.append(TA)
    meta.append({"idx": len(pts) - 1, "typ": "przed_zmiana_pietra", "komentarz": f"DZIURA z8 {TA[:2]} (kolor 210, flaga 2, nad nią z7 ściana) -> z9; pod nią pole liny"})
    LA = (TA[0], TA[1], 9)
    pts.append(LA)
    meta.append({"idx": len(pts) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z9 {LA[:2]} w kieszeni (80 pól); to jest pole liny tej dziury, zejść z niego"})
    # 3. z9 kieszeń -> lina (32700,31580) -> z8
    s = stoj_obok(m, LA, ROPE_A, zle)
    cR, dR = s
    dodaj(dR)
    meta.append({"idx": len(pts) - 1, "typ": "przed_zmiana_pietra",
                 "komentarz": f"LINA na polu {ROPE_A[:2]} z9 (pod dziurą z8 tych samych xy): stoimy OBOK na {cR[:2]}, pole liny wolne; lądowanie (x, y+1) pola liny. Potrzebna LINA"})
    L8b = (ROPE_A[0], ROPE_A[1] + 1, 8)
    if not chodliwe(m, L8b):
        raise SystemExit(f"lądowanie liny {L8b} nieprzechodnie")
    pts.append(L8b)
    meta.append({"idx": len(pts) - 1, "typ": "schody_w_gore", "komentarz": f"lądowanie z8 {L8b[:2]} po linie (składowa 55 pól)"})
    # 4. z8 małe -> dziura (32711,31577) -> z9 37
    cB, dB = stoj_obok(m, L8b, HB, zle)
    dodaj(dB)
    pts.append(HB)
    meta.append({"idx": len(pts) - 1, "typ": "przed_zmiana_pietra", "komentarz": f"DZIURA z8 {HB[:2]} -> z9 (kolor 210, nad nią z7 ściana)"})
    LB = (HB[0], HB[1], 9)
    pts.append(LB)
    meta.append({"idx": len(pts) - 1, "typ": "schody_w_dol", "komentarz": f"lądowanie z9 {LB[:2]} (składowa 37 pól)"})
    # 5. z9 37 -> dziura (32713,31585) -> z10 spot
    cC, dC = stoj_obok(m, LB, HC, zle)
    dodaj(dC)
    pts.append(HC)
    meta.append({"idx": len(pts) - 1, "typ": "przed_zmiana_pietra", "komentarz": f"DZIURA z9 {HC[:2]} -> z10 (kolor 210; nad nią z8 ściana)"})
    L10 = (HC[0], HC[1], 10)
    if L10 != START10:
        raise SystemExit(f"lądowanie {L10} != START10 {START10}")
    pts.append(L10)
    meta.append({"idx": len(pts) - 1, "typ": "schody_w_dol",
                 "komentarz": f"lądowanie z10 {L10[:2]} = start pętli abdendriel_trolle_z10 (składowa spotu 1244 pól, ok. 34 trolli)"})
    n10 = len(pts)
    meta10 = [dict(x) for x in meta] + [{"idx": n10 - 1, "typ": "koniec", "komentarz": "start pętli abdendriel_trolle_z10 (pętla zaczyna się w punkcie lądowania)"}]
    pts10 = list(pts)
    # 6. z10 -> lina (32668,31624) -> z9 spot
    cD, dD = stoj_obok(m, L10, ROPE_B, zle | NIE_STAWAJ, NIE_STAWAJ)
    dodaj(dD)
    meta.append({"idx": len(pts) - 1, "typ": "przed_zmiana_pietra",
                 "komentarz": f"LINA na polu {ROPE_B[:2]} z10 (pod dziurą z9 tych samych xy): stoimy OBOK na {cD[:2]}; NIE na (32668,31625,z10) - tam flaga 2. Lądowanie (x, y+1). Potrzebna LINA"})
    L9 = (ROPE_B[0], ROPE_B[1] + 1, 9)
    if L9 != START9 or not pole_ok(m, L9, zle, wyniki[9][0]):
        raise SystemExit(f"lądowanie liny {L9} poza składową pętli z9 albo != START9")
    pts.append(L9)
    meta.append({"idx": len(pts) - 1, "typ": "schody_w_gore", "komentarz": f"lądowanie z9 {L9[:2]} = start pętli abdendriel_trolle_z9 (składowa 686 pól, ok. 27 trolli)"})
    meta.append({"idx": len(pts) - 1, "typ": "koniec", "komentarz": "start pętli abdendriel_trolle_z9"})
    meta.sort(key=lambda x: x["idx"])
    meta10.sort(key=lambda x: x["idx"])
    # 7. z10 -> dziura (32668,31625) -> z11 spot (start pętli z11); idzie dalej z pts10 (nie z pts: ta gałąź to lina w górę na z9)
    pts11, meta11 = list(pts10), [dict(x) for x in meta10 if x["typ"] != "koniec"]
    cE, dE = stoj_obok(m, START10, H10, zle)
    for q in dE:
        if q != pts11[-1]:
            pts11.append(q)
    pts11.append(H10)
    meta11.append({"idx": len(pts11) - 1, "typ": "przed_zmiana_pietra",
                   "komentarz": f"DZIURA z10 {H10[:2]} (kolor 210, flaga 2; pod nią pole liny z11 {H10[:2]}) -> z11; stoimy obok na {cE[:2]}. Kierunek W DÓŁ wg wzorca dziura + pole liny (przejscia_pieter pisze W GÓRĘ), NIEPOTWIERDZONE na żywo"})
    if not pole_ok(m, START11, zle, wyniki[11][0]) or (H10[0], H10[1], 11) != START11:
        raise SystemExit(f"lądowanie {(H10[0], H10[1], 11)} != START11 albo poza składową z11")
    pts11.append(START11)
    meta11.append({"idx": len(pts11) - 1, "typ": "schody_w_dol",
                   "komentarz": f"lądowanie z11 {START11[:2]} = pole liny dziury z10, zejść z niego; start pętli abdendriel_trolle_z11 (składowa 1509 pól, ok. 26 trolli)"})
    n11 = len(pts11)
    meta11.append({"idx": n11 - 1, "typ": "koniec", "komentarz": "start pętli abdendriel_trolle_z11 (pętla zaczyna się w punkcie lądowania)"})
    # 8. z11 -> dziura (32668,31624) -> z12 spot (start pętli z12)
    pts12, meta12 = list(pts11), [dict(x) for x in meta11 if x["typ"] != "koniec"]
    cF, dF = stoj_obok(m, START11, H11, zle)
    for q in dF:
        if q != pts12[-1]:
            pts12.append(q)
    pts12.append(H11)
    meta12.append({"idx": len(pts12) - 1, "typ": "przed_zmiana_pietra",
                   "komentarz": f"DZIURA z11 {H11[:2]} (kolor 210, flaga 2; pod nią pole liny z12 {H11[:2]}) -> z12; stoimy obok na {cF[:2]}. Kierunek W DÓŁ wg wzorca dziura + pole liny (przejscia_pieter pisze W GÓRĘ), NIEPOTWIERDZONE na żywo"})
    if not pole_ok(m, START12, zle, wyniki[12][0]) or (H11[0], H11[1], 12) != START12:
        raise SystemExit(f"lądowanie {(H11[0], H11[1], 12)} != START12 albo poza składową z12")
    pts12.append(START12)
    meta12.append({"idx": len(pts12) - 1, "typ": "schody_w_dol",
                   "komentarz": f"lądowanie z12 {START12[:2]} = pole liny dziury z11, zejść z niego; start pętli abdendriel_trolle_z12 (składowa 359 pól, ok. 11 trolli)"})
    meta12.append({"idx": len(pts12) - 1, "typ": "koniec", "komentarz": "start pętli abdendriel_trolle_z12 (pętla zaczyna się w punkcie lądowania)"})
    for mt in (meta11, meta12):
        mt.sort(key=lambda x: x["idx"])
    for tr_ in (pts, pts10, pts11, pts12):
        kontrole(m, tr_, zle, pola_tr, dz)
    return m, kand, zle, wyniki, {9: (pts, meta), 10: (pts10, meta10), 11: (pts11, meta11), 12: (pts12, meta12)}


DOZW_FLAGA2 = set(H7) | set(HA) | {HB, HC, H10, H11}


def kontrole(m, pts, zle, pola_tr, dz):
    """Twarde warunki: ciągłość, brak ścian, flaga 2 tylko na celowych polach przejść, zero punktów w strefach zakazanych, nauczone dziury nieużyte."""
    zle_t = []
    prz = []
    for a, b in zip(pts, pts[1:]):
        if a[2] != b[2]:
            prz.append((a, b))
            continue
        if max(abs(a[0] - b[0]), abs(a[1] - b[1])) > 1:
            zle_t.append(f"skok {a}->{b}")
    for i, q in enumerate(pts):
        f = m.flagi(*q)
        if not f & _mapa.WIDZIANE or f & _mapa.SCIANA:
            zle_t.append(f"ściana/niewidziane {q}")
        elif f & _mapa.BEZ_DROGI and q not in DOZW_FLAGA2 and q[2] != 7:
            zle_t.append(f"flaga 2 poza celowym przejściem {q}")
        if q in NIE_STAWAJ and not (i + 1 < len(pts) and pts[i + 1][2] == q[2] + 1):     # pole obok liny wolno tylko jako dziura (krok w dół)
            zle_t.append(f"pole zakazane obok liny {q}")
    if zle_t:
        raise SystemExit("trasa niepoprawna: " + "; ".join(zle_t[:6]))
    w_strefie = sorted(q for q in pts if q in zle)
    if w_strefie:
        raise SystemExit(f"punkty trasy w strefie zakazanej (trucizna/ogień + bufor 1): {w_strefie[:6]}")
    wd = sorted(q for q in pts if q in dz)
    if wd:
        raise SystemExit(f"trasa zawiera nauczone dziury: {wd}")
    print(f"kontrole: {len(pts)} pkt, {len(prz)} przejść pięter, zero punktów w strefie zakazanej, zero ścian/skoków")


def odl_min(pts, pola_tr):
    """Najmniejsza odległość (Chebyshev) punktu trasy od kandydata trucizny na tym samym piętrze; (odl, punkt, kandydat)."""
    best = None
    for q in pts:
        for p in pola_tr:
            if p[2] == q[2]:
                d = max(abs(q[0] - p[0]), abs(q[1] - p[1]))
                if best is None or d < best[0]:
                    best = (d, q, p)
    return best


def obrazy(m, kand, zle, wyniki, pts, plik, panele=None, uklad=None):
    """PNG dojścia: z7 / z8 / z9 / z10 z trasą (czerwona), pętlami (niebieska), kandydatami trucizny (fiolet, bufor jaśniejszy), polami przejść (żółte)."""
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415
    S = 11
    F = ImageFont.load_default(size=13)
    tr = {(x, y, z) for x, y, z, _ in kand}

    def panel(z, x0, x1, y0, y1, tytul):
        img = Image.new("RGB", ((x1 - x0 + 1) * S, (y1 - y0 + 1) * S + 22), (0, 0, 0))
        d = ImageDraw.Draw(img)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                p = m.pole(x, y, z)
                if p is None or not p[0] & 1:
                    continue
                rgb = _mapa._kolor_tibii(p[1])
                if p[0] & 4:
                    rgb = tuple(v // 3 for v in rgb)
                elif p[0] & 2:
                    rgb = (255, 220, 0)
                if (x, y, z) in zle:
                    rgb = tuple((a + b) // 2 for a, b in zip(rgb, (170, 60, 230)))
                if (x, y, z) in tr:
                    rgb = (200, 0, 255)
                d.rectangle([(x - x0) * S, (y - y0) * S + 22, (x - x0) * S + S - 1, (y - y0) * S + 22 + S - 1], fill=rgb)

        def c(q):
            return ((q[0] - x0) * S + S // 2, (q[1] - y0) * S + 22 + S // 2)

        if z in wyniki:
            for q in wyniki[z][4]:
                cc = c(q)
                d.rectangle([cc[0] - 2, cc[1] - 2, cc[0] + 2, cc[1] + 2], fill=(80, 140, 255))
        cur = []
        for q in pts + [None]:
            if q is not None and q[2] == z:
                cur.append(c(q))
            else:
                if len(cur) > 1:
                    d.line(cur, fill=(255, 255, 255), width=4)
                    d.line(cur, fill=(235, 30, 30), width=2)
                elif len(cur) == 1:
                    d.ellipse([cur[0][0] - 3, cur[0][1] - 3, cur[0][0] + 3, cur[0][1] + 3], fill=(235, 30, 30))
                cur = []
        d.rectangle([0, 0, img.size[0], 20], fill=(20, 20, 20))
        d.text((4, 3), tytul, fill=(240, 240, 240), font=F)
        return img

    if panele is None:
        panele = [(7, 32688, 32736, 31616, 31636, "z7: swiatynia -> zasypana dziura (32695..97,31621)"),
                  (8, 32686, 32718, 31574, 31626, "z8: dziury (zolte) -> kieszen; trojka z7 laduje u dolu"),
                  (9, 32692, 32718, 31574, 31600, "z9 kieszenie: lina (32700,31580), dziura (32713,31585)"),
                  (10, 32660, 32720, 31578, 31632, "z10 spot: laduje (32713,31585), lina (32668,31624); petla niebieska"),
                  (9, 32630, 32690, 31612, 31646, "z9 spot: laduje po linie (32668,31625); petla niebieska")]
        uklad = [[0, 1], [2, 4], [3]]
    pl = [panel(*a) for a in panele]
    kol = [[pl[i] for i in rz] for rz in uklad]
    szer = max(sum(p.size[0] for p in rz) + 8 * (len(rz) - 1) for rz in kol)
    wys = sum(max(p.size[1] for p in rz) + 6 for rz in kol)
    out = Image.new("RGB", (szer, wys), (30, 30, 30))
    y = 0
    for rz in kol:
        x = 0
        for p in rz:
            out.paste(p, (x, y))
            x += p.size[0] + 8
        y += max(p.size[1] for p in rz) + 6
    out.save(plik)


def potwory_w(comp, z):
    """Zliczenie potworów ze spawnów CipSoft (potwory_pelne.json) o środku w składowej (tolerancja 3 pola)."""
    dane = json.loads(spot_lib.SPAWNY.read_text())["potwory"]
    res = Counter()
    for mo in dane:
        for s in mo.get("spawny", []):
            if s["z"] == z and any(max(abs(s["x"] - c[0]), abs(s["y"] - c[1])) <= 3 for c in comp if abs(c[0] - s["x"]) <= 3):
                res[mo["nazwa"]] += s["ilosc"]
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m, kand, zle, wyniki, dojscia = zbuduj()
    pts = dojscia[9][0]
    pola_tr = {(x, y, z) for x, y, z, _ in kand}
    for z in STARTY:
        print(f"potwory ze spawnów w składowej z{z}: {dict(potwory_w(wyniki[z][0], z))}")
    for z in STARTY:
        for nm, tr_ in ((f"dojscie z{z}", dojscia[z][0]), (f"petla z{z}", [(x, y, z) for x, y in wyniki[z][4]])):
            o = odl_min(tr_, pola_tr)
            print(f"{nm}: {len(tr_)} pkt; najbliżej kandydata trucizny {o[0]} pól (punkt {o[1]}, kandydat {o[2]})" if o else f"{nm}: brak kandydatów na tych piętrach (zero pól trucizny w buforze)")
        print(f"dojście z{z}: {len(dojscia[z][0])} pkt, długość {trasa_io.dlugosc(dojscia[z][0])} pól")
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    zapisz_trucizne(kand)
    for z in STARTY:
        comp, st, order, nodes, pelna = wyniki[z]
        spot_lib.zapis_spotu(m, f"{NAZWA}_z{z}", z, pelna, order, nodes, st, f"Ab'Dendriel trolle z{z}", jedn="trolli", opis_przyst="spawn(y) trolli",
                             ekstra={"bufor_kandydatow_trucizny": BUFOR, "kandydatow_trucizny": len(kand)}, strefa={p for p in zle if p[2] == z})
    for z in STARTY:
        trasa_io.zapisz(f"{NAZWA}_z{z}_dojscie", *dojscia[z])
    obrazy(m, kand, zle, wyniki, pts, spot_lib.OBRAZY / f"{NAZWA}_dojscie.png")
    obrazy(m, kand, zle, wyniki, dojscia[12][0], spot_lib.OBRAZY / f"{NAZWA}_dojscie_z11z12.png",
           [(10, 32600, 32725, 31575, 31640, "z10 spot: dojscie od (32713,31585) do dziury (32668,31625); petla niebieska"),
            (11, 32612, 32746, 31592, 31677, "z11 spot: laduje (32668,31625) po dziurze, dziura (32668,31624); petla niebieska"),
            (12, 32636, 32710, 31584, 31634, "z12 spot: laduje (32668,31624) po dziurze; petla niebieska")],
           [[0, 2], [1]])
    print("zapisano trasy/ (pętle, dojścia z .meta, trucizna_stale.json) i dane_tibia/mapy/ (PNG pętli + abdendriel_trolle_dojscie.png); mapy.json osobno")


if __name__ == "__main__":
    main()
