"""D3, krok A (SPEC_model_D3_utkniecia_1015): detektor zawieszki + log decyzji. BEZ zmiany zachowania bota.

Zawieszka = pozycja w promieniu 2 pól od kotwicy przez >= D3_PROG_S sekund, poza walką (czas walki < 30% okna),
exp bez zmian. Liczone z tego, co cavebot ma w każdym obiegu (pozycja, stan, exp); zero RPC.
Na starcie zawieszki: rekord telemetrii `decyzja` rodzaj "D3" (opcje z sekcji 2 specyfikacji + cechy), wybrana = None
(reguła bota jeszcze nie wybrała; to, co zrobiła, trafia do `d3_wynik.regula`). Na końcu: rekord `d3_wynik`.
Telemetria nigdy nie wywraca bota. Koszt: A* najwyżej D3_ASTAR_MAX razy na zawieszkę (stan A* bota zostaje nietknięty).
"""
import collections

PROMIEN = 2                 # pola (Czebyszew): ruch w tym promieniu od kotwicy to nadal "stoimy"
UDZIAL_WALKI = 0.30         # >= tyle czasu okna w walce = to nie zawieszka (sekcja 1 specyfikacji)
OKNO_RUCHU_S = 20.0         # "ruszyliśmy w ciągu 20 s" (etykieta modelu D3)
MAX_PRZERWA_OBIEGU_S = 30.0  # luka między obiegami dłuższa niż to = bot nie był obserwowany (zawieszony proces): nowa kotwica
# stany walki i pokrewne (czas w nich nie liczy się jako stanie w miejscu)
STANY_WALKI = ("WALKA", "WALKA_PVP", "LOOT", "POGON", "UCIECZKA", "UH", "ZDROWIE")
STANY_ZAMIERZONE = ("PRZERWA", "PAUZA", "PAUZA_PK", "GRACZ")   # bot stoi z własnej woli: rekord jest, z flagą
KIERUNKI_8 = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))
OPCJE = ("krok_skos", "cofnij", "inny_punkt", "przejscie_pietra", "czekaj", "alarm")


def _pasuje(stan, stany):
    """Stan bota pasuje do listy także po prefiksie (bot używa PAUZA_x, GRACZ_x, WALKA_x)."""
    s = str(stan or "")
    return any(s == x or s.startswith(x + "_") for x in stany)


def _czeb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _znak(v):
    return (v > 0) - (v < 0)


class Zawieszka:
    def __init__(self, cb, konf):
        self.cb, self.konf = cb, konf
        self.kotwica = None                              # {"poz","t0","exp0","boj"}
        self.ost_t = None
        self.ost_walka = False
        self.hist = collections.deque(maxlen=12)         # ostatnie RÓŻNE pozycje (do opcji "cofnij")
        self.akt = None                                  # trwająca zawieszka
        self.dawne = []                                  # (poz, t) startów zawieszek w tej sesji (licznik prób)
        self.regula = []                                 # co zrobiła obecna reguła w trakcie zawieszki
        self.astar_licznik = 0                           # wywołania A* w bieżącym liczeniu opcji (test kosztu)

    # --- API dla cavebota ---
    def nota_reguly(self, nazwa):
        """Cavebot zgłasza akcję istniejącej reguły wyjścia z utknięcia (tylko zapis, bez wpływu na ruch)."""
        if self.akt is not None and nazwa not in self.regula:
            self.regula.append(nazwa)

    def tick(self, g, poz, teraz):
        """Wołane raz na obieg, na początku. Błąd nie wychodzi poza ten moduł."""
        cb, k = self.cb, self.konf
        poz3 = tuple(poz[:3])
        exp = g.get("exp") if isinstance(g, dict) else None
        prog = float(getattr(k, "D3_PROG_S", 30.0))
        dt = 0.0 if self.ost_t is None else max(0.0, teraz - self.ost_t)
        walka_dt, self.ost_t = self.ost_walka, teraz
        stan = str(cb.stan)
        self.ost_walka = self._walka(stan)
        if not self.hist or self.hist[-1] != poz3:
            self.hist.append(poz3)
        a = self.kotwica
        if dt > MAX_PRZERWA_OBIEGU_S or a is None or a["poz"][2] != poz3[2] or _czeb(a["poz"], poz3) > PROMIEN:
            if self.akt is not None:
                self._koniec(poz3, teraz, exp, "pietro" if a and a["poz"][2] != poz3[2] else
                             ("luka" if dt > MAX_PRZERWA_OBIEGU_S else "ruch"),
                             ruszyl=not (dt > MAX_PRZERWA_OBIEGU_S))
            self.kotwica = {"poz": poz3, "t0": teraz, "exp0": exp, "boj": 0.0}
            return
        if exp is not None and a["exp0"] is not None and exp > a["exp0"]:
            if self.akt is not None:
                self._koniec(poz3, teraz, exp, "exp", ruszyl=False)
            self.kotwica = {"poz": poz3, "t0": teraz, "exp0": exp, "boj": 0.0}
            return
        if exp is not None and a["exp0"] is None:
            a["exp0"] = exp
        if walka_dt:
            a["boj"] += dt
        trwa = teraz - a["t0"]
        if trwa < prog:
            return
        udzial = a["boj"] / trwa if trwa > 0 else 0.0
        if self.akt is not None:
            if udzial >= UDZIAL_WALKI:
                self._koniec(poz3, teraz, exp, "walka", ruszyl=False)
                self.kotwica = {"poz": poz3, "t0": teraz, "exp0": exp, "boj": 0.0}
            return
        if udzial >= UDZIAL_WALKI:
            self.kotwica = {"poz": poz3, "t0": teraz, "exp0": exp, "boj": 0.0}   # okno z walką: liczymy od nowa
            return
        self._start(g, poz3, teraz, exp, trwa, stan)

    def zamknij(self, teraz=None):
        """Koniec pracy bota w trakcie zawieszki: zapisz wynik (koniec = "stop")."""
        if self.akt is None:
            return
        try:
            t = self.cb.zegar() if teraz is None else teraz
            self._koniec(self.akt["poz"], t, None, "stop", ruszyl=False)
        except Exception:
            self.akt = None

    # --- wewnętrzne ---
    def _walka(self, stan):
        cb = self.cb
        return _pasuje(stan, STANY_WALKI) or getattr(cb, "pk_stan", None) in ("WALKA", "UCIECZKA") \
            or bool(getattr(cb, "ucieczka", False))

    def _start(self, g, poz3, teraz, exp, trwa, stan):
        cb = self.cb
        self.regula = []
        try:
            opcje, cechy = self._opcje(g, poz3, trwa, stan)
            did = self._zapisz(poz3, opcje, cechy)
        except Exception as e:        # błąd liczenia opcji = brak rekordu, bot idzie dalej
            self._log(f"debug: D3 błąd {e!r}")
            did = None
        self.akt = {"id": did, "t": teraz, "poz": poz3, "exp0": exp, "t0": self.kotwica["t0"]}
        self.dawne.append((poz3, teraz))
        del self.dawne[:-50]
        self._log(f"debug: D3 zawieszka {trwa:.0f} s w {poz3} (stan {stan}, rekord {did})")

    def _koniec(self, poz3, teraz, exp, jak, ruszyl):
        akt, self.akt = self.akt, None
        if akt is None or akt["id"] is None:
            return
        cb = self.cb
        czas = round(max(0.0, teraz - akt["t"]), 1)
        zm = None
        if exp is not None and akt["exp0"] is not None:
            zm = exp - akt["exp0"]
        try:
            cb.tele.zdarzenie("d3_wynik", decyzja_id=akt["id"], ruszyl=bool(ruszyl), czas_s=czas,
                              ruszyl_20s=bool(ruszyl and czas <= OKNO_RUCHU_S), exp_zmiana=zm, koniec=jak,
                              stoi_s=round(max(0.0, teraz - akt["t0"]), 1), poz_start=list(akt["poz"]),
                              poz_koniec=list(poz3[:3]), regula=list(self.regula))
        except Exception as e:
            self._log(f"debug: D3 wynik błąd {e!r}")

    def _zapisz(self, poz3, opcje, cechy):
        """Rekord `decyzja` jak D1/D2 (to samo id z wspólnego licznika); niezależny od DECYZJE_LOG, zależny od D3_LOG."""
        cb = self.cb
        if not cb.tele:
            return None
        cb._decyzja_nr = getattr(cb, "_decyzja_nr", 0) + 1
        cb.tele.zdarzenie("decyzja", id=cb._decyzja_nr, rodzaj="D3", poz=list(poz3), opcje=opcje, wybrana=None, **cechy)
        return cb._decyzja_nr

    def _log(self, txt):
        try:
            self.konf.log(txt)
        except Exception:
            pass

    # --- cechy ---
    def _astar(self, poz3, q):
        """Długość drogi A* (bez schodów/dziur/ognia, jak droga bota) albo None. Budżet D3_ASTAR_MAX na zawieszkę.
        Zwraca (długość|None, policzona). Stan statystyk A* bota (blokujący, licznik bez blokad) zostaje nietknięty."""
        cb = self.cb
        if self.astar_licznik >= int(getattr(self.konf, "D3_ASTAR_MAX", 6)) or q[2] != poz3[2]:
            return None, False
        self.astar_licznik += 1
        zapas = (getattr(cb, "ostatni_blokujacy", None), getattr(cb, "droga_bez_blokad", 0))
        try:
            d = [] if tuple(poz3[:2]) == tuple(q[:2]) else cb.droga(tuple(poz3), tuple(q[:2]), dlugosc=0)
            return (None if d is None else len(d)), True
        except Exception:
            return None, True
        finally:
            cb.ostatni_blokujacy, cb.droga_bez_blokad = zapas

    def _kod_pola(self, pole, stwory):
        """. wolne · # ściana · o ogień · d nauczona dziura · s schody/dziura z mapy · m mob · g gracz · ? nieznane."""
        cb = self.cb
        try:
            if cb.dziura_nauczona(pole):
                return "d"
            if cb._ogien_na(pole):
                return "o"
            m = cb.mapa
            if m is not None and m.schody_lub_dziura(*pole):
                return "s"
            for s in stwory:
                if (s.get("x"), s.get("y"), s.get("z")) == tuple(pole) and s.get("hp", 100) > 0:
                    return "g" if s.get("gracz") else "m"
            if cb.sciana(pole) or (m is not None and m.przechodnie(*pole) is False):
                return "#"
            if m is not None and m.przechodnie(*pole) is None and tuple(pole) not in cb.znane:
                return "?"
        except Exception:
            return "?"
        return "."

    def _cel(self, poz3):
        """Bieżący cel marszu (x, y, z) i jego źródło, z gotowego stanu bota; (None, None), gdy nieznany."""
        cb = self.cb
        p = getattr(cb, "patrol", None)
        if isinstance(p, dict) and p.get("m"):
            m = p["m"]
            return (m["x"], m["y"], m["z"]), "patrol"
        try:
            q = cb.punkty[cb.idx]
            return (q[0], q[1], q[2]), "trasa"
        except Exception:
            return None, None

    def _opcje(self, g, poz3, trwa, stan):
        cb = self.cb
        self.astar_licznik = 0
        stwory = list(getattr(cb, "ostatnie_stwory", None) or [])
        ja = getattr(cb.postac, "nazwa", None)
        inni = [s for s in stwory if s.get("z") == poz3[2] and not (s.get("gracz") and s.get("nazwa") == ja)
                and s.get("hp", 100) > 0]
        gracze = sorted(_czeb(poz3, (s["x"], s["y"])) for s in inni if s.get("gracz"))
        moby = sorted(_czeb(poz3, (s["x"], s["y"])) for s in inni if not s.get("gracz"))
        wokol = {}
        for dx, dy in KIERUNKI_8:
            wokol["%+d%+d" % (dx, dy)] = self._kod_pola((poz3[0] + dx, poz3[1] + dy, poz3[2]), stwory)
        proc = g.get("proc") if isinstance(g, dict) else None
        hp_ok = proc is None or proc > getattr(cb, "prog_aktualny", 0)
        cel, zrodlo = self._cel(poz3)
        cel_droga = cel_policz = None
        if cel is not None:
            cel_droga, cel_policz = self._astar(poz3, cel)
        kier = (_znak(cel[0] - poz3[0]), _znak(cel[1] - poz3[1])) if cel is not None else None
        tu = sum(1 for p, _ in self.dawne if p[2] == poz3[2] and _czeb(p, poz3) <= 3)
        opcje = [self._o_skos(poz3, kier, wokol, hp_ok), self._o_cofnij(poz3, hp_ok),
                 self._o_punkt(poz3, hp_ok), self._o_pietro(poz3, hp_ok),
                 {"akcja": "czekaj", "mozliwa": True, "dopuszczalna": hp_ok,
                  "gracz_blisko": bool(gracze and gracze[0] <= 2), "mob_blisko": bool(moby and moby[0] <= 2),
                  "s_bez_ruchu": round(trwa, 1)},
                 {"akcja": "alarm", "mozliwa": True, "dopuszczalna": True, "s_bez_ruchu": round(trwa, 1),
                  "poprzednie_tu": tu}]
        cechy = {"stan": stan, "zamierzony": _pasuje(stan, STANY_ZAMIERZONE), "stoi_s": round(trwa, 1),
                 "cel": list(cel) if cel else None, "cel_zrodlo": zrodlo, "kier_cel": list(kier) if kier else None,
                 "odl_cel": _czeb(poz3, cel) if cel and cel[2] == poz3[2] else None,
                 "cel_droga": cel_droga, "cel_droga_policzona": bool(cel_policz),
                 "wokol": wokol, "wolne_wokol": sum(1 for v in wokol.values() if v == "."),
                 "gracze_odl": gracze[:3], "moby_odl": moby[:5], "hp_gracza": proc, "hp_ok": hp_ok,
                 "astar_wywolan": self.astar_licznik, "poprzednie_tu": tu}
        return opcje, cechy

    def _o_skos(self, poz3, kier, wokol, hp_ok):
        o = {"akcja": "krok_skos", "mozliwa": False, "dopuszczalna": False}
        if kier is None:
            o["powod"] = "brak_celu"
            return o
        if kier[0] and kier[1]:
            kand = [kier]
        else:    # cel w osi: dwa skosy po bokach kierunku
            kand = [(kier[0] or s, kier[1] or s) for s in (-1, 1)]
        for v in kand:
            kod = wokol.get("%+d%+d" % v, "?")
            if kod == ".":
                o.update(mozliwa=True, dopuszczalna=hp_ok, kierunek=list(v), pole=kod)
                return o
        o.update(kierunek=list(kand[0]), pole=wokol.get("%+d%+d" % kand[0], "?"), powod="pole_zajete")
        return o

    def _o_cofnij(self, poz3, hp_ok):
        o = {"akcja": "cofnij", "mozliwa": False, "dopuszczalna": False}
        wstecz = [p for p in list(self.hist)[:-1] if p[2] == poz3[2]][-3:]
        if not wstecz:
            o["powod"] = "brak_historii"
            return o
        kod = self._kod_pola(wstecz[-1], list(getattr(self.cb, "ostatnie_stwory", None) or []))
        ok = kod == "."
        o.update(mozliwa=ok, dopuszczalna=ok and hp_ok, kroki=len(wstecz), pole=kod,
                 cel_poz=list(wstecz[0]), odl=_czeb(poz3, wstecz[0]))
        return o

    def _o_punkt(self, poz3, hp_ok):
        """Najbliższe punkty trasy tego piętra (poza naszym polem) z długością A*; budżet A* wspólny z resztą."""
        cb = self.cb
        o = {"akcja": "inny_punkt", "mozliwa": False, "dopuszczalna": False, "osiagalnych": 0, "sprawdzono": 0}
        try:
            pts = [(i, q) for i, q in enumerate(cb.punkty) if q[2] == poz3[2] and tuple(q[:2]) != tuple(poz3[:2])]
        except Exception:
            pts = []
        uniq, widz = [], set()
        for i, q in sorted(pts, key=lambda iq: _czeb(poz3, iq[1])):
            if tuple(q[:3]) in widz:
                continue
            widz.add(tuple(q[:3]))
            uniq.append((i, q))
        rezerwa = 1 if getattr(cb, "przejscia", None) else 0          # jedno A* zostaje dla przejścia pięter
        najl = None
        for i, q in uniq:
            if self.astar_licznik >= int(getattr(self.konf, "D3_ASTAR_MAX", 6)) - rezerwa:
                break
            d, ok = self._astar(poz3, q)
            if not ok:
                break
            o["sprawdzono"] += 1
            if d is not None:
                o["osiagalnych"] += 1
                if najl is None or d < najl[0]:
                    najl = (d, i, q)
        if najl:
            o.update(mozliwa=True, dopuszczalna=hp_ok, droga=najl[0], idx=najl[1], punkt=list(najl[2][:3]),
                     odl=_czeb(poz3, najl[2]))
        return o

    def _o_pietro(self, poz3, hp_ok):
        """Najbliższe przejście pięter z grafu patrolu (jeśli wczytany; nie wczytujemy go tu). Pewność: UNKNOWN."""
        cb = self.cb
        o = {"akcja": "przejscie_pietra", "mozliwa": False, "dopuszczalna": False}
        kraw = [e for e in (getattr(cb, "przejscia", None) or []) if e.get("pieta") and e.get("z") == poz3[2]]
        if not kraw:
            o["powod"] = "brak_grafu_przejsc"
            return o
        e = min(kraw, key=lambda e: _czeb(poz3, e["wej"]))
        d, ok = self._astar(poz3, e["wej"])
        o.update(id=e.get("id"), wej=list(e["wej"]), pietro_docelowe=e["wyj"][2], odl=_czeb(poz3, e["wej"]),
                 droga=d, droga_policzona=ok)
        if d is not None:
            o.update(mozliwa=True, dopuszczalna=hp_ok)
        return o
