#!/usr/bin/env python3
"""Thais północ, jaskinia trolli z9 (thais_pn_z9): trasa POWROTU do depo Thais (23.10, Gebelish). Nic nie wysyła do gry:

  python3 -I generuj_powrot_thais_pn_z9.py [--zapisz]        bez --zapisz tylko liczy, sprawdza i drukuje podsumowanie

Powód: wyprawa.PLANY_PK ma plan thais_pn tylko dla z8 (wyjście liną z (32347,32123,z8)); postać na z9 nie ma w nim ani jednego punktu "do" na swoim piętrze,
więc wyprawa po blanki/zapasy (WYPRAWA_DEPO_BLANKI=1, tryb runy) kończyła się "pozycja poza planami". Spot thais_pn_z9 (zachodnia sala) jest zamknięty:
jedyne wyjście to droga dojścia odwrócona (dojście z8 -> dziura -> korytarz Poison Spiderów -> dziura -> z10 -> lina), a W GÓRĘ idzie się LINAMI.

Powstaje trasy/thais_pn_z9_do_depo (+ .meta) = pięć kawałków:
  1. z9 zachód: od styku z pętlą (koniec dojścia) odwrócone dojście do (32339,32123,z9) (pole stania nad dziurą z10);
  2. z9 -> z10: krok na północ w dziurę (32339,32122,z9) (zmiana piętra pewna wg mapy: flaga 2, pole pod nią kolor 210), lądowanie (32339,32122,z10);
  3. z10: kieszeń odwrócona (nagranie 23.10) do pola stania (32343,32123,z10), obok pola liny (32343,32122,z10); pola liny NIE wchodzimy;
  4. LINA z10 -> z9 wschód: pole liny (32343,32122,z10) leży pod dziurą (32343,32122,z9), lądowanie (x, y+1) = (32343,32123,z9); korytarz Poison Spiderów
     y=32123 na wschód do (32356,32123,z9) (jak dojście, tylko równoległy wiersz; 3 Poison Spidery, spawn (32352,32122));
  5. LINA z9 -> z8: pole liny (32356,32122,z9) pod dziurą (32356,32122,z8), lądowanie (32356,32123,z8); korytarz z8 na zachód do (32347,32124,z8)
     (BEZ pola liny (32347,32123,z8) i BEZ dziury (32356,32122,z8)), dalej cały kawałek thais_pn_z8_do_depo od tego pola (przejście z8 -> z7 liną/Use PRZESZŁO
     (przejscia_nauczone 32347,32123,8>7: use) i z7 do depo).
NIEZWERYFIKOWANE NA ŻYWO: dwie liny (32343,32122,z10) i (32356,32122,z9). Dowód pośredni: ten sam układ co lina (32339,32122,z10), którą Karol 23.10 wszedł w górę
(mapa: pod każdą z trzech dziur pole koloru 210 z flagą 1, nagranie Geblish), oraz regułę "lina = lądowanie (x, y+1) pola liny".
Wpis do wyprawa.PLANY_PK: patrz plan_pk(). Test: testy/test_powrot_thais_pn_z9.py.
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generuj_powrot_thais_pn as P8  # noqa: E402  (STOI, POLE_LINY, LAD, DZIURA_Z9 z powrotu z8)
import generuj_trasy_edron_wschod as _ogn  # noqa: E402
import generuj_trasy_thais_pn_z9 as D9  # noqa: E402
import mapa as _mapa  # noqa: E402
import trasa_io  # noqa: E402

NAZWA = "thais_pn_z9_do_depo"
DOJSCIE = "thais_pn_z9_dojscie"
DO8 = "thais_pn_z8_do_depo"
DZIURA_Z10 = (32339, 32122, 9)                  # dziura z9 -> z10 (zachodnia sala), krok na północ z (32339,32123,z9)
LAD_Z10 = (32339, 32122, 10)                    # lądowanie = (x, y) dziury (pole liny z10 dojścia)
STOI_Z10 = (32343, 32123, 10)                   # pole stania przy linie wschodniej
LINA_Z10 = (32343, 32122, 10)                   # pole liny z10 (pod dziurą (32343,32122,z9)), NIE wchodzimy
LAD_E9 = (32343, 32123, 9)                      # lądowanie liny z10 -> z9 wschód = (x, y+1) pola liny
STOI_E9 = (32356, 32123, 9)                     # pole stania przy linie z9 -> z8
LINA_E9 = (32356, 32122, 9)                     # pole liny z9 (pod dziurą (32356,32122,z8)), NIE wchodzimy
LAD_E8 = (32356, 32123, 8)                      # lądowanie liny z9 -> z8
Z9_WSCHOD = [(x, 32123, 9) for x in (32345, 32347, 32349, 32351, 32353, 32355, 32356)]      # po lądowaniu (32343,32123,9); punkty co 2 pola jak nagranie
Z8_ZACHOD = [(32354, 32123, 8), (32352, 32123, 8), (32350, 32123, 8), (32349, 32123, 8), (32348, 32124, 8)]   # po (32356,32123,8) do STOI (32347,32124,8)


def plan_pk():
    """Wpis do wyprawa.PLANY_PK. Bez "wyjscia": plik "do" zawiera całą drogę z przejściami pięter (wzór trolle_kazordoon_z9)."""
    return {"nazwa": "thais_pn_z9", "do": NAZWA + ".json", "z": DOJSCIE + ".json", "npc": None, "prefix": False}


def zbuduj():
    d9, _ = trasa_io.wczytaj(DOJSCIE)
    do8, _ = trasa_io.wczytaj(DO8)
    i_lad = d9.index(D9.LAD9)
    zachod = list(reversed(d9[i_lad:]))                 # styk z pętlą .. (32339,32123,z9)
    if zachod[-1] != D9.LAD9 or any(q[2] != 9 for q in zachod):
        raise SystemExit("odcinek z9 zachód dojścia niespójny")
    i_stoi = do8.index(P8.STOI)
    ogon = list(do8[i_stoi:])                           # STOI z8 .. depo (z8 -> z7 liną/Use, z7)
    kiesz = [LAD_Z10, D9.STOI10] + list(reversed(D9.Z10_KIESZEN[2:-1])) + [STOI_Z10]
    pts = list(zachod)
    meta = [{"idx": 0, "typ": "start", "komentarz": f"styk z pętlą {zachod[0][:2]} (koniec dojścia {DOJSCIE}), zachodnia sala z9"}]
    meta.append({"idx": len(pts) - 1, "typ": "przed_zmiana_pietra",
                 "komentarz": f"dziura {DZIURA_Z10[:2]} z9 -> z10: krok na północ z {D9.LAD9[:2]} (flaga 2, pole pod nią kolor 210; to ta sama dziura, "
                              f"pod którą Karol 23.10 wszedł liną w górę); zmiana w dół = upadek, bez liny"})
    pts += kiesz
    meta.append({"idx": len(pts) - len(kiesz), "typ": "schody_w_dol",
                 "komentarz": f"lądowanie z10 {LAD_Z10[:2]} = (x, y) dziury = pole liny dojścia (nie wchodzimy na nie ponownie); kieszeń pod ścianą x=32341..32342"})
    meta.append({"idx": len(pts) - 1, "typ": "przed_zmiana_pietra",
                 "komentarz": f"LINA na polu {LINA_Z10[:2]} z10 (pod dziurą (32343,32122,z9), tam Karol spadł 23.10): stoimy OBOK na {STOI_Z10[:2]} (pole liny wolne), "
                              f"lądowanie (x, y+1). NIEZWERYFIKOWANE na żywo (ten sam układ co lina (32339,32122,z10) z nagrania); potrzebna lina w plecaku"})
    pts += [LAD_E9] + Z9_WSCHOD
    meta.append({"idx": len(pts) - 1 - len(Z9_WSCHOD), "typ": "schody_w_gore",
                 "komentarz": f"lądowanie z9 {LAD_E9[:2]}: korytarz Poison Spiderów (3 szt., spawn {D9.SPAWN_JADU9}), idź prosto na wschód do {STOI_E9[:2]}"})
    meta.append({"idx": len(pts) - 1, "typ": "przed_zmiana_pietra",
                 "komentarz": f"LINA na polu {LINA_E9[:2]} z9 (pod dziurą (32356,32122,z8)): stoimy OBOK na {STOI_E9[:2]} (pole liny wolne), lądowanie (x, y+1). "
                              f"NIEZWERYFIKOWANE na żywo; tu zginął kutangen 21.10 (wpadł dziurą z z8), z liną w plecaku to wyjście"})
    pts += [LAD_E8] + Z8_ZACHOD
    meta.append({"idx": len(pts) - 1 - len(Z8_ZACHOD), "typ": "schody_w_gore",
                 "komentarz": f"lądowanie z8 {LAD_E8[:2]}; dalej korytarz z8 na zachód BEZ pola liny (32347,32123,z8) i BEZ dziury (32356,32122,z8)"})
    n8 = len(pts)
    if ogon[0] != P8.STOI or max(abs(pts[-1][0] - P8.STOI[0]), abs(pts[-1][1] - P8.STOI[1])) != 1:
        raise SystemExit(f"z8 zachód {pts[-1]} nie przylega do {P8.STOI}")
    pts += ogon
    meta.append({"idx": n8, "typ": "przed_zmiana_pietra",
                 "komentarz": f"stanie {P8.STOI[:2]} obok pola liny/Use {P8.POLE_LINY[:2]} z8 (wolne); przejście w górę PRZESZŁO (przejscia_nauczone 32347,32123,8>7: use)"})
    meta.append({"idx": n8 + 1, "typ": "schody_w_gore", "komentarz": f"lądowanie z7 {P8.LAD[:2]} = (x, y+1) pola liny; dalej dojście z7 odwrócone"})
    meta.append({"idx": len(pts) - 1, "typ": "koniec", "komentarz": "depo Thais (start depo_troll_cave)"})
    kontrole(pts)
    return pts, meta


def _linia(a, b):
    n = max(abs(a[0] - b[0]), abs(a[1] - b[1]))
    return [(a[0] + round((b[0] - a[0]) * i / n), a[1] + round((b[1] - a[1]) * i / n), a[2]) for i in range(1, n)] if n > 1 else []


def kontrole(pts):
    m = _mapa.Mapa()
    ogien = _ogn.ogien_pola()
    dz = {tuple(p) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])}
    przejscia = [(a, b) for a, b in zip(pts, pts[1:]) if a[2] != b[2]]
    oczek = [(D9.LAD9, LAD_Z10), (STOI_Z10, LAD_E9), (STOI_E9, LAD_E8), (P8.STOI, P8.LAD)]
    # (D9.LAD9, LAD_Z10): z (32339,32123,z9) krok na północ w dziurę (32339,32122,z9); parę zapisuje zbuduj_etapy jako DZIURA
    if przejscia != oczek:
        raise SystemExit(f"przejścia pięter inne niż oczekiwane: {przejscia}")
    zle = []
    for a, b in zip(pts, pts[1:]):
        if a[2] != b[2]:
            continue
        if max(abs(a[0] - b[0]), abs(a[1] - b[1])) > 3:
            zle.append(f"skok {a}->{b}")
        for q in [a] + _linia(a, b):
            f = m.flagi(*q)
            if not f & _mapa.WIDZIANE or f & _mapa.SCIANA:
                zle.append(f"ściana/niewidziane {q}")
            elif f & _mapa.BEZ_DROGI and q[2] != 7 and q != P8.STOI:
                zle.append(f"flaga 2 {q}")
    if zle:
        raise SystemExit("trasa niepoprawna: " + "; ".join(zle[:6]))
    # pola liny i dziury nie są na trasie (poza polami stania/lądowania)
    zakaz = {LINA_Z10, LINA_E9, P8.POLE_LINY, DZIURA_Z10, D9.DZIURA9, D9.DZIURA8, P8.DZIURA_Z9}
    if zakaz & set(pts):
        raise SystemExit(f"trasa wchodzi na pole liny/dziurę: {sorted(zakaz & set(pts))}")
    if {q for q in pts if q in ogien}:
        raise SystemExit(f"punkty na ogniu/obok (bufor 1): {sorted(q for q in pts if q in ogien)[:5]}")
    if sorted(q for q in pts if q in dz):
        raise SystemExit(f"trasa zawiera nauczoną dziurę: {sorted(q for q in pts if q in dz)}")
    # pola liny: mapa = kolor 210, flaga 1 (chodliwe, nad nim dziura z flagą 2 piętro wyżej), lądowanie chodliwe
    for lina, dziura in ((LINA_Z10, D9.DZIURA9), (LINA_E9, D9.DZIURA8), (D9.POLE_LINY10, DZIURA_Z10)):
        fl, fd = m.flagi(*lina), m.flagi(*dziura)
        if not (m.pole(*lina)[1] == 210 and fl & 1 and not fl & (2 | 4) and fd & 2 and not fd & 4):
            raise SystemExit(f"pole liny {lina}/dziura {dziura}: mapa nie potwierdza układu (kolor 210 + flaga 2 nad nim)")
    print(f"kontrole powrotu: {len(pts)} pkt, przejścia {przejscia}; zero pól liny/dziur/ognia/ścian na trasie, układy lina+dziura potwierdzone mapą")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    pts, meta = zbuduj()
    z = {}
    for q in pts:
        z[q[2]] = z.get(q[2], 0) + 1
    print(f"{NAZWA}: {len(pts)} pkt ({', '.join(f'z{k}: {v}' for k, v in sorted(z.items()))}), długość {trasa_io.dlugosc(pts)} pól, "
          f"start {pts[0]}, koniec {pts[-1]}, meta {len(meta)}")
    if a.zapisz:
        print("zapisano", trasa_io.zapisz(NAZWA, pts, meta))
    else:
        print("(bez --zapisz: nic nie zapisano)")


if __name__ == "__main__":
    main()
