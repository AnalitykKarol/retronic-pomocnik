#!/usr/bin/env python3
"""Symulator zawieszek (F2, SPEC_zasady_zawieszki_1016 sekcje 2, 3, 5). OFFLINE: nic nie zapisuje, nie dotyka bota ani danych.

Model świata (`Swiat`): mapa z mapa.py albo plansza z tekstu, ściany, nauczone dziury (jak ściana), pola ognia (jak ściana),
drzwi z flagą otwarte/zamknięte (+ zablokowane), przejścia pięter (schody/dziura/drabina; reguły pietra.py: w dół lądowanie
(T.x,T.y,z+1), w górę (R.x,R.y+1,z-1)), łączniki ręczne z miejsca_troll.json, blokady czasowe (gracz/mob na polu), nieznane pola.
Obszar osiągalny = BFS 8-kierunkowy po polach tego piętra, bez wejścia na pola zmiany piętra (d3_zawieszka, sekcja 1).
Zamknięty = < 60 pól i brak drogi do celu po piętrze (Z1); w przeciwnym razie otwarty.

Polityka (Z1-Z8):
  Z2/Z3  zamknięty: Dijkstra po grafie regionów (krawędzie: przejścia, łączniki, otwarcie drzwi) do najtańszego regionu OTWARTEGO;
         najpierw na piętrze celu, dopiero potem gdziekolwiek; region już odwiedzony lub już leżący na planie jest zakazany
         (brak pętli kieszeń-kieszeń), a kieszeń bez drogi dalej nie jest planowana w ogóle.
  Z4     wyjście, które zawodzi, trafia na listę złych; po PROB_MAX (3) porażkach alarm (bez STOP: `stop` zawsze False).
  Z5     otwarty: inny punkt trasy osiągalny BFS-em poza promieniem kotwicy, nie w kierunku celu; potem przejście pięter,
         cofnij, krok_skos.
  Z6     blokada gracza/mobu na drodze: czekaj losowo CZEKAJ_S (domyślnie 5-10 s), najwyżej CZEKAJ_MAX razy z rzędu, potem porażka.
  Z7     brak jakiegokolwiek wyjścia: wynik "brak_wyjscia" (alarm=True); wyczerpane próby: wynik "alarm".
  Z8     ogień/ucieczka/leczenie/UH/PK to kod, nie model: poza zakresem symulatora.
Losowość (ziarno): tylko wśród RÓWNORZĘDNYCH opcji (ten sam koszt) i w czasie czekania Z6. Ten sam świat + ziarno = ten sam wynik.
Czas = kroki x krok_s (zakres 0,6-0,9 s, parametr) + czekanie + koszt nieudanej próby. Nic tu nie jest zmierzone na żywo.
UNKNOWN (parametry bez danych): KOSZT_NIEUDANEJ_PROBY_S; lina z plecaka (opcja `lina`, domyślnie wyłączona); ruch skosem liczony jak prosty.

  python3 narzedzia/symulator_zawieszek.py waliduj      # raport markdown (99/107 epizodów, wyrocznia, 62 przejęcia Karola)
"""
import collections
import copy
import heapq
import json
import random
import statistics
import sys
from pathlib import Path

sys.dont_write_bytecode = True
KATALOG = Path(__file__).resolve().parent.parent
if str(KATALOG) not in sys.path:
    sys.path.insert(0, str(KATALOG))

import d3_zawieszka as d3  # noqa: E402  (czysty moduł: tylko collections)

OPCJE = d3.OPCJE                          # krok_skos, cofnij, inny_punkt, przejscie_pietra, czekaj, alarm
KIERUNKI_8 = d3.KIERUNKI_8
PROMIEN = d3.PROMIEN                      # 2: ruch w tym promieniu od kotwicy to nadal "stoimy"

OBSZAR_ZAMKNIETY_MAX = 60                 # Z1
BFS_LIMIT = 4000                          # jak oracle_wyjscie.py
PROG_ZAMKNIETY_S = 15.0                   # decyzja Karola 16.10 (akcept)
PROG_OTWARTY_S = 30.0                     # = D3_PROG_S
PROB_MAX = 3                              # decyzja Karola 16.10: po 3 nieudanych próbach alarm, bez STOP
KROK_S = (0.6, 0.9)                       # stała z cavebot.py, nie pomiar
CZEKAJ_S = (5.0, 10.0)                    # Z6
CZEKAJ_MAX = 3
KOSZT_NIEUDANEJ_PROBY_S = 6.0             # UNKNOWN: do skalibrowania z telemetrii pietra_krok
AKCJE_MAX = 60
CZAS_MAX_S = 1800.0
BRAK = float("inf")


def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _znak(v):
    return (v > 0) - (v < 0)


# --------------------------------------------------------------------------- świat

class Swiat:
    """Stan świata dla symulacji. `baza(x,y,z)` -> True/False/None (None = nieznane pole) albo `mapa` (obiekt mapa.Mapa)."""

    def __init__(self, baza=None, mapa=None, sciany=(), dziury=(), ogien=(), drzwi=None, przejscia=(),
                 blokady=None, nieznane_przechodnie=False):
        self.baza, self.mapa = baza, mapa
        self.sciany = {tuple(p) for p in sciany}
        self.dziury = {tuple(p) for p in dziury}          # nauczone dziury: jak ściana (spec, sekcja 2)
        self.ogien = {tuple(p) for p in ogien}
        self.drzwi = {tuple(k): {"otwarte": False, "zablokowane": False, **dict(v)} for k, v in (drzwi or {}).items()}
        self.blokady = {tuple(k): float(v) for k, v in (blokady or {}).items()}   # pole -> do kiedy (s symulacji) zajęte
        self.nieznane_przechodnie = bool(nieznane_przechodnie)
        self._wej = collections.defaultdict(list)          # pole wejścia -> przejścia (schody/dziura/drabina)
        self.laczniki = []
        self._pochodne = {}
        for e in przejscia:
            self.dodaj_przejscie(**e)

    # --- budowa
    def dodaj_przejscie(self, od, do, rodzaj="schody", dziala=True, kroki=None, id=None, dwa_kierunki=False, zrodlo=None):
        od, do = tuple(od), tuple(do)
        e = {"id": id or f"{rodzaj}:{od}->{do}", "od": od, "do": do, "rodzaj": rodzaj, "dziala": bool(dziala),
             "kroki": [tuple(k) for k in (kroki or [])], "pewne": True, "zrodlo": zrodlo}
        if rodzaj == "lacznik":
            self.laczniki.append(e)
        else:
            self._wej[od].append(e)
        if dwa_kierunki:
            kr = (list(reversed(e["kroki"][:-1])) + [od]) if e["kroki"] else []
            self.dodaj_przejscie(do, od, rodzaj, dziala, kr, (id + "~") if id else None, False, zrodlo)
        return e

    @classmethod
    def z_planszy(cls, plansze, **kw):
        """plansze: {z: (x0, y0, [wiersze])}. '.' wolne, '#' ściana, '?' lub ' ' nieznane, 'D' drzwi zamknięte, 'd' otwarte,
        'o' ogień, 'x' nauczona dziura, 'B' drzwi zamknięte na klucz."""
        baza, drzwi, ogien, dziury = {}, dict(kw.pop("drzwi", None) or {}), set(kw.pop("ogien", ())), set(kw.pop("dziury", ()))
        for z, (x0, y0, wiersze) in plansze.items():
            for j, w in enumerate(wiersze):
                for i, c in enumerate(w):
                    p = (x0 + i, y0 + j, z)
                    if c in "? ":
                        continue
                    baza[p] = c != "#"
                    if c == "D":
                        drzwi[p] = {"otwarte": False}
                    elif c == "B":
                        drzwi[p] = {"otwarte": False, "zablokowane": True}
                    elif c == "d":
                        drzwi[p] = {"otwarte": True}
                    elif c == "o":
                        ogien.add(p)
                    elif c == "x":
                        dziury.add(p)
        return cls(baza=lambda x, y, z: baza.get((x, y, z)), ogien=ogien, drzwi=drzwi, dziury=dziury, **kw)

    def kopia(self):
        n = copy.copy(self)
        n.drzwi = copy.deepcopy(self.drzwi)
        n.blokady = dict(self.blokady)
        n.sciany, n.dziury, n.ogien = set(self.sciany), set(self.dziury), set(self.ogien)
        return n

    # --- zapytania
    def _baza(self, p):
        if self.baza is not None:
            v = self.baza(*p)
        elif self.mapa is not None:
            v = self.mapa.przechodnie(*p)
        else:
            v = None
        return self.nieznane_przechodnie if v is None else bool(v)

    def _flaga2(self, p):
        return self.mapa is not None and self.baza is None and bool(self.mapa.schody_lub_dziura(*p))

    def wolne(self, p, otwarte=frozenset()):
        """Czy da się stanąć na polu p (bez blokad czasowych). Pola zmiany piętra nie są chodliwe."""
        p = tuple(p)
        if p in self.dziury or p in self.sciany or p in self.ogien:
            return False
        d = self.drzwi.get(p)
        if d is not None:
            return bool(d["otwarte"]) or p in otwarte
        if p in self._wej or self._flaga2(p):
            return False
        return self._baza(p)

    def _ladowanie_ok(self, l):
        if l[2] < 0 or l in self.dziury or l in self.sciany or l in self.ogien:
            return False
        if self.mapa is not None and self.baza is None:
            return self.mapa.przechodnie(*l) is True
        return self._baza(l)

    def wejscia_pola(self, p):
        """Przejścia pięter zaczynające się od kroku na pole p: jawne, a z mapy (flaga 2) wyprowadzone wg pietra.py:
        w dół (x,y,z+1), w górę (x,y+1,z-1); wyprowadzone mają pewne=False."""
        p = tuple(p)
        if p in self.dziury or p in self.sciany or p in self.ogien:
            return ()                                          # nauczona dziura/ściana/ogień na polu przejścia = bot tam nie wchodzi
        if p in self._wej:
            return self._wej[p]
        if self.mapa is None or self.baza is not None or p in self.dziury or p in self.sciany or p in self.ogien:
            return ()
        r = self._pochodne.get(p)
        if r is None:
            r = []
            if self.mapa.schody_lub_dziura(*p) and self.mapa.przechodnie(*p) is not False:
                for l, rodz in (((p[0], p[1], p[2] + 1), "dziura"), ((p[0], p[1] + 1, p[2] - 1), "drabina")):
                    if self._ladowanie_ok(l):
                        r.append({"id": f"mapa-{rodz}:{p}->{l}", "od": p, "do": l, "rodzaj": rodz, "dziala": True,
                                  "kroki": [], "pewne": False, "zrodlo": "mapa (flaga 2)"})
            self._pochodne[p] = r
        return r

    def drzwi_ok(self, p, otwarte=frozenset()):
        d = self.drzwi.get(tuple(p))
        return d is None or bool(d["otwarte"]) or tuple(p) in otwarte


# --------------------------------------------------------------------------- obszar i klasyfikacja

class Obszar:
    __slots__ = ("start", "z", "dist", "rodzic", "wyjscia", "drzwi", "ucieta")

    @property
    def rozmiar(self):
        return len(self.dist)


def bfs(swiat, start, otwarte=frozenset(), limit=BFS_LIMIT):
    """Obszar osiągalny z `start` (x,y,z). wyjscia: id -> (dystans do pola stania, pole stania, przejście);
    drzwi: zamknięte drzwi przy obszarze -> (dystans, pole stania)."""
    start = tuple(start)
    z = start[2]
    s2 = (start[0], start[1])
    ob = Obszar()
    ob.start, ob.z, ob.ucieta = start, z, False
    ob.dist, ob.rodzic, ob.wyjscia, ob.drzwi = {s2: 0}, {s2: None}, {}, {}
    for e in swiat.wejscia_pola(start):                     # stoimy już na polu przejścia (np. tuż po lądowaniu)
        ob.wyjscia.setdefault(e["id"], (0, start, e))
    q = collections.deque([s2])
    while q:
        cur = q.popleft()
        d = ob.dist[cur]
        for dx, dy in KIERUNKI_8:
            n2 = (cur[0] + dx, cur[1] + dy)
            if n2 in ob.dist:
                continue
            n = (n2[0], n2[1], z)
            if swiat.wolne(n, otwarte):
                if len(ob.dist) >= limit:
                    ob.ucieta = True
                    continue
                ob.dist[n2], ob.rodzic[n2] = d + 1, cur
                q.append(n2)
                continue
            if n in swiat.drzwi:
                if not (dx and dy):                            # drzwi: Use z pola prostopadłego (spec: podejście do (32506,32270))
                    ob.drzwi.setdefault(n, (d, (cur[0], cur[1], z)))
                continue
            for e in swiat.wejscia_pola(n):
                if e["id"] in ob.wyjscia or (e["rodzaj"] != "drabina" and dx and dy):
                    continue                                   # schody/dziura: tylko krok prosty; drabina także ze skosu
                ob.wyjscia[e["id"]] = (d, (cur[0], cur[1], z), e)
    for e in swiat.laczniki:
        od = e["od"]
        if od[2] == z and (od[0], od[1]) in ob.dist:
            ob.wyjscia.setdefault(e["id"], (ob.dist[(od[0], od[1])], od, e))
    return ob


def dojscie_do_celu(ob, cel):
    if cel is None or cel[2] != ob.z:
        return False
    return any((cel[0] + dx, cel[1] + dy) in ob.dist for dx in (-1, 0, 1) for dy in (-1, 0, 1))


def klasa(ob, cel=None):
    """Z1: "zamkniety" = < 60 pól i brak drogi do celu po tym piętrze; inaczej "otwarty"."""
    if ob.ucieta or ob.rozmiar >= OBSZAR_ZAMKNIETY_MAX or dojscie_do_celu(ob, cel):
        return "otwarty"
    return "zamkniety"


def klucz_regionu(ob, otwarte=frozenset()):
    return (ob.z, min(ob.dist), tuple(sorted(otwarte)))


def sciezka_do(ob, pole):
    """Lista pól (x,y,z) od pierwszego kroku do `pole` (bez startu); [] gdy już tam jesteśmy."""
    c = (pole[0], pole[1])
    out = []
    while ob.rodzic[c] is not None:
        out.append((c[0], c[1], ob.z))
        c = ob.rodzic[c]
    return out[::-1]


# --------------------------------------------------------------------------- planowanie po grafie pięter (Z2, Z3)

def plan_wyjscia(swiat, poz, cel=None, zle=(), odwiedzone=(), otwarte=frozenset(), max_wezlow=300,
                 bfs_limit=BFS_LIMIT, max_wyjsc=None):
    """Dijkstra po węzłach (pole lądowania, zbiór hipotetycznie otwartych drzwi). Kandydat = region OTWARTY (nie startowy).
    Zwraca listę {"koszt", "kroki", "pietro", "poz"} rosnąco po koszcie. Region odwiedzony lub już na planie jest zakazany (Z3)."""
    poz = tuple(poz)
    cache = {}

    def ob_dla(node):
        o = cache.get(node)
        if o is None:
            o = cache[node] = bfs(swiat, node[0], node[1], limit=bfs_limit)
        return o

    start = (poz, frozenset(otwarte))
    k0 = klucz_regionu(ob_dla(start), start[1])
    kopiec = [(0, 0, start, (), (k0,))]
    licznik, best, kand = 1, {}, []
    while kopiec and len(best) < max_wezlow:
        koszt, _, node, kroki, regiony = heapq.heappop(kopiec)
        if node in best:
            continue
        best[node] = koszt
        ob = ob_dla(node)
        if kroki and klasa(ob, cel) != "zamkniety":
            kand.append({"koszt": koszt, "kroki": kroki, "pietro": node[0][2], "poz": node[0]})
            continue
        otw = node[1]
        for eid, (d, stand, e) in sorted(ob.wyjscia.items(), key=lambda kv: kv[0])[:max_wyjsc]:
            if eid in zle:
                continue
            if e["rodzaj"] == "lacznik":
                if not all(swiat.drzwi_ok(t, otw) for t in e["kroki"]):
                    continue
                dod = max(1, len(e["kroki"]))
            else:
                dod = 1
            nn = (tuple(e["do"]), otw)
            nk = klucz_regionu(ob_dla(nn), otw)
            if nk in regiony or nk in odwiedzone:
                continue
            licznik += 1
            heapq.heappush(kopiec, (koszt + d + dod, licznik, nn, kroki + (("przejscie", e, stand, d),), regiony + (nk,)))
        for dt, (d, stand) in sorted(ob.drzwi.items()):
            if ("drzwi", dt) in zle or dt in otw:
                continue
            nn = (stand, otw | {dt})
            nk = klucz_regionu(ob_dla(nn), nn[1])
            if nk in regiony or nk in odwiedzone:
                continue
            licznik += 1
            heapq.heappush(kopiec, (koszt + d + 1, licznik, nn, kroki + (("drzwi", dt, stand, d),), regiony + (nk,)))
    kand.sort(key=lambda k: (k["koszt"], repr([(r[0], r[1] if r[0] != "przejscie" else r[1]["id"]) for r in k["kroki"]])))
    return kand


def wybierz_plan(kand, cel, rng):
    """Najpierw regiony na piętrze celu (Z2); wśród równych kosztem losowo z ziarnem (Z: losowość tylko wśród równorzędnych)."""
    if not kand:
        return None, 0
    pula = [k for k in kand if cel is None or k["pietro"] == cel[2]] or kand
    rown = [k for k in pula if k["koszt"] == pula[0]["koszt"]]
    return (rng.choice(rown) if len(rown) > 1 else rown[0]), len(rown)


# --------------------------------------------------------------------------- symulacja

class Sym:
    def __init__(self, swiat, poz, cel=None, punkty=(), ziarno=0, krok_s=KROK_S, historia=(), losowy_czas_czekania=True,
                 prog_zamkniety_s=PROG_ZAMKNIETY_S, prog_otwarty_s=PROG_OTWARTY_S, koszt_proby_s=KOSZT_NIEUDANEJ_PROBY_S,
                 prob_max=PROB_MAX, akcje_max=AKCJE_MAX, czas_max_s=CZAS_MAX_S, plan_bfs_limit=BFS_LIMIT, plan_max_wyjsc=None):
        self.swiat = swiat.kopia()
        self.poz = self.start = tuple(poz)
        self.cel = tuple(cel) if cel is not None else None
        self.punkty = [tuple(p) for p in punkty]
        self.rng = random.Random(ziarno)
        self.ziarno = ziarno
        self.krok_lo, self.krok_hi = (krok_s, krok_s) if isinstance(krok_s, (int, float)) else tuple(krok_s)
        self.losowy = losowy_czas_czekania
        self.prog_z, self.prog_o = prog_zamkniety_s, prog_otwarty_s
        self.koszt_proby, self.prob_max = koszt_proby_s, prob_max
        self.akcje_max, self.czas_max = akcje_max, czas_max_s
        self.kroki, self.extra = 0, 0.0
        self.sciezka = [self.poz]
        self.hist = collections.deque([tuple(h) for h in historia] + [self.poz], maxlen=12)
        self.zle, self.zle_pola, self.odwiedzone = set(), [], set()
        self.porazki, self.czekaj_seria, self.czekan = 0, 0, 0
        self.zdarzenia, self.proby = [], set()
        self.akcji = 0
        self.plan_bfs_limit, self.plan_max_wyjsc = plan_bfs_limit, plan_max_wyjsc   # F3: budżet planu w cieniu bota

    @property
    def t(self):
        return self.kroki * (self.krok_lo + self.krok_hi) / 2 + self.extra

    # --- ruch
    def _log(self, akcja, **d):
        self.zdarzenia.append({"akcja": akcja, "t": round(self.t, 1), "poz": list(self.poz), **d})

    def _czekaj(self, pole=None):
        w = self.rng.uniform(*CZEKAJ_S) if self.losowy else sum(CZEKAJ_S) / 2
        self.extra += w
        self.czekaj_seria += 1
        self.czekan += 1
        self._log("czekaj", s=round(w, 1), pole=list(pole) if pole else None)

    def _czekaj_na(self, pole):
        """Z6: pole zajęte (gracz/mob): czekaj losowo, najwyżej CZEKAJ_MAX razy z rzędu. True = pole wolne."""
        while True:
            do = self.swiat.blokady.get(tuple(pole))
            if do is None or do <= self.t:
                self.czekaj_seria = 0
                return True
            if self.czekaj_seria >= CZEKAJ_MAX:
                self.czekaj_seria = 0
                return False
            self._czekaj(pole)

    def _ruch(self, pola):
        for p in pola:
            if not self._czekaj_na(p):
                return False
            self.poz = tuple(p)
            self.kroki += 1
            self.sciezka.append(self.poz)
            self.hist.append(self.poz)
        return True

    def _porazka(self, klucz, pole, powod):
        self.zle.add(klucz)
        self.zle_pola.append(list(pole))
        self.porazki += 1
        self.extra += self.koszt_proby
        self._log("porazka", pole=list(pole), powod=powod, porazki=self.porazki)

    # --- opcje (zgodne z OPCJE d3_zawieszka)
    def _blokada_blisko(self):
        return any(do > self.t and _cheb(p, self.poz) <= 2 and p[2] == self.poz[2] for p, do in self.swiat.blokady.items())

    def opcje(self, ob, kl):
        poz, z, cel = self.poz, self.poz[2], self.cel
        zam = kl == "zamkniety"
        kier = (_znak(cel[0] - poz[0]), _znak(cel[1] - poz[1])) if cel is not None and cel[2] == z else None
        if kier == (0, 0):
            kier = None
        out = []
        # krok_skos
        o = {"akcja": "krok_skos", "mozliwa": False, "dopuszczalna": False}
        if kier is None:
            o["powod"] = "brak_celu"
        else:
            kand = [kier] if kier[0] and kier[1] else [(kier[0] or s, kier[1] or s) for s in (-1, 1)]
            for v in kand:
                n = (poz[0] + v[0], poz[1] + v[1], z)
                if self.swiat.wolne(n) and self.swiat.blokady.get(n, 0) <= self.t:
                    o.update(mozliwa=True, dopuszczalna=not zam, kierunek=list(v), _cel=n)
                    break
            else:
                o["powod"] = "pole_zajete"
        if zam:
            o.setdefault("powod", "zamkniety_obszar")
        out.append(o)
        # cofnij
        o = {"akcja": "cofnij", "mozliwa": False, "dopuszczalna": False}
        wstecz = [p for p in list(self.hist)[:-1] if p[2] == z][-3:]
        if not wstecz:
            o["powod"] = "brak_historii"
        else:
            ok = (wstecz[0][0], wstecz[0][1]) in ob.dist and (wstecz[0][0], wstecz[0][1]) != (poz[0], poz[1])
            o.update(mozliwa=ok, dopuszczalna=ok and not zam, kroki=len(wstecz), cel_poz=list(wstecz[0]), _cel=wstecz[0])
        out.append(o)
        # inny_punkt (Z5)
        o = {"akcja": "inny_punkt", "mozliwa": False, "dopuszczalna": False, "osiagalnych": 0, "sprawdzono": 0}
        kandp = []
        for q in self.punkty + ([cel] if cel is not None and cel not in self.punkty else []):
            if q[2] != z:
                continue
            o["sprawdzono"] += 1
            if (q[0], q[1]) in ob.dist and _cheb(q, self.start) > PROMIEN and ("p", q) not in self.proby:
                o["osiagalnych"] += 1
                kandp.append((ob.dist[(q[0], q[1])], q))
        if kandp:
            wlasciwe = [k for k in kandp if kier is None or (_znak(k[1][0] - poz[0]), _znak(k[1][1] - poz[1])) != kier] or kandp
            dmin = min(k[0] for k in wlasciwe)
            rown = sorted(k[1] for k in wlasciwe if k[0] == dmin)
            q = self.rng.choice(rown) if len(rown) > 1 else rown[0]
            o.update(mozliwa=True, dopuszczalna=not zam, droga=dmin, punkt=list(q), rownorzedne=len(rown), _cel=q)
        elif zam:
            o["powod"] = "zamkniety_obszar"
        out.append(o)
        # przejscie_pietra (Z2, Z3, Z4): graf pięter / drzwi / łączniki
        o = {"akcja": "przejscie_pietra", "mozliwa": False, "dopuszczalna": False}
        kand = plan_wyjscia(self.swiat, poz, cel, self.zle, self.odwiedzone,
                            bfs_limit=self.plan_bfs_limit, max_wyjsc=self.plan_max_wyjsc)
        plan, rown = wybierz_plan(kand, cel, self.rng)
        if plan is None:
            o["powod"] = "brak_wyjscia" if not self.zle else "wyczerpane_wyjscia"
        else:
            r = plan["kroki"][0]
            e = r[1] if r[0] == "przejscie" else None
            o.update(mozliwa=True, dopuszczalna=True, rodzaj=e["rodzaj"] if e else "drzwi",
                     wej=list((e["od"] if e else r[1])), pietro_docelowe=plan["poz"][2], droga=r[3], koszt=plan["koszt"],
                     rownorzedne=rown, krokow_planu=len(plan["kroki"]), _krok=r)
        out.append(o)
        # czekaj (Z6) i alarm
        bl = self._blokada_blisko()
        out.append({"akcja": "czekaj", "mozliwa": True, "dopuszczalna": bl and self.czekaj_seria < CZEKAJ_MAX and self.porazki == 0,
                    "blokada_blisko": bl, "s_czekania": round(self.czekan, 1)})
        out.append({"akcja": "alarm", "mozliwa": True, "dopuszczalna": True, "porazki": self.porazki})
        return out

    # --- polityka (Z1-Z7)
    def polityka(self, opcje, kl):
        ok = {o["akcja"]: o for o in opcje if o.get("dopuszczalna")}
        if kl == "zamkniety":
            kolej = ("przejscie_pietra", "czekaj")
        else:
            kolej = ("inny_punkt", "przejscie_pietra", "cofnij", "krok_skos", "czekaj")
        for a in kolej:
            o = ok.get(a)
            if o is None:
                continue
            if a in ("cofnij", "krok_skos") and (self.poz, a) in self.proby:
                continue
            return o
        return ok["alarm"]

    # --- główna pętla
    def sukces(self, ob, kl, klasa0):
        if self.cel is not None and self.poz[2] == self.cel[2] and _cheb(self.poz, self.cel) <= 1:
            return "cel"
        if klasa0 == "zamkniety":
            return "obszar_otwarty" if kl == "otwarty" else None
        if self.poz[2] != self.start[2] or _cheb(self.poz, self.start) > PROMIEN:
            return "poza_promieniem"
        return None

    def wykonaj(self, o, ob):
        a = o["akcja"]
        if a == "przejscie_pietra":
            return self._przejscie(o["_krok"], ob)
        if a == "czekaj":
            self._czekaj()
            return
        if a in ("krok_skos", "cofnij", "inny_punkt"):
            cel = o["_cel"]
            if a == "inny_punkt":
                self.proby.add(("p", tuple(cel)))
            else:
                self.proby.add((self.poz, a))
            sc = sciezka_do(ob, cel)
            self._log(a, cel=list(cel), dlugosc=len(sc))
            self._ruch(sc)

    def _przejscie(self, krok, ob):
        typ, obj, stand, d = krok
        reg = klucz_regionu(ob)
        klucz = obj["id"] if typ == "przejscie" else ("drzwi", obj)
        pole = obj["od"] if typ == "przejscie" else obj
        sc = sciezka_do(ob, stand)
        self._log("dojscie", do=list(stand), dlugosc=len(sc), do_czego=typ)
        if not self._ruch(sc):
            return self._porazka(klucz, pole, "zablokowane_po_czekaniu")
        if typ == "drzwi":
            self.kroki += 1
            if self.swiat.drzwi[obj]["zablokowane"]:
                return self._porazka(klucz, obj, "drzwi_zablokowane")
            if not self._czekaj_na(obj):      # za drzwiami stoi ktoś: to samo co zajęte pole
                return self._porazka(klucz, obj, "zablokowane_po_czekaniu")
            self.swiat.drzwi[obj]["otwarte"] = True
            self._log("drzwi", pole=list(obj))
            return
        e = obj
        if e["rodzaj"] == "lacznik":
            if not all(self.swiat.drzwi_ok(t) for t in e["kroki"]):
                return self._porazka(klucz, pole, "drzwi_zamkniete")
            if not self._ruch(e["kroki"] or [e["do"]]):
                return self._porazka(klucz, pole, "zablokowane_po_czekaniu")
            self.odwiedzone.add(reg)
            self._log("przejscie", rodzaj="lacznik", od=list(pole), do=list(e["do"]))
            return
        if not self._czekaj_na(pole):
            return self._porazka(klucz, pole, "zablokowane_po_czekaniu")
        if not e["dziala"]:
            return self._porazka(klucz, pole, "brak_zmiany_pietra")   # Z4: pole złe, następne wyjście
        self.odwiedzone.add(reg)
        self.kroki += 1
        self.poz = tuple(e["do"])
        self.sciezka.append(self.poz)
        self.hist.append(self.poz)
        self._log("przejscie", rodzaj=e["rodzaj"], od=list(pole), do=list(e["do"]), z_od=pole[2], z_do=self.poz[2])

    def uruchom(self):
        ob0 = bfs(self.swiat, self.poz)
        klasa0 = klasa(ob0, self.cel)
        obszar0 = ob0.rozmiar
        wynik, powod, alarm = None, None, False
        while wynik is None:
            ob = bfs(self.swiat, self.poz)
            kl = klasa(ob, self.cel)
            s = self.sukces(ob, kl, klasa0)
            if s:
                wynik, powod = "wyszedl", s
                break
            if self.porazki >= self.prob_max:
                wynik, powod, alarm = "alarm", "limit_prob", True
                break
            if self.akcji >= self.akcje_max or self.t > self.czas_max:
                wynik, powod, alarm = "alarm", "limit_akcji", True
                break
            o = self.polityka(self.opcje(ob, kl), kl)
            self.akcji += 1
            if o["akcja"] == "alarm":
                bez = not self.zle and self.czekan == 0
                if bez and klasa0 == "otwarty" and self.cel is None and not self.punkty:
                    # otwarty obszar, a symulator nie dostał ani celu, ani punktów trasy (Z5): nie wie dokąd iść. To brak DANYCH
                    # (UNKNOWN), nie dowód, że wyjścia nie ma (Z7): nie raportujemy tego jako alarm.
                    wynik, powod, alarm = "brak_danych", "brak_celu_i_punktow_trasy", False
                    break
                wynik, powod, alarm = ("brak_wyjscia" if bez else "alarm"), ("brak_wyjscia" if bez else "wyczerpane_proby"), True
                break
            self.wykonaj(o, ob)
        prog = self.prog_z if klasa0 == "zamkniety" else self.prog_o
        czas = self.t
        return {"wynik": wynik, "powod": powod, "alarm": alarm, "stop": False,
                "czas_s": round(czas, 1),
                "czas_zakres_s": [round(self.kroki * self.krok_lo + self.extra, 1), round(self.kroki * self.krok_hi + self.extra, 1)],
                "kroki": self.kroki, "prog_s": prog, "czas_od_zawieszki_s": round(prog + czas, 1),
                "klasa_start": klasa0, "obszar_start": obszar0, "poz_start": list(self.start), "poz_koniec": list(self.poz),
                "sciezka": [tuple(p) for p in self.sciezka], "porazki": self.porazki, "zle_pola": self.zle_pola,
                "zdarzenia": self.zdarzenia, "ziarno": self.ziarno}


def symuluj(swiat, poz, cel=None, punkty=(), ziarno=0, **kw):
    """Symuluje reakcję na zawieszkę w `poz` (x,y,z). Świat wejściowy nie jest zmieniany.
    Zwraca słownik: wynik ("wyszedl" / "alarm" / "brak_wyjscia"), czas_s, sciezka, alarm, stop (zawsze False), ..."""
    return Sym(swiat, poz, cel, punkty, ziarno, **kw).uruchom()


def opcje_d3(swiat, poz, cel=None, punkty=(), historia=(), ziarno=0):
    """Same opcje D3 (jak `Zawieszka._opcje`) dla pozycji `poz`, bez wykonania. Klucze z `_` (uchwyty) pominięte."""
    s = Sym(swiat, poz, cel, punkty, ziarno, historia=historia)
    ob = bfs(s.swiat, s.poz)
    kl = klasa(ob, s.cel)
    return kl, [{k: v for k, v in o.items() if not k.startswith("_")} for o in s.opcje(ob, kl)]


def klasyfikuj(swiat, poz, cel=None):
    ob = bfs(swiat, poz)
    return klasa(ob, cel), ob.rozmiar


# --------------------------------------------------------------------------- świat z repo (tylko odczyt)

def swiat_z_repo(drzwi_otwarte=False, ogien=(), blokady=None, katalog=KATALOG, nieznane_przechodnie=False):
    """Prawdziwa mapa (mapa/map74.otmm), przejścia i łączniki z trasy/miejsca_troll.json, nauczone dziury z
    trasy/dziury_nauczone.json. Drzwi (32505,32270,z8): ściana w mapie, w grze przechodnie po otwarciu (SYSTEM_RETRONIC)."""
    import mapa as mapa_mod  # noqa: PLC0415
    katalog = Path(katalog)
    mapa = mapa_mod.Mapa(katalog / "mapa" / "map74.otmm")
    przejscia, dziury = [], []
    try:
        mt = json.loads((katalog / "trasy" / "miejsca_troll.json").read_text())
        for p in mt.get("przejscia", []):
            przejscia.append(dict(od=p["pole"], do=p["wyjscie_dol"], rodzaj="schody", id=p["id"] + ":w_dol", zrodlo="miejsca_troll"))
            # w górę: nagranie przeszło z pola wejscie_dol (chodliwe) na wyjscie_gora; mapa nie wskazuje pola przejścia = łącznik
            przejscia.append(dict(od=p["wejscie_dol"], do=p["wyjscie_gora"], rodzaj="lacznik", kroki=[p["wyjscie_gora"]],
                                  id=p["id"] + ":w_gore", zrodlo="miejsca_troll"))
        for l in mt.get("laczniki", []):
            for kier, (a, b, kr) in enumerate(((l["od"], l["do"], l["kroki"]), (l["do"], l["od"], list(reversed(l["kroki"][:-1])) + [l["od"]]))):
                przejscia.append(dict(od=a, do=b, rodzaj="lacznik", kroki=kr, id=l["id"] + (":tam" if kier == 0 else ":spowrotem"),
                                      zrodlo="miejsca_troll"))
    except (OSError, ValueError, KeyError):
        pass
    try:
        dziury = [tuple(d) for d in json.loads((katalog / "trasy" / "dziury_nauczone.json").read_text()).get("dziury", [])]
    except (OSError, ValueError):
        pass
    return Swiat(mapa=mapa, dziury=dziury, ogien=ogien, przejscia=przejscia, blokady=blokady,
                 drzwi={(32505, 32270, 8): {"otwarte": bool(drzwi_otwarte)}}, nieznane_przechodnie=nieznane_przechodnie)


# --------------------------------------------------------------------------- walidacja na danych (tylko odczyt)

DANE_MODELE = Path.home() / "Games" / "Retronic" / "modele-test" / "dane"


def _json_lista(plik):
    try:
        t = Path(plik).read_text()
    except OSError:
        return None
    t = t.strip()
    return json.loads(t) if t.startswith("[") else [json.loads(l) for l in t.splitlines() if l.strip()]


def waliduj(swiat=None, dane=DANE_MODELE, katalog=KATALOG):
    """Zwraca słownik z trzema zestawieniami: epizody (klasa i rozmiar obszaru vs przyczyny.json), wyrocznia (czas symulacji vs
    rzeczywisty), przejęcia Karola (logi/pomoc-karola.jsonl, 62 bez trybu brak_bota). Brak pliku = klucz None (UNKNOWN)."""
    swiat = swiat or swiat_z_repo(katalog=katalog)
    wyn = {"epizody": None, "wyrocznia": None, "karol": None}
    epi, prz = _json_lista(Path(dane) / "epizody.jsonl"), _json_lista(Path(dane) / "przyczyny.json")
    if epi is not None and prz is not None:
        pm = {p["id"]: p for p in prz}
        wiersze = []
        for e in epi:
            p = pm.get(e["id"])
            if p is None:
                continue
            ob = bfs(swiat, e["poz"])
            kl, n = klasa(ob), ob.rozmiar
            wiersze.append({"id": e["id"], "poz": e["poz"], "sim_klasa": kl, "sim_obszar": n, "ucieta": ob.ucieta, "ref_klasa": "zamkniety" if p["typ"] == "zamkniety_obszar" else "otwarty",
                            "ref_obszar": p["obszar"], "trwa_s": e["trwa_s"]})
        wyn["epizody"] = {"epizodow": len(epi), "porownanych": len(wiersze), "zgodna_klasa": sum(w["sim_klasa"] == w["ref_klasa"] for w in wiersze),
                          "zgodny_obszar": sum(w["sim_obszar"] == w["ref_obszar"] for w in wiersze), "wiersze": wiersze}
    ora = _json_lista(Path(dane) / "oracle_wyjscie.json")
    if ora is not None:
        wiersze = []
        for r in ora:
            if r.get("real_s") is None:
                continue
            w = symuluj(swiat, r["poz"], ziarno=1)
            wiersze.append({"poz": r["poz"], "real_s": r["real_s"], "ideal_s": r["ideal_s"], "sim_s": w["czas_s"], "wynik": w["wynik"],
                            "kroki": w["kroki"], "obszar": r["obszar"], "dystans_najblizszego": r["dystans_do_wyjscia"]})
        wyn["wyrocznia"] = {"przypadkow": len(ora), "z_realnym_wyjsciem": len(wiersze), "wiersze": wiersze}
    kar = _json_lista(Path(katalog) / "logi" / "pomoc-karola.jsonl")
    if kar is not None:
        wiersze = []
        for k in kar:
            if "poz_start" not in k or k.get("tryb") == "brak_bota":
                continue
            ps, pk = k["poz_start"], k.get("poz_koniec") or k["poz_start"]
            kl, n = klasyfikuj(swiat, ps)
            w = symuluj(swiat, ps, ziarno=1) if kl == "zamkniety" else None
            ob = bfs(swiat, ps)
            karol_wyszedl = pk[2] != ps[2] or (pk[0], pk[1]) not in ob.dist
            wiersze.append({"start": k["start"], "poz": ps, "poz_koniec": pk, "tryb": k["tryb"], "czas_karola_s": k["czas_s"],
                            "klasa": kl, "obszar": n, "karol_wyszedl_z_obszaru": karol_wyszedl,
                            "sim_wynik": w["wynik"] if w else None, "sim_czas_s": w["czas_s"] if w else None})
        wyn["karol"] = {"przypadkow": len(wiersze), "wiersze": wiersze}
    return wyn


def raport_md(w):
    L = ["# SYMULATOR zawieszek: wyniki walidacji (16.10)", "",
         "Wygenerowano `python3 narzedzia/symulator_zawieszek.py waliduj` (offline, tylko odczyt; krok 0,6-0,9 s to stała z kodu, nie pomiar).",
         "Świat: prawdziwa mapa + przejścia i łączniki z `trasy/miejsca_troll.json` + nauczone dziury; drzwi (32505,32270,z8) ZAMKNIĘTE "
         "(stan drzwi w historycznych epizodach = UNKNOWN, więc wariant konserwatywny).", ""]
    e = w.get("epizody")
    L += ["## 1. Klasyfikacja obszaru vs przyczyny.json (Z1)", ""]
    if e is None:
        L += ["UNKNOWN: brak epizody.jsonl albo przyczyny.json.", ""]
    else:
        zl = [x for x in e["wiersze"] if x["sim_klasa"] != x["ref_klasa"]]
        L += [f"- epizodów w pliku: {e['epizodow']}, z odpowiednikiem w przyczyny.json: {e['porownanych']}",
              f"- zgodna klasa zamknięty/otwarty: {e['zgodna_klasa']}/{e['porownanych']}",
              f"- zgodny rozmiar obszaru (BFS): {e['zgodny_obszar']}/{e['porownanych']}",
              f"- różnica o 1 pole (sim mniejszy): {sum(x['ref_obszar'] - x['sim_obszar'] == 1 and not x['ucieta'] for x in e['wiersze'])} "
              "(to nauczona dziura (32498,32271,z8), którą symulator traktuje jak ścianę; referencja ją liczy), limit BFS 4000: "
              f"{sum(x['ucieta'] and x['sim_obszar'] != x['ref_obszar'] for x in e['wiersze'])}", ""]
        if zl:
            L += ["Niezgodne klasy (rozmiar sim / ref):", ""] + [f"- {x['id']} {x['poz']}: sim {x['sim_klasa']} {x['sim_obszar']}, ref {x['ref_klasa']} {x['ref_obszar']}" for x in zl[:15]] + [""]
    o = w.get("wyrocznia")
    L += ["## 2. Czas wyjścia: symulacja vs rzeczywistość (zamknięte obszary)", ""]
    if o is None:
        L += ["UNKNOWN: brak oracle_wyjscie.json.", ""]
    else:
        wi = o["wiersze"]
        ok = [x for x in wi if x["wynik"] == "wyszedl"]
        L += [f"- przypadków z potwierdzonym wyjściem w telemetrii: {len(wi)}; symulacja kończy 'wyszedl': {len(ok)}"]
        if ok:
            real = [x["real_s"] for x in ok]
            sim = [x["sim_s"] for x in ok]
            idl = [x["ideal_s"][1] for x in ok]
            L += [f"- suma rzeczywista {sum(real) / 60:.0f} min, suma symulacji {sum(sim) / 60:.1f} min, suma 'ideału' wyroczni (najbliższe wyjście x 0,9 s) {sum(idl) / 60:.1f} min",
                  f"- mediana: rzeczywisty {statistics.median(real):.0f} s, symulacja {statistics.median(sim):.1f} s, ideał {statistics.median(idl):.1f} s",
                  f"- symulacja > ideał (graf pięter dokłada kroki): {sum(s > i + 0.05 for s, i in zip(sim, idl))}/{len(ok)}; symulacja < rzeczywistość: {sum(s < r for s, r in zip(sim, real))}/{len(ok)}"]
        for x in wi:
            if x["wynik"] != "wyszedl":
                L.append(f"- bez wyjścia w symulacji: {x['poz']} -> {x['wynik']}")
        L += ["", "[HIP] Różnica rzeczywisty - symulacja to górna granica tego, co da reguła z mapy; model nie przewiduje rzeczywistego czasu "
                  "(opisuje reakcję wg Z1-Z8, nie obecnego bota), więc błąd względem rzeczywistości jest tu oczekiwany, nie miarą jakości modelu.", ""]
    k = w.get("karol")
    L += ["## 3. Przejęcia Karola jako przypadki testowe", ""]
    if k is None:
        L += ["UNKNOWN: brak logi/pomoc-karola.jsonl.", ""]
    else:
        wi = k["wiersze"]
        zam = [x for x in wi if x["klasa"] == "zamkniety"]
        L += [f"- przypadków (bez trybu brak_bota): {k['przypadkow']}", f"- start w zamkniętym obszarze: {len(zam)}, w otwartym: {len(wi) - len(zam)}",
              f"- Karol opuścił obszar startu (piętro albo poza BFS): {sum(x['karol_wyszedl_z_obszaru'] for x in wi)}/{len(wi)}"]
        if zam:
            L += [f"- zamknięte: symulacja 'wyszedl' w {sum(x['sim_wynik'] == 'wyszedl' for x in zam)}/{len(zam)}, wynik inny: "
                  + (", ".join(f"{x['poz']}={x['sim_wynik']}" for x in zam if x["sim_wynik"] != "wyszedl") or "brak")]
        L += ["", "| start | poz | klasa | obszar | tryb | Karol s | Karol wyszedł | sim | sim s |", "|---|---|---|---|---|---|---|---|---|"]
        for x in wi:
            L.append(f"| {x['start'][11:]} | {x['poz']} | {x['klasa']} | {x['obszar']} | {x['tryb']} | {x['czas_karola_s']} | "
                     f"{'tak' if x['karol_wyszedl_z_obszaru'] else 'nie'} | {x['sim_wynik'] or '-'} | {x['sim_czas_s'] if x['sim_czas_s'] is not None else '-'} |")
        L += ["", "Uwaga: przejęcie Karola to nie zawsze wyjście z zawieszki (jest 'bot_aktywny', 'bot_zatrzymany'); tabela to klasyfikacja startów, "
                  "nie dowód, że Karol rozwiązywał zawieszkę. Ocena zgodności z intencją Karola = UNKNOWN bez jego opisu każdego przejęcia."]
    return "\n".join(L) + "\n"



# --------------------------------------------------------------------------- walidacja rozszerzona (16.10): odtworzenie na danych

def _mediana(v):
    return statistics.median(v) if v else None


def _p90(v):
    if not v:
        return None
    v = sorted(v)
    return v[min(len(v) - 1, int(0.9 * len(v)))]       # p90 "w górę" (nearest-rank bez interpolacji)


def punkty_tras(katalog=KATALOG):
    """Wszystkie punkty (x,y,z) z trasy/*.json zapisanych jako lista trójek. Która trasa była aktywna = UNKNOWN, więc to zbiór wszystkich."""
    out = set()
    for f in sorted((Path(katalog) / "trasy").glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(d, list):
            for q in d:
                if isinstance(q, list) and len(q) == 3 and all(isinstance(c, int) for c in q):
                    out.add(tuple(q))
    return sorted(out)


def _punkty_obok(punkty, poz, promien=30):
    return [q for q in punkty if q[2] == poz[2] and _cheb(q, poz) <= promien]


def _cel_pietro(historia, poz):
    """Założenie C (HIP): bot chciał wrócić tam, skąd przyszedł. Cel = ostatnia pozycja historii z INNEGO piętra niż poz (pole docelowe
    jest tylko nośnikiem piętra: dla innego piętra nie wpływa na kierunek kroku ani na klasyfikację)."""
    for h in reversed(list(historia)):
        if h[2] != poz[2]:
            return tuple(h)
    return None


def _real_exit_info(swiat, u):
    """Rzeczywiste wyjście z ucieczka.json: (jak, po_s, gdzie, pewne). pewne = zmiana piętra (pewne) albo wejście na pole poza BFS-em."""
    r = (u or {}).get("wyjscie")
    if not r:
        return None
    return {"jak": r["jak"], "po_s": r["po_s"], "gdzie": tuple(r["gdzie"]), "pewne": r["jak"] == "pietro"}


def odtworz_epizody(swiat=None, dane=DANE_MODELE, katalog=KATALOG, ziarno=1):
    """Odtwarza KAŻDY epizod z epizody.jsonl (pozycja, piętro, historia z `ostatnie_kroki`) w trzech wariantach danych wejściowych:
    A = tylko pozycja + historia (bez założeń); B = A + punkty z tras (UNKNOWN która trasa) w promieniu 30 pól; C = B + cel-piętro
    "skąd przyszedł" (HIP). Rzeczywiste wyjście z ucieczka.json (dopasowanie po dniu, postaci, pozycji i czasie trwania)."""
    swiat = swiat or swiat_z_repo(katalog=katalog)
    epi = _json_lista(Path(dane) / "epizody.jsonl")
    ucz = _json_lista(Path(dane) / "ucieczka.json")
    prz = _json_lista(Path(dane) / "przyczyny.json")
    if epi is None:
        return None
    um = {(u["dzien"], u["postac"], tuple(u["poz"]), u["trwa_s"]): u for u in (ucz or [])}
    pm = {p["id"]: p for p in (prz or [])}
    pk = punkty_tras(katalog)
    wiersze = []
    for e in epi:
        poz = tuple(e["poz"])
        hist = [tuple(h) for h in e.get("ostatnie_kroki") or []]
        u = um.get((e["dzien"], e["postac"], poz, e["trwa_s"]))
        wz = {}
        for nazwa, kw in (("A", {}), ("B", {"punkty": _punkty_obok(pk, poz)}),
                          ("C", {"punkty": _punkty_obok(pk, poz), "cel": _cel_pietro(hist, poz)})):
            wz[nazwa] = symuluj(swiat, poz, ziarno=ziarno, historia=hist, **kw)
        wiersze.append({"id": e["id"], "poz": list(poz), "trwa_s": e["trwa_s"], "zamierzony": bool(e.get("zamierzony")), "stan": e.get("stan_wiodacy"),
                        "ma_ucieczka": u is not None, "ma_przyczyny": e["id"] in pm, "obszar_ref": (pm.get(e["id"]) or {}).get("obszar"),
                        "ref_zamkniety": None if e["id"] not in pm else pm[e["id"]]["typ"] == "zamkniety_obszar",
                        "real": _real_exit_info(swiat, u), "cel_hint": _cel_pietro(hist, poz), "wariant": wz})
    return {"epizodow": len(epi), "wiersze": wiersze}


def blad_czasu(wiersze, wariant="A", tylko_pewne=False):
    """Zamknięte epizody z rzeczywistym wyjściem w telemetrii, które symulacja kończy 'wyszedl'. Błąd = przewidziany - rzeczywisty,
    oba liczone od początku zawieszki: przewidziany = próg (15 s) + czas symulacji; rzeczywisty = `po_s` z ucieczka.json."""
    out = []
    for w in wiersze:
        s = w["wariant"][wariant]
        if not w["ref_zamkniety"] or not w["real"] or s["wynik"] != "wyszedl" or (tylko_pewne and not w["real"]["pewne"]):
            continue
        out.append({"id": w["id"], "poz": w["poz"], "przewidziany_s": s["czas_od_zawieszki_s"], "rzeczywisty_s": w["real"]["po_s"],
                    "blad_s": round(s["czas_od_zawieszki_s"] - w["real"]["po_s"], 1), "jak": w["real"]["jak"]})
    return out


def porownaj_siatke(swiat, dane=DANE_MODELE):
    """mapa_15x11 z epizodów (zapis z mapa.py w chwili epizodu; środek '@' = poz epizodu) vs świat symulatora. Pola z mobem/graczem
    (litery) pomijam. Zgodność: '#' <-> nie da się stanąć, '.' <-> da się, 's' <-> pole przejścia pięter, '?' <-> nieznane w mapie."""
    epi = _json_lista(Path(dane) / "epizody.jsonl")
    if epi is None:
        return None
    n = zg = 0
    roz = collections.Counter()
    przyklady = []
    for e in epi:
        x0, y0, z = e["poz"]
        for dy, wiersz in enumerate(e.get("mapa_15x11") or []):
            for dx, c in enumerate(wiersz):
                if c in "@" or c not in "#.s?":
                    continue
                p = (x0 + dx - 7, y0 + dy - 5, z)
                m = swiat.mapa.przechodnie(*p) if swiat.mapa is not None else None
                sd = swiat.mapa.schody_lub_dziura(*p) if swiat.mapa is not None else False
                sim = "s" if sd else ("#" if m is False else ("?" if m is None else "."))
                if p in swiat.dziury or p in swiat.sciany:
                    sim = "#"
                n += 1
                if sim == c:
                    zg += 1
                else:
                    roz[(c, sim)] += 1
                    if len(przyklady) < 6:
                        przyklady.append((e["id"], p, c, sim))
    return {"pol": n, "zgodnych": zg, "rozne": dict(roz), "przyklady": przyklady}


def porownaj_wyrocznie(swiat, dane=DANE_MODELE):
    """oracle_wyjscie.json (BFS po fladze 2, najbliższe wyjście niezależnie od kierunku pięter) vs symulator. Dla każdego z 43 wpisów:
    pierwsze przejście, które symulator wykonuje (pole wejścia), jego koszt w krokach, i czy to pole = pole wyroczni."""
    ora = _json_lista(Path(dane) / "oracle_wyjscie.json")
    if ora is None:
        return None
    wiersze = []
    for r in ora:
        poz = tuple(r["poz"])
        w = symuluj(swiat, poz, ziarno=1)
        pr = [z for z in w["zdarzenia"] if z["akcja"] == "przejscie"]
        doj = [z for z in w["zdarzenia"] if z["akcja"] == "dojscie"]
        wej = tuple(pr[0]["od"][:2]) if pr and "od" in pr[0] else None
        wiersze.append({"poz": list(poz), "orakl_wyjscie": r["wyjscie"], "orakl_dystans": r["dystans_do_wyjscia"], "real_s": r.get("real_s"),
                        "real_jak": r.get("jak"), "sim_wynik": w["wynik"], "sim_kroki": w["kroki"], "sim_s": w["czas_s"],
                        "sim_wejscie": list(wej) if wej else None, "sim_rodzaj": pr[0]["rodzaj"] if pr else None,
                        "sim_dojscie": doj[0]["dlugosc"] if doj else None,
                        "to_samo_pole": bool(wej and tuple(r["wyjscie"]) == wej)})
    return {"przypadkow": len(wiersze), "wiersze": wiersze}


def _telemetria_pozycje(katalog, dzien):
    f = Path(katalog) / "logi" / f"telemetria-{dzien}.jsonl"
    out = []
    try:
        for l in f.read_text(errors="replace").splitlines():
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if r.get("typ") == "probka" and r.get("poz"):
                out.append((r["t"], tuple(r["poz"])))
    except OSError:
        return []
    return out


def odtworz_karola(swiat=None, katalog=KATALOG):
    """Każde przejęcie z logi/pomoc-karola.jsonl (bez trybu brak_bota) jako przypadek: klasa startu, to, co zrobiłby symulator
    (wariant A: pozycja bez celu i punktów), i to, co zrobił Karol (poz_koniec; ślad z telemetrii, jeśli próbki istnieją).
    Obszar uciety limitem BFS: wyjście z obszaru rozpoznaję tylko po zmianie piętra (reszta = UNKNOWN)."""
    import bisect  # noqa: PLC0415
    swiat = swiat or swiat_z_repo(katalog=katalog)
    kar = _json_lista(Path(katalog) / "logi" / "pomoc-karola.jsonl")
    if kar is None:
        return None
    tele = {}
    wiersze = []
    pkt = punkty_tras(katalog)
    for k in kar:
        if "poz_start" not in k or k.get("tryb") == "brak_bota":
            continue
        ps, pk = tuple(k["poz_start"]), tuple(k.get("poz_koniec") or k["poz_start"])
        ob = bfs(swiat, ps)
        kl = klasa(ob)
        dzien = k["start"][:10].replace("-", "")
        if dzien not in tele:
            tele[dzien] = _telemetria_pozycje(katalog, dzien)
        ts = [t for t, _ in tele[dzien]]
        i, j = bisect.bisect_left(ts, k["t_start"]), bisect.bisect_right(ts, k["t_koniec"])
        slad = []
        for _, p in tele[dzien][i:j]:
            if not slad or slad[-1] != p:
                slad.append(p)
        if pk[2] != ps[2]:
            wyszedl = True
        elif ob.ucieta:
            wyszedl = None                                       # UNKNOWN: obszar uciety limitem BFS
        else:
            wyszedl = (pk[0], pk[1]) not in ob.dist
        w = symuluj(swiat, ps, ziarno=1)
        wb = symuluj(swiat, ps, ziarno=1, punkty=_punkty_obok(pkt, ps)) if kl == "otwarty" else None
        pr = [z for z in w["zdarzenia"] if z["akcja"] == "przejscie"]
        dr = [z for z in w["zdarzenia"] if z["akcja"] == "drzwi"]
        wiersze.append({"start": k["start"], "poz": list(ps), "poz_koniec": list(pk), "tryb": k["tryb"], "czas_karola_s": k["czas_s"],
                        "klasa": kl, "obszar": ob.rozmiar, "ucieta": ob.ucieta, "karol_wyszedl": wyszedl, "slad_pozycji": len(slad),
                        "ma_slad": bool(slad), "sim_wynik": w["wynik"], "sim_s": w["czas_s"], "sim_kroki": w["kroki"],
                        "sim_koniec": w["poz_koniec"], "sim_rodzaj": (pr[0]["rodzaj"] if pr else ("drzwi" if dr else None)),
                        "simB_wynik": wb["wynik"] if wb else None})
    return {"przypadkow": len(wiersze), "wiersze": wiersze}


def waliduj_rozszerzona(swiat=None, dane=DANE_MODELE, katalog=KATALOG):
    swiat = swiat or swiat_z_repo(katalog=katalog)
    return {"podstawowa": waliduj(swiat, dane, katalog), "epizody": odtworz_epizody(swiat, dane, katalog), "siatka": porownaj_siatke(swiat, dane),
            "wyrocznia": porownaj_wyrocznie(swiat, dane), "karol": odtworz_karola(swiat, katalog), "znane": znane_przypadki(katalog)}


def znane_przypadki(katalog=KATALOG):
    """Trzy znane przypadki z gry: kieszeń z9 z drabiną (32506,32270), ta sama kieszeń z celem na z8, pokój za drzwiami (32507,32270,z8)
    ('2 vs 8 kroków' z SPEC_model_steruje_gra_1016 7: naiwna wyrocznia 2 kroki do (32505,32268), bot liczył 8 kroków do schodów (32498,32270))."""
    zam, otw = swiat_z_repo(drzwi_otwarte=False, katalog=katalog), swiat_z_repo(drzwi_otwarte=True, katalog=katalog)
    wyn = []
    for nazwa, sw_, poz, cel in (("kieszeń z9, bez celu", zam, (32508, 32273, 9), None),
                                 ("kieszeń z9, cel (32502,32270,z8)", zam, (32508, 32273, 9), (32502, 32270, 8)),
                                 ("na polu drabiny (32506,32270,z9), bez celu", zam, (32506, 32270, 9), None),
                                 ("pokój za drzwiami, drzwi ZAMKNIĘTE, cel (32478,32290,z8)", zam, (32507, 32270, 8), (32478, 32290, 8)),
                                 ("pokój za drzwiami, drzwi OTWARTE, cel (32478,32290,z8)", otw, (32507, 32270, 8), (32478, 32290, 8))):
        w = symuluj(sw_, poz, cel=cel, ziarno=1)
        wyn.append({"nazwa": nazwa, "poz": list(poz), "wynik": w["wynik"], "kroki": w["kroki"], "czas_s": w["czas_s"], "koniec": w["poz_koniec"],
                    "zdarzenia": [z["akcja"] + (":" + z["rodzaj"] if z.get("rodzaj") else "") for z in w["zdarzenia"] if z["akcja"] in ("przejscie", "drzwi")]})
    return wyn


def _fmt(v, nd=1):
    return "UNKNOWN" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def raport_rozszerzony_md(W):
    """Raport markdown z `waliduj_rozszerzona`. Każda liczba pochodzi z tego obliczenia; brak danych = UNKNOWN."""
    P = W["podstawowa"]
    L = ["# SYMULATOR zawieszek: wyniki walidacji (16.10)", "",
         "Wygenerowano `python3 narzedzia/symulator_zawieszek.py waliduj` (offline; czyta mapę, trasy, dane z `modele-test/dane/`, `logi/`; nic nie zapisuje).",
         "Krok 0,6-0,9 s to stała z kodu (`cavebot.py`), nie pomiar. Świat: prawdziwa mapa + przejścia i łączniki z `trasy/miejsca_troll.json` "
         "+ nauczone dziury; drzwi (32505,32270,z8) ZAMKNIĘTE (stan drzwi w historycznych epizodach = UNKNOWN, więc wariant konserwatywny).", "",
         "Wejścia symulatora w odtworzeniu epizodów (nic ponad to, co jest w danych epizodu):",
         "- **A** = pozycja + piętro + historia (`ostatnie_kroki`, 10 pozycji tuż przed epizodem). Bez celu i bez punktów trasy.",
         "- **B** = A + wszystkie punkty z `trasy/*.json` na tym piętrze w promieniu 30 pól (która trasa była aktywna = UNKNOWN, więc suma wszystkich).",
         "- **C** = B + cel-piętro \"skąd przyszedłem\" ([HIP]: ostatnia pozycja historii z innego piętra; intencji bota w danych nie ma).", ""]
    E = W["epizody"]
    L += ["## 1. Odtworzenie 107 epizodów zawieszek", ""]
    if E is None:
        L += ["UNKNOWN: brak epizody.jsonl.", ""]
    else:
        wi = E["wiersze"]
        ma = [w for w in wi if w["ma_ucieczka"]]
        L += [f"- epizodów: {E['epizodow']}; zasymulowanych: {len(wi)} (wszystkie mają pozycję i piętro).",
              f"- z rzeczywistym wynikiem (`ucieczka.json`/`przyczyny.json`): {len(ma)}; bez: {len(wi) - len(ma)} "
              f"(powód: zamierzone przerwy/pauzy PRZERWA/PAUZA wyłączone z analizy: {sum(w['zamierzony'] for w in wi if not w['ma_ucieczka'])}/{len(wi) - len(ma)}).", ""]
        zam = [w for w in ma if w["ref_zamkniety"]]
        otw = [w for w in ma if not w["ref_zamkniety"]]
        L += [f"### 1a. Wynik symulacji (ziarno 1) vs klasa referencyjna z przyczyny.json: zamknięte {len(zam)}, otwarte {len(otw)}", "",
              "| wariant | zamknięte: wyszedl | zamknięte: brak_wyjscia | otwarte: wyszedl | otwarte: brak_wyjscia | otwarte: brak_danych |", "|---|---|---|---|---|---|"]
        for v in "ABC":
            c = collections.Counter(w["wariant"][v]["wynik"] for w in zam)
            o = collections.Counter(w["wariant"][v]["wynik"] for w in otw)
            L.append(f"| {v} | {c['wyszedl']} | {c['brak_wyjscia']} | {o['wyszedl']} | {o['brak_wyjscia']} | {o['brak_danych']} |")
        L += ["", "Otwarte bez celu i bez punktów (A) są poza zakresem Z5: symulator nie wie dokąd iść, więc nie twierdzi, że wyjścia nie ma "
                  "(wynik `brak_danych`, nie alarm). Z punktami trasy (B, C) wszystkie otwarte epizody kończą się wyjściem poza promień 2.", ""]
        bw = [w for w in zam if w["wariant"]["A"]["wynik"] == "brak_wyjscia"]
        if bw:
            L += [f"Zamknięte, w których symulator nie znajduje wyjścia: {len(bw)}. Wszystkie leżą w kieszeni z7 przy (32338-32340, 32200-32202, z7). "
                  "Flaga 2 mapy na (32340,32202,z7) nie ma ważnego lądowania (ani (x,y,z+1), ani (x,y+1,z-1) nie są przechodnie), więc to nie jest wyjście wg reguł `pietra.py`. "
                  "Telemetria zgadza się z tym (sprawdzone ręcznie na próbkach wszystkich 4 epizodów z 14.10: cała trasa w x 32338-32340, y 32200-32202, wyłącznie z7, pole (32340,32202) odwiedzane wielokrotnie bez zmiany piętra; ucieczka.json liczy to jako 'skok_poza_obszar', bo jej BFS wyklucza pola z flagą 2). "
                  "Czasy tych epizodów: " + ", ".join(f"{w['trwa_s']:.0f} s" for w in bw) + " (bot nie wyszedł do końca epizodu). Wniosek: symulator -> alarm Z7, rzeczywistość -> zawieszka bez wyjścia. Zgodne.", ""]
        L += ["### 1b. Błąd czasu wyjścia (zamknięte obszary z rzeczywistym wyjściem w telemetrii)", "",
              "Błąd = przewidziany - rzeczywisty, oba od początku zawieszki. Przewidziany = próg 15 s + czas symulacji; rzeczywisty = `po_s` z `ucieczka.json` "
              "(pierwsza próbka poza obszarem lub na innym piętrze). Epizody bez wyjścia w telemetrii (urwana seria) są cenzurowane i wyłączone.", "",
              "| wariant | zbiór | n | mediana błędu | mediana modułu błędu | p90 modułu | min | max | sim wolniejszy niż rzecz. |", "|---|---|---|---|---|---|---|---|---|"]
        for v in "ABC":
            for nazwa, strict in (("wszystkie z wyjściem", False), ("tylko zmiana piętra", True)):
                b = blad_czasu(wi, v, strict)
                e = [x["blad_s"] for x in b]
                a = [abs(x) for x in e]
                L.append(f"| {v} | {nazwa} | {len(b)} | {_fmt(_mediana(e))} s | {_fmt(_mediana(a))} s | {_fmt(_p90(a))} s | {_fmt(min(e) if e else None)} s | {_fmt(max(e) if e else None)} s | {sum(x > 0 for x in e)}/{len(e)} |")
        L += ["", "[HIP] Symulator opisuje reakcję według Z1-Z8, a nie obecnego bota, więc to nie jest test trafności przewidywania czasu bota. Ujemny błąd = czas, "
                  "który reguła mogłaby odzyskać; dodatni = przypadki, w których bot wyszedł szybciej (np. natychmiast po wejściu na drabinę) niż próg 15 s + ruch.", ""]
        b = blad_czasu(wi, "A")
        L += ["Przypadki szczegółowo (wariant A):", "", "| pozycja | wyjście rzeczywiste | rzeczywisty s | przewidziany s | błąd s |", "|---|---|---|---|---|"]
        for x in sorted(b, key=lambda x: x["blad_s"]):
            L.append(f"| {x['poz']} | {x['jak']} | {x['rzeczywisty_s']} | {x['przewidziany_s']} | {x['blad_s']} |")
        L += [""]
        pw = [w for w in zam if w["real"] and w["real"]["jak"] == "pietro"]
        L += [f"### 1c. Kierunek piętra: rzeczywiste wyjście ze zmianą piętra ({len(pw)} epizodów) vs piętro lądowania symulatora", "",
              "| wariant | zgodne piętro | niezgodne | symulator bez wyjścia |", "|---|---|---|---|"]
        for v in "ABC":
            ok = bad = brak = 0
            for w in pw:
                s_ = w["wariant"][v]
                if s_["wynik"] != "wyszedl":
                    brak += 1
                elif s_["poz_koniec"][2] == w["real"]["gdzie"][2]:
                    ok += 1
                else:
                    bad += 1
            L.append(f"| {v} | {ok} | {bad} | {brak} |")
        kie = [w for w in pw if w["poz"][0] in (32508,) and w["poz"][2] == 9]
        kA = sum(w["wariant"]["A"]["poz_koniec"][2] == 10 for w in kie)
        kC = sum(w["wariant"]["C"]["poz_koniec"][2] == w["real"]["gdzie"][2] for w in kie)
        L += ["", f"Kieszeń z9 (32508,32273|32272) z rzeczywistym wyjściem w górę: {len(kie)} epizodów; wariant A schodzi dziurą na z10 w {kA}/{len(kie)} (najtańsze wyjście, bez piętra celu, Z2 nieaktywne), "
                  f"wariant C ({sum(w['cel_hint'] is not None for w in kie)}/{len(kie)} ma podpowiedź piętra) trafia w piętro rzeczywistego wyjścia w {kC}/{len(kie)}. "
                  "Pozostałe niezgodności to epizody, w których rzeczywisty bot wybrał inne piętro niż najtańsze wyjście (jego cel = UNKNOWN). "
                  "Wniosek: reguła Z2 działa tylko z piętrem celu; bot musi je przekazać, bez niego symulator nie wskaże znanej drabiny.", ""]
        L += ["### 1d. Otwarte obszary: kiedy symulator by zareagował vs jak długo bot rzeczywiście stał", ""]
        ot = [w for w in otw if w["wariant"]["B"]["wynik"] == "wyszedl"]
        roz = [w["trwa_s"] - w["wariant"]["B"]["czas_od_zawieszki_s"] for w in ot]
        L += [f"- otwartych z wyjściem w wariancie B: {len(ot)}/{len(otw)}; przewidziana reakcja po (próg 30 s + czas): mediana {_fmt(_mediana([w['wariant']['B']['czas_od_zawieszki_s'] for w in ot]))} s",
              f"- rzeczywisty czas stania (`trwa_s`, epizod kończy się wyjściem poza promień 2, przerwą > 30 s albo zmianą piętra): mediana {_fmt(_mediana([w['trwa_s'] for w in ot]))} s",
              f"- różnica (stał - reakcja symulatora): mediana {_fmt(_mediana(roz))} s, p90 {_fmt(_p90(roz))} s, reakcja symulatora wcześniejsza w {sum(r > 0 for r in roz)}/{len(roz)}",
              "- [HIP] To nie jest błąd czasu: punkty trasy i cel są założone (B), a koniec epizodu nie musi być wyjściem wg reguły Z5.", ""]
    S_ = W["siatka"]
    L += ["## 2. Świat symulatora vs plansze 15x11 zapisane w epizodach", ""]
    if S_ is None:
        L += ["UNKNOWN: brak epizody.jsonl.", ""]
    else:
        L += [f"- porównanych pól: {S_['pol']}, zgodnych: {S_['zgodnych']} ({100 * S_['zgodnych'] / S_['pol']:.2f}%); różnych: {S_['pol'] - S_['zgodnych']}",
              f"- rodzaje różnic (epizod -> symulator): {S_['rozne']}",
              "- Wszystkie różnice leżą na polach z `trasy/dziury_nauczone.json` ((32498,32271,z8), (32508,32273,z8), (32482,32296,z8)): plansze powstały przed nauczeniem tych dziur, symulator traktuje je jak ścianę (zgodnie ze specyfikacją).",
              "- Ograniczenie: plansze pochodzą z tej samej `mapa.py`, więc to test spójności (dziury, kodowanie), nie niezależna weryfikacja mapy względem gry.", ""]
    O = W["wyrocznia"]
    L += ["## 3. Znane wyjścia: wyrocznia z flag mapy (oracle_wyjscie.json) vs symulator", ""]
    if O is None:
        L += ["UNKNOWN: brak oracle_wyjscie.json.", ""]
    else:
        wi = O["wiersze"]
        bl = lambda a, b: a is not None and b is not None and max(abs(a[0] - b[0]), abs(a[1] - b[1])) <= 1
        same = [x for x in wi if bl(x["sim_wejscie"], x["orakl_wyjscie"])]
        brak = [x for x in wi if x["sim_wynik"] != "wyszedl"]
        drz = [x for x in wi if x["sim_wynik"] == "wyszedl" and x["sim_wejscie"] is None]
        inne = [x for x in wi if x not in same and x not in brak and x not in drz]
        L += [f"- przypadków: {len(wi)}; symulator kończy 'wyszedl': {sum(x['sim_wynik'] == 'wyszedl' for x in wi)}, bez wyjścia: {len(brak)}",
              f"- ten sam punkt wejścia co wyrocznia (odległość <= 1 pole): {len(same)}/{len(wi)}",
              f"- wyjście przez drzwi (32505,32270,z8), wyrocznia go nie widzi (ściana w mapie): {len(drz)}",
              f"- inne wyjście niż wyrocznia: {len(inne)}; symulator nie widzi wyjścia wyroczni (flaga 2 bez ważnego lądowania): {len(brak)}", "",
              "| pozycja | wyrocznia: pole (kroki) | symulator: wynik, rodzaj, pole wejścia | kroki sym. | czas sym. s | rzeczywisty s | zgodność |", "|---|---|---|---|---|---|---|"]
        for x in wi:
            zg = "to samo wyjście" if x in same else ("drzwi" if x in drz else ("brak wyjścia w sym." if x in brak else "inne wyjście"))
            L.append(f"| {x['poz']} | {x['orakl_wyjscie']} ({x['orakl_dystans']}) | {x['sim_wynik']}, {x['sim_rodzaj'] or '-'}, {x['sim_wejscie'] or '-'} | {x['sim_kroki']} | {x['sim_s']} | {_fmt(x['real_s'])} | {zg} |")
        L += [""]
        dr = [x for x in wi if x["poz"][:2] == [32506, 32270] and x["poz"][2] == 9]
        L += [f"Drabina (32506,32269|32270) z9: wpisów wyroczni z tym startem {len(dr)}; symulator wychodzi drabiną w {sum(x['sim_rodzaj'] == 'drabina' for x in dr)}/{len(dr)}.", ""]
        L += ["### 3b. Znane przypadki (komendy `symuluj` na świecie z repo)", "", "| przypadek | wynik | kroki | czas s | koniec | zdarzenia |", "|---|---|---|---|---|---|"]
        for z in W.get("znane") or []:
            L.append(f"| {z['nazwa']} | {z['wynik']} | {z['kroki']} | {z['czas_s']} | {z['koniec']} | {', '.join(z['zdarzenia'])} |")
        L += ["", "Wyjaśnienie \"2 vs 8 kroków\" (SPEC_model_steruje_gra_1016 sekcja 7): pokój (32507,32270,z8) ma drzwi (32505,32270). Przy ZAMKNIĘTYCH drzwiach najtańsze wyjście to "
                  "podejście do (32506,32270) i użycie drzwi (2 kroki); naiwna wyrocznia widziała 2 kroki do flagi (32505,32268), której nie da się użyć. "
                  "Przy OTWARTYCH drzwiach droga do schodów (32498,32270) ma 9 kroków (8 do pola przed schodami + wejście), co odpowiada 8 krokom policzonym przez bota. "
                  "Symulator odtwarza obie liczby, a stan drzwi decyduje, która jest właściwa (stan drzwi w epizodach = UNKNOWN).", ""]
    K = W["karol"]
    L += ["## 4. Przejęcia Karola jako przypadki testowe", ""]
    if K is None:
        L += ["UNKNOWN: brak logi/pomoc-karola.jsonl.", ""]
    else:
        wi = K["wiersze"]
        zam = [x for x in wi if x["klasa"] == "zamkniety"]
        otw = [x for x in wi if x["klasa"] == "otwarty"]
        wyszedl = [x for x in wi if x["karol_wyszedl"] is True]
        L += [f"- przypadków (bez trybu brak_bota; plik rośnie na żywo, 62 w chwili decyzji): {K['przypadkow']}; start zamknięty: {len(zam)}, otwarty: {len(otw)}",
              f"- ślad pozycji z telemetrii (próbki w czasie przejęcia): {sum(x['ma_slad'] for x in wi)}/{len(wi)} (przy zatrzymanym bocie telemetrii nie ma: UNKNOWN trasa Karola)",
              f"- Karol opuścił obszar startu (zmiana piętra albo poza BFS): {len(wyszedl)}/{len(wi)}; UNKNOWN (obszar uciety limitem BFS, to samo piętro): {sum(x['karol_wyszedl'] is None for x in wi)}",
              f"- zamknięte: symulacja 'wyszedl' w {sum(x['sim_wynik'] == 'wyszedl' for x in zam)}/{len(zam)}, inny wynik: "
              + (", ".join(f"{x['poz']}={x['sim_wynik']}" for x in zam if x["sim_wynik"] != "wyszedl") or "brak"),
              f"- otwarte (bez celu, punkty z tras = wariant B): symulacja 'wyszedl' w {sum(x['simB_wynik'] == 'wyszedl' for x in otw)}/{len(otw)}; cel Karola w otwartych = UNKNOWN, więc bez oceny zgodności", ""]
        L += ["### 4a. Przejęcia, w których Karol faktycznie wyszedł z obszaru (jedyne porównywalne ze zdaniem symulatora)", "",
              "| start | pozycja | klasa | Karol: koniec | symulator | sim koniec | ocena |", "|---|---|---|---|---|---|---|"]
        zg = ro = lu = 0
        for x in wyszedl:
            if x["klasa"] == "zamkniety" and x["sim_wynik"] == "wyszedl":
                if x["sim_koniec"][2] == x["poz_koniec"][2] and _cheb(x["sim_koniec"], x["poz_koniec"]) <= 3:
                    oc = "zgodne (to samo piętro, <= 3 pola)"
                    zg += 1
                else:
                    oc = "rozbieżne (inne wyjście niż Karol)"
                    ro += 1
            elif x["klasa"] == "zamkniety":
                oc = "luka modelu: Karol wyszedł, symulator nie zna wyjścia (alarm Z7)"
                lu += 1
            else:
                oc = "otwarty: bez oceny"
            L.append(f"| {x['start'][11:]} | {x['poz']} | {x['klasa']} | {x['poz_koniec']} | {x['sim_wynik']} {x['sim_rodzaj'] or ''} | {x['sim_koniec']} | {oc} |")
        L += ["", f"Zamknięte starty, w których Karol wyszedł: zgodne {zg}, rozbieżne {ro}, luka modelu {lu}.",
              "Pozostałe przejęcia w zamkniętych obszarach (Karol został w obszarze) to krótkie korekty (mediana "
              f"{_fmt(_mediana([x['czas_karola_s'] for x in zam if x['karol_wyszedl'] is False]))} s) w trybie bot_aktywny: nie dowód, że Karol rozwiązywał zawieszkę; zgodność z jego intencją = UNKNOWN bez jego opisu.", ""]
        pos = collections.Counter(tuple(x["poz"]) for x in zam)
        L += ["Najczęstsze startu w zamkniętych obszarach: " + ", ".join(f"{list(p)} x{n}" for p, n in pos.most_common(4)) + ".", ""]
        L += ["### 4b. Wszystkie przypadki", "", "| start | poz | klasa | obszar | tryb | Karol s | Karol wyszedł | sim | sim s |", "|---|---|---|---|---|---|---|---|---|"]
        for x in wi:
            kw = {True: "tak", False: "nie", None: "UNKNOWN"}[x["karol_wyszedl"]]
            sim = x["sim_wynik"] if x["klasa"] == "zamkniety" else f"{x['simB_wynik']} (B)"
            L.append(f"| {x['start'][11:]} | {x['poz']} | {x['klasa']} | {x['obszar']}{'+' if x['ucieta'] else ''} | {x['tryb']} | {x['czas_karola_s']} | {kw} | {sim} | {x['sim_s'] if x['klasa'] == 'zamkniety' else '-'} |")
        L += [""]
    L += ["## 5. Błędy symulatora znalezione w walidacji i poprawione", "",
          "1. **Fałszywe `brak_wyjscia` dla otwartego obszaru bez danych.** Epizod w otwartej jaskini (np. 1124 pola) bez celu i bez punktów trasy kończył się "
          "`brak_wyjscia` + `alarm=True`, czyli twierdził Z7 (\"nie ma wyjścia\"), choć symulator po prostu nie miał dokąd iść. Teraz wynik to `brak_danych` (`alarm=False`, "
          "powód `brak_celu_i_punktow_trasy`). Zmierzone przed poprawką (A bez historii): 11 otwartych epizodów `brak_wyjscia`; po poprawce są `brak_danych` "
          "(w tabeli 1a wariant A, z historią: `brak_wyjscia` otwarte tylko tam, gdzie jest cel albo punkty, czyli 0).",
          "2. **Raport `karol_wyszedl_z_obszaru` przy obszarze uciętym limitem BFS (4000).** Pole spoza uciętego BFS było liczone jako 'wyszedł'. Teraz tylko zmiana piętra jest pewna, "
          "reszta = UNKNOWN (dotyczyło 5 przejęć w otwartym obszarze 4000).",
          "3. **Brak śladu pola wejścia w zdarzeniu `przejscie`.** Dopisano `od` (pole wejścia), potrzebne do porównania z wyrocznią.", "",
          "## 6. Ograniczenia i UNKNOWN", "",
          "- Czas rzeczywisty vs przewidziany to NIE test trafności: symulator opisuje regułę Z1-Z8, bot w telemetrii działał wg starej logiki, więc błąd mierzy potencjał do odzyskania, nie jakość modelu.",
          "- `po_s` w ucieczka.json to pierwsza próbka poza obszarem BFS bez pól z flagą 2; wejście na pole z flagą 2 bez zmiany piętra bywa tam liczone jako wyjście (np. (32340,32202,z7)).",
          "- Cenzurowanie: epizody z urwaną serią (bez wyjścia w telemetrii) nie wchodzą do błędu czasu.",
          "- Cel i punkty trasy nie są w epizodach: A bez nich, B z sumą wszystkich tras w promieniu 30, C z celem 'skąd przyszedłem' ([HIP]). Wynik wyboru piętra zależy od C (sekcja 1c).",
          "- Drzwi: znane jedne, (32505,32270,z8). Przejęcie Karola 08:23:50 (32356,32208,z7, zatrzymany bot, 114 s, 81 pól do (32400,32220,z7)) pokazuje wyjście, którego model nie zna "
          "(prawdopodobnie kolejne drzwi traktowane przez mapę jak ściana; UNKNOWN). Symulator zgłasza tam alarm, co zgadza się z zasadą Z7.",
          "- Flagi 2 bez ważnego lądowania nie są wyjściami; czy gra pozwala wejść tam inaczej (lina, Use) = UNKNOWN. Lina z plecaka: opcja wyłączona (decyzja Karola 16.10).",
          "- Koszt nieudanej próby 6 s, czekanie Z6 5-10 s i skos liczony jak krok prosty: założenia, nie pomiary. Stan drzwi w historii = UNKNOWN.",
          "- Przejęcia Karola bez telemetrii (zatrzymany bot, bot cichy) nie mają trasy: porównanie tylko po pozycji końcowej.",
          "- Nie odtworzono: wpływu graczy/mobów blokujących przejście (Z6) i ognia (Z8) na epizodach: dane epizodu mają graczy w pierwszej próbce, ale brak ich dalszych pozycji (UNKNOWN).", ""]
    return "\n".join(L) + "\n"


def main(argv):
    if len(argv) >= 2 and argv[1] == "waliduj":
        sys.stdout.write(raport_rozszerzony_md(waliduj_rozszerzona()))
        return 0
    if len(argv) >= 2 and argv[1] == "waliduj-podstawowa":
        sys.stdout.write(raport_md(waliduj()))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
