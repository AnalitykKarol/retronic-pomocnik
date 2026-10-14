#!/usr/bin/env python3
"""Porównanie ruchu bota w dwóch oknach czasu (metryki z tabeli "Stan wyjściowy" w dane_tibia/SPEC_ruch_pietra_1014.md).

  python3 -I narzedzia/porownaj_ruch.py OKNO_A [OKNO_B] [--json] [--logi KATALOG]
  OKNO = POCZĄTEK-KONIEC, czas lokalny, np. 2026-10-14T12:55-2026-10-14T13:55 (też z sekundami: ...T12:55:30)

Tylko odczyt: logi/telemetria-RRRRMMDD.jsonl(.1) i logi/mozg-stdout-MMDD-GGMM.log (ogień). Bez OKNO_B tylko jedna kolumna (baza).
Szum odfiltrowany: rekordy src=test, próbki z graczem "Ja" (atrapy z testów), zdarzenia pietra_* bez próbki w +-3 s.

Definicje (przybliżenia z analizy 14.10, dane_tibia/ruch/PLYNNOSC.md; porównujemy okna TĄ SAMĄ miarą, nie z liczbami z analizy):
  - patrol: próbka/okno w promieniu 400 s od zdarzenia patrol_cel/patrol_wizyta.
  - okno próbek: dwie kolejne próbki IDZ, to samo piętro, odstęp <= 15 s, przesunięcie <= 6 pól.
  - efektywny marsz: suma min(odstęp, pola * krok_s) / suma odstępów; pola = Czebyszew, krok_s = 0,047 s * prędkość pola
    docelowego z mapy (jak POSCIG_KROK_S_NA_PREDKOSC), bez mapy 0,6 s. Postój patrolu zostaje w mianowniku.
  - s na pole (wizyta ze schodami): patrol_wizyta.dojscie_s / patrol_cel.droga dla wizyt bez zabić po drodze i bez pościgu,
    ze zdarzeniem pietra_start między celem a wizytą; mediana i suma/suma.
  - ogień (strata): w oknach IDZ patrolu, w których pole ognia z logu [OGIEN] pola (ważne 40 s, to samo piętro) leży w 3 polach
    od któregoś końca okna, liczymy czas ponad sufit marszu (odstęp - min(odstęp, pola * krok_s)) pomniejszony o to, co w tych
    samych oknach straciłoby się bez ognia (średnia strata na sekundę w oknach bez ognia) / czas IDZ patrolu.
  - przejścia: pietra_krok (udane); 1. próba = proba==1; czas = pietra_krok.t - najbliższe wcześniejsze pietra_start (to samo
    z_od/z_do, do 120 s).
  - odpuszczenia za ścianą: zdarzenia odpuszczenie z powodem zaczynającym się od "za ścianą".
  - postój na miejscu: czas okien IDZ patrolu leżących w przedziale [wizyta - na_miejscu_s, wizyta] / czas IDZ patrolu.
Dodatkowo (gdy są rekordy ruch_okno, R0b): marsz/IDZ, luki ticka, kliki, strzałki, przyczyny stania.
"""
import bisect
import datetime
import glob
import json
import os
import re
import sys

KAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KAT)

PATROL_PROMIEN_S = 400.0
OKNO_PROBEK_MAX_S = 15.0
SKOK_MAX = 6
KROK_S_NA_PREDKOSC = 0.047
KROK_S_BEZ_MAPY = 0.6
OGIEN_WAZNY_S = 40.0
OGIEN_PROMIEN = 3
FILTR_PROBKA_S = 3.0
NAZWY_TESTOWE = ("Ja",)


# --- okna i wczytywanie ---
def parsuj_czas(txt):
    txt = txt.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(txt, fmt).timestamp()
        except ValueError:
            pass
    raise ValueError(f"zły czas: {txt!r} (oczekiwane RRRR-MM-DDTGG:MM)")


def parsuj_okno(txt):
    m = re.fullmatch(r"(\d{4}-\d\d-\d\d(?:T[\d:]+)?)-(\d{4}-\d\d-\d\d(?:T[\d:]+)?)", txt.strip())
    if not m:
        raise ValueError(f"zły format okna: {txt!r} (oczekiwane np. 2026-10-14T12:55-2026-10-14T13:55)")
    a, b = parsuj_czas(m.group(1)), parsuj_czas(m.group(2))
    if b <= a:
        raise ValueError("koniec okna przed początkiem")
    return a, b


def wczytaj_telemetrie(t0, t1, katalog=None):
    """Rekordy z telemetrii z zapasem 10 min po obu stronach (filtr szumu patrzy w sąsiedztwo)."""
    katalog = katalog or os.path.join(KAT, "logi")
    dni = set()
    d = datetime.datetime.fromtimestamp(t0 - 600).date()
    koniec = datetime.datetime.fromtimestamp(t1 + 600).date()
    while d <= koniec:
        dni.add(d.strftime("%Y%m%d"))
        d += datetime.timedelta(days=1)
    rek = []
    for dzien in sorted(dni):
        for p in (f"telemetria-{dzien}.jsonl.1", f"telemetria-{dzien}.jsonl"):
            f = os.path.join(katalog, p)
            if not os.path.exists(f):
                continue
            with open(f, errors="replace") as fh:
                for l in fh:
                    try:
                        r = json.loads(l)
                    except ValueError:
                        continue
                    if isinstance(r, dict) and isinstance(r.get("t"), (int, float)) and t0 - 600 <= r["t"] <= t1 + 600:
                        rek.append(r)
    rek.sort(key=lambda r: r["t"])
    return rek


def _wlasny_testowy(r):
    st = r.get("stwory")
    if not isinstance(st, list):
        return False
    return any(isinstance(s, dict) and s.get("gracz") and s.get("n") in NAZWY_TESTOWE for s in st)


def filtruj_szum(rek):
    """Zwraca (czyste, liczniki odrzuceń)."""
    odrz = {"src_test": 0, "gracz_Ja": 0, "pietra_bez_probki": 0}
    ok = []
    for r in rek:
        if r.get("src") == "test":
            odrz["src_test"] += 1
        elif r.get("typ") == "probka" and _wlasny_testowy(r):
            odrz["gracz_Ja"] += 1
        else:
            ok.append(r)
    ts = [r["t"] for r in ok if r.get("typ") == "probka"]
    wynik = []
    for r in ok:
        if str(r.get("typ", "")).startswith("pietra_"):
            i = bisect.bisect_left(ts, r["t"] - FILTR_PROBKA_S)
            if i >= len(ts) or ts[i] > r["t"] + FILTR_PROBKA_S:
                odrz["pietra_bez_probki"] += 1
                continue
        wynik.append(r)
    return wynik, odrz


def wczytaj_ogien(t0, t1, katalog=None):
    """[(czas, piętro, {(x,y)})] z logów [OGIEN] pola (kolejne wpisy; 'brak' = pusty zbiór)."""
    katalog = katalog or os.path.join(KAT, "logi")
    wpisy = []
    rok = datetime.datetime.fromtimestamp(t0).year
    re_og = re.compile(r"\[OGIEN\] pola: (.*)")
    re_xy = re.compile(r"\((\d+),(\d+)\)")
    re_z = re.compile(r"piętro (\d+)")
    for f in sorted(glob.glob(os.path.join(katalog, "mozg-stdout-*-*.log"))):
        m = re.search(r"mozg-stdout-(\d\d)(\d\d)-(\d\d)(\d\d)", f)
        if not m:
            continue
        mo, d, h, mi = map(int, m.groups())
        try:
            baza = datetime.datetime(rok, mo, d)
        except ValueError:
            continue
        if baza.timestamp() > t1 or os.path.getmtime(f) < t0 - 600:
            continue
        dzien, ost = 0, None
        with open(f, errors="replace") as fh:
            for l in fh:
                mm = re.match(r"(\d\d):(\d\d):(\d\d) (.*)", l.rstrip("\n"))
                if not mm:
                    continue
                sek = int(mm[1]) * 3600 + int(mm[2]) * 60 + int(mm[3])
                if ost is not None and sek < ost - 3600:
                    dzien += 1
                ost = sek
                t = (baza + datetime.timedelta(days=dzien, seconds=sek)).timestamp()
                if not (t0 - 600 <= t <= t1 + 600):
                    continue
                mo_ = re_og.search(mm[4])
                if not mo_:
                    continue
                tekst = mo_.group(1)
                zz = re_z.search(tekst)
                z = int(zz.group(1)) if zz else None
                pola = {(int(a), int(b)) for a, b in re_xy.findall(tekst)}
                wpisy.append((t, z, pola))
    wpisy.sort(key=lambda w: w[0])
    return wpisy


# --- metryki ---
def _mapa():
    try:
        import mapa as mapa_mod  # noqa: PLC0415
        return mapa_mod.mapa()
    except Exception:
        return None


def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _mediana(v):
    v = sorted(v)
    if not v:
        return None
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def policz(rek, t0, t1, ogien, M):
    """Metryki dla jednego okna [t0, t1]; rek = czyste rekordy (z zapasem), ogien = wpisy z logu."""
    w = [r for r in rek if t0 <= r["t"] < t1]
    probki = [r for r in w if r.get("typ") == "probka" and r.get("poz")]
    pat_t = sorted(r["t"] for r in rek if r.get("typ") in ("patrol_cel", "patrol_wizyta"))
    postoje = sorted((r["t"] - (r.get("na_miejscu_s") or 0.0), r["t"]) for r in rek
                     if r.get("typ") == "patrol_wizyta" and r.get("na_miejscu_s"))
    po_t = [p[0] for p in postoje]

    def patrol(t):
        i = bisect.bisect_left(pat_t, t - PATROL_PROMIEN_S)
        return i < len(pat_t) and pat_t[i] <= t + PATROL_PROMIEN_S

    wynik = {"okno_s": t1 - t0, "probek": len(probki)}
    # okna próbek IDZ w patrolu
    idz = marsz = ogien_s = postoj_s = og_dt = bez_dt = bez_strata = 0.0
    og_t = [o[0] for o in ogien]
    for a, b in zip(probki, probki[1:]):
        dt = b["t"] - a["t"]
        if a.get("stan") != "IDZ" or b.get("stan") != "IDZ" or not (0 < dt <= OKNO_PROBEK_MAX_S):
            continue
        pa, pb = tuple(a["poz"]), tuple(b["poz"])
        if pa[2] != pb[2] or _cheb(pa, pb) > SKOK_MAX or not patrol(a["t"]):
            continue
        idz += dt
        k = _cheb(pa, pb)
        ef = 0.0
        if k:
            sp = M.pole(pb[0], pb[1], pb[2]) if M is not None else None
            krok = KROK_S_NA_PREDKOSC * sp[2] if sp and sp[2] else KROK_S_BEZ_MAPY
            ef = min(dt, k * krok)
            marsz += ef
        j = bisect.bisect_right(po_t, a["t"]) - 1
        if j >= 0 and a["t"] < postoje[j][1]:
            postoj_s += dt
        # ogień: ostatni wpis [OGIEN] przed oknem, ważny OGIEN_WAZNY_S
        i = bisect.bisect_right(og_t, a["t"]) - 1
        if i >= 0 and a["t"] - ogien[i][0] <= OGIEN_WAZNY_S and ogien[i][1] in (None, pa[2]):
            if any(_cheb((x, y), pa) <= OGIEN_PROMIEN or _cheb((x, y), pb) <= OGIEN_PROMIEN for x, y in ogien[i][2]):
                ogien_s += dt - ef
                og_dt += dt
                continue
        bez_dt += dt
        bez_strata += dt - ef
    wynik["idz_patrol_s"] = idz
    wynik["marsz_efektywny"] = marsz / idz if idz else None
    tlo = bez_strata / bez_dt if bez_dt else 0.0
    wynik["ogien_strata"] = max(0.0, ogien_s - tlo * og_dt) / idz if idz else None
    wynik["ogien_okna_s"] = og_dt
    wynik["ogien_logi"] = bool(ogien)
    # wizyty patrolu
    cele = [r for r in rek if r.get("typ") == "patrol_cel"]
    cele_t = [r["t"] for r in cele]
    start_t = sorted(r["t"] for r in rek if r.get("typ") == "pietra_start")
    pos_t = sorted(r["t"] for r in rek if r.get("typ") == "poscig_start")
    s_pole_schody, s_pole_zwykle = [], []
    na_miejscu = 0.0
    wizyt = 0
    for v in w:
        if v.get("typ") != "patrol_wizyta":
            continue
        wizyt += 1
        na_miejscu += v.get("na_miejscu_s") or 0.0
        if not v.get("dotarl") or v.get("zabicia_droga") or not v.get("dojscie_s"):
            continue
        poczatek = v["t"] - (v.get("na_miejscu_s") or 0.0) - v["dojscie_s"]
        i = bisect.bisect_right(cele_t, poczatek + 1.0) - 1
        if i < 0 or cele[i].get("id") != v.get("id") or not cele[i].get("droga"):
            continue
        # bez pościgu w trakcie dojścia
        j = bisect.bisect_left(pos_t, poczatek)
        if j < len(pos_t) and pos_t[j] <= v["t"]:
            continue
        spp = v["dojscie_s"] / cele[i]["droga"]
        j = bisect.bisect_left(start_t, cele[i]["t"] - 1.0)
        ze_schodami = j < len(start_t) and start_t[j] <= v["t"]
        (s_pole_schody if ze_schodami else s_pole_zwykle).append((v["dojscie_s"], cele[i]["droga"]))
    def agreguj(lst):
        if not lst:
            return {"n": 0, "mediana": None, "suma": None}
        return {"n": len(lst), "mediana": _mediana([a / b for a, b in lst]),
                "suma": sum(a for a, _ in lst) / sum(b for _, b in lst)}
    wynik["wizyt"] = wizyt
    wynik["s_na_pole_schody"] = agreguj(s_pole_schody)
    wynik["s_na_pole_zwykle"] = agreguj(s_pole_zwykle)
    wynik["postoj_patrolu"] = postoj_s / idz if idz else None
    # przejścia pięter
    krok_ev = [r for r in w if r.get("typ") == "pietra_krok"]
    starty = [r for r in rek if r.get("typ") == "pietra_start"]
    st_t = [r["t"] for r in starty]
    czasy, pierwsza = [], 0
    for k in krok_ev:
        if k.get("proba") == 1:
            pierwsza += 1
        i = bisect.bisect_right(st_t, k["t"]) - 1
        while i >= 0 and (starty[i].get("z_od"), starty[i].get("z_do")) != (k.get("z_od"), k.get("z_do")):
            i -= 1
            if i >= 0 and k["t"] - st_t[i] > 120:
                i = -1
        if i >= 0 and 0 <= k["t"] - st_t[i] <= 120:
            czasy.append(k["t"] - st_t[i])
    wynik["przejscia"] = len(krok_ev)
    wynik["przejscia_pierwsza"] = pierwsza
    wynik["przejscia_pierwsza_proc"] = pierwsza / len(krok_ev) if krok_ev else None
    wynik["przejscie_czas_sr"] = sum(czasy) / len(czasy) if czasy else None
    wynik["przejscie_czas_n"] = len(czasy)
    wynik["pietra_porazki"] = sum(1 for r in w if r.get("typ") == "pietra_blad" and r.get("rodzaj") == "porazka")
    # odpuszczenia
    odp = [r for r in w if r.get("typ") == "odpuszczenie"]
    wynik["odpuszczenia"] = len(odp)
    wynik["odpuszczenia_za_sciana"] = sum(1 for r in odp if str(r.get("powod", "")).startswith("za ścianą"))
    # bezpieczeństwo i wynik gry
    for k in ("utkniecie", "utkniecie_trasa", "watchdog_bezczynnosc", "zabicie", "ruch_okno"):
        wynik["n_" + k] = sum(1 for r in w if r.get("typ") == k)
    hp = [r["hp"] for r in probki if isinstance(r.get("hp"), (int, float))]
    wynik["hp_min"] = min(hp) if hp else None
    exp = [(r["t"], r["exp"]) for r in probki if isinstance(r.get("exp"), (int, float))]
    wynik["exp_h"] = (exp[-1][1] - exp[0][1]) / ((exp[-1][0] - exp[0][0]) / 3600) if len(exp) > 1 and exp[-1][0] > exp[0][0] else None
    # ruch_okno (R0b)
    ro = [r for r in w if r.get("typ") == "ruch_okno"]
    if ro:
        m_idz = sum(r.get("stany", {}).get("IDZ", [0, 0])[0] for r in ro)
        s_idz = sum(r.get("stany", {}).get("IDZ", [0, 0])[1] for r in ro)
        przyczyny = {}
        for r in ro:
            for k, v in (r.get("powody_idz_s") or {}).items():
                przyczyny[k] = przyczyny.get(k, 0.0) + v
        wynik["ruch_okno"] = {
            "okien": len(ro), "idz_s": m_idz + s_idz, "marsz_idz": m_idz / (m_idz + s_idz) if m_idz + s_idz else None,
            "luki": sum(r.get("luki", 0) for r in ro), "luki_s": sum(r.get("luki_s", 0.0) for r in ro),
            "kliki": sum(r.get("kliki", 0) for r in ro), "strzalki": sum(r.get("strzalki", 0) for r in ro),
            "kroki": sum(r.get("kroki", 0) for r in ro), "stoi_idz_powody_s": {k: round(v, 1) for k, v in sorted(przyczyny.items())}}
    return wynik


# --- wyjście ---
def _p(v, d=1):
    return "-" if v is None else f"{100 * v:.{d}f}%"


def _f(v, d=2):
    return "-" if v is None else f"{v:.{d}f}"


def wiersze(m):
    """[(nazwa metryki, tekst, cel po R1)] dla jednego okna."""
    sch, zw = m["s_na_pole_schody"], m["s_na_pole_zwykle"]
    return [
        ("Efektywny marsz w IDZ (patrol)", _p(m["marsz_efektywny"]), ">= 60%"),
        ("Sekundy na pole, wizyta ze schodami (mediana; suma/suma; n)",
         f"{_f(sch['mediana'])}; {_f(sch['suma'])}; {sch['n']}", "<= 0,70"),
        ("Sekundy na pole, wizyta bez schodów (mediana; suma/suma; n)",
         f"{_f(zw['mediana'])}; {_f(zw['suma'])}; {zw['n']}", "(odniesienie 0,55)"),
        ("Ogień: strata czasu IDZ (ponad sufit marszu)" + ("" if m["ogien_logi"] else " (brak logów [OGIEN])"), _p(m["ogien_strata"]), "< 4%"),
        ("Przejścia z udaną 1. próbą", f"{m['przejscia_pierwsza']}/{m['przejscia']} ({_p(m['przejscia_pierwsza_proc'], 0)})", "90%"),
        ("Średni czas przejścia (s; n)", f"{_f(m['przejscie_czas_sr'], 1)}; {m['przejscie_czas_n']}", "1,5 s"),
        ("Odpuszczenia za ścianą (z wszystkich; na godz.)",
         f"{m['odpuszczenia_za_sciana']} ({m['odpuszczenia']}); {_f(m['odpuszczenia_za_sciana'] / (m['okno_s'] / 3600), 1)}/h", "-70%"),
        ("Postój na miejscu patrolu", _p(m["postoj_patrolu"]), "bez zmian"),
        ("Czas IDZ w patrolu (s) / wizyt", f"{m['idz_patrol_s']:.0f} / {m['wizyt']}", ""),
        ("Utknięcia / watchdog / porażki pięter", f"{m['n_utkniecie']} / {m['n_watchdog_bezczynnosc']} / {m['pietra_porazki']}", "nie rośnie"),
        ("HP min (%) / exp na godz. (z próbek)", f"{_f(m['hp_min'], 0)} / {_f(m['exp_h'], 0)}", "exp nie niżej"),
    ]


def drukuj(nazwy, wyniki, odrzucone):
    print("# Porównanie ruchu")
    for n, (okno, m, o) in zip(nazwy, wyniki):
        print(f"- {n}: {datetime.datetime.fromtimestamp(okno[0]):%Y-%m-%d %H:%M} do {datetime.datetime.fromtimestamp(okno[1]):%Y-%m-%d %H:%M}"
              f" ({(okno[1] - okno[0]) / 3600:.2f} h), próbek {m['probek']}, odfiltrowano {o}")
    kol = [wiersze(m) for _, m, _ in wyniki]
    print()
    print("| Metryka | " + " | ".join(nazwy) + (" | Cel po R1 |"))
    print("|---|" + "---|" * len(nazwy) + "---|")
    for i, (nazwa, _, cel) in enumerate(kol[0]):
        print(f"| {nazwa} | " + " | ".join(k[i][1] for k in kol) + f" | {cel} |")
    for n, (_, m, _) in zip(nazwy, wyniki):
        ro = m.get("ruch_okno")
        if ro:
            print(f"\nruch_okno {n}: okien {ro['okien']}, marsz/IDZ {_p(ro['marsz_idz'])}, luki {ro['luki']} ({ro['luki_s']:.0f} s), "
                  f"kliki {ro['kliki']}, strzałki {ro['strzalki']}, kroki {ro['kroki']}, stanie w IDZ wg przyczyn {ro['stoi_idz_powody_s']}")


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    katalog = None
    if "--logi" in argv:
        katalog = argv[argv.index("--logi") + 1]
        args = [a for a in args if a != katalog]
    if not 1 <= len(args) <= 2:
        print(__doc__)
        return 2
    try:
        okna = [parsuj_okno(a) for a in args]
    except ValueError as e:
        print("błąd:", e)
        return 2
    M = _mapa()
    wyniki = []
    for okno in okna:
        rek = wczytaj_telemetrie(okno[0], okno[1], katalog)
        czyste, odrz = filtruj_szum(rek)
        ogien = wczytaj_ogien(okno[0], okno[1], katalog)
        wyniki.append((okno, policz(czyste, okno[0], okno[1], ogien, M), odrz))
    nazwy = ["A", "B"][:len(okna)]
    if "--json" in argv:
        print(json.dumps([{"okno": list(o), "metryki": m, "odfiltrowane": d} for o, m, d in wyniki], ensure_ascii=False, indent=1))
    else:
        drukuj(nazwy, wyniki, [d for _, _, d in wyniki])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
