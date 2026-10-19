"""Ratunek (SPEC_ratunek_haiku_1019), F1: detektor zachowań „jak bot” w CIENIU. Nic nie zmienia w ruchu bota.

Sygnały (spec, sekcja „Sygnały”): S1 porażka trasy (dojście/wyprawa/serwis), S2 złe piętro, S3 stoi, S4 kręci się,
S5 kroki bez skutku, S6 klik bez skutku, S7 pusta pętla trasy. Walka, stany zamierzone (PRZERWA, PAUZA, PAUZA_PK, GRACZ)
i ucieczka nie są sygnałem. RATUNEK_HAIKU: 0 = wyłączone, 1 = cień (log + telemetria + logi/ratunek-<data>.jsonl:
„wołałbym Haiku”); 2 (wykonanie, F2) jeszcze NIE istnieje.
F2a (RATUNEK_HAIKU_PYTAJ=1 przy RATUNEK_HAIKU=1): do tego Haiku W CIENIU w osobnym wątku, bez ruchu — ratunek_cien.py.

Detektor żyje w procesie, nie w obiekcie cavebota (`detektor()`): mozg.py tworzy nowy CavebotDojscie na każdą próbę dojścia
(R1 19.10: 5 prób po ~5 s), więc licznik złego piętra i okrążeń musi przetrwać kolejne instancje.
"""
import collections
import json
import time

STANY_WALKI = ("WALKA", "WALKA_PVP", "LOOT", "POGON", "UCIECZKA", "UH", "ZDROWIE")
STANY_ZAMIERZONE = ("PRZERWA", "PAUZA", "PAUZA_PK", "GRACZ", "JEDZENIE", "ML")   # + krótkie własne czynności bota (przegląd 19.10)
ZASTRZEZONE = ("kod", "opis", "t", "poz", "wolan_h", "ponad_limit", "tryb", "stan", "czas", "id")
MAX_PRZERWA_S = 30.0          # luka między obiegami dłuższa niż to = bot nie był obserwowany: liczniki od nowa
OPISY = {"S1": "porażka trasy", "S2": "złe piętro", "S3": "stoi", "S4": "kręci się", "S5": "kroki bez skutku",
         "S6": "klik bez skutku", "S7": "pusta pętla trasy"}

# wartości domyślne (cavebot.py ma te same stałe; pokretla.py nadpisuje je na żywo)
DOMYSLNE = dict(RATUNEK_HAIKU=0, RATUNEK_HAIKU_PYTAJ=0, RATUNEK_PIETRO_S=10.0, RATUNEK_STOI_S=30.0, RATUNEK_STOI_PROMIEN=2,
                RATUNEK_KRAG_WIZYT=4, RATUNEK_KRAG_S=60.0, RATUNEK_OSC_N=3, RATUNEK_KROKI_N=6, RATUNEK_KLIK_N=5,
                RATUNEK_OKRAZENIA_N=3, RATUNEK_OKRAZENIA_S=60.0, RATUNEK_PRZERWA_S=120.0, RATUNEK_LIMIT_H=20)


def _pasuje(stan, stany):
    s = str(stan or "")
    return any(s == x or s.startswith(x) for x in stany)


def _czeb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


class Detektor:
    """Czyste liczenie sygnałów. `teraz` we wszystkich wywołaniach z jednego zegara (na żywo: time.monotonic, jak
    Cavebot.zegar; offline: czas telemetrii); czas ścienny dopisuje dopiero zglos(). `konf` = obiekt ze stałymi RATUNEK_* (moduł cavebot albo SimpleNamespace w testach).
    `tick()` raz na obieg; `zdarzenie()` z miejsc w kodzie, które już dziś logują porażkę (krok, klik, okrążenie, trasa).
    Zwraca listę nowych sygnałów (dict), które minęły debounce; nic nie wykonuje."""

    def __init__(self, konf=None):
        self.konf = konf
        self.ost_t = None
        self.ost_poz = None
        self.pietro_t = 0.0                  # s poza walką na piętrze spoza trasy (S2)
        self.kotwica = None                  # S3: {"poz","t0","exp0"}
        self.wizyty = collections.deque()    # S4: (t, poz) kolejnych RÓŻNYCH pozycji poza walką
        self.kroki_zle = 0                   # S5: nieudane kroki od ostatniej zmiany pozycji
        self.okrazenia = collections.deque() # S7: (t, poz) końców okrążeń
        self.ost_sygnal = {}                 # kod -> (t, poz): debounce
        self.wolania = collections.deque()   # czasy sygnałów (licznik „wywołań na godzinę”)
        self.trasa_pietra = None             # zbiór pięter bieżącej trasy (S2); None = nie wiadomo
        self.ruchy = collections.deque(maxlen=30)   # F2a: ostatnie zmiany pozycji i porażki (kontekst dla Haiku w cieniu)

    def k(self, nazwa):
        return getattr(self.konf, nazwa, DOMYSLNE[nazwa]) if self.konf is not None else DOMYSLNE[nazwa]

    # --- wejście ---
    def ustaw_trase(self, punkty):
        try:
            self.trasa_pietra = {int(p[2]) for p in punkty} or None
        except Exception:
            self.trasa_pietra = None

    def tick(self, teraz, poz, stan, exp=None):
        poz = tuple(poz[:3])
        dt = 0.0 if self.ost_t is None else teraz - self.ost_t
        if dt < 0 or dt > MAX_PRZERWA_S:
            self._reset(teraz)
            dt = 0.0
        self.ost_t = teraz
        ruszyl = self.ost_poz is not None and poz != self.ost_poz
        if ruszyl:
            self.kroki_zle = 0
            self.ruchy.append({"t": teraz, "rodzaj": "pozycja", "poz": list(poz), "stan": str(stan)})
        self.ost_poz = poz
        walka = _pasuje(stan, STANY_WALKI)
        zamierzony = _pasuje(stan, STANY_ZAMIERZONE)
        nowe = []
        if walka or zamierzony:
            # walka i postój z własnej woli nie są sygnałem: S3/S4 liczą od nowa, S2 nie przyrasta
            self.kotwica = {"poz": poz, "t0": teraz, "exp0": exp}
            self.wizyty.clear()
            return nowe
        # S2: złe piętro
        if self.trasa_pietra and poz[2] not in self.trasa_pietra:
            self.pietro_t += dt
            if self.pietro_t >= self.k("RATUNEK_PIETRO_S"):
                nowe += self._sygnal("S2", teraz, poz, pietro=poz[2], trasa=sorted(self.trasa_pietra),
                                     trwa_s=round(self.pietro_t, 1))
        else:
            self.pietro_t = 0.0
        # S3: stoi (promień od kotwicy, exp bez zmian)
        a = self.kotwica
        if a is None or a["poz"][2] != poz[2] or _czeb(a["poz"], poz) > self.k("RATUNEK_STOI_PROMIEN") \
                or (exp is not None and a["exp0"] is not None and exp > a["exp0"]):
            self.kotwica = {"poz": poz, "t0": teraz, "exp0": exp}
        else:
            if a["exp0"] is None:
                a["exp0"] = exp
            if teraz - a["t0"] >= self.k("RATUNEK_STOI_S"):
                nowe += self._sygnal("S3", teraz, poz, stoi_s=round(teraz - a["t0"], 1), kotwica=list(a["poz"]))
        # S4: kręci się (to samo pole wiele razy w oknie albo oscylacja A-B-A)
        if not self.wizyty or self.wizyty[-1][1] != poz:
            self.wizyty.append((teraz, poz))
        okno = self.k("RATUNEK_KRAG_S")
        while self.wizyty and teraz - self.wizyty[0][0] > okno:
            self.wizyty.popleft()
        if self.wizyty and self.wizyty[-1][1] == poz:
            n = sum(1 for _, p in self.wizyty if p == poz)
            # oscylacja tylko TU: ciągły ogon ruchu w promieniu 2 pól od bieżącej pozycji (inaczej jedna oscylacja w oknie
            # dawałaby sygnał na każdym kolejnym polu marszu; pomiar 17.10: 36 x S4 w 3,2 h, większość wizyt=1)
            ogon = []
            for _, p in reversed(self.wizyty):
                if p[2] != poz[2] or _czeb(p, poz) > 2:
                    break
                ogon.append(p)
            osc = sum(1 for i in range(2, len(ogon)) if ogon[i] == ogon[i - 2])
            if n >= self.k("RATUNEK_KRAG_WIZYT") or osc >= self.k("RATUNEK_OSC_N"):
                nowe += self._sygnal("S4", teraz, poz, wizyt=n, oscylacje=osc, okno_s=okno)
        return nowe

    def zdarzenie(self, rodzaj, teraz, poz=None, /, **d):
        """rodzaj: krok_nieudany | klik_bez_efektu (n=liczba klików) | okrazenie | porazka_trasy (co=dojscie|wyprawa|serwis)."""
        poz = tuple(poz[:3]) if poz else self.ost_poz
        self.ruchy.append({"t": teraz, "rodzaj": rodzaj, "poz": list(poz) if poz else None})
        if rodzaj == "krok_nieudany":
            if poz is not None and self.ost_poz is not None and poz != self.ost_poz:
                self.kroki_zle = 0
            self.kroki_zle += 1
            if self.kroki_zle >= self.k("RATUNEK_KROKI_N"):
                return self._sygnal("S5", teraz, poz, kroki=self.kroki_zle)
        elif rodzaj == "klik_bez_efektu":
            if int(d.get("n", 0)) >= self.k("RATUNEK_KLIK_N"):
                return self._sygnal("S6", teraz, poz, **d)
        elif rodzaj == "okrazenie":
            self.okrazenia.append((teraz, poz))
            okno = self.k("RATUNEK_OKRAZENIA_S")
            while self.okrazenia and teraz - self.okrazenia[0][0] > okno:
                self.okrazenia.popleft()
            pozy = [p for _, p in self.okrazenia if p is not None]
            malo_ruchu = len(pozy) == len(self.okrazenia) and all(p[2] == pozy[0][2] and _czeb(p, pozy[0]) <= 2
                                                                  for p in pozy)
            if len(self.okrazenia) >= self.k("RATUNEK_OKRAZENIA_N") and malo_ruchu:
                return self._sygnal("S7", teraz, poz, okrazen=len(self.okrazenia), okno_s=okno)
        elif rodzaj == "porazka_trasy":
            return self._sygnal("S1", teraz, poz, **d)
        return []

    def ostatnie_ruchy(self, teraz, n=10):
        """Ostatnie n wpisów (zmiana pozycji / porażka kroku, kliku, okrążenie) z wiekiem w s względem `teraz`."""
        return [{"temu_s": round(teraz - r["t"], 1), **{k: v for k, v in r.items() if k != "t"}}
                for r in list(self.ruchy)[-n:]]

    # --- wewnętrzne ---
    def _reset(self, teraz):
        self.pietro_t = 0.0
        self.kotwica = None
        self.wizyty.clear()
        self.kroki_zle = 0
        self.okrazenia.clear()

    def _sygnal(self, kod, teraz, poz, /, **d):
        """Debounce: ten sam sygnał najwcześniej po RATUNEK_PRZERWA_S, chyba że postać odeszła > 5 pól albo zmieniła piętro."""
        ost = self.ost_sygnal.get(kod)
        if ost is not None and teraz - ost[0] < self.k("RATUNEK_PRZERWA_S"):
            p0 = ost[1]
            if p0 is None or poz is None or (p0[2] == poz[2] and _czeb(p0, poz) <= 5):
                return []
        self.ost_sygnal[kod] = (teraz, poz)
        while self.wolania and teraz - self.wolania[0] > 3600:
            self.wolania.popleft()
        self.wolania.append(teraz)
        n_h = len(self.wolania)
        szczeg = {("x_" + k if k in ZASTRZEZONE else k): v for k, v in d.items()}   # np. opis= z wypadu nie nadpisze opisu sygnału
        return [dict(szczeg, kod=kod, opis=OPISY[kod], t=teraz, poz=list(poz) if poz else None, wolan_h=n_h,
                     ponad_limit=n_h > self.k("RATUNEK_LIMIT_H"))]


# --- proces: jeden detektor na proces bota (przeżywa kolejne instancje cavebota) ---
_DET = None


def detektor(konf=None):
    global _DET
    if _DET is None:
        _DET = Detektor(konf)
    elif konf is not None:
        _DET.konf = konf
    return _DET


_SEQ = 0


def _id_sygnalu(kod):
    global _SEQ
    _SEQ += 1
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{kod}-{_SEQ}"


def zglos(sygnaly, log=print, tele=None, plik_logu=None, stan=None, pytaj=False, kontekst=None, limit_h=None):
    """Cień: log + telemetria + jsonl. Błąd zapisu nigdy nie wywraca bota.
    F2a: `pytaj` (RATUNEK_HAIKU=1 i RATUNEK_HAIKU_PYTAJ=1, liczy wołający) -> Haiku w cieniu w osobnym wątku
    (ratunek_cien.py): bez ruchu, bez czekania. `kontekst(rek)` = migawka z miejsca zgłoszenia, wołana tylko gdy pytamy."""
    for s in sygnaly or ():
        szczeg = ", ".join(f"{k}={v}" for k, v in s.items() if k not in ZASTRZEZONE)
        try:
            log(f"[RATUNEK] cień: {s['kod']} {s['opis']} w {tuple(s['poz']) if s['poz'] else '?'}"
                f"{' (' + szczeg + ')' if szczeg else ''}; wołałbym Haiku ({s['wolan_h']}/h"
                f"{', PONAD LIMIT' if s['ponad_limit'] else ''}).")
        except Exception:
            pass
        rek = dict(s, tryb="cien", stan=stan, id=_id_sygnalu(s["kod"]))
        if tele is not None:
            try:
                tele.zdarzenie("ratunek", **{k: v for k, v in rek.items() if k != "t"})
            except Exception:
                pass
        if plik_logu is not None:
            try:
                with open(plik_logu, "a") as f:
                    f.write(json.dumps(dict(rek, czas=time.strftime("%Y-%m-%d %H:%M:%S")),
                                       ensure_ascii=False) + "\n")
            except Exception:
                pass
        if pytaj:
            try:
                import ratunek_cien  # noqa: PLC0415
                if kontekst is not None:
                    migawka = kontekst
                else:
                    migawka = lambda r: {}   # noqa: E731
                ratunek_cien.cien().zglos(rek, _z_ruchami(migawka), plik_logu,
                                          limit_h if limit_h is not None else DOMYSLNE["RATUNEK_LIMIT_H"], log)
            except Exception:
                pass


def _z_ruchami(migawka):
    """Migawka + ostatnie 10 ruchów z detektora procesu (jeśli migawka ich nie ma)."""
    def f(rek):
        snap = dict(migawka(rek) or {})
        if "ruchy" not in snap:
            snap["ruchy"] = detektor().ostatnie_ruchy(rek.get("t", 0.0))
        return snap
    return f


def plik_logu(katalog_logow):
    """logi/ratunek-<data>.jsonl w katalogu logów instancji."""
    from pathlib import Path  # noqa: PLC0415
    return Path(katalog_logow) / f"ratunek-{time.strftime('%Y%m%d')}.jsonl"
