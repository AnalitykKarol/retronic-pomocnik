#!/usr/bin/env python3
"""Thais północ, jaskinia trolli z9 (thais_pn_z9): DOJŚCIE z depo Thais przez korytarz Poison Spiderów (23.10, Gebelish). Nic nie wysyła do gry:

  python3 -I generuj_trasy_thais_pn_z9.py [--zapisz]        bez --zapisz tylko liczy, sprawdza i drukuje podsumowanie

Pętla thais_pn_z9_petla (109 pól, 16 trolli, z mapy klienta 21.10) zostaje BEZ ZMIAN: generator tylko sprawdza, że generuj_trasy_thais_pn.py
daje dziś dokładnie ten sam plik. Cała składowa z9 (257 pól, zachodnia sala (32314..32340, 32121..32157)) leży POZA zasięgiem Poison Spiderów:
ich spawn (32352,32122) jest we wschodnim korytarzu z9, osobnej składowej za ścianą x=32341..32342. Pętla strefy zakazanej nie dotyka.

DOJŚCIE (nowe) = z depo Thais (32348,32225,z7) do zachodniej sali z9 JEDYNĄ znaną drogą, tą, którą 23.10 12:24 przeszedł Karol postacią Geblish
(nagranie trasy/gebelish_thais_pn_nowy_spot_1023.json; typy i kierunki przejść z NAGRANIA, nie z flag mapy: narzędzie przejscia_pieter.py myli tu
kierunek, patrz CLAUDE.md pomocnika, zgon kutangena 21.10). Odcinki:
  1. z7: dojście thais_pn_z8_dojscie (generuj_trasy_thais_pn.py) do zasypanej dziury (32347,32123,z7) (ŁOPATA, sprawdzone 21.10) i lądowanie (32347,32123,z8);
  2. z8: korytarz y=32123 na wschód do (32356,32123,z8) (nagranie, punkty co 2 pola) i DZIURA (32356,32122,z8) w dół na z9 (pole w dziury_nauczone.json:
     trasa wchodzi w nią CELOWO, więc zawiera parę (32356,32122,z8) -> (32356,32122,z9), jak trolle_edron_z9z_dojscie; cavebot._dziura_w_trasie);
  3. z9 wschód: korytarz Poison Spiderów (3 szt., spawn (32352,32122)) na zachód do (32344,32122,z9), prosty odcinek 12 pól (nagranie omija pole (32355,32122)
     przez (32355,32121)); tu zginął kutangen 21.10, Karol przeszedł nagraniem. DZIURA (32343,32122,z9) w dół na z10 (lądowanie (32343,32122,z10));
  4. z10 (kieszeń pod ścianą): (32343,32123), (32341,32123), (32341,32125), (32340,32125), (32340,32124), (32339,32124) do (32339,32123,z10) obok pola liny (32339,32122,z10)
     (pod dziurą (32339,32122,z9)); LINA w górę: stoi się na (32339,32123,z10), lądowanie (32339,32123,z9) = (x, y+1) pola liny, jak w nagraniu. Potrzebna LINA w plecaku;
  5. z9 zachód: (32339,32123) .. (32337,32122) (nagranie) i A* po składowej do najbliższego punktu pętli (druga sala jest składową pętli).
Postać startująca NA z9 w zachodniej sali (np. (32337,32122,z9)) jest <= 10 pól od pętli: mozg.py (DOJSCIE_POMIN_ODL) pomija dojście i rusza po pętli.

Powstaje (przy --zapisz): trasy/thais_pn_z9_dojscie (+ .meta z typami przejść) oraz dane_tibia/mapy/thais_pn_z9_dojscie.png (z8 / z9 / z10 obok siebie).
Wpisu mapy.json i powrotu (generuj_powrot_thais_pn_z9.py) ten plik nie rusza.
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generuj_trasy_edron_wschod as _ogn  # noqa: E402  (ogien_pola z buforem 1)
import generuj_trasy_thais_pn as G  # noqa: E402
import mapa as _mapa  # noqa: E402
import spot_lib  # noqa: E402
import trasa_io  # noqa: E402

NAZWA = "thais_pn_z9_dojscie"
PETLA = "thais_pn_z9_petla"
NAGRANIE = "gebelish_thais_pn_nowy_spot_1023"    # tylko do porównania, gdy plik jeszcze leży w trasy/ (dane niżej są wpisane na stałe)
LAD8 = (32347, 32123, 8)                         # lądowanie po zasypanej dziurze z7
DZIURA8 = (32356, 32122, 8)                      # dziura w dół na z9 (dziury_nauczone.json)
DZIURA9 = (32343, 32122, 9)                      # dziura w dół na z10 (pole przed nią: (32344,32122,9))
POLE_LINY10 = (32339, 32122, 10)                 # pole liny na z10 (pod dziurą (32339,32122,9)); stoimy na (32339,32123,10)
STOI10 = (32339, 32123, 10)
LAD9 = (32339, 32123, 9)                         # lądowanie po linie = (x, y+1) pola liny
SPAWN_JADU9 = (32352, 32122)                     # środek spawnu 3 Poison Spiderów na z9 (potwory_pelne.json)

# NAGRANIE Karola 23.10 12:24 (Geblish, lvl 10), fragment od x=32347 na z8; pełne trasy/gebelish_thais_pn_nowy_spot_1023.json (41 pkt)
Z8_WSCHOD = [(x, 32123, 8) for x in (32349, 32351, 32353, 32355, 32356)]                  # po LAD8 (32347,32123,8)
Z9_KORYTARZ = [(32356, 32122, 9), (32355, 32122, 9), (32355, 32121, 9), (32353, 32122, 9), (32351, 32122, 9), (32349, 32122, 9),
               (32347, 32122, 9), (32345, 32122, 9), (32344, 32122, 9)]                    # lądowanie (32356,32122,9) .. pole przed dziurą
Z10_KIESZEN = [(32343, 32122, 10), (32343, 32123, 10), (32341, 32123, 10), (32341, 32125, 10), (32340, 32125, 10), (32340, 32124, 10),
               (32339, 32124, 10), (32339, 32123, 10)]                                     # lądowanie (32343,32122,10) .. pole stania przy linie
Z9_ZACHOD = [(32339, 32123, 9), (32338, 32123, 9), (32338, 32122, 9), (32337, 32122, 9)]   # lądowanie po linie .. koniec nagrania


def sprawdz_nagranie(punkty):
    """Dane wpisane na stałe == plik nagrania (gdy leży w trasy/). Zwraca komunikat albo None."""
    try:
        rec, _ = trasa_io.wczytaj(NAGRANIE)
    except (OSError, ValueError):
        return "nagranie nie leży już w trasy/ (porównanie pominięte)"
    zlozone = [LAD8] + Z8_WSCHOD + Z9_KORYTARZ + Z10_KIESZEN + Z9_ZACHOD
    if rec[14:] != zlozone:
        raise SystemExit(f"nagranie {NAGRANIE} (od idx 14) różni się od danych w generatorze:\n{rec[14:]}\n{zlozone}")
    return f"dane zgodne z nagraniem {NAGRANIE} (idx 14..{len(rec) - 1})"


def zbuduj():
    m, w = G.zbuduj()
    dojscie_z8, meta_z8 = w.pop("_dojscie")
    z, comp, st, order, nodes, pelna, zle = w["thais_pn_z9"]
    # --- pętla == zapisana ---
    zap, _ = trasa_io.wczytaj(PETLA)
    if [(q[0], q[1]) for q in zap] != list(pelna) or any(q[2] != 9 for q in zap):
        raise SystemExit(f"{PETLA}: zapisany plik różni się od wyniku generuj_trasy_thais_pn.py (pętla z9 zmieniona?)")
    print(f"pętla {PETLA}: {len(pelna)} pól, taka sama jak zapisana; składowa z9 {len(comp)} pól")
    # --- składowa z9 w ogóle nie zawiera korytarza Poison Spiderów ani pól dziur ---
    wschod = {(q[0], q[1]) for q in Z9_KORYTARZ}
    if wschod & comp:
        raise SystemExit(f"korytarz z9 wschód w składowej pętli: {sorted(wschod & comp)[:3]}")
    jady9 = [(s["x"], s["y"]) for s in spot_lib.spawny(9, ("poison spider",), (32300, 32400, 32090, 32190))]
    print(f"Poison Spidery z9: spawny {jady9}; najbliżej pętli {min(max(abs(q[0] - j[0]), abs(q[1] - j[1])) for q in pelna for j in jady9)} pól")
    print(sprawdz_nagranie(None))
    # --- prefiks z7/z8 z dojścia thais_pn_z8 (do lądowania z8) ---
    i_lad = dojscie_z8.index(LAD8)
    prefiks = list(dojscie_z8[:i_lad + 1])
    meta = [dict(x) for x in meta_z8 if x["idx"] <= i_lad]
    # --- z8 wschód -> dziura -> z9 ---
    pts = prefiks + Z8_WSCHOD
    pts.append(DZIURA8)                      # wchodzimy CELOWO w nauczoną dziurę (cavebot._dziura_w_trasie: para (x,y,z) -> (x,y,z+1))
    pts += Z9_KORYTARZ
    meta.append({"idx": len(prefiks) + len(Z8_WSCHOD), "typ": "przed_zmiana_pietra",
                 "komentarz": f"dziura {DZIURA8[:2]} z8 -> z9 (w dziury_nauczone.json, trasa wchodzi w nią celowo; pole (32356,32123,z8) przed nią NIE jest dziurą, Use tam nic nie robi); "
                              f"nagranie Karola 23.10: krok na północ = upadek. Lądowanie w korytarzu Poison Spiderów (3 szt., spawn {SPAWN_JADU9}): "
                              f"zgon kutangena 21.10 19:11; Karol przeszedł 23.10"})
    meta.append({"idx": len(pts) - len(Z9_KORYTARZ), "typ": "schody_w_dol",
                 "komentarz": "lądowanie z9 (32356,32122) = (x,y) dziury; HP i trucizna pod kontrolą (antidote/exura), nie zatrzymywać się w korytarzu"})
    # --- z9 wschód -> dziura -> z10 ---
    meta.append({"idx": len(pts) - 1, "typ": "przed_zmiana_pietra",
                 "komentarz": f"ostatnie pole z9 przed dziurą {DZIURA9[:2]} (flaga 2 na mapie, nagranie: krok na zachód = upadek na z10)"})
    pts += Z10_KIESZEN
    meta.append({"idx": len(pts) - len(Z10_KIESZEN), "typ": "schody_w_dol",
                 "komentarz": "lądowanie z10 (32343,32122) = (x,y) dziury: kieszeń pod ścianą x=32341..32342, poza Poison Spiderami"})
    # --- z10 -> lina -> z9 zachód ---
    meta.append({"idx": len(pts) - 1, "typ": "przed_zmiana_pietra",
                 "komentarz": f"LINA na polu {POLE_LINY10[:2]} z10 (pod dziurą (32339,32122,z9)): stoimy OBOK na {STOI10[:2]} (pole liny wolne), "
                              f"lądowanie (x, y+1) pola liny; nagranie 23.10 tak przeszło; potrzebna lina w plecaku"})
    pts += Z9_ZACHOD
    meta.append({"idx": len(pts) - len(Z9_ZACHOD), "typ": "schody_w_gore",
                 "komentarz": f"lądowanie z9 {LAD9[:2]} w zachodniej sali (składowa pętli {PETLA})"})
    # --- z9 zachód: od końca nagrania do najbliższego punktu pętli (A* po składowej, strefa pusta) ---
    ogien = _ogn.ogien_pola()
    sciany = sorted(p for p in ogien if p[2] == 9)
    ostatni = pts[-1]
    d = spot_lib.dojscie_do_petli(m, ostatni, pelna, set(sciany))
    if d is None:
        raise SystemExit(f"brak drogi z {ostatni} do pętli")
    cel = d[-1] if d else ostatni[:2]
    pts += [(x, y, 9) for x, y in d if (x, y, 9) != ostatni]
    meta.append({"idx": len(pts) - 1, "typ": "koniec", "komentarz": f"styk z pętlą {PETLA} {cel} (najbliższy punkt pętli; {len(d)} pól A* od końca nagrania)"})
    meta.sort(key=lambda x: x["idx"])
    kontrole(m, pts, meta, comp, pelna)
    return m, w, pts, meta, ogien


def _linia(a, b):
    n = max(abs(a[0] - b[0]), abs(a[1] - b[1]))
    return [(a[0] + round((b[0] - a[0]) * i / n), a[1] + round((b[1] - a[1]) * i / n), a[2]) for i in range(1, n)] if n > 1 else []


def kontrole(m, pts, meta, comp, pelna):
    """Twarde warunki: ciągłość, brak ścian, przejścia tylko znane, ogień z buforem 1, dziury nauczone tylko celowe."""
    ogien = _ogn.ogien_pola()
    dz = {tuple(p) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])}
    przejscia = [(a, b) for a, b in zip(pts, pts[1:]) if a[2] != b[2]]
    oczek = [(DZIURA8, (32356, 32122, 9)), (( 32344, 32122, 9), (32343, 32122, 10)), (STOI10, LAD9), ((32347, 32123, 7), LAD8)]
    if sorted(przejscia) != sorted(oczek):
        # przejście z7 jest w prefiksie: (32347,32123,7)->(32347,32123,8); reszta wg nagrania (a=pole przed przejściem lub dziura)
        raise SystemExit(f"przejścia pięter inne niż oczekiwane: {przejscia}")
    zle = []
    for a, b in zip(pts, pts[1:]):
        if a[2] != b[2]:
            continue
        if max(abs(a[0] - b[0]), abs(a[1] - b[1])) > 3 and a[2] != 7:
            zle.append(f"skok {a}->{b}")
        for q in [a] + _linia(a, b):
            f = m.flagi(q[0], q[1], q[2])
            if not f & _mapa.WIDZIANE or f & _mapa.SCIANA:
                zle.append(f"ściana/niewidziane {q}")
            elif f & _mapa.BEZ_DROGI and q not in (DZIURA8,) and q[2] != 7 and q != (32347, 32123, 8) and q != STOI10:
                zle.append(f"flaga 2 (schody/dziura/przeszkoda) {q}")
    if zle:
        raise SystemExit("trasa niepoprawna: " + "; ".join(zle[:6]))
    og = sorted({q for q in pts if q in ogien})
    if og:
        raise SystemExit(f"punkty trasy na ogniu albo obok (bufor 1): {og[:6]}")
    wchodzi = sorted(q for q in pts if q in dz)
    if wchodzi != [DZIURA8]:
        raise SystemExit(f"trasa zawiera nauczone dziury inne niż celowa {DZIURA8}: {wchodzi}")
    # dojście z8 do lądowania zachowuje to, co sprawdził generuj_trasy_thais_pn (strefa z8 daleko); część z8 wschód jest >= 23 pola od spawnu z8
    print(f"kontrole: {len(pts)} pkt, przejścia {przejscia}; zero punktów na ogniu/obok (bufor 1), celowa dziura {DZIURA8}, zero ścian/skoków")


def podsumowanie(pts):
    z = {}
    for q in pts:
        z[q[2]] = z.get(q[2], 0) + 1
    return ", ".join(f"z{k}: {v} pkt" for k, v in sorted(z.items()))


def obraz_dojscia(m, pts, pelna, plik):
    """PNG: trzy panele (z8, z9, z10) z trasą dojścia (czerwona), pętlą z9 (niebieska), korytarzem Poison Spiderów (fiolet), ogniem (pomarańcz)."""
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415
    S = 12
    ogien = _ogn.ogien_pola()
    F = ImageFont.load_default(size=13)

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
                if (x, y, z) in ogien:
                    rgb = (255, 120, 0)
                d.rectangle([(x - x0) * S, (y - y0) * S + 22, (x - x0) * S + S - 1, (y - y0) * S + 22 + S - 1], fill=rgb)

        def c(q):
            return ((q[0] - x0) * S + S // 2, (q[1] - y0) * S + 22 + S // 2)

        if z == 9:
            for q in pelna:
                d.rectangle([c(q)[0] - 2, c(q)[1] - 2, c(q)[0] + 2, c(q)[1] + 2], fill=(80, 140, 255))
        for s in spot_lib.spawny(z, ("poison spider",), (x0, x1, y0, y1)):
            if True:
                cx, cy = c((s["x"], s["y"]))
                d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], outline=(190, 60, 255), width=3)
        seg = [q for q in pts if q[2] == z and x0 <= q[0] <= x1 and y0 <= q[1] <= y1]
        cur = []
        for q in pts:
            if q[2] == z:
                cur.append(c(q))
            elif len(cur) > 1:
                d.line(cur, fill=(255, 255, 255), width=5)
                d.line(cur, fill=(235, 30, 30), width=3)
                cur = []
            else:
                cur = []
        if len(cur) > 1:
            d.line(cur, fill=(255, 255, 255), width=5)
            d.line(cur, fill=(235, 30, 30), width=3)
        for q in seg:
            d.ellipse([c(q)[0] - 3, c(q)[1] - 3, c(q)[0] + 3, c(q)[1] + 3], fill=(255, 255, 255))
        d.rectangle([0, 0, img.size[0], 20], fill=(20, 20, 20))
        d.text((4, 3), tytul, fill=(240, 240, 240), font=F)
        return img

    p8 = panel(8, 32336, 32362, 32118, 32128, "z8: korytarz + dziura (32356,32122)")
    p9e = panel(9, 32336, 32362, 32118, 32126, "z9: korytarz Poison Spiderow (fiolet), dziury zolte")
    p10 = panel(10, 32334, 32348, 32119, 32128, "z10: kieszen, lina (32339,32122)")
    p9w = panel(9, 32308, 32342, 32118, 32160, "z9 zachod: petla (niebieska) + styk dojscia")
    szer = max(p8.size[0], p9e.size[0], p10.size[0] + p9w.size[0])
    wys = p8.size[1] + p9e.size[1] + max(p10.size[1], p9w.size[1]) + 12
    out = Image.new("RGB", (szer, wys), (30, 30, 30))
    y = 0
    out.paste(p8, (0, y)); y += p8.size[1] + 4
    out.paste(p9e, (0, y)); y += p9e.size[1] + 4
    out.paste(p10, (0, y)); out.paste(p9w, (p10.size[0] + 8, y))
    out.save(plik)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    m, w, pts, meta, _ogien = zbuduj()
    z, comp, st, order, nodes, pelna, zle = w["thais_pn_z9"]
    print(f"{NAZWA}: {len(pts)} pkt ({podsumowanie(pts)}), długość {trasa_io.dlugosc(pts)} pól, start {pts[0]}, koniec {pts[-1]}")
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    print("zapisano", trasa_io.zapisz(NAZWA, pts, meta))
    obraz_dojscia(m, pts, pelna, spot_lib.OBRAZY / f"{NAZWA}.png")
    print("zapisano", spot_lib.OBRAZY / f"{NAZWA}.png", "(pętla thais_pn_z9_petla i jej PNG bez zmian; wpis mapy.json osobno)")


if __name__ == "__main__":
    main()
