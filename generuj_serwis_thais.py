#!/usr/bin/env python3
"""Dane serwisu Thais (K3, 21.10): przystanki, wnęki depo, drzwi sklepów. Z mapy klienta i danych repo, bez ręcznego nagrania.

  python3 -I generuj_serwis_thais.py [--wyjscie trasy/serwis_thais.json] [--meta trasy/serwis_thais.meta] [--sprawdz]

Czyta tylko pliki (zero gry): mapa/map74.otmm (mapa.py), dane_tibia/serwer74/npc_pelne.json (pozycje NPC, oferty),
trasy/wyprawa_sklepy.json (pola stania Frodo i Xodeta zmierzone na żywo 13-14.10 i nagrane dojścia, z nich drzwi),
trasy/troll_do_miasta.json (koniec = stoisko Gorna). Wynik jest deterministyczny (te same pliki -> te same bajty).
`--sprawdz` nie zapisuje, tylko porównuje wynik z plikami na dysku (kod wyjścia 1 = rozjazd).

Wyjście `trasy/serwis_thais.json` ma ten sam układ co `serwis_edron.json` (czyta je serwis.py i panel.py), plus pola
informacyjne (`status`, `zrodlo`, `drzwi`, `do_pomiaru`), których serwis.py nie wymaga. Źródło każdej współrzędnej i to,
czego nikt nie zmierzył na żywo, opisuje `trasy/serwis_thais.meta` i dane_tibia/SPEC_serwis_thais_1021.md.

Czego NIE robi: nie otwiera drzwi (Frodo i Xodet stoją w sklepach za drzwiami, które mapa widzi jako ścianę; serwis.py
odmawia kroków z polem `drzwi`), nie zgaduje dialogu banku Suzy (pole stania i słowa niezmierzone: `do_pomiaru`).
"""
import argparse
import json
import sys
from collections import deque
from pathlib import Path

sys.dont_write_bytecode = True
KATALOG = Path(__file__).resolve().parent
sys.path.insert(0, str(KATALOG))
TRASY = KATALOG / "trasy"
NPC_PLIK = KATALOG / "dane_tibia" / "serwer74" / "npc_pelne.json"
SKLEPY_PLIK = TRASY / "wyprawa_sklepy.json"
DO_MIASTA_PLIK = TRASY / "troll_do_miasta.json"

MIASTO = "thais"
# Punkt przybycia wyprawy do depo Thais: start trasy depo_troll_cave, S7 w generuj_trasy_thais_pn.py, pozycja z logu
# invincible 21.10 ~16:13 ("brak planu serwisu ... pozycja (32348, 32225, 7)"). To otwarta podłoga w sali depo, NIE wnęka.
PRZYBYCIE = (32348, 32225, 7)
# Pole stania przy skrzyni depo zmierzone na żywo 13.10 (wyprawa.POLE_ZLOZ_DEPO: Use na północ, skrzynia (32343,32225,7)).
DEPO_ZMIERZONE = (32343, 32226, 7)
# Prostokąt sali depo na z7 (mapa klienta): wnęki szukamy tylko tu, nie w całym mieście.
DEPO_X = (32338, 32358)
DEPO_Y = (32223, 32231)
DEPO_Z = 7
# NPC -> (klucz w wyprawa_sklepy.json, rola). Gorn nie ma wpisu w wyprawa_sklepy (stoisko = koniec trasy do miasta).
KROKI_NPC = {
    "jedzenie": {"npc": "Frodo", "sklep": "frodo", "trasa": "dojscie", "odwroc": False},
    "backpack": {"npc": "Gorn", "sklep": None},
    "blanki": {"npc": "Xodet", "sklep": "xodet", "trasa": "powrot", "odwroc": True},
}
# Kolejność domyślna: tylko kroki, które serwis.py umie dziś wykonać (bez drzwi). Pełną podaje `kolejnosc_po_drzwiach`.
KOLEJNOSC = ["depo", "backpack", "wyjscie"]
KOLEJNOSC_PO_DRZWIACH = ["depo", "jedzenie", "backpack", "blanki", "wyjscie"]
BANK = {"npc": "Suzy"}                              # bank Thais: dialog i pole stania niezmierzone


def _t(p):
    return tuple(int(v) for v in p)


def wczytaj_npc(plik=NPC_PLIK):
    return {n["nazwa"]: n for n in json.loads(Path(plik).read_text())["npc"]}


def chodliwe(mapa, x, y, z):
    """Pole widziane i bez flagi ściany (flaga 2 = schody/dziura/szum nie blokuje: tak liczy osiągalność test serwisu)."""
    f = int(mapa.flagi(x, y, z))
    return bool(f & 1) and not f & 4


def wneki_depo(mapa):
    """Pola stania w ślepych wnękach sali depo: chodliwe, a pola na N, W i E od nich nie, pole na S chodliwe. Skrzynia depo to
    pole nieprzechodnie na końcu wnęki (wzór ze zmierzonego pola DEPO_ZMIERZONE i z ośmiu wnęk Edronu). Tylko wnęki ze skrzynią
    na północy (dy = -1): tak jest w zmierzonym polu i tak otwiera `serwis_akcje._otworz_depo` w pierwszej kolejności."""
    z = DEPO_Z
    wynik = []
    for y in range(DEPO_Y[0], DEPO_Y[1] + 1):
        for x in range(DEPO_X[0], DEPO_X[1] + 1):
            if (chodliwe(mapa, x, y, z) and not chodliwe(mapa, x, y - 1, z) and not chodliwe(mapa, x - 1, y, z)
                    and not chodliwe(mapa, x + 1, y, z) and chodliwe(mapa, x, y + 1, z)):
                wynik.append((x, y, z))
    return sorted(wynik)


def wneki_depo_poludnie(mapa):
    """Jak wneki_depo, ale skrzynia na południu (dy = +1). Tylko informacyjnie: niezmierzone, serwis.py ich nie używa."""
    z = DEPO_Z
    return sorted((x, y, z) for y in range(DEPO_Y[0], DEPO_Y[1] + 1 + 1) for x in range(DEPO_X[0], DEPO_X[1] + 1)
                  if chodliwe(mapa, x, y, z) and not chodliwe(mapa, x, y + 1, z) and not chodliwe(mapa, x - 1, y, z)
                  and not chodliwe(mapa, x + 1, y, z) and chodliwe(mapa, x, y - 1, z))


def drzwi_na_trasie(punkty, mapa):
    """Pola trasy (z sąsiadem przed i po na tym samym piętrze), które mapa widzi jako ścianę: zamknięte drzwi nagrane przez gracza
    (ta sama reguła co wypad.drzwi_z_mapy, bez importu wypad: ten ciągnie cavebota i całą grę)."""
    pts = [_t(p) for p in punkty]
    wynik = []
    for i in range(1, len(pts) - 1):
        a, p, b = pts[i - 1], pts[i], pts[i + 1]
        if a[2] != p[2] or b[2] != p[2]:
            continue
        if mapa.przechodnie(*p) is False and p not in wynik:
            wynik.append(p)
    return wynik


def osiagalne(mapa, start, cele, otwarte=(), promien=(90, 70)):
    """Które z `cele` (pola na piętrze startu) są osiągalne z `start` chodząc po polach bez ściany (8 kierunków), z `otwarte` jako
    dodatkowymi chodliwymi polami (drzwi). Przeszukanie w prostokącie wokół startu."""
    start = _t(start)
    z = start[2]
    cele = {_t(c) for c in cele}
    otw = {_t(o)[:2] for o in otwarte}
    widziane, kol = {start[:2]}, deque([start[:2]])
    while kol:
        x, y = kol.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                q = (x + dx, y + dy)
                if q in widziane or abs(q[0] - start[0]) > promien[0] or abs(q[1] - start[1]) > promien[1]:
                    continue
                if not (chodliwe(mapa, q[0], q[1], z) or q in otw):
                    continue
                widziane.add(q)
                kol.append(q)
    return {c for c in cele if c[:2] in widziane}


def zbuduj(mapa=None, npc=None, sklepy=None, do_miasta=None):
    if mapa is None:
        import mapa as mapa_mod
        mapa = mapa_mod.mapa()
    npc = npc if npc is not None else wczytaj_npc()
    sklepy = sklepy if sklepy is not None else json.loads(SKLEPY_PLIK.read_text())["przystanki"]
    do_miasta = do_miasta if do_miasta is not None else json.loads(DO_MIASTA_PLIK.read_text())

    wneki = wneki_depo(mapa)
    if DEPO_ZMIERZONE not in wneki:
        raise SystemExit(f"wnęka zmierzona na żywo {DEPO_ZMIERZONE} nie wychodzi z mapy (mapa się zmieniła?): {wneki}")
    # zmierzona pierwsza, reszta od zachodu na wschód
    stoiska = [DEPO_ZMIERZONE] + [w for w in wneki if w != DEPO_ZMIERZONE]

    przystanki = {
        "depo": {
            "rodzaj": "depo", "npc": None, "stoi": list(PRZYBYCIE),
            "status": "przybycie z logu wyprawy; wnęki ze skrzyniami w depo_stoiska",
            "zrodlo": "start trasy depo_troll_cave = S7 w generuj_trasy_thais_pn.py = log invincible 21.10 16:13",
        },
    }
    zastrzezenia = {}
    for krok, opis in KROKI_NPC.items():
        n = npc[opis["npc"]]
        poz = (n["pozycja"]["x"], n["pozycja"]["y"], n["pozycja"]["z"])
        if opis["sklep"]:
            sk = sklepy[opis["sklep"]]
            stoi = _t(sk["stoi"])
            zrodlo = f"trasy/wyprawa_sklepy.json[{opis['sklep']}].stoi"
            status = "pole stania zmierzone na żywo (wyprawa: " + {"frodo": "13.10 hi/buy 3 ham/yes", "xodet": "14.10 buy 20 blank rune/yes"}[opis["sklep"]] + ")"
            trasa = [_t(p) for p in sk[opis["trasa"]]]
            if opis["odwroc"]:
                trasa = trasa[::-1]
            drzwi = drzwi_na_trasie(trasa, mapa)
        else:
            stoi = _t(do_miasta[-1])
            zrodlo = "ostatni punkt trasy/troll_do_miasta.json (stoisko Gorna, pole obok NPC)"
            status = "pole stania z nagrania trasy; dialog u Gorna niezmierzony (analogia: Beatrice w Edronie, ta sama oferta 'backpack' 20 gp)"
            drzwi = []
        oferta = {"frodo": "ham", "gorn": "backpack", "xodet": "blank rune"}[opis["npc"].lower()]
        ceny = [q["cena"] for q in n["gracz_kupuje_od_npc"] if oferta in q["przedmiot"]]
        if not ceny:
            raise SystemExit(f"NPC {opis['npc']} nie sprzedaje {oferta!r} wg danych serwera")
        wpis = {
            "rodzaj": "kup", "npc": opis["npc"], "stoi": list(stoi),
            "npc_poz": list(poz), "oferta": oferta, "cena": ceny[0],
            "status": status, "zrodlo": zrodlo,
        }
        if drzwi:
            wpis["drzwi"] = [list(d) for d in drzwi]
        przystanki[krok] = wpis
        bez = osiagalne(mapa, PRZYBYCIE, [stoi])
        z_drzwiami = osiagalne(mapa, PRZYBYCIE, [stoi], otwarte=drzwi)
        if drzwi and (bez or not z_drzwiami):
            raise SystemExit(f"{krok}: drzwi {drzwi} nie tłumaczą dojścia (bez drzwi {bool(bez)}, z drzwiami {bool(z_drzwiami)})")
        if not drzwi and not bez:
            raise SystemExit(f"{krok}: pole stania {stoi} nieosiągalne z {PRZYBYCIE} i brak drzwi na nagranej trasie")
        zastrzezenia[krok] = {"drzwi": bool(drzwi)}

    n = npc[BANK["npc"]]
    do_pomiaru = {
        "bank": {
            "npc": BANK["npc"], "npc_poz": [n["pozycja"]["x"], n["pozycja"]["y"], n["pozycja"]["z"]],
            "brak": ["pole stania", "drzwi/wejście do banku", "dialog (czy 'change gold' jak u Ebenizera w Edronie)"],
            "uwaga": "w danych serwera Suzy ma tylko tematy bye/farewell/job/name/time, jak Ebenizer; mapa nie pokazuje wejścia (zamknięty budynek)",
        },
        "rook": "patrz dane_tibia/SPEC_serwis_thais_1021.md, część Rook",
    }
    return {
        "_opis": "Serwis Thais (K3, 21.10): generuj_serwis_thais.py z mapy klienta i danych repo. Kolejność edytowalna; stoi = pole stania, "
                 "depo.stoi = przybycie wyprawy (stanowiska przy skrzyniach w depo_stoiska). Kroki z polem 'drzwi' wymagają obsługi drzwi.",
        "miasto": MIASTO,
        "przystanki": przystanki,
        "wyjscie": list(PRZYBYCIE),
        "laczniki": [],
        "depo_stoiska": [list(s) for s in stoiska],
        "kolejnosc": KOLEJNOSC,
        "kolejnosc_po_drzwiach": KOLEJNOSC_PO_DRZWIACH,
        "do_pomiaru": do_pomiaru,
    }


def meta(dane, mapa):
    """Plik .meta: pusta lista `specjalne` (jak przy trasach, żeby nic go nie pomyliło) i źródła współrzędnych."""
    poludnie = wneki_depo_poludnie(mapa)
    return {
        "specjalne": [],
        "zrodla": {
            "przybycie": "start trasy depo_troll_cave / S7 generuj_trasy_thais_pn.py / log invincible 21.10 16:13: " + str(list(PRZYBYCIE)),
            "depo_zmierzone": f"{list(DEPO_ZMIERZONE)}: wyprawa.POLE_ZLOZ_DEPO, Use na północ na skrzynię (32343,32225,7), 13.10",
            "depo_wnęki": "ślepe wnęki ze skrzynią na północy w sali depo z mapy klienta (mapa.py), prostokąt "
                          f"x {DEPO_X[0]}..{DEPO_X[1]}, y {DEPO_Y[0]}..{DEPO_Y[1]}, z{DEPO_Z}; poza zmierzoną tylko wzór z mapy",
            "depo_wnęki_południe_niezmierzone": [list(p) for p in poludnie],
            "frodo": "wyprawa_sklepy.json: pole stania zmierzone na żywo 13.10; drzwi z mapy ∩ nagrane dojście",
            "xodet": "wyprawa_sklepy.json: pole stania zmierzone na żywo 14.10; drzwi z mapy ∩ nagrany powrót",
            "gorn": "ostatni punkt troll_do_miasta.json, NPC (32377,32200,7) z npc_pelne.json; dialog niezmierzony",
            "bank_suzy": "npc_pelne.json (32320,32258,7); pole stania, wejście i dialog niezmierzone",
        },
        "niezmierzone_na_zywo": [
            "wnęki depo inne niż (32343,32226,7): że na ich północnym polu stoi skrzynia, nie ściana",
            "dialog 'backpack' u Gorna (oferta 20 gp jest w danych serwera)",
            "cała droga serwisu po mieście botem (A* sprawdzony tylko offline na mapie)",
            "bank Suzy: pole stania, wejście, dialog",
            "otwieranie drzwi sklepów w serwisie (kod nie istnieje)",
        ],
        "kroki": {k: ("drzwi" in v) for k, v in dane["przystanki"].items()},
    }


def tekst(obiekt):
    return json.dumps(obiekt, ensure_ascii=False, indent=1) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--wyjscie", default=str(TRASY / "serwis_thais.json"))
    p.add_argument("--meta", default=str(TRASY / "serwis_thais.meta"))
    p.add_argument("--sprawdz", action="store_true", help="nie zapisuj; porównaj z plikami (kod 1 = rozjazd)")
    a = p.parse_args(argv)
    import mapa as mapa_mod
    mp = mapa_mod.mapa()
    dane = zbuduj(mp)
    t_dane, t_meta = tekst(dane), tekst(meta(dane, mp))
    if a.sprawdz:
        same = Path(a.wyjscie).read_text() == t_dane and Path(a.meta).read_text() == t_meta
        print("zgodne z plikami" if same else "ROZJAZD: wynik generatora różni się od plików")
        return 0 if same else 1
    Path(a.wyjscie).write_text(t_dane)
    Path(a.meta).write_text(t_meta)
    print(f"zapisano {a.wyjscie}: {len(dane['przystanki'])} przystanków, {len(dane['depo_stoiska'])} stanowisk depo, "
          f"kroki z drzwiami: {[k for k, v in dane['przystanki'].items() if 'drzwi' in v]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
