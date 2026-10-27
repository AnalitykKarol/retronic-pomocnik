"""Relog postaci, których bot sam się wylogował (23.10, decyzja Karola po resecie serwera: „Boty powinny być wyłączane po wylogowaniu od razu
i włączane ponownie”). Bot kończy proces i zostawia `instancje/<id>/wylogowany.json` (wylogowanie.py); TU jest „włączane ponownie”.

Kolejka, pojedynczo (decyzja Karola 22.10: odstęp między postaciami; jedna postać naraz):
  postać ze znacznikiem czeka >= RELOG_CZEKAJ_MIN min (po resecie serwera: do 10:11), potem
  sesja_gry zamknij -> sesja_gry start -> ekran logowania -> zaloguj.sh -> gra -> uruchom_instancje.sh <id> <mapa> <tryb> (RETRONIC_POSTAC)
  (strażnik widzi postać: uruchom.sh czeka sam do 60 s) -> pierwsze zabicie (max 6 min) -> losowa przerwa 3-6 min -> następna.

Rozróżnienie od ręcznej gry Karola (STOP_RECZNY): zatrzymaj.sh i `sesja_gry zamknij` same tworzą STOP_RECZNY, więc dawny relog uznałby
każdą postać za „Karol gra”. Kolejka ustawia RETRONIC_RELOG=1 (zatrzymaj.sh wtedy NIE tworzy STOP_RECZNY), a STOP_RECZNY, który istnieje
PRZED krokiem lub pojawi się w trakcie, zawsze oznacza Karola: postać pominięta, niczego nie kasujemy.

Moduł: czysta logika (`najwczesniej`, `kandydaci`, `relog_jednej`, `kolejka`) z wstrzykiwanym wykonawcą, zegarem i spaniem — testy offline —
oraz `WykonawcaRelog` (polecenia jak w ręcznym relogu 23.10) i CLI:
  python3 -I relog_wylogowanych.py kolejka       jedna kolejka (singleton: blokada _wspolne/relog_kolejka.lock); woła ją nadzor.py
  python3 -I relog_wylogowanych.py stan          kto czeka / kiedy gotowy (JSON)
"""
import fcntl
import json
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True
DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))
import instancja  # noqa: E402
import wylogowanie  # noqa: E402
RELOG_CZEKAJ_MIN = 10                 # tyle po wylogowaniu (po resecie: po godzinie resetu) czeka postać
RESET_SERWERA = (10, 0)               # godzina resetu serwera (zmierzone 23.10)
OKNO_RESETU_PRZED_MIN = 30            # wylogowanie w tym oknie przed resetem lub do RELOG_CZEKAJ_MIN po nim = „przez reset”
PRZERWA_S = (60, 150)                 # losowa przerwa między postaciami (24.10 Karol: „trochę szybciej”; było 180-360 s)
MAX_PROB = 3                          # tyle nieudanych relogów, potem eskalacja do Karola (nadzor.py)
PONOW_MIN = 5                         # odstęp między próbami tej samej postaci
ZNACZNIK_WAZNY_H = 12                 # starszy znacznik to nie świeże wylogowanie: nadzor go ignoruje
ZABICIE_LIMIT_S = 360
RE_EKRAN_START = r"enter_game|character_list|gra"
RE_ZABITY = re.compile(r"zabity")
RE_PROBLEM = re.compile(r"ALARM|ROZŁĄCZENIE|Traceback")
STAN_NAZWA = "relog_wylog.json"
SINGLETON = "relog_kolejka.lock"
ZAMEK_LOGOWANIA = "nadzor_logowanie.lock"     # ten sam co w nadzor.py: jedna akcja logowania naraz
ZAMEK_CZEKAJ_S = 180


def _kat(korzen, id_):
    return Path(korzen) / "instancje" / id_


def _wspolne(korzen):
    return Path(korzen) / "instancje" / "_wspolne"


def najwczesniej(ts, czekaj_min=RELOG_CZEKAJ_MIN, reset=RESET_SERWERA):
    """Epoka, od której postać wylogowana o `ts` może być zalogowana ponownie: ts + czekaj_min; gdy wylogowanie wypadło w okolicy resetu
    serwera (reset - 30 min .. reset + czekaj_min), nie wcześniej niż reset + czekaj_min + 1 min (10:11), bo serwer wstaje po resecie."""
    gotowe = ts + czekaj_min * 60
    t = datetime.fromtimestamp(ts)
    r = t.replace(hour=reset[0], minute=reset[1], second=0, microsecond=0)
    if r - timedelta(minutes=OKNO_RESETU_PRZED_MIN) <= t <= r + timedelta(minutes=czekaj_min):
        gotowe = max(gotowe, (r + timedelta(minutes=czekaj_min + 1)).timestamp())
    return gotowe


def stan_prob(kat):
    try:
        d = json.loads((Path(kat) / STAN_NAZWA).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def zapisz_stan_prob(kat, d):
    try:
        tmp = Path(kat) / (STAN_NAZWA + f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, Path(kat) / STAN_NAZWA)
    except OSError:
        pass


def profil(korzen, id_):
    try:
        return json.loads((_kat(korzen, id_) / "profil.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def bramka(korzen, id_):
    """Powód odmowy relogu postaci albo None. STOP_RECZNY = Karol gra (kolejka sama go nie tworzy: RETRONIC_RELOG=1)."""
    if (_wspolne(korzen) / "NADZOR_PAUZA").exists():
        return "NADZOR_PAUZA"
    if (_kat(korzen, id_) / "STOP_RECZNY").exists():
        return "STOP_RECZNY: Karol gra"
    if profil(korzen, id_).get("nadzor") is False:
        return "profil: nadzor false"
    return None


def kolejka_dziala(korzen):
    """True, gdy inny proces trzyma blokadę kolejki (sonda flock, nic nie zostawia)."""
    p = _wspolne(korzen) / SINGLETON
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return True
            fcntl.flock(f, fcntl.LOCK_UN)
    except OSError:
        return False
    return False


def ocen(korzen, id_, teraz_ts):
    """Stan relogu postaci -> {"id", "marker", "gotowa", "od" (epoka), "powod", "proby"} albo None (brak świeżego znacznika)."""
    m = wylogowanie.wczytaj(_kat(korzen, id_))
    if not m or not isinstance(m.get("ts"), (int, float)):
        return None
    if teraz_ts - m["ts"] > ZNACZNIK_WAZNY_H * 3600:
        return None
    od = najwczesniej(m["ts"])
    sp = stan_prob(_kat(korzen, id_))
    proby = int(sp.get("proby") or 0)
    r = {"id": id_, "marker": m, "od": od, "proby": proby, "gotowa": False, "powod": ""}
    odm = bramka(korzen, id_)
    if odm:
        r["powod"] = odm
    elif proby >= MAX_PROB:
        r["powod"] = f"{proby} nieudane próby relogu: eskalacja"
    elif teraz_ts < od:
        r["powod"] = f"relog nie wcześniej niż {datetime.fromtimestamp(od):%H:%M}"
    elif sp.get("ost_ts") and teraz_ts - sp["ost_ts"] < PONOW_MIN * 60:
        r["powod"] = f"ponowienie po {PONOW_MIN} min od nieudanej próby"
    else:
        r["gotowa"] = True
    return r


def kandydaci(korzen, teraz_ts, ids=None):
    """Postacie ze świeżym znacznikiem wylogowania, w kolejności wylogowania."""
    if ids is None:
        try:
            ids = sorted(d.name for d in (Path(korzen) / "instancje").iterdir() if d.is_dir() and not d.name.startswith("_"))
        except OSError:
            ids = []
    wynik = [r for r in (ocen(korzen, i, teraz_ts) for i in ids) if r]
    wynik.sort(key=lambda r: (r["marker"]["ts"], r["id"]))
    return wynik


def relog_jednej(korzen, r, W, log, spij=time.sleep):
    """Pełny relog jednej postaci. -> (wynik, tekst): True = bot wystartował, False = porażka (liczy się do MAX_PROB), None = pominięta
    (Karol gra / pauza), nie porażka."""
    id_, m = r["id"], r["marker"]
    nick = profil(korzen, id_).get("postac") or m.get("nick")
    if not nick:
        return False, "brak nicka postaci (profil.json, znacznik)"
    mapa, tryb = m.get("mapa"), m.get("tryb")
    if not mapa:
        return False, "znacznik bez mapy (brak [TRYB] w tryb.log bota)"

    def odmowa():
        return bramka(korzen, id_)

    o = odmowa()
    if o:
        return None, o
    log(f"{id_} ({nick}): zamykam klienta")
    ok, txt = W.zamknij(id_)
    if not ok:
        return False, "zamknięcie klienta: " + txt
    spij(8)
    log(f"{id_}: start klienta")
    ok, txt = W.start_klienta(id_)
    if not ok:
        return False, "start klienta: " + txt
    ok, ekran = W.czekaj_ekran(id_, RE_EKRAN_START, 240)
    if not ok:
        return False, f"klient nie wstał (ekran: {ekran})"
    log(f"{id_}: ekran {ekran}, loguję")
    o = odmowa()
    if o:
        return None, o
    ok, txt = W.zaloguj(id_)
    if not ok:
        return False, "zaloguj.sh: " + txt
    ok, ekran = W.czekaj_ekran(id_, r"^gra$", 60)
    if not ok:
        return False, f"po logowaniu ekran {ekran}"
    o = odmowa()          # uruchom.sh kasuje STOP_RECZNY: nigdy, gdy Karol przejął postać w trakcie relogu
    if o:
        return None, o
    log(f"{id_}: w grze, start bota na {mapa} / {tryb or '-'}")
    ok, txt = W.uruchom(id_, nick, mapa, tryb)
    if not ok:
        return False, "uruchom.sh: " + txt
    wynik, linia = W.pierwsze_zabicie(id_, ZABICIE_LIMIT_S)
    log(f"{id_}: {wynik}{(': ' + linia) if linia else ''}")
    if wynik == "problem":
        return False, "po starcie bota: " + linia
    return True, f"bot wystartował ({wynik})"


def kolejka(korzen, W, log, zegar=time.time, spij=time.sleep, los=random.uniform, ids=None):
    """Jedna kolejka relogów: pojedynczo, między postaciami losowa przerwa. -> lista (id, wynik, tekst)."""
    p = _wspolne(korzen) / SINGLETON
    p.parent.mkdir(parents=True, exist_ok=True)
    s = open(p, "a")
    try:
        fcntl.flock(s, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        s.close()
        log("inna kolejka relogów trwa: kończę")
        return []
    wyniki, zrobione = [], set()
    try:
        while True:
            gotowe = [r for r in kandydaci(korzen, zegar(), ids) if r["gotowa"] and r["id"] not in zrobione]
            if not gotowe:
                break
            if zrobione:
                przerwa = los(*PRZERWA_S)
                log(f"przerwa {przerwa:.0f} s przed następną postacią")
                spij(przerwa)
                gotowe = [r for r in kandydaci(korzen, zegar(), ids) if r["gotowa"] and r["id"] not in zrobione]
                if not gotowe:
                    break
            r = gotowe[0]
            zrobione.add(r["id"])
            z = _zamek_logowania(korzen, spij, zegar)
            if z is None:
                wyniki.append((r["id"], None, "inna akcja logowania trwa (blokada), wrócę w następnej kolejce"))
                log(f"{r['id']}: inna akcja logowania trwa, pomijam")
                continue
            try:
                try:
                    wynik, txt = relog_jednej(korzen, r, W, log, spij)
                except Exception as e:      # noqa: BLE001  jedna postać nie wywraca kolejki
                    wynik, txt = False, f"wyjątek: {e!r}"
            finally:
                z.close()
            kat = _kat(korzen, r["id"])
            if wynik is True:
                wylogowanie.usun(kat)
                (kat / STAN_NAZWA).unlink(missing_ok=True)
            elif wynik is False:
                sp = stan_prob(kat)
                zapisz_stan_prob(kat, {"proby": int(sp.get("proby") or 0) + 1, "ost_ts": round(zegar(), 1), "ost_blad": txt[:200]})
            log(f"{r['id']}: {'OK' if wynik else ('BLAD' if wynik is False else 'POMINIETA')}: {txt}")
            wyniki.append((r["id"], wynik, txt))
        log("KONIEC kolejki relogów")
    finally:
        s.close()
    return wyniki


def _zamek_logowania(korzen, spij, zegar):
    """Zamek wspólny z nadzor.py (jedna akcja logowania naraz); czeka do ZAMEK_CZEKAJ_S. Uchwyt do zamknięcia albo None."""
    p = _wspolne(korzen) / ZAMEK_LOGOWANIA
    f = open(p, "a")
    start = zegar()
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return f
        except OSError:
            if zegar() - start >= ZAMEK_CZEKAJ_S:
                f.close()
                return None
            spij(5)


class WykonawcaRelog:
    """Polecenia jak w ręcznym relogu 23.10. Każde (ok, tekst); nic nie rzuca."""

    def __init__(self, korzen, spij=time.sleep):
        self.korzen = Path(korzen)
        self.spij = spij

    def _env(self, id_, **dod):
        e = dict(os.environ)
        e["RETRONIC_ID"] = id_
        e["RETRONIC_RELOG"] = "1"          # zatrzymaj.sh: nie twórz STOP_RECZNY (to nie Karol)
        e.update(dod)
        return e

    def _run(self, argv, id_, limit, **env):
        try:
            r = subprocess.run([str(a) for a in argv], cwd=str(DIR), env=self._env(id_, **env), capture_output=True, text=True,
                               timeout=limit, stdin=subprocess.DEVNULL)
            return r.returncode, (r.stdout + r.stderr).strip()
        except subprocess.TimeoutExpired:
            return 124, f"przekroczony limit {limit} s"
        except OSError as e:
            return 127, str(e)

    def zamknij(self, id_):
        k, w = self._run([sys.executable, "-I", DIR / "sesja_gry.py", "zamknij"], id_, 120)
        return k == 0, f"kod {k}: {w[-150:]}"

    def start_klienta(self, id_):
        k, w = self._run([sys.executable, "-I", DIR / "sesja_gry.py", "start"], id_, 180)
        return k == 0, f"kod {k}: {w[-150:]}"

    def ekran(self, id_):
        k, w = self._run([sys.executable, "-I", DIR / "logowanie.py", "stan-ekranu"], id_, 20)
        return w.strip().splitlines()[-1] if k == 0 and w.strip() else "brak"

    def czekaj_ekran(self, id_, wzor, limit_s):
        t, e = 0, "brak"
        while True:
            e = self.ekran(id_)
            if re.search(wzor, e):
                return True, e
            if t >= limit_s:
                return False, e
            self.spij(5)
            t += 5

    def zaloguj(self, id_):
        k, w = self._run([DIR / "zaloguj.sh", "--limit", "120"], id_, 180)
        return k == 0, f"kod {k}: {w[-150:]}"

    def uruchom(self, id_, nick, mapa, tryb):
        k, w = self._run([DIR / "uruchom_instancje.sh", id_, mapa, tryb or ""], id_, 180, RETRONIC_POSTAC=nick)
        return k == 0, f"kod {k}: {w[-200:]}"

    def pierwsze_zabicie(self, id_, limit_s):
        """-> ("zabity" | "problem" | "czas", linia). Czyta najnowszy mozg-stdout instancji."""
        logi = _kat(self.korzen, id_) / "logi"
        t = 0
        self.spij(10)
        while True:
            try:
                pliki = sorted(logi.glob("mozg-stdout*"), key=lambda p: p.stat().st_mtime)
                tekst = pliki[-1].read_text(encoding="utf-8", errors="replace") if pliki else ""
            except OSError:
                tekst = ""
            for l in tekst.splitlines():
                if RE_ZABITY.search(l):
                    return "zabity", l[:120]
                if RE_PROBLEM.search(l):
                    return "problem", l[:120]
            if t >= limit_s:
                return "czas", ""
            self.spij(10)
            t += 10


def uruchom_kolejke_w_tle(korzen=None):
    """Dla nadzor.py: kolejka jako osobny proces (relog trwa kilkanaście minut, tick nadzoru nie może czekać). Nic poza tym."""
    korzen = Path(korzen or DIR)
    if kolejka_dziala(korzen):
        return False, "kolejka relogów już trwa"
    try:
        # 26.10: własna jednostka systemd (w_scope.sh), żeby kolejka nie umierała z cgroupem, z którego wystartowała
        subprocess.Popen(instancja.w_scope("kolejka", [sys.executable, "-I", str(DIR / "relog_wylogowanych.py"), "kolejka"]),
                         cwd=str(DIR), stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        return False, str(e)
    return True, "kolejka relogów uruchomiona w tle"


def _logger(korzen):
    d = _wspolne(korzen) / "logi"

    def log(tekst):
        linia = f"{time.strftime('%H:%M:%S')} {tekst}"
        print(linia, flush=True)
        try:
            d.mkdir(parents=True, exist_ok=True)
            with open(d / f"relog-wylog-{time.strftime('%Y%m%d')}.log", "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d')} {linia}\n")
        except OSError:
            pass
    return log


def main(argv):
    if len(argv) >= 2 and argv[1] == "kolejka":
        w = kolejka(DIR, WykonawcaRelog(DIR), _logger(DIR))
        return 0 if all(x[1] is not False for x in w) else 1
    if len(argv) >= 2 and argv[1] == "stan":
        print(json.dumps([{**r, "od": datetime.fromtimestamp(r["od"]).strftime("%H:%M:%S")} for r in kandydaci(DIR, time.time())],
                         ensure_ascii=False, indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
