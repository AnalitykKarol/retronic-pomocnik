"""27.10: Ab'Dendriel zachod z8/z9 (generuj_trasy_abdendriel_zachod.py): dojscie Z DEPO i powrot DO DEPO + wpisy abdendriel_zachod_z8/z9 w wyprawa.PLANY_PK.
Nic nie wysyla do gry i niczego nie zmienia na dysku (poza katalogiem tymczasowym). Wzor: test_gobliny_abdendriel.py.
Sprawdza: pliki tras == wynik generatora (punkty i meta), start dojscia = depo, koniec powrotu = depo, dokladnie dwa (z8) / trzy (z9) przejscia pieter w kazdej trasie,
spojnosc dojscie <-> powrot (odcinek depo -> schody bajt w bajt odwrocony, te same przejscia, ten sam ogon z8 w powrocie z9 i z8), pola lin i dziur poza trasami,
zero scian / ognia / stref zakazanych (rotworm 12, poison spider 6) / nauczonych dziur na trasach i petlach, etapy wypad.zbuduj_etapy (LINA bez "schody"/"wlasne", stoi = sasiad
pola liny), sprawdz_plan, brak drzwi, wpisy PLANY_PK (pliki, zasieg, PLAN_PIETRA_WYBOR), wybor planu z punktow petli z8/z9 i pelny start ucieczki PK (Wyprawa._start_wyprawa)
takze z punktow dalszych niz PK_PLAN_ZASIEG od pola liny i dalszych niz DEPO_DOJSCIE_ZASIEG od depo.
NIEPOTWIERDZONE NA ZYWO: polozenie depo (32679,31687,z8), obie liny (pod zasypana dziura z7 (32490,31697) i pod dziura z8 (32480,31721)), schody w dol z7 (32654,31674),
przejezdnosc 225 pol z7, lopata na (32490,31697,z7)."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import json
import sys
import tempfile
import types
from pathlib import Path

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa
import panel
import trasa_io
import wypad
import wyprawa as W
import generuj_trasy_abdendriel_zachod as Z
import generuj_trasy_abdendriel_gobliny as G

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam test zachod abdendriel")
    sys.exit(0)

MAPA = _mapa.Mapa()
DEPO = Z.PW.DEPO_STOI
N = {z: f"{Z.NAZWA}_z{z}" for z in (8, 9)}
PETLA = {z: [tuple(p) for p in trasa_io.wczytaj(N[z] + "_petla")[0]] for z in (8, 9)}
DOJ, META_D, POW, META_P = {}, {}, {}, {}
for z in (8, 9):
    DOJ[z], META_D[z] = trasa_io.wczytaj(N[z] + "_dojscie")
    POW[z], META_P[z] = trasa_io.wczytaj(N[z] + "_do_depo")
    DOJ[z], POW[z] = [tuple(p) for p in DOJ[z]], [tuple(p) for p in POW[z]]
m, pet, dojscia, powroty, prz, zle, dz = Z.zbuduj()
START = {8: (32490, 31697, 8), 9: (32480, 31721, 9)}   # pole liny = start petli (wpisane niezaleznie od generatora)
ZASYP7 = (32490, 31697, 7)                                          # zasypana dziura z7 (32490,31697)
LAD7R = (START[8][0], START[8][1] + 1, 7)                      # ladowanie liny z8 -> z7
STOI8R = (START[8][0], START[8][1] - 1, 8)
STOI9R = (START[9][0], START[9][1] - 1, 9)
LAD8R = (START[9][0], START[9][1] + 1, 8)
DZ8 = (32480, 31721, 8)                                # dziura z8 -> z9 (pole liny z9 = start petli z9)

# 1. pliki == generator
for z in (8, 9):
    L, comp, st, order, nodes, pelna, str_ = pet[z]
    sprawdz(f"1a z{z} petla == generator, jedno pietro, cala w skladowej, start = pole liny", PETLA[z] == [(x, y, z) for x, y in pelna] and PETLA[z][0] == START[z]
            and all((p[0], p[1]) in comp for p in PETLA[z]), (len(PETLA[z]), len(pelna)))
    sprawdz(f"1b z{z} dojscie == generator (punkty i meta)", DOJ[z] == [tuple(p) for p in dojscia[z][0]] and META_D[z] == dojscia[z][1], (len(DOJ[z]), len(dojscia[z][0])))
    sprawdz(f"1c z{z} powrot == generator (punkty i meta)", POW[z] == [tuple(p) for p in powroty[z][0]] and META_P[z] == powroty[z][1], (len(POW[z]), len(powroty[z][0])))
# 27.10 (z9 przeliczona: ogien z epizodami, pelny skan przeszkod, dziury omijaj z buforem): dlugosc/przystanki pętli z9 NIE sa na stale (ogien sie zmienia): limit +10% bazy 1163 z generatora
_j9 = json.loads((Path(_R) / "dane_tibia" / "mapy" / "abdendriel_zachod_z9.json").read_text())
sprawdz("1d liczby punktow: dojscie 254/302, powrot 254/305, petla z8 683 (bez zmian), petla z9 <= limit generatora (110% z 1163 pol), opis .json zgodny z plikiem trasy",
        (len(DOJ[8]), len(DOJ[9]), len(POW[8]), len(POW[9]), len(PETLA[8])) == (254, 302, 254, 305, 683) and len(PETLA[9]) <= int(Z.PETLA9_BAZA[0] * Z.PETLA9_LIMIT) + 1
        and _j9["dlugosc_petli"] == len(PETLA[9]), (len(DOJ[8]), len(DOJ[9]), len(POW[8]), len(POW[9]), len(PETLA[8]), len(PETLA[9]), _j9["dlugosc_petli"]))
sprawdz("1d2 petla z9: przystanki >= 70% i potwory >= 75% bazy (19 przyst./50 potw. przed 27.10; 27.10 wyszlo 14/38: ogien, dziury i przeszkody z buforem 1 odcinaja czesc labiryntu, patrz STAN.md)",
        len(_j9["przystanki"]) - 1 >= 0.70 * Z.PETLA9_BAZA[1] and sum(p.get("potworow", 0) for p in _j9["przystanki"]) >= 0.75 * Z.PETLA9_BAZA[2],
        (len(_j9["przystanki"]) - 1, sum(p.get("potworow", 0) for p in _j9["przystanki"])))
sprawdz("1e petle zamykaja sie (ostatni punkt sasiaduje ze startem)", all(max(abs(PETLA[z][-1][0] - PETLA[z][0][0]), abs(PETLA[z][-1][1] - PETLA[z][0][1])) <= 1 for z in (8, 9)), "")

# 2. start / koniec / przejscia pieter
for z in (8, 9):
    sprawdz(f"2a z{z} dojscie zaczyna sie w depo, konczy startem petli; powrot konczy sie w depo", DOJ[z][0] == DEPO == POW[z][-1] and DOJ[z][-1] == START[z] == PETLA[z][0], (DOJ[z][0], DOJ[z][-1], POW[z][-1]))
    nz = lambda t: [(a, b) for a, b in zip(t, t[1:]) if a[2] != b[2]]      # noqa: E731
    sprawdz(f"2b z{z} dojscie: przejscia pieter: schody w gore z8->z7 (nagranie), zasypana dziura z7->z8" + (", dziura z8->z9" if z == 9 else ""),
            nz(DOJ[z]) == [(G.STOI8, G.LAD7), (ZASYP7, START[8])] + ([(DZ8, START[9])] if z == 9 else []), nz(DOJ[z]))
    sprawdz(f"2c z{z} powrot: przejscia pieter: " + ("lina z9->z8, " if z == 9 else "") + "lina z8->z7, schody w dol z7->z8",
            nz(POW[z]) == ([(STOI9R, LAD8R)] if z == 9 else []) + [(STOI8R, LAD7R), (G.LAD7, G.LAD8)], nz(POW[z]))
sprawdz("2d powrot z9: ogon od pola stania liny z8 == powrot z8 (jedna geometria)", POW[9][POW[9].index(STOI8R):] == POW[8], "")
i_l = DOJ[8].index(G.LAD7)
sprawdz("2e odcinek depo -> schody dojscia (do pola pod schodami) == odwrocony koniec powrotu (bajt w bajt), ten sam co w dojsciu gobliny",
        list(reversed(DOJ[8][:i_l])) == POW[8][POW[8].index(G.LAD8):] and DOJ[8][:i_l] == [tuple(p) for p in trasa_io.wczytaj("abdendriel_gobliny_dojscie")[0]][:i_l], i_l)
z7d, z7p = [p for p in DOJ[8] if p[2] == 7], [p for p in POW[8] if p[2] == 7]
sprawdz("2f odcinki z7: dojscie od ladowania schodow do zasypanej dziury, powrot od ladowania liny do pola nad schodami w dol; dlugosci zblizone (+-6)",
        z7d[0] == G.LAD7 and z7d[-1] == ZASYP7 and z7p[0] == LAD7R and z7p[-1] == G.LAD7 and abs(len(z7d) - len(z7p)) <= 6, (len(z7d), len(z7p)))
sprawdz("2g sasiedztwo lin: pole stania powrotu jest sasiadem PROSTOPADLYM pola liny (nie nim, nie polem pod ladowaniem); ladowanie = (x, y+1) pola liny; pole liny = start petli",
        all(a != s and abs(a[0] - s[0]) + abs(a[1] - s[1]) == 1 and a != (b[0], b[1], a[2]) and b == (s[0], s[1] + 1, s[2] - 1)
            for a, s, b in ((STOI8R, START[8], LAD7R), (STOI9R, START[9], LAD8R))), "")
wszystko = set(DOJ[8]) | set(DOJ[9]) | set(POW[8]) | set(POW[9]) | set(PETLA[8]) | set(PETLA[9])
sprawdz("2h schody (32654,31674,z7/z8) poza wszystkimi trasami; zasypana dziura z7 tylko w dojsciach (jako pole przejscia); dziura z8 (32480,31721) tylko w dojsciu z9; powroty i petle jej nie dotykaja",
        not ({G.SCHODY8, G.SCHODY7_DOL} & wszystko) and ZASYP7 in DOJ[8] and ZASYP7 in DOJ[9] and DZ8 in DOJ[9] and DZ8 not in DOJ[8]
        and not ({ZASYP7, DZ8} & (set(POW[8]) | set(POW[9]) | set(PETLA[8]) | set(PETLA[9]))), "")
sprawdz("2i mapa: schody (32654,31674) flaga 2 na z7 i z8; zasypana dziura z7 flaga 2 kolor 24; dziura z8 (32480,31721) flaga 2 kolor 210; pola lin i stania chodliwe bez flagi 2",
        all(MAPA.flagi(*s) & _mapa.BEZ_DROGI for s in (G.SCHODY8, G.SCHODY7_DOL, ZASYP7, DZ8))
        and MAPA.pole(*ZASYP7)[1] == 24 and MAPA.pole(*DZ8)[1] == 210
        and all(not MAPA.flagi(*q) & (_mapa.SCIANA | _mapa.BEZ_DROGI) and MAPA.flagi(*q) & _mapa.WIDZIANE for q in (STOI8R, LAD7R, STOI9R, LAD8R, START[8], START[9])), "")

# 3. brak scian / ognia / stref / dziur
ogien = Z._ogn.ogien_pola() | Z.ogien_pola()          # 27.10: stary (tylko ogien_stale) i generatora (stale + epizody hp / n>=OGIEN_EPIZODY_MIN_N), oba z buforem 1
dzn = Z.dziury_nauczone() | Z.dziury_omijaj()          # 27.10: nauczone + reczna lista omijaj
for z in (8, 9):
    sciany = [p for t in (DOJ[z], POW[z], PETLA[z]) for p in t if not MAPA.flagi(*p) & _mapa.WIDZIANE or MAPA.flagi(*p) & _mapa.SCIANA]
    flaga2 = [p for t in (DOJ[z], POW[z], PETLA[z]) for p in t if MAPA.flagi(*p) & _mapa.BEZ_DROGI and p not in (ZASYP7, DZ8)]
    sprawdz(f"3a z{z} zero scian/niewidzianych i flagi 2 (poza polami zasypanej dziury z7 i dziury z8 w dojsciu) na trasach", not sciany and not flaga2, (sciany[:2], flaga2[:2]))
    sprawdz(f"3b z{z} zero punktow w ogniu, nauczonych dziurach i w strefie generatora (strefy zakazane + przeszkody + ogien, bufor 1)",
            not [p for t in (DOJ[z], POW[z], PETLA[z]) for p in t if p in ogien or p in dzn or p in zle], [p for t in (DOJ[z], POW[z], PETLA[z]) for p in t if p in zle][:3])
    skoki = [(a, b) for t in (DOJ[z], POW[z]) for a, b in zip(t, t[1:]) if a[2] == b[2] and max(abs(a[0] - b[0]), abs(a[1] - b[1])) > (4 if a[2] == 8 and a in set(DOJ[8][:i_l]) | set(POW[8][-i_l:]) else 1)]
    sprawdz(f"3c z{z} ciaglosc: krok 1 pole (A* po mapie), wyjatek <= 4 pola tylko w nagraniu Karola z8", not skoki, skoki[:2])
# niezalezna kontrola stref zakazanych (odleglosc Chebysheva od srodka spawnu): rotworm 12, poison spider 6 na z8/z9
for z in (8, 9):
    zle_sp = []
    for nazwa, r in Z.STREFA.items():
        for s in Z.spot_lib.spawny(z, (nazwa,), (32380, 32640, 31560, 31800)):
            for t in (DOJ[8], DOJ[9], POW[8], POW[9], PETLA[8], PETLA[9]):
                zle_sp += [(nazwa, (s["x"], s["y"]), p) for p in t if p[2] == z and max(abs(p[0] - s["x"]), abs(p[1] - s["y"])) <= r]
    sprawdz(f"3d z{z}: zaden punkt dojsc/powrotow/petli na z{z} w strefie rotwormow (12) i poison spiderow (6) wg spawnow (niezaleznie od generatora)", not zle_sp, zle_sp[:3])
sprawdz("3e kontrole generatora przechodza dla plikow (ciaglosc, sciany, flaga 2 tylko w polach przejsc, zmiany pieter)",
        Z.kontrole(MAPA, DOJ[9], zle, dz, dozw={ZASYP7, DZ8}, przej=[(G.STOI8, G.LAD7), (ZASYP7, START[8]), (DZ8, START[9])], nazwa="z9 dojscie") is None
        and Z.kontrole(MAPA, POW[9], zle, dz, przej=[(STOI9R, LAD8R), (STOI8R, LAD7R), (G.LAD7, G.LAD8)], nazwa="z9 powrot") is None, "")

# 3f-3k. 27.10 (z9 przeliczona): ogien (pliki ogien_*.json czytane NIEZALEZNIE od generatora), pelny skan przeszkod, dziury omijaj z buforem 1, wyjatki bez bufora
_og_stale = {tuple(q[:3]) for q in json.loads((Path(_R) / "trasy" / "ogien_stale.json").read_text()).get("pola", [])}
_og_ep = json.loads((Path(_R) / "trasy" / "ogien_epizody.json").read_text()).get("pola", {})
_og_raw = _og_stale | {tuple(int(a) for a in k.split(",")) for k, v in _og_ep.items()
                       if v.get("hp") or (Z.OGIEN_EPIZODY_MIN_N is not None and v.get("n", 0) >= Z.OGIEN_EPIZODY_MIN_N)}
_og_buf = {(x + dx, y + dy, zz) for x, y, zz in _og_raw for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
_og_wszystkie = {tuple(int(a) for a in k.split(",")) for k in _og_ep} | _og_stale
_og_wszystkie_buf = {(x + dx, y + dy, zz) for x, y, zz in _og_wszystkie for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
_wszystkie = {z: [(f"{n}", p) for n, t in (("dojscie", DOJ[z]), ("powrot", POW[z]), ("petla", PETLA[z])) for p in t] for z in (8, 9)}
for z in (8, 9):
    zly = [(n, p) for n, p in _wszystkie[z] if p in _og_buf]
    sprawdz(f"3f z{z} zero punktow dojscia/powrotu/petli w ogniu (ogien_stale + epizody hp{'' if Z.OGIEN_EPIZODY_MIN_N is None else f' lub n>={Z.OGIEN_EPIZODY_MIN_N}'}, bufor 1), pliki ognia czytane w tescie", not zly, zly[:3])
_omz = {tuple(q[:3]) for q in json.loads((Path(_R) / "trasy" / "dziury_omijaj.json").read_text())["dziury"]}
_om9 = {q for q in _omz if q[2] == 9}
zly = [(n, p) for z in (8, 9) for n, p in _wszystkie[z] if p in _omz]
sprawdz("3g zero punktow na polach z dziury_omijaj.json (z8 i z9)", not zly, zly[:3])
zly = [(n, p) for n, p in _wszystkie[9] if p[2] == 9 and any(max(abs(p[0] - q[0]), abs(p[1] - q[1])) <= 1 for q in _om9)]
sprawdz("3h z9: odstep >= 2 pola (Chebyshev) od kazdego pola dziury z9 z dziury_omijaj dla dojscia/powrotu/petli (upadek na z10 = smoki, bufor 1)", not zly, zly[:3])
# niezalezny pelny skan: wszystkie przeszkody (flaga 2 w kolorze podlogi) w bbox skladowej z9 +- margines; zadna nie moze lezec na trasie, a w odleglosci 1 tylko wyjatki BUFOR_WYJATKI9
_xs = [c[0] for c in pet[9][1]]                       # obszar SKLADOWEJ (nie tylko petli: przeszkody tuz za petla tez tworza bufor/zamykaja przejscia)
_ys = [c[1] for c in pet[9][1]]
_obsz = (min(_xs) - Z.MARGINES_SKANU, min(_ys) - Z.MARGINES_SKANU, max(_xs) + Z.MARGINES_SKANU, max(_ys) + Z.MARGINES_SKANU)
_prz9 = set(Z.skan_przeszkod(MAPA, 9, _obsz))
_stary_skan = {q for q in _prz9 if Z.SKAN[0] <= q[0] <= Z.SKAN[2] and Z.SKAN[1] <= q[1] <= Z.SKAN[3]}
sprawdz("3i z9: skan przeszkod w obszarze skladowej (nie w stalym prostokacie): pol flaga 2 w kolorze podlogi >= 57, wiecej niz w starym SKAN (poza nim lezaly 33 z 57 pol)",
        len(_prz9) >= 57 and len(_prz9 - _stary_skan) >= 33, (len(_prz9), len(_prz9 - _stary_skan)))
_blisko = sorted({(p, q) for _, p in _wszystkie[9] if p[2] == 9 for q in _prz9 if max(abs(p[0] - q[0]), abs(p[1] - q[1])) <= 1 and q not in Z.BUFOR_WYJATKI9})
sprawdz("3j z9: zaden punkt dojscia/powrotu/petli nie lezy na przeszkodzie ani tuz obok niej (bufor 1), poza wyjatkami BUFOR_WYJATKI9 (ich sasiedzi wolni, same pola nie)",
        not _blisko and not [p for _, p in _wszystkie[9] if p in _prz9], _blisko[:3])
print(f"INFO z9: punkty petli w buforze WSZYSTKICH epizodow ognia (takze n=1..2 bez spadku HP, szum wykrywania przy walce; informacyjnie, nie warunek): "
      f"{len({p for _, p in _wszystkie[9] if p in _og_wszystkie_buf})} roznych pol")
sprawdz("3k z9: wyjatki BUFOR_WYJATKI9 to przeszkody spoza listy dziur (dziury zawsze z buforem 1) i lezace w skanie", Z.BUFOR_WYJATKI9 <= _prz9 and not (Z.BUFOR_WYJATKI9 & _omz), sorted(Z.BUFOR_WYJATKI9 - _prz9)[:3])
_gardla = Z.waskie_gardla(MAPA, pet[9][1], zle, [(p[0], p[1]) for p in PETLA[9]], 9)
print(f"INFO z9 waskie gardla petli (pas szer. 1 przez bufor/ogien/przeszkode/dziure): {len(_gardla)} pol: {_gardla}")
sprawdz("3l petla z9 jest jedna skladowa: kazdy punkt w skladowej generatora, kroki 1 pole, brak powtorzen poza zawracaniem (zamknieta pętla)", all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 1 for a, b in zip(PETLA[9], PETLA[9][1:])), "")


# 4. wpis mapy.json
MJ = json.loads((Path(_R) / "mapy.json").read_text())
for z, pot in ((8, "Wolf,Snake"), (9, "Troll,Wolf,Snake")):   # 27.10: z9 bije też wilki/węże z korytarza z8 na dojściu (wilk blokował dojście, Karol)
    w = MJ.get(N[z], {})
    sprawdz(f"4a mapy.json {N[z]}: trasa/dojscie/potwory/prog_hp/dojscie_z_dowolnego_pietra, opis wspomina powrot i NIEZWERYFIKOWANE",
            w.get("trasa") == N[z] + "_petla" and w.get("dojscie") == N[z] + "_dojscie" and w.get("potwory") == pot and w.get("prog_hp") == 35
            and w.get("dojscie_z_dowolnego_pietra") is True and N[z] + "_do_depo" in w.get("opis", "") and "NIEZWERYFIKOWANE" in w.get("opis", ""), w)
sprawdz("4b spoty_nadzorca.json bez wpisow zachod (osobna decyzja Karola)", "abdendriel_zachod" not in (Path(_R) / "dane_tibia" / "spoty_nadzorca.json").read_text(), "")

# 5. etapy
for z in (8, 9):
    et = wypad.zbuduj_etapy(DOJ[z], MAPA, wypad.drzwi_z_mapy(DOJ[z], MAPA))
    typy = [e["typ"] for e in et]
    sprawdz(f"5a z{z} dojscie: etapy " + ("IDZ LINA IDZ DZIURA IDZ DZIURA IDZ" if z == 9 else "IDZ LINA IDZ DZIURA IDZ"), typy == (["IDZ", "LINA", "IDZ", "DZIURA", "IDZ"] + (["DZIURA", "IDZ"] if z == 9 else [])), typy)
    sprawdz(f"5b z{z} dojscie: schody z8 (32654,31674): cel = pole schodow, schody=True, stoi (32654,31675,z8), ladunek (32654,31673,z7); sprawdz_plan bez uwag",
            et[1]["cel"] == G.SCHODY8 and et[1].get("schody") is True and tuple(et[1]["stoi"]) == G.STOI8 and tuple(et[1]["ladunek"]) == G.LAD7
            and not wypad.sprawdz_plan(et, MAPA, {}, rampy_ok=True), (et[1], wypad.sprawdz_plan(et, MAPA, {}, rampy_ok=True)[:2]))
    sprawdz(f"5c z{z} dojscie: bez drzwi (drzwi_z_mapy puste)", not wypad.drzwi_z_mapy(DOJ[z], MAPA), sorted(wypad.drzwi_z_mapy(DOJ[z], MAPA)))
    ep = wypad.zbuduj_etapy(POW[z], MAPA, wypad.drzwi_z_mapy(POW[z], MAPA))
    typy = [e["typ"] for e in ep]
    sprawdz(f"5d z{z} powrot: etapy " + ("IDZ LINA IDZ LINA IDZ DZIURA IDZ" if z == 9 else "IDZ LINA IDZ DZIURA IDZ"),
            typy == (["IDZ", "LINA", "IDZ", "LINA", "IDZ", "DZIURA", "IDZ"] if z == 9 else ["IDZ", "LINA", "IDZ", "DZIURA", "IDZ"]), typy)
    linie = [e for e in ep if e["typ"] == "LINA"]
    cele = [(START[9], STOI9R, LAD8R), (START[8], STOI8R, LAD7R)] if z == 9 else [(START[8], STOI8R, LAD7R)]
    sprawdz(f"5e z{z} powrot: kazda LINA ma cel = pole liny, stoi = sasiad prostopadly, ladunek (x, y+1) pietro wyzej, bez 'schody' i 'wlasne'",
            [(tuple(e["cel"]), tuple(e["stoi"]), tuple(e["ladunek"])) for e in linie] == cele and not any(e.get("schody") or e.get("wlasne") for e in linie), linie)
    dz_ = [e for e in ep if e["typ"] == "DZIURA"]
    sprawdz(f"5f z{z} powrot: schody w dol z7 jak w gobliny: DZIURA stoi (32654,31673,z7), ladunek (32654,31675,z8); sprawdz_plan bez uwag",
            [(tuple(e["stoi"]), tuple(e["ladunek"])) for e in dz_] == [(G.LAD7, G.LAD8)] and not wypad.sprawdz_plan(ep, MAPA, {}, rampy_ok=True), (dz_, wypad.sprawdz_plan(ep, MAPA, {}, rampy_ok=True)[:2]))
    sprawdz(f"5g z{z} powrot: bez drzwi", not wypad.drzwi_z_mapy(POW[z], MAPA), sorted(wypad.drzwi_z_mapy(POW[z], MAPA)))

# 6. wpisy PLANY_PK i wybor planu
PL = {z: next((p for p in W.PLANY_PK if p["nazwa"] == N[z]), None) for z in (8, 9)}
sprawdz("6a PLANY_PK: oba wpisy, do = _do_depo, z = _dojscie, bez npc/prefiksu/drzwi/kluczy/wyjsc, pliki istnieja",
        all(PL[z] and PL[z]["do"] == f"{N[z]}_do_depo.json" and PL[z]["z"] == f"{N[z]}_dojscie.json" and not PL[z]["npc"] and not PL[z]["prefix"]
            and not any(k in PL[z] for k in ("drzwi", "klucze", "wyjscia")) and trasa_io.sciezka(PL[z]["do"]).is_file() and trasa_io.sciezka(PL[z]["z"]).is_file() for z in (8, 9)), PL)
nazwy = [p["nazwa"] for p in W.PLANY_PK]
sprawdz("6b kolejnosc: wpisy zachod za planami trolli i gobliny (remis na wspolnym korytarzu depo wygrywa wczesniejszy plan)",
        nazwy.index(N[8]) > nazwy.index("abdendriel_gobliny_z6") > nazwy.index("abdendriel_trolle_z12") > nazwy.index("abdendriel_trolle_z10") and nazwy.index(N[9]) == nazwy.index(N[8]) + 1, nazwy[-5:])
dmax = {z: max(max(abs(p[0] - DEPO[0]), abs(p[1] - DEPO[1])) for p in PETLA[z]) for z in (8, 9)}
sprawdz(f"6c zasieg planow >= odleglosc najdalszego punktu petli od depo ({dmax[8]}/{dmax[9]}), a domyslne {W.DEPO_DOJSCIE_ZASIEG} nie wystarcza",
        all(W.zasieg_planu(N[z]) >= dmax[z] for z in (8, 9)) and max(dmax.values()) > W.DEPO_DOJSCIE_ZASIEG, (dmax, [W.zasieg_planu(N[z]) for z in (8, 9)]))
sprawdz("6d PLAN_PIETRA_WYBOR: plan z9 wybierany tylko z z9 (jego 'do' ma 75 punktow z8)", W.PLAN_PIETRA_WYBOR.get(N[9]) == (9,), W.PLAN_PIETRA_WYBOR)
baza = W.punkty_bazy(nazwy=W.BAZY_PK)
sprawdz("6e punkty_bazy wczytuje oba plany (do == powrot, z == dojscie)", all(N[z] in baza and [tuple(p) for p in baza[N[z]][0]] == POW[z] and [tuple(p) for p in baza[N[z]][1]] == DOJ[z] for z in (8, 9)), list(baza)[-3:])
w8 = {W.wybierz_baze(baza, p, W.PK_PLAN_ZASIEG) for p in PETLA[8][::7]}
w9 = {W.wybierz_baze(baza, p, W.PK_PLAN_ZASIEG) for p in PETLA[9][::7]}
sprawdz("6f wybierz_baze (zasieg PK 80): z kazdego 7. punktu petli z8 tylko plan abdendriel_zachod_z8; z petli z9 plan z9 albo None (None = dalej niz 80 od pola liny, wtedy _baza_dojscie)",
        w8 == {N[8]} and w9 <= {N[9], None} and N[9] in w9, (w8, w9))
dalej9 = [p for p in PETLA[9] if W.wybierz_baze(baza, p, W.PK_PLAN_ZASIEG) is None]
sprawdz("6g punkty petli z9 z wybierz_baze == None (ok. 40%) maja _baza_dojscie bez bledu, panel.plan_depo != None (plan_depo_dostepny w panelu) takze dla petli z8",
        dalej9 and all(panel.plan_depo(p) is not None for p in dalej9[::10] + PETLA[8][::40]), len(dalej9))
inne = [(n, tuple(d[0][i])) for n, d in baza.items() if not n.startswith("abdendriel_zachod") for i in range(0, len(d[0]), 15)]
zm = [(n, p) for n, p in inne if W.wybierz_baze(baza, p, W.PK_PLAN_ZASIEG) in (N[8], N[9])]
sprawdz("6h punkty 'do' innych planow (Edron/Kazordoon/Thais/Rook/Port Hope/Ab'Dendriel trolle i gobliny) nie wybieraja planow zachod", not zm, zm[:3])
zm2 = [(z, p) for z in (8, 9) for p in POW[z] if p[2] in (7, 8) and p[1] < 31690 and W.wybierz_baze(baza, p, W.PK_PLAN_ZASIEG) is None]
sprawdz("6i kazdy punkt 'do' zachodu na z7/z8 ma wybrany jakis plan", not zm2, zm2[:3])

# 7. pelny start ucieczki PK z punktow petli: ten sam harness co gobliny (test 6e), ale z prawdziwymi PLANY_PK
TMP = Path(tempfile.mkdtemp())


class KonfW:
    WYPRAWA_AKTYWNA = 1
    WYPRAWA_MAX_CZAS_S = 1800
    WYPRAWA_MAX_KROKOW = 6000
    WYPRAWA_STOP_PRZY_UTKNIECIU = 1
    WYPRAWA_CO_MIN = 20
    WYPRAWA_PO_DEPO_S = 900
    WYPRAWA_DEPO_POWROT = 0
    WYPRAWA_TYLKO_DEPO = 1


class OpsW:
    def wiadomosci(o):
        return []


def _cbw(poz, petla):
    class CBW:
        mapa = MAPA

        def __init__(c):
            c.t, c.wypad_aktywny, c.poz, c.punkty, c.stan = 0.0, False, poz, list(petla), None
            c.postac = types.SimpleNamespace(pozycja=lambda: c.poz)

        def zegar(c):
            return c.t

        def gracz(c):
            return {"proc": 60.0}

        def _wypad_reset_klik(c):
            pass

        def droga(c, *a, **k):
            return []

        def pauza(c, *a):
            pass
    return CBW()


dane = {"powody": ["pk"], "zapas": None, "blanki": None, "zloto": None, "cap": None, "hp": 60, "pochodnie": None, "depo": True}
OCZEK = {8: ["IDZ", "LINA", "IDZ", "DZIURA", "IDZ"], 9: ["IDZ", "LINA", "IDZ", "LINA", "IDZ", "DZIURA", "IDZ"]}
for z in (8, 9):
    P = PETLA[z]
    pole = START[z]
    # probki: co ~70-90 punkt petli + najdalszy od depo + najdalszy od pola liny (na pietrze petli) + najblizszy depo
    dal_depo = max(range(len(P)), key=lambda i: max(abs(P[i][0] - DEPO[0]), abs(P[i][1] - DEPO[1])))
    dal_lina = max(range(len(P)), key=lambda i: max(abs(P[i][0] - pole[0]), abs(P[i][1] - pole[1])))
    probki = sorted(set(list(range(0, len(P), 70 if z == 8 else 90)) + [dal_depo, dal_lina, len(P) - 1]))
    zle7, ile_dal_depo, ile_dal_lina, ile_poza_zasiegiem = [], 0, 0, 0
    for i in probki:
        poz = P[i]
        w = W.Wyprawa(_cbw(poz, P), OpsW(), konf=KonfW(), log=lambda *_: None, plik_stanu=TMP / f"s{z}_{i}.json", plik_sklepow=TMP / "sk.json",
                      plik_npc=TMP / "npc.json", plik_stop=TMP / f"STOP{z}_{i}", czas=lambda: 5_000_000.0)
        wynik = w._start_wyprawa("depo:pk_ucieczka", dane, 0.0, baza_nazwa=None, pk="ucieczka")
        et = w.w["legs"][0] if w.w else []
        ile_dal_lina += max(abs(poz[0] - pole[0]), abs(poz[1] - pole[1])) > W.PK_PLAN_ZASIEG
        ile_poza_zasiegiem += max(abs(poz[0] - DEPO[0]), abs(poz[1] - DEPO[1])) > W.DEPO_DOJSCIE_ZASIEG
        if not (wynik is True and w.w["baza"] == N[z] and [e["typ"] for e in et] == OCZEK[z] and not wypad.sprawdz_plan(et, MAPA, {}, rampy_ok=True)
                and tuple(et[-1]["punkty"][-1]) == DEPO):
            zle7.append((i, poz, w.w and w.w["baza"], [e["typ"] for e in et]))
    sprawdz(f"7{'ab'[z - 8]} z{z}: ucieczka PK z {len(probki)} punktow petli (w tym {ile_dal_lina} dalszych niz {W.PK_PLAN_ZASIEG} od pola liny i {ile_poza_zasiegiem} dalszych niz {W.DEPO_DOJSCIE_ZASIEG} od depo): baza {N[z]}, "
            f"etapy {' '.join(OCZEK[z])}, koniec = depo, sprawdz_plan bez uwag", not zle7 and (z == 8 or ile_dal_lina > 0), zle7[:3])

# ---- 8. 27.10 (Karol: "na z10 są smoki, na pewno zginie"): pola flaga 2 na z9/z8 zakazane jak ściana, trasy ich nie dotykają
import json as _j
_om = _j.loads((Path(__file__).resolve().parent.parent / "trasy" / "dziury_omijaj.json").read_text())
_omz = {tuple(p[:3]) for p in _om["dziury"]}
_z9f = {(x, y, 9) for x in range(32380, 32550) for y in range(31555, 31750)
        if MAPA.flagi(x, y, 9) & _mapa.WIDZIANE and not MAPA.flagi(x, y, 9) & _mapa.SCIANA and MAPA.flagi(x, y, 9) & _mapa.BEZ_DROGI}
_z9d = {q for q in _z9f if any(Z.spot_lib.chodliwe_z(MAPA, q[0] + a, q[1] + b, 10) for a in (-1, 0, 1) for b in (-1, 0, 1))}
sprawdz("8a pola flaga 2 na z9 w obszarze pętli, pod którymi jest chodliwe z10 (możliwe dziury), są na liście dziury_omijaj (27.10: pola bez podłoża pod spodem to przeszkody, poza listą: orbita w przejściu między nimi)",
        len(_z9f) >= 57 and len(_z9d) >= 35 and _z9d <= _omz, sorted(_z9d - _omz)[:5])
sprawdz("8b dziura z8 (32513,31656) z listy zakazanych", (32513, 31656, 8) in _omz)
for _n in ("abdendriel_zachod_z8_petla", "abdendriel_zachod_z8_dojscie", "abdendriel_zachod_z8_do_depo",
           "abdendriel_zachod_z9_petla", "abdendriel_zachod_z9_dojscie", "abdendriel_zachod_z9_do_depo"):
    _p = _j.loads((Path(__file__).resolve().parent.parent / "trasy" / f"{_n}.json").read_text())
    _p = _p.get("punkty", _p) if isinstance(_p, dict) else _p
    sprawdz(f"8c {_n}: zero punktów na polach zakazanych", not [q for q in map(tuple, _p) if q in _omz])

# ---- 9. 27.10 (Karol: porownanie na zywo pelna / polnoc / poludnie): warianty petli z9 (generuj_trasy_abdendriel_zachod_ns.py) ----
import generuj_trasy_abdendriel_zachod_ns as NS
WAR = ("polnoc", "poludnie")
NW = {w: f"{Z.NAZWA}_z9_{w}" for w in WAR}
LAD9 = START[9]                                                    # (32480,31721,9): pole liny = start i koniec (wpisane niezaleznie od generatora)
PW_ = {w: [tuple(p) for p in trasa_io.wczytaj(NW[w] + "_petla")[0]] for w in WAR}
ns_out = NS.zbuduj_ns(MAPA)
_og_all = _og_buf                                                  # ogien (stale + epizody hp, bufor 1), czytany w tescie niezaleznie od generatora
for w in WAR:
    P, o = PW_[w], ns_out[w]
    sprawdz(f"9a {w}: plik petli == generator, jedno pietro z9, cala w skladowej generatora pelnej petli z9",
            P == [(x, y, 9) for x, y in o["pelna"]] and all(p[2] == 9 for p in P) and all((p[0], p[1]) in pet[9][1] for p in P), (len(P), len(o["pelna"])))
    sprawdz(f"9b {w}: start = koniec = ladowanie (32480,31721,z9) = pole liny i start dojscia z9 konczy sie tam; ciaglosc: kroki <= 1 pole",
            P[0] == P[-1] == LAD9 == DOJ[9][-1] and all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 1 for a, b in zip(P, P[1:])), (P[0], P[-1]))
    zly = [(n, p) for n, p in (("ogien", [q for q in P if q in _og_all]), ("dziura", [q for q in P if q in _omz]),
                              ("przeszkoda/bufor", [q for q in P if q in _prz9 or any(max(abs(q[0] - r[0]), abs(q[1] - r[1])) <= 1 for r in _prz9)]),
                              ("sciana/flaga2", [q for q in P if not MAPA.flagi(*q) & _mapa.WIDZIANE or MAPA.flagi(*q) & (_mapa.SCIANA | _mapa.BEZ_DROGI)]),
                              ("odstep<2 od dziury z9", [q for q in P if any(max(abs(q[0] - r[0]), abs(q[1] - r[1])) <= 1 for r in _om9)])) if p]
    sprawdz(f"9c {w}: zero punktow w ogniu (pliki ognia, bufor 1), na polach dziur, w buforze przeszkod (pelny skan), na scianach/flagach 2, odstep >= 2 od dziur z9", not zly, zly[:3])
    zle_sp = []
    for nazwa, r in Z.STREFA.items():
        for s_ in Z.spot_lib.spawny(9, (nazwa,), (32380, 32640, 31560, 31800)):
            zle_sp += [(nazwa, (s_["x"], s_["y"]), p) for p in P if max(abs(p[0] - s_["x"]), abs(p[1] - s_["y"])) <= r]
    sprawdz(f"9d {w}: zadna strefa zakazana (rotworm 12, poison spider 6) nie dotyka petli (niezaleznie od generatora)", not zle_sp, zle_sp[:3])
    jw = json.loads((Path(_R) / "dane_tibia" / "mapy" / f"{NW[w]}.json").read_text())
    sprawdz(f"9e {w}: opis .json: start = ladowanie, dlugosc_petli == punkty pliku, przystanki == generator",
            jw["start"] == list(LAD9) and jw["dlugosc_petli"] == len(P) and len(jw["przystanki"]) - 1 == len(o["st"])
            and sum(t.get("potworow", 0) for t in jw["przystanki"]) == sum(t["n"] for t in o["st"]), jw["dlugosc_petli"])
    print(f"INFO {w}: {len(P)} pkt, {len(o['st'])} przystankow, {sum(t['n'] for t in o['st'])} potworow, {len(P) / sum(t['n'] for t in o['st']):.1f} pola/potwora, waskie gardla (generator) {len(o['gardla'])}: {o['gardla']}")
# 9f. podzial: rozlaczne, suma = wszystkie osiagalne przystanki celowane bez WYKLUCZONE_NS (minus pominiete regula kosztu), prog y
_L, _comp, _sc, _zle, _wszystkie = NS.przygotuj(MAPA)
sprawdz("9f skladowa i sciany z9 obu wariantow = skladowa i sciany generatora pelnej petli z9 (ta sama polityka: ogien, dziury, skan, strefy)",
        set(_comp) == set(pet[9][1]) and _zle == {p for p in zle if p[2] == 9}, (len(_comp), len(pet[9][1])))
_cele = {t["pt"]: t["n"] for t in _wszystkie if t["pt"] not in NS.WYKLUCZONE_NS}
_st = {w: {t["pt"]: t["n"] for t in ns_out[w]["st"]} for w in WAR}
_pom = {w: {pt for pt, *_ in ns_out[w]["pomin"]} for w in WAR}
sprawdz("9g podzial wg y: polnoc y < PROG_Y, poludnie y >= PROG_Y; rozlaczne; razem = wszystkie osiagalne przystanki bez wykluczonych i bez pominietych regula kosztu; polnocny pokoj (32436,31573) wykluczony",
        all(pt[1] < NS.PROG_Y for pt in _st["polnoc"]) and all(pt[1] >= NS.PROG_Y for pt in _st["poludnie"]) and not (set(_st["polnoc"]) & set(_st["poludnie"]))
        and set(_st["polnoc"]) | set(_st["poludnie"]) | _pom["polnoc"] | _pom["poludnie"] == set(_cele) and (32436, 31573) in NS.WYKLUCZONE_NS and (32436, 31573) not in _cele
        and all(_cele[pt] == n for w in WAR for pt, n in _st[w].items()), (sorted(_cele), _st))
_n = {w: sum(_st[w].values()) for w in WAR}
sprawdz("9h liczby potworow polnoc/poludnie zblizone (roznica <= 6; 17/22 w stanie 27.10) i kazda polowa ma >= 5 przystankow",
        abs(_n["polnoc"] - _n["poludnie"]) <= 6 and all(len(_st[w]) >= 5 for w in WAR), _n)
def _cykl_ns(stops):
    wez = [tuple(LAD9[:2])] + list(stops)
    return Z.held_karp(Z.macierz_drog(MAPA, 9, wez, _sc))[1]


_zle_ns = []
for w in WAR:
    pts = [t["pt"] for t in ns_out[w]["st"]]
    pelny = _cykl_ns(pts)
    if pelny != len(ns_out[w]["pelna"]) - 1:
        _zle_ns.append((w, "dlugosc", pelny, len(ns_out[w]["pelna"]) - 1))
    for pt in pts:                                                    # zachowany przystanek <= 2 potwory nie moze kosztowac > 25% cyklu
        if _st[w][pt] <= NS.KOSZT_MAX_POTW and pelny - _cykl_ns([q for q in pts if q != pt]) > NS.KOSZT_PROG * pelny:
            _zle_ns.append((w, "zachowany drogi", pt))
    for pt, n_, g, proc in ns_out[w]["pomin"]:                      # pominiety: n <= 2 i zysk > 25% cyklu przed pominieciem
        if not (n_ <= NS.KOSZT_MAX_POTW and g > NS.KOSZT_PROG * (pelny + g)):
            _zle_ns.append((w, "pominiety nie spelnia reguly", pt, g))
sprawdz("9i dlugosc petli = DOKLADNY cykl Held-Karp (niezalezna macierz A*); regula kosztu: zaden zachowany przystanek <= 2 potwory nie skraca cyklu o > 25%, kazdy pominiety (n <= 2) skracal o > 25%",
        not _zle_ns, _zle_ns[:3])
# 9j. wpisy mapy.json
for w in WAR:
    e = MJ.get(NW[w], {})
    sprawdz(f"9j mapy.json {NW[w]}: trasa, potwory Troll,Wolf,Snake, prog_hp 35, dojscie = dojscie pelnej z9, dojscie_z_dowolnego_pietra, plik petli i opis z liczbami pol/przystankow",
            e.get("trasa") == NW[w] + "_petla" and e.get("potwory") == "Troll,Wolf,Snake" and e.get("prog_hp") == 35 and e.get("dojscie") == N[9] + "_dojscie"
            and e.get("dojscie_z_dowolnego_pietra") is True and trasa_io.sciezka(NW[w] + "_petla").is_file() and str(len(PW_[w])) in e.get("opis", "")
            and "NIEPRZEJŚTE NA ŻYWO" in e.get("opis", ""), e)
sprawdz("9k nazwy wariantow rozne od pelnej petli, dojscia i z8; wpis mapy pelnej z9 wskazuje wciaz swoja petle (generator ns nie pisze w nazwy pelnej; zgodnosc pliku pelnej petli z ogniem sprawdza 1a)",
        all(NW[w] not in (N[8], N[9]) for w in WAR) and MJ[N[9]]["trasa"] == N[9] + "_petla" and MJ[N[9]]["dojscie"] == N[9] + "_dojscie", "")
# 9l. pelny start ucieczki PK z punktow obu petli: plan abdendriel_zachod_z9 (wybor po pozycji, nie po nazwie mapy)
for w in WAR:
    P = PW_[w]
    dal_lina = max(range(len(P)), key=lambda i: max(abs(P[i][0] - LAD9[0]), abs(P[i][1] - LAD9[1])))
    dal_depo = max(range(len(P)), key=lambda i: max(abs(P[i][0] - DEPO[0]), abs(P[i][1] - DEPO[1])))
    probki = sorted(set(list(range(0, len(P), 40)) + [dal_depo, dal_lina, len(P) - 1]))
    zle9l, ile_dal_lina, ile_poza = [], 0, 0
    for i in probki:
        poz = P[i]
        wy = W.Wyprawa(_cbw(poz, P), OpsW(), konf=KonfW(), log=lambda *_: None, plik_stanu=TMP / f"s{w}_{i}.json", plik_sklepow=TMP / "sk.json",
                       plik_npc=TMP / "npc.json", plik_stop=TMP / f"STOP{w}_{i}", czas=lambda: 5_000_000.0)
        wynik = wy._start_wyprawa("depo:pk_ucieczka", dane, 0.0, baza_nazwa=None, pk="ucieczka")
        et = wy.w["legs"][0] if wy.w else []
        ile_dal_lina += max(abs(poz[0] - LAD9[0]), abs(poz[1] - LAD9[1])) > W.PK_PLAN_ZASIEG
        ile_poza += max(abs(poz[0] - DEPO[0]), abs(poz[1] - DEPO[1])) > W.DEPO_DOJSCIE_ZASIEG
        if not (wynik is True and wy.w["baza"] == N[9] and [e["typ"] for e in et] == OCZEK[9] and not wypad.sprawdz_plan(et, MAPA, {}, rampy_ok=True)
                and tuple(et[-1]["punkty"][-1]) == DEPO):
            zle9l.append((i, poz, wy.w and wy.w["baza"], [e["typ"] for e in et]))
    sprawdz(f"9l {w}: ucieczka PK z {len(probki)} punktow petli (w tym {ile_dal_lina} dalszych niz {W.PK_PLAN_ZASIEG} od pola liny, {ile_poza} dalszych niz {W.DEPO_DOJSCIE_ZASIEG} od depo): "
            f"baza {N[9]}, etapy {' '.join(OCZEK[9])}, koniec = depo, sprawdz_plan bez uwag", not zle9l and ile_dal_lina > 0, zle9l[:3])
    wb = {W.wybierz_baze(baza, p, W.PK_PLAN_ZASIEG) for p in P[::5]}
    sprawdz(f"9m {w}: wybierz_baze (zasieg PK 80) z kazdego 5. punktu petli: plan {N[9]} albo None (None = dalej niz 80, wtedy _baza_dojscie); nigdy inny plan",
            wb <= {N[9], None} and N[9] in wb, wb)

print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
