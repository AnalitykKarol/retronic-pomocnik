#!/usr/bin/env python3
"""Wykonawca nadzorcy zestawu (SPEC_nadzor_wykonawca_1021, F2 + biała lista napraw). Deterministyczny; model nie klika po grze.

  python3 -I nadzor.py cien [--raz]        jeden przebieg W CIENIU: tylko log "zrobiłbym X". --raz = tylko odczyt i wydruk, zero zapisów
  python3 -I nadzor.py tick                jeden przebieg (timer co ~1 min). Na żywo TYLKO gdy istnieje instancje/_wspolne/NADZOR_ZYWO
  python3 -I nadzor.py napraw <id> <rodzaj>   biała lista: restart | wznow | wroc | relog | wyloguj | zmien_spot | okna | wroc_poziom
  python3 -I nadzor.py stan                skrót dla obchodu (JSON): fazy, zmiany, naprawy, ostatnie decyzje
  python3 -I nadzor.py odblokuj <id>       zdejmuje wstrzymanie po eskalacji (polecenie Karola, NIE dla modelu)

Cykl postaci: OFFLINE -> LOGOWANIE -> DOJSCIE -> EXP -> POWROT (WROC) -> MIASTO (serwis, jeśli miasto ma) -> WYLOGOWANIE -> OFFLINE.
Blokady (przed każdą akcją): instancje/<id>/STOP_RECZNY, instancje/_wspolne/NADZOR_PAUZA, "nadzor": false w profil.json,
wstrzymanie po eskalacji. Jedna akcja logowania/wylogowania naraz (flock + jedna na tick), odstęp od poprzedniego zdarzenia.
Każda decyzja i akcja: instancje/_wspolne/logi/nadzor-RRRRMMDD.jsonl. Restart bota: mapa/tryb z tryb.log, nie z env.
Wybór spotu (Q5, SPEC_wybor_spotu_1021): przy starcie zmiany i przy zmien_spot z tabeli dane_tibia/spoty_nadzorca.json (spoty.py): miasto z pozycji,
poziom, jeden bot na jaskinię, lina/łopata, mieszanie między zmianami. Cień (cien --raz) pokazuje "spot_podglad" dla każdej postaci w grze.
Wyrósł ze spotu (23.10, Karol: „limit na Rooku to 8 lvl”): postać z botem na mapie, której widełki (poziom_zrodlo „karol”) kończą się poniżej BIEŻĄCEGO
poziomu z gry, dostaje WROC raz (stan `wroc_poziom`), jedno powiadomienie. Jedyna decyzja wykonywana na żywo także bez NADZOR_ZYWO, gdy włączone
NADZOR_NAPRAWY (env albo plik instancje/_wspolne/NADZOR_NAPRAWY) w `tick` i `napraw <id> wroc_poziom`; `cien` / `cien --raz` nigdy.
Plan postaci (23.10, Karol: „Wszystko powinien robić nadzorca, powinien mieć jakiś plan”): instancje/_wspolne/plan_postaci.json (plan_postaci.py,
NADZORCA.md „Plan postaci”): kroki `{warunek, akcja}` wykonywane RAZ przez kod; warunek `poziom >= N` w `tick` (poza walką, bramki jak wroc-poziom, na żywo
przy NADZOR_NAPRAWY, w cieniu tylko dziennik), `po_refillu` / `przy_nastepnym_starcie` przy starcie bota (uruchom.sh dla refilla, start/restart nadzorcy).
`spot_przypiety`: nadzorca nie przenosi postaci (start zmiany, zmien_spot, drabina napraw) bez wpisu Karola.
`zostan_w_depo` (23.10, Karol: invincible, dawajkesh, wydra): postać w depo ze STOP (bez bota, dowód depo: log „DEPO osiągnięte” albo panel `w_depo`) ZOSTAJE:
decyzja `czekaj` („zostaje-w-depo”), zero wznow/restart/serwis/relog/wylogowania/zmien_spot/startu z grafiku; offline lub rozłączona po
takim stanie (znacznik `zostan_depo_od` w stanie nadzorcy + STOP) też nie jest logowana. Poza depo (spot, droga) nadzorca działa jak dotąd.
24.10 (Karol: „invincible i dawajkesh mają zrobić po 2 bp UH-ów, zakończyć i wylogować się w depo”): `zostan_w_depo_po_refillach: N` uzbraja tę flagę
dopiero po N refillach od `zostan_w_depo_od` (licznik refille.json) ORAZ po starcie bota po N-tym refillu (w trakcie refillu postać stoi w depo ze STOP bez
bota i nie wolno jej wylogować); `wyloguj_w_depo: true` = uzbrojona postać w depo ze STOP jest wylogowywana (decyzja `wyloguj`, kod plan-wyloguj-depo: na żywo
przy NADZOR_NAPRAWY, bramki i odstęp logowań jak każde wylogowanie), potem znacznik + STOP trzymają ją offline (bez relogu). Reguła: zostan_depo.py.
24.10 (Karol: „nadzorca ma sam robić przerwy postaci i ewentualnie zmieniać spot”; SPEC_przerwa_postaci_1024): pole `przerwa` w planie postaci
({min, rozrzut_min, kiedy: po_refillu|teraz, zmien_spot: nie|jesli_gracz, gracz, powod}, jednorazowe). Refill pomija wyjście z miasta (refill_auto +
REFILL_BEZ_WYJSCIA), postać stoi w mieście ze STOP, nadzorca ją wylogowuje (kod plan-przerwa-wyloguj, zapis `wylogowano_t`/`do_t` w planie PRZED wylogowaniem),
po `do_t` loguje (plan-przerwa-powrot / plan-przerwa-zaloguj, jedna akcja logowania na przebieg, odstęp i cisza nocna jak zawsze) i startuje `refill.sh --spot`
(plan-przerwa-spot), po zmianie spotu, gdy przeszkadzał gracz. Wyłącznik: NADZOR_PRZERWY=0 albo „przerwy”: false w nadzor_konfig.json. Bez wpisu `przerwa`
zachowanie bez zmian.
Nigdy: czat gry, pokrętła ryzyka śmierci, STOP_RECZNY, zakładanie kont, handel."""
import argparse
import ast
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
import zlib
from datetime import datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True          # cień = zero zapisów (także __pycache__ importowanych modułów)
DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))
import grafik as G  # noqa: E402
import spoty as SP  # noqa: E402
import spot_gracz as SGR  # noqa: E402
import plan_postaci as PP  # noqa: E402
import przerwa as PR  # noqa: E402
import relog_wylogowanych as RW  # noqa: E402
import zostan_depo as ZD  # noqa: E402

KORZEN = Path(os.environ.get("RETRONIC_NADZOR_KORZEN") or DIR)
FMT = G.FMT
BIALA_LISTA = ("restart", "wznow", "wroc", "relog", "wyloguj", "zmien_spot", "okna", "wroc_poziom", "zamknij_sesje")
# 22.10: bez NADZOR_ZYWO (przy NADZOR_NAPRAWY) obchód wolno tylko ratować. 23.10 (Karol: „limit na Rooku to 8 lvl”): do tego `wroc_poziom` =
# powrót do miasta WYŁĄCZNIE z powodu „poziom > max spotu”; zwykłe `wroc`, `wyloguj` i `zmien_spot` nadal odmowa (kod 3)
NAPRAWY_BEZ_ZYWO = ("restart", "wznow", "relog", "okna", "wroc_poziom", "zamknij_sesje")
PLAN_PROBY = 3             # 23.10: tyle razy najwyżej próbuję wykonać krok planu, gdy skrypt zawodzi (sukces = raz i koniec)
WROC_POZIOM_PROBY = 3      # 23.10: tyle razy najwyżej próbuję zlecić wroc_poziom, gdy wroc.sh zawodzi (sukces = jedno zlecenie i koniec)
FAZY = ("OFFLINE", "LOGOWANIE", "DOJSCIE", "EXP", "POWROT", "MIASTO", "WYLOGOWANIE")
ZDARZENIA_LOGOWANIA = ("sesja_start", "wyloguj", "relog", "zamknij_sesje")     # 23.10: zamknięcie sesji też „jedna naraz, z odstępem”

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
# 22.10 okna po starcie: walka BEZ linii lootu (powtarzające się "Loot: brak_plecaka" to sam objaw, nie walka: inaczej naprawa okien
# byłaby odraczana w nieskończoność przez własny sygnał)
RE_WALKA_BEZ_LOOTU = re.compile(r"[Cc]el|WALKA|ATAK|POGO|UCIEC")
RE_BRAK_PLECAKA = re.compile(r"Loot: brak_plecaka|brak_plecaka \(zero lub kilka okien plecaka\)")
RE_BRAK_OKNA = re.compile(r"Loot: brak_okna|Loot w walce przerwany: brak_okna")
# 23.10 (strategia Karola, pkt 4/12): postać nie zna czaru zdrowia (odchyd: exura): bot po rzucie widzi, że ani HP, ani mana się nie zmieniły
RE_CZAR_PORAZKA = re.compile(r"ZDROWIE: po rzucie ani HP, ani mana się nie zmieniły.*porażka (\d+)/(\d+)")
RE_CZAR_RZUT = re.compile(r"\[ZDROWIE\] czar (\S+)")
CZAR_INFO_KARENCJA_S = 3 * 3600        # bot ponawia serię porażek co ~10 min; powiadomienie najwyżej raz na 3 h na postać
POKRETLO_RESTART_KOD = "NADZOR_RESTART_PO_KODZIE"      # 23.10: restart bota po zmianie jego kodu (domyślnie WYŁĄCZONE: decyzja Karola)
POKRETLO_ZAMYKAJ_SESJE = "NADZOR_ZAMYKAJ_SESJE"        # 23.10: zamykanie sesji wylogowanych postaci (domyślnie WYŁĄCZONE)
RESTART_KOD_MARGINES_S = 30            # plik nowszy od startu bota o mniej niż to = ten sam zapis co start
RESTART_KOD_PRZERWA_S = 120            # najmniejszy odstęp między dwoma restartami po zmianie kodu (różne postacie)
RESTART_KOD_PROBY = 3                  # tyle razy najwyżej próbuję restartu po tej samej zmianie kodu
OKNA_PROG = int(os.environ.get("NADZOR_OKNA_PROG", "5"))            # brak_plecaka w ostatnich 5 min, by zlecić kontrolę okien
OKNA_PROG_OKNA = int(os.environ.get("NADZOR_OKNA_PROG_OKNA", "15"))  # brak_okna (zwłoki) jest zwykły; dopiero seria to sygnał
OKNA_KARENCJA_S = 900                                                # najwyżej raz na 15 min na postać
WROC_CZEKAJ_MIN = 15       # 22.10: tyle czekam na efekt zleconego powrotu (koniec zmiany), potem jedna eskalacja i cisza (konf "wroc_czekaj_min")
POZIOM_MAX_WIEK_H = 24     # 22.10: najstarszy zapamiętany poziom, którego jeszcze używam przy braku bieżącego odczytu (konf "poziom_max_wiek_h")
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
         "pelny": 0, "cap": 0, "glod": 0, "walka": False, "walka_bez_lootu": False, "brak_plecaka": 0, "brak_okna": 0, "ost_linia": None,
         "czar_bez_efektu": None}
    czar = None
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
        m_czar = RE_CZAR_RZUT.search(l)
        if m_czar:
            czar = m_czar[1]
        m_por = RE_CZAR_PORAZKA.search(l)
        if m_por and int(m_por[1]) >= int(m_por[2]):      # dopiero ostatnia porażka serii (3/3) to sygnał „nie zna czaru”
            a["czar_bez_efektu"] = {"ts": t, "czar": czar or "?", "porazka": int(m_por[1]), "z": int(m_por[2])}
        if t >= teraz_ep - 300:
            a["brak_plecaka"] += bool(RE_BRAK_PLECAKA.search(l))
            a["brak_okna"] += bool(RE_BRAK_OKNA.search(l))
    # walka: któraś z linii z ostatnich 20 s
    a["walka"] = any(t >= teraz_ep - 20 and RE_WALKA.search(l) for t, l in linie[-40:])
    a["walka_bez_lootu"] = any(t >= teraz_ep - 20 and RE_WALKA_BEZ_LOOTU.search(l) for t, l in linie[-40:])
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
        # 22.10: poziom postaci ginął, bo strażnik nie mieścił się w limitach okna/paska (0.3 s na `gracz`, 1.5/1.9 s na panel i całość)
        # albo odczyt był wstrzymany znacznikiem gracz_brak. Nadzór nie ma budżetu paska (tick co 5 min): szersze limity i bez pauzy,
        # tylko dla tego wywołania (opt-in przez środowisko; okno i pasek zostają przy swoich).
        env = dict(os.environ, RETRONIC_PANEL_GRACZ_S="2.5", RETRONIC_PANEL_GRACZ_BEZ_PAUZY="1",
                   RETRONIC_OKNO_PANEL_LIMIT_S="5", RETRONIC_OKNO_CALOSC_LIMIT_S="8")
        r = subprocess.run([sys.executable, "-I", str(DIR / "okno_api.py"), "stan"], cwd=str(DIR), capture_output=True,
                           text=True, timeout=60, env=env)
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

    def blanki(self, id_):
        """Liczba blanków (UH) w otwartych kontenerach postaci albo None (brak odczytu, nic nie otwarte). Tylko odczyt pamięci gry (plan_postaci.py blanki)."""
        try:
            r = subprocess.run([sys.executable, "-I", str(DIR / "plan_postaci.py"), "blanki"], cwd=str(DIR), capture_output=True, text=True,
                               timeout=30, env=dict(os.environ, RETRONIC_ID=id_), stdin=subprocess.DEVNULL)
            w = json.loads((r.stdout or "").strip().splitlines()[-1]).get("blanki")
            return w if isinstance(w, int) and not isinstance(w, bool) else None
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            return None

    def telemetria(self, id_):
        import nadzor_stan  # noqa: PLC0415
        return nadzor_stan.przejrzyj_telemetrie(self.korzen / "instancje" / id_ / "logi", time.time())

    def procesy_serwisu(self, id_):
        import instancja  # noqa: PLC0415
        return instancja.procesy(r"(^|[ /])serwis\.py ", id_=id_)

    def procesy_refillu(self, id_):
        """25.10: refill tej instancji w toku (refill.sh albo czekacz auto-refillu): w jego trakcie postać w depo nie jest wylogowywana."""
        import instancja  # noqa: PLC0415
        return (instancja.procesy(r"(^|[ /])refill_auto\.py czekaj", id_=id_)
                + instancja.procesy(r"^(\S*/)?bash (\S*/)?refill\.sh *$", id_=id_, comm=None)         # wzorce jak refill_auto.WZOR_REFILL / refill.sh pidy_serwis_sh
                + instancja.procesy(r"^(\S*/)?bash (\S*/)?serwis\.sh( .*)?$", id_=id_, comm=None))

    def procesy_bota(self, id_):
        import instancja  # noqa: PLC0415
        return instancja.procesy(r"(mozg|cavebot)\.py", id_=id_)

    def bot_start_ts(self, id_):
        """Epoch startu NAJNOWSZEGO procesu bota tej instancji (z /proc/<pid>/stat) albo None (brak procesu / nieczytelne)."""
        try:
            btime = next(int(l.split()[1]) for l in Path("/proc/stat").read_text().splitlines() if l.startswith("btime "))
            tiki = os.sysconf("SC_CLK_TCK")
            starty = []
            for pid in self.procesy_bota(id_):
                pole = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
                starty.append(btime + int(pole[19]) / tiki)       # pole 22 (starttime) po usunięciu pid i comm
            return max(starty) if starty else None
        except (OSError, ValueError, IndexError, StopIteration, ImportError):
            return None


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
    def relog_kolejka(self, id_): return self._w("relog_kolejka", id_)
    def powiadom(self, id_, tytul, tresc): return self._w("powiadom", id_, tytul, tresc)
    def powiadom_info(self, id_, tytul, tresc): return self._w("powiadom_info", id_, tytul, tresc)
    def okna(self, id_): return self._w("okna", id_)
    def zamknij_sesje(self, id_): return self._w("zamknij_sesje", id_)
    def refill_spot(self, id_, mapa=None, tryb=None): return self._w("refill_spot", id_, mapa, tryb)


class WykonawcaZywy:
    """Uruchamia istniejące skrypty przez interfejs poleceń. Brak narzędzia = (False, "brak ..."), nigdy wyjątek."""
    zywy = True

    def __init__(self, korzen):
        self.korzen = Path(korzen)

    def _env(self, id_):
        e = dict(os.environ)
        e["RETRONIC_ID"] = id_
        return e

    def _uruchom(self, argv, id_, limit, odlacz=False, env_dod=None):
        try:
            env = {**self._env(id_), **(env_dod or {})}
            if odlacz:
                subprocess.Popen([str(a) for a in argv], cwd=str(DIR), env=env, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                return True, "uruchomiono w tle"
            r = subprocess.run([str(a) for a in argv], cwd=str(DIR), env=env, capture_output=True, text=True,
                               timeout=limit, stdin=subprocess.DEVNULL)
            wyj = " | ".join((r.stdout + r.stderr).strip().splitlines()[-3:])
            return r.returncode == 0, f"kod {r.returncode}: {wyj}"[:300]
        except subprocess.TimeoutExpired:
            return False, f"przekroczony limit {limit} s"
        except OSError as e:
            return False, str(e)

    def _skrypt(self, nazwa, id_, limit, argv_dod=(), odlacz=False, env_dod=None):
        p = DIR / nazwa
        if not p.exists():
            return False, f"brak narzędzia {nazwa}"
        return self._uruchom([p, *argv_dod], id_, limit, odlacz, env_dod)

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

    def refill_spot(self, id_, mapa=None, tryb=None):
        """24.10 (przerwa postaci): `refill.sh --spot` = BEZ zakupów, tylko wyjście z miasta i start bota. Praca idzie odłączona (setsid), wywołanie wraca od razu.
        Zmiana spotu: MAPA/TRYB w env wygrywają z ostatni_start (uruchom.sh); bez nich bot rusza na ostatniej mapie i trybie."""
        env = {"MAPA": mapa, "TRYB": tryb or ""} if mapa else None
        return self._skrypt("refill.sh", id_, 30, ["--spot"], env_dod=env)

    def okna(self, id_):
        """Kontrola okien po starcie (okna_start.py): zwiń minimapę / otwórz plecak, gdy pokrętło naprawy włączone, inaczej tylko
        powiadomienie. Kod 0 = ok/naprawione, 1 = wymaga człowieka (powiadomione), 3 = odroczone, 4 = brak odczytu."""
        return self._uruchom([sys.executable, "-I", DIR / "okna_start.py", "napraw"], id_, 90)

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

    def zamknij_sesje(self, id_):
        """23.10 (Karol 17:05: „niech pozamyka sesje”): `sesja_gry.py zamknij` dla postaci na ekranie logowania / liście postaci, bez bota.
        Zatrzymuje wyłącznie procesy tej instancji (sway, klient, proxy); bota nie ma, gra nie biegnie. Powrót: sesja_gry.py start + zaloguj.sh."""
        return self._uruchom([sys.executable, "-I", DIR / "sesja_gry.py", "zamknij"], id_, 120)

    def relog_kolejka(self, id_):
        """23.10: bot wylogował się sam (wylogowany.json): kolejka relogów (relog_wylogowanych.py) jako osobny proces, bo relog trwa
        kilkanaście minut. Kolejka bierze WSZYSTKIE gotowe postacie pojedynczo, z przerwą 3-6 min; drugi start = no-op (singleton)."""
        return RW.uruchom_kolejke_w_tle(self.korzen)

    def powiadom(self, id_, tytul, tresc):
        try:
            import powiadom  # noqa: PLC0415
            poszlo = powiadom.powiadom(tytul, tresc, "critical", klucz=f"nadzor-{id_}-{tytul}")
            return bool(poszlo), "powiadomienie wysłane" if poszlo else "powiadomienie wyciszone (plik cisza / limit)"
        except Exception as e:      # noqa: BLE001
            return False, f"powiadomienie: {e!r}"

    def powiadom_info(self, id_, tytul, tresc):
        """Zwykłe (nie critical, bez głosu) powiadomienie o decyzji nadzorcy, która nie jest alarmem (23.10: wyrósł ze spotu).
        Klucz zaczyna się od „stop” (powiadom.ZAWSZE): nie-critical bez takiego prefiksu jest tam wyciszany."""
        try:
            import powiadom  # noqa: PLC0415
            poszlo = powiadom.powiadom(tytul, tresc, "normal", klucz=f"stop-nadzor-{id_}-{tytul}")
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
def stoj_wlaczony(korzen, id_):
    """True, gdy instancja ma plik-flagę STOJ (stoj.py, 23.10). Błąd odczytu = False (zwykłe zasady). Funkcja modułowa, nie metoda:
    `zaciecie` bywa wołane na atrapie obiektu (testy)."""
    try:
        return (Path(korzen) / "instancje" / id_ / "STOJ").exists()
    except OSError:
        return False


class Nadzorca:
    def __init__(self, korzen=None, zegar=None, zrodla=None, wykonawca=None, zywo=False, zapis=True, czysty=None,
                 naprawy_poziom=False, wykonawca_poziom=None):
        self.korzen = Path(korzen or KORZEN)
        self.zegar = zegar or (lambda: datetime.now().replace(microsecond=0))
        self.zrodla = zrodla or Zrodla(self.korzen)
        self.zywo = self.zywo_zadane = zywo
        self.wykonawca = wykonawca or (WykonawcaZywy(self.korzen) if zywo else WykonawcaCien())
        # 23.10: NADZOR_NAPRAWY + `tick`/`napraw` = na żywo TYLKO decyzja wroc_poziom (wyrósł ze spotu), reszta (grafik) zostaje w cieniu.
        # `cien` / `cien --raz` nigdy tego nie ustawiają (okno obchodu eksportuje NADZOR_NAPRAWY=1 także dla przebiegu w cieniu).
        self.naprawy_poziom = bool(naprawy_poziom) and not zywo
        self._wykonawca_poziom = wykonawca_poziom
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
        self._poziom_z_pamieci = {}     # id -> (poziom, data odczytu), gdy w tym przebiegu użyto zapamiętanego poziomu zamiast bieżącego
        self._plan = None               # plan_postaci.json wczytany raz na przebieg (tick / napraw)
        self._kod_bota = None           # 23.10: pliki kodu bota (domknięcie importów mozg.py/cavebot.py), raz na przebieg
        self._restart_kod_w_przebiegu = False
        self._plan_czeka = []           # (id, decyzja czekaj) kroków planu, które czekają: wpis do dziennika bez blokowania reszty decyzji

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
        poza = G.poza_nadzorem(self.profil(id_), self.konf.get("postacie", {}).get(id_), self.zegar())
        if poza:
            return poza
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
        o["refill_trwa"] = False       # 25.10: refill.sh / czekacz auto-refillu tej instancji (tylko postać bez bota; brak metody w atrapie = False)
        if o["online"] and not o["bot"] and self.zostan_depo_pc(id_):
            try:
                o["refill_trwa"] = bool(self.zrodla.procesy_refillu(id_))
            except Exception:       # noqa: BLE001
                o["refill_trwa"] = False
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
        luz = int(self.konf["przerwa_min"][0])
        if online and st.get("zmiana_od"):
            for z in G.zmiany_postaci(plan, id_):
                if z["od"] == st["zmiana_od"]:
                    # 22.10: przypięcie wygasa, gdy okno tej zmiany (wylog + luz) minęło, a trwa już inna (wydra: pin 08:50-11:13 do 16:37,
                    # kolejna zmiana 13:30-16:10 ignorowana). Gdy innej aktywnej nie ma, przypięcie zostaje (koniec zmiany nadal obowiązuje).
                    if teraz >= datetime.strptime(z["wylog"], FMT) + timedelta(minutes=luz):
                        nowa = G.aktywna_zmiana(plan, id_, teraz, luz_min=luz)
                        if nowa and nowa["od"] != z["od"]:
                            st["zmiana_od"] = nowa["od"]
                            return nowa
                    return z
        if online:
            z = G.aktywna_zmiana(plan, id_, teraz, luz_min=luz)
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

    def _decyzja_konca(self, id_, st, zm, koniec, teraz):
        """22.10 (dziennik wydry: `wroc` z powodem „koniec zmiany (11:13)” 28 razy w 5 h): koniec zmiany zleca powrót RAZ. Dalej: czekam na efekt
        (wroc_czekaj_min), potem jedna eskalacja „nieustalony” (bez wstrzymania) i cisza, aż zmieni się sytuacja (bot stanął, wylogowanie,
        przejęcie przez Karola, następna zmiana). Zlecenie ma tryb (cień/żywo): to z cienia nie tłumi prawdziwego `wroc` po włączeniu NADZOR_ZYWO."""
        w = st.get("wroc_koniec")
        if not (w and w.get("tryb") == ("zywo" if self.zywo else "cien") and w.get("zmiana") == (zm or {}).get("od")):
            return [D(id_, "wroc", koniec[1] + ": zlecam powrót do miasta", "koniec-" + koniec[0], klasa="naprawa", problem="koniec",
                      zm=(zm or {}).get("od"), powod_konca=koniec[1])]
        o_ktorej = datetime.fromtimestamp(w["ts"]).strftime("%H:%M")
        wiek_min = (ts_ep(teraz) - w["ts"]) / 60
        if wiek_min < float(self.konf.get("wroc_czekaj_min", WROC_CZEKAJ_MIN)):
            return [D(id_, "czekaj", f"powrót zlecony o {o_ktorej} ({w['powod']}): czekam na efekt", "wroc-zlecony")]
        if not w.get("eskalowano"):
            return [D(id_, "eskaluj", f"powrót do miasta zlecony o {o_ktorej} ({w['powod']}), bez efektu po {int(wiek_min)} min: bot nadal działa, nie ponawiam",
                      "wroc-bez-efektu", klasa="eskalacja", kod_eskalacji="nieustalony", wroc_koniec=True)]
        return [D(id_, "czekaj", f"powrót zlecony o {o_ktorej}, bez efektu; Karol powiadomiony, nie ponawiam", "wroc-bez-efektu")]

    def _zapisz_wroc_koniec(self, st, d, teraz):
        if d["akcja"] == "wroc" and d["arg"].get("problem") == "koniec":
            st["wroc_koniec"] = {"tryb": "zywo" if self.zywo else "cien", "zmiana": d["arg"].get("zm"), "ts": ts_ep(teraz),
                                 "powod": d["arg"].get("powod_konca") or d["powod"]}

    # --- wyrósł ze spotu (23.10, Karol: „limit na Rooku to 8 lvl, jak wbije 8 lvl to niech wraca do miasta”) ---
    def poziom_zywo(self):
        """True, gdy decyzja wroc_poziom jest wykonywana NAPRAWDĘ: tryb na żywo albo NADZOR_NAPRAWY (tick/napraw). Tak jak B-1 dla eskalacji:
        przy wyciszonych powiadomieniach (plik cisza) postać nie wraca po cichu bez wiedzy Karola, zostaje wpis w cieniu."""
        return bool(self.zywo or (self.naprawy_poziom and not self.powiadomienia_wylaczone()))

    # --- strategia 23.10 (Karol): pokrętła, restart po zmianie kodu, zamknięcie sesji, czar bez efektu ---
    def pokretlo(self, nazwa):
        """Pokrętło nadzorcy: zmienna środowiska =1 albo plik instancje/_wspolne/<nazwa>. Domyślnie WYŁĄCZONE."""
        return os.environ.get(nazwa) == "1" or (self.W / nazwa).exists()

    def kod_bota(self):
        """Ścieżki plików .py w korzeniu, które bot ładuje: domknięcie lokalnych importów od mozg.py i cavebot.py (ast, bez uruchamiania).
        Jeden raz na przebieg. Zmiana pliku spoza tego zbioru (nadzor.py, testy, okno_api...) nie jest powodem restartu bota."""
        if self._kod_bota is None:
            korzenie = ("mozg", "cavebot")
            wynik, kolejka = set(), list(korzenie)
            while kolejka:
                nazwa = kolejka.pop()
                plik = self.korzen / f"{nazwa}.py"
                if nazwa in wynik or not plik.is_file():
                    continue
                wynik.add(nazwa)
                try:
                    drzewo = ast.parse(plik.read_text(encoding="utf-8", errors="replace"))
                except (OSError, SyntaxError, ValueError):
                    continue
                # korzenie (mozg, cavebot): wszystkie importy, także leniwe w funkcjach (loot, uh, zwiecha, zatrucie... ładują się w trakcie pracy bota).
                # Dalej tylko importy poziomu modułu (też w if/try): leniwe importy narzędzi (nadzor.py, grafik.py...) dociągnęłyby pół repo
                # i każda edycja narzędzia restartowałaby boty
                if nazwa in korzenie:
                    wezly = list(ast.walk(drzewo))
                else:
                    wezly, stos = [], list(drzewo.body)
                    while stos:
                        w = stos.pop()
                        wezly.append(w)
                        if isinstance(w, (ast.If, ast.Try, ast.With)):
                            for pole in ("body", "orelse", "finalbody"):
                                stos.extend(getattr(w, pole, []) or [])
                            stos.extend(h for hh in getattr(w, "handlers", []) for h in hh.body)
                for w in wezly:
                    if isinstance(w, ast.Import):
                        kolejka.extend(x.name.split(".")[0] for x in w.names)
                    elif isinstance(w, ast.ImportFrom) and w.module and not w.level:
                        kolejka.append(w.module.split(".")[0])
            self._kod_bota = sorted(self.korzen / f"{n}.py" for n in wynik)
        return self._kod_bota

    def kod_nowszy_niz_start(self, id_, o, a):
        """(nazwa_pliku, mtime) najnowszego pliku kodu bota nowszego niż START bota, inaczej None. Start = późniejszy z: proces (zrodla.bot_start_ts)
        i ostatnia linia `Mózg:` w logu. Brak ustalonego startu = nie wiem, nie restartuję."""
        fn = getattr(self.zrodla, "bot_start_ts", None)
        try:
            start = fn(id_) if fn else None
        except Exception:       # noqa: BLE001
            start = None
        if not start:
            return None
        start = max(start, a.get("start") or 0)
        najnowszy = None
        for p in self.kod_bota():
            try:
                m = p.stat().st_mtime
            except OSError:
                continue
            if m > start + RESTART_KOD_MARGINES_S and (najnowszy is None or m > najnowszy[1]):
                najnowszy = (p.name, m)
        return najnowszy

    def decyzja_restart_kod(self, id_, o, a, st, teraz):
        """Restart bota po zmianie jego kodu (strategia Karola pkt 1): tylko przy pokrętle NADZOR_RESTART_PO_KODZIE, nie w walce, nie w trakcie powrotu,
        JEDNA postać na przebieg i >= RESTART_KOD_PRZERWA_S po poprzednim restarcie. STOP_RECZNY, nadzor:false, pauza i hold odrzuca bramka;
        postać w depo ze STOP (zostan_w_depo) nie ma bota, więc tu nie trafia. Nie zużywa drabiny napraw."""
        if not self.pokretlo(POKRETLO_RESTART_KOD) or not o["bot"]:
            return None
        n = self.kod_nowszy_niz_start(id_, o, a)
        if n is None:
            return None
        plik, mt = n
        powod = f"kod bota zmieniony ({plik} {datetime.fromtimestamp(mt):%H:%M}) po starcie bota"
        if o["wroc"] or o["wyprawa"] or o["stop"]:
            return D(id_, "czekaj", f"{powod}: bot wraca do miasta / stoi (STOP), restart po zakończeniu", "restart-kod-odroczony")
        if a.get("walka"):
            return D(id_, "czekaj", f"{powod}, ale bot w walce: restart w następnym przebiegu", "restart-kod-walka")
        pr = st.get("restart_kod") or {}
        if pr.get("mtime") == mt and pr.get("proby", 0) >= RESTART_KOD_PROBY:
            return D(id_, "czekaj", f"{powod}: restart nieudany {pr['proby']} razy, nie ponawiam (do następnej zmiany kodu)", "restart-kod-wyczerpany")
        ost = self.stan["globalne"].get("ostatni_restart_kod", 0)
        if self._restart_kod_w_przebiegu or ts_ep(teraz) - ost < RESTART_KOD_PRZERWA_S:
            return D(id_, "czekaj", f"{powod}: kolej tej postaci w następnym przebiegu (jeden restart naraz, przerwa >= {RESTART_KOD_PRZERWA_S} s)",
                     "restart-kod-kolejka")
        self._restart_kod_w_przebiegu = True
        return D(id_, "restart", powod + ": restart (poza walką, jedna postać naraz)", "restart-kod", klasa="naprawa", problem="kod",
                 mtime=mt)

    def decyzja_czar(self, id_, a, st, teraz):
        """Powiadomienie (nie naprawa, nie eskalacja, bez wstrzymania): bot zgłosił 3/3 „po rzucie ani HP, ani mana się nie zmieniły” = postać
        najpewniej nie zna czaru zdrowia (odchyd: exura, 23.10). Nadzorca NIE zmienia pokręteł bota (tryb.py przy starcie i tak je scala)."""
        c = a.get("czar_bez_efektu")
        if not c or ts_ep(teraz) - c["ts"] > 20 * 60:
            return None
        if ts_ep(teraz) - st.get("czar_info_ts", 0) < CZAR_INFO_KARENCJA_S:
            return None
        return D(id_, "powiadom_info", f"czar {c['czar']} bez efektu {c['porazka']}/{c['z']}: postać najpewniej nie zna tego czaru", "czar-bez-efektu",
                 klasa="naprawa", czar=c["czar"], nick=self.profil(id_).get("postac") or id_)

    def decyzja_zamknij_sesje(self, id_, o, zm):
        """Zamknięcie sesji postaci wylogowanej (strategia Karola, 17:05): sesja jest, klient na ekranie logowania / liście postaci, bota brak, a w
        grafiku nie ma teraz jej zmiany (w trakcie zmiany to rozłączenie: relog jak dotąd). Tylko przy pokrętle NADZOR_ZAMYKAJ_SESJE. Ekran śmierci
        to eskalacja do Karola, nie zamykanie; STOP_RECZNY odrzuca bramka (Karol gra)."""
        if zm is not None or o["bot"] or o["ekran"] not in ("lista", "logowanie") or not self.pokretlo(POKRETLO_ZAMYKAJ_SESJE):
            return None
        return D(id_, "zamknij_sesje", f"wylogowana (ekran: {o['ekran']}), bota brak, poza zmianą: zamykam sesję klienta (jedna naraz)", "zamknij-sesje",
                 klasa="zdarzenie")

    # --- zmiana spotu po 3. spotkaniu tego samego gracza (26.10, Karol; spot_gracz.py, dane_tibia/SPEC_spot_gracz_1026.md) ---
    def pokretlo_spot_gracz(self, id_):
        """SPOT_ZMIANA_PRZY_GRACZU == 1 w instancje/<id>/na_zywo.json (plik pokręteł bota). Brak pliku/klucza/zły typ = wyłączone."""
        try:
            v = json.loads((self.kat(id_) / "na_zywo.json").read_text(encoding="utf-8")).get("SPOT_ZMIANA_PRZY_GRACZU", 0)
        except (OSError, ValueError, AttributeError):
            return False
        return v == 1 and not isinstance(v, bool)

    def pokretlo_licznik_od_startu(self, id_):
        """LICZNIK_OD_STARTU w instancje/<id>/na_zywo.json: brak klucza = domyślnie 1 (licznik spotkań żyje w jednej sesji bota); 0 = stare zachowanie."""
        try:
            v = json.loads((self.kat(id_) / "na_zywo.json").read_text(encoding="utf-8")).get("LICZNIK_OD_STARTU", 1)
        except (OSError, ValueError, AttributeError):
            return True
        return not (v == 0 and not isinstance(v, bool))

    def pokretlo_spot_powrot(self, id_):
        """SPOT_GRACZ_POWROT_DO_MIASTA w instancje/<id>/na_zywo.json: brak klucza = domyślnie 1 (powrót do miasta, gdy nie ma wolnego spotu); 0 = postać zostaje."""
        try:
            v = json.loads((self.kat(id_) / "na_zywo.json").read_text(encoding="utf-8")).get("SPOT_GRACZ_POWROT_DO_MIASTA", 1)
        except (OSError, ValueError, AttributeError):
            return True
        return not (v == 0 and not isinstance(v, bool))

    def _spot_gracz_marker_sprzataj(self, id_):
        """Bot działa i wystartował PO zapisie znacznika powrotu (Karol albo plan podjął decyzję): znacznik już nie trzyma postaci w depo."""
        p = self.kat(id_) / ZD.PLIK_SPOT_GRACZ_DEPO
        if p.exists() and not ZD.spot_gracz_depo(self.kat(id_), self.zegar().timestamp(), self.start_bota_ep(id_)):
            ZD.usun_spot_gracz_depo(self.kat(id_))

    def spot_gracz_stan(self, id_):
        return self.post(id_).setdefault("spot_gracz", {})

    def wybierz_spot_gracz(self, id_, o, teraz, biezaca):
        """Nowy spot dla postaci, której gracz przeszkadza: spoty.wybierz z kolejnością Karola 26.10 (najpierw ta sama rodzina, potem reszta miasta),
        bez bieżącego, niedawno unikanych i spotów zakazanych (SPOTY_ZAKAZANE + `auto:false` w tabeli), bez jaskiń zajętych przez inne nasze boty.
        -> wynik spoty.wybierz (mapa None = brak) albo None, gdy tabeli spotów brak."""
        sg = self.spot_gracz_stan(id_)
        unikane = [u["mapa"] for u in SGR.unikane_aktywne(sg.get("unikane"), ts_ep(teraz))]
        wyklucz = {biezaca, *unikane, *SGR.SPOTY_ZAKAZANE} - {None}
        return self.wybierz_spot(id_, o.get("panel"), o.get("gracz"), teraz, biezaca, f"spot_gracz-{teraz:%H%M}", wyklucz_mapy=tuple(sorted(wyklucz)),
                                 rodzina_z=biezaca)

    def decyzja_spot_gracz(self, id_, o, a, st, teraz):
        """Zlecenie bota (`spot_gracz_zadanie.json`, bot z SPOT_ZMIANA_PRZY_GRACZU=1) -> decyzja `zmien_spot` (kod spot-gracz) albo `czekaj` z powodem
        albo None (brak zlecenia). Bramki: pokrętło w na_zywo.json instancji, spot przypięty, limity 1/30 min i 4/dobę (liczone z WYKONANYCH zmian),
        bot nie w walce, potwierdzenie spokoju od bota nie starsze niż GOTOWY_SWIEZY_S. Brak sensownego spotu = zlecenie kasowane, postać zostaje."""
        self._spot_gracz_marker_sprzataj(id_)
        zad, powod = SGR.wczytaj_zadanie(self.kat(id_), ts_ep(teraz))
        if zad is None:
            if powod != "brak zlecenia":
                SGR.usun_zadanie(self.kat(id_))          # przeterminowane / nieczytelne: sprzątamy (plik zlecenia jest jednorazowy)
            return None
        nick, ile = str(zad["nick"]).strip(), zad.get("spotkan", "?")
        if self.pokretlo_licznik_od_startu(id_) and SGR.zadanie_sprzed_startu(zad, self.start_bota_ep(id_)):
            SGR.usun_zadanie(self.kat(id_))            # 26.10 (Karol): licznik liczy od ostatniego odpalenia bota; zlecenie sprzed tego startu opiera się na wyzerowanym liczniku
            return D(id_, "czekaj", f"gracz {nick} ({ile}. spotkanie): zlecenie z poprzedniej sesji bota (bot wystartował po jego zapisie), wygasło", "spot-gracz-stara-sesja")
        if not self.pokretlo_spot_gracz(id_):
            SGR.usun_zadanie(self.kat(id_))
            return D(id_, "czekaj", f"gracz {nick}: SPOT_ZMIANA_PRZY_GRACZU wyłączone w na_zywo.json, zlecenie bota wycofane", "spot-gracz-wylaczone")
        sg = self.spot_gracz_stan(id_)
        ok, lim = SGR.limit_ok(sg.get("zmiany"), ts_ep(teraz))
        if not ok:
            SGR.usun_zadanie(self.kat(id_))
            return D(id_, "czekaj", f"gracz {nick} ({ile}. spotkanie): zmiana spotu odłożona, {lim}; zostaje", "spot-gracz-limit")
        pin = self.spot_przypiety(id_)
        if pin:
            SGR.usun_zadanie(self.kat(id_))
            return D(id_, "czekaj", f"gracz {nick} ({ile}. spotkanie): spot przypięty ({pin}), zostaje", "spot-gracz-przypiety")
        if o["log"] and a.get("walka"):
            return D(id_, "czekaj", f"gracz {nick} ({ile}. spotkanie): bot w walce, zmiana spotu czeka na spokój", "spot-gracz-walka")
        if not SGR.gotowe(zad, ts_ep(teraz)):
            return D(id_, "czekaj", f"gracz {nick} ({ile}. spotkanie): czekam na potwierdzenie spokoju od bota (HP >= {SGR.BEZPIECZNY_HP:.0f} %, zero potworów w "
                                    f"<= {SGR.BEZPIECZNY_ODL} polach, gotowy_t nie starszy niż {SGR.GOTOWY_SWIEZY_S} s)", "spot-gracz-czeka")
        prob = sg.get("proby") or {}
        if prob.get("t") == zad["t"] and prob.get("n", 0) >= 3:
            SGR.usun_zadanie(self.kat(id_))
            return D(id_, "czekaj", f"gracz {nick}: zmiana spotu nieudana {prob['n']} razy, zlecenie wycofane", "spot-gracz-nieudana")
        mapa, tryb, _skad = mapa_tryb_biezace(self.korzen, id_, teraz)
        if not mapa:
            return D(id_, "czekaj", f"gracz {nick}: bieżącej mapy nie ustalam (tryb.log), zostaje", "spot-gracz-brak-mapy")
        brak_spotu = False          # True = ustalone, że NIE MA dopuszczalnego spotu (nie: brak danych); wtedy ostatni szczebel to powrót do miasta
        if self.profil(id_).get("spoty_zapasowe"):
            s = self.spot_zapasowy(id_, mapa, self._zajete_mapy(id_))
            nowa, nowy_tryb, jak = (s[0], s[1] or tryb, "spot zapasowy z profil.json") if s else (None, None, "brak spotu zapasowego w profil.json")
            brak_spotu = not s
        else:
            w = self.wybierz_spot_gracz(id_, o, teraz, mapa)
            if w and w.get("mapa"):
                nowa, nowy_tryb, jak = w["mapa"], tryb, w["powod"]
            else:
                nowa, nowy_tryb, jak = None, None, (w or {}).get("powod", "brak tabeli spotów")
                brak_spotu = bool(w) and w.get("brak") == "spot" and str(jak).startswith("brak spotu")
        if not nowa or nowa == mapa:
            if brak_spotu and self.pokretlo_spot_powrot(id_):
                # 26.10 (Karol): ostatnia faza drabiny = powrót do miasta (to samo WROC co wroc.sh, bot idzie do depo w spokojnej chwili, postać zostaje w depo)
                return D(id_, "wroc", f"gracz {nick} spotkany {ile}. raz na {mapa}: brak wolnego spotu -> powrót do miasta ({jak})"[:500], "spot-gracz-powrot",
                         klasa="naprawa", problem="spot_gracz_wroc", stara=mapa, nick=nick, spotkan=ile, req_t=zad["t"])
            SGR.usun_zadanie(self.kat(id_))
            return D(id_, "czekaj", f"gracz {nick} ({ile}. spotkanie) na {mapa}: brak sensownego spotu, zostaje ({jak})"[:400], "spot-gracz-brak")
        return D(id_, "zmien_spot", f"gracz {nick} spotkany {ile}. raz na {mapa}: zmiana spotu -> {nowa} ({jak})"[:500], "spot-gracz", klasa="naprawa",
                 problem="spot_gracz", mapa=nowa, tryb=nowy_tryb, stara=mapa, nick=nick, spotkan=ile, req_t=zad["t"])

    def _spot_gracz_po(self, teraz, id_, d, st, ok, txt, W):
        """Po próbie zmiany spotu: sukces = wpis w liście wykonanych zmian (limity), unikany spot, skasowane zlecenie, powiadomienie (jedna krótka
        linia: nick, licznik, stary -> nowy); porażka = licznik prób (3 = wycofanie), bez prób przy odroczeniu z powodu walki."""
        arg, sg = d["arg"], self.spot_gracz_stan(id_)
        if ok and arg.get("problem") == "spot_gracz_wroc":
            tab = self.tabela_spotow()
            jask = tab.jaskinia_mapy(arg["stara"]) if tab is not None and not tab.blad else arg["stara"]
            sg["zmiany"] = [t for t in (sg.get("zmiany") or []) if ts_ep(teraz) - t < SGR.LIMIT_DOBA_S] + [ts_ep(teraz)]
            sg["unikane"] = SGR.unikane_dodaj(sg.get("unikane"), arg["stara"], jask, arg["nick"], ts_ep(teraz))
            sg.pop("proby", None)
            SGR.usun_zadanie(self.kat(id_))
            ZD.zapisz_spot_gracz_depo(self.kat(id_), ts_ep(teraz), f"powrót do miasta: gracz {arg['nick']} ({arg['spotkan']}. spotkanie) na {arg['stara']}, brak wolnego spotu")
            W.powiadom_info(id_, f"{id_}: brak wolnego spotu"[:80], f"{arg['nick']} spotkany {arg['spotkan']}. raz na {arg['stara']}: brak wolnego spotu -> powrót do miasta"[:300])
        elif ok:
            tab = self.tabela_spotow()
            jask = tab.jaskinia_mapy(arg["stara"]) if tab is not None and not tab.blad else arg["stara"]
            sg["zmiany"] = [t for t in (sg.get("zmiany") or []) if ts_ep(teraz) - t < SGR.LIMIT_DOBA_S] + [ts_ep(teraz)]
            sg["unikane"] = SGR.unikane_dodaj(sg.get("unikane"), arg["stara"], jask, arg["nick"], ts_ep(teraz))
            sg.pop("proby", None)
            SGR.usun_zadanie(self.kat(id_))
            W.powiadom_info(id_, f"{id_}: zmiana spotu"[:80], f"{arg['nick']} spotkany {arg['spotkan']}. raz: {arg['stara']} -> {arg['mapa']}"[:300])
        elif not str(txt).startswith("bot w walce"):
            pr = sg.get("proby") or {}
            sg["proby"] = {"t": arg["req_t"], "n": (pr.get("n", 0) + 1) if pr.get("t") == arg["req_t"] else 1}

    def _wykonawca_dla(self, d):
        # 23.10: na żywo przy NADZOR_NAPRAWY także kroki planu postaci (kod plan-*), z tymi samymi bramkami co wroc-poziom
        # 23.10: także relog po wylogowaniu bota (kod relog-wylog): kolejka relogów na żywo przy NADZOR_NAPRAWY, bramki jak wyżej
        # 23.10 (strategia Karola): tak samo restart po zmianie kodu, zamknięcie sesji i powiadomienie „czar bez efektu”; decyzje restart-kod
        # i zamknij-sesje powstają WYŁĄCZNIE przy włączonym pokrętle (pliki NADZOR_RESTART_PO_KODZIE / NADZOR_ZAMYKAJ_SESJE: domyślnie ich nie ma)
        if self.zywo or not ((d["akcja"] == "wroc" and d["kod"] == "wroc-poziom" or str(d["kod"]).startswith("plan-")
                              or d["kod"] in ("relog-wylog", "restart-kod", "zamknij-sesje", "czar-bez-efektu", "spot-gracz", "spot-gracz-powrot")) and self.poziom_zywo()):
            return self.wykonawca
        if self._wykonawca_poziom is None:
            self._wykonawca_poziom = WykonawcaZywy(self.korzen)
        return self._wykonawca_poziom

    def wyrosl_ze_spotu(self, id_, o, teraz):
        """(mapa, poziom, max) gdy postać z działającym botem na mapie ze spotu, którego widełki karolowe (poziom_zrodlo „karol”) kończą się poniżej
        BIEŻĄCEGO poziomu odczytanego z gry (nie zapamiętanego), inaczej None. Widełki „domyslne” to szacunek wg potworów, nie decyzja Karola:
        nie odsyłają postaci do miasta."""
        tab = self.tabela_spotow()
        if tab is None or tab.blad or not o.get("bot"):
            return None
        poziom = self.poziom_z_odczytu(o.get("gracz"), o.get("panel"))
        if poziom is None:
            return None
        try:
            mapa = mapa_tryb_biezace(self.korzen, id_, teraz)[0]
        except Exception:       # noqa: BLE001
            return None
        spot = tab.spoty.get(mapa) if mapa else None
        if spot is None or spot.poziom_zrodlo != "karol" or not spot.poziom:
            return None
        maks = spot.poziom[1]
        return (mapa, poziom, maks) if poziom > maks else None

    def _zlecone_poziom(self, st, mapa):
        """Zapis wcześniejszego zlecenia wroc_poziom dla tej mapy i tego trybu wykonania (cień nie tłumi żywego), jeśli wyczerpuje zlecanie."""
        z = st.get("wroc_poziom")
        tryb = "zywo" if self.poziom_zywo() else "cien"
        if z and z.get("mapa") == mapa and z.get("tryb") == tryb and (z.get("ok") or z.get("proby", 1) >= WROC_POZIOM_PROBY):
            return z
        return None

    def decyzja_wyrosl(self, id_, o, a, st, teraz):
        """Decyzja „wyrósł ze spotu” albo None. Zlecenie RAZ (stan `wroc_poziom`), nie w walce. Wyjątki (STOP_RECZNY, pauza, hold, nadzor:false)
        odrzuca bramka przed decyduj; powrót w toku i serwis odrzuca kolejność w decyduj."""
        w = self.wyrosl_ze_spotu(id_, o, teraz)
        if w is None:
            return None
        mapa, poziom, maks = w
        powod = f"poziom {poziom} > max {maks} spotu {mapa}"
        z = self._zlecone_poziom(st, mapa)
        if z:
            o_ktorej = datetime.fromtimestamp(z["ts"]).strftime("%H:%M")
            return D(id_, "czekaj", f"{powod}: powrót {'zlecony o ' + o_ktorej if z.get('ok') else 'nieudany ' + str(z.get('proby')) + ' razy (ostatnio ' + o_ktorej + ')'}, nie ponawiam",
                     "wroc-poziom-zlecony")
        if o["log"] and a.get("walka"):
            return D(id_, "czekaj", f"{powod}, ale bot w walce: czekam z powrotem do miasta", "wroc-poziom-walka")
        return D(id_, "wroc", powod + ": zlecam powrót do miasta (limit poziomu spotu)", "wroc-poziom", klasa="naprawa", problem="poziom",
                 mapa=mapa, poziom=poziom, maks=maks, nick=o.get("nick") or id_)

    def _zapisz_wroc_poziom(self, st, d, teraz, ok, tryb):
        if d["akcja"] == "wroc" and d["arg"].get("problem") == "poziom":
            z = st.get("wroc_poziom")
            proby = (z.get("proby", 0) + 1) if (z and z.get("mapa") == d["arg"].get("mapa") and z.get("tryb") == tryb) else 1
            st["wroc_poziom"] = {"tryb": tryb, "mapa": d["arg"].get("mapa"), "poziom": d["arg"].get("poziom"), "maks": d["arg"].get("maks"),
                                 "ts": ts_ep(teraz), "ok": bool(ok), "proby": proby}

    def _powiadom_wyrosl(self, id_, d, W):
        nick = d["arg"].get("nick") or id_
        return W.powiadom_info(id_, f"{nick}: poziom {d['arg'].get('poziom')}, wraca do miasta",
                               f"Limit poziomu spotu {d['arg'].get('mapa')} to {d['arg'].get('maks')}. Nadzorca zlecił WROC (bot idzie do depo i staje).")

    # --- plan postaci (23.10, Karol: „Wszystko powinien robić nadzorca, powinien mieć jakiś plan”) ---
    def plan_zywo(self):
        """True, gdy kroki planu są wykonywane NAPRAWDĘ (tak jak wroc-poziom): NADZOR_ZYWO albo NADZOR_NAPRAWY przy działających powiadomieniach."""
        return self.poziom_zywo()

    def plan_postaci(self):
        if self._plan is None:
            self._plan = PP.wczytaj(self.korzen)
        return self._plan

    def spot_przypiety(self, id_):
        """Powód przypięcia spotu (tekst) albo None. Postać przypięta (dawajkesh, invincible: Karol 23.10) zostaje na swoim spocie: nie rusza jej
        wybór spotu przy starcie zmiany, zmien_spot ani drabina napraw. Plan nieczytelny = nie wiem, kto jest przypięty: nikogo nie przenoszę."""
        plan = self.plan_postaci()
        if plan.nieczytelny:
            return "plan_postaci.json nieczytelny: nie zmieniam spotów"
        pc = plan.postacie.get(id_)
        if pc is not None and pc.spot_przypiety:
            return pc.spot_przypiety_powod or "plan_postaci.json"
        return None

    def zostan_depo_pc(self, id_):
        """Odczyt flagi (zostan_depo.Zostan) z planu postaci albo None (brak wpisu, plan nieczytelny, flaga wyłączona/błędna)."""
        plan = self.plan_postaci()
        if plan.nieczytelny:
            return None
        pc = plan.postacie.get(id_)
        z = pc.zostan if pc is not None else plan.zostan_domyslny      # 25.10 (Karol): postać bez wpisu w planie dostaje tylko pola `domyslne` (gdy włączone)
        return z if z.flaga else None

    def start_bota_ep(self, id_):
        """Epoch (koniec minuty) startu najnowszego bota instancji z nazwy logu `mozg-stdout-MMDD-GGMM.log` (uruchom.sh) albo None. Nazwa, bo
        `analizuj_log` czyta tylko końcówkę logu i `start` bywa None."""
        teraz = self.zegar()
        najlepszy = None
        try:
            for p in (self.kat(id_) / "logi").glob("mozg-stdout-*.log"):
                m = re.fullmatch(r"mozg-stdout-(\d{2})(\d{2})-(\d{2})(\d{2})\.log", p.name)
                if not m:
                    continue
                try:
                    t = datetime(teraz.year, int(m[1]), int(m[2]), int(m[3]), int(m[4]))
                except ValueError:
                    continue
                if t > teraz + timedelta(days=1):
                    t = t.replace(year=t.year - 1)
                if najlepszy is None or t > najlepszy:
                    najlepszy = t
        except OSError:
            return None
        return najlepszy.timestamp() + 59 if najlepszy else None

    def zostan_w_depo(self, id_, st=None):
        """Powód (tekst) albo None. Flaga `zostan_w_depo` w planie postaci (Karol 23.10: invincible, dawajkesh, wydra): po dojściu do depo postać zostaje
        w depo. Plan nieczytelny = flagi nieznane, nadzorca działa jak przed flagą (ostrzeżenie `plan-blad` jest w dzienniku).
        24.10: z `zostan_w_depo_po_refillach` flaga działa dopiero po N refillach i po starcie bota po N-tym (albo gdy znacznik `zostan_depo_od` już stoi)."""
        sg = ZD.spot_gracz_depo(self.kat(id_), self.zegar().timestamp(), self.start_bota_ep(id_) if (self.kat(id_) / ZD.PLIK_SPOT_GRACZ_DEPO).exists() else None)
        if sg:
            return sg           # 26.10: powrót do miasta po spotkaniach graczy (brak wolnego spotu): postać stoi w depo do decyzji, bez refillu i startu na spot
        z = self.zostan_depo_pc(id_)
        if z is None:
            return None
        if ZD.tylko_cap(self.kat(id_), self.zegar().timestamp()):      # 24.10 (Karol): depo wyłącznie po cap = bank + powrót na spot, nie "zostaje"
            return None
        powod = z.powod or "plan_postaci.json"
        if not z.po_refillach:
            return powod
        st = self.post(id_) if st is None else st
        if st.get("zostan_depo_od"):
            return powod
        return powod if ZD.uzbrojona(z, self.kat(id_), start_bota=self.start_bota_ep(id_), wymagaj_startu=True) else None

    @staticmethod
    def _w_depo(o, a):
        """Dowód depo: „Wyprawa: DEPO osiągnięte” w logu nowsze od startu bota albo panel (pozycja przy polu depo)."""
        return bool(a.get("depo") and (a.get("start") is None or a["depo"] >= a["start"])) or bool(o["panel"].get("w_depo"))

    def zostaje_w_depo(self, id_, o, st):
        """Powód (tekst), gdy postać z flagą `zostan_w_depo` jest w stanie „w depo + STOP, bez bota” i ma tam zostać, inaczej None. Bez skutków ubocznych.
        W grze: dowód depo (log albo panel). Offline / rozłączona: znacznik `zostan_depo_od` (nadzorca widział ją wcześniej w depo ze STOP) i dalej STOP.
        STOP_RECZNY (Karol gra) odrzuca bramka wcześniej; tu dla pewności też None."""
        powod = self.zostan_w_depo(id_, st)
        if not powod or not o["stop"] or o["stop_reczny"] or o["bot"]:
            return None
        if o["online"] and o["w_grze"]:
            return powod if self._w_depo(o, o["log"] or {}) else None
        return powod if st.get("zostan_depo_od") else None

    def _krok_planu(self, id_, krok_id):
        pc = self.plan_postaci().postacie.get(id_)
        return next((k for k in (pc.kroki if pc else []) if k.id == krok_id), None)

    def _tabela_dla_planu(self):
        tab = self.tabela_spotow()
        return tab if (tab is not None and not tab.blad) else None

    def _ekwipunek_dla_planu(self, id_):
        fn = getattr(self.zrodla, "ekwipunek", None)
        return (lambda: fn(id_)) if fn else None

    def _plan_log(self, teraz, id_):
        """Wpisy planu z konsumuj_start(zapis=False) do dziennika (z odsiewem powtórek)."""
        return lambda ak, w, po, **e: self.wpisz(teraz, D(id_, "plan", po, f"plan-{w}-{zlib.crc32(po.encode('utf-8')) % 10**6}"), "info")

    def plan_blanki(self, id_):
        fn = getattr(self.zrodla, "blanki", None)
        if not fn:
            return None
        try:
            return fn(id_)
        except Exception:       # noqa: BLE001
            return None

    def decyzja_planu(self, id_, o, a, st, zm, teraz):
        """Pierwszy niezrobiony, nieuzbrojony krok z warunkiem `poziom >= N` spełnionym przez BIEŻĄCY poziom z gry (nie zapamiętany) albo None.
        Krok raz, nie w walce; wyjątki (STOP_RECZNY, pauza, hold, nadzor:false) odrzuca bramka przed decyduj, powrót w toku i serwis kolejność w decyduj.
        Kroki `po_refillu` / `przy_nastepnym_starcie` nie są tu: zużywa je start bota (konsumuj_start)."""
        pc = self.plan_postaci().postacie.get(id_)
        if pc is None or not pc.kroki:
            return None
        if zm is not None and teraz >= datetime.strptime(zm["koniec"], FMT):
            return None         # koniec zmiany ma własny cykl (WROC, serwis, wylogowanie): plan nie wchodzi mu w drogę
        poziom = self.poziom_z_odczytu(o.get("gracz"), o.get("panel"))
        if poziom is None:
            return None
        for k in pc.kroki:
            if k.zrobione_t or k.uzbrojone_t:
                continue
            if k.warunek["typ"] == "po_zwolnieniu":         # 23.10 (Karol): odchyd wchodzi na spot gebelisha ~10 min po jego wyjściu
                d = self._decyzja_zwolnienia(id_, o, a, st, teraz, k, poziom)
                if d:
                    return d
                continue
            if k.warunek["typ"] != "poziom" or poziom < k.warunek["n"]:
                continue
            return self._decyzja_kroku(id_, o, a, st, teraz, k, poziom)
        return None

    def _zwolnienie(self, kto, mapa, teraz):
        """(t_ep, skąd) gdy postać `kto` ZWOLNIŁA mapę `mapa` (od t_ep), inaczej (None, powód). Dowód z plików i procesów, bez stanu nadzorcy:
        - bot `kto` działa na `mapa` (tryb.log + `Mózg: … trasa`) -> zajęta;
        - bot działa na innej mapie -> zwolniona od ostatniego wpisu `[TRYB] mapa` w jej tryb.log;
        - bota nie ma, plik STOP (bot staje w depo albo nadzorca go zatrzymał) i ostatnia mapa to `mapa` -> zwolniona od mtime STOP
          (to chwila dojścia do depo, więc nie wcześniej niż faktyczne zejście ze spotu: odliczanie jest ostrożne);
        - bota nie ma, ostatnia mapa inna -> zwolniona od ostatniego wpisu `[TRYB] mapa`;
        - bota nie ma i NIE MA STOP (awaria, restart w toku) albo STOP_RECZNY (Karol gra) -> nie wiem, spot NIE jest zwolniony (nadzorca ją podniesie)."""
        raw = (getattr(self, "_raw", {}) or {}).get(kto)
        if raw is None:
            return None, f"brak odczytu {kto}"
        try:
            mapa_k = mapa_tryb_biezace(self.korzen, kto, teraz)[0]
        except Exception:       # noqa: BLE001
            mapa_k = None
        kat = self.kat(kto)
        if (kat / "STOP_RECZNY").exists():
            return None, f"{kto} ma STOP_RECZNY (Karol gra): nie wiem, czy zwolniła"
        t_mapa = None
        try:
            for l in (kat / "logi" / "tryb.log").read_text(encoding="utf-8", errors="replace")[-300_000:].splitlines():
                m = RE_TRYB_MAPA.match(l)
                if m:
                    t_mapa = datetime.strptime(m[1], "%Y-%m-%d %H:%M:%S").timestamp()
        except (OSError, ValueError):
            pass
        if raw.get("bot"):
            if mapa_k == mapa or mapa_k is None:
                return None, f"{kto} ma tam działającego bota"
            return (t_mapa, f"{kto} działa na {mapa_k}") if t_mapa else (None, f"{kto}: brak czasu wpisu mapy")
        if mapa_k is None:
            return None, f"{kto}: nieznana ostatnia mapa (brak [TRYB] mapa)"
        if mapa_k != mapa:
            return (t_mapa, f"{kto} stoi bez bota, ostatnio na {mapa_k}") if t_mapa else (None, f"{kto}: brak czasu wpisu mapy")
        try:
            return (kat / "STOP").stat().st_mtime, f"{kto} zeszła ze spotu: bez bota, STOP"
        except OSError:
            return None, f"{kto} bez bota i bez STOP (awaria / restart w toku): nie traktuję jako zwolnienia"

    def _zajete_bez(self, id_, kto, teraz):
        """Zajęte mapy jak `_zajete_mapy`, ale bez spotu zapisanego w stanie dla postaci `kto` (zwalniająca ma go jeszcze w stanie, w depo, bez bota):
        z `kto` liczy się tylko działający bot (tryb.log)."""
        zaj = self.mapy_zajete(id_, teraz)
        zaj.pop(kto, None)
        wynik = set().union(*zaj.values()) if zaj else set()
        raw = (getattr(self, "_raw", {}) or {}).get(kto) or {}
        if raw.get("bot"):
            try:
                wynik.add(mapa_tryb_biezace(self.korzen, kto, teraz)[0])
            except Exception:       # noqa: BLE001
                pass
        wynik.discard(None)
        return wynik

    def _decyzja_zwolnienia(self, id_, o, a, st, teraz, k, poziom):
        """Krok `po_zwolnieniu <kto> <mapa> +Nmin`: po N minutach od zwolnienia mapy przez `kto` -> powrót do miasta i start na tej mapie
        (jak `mapa` z warunkiem poziomu: WROC, uzbrojenie, start z depo), chyba że bot już na niej stoi. Cel ścisły. Przed czasem / bez dowodu: None."""
        w, akcja = k.warunek, k.akcja
        t_free, skad = self._zwolnienie(w["kto"], w["mapa"], teraz)
        if t_free is None or ts_ep(teraz) - t_free < w["min"] * 60:
            return None
        opis = f"plan {k.id} ({k.opis()}, poziom {poziom}; {skad} od {datetime.fromtimestamp(t_free):%H:%M})"
        if st.get("plan_proby", {}).get(k.id, 0) >= PLAN_PROBY:
            return D(id_, "czekaj", f"{opis}: {PLAN_PROBY} nieudane próby, nie ponawiam (do sprawdzenia przez Karola)", "plan-proby")
        if o["log"] and a.get("walka"):
            return D(id_, "czekaj", f"{opis}, ale bot w walce: czekam", "plan-walka")
        mapa_b, tryb_b, _skad = mapa_tryb_biezace(self.korzen, id_, teraz)
        if not mapa_b:
            return D(id_, "czekaj", f"{opis}: nieznana bieżąca mapa (brak [TRYB] mapa w tryb.log), nie zgaduję", "plan-bez-mapy")
        tryb = akcja["tryb"] or tryb_b
        if not tryb:
            return D(id_, "czekaj", f"{opis}: nieznany bieżący tryb, nie zgaduję", "plan-bez-trybu")
        if "runy" in tryb.split(","):
            return D(id_, "czekaj", f"{opis}: tryb runy nie jest obsługiwany przez po_zwolnieniu (brak kontroli blanków)", "plan-runy")
        cel, kom = PP.wybierz_cel(self.korzen, id_, akcja["mapa"], self._zajete_bez(id_, w["kto"], teraz), poziom, self._tabela_dla_planu(),
                                  self._ekwipunek_dla_planu(id_), scisle=True)
        if cel is None:
            return D(id_, "czekaj", f"{opis}: {kom}", "plan-brak", krok=k.id)
        arg = {"krok": k.id, "poziom": poziom, "nick": o.get("nick") or id_, "mapa": mapa_b}
        if cel == mapa_b:
            if tryb == tryb_b:
                return D(id_, "plan_juz", f"{opis}: już na {mapa_b} z trybem {tryb_b}, nic do zmiany", "plan-juz", klasa="naprawa", problem="plan",
                         **dict(arg, tryb=tryb))
            return D(id_, "plan_tryb", f"{opis}: restart bota na {mapa_b} z trybem {tryb}", "plan-tryb", klasa="naprawa", problem="plan",
                     **dict(arg, tryb=tryb))
        return D(id_, "plan_mapa", f"{opis}: powrót do miasta, start na {cel}", "plan-mapa", klasa="naprawa", problem="plan",
                 cel=cel, tryb=akcja["tryb"], **arg)

    def _decyzja_kroku(self, id_, o, a, st, teraz, k, poziom):
        opis = f"plan {k.id} ({k.opis()}, poziom {poziom})"
        if st.get("plan_proby", {}).get(k.id, 0) >= PLAN_PROBY:
            return D(id_, "czekaj", f"{opis}: {PLAN_PROBY} nieudane próby, nie ponawiam (do sprawdzenia przez Karola)", "plan-proby")
        if o["log"] and a.get("walka"):
            return D(id_, "czekaj", f"{opis}, ale bot w walce: czekam", "plan-walka")
        mapa_b, tryb_b, _skad = mapa_tryb_biezace(self.korzen, id_, teraz)
        arg = {"krok": k.id, "poziom": poziom, "nick": o.get("nick") or id_, "mapa": mapa_b}
        akcja = k.akcja
        if akcja["typ"] == "wroc":
            return D(id_, "wroc", f"{opis}: zlecam powrót do miasta", "plan-wroc", klasa="naprawa", problem="plan", **arg)
        cel_info = ""
        if akcja["typ"] == "mapa":
            cel, kom = PP.wybierz_cel(self.korzen, id_, akcja["mapa"], self._zajete_mapy(id_), poziom, self._tabela_dla_planu(),
                                      self._ekwipunek_dla_planu(id_))
            if cel is None:
                return D(id_, "czekaj", f"{opis}: {kom}", "plan-brak", krok=k.id)
            cel_info = f" ({kom})" if kom else ""
            if cel != mapa_b:
                return D(id_, "plan_mapa", f"{opis}: powrót do miasta, start na {cel}{cel_info}", "plan-mapa", klasa="naprawa", problem="plan",
                         cel=cel, tryb=akcja["tryb"], **arg)
            akcja = {"typ": "tryb", "tryb": akcja["tryb"] or tryb_b}        # już stoi na celu: zostaje, najwyżej zmiana trybu
        if not mapa_b:
            return D(id_, "czekaj", f"{opis}: nieznana bieżąca mapa (brak [TRYB] mapa w tryb.log), nie zgaduję", "plan-bez-mapy")
        if akcja["tryb"] == tryb_b:
            return D(id_, "plan_juz", f"{opis}: już na {mapa_b} z trybem {tryb_b}, nic do zmiany", "plan-juz", klasa="naprawa", problem="plan", **arg)
        if "runy" in akcja["tryb"].split(","):
            bl = self.plan_blanki(id_)
            if bl is None or bl < k.blanki_min:
                ile = "brak odczytu blanków" if bl is None else f"blanków {bl} < {k.blanki_min}"
                return D(id_, "plan_blanki", f"{opis}: {ile} w plecaku, nie startuję trybu runy na ślepo: powrót do miasta, tryb ruszy po refillu (kupi blanki)",
                         "plan-blanki", klasa="naprawa", problem="plan", tryb=akcja["tryb"], blanki=bl, **arg)
        return D(id_, "plan_tryb", f"{opis}: restart bota na {mapa_b} z trybem {akcja['tryb']}", "plan-tryb", klasa="naprawa", problem="plan",
                 tryb=akcja["tryb"], **arg)

    def _plan_porazka(self, st, krok_id):
        st.setdefault("plan_proby", {})[krok_id] = st.get("plan_proby", {}).get(krok_id, 0) + 1

    def _plan_stub_wroc(self, st, d, teraz):
        """Krok planu zlecił WROC: wroc-poziom nie zleca drugiego (Rook 1-7: plan `poziom >= 8 -> wroc` i limit spotu to ten sam powrót)."""
        st["wroc_poziom"] = {"tryb": "zywo", "mapa": d["arg"].get("mapa"), "poziom": d["arg"].get("poziom"), "maks": None, "ts": ts_ep(teraz),
                             "ok": True, "proby": 1}

    def _powiadom_plan(self, W, id_, d, tresc):
        k = self._krok_planu(id_, d["arg"].get("krok"))
        powod = f" ({k.powod})" if k and k.powod else ""
        nick = d["arg"].get("nick") or id_
        return W.powiadom_info(id_, f"{nick}: plan, krok {d['arg'].get('krok')}"[:80], tresc + powod)

    def _wykonaj_plan(self, teraz, id_, d, st, W):
        """wroc / plan_blanki / plan_mapa / plan_tryb: jeden krok planu NA ŻYWO. -> (ok, tekst). `zrobione_t` (atomowo) dopiero po udanym skutku."""
        akcja, arg = d["akcja"], d["arg"]
        krok = arg.get("krok")
        if akcja == "plan_juz":
            PP.oznacz_zrobione(self.korzen, id_, krok, teraz, "już na tej mapie i w tym trybie")
            self._powiadom_plan(W, id_, d, f"Już na {arg.get('mapa')} z trybem {arg.get('tryb')}: bez zmian.")
            return True, "bez zmian"
        if akcja == "plan_tryb":
            raw = getattr(self, "_raw", {}).get(id_) or {}
            if raw.get("bot"):
                ok, txt = W.zatrzymaj_bota(id_)
                if not ok:
                    self._plan_porazka(st, krok)
                    return False, "zatrzymanie nieudane: " + txt
            odmowa = self.bramka(id_)
            if odmowa:          # zatrzymanie trwa kilka sekund: w tym czasie mogło pojawić się STOP_RECZNY (uruchom.sh by go skasował)
                return False, "start bota anulowany po zatrzymaniu: " + odmowa
            ok, txt = W.start_bota(id_, arg.get("mapa"), arg.get("tryb"))
            if not ok:
                self._plan_porazka(st, krok)
                return False, txt
            st["bot_start"], st["faza"] = ts_ep(teraz), "DOJSCIE"
            st["stoi_w_depo_od"] = None
            PP.oznacz_zrobione(self.korzen, id_, krok, teraz, f"restart: {arg.get('mapa')} / {arg.get('tryb')}")
            self._powiadom_plan(W, id_, d, f"Restart bota na {arg.get('mapa')} z trybem {arg.get('tryb')}.")
            return True, f"{arg.get('mapa')} / {arg.get('tryb')}; {txt}"
        ok, txt = W.wroc(id_)
        if not ok:
            self._plan_porazka(st, krok)
            return False, txt
        st["faza"], st["powrot_od"] = "POWROT", ts_ep(teraz)
        self._plan_stub_wroc(st, d, teraz)
        if akcja == "wroc":
            PP.oznacz_zrobione(self.korzen, id_, krok, teraz, "wroc")
            self._powiadom_plan(W, id_, d, f"Poziom {arg.get('poziom')}: wraca do miasta (bot idzie do depo i staje).")
        elif akcja == "plan_blanki":
            PP.uzbroj(self.korzen, id_, krok, teraz, mapa=arg.get("mapa"), tylko_refill=True)
            self._powiadom_plan(W, id_, d, f"Poziom {arg.get('poziom')}, brak blanków na runy: wraca do miasta; tryb {arg.get('tryb')} ruszy po refillu.")
        else:
            PP.uzbroj(self.korzen, id_, krok, teraz, tylko_refill=False)
            self._powiadom_plan(W, id_, d, f"Poziom {arg.get('poziom')}: wraca do miasta; następny start bota pójdzie na {arg.get('cel')}"
                                           + (f" ({arg.get('tryb')})" if arg.get("tryb") else "") + ".")
        return True, txt

    def _plan_start(self, id_, teraz, poziom, biezaca):
        """Kroki planu, które ten start nadzorcy (login, relog, restart, wznów) ma wykonać: {"mapa","tryb","kroki"} albo None. NIC nie zapisuje do pliku
        planu (zużycie dopiero po udanym starcie: `_plan_zuzyj`); zajętość mapy liczona z bieżących map innych botów."""
        try:
            return PP.konsumuj_start(self.korzen, id_, "nadzor", teraz, zapis=False, zajete=self._zajete_mapy(id_), poziom=poziom,
                                     ekwipunek=self._ekwipunek_dla_planu(id_), powiadom=self._wykonawca_dla({"akcja": "start_bota", "kod": "plan-start"}).powiadom_info,
                                     log=self._plan_log(teraz, id_), bramki=False, biezaca=biezaca, tabela=self._tabela_dla_planu(), ostrzez=self.plan_zywo(),
                                     zajete_bez=lambda kto: self._zajete_bez(id_, kto, teraz))
        except Exception as e:      # noqa: BLE001  (plan nie wolno wywrócić startu postaci)
            self.wpisz(teraz, D(id_, "ostrzezenie", f"plan: błąd przy ustalaniu startu: {e!r}; start bez planu", "plan-wyjatek"), "ostrzezenie")
            return None

    def _plan_zuzyj(self, id_, r, teraz, W):
        """Po UDANYM starcie bota z planu: zrobione_t (atomowo) + jedno zwykłe powiadomienie na krok (uzbrojony krok powiadomił już przy WROC)."""
        for kid in r["kroki"]:
            k = self._krok_planu(id_, kid)
            if PP.oznacz_zrobione(self.korzen, id_, kid, teraz, f"start (nadzor): {r['mapa']} / {r['tryb'] or '-'}") and k and not k.uzbrojone_t:
                W.powiadom_info(id_, f"{id_}: plan, krok {kid}"[:80],
                                f"{k.opis()} ({k.powod}). Start: {r['mapa']} / {r['tryb'] or '-'}.")

    def _ostrzez_plan_brak(self, teraz, id_, d):
        """Krok `mapa` czeka, bo cel jest zajęty i nie ma wolnego spotu w tych samych widełkach: dziennik (wpis `czekaj` już jest) + jedno powiadomienie
        na krok raz na kilka godzin (tylko gdy plan jest wykonywany naprawdę)."""
        krok = d["arg"].get("krok")
        if not (krok and self.plan_zywo()) or not PP.ostrzez_raz(self.korzen, id_, krok, teraz):
            return
        W = self._wykonawca_dla(d)
        W.powiadom_info(id_, f"{id_}: plan czeka, brak wolnego spotu"[:80], d["powod"][:300])

    # --- wybór spotu (Q5, SPEC_wybor_spotu_1021) ---
    def tabela_spotow(self):
        """Tabela spotów (spoty.py) albo None, gdy nie ma pliku dane_tibia/spoty_nadzorca.json (wtedy zachowanie jak przed Q5). Raz na przebieg."""
        if not self._tab_ladowana:
            self._tab_ladowana = True
            plik = self.korzen / "dane_tibia" / "spoty_nadzorca.json"
            self._tab = SP.wczytaj(self.korzen) if plik.exists() else None
        return self._tab

    @staticmethod
    def poziom_z_odczytu(gracz, panel):
        """Poziom z bieżącego odczytu (gracz.level, potem panel.level) albo None."""
        for zrodlo in (gracz, panel):
            v = zrodlo.get("level") if isinstance(zrodlo, dict) else None
            if isinstance(v, int) and not isinstance(v, bool) and v > 0:
                return v
        return None

    def poziom_znany(self, id_, teraz):
        """(poziom, data odczytu) ostatniego udanego odczytu tej postaci, jeśli młodszy niż poziom_max_wiek_h; inaczej None. Nie zgaduję."""
        z = self.post(id_).get("poziom")
        if not (isinstance(z, dict) and isinstance(z.get("wartosc"), int) and z.get("t")):
            return None
        try:
            wiek_h = (teraz - datetime.strptime(z["t"], FMT)).total_seconds() / 3600
        except ValueError:
            return None
        if wiek_h > float(self.konf.get("poziom_max_wiek_h", POZIOM_MAX_WIEK_H)):
            return None
        return z["wartosc"], z["t"]

    def zapamietaj_poziom(self, id_, o, teraz):
        """22.10: ostatni znany poziom z datą odczytu (strażnik bywa chwilowo nieosiągalny: nie traci się wtedy poziomu postaci)."""
        v = self.poziom_z_odczytu(o.get("gracz"), o.get("panel"))
        if v is not None:
            self.post(id_)["poziom"] = {"wartosc": v, "t": teraz.strftime(FMT)}

    @staticmethod
    def _kiedy(odczyt, teraz):
        return odczyt[11:] if odczyt[:10] == teraz.strftime("%Y-%m-%d") else odczyt[5:]

    def fakty_postaci(self, id_, panel, gracz):
        """Pozycja (z gry: panel.pozycja z okno_api stan) i poziom postaci dla spoty.wybierz; ekwipunek leniwie (odczyt tylko na żądanie).
        Przy braku bieżącego poziomu: ostatni znany (poziom_odczyt = data odczytu), jeśli nie starszy niż poziom_max_wiek_h."""
        poz = (panel or {}).get("pozycja")
        poz = tuple(int(v) for v in poz[:3]) if isinstance(poz, (list, tuple)) and len(poz) >= 3 else None
        poziom, odczyt = self.poziom_z_odczytu(gracz, panel), None
        self._poziom_z_pamieci.pop(id_, None)
        if poziom is None:
            zn = self.poziom_znany(id_, self.zegar())
            if zn:
                poziom, odczyt = zn
                self._poziom_z_pamieci[id_] = zn
        fn = getattr(self.zrodla, "ekwipunek", None)
        return {"id": id_, "poz": poz, "poziom": poziom, "poziom_odczyt": odczyt,
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

    def wybierz_spot(self, id_, panel, gracz, teraz, biezaca, przyczyna, dodatkowo_zajete=(), zajete=None, z_depo=False, wyklucz_mapy=(), rodzina_z=None):
        """spoty.wybierz z faktami tej postaci. -> wynik wybierz() albo None, gdy tabeli brak. Ziarno: dzień + przyczyna (początek zmiany / zmien_spot).
        zajete (zbiór map) zastępuje bieżące mapy innych botów (podgląd w cieniu); z_depo=True liczy start z z7 (postać zaczynałaby od depo)."""
        tab = self.tabela_spotow()
        if tab is None:
            return None
        zaj = (set(zajete) if zajete is not None else set().union(*self.mapy_zajete(id_, teraz).values())) | set(m for m in dodatkowo_zajete if m)
        fakty = self.fakty_postaci(id_, panel, gracz)
        if z_depo and fakty["poz"]:
            fakty["poz"] = (fakty["poz"][0], fakty["poz"][1], SP.LEKKIE_Z)
        return SP.wybierz(fakty, zaj, self.historia_spotow(id_, biezaca), tab, ziarno=f"{teraz:%Y-%m-%d}|{przyczyna}",
                          wyklucz_mapy=wyklucz_mapy, rodzina_z=rodzina_z)

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
        if not self.spot_przypiety(id_) and (self.spot_zapasowy(id_, mapa, self._zajete_mapy(id_)) or self._alternatywa_spotu(id_, o, mapa, teraz)):
            szczeble.append("zmien_spot")       # spot przypięty (dawajkesh, invincible): bez zmiany spotu w drabinie
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
        zostaje = self.zostaje_w_depo(id_, o, st)       # 23.10 (Karol): invincible, dawajkesh, wydra w depo ze STOP zostają w depo
        wyl = None if zostaje else self._po_wylogowaniu_bota(id_, o, teraz)
        if wyl is not None:
            return [wyl]
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
                st.pop("wroc_koniec", None)
                st.pop("wroc_poziom", None)
            st.pop("adopcja_od", None)
            if zostaje:
                return [D(id_, "czekaj", f"offline, ostatnio w depo ze STOP (zostan_w_depo: {zostaje}): nie loguję, postać zostaje w depo", "zostaje-offline")]
            pr_off = self._przerwa_offline(id_, o, st, teraz, zm, cisza)       # 24.10: przerwa postaci (zmiana w grafiku jej nie przebija)
            if pr_off:
                return [pr_off]
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
        if zm is not None and zm["od"] in st.get("zakonczone", []) and not self.przerwa_trwa(id_):
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
        if zostaje:     # w depo ze STOP, bez bota, flaga zostan_w_depo: żadnego wznow/restart/serwis/relog/wylogowania/startu; powrót (WROC) już się skończył
            st.setdefault("zostan_depo_od", ts_ep(teraz))
            st["faza"] = "MIASTO"
            if self.wyloguj_w_depo(id_):
                return [self._wylogowanie_w_depo(id_, o, a, st, teraz, zostaje)]
            return [D(id_, "czekaj", f"stoi w depo ze STOP (zostan_w_depo: {zostaje}): zostaje, nie wznawiam, bez serwisu, refillu, relogu i wylogowania", "zostaje-w-depo")]
        st.pop("zostan_depo_od", None)
        pr_on = self._przerwa_online(id_, o, a, st, teraz)         # 24.10: przerwa postaci (przed „poza grafikiem: nie ruszam”)
        if pr_on:
            return [pr_on]
        if zm is None:
            # Sesja bez zmiany w grafiku (nowa instancja, ręczny start, grafik zrobiony przed jej pojawieniem się). Bot działa albo wraca do miasta:
            # to aktywna sesja i trafia pod nadzór od razu (zacięcie, limit dzienny, plecak, cap, jedzenie, powrót), tylko bez końca zmiany z grafiku.
            # Brak bota i brak powrotu = ręczna gra Karola: nie ruszam.
            if not (o["bot"] or o["wroc"] or o["wyprawa"]):
                return [D(id_, "czekaj", "online poza grafikiem, bez bota: nie ruszam (ręczna gra; do przyjęcia: grafik.py nowy --od-teraz)", "poza-grafikiem")]
            if not st.get("adopcja_od"):
                st["adopcja_od"] = ts_ep(teraz)
                self.wpisz(teraz, D(id_, "adopcja", "sesja bez zmiany w grafiku, bot działa: biorę pod nadzór "
                                    "(bez końca zmiany z grafiku; limity, zacięcia, plecak, cap i jedzenie pilnuję)", "adopcja"), "info")
        # POWROT w toku
        if o["wroc"] or o["wyprawa"]:
            st["faza"] = "POWROT"
            st.setdefault("powrot_od", ts_ep(teraz))
            if ts_ep(teraz) - st["powrot_od"] > 40 * 60:
                return [D(id_, "eskaluj", "powrót do miasta trwa > 40 min", "powrot-dlugo", klasa="eskalacja", kod_eskalacji="wyczerpana")]
            return [D(id_, "czekaj", "powrót do miasta (WROC) w toku", "powrot")]
        if not o["bot"]:
            st.pop("wroc_koniec", None)         # bot stoi: powrót się udał (albo bota nie ma); następny koniec zmiany to nowe zlecenie
            return [self._bez_bota(id_, o, a, st, teraz, zm)]
        # bot działa
        if st.get("faza") in ("MIASTO", "WYLOGOWANIE", "POWROT"):
            st["faza"] = "EXP"
        if st.get("faza") == "DOJSCIE" and (a.get("zabicia_od_startu", 0) > 0 or ts_ep(teraz) - (st.get("bot_start") or 0) > 900):
            st["faza"] = "EXP"
        pl = self.decyzja_planu(id_, o, a, st, zm, teraz)       # 23.10: plan postaci przed „wyrósł ze spotu” (Rook: poziom 8 to ten sam powrót)
        if pl:
            if pl["akcja"] != "czekaj":
                return [pl]
            self._plan_czeka.append((id_, pl))          # krok czeka (walka, brak wolnego spotu, próby): wpis, ale reszta kontroli idzie dalej
        wyr = self.decyzja_wyrosl(id_, o, a, st, teraz)         # 23.10: przed grafikiem (grafik jest w cieniu, to jedyna decyzja na żywo bez NADZOR_ZYWO)
        if wyr:
            return [wyr]
        koniec = self.koniec_zmiany(id_, o, zm, teraz)
        if koniec:
            st["koniec"] = koniec[0]
            return self._decyzja_konca(id_, st, zm, koniec, teraz)
        zaciecie = self.zaciecie(id_, o, a, st, teraz)
        if zaciecie:
            if o["log"] and a.get("walka"):
                return [D(id_, "czekaj", f"{zaciecie}, ale bot w walce: odkładam restart", "walka-odroczenie")]
            return [self.drabina(id_, teraz, "zaciecie", o)]
        if (a.get("brak_plecaka", 0) >= OKNA_PROG or a.get("brak_okna", 0) >= OKNA_PROG_OKNA) \
                and ts_ep(teraz) - st.get("okna_ts", 0) >= OKNA_KARENCJA_S:
            # 22.10: log powtarza brak plecaka/okna (po padzie klienci wystartowali z rozwiniętą minimapą i bez plecaka): kontrola okien
            powod = f"log bota: brak_plecaka x{a.get('brak_plecaka', 0)}, brak_okna x{a.get('brak_okna', 0)} w 5 min: kontrola okien"
            if o["log"] and a.get("walka_bez_lootu"):
                return [D(id_, "czekaj", f"{powod}, ale bot w walce: odkładam", "okna-odroczenie")]
            return [D(id_, "okna", powod, "okna", klasa="naprawa", problem="okna")]
        # 23.10 (strategia Karola): „czar bez efektu 3×” (powiadomienie) i restart po zmianie kodu (pokrętło, domyślnie wyłączone)
        try:
            sgd = self.decyzja_spot_gracz(id_, o, a, st, teraz)     # 26.10: zmiana spotu po 3. spotkaniu tego samego gracza (zlecenie bota)
        except Exception as e:      # noqa: BLE001
            sgd = None              # nowa ścieżka nigdy nie psuje przebiegu nadzorcy dla pozostałych decyzji
            self.wpisz(teraz, D(id_, "ostrzezenie", f"spot-gracz: błąd {e!r}", "spot-gracz-blad"), "ostrzezenie")
        if sgd:
            return [sgd]
        dodatkowe = [d for d in (self.decyzja_czar(id_, a, st, teraz), self.decyzja_restart_kod(id_, o, a, st, teraz)) if d]
        if dodatkowe:
            return dodatkowe
        return [D(id_, "czekaj", f"{st.get('faza', 'EXP')}: bot działa, bez uwag", "ok")]

    def _stanowisko(self, id_, teraz):
        """True, gdy bieżąca mapa instancji to stanowisko (stoj_runy_*): bot stoi i robi runy, nie poluje."""
        try:
            mapa = mapa_tryb_biezace(self.korzen, id_, teraz)[0]
        except Exception:
            return False
        return bool(mapa) and str(mapa).startswith("stoj_runy")

    def zaciecie(self, id_, o, a, st, teraz):
        t = o.get("tele") or {}
        if (t.get("wiek_probki_s") or 0) > 120:
            return f"telemetria stara ({t['wiek_probki_s']} s): bot zawieszony"
        if stoj_wlaczony(self.korzen, id_):
            return None         # 23.10 przełącznik STÓJ (stoj.py, plik instancje/<id>/STOJ): postać stoi z woli Karola, nie jest zacięta (ani „stoi > N min”, ani „brak zabić”)
        if self._stanowisko(id_, teraz):
            return None         # 22.10 tryb stoj (stoj_runy_*): stanie na polu i brak zabić to norma, nie zacięcie; stara telemetria wyżej nadal liczy się jako zawieszenie
        if (t.get("stoi_poza_walka_s") or 0) > float(self.konf["stoi_min"]) * 60:
            return f"stoi w miejscu {t['stoi_poza_walka_s']} s poza walką"
        start = st.get("bot_start") or a.get("start")
        if start and st.get("faza") == "EXP" and ts_ep(teraz) - start > float(self.konf["brak_zabic_min"]) * 60:
            ost = max(a.get("ost_zabicie") or 0, start)
            if ts_ep(teraz) - ost > float(self.konf["brak_zabic_min"]) * 60:
                return f"brak zabić od {round((ts_ep(teraz) - ost) / 60)} min"
        return None

    def _po_wylogowaniu_bota(self, id_, o, teraz):
        """23.10 (decyzja Karola po resecie serwera): bot, który zobaczył ekran logowania / listę postaci / brak postaci, kończy proces i zostawia
        instancje/<id>/wylogowany.json (wylogowanie.py). Taka postać NIE jest awarią (`_bez_bota` -> drabina awaria -> restart bota na ekranie
        logowania) ani rozłączeniem do natychmiastowego `zaloguj` (`_poza_gra` -> relog w trakcie resetu): czeka na kolejkę relogów
        (relog_wylogowanych.py: >= 10 min po wylogowaniu / po resecie, pełny restart klienta, jedna postać naraz, przerwa 3-6 min).
        -> decyzja albo None (brak świeżego znacznika albo bot już działa: znacznik nieaktualny, zajmie się nim mozg.main)."""
        if o.get("bot"):
            return None
        r = RW.ocen(self.korzen, id_, ts_ep(teraz))
        if r is None:
            return None
        m, od = r["marker"], datetime.fromtimestamp(r["od"])
        kto = f"wylogowany o {m.get('czas', '?')[11:16]} ({m.get('powod', '?')[:60]}); mapa {m.get('mapa') or '?'}"
        if r["proby"] >= RW.MAX_PROB:
            return D(id_, "eskaluj", f"relog po wylogowaniu bota nieudany {r['proby']} razy ({kto})", "relog-wylog-wyczerpany",
                     klasa="eskalacja", kod_eskalacji="relog_wylog")
        if RW.kolejka_dziala(self.korzen):
            return D(id_, "czekaj", f"{kto}: kolejka relogów trwa (jedna postać naraz)", "relog-wylog-trwa")
        if not r["gotowa"]:
            return D(id_, "czekaj", f"{kto}: {r['powod']}", "relog-wylog-czeka")
        return D(id_, "relog_wylog", f"{kto}: relog (restart klienta, logowanie, bot na {m.get('mapa')} / {m.get('tryb') or '-'}), od {od:%H:%M}",
                 "relog-wylog", klasa="bot", mapa=m.get("mapa"), tryb=m.get("tryb"))

    def _poza_gra(self, id_, o, a, st, teraz, zm):
        """Sesja jest, ale klient nie jest w grze: logowanie w toku, rozłączenie albo stan nieustalony."""
        zostaje = self.zostaje_w_depo(id_, o, st)
        if zostaje:     # 23.10: po resecie serwera / rozłączeniu postać z flagą zostan_w_depo (ostatnio w depo ze STOP) nie jest logowana na siłę
            return D(id_, "czekaj", f"klient poza grą, ostatnio w depo ze STOP (zostan_w_depo: {zostaje}): nie loguję ponownie, postać zostaje w depo", "zostaje-poza-gra")
        pr_trwa = self.przerwa_trwa(id_)        # 24.10: przerwa postaci: nasz powrót po przerwie nie jest „sesją poza zmianą”
        zamkniecie = None if pr_trwa else self.decyzja_zamknij_sesje(id_, o, zm)         # 23.10 (Karol): wylogowana poza zmianą = zamknięta sesja klienta
        if zamkniecie:
            return zamkniecie
        rozl = bool(a.get("rozl") and a["rozl"] > (a.get("rozl_koniec") or 0)) or o["ekran"] in ("logowanie", "lista")
        w_logowaniu = (st.get("faza") == "LOGOWANIE" and st.get("logowanie_nasze")
                       and ts_ep(teraz) - st.get("login_ts", ts_ep(teraz)) < 600)
        if w_logowaniu and (zm is not None or pr_trwa):
            if ts_ep(teraz) - st.get("zaloguj_ts", 0) < 60:
                return D(id_, "czekaj", "logowanie w toku: czekam na wejście do gry", "logowanie-czeka")
            if pr_trwa:         # kod plan-*: na żywo także wtedy, gdy zmiana z grafiku jest aktywna (grafik działa w cieniu)
                return D(id_, "zaloguj", "przerwa skończona, sesja stoi, klient na ekranie logowania: zaloguj.sh (kliki Login i Ok)", "plan-przerwa-zaloguj",
                         klasa="logowanie", przerwa=True)
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
        w_depo = self._w_depo(o, a)
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
                     klasa="bot", mapa=mapa, tryb=tryb, spot=spot, plan_kroki=wyb.get("plan_kroki"), poziom=wyb.get("poziom"))
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
        biez_mapa, biez_tryb, _skad = mapa_tryb_biezace(self.korzen, id_, teraz)
        poziom = self.poziom_z_odczytu(o.get("gracz"), o.get("panel"))
        r = self._plan_start(id_, teraz, poziom, (biez_mapa, biez_tryb))
        if r:       # 23.10: zaplanowana mapa/tryb na następny start wygrywa z tryb.log i spotem; po starcie źródłem prawdy jest znów tryb.log
            self._przypisane[id_] = r["mapa"]
            return {"mapa": r["mapa"], "tryb": r["tryb"], "skad": "plan: krok " + ", ".join(r["kroki"]), "spot": None, "plan_kroki": r["kroki"], "poziom": poziom}
        if zm and zm.get("mapa"):
            return {"mapa": zm["mapa"], "tryb": zm.get("tryb"), "skad": "grafik", "spot": None}
        pin = self.spot_przypiety(id_)
        if pin:     # dawajkesh / invincible (Karol 23.10): zostają na bieżącym spocie, bez mieszania jaskiń przy starcie zmiany
            tab = self.tabela_spotow()
            jask = (lambda m: tab.jaskinia_mapy(m)) if (tab is not None and not tab.blad) else (lambda m: m)       # noqa: E731
            zaj = {jask(m) for m in self._zajete_mapy(id_)}
            if biez_mapa and jask(biez_mapa) not in zaj:
                return {"mapa": biez_mapa, "tryb": biez_tryb, "skad": f"spot przypięty ({pin})", "spot": {"mapa": biez_mapa, "jaskinia": jask(biez_mapa)}}
            ile = ts_ep(teraz) - (st.get("login_ts") or ts_ep(teraz))
            powod = (f"spot przypięty ({pin}), ale " + (f"jaskinia {jask(biez_mapa)} zajęta przez innego bota" if biez_mapa else "bieżącej mapy nie ustalam (tryb.log)")
                     + ": nie przenoszę bez wpisu Karola")
            if ile >= 600:
                return D(id_, "eskaluj", f"{powod} od {round(ile / 60)} min po zalogowaniu", "przypiety-brak", klasa="eskalacja", kod_eskalacji="nieustalony")
            return D(id_, "czekaj", powod + "; czekam (do 10 min po zalogowaniu)", "przypiety-czeka")
        tab = self.tabela_spotow()
        if tab is None or tab.blad:
            if not self._ostrzezono_tabele:
                self._ostrzezono_tabele = True
                self.wpisz(teraz, D("*", "ostrzezenie", (tab.blad if tab else "brak dane_tibia/spoty_nadzorca.json")
                                    + ": wybór spotu wyłączony, start na bieżącej mapie z tryb.log (jak przed Q5)", "spoty-brak-tabeli"), "ostrzezenie")
            mapa, tryb, skad = self._mapa_zmiany(id_, zm)
            return {"mapa": mapa, "tryb": tryb, "skad": skad, "spot": None}
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

    def zostan_stan(self, id_, st):
        """Do `stan`: ile refilli od wpisu i czy flaga jest TERAZ uzbrojona (bez skutków ubocznych)."""
        z = self.zostan_depo_pc(id_)
        return {"refille_od_wpisu": len(ZD.refille_od_wpisu(z, self.kat(id_))) if z and z.po_refillach else 0,
                "zostan_uzbrojone": bool(z and self.zostan_w_depo(id_, st))}

    def wyloguj_w_depo(self, id_):
        z = self.zostan_depo_pc(id_)
        return bool(z and z.wyloguj)

    def _wylogowanie_w_depo(self, id_, o, a, st, teraz, zostaje):
        """24.10 (Karol: „zakończyć i wylogować się w depo”): uzbrojona postać z `wyloguj_w_depo` stoi w depo ze STOP (bez bota): wylogowanie jak na koniec
        zmiany (spokój, nie w serwisie, 3 porażki = eskalacja, jedna postać naraz i odstęp logowań w pętli zdarzeń), kod `plan-wyloguj-depo` = także na
        żywo przy NADZOR_NAPRAWY. Offline znacznik `zostan_depo_od` + STOP trzymają ją w depo (zostaje-offline), bez relogu."""
        if o["serwis_dziala"] or o.get("refill_trwa"):
            return D(id_, "czekaj", f"stoi w depo ze STOP (zostan_w_depo: {zostaje}): czekam na koniec serwisu / refillu przed wylogowaniem", "wyloguj-depo-serwis")
        if st.get("wylog_bl", 0) >= 3:
            return D(id_, "eskaluj", f"stan nieustalony: wylogowanie w depo nieudane {st['wylog_bl']} razy (ostatni kod {st.get('wylog_kod')})",
                     "wylog-nieudane", klasa="eskalacja", kod_eskalacji="nieustalony")
        if a.get("walka"):
            return D(id_, "czekaj", "stoi w depo ze STOP: czekam na spokój (walka w ostatnich 20 s) przed wylogowaniem", "wyloguj-depo-spokoj")
        return D(id_, "wyloguj", f"zostan_w_depo ({zostaje}): zadanie wykonane, postać w depo ze STOP: wyloguj.sh i zamknięcie sesji, bez ponownego logowania",
                 "plan-wyloguj-depo", klasa="zdarzenie")

    # --- przerwa postaci (24.10, Karol: „nadzorca ma sam robić przerwy postaci i ewentualnie zmieniać spot”; SPEC_przerwa_postaci_1024) ---
    def przerwa_pc(self, id_):
        """PR.Przerwa niezakończona albo None (brak wpisu, wpis błędny, plan nieczytelny, już zrobiona). Wyłącznik (NADZOR_PRZERWY=0 / „przerwy”: false) gasi tylko
        NOWE przerwy: trwająca (`wylogowano_t`) kończy się powrotem, żeby postać nie zostawała offline."""
        plan = self.plan_postaci()
        if plan.nieczytelny:
            return None
        pc = plan.postacie.get(id_)
        pr = pc.przerwa if pc is not None else None
        if pr is None or pr.zrobione_t:
            return None
        if not pr.wylogowano_t and not PR.wlaczone(self.konf):
            return None
        return pr

    def _pz(self, id_, pola, warunek=None):
        """Zapis pól stanu przerwy do planu (flock + atomowo) i unieważnienie odczytanego planu tego obiektu (następny odczyt widzi zapis)."""
        ok = PP.przerwa_zapisz(self.korzen, id_, pola, warunek=warunek)
        self._plan = None
        return ok

    def przerwa_trwa(self, id_):
        pr = self.przerwa_pc(id_)
        return bool(pr and pr.wylogowano_t)

    def _przerwa_stop_wiek_s(self, id_, teraz):
        try:
            return teraz.timestamp() - (self.kat(id_) / "STOP").stat().st_mtime
        except OSError:
            return 0.0

    def _przerwa_offline(self, id_, o, st, teraz, zm, cisza):
        """Offline: przerwa uzbrojona na `teraz` zaczyna odliczanie od razu; trwająca czeka do `do_t` (nie logujemy wcześniej, nie w ciszy nocnej) i wtedy
        zleca start sesji (kod plan-przerwa-powrot: jedna akcja logowania na przebieg, odstęp i komplet online jak każdy sesja_start). -> decyzja albo None."""
        pr = self.przerwa_pc(id_)
        if pr is None:
            return None
        if not pr.wylogowano_t:
            if pr.kiedy != "teraz":
                return None
            return D(id_, "przerwa_start", f"przerwa {pr.min} min od razu: postać jest offline, zaczynam odliczanie", "plan-przerwa-start", klasa="naprawa")
        do = pr.do_ts()
        if do is None or teraz.timestamp() < do:
            return D(id_, "czekaj", f"przerwa: offline do {pr.do_t[11:16]} ({pr.min} min ± {pr.rozrzut_min})", "plan-przerwa-czeka")
        if cisza:
            return D(id_, "czekaj", f"przerwa skończona ({pr.do_t[11:16]}), ale cisza nocna: zero logowań", "plan-przerwa-cisza")
        if st.get("start_bl", 0) >= 3:
            return D(id_, "eskaluj", "przerwa: start sesji po przerwie nieudany 3 razy z rzędu", "start-nieudany", klasa="eskalacja", kod_eskalacji="wyczerpana")
        return D(id_, "sesja_start", f"przerwa skończona ({pr.do_t[11:16]}): start sesji, logowanie i refill.sh --spot (bez zakupów)", "plan-przerwa-powrot",
                 klasa="zdarzenie", przerwa=True)

    def _przerwa_online(self, id_, o, a, st, teraz):
        """Online i w grze: (1) przerwa trwa (wylogowana i znów zalogowana przez nas): po `do_t` start z miasta (`_przerwa_spot`); (2) przerwa uzbrojona:
        postać stoi w mieście ze STOP po refillu bez wyjścia (znacznik przerwa_refill.ok) albo, dla `kiedy: teraz`, w depo bez refillu w toku -> wylogowanie;
        `kiedy: teraz` z działającym botem -> powrót do miasta (WROC). Poza tym None (normalny przepływ). Bramki (STOP_RECZNY, pauza, hold) odrzucił decyduj."""
        pr = self.przerwa_pc(id_)
        if pr is None:
            return None
        if pr.wylogowano_t:
            if o["bot"]:
                return D(id_, "przerwa_juz", "przerwa: bot już działa po powrocie (start poza moim powrotem): kończę przerwę", "plan-przerwa-juz", klasa="naprawa")
            do = pr.do_ts()
            if do is None or teraz.timestamp() < do:
                return D(id_, "czekaj", f"przerwa do {pr.do_t[11:16]}: sesja jeszcze wygasa albo ktoś zalogował postać wcześniej; nie ruszam", "plan-przerwa-wygasa")
            if not st.get("sesja_nasza"):
                return D(id_, "czekaj", "przerwa skończona, ale postać zalogowana nie przeze mnie (ręczna gra?): nie startuję bota", "plan-przerwa-obca")
            if o["serwis_dziala"] or o["wroc"] or o["wyprawa"]:
                return D(id_, "czekaj", "przerwa skończona: serwis / powrót w toku, czekam", "plan-przerwa-zajety")
            return self._przerwa_spot(id_, o, a, st, teraz, pr)
        if o["bot"]:
            if pr.kiedy != "teraz" or o["wroc"] or o["wyprawa"]:
                return None
            if a.get("walka"):
                return D(id_, "czekaj", "przerwa od razu: czekam na spokój (walka w ostatnich 20 s) przed powrotem do miasta", "plan-przerwa-walka")
            w = st.get("przerwa_wroc") or {}
            if w and ts_ep(teraz) - w.get("ts", 0) < 20 * 60:
                return D(id_, "czekaj", f"przerwa od razu: powrót zlecony o {datetime.fromtimestamp(w['ts']):%H:%M}, czekam na efekt", "plan-przerwa-wroc-zlecony")
            if w.get("n", 0) >= 3:
                return D(id_, "eskaluj", f"przerwa od razu: powrót do miasta zlecony {w['n']} razy, bot nadal działa", "przerwa-wroc-bez-efektu",
                         klasa="eskalacja", kod_eskalacji="nieustalony")
            return D(id_, "wroc", f"przerwa {pr.min} min od razu" + (f" ({pr.powod})" if pr.powod else "") + ": zlecam powrót do miasta", "plan-przerwa-wroc",
                     klasa="naprawa", problem="przerwa")
        if not o["stop"]:
            return None
        znacznik = PR.marker_refill(self.kat(id_), teraz.timestamp())
        miasto = bool(self._w_depo(o, a) or o["panel"].get("w_miescie"))
        if znacznik is None:
            if pr.kiedy != "teraz" or not miasto:
                return None
            # Uzbrojona przerwa „od razu” trzyma postać, dopóki bramka nie puści: zwykły przepływ (faza POWROT po WROC) zrobiłby z niej „koniec zmiany”
            # (serwis + wylogowanie BEZ przerwy = postać offline na zawsze) w trybie NADZOR_ZYWO, a w cieniu zaśmiecił odstęp między zdarzeniami.
            if o["panel"].get("wroc_refill") not in (None, "", "pominiety", "brak_planu"):
                return D(id_, "czekaj", "przerwa od razu: auto-refill czeka / trwa / padł, wylogowuję po nim (refill bez wyjścia)", "plan-przerwa-refill")
            if self._przerwa_stop_wiek_s(id_, teraz) < 120:
                return D(id_, "czekaj", "przerwa od razu: STOP świeży (< 2 min), daję auto-refillowi szansę na start", "plan-przerwa-stop-swiezy")
        return self._przerwa_wyloguj(id_, o, a, st, teraz, pr, znacznik is not None)

    def _przerwa_wyloguj(self, id_, o, a, st, teraz, pr, po_refillu):
        """Wylogowanie na przerwę: bramki jak `_wylogowanie_w_depo` (nie w serwisie, 3 porażki = eskalacja, spokój), kod plan-przerwa-wyloguj (na żywo)."""
        if o["serwis_dziala"]:
            return D(id_, "czekaj", "przerwa: czekam na koniec serwisu przed wylogowaniem", "plan-przerwa-serwis")
        if st.get("wylog_bl", 0) >= 3:
            return D(id_, "eskaluj", f"stan nieustalony: wylogowanie na przerwę nieudane {st['wylog_bl']} razy (ostatni kod {st.get('wylog_kod')})",
                     "wylog-nieudane", klasa="eskalacja", kod_eskalacji="nieustalony")
        if a.get("walka"):
            return D(id_, "czekaj", "przerwa: czekam na spokój (walka w ostatnich 20 s) przed wylogowaniem", "plan-przerwa-spokoj")
        return D(id_, "wyloguj", f"przerwa {pr.min} min ± {pr.rozrzut_min}" + (f" ({pr.powod})" if pr.powod else "")
                 + (": refill zrobiony bez wyjścia, " if po_refillu else ": ") + "postać w mieście ze STOP: wyloguj.sh i zamknięcie sesji, powrót po przerwie",
                 "plan-przerwa-wyloguj", klasa="zdarzenie", przerwa=True)

    def _przerwa_nowy_spot(self, id_, o, st, teraz, pr):
        """(mapa, tryb, powód) nowego spotu po przerwie albo (None, None, powód): gracz przeszkadzał (nick w `gracz` / `gracz_wykryty`) albo dotychczasowa
        jaskinia jest zajęta przez innego bota (jeden bot na jaskinię). Spot przypięty i brak alternatywy = zostaje stary."""
        biez_mapa, biez_tryb, _skad = mapa_tryb_biezace(self.korzen, id_, teraz)
        gracz = pr.gracz or pr.gracz_wykryty
        tab = self.tabela_spotow()
        jask = (lambda m: tab.jaskinia_mapy(m)) if (tab is not None and not tab.blad) else (lambda m: m)       # noqa: E731
        zajeta = bool(biez_mapa) and jask(biez_mapa) in {jask(m) for m in self._zajete_mapy(id_)}
        if not biez_mapa:
            return None, None, "bieżącej mapy nie ustalam (tryb.log): bez zmiany spotu"
        powody = []
        if pr.zmien_spot == "jesli_gracz" and gracz:
            powody.append(f"gracz {gracz}")
        if zajeta:
            powody.append(f"jaskinia {jask(biez_mapa)} zajęta przez innego bota")
        if not powody:
            return None, None, "bez zmiany spotu" + ("" if pr.zmien_spot == "jesli_gracz" else " (zmien_spot: nie)")
        pin = self.spot_przypiety(id_)
        if pin:
            return None, None, f"spot przypięty ({pin}): zostaje {biez_mapa}"
        if self.profil(id_).get("spoty_zapasowe") or tab is None or tab.blad:
            s = self.spot_zapasowy(id_, biez_mapa, self._zajete_mapy(id_))
            if not s:
                return None, None, f"{' + '.join(powody)}, ale brak spotu zapasowego: zostaje {biez_mapa}"
            return s[0], s[1] or biez_tryb, f"{' + '.join(powody)}: spot zapasowy {s[0]}"
        w = self.wybierz_spot(id_, o.get("panel"), o.get("gracz"), teraz, biez_mapa, f"przerwa-{teraz:%H%M}", dodatkowo_zajete=(biez_mapa,))
        if not w or not w.get("mapa"):
            return None, None, f"{' + '.join(powody)}, ale brak wolnego spotu ({(w or {}).get('powod', 'brak tabeli')}): zostaje {biez_mapa}"
        return w["mapa"], biez_tryb, f"{' + '.join(powody)}: {w['powod']}"

    def _przerwa_spot(self, id_, o, a, st, teraz, pr):
        """Powrót po przerwie: `refill.sh --spot` na tym samym albo nowym spocie (decyzja `przerwa_spot`, kod plan-przerwa-spot)."""
        mapa, tryb, powod = self._przerwa_nowy_spot(id_, o, st, teraz, pr)
        if st.get("przerwa_spot_bl", 0) >= 3:
            return D(id_, "eskaluj", f"przerwa: refill.sh --spot nieudany {st['przerwa_spot_bl']} razy po powrocie z przerwy", "przerwa-spot-nieudany",
                     klasa="eskalacja", kod_eskalacji="nieustalony")
        return D(id_, "przerwa_spot", f"po przerwie ({pr.do_t[11:16]}): start z miasta (refill.sh --spot, bez zakupów); " + powod, "plan-przerwa-spot",
                 klasa="bot", mapa=mapa, tryb=tryb, nowy_spot=bool(mapa))

    def _przerwa_zapisz_wylogowanie(self, teraz, id_, pr):
        """PRZED wylogowaniem: `wylogowano_t`, `do_t` i `gracz_wykryty` do planu (atomowo). Postać wylogowana bez śladu w planie byłaby zapomniana offline.
        -> do_t (tekst) albo None, gdy zapis się nie udał (wtedy nie wylogowujemy)."""
        do = PR.losuj_do(pr, teraz).strftime(PR.FMT)
        gracz = pr.gracz
        if not gracz and pr.zmien_spot == "jesli_gracz":
            gracz = PR.gracze_w_logu(self.kat(id_), teraz, wlasne=PR.nicki_wlasne(self.korzen))
        pola = {"wylogowano_t": teraz.strftime(PR.FMT), "do_t": do, "gracz_wykryty": gracz or None}
        if not self._pz(id_, pola, warunek=lambda w: not w.get("wylogowano_t") and not w.get("zrobione_t")):
            return None
        return do

    def _przerwa_cofnij_wylogowanie(self, id_):
        self._pz(id_, {"wylogowano_t": None, "do_t": None, "gracz_wykryty": None},
                          warunek=lambda w: bool(w.get("wylogowano_t")) and not w.get("zrobione_t"))

    def _wykonaj_przerwa_spot(self, teraz, id_, d, st, W):
        arg = d["arg"]
        ok, txt = W.refill_spot(id_, arg.get("mapa"), arg.get("tryb"))
        if not ok:
            st["przerwa_spot_bl"] = st.get("przerwa_spot_bl", 0) + 1
            return False, txt
        st.pop("przerwa_spot_bl", None)
        pola = {"zrobione_t": teraz.strftime(PR.FMT)}
        if arg.get("mapa"):
            pola["nowy_spot"] = arg["mapa"]
        self._pz(id_, pola, warunek=lambda w: not w.get("zrobione_t"))
        (self.kat(id_) / PR.MARKER_REFILL).unlink(missing_ok=True)
        st["faza"], st["powrot_od"] = "POWROT", ts_ep(teraz)
        st.pop("przerwa_wroc", None)
        if arg.get("mapa"):
            self.zapamietaj_spot(id_, st, arg["mapa"], teraz)
        W.powiadom_info(id_, f"{id_}: koniec przerwy"[:80], d["powod"][:300])
        return True, txt + (f" (nowy spot {arg['mapa']})" if arg.get("mapa") else "")

    # --- przebieg ---
    def tick(self):
        teraz = self.zegar()
        konf = self.konf = G.wczytaj_konfig(self.korzen)
        self.raport = []
        self._tab_ladowana, self._przypisane, self._obs = False, {}, {}     # tabela spotów i przypisania są na jeden przebieg
        self._plan, self._plan_czeka = None, []
        self._kod_bota, self._restart_kod_w_przebiegu = None, False
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
        pl_bledy = self.plan_postaci().bledy
        if pl_bledy:
            self.wpisz(teraz, D("*", "ostrzezenie", "plan_postaci.json: " + "; ".join(pl_bledy)[:400] + " (błędne kroki pomijam; przy nieczytelnym pliku nikogo nie przenoszę)",
                                "plan-blad"), "ostrzezenie")
        self._raw = {r["id"]: r for r in raw_lista}
        online_teraz = sorted(i for i, r in self._raw.items() if r.get("sesja") or r.get("gra"))
        glob = self.stan["globalne"]
        if glob.get("online") is not None and sorted(glob["online"]) != online_teraz:
            if ts_ep(teraz) - (glob.get("ostatnie_zdarzenie") or 0) > 150:
                glob["ostatnie_zdarzenie"] = ts_ep(teraz)
                self.wpisz(teraz, D("*", "zdarzenie_zewn", f"zmiana liczby sesji {glob['online']} -> {online_teraz} bez naszej akcji", "zewn-" + ",".join(online_teraz)), "info")
        glob["online"] = online_teraz
        ids = G.pula(self.korzen, konf)
        poza = G.poza_pula(self.korzen, konf, teraz)
        for id_ in online_teraz:      # aktywna sesja poza pulą nie jest pilnowana: nie wolno tego robić po cichu
            if id_ not in ids:
                self.wpisz(teraz, D(id_, "ostrzezenie", f"sesja online, ale poza nadzorem: {poza.get(id_) or 'brak katalogu instancji'}", "poza-nadzorem"), "ostrzezenie")
        plan, utworzono = G.plan_dla(teraz, self.korzen, konf, online={i: {"od": None} for i in online_teraz if i in ids}, zapis=self.zapis)
        if utworzono:
            self.wpisz(teraz, D("*", "grafik", f"brak grafiku doby: wygenerowano ({plan['zrodlo']}, {len(plan['zmiany'])} zmian)", "grafik-nowy"), "info")
        kandydaci = []
        for id_ in ids:
            odmowa = self.bramka(id_)
            st = self.post(id_)
            raw = self._raw.get(id_)
            if odmowa:
                st.pop("wroc_koniec", None)     # STOP_RECZNY / pauza postaci / hold: zlecenie powrotu nie dotyczy już tej sytuacji
                st.pop("wroc_poziom", None)
                self.wpisz(teraz, D(id_, "zablokowane", odmowa, "bramka-" + odmowa[:12]), "info")
                self._ponow_powiadomienie(teraz, id_)
                if raw and not (raw.get("sesja") or raw.get("gra")) and st.get("faza") != "OFFLINE":
                    self.licz_wylogowanie(id_, teraz)
                    st["faza"] = "OFFLINE"
                continue
            try:
                o = self.obserwuj(id_, raw, teraz)
                self._obs[id_] = o
                self.zapamietaj_poziom(id_, o, teraz)
                dec = self.decyduj(id_, o, plan, teraz)
                kandydaci.extend((pid, pd, o) for pid, pd in self._plan_czeka)
                self._plan_czeka = []
                for d in dec:
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
                if self.zostaje_w_depo(id_, o, self.post(id_)):
                    self.wpisz(teraz, D(id_, "spot_podglad", f"stoi w depo ze STOP (zostan_w_depo): zostaje w depo, bez wyboru spotu", "podglad-zostaje-w-depo"),
                               "cień", szczegol="podgląd, bez akcji")
                    continue
                pin = self.spot_przypiety(id_)
                if pin:     # spot przypięty (Karol 23.10): zero propozycji innej jaskini; bieżąca zostaje zarezerwowana dla pozostałych
                    if biez:
                        rezerwacje[id_] = biez
                    self.wpisz(teraz, D(id_, "spot_podglad", f"teraz na {biez or '?'}; spot przypięty ({pin}): przy starcie zmiany zostaje na {biez or 'bieżącym'}",
                                        "podglad-przypiety"), "cień", szczegol="podgląd, bez akcji")
                    continue
                w = self.wybierz_spot(id_, o.get("panel"), o.get("gracz"), teraz, biez, "podglad", zajete=set(rezerwacje.values()), z_depo=True)
            except Exception as e:      # noqa: BLE001
                self.wpisz(teraz, D(id_, "brak", f"podgląd spotu nieudany: {e!r}", "spot-podglad-wyjatek"), "blad")
                continue
            pam = self._poziom_z_pamieci.get(id_)
            dopisek = f" (poziom {pam[0]} z odczytu {self._kiedy(pam[1], teraz)}; bieżącego odczytu brak)" if pam else ""
            if w["mapa"]:
                rezerwacje[id_] = w["mapa"]
                tekst = f"teraz na {biez or '?'}; przy starcie zmiany wybrałbym: {w['powod']}{dopisek}"
                kod = "podglad-" + w["mapa"]
            else:
                tekst = f"teraz na {biez or '?'}; przy starcie zmiany: {w['powod']}{dopisek}" + (" [eskalacja brak_spotu]" if w["brak"] == "spot" else " [czekam na dane]")
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
            if d["kod"] == "plan-brak":
                self._ostrzez_plan_brak(teraz, id_, d)
            return True, ""
        # B-2: bramki (STOP_RECZNY, NADZOR_PAUZA, nadzor:false, hold) sprawdzane ZNOWU tuż przed każdą akcją, nie tylko raz na przebieg
        odmowa = self.bramka(id_, czy_hold=(akcja != "eskaluj"))
        if odmowa:
            self.wpisz(teraz, D(id_, "zablokowane", f"{akcja} wstrzymane tuż przed wykonaniem: {odmowa}", "bramka-przed-" + akcja), "odmowa")
            return False, odmowa
        if akcja == "eskaluj":
            return self.eskaluj(teraz, id_, d)
        if self.zywo is False and self._wykonawca_dla(d) is self.wykonawca:
            self._zapisz_wroc_koniec(st, d, teraz)
            self._zapisz_wroc_poziom(st, d, teraz, True, "cien")
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
        akcja, arg, W = d["akcja"], d["arg"], self._wykonawca_dla(d)
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
                    if arg.get("zmiana_od"):
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
                mapa_s, tryb_s, r_plan = arg.get("mapa"), arg.get("tryb"), None
                if arg.get("plan_kroki"):       # plan: sprawdź jeszcze raz tuż przed startem (zajętość mogła się zmienić), zużyj po udanym starcie
                    r_plan = self._plan_start(id_, teraz, arg.get("poziom"), mapa_tryb_biezace(self.korzen, id_, teraz)[:2])
                    if r_plan is None:
                        ok, txt = False, "plan: krok niewykonalny w chwili startu (spot zajęty albo plan zmieniony); start w następnym przebiegu"
                    else:
                        mapa_s, tryb_s = r_plan["mapa"], r_plan["tryb"]
                if not arg.get("plan_kroki") or r_plan is not None:
                    ok, txt = W.start_bota(id_, mapa_s, tryb_s)
                    if ok:
                        st["bot_start"], st["faza"] = ts_ep(teraz), "DOJSCIE"
                        if mapa_s:
                            self.zapamietaj_spot(id_, st, mapa_s, teraz)
                        if r_plan is not None:
                            self._plan_zuzyj(id_, r_plan, teraz, W)
            elif akcja in ("plan_tryb", "plan_blanki", "plan_mapa", "plan_juz") or (akcja == "wroc" and arg.get("problem") == "plan"):
                ok, txt = self._wykonaj_plan(teraz, id_, d, st, W)
            elif akcja in ("restart", "wznow", "zmien_spot"):
                po_kodzie = arg.get("problem") == "kod"
                gracz_sp = akcja == "zmien_spot" and arg.get("problem") == "spot_gracz"
                ok, txt = self._restart(teraz, id_, akcja, st, W=W, zalicz=not (po_kodzie or gracz_sp),
                                        cel=(arg.get("mapa"), arg.get("tryb")) if gracz_sp else None)
                if gracz_sp:
                    self._spot_gracz_po(teraz, id_, d, st, ok, txt, W)
                if po_kodzie:
                    pr = st.get("restart_kod") or {}
                    st["restart_kod"] = {"mtime": arg.get("mtime"), "proby": (pr.get("proby", 0) + 1) if pr.get("mtime") == arg.get("mtime") else 1}
                    if ok:
                        st["restart_kod_ts"] = self.stan["globalne"]["ostatni_restart_kod"] = ts_ep(teraz)
            elif akcja == "zamknij_sesje":
                ok, txt = W.zamknij_sesje(id_)
                if ok:
                    st["sesja_zamknieta_ts"] = ts_ep(teraz)     # faza OFFLINE i liczenie minut: następny przebieg (offline w decyduj)
            elif akcja == "powiadom_info":
                ok, txt = W.powiadom_info(id_, f"{arg.get('nick')}: czar {arg.get('czar')} nie działa",
                                          f"{d['powod']}. Bot ponawia próby co ~10 min. Zalecenie Karola (23.10): postać, która nie zna czaru, trenuje ML tym, "
                                          "co umie (ML_CZAR_AKTYWNY=1, ZDROWIE_CZAR_AKTYWNY=0 w na_zywo.json; uwaga: tryb.py ostrozny/ml przy każdym "
                                          "starcie ustawia ZDROWIE_CZAR_AKTYWNY=1 z powrotem).")
                if ok:
                    st["czar_info_ts"] = ts_ep(teraz)
            elif akcja == "relog_wylog":
                ok, txt = W.relog_kolejka(id_)
                if ok:
                    st["relog_wylog_ts"] = ts_ep(teraz)
            elif akcja == "wroc":
                ok, txt = W.wroc(id_)
                if ok:
                    st["faza"], st["powrot_od"] = "POWROT", ts_ep(teraz)
                    self._zapisz_wroc_koniec(st, d, teraz)
                self._zapisz_wroc_poziom(st, d, teraz, ok, "zywo")
                if d.get("arg", {}).get("problem") == "przerwa":
                    st["przerwa_wroc"] = {"ts": ts_ep(teraz), "n": (st.get("przerwa_wroc") or {}).get("n", 0) + 1}
                if d.get("arg", {}).get("problem") == "spot_gracz_wroc":
                    self._spot_gracz_po(teraz, id_, d, st, ok, txt, W)        # 26.10: powrót po spotkaniach graczy (limity, unikany spot, znacznik „zostaje w depo”)
                if d.get("arg", {}).get("problem") not in ("koniec", "poziom", "przerwa", "spot_gracz_wroc"):
                    st.setdefault("naprawy", []).append([ts_ep(teraz), "wroc"])
                if ok and d.get("arg", {}).get("problem") == "poziom":
                    nok, ntxt = self._powiadom_wyrosl(id_, d, W)
                    txt = f"{txt} | {ntxt}"
            elif akcja == "serwis":
                ok, txt = W.serwis(id_)
                if ok:
                    st["serwis_start"] = ts_ep(teraz)
                st["serwis_blad"] = st.get("serwis_blad", 0)
            elif akcja == "przerwa_start":
                pr = self.przerwa_pc(id_)
                do = self._przerwa_zapisz_wylogowanie(teraz, id_, pr) if pr is not None and not pr.wylogowano_t else None
                ok, txt = (True, f"przerwa do {do[11:16]}") if do else (False, "przerwa: nie zapisano do planu (już trwa, zrobiona albo plan nieczytelny)")
            elif akcja == "przerwa_juz":
                ok = self._pz(id_, {"zrobione_t": teraz.strftime(PR.FMT)}, warunek=lambda w: not w.get("zrobione_t"))
                txt = "przerwa zakończona (bot działa)" if ok else "przerwa: nie zapisano do planu"
                (self.kat(id_) / PR.MARKER_REFILL).unlink(missing_ok=True)
            elif akcja == "przerwa_spot":
                ok, txt = self._wykonaj_przerwa_spot(teraz, id_, d, st, W)
            elif akcja == "wyloguj":
                przerwa_do = None
                if arg.get("przerwa"):          # 24.10: przerwa postaci: najpierw ślad w planie (do_t), dopiero potem wylogowanie
                    pr = self.przerwa_pc(id_)
                    przerwa_do = self._przerwa_zapisz_wylogowanie(teraz, id_, pr) if pr is not None and not pr.wylogowano_t else None
                    if przerwa_do is None:
                        return False, "przerwa: nie zapisano do planu (już trwa, zrobiona albo plan nieczytelny): nie wylogowuję"
                ok, txt = W.wyloguj(id_)
                if przerwa_do and not ok:
                    self._przerwa_cofnij_wylogowanie(id_)
                if przerwa_do and ok:
                    (self.kat(id_) / PR.MARKER_REFILL).unlink(missing_ok=True)
                    txt = f"{txt} | przerwa do {przerwa_do[11:16]}"
                    W.powiadom_info(id_, f"{id_}: przerwa do {przerwa_do[11:16]}"[:80], d["powod"][:300])
                if not ok:
                    st["wylog_bl"] = st.get("wylog_bl", 0) + 1
                    st["wylog_kod"] = _kod(txt)
                    if _kod(txt) == 6:
                        self.eskaluj(teraz, id_, D(id_, "eskaluj", "zgon (wyloguj.sh kod 6)", "zgon-wyloguj", klasa="eskalacja", kod_eskalacji="zgon"))
                if ok:
                    self.licz_wylogowanie(id_, teraz)
                    if not arg.get("przerwa"):      # przerwa postaci nie kończy zmiany z grafiku (inaczej powrót wyglądałby na „sesję po wylogowaniu”)
                        st["zakonczone"] = (st.get("zakonczone", []) + [st.get("zmiana_od")])[-30:]
                    st["faza"], st["ostatnie_wylog"] = "OFFLINE", ts_ep(teraz)
                    for k in ("serwis_start", "serwis_koniec", "serwis_blad", "wylog_od", "koniec", "bot_start", "stoi_w_depo_od", "zmiana_od", "naprawy", "sesja_nasza", "bot_widziany", "wylog_bl", "wylog_kod", "powrot_od", "stoi_w_depo_od", "spot", "wroc_koniec", "przerwa_wroc", "przerwa_spot_bl"):
                        st.pop(k, None)
            elif akcja == "relog":
                ok, txt = self._relog(teraz, id_, st)
            elif akcja == "okna":
                st["okna_ts"] = ts_ep(teraz)
                ok, txt = W.okna(id_)
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

    def _restart(self, teraz, id_, akcja, st, W=None, zalicz=True, cel=None):
        """restart / wznow / zmien_spot: bot na BIEŻĄCEJ mapie i trybie (tryb.log), zmien_spot na zapasowym. Restart tylko poza walką.
        `zalicz=False` (restart po zmianie kodu): nie wpisuje próby do `naprawy` (drabina: 3 restarty = eskalacja, a to nie awaria)."""
        W = W or self.wykonawca
        raw = getattr(self, "_raw", {}).get(id_) or {}
        o_log = analizuj_log(czytaj_log(najnowszy_log(self.kat(id_) / "logi"), teraz), ts_ep(teraz))
        if akcja in ("restart", "zmien_spot") and raw.get("bot") and o_log.get("walka"):
            return False, f"bot w walce: {akcja} odroczony"
        mapa, tryb, skad = mapa_tryb_biezace(self.korzen, id_, self.zegar())
        nowy_spot = None
        if akcja == "zmien_spot":
            pin = self.spot_przypiety(id_)
            if pin:
                return False, f"spot przypięty ({pin}): zmiana spotu tylko z wpisem Karola w plan_postaci.json"
            if cel and cel[0]:                          # 26.10 spot_gracz: nowy spot wybrany przez decyzję w tym samym przebiegu
                mapa, tryb, nowy_spot, skad = cel[0], cel[1] or tryb, cel[0], "spot_gracz (gracz przeszkadza)"
            elif self.profil(id_).get("spoty_zapasowe") or self.tabela_spotow() is None or self.tabela_spotow().blad:
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
            if zalicz:
                st.setdefault("naprawy", []).append([ts_ep(teraz), akcja])
            return False, "start bota anulowany po zatrzymaniu: " + odmowa
        r_plan = None
        if akcja in ("restart", "wznow"):       # 23.10: zaplanowana mapa/tryb „na następny start” obowiązuje także po restarcie i wznowieniu
            r_plan = self._plan_start(id_, teraz, self.poziom_z_odczytu(raw.get("gracz"), raw.get("panel")), (mapa, tryb))
            if r_plan:
                mapa, tryb, skad = r_plan["mapa"], r_plan["tryb"], "plan: krok " + ", ".join(r_plan["kroki"])
        ok, txt = W.start_bota(id_, mapa, tryb)
        if zalicz:
            st.setdefault("naprawy", []).append([ts_ep(teraz), akcja])
        if ok:
            st["bot_start"], st["faza"] = ts_ep(teraz), "DOJSCIE"
            st["stoi_w_depo_od"] = None
            if nowy_spot:
                self.zapamietaj_spot(id_, st, nowy_spot, teraz)
            if r_plan:
                self._plan_zuzyj(id_, r_plan, teraz, W)
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
        if d["arg"].get("wroc_koniec") and st.get("wroc_koniec"):
            st["wroc_koniec"]["eskalowano"] = ts_ep(teraz)      # jedna eskalacja na zlecenie powrotu (potem cisza, nie co eskalacja_powtorz_min)
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
        self._plan = None
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
        pin = self.spot_przypiety(id_) if rodzaj == "zmien_spot" else None
        zostaje = self.zostaje_w_depo(id_, o, self.post(id_)) if rodzaj in ("restart", "wznow", "zmien_spot", "relog", "wyloguj") else None
        if zostaje:
            blok = f"postać zostaje w depo (zostan_w_depo: {zostaje}): {rodzaj} tylko na polecenie Karola"
        elif pin:
            blok = f"spot przypięty ({pin}): zmiana spotu tylko z wpisem Karola w plan_postaci.json"
        elif rodzaj in ("restart", "wznow", "zmien_spot", "wroc", "wyloguj", "relog", "wroc_poziom", "zamknij_sesje") and not o["online"] and rodzaj != "relog":
            blok = "postać offline (brak sesji)"
        elif rodzaj in ("restart", "wznow", "zmien_spot") and wyn:
            blok = "zdarzenie dla Karola (PK/zgon/GM/IP): " + wyn[0]["powod"]
        elif rodzaj == "wznow" and (o["bot"] or not o["stop"]):
            blok = "wznow dotyczy bota zatrzymanego STOP po alarmie (bot działa albo brak STOP)"
        elif rodzaj in ("restart", "zmien_spot") and o["bot"] and a.get("walka"):
            blok = "bot w walce: restart tylko poza walką"
        elif rodzaj == "restart" and not o["bot"]:
            blok = "bot nie działa: użyj wznow"
        elif rodzaj in ("wroc", "wroc_poziom") and not o["bot"]:
            blok = "wroc.sh wymaga działającego bota"
        elif rodzaj == "wroc_poziom" and (o["wroc"] or o["wyprawa"]):
            blok = "bot już wraca do miasta (WROC / wyprawa w toku)"
        elif rodzaj == "wroc_poziom":
            wyr = self.decyzja_wyrosl(id_, o, a, self.post(id_), teraz)
            if wyr is None:
                blok = ("wroc_poziom tylko gdy poziom z gry > max spotu (widełki 'karol') bieżącej mapy; tu tego nie ma "
                        "(brak odczytu poziomu, spot bez widełek Karola albo poziom w widełkach)")
            elif wyr["akcja"] != "wroc":
                blok = wyr["powod"]
        elif rodzaj == "relog" and not (a.get("rozl") or o["ekran"] in ("logowanie", "lista") or not o["w_grze"]):
            blok = "brak śladów rozłączenia (log bota, ekran) i klient w grze"
        elif rodzaj == "zamknij_sesje" and (o["bot"] or o["ekran"] not in ("lista", "logowanie")):
            blok = ("bot działa: zamykanie sesji tylko wylogowanej postaci" if o["bot"] else
                    f"klient nie jest na ekranie logowania ani liście postaci (ekran: {o['ekran']}): zamykam tylko wylogowane postacie")
        elif rodzaj == "wyloguj" and o["bot"]:
            blok = "bot działa: najpierw wroc (wylogowanie dopiero po powrocie do miasta)"
        elif rodzaj == "wyloguj" and a.get("walka"):
            blok = "walka w ostatnich 20 s: wylogowanie tylko w spokoju"
        elif rodzaj == "okna" and not o["online"]:
            blok = "postać offline (brak sesji): nie ma okien do sprawdzenia"
        elif rodzaj == "okna" and o["bot"] and a.get("walka_bez_lootu"):
            blok = "bot w walce: okna tylko poza walką"
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
        if rodzaj == "wroc_poziom":
            d = {**wyr, "powod": "obchód: " + wyr["powod"]}
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

    def poziom_do_stanu(self, id_, raw, blad_odczytu, teraz):
        """Pole `poziom` w `stan`: {wartosc, odczyt, zrodlo, powod}. Bieżący odczyt, ostatni znany (z datą) albo wartość None z jawnym powodem."""
        online = bool(raw and (raw.get("sesja") or raw.get("gra")))
        v = self.poziom_z_odczytu((raw or {}).get("gracz"), (raw or {}).get("panel")) if online else None
        if v is not None:
            return {"wartosc": v, "odczyt": teraz.strftime(FMT), "zrodlo": "odczyt teraz", "powod": None}
        zn = self.poziom_znany(id_, teraz)
        if online:
            powod = "bieżący odczyt z gry niedostępny (strażnik nie odpowiedział w limicie albo postać nie w grze)"
        elif blad_odczytu:
            powod = blad_odczytu
        else:
            powod = "postać offline"
        if zn:
            return {"wartosc": zn[0], "odczyt": zn[1], "zrodlo": "ostatni znany", "powod": powod}
        return {"wartosc": None, "odczyt": None, "zrodlo": None,
                "powod": f"brak odczytu z gry ({powod}) i brak zapamiętanego poziomu (nie starszego niż {self.konf.get('poziom_max_wiek_h', POZIOM_MAX_WIEK_H)} h)"}

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
        wynik["poza_nadzorem"] = G.poza_pula(self.korzen, self.konf, teraz)
        self._plan = None
        pl = self.plan_postaci()
        for b in pl.bledy:
            wynik["uwagi"].append("plan_postaci.json: " + b)
        try:        # tylko odczyt: bieżący stan z gry (okno_api stan) dla pola `poziom`; bez niego zostaje ostatni znany
            raw_stan, blad_odczytu = {r["id"]: r for r in self.zrodla.stan()}, None
        except Exception as e:      # noqa: BLE001
            raw_stan, blad_odczytu = {}, f"odczyt stanu nieudany: {e!r}"
        for id_ in G.pula(self.korzen, self.konf):
            st = self.post(id_)
            zm = G.aktywna_zmiana(plan, id_, teraz) if plan else None
            nast = next((z for z in G.zmiany_postaci(plan, id_) if z["od"] > teraz.strftime(FMT)), None) if plan else None
            if st.get("hold") and st["hold"].get("powiadomiono") is False:
                wynik["uwagi"].append(f"{id_}: WSTRZYMANA BEZ DOSTARCZONEGO POWIADOMIENIA ({st['hold'].get('powod')})")
            poz = self.poziom_do_stanu(id_, raw_stan.get(id_), blad_odczytu, teraz)
            wynik["postacie"][id_] = {"faza": st.get("faza"), "zmiana": zm and {k: zm[k] for k in ("od", "koniec", "wylog")},
                                      "nastepna": nast and nast["od"], "blok": self.bramka(id_), "hold": st.get("hold"), "spot": (st.get("spot") or {}).get("mapa"),
                                      "naprawy_w_oknie": len(self.naprawy_w_oknie(id_, teraz)),
                                      "poziom": poz, "plan": {**PP.opis_planu(self.korzen, id_, poz["wartosc"], teraz, pl), **self.zostan_stan(id_, st)},
                                      "zostan_w_depo": bool(self.zostan_depo_pc(id_)), "zostaje_w_depo_od": st.get("zostan_depo_od")}
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
    # NADZOR_NAPRAWY (env albo plik instancje/_wspolne/NADZOR_NAPRAWY), bez NADZOR_ZYWO: na żywo tylko naprawy z NAPRAWY_BEZ_ZYWO
    tylko_naprawy = not zywo_plik and (os.environ.get("NADZOR_NAPRAWY") == "1" or (G.wspolne(KORZEN) / "NADZOR_NAPRAWY").exists())
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
        # 23.10: przy NADZOR_NAPRAWY (bez NADZOR_ZYWO) grafik zostaje w cieniu, na żywo idzie tylko decyzja wroc_poziom (wyrósł ze spotu)
        nz = Nadzorca(zywo=zywo_plik, naprawy_poziom=tylko_naprawy)
        wydruk(nz.tick(), f"Nadzór ({'NA ŻYWO' if zywo_plik else 'CIEŃ' + (' + wroc_poziom NA ŻYWO' if tylko_naprawy else '')}) {nz.zegar():%Y-%m-%d %H:%M:%S}")
        return 0
    if a.cmd == "napraw":
        # 22.10 (Karol: obchód AI ma ratować postacie, grafik zostaje w cieniu): NADZOR_NAPRAWY=1 w środowisku albo plik
        # instancje/_wspolne/NADZOR_NAPRAWY włącza na żywo same naprawy z NAPRAWY_BEZ_ZYWO, bez NADZOR_ZYWO (logowania wg grafiku)
        if tylko_naprawy and a.rodzaj not in NAPRAWY_BEZ_ZYWO:
            # 22.10 10:17: obchód odesłał invincible'a do miasta (wroc) przez koniec zmiany z grafiku; bez NADZOR_ZYWO tylko ratunek
            # (23.10: zwykłe wroc nadal odmowa; wroc_poziom = powrót tylko z powodu „poziom > max spotu”, sprawdza to nadzorca)
            print(f"NAPRAWY: odmowa: rodzaj {a.rodzaj} niedozwolony bez NADZOR_ZYWO (tylko {', '.join(NAPRAWY_BEZ_ZYWO)})")
            return 3
        zywo_plik = zywo_plik or tylko_naprawy
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
