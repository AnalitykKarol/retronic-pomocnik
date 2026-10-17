"""Unikanie zwykłych graczy (nie GM/PK; te obsługuje cavebot stanem GRACZ) bez zatrzymywania bota.

Czysta logika, bez wejścia/wyjścia: cavebot podaje listę stworów, pozycję, trasę i funkcję drogi
(A* z mapa.py), a dostaje decyzję (Ruch). Zasady (Karol 11.10):
 - gracz w promieniu UNIKANIE_PROMIEN przez UNIKANIE_DEBOUNCE s (albo w UNIKANIE_PUNKT_D od razu) włącza unikanie; trwa, dopóki ktoś jest
   w UNIKANIE_PROMIEN_MAX, i kończy się po UNIKANIE_ZNIKL_S s bez gracza (wtedy normalny plan);
 - cele (moby) w UNIKANIE_MOB_PROMIEN od gracza są pomijane (poza tym, co stoi obok nas albo nas gryzie);
 - punkt trasy bliżej gracza niż UNIKANIE_PUNKT_D jest pomijany: bierzemy następny punkt rotacji
   (do przodu), a gdy się nie da, poprzedni (cofamy się); droga A* nie schodzi bliżej gracza niż
   UNIKANIE_DROGA_MIN (ani bliżej niż stoimy teraz);
 - gracz zamyka drogę: cofamy się i czekamy w ruchu (krok w tył, krok w przód), nigdy nie stoimy;
   po UNIKANIE_BLOK_S s bez zmiany: inny punkt rotacji z całej trasy, a potem "luz" (trasa dalej, byle
   nie przez gracza i nie tuż obok) na kolejne UNIKANIE_BLOK_S s;
 - powiadomienie: gracz na spocie dłużej niż UNIKANIE_SPOT_S, najwyżej raz na UNIKANIE_POWIADOM_S;
 - tor gracza (UNIKANIE_TOR, 17.10, dane_tibia/SPEC_unikanie_tor_gracza_1017.md): z historii pozycji liczymy kierunek ruchu gracza;
   droga prowadząca tam, dokąd on idzie, i w jego stronę ("idziemy za nim") jest odrzucana; gracz, który zniknął z widoku,
   zostaje "duchem" (ostatnia pozycja i kierunek) przez UNIKANIE_TOR_PAMIEC_S, a unikanie w tym czasie trwa.
Stałe czyta z `konf` (moduł cavebot) przy każdym wywołaniu, więc pokrętła z na_zywo.json działają od razu."""
import time
from collections import deque

PRZOD = 40            # ile punktów trasy do przodu sprawdzamy przy omijaniu
TYL = 15              # ile punktów wstecz
ASTAR_MAX = 12        # maks. wywołań drogi w jednej decyzji (dalej: skan globalny po UNIKANIE_BLOK_S)
ASTAR_GLOBALNY = 60
DROGA_MAX = 60        # pola: dłuższa droga omijająca nie jest "omijaniem" (skan globalny: 2.5x)
LUZ_D = 3             # w trybie luzu: punkt i droga nie bliżej niż tyle od gracza (nigdy tuż obok)
LUZ_S = 45.0          # s luzu po nieudanym skanie globalnym
OK_RESET_S = 10.0     # s spokojnej trasy zerujące licznik blokady
PRZEPLAN_S = 1.0      # s: jak często w blokadzie ponawiamy szukanie wolnego punktu
PAUZA_WIG = (0.3, 0.9)  # s: krótka pauza po dojściu do punktu czekania (naturalny ruch)
MOB_LOG_S = 30.0


def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


class Ruch:
    """Decyzja dla trasy: idx = punkt, do którego idziemy; droga = pola A* (bez pozycji) albo None;
    zmiana = True, gdy idx różni się od tego, co cavebot i tak by wybrał."""
    __slots__ = ("idx", "droga", "tryb", "powod", "zmiana", "pauza")

    def __init__(self, idx, droga, tryb, powod="", zmiana=False, pauza=None):
        self.idx, self.droga, self.tryb, self.powod, self.zmiana, self.pauza = idx, droga, tryb, powod, zmiana, pauza

    def __repr__(self):
        return f"Ruch(idx={self.idx}, tryb={self.tryb}, zmiana={self.zmiana}, droga={len(self.droga or [])})"


class Unikanie:
    def __init__(self, konf, zegar=time.time, log=print, zdarzenie=None, powiadom=None):
        self.konf, self.zegar, self.log = konf, zegar, log
        self.zdarzenie = zdarzenie or (lambda typ, **d: None)
        self._powiadom = powiadom
        self.gracze = []              # gracze w UNIKANIE_PROMIEN_MAX (to samo piętro), bez nas
        self.moby = []                # [(x, y)] moby w UNIKANIE_MOB_PROMIEN od gracza: droga nie przechodzi tuż obok
        self.bylo = {}                # nick -> {"od", "ost"}: obecność na spocie (luki <= UNIKANIE_ZNIKL_S nie liczą się)
        self.aktywne = False
        self.od = None                # czas aktywacji
        self.blisko_od = self.blisko_ost = None
        self.znikl_od = None
        self.ost_powiadomienie = float("-inf")
        self.zmian = 0                # ile razy zmieniono punkt w tej serii
        self.tryb = None              # None | "omin" | "tyl" | "czekaj" | "luz"
        self.blok_od = None           # od kiedy trwa "nie da się iść do przodu"
        self.ok_od = None             # od kiedy trasa jest spokojna (bez omijania)
        self.luz_do = float("-inf")
        self.plan = None              # {"k", "droga"}: ostatnia bezpieczna droga do punktu k
        self.wig = None               # {"a","b","cel"}: dwa punkty czekania w ruchu
        self.przeplan_ost = float("-inf")
        self.brak_do = float("-inf")  # do kiedy nie szukamy ponownie po porażce (koszt A*)
        self.ost_wybor = (None, None, float("-inf"))
        self.mob_log = {}             # id moba -> czas ostatniego wpisu "pomijam"
        self.pominiete_moby = 0
        self.hist = {}                # klucz gracza -> deque[(t, x, y)]: ostatnie UNIKANIE_TOR_OKNO_S s (tor gracza)
        self.kier = {}                # klucz gracza -> {"h", "x", "y", "z", "nazwa", "id", "t"}: ostatni znany kierunek
        self.duchy = []               # gracze, którzy zniknęli z widoku, ale ich tor jeszcze się liczy (UNIKANIE_TOR_PAMIEC_S)
        self.tor_log_ost = float("-inf")
        self.czat_spot = None         # czat_spot.CzatSpot: wiadomość do gracza, który wraca/zabiera moby (mózg wysyła)
        try:
            import czat_spot  # noqa: PLC0415
            self.czat_spot = czat_spot.CzatSpot(konf, zegar=zegar)
        except Exception as e:      # czat nigdy nie wywraca unikania
            self.log(f"czat_spot wyłączony: {e!r}")

    # --- stałe ---

    def _k(self, nazwa, domyslna):
        return getattr(self.konf, nazwa, domyslna)

    def wlaczone(self):
        return bool(self._k("UNIKANIE", 1))

    # --- tor gracza (UNIKANIE_TOR) ---

    def _tor_wlaczony(self):
        return bool(self._k("UNIKANIE_TOR", 0)) and self.wlaczone()

    def _tor_aktualizuj(self, gracze, poz, t):
        """Historia pozycji -> kierunek ruchu każdego gracza (g["kier"] = (dx, dy) albo None, gdy stoi) i "duchy":
        gracze, którzy zniknęli z widoku w ciągu UNIKANIE_TOR_PAMIEC_S, z ostatnią pozycją i kierunkiem."""
        if not self._tor_wlaczony():
            self.hist, self.kier, self.duchy = {}, {}, []
            for g in gracze:
                g["kier"] = None
            return
        okno = self._k("UNIKANIE_TOR_OKNO_S", 4.0)
        ruch_min = self._k("UNIKANIE_TOR_RUCH_MIN", 2)
        pamiec = self._k("UNIKANIE_TOR_PAMIEC_S", 25.0)
        widoczne = set()
        for g in gracze:
            klucz = g["id"] if g.get("id") is not None else g["nazwa"]
            widoczne.add(klucz)
            h = self.hist.setdefault(klucz, deque())
            h.append((t, g["x"], g["y"]))
            while h and t - h[0][0] > okno:
                h.popleft()
            dx, dy = h[-1][1] - h[0][1], h[-1][2] - h[0][2]
            kier = (dx, dy) if max(abs(dx), abs(dy)) >= ruch_min else None
            g["kier"] = kier
            self.kier[klucz] = {"h": kier, "x": g["x"], "y": g["y"], "z": g["z"], "nazwa": g["nazwa"],
                                "id": g.get("id"), "t": t}
        duchy = []
        for klucz in list(self.kier):
            if klucz in widoczne:
                continue
            rec = self.kier[klucz]
            if t - rec["t"] > max(pamiec, okno):
                del self.kier[klucz]
                self.hist.pop(klucz, None)
                continue
            if rec["h"] and rec["z"] == poz[2] and t - rec["t"] <= pamiec:
                duchy.append({"id": rec["id"], "nazwa": rec["nazwa"], "x": rec["x"], "y": rec["y"], "z": rec["z"],
                              "odl": _cheb((rec["x"], rec["y"]), poz), "kier": rec["h"], "duch": True})
        self.duchy = duchy

    def _za_graczem(self, poz3, droga):
        """True, gdy droga (pola bez startu) prowadzi tam, dokąd idzie gracz, i w jego stronę: v·h > 0 oraz v·r > 0
        (v = kierunek pierwszych UNIKANIE_TOR_LOOK pól, h = ruch gracza, r = wektor do gracza). Gracz stojący się nie liczy."""
        if not droga or not self._tor_wlaczony():
            return False
        zasieg = self._k("UNIKANIE_TOR_ZASIEG", 12)
        k = droga[min(len(droga), self._k("UNIKANIE_TOR_LOOK", 8)) - 1]
        vx, vy = k[0] - poz3[0], k[1] - poz3[1]
        if vx == 0 and vy == 0:
            return False
        for e in list(self.gracze) + list(self.duchy):
            h = e.get("kier")
            if not h:
                continue
            rx, ry = e["x"] - poz3[0], e["y"] - poz3[1]
            if max(abs(rx), abs(ry)) > zasieg:
                continue
            if vx * h[0] + vy * h[1] > 0 and vx * rx + vy * ry > 0:
                t = self.zegar()
                if t - self.tor_log_ost > 5.0:
                    self.tor_log_ost = t
                    self.log(f"Unikanie: nie idę za graczem {e['nazwa']}{' (zniknął z widoku)' if e.get('duch') else ''}: "
                             f"idzie w kierunku {h}, droga prowadziłaby tam samo.")
                    self.zdarzenie("unikanie_tor", gracz=e["nazwa"], gracz_id=e.get("id"), kier=list(h),
                                   duch=bool(e.get("duch")), odl=_cheb((e["x"], e["y"]), poz3))
                return True
        return False

    def _zrodlo(self):
        """Gracze do logów i powodów: widoczni, a gdy ich brak - duchy."""
        return self.gracze or self.duchy

    # --- detekcja ---

    def obserwuj(self, lista, poz, wlasna_nazwa, wylacz=False):
        """Wołane co obieg. Aktualizuje listę graczy, debounce, koniec po zniknięciu i powiadomienie.
        -> True, gdy unikanie jest aktywne."""
        t = self.zegar()
        if wylacz or not self.wlaczone():
            if self.aktywne:
                self._koniec("wylaczone", t)
            self.gracze = []
            self.duchy = []
            return False
        r_max = self._k("UNIKANIE_PROMIEN_MAX", 14)
        r = self._k("UNIKANIE_PROMIEN", 9)
        gracze = []
        for s in lista:
            if not s.get("gracz") or s.get("nazwa") == wlasna_nazwa or s.get("z") != poz[2]:
                continue
            if s.get("hp", 100) <= 0:
                continue
            odl = _cheb((s["x"], s["y"]), poz)
            if odl <= r_max:
                gracze.append({"id": s.get("id"), "nazwa": s.get("nazwa") or "?", "x": s["x"], "y": s["y"],
                               "z": s["z"], "odl": odl})
        gracze.sort(key=lambda g: g["odl"])
        self.gracze = gracze
        self._tor_aktualizuj(gracze, poz, t)
        pr = self._k("UNIKANIE_MOB_PROMIEN", 4)
        self.moby = [(s["x"], s["y"]) for s in lista
                     if not s.get("gracz") and s.get("z") == poz[2] and s.get("hp", 100) > 0
                     and _cheb((s["x"], s["y"]), poz) <= r_max
                     and any(_cheb((s["x"], s["y"]), (g["x"], g["y"])) <= pr for g in gracze)] if gracze else []
        znikl_s = self._k("UNIKANIE_ZNIKL_S", 10.0)
        # obecność na spocie (do powiadomienia)
        for g in gracze:
            rec = self.bylo.get(g["nazwa"])
            if rec is None or t - rec["ost"] > znikl_s:
                rec = self.bylo[g["nazwa"]] = {"od": t, "ost": t}
            rec["ost"] = t
        for n in [n for n, rec in self.bylo.items() if t - rec["ost"] > max(600.0, 3 * znikl_s)]:
            del self.bylo[n]
        if self.czat_spot is not None:
            self.czat_spot.obserwuj(gracze, poz, t, znikl_s)
        self._powiadomienie(t)
        # debounce / koniec
        blisko = [g for g in gracze if g["odl"] <= r]
        if not self.aktywne:
            if blisko:
                self.blisko_ost = t
                if self.blisko_od is None:
                    self.blisko_od = t
                # debounce chroni przed przypadkowym przechodniem; gracz już w odległości punktu rotacji
                # (UNIKANIE_PUNKT_D) nie czeka: w 1,5 s zbliżylibyśmy się o 4-5 pól
                if t - self.blisko_od >= self._k("UNIKANIE_DEBOUNCE", 1.5) \
                        or blisko[0]["odl"] <= self._k("UNIKANIE_PUNKT_D", 6):
                    self._start(blisko[0], t)
            elif self.blisko_od is not None and t - (self.blisko_ost or t) > 1.0:
                self.blisko_od = None
        else:
            if gracze or self.duchy:
                self.znikl_od = None
            else:
                if self.znikl_od is None:
                    self.znikl_od = t
                if t - self.znikl_od >= znikl_s:
                    self._koniec("gracz_zniknal", t)
        return self.aktywne

    def _start(self, g, t):
        self.aktywne, self.od, self.znikl_od = True, t, None
        self.zmian, self.tryb, self.blok_od, self.ok_od, self.plan, self.wig = 0, None, None, t, None, None
        self.luz_do = float("-inf")
        self.log(f"Unikanie: gracz {g['nazwa']} {g['odl']} pól od nas, omijam jego okolicę i trzymam dystans.")
        self.zdarzenie("unikanie_start", gracz=g["nazwa"], gracz_id=g["id"], odl=g["odl"],
                       powod="gracz_w_promieniu", promien=self._k("UNIKANIE_PROMIEN", 9),
                       gracze=[x["nazwa"] for x in self.gracze])

    def _koniec(self, powod, t):
        czas = t - (self.od or t)
        self.log(f"Unikanie: koniec po {czas:.0f} s ({powod}), wracam do normalnego planu.")
        self.zdarzenie("unikanie_koniec", powod=powod, czas_s=round(czas, 1), zmian=self.zmian)
        self.aktywne, self.od, self.blisko_od, self.blisko_ost, self.znikl_od = False, None, None, None, None
        self.tryb, self.blok_od, self.ok_od, self.plan, self.wig = None, None, None, None, None

    def _powiadomienie(self, t):
        spot_s = self._k("UNIKANIE_SPOT_S", 180.0)
        co_s = self._k("UNIKANIE_POWIADOM_S", 300.0)
        if t - self.ost_powiadomienie < co_s:
            return
        for nick, rec in sorted(self.bylo.items(), key=lambda kv: kv[1]["od"]):
            if t - rec["ost"] <= 1e-9 and t - rec["od"] >= spot_s:
                min_ = (t - rec["od"]) / 60.0
                self.ost_powiadomienie = t
                txt = f"gracz {nick} na spocie od {min_:.0f} min"
                self.log(f"Unikanie: {txt}.")
                self.zdarzenie("gracz_na_spocie", gracz=nick, minut=round(min_, 1))
                try:
                    f = self._powiadom
                    if f is None:
                        import powiadom as _p  # noqa: PLC0415
                        f = _p.powiadom
                    f("Gracz na spocie", txt, "normal", klucz="gracz_na_spocie")
                except Exception:
                    pass
                return

    # --- cele (moby) ---

    def _zabrany(self, g, s, t):
        """Mob tuż przy graczu g (on go bije): dowód "zabiera moby" dla czat_spot (S3)."""
        if self.czat_spot is not None and s.get("id") is not None:
            self.czat_spot.zabrany(g["nazwa"], s["id"], s.get("nazwa"), t)

    def pomin_moba(self, s, poz, gryzie=False):
        """True: nie bierzemy tego moba na cel (stoi przy graczu). Mob obok nas albo (przy gryzieniu)
        w odl 2 zostaje: bijemy to, co nas gryzie."""
        if not self.gracze or not self.wlaczone():
            return False
        odl = _cheb((s["x"], s["y"]), poz)
        if odl <= 1 and not gryzie:
            # 15.10: mob obok nas, ale też tuż przy innym graczu i nas nie gryzie: to jego mob (12:53 bilismy trolla Qubena)
            g = next((g for g in self.gracze if g["z"] == s.get("z")
                      and _cheb((s["x"], s["y"]), (g["x"], g["y"])) <= 1), None)
            if g is not None:
                t = self.zegar()
                self.pominiete_moby += 1
                self._zabrany(g, s, t)
                if t - self.mob_log.get(s.get("id"), float("-inf")) > MOB_LOG_S:
                    self.mob_log[s.get("id")] = t
                    self.log(f"Unikanie: pomijam {s.get('nazwa')} ({s['x']},{s['y']}) obok nas: stoi przy graczu "
                             f"{g['nazwa']} i nas nie bije.")
                return True
        if odl <= 1 or (gryzie and odl <= 2):
            return False
        pr = self._k("UNIKANIE_MOB_PROMIEN", 4)
        for g in self.gracze:
            if g["z"] == s.get("z") and _cheb((s["x"], s["y"]), (g["x"], g["y"])) <= pr:
                t = self.zegar()
                self.pominiete_moby += 1
                if _cheb((s["x"], s["y"]), (g["x"], g["y"])) <= 1:
                    self._zabrany(g, s, t)
                if t - self.mob_log.get(s.get("id"), float("-inf")) > MOB_LOG_S:
                    self.mob_log[s.get("id")] = t
                    if len(self.mob_log) > 200:
                        self.mob_log = {k: v for k, v in self.mob_log.items() if t - v < MOB_LOG_S}
                    self.log(f"Unikanie: pomijam {s.get('nazwa')} ({s['x']},{s['y']}), "
                             f"{_cheb((s['x'], s['y']), (g['x'], g['y']))} pól od gracza {g['nazwa']}.")
                return True
        return False

    # --- trasa ---

    def _blok(self, gracze, r):
        """Pola zakazane dla drogi: Chebyshev < r od gracza (r >= 1: samo pole gracza)."""
        z = set()
        for g in gracze:
            for dx in range(-(r - 1), r):
                for dy in range(-(r - 1), r):
                    z.add((g["x"] + dx, g["y"] + dy, g["z"]))
        return z

    def _przy_mobie(self, p):
        return any(_cheb(p, m) <= 1 for m in self.moby)

    def _min_odl(self, p):
        return min((_cheb(p, (g["x"], g["y"])) for g in self.gracze), default=999)

    def decyduj(self, poz, punkty, idx, droga_fn):
        """-> Ruch albo None (cavebot idzie normalnie). droga_fn(start(x,y,z), cel(x,y), blok(zbiór)) ->
        lista pól (bez startu, kończy się na cel) albo None."""
        t = self.zegar()
        if not self.aktywne or not (self.gracze or self.duchy) or not punkty:
            return None
        tor = self._tor_wlaczony()
        n, z = len(punkty), poz[2]
        poz3 = (poz[0], poz[1], z)
        d_now = self._min_odl(poz)
        luz = t < self.luz_do
        if self.luz_do != float("-inf") and not luz:
            self.luz_do = float("-inf")           # luz skończony: znów ścisłe zasady, nowe okno blokady
            self.blok_od = t
            self.log("Unikanie: koniec luzu, znów trzymam dystans od gracza.")
        D = LUZ_D if luz else self._k("UNIKANIE_PUNKT_D", 6)
        r_sciezki = min(LUZ_D if luz else self._k("UNIKANIE_DROGA_MIN", 4), d_now)
        r_sciezki = max(1, r_sciezki)
        blok = self._blok(self.gracze, r_sciezki)
        for (mx, my) in self.moby:                 # mob przy graczu: nie przechodzimy po nim ani obok niego
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    blok.add((mx + dx, my + dy, z))
        blok.discard(poz3)
        licznik = [0]

        def kandydat(k, budzet, limit, filtr=False):
            q = punkty[k % n]
            if q[2] != z or q[:2] == poz3[:2]:
                return None
            if self._min_odl(q) < D or self._przy_mobie(q):
                return None
            if licznik[0] >= budzet:
                return None
            licznik[0] += 1
            d = droga_fn(poz3, q[:2], blok)
            if d is None or len(d) > limit:
                return None
            if filtr and self._za_graczem(poz3, d):
                return None
            return d

        k_cel = idx % n
        if punkty[k_cel][:2] == poz3[:2] and punkty[k_cel][2] == z:
            k_cel = (k_cel + 1) % n
        q = punkty[k_cel]
        if q[2] != z:
            return None                            # zmiana piętra: nie ingerujemy
        # 1. czy bieżący cel jest bezpieczny (punkt dość daleko i da się tam dojść drogą poza strefą gracza)
        d = None
        if self._min_odl(q) >= D and not self._przy_mobie(q):
            d = self._droga_z_planu(k_cel, poz3, blok)
            if d is None:
                licznik[0] += 1
                d = droga_fn(poz3, q[:2], blok)
                if d is not None and len(d) > DROGA_MAX:
                    d = None
        d_zap = d                                  # droga do bieżącego celu bez filtra toru (stare zachowanie, gdy nic lepszego)
        if tor and d is not None and self._za_graczem(poz3, d):
            d = None                               # bezpieczna z dystansu, ale idzie za graczem: szukamy innej
        if d is not None:
            return self._bezpieczny(t, k_cel, d)
        # 2. cel zbyt blisko gracza (albo droga do niego przechodzi przy graczu)
        self.ok_od = None
        self.plan = None
        powod = self._powod(q)
        if t < self.brak_do:
            return None
        if self.tryb in ("tyl", "czekaj") and t - self.przeplan_ost < PRZEPLAN_S and self.wig:
            return self._wiggle(t, poz3, punkty, droga_fn, blok, powod, k_cel, tor=tor)
        self.przeplan_ost = t
        # eskalacja po UNIKANIE_BLOK_S bez zmiany
        if self.blok_od is not None and t - self.blok_od >= self._k("UNIKANIE_BLOK_S", 45.0) and not luz:
            for k in range(k_cel + 1, k_cel + n):
                if licznik[0] >= ASTAR_GLOBALNY:
                    break
                dd = kandydat(k, ASTAR_GLOBALNY, int(DROGA_MAX * 2.5), tor)
                if dd is not None:
                    return self._wybierz(t, k % n, dd, "omin", f"po {t - self.blok_od:.0f} s blokady inny punkt rotacji",
                                         k_cel, powod)
            self.luz_do = t + LUZ_S
            self.blok_od = t
            self.tryb, self.wig = "luz", None
            self.log(f"Unikanie: {self._k('UNIKANIE_BLOK_S', 45.0):.0f} s bez zmiany, trasa dalej "
                     f"byle nie przez gracza (luz {LUZ_S:.0f} s).")
            self.zdarzenie("unikanie_luz", s=LUZ_S, punkt=k_cel)
            return None
        # do przodu, potem do tyłu; z torem gracza najpierw bez dróg "za graczem" (przód, tył, czekanie w ruchu),
        # na końcu (brak alternatywy) jak dawniej: nie zawieszamy bota
        for filtr in ((True, False) if tor else (False,)):
            if tor and not filtr:
                if d_zap is not None:
                    return self._bezpieczny(t, k_cel, d_zap)  # jedyna bezpieczna droga to ta za graczem
                licznik[0] = 0                                # drugi przebieg (bez filtra) ma pełny budżet A*
            for off in range(1, PRZOD + 1):
                k = (k_cel + off) % n
                dd = kandydat(k, ASTAR_MAX, DROGA_MAX, filtr)
                if dd is not None:
                    self.blok_od = None
                    return self._wybierz(t, k, dd, "omin", f"{powod}, następny punkt rotacji", k_cel, powod)
                if licznik[0] >= ASTAR_MAX:
                    break
            # do tyłu (cofamy się do poprzedniego punktu)
            licznik[0] = 0
            for off in range(1, TYL + 1):
                k = (k_cel - off) % n
                dd = kandydat(k, ASTAR_MAX, DROGA_MAX, filtr)
                if dd is not None:
                    if self.blok_od is None:
                        self.blok_od = t
                    return self._wybierz(t, k, dd, "tyl", f"{powod}, cofam się do poprzedniego punktu", k_cel, powod)
                if licznik[0] >= ASTAR_MAX:
                    break
            if tor and filtr:
                r_cz = self._wiggle(t, poz3, punkty, droga_fn, blok, powod, k_cel, nowy=self.tryb != "czekaj", tor="filtr")
                if r_cz is not None:
                    if self.blok_od is None:
                        self.blok_od = t
                    return r_cz
        # nic: czekamy w ruchu
        if self.blok_od is None:
            self.blok_od = t
        return self._wiggle(t, poz3, punkty, droga_fn, blok, powod, k_cel, nowy=self.tryb != "czekaj", tor=tor)

    def _bezpieczny(self, t, k_cel, d):
        """Bieżący cel jest bezpieczny: zapamiętujemy drogę, cavebot idzie normalnie (zmiana=False)."""
        self.plan = {"k": k_cel, "droga": [tuple(p) for p in d]}
        if self.ok_od is None:
            self.ok_od = t
        if self.tryb in ("tyl", "czekaj", "omin") and t - self.ok_od >= OK_RESET_S:
            self.tryb, self.blok_od, self.wig = None, None, None
        return Ruch(k_cel, d, self.tryb, "bezpieczny", zmiana=False)

    def _powod(self, q):
        g = min(self._zrodlo(), key=lambda g: _cheb(q, (g["x"], g["y"])))
        return f"punkt {tuple(q[:2])} {_cheb(q, (g['x'], g['y']))} pól od gracza {g['nazwa']}"

    def _droga_z_planu(self, k, poz3, blok):
        """Reszta zapamiętanej bezpiecznej drogi do punktu k, jeśli nadal po niej idziemy i nic nie wchodzi w strefę."""
        p = self.plan
        if not p or p["k"] != k:
            return None
        droga = p["droga"]
        if poz3 in droga:
            rest = droga[droga.index(poz3) + 1:]
        elif droga and max(abs(poz3[0] - droga[0][0]), abs(poz3[1] - droga[0][1])) <= 1:
            rest = list(droga)           # stoimy tuż przed pierwszym polem drogi
        else:
            return None
        if not rest or any(c in blok for c in rest):
            return None
        return rest

    def _wybierz(self, t, k, droga, tryb, powod, k_stary, powod_zrodlo):
        """Zapisuje wybór nowego punktu: log + zdarzenie (tylko przy zmianie punktu albo trybu)."""
        zmiana_punktu = (k, tryb) != self.ost_wybor[:2] or t - self.ost_wybor[2] > 5.0
        self.ost_wybor = (k, tryb, t)
        self.plan = {"k": k, "droga": [tuple(p) for p in droga]}
        self.tryb = tryb
        self.wig = None
        if zmiana_punktu:
            self.zmian += 1
            g = self._zrodlo()[0]
            self.log(f"Unikanie: {powod}: punkt {k_stary} -> {k} (droga {len(droga)} pól, "
                     f"gracz {g['nazwa']} {g['odl']} pól).")
            self.zdarzenie("unikanie_punkt", tryb=tryb, powod=powod, punkt_stary=k_stary, punkt=k,
                           droga=len(droga), gracz=g["nazwa"], gracz_id=g["id"], odl=g["odl"])
        return Ruch(k, droga, tryb, powod, zmiana=True)

    def _wiggle(self, t, poz3, punkty, droga_fn, blok, powod, k_cel, nowy=False, tor=False):
        """Żadnego bezpiecznego punktu: dwa najdalsze od gracza sąsiednie punkty trasy w zasięgu
        (cofanie i powrót krok po kroku), dopóki droga się nie otworzy. Bez stania."""
        n, z = len(punkty), poz3[2]
        if self.wig is None:
            kand = []
            # z torem gracza: punkty czekania nie "za graczem"; tor="filtr" = tylko takie (brak = None bez skutków ubocznych)
            for filtr in ((True,) if tor == "filtr" else (True, False) if tor else (False,)):
                for off in range(-TYL, TYL + 1):
                    k = (k_cel + off) % n
                    q = punkty[k]
                    if q[2] != z or q[:2] == poz3[:2]:
                        continue
                    d = droga_fn(poz3, q[:2], blok)
                    if d is None or len(d) > 20:
                        continue
                    if filtr and self._za_graczem(poz3, d):
                        continue
                    kand.append((-self._min_odl(q), len(d), k))
                if kand:
                    break
            if not kand and tor == "filtr":
                return None
            if not kand:
                # brak jakiegokolwiek ruchu bez zbliżania się: pozostawiamy trasę cavebotowi
                if nowy or self.tryb != "czekaj":
                    self.log("Unikanie: brak bezpiecznego punktu do czekania, trasa idzie normalnie.")
                self.tryb = "czekaj"
                self.brak_do = t + PRZEPLAN_S
                return None
            kand.sort()
            a = kand[0][2]
            sas = [(-self._min_odl(punkty[k]), 0 if k == (a + 1) % n else 1, k)
                   for k in ((a - 1) % n, (a + 1) % n) if k != a and punkty[k][2] == z]
            b = min(sas)[2] if sas else a
            self.wig = {"a": a, "b": b, "cel": a}
            self.tryb = "czekaj"
            g = self._zrodlo()[0]
            self.log(f"Unikanie: gracz {g['nazwa']} blokuje drogę ({powod}), czekam w ruchu między "
                     f"punktami {a} i {b}.")
            self.zdarzenie("unikanie_blokada", gracz=g["nazwa"], gracz_id=g["id"], odl=g["odl"],
                           powod=powod, punkty=[a, b])
        w = self.wig
        cel_k = w["cel"]
        q = punkty[cel_k]
        pauza = None
        if q[:2] == poz3[:2]:
            w["cel"] = cel_k = w["b"] if cel_k == w["a"] else w["a"]
            q = punkty[cel_k]
            pauza = PAUZA_WIG
        d = droga_fn(poz3, q[:2], blok)
        if d is None:
            self.wig = None                   # punkt czekania przestał być osiągalny: nowy wybór w następnym obiegu
            return None
        return Ruch(cel_k, d, "czekaj", powod, zmiana=True, pauza=pauza)
