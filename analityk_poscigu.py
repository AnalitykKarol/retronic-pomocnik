"""Analityk POŚCIGU: osobny wątek obok Obserwatora (analityk.py). Co ~120 s liczy w Pythonie statystyki
pościgu (zdarzenia poscig_start/poscig_koniec, próbki, utknięcia, epizody celu) z okien 5 i 30 min,
a Haiku (`claude -p --model haiku`, bez narzędzi; klasa Claude z mozg.py) tylko interpretuje je i zwraca
wnioski. WYŁĄCZNIE wnioski: żadnych zmian pokręteł (błąd z POGON_LIMIT=8).

Zapis: logi/poscig-wnioski.md (czytelny, przyrostowy, deduplikacja, rotacja do 200 KB),
logi/poscig-wnioski.jsonl (maszynowy), status `problem` -> linia w logi/obserwator-alerty.log
(dedup 10 min) + powiadomienie (max 1/10 min).

`python3 -I analityk_poscigu.py --raz [--od GG:MM] [--bez-modelu]`: jedna analiza istniejących danych,
nic nie zapisuje do logi/ i nie powiadamia (debug).

Uwaga o danych: w trakcie pościgu pętla nie zapisuje próbek telemetrii, więc oscylacje A-B-A-B
widać tylko w próbkach przed/po pościgu i w zwykłych tickach (WALKA/IDZ); postęp samego pościgu
mierzą odl_start/odl_koniec i kroki."""
import hashlib
import json
import os
import re
import sys
import threading
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # python3 -I nie dodaje katalogu skryptu

import instancja  # noqa: E402
import powiadom  # noqa: E402
import telemetria  # noqa: E402

LOGI = instancja.S.logi
CYKL_S = 120
CYKL_MIN_S = 60
LIMIT_H = 30
OKNO_KROTKIE_S = 300
OKNO_DLUGIE_S = 1800
MIN_POSCIGOW = 3                 # tyle pościgów w oknie 5 min uruchamia model
OSC_OKNO_S = 3.5                 # A-B-A-B w tym czasie (próbki co >=1 s: 4 próbki = min 3,0 s)
OSC_PRZYKLADY = 5
MIN_KROKOW_BEZ_POSTEPU = 3
MD_MAX = 200 * 1024
ALERT_DEDUP_S = 600
POWIADOM_S = 600
PODOBNE = 0.6                    # próg podobieństwa wniosków (Jaccard na słowach)
KROK_S_NA_PREDKOSC = 0.047       # jak cavebot.POSCIG_KROK_S_NA_PREDKOSC (s kroku na jednostkę prędkości pola)
SUKCES = ("odl<=1", "cel_martwy")
GUBIENIE = ("cel_znikl",)
OCENY = ("ok", "uwaga", "problem")
POWODY_ZDARZEN = ("obcy_gracz", "gryzacy", "hp_spadek", "oscylacja")   # nowy pościg z takim powodem = "nowe zdarzenie"

SYSTEM = (
    "Jesteś analitykiem POŚCIGU w bocie do gry Tibia 7.4. Pościg to pętla cavebota, która biegnie za "
    "uciekającym potworem (zwykle słaby, z niskim HP) i dobija go. powody: odl<=1 i cel_martwy = dobicie; cel_znikl = zgubienie; okno i brak_ruchu = bez dojścia (czas pętli minął albo postać stoi, cel nadal daleko). Dostajesz statystyki liczone kodem "
    "(wiarygodne) z okna krótkiego i długiego: kroki_na_s per tryb (trzymaj = klawisz trzymany, stuk = "
    "pojedyncze naciśnięcia), powody wyjść, odrzucone/wysłane, zmiany_kierunku, trzymane_s, odległość "
    "start->koniec, kroki bez postępu, oscylacje pozycji A-B-A-B, utknięcia z prędkością pola, najgorsze "
    "pościgi z kontekstem i różnice trzymaj vs stuk (gdy oba były w użyciu). Wyciągnij wnioski o tym, "
    "DLACZEGO pościg bywa nieskuteczny, oparte na liczbach z danych; nie zmyślaj, nie powtarzaj "
    "ostatnich_wnioskow bez nowej przesłanki. Małe próby (n<5) zaznacz niską pewnością. "
    "ocena: ok (pościg działa dobrze), uwaga (coś odbiega), problem (wyraźna utrata dobić lub błąd). "
    "NIE proponuj zmiany wartości pokręteł jako gotowej akcji i nie skracaj pościgu: propozycja to opis "
    "zmiany stałej lub funkcji w kodzie (np. nazwa stałej i kierunek), do rozważenia przez człowieka. "
    "Odpowiedz WYŁĄCZNIE jednym obiektem JSON: "
    '{"ocena":"ok|uwaga|problem","wnioski":[{"co":"1 zdanie","dowod":"liczby z danych",'
    '"skutek":"co to kosztuje","propozycja":"stała/funkcja i kierunek zmiany","pewnosc":0.0-1.0}],'
    '"hipotezy_do_zmierzenia":["co dodatkowo zmierzyć, żeby to rozstrzygnąć"]}. '
    "Najwyżej 5 wniosków; pusta lista jest poprawna."
)


# ---------------------------------------------------------------------------------------------
# statystyki (czysty Python)
# ---------------------------------------------------------------------------------------------
def _med(l):
    return telemetria._mediana(list(l))


def _kwantyl(l, q):
    """Kwantyl metodą najbliższego rankingu (q 0..1) albo None."""
    l = sorted(l)
    if not l:
        return None
    return l[min(len(l) - 1, max(0, int(round(q * (len(l) - 1)))))]


def _r(x, n=2):
    return None if x is None else round(x, n)


def _hash(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


def norm(s):
    return re.sub(r"\W+", " ", str(s).lower()).strip()


def slowa(s):
    return {w for w in norm(s).split() if len(w) >= 4}


def podobne(a, b, prog=PODOBNE):
    na, nb = norm(a), norm(b)
    if na == nb:
        return True
    sa, sb = slowa(a), slowa(b)
    if not sa or not sb:
        return False
    return len(sa & sb) / len(sa | sb) >= prog


def pole_info(mapa, poz):
    """Prędkość pola z mapy (najwolniejsze z pola i 4 sąsiadów, jak cavebot._czas_kroku) albo None."""
    if mapa is None or not poz or not hasattr(mapa, "pole"):
        return None
    try:
        v = 0
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            p = mapa.pole(poz[0] + dx, poz[1] + dy, poz[2])
            if p and 0 < p[2] <= 60:
                v = max(v, p[2])
        if not v:
            return None
        return {"v": v, "krok_s": round(v * KROK_S_NA_PREDKOSC, 2)}
    except Exception:
        return None


def poscigi(rek):
    """Paruje poscig_start z poscig_koniec. -> lista dict (koniec + 't0', 'start' = rekord startu albo None),
    posortowana po czasie końca. Rekord bez startu też jest zwracany."""
    out, start = [], None
    for r in sorted((r for r in rek if r.get("typ") in ("poscig_start", "poscig_koniec")), key=lambda r: r["t"]):
        if r["typ"] == "poscig_start":
            start = r
            continue
        czas = r.get("czas") or 0
        s = start if start and start.get("cel") == r.get("cel") and r["t"] - start["t"] <= czas + 3 else None
        start = None
        d = dict(r)
        d["t0"] = round(r["t"] - czas, 1)
        d["start"] = s
        out.append(d)
    return out


def oscylacje(probki, okno_s=OSC_OKNO_S):
    """Pozycja gracza wraca A-B-A-B w <= okno_s s (z kolejnych próbek). Nakładające się wzorce
    (A-B-A-B-A-B) liczą się jako jedna oscylacja. -> [{"t","poz":[A,B]}...]."""
    p = [(r["t"], tuple(r["poz"])) for r in sorted(probki, key=lambda r: r["t"]) if r.get("poz")]
    wynik, i = [], 0
    while i + 3 < len(p):
        a0, b0, a1, b1 = p[i], p[i + 1], p[i + 2], p[i + 3]
        if a0[1] == a1[1] and b0[1] == b1[1] and a0[1] != b0[1] and a0[1][2:] == b0[1][2:] \
                and b1[0] - a0[0] <= okno_s:
            j = i + 4
            while j < len(p) and p[j][1] == (a0[1] if (j - i) % 2 == 0 else b0[1]):
                j += 1
            wynik.append({"t": a0[0], "poz": [list(a0[1][:2]), list(b0[1][:2])], "probek": j - i,
                          "czas_s": round(p[j - 1][0] - a0[0], 1)})
            i = j - 1
        else:
            i += 1
    return wynik


def _grupa(lst):
    """Statystyki zbioru pościgów jednego trybu."""
    if not lst:
        return None
    dlugie = [p for p in lst if (p.get("czas") or 0) >= 1.0 and (p.get("kroki") or 0) >= 2]
    ks = [p["kroki_na_s"] for p in dlugie if p.get("kroki_na_s") is not None]
    czas = sum(p.get("czas") or 0 for p in lst)
    kroki = sum(p.get("kroki") or 0 for p in lst)
    wys = sum(p.get("wyslane") or 0 for p in lst)
    odrz = sum(p.get("odrzucone") or 0 for p in lst)
    trz = sum(p.get("trzymane_s") or 0 for p in lst)
    zk = sum(p.get("zmiany_kierunku") or 0 for p in lst)
    lat = [p["lat_med"] for p in lst if p.get("lat_med") is not None]
    dec = [p["dec_med"] for p in lst if p.get("dec_med") is not None]
    return {
        "n": len(lst), "n_do_tempa": len(dlugie), "kroki": kroki, "czas_s": _r(czas, 1),
        "kroki_na_s": {"med": _r(_med(ks)), "p10": _r(_kwantyl(ks, 0.1)), "p90": _r(_kwantyl(ks, 0.9))},
        "kroki_na_s_ogolem": _r(kroki / czas) if czas > 0 else None,
        "wyslane": wys, "odrzucone": odrz,
        "odrzucone_proc": round(100 * odrz / wys) if wys else None,
        "ponow_brak": sum(p.get("ponow_brak") or 0 for p in lst),
        "zmiany_kierunku": zk, "zmiany_kierunku_na_krok": _r(zk / kroki) if kroki else None,
        "trzymane_s": _r(trz, 1), "trzymane_proc_czasu": round(100 * trz / czas) if czas > 0 and trz else None,
        "naciski_z_postoju": max(0, wys - zk) if any(p.get("tryb") == "trzymaj" for p in lst) else None,
        "lat_med_s": _r(_med(lat), 3), "dec_med_s": _r(_med(dec), 3),
    }


def _koniec(p):
    """'dobicie' | 'zgubienie' | 'bez_dojscia' (okno/brak_ruchu: cel nadal daleko) | 'przerwane' (obcy gracz,
    gryzący, spadek HP, objazd itd.) wg powodu końca pościgu."""
    if p.get("powod") in SUKCES:
        return "dobicie"
    if p.get("powod") in GUBIENIE:
        return "zgubienie"
    if p.get("powod") in ("okno", "brak_ruchu"):
        return "bez_dojscia"
    return "przerwane"


def bez_postepu(p):
    return (p.get("kroki") or 0) >= MIN_KROKOW_BEZ_POSTEPU and p.get("odl_koniec") is not None \
        and p.get("odl_start") is not None and p["odl_koniec"] >= p["odl_start"]


def stat_okna(rek, mapa=None):
    """Statystyki pościgu z listy rekordów jednego okna."""
    ps = poscigi(rek)
    probki = [r for r in rek if r["typ"] == "probka"]
    tryby = {}
    for p in ps:
        tryby.setdefault(p.get("tryb") or "brak_pola", []).append(p)
    kon = Counter(_koniec(p) for p in ps)
    n = len(ps)
    od = [p["odl_start"] for p in ps if p.get("odl_start") is not None]
    do = [p["odl_koniec"] for p in ps if p.get("odl_koniec") is not None]
    delta = [p["odl_koniec"] - p["odl_start"] for p in ps
             if p.get("odl_start") is not None and p.get("odl_koniec") is not None]
    bp = [p for p in ps if bez_postepu(p)]
    osc = oscylacje(probki)
    n_osc_wyj = sum(1 for p in ps if p.get("powod") == "oscylacja")   # bezpiecznik cavebota też wykrył oscylację
    utk = [r for r in rek if r["typ"] == "utkniecie"]
    utk_o = []
    for u in utk[-6:]:
        pi = pole_info(mapa, u.get("poz"))
        utk_o.append({"godz": time.strftime("%H:%M:%S", time.localtime(u["t"])), "stan": u.get("stan"),
                      "poz": u.get("poz"), "s": u.get("s"), "stwory": u.get("stwory"), "pole": pi})
    trzymaj = tryby.get("trzymaj") or []
    puszczanie = None
    if trzymaj:
        g = _grupa(trzymaj)
        puszczanie = {"trzymane_proc_czasu": g["trzymane_proc_czasu"],
                      "naciski_z_postoju": g["naciski_z_postoju"],
                      "zmiany_kierunku_na_krok": g["zmiany_kierunku_na_krok"],
                      "naciski_z_postoju_na_poscig": _r(g["naciski_z_postoju"] / len(trzymaj))}
    dob = telemetria.dobicie([r for r in rek if r["typ"] == "epizod_celu"], ref_exp={})
    return {
        "poscigow": n,
        "tryby": {k: _grupa(v) for k, v in tryby.items()},
        "powody_wyjsc": dict(Counter(p.get("powod") for p in ps).most_common(8)),
        "koniec": {"dobicie": kon["dobicie"], "zgubienie": kon["zgubienie"],
                   "bez_dojscia_okno_lub_brak_ruchu": kon["bez_dojscia"], "przerwane_inne": kon["przerwane"],
                   "dobicie_proc": round(100 * kon["dobicie"] / n) if n else None,
                   "zgubienie_proc": round(100 * kon["zgubienie"] / n) if n else None},
        "odleglosc": {"start_med": _med(od), "koniec_med": _med(do),
                      "delta_med": _med(delta), "wzrosla_pościgow": sum(1 for d in delta if d > 0)},
        "bez_postepu": {"poscigow": len(bp), "kroki": sum(p["kroki"] for p in bp)},
        "oscylacje": {"liczba": len(osc) + n_osc_wyj, "z_probek": len(osc), "z_wyjscia_pocigu": n_osc_wyj,
                      "przyklady": osc[-OSC_PRZYKLADY:]},
        "utkniecia": {"liczba": len(utk), "ostatnie": utk_o},
        "puszczanie_klawisza": puszczanie,
        "epizody_celu": {k: dob[k] for k in ("epizody", "zabite", "porzucone", "zgubione", "wskaznik", "powod_top")},
    }


def roznice_trybow(okno):
    """Różnice trzymaj vs stuk, gdy oba w oknie. None, gdy brak któregoś (albo brak pola `tryb`)."""
    t = okno.get("tryby") or {}
    a, b = t.get("trzymaj"), t.get("stuk")
    if not a or not b:
        return None
    def k(g):
        return g["kroki_na_s"]["med"]
    wyn = {"n": {"trzymaj": a["n"], "stuk": b["n"]}}
    if k(a) is not None and k(b) is not None:
        wyn["kroki_na_s_med"] = {"trzymaj": k(a), "stuk": k(b), "roznica": _r(k(a) - k(b))}
    wyn["kroki_na_s_ogolem"] = {"trzymaj": a["kroki_na_s_ogolem"], "stuk": b["kroki_na_s_ogolem"]}
    wyn["lat_med_s"] = {"trzymaj": a["lat_med_s"], "stuk": b["lat_med_s"]}
    wyn["odrzucone_proc"] = {"trzymaj": a["odrzucone_proc"], "stuk": b["odrzucone_proc"]}
    wyn["zmiany_kierunku_na_krok"] = {"trzymaj": a["zmiany_kierunku_na_krok"], "stuk": b["zmiany_kierunku_na_krok"]}
    wyn["uwaga"] = "mało pościgów na tryb: ostrożnie" if min(a["n"], b["n"]) < 5 else None
    return wyn


def najgorsze(rek, mapa=None, ile=5):
    """Najgorsze pościgi z kontekstem: cel, HP celu, pole (prędkość), droga (A*), stan postaci."""
    probki = sorted((r for r in rek if r["typ"] == "probka"), key=lambda r: r["t"])
    wyn = []
    for p in poscigi(rek):
        czas = p.get("czas") or 0
        score = 0.0
        if bez_postepu(p):
            score += 3
        if p.get("powod") in ("brak_ruchu", "cel_znikl", "objazd", "oscylacja"):
            score += 2
        score += p.get("odrzucone") or 0
        if czas >= 2 and (p.get("kroki_na_s") or 0) < 0.8:
            score += 1
        if p.get("odl_start") is not None and p.get("odl_koniec") is not None:
            score += max(0, p["odl_koniec"] - p["odl_start"])
        score += czas / 10
        if p.get("powod") in SUKCES:
            score -= 2
        wyn.append((score, p))
    wyn.sort(key=lambda x: (-x[0], -x[1]["t"]))
    out = []
    for score, p in wyn[:ile]:
        if score <= 0:
            break
        ost = None
        for r in probki:
            if r["t"] <= p["t0"] + 0.5:
                ost = r
            else:
                break
        ctx = {}
        if ost is not None and p["t0"] - ost["t"] <= 10:
            cel = next((w for w in ost.get("stwory", []) if w.get("cel")), None)
            if cel is None:
                cel = next((w for w in ost.get("stwory", []) if w.get("n") == p.get("cel") and not w.get("gracz")),
                           None)
            ctx = {"poz": ost.get("poz"), "stan": ost.get("stan"), "hp_gracza": ost.get("hp"),
                   "pole": pole_info(mapa, ost.get("poz")),
                   "cel_dxdy": [cel["dx"], cel["dy"]] if cel else None,
                   "droga": cel.get("droga") if cel else None,
                   "osiagalny": cel.get("osiagalny") if cel else None}
            ctx = {k: v for k, v in ctx.items() if v is not None}
        w = {"godz": time.strftime("%H:%M:%S", time.localtime(p["t0"])), "cel": p.get("cel"),
             "hp_celu": (p.get("start") or {}).get("hp_celu"), "tryb": p.get("tryb"),
             "powod": p.get("powod"), "kroki": p.get("kroki"), "czas": p.get("czas"),
             "kroki_na_s": p.get("kroki_na_s"), "odl": [p.get("odl_start"), p.get("odl_koniec")],
             "odrzucone": p.get("odrzucone"), "zmiany_kier": p.get("zmiany_kierunku"),
             "lat_med": p.get("lat_med"), "ocena_zlego": round(score, 1), **ctx}
        out.append({k: v for k, v in w.items() if v is not None})
    return out


def niespojnosci(d):
    """Sprawdza własne dane wejścia (czy agregacja nie jest zepsuta). -> lista opisów (pusta = spójne)."""
    k, l = d["okno_krotkie"], d["okno_dlugie"]
    wyn = []
    if l["poscigow"] < k["poscigow"]:
        wyn.append("okno długie ma mniej pościgów niż krótkie")
    if l["poscigow"] and k["poscigow"] == l["poscigow"] and l.get("tryby") == k.get("tryby") \
            and (l.get("pokrycie_s") or 0) > OKNO_KROTKIE_S + 60:
        wyn.append("okno długie identyczne z krótkim mimo szerszego zakresu danych")
    for o in (k, l):
        if (o["powody_wyjsc"].get("oscylacja", 0)) > o["oscylacje"]["liczba"]:
            wyn.append("powód oscylacja w pościgach, a liczba oscylacji mniejsza")
    return wyn


RE_WLASNA_NIESPOJNOSC = re.compile(r"niesp[óo]jn|identyczn|błąd agregacji|blad agregacji|agregacj", re.I)


def zdarzenia_do_hasha(rek):
    """Rekordy, których pojawienie się zmienia obraz pościgu: koniec pościgu, utknięcie."""
    return sorted((r["typ"], r["t"]) for r in rek if r["typ"] in ("poscig_koniec", "utkniecie"))


# ---------------------------------------------------------------------------------------------
# walidacja odpowiedzi modelu
# ---------------------------------------------------------------------------------------------
def _txt(x, n):
    return re.sub(r"\s+", " ", str(x if x is not None else "")).strip()[:n]


def waliduj(tekst):
    """Odpowiedź modelu -> {"ocena","wnioski":[{co,dowod,skutek,propozycja,pewnosc}],"hipotezy":[str]}
    albo None (nie-JSON, zła ocena, zły kształt). Wniosek bez `co` jest odrzucany, pewność ścinana do 0..1,
    wnioski max 5, hipotezy max 5."""
    m = re.search(r"\{.*\}", tekst or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m[0])
    except ValueError:
        return None
    if not isinstance(d, dict):
        return None
    ocena = str(d.get("ocena", "")).strip().lower()
    if ocena not in OCENY:
        return None
    sur = d.get("wnioski", [])
    if not isinstance(sur, list):
        return None
    wnioski = []
    for w in sur:
        if not isinstance(w, dict):
            continue
        co = _txt(w.get("co"), 220)
        if not co:
            continue
        try:
            pew = float(w.get("pewnosc", 0))
            if pew != pew:        # NaN
                pew = 0.0
        except (TypeError, ValueError):
            pew = 0.0
        wnioski.append({"co": co, "dowod": _txt(w.get("dowod"), 260), "skutek": _txt(w.get("skutek"), 200),
                        "propozycja": _txt(w.get("propozycja"), 320), "pewnosc": round(min(1.0, max(0.0, pew)), 2)})
    hip = d.get("hipotezy_do_zmierzenia", [])
    hip = [_txt(h, 200) for h in hip if _txt(h, 1)] if isinstance(hip, list) else []
    return {"ocena": ocena, "wnioski": wnioski[:5], "hipotezy": hip[:5]}


# ---------------------------------------------------------------------------------------------
# analityk
# ---------------------------------------------------------------------------------------------
def _wczytaj_ogon(plik, od_t, do_t, max_b=8 * 1024 * 1024):
    """Rekordy z pliku telemetrii o czasie w [od_t, do_t): czyta tylko końcówkę (max_b)."""
    plik = Path(plik)
    wyn = []
    try:
        with plik.open("rb") as f:
            rozm = f.seek(0, 2)
            if rozm > max_b:
                f.seek(rozm - max_b)
                f.readline()
            else:
                f.seek(0)
            for b in f:
                try:
                    r = json.loads(b)
                except ValueError:
                    continue
                if isinstance(r, dict) and "t" in r and "typ" in r and od_t <= r["t"] < do_t:
                    wyn.append(r)
    except OSError:
        pass
    return wyn


def _przytnij_plik(plik, max_b=MD_MAX, nagl=b"\n## "):
    """Rotacja: plik > max_b -> zostaje ostatnie ~połowa, ucięta na granicy wpisu (md) albo linii (jsonl)."""
    try:
        if plik.stat().st_size <= max_b:
            return
        dane = plik.read_bytes()[-max_b // 2:]
        sep = nagl if plik.suffix == ".md" else b"\n"
        i = dane.find(sep)
        dane = dane[i + 1:] if i >= 0 else dane
        plik.write_bytes(dane)
    except OSError:
        pass


class AnalitykPoscigu:
    """model(prompt, system) -> (tekst, meta). `mapa`: obiekt z .pole(x,y,z) albo None. `zapis`: False w --raz."""

    def __init__(self, tele, model, log=print, zegar=time.time, logi=LOGI, cykl_s=None, limit_h=LIMIT_H,
                 mapa=None, zapis=True, powiadamiaj=True):
        self.tele, self.model, self.log, self.zegar = tele, model, log, zegar
        self.logi = Path(logi)
        if cykl_s is None:
            try:
                cykl_s = float(os.environ.get("RETRONIC_POSCIG_ANALITYK_S", CYKL_S))
            except ValueError:
                cykl_s = CYKL_S
        self.cykl_s = max(CYKL_MIN_S, cykl_s)
        self.limit_h, self.mapa = limit_h, mapa
        self.zapis, self.powiadamiaj = zapis, powiadamiaj
        self.nastepne = self.zegar() + self.cykl_s
        self.podpis = None
        self.znak = float("-inf")        # czas najnowszego zdarzenia uwzględnionego w ostatniej analizie
        self.wywolania = []
        self.koszt = 0.0
        self.koniec = False
        self.pominiete = 0
        self.ocena = None                # ostatnia ocena (do md)
        self.znane = []                  # [(co, pewnosc)] wnioski już zapisane (dedup)
        self.hip_znane = []
        self.ostatnie_co = []            # 3 ostatnie wnioski do promptu
        self.alerty = {}                 # norm -> czas
        self.ost_powiad = float("-inf")
        if zapis:
            self._wczytaj_znane()

    # --- stan z dysku ---
    def _wczytaj_znane(self):
        try:
            linie = (self.logi / "poscig-wnioski.jsonl").read_text().splitlines()[-60:]
        except OSError:
            return
        for l in linie:
            try:
                r = json.loads(l)
            except ValueError:
                continue
            for w in r.get("wnioski", []):
                if w.get("co"):
                    self.znane.append(w["co"])
            self.hip_znane += [h for h in r.get("hipotezy", []) if h]
            self.ocena = r.get("ocena", self.ocena)
        self.znane, self.hip_znane = self.znane[-60:], self.hip_znane[-60:]
        self.ostatnie_co = self.znane[-3:]

    # --- wejście ---
    def _rekordy(self, teraz):
        """Rekordy z ostatnich 30 min: pamięć telemetrii (od startu procesu) uzupełniona z plików dnia,
        gdy pamięć nie sięga tak daleko wstecz (np. po restarcie bota)."""
        rek = list(self.tele.rek)
        od = teraz - OKNO_DLUGIE_S
        if rek and rek[0]["t"] <= od + 5:
            return rek
        granica = rek[0]["t"] if rek else float("inf")
        try:
            kat = Path(self.tele.katalog)
            pliki = {self.tele._plik(teraz), self.tele._plik(od)}
            stare = []
            for pl in sorted(pliki):
                stare += [r for r in _wczytaj_ogon(pl, od, granica)]
        except Exception:
            return rek
        return sorted(stare + rek, key=lambda r: r["t"])

    def wejscie(self, teraz):
        wszystkie = self._rekordy(teraz)
        kr = [r for r in wszystkie if r["t"] >= teraz - OKNO_KROTKIE_S]
        dl = [r for r in wszystkie if r["t"] >= teraz - OKNO_DLUGIE_S]
        s_kr, s_dl = stat_okna(kr, self.mapa), stat_okna(dl, self.mapa)
        d = {"okno_krotkie": {"sekundy": OKNO_KROTKIE_S, **s_kr},
             "okno_dlugie": {"sekundy": OKNO_DLUGIE_S, **s_dl},
             "roznice_trybow": roznice_trybow(s_dl) or roznice_trybow(s_kr),
             "najgorsze_poscigi": najgorsze(dl, self.mapa, 5),
             "ostatnie_wnioski": self.ostatnie_co[-3:]}
        d["okno_dlugie"]["pokrycie_s"] = round(teraz - dl[0]["t"]) if dl else 0
        d["niespojnosci"] = niespojnosci(d)
        if d["niespojnosci"]:
            d["uwaga_dane"] = "dane niespójne: nie podnoś oceny do problem z ich powodu"
        return d, kr

    def wymaga_modelu(self, kr):
        """-> (czy wołać, powód). >=3 pościgi w oknie 5 min albo nowe zdarzenie (utknięcie, oscylacja,
        pościg przerwany przez obcego gracza/gryzącego/spadek HP) od ostatniej analizy."""
        nowe = [r for r in kr if r["t"] > self.znak and r["typ"] in ("poscig_koniec", "utkniecie")]
        if not nowe:
            return False, "brak_nowych"
        n = sum(1 for r in kr if r["typ"] == "poscig_koniec")
        if n >= MIN_POSCIGOW:
            return True, f"{n}_poscigow"
        if any(r["typ"] == "utkniecie" or r.get("powod") in POWODY_ZDARZEN for r in nowe):
            return True, "zdarzenie"
        if oscylacje([r for r in kr if r["typ"] == "probka"]):
            return True, "oscylacja"
        return False, "za_malo"

    # --- cykl ---
    def obieg(self):
        teraz = self.zegar()
        if teraz < self.nastepne:
            return None
        self.nastepne = teraz + self.cykl_s
        return self.cykl(teraz)

    def cykl(self, teraz, wymus=False):
        d, kr = self.wejscie(teraz)
        czy, powod = (True, "wymuszone") if wymus else self.wymaga_modelu(kr)
        if not czy:
            self.pominiete += 1
            return {"status": "pominiete", "powod": powod}
        dh = {k: v for k, v in d.items() if k != "ostatnie_wnioski"}
        dh["okno_dlugie"] = {k: v for k, v in d["okno_dlugie"].items() if k != "pokrycie_s"}
        pod = _hash({"d": dh, "z": zdarzenia_do_hasha(kr)})
        if pod == self.podpis:
            self.pominiete += 1
            return {"status": "pominiete", "powod": "ten_sam_hash"}
        self.wywolania = [t for t in self.wywolania if teraz - t < 3600]
        if len(self.wywolania) >= self.limit_h:
            return {"status": "limit_h", "limit": self.limit_h}
        self.podpis = pod
        self.znak = max((r["t"] for r in kr if r["typ"] in ("poscig_koniec", "utkniecie")), default=self.znak)
        self.wywolania.append(teraz)
        try:
            tekst, meta = self.model(json.dumps(_bez_none(d), ensure_ascii=False, separators=(",", ":")), SYSTEM)
        except Exception as e:
            self.log(f"ANALITYK POŚCIGU błąd modelu: {e!r}")
            return {"status": "blad_modelu", "blad": repr(e)[:120]}
        koszt = float((meta or {}).get("total_cost_usd") or 0)
        self.koszt += koszt
        w = waliduj(tekst)
        if w is None:
            self.log(f"ANALITYK POŚCIGU: niepoprawny JSON z modelu: {str(tekst)[:100]!r}")
            return {"status": "blad_json", "surowe": str(tekst)[:120], "koszt": koszt}
        niesp = list(d.get("niespojnosci") or [])
        if not niesp and w["ocena"] == "problem" and w["wnioski"] and all(
                RE_WLASNA_NIESPOJNOSC.search(x["co"] + " " + x["dowod"]) for x in w["wnioski"]):
            niesp = ["model zgłasza niespójność danych"]      # problem tylko z powodu własnych danych
        if niesp and w["ocena"] == "problem":
            w["ocena"] = "uwaga"
            for x in w["wnioski"]:
                x["co"] = (x["co"] + " [dane niespójne]")[:240]
        nowe, powt = [], 0
        for x in w["wnioski"]:
            if any(podobne(x["co"], k) for k in self.znane + [n["co"] for n in nowe]):
                powt += 1
            else:
                nowe.append(x)
        hip = []
        for h in w["hipotezy"]:
            if not any(podobne(h, k) for k in self.hip_znane + hip):
                hip.append(h)
        self.log(f"ANALITYK POŚCIGU [{w['ocena']}] ({powod}): {len(nowe)} nowych wniosków, {powt} powtórzonych "
                 f"(${koszt:.4f}, sesja ${self.koszt:.3f}, {len(self.wywolania)}/{self.limit_h} w godz.)")
        wynik = {"status": "ok", "powod": powod, "ocena": w["ocena"], "wnioski": nowe, "hipotezy": hip,
                 "powtorzone": powt, "koszt": round(koszt, 5), "wszystkie": w["wnioski"]}
        if self.zapis:
            self.zapisz(wynik, teraz, d)
        self.znane = (self.znane + [x["co"] for x in nowe])[-60:]
        self.hip_znane = (self.hip_znane + hip)[-60:]
        self.ostatnie_co = (self.ostatnie_co + [x["co"] for x in w["wnioski"]])[-3:] or self.ostatnie_co
        self.ocena = w["ocena"]
        return wynik

    # --- zapis ---
    def zapisz(self, w, teraz, d):
        godz = time.strftime("%H:%M:%S", time.localtime(teraz))
        zmiana_oceny = w["ocena"] != self.ocena
        try:
            self.logi.mkdir(exist_ok=True)
            row = {"t": round(teraz), "godz": godz, "ocena": w["ocena"], "powod": w["powod"],
                   "wnioski": w["wnioski"], "hipotezy": w["hipotezy"], "powtorzone": w["powtorzone"],
                   "poscigow_5min": d["okno_krotkie"]["poscigow"], "poscigow_30min": d["okno_dlugie"]["poscigow"],
                   "koszt": w["koszt"], "suma": round(self.koszt, 4), "wywolan_h": len(self.wywolania)}
            jl = self.logi / "poscig-wnioski.jsonl"
            with jl.open("a") as f:
                f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            _przytnij_plik(jl)
            if w["wnioski"] or w["hipotezy"] or zmiana_oceny:
                md = self.logi / "poscig-wnioski.md"
                bl = [f"\n## {time.strftime('%Y-%m-%d %H:%M', time.localtime(teraz))} | {w['ocena']} | "
                      f"pościgów 5 min: {d['okno_krotkie']['poscigow']}, 30 min: {d['okno_dlugie']['poscigow']}"]
                for x in w["wnioski"]:
                    bl.append(f"- {x['co']} (pewność {x['pewnosc']})\n  dowód: {x['dowod']}\n"
                              f"  skutek: {x['skutek']}\n  propozycja: {x['propozycja']}")
                if not w["wnioski"]:
                    bl.append("- bez nowych wniosków" + (f" ({w['powtorzone']} powtórzonych)" if w["powtorzone"] else ""))
                for h in w["hipotezy"]:
                    bl.append(f"- do zmierzenia: {h}")
                with md.open("a") as f:
                    f.write("\n".join(bl) + "\n")
                _przytnij_plik(md)
        except OSError as e:
            self.log(f"ANALITYK POŚCIGU: zapis nieudany: {e!r}")
        if w["ocena"] == "problem":
            self.alert(w, teraz)

    def alert(self, w, teraz):
        """Status problem: linia w obserwator-alerty.log (dedup 10 min) i powiadomienie (max 1/10 min)."""
        wsz = w.get("wszystkie") or w["wnioski"]
        gl = max(wsz, key=lambda x: x["pewnosc"]) if wsz else None
        wniosek = "Pościg: " + (gl["co"] if gl else "ocena problem bez wniosku")
        dowod = gl["dowod"] if gl else ""
        klucz = norm(wniosek)[:80]
        if any(teraz - t < ALERT_DEDUP_S and podobne(wniosek, k) for k, t in self.alerty.items()):
            return
        self.alerty[klucz] = teraz
        try:
            with (self.logi / "obserwator-alerty.log").open("a") as f:     # format jak Obserwator
                f.write(re.sub(r"\s+", " ", f"{time.strftime('%H:%M:%S', time.localtime(teraz))} "
                               f"[problem] {wniosek} | {dowod}") + "\n")
        except OSError:
            pass
        if self.powiadamiaj and teraz - self.ost_powiad >= POWIADOM_S:
            self.ost_powiad = teraz
            try:
                powiadom.powiadom("Analityk pościgu: problem", wniosek, "normal", klucz="poscig:" + klucz[:40])
            except Exception:
                pass

    # --- wątek ---
    def watek(self, sprawdzaj=5.0, spij=time.sleep):
        while not self.koniec:
            try:
                self.obieg()
            except Exception as e:
                self.log(f"ANALITYK POŚCIGU błąd: {e!r}")
            spij(sprawdzaj)

    def start(self):
        t = threading.Thread(target=self.watek, daemon=True)
        t.start()
        return t


def _bez_none(o):
    if isinstance(o, dict):
        return {k: _bez_none(v) for k, v in o.items() if v is not None}
    if isinstance(o, list):
        return [_bez_none(v) for v in o]
    return o


# ---------------------------------------------------------------------------------------------
# --raz
# ---------------------------------------------------------------------------------------------
def _wczytaj(plik, od_t=None):
    rek = []
    try:
        with open(plik) as f:
            for l in f:
                try:
                    r = json.loads(l)
                except ValueError:
                    continue
                if isinstance(r, dict) and "t" in r and "typ" in r and (od_t is None or r["t"] >= od_t):
                    rek.append(r)
    except OSError:
        pass
    return rek


def _raz(argv):
    import tempfile  # noqa: PLC0415
    pliki = sorted(LOGI.glob("telemetria-*.jsonl"))
    if not pliki:
        print("Brak telemetrii w logi/.")
        return 1
    od_t = None
    if "--od" in argv:
        gm = argv[argv.index("--od") + 1]
        try:
            lt = time.localtime(_wczytaj(pliki[-1])[-1]["t"])
            h, m = (int(x) for x in gm.split(":"))
            od_t = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))
        except (ValueError, IndexError):
            print("Zły format --od (GG:MM).")
            return 2
    rek = _wczytaj(pliki[-1], od_t)
    if not rek:
        print("Brak rekordów telemetrii w tym zakresie.")
        return 1
    t_k = rek[-1]["t"]
    tele = telemetria.Telemetria(Path(tempfile.mkdtemp()), zegar=lambda: t_k, zapis=False)
    tele.rek.extend(rek)
    mapa = None
    try:
        import mapa as mapa_mod  # noqa: PLC0415
        mapa = mapa_mod.mapa()
    except Exception:
        pass
    os.environ["RETRONIC_POWIADOMIENIA"] = "0"
    if "--bez-modelu" in argv:
        model = lambda p, s: ('{"ocena":"ok","wnioski":[]}', {})       # noqa: E731
    else:
        import mozg  # noqa: PLC0415
        model = mozg.Claude()
    an = AnalitykPoscigu(tele, model, log=print, zegar=lambda: t_k, logi=Path(tempfile.mkdtemp()),
                         mapa=mapa, zapis=False, powiadamiaj=False)
    d, kr = an.wejscie(t_k)
    print(f"Zakres: {time.strftime('%H:%M:%S', time.localtime(rek[0]['t']))}-"
          f"{time.strftime('%H:%M:%S', time.localtime(t_k))}, rekordów {len(rek)}")
    print("=== WEJŚCIE (liczone w Pythonie) ===")
    print(json.dumps(_bez_none(d), ensure_ascii=False, indent=1))
    if "--bez-modelu" in argv:
        return 0
    an.znak = float("-inf")
    w = an.cykl(t_k, wymus=True)
    print("=== WYNIK MODELU ===")
    print(json.dumps(w, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    if "--raz" in sys.argv:
        sys.exit(_raz(sys.argv))
    print(__doc__)
