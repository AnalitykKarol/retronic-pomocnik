#!/usr/bin/env python3
"""Mapa obecności mobów i wybór celu patrolu według respawnu (SPEC_patrol_respawn_1015, kroki 1-2).

Czysta logika, bez I/O gry: siatka komórek KOM x KOM pól per piętro, ograniczona do obszaru jaskini.
Komórka pamięta, kiedy była w widoku (t_widok), kiedy widziano w niej moba-cel (t_mob), kiedy była w widoku
i pusta (t_czyste), zabicia (licznik + czas) i gęstość (średnia liczba mobów w komórce, gdy była w widoku).
Z tego: oczekiwana liczba mobów teraz = gęstość x f(czas od wyczyszczenia, respawn), a wartość celu patrolu =
suma oczekiwanych w unikalnych komórkach drogi i celu / czas dojścia.

  python3 -I obecnosc.py --raport [--logi DIR] [--wyjscie PLIK]    raport offline z telemetrii (tylko odczyt)

Bot jeszcze tego nie używa (krok 3 specyfikacji: wpięcie i pokrętło PATROL_RESPAWN po akceptacji).
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True

KAT = Path(__file__).resolve().parent

# --- stałe (docelowo pokrętła cavebot.PATROL_RESPAWN_*; tu wartości domyślne modułu) ---
KOM = 4                            # bok komórki (pola)
WIDOK = (7, 5)                     # połowa widoku klienta: dx -7..7, dy -5..5 (15 x 11 pól)
MARGINES = 12                      # pola: margines bbox wokół miejsc patrolu
RESPAWN_DOMYSLNY_S = 300.0         # s: mediana czasu od wyczyszczenia do następnego moba, gdy brak danych
RESPAWN_MIN_PRZYPADKOW = 5         # tyle przypadków w komórce, by użyć jej własnego respawnu
RESPAWN_GLOBALNY_MIN = 30          # tyle przypadków łącznie, by użyć globalnej mediany zamiast domyślnej
GEST_DOMYSLNA = 0.05               # mobów na komórkę: gdy komórki nigdy nie widziano
GEST_WAGA_S = 120.0                # s widoku "pseudo-obserwacji" przy wartości domyślnej (wygładzenie gęstości)
MOB_SWIEZY_S = 45.0                # s: mob widziany niedawno (i nie zabity po tym) = komórka "wysoka"
MOB_SWIEZY_MIN = 0.5               # oczekiwane w komórce ze świeżym mobem: max(2 x gęstość, tyle)
DT_PROBKI_MAX_S = 5.0              # s: tyle maks. waży jedna obserwacja w czasie widoku (przerwy w próbkowaniu)
DOKLADNA_LUKA_S = 10.0             # s: przerwa między obserwacjami komórki, powyżej której przypadek respawnu jest "luką"
PRZYPADEK_MIN_S = 30.0             # s: krótszy powrót moba to raczej sąsiad z grupy niż respawn, więc nie wchodzi do respawnu
PRZYPADKI_MAX = 60                 # tyle ostatnich przypadków respawnu na komórkę
MIN_CZAS_DOJSCIA_S = 10.0          # s: dolna granica dzielnika w wartosc_celu
CEL_PROMIEN = 4                    # pola wokół miejsca patrolu, które liczą się jako "przy miejscu"
GRACZ_PROMIEN = 10                 # pola: komórka tak blisko obcego gracza dostaje karę
GRACZ_KARA = 0.2                   # mnożnik oczekiwanych w komórce przy graczu (moby zabiera on)
PEWNOSC_MIN = 0.15                 # poniżej: wybierz() zwraca None (decyduje dzisiejsza reguła)
DANE_MIN_S = 10.0                  # s widoku, od których komórka liczy się jako "z danymi"
STAN_STARY_S = 4 * 3600.0          # stan starszy: tylko gęstość i przypadki respawnu, bez t_*
STAN_WERSJA = 1


def komorka_pola(x, y, z, kom=KOM):
    """Klucz komórki (cx, cy, z) dla pola."""
    return (x // kom, y // kom, z)


class Komorka:
    __slots__ = ("t_widok", "t_mob", "t_czyste", "zabicia", "t_zab", "suma_mob_s", "czas_widoku",
                 "pusta_od", "luka_max", "przypadki")

    def __init__(self):
        self.t_widok = None            # ostatnia obserwacja w widoku
        self.t_mob = None              # ostatnio widziany mob-cel
        self.t_czyste = None           # ostatnio w widoku i pusta
        self.zabicia = 0
        self.t_zab = None
        self.suma_mob_s = 0.0          # suma (liczba mobów x waga czasu) w obserwacjach w widoku
        self.czas_widoku = 0.0         # suma wag czasu obserwacji w widoku
        self.pusta_od = None           # początek bieżącej passy pustki (pierwsza obserwacja pusta po mobie / zabiciu)
        self.luka_max = 0.0            # największa przerwa między obserwacjami w bieżącej passie pustki
        self.przypadki = []            # [[dt_s, dokladny 0/1], ...] czas od wyczyszczenia do następnego moba

    def do_slownika(self):
        return {"t_widok": self.t_widok, "t_mob": self.t_mob, "t_czyste": self.t_czyste, "zabicia": self.zabicia,
                "t_zab": self.t_zab, "suma_mob_s": round(self.suma_mob_s, 2),
                "czas_widoku": round(self.czas_widoku, 2), "pusta_od": self.pusta_od,
                "luka_max": round(self.luka_max, 2), "przypadki": self.przypadki[-PRZYPADKI_MAX:]}

    @classmethod
    def ze_slownika(cls, d, stary=False):
        k = cls()
        k.zabicia = int(d.get("zabicia", 0))
        k.suma_mob_s = float(d.get("suma_mob_s", 0.0))
        k.czas_widoku = float(d.get("czas_widoku", 0.0))
        k.przypadki = [list(p) for p in d.get("przypadki", [])][-PRZYPADKI_MAX:]
        if not stary:
            for a in ("t_widok", "t_mob", "t_czyste", "t_zab", "pusta_od"):
                setattr(k, a, d.get(a))
            k.luka_max = float(d.get("luka_max", 0.0))
        return k


def mediana(l):
    l = sorted(l)
    if not l:
        return None
    n = len(l)
    return l[n // 2] if n % 2 else 0.5 * (l[n // 2 - 1] + l[n // 2])


class MapaObecnosci:
    """Siatka komórek obszaru jaskini. bbox = (x0, y0, x1, y1) włącznie, pietra = zbiór z."""

    def __init__(self, bbox, pietra, kom=KOM, respawn_domyslny=RESPAWN_DOMYSLNY_S,
                 gest_domyslna=GEST_DOMYSLNA):
        self.bbox = tuple(bbox)
        self.pietra = frozenset(pietra)
        self.kom = kom
        self.respawn_domyslny = respawn_domyslny
        self.gest_domyslna = gest_domyslna
        self.k = {}                    # (cx, cy, z) -> Komorka (tworzone przy pierwszym dotknięciu)
        self._resp_glob = None         # pamięć podręczna globalnej mediany respawnu
        self._resp_glob_n = -1
        self._przyp_n = 0              # łączna liczba przypadków (do unieważniania pamięci)
        self.swieze = True             # False = bez wzmocnienia komórek ze świeżym mobem (tylko zegar respawnu; diagnostyka)

    @classmethod
    def dla_miejsc(cls, miejsca, margines=MARGINES, **kw):
        """Obszar z listy miejsc patrolu [{x, y, z}] + margines."""
        xs = [m["x"] for m in miejsca]
        ys = [m["y"] for m in miejsca]
        return cls((min(xs) - margines, min(ys) - margines, max(xs) + margines, max(ys) + margines),
                   {m["z"] for m in miejsca}, **kw)

    # --- geometria ---
    def w_obszarze(self, x, y, z):
        b = self.bbox
        return z in self.pietra and b[0] <= x <= b[2] and b[1] <= y <= b[3]

    def klucz(self, x, y, z):
        return komorka_pola(x, y, z, self.kom)

    def _klucz_w_obszarze(self, key):
        cx, cy, z = key
        kom = self.kom
        return self.w_obszarze(cx * kom, cy * kom, z) or self.w_obszarze(cx * kom + kom - 1, cy * kom + kom - 1, z)

    def komorki_w_widoku(self, poz, widok=WIDOK):
        """Klucze komórek w całości w widoku gracza (i w obszarze)."""
        px, py, z = poz[0], poz[1], poz[2]
        kom = self.kom
        x0, x1 = px - widok[0], px + widok[0]
        y0, y1 = py - widok[1], py + widok[1]
        wynik = []
        for cx in range(-((-x0) // kom), (x1 - kom + 1) // kom + 1):
            for cy in range(-((-y0) // kom), (y1 - kom + 1) // kom + 1):
                key = (cx, cy, z)
                if self._klucz_w_obszarze(key):
                    wynik.append(key)
        return wynik

    def komorki_pol(self, pola, promien_komorek=0):
        """Unikalne klucze komórek (w obszarze) dla pól (x, y, z); promien_komorek rozszerza o sąsiednie komórki."""
        wynik = set()
        r = promien_komorek
        for p in pola:
            cx, cy, z = self.klucz(p[0], p[1], p[2])
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    key = (cx + dx, cy + dy, z)
                    if self._klucz_w_obszarze(key):
                        wynik.add(key)
        return wynik

    def komorki_celu(self, cel, promien=CEL_PROMIEN):
        """Komórki przy miejscu (x, y, z): każda, która ma pole w promieniu `promien` (Czebyszew)."""
        x, y, z = cel
        kom = self.kom
        wynik = set()
        for cx in range((x - promien) // kom, (x + promien) // kom + 1):
            for cy in range((y - promien) // kom, (y + promien) // kom + 1):
                key = (cx, cy, z)
                if self._klucz_w_obszarze(key):
                    wynik.add(key)
        return wynik

    def _kom(self, key):
        c = self.k.get(key)
        if c is None:
            c = self.k[key] = Komorka()
        return c

    # --- obserwacje ---
    def obserwuj(self, t, poz, stwory, potwory, widok=WIDOK):
        """Jedna obserwacja z ticku. poz=(x,y,z); stwory = [{nazwa|n, x, y, z?, gracz?}] (współrzędne bezwzględne);
        potwory = zbiór nazw celów (małe litery). Komórki w całości w widoku: pusta -> t_czyste, z mobem -> t_mob.
        Zwraca liczbę zaktualizowanych komórek."""
        z = poz[2]
        w_widoku = self.komorki_w_widoku(poz, widok)
        if not w_widoku:
            return 0
        licznik = {}
        for s in stwory:
            if s.get("gracz"):
                continue
            nazwa = (s.get("nazwa") or s.get("n") or "").lower()
            if nazwa not in potwory:
                continue
            if s.get("z", z) != z:
                continue
            key = self.klucz(s["x"], s["y"], z)
            licznik[key] = licznik.get(key, 0) + 1
        for key in w_widoku:
            c = self._kom(key)
            prev = c.t_widok
            dt = 1.0 if prev is None else max(0.0, min(t - prev, DT_PROBKI_MAX_S))
            n = licznik.get(key, 0)
            c.czas_widoku += dt
            c.suma_mob_s += n * dt
            luka = 0.0 if prev is None else t - prev
            if n:
                if c.pusta_od is not None:
                    c.luka_max = max(c.luka_max, luka)
                    dokl = 1 if c.luka_max <= DOKLADNA_LUKA_S else 0
                    dt_p = t - c.pusta_od
                    if dt_p >= PRZYPADEK_MIN_S:
                        c.przypadki.append([round(dt_p, 1), dokl])
                        if len(c.przypadki) > PRZYPADKI_MAX:
                            del c.przypadki[0]
                        self._przyp_n += 1
                    c.pusta_od = None
                    c.luka_max = 0.0
                c.t_mob = t
            else:
                if c.pusta_od is None:
                    if c.t_mob is not None or c.t_zab is not None:     # pustka liczy się od chwili, gdy mob stąd zniknął
                        c.pusta_od = t
                        c.luka_max = 0.0
                else:
                    c.luka_max = max(c.luka_max, luka)
                c.t_czyste = t
            c.t_widok = t
        # komórki z mobem poza "w całości w widoku" (brzeg widoku): tylko t_mob (obecność), bez gęstości i pustki
        for key, n in licznik.items():
            if key not in w_widoku and self._klucz_w_obszarze(key):
                c = self._kom(key)
                if c.t_mob is None or t > c.t_mob:
                    c.t_mob = t
        return len(w_widoku)

    def zabicie(self, t, x, y, z):
        """Zabity mob na polu: licznik, czas; passa pustki komórki zaczyna się od nowa (po zabiciu nie jest pusta)."""
        key = self.klucz(x, y, z)
        if not self._klucz_w_obszarze(key):
            return False
        c = self._kom(key)
        c.zabicia += 1
        c.t_zab = t
        c.pusta_od = None
        c.luka_max = 0.0
        return True

    # --- model ---
    def gestosc(self, key):
        """Średnia liczba mobów w komórce, gdy była w widoku (wygładzona wartością domyślną)."""
        c = self.k.get(key)
        if c is None:
            return self.gest_domyslna
        return (c.suma_mob_s + GEST_WAGA_S * self.gest_domyslna) / (c.czas_widoku + GEST_WAGA_S)

    def _respawn_globalny(self):
        if self._resp_glob_n != self._przyp_n:
            wszystkie = [p[0] for c in self.k.values() for p in c.przypadki]
            self._resp_glob = mediana(wszystkie) if len(wszystkie) >= RESPAWN_GLOBALNY_MIN else None
            self._resp_glob_n = self._przyp_n
        return self._resp_glob

    def respawn(self, key):
        """Mediana czasu od wyczyszczenia do następnego moba: komórki (>= N przypadków), inaczej globalna
        (>= RESPAWN_GLOBALNY_MIN), inaczej domyślna."""
        c = self.k.get(key)
        if c is not None and len(c.przypadki) >= RESPAWN_MIN_PRZYPADKOW:
            m = mediana([p[0] for p in c.przypadki])
            if m and m > 0:
                return m
        g = self._respawn_globalny()
        return g if g and g > 0 else self.respawn_domyslny

    @staticmethod
    def f(dt, respawn):
        """Prawdopodobieństwo, że po dt s od wyczyszczenia mobów już wróciły: rośnie od 0 do 1; w czasie `respawn`
        (mediana) wynosi 1/2 (czas połowicznego powrotu)."""
        if dt <= 0 or respawn <= 0:
            return 0.0
        return 1.0 - 0.5 ** (dt / respawn)

    def ma_dane(self, key):
        c = self.k.get(key)
        return c is not None and c.czas_widoku >= DANE_MIN_S

    def czas_odniesienia(self, key):
        """Chwila, od której liczymy powrót mobów: ostatnie wyczyszczenie komórki (obserwacja pusta w widoku albo
        zabicie). None = brak informacji albo po wyczyszczeniu widziano w niej moba (komórka znów zaludniona)."""
        c = self.k.get(key)
        if c is None:
            return None
        ref = c.t_czyste
        if c.t_zab is not None and (ref is None or c.t_zab > ref):
            ref = c.t_zab
        if ref is None or (c.t_mob is not None and c.t_mob > ref):
            return None
        return ref

    def oczekiwane(self, key, t):
        """Oczekiwana liczba mobów w komórce teraz."""
        if not self._klucz_w_obszarze(key):
            return 0.0
        g = self.gestosc(key)
        c = self.k.get(key)
        if c is None:
            return g                                  # brak obserwacji: gęstość historyczna / domyślna
        ref = self.czas_odniesienia(key)
        if ref is None:
            # zaludniona (mob widziany po ostatnim wyczyszczeniu) albo nigdy nie widziana pusta
            if self.swieze and c.t_mob is not None and t - c.t_mob < MOB_SWIEZY_S:
                return max(2.0 * g, MOB_SWIEZY_MIN)   # mob widziany niedawno = wysoka
            return g
        return g * self.f(t - ref, self.respawn(key))

    def zegar(self, key, t):
        """Sam zegar respawnu bez gęstości (diagnostyka raportu): f(czas od wyczyszczenia), 1 gdy brak wyczyszczenia."""
        ref = self.czas_odniesienia(key)
        return 1.0 if ref is None else self.f(t - ref, self.respawn(key))

    def kara_gracza(self, key, gracze):
        """Mnożnik (GRACZ_KARA albo 1) dla komórki blisko któregoś z graczy (x, y, z) na tym samym piętrze."""
        if not gracze:
            return 1.0
        cx, cy, z = key
        sx, sy = cx * self.kom + self.kom / 2.0, cy * self.kom + self.kom / 2.0
        for g in gracze:
            if g[2] == z and max(abs(g[0] - sx), abs(g[1] - sy)) <= GRACZ_PROMIEN:
                return GRACZ_KARA
        return 1.0

    def wartosc_celu(self, droga_komorki, czas_dojscia, t, gracze=()):
        """Suma oczekiwanych mobów w unikalnych komórkach (drogi i celu) / max(czas dojścia, MIN_CZAS_DOJSCIA_S).
        Komórki przy graczu x GRACZ_KARA."""
        suma = 0.0
        for key in set(droga_komorki):
            suma += self.oczekiwane(key, t) * self.kara_gracza(key, gracze)
        return suma / max(czas_dojscia, MIN_CZAS_DOJSCIA_S)

    def komorki_celu_i_drogi(self, cel, promien_komorek=0):
        """Komórki z drogi (lista pól cel['droga']) i przy końcu drogi (miejscu)."""
        droga = cel.get("droga") or []
        zbior = self.komorki_pol(droga, promien_komorek)
        if droga:
            zbior |= self.komorki_celu(tuple(droga[-1][:3]))
        elif cel.get("poz"):
            zbior |= self.komorki_celu(tuple(cel["poz"][:3]))
        return zbior

    def wybierz(self, cele, t, gracze=(), prog=PEWNOSC_MIN, promien_komorek=0):
        """cele: [{id, droga: [(x,y,z)...] od bota do celu, dojscie_s}]. Zwraca (id | None, {id: wartość}, pewność).
        Pewność = udział komórek z danymi w najlepszym celu x względna przewaga nad drugim (0..1); poniżej `prog`
        (albo brak celów / wartość 0) id = None, czyli decyduje dzisiejsza reguła."""
        wartosci, dane = {}, {}
        for c in cele:
            kom = self.komorki_celu_i_drogi(c, promien_komorek)
            wartosci[c["id"]] = self.wartosc_celu(kom, c.get("dojscie_s", 0.0), t, gracze)
            dane[c["id"]] = (sum(1 for key in kom if self.ma_dane(key)) / len(kom)) if kom else 0.0
        if not wartosci:
            return None, {}, 0.0
        porz = sorted(wartosci, key=lambda i: wartosci[i], reverse=True)
        najl = porz[0]
        v1 = wartosci[najl]
        v2 = wartosci[porz[1]] if len(porz) > 1 else 0.0
        przewaga = (v1 - v2) / v1 if v1 > 0 else 0.0
        pewnosc = dane[najl] * przewaga
        if v1 <= 0 or pewnosc < prog:
            return None, wartosci, pewnosc
        return najl, wartosci, pewnosc

    # --- stan ---
    def do_slownika(self, teraz):
        return {"wersja": STAN_WERSJA, "zapisano": teraz, "kom": self.kom, "bbox": list(self.bbox),
                "pietra": sorted(self.pietra),
                "komorki": {f"{k[0]},{k[1]},{k[2]}": c.do_slownika() for k, c in self.k.items()}}

    def zapisz(self, plik, teraz):
        """Zapis atomowy (plik tymczasowy obok + os.replace)."""
        plik = Path(plik)
        plik.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(plik.parent), prefix=plik.name + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self.do_slownika(teraz), f, separators=(",", ":"))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, plik)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    @classmethod
    def wczytaj(cls, plik, teraz, stary_s=STAN_STARY_S, **kw):
        """Odczyt stanu; None, gdy brak pliku albo jest uszkodzony. Stan starszy niż stary_s: tylko gęstość i
        przypadki respawnu (bez t_*), bo położenie mobów sprzed kilku godzin nic nie mówi."""
        try:
            d = json.loads(Path(plik).read_text())
            if d.get("wersja") != STAN_WERSJA:
                return None
            stary = (teraz - float(d.get("zapisano", 0))) > stary_s
            m = cls(d["bbox"], d["pietra"], kom=int(d.get("kom", KOM)), **kw)
            for ks, cd in d["komorki"].items():
                cx, cy, z = (int(v) for v in ks.split(","))
                m.k[(cx, cy, z)] = Komorka.ze_slownika(cd, stary)
            m._przyp_n = sum(len(c.przypadki) for c in m.k.values())
            return m
        except (OSError, ValueError, KeyError, TypeError):
            return None


# =====================================================================================================
# Raport offline (krok 1): telemetria -> gęstość, respawn, symulacja wyboru celu. Tylko odczyt.
# =====================================================================================================

OBSZAR_RAPORTU = (32465, 32250, 32515, 32305)       # x0, y0, x1, y1 jaskini trolli
PIETRA_RAPORTU = (8, 9)
CEL_NAZWY = frozenset({"troll"})
KROK_S = 0.4                       # założenie symulacji: s na pole
SCHODY_S = 3.0                     # założenie: s na jedno przejście pięter
PROG_SWIEZE_S = 300.0              # "świeżo wyczyszczone": czas od wyczyszczenia < 300 s
ODL_MIN_MIEJSCA = 3                # jak PATROL_ODL_MIN: miejsca bliżej niż 3 pola nie są kandydatami


def _wczytaj_rekordy(katalog):
    import glob
    rek, zle, pliki = [], 0, []
    for p in sorted(glob.glob(os.path.join(katalog, "telemetria-*.jsonl"))):
        pliki.append(os.path.basename(p))
        with open(p, encoding="utf-8", errors="replace") as f:
            for l in f:
                try:
                    e = json.loads(l)
                except ValueError:
                    zle += 1
                    continue
                if e.get("typ") in ("probka", "epizod_celu", "patrol_cel", "patrol_wizyta"):
                    rek.append(e)
    rek.sort(key=lambda e: e.get("t", 0.0))
    return rek, pliki, zle


def _probka_na_stwory(e):
    """Próbka (dx/dy względem gracza) -> (poz, stwory bezwzględne, gracze obcy)."""
    px, py, pz = e["poz"]
    stwory, gracze = [], []
    for s in e.get("stwory", []):
        x, y = px + s["dx"], py + s["dy"]
        if s.get("gracz"):
            if s.get("odl", 1) > 0 or s["dx"] or s["dy"]:     # (0,0) = bot sam
                gracze.append((x, y, pz))
            continue
        stwory.append({"nazwa": s["n"], "x": x, "y": y, "z": pz, "hp": s.get("hp")})
    return (px, py, pz), stwory, gracze


class Droga:
    """Drogi z pozycji do miejsc patrolu: A* mapa.py na piętrze + graf przejść pięter (miejsca_troll.json).
    Założenia: czas = pola x KROK_S + SCHODY_S za przejście; schody wg `przejscia` i `laczniki` pliku miejsc."""

    def __init__(self, miejsca_plik, znane_plik=None):
        import mapa as _m
        self.m = _m.mapa()
        self._K = _m._K
        d = json.loads(Path(miejsca_plik).read_text())
        self.miejsca = d["miejsca"]
        self.znane = {}
        if znane_plik and Path(znane_plik).exists():
            for x, y, z in json.loads(Path(znane_plik).read_text()):
                self.znane.setdefault(z, set()).add(x * self._K + y)
        g = d["graf"]
        self.wezly = [tuple(w["pole"]) for w in g["wezly"]]
        self.komp = [w["komp"] for w in g["wezly"]]
        self.idx = {p: i for i, p in enumerate(self.wezly)}
        self.kraw = {i: [] for i in range(len(self.wezly))}     # i -> [(j, koszt_s, typ)]
        for i, j, dl in g["odl"]:
            self.kraw[i].append((j, dl * KROK_S, ("a", i, j)))
            self.kraw[j].append((i, dl * KROK_S, ("a", j, i)))
        for p in d["przejscia"]:
            for a, b in ((p["wejscie_gora"], p["wyjscie_dol"]), (p["wejscie_dol"], p["wyjscie_gora"])):
                i, j = self.idx.get(tuple(a)), self.idx.get(tuple(b))
                if i is None or j is None:
                    continue
                self.kraw[i].append((j, KROK_S + SCHODY_S, ("s", i, j)))
                self.kraw[j].append((i, KROK_S + SCHODY_S, ("s", j, i)))
        for l in d["laczniki"]:
            i, j = self.idx.get(tuple(l["od"])), self.idx.get(tuple(l["do"]))
            if i is None or j is None:
                continue
            kr = len(l["kroki"]) * KROK_S
            self.kraw[i].append((j, kr, ("l", i, j, l["kroki"])))
            if l.get("dwa_kierunki"):
                self.kraw[j].append((i, kr, ("l", j, i, l["kroki"][::-1])))
        self.nodes_miejsc = {}
        for mi in self.miejsca:
            self.nodes_miejsc[mi["id"]] = self.idx.get((mi["x"], mi["y"], mi["z"]))
        self._cache_a = {}
        self.brak_drogi = 0

    def astar(self, a, b):
        """Lista pól (bez startu) albo None."""
        k = (a, b)
        if k in self._cache_a:
            return self._cache_a[k]
        w = self.m.droga(a, b, dlugosc=0, znane=self.znane.get(a[2]))
        self._cache_a[k] = w
        return w

    def drogi_z(self, poz):
        """Dla każdego miejsca: {id: (droga_pol [(x,y,z)], czas_s)} lub brak klucza (nieosiągalne w modelu)."""
        import heapq
        poz = tuple(poz)
        n = len(self.wezly)
        # krawędzie startowe: A* z poz do węzłów na tym samym piętrze
        start = {}
        for i, p in enumerate(self.wezly):
            if p[2] != poz[2]:
                continue
            w = self.astar(poz, p)
            if w is not None:
                start[i] = w
        odleglosc = {}
        poprz = {}
        h = []
        for i, w in start.items():
            c = max(len(w), 0) * KROK_S
            odleglosc[i] = c
            poprz[i] = ("start", None)
            heapq.heappush(h, (c, i))
        while h:
            c, i = heapq.heappop(h)
            if c > odleglosc.get(i, 1e18):
                continue
            for j, kc, typ in self.kraw[i]:
                nc = c + kc
                if nc < odleglosc.get(j, 1e18):
                    odleglosc[j] = nc
                    poprz[j] = (typ, i)
                    heapq.heappush(h, (nc, j))
        wynik = {}
        for mid, node in self.nodes_miejsc.items():
            if node is None or node not in odleglosc:
                continue
            # odtwórz drogę (listę pól) od celu wstecz
            seg = []
            j = node
            while True:
                typ, i = poprz[j]
                if typ == "start":
                    seg.append(start[j])
                    break
                seg.append(self._pola_segmentu(typ))
                j = i
            pola = [p for s in reversed(seg) for p in s]
            wynik[mid] = (pola, odleglosc[node])
        return wynik

    def _pola_segmentu(self, typ):
        if typ[0] == "a":
            w = self.astar(self.wezly[typ[1]], self.wezly[typ[2]])
            return w if w is not None else [self.wezly[typ[2]]]
        if typ[0] == "s":
            return [self.wezly[typ[2]]]
        return [tuple(k) for k in typ[3]]


class DrogiGraf:
    """Drogi do miejsc patrolu na żywo, BEZ A* (tani tryb cienia w ticku): graf z pliku miejsc (węzły, długości
    odcinków "odl", przejścia pięter, łączniki). Start = węzły na piętrze bota w PROMIEN_STARTU (koszt Chebyshev),
    pola drogi = linie proste między kolejnymi węzłami (przybliżenie przebiegu, długość z grafu). Czas jak Droga."""
    PROMIEN_STARTU = 15

    def __init__(self, dane):
        g = dane["graf"]
        self.wezly = [tuple(w["pole"]) for w in g["wezly"]]
        self.idx = {p: i for i, p in enumerate(self.wezly)}
        self.kraw = {i: [] for i in range(len(self.wezly))}     # i -> [(j, koszt_s)]
        for i, j, dl in g["odl"]:
            self.kraw[i].append((j, dl * KROK_S))
            self.kraw[j].append((i, dl * KROK_S))
        for p in dane.get("przejscia") or ():
            for a, b in ((p["wejscie_gora"], p["wyjscie_dol"]), (p["wejscie_dol"], p["wyjscie_gora"])):
                i, j = self.idx.get(tuple(a)), self.idx.get(tuple(b))
                if i is not None and j is not None:
                    self.kraw[i].append((j, KROK_S + SCHODY_S))
                    self.kraw[j].append((i, KROK_S + SCHODY_S))
        for l in dane.get("laczniki") or ():
            i, j = self.idx.get(tuple(l["od"])), self.idx.get(tuple(l["do"]))
            if i is not None and j is not None:
                kr = max(1, len(l.get("kroki") or ())) * KROK_S
                self.kraw[i].append((j, kr))
                if l.get("dwa_kierunki"):
                    self.kraw[j].append((i, kr))
        self.wezel_miejsca = {m["id"]: self.idx.get((m["x"], m["y"], m["z"])) for m in dane.get("miejsca") or ()}

    @classmethod
    def z_pliku(cls, plik):
        return cls(json.loads(Path(plik).read_text()))

    @staticmethod
    def linia(a, b):
        """Pola na prostej z a do b (bez a), to samo piętro co b."""
        n = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
        return [(a[0] + (b[0] - a[0]) * i // n, a[1] + (b[1] - a[1]) * i // n, b[2]) for i in range(1, n + 1)] if n else []

    def drogi_z(self, poz):
        """{id miejsca: (pola [(x,y,z)], czas_s)}; brak klucza = brak drogi w grafie."""
        import heapq
        poz = tuple(poz)
        odl, poprz, h = {}, {}, []
        for i, p in enumerate(self.wezly):
            if p[2] == poz[2]:
                d = max(abs(p[0] - poz[0]), abs(p[1] - poz[1]))
                if d <= self.PROMIEN_STARTU:
                    odl[i], poprz[i] = d * KROK_S, None
                    heapq.heappush(h, (odl[i], i))
        while h:
            c, i = heapq.heappop(h)
            if c > odl.get(i, 1e18):
                continue
            for j, kc in self.kraw[i]:
                if c + kc < odl.get(j, 1e18):
                    odl[j], poprz[j] = c + kc, i
                    heapq.heappush(h, (c + kc, j))
        wynik = {}
        for mid, w in self.wezel_miejsca.items():
            if w is None or w not in odl:
                continue
            sciezka, j = [], w
            while j is not None:
                sciezka.append(self.wezly[j])
                j = poprz[j]
            sciezka.reverse()
            pola, ost = [], poz
            for q in sciezka:
                pola += self.linia(ost, q) if q[2] == ost[2] else [q]
                ost = q
            wynik[mid] = (pola, odl[w])
        return wynik


def odtworz(rek, droga, miejsca, promien_komorek=0, kom=KOM, swieze=True):
    """Odtwarza telemetrię chronologicznie: mapa obecności rośnie tylko z danych sprzed chwili wyboru,
    przy każdym `patrol_cel` ocenia wszystkie miejsca. Zwraca (mapa, zdarzenia, statystyki)."""
    mo = MapaObecnosci((OBSZAR_RAPORTU[0], OBSZAR_RAPORTU[1], OBSZAR_RAPORTU[2], OBSZAR_RAPORTU[3]),
                       set(PIETRA_RAPORTU), kom=kom)
    mo.swieze = swieze
    zd = []
    ost_poz, ost_gracze, ost_moby = None, [], 0
    otwarte = {}                       # id miejsca -> zdarzenie (czeka na patrol_wizyta)
    ost = None
    for e in rek:
        typ, t = e["typ"], e["t"]
        if typ == "probka":
            if e.get("poz") is None:
                continue
            poz, stw, gr = _probka_na_stwory(e)
            ost_poz, ost_gracze, ost_moby = poz, gr, len(stw) and sum(1 for x in stw if x['nazwa'].lower() in CEL_NAZWY)
            mo.obserwuj(t, poz, stw, CEL_NAZWY)
        elif typ == "epizod_celu":
            if e.get("wynik") == "zabity" and e.get("pos") and ost_poz:
                mo.zabicie(t, e["pos"][0], e["pos"][1], ost_poz[2])
        elif typ == "patrol_cel":
            poz = tuple(e["poz"])
            if ost_poz is None:
                continue
            drogi = droga.drogi_z(poz)
            cele = []
            for mi in miejsca:
                if mi["id"] not in drogi:
                    continue
                pola, czas = drogi[mi["id"]]
                if mi["z"] == poz[2] and max(abs(mi["x"] - poz[0]), abs(mi["y"] - poz[1])) < ODL_MIN_MIEJSCA:
                    continue
                cele.append({"id": mi["id"], "droga": pola, "dojscie_s": czas})
            ev = {"t": t, "poz": poz, "wybor_bota": e["id"], "powod": e.get("powod"), "droga_bota": e.get("droga"),
                  "gracze": len(ost_gracze), "moby_widok": ost_moby, "kandydaci": len(cele), "wizyta": None}
            if cele:
                # wartości przy progu 0 (bez odrzucania): potem filtrujemy progami w analizie
                id0, wart, pew = mo.wybierz(cele, t, ost_gracze, prog=-1.0, promien_komorek=promien_komorek)
                ev["wartosci"] = wart
                ev["nowy"] = id0
                ev["pewnosc"] = pew
                ev["cele"] = {c["id"]: {"dojscie_s": c["dojscie_s"], "pola": len(c["droga"]),
                                        "kom": mo.komorki_celu_i_drogi(c, promien_komorek)} for c in cele}
                # oczekiwane mobów na drodze+celu (bez dzielenia przez czas) i świeżość komórek przy miejscu
                for c in cele:
                    kk = ev["cele"][c["id"]]["kom"]
                    ev["cele"][c["id"]]["oczek"] = sum(mo.oczekiwane(k, t) * mo.kara_gracza(k, ost_gracze) for k in kk)
                    ev["cele"][c["id"]]["gest"] = sum(mo.gestosc(k) for k in kk)
                    ev["cele"][c["id"]]["zegar"] = sum(mo.zegar(k, t) for k in kk)
                    ev["cele"][c["id"]]["n_kom"] = len(kk)
                    mi = next(m for m in miejsca if m["id"] == c["id"])
                    przy = mo.komorki_celu((mi["x"], mi["y"], mi["z"]))
                    refy = [mo.czas_odniesienia(k) for k in przy]
                    z_ref = [t - r for r in refy if r is not None]
                    ev["cele"][c["id"]]["swiezosc"] = (sum(1 for a in z_ref if a < PROG_SWIEZE_S) / len(przy)) if przy else 0.0
                    ev["cele"][c["id"]]["przy_z_ref"] = len(z_ref)
            zd.append(ev)
            otwarte[e["id"]] = ev
            ost = ev
        elif typ == "patrol_wizyta":
            ev = otwarte.pop(e["id"], None)
            if ev is not None and ev["wizyta"] is None:
                ev["wizyta"] = {k: e.get(k) for k in ("dotarl", "powod", "dojscie_s", "na_miejscu_s",
                                                       "zabicia_miejsce", "zabicia_droga")}
    return mo, zd


# --- statystyki do raportu ---

def _kwartyle(l):
    if not l:
        return None
    s = sorted(l)

    def q(p):
        return s[min(len(s) - 1, int(p * (len(s) - 1) + 0.5))]
    return q(0.25), q(0.5), q(0.75), q(0.9)


def _spearman(a, b):
    import numpy as np
    if len(a) < 5:
        return None
    ra, rb = _rangi(a), _rangi(b)
    if ra.std() == 0 or rb.std() == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def _zab(ev):
    w = ev["wizyta"]
    return (w.get("zabicia_miejsce") or 0) + (w.get("zabicia_droga") or 0)


def _rangi(x):
    import numpy as np
    x = np.asarray(x, float)
    o = np.argsort(x, kind="stable")
    r = np.empty(len(x))
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[o[j + 1]] == x[o[i]]:
            j += 1
        r[o[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return r


def _korelacja_czastkowa(x, y, kontrolne):
    """Spearman(x, y) po usunięciu liniowego wpływu rang `kontrolne` (lista wektorów)."""
    import numpy as np
    rx, ry = _rangi(x), _rangi(y)
    if rx.std() == 0 or ry.std() == 0:
        return None
    Z = np.column_stack([np.ones(len(rx))] + [_rangi(k) for k in kontrolne])
    res = lambda v: v - Z @ np.linalg.lstsq(Z, v, rcond=None)[0]
    ex, ey = res(rx), res(ry)
    if ex.std() < 1e-12 or ey.std() < 1e-12:
        return None
    return float(np.corrcoef(ex, ey)[0, 1])


def _baza(wiz):
    """Czy zegar respawnu dodaje cokolwiek ponad prostsze predyktory (długość drogi, gęstość historyczna)?"""
    zab = [_zab(e) for e in wiz]
    cz = [e["cele"][e["wybor_bota"]]["dojscie_s"] for e in wiz]
    ncz = [max(c, MIN_CZAS_DOJSCIA_S) for c in cz]
    wart = [e["wartosci"][e["wybor_bota"]] for e in wiz]
    gest = [e["cele"][e["wybor_bota"]]["gest"] / n for e, n in zip(wiz, ncz)]
    zeg = [e["cele"][e["wybor_bota"]]["zegar"] / n for e, n in zip(wiz, ncz)]
    nkom = [e["cele"][e["wybor_bota"]]["n_kom"] for e in wiz]
    rz = [e["cele"][e["wybor_bota"]]["oczek"] for e in wiz]
    return {"spearman_czas_modelu": _spearman(cz, zab), "spearman_liczba_komorek": _spearman(nkom, zab),
            "spearman_gestosc_na_s": _spearman(gest, zab), "spearman_zegar_na_s": _spearman(zeg, zab),
            "spearman_pelny": _spearman(wart, zab),
            "czastkowa_pelny_po_gest_i_czasie": _korelacja_czastkowa(wart, zab, [gest, cz]),
            "czastkowa_zegar_po_gest_i_czasie": _korelacja_czastkowa(zeg, zab, [gest, cz]),
            "czastkowa_pelny_po_czasie": _korelacja_czastkowa(wart, zab, [cz]),
            "czastkowa_oczek_po_czasie": _korelacja_czastkowa(rz, zab, [cz]),
            "czastkowa_pelny_po_gest_czasie_komorkach": _korelacja_czastkowa(wart, zab, [gest, cz, nkom])}


def analiza(zd, prog_lista=(0.0, 0.05, 0.1, 0.15, 0.25, 0.4), filtr=None):
    """Zbiera liczby symulacji. Ewaluowalne = bot wybrał miejsce osiągalne w modelu i było >= 2 kandydatów."""
    ew = [e for e in zd if e.get("wartosci") and e["wybor_bota"] in e["wartosci"] and len(e["wartosci"]) >= 2
          and (filtr is None or filtr(e))]
    wiz = [e for e in ew if e["wizyta"] and e["wizyta"].get("dojscie_s") is not None]
    wynik = {"zdarzen": len(zd), "ewaluowalne": len(ew), "z_wizyta": len(wiz)}
    # dopasowanie modelu do bota: czy bot idzie tam, gdzie model by poszedł
    roznych = {}
    for p in prog_lista:
        r = sum(1 for e in ew if e["pewnosc"] >= p and e["nowy"] != e["wybor_bota"])
        d = sum(1 for e in ew if e["pewnosc"] >= p)
        roznych[p] = (d, r)
    wynik["progi"] = roznych
    # oczekiwane moby po drodze: wybór bota vs nowy (na tych, gdzie nowy != bot)
    ro = [e for e in ew if e["nowy"] != e["wybor_bota"] and e["nowy"] is not None]
    wynik["rozne_n"] = len(ro)
    if ro:
        ob = [e["cele"][e["wybor_bota"]]["oczek"] for e in ro]
        on = [e["cele"][e["nowy"]]["oczek"] for e in ro]
        vb = [e["wartosci"][e["wybor_bota"]] for e in ro]
        vn = [e["wartosci"][e["nowy"]] for e in ro]
        tb = [e["cele"][e["wybor_bota"]]["dojscie_s"] for e in ro]
        tn = [e["cele"][e["nowy"]]["dojscie_s"] for e in ro]
        wynik["rozne"] = {"oczek_bot": sum(ob) / len(ro), "oczek_nowy": sum(on) / len(ro),
                          "wart_bot": sum(vb) / len(ro), "wart_nowy": sum(vn) / len(ro),
                          "czas_bot": sum(tb) / len(ro), "czas_nowy": sum(tn) / len(ro)}
    wsz_b = [e["cele"][e["wybor_bota"]]["oczek"] for e in ew]
    wsz_n = [e["cele"][e["nowy"]]["oczek"] for e in ew if e["nowy"] is not None]
    wynik["oczek_wsz_bot"] = sum(wsz_b) / len(wsz_b) if wsz_b else None
    wynik["oczek_wsz_nowy"] = sum(wsz_n) / len(wsz_n) if wsz_n else None
    # rozkład wyborów
    # kalibracja: czy wartość modelu wybranego przez bota celu przewiduje faktyczne zabicia wizyty
    if wiz:
        zab = [_zab(e) for e in wiz]
        wr = [e["wartosci"][e["wybor_bota"]] for e in wiz]
        oc = [e["cele"][e["wybor_bota"]]["oczek"] for e in wiz]
        minuty = [max(e["wizyta"]["dojscie_s"] or 0.0, 5.0) / 60.0 for e in wiz]
        zpm = [z / m for z, m in zip(zab, minuty)]
        wynik["baza"] = _baza(wiz)
        wynik["kalibracja"] = {"spearman_wart_zab": _spearman(wr, zab), "spearman_oczek_zab": _spearman(oc, zab),
                               "spearman_wart_zab_na_min": _spearman(wr, zpm),
                               "srednie_zab": sum(zab) / len(zab), "n": len(zab)}
        # kwartyle wartości wybranego celu -> średnie zabicia i zabicia/min dojścia
        porz = sorted(range(len(wiz)), key=lambda i: wr[i])
        q = []
        for k in range(4):
            idx = porz[k * len(porz) // 4:(k + 1) * len(porz) // 4]
            if not idx:
                continue
            q.append({"od": wr[idx[0]], "do": wr[idx[-1]], "n": len(idx),
                      "zab": sum(zab[i] for i in idx) / len(idx),
                      "zab_na_min": sum(zab[i] for i in idx) / max(sum(minuty[i] for i in idx), 1e-9)})
        wynik["kwartyle_wartosci"] = q
        # szacunek górny: zabicia/min dojścia odczytane z kwartyli wartości dla wyboru bota vs nowego (ekstrapolacja
        # z korelacji, zakłócona długością drogi; NIE jest prognozą zysku)
        def przewid(v):
            for qq in q:
                if v <= qq["do"]:
                    return qq["zab_na_min"]
            return q[-1]["zab_na_min"]
        rozne_w = [e for e in ew if e["nowy"] is not None and e["nowy"] != e["wybor_bota"]]
        if rozne_w and len(q) == 4:
            wynik["szacunek"] = {"n": len(rozne_w),
                                 "bot": sum(przewid(e["wartosci"][e["wybor_bota"]]) for e in rozne_w) / len(rozne_w),
                                 "nowy": sum(przewid(e["wartosci"][e["nowy"]]) for e in rozne_w) / len(rozne_w)}
        # ratio: wartość wyboru bota / najlepsza wartość w modelu; trzy przedziały
        rat = sorted(range(len(wiz)), key=lambda i: wr[i] / max(max(wiz[i]["wartosci"].values()), 1e-12))
        biny = []
        for k in range(3):
            idx = rat[k * len(rat) // 3:(k + 1) * len(rat) // 3]
            if not idx:
                continue
            rr = [wr[i] / max(max(wiz[i]["wartosci"].values()), 1e-12) for i in idx]
            biny.append({"od": min(rr), "do": max(rr), "n": len(idx),
                         "zab": sum(zab[i] for i in idx) / len(idx),
                         "zab_na_min": sum(zab[i] for i in idx) / max(sum(minuty[i] for i in idx), 1e-9),
                         "puste": sum(1 for i in idx if zab[i] == 0) / len(idx)})
        wynik["biny_ratio"] = biny
        # zgodność z modelem: bot wybrał to, co model; kontra reszta
        zg = [e for e in wiz if e["nowy"] == e["wybor_bota"]]
        nz = [e for e in wiz if e["nowy"] != e["wybor_bota"]]

        def opis(l):
            if not l:
                return None
            z = sum(_zab(e) for e in l)
            m = sum(max(e["wizyta"]["dojscie_s"] or 0.0, 5.0) for e in l) / 60.0
            return {"n": len(l), "zab_na_wizyte": z / len(l), "zab_na_min": z / m,
                    "pusta_czesc": sum(1 for e in l if _zab(e) == 0) / len(l)}
        wynik["zgodne"], wynik["niezgodne"] = opis(zg), opis(nz)
        # ranga wyboru bota w rankingu modelu vs zabicia
        rang = []
        for e in wiz:
            porz2 = sorted(e["wartosci"], key=lambda i: e["wartosci"][i], reverse=True)
            rang.append(porz2.index(e["wybor_bota"]) + 1)
        wynik["spearman_ranga_zab"] = _spearman([-r for r in rang], zab)
        # świeżość: wizyty bota w miejsca świeżo wyczyszczone
        sw = [e for e in wiz if e["cele"][e["wybor_bota"]]["przy_z_ref"] > 0
              and e["cele"][e["wybor_bota"]]["swiezosc"] >= 0.5]
        nsw = [e for e in wiz if e not in sw and e["cele"][e["wybor_bota"]]["przy_z_ref"] > 0]
        wynik["swieze"] = opis(sw)
        wynik["nieswieze"] = opis(nsw)
        wynik["swieze_nowy"] = sum(1 for e in ew if e["nowy"] is not None and e["cele"][e["nowy"]]["przy_z_ref"] > 0
                                   and e["cele"][e["nowy"]]["swiezosc"] >= 0.5)
        wynik["swieze_bot_wsz"] = sum(1 for e in ew if e["cele"][e["wybor_bota"]]["przy_z_ref"] > 0
                                      and e["cele"][e["wybor_bota"]]["swiezosc"] >= 0.5)
        wynik["z_ref_bot"] = sum(1 for e in ew if e["cele"][e["wybor_bota"]]["przy_z_ref"] > 0)
        # kalibracja czasu: faktyczny dojscie_s vs model (pola x 0,4 + schody) dla wizyt bez zabić, które dotarły
        rat = []
        for e in wiz:
            w = e["wizyta"]
            if w.get("dotarl") and _zab(e) == 0 and w.get("dojscie_s") and e["cele"][e["wybor_bota"]]["dojscie_s"] > 0:
                rat.append(w["dojscie_s"] / e["cele"][e["wybor_bota"]]["dojscie_s"])
        wynik["czas_rzecz_do_modelu"] = _kwartyle(rat)
        wynik["czas_rzecz_n"] = len(rat)
    return wynik


def wariant(nazwa, zd, filtr=None):
    """Zwięzła linia porównawcza wariantu: sygnał i różnica wyboru."""
    an = analiza(zd, filtr=filtr)
    k = an.get("kalibracja") or {}
    zg, nz = an.get("zgodne"), an.get("niezgodne")
    d, r = an["progi"][0.0]
    d2, r2 = an["progi"][PEWNOSC_MIN]
    return {"nazwa": nazwa, "n": an["z_wizyta"], "spearman": k.get("spearman_wart_zab"),
            "spearman_min": k.get("spearman_wart_zab_na_min"),
            "zg": zg, "nz": nz, "rozne": (100.0 * r / d) if d else None,
            "decyzje_pewne": d2, "rozne_pewne": (100.0 * r2 / d2) if d2 else None}


def zbuduj_statystyki_mapy(mo):
    """Gęstość top, kwartyle respawnu (wszystkie / dokładne / luka), respawn per komórka."""
    kom = []
    for key, c in mo.k.items():
        if c.czas_widoku < DANE_MIN_S:
            continue
        kom.append((key, mo.gestosc(key), c))
    kom.sort(key=lambda a: a[1], reverse=True)
    wszystkie = [p[0] for c in mo.k.values() for p in c.przypadki]
    dokl = [p[0] for c in mo.k.values() for p in c.przypadki if p[1]]
    luka = [p[0] for c in mo.k.values() for p in c.przypadki if not p[1]]
    per_kom = []
    for key, c in mo.k.items():
        if len(c.przypadki) >= RESPAWN_MIN_PRZYPADKOW:
            per_kom.append((key, mediana([p[0] for p in c.przypadki]), len(c.przypadki)))
    return {"gestosc": kom, "przyp_wsz": wszystkie, "przyp_dokl": dokl, "przyp_luka": luka, "per_kom": per_kom}


def _f(x, n=2):
    return "-" if x is None else f"{x:.{n}f}"


def raport_md(pliki, rek, zle, mo, zd, an, st, warianty=()):
    probki = sum(1 for e in rek if e["typ"] == "probka")
    sesje = len({(e.get("pid"), e.get("sesja")) for e in rek if e["typ"] == "probka"})
    L = []
    L.append("# Raport: mapa obecności i patrol według respawnu (15.10, krok 1)")
    L.append("")
    L.append("Wygenerowany przez `python3 -I obecnosc.py --raport` (tylko odczyt telemetrii). Bot się nie zmienia.")
    L.append("")
    L.append("## 1. Dane")
    L.append("")
    L.append(f"- Pliki: {', '.join(pliki)}; rekordy użyte: {len(rek)} (uszkodzonych linii: {zle}); próbek: {probki}; sesji: {sesje}.")
    L.append(f"- Obszar: x {OBSZAR_RAPORTU[0]}-{OBSZAR_RAPORTU[2]}, y {OBSZAR_RAPORTU[1]}-{OBSZAR_RAPORTU[3]}, z {PIETRA_RAPORTU[0]}-{PIETRA_RAPORTU[1]}; "
             f"komórki {KOM}x{KOM}, widok {2 * WIDOK[0] + 1}x{2 * WIDOK[1] + 1} pól; cele-moby: {', '.join(sorted(CEL_NAZWY))}.")
    L.append(f"- Komórek z danymi (>= {DANE_MIN_S:.0f} s w widoku): {len(st['gestosc'])}; zabić przypisanych komórkom: "
             f"{sum(c.zabicia for c in mo.k.values())}.")
    w_jask = [e for e in zd if e.get("wartosci")]
    dni = sorted({time.strftime("%d.%m", time.localtime(e["t"])) for e in w_jask})
    L.append(f"- Zdarzeń `patrol_cel` w jaskini (miejsca m1..m8 osiągalne z pozycji bota): {len(w_jask)} z {len(zd)} (dni: {', '.join(dni)}); "
             f"pozostałe to patrol poza jaskinią (miasto, inne piętra), pomijane.")
    L.append("")
    L.append("## 2. Gęstość (średnia liczba trolli w komórce, gdy była w widoku)")
    L.append("")
    L.append("Wygładzona wartością domyślną (waga %.0f s). Uwaga: to gęstość stanu faktycznego, z udziałem zabić bota "
             "(bot sam czyści komórki, więc wartości są lekko zaniżone)." % GEST_WAGA_S)
    L.append("")
    L.append("| komórka (x,y,z) lewy-górny róg | gęstość | czas w widoku [min] | zabicia | respawn mediana [s] |")
    L.append("|---|---|---|---|---|")
    for key, g, c in st["gestosc"][:15]:
        L.append(f"| ({key[0] * KOM},{key[1] * KOM},z{key[2]}) | {g:.2f} | {c.czas_widoku / 60:.0f} | {c.zabicia} | "
                 f"{_f(mo.respawn(key), 0)}{'' if len(c.przypadki) >= RESPAWN_MIN_PRZYPADKOW else ' (domyślny/globalny)'} |")
    L.append("")
    L.append("## 3. Respawn (czas od wyczyszczenia komórki do następnego moba w niej)")
    L.append("")
    L.append("Start odliczania: pierwsza obserwacja komórki w widoku i pustej po tym, jak był w niej mob (albo zabicie); "
             "koniec: następna obserwacja moba w komórce. Tylko komórki, które bot widział (w całości w widoku). "
             "Przypadek \"dokładny\" = bot patrzył na komórkę ciągle (przerwy <= %.0f s), \"luka\" = bot wrócił po czasie, więc "
             "to górne ograniczenie (mob mógł się pojawić wcześniej, a nawet wejść i wyjść). Moby wchodzące z sąsiednich komórek "
             "też liczą się jako powrót obecności. Przypadki krótsze niż %.0f s odrzucam (to sąsiad z grupy, nie respawn); "
             "liczba dokładnych przypadków po filtrze jest niska, a rozkład dwumodalny, więc prawdziwy czas respawnu jest tylko "
             "przybliżony (UNKNOWN dokładnie)." % (DOKLADNA_LUKA_S, PRZYPADEK_MIN_S))
    L.append("")
    L.append("| zbiór | przypadków | Q1 [s] | mediana [s] | Q3 [s] | P90 [s] |")
    L.append("|---|---|---|---|---|---|")
    for nazwa, l in (("wszystkie", st["przyp_wsz"]), ("dokładne (ciągły widok)", st["przyp_dokl"]), ("z luką w widoku", st["przyp_luka"])):
        q = _kwartyle(l)
        L.append(f"| {nazwa} | {len(l)} | " + (" | ".join(f"{v:.0f}" for v in q) if q else "- | - | - | -") + " |")
    L.append("")
    pk = st["per_kom"]
    if pk:
        med = _kwartyle([m for _, m, _ in pk])
        L.append(f"Komórek z własnym respawnem (>= {RESPAWN_MIN_PRZYPADKOW} przypadków): {len(pk)}; kwartyle ich median "
                 f"(Q1/mediana/Q3/P90): " + "/".join(f"{v:.0f}" for v in med) + " s.")
    else:
        L.append("Żadna komórka nie ma jeszcze wystarczająco przypadków na własny respawn.")
    L.append(f"Respawn globalny używany przez model: {_f(mo._respawn_globalny(), 0)} s (domyślny {RESPAWN_DOMYSLNY_S:.0f} s).")
    L.append("")
    L.append("## 4. Symulacja wyboru celu patrolu")
    L.append("")
    L.append("Dla każdego historycznego `patrol_cel` odtwarzam mapę obecności z danych WYŁĄCZNIE sprzed tej chwili "
             "(próbki, zabicia z `epizod_celu`) i oceniam wszystkie miejsca z `trasy/miejsca_troll.json` (m1..m8).")
    L.append("")
    L.append("Założenia (uczciwie):")
    L.append(f"- Droga: A* z `mapa.py` (pola przechodnie z minimapy + `znane_pola.json`) na piętrze do węzłów grafu, dalej graf z pliku miejsc "
             f"(`graf.odl`, `przejscia`, `laczniki`) algorytmem Dijkstry. Czas = pola x {KROK_S} s + {SCHODY_S:.0f} s za przejście pięter. "
             f"Miejsca bliżej niż {ODL_MIN_MIEJSCA} pola od bota odpadają (jak `PATROL_ODL_MIN`); reszty reguł bota "
             f"(ostatnie 4 wizyty, runda, gniazda wymagające HP/many, blokady) NIE odtwarzam, więc nowa metoda ma tu więcej swobody niż bot.")
    L.append(f"- Wartość = suma oczekiwanych mobów w unikalnych komórkach drogi i miejsca (promień {CEL_PROMIEN} pól) / max(czas, {MIN_CZAS_DOJSCIA_S:.0f} s), "
             f"komórka przy obcym graczu (<= {GRACZ_PROMIEN} pól) x {GRACZ_KARA}. Pewność = udział komórek z danymi x przewaga nad drugim; "
             f"próg domyślny {PEWNOSC_MIN}.")
    L.append("- Mapa uczy się w trakcie odtwarzania: początek (pierwsze godziny) to mapa prawie pusta (gęstość domyślna), więc "
             "wartości z początku są słabe i pewność niska.")
    L.append("- Kontrfaktycznego wyniku (ile zabić dałby inny wybór) NIE znamy: wiemy tylko, co się stało po wyborze bota. "
             "Stąd ocena pośrednia: kalibracja (czy wartość modelu przewiduje zabicia wizyt bota) i zgodny/niezgodny z modelem.")
    L.append("")
    L.append(f"- Zdarzeń `patrol_cel`: {an['zdarzen']}; ewaluowalnych (wybór bota osiągalny w modelu, >= 2 kandydatów): {an['ewaluowalne']}; "
             f"z wynikiem wizyty: {an['z_wizyta']}.")
    L.append("")
    L.append("### 4a. Czy nowa metoda wybrałaby inaczej")
    L.append("")
    L.append("| próg pewności | zdarzeń z pewnością >= próg | wybrałaby inne miejsce niż bot | odsetek |")
    L.append("|---|---|---|---|")
    for p, (d, r) in an["progi"].items():
        L.append(f"| {p:.2f} | {d} | {r} | {_f(100.0 * r / d if d else None, 0)}% |")
    L.append("")
    L.append("### 4b. Oczekiwane moby po drodze i przy miejscu (wg samego modelu, więc to nie dowód na rzeczywiste zabicia)")
    L.append("")
    if an.get("rozne"):
        r = an["rozne"]
        L.append(f"W {an['rozne_n']} zdarzeniach, gdzie nowy wybór != wybór bota (bez progu pewności):")
        L.append("")
        L.append("| | oczekiwane moby na drodze+miejscu | wartość (moby/s) | czas dojścia (model) [s] |")
        L.append("|---|---|---|---|")
        L.append(f"| wybór bota | {r['oczek_bot']:.2f} | {r['wart_bot']:.4f} | {r['czas_bot']:.0f} |")
        L.append(f"| nowa metoda | {r['oczek_nowy']:.2f} | {r['wart_nowy']:.4f} | {r['czas_nowy']:.0f} |")
        L.append("")
    L.append(f"Średnio oczekiwanych mobów na drodze+miejscu (wszystkie ewaluowalne): bot {_f(an['oczek_wsz_bot'])}, nowa {_f(an['oczek_wsz_nowy'])}.")
    L.append("Nowa metoda z definicji maksymalizuje wartość (moby/s), więc ta tabela pokazuje tylko, jak duża jest różnica "
             "w oczach modelu, nie czy model ma rację.")
    L.append("")
    if "kalibracja" in an:
        k = an["kalibracja"]
        L.append("### 4c. Czy model ma sygnał: wartość wybranego przez bota celu a faktyczne zabicia wizyty")
        L.append("")
        L.append(f"Wizyt z wynikiem: {k['n']}, średnio {k['srednie_zab']:.2f} zabić na wizytę (na miejscu + w drodze).")
        L.append(f"- Spearman(wartość modelu, zabicia wizyty) = {_f(k['spearman_wart_zab'], 3)}; "
                 f"(oczekiwane moby, zabicia) = {_f(k['spearman_oczek_zab'], 3)}; "
                 f"(wartość, zabicia na minutę dojścia) = {_f(k['spearman_wart_zab_na_min'], 3)}; "
                 f"(ranga wyboru bota w rankingu modelu, zabicia) = {_f(an['spearman_ranga_zab'], 3)}.")
        L.append("")
        L.append("| kwartyl wartości wybranego celu | zakres wartości | wizyt | zabicia / wizyta | zabicia / min dojścia |")
        L.append("|---|---|---|---|---|")
        for i, q in enumerate(an["kwartyle_wartosci"], 1):
            L.append(f"| Q{i} | {q['od']:.4f} - {q['do']:.4f} | {q['n']} | {q['zab']:.2f} | {q['zab_na_min']:.2f} |")
        L.append("")
        L.append("| wybór bota względem modelu | wizyt | zabicia / wizyta | zabicia / min dojścia | wizyt bez zabicia |")
        L.append("|---|---|---|---|---|")
        for nazwa, o in (("zgodny z modelem (model wybrałby to samo)", an["zgodne"]), ("niezgodny z modelem", an["niezgodne"])):
            if o:
                L.append(f"| {nazwa} | {o['n']} | {o['zab_na_wizyte']:.2f} | {o['zab_na_min']:.2f} | {100 * o['pusta_czesc']:.0f}% |")
        L.append("")
        b = an["baza"]
        L.append("Kontrola zakłócenia: kto jeszcze przewiduje zabicia wizyty?")
        L.append("")
        L.append("| predyktor | Spearman z zabiciami wizyty |")
        L.append("|---|---|")
        for nazwa, k_ in (("sam czas dojścia wg modelu (dłuższa droga = więcej walk)", "spearman_czas_modelu"),
                          ("liczba komórek na drodze i przy miejscu", "spearman_liczba_komorek"),
                          ("tylko gęstość historyczna / czas (bez zegara respawnu)", "spearman_gestosc_na_s"),
                          ("tylko zegar respawnu / czas (bez gęstości)", "spearman_zegar_na_s"),
                          ("pełna wartość modelu", "spearman_pelny")):
            L.append(f"| {nazwa} | {_f(b[k_], 3)} |")
        L.append("")
        L.append("Korelacja cząstkowa (po odjęciu liniowego wpływu rang wymienionych zmiennych):")
        L.append("")
        L.append(f"- pełna wartość | czas dojścia: {_f(b['czastkowa_pelny_po_czasie'], 3)}; | gęstość i czas: {_f(b['czastkowa_pelny_po_gest_i_czasie'], 3)}; "
                 f"| gęstość, czas i liczba komórek: {_f(b['czastkowa_pelny_po_gest_czasie_komorkach'], 3)}.")
        L.append(f"- sam zegar respawnu | gęstość i czas: {_f(b['czastkowa_zegar_po_gest_i_czasie'], 3)}.")
        L.append("")
        L.append("Wybór bota względem najlepszej wartości modelu (trzy równe przedziały stosunku wartość_bota / wartość_najlepsza):")
        L.append("")
        L.append("| przedział stosunku | wizyt | zabicia / wizyta | zabicia / min dojścia | wizyt bez zabicia |")
        L.append("|---|---|---|---|---|")
        for q_ in an.get("biny_ratio", []):
            L.append(f"| {q_['od']:.2f} - {q_['do']:.2f} | {q_['n']} | {q_['zab']:.2f} | {q_['zab_na_min']:.2f} | {100 * q_['puste']:.0f}% |")
        L.append("")
        if an.get("szacunek"):
            e_ = an["szacunek"]
            L.append(f"Szacunek górny (ekstrapolacja z kwartyli, zakłócona długością drogi, NIE prognoza): w {e_['n']} zdarzeniach z innym wyborem "
                     f"przewidywane zabicia/min dojścia: bot {e_['bot']:.2f}, nowa metoda {e_['nowy']:.2f} "
                     f"({100.0 * (e_['nowy'] / e_['bot'] - 1):+.0f}%). Dojścia to ok. 35% czasu, więc w exp/h zysk byłby wielokrotnie mniejszy; "
                     f"offline nie da się go policzyć wiarygodnie, bo wynik innego wyboru jest nieznany.")
            L.append("")
        L.append("### 4d. Wizyty w komórki świeżo wyczyszczone (< %.0f s)" % PROG_SWIEZE_S)
        L.append("")
        L.append("Świeże = co najmniej połowa komórek przy miejscu ma czas odniesienia (ostatnio pusta w widoku / po zabiciu) młodszy "
                 "niż 300 s. Liczone tam, gdzie mapa ma w ogóle jakąś informację o komórkach miejsca.")
        L.append("")
        L.append(f"- Wizyt bota z informacją o komórkach miejsca: {an['z_ref_bot']}; z tego świeżych: {an['swieze_bot_wsz']}; "
                 f"nowa metoda wybrałaby świeże: {an['swieze_nowy']} razy (na tych samych zdarzeniach).")
        L.append("")
        L.append("| wizyty bota | wizyt | zabicia / wizyta | zabicia / min dojścia | wizyt bez zabicia |")
        L.append("|---|---|---|---|---|")
        for nazwa, o in (("do świeżo wyczyszczonych", an["swieze"]), ("do pozostałych (z informacją)", an["nieswieze"])):
            if o:
                L.append(f"| {nazwa} | {o['n']} | {o['zab_na_wizyte']:.2f} | {o['zab_na_min']:.2f} | {100 * o['pusta_czesc']:.0f}% |")
        L.append("")
        L.append("### 4e. Kalibracja czasu dojścia")
        L.append("")
        q = an.get("czas_rzecz_do_modelu")
        if q:
            L.append(f"Stosunek faktycznego `dojscie_s` do czasu modelu (pola x {KROK_S} s + schody) dla wizyt, które dotarły i "
                     f"nie miały zabić ({an['czas_rzecz_n']}): Q1/mediana/Q3/P90 = " + "/".join(f"{v:.2f}" for v in q) + ".")
        L.append("")
    if warianty:
        L.append("### 4f. Warianty i kontrola zakłócenia")
        L.append("")
        L.append("Zakłócenie: bot wybiera miejsce zwykle zaraz po walce, gdy trolle są w widoku i na drodze, więc sama obecność "
                 "mobów w widoku \"przewiduje\" kolejne zabicia, bez żadnego zegara respawnu. Stąd warianty: `bez świeżych` = "
                 "model bez wzmocnienia komórek ze świeżym mobem (został tylko zegar od wyczyszczenia i gęstość); "
                 "`widok pusty` = tylko zdarzenia, gdy w chwili wyboru w widoku nie było żadnego trolla; `promień 1` = droga "
                 "rozszerzona o sąsiednie komórki.")
        L.append("")
        L.append("| wariant | wizyt | Spearman(wartość, zabicia) | Spearman(wartość, zab./min) | zgodne zab./min (n) | niezgodne zab./min (n) | inny wybór niż bot | decyzji pewnych / z nich inny wybór |")
        L.append("|---|---|---|---|---|---|---|---|")
        for w in warianty:
            zg = f"{w['zg']['zab_na_min']:.2f} ({w['zg']['n']})" if w["zg"] else "-"
            nz = f"{w['nz']['zab_na_min']:.2f} ({w['nz']['n']})" if w["nz"] else "-"
            L.append(f"| {w['nazwa']} | {w['n']} | {_f(w['spearman'], 3)} | {_f(w['spearman_min'], 3)} | {zg} | {nz} | "
                     f"{_f(w['rozne'], 0)}% | {w['decyzje_pewne']} / {_f(w['rozne_pewne'], 0)}% |")
        L.append("")
    return "\n".join(L)


def wnioski(an, st, warianty=()):
    """Wnioski wyprowadzone z liczb (bez przesądzania)."""
    L = ["## 5. Wnioski (z liczb powyżej)", ""]
    k = an.get("kalibracja")
    if not k:
        return "\n".join(L + ["Brak wizyt z wynikiem: nie da się ocenić sygnału."])
    b = an["baza"]
    zg, nz = an.get("zgodne"), an.get("niezgodne")
    sw, nsw = an.get("swieze"), an.get("nieswieze")
    kw = an.get("kwartyle_wartosci") or []
    L.append(f"- Wartość modelu wybranego przez bota celu koreluje z zabiciami wizyty (Spearman {_f(k['spearman_wart_zab'], 3)}), "
             f"ale sama długość drogi koreluje podobnie ({_f(b['spearman_czas_modelu'], 3)}): dłuższe dojście = więcej walk po drodze. "
             f"Po odjęciu wpływu czasu i gęstości zostaje {_f(b['czastkowa_pelny_po_gest_i_czasie'], 3)} (zegar respawnu sam: "
             f"{_f(b['czastkowa_zegar_po_gest_i_czasie'], 3)}).")
    L.append(f"- Gęstość historyczna bez zegara prawie nic nie przewiduje ({_f(b['spearman_gestosc_na_s'], 3)}), zegar respawnu bez gęstości "
             f"więcej ({_f(b['spearman_zegar_na_s'], 3)}): czas od wyczyszczenia niesie informację, której stały rozkład gęstości nie ma.")
    if len(kw) == 4:
        L.append(f"- Zabicia/wizyta w kwartylach wartości: Q1 {kw[0]['zab']:.2f}, Q2 {kw[1]['zab']:.2f}, Q3 {kw[2]['zab']:.2f}, Q4 {kw[3]['zab']:.2f}; "
                 f"na minutę dojścia: {kw[0]['zab_na_min']:.2f} / {kw[1]['zab_na_min']:.2f} / {kw[2]['zab_na_min']:.2f} / {kw[3]['zab_na_min']:.2f}.")
    if zg and nz:
        L.append(f"- Wizyty zgodne z modelem: {zg['zab_na_min']:.2f} zabić/min dojścia (n={zg['n']}), niezgodne: {nz['zab_na_min']:.2f} (n={nz['n']}).")
    if sw and nsw:
        L.append(f"- Do świeżo wyczyszczonych (< {PROG_SWIEZE_S:.0f} s): {sw['zab_na_wizyte']:.2f} zab./wizyta, {100 * sw['pusta_czesc']:.0f}% bez zabicia (n={sw['n']}); "
                 f"do pozostałych: {nsw['zab_na_wizyte']:.2f}, {100 * nsw['pusta_czesc']:.0f}% bez zabicia (n={nsw['n']}).")
    L.append("")
    if an.get("szacunek"):
        e_ = an["szacunek"]
        L.append(f"- Nowa metoda wybrałaby inne miejsce niż bot w {100.0 * an['progi'][0.0][1] / max(an['progi'][0.0][0], 1):.0f}% zdarzeń "
                 f"(przy progu pewności {PEWNOSC_MIN}: {100.0 * an['progi'][PEWNOSC_MIN][1] / max(an['progi'][PEWNOSC_MIN][0], 1):.0f}% z {an['progi'][PEWNOSC_MIN][0]} decyzji), "
                 f"czyli często; szacunek górny zysku na minutę dojścia {100.0 * (e_['nowy'] / e_['bot'] - 1):+.0f}%.")
        L.append("")
    sygnal = b["czastkowa_pelny_po_gest_i_czasie"] is not None and b["czastkowa_pelny_po_gest_i_czasie"] >= 0.15
    L.append("Werdykt: " + (
        "model ma WALIDACJĘ PREDYKCYJNĄ (wartość przewiduje zabicia ponad samą długość drogi i gęstość), ale to NIE jest pomiar zysku: "
        "wyniku innego wyboru nie znamy, a bot wybierał własnymi regułami (blisko, po wagach), więc część sygnału to "
        "pamięć tego, gdzie trolle niedawno były w drodze bota. Zysk w exp/h rozstrzygnie dopiero tryb cienia, a potem A/B (krok 3)."
        if sygnal else
        "symulacja NIE pokazuje wyraźnego zysku (po odjęciu długości drogi i gęstości nie zostaje sygnał); to nie dowód, że metoda nie "
        "zadziała (kontrfaktyk jest nieznany), ale uzasadnienia do włączenia nie ma. Tryb cienia zbierze dane do rozstrzygnięcia."))
    L.append("")
    L.append("Ograniczenia: wynik wizyty zależy też od walk w drodze, których wybór miejsca nie kontroluje; odtwarzam tylko część reguł bota; "
             "zabicia liczone z `epizod_celu` (pozycja zabitego), moby z próbek co ~1-5 s; respawn jest tylko przybliżony (patrz sekcja 3); "
             "mapa uczy się w trakcie na tych samych danych, na których ocenia (kauzalnie: tylko dane sprzed chwili wyboru, "
             "ale początek to mapa prawie pusta); dwa dni danych, jedna jaskinia.")
    return "\n".join(L)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="Mapa obecności: raport offline z telemetrii")
    ap.add_argument("--raport", action="store_true", help="zbuduj raport md z telemetrii")
    ap.add_argument("--logi", default=str(KAT / "logi"), help="katalog z telemetria-*.jsonl (tylko odczyt)")
    ap.add_argument("--wyjscie", default=str(KAT / "dane_tibia" / "RAPORT_obecnosc_1015.md"))
    ap.add_argument("--miejsca", default=str(KAT / "trasy" / "miejsca_troll.json"))
    ap.add_argument("--promien-komorek", type=int, default=0, help="rozszerz drogę o sąsiednie komórki (0 = tylko droga)")
    a = ap.parse_args(argv)
    if not a.raport:
        ap.print_help()
        return 2
    import time
    sys.path.insert(0, str(KAT))
    t0 = time.time()
    rek, pliki, zle = _wczytaj_rekordy(a.logi)
    if not rek:
        print(f"brak telemetrii w {a.logi}", file=sys.stderr)
        return 1
    droga = Droga(a.miejsca, KAT / "znane_pola.json")
    mo, zd = odtworz(rek, droga, droga.miejsca, a.promien_komorek)
    an = analiza(zd)
    st = zbuduj_statystyki_mapy(mo)
    _, zd_bs = odtworz(rek, droga, droga.miejsca, a.promien_komorek, swieze=False)
    _, zd_r1 = odtworz(rek, droga, droga.miejsca, 1)
    _, zd_r1bs = odtworz(rek, droga, droga.miejsca, 1, swieze=False)
    pusty = lambda e: e["moby_widok"] == 0
    t_med = mediana([e["t"] for e in zd if e.get("wartosci")]) or 0.0
    warianty = [wariant("model pełny (jak raport)", zd),
                wariant("bez świeżych", zd_bs),
                wariant("pełny, widok pusty", zd, pusty),
                wariant("bez świeżych, widok pusty", zd_bs, pusty),
                wariant("pełny, pierwsza połowa zdarzeń", zd, lambda e: e["t"] < t_med),
                wariant("pełny, druga połowa zdarzeń", zd, lambda e: e["t"] >= t_med),
                wariant("promień 1", zd_r1),
                wariant("promień 1, bez świeżych, widok pusty", zd_r1bs, pusty)]
    md = raport_md(pliki, rek, zle, mo, zd, an, st, warianty) + "\n" + wnioski(an, st, warianty) + "\n"
    out = Path(a.wyjscie)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"zapisano {out} ({len(md)} B, {time.time() - t0:.1f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
