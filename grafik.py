#!/usr/bin/env python3
"""Grafik doby dla nadzorcy zestawu (SPEC_nadzor_wykonawca_1021, F1). Deterministyczny, bez dostępu do gry.

  python3 -I grafik.py pokaz [--data RRRRMMDD]            tabela zmian na dobę (domyślnie bieżąca)
  python3 -I grafik.py nowy [--od-teraz] [--data RRRRMMDD] [--online id,id]   generuje i zapisuje plik grafiku
                                                          (istniejący plik idzie do kopii .bak-HHMMSS)
  python3 -I grafik.py waliduj [--data RRRRMMDD]          sprawdza plik (także ręcznie edytowany) z regułami

Doba = od 08:00 (koniec ciszy) do 08:00 następnego dnia, plik `instancje/_wspolne/grafik-RRRRMMDD.json` nosi datę początku doby.
Zmiana: `od` (logowanie), `koniec` (początek powrotu do miasta), `wylog` (planowane wylogowanie = koniec + miasto_min).
Zdarzeniami odstępu są `od` i `wylog`. Reguły (nadzor_konfig.json): najwyżej `max_online` postaci naraz, odstęp między
dowolnymi dwoma zdarzeniami >= `odstep_min`[0] (losowo do [1]), zmiana = hunt `zmiana_min` + `miasto_min`, przerwa `przerwa_min`,
limit `limit_dzienny_min` na postać, cisza `cisza_od`-`cisza_do` (zero zdarzeń), pierwsze logowanie przesuwa się z dnia na dzień
o najwyżej `przesuniecie_dzienne_min`. Ręczna edycja pliku wygrywa: istniejący plik nie jest nigdy nadpisywany przez nadzorcę.
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True          # cień = zero zapisów (także __pycache__)
KORZEN = Path(os.environ.get("RETRONIC_NADZOR_KORZEN") or Path(__file__).resolve().parent)
FMT = "%Y-%m-%d %H:%M"
EPOKA = date(2026, 1, 1)

DOMYSLNE = {
    "max_online": 5,
    "zmiana_min": [120, 180],
    "przerwa_min": [30, 120],
    "limit_dzienny_min": 480,
    "cisza_od": "01:00",
    "cisza_do": "08:00",
    "odstep_min": [7, 25],
    "przesuniecie_dzienne_min": 60,
    "start_okno_min": 240,
    "miasto_min": 15,
    "wylog_spokoj_max_min": 15,
    "cien_powtorz_min": 30,
    "eskalacja_powtorz_min": 30,
    "napraw_okno_min": 90,
    "brak_zabic_min": 25,
    "stoi_min": 8,
    "nieustalony_min": 10,
    "postacie": {},
}


# ---------- konfiguracja i pula ----------
def wspolne(korzen=None):
    return Path(korzen or KORZEN) / "instancje" / "_wspolne"


def wczytaj_konfig(korzen=None):
    konf = json.loads(json.dumps(DOMYSLNE))
    try:
        dane = json.loads((wspolne(korzen) / "nadzor_konfig.json").read_text(encoding="utf-8"))
        konf.update({k: v for k, v in dane.items() if not k.startswith("_")})
    except (OSError, ValueError):
        pass
    return konf


def hm(txt):
    g, m = str(txt).split(":")
    return int(g) * 60 + int(m)


def dlugosc_doby(konf):
    """Minuty od końca ciszy (cisza_do) do jej początku (cisza_od następnego dnia)."""
    od, do = hm(konf["cisza_od"]), hm(konf["cisza_do"])
    if od >= do:
        raise ValueError("cisza_od musi być wcześniej niż cisza_do (cisza przez północ nie jest obsługiwana)")
    return od + 1440 - do


def doba_dla(teraz, konf=None):
    """Data początku doby, do której należy chwila `teraz` (przed końcem ciszy = poprzednia doba)."""
    konf = konf or DOMYSLNE
    d = teraz.date()
    if teraz.hour * 60 + teraz.minute < hm(konf["cisza_do"]):
        d -= timedelta(days=1)
    return d


def poczatek_doby(data, konf):
    return datetime(data.year, data.month, data.day) + timedelta(minutes=hm(konf["cisza_do"]))


def poza_nadzorem(profil, wpis_konf, teraz=None):
    """Powód wyłączenia postaci z nadzoru albo None. `"nadzor": false` = bezterminowo; `"nadzor_do": "RRRR-MM-DD HH:MM"` =
    do tej chwili (profil albo konfiguracja). Nieczytelna data = wyłączona (lepiej pominąć postać niż ją uruchomić)."""
    teraz = teraz or datetime.now()
    for zrodlo in (profil or {}, wpis_konf or {}):
        do = zrodlo.get("nadzor_do")
        if do:
            # `nadzor_do` w tym samym źródle ma pierwszeństwo przed `nadzor: false` (Karol 22.10, Q-N Przeglądu):
            # przyszła data = poza nadzorem do niej, minęła = postać wraca (stare `nadzor: false` obok daty jej nie blokuje).
            try:
                if teraz < datetime.strptime(str(do), FMT):
                    return f"postać tymczasowo poza nadzorem do {do} (nadzor_do)"
                continue
            except ValueError:
                return f"postać poza nadzorem: nieczytelne nadzor_do {do!r}"
        if zrodlo.get("nadzor") is False:
            return "postać poza nadzorem (nadzor: false)"
    return None


def powod_poza_pula(korzen, konf, n, teraz=None):
    """Powód, dla którego katalog instancji `n` nie jest w puli nadzorowanych, albo None (jest w puli).
    Jedno źródło prawdy dla `pula` i dla ostrzeżeń „sesja online poza nadzorem”. Katalogi `_*` nie są postaciami."""
    p = Path(korzen or KORZEN) / "instancje" / n
    if not p.is_dir() or n.startswith("_"):
        return "nie jest postacią (brak katalogu albo nazwa z _)"
    if n.startswith("test"):
        return "nazwa zaczyna się od test (spec: instancje testowe poza nadzorem)"
    try:
        profil = json.loads((p / "profil.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "brak czytelnego profil.json"
    return poza_nadzorem(profil, (konf or {}).get("postacie", {}).get(n), teraz)


def poza_pula(korzen=None, konf=None, teraz=None):
    """{id: powód} dla katalogów instancji (bez `_*`), które NIE są w puli."""
    konf = konf or wczytaj_konfig(korzen)
    kat = Path(korzen or KORZEN) / "instancje"
    wynik = {}
    if not kat.is_dir():
        return wynik
    for p in sorted(kat.iterdir()):
        if not p.is_dir() or p.name.startswith("_"):
            continue
        powod = powod_poza_pula(korzen, konf, p.name, teraz)
        if powod:
            wynik[p.name] = powod
    return wynik


def pula(korzen=None, konf=None, teraz=None):
    """Postacie nadzorowane: instancje/*/profil.json, bez `_*`, `test*` i wyłączonych (`poza_nadzorem`: profil albo konfiguracja).
    Lista jest liczona od nowa przy każdym wywołaniu (przebieg nadzorcy co tick): nowa instancja z profil.json wchodzi sama."""
    konf = konf or wczytaj_konfig(korzen)
    wynik = []
    kat = Path(korzen or KORZEN) / "instancje"
    if not kat.is_dir():
        return wynik
    for p in sorted(kat.iterdir()):
        n = p.name
        if not p.is_dir() or n.startswith("_"):
            continue
        if powod_poza_pula(korzen, konf, n, teraz) is None:
            wynik.append(n)
    return wynik


# ---------- przesunięcie dzienne ----------
_LANCUCHY = {}


def przesuniecie_startu(id_, data, konf):
    """Minuty po końcu ciszy, o które przesunięte jest pierwsze logowanie postaci w danej dobie. Błądzenie z odbiciem w
    [0, start_okno_min]: kolejny dzień różni się od poprzedniego o najwyżej `przesuniecie_dzienne_min`."""
    lim, krok = float(konf["start_okno_min"]), float(konf["przesuniecie_dzienne_min"])
    dn = (data - EPOKA).days
    klucz = (id_, lim, krok)
    lanc = _LANCUCHY.setdefault(klucz, [random.Random(f"start|{id_}").uniform(0, lim)])
    while len(lanc) <= max(dn, 0):
        r = random.Random(f"krok|{id_}|{len(lanc)}")
        x = lanc[-1] + r.uniform(-krok, krok)
        if x < 0:
            x = -x
        if x > lim:
            x = 2 * lim - x
        lanc.append(min(lim, max(0.0, x)))
    return lanc[max(dn, 0)]


# ---------- generator ----------
def generuj(data, ids, konf=None, teraz=None, online=None):
    """Czysta funkcja: zmiany doby `data` dla postaci `ids`.
    teraz (datetime) = nic nie jest planowane wcześniej niż teraz; online = {id: {"od": datetime|None}} postacie, które już grają
    (przyjęte jako zmiany w toku, `adoptowana`). Zwraca plan (dict) gotowy do zapisu."""
    konf = konf or DOMYSLNE
    D = dlugosc_doby(konf)
    start = poczatek_doby(data, konf)
    N = int(konf["max_online"])
    lo, hi = (int(x) for x in konf["odstep_min"])
    zlo, zhi = (int(x) for x in konf["zmiana_min"])
    plo, phi = (int(x) for x in konf["przerwa_min"])
    miasto = int(konf["miasto_min"])
    limit = int(konf["limit_dzienny_min"])
    t0 = 0
    if teraz is not None:
        t0 = max(0, int((teraz - start).total_seconds() // 60))
    rng = random.Random(f"grafik|{data:%Y%m%d}|{t0 if teraz is not None else 'doba'}")
    zdarzenia, przedzialy, zm = [], [], []
    ids = sorted(ids)

    def pojemnosc_ok(a, b):
        for p in [a] + [x[0] for x in przedzialy if a < x[0] < b]:
            if sum(1 for x in przedzialy if x[0] <= p < x[1]) + 1 > N:
                return False
        return True

    def znajdz(nxt, L):
        t = int(-(-nxt // 1))
        gl, gw = rng.randint(lo, hi), rng.randint(lo, hi)
        while t + L <= D:
            c = next((e for e in zdarzenia if abs(t - e) < gl), None)
            if c is not None:
                t = max(t + 1, c + gl)
                continue
            c = next((e for e in zdarzenia if abs(t + L - e) < gw), None)
            if c is not None:
                t = max(t + 1, c + gw - L)
                continue
            if not pojemnosc_ok(t, t + L):
                konce = [x[1] for x in przedzialy if x[1] > t]
                t = max(t + 1, min(konce) if konce else t + 1)
                continue
            return t
        return None

    def czas(m):
        return (start + timedelta(minutes=m)).strftime(FMT)

    nast, uzyte = {}, {}
    online = online or {}
    for id_ in ids:
        nast[id_] = (t0 + rng.randint(0, 20)) if teraz is not None else przesuniecie_startu(id_, data, konf)
        uzyte[id_] = 0
    # postacie już grające: zmiana w toku
    for id_ in ids:
        if id_ not in online:
            continue
        od_dt = online[id_].get("od") if isinstance(online[id_], dict) else None
        od_m = int((od_dt - start).total_seconds() // 60) if od_dt else t0 - 30
        od_m = max(0, od_m)
        H = rng.randint(zlo, zhi)
        koniec = max(t0 + 5, od_m + H)
        wylog = koniec + miasto
        if wylog - od_m > limit:
            wylog = od_m + limit
            koniec = wylog - miasto
        g = rng.randint(lo, hi)
        t = wylog
        while t <= D and any(abs(t - e) < g for e in zdarzenia):
            t = max(t + 1, next(e for e in zdarzenia if abs(t - e) < g) + g)
        if t <= D and t - od_m <= limit:
            wylog = t
            koniec = max(t0 + 1, wylog - miasto)
        else:
            continue
        zdarzenia.append(wylog)           # logowanie adoptowane jest w przeszłości: nie liczy się jako zdarzenie odstępu
        przedzialy.append((od_m, wylog, id_))
        zm.append({"id": id_, "od": czas(od_m), "koniec": czas(koniec), "wylog": czas(wylog), "adoptowana": True})
        uzyte[id_] += wylog - od_m
        nast[id_] = wylog + rng.randint(plo, phi)
    aktywne = list(ids)
    while aktywne:
        id_ = min(aktywne, key=lambda i: (nast[i], i))
        ost = limit - uzyte[id_]
        if ost < zlo + miasto:
            aktywne.remove(id_)
            continue
        H = rng.randint(zlo, zhi)
        L = min(H + miasto, ost)
        t = znajdz(nast[id_], L)
        if t is None and L > zlo + miasto:
            L = zlo + miasto
            t = znajdz(nast[id_], L)
        if t is None:
            aktywne.remove(id_)
            continue
        zdarzenia += [t, t + L]
        przedzialy.append((t, t + L, id_))
        pk = (konf.get("postacie", {}).get(id_) or {})
        zm.append({"id": id_, "od": czas(t), "koniec": czas(t + L - miasto), "wylog": czas(t + L),
                   "mapa": pk.get("mapa"), "tryb": pk.get("tryb")})
        uzyte[id_] += L
        nast[id_] = t + L + rng.randint(plo, phi)
    zm.sort(key=lambda z: (z["od"], z["id"]))
    for z in zm:
        z.setdefault("mapa", None)
        z.setdefault("tryb", None)
    return {"data": f"{data:%Y%m%d}", "zrodlo": "od-teraz" if teraz is not None else "auto",
            "wygenerowano": (teraz or start).strftime(FMT),
            "reguly": {k: konf[k] for k in ("max_online", "odstep_min", "zmiana_min", "przerwa_min", "limit_dzienny_min",
                                            "cisza_od", "cisza_do", "miasto_min")},
            "zmiany": zm}


# ---------- walidacja ----------
def waliduj(plan, konf=None):
    """Lista naruszeń reguł (pusta = zgodny). Sprawdza także ręcznie edytowane pliki."""
    konf = konf or DOMYSLNE
    bl = []
    try:
        data = datetime.strptime(plan["data"], "%Y%m%d").date()
        start = poczatek_doby(data, konf)
        D = dlugosc_doby(konf)
        zm = plan["zmiany"]
        ev = []
        for z in zm:
            od, kon, wy = (datetime.strptime(z[k], FMT) for k in ("od", "koniec", "wylog"))
            if not od < kon <= wy:
                bl.append(f"{z['id']} {z['od']}: kolejność od < koniec <= wylog")
            mo, mw = (od - start).total_seconds() / 60, (wy - start).total_seconds() / 60
            if mo < 0 and not z.get("adoptowana"):
                bl.append(f"{z['id']} {z['od']}: logowanie w ciszy")
            if mw > D:
                bl.append(f"{z['id']} {z['wylog']}: wylogowanie w ciszy")
            if not z.get("adoptowana"):
                ev.append((mo, "od", z["id"]))
            ev.append((mw, "wylog", z["id"]))
        ev.sort()
        for a, b in zip(ev, ev[1:]):
            if b[0] - a[0] < int(konf["odstep_min"][0]):
                bl.append(f"odstęp {b[0] - a[0]:.0f} min < {konf['odstep_min'][0]}: {a[2]} {a[1]} i {b[2]} {b[1]}")
        pkt = sorted({(datetime.strptime(z["od"], FMT)) for z in zm})
        for p in pkt:
            ile = sum(1 for z in zm if datetime.strptime(z["od"], FMT) <= p < datetime.strptime(z["wylog"], FMT))
            if ile > int(konf["max_online"]):
                bl.append(f"{p:%H:%M}: {ile} online > {konf['max_online']}")
        per = {}
        for z in zm:
            od, wy = datetime.strptime(z["od"], FMT), datetime.strptime(z["wylog"], FMT)
            od = max(od, start)
            per.setdefault(z["id"], []).append((od, wy))
        for id_, l in per.items():
            suma = sum((w - o).total_seconds() / 60 for o, w in l)
            if suma > int(konf["limit_dzienny_min"]):
                bl.append(f"{id_}: {suma:.0f} min > limit {konf['limit_dzienny_min']}")
            l.sort()
            for (o1, w1), (o2, _w2) in zip(l, l[1:]):
                if o2 < w1:
                    bl.append(f"{id_}: zmiany nachodzą na siebie ({w1:%H:%M} > {o2:%H:%M})")
    except (KeyError, ValueError, TypeError) as e:
        bl.append(f"plik grafiku nieczytelny: {e!r}")
    return bl


# ---------- plik ----------
def sciezka(data, korzen=None):
    return wspolne(korzen) / f"grafik-{data:%Y%m%d}.json"


def zaladuj(data, korzen=None):
    """Plan z pliku albo None (brak / nieczytelny)."""
    try:
        return json.loads(sciezka(data, korzen).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def zapisz(plan, korzen=None, kopia=True):
    data = datetime.strptime(plan["data"], "%Y%m%d").date()
    p = sciezka(data, korzen)
    p.parent.mkdir(parents=True, exist_ok=True)
    if kopia and p.exists():
        p.replace(p.with_name(p.name + time.strftime(".bak-%H%M%S")))
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(p)
    return p


def plan_dla(teraz, korzen=None, konf=None, online=None, zapis=True):
    """Plan bieżącej doby: istniejący plik wygrywa; brak pliku = nowy (zwykły, gdy doba dopiero się zaczęła, inaczej od teraz).
    -> (plan, utworzono). zapis=False: tylko w pamięci."""
    konf = konf or wczytaj_konfig(korzen)
    data = doba_dla(teraz, konf)
    plan = zaladuj(data, korzen)
    if plan is not None:
        return plan, False
    ids = pula(korzen, konf)
    swiezo = (teraz - poczatek_doby(data, konf)).total_seconds() < 3600
    plan = generuj(data, ids, konf, teraz=None if swiezo and not online else teraz, online=online)
    if zapis:
        zapisz(plan, korzen, kopia=False)
    return plan, True


def zmiany_postaci(plan, id_):
    return sorted((z for z in plan.get("zmiany", []) if z.get("id") == id_), key=lambda z: z["od"])


def aktywna_zmiana(plan, id_, teraz, luz_min=0):
    """Zmiana postaci obejmująca `teraz` (od <= teraz < wylog + luz) albo None."""
    for z in zmiany_postaci(plan, id_):
        if datetime.strptime(z["od"], FMT) <= teraz < datetime.strptime(z["wylog"], FMT) + timedelta(minutes=luz_min):
            return z
    return None


# ---------- CLI ----------
def _online_z_okno_api(korzen=None):
    try:
        r = subprocess.run([sys.executable, "-I", str(Path(korzen or KORZEN) / "okno_api.py"), "stan"], capture_output=True,
                           text=True, timeout=60, cwd=str(Path(korzen or KORZEN)))
        return {i["id"]: {"od": None} for i in json.loads(r.stdout).get("instancje", []) if i.get("sesja") or i.get("gra")}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}


def tabela(plan, konf=None):
    konf = konf or DOMYSLNE
    zm = plan.get("zmiany", [])
    wiersze = [f"Grafik doby {plan['data']} ({plan.get('zrodlo')}, {len(zm)} zmian, max {konf['max_online']} online)"]
    ev = []
    for z in zm:
        ev.append((z["od"], 0, z["id"], f"login   {z.get('mapa') or '(bieżąca)'} {z.get('tryb') or ''}".rstrip()
                   + (" [w toku]" if z.get("adoptowana") else "")))
        ev.append((z["koniec"], 1, z["id"], "powrót (WROC)"))
        ev.append((z["wylog"], 2, z["id"], "wylogowanie"))
    ev.sort()
    for t, _, id_, opis in ev:
        ile = sum(1 for z in zm if z["od"] <= t < z["wylog"])
        wiersze.append(f"  {t[11:]}  {id_:<11} {opis:<34} online po zdarzeniu ~{ile}")
    per = {}
    for z in zm:
        per[z["id"]] = per.get(z["id"], 0) + int((datetime.strptime(z["wylog"], FMT) - datetime.strptime(z["od"], FMT)).total_seconds() // 60)
    wiersze.append("  razem: " + ", ".join(f"{i} {m // 60}h{m % 60:02d}" for i, m in sorted(per.items())))
    return "\n".join(wiersze)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="grafik.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("pokaz", "nowy", "waliduj"):
        s = sub.add_parser(n)
        s.add_argument("--data")
        if n == "nowy":
            s.add_argument("--od-teraz", action="store_true")
            s.add_argument("--online", help="id po przecinku zamiast odczytu z okno_api.py")
    a = ap.parse_args(argv)
    konf = wczytaj_konfig()
    teraz = datetime.now().replace(second=0, microsecond=0)
    data = datetime.strptime(a.data, "%Y%m%d").date() if a.data else doba_dla(teraz, konf)
    if a.cmd == "nowy":
        if a.online is not None:
            online = {i: {"od": None} for i in a.online.split(",") if i}
        elif a.od_teraz:
            online = _online_z_okno_api()
        else:
            online = {}
        ids = pula(None, konf)
        plan = generuj(data, ids, konf, teraz=teraz if a.od_teraz else None, online={i: v for i, v in online.items() if i in ids})
        p = zapisz(plan)
        print(f"zapisano {p}")
        print(tabela(plan, konf))
        bl = waliduj(plan, konf)
        print("walidacja: " + ("OK" if not bl else "; ".join(bl)))
        return 1 if bl else 0
    plan = zaladuj(data)
    if plan is None:
        print(f"brak pliku {sciezka(data)} (utwórz: grafik.py nowy)", file=sys.stderr)
        return 1
    if a.cmd == "pokaz":
        print(tabela(plan, konf))
        return 0
    bl = waliduj(plan, konf)
    print("OK" if not bl else "\n".join(bl))
    return 1 if bl else 0


if __name__ == "__main__":
    sys.exit(main())
