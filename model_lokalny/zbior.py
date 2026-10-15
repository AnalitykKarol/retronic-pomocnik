"""Budowa zbiorów D1 (wybór celu), D2 (pościg) i D3 (zawieszka) ze starej telemetrii (logi/telemetria-*.jsonl).

Krok B specyfikacji: opcje odtworzone z najbliższej wcześniejszej `probka` — przybliżenie, tylko do oceny sygnału.
Czysta funkcja rekordów -> zbiór; nic nie zgadujemy: braki dopasowań są liczone w statystykach i zwracane.
"""
import glob
import json
import os
import re

import numpy as np

# stałe dopasowania (jawne, do raportu)
MAKS_WIEK_PROBKI_S = 3.0      # próbka nie starsza niż tyle względem nowy_cel / poscig_start
MAKS_PRZESUNIECIE = 3         # maks. odległość (kratki, Czebyszew) pozycji nowy_cel od kandydata z próbki
TOL_T0_S = 0.05               # tolerancja t0 epizodu względem t nowy_cel (dopasowanie dokładne)
MAKS_T0_NAZWA_S = 5.0         # dopasowanie awaryjne po nazwie: najbliższe t0, ale nie dalej niż tyle
PROG_ZAB_S = 15.0             # etykieta D1: zabity w <= tyle sekund
DUZA_ODL = 50.0               # odległość do gracza, gdy w próbce nie ma innego gracza
PROMIEN_TLUMU = 2             # „inne moby w odl<=2 od kandydata”

POWODY_D2_1 = ("odl<=1", "cel_martwy")
# porażka pościgu: bot nie doszedł (brak ruchu, zawracanie) albo odpuścił (objazd, okno); "cel_znikl" (cel zniknął z
# widoku, np. zszedł piętro) to nie wina pościgu: pomijany jak "gryzacy"
POWODY_D2_0 = ("brak_ruchu", "zawracanie", "objazd", "okno")

CECHY_D1 = ["odl", "adx", "ady", "hp", "osiag_tak", "osiag_nie", "inne_w2", "odl_gracza", "byl_celem"]
CECHY_D2 = ["odl", "hp_celu", "inne_w2", "odl_gracza", "osiag_tak", "osiag_nie"]
# D3 (16.10, krok A SPEC_model_D3_utkniecia_1015): jeden wiersz = jedna zawieszka (rekord `decyzja` D3 + `d3_wynik`).
# Brak wartości (np. A* nie policzono) = -1 plus osobna flaga, nic nie zgadujemy. Cechy per opcja trafią do zbioru
# dopiero z etykietami nauczyciela (krok B); tu etykieta dotyczy zawieszki jako całości.
CECHY_D3 = ["stoi_s", "wolne_wokol", "ogien_dziura_wokol", "odl_cel", "cel_droga", "cel_droga_policzona", "gracz_odl",
            "mob_odl", "hp_gracza", "poprzednie_tu", "skos_mozliwa", "cofnij_mozliwa", "cofnij_kroki",
            "punkt_osiagalnych", "punkt_droga", "pietro_mozliwe", "pietro_odl"]
PROG_RUCHU_D3_S = 20.0        # etykieta D3: ruszyliśmy w ciągu tylu sekund od wykrycia zawieszki


def _data_z_nazwy(sciezka):
    m = re.search(r"telemetria-(\d{8})\.jsonl$", os.path.basename(sciezka))
    return m.group(1) if m else None


def wczytaj_telemetrie(katalog, od=None):
    """Czyta telemetria-*.jsonl (tylko odczyt) od daty RRRRMMDD. Zwraca (rekordy posortowane po t, statystyki)."""
    pliki = sorted(glob.glob(os.path.join(katalog, "telemetria-*.jsonl")))
    stat = {"pliki": 0, "rekordy": 0, "zle_linie": 0}
    rek = []
    for p in pliki:
        d = _data_z_nazwy(p)
        if od and d and d < str(od):
            continue
        stat["pliki"] += 1
        with open(p, encoding="utf-8") as f:
            for lin in f:
                lin = lin.strip()
                if not lin:
                    continue
                try:
                    r = json.loads(lin)
                except ValueError:
                    stat["zle_linie"] += 1
                    continue
                if isinstance(r, dict) and "t" in r and "typ" in r:
                    rek.append(r)
    rek.sort(key=lambda r: r["t"])  # sort stabilny: remisy zostają w kolejności zapisu
    stat["rekordy"] = len(rek)
    return rek, stat


def _inne_ob(stwory):
    """Moby (gracz != True) z próbki."""
    return [s for s in stwory if not s.get("gracz") and (s.get("hp") or 0) > 0]


def _odl_czeb(a, b):
    return max(abs(a["dx"] - b["dx"]), abs(a["dy"] - b["dy"]))


def _odl_gracza(kand, stwory):
    """Odległość kandydata do najbliższego INNEGO gracza (wpis w (0,0) to my sami); brak -> DUZA_ODL."""
    best = DUZA_ODL
    for s in stwory:
        if s.get("gracz") and not (s["dx"] == 0 and s["dy"] == 0):
            best = min(best, _odl_czeb(kand, s))
    return float(best)


def _inne_w_tlumie(kand, moby):
    return sum(1 for s in moby if s is not kand and _odl_czeb(kand, s) <= PROMIEN_TLUMU)


def _osiag(s):
    o = s.get("osiagalny")
    return (1.0 if o is True else 0.0, 1.0 if o is False else 0.0)


def cechy_d1(kand, stwory):
    """Wektor cech kandydata D1 (kolejność = CECHY_D1). `kand` jest elementem `stwory` (próbka)."""
    moby = _inne_ob(stwory)
    tak, nie = _osiag(kand)
    return [float(kand["odl"]), float(abs(kand["dx"])), float(abs(kand["dy"])), float(kand["hp"]), tak, nie,
            float(_inne_w_tlumie(kand, moby)), _odl_gracza(kand, stwory), 1.0 if kand.get("cel") else 0.0]


def cechy_d2(kand, stwory, odl, hp_celu):
    """Wektor cech pościgu D2 (kolejność = CECHY_D2); kand = cel w próbce albo None (wtedy braki = neutralne)."""
    if kand is None:
        return [float(odl), float(hp_celu), 0.0, DUZA_ODL, 0.0, 0.0]
    moby = _inne_ob(stwory)
    tak, nie = _osiag(kand)
    return [float(odl), float(hp_celu), float(_inne_w_tlumie(kand, moby)), _odl_gracza(kand, stwory), tak, nie]


class Zbior:
    """Zbiór: X (n×k), y (n,), sesja (n,), t (n,), nazwy cech, plus (D1) kandydaci/wybrany do oceny wyboru."""

    def __init__(self, nazwy):
        self.nazwy = list(nazwy)
        self.wiersze, self.y, self.sesja, self.t = [], [], [], []
        self.kandydaci = []   # D1: lista macierzy cech wszystkich kandydatów danego zdarzenia
        self.wybrany = []     # D1: indeks wybranego w kandydaci
        self.najblizszy = []  # D1: indeks kandydata o najmniejszej odl (remis: pierwszy)

    @property
    def X(self):
        return np.array(self.wiersze, dtype=float).reshape(-1, len(self.nazwy))

    @property
    def Y(self):
        return np.array(self.y, dtype=float)

    def __len__(self):
        return len(self.y)


def _indeks_probek(rekordy):
    """Dla każdej sesji: posortowane listy t i próbek."""
    wg = {}
    for r in rekordy:
        if r["typ"] == "probka":
            wg.setdefault(r.get("sesja"), []).append(r)
    return {s: ([p["t"] for p in lst], lst) for s, lst in wg.items()}


def _probka_przed(idx, sesja, t):
    """Najbliższa WCZEŚNIEJSZA (t_probki <= t) próbka tej sesji. Zwraca (probka|None, powod_braku|None)."""
    if sesja not in idx:
        return None, "brak_probki"
    ts, lst = idx[sesja]
    # bisect_right: ostatnia próbka z t_p <= t
    lo, hi = 0, len(ts)
    while lo < hi:
        mid = (lo + hi) // 2
        if ts[mid] <= t:
            lo = mid + 1
        else:
            hi = mid
    if lo == 0:
        return None, "brak_probki"
    p = lst[lo - 1]
    if t - p["t"] > MAKS_WIEK_PROBKI_S:
        return None, "probka_za_stara"
    return p, None


def _dopasuj_epizody(rekordy):
    """Dla każdego nowy_cel (indeks w `rekordy`) -> (epizod|None, tryb 'dokladny'|'po_nazwie'|None)."""
    epi = {}
    for i, r in enumerate(rekordy):
        if r["typ"] == "epizod_celu":
            epi.setdefault(r.get("sesja"), []).append(i)
    uzyte = set()
    wynik = {}
    nowe = [i for i, r in enumerate(rekordy) if r["typ"] == "nowy_cel"]
    # przebieg 1: dokładny t0 == t (tolerancja)
    for i in nowe:
        nc = rekordy[i]
        best, bd = None, None
        for j in epi.get(nc.get("sesja"), []):
            if j in uzyte or "t0" not in rekordy[j]:
                continue
            d = abs(rekordy[j]["t0"] - nc["t"])
            if d <= TOL_T0_S and (bd is None or d < bd):
                best, bd = j, d
        if best is not None:
            uzyte.add(best)
            wynik[i] = (rekordy[best], "dokladny")
    # przebieg 2: ta sama nazwa, najbliższe t0 (nie dalej niż MAKS_T0_NAZWA_S), epizod jeszcze nieużyty
    for i in nowe:
        if i in wynik:
            continue
        nc = rekordy[i]
        best, bd = None, None
        for j in epi.get(nc.get("sesja"), []):
            e = rekordy[j]
            if j in uzyte or "t0" not in e or e.get("n") != nc.get("n"):
                continue
            d = abs(e["t0"] - nc["t"])
            if d <= MAKS_T0_NAZWA_S and (bd is None or d < bd):
                best, bd = j, d
        if best is not None:
            uzyte.add(best)
            wynik[i] = (rekordy[best], "po_nazwie")
        else:
            wynik[i] = (None, None)
    return wynik


def etykieta_d1(epizod):
    """1 gdy zabity w <= PROG_ZAB_S sekund, inaczej 0."""
    dz = epizod.get("do_zab_s")
    return 1 if epizod.get("wynik") == "zabity" and dz is not None and dz <= PROG_ZAB_S else 0


def zbuduj_d1(rekordy):
    """Zbiór D1. Zwraca (Zbior, statystyki). Każde nowy_cel bez próbki / kandydata / epizodu jest liczone, nie zgadywane."""
    idx = _indeks_probek(rekordy)
    epi = _dopasuj_epizody(rekordy)
    z = Zbior(CECHY_D1)
    st = {"nowy_cel": 0, "brak_probki": 0, "probka_za_stara": 0, "brak_kandydatow": 0, "brak_dopasowania_pozycji": 0,
          "bez_epizodu": 0, "uzyte": 0, "epizod_dokladny": 0, "epizod_po_nazwie": 0, "etykieta_1": 0, "etykieta_0": 0,
          "przesuniecie": {}, "wybrany_najblizszy": 0, "z_wieloma_kandydatami": 0}
    for i, r in enumerate(rekordy):
        if r["typ"] != "nowy_cel":
            continue
        st["nowy_cel"] += 1
        p, powod = _probka_przed(idx, r.get("sesja"), r["t"])
        if p is None:
            st[powod] += 1
            continue
        kand = [s for s in p["stwory"] if not s.get("gracz") and (s.get("hp") or 0) > 0]
        if not kand:
            st["brak_kandydatow"] += 1
            continue
        px, py = r["pos"][0], r["pos"][1]
        # pozycja kandydata = poz próbki + (dx, dy); wybrany = ta sama nazwa i najbliżej pozycji nowy_cel
        wyb, wd = None, None
        for k, s in enumerate(kand):
            if s.get("n") != r.get("n"):
                continue
            d = max(abs(p["poz"][0] + s["dx"] - px), abs(p["poz"][1] + s["dy"] - py))
            if wd is None or d < wd:
                wyb, wd = k, d
        if wyb is None or wd > MAKS_PRZESUNIECIE:
            st["brak_dopasowania_pozycji"] += 1
            continue
        e, tryb = epi.get(i, (None, None))
        if e is None:
            st["bez_epizodu"] += 1
            continue
        st["epizod_" + tryb] += 1
        st["przesuniecie"][wd] = st["przesuniecie"].get(wd, 0) + 1
        macierz = [cechy_d1(s, p["stwory"]) for s in kand]
        y = etykieta_d1(e)
        z.wiersze.append(macierz[wyb])
        z.y.append(y)
        z.sesja.append(r.get("sesja"))
        z.t.append(r["t"])
        z.kandydaci.append(np.array(macierz, dtype=float))
        z.wybrany.append(wyb)
        z.najblizszy.append(int(np.argmin([s["odl"] for s in kand])))
        st["uzyte"] += 1
        st["etykieta_%d" % y] += 1
        st["wybrany_najblizszy"] += int(kand[wyb]["odl"] == min(s["odl"] for s in kand))
        st["z_wieloma_kandydatami"] += int(len(kand) > 1)
    return z, st


def etykieta_d2(powod):
    """1 = dojście/cel martwy, 0 = porażka pościgu, None = pomiń."""
    if powod in POWODY_D2_1:
        return 1
    if powod in POWODY_D2_0:
        return 0
    return None


def zbuduj_d2(rekordy):
    """Zbiór D2: pary poscig_start -> następny poscig_koniec tej samej sesji (przed kolejnym startem)."""
    idx = _indeks_probek(rekordy)
    z = Zbior(CECHY_D2)
    st = {"poscig_start": 0, "bez_konca": 0, "brak_probki": 0, "probka_za_stara": 0, "bez_celu_w_probce": 0,
          "powod_pominiety": 0, "uzyte": 0, "etykieta_1": 0, "etykieta_0": 0, "pominiete_powody": {}}
    otwarte = {}  # sesja -> poscig_start czekający na koniec
    pary = []
    for r in rekordy:
        s = r.get("sesja")
        if r["typ"] == "poscig_start":
            st["poscig_start"] += 1
            if s in otwarte:
                st["bez_konca"] += 1  # poprzedni start nie dostał końca przed kolejnym startem
            otwarte[s] = r
        elif r["typ"] == "poscig_koniec":
            if s in otwarte:
                pary.append((otwarte.pop(s), r))
    st["bez_konca"] += len(otwarte)
    for start, koniec in pary:
        y = etykieta_d2(koniec.get("powod"))
        if y is None:
            st["powod_pominiety"] += 1
            k = str(koniec.get("powod"))
            st["pominiete_powody"][k] = st["pominiete_powody"].get(k, 0) + 1
            continue
        p, powod = _probka_przed(idx, start.get("sesja"), start["t"])
        if p is None:
            st[powod] += 1
            continue
        # cel w próbce: ta sama nazwa, odległość najbliższa odl ze startu; bez dopasowania -> liczymy i pomijamy
        moby = [s for s in p["stwory"] if not s.get("gracz") and s.get("n") == start.get("cel")]
        if not moby:
            st["bez_celu_w_probce"] += 1
            continue
        kand = min(moby, key=lambda s: abs(s["odl"] - start["odl"]))
        z.wiersze.append(cechy_d2(kand, p["stwory"], start["odl"], start["hp_celu"]))
        z.y.append(y)
        z.sesja.append(start.get("sesja"))
        z.t.append(start["t"])
        st["uzyte"] += 1
        st["etykieta_%d" % y] += 1
    return z, st


def _opt_d3(r, akcja):
    return next((o for o in r.get("opcje", []) if o.get("akcja") == akcja), {})


def _num(v, brak=-1.0):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else float(brak)


def cechy_d3(r):
    """Wektor cech zawieszki z rekordu `decyzja` D3 (kolejność = CECHY_D3)."""
    wok = r.get("wokol") or {}
    sk, co, pu, pi = (_opt_d3(r, a) for a in ("krok_skos", "cofnij", "inny_punkt", "przejscie_pietra"))
    gr, mo = r.get("gracze_odl") or [], r.get("moby_odl") or []
    return [_num(r.get("stoi_s")), float(sum(1 for v in wok.values() if v == ".")),
            float(sum(1 for v in wok.values() if v in ("o", "d", "s"))), _num(r.get("odl_cel")),
            _num(r.get("cel_droga")), 1.0 if r.get("cel_droga_policzona") else 0.0,
            float(min(gr)) if gr else DUZA_ODL, float(min(mo)) if mo else DUZA_ODL, _num(r.get("hp_gracza"), 100.0),
            _num(r.get("poprzednie_tu"), 0.0), 1.0 if sk.get("mozliwa") else 0.0, 1.0 if co.get("mozliwa") else 0.0,
            _num(co.get("kroki"), 0.0), _num(pu.get("osiagalnych"), 0.0), _num(pu.get("droga")),
            1.0 if pi.get("mozliwa") else 0.0, _num(pi.get("odl"))]


def etykieta_d3(w):
    """Etykieta zawieszki z `d3_wynik`: 1 = ruszyliśmy w ciągu PROG_RUCHU_D3_S s od wykrycia; 0 = zawieszka trwała dłużej
    (niezależnie od tego, jak się skończyła); None = obserwacja ucięta przed upływem progu (exp, walka, stop, luka)."""
    czas = w.get("czas_s")
    if w.get("ruszyl") and czas is not None and czas <= PROG_RUCHU_D3_S:
        return 1
    if czas is not None and czas > PROG_RUCHU_D3_S:
        return 0
    return None


def zbuduj_d3(rekordy):
    """Zbiór D3: `decyzja` D3 sparowana z `d3_wynik` (ten sam decyzja_id i sesja). Pomijane i liczone: bez wyniku,
    zamierzone (PRZERWA/PAUZA/GRACZ), obserwacja ucięta. Zwraca (Zbior, statystyki)."""
    z = Zbior(CECHY_D3)
    st = {"decyzje_d3": 0, "bez_wyniku": 0, "zamierzone": 0, "obserwacja_ucieta": 0, "uzyte": 0,
          "etykieta_1": 0, "etykieta_0": 0}
    wyniki = {}
    for r in rekordy:
        if r.get("typ") == "d3_wynik" and r.get("decyzja_id") is not None:
            wyniki[(r.get("sesja"), r["decyzja_id"])] = r
    for r in rekordy:
        if r.get("typ") != "decyzja" or r.get("rodzaj") != "D3":
            continue
        st["decyzje_d3"] += 1
        w = wyniki.get((r.get("sesja"), r.get("id")))
        if w is None:
            st["bez_wyniku"] += 1
            continue
        if r.get("zamierzony"):
            st["zamierzone"] += 1
            continue
        y = etykieta_d3(w)
        if y is None:
            st["obserwacja_ucieta"] += 1
            continue
        z.wiersze.append(cechy_d3(r))
        z.y.append(y)
        z.sesja.append(r.get("sesja"))
        z.t.append(r["t"])
        st["uzyte"] += 1
        st["etykieta_%d" % y] += 1
    return z, st
