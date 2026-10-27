"""27.10: PODGLAD poludniowej petli v3 (generuj_trasy_abdendriel_zachod_ns3.py): jedyny wyjatek od polityki = bufor ognia 0 dla (32437,31695,z9) (samo pole sciana, sasiedzi wolni).
Nic nie wysyla do gry i niczego nie zmienia na dysku. Sprawdza: plik == generator, start = koniec = ladowanie (32480,31721,z9), ciaglosc, zero punktow NA polach ognia surowego i dziur,
zero w buforze KAZDEGO innego pola ognia (bufor 1), zero w buforze przeszkod i dziur (odstep >= 2), sciany/flaga 2/strefy, wspolne pola z polnocna v2 poza ladowaniem = 0,
dlugosc == niezalezny Held-Karp, BRAK wpisu v3 w mapy.json, BRAK zmian plikow (sha256 sprzed v3: v2, stare N/S, pelna, mapy.json, generatory ns/ns2/Z).
NIEPOTWIERDZONE NA ZYWO: przejscie OBOK pola ognia (sasiedztwo 1 pola) i wszystko, co dotyczy gry."""
import os as _os
_os.environ["RETRONIC_TESTY"] = "1"
import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
_R = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _R)
import mapa as _mapa
import trasa_io
import generuj_trasy_abdendriel_zachod as Z
import generuj_trasy_abdendriel_zachod_ns as NS
import generuj_trasy_abdendriel_zachod_ns2 as V2
import generuj_trasy_abdendriel_zachod_ns3 as V3

ok = []


def sprawdz(nazwa, warunek, info=""):
    warunek = bool(warunek)
    ok.append(warunek)
    print(("OK   " if warunek else "FAIL ") + nazwa + ("" if warunek else f"  [{info}]"))


if not _mapa.PLIK_MAPY.is_file():
    print("brak pliku mapy, pomijam")
    sys.exit(0)
ROOTP = Path(_R)
MAPA = _mapa.Mapa()
LAD9 = (32480, 31721, 9)
WYJ = {(32437, 31695, 9)}
cheb = V2.cheb
P = [tuple(p) for p in trasa_io.wczytaj("abdendriel_zachod_z9_poludnie_v3_petla")[0]]
PN = [tuple(p) for p in trasa_io.wczytaj("abdendriel_zachod_z9_polnoc_v2_petla")[0]]
DOJ9 = [tuple(p) for p in trasa_io.wczytaj("abdendriel_zachod_z9_dojscie")[0]]
o = V3.zbuduj_v3(MAPA)

_og_stale = {tuple(q[:3]) for q in json.loads((ROOTP / "trasy" / "ogien_stale.json").read_text()).get("pola", [])}
_og_ep = json.loads((ROOTP / "trasy" / "ogien_epizody.json").read_text()).get("pola", {})
_og_raw = _og_stale | {tuple(int(a) for a in k.split(",")) for k, v in _og_ep.items() if v.get("hp")}
_og_inne = _og_raw - WYJ
_og_buf_inne = {(x + dx, y + dy, zz) for x, y, zz in _og_inne for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
_omz = {tuple(q[:3]) for q in json.loads((ROOTP / "trasy" / "dziury_omijaj.json").read_text())["dziury"]}
_om9 = {q for q in _omz if q[2] == 9}
_dzn = {tuple(q) for q in json.loads((ROOTP / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])}
_xs, _ys = [c[0] for c in o["comp"]], [c[1] for c in o["comp"]]
_prz9 = set(Z.skan_przeszkod(MAPA, 9, (min(_xs) - Z.MARGINES_SKANU, min(_ys) - Z.MARGINES_SKANU, max(_xs) + Z.MARGINES_SKANU, max(_ys) + Z.MARGINES_SKANU)))

sprawdz("a plik v3 == generator v3 (ogien/dziury jak dzis), jedno pietro z9, cala w skladowej",
        P == [(x, y, 9) for x, y in o["pelna"]] and all(p[2] == 9 for p in P) and all((p[0], p[1]) in o["comp"] for p in P), (len(P), len(o["pelna"])))
sprawdz("b start = koniec = ladowanie (32480,31721,z9) = ostatni punkt dojscia z9; ciaglosc: kroki <= 1 pole",
        P[0] == P[-1] == LAD9 == DOJ9[-1] and all(cheb(a, b) <= 1 for a, b in zip(P, P[1:])), (P[0], P[-1]))
zly = [(n, p) for n, p in (("NA polu ognia surowego", [q for q in P if q in _og_raw]), ("w buforze INNEGO pola ognia", [q for q in P if q in _og_buf_inne]),
                          ("na polu dziury", [q for q in P if q in _omz or q in _dzn]),
                          ("przeszkoda/bufor", [q for q in P if q in _prz9 or any(cheb(q, r) <= 1 for r in _prz9)]),
                          ("sciana/flaga2", [q for q in P if not MAPA.flagi(*q) & _mapa.WIDZIANE or MAPA.flagi(*q) & (_mapa.SCIANA | _mapa.BEZ_DROGI)]),
                          ("odstep<2 od dziury z9", [q for q in P if any(cheb(q, r) <= 1 for r in _om9)])) if p]
sprawdz("c zero punktow NA polach ognia surowego, w buforze innych pol ognia, na polach dziur, w buforze przeszkod, na scianach/flagach 2, odstep >= 2 od dziur z9", not zly, zly[:3])
przy = sorted({q for q in P if cheb(q, (32437, 31695)) <= 1})
sprawdz("c2 punkty przy polu wyjatku (32437,31695) sa tylko jego sasiadami (Chebyshev == 1), same pole nie nalezy do trasy", (32437, 31695, 9) not in P and all(cheb(q, (32437, 31695)) == 1 for q in przy), przy)
print(f"INFO punkty trasy w Chebyshev <= 1 od (32437,31695): {sum(1 for q in P if cheb(q, (32437, 31695)) <= 1)}, unikalne {przy}")
zle_sp = []
for nazwa, r in Z.STREFA.items():
    for s_ in Z.spot_lib.spawny(9, (nazwa,), (32380, 32640, 31560, 31800)):
        zle_sp += [(nazwa, p) for p in P if cheb(p, (s_["x"], s_["y"])) <= r]
sprawdz("d zadna strefa zakazana (rotworm 12, poison spider 6) nie dotyka petli", not zle_sp, zle_sp[:3])
A, B = [(p[0], p[1]) for p in PN], [(p[0], p[1]) for p in P]
wsp = set(A) & set(B)
poza = sorted(p for p in wsp if cheb(p, LAD9) > V2.LAD_PROMIEN)
sprawdz("e wspolne pola v3 z polnocna v2 (plik): poza ladowaniem 0, wspolnych <= 5", not poza and len(wsp) <= V2.WSPOLNE_MAX, (len(wsp), poza[:5]))
da, db = [q for q in set(A) if cheb(q, LAD9) > V2.LAD_PROMIEN_BLISKO], [q for q in set(B) if cheb(q, LAD9) > V2.LAD_PROMIEN_BLISKO]
bl1 = sum(1 for p in da if any(cheb(p, q) <= 1 for q in db))
sprawdz(f"e2 brak sasiedztwa (Chebyshev <= 1) punktow v3 i polnocnej v2 poza promieniem {V2.LAD_PROMIEN_BLISKO} od ladowania", bl1 == 0, bl1)
wez = [tuple(LAD9[:2])] + [t["pt"] for t in o["st"]]
sprawdz("f dlugosc petli = DOKLADNY cykl Held-Karp (niezalezna macierz A*)", Z.held_karp(Z.macierz_drog(MAPA, 9, wez, o["sciana"]))[1] == len(P) - 1, (len(P) - 1))
MJ = json.loads((ROOTP / "mapy.json").read_text())
sprawdz("g BRAK wpisu v3 w mapy.json (podglad)", not [k for k in MJ if k.endswith("_v3")], [k for k in MJ if "v3" in k])
SHA = {}
SHA.update({
    "trasy/abdendriel_zachod_z9_petla.json": "3f395e0f799ac623abbee61a66ea5d9d2b53f4f81c95f3148fb03c52f99887b3",
    "trasy/abdendriel_zachod_z9_polnoc_petla.json": "75dfcbb74ffdaa4b39321c7c0bc86fcbdcc57ddb6cda0febd24557b60302eef8",
    "trasy/abdendriel_zachod_z9_polnoc_v2_petla.json": "e7490cc29d5aba61acfd4c52a430afe142990e5b11777adef223df86a754c3d5",
    "trasy/abdendriel_zachod_z9_poludnie_petla.json": "dd45c6982c3fec92b36a19b7c66718bb020791b5e3a8d18d32687b6863284dd6",
    "trasy/abdendriel_zachod_z9_poludnie_v2_petla.json": "493de90213391dce53e95133761582b863272a97cfe6cd2ebd60705479821f18",
    "dane_tibia/mapy/abdendriel_zachod_z9.json": "16584c185696a589f2432b42b1eedd99566f13fa3db3449451c3d2f7ef364f7e",
    "dane_tibia/mapy/abdendriel_zachod_z9_polnoc.json": "681fb250d9d60b2993548ecbe7dd867ae9541f1bc70947a0d1ea47cd7dad31a1",
    "dane_tibia/mapy/abdendriel_zachod_z9_polnoc_v2.json": "16eb46b1f520ce2e0b736d4ae10b4b186eb0d46a3706a7fbd7088e196ba2b259",
    "dane_tibia/mapy/abdendriel_zachod_z9_poludnie.json": "75a2de671c56cb343b01eb2553904d41c29f28b2a015817dd3f43b82df089bea",
    "dane_tibia/mapy/abdendriel_zachod_z9_poludnie_v2.json": "d5cc20158865e59fd5112739738cb5f698ed1fc3b117b0548bfc116b8d1f27a6",
    "dane_tibia/mapy/abdendriel_zachod_z9_dojscie.png": "a1d70e54c6fe154081e8009c2cbde58dcbbf8b3c60f82e1935cc0cfb39393d30",
    "dane_tibia/mapy/abdendriel_zachod_z9.png": "4b79e2a6a51240a59f54e10b2ecc636607662681c36bb2052f0eeb90f4be3812",
    "dane_tibia/mapy/abdendriel_zachod_z9_polnoc.png": "b409f7716d5101ba111f6d0522c6c04e3ed0709a6eb7ff9e93caeb145557d075",
    "dane_tibia/mapy/abdendriel_zachod_z9_polnoc_v2.png": "08e1f7423f45ab9b273d8ef2c10c392639fcfc07cf3b4c3f4cd8fda30215e06c",
    "dane_tibia/mapy/abdendriel_zachod_z9_poludnie.png": "be6907d83694f49b5c931471161781804e3da6526d83f7fc39ff45ac1eacd22f",
    "dane_tibia/mapy/abdendriel_zachod_z9_poludnie_v2.png": "f2142f8c579cbed952f68d7dfa6e2f3dc6ba902ff5baa6644c0a85974370bf57",
    "mapy.json": "71ccc9d4bf8ef70ae2c0df6ac61842ecd98d5f370b590016857b1ac6bb368a33",
    "generuj_trasy_abdendriel_zachod_ns.py": "6949a1c6fcf6f94572f9bd74438196ee2612b6ff2aaf44b4d825ad3344250138",
    "generuj_trasy_abdendriel_zachod_ns2.py": "01a86ffd828ef282639b3538cebebdf00722723b615c65b8e49390f76f89aed2",
    "generuj_trasy_abdendriel_zachod.py": "1ce77a518de54f2774ea3121d8f761c76a344afb56f2ac3b62ac1abccb07ba15",
})
zmienione = [f for f, h in SHA.items() if hashlib.sha256((ROOTP / f).read_bytes()).hexdigest() != h]
sprawdz("h pliki v2, starych N/S, pelnej z9, mapy.json i generatory Z/ns/ns2 bajt w bajt jak przed v3 (sha256)", not zmienione, zmienione)
print(f"\n{sum(ok)}/{len(ok)} OK")
sys.exit(0 if all(ok) else 1)
