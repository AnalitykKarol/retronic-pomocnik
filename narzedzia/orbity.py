#!/usr/bin/env python3
"""Skan orbit w telemetrii (SPEC_orbity_straznik_1020, punkt C): epizody „postać w ruchu, ale zamknięta w kilku polach”.

  python3 -I narzedzia/orbity.py                          # logi/ i instancje/*/logi/ tego checkoutu
  python3 -I narzedzia/orbity.py --katalog ~/Games/Retronic/pomocnik --dni 7
  python3 -I narzedzia/orbity.py --instancja kutangen --json
  python3 -I narzedzia/orbity.py logi/telemetria-20261015.jsonl --min-s 30 --pol 8

Wejście: pliki `telemetria-*.jsonl` (rekordy `probka`: t, poz [x,y,z], stan, sesja/pid; do kontekstu też `poscig_start`,
`poscig_koniec`, `wpadniecie*`). Czytane strumieniowo, linia po linii; w pamięci zostają tylko skrócone krotki próbek.
Domyślnie: `<katalog>/logi/` i `<katalog>/instancje/*/logi/`; `--katalog` wskazuje inny checkout (dane bywają tylko w głównym).

Epizod = ciąg próbek jednej sesji, bez stanu WALKA/LOOT, bez przerwy >= 20 s między próbkami, w którym zbiór odwiedzonych pól
(x,y,z) ma <= `--pol` elementów, trwa >= `--min-s` s i ma >= `--min-ruchow` zmian pozycji. Epizod startuje od najwcześniejszej
próbki, z której to się da zbudować, i kończy przy siódmym polu / walce / lootcie / przerwie.
Dla każdego epizodu: instancja, data i czas, piętro, róg obszaru, liczba pól, ruchy, rozkład stanów oraz „co tuż przed”
(do `--przed-s` s wstecz: pościg start/koniec, wpadnięcie, zmiana piętra między próbkami).
Wahadło: ta sama sekwencja >= `--min-cykl` (4) pól (kolejne powtórzenia tego samego pola zwinięte) powtórzona >= `--powt` (3)
razy z rzędu -> flaga `wahadlo` + długość cyklu. Cykl musi być pierwotny (ABAB to nie cykl 4). Cykl z dokładnie tych samych pól;
sekwencja pól pochodzi z próbek ~1/s, więc bardzo szybki marsz może gubić pola pośrednie.
Kolumna `zamierzone_proc` = udział próbek w stanach PAUZA/PRZERWA/JEDZENIE itp. (stanie z zamiaru — to nie orbita; tabela
oznacza epizody >= 50%). Czas: lokalny strefy komputera. Nic nie zapisuje, nic nie uruchamia.
"""
import argparse
import bisect
import collections
import datetime
import json
import re
import sys
from pathlib import Path

PRZERWA_S = 20.0
MAX_CYKL = 80
STANY_WALKI = ("WALKA", "LOOT")
# kopia ratunek.STANY_ZAMIERZONE (stoi z zamiaru, nie orbita) — tylko do kolumny „zamierzone”, nie wpływa na wykrywanie
STANY_ZAMIERZONE = ("PRZERWA", "PAUZA", "PAUZA_PK", "GRACZ", "JEDZENIE", "ML")
RE_DATA = re.compile(r"telemetria-(\d{8})")


def wczytaj(plik):
    """Strumieniowo: (próbki [(t, poz, stan, sesja)], zdarzenia [(t, typ, szczegół)]) posortowane po t."""
    probki, zdarzenia = [], []
    with open(plik, errors="ignore") as f:
        for linia in f:
            if '"probka"' in linia:
                pass
            elif '"poscig_' not in linia and '"wpadniecie' not in linia:
                continue
            try:
                d = json.loads(linia)
            except ValueError:
                continue
            typ, t = d.get("typ"), d.get("t")
            if t is None:
                continue
            if typ == "probka":
                poz = d.get("poz")
                if poz and len(poz) == 3:
                    probki.append((t, (poz[0], poz[1], poz[2]), d.get("stan"), d.get("sesja") or d.get("pid")))
            elif typ and (typ.startswith("poscig_") or typ.startswith("wpadniecie")):
                szczegol = d.get("cel") or d.get("powod") or d.get("co") or ""
                if typ == "poscig_koniec" and d.get("powod"):
                    szczegol = f"{d.get('cel') or ''} {d.get('powod')}".strip()
                zdarzenia.append((t, typ, str(szczegol)))
    probki.sort(key=lambda p: p[0])
    zdarzenia.sort(key=lambda e: e[0])
    return probki, zdarzenia


def epizody(pr, min_s, pol, min_ruchow):
    """Zwraca listę (i, j) — indeksy pierwszej i ostatniej próbki epizodu."""
    wyn, i, n = [], 0, len(pr)
    while i < n:
        if pr[i][2] in STANY_WALKI:
            i += 1
            continue
        pola = {pr[i][1]}
        j, ruchy, przez_limit = i, 0, False
        while j + 1 < n:
            nast = pr[j + 1]
            if nast[2] in STANY_WALKI or nast[3] != pr[i][3] or nast[0] - pr[j][0] >= PRZERWA_S:
                break
            if nast[1] not in pola and len(pola) >= pol:
                przez_limit = True
                break
            pola.add(nast[1])
            if nast[1] != pr[j][1]:
                ruchy += 1
            j += 1
        if pr[j][0] - pr[i][0] >= min_s and ruchy >= min_ruchow:
            wyn.append((i, j))
            i = j + 1
        elif przez_limit:
            i += 1
        else:
            # okno skończyło się granicą (walka/przerwa/sesja): każde późniejsze okno w tym bloku jest jego podzbiorem,
            # więc też nie spełni progów — przeskocz cały blok (bez tego długi bezruch kosztuje O(n^2))
            i = j + 1
    return wyn


def wahadlo(poz, min_cykl, powt):
    """Szuka cyklu pierwotnego długości >= min_cykl powtórzonego >= powt razy z rzędu w sekwencji pól (zwiniętej).
    Zwraca (długość_cyklu, liczba_powtórzeń) albo None; przy kilku kandydatach wybiera najkrótszy, który pokrywa
    >= 90% najdłuższego pokrycia (krótszy cykl wewnątrz dłuższego, np. 4 pola w cyklu 10, przegrywa; wielokrotność nie wygrywa)."""
    s = [p for k, p in enumerate(poz) if k == 0 or p != poz[k - 1]]
    kandydaci = []
    for dl in range(max(min_cykl, 2), min(len(s) // powt, MAX_CYKL) + 1):
        seria = dlugosc = start = 0
        for k in range(len(s) - dl):
            seria = seria + 1 if s[k] == s[k + dl] else 0
            if seria > dlugosc:
                dlugosc, start = seria, k - seria + 1
        if dlugosc >= (powt - 1) * dl and _pierwotny(s[start:start + dl]):
            kandydaci.append((dl, dlugosc + dl))
    if not kandydaci:
        return None
    prog = 0.9 * max(c[1] for c in kandydaci)
    dl, pokrycie = next(c for c in kandydaci if c[1] >= prog)
    return dl, pokrycie // dl


def _pierwotny(c):
    n = len(c)
    return not any(n % d == 0 and c == c[d:] + c[:d] for d in range(1, n))


def tuz_przed(pr, zdarzenia, zd_t, i, przed_s):
    """Co działo się do przed_s s przed startem epizodu (próbka i)."""
    t0 = pr[i][0]
    wyn = []
    k = bisect.bisect_left(zd_t, t0 - przed_s)
    while k < len(zdarzenia) and zdarzenia[k][0] <= t0:
        t, typ, szcz = zdarzenia[k]
        wyn.append({"t": t0 - t, "typ": typ, "szczegol": szcz})
        k += 1
    m = i
    while m > 0 and pr[m - 1][0] >= t0 - przed_s and pr[m - 1][3] == pr[i][3]:
        m -= 1
    for a in range(max(m, 1), i + 1):
        if pr[a][3] == pr[a - 1][3] and pr[a][1][2] != pr[a - 1][1][2]:
            wyn.append({"t": t0 - pr[a][0], "typ": "zmiana_pietra",
                        "szczegol": f"z{pr[a - 1][1][2]}->z{pr[a][1][2]} przerwa {pr[a][0] - pr[a - 1][0]:.1f}s"})
    wyn.sort(key=lambda e: -e["t"])
    if i > 0 and pr[i - 1][3] == pr[i][3]:
        wyn.append({"t": t0 - pr[i - 1][0], "typ": "poprzednia_probka", "szczegol": str(pr[i - 1][2])})
    return wyn


def etykieta(plik, korzen):
    sciezka = Path(plik).resolve()
    czesci = sciezka.parts
    if "instancje" in czesci:
        k = len(czesci) - 1 - czesci[::-1].index("instancje")
        if k + 1 < len(czesci) - 1:
            return czesci[k + 1]
    return "glowna"


def skanuj_plik(plik, korzen, a):
    pr, zd = wczytaj(plik)
    zd_t = [e[0] for e in zd]
    wyn = []
    for i, j in epizody(pr, a.min_s, a.pol, a.min_ruchow):
        seg = pr[i:j + 1]
        pola = {p[1] for p in seg}
        stany = collections.Counter(p[2] or "-" for p in seg)
        z = collections.Counter(p[1][2] for p in seg).most_common(1)[0][0]
        poz = [p[1] for p in seg]
        w = wahadlo(poz, a.min_cykl, a.powt)
        wyn.append({
            "instancja": etykieta(plik, korzen), "plik": Path(plik).name,
            "start": datetime.datetime.fromtimestamp(seg[0][0]).isoformat(timespec="seconds"),
            "t": seg[0][0], "czas_s": round(seg[-1][0] - seg[0][0], 1),
            "pietro": z, "pietra": sorted({p[2] for p in pola}),
            "rog": [min(p[0] for p in pola), min(p[1] for p in pola)],
            "rozmiar": [max(p[0] for p in pola) - min(p[0] for p in pola) + 1, max(p[1] for p in pola) - min(p[1] for p in pola) + 1],
            "pola": len(pola), "ruchy": sum(1 for k in range(1, len(poz)) if poz[k] != poz[k - 1]),
            "probki": len(seg), "stany": dict(stany),
            "zamierzone_proc": round(100 * sum(1 for p in seg if p[2] in STANY_ZAMIERZONE) / len(seg)),
            "wahadlo": bool(w), "cykl": w[0] if w else None, "powtorzen": w[1] if w else None,
            "przed": tuz_przed(pr, zd, zd_t, i, a.przed_s),
        })
    return wyn


def znajdz_pliki(a, korzen):
    if a.pliki:
        pliki = [Path(p) for p in a.pliki]
    else:
        pliki = sorted(korzen.glob("logi/telemetria-*.jsonl")) + sorted(korzen.glob("instancje/*/logi/telemetria-*.jsonl"))
    if a.instancja:
        pliki = [p for p in pliki if etykieta(p, korzen) == a.instancja]
    if a.dni:
        granica = (datetime.date.today() - datetime.timedelta(days=a.dni - 1)).strftime("%Y%m%d")
        pliki = [p for p in pliki if (RE_DATA.search(p.name) or [None, "99999999"])[1] >= granica]
    return pliki


def opis_przed(przed):
    czesci = []
    for e in przed:
        if e["typ"] == "poprzednia_probka":
            czesci.append(f"-{e['t']:.0f}s próbka {e['szczegol']}")
        else:
            czesci.append(f"-{e['t']:.0f}s {e['typ']}{(' ' + e['szczegol']) if e['szczegol'] else ''}")
    # zdarzeń pościgu bywa dużo; pokaż 4 ostatnie + wszystkie zmiany piętra/wpadnięcia
    waz = [c for c, e in zip(czesci, przed) if e["typ"] in ("zmiana_pietra", "poprzednia_probka") or e["typ"].startswith("wpadniecie")]
    pozostale = [c for c, e in zip(czesci, przed) if c not in waz][-4:]
    return "; ".join(sorted(waz + pozostale, key=lambda c: -int(re.match(r"-(\d+)s", c).group(1)))) or "-"


def tabela(wiersze):
    if not wiersze:
        print("Brak epizodów orbitowania.")
        return
    for w in wiersze:
        stany = " ".join(f"{k}:{v}" for k, v in sorted(w["stany"].items(), key=lambda kv: -kv[1]))
        wah = f" WAHADŁO cykl {w['cykl']} x{w['powtorzen']}" if w["wahadlo"] else ""
        print(f"{w['instancja']:<10} {w['start'].replace('T', ' ')} {w['czas_s'] / 60:5.1f} min  z{w['pietro']}  "
              f"od ({w['rog'][0]},{w['rog'][1]}) {w['rozmiar'][0]}x{w['rozmiar'][1]}  {w['pola']} pól  ruchów {w['ruchy']}{wah}"
              f"{'  [' + str(w['zamierzone_proc']) + '% stanów zamierzonych]' if w['zamierzone_proc'] >= 50 else ''}")
        print(f"    stany: {stany}")
        print(f"    tuż przed: {opis_przed(w['przed'])}")
    razem = sum(w["czas_s"] for w in wiersze) / 60
    print(f"\nEpizodów: {len(wiersze)}, z wahadłem: {sum(w['wahadlo'] for w in wiersze)}, łącznie {razem:.1f} min")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Skan orbit w telemetrii Retronic (SPEC_orbity_straznik_1020 C)")
    ap.add_argument("pliki", nargs="*", help="pliki telemetria-*.jsonl (domyślnie wszystkie z --katalog)")
    ap.add_argument("--katalog", default=str(Path(__file__).resolve().parent.parent), help="checkout z logi/ i instancje/*/logi/")
    ap.add_argument("--dni", type=int, default=0, help="tylko pliki z ostatnich N dni (po dacie w nazwie)")
    ap.add_argument("--instancja", help="tylko ta instancja ('glowna' = logi/)")
    ap.add_argument("--min-s", type=float, default=45)
    ap.add_argument("--pol", type=int, default=6, help="maks. liczba pól obszaru")
    ap.add_argument("--min-ruchow", type=int, default=8)
    ap.add_argument("--min-cykl", type=int, default=4, help="min. długość cyklu wahadła (pól)")
    ap.add_argument("--powt", type=int, default=3, help="min. liczba powtórzeń cyklu")
    ap.add_argument("--przed-s", type=float, default=60, help="jak daleko wstecz szukać „co tuż przed”")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    korzen = Path(a.katalog).expanduser().resolve()
    wiersze = []
    for p in znajdz_pliki(a, korzen):
        wiersze += skanuj_plik(p, korzen, a)
    wiersze.sort(key=lambda w: (w["t"], w["instancja"]))
    if a.json:
        json.dump(wiersze, sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        tabela(wiersze)
    return 0


if __name__ == "__main__":
    sys.exit(main())
