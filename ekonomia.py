"""Dziennik ekonomii bota (SPEC_ekonomia_lootu_1017): gold, uhy, exp, jedzenie, cenne dropy.

Plik logi/ekonomia-RRRRMMDD.jsonl pisze Telemetria (ta sama blokada i bezpieczniki co telemetria), ale bez
rotacji i bez sprzątania: dane służą do liczenia opłacalności spotów i do trenowania modeli. Tu: czyste
funkcje (regexy linii lootu, ceny NPC, składanie rekordu `lup`) i raport CLI. Tylko stdlib.

  python3 -I ekonomia.py [--katalog logi] [--dni 7]      # gold/h, uh/h, exp/h, zabicia/h per sesja i potwór
"""
import argparse
import glob
import json
import os
import re
import time
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

KATALOG = Path(__file__).resolve().parent
PRZEDMIOTY = KATALOG / "dane_tibia" / "przedmioty.json"
PROG_CENNY_GP = 100            # decyzja Karola 17.10: NPC płaci >= 100 gp = cenny przedmiot
PRZYPISANIE_S = 30.0           # lup przypisujemy do ostatniego zabicia nie starszego niż tyle sekund
TIK_S = 60.0                   # co tyle sekund rekord `tik` (mianownik czasu aktywnego)
WERSJA = 1
JEDZENIE = ("meat", "ham", "dragon ham", "fish", "cheese", "moldy cheese", "bread", "brown bread", "apple",
            "egg", "salmon", "northern pike", "carrot", "cookie", "cake", "grapes", "meat ball")

# linie logu loot.py: "loot: zebrano gold coin +12", "loot w walce: zebrano meat +1" i wersja bez ilości
RE_ZEBRANO = re.compile(r"^loot(?: w walce)?: zebrano (.+?)(?: \+(\d+)| \(ilość nieznana.*\))$")
RE_CENNE = re.compile(r"^loot(?: w walce)?: cenne zostały (.+)$")     # nowa linia z loot.py (patrz cenne_opis)
RE_LUP_WALKA = re.compile(r"^loot w walce: koniec$")   # znacznik z loot.py po zamknięciu zwłok w walce
RE_ZJEDZONO = re.compile(r"^loot(?: w walce)?: zjedzono ze zwłok: (.+)$")


def _norm(nazwa):
    n = str(nazwa).strip().lower()
    for art in ("a ", "an ", "the "):
        if n.startswith(art):
            return n[len(art):]
    return n


@lru_cache(maxsize=1)
def ceny_npc(sciezka=None):
    """{nazwa bez rodzajnika: cena sprzedaży do NPC w gp} z dane_tibia/przedmioty.json (brak pliku = {})."""
    try:
        kat = json.loads(Path(sciezka or PRZEDMIOTY).read_text(encoding="utf-8"))["kategorie"]
    except (OSError, ValueError, KeyError):
        return {}
    ceny = {}
    for lista in kat.values():
        for it in lista:
            c = it.get("cena_sprzedaz_do_npc")
            c = c.get("najczestsza") if isinstance(c, dict) else c
            if isinstance(c, (int, float)) and c > 0 and it.get("nazwa"):
                ceny[_norm(it["nazwa"])] = float(c)
    return ceny


def cena(nazwa, ceny=None):
    return (ceny if ceny is not None else ceny_npc()).get(_norm(nazwa))


def cenne(nazwy, ilosci=None, prog=PROG_CENNY_GP, ceny=None):
    """Z listy nazw (np. wynik['zostalo'] + wynik['zebrano']) wybiera te warte >= prog gp.
    Zwraca [{"n","ile","cena"}] (ile z `ilosci`, domyślnie liczba wystąpień), posortowane malejąco po cenie."""
    licz = Counter(nazwy)
    wynik = []
    for n, ile in licz.items():
        c = cena(n, ceny)
        if c is not None and c >= prog:
            wynik.append({"n": n, "ile": int((ilosci or {}).get(n, ile)), "cena": c})
    return sorted(wynik, key=lambda x: -x["cena"])


def cenne_opis(lista):
    """Treść linii logu dla loot.py: 'silver amulet x1 (50 gp), ...'. Pusta lista = ''."""
    return ", ".join(f"{x['n']} x{x['ile']} ({x['cena']:.0f} gp)" for x in lista)


def parsuj_cenne(tekst, ceny=None):
    """Odwrotność cenne_opis dla linii 'loot: cenne zostały …'."""
    wynik = []
    for czesc in str(tekst).split(", "):
        m = re.match(r"^(.+?) x(\d+) \((\d+(?:\.\d+)?) gp\)$", czesc.strip())
        if m:
            wynik.append({"n": m[1], "ile": int(m[2]), "cena": float(m[3])})
    return wynik


class Lup:
    """Akumulator jednych zwłok: linie logu => rekord `lup` (patrz SPEC). Czysta logika, bez I/O."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.zebrano = {}          # nazwa -> sztuk (None = ilość nieznana)
        self.nieznane = 0          # ile przeniesień bez znanej ilości
        self.jedzono = []
        self.cenne = []

    def pusty(self):
        return not (self.zebrano or self.nieznane or self.jedzono or self.cenne)

    def linia(self, txt):
        """Zwraca True, gdy linia należała do lootu (i została zużyta)."""
        m = RE_ZEBRANO.match(txt)
        if m:
            nazwa = _norm(m[1])
            if m[2] is None:
                self.nieznane += 1
                self.zebrano.setdefault(nazwa, 0)
            else:
                self.zebrano[nazwa] = self.zebrano.get(nazwa, 0) + int(m[2])
            return True
        m = RE_CENNE.match(txt)
        if m:
            self.cenne = parsuj_cenne(m[1])
            return True
        m = RE_ZJEDZONO.match(txt)
        if m:
            self.jedzono.append(_norm(m[1]))
            return True
        return False

    def rekord(self, zrodlo, wynik, ostatnie_zabicie=None, t=None):
        """ostatnie_zabicie: (nazwa, czas) albo None. gold=None, gdy zebrano monety bez znanej ilości."""
        gold = self.zebrano.get("gold coin", 0)
        gold_nieznany = self.nieznane > 0 and gold == 0 and "gold coin" in self.zebrano
        r = {"zrodlo": zrodlo, "wynik": wynik,
             "gold": None if gold_nieznany else int(gold),
             "zebrano": {n: k for n, k in self.zebrano.items() if n != "gold coin" and n not in JEDZENIE},
             "jedzenie": {n: k for n, k in self.zebrano.items() if n in JEDZENIE},
             "zjedzono": list(self.jedzono),
             "cenne": list(self.cenne)}
        # cenne mogły też zostać zebrane (np. po zmianie do_zebrania.txt): dopisz je z `zebrano`
        znane = {x["n"] for x in r["cenne"]}
        for x in cenne(list(self.zebrano), self.zebrano):
            if x["n"] not in znane:
                r["cenne"].append(x)
        if ostatnie_zabicie and t is not None and t - ostatnie_zabicie[1] <= PRZYPISANIE_S:
            r["n"], r["n_pewne"] = ostatnie_zabicie[0], True
        else:
            r["n"] = ostatnie_zabicie[0] if ostatnie_zabicie else None
            r["n_pewne"] = False
        return r


def wczytaj(katalog, dni=None):
    """Rekordy ze wszystkich plików ekonomia-*.jsonl (opcjonalnie tylko z ostatnich `dni` plików)."""
    pliki = sorted(glob.glob(os.path.join(str(katalog), "ekonomia-*.jsonl")))
    if dni:
        pliki = pliki[-dni:]
    rek = []
    for p in pliki:
        with open(p, encoding="utf-8") as f:
            for linia in f:
                try:
                    rek.append(json.loads(linia))
                except ValueError:
                    continue
    return rek


def raport(rek, tik_s=TIK_S):
    """Agregaty per sesja: czas aktywny (z `tik`), gold, uhy, exp, zabicia per potwór, cenne dropy.
    Czas aktywny = liczba `tik` * TIK_S (pauza/przerwa bota to brak tików)."""
    ses = defaultdict(lambda: {"tik": 0, "gold": 0, "gold_nieznany": 0, "lupy": 0, "uh": 0, "uh_rzuty": 0,
                               "uh_przerwane": 0, "exp": 0.0, "zab": Counter(), "jedzenie": Counter(),
                               "cenne": Counter(), "cenne_gp": 0.0, "t0": None, "spot": None})
    for r in rek:
        s = ses[(r.get("sesja"), r.get("pid"))]
        s["t0"] = r["t"] if s["t0"] is None else min(s["t0"], r["t"])
        s["spot"] = r.get("spot") or s["spot"]
        typ = r.get("typ")
        if typ == "tik":
            s["tik"] += 1
        elif typ == "lup":
            s["lupy"] += 1
            if r.get("gold") is None:
                s["gold_nieznany"] += 1
            else:
                s["gold"] += r["gold"]
            for n, k in (r.get("jedzenie") or {}).items():
                s["jedzenie"][n] += k or 0
            for x in r.get("cenne") or []:
                s["cenne"][x["n"]] += x["ile"]
                s["cenne_gp"] += x["ile"] * x["cena"]
        elif typ == "uh":
            if r.get("wynik") == "ok":
                s["uh"] += 1
                s["uh_rzuty"] += r.get("rzuty") or 1
            elif r.get("wynik") == "przerwane":
                s["uh_przerwane"] += 1
        elif typ == "zabicie":
            s["zab"][r.get("n")] += 1
        elif typ == "exp":
            s["exp"] += r.get("exp") or 0
    wynik = []
    for (sesja, pid), s in sorted(ses.items(), key=lambda x: x[1]["t0"] or 0):
        h = s["tik"] * tik_s / 3600.0
        if h <= 0:
            continue
        wynik.append({"sesja": sesja, "pid": pid, "start": s["t0"], "spot": s["spot"], "godz": round(h, 2),
                      "gold": s["gold"], "gold_h": round(s["gold"] / h), "gold_nieznany_lupow": s["gold_nieznany"],
                      "uh_h": round(s["uh_rzuty"] / h, 1), "uh_przerwane": s["uh_przerwane"],
                      "exp_h": round(s["exp"] / h), "zab_h": round(sum(s["zab"].values()) / h),
                      "zabicia": dict(s["zab"]), "jedzenie": dict(s["jedzenie"]),
                      "cenne": dict(s["cenne"]), "cenne_gp": round(s["cenne_gp"])})
    return wynik


def _wypisz(wiersze):
    if not wiersze:
        print("brak danych (jeszcze nic nie zapisano w ekonomia-*.jsonl)")
        return
    for w in wiersze:
        start = time.strftime("%d.%m %H:%M", time.localtime(w["start"])) if w["start"] else "?"
        top = ", ".join(f"{n} {k}" for n, k in sorted(w["zabicia"].items(), key=lambda x: -x[1])[:3])
        nieznany = f" (+{w['gold_nieznany_lupow']} lupów bez ilości)" if w["gold_nieznany_lupow"] else ""
        cenne_txt = f", cenne {w['cenne']} = {w['cenne_gp']} gp" if w["cenne"] else ""
        print(f"{start} {w['godz']:.1f}h [{w['spot'] or '-'}] {top} | gold {w['gold']} ({w['gold_h']}/h){nieznany}"
              f" | uh {w['uh_h']}/h (przerwane {w['uh_przerwane']}) | exp {w['exp_h']}/h | zab {w['zab_h']}/h{cenne_txt}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Raport ekonomii bota z logi/ekonomia-*.jsonl")
    ap.add_argument("--katalog", default=str(KATALOG / "logi"))
    ap.add_argument("--dni", type=int, default=None, help="tylko ostatnie N plików dziennych")
    a = ap.parse_args(argv)
    _wypisz(raport(wczytaj(a.katalog, a.dni)))


if __name__ == "__main__":
    main()
