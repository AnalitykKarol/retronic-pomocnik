#!/usr/bin/env python3
"""Serwis w mieście (Edron, 19.10): wymiana gold, depo, jedzenie, backpack, blanki i wyjście, jednym skryptem.

  python3 -I serwis.py edron [--kroki bank,depo,jedzenie,backpack,blanki,wyjscie] [--na-sucho] [--bez-stop]

Kolejność kroków jest w `trasy/serwis_<miasto>.json` ("kolejnosc") albo w `--kroki`. Chodzenie: A* po piętrze
(wyprawa.Trasownik) i łączniki pięter z nagrania Karola (laczniki); akcje na żywo (UI plecaków, rozmowa z NPC, depo)
są w serwis_akcje.py. Każdy krok jest weryfikowany po plecaku; porażka = SerwisBlad (alarm + STOP), nic nie zgadujemy.
`--na-sucho`: tylko plan dróg od bieżącej pozycji (odczyt pozycji, zero inputu do gry).
"""
import argparse
import heapq
import json
import os
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

KATALOG = Path(__file__).resolve().parent
TRASY = KATALOG / "trasy"
KOSZT_LACZNIKA = 6.0                    # w "polach": przejście piętra

from serwis_blad import SerwisBlad, cheb  # noqa: E402


def wczytaj(miasto, katalog=TRASY):
    plik = Path(katalog) / f"serwis_{miasto}.json"
    try:
        dane = json.loads(plik.read_text())
    except (OSError, ValueError) as e:
        raise SerwisBlad("start", f"brak danych serwisu {plik} ({e})")
    for k in ("przystanki", "laczniki", "kolejnosc"):
        if k not in dane:
            raise SerwisBlad("start", f"dane serwisu bez pola {k!r}")
    return dane


class Planer:
    """Droga między dowolnymi dwoma polami: odcinki na jednym piętrze z A*, przejścia pięter tylko po łącznikach z nagrania.

    Odcinek A* liczy się tylko wtedy, gdy cała jego droga leży na jednym piętrze (graf mapy bywa niepełny co do schodów,
    a łączniki z nagrania są sprawdzone na żywo). Dijkstra po węzłach: start, cel i końce łączników."""

    def __init__(self, trasownik, laczniki):
        self.tr = trasownik
        self.lacz = [(tuple(l["z"]), tuple(l["do"])) for l in laczniki]
        self._cache = {}

    def _odcinek(self, a, b):
        """Punkty a..b po jednym piętrze (A*) albo None."""
        if a == b:
            return [a]
        klucz = (a, b)
        if klucz not in self._cache:
            o = self.tr.odcinek(a, b) if a[2] == b[2] else None
            if o is not None and any(p[2] != a[2] for p in o):
                o = None
            self._cache[klucz] = o
        return self._cache[klucz]

    def droga(self, od, do):
        """Lista punktów od `od` do `do` (z punktami zmiany pięter jako kolejne pozycje o innym z) albo None."""
        od, do = tuple(od), tuple(do)
        if od == do:
            return [od]
        wezly = {od, do}
        for a, b in self.lacz:
            wezly.add(a)
            wezly.add(b)
        wyjscie = {}                      # a -> [b]
        for a, b in self.lacz:
            wyjscie.setdefault(a, []).append(b)
        d, skad = {od: 0.0}, {od: None}
        pq = [(0.0, od)]
        while pq:
            c, p = heapq.heappop(pq)
            if c > d.get(p, 1 << 60):
                continue
            if p == do:
                break
            for b in wyjscie.get(p, ()):
                nc = c + KOSZT_LACZNIKA
                if nc < d.get(b, 1 << 60):
                    d[b], skad[b] = nc, (p, None)
                    heapq.heappush(pq, (nc, b))
            for q in wezly:
                if q == p or q[2] != p[2]:
                    continue
                o = self._odcinek(p, q)
                if o is None:
                    continue
                nc = c + sum(cheb(x, y) for x, y in zip(o, o[1:]))
                if nc < d.get(q, 1 << 60):
                    d[q], skad[q] = nc, (p, o)
                    heapq.heappush(pq, (nc, q))
        if do not in skad:
            return None
        odcinki, q = [], do
        while skad[q] is not None:
            p, o = skad[q]
            odcinki.append(o if o is not None else [q])    # łącznik: samo pole docelowe
            q = p
        wynik = [od]
        for o in reversed(odcinki):
            wynik.extend(o[1:] if o and o[0] == wynik[-1] else o)
        return wynik


def plecak_ilosc(plecak, ids):
    """Suma sztuk przedmiotów o ID z `ids` w odczycie plecaka ({"id": {id: ilosc}}) albo None, gdy odczytu brak."""
    if plecak is None:
        return None
    return sum(v for k, v in plecak.get("id", {}).items() if k in ids)


class Serwis:
    """Orkiestrator kroków. `akcje` = obiekt z metodami z serwis_akcje.AkcjeZywe (w testach atrapa); `chodz(punkty)` -> bool."""

    def __init__(self, dane, akcje, planer, pozycja, chodz, log=print, cele=None, spij=time.sleep, stan_plik=None,
                 teraz=time.time):
        self.d = dane
        self.stan_plik = Path(stan_plik) if stan_plik else None
        self.teraz = teraz
        self.akcje = akcje
        self.planer = planer
        self.pozycja = pozycja
        self.chodz = chodz
        self.log = log
        self.spij = spij
        self.cele = dict({"ham": 5, "blanki": 20, "platinum_zostaw": 3}, **(cele or {}))
        self.wynik = {}

    # --- chodzenie -----------------------------------------------------------------------------

    def _idz(self, krok, cel, tolerancja=0):
        """Dojście do `cel` (tolerancja w polach; domyślnie dokładnie na polu stania, bo NPC mówią tylko z kilku pól).
        Niepowodzenie (ucieczka, niskie HP, gracz na polu) = SerwisBlad: nie próbujemy po cichu innych miejsc."""
        poz = tuple(self.pozycja())
        droga = self.planer.droga(poz, tuple(cel))
        if droga is None:
            raise SerwisBlad(krok, f"brak drogi z {poz} do {tuple(cel)}")
        self.log(f"serwis[{krok}]: idę {poz} -> {tuple(cel)} ({len(droga)} pkt, piętra {sorted({p[2] for p in droga})})")
        if len(droga) > 1 and not self.chodz(droga, tolerancja):
            raise SerwisBlad(krok, f"nie doszedłem do {tuple(cel)} (stoję w {tuple(self.pozycja())})")

    def plan(self, kroki, od=None):
        """[(krok, cel, liczba punktów)] od `od` (bez inputu do gry); None w liczbie = brak drogi."""
        poz = tuple(od or self.pozycja())
        wynik = []
        for k in kroki:
            for cel in self._cele_kroku(k):
                d = self.planer.droga(poz, cel)
                wynik.append((k, cel, None if d is None else len(d)))
                if d is not None:
                    poz = cel
                break
        return wynik

    def _cele_kroku(self, krok):
        if krok == "depo":
            return [tuple(s) for s in self.d.get("depo_stoiska", [])] or [tuple(self.d["przystanki"]["depo"]["stoi"])]
        if krok == "wyjscie":
            return [tuple(self.d["wyjscie"])]
        return [tuple(self.d["przystanki"][krok]["stoi"])]

    # --- kroki ---------------------------------------------------------------------------------

    # --- stan (wznawianie po awarii) -------------------------------------------------------------

    def _stan_czytaj(self):
        try:
            d = json.loads(self.stan_plik.read_text())
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError, AttributeError):
            return {}

    def _stan_zapisz(self, **d):
        if self.stan_plik is None:
            return
        try:
            self.stan_plik.write_text(json.dumps(d, ensure_ascii=False))
        except OSError:
            pass

    def _koszt(self, kroki):
        """Szacowany koszt zakupów w gp (z zapasem: ham 10, backpack 20, blanki 10 za sztukę). Gdy depo jeszcze przed nami,
        bag z runami i jego blanki zaraz znikną z plecaka, więc liczymy zakup baga i pełnego celu blanków."""
        depo_przed = "depo" in kroki
        k = 0
        if "jedzenie" in kroki:
            k += 10 * self.akcje.brakuje("ham", self.cele["ham"])
        if "backpack" in kroki:
            k += 20 * (1 if depo_przed else self.akcje.brakuje("backpack", 1))
        if "blanki" in kroki:
            k += 10 * (self.cele["blanki"] if depo_przed else self.akcje.brakuje("blank rune", self.cele["blanki"]))
        return k

    def _kontrola_budzetu(self, kroki, ukonczone):
        """Zanim cokolwiek kupimy: czy stać nas na kolejkę (po złożeniu w depo zostaje 3 platinum + reszta poniżej 100 gold)."""
        kroki_do_zrobienia = [k for k in kroki if k not in ukonczone]
        koszt = self._koszt(kroki_do_zrobienia)
        depo_przed = "depo" in kroki_do_zrobienia
        majatek = self.akcje.majatek(tylko_glowny=depo_przed)       # pieniądze w bagu na runy odejdą z nim do depo
        zostaje = majatek
        if depo_przed:
            zostaje = min(majatek, 100 * self.cele["platinum_zostaw"] + majatek % 100)
        if zostaje < koszt:
            raise SerwisBlad("start", f"za mało pieniędzy: po depo zostanie {zostaje} gp, kolejka kosztuje ok. {koszt} gp "
                                      f"(majątek {majatek} gp)")
        self.log(f"serwis: budżet ok (majątek {majatek} gp, po depo {zostaje} gp, koszt ok. {koszt} gp)")

    def uruchom(self, kroki=None, od_nowa=False):
        """Wykonuje kroki po kolei. Gdy poprzedni przebieg przerwał się błędem (do 3 h temu, bez względu na listę kroków),
        kroki już zakończone są pomijane: ponowne uruchomienie nie kupuje drugi raz i nie odkłada nowego baga do depo.
        Przebieg jest „zakończony”, gdy ukończono wszystkie kroki domyślnej kolejności; `od_nowa` ignoruje stan."""
        kroki = list(kroki or self.d["kolejnosc"])
        nieznane = [k for k in kroki if k not in self.d["przystanki"] and k != "wyjscie"]
        if nieznane:
            raise SerwisBlad("start", f"nieznane kroki {nieznane}")
        stan = {} if od_nowa else self._stan_czytaj()
        wznow = bool(stan) and not stan.get("koniec") and self.teraz() - stan.get("t", 0) < 3 * 3600
        ukonczone = [k for k in stan.get("ukonczone", []) if k != "wyjscie"] if wznow else []
        if ukonczone:
            self.log(f"serwis: wznawiam przerwany przebieg, już wykonane: {ukonczone}")
        self.akcje.sprawdz_start()
        self.akcje.przygotuj_okna()
        self._kontrola_budzetu(kroki, ukonczone)

        def zapisz():
            pelny = set(self.d["kolejnosc"]) - {"wyjscie"} <= set(ukonczone)
            self._stan_zapisz(ukonczone=ukonczone, koniec=pelny, t=self.teraz())

        zapisz()
        for k in kroki:
            if k in ukonczone:
                self.log(f"serwis: krok {k} już wykonany, pomijam")
                self.wynik[k] = "pominięty"
                continue
            self.log(f"serwis: krok {k}")
            getattr(self, "_krok_" + k)()
            self.wynik[k] = "ok"
            if k != "wyjscie":
                ukonczone.append(k)
            zapisz()
        self.log(f"serwis: koniec {self.wynik}")
        return self.wynik

    def _krok_bank(self):
        self._idz("bank", self.d["przystanki"]["bank"]["stoi"])
        self.akcje.bank_zmien(self.d["przystanki"]["bank"]["npc"])

    def _krok_depo(self):
        """Najbliższe wolne stanowisko przy skrzyni depo (liczone po długości drogi od bieżącej pozycji). Zajęte stanowisko
        i skrzynia, która się nie otworzyła, przechodzą do następnego; błąd chodzenia kończy serwis (STOP)."""
        poz = tuple(self.pozycja())
        koszty = []
        for st in self._cele_kroku("depo"):
            dr = self.planer.droga(poz, st)
            if dr is not None:
                koszty.append((sum(cheb(a, b) for a, b in zip(dr, dr[1:])), st))
        if not koszty:
            raise SerwisBlad("depo", f"brak drogi do żadnego stanowiska depo z {poz}")
        for _koszt, stoisko in sorted(koszty):
            if self.akcje.pole_zajete(stoisko):
                self.log(f"serwis[depo]: stanowisko {stoisko} zajęte, następne")
                continue
            self._idz("depo", stoisko, tolerancja=0)
            if self.akcje.depo_zloz(zostaw_platinum=self.cele["platinum_zostaw"]):
                return
            self.log(f"serwis[depo]: skrzynia przy {stoisko} się nie otworzyła, następne stanowisko")
        raise SerwisBlad("depo", "wszystkie stanowiska zajęte albo skrzynie się nie otworzyły")

    def _krok_jedzenie(self):
        s = self.d["przystanki"]["jedzenie"]
        self._idz("jedzenie", s["stoi"])
        self.akcje.kup(s["npc"], "ham", self.cele["ham"])

    def _krok_backpack(self):
        s = self.d["przystanki"]["backpack"]
        if not self.akcje.potrzeba_baga():
            self.log("serwis[backpack]: bag na runy już jest, nie kupuję")
            return
        self._idz("backpack", s["stoi"])
        self.akcje.kup(s["npc"], "backpack", 1)
        self.akcje.przygotuj_okna()        # nowy bag staje się osobnym oknem, zanim kupione blanki trafią do plecaka

    def _krok_blanki(self):
        s = self.d["przystanki"]["blanki"]
        self.akcje.przygotuj_okna()
        brak = self.akcje.brakuje("blank rune", self.cele["blanki"])
        if brak > 0 and self.akcje.wolne_w_bagu() < brak:
            raise SerwisBlad("blanki", f"w bagu na runy jest miejsce na {self.akcje.wolne_w_bagu()} blanków, a brakuje {brak}: "
                                       "najpierw krok backpack (albo zrób miejsce), nic nie kupiłem")
        self._idz("blanki", s["stoi"])
        self.akcje.kup(s["npc"], "blank rune", self.cele["blanki"])
        self.akcje.przenies_blanki()
        self.akcje.przygotuj_okna()

    def _krok_wyjscie(self):
        self._idz("wyjscie", self.d["wyjscie"], tolerancja=2)    # tu dokładność nie ma znaczenia: uruchom.sh liczy dojście od pozycji


def powiadom(tytul, tresc):
    """Dymek na pulpicie (jak nagraj_trase.py); brak notify-send nie przeszkadza."""
    import subprocess
    try:
        subprocess.run(["notify-send", "-a", "Retronic", tytul, tresc], timeout=3, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        pass


# --- CLI ---------------------------------------------------------------------------------------

def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def pola_schodow(mp, a, zb, promien=3):
    """Pola schodów (flaga 2 na obu piętrach, chodliwe) w promieniu `promien` od wejścia `a`: krok na takie pole zmienia piętro."""
    za, wyn = a[2], []
    for dx in range(-promien, promien + 1):
        for dy in range(-promien, promien + 1):
            x, y = a[0] + dx, a[1] + dy
            f, g = int(mp.flagi(x, y, za)), int(mp.flagi(x, y, zb))
            if f & 1 and f & 2 and not f & 4 and g & 2 and not g & 4:
                wyn.append((x, y, za))
    return wyn


def pola_startowe(mp, T):
    """Chodliwe pola obok schodu T (ortogonalnie, nie będące schodem) z kierunkiem strzałki na T."""
    wyn = []
    for dx, dy, kier in ((0, -1, "Down"), (0, 1, "Up"), (-1, 0, "Right"), (1, 0, "Left")):
        x, y = T[0] + dx, T[1] + dy
        f = int(mp.flagi(x, y, T[2]))
        if f & 1 and not f & 4 and not f & 2:
            wyn.append(((x, y, T[2]), kier))
    return wyn


def przejdz_schody(postac, mp, akcje, chodz1, a, zb, maks_s=90.0, log=print):
    """Przejście pięter schodami z wejścia `a` na piętro `zb`. Wybiera pole schodu i stronę wejścia, które są wolne
    (gracze stoją przy schodach i na nich), a po nieudanej próbie bierze inne. True = jesteśmy na `zb`, False = nie
    wyszło w limicie czasu, None = brak schodów na mapie przy `a` (wołający używa starego chodzika)."""
    t0, nieudane = time.time(), {}
    ostatni_log = None
    while time.time() - t0 < maks_s:
        poz = tuple(postac.pozycja())
        if poz[2] == zb:
            return True
        if poz[2] != a[2]:
            return False
        schody = pola_schodow(mp, a, zb)
        if not schody:
            return None
        zajete = {(s["x"], s["y"]) for s in akcje._stwory()
                  if s.get("z") == poz[2] and s.get("x") is not None and s.get("nazwa") != akcje.nick}
        opcje = []
        for T in schody:
            if (T[0], T[1]) in zajete:
                continue
            for S, kier in pola_startowe(mp, T):
                if (S[0], S[1]) not in zajete or (S[0], S[1]) == (poz[0], poz[1]):
                    opcje.append((nieudane.get((S, T), 0), _cheb(S, poz), S, T, kier))
        if not opcje:
            if ostatni_log != "zajete":
                log(f"schody z{poz[2]} -> z{zb}: wszystkie pola przy schodach zajęte, czekam")
                ostatni_log = "zajete"
            time.sleep(1.5)
            continue
        _, _, S, T, kier = min(opcje, key=lambda o: o[:2])
        klucz = (S, T)
        log(f"schody z{poz[2]} -> z{zb}: pole {T[:2]}, wejście z {S[:2]} (strzałka {kier}), nieudane próby: {nieudane.get(klucz, 0)}")
        if (poz[0], poz[1]) != (S[0], S[1]):
            chodz1([S], 0)
            poz = tuple(postac.pozycja())
            if (poz[0], poz[1]) != (S[0], S[1]):
                nieudane[klucz] = nieudane.get(klucz, 0) + 1
                continue
        if akcje.pole_zajete(T):
            nieudane[klucz] = nieudane.get(klucz, 0) + 1
            time.sleep(1.0)
            continue
        postac.krok(kier)
        time.sleep(0.8)
        poz = tuple(postac.pozycja())
        if poz[2] == zb:
            log(f"schody: przeszedłem na z{zb}, stoję w {poz}")
            return True
        nieudane[klucz] = nieudane.get(klucz, 0) + 1
        log(f"schody: krok {kier} z {S[:2]} bez przejścia (stoję w {poz})")
    return False


def idz_krokami(postac, tr, cel, tolerancja=0, maks_zlych=5, log=print):
    """Rezerwa, gdy chodzik (kliki w mapę) kończy trasę bez dojścia do celu: ścieżka A* po jednym piętrze i krok po kroku
    strzałkami (po skosie numpadem), z kontrolą pozycji po każdym kroku. True = stoimy w `tolerancja` pól od celu."""
    cel = tuple(cel)
    poz = tuple(postac.pozycja())
    if poz[2] != cel[2]:
        return False
    sciezka = tr.odcinek(poz, cel)
    if not sciezka:
        log(f"serwis: brak ścieżki A* z {poz} do {cel}")
        return False
    log(f"serwis: chodzik nie doszedł, idę krokami z {poz} do {cel}: {sciezka}")
    klawisz = {(0, -1): "Up", (0, 1): "Down", (-1, 0): "Left", (1, 0): "Right"}
    zle = 0
    for p in sciezka[1:]:
        while True:
            poz = tuple(postac.pozycja())
            if poz[2] != cel[2]:
                return False
            if (poz[0], poz[1]) == (p[0], p[1]):
                break
            dx = (p[0] > poz[0]) - (p[0] < poz[0])
            dy = (p[1] > poz[1]) - (p[1] < poz[1])
            if dx and dy:                       # skos numpadem bywa bez skutku: najpierw krok w poziomie, potem w pionie
                dy = 0 if (zle % 2 == 0) else dy
                dx = dx if dy == 0 else 0
            nowa = postac.krok(klawisz[(dx, dy)])
            if nowa is not None and (nowa[0], nowa[1]) == (poz[0] + dx, poz[1] + dy):
                zle = 0                         # liczymy tylko kolejne nieudane kroki
            else:
                zle += 1
                log(f"serwis: krok ({dx},{dy}) z {poz[:2]} bez skutku ({zle}/{maks_zlych})")
                if zle >= maks_zlych:
                    return False
                time.sleep(0.6)
    poz = tuple(postac.pozycja())
    return poz[2] == cel[2] and _cheb(poz, cel) <= tolerancja


def idz_pewnie(postac, mp, akcje, cel, tolerancja=0, maks_s=150.0, log=print, unik=()):
    """Marsz po kafelkach na jednym piętrze, bez chodzika mozg (ten ma ~20 s inicjalizacji na odcinek i kończy trasy
    jednopunktowe od razu): BFS po polach chodliwych mapy (bez schodów i dziur poza celem), omija pola zajęte przez innych
    graczy/stwory i pola, na których krok się nie udał (zdejmowane po kilku sekundach), jeden krok strzałką, kontrola
    pozycji. Gdy cały dojazd zablokowany przez ludzi, czeka i planuje od nowa. True = stoimy w `tolerancja` pól od celu,
    False = brak planu (nieznane pola mapy) albo przekroczony czas."""
    import heapq
    cel = tuple(cel)
    klawisz = {(0, -1): "Up", (0, 1): "Down", (-1, 0): "Left", (1, 0): "Right"}
    zablok, t0, ost_log = {}, time.monotonic(), 0.0

    unik = {tuple(u)[:2] for u in unik if tuple(u)[2] == cel[2]}

    def koszt(x, y, z):
        """None = nie wchodzimy; 1 = zwykłe pole; 6 = pole z flagą 2 (na mapie to bywa szum, ale może być przejście pięter)."""
        if (x, y) == (cel[0], cel[1]):
            return 1.0
        f = mp.flagi(x, y, z)
        if not (f & 1) or (f & 4) or (x, y) in unik:
            return None
        return 6.0 if f & 2 else 1.0

    while time.monotonic() - t0 < maks_s:
        poz = tuple(postac.pozycja())
        if poz[2] != cel[2]:
            return False
        if _cheb(poz, cel) <= tolerancja:
            return True
        teraz = time.monotonic()
        try:
            zajete = {(q.get("x"), q.get("y")) for q in akcje._stwory() if q.get("z") == poz[2] and q.get("nazwa") != akcje.nick}
        except Exception:
            zajete = set()
        zajete |= {pole for pole, do in zablok.items() if do > teraz}
        zajete.discard((poz[0], poz[1]))
        skad, d = {(poz[0], poz[1]): None}, {(poz[0], poz[1]): 0.0}
        kol, meta = [(0.0, (poz[0], poz[1]))], None
        marg = 8
        xmin, xmax = min(poz[0], cel[0]) - marg, max(poz[0], cel[0]) + marg
        ymin, ymax = min(poz[1], cel[1]) - marg, max(poz[1], cel[1]) + marg
        while kol:
            cc, c = heapq.heappop(kol)
            if cc > d.get(c, 1e18):
                continue
            if max(abs(c[0] - cel[0]), abs(c[1] - cel[1])) <= tolerancja:
                meta = c
                break
            for dx, dy in klawisz:
                q = (c[0] + dx, c[1] + dy)
                if not (xmin <= q[0] <= xmax and ymin <= q[1] <= ymax) or q in zajete:
                    continue
                k = koszt(q[0], q[1], poz[2])
                if k is None:
                    continue
                if cc + k < d.get(q, 1e18):
                    d[q] = cc + k
                    skad[q] = c
                    heapq.heappush(kol, (cc + k, q))
        if meta is None:
            if teraz - ost_log > 8:
                log(f"serwis: brak drogi z {poz[:2]} do {cel[:2]} (ludzie na drodze albo nieznane pola), czekam")
                ost_log = teraz
            if not zajete and not zablok:
                return False                      # nic nie blokuje, a drogi nie ma: mapa nie zna pól
            time.sleep(1.0)
            continue
        sciezka = []
        while meta is not None:
            sciezka.append(meta)
            meta = skad[meta]
        sciezka.reverse()
        nast = sciezka[1]
        d = (nast[0] - poz[0], nast[1] - poz[1])
        nowa = postac.krok(klawisz[d])
        if nowa is not None and nowa[2] != poz[2]:
            log(f"serwis: krok na {nast} zmienił piętro ({poz[2]} -> {nowa[2]})")
            return False
        if nowa is None or (nowa[0], nowa[1]) != nast:
            zablok[nast] = time.monotonic() + 5.0
            time.sleep(0.3)
    return False


def _czekaj_na_ekran_gry(maks_s=45.0, wzorzec=(1175, 910)):
    """Po starcie sesji podgląd ma rozmiar okna (np. 1498x1820), a zrzut takiego ekranu trwa dłużej niż limit grim.
    dopasuj_okno przestawia sesję na 1175x910 w skali 1 dopiero, gdy widzi działający serwis.py, więc czekamy tu."""
    import ekran
    t0 = time.time()
    while time.time() - t0 < maks_s:
        try:
            szer, wys = ekran.zrzut().size                  # wychodzi 1174x910 (parzyste wymiary RFB), stąd tolerancja
            if abs(szer - wzorzec[0]) <= 2 and abs(wys - wzorzec[1]) <= 2:
                return True
        except Exception:
            pass
        time.sleep(1.5)
    print(f"serwis: ekran sesji nie ma rozmiaru {wzorzec} po {maks_s:.0f} s, idę dalej", flush=True)
    return False


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("miasto", choices=["edron"])
    p.add_argument("--kroki", help="lista kroków po przecinku (domyślnie z pliku danych)")
    p.add_argument("--na-sucho", action="store_true", help="tylko plan dróg, bez inputu do gry")
    p.add_argument("--od", help="x,y,z: plan na sucho z tego pola zamiast z bieżącej pozycji")
    p.add_argument("--bez-stop", action="store_true", help="po błędzie nie zapisuj pliku STOP")
    p.add_argument("--od-nowa", action="store_true", help="ignoruj stan poprzedniego przerwanego przebiegu (zrób wszystkie kroki)")
    a = p.parse_args(argv)
    import bot
    import mapa as mapa_mod
    import wyprawa
    dane = wczytaj(a.miasto)
    postac = bot.Postac()
    mp = mapa_mod.mapa()
    planer = Planer(wyprawa.Trasownik(mp), dane["laczniki"])
    kroki = a.kroki.split(",") if a.kroki else None
    if a.na_sucho:
        s = Serwis(dane, None, planer, postac.pozycja, None)
        od = tuple(int(v) for v in a.od.split(",")) if a.od else None
        for k, cel, n in s.plan(kroki or dane["kolejnosc"], od=od):
            print(f"{k:10s} -> {cel}  {'BRAK DROGI' if n is None else str(n) + ' pkt'}")
        return 0
    import serwis_akcje
    _czekaj_na_ekran_gry()
    akcje = serwis_akcje.AkcjeZywe(postac, log=print)

    def chodz_proste(punkty, tolerancja=0):
        import mozg
        cel = tuple(punkty[-1])
        if tuple(postac.pozycja())[2] == cel[2] and idz_pewnie(postac, mp, akcje, cel, tolerancja, log=print,
                                                              unik=[p for l in planer.lacz for p in l]):
            return True
        return mozg.przejdz_dojscie(postac, punkty, prog_hp=40, jedzenie=None, potwory=None, graczy=True,
                                    stop_przy_graczach=False, tolerancja=tolerancja, proby=4)

    def chodz(punkty, tolerancja=0):
        """Trasa z przejściami pięter: dojście do okolicy schodów, przejście własnym kodem (wiele pól i stron wejścia,
        omija zajęte przez graczy), reszta trasy na nowym piętrze. Bez schodów na mapie: stary chodzik na całości."""
        punkty = [tuple(p) for p in punkty]
        j = next((i for i in range(1, len(punkty)) if punkty[i][2] != punkty[i - 1][2]), None)
        if j is None:
            return chodz_proste(punkty, tolerancja) or idz_krokami(postac, planer.tr, punkty[-1], tolerancja)
        a, zb = punkty[j - 1], punkty[j][2]
        chodz_proste(punkty[:j], 3)
        r = przejdz_schody(postac, mp, akcje, lambda pts, tol: chodz_proste(pts, tol), a, zb)
        if r is None:
            return chodz_proste(punkty, tolerancja) or idz_krokami(postac, planer.tr, punkty[-1], tolerancja)
        return bool(r) and chodz(punkty[j:], tolerancja)

    import instancja
    s = Serwis(dane, akcje, planer, postac.pozycja, chodz, log=print, stan_plik=instancja.S.stan / "serwis_stan.json")
    try:
        s.uruchom(kroki, od_nowa=a.od_nowa)
        powiadom("Serwis: gotowe", "Kroki: " + ", ".join(f"{k}={v}" for k, v in s.wynik.items()))
    except Exception as e:                   # SerwisBlad i wszystko inne (Zatrzymano, IndexError...): zawsze STOP i dymek
        krok = getattr(e, "krok", "?")
        powod = getattr(e, "powod", repr(e))
        print(f"SERWIS: PORAŻKA w kroku {krok}: {powod}", flush=True)
        powiadom("Serwis: porażka", f"Krok {krok}: {powod}")
        if not a.bez_stop:
            try:
                instancja.S.stop.write_text(f"serwis: {krok}: {powod}\n")
            except Exception:
                pass
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
