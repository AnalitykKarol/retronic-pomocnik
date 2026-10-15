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
import json
import math
import os
import time
from pathlib import Path

import bot

try:
    import wypad
except Exception:       # wypad nigdy nie wywraca bota
    wypad = None


# 13.10: pole startowe (ortogonalne do schodów), z którego przejście wyszło; per schody, klucz "x,y,z" pola T.
# W testach (RETRONIC_TESTY) bez zapisu, chyba że test sam ustawi PLIK_STARTOW.
PLIK_STARTOW = None if os.environ.get("RETRONIC_TESTY") else Path(__file__).resolve().parent / "trasy" / "pietra_start.json"
PLIK_ZLYCH = (Path(PLIK_STARTOW).with_name("pietra_zle.json") if PLIK_STARTOW is not None else None)  # 14.10: pola startowe, które nie dały ruchu
PLIK_STARTOW_DOMYSLNE = (None if os.environ.get("RETRONIC_TESTY")       # 14.10 (R1b): zasiane dobre pola startowe, tylko do odczytu
                         else Path(__file__).resolve().parent / "trasy" / "pietra_starty_domyslne.json")
START_KROK_NIE_MAX = 2              # tyle nieudanych kroków strzałką (postać stoi w miejscu) na pole startowe, potem je pomijamy
START_RUCHY_MAX = 8                 # ticków na dojście do jednego pola startowego, potem je pomijamy
PRE_SUMA_MAX = 2                    # 14.10 (R1b-fix): najwyżej tyle pre-kroków strzałką łącznie na jedno przejście (przy schodach T), potem próbujemy stąd
SKOS_MAX = 2                        # 14.10 (R1b-fix): najwyżej tyle kroków/kliknięć "po skosie" na pole przejścia w jednym przejściu; potem slot kroku jest spalony
# 14.10 (R1b-fix): statystyki udanych przejść z 12 h (który tryb zadziałał w górę); typ przejścia wg danych ma pierwszeństwo przed flagami mapy
PLIK_STAT = Path(__file__).resolve().parent / "dane_tibia" / "ruch" / "pietra_statystyki_przejsc.json"
_STAT = None


def _statystyki():
    global _STAT
    if _STAT is None:
        _STAT = {}
        try:
            if PLIK_STAT is not None and Path(PLIK_STAT).exists():
                for e in json.loads(Path(PLIK_STAT).read_text()):
                    _STAT[(int(e["pole"][0]), int(e["pole"][1]), int(e["z_od"]))] = e.get("tryby") or {}
        except Exception:
            _STAT = {}
    return _STAT


def tryb_z_danych(pole, min_n=3):
    """Tryb, który w danych (pietra_statystyki_przejsc.json) działał przy przejściu z piętra pole[2] przez pole[:2]:
    "R" (Ctrl+klik, drabina), "krok" (schody) albo None (brak danych albo remis)."""
    tr = _statystyki().get((int(pole[0]), int(pole[1]), int(pole[2])))
    if not tr:
        return None
    r, k = int(tr.get("R", 0)), int(tr.get("krok", 0))
    if r >= min_n and r > k:
        return "R"
    if k >= min_n and k > r:
        return "krok"
    return None


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _flaga(mapa, x, y, z):
    try:
        return int(mapa.flagi(x, y, z)) if mapa is not None and z >= 0 else 0
    except Exception:
        return 0


def _schody(mapa, pole, lad):
    """Typ "schody" (14.10, R1b): pole przejścia ma flagę 2 na obu piętrach (schody (32498,32270) z8 i z9), więc krok
    działa w obie strony. `pole` to pole T na piętrze startu, `lad` lądowanie (inne piętro, tylko x,y i z się liczą)."""
    if mapa is None:
        return False
    return bool(_flaga(mapa, pole[0], pole[1], pole[2]) & 2 and _flaga(mapa, pole[0], pole[1], lad[2]) & 2)


def _domysl_ok(mapa, pole, poz, promien, flaga_tu, flaga_nad):
    """Czy kandydat "domysł" `pole` przechodzi sprawdzenie R1b. Bez promienia (0) albo bez pozycji gracza: zawsze (dawne).
    `flaga_tu` = bit wymagany na polu (w dół 2 = dziura; w górę 1 = chodliwe), `flaga_nad` = bit wymagany piętro wyżej
    (w górę 2 = dziura nad R); bez mapy sprawdzamy tylko promień."""
    if not promien or poz is None:
        return True
    if cheb(pole, poz) > promien:
        return False
    if mapa is None:
        return True
    f = _flaga(mapa, pole[0], pole[1], pole[2])
    if f & 4 or not f & flaga_tu:
        return False
    return not flaga_nad or bool(_flaga(mapa, pole[0], pole[1], pole[2] - 1) & flaga_nad)


def kandydaci(mapa, a, b, poz=None, promien=0):
    """Pola, którymi da się przejść z `a` (stoimy tu, piętro a[2]) na punkt `b` (inne piętro).
    Lista słowników {"pole": (x, y, z) na piętrze a, "pewne": bool, "lad": (x, y, z) lądowanie}, najlepsze pierwsze.
    Brak mapy = tylko założenie z wypad.py (dziura pod b / lina na (b.x, b.y-1)).
    R1b: z `promien` > 0 i `poz` (pozycja gracza) kandydat "domysł" (poza pewnymi z mapy) jest tylko w promieniu `promien`
    od gracza i z flagami mapy zgodnymi z przejściem (dawniej kotwica na `a` i brak sprawdzenia)."""
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
        if (b[0], b[1]) not in widziane and _domysl_ok(mapa, (b[0], b[1], z), poz, promien, 2, 0):
            dodaj(b[0], b[1], False, (b[0], b[1], z + 1))      # założenie wypad.py: dziura leży pod punktem b
        # 15.10: kratka kanału (Edron) nie ma flagi 2 w mapie; nagrana trasa jest dowodem przejścia, więc bez żadnego
        # kandydata bierzemy pole nad b jako domysł (tryby "pewne"=False zaczynają od "use", czyli ctrl+klik na kratkę)
        if not wyn and cheb((b[0], b[1]), poz or a) <= max(promien, 3):
            dodaj(b[0], b[1], False, (b[0], b[1], z + 1))
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
        if (b[0], b[1] - 1) not in widziane and _domysl_ok(mapa, (b[0], b[1] - 1, z), poz, promien, 1, 2):
            dodaj(b[0], b[1] - 1, False, (b[0], b[1], z - 1))   # konwencja wypad.py: R = (b.x, b.y-1) na piętrze a
        if not wyn and cheb((b[0], b[1] - 1), poz or a) <= max(promien, 3):   # 15.10: jak w dół, nagrana trasa = dowód
            dodaj(b[0], b[1] - 1, False, (b[0], b[1], z - 1))
    return wyn[:3]


# "lopata" = odkopanie zasypanej dziury łopatą z plecaka (Use with na polu dziury, albo na własnym, gdy już na nim stoimy);
# potem kolejny "krok" wchodzi w odkopaną dziurę. Wyłączane pokrętłem PIETRA_LOPATA=0 (próba jest wtedy pomijana).
TRYBY_DOL = {True: ("krok", "lopata", "krok", "use", "lopata", "krok", "use_wlasne"),
             False: ("use", "krok", "use_wlasne", "lopata", "krok", "use", "use_wlasne")}
TRYBY_GORA = ("R", "krok", "R", "lina", "wlasne", "E", "W", "N")
# 14.10 (R1b, PIETRA_TRYBY_Z_DANYCH=1): tylko tryby, które w danych 12 h kiedykolwiek zadziałały. Typ "schody" (flaga 2 na obu
# piętrach) = krok w obie strony jako pierwsza próba; drabina w górę = R (ze skosu, bez ustawiania się); dziura w dół = krok.
# "lopata" tylko dla zasypanej dziury (ZASYPANE) i z pola sąsiedniego; slot bez zastosowania nie zużywa numeru próby.
TRYBY_DOL_DANE = ("krok", "lopata", "krok", "lopata", "krok")
TRYBY_GORA_SCHODY = ("krok", "krok", "R")
TRYBY_GORA_DRABINA = ("R", "krok", "R")
ZASYPANE = {(32493, 32259, 7)}      # dziury zasypane (piętro z, na którym stoimy), jedyne, gdzie łopata ma sens


class Pietra:
    """Maszyna przejść pięter dla Cavebot (cb). Jedno przejście naraz; tick() zużywa obieg albo oddaje None."""

    def __init__(self, cb, konf=None, log=print):
        self.cb = cb
        self.konf = konf
        self.log = log
        self.st = None                  # stan bieżącego przejścia
        self.resync = []                # czasy ostatnich resynchronizacji (pętla zabezpieczająca)
        self.ostrzezenia = set()
        self._starty = None             # {"x,y,z": [x, y]} z PLIK_STARTOW (wczytywane przy pierwszym użyciu)
        self._domyslne = None           # {"x,y,z": [x, y]} z PLIK_STARTOW_DOMYSLNE (tylko odczyt, nigdy nie trafia do PLIK_STARTOW)
        self._nd = {}                   # R1b: (T, S) -> ile razy nie dotarliśmy na pole startowe S (nie zeruje się przy migotaniu)

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
            st["kand"] = kandydaci(cb.mapa, a, cel, tuple(poz), int(self._k("PIETRA_DOMYSL_PROMIEN", 3)))
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
        if float(self._k("PIETRA_CZEKAJ_KROK_S", 1.2)) > 0 and st["proby"] > 0:
            # R1b: przed kolejną próbą ponowny odczyt pozycji (poprzednia mogła się udać z opóźnieniem)
            p = tuple(cb.postac.pozycja())
            if p[2] != poz[2]:
                return self._po_przejsciu(poz[2], st, poz, teraz, k, "opóźnione", czekaj=0) or True
            if p != tuple(poz):
                if cheb(p, T) > 1:
                    return True                 # odeszliśmy od pola: następny obieg zrobi dojście
                poz = p
        S = None
        if self._dane():
            # R1b: ortogonalne pole startowe tylko przed krokiem; R (Ctrl+klik) działa ze skosu i z własnego pola
            if st["tryby"] is None:
                st["tryby"] = self._tryby(k, st)
                st["proby"] = 0
            if self._wybierz(st, k, poz, teraz) == "krok":
                S = self._start(poz, T, st)
        else:
            S = self._start(poz, T, st)
        if S is not None:
            return self._na_start(poz, S, T, st)
        return self._proba(poz, st, k, teraz)

    # --- pole startowe: ortogonalnie ze schodami (po skosie Ctrl+klik i krok bywają wolne albo bez skutku) ---

    def _wczytaj_starty(self):
        if self._starty is None:
            self._starty = {}
            try:
                if PLIK_STARTOW is not None and Path(PLIK_STARTOW).exists():
                    d = json.loads(Path(PLIK_STARTOW).read_text())
                    self._starty = {str(k): [int(v[0]), int(v[1])] for k, v in d.items()}
            except Exception:
                self._starty = {}
        return self._starty

    def _wczytaj_domyslne(self):
        if self._domyslne is None:
            self._domyslne = {}
            try:
                if PLIK_STARTOW_DOMYSLNE is not None and self._k("PIETRA_STARTY_DOMYSLNE", 1) and Path(PLIK_STARTOW_DOMYSLNE).exists():
                    d = json.loads(Path(PLIK_STARTOW_DOMYSLNE).read_text())
                    self._domyslne = {str(k): [int(v[0]), int(v[1])] for k, v in d.items() if not str(k).startswith("_")}
            except Exception:
                self._domyslne = {}
        return self._domyslne

    def _zle_starty(self, T):
        """Pola startowe przy schodach T, które już nie rusza krokiem (zablokowane mimo mapy): pomijane na stałe."""
        if getattr(self, "_zle", None) is None:
            self._zle = {}
            try:
                if PLIK_ZLYCH is not None and Path(PLIK_ZLYCH).exists():
                    d = json.loads(Path(PLIK_ZLYCH).read_text())
                    self._zle = {str(k): [tuple(int(a) for a in q[:2]) for q in v] for k, v in d.items()}
            except Exception:
                self._zle = {}
        return self._zle.get(f"{T[0]},{T[1]},{T[2]}", [])

    def _zapisz_zle(self, T, S):
        zle = self._zle_starty(T)
        if tuple(S) in zle:
            return
        zle.append(tuple(S))
        self._zle[f"{T[0]},{T[1]},{T[2]}"] = zle
        d = self._wczytaj_starty()
        klucz = f"{T[0]},{T[1]},{T[2]}"
        if d.get(klucz) == [S[0], S[1]]:
            d.pop(klucz, None)                  # zła pamięć startu: nie wracamy do tego pola
        if PLIK_ZLYCH is None:
            return
        try:
            tmp = Path(str(PLIK_ZLYCH) + ".tmp")
            tmp.write_text(json.dumps({k: [list(q) for q in v] for k, v in self._zle.items()}, indent=1, sort_keys=True))
            os.replace(tmp, PLIK_ZLYCH)
        except Exception:
            pass

    def _zapamietaj_start(self, T, poz):
        """Przejście wyszło z pola ortogonalnego do T: zapamiętaj je jako pierwsze na następny raz (per schody)."""
        d = self._wczytaj_starty()
        klucz = f"{T[0]},{T[1]},{T[2]}"
        if d.get(klucz) == [poz[0], poz[1]]:
            return
        d[klucz] = [poz[0], poz[1]]
        if PLIK_STARTOW is None:
            return
        try:
            tmp = Path(str(PLIK_STARTOW) + ".tmp")
            tmp.write_text(json.dumps(d, indent=1, sort_keys=True))
            os.replace(tmp, PLIK_STARTOW)
        except Exception:
            pass                        # zapis pamięci nigdy nie wywraca przejścia

    def _start(self, poz, T, st):
        """Pole, na które trzeba się ustawić przed próbą (None = próbujemy stąd, gdzie stoimy). Kolejność: pole
        zapamiętane dla tych schodów, potem pole, na którym stoimy, potem najbliższe; tylko chodliwe wg mapy,
        bez schodów/dziur i bez zajętych. Pole z nieudaną próbą Ctrl+klik jest odhaczone (st['zmien'])."""
        cb = self.cb
        p = (poz[0], poz[1])
        if p == (T[0], T[1]):
            return None
        if st.get("starty_dla") != T:
            zaj = set()
            try:
                zaj = {tuple(q[:2]) for q in cb.zajete_bez_nas(poz)}
            except Exception:
                pass
            klucz = f"{T[0]},{T[1]},{T[2]}"
            mem = tuple(self._wczytaj_starty().get(klucz) or self._wczytaj_domyslne().get(klucz) or ())
            pola = []
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                c = (T[0] + dx, T[1] + dy)
                f = _flaga(cb.mapa, c[0], c[1], T[2])
                if f & 1 and not f & (2 | 4) and (c not in zaj or c == p) and c not in self._zle_starty(T):
                    pola.append(c)
            pola.sort(key=lambda c: (c != mem, cheb(c, p)))
            st.update(starty_dla=T, starty=pola, odw=set(), biezacy=None, zmien=False, ruchy=0)
        if st["biezacy"] == p and not st["zmien"]:
            return None
        for S in st["starty"]:
            if S in st["odw"]:
                continue
            if S == p:
                st.update(biezacy=S, zmien=False, ruchy=0)
                st["odw"].add(S)
                self._nd.pop((tuple(T), S), None)       # dotarliśmy na S: licznik "nie dotarł" od zera
                return None
            return S
        return None

    def _na_start(self, poz, S, T, st):
        """Jeden obieg dojścia na pole startowe S: strzałka, gdy sąsiaduje w osi, inaczej zwykłe podejście."""
        cb = self.cb
        pre_max = int(self._k("PIETRA_PRE_MAX", 1))
        if pre_max > 0 and cheb(poz, S) == 1 and st.get("pre", {}).get(S, 0) >= pre_max:
            # R1b: pre-krok na S już był, a dalej stoimy poza S: to "nie dotarł na S" (liczone po pozycji, więc odporne
            # na migotanie wyniku kroku); po START_KROK_NIE_MAX takich razach pole idzie do pietra_zle.json
            T_ = tuple(T)
            self._nd[(T_, S)] = self._nd.get((T_, S), 0) + 1
            st["odw"].add(S)
            st["ruchy"] = 0
            if self._nd[(T_, S)] >= START_KROK_NIE_MAX:
                self._zapisz_zle(T, S)
                self.log(f"Przejście pięter: nie dotarłem na {S} przy schodach {T[:2]} {self._nd[(T_, S)]} razy, "
                         f"pole startowe do złych")
            else:
                self.log(f"Przejście pięter: pre-krok na {S} przy schodach {T[:2]} nie dotarł, próbuję stąd")
            return True
        if pre_max > 0 and st.get("pre_suma", 0) >= PRE_SUMA_MAX:
            # R1b-fix: dość pre-kroków na to przejście (postać nie rusza się strzałkami): próbujemy stąd, bez dalszego ustawiania
            st["odw"].update(st["starty"])
            st["ruchy"] = 0
            self.log(f"Przejście pięter: {PRE_SUMA_MAX} pre-kroki bez skutku przy schodach {T[:2]}, próbuję stąd")
            return True
        st["ruchy"] += 1
        if st["ruchy"] > START_RUCHY_MAX:
            st["odw"].add(S)
            st["ruchy"] = 0
            self._zapisz_zle(T, S)
            self.log(f"Przejście pięter: nie dochodzę na pole {S} przy schodach {T[:2]}, pomijam")
            return True
        dx, dy = S[0] - poz[0], S[1] - poz[1]
        if cheb(poz, S) == 1 and not (dx and dy) and not _flaga(cb.mapa, S[0], S[1], poz[2]) & 4:
            kier = ("Right" if dx > 0 else "Left") if dx else ("Down" if dy > 0 else "Up")
            self.log(f"Przejście pięter: ustawiam się ortogonalnie ze schodami {T[:2]}: krok {kier} z {tuple(poz)} na {S}")
            ruszyl = None
            if pre_max > 0:
                st.setdefault("pre", {})[S] = st.get("pre", {}).get(S, 0) + 1
                st["pre_suma"] = st.get("pre_suma", 0) + 1
            try:
                cb.zatrzymaj_klik(poz)
                cb.klik_cel = None
                ruszyl = cb.postac.krok(kier)
            except bot.Zatrzymano:
                raise
            except Exception:
                pass
            if pre_max > 0:
                pass                # R1b: skutek oceniamy po pozycji w następnym obiegu (patrz początek _na_start)
            elif ruszyl is None:      # 14.10: pole nie odpowiada na krok (zajęte/zablokowane mimo mapy): nie męczymy go 8 razy
                st["krok_nie"] = st.get("krok_nie", 0) + 1
                if st["krok_nie"] >= START_KROK_NIE_MAX:
                    st["odw"].add(S)
                    st["ruchy"] = 0
                    st["krok_nie"] = 0
                    self._zapisz_zle(T, S)
                    self.log(f"Przejście pięter: krok {kier} na {S} nie rusza postaci {START_KROK_NIE_MAX} razy, "
                             f"pomijam pole startowe przy schodach {T[:2]}")
            else:
                st["krok_nie"] = 0
            cb.pauza(0.15, 0.3)
            return True
        r = cb.podejdz(S, poz, objazd=False, dlugosc=0)
        if r is None or r is False:
            cb.nieudane += 1
            cb.pauza(0.2, 0.5)
        return True

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

    def _dane(self):
        """R1b: tryby i pole startowe z danych (PIETRA_TRYBY_Z_DANYCH=1); 0 = dawny porządek prób."""
        return bool(self._k("PIETRA_TRYBY_Z_DANYCH", 1))

    def _tryby(self, k, st):
        if self._dane():
            if k["lad"][2] > st["z0"]:
                return list(TRYBY_DOL_DANE)
            z_danych = tryb_z_danych(k["pole"])          # dane z 12 h przed flagami mapy (flagi bywają mylące)
            if z_danych == "R":
                return list(TRYBY_GORA_DRABINA)
            if z_danych == "krok" or _schody(self.cb.mapa, k["pole"], k["lad"]):
                return list(TRYBY_GORA_SCHODY)
            return list(TRYBY_GORA_DRABINA)
        if k["lad"][2] > st["z0"]:
            return list(TRYBY_DOL[bool(k["pewne"])])
        return list(TRYBY_GORA)

    def _stosuje(self, tryb, poz, T, teraz):
        """R1b: czy tryb ma zastosowanie w tej chwili. "krok" nie z własnego pola przejścia; "lopata" tylko dla dziury
        zasypanej (ZASYPANE), przy włączonym PIETRA_LOPATA, z łopatą w plecaku i z operacją łopaty."""
        if tryb == "krok":
            return (poz[0], poz[1]) != (T[0], T[1])
        if tryb == "lopata":
            return bool(self._k("PIETRA_LOPATA", 1)) and (T[0], T[1], T[2]) in ZASYPANE \
                and teraz >= getattr(self, "brak_lopaty_do", float("-inf")) \
                and getattr(self.ops, "uzyj_lopate", None) is not None
        return True

    def _wybierz(self, st, k, poz, teraz):
        """R1b: najbliższy tryb z zastosowaniem na bieżącym slocie; sloty bez zastosowania wypadają z listy, więc nie
        zużywają numeru próby. None = lista wyczerpana."""
        tr = st["tryby"]
        while st["proby"] < len(tr):
            if self._stosuje(tr[st["proby"]], poz, k["pole"], teraz):
                return tr[st["proby"]]
            tr.pop(st["proby"])
        return None

    def _proba(self, poz, st, k, teraz):
        cb = self.cb
        if st["tryby"] is None:
            st["tryby"] = self._tryby(k, st)
            st["proby"] = 0
        if self._dane():
            self._wybierz(st, k, poz, teraz)
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
                        # R1b-fix: każdy krok i klik liczy się do SKOS_MAX na pole T (także gdy pozycja migocze); po limicie slot
                        # kroku jest spalony i idziemy do następnego trybu, zamiast stać do limitu czasu.
                        licz = st.setdefault("skos", {})
                        if licz.get(tuple(T), 0) >= SKOS_MAX:
                            self.log(f"Przejście pięter: {SKOS_MAX} kroki po skosie bez skutku przy {T[:2]}, następny tryb")
                        for kier, (kx, ky) in (("Right" if dx > 0 else "Left", (poz[0] + (1 if dx > 0 else -1), poz[1])),
                                               ("Down" if dy > 0 else "Up", (poz[0], poz[1] + (1 if dy > 0 else -1)))):
                            if _flaga(cb.mapa, kx, ky, z0) & 4:
                                continue                    # ściana na mapie: nie walimy w nią strzałką
                            if licz.get(tuple(T), 0) >= SKOS_MAX:
                                break
                            licz[tuple(T)] = licz.get(tuple(T), 0) + 1
                            self.log(f"Przejście pięter: krok {kier} z {tuple(poz)} (pole {T[:2]} po skosie)")
                            try:
                                cb.postac.krok(kier)
                            except bot.Zatrzymano:
                                raise
                            except Exception:
                                pass
                            cb.pauza(0.15, 0.3)
                            if tuple(cb.postac.pozycja()) != tuple(poz):
                                if licz.get(tuple(T), 0) < SKOS_MAX:
                                    st["proby"] = n         # ruszyliśmy się: ten sam slot jeszcze raz, już z nowego pola
                                return True
                        if getattr(cb, "klik", None) is not None and licz.get(tuple(T), 0) < SKOS_MAX:       # po skosie tylko klik klienta (marsz 1 pola)
                            licz[tuple(T)] = licz.get(tuple(T), 0) + 1
                            self.log(f"Przejście pięter: klik na pole {T[:2]} po skosie z {tuple(poz)}")
                            try:
                                cb.klik(dx, dy)
                            except bot.Zatrzymano:
                                raise
                            except Exception:
                                pass
                            cb.spij(0.5)
                            if tuple(cb.postac.pozycja()) != tuple(poz):
                                if licz.get(tuple(T), 0) < SKOS_MAX:
                                    st["proby"] = n
                                return self._po_przejsciu(z0, st, poz, teraz, k, "klik po skosie", czekaj=self._czekaj("krok")) or True
                        tryb, opis = "krok_skos", "krok po skosie bez skutku"
                        if self._po_przejsciu(z0, st, poz, teraz, k, opis, czekaj=self._czekaj("krok")):
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
            elif tryb == "lopata":
                if not self._k("PIETRA_LOPATA", 1):
                    return True
                if self._k("PIETRA_LOPATA_TYLKO_Z7", 1) and z0 != 7:
                    return True                 # 13.10: łopata tylko przy wejściu z powierzchni (z7); jaskinia nie ma zasypanych dziur
                if teraz < getattr(self, "brak_lopaty_do", float("-inf")):
                    return True                 # brak łopaty w plecaku: nie ponawiamy przez PIETRA_LOPATA_BRAK_S
                uzyj = getattr(self.ops, "uzyj_lopate", None)
                if uzyj is None:
                    return True
                cel_k = T
                if na_polu:
                    # 13.10: z własnego pola dziury nie da się jej odkopać: schodzimy o 1 kratkę (poziomo/pionowo,
                    # nie w ścianę ani w inną dziurę) i kopiemy stamtąd
                    for kier, (kx, ky) in (("Left", (poz[0] - 1, poz[1])), ("Right", (poz[0] + 1, poz[1])),
                                           ("Up", (poz[0], poz[1] - 1)), ("Down", (poz[0], poz[1] + 1))):
                        if _flaga(cb.mapa, kx, ky, z0) & (4 | 2):
                            continue
                        self.log(f"Przejście pięter: stoję na dziurze {T[:2]}, schodzę {kier} o kratkę, żeby ją odkopać")
                        try:
                            cb.postac.krok(kier)
                        except bot.Zatrzymano:
                            raise
                        except Exception:
                            pass
                        cb.pauza(0.3, 0.5)
                        nowa = tuple(cb.postac.pozycja())
                        if nowa != tuple(poz):
                            poz = nowa
                            break
                if self._dane() and (poz[0], poz[1]) == (T[0], T[1]):
                    self.log(f"Przejście pięter: nie zeszło z dziury {T[:2]}, łopata z własnego pola nie działa, pomijam")
                    return True
                self.log(f"Przejście pięter: próba {n + 1}/{len(tryby)} (łopata na {cel_k[:2]}, odkopuję dziurę) "
                         f"z {tuple(poz)}")
                self._tele("pietra_lopata", poz=list(poz), pole=list(cel_k), proba=n + 1)
                try:
                    uzyj(cel_k, poz)
                except bot.Zatrzymano:
                    raise
                except Exception as ex_l:
                    if "nie widzę" in str(ex_l):
                        self.brak_lopaty_do = teraz + float(self._k("PIETRA_LOPATA_BRAK_S", 600.0))
                        self.log(f"Przejście pięter: brak łopaty w plecaku, nie próbuję ponownie przez "
                                 f"{self._k('PIETRA_LOPATA_BRAK_S', 600.0):.0f} s")
                    raise
                cb.spij(0.6)                    # dziura otwiera się po chwili; kolejna próba to krok w nią
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
        if self._po_przejsciu(z0, st, poz, teraz, k, opis, czekaj=self._czekaj(tryb)):
            return True
        if tryb in ("use", "R") and not na_polu and not self._dane():
            st["zmien"] = True          # Ctrl+klik bez skutku: następna próba z innego pola ortogonalnego (jeśli jest)
        st["nast"] = cb.zegar() + self._odstep(n)
        return True

    def _use(self, pole, poz, _):
        self.ops.uzyj_pole(pole, poz)

    def _odstep(self, n):
        # R1b: przy skróconym czekaniu pierwszy odstęp między próbami ledwie zauważalny (dawniej 1 s po 3,5 s czekania)
        odst = (0.2, 1.0, 2.0, 4.0) if float(self._k("PIETRA_CZEKAJ_KROK_S", 1.2)) > 0 else (1.0, 2.0, 4.0, 6.0)
        return odst[min(n, len(odst) - 1)]

    def _czekaj(self, tryb):
        """s czekania na zmianę piętra po próbie: krok 1,2, R i reszta 2,0 (p99 udanych 1,5 i 1,8 s); 0 w pokrętle = dawne 2,0."""
        ks = float(self._k("PIETRA_CZEKAJ_KROK_S", 1.2))
        rs = float(self._k("PIETRA_CZEKAJ_R_S", 2.0))
        if tryb == "lopata" and ks > 0:
            return 0.4                  # łopata otwiera dziurę, piętra nie zmienia
        if tryb.startswith("krok"):
            return ks if ks > 0 else 2.0
        return rs if rs > 0 else 2.0

    def _po_przejsciu(self, z0, st, poz_przed, teraz, k, opis, czekaj=2.0):
        """Po próbie: przez `czekaj` s (co 0,4 s) sprawdzamy pozycję (z rdzenia). Zmiana piętra = sukces.
        czekaj 0 = jeden odczyt bez czekania (opóźniony sukces wykryty przed kolejną próbą)."""
        cb = self.cb
        for _ in range(max(1, int(math.ceil(czekaj / 0.4 - 1e-9))) if czekaj > 0 else 1):
            if czekaj > 0:
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
                T = k["pole"]
                if cheb(poz_przed, T) == 1 and (poz_przed[0] == T[0] or poz_przed[1] == T[1]) and poz_przed[2] == T[2] \
                        and (not self._dane() or opis.startswith("krok")):      # R1b: pamięć startu tylko dla kroku
                    self._zapamietaj_start(T, poz_przed)
                self._sukces(p)
                return True
        return False

    def _sukces(self, p):
        cb = self.cb
        self.st = None
        cb.pietra_porazki = 0
        cb.pietra_zmiana_t = cb.zegar()    # 15.10: planowana zmiana piętra (wpadniecie.py nie uzna jej za upadek)
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
