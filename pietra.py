"""Trasa wielopiętrowa w głównej pętli łowiska (13.10): przejścia pięter (schody, dziura, drabina, lina)
wynikające z trasy, wykonywane przez Cavebot._idz_trasa, gdy KOLEJNY punkt trasy leży na innym piętrze.

Zasady (te same, które wypad.py zweryfikował na żywo w do_miasta/z_miasta):
  w dół  (b.z > a.z): DZIURA/SCHODY. Pole zmiany piętra T leży na piętrze a, ma flagę mapy "bez drogi" (2),
                      a lądowanie to (T.x, T.y, z+1). Wchodzimy na T strzałką ("krok"), awaryjnie Ctrl+klik (Use).
  w górę (b.z < a.z): DRABINA / LINA / SCHODY W GÓRĘ. Pole R na piętrze a, nad którym (piętro wyżej) jest dziura
                      (flaga 2); lądowanie (R.x, R.y+1, z-1). Próby: Ctrl+klik na R (drabina), krok na R
                      (schody), Ctrl+klik z liną z plecaka, pole własne i sąsiednie (wypad._proby_drabiny).
Po każdej próbie czytamy pozycję (postac.pozycja() = rdzen.pozycja) i sprawdzamy zmianę piętra.
Pościg NIGDY nie wchodzi tu: moduł jest wołany tylko z idz() (brak celu), a zakaz zmiany piętra w A*/pościgu
(Cavebot._zakaz_pol) zostaje bez zmian.

Przy porażce przejścia: log + telemetria + powiadomienie, trasa zawraca (inna strona okrążenia); po
PIETRA_PORAZKI_STOP porażkach z rzędu bot przerywa (jak przy "Trzy punkty z rzędu nieosiągalne").
"""
import time

import bot

try:
    import wypad
except Exception:       # wypad nigdy nie wywraca bota
    wypad = None


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _flaga(mapa, x, y, z):
    try:
        return int(mapa.flagi(x, y, z)) if mapa is not None and z >= 0 else 0
    except Exception:
        return 0


def kandydaci(mapa, a, b):
    """Pola, którymi da się przejść z `a` (stoimy tu, piętro a[2]) na punkt `b` (inne piętro).
    Lista słowników {"pole": (x, y, z) na piętrze a, "pewne": bool, "lad": (x, y, z) lądowanie}, najlepsze pierwsze.
    Brak mapy = tylko założenie z wypad.py (dziura pod b / lina na (b.x, b.y-1))."""
    z = a[2]
    wyn, widziane = [], set()

    def dodaj(x, y, pewne, lad):
        if (x, y) in widziane:
            return
        widziane.add((x, y))
        wyn.append({"pole": (x, y, z), "pewne": pewne, "lad": lad})

    if b[2] > z:                                    # w dół: pole z flagą 2 na piętrze a, lądowanie pod nim
        for dx in (0, -1, 1):
            for dy in (0, -1, 1):
                x, y = b[0] + dx, b[1] + dy
                f = _flaga(mapa, x, y, z)
                if f & 1 and f & 2 and not f & 4 and cheb((x, y), a) <= 3:
                    dodaj(x, y, True, (x, y, z + 1))
        wyn.sort(key=lambda k: ((k["pole"][0], k["pole"][1]) != (b[0], b[1]), cheb(k["pole"], a)))
        if (b[0], b[1]) not in widziane:
            dodaj(b[0], b[1], False, (b[0], b[1], z + 1))      # założenie wypad.py: dziura leży pod punktem b
    else:                                           # w górę: R z dziurą nad sobą, lądowanie (R.x, R.y+1, z-1)
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                x, y = a[0] + dx, a[1] + dy
                f = _flaga(mapa, x, y, z)
                if f & 4 or not f & 1:
                    continue
                gora = _flaga(mapa, x, y, z - 1)
                if gora & 1 and gora & 2 and cheb((x, y + 1), (b[0], b[1])) <= 1:
                    dodaj(x, y, True, (x, y + 1, z - 1))
        wyn.sort(key=lambda k: (cheb(k["pole"], a), cheb(k["lad"], b)))
        if (b[0], b[1] - 1) not in widziane:
            dodaj(b[0], b[1] - 1, False, (b[0], b[1], z - 1))   # konwencja wypad.py: R = (b.x, b.y-1) na piętrze a
    return wyn[:3]


TRYBY_DOL = {True: ("krok", "krok", "use", "krok", "use", "use_wlasne"),
             False: ("use", "krok", "use_wlasne", "krok", "use", "use_wlasne")}
TRYBY_GORA = ("R", "krok", "R", "lina", "wlasne", "E", "W", "N")


class Pietra:
    """Maszyna przejść pięter dla Cavebot (cb). Jedno przejście naraz; tick() zużywa obieg albo oddaje None."""

    def __init__(self, cb, konf=None, log=print):
        self.cb = cb
        self.konf = konf
        self.log = log
        self.st = None                  # stan bieżącego przejścia
        self.resync = []                # czasy ostatnich resynchronizacji (pętla zabezpieczająca)
        self.ostrzezenia = set()

    # --- konfiguracja (stałe modułu cavebot) ---

    def _k(self, nazwa, domyslna):
        return getattr(self.konf, nazwa, domyslna) if self.konf is not None else domyslna

    @property
    def ops(self):
        cb = self.cb
        o = getattr(cb, "pietra_ops", None)
        if o is None:
            w = getattr(cb, "wyprawa", None)
            o = getattr(w, "ops", None)
        if o is None and wypad is not None:
            o = wypad.OperacjeZywe(log=self.log)
        cb.pietra_ops = o
        return o

    def _tele(self, typ, **d):
        t = getattr(self.cb, "tele", None)
        if t is not None:
            try:
                t.zdarzenie(typ, **d)
            except Exception:
                pass

    def _powiadom(self, tytul, tresc, pilnosc="normal"):
        try:
            import powiadom  # noqa: PLC0415
            powiadom.powiadom(tytul, tresc, pilnosc, "pietra")
        except Exception:
            pass

    # --- główny punkt wejścia ---

    def tick(self, poz, cel):
        """poz = (x,y,z) gracza, cel = punkt trasy (inne piętro niż gracz). True = obieg zużyty, False = przerwij
        bota (kolejne porażki), None = nie umiem, idź starą ścieżką."""
        cb = self.cb
        stop = getattr(cb, "_trasa_stop_potwor", None)
        if stop is not None and stop(tuple(poz)):
            return True                         # potwór tuż obok: żadnej próby przejścia ani dojścia, walka pierwsza
        teraz = cb.zegar()
        n = len(cb.punkty)
        z = poz[2]
        a = cb.punkty[(cb.idx - 1) % n]
        st = self.st
        if st is not None and (st["cel"] != tuple(cel) or st["z0"] != z):
            st = None                           # inny cel albo piętro zmienione poza nami: liczymy od nowa
        if st is None:
            if a[2] != z:
                return self._resync(poz, cel, teraz)
            st = self.st = {"cel": tuple(cel), "a": tuple(a), "z0": z, "od": teraz, "kand": None, "ki": 0,
                            "proby": 0, "nast": teraz, "postep": [teraz, 999], "tryby": None}
            st["kand"] = kandydaci(cb.mapa, a, cel)
            self.log(f"Przejście pięter: z{z} -> z{cel[2]} (punkt trasy {cb.idx}), kandydaci: "
                     f"{[(k['pole'][:2], 'pewny' if k['pewne'] else 'domysł') for k in st['kand']]}")
            self._tele("pietra_start", z_od=z, z_do=cel[2], idx=cb.idx, poz=list(poz),
                       kandydaci=[list(k["pole"][:2]) for k in st["kand"]])
        if teraz - st["od"] > self._k("PIETRA_MAX_S", 150.0):
            return self._porazka(f"limit czasu {self._k('PIETRA_MAX_S', 150.0):.0f} s", poz)
        if st["ki"] >= len(st["kand"]):
            return self._porazka("wyczerpane pola przejścia", poz)
        k = st["kand"][st["ki"]]
        T = k["pole"]
        if cheb(poz, T) > 1:
            return self._dojdz(poz, T, st, teraz)
        if teraz < st["nast"]:
            cb.pauza(0.2, 0.5)
            return True
        return self._proba(poz, st, k, teraz)

    # --- dojście do pola przejścia ---

    def _dojdz(self, poz, T, st, teraz):
        cb = self.cb
        d = cheb(poz, T)
        p = st["postep"]
        if d < p[1]:
            st["postep"] = [teraz, d]
        elif teraz - p[0] > self._k("PIETRA_DOJSCIE_S", 25.0):
            self.log(f"Przejście pięter: nie zbliżam się do pola {T[:2]} (odl {d}), zmieniam kandydata")
            st["ki"] += 1
            st["proby"] = 0
            st["tryby"] = None
            st["postep"] = [teraz, 999]
            return True
        # ucieczka/walka już przejęły obieg wcześniej (tick); tu zwykłe podejście po drodze z mapy
        r = cb.podejdz((T[0], T[1]), poz, objazd=False)
        if r is None or r is False:
            cb.nieudane += 1
            cb.pauza(0.2, 0.5)
        return True

    # --- próby przejścia ---

    def _tryby(self, k, st):
        if k["lad"][2] > st["z0"]:
            return list(TRYBY_DOL[bool(k["pewne"])])
        return list(TRYBY_GORA)

    def _proba(self, poz, st, k, teraz):
        cb = self.cb
        if st["tryby"] is None:
            st["tryby"] = self._tryby(k, st)
            st["proby"] = 0
        tryby = st["tryby"]
        n = st["proby"]
        if n >= len(tryby):
            st["ki"] += 1
            st["tryby"] = None
            st["proby"] = 0
            st["postep"] = [teraz, 999]
            self.log(f"Przejście pięter: pole {k['pole'][:2]} bez skutku po {n} próbach")
            return True
        tryb = tryby[n]
        T = k["pole"]
        st["proby"] = n + 1
        na_polu = (poz[0], poz[1]) == (T[0], T[1])
        # postać jeszcze idzie po starym kliku: Escape + chwila spokoju
        try:
            cb.zatrzymaj_klik(poz)
        except bot.Zatrzymano:
            raise
        except Exception:
            pass
        cb.klik_cel = None
        z0 = poz[2]
        opis = f"{tryb}"
        try:
            if tryb == "krok":
                if na_polu:
                    tryb, opis = "use_wlasne", "krok->use_wlasne"
                    self._use(T, poz, poz)
                else:
                    dx, dy = T[0] - poz[0], T[1] - poz[1]
                    if dx and dy:
                        # strzałki nie chodzą po skosie: najpierw krok w poziomie albo w pionie (to nie jest próba),
                        # potem pole jest obok. Oba zablokowane = zwykła nieudana próba (bez pętli bez końca).
                        for kier, (kx, ky) in (("Right" if dx > 0 else "Left", (poz[0] + (1 if dx > 0 else -1), poz[1])),
                                               ("Down" if dy > 0 else "Up", (poz[0], poz[1] + (1 if dy > 0 else -1)))):
                            if _flaga(cb.mapa, kx, ky, z0) & 4:
                                continue                    # ściana na mapie: nie walimy w nią strzałką
                            self.log(f"Przejście pięter: krok {kier} z {tuple(poz)} (pole {T[:2]} po skosie)")
                            try:
                                cb.postac.krok(kier)
                            except bot.Zatrzymano:
                                raise
                            except Exception:
                                pass
                            cb.pauza(0.15, 0.3)
                            if tuple(cb.postac.pozycja()) != tuple(poz):
                                st["proby"] = n
                                return True
                        if getattr(cb, "klik", None) is not None:       # po skosie tylko klik klienta (marsz 1 pola)
                            self.log(f"Przejście pięter: klik na pole {T[:2]} po skosie z {tuple(poz)}")
                            try:
                                cb.klik(dx, dy)
                            except bot.Zatrzymano:
                                raise
                            except Exception:
                                pass
                            cb.spij(0.5)
                            if tuple(cb.postac.pozycja()) != tuple(poz):
                                st["proby"] = n
                                return self._po_przejsciu(z0, st, poz, teraz, k, "klik po skosie") or True
                        tryb, opis = "krok_skos", "krok po skosie bez skutku"
                        if self._po_przejsciu(z0, st, poz, teraz, k, opis):
                            return True
                        st["nast"] = cb.zegar() + self._odstep(n)
                        return True
                    kier = ("Right" if dx > 0 else "Left") if dx else ("Down" if dy > 0 else "Up")
                    self.log(f"Przejście pięter: próba {n + 1}/{len(tryby)} (krok {kier}) z {tuple(poz)}, pole {T[:2]}")
                    cb.postac.krok(kier)
            elif tryb in ("use", "R"):
                self.log(f"Przejście pięter: próba {n + 1}/{len(tryby)} ({tryb}, Ctrl+klik) z {tuple(poz)}, pole {T[:2]}")
                self._use(T, poz, poz)
            elif tryb in ("use_wlasne", "wlasne"):
                self.log(f"Przejście pięter: próba {n + 1}/{len(tryby)} ({tryb}) z {tuple(poz)}")
                self._use((poz[0], poz[1], poz[2]), poz, poz)
            elif tryb in ("E", "W", "N"):
                dx, dy = {"E": (1, 0), "W": (-1, 0), "N": (0, -1)}[tryb]
                q = (poz[0] + dx, poz[1] + dy, poz[2])
                if (q[0], q[1]) == (T[0], T[1]):
                    return True                 # to samo pole co R (już próbowane)
                self.log(f"Przejście pięter: próba {n + 1}/{len(tryby)} ({tryb}) z {tuple(poz)}, pole {q[:2]}")
                self._use(q, poz, poz)
            elif tryb == "lina":
                self.log(f"Przejście pięter: próba {n + 1}/{len(tryby)} (lina z plecaka) z {tuple(poz)}, pole {T[:2]}")
                self.ops.uzyj_line(T, poz)
            else:
                return True
        except bot.Zatrzymano:
            raise
        except Exception as ex:
            self._tele("pietra_blad", rodzaj=type(ex).__name__, opis=str(ex)[:120], tryb=tryb, poz=list(poz))
            self.log(f"Przejście pięter: próba {tryb} nie wyszła ({ex!r})")
            st["nast"] = teraz + self._odstep(n)
            return True
        if self._po_przejsciu(z0, st, poz, teraz, k, opis):
            return True
        st["nast"] = cb.zegar() + self._odstep(n)
        return True

    def _use(self, pole, poz, _):
        self.ops.uzyj_pole(pole, poz)

    @staticmethod
    def _odstep(n):
        odst = (1.0, 2.0, 4.0, 6.0)
        return odst[min(n, len(odst) - 1)]

    def _po_przejsciu(self, z0, st, poz_przed, teraz, k, opis):
        """Po próbie: do ~2 s sprawdzamy pozycję (z rdzenia). Zmiana piętra = sukces."""
        cb = self.cb
        for _ in range(5):
            cb.spij(0.4)
            p = cb.postac.pozycja()
            if p[2] != z0:
                n = st["proby"]
                cel = st["cel"]
                oczekiwane = p[2] == cel[2]
                self.log(f"Przejście pięter: z{z0} -> z{p[2]} w {tuple(p)} (próba {n}, {opis}"
                         f"{'' if oczekiwane else ', NIEOCZEKIWANE piętro'})")
                self._tele("pietra_krok", z_od=z0, z_do=p[2], poz=list(p), idx=cb.idx, proba=n, tryb=opis,
                           oczekiwane=oczekiwane, czas_s=round(teraz - st["od"], 1))
                self._sukces(p)
                return True
        return False

    def _sukces(self, p):
        cb = self.cb
        self.st = None
        cb.pietra_porazki = 0
        cb._wypad_reset_klik()          # klik, droga, utknięcie: nowe piętro = nowy odczyt
        cb.stwory_pola.clear()          # (x, y) bez z: stare wpisy z innego piętra by mylily naukę ścian
        cb.krok_prosto_ost = None
        cb.krok_z = None
        cb.pominiete = 0
        cb.pauza(0.15, 0.35)

    # --- resynchronizacja (gracz na piętrze, które nie jest ani przed, ani po przejściu) ---

    def _resync(self, poz, cel, teraz):
        cb = self.cb
        self.resync = [t for t in self.resync if teraz - t < 120.0]
        self.resync.append(teraz)
        if len(self.resync) > self._k("PIETRA_RESYNC_MAX", 6):
            self.resync.clear()
            return self._porazka("pętla resynchronizacji (piętro poza trasą)", poz)
        poprzedni = cb.punkty[(cb.idx - 1) % len(cb.punkty)]
        self.log(f"Przejście pięter: stoję na z{poz[2]}, a punkt przed {cb.idx} jest na z{poprzedni[2]} "
                 f"(cel z{cel[2]}), szukam punktu trasy na tym piętrze")
        n = len(cb.punkty)
        for k in range(1, min(8, n)):             # wpadliśmy w dziurę leżącą na trasie: kolejny punkt na tym piętrze
            if cb.punkty[(cb.idx + k) % n][2] == poz[2]:
                cb.idx = (cb.idx + k) % n
                self.log(f"Przejście pięter: jestem na z{poz[2]}, przechodzę do punktu trasy {cb.idx}")
                cb._wypad_reset_klik()
                self.resync.clear()
                return True
        if any(p[2] == poz[2] for p in cb.punkty):
            if cb._wroc_na_trase(tuple(poz)):
                return True
        self.st = {"cel": tuple(cel), "a": None, "z0": poz[2], "od": teraz, "kand": [], "ki": 0,
                   "proby": 0, "nast": teraz, "postep": [teraz, 999], "tryby": None}
        cb.pauza(0.5, 1.0)
        return True

    # --- porażka ---

    def _porazka(self, powod, poz):
        cb = self.cb
        cb.pietra_porazki = getattr(cb, "pietra_porazki", 0) + 1
        lim = int(self._k("PIETRA_PORAZKI_STOP", 3))
        self.log(f"Przejście pięter NIEUDANE ({powod}), z {tuple(poz)} do punktu {cb.idx}; "
                 f"porażka {cb.pietra_porazki}/{lim}")
        self._tele("pietra_blad", rodzaj="porazka", opis=powod, poz=list(poz), idx=cb.idx, n=cb.pietra_porazki)
        self._powiadom("Bot: przejście pięter nie wychodzi", f"{powod}; {tuple(poz)}, punkt trasy {cb.idx}",
                       "critical" if cb.pietra_porazki >= lim else "normal")
        self.st = None
        cb._wypad_reset_klik()
        if cb.pietra_porazki >= lim:
            self.log(f"Przejście pięter nieudane {lim} razy z rzędu, przerywam.")
            return False
        cb._pietra_zawroc(tuple(poz))
        return True
