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
import random
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


def _po_kroku(czas_kroku=None):
    """Zapamiętuje, kiedy skończy się krok, który właśnie się zaczął (Postac.krok wraca ok. 0,06 s po zmianie pozycji)."""
    _RUCH["koniec"] = time.monotonic() - 0.06 + (czas_kroku if czas_kroku is not None else KROK_S_DOMYSLNY * _RUCH["skala"])


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


KLIK_MAKS_POL = 5      # ile pól naprzód klikamy naraz (widok mapy ma ±7 x ±5 pól)


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

    unik = {tuple(u)[:2] for u in unik if tuple(u)[2] == cel[2]}

    def koszt(x, y, z):
        """None = nie wchodzimy; 1 = zwykłe pole; 6 = pole z flagą 2 (na mapie to bywa szum, ale może być przejście pięter)."""
        if (x, y) == (cel[0], cel[1]):
            return 1.0
        f = mp.flagi(x, y, z)
        if not (f & 1) or (f & 4) or (x, y) in unik:
            return None
        if f & 2:
            # schody/dziury mają odpowiednik z flagą 2 na piętrze nad lub pod; krzesła i meble go nie mają (wtedy chodzimy)
            for zz in (z - 1, z + 1):
                for ddx in (-1, 0, 1):
                    for ddy in (-1, 0, 1):
                        if mp.flagi(x + ddx, y + ddy, zz) & 2:
                            return None
            return 6.0
        return 1.0

    def koniec(wynik, powod=None):
        dt = time.monotonic() - t0
        if powod and stan is not None:
            stan["utkniecie"] = powod
        if ok_krokow or zle_razem or powod:
            log(f"serwis: marsz do {cel[:2]}: {ok_krokow} kroków w {dt:.1f} s"
                f"{f' ({dt / ok_krokow:.2f} s/krok)' if ok_krokow else ''}, nieudanych {zle_razem}"
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
        start = (poz[0], poz[1])
        skad, d = {(start, ost_kier): None}, {(start, ost_kier): 0.0}
        kol, meta, n = [(0.0, 0, start, ost_kier)], None, 0
        marg = 8
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
        dalej = 1
        while (dalej < len(sciezka) - 1 and dalej < KLIK_MAKS_POL
               and koszt(sciezka[dalej + 1][0], sciezka[dalej + 1][1], poz[2]) == 1.0):
            dalej += 1
        if dalej >= 2:
            import ekran
            cel_kl = sciezka[dalej]
            try:
                ekran.klik_pola(cel_kl[0] - poz[0], cel_kl[1] - poz[1])
            except ValueError:
                dalej = 1
            else:
                t1, ost, stoi = time.monotonic(), poz, 0
                while time.monotonic() - t1 < 0.8 + 0.45 * dalej:
                    time.sleep(0.12)
                    teraz_poz = tuple(postac.pozycja())
                    if teraz_poz[2] != poz[2]:
                        log(f"serwis: klik na {cel_kl} zmienił piętro ({poz[2]} -> {teraz_poz[2]})")
                        return False
                    if teraz_poz[:2] == cel_kl[:2]:
                        break
                    stoi = stoi + 1 if teraz_poz == ost else 0
                    ost = teraz_poz
                    if stoi >= 4 and teraz_poz != poz:
                        break
                    if stoi >= 6:
                        break
                if tuple(postac.pozycja())[:2] != poz[:2]:
                    continue
                dalej = 1                        # klik nic nie ruszył: ten krok strzałką
        nast = sciezka[1]
        dd = (nast[0] - poz[0], nast[1] - poz[1])
        czas_kroku = _czas_kroku(mp, (nast[0], nast[1], poz[2]))
        _czekaj_koniec_kroku()
        nowa = postac.krok(klawisz[dd])
        if nowa is not None and nowa[2] != poz[2]:
            log(f"serwis: krok na {nast} zmienił piętro ({poz[2]} -> {nowa[2]})")
            return koniec(False)
        if nowa is not None and (nowa[0], nowa[1]) == nast:
            zle_z_rzedu, ok_krokow, ost_kier = 0, ok_krokow + 1, kierunki.index(dd)
            wizyty[nast] = wizyty.get(nast, 0) + 1
            _RUCH["skala"] = max(1.0, _RUCH["skala"] * 0.995)     # skala po zawodach wraca do normy powoli (połowa po ok. 140 udanych krokach)
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
        return marsz(postac, mp, akcje, planer.lacz, punkty, tolerancja, log=print,
                     zapasowy=lambda pts, tol: mozg.przejdz_dojscie(postac, pts, prog_hp=40, jedzenie=None, potwory=None,
                                                                    graczy=True, stop_przy_graczach=False, tolerancja=tol,
                                                                    proby=4))

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
