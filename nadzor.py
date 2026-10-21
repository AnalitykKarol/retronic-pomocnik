#!/usr/bin/env python3
"""Wykonawca nadzorcy zestawu (SPEC_nadzor_wykonawca_1021, F2 + biała lista napraw). Deterministyczny; model nie klika po grze.

  python3 -I nadzor.py cien [--raz]        jeden przebieg W CIENIU: tylko log "zrobiłbym X". --raz = tylko odczyt i wydruk, zero zapisów
  python3 -I nadzor.py tick                jeden przebieg (timer co ~1 min). Na żywo TYLKO gdy istnieje instancje/_wspolne/NADZOR_ZYWO
  python3 -I nadzor.py napraw <id> <rodzaj>   biała lista: restart | wznow | wroc | relog | wyloguj | zmien_spot
  python3 -I nadzor.py stan                skrót dla obchodu (JSON): fazy, zmiany, naprawy, ostatnie decyzje
  python3 -I nadzor.py odblokuj <id>       zdejmuje wstrzymanie po eskalacji (polecenie Karola, NIE dla modelu)

Cykl postaci: OFFLINE -> LOGOWANIE -> DOJSCIE -> EXP -> POWROT (WROC) -> MIASTO (serwis, jeśli miasto ma) -> WYLOGOWANIE -> OFFLINE.
Blokady (przed każdą akcją): instancje/<id>/STOP_RECZNY, instancje/_wspolne/NADZOR_PAUZA, "nadzor": false w profil.json,
wstrzymanie po eskalacji. Jedna akcja logowania/wylogowania naraz (flock + jedna na tick), odstęp od poprzedniego zdarzenia.
Każda decyzja i akcja: instancje/_wspolne/logi/nadzor-RRRRMMDD.jsonl. Restart bota: mapa/tryb z tryb.log, nie z env.
Wybór spotu (Q5, SPEC_wybor_spotu_1021): przy starcie zmiany i przy zmien_spot z tabeli dane_tibia/spoty_nadzorca.json (spoty.py): miasto z pozycji,
poziom, jeden bot na jaskinię, lina/łopata, mieszanie między zmianami. Cień (cien --raz) pokazuje "spot_podglad" dla każdej postaci w grze.
Nigdy: czat gry, pokrętła ryzyka śmierci, STOP_RECZNY, zakładanie kont, handel."""
import argparse
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True          # cień = zero zapisów (także __pycache__ importowanych modułów)
DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))
import grafik as G  # noqa: E402
import spoty as SP  # noqa: E402

KORZEN = Path(os.environ.get("RETRONIC_NADZOR_KORZEN") or DIR)
FMT = G.FMT
BIALA_LISTA = ("restart", "wznow", "wroc", "relog", "wyloguj", "zmien_spot")
FAZY = ("OFFLINE", "LOGOWANIE", "DOJSCIE", "EXP", "POWROT", "MIASTO", "WYLOGOWANIE")
ZDARZENIA_LOGOWANIA = ("sesja_start", "wyloguj", "relog")

# ---------- sygnały z logu bota ----------
RE_GODZ = re.compile(r"^(\d\d):(\d\d):(\d\d) (.*)$")
RE_PK = re.compile(r"ALARM: PK|\[PK\] .*atak|Czaszka: .* = (?!nieczytelne|brak|bez)")
RE_GM = re.compile(r"ALARM_GM|ALARM: gracz")
RE_ZGON = re.compile(r"MARTWY|Bot zginął|\[UCIECZKA\] HP 0%|niskie HP 0%")
RE_ROZL = re.compile(r"ROZŁĄCZENIE: pamięć gry")
RE_ROZL_KONIEC = re.compile(r"Rozłączenie zakończone")
RE_DEPO = re.compile(r"Wyprawa: DEPO osiągnięte")
RE_ALARM = re.compile(r"^ALARM: (?!niskie HP|PK|gracz)")
RE_STOP = re.compile(r"Zatrzymano \(plik STOP\)")
RE_PLECAK = re.compile(r"loot: pełny plecak(?: w walce)?: powód sloty_pelne")
RE_CAP = re.compile(r"loot: pełny plecak(?: w walce)?: powód za_ciezki")
RE_GLOD = re.compile(r"\[jedzenie: brak jedzenia w plecaku\]")
RE_MOZG = re.compile(r"Mózg: tryb \S+, postać \S+, trasa (\S+)")
RE_WALKA = re.compile(r"[Cc]el|WALKA|ATAK|Loot|loot|POGO|UCIEC")
RE_TRYB_MAPA = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) \[TRYB\] mapa (\S+?):")
RE_TRYB_TRYB = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) \[TRYB\] tryb (\S*?):")


def _kod(txt):
    """Kod wyjścia skryptu z tekstu wykonawcy ("kod 9: ...") albo None."""
    m = re.match(r"kod (\d+)", str(txt or ""))
    return int(m[1]) if m else None


def ts_ep(dt):
    return dt.timestamp()


def czytaj_log(plik, teraz, ile=4000):
    """Ostatnie linie logu bota jako [(epoch, tekst)]. Data z zegara (linia z przyszłości = wczoraj), linie bez godziny dziedziczą."""
    if not plik:
        return []
    try:
        with open(plik, encoding="utf-8", errors="replace") as f:
            surowe = f.readlines()[-ile:]
    except OSError:
        return []
    wynik, ost = [], None
    for l in surowe:
        l = l.rstrip("\n")
        m = RE_GODZ.match(l)
        if m:
            t = teraz.replace(hour=int(m[1]), minute=int(m[2]), second=int(m[3]), microsecond=0)
            if t > teraz + timedelta(seconds=90):
                t -= timedelta(days=1)
            ost = t.timestamp()
            wynik.append((ost, m[4]))
        elif ost is not None and l.strip():
            wynik.append((ost, l.strip()))
    return wynik


def najnowszy_log(katalog_logow):
    p = Path(katalog_logow)
    pliki = sorted(p.glob("mozg-stdout-*.log"), key=lambda x: x.stat().st_mtime) if p.is_dir() else []
    return pliki[-1] if pliki else None


def analizuj_log(linie, teraz_ep):
    """Sygnały z logu. Wartości *_ts to epoch ostatniego wystąpienia (None = brak)."""
    a = {"pk": None, "pk_tekst": None, "gm": None, "zgon": None, "rozl": None, "rozl_koniec": None, "depo": None, "alarm": None,
         "alarm_tekst": None, "stop": None, "start": None, "trasa": None, "ost_zabicie": None, "zabicia_od_startu": 0,
         "pelny": 0, "cap": 0, "glod": 0, "walka": False, "ost_linia": None}
    for t, l in linie:
        if "[OGIEN]" in l or l.startswith("debug:"):
            continue
        a["ost_linia"] = t
        if RE_MOZG.search(l):
            a["start"], a["trasa"], a["zabicia_od_startu"] = t, RE_MOZG.search(l)[1], 0
        if "zabity" in l:
            a["ost_zabicie"] = t
            a["zabicia_od_startu"] += 1
        if RE_PK.search(l):
            a["pk"], a["pk_tekst"] = t, l[:140]
        if RE_GM.search(l):
            a["gm"] = t
        if RE_ZGON.search(l):
            a["zgon"] = t
        if RE_ROZL.search(l):
            a["rozl"] = t
        if RE_ROZL_KONIEC.search(l):
            a["rozl_koniec"] = t
        if RE_DEPO.search(l):
            a["depo"] = t
        if RE_ALARM.search(l):
            a["alarm"], a["alarm_tekst"] = t, l[:140]
        if RE_STOP.search(l):
            a["stop"] = t
        if t >= teraz_ep - 600:
            a["pelny"] += bool(RE_PLECAK.search(l))
            a["cap"] += bool(RE_CAP.search(l))
        if t >= teraz_ep - 1200:
            a["glod"] += bool(RE_GLOD.search(l))
    # walka: któraś z linii z ostatnich 20 s
    a["walka"] = any(t >= teraz_ep - 20 and RE_WALKA.search(l) for t, l in linie[-40:])
    return a


# ---------- mapa i tryb: bieżące, nie z env ----------
def _norm_trasy(t):
    """mapy.json ma `patrol:troll`, a `Mózg:` drukuje `patrol(troll)`; porównujemy bez `:()` (nigdy po prefiksie: `patrol` to też Rook)."""
    return re.sub(r"[:()]", "", str(t or ""))


def mapa_tryb_biezace(korzen, id_, teraz=None):
    """(mapa, tryb) tego, co bot robi TERAZ: ostatni [TRYB] mapa/tryb w tryb.log, skorygowane o `Mózg: … trasa` z najnowszego
    mozg-stdout, gdy bot wystartował po wpisie (lekcja 21.10 15:36: nigdy ostatni_start.<id>.env). -> (mapa|None, tryb|None, skąd)."""
    kat = Path(korzen) / "instancje" / id_
    mapa = tryb = None
    t_mapa = None
    try:
        tekst = (kat / "logi" / "tryb.log").read_text(encoding="utf-8", errors="replace")[-300_000:]
    except OSError:
        tekst = ""
    for l in tekst.splitlines():
        m = RE_TRYB_MAPA.match(l)
        if m:
            t_mapa, mapa = m[1], m[2]
            tryb = None
            continue
        m = RE_TRYB_TRYB.match(l)
        if m and mapa is not None:
            tryb = ",".join(x for x in m[2].split("+") if x)
    skad = "tryb.log"
    try:
        mapy = json.loads((Path(korzen) / "mapy.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        mapy = {}
    log = najnowszy_log(kat / "logi")
    trasa = None
    t_mozg = None
    if log:
        for t, l in czytaj_log(log, teraz or datetime.now(), 20000)[::-1]:
            m = RE_MOZG.search(l)
            if m:
                trasa, t_mozg = m[1], t
                break
    if trasa and mapy:
        trasa_log = (mapy.get(mapa) or {}).get("trasa") if mapa else None
        t_mapa_ep = datetime.strptime(t_mapa, "%Y-%m-%d %H:%M:%S").timestamp() if t_mapa else 0
        niespojne = trasa_log is None or _norm_trasy(trasa) != _norm_trasy(trasa_log)
        if niespojne and t_mozg is not None and t_mozg >= t_mapa_ep - 60:
            kandydaci = [k for k, v in mapy.items() if not k.startswith("_") and isinstance(v, dict)
                         and _norm_trasy(v.get("trasa")) == _norm_trasy(trasa)]
            if kandydaci:
                mapa = mapa if mapa in kandydaci else kandydaci[0]
                skad = "mozg-stdout (trasa)"
    return mapa, tryb, skad


# ---------- źródła (żywe) ----------
class Zrodla:
    """Wszystko, co wykonawca czyta spoza plików stanu. Podmieniane w testach."""

    def __init__(self, korzen):
        self.korzen = Path(korzen)
        self._ip = {}
        self._ekw = {}

    def stan(self):
        r = subprocess.run([sys.executable, "-I", str(DIR / "okno_api.py"), "stan"], cwd=str(DIR), capture_output=True,
                           text=True, timeout=60)
        return json.loads(r.stdout).get("instancje", [])

    def ekran(self, id_):
        """K1: `logowanie.py stan-ekranu <id>` -> gra | logowanie | lista | smierc | None (brak narzędzia / nieczytelne)."""
        p = DIR / "logowanie.py"
        if not p.exists():
            return None
        try:
            r = subprocess.run([sys.executable, "-I", str(p), "stan-ekranu", id_], cwd=str(DIR), capture_output=True, text=True,
                               timeout=30, env=dict(os.environ, RETRONIC_ID=id_), stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            return None
        txt = (r.stdout or "").strip()
        try:
            d = json.loads(txt)
            txt = str(d.get("ekran") or d.get("stan") or "") if isinstance(d, dict) else txt
        except ValueError:
            pass
        txt = txt.lower()
        for klucz, wartosc in (("smier", "smierc"), ("zgon", "smierc"), ("lista", "lista"), ("character", "lista"),
                               ("enter", "logowanie"), ("logowan", "logowanie"), ("gra", "gra"), ("game", "gra")):
            if klucz in txt:
                return wartosc
        return None

    def ip_zgodne(self, id_):
        t, w = self._ip.get(id_, (0, None))
        if time.time() - t < 600:
            return w
        try:
            r = subprocess.run([sys.executable, "-I", str(DIR / "okno_api.py"), "sesja", "--instancja", id_], cwd=str(DIR),
                               capture_output=True, text=True, timeout=30)
            w = (json.loads(r.stdout).get("ip") or {}).get("zgodne")
        except (OSError, ValueError, subprocess.SubprocessError):
            w = None
        self._ip[id_] = (time.time(), w)
        return w

    def ekwipunek(self, id_):
        """{"lina": True|False|None, "lopata": ...} z odczytu pamięci gry (spoty.py ekwipunek, RETRONIC_ID=<id>; tylko odczyt). Pamięć podręczna 2 min."""
        t, w = self._ekw.get(id_, (0, None))
        if w is not None and time.time() - t < 120:
            return w
        try:
            r = subprocess.run([sys.executable, "-I", str(DIR / "spoty.py"), "ekwipunek"], cwd=str(DIR), capture_output=True, text=True,
                               timeout=30, env=dict(os.environ, RETRONIC_ID=id_), stdin=subprocess.DEVNULL)
            w = json.loads((r.stdout or "").strip().splitlines()[-1])
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            w = {"lina": None, "lopata": None}
        self._ekw[id_] = (time.time(), w)
        return w

    def telemetria(self, id_):
        import nadzor_stan  # noqa: PLC0415
        return nadzor_stan.przejrzyj_telemetrie(self.korzen / "instancje" / id_ / "logi", time.time())

    def procesy_serwisu(self, id_):
        import instancja  # noqa: PLC0415
        return instancja.procesy(r"(^|[ /])serwis\.py ", id_=id_)

    def procesy_bota(self, id_):
        import instancja  # noqa: PLC0415
        return instancja.procesy(r"(mozg|cavebot)\.py", id_=id_)


# ---------- wykonawcy akcji ----------
class WykonawcaCien:
    """Nic nie uruchamia. Zapamiętuje wywołania (do testów)."""
    zywy = False

    def __init__(self):
        self.wywolania = []

    def _w(self, nazwa, *a):
        self.wywolania.append((nazwa,) + a)
        return True, f"cień: {nazwa} nie wykonano"

    def sesja_start(self, id_): return self._w("sesja_start", id_)
    def zaloguj(self, id_): return self._w("zaloguj", id_)
    def start_bota(self, id_, mapa, tryb): return self._w("start_bota", id_, mapa, tryb)
    def zatrzymaj_bota(self, id_): return self._w("zatrzymaj_bota", id_)
    def wroc(self, id_): return self._w("wroc", id_)
    def serwis(self, id_): return self._w("serwis", id_)
    def wyloguj(self, id_): return self._w("wyloguj", id_)
    def powiadom(self, id_, tytul, tresc): return self._w("powiadom", id_, tytul, tresc)


class WykonawcaZywy:
    """Uruchamia istniejące skrypty przez interfejs poleceń. Brak narzędzia = (False, "brak ..."), nigdy wyjątek."""
    zywy = True

    def __init__(self, korzen):
        self.korzen = Path(korzen)

    def _env(self, id_):
        e = dict(os.environ)
        e["RETRONIC_ID"] = id_
        return e

    def _uruchom(self, argv, id_, limit, odlacz=False):
        try:
            if odlacz:
                subprocess.Popen([str(a) for a in argv], cwd=str(DIR), env=self._env(id_), stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                return True, "uruchomiono w tle"
            r = subprocess.run([str(a) for a in argv], cwd=str(DIR), env=self._env(id_), capture_output=True, text=True,
                               timeout=limit, stdin=subprocess.DEVNULL)
            wyj = " | ".join((r.stdout + r.stderr).strip().splitlines()[-3:])
            return r.returncode == 0, f"kod {r.returncode}: {wyj}"[:300]
        except subprocess.TimeoutExpired:
            return False, f"przekroczony limit {limit} s"
        except OSError as e:
            return False, str(e)

    def _skrypt(self, nazwa, id_, limit, argv_dod=(), odlacz=False):
        p = DIR / nazwa
        if not p.exists():
            return False, f"brak narzędzia {nazwa}"
        return self._uruchom([p, *argv_dod], id_, limit, odlacz)

    def sesja_start(self, id_):
        return self._uruchom([sys.executable, "-I", DIR / "sesja_gry.py", "start"], id_, 120)

    def zaloguj(self, id_):
        return self._skrypt("zaloguj.sh", id_, 120)

    def start_bota(self, id_, mapa, tryb):
        if not mapa:
            return False, "nieznana bieżąca mapa (brak [TRYB] w tryb.log)"
        return self._skrypt("uruchom_instancje.sh", id_, 60, [id_, mapa, tryb or ""])

    def zatrzymaj_bota(self, id_):
        """Miękkie zatrzymanie BEZ STOP_RECZNY (zatrzymaj.sh go tworzy): plik STOP, potem TERM, potem KILL; puszcza strzałki."""
        import instancja  # noqa: PLC0415
        stan = self.korzen / "instancje" / id_
        (stan / "STOP").touch()
        wzor = r"(mozg|cavebot)\.py"

        def czekaj(s):
            koniec = time.time() + s
            while time.time() < koniec:
                if not instancja.procesy(wzor, id_=id_):
                    return True
                time.sleep(0.3)
            return False

        wynik = "zatrzymany (STOP)"
        if not czekaj(10):
            for p in instancja.procesy(wzor, id_=id_):
                os.kill(p, signal.SIGTERM)
            wynik = "zatrzymany (TERM)"
            if not czekaj(4):
                for p in instancja.procesy(wzor, id_=id_):
                    os.kill(p, signal.SIGKILL)
                wynik = "zatrzymany (KILL)"
        self._uruchom([sys.executable, "-I", "-c",
                       f"import sys; sys.path.insert(0, {str(DIR)!r}); import bot, klawisz_x11; "
                       "klawisz_x11.puszczaj_wszystkie_strzalki(bot.ekran_gry())"], id_, 8)
        return True, wynik

    def wroc(self, id_):
        return self._skrypt("wroc.sh", id_, 20)

    def serwis(self, id_):
        kod = G.wspolne(self.korzen) / f"nadzor_serwis_{id_}.kod"
        kod.unlink(missing_ok=True)
        if not (DIR / "serwis.sh").exists():
            return False, "brak narzędzia serwis.sh"
        return self._uruchom(["bash", "-c", f"{DIR / 'serwis.sh'}; echo $? > {kod}"], id_, 0, odlacz=True)

    def wyloguj(self, id_):
        """wyloguj.sh (K1) sam zamyka sesję po wylogowaniu (`sesja_gry.py zamknij`), więc nie wołamy tego drugi raz.
        Kody: 0 ok, 4 ręczna gra, 5 brak spokoju, 6 zgon, 7 ekran nierozpoznany, 8 bot poza miastem."""
        return self._skrypt("wyloguj.sh", id_, 330)

    def powiadom(self, id_, tytul, tresc):
        try:
            import powiadom  # noqa: PLC0415
            poszlo = powiadom.powiadom(tytul, tresc, "critical", klucz=f"nadzor-{id_}-{tytul}")
            return bool(poszlo), "powiadomienie wysłane" if poszlo else "powiadomienie wyciszone (plik cisza / limit)"
        except Exception as e:      # noqa: BLE001
            return False, f"powiadomienie: {e!r}"


# ---------- dziennik ----------
class Dziennik:
    def __init__(self, korzen, zapis=True):
        self.dir = G.wspolne(korzen) / "logi"
        self.zapis = zapis
        self.ostatnie = []

    def pisz(self, teraz, tryb, **pola):
        rek = {"t": teraz.strftime("%Y-%m-%d %H:%M:%S"), "tryb": tryb, **pola}
        self.ostatnie.append(rek)
        if self.zapis:
            self.dir.mkdir(parents=True, exist_ok=True)
            with open(self.dir / f"nadzor-{teraz:%Y%m%d}.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(rek, ensure_ascii=False) + "\n")
        return rek


def D(id_, akcja, powod, kod=None, klasa="info", **arg):
    return {"id": id_, "akcja": akcja, "powod": powod, "kod": kod or akcja, "klasa": klasa, "arg": arg}


# ---------- nadzorca ----------
class Nadzorca:
    def __init__(self, korzen=None, zegar=None, zrodla=None, wykonawca=None, zywo=False, zapis=True, czysty=None):
        self.korzen = Path(korzen or KORZEN)
        self.zegar = zegar or (lambda: datetime.now().replace(microsecond=0))
        self.zrodla = zrodla or Zrodla(self.korzen)
        self.zywo = self.zywo_zadane = zywo
        self.wykonawca = wykonawca or (WykonawcaZywy(self.korzen) if zywo else WykonawcaCien())
        self.zapis = zapis
        self.W = G.wspolne(self.korzen)
        self.dziennik = Dziennik(self.korzen, zapis)
        self.konf = G.wczytaj_konfig(self.korzen)
        self.stan = self._wczytaj_stan(tylko_odczyt=(not zapis) if czysty is None else czysty)
        self.raport = []            # decyzje bieżącego przebiegu (do wydruku)
        self._tab = None            # tabela spotów (spoty.wczytaj), ładowana leniwie raz na przebieg
        self._tab_ladowana = False
        self._przypisane = {}       # id -> mapa przypisana w tym przebiegu (zajętość zanim bot ruszy)
        self._obs = {}              # id -> obserwacja z tego przebiegu (podgląd spotów w cieniu)
        self._ostrzezono_tabele = False

    # --- stan trwały ---
    def _wczytaj_stan(self, tylko_odczyt=False):
        try:
            s = json.loads((self.W / "nadzor_stan.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            s = {}
        if tylko_odczyt:
            s = {}                      # --raz: świeży stan, nic nie wpływa na wynik poza rzeczywistością
        s.setdefault("globalne", {})
        s.setdefault("postacie", {})
        s.setdefault("cien", {})
        s.setdefault("minuty", {})
        return s

    def zapisz_stan(self, teraz):
        if not self.zapis:
            return
        self.stan["cien"] = {k: v for k, v in self.stan["cien"].items() if ts_ep(teraz) - v < 2 * 86400}
        self.stan["czas"] = teraz.strftime(FMT)
        self.stan["tryb"] = "zywo" if self.zywo else "cien"
        self.W.mkdir(parents=True, exist_ok=True)
        tmp = self.W / "nadzor_stan.json.tmp"
        tmp.write_text(json.dumps(self.stan, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.W / "nadzor_stan.json")

    def post(self, id_):
        return self.stan["postacie"].setdefault(id_, {"faza": "OFFLINE"})

    # --- powiadomienia ---
    def powiadomienia_wylaczone(self):
        """Powód, dla którego powiadom.py nic nie wyśle (eskalacje niewidoczne dla Karola), albo None. Te same wyłączniki co powiadom.py."""
        if os.environ.get("RETRONIC_POWIADOMIENIA", "").strip() == "0":
            return "RETRONIC_POWIADOMIENIA=0"
        if (self.korzen / "cisza").exists():
            return "plik cisza"
        return None

    def _ponow_powiadomienie(self, teraz, id_):
        """Hold bez dostarczonego powiadomienia: gdy powiadomienia znów działają, wyślij je jeszcze raz (raz na przebieg)."""
        h = self.post(id_).get("hold")
        if not (self.zywo and h and h.get("powiadomiono") is False) or self.powiadomienia_wylaczone():
            return
        ok, txt = self.wykonawca.powiadom(id_, f"Nadzór Retronic [{id_}]", f"{id_}: {h.get('powod')} (powtórzone: pierwsze powiadomienie nie dotarło)")
        h["powiadomiono"] = bool(ok)
        self.raport.append(self.dziennik.pisz(teraz, "zywo", id=id_, akcja="eskaluj", wynik="powiadomiono" if ok else "powiadomienie nieudane",
                                              powod="ponowienie powiadomienia dla wstrzymanej postaci", szczegol=txt))

    # --- pliki i bramki ---
    def kat(self, id_):
        return self.korzen / "instancje" / id_

    def profil(self, id_):
        try:
            return json.loads((self.kat(id_) / "profil.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def bramka(self, id_, czy_hold=True):
        """Powód odmowy wszelkiej akcji dla postaci albo None. Kolejność: pauza, nadzor:false, STOP_RECZNY, wstrzymanie."""
        if (self.W / "NADZOR_PAUZA").exists():
            return "NADZOR_PAUZA: zero akcji"
        if self.profil(id_).get("nadzor") is False or (self.konf.get("postacie", {}).get(id_) or {}).get("nadzor") is False:
            return "postać poza nadzorem (nadzor: false)"
        if (self.kat(id_) / "STOP_RECZNY").exists():
            return "STOP_RECZNY: Karol gra, zero akcji dla tej postaci"
        h = self.post(id_).get("hold")
        if czy_hold and h:
            bez = " [POWIADOMIENIE NIE DOTARŁO do Karola]" if h.get("powiadomiono") is False else ""
            return f"wstrzymana po eskalacji ({h.get('powod')}){bez}; odblokuj: nadzor.py odblokuj {id_}"
        return None

    # --- obserwacja ---
    def obserwuj(self, id_, raw, teraz):
        k = self.kat(id_)
        raw = raw or {}
        o = {"id": id_, "sesja": bool(raw.get("sesja")), "gra": bool(raw.get("gra")), "bot": bool(raw.get("bot")),
             "gracz": raw.get("gracz"), "panel": raw.get("panel") or {}, "nick": raw.get("nick"),
             "stop": (k / "STOP").exists(), "stop_reczny": (k / "STOP_RECZNY").exists(), "wroc": (k / "WROC").exists()}
        o["online"] = o["sesja"] or o["gra"]
        try:
            ws = json.loads((k / "wyprawa_stan.json").read_text(encoding="utf-8"))
            o["wyprawa"] = bool(ws.get("aktywna"))
        except (OSError, ValueError):
            o["wyprawa"] = False
        o["log"] = analizuj_log(czytaj_log(najnowszy_log(k / "logi"), teraz), ts_ep(teraz)) if o["online"] else None
        o["tele"] = {}
        if o["online"] and o["bot"]:
            try:
                o["tele"] = self.zrodla.telemetria(id_) or {}
            except Exception:       # noqa: BLE001
                o["tele"] = {}
        w_grze = o["gracz"] is not None
        o["ekran"] = None
        if o["online"] and not w_grze:
            try:
                o["ekran"] = self.zrodla.ekran(id_)
            except Exception:       # noqa: BLE001
                o["ekran"] = None
            w_grze = o["ekran"] == "gra"
        elif o["online"]:
            o["ekran"] = "gra"
        o["w_grze"] = w_grze
        o["serwis_dziala"] = False
        if o["online"] and not o["bot"]:
            try:
                o["serwis_dziala"] = bool(o["panel"].get("serwis_dziala")) or bool(self.zrodla.procesy_serwisu(id_))
            except Exception:       # noqa: BLE001
                o["serwis_dziala"] = bool(o["panel"].get("serwis_dziala"))
        o["ip_zgodne"] = None
        if o["online"]:
            try:
                o["ip_zgodne"] = self.zrodla.ip_zgodne(id_)
            except Exception:       # noqa: BLE001
                o["ip_zgodne"] = None
        return o

    # --- liczniki ---
    def naprawy_w_oknie(self, id_, teraz):
        okno = float(self.konf["napraw_okno_min"]) * 60
        st = self.post(id_)
        st["naprawy"] = [x for x in st.get("naprawy", []) if ts_ep(teraz) - x[0] <= okno]
        return st["naprawy"]

    def minuty_dzis(self, id_, teraz, online):
        doba = G.doba_dla(teraz, self.konf).strftime("%Y%m%d")
        m = float(self.stan["minuty"].get(doba, {}).get(id_, 0))
        st = self.post(id_)
        if online and st.get("login_ts"):
            m += (ts_ep(teraz) - st["login_ts"]) / 60
        return m

    def licz_wylogowanie(self, id_, teraz):
        st = self.post(id_)
        if st.get("login_ts"):
            doba = G.doba_dla(datetime.fromtimestamp(st["login_ts"]), self.konf).strftime("%Y%m%d")
            self.stan["minuty"].setdefault(doba, {})
            self.stan["minuty"][doba][id_] = round(self.stan["minuty"][doba].get(id_, 0) + (ts_ep(teraz) - st["login_ts"]) / 60, 1)
        st["login_ts"] = None

    def odstep_ok(self, teraz):
        """(ok, powód): odstęp od ostatniego zdarzenia logowania/wylogowania (naszego, cienia lub zewnętrznego)."""
        t = self.stan["globalne"].get("ostatnie_zdarzenie")
        gap = int(self.konf["odstep_min"][0]) * 60
        if t is not None and ts_ep(teraz) - t < gap:
            kiedy = datetime.fromtimestamp(t + gap).strftime("%H:%M")
            return False, f"odstęp od poprzedniego logowania/wylogowania < {self.konf['odstep_min'][0]} min (wolne od {kiedy})"
        return True, ""

    # --- reguły ---
    def zmiana_postaci(self, plan, id_, teraz, online):
        st = self.post(id_)
        if online and st.get("zmiana_od"):
            for z in G.zmiany_postaci(plan, id_):
                if z["od"] == st["zmiana_od"]:
                    return z
        if online:
            z = G.aktywna_zmiana(plan, id_, teraz, luz_min=int(self.konf["przerwa_min"][0]))
            if z:
                st["zmiana_od"] = z["od"]
            return z
        return G.aktywna_zmiana(plan, id_, teraz)

    def koniec_zmiany(self, id_, o, zm, teraz):
        """Powód końca zmiany albo None: czas z grafiku, limit dzienny, pełny plecak, brak capu, brak jedzenia."""
        if zm is not None and teraz >= datetime.strptime(zm["koniec"], FMT):
            return "czas", f"koniec zmiany z grafiku ({zm['koniec'][11:]})"
        limit = float(self.konf["limit_dzienny_min"]) - float(self.konf["miasto_min"])
        if self.minuty_dzis(id_, teraz, True) >= limit:
            return "limit", "limit dzienny gry wyczerpany"
        a = o["log"] or {}
        if a.get("pelny", 0) >= 3:
            return "plecak", f"pełny plecak ({a['pelny']} wpisów w 10 min)"
        if a.get("cap", 0) >= 3:
            return "cap", f"brak capu ({a['cap']} wpisów w 10 min)"
        if a.get("glod", 0) >= 2:
            return "jedzenie", f"brak jedzenia w plecaku ({a['glod']} wpisów w 20 min)"
        return None

    # --- wybór spotu (Q5, SPEC_wybor_spotu_1021) ---
    def tabela_spotow(self):
        """Tabela spotów (spoty.py) albo None, gdy nie ma pliku dane_tibia/spoty_nadzorca.json (wtedy zachowanie jak przed Q5). Raz na przebieg."""
        if not self._tab_ladowana:
            self._tab_ladowana = True
            plik = self.korzen / "dane_tibia" / "spoty_nadzorca.json"
            self._tab = SP.wczytaj(self.korzen) if plik.exists() else None
        return self._tab

    def fakty_postaci(self, id_, panel, gracz):
        """Pozycja (z gry: panel.pozycja z okno_api stan) i poziom postaci dla spoty.wybierz; ekwipunek leniwie (odczyt tylko na żądanie)."""
        poz = (panel or {}).get("pozycja")
        poz = tuple(int(v) for v in poz[:3]) if isinstance(poz, (list, tuple)) and len(poz) >= 3 else None
        poziom = (gracz or {}).get("level") if isinstance(gracz, dict) else None
        poziom = poziom if isinstance(poziom, int) and not isinstance(poziom, bool) else (panel or {}).get("level")
        fn = getattr(self.zrodla, "ekwipunek", None)
        return {"id": id_, "poz": poz, "poziom": poziom if isinstance(poziom, int) else None,
                "ekwipunek": (lambda: fn(id_)) if fn else None}

    def mapy_zajete(self, id_, teraz):
        """{inna postać: {mapy}} BIEŻĄCYCH map innych botów (tryb.log + `Mózg: … trasa`, nie ostatni_start.env), plus spot zapisany w stanie
        nadzorcy dla postaci online (bot jeszcze nie widoczny w tryb.log) i przypisany w tym przebiegu. Przy rozbieżności źródeł liczą się oba."""
        zaj = {}
        for inny, raw in getattr(self, "_raw", {}).items():
            if inny == id_:
                continue
            mapy = set()
            if raw.get("bot"):
                try:
                    mapy.add(mapa_tryb_biezace(self.korzen, inny, teraz)[0])
                except Exception:       # noqa: BLE001
                    pass
            if raw.get("sesja") or raw.get("gra"):
                mapy.add(((self.stan["postacie"].get(inny) or {}).get("spot") or {}).get("mapa"))
            mapy.discard(None)
            if mapy:
                zaj[inny] = mapy
        for inny, mapa in self._przypisane.items():
            if inny != id_:
                zaj.setdefault(inny, set()).add(mapa)
        return zaj

    def historia_spotow(self, id_, biezaca):
        h = [x.get("mapa") for x in self.post(id_).get("spoty_hist", []) if x.get("mapa")][-3:]
        return h + ([biezaca] if biezaca else [])

    def wybierz_spot(self, id_, panel, gracz, teraz, biezaca, przyczyna, dodatkowo_zajete=(), zajete=None, z_depo=False):
        """spoty.wybierz z faktami tej postaci. -> wynik wybierz() albo None, gdy tabeli brak. Ziarno: dzień + przyczyna (początek zmiany / zmien_spot).
        zajete (zbiór map) zastępuje bieżące mapy innych botów (podgląd w cieniu); z_depo=True liczy start z z7 (postać zaczynałaby od depo)."""
        tab = self.tabela_spotow()
        if tab is None:
            return None
        zaj = (set(zajete) if zajete is not None else set().union(*self.mapy_zajete(id_, teraz).values())) | set(m for m in dodatkowo_zajete if m)
        fakty = self.fakty_postaci(id_, panel, gracz)
        if z_depo and fakty["poz"]:
            fakty["poz"] = (fakty["poz"][0], fakty["poz"][1], SP.LEKKIE_Z)
        return SP.wybierz(fakty, zaj, self.historia_spotow(id_, biezaca), tab, ziarno=f"{teraz:%Y-%m-%d}|{przyczyna}")

    def zapamietaj_spot(self, id_, st, mapa, teraz, historia=True):
        tab = self.tabela_spotow()
        jask = tab.jaskinia_mapy(mapa) if tab is not None else mapa
        st["spot"] = {"mapa": mapa, "jaskinia": jask, "od": ts_ep(teraz)}
        if historia:
            st["spoty_hist"] = (st.get("spoty_hist", []) + [{"mapa": mapa, "jaskinia": jask, "od": teraz.strftime(FMT)}])[-10:]

    def spot_zapasowy(self, id_, biezaca, zajete):
        lista = self.profil(id_).get("spoty_zapasowe") or []
        spoty = [(x, None) if isinstance(x, str) else (x.get("mapa"), x.get("tryb")) for x in lista if x]
        spoty = [s for s in spoty if s[0]]
        if not spoty:
            return None
        nazwy = [s[0] for s in spoty]
        start = (nazwy.index(biezaca) + 1) if biezaca in nazwy else 0
        for i in range(len(spoty)):
            s = spoty[(start + i) % len(spoty)]
            if s[0] != biezaca and s[0] not in zajete:
                return s
        for i in range(len(spoty)):
            s = spoty[(start + i) % len(spoty)]
            if s[0] != biezaca:
                return s
        return None

    def drabina(self, id_, teraz, problem, o):
        """Kolejny szczebel napraw dla zacięcia (okno napraw_okno_min): restart/wznow, to samo, zmiana spotu (jeśli jest zapasowy),
        WROC i koniec zmiany, potem eskalacja. Nie zmienia stanu (cień pokazuje zawsze bieżący szczebel)."""
        pierwszy = "wznow" if problem == "alarm" else "restart"
        mapa = mapa_tryb_biezace(self.korzen, id_, teraz)[0]
        szczeble = [pierwszy, pierwszy]
        if self.spot_zapasowy(id_, mapa, self._zajete_mapy(id_)) or self._alternatywa_spotu(id_, o, mapa, teraz):
            szczeble.append("zmien_spot")
        if o.get("bot"):
            szczeble.append("wroc")         # WROC wymaga żywego bota; przy martwym ostatni szczebel to eskalacja
        ost = self.naprawy_w_oknie(id_, teraz)
        n = len(ost)
        if ost and ts_ep(teraz) - ost[-1][0] < 180:
            return D(id_, "czekaj", f"poprzednia naprawa ({ost[-1][1]}) < 3 min temu, czekam na efekt", f"naprawa-czeka-{problem}")
        if n < len(szczeble):
            r = szczeble[n]
            return D(id_, r, f"naprawa {n + 1}/{len(szczeble)} ({problem})", f"napraw-{problem}-{r}", klasa="naprawa", problem=problem)
        return D(id_, "eskaluj", f"wyczerpana rotacja napraw ({problem}, {n} prób w {self.konf['napraw_okno_min']} min)",
                 "wyczerpana", klasa="eskalacja", kod_eskalacji="wyczerpana")

    def _alternatywa_spotu(self, id_, o, biezaca, teraz):
        """Czy tabela spotów ma dla tej postaci inny spot niż bieżący (bez profil.spoty_zapasowe)? Nie zapisuje stanu."""
        if self.profil(id_).get("spoty_zapasowe"):
            return False
        try:
            w = self.wybierz_spot(id_, o.get("panel"), o.get("gracz"), teraz, biezaca, "alternatywa", dodatkowo_zajete=(biezaca,))
        except Exception:       # noqa: BLE001
            return False
        return bool(w and w.get("mapa"))

    def _zajete_mapy(self, id_):
        """Mapy zajęte przez inne boty: BIEŻĄCE (tryb.log), nie `raw["mapa"]` (to ostatni_start.env, lekcja 21.10 15:36)."""
        return set().union(*self.mapy_zajete(id_, self.zegar()).values())

    def eskalacje_z_logu(self, id_, o, teraz):
        """Nowe zdarzenia wymagające Karola: PK/atak, zgon, GM/'bot?', IP niezgodne, ekran śmierci."""
        a, st, wynik = o["log"] or {}, self.post(id_), []
        wiek = float(self.konf.get("zdarzenie_wiek_min", 30)) * 60
        widziane = st.setdefault("eskalowane", {})
        for kod, t, opis in (("pk", a.get("pk"), f"PK / atak gracza: {a.get('pk_tekst')}"), ("gm", a.get("gm"), "GM albo pytanie 'bot?' (ALARM_GM)"),
                             ("zgon", a.get("zgon"), "możliwy zgon postaci (HP 0% / MARTWY)")):
            if t and ts_ep(teraz) - t <= wiek and t > widziane.get(kod, 0):
                wynik.append(D(id_, "eskaluj", opis, kod, klasa="eskalacja", kod_eskalacji=kod, zdarzenie_ts=t))
        if o["ekran"] == "smierc":
            wynik.append(D(id_, "eskaluj", "ekran śmierci postaci", "zgon-ekran", klasa="eskalacja", kod_eskalacji="zgon"))
        if o["ip_zgodne"] is False:
            wynik.append(D(id_, "eskaluj", "IP proxy niezgodne z profilem", "ip", klasa="eskalacja", kod_eskalacji="ip"))
        return wynik

    def decyduj(self, id_, o, plan, teraz):
        """Zwraca listę decyzji dla postaci (zwykle jedna). Bramki sprawdzone wcześniej."""
        st = self.post(id_)
        konf = self.konf
        zm = self.zmiana_postaci(plan, id_, teraz, o["online"])
        cisza = not (G.hm(konf["cisza_do"]) <= teraz.hour * 60 + teraz.minute or teraz.hour * 60 + teraz.minute < G.hm(konf["cisza_od"]))
        # ---------- offline ----------
        if not o["online"]:
            if st.get("faza") != "OFFLINE":
                self.licz_wylogowanie(id_, teraz)
                st["faza"] = "OFFLINE"
                st["ostatnie_wylog"] = ts_ep(teraz)
                st["zmiana_od"] = None
                st["bot_start"] = None
                st["koniec"] = None
                st["spot"] = None
            if zm is None:
                return [D(id_, "czekaj", "offline, brak zmiany w grafiku w tej chwili", "offline")]
            if cisza:
                return [D(id_, "czekaj", "cisza nocna: zero logowań", "cisza")]
            if zm["od"] in st.get("wykonane", []) or zm["od"] in st.get("zakonczone", []):
                return [D(id_, "czekaj", f"zmiana {zm['od'][11:]} już odbyta", f"odbyta-{zm['od']}")]
            if st.get("start_bl", 0) >= 3:
                return [D(id_, "eskaluj", "start sesji nieudany 3 razy z rzędu", "start-nieudany", klasa="eskalacja", kod_eskalacji="wyczerpana")]
            if teraz < datetime.strptime(zm["od"], FMT):
                return [D(id_, "czekaj", f"zmiana o {zm['od'][11:]}", f"przed-{zm['od']}")]
            if (datetime.strptime(zm["koniec"], FMT) - teraz).total_seconds() < 30 * 60:
                return [D(id_, "czekaj", f"zmiana {zm['od'][11:]}-{zm['koniec'][11:]} przepadła (zostało < 30 min huntu)", f"przepadla-{zm['od']}")]
            if st.get("ostatnie_wylog") and ts_ep(teraz) - st["ostatnie_wylog"] < int(konf["przerwa_min"][0]) * 60:
                return [D(id_, "czekaj", f"przerwa po wylogowaniu < {konf['przerwa_min'][0]} min", "przerwa")]
            reszta = (datetime.strptime(zm["wylog"], FMT) - teraz).total_seconds() / 60
            if self.minuty_dzis(id_, teraz, False) + reszta > float(konf["limit_dzienny_min"]):
                return [D(id_, "czekaj", "limit dzienny gry nie pozwala na tę zmianę", "limit")]
            return [D(id_, "sesja_start", f"zmiana {zm['od'][11:]}-{zm['koniec'][11:]} z grafiku (start sesji, potem logowanie i bot)",
                      "start-" + zm["od"], klasa="zdarzenie", zmiana_od=zm["od"])]
        # ---------- online ----------
        if not st.get("login_ts"):
            st["login_ts"] = ts_ep(teraz)
            st["faza"] = st["faza"] if st.get("faza") not in (None, "OFFLINE") else "LOGOWANIE"
        if o["bot"]:
            st["bot_widziany"] = ts_ep(teraz)
        wyn = self.eskalacje_z_logu(id_, o, teraz)
        if wyn:
            return wyn
        a = o["log"] or {}
        if zm is not None and zm["od"] in st.get("zakonczone", []):
            if ts_ep(teraz) - st.get("ostatnie_wylog", 0) > 300:
                return [D(id_, "eskaluj", "po wylogowaniu sesja nadal działa > 5 min", "sesja-po-wylogowaniu", klasa="eskalacja",
                          kod_eskalacji="wyczerpana")]
            return [D(id_, "czekaj", "po wylogowaniu: sesja jeszcze wygasa", "po-wylogowaniu")]
        if not o["w_grze"]:
            return [self._poza_gra(id_, o, a, st, teraz, zm)]
        st.pop("nieustalony_od", None)
        if st.get("faza") in ("OFFLINE", "LOGOWANIE", None):
            st["faza"] = "DOJSCIE"
        st["logowanie_nasze"] = False
        if zm is None:
            return [D(id_, "czekaj", "online poza grafikiem: nie ruszam (do przyjęcia: grafik.py nowy --od-teraz)", "poza-grafikiem")]
        # POWROT w toku
        if o["wroc"] or o["wyprawa"]:
            st["faza"] = "POWROT"
            st.setdefault("powrot_od", ts_ep(teraz))
            if ts_ep(teraz) - st["powrot_od"] > 40 * 60:
                return [D(id_, "eskaluj", "powrót do miasta trwa > 40 min", "powrot-dlugo", klasa="eskalacja", kod_eskalacji="wyczerpana")]
            return [D(id_, "czekaj", "powrót do miasta (WROC) w toku", "powrot")]
        if not o["bot"]:
            return [self._bez_bota(id_, o, a, st, teraz, zm)]
        # bot działa
        if st.get("faza") in ("MIASTO", "WYLOGOWANIE", "POWROT"):
            st["faza"] = "EXP"
        if st.get("faza") == "DOJSCIE" and (a.get("zabicia_od_startu", 0) > 0 or ts_ep(teraz) - (st.get("bot_start") or 0) > 900):
            st["faza"] = "EXP"
        koniec = self.koniec_zmiany(id_, o, zm, teraz)
        if koniec:
            st["koniec"] = koniec[0]
            return [D(id_, "wroc", koniec[1] + ": zlecam powrót do miasta", "koniec-" + koniec[0], klasa="naprawa", problem="koniec")]
        zaciecie = self.zaciecie(id_, o, a, st, teraz)
        if zaciecie:
            if o["log"] and a.get("walka"):
                return [D(id_, "czekaj", f"{zaciecie}, ale bot w walce: odkładam restart", "walka-odroczenie")]
            return [self.drabina(id_, teraz, "zaciecie", o)]
        return [D(id_, "czekaj", f"{st.get('faza', 'EXP')}: bot działa, bez uwag", "ok")]

    def zaciecie(self, id_, o, a, st, teraz):
        t = o.get("tele") or {}
        if (t.get("wiek_probki_s") or 0) > 120:
            return f"telemetria stara ({t['wiek_probki_s']} s): bot zawieszony"
        if (t.get("stoi_poza_walka_s") or 0) > float(self.konf["stoi_min"]) * 60:
            return f"stoi w miejscu {t['stoi_poza_walka_s']} s poza walką"
        start = st.get("bot_start") or a.get("start")
        if start and st.get("faza") == "EXP" and ts_ep(teraz) - start > float(self.konf["brak_zabic_min"]) * 60:
            ost = max(a.get("ost_zabicie") or 0, start)
            if ts_ep(teraz) - ost > float(self.konf["brak_zabic_min"]) * 60:
                return f"brak zabić od {round((ts_ep(teraz) - ost) / 60)} min"
        return None

    def _poza_gra(self, id_, o, a, st, teraz, zm):
        """Sesja jest, ale klient nie jest w grze: logowanie w toku, rozłączenie albo stan nieustalony."""
        rozl = bool(a.get("rozl") and a["rozl"] > (a.get("rozl_koniec") or 0)) or o["ekran"] in ("logowanie", "lista")
        w_logowaniu = (st.get("faza") == "LOGOWANIE" and st.get("logowanie_nasze")
                       and ts_ep(teraz) - st.get("login_ts", ts_ep(teraz)) < 600)
        if w_logowaniu and zm is not None:
            if ts_ep(teraz) - st.get("zaloguj_ts", 0) < 60:
                return D(id_, "czekaj", "logowanie w toku: czekam na wejście do gry", "logowanie-czeka")
            return D(id_, "zaloguj", "sesja stoi, klient na ekranie logowania: zaloguj.sh (kliki Login i Ok)", "zaloguj",
                     klasa="logowanie", zmiana_od=zm["od"])
        if rozl and zm is not None:
            n = len(self.naprawy_w_oknie(id_, teraz))
            if n >= 3:
                return D(id_, "eskaluj", f"wyczerpana rotacja napraw (rozłączenie, {n} relogów w {self.konf['napraw_okno_min']} min)",
                         "wyczerpana", klasa="eskalacja", kod_eskalacji="wyczerpana")
            return D(id_, "relog", "rozłączenie (ROZŁĄCZENIE w logu bota / ekran logowania): ponowne logowanie", "relog",
                     klasa="zdarzenie", problem="rozlaczenie")
        od = st.setdefault("nieustalony_od", ts_ep(teraz))
        if ts_ep(teraz) - od >= float(self.konf["nieustalony_min"]) * 60:
            return D(id_, "eskaluj", f"stan nieustalony od {round((ts_ep(teraz) - od) / 60)} min (sesja jest, odczytu gry brak)",
                     "nieustalony", klasa="eskalacja", kod_eskalacji="nieustalony")
        return D(id_, "czekaj", "sesja jest, brak odczytu gry: obserwuję (stan nieustalony po "
                 f"{self.konf['nieustalony_min']} min)", "nieustalony-obserwacja")

    def _bez_bota(self, id_, o, a, st, teraz, zm):
        """W grze, bota brak. Start po logowaniu, koniec w depo, alarm albo awaria."""
        koniec_flaga = st.get("koniec") is not None or teraz >= datetime.strptime(zm["koniec"], FMT)
        w_depo = bool(a.get("depo") and (a.get("start") is None or a["depo"] >= a["start"])) or bool(o["panel"].get("w_depo"))
        znany = st.get("bot_start") or st.get("bot_widziany") or st.get("sesja_nasza") or st.get("faza") in ("POWROT", "MIASTO", "WYLOGOWANIE")
        if not znany and not (o["stop"] and w_depo):
            return D(id_, "czekaj", "bot nie działa, a nie widziałem go w tej sesji nadzoru: możliwa ręczna gra, nie ruszam",
                     "bot-nieznany")
        dowod_miasta = bool(w_depo or o["panel"].get("w_miescie"))      # dodatni dowód z obserwacji, nie z fazy zapamiętanej
        nowa_sesja = (st.get("faza") in ("LOGOWANIE", "DOJSCIE") and not st.get("bot_start") and st.get("sesja_nasza")
                      and not o["stop_reczny"])
        if nowa_sesja:
            # B-4: zalegający STOP po poprzednim wroc.sh nie blokuje startu na następnej zmianie (uruchom.sh go czyści); STOP_RECZNY nigdy
            wyb = self._wybor_startu(id_, o, st, zm, teraz)
            if "akcja" in wyb:          # czekaj / eskaluj (brak danych albo brak spotu): bez startu
                return wyb
            mapa, tryb, skad, spot = wyb["mapa"], wyb["tryb"], wyb["skad"], wyb["spot"]
            return D(id_, "start_bota", f"zalogowany, start bota na {mapa} / {tryb or '-'} (źródło: {skad})"
                     + (" [zalegający STOP zostanie skasowany przez uruchom.sh]" if o["stop"] else ""), "start-bota",
                     klasa="bot", mapa=mapa, tryb=tryb, spot=spot)
        if o["stop"] and (koniec_flaga or st.get("faza") in ("POWROT", "MIASTO", "WYLOGOWANIE")):
            if not dowod_miasta:
                # B-3: STOP, ale brak dowodu, że postać jest w mieście (alarm w połowie WROC): ani serwis, ani wylogowanie.
                # WROC wymaga żywego bota, więc naprawa = wznowienie (po nim koniec zmiany znów zleci WROC), a po wyczerpaniu eskalacja.
                return self.drabina(id_, teraz, "alarm", o)
            return self._miasto(id_, o, st, teraz, zm)
        if o["stop"]:
            if a.get("alarm") and (a.get("stop") is None or a["alarm"] >= (a.get("stop") or 0) - 120):
                return self.drabina(id_, teraz, "alarm", o)
            if w_depo or o["panel"].get("w_depo"):
                ile = ts_ep(teraz) - st.setdefault("stoi_w_depo_od", ts_ep(teraz))
                if ile < 600:
                    return D(id_, "czekaj", "bot stoi w depo poza moim cyklem (STOP): daję 10 min na refill/ręczne wznowienie", "depo-poza")
            return self.drabina(id_, teraz, "alarm", o)
        return self.drabina(id_, teraz, "awaria", o)

    def _wybor_startu(self, id_, o, st, zm, teraz):
        """Mapa i tryb na start zmiany. -> {"mapa", "tryb", "skad", "spot"} albo decyzja D (czekaj / eskaluj), gdy startu być nie może.
        Jawna mapa z grafiku/konfiguracji (decyzja Karola) wygrywa; inaczej tabela spotów; bez tabeli jak dotąd (bieżąca mapa z tryb.log)."""
        if zm and zm.get("mapa"):
            return {"mapa": zm["mapa"], "tryb": zm.get("tryb"), "skad": "grafik", "spot": None}
        tab = self.tabela_spotow()
        if tab is None or tab.blad:
            if not self._ostrzezono_tabele:
                self._ostrzezono_tabele = True
                self.wpisz(teraz, D("*", "ostrzezenie", (tab.blad if tab else "brak dane_tibia/spoty_nadzorca.json")
                                    + ": wybór spotu wyłączony, start na bieżącej mapie z tryb.log (jak przed Q5)", "spoty-brak-tabeli"), "ostrzezenie")
            mapa, tryb, skad = self._mapa_zmiany(id_, zm)
            return {"mapa": mapa, "tryb": tryb, "skad": skad, "spot": None}
        biez_mapa, biez_tryb, _skad = mapa_tryb_biezace(self.korzen, id_, teraz)
        w = self.wybierz_spot(id_, o.get("panel"), o.get("gracz"), teraz, biez_mapa, zm["od"] if zm else "start")
        if w["mapa"]:
            self._przypisane[id_] = w["mapa"]
            return {"mapa": w["mapa"], "tryb": biez_tryb, "skad": "wybór spotu: " + w["powod"], "spot": {"mapa": w["mapa"], "jaskinia": w["jaskinia"]}}
        if w["brak"] == "dane":
            ile = ts_ep(teraz) - (st.get("login_ts") or ts_ep(teraz))
            if ile >= 600:
                return D(id_, "eskaluj", f"wybór spotu niemożliwy od {round(ile / 60)} min po zalogowaniu: {w['powod']}", "spot-dane",
                         klasa="eskalacja", kod_eskalacji="nieustalony")
            return D(id_, "czekaj", f"wybór spotu: {w['powod']}; czekam na odczyt (do 10 min po zalogowaniu)", "spot-dane")
        return D(id_, "eskaluj", w["powod"], "brak-spotu", klasa="eskalacja", kod_eskalacji="brak_spotu")

    def _mapa_zmiany(self, id_, zm):
        if zm and zm.get("mapa"):
            return zm["mapa"], zm.get("tryb"), "grafik"
        mapa, tryb, skad = mapa_tryb_biezace(self.korzen, id_, self.zegar())
        zaj = self._zajete_mapy(id_)
        if mapa in zaj:
            s = self.spot_zapasowy(id_, mapa, zaj)
            if s:
                return s[0], s[1] or tryb, "spot zapasowy (mapa zajęta przez inny bot)"
        return mapa, tryb, skad

    def _miasto(self, id_, o, st, teraz, zm):
        """Postać w mieście po powrocie: serwis (jeśli miasto ma plan i serwis.sh istnieje), potem wylogowanie."""
        st["faza"] = "MIASTO"
        serwis_ma = o["panel"].get("wroc_refill") != "brak_planu" and (DIR / "serwis.sh").exists()
        kod_plik = self.W / f"nadzor_serwis_{id_}.kod"
        if not serwis_ma:
            st.setdefault("serwis_koniec", "brak planu serwisu w tym mieście")
        if not st.get("serwis_koniec"):
            if o["serwis_dziala"]:
                return D(id_, "czekaj", "MIASTO: serwis trwa", "serwis-trwa")
            if not st.get("serwis_start"):
                return D(id_, "serwis", "MIASTO: odkładanie do depo i serwis (serwis.sh)", "serwis", klasa="naprawa", problem="serwis")
            kod = kod_plik.read_text().strip() if kod_plik.exists() else None
            if kod is None and ts_ep(teraz) - st["serwis_start"] < 180:
                return D(id_, "czekaj", "MIASTO: serwis wystartował, czekam na wynik", "serwis-trwa")
            kod = kod if kod is not None else "?"
            st["serwis_koniec"] = kod
            if kod != "0":
                st["serwis_blad"] = st.get("serwis_blad", 0) + 1
                if st["serwis_blad"] < 2:
                    st.pop("serwis_koniec", None)
                    st.pop("serwis_start", None)
                    return D(id_, "serwis", f"serwis zakończył się kodem {kod}: ponawiam raz", "serwis-ponow", klasa="naprawa", problem="serwis")
        return self._wylogowanie(id_, o, st, teraz, zm)

    def _wylogowanie(self, id_, o, st, teraz, zm):
        st["faza"] = "WYLOGOWANIE"
        st.setdefault("wylog_od", ts_ep(teraz))
        if st.get("koniec") == "czas" and teraz < datetime.strptime(zm["wylog"], FMT):
            return D(id_, "czekaj", f"WYLOGOWANIE: czekam na planowaną godzinę {zm['wylog'][11:]} (odstęp od innych)", "wylog-plan")
        a = o["log"] or {}
        if st.get("wylog_bl", 0) >= 3:
            return D(id_, "eskaluj", f"stan nieustalony: wylogowanie nieudane {st['wylog_bl']} razy (ostatni kod {st.get('wylog_kod')})",
                     "wylog-nieudane", klasa="eskalacja", kod_eskalacji="nieustalony")
        czekaj_max = float(self.konf["wylog_spokoj_max_min"]) * 60
        if a.get("walka") and ts_ep(teraz) - st["wylog_od"] < czekaj_max:
            return D(id_, "czekaj", "WYLOGOWANIE: czekam na spokój (walka w ostatnich 20 s)", "wylog-spokoj")
        pow_ = "koniec zmiany, postać w mieście" + (" (spokój)" if not a.get("walka") else " (po 15 min bez spokoju)")
        return D(id_, "wyloguj", pow_ + f": wyloguj.sh i zamknięcie sesji (powód: {st.get('koniec') or 'grafik'})", "wyloguj", klasa="zdarzenie")

    # --- przebieg ---
    def tick(self):
        teraz = self.zegar()
        konf = self.konf = G.wczytaj_konfig(self.korzen)
        self.raport = []
        self._tab_ladowana, self._przypisane, self._obs = False, {}, {}     # tabela spotów i przypisania są na jeden przebieg
        cisza = self.powiadomienia_wylaczone()
        if cisza and self.zywo:
            # B-1: bez widocznych powiadomień eskalacja (i hold) zamroziłaby postać bez wiedzy Karola: żywy tryb się nie włącza
            self.zywo, self.wykonawca = False, WykonawcaCien()
            self.stan["globalne"]["zywy_zablokowany"] = f"powiadomienia wyłączone ({cisza}): tryb na żywo nie startuje, praca w cieniu"
            self.wpisz(teraz, D("*", "zywy_zablokowany", f"NADZOR_ZYWO nie startuje: eskalacje niewidoczne ({cisza}); praca w cieniu", "zywy-cisza"), "blokada")
        else:
            self.stan["globalne"].pop("zywy_zablokowany", None)
        self.stan["globalne"]["powiadomienia_wylaczone"] = cisza
        if cisza and not self.zywo:
            self.wpisz(teraz, D("*", "ostrzezenie", f"eskalacje niewidoczne: {cisza} (Karol nie zobaczyłby powiadomień critical)", "cisza"), "ostrzezenie")
        if (self.W / "NADZOR_PAUZA").exists():
            self.wpisz(teraz, D("*", "pauza", "NADZOR_PAUZA: zero akcji", "pauza"), "pauza")
            self.zapisz_stan(teraz)
            return self.raport
        try:
            raw_lista = self.zrodla.stan()
        except Exception as e:      # noqa: BLE001
            self.wpisz(teraz, D("*", "brak", f"odczyt stanu nieudany: {e!r}", "odczyt"), "blad")
            return self.raport
        self._raw = {r["id"]: r for r in raw_lista}
        online_teraz = sorted(i for i, r in self._raw.items() if r.get("sesja") or r.get("gra"))
        glob = self.stan["globalne"]
        if glob.get("online") is not None and sorted(glob["online"]) != online_teraz:
            if ts_ep(teraz) - (glob.get("ostatnie_zdarzenie") or 0) > 150:
                glob["ostatnie_zdarzenie"] = ts_ep(teraz)
                self.wpisz(teraz, D("*", "zdarzenie_zewn", f"zmiana liczby sesji {glob['online']} -> {online_teraz} bez naszej akcji", "zewn-" + ",".join(online_teraz)), "info")
        glob["online"] = online_teraz
        ids = G.pula(self.korzen, konf)
        plan, utworzono = G.plan_dla(teraz, self.korzen, konf, online={i: {"od": None} for i in online_teraz if i in ids}, zapis=self.zapis)
        if utworzono:
            self.wpisz(teraz, D("*", "grafik", f"brak grafiku doby: wygenerowano ({plan['zrodlo']}, {len(plan['zmiany'])} zmian)", "grafik-nowy"), "info")
        kandydaci = []
        for id_ in ids:
            odmowa = self.bramka(id_)
            st = self.post(id_)
            raw = self._raw.get(id_)
            if odmowa:
                self.wpisz(teraz, D(id_, "zablokowane", odmowa, "bramka-" + odmowa[:12]), "info")
                self._ponow_powiadomienie(teraz, id_)
                if raw and not (raw.get("sesja") or raw.get("gra")) and st.get("faza") != "OFFLINE":
                    self.licz_wylogowanie(id_, teraz)
                    st["faza"] = "OFFLINE"
                continue
            try:
                o = self.obserwuj(id_, raw, teraz)
                self._obs[id_] = o
                for d in self.decyduj(id_, o, plan, teraz):
                    kandydaci.append((id_, d, o))
            except Exception as e:      # noqa: BLE001  (jedna postać nie wywraca przebiegu pozostałych)
                self.wpisz(teraz, D(id_, "brak", f"błąd oceny postaci: {e!r}", "wyjatek"), "blad")
        # akcje niezwiązane z logowaniem od razu, zdarzenia logowania po jednym na tick
        zdarzenia = []
        for id_, d, o in kandydaci:
            if d["klasa"] in ("zdarzenie", "logowanie"):
                zdarzenia.append((id_, d, o))
            else:
                self.wykonaj(teraz, id_, d, o)
        zdarzenia.sort(key=lambda x: (0 if x[1]["akcja"] == "wyloguj" else (1 if x[1]["akcja"] == "zaloguj" else 2), x[0]))
        wolne = int(konf["max_online"]) - len(set(online_teraz) | self._wirtualne(teraz))
        zajety = False
        for id_, d, o in zdarzenia:
            if d["klasa"] == "logowanie":     # kolejny krok trwającego logowania nie jest nowym zdarzeniem
                if zajety:
                    self.wpisz(teraz, {**d, "akcja": "odroczone", "powod": "inna akcja logowania/wylogowania w tym przebiegu"}, "odroczone")
                    continue
                self.wykonaj(teraz, id_, d, o)
                zajety = True
                continue
            if self.zywo is False and self._cien_zdublowany(id_, d, teraz):
                continue                      # cień: ta sama decyzja już zapisana, nie blokuje następnych
            if zajety:
                self.wpisz(teraz, D(id_, "odroczone", "inna akcja logowania/wylogowania w tym przebiegu (jedna naraz)", "slot"), "odroczone")
                continue
            ok, powod = self.odstep_ok(teraz)
            if not ok:
                self.wpisz(teraz, D(id_, "odroczone", f"{d['akcja']}: {powod}", "odstep-" + d["akcja"]), "odroczone")
                continue
            if d["akcja"] == "sesja_start" and wolne <= 0:
                self.wpisz(teraz, D(id_, "odroczone", f"komplet online ({konf['max_online']})", "komplet"), "odroczone")
                continue
            self.wykonaj(teraz, id_, d, o)
            zajety = True
            if d["akcja"] == "sesja_start":
                wolne -= 1
        if not self.zywo:
            try:
                self.podglad_spotow(teraz)
            except Exception as e:      # noqa: BLE001  (podgląd jest dodatkiem: nie wywraca przebiegu)
                self.wpisz(teraz, D("*", "brak", f"podgląd spotów nieudany: {e!r}", "spot-podglad-wyjatek"), "blad")
        if zajety and self.zywo:
            try:      # po własnej akcji logowania/wylogowania zapamiętaj NOWY zestaw sesji (inaczej następny przebieg uzna go za zdarzenie zewnętrzne)
                glob["online"] = sorted(r["id"] for r in self.zrodla.stan() if r.get("sesja") or r.get("gra"))
            except Exception:       # noqa: BLE001
                pass
        self.zapisz_stan(teraz)
        return self.raport

    def podglad_spotow(self, teraz):
        """CIEŃ: plan „gdyby wszystkie postacie w grze (poza blokadami) zaczynały zmianę teraz, po kolei, od depo”: każda wybiera spot przy zajętości
        z wyborów poprzednich (ich bieżące spoty są wolne, ale bieżąca jaskinia odpada przez mieszanie). Tylko wpis do dziennika/wydruku
        (zero akcji, zero zmian stanu poza dedupem)."""
        if self.tabela_spotow() is None or self.tabela_spotow().blad:
            return
        g = self.stan["globalne"]
        if self.zapis and ts_ep(teraz) - (g.get("podglad_spotow_ts") or 0) < 1800:
            return      # z zapisem najwyżej raz na 30 min (odczyt ekwipunku z pamięci gry nie co przebieg); --raz zawsze
        if self.zapis:
            g["podglad_spotow_ts"] = ts_ep(teraz)
        rezerwacje = {}
        for id_ in sorted(self._obs):
            o = self._obs[id_]
            if not (o["online"] and o["w_grze"]) or self.bramka(id_):
                continue
            try:
                biez = mapa_tryb_biezace(self.korzen, id_, teraz)[0]
                w = self.wybierz_spot(id_, o.get("panel"), o.get("gracz"), teraz, biez, "podglad", zajete=set(rezerwacje.values()), z_depo=True)
            except Exception as e:      # noqa: BLE001
                self.wpisz(teraz, D(id_, "brak", f"podgląd spotu nieudany: {e!r}", "spot-podglad-wyjatek"), "blad")
                continue
            if w["mapa"]:
                rezerwacje[id_] = w["mapa"]
                tekst = f"teraz na {biez or '?'}; przy starcie zmiany wybrałbym: {w['powod']}"
                kod = "podglad-" + w["mapa"]
            else:
                tekst = f"teraz na {biez or '?'}; przy starcie zmiany: {w['powod']}" + (" [eskalacja brak_spotu]" if w["brak"] == "spot" else " [czekam na dane]")
                kod = "podglad-brak-" + w["brak"]
            self.wpisz(teraz, D(id_, "spot_podglad", tekst, kod), "cień", szczegol="podgląd, bez akcji")

    def _wirtualne(self, teraz):
        """Cień: postacie, którym w ostatnich 30 min 'zrobiłbym start sesji', a realnie jeszcze offline (liczą się do kompletu)."""
        if self.zywo:
            return set()
        wynik = set()
        for id_, st in self.stan["postacie"].items():
            if st.get("wirt_login") and ts_ep(self.zegar()) - st["wirt_login"] < 1800:
                wynik.add(id_)
        return wynik

    def _cien_zdublowany(self, id_, d, teraz):
        t = self.stan["cien"].get(f"{id_}|{d['akcja']}|{d['kod']}")
        return t is not None and ts_ep(teraz) - t < float(self.konf["cien_powtorz_min"]) * 60

    def wpisz(self, teraz, d, wynik, **extra):
        """Zapis decyzji bez wykonania (info, odroczenia, blokady) z odsiewem powtórek."""
        klucz = f"{d['id']}|{d['akcja']}|{d['kod']}"
        t = self.stan["cien"].get(klucz)
        if t is not None and ts_ep(teraz) - t < float(self.konf["cien_powtorz_min"]) * 60 * (2 if d["akcja"] in ("czekaj", "zablokowane", "odroczone", "spot_podglad") else 1):
            return None
        self.stan["cien"][klucz] = ts_ep(teraz)
        rek = self.dziennik.pisz(teraz, "zywo" if self.zywo else "cien", id=d["id"], akcja=d["akcja"], wynik=wynik, powod=d["powod"], **extra)
        self.raport.append(rek)
        return rek

    def wykonaj(self, teraz, id_, d, o=None):
        """Wykonanie (na żywo) albo zapis 'zrobiłbym' (cień) jednej decyzji. Aktualizuje znaczniki stanu."""
        akcja = d["akcja"]
        st = self.post(id_)
        if akcja in ("czekaj", "zablokowane", "brak"):
            self.wpisz(teraz, d, "info")
            return True, ""
        # B-2: bramki (STOP_RECZNY, NADZOR_PAUZA, nadzor:false, hold) sprawdzane ZNOWU tuż przed każdą akcją, nie tylko raz na przebieg
        odmowa = self.bramka(id_, czy_hold=(akcja != "eskaluj"))
        if odmowa:
            self.wpisz(teraz, D(id_, "zablokowane", f"{akcja} wstrzymane tuż przed wykonaniem: {odmowa}", "bramka-przed-" + akcja), "odmowa")
            return False, odmowa
        if akcja == "eskaluj":
            return self.eskaluj(teraz, id_, d)
        if self.zywo is False:
            if self._cien_zdublowany(id_, d, teraz):
                return True, "cień (powtórka)"
            ok, txt = True, f"cień: zrobiłbym {akcja}"
            if akcja in ("start_bota",):
                txt += f" {d['arg'].get('mapa')} / {d['arg'].get('tryb')}"
            self.stan["cien"][f"{id_}|{akcja}|{d['kod']}"] = ts_ep(teraz)
            self.raport.append(self.dziennik.pisz(teraz, "cien", id=id_, akcja=akcja, wynik="cień", powod=d["powod"], szczegol=txt))
            if d["klasa"] == "zdarzenie":
                self.stan["globalne"]["ostatnie_zdarzenie"] = ts_ep(teraz)
                if akcja == "sesja_start":
                    st["wirt_login"] = ts_ep(teraz)
            return ok, txt
        poprz = st.setdefault("akcje_ts", {}).get(akcja)
        if poprz is not None and ts_ep(teraz) - poprz < 120 and akcja not in ("zaloguj",):
            self.wpisz(teraz, D(id_, "czekaj", f"{akcja}: ponowienie < 2 min po poprzedniej próbie", "ponow-" + akcja), "info")
            return False, "zbyt wcześnie"
        st["akcje_ts"][akcja] = ts_ep(teraz)
        return self._wykonaj_zywo(teraz, id_, d, st)

    def _wykonaj_zywo(self, teraz, id_, d, st):
        akcja, arg, W = d["akcja"], d["arg"], self.wykonawca
        zamek = None
        if d["klasa"] in ("zdarzenie", "logowanie"):
            self.W.mkdir(parents=True, exist_ok=True)
            zamek = open(self.W / "nadzor_logowanie.lock", "a")
            try:
                fcntl.flock(zamek, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                zamek.close()
                self.wpisz(teraz, D(id_, "odroczone", "inna akcja logowania/wylogowania trwa (blokada pliku)", "zamek"), "odroczone")
                return False, "zamek"
        try:
            odmowa = self.bramka(id_)
            if odmowa:
                self.wpisz(teraz, D(id_, "zablokowane", f"{akcja} wstrzymane po zdobyciu blokady: {odmowa}", "bramka-zamek-" + akcja), "odmowa")
                return False, odmowa
            if akcja == "sesja_start":
                ok, txt = W.sesja_start(id_)
                st["start_bl"] = 0 if ok else st.get("start_bl", 0) + 1
                if ok:
                    st["faza"], st["zmiana_od"], st["login_ts"] = "LOGOWANIE", arg.get("zmiana_od"), ts_ep(teraz)
                    st["logowanie_nasze"] = st["sesja_nasza"] = True
                    st["wykonane"] = (st.get("wykonane", []) + [arg.get("zmiana_od")])[-30:]
                    st["zaloguj_ts"] = 0
            elif akcja == "zaloguj":
                ok, txt = W.zaloguj(id_)
                st["zaloguj_ts"] = ts_ep(teraz)
                self._po_logowaniu(teraz, id_, ok, txt)
            elif akcja == "start_bota":
                odmowa = self.bramka(id_)
                if odmowa:       # uruchom.sh robi rm -f STOP_RECZNY: nigdy, gdy Karol przejął postać w trakcie przebiegu
                    return False, odmowa
                ok, txt = W.start_bota(id_, arg.get("mapa"), arg.get("tryb"))
                if ok:
                    st["bot_start"], st["faza"] = ts_ep(teraz), "DOJSCIE"
                    if arg.get("mapa"):
                        self.zapamietaj_spot(id_, st, arg["mapa"], teraz)
            elif akcja in ("restart", "wznow", "zmien_spot"):
                ok, txt = self._restart(teraz, id_, akcja, st)
            elif akcja == "wroc":
                ok, txt = W.wroc(id_)
                if ok:
                    st["faza"], st["powrot_od"] = "POWROT", ts_ep(teraz)
                if d.get("arg", {}).get("problem") != "koniec":
                    st.setdefault("naprawy", []).append([ts_ep(teraz), "wroc"])
            elif akcja == "serwis":
                ok, txt = W.serwis(id_)
                if ok:
                    st["serwis_start"] = ts_ep(teraz)
                st["serwis_blad"] = st.get("serwis_blad", 0)
            elif akcja == "wyloguj":
                ok, txt = W.wyloguj(id_)
                if not ok:
                    st["wylog_bl"] = st.get("wylog_bl", 0) + 1
                    st["wylog_kod"] = _kod(txt)
                    if _kod(txt) == 6:
                        self.eskaluj(teraz, id_, D(id_, "eskaluj", "zgon (wyloguj.sh kod 6)", "zgon-wyloguj", klasa="eskalacja", kod_eskalacji="zgon"))
                if ok:
                    self.licz_wylogowanie(id_, teraz)
                    st["zakonczone"] = (st.get("zakonczone", []) + [st.get("zmiana_od")])[-30:]
                    st["faza"], st["ostatnie_wylog"] = "OFFLINE", ts_ep(teraz)
                    for k in ("serwis_start", "serwis_koniec", "serwis_blad", "wylog_od", "koniec", "bot_start", "stoi_w_depo_od", "zmiana_od", "naprawy", "sesja_nasza", "bot_widziany", "wylog_bl", "wylog_kod", "powrot_od", "stoi_w_depo_od", "spot"):
                        st.pop(k, None)
            elif akcja == "relog":
                ok, txt = self._relog(teraz, id_, st)
            else:
                ok, txt = False, f"nieznana akcja {akcja}"
            if d["klasa"] == "zdarzenie" and ok:
                self.stan["globalne"]["ostatnie_zdarzenie"] = ts_ep(teraz)
        finally:
            if zamek:
                fcntl.flock(zamek, fcntl.LOCK_UN)
                zamek.close()
        rek = self.dziennik.pisz(teraz, "zywo", id=id_, akcja=akcja, wynik="ok" if ok else "blad", powod=d["powod"], szczegol=txt)
        self.raport.append(rek)
        return ok, txt

    def _restart(self, teraz, id_, akcja, st):
        """restart / wznow / zmien_spot: bot na BIEŻĄCEJ mapie i trybie (tryb.log), zmien_spot na zapasowym. Restart tylko poza walką."""
        W = self.wykonawca
        raw = getattr(self, "_raw", {}).get(id_) or {}
        o_log = analizuj_log(czytaj_log(najnowszy_log(self.kat(id_) / "logi"), teraz), ts_ep(teraz))
        if akcja in ("restart", "zmien_spot") and raw.get("bot") and o_log.get("walka"):
            return False, f"bot w walce: {akcja} odroczony"
        mapa, tryb, skad = mapa_tryb_biezace(self.korzen, id_, self.zegar())
        nowy_spot = None
        if akcja == "zmien_spot":
            if self.profil(id_).get("spoty_zapasowe") or self.tabela_spotow() is None or self.tabela_spotow().blad:
                s = self.spot_zapasowy(id_, mapa, self._zajete_mapy(id_))
                if not s:
                    return False, "brak spotu zapasowego w profil.json (spoty_zapasowe)"
                mapa, tryb = s[0], s[1] or tryb
                skad = "spoty_zapasowe"
            else:
                w = self.wybierz_spot(id_, raw.get("panel"), raw.get("gracz"), teraz, mapa, f"zmien_spot-{teraz:%H%M}", dodatkowo_zajete=(mapa,))
                if not w["mapa"]:
                    return False, "zmiana spotu niemożliwa: " + w["powod"]
                mapa, nowy_spot = w["mapa"], w["mapa"]
                skad = "wybór spotu: " + w["powod"]
        if raw.get("bot"):
            ok, txt = W.zatrzymaj_bota(id_)
            if not ok:
                return False, "zatrzymanie nieudane: " + txt
        odmowa = self.bramka(id_)
        if odmowa:           # zatrzymanie trwa kilka sekund: w tym czasie mogło pojawić się STOP_RECZNY (uruchom.sh by go skasował)
            st.setdefault("naprawy", []).append([ts_ep(teraz), akcja])
            return False, "start bota anulowany po zatrzymaniu: " + odmowa
        ok, txt = W.start_bota(id_, mapa, tryb)
        st.setdefault("naprawy", []).append([ts_ep(teraz), akcja])
        if ok:
            st["bot_start"], st["faza"] = ts_ep(teraz), "DOJSCIE"
            st["stoi_w_depo_od"] = None
            if nowy_spot:
                self.zapamietaj_spot(id_, st, nowy_spot, teraz)
        return ok, f"{mapa} / {tryb or '-'} (źródło: {skad}); {txt}"

    def _relog(self, teraz, id_, st):
        W = self.wykonawca
        raw = getattr(self, "_raw", {}).get(id_) or {}
        if not raw.get("sesja"):
            ok, txt = W.sesja_start(id_)
            if not ok:
                return False, "start sesji: " + txt
        ok, txt = W.zaloguj(id_)
        self._po_logowaniu(teraz, id_, ok, txt)
        st.setdefault("naprawy", []).append([ts_ep(teraz), "relog"])
        st["faza"], st["zaloguj_ts"] = "LOGOWANIE", ts_ep(teraz)
        st["logowanie_nasze"] = st["sesja_nasza"] = True
        st["bot_start"] = None
        st["login_ts"] = st.get("login_ts") or ts_ep(teraz)
        return ok, txt

    def _po_logowaniu(self, teraz, id_, ok, txt):
        """zaloguj.sh: kod 9 = zalogowano INNĄ postać, kod 6 = zgon: nie zwykła porażka, tylko eskalacja do Karola (z wstrzymaniem)."""
        if ok:
            return
        k = _kod(txt)
        if k == 9:
            self.eskaluj(teraz, id_, D(id_, "eskaluj", "zaloguj.sh kod 9: zalogowano INNĄ postać niż w profilu", "zla-postac", klasa="eskalacja", kod_eskalacji="zla_postac"))
        elif k == 6:
            self.eskaluj(teraz, id_, D(id_, "eskaluj", "zaloguj.sh kod 6: zgon postaci", "zgon-zaloguj", klasa="eskalacja", kod_eskalacji="zgon"))

    # --- eskalacja ---
    def eskaluj(self, teraz, id_, d):
        kod = d["arg"].get("kod_eskalacji") or d["kod"]
        st = self.post(id_)
        if d["arg"].get("zdarzenie_ts") and self.zywo:      # cień nie "zużywa" zdarzenia: po włączeniu żywego trybu Karol je dostanie
            st.setdefault("eskalowane", {})[kod] = d["arg"]["zdarzenie_ts"]
        klucz = f"{'esk' if self.zywo else 'ciesk'}|{id_}|{kod}"
        t = self.stan["cien"].get(klucz)
        if t is not None and ts_ep(teraz) - t < float(self.konf["eskalacja_powtorz_min"]) * 60:
            return True, "eskalacja już zgłoszona"
        self.stan["cien"][klucz] = ts_ep(teraz)
        tresc = f"{id_}: {d['powod']}"
        if self.zywo:
            ok, txt = self.wykonawca.powiadom(id_, f"Nadzór Retronic [{id_}]", tresc)
            if self.powiadomienia_wylaczone():
                ok = False
            if kod not in ("nieustalony", "brak_spotu"):
                st["hold"] = {"powod": d["powod"][:100], "od": teraz.strftime(FMT), "powiadomiono": bool(ok)}
            wynik = "powiadomiono" if ok else "powiadomienie NIE dotarło (postać wstrzymana bez wiedzy Karola)"
        else:
            ok, wynik = True, "cień"
            txt = "cień: powiadomiłbym (critical)" + (f"; UWAGA eskalacje niewidoczne: {self.powiadomienia_wylaczone()}" if self.powiadomienia_wylaczone() else "")
        rek = self.dziennik.pisz(teraz, "zywo" if self.zywo else "cien", id=id_, akcja="eskaluj", wynik=wynik, powod=d["powod"],
                                 szczegol=txt, wstrzymanie=bool(self.zywo and kod not in ("nieustalony", "brak_spotu")))
        self.raport.append(rek)
        return ok, txt

    # --- biała lista (CLI / obchód) ---
    def napraw(self, id_, rodzaj):
        """Jedna akcja z białej listy z tymi samymi bramkami co tick. -> (kod_wyjścia, tekst)."""
        teraz = self.zegar()
        self.raport = []
        if rodzaj not in BIALA_LISTA:
            return 2, f"rodzaj spoza białej listy: {rodzaj} (dozwolone: {', '.join(BIALA_LISTA)})"
        if self.zywo_zadane and self.powiadomienia_wylaczone():
            return 3, f"odmowa: tryb na żywo nie działa przy wyłączonych powiadomieniach ({self.powiadomienia_wylaczone()})"
        if not (self.kat(id_) / "profil.json").exists() or id_.startswith("_"):
            return 2, f"nieznana instancja {id_}"
        odmowa = self.bramka(id_)
        if odmowa:
            self.wpisz(teraz, D(id_, rodzaj, "odmowa: " + odmowa, "odmowa-" + rodzaj), "odmowa", zrodlo="obchod")
            return 3, "odmowa: " + odmowa
        try:
            self._raw = {r["id"]: r for r in self.zrodla.stan()}
        except Exception as e:      # noqa: BLE001
            return 4, f"odczyt stanu nieudany: {e!r}"
        raw = self._raw.get(id_)
        o = self.obserwuj(id_, raw, teraz)
        a = o["log"] or {}
        wyn = self.eskalacje_z_logu(id_, o, teraz) if o["online"] else []
        pow_ = f"obchód: napraw {rodzaj}"
        blok = None
        if rodzaj in ("restart", "wznow", "zmien_spot", "wroc", "wyloguj", "relog") and not o["online"] and rodzaj != "relog":
            blok = "postać offline (brak sesji)"
        elif rodzaj in ("restart", "wznow", "zmien_spot") and wyn:
            blok = "zdarzenie dla Karola (PK/zgon/GM/IP): " + wyn[0]["powod"]
        elif rodzaj == "wznow" and (o["bot"] or not o["stop"]):
            blok = "wznow dotyczy bota zatrzymanego STOP po alarmie (bot działa albo brak STOP)"
        elif rodzaj in ("restart", "zmien_spot") and o["bot"] and a.get("walka"):
            blok = "bot w walce: restart tylko poza walką"
        elif rodzaj == "restart" and not o["bot"]:
            blok = "bot nie działa: użyj wznow"
        elif rodzaj == "wroc" and not o["bot"]:
            blok = "wroc.sh wymaga działającego bota"
        elif rodzaj == "relog" and not (a.get("rozl") or o["ekran"] in ("logowanie", "lista") or not o["w_grze"]):
            blok = "brak śladów rozłączenia (log bota, ekran) i klient w grze"
        elif rodzaj == "wyloguj" and o["bot"]:
            blok = "bot działa: najpierw wroc (wylogowanie dopiero po powrocie do miasta)"
        elif rodzaj == "wyloguj" and a.get("walka"):
            blok = "walka w ostatnich 20 s: wylogowanie tylko w spokoju"
        if blok is None and rodzaj in ZDARZENIA_LOGOWANIA:
            ok, powod = self.odstep_ok(teraz)
            if not ok:
                blok = powod
        if blok:
            self.wpisz(teraz, D(id_, rodzaj, "odmowa: " + blok, "odmowa-" + rodzaj), "odmowa", zrodlo="obchod")
            self.zapisz_stan(teraz)
            return 3, "odmowa: " + blok
        klasa = "zdarzenie" if rodzaj in ZDARZENIA_LOGOWANIA else "naprawa"
        d = D(id_, rodzaj, pow_, "obchod-" + rodzaj, klasa=klasa, problem="obchod")
        ok, txt = self.wykonaj(teraz, id_, d, o)
        self.zapisz_stan(teraz)
        return (0 if ok else 1), txt

    def odblokuj(self, id_):
        st = self.post(id_)
        h = st.pop("hold", None)
        for k in [k for k in self.stan["cien"] if k.startswith(f"esk|{id_}|")]:
            self.stan["cien"].pop(k)
        self.zapisz_stan(self.zegar())
        return f"odblokowano {id_}" + (f" (było: {h.get('powod')})" if h else " (nie było wstrzymania)")

    # --- skrót dla obchodu ---
    def podsumowanie(self, ile_decyzji=15):
        teraz = self.zegar()
        plan = G.zaladuj(G.doba_dla(teraz, self.konf), self.korzen)
        wynik = {"czas": teraz.strftime(FMT), "tryb": "zywo" if (self.W / "NADZOR_ZYWO").exists() else "cien",
                 "pauza": (self.W / "NADZOR_PAUZA").exists(), "grafik": bool(plan), "postacie": {},
                 "powiadomienia_wylaczone": self.powiadomienia_wylaczone(),
                 "uwagi": []}
        if wynik["powiadomienia_wylaczone"] and wynik["tryb"] == "zywo":
            wynik["tryb"] = f"cien (NADZOR_ZYWO jest, ale zablokowany: {wynik['powiadomienia_wylaczone']})"
        if wynik["powiadomienia_wylaczone"]:
            wynik["uwagi"].append(f"ESKALACJE NIEWIDOCZNE: {wynik['powiadomienia_wylaczone']}; tryb na żywo się nie włączy, cień ostrzega")
        for id_ in G.pula(self.korzen, self.konf):
            st = self.post(id_)
            zm = G.aktywna_zmiana(plan, id_, teraz) if plan else None
            nast = next((z for z in G.zmiany_postaci(plan, id_) if z["od"] > teraz.strftime(FMT)), None) if plan else None
            if st.get("hold") and st["hold"].get("powiadomiono") is False:
                wynik["uwagi"].append(f"{id_}: WSTRZYMANA BEZ DOSTARCZONEGO POWIADOMIENIA ({st['hold'].get('powod')})")
            wynik["postacie"][id_] = {"faza": st.get("faza"), "zmiana": zm and {k: zm[k] for k in ("od", "koniec", "wylog")},
                                      "nastepna": nast and nast["od"], "blok": self.bramka(id_), "hold": st.get("hold"), "spot": (st.get("spot") or {}).get("mapa"),
                                      "naprawy_w_oknie": len(self.naprawy_w_oknie(id_, teraz))}
        p = self.W / "logi" / f"nadzor-{teraz:%Y%m%d}.jsonl"
        try:
            wynik["ostatnie_decyzje"] = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()[-ile_decyzji:]]
        except (OSError, ValueError):
            wynik["ostatnie_decyzje"] = []
        return wynik


def blokada_przebiegu(czekaj_s=0.0):
    """Jeden przebieg (tick / napraw / odblokuj) naraz: flock na _wspolne/nadzor_przebieg.lock. -> otwarty plik albo None."""
    G.wspolne(KORZEN).mkdir(parents=True, exist_ok=True)
    f = open(G.wspolne(KORZEN) / "nadzor_przebieg.lock", "a")
    koniec = time.time() + czekaj_s
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return f
        except OSError:
            if time.time() >= koniec:
                f.close()
                return None
            time.sleep(0.5)


def wydruk(raport, nagl):
    print(nagl)
    if not raport:
        print("  (nic do zapisania: wszystko bez zmian względem poprzedniego przebiegu)")
    for r in raport:
        extra = f"  [{r['szczegol']}]" if r.get("szczegol") else ""
        print(f"  {r['t'][11:]} {r['id']:<11} {r['akcja']:<14} {r['wynik']:<10} {r['powod']}{extra}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nadzor.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cien")
    c.add_argument("--raz", action="store_true")
    sub.add_parser("tick")
    n = sub.add_parser("napraw")
    n.add_argument("id")
    n.add_argument("rodzaj")
    sub.add_parser("stan")
    b = sub.add_parser("odblokuj")
    b.add_argument("id")
    a = ap.parse_args(argv)
    zywo_plik = (G.wspolne(KORZEN) / "NADZOR_ZYWO").exists()
    if a.cmd == "cien" and a.raz:
        nz = Nadzorca(zywo=False, zapis=False, czysty=True)
        wydruk(nz.tick(), f"Nadzór (CIEŃ, tylko odczyt) {nz.zegar():%Y-%m-%d %H:%M:%S}")
        return 0
    if a.cmd == "stan":
        print(json.dumps(Nadzorca(zywo=False, zapis=False, czysty=False).podsumowanie(), ensure_ascii=False, indent=1))
        return 0
    zamek = blokada_przebiegu(20.0 if a.cmd in ("napraw", "odblokuj") else 0.0)
    if zamek is None:
        print("inny przebieg nadzoru trwa (blokada _wspolne/nadzor_przebieg.lock): pomijam", file=sys.stderr)
        return 0 if a.cmd in ("tick", "cien") else 3
    if a.cmd == "cien":
        nz = Nadzorca(zywo=False, zapis=True)
        wydruk(nz.tick(), f"Nadzór (CIEŃ) {nz.zegar():%Y-%m-%d %H:%M:%S}")
        return 0
    if a.cmd == "tick":
        nz = Nadzorca(zywo=zywo_plik)
        wydruk(nz.tick(), f"Nadzór ({'NA ŻYWO' if zywo_plik else 'CIEŃ'}) {nz.zegar():%Y-%m-%d %H:%M:%S}")
        return 0
    if a.cmd == "napraw":
        nz = Nadzorca(zywo=zywo_plik)
        kod, txt = nz.napraw(a.id, a.rodzaj)
        print(("NA ŻYWO: " if zywo_plik else "CIEŃ: ") + txt)
        return kod
    if a.cmd == "odblokuj":
        print(Nadzorca(zywo=False).odblokuj(a.id))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
