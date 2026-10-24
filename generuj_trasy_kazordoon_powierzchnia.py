#!/usr/bin/env python3
"""Kazordoon, trolle i węże NA POWIERZCHNI z7 przy wspólnym dojściu Thais -> Kazordoon (trolle_kazordoon_z7), z mapy klienta i spawnów CipSoft 7.4 (24.10).
Metoda jak generuj_trasy_kazordoon_trolle.py (spot_lib: składowa, przystanki, pętla, zapis_spotu; Planista i sprawdz importowane stamtąd); nic nie
wysyła do gry:

  python3 -I generuj_trasy_kazordoon_powierzchnia.py [--zapisz]      bez --zapisz tylko liczy i drukuje podsumowanie

Powstają (przy --zapisz), w trasy/ i dane_tibia/mapy/:
  trolle_kazordoon_z7_petla, trolle_kazordoon_z7_dojscie   pętla na z7 + dojście = PREFIKS wspólnego odcinka z trolle_kazordoon_z8/z9_dojscie
  trolle_kazordoon_z7_do_depo                              powrót pętla -> depo Thais (jawny, NIE odwrócone dojście)
  trolle_kazordoon_z7.png (+ .json)

Po co (Karol 24.10 ~10:55): jaskinię trolli z8 zajął inny gracz (~40 min), a na powierzchni przy tej samej drodze Thais -> Kazordoon widać
trolle, węże i osy (wschodni brzeg z7 przy drzwiach (32659,31966) i dziurze (32663,31962)). Zasada Karola: JEDNA droga + odgałęzienia, bez
dublowania dróg: dojście tego spotu to początek tej samej listy punktów kontrolnych (THAIS_MOST + A* po z7), co dojście z8/z9, urwany w punkcie
ROZGALEZIENIE (32660,31985,z7), gdzie droga skręca na północ ku drzwiom; pętla zaczyna się i kończy w tym punkcie. Test: testy/test_kazordoon_powierzchnia.py.

Wybór spotu: składowa z7 jest jedna ogromna (124 tys. pól), więc spot to lokalne skupisko spawnów CipSoft w prostokącie SPAWNY_OBSZAR:
trolle (32661,31965) x5, (32656,31963) x5, (32668,31967) x2, (32666,31949) x3 i węże (32662,31974) x5, (32645,31972) x4. Osy (32694,31965),
(32688,31989), (32682,31940) po jednej sztuce leżą 26+ pól od pętli: NIE są na pętli, ale potwór "Wasp" jest na liście `potwory` mapy (bije osy,
które przyjdą, a CELE_PIERWSZE "Wasp,Snake" bije je pierwsze).

STREFY ZAKAZANE (ściana dla pętli i dojścia/powrotu):
  * ogień z trasy/ogien_*.json + bufor 1 (jak wszędzie), dziury trasy/dziury_nauczone.json;
  * DZIURA i POLE LINY: dziura z7 (32663,31962) i lądowanie liny (32663,31963) z buforem DZIURA_BUFOR=2 (pola o Chebyshevie <= 2). Korekta Karola:
    "dziura i pole liny NIE mogą być na pętli"; promień 2, a nie 1, bo przystanek wprost przy buforze (troll goniący) wypchnąłby bota w dziurę;
    to MÓJ zapas bezpieczeństwa (24.10, patrz raport), nie dana z gry;
  * spawny GROŹNIEJSZYCH potworów niż troll (hp > 50 albo atak > 10, tak samo jak strefy_zakazane w generuj_trase_thais_kazordoon.py), poza celami
    (troll, snake, wasp): promień STREFA=6 jako ściana + przystanki >= STREFA+2 od ich spawnów; tu: niedźwiedź (32666,31930), pająk jadowity
    (32704,31986), wilki (32640,32011); pętla trzyma 19+ pól odstępu, test to pilnuje;
  * nie wchodzimy na piętro z6 (grobla z dwarfami (32616..32624,31964..31974) i miasto Kazordoon nie leżą na tej pętli).
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import mapa as _mapa  # noqa: E402
import generuj_trase_thais_kazordoon as _thais  # noqa: E402
import generuj_trasy_kazordoon_trolle as _k  # noqa: E402
import spot_lib  # noqa: E402
import trasa_io  # noqa: E402
from generuj_trasy_edron_z9z import ogien_pola  # noqa: E402
from spot_lib import petla, przystanki, skladowa  # noqa: E402

N7 = "trolle_kazordoon_z7"
Z = 7
DEPO = _thais.DEPO_THAIS
ROZGALEZIENIE = (32660, 31985, 7)          # punkt wspólnego odcinka (index 565 w dojściach z8/z9), skręt z wschodu na północ ku drzwiom; start i koniec pętli
PRZED_DRZWIAMI = (32659, 31967, 7)         # pole przed drzwiami (32659,31966,z7): koniec A* wspólnego odcinka przed nimi (jak krok "drzwi" w z8/z9)
DZIURA = _thais.DZIURA_TROLLE              # (32663,31962,z7): dziura w dół (ZASYPANA: łopata); NIE na pętli, NIE na dojściu/powrocie
POLE_LINY_LAD = (32663, 31963, 7)          # lądowanie liny z8 -> z7 (powrót z jaskini trolli); NIE na pętli
DZIURA_BUFOR = 2                           # patrz docstring: promień (Chebyshev) ściany wokół dziury i lądowania liny
STREFA = 6                                 # promień strefy wokół spawnów groźnych potworów (jak Thais północ / Kazordoon z9)
CELE = ("troll", "snake", "wasp")          # potwory mapy; strefy zakazane powstają z KAŻDEGO innego groźniejszego niż troll
CELE_PRZYSTANKI = ("troll", "snake")       # przystanki pętli (osy po jednej sztuce, daleko: bez przystanków)
SPAWNY_OBSZAR = (32630, 32672, 31945, 31976)   # x1, x2, y1, y2: skupisko spawnów wokół drogi Thais -> Kazordoon (przystanki tylko stąd)
OBSZAR_GROZNYCH = (32560, 32760, 31880, 32070)  # prostokąt, w którym szukamy groźnych spawnów (cała okolica wspólnego odcinka)
MOST_E = _thais.MOST_E


def glowne_zajete(m):
    """(dz, ogień, zajęte): dziury nauczone + ogień z buforem 1; jak w generuj_trasy_kazordoon_trolle.zbuduj()."""
    dz = [tuple(p) for p in json.loads((ROOT / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])]
    ogien = ogien_pola()
    return dz, ogien, set(dz) | ogien


def strefa_dziury():
    """Ściana wokół dziury z7 i lądowania liny: x, y w promieniu DZIURA_BUFOR od obu pól (jeden obszar)."""
    out = set()
    for (cx, cy, cz) in (DZIURA, POLE_LINY_LAD):
        for dx in range(-DZIURA_BUFOR, DZIURA_BUFOR + 1):
            for dy in range(-DZIURA_BUFOR, DZIURA_BUFOR + 1):
                out.add((cx + dx, cy + dy, cz))
    return out


def grozne_spawny():
    """Spawny groźniejszych niż troll potworów (hp > hp trolla albo atak > ataku trolla) poza CELE w OBSZAR_GROZNYCH na z7 -> [(nazwa, x, y, ilość, hp, atak)]."""
    dane = json.loads(spot_lib.SPAWNY.read_text())["potwory"]
    troll = next(mo for mo in dane if mo["nazwa"] == "troll")
    x1, x2, y1, y2 = OBSZAR_GROZNYCH
    out = []
    for mo in dane:
        if mo["nazwa"] in CELE or not (mo["hp"] > troll["hp"] or mo["atak"] > troll["atak"]):
            continue
        for s in mo.get("spawny", []):
            if s["z"] == Z and x1 <= s["x"] <= x2 and y1 <= s["y"] <= y2:
                out.append((mo["nazwa"], s["x"], s["y"], s["ilosc"], mo["hp"], mo["atak"]))
    return sorted(out, key=lambda t: (t[2], t[1]))


def strefa_groznych(grozne):
    return spot_lib.strefa_zakazana([{"x": x, "y": y} for _, x, y, *_ in grozne], Z, STREFA)


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def zbuduj():
    m = _mapa.Mapa()
    dz, ogien, zajete = glowne_zajete(m)
    dziura = strefa_dziury()
    grozne = grozne_spawny()
    zgrozne = strefa_groznych(grozne)
    # --- dojście: początek wspólnego odcinka (te same punkty kontrolne i ten sam A*, co WSPOLNA w generuj_trasy_kazordoon_trolle.py), urwany w ROZGALEZIENIE
    strefy_thais = _thais.strefy_zakazane(m, ogien, dz)
    ok_pkt = {k[1] for k in _k.WSPOLNA + _k.DOJSCIE_DO_ROZWIDLENIA + _k.POWROT_Z8 if k[0] in ("start", "do")} | {(32663, 31961, 8), POLE_LINY_LAD, DZIURA}
    zajete_wsp = set(zajete) | {p for p in strefy_thais if p not in ok_pkt}
    kroki_wsp = _thais.THAIS_MOST + (("do", PRZED_DRZWIAMI),)
    pl = _k.Planista(m, zajete_wsp)
    pelne = pl.zbuduj(kroki_wsp)
    przej_wsp = list(pl.przejscia)
    if ROZGALEZIENIE not in pelne:
        raise SystemExit(f"punkt rozgałęzienia {ROZGALEZIENIE} nie leży na wspólnym odcinku (zmieniła się mapa/ogień?)")
    i0 = pelne.index(ROZGALEZIENIE)
    doj = pelne[:i0 + 1]
    przej_doj = [q for q in przej_wsp if q[0] < i0]
    # ściany dla dojścia/powrotu: dziura i pole liny nie mogą być na drodze, więc dojście nie przechodzi też przez bufor dziury ani groźne strefy
    _k.sprawdz(m, doj, przej_doj, ogien)
    for p in doj:
        if p in dziura or p in zgrozne:
            raise SystemExit(f"dojście wchodzi w strefę dziury/groźnych: {p}")
    print(f"dojście: {len(doj)} pkt, {doj[0]} -> {doj[-1]}, przejść pięter {len(przej_doj)}, piętra {sorted({p[2] for p in doj})}")
    # --- pętla
    sciany = [p for p in (set(zajete) | dziura | zgrozne) if p[2] == Z]
    comp = skladowa(m, ROZGALEZIENIE, sciany)
    sp = [s for s in spot_lib.spawny(Z, CELE_PRZYSTANKI, SPAWNY_OBSZAR)]
    st = przystanki(sp, comp)
    jady = [(x, y) for _, x, y, *_ in grozne]
    # przystanki daleko od groźnych spawnów (>= STREFA + 2, jak z9)
    st = [t for t in st if not any(cheb(t["pt"], j) <= STREFA + 2 for j in jady)]
    if not st:
        raise SystemExit("brak przystanków")
    order, nodes, pelna = petla(m, Z, ROZGALEZIENIE[:2], st, sciany)
    print(f"{N7}: składowa {len(comp)} pól, spawnów celów w obszarze {len(sp)}, przystanków {len(st)} ({sum(t['n'] for t in st)} potworów w {sum(t['spawny'] for t in st)} spawnach), "
          f"pętla {len(pelna)} pól, kolejność {order}")
    for k, o in enumerate(order):
        if o:
            print(f"   {k}: {nodes[o]} potworów {st[o - 1]['n']} (spawnów {st[o - 1]['spawny']})")
    # --- powrót: jawnie z ROZGALEZIENIE do depo (ten sam ogon co powroty z8/z9: _thais.THAIS_POWROT_KONIEC)
    kroki_pow = (("start", ROZGALEZIENIE), ("do", MOST_E)) + _thais.THAIS_POWROT_KONIEC
    pr = _k.Planista(m, zajete_wsp)
    pow7 = pr.zbuduj(kroki_pow)
    przej_pow = list(pr.przejscia)
    _k.sprawdz(m, pow7, przej_pow, ogien)
    for p in pow7:
        if p in dziura or p in zgrozne:
            raise SystemExit(f"powrót wchodzi w strefę dziury/groźnych: {p}")
    print(f"powrót: {len(pow7)} pkt, {pow7[0]} -> {pow7[-1]}, przejść pięter {len(przej_pow)}")
    # --- asercje pętli
    pelna3 = [(x, y, Z) for x, y in pelna]
    _k.sprawdz(m, pelna3, [], ogien)
    for p in pelna3:
        if p in dziura or p in zgrozne:
            raise SystemExit(f"pętla w strefie dziury/groźnych: {p}")
    assert pelna3[0] == ROZGALEZIENIE == pelna3[-1]
    assert DZIURA not in pelna3 and POLE_LINY_LAD not in pelna3
    meta_doj = [{"idx": 0, "typ": "start", "komentarz": "depo Thais (z7), wspólny odcinek z dojściami z8/z9 (24.10: prefiks do rozgałęzienia, potem pętla na powierzchni z7)"}] \
        + _k.meta_z_przejsc(przej_doj, doj, _k.KOMENTARZE) \
        + [{"idx": len(doj) - 1, "typ": "koniec", "komentarz": f"rozgałęzienie {ROZGALEZIENIE[:2]} z7: start i koniec pętli (dalej wspólny odcinek skręca na północ ku drzwiom/dziurze, tego spot NIE używa)"}]
    meta_pow = [{"idx": 0, "typ": "start", "komentarz": "rozgałęzienie z7 (start i koniec pętli); wyprawa dochodzi tu pętlą z dowolnego jej punktu"}] \
        + _k.meta_z_przejsc(przej_pow, pow7, _k.KOMENTARZE) \
        + [{"idx": len(pow7) - 1, "typ": "koniec", "komentarz": "depo Thais (z7), pole przybycia wyprawy"}]
    inne = _k.potwory_obok(Z, pelna3, nazwy_poza=CELE)[:6]
    print("najbliższe INNE (nie cele) potwory od pętli (nazwa, x, y, ilość, odl):", inne)
    print("groźne spawny w okolicy (nazwa, x, y, ilość, hp, atak):", grozne)
    return dict(m=m, doj=doj, meta_doj=meta_doj, pelna=pelna, order=order, nodes=nodes, st=st, pow7=pow7, meta_pow=meta_pow,
                strefa=(dziura | zgrozne | {p for p in ogien if p[2] == Z}), comp=comp, sp=sp, grozne=grozne)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zapisz", action="store_true")
    a = ap.parse_args(argv)
    w = zbuduj()
    if not a.zapisz:
        print("(bez --zapisz: nic nie zapisano)")
        return
    ekstra = {"strefa_zakazana": STREFA, "dziura_bufor": DZIURA_BUFOR, "zakazane": [(n, x, y) for n, x, y, *_ in w["grozne"]]}
    spot_lib.zapis_spotu(w["m"], N7, Z, w["pelna"], w["order"], w["nodes"], w["st"], "Kazordoon powierzchnia z7 (trolle, weze)",
                         klucz="potworow", jedn="potw.", opis_przyst="spawn(y) trolli/wezy", doj=w["doj"], meta=w["meta_doj"],
                         strefa=w["strefa"], ekstra=ekstra)
    print("zapisano", trasa_io.zapisz(f"{N7}_do_depo", w["pow7"], w["meta_pow"]))
    print("zapisano trasy/ i dane_tibia/mapy/ (wpisy mapy.json, spoty_nadzorca.json i wyprawa.PLANY_PK dodaj osobno)")


if __name__ == "__main__":
    main()
