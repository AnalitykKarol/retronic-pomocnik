#!/usr/bin/env python3
"""Statystyki spotkań z obcymi graczami dla okna (26.10, Karol: „na karcie postaci i w zakładce Spotkania”). TYLKO ODCZYT: nic nie zapisuje w instancje/*,
nie dotyka gry ani botów; jedyny zapis to cache obliczenia w katalogu runtime (XDG_RUNTIME_DIR), czyli poza repo.

Używane przez `okno_api.py` (sekcja `spotkania` w `stan`, polecenie `spotkania`). Liczenie NIE jest tu powielane:
  * czas na spocie, liczba graczy, SPOTKAŃ, spotkań/h, bywalec (najczęstszy nick) i ostatnio widziany gracz: `narzedzia/spotkania_graczy_raport.py` (`raport_instancji`,
    „od ostatniego startu bota”, kryterium „na spocie” z telemetrii i logu sesji). Od 26.10 (Karol) „spotkań”, spotkań/h i bywalec to spotkania BEZ minimalnego czasu widoku
    (1 próbka wystarczy, nowy epizod tego samego nicku po >= 5 min bez niego), ZAWSZE z telemetrii; to tylko wyświetlanie, bot liczy po staremu;
  * licznik decyzyjny bota n/PRÓG (`n`, `prog`, `spotkan_prog15`, `bywalec_prog15`; nadzorca zmienia spot po PRÓG spotkaniach, każde >= 15 s w widoku): gdy `instancje/<id>/spotkania_graczy.json` pochodzi Z BIEŻĄCEJ sesji bota (klucz `sesja` = „<pid>-<epoch>” procesu, który teraz działa;
    pokrętło SPOT_ZMIANA_PRZY_GRACZU=1 + LICZNIK_OD_STARTU=1), bierzemy go zamiast telemetrii (to jest dokładnie to, co liczy bot, razem z jego filtrami wrogów/czaszek);
    inaczej reguły bota policzone z telemetrii (`spotkan_prog15`, `nicki_prog15`; `zrodlo` = „telemetria”). `zrodlo` opisuje więc tylko licznik n/PRÓG;
  * „widziani” (26.10): różni obcy gracze w zasięgu wzroku od WEJŚCIA NA OBECNY SPOT (`ostatnie.json` `na_spocie_od`), >= 1 próbka, bez progu 15 s; zawsze z telemetrii
    (`RAP.licz_widzianych`, te same filtry i kryterium „na spocie”), także gdy `zrodlo` = „bot”. Brak `na_spocie_od` = `widziani` None + `widziani_powod` (okno: „-”);
  * zmiany spotu: dziennik nadzorcy `instancje/_wspolne/logi/nadzor-RRRRMMDD.jsonl` (kody spot-gracz / spot-gracz-powrot / spot-gracz-brak) i lista unikanych spotów
    w `instancje/_wspolne/nadzor_stan.json` (`postacie.<id>.spot_gracz.unikane`, `.zmiany`).

Wiarygodność: wpis „dostepne” tylko gdy bot instancji DZIAŁA TERAZ, jego pid jest pidem próbek telemetrii z liczonej sesji i (gdy znany) `ostatnie.json` `sesja.start`
zgadza się z `sesja` telemetrii. Inaczej `dostepne: false` z powodem (okno pokazuje „-”). Koszt: raport czyta telemetrię (ok. 0,5 s na instancję), więc wynik jest
w cache (TTL 60 s, plik w runtime, blokada flock); `stan` czyta wyłącznie cache, liczy tylko polecenie `spotkania`.
"""
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent
for _p in (str(KAT), str(KAT / "narzedzia")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import spot_gracz as SG  # noqa: E402
import spotkania_graczy_raport as RAP  # noqa: E402

CACHE_TTL_S = 60.0          # liczenie z telemetrii najwyżej raz na tyle sekund (polecenie `spotkania`); okno pyta co 30 s
PRZELICZ_MIN_S = 15.0       # nowa sesja bota / brakujący wpis wymusza przeliczenie wcześniej niż TTL, ale nie częściej niż co tyle sekund
STARE_S = 180.0             # wynik starszy niż tyle sekund nie trafia na kartę (nikt nie odświeża, np. okno nie pyta)
SWIEZA_TELEMETRIA_S = 180.0 # ostatnia próbka telemetrii starsza niż tyle sekund = bot nie pisze, dane nieaktualne
MIN_NA_H_S = 600.0          # spotkań/h pokazujemy dopiero po 10 minutach na spocie (krótszy czas daje zawyżoną, losową średnią)
SESJA_ZGODA_S = 5.0         # tolerancja porównania `sesja` telemetrii z `ostatnie.json` `sesja.start`
SESJA_BOT_ZGODA_S = 600.0   # tolerancja epoch w `sesja` licznika bota („<pid>-<epoch>”) względem startu sesji telemetrii
WIDZIANI_LISTA_MAX = 8      # tylu najczęściej widzianych graczy niesie cache/stan (pełna lista tylko w raporcie)
ZMIANY_MAX = 40             # tyle zmian spotu z dziennika dziś (najnowsze pierwsze)
PROG = SG.SPOTKAN_MAX

GRANICE = (
    "Czas i spotkania liczone od ostatniego startu bota, tylko gdy postać jest na spocie (nie w dojściu, w mieście ani na wyprawie po serwis).",
    "Spotkanie (kolumna „spotkań”, spotkań/h, bywalec) = obcy gracz w zasięgu wzroku choćby na jedną próbkę; ten sam gracz liczy się znów po 5 minutach bez niego. Z telemetrii, bez listy wrogów PK ani czaszek.",
    "„Próg bota n/3” to licznik decyzyjny bota: spotkanie liczy się dopiero po 15 s w widoku, po 3. spotkaniu tego samego gracza nadzorca zmienia spot. Dlatego bywa mniejszy niż „spotkań”.",
    "Widziani: różni obcy gracze w zasięgu wzroku (nawet na jedną próbkę telemetrii) od wejścia na obecny spot, tylko gdy postać jest na spocie; z telemetrii, bez listy wrogów PK.",
    "Licznik „próg bota” ze źródła „bot” to dokładnie licznik bota, ale po zleceniu zmiany spotu jego licznik tego gracza startuje od zera.",
    "Spotkań na godzinę dopiero po 10 minutach na spocie. Dane odświeżają się co ok. minutę.",
    "Zmiany spotu z dziennika nadzorcy: wpis „cień” znaczy, że nadzorca tylko zapisał, co by zrobił.",
)

RE_ZMIANA = re.compile(r"^gracz (?P<nick>.+?) spotkany (?P<n>\d+)\. raz na (?P<z>\S+): zmiana spotu -> (?P<na>\S+)")
RE_POWROT = re.compile(r"^gracz (?P<nick>.+?) spotkany (?P<n>\d+)\. raz na (?P<z>\S+): brak wolnego spotu -> powrót do miasta")
RE_BRAK = re.compile(r"^gracz (?P<nick>.+?) \((?P<n>\d+)\. spotkanie\) na (?P<z>\S+): brak sensownego spotu, zostaje")
KODY = {"spot-gracz": "zmiana", "spot-gracz-powrot": "powrot", "spot-gracz-brak": "brak"}
POWOD_TXT = {"zmiana": "gracz {nick} {n}. raz", "powrot": "brak wolnego spotu → powrót do miasta", "brak": "brak sensownego spotu, zostaje"}


# ---------- cache ----------
def _runtime():
    for k in (os.environ.get("XDG_RUNTIME_DIR"), f"/run/user/{os.getuid()}"):
        if k and Path(k).is_dir():
            return Path(k)
    return Path("/tmp")


def sciezka_cache(korzen):
    h = hashlib.sha1(str(Path(korzen).resolve()).encode()).hexdigest()[:10]
    return _runtime() / f"retronic-okno-spotkania-{h}.json"


def czytaj_cache(korzen):
    try:
        c = json.loads(sciezka_cache(korzen).read_text(encoding="utf-8"))
        return c if isinstance(c, dict) and isinstance(c.get("instancje"), dict) and isinstance(c.get("t"), (int, float)) else None
    except (OSError, ValueError):
        return None


def zapisz_cache(korzen, dane):
    p = sciezka_cache(korzen)
    tmp = p.with_name(p.name + f".{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(dane, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, p)
        return True
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


# ---------- pomocnicze odczyty ----------
def _json(plik):
    try:
        d = json.loads(Path(plik).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _liczba(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def postac_instancji(korzen, id_):
    return str(_json(Path(korzen) / "instancje" / id_ / "profil.json").get("postac") or "").strip() or id_


def stracona(korzen, id_):
    return bool(_json(Path(korzen) / "instancje" / id_ / "profil.json").get("stracony"))


def start_sesji_ostatnie(korzen, id_):
    ses = _json(Path(korzen) / "instancje" / id_ / "ostatnie.json").get("sesja")
    return ses.get("start") if isinstance(ses, dict) and _liczba(ses.get("start")) else None


def licznik_bota(korzen, id_, pid, sesja_tel):
    """Licznik z `instancje/<id>/spotkania_graczy.json`, ale tylko gdy jego `sesja` („<pid>-<epoch>”) to proces, który teraz działa (pid z telemetrii = pid bota),
    a epoch jest blisko startu sesji telemetrii. None = plik nieobecny albo z innej sesji (wtedy raport z telemetrii). Tylko odczyt."""
    d = _json(Path(korzen) / "instancje" / id_ / SG.PLIK_LICZNIKA)
    ses = d.get("sesja")
    gr = d.get("gracze")
    if not isinstance(ses, str) or not isinstance(gr, dict) or "-" not in ses or not _liczba(sesja_tel) or pid is None:
        return None
    p, _, ep = ses.rpartition("-")
    try:
        if int(p) != int(pid) or abs(int(ep) - float(sesja_tel)) > SESJA_BOT_ZGODA_S:
            return None
    except ValueError:
        return None
    wpisy = []
    for e in gr.values():
        if isinstance(e, dict) and _liczba(e.get("ostatnio_t")) and isinstance(e.get("spotkan"), int) and not isinstance(e.get("spotkan"), bool):
            wpisy.append((max(0, e["spotkan"]), float(e["ostatnio_t"]), str(e.get("nick") or "?")))
    return wpisy


# ---------- liczenie jednej instancji ----------
def niedostepne(id_, postac, powod, teraz, **extra):
    return {"id": id_, "postac": postac, "dostepne": False, "powod": powod, "prog": PROG, "obliczono_t": round(teraz, 1), **extra}


def licz_instancje(korzen, id_, postac, pidy, teraz):
    """Wpis cache jednej instancji. `pidy` = pidy działających botów tej instancji (z /proc). Zawsze słownik; nigdy wyjątek."""
    try:
        if not pidy:
            return niedostepne(id_, postac, "bot nie działa", teraz)
        r = RAP.raport_instancji(korzen, id_)
        if r.get("blad"):
            return niedostepne(id_, postac, r["blad"], teraz)
        pid, ses = r.get("pid"), r.get("sesja")
        if r.get("do") is None or teraz - r["do"] > SWIEZA_TELEMETRIA_S:
            return niedostepne(id_, postac, "telemetria nieświeża (bot nie pisze)", teraz)
        if pid is not None and pid not in pidy:
            return niedostepne(id_, postac, "dane z innej sesji bota", teraz)
        ost_start = start_sesji_ostatnie(korzen, id_)
        if ost_start is not None and _liczba(ses) and abs(ost_start - ses) > SESJA_ZGODA_S:
            return niedostepne(id_, postac, "dane z innej sesji bota", teraz)
        if pid is None and ost_start is None:
            return niedostepne(id_, postac, "nie da się potwierdzić sesji bota", teraz)
        czas_s = float(r.get("czas_na_spocie_h") or 0.0) * 3600.0
        nicki = [(n, int(c)) for n, c in (r.get("nicki") or [])]                              # spotkania BEZ progu widoku (to pokazuje okno jako „spotkań”)
        nicki15 = [(n, int(c)) for n, c in (r.get("nicki_prog15") or [])]                      # reguły bota (15 s w widoku): licznik n/PRÓG
        graczy, spotkan = int(r.get("graczy") or 0), int(r.get("spotkan") or 0)
        spotkan15 = int(r.get("spotkan_prog15") or 0)
        bywalec = {"nick": nicki[0][0], "n": nicki[0][1]} if nicki else None
        n = nicki15[0][1] if nicki15 else 0
        bywalec15 = {"nick": nicki15[0][0], "n": nicki15[0][1]} if nicki15 else None
        ostatni = dict(r["ostatni"]) if isinstance(r.get("ostatni"), dict) else None
        zrodlo = "telemetria"
        bot = licznik_bota(korzen, id_, pid, ses)
        if bot is not None:
            zrodlo = "bot"
            graczy, spotkan15 = len(bot), sum(w[0] for w in bot)
            top = max(bot, key=lambda w: (w[0], w[1]), default=None)
            n = top[0] if top else 0
            bywalec15 = {"nick": top[2], "n": top[0]} if top and top[0] >= 1 else None
            ost = max(bot, key=lambda w: w[1], default=None)
            ostatni = {"nick": ost[2], "t": ost[1]} if ost else ostatni
        na_h = round(spotkan / (czas_s / 3600.0), 2) if czas_s >= MIN_NA_H_S else None
        wid_lista = [dict(e) for e in (r.get("widziani_lista") or [])[:WIDZIANI_LISTA_MAX]]
        wpis = {"id": id_, "postac": postac, "dostepne": True, "powod": None, "zrodlo": zrodlo, "sesja_start": ses, "pid": pid, "od": r.get("od"), "do": r.get("do"),
                "n": n, "prog": PROG, "bywalec": bywalec, "bywalec_prog15": bywalec15, "graczy": graczy, "spotkan": spotkan, "spotkan_prog15": spotkan15, "czas_na_spocie_s": round(czas_s), "spotkan_na_h": na_h,
                "ostatni": ostatni, "uwaga": r.get("uwaga"), "obliczono_t": round(teraz, 1),
                "widziani": r.get("widziani"), "widziani_od": r.get("widziani_od"), "widziani_lista": wid_lista, "widziani_powod": r.get("widziani_powod"),
                "widziani_uwaga": r.get("widziani_uwaga")}
        return wpis
    except Exception as e:                              # jeden błąd nie psuje reszty (i nigdy okna)
        return niedostepne(id_, postac, "błąd liczenia", teraz, blad=f"{type(e).__name__}: {e}")


# ---------- odświeżanie cache (polecenie `spotkania`) ----------
def wymaga_przeliczenia(cache, procesy_bot, teraz):
    """Czy cache jest za stary albo nie zna bieżącej sesji któregoś działającego bota. `procesy_bot` = {id: [pid, ...]}."""
    if cache is None:
        return True
    wiek = teraz - cache["t"]
    if wiek < 0 or wiek >= CACHE_TTL_S:             # cofnięty zegar też unieważnia
        return True
    if wiek < PRZELICZ_MIN_S:
        return False
    for id_, pidy in procesy_bot.items():
        e = cache["instancje"].get(id_)
        if pidy and (e is None or (e.get("dostepne") and e.get("pid") not in pidy) or e.get("powod") == "bot nie działa"):
            return True
        if not pidy and e is not None and e.get("dostepne"):
            return True
    return False


def odswiez(korzen, procesy_bot, teraz, wymus=False):
    """-> (cache, status) gdzie status: "swiezy" (z cache), "przeliczony", "liczy_sie" (ktoś inny liczy: stary cache albo None). `procesy_bot` = {id: [pid, ...]}
    dla WSZYSTKICH instancji do pokazania (puste = bot nie działa)."""
    cache = czytaj_cache(korzen)
    if not wymus and not wymaga_przeliczenia(cache, procesy_bot, teraz):
        return cache, "swiezy"
    import fcntl  # noqa: PLC0415
    p = sciezka_cache(korzen)
    try:
        blokada = open(p.with_name(p.name + ".lock"), "a")
    except OSError:
        blokada = None
    try:
        if blokada is not None:
            try:
                fcntl.flock(blokada, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return cache, "liczy_sie"
            cache2 = czytaj_cache(korzen)           # ktoś mógł zdążyć między odczytem a blokadą
            if cache2 is not None and not wymus and not wymaga_przeliczenia(cache2, procesy_bot, teraz):
                return cache2, "swiezy"
        t0 = time.monotonic()
        wpisy = {}
        for id_, pidy in procesy_bot.items():
            postac = postac_instancji(korzen, id_)
            wpisy[id_] = niedostepne(id_, postac, "postać stracona", teraz) if stracona(korzen, id_) else licz_instancje(korzen, id_, postac, pidy, teraz)
        cache = {"v": 1, "t": round(teraz, 1), "czas_liczenia_s": round(time.monotonic() - t0, 2), "instancje": wpisy}
        zapisz_cache(korzen, cache)
        return cache, "przeliczony"
    finally:
        if blokada is not None:
            blokada.close()


# ---------- sekcja `spotkania` w `stan` (lekka, tylko cache) ----------
POLA_LEKKIE = ("zrodlo", "n", "prog", "bywalec", "bywalec_prog15", "graczy", "spotkan", "spotkan_prog15", "czas_na_spocie_s", "spotkan_na_h", "ostatni", "uwaga",
               "widziani", "widziani_od", "widziani_lista", "widziani_powod", "widziani_uwaga")


def sekcja_dla_stanu(korzen, id_, pidy, ostatnie_sesja_start, teraz):
    """Kształt `stan.instancje[].spotkania`: {"dostepne": bool, "powod": str|None, ...pola lekkie, "wiek_s"}. Nigdy wyjątek (błąd = dostepne false + `blad`)."""
    try:
        if not id_:
            return {"dostepne": False, "powod": "instancja główna", "prog": PROG}
        if not pidy:
            return {"dostepne": False, "powod": "bot nie działa", "prog": PROG}
        c = czytaj_cache(korzen)
        e = c["instancje"].get(id_) if c else None
        if e is None:
            return {"dostepne": False, "powod": "jeszcze nie policzone", "prog": PROG}
        wiek = round(max(0.0, teraz - c["t"]), 1)
        if wiek > STARE_S:
            return {"dostepne": False, "powod": "dane nieaktualne", "prog": PROG, "wiek_s": wiek}
        if not e.get("dostepne"):
            return {"dostepne": False, "powod": e.get("powod"), "prog": PROG, "wiek_s": wiek}
        if e.get("pid") is not None and e["pid"] not in pidy:
            return {"dostepne": False, "powod": "dane z poprzedniej sesji bota", "prog": PROG, "wiek_s": wiek}
        if _liczba(ostatnie_sesja_start) and _liczba(e.get("sesja_start")) and abs(ostatnie_sesja_start - e["sesja_start"]) > SESJA_ZGODA_S:
            return {"dostepne": False, "powod": "dane z poprzedniej sesji bota", "prog": PROG, "wiek_s": wiek}
        return {"dostepne": True, "powod": None, **{k: e.get(k) for k in POLA_LEKKIE}, "wiek_s": wiek}
    except Exception as ex:
        return {"dostepne": False, "powod": "błąd odczytu", "blad": f"{type(ex).__name__}: {ex}", "prog": PROG}


# ---------- zmiany spotu (dziennik nadzorcy) i unikane spoty ----------
def _epoch_lokalny(tekst):
    try:
        return time.mktime(time.strptime(str(tekst), "%Y-%m-%d %H:%M:%S"))
    except (ValueError, OverflowError):
        return None


def zmiany_dzis(korzen, teraz, nazwy=None):
    """Zmiany spotu po spotkaniach graczy z dziennika nadzorcy z dzisiaj (lokalnie), najnowsze pierwsze, powtórki tego samego zdarzenia zwinięte
    (`powt`). -> [{"t","id","postac","typ": zmiana|powrot|brak,"nick","n","z","na","powod","status": wykonano|cien|blad|info,"tekst"}]."""
    plik = Path(korzen) / "instancje" / "_wspolne" / "logi" / f"nadzor-{time.strftime('%Y%m%d', time.localtime(teraz))}.jsonl"
    nazwy = nazwy if nazwy is not None else {}
    lt = time.localtime(teraz)
    poczatek_dnia = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    wynik, widziane = [], {}
    try:
        f = open(plik, encoding="utf-8", errors="replace")
    except OSError:
        return wynik
    with f:
        for l in f:
            if "gracz " not in l and "spot-gracz" not in l:
                continue
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if not isinstance(r, dict) or not isinstance(r.get("powod"), str):
                continue
            tekst = r["powod"]
            typ, m = None, None
            for kod_typ, wz in (("zmiana", RE_ZMIANA), ("powrot", RE_POWROT), ("brak", RE_BRAK)):
                m = wz.match(tekst)
                if m:
                    typ = kod_typ
                    break
            if typ is None and r.get("kod") in KODY:           # dziennik z polem `kod`, ale innym brzmieniem tekstu
                typ = KODY[r["kod"]]
            if typ is None:
                continue
            g = m.groupdict() if m else {}
            t = _epoch_lokalny(r.get("t"))
            if t is None or t < poczatek_dnia:
                continue
            id_ = str(r.get("id") or "")
            wynik_log = str(r.get("wynik") or "")
            status = "wykonano" if wynik_log == "ok" else "blad" if wynik_log == "blad" else "cien" if wynik_log in ("cień", "cien") else "info"
            nick, n = g.get("nick") or "?", int(g["n"]) if g.get("n") else None
            wpis = {"t": t, "id": id_, "postac": nazwy.get(id_) or id_, "typ": typ, "nick": nick, "n": n, "z": g.get("z"), "na": g.get("na"),
                    "powod": POWOD_TXT[typ].format(nick=nick, n=n), "status": status, "tekst": tekst[:300], "powt": 1}
            k = (id_, typ, nick, n, wpis["z"], wpis["na"], status)
            if k in widziane:
                widziane[k]["powt"] += 1
                continue
            widziane[k] = wpis
            wynik.append(wpis)
    wynik.sort(key=lambda w: -w["t"])
    return wynik[:ZMIANY_MAX]


def unikane_i_zmiany(korzen, teraz, nazwy=None):
    """Z `nadzor_stan.json`: ({"unikane": [{id, postac, mapa, jaskinia, nick, do, zostalo_s}], "zmian_doba": {id: n}}). Brak pliku = puste."""
    nazwy = nazwy if nazwy is not None else {}
    stan = _json(Path(korzen) / "instancje" / "_wspolne" / "nadzor_stan.json")
    post = stan.get("postacie") if isinstance(stan.get("postacie"), dict) else {}
    unik, doba = [], {}
    for id_, p in post.items():
        sg = p.get("spot_gracz") if isinstance(p, dict) and isinstance(p.get("spot_gracz"), dict) else None
        if not sg:
            continue
        for u in SG.unikane_aktywne(sg.get("unikane"), teraz):
            unik.append({"id": id_, "postac": nazwy.get(id_) or id_, "mapa": str(u.get("mapa")), "jaskinia": str(u.get("jaskinia") or u.get("mapa")),
                         "nick": str(u.get("nick") or "?"), "do": u["do"], "zostalo_s": round(u["do"] - teraz)})
        z = sg.get("zmiany") if isinstance(sg.get("zmiany"), list) else []
        n = sum(1 for t in z if _liczba(t) and 0 <= teraz - t < SG.LIMIT_DOBA_S)
        if n:
            doba[id_] = n
    unik.sort(key=lambda u: u["do"])
    return {"unikane": unik, "zmian_doba": doba}


def ostatni_gracz(wpisy):
    """Najświeższy `ostatni` z dostępnych wpisów -> {"nick","t","postac","instancja"} albo None."""
    naj = None
    for e in wpisy:
        o = e.get("ostatni") if e.get("dostepne") else None
        if isinstance(o, dict) and _liczba(o.get("t")) and (naj is None or o["t"] > naj["t"]):
            naj = {"nick": o.get("nick"), "t": o["t"], "postac": e.get("postac"), "instancja": e.get("id")}
    return naj
