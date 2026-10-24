#!/usr/bin/env python3
"""Przerwa postaci (24.10, Karol: „nadzorca ma sam robić przerwy postaci i ewentualnie zmieniać spot”). Spec: dane_tibia/SPEC_przerwa_postaci_1024.md.

Wspólna, lekka (tylko stdlib) ocena pola `przerwa` z wpisu postaci w instancje/_wspolne/plan_postaci.json. Używają jej plan_postaci.py (zapis, `pokaz`,
CLI), nadzor.py (wylogowanie, powrót, zmiana spotu) i refill_auto.py (refill bez kroku `wyjscie`), żeby wszyscy czytali tę samą regułę.

  "przerwa": {"min": 60, "rozrzut_min": 10, "kiedy": "po_refillu" | "teraz", "powod": "...", "zmien_spot": "nie" | "jesli_gracz", "gracz": "Nick",
              (pola stanu, pisze nadzorca:) "wylogowano_t": "RRRR-MM-DD GG:MM:SS", "do_t": "...", "gracz_wykryty": "Nick", "zrobione_t": "..."}

Przerwa jest JEDNORAZOWA (`zrobione_t` po powrocie). Wyłącznik globalny: env NADZOR_PRZERWY=0 albo `"przerwy": false` w nadzor_konfig.json — wstrzymuje
NOWE przerwy (refill idzie jak dotąd, nadzorca nikogo nie wylogowuje); przerwa już trwająca (`wylogowano_t`) kończy się powrotem."""
import json
import os
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

FMT = "%Y-%m-%d %H:%M:%S"
KIEDY = ("po_refillu", "teraz")
ZMIEN_SPOT = ("nie", "jesli_gracz")
MIN_MAX = 720                     # przerwa dłuższa niż 12 h to literówka (60 min = typowa)
ROZRZUT_DOMYSLNY = 10
GRACZ_PROG = 4                    # tyle wpisów „Gracz w pobliżu: <nick>” ...
GRACZ_OKNO_MIN = 60               # ... w tylu minutach przed wylogowaniem = gracz przeszkadza (bot loguje tego samego gracza najwyżej raz na 120 s)
MARKER_REFILL = "przerwa_refill.ok"   # instancje/<id>/: refill.sh (REFILL_STARTUJ=0) zapisuje epoch po udanym refillu bez wyjścia
MARKER_WAZNY_S = 3 * 3600
RE_NICK = re.compile(r"^[^\s,()]+(?: [^\s,()]+){0,3}$")
RE_GRACZ = re.compile(r"^(\d\d):(\d\d):(\d\d) Gracz w pobliżu: (.+?) \(\d+ pól\)")


class Przerwa:
    """Jeden wpis `przerwa`. `blad` niepuste = wpis niepoprawny (nie jest używany)."""

    def __init__(self):
        self.min = 0
        self.rozrzut_min = ROZRZUT_DOMYSLNY
        self.kiedy = "po_refillu"
        self.powod = ""
        self.zmien_spot = "nie"
        self.gracz = ""
        self.wylogowano_t = ""
        self.do_t = ""
        self.gracz_wykryty = ""
        self.zrobione_t = ""
        self.blad = None

    def do_ts(self):
        try:
            return datetime.strptime(self.do_t, FMT).timestamp()
        except (ValueError, TypeError):
            return None


def _ts(pole, nazwa):
    if pole in (None, ""):
        return ""
    try:
        datetime.strptime(str(pole), FMT)
    except ValueError:
        raise ValueError(f"{nazwa}={pole!r}: oczekiwano „RRRR-MM-DD GG:MM:SS”") from None
    return str(pole)


def parsuj(sur):
    """Surowy wpis `przerwa` -> Przerwa; ValueError z powodem przy błędzie. None (brak pola) obsługuje wołający."""
    if not isinstance(sur, dict):
        raise ValueError("„przerwa” nie jest obiektem")
    p = Przerwa()
    m = sur.get("min")
    if isinstance(m, bool) or not isinstance(m, int) or not 1 <= m <= MIN_MAX:
        raise ValueError(f"przerwa.min musi być liczbą całkowitą 1-{MIN_MAX}, jest {m!r}")
    p.min = m
    r = sur.get("rozrzut_min", ROZRZUT_DOMYSLNY)
    if isinstance(r, bool) or not isinstance(r, int) or not 0 <= r <= m:
        raise ValueError(f"przerwa.rozrzut_min musi być liczbą całkowitą 0-{m} (nie większą niż min), jest {r!r}")
    p.rozrzut_min = r
    p.kiedy = sur.get("kiedy", "po_refillu")
    if p.kiedy not in KIEDY:
        raise ValueError(f"przerwa.kiedy={p.kiedy!r}: dozwolone {' | '.join(KIEDY)}")
    p.zmien_spot = sur.get("zmien_spot", "nie")
    if p.zmien_spot not in ZMIEN_SPOT:
        raise ValueError(f"przerwa.zmien_spot={p.zmien_spot!r}: dozwolone {' | '.join(ZMIEN_SPOT)}")
    p.powod = str(sur.get("powod") or "")[:300]
    g = sur.get("gracz") or ""
    if g and (not isinstance(g, str) or not RE_NICK.match(g.strip())):
        raise ValueError(f"przerwa.gracz={g!r}: oczekiwano nicku gracza (do 4 słów)")
    p.gracz = str(g).strip()
    p.wylogowano_t = _ts(sur.get("wylogowano_t"), "wylogowano_t")
    p.do_t = _ts(sur.get("do_t"), "do_t")
    p.gracz_wykryty = str(sur.get("gracz_wykryty") or "")[:60]
    p.zrobione_t = _ts(sur.get("zrobione_t"), "zrobione_t")
    if p.wylogowano_t and not p.do_t:
        raise ValueError("przerwa ma wylogowano_t bez do_t (powrót nieustalony)")
    return p


def wlaczone(konf=None, korzen=None):
    """Wyłącznik globalny: env NADZOR_PRZERWY=0 albo `"przerwy": false` w nadzor_konfig.json (konf = już wczytana konfiguracja, inaczej czytamy plik)."""
    if os.environ.get("NADZOR_PRZERWY", "").strip() == "0":
        return False
    if konf is None and korzen is not None:
        try:
            konf = json.loads((Path(korzen) / "instancje" / "_wspolne" / "nadzor_konfig.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            konf = {}
    return (konf or {}).get("przerwy", True) is not False


def odczyt(stan_dir, korzen=None):
    """Przerwa „do zrobienia” instancji (stan_dir = instancje/<id>) z planu postaci albo None: brak wpisu, wpis błędny, wyłącznik, już zrobiona,
    plik nieczytelny. Lekki odczyt dla refill_auto (bez importu plan_postaci)."""
    stan_dir = Path(stan_dir)
    if not wlaczone(korzen=korzen or stan_dir.parent.parent):
        return None
    try:
        d = json.loads((stan_dir.parent / "_wspolne" / "plan_postaci.json").read_text(encoding="utf-8"))
        sur = ((d.get("postacie") or {}).get(stan_dir.name) or {}).get("przerwa")
    except (OSError, ValueError, AttributeError):
        return None
    if sur is None:
        return None
    try:
        p = parsuj(sur)
    except ValueError:
        return None
    return None if p.zrobione_t else p


def marker_refill(stan_dir, teraz_ts):
    """Epoch udanego refillu bez wyjścia (przerwa_refill.ok) albo None (brak / nieczytelny / starszy niż MARKER_WAZNY_S)."""
    try:
        t = float((Path(stan_dir) / MARKER_REFILL).read_text().strip().split()[0])
    except (OSError, ValueError, IndexError):
        return None
    return t if 0 <= teraz_ts - t <= MARKER_WAZNY_S else None


def losuj_do(p, teraz, rng=random):
    """Chwila powrotu: teraz + min ± rozrzut_min (równomiernie, całe minuty); co najmniej minuta."""
    delta = p.min + (rng.randint(-p.rozrzut_min, p.rozrzut_min) if p.rozrzut_min else 0)
    return teraz + timedelta(minutes=max(1, delta))


def _linie_gracza(plik, ref):
    """[(epoch, nick)] z logu bota (linie „GG:MM:SS Gracz w pobliżu: Nick (N pól)…”); data z `ref` (linia z przyszłości względem ref = poprzedni dzień)."""
    wynik = []
    try:
        with open(plik, encoding="utf-8", errors="replace") as f:
            linie = f.readlines()[-20000:]
    except OSError:
        return wynik
    for l in linie:
        m = RE_GRACZ.match(l)
        if not m:
            continue
        t = ref.replace(hour=int(m[1]), minute=int(m[2]), second=int(m[3]), microsecond=0)
        if t > ref + timedelta(seconds=90):
            t -= timedelta(days=1)
        wynik.append((t.timestamp(), m[4].strip()))
    return wynik


def gracze_w_logu(stan_dir, ref, wlasne=(), prog=GRACZ_PROG, okno_min=GRACZ_OKNO_MIN):
    """Nick gracza widzianego >= `prog` razy w ostatnich `okno_min` min przed `ref` w najnowszym logu bota instancji, albo "". `wlasne` = nicki
    naszych postaci (pomijane: nasze boty nie przeszkadzają). Najczęstszy nick wygrywa."""
    logi = Path(stan_dir) / "logi"
    try:
        pliki = sorted(logi.glob("mozg-stdout-*.log"), key=lambda p: p.stat().st_mtime)
    except OSError:
        return ""
    if not pliki:
        return ""
    od = ref.timestamp() - okno_min * 60
    wlasne = {str(n).strip().lower() for n in wlasne if n}
    licz = {}
    for t, nick in _linie_gracza(pliki[-1], ref):
        if od <= t <= ref.timestamp() + 90 and nick.lower() not in wlasne:
            licz[nick] = licz.get(nick, 0) + 1
    if not licz:
        return ""
    nick, ile = max(licz.items(), key=lambda kv: kv[1])
    return nick if ile >= prog else ""


def nicki_wlasne(korzen):
    """Nicki naszych postaci (profil.json `postac` każdej instancji)."""
    wynik = set()
    try:
        for p in (Path(korzen) / "instancje").iterdir():
            try:
                n = json.loads((p / "profil.json").read_text(encoding="utf-8")).get("postac")
            except (OSError, ValueError, AttributeError):
                continue
            if isinstance(n, str) and n.strip():
                wynik.add(n.strip())
    except OSError:
        pass
    return wynik


def opis(p):
    """Jedna linia do `pokaz` / dziennika."""
    s = f"przerwa {p.min}±{p.rozrzut_min} min, {'po refillu' if p.kiedy == 'po_refillu' else 'od razu (wróć do miasta)'}"
    if p.zmien_spot == "jesli_gracz":
        s += ", zmiana spotu jeśli gracz"
    if p.zrobione_t:
        return s + f" [zrobiona {p.zrobione_t[5:16]}]"
    if p.wylogowano_t:
        return s + f" [wylogowana {p.wylogowano_t[11:16]}, powrót {p.do_t[11:16]}]"
    return s + (" [czeka na refill]" if p.kiedy == "po_refillu" else " [czeka na powrót do miasta]")
