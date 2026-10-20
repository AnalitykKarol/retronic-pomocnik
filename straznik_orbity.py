"""Strażnik orbit (SPEC_orbity_straznik_1020, punkt B): bot nie może chodzić w kółko po kilku polach.

Przypadek K1 (Kutangen, 20.10 16:38-17:02): po upadku w dziurę w pościgu bot 24 min chodził stałym cyklem 6 pól na złym piętrze;
detektor ratunku (F1, cień) zgłosił to 41 razy i nic nie zrobił. Człowiek tak nie chodzi, a inni gracze zabijają nas wtedy, gdy
zorientują się, że to bot.

Dwie części:
  * `Detektor` — czyste liczenie jak `ratunek.Detektor` (ten sam zegar `teraz`, te same `STANY_WALKI`/`STANY_ZAMIERZONE`, ta sama
    luka MAX_PRZERWA_S). Okno przesuwne `STRAZNIK_ORBITA_S`: ORBITA = >= MIN_ZMIAN zmian pozycji, wszystkie pozycje na jednym
    piętrze i w <= `STRAZNIK_ORBITA_POL` różnych polach, bez długiego stania w środku; PIETRO = złe piętro >= `STRAZNIK_ORBITA_S`.
    Walka/loot nie zeruje okna (orbita z przerwami na szczura to nadal orbita), stany zamierzone (PRZERWA, PAUZA, ...) zerują.
  * `Reakcja` — maszyna stanów w cavebocie (tylko `STRAZNIK_ORBITY=2`): stop chodzenia (stan ORBITA, pauza 3-8 s) -> jedna
    próba wyjścia (wpadniecie.py: plan po mapie + pietra.py; na tym samym piętrze A* do najbliższego osiągalnego punktu trasy
    z polami orbity jako zakazanymi) w limicie `STRAZNIK_WYJSCIE_S` -> postęp (normalna praca) albo ALARM (powiadom critical
    „orbita” + plik STOP, jak wpadniecie.py), postać stoi.
Pokrętło `STRAZNIK_ORBITY`: 0 wyłączony (zero zmian w zachowaniu), 1 cień (log `[ORBITA] cień` + telemetria `straznik_orbita`),
2 działa. Progi: STRAZNIK_ORBITA_S, STRAZNIK_ORBITA_POL, STRAZNIK_WYJSCIE_S (stałe w cavebot.py, pokrętła w pokretla.py).
"""
import collections
import os
import random
from pathlib import Path

import ratunek
from ratunek import STANY_WALKI, STANY_ZAMIERZONE

DOMYSLNE = dict(STRAZNIK_ORBITY=0, STRAZNIK_ORBITA_S=60.0, STRAZNIK_ORBITA_POL=6, STRAZNIK_WYJSCIE_S=90.0)
MIN_ZMIAN = 8                        # tyle zmian pozycji w oknie = „zmienia pozycję” (spec)
MAX_STOJ_UL = 0.5                    # w oknie nie ma stania (poza walką) dłuższego niż tyle okna: to nie wahadło, tylko przystanek
PAUZA_S = (3.0, 8.0)                 # losowa pauza (stop chodzenia) przed próbą wyjścia
DEBOUNCE_S = 300.0                   # ten sam sygnał w tym samym miejscu najwcześniej po tylu s
POSTEP_POL = 3                       # postęp = >= tyle pól od najbliższego pola orbity (albo powrót na piętro trasy)
KAND_TRASY = 8                       # ile najbliższych punktów trasy/patrolu sprawdzamy A*
MAX_PRZERWA_S = ratunek.MAX_PRZERWA_S
_pasuje = ratunek._pasuje
_czeb = ratunek._czeb


def _nazwa_stanu(stan):
    return str(stan or "").split(" ")[0].split(":")[0]


class Detektor:
    """Czyste liczenie. `teraz` we wszystkich wywołaniach z jednego zegara (na żywo cb.zegar, offline czas telemetrii).
    `tick(teraz, poz, stan, zle_pietro, exp)` raz na obieg; zwraca listę zdarzeń (dict) po debounce; nic nie wykonuje.
    `konf` = obiekt ze stałymi STRAZNIK_* (moduł cavebot albo SimpleNamespace); bez niego domyślne."""

    def __init__(self, konf=None):
        self.konf = konf
        self.ost_t = None
        self.biegi = collections.deque()    # [t_start, poz, stan, exp, stoi_s]: kolejne różne pozycje poza walką/stanami zamierzonymi
        self.pietro_t = 0.0                 # s poza walką na złym piętrze
        self.ost = {}                       # rodzaj -> (t, poz): debounce

    def k(self, nazwa):
        return getattr(self.konf, nazwa, DOMYSLNE[nazwa]) if self.konf is not None else DOMYSLNE[nazwa]

    def reset(self):
        """Okno od nowa (luka w obserwacji, stan zamierzony, koniec reakcji)."""
        self.biegi.clear()
        self.pietro_t = 0.0

    def po_reakcji(self):
        self.reset()
        self.ost.clear()

    def tick(self, teraz, poz, stan, zle_pietro=False, exp=None):
        poz = tuple(poz[:3])
        dt = 0.0 if self.ost_t is None else teraz - self.ost_t
        if dt < 0 or dt > MAX_PRZERWA_S:
            self.reset()
            dt = 0.0
        self.ost_t = teraz
        if _pasuje(stan, STANY_ZAMIERZONE):
            self.reset()                    # postój z własnej woli: okno od nowa
            return []
        if _pasuje(stan, STANY_WALKI):
            return []                       # walka/loot nie zeruje okna i nie przyrasta (po niej liczymy dalej)
        if zle_pietro:
            self.pietro_t += dt
        else:
            self.pietro_t = 0.0
        b = self.biegi
        if b and b[-1][1] == poz:
            b[-1][4] += dt
        else:
            b.append([teraz, poz, _nazwa_stanu(stan), exp, 0.0])
        okno = float(self.k("STRAZNIK_ORBITA_S"))
        while len(b) >= 2 and b[1][0] <= teraz - okno:
            b.popleft()
        nowe = []
        if zle_pietro and self.pietro_t >= okno:
            nowe += self._zdarzenie("pietro", teraz, poz, trwa_s=round(self.pietro_t, 1))
        if teraz - b[0][0] >= okno:
            nowe += self._orbita(teraz, poz)
        return nowe

    def _orbita(self, teraz, poz):
        b = self.biegi
        zmian = len(b) - 1
        if zmian < MIN_ZMIAN:
            return []
        pola = {p for _, p, _, _, _ in b}
        if len({p[2] for p in pola}) != 1 or len(pola) > int(self.k("STRAZNIK_ORBITA_POL")):
            return []
        okno = float(self.k("STRAZNIK_ORBITA_S"))
        stoj = [r[4] for r in list(b)[1:]] + [max(0.0, b[1][0] - (teraz - okno))]   # + stanie na pierwszym polu w oknie
        if max(stoj) > MAX_STOJ_UL * okno:
            return []
        stany = collections.Counter(r[2] for r in b)
        exp0 = next((r[3] for r in b if r[3] is not None), None)
        exp1 = next((r[3] for r in reversed(b) if r[3] is not None), None)
        return self._zdarzenie("orbita", teraz, poz, pola=sorted(list(p) for p in pola), zmian=zmian,
                               czas_s=round(teraz - b[0][0], 1), stany=dict(stany),
                               exp_przyrost=(exp1 - exp0) if exp0 is not None and exp1 is not None else None)

    def _zdarzenie(self, rodzaj, teraz, poz, /, **d):
        ost = self.ost.get(rodzaj)
        if ost is not None and teraz - ost[0] < DEBOUNCE_S and ost[1][2] == poz[2] and _czeb(ost[1], poz) <= 5:
            return []
        self.ost[rodzaj] = (teraz, poz)
        return [dict(d, rodzaj=rodzaj, t=teraz, poz=list(poz))]


class Reakcja:
    """Maszyna stanów reakcji (STRAZNIK_ORBITY=2). `cb` = Cavebot (zegar, postac, punkty, droga/podejdz, _wp(), tele, alarm),
    `konf` = moduł cavebot (stałe), `plik_stop` = None -> bot.STOP (w testach RETRONIC_TESTY bez pliku)."""

    def __init__(self, cb, konf=None, log=print, plik_stop=None):
        self.cb = cb
        self.konf = konf
        self.log = log
        self.plik_stop = plik_stop
        self.faza = None                    # None | start | pauza | wp | droga | alarm
        self.ep = None
        self.stop_zapisany = False
        self.epizody = 0

    def k(self, nazwa):
        return getattr(self.konf, nazwa, DOMYSLNE[nazwa]) if self.konf is not None else DOMYSLNE[nazwa]

    def aktywna(self):
        return self.faza is not None

    def _tele(self, etap, **d):
        t = getattr(self.cb, "tele", None)
        if t is not None:
            try:
                t.zdarzenie("straznik_orbita", etap=etap, **d)
            except Exception:
                pass

    # --- wejście: zdarzenie z detektora ---
    def start(self, zd, teraz):
        self.epizody += 1
        self.faza = "start"
        self.ep = {"zd": zd, "t0": teraz, "z": zd["poz"][2], "pola": [tuple(p) for p in zd.get("pola") or [tuple(zd["poz"])]],
                   "nr": self.epizody}
        self.log(f"[ORBITA] wykryto {zd['rodzaj']} w {tuple(zd['poz'])}: {self._opis(zd)}; zatrzymuję chodzenie.")
        self._tele("start", **self._tele_zd(zd))

    @staticmethod
    def _opis(zd):
        if zd["rodzaj"] == "pietro":
            return f"złe piętro z{zd['poz'][2]} od {zd.get('trwa_s')} s"
        return f"{zd.get('zmian')} zmian w {len(zd.get('pola') or [])} polach przez {zd.get('czas_s')} s, stany {zd.get('stany')}"

    @staticmethod
    def _tele_zd(zd):
        return {k: v for k, v in zd.items() if k != "t"}

    # --- obieg ---
    def tick(self, poz, teraz):
        """True = obieg zużyty. None = nic do roboty (brak epizodu)."""
        if self.faza is None:
            return None
        cb = self.cb
        p = (int(poz[0]), int(poz[1]), int(poz[2]))
        f = self.faza
        if f == "start":
            self._stop_chodzenia(p)
            self.ep["pauza_do"] = teraz + random.uniform(*PAUZA_S)
            self.faza = "pauza"
            self.log(f"[ORBITA] stoję {self.ep['pauza_do'] - teraz:.1f} s, potem jedna próba wyjścia (limit {self.k('STRAZNIK_WYJSCIE_S'):.0f} s).")
            self._tele("pauza", poz=list(p), pauza_s=round(self.ep["pauza_do"] - teraz, 1))
            f = "pauza"
        if f == "pauza":
            cb.ustaw_stan("ORBITA", f"pauza przed wyjściem z {tuple(p)}")
            if teraz < self.ep["pauza_do"]:
                cb.pauza(0.3, 0.8)
                return True
            return self._wyjscie(p, teraz)
        if f == "alarm":
            cb.ustaw_stan("ORBITA", "alarm: czekam na STOP")
            cb.pauza(1.0, 2.0)
            return True
        if teraz - self.ep["t_wyj"] > float(self.k("STRAZNIK_WYJSCIE_S")):
            return self._alarm(f"brak postępu w {self.k('STRAZNIK_WYJSCIE_S'):.0f} s", p, teraz)
        if f == "wp":
            return self._tick_wp(p, teraz)
        if f == "droga":
            return self._tick_droga(p, teraz)
        self.faza = None
        return None

    def _stop_chodzenia(self, p):
        cb = self.cb
        try:
            cb.zatrzymaj_klik(p)                 # Escape, jeśli klient jeszcze idzie po starym kliku/marszu
        except Exception as e:
            if type(e).__name__ == "Zatrzymano":
                raise
        cb.cel = None
        try:
            cb._wypad_reset_klik()
        except Exception:
            pass
        cb.ustaw_stan("ORBITA", f"stop chodzenia w {tuple(p)}")

    # --- wyjście ---
    def _wyjscie(self, p, teraz):
        cb = self.cb
        ep = self.ep
        ep["t_wyj"] = teraz
        wp = cb._wp()
        if wp is not None:
            try:
                if wp.st is not None or wp.z_kieszeni(p, teraz):
                    self.faza = "wp"
                    ep["wp_z0"] = wp.st["z0"] if wp.st else None
                    self.log(f"[ORBITA] wyjście: plan po mapie (wpadniecie.py, wyjście na z{ep['wp_z0']}).")
                    self._tele("wyjscie", sposob="plan_pietra", poz=list(p), z0=ep["wp_z0"])
                    return True
            except Exception as e:
                if type(e).__name__ == "Zatrzymano":
                    raise
                self.log(f"[ORBITA] plan pięter nie wyszedł ({e!r}), próbuję A* po piętrze.")
        cel = self._cel_na_pietrze(p)
        if cel is None:
            return self._alarm("brak osiągalnego punktu trasy poza polami orbity", p, teraz)
        ep.update(cel=cel, fails=0)
        self.faza = "droga"
        self.log(f"[ORBITA] wyjście: A* do punktu trasy {cel[:2]} z pominięciem {len(ep['pola'])} pól orbity.")
        self._tele("wyjscie", sposob="astar", poz=list(p), cel=list(cel))
        return True

    def _zakazane(self, ep, p):
        return [(q[0], q[1]) for q in ep["pola"] if tuple(q[:2]) != tuple(p[:2])]

    def _kandydaci(self, z):
        cb = self.cb
        wyn = [(q[0], q[1]) for q in (cb.punkty or []) if q[2] == z]
        try:
            if cb._patrol_pietra_ok():
                wyn += [(m["x"], m["y"]) for m in (cb.miejsca or []) if m.get("z") == z]
        except Exception:
            pass
        return wyn

    def _daleko(self, q, pola):
        return all(q[2] != f[2] or _czeb(q, f) >= POSTEP_POL for f in pola)

    def _cel_na_pietrze(self, p):
        """Najbliższy osiągalny punkt trasy/patrolu poza obszarem orbity (A* z polami orbity jako zakazanymi) albo None."""
        cb = self.cb
        pola = self.ep["pola"]
        zak = self._zakazane(self.ep, p)
        kand = [q for q in dict.fromkeys(self._kandydaci(p[2])) if self._daleko((q[0], q[1], p[2]), pola)]
        kand.sort(key=lambda q: _czeb(q, p))
        for q in kand[:KAND_TRASY]:
            try:
                d = cb.droga((p[0], p[1], p[2]), q, zak, 0)
            except Exception as e:
                if type(e).__name__ == "Zatrzymano":
                    raise
                continue
            if d is not None:
                return (q[0], q[1], p[2])
        return None

    def _tick_wp(self, p, teraz):
        cb = self.cb
        wp = cb._wp()
        if wp is None or wp.st is None:
            return self._postep(p, teraz, "plan pięter zakończony", sync=False)
        if wp.st.get("alarm"):
            self.faza = "alarm"                  # wpadniecie.py samo już zaalarmowało (powiadomienie + STOP)
            self.log("[ORBITA] wpadniecie.py zaalarmowało: stoję.")
            self._tele("alarm", powod="alarm wpadniecie.py", poz=list(p))
            return True
        try:
            wp.tick(p, teraz)
        except Exception as e:
            if type(e).__name__ == "Zatrzymano":
                raise
            self.log(f"[ORBITA] plan pięter: błąd {e!r}")
            return self._alarm(f"błąd planu pięter {e!r}", p, teraz)
        if wp.st is None:
            return self._postep(tuple(cb.postac.pozycja()), teraz, "plan pięter zakończony", sync=False)
        return True

    def _tick_droga(self, p, teraz):
        cb = self.cb
        ep = self.ep
        if self._wyszedl(p):
            return self._postep(p, teraz, "wyszedłem poza obszar orbity")
        cel = ep["cel"]
        zajete = self._zakazane(ep, p) + [(s["x"], s["y"]) for s in (cb.ostatnie_stwory or [])
                                           if s.get("z") == p[2] and s.get("hp", 100) > 0 and (s["x"], s["y"]) != tuple(p[:2])
                                           and not (s.get("gracz") and s.get("nazwa") == getattr(cb.postac, "nazwa", None))]
        cb.ustaw_stan("ORBITA", f"wychodzę do {cel[:2]}")
        try:
            r = cb.podejdz(cel[:2], p, zajete=zajete, objazd=False, dlugosc=0)
        except Exception as e:
            if type(e).__name__ == "Zatrzymano":
                raise
            self.log(f"[ORBITA] krok wyjścia: błąd {e!r}")
            r = None
        q = tuple(cb.postac.pozycja())
        if q[2] != p[2] or self._wyszedl(q):
            return self._postep(q, teraz, "wyszedłem poza obszar orbity" if q[2] == p[2] else "zmiana piętra")
        ep["fails"] = 0 if (r and q != tuple(p)) else ep.get("fails", 0) + 1
        if ep["fails"] >= 12:
            return self._alarm("kroki wyjścia nie ruszają postaci", q, teraz)
        return True

    def _wyszedl(self, p):
        pola = self.ep["pola"]
        return self._daleko(p, pola)

    # --- koniec epizodu ---
    def _postep(self, p, teraz, powod, sync=True):
        cb = self.cb
        ep = self.ep
        self.faza = None
        czas = teraz - ep["t0"]
        self.log(f"[ORBITA] postęp: {powod}, jestem w {tuple(p)} po {czas:.0f} s od wykrycia; wracam do pracy.")
        self._tele("postep", wynik="ok", poz=list(p), czas_s=round(czas, 1), powod=powod, pola=[list(q) for q in ep["pola"]])
        wp = cb._wp()
        if wp is not None and wp.st is not None:
            wp.st = None
        try:
            if sync and not cb._wypad_wroc_na_trase(p):         # plan pięter robi to sam (wpadniecie._powrot)
                cb._patrol_sync_idx(p)
        except Exception as e:
            if type(e).__name__ == "Zatrzymano":
                raise
            self.log(f"[ORBITA] powrót na trasę nie wyszedł ({e!r})")
            try:
                cb._patrol_sync_idx(p)
            except Exception:
                pass
        self.ep = None
        cb.pauza(0.15, 0.35)
        return True

    def _alarm(self, powod, p, teraz):
        cb = self.cb
        ep = self.ep
        self.faza = "alarm"
        wp = cb._wp()
        if wp is not None and wp.st is not None:
            wp.st["alarm"] = True               # wpadniecie.tick tylko czeka; pietra.py nie kończy przejścia w tle
            if getattr(cb, "pietra", None) is not None:
                cb.pietra.st = None
        czas = teraz - ep["t0"]
        tresc = f"orbita {self._opis(ep['zd'])}; wyjście nie wyszło ({powod}); jestem w {tuple(p)}"
        self.log(f"[ORBITA] ALARM, {tresc}. Zatrzymuję bota (STOP).")
        self._tele("alarm", powod=powod, wynik="alarm", poz=list(p), czas_s=round(czas, 1), pola=[list(q) for q in ep["pola"]])
        try:
            import powiadom  # noqa: PLC0415
            powiadom.powiadom("Bot: orbita bez wyjścia", tresc, "critical", "orbita")
        except Exception:
            pass
        al = getattr(cb, "alarm", None)
        if callable(al):
            try:
                al(f"orbita: {tresc}")
            except Exception:
                pass
        plik = self.plik_stop
        if plik is None and not os.environ.get("RETRONIC_TESTY"):
            import bot  # noqa: PLC0415
            plik = bot.STOP
        self.stop_zapisany = False
        if plik is not None:
            try:
                Path(plik).write_text(f"orbita: {tresc}\n")
                self.stop_zapisany = True
                self.log(f"[ORBITA] zapisałem {plik} (zatrzymanie bota).")
            except OSError as e:
                self.log(f"[ORBITA] nie zapisałem STOP ({e})")
        cb.pauza(1.0, 2.0)
        return True
