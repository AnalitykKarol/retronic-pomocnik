#!/usr/bin/env python3
"""Dane serwisu Ab'Dendriel (24.10, Marinarra, runy HMM): bank, depo, backpack, blanki, wyjście. Z danych repo i mapy klienta, bez gry.

  python3 -I generuj_serwis_abdendriel.py [--wyjscie trasy/serwis_abdendriel.json] [--meta trasy/serwis_abdendriel.meta] [--sprawdz]

Czyta tylko pliki (zero gry): mapa/map74.otmm (mapa.py), dane_tibia/serwer74/npc_pelne.json (pozycje NPC i ceny),
trasy/abdendriel_bashira_shiriel.json i trasy/abdendriel_depo_trolle_nagranie.json (przejścia pięter nagrane przez Karola 24.10),
generuj_powrot_abdendriel.py (DEPO_STOI, KLUCZE_DRZWI: JEDNO źródło kluczy, to samo co wyprawa.PLANY_PK["klucze"] i cavebot w dojściu).
Wynik jest deterministyczny. `--sprawdz` nie zapisuje, tylko porównuje wynik z plikami (kod 1 = rozjazd).

Układ jak `serwis_thais.json` (czyta go serwis.py i panel.py) plus:
  drzwi_klucz    [{"pole": [x,y,z], "klucz": 2970}]: DWOJE drzwi z9 zamkniętych na klucz (mapa widzi je jako ścianę). Planer prowadzi trasę
                 przez nie, a serwis.przejdz_drzwi robi jak wypad._drzwi: krok, KLUCZ (Ctrl+klik na kluczu, klik na drzwiach), krok.
  obszar_miasta  [x0, y0, x1, y1, zmin, zmax]: tylko to jest „miasto” dla panelu i auto-refillu (wyjście serwisu leży w jaskini z9).
Kolejność: bank (Briasol), depo, backpack (Bashira), blanki (Shiriel), wyjście. BEZ kroku jedzenie (Karol 24.10: Marinarra nie chce jedzenia,
wydropi je z trolli), więc go tu nie ma (serwis robi `pomin_brakujace`).

Wyjście serwisu = pierwszy punkt dojścia abdendriel_z9_do_z10 (32675,31633,z9), czyli ZA obojgiem drzwi: serwis przechodzi je kluczem w drodze
powrotnej, a uruchom.sh liczy dojście od tego pola (dojście zna też te drzwi: cavebot, 24.10).

NIEZMIERZONE NA ŻYWO (wszystko w `.meta`, `niezmierzone_na_zywo`): że klucz 2970 pasuje do obojga drzwi; dialog wymiany u Briasola; dialog zakupu
u Bashiry i Shiriel; położenie depo (DEPO_STOI to ZASTĘPCZA decyzja be-dev z generuj_powrot_abdendriel.py) i strona skrzyni; schody W GÓRĘ z6->z7->z8
i z9->z8 (nagrania szły w drugą stronę); cała droga serwisu po mieście botem.
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
KATALOG = Path(__file__).resolve().parent
sys.path.insert(0, str(KATALOG))
TRASY = KATALOG / "trasy"
NPC_PLIK = KATALOG / "dane_tibia" / "serwer74" / "npc_pelne.json"
BASHIRA_SHIRIEL = TRASY / "abdendriel_bashira_shiriel.json"
DEPO_TROLLE = TRASY / "abdendriel_depo_trolle_nagranie.json"
WYJSCIE_DOJSCIA = TRASY / "abdendriel_z9_do_z10.json"

MIASTO = "abdendriel"
# Pola stania zmierzone na żywo 24.10 (dane_tibia/SKLEPY_abdendriel.md): bank 15:24:05 (Marianni, Karol stał przy NPC), Bashira 15:25:22, Shiriel 15:28:05.
STOI = {"bank": (32637, 31667, 8), "backpack": (32667, 31655, 8), "blanki": (32669, 31659, 6)}
NPC = {"bank": "Briasol", "backpack": "Bashira", "blanki": "Shiriel"}
OFERTA = {"backpack": "backpack", "blanki": "blank rune"}
KOLEJNOSC = ["bank", "depo", "backpack", "blanki", "wyjscie"]
# Stanowiska przy skrzyniach depo: sala z8 x 32679..32680, nieparzyste y 31683..31689; N i S od każdego pola to pola z flagą 4 (skrzynie/ściana).
# Pierwsze cztery w x=32679 (DEPO_STOI = (32679,31687,8) to ZASTĘPCZA decyzja be-dev), potem x=32680. serwis_akcje._otworz_depo próbuje wszystkich
# czterech sąsiadów, więc strona skrzyni nie jest tu założona.
DEPO_Y = (31687, 31685, 31683, 31689)
DEPO_X = (32679, 32680)
DEPO_SALA = [32679, 31683, 32682, 31689, 8]
# Obszar „miasto” dla panelu i auto-refillu: od banku (x 32635) do wschodu sali depo, piętra 6..9; bez jaskini z9 na północ od y 31646
# (tam jest wyjście serwisu i spot), bez z10.
OBSZAR_MIASTA = [32625, 31646, 32695, 31700, 6, 9]


def _t(p):
    return tuple(int(v) for v in p)


def wczytaj_npc(plik=NPC_PLIK):
    return {n["nazwa"]: n for n in json.loads(Path(plik).read_text())["npc"]}


def chodliwe(mapa, p):
    f = int(mapa.flagi(*p))
    return bool(f & 1) and not f & 4


def przejscia_pieter(punkty):
    """[(z, do)] dla kolejnych punktów nagrania o różnym piętrze."""
    pts = [_t(p) for p in punkty]
    return [(a, b) for a, b in zip(pts, pts[1:]) if a[2] != b[2]]


def zbuduj(mapa=None, npc=None):
    if mapa is None:
        import mapa as mapa_mod
        mapa = mapa_mod.mapa()
    npc = npc if npc is not None else wczytaj_npc()
    import generuj_powrot_abdendriel as GP

    depo = _t(GP.DEPO_STOI)
    wyjscie = _t(json.loads(WYJSCIE_DOJSCIA.read_text())[0])
    przystanki = {
        "bank": None,
        "depo": {"rodzaj": "depo", "npc": None, "stoi": list(depo),
                 "status": "ZASTĘPCZE położenie depo (generuj_powrot_abdendriel.DEPO_STOI = koniec trasy powrotu), NIEPOMIERZONE na żywo",
                 "zrodlo": "generuj_powrot_abdendriel.DEPO_STOI = pierwszy punkt nagrania abdendriel_depo_trolle_nagranie.json"},
    }
    for krok in ("bank", "backpack", "blanki"):
        n = npc[NPC[krok]]
        poz = [n["pozycja"]["x"], n["pozycja"]["y"], n["pozycja"]["z"]]
        wpis = {"rodzaj": "bank" if krok == "bank" else "kup", "npc": NPC[krok], "stoi": list(STOI[krok]), "npc_poz": poz}
        if krok != "bank":
            ceny = [q["cena"] for q in n["gracz_kupuje_od_npc"] if OFERTA[krok] in q["przedmiot"]]
            if not ceny:
                raise SystemExit(f"NPC {NPC[krok]} nie sprzedaje {OFERTA[krok]!r} wg danych serwera")
            wpis["oferta"], wpis["cena"] = OFERTA[krok], ceny[0]
        wpis["status"] = {
            "bank": "pole stania zmierzone na żywo 24.10 15:24:05; dialog wymiany u Briasola (jubiler) NIEZMIERZONY: serwis zakłada hi/change gold/liczba/yes jak u Ebenizera",
            "backpack": "pole stania zmierzone na żywo 24.10 15:25:22; dialog zakupu NIEZMIERZONY (oferta 'backpack' 20 gp jest w danych serwera)",
            "blanki": "pole stania zmierzone na żywo 24.10 15:28:05; dialog zakupu NIEZMIERZONY (oferta 'blank rune' 10 gp jest w danych serwera)",
        }[krok]
        przystanki[krok] = wpis
    przystanki = {k: przystanki[k] for k in ("bank", "depo", "backpack", "blanki")}

    # --- łączniki pięter ---
    zmierzone = przejscia_pieter(json.loads(BASHIRA_SHIRIEL.read_text())) + [
        pr for pr in przejscia_pieter(json.loads(DEPO_TROLLE.read_text())) if pr[0][2] == 8 and pr[1][2] == 9]
    laczniki, niezm_laczniki = [], []
    for a, b in zmierzone:
        laczniki.append({"z": list(a), "do": list(b), "status": "nagrane przez Karola 24.10"})
    # drogi powrotne (nagrania szły tylko w jedną stronę): schody z6->z7 i z7->z8 pod tym samym x, z9->z8 z planu powrotu (pole stania i lądowanie)
    odwrotne = [
        ((32682, 31688, 6), (32682, 31686, 7)),
        ((32682, 31686, 7), (32682, 31685, 8)),
        (_t(GP.STOI_SCHODY9), _t(GP.LAD8)),
    ]
    for a, b in odwrotne:
        laczniki.append({"z": list(a), "do": list(b), "status": "NIEZMIERZONE: strona powrotna przejścia (nagranie szło w drugą stronę)"})
        niezm_laczniki.append(f"{list(a)} -> {list(b)}")

    # --- stanowiska depo (ze sprawdzeniem mapy) ---
    stoiska = [(x, y, 8) for x in DEPO_X for y in DEPO_Y]
    for s in stoiska:
        if not chodliwe(mapa, s):
            raise SystemExit(f"stanowisko depo {s} nie jest chodliwe na mapie")
    if depo not in stoiska:
        raise SystemExit(f"DEPO_STOI {depo} poza listą stanowisk")
    stoiska.remove(depo)
    stoiska.insert(0, depo)

    for krok, p in list(STOI.items()) + [("wyjscie", wyjscie), ("depo", depo)]:
        if not chodliwe(mapa, _t(p)):
            raise SystemExit(f"{krok}: pole {tuple(p)} nie jest chodliwe na mapie")
    drzwi = []
    for pole, klucz in GP.KLUCZE_DRZWI:
        if chodliwe(mapa, _t(pole)):
            raise SystemExit(f"drzwi {tuple(pole)} nie są ścianą w mapie: dane do przejrzenia")
        drzwi.append({"pole": list(_t(pole)), "klucz": int(klucz)})

    return {
        "_opis": "Serwis Ab'Dendriel (24.10): generuj_serwis_abdendriel.py. Bez kroku jedzenie (Marinarra nie chce jedzenia). Kolejność edytowalna; "
                 "stoi = pole stania, depo.stoi = ZASTĘPCZE położenie depo (stanowiska przy skrzyniach w depo_stoiska). drzwi_klucz = dwoje drzwi z9 na klucz "
                 "(serwis.py: krok, klucz, krok); obszar_miasta = co panel i auto-refill uznają za miasto.",
        "miasto": MIASTO,
        "przystanki": przystanki,
        "wyjscie": list(wyjscie),
        "laczniki": laczniki,
        "depo_stoiska": [list(s) for s in stoiska],
        "depo_sala": DEPO_SALA,
        "drzwi_klucz": drzwi,
        "obszar_miasta": OBSZAR_MIASTA,
        "kolejnosc": KOLEJNOSC,
        "do_pomiaru": {"depo": "stań przy skrzyni depo, odczytaj pozycję, wpisz w generuj_powrot_abdendriel.DEPO_STOI i uruchom oba generatory z --zapisz"},
    }


def meta(dane):
    GP = __import__("generuj_powrot_abdendriel")
    return {
        "specjalne": [],
        "zrodla": {
            "bank_briasol": "npc_pelne.json (32635,31667,8); pole stania (32637,31667,8) odczyt z gry 24.10 15:24:05; dane_tibia/SKLEPY_abdendriel.md",
            "backpack_bashira": "npc_pelne.json (32669,31655,8); pole stania (32667,31655,8) odczyt z gry 24.10 15:25:22",
            "blanki_shiriel": "npc_pelne.json (32670,31657,6); pole stania (32669,31659,6) odczyt z gry 24.10 15:28:05",
            "depo": f"ZASTĘPCZE: generuj_powrot_abdendriel.DEPO_STOI = {list(GP.DEPO_STOI)}; sala z8 x 32679..32682, y 31683..31689 z nazwy nagrania depo_trolle i mapy klienta",
            "laczniki": "abdendriel_bashira_shiriel.json (z8->z7->z6, zmierzone 24.10) i abdendriel_depo_trolle_nagranie.json (z8->z9 przy (32655,31670,8))",
            "wyjscie": "pierwszy punkt trasy/abdendriel_z9_do_z10.json = (32675,31633,z9), za obojgiem drzwi",
            "drzwi_klucz": "generuj_powrot_abdendriel.KLUCZE_DRZWI = wyprawa.PLANY_PK['klucze'] (jedno źródło)",
        },
        "niezmierzone_na_zywo": [
            "że klucz 2970 (a copper key) pasuje do obojga drzwi (32658,31645,9) i (32655,31655,9)",
            "reakcja zamkniętych drzwi na zwykły krok (serwis robi: krok, klucz, krok; jak wypad._drzwi)",
            "dialog wymiany gold -> platinum u Briasola (serwis zakłada: hi, change gold, liczba, yes)",
            "dialog zakupu 'backpack' u Bashiry i 'blank rune' u Shiriel (oferty są w danych serwera)",
            "położenie depo (ZASTĘPCZE) i strona skrzyni przy stanowiskach",
            "schody w górę z6->z7->z8 i z9->z8 (nagrania szły w dół/w drugą stronę)",
            "cała droga serwisu po mieście botem (A* sprawdzony tylko offline na mapie)",
            "że krok backpack (zakup baga) nie wyrzuca klucza 2970 z plecaka",
        ],
        "kroki": {k: False for k in dane["przystanki"]},
    }


def tekst(obiekt):
    return json.dumps(obiekt, ensure_ascii=False, indent=1) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--wyjscie", default=str(TRASY / "serwis_abdendriel.json"))
    p.add_argument("--meta", default=str(TRASY / "serwis_abdendriel.meta"))
    p.add_argument("--sprawdz", action="store_true", help="nie zapisuj; porównaj z plikami (kod 1 = rozjazd)")
    a = p.parse_args(argv)
    import mapa as mapa_mod
    mp = mapa_mod.mapa()
    dane = zbuduj(mp)
    t_dane, t_meta = tekst(dane), tekst(meta(dane))
    if a.sprawdz:
        try:
            same = Path(a.wyjscie).read_text() == t_dane and Path(a.meta).read_text() == t_meta
        except OSError:
            same = False
        print("zgodne z plikami" if same else "ROZJAZD: wynik generatora różni się od plików")
        return 0 if same else 1
    Path(a.wyjscie).write_text(t_dane)
    Path(a.meta).write_text(t_meta)
    print(f"zapisano {a.wyjscie}: {len(dane['przystanki'])} przystanków, {len(dane['depo_stoiska'])} stanowisk depo, "
          f"{len(dane['laczniki'])} łączników, drzwi na klucz: {[tuple(d['pole']) for d in dane['drzwi_klucz']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
