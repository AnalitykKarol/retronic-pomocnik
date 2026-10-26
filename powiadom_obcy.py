#!/usr/bin/env python3
"""Dymek na pulpicie, gdy OBCY gracz pojawia się w zasięgu wzroku postaci (26.10, decyzje Karola). TYLKO ODCZYT: ogonuje
`instancje/<id>/logi/telemetria-RRRRMMDD.jsonl` (to, co bot i tak zapisuje), nic nie klika, nic nie pisze w grze, nie dotyka
bota, `spot_gracz.Licznik` ani cavebota. Czytnik osobnym procesem (jak powiadom_czat.py), więc jego awaria nie rusza bota.

Kiedy dymek: na POCZĄTEK każdego „spotkania” w nowym znaczeniu raportu spotkań, czyli gdy pierwsza próbka z tym nickiem pojawia się
po >= spot_gracz.PRZERWA_S (300 s) bez niego (albo w ogóle pierwszy raz). Bez progu czasu widoku i bez progu odległości (zasięg =
to, co telemetria zapisuje w `stwory`: okno mapy). Tylko gdy postać jest „na spocie” i z TYMI SAMYMI filtrami co licznik spotkań:
reguły bierzemy WPROST z narzedzia/spotkania_graczy_raport.py (`_widoczni_obcy`: bez własnego nicku, naszych postaci, GM, czaszki/PK,
hp <= 0; `_na_spocie`: stan bota poza WYPAD/WPADNIECIE/PAUZA_STOJ/..., nie w dojściu; `okna_dojscia`), niczego nie kopiujemy.
Test pilnuje zgodności: liczba dymków == `spotkan` z raportu na tych samych próbkach.

Treść (1 linia, pilność low): „Geblish: Vados obok (3 pola) · ph_raty_z8”. Klucz = obcy:<instancja>:<nick>; powiadom.Powiadamiacz
(1 dymek na klucz / 60 s, cisza: plik `cisza` albo RETRONIC_POWIADOMIENIA=0). Limit godzinowy: własny egzemplarz Powiadamiacza w
tym procesie z limitem LIMIT_H (60 zamiast 20), bo 20/h zgubiłoby dymki na ruchliwym spocie; nie dzieli go z botem ani z czytnikiem czatu.
Nazwa mapy: ostatni wpis `[TRYB] mapa <nazwa>:` z logi/tryb.log nie późniejszy niż próbka (fallback: ostatnie.json `mapa`).

Samonaprawa: ogon pliku trzyma offset i numer i-węzła per plik (obcięcie / podmiana pliku = od początku), czyta tylko kompletne linie
(niedopisana ostatnia zostaje na następny obieg), zna dwa ostatnie pliki dzienne (przejście przez północ: dopisanie starego pliku
jeszcze po północy + nowy plik), restart bota nic nie zmienia (ten sam plik), brak pliku = czekanie. Przy starcie czytnika
„rozgrzewka”: ostatnie PRZERWA_S + 120 s telemetrii przechodzi przez detektor BEZ dymków, więc restart czytnika nie wywołuje dymków
za gracza widzianego przed chwilą. Próbki starsze niż STARE_S (np. po uśpieniu komputera) nie dają dymka, tylko wpis w logu.
Log: instancje/<id>/logi/powiadom-obcy-RRRRMMDD.log (każdy epizod: czas próbki, nick, odległość, mapa, dymek tak/nie).

Włączanie: flaga `"powiadom_obcy": true` w instancje/<id>/profil.json, DOMYŚLNIE WYŁĄCZONA. sesja.sh woła `powiadom_obcy.py --uruchom`
(odłączony, setsid, jeden egzemplarz: kontrola po /proc + flock). Czytnik startowany przez --uruchom kończy się, gdy flaga zniknie z profilu.

Użycie:  RETRONIC_ID=gebelish python3 -I powiadom_obcy.py --wlacz     # ustawia flagę w profilu (edycja tekstowa) i od razu startuje czytnik
         RETRONIC_ID=gebelish python3 -I powiadom_obcy.py --wylacz    # flaga false; czytnik sam się kończy w ciągu ~30 s
         RETRONIC_ID=gebelish python3 -I powiadom_obcy.py --uruchom   # jak sesja.sh: start w tle, jeśli flaga w profilu
         RETRONIC_ID=gebelish python3 -I powiadom_obcy.py             # na pierwszym planie
         python3 -I powiadom_obcy.py --sucho [--instancja gebelish] [--dzien 20261026]   # co by poszło, bez wysyłania (domyślnie dziś, wszystkie instancje)
Zmienne (testy): RETRONIC_POWIADOM_KATALOG (zamiast katalogu pomocnika), RETRONIC_POWIADOM_NOTIFY (zamiast notify-send),
RETRONIC_POWIADOM_OBCY_ODSWIEZ_S."""
import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
KAT = Path(__file__).resolve().parent
for _p in (str(KAT), str(KAT / "narzedzia")):
    if _p not in sys.path:
        sys.path.insert(0, _p)                        # python3 -I nie dodaje katalogu skryptu
import instancja  # noqa: E402
import powiadom  # noqa: E402
import spot_gracz as SG  # noqa: E402
import spotkania_graczy_raport as R  # noqa: E402

ODSWIEZ_S = float(os.environ.get("RETRONIC_POWIADOM_OBCY_ODSWIEZ_S", "1.0"))
LIMIT_H = 60                                          # dymków/h w tym procesie (powiadom.LIMIT_H = 20 zgubiłby je przy ruchliwym spocie)
ROZGRZEWKA_S = SG.PRZERWA_S + 120                     # tyle telemetrii wstecz przechodzi przez detektor bez dymków (start czytnika)
ROZGRZEWKA_BAJTY = 4_000_000                          # i tyle bajtów z końca pliku (próbka ~0,5-1 KB, 1 próbka/s)
STARE_S = 120                                         # próbka starsza niż tyle (względem zegara) nie daje dymka
OKNA_TTL_S = 3.0                                      # jak długo trzymamy wynik okna_dojscia (czytanie logów bota tylko, gdy jest kandydat)
ODSWIEZ_NAZW_S = 60.0                                 # nasze postacie i własny nick: nowe instancje/zmiany profilu
SPRAWDZ_FLAGE_S = 30.0
MAX_BAJTOW_OBIEGU = 8_000_000
PLIKI_TELEMETRII = 2                                  # ostatni dzień i poprzedni (przejście przez północ)
RE_MAPA = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) \[TRYB\] mapa (\S+?):")
FLAGA = "powiadom_obcy"


def pola(n):
    """„1 pole”, „2 pola”, „5 pól”, „12 pól”, „22 pola”."""
    n = int(n)
    if n == 1:
        return "1 pole"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} pola"
    return f"{n} pól"


def odleglosc(r, nick):
    """Najmniejsza `odl` wpisów gracza o tym nicku w próbce (telemetria zapisuje odl = Czebyszew); None, gdy brak pola."""
    k = SG.klucz(nick)
    odl = [s.get("odl") for s in r.get("stwory") or () if isinstance(s, dict) and s.get("gracz") and SG.klucz(s.get("n")) == k
           and isinstance(s.get("odl"), (int, float)) and not isinstance(s.get("odl"), bool)]
    return int(min(odl)) if odl else None


def tytul_dymka(ja, nick, odl, mapa):
    t = f"{ja}: {nick} obok" + (f" ({pola(odl)})" if odl is not None else "") + (f" · {mapa}" if mapa else "")
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------------------------------------
# detektor początku spotkania

class LeniweOkna:
    """Okna dojścia (R.okna_dojscia) ładowane dopiero przy pierwszym użyciu (tylko gdy w próbce jest kandydat) i trzymane OKNA_TTL_S
    (ttl None = raz na zawsze: tryb --sucho na zamkniętych plikach). Zachowuje się jak lista dla R.w_dojsciu (iteracja)."""

    def __init__(self, kat_logi, ttl=OKNA_TTL_S, zegar=time.time):
        self.kat_logi, self.ttl, self.zegar = Path(kat_logi), ttl, zegar
        self.rok = datetime.now().year
        self._dane, self._rok, self._kiedy = None, None, 0.0

    def __iter__(self):
        t = self.zegar()
        if self._dane is None or self._rok != self.rok or (self.ttl is not None and t - self._kiedy >= self.ttl):
            try:
                self._dane = R.okna_dojscia(self.kat_logi, self.rok)
            except Exception:  # noqa: BLE001 - brak logów = dojście niesprawdzone, jak w raporcie
                self._dane = []
            self._rok, self._kiedy = self.rok, t
        return iter(self._dane)

    def uniewaznij(self):
        self._dane = None


class MapaZLogu:
    """Nazwa mapy w chwili t: `[TRYB] mapa <nazwa>:` z logi/tryb.log (ostatni wpis <= t); fallback ostatnie.json `mapa`."""

    def __init__(self, stan):
        self.stan = Path(stan)
        self._sygn, self._wpisy = None, []

    def _wczytaj(self):
        p = self.stan / "logi" / "tryb.log"
        try:
            st = p.stat()
        except OSError:
            self._wpisy, self._sygn = [], None
            return
        sygn = (st.st_mtime_ns, st.st_size)
        if sygn == self._sygn:
            return
        wpisy = []
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                for l in f:
                    m = RE_MAPA.match(l)
                    if m:
                        try:
                            wpisy.append((datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").timestamp(), m.group(2)))
                        except ValueError:
                            pass
        except OSError:
            return
        self._wpisy, self._sygn = wpisy, sygn

    def mapa(self, t):
        self._wczytaj()
        nazwa = None
        for ts, n in self._wpisy:
            if ts <= t + 1:
                nazwa = n
            else:
                break
        if nazwa:
            return nazwa
        try:
            return json.loads((self.stan / "ostatnie.json").read_text(encoding="utf-8")).get("mapa") or None
        except (OSError, ValueError, AttributeError):
            return None


class Detektor:
    """Przepuszcza próbki (rosnąco po t) i zwraca początki spotkań: [{t, nick, odl}]. Stan: ostatni czas widzenia nicku NA SPOCIE
    (tak jak `ost_epizod` w R.licz: nick zobaczony poza spotem nie przedłuża epizodu)."""

    def __init__(self, okna, nasze, wlasny):
        self.okna, self.nasze, self.wlasny_k = okna, nasze, SG.klucz(wlasny)
        self.ost = {}

    def ustaw(self, nasze, wlasny):
        self.nasze, self.wlasny_k = nasze, SG.klucz(wlasny)

    def przetworz(self, r):
        widoczni = R._widoczni_obcy(r, self.nasze, self.wlasny_k)
        if not widoczni:
            return []
        t = float(r["t"])
        self.okna.rok = datetime.fromtimestamp(t).year
        if not R._na_spocie(r, self.okna):
            return []
        wynik = []
        for x in widoczni:
            k = SG.klucz(x)
            ost = self.ost.get(k)
            if ost is None or t - ost >= SG.PRZERWA_S:            # ta sama definicja epizodu co R.licz (próbki posortowane po t)
                wynik.append({"t": t, "nick": str(x).strip(), "odl": odleglosc(r, x)})
            self.ost[k] = t if ost is None else max(ost, t)
        return wynik


# ---------------------------------------------------------------------------------------------
# ogon plików telemetrii

def rekord(linia):
    """Próbka telemetrii z linii jsonl albo None (ta sama walidacja co R.probki; src inny niż "mozg" pomijany jak w raporcie)."""
    if '"probka"' not in linia:
        return None
    try:
        r = json.loads(linia)
    except ValueError:
        return None
    if isinstance(r, dict) and r.get("typ") == "probka" and isinstance(r.get("t"), (int, float)) \
            and isinstance(r.get("poz"), list) and r.get("src", "mozg") == "mozg":
        return r
    return None


class Ogon:
    """Ogonuje dwa ostatnie `telemetria-*.jsonl` katalogu logów. `nowe()` zwraca nowe próbki (posortowane po t)."""

    def __init__(self, kat_logi):
        self.kat = Path(kat_logi)
        self.stan = {}                                # nazwa -> {"ino", "off"}

    def pliki(self):
        try:
            return sorted(self.kat.glob("telemetria-*.jsonl"))[-PLIKI_TELEMETRII:]
        except OSError:
            return []

    def rozgrzewka(self, od_t):
        """Próbki z końcówki plików z t >= od_t; ustawia offsety na koniec (po ostatniej kompletnej linii). Nic nie wysyła."""
        wynik = []
        for p in self.pliki():
            try:
                with open(p, "rb") as f:
                    st = os.fstat(f.fileno())
                    pocz = max(0, st.st_size - ROZGRZEWKA_BAJTY)
                    f.seek(pocz)
                    dane = f.read(st.st_size - pocz)
            except OSError:
                continue
            ostatni = dane.rfind(b"\n")
            kompletne = dane[:ostatni + 1] if ostatni >= 0 else b""
            linie = kompletne.split(b"\n")
            if pocz > 0 and linie:
                linie = linie[1:]                     # pierwsza linia mogła zacząć się w środku
            for l in linie:
                r = rekord(l.decode("utf-8", errors="replace"))
                if r and r["t"] >= od_t:
                    wynik.append(r)
            self.stan[p.name] = {"ino": st.st_ino, "off": pocz + len(kompletne)}
        wynik.sort(key=lambda r: r["t"])
        return wynik

    def nowe(self):
        wynik = []
        aktualne = self.pliki()
        for p in aktualne:
            try:
                with open(p, "rb") as f:
                    st = os.fstat(f.fileno())
                    s = self.stan.get(p.name)
                    if s is None:                     # nowy plik (np. po północy): od początku
                        s = self.stan[p.name] = {"ino": st.st_ino, "off": 0}
                    elif s["ino"] != st.st_ino or st.st_size < s["off"]:
                        s["ino"], s["off"] = st.st_ino, 0          # podmieniony / obcięty: od początku
                    if st.st_size <= s["off"]:
                        continue
                    f.seek(s["off"])
                    dane = f.read(min(st.st_size - s["off"], MAX_BAJTOW_OBIEGU))
            except OSError:
                continue
            ostatni = dane.rfind(b"\n")
            if ostatni < 0:
                continue                              # niedopisana linia: zostaje na następny obieg
            s["off"] += ostatni + 1
            for l in dane[:ostatni + 1].split(b"\n"):
                r = rekord(l.decode("utf-8", errors="replace"))
                if r:
                    wynik.append(r)
        for n in list(self.stan):
            if n not in {p.name for p in aktualne}:
                del self.stan[n]
        wynik.sort(key=lambda r: r["t"])
        return wynik


# ---------------------------------------------------------------------------------------------
# profil i start automatyczny

def profil_wlaczony(stan):
    try:
        return json.loads((Path(stan) / "profil.json").read_text()).get(FLAGA) is True
    except (OSError, ValueError, AttributeError):
        return False


def czytniki(id_, proc="/proc"):
    """Pidy działających czytników tej instancji (cmdline + RETRONIC_ID); starter `--uruchom` i pliki testowe się nie liczą."""
    return instancja.procesy(r"(?<![\w])powiadom_obcy\.py(?! --uruchom)(?! --wlacz)(?! --wylacz)(?! --sucho)", id_=id_, proc=proc)


def uruchom(id_, katalog=None, runtime_dir=None, proc="/proc", popen=subprocess.Popen):
    """Idempotentny start czytnika w tle (flaga "powiadom_obcy": true w profilu). Zdanie po polsku; nigdy nie rzuca (best effort dla sesja.sh)."""
    if not id_:
        return "powiadom_obcy: brak RETRONIC_ID (główna instancja nieobsługiwana)"
    try:
        s = instancja.sciezki(id_, runtime_dir or instancja.runtime(f"/run/user/{os.getuid()}"), katalog or instancja.KATALOG)
        if not profil_wlaczony(s.stan):
            return f"powiadom_obcy: wyłączony w profilu {id_} (brak \"{FLAGA}\": true)"
        dziala = czytniki(id_, proc)
        if dziala:
            return f"powiadom_obcy: już działa (pid {dziala[0]})"
        s.logi.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, RETRONIC_ID=id_, RETRONIC_POWIADOM_OBCY_AUTO="1")
        if katalog:
            env["RETRONIC_POWIADOM_KATALOG"] = str(katalog)
        with open(s.logi / "powiadom-obcy-stdout.log", "ab") as out:
            p = popen([sys.executable, "-I", os.path.abspath(__file__)], env=env, stdin=subprocess.DEVNULL,
                      stdout=out, stderr=out, start_new_session=True, cwd=str(s.katalog))
        return f"powiadom_obcy: wystartowany (pid {p.pid})"
    except Exception as e:  # noqa: BLE001 - start sesji nie może przez to paść
        return f"powiadom_obcy: błąd startu: {type(e).__name__}: {e}"


def ustaw_flage(plik, wartosc):
    """Ustawia "powiadom_obcy" w profil.json EDYCJĄ TEKSTOWĄ (reszta pliku bajt w bajt, bez przeformatowania); wynik musi być poprawnym JSON-em
    obiektu. -> True, gdy zapisano (atomowo: tmp + rename)."""
    plik = Path(plik)
    tekst = plik.read_text(encoding="utf-8")
    json.loads(tekst)
    lit = "true" if wartosc else "false"
    nowy, n = re.subn(r'("' + FLAGA + r'"\s*:\s*)(true|false)', lambda m: m.group(1) + lit, tekst, count=1)
    if n == 0:
        k = tekst.rstrip().rfind("}")
        if k < 0:
            raise ValueError("profil.json nie jest obiektem")
        przed = tekst[:k].rstrip()
        przecinek = "" if przed.endswith("{") else ","
        wciecie = " " if "\n" in tekst else ""
        sep = "\n" if "\n" in tekst else ""
        nowy = f'{przed}{przecinek}{sep}{wciecie}"{FLAGA}": {lit}{sep}{tekst[k:]}'
    d = json.loads(nowy)
    if d.get(FLAGA) is not bool(wartosc):
        raise ValueError("edycja nie dała oczekiwanej wartości")
    tmp = plik.with_name(plik.name + ".tmp-powiadom-obcy")
    tmp.write_text(nowy, encoding="utf-8")
    os.replace(tmp, plik)
    return True


# ---------------------------------------------------------------------------------------------
# czytnik na żywo

def nick_postaci(stan, id_):
    try:
        n = (json.loads((Path(stan) / "profil.json").read_text(encoding="utf-8")).get("postac") or "").strip()
    except (OSError, ValueError, AttributeError):
        n = ""
    return n or id_.capitalize()


def petla(s, ja, zegar=time.time, spij=time.sleep, powiadamiacz=None, auto=False, limit_obiegow=None):
    """Główna pętla czytnika. limit_obiegow tylko dla testów (None = bez końca). Zwraca przyczynę zakończenia."""
    logi = Path(s.logi)
    logi.mkdir(parents=True, exist_ok=True)
    pw = powiadamiacz or powiadom.Powiadamiacz(
        uruchom=_notify_z_env(), zegar=zegar, limit_h=LIMIT_H)

    def log(t):
        with open(logi / f"powiadom-obcy-{time.strftime('%Y%m%d', time.localtime(zegar()))}.log", "a") as f:
            f.write(f"{time.strftime('%H:%M:%S', time.localtime(zegar()))} {t}\n")

    nasze = SG.nasze_nicki(Path(s.katalog) / "instancje")
    okna = LeniweOkna(logi, zegar=zegar)
    det = Detektor(okna, nasze, ja)
    mapa = MapaZLogu(s.stan)
    ogon = Ogon(logi)
    for r in ogon.rozgrzewka(zegar() - ROZGRZEWKA_S):
        det.przetworz(r)
    log(f"start: {ja} ({s.id}){' [auto]' if auto else ''}, rozgrzewka: znani gracze {len(det.ost)}")
    odswiez_nazw = sprawdz_flage = zegar()
    obiegi = 0
    ostatni_blad = None
    while True:
        obiegi += 1
        if limit_obiegow is not None and obiegi > limit_obiegow:
            return "limit"
        try:
            teraz = zegar()
            if teraz - odswiez_nazw >= ODSWIEZ_NAZW_S:
                odswiez_nazw = teraz
                ja = nick_postaci(s.stan, s.id)
                det.ustaw(SG.nasze_nicki(Path(s.katalog) / "instancje"), ja)
            if auto and teraz - sprawdz_flage >= SPRAWDZ_FLAGE_S:
                sprawdz_flage = teraz
                if not profil_wlaczony(s.stan):
                    log(f"koniec: flaga {FLAGA} zdjęta z profilu")
                    return "flaga"
            for r in ogon.nowe():
                for ev in det.przetworz(r):
                    m = mapa.mapa(ev["t"])
                    stare = teraz - ev["t"] > STARE_S
                    tytul = tytul_dymka(ja, ev["nick"], ev["odl"], m)
                    poszlo = False if stare else pw.powiadom(tytul, "", "low", klucz=f"obcy:{s.id}:{SG.klucz(ev['nick'])}")
                    powod = "" if poszlo else (" [stara próbka]" if stare else " [limit/cisza]")
                    log(f"{datetime.fromtimestamp(ev['t']):%H:%M:%S} {ev['nick']} odl={ev['odl']} mapa={m} dymek={'tak' if poszlo else 'nie'}{powod}")
            ostatni_blad = None
        except Exception as e:  # noqa: BLE001 - czytnik nie może paść od jednej dziwnej próbki
            opis = f"{type(e).__name__}: {e}"
            if opis != ostatni_blad:
                ostatni_blad = opis
                log(f"BŁĄD w pętli (czytnik trwa): {opis}\n{traceback.format_exc(limit=3)}")
        spij(ODSWIEZ_S)


def _notify_z_env():
    cmd = os.environ.get("RETRONIC_POWIADOM_NOTIFY")
    if not cmd:
        return powiadom._notify_send
    return lambda arg: subprocess.run([*cmd.split(), *arg], timeout=powiadom.TIMEOUT_S, capture_output=True)


# ---------------------------------------------------------------------------------------------
# tryb --sucho

def sucho_instancji(korzen, id_, dzien):
    """Co by poszło dla instancji w dniu `dzien` (RRRRMMDD): lista {t, nick, odl, mapa}, bez wysyłania i bez limitów czasowych dymków.
    Próbki jak w raporcie (R.probki, src mozg, posortowane po t), okna dojścia z logów bota."""
    kat = Path(korzen) / "instancje" / id_
    pliki = R.pliki_telemetrii(kat / "logi", dzien)
    lista = [r for p in pliki for r in R.probki(p) if r.get("src", "mozg") == "mozg"]
    lista.sort(key=lambda r: r["t"])
    if not lista:
        return [], None
    postac = nick_postaci(kat, id_)
    okna = LeniweOkna(kat / "logi", ttl=None)
    det = Detektor(okna, R.nasze_nicki_instancji(korzen), postac)
    mapa = MapaZLogu(kat)
    wynik = []
    for r in lista:
        for ev in det.przetworz(r):
            wynik.append({**ev, "mapa": mapa.mapa(ev["t"])})
    return wynik, postac


def sucho(korzen, tylko, dzien, out=print):
    lacznie = 0
    for id_ in R.instancje(korzen, tylko):
        ev, postac = sucho_instancji(korzen, id_, dzien)
        if postac is None:
            out(f"{id_}: brak telemetrii z dnia {dzien}")
            continue
        for e in ev:
            out(f"{datetime.fromtimestamp(e['t']):%H:%M:%S}  {id_:<10} {tytul_dymka(postac, e['nick'], e['odl'], e['mapa'])}")
        ts = [e["t"] for e in ev]
        kroczace = max((sum(1 for u in ts if 0 <= t0 - u < 3600) for t0 in ts), default=0)
        razem = sorted({e["nick"] for e in ev})
        rap = R.raport_instancji(korzen, id_, dzien)
        zgodne = "zgodne" if rap.get("spotkan") == len(ev) else f"RÓŻNICA (raport: {rap.get('spotkan')})"
        out(f"  {id_} ({postac}): dymków {len(ev)}, różnych nicków {len(razem)}, najwięcej w 60 min {kroczace} (limit {LIMIT_H}/h); "
            f"raport spotkań: {rap.get('spotkan')} ({zgodne})")
        lacznie += len(ev)
    out(f"RAZEM dymków (sucho, bez limitów czasowych): {lacznie}")
    return lacznie


def main(argv=None):
    a = argparse.ArgumentParser(description="Dymek przy pojawieniu się obcego gracza (czytnik telemetrii, tylko odczyt)")
    a.add_argument("--uruchom", action="store_true", help="start w tle, jeśli flaga w profilu (jak z sesja.sh)")
    a.add_argument("--wlacz", action="store_true", help="ustaw flagę w profilu i wystartuj czytnik")
    a.add_argument("--wylacz", action="store_true", help="zdejmij flagę w profilu (czytnik sam się kończy)")
    a.add_argument("--sucho", action="store_true", help="wypisz dymki z telemetrii dnia --dzien, bez wysyłania")
    a.add_argument("--instancja", help="--sucho: tylko ta instancja (poza tym RETRONIC_ID)")
    a.add_argument("--dzien", help="--sucho: RRRRMMDD (domyślnie dziś)")
    o = a.parse_args(argv)
    katalog = os.environ.get("RETRONIC_POWIADOM_KATALOG") or instancja.KATALOG
    if o.sucho:
        dzien = o.dzien or time.strftime("%Y%m%d")
        if not re.fullmatch(r"\d{8}", dzien):
            a.error("--dzien: RRRRMMDD")
        sucho(str(katalog), o.instancja or os.environ.get("RETRONIC_ID") or None, dzien)
        return 0
    id_ = os.environ.get("RETRONIC_ID")
    if not id_:
        sys.exit("ustaw RETRONIC_ID (np. gebelish)")
    rt = instancja.runtime(f"/run/user/{os.getuid()}")
    if o.wlacz or o.wylacz:
        s = instancja.sciezki(id_, rt, katalog)
        ustaw_flage(s.stan / "profil.json", o.wlacz)
        print(f"powiadom_obcy: flaga {FLAGA} = {'true' if o.wlacz else 'false'} w instancje/{id_}/profil.json")
        if o.wlacz:
            print(uruchom(id_, katalog, rt))
        return 0
    if o.uruchom:
        print(uruchom(id_, katalog, rt))
        return 0
    s = instancja.sciezki(id_, rt, katalog)
    blokada = open(Path(rt) / f"retronic-powiadom-obcy-{id_}.lock", "w")
    try:
        fcntl.flock(blokada, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(f"powiadom_obcy {id_}: już działa (blokada)")
    if "DBUS_SESSION_BUS_ADDRESS" not in os.environ and Path(rt, "bus").exists():
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={rt}/bus"
    petla(s, nick_postaci(s.stan, id_), auto=os.environ.get("RETRONIC_POWIADOM_OBCY_AUTO") == "1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
