"""Wyprawa po zapasy (13.10): bot sam wraca do Thais, kupuje jedzenie u Frodo (jedzenie na miejscu do "full",
dokup ponad cel), opcjonalnie blank runy u Xodeta i pochodnie u Gorna, po czym wraca na spot i patrol rusza dalej.

To ta sama maszyna co wypad po pochodnie (wypad.Wypad): trasa jako etapy IDZ/LINA/DZIURA, chodzenie przez
Cavebot._idz_odcinek, dialog z NPC przez ops.czat/ops.wiadomosci (hi / buy N x / yes), ucieczka, STOP, ALARM_GM.
Klasa Wyprawa dziedziczy po Wypad i dokłada tylko to, czego wypad nie ma:
  * wyzwalacz zapasu: jedzenie w plecaku < próg (JEDZENIE_ZAPAS_MIN albo WYPRAWA_ZAPAS_PROG), głód bez jedzenia,
    opcjonalnie blank runy < WYPRAWA_BLANKI_PROG; poza walką/lootem/UH, HP ok, cooldown WYPRAWA_CO_MIN;
  * wiele przystanków (Gorn -> Frodo -> Xodet) i odcinki między nimi z A* po mapie (generuj_trase_miasta.Graf)
    albo z nagrania (trasy/wyprawa_sklepy.json);
  * zakupy z kontrolą capacity, złota i kosztu (ceny z ofert NPC "Do you want to buy N x for G gold?");
  * jedzenie u NPC aż klient przestanie zjadać ("You are full" / liczba sztuk nie spada), potem dokup;
  * kolejka u NPC ("I am talking to ...", "wait a moment"): czekamy, nie liczymy jako porażkę;
  * trwały stan (wyprawa_stan.json): restart bota w środku wyprawy wznawia ją od najbliższego odcinka;
  * twarde limity czasu i obiegów, wykrycie teleportu/śmierci, alarm + plik STOP przy utknięciu w mieście.

Wyłączona domyślnie (WYPRAWA_AKTYWNA = 0). Włącza tryb "wyprawa" z tryby.json (albo pokrętło w na_zywo.json).
Pozycje NPC: trasy/wyprawa_sklepy.json (ręcznie) albo uczone z widoku (wyprawa_npc.json: gdy Frodo/Xodet pojawią
się w liście stworów, bot zapisuje ich pole). Bez znanej pozycji Frodo wyprawa nie startuje (log + powiadomienie).

CLI (tylko odczyt plików i mapy, nic nie rusza gry):  python3 -I wyprawa.py [plan|stan]
"""

import heapq
import json
import math
import os
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bot
import instancja
import wypad
from wypad import Wypad, cheb, sprawdz_plan, zbuduj_etapy

KATALOG = Path(__file__).resolve().parent
TRASY = KATALOG / "trasy"
PLIK_SKLEPOW = TRASY / "wyprawa_sklepy.json"
PLIK_STANU = instancja.S.stan / "wyprawa_stan.json"
PLIK_NPC = instancja.S.stan / "wyprawa_npc.json"

BAZY = ("troll", "thais_kanaly")       # plany wypadu (wypad.PLANY) kończące się u Gorna w Thais; rook ma inne miasto
WAGI_DOMYSLNE = {                      # oz; NIEZWERYFIKOWANE na serwerze, bot poprawia je z delty cap po zakupie
    "ham": 13.6, "dragon ham": 15.0, "meat": 13.0, "cheese": 5.0, "bread": 3.0, "fish": 5.2,
    "blank": 1.2, "torch": 5.0,
}
ID_BLANK = {3147}
WARTOSC_ID_ZLOTA = {3031: 1, 3035: 100, 3043: 10000}    # gold / platinum / crystal coin
GOLD_WAGA = 0.1                                          # oz za monetę (poprawka delty cap po zakupie)
SLOWA_DOMYSLNE = {"blank": "blank rune"}                 # klucz -> słowo w "buy N ..." (nadpisuje config "slowa")
NPC_DOMYSLNE = {"gorn": "Gorn", "frodo": "Frodo", "xodet": "Xodet"}

DOMYSLNE = {                                             # gdy konf (cavebot) nie ma stałej
    "WYPRAWA_AKTYWNA": 0, "WYPRAWA_ZAPAS_PROG": 0, "WYPRAWA_JEDZENIE_CEL": 20, "WYPRAWA_JEDZENIE_DOKUP": 5,
    "WYPRAWA_JEDZ_NA_MIEJSCU": 1, "WYPRAWA_JEDZ_MAKS": 12, "WYPRAWA_BLANKI": 0, "WYPRAWA_BLANKI_PROG": 2,
    "WYPRAWA_BLANKI_MAX_KOSZT": 500, "WYPRAWA_POCHODNIE": 1, "WYPRAWA_CAP_REZERWA": 8, "WYPRAWA_ZLOTO_MIN": 30,
    "WYPRAWA_MIN_HP": 70, "WYPRAWA_CO_MIN": 20, "WYPRAWA_MAX_CZAS_S": 1800, "WYPRAWA_MAX_KROKOW": 6000,
    "WYPRAWA_STOP_PRZY_UTKNIECIU": 1, "JEDZENIE_ZAPAS_MIN": 5, "WYPAD_ILE_TORCHY": 5,
}

POTWIERDZ = 2                  # kolejne odczyty z warunkiem = start
WZNOW_MAX_S = 2400.0           # s (zegar ścienny): starszy zapis stanu = nie wznawiamy
WZNOW_ODL = 15                 # pola od najbliższego punktu odcinka, by wznowić po restarcie
SKOK_POZ = 25                  # pola na jednym piętrze między obiegami = teleport/śmierć
KOLEJKA_MAKS = 12              # tyle odpowiedzi "zajęty" resetuje czas oczekiwania na NPC (~6 s każda)
KOLEJKA_PAUZA_S = 5.0
LIMIT_DIJKSTRY = 80000
STOP_STANY = ("WALKA", "LOOT", "JEDZENIE", "POCHODNIA", "GRACZ", "UCIECZKA", "UH", "PAUZA", "MOZG", "PRZERWA",
              "WYPAD", "ML", "ZDROWIE")

ODP_PELNY = re.compile(r"you are full|you are not hungry|you cannot eat more|too full", re.I)
ODP_OFERTA = re.compile(r"buy\s+(\d+)\s+(.+?)\s+for\s+(\d+)\s+gold", re.I)
ODP_ZAJETY = re.compile(r"talking to|is talking|i am busy|i'm busy|\bbusy\b|wait a moment|please wait|"
                        r"in a moment|one at a time|in line|queue|be with you", re.I)


# --- konfiguracja i dane o sklepach -------------------------------------------

def _json(plik):
    try:
        d = json.loads(Path(plik).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _punkt(p):
    try:
        x, y, z = p
        return (int(x), int(y), int(z))
    except (TypeError, ValueError):
        return None


def wczytaj_sklepy(plik=PLIK_SKLEPOW):
    """{"frodo": {...}, "xodet": {...}} z trasy/wyprawa_sklepy.json (ręczne dane; puste pola = brak)."""
    d = _json(plik).get("przystanki", {})
    return d if isinstance(d, dict) else {}


def wczytaj_npc(plik=PLIK_NPC):
    """{"Frodo": (x, y, z)} pozycje NPC uczone z widoku."""
    wynik = {}
    for nazwa, v in _json(plik).items():
        p = _punkt(v.get("poz")) if isinstance(v, dict) else None
        if p:
            wynik[nazwa] = p
    return wynik


class Trasownik:
    """Odcinki trasy po mapie (A* z generuj_trase_miasta.Graf) i wybór pola stania obok NPC."""

    def __init__(self, mapa):
        import generuj_trase_miasta as g  # noqa: PLC0415
        self.g = g
        self.graf = g.Graf(mapa)

    def odcinek(self, od, do):
        """Punkty [(x,y,z)] od `od` do `do` (rzadkie, z przejściami pięter) albo None."""
        od, do = tuple(od), tuple(do)
        if od == do:
            return [od]
        droga = self.graf.astar(od, do)
        if droga is None:
            return None
        return self.g.scal(self.g.rzadko(droga))

    def stoisko(self, od, npc, promien=2):
        """(pole stania, punkty drogi) najtańsze z pól w promieniu `promien` od NPC (nie samo pole NPC)."""
        npc = tuple(npc)
        kand = {(npc[0] + dx, npc[1] + dy, npc[2]) for dx in range(-promien, promien + 1)
                for dy in range(-promien, promien + 1) if (dx, dy) != (0, 0)}
        kand = {q for q in kand if self.graf.idzie(*q)}
        if not kand:
            return None
        od = tuple(od)
        d = {od: 0}
        pq = [(0, od)]
        n = 0
        while pq:
            c, p = heapq.heappop(pq)
            if c > d.get(p, 1 << 60):
                continue
            if p in kand:
                return p, self.odcinek(od, p)
            n += 1
            if n > LIMIT_DIJKSTRY:
                return None
            for q, cc, _t in self.graf.sasiedzi(p):
                nc = c + cc
                if nc < d.get(q, 1 << 60):
                    d[q] = nc
                    heapq.heappush(pq, (nc, q))
        return None


def punkty_bazy(katalog=TRASY, plany=wypad.PLANY, nazwy=BAZY):
    """{nazwa: (do_miasta, z_miasta, npc)} z plików planów wypadu (listy punktów)."""
    wynik = {}
    for p in plany:
        if p["nazwa"] not in nazwy:
            continue
        try:
            do = [_punkt(q) for q in json.loads((Path(katalog) / p["do"]).read_text())]
            z = [_punkt(q) for q in json.loads((Path(katalog) / p["z"]).read_text())]
        except (OSError, ValueError, TypeError):
            continue
        if None in do or None in z or not do or not z:
            continue
        wynik[p["nazwa"]] = (do, z, p.get("npc") or "Gorn")
    return wynik


def wybierz_baze(baza, poz, zasieg=wypad.PLAN_ZASIEG):
    """Nazwa planu bazowego z punktem do_miasta najbliżej `poz` na tym piętrze (<= zasieg pól) albo None."""
    najl = None
    for nazwa, (do, _z, _n) in baza.items():
        d = min((cheb(poz, q) for q in do if q[2] == poz[2]), default=None)
        if d is not None and d <= zasieg and (najl is None or d < najl[0]):
            najl = (d, nazwa)
    return najl[1] if najl else None


# --- operacje na żywo ----------------------------------------------------------

class OperacjeZywe(wypad.OperacjeZywe):
    """Operacje wypadu + jedzenie przy NPC i plecak z pojemnikami na runy (blank runy)."""

    def plecak(self):
        import loot  # noqa: PLC0415
        odp = self.zapytaj({"cmd": "kontenery"})
        kont = [k for k in (odp.get("kontenery") or []) if loot.czy_plecak(k) or loot.czy_runy(k)]
        if not any(loot.czy_plecak(k) for k in kont):
            return None
        ids = {}
        for k in kont:
            for p in k.get("przedmioty", []):
                ids[p["id"]] = ids.get(p["id"], 0) + max(1, p.get("ilosc", 1))
        return {"id": ids}

    def zjedz(self):
        """Jeden Use na jedzeniu z plecaka (loot.zjedz): lista zjedzonych nazw; [] = nic nie ubyło (najedzony)."""
        import loot  # noqa: PLC0415
        return loot.zjedz(1, log=self.log)


# --- wyprawa ---------------------------------------------------------------------

class Wyprawa(Wypad):
    """Wypad do Thais po zapasy. Wołany tak jak Wypad (Cavebot._wypad_tick); torch-trip z wypad.py zostaje."""

    def __init__(self, cb, ops, konf=None, log=print, katalog=TRASY, plik_stanu=None, plik_sklepow=None,
                 plik_npc=None, plik_stop=None, czas=time.time, trasownik=None, **kw):
        super().__init__(cb, ops, konf=konf, log=log, katalog=katalog, **kw)
        self.plik_stanu = Path(plik_stanu or PLIK_STANU)
        self.plik_sklepow = Path(plik_sklepow or PLIK_SKLEPOW)
        self.plik_npc = Path(plik_npc or PLIK_NPC)
        self.plik_stop = Path(plik_stop) if plik_stop else None     # None = bot.STOP
        self.czas = czas
        self._trasownik = trasownik
        self.w = None                    # bieżąca wyprawa: {"stops","legs","k","powod","baza",...}
        self._plan_wyprawy = None
        self._wznowiono = False
        self.potw_w = 0
        self.sprawdzono_w = float("-inf")
        self.nast_wyprawa = float("-inf")
        self._ost_poz_w = None
        self._npc_zapis = float("-inf")
        self._brak_pozycji_log = set()
        dane = _json(self.plik_stanu)
        self.wagi = {k: float(v) for k, v in (dane.get("wagi") or {}).items() if isinstance(v, (int, float))}
        self.ceny = {k: float(v) for k, v in (dane.get("ceny") or {}).items() if isinstance(v, (int, float))}
        self.npc_widziane = wczytaj_npc(self.plik_npc)

    # --- konfiguracja ---

    def _k(self, nazwa, domyslna):
        if nazwa == "WYPAD_JEDZENIE" and self._wyprawa_wlaczona():
            return False              # jedzenie: wyprawa (Frodo), nie wypad u Al Dee
        return super()._k(nazwa, domyslna)

    def _wyprawa_wlaczona(self):
        return bool(self.konf is not None and getattr(self.konf, "WYPRAWA_AKTYWNA", 0))

    def _kw(self, nazwa):
        return self._k(nazwa, DOMYSLNE.get(nazwa))

    def _max_czas(self):
        if self.w is not None:
            return float(self._kw("WYPRAWA_MAX_CZAS_S"))
        return super()._max_czas()

    # --- trwały stan ---

    def _stan_czytaj(self):
        return _json(self.plik_stanu)

    def _stan_zapisz(self, **zmiany):
        d = self._stan_czytaj()
        d["wagi"], d["ceny"] = dict(self.wagi), dict(self.ceny)
        d.update(zmiany)
        try:
            self.plik_stanu.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.plik_stanu.with_name(self.plik_stanu.name + ".tmp")
            tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1))
            os.replace(tmp, self.plik_stanu)
        except OSError as e:
            self.log(f"Wyprawa: nie zapisałem stanu ({e})")

    def _stan_trasy(self, **extra):
        w = self.w
        if w is None:
            return
        self._stan_zapisz(aktywna=True, przerwana=False, powod=w["powod"], baza=w["baza"], k=w["k"],
                          faza=self.faza, potrzeby=w["potrzeby"], t_wall=w["t_wall"],
                          kupione=dict(self.kupione), zapis_wall=self.czas(), **extra)

    def _stan_koniec(self, **extra):
        self._stan_zapisz(aktywna=False, przerwana=False, faza=None, zapis_wall=self.czas(), **extra)

    # --- pomocnicze odczyty ---

    def _tele_w(self, typ, **d):
        self._tele(typ, **d)

    def _cap(self):
        try:
            g = self.cb.gracz()
        except bot.Zatrzymano:
            raise
        except Exception:
            return None
        cap, mx = g.get("cap"), g.get("max_cap")
        if cap is None:
            return None
        if mx and mx > 5000:            # cap w setnych oz (niezweryfikowane)
            cap = cap / 100.0
        return float(cap)

    def _zloto(self, plecak=None):
        if plecak is None:
            try:
                plecak = self.ops.plecak()
            except bot.Zatrzymano:
                raise
            except Exception:
                return None
        if plecak is None:
            return None
        return sum(n * WARTOSC_ID_ZLOTA[i] for i, n in plecak.get("id", {}).items() if i in WARTOSC_ID_ZLOTA)

    def _waga(self, klucz):
        return self.wagi.get(klucz, WAGI_DOMYSLNE.get(klucz))

    def _ids(self, klucz):
        ids = super()._ids(klucz)
        if ids:
            return ids
        if klucz in ("blank", "blank rune"):
            return set(ID_BLANK)
        try:
            import loot  # noqa: PLC0415
            if klucz in loot.JEDZENIE_ID:
                return {loot.JEDZENIE_ID[klucz]}
        except Exception:
            pass
        return set()

    def _slowo(self, klucz):
        if self.w is not None:
            for st in self.w["stops"]:
                if klucz in (st.get("slowa") or {}):
                    return st["slowa"][klucz]
        return SLOWA_DOMYSLNE.get(klucz) or super()._slowo(klucz)

    def _uh_blokuje(self):
        cb = self.cb
        if getattr(cb, "uh_restore", None):
            return True
        plik = getattr(self.konf, "UH_STAN_PLIK", None)
        if plik:
            return bool(_json(plik).get("tarcza_id"))
        return False

    # --- uczenie pozycji NPC ---

    def _ucz_npc(self, lista, teraz):
        nazwy = {n.casefold(): n for n in NPC_DOMYSLNE.values()}
        zmiana = False
        for s in lista or []:
            n = (s.get("nazwa") or "").casefold()
            if n not in nazwy or s.get("hp", 100) <= 0 or s.get("x") is None:
                continue
            p = (int(s["x"]), int(s["y"]), int(s.get("z", 0)))
            if self.npc_widziane.get(nazwy[n]) != p:
                self.npc_widziane[nazwy[n]] = p
                zmiana = True
        if zmiana and teraz - self._npc_zapis > 30.0:
            self._npc_zapis = teraz
            try:
                self.plik_npc.write_text(json.dumps(
                    {n: {"poz": list(p), "wall": self.czas()} for n, p in self.npc_widziane.items()},
                    ensure_ascii=False, indent=1))
                self.log(f"Wyprawa: zapisałem pozycje NPC {self.npc_widziane}")
            except OSError:
                pass

    # --- wyzwalacz ---

    def _blokada_startu(self, teraz, poz, lista):
        cb = self.cb
        if getattr(cb, "wypad_aktywny", False):
            return "wypad"
        if cb.cel is not None or getattr(cb, "ucieczka", False) or getattr(cb, "ostrozny", False) \
                or getattr(cb, "w_poscigu", False) or getattr(cb, "pamiec", None) is not None:
            return "walka"
        if getattr(cb, "w_lootcie", False) or getattr(cb, "lww", None) is not None \
                or getattr(cb, "lww_zalegle", None) is not None or getattr(cb, "zwloki_czekajace", None):
            return "loot"
        if str(getattr(cb, "stan", "")).startswith(STOP_STANY):
            return "stan"
        for atr in ("zd_oczekuje", "jc_oczekuje", "jz_oczekuje", "ml_oczekuje"):
            if getattr(cb, atr, None) is not None:
                return "czar_w_toku"
        fn = getattr(cb, "_czar_blokada", None)
        if callable(fn) and fn() is not None:
            return "czar_blokada"
        if self._uh_blokuje():
            return "uh"
        czat = getattr(cb, "wypad_czat", None)
        if czat is not None and getattr(czat, "zablokowany", False):
            return "alarm_gm"
        moby = cb._zywe_w_promieniu(lista, poz, wypad.MOBY_ODL)
        if moby:
            return "moby"
        ja = getattr(getattr(cb, "postac", None), "nazwa", None)
        for s in lista or []:
            if s.get("gracz") and s.get("nazwa") != ja and s.get("z") == poz[2] and s.get("hp", 100) > 0 \
                    and cheb((s["x"], s["y"]), poz) <= 14:
                return "gracz"
        return None

    def _okazja(self, teraz):
        if not self._wznowiono:
            self._wznowiono = True
            try:
                if self._wznow(teraz):
                    return True
            except bot.Zatrzymano:
                raise
            except Exception as e:
                self._blad("wznowienie", opis=repr(e))
        try:
            lista = getattr(self.cb, "ostatnie_stwory", [])
            self._ucz_npc(lista, teraz)
            if self._okazja_wyprawa(teraz):
                return True
        except bot.Zatrzymano:
            raise
        except Exception as e:
            self._blad("wyprawa_okazja", opis=repr(e))
        return super()._okazja(teraz)

    def _okazja_wyprawa(self, teraz):
        cb = self.cb
        if not self._wyprawa_wlaczona():
            self.potw_w = 0
            return False
        if self.zablokowany or teraz < self.blokada_do or teraz < self.nast_wyprawa:
            return False
        if self._stan_czytaj().get("nast_wall", 0) > self.czas():
            return False
        poz = cb.ruch_poz if getattr(cb, "ruch_poz", None) else None
        if poz is None:
            return False
        if teraz - self.sprawdzono_w < self._k("WYPAD_SPRAWDZ_S", wypad.SPRAWDZ_S):
            return False
        lista = getattr(cb, "ostatnie_stwory", [])
        blok = self._blokada_startu(teraz, poz, lista)
        if blok is not None:
            self.potw_w = 0
            return False
        self.sprawdzono_w = teraz
        g = cb.gracz()
        proc = g.get("proc", 100.0)
        if proc < float(self._kw("WYPRAWA_MIN_HP")) or proc <= getattr(cb, "prog_aktualny", 40) + 10:
            self.potw_w = 0
            return False
        plecak = self.ops.plecak()
        if plecak is None:
            if "w_plecak" not in self.ostrzezenia:
                self.ostrzezenia.add("w_plecak")
                self.log("Wyprawa: nie widzę otwartego plecaka w pamięci, nie sprawdzę zapasu")
            self.potw_w = 0
            return False
        self.ostrzezenia.discard("w_plecak")
        zapas = self._jedzenie_ile(plecak)
        prog = int(self._kw("WYPRAWA_ZAPAS_PROG")) or int(self._kw("JEDZENIE_ZAPAS_MIN"))
        glod = bool(getattr(cb, "jedzenie_znane_brak", lambda t: False)(teraz))
        czar = getattr(cb, "jedzenie_czar_zastepuje_wypad", None)
        czar_ok = bool(czar is not None and czar(g, teraz))
        powody = []
        if zapas is not None and zapas < prog and not czar_ok:
            powody.append("zapas")
        if (zapas == 0 or glod) and not czar_ok and "zapas" not in powody:
            powody.append("glod")
        blanki = self._ile(plecak, "blank")
        cel_blank = int(self._kw("WYPRAWA_BLANKI"))
        if cel_blank > 0 and blanki is not None and blanki < int(self._kw("WYPRAWA_BLANKI_PROG")):
            powody.append("blanki")
        self.potw_w = self.potw_w + 1 if powody else 0
        if self.potw_w < POTWIERDZ:
            return False
        # warunki sensu: złoto i miejsce w capie (bez nich wyprawa byłaby marszem na darmo)
        zloto = self._zloto(plecak)
        if zloto is not None and zloto < int(self._kw("WYPRAWA_ZLOTO_MIN")):
            self._odloz(teraz, f"za mało złota ({zloto})", 1800.0)
            return False
        cap = self._cap()
        waga_min = self._waga("ham") or 1.0
        if cap is not None and cap < waga_min + float(self._kw("WYPRAWA_CAP_REZERWA")) and "blanki" not in powody:
            self._odloz(teraz, f"za mało capa ({cap:.0f} oz) na jedzenie", 900.0)
            return False
        dane = {"powody": powody, "zapas": zapas, "blanki": blanki, "zloto": zloto, "cap": cap, "hp": round(proc),
                "pochodnie": self._ile(plecak, "torch")}
        return self._start_wyprawa("+".join(powody), dane, teraz)

    def _odloz(self, teraz, powod, s):
        self.potw_w = 0
        self.nast_wyprawa = teraz + s
        self.log(f"Wyprawa: nie ruszam, {powod}; kolejna próba za {s / 60:.0f} min")
        self._tele("wyprawa_odlozona", powod=powod, na_s=s)

    # --- budowa trasy ---

    def _trasownik_get(self):
        if self._trasownik is None:
            mapa = getattr(self.cb, "mapa", None)
            if mapa is None:
                raise RuntimeError("brak mapy (cb.mapa), nie zbuduję trasy po mapie")
            self._trasownik = Trasownik(mapa)
        return self._trasownik

    def _odc(self, od, do, nagranie=None):
        """Punkty od `od` do `do`: nagranie (lista z JSON) albo A*; None = brak drogi."""
        od = tuple(od)
        if nagranie:
            pts = [q for q in (_punkt(p) for p in nagranie) if q]
            if pts:
                return ([od] if pts[0] != od else []) + pts
        return self._trasownik_get().odcinek(od, do)

    def _stoisko(self, nazwa_klucza, cfg, npc, od):
        """(pole stania, punkty drogi od `od`) dla przystanku albo (None, powód)."""
        stoi = _punkt(cfg.get("stoi")) if cfg.get("stoi") else None
        if stoi is not None:
            pts = self._odc(od, stoi, cfg.get("dojscie"))
            return (stoi, pts) if pts else (None, f"{nazwa_klucza}: brak drogi do {stoi}")
        npc_poz = _punkt(cfg.get("npc_poz")) if cfg.get("npc_poz") else self.npc_widziane.get(npc)
        if npc_poz is None:
            return None, f"{nazwa_klucza}: nie znam pozycji {npc} (wpisz stoi/npc_poz w wyprawa_sklepy.json albo podejdź do NPC)"
        wynik = self._trasownik_get().stoisko(od, npc_poz)
        if not wynik or not wynik[1]:
            return None, f"{nazwa_klucza}: brak drogi do pola obok {npc} {npc_poz}"
        return wynik

    def _zbuduj(self, baza_nazwa, potrzeby):
        """-> (wyprawa dict, None) albo (None, powód). Nic nie rusza w grze."""
        baza = punkty_bazy(self.katalog)
        if baza_nazwa not in baza:
            return None, f"brak planu bazowego {baza_nazwa}"
        do, z, npc_gorn = baza[baza_nazwa]
        cfg = wczytaj_sklepy(self.plik_sklepow)
        stops = []
        cel_torch = max(int(self._kw("WYPAD_ILE_TORCHY")), int(dict(wypad.Wypad.zakupy(self)).get("torch", 0)))
        if potrzeby.get("gorn"):
            stops.append({"id": "gorn", "npc": npc_gorn, "stoi": do[-1], "dojscie": None,
                          "zakupy": [("torch", cel_torch)]})
        if potrzeby.get("frodo", True):
            c = cfg.get("frodo", {})
            food = str(c.get("jedzenie") or "ham")
            cel = int(self._kw("WYPRAWA_JEDZENIE_CEL"))
            dok = int(self._kw("WYPRAWA_JEDZENIE_DOKUP"))
            lista = [(food, cel)]
            if int(self._kw("WYPRAWA_JEDZ_NA_MIEJSCU")):
                lista.append(("@jedz", None))
            if dok > 0 or int(self._kw("WYPRAWA_JEDZ_NA_MIEJSCU")):
                lista.append((food, cel + dok))
            stops.append({"id": "frodo", "npc": c.get("npc") or "Frodo", "cfg": c, "jedzenie": food,
                          "zakupy": lista, "slowa": c.get("slowa") or {}})
        if potrzeby.get("xodet"):
            c = cfg.get("xodet", {})
            stops.append({"id": "xodet", "npc": c.get("npc") or "Xodet", "cfg": c, "opcjonalny": True,
                          "zakupy": [("blank", int(self._kw("WYPRAWA_BLANKI")))],
                          "slowa": {**SLOWA_DOMYSLNE, **(c.get("slowa") or {})}})
        biez = do[-1]
        legs, kept = [], []    # legs[i] = punkty odcinka "do" przystanku kept[i]
        for st in stops:
            if st["id"] == "gorn":
                stoi, pts = do[-1], list(do)
            else:
                stoi, pts = self._stoisko(st["id"], st["cfg"], st["npc"], biez)
                if stoi is None:
                    if st.get("opcjonalny"):
                        self.log(f"Wyprawa: pomijam przystanek {st['id']}: {pts}")
                        continue
                    return None, pts
                if not legs:
                    pts = list(do) + [q for q in pts[1:]]     # pierwszy odcinek: cała trasa do Gorna + dojście
            st["stoi"] = stoi
            legs.append(pts)
            kept.append(st)
            biez = stoi
        stops = kept
        if not stops:
            return None, "brak przystanków"
        ost = stops[-1]
        if tuple(ost["stoi"]) == tuple(z[0]):
            powrot = list(z)
        else:
            seg = self._odc(ost["stoi"], z[0], (ost.get("cfg") or {}).get("powrot"))
            if not seg:
                return None, f"brak drogi powrotnej z {ost['id']} do {tuple(z[0])}"
            if tuple(seg[-1]) != tuple(z[0]):
                seg = list(seg) + [tuple(z[0])]
            powrot = list(seg) + list(z[1:])
        mapa = getattr(self.cb, "mapa", None)
        legs_etapy = [zbuduj_etapy([_punkt(q) for q in l], mapa) for l in legs]
        etapy_z = zbuduj_etapy([_punkt(q) for q in powrot], mapa)
        for nazwa, et in [(f"leg{i}", e) for i, e in enumerate(legs_etapy)] + [("powrot", etapy_z)]:
            for b in sprawdz_plan(et, mapa):
                self.log(f"Wyprawa: plan {nazwa}: {b}")
        return {"stops": stops, "legs": legs_etapy, "powrot": etapy_z, "k": 0, "baza": baza_nazwa,
                "wyniki": {}, "kroki": 0, "sukces": False, "potrzeby": dict(potrzeby)}, None

    # --- start / wznowienie ---

    def _start_wyprawa(self, powod, dane, teraz):
        cb = self.cb
        poz = tuple(cb.postac.pozycja())
        baza = punkty_bazy(self.katalog)
        nazwa = wybierz_baze(baza, poz)
        if nazwa is None:
            self._odloz(teraz, f"pozycja {poz} poza planami {BAZY}", 900.0)
            return False
        potrzeby = {"frodo": True,
                    "gorn": bool(self._kw("WYPRAWA_POCHODNIE") and dane.get("pochodnie") is not None
                                 and dane["pochodnie"] < int(self._kw("WYPAD_ILE_TORCHY"))),
                    "xodet": bool(int(self._kw("WYPRAWA_BLANKI")) > 0 and dane.get("blanki") is not None
                                  and dane["blanki"] < int(self._kw("WYPRAWA_BLANKI")))}
        try:
            w, blad = self._zbuduj(nazwa, potrzeby)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            w, blad = None, f"wyjątek {e!r}"
        if w is None:
            if blad not in self._brak_pozycji_log:
                self._brak_pozycji_log.add(blad)
                self._powiadom("Wyprawa: nie mogę zacząć", blad, "normal", "wyprawa_brak")
            self.log(f"Wyprawa: nie startuję: {blad}")
            self._tele("wyprawa_odrzucona", powod=blad)
            self.potw_w = 0
            self.nast_wyprawa = teraz + 1800.0
            return False
        w["powod"], w["t_wall"] = powod, self.czas()
        self.w = w
        self._plan_wyprawy = (w["legs"][0], w["powrot"])
        self.npc = w["stops"][0]["npc"]
        if not super()._start("wyprawa:" + powod, dane):
            self.w = None
            self._plan_wyprawy = None
            self.potw_w = 0
            self.nast_wyprawa = teraz + 900.0
            return False
        self._ost_poz_w = poz
        self._stan_trasy()
        self.log(f"Wyprawa: start ({powod}), baza {nazwa}, przystanki {[st['id'] for st in w['stops']]}")
        return True

    def _wybierz_plan(self, poz):
        if self._plan_wyprawy is not None:
            self.plan, self.plan_nazwa = self._plan_wyprawy, "wyprawa"
            return self.plan
        return super()._wybierz_plan(poz)

    def _wznow(self, teraz):
        """Po restarcie bota: kontynuacja wyprawy z pliku stanu (tylko gdy postać jest przy planie)."""
        st = self._stan_czytaj()
        if not st.get("aktywna"):
            return False
        wiek = self.czas() - float(st.get("t_wall", 0))
        if wiek > WZNOW_MAX_S:
            self.log(f"Wyprawa: stary zapis stanu ({wiek:.0f} s), nie wznawiam")
            self._stan_koniec(wynik="przestarzaly")
            return False
        poz = tuple(self.cb.postac.pozycja())
        potrzeby = st.get("potrzeby") or {"frodo": True}
        w, blad = self._zbuduj(st.get("baza", "troll"), potrzeby)
        if w is None:
            self.log(f"Wyprawa: nie wznowię ({blad})")
            self._stan_koniec(wynik="nie_wznowiona", powod=blad)
            self._alarm_utknieciu(f"nie wznowię wyprawy po restarcie: {blad}", stop=False)
            return False
        k0 = min(int(st.get("k", 0)), len(w["stops"]) - 1)
        # kandydaci: odcinek "do" k.., potem powrót; wybór po odległości od `poz`
        kand = []
        for j in range(k0, len(w["legs"])):
            kand.append(("do", j, w["legs"][j]))
        kand.append(("z", len(w["legs"]), w["powrot"]))
        najl = None
        for faza, j, etapy in kand:
            for ei, e in enumerate(etapy):
                if e["typ"] != "IDZ" or e["punkty"][0][2] != poz[2]:
                    continue
                for p in e["punkty"]:
                    d = cheb(poz, p)
                    if najl is None or d < najl[0]:
                        najl = (d, faza, j)
        if najl is None or najl[0] > WZNOW_ODL:
            self.log(f"Wyprawa: pozycja {poz} poza planem wyprawy, nie wznawiam")
            self._stan_koniec(wynik="poza_planem")
            self._alarm_utknieciu(f"po restarcie postać {poz} jest poza planem wyprawy", stop=False)
            return False
        _d, faza, j = najl
        w["powod"], w["t_wall"] = st.get("powod", "wznowiona"), self.czas()
        w["k"] = min(j, len(w["stops"]) - 1)
        self.w = w
        self.kupione = dict(st.get("kupione") or {})
        self._plan_wyprawy = (w["legs"][min(j, len(w["legs"]) - 1)], w["powrot"])
        cb = self.cb
        self.plan, self.plan_nazwa = self._plan_wyprawy, "wyprawa"
        teraz = cb.zegar()
        self.stan = "WYPAD"
        self.t_start = teraz
        self.sklep = None
        self.utk = 0
        self.postep = None
        self.wyjatki = 0
        self.wynik = None
        self.npc = w["stops"][w["k"]]["npc"]
        if faza == "z":
            self.faza, self.etapy = "z", w["powrot"]
        else:
            self.etapy = w["legs"][j]
            stoi = w["stops"][w["k"]]["stoi"]
            self.faza = "sklep" if cheb(poz, stoi) <= 2 and poz[2] == stoi[2] else "do"
        if self.faza != "sklep" and not self._resync_globalny(poz):
            self.stan, self.faza = "SPOKOJ", None
            self.w = None
            self._plan_wyprawy = None
            return False
        cb.wypad_aktywny = True
        cb._wypad_reset_klik()
        try:
            self.ops.wiadomosci()
        except Exception:
            pass
        self._ost_poz_w = poz
        self.log(f"Wyprawa: WZNOWIONA po restarcie ({st.get('powod')}), faza {self.faza}, przystanek "
                 f"{w['stops'][w['k']]['id']}, poz {poz}")
        self._tele("wyprawa_wznowiona", faza=self.faza, poz=list(poz), przystanek=w["stops"][w["k"]]["id"])
        self._stan_trasy()
        return True

    # --- obieg ---

    def _obieg(self, teraz):
        if self.w is not None:
            self.w["kroki"] += 1
            if self.w["kroki"] > int(self._kw("WYPRAWA_MAX_KROKOW")):
                self.w["kroki"] = 0
                return self._awaria("limit_krokow", f"ponad {self._kw('WYPRAWA_MAX_KROKOW')} obiegów wyprawy")
            poz = tuple(self.cb.postac.pozycja())
            ost = self._ost_poz_w
            self._ost_poz_w = poz
            if ost is not None and ost[2] == poz[2] and cheb(ost, poz) > SKOK_POZ:
                return self._teleport(ost, poz)
        return super()._obieg(teraz)

    def _teleport(self, ost, poz):
        self.log(f"Wyprawa: skok pozycji {ost} -> {poz}: teleport albo śmierć")
        self._alarm_utknieciu(f"skok pozycji {ost} -> {poz} (śmierć/teleport?), wyprawa przerwana", stop=True)
        self.zablokowany = True
        return self._koniec("blad", "teleport")

    def _etap_gotowy(self, e, poz, teraz):
        r = super()._etap_gotowy(e, poz, teraz)
        if self.w is not None:
            self._stan_trasy()
        return r

    def zakupy(self):
        if self.w is None:
            return super().zakupy()
        return [(k, c) for k, c in self.w["stops"][min(self.w["k"], len(self.w["stops"]) - 1)]["zakupy"]]

    # --- zakupy: limity ---

    def _max_koszt(self, klucz):
        if klucz == "blank":
            return int(self._kw("WYPRAWA_BLANKI_MAX_KOSZT"))
        return 0

    def _ile_zakupu(self, s, klucz, cel, ma):
        if self.w is None:
            return super()._ile_zakupu(s, klucz, cel, ma)
        ile = max(0, cel - (ma or 0))
        lim = s.get("limit_ile")
        if lim is not None:
            ile = min(ile, int(lim))
        cap = self._cap()
        s["cap_przed"] = cap
        waga = self._waga(klucz)
        if waga and cap is not None:
            wolne = cap - float(self._kw("WYPRAWA_CAP_REZERWA"))
            ile = min(ile, int(max(0.0, math.floor(wolne / waga))))
        cena = self.ceny.get(klucz)
        if cena:
            zloto = self._zloto()
            if zloto is not None:
                ile = min(ile, int(zloto // cena))
            mk = self._max_koszt(klucz)
            if mk > 0:
                ile = min(ile, int(mk // cena))
        return ile

    def _kontrola_oferty(self, s, klucz, teraz):
        if self.w is None:
            return None
        oferta = None
        for t in reversed(s["odpowiedzi"]):
            m = ODP_OFERTA.search(t)
            if m:
                oferta = (int(m[1]), int(m[3]))
                break
        if oferta is None or oferta[0] <= 0:
            return None
        n, koszt = oferta
        cena = koszt / n
        self.ceny[klucz] = cena
        zloto = self._zloto()
        limit, powod = n, None
        if zloto is not None and koszt > zloto:
            limit, powod = int(zloto // cena), "brak_zlota"
        mk = self._max_koszt(klucz)
        if mk > 0 and koszt > mk and int(mk // cena) < limit:
            limit, powod = int(mk // cena), "za_drogo"
        if limit >= n:
            return None
        self.log(f"Wyprawa: oferta {n} {klucz} za {koszt} gp ({cena:.1f}/szt.) ponad limit, schodzę do {limit}")
        if limit <= 0 or s.get("zmniejszen", 0) >= 3:
            return ("odmowa", powod or "za_drogo")
        s["zmniejszen"] = s.get("zmniejszen", 0) + 1
        return ("zmniejsz", limit)

    def _po_zakupie(self, s, klucz, kupiono):
        if self.w is None or not kupiono:
            return
        przed, po = s.get("cap_przed"), self._cap()
        if przed is not None and po is not None:
            cena = self.ceny.get(klucz, 0.0)
            w = (przed - po) / kupiono + cena * GOLD_WAGA     # zapłata złotem też coś waży
            if 0.2 <= w <= 60.0:
                if abs(w - (self._waga(klucz) or 0)) > 0.3:
                    self.log(f"Wyprawa: waga {klucz} z delty cap: {w:.2f} oz (było {self._waga(klucz)})")
                self.wagi[klucz] = round(w, 2)
        self._stan_zapisz()

    def _nastepny_przedmiot(self, s, teraz):
        s.pop("cap_proby", None)
        return super()._nastepny_przedmiot(s, teraz)

    def _odmowa(self, s, klucz, powod, teraz):
        if self.w is None:
            return super()._odmowa(s, klucz, powod, teraz)
        if powod == "brak_miejsca" and s.get("ile", 0) > 1 and s.get("cap_proby", 0) < 3:
            # serwer odrzucił za duży zakup (waga/cap inne niż zakładamy): połowa i jeszcze raz
            s["cap_proby"] = s.get("cap_proby", 0) + 1
            s["limit_ile"] = max(1, int(s["ile"]) // 2)
            self.log(f"Wyprawa: NPC odrzucił {s['ile']} {klucz} (miejsce/cap), próbuję {s['limit_ile']}")
            self._tele("wyprawa_krok", rodzaj="cap_odmowa", przedmiot=klucz, ile=s["ile"], nowe=s["limit_ile"])
            s["krok"] = "buy"
            s["nast"] = teraz + 1.0
            s["odpowiedzi"] = []
            return True
        self.log(f"Wyprawa: nie kupiłem {klucz}: {powod}")
        self._tele("wypad_zakup_odmowa", przedmiot=klucz, powod=powod, odpowiedzi=s["odpowiedzi"][-3:])
        s["wynik"][klucz] = "odmowa"
        if powod in ("brak_zlota", "brak_miejsca"):
            # kolejnych zakupów nie próbujemy, ale jedzenie na miejscu ("@jedz") nadal wykonujemy
            s["lista"] = s["lista"][:s["i"] + 1] + [(k, c) for k, c in s["lista"][s["i"] + 1:] if k == "@jedz"]
        return self._nastepny_przedmiot(s, teraz)

    # --- sklep: jedzenie na miejscu, kolejka ---

    def _sklep(self, poz, teraz):
        if self.w is None:
            return super()._sklep(poz, teraz)
        s = self.sklep
        if s is not None and s["i"] < len(s["lista"]) and s["lista"][s["i"]][0] == "@jedz":
            return self._krok_jedz(s, teraz)
        wynik = super()._sklep(poz, teraz)
        s = self.sklep
        if s is not None:
            self._kolejka(s, teraz)
        return wynik

    def _kolejka(self, s, teraz):
        """NPC rozmawia z kimś innym: nie liczymy tego jako brak odpowiedzi (do KOLEJKA_MAKS razy)."""
        zajete = [t for t in s["odpowiedzi"] if ODP_ZAJETY.search(t)]
        if not zajete or s["krok"] not in ("hi", "hi_czeka"):
            return
        s["odpowiedzi"] = [t for t in s["odpowiedzi"] if not ODP_ZAJETY.search(t)]
        s["kolejka"] = s.get("kolejka", 0) + 1
        if s["kolejka"] > KOLEJKA_MAKS:
            return
        self.log(f"Wyprawa: NPC zajęty ({zajete[-1]!r}), czekam ({s['kolejka']}/{KOLEJKA_MAKS})")
        self._tele("wyprawa_kolejka", n=s["kolejka"])
        s["hi_proby"] = max(0, s["hi_proby"] - 1)
        s["od"] = teraz
        s["krok"] = "hi"                             # po pauzie powitanie od nowa (bez błędu "brak odpowiedzi")
        s["nast"] = max(s["nast"], teraz + KOLEJKA_PAUZA_S)

    def _krok_jedz(self, s, teraz):
        cb = self.cb
        j = s.setdefault("jedz", {"n": 0, "nast": teraz, "pusty": 0, "bledy": 0})
        if not int(self._kw("WYPRAWA_JEDZ_NA_MIEJSCU")):
            return self._jedz_koniec(s, j, "wylaczone", teraz)
        if teraz < j["nast"]:
            cb.pauza(0.2, 0.5)
            return True
        if j["n"] >= int(self._kw("WYPRAWA_JEDZ_MAKS")):
            return self._jedz_koniec(s, j, "limit", teraz)
        try:
            plecak = self.ops.plecak()
        except bot.Zatrzymano:
            raise
        except Exception as ex:
            self._blad("jedz_plecak", opis=repr(ex))
            return self._jedz_koniec(s, j, "blad_odczytu", teraz)
        if not self._jedzenie_ile(plecak):
            return self._jedz_koniec(s, j, "brak_jedzenia", teraz)
        try:
            zjedzone = self.ops.zjedz()
        except bot.Zatrzymano:
            raise
        except Exception as ex:
            j["bledy"] += 1
            self._blad("jedz_wyjatek", opis=repr(ex), n=j["bledy"])
            if j["bledy"] >= 3:
                return self._jedz_koniec(s, j, "blad", teraz)
            j["nast"] = teraz + 1.5
            return True
        pelny = False
        try:
            for w in self.ops.wiadomosci():
                if ODP_PELNY.search(w["tekst"]):
                    pelny = True
        except bot.Zatrzymano:
            raise
        except Exception:
            pass
        if zjedzone:
            j["n"] += len(zjedzone)
            j["pusty"] = 0
            self._tele("wyprawa_krok", rodzaj="jedzenie", zjedzone=list(zjedzone), n=j["n"])
        else:
            j["pusty"] += 1
        if pelny:
            return self._jedz_koniec(s, j, "full", teraz)
        if j["pusty"] >= 2:
            return self._jedz_koniec(s, j, "najedzony", teraz)
        j["nast"] = teraz + random.uniform(0.6, 1.2)
        cb.pauza(0.1, 0.3)
        return True

    def _jedz_koniec(self, s, j, powod, teraz):
        self.log(f"Wyprawa: jedzenie na miejscu: {j['n']} szt., koniec ({powod})")
        self._tele("wyprawa_krok", rodzaj="jedzenie_koniec", n=j["n"], powod=powod)
        s["wynik"]["@jedz"] = f"{powod}:{j['n']}"
        return self._nastepny_przedmiot(s, teraz)

    # --- koniec sklepu / wyprawy ---

    def _koniec_sklepu(self, teraz):
        if self.w is None:
            return super()._koniec_sklepu(teraz)
        s = self.sklep
        wynik = dict(s["wynik"]) if s else {}
        w = self.w
        st = w["stops"][w["k"]]
        w["wyniki"][st["id"]] = wynik
        if any(v in ("kupione", "mam") for k, v in wynik.items() if k != "@jedz"):
            w["sukces"] = True
        self.log(f"Wyprawa: przystanek {st['id']} zakończony: {wynik}")
        self._tele("wypad_krok", rodzaj="sklep_koniec", przystanek=st["id"], wynik=wynik,
                   kupione=dict(self.kupione), czas_s=round(teraz - self.t_start))
        self.sklep = None
        self.wynik = None            # wynik wyprawy liczy _sukces()
        w["k"] += 1
        if w["k"] < len(w["stops"]):
            self.faza, self.etapy = "do", w["legs"][w["k"]]
            self.npc = w["stops"][w["k"]]["npc"]
        else:
            self.faza, self.etapy = "z", w["powrot"]
        poz = self.cb.postac.pozycja()
        self.ei = self.pi = 0
        if not self._resync_globalny(poz):
            return self._awaria("zgubiona_pozycja", f"po sklepie poz {poz}")
        self.postep = None
        self.przystanek_od = None
        self.cb._wypad_reset_klik()
        self._stan_trasy()
        return True

    def _sukces(self):
        if self.w is not None:
            return bool(self.w.get("sukces"))
        return super()._sukces()

    def _alarm_utknieciu(self, opis, stop=True):
        self._powiadom("Wyprawa: UTKNĘŁA", opis + (" Bot zatrzymany, potrzebny człowiek." if stop else ""),
                       "critical", "wyprawa_utknela")
        al = getattr(self.cb, "alarm", None)
        if callable(al):
            try:
                al(f"wyprawa: {opis}")
            except Exception:
                pass
        if stop and int(self._kw("WYPRAWA_STOP_PRZY_UTKNIECIU")):
            try:
                plik = self.plik_stop or bot.STOP
                Path(plik).write_text(f"wyprawa: {opis}\n")
                self.log(f"Wyprawa: zapisałem {plik} (zatrzymanie bota)")
            except OSError as e:
                self.log(f"Wyprawa: nie zapisałem STOP ({e})")

    def _koniec(self, wynik, opis):
        w = self.w
        if w is not None:
            teraz = self.cb.zegar()
            if wynik == "blad" and self.faza == "z" and opis != "teleport":
                self._alarm_utknieciu(f"{opis or 'utknięcie w drodze powrotnej'} (poz {tuple(self.cb.postac.pozycja())})")
            self.nast_wyprawa = teraz + float(self._kw("WYPRAWA_CO_MIN")) * 60.0
            self._stan_koniec(wynik=wynik, opis=opis, kupione=dict(self.kupione),
                              nast_wall=self.czas() + float(self._kw("WYPRAWA_CO_MIN")) * 60.0,
                              wyniki=w.get("wyniki"))
            self._tele("wyprawa_koniec", wynik=wynik, opis=opis, kupione=dict(self.kupione),
                       wyniki=w.get("wyniki"), czas_s=round(teraz - self.t_start))
            self.w = None
            self._plan_wyprawy = None
        return super()._koniec(wynik, opis)

    def przerwij(self, powod):
        if self.w is not None:
            if str(powod).upper().startswith("ALARM"):
                self._stan_koniec(wynik="przerwana", powod=str(powod))
            else:
                # STOP: zapis zostaje (przerwana=True), kolejny start bota wznowi wyprawę od najbliższego odcinka
                self._stan_zapisz(przerwana=True, zapis_wall=self.czas())
            self.w = None
            self._plan_wyprawy = None
        return super().przerwij(powod)


# --- CLI: sprawdzenie danych bez ruszania gry -----------------------------------

def raport(katalog=TRASY, plik_sklepow=PLIK_SKLEPOW, plik_npc=PLIK_NPC, mapa=None, log=print):
    """Czego brakuje do uruchomienia wyprawy; zwraca listę problemów (puste = gotowe do prób)."""
    problemy = []
    baza = punkty_bazy(katalog)
    for n in BAZY:
        if n not in baza:
            problemy.append(f"brak plików trasy bazowej {n} (generuj_trase_miasta.py)")
        else:
            do, z, npc = baza[n]
            log(f"baza {n}: do_miasta {len(do)} pkt -> {do[-1]} (NPC {npc}), z_miasta {len(z)} pkt od {z[0]}")
    cfg = wczytaj_sklepy(plik_sklepow)
    npc = wczytaj_npc(plik_npc)
    for klucz, domyslny in (("frodo", "Frodo"), ("xodet", "Xodet")):
        c = cfg.get(klucz, {})
        nazwa = c.get("npc") or domyslny
        if c.get("stoi") or c.get("npc_poz") or nazwa in npc:
            zr = "stoi" if c.get("stoi") else ("npc_poz" if c.get("npc_poz") else "uczone z widoku")
            log(f"{klucz}: pozycja znana ({zr}), zweryfikowana={c.get('zweryfikowane', False)}")
        else:
            problemy.append(f"{klucz}: brak pozycji (wpisz 'stoi' albo 'npc_poz' w {Path(plik_sklepow).name} "
                            f"albo przejdź obok NPC {nazwa} z działającym botem)")
    if mapa is not None and baza:
        t = Trasownik(mapa)
        for klucz, domyslny in (("frodo", "Frodo"), ("xodet", "Xodet")):
            c = cfg.get(klucz, {})
            nazwa = c.get("npc") or domyslny
            n0 = next(iter(baza.values()))
            do = n0[0]
            if c.get("stoi"):
                pts = t.odcinek(do[-1], tuple(c["stoi"]))
            elif c.get("npc_poz") or nazwa in npc:
                r = t.stoisko(do[-1], tuple(c.get("npc_poz") or npc[nazwa]))
                pts = r[1] if r else None
            else:
                continue
            log(f"{klucz}: A* od {do[-1]}: " + (f"{len(pts)} pkt, koniec {pts[-1]}" if pts else "BRAK DROGI"))
            if not pts:
                problemy.append(f"{klucz}: brak drogi po mapie od Gorna")
    return problemy


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "plan"
    if cmd == "stan":
        print(json.dumps(_json(PLIK_STANU), ensure_ascii=False, indent=1))
        return 0
    if cmd == "plan":
        mapa = None
        try:
            import mapa as _m  # noqa: PLC0415
            mapa = _m.Mapa()
        except Exception as e:
            print(f"mapa niedostępna ({e!r}), sprawdzam tylko pliki")
        problemy = raport(mapa=mapa)
        for p in problemy:
            print("DO ZROBIENIA:", p)
        print("gotowe do prób" if not problemy else f"{len(problemy)} rzeczy do uzupełnienia")
        return 0 if not problemy else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
