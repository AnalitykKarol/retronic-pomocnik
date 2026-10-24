#!/usr/bin/env python3
"""Ostatnio znane dane postaci: `instancje/<id>/ostatnie.json` (spec wtyczka-paska/specs/2026-10-22-retronic-przeglad.md, F1).

Jeden obiekt `v:1`, nadpisywany w całości (nie dziennik). Pisarze: bot (telemetria.py, co 60 s i przy zdarzeniach), logowanie
(logowanie.py: wejście do gry, wylogowanie), `ml-ustaw` (okno_api.py) i backfill (ten plik, `--uzupelnij`). Czytelnik: `okno_api.py stan`.
Tylko stdlib; moduł nie importuje bota ani rdzenia. Nic stąd nie rzuca wyjątku do wołającego (zapis `zapisz` zwraca None i
pisze jedną linię diagnostyczną na stdout, najwyżej raz na 5 min na rodzaj błędu).

  python3 -I ostatnie.py --uzupelnij --sucho [--instancja ID ...]    wydruk tego, co backfill by zapisał (zero zapisów)
  python3 -I ostatnie.py --uzupelnij [--instancja ID ...]            zapis TYLKO dla instancji bez działającej gry (sprawdzane tuż przed zapisem)

Pola (wszystkie poza `v`, `zapisano`, `zrodlo` mogą być null = „nie wiem”, nigdy 0 w zastępstwie):
  v, zapisano (epoch), zrodlo (bot|logowanie|stop|backfill|reczny), dane_t (epoch próbki, z której pochodzą poz/exp/hp; zdarzenia go
  nie ruszają), postac, exp, level, level_proc, hp, max_hp, mana, max_mana, ml, ml_proc, ml_t, ml_zrodlo, poz [x,y,z], pietro,
  miasto, w_depo, mapa, tryb [..], stan_bota, sesja {start, koniec, zab, exp_start, gold, uh}, na_spocie_od, w_grze_t,
  alarm {t, tekst, kod}, stop {t, powod, reczny}, koniec_sesji (alarm_stop|wylogowanie|znikniecie), przyblizone [nazwy pól].
"""
import argparse
import contextlib
import fcntl
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
KORZEN = Path(__file__).resolve().parent

WERSJA = 1
NAZWA = "ostatnie.json"
NAZWA_BLOKADY = "ostatnie.lock"
CO_S = 60.0                  # bot: odstęp zapisów okresowych (jak ekonomia.TIK_S)
MIN_ZDARZENIE_S = 5.0        # bot: zapisy ze zdarzeń (poziom, alarm) nie częściej niż co tyle
ML_CO_S = 15.0               # bot: odstęp odczytów magic levelu z pamięci klienta (ml_zywo.py); zmiana ML/procentu zapisuje od razu
BLOKADA_BOT_S = 0.05         # bot: ile najwyżej czekamy na blokadę (pętla bota nie czeka dłużej); inni pisarze czekają dłużej
BLOKADA_INNI_S = 2.0
TEKST_ALARMU_MAX = 200
ZRODLA = ("bot", "logowanie", "stop", "backfill", "reczny")
KONCE_SESJI = ("alarm_stop", "wylogowanie", "znikniecie")
KLUCZE = ("v", "zapisano", "zrodlo", "dane_t", "postac", "exp", "level", "level_proc", "hp", "max_hp", "mana", "max_mana",
          "ml", "ml_proc", "ml_t", "ml_zrodlo", "poz", "pietro", "miasto", "w_depo", "mapa", "tryb", "stan_bota", "sesja",
          "na_spocie_od", "w_grze_t", "alarm", "stop", "koniec_sesji", "przyblizone")

_DIAG_OST = {}


def _diag(rodzaj, tekst):
    """Jedna linia diagnostyczna na stdout (mozg-stdout), najwyżej raz na 5 min na rodzaj."""
    teraz = time.monotonic()
    if teraz - _DIAG_OST.get(rodzaj, float("-inf")) < 300:
        return
    _DIAG_OST[rodzaj] = teraz
    with contextlib.suppress(Exception):
        print(f"ostatnie: {tekst}", flush=True)


# ---------- odczyt ----------
def plik(katalog):
    return Path(katalog) / NAZWA


def czytaj(katalog):
    """-> (dict|None, blad|None). Brak pliku = (None, None). Uszkodzony / nie-obiekt / inna wersja = (None, komunikat)."""
    try:
        surowe = plik(katalog).read_bytes()
    except FileNotFoundError:
        return None, None
    except OSError as e:
        return None, f"{NAZWA}: {e}"
    try:
        d = json.loads(surowe)
    except ValueError as e:
        return None, f"{NAZWA}: nieprawidłowy JSON ({e})"
    if not isinstance(d, dict):
        return None, f"{NAZWA}: oczekiwano obiektu JSON"
    if d.get("v") != WERSJA:
        return None, f"{NAZWA}: nieobsługiwana wersja v={d.get('v')!r}"
    return d, None


def pusty():
    return {k: None for k in KLUCZE}


def dla_api(katalog, teraz=None):
    """Treść pliku dla `okno_api.py stan` (pole `ostatnie`): wszystkie klucze kontraktu + `wiek_s` + `blad`.
    Brak pliku = None. Nieczytelny / stary format = wszystkie pola null i `blad`."""
    teraz = time.time() if teraz is None else teraz
    d, blad = czytaj(katalog)
    if d is None and blad is None:
        return None
    if d is None:
        return {**pusty(), "blad": blad, "wiek_s": None}
    w = {k: d.get(k) for k in KLUCZE}
    z = d.get("zapisano")
    w["wiek_s"] = round(max(0.0, teraz - z), 1) if isinstance(z, (int, float)) and not isinstance(z, bool) else None
    w["blad"] = None
    return w


# ---------- zapis ----------
@contextlib.contextmanager
def _blokada(katalog, czekaj_s):
    """flock na katalog/ostatnie.lock; bierze `True`, gdy zajęta w czasie `czekaj_s` (wtedy zapisu nie robimy), `False` inaczej."""
    fd = None
    try:
        fd = os.open(Path(katalog) / NAZWA_BLOKADY, os.O_RDWR | os.O_CREAT, 0o644)
        koniec = time.monotonic() + czekaj_s
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= koniec:
                    yield False
                    return
                time.sleep(0.005)
        try:
            yield True
        finally:
            with contextlib.suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)


def _zapisz_plik_atomowo(cel, tekst, fsync):
    tmp = cel.with_name(f"{cel.name}.tmp-{os.getpid()}")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(tekst)
            f.flush()
            if fsync:
                os.fsync(f.fileno())
        os.replace(tmp, cel)
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink()


def scal(stary, pola, scalaj=()):
    """Nowy obiekt = stary + pola. Pola z `scalaj` (słowniki, np. "sesja") scala płytko; reszta jest podmieniana."""
    nowy = dict(stary or {})
    for k, v in (pola or {}).items():
        if k in scalaj and isinstance(v, dict) and isinstance(nowy.get(k), dict):
            nowy[k] = {**nowy[k], **v}
        else:
            nowy[k] = v
    return nowy


def zapisz(katalog, zrodlo, pola=None, *, t=None, czekaj_s=BLOKADA_INNI_S, fsync=False, scalaj=(), znacznik=True):
    """Wczytaj stary plik, scal `pola`, zapisz atomowo (plik tymczasowy w tym samym katalogu + os.replace) pod blokadą.
    `znacznik=False`: istniejące `zapisano` i `zrodlo` zostają (zapis pomocniczy, np. ml_zywo.py, nie udaje świeżych danych bota).
    -> zapisany obiekt albo None (blokada zajęta / błąd). Nigdy nie rzuca. Uszkodzony stary plik jest zastępowany."""
    try:
        katalog = Path(katalog)
        t = time.time() if t is None else t
        katalog.mkdir(parents=True, exist_ok=True)
        with _blokada(katalog, czekaj_s) as ok:
            if not ok:
                _diag("blokada", f"blokada {NAZWA_BLOKADY} zajęta ponad {czekaj_s:g} s, pomijam zapis ({zrodlo})")
                return None
            stary, _blad = czytaj(katalog)
            nowy = scal(stary, pola, scalaj)
            nowy.update(v=WERSJA)
            if znacznik or not (stary and _liczba(stary.get("zapisano")) and stary.get("zrodlo")):
                nowy.update(zapisano=round(t, 1), zrodlo=zrodlo)
            tekst = json.dumps(nowy, ensure_ascii=False, separators=(",", ":"))
            _zapisz_plik_atomowo(plik(katalog), tekst, fsync)
            return nowy
    except Exception as e:      # noqa: BLE001  zapis nigdy nie psuje wołającego (bota, logowania, okna)
        _diag("zapis", f"błąd zapisu {NAZWA} ({zrodlo}): {e!r}")
        return None


# ---------- obliczenia ----------
def exp_na_level(level):
    """Doświadczenie potrzebne do levelu (wzór Tibii; ten sam co rdzen.exp_na_level, kopia, bo rdzen ciągnie numpy)."""
    return 50 * (level ** 3 - 6 * level ** 2 + 17 * level - 12) / 3


def _liczba(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def level_z_exp(exp):
    """(level, procent do następnego, 1 miejsce) z doświadczenia albo (None, None)."""
    if not _liczba(exp) or exp < 0:
        return None, None
    lv = 1
    while lv < 2000 and exp_na_level(lv + 1) <= exp:
        lv += 1
    lo, hi = exp_na_level(lv), exp_na_level(lv + 1)
    return lv, round(100.0 * (exp - lo) / (hi - lo), 1)


def kod_alarmu(tekst):
    """Krótki kod z linii logu: „ALARM: wyprawa: utknięcie…” -> „wyprawa”, „ALARM_GM: …” -> „ALARM_GM”."""
    t = str(tekst).strip()
    if t.startswith("ALARM_GM"):
        return "ALARM_GM"
    m = re.match(r"ALARM:?\s*([^:]*)", t)
    kod = (m[1].strip() if m else "") or "ALARM"
    return kod[:40]


def korzen_i_id(katalog_stanu):
    """(korzen pomocnika, id) z katalogu stanu: korzen/instancje/<id> albo (korzen, "") dla głównej."""
    k = Path(katalog_stanu)
    if k.parent.name == "instancje":
        return k.parent.parent, k.name
    return k, ""


def ostatni_start(katalog_stanu):
    """{mapa, tryb[]} z ostatni_start.<id>.env (ten sam format co okno_api.ostatni_start; własna kopia, bo okno_api zmienia środowisko)."""
    korzen, id_ = korzen_i_id(katalog_stanu)
    wynik = {"mapa": None, "tryb": []}
    try:
        tekst = (korzen / (f"ostatni_start.{id_}.env" if id_ else "ostatni_start.env")).read_text(encoding="utf-8")
    except OSError:
        return wynik
    for linia in tekst.splitlines():
        try:
            czesci = shlex.split(linia)
        except ValueError:
            continue
        m = re.match(r"(MAPA|TRYB)=(.*)$", czesci[0]) if czesci else None
        if not m:
            continue
        if m[1] == "MAPA":
            wynik["mapa"] = m[2] or None
        else:
            wynik["tryb"] = [x for x in m[2].split(",") if x]
    return wynik


def miasto_pozycji(poz):
    """(miasto|None, w_depo) przez panel.miasto_pozycji; import leniwy, błąd = (None, None)."""
    try:
        import panel  # noqa: PLC0415
        m, depo = panel.miasto_pozycji(tuple(poz))
        return m, bool(depo)
    except Exception:       # noqa: BLE001
        return None, None


# ---------- pisarz bota ----------
class Pisarz:
    """Stan zapisów jednego procesu bota. `tik` jest wołane z telemetrii przy każdej próbce (co >= 1 s): zapis okresowy co `co_s`
    albo od razu przy zmianie levelu; `alarm` i `stop` zapisują natychmiast. Nic nie rzuca; blokada czeka najwyżej BLOKADA_BOT_S."""

    def __init__(self, katalog_stanu, zegar=time.time, co_s=CO_S, miasto=miasto_pozycji):
        self.katalog = Path(katalog_stanu)
        self.zegar = zegar
        self.co_s = co_s
        self._miasto = miasto
        self.ost_zapis = float("-inf")
        self.ost_zdarzenie = float("-inf")
        self.level = None
        self.exp_start = None
        self.mapa = None
        self.na_spocie_od = None
        self.ost_alarm = (None, float("-inf"))     # (tekst, kiedy)
        self.ost_poz = None
        self.ost_miasto = (None, None)
        self.ml_odczyt = None          # (wynik ml_zywo.odczytaj, czas odczytu): ostatni UDANY odczyt ML z pamięci klienta
        self.ml_ost_t = float("-inf")  # kiedy ostatnio pytaliśmy klienta o ML (udanie albo nie)
        self.ml_zapisany = None        # (ml, ml_proc) ostatnio zapisane przez ten proces

    def _poz_miasto(self, poz):
        if poz is None:
            return None, None
        if self.ost_poz is None or max(abs(a - b) for a, b in zip(poz, self.ost_poz)) > 2:
            self.ost_poz = list(poz)
            self.ost_miasto = self._miasto(poz)
        return self.ost_miasto

    def _ml_klucz(self):
        return None if self.ml_odczyt is None else (self.ml_odczyt[0]["ml"], self.ml_odczyt[0]["ml_proc"])

    def _ml_czytaj(self, t, g, zapytaj):
        """Odczyt ML z pamięci klienta (ml_zywo: jedno `hexdump` pod adresem bloku z `g`), najwyżej co ML_CO_S. Zły odczyt zostawia
        poprzedni udany (nic nie zeruje). -> True, gdy ML albo procent różni się od ostatnio zapisanych."""
        if callable(zapytaj) and isinstance(g, dict) and t - self.ml_ost_t >= ML_CO_S:
            self.ml_ost_t = t
            try:
                import ml_zywo  # noqa: PLC0415  (leniwie: `python3 -I ostatnie.py` nie ma katalogu skryptu na sys.path)
                w = ml_zywo.odczytaj(zapytaj, g)
            except Exception:       # noqa: BLE001
                w = None
            if w is not None:
                self.ml_odczyt = (w, t)
        return self.ml_odczyt is not None and self._ml_klucz() != self.ml_zapisany

    def tik(self, t, g, poz, stan_bota, postac, sesja, zapytaj=None):
        """g: odpowiedź `gracz` (hp, max_hp, mana, max_mana, exp, level, procent, adres); sesja: {start, zab, gold, uh}; zapytaj: gniazdo
        strażnika bota (odczyt ML, opcjonalny). -> True, gdy zapisano."""
        try:
            zmiana_ml = self._ml_czytaj(t, g, zapytaj)
            lv = g.get("level") if isinstance(g, dict) else None
            lv = int(lv) if _liczba(lv) and 1 <= lv <= 2000 else None
            zmiana_lv = self.level is not None and lv is not None and lv != self.level
            if not (t - self.ost_zapis >= self.co_s or ((zmiana_lv or zmiana_ml) and t - self.ost_zdarzenie >= MIN_ZDARZENIE_S)):
                if lv is not None:
                    self.level = lv if self.level is None else self.level
                return False
            exp = g.get("exp") if isinstance(g, dict) else None
            exp = int(exp) if _liczba(exp) else None
            proc = g.get("procent") if isinstance(g, dict) else None
            if lv is None:
                lv, proc = level_z_exp(exp)
            elif not _liczba(proc):
                proc = None
            else:
                proc = round(float(proc), 1)
            if self.exp_start is None and exp is not None:
                self.exp_start = exp
            st = ostatni_start(self.katalog)
            if st["mapa"] != self.mapa or self.na_spocie_od is None:
                self.mapa = st["mapa"]
                prev, _ = czytaj(self.katalog)
                # restart bota na tym samym spocie bez przerwy w grze nie zeruje „na spocie od”
                if prev and prev.get("mapa") == st["mapa"] and _liczba(prev.get("na_spocie_od")) \
                        and _liczba(prev.get("w_grze_t")) and t - prev["w_grze_t"] < 180 and not prev.get("koniec_sesji"):
                    self.na_spocie_od = prev["na_spocie_od"]
                else:
                    self.na_spocie_od = round(t, 1)
            miasto, w_depo = self._poz_miasto(poz)
            ints = {k: (int(g[k]) if _liczba(g.get(k)) else None) for k in ("hp", "max_hp", "mana", "max_mana")} \
                if isinstance(g, dict) else {}
            pola = {
                "dane_t": round(t, 1), "postac": postac if isinstance(postac, str) else None,
                "exp": exp, "level": lv, "level_proc": proc, **ints,
                "poz": list(poz) if poz is not None else None, "pietro": poz[2] if poz is not None else None,
                "miasto": miasto, "w_depo": w_depo, "mapa": st["mapa"], "tryb": st["tryb"], "stan_bota": stan_bota,
                "sesja": {"start": sesja.get("start"), "koniec": None, "zab": sesja.get("zab"), "exp_start": self.exp_start,
                          "gold": sesja.get("gold"), "uh": sesja.get("uh")},
                "na_spocie_od": self.na_spocie_od, "w_grze_t": round(t, 1), "koniec_sesji": None,
            }
            if self.ml_odczyt is not None:
                pola.update(ml=self.ml_odczyt[0]["ml"], ml_proc=self.ml_odczyt[0]["ml_proc"], ml_t=round(self.ml_odczyt[1], 1),
                            ml_zrodlo="pamiec")
            ok = zapisz(self.katalog, "bot", pola, t=t, czekaj_s=BLOKADA_BOT_S) is not None
            if ok:
                self.ml_zapisany = self._ml_klucz()
                self.ost_zapis = t
                self.ost_zdarzenie = t
                self.level = lv if lv is not None else self.level
            return ok
        except Exception as e:      # noqa: BLE001
            _diag("tik", f"tik: {e!r}")
            return False

    def alarm(self, tekst):
        """Linia logu „ALARM…”: trwały „ostatni alarm” (panel pokazuje alarm tylko 60 s). Ten sam tekst najwyżej raz na 30 s."""
        try:
            t = self.zegar()
            tekst = str(tekst).strip()[:TEKST_ALARMU_MAX]
            if tekst == self.ost_alarm[0] and t - self.ost_alarm[1] < 30:
                return False
            self.ost_alarm = (tekst, t)
            return zapisz(self.katalog, "bot", {"alarm": {"t": round(t, 1), "tekst": tekst, "kod": kod_alarmu(tekst)},
                                                "w_grze_t": round(t, 1)},
                          t=t, czekaj_s=BLOKADA_BOT_S) is not None
        except Exception as e:      # noqa: BLE001
            _diag("alarm", f"alarm: {e!r}")
            return False

    def stop(self, powod=None):
        """Bot kończy z powodu STOP / STOP_RECZNY / sygnału: treść pliku STOP (<= 200 znaków), flaga ręcznego, koniec sesji."""
        try:
            t = self.zegar()
            auto, reczny = self.katalog / "STOP", self.katalog / "STOP_RECZNY"
            tresc = None
            with contextlib.suppress(OSError):
                tresc = auto.read_text(encoding="utf-8", errors="replace").strip()[:TEKST_ALARMU_MAX] or None
            jest_reczny = reczny.exists()
            opis = tresc or powod or ("STOP_RECZNY" if jest_reczny else "STOP")
            pola = {"stop": {"t": round(t, 1), "powod": str(opis)[:TEKST_ALARMU_MAX], "reczny": jest_reczny},
                    "sesja": {"koniec": round(t, 1)}, "w_grze_t": round(t, 1)}
            if not jest_reczny:
                pola["koniec_sesji"] = "alarm_stop"
            return zapisz(self.katalog, "stop", pola, t=t, czekaj_s=BLOKADA_BOT_S, scalaj=("sesja",)) is not None
        except Exception as e:      # noqa: BLE001
            _diag("stop", f"stop: {e!r}")
            return False


# ---------- zdarzenia logowania ----------
def zdarzenie_logowania(katalog_logow, akcja, typ, kw=None, t=None):
    """Wołane z logowanie.Dziennik.zdarzenie. Pisze tylko pola logowania (bot może nie żyć): `w_grze_t`, `koniec_sesji`, `sesja`.
    Dotyczy: w_grze (wejście do gry: nowa sesja), zaloguj+koniec kod 0 (postać już była w grze), wylogowano. Nigdy nie rzuca."""
    try:
        kw = kw or {}
        katalog = Path(katalog_logow)
        if katalog.name != "logi":
            return None
        stan = katalog.parent
        t = time.time() if t is None else t
        if typ == "w_grze":
            zal, ocz = kw.get("zalogowany"), kw.get("oczekiwany")
            if zal and ocz and str(zal).lower() != str(ocz).lower():
                return None                      # w grze inna postać niż instancji: to nie jest jej sesja
            return zapisz(stan, "logowanie", {"w_grze_t": round(t, 1), "koniec_sesji": None,
                                              "sesja": {"start": round(t, 1), "koniec": None, "zab": None, "exp_start": None,
                                                        "gold": None, "uh": None}},
                          t=t)
        if typ == "koniec" and akcja == "zaloguj" and kw.get("kod") == 0:
            return zapisz(stan, "logowanie", {"w_grze_t": round(t, 1)}, t=t)
        if typ == "wylogowano":
            return zapisz(stan, "logowanie", {"w_grze_t": round(t, 1), "koniec_sesji": "wylogowanie",
                                              "sesja": {"koniec": round(t, 1)}}, t=t, scalaj=("sesja",))
    except Exception as e:      # noqa: BLE001
        _diag("logowanie", f"logowanie: {e!r}")
    return None


# ---------- ml-ustaw ----------
def ml_ustaw(katalog, ml, t=None):
    """Ręczne ustawienie magic levelu (czat podaje tylko zmiany). Zapisuje WYŁĄCZNIE ml, ml_proc, ml_t, ml_zrodlo w ostatnie.json."""
    if isinstance(ml, bool) or not isinstance(ml, int) or not 0 <= ml <= 999:
        raise ValueError(f"magic level musi być liczbą całkowitą 0-999, dostałem {ml!r}")
    t = time.time() if t is None else t
    wynik = zapisz(katalog, "reczny", {"ml": ml, "ml_proc": None, "ml_t": round(t, 1), "ml_zrodlo": "reczny"}, t=t, fsync=True)
    if wynik is None:
        raise OSError(f"nie zapisałem {NAZWA} w {katalog}")
    return wynik


# ---------- backfill ----------
TAIL_BAJTOW = 600_000


def _ogon_linii(sciezka, maks=TAIL_BAJTOW):
    try:
        with open(sciezka, "rb") as f:
            f.seek(0, 2)
            rozmiar = f.tell()
            f.seek(max(0, rozmiar - maks))
            dane = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []
    return dane[1:] if rozmiar > maks and dane else dane      # pierwsza linia z ogona bywa ucięta


def _rekordy(sciezka, maks=TAIL_BAJTOW):
    for linia in _ogon_linii(sciezka, maks):
        if not linia.startswith("{"):
            continue
        try:
            r = json.loads(linia)
        except ValueError:
            continue
        if isinstance(r, dict):
            yield r


def _ostatni(pliki, pasuje):
    """Ostatni rekord spełniający `pasuje` z najnowszych plików (od najnowszego)."""
    for p in reversed(pliki):
        znaleziony = None
        for r in _rekordy(p):
            if pasuje(r):
                znaleziony = r
        if znaleziony is not None:
            return znaleziony
    return None


def _ts(tekst):
    """„2026-10-22 18:20:03” -> epoch albo None."""
    try:
        return time.mktime(time.strptime(tekst[:19], "%Y-%m-%d %H:%M:%S"))
    except (ValueError, TypeError):
        return None


def _ostatni_alarm_z_logow(logi):
    """Ostatnia linia „HH:MM:SS ALARM…” z mozg-RRRRMMDD-GGMM.log (data z nazwy pliku, północ wykrywana spadkiem czasu)."""
    pliki = sorted(logi.glob("mozg-2*.log"))
    for p in reversed(pliki[-6:]):
        m = re.match(r"mozg-(\d{8})-(\d{4})\.log$", p.name)
        if not m:
            continue
        start = time.mktime(time.strptime(m[1] + m[2], "%Y%m%d%H%M"))
        wynik, prev_s, doba = None, None, 0
        for linia in _ogon_linii(p, 2_000_000):
            mm = re.match(r"(\d\d):(\d\d):(\d\d) (ALARM.*)$", linia)
            gg = re.match(r"(\d\d):(\d\d):(\d\d) ", linia)
            if not gg:
                continue
            s = int(gg[1]) * 3600 + int(gg[2]) * 60 + int(gg[3])
            if prev_s is not None and s < prev_s - 3600:
                doba += 86400
            prev_s = s
            if mm:
                t = time.mktime(time.strptime(m[1], "%Y%m%d")) + doba + s
                if t < start - 60:
                    t += 86400
                wynik = {"t": round(t, 1), "tekst": mm[4][:TEKST_ALARMU_MAX], "kod": kod_alarmu(mm[4])}
        if wynik:
            return wynik
    return None


def zbierz(korzen, id_, teraz=None, miasto=miasto_pozycji):
    """Odtwarza `ostatnie.json` instancji z telemetria-*.jsonl, ekonomia-*.jsonl, logowanie.jsonl, tryb.log, mozg-*.log, profil.json,
    ostatni_start.env i plików STOP. -> (pola, uwagi). Tylko odczyt. Brak próbki w telemetrii (4 dni) = pola gry null."""
    korzen = Path(korzen)
    stan = korzen / "instancje" / id_
    logi = stan / "logi"
    teraz = time.time() if teraz is None else teraz
    uwagi = []
    pola = {k: None for k in KLUCZE if k not in ("v", "zapisano", "zrodlo")}
    przybl = []
    tel = sorted(logi.glob("telemetria-*.jsonl"))
    eko = sorted(logi.glob("ekonomia-*.jsonl"))
    pr = _ostatni(tel, lambda r: r.get("typ") == "probka" and _liczba(r.get("exp")) and r.get("poz"))
    prof = {}
    with contextlib.suppress(OSError, ValueError):
        prof = json.loads((stan / "profil.json").read_text(encoding="utf-8"))
        if not isinstance(prof, dict):
            prof = {}
    sesja_ep = None
    tik = None
    start_eko = None
    if pr:
        sesja_ep = pr.get("sesja")
        tik = _ostatni(eko, lambda r: r.get("typ") == "tik" and r.get("sesja") == sesja_ep)
        start_eko = _ostatni(eko, lambda r: r.get("typ") == "start" and r.get("sesja") == sesja_ep)
        lv, proc = level_z_exp(pr["exp"])
        pozycja = [int(x) for x in pr["poz"]]
        m, depo = miasto(pozycja)
        pola.update(dane_t=pr["t"], exp=int(pr["exp"]), level=lv, level_proc=proc, mana=pr.get("mana"),
                    max_mana=pr.get("max_mana"), poz=pozycja, pietro=pozycja[2], miasto=m, w_depo=depo, stan_bota=pr.get("stan"))
    else:
        uwagi.append("brak próbki telemetrii (pliki starsze niż 4 dni albo bot nigdy nie pisał)")
    # nick: profil, potem rekord start ekonomii
    pola["postac"] = (prof.get("postac") or None) or ((start_eko or {}).get("postac") if start_eko else None) \
        or ((_ostatni(eko, lambda r: r.get("typ") == "start") or {}).get("postac"))
    # sesja
    if pr:
        exp_start = None
        if sesja_ep is not None:
            for r in _rekordy(eko[-1] if eko else logi / "brak"):
                if r.get("typ") == "tik" and r.get("sesja") == sesja_ep and _liczba(r.get("exp")):
                    exp_start = int(r["exp"])
                    break
        pola["sesja"] = {"start": sesja_ep, "koniec": pr["t"], "zab": (tik or {}).get("zab_razem"), "exp_start": exp_start,
                         "gold": (tik or {}).get("gold_razem"), "uh": (tik or {}).get("uh_razem")}
    # mapa, tryb, na_spocie_od
    st = ostatni_start(stan)
    pola["mapa"], pola["tryb"] = st["mapa"], st["tryb"] or None
    tryb_log = None
    for linia in _ogon_linii(logi / "tryb.log", 200_000):
        mm = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) \[TRYB\] mapa (\S+?):", linia)
        if mm:
            tryb_log = (mm[1], mm[2])
    if tryb_log:
        pola["mapa"] = tryb_log[1]
        pola["na_spocie_od"] = _ts(tryb_log[0])
    # logowanie: wejścia, wyloguj, HP przy logowaniu
    ev = [r for r in _rekordy(logi / "logowanie.jsonl", 400_000) if isinstance(r.get("t"), (int, float))]
    w_grze = [r for r in ev if r.get("zdarzenie") == "w_grze"]
    obecnosc = [r["t"] for r in ev if r.get("zdarzenie") in ("w_grze", "wylogowano")
                or (r.get("zdarzenie") == "koniec" and r.get("akcja") == "zaloguj" and r.get("kod") == 0)]
    if pr:
        obecnosc.append(pr["t"])
    pola["w_grze_t"] = round(max(obecnosc), 1) if obecnosc else None
    hp_login = next((r.get("hp") for r in reversed(w_grze) if _liczba(r.get("hp"))), None)
    if hp_login is not None:
        pola["max_hp"] = int(hp_login)
        przybl.append("max_hp")
        uwagi.append("max_hp = HP z ostatniego logowania (przybliżenie; telemetria zna tylko HP%)")
    # STOP
    stop_auto, stop_rec = stan / "STOP", stan / "STOP_RECZNY"
    stop = None
    for sciezka, reczny in ((stop_rec, True), (stop_auto, False)):
        try:
            mt = sciezka.stat().st_mtime
        except OSError:
            continue
        tresc = ""
        with contextlib.suppress(OSError):
            tresc = (stop_auto.read_text(encoding="utf-8", errors="replace") if stop_auto.exists() else "").strip()
        stop = {"t": round(mt, 1), "powod": (tresc or ("STOP_RECZNY" if reczny else "STOP"))[:TEKST_ALARMU_MAX], "reczny": reczny}
        break
    pola["stop"] = stop
    # alarm
    pola["alarm"] = _ostatni_alarm_z_logow(logi)
    # koniec sesji
    ost_wyl = max((r["t"] for r in ev if r.get("zdarzenie") == "wylogowano"), default=None)
    ost_wej = max((r["t"] for r in w_grze), default=None)
    if ost_wyl is not None and (ost_wej is None or ost_wyl > ost_wej) and (pr is None or ost_wyl >= pr["t"] - 5):
        pola["koniec_sesji"] = "wylogowanie"
    elif stop and not stop["reczny"] and (ost_wej is None or stop["t"] >= ost_wej):
        pola["koniec_sesji"] = "alarm_stop"      # STOP z poprzedniej sesji (starszy niż ostatnie wejście do gry) nie opisuje tej
    elif pola["w_grze_t"] is not None:
        pola["koniec_sesji"] = "znikniecie"
    pola["przyblizone"] = przybl or None
    return pola, uwagi


def offline_okno_api(korzen):
    """Funkcja `czy_offline(id) -> (bool, powód)` oparta na tym samym skanie procesów i gniazdach co `okno_api.py stan`.
    Import leniwy: okno_api zmienia środowisko (zdejmuje RETRONIC_ID), więc tylko w CLI."""
    os.environ.setdefault("RETRONIC_OKNO_KATALOG", str(korzen))
    import okno_api  # noqa: PLC0415

    def sprawdz(id_):
        procesy = okno_api.skan_procesow().get(id_, {"bot": [], "straznik": [], "sway": []})
        sc = okno_api.sciezki(id_)
        powody = []
        if Path(sc.gniazdo).exists():
            powody.append("gniazdo gry istnieje")
        if procesy["bot"]:
            powody.append("działa bot")
        if procesy["straznik"]:
            powody.append("działa klient gry")
        if procesy["sway"]:
            powody.append("działa sesja gry")
        return (not powody), ", ".join(powody)
    return sprawdz


def uzupelnij(korzen, ids=None, sucho=True, czy_offline=None, teraz=None, miasto=miasto_pozycji):
    """Backfill. -> lista {id, decyzja: zapis|sucho|pomijam, powod, pola, uwagi}. Zapis tylko gdy `czy_offline(id)` daje True
    (sprawdzane tuż przed zapisem tej instancji) i istniejący plik nie jest świeższy niż odtwarzane dane (nigdy nie cofa danych bota)."""
    korzen = Path(korzen)
    teraz = time.time() if teraz is None else teraz
    kat = korzen / "instancje"
    wszystkie = sorted(p.name for p in kat.iterdir() if p.is_dir() and not p.name.startswith("_")) if kat.is_dir() else []
    wynik = []
    for id_ in (ids or wszystkie):
        w = {"id": id_, "decyzja": None, "powod": None, "pola": None, "uwagi": []}
        wynik.append(w)
        if id_ not in wszystkie:
            w["decyzja"], w["powod"] = "pomijam", "brak katalogu instancji"
            continue
        pola, w["uwagi"] = zbierz(korzen, id_, teraz, miasto)
        w["pola"] = pola
        if pola.get("dane_t") is None and pola.get("w_grze_t") is None:
            w["decyzja"], w["powod"] = "pomijam", "brak jakichkolwiek danych do odtworzenia"
            continue
        ok, powod = (True, "") if czy_offline is None else czy_offline(id_)
        if not ok:
            w["decyzja"], w["powod"] = "pomijam", f"instancja online: {powod}"
            continue
        stary, _ = czytaj(kat / id_)
        if stary and stary.get("zrodlo") != "backfill" and isinstance(stary.get("dane_t"), (int, float)) \
                and stary["dane_t"] >= (pola.get("dane_t") or 0):
            w["decyzja"], w["powod"] = "pomijam", f"{NAZWA} jest świeższy (zrodlo {stary.get('zrodlo')})"
            continue
        if sucho:
            w["decyzja"], w["powod"] = "sucho", "tryb --sucho: nic nie zapisano"
            continue
        ok2, powod2 = (True, "") if czy_offline is None else czy_offline(id_)       # jeszcze raz tuż przed zapisem
        if not ok2:
            w["decyzja"], w["powod"] = "pomijam", f"instancja online tuż przed zapisem: {powod2}"
            continue
        z = zapisz(kat / id_, "backfill", {k: v for k, v in pola.items() if k != "ml" and not k.startswith("ml_")},
                   t=teraz, fsync=True)
        w["decyzja"], w["powod"] = ("zapis", "") if z else ("pomijam", "zapis nie powiódł się (blokada albo błąd)")
    return wynik


def _data(t):
    return time.strftime("%m-%d %H:%M", time.localtime(t)) if _liczba(t) else "-"


def opis_wiersza(w):
    p = w["pola"] or {}
    a = p.get("alarm") or {}
    return (f"{w['id']:<11} {w['decyzja']:<8} level {p.get('level')} ({p.get('level_proc')}%) · poz {p.get('poz')} "
            f"{('(' + p['miasto'] + (', depo' if p.get('w_depo') else '') + ')') if p.get('miasto') else ''}· ostatnio {_data(p.get('w_grze_t'))} "
            f"· dane {_data(p.get('dane_t'))} · alarm {_data(a.get('t'))} {a.get('kod') or ''} · koniec {p.get('koniec_sesji')}"
            + (f"\n{'':<20}-> {w['powod']}" if w["powod"] else ""))


def main(argv=None):
    p = argparse.ArgumentParser(prog="ostatnie.py", description=__doc__.split("\n")[0])
    p.add_argument("--uzupelnij", action="store_true", help="jednorazowy backfill z telemetrii, ekonomii i logowanie.jsonl")
    p.add_argument("--sucho", action="store_true", help="tylko wydruk, zero zapisów")
    p.add_argument("--instancja", action="append", default=None, help="tylko ta instancja (można powtarzać)")
    p.add_argument("--json", action="store_true", help="pełne pola w JSON zamiast jednego wiersza na instancję")
    a = p.parse_args(argv)
    if not a.uzupelnij:
        p.error("podaj --uzupelnij (jedyna operacja CLI)")
    if str(KORZEN) not in sys.path:     # `python3 -I` nie dodaje katalogu skryptu; panel i okno_api importujemy z pomocnika
        sys.path.insert(0, str(KORZEN))
    korzen = Path(os.environ.get("RETRONIC_OSTATNIE_KORZEN") or KORZEN)
    wyniki = uzupelnij(korzen, a.instancja, a.sucho, offline_okno_api(korzen))
    for w in wyniki:
        if a.json:
            print(json.dumps(w, ensure_ascii=False, default=str))
        else:
            print(opis_wiersza(w))
            for u in w["uwagi"]:
                print(f"{'':<20}uwaga: {u}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
