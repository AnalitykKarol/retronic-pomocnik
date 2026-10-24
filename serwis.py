#!/usr/bin/env python3
"""Serwis w mieście (Edron 19.10, Thais 21.10): wymiana gold, depo, jedzenie, backpack, blanki i wyjście, jednym skryptem.

  python3 -I serwis.py [edron|thais|auto] [--kroki bank,depo,jedzenie,backpack,blanki,wyjscie] [--na-sucho] [--bez-stop]

Miasto = plik `trasy/serwis_<miasto>.json`; bez argumentu edron (jak dotąd), `auto` = miasto z bieżącej pozycji postaci
(panel.miasto_pozycji; z `--na-sucho --od x,y,z` z podanego pola). Bez argumentu: miasto z pozycji postaci, gdy stoi w mieście
z planem (Thais), inaczej edron (jak dotąd). Kroki z polem `drzwi` w danych (Thais: Frodo, Xodet) serwis przechodzi przez zamknięte
drzwi własnym marszem (22.10): stoi przed drzwiami, czeka na stojącą pozycję, krok, Use, krok (`przejdz_drzwi`); brak otwarcia
po DRZWI_PROB próbach = SerwisBlad. `--pomin-brakujace`: kroki, których miasto nie ma (bank w Thais), są pomijane z notatką
(używa tego refill.sh), bez tej flagi nieznany krok to błąd startu.

Kolejność kroków jest w `trasy/serwis_<miasto>.json` ("kolejnosc") albo w `--kroki`. Chodzenie: A* po piętrze
(wyprawa.Trasownik) i łączniki pięter z nagrania Karola (laczniki); akcje na żywo (UI plecaków, rozmowa z NPC, depo)
są w serwis_akcje.py. Każdy krok jest weryfikowany po plecaku; porażka = SerwisBlad (alarm + STOP), nic nie zgadujemy.
`--na-sucho`: tylko plan dróg od bieżącej pozycji (odczyt pozycji, zero inputu do gry).
"""
import argparse
import heapq
import json
import os
import random
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

KATALOG = Path(__file__).resolve().parent
TRASY = KATALOG / "trasy"
KOSZT_LACZNIKA = 6.0                    # w "polach": przejście piętra
DRZWI_PROB = 4                          # tyle prób przejścia przez jedne drzwi (krok, krok, Use + krok, krok), potem SerwisBlad; 24.10: było 3
DRZWI_CZEKAJ_S = (0.6, 1.0)             # po Use czekamy, aż drzwi się otworzą (jak wypad._drzwi)
SKLADOWA_MAKS_POL = 400000              # zalew spójności większy niż to = nie odrzucamy pary (A* sam zdecyduje)
DRZWI_SPOKOJ_S = 0.4                    # odstęp dwóch odczytów pozycji „postać stoi” (jak cavebot._drzwi_spokoj)

import marsz_klik  # noqa: E402
from serwis_blad import BrakOdpowiedziNpc, SerwisBlad, cheb  # noqa: E402

# 23.10 (decyzja Karola ~11:00: „niech on próbuje pisać, jeśli nie ma przejścia”): gdy serwis nie może wejść na pole stania przy NPC
# (pole zajęte, brak drogi, marsz utknął) albo NPC odszedł, rozmawia z miejsca w zasięgu NPC. Zasięg = odległość Czebyszewa na tym
# samym piętrze. Wartość 3 z polecenia Karola (Tibia 7.x: NPC słyszy z kilku pól; w repo NIE MA zmierzonej wartości, są tylko pola
# stania 1-2 pola od NPC, np. Frodo 2). Do zmierzenia na żywo: z jakiej odległości Frodo odpowiada na „hi”; przy mniejszej wartości
# zmień tylko tę stałą. Wybierając pole do podejścia preferujemy pola nie dalej niż ZASIEG_PREFEROWANY od NPC (margines na błąd stałej).
ZASIEG_ROZMOWY = 3
ZASIEG_PREFEROWANY = 2
MAKS_POL_DO_ZASIEGU = 3                 # tyle różnych pól w zasięgu NPC serwis próbuje, zanim odda oryginalny błąd
NPC_WIDOK_X, NPC_WIDOK_Y = 7, 5         # widok mapy klienta (±7 x ±5 pól): dalej lista stworów NPC nie zawiera
_DOSC = {"cel": None, "fn": None}       # hak marszu: patrz dosc_marszu


class dosc_marszu:
    """Kontekst: dla marszu `idz_pewnie` do pola `cel` (x, y, z) zajęte albo zablokowane pole docelowe nie każe czekać, tylko pyta
    `fn(poz)` (23.10, rozmowa z NPC z miejsca): True = z `poz` NPC jest w zasięgu rozmowy, marsz kończy się sukcesem; False = NPC jest
    poza zasięgiem, marsz kończy się od razu porażką (powód w stan["utkniecie"]), serwis szuka innego pola; None = nie wiadomo
    (NPC niewidoczny), czekanie jak dotąd. Bez kontekstu (inne użycia idz_pewnie) nic się nie zmienia."""

    def __init__(self, cel, fn):
        self.cel, self.fn, self.poprzedni = tuple(cel), fn, None

    def __enter__(self):
        self.poprzedni = dict(_DOSC)
        _DOSC.update(cel=self.cel, fn=self.fn)
        return self

    def __exit__(self, *_):
        _DOSC.update(self.poprzedni)
        return False


def miasta(katalog=TRASY):
    """Miasta z planem serwisu: nazwy plików trasy/serwis_<miasto>.json (bez pomocniczych serwis_stan itp.)."""
    return sorted(p.stem[len("serwis_"):] for p in Path(katalog).glob("serwis_*.json"))


def wybierz_miasto(arg, poz=None, katalog=TRASY):
    """Nazwa miasta do serwisu: `arg` z wiersza poleceń albo przy "auto" miasto z pozycji `poz` (x, y, z).
    Bez argumentu (None; 22.10 Karol: refill ma działać w każdym mieście z planem): miasto z pozycji, gdy postać stoi w mieście
    z planem serwisu, inaczej edron (jak dotąd: Edron startuje też z jaskini czy z z5). Jawne miasto, a postać w INNYM mieście
    z planem = błąd startu. SerwisBlad, gdy miasta nie ma wśród planów albo przy "auto" pozycja nie leży w żadnym z nich."""
    if arg is None:
        if poz is not None:
            import panel  # noqa: PLC0415
            miasto, _w_depo = panel.miasto_pozycji(tuple(poz), panel.dane_serwisu(katalog))
            if miasto is not None:
                return miasto
        arg = "edron"
    if arg != "auto":
        if arg not in miasta(katalog):
            raise SerwisBlad("start", f"brak planu serwisu dla miasta {arg!r} (są: {', '.join(miasta(katalog))})")
        if poz is not None:
            # 21.10 (checker K3): guzik paska "Refill" w Thais wołał serwis Edronu; A* szukał drogi 20 s i kończył STOP-em.
            # Pozycja w INNYM mieście z planem = od razu błąd startu, bez ruchu. Poza miastami jak dotąd.
            import panel  # noqa: PLC0415
            inne, _w_depo = panel.miasto_pozycji(tuple(poz), panel.dane_serwisu(katalog))
            if inne is not None and inne != arg:
                raise SerwisBlad("start", f"postać jest w mieście {inne!r} {tuple(poz)}, a serwis zlecony dla {arg!r}")
        return arg
    if poz is None:
        raise SerwisBlad("start", "auto: nieznana pozycja postaci")
    import panel  # noqa: PLC0415
    miasto, _w_depo = panel.miasto_pozycji(tuple(poz), panel.dane_serwisu(katalog))
    if miasto is None:
        raise SerwisBlad("start", f"auto: pozycja {tuple(poz)} nie leży w żadnym mieście z planem serwisu ({', '.join(miasta(katalog))})")
    return miasto


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


def drzwi_miasta(dane):
    """Wszystkie pola drzwi z pola `drzwi` przystanków planu (Thais: Frodo, Xodet) jako krotki (x, y, z), bez powtórzeń."""
    wynik = []
    for p in dane.get("przystanki", {}).values():
        for h in p.get("drzwi") or []:
            h = tuple(int(v) for v in h)
            if h not in wynik:
                wynik.append(h)
    return wynik


def boki_drzwi(mapa, h):
    """Dwa pola po obu stronach drzwi `h` w jednej osi: (przed, za) albo None. Oba chodliwe (mapa widzi sam kafelek drzwi jako
    ścianę), a pola prostopadłe do osi to ściana (drzwi w murze). Frodo: oś x (32364|32366, 32208), Xodet: oś y (32400, 32216|32218)."""
    h = tuple(h)
    wolne = []
    for dx, dy in ((1, 0), (0, 1)):
        a, b = (h[0] - dx, h[1] - dy, h[2]), (h[0] + dx, h[1] + dy, h[2])
        if all(int(mapa.flagi(*q)) & 1 and not int(mapa.flagi(*q)) & 4 for q in (a, b)):
            bok = [(h[0] + dy, h[1] + dx, h[2]), (h[0] - dy, h[1] - dx, h[2])]
            w_murze = all(not (int(mapa.flagi(*q)) & 1) or int(mapa.flagi(*q)) & 4 for q in bok)
            wolne.append((w_murze, (a, b)))
    if not wolne:
        return None
    return sorted(wolne, key=lambda w: not w[0])[0][1]


class Planer:
    """Droga między dowolnymi dwoma polami: odcinki na jednym piętrze z A*, przejścia pięter tylko po łącznikach z nagrania.

    Odcinek A* liczy się tylko wtedy, gdy cała jego droga leży na jednym piętrze (graf mapy bywa niepełny co do schodów,
    a łączniki z nagrania są sprawdzone na żywo). Dijkstra po węzłach: start, cel i końce łączników.

    `drzwi` + `mapa` (22.10, Thais): zamknięte drzwi sklepów to dla A* ściana, więc każde drzwi to dwie krawędzie między polami
    po ich obu stronach (koszt 2); droga przez nie zawiera pole drzwi jako zwykły punkt [... przed, drzwi, za ...]. Marsz dzieli ją
    na tym punkcie (`podziel_na_drzwiach`). Drzwi NIE są łącznikami (`self.lacz` idzie do marszu jako pola do omijania)."""

    def __init__(self, trasownik, laczniki, drzwi=(), mapa=None):
        self.tr = trasownik
        self.lacz = [(tuple(l["z"]), tuple(l["do"])) for l in laczniki]
        self._cache = {}
        self._sklad = {}                    # pole -> numer składowej spójności (zalew, patrz _ta_sama_skladowa)
        self.drzwi = {}                     # pole drzwi -> (przed, za)
        for h in drzwi:
            h = tuple(int(v) for v in h)
            boki = boki_drzwi(mapa, h) if mapa is not None else None
            if boki is None:
                raise SerwisBlad("start", f"drzwi {h} nie mają po obu stronach pola do stania (mapa?)")
            self.drzwi[h] = boki

    def _ta_sama_skladowa(self, a, b):
        """Szybkie odrzucenie par pól bez drogi po jednym piętrze: zalew po polach, po których chodzi A* (Graf.idzie, te same ruchy),
        liczony raz na składową. A* z pola odciętego drzwiami przeszukiwałby całą mapę (ok. 3 s na parę, z drzwiami ponad 10 s na
        trasę), a odpowiedź to i tak None. True = nie wiadomo albo jest w tej samej składowej (wtedy decyduje A*)."""
        graf = getattr(self.tr, "graf", None)
        ruchy = getattr(getattr(self.tr, "g", None), "RUCHY", None)
        if graf is None or ruchy is None or not self.drzwi:
            return True
        for pole in (a, b):
            if pole not in self._sklad:
                if not graf.idzie(*pole):
                    return True                                  # pole poza grafem (np. schody): niech rozstrzygnie A*
                id_ = len(self._sklad) + 1
                kol, widziane = [pole], {pole}
                while kol and len(widziane) <= SKLADOWA_MAKS_POL:
                    x, y, z = kol.pop()
                    for dx, dy, _c in ruchy:
                        q = (x + dx, y + dy, z)
                        if q not in widziane and graf.idzie(*q):
                            widziane.add(q)
                            kol.append(q)
                if kol:                                          # zalew za duży: nie wiemy, nie odrzucamy
                    return True
                for q in widziane:
                    self._sklad[q] = id_
        return self._sklad[a] == self._sklad[b]

    def _mapa(self):
        graf = getattr(self.tr, "graf", None)
        return getattr(graf, "m", None)

    def _schody(self, pole):
        """True = pole chodliwe z flagą 2 (schody, rampa, dziura): krok na nie zmienia piętro. W obrębie jednego piętra nieprzechodnie
        (A* w Graf.idzie też je pomija); wyjątek robią tylko łączniki planu (`self.lacz`). Brak mapy = False."""
        mp = self._mapa()
        if mp is None:
            return False
        return pole_schodow_lub_dziur(mp, pole[0], pole[1], pole[2])

    def _odcinek_czysty(self, p, q):
        """Prosty odcinek p->q (w osi albo po przekątnej) bez pola, na które nie wolno wejść; inny kształt = False (marsz ma
        iść po sąsiednich polach, a nie po linii „na oko” przez róg ściany albo schodów). Brak grafu = True (atrapy)."""
        graf = getattr(self.tr, "graf", None)
        if graf is None:
            return True
        dx, dy = q[0] - p[0], q[1] - p[1]
        if dx and dy and abs(dx) != abs(dy):
            return False
        d = max(abs(dx), abs(dy))
        sx, sy = (dx > 0) - (dx < 0), (dy > 0) - (dy < 0)
        return all(graf.idzie(p[0] + sx * i, p[1] + sy * i, p[2]) for i in range(1, d))

    def _zagesc(self, o):
        """Rzadkie punkty odcinka A* (`Trasownik.odcinek` przerzedza drogę co 3. pole) mogą ciąć róg ściany albo pole schodów: marsz
        idzie wtedy wprost między punktami. Każdy nieczysty odcinek zastępujemy gęstą ścieżką A* (pole po polu)."""
        graf = getattr(self.tr, "graf", None)
        if graf is None or len(o) < 2:
            return o
        wynik = [o[0]]
        for p, q in zip(o, o[1:]):
            if self._odcinek_czysty(p, q):
                wynik.append(q)
                continue
            gesta = graf.astar(p, q)
            if gesta is None:
                return None
            wynik.extend(tuple(x) for x, _t in gesta[1:])
        return wynik

    def _odcinek(self, a, b):
        """Punkty a..b po jednym piętrze (A*) albo None."""
        if a == b:
            return [a]
        klucz = (a, b)
        if klucz not in self._cache:
            o = self.tr.odcinek(a, b) if a[2] == b[2] and self._ta_sama_skladowa(a, b) else None
            if o is not None and any(p[2] != a[2] for p in o):
                o = None
            if o is not None:
                o = self._zagesc(o)
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
        przez_drzwi = {}                  # a -> [(drzwi, b)]: krok przez drzwi w obie strony
        for h, (a, b) in self.drzwi.items():
            wezly.add(a)
            wezly.add(b)
            przez_drzwi.setdefault(a, []).append((h, b))
            przez_drzwi.setdefault(b, []).append((h, a))
            if od == h:                   # stoimy na kafelku drzwi: obie strony o krok
                przez_drzwi.setdefault(od, []).extend([(h, a), (h, b)])
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
            for h, b in przez_drzwi.get(p, ()):
                nc = c + 2.0
                if p == h:
                    o = [p, b]
                    nc = c + 1.0
                else:
                    o = [p, h, b]
                if nc < d.get(b, 1 << 60):
                    d[b], skad[b] = nc, (p, o)
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
        if self._schody_na_drodze(wynik):
            return None
        return wynik

    def _schody_na_drodze(self, droga):
        """True, gdy droga w obrębie jednego piętra prowadzi przez pole schodów/dziury, które nie jest zamierzonym przejściem planu
        (początek i koniec drogi oraz pola łączników są dozwolone). Pole ze zmianą piętra w drodze (łącznik) nie liczy się."""
        dozwolone = {tuple(droga[0]), tuple(droga[-1])}
        for a, b in self.lacz:
            dozwolone.update((a, b))
        for i, p in enumerate(droga):
            p = tuple(p)
            if p in dozwolone:
                continue
            ma_pietro = (i > 0 and droga[i - 1][2] != p[2]) or (i + 1 < len(droga) and droga[i + 1][2] != p[2])
            if not ma_pietro and self._schody(p):
                return True
        return False


def plecak_ilosc(plecak, ids):
    """Suma sztuk przedmiotów o ID z `ids` w odczycie plecaka ({"id": {id: ilosc}}) albo None, gdy odczytu brak."""
    if plecak is None:
        return None
    return sum(v for k, v in plecak.get("id", {}).items() if k in ids)


ID_BLANK_RUNY = 3147     # blank rune (jak serwis_akcje.ID_BLANK)

# kroki, których wynik cofa depo (odkłada bag z runami razem z blankami); przy wznawianiu oceniane na nowo (Serwis._stan_zmieniony)
KROKI_ZALEZNE_OD_DEPO = ("backpack", "blanki")

# krok wirtualny (bez przystanku w danych miasta): wyprawa tylko po cap (refill_auto.KROKI_CAP = "bank,cap,wyjscie"); 24.10
KROKI_WIRTUALNE = ("cap",)

# 24.10 (invincible/gebelish/dawajkesh: kupione 5 ham zjadło cap, łupu z huntu nie było gdzie nosić). Pokrętła z na_zywo.json instancji
# (serwis nie ładuje pokrętł cavebota, jak RATUNEK_HAIKU); 0 = dawne zachowanie. Zakresy i opis: pokretla.ZAKRESY.
POKRETLA_SERWISU = {
    "SERWIS_CAP_NA_LOOT": 50,     # oz capa, które zostaje wolne po zakupie ham (rezerwa na łup) i do którego krok `cap` odkłada nadmiar
    "SERWIS_HAM_MIN": 2,          # tyle ham najmniej kupujemy, gdy postać nie ma jedzenia (jeśli cap pozwala), nawet gdy rezerwa każe 0
    "SERWIS_CAP_DEPO_LOOT": 0,    # 1 = krok `cap` odkłada do depo ciężki łup-sprzęt (DO POTWIERDZENIA KAROLA, domyślnie wyłączone)
}
_CELE_STARE = {"cap_na_loot": 0, "ham_min": 0, "cap_depo_loot": 0}      # domyślne w Serwis(): atrapy i testy = jak dotąd
_KLUCZE_CELE = {"SERWIS_CAP_NA_LOOT": "cap_na_loot", "SERWIS_HAM_MIN": "ham_min", "SERWIS_CAP_DEPO_LOOT": "cap_depo_loot"}


def pokretla_serwisu(plik=None):
    """{cap_na_loot, ham_min, cap_depo_loot} z na_zywo.json (domyślne POKRETLA_SERWISU; brak pliku albo śmieć w polu =
    domyślna wartość tego pola, nigdy wyjątek). Wartość ujemna = 0."""
    nz = {}
    try:
        if plik is None:
            import instancja  # noqa: PLC0415
            plik = instancja.S.na_zywo
        nz = json.loads(Path(plik).read_text())
        nz = nz if isinstance(nz, dict) else {}
    except (OSError, ValueError, TypeError, AttributeError, ImportError):
        nz = {}
    wynik = {}
    for k, nazwa in _KLUCZE_CELE.items():
        try:
            v = float(nz.get(k, POKRETLA_SERWISU[k]))
            v = v if v == v else POKRETLA_SERWISU[k]
        except (TypeError, ValueError):
            v = POKRETLA_SERWISU[k]
        wynik[nazwa] = max(0, int(v))
    return wynik


class Serwis:
    """Orkiestrator kroków. `akcje` = obiekt z metodami z serwis_akcje.AkcjeZywe (w testach atrapa); `chodz(punkty)` -> bool."""

    def __init__(self, dane, akcje, planer, pozycja, chodz, log=print, cele=None, spij=time.sleep, stan_plik=None,
                 teraz=time.time, obsluga_drzwi=None):
        self.d = dane
        # None = serwis przechodzi przez drzwi, gdy planer je zna (Planer(drzwi=...)); marsz `chodz` musi je wtedy obsłużyć
        self.obsluga_drzwi = bool(getattr(planer, "drzwi", None)) if obsluga_drzwi is None else bool(obsluga_drzwi)
        self.stan_plik = Path(stan_plik) if stan_plik else None
        self.teraz = teraz
        self.akcje = akcje
        self.planer = planer
        self.pozycja = pozycja
        self.chodz = chodz
        self.log = log
        self.spij = spij
        self.cele = {"ham": 5, "blanki": 20, "platinum_zostaw": 3, **_CELE_STARE, **(cele or {})}
        self.wynik = {}
        self.kroki_przebiegu = []

    # Drzwi sklepów (Thais: Frodo, Xodet) mapa widzi jako ścianę. Planer bez drzwi (`Planer(drzwi=...)`) ich nie przejdzie: krok z polem
    # "drzwi" w danych jest wtedy odrzucany PRZED pierwszym ruchem i inputem (inaczej A* przeszukiwałby minutami całą mapę, a potem
    # i tak zgłosił brak drogi). Z drzwiami w planerze marsz otwiera je sam (przejdz_drzwi, 22.10).
    obsluga_drzwi = False

    def _za_drzwiami(self, krok):
        return [] if self.obsluga_drzwi else (self.d["przystanki"].get(krok) or {}).get("drzwi") or []

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

    # --- rozmowa z NPC z miejsca (23.10, decyzja Karola) ---------------------------------------------

    def _stwory(self):
        """Lista stworów z akcji (puste, gdy akcje jej nie mają albo odczyt zawiódł: wtedy nic nie zgadujemy)."""
        f = getattr(self.akcje, "_stwory", None)
        if f is None:
            return []
        try:
            return list(f())
        except Exception:
            return []

    def _poz_npc(self, npc, z, od=None):
        """Widoczna bieżąca pozycja NPC `npc` na piętrze `z` (lista stworów klienta, NPC chodzą), najbliższa `od`, albo None."""
        wiersze = [(q["x"], q["y"], q["z"]) for q in self._stwory()
                   if (q.get("nazwa") or "").casefold() == npc.casefold() and q.get("z") == z
                   and q.get("x") is not None and q.get("y") is not None and not q.get("gracz")]
        if not wiersze:
            return None
        return min(wiersze, key=lambda p: cheb(p, od) if od else 0)

    def _npc_znany(self, przyst, poz):
        """Gdzie jest NPC kroku: widoczny na liście stworów albo, gdy `poz` jest poza widokiem klienta (lista go wtedy nie zawiera),
        pozycja z danych (`npc_poz`). Z bliska bez NPC na liście = None (nie zgadujemy: zachowanie jak dotąd)."""
        n = self._poz_npc(przyst["npc"], poz[2], poz)
        if n is not None:
            return n
        d = przyst.get("npc_poz")
        if d and tuple(d)[2] == poz[2] and (abs(d[0] - poz[0]) > NPC_WIDOK_X or abs(d[1] - poz[1]) > NPC_WIDOK_Y):
            return tuple(d)
        return None

    @staticmethod
    def _w_zasiegu(poz, npc_poz):
        return poz[2] == npc_poz[2] and cheb(poz, npc_poz) <= ZASIEG_ROZMOWY

    def _idz_z_hakiem(self, krok, cel, przyst):
        """`_idz` do `cel`, a gdy pole `cel` jest zajęte/zablokowane, marsz nie czeka: kończy od razu, jeśli NPC jest w zasięgu rozmowy
        (sukces), albo gdy jest poza nim (porażka)."""
        def hak(poz):
            n = self._npc_znany(przyst, tuple(poz))
            return None if n is None else self._w_zasiegu(tuple(poz), n)
        with dosc_marszu(cel, hak):
            self._idz(krok, cel)

    def _pole_w_zasiegu(self, npc_poz, poz, wyklucz=()):
        """Najbliższe postaci wolne pole w zasięgu rozmowy z NPC stojącym w `npc_poz` (z preferencją pól do ZASIEG_PREFEROWANY od NPC),
        do którego planer zna drogę, albo None. Pomija pola zajęte (gracze, stwory, sam NPC), schody/dziury i już próbowane."""
        zajete = {(q.get("x"), q.get("y")) for q in self._stwory()
                  if q.get("z") == npc_poz[2] and q.get("nazwa") != getattr(self.akcje, "nick", None) and not q.get("widmo")}
        schody = getattr(self.planer, "_schody", lambda _p: False)
        kand = []
        for dx in range(-ZASIEG_ROZMOWY, ZASIEG_ROZMOWY + 1):
            for dy in range(-ZASIEG_ROZMOWY, ZASIEG_ROZMOWY + 1):
                p = (npc_poz[0] + dx, npc_poz[1] + dy, npc_poz[2])
                if p[:2] == tuple(npc_poz[:2]) or p[:2] in zajete or p in wyklucz:
                    continue
                kand.append((cheb(p, npc_poz) > ZASIEG_PREFEROWANY, cheb(poz, p) if poz[2] == p[2] else 99,
                             abs(p[0] - poz[0]) + abs(p[1] - poz[1]), cheb(p, npc_poz), p))
        for *_k, p in sorted(kand)[:8]:
            if schody(p):
                continue
            if self.planer.droga(poz, p) is not None:
                return p
        return None

    def _do_zasiegu_npc(self, krok, przyst, npc_poz, blad):
        """Postać stoi poza zasięgiem NPC, który jest w `npc_poz`: idzie na najbliższe wolne pole w jego zasięgu (do
        MAKS_POL_DO_ZASIEGU pól, każde z tym samym hakiem „zajęte pole, ale NPC w zasięgu”). Nic z tego = `blad` (oryginalny)."""
        wyklucz = set()
        for _ in range(MAKS_POL_DO_ZASIEGU):
            poz = tuple(self.pozycja())
            pole = self._pole_w_zasiegu(npc_poz, poz, wyklucz)
            if pole is None:
                break
            wyklucz.add(pole)
            self.log(f"serwis[{krok}]: NPC {przyst['npc']} w {npc_poz[:2]}, poza zasięgiem rozmowy ({ZASIEG_ROZMOWY}) z {poz[:2]}: "
                     f"idę na pole {pole[:2]} w jego zasięgu (decyzja Karola 23.10: próbuję rozmowy zamiast czekać)")
            try:
                self._idz_z_hakiem(krok, pole, przyst)
                return
            except SerwisBlad as e:
                if e.krok not in (krok, "marsz"):
                    raise
            poz = tuple(self.pozycja())
            n = self._npc_znany(przyst, poz)
            if n is not None:
                npc_poz = n
                if self._w_zasiegu(poz, n):
                    return
        raise blad

    def _idz_npc(self, krok, przyst):
        """Dojście do pola stania przy NPC (23.10). Zwykły przypadek bez zmian (`_idz` na pole stania, tolerancja 0). Gdy się nie udaje
        (pole zajęte/zablokowane, brak drogi, marsz utknął, timeout), a NPC jest w zasięgu rozmowy z miejsca, w którym stoimy, rozmowa
        zaczyna się od razu; gdy NPC jest widoczny poza zasięgiem, serwis idzie na najbliższe wolne pole w jego zasięgu. NPC niewidoczny
        (z bliska) albo brak takiego pola = oryginalny błąd. Inne porażki (drzwi, STOP, ucieczka) nie są łagodzone."""
        cel = tuple(przyst["stoi"])
        try:
            self._idz_z_hakiem(krok, cel, przyst)
            return
        except SerwisBlad as e:
            if e.krok not in (krok, "marsz"):
                raise
            blad = e
        poz = tuple(self.pozycja())
        n = self._npc_znany(przyst, poz)
        if n is None:
            raise blad
        if self._w_zasiegu(poz, n):
            self.log(f"serwis[{krok}]: nie doszedłem na pole stania {cel[:2]} ({blad.powod}), ale NPC {przyst['npc']} jest w zasięgu rozmowy "
                     f"({n[:2]}, odl. {cheb(poz, n)}): rozmawiam z miejsca {poz[:2]} (decyzja Karola 23.10)")
            return
        self._do_zasiegu_npc(krok, przyst, n, blad)

    def _rozmowa(self, krok, przyst, f):
        """Rozmowa z NPC (`f` = kup/bank_zmien). NPC, który nie odpowiada na `hi`, a stoi teraz poza zasięgiem (odszedł), dostaje JEDNĄ
        ponowną próbę po podejściu do jego nowej pozycji (23.10). NPC w zasięgu albo niewidoczny: błąd jak dotąd."""
        try:
            return f()
        except BrakOdpowiedziNpc as e:
            poz = tuple(self.pozycja())
            n = self._poz_npc(przyst["npc"], poz[2], poz)
            if n is None or self._w_zasiegu(poz, n):
                raise
            self.log(f"serwis[{krok}]: {przyst['npc']} nie odpowiada na hi, a stoi teraz w {n[:2]} (poza zasięgiem z {poz[:2]}): "
                     f"podchodzę i próbuję jeszcze raz (jedna próba, 23.10)")
            self._do_zasiegu_npc(krok, przyst, n, e)
            return f()

    def plan(self, kroki, od=None):
        """[(krok, cel, liczba punktów)] od `od` (bez inputu do gry); None w liczbie = brak drogi."""
        poz = tuple(od or self.pozycja())
        wynik = []
        for k in kroki:
            if self._za_drzwiami(k):
                wynik.append((k, self._cele_kroku(k)[0], None))      # za drzwiami: brak drogi, planer nie liczy
                continue
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
        if krok == "cap":
            return self._cele_kroku("depo")           # krok wirtualny: odkłada nadmiar w depo (w planie liczymy dojście do skrzyni)
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
        elif "cap" in kroki and self.cele["ham_min"] > 0:
            k += 10 * self.akcje.brakuje("ham", min(self.cele["ham_min"], self.cele["ham"]))        # krok `cap` może dokupić minimum jedzenia
        if "backpack" in kroki:
            k += 20 * (1 if depo_przed else self.akcje.brakuje("backpack", 1))
        if "blanki" in kroki:
            if depo_przed:
                # depo zabierze blanki z baga na runy; te luzem w plecaku zostają i nie wymagają zakupu (22.10 wydra: nie żądaj
                # pieniędzy na to, czego nie trzeba kupować); atrapa bez odczytu = pełny cel jak dotąd
                luzem = getattr(self.akcje, "ilosc_w_plecaku", lambda _ids: 0)({ID_BLANK_RUNY})
                k += 10 * max(0, self.cele["blanki"] - luzem)
            else:
                k += 10 * self.akcje.brakuje("blank rune", self.cele["blanki"])
        return k

    def _kontrola_budzetu(self, kroki, ukonczone):
        """Zanim cokolwiek kupimy: czy stać nas na kolejkę (po złożeniu w depo zostaje 3 platinum + reszta poniżej 100 gold)."""
        kroki_do_zrobienia = [k for k in kroki if k not in ukonczone]
        koszt = self._koszt(kroki_do_zrobienia)
        depo_przed = "depo" in kroki_do_zrobienia
        majatek = self.akcje.majatek(tylko_glowny=depo_przed)       # pieniądze w bagu na runy odejdą z nim do depo
        zostaje = majatek
        if depo_przed:
            # monety ze slotu ekwipunku depo zostawia w całości; platinum ponad „zostaw” odkłada tylko z plecaka
            ekw = getattr(self.akcje, "majatek_w_ekwipunku", lambda: 0)()
            plecak = majatek - ekw
            zostaje = min(plecak, 100 * self.cele["platinum_zostaw"] + plecak % 100) + ekw
        if zostaje < koszt:
            raise SerwisBlad("start", f"za mało pieniędzy: po depo zostanie {zostaje} gp, kolejka kosztuje ok. {koszt} gp "
                                      f"(majątek {majatek} gp)")
        self.log(f"serwis: budżet ok (majątek {majatek} gp, po depo {zostaje} gp, koszt ok. {koszt} gp)")

    def uruchom(self, kroki=None, od_nowa=False, pomin_brakujace=False):
        """Wykonuje kroki po kolei. Gdy poprzedni przebieg przerwał się błędem (do 3 h temu, bez względu na listę kroków),
        kroki już zakończone są pomijane: ponowne uruchomienie nie kupuje drugi raz i nie odkłada nowego baga do depo.
        Przebieg jest „zakończony”, gdy ukończono wszystkie kroki domyślnej kolejności; `od_nowa` ignoruje stan.
        `pomin_brakujace`: kroki, których miasto nie ma w danych (Thais nie ma kroku bank), są pomijane z wpisem w logu zamiast
        błędu startu (refill zleca jedną listę kroków dla każdego miasta)."""
        kroki = list(kroki or self.d["kolejnosc"])
        nieznane = [k for k in kroki if k not in self.d["przystanki"] and k != "wyjscie" and k not in KROKI_WIRTUALNE]
        if nieznane and pomin_brakujace:
            self.log(f"serwis: miasto nie ma kroków {nieznane}, pomijam je")
            kroki = [k for k in kroki if k not in nieznane]
            nieznane = []
        self.kroki_przebiegu = kroki
        if nieznane:
            raise SerwisBlad("start", f"nieznane kroki {nieznane}")
        za_drzwiami = {k: self._za_drzwiami(k) for k in kroki if self._za_drzwiami(k)}
        if za_drzwiami:
            raise SerwisBlad("start", f"kroki za drzwiami sklepu {za_drzwiami}: serwis nie otwiera drzwi, nic nie ruszone "
                                      "(usuń je z --kroki; SPEC_serwis_thais_1021, część Drzwi)")
        stan = {} if od_nowa else self._stan_czytaj()
        wznow = bool(stan) and not stan.get("koniec") and self.teraz() - stan.get("t", 0) < 3 * 3600
        ukonczone = [k for k in stan.get("ukonczone", []) if k != "wyjscie"] if wznow else []
        if ukonczone:
            self.log(f"serwis: wznawiam przerwany przebieg, już wykonane: {ukonczone}")
        self.akcje.sprawdz_start()
        self.akcje.przygotuj_okna()
        # krok zależny od stanu, który depo jeszcze zmieni (odłoży bag z blankami), liczymy do kosztu jak niezrobiony
        zaleznosc = [k for k in ukonczone if k in KROKI_ZALEZNE_OD_DEPO] if "depo" in kroki and "depo" not in ukonczone else []
        self._kontrola_budzetu(kroki, [k for k in ukonczone if k not in zaleznosc])

        def zapisz():
            pelny = set(self.d["kolejnosc"]) - {"wyjscie"} <= set(ukonczone)
            self._stan_zapisz(ukonczone=ukonczone, koniec=pelny, t=self.teraz())

        zapisz()
        for k in kroki:
            if k in ukonczone and self._stan_zmieniony(k):
                self.log(f"serwis: krok {k} był wykonany, ale stan się zmienił (np. depo odłożyło bag), wykonuję ponownie")
                ukonczone.remove(k)
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

    def _stan_zmieniony(self, k):
        """Czy krok zaliczony w tym lub poprzednim przebiegu znów jest potrzebny, bo zmienił się stan, od którego zależy.
        22.10 invincible: backpack zaliczono bez zakupu (postać miała bag), potem depo odłożyło ten bag i „pomijam” zostawiło
        blanki bez miejsca. Dotyczy kroków, które depo cofa: backpack (bag poszedł do depo) i blanki (leżały w tym bagu).
        Jedzenie zostaje: depo nie rusza ham (tylko bag i platinum). Odczyt ze stanu gry, bez ruchu."""
        if k == "backpack":
            return bool(self.akcje.potrzeba_baga())
        if k == "blanki":
            return self.akcje.brakuje("blank rune", self.cele["blanki"]) > 0
        return False

    def _krok_bank(self):
        s = self.d["przystanki"]["bank"]
        self._idz_npc("bank", s)
        self._rozmowa("bank", s, lambda: self.akcje.bank_zmien(s["npc"]))

    def _krok_depo(self):
        """Najbliższe wolne stanowisko przy skrzyni depo (liczone po długości drogi od bieżącej pozycji). Zajęte stanowisko
        i skrzynia, która się nie otworzyła, przechodzą do następnego; błąd chodzenia kończy serwis (STOP)."""
        self._przy_depo(lambda st: self.akcje.depo_zloz(zostaw_platinum=self.cele["platinum_zostaw"],
                                                         odejdz=lambda: self._odejdz_od_depo(st)))

    def _przy_depo(self, f):
        """Dojście do najbliższego wolnego stanowiska przy skrzyni depo i `f(stoisko)` (True = zrobione, False = skrzynia się nie
        otworzyła -> następne stanowisko). Wspólne dla kroków depo i cap."""
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
            if f(stoisko):
                return
            self.log(f"serwis[depo]: skrzynia przy {stoisko} się nie otworzyła, następne stanowisko")
        raise SerwisBlad("depo", "wszystkie stanowiska zajęte albo skrzynie się nie otworzyły")

    def _odejdz_od_depo(self, stoisko):
        """Krok na najbliższe wolne pole obok stanowiska, z którego jest droga (serwer zamyka depo, gdy odejdziesz od skrzyni)."""
        poz = tuple(self.pozycja())
        for dx, dy in ((0, 1), (-1, 0), (1, 0), (0, -1), (-1, 1), (1, 1), (-1, -1), (1, -1)):
            pole = (stoisko[0] + dx, stoisko[1] + dy, stoisko[2])
            if self.akcje.pole_zajete(pole):
                continue
            dr = self.planer.droga(poz, pole)
            if dr is not None and len(dr) <= 3:
                self.log(f"serwis[depo]: odchodzę od skrzyni na {pole}")
                self._idz("depo", pole, tolerancja=0)
                return
        raise SerwisBlad("depo", f"nie mam gdzie odejść od skrzyni przy {tuple(stoisko)}")

    @staticmethod
    def _kup_kw(przystanek):
        """Argumenty kup() z danych przystanku: `zakup_prefiks` (Thais „buy ”) tylko gdy ustawiony, żeby atrapy i Edron zostały bez zmian."""
        return {"prefiks": przystanek["zakup_prefiks"]} if przystanek.get("zakup_prefiks") else {}

    def _krok_jedzenie(self):
        s = self.d["przystanki"]["jedzenie"]
        self._idz_npc("jedzenie", s)
        cel = self.cele["ham"]
        loot = self.cele["cap_na_loot"]
        if "blanki" in self.kroki_przebiegu or loot > 0:
            # ham nie może zabrać capa bagu z blankami ani miejsca na łup z huntu (24.10: pięć ham po 20 oz zjadło cap do zera)
            rezerwa = loot + (self.akcje.rezerwa_na_blanki(self.cele["blanki"]) if "blanki" in self.kroki_przebiegu else 0)
            cel = self.akcje.cel_ham(cel, rezerwa)
        if self.cele["ham_min"] > 0:
            # bez jedzenia nie idziemy na hunt (odchyd 24.10: 0 ham); minimum ograniczone tylko realnym capem, bez rezerwy
            cel = max(cel, self.akcje.cel_ham(min(self.cele["ham_min"], self.cele["ham"]), 0))
        self._rozmowa("jedzenie", s, lambda: self.akcje.kup(s["npc"], "ham", cel, **self._kup_kw(s)))

    def _krok_cap(self):
        """Krok wirtualny wyprawy tylko po cap (po banku, który zamienia gold na platinum). Ham NIE idzie do depo (korekta Karola
        24.10: na łowisku bot najpierw zjada i wyrzuca jedzenie, wyprawa.py). Tu: (1) gdy SERWIS_CAP_DEPO_LOOT=1 i wolny cap
        < SERWIS_CAP_NA_LOOT, odkłada w depo ciężki łup-sprzęt; (2) gdy ham < SERWIS_HAM_MIN, kupuje to minimum (tyle, ile pozwala
        cap): postać po wyrzuceniu jedzenia nie może zostać bez niczego. Pokrętło 0 wyłącza odpowiednią część."""
        c = self.cele
        stan = getattr(self.akcje, "stan_cap", None)
        if stan is None or (c["cap_na_loot"] <= 0 and c["ham_min"] <= 0):
            self.log("serwis[cap]: wyłączone (SERWIS_CAP_NA_LOOT=0 i SERWIS_HAM_MIN=0), nic nie robię")
            return
        if c["cap_depo_loot"] and c["cap_na_loot"] > 0 and "depo" in self.d["przystanki"]:
            from serwis_akcje import plan_nadmiaru  # noqa: PLC0415
            cap, ham, przedmioty = stan()
            loot = plan_nadmiaru(cap, c["cap_na_loot"], przedmioty)
            self.log(f"serwis[cap]: wolne {cap:.1f} oz (cel {c['cap_na_loot']}), ham {ham}, łupu do depo {len(loot)} szt.")
            if loot:
                self._przy_depo(lambda st: self.akcje.depo_nadmiar(loot, odejdz=lambda: self._odejdz_od_depo(st)))
        if c["ham_min"] <= 0 or "jedzenie" not in self.d["przystanki"]:
            return
        cap, ham, _ = stan()
        cel = self.akcje.cel_ham(min(c["ham_min"], c["ham"]), 0)
        if ham >= c["ham_min"] or cel <= ham:
            self.log(f"serwis[cap]: ham {ham} (minimum {c['ham_min']}, wolne {cap:.1f} oz): nie kupuję")
            return
        if self._za_drzwiami("jedzenie"):
            self.log(f"serwis[cap]: ham {ham} < minimum {c['ham_min']}, ale sklep jest za drzwiami, których serwis tu nie otwiera: nie kupuję")
            return
        s = self.d["przystanki"]["jedzenie"]
        self._idz_npc("jedzenie", s)
        self._rozmowa("jedzenie", s, lambda: self.akcje.kup(s["npc"], "ham", cel, **self._kup_kw(s)))

    def _krok_backpack(self):
        s = self.d["przystanki"]["backpack"]
        if not self.akcje.potrzeba_baga():
            self.log("serwis[backpack]: bag na runy już jest, nie kupuję")
            return
        self._idz_npc("backpack", s)
        self._rozmowa("backpack", s, lambda: self.akcje.kup(s["npc"], "backpack", 1, **self._kup_kw(s)))
        self.akcje.przygotuj_okna()        # nowy bag staje się osobnym oknem, zanim kupione blanki trafią do plecaka

    def _krok_blanki(self):
        s = self.d["przystanki"]["blanki"]
        self.akcje.przygotuj_okna()
        brak = self.akcje.brakuje("blank rune", self.cele["blanki"])
        if brak > 0 and self.akcje.wolne_w_bagu() < brak:
            raise SerwisBlad("blanki", f"w bagu na runy jest miejsce na {self.akcje.wolne_w_bagu()} blanków, a brakuje {brak}: "
                                       "najpierw krok backpack (albo zrób miejsce), nic nie kupiłem")
        self._idz_npc("blanki", s)
        self._rozmowa("blanki", s, lambda: self.akcje.kup(s["npc"], "blank rune", self.cele["blanki"], **self._kup_kw(s)))
        self.akcje.przenies_blanki()
        self.akcje.przygotuj_okna()

    def _krok_wyjscie(self):
        self._idz("wyjscie", self.d["wyjscie"], tolerancja=2)    # tu dokładność nie ma znaczenia: uruchom.sh liczy dojście od pozycji


def powiadom(tytul, tresc, krytyczne=False):
    """Dymek na pulpicie (jak nagraj_trase.py); brak notify-send nie przeszkadza.
    krytyczne=True (porażka serwisu, 22.10) = `-u critical`: przebija tryb nie przeszkadzać, bo postać stoi i czeka na Karola."""
    import subprocess
    try:
        subprocess.run(["notify-send", "-a", "Retronic"] + (["-u", "critical"] if krytyczne else []) + [tytul, tresc],
                       timeout=3, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        pass


# --- CLI ---------------------------------------------------------------------------------------

def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def pole_schodow_lub_dziur(mp, x, y, z):
    """Pole chodliwe z flagą 2 (schody, rampa, dziura): krok na nie zmienia piętro (22.10, wydra Thais: depo). Nie wchodzimy w nie
    „przy okazji” drogi po jednym piętrze, a klik w mapę nie może prowadzić przez prostokąt, w którym takie pole leży."""
    f = int(mp.flagi(x, y, z))
    return bool(f & marsz_klik.FLAGA_CHODLIWE and f & marsz_klik.FLAGA_SCHODY and not f & marsz_klik.FLAGA_BLOK)


def przejscie_pewne_w_prostokacie(mp, a, b, margines=1, wyjatek=()):
    """Jak schody_w_prostokacie, ale tylko PRAWDZIWE przejścia pięter (marsz_klik.przejscie_pewne: kolor 210 albo odpowiednik na z±1);
    dekoracje z flagą 2 bez odpowiednika nie liczą się. Dla kliku w linii prostej (klient idzie prosto, nie skręca w bok)."""
    x0, x1 = sorted((a[0], b[0]))
    y0, y1 = sorted((a[1], b[1]))
    z = a[2]
    for x in range(x0 - margines, x1 + margines + 1):
        for y in range(y0 - margines, y1 + margines + 1):
            if (x, y) not in wyjatek and marsz_klik.przejscie_pewne(mp, x, y, z):
                return True
    return False


def prosty_odcinek(sciezka, maks):
    """Ile początkowych kroków `sciezki` ((x, y, ...) od pozycji postaci) leży w jednej linii (ta sama kolumna albo ten sam wiersz), najwyżej `maks`.
    Klik na koniec takiego odcinka prowadzi klienta prosto: nie ma równorzędnych objazdów po bokach."""
    najlepiej = 0
    for os_ in (0, 1):
        k = 0
        while k < maks and k + 1 < len(sciezka) and sciezka[k + 1][os_] == sciezka[0][os_]:
            k += 1
        najlepiej = max(najlepiej, k)
    return najlepiej


def schody_w_prostokacie(mp, a, b, margines=1, wyjatek=()):
    """True, gdy w prostokącie pól a..b (+ `margines`) na piętrze a[2] leży pole schodów/dziury z `pole_schodow_lub_dziur`. Klient
    prowadzi klik własną drogą po 8 kierunkach (skos przez róg), więc sprawdzamy cały prostokąt, nie tylko pola naszej ścieżki.
    `wyjatek` = pola (x, y), które wolno (cel marszu)."""
    x0, x1 = sorted((a[0], b[0]))
    y0, y1 = sorted((a[1], b[1]))
    z = a[2]
    for x in range(x0 - margines, x1 + margines + 1):
        for y in range(y0 - margines, y1 + margines + 1):
            if (x, y) not in wyjatek and pole_schodow_lub_dziur(mp, x, y, z):
                return True
    return False


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


def fabryka_dojscia_bez_schodow(mp, laczniki=()):
    """Fabryka dla `mozg.przejdz_dojscie` (zapasowy chodzik serwisu): CavebotDojscie, dla którego pola schodów/dziur z mapy (flaga 2)
    są ścianą drogi i kroku (jak nauczone dziury), a klik nie prowadzi przez prostokąt z takim polem. Wcześniej strażnik schodów
    w `Cavebot.krok_do` działał tylko na trasie wielopiętrowej (TRASA_PIETRA=2), a serwis Thais chodzi po jednym piętrze (22.10).
    Dozwolone (zamierzone przejście planu): pola punktów trasy dojścia i końce łączników planu (`laczniki` = [(z, do)]), a dla KLIKU
    także pola schodów w Chebyshev <= 1 od celu dojścia (ostatni punkt trasy): ostatni odcinek do wejścia przy schodach (przejdz_schody, Edron
    (33257,31843,5) -> (33258,31841,5), 22.10 13:24) nie ma innej drogi niż klik klienta po skosie, krok strzałką na samo pole schodów
    zostaje zakazany."""
    import cavebot  # noqa: PLC0415

    konce = {(int(p[0]), int(p[1])) for l in laczniki for p in l}

    class DojscieBezSchodow(cavebot.CavebotDojscie):
        mapa = None     # cavebot.py ustawia self.mapa dopiero po pierwszym _ogien_stale_wczytaj() (bez tego AttributeError w logu)

        def _punkty_xy(self):
            return {(int(p[0]), int(p[1])) for p in (getattr(self, "punkty", None) or [])}

        def _dozwolone_xy(self):
            return self._punkty_xy() | konce

        def _dozwolone_klik_xy(self):
            wyn = set(self._dozwolone_xy())
            punkty = getattr(self, "punkty", None) or []
            if punkty:                       # tylko cel dojścia (wejście przy schodach), nie punkty pośrednie: te mogą leżeć obok obcych schodów
                x, y = int(punkty[-1][0]), int(punkty[-1][1])
                wyn.update((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            return wyn

        def dziura_nauczona(self, pole):
            if super().dziura_nauczona(pole):
                return True
            if len(pole) < 3 or (pole[0], pole[1]) in self._dozwolone_xy():
                return False
            return pole_schodow_lub_dziur(mp, pole[0], pole[1], pole[2])

        def _dziura_na_drodze(self, poz, cel_xy):
            if super()._dziura_na_drodze(poz, cel_xy):
                return True
            return schody_w_prostokacie(mp, poz, (cel_xy[0], cel_xy[1], poz[2]), wyjatek=self._dozwolone_klik_xy())

    return DojscieBezSchodow


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
                  if s.get("z") == poz[2] and s.get("x") is not None and s.get("nazwa") != akcje.nick
                  and not s.get("widmo")}
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
        _czekaj_koniec_kroku()            # ostatni krok dojścia mógł jeszcze trwać: strzałka w trakcie kroku bywa odrzucana
        postac.krok(kier)
        time.sleep(0.8)
        poz = tuple(postac.pozycja())
        if poz[2] == zb:
            log(f"schody: przeszedłem na z{zb}, stoję w {poz}")
            return True
        nieudane[klucz] = nieudane.get(klucz, 0) + 1
        log(f"schody: krok {kier} z {S[:2]} bez przejścia (stoję w {poz})")
    return False


# --- tempo marszu (19.10: postać krążyła w 4 polach, bo kolejne strzałki szły w trakcie trwającego kroku) -------
KROK_S_NA_PREDKOSC = 0.047      # czas kroku = bajt prędkości pola z mapy * 0,047 s (jak cavebot.POSCIG_KROK_S_NA_PREDKOSC)
KROK_S_DOMYSLNY = 0.55          # gdy mapa nie zna prędkości pola
KROK_S_MIN, KROK_S_MAX = 0.30, 1.20
SKALA_KROKU_MAX = 1.6           # o tyle (najwyżej) wydłużamy oczekiwany czas kroku po nieudanych krokach
MAKS_ZLYCH_Z_RZEDU = 6          # tyle kolejnych nieudanych kroków przerywa marsz (porażka + STOP zamiast krążenia)
MAKS_WIZYT_POLA = 3             # czwarte wejście na to samo pole w jednym marszu = krążenie, przerywamy
ZABLOK_POLA_S = 30.0            # pole, na którym krok zawiódł dwa razy, omijamy tak długo (nie 5 s: stąd pętla A-B-A-B)
KARA_ZAKRETU, KARA_ZAWROTU = 0.05, 0.5   # remis dróg rozstrzyga prosta linia; zawrót prawie nigdy (nie wygrywa z dłuższą drogą)
_RUCH = {"koniec": 0.0, "skala": 1.0}    # kiedy kończy się trwający krok (monotonic) i mnożnik czasu kroku


def _czas_kroku(mp, pole):
    """Szacunek czasu kroku (s) na `pole` (x, y, z) z prędkości pola na mapie, razy bieżąca skala (rośnie po nieudanych krokach)."""
    v = 0
    try:
        p = mp.pole(pole[0], pole[1], pole[2])
        if p and 0 < p[2] <= 60:
            v = p[2]
    except Exception:
        pass
    t = v * KROK_S_NA_PREDKOSC if v else KROK_S_DOMYSLNY
    return min(KROK_S_MAX, max(KROK_S_MIN, t)) * _RUCH["skala"]


# 23.10 (invincible, Edron, „chodzi po 1 kratce”): strzałki szły 0,72-0,82 s/krok przy kroku postaci ok. 0,4-0,5 s, bo kolejny klawisz
# czekał na PEŁNY szacunek kroku plus opóźnienia wykrycia i wysyłki (martwy czas ok. 0,25-0,3 s między krokami). Płynny marsz wysyła następną
# strzałkę PLYNNY_PRZED_S przed szacowanym końcem kroku (klawisz dociera do klienta, gdy krok już się kończy). To założenie NIE jest jeszcze
# zmierzone na żywo, więc: tylko gdy skala czasu kroku <= 1 (po nieudanym kroku wraca do ostrożnego), a pierwszy zawód, który udaje się
# po ponowieniu na tym samym polu (= klawisz odrzucony, nie ściana), wyłącza płynny marsz do końca procesu (_RUCH["plynny_wyl"]).
# Wyłącznik: RETRONIC_MARSZ_PLYNNY=0 w środowisku serwisu (stare tempo, czas kroku - 0,06 s).
PLYNNY_PRZED_S = 0.10


def _plynny():
    """True, gdy następną strzałkę wolno wysłać PLYNNY_PRZED_S przed szacowanym końcem kroku."""
    return (os.environ.get("RETRONIC_MARSZ_PLYNNY", "1") != "0" and not _RUCH.get("plynny_wyl")
            and _RUCH["skala"] <= 1.0)


def _po_kroku(czas_kroku=None, plynnie=True):
    """Zapamiętuje, kiedy skończy się krok, który właśnie się zaczął (Postac.krok wraca ok. 0,06 s po zmianie pozycji).
    `plynnie=False` (po kliku: moment startu ostatniego kroku znamy tylko z odpytywania) = bez wyprzedzenia."""
    przed = PLYNNY_PRZED_S if plynnie and _plynny() else 0.0
    _RUCH["koniec"] = time.monotonic() - 0.06 - przed + (czas_kroku if czas_kroku is not None else KROK_S_DOMYSLNY * _RUCH["skala"])
    _RUCH["przed"] = przed > 0


def _czekaj_koniec_kroku():
    """Następną strzałkę wysyłamy dopiero, gdy trwający krok się skończył: klawisz w trakcie kroku bywa odrzucany."""
    dt = _RUCH["koniec"] - time.monotonic()
    if dt > 0:
        time.sleep(dt + random.uniform(0.0, 0.05))


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
            _czekaj_koniec_kroku()
            nowa = postac.krok(klawisz[(dx, dy)])
            if nowa is not None and (nowa[0], nowa[1]) == (poz[0] + dx, poz[1] + dy):
                zle = 0                         # liczymy tylko kolejne nieudane kroki
                _po_kroku()
            else:
                zle += 1
                log(f"serwis: krok ({dx},{dy}) z {poz[:2]} bez skutku ({zle}/{maks_zlych})")
                if zle >= maks_zlych:
                    return False
                time.sleep(0.6)
    poz = tuple(postac.pozycja())
    return poz[2] == cel[2] and _cheb(poz, cel) <= tolerancja


def _klawisz_ruchu(a, b):
    """Strzałka na sąsiednie pole `b` z `a` (jedna oś) albo None."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if abs(dx) + abs(dy) != 1:
        return None
    return ("Right" if dx > 0 else "Left") if dx else ("Down" if dy > 0 else "Up")


def _postac_stoi(postac, spij=time.sleep, maks_s=4.0):
    """Czeka, aż pozycja postaci przestanie się zmieniać (dwa odczyty w odstępie DRZWI_SPOKOJ_S dają to samo pole) i ją zwraca.
    Wzór: cavebot._drzwi_spokoj; krok wysłany w trakcie trwającego kroku bywa odrzucany. Po maks_s zwraca ostatni odczyt."""
    ost = tuple(postac.pozycja())
    t0 = time.monotonic()
    while time.monotonic() - t0 < maks_s:
        spij(DRZWI_SPOKOJ_S)
        nowa = tuple(postac.pozycja())
        if nowa == ost:
            return nowa
        ost = nowa
    return ost


_DRZWI_OTWARTE = set()       # drzwi, przez które ten proces już przeszedł (zostają otwarte): nie dostają Use na początku, bo Use zamyka otwarte


def przejdz_drzwi(postac, przed, drzwi, za, log=print, otworz=None, spij=time.sleep):
    """Przejście przez zamknięte drzwi sklepu (22.10, Thais): stoimy na `przed` (pole przed drzwiami), czekamy aż postać
    stoi, Use na drzwiach (Ctrl+klik), pauza, krok na kafelek drzwi, krok na `za`; po każdym kroku sprawdzamy pozycję.
    Do DRZWI_PROB prób: krok, krok, Use + krok, krok (Use na otwartych drzwiach by je zamknęło, więc najpierw zawsze krok). Bez powodzenia SerwisBlad("drzwi"). True = stoimy na `za`.
    Wzór: cavebot._drzwi_trasa_tick, pietra._przed_use, wypad._drzwi."""
    przed, h, za = tuple(przed), tuple(drzwi), tuple(za)
    k_h, k_za = (_klawisz_ruchu(przed, h) if przed != h else "-"), _klawisz_ruchu(h, za)
    if k_h is None or k_za is None:
        raise SerwisBlad("drzwi", f"drzwi {h[:2]}: pola {przed[:2]} -> {za[:2]} nie leżą w jednej osi przez drzwi")
    if otworz is None:
        import ekran  # noqa: PLC0415
        otworz = ekran.otworz
    dx, dy = h[0] - przed[0], h[1] - przed[1]
    poz = _postac_stoi(postac, spij)
    if poz == za:
        return True
    if poz not in (przed, h):
        raise SerwisBlad("drzwi", f"drzwi {h[:2]}: stoję w {poz[:2]}, a powinienem na {przed[:2]} (przed drzwiami)")
    # 24.10 (Karol: „zamyka drzwi przed wejściem”): ZAWSZE najpierw dwa kroki, Use dopiero, gdy krok nie przeszedł; wcześniej
    # nieznane drzwi zaczynały od Use, które zamykało otwarte drzwi (wydra, Thais 13:3x). Jak cavebot DRZWI_NAJPIERW_KROK.
    tryby = ("krok", "krok", "use", "krok")
    for n in range(DRZWI_PROB):
        tryb = tryby[n % len(tryby)]
        poz = _postac_stoi(postac, spij)
        if poz == za:
            _DRZWI_OTWARTE.add(h)
            return True
        if poz == przed:
            log(f"serwis: drzwi {h[:2]} próba {n + 1}/{DRZWI_PROB} ({tryb}) z {przed[:2]}")
            if tryb == "use":
                otworz(dx, dy)
                spij(random.uniform(*DRZWI_CZEKAJ_S))
                poz = _postac_stoi(postac, spij)
                if poz != przed:
                    log(f"serwis: drzwi {h[:2]}: po Use stoję w {poz[:2]}, nie w {przed[:2]}")
                    continue
            _czekaj_koniec_kroku()
            nowa = postac.krok(k_h)
            poz = tuple(nowa) if nowa is not None else _postac_stoi(postac, spij)
            if poz != h:
                log(f"serwis: drzwi {h[:2]}: krok na drzwi bez skutku (stoję w {poz[:2]})")
                continue
            _po_kroku()
        if poz == h:                       # stoimy na kafelku drzwi (drzwi puszczają): krok dalej
            _czekaj_koniec_kroku()
            nowa = postac.krok(k_za)
            poz = tuple(nowa) if nowa is not None else _postac_stoi(postac, spij)
            if poz == za:
                _po_kroku()
                _DRZWI_OTWARTE.add(h)
                log(f"serwis: drzwi {h[:2]} przeszedłem, stoję w {poz[:2]}")
                return True
            log(f"serwis: drzwi {h[:2]}: krok na {za[:2]} bez skutku (stoję w {poz[:2]})")
    _DRZWI_OTWARTE.discard(h)
    raise SerwisBlad("drzwi", f"drzwi {h[:2]}: nie przeszedłem po {DRZWI_PROB} próbach (stoję w {tuple(postac.pozycja())[:2]})")


def podziel_na_drzwiach(punkty, drzwi):
    """Dzieli trasę z Planera na części: [("idz", [pkt...])] i [("drzwi", przed, drzwi, za)] w miejscu, gdzie punkt trasy to
    pole drzwi z `drzwi`. Część „idz” przed drzwiami kończy się na polu `przed`, następna zaczyna na `za`. Trasa zaczynająca
    się na kafelku drzwi daje najpierw część „drzwi” z przed == drzwi (przejdz_drzwi wtedy robi sam krok)."""
    drzwi = {tuple(h) for h in drzwi}
    punkty = [tuple(p) for p in punkty]
    czesci, biezaca, i = [], [], 0
    while i < len(punkty):
        p = punkty[i]
        if p in drzwi and i + 1 < len(punkty):
            przed = punkty[i - 1] if i > 0 else p
            if biezaca:
                czesci.append(("idz", biezaca))
            czesci.append(("drzwi", przed, p, punkty[i + 1]))
            biezaca = [punkty[i + 1]]
            i += 2
            continue
        biezaca.append(p)
        i += 1
    if len(biezaca) > 1 or (biezaca and not czesci):
        czesci.append(("idz", biezaca))
    return czesci


def idz_z_drzwiami(postac, punkty, drzwi, chodz1, tolerancja=0, log=print, otworz=None, spij=time.sleep):
    """Trasa z drzwiami: odcinki „idz” przez `chodz1(punkty, tolerancja)` (przed drzwiami dokładnie na polu `przed`),
    drzwi przez przejdz_drzwi. False, gdy odcinek marszu się nie udał; porażka drzwi to SerwisBlad."""
    czesci = podziel_na_drzwiach(punkty, drzwi)
    for n, c in enumerate(czesci):
        if c[0] == "idz":
            ostatnia = n == len(czesci) - 1
            if len(c[1]) > 1 and not chodz1(c[1], tolerancja if ostatnia else 0):
                return False
        else:
            przejdz_drzwi(postac, c[1], c[2], c[3], log=log, otworz=otworz, spij=spij)
    return True


KLIK_MAKS_POL = marsz_klik.KLIK_MAKS_POL      # ile pól naprzód klikamy naraz (widok mapy ma ±7 x ±5 pól)


def _dosc_npc(cel, poz):
    """Hak `dosc_marszu` dla marszu do `cel`: True / False / None (patrz klasa); poza kontekstem albo przy innym celu None."""
    fn = _DOSC.get("fn")
    if fn is None or _DOSC.get("cel") != tuple(cel):
        return None
    try:
        return fn(tuple(poz))
    except Exception:
        return None


def idz_pewnie(postac, mp, akcje, cel, tolerancja=0, maks_s=150.0, log=print, unik=(), stan=None):
    """Marsz po kafelkach na jednym piętrze, bez chodzika mozg (ten ma ~20 s inicjalizacji na odcinek i kończy trasy
    jednopunktowe od razu): Dijkstra po polach chodliwych mapy (bez schodów i dziur poza celem; remis dróg rozstrzyga
    prosta linia, zawrotu unikamy), omija pola zajęte przez innych graczy/stwory i pola, na których krok zawiódł dwa razy,
    jeden krok strzałką, kontrola pozycji. Gdy cały dojazd zablokowany przez ludzi, czeka i planuje od nowa.

    Tempo (19.10): kolejną strzałkę wysyłamy dopiero po końcu trwającego kroku (czas z prędkości pola, rośnie po
    nieudanych krokach): klawisz w trakcie kroku bywa odrzucany, a stary kod wysyłał go zaraz po zmianie pozycji i krążył.
    Nieudany krok jest logowany; pierwszy zawód na polu = ponowienie po dokończeniu kroku, drugi = pole zablokowane na
    ZABLOK_POLA_S. Bezpieczniki: MAKS_ZLYCH_Z_RZEDU nieudanych kroków z rzędu albo czwarte wejście na to samo pole
    przerywa marsz (False, `stan["utkniecie"]` = powód): lepiej porażka i STOP niż postać kręcąca się w kółko.
    True = stoimy w `tolerancja` pól od celu, False = brak planu (nieznane pola mapy), utknięcie albo przekroczony czas."""
    cel = tuple(cel)
    kierunki = [(0, -1), (0, 1), (-1, 0), (1, 0)]
    klawisz = {(0, -1): "Up", (0, 1): "Down", (-1, 0): "Left", (1, 0): "Right"}
    zablok, zawiodlo, wizyty = {}, {}, {}
    t0, ost_log = time.monotonic(), 0.0
    zle_z_rzedu, ok_krokow, zle_razem, ost_kier = 0, 0, 0, None
    kliki, powody = 0, {}      # 23.10: ile razy szliśmy klikiem i dlaczego strzałką (w podsumowaniu: s/krok liczy tylko strzałki)
    marg = 8      # margines prostokąta szukania drogi wokół start-cel; rośnie, gdy ściana każe obejść poza prostokąt (21.10 Edron z7 do Xodeta)

    unik = {tuple(u)[:2] for u in unik if tuple(u)[2] == cel[2]}

    def koszt(x, y, z):
        """None = nie wchodzimy; 1 = zwykłe pole; 6 = pole z flagą 2 (na mapie to bywa szum, ale może być przejście pięter)."""
        return marsz_klik.koszt_pola(mp, x, y, z, cel, unik)

    def koniec(wynik, powod=None):
        dt = time.monotonic() - t0
        if powod and stan is not None:
            stan["utkniecie"] = powod
        if ok_krokow or zle_razem or powod:
            log(f"serwis: marsz do {cel[:2]}: {ok_krokow} kroków w {dt:.1f} s"
                f"{f' ({dt / ok_krokow:.2f} s/krok)' if ok_krokow and not kliki else ''}"
                f"{f', klików {kliki}' if kliki else ''}"
                f"{f', strzałką bo: {dict(powody)}' if powody and ok_krokow else ''}, nieudanych {zle_razem}"
                f"{f', PRZERWANY: {powod}' if powod else ''}")
        return wynik

    while time.monotonic() - t0 < maks_s:
        poz = tuple(postac.pozycja())
        if poz[2] != cel[2]:
            return koniec(False)
        if _cheb(poz, cel) <= tolerancja:
            return koniec(True)
        wizyty.setdefault((poz[0], poz[1]), 1)       # pole, z którego ruszamy, liczy się jako pierwsze wejście
        teraz = time.monotonic()
        try:
            zajete = {(q.get("x"), q.get("y")) for q in akcje._stwory()
                      if q.get("z") == poz[2] and q.get("nazwa") != akcje.nick and not q.get("widmo")}
        except Exception:
            zajete = set()
        zajete |= {pole for pole, do in zablok.items() if do > teraz}
        zajete.discard((poz[0], poz[1]))
        if (cel[0], cel[1]) in zajete:
            # 23.10 (decyzja Karola): zajęte/zablokowane pole stania przy NPC nie każe czekać do końca limitu
            r = _dosc_npc(cel, poz)
            if r is True:
                log(f"serwis: pole stania {cel[:2]} zajęte, ale NPC jest w zasięgu rozmowy z {poz[:2]}: kończę marsz")
                return koniec(True)
            if r is False:
                log(f"serwis: pole stania {cel[:2]} zajęte, NPC poza zasięgiem rozmowy z {poz[:2]}: kończę marsz (serwis szuka innego pola)")
                return koniec(False, "pole stania zajęte, NPC poza zasięgiem rozmowy")
        start = (poz[0], poz[1])
        skad, d = {(start, ost_kier): None}, {(start, ost_kier): 0.0}
        kol, meta, n = [(0.0, 0, start, ost_kier)], None, 0
        xmin, xmax = min(poz[0], cel[0]) - marg, max(poz[0], cel[0]) + marg
        ymin, ymax = min(poz[1], cel[1]) - marg, max(poz[1], cel[1]) + marg
        while kol:
            cc, _, c, kc = heapq.heappop(kol)
            if cc > d.get((c, kc), 1e18):
                continue
            if max(abs(c[0] - cel[0]), abs(c[1] - cel[1])) <= tolerancja:
                meta = (c, kc)
                break
            for ki, (dx, dy) in enumerate(kierunki):
                q = (c[0] + dx, c[1] + dy)
                if not (xmin <= q[0] <= xmax and ymin <= q[1] <= ymax) or q in zajete:
                    continue
                k = koszt(q[0], q[1], poz[2])
                if k is None:
                    continue
                if kc is not None and ki != kc:
                    k += KARA_ZAWROTU if (dx, dy) == (-kierunki[kc][0], -kierunki[kc][1]) else KARA_ZAKRETU
                if cc + k < d.get((q, ki), 1e18):
                    d[(q, ki)] = cc + k
                    skad[(q, ki)] = (c, kc)
                    n += 1
                    heapq.heappush(kol, (cc + k, n, q, ki))
        if meta is None:
            if marg < 64:
                marg *= 2     # droga może prowadzić poza prostokątem: szukamy szerzej, zanim uznamy brak drogi
                continue
            r = _dosc_npc(cel, poz) if zajete else None            # 23.10: droga zablokowana ludźmi, a NPC w zasięgu = rozmowa z miejsca
            if r is True:
                log(f"serwis: brak drogi z {poz[:2]} do {cel[:2]}, ale NPC jest w zasięgu rozmowy: kończę marsz")
                return koniec(True)
            if r is False:
                log(f"serwis: brak drogi z {poz[:2]} do {cel[:2]}, NPC poza zasięgiem rozmowy: kończę marsz (serwis szuka innego pola)")
                return koniec(False, "brak drogi do pola stania, NPC poza zasięgiem rozmowy")
            if teraz - ost_log > 8:
                log(f"serwis: brak drogi z {poz[:2]} do {cel[:2]} (ludzie na drodze albo nieznane pola), czekam")
                ost_log = teraz
            if not zajete and not zablok:
                return koniec(False)              # nic nie blokuje, a drogi nie ma: mapa nie zna pól
            time.sleep(1.0)
            continue
        sciezka = []
        while meta is not None:
            sciezka.append(meta[0])
            meta = skad[meta]
        sciezka.reverse()
        # klik w mapę (klient sam idzie ciągiem, kilka razy szybciej niż krok po kroku): najdalsze pole ścieżki w zasięgu
        # widoku, do którego wszystkie pola są zwykłe (bez flagi 2) i wolne
        dalej = marsz_klik.dalej_klik(sciezka, koszt, poz[2], KLIK_MAKS_POL)
        powod_strzalki = "cel_blisko" if len(sciezka) <= 2 else ("pole_flagi_2_albo_zajete" if dalej < 2 else None)
        dalej0 = dalej
        # 22.10 (wydra, depo Thais): klient prowadzi klik własną drogą (8 kierunków, skos przez róg), więc pole schodów NIE na naszej
        # ścieżce, ale w prostokącie poz-klik, potrafi wciągnąć postać na inne piętro. Przy schodach idziemy strzałkami po naszej ścieżce.
        wyjatek = {(cel[0], cel[1])}
        while dalej >= 2 and schody_w_prostokacie(mp, (poz[0], poz[1], poz[2]), sciezka[dalej] + (poz[2],), wyjatek=wyjatek):
            dalej -= 1
        # 23.10 (Edron z6, 17 strzałek zamiast kliku): flaga 2 bez odpowiednika (dekoracja, kolor 129) obok korytarza skracała klik do 1 dla
        # całego odcinka. Prosty odcinek ścieżki (ta sama kolumna/wiersz) klient przechodzi prosto, więc tam liczą się tylko PRAWDZIWE
        # przejścia pięter w prostokącie z marginesem 1; i tylko gdy nikt (stwór, gracz, zablokowane pole) nie jest bliżej niż 2 pola od linii
        # (obchodząc go klient mógłby skręcić w bok).
        prosty = min(dalej0, prosty_odcinek(sciezka, dalej0)) if dalej0 >= 2 else 0
        if prosty > dalej and prosty >= 2:
            linia = sciezka[:prosty + 1]
            blisko = any(max(abs(q[0] - l[0]), abs(q[1] - l[1])) <= 2 for q in zajete for l in linia)
            while prosty >= 2 and not blisko and prosty > dalej and przejscie_pewne_w_prostokacie(
                    mp, (poz[0], poz[1], poz[2]), sciezka[prosty] + (poz[2],), wyjatek=wyjatek):
                prosty -= 1
            if prosty > dalej and not blisko:
                dalej = prosty
        if dalej >= 2:
            import ekran
            cel_kl = sciezka[dalej]
            try:
                ekran.klik_pola(cel_kl[0] - poz[0], cel_kl[1] - poz[1])
            except ValueError:
                dalej = 1
                powod_strzalki = "klik_poza_widokiem"
            else:
                kliki += 1
                wynik_kl = marsz_klik.klik_i_czekaj(postac, poz, cel_kl, dalej, zegar=time, log=log, prefiks="serwis")
                if wynik_kl == "pietro":
                    return False
                if wynik_kl == "ruch":
                    if tuple(postac.pozycja())[:2] == tuple(cel_kl[:2]):
                        # pozycja zmienia się na STARCIE kroku: ostatni krok kliku trwa jeszcze, strzałka teraz byłaby odrzucona (23.10: 2x w logu)
                        _po_kroku(_czas_kroku(mp, (cel_kl[0], cel_kl[1], poz[2])), plynnie=False)
                    continue
                dalej = 1                        # klik nic nie ruszył: ten krok strzałką
                powod_strzalki = "klik_bez_ruchu"
        elif powod_strzalki is None:
            powod_strzalki = "schody_obok"
        powody[powod_strzalki] = powody.get(powod_strzalki, 0) + 1
        nast = sciezka[1]
        dd = (nast[0] - poz[0], nast[1] - poz[1])
        czas_kroku = _czas_kroku(mp, (nast[0], nast[1], poz[2]))
        wyslano_przed = bool(_RUCH.get("przed")) and _plynny()      # klawisz wyszedł PLYNNY_PRZED_S przed szacowanym końcem kroku
        _czekaj_koniec_kroku()
        nowa = postac.krok(klawisz[dd])
        if nowa is not None and nowa[2] != poz[2]:
            log(f"serwis: krok na {nast} zmienił piętro ({poz[2]} -> {nowa[2]})")
            return koniec(False)
        if nowa is not None and (nowa[0], nowa[1]) == nast:
            zle_z_rzedu, ok_krokow, ost_kier = 0, ok_krokow + 1, kierunki.index(dd)
            wizyty[nast] = wizyty.get(nast, 0) + 1
            _RUCH["skala"] = max(1.0, _RUCH["skala"] * 0.995)     # skala po zawodach wraca do normy powoli (połowa po ok. 140 udanych krokach)
            if _RUCH.get("podejrzany") == nast and not _RUCH.get("plynny_wyl"):
                # to samo pole: wcześniej zawód klawisza wysłanego z wyprzedzeniem, teraz krok idzie = klawisz był odrzucony przez trwający krok
                _RUCH["plynny_wyl"] = True
                log(f"serwis: płynny marsz wyłączony do końca procesu (klawisz wysłany przed końcem kroku odrzucony na {nast}, "
                    f"po ponowieniu poszło); strzałki wracają do pełnego czasu kroku")
            _RUCH.pop("podejrzany", None)
            _po_kroku(czas_kroku)
            if wizyty[nast] > MAKS_WIZYT_POLA:
                powod = f"krążę: {wizyty[nast]}. wejście na pole {nast}"
                log(f"serwis: {powod}, przerywam marsz")
                return koniec(False, powod)
            continue
        # krok bez skutku (albo postać trafiła gdzie indziej): log, ponowienie po dokończeniu kroku, potem blokada pola
        zle_z_rzedu += 1
        zle_razem += 1
        zawiodlo[nast] = zawiodlo.get(nast, 0) + 1
        jest = None if nowa is None else tuple(nowa[:2])
        akcja = "ponowię po dokończeniu kroku" if zawiodlo[nast] < 2 else f"blokuję pole na {ZABLOK_POLA_S:.0f} s"
        log(f"serwis: krok {klawisz[dd]} z {poz[:2]} -> {nast} bez skutku (po kroku: {jest}), "
            f"nieudane z rzędu {zle_z_rzedu}/{MAKS_ZLYCH_Z_RZEDU}, na tym polu {zawiodlo[nast]}x, {akcja}")
        if zle_z_rzedu >= MAKS_ZLYCH_Z_RZEDU:
            now = tuple(postac.pozycja())[:2]
            powod = f"{MAKS_ZLYCH_Z_RZEDU} nieudanych kroków z rzędu (stoję w {now}, cel {cel[:2]})"
            log(f"serwis: {powod}, przerywam marsz")
            return koniec(False, powod)
        if wyslano_przed and jest in (None, tuple(poz[:2])):
            _RUCH["podejrzany"] = nast                 # nie wiemy jeszcze: odrzucony klawisz czy zwykła przeszkoda; rozstrzyga ponowienie
        if zawiodlo[nast] >= 2:
            zablok[nast] = time.monotonic() + ZABLOK_POLA_S
        _RUCH["skala"] = min(SKALA_KROKU_MAX, _RUCH["skala"] * 1.25)      # krok trwa dłużej, niż zakładaliśmy
        _RUCH["koniec"] = time.monotonic() + _czas_kroku(mp, (nast[0], nast[1], poz[2])) + 0.15
    return koniec(False)


def marsz(postac, mp, akcje, laczniki, punkty, tolerancja=0, log=print, zapasowy=None):
    """Jeden odcinek na jednym piętrze: idz_pewnie, a gdy brak planu albo czas minął, `zapasowy(punkty, tolerancja)` (chodzik
    mozg). Utknięcie (nieudane kroki z rzędu, krążenie) to SerwisBlad: serwis kończy się porażką i STOP-em, bez zapasowego."""
    cel = tuple(punkty[-1])
    stan = {}
    if tuple(postac.pozycja())[2] == cel[2]:
        if idz_pewnie(postac, mp, akcje, cel, tolerancja, log=log, unik=[p for l in laczniki for p in l], stan=stan):
            return True
        if stan.get("utkniecie"):
            raise SerwisBlad("marsz", f"{stan['utkniecie']}; nie kręcę się dalej")
    return zapasowy(punkty, tolerancja) if zapasowy else False


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


def _ratunek_porazka(postac, krok, powod, e, bot):
    """Ratunek F1 (SPEC_ratunek_haiku_1019, S1, cień): porażka serwisu -> log „wołałbym Haiku”. Pokrętło RATUNEK_HAIKU
    czytane z na_zywo.json instancji (serwis nie ładuje pokrętł cavebota). STOP ręczny (Zatrzymano) to nie sygnał."""
    try:
        if isinstance(e, bot.Zatrzymano):
            return
        import instancja  # noqa: PLC0415
        import ratunek  # noqa: PLC0415
        try:
            nz = json.loads(instancja.S.na_zywo.read_text())
            wl = int(nz.get("RATUNEK_HAIKU", 0))
            pytaj = wl == 1 and int(nz.get("RATUNEK_HAIKU_PYTAJ", 0)) == 1      # F2a: Haiku w cieniu (wątek, bez ruchu)
            limit_h = int(nz.get("RATUNEK_LIMIT_H", 20))
        except (OSError, ValueError, TypeError, AttributeError):
            wl, pytaj, limit_h = 0, False, 20
        if not wl:
            return
        try:
            poz = tuple(postac.pozycja())
        except Exception:
            poz = None
        s = ratunek.detektor().zdarzenie("porazka_trasy", time.monotonic(), poz, co="serwis", krok=krok, powod=str(powod)[:200])
        ratunek.zglos(s, log=lambda m: print(m, flush=True), plik_logu=ratunek.plik_logu(instancja.S.logi),
                      pytaj=pytaj, limit_h=limit_h)
    except Exception as ex:
        print(f"debug: ratunek błąd {ex!r}", flush=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("miasto", nargs="?", default=None, choices=miasta() + ["auto"],
                   help="edron, thais albo auto = miasto z pozycji postaci; bez argumentu też z pozycji (poza miastami edron)")
    p.add_argument("--kroki", help="lista kroków po przecinku (domyślnie z pliku danych)")
    p.add_argument("--na-sucho", action="store_true", help="tylko plan dróg, bez inputu do gry")
    p.add_argument("--od", help="x,y,z: plan na sucho z tego pola zamiast z bieżącej pozycji")
    p.add_argument("--bez-stop", action="store_true", help="po błędzie nie zapisuj pliku STOP")
    p.add_argument("--od-nowa", action="store_true", help="ignoruj stan poprzedniego przerwanego przebiegu (zrób wszystkie kroki)")
    p.add_argument("--pomin-brakujace", action="store_true",
                   help="kroków, których miasto nie ma w danych (np. bank w Thais), nie traktuj jako błąd: pomiń je")
    a = p.parse_args(argv)
    import bot
    import mapa as mapa_mod
    import wyprawa
    postac = bot.Postac()
    od_pola = tuple(int(v) for v in a.od.split(",")) if a.od else None
    try:
        poz_auto = None
        if a.miasto == "auto":
            poz_auto = od_pola if (a.na_sucho and od_pola) else postac.pozycja()
        elif a.miasto is None:                     # bez miasta: z pozycji postaci; brak odczytu = dawny domyślny edron
            try:
                poz_auto = od_pola if (a.na_sucho and od_pola) else postac.pozycja()
            except Exception:
                poz_auto = None
        elif not a.na_sucho:
            try:                                   # jawne miasto: tylko sprawdzenie, że postać nie stoi w innym mieście
                poz_auto = postac.pozycja()
            except Exception:
                poz_auto = None
        miasto = wybierz_miasto(a.miasto, poz_auto)
    except SerwisBlad as e:
        print(f"SERWIS: {e}", flush=True)
        return 2
    print(f"serwis: miasto {miasto}", flush=True)
    dane = wczytaj(miasto)
    mp = mapa_mod.mapa()
    planer = Planer(wyprawa.Trasownik(mp), dane["laczniki"], drzwi=drzwi_miasta(dane), mapa=mp)
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
        return marsz(postac, mp, akcje, planer.lacz, punkty, tolerancja, log=print,
                     zapasowy=lambda pts, tol: mozg.przejdz_dojscie(postac, pts, prog_hp=40, jedzenie=None, potwory=None,
                                                                    graczy=True, stop_przy_graczach=False, tolerancja=tol,
                                                                    proby=4, fabryka=fabryka_dojscia_bez_schodow(mp, planer.lacz)))

    def chodz(punkty, tolerancja=0):
        """Trasa z drzwiami sklepów (Thais) dzielona na odcinki i przejścia przez drzwi (przejdz_drzwi), reszta jak chodz_pietra."""
        if planer.drzwi and any(tuple(p) in planer.drzwi for p in punkty):
            return idz_z_drzwiami(postac, punkty, planer.drzwi, chodz_pietra, tolerancja, log=print)
        return chodz_pietra(punkty, tolerancja)

    def chodz_pietra(punkty, tolerancja=0):
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
        return bool(r) and chodz_pietra(punkty[j:], tolerancja)

    import instancja
    cele = pokretla_serwisu()
    print(f"serwis: pokrętła {cele}", flush=True)
    s = Serwis(dane, akcje, planer, postac.pozycja, chodz, log=print, cele=cele, stan_plik=instancja.S.stan / "serwis_stan.json")
    try:
        s.uruchom(kroki, od_nowa=a.od_nowa, pomin_brakujace=a.pomin_brakujace)
        powiadom("Serwis: gotowe", "Kroki: " + ", ".join(f"{k}={v}" for k, v in s.wynik.items()))
    except Exception as e:                   # SerwisBlad i wszystko inne (Zatrzymano, IndexError...): zawsze STOP i dymek
        krok = getattr(e, "krok", "?")
        powod = getattr(e, "powod", repr(e))
        print(f"SERWIS: PORAŻKA w kroku {krok}: {powod}", flush=True)
        powiadom("Serwis: porażka", f"Krok {krok}: {powod}", krytyczne=True)
        _ratunek_porazka(postac, krok, powod, e, bot)
        if not a.bez_stop:
            try:
                instancja.S.stop.write_text(f"serwis: {krok}: {powod}\n")
            except Exception:
                pass
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
