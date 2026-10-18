#!/usr/bin/env python3
"""Odtworzenie spotkań z graczami na spocie: co zrobiłby nowy kod (MIJANIE=1) vs co zrobił bot (F2, dane_tibia/SPEC_mijanie_graczy_1018.md).

OFFLINE, TYLKO ODCZYT: czyta logi/telemetria-RRRRMMDD.jsonl (src=mozg, typ=probka i zdarzenia unikanie_*), mapę klienta i trasy z repo.
Nic nie zapisuje poza raportem (--raport), nie dotyka bota, gry ani gniazda.

  python3 -I narzedzia/odtworz_mijanie.py [--logi KATALOG] [--wzorzec 'telemetria-2026101[5-8].jsonl'] [--raport PLIK.md] [--json PLIK.json]

Model (przybliżenie, nie nagranie kontrfaktyczne):
  - Spotkanie = ciągła obecność tego samego obcego gracza w widoku (przerwa <= PRZERWA_S) na spocie (piętro >= 8); obcy = nie nasza postać
    (nasze: wpisy dx=dy=0 z >= 100 próbek, czyli Mastafian, Sau Moreno, Ucho, Vermitor). Rodzaj: przechodzi (< 30 s w widoku),
    poluje (>= 30 s, rusza się), stoi (>= 30 s, rozrzut pozycji <= 3 pola).
  - Trasa = ta z trasy/*.json, po której chodził bot w oknie spotkania (>= 50% próbek IDZ w promieniu PROMIEN_TRASY = 2 pól od jej punktów); kierunek
    obiegu z kolejności odwiedzanych punktów. Spotkania bez dopasowanej trasy (patrol po miejscach, wypad, dojście) są policzone, ale
    nie odtwarzane.
  - Odtwarzanie: zegar 0,4 s (faktyczny okres ticka cavebota, mediana ruch_okno 0,40 s), próbki telemetrii co ~1 s są interpolowane
    liniowo (gracze) albo trzymane (stan). Gdy nagrany bot był w IDZ, nasz model chodzi sam po trasie (krok co KROK_S = 0,55 s, tempo
    z telemetrii: P75 1,7 pola/s) i podejmuje decyzje prawdziwym `unikanie.Unikanie.mijanie()` + `cavebot.Cavebot._mijanie_zastosuj()` na
    prawdziwej mapie (A* z mapa.py); w innych stanach (WALKA, LOOT, PRZERWA, ...) model przyjmuje nagraną pozycję i nic nie decyduje
    (walka ma pierwszeństwo). Mobów nie ma: walka jest tylko oknem, w którym stoimy tam, gdzie stał nagrany bot.
  - Metryki stare = z nagrania (zdarzenia unikanie_*, tor pozycji), nowe = z modelu. Zawrót = zmiana kierunku marszu o > 90 stopni
    (dot < 0 między kolejnymi przesunięciami), liczony na pozycjach co ~1 s tylko w IDZ.
"""
import argparse
import collections
import datetime
import glob
import json
import math
import os
import statistics
import sys
import types
import zlib

sys.dont_write_bytecode = True
KAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KAT)
os.environ.setdefault("RETRONIC_TESTY", "1")     # cavebot.py jako biblioteka: bez telemetrii i zapisów

PRZERWA_S = 30.0          # przerwa w widoku, po której gracz to nowe spotkanie
MARGINES_S = 15.0         # okno odtwarzania: spotkanie +- tyle s
TICK_S = 0.4              # okres ticka cavebota (ruch_okno: mediana okno_s / ticki = 0,40 s, 3577 okien 15-18.10)
PROMIEN_TRASY = 2         # bot idący "trasą" bywa tyle pól od jej punktów (walka, loot, pościg)
KROKI_KIERUNKU = 8        # kierunek obiegu z pierwszych tylu kroków nagranego bota w oknie spotkania
KROK_S = 0.55             # s na krok marszu w IDZ (telemetria: P75 1,7 pola/s)
STANY_SPOTU = ("IDZ", "WALKA", "LOOT", "PRZERWA")
WIDOK = (7, 5)
OBCY_PROG_PROBEK = 100    # wpis dx=dy=0 w tylu próbkach = nasza postać
OBOWIAZKOWE = (("Palandysz", "2026-10-18T13:31"), ("Palandysz", "2026-10-18T14:03"),
               ("Harley Queen", "2026-10-17T18:26"), ("Eliu", "2026-10-17T17:44"))
CHEB = lambda a, b: max(abs(a[0] - b[0]), abs(a[1] - b[1]))


# ---------------------------------------------------------------- wczytywanie ----
def znajdz_logi(arg, wzorzec="telemetria-*.jsonl"):
    """Pierwszy katalog z plikami telemetrii: --logi, $RETRONIC_LOGI, logi/ tego checkoutu, logi/ głównego checkoutu (../pomocnik)."""
    for k in (arg, os.environ.get("RETRONIC_LOGI"), os.path.join(KAT, "logi"), os.path.join(os.path.dirname(KAT), "pomocnik", "logi")):
        if k and os.path.isdir(k) and glob.glob(os.path.join(k, wzorzec)):
            return k
    raise SystemExit("brak katalogu logi/ z telemetrią (podaj --logi)")


def wczytaj(logi, wzorzec, do_t=None):
    """-> (próbki, zdarzenia) tylko src=mozg, posortowane po czasie. Próbka: t, poz, stan, obcy [(nazwa, x, y, z)], wlasny nick, sesja."""
    surowe_probki, zdarzenia = [], []
    for plik in sorted(glob.glob(os.path.join(logi, wzorzec))):
        with open(plik, encoding="utf-8") as f:
            for linia in f:
                try:
                    r = json.loads(linia)
                except ValueError:
                    continue
                if r.get("src") != "mozg" or (do_t is not None and r.get("t", 0) > do_t):
                    continue
                if r.get("typ") == "probka":
                    surowe_probki.append(r)
                elif str(r.get("typ", "")).startswith("unikanie_"):
                    zdarzenia.append(r)
    wlasne = collections.Counter(s["n"] for r in surowe_probki for s in r.get("stwory", [])
                                 if s.get("gracz") and s.get("dx") == 0 and s.get("dy") == 0)
    wlasne = {n for n, c in wlasne.items() if c >= OBCY_PROG_PROBEK}
    probki = []
    for r in surowe_probki:
        p = r["poz"]
        obcy = [(s["n"], p[0] + s["dx"], p[1] + s["dy"], p[2]) for s in r.get("stwory", [])
                if s.get("gracz") and (s["dx"], s["dy"]) != (0, 0) and s["n"] not in wlasne]
        probki.append({"t": r["t"], "poz": tuple(p), "stan": r.get("stan"), "obcy": obcy, "sesja": (r.get("pid"), r.get("sesja"))})
    probki.sort(key=lambda r: r["t"])
    zdarzenia.sort(key=lambda r: r["t"])
    return probki, zdarzenia, wlasne


def wczytaj_trasy():
    trasy = {}
    for plik in glob.glob(os.path.join(KAT, "trasy", "*.json")):
        try:
            d = json.load(open(plik, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, list) and len(d) >= 20 and all(isinstance(p, list) and len(p) == 3 and all(isinstance(v, int) for v in p) for p in d[:5]):
            nazwa = os.path.basename(plik)[:-5]
            if "depo" in nazwa or "miasta" in nazwa or "dojscie" in nazwa or "drzwi" in nazwa:
                continue                                 # trasy przejść / dojść: nie pętle spotów
            trasy[nazwa] = [tuple(p) for p in d]
    return trasy


# ---------------------------------------------------------------- spotkania ----
def spotkania(probki):
    """Ciągłe obecności obcych graczy (jedna sesja, jedna nazwa, przerwa <= PRZERWA_S), tylko spot (z >= 8, stan z STANY_SPOTU)."""
    po_sesji = collections.defaultdict(list)
    for r in probki:
        po_sesji[r["sesja"]].append(r)
    wyn = []
    for sesja, lista in po_sesji.items():
        biezace = {}
        for r in lista:
            for (n, x, y, z) in r["obcy"]:
                e = biezace.get(n)
                if e and r["t"] - e["ost"] <= PRZERWA_S:
                    e["ost"] = r["t"]
                    e["pkt"].append((r["t"], x, y, z))
                    e["stany"].append(r["stan"])
                else:
                    if e:
                        wyn.append(e)
                    biezace[n] = {"nazwa": n, "pierwszy": r["t"], "ost": r["t"], "pkt": [(r["t"], x, y, z)], "stany": [r["stan"]], "sesja": sesja}
        wyn.extend(biezace.values())
    spot = [e for e in wyn if e["pkt"][0][3] >= 8 and any(s in STANY_SPOTU for s in e["stany"])]
    for e in spot:
        d = e["ost"] - e["pierwszy"]
        xs, ys = [p[1] for p in e["pkt"]], [p[2] for p in e["pkt"]]
        rozrzut = max(max(xs) - min(xs), max(ys) - min(ys))
        e["rodzaj"] = "przechodzi" if d < 30 else ("stoi" if rozrzut <= 3 else "poluje")
        e["czas_s"] = d
    spot.sort(key=lambda e: e["pierwszy"])
    return spot, len(wyn)


def dopasuj_trase(e, probki_sesji, trasy):
    """(nazwa, udział, kierunek +1/-1) trasy, po której szedł bot w oknie spotkania, albo None."""
    okno = [r for r in probki_sesji if e["pierwszy"] - MARGINES_S <= r["t"] <= e["ost"] + MARGINES_S and r["stan"] == "IDZ"]
    if len(okno) < 3:
        return None
    najl = None
    for nazwa, pkt in trasy.items():
        zbior = set(pkt)
        udzial = sum(1 for r in okno if any((r["poz"][0] + dx, r["poz"][1] + dy, r["poz"][2]) in zbior
                                            for dx in range(-PROMIEN_TRASY, PROMIEN_TRASY + 1) for dy in range(-PROMIEN_TRASY, PROMIEN_TRASY + 1))) / len(okno)
        if najl is None or udzial > najl[1]:
            najl = (nazwa, udzial)
    if najl is None or najl[1] < 0.5:
        return None
    pkt = trasy[najl[0]]
    n = len(pkt)
    otwarta = pkt[0][2] != pkt[-1][2] or abs(pkt[0][0] - pkt[-1][0]) + abs(pkt[0][1] - pkt[-1][1]) > 3
    pozycje = {}
    for i, p in enumerate(pkt):
        pozycje.setdefault(p[:2], []).append(i)
    # dopasowanie próbek IDZ do indeksów trasy (Viterbi): pole bywa na trasie kilka razy, wybieramy spójny ciąg indeksów
    # (przeskok po indeksach <= 8 prawie za darmo, dalszy kosztuje 5), więc kierunek i start wynikają z sąsiednich próbek
    seria = []
    for r in okno:
        kand = [i for dx in range(-PROMIEN_TRASY, PROMIEN_TRASY + 1) for dy in range(-PROMIEN_TRASY, PROMIEN_TRASY + 1)
                for i in pozycje.get((r["poz"][0] + dx, r["poz"][1] + dy), []) if pkt[i][2] == r["poz"][2]]
        if kand:
            seria.append((r["t"], r["poz"], sorted(set(kand))))

    def delta(a, b):
        return (b - a) if otwarta else ((b - a + n // 2) % n) - n // 2

    if len(seria) < 3:
        return None
    koszt = [{i: (CHEB(pkt[i], seria[0][1]) * 0.5, None) for i in seria[0][2]}]
    for (t, poz, kand), (tp, _, _) in zip(seria[1:], seria):
        nowy = {}
        for j in kand:
            najl_i = min(koszt[-1], key=lambda i: koszt[-1][i][0] + (0.1 * abs(delta(i, j)) if abs(delta(i, j)) <= 8 else 5.0))
            c = koszt[-1][najl_i][0] + (0.1 * abs(delta(najl_i, j)) if abs(delta(najl_i, j)) <= 8 else 5.0) + CHEB(pkt[j], poz) * 0.5
            nowy[j] = (c, najl_i)
        koszt.append(nowy)
    j = min(koszt[-1], key=lambda i: koszt[-1][i][0])
    sciezka = []
    for k in range(len(koszt) - 1, -1, -1):
        sciezka.append(j)
        j = koszt[k][j][1]
    sciezka.reverse()
    deltas = [delta(a, b) for a, b in zip(sciezka, sciezka[1:]) if 0 < abs(delta(a, b)) <= 8]
    suma = sum(deltas)
    suma_start = sum(deltas[:KROKI_KIERUNKU])
    znak = suma_start if suma_start else suma
    return najl[0], najl[1], (-1 if znak < 0 else 1), otwarta, sciezka[0], {t: i for (t, _, _), i in zip(seria, sciezka)}


# ---------------------------------------------------------------- metryki ----
def zawroty(punkty_t):
    """Zawroty marszu w liście (t, (x, y)): kolejne różne pozycje a, b, c (odstępy <= 3 s) z przesunięciami o dot < 0 (zmiana kierunku o > 90 stopni),
    czyli krok w tył po kroku w przód. Pozycje ze skoków modelu (odstęp > 3 s albo > 3 pola) nie łączą się w zawrót. Zwraca czasy zawrotów.
    Ta miara na nagraniu daje ok. 3-4,5/min w tle i przy graczu polującym obok (specyfikacja: 4,15 i 3,7), więc jest zbliżona do tamtej."""
    pts = []
    for t, p in punkty_t:
        if not pts or p != pts[-1][1]:
            pts.append((t, p))
    wyn = []
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        if b[0] - a[0] > 3.0 or c[0] - b[0] > 3.0 or CHEB(a[1], b[1]) > 3 or CHEB(b[1], c[1]) > 3:
            continue
        v1 = (b[1][0] - a[1][0], b[1][1] - a[1][1])
        v2 = (c[1][0] - b[1][0], c[1][1] - b[1][1])
        if v1[0] * v2[0] + v1[1] * v2[1] < 0:
            wyn.append(b[0])
    return wyn


def czas_w_widoku(serie):
    """Sekundy, w których któryś obcy był w widoku (dx <= 7, dy <= 5). serie: [(t, poz, [(x, y), ...])] co ~1 s."""
    suma = 0.0
    for (t0, p0, o0), (t1, _, _) in zip(serie, serie[1:]):
        if t1 - t0 <= 3.0 and any(abs(x - p0[0]) <= WIDOK[0] and abs(y - p0[1]) <= WIDOK[1] for x, y in o0):
            suma += t1 - t0
    return suma


# ---------------------------------------------------------------- odtwarzanie ----
class Model:
    """Model świata do odtwarzania jednego spotkania: mapa klienta, znane pola i konfiguracja z cavebot.py."""
    def __init__(self):
        import cavebot  # noqa: PLC0415
        import mapa as mapa_mod  # noqa: PLC0415
        import unikanie  # noqa: PLC0415
        self.cavebot, self.unikanie = cavebot, unikanie
        self.mapa = mapa_mod.Mapa()
        self.K = mapa_mod._K
        self.znane = {}
        try:
            for p in json.load(open(os.path.join(KAT, "znane_pola.json"), encoding="utf-8")):
                self.znane.setdefault(p[2], set()).add(p[0] * self.K + p[1])
        except (OSError, ValueError):
            pass
        self.konf0 = {k: getattr(cavebot, k) for k in dir(cavebot) if k.startswith(("UNIKANIE", "MIJANIE"))}

    def konf(self, mijanie):
        k = dict(self.konf0, MIJANIE=1 if mijanie else 0, UNIKANIE_TOR=1, UNIKANIE_PRZERWA=1)    # jak na żywo od 17.10 23:21
        return types.SimpleNamespace(**k)

    def droga(self, start, cel, blok):
        z = start[2]
        zaj = [p for p in blok]
        return self.mapa.droga(start, cel, zaj, 0, False, limit=6000, znane=self.znane.get(z, set()))

    def wolne(self, p):
        f = self.mapa.flagi(p[0], p[1], p[2])
        return bool((f & 1 or p[0] * self.K + p[1] in self.znane.get(p[2], ())) and not f & (4 | 2))


def odtworz(model, e, probki_sesji, trasa_info, trasy, mijanie=True):
    """Odtwarza spotkanie e: zwraca słownik z decyzjami, trasą modelu i miarami. Zob. docstring modułu o przybliżeniach."""
    nazwa_trasy, _, kierunek, otwarta, i0, mapa_idx = trasa_info
    pkt = list(trasy[nazwa_trasy])
    rev = kierunek < 0                                  # czy lista modelu jest odwrócona względem pliku trasy (zmienia się po odwróceniu obiegu)
    if rev:
        pkt.reverse()
        i0 = len(pkt) - 1 - i0 if i0 is not None else None
    t0, t1 = e["pierwszy"] - MARGINES_S, e["ost"] + MARGINES_S
    okno = [r for r in probki_sesji if t0 <= r["t"] <= t1]
    if len(okno) < 3:
        return None
    z = okno[0]["poz"][2]
    zegar = [okno[0]["t"]]
    zd = []
    u = model.unikanie.Unikanie(model.konf(mijanie), zegar=lambda: zegar[0], log=lambda *a: None,
                                zdarzenie=lambda typ, **d: zd.append((zegar[0], typ, d)), powiadom=lambda *a, **k: None)
    u.czat_spot = None
    poz = list(okno[0]["poz"][:2])
    # indeks początkowy: najbliższy punkt trasy, a gdy stoimy na nim - następny
    k0 = i0 if i0 is not None and CHEB(pkt[i0], poz) <= 1 and okno[0]["stan"] == "IDZ" else \
        min(range(len(pkt)), key=lambda i: (pkt[i][2] != z, CHEB(pkt[i], poz)))
    cb = types.SimpleNamespace(punkty=pkt, idx=(k0 + 1) % len(pkt) if tuple(pkt[k0][:2]) == tuple(poz) else k0,
                               klik_j=None, klik_cel=None, nieudane=0, pominiete=0, zablokowane={}, trasa_droga=None, utk_okno=None,
                               pauza=lambda *a: None)
    obcy_teraz = {}

    def zajete(p):
        return any((x, y) == tuple(p) for x, y in obcy_teraz.values())

    def krok_do(cel):
        c = tuple(cel[:2])
        if CHEB(c, poz) == 1 and model.wolne((c[0], c[1], z)) and not zajete(c):
            poz[0], poz[1] = c
            return True
        return False
    cb.krok_do = krok_do
    seria_model = []
    ostatni_krok = -1e9
    po_snapie = False
    j = 0
    T = okno[0]["t"]
    stand = 0.0
    decyzje = collections.Counter()
    while T <= t1:
        while j + 1 < len(okno) and okno[j + 1]["t"] <= T:
            j += 1
        a = okno[j]
        b = okno[j + 1] if j + 1 < len(okno) else None
        # gracze: interpolacja liniowa między sąsiednimi próbkami (<= 3 s), inaczej trzymamy do 1,2 s
        obcy_teraz.clear()
        A = {n: (x, y) for n, x, y, zz in a["obcy"]}
        B = {n: (x, y) for n, x, y, zz in b["obcy"]} if b else {}
        for n, (x, y) in A.items():
            if b and b["t"] - a["t"] <= 3.0 and n in B:
                f = (T - a["t"]) / max(b["t"] - a["t"], 1e-6)
                obcy_teraz[n] = (round(x + (B[n][0] - x) * f), round(y + (B[n][1] - y) * f))
            elif T - a["t"] <= 1.2:
                obcy_teraz[n] = (x, y)
        lista = [{"id": zlib.crc32(n.encode()), "nazwa": n, "gracz": True, "x": x, "y": y, "z": z, "hp": 100} for n, (x, y) in obcy_teraz.items()]
        zegar[0] = T
        stan = a["stan"]
        idz = stan == "IDZ"
        if not idz:
            poz[0], poz[1] = a["poz"][0], a["poz"][1]      # model przyjmuje nagraną pozycję (walka, loot, przerwa, ...)
            po_snapie = True
        elif po_snapie:
            # po skoku na nagraną pozycję: kierunek obiegu zostaje (nowa decyzja trzymana), a cel to punkt trasy tuż za nagraną pozycją w tym
            # kierunku; indeks bierzemy z dopasowania nagrania do trasy (pole bywa na trasie kilka razy), inaczej najbliższy punkt
            n_ = len(cb.punkty)
            if a["t"] in mapa_idx:
                cur = (n_ - 1 - mapa_idx[a["t"]]) if rev else mapa_idx[a["t"]]
                cb.idx = (cur + 1) % n_
            else:
                k = min(range(n_), key=lambda i: (cb.punkty[i][2] != z, CHEB(cb.punkty[i], poz)))
                cb.idx = (k + 1) % n_ if tuple(cb.punkty[k][:2]) == tuple(poz) else k
            po_snapie = False
        u.obserwuj(lista, (poz[0], poz[1], z), "__ja__")
        akcja = None
        if idz:
            poz3 = (poz[0], poz[1], z)
            r = u.mijanie(poz3, cb.punkty, cb.idx, lambda s, c, bl: model.droga(s, c, bl), wolne_fn=lambda p: model.wolne(p),
                          otwarta=otwarta, w_walce=False) if mijanie else None
            if r is not None:
                akcja = r.akcja
                decyzje[r.akcja] += 1
            zuzyty = model.cavebot.Cavebot._mijanie_zastosuj(cb, poz3, r) if r is not None else False
            if r is not None and r.akcja == "odwroc":
                rev = not rev
            if r is not None and r.akcja == "stoj":
                stand += TICK_S
            if not zuzyty and T - ostatni_krok >= KROK_S:
                n = len(cb.punkty)
                for dalej in range(min(10, n)):
                    kk = cb.idx + dalej
                    if not otwarta or kk < n:
                        if tuple(cb.punkty[kk % n][:2]) == tuple(poz):
                            cb.idx = kk + 1
                            break
                if otwarta and cb.idx >= n:
                    cb.punkty.reverse()
                    cb.idx = 1
                    rev = not rev
                cb.idx %= n
                cel = cb.punkty[cb.idx]
                d = model.droga((poz[0], poz[1], z), cel[:2], [(x, y, z) for x, y in obcy_teraz.values()]) if cel[2] == z else None
                if d:
                    if krok_do(d[0]):
                        ostatni_krok = T
            elif zuzyty and r is not None and r.akcja == "marsz":
                ostatni_krok = T
        # próbkowanie co ~1 s do miar
        if not seria_model or T - seria_model[-1][0] >= 1.0:
            seria_model.append((T, (poz[0], poz[1]), idz, list(obcy_teraz.values())))
        T += TICK_S
    # miary
    track_nowy = [(t, p) for t, p, idz, _ in seria_model if idz]
    track_stary = [(r["t"], r["poz"][:2]) for r in okno if r["stan"] == "IDZ"]
    w_widoku_nowy = czas_w_widoku([(t, p, o) for t, p, _, o in seria_model])
    w_widoku_stary = czas_w_widoku([(r["t"], r["poz"][:2], [(x, y) for _, x, y, _z in r["obcy"]]) for r in okno])
    ev = [(t, typ, d) for t, typ, d in zd if typ.startswith("mijanie_")]
    seria_stara = [(r["t"], r["poz"][:2], [(x, y) for _, x, y, _z in r["obcy"]]) for r in okno]
    return {"zd": ev, "decyzje": dict(decyzje), "seria_stara": seria_stara, "track_nowy": track_nowy, "track_stary": track_stary, "postoj_s": stand,
            "zawroty_nowe": zawroty(track_nowy), "zawroty_stare": zawroty(track_stary), "okno": (t0, t1),
            "w_widoku_nowy": w_widoku_nowy, "w_widoku_stary": w_widoku_stary, "seria_model": seria_model, "odwroty": sum(
                1 for _, typ, d in ev if typ == "mijanie_kierunek" and d.get("akcja") == "odwrocenie"),
            "skroty": sum(1 for _, typ, d in ev if typ == "mijanie_kierunek" and d.get("akcja") == "skrot"),
            "przejscia": sum(1 for _, typ, d in ev if typ == "mijanie_przejscie" and d.get("etap") == "start")}


# ---------------------------------------------------------------- całość ----
def czas_txt(t):
    return datetime.datetime.fromtimestamp(t).strftime("%d.%m %H:%M:%S")


def stare_zdarzenia(e, zdarzenia):
    """Zdarzenia unikanie_* nagranego bota w oknie spotkania (ta sama sesja)."""
    t0, t1 = e["pierwszy"] - 5.0, e["ost"] + 15.0
    return [z for z in zdarzenia if t0 <= z["t"] <= t1 and (z.get("pid"), z.get("sesja")) == e["sesja"]]


def analizuj(probki, zdarzenia, model, trasy, log=print):
    po_sesji = collections.defaultdict(list)
    for r in probki:
        po_sesji[r["sesja"]].append(r)
    spot, wszystkich = spotkania(probki)
    wyniki = []
    for i, e in enumerate(spot):
        stare = stare_zdarzenia(e, zdarzenia)
        typy = collections.Counter(z["typ"] for z in stare)
        info = dopasuj_trase(e, po_sesji[e["sesja"]], trasy)
        w = {"e": e, "stare": typy, "stare_zd": stare, "trasa": info, "nowe": None}
        if info is not None:
            try:
                w["nowe"] = odtworz(model, e, po_sesji[e["sesja"]], info, trasy)
                w["kontrola"] = odtworz(model, e, po_sesji[e["sesja"]], info, trasy, mijanie=False)      # ten sam model bez decyzji mijania
                w["po_dec"] = czas_po_decyzji(w)
            except Exception as ex:                     # jedno spotkanie nigdy nie przerywa całości
                w["blad"] = repr(ex)
        wyniki.append(w)
        if (i + 1) % 20 == 0:
            log(f"  odtworzono {i + 1}/{len(spot)}")
    return wyniki, wszystkich


def czas_po_decyzji(w):
    """(stary_s, nowy_s): sekundy w widoku obcego od pierwszej decyzji (stary: pierwszy unikanie_punkt albo unikanie_start; nowy: pierwsza zmiana
    kierunku albo ustąpienie) do końca okna. None, gdy któraś strona decyzji nie podjęła."""
    n = w["nowe"]
    t_nowy = next((t for t, typ, d in n["zd"] if typ == "mijanie_kierunek" or (typ == "mijanie_przejscie" and d.get("etap") == "start")), None)
    stare = [z["t"] for z in w["stare_zd"] if z["typ"] == "unikanie_punkt"] or [z["t"] for z in w["stare_zd"] if z["typ"] == "unikanie_start"]
    if t_nowy is None or not stare:
        return None
    po = lambda seria, t0: czas_w_widoku([x for x in seria if x[0] >= t0])
    return po(n["seria_stara"], stare[0]), po([(t, p, o) for t, p, _, o in n["seria_model"]], t_nowy)


def tlo_zawrotow(probki, spot):
    """Zawroty na minutę w IDZ poza spotkaniami (+- MARGINES_S) - tło."""
    zajete = [(e["pierwszy"] - MARGINES_S, e["ost"] + MARGINES_S, e["sesja"]) for e in spot]
    po_sesji = collections.defaultdict(list)
    for r in probki:
        if r["stan"] == "IDZ" and r["poz"][2] >= 8:
            po_sesji[r["sesja"]].append(r)
    suma_z, suma_s = 0, 0.0
    for sesja, lista in po_sesji.items():
        wolne = [r for r in lista if not any(a <= r["t"] <= b and s == sesja for a, b, s in zajete)]
        seg, ostatni = [], None
        for r in wolne:
            if ostatni is not None and r["t"] - ostatni > 3.0:
                if len(seg) > 8:
                    suma_z += len(zawroty([(x["t"], x["poz"][:2]) for x in seg]))
                    suma_s += seg[-1]["t"] - seg[0]["t"]
                seg = []
            seg.append(r)
            ostatni = r["t"]
        if len(seg) > 8:
            suma_z += len(zawroty([(x["t"], x["poz"][:2]) for x in seg]))
            suma_s += seg[-1]["t"] - seg[0]["t"]
    return suma_z / (suma_s / 60.0) if suma_s else float("nan"), suma_s


def pct(a, b):
    return f"{100.0 * a / b:.0f}%" if b else "-"


def mediana(v):
    return f"{statistics.median(v):.1f}" if v else "-"


def zawroty_na_min(ws, klucz_nowe="nowe", pole="zawroty_nowe"):
    """(zawroty, minuty IDZ) z listy wyników; klucz_nowe: "nowe" (model z mijaniem) albo "kontrola" (model bez)."""
    z = sum(len(w[klucz_nowe][pole]) for w in ws)
    min_ = sum(len(w[klucz_nowe]["track_nowy" if pole == "zawroty_nowe" else "track_stary"]) for w in ws) / 60.0
    return z, min_


def podsumowanie(wyniki, tlo):
    """Sekcja "Wynik w skrócie" - te same liczby co tabele niżej, zebrane pod zadane miary specyfikacji (generowana, nie ręczna)."""
    od = [w for w in wyniki if w["nowe"]]
    pr = [w for w in od if w["e"]["rodzaj"] == "przechodzi"]
    po = [w for w in od if w["e"]["rodzaj"] in ("poluje", "stoi")]
    bez = lambda ws: sum(1 for w in ws if not (w["nowe"]["odwroty"] or w["nowe"]["skroty"] or w["nowe"]["przejscia"]))
    bez_start = sum(1 for w in pr if not w["stare"].get("unikanie_start"))
    bez_punkt = sum(1 for w in pr if not (w["stare"].get("unikanie_punkt") or w["stare"].get("unikanie_blokada")))
    L = ["## Wynik w skrócie (model, nie gra)", ""]
    L.append(f"- **Przechodnie bez zmiany planu** (cel >= 80%): model {bez(pr)}/{len(pr)} = **{pct(bez(pr), len(pr))}**; nagrany bot: "
             f"{bez_start}/{len(pr)} = {pct(bez_start, len(pr))} bez `unikanie_start`, {bez_punkt}/{len(pr)} = {pct(bez_punkt, len(pr))} bez zmiany punktu trasy "
             f"(specyfikacja podaje 21%, inna definicja spotkania).")
    zs, ms = zawroty_na_min(po, "nowe", "zawroty_stare")
    zn, mn = zawroty_na_min(po, "nowe", "zawroty_nowe")
    zk, mk = zawroty_na_min(po, "kontrola", "zawroty_nowe")
    if ms and mn and mk:
        L.append(f"- **Zawroty na minutę przy graczu polującym/stojącym obok** (cel: nie więcej niż tło): nagrany bot {zs / ms:.1f}/min ({zs} w {ms:.0f} min IDZ), "
                 f"model z mijaniem {zn / mn:.1f}/min ({zn}), kontrola modelu bez mijania {zk / mk:.1f}/min ({zk}), tło poza spotkaniami {tlo:.1f}/min.")
    dec = [w["po_dec"] for w in od if w.get("po_dec")]
    L.append(f"- **Czas w widoku obcego od pierwszej decyzji** (miara nowa; spotkania z decyzją po obu stronach: {len(dec)}): nagrany bot {sum(a for a, _ in dec):.0f} s, "
             f"model {sum(b for _, b in dec):.0f} s.")
    ust = sum(w["nowe"]["przejscia"] for w in od)
    L.append(f"- **Ustępowanie przejścia** (wąski korytarz, gracz idzie na nas, widzimy go): w {len(od)} odtworzonych spotkaniach model ustąpił {ust} raz(y); "
             f"nagrania zawierają mało takich sytuacji, więc ta część jest sprawdzona głównie testami syntetycznymi (`testy/test_mijanie.py`, korytarz z wnęką), nie nagraniami.")
    L.append("- **Dreptanie przy graczu**: model nie ma `_wiggle`; postoje powstają tylko przy ustępowaniu (suma postoju w modelu: "
             f"{sum(w['nowe']['postoj_s'] for w in od):.0f} s).")
    L.append("")
    L.append("Spotkania obowiązkowe (szczegóły w sekcji niżej):")
    L.append("")
    L.append("| Spotkanie | Rodzaj | Stary kod (zdarzenia) | Nowy kod (model) | Zawroty stary/nowy | W widoku stary/nowy |")
    L.append("|---|---|---|---|---|---|")
    for (nick, kiedy) in OBOWIAZKOWE:
        t_ref = datetime.datetime.strptime(kiedy, "%Y-%m-%dT%H:%M").timestamp()
        for w in [w for w in wyniki if w["e"]["nazwa"] == nick and abs(w["e"]["pierwszy"] - t_ref) <= 150]:
            stary = ", ".join(f"{k.replace('unikanie_', '')}×{v}" for k, v in sorted(w["stare"].items())) or "-"
            n = w["nowe"]
            if n:
                dec_t = [f"{typ.replace('mijanie_', '')}:{d.get('akcja') or d.get('etap')}" for _, typ, d in n["zd"] if typ in ("mijanie_kierunek", "mijanie_przejscie")]
                L.append(f"| {nick} {czas_txt(w['e']['pierwszy'])} | {w['e']['rodzaj']} ({w['e']['czas_s']:.0f} s) | {stary} | {', '.join(dec_t) or 'bez zmian'} | "
                         f"{len(n['zawroty_stare'])}/{len(n['zawroty_nowe'])} | {n['w_widoku_stary']:.0f}/{n['w_widoku_nowy']:.0f} s |")
            else:
                L.append(f"| {nick} {czas_txt(w['e']['pierwszy'])} | {w['e']['rodzaj']} ({w['e']['czas_s']:.0f} s) | {stary} | nie odtworzono (brak trasy) | - | - |")
    L.append("")
    L.append("**Czego ten raport nie dowodzi:** zachowania w grze (gracze w nagraniu nie reagują na bota, nie ma mobów ani walki, skoki modelu na nagraną pozycję w stanach "
             "innych niż IDZ), trafności klasyfikacji „idzie w naszą stronę / stoi / zatyka przejście” na żywym ruchu, ani promienia „obrębu” mobów (UNIKANIE_MOB_PROMIEN). "
             "Sprawdza dopiero naturalna QA po wdrożeniu (F3, za zgodą Karola).")
    L.append("")
    return L


def raport(wyniki, wszystkich, probki, trasy, wlasne, logi, wzorzec, do=None):
    L = []
    P = L.append
    spot = [w["e"] for w in wyniki]
    tlo, tlo_s = tlo_zawrotow(probki, spot)
    P("# RAPORT F2: mijanie graczy — odtworzenie spotkań z telemetrii (18.10.2026)")
    P("")
    P(f"Wygenerowano: `narzedzia/odtworz_mijanie.py` (offline, tylko odczyt) z `{wzorzec}` w `{logi}`, {len(probki)} próbek"
      f"{', rekordy do ' + do if do else ''}, ostatnia {czas_txt(probki[-1]['t'])}. Spec: `SPEC_mijanie_graczy_1018.md`. "
      f"Kod: `unikanie.Unikanie.mijanie()` + `cavebot.Cavebot._mijanie_zastosuj()` (te same funkcje, które wykona bot przy MIJANIE=1), mapa klienta `mapa/map74.otmm`.")
    P("")
    L.extend(podsumowanie(wyniki, tlo))
    P("## Jak to liczono i czego to nie dowodzi")
    P("")
    P("- Źródło: próbki telemetrii co ~1 s (poz, stan, stwory z `gracz: true`) i zdarzenia `unikanie_*`. **Nie ma tu mobów ani nagrania ruchu "
      "co tick**, więc to nie jest powtórka z gry, tylko model: nagrani gracze (interpolacja liniowa między próbkami) + nasz model bota "
      f"(tick {TICK_S} s, krok co {KROK_S} s po trasie, A* z mapy klienta), który podejmuje decyzje nowym kodem. W stanach innych niż IDZ "
      "(WALKA, LOOT, PRZERWA, ...) model przyjmuje nagraną pozycję bota i nie decyduje (walka ma pierwszeństwo, Z3).")
    P(f"- Spotkanie = ciągła obecność tego samego obcego gracza w widoku (przerwa do {PRZERWA_S:.0f} s) na spocie (z >= 8). "
      f"Obcy = nie nasza postać (nasze: {', '.join(sorted(wlasne))}). Rodzaj: przechodzi (< 30 s), poluje (>= 30 s, rusza się), stoi (>= 30 s, rozrzut <= 3 pola).")
    P(f"- **Liczby spotkań nie zgadzają się z tabelą w specyfikacji** (84 na spocie; 63/15/6): skrypt z analizy 18.10 nie został w repo, "
      f"definicja spotkania jest tu inna (przerwa {PRZERWA_S:.0f} s zamiast nieznanej), więc porównuję stare i nowe tą samą miarą, nie z tamtą tabelą. "
      f"Wszystkich spotkań z obcymi (także poza spotem): {wszystkich}.")
    P("- Zawrót = krok w tył po kroku w przód: zmiana kierunku o > 90° między kolejnymi różnymi pozycjami z próbek co ~1 s w IDZ (odstępy <= 3 s). "
      f"Tło (IDZ na spocie poza spotkaniami +-{MARGINES_S:.0f} s, {tlo_s / 3600:.1f} h): **{tlo:.1f} zawrotu/min** (specyfikacja: 4,15; miara jest zbliżona, nie identyczna).")
    P("- Model nie wie, co zrobiłby gracz, gdyby bot zachował się inaczej (gracze są nagraniem, nie reagują na nas), nie zna mobów, "
      "a pozycja bota w stanach innych niż IDZ jest nagrana, nie modelowana. Odtwarzane są tylko spotkania z dopasowaną trasą (pętla/trasa w `trasy/`); "
      "patrol po miejscach, wypad i dojście nie są objęte MIJANIE.")
    P("")
    # ---- zbiorcze
    P("## Wyniki zbiorcze")
    P("")
    P("| Rodzaj | Spotkań | Odtworzonych | Stary: włączył unikanie | Stary: zmienił punkt | Nowy: bez zmiany planu | Nowy: odwrócenie | Nowy: skrót | Nowy: ustąpienie |")
    P("|---|---|---|---|---|---|---|---|---|")
    for rodzaj in ("przechodzi", "poluje", "stoi", "razem"):
        ws = [w for w in wyniki if rodzaj == "razem" or w["e"]["rodzaj"] == rodzaj]
        od = [w for w in ws if w["nowe"]]
        st_start = sum(1 for w in od if w["stare"].get("unikanie_start"))
        st_pkt = sum(1 for w in od if w["stare"].get("unikanie_punkt") or w["stare"].get("unikanie_blokada"))
        bez = sum(1 for w in od if not (w["nowe"]["odwroty"] or w["nowe"]["skroty"] or w["nowe"]["przejscia"]))
        P(f"| {rodzaj} | {len(ws)} | {len(od)} | {st_start} ({pct(st_start, len(od))}) | {st_pkt} ({pct(st_pkt, len(od))}) | "
          f"{bez} ({pct(bez, len(od))}) | {sum(w['nowe']['odwroty'] for w in od)} | {sum(w['nowe']['skroty'] for w in od)} | {sum(w['nowe']['przejscia'] for w in od)} |")
    P("")
    P("„Stary: włączył unikanie” = zdarzenie `unikanie_start` w oknie spotkania (to miara „zmienia plan” ze specyfikacji); „zmienił punkt” = `unikanie_punkt`/`unikanie_blokada`. "
      "„Nowy: bez zmiany planu” = żadnego odwrócenia, skrótu ani ustąpienia w modelu. Wszystkie wiersze liczą tylko spotkania odtworzone (z dopasowaną trasą).")
    P("")
    po_powodzie = collections.Counter()
    for w in wyniki:
        if w["nowe"]:
            for _, typ, d in w["nowe"]["zd"]:
                if typ == "mijanie_kierunek":
                    po_powodzie[(w["e"]["rodzaj"], d["powod"], d["akcja"])] += 1
                elif typ == "mijanie_przejscie" and d.get("etap") == "start":
                    po_powodzie[(w["e"]["rodzaj"], "idzie_na_nas_wasko", "ustapienie")] += 1
    P("Decyzje nowego kodu wg powodu (rodzaj spotkania, powód, akcja): " + (", ".join(f"{r}/{pw}/{a} ×{n}" for (r, pw, a), n in sorted(po_powodzie.items())) or "brak") + ". "
      "Powód `ta_strona` = gracz idzie przed nami tą samą stroną pętli, `oboz` = stoi na pętli (Q1).")
    P("")
    P("### Przechodnie (cel: >= 80% bez zmiany planu, dziś ok. 21%)")
    pr = [w for w in wyniki if w["e"]["rodzaj"] == "przechodzi" and w["nowe"]]
    bez_s = sum(1 for w in pr if not w["stare"].get("unikanie_start"))
    bez_n = sum(1 for w in pr if not (w["nowe"]["odwroty"] or w["nowe"]["skroty"] or w["nowe"]["przejscia"]))
    P("")
    P(f"- Stary kod (nagranie): bez `unikanie_start` {bez_s}/{len(pr)} = **{pct(bez_s, len(pr))}**.")
    P(f"- Nowy kod (model): bez zmiany planu {bez_n}/{len(pr)} = **{pct(bez_n, len(pr))}**.")
    P("")
    P("### Zawroty na minutę i czas w widoku gracza")
    P("")
    P("| Rodzaj | Zawroty/min stary (nagranie) | Zawroty/min model bez mijania (kontrola) | Zawroty/min nowy (MIJANIE=1) | Czas w widoku stary (med. s) | Czas w widoku nowy (med. s) | Postój nowy (suma s) |")
    P("|---|---|---|---|---|---|---|")
    for rodzaj in ("przechodzi", "poluje", "stoi"):
        od = [w for w in wyniki if w["e"]["rodzaj"] == rodzaj and w["nowe"]]
        min_s = sum(len(w["nowe"]["track_stary"]) for w in od) / 60.0     # próbki IDZ co ~1 s
        min_n = sum(len(w["nowe"]["track_nowy"]) for w in od) / 60.0
        min_k = sum(len(w["kontrola"]["track_nowy"]) for w in od) / 60.0
        zs = sum(len(w["nowe"]["zawroty_stare"]) for w in od)
        zn = sum(len(w["nowe"]["zawroty_nowe"]) for w in od)
        zk = sum(len(w["kontrola"]["zawroty_nowe"]) for w in od)
        if min_s and min_n and min_k:
            P(f"| {rodzaj} | {zs / min_s:.1f} ({zs}) | {zk / min_k:.1f} ({zk}) | {zn / min_n:.1f} ({zn}) | {mediana([w['nowe']['w_widoku_stary'] for w in od])} | "
              f"{mediana([w['nowe']['w_widoku_nowy'] for w in od])} | {sum(w['nowe']['postoj_s'] for w in od):.0f} |")
        else:
            P(f"| {rodzaj} | - | - | - | - | - | - |")
    P("")
    P(f"Tło (IDZ na spocie poza spotkaniami): {tlo:.1f} zawrotu/min. Kontrola = ten sam model bota z tymi samymi graczami, ale bez decyzji mijania "
      "(sam marsz po trasie ze skokami na nagraną pozycję): to dolna granica szumu modelu, nie zachowanie bota.")
    P("")
    po = [w["po_dec"] for w in wyniki if w.get("po_dec")]
    P(f"Czas w widoku obcego od pierwszej decyzji (miara nowa ze specyfikacji; tylko spotkania, w których zdecydowały obie strony: {len(po)}): "
      f"stary suma {sum(a for a, _ in po):.0f} s (med. {mediana([a for a, _ in po])} s), nowy suma {sum(b for _, b in po):.0f} s (med. {mediana([b for _, b in po])} s).")
    P("")
    P("Zawroty/min = zawroty / minuty IDZ w oknie spotkania (+-15 s). W nawiasie liczba zawrotów. Czas w widoku = sekundy z obcym w oknie 15x11 pól wokół bota.")
    P("")
    # ---- trasy
    P("## Trasy dopasowane do spotkań")
    P("")
    tr = collections.Counter((w["trasa"][0] if w["trasa"] else "brak (patrol/wypad/dojście)") for w in wyniki)
    for k, v in tr.most_common():
        P(f"- `{k}`: {v}")
    bledy = [w for w in wyniki if w.get("blad")]
    if bledy:
        P("")
        P(f"Błędy odtwarzania: {len(bledy)} (np. {bledy[0]['blad']}).")
    P("")
    # ---- obowiązkowe
    P("## Spotkania obowiązkowe")
    P("")
    for (nick, kiedy) in OBOWIAZKOWE:
        t_ref = datetime.datetime.strptime(kiedy, "%Y-%m-%dT%H:%M").timestamp()
        kand = [w for w in wyniki if w["e"]["nazwa"] == nick and abs(w["e"]["pierwszy"] - t_ref) <= 150]
        if not kand:
            P(f"### {nick} {kiedy}: NIE ZNALEZIONO w telemetrii")
            P("")
            continue
        for w in kand:
            P(opis_spotkania(w))
    # ---- wszystkie przechodzi
    P("## Wszystkie przechodnie (jedna linia na spotkanie)")
    P("")
    P("| Kiedy | Gracz | s w widoku | Trasa | Stary (zdarzenia) | Nowy (decyzje) | Bez zmiany planu (nowy) |")
    P("|---|---|---|---|---|---|---|")
    for w in wyniki:
        e = w["e"]
        if e["rodzaj"] != "przechodzi":
            continue
        stary = ", ".join(f"{k.replace('unikanie_', '')}×{v}" for k, v in sorted(w["stare"].items())) or "-"
        if w["nowe"]:
            n = w["nowe"]
            nowy = f"odw {n['odwroty']}, skrót {n['skroty']}, ustąp {n['przejscia']}" if (n["odwroty"] or n["skroty"] or n["przejscia"]) else "bez zmian"
            bez = "tak" if nowy == "bez zmian" else "nie"
        else:
            nowy, bez = ("(nie odtwarzano: " + ("błąd" if w.get("blad") else "brak trasy") + ")"), "-"
        P(f"| {czas_txt(e['pierwszy'])} | {e['nazwa']} | {e['czas_s']:.0f} | {w['trasa'][0] if w['trasa'] else '-'} | {stary} | {nowy} | {bez} |")
    P("")
    return "\n".join(L)


def opis_spotkania(w):
    e, n = w["e"], w["nowe"]
    L = []
    P = L.append
    P(f"### {e['nazwa']} {czas_txt(e['pierwszy'])} ({e['czas_s']:.0f} s w widoku, {e['rodzaj']}, trasa {w['trasa'][0] if w['trasa'] else 'brak'})")
    P("")
    stary = ", ".join(f"{k.replace('unikanie_', '')}×{v}" for k, v in sorted(w["stare"].items())) or "brak zdarzeń"
    P(f"- Stary kod (nagranie): {stary}.")
    for z in w["stare_zd"][:8]:
        opis = z.get("powod") or z.get("tryb") or ""
        P(f"  - {czas_txt(z['t'])} `{z['typ']}` {opis}"[:200])
    if not n:
        P("- Nowy kod: nie odtworzono (" + ("błąd " + w.get("blad", "") if w.get("blad") else "brak dopasowanej trasy") + ").")
        P("")
        return "\n".join(L)
    P(f"- Nowy kod (model): odwróceń {n['odwroty']}, skrótów {n['skroty']}, ustąpień {n['przejscia']}, postój {n['postoj_s']:.1f} s; "
      f"zawrotów stary/nowy {len(n['zawroty_stare'])}/{len(n['zawroty_nowe'])}; w widoku gracza stary/nowy {n['w_widoku_stary']:.0f}/{n['w_widoku_nowy']:.0f} s.")
    for t, typ, d in n["zd"][:10]:
        szczegol = {k: v for k, v in d.items() if k in ("akcja", "powod", "etap", "gracz", "odl", "kier", "czas_widoku", "pole", "punkt", "czas_s", "stal_s", "zmian_kierunku", "przejsc")}
        P(f"  - {czas_txt(t)} `{typ}` {szczegol}")
    # przebieg odległości co ~5 s: nagrany bot vs model
    P("")
    P("| t od początku | dystans do gracza: nagranie | dystans: model | pozycja nagrana | pozycja modelu |")
    P("|---|---|---|---|---|")
    po_t = {round(t): (p, o) for t, p, idz, o in n["seria_model"]}
    for k in range(0, int(e["ost"] - e["pierwszy"]) + 1, 5):
        t_abs = e["pierwszy"] + k
        # najbliższa nagrana pozycja bota i gracza
        ts = [(abs(t - t_abs), t, p) for t, p in n["track_stary"]]
        if not ts:
            continue
        _, t_n, p_n = min(ts)
        gr_n = next((CHEB(p_n, (x, y)) for (t, x, y, zz) in e["pkt"] if abs(t - t_n) <= 1.5), None)
        m = min(n["seria_model"], key=lambda s: abs(s[0] - t_abs))
        gr_m = min((CHEB(m[1], o) for o in m[3]), default=None)
        P(f"| {k} s | {gr_n if gr_n is not None else '-'} | {gr_m if gr_m is not None else '-'} | {p_n} | {m[1]} |")
    P("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--logi", default=None)
    ap.add_argument("--wzorzec", default="telemetria-2026101[5-8].jsonl")
    ap.add_argument("--do", default=None, help="odrzuć rekordy późniejsze niż RRRR-MM-DDTGG:MM (czas lokalny): logi bieżącego dnia rosną, raport ma być powtarzalny")
    ap.add_argument("--raport", default=None, help="zapisz raport markdown")
    ap.add_argument("--json", default=None, help="zapisz miary per spotkanie")
    a = ap.parse_args(argv)
    logi = znajdz_logi(a.logi, a.wzorzec)
    print(f"Wczytuję {a.wzorzec} z {logi} (tylko odczyt) ...", flush=True)
    do_t = datetime.datetime.strptime(a.do, "%Y-%m-%dT%H:%M").timestamp() if a.do else None
    probki, zdarzenia, wlasne = wczytaj(logi, a.wzorzec, do_t)
    print(f"  próbek {len(probki)}, zdarzeń unikanie_* {len(zdarzenia)}, nasze postacie {sorted(wlasne)}", flush=True)
    trasy = wczytaj_trasy()
    model = Model()
    wyniki, wszystkich = analizuj(probki, zdarzenia, model, trasy)
    txt = raport(wyniki, wszystkich, probki, trasy, wlasne, logi, a.wzorzec, a.do)
    if a.raport:
        with open(a.raport, "w", encoding="utf-8") as f:
            f.write(txt + "\n")
        print(f"Raport: {a.raport}")
    else:
        print(txt)
    if a.json:
        out = [{"gracz": w["e"]["nazwa"], "t": w["e"]["pierwszy"], "czas_s": w["e"]["czas_s"], "rodzaj": w["e"]["rodzaj"],
                "trasa": w["trasa"][0] if w["trasa"] else None, "stare": dict(w["stare"]),
                "nowe": ({k: v for k, v in w["nowe"].items() if k in ("odwroty", "skroty", "przejscia", "postoj_s", "w_widoku_nowy", "w_widoku_stary")}
                         | {"zawroty_nowe": len(w["nowe"]["zawroty_nowe"]), "zawroty_stare": len(w["nowe"]["zawroty_stare"])}) if w["nowe"] else None}
               for w in wyniki]
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
