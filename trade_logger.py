#!/usr/bin/env python3
"""trade_logger: demon TYLKO DO ODCZYTU czatu Trade z gniazda retronic-pomocnik.sock.

Nie wysyla klawiszy ani klikniec, nie rusza bota ani mozgu. Odpytuje komende
{"cmd":"wiadomosci"} co 5 s, deduplikuje po 'nr', rozpoznaje oferty sprzedazy
i kupna (przedmiot, ilosc, cena, miasto), zapisuje je do dane_tibia/ceny_trade.jsonl,
co 5 min przelicza dane_tibia/ceny_trade_podsumowanie.json i pisze alerty kupna
UH / HMM / blank rune do dane_tibia/alerty_trade.jsonl (+ notify-send).

Uzycie:
  python3 -I trade_logger.py                 # demon (ctrl-c konczy czysto)
  python3 -I trade_logger.py --raz --sucho   # jedna iteracja, bez notify-send
"""
import argparse
import json
import os
import re
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

BAZA = Path(__file__).resolve().parent
DANE = BAZA / "dane_tibia"
PLIK_PRZEDMIOTY = DANE / "przedmioty.json"
PLIK_OFERT = DANE / "ceny_trade.jsonl"
PLIK_ALERTOW = DANE / "alerty_trade.jsonl"
PLIK_PODSUMOWANIA = DANE / "ceny_trade_podsumowanie.json"
PLIK_PID = Path.home() / ".cache" / "retronic-trade-logger.pid"

KANAL = "Trade"
WLASNY_NICK = "Jointoramix"
INTERWAL = 5.0            # s, zwykly odpyt
PONOW = 10.0              # s, po bledzie gniazda
INTERWAL_PODSUMOWANIA = 300.0
CISZA_ALERTU = 600.0      # s, max 1 powiadomienie na nadawce
ALERT_PRZEDMIOTY = {"ultimate healing rune", "heavy magic missile rune", "blank rune"}

ALIASY = {
    "uh": "ultimate healing rune",
    "hmm": "heavy magic missile rune",
    "gfb": "great fireball rune",
    "sd": "sudden death rune",
}
MIASTA = {
    "thais": "Thais", "carlin": "Carlin", "venore": "Venore", "ankrahmun": "Ankrahmun",
    "ank": "Ankrahmun", "edron": "Edron", "darashia": "Darashia", "kazordoon": "Kazordoon",
    "svargrond": "Svargrond", "yalahar": "Yalahar", "rookgaard": "Rookgaard",
    "liberty bay": "Liberty Bay", "port hope": "Port Hope", "ab'dendriel": "Ab'Dendriel",
    "ab dendriel": "Ab'Dendriel",
}
# slowa, ktore moga stac obok ceny/ilosci i nie oznaczaja nieznanego przedmiotu
SLOWA_WYPELNIACZE = {
    "each", "ea", "all", "for", "per", "total", "x", "bp", "bps", "bag", "bags", "and",
    "or", "gp", "gold", "the", "of", "in", "at", "to", "only", "msg", "me", "pm", "price",
    "good", "pls", "now", "ok", "k",
}

RX_ZNACZNIK = re.compile(r"(?<![a-z])(sell\w*|wts|buy\w*|wtb)(?![a-z])")
RX_SEPARATOR = re.compile(r"[/,;+&*]")
RX_CENA = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(kk|k|gp|gold|gc)?(?![\w.])")
RX_PO_ILOSCI = re.compile(r"\s*(?:bps?|bags?|x)(?![a-z])")
RX_MIASTA = re.compile(
    r"(?<![a-z])(" + "|".join(re.escape(m) for m in sorted(MIASTA, key=len, reverse=True)) + r")(?![a-z])"
)
RX_NA_BP = re.compile(r"(?<![a-z])(bps?|bags?)\s*$")

_WZORCE = None   # (regex, nazwa kanoniczna), najdluzsze pierwsze
_PRZEDMIOTY = None


def log(msg):
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def zaladuj_przedmioty(sciezka=PLIK_PRZEDMIOTY):
    dane = json.loads(sciezka.read_text(encoding="utf-8"))
    nazwy = set()
    for lista in dane["kategorie"].values():
        for p in lista:
            nazwa = p["nazwa"].strip().lower()
            if nazwa:
                nazwy.add(nazwa)
    return sorted(nazwy)


def _wzorce():
    global _WZORCE, _PRZEDMIOTY
    if _WZORCE is None:
        _PRZEDMIOTY = zaladuj_przedmioty()
        pary = []
        for p in _PRZEDMIOTY:
            pary.append((p, p))
            if p.endswith(" rune"):
                pary.append((p[: -len(" rune")], p))   # "heavy magic missile" -> runa
        for alias, p in ALIASY.items():
            pary.append((alias, p))
        pary.sort(key=lambda x: -len(x[0]))
        _WZORCE = [
            (re.compile(r"(?<![a-z])" + re.escape(t) + r"(?:'?s)?(?![a-z])"), kanon)
            for t, kanon in pary
        ]
    return _WZORCE


def normalizuj(tekst):
    t = tekst.lower().replace("\xa0", " ").replace("|", "/").replace("–", "-")
    t = re.sub(r"(\d),(\d{3})(?!\d)", r"\1\2", t)     # 2,500 -> 2500
    t = re.sub(r"(\d),(\d)", r"\1.\2", t)             # 2,5k -> 2.5k
    t = re.sub(r"[\[\]{}!_~=<>\"()@#]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def segmenty(t):
    """Dzieli tekst na odcinki zaczynajace sie od znacznika sell/buy (wiele ofert w jednej wiadomosci)."""
    znaczniki = list(RX_ZNACZNIK.finditer(t))
    wyn = []
    for i, m in enumerate(znaczniki):
        koniec = znaczniki[i + 1].start() if i + 1 < len(znaczniki) else len(t)
        intencja = "sprzedaje" if m.group(1).startswith(("sell", "wts")) else "kupuje"
        wyn.append((intencja, t[m.end():koniec]))
    return wyn


def znajdz_przedmioty(seg):
    zajete = [False] * len(seg)
    wyn = []
    for rx, kanon in _wzorce():
        for m in rx.finditer(seg):
            a, b = m.span()
            if any(zajete[a:b]):
                continue
            for i in range(a, b):
                zajete[i] = True
            wyn.append((a, b, kanon))
    wyn.sort()
    return wyn


def ilosc_z_lewej(s):
    """Ilosc i jednostka tuz przed przedmiotem: '3 bp', '20x', 'x5', '77', 'bp' (=1), 'all bp' (=?)."""
    s = s.strip()
    m = re.search(r"(\d+)\s*x?\s*(?<![a-z])(?:bps?|bags?)$", s)
    if m:
        return int(m.group(1)), "bp"
    if re.search(r"(?<![a-z])all\s+(?:bps?|bags?)$", s):
        return None, "bp"
    m = re.search(r"(?:(\d+)\s*x|x\s*(\d+))$", s)
    if m:
        return int(m.group(1) or m.group(2)), None
    m = RX_NA_BP.search(s)
    if m:
        return 1, "bp"
    m = re.search(r"(\d+)$", s)
    if m:
        return int(m.group(1)), None
    return None, None


def tokeny_ceny(s):
    """Liczby-ceny w tekscie (prawa strona przedmiotu) z typem: ea / all / None."""
    tokeny = []
    for m in RX_CENA.finditer(s):
        liczba, suf = m.group(1), m.group(2)
        po = s[m.end():]
        if suf is None and RX_PO_ILOSCI.match(po):
            continue                                   # to ilosc, nie cena
        mnoznik = {"k": 1000, "kk": 1000000}.get(suf, 1)
        wartosc = round(float(liczba) * mnoznik, 2)
        typ = None
        if re.match(r"\s*(each|ea|per|apiece)(?![a-z])", po):
            typ = "ea"
        elif re.match(r"\s*(for\s+all|all|total)(?![a-z])", po) or re.search(r"(?<![a-z])all\s+for\s*$|(?<![a-z])all\s*$", s[:m.start()]):
            typ = "all"
        tokeny.append({"wartosc": wartosc, "typ": typ, "poz": m.start()})
    bez = RX_MIASTA.sub(" ", RX_CENA.sub(" ", s))
    niezrozumiale = [w for w in re.findall(r"[a-z']+", bez) if w not in SLOWA_WYPELNIACZE]
    return tokeny, niezrozumiale


def znajdz_miasto(t):
    m = RX_MIASTA.search(t)
    return MIASTA[m.group(1)] if m else None


def _wybierz_cene(tokeny):
    """Cena za sztuke (ea) > cena bez oznaczenia > cena lacznie (all); calk = suma 'for all' gdy cena nie jest lacznie."""
    ea = [t for t in tokeny if t["typ"] == "ea"]
    nn = [t for t in tokeny if t["typ"] is None]
    al = [t for t in tokeny if t["typ"] == "all"]
    cena = cena_typ = calk = None
    if ea:
        cena, cena_typ = ea[0]["wartosc"], "ea"
    elif nn:
        cena, cena_typ = nn[0]["wartosc"], None
    elif al:
        cena, cena_typ = al[0]["wartosc"], "all"
    if al and cena_typ != "all":
        calk = al[0]["wartosc"]
    niejednoznaczna = len(ea) > 1 or len(nn) > 1
    return cena, cena_typ, calk, niejednoznaczna


def _przetworz_segment(intencja, seg):
    """Zwraca liste slownikow ofert z jednego odcinka (jeden wpis na przedmiot)."""
    spans = znajdz_przedmioty(seg)
    if not spans:
        tokeny, _ = tokeny_ceny(seg)
        cena, cena_typ, calk, _ = _wybierz_cene(tokeny)
        return [{
            "intencja": intencja, "przedmiot": None, "ilosc": None, "jednostka": None,
            "cena": cena, "cena_typ": cena_typ, "cena_calkowita": calk, "niepewne": True,
        }]
    wyn = []
    for idx, (a, b, kanon) in enumerate(spans):
        poprz = spans[idx - 1][1] if idx > 0 else 0
        nast = spans[idx + 1][0] if idx + 1 < len(spans) else len(seg)
        lewo = RX_SEPARATOR.split(seg[poprz:a])[-1]
        prawo = RX_SEPARATOR.split(seg[b:nast])[0]
        ilosc, jednostka = ilosc_z_lewej(lewo)
        tokeny, niezrozumiale = tokeny_ceny(prawo)
        cena, cena_typ, calk, niejednoznaczna = _wybierz_cene(tokeny)
        wyn.append({
            "intencja": intencja, "przedmiot": kanon, "ilosc": ilosc, "jednostka": jednostka,
            "cena": cena, "cena_typ": cena_typ, "cena_calkowita": calk,
            "niepewne": bool(niezrozumiale) or niejednoznaczna,
        })
    return wyn


def rozpoznaj(tekst, nadawca="", ts=None, nr=None, epoka=None):
    """Parser: tekst wiadomosci -> lista ofert (dict gotowy do zapisu w ceny_trade.jsonl)."""
    t = normalizuj(tekst)
    miasto = znajdz_miasto(t)
    oferty = []
    widziane = set()
    for intencja, seg in segmenty(t):
        for o in _przetworz_segment(intencja, seg):
            klucz = (o["intencja"], o["przedmiot"], o["ilosc"], o["jednostka"], o["cena"],
                     o["cena_typ"], o["cena_calkowita"])
            if klucz in widziane:
                continue                       # ta sama reklama powtorzona w jednej wiadomosci
            widziane.add(klucz)
            o.update({
                "ts": ts,
                "czas": datetime.fromtimestamp(ts).isoformat(timespec="seconds") if ts else None,
                "nadawca": nadawca,
                "miasto": miasto,
                "tekst_oryg": tekst,
                "nr": nr,
                "epoka": epoka,
            })
            oferty.append(o)
    return oferty


class Stan:
    """Deduplikacja po 'nr'; po zmianie 'epoka' zapomina wszystko (opcjonalnie dowczytuje z pliku ofert)."""

    def __init__(self, plik_seed=None):
        self.plik_seed = plik_seed
        self.epoka = None
        self.kolejka = deque(maxlen=5000)
        self.zbior = set()
        self.ostatnio_powiadomiono = {}

    def _reset(self, epoka):
        self.epoka = epoka
        self.kolejka.clear()
        self.zbior.clear()
        if self.plik_seed:
            for nr in wczytaj_nr_z_pliku(self.plik_seed, epoka):
                self._dodaj(nr)

    def _dodaj(self, nr):
        if len(self.kolejka) == self.kolejka.maxlen:
            self.zbior.discard(self.kolejka[0])
        self.kolejka.append(nr)
        self.zbior.add(nr)

    def nowe(self, wiadomosci, epoka):
        if epoka != self.epoka:
            self._reset(epoka)
        wyn = []
        for m in wiadomosci:
            if m.get("kanal") != KANAL:
                continue
            nr = m.get("nr")
            if nr is None or nr in self.zbior:
                continue
            self._dodaj(nr)
            wyn.append(m)
        return wyn


def wczytaj_nr_z_pliku(plik, epoka, ile=5000):
    if not plik.exists():
        return []
    nr = []
    try:
        with plik.open(encoding="utf-8") as f:
            for linia in deque(f, maxlen=ile):
                try:
                    r = json.loads(linia)
                except ValueError:
                    continue
                if r.get("epoka") == epoka and r.get("nr") is not None:
                    nr.append(r["nr"])
    except OSError:
        return []
    return nr


def pobierz_wiadomosci(sciezka, timeout=3.0):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(str(sciezka))
        s.sendall(b'{"cmd":"wiadomosci"}\n')
        bufor = bytearray()
        while True:
            kawalek = s.recv(65536)
            if not kawalek:
                break
            bufor += kawalek
            if b"\n" in kawalek:
                break
    dane = json.loads(bufor.decode("utf-8"))
    if not dane.get("ok"):
        raise RuntimeError(f"gniazdo odrzucilo zapytanie: {dane}")
    return dane


def sciezka_gniazda():
    baza = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(baza) / "retronic-pomocnik.sock"


def zapisz_jsonl(plik, rekordy):
    if not rekordy:
        return
    with plik.open("a", encoding="utf-8") as f:
        for r in rekordy:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _statystyka(ceny):
    if not ceny:
        return {"mediana": None, "min": None, "max": None}
    return {"mediana": round(statistics.median(ceny)), "min": min(ceny), "max": max(ceny)}


def przelicz_podsumowanie(plik_ofert=PLIK_OFERT, plik_wyj=PLIK_PODSUMOWANIA, teraz=None):
    teraz = time.time() if teraz is None else teraz
    rekordy = []
    if plik_ofert.exists():
        with plik_ofert.open(encoding="utf-8") as f:
            for linia in f:
                try:
                    rekordy.append(json.loads(linia))
                except ValueError:
                    continue
    wynik = {"wygenerowano": datetime.fromtimestamp(teraz).isoformat(timespec="seconds"),
             "uwagi": "liczba = unikalne pewne oferty (nadawca+intencja+przedmiot+cena+ilosc); "
                      "mediana/min/max tylko z cena za sztuke (ea)",
             "okna": {}}
    for nazwa, delta in (("24h", timedelta(hours=24)), ("7d", timedelta(days=7))):
        od = teraz - delta.total_seconds()
        unikalne = {}
        for r in rekordy:
            if not r.get("przedmiot") or r.get("niepewne") or (r.get("ts") or 0) < od:
                continue
            klucz = (r.get("nadawca"), r.get("intencja"), r["przedmiot"], r.get("cena"),
                     r.get("cena_typ"), r.get("ilosc"), r.get("jednostka"))
            unikalne.setdefault(klucz, r)
        per = {}
        for r in unikalne.values():
            strona = "sprzedaz" if r["intencja"] == "sprzedaje" else "kupno"
            d = per.setdefault(r["przedmiot"], {"sprzedaz": {"liczba": 0, "_ea": []},
                                                "kupno": {"liczba": 0, "_ea": []}})
            d[strona]["liczba"] += 1
            if r.get("cena_typ") == "ea" and r.get("cena") is not None:
                d[strona]["_ea"].append(r["cena"])
        for d in per.values():
            for strona in ("sprzedaz", "kupno"):
                ceny = d[strona].pop("_ea")
                d[strona].update(_statystyka(ceny))
        wynik["okna"][nazwa] = dict(sorted(per.items()))
    plik_wyj.write_text(json.dumps(wynik, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return wynik


def powiadom(stan, nadawca, tekst, sucho, teraz):
    if sucho or shutil.which("notify-send") is None:
        return False
    ostatnio = stan.ostatnio_powiadomiono.get(nadawca)
    if ostatnio is not None and teraz - ostatnio < CISZA_ALERTU:
        return False
    stan.ostatnio_powiadomiono[nadawca] = teraz
    try:
        subprocess.run(["notify-send", tekst], timeout=5, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        log(f"notify-send nieudany: {e}")
        return False
    return True


def _cena_tekst(o):
    if o.get("cena") is None:
        return "(bez ceny)"
    txt = f"{o['cena']:g} gp"
    if o.get("cena_typ") == "ea":
        txt += " ea"
    elif o.get("cena_typ") == "all":
        txt += " all"
    return txt


def alerty_z_ofert(oferty, stan, sucho, plik_alertow=PLIK_ALERTOW, teraz=None, notyfikuj=True):
    teraz = time.monotonic() if teraz is None else teraz
    alerty = []
    for o in oferty:
        if o["intencja"] != "kupuje" or o["przedmiot"] not in ALERT_PRZEDMIOTY:
            continue
        cena = _cena_tekst(o)
        tekst = f"Trade: {o['nadawca']} kupuje {o['przedmiot']} {cena}"
        pow = powiadom(stan, o["nadawca"], tekst, sucho, teraz) if notyfikuj else False
        alerty.append({"ts": o["ts"], "czas": o["czas"], "nadawca": o["nadawca"],
                       "przedmiot": o["przedmiot"], "ilosc": o["ilosc"], "jednostka": o["jednostka"],
                       "cena": o["cena"], "cena_typ": o["cena_typ"],
                       "cena_calkowita": o["cena_calkowita"], "tekst_oryg": o["tekst_oryg"],
                       "nr": o["nr"], "powiadomiono": pow})
    zapisz_jsonl(plik_alertow, alerty)
    return alerty


def jeden_cykl(stan, sucho, przedmioty_sciezka=None, plik_ofert=PLIK_OFERT, plik_alertow=PLIK_ALERTOW):
    dane = pobierz_wiadomosci(sciezka_gniazda())
    nowe = stan.nowe(dane.get("wiadomosci", []), dane.get("epoka"))
    oferty = []
    wlasne = 0
    for m in nowe:
        if m.get("nadawca") == WLASNY_NICK:
            wlasne += 1
            continue
        oferty.extend(rozpoznaj(m.get("tekst") or "", m.get("nadawca") or "", m.get("ts"),
                                m.get("nr"), dane.get("epoka")))
    zapisz_jsonl(plik_ofert, oferty)
    alerty = alerty_z_ofert(oferty, stan, sucho, plik_alertow)
    return {"nowe": len(nowe), "wlasne": wlasne, "oferty": oferty, "alerty": alerty}


_STOP = False


def _sygnal(sig, ramka):
    global _STOP
    _STOP = True


def _spij(sekundy):
    koniec = time.monotonic() + sekundy
    while not _STOP and time.monotonic() < koniec:
        time.sleep(min(0.2, max(0.0, koniec - time.monotonic())))


def _zyje(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def zajmij_pid():
    PLIK_PID.parent.mkdir(parents=True, exist_ok=True)
    if PLIK_PID.exists():
        try:
            pid = int(PLIK_PID.read_text().strip())
        except ValueError:
            pid = None
        if pid and pid != os.getpid() and _zyje(pid):
            raise SystemExit(f"trade_logger juz dziala (PID {pid}), odmowa startu")
    PLIK_PID.write_text(str(os.getpid()) + "\n", encoding="utf-8")


def zwolnij_pid():
    try:
        if PLIK_PID.read_text().strip() == str(os.getpid()):
            PLIK_PID.unlink()
    except OSError:
        pass


def petla(stan, sucho):
    ostatnie_podsumowanie = None
    while not _STOP:
        sen = INTERWAL
        try:
            wynik = jeden_cykl(stan, sucho)
            if wynik["nowe"]:
                log(f"nowe wiadomosci Trade: {wynik['nowe']}, oferty: {len(wynik['oferty'])}, "
                    f"alerty: {len(wynik['alerty'])}")
        except (OSError, ValueError, RuntimeError) as e:
            sen = PONOW
            log(f"blad gniazda: {e}; ponawiam za {PONOW:.0f} s")
        if ostatnie_podsumowanie is None or time.monotonic() - ostatnie_podsumowanie >= INTERWAL_PODSUMOWANIA:
            try:
                przelicz_podsumowanie()
            except OSError as e:
                log(f"podsumowanie nieudane: {e}")
            ostatnie_podsumowanie = time.monotonic()
        _spij(sen)


def tryb_raz(stan, sucho):
    wynik = jeden_cykl(stan, sucho)
    oferty = wynik["oferty"]
    pewne = [o for o in oferty if o["przedmiot"] and not o["niepewne"]]
    niepewne = [o for o in oferty if o["niepewne"]]
    print(f"nowe wiadomosci Trade: {wynik['nowe']} (wlasne pominiete: {wynik['wlasne']})")
    print(f"rozpoznane oferty: {len(oferty)}, pewne z przedmiotem: {len(pewne)}, niepewne: {len(niepewne)}")
    print(f"z cena za sztuke (ea): {sum(1 for o in pewne if o['cena_typ'] == 'ea')}, "
          f"z cena lacznie (all): {sum(1 for o in pewne if o['cena_typ'] == 'all')}")
    per = {}
    for o in pewne:
        per[(o["intencja"], o["przedmiot"])] = per.get((o["intencja"], o["przedmiot"]), 0) + 1
    for (intencja, przedmiot), n in sorted(per.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {intencja:10s} {przedmiot}: {n}")
    print(f"alerty kupna: {len(wynik['alerty'])}")
    przelicz_podsumowanie()
    print(f"podsumowanie zapisane: {PLIK_PODSUMOWANIA}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Logger czatu Trade (tylko odczyt).")
    ap.add_argument("--raz", action="store_true", help="jedna iteracja i koniec")
    ap.add_argument("--sucho", action="store_true", help="bez notify-send")
    args = ap.parse_args(argv)

    stan = Stan(plik_seed=PLIK_OFERT)
    if args.raz:
        return tryb_raz(stan, args.sucho)

    zajmij_pid()
    signal.signal(signal.SIGINT, _sygnal)
    signal.signal(signal.SIGTERM, _sygnal)
    log(f"start trade_logger (gniazdo: {sciezka_gniazda()}, sucho: {args.sucho})")
    try:
        petla(stan, args.sucho)
    except KeyboardInterrupt:
        pass
    finally:
        zwolnij_pid()
        log("koniec trade_logger")
    return 0


if __name__ == "__main__":
    sys.exit(main())
