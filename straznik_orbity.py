"""Strażnik orbit (SPEC_orbity_straznik_1020, punkt B): bot nie może chodzić w kółko po kilku polach.

Przypadek K1 (Kutangen, 20.10 16:38-17:02): po upadku w dziurę w pościgu bot 24 min chodził stałym cyklem 6 pól na złym piętrze;
detektor ratunku (F1, cień) zgłosił to 41 razy i nic nie zrobił. Człowiek tak nie chodzi, a inni gracze zabijają nas wtedy, gdy
zorientują się, że to bot.

Dwie części:
  * `Detektor` — czyste liczenie jak `ratunek.Detektor` (ten sam zegar `teraz`, te same `STANY_WALKI`/`STANY_ZAMIERZONE`, ta sama
    luka MAX_PRZERWA_S). Okno przesuwne `STRAZNIK_ORBITA_S` (60 s): ORBITA = >= `STRAZNIK_ORBITA_ZMIAN` (15) zmian pozycji, wszystkie
    na jednym piętrze i w <= `STRAZNIK_ORBITA_POL` (8) różnych polach, bez długiego stania w środku; PIETRO = złe piętro >= okno.
    Walka/loot nie zeruje okna (orbita z przerwami na szczura to nadal orbita), stany zamierzone (PRZERWA, PAUZA, ...) zerują.
  * `Reakcja` — NAPRAWA, nigdy STOP (Karol 20.10, Q2; CLAUDE.md „Zasada naprawiania"). Tylko `STRAZNIK_ORBITY=2`: stop chodzenia
    (stan ORBITA, pauza 3-8 s), potem rotacja sposobów naprawy aż do skutku, między próbami losowe pauzy 2-6 s:
      wyjscie  jedna próba wg speca: plan pięter (wpadniecie.py + pietra.py) albo A* do najbliższego punktu trasy poza orbitą
      klik     klik w inne osiągalne pole 3-7 pól poza obszarem orbity (losowe, nie to samo co poprzednio)
      punkt    rotacja punktu: inne miejsce patrolu / odwrócenie pętli / inny punkt trasy (mechanizmy cavebota)
      astar    A* do DALSZEGO punktu trasy z polami orbity zakazanymi
      plan     plan pięter (wpadniecie.z_kieszeni), gdy zła kieszeń/piętro
      krok     jeden krok w losowym wolnym kierunku
    Każdy sposób ma limit czasu AKTYWNEGO (bez czasu walki/lootu, który ma pierwszeństwo). Po ROTACJE_N pełnych nieudanych rotacjach
    jedno zwykłe powiadomienie (nie critical, bez STOP, rzadko) i dalsza rotacja z dłuższymi pauzami. Kolejny epizod w ciągu
    POWROTY_OKNO_S zaczyna od mocniejszej naprawy (rotacja punktu).
Pokrętło `STRAZNIK_ORBITY`: 0 wyłączony (zero zmian w zachowaniu), 1 cień (log `[ORBITA] cień` + telemetria `straznik_orbita`),
2 działa. Progi: STRAZNIK_ORBITA_S/POL/ZMIAN, STRAZNIK_WYJSCIE_S (stałe w cavebot.py, pokrętła w pokretla.py).
"""
import collections
import random

import ratunek
from ratunek import STANY_WALKI, STANY_ZAMIERZONE

DOMYSLNE = dict(STRAZNIK_ORBITY=0, STRAZNIK_ORBITA_S=60.0, STRAZNIK_ORBITA_POL=8, STRAZNIK_WYJSCIE_S=90.0,
                STRAZNIK_ORBITA_ZMIAN=15)
MAX_STOJ_UL = 0.5                    # w oknie nie ma stania (poza walką) dłuższego niż tyle okna: to nie wahadło, tylko przystanek
PAUZA_S = (3.0, 8.0)                 # losowa pauza (stop chodzenia) po wykryciu, przed pierwszą próbą
PAUZA_MIEDZY_S = (2.0, 6.0)          # losowa pauza między sposobami naprawy
PAUZA_DLUGA_S = (6.0, 15.0)          # ... po powiadomieniu (dłuższe)
DEBOUNCE_S = 300.0                   # ten sam sygnał w tym samym miejscu najwcześniej po tylu s
POWROTY_OKNO_S = 1800.0              # drugi epizod w tym oknie = start od mocniejszej naprawy (rotacja punktu)
ROTACJE_N = 2                        # tyle pełnych nieudanych rotacji = jedno zwykłe powiadomienie
POWIADOM_CO_S = 1800.0               # powiadomienie najwyżej raz na tyle s
POSTEP_POL = 3                       # postęp = >= tyle pól od najbliższego pola orbity (albo powrót na piętro trasy)
KAND_TRASY = 8                       # ile najbliższych punktów trasy/patrolu sprawdzamy A*
LIMIT_KLIK_S = 25.0                  # limity czasu aktywnego sposobów (s); wyjscie/astar/plan: STRAZNIK_WYJSCIE_S
LIMIT_PUNKT_S = 30.0
PLAN_MAX_S = 120.0                   # plan pięter zwijamy zawsze przed PIETRA_MAX_S (150 s) wpadniecie.py, mimo STRAZNIK_WYJSCIE_S
MAX_DT_S = 6.0                       # dłuższa luka między obiegami reakcji = była walka/loot: nie liczy się do limitów
KLIK_MIN, KLIK_MAX = 3, 7            # klik: odległość pola od najbliższego pola orbity
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
        self.walka = collections.deque()    # (t, poz) pozycji z walki/lootu w oknie: liczą się do obszaru, nie do zmian
        self.pietro_t = 0.0                 # s poza walką na złym piętrze
        self.ost = {}                       # rodzaj -> (t, poz): debounce

    def k(self, nazwa):
        return getattr(self.konf, nazwa, DOMYSLNE[nazwa]) if self.konf is not None else DOMYSLNE[nazwa]

    def reset(self):
        """Okno od nowa (luka w obserwacji, stan zamierzony, koniec reakcji)."""
        self.biegi.clear()
        self.walka.clear()
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
            # walka/loot nie zeruje okna i nie jest ruchem orbity (po niej liczymy dalej), ale pola, na których staliśmy
            # w walce, wchodzą do obszaru: pościg o 14 pól w bok to nie ta sama orbita (pomiar 14-20.10: fałszywe wyzwolenia)
            if not self.walka or self.walka[-1][1] != poz:
                self.walka.append((teraz, poz))
            while self.walka and self.walka[0][0] <= teraz - float(self.k("STRAZNIK_ORBITA_S")):
                self.walka.popleft()
            return []
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
        while self.walka and self.walka[0][0] <= teraz - okno:
            self.walka.popleft()
        nowe = []
        if zle_pietro and self.pietro_t >= okno:
            pola = list(dict.fromkeys(r[1] for r in reversed(b)))[:20]            # ostatnie różne pola (A* wyjścia omija je)
            nowe += self._zdarzenie("pietro", teraz, poz, trwa_s=round(self.pietro_t, 1), pola=sorted(list(p) for p in pola))
        if teraz - b[0][0] >= okno:
            nowe += self._orbita(teraz, poz)
        return nowe

    def _orbita(self, teraz, poz):
        b = self.biegi
        zmian = len(b) - 1
        if zmian < int(self.k("STRAZNIK_ORBITA_ZMIAN")):
            return []
        okno_ = float(self.k("STRAZNIK_ORBITA_S"))
        pola = {p for _, p, _, _, _ in b} | {p for tw, p in self.walka if tw > teraz - okno_}
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
    """Maszyna stanów naprawy (STRAZNIK_ORBITY=2). `cb` = Cavebot, `konf` = moduł cavebot (stałe). Nigdy STOP ani alarm critical.
    faza: None | start | pauza | m_<sposób>. `tick(poz, teraz)`: True = obieg zużyty, None = bot pracuje normalnie (sposób `punkt`)."""

    def __init__(self, cb, konf=None, log=print):
        self.cb = cb
        self.konf = konf
        self.log = log
        self.faza = None
        self.ep = None
        self.epizody = 0
        self.hist = []                      # czasy startów epizodów (zegar bota)
        self.var_punkt = 0                  # kolejny wariant rotacji punktu (przeżywa epizody: za każdym razem inny)
        self.ost_powiad = float("-inf")
        self.akt = 0.0                      # czas aktywny reakcji (bez walki/lootu), s
        self.ost_tick = None
        self.det = None                     # Detektor do wyzerowania po epizodzie (ustawia cavebot)
        self.historia = []                  # [(sposób, wynik)] ostatniego epizodu (testy, telemetria)
        self.wp_moj = False                 # True, gdy wp.st / pietra.st ustawił strażnik (sprzątamy tylko swoje)

    def k(self, nazwa):
        return getattr(self.konf, nazwa, DOMYSLNE[nazwa]) if self.konf is not None else DOMYSLNE[nazwa]

    def aktywna(self):
        return self.faza is not None

    def sprzatnij(self):
        """Przerwanie reakcji z zewnątrz (wyjątek, STRAZNIK_ORBITY 2->0 w locie): oddajemy stan, który ustawił strażnik
        (wp.st, pietra.st), bo zwykłe 3b doprowadziłoby go do alarmu wpadniecie.py."""
        cb = self.cb
        if self.wp_moj:
            try:
                wp = cb._wp()
                if wp is not None:
                    wp.st = None
                    wp.bez_alarmu = False
                if getattr(cb, "pietra", None) is not None:
                    cb.pietra.st = None
            except Exception:
                pass
            self.wp_moj = False
        self.faza = None
        self.ep = None

    def _tele(self, etap, **d):
        t = getattr(self.cb, "tele", None)
        if t is not None:
            try:
                t.zdarzenie("straznik_orbita", etap=etap, **d)
            except Exception:
                pass

    @staticmethod
    def _opis(zd):
        if zd["rodzaj"] == "pietro":
            return f"złe piętro z{zd['poz'][2]} od {zd.get('trwa_s')} s"
        return f"{zd.get('zmian')} zmian w {len(zd.get('pola') or [])} polach przez {zd.get('czas_s')} s, stany {zd.get('stany')}"

    # --- wejście: zdarzenie z detektora ---
    def start(self, zd, teraz):
        self.epizody += 1
        self.faza = "start"
        self.hist = [x for x in self.hist if teraz - x < POWROTY_OKNO_S] + [teraz]
        powrot = len(self.hist) >= 2
        wp = self.cb._wp()
        zle = zd["rodzaj"] == "pietro" or bool(wp is not None and not wp._trasa_na_pietrze(zd["poz"][2]))
        self.ep = {"zd": zd, "t0": teraz, "z": zd["poz"][2], "pola": [tuple(p) for p in zd.get("pola") or [tuple(zd["poz"])]],
                   "nr": self.epizody, "powrot": powrot, "zle": zle, "runda": 0, "n_met": 0, "kolejka": [],
                   "uzyte_kliki": [], "uzyte_cele": [], "powiadomiono": False}
        self.historia = []
        self.log(f"[ORBITA] wykryto {zd['rodzaj']} w {tuple(zd['poz'])}: {self._opis(zd)}; zatrzymuję chodzenie"
                 f"{' (kolejny epizod w 30 min: zaczynam od zmiany punktu)' if powrot else ''}.")
        self._tele("start", powrot=powrot, **{k: v for k, v in zd.items() if k != "t"})

    # --- obieg ---
    def tick(self, poz, teraz):
        if self.faza is None:
            return None
        cb = self.cb
        p = (int(poz[0]), int(poz[1]), int(poz[2]))
        dt = 0.0 if self.ost_tick is None else teraz - self.ost_tick
        self.ost_tick = teraz
        if 0 < dt <= MAX_DT_S:
            self.akt += dt                   # luka (walka, loot, pauza po ticku) dłuższa niż MAX_DT_S nie liczy się do limitów
        f = self.faza
        if f == "start":
            self._stop_chodzenia(p)
            self.ep["pauza_do"] = teraz + random.uniform(*PAUZA_S)
            self.faza = f = "pauza"
            self.log(f"[ORBITA] stoję {self.ep['pauza_do'] - teraz:.1f} s, potem sposoby naprawy (rotacja, nigdy STOP).")
            self._tele("pauza", poz=list(p), pauza_s=round(self.ep["pauza_do"] - teraz, 1))
        if f == "pauza":
            cb.ustaw_stan("ORBITA", f"pauza przed próbą naprawy w {tuple(p)}")
            if teraz < self.ep["pauza_do"]:
                cb.pauza(0.3, 0.8)
                return True
            return self._nastepny(p, teraz)
        if self._sukces(p):
            return self._postep(p, teraz, "wyszedłem z orbity")
        met = f[2:]
        r = getattr(self, "_t_" + met)(p, teraz)
        return r

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

    # --- rotacja ---
    def _nowa_kolejka(self):
        ep = self.ep
        if ep["zle"]:
            return ["plan", "klik", "krok"]
        if ep["runda"] == 0 and not ep["powrot"]:
            return ["wyjscie", "klik", "punkt", "astar", "plan", "krok"]
        if ep["runda"] == 0:                  # kolejny epizod w krótkim czasie: mocniejsza naprawa od razu
            return ["punkt", "klik", "astar", "plan", "krok", "wyjscie"]
        return ["klik", "punkt", "astar", "plan", "krok"]

    def _nastepny(self, p, teraz):
        ep = self.ep
        proby = 0
        while True:
            if not ep["kolejka"]:
                if ep["n_met"]:      # pełna rotacja za nami
                    ep["runda"] += 1
                    self._po_rundzie(p, teraz)
                ep["kolejka"] = self._nowa_kolejka()
            met = ep["kolejka"].pop(0)
            proby += 1
            ep["t_met"] = teraz
            ep["akt0"] = self.akt
            ep["n_met"] += 1
            ok = getattr(self, "_s_" + met)(p, teraz)
            if ok:
                ep["w_rundzie"] = ep.get("w_rundzie", 0) + 1
                self.faza = "m_" + met
                self.log(f"[ORBITA] sposób {ep['n_met']} (runda {ep['runda'] + 1}): {met}.")
                self._tele("sposob", sposob=met, nr=ep["n_met"], runda=ep["runda"] + 1, poz=list(p))
                self.historia.append((met, "start"))
                return True
            ep["n_met"] -= 1
            self.historia.append((met, "pominiety"))
            if proby >= 12:                                        # nic nie ma zastosowania: pauza i od nowa
                ep["kolejka"] = []
                return self._pauza(p, teraz, "żaden sposób nie ma zastosowania")

    def _po_rundzie(self, p, teraz):
        ep = self.ep
        self.log(f"[ORBITA] rotacja {ep['runda']} bez skutku.")
        self._tele("rotacja_bez_skutku", runda=ep["runda"], poz=list(p))
        if ep["runda"] >= ROTACJE_N and teraz - self.ost_powiad >= POWIADOM_CO_S:
            self.ost_powiad = teraz
            ep["powiadomiono"] = True
            tresc = f"orbita {self._opis(ep['zd'])}; {ep['runda']} rotacje naprawy bez skutku, próbuję dalej; jestem w {tuple(p)}"
            self.log(f"[ORBITA] powiadomienie (zwykłe, bez STOP): {tresc}")
            self._tele("powiadomienie", runda=ep["runda"], poz=list(p))
            try:
                import powiadom  # noqa: PLC0415
                powiadom.powiadom("Bot: orbita, naprawiam", tresc, "normal", "orbita")
            except Exception:
                pass

    def _pauza(self, p, teraz, powod):
        ep = self.ep
        self._stop_chodzenia(p)
        zakres = PAUZA_DLUGA_S if ep["powiadomiono"] else PAUZA_MIEDZY_S
        ep["pauza_do"] = teraz + random.uniform(*zakres)
        self.faza = "pauza"
        self.log(f"[ORBITA] {powod}; stoję {ep['pauza_do'] - teraz:.1f} s i próbuję kolejny sposób.")
        cb = self.cb
        cb.pauza(0.3, 0.8)
        return True

    def _koniec_sposobu(self, p, teraz, powod):
        met = self.faza[2:]
        self.historia.append((met, powod))
        self._tele("sposob_nieudany", sposob=met, powod=powod, poz=list(p))
        return self._pauza(p, teraz, f"sposób {met} bez skutku ({powod})")

    # --- postęp ---
    def _wyszedl(self, p):
        return self._daleko(p, self.ep["pola"])

    def _daleko(self, q, pola):
        return all(q[2] != f[2] or _czeb(q, f) >= POSTEP_POL for f in pola)

    def _sukces(self, p):
        ep = self.ep
        if ep["zle"]:
            wp = self.cb._wp()
            na_trasie = wp._trasa_na_pietrze(p[2]) if wp is not None else any(q[2] == p[2] for q in self.cb.punkty)
            return p[2] != ep["z"] and na_trasie
        return p[2] != ep["z"] or self._wyszedl(p)

    def _postep(self, p, teraz, powod, sync=True):
        cb = self.cb
        ep = self.ep
        po_punkcie = self.faza == "m_punkt"          # bot pracuje na już zmienionym punkcie: nie nadpisujemy go synchronizacją
        self.faza = None
        czas = teraz - ep["t0"]
        self.log(f"[ORBITA] postęp: {powod}, jestem w {tuple(p)} po {czas:.0f} s od wykrycia ({ep['n_met']} sposobów); wracam do pracy.")
        self._tele("postep", wynik="ok", poz=list(p), czas_s=round(czas, 1), powod=powod, sposoby=ep["n_met"],
                   pola=[list(q) for q in ep["pola"]])
        wp = cb._wp()
        if self.wp_moj and wp is not None and wp.st is not None:
            wp.st = None
            if getattr(cb, "pietra", None) is not None:
                cb.pietra.st = None
        self.wp_moj = False
        try:
            if sync and not po_punkcie and not cb._wypad_wroc_na_trase(p):   # plan pięter robi to sam
                cb._patrol_sync_idx(p)
        except Exception as e:
            if type(e).__name__ == "Zatrzymano":
                raise
            self.log(f"[ORBITA] powrót na trasę nie wyszedł ({e!r})")
        self.ep = None
        if self.det is not None:
            self.det.po_reakcji()
        cb.pauza(0.15, 0.35)
        return True

    # --- sposoby: _s_<nazwa> = start (True = zastosowano), _t_<nazwa> = obieg ---
    def _zakazane(self, p):
        return [(q[0], q[1]) for q in self.ep["pola"] if tuple(q[:2]) != tuple(p[:2]) and q[2] == p[2]]

    def _stwory_xy(self, p):
        cb = self.cb
        return [(s["x"], s["y"]) for s in (cb.ostatnie_stwory or [])
                if s.get("z") == p[2] and s.get("hp", 100) > 0 and (s["x"], s["y"]) != tuple(p[:2])
                and not (s.get("gracz") and s.get("nazwa") == getattr(cb.postac, "nazwa", None))]

    def _kandydaci(self, z):
        cb = self.cb
        wyn = [(q[0], q[1]) for q in (cb.punkty or []) if q[2] == z]
        try:
            if cb._patrol_pietra_ok():
                wyn += [(m["x"], m["y"]) for m in (cb.miejsca or []) if m.get("z") == z]
        except Exception:
            pass
        return list(dict.fromkeys(wyn))

    def _droga(self, p, cel_xy, extra=()):
        try:
            return self.cb._droga_do((p[0], p[1], p[2]), cel_xy, self._zakazane(p) + list(extra))   # bez zapasowej drogi „po samej mapie”
        except Exception as e:
            if type(e).__name__ == "Zatrzymano":
                raise
            return None

    def _ustaw_cel(self, p, cel, limit_s):
        ep = self.ep
        ep.update(cel=cel, fails=0, limit=limit_s, ost_poz=tuple(p))

    # wyjscie: wg speca jedna próba: plan pięter (kieszeń) albo A* do najbliższego punktu trasy
    def _s_wyjscie(self, p, teraz):
        if self._s_plan(p, teraz):
            self.ep["alias"] = "plan"
            return True
        kand = [q for q in self._kandydaci(p[2]) if self._daleko((q[0], q[1], p[2]), self.ep["pola"])]
        kand.sort(key=lambda q: _czeb(q, p))
        for q in kand[:KAND_TRASY]:
            if self._droga(p, q) is not None:
                self._ustaw_cel(p, (q[0], q[1], p[2]), float(self.k("STRAZNIK_WYJSCIE_S")))
                self.ep["alias"] = "droga"
                self.ep["uzyte_cele"].append(q)
                return True
        return False

    def _t_wyjscie(self, p, teraz):
        if self.ep.get("alias") == "plan":
            return self._t_plan(p, teraz)
        return self._idz(p, teraz)

    # klik: inne osiągalne pole 3-7 pól poza obszarem orbity
    def _s_klik(self, p, teraz):
        ep = self.ep
        cb = self.cb
        m = cb.mapa
        cand = []
        for dx in range(-(KLIK_MAX + 8), KLIK_MAX + 9):
            for dy in range(-(KLIK_MAX + 8), KLIK_MAX + 9):
                c = (p[0] + dx, p[1] + dy, p[2])
                odl = min((_czeb(c, f) for f in ep["pola"] if f[2] == p[2]), default=KLIK_MAX)
                if not KLIK_MIN <= odl <= KLIK_MAX:
                    continue
                if any(_czeb(c, u) <= 1 for u in ep["uzyte_kliki"]):
                    continue
                if m is not None:
                    try:
                        v = int(m.flagi(c[0], c[1], c[2]))
                    except Exception:
                        continue
                    if not v & 1 or v & 4 or v & 2:
                        continue
                if cb.pole_zmiany_pietra(c):
                    continue
                cand.append(c)
        random.shuffle(cand)
        for c in cand[:14]:
            d = self._droga(p, c[:2])
            if d is not None and len(d) <= 30:
                ep["uzyte_kliki"].append(c)
                self._ustaw_cel(p, c, LIMIT_KLIK_S)
                self.log(f"[ORBITA] klik w pole {c[:2]} ({len(d)} kroków drogi).")
                return True
        return False

    def _t_klik(self, p, teraz):
        return self._idz(p, teraz)

    # astar: dalszy punkt trasy z polami orbity zakazanymi
    def _s_astar(self, p, teraz):
        ep = self.ep
        kand = [q for q in self._kandydaci(p[2]) if self._daleko((q[0], q[1], p[2]), ep["pola"]) and q not in ep["uzyte_cele"]]
        dalekie = [q for q in kand if _czeb(q, p) >= 8] or sorted(kand, key=lambda q: -_czeb(q, p))[:3]
        random.shuffle(dalekie)
        for q in dalekie[:KAND_TRASY]:
            if self._droga(p, q) is not None:
                ep["uzyte_cele"].append(q)
                self._ustaw_cel(p, (q[0], q[1], p[2]), float(self.k("STRAZNIK_WYJSCIE_S")))
                self.log(f"[ORBITA] A* do dalszego punktu trasy {q}.")
                return True
        return False

    def _t_astar(self, p, teraz):
        return self._idz(p, teraz)

    def _idz(self, p, teraz):
        """Wspólny marsz do ep['cel'] po drodze z polami orbity zakazanymi; koniec: dotarł / limit / stoi w miejscu."""
        cb = self.cb
        ep = self.ep
        cel = ep["cel"]
        if self.akt - ep["akt0"] > ep["limit"]:
            return self._koniec_sposobu(p, teraz, "limit czasu")
        d = self._droga(p, cel[:2], self._stwory_xy(p))
        if d is None:
            return self._koniec_sposobu(p, teraz, "brak drogi")
        if not d and _czeb(p, cel) == 0:
            return self._koniec_sposobu(p, teraz, "dotarłem, orbita nie ustała")
        cb.ustaw_stan("ORBITA", f"naprawa: idę do {cel[:2]}")
        r = None
        try:
            if d:
                r = cb.idz_do(self._cel_kroku(p, d), p, True, krok=d[0])
        except Exception as e:
            if type(e).__name__ == "Zatrzymano":
                raise
            self.log(f"[ORBITA] krok naprawy: błąd {e!r}")
        q = tuple(cb.postac.pozycja())
        if q[2] != p[2] or self._sukces(q):
            return self._postep(q, teraz, "wyszedłem z orbity" if q[2] == p[2] else "zmiana piętra")
        ep["fails"] = 0 if (r and q != tuple(p)) else ep.get("fails", 0) + 1
        if ep["fails"] >= 12:
            return self._koniec_sposobu(q, teraz, "kroki nie ruszają postaci")
        return True

    @staticmethod
    def _cel_kroku(p, d):
        """Najdalsze pole drogi (do 4 pól), do którego z `p` idzie się prosto po polach drogi (klient nie skróci przez orbitę)."""
        for k in range(min(len(d), 4), 0, -1):
            dx, dy = d[0][0] - p[0], d[0][1] - p[1]
            if all(d[i][0] - (p[0] if i == 0 else d[i - 1][0]) == dx and d[i][1] - (p[1] if i == 0 else d[i - 1][1]) == dy
                   for i in range(k)):
                return (d[k - 1][0], d[k - 1][1])
        return (d[0][0], d[0][1])

    # punkt: rotacja punktu trasy / miejsca patrolu / kierunku pętli (mechanizmy cavebota); potem bot pracuje sam
    def _s_punkt(self, p, teraz):
        cb = self.cb
        ep = self.ep
        n = len(cb.punkty or [])
        patrol = False
        try:
            patrol = bool(cb._patrol_aktywny())
        except Exception:
            pass
        warianty = ["patrol", "odwroc", "inny"] if patrol else ["inny", "odwroc"]
        if patrol and not cb.patrol:
            warianty = ["odwroc", "inny"]
        if ep.get("odwrocono"):                  # jedno odwrócenie pętli na epizod (inaczej wahadło kierunków)
            warianty = [w for w in warianty if w != "odwroc"] or ["inny"]
        if n < 2 and not patrol:
            return False
        wariant = warianty[self.var_punkt % len(warianty)]
        self.var_punkt += 1
        opis = None
        if wariant == "patrol" and cb.patrol:
            try:
                pp = cb.patrol
                cb.patrol_blok[pp["m"]["id"]] = teraz + float(getattr(self.konf, "PATROL_BLOK_S", 150.0))
                try:
                    cb._patrol_zakoncz(pp, "strażnik orbit")
                except Exception:
                    pass
                cb._patrol_reset(False)
                opis = f"inne miejsce patrolu (blokuję {pp['m']['id']})"
            except Exception as e:
                if type(e).__name__ == "Zatrzymano":
                    raise
                return False
        elif wariant == "odwroc" and n >= 2:
            ep["odwrocono"] = True
            cb.punkty.reverse()
            cb.idx = (n - (cb.idx - 1) % n) % n
            cb.__dict__["utk_zakaz"] = {}
            opis = f"odwrócenie pętli (punkt {cb.idx})"
        else:
            kand = [i for i in range(n) if cb.punkty[i][2] == p[2] and i != cb.idx
                    and self._daleko(cb.punkty[i], ep["pola"]) and _czeb(cb.punkty[i], p) >= 5]
            if not kand:
                return False
            k = random.choice(kand)
            cb.idx = k
            opis = f"inny punkt trasy {k} {tuple(cb.punkty[k])}"
        for a in ("klik_j", "klik_cel", "trasa_droga", "utk_okno"):
            setattr(cb, a, None)
        cb.nieudane = 0
        cb.cel = None
        ep["limit"] = LIMIT_PUNKT_S
        self.log(f"[ORBITA] rotacja punktu: {opis}.")
        self._tele("rotacja_punktu", wariant=wariant, opis=opis, poz=list(p))
        return True

    def _t_punkt(self, p, teraz):
        if self.akt - self.ep["akt0"] > self.ep["limit"]:
            return self._koniec_sposobu(p, teraz, "limit czasu")
        return None                              # bot pracuje normalnie na nowym punkcie; _sukces sprawdzamy co obieg

    # plan: plan pięter (wpadniecie.py), gdy kieszeń/złe piętro i istnieje plan po mapie
    def _s_plan(self, p, teraz):
        wp = self.cb._wp()
        if wp is None or wp.st is not None:
            return False
        try:
            if not wp.z_kieszeni(p, teraz):                      # brak kieszeni/złego piętra albo trasa osiągalna
                return False
            if wp._znajdz_plan(p, set()) is None:                # plan musi istnieć: wpadniecie.py bez planu zaalarmowałoby STOP, my nie dopuszczamy
                wp.st = None
                return False
        except Exception as e:
            if type(e).__name__ == "Zatrzymano":
                raise
            self.log(f"[ORBITA] plan pięter nie wyszedł ({e!r})")
            wp.st = None
            return False
        self.wp_moj = True
        self.ep["limit"] = min(float(self.k("STRAZNIK_WYJSCIE_S")), PLAN_MAX_S)
        self.ep["alias"] = "plan"
        self.log(f"[ORBITA] plan pięter (wpadniecie.py), wyjście na z{wp.st['z0'] if wp.st else '?'}.")
        return True

    def _t_plan(self, p, teraz):
        cb = self.cb
        ep = self.ep
        wp = cb._wp()
        if wp is None or wp.st is None:
            return self._koniec_sposobu(p, teraz, "plan pięter zakończony bez skutku")
        if self.akt - ep["akt0"] > ep["limit"]:
            return self._zwin_plan(p, teraz, "limit czasu")
        st = wp.st
        if st["krok"] is None and teraz >= st["nast"] and wp._znajdz_plan(p, st["zle"]) is None:
            return self._zwin_plan(p, teraz, "plan wyczerpany")      # wpadniecie.py zaalarmowałoby STOP: my nie dopuszczamy
        # wpadniecie.py w tym kroku nie alarmuje (STOP + critical): porażkę oddaje nam (st["porazka_dla_straznika"]), a licznik
        # porażek pięter (critical po PIETRA_PORAZKI_STOP) liczy od zera i po kroku wraca do dawnej wartości
        porazki = getattr(cb, "pietra_porazki", 0)
        cb.pietra_porazki = 0
        wp.bez_alarmu = True
        try:
            wp.tick(p, teraz)
        except Exception as e:
            if type(e).__name__ == "Zatrzymano":
                raise
            self.log(f"[ORBITA] plan pięter: błąd {e!r}")
            cb.pietra_porazki = porazki
            return self._zwin_plan(p, teraz, "błąd")
        finally:
            wp.bez_alarmu = False
        if wp.st is None:
            q = tuple(cb.postac.pozycja())
            self.wp_moj = False
            if self._sukces(q):
                return self._postep(q, teraz, "plan pięter zakończony", sync=False)
            cb.pietra_porazki = porazki
            return self._koniec_sposobu(q, teraz, "plan pięter zakończony bez skutku")
        cb.pietra_porazki = porazki
        if wp.st.get("porazka_dla_straznika"):
            return self._zwin_plan(p, teraz, f"wpadniecie.py bez wyjścia: {wp.st['porazka_dla_straznika']}")
        return True

    def _zwin_plan(self, p, teraz, powod):
        wp = self.cb._wp()
        self.wp_moj = False
        if wp is not None:
            wp.st = None
            wp.bez_alarmu = False
        if getattr(self.cb, "pietra", None) is not None:
            self.cb.pietra.st = None
        return self._koniec_sposobu(p, teraz, powod)

    # krok: jeden krok w losowym wolnym kierunku
    def _s_krok(self, p, teraz):
        cb = self.cb
        zajete = set(self._stwory_xy(p))
        orb = {(q[0], q[1]) for q in self.ep["pola"]}
        wolne = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c = (p[0] + dx, p[1] + dy, p[2])
            if (c[0], c[1]) in zajete or cb.pole_zmiany_pietra(c):
                continue
            if cb.mapa is not None:
                try:
                    v = int(cb.mapa.flagi(c[0], c[1], c[2]))
                except Exception:
                    continue
                if not v & 1 or v & 4 or v & 2:
                    continue
            wolne.append(c)
        if not wolne:
            return False
        poza = [c for c in wolne if (c[0], c[1]) not in orb]
        c = random.choice(poza or wolne)
        self.ep["krok_cel"] = c
        return True

    def _t_krok(self, p, teraz):
        cb = self.cb
        c = self.ep["krok_cel"]
        cb.ustaw_stan("ORBITA", f"naprawa: krok w {c[:2]}")
        try:
            cb.krok_do(c)
        except Exception as e:
            if type(e).__name__ == "Zatrzymano":
                raise
        q = tuple(cb.postac.pozycja())
        if self._sukces(q):
            return self._postep(q, teraz, "wyszedłem z orbity")
        return self._koniec_sposobu(q, teraz, "krok nie wyprowadził z orbity")
