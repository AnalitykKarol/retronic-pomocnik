#!/usr/bin/env python3
"""Dane serwisu Port Hope (25.10): TERAZ działa tylko krok DEPO (+ wyjście). Z mapy klienta i danych repo, bez gry.

  python3 -I generuj_serwis_port_hope.py [--wyjscie trasy/serwis_port_hope.json] [--meta trasy/serwis_port_hope.meta] [--sprawdz]

Czyta tylko pliki (zero gry): mapa/map74.otmm (mapa.py) i generuj_powrot_port_hope.py (DEPO = (32632,32743,z7), podał Karol 25.10: JEDNO źródło
położenia depo, to samo co końcówka tras ph_raty_z8_do_depo i port_hope_swamp_do_depo). Wynik jest deterministyczny. `--sprawdz` nie zapisuje,
tylko porównuje wynik z plikami (kod 1 = rozjazd).

Układ jak `serwis_thais.json` / `serwis_abdendriel.json` (czyta go serwis.py i panel.py):
  przystanki     TYLKO "depo" (stoi = pole przybycia DEPO). Bank, backpack, blanki i ham NIE są przystankami: serwis zna kroki wyłącznie z tego
                 pola, więc przy `--pomin-brakujace` (refill.sh) pomija je z wpisem w logu, a bez tej flagi kończy się czytelnym błędem startu.
  kolejnosc      ["depo", "wyjscie"].
  wyjscie        = DEPO: dojście na spot liczy uruchom.sh od pozycji postaci (jak Thais: wyjście = przybycie wyprawy), a trasy powrotu
                 ph_raty_z8_do_depo i port_hope_swamp_do_depo kończą się właśnie w DEPO.
  depo_stoiska   pola stania przy skrzyniach sali depo (z mapy klienta, patrz `skrzynie_depo`): pierwsze = najbliższe DEPO.
                 serwis_akcje._otworz_depo próbuje wszystkich czterech sąsiadów pola (N, E, S, W), więc strona skrzyni nie jest tu założona;
                 serwis.py i tak wybiera stanowisko po koszcie drogi od bieżącej pozycji (kolejność listy rozstrzyga tylko remisy: najpierw mniejsze x).
  depo_sala      [x0, y0, x1, y1, z]: cała sala ze skrzyniami = „przy depo” dla panelu i auto-refillu.
  obszar_miasta  [x0, y0, x1, y1, zmin, zmax]: budynek depo (piętra 5..7) i ulica przed nim; wejście do jaskini swamp i jaskinia ratów
                 (x >= 32650, z8) NIE są miastem.
  plan_do_pomiaru  OPIS (nie dane wykonywane): NPC i docelowa kolejność reszty refilu. Nic stąd nie trafia do `przystanki` ani `kolejnosc`.
  do_pomiaru     lista rzeczy do zmierzenia na żywo, zanim ktoś zamieni plan w przystanki (konwencja pliku jak w serwis_abdendriel.json).

NIEZMIERZONE NA ŻYWO (wszystko w `.meta`, `niezmierzone_na_zywo`): położenie skrzyń i strona skrzyni przy stanowiskach (wzór z mapy: kafle
nieprzechodnie o kolorze minimapy 129 w sali depo), wszystkie pola stania przy NPC, schody z6->z5, dialogi.
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
KATALOG = Path(__file__).resolve().parent
sys.path.insert(0, str(KATALOG))
TRASY = KATALOG / "trasy"

MIASTO = "port_hope"
KOLEJNOSC = ["depo", "wyjscie"]

# Sala ze skrzyniami depo (z7, prawa hala: DEPO leży w jej osi). Kafle skrzyń to kafle nieprzechodnie o kolorze minimapy 129 (szary);
# ściany sali mają kolor 186 (mapa klienta, podgląd mapa.podglad). Lewa hala (x 32620..32625) jest lustrzana, ale DEPO jej nie dotyczy.
SALA = (32629, 32737, 32634, 32748, 7)          # x0, y0, x1, y1, z
KOLOR_SKRZYNI = 129
# Kolejność prób w serwis_akcje.SASIEDZI_SKRZYNI: N, E, S, W (dx, dy).
SASIEDZI = ((0, -1), (1, 0), (0, 1), (-1, 0))
# Budynek depo (x ok. 32615..32645, y ok. 32733..32752, piętra 5..7) razem z ulicą przed nim; jaskinia ratów (z8) i swamp (y ~ 32612) poza.
OBSZAR_MIASTA = [32615, 32733, 32645, 32752, 5, 7]

# Plan reszty refilu. Źródło: dane_tibia/SKLEPY_port_hope.md (world-spawn.xml i npc/*.xml serwera jamera 7.6), NIEPOTWIERDZONE NA ŻYWO.
# Pozycja NPC (npc_poz) to centrum spawnu z danych (NPC chodzi w promieniu 1-2 pól), NIE pole stania gracza.
PLAN_NPC = {
    "bank": {"npc": "Ferks", "npc_poz": [32634, 32739, 6], "rola": "bank, wymiana gold -> platinum", "cena": None},
    "backpack": {"npc": "Perod", "npc_poz": [32634, 32740, 5], "rola": "backpack (id 3940)", "cena": 20},
    "blanki": {"npc": "Tandros", "npc_poz": [32622, 32740, 5], "rola": "blank rune (id 2260), sklep run (runes.lua)", "cena": 10},
    "ham": {"npc": "Clyde", "npc_poz": [32574, 32753, 7], "rola": "ham (id 2671), karczma", "cena": 8},
}
SCHODY_Z7_Z6 = [32629, 32749]                    # schody w górę z7 -> z6 (drugie: (32625,32749)), kafel „schody” w mapie klienta
KOLEJNOSC_DOCELOWA = [
    "depo (z7)", "schody z7 -> z6 (32629,32749)", "Ferks, bank (z6)", "schody z6 -> z5 (ok. 32626,32743, NIEZMIERZONE)",
    "Tandros, blanki (z5)", "Perod, backpack (z5)", "powrót w dół do depo (z7)", "Clyde, ham (z7, karczma na zachodzie)",
]
DO_POMIARU = [
    "pola stania przy Ferksie (z6), Perodzie i Tandrosie (z5), Clyde (z7): odczyt pozycji gracza przy NPC, jak w Ab'Dendriel",
    "schody z6 -> z5: dokładne kafle (ok. 32626,32743,z6; kafle (32626,32742) i (32630,32742) na z5 są „w dół”)",
    "dialog zakupu backpack u Peroda i blank rune u Tandrosa (ilość), dialog zakupu hama u Clyde",
    "dialog wymiany gold -> platinum u Ferksa",
    "wnęka Peroda niedostępna z sali na mapie: stać ok. (32633,32741,z5)",
    "które kafle sali depo naprawdę są skrzyniami i z której strony serwis_akcje._otworz_depo je otwiera",
]


def _t(p):
    return tuple(int(v) for v in p)


def chodliwe(mapa, p):
    f = int(mapa.flagi(*p))
    return bool(f & 1) and not f & 4


def skrzynie_depo(mapa):
    """Kafle skrzyń w sali (nieprzechodnie, kolor minimapy KOLOR_SKRZYNI), posortowane."""
    x0, y0, x1, y1, z = SALA
    wynik = []
    for y in range(y0 - 1, y1 + 2):
        for x in range(x0 - 1, x1 + 2):
            pole = mapa.pole(x, y, z)
            if pole and pole[0] & 1 and pole[0] & 4 and pole[1] == KOLOR_SKRZYNI:
                wynik.append((x, y, z))
    return sorted(wynik)


def stanowiska(mapa, depo):
    """Chodliwe pola sali z kaflem skrzyni na N/E/S/W; najpierw najbliższe DEPO, potem wg kolejności prób _otworz_depo (N, E, S, W)."""
    x0, y0, x1, y1, z = SALA
    skrz = set(skrzynie_depo(mapa))
    wynik = []
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            p = (x, y, z)
            if not chodliwe(mapa, p):
                continue
            kier = [i for i, (dx, dy) in enumerate(SASIEDZI) if (x + dx, y + dy, z) in skrz]
            if kier:
                wynik.append((max(abs(x - depo[0]), abs(y - depo[1])), kier[0], y, x, p))
    return [w[-1] for w in sorted(wynik)]


def zbuduj(mapa=None):
    if mapa is None:
        import mapa as mapa_mod
        mapa = mapa_mod.mapa()
    import generuj_powrot_port_hope as GP

    depo = _t(GP.DEPO)
    if not chodliwe(mapa, depo):
        raise SystemExit(f"depo {depo} nie jest chodliwe na mapie")
    x0, y0, x1, y1, z = SALA
    if not (x0 <= depo[0] <= x1 and y0 <= depo[1] <= y1 and depo[2] == z):
        raise SystemExit(f"depo {depo} poza salą {SALA}")
    stoiska = stanowiska(mapa, depo)
    if not stoiska:
        raise SystemExit("brak stanowisk przy skrzyniach w sali depo (mapa się zmieniła?)")
    ox0, oy0, ox1, oy1, oz0, oz1 = OBSZAR_MIASTA
    if not (ox0 <= depo[0] <= ox1 and oy0 <= depo[1] <= oy1 and oz0 <= depo[2] <= oz1):
        raise SystemExit("depo poza obszarem miasta")

    przystanki = {"depo": {"rodzaj": "depo", "npc": None, "stoi": list(depo),
                           "status": "pole depo podał Karol 25.10 (generuj_powrot_port_hope.DEPO); NIEPOMIERZONE na żywo: położenie skrzyń "
                                     "(wzór z mapy) i strona skrzyni przy stanowiskach",
                           "zrodlo": "generuj_powrot_port_hope.DEPO = koniec tras ph_raty_z8_do_depo i port_hope_swamp_do_depo"}}
    plan = {
        "_opis": "OPIS, nie dane wykonywane: kroki bank/backpack/blanki/ham Port Hope NIE są w `przystanki` ani w `kolejnosc`, serwis ich nie robi "
                 "(refill pomija je przez --pomin-brakujace). Pozycje NPC z dane_tibia/SKLEPY_port_hope.md (dane serwera), niepotwierdzone na żywo.",
        "status": "DO POMIARU",
        "npc": {k: dict(v) for k, v in PLAN_NPC.items()},
        "schody_z7_z6": list(SCHODY_Z7_Z6),
        "kolejnosc_docelowa": list(KOLEJNOSC_DOCELOWA),
    }
    return {
        "_opis": "Serwis Port Hope (25.10): generuj_serwis_port_hope.py. TERAZ tylko krok depo (+ wyjście); bank, backpack, blanki i ham czekają na "
                 "pomiary (plan_do_pomiaru, poza kolejnością). Kolejność edytowalna; stoi = pole przybycia DEPO, stanowiska przy skrzyniach w "
                 "depo_stoiska; obszar_miasta = co panel i auto-refill uznają za miasto.",
        "miasto": MIASTO,
        "przystanki": przystanki,
        "wyjscie": list(depo),
        "laczniki": [],
        "depo_stoiska": [list(s) for s in stoiska],
        "depo_sala": list(SALA),
        "obszar_miasta": list(OBSZAR_MIASTA),
        "kolejnosc": list(KOLEJNOSC),
        "plan_do_pomiaru": plan,
        "do_pomiaru": {"reszta_refilu": list(DO_POMIARU)},
    }


def meta(dane, mapa=None):
    if mapa is None:
        import mapa as mapa_mod
        mapa = mapa_mod.mapa()
    return {
        "specjalne": [],
        "zrodla": {
            "depo": "generuj_powrot_port_hope.DEPO = (32632,32743,z7), podał Karol 25.10",
            "depo_stoiska": f"mapa klienta (mapa.py): kafle skrzyń = nieprzechodnie o kolorze minimapy {KOLOR_SKRZYNI} w sali {list(SALA)}: "
                            f"{[list(s) for s in skrzynie_depo(mapa)]}; stanowiska = chodliwe pola z takim kaflem na N/E/S/W",
            "wyjscie": "= depo: dojście na spot liczy uruchom.sh od pozycji postaci (jak Thais)",
            "plan_do_pomiaru": "dane_tibia/SKLEPY_port_hope.md (world-spawn.xml, npc/*.xml, scripts/runes.lua serwera jamera 7.6)",
        },
        "niezmierzone_na_zywo": [
            "położenie skrzyń depo i strona skrzyni przy stanowiskach (wzór z mapy, serwis_akcje._otworz_depo próbuje N, E, S, W)",
            "czy pole DEPO (przybycie z tras powrotu) leży na tyle blisko skrzyń, że serwis dochodzi do stanowiska bez problemu",
            "wszystko z plan_do_pomiaru: pola stania, schody z6->z5, dialogi Ferks / Perod / Tandros / Clyde",
            "cała droga serwisu po mieście botem (A* sprawdzony tylko offline na mapie)",
        ],
        "kroki": {k: False for k in dane["przystanki"]},
    }


def tekst(obiekt):
    return json.dumps(obiekt, ensure_ascii=False, indent=1) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--wyjscie", default=str(TRASY / "serwis_port_hope.json"))
    p.add_argument("--meta", default=str(TRASY / "serwis_port_hope.meta"))
    p.add_argument("--sprawdz", action="store_true", help="nie zapisuj; porównaj z plikami (kod 1 = rozjazd)")
    a = p.parse_args(argv)
    import mapa as mapa_mod
    mp = mapa_mod.mapa()
    dane = zbuduj(mp)
    t_dane, t_meta = tekst(dane), tekst(meta(dane, mp))
    if a.sprawdz:
        try:
            same = Path(a.wyjscie).read_text() == t_dane and Path(a.meta).read_text() == t_meta
        except OSError:
            same = False
        print("zgodne z plikami" if same else "ROZJAZD: wynik generatora różni się od plików")
        return 0 if same else 1
    Path(a.wyjscie).write_text(t_dane)
    Path(a.meta).write_text(t_meta)
    print(f"zapisano {a.wyjscie}: {len(dane['przystanki'])} przystanek (depo), {len(dane['depo_stoiska'])} stanowisk depo, "
          f"pierwsze {dane['depo_stoiska'][0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
