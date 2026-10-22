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
Mijanie (MIJANIE=1, 18.10, dane_tibia/SPEC_mijanie_graczy_1018.md) zastępuje powyższe unikanie na trasie: zamiast bańki dystansu
 i dreptania ocena kierunku gracza względem naszej pętli (nie idziemy tą samą stroną, mijamy się bez zawracania, obozowicza
 omijamy skrótem albo odwróceniem obiegu), nowy kierunek trzymamy na stałe, a przejście udostępniamy tylko gdy gracz idzie
 w naszą stronę, nie ma jak się minąć i go widzimy (krok w bok, postój, bezpiecznik). `mijanie()` jest osobną ścieżką;
 `decyduj()` i `_wiggle()` zostają nietknięte (MIJANIE=0 = dotychczasowe zachowanie).
Mijanie, poprawka 22.10 (dane_tibia/ruch/DIAGNOZA_mijanie_za_graczem_1022.md; pod MIJANIE=1, wyłączniki: 0 w konf):
 - MIJANIE_HORYZONT: odwrócony obieg (i skrót) oceniamy na tylu punktach (nie 10-20) względem przewidywanego toru gracza
   (jego pozycja + kierunek: po naszej trasie, gdy nią idzie, inaczej prosta); zbiega się z nim w tę samą stronę = odrzucony;
 - MIJANIE_ZA_S / MIJANIE_ZA_ODL: gracz za nami <= tyle pól, idący w tę samą stronę tyle sekund, dostaje przepuszczenie
   (krótka pauza z boku, MIJANIE_PAUZA_MIN_S..MAX_S, nie częściej niż MIJANIE_PAUZA_PONOW_S na gracza);
 - brak bezpiecznego kierunku: ta sama pauza zamiast marszu dalej obok gracza;
 - MIJANIE_POLUJACY_R: stojący gracz z mobem tyle pól od siebie poluje: bez skrótu, odwrócenie tylko od niego.
Stałe czyta z `konf` (moduł cavebot) przy każdym wywołaniu, więc pokrętła z na_zywo.json działają od razu."""
import math
import random
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
MIJ_WIDOK = (7, 5)    # widok gry 15x11 pól: dx +-7, dy +-5 (gracz poza nim "znika nam z oczu")
MIJ_TANG = 4          # punkty trasy brane do kierunku trasy w miejscu gracza
MIJ_SLAD_S = 30.0     # s: jak długo pamiętamy, którędy szedł gracz (Z2: jego ślad dopiero na końcu)
MIJ_LOG_S = 10.0      # s: najczęściej tak często ten sam wpis "nie ma bezpiecznego kierunku"
MIJ_ZMIANA_MIN_S = 8.0  # s: najmniejszy odstęp między dwiema zmianami kierunku (odwrócenie / skrót): bez przeskoków tam i z powrotem przy dwóch graczach
MIJ_BRAK_S = 2.0      # s: po braku bezpiecznego kierunku nie szukamy ponownie (A* co tick byłby zbędny)
# 22.10: domyślne nowych pokręteł mijania (konf.NAZWA nadpisuje; 0 = zachowanie sprzed poprawki)
MIJ_HORYZONT = 40     # MIJANIE_HORYZONT: punkty kandydata sprawdzane względem toru gracza (0 = tylko stare pts[:12/10])
MIJ_ZBIEG_D = 2       # MIJANIE_ZBIEG_D: pola: kandydat tak blisko toru gracza (w tę samą stronę, w podobnym czasie) = zbiega się z nim
MIJ_ZBIEG_DT = 6      # kroki: tolerancja czasu zbiegu (gracz idzie trochę szybciej / wolniej)
MIJ_ZA_S = 15.0       # MIJANIE_ZA_S: s, przez które gracz za nami idzie w tę samą stronę, zanim go przepuścimy (0 = wyłączone)
MIJ_ZA_ODL = 4        # MIJANIE_ZA_ODL: pola: tak blisko za nami musi być
MIJ_PAUZA_MIN_S = 2.0  # MIJANIE_PAUZA_MIN_S / MAX_S: długość przepuszczenia (losowa)
MIJ_PAUZA_MAX_S = 5.0
MIJ_PAUZA_PONOW_S = 60.0  # MIJANIE_PAUZA_PONOW_S: najczęściej raz na tyle s dla tego samego gracza
MIJ_PAUZA_BRAK = 1    # MIJANIE_PAUZA_BRAK: 1 = brak bezpiecznego kierunku -> pauza z boku zamiast marszu dalej obok gracza
MIJ_POLUJACY_R = 3    # MIJANIE_POLUJACY_R: pola: stojący gracz z mobem tak blisko poluje (0 = wyłączone)


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


class Mij:
    """Decyzja mijania dla cavebota: akcja = "odwroc" (odwróć kierunek obiegu trasy; indeks przelicza cavebot),
    "marsz" (jeden krok `krok` po drodze: skrót do `idx` albo krok w bok) albo "stoj" (stoimy z boku, gracz przechodzi)."""
    __slots__ = ("akcja", "idx", "krok", "powod")

    def __init__(self, akcja, idx=None, krok=None, powod=""):
        self.akcja, self.idx, self.krok, self.powod = akcja, idx, krok, powod

    def __repr__(self):
        return f"Mij({self.akcja}, idx={self.idx}, krok={self.krok})"


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
        # mijanie (MIJANIE): pamięć decyzji per gracz, trwające udostępnianie przejścia i skrót
        self.mij_widz = {}            # klucz gracza -> czas ostatniego zobaczenia
        self.mij_dec = {}             # klucz -> {"t", "rodzaj"}: decyzja o kierunku względem tego gracza (do jego zniknięcia)
        self.mij_odwroty = {}         # klucz obozowicza -> [czasy odwróceń obiegu przez niego]
        self.mij_slad = {}            # klucz -> deque[(t, x, y)]: którędy szedł gracz (MIJ_SLAD_S)
        self.mij_prz = None           # trwające udostępnianie przejścia: {"klucz", "nazwa", "cel", "od", "h", "stoi", ...}
        self.mij_prz_ost = {}         # klucz -> czas końca ostatniego udostępniania przejścia temu graczowi
        self.mij_skrot = None         # trwający skrót: {"cel": (x, y), "klucz", "do"}
        self.mij_wroc = None          # powrót z wnęki na pole, z którego zeszliśmy graczowi z drogi: {"cel": (x, y), "do"}
        self.mij_zmiana_ost = float("-inf")   # czas ostatniej zmiany kierunku (odwrócenie / skrót)
        self.mij_brak = {}            # klucz -> czas: nie było bezpiecznego kierunku, nie liczymy ponownie przez MIJ_BRAK_S (koszt A*)
        self.mij_zmian = 0            # zmiany kierunku w tym spotkaniu (do mijanie_koniec)
        self.mij_przejsc = 0
        self.mij_log_ost = {}         # rodzaj wpisu -> czas (bez spamu w logu)
        self.mij_pauza = None         # trwające przepuszczenie gracza: {"klucz","nazwa","od","do","cel","powod","kroki"}
        self.mij_pauza_ost = {}       # klucz -> czas początku ostatniego przepuszczenia (cooldown MIJANIE_PAUZA_PONOW_S)
        self.mij_za = {}              # klucz -> {"od","ost"}: od kiedy gracz idzie za nami w tę samą stronę
        self.mij_tory = {}            # klucz -> przewidywany tor ruchomego gracza (ustawiany w _mij_kierunek, czytany przez _mij_ocena)
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

    def _mij_wlaczone(self):
        return bool(self._k("MIJANIE", 0)) and self.wlaczone()

    def _tor_aktualizuj(self, gracze, poz, t):
        """Historia pozycji -> kierunek ruchu każdego gracza (g["kier"] = (dx, dy) albo None, gdy stoi) i "duchy":
        gracze, którzy zniknęli z widoku w ciągu UNIKANIE_TOR_PAMIEC_S, z ostatnią pozycją i kierunkiem.
        MIJANIE liczy kierunek tak samo (bez UNIKANIE_TOR), tworzy te same duchy (mijanie() z nich nie korzysta; używa ich tylko
        decyduj/_za_graczem) i dopisuje g["obs_s"] (jak długo obserwujemy, najwyżej UNIKANIE_TOR_OKNO_S)."""
        mij = self._mij_wlaczone()
        if not self._tor_wlaczony() and not mij:
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
            if mij:
                g["obs_s"] = t - h[0][0]
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
            self._mij_obserwuj([], t)
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
        self._mij_obserwuj(gracze, t)
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
            if gracze or (self.duchy and not self._mij_wlaczone()):
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
        if self._mij_wlaczone():
            self.mij_zmian = self.mij_przejsc = 0
            self.log(f"Mijanie: gracz {g['nazwa']} {g['odl']} pól od nas, patrzę w którą stronę idzie.")
            self.zdarzenie("mijanie_start", gracz=g["nazwa"], gracz_id=g["id"], odl=g["odl"], kier=list(g["kier"]) if g.get("kier") else None,
                           promien=self._k("UNIKANIE_PROMIEN", 9), gracze=[x["nazwa"] for x in self.gracze])
            return
        self.log(f"Unikanie: gracz {g['nazwa']} {g['odl']} pól od nas, omijam jego okolicę i trzymam dystans.")
        self.zdarzenie("unikanie_start", gracz=g["nazwa"], gracz_id=g["id"], odl=g["odl"],
                       powod="gracz_w_promieniu", promien=self._k("UNIKANIE_PROMIEN", 9),
                       gracze=[x["nazwa"] for x in self.gracze])

    def _koniec(self, powod, t):
        czas = t - (self.od or t)
        if self._mij_wlaczone():
            self.log(f"Mijanie: koniec spotkania po {czas:.0f} s ({powod}), zmian kierunku {self.mij_zmian}, przejść {self.mij_przejsc}.")
            self.zdarzenie("mijanie_koniec", powod=powod, czas_s=round(czas, 1), zmian_kierunku=self.mij_zmian,
                           przejsc=self.mij_przejsc)
        else:
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

    # --- mijanie graczy (MIJANIE, 18.10): kierunek gracza -> nic / odwrócenie obiegu / skrót / przejście ---

    @staticmethod
    def _mij_klucz(g):
        return g["id"] if g.get("id") is not None else g["nazwa"]

    def _mij_stoi(self, g):
        """Gracz stoi (nie ruszył się o UNIKANIE_TOR_RUCH_MIN pól w oknie) i obserwujemy go dość długo, by to wiedzieć."""
        return not g.get("kier") and g.get("obs_s", 0.0) >= self._k("MIJANIE_OBOZ_S", 3.0)

    def _mij_obserwuj(self, gracze, t):
        """Pamięć mijania: kiedy widzieliśmy gracza, którędy szedł; decyzja o kierunku wobec gracza trwa, dopóki
        nie zniknie z widoku na MIJANIE_ZNIKL_S (kolejne spotkanie = ocena od nowa, Z6); obozowicza oceniamy
        ponownie po MIJANIE_OBOZ_PAMIEC_S (stoi dalej, a pętla znów do niego dochodzi)."""
        if not self._mij_wlaczone():
            if self.mij_widz or self.mij_dec or self.mij_prz is not None or self.mij_skrot is not None or self.mij_wroc is not None \
                    or self.mij_pauza is not None:
                self.mij_widz, self.mij_dec, self.mij_odwroty, self.mij_slad, self.mij_brak = {}, {}, {}, {}, {}
                self.mij_pauza, self.mij_pauza_ost, self.mij_za, self.mij_tory = None, {}, {}, {}
                self.mij_prz, self.mij_skrot, self.mij_prz_ost, self.mij_wroc = None, None, {}, None
                self.mij_zmiana_ost = float("-inf")
            return
        zn = self._k("MIJANIE_ZNIKL_S", 6.0)
        pam = self._k("MIJANIE_OBOZ_PAMIEC_S", 60.0)
        for g in gracze:
            k = self._mij_klucz(g)
            self.mij_widz[k] = t
            sl = self.mij_slad.setdefault(k, deque())
            sl.append((t, g["x"], g["y"]))
            while sl and t - sl[0][0] > MIJ_SLAD_S:
                sl.popleft()
        for k in list(self.mij_dec):
            d = self.mij_dec[k]
            if t - self.mij_widz.get(k, float("-inf")) > zn or (d["rodzaj"] == "oboz" and t - d["t"] > pam):
                del self.mij_dec[k]
        for k in [k for k, v in self.mij_widz.items() if t - v > max(120.0, 4 * zn)]:
            for sl in (self.mij_widz, self.mij_slad, self.mij_odwroty, self.mij_prz_ost, self.mij_brak, self.mij_za):
                sl.pop(k, None)
        for k in [k for k, v in self.mij_pauza_ost.items() if t - v > max(300.0, 2 * self._k("MIJANIE_PAUZA_PONOW_S", MIJ_PAUZA_PONOW_S))]:
            del self.mij_pauza_ost[k]

    def _mij_log(self, rodzaj, tekst, t):
        """Wpis do logu najwyżej raz na MIJ_LOG_S s dla danego rodzaju (bez spamu w każdym obiegu)."""
        if t - self.mij_log_ost.get(rodzaj, float("-inf")) >= MIJ_LOG_S:
            if len(self.mij_log_ost) > 100:
                self.mij_log_ost = {k: v for k, v in self.mij_log_ost.items() if t - v < MIJ_LOG_S}
            self.mij_log_ost[rodzaj] = t
            self.log(tekst)

    def mijanie_trzyma(self):
        """True, gdy mijanie trzyma kierunek obiegu: trwa decyzja wobec któregoś gracza (mij_dec) albo jakiś gracz był w widoku
        w ostatnich MIJANIE_ZNIKL_S. Cavebot nie odwraca wtedy losowo trasy na końcu okrążenia (Q3: nie wracamy w stronę gracza)."""
        if not self._mij_wlaczone():
            return False
        if self.mij_dec:
            return True
        zn = self._k("MIJANIE_ZNIKL_S", 6.0)
        t = self.zegar()
        return any(t - v <= zn for v in self.mij_widz.values())

    def mijanie(self, poz, punkty, idx, droga_fn, wolne_fn=None, otwarta=False, w_walce=False):
        """-> Mij albo None (cavebot idzie normalnie). Wołane w obiegu marszu po trasie, gdy MIJANIE=1.
        droga_fn(start(x,y,z), cel(x,y), blok(zbiór)) -> pola (bez startu) albo None; wolne_fn((x,y,z)) -> bool (pole
        do przejścia, ściany/ogień/schody = False); otwarta = trasa nie jest pętlą (bez zawijania indeksów);
        w_walce = mamy cel albo moby nas biją (Z3: walka ma pierwszeństwo, zmiany kierunku i przejścia czekają)."""
        if not self._mij_wlaczone() or not punkty:
            return None
        t = self.zegar()
        z = poz[2]
        poz3 = (poz[0], poz[1], z)
        n = len(punkty)
        idx %= n
        if self.mij_prz is not None:
            r = self._mij_przejscie_krok(poz3, t, droga_fn, w_walce)
            if r is not None or self.mij_prz is not None:
                return r
            # ustępowanie skończyło się w tym obiegu: od razu wychodzimy z wnęki (bez zachłannego kroku cavebota w jej głąb)
        if w_walce:
            self.mij_wroc = None
            self.mij_pauza = None                      # walka ma pierwszeństwo: przepuszczanie kończy się bez wpisu
            return None
        if self.mij_pauza is not None:
            r = self._mij_pauza_krok(poz3, t)
            if r is not None:
                return r
        if self.mij_wroc is not None:
            w = self.mij_wroc
            d = None if t > w["do"] or poz3[:2] == w["cel"] else droga_fn(poz3, w["cel"], set())
            if d:
                return Mij("marsz", krok=tuple(d[0]), powod="powrot")
            self.mij_wroc = None
        r_max = self._k("UNIKANIE_PROMIEN", 9)
        wid = [g for g in self.gracze if g["z"] == z and g["odl"] <= r_max]
        if self.mij_skrot is not None:
            r = self._mij_skrot_krok(poz3, punkty, idx, droga_fn, wid, t, otwarta)
            if r is not None:
                return r
        if not wid:
            return None
        przod = self._k("MIJANIE_PRZOD", 16)
        ok_p = self._mij_okno(punkty, idx, 1, przod + 40, z, otwarta)      # dalej niż przod: skrót za komorą obozowicza
        hor = max(0, int(self._k("MIJANIE_HORYZONT", MIJ_HORYZONT)))
        ok_t = self._mij_okno(punkty, idx, -1, max(przod + MIJ_TANG, hor + 1), z, otwarta)    # odwrócony obieg: do horyzontu toru gracza
        r = self._mij_przejscie_start(poz3, wid, droga_fn, wolne_fn, t, ok_p, ok_t)
        if r is not None:
            return r
        r = self._mij_za_graczem(poz3, wid, wolne_fn, t, ok_p, ok_t)
        if r is not None:
            return r
        return self._mij_kierunek(poz3, droga_fn, wid, [g for g in self.gracze if g["z"] == z], t, ok_p, ok_t, wolne_fn=wolne_fn)

    # -- geometria trasy --

    @staticmethod
    def _mij_okno(punkty, idx, znak, dl, z, otwarta):
        """Kolejne punkty trasy w kierunku `znak` (+1: idx, idx+1, ... przed nami; -1: idx-1, idx-2, ... za nami)
        jako [(indeks, punkt)], do `dl` punktów, urywane na zmianie piętra (i na końcu trasy otwartej)."""
        n = len(punkty)
        wyn = []
        for k in range(dl):
            i = idx + k if znak > 0 else idx - 1 - k
            if otwarta and not 0 <= i < n:
                break
            i %= n
            if punkty[i][2] != z:
                break
            wyn.append((i, punkty[i]))
        return wyn

    @staticmethod
    def _mij_na_trasie(okno, P, r):
        """Numer (od 0) pierwszego punktu okna w promieniu r od pola P albo None."""
        for k, (_, q) in enumerate(okno):
            if _cheb(q[:2], P) <= r:
                return k
        return None

    @staticmethod
    def _mij_tangens(okno, k):
        """Kierunek trasy w k-tym punkcie okna (do punktu MIJ_TANG dalej; na końcu okna: od punktu wcześniejszego)."""
        a = okno[k][1]
        j = k + MIJ_TANG
        if j < len(okno):
            b = okno[j][1]
            v = (b[0] - a[0], b[1] - a[1])
        else:
            c = okno[max(k - MIJ_TANG, 0)][1]
            v = (a[0] - c[0], a[1] - c[1])
        return v if v != (0, 0) else None

    @staticmethod
    def _mij_czas_widoku(pts, P):
        """Ile kroków po tych polach, zanim znikniemy z widoku gracza w P (poza dx +-7, dy +-5); 40 = nie znikamy."""
        for i, c in enumerate(pts[:40]):
            if abs(c[0] - P[0]) > MIJ_WIDOK[0] or abs(c[1] - P[1]) > MIJ_WIDOK[1]:
                return i + 1
        return 40

    def _mij_ku_graczowi(self, poz3, pts, g):
        """Jak `_za_graczem`, ale na liście pól i bez UNIKANIE_TOR: kierunek pierwszych UNIKANIE_TOR_LOOK pól v, ruch gracza h,
        v*h > 0 i v*r > 0 (r = wektor do gracza) = idziemy tam, dokąd on idzie, w jego stronę (Z1)."""
        h = g.get("kier")
        if not pts or not h:
            return False
        rx, ry = g["x"] - poz3[0], g["y"] - poz3[1]
        if max(abs(rx), abs(ry)) > self._k("UNIKANIE_TOR_ZASIEG", 12):
            return False
        k = pts[min(len(pts), self._k("UNIKANIE_TOR_LOOK", 8)) - 1]
        vx, vy = k[0] - poz3[0], k[1] - poz3[1]
        return (vx or vy) and vx * h[0] + vy * h[1] > 0 and vx * rx + vy * ry > 0

    def _mij_ocena(self, poz3, pts, g, wid, sprawdz_g=True, pts_dl=None):
        """Ocena kierunku (lista pól `pts` przed nami): None = odrzucony (wchodzi w obozowicza, idzie za innym graczem albo zbiega się
        z torem idącego gracza na `pts_dl`, 22.10), inaczej liczba kroków do zniknięcia z widoku gracza g (mniej = lepiej) z karą
        za jego ślad (Z2: jego ślad na końcu). `pts_dl` = ten sam kierunek na dłuższym horyzoncie (domyślnie `pts`)."""
        oboz_r = self._k("MIJANIE_OBOZ_R", 3)
        dl = pts if pts_dl is None else pts_dl
        for g2 in wid:
            if g2 is g and not sprawdz_g:
                if g2.get("kier") and self._mij_zbiega(dl, g2):
                    return None                        # 22.10: odwrócony obieg znów schodzi się z torem tego samego gracza (równoległe ramiona pętli)
                continue
            if g2 is g and not self._mij_stoi(g2):
                if g2.get("kier") and self._mij_zbiega(dl, g2):
                    return None
                continue                               # gracz, który nas wywołał, idzie przed nami: kierunek od niego z definicji
            if self._mij_stoi(g2):
                if any(_cheb(c, (g2["x"], g2["y"])) <= oboz_r for c in pts[:12]):
                    return None
            elif self._mij_ku_graczowi(poz3, pts, g2):
                return None
            elif g2.get("kier") and self._mij_zbiega(dl, g2):
                return None
        czas = self._mij_czas_widoku(pts, (g["x"], g["y"]))
        slad = self.mij_slad.get(self._mij_klucz(g), ())
        trafien = sum(1 for c in pts[:10] if any(_cheb(c, (sx, sy)) <= 1 for _, sx, sy in slad))
        return czas + 2 * trafien

    def _mij_blok_obozu(self, wid, poz3):
        """Pola zakazane dla skrótu: strefa 2 pól wokół każdego stojącego gracza (bańki dystansu nie ma, ale komory obozowicza nie mijamy tuż obok)."""
        blok = set()
        for g in wid:
            if self._mij_stoi(g):
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        blok.add((g["x"] + dx, g["y"] + dy, g["z"]))
        blok.discard(poz3)
        return blok

    # -- zmiana kierunku obiegu (Z1, Z2, Q1, Q3) --

    def _mij_kierunek(self, poz3, droga_fn, wid, wszyscy, t, ok_p, ok_t, wolne_fn=None):
        """Ocena graczy z `wid` (w UNIKANIE_PROMIEN); `wszyscy` (do UNIKANIE_PROMIEN_MAX, to samo piętro) wchodzą tylko do oceny
        kierunku: nie odwracamy obiegu w stronę innego gracza, który odchodzi w tę stronę (Z1), nawet gdy jest dalej niż 9 pól."""
        if t - self.mij_zmiana_ost < MIJ_ZMIANA_MIN_S:
            return None
        hor = max(0, int(self._k("MIJANIE_HORYZONT", MIJ_HORYZONT)))
        self.mij_tory = {self._mij_klucz(g): self._mij_tor(g, ok_p, ok_t, hor) for g in wszyscy if g.get("kier")} if hor else {}
        przod = self._k("MIJANIE_PRZOD", 16)
        r_trasa = self._k("MIJANIE_TRASA_R", 2)
        oboz_r = self._k("MIJANIE_OBOZ_R", 3)
        for g in wid:
            klucz = self._mij_klucz(g)
            if klucz in self.mij_dec or t - self.mij_brak.get(klucz, float("-inf")) < MIJ_BRAK_S:
                continue                               # decyzja trzymana do zniknięcia gracza (Q3)
            P = (g["x"], g["y"])
            if g.get("kier"):
                h = g["kier"]
                kp = self._mij_na_trasie(ok_p[:przod + 1], P, r_trasa)
                if kp is None:
                    continue                           # nie leży na naszej drodze: przechodzi / idzie inną stroną
                kt = self._mij_na_trasie(ok_t[:przod + 1], P, r_trasa)
                if kt is not None and kt < kp:
                    continue                           # jest za nami: nie wchodzimy mu na plecy, ale i nie zawracamy do niego
                tang = self._mij_tangens(ok_p, kp)
                if tang is None or tang[0] * h[0] + tang[1] * h[1] <= 0:
                    continue                           # naprzeciw albo w poprzek: mijamy się, bez zawracania (Z5)
                rodzaj = "ta_strona"
            elif self._mij_stoi(g):
                kp = self._mij_na_trasie(ok_p[:przod + 1], P, oboz_r)
                if kp is None:
                    continue
                kt = self._mij_na_trasie(ok_t[:przod + 1], P, oboz_r)
                if kt is not None and kt < kp:
                    continue
                rodzaj = "oboz"
            else:
                continue                               # jeszcze nie wiemy, czy idzie, czy stoi
            r = self._mij_wybierz(poz3, droga_fn, wszyscy, g, rodzaj, kp, ok_p, ok_t, t, wolne_fn=wolne_fn)
            if r is not None:
                return r
        return None

    def _mij_skrot_plan(self, poz3, droga_fn, wid, g, kp, ok_p):
        """Skrót do pierwszego punktu pętli za komorą obozowicza g (Q1): {"idx", "cel", "droga", "pts"} albo None, gdy drogi
        poza strefą obozowiczów nie ma, jest dłuższa niż MIJANIE_SKROT_MAX albo pętla za komorą znów do niego wraca."""
        oboz_r = self._k("MIJANIE_OBOZ_R", 3)
        P = (g["x"], g["y"])
        j = kp
        while j < len(ok_p) and _cheb(ok_p[j][1][:2], P) <= oboz_r:
            j += 1
        while j + 4 <= len(ok_p) and any(_cheb(ok_p[i][1][:2], P) <= oboz_r for i in range(j, j + 4)):
            j += 1
        if j + 12 > len(ok_p):
            return None
        if any(_cheb(ok_p[i][1][:2], P) <= oboz_r for i in range(j, j + 12)):
            return None
        cel = ok_p[j][1][:2]
        droga = droga_fn(poz3, cel, self._mij_blok_obozu(wid, poz3))
        if not droga or len(droga) > self._k("MIJANIE_SKROT_MAX", 40):
            return None
        pts = [tuple(p[:2]) for p in droga] + [ok_p[i][1][:2] for i in range(j, min(len(ok_p), j + 20))]
        hor = max(0, int(self._k("MIJANIE_HORYZONT", MIJ_HORYZONT)))
        pts_dl = [tuple(p[:2]) for p in droga] + [ok_p[i][1][:2] for i in range(j, min(len(ok_p), j + max(20, hor)))]
        return {"idx": ok_p[j][0], "cel": tuple(cel), "droga": [tuple(p) for p in droga], "pts": pts, "pts_dl": pts_dl}

    def _mij_wybierz(self, poz3, droga_fn, wid, g, rodzaj, kp, ok_p, ok_t, t, wolne_fn=None):
        """Wybór między skrótem (tylko obozowicz) a odwróceniem obiegu wg oceny Z1/Z2; zapamiętuje decyzję."""
        klucz = self._mij_klucz(g)
        oboz = rodzaj == "oboz"
        if oboz:
            ost = [x for x in self.mij_odwroty.get(klucz, []) if t - x < 120.0]
            self.mij_odwroty[klucz] = ost
            if len(ost) >= self._k("MIJANIE_OBOZ_ODWROTY", 2):
                # obie strony już próbowaliśmy, a obozowicz dalej zagradza pętlę: przechodzimy obok niego (Q1)
                self.mij_dec[klucz] = {"t": t, "rodzaj": rodzaj}
                self._mij_log(f"przejdz_{klucz}", f"Mijanie: gracz {g['nazwa']} stoi na pętli, obie strony już próbowałem - "
                              f"przechodzę obok niego.", t)
                return None
        poluje = oboz and self._mij_poluje(g)          # 22.10: stoi, ale ma moba tuż przy sobie = poluje, zaraz ruszy za nim
        hor = max(0, int(self._k("MIJANIE_HORYZONT", MIJ_HORYZONT)))
        pts_b = [q[:2] for _, q in ok_t[:30]]
        pts_bd = [q[:2] for _, q in ok_t[:max(30, hor)]]
        cz_b = self._mij_ocena(poz3, pts_b, g, wid, sprawdz_g=oboz, pts_dl=pts_bd) if pts_b else None   # obozowicz: druga strona pętli nie może wchodzić w jego komorę
        plan_a = self._mij_skrot_plan(poz3, droga_fn, wid, g, kp, ok_p) if oboz and not poluje else None   # polujący: bez skrótu obok niego
        cz_a = self._mij_ocena(poz3, plan_a["pts"], g, wid, sprawdz_g=False, pts_dl=plan_a["pts_dl"]) if plan_a else None
        if plan_a is not None and cz_a is not None and (cz_b is None or cz_a <= cz_b + 6):
            wybor = "skrot"
        elif cz_b is not None:
            wybor = "odwroc"
        else:
            self.mij_brak[klucz] = t
            if (rodzaj == "ta_strona" or poluje) and self._k("MIJANIE_PAUZA_BRAK", MIJ_PAUZA_BRAK):
                # 22.10: nie idziemy dalej obok gracza (wygląda jak bot): krótka ludzka pauza z boku, on idzie przodem
                r = self._mij_pauza_start(poz3, g, "brak", wolne_fn, t, ok_p, ok_t)
                if r is not None:
                    return r
            self._mij_log(f"brak_{klucz}", f"Mijanie: gracz {g['nazwa']} ({rodzaj}), ale żadnego bezpiecznego kierunku "
                          f"nie ma - idę dalej po trasie.", t)
            return None
        if oboz and wybor == "odwroc" and g["odl"] <= self._k("MIJANIE_OBOZ_BLISKO", 3):
            # 19.10 (Mastafian + Raczek): gracz bez kierunku tuż przy nas zwykle walczy obok (te same moby), to nie obozowicz;
            # odwrócony obieg poprowadził bota tam, dokąd gracz zaraz ruszył. Bez odwracania: idziemy dalej, ocena po MIJ_BRAK_S.
            self.mij_brak[klucz] = t
            self._mij_log(f"blisko_{klucz}", f"Mijanie: gracz {g['nazwa']} stoi tuż obok ({g['odl']} pól, kier None), raczej walczy - "
                          f"nie odwracam obiegu, idę dalej po trasie.", t)
            return None
        self.mij_dec[klucz] = {"t": t, "rodzaj": rodzaj}
        self.mij_zmiana_ost = t
        self.mij_zmian += 1
        opis = {"ta_strona": "idzie tą samą stroną przed nami", "oboz": "stoi na pętli"}[rodzaj]
        if wybor == "odwroc":
            if oboz:
                self.mij_odwroty.setdefault(klucz, []).append(t)
            self.mij_skrot = None
            self.log(f"Mijanie: gracz {g['nazwa']} {opis} ({g['odl']} pól, kier {g.get('kier')}), odwracam kierunek obiegu "
                     f"i trzymam go.")
            self.zdarzenie("mijanie_kierunek", akcja="odwrocenie", powod=rodzaj, gracz=g["nazwa"], gracz_id=g.get("id"),
                           odl=g["odl"], kier=list(g["kier"]) if g.get("kier") else None, czas_widoku=cz_b,
                           alternatywa=cz_a)
            return Mij("odwroc", powod=rodzaj)
        self.mij_skrot = {"cel": plan_a["cel"], "klucz": klucz, "do": t + 60.0, "droga": plan_a["droga"]}
        self.log(f"Mijanie: gracz {g['nazwa']} {opis} ({g['odl']} pól), omijam jego komorę skrótem do punktu {plan_a['idx']} "
                 f"({len(plan_a['droga'])} pól).")
        self.zdarzenie("mijanie_kierunek", akcja="skrot", powod=rodzaj, gracz=g["nazwa"], gracz_id=g.get("id"), odl=g["odl"],
                       kier=None, czas_widoku=cz_a, alternatywa=cz_b, punkt=plan_a["idx"], droga=len(plan_a["droga"]))
        return Mij("marsz", idx=plan_a["idx"], krok=plan_a["droga"][0], powod="skrot")

    def _mij_skrot_krok(self, poz3, punkty, idx, droga_fn, wid, t, otwarta):
        """Kolejny krok trwającego skrótu (po zakończeniu walki marsz trwa dalej, aż do celu, najwyżej 60 s)."""
        s = self.mij_skrot
        if t > s["do"] or poz3[:2] == s["cel"]:
            self.mij_skrot = None
            return None
        n = len(punkty)
        k = None
        for off in range(0, 80):
            i = idx + off
            if otwarta and i >= n:
                break
            q = punkty[i % n]
            if q[:2] == s["cel"] and q[2] == poz3[2]:
                k = i % n
                break
        if k is None:
            self.mij_skrot = None
            return None
        blok = self._mij_blok_obozu(wid, poz3)
        droga = s.get("droga") or []
        if poz3 in droga:
            rest = droga[droga.index(poz3) + 1:]
        elif droga and _cheb(poz3, droga[0]) <= 1:
            rest = list(droga)
        else:
            rest = None
        if not rest or any(c in blok for c in rest):
            rest = droga_fn(poz3, s["cel"], blok)
            rest = [tuple(p) for p in rest] if rest else None
        if not rest:
            self.mij_skrot = None
            self._mij_log("skrot_brak", "Mijanie: skrót przestał być osiągalny, wracam do zwykłej trasy.", t)
            return None
        s["droga"] = rest
        return Mij("marsz", idx=k, krok=rest[0], powod="skrot")

    # -- tor gracza, polujący, przepuszczenie (22.10) --

    @staticmethod
    def _mij_gesto(pts, n):
        """Lista pól `pts` (punkty trasy bywają co kilka pól) zagęszczona do kroków po 1 pole (prosto/skosem między kolejnymi), do `n` pól:
        czas zbiegu liczymy w krokach, nie w punktach."""
        if not pts:
            return []
        wyn = [tuple(pts[0][:2])]
        for b in pts[1:]:
            b = tuple(b[:2])
            c = wyn[-1]
            while c != b and len(wyn) < n:
                c = (c[0] + (b[0] > c[0]) - (b[0] < c[0]), c[1] + (b[1] > c[1]) - (b[1] < c[1]))
                wyn.append(c)
            if len(wyn) >= n:
                break
        return wyn[:n]

    def _mij_tor(self, g, ok_p, ok_t, hor):
        """Możliwe tory idącego gracza (lista list pól, każdy `hor` pól). Leży na naszej trasie (MIJANIE_TRASA_R) i jego ruch zgadza się
        z kierunkiem trasy = dalsze punkty trasy w tamtą stronę; gdy zgadza się z obiema (skrzyżowanie, zakręt, ruch ukośny) - oba
        warianty (nie wiemy, w którą stronę skręci: 22.10 Harley Queen szedł na południe, a potem w głąb odwróconego obiegu).
        Poza trasą: prosta w kierunku jego ruchu."""
        h = g.get("kier")
        if not h or hor <= 0:
            return []
        P = (g["x"], g["y"])
        r_trasa = self._k("MIJANIE_TRASA_R", 2)
        tory = []
        for okno in (ok_p, ok_t):
            k = self._mij_na_trasie(okno, P, r_trasa)
            if k is None:
                continue
            tang = self._mij_tangens(okno, k)
            if tang is not None and tang[0] * h[0] + tang[1] * h[1] > 0:
                tor = self._mij_gesto([P] + [q[:2] for _, q in okno[k + 1:k + 1 + hor]], hor + 1)[1:]
                if len(tor) >= 6:
                    dl_k = math.hypot(h[0], h[1]) * math.hypot(tang[0], tang[1]) or 1.0
                    tory.append(((tang[0] * h[0] + tang[1] * h[1]) / dl_k, tor))
        if tory:
            # tylko warianty zgodne z jego ruchem tak dobrze jak najlepszy (ruch ukośny wobec obu ramion = oba)
            najl = max(c for c, _ in tory)
            return [t for c, t in tory if c >= najl - 0.25]
        dl = math.hypot(h[0], h[1])
        ux, uy = h[0] / dl, h[1] / dl
        return [[(P[0] + round(ux * i), P[1] + round(uy * i)) for i in range(1, hor + 1)]]

    def _mij_zbiega(self, pts, g):
        """True, gdy kandydat `pts` (pola przed nami, do MIJANIE_HORYZONT) schodzi się z torem gracza g: w podobnym czasie jest od
        niego nie dalej niż MIJANIE_ZBIEG_D pól i idzie w tę samą stronę (zderzenie czołowe to zwykłe mijanie, nie zbieg)."""
        tory = self.mij_tory.get(self._mij_klucz(g))
        hor = int(self._k("MIJANIE_HORYZONT", MIJ_HORYZONT))
        if not tory or not pts or hor <= 0:
            return False
        pts = self._mij_gesto(pts, hor)
        d = self._k("MIJANIE_ZBIEG_D", MIJ_ZBIEG_D)
        dt = self._k("MIJANIE_ZBIEG_DT", MIJ_ZBIEG_DT)
        for tor in tory:
            for i, c in enumerate(pts):
                b = pts[min(i + MIJ_TANG, len(pts) - 1)]
                vc = (b[0] - c[0], b[1] - c[1]) if b != c else (c[0] - pts[max(i - MIJ_TANG, 0)][0], c[1] - pts[max(i - MIJ_TANG, 0)][1])
                tol = dt + i // 3
                for j in range(max(0, i - tol), min(len(tor), i + tol + 1)):
                    if _cheb(c, tor[j]) > d:
                        continue
                    a = tor[min(j + MIJ_TANG, len(tor) - 1)]
                    vt = (a[0] - tor[j][0], a[1] - tor[j][1])
                    if vt == (0, 0):
                        e = tor[max(j - MIJ_TANG, 0)]
                        vt = (tor[j][0] - e[0], tor[j][1] - e[1])
                    if vc[0] * vt[0] + vc[1] * vt[1] > 0:
                        return True
        return False

    def _mij_poluje(self, g):
        """Stojący gracz z mobem w MIJANIE_POLUJACY_R polach od siebie: poluje (zaraz ruszy za mobem), nie obozuje."""
        r = self._k("MIJANIE_POLUJACY_R", MIJ_POLUJACY_R)
        if r <= 0 or g.get("kier"):
            return False
        return any(_cheb(m, (g["x"], g["y"])) <= r for m in self.moby)

    def _mij_bok_pauzy(self, poz3, g, ok_p, ok_t, wolne_fn):
        """Wolne pole obok nas poza trasą (12 punktów w obie strony), nie przy graczu: tam stajemy, gdy go przepuszczamy; None = stoimy w miejscu."""
        if wolne_fn is None:
            return None
        trasa = {q[:2] for _, q in ok_p[:12]} | {q[:2] for _, q in ok_t[:12]}
        z = poz3[2]
        inni = [(x["x"], x["y"]) for x in self.gracze if x["z"] == z]
        kand = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (poz3[0] + dx, poz3[1] + dy)
            if q in trasa or any(_cheb(q, c) < 2 for c in inni) or not wolne_fn((q[0], q[1], z)):
                continue
            kand.append(q)
        return random.choice(kand) if kand else None

    def _mij_pauza_start(self, poz3, g, powod, wolne_fn, t, ok_p, ok_t):
        """Przepuszczenie gracza g: losowa pauza MIJANIE_PAUZA_MIN_S..MAX_S, jeśli jest wolne pole poza trasą - z boku. Najwyżej raz na
        MIJANIE_PAUZA_PONOW_S na tego samego gracza (potem None: idziemy normalnie, bez pętli wahadła)."""
        klucz = self._mij_klucz(g)
        if t - self.mij_pauza_ost.get(klucz, float("-inf")) < self._k("MIJANIE_PAUZA_PONOW_S", MIJ_PAUZA_PONOW_S):
            return None
        lo = self._k("MIJANIE_PAUZA_MIN_S", MIJ_PAUZA_MIN_S)
        hi = max(lo, self._k("MIJANIE_PAUZA_MAX_S", MIJ_PAUZA_MAX_S))
        dl = random.uniform(lo, hi)
        cel = self._mij_bok_pauzy(poz3, g, ok_p, ok_t, wolne_fn)
        self.mij_pauza_ost[klucz] = t
        self.mij_pauza = {"klucz": klucz, "nazwa": g["nazwa"], "gracz_id": g.get("id"), "od": t, "do": t + dl,
                          "cel": cel, "start": poz3[:2], "powod": powod, "kroki": 0}
        self.log(f"Mijanie: gracz {g['nazwa']} ({g['odl']} pól, kier {g.get('kier')}, {powod}) - przepuszczam go: "
                 f"{'schodzę na ' + str(cel) + ' i ' if cel else ''}stoję {dl:.1f} s.")
        self.zdarzenie("mijanie_pauza", etap="start", powod=powod, gracz=g["nazwa"], gracz_id=g.get("id"), odl=g["odl"],
                       kier=list(g["kier"]) if g.get("kier") else None, pole=list(cel) if cel else None, czas_s=round(dl, 1))
        return self._mij_pauza_krok(poz3, t)

    def _mij_pauza_krok(self, poz3, t):
        """Trwające przepuszczenie: krok na pole z boku (jeśli jest), potem stoimy do końca pauzy albo do zniknięcia gracza."""
        p = self.mij_pauza
        if not any(self._mij_klucz(x) == p["klucz"] and x["z"] == poz3[2] for x in self.gracze):
            return self._mij_pauza_koniec(poz3, t, "zniknal")
        if t >= p["do"]:
            return self._mij_pauza_koniec(poz3, t, "czas")
        cel = p["cel"]
        if cel is not None and poz3[:2] != cel:
            if _cheb(poz3[:2], cel) == 1 and p["kroki"] < 3:
                p["kroki"] += 1
                return Mij("marsz", krok=(cel[0], cel[1], poz3[2]), powod="pauza")
            p["cel"] = None                            # zepchnięci z drogi / krok się nie udał: stoimy tam, gdzie jesteśmy
        return Mij("stoj", powod="pauza")

    def _mij_pauza_koniec(self, poz3, t, powod):
        p = self.mij_pauza
        self.mij_pauza = None
        if p["start"] != poz3[:2]:
            self.mij_wroc = {"cel": p["start"], "do": t + 8.0}       # wracamy na oś trasy
        self.log(f"Mijanie: koniec przepuszczania gracza {p['nazwa']} po {t - p['od']:.1f} s ({powod}).")
        self.zdarzenie("mijanie_pauza", etap="koniec", powod=powod, gracz=p["nazwa"], gracz_id=p.get("gracz_id"),
                       czas_s=round(t - p["od"], 1))
        return None

    def _mij_za_graczem(self, poz3, wid, wolne_fn, t, ok_p, ok_t):
        """Gracz idzie za nami (<= MIJANIE_ZA_ODL pól, w tę samą stronę) dłużej niż MIJANIE_ZA_S: przepuszczamy go (pauza z boku)."""
        zs = self._k("MIJANIE_ZA_S", MIJ_ZA_S)
        if zs <= 0 or not ok_p:
            return None
        tang = self._mij_tangens(ok_p, 0)
        if tang is None:
            return None
        odl_max = self._k("MIJANIE_ZA_ODL", MIJ_ZA_ODL)
        for g in wid:
            h = g.get("kier")
            if not h or g.get("duch"):
                continue
            klucz = self._mij_klucz(g)
            rx, ry = g["x"] - poz3[0], g["y"] - poz3[1]
            if not (1 <= g["odl"] <= odl_max and h[0] * tang[0] + h[1] * tang[1] > 0 and rx * tang[0] + ry * tang[1] < 0):
                continue                               # nie za nami albo nie w tę samą stronę
            rec = self.mij_za.setdefault(klucz, {"od": t, "ost": t})
            if t - rec["ost"] > 3.0:
                rec["od"] = t                          # przerwa w obserwacji: liczymy od nowa
            rec["ost"] = t
            if t - rec["od"] >= zs:
                rec["od"] = t
                r = self._mij_pauza_start(poz3, g, "za_nami", wolne_fn, t, ok_p, ok_t)
                if r is not None:
                    return r
        return None

    # -- udostępnianie przejścia (Z4, Q2) --

    def _mij_przejscie_start(self, poz3, wid, droga_fn, wolne_fn, t, ok_p, ok_t):
        """Gracz idzie na nas, nie ma jak się minąć (wąskie miejsce na odcinku między nami) i go widzimy: krok na pole poza
        osią jego ruchu (wnęka, bok korytarza), tam stoimy, aż przejdzie. Inaczej None (mijamy się normalnie)."""
        if wolne_fn is None:
            return None
        z = poz3[2]
        odl_max = self._k("MIJANIE_PRZEJSCIE_ODL", 6)
        ponow = self._k("MIJANIE_PONOW_S", 20.0)
        for g in wid:
            h = g.get("kier")
            klucz = self._mij_klucz(g)
            if not h or g.get("duch") or not 1 <= g["odl"] <= odl_max:
                continue
            if t - self.mij_prz_ost.get(klucz, float("-inf")) < ponow:
                continue
            rx, ry = poz3[0] - g["x"], poz3[1] - g["y"]
            if h[0] * rx + h[1] * ry <= 0:
                continue                               # (a) nie idzie w naszą stronę
            if abs(h[0] * ry - h[1] * rx) / math.hypot(h[0], h[1]) > 1.5:
                continue                               # idzie obok nas, nie na nas
            P = (g["x"], g["y"], z)
            sc = droga_fn(P, poz3[:2], set())
            if not sc:
                continue
            os_ = [P[:2]] + [tuple(p[:2]) for p in sc]
            m = len(os_) // 2
            if self._mij_jest_przejscie(os_, m, z, wolne_fn):
                continue                               # (b) minie się bez nas
            # oś jego ruchu: odcinek do nas i dalej za nami (trasa w stronę jego ruchu, a poza trasą prosta w kierunku h)
            uc = (1 if h[0] > 0 else -1, 0) if abs(h[0]) >= abs(h[1]) else (0, 1 if h[1] > 0 else -1)
            os_set = set(os_) | {(poz3[0] + uc[0] * i, poz3[1] + uc[1] * i) for i in range(1, 7)}
            for okno in (ok_p, ok_t):
                if len(okno) > 3 and (okno[3][1][0] - poz3[0]) * h[0] + (okno[3][1][1] - poz3[1]) * h[1] > 0:
                    os_set |= {q[:2] for _, q in okno[:12]}
            bok = self._mij_wneka(poz3, P, os_set, wolne_fn)
            if bok is None:
                self._mij_log(f"wneka_{klucz}", f"Mijanie: gracz {g['nazwa']} idzie na nas w wąskim miejscu, ale wnęki w "
                              f"zasięgu {self._k('MIJANIE_BOK_R', 6)} pól nie ma - idę dalej.", t)
                continue
            cel, droga = bok
            self.mij_prz = {"klucz": klucz, "nazwa": g["nazwa"], "gracz_id": g.get("id"), "cel": cel, "od": t, "h": h,
                            "stoi": False, "stoi_od": None, "bez_ruchu": None, "droga": droga, "start": poz3[:2]}
            self.mij_przejsc += 1
            self.log(f"Mijanie: gracz {g['nazwa']} idzie na nas ({g['odl']} pól), korytarz za wąski - schodzę mu z drogi "
                     f"na {cel} ({len(droga)} kroków) i stoję, aż przejdzie.")
            self.zdarzenie("mijanie_przejscie", etap="start", gracz=g["nazwa"], gracz_id=g.get("id"), odl=g["odl"],
                           kier=list(h), pole=list(cel), kroki=len(droga))
            return Mij("marsz", krok=droga[0], powod="przejscie")
        return None

    @staticmethod
    def _mij_jest_przejscie(os_, m, z, wolne_fn):
        """True, gdy na odcinku między graczem a nami (okolice miejsca spotkania m i nasze pole) da się minąć: wolne pole obok
        trasy (korytarz szerszy niż 1) w każdym z tych punktów."""
        L = len(os_)
        for i in {max(m - 1, 0), m, min(m + 1, L - 1), L - 1}:
            a, b = os_[max(i - 1, 0)], os_[min(i + 1, L - 1)]
            d = (b[0] - a[0], b[1] - a[1])
            bok = ((0, 1), (0, -1)) if abs(d[0]) >= abs(d[1]) else ((1, 0), (-1, 0))
            if not any(wolne_fn((os_[i][0] + s[0], os_[i][1] + s[1], z)) for s in bok):
                return False
        return True

    def _mij_wneka(self, poz3, P, os_set, wolne_fn):
        """Najbliższe pole poza osią jego ruchu (BFS po wolnych polach do MIJANIE_BOK_R kroków, nie tuż przy graczu), do którego
        dojdziemy, zanim on tam dojdzie: (pole, droga) albo None."""
        z = poz3[2]
        r_max = self._k("MIJANIE_BOK_R", 6)
        start = poz3[:2]
        skad = {start: None}
        gl = {start: 0}
        kol = deque([start])
        najl = None
        while kol:
            c = kol.popleft()
            if gl[c] >= r_max:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = (c[0] + dx, c[1] + dy)
                if q in skad or _cheb(q, P) <= 1 or not wolne_fn((q[0], q[1], z)):
                    continue
                skad[q] = c
                gl[q] = gl[c] + 1
                if q not in os_set and gl[q] + 1 < _cheb(q, P):
                    if najl is None or (gl[q], -_cheb(q, P)) < (gl[najl], -_cheb(najl, P)):
                        najl = q
                kol.append(q)
        if najl is None:
            return None
        droga = []
        c = najl
        while c != start:
            droga.append((c[0], c[1], z))
            c = skad[c]
        return najl, droga[::-1]

    def _mij_koniec_przejscia(self, t, powod):
        p = self.mij_prz
        self.mij_prz = None
        self.mij_prz_ost[p["klucz"]] = t
        if powod != "walka":
            self.mij_wroc = {"cel": p["start"], "do": t + 8.0}       # wychodzimy z wnęki z powrotem na oś korytarza
        self.log(f"Mijanie: koniec udostępniania przejścia graczowi {p['nazwa']} po {t - p['od']:.0f} s ({powod}).")
        self.zdarzenie("mijanie_przejscie", etap="koniec", powod=powod, gracz=p["nazwa"], gracz_id=p.get("gracz_id"),
                       czas_s=round(t - p["od"], 1), stal_s=round(t - p["stoi_od"], 1) if p["stoi_od"] is not None else 0.0)
        return None

    def _mij_przejscie_krok(self, poz3, t, droga_fn, w_walce):
        """Trwające udostępnianie przejścia: idziemy do wnęki, stoimy, kończymy gdy gracz przeszedł / zniknął / stanął / walka
        / bezpiecznik MIJANIE_POSTOJ_S."""
        p = self.mij_prz
        g = next((x for x in self.gracze if self._mij_klucz(x) == p["klucz"] and x["z"] == poz3[2]), None)
        if w_walce:
            return self._mij_koniec_przejscia(t, "walka")
        if g is None:
            return self._mij_koniec_przejscia(t, "zniknal")           # (c) stoimy tylko, gdy go widzimy
        if t - p["od"] > self._k("MIJANIE_POSTOJ_S", 15.0):
            return self._mij_koniec_przejscia(t, "bezpiecznik")
        h0 = p["h"]
        if (g["x"] - poz3[0]) * h0[0] + (g["y"] - poz3[1]) * h0[1] > 0:
            return self._mij_koniec_przejscia(t, "przeszedl")
        h = g.get("kier")
        if h is None:
            p["bez_ruchu"] = p["bez_ruchu"] if p["bez_ruchu"] is not None else t
            if t - p["bez_ruchu"] >= 3.0:
                return self._mij_koniec_przejscia(t, "stanal")
        else:
            p["bez_ruchu"] = None
            if h[0] * (poz3[0] - g["x"]) + h[1] * (poz3[1] - g["y"]) < 0:
                return self._mij_koniec_przejscia(t, "odchodzi")
        if poz3[:2] == p["cel"]:
            if not p["stoi"]:
                p["stoi"], p["stoi_od"] = True, t
                self.zdarzenie("mijanie_przejscie", etap="stoi", gracz=p["nazwa"], gracz_id=p.get("gracz_id"),
                               pole=list(p["cel"]), odl=g["odl"])
            return Mij("stoj", powod="przejscie")
        droga = p["droga"]
        if poz3 in droga:
            rest = droga[droga.index(poz3) + 1:]
        elif droga and _cheb(poz3, droga[0]) <= 1:
            rest = list(droga)
        else:
            rest = None
        if not rest:
            d = droga_fn(poz3, p["cel"], set())
            rest = [tuple(q) for q in d] if d else None
        if not rest:
            return self._mij_koniec_przejscia(t, "brak_drogi")
        p["droga"] = rest
        return Mij("marsz", krok=rest[0], powod="przejscie")
