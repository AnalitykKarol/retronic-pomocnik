"""Wpadnięcie (15.10): bot sam wychodzi, gdy niespodziewanie zmieni piętro (wpadnie w dziurę, której mapa nie
oznaczyła albo którą ominął A*). Przypadek 15.10 09:11:47: z (33080,31741,8) na (33081,31742,9), potem minuty
kręcenia się po z9 ("Sorry, not possible"), bo punkty trasy leżą na z8.

Przebieg (Cavebot.tick woła obserwuj() na początku każdego obiegu i tick() po walce, przed idz()):
  1. WYKRYCIE: piętro zmieniło się poza planowanym przejściem (nie pietra.py, nie wypad/wyprawa/dojście), pole
     lądowania jest blisko poprzedniej pozycji (WPADNIECIE_ODL): log "Wpadłem: (x,y,z0) -> (x,y,z1)", telemetria,
     zatrzymanie pościgu i kliknięć. Stan WPADNIECIE tylko, gdy trasa/patrol nie ma punktów na nowym piętrze.
  2. NAUKA: dziura = (x lądowania, y lądowania, z0) -> trasy/dziury_nauczone.json (zapis atomowy, wczytywane przy
     starcie). Cavebot traktuje te pola jak ścianę we WSZYSTKICH drogach A* (droga, _droga_do, unikanie, loot) i
     w krokach (pole_zmiany_pietra).
  3. WYJŚCIE: (a) lina: Use liny na polu lądowania (rope spot pod dziurą), do WPADNIECIE_LINA_PROB prób; lina z
     plecaka, a gdy jej tam nie ma, ze slotu ekwipunku 10 (jak pochodnia.py); (b) plan po mapie: wielopiętrowy
     Dijkstra po przejściach (mapa_doswiadczenia.json, miejsca_troll.json "przejscia", nagrane trasy, na końcu
     niepewne flagi 2 z mapy), przejście wykonuje pietra.py; (c) nic nie działa albo PIETRA_MAX_S: ALARM,
     powiadomienie krytyczne i plik STOP (bot się zatrzymuje zamiast kręcić się w kółko).
  4. Powrót na piętro trasy: najbliższy punkt trasy po drodze (_wypad_wroc_na_trase / _patrol_sync_idx).
Pokrętła (cavebot.py + pokretla.py): WPADNIECIE, WPADNIECIE_LINA, WPADNIECIE_PLAN, DZIURY_NAUCZONE (0/1, domyślnie 1),
WPADNIECIE_ODL, WPADNIECIE_LINA_PROB."""
import heapq
import json
import os
import time
from pathlib import Path

import bot

KATALOG = Path(__file__).resolve().parent
# w testach (RETRONIC_TESTY) bez pliku, chyba że test sam ustawi PLIK_DZIUR
PLIK_DZIUR = None if os.environ.get("RETRONIC_TESTY") else KATALOG / "trasy" / "dziury_nauczone.json"
PLIK_DOSWIADCZENIA = KATALOG / "dane_tibia" / "ruch" / "mapa_doswiadczenia.json"
PLIK_MIEJSC_TROLL = KATALOG / "trasy" / "miejsca_troll.json"
KATALOG_TRAS = KATALOG / "trasy"
ID_LINA = 3003
SLOT_LINY = 10                    # lina w slocie amunicji (jak pochodnia), gdy nie ma jej w oknie plecaka
KARENCJA_S = 5.0                  # tyle s po planowanym przejściu (pietra.py, wypad, dojście) zmiana piętra nie jest wpadnięciem
WIEK_PROBKI_S = 15.0              # starsza poprzednia pozycja nie liczy się (długi postój, teleport, śmierć)
NIEPEWNA_KARA = 150               # pola doliczane do kosztu przejścia z flagi 2 mapy (najpierw pewne z danych)
PRZEJSCIE_KOSZT = 10
PLAN_MAX_PIETER = 4               # maks. przejść w jednym planie
PLAN_MAX_ROZWINIEC = 40
PLAN_MAX_KAND = 14                # maks. przejść na piętrze, do których liczymy drogę
PROMIEN_MAPY = 25                 # pola: okno szukania niepewnych przejść w górę (flaga 2 piętro wyżej)
PLAN_PROBY = 3                    # tyle razy z rzędu brak planu = koniec (alarm)
OSIAG_KAND = 6                    # 15.10 (kieszeń): ile najbliższych punktów trasy/miejsc na piętrze sprawdzamy A*
OSIAG_ODSWIEZ_S = 3.0             # co ile s w stanie WPADNIECIE ponawiamy sprawdzenie "trasa osiągalna"


def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


class Wpadniecie:
    def __init__(self, cb, konf=None, log=print, plik=None, plik_stop=None):
        self.cb = cb
        self.konf = konf
        self.log = log
        self.plik = plik if plik is not None else PLIK_DZIUR
        self.plik_stop = plik_stop
        self.dziury = set()               # {(x, y, z)}: pole piętra z, na którym krok kończy się upadkiem
        self.st = None                    # bieżące wpadnięcie
        self._ost = None                  # (poz, czas) z poprzedniego obiegu
        self._plan_t = float("-inf")      # kiedy ostatnio widziano wypad/wyprawę/dojście
        self._przejscia = None            # leniwa lista przejść z danych
        self.wykryte = 0
        self.wczytaj()

    def _k(self, nazwa, domyslna):
        return getattr(self.konf, nazwa, domyslna) if self.konf is not None else domyslna

    def _tele(self, typ, **d):
        t = getattr(self.cb, "tele", None)
        if t is not None:
            try:
                t.zdarzenie(typ, **d)
            except Exception:
                pass

    # --- nauczone dziury ---

    def wczytaj(self):
        self.dziury = set()
        try:
            if self.plik is not None and Path(self.plik).exists():
                d = json.loads(Path(self.plik).read_text())
                lista = d.get("dziury", []) if isinstance(d, dict) else d
                for e in lista:
                    if isinstance(e, dict):
                        e = (e["x"], e["y"], e["z"])
                    self.dziury.add((int(e[0]), int(e[1]), int(e[2])))
        except Exception as e:
            self.log(f"Wpadnięcie: nie wczytano {self.plik} ({e!r})")

    def zapisz(self):
        if self.plik is None:
            return
        try:
            tmp = Path(str(self.plik) + ".tmp")
            tmp.write_text(json.dumps(
                {"_opis": "pola (x, y, piętro), na których krok kończył się niespodziewanym upadkiem; bot traktuje je jak ścianę",
                 "dziury": [list(p) for p in sorted(self.dziury)]}, indent=1))
            os.replace(tmp, self.plik)
        except Exception as e:
            self.log(f"Wpadnięcie: nie zapisałem {self.plik} ({e!r})")

    def ucz(self, pole):
        pole = (int(pole[0]), int(pole[1]), int(pole[2]))
        if pole in self.dziury:
            return False
        self.dziury.add(pole)
        self.zapisz()
        self.log(f"Wpadnięcie: nauczona dziura {pole[:2]} na z{pole[2]} (od teraz ściana dla dróg A*).")
        return True

    def lista(self, z, start=None, cel=None, margines=30):
        """Dziury piętra z jako lista (x, y, z) dla A* (w prostokącie start-cel z marginesem, jeśli podano)."""
        wyn = [p for p in self.dziury if p[2] == z]
        if start is not None and cel is not None:
            x0, x1 = sorted((start[0], cel[0]))
            y0, y1 = sorted((start[1], cel[1]))
            wyn = [p for p in wyn if x0 - margines <= p[0] <= x1 + margines and y0 - margines <= p[1] <= y1 + margines]
        return wyn

    # --- wykrycie ---

    def _planowane(self, teraz):
        cb = self.cb
        if getattr(cb, "wypad_aktywny", False) or getattr(cb, "dojscie_aktywne", False):
            self._plan_t = teraz
        w = getattr(cb, "wyprawa", None)
        if w is not None and getattr(w, "w", None) is not None:
            self._plan_t = teraz
        if teraz - self._plan_t < KARENCJA_S:
            return True
        if teraz - getattr(cb, "pietra_zmiana_t", float("-inf")) < KARENCJA_S:
            return True
        return False

    def _trasa_na_pietrze(self, z):
        cb = self.cb
        if any(p[2] == z for p in (cb.punkty or [])):
            return True
        try:
            if cb._patrol_pietra_ok() and any(m.get("z") == z for m in (cb.miejsca or [])):
                return True
        except Exception:
            pass
        return False

    def _kandydaci_trasy(self, z):
        """Punkty trasy i miejsca patrolu (x, y) leżące na piętrze z (miejsca tylko gdy patrol wielopiętrowy je uwzględnia)."""
        cb = self.cb
        wyn = [(p[0], p[1]) for p in (cb.punkty or []) if p[2] == z]
        try:
            if cb._patrol_pietra_ok():
                wyn += [(m["x"], m["y"]) for m in (cb.miejsca or []) if m.get("z") == z]
        except Exception:
            pass
        return wyn

    def _trasa_osiagalna(self, p):
        """15.10 (kieszeń): trasa/patrol ma punkty na piętrze p.z ORAZ któryś z najbliższych jest osiągalny A* (cb.droga:
        mapa serwera + nauczone ściany) z pozycji p. Upadek do zamkniętej kieszeni z9 (32506..32509, 32267..32273) miał
        punkty trasy na z9, ale żaden nieosiągalny: samo "piętro jest na trasie" nie wystarcza. Bez cb.droga albo przy
        błędzie A*: dawne zachowanie (wystarcza piętro)."""
        cb = self.cb
        if not self._trasa_na_pietrze(p[2]):
            return False
        droga = getattr(cb, "droga", None)
        if droga is None:
            return True
        kand = sorted(set(self._kandydaci_trasy(p[2])), key=lambda q: _cheb(q, p))[:OSIAG_KAND]
        if not kand:
            return True                       # piętro jest na trasie, ale bez punktów do sprawdzenia: dawne zachowanie
        blad = False
        for q in kand:
            if _cheb(q, p) <= 1:
                return True
            try:
                if droga((p[0], p[1], p[2]), q, dlugosc=1) is not None:
                    return True
            except bot.Zatrzymano:
                raise
            except Exception:
                blad = True
        return blad                           # błąd A* = nie wiemy: dawne zachowanie

    def z_kieszeni(self, poz, teraz):
        """15.10: patrol nie znalazł osiągalnego miejsca (np. start bota w kieszeni bez wykrytego upadku). Jeśli żaden
        punkt trasy/miejsce na piętrze poz.z nie jest osiągalny A*, a trasa ma punkty na innym piętrze: wchodzimy w stan
        WPADNIECIE (z0 = piętro najbliższego takiego punktu), jak po upadku, ale bez liny (nie znamy rope spotu).
        True = stan ustawiony."""
        if self.st is not None:
            return False
        cb = self.cb
        p = (int(poz[0]), int(poz[1]), int(poz[2]))
        if self._trasa_osiagalna(p):
            return False
        inne = [(q[0], q[1], q[2]) for q in (cb.punkty or []) if q[2] != p[2]]
        try:
            inne += [(m["x"], m["y"], m["z"]) for m in (cb.miejsca or []) if m.get("z") not in (None, p[2])]
        except Exception:
            pass
        if not inne:
            return False
        z0 = min(inne, key=lambda q: (abs(q[2] - p[2]), _cheb(q, p)))[2]
        self.wykryte += 1
        self.log(f"Wpadnięcie: kieszeń, z{p[2]} {p[:2]} bez osiągalnego punktu trasy/miejsca, wychodzę na z{z0} planem po mapie.")
        self._tele("wpadniecie_kieszen", poz=list(p), z0=z0, n=self.wykryte)
        try:
            cb.zatrzymaj_klik(p)
        except bot.Zatrzymano:
            raise
        except Exception:
            pass
        cb.cel = None
        cb._wypad_reset_klik()
        self.st = {"z0": z0, "z1": p[2], "od": teraz, "p0": p, "lad": p, "lina": int(self._k("WPADNIECIE_LINA_PROB", 3)),
                   "dojscie": 0, "nast": teraz, "zle": set(), "krok": None, "brak_planu": 0, "alarm": False,
                   "osiag": (teraz, False)}
        return True

    def obserwuj(self, poz, teraz):
        """Początek obiegu: porównanie z poprzednią pozycją. True, gdy wykryto wpadnięcie."""
        p = (int(poz[0]), int(poz[1]), int(poz[2]))
        prev, self._ost = self._ost, (p, teraz)
        planowane = self._planowane(teraz)
        if prev is None or prev[0][2] == p[2] or self.st is not None:
            return False
        if planowane:
            return False
        p0, t0 = prev
        if teraz - t0 > WIEK_PROBKI_S:
            return False
        if _cheb(p0, p) > int(self._k("WPADNIECIE_ODL", 3)):
            return False
        return self._wykryto(p0, p, teraz)

    def _flaga_mapy(self, x, y, z):
        m = getattr(self.cb, "mapa", None)
        try:
            return int(m.flagi(x, y, z)) if m is not None else None
        except Exception:
            return None

    def _przejscia_troll(self):
        """Pola przejść z trasy/miejsca_troll.json (wszystkie pola opisujące przejście) jako zbiór (x, y, z)."""
        if getattr(self, "_pola_troll", None) is None:
            wyn = set()
            try:
                for e in json.loads(PLIK_MIEJSC_TROLL.read_text()).get("przejscia", []):
                    for k in ("pole", "wejscie_gora", "wyjscie_dol", "wejscie_dol", "wyjscie_gora"):
                        if e.get(k) and len(e[k]) == 3:
                            wyn.add(tuple(int(v) for v in e[k]))
            except Exception:
                pass
            self._pola_troll = wyn
        return self._pola_troll

    def _walidacja(self, p0, p):
        """WPADNIECIE_WALIDACJA=1: czy pole (p.x, p.y, z0) wolno uczyć jako dziurę. None = wolno, inaczej powód odmowy."""
        import pietra  # noqa: PLC0415
        z0, z1 = p0[2], p[2]
        m = getattr(self.cb, "mapa", None)
        f = self._flaga_mapy(p[0], p[1], z0)
        if m is None or f is None or not (f & 2) or f & 4:
            return "bez dziury na mapie"
        troll = self._przejscia_troll()
        for c in (p, p0):
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    x, y = c[0] + dx, c[1] + dy
                    if pietra._schody(m, (x, y, z0), (x, y, z1)) or (x, y, z0) in troll or (x, y, z1) in troll:
                        return "przejście schodowe w pobliżu"
        return None

    def _wykryto(self, p0, p, teraz):
        cb = self.cb
        z0, z1 = p0[2], p[2]
        self.wykryte += 1
        self.log(f"Wpadłem: ({p0[0]},{p0[1]},{z0}) -> ({p[0]},{p[1]},{z1})")
        nauczona = False
        extra = {}
        if z1 == z0 + 1 and self._k("DZIURY_NAUCZONE", 1):
            if self._k("WPADNIECIE_WALIDACJA", 0):
                powod = self._walidacja(p0, p)
                extra["znana"] = (p[0], p[1], z0) in self.dziury
                if powod:
                    self.log(f"Wpadnięcie: nie uczę dziury {p[:2]} na z{z0} ({powod}).")
                    if powod == "bez dziury na mapie":
                        self._tele("wpadniecie_bez_dziury", opis="wpadniecie bez dziury na mapie", poz_od=list(p0),
                                   poz_do=list(p), flaga=self._flaga_mapy(p[0], p[1], z0))
                else:
                    nauczona = self.ucz((p[0], p[1], z0))
            else:
                nauczona = self.ucz((p[0], p[1], z0))
        w_trasie = self._trasa_osiagalna(p)
        self._tele("wpadniecie", z_od=z0, z_do=z1, poz_od=list(p0), poz_do=list(p), nauczona=nauczona,
                   w_trasie=w_trasie, n=self.wykryte, **extra)
        # zatrzymanie pościgu i kliknięć
        try:
            cb.zatrzymaj_klik(p0)
        except bot.Zatrzymano:
            raise
        except Exception:
            pass
        cb.cel = None
        try:
            if getattr(cb, "pamiec", None):
                cb._pamiec_koniec("przerwany", "wpadniecie", p)
        except Exception:
            pass
        cb._wypad_reset_klik()
        if w_trasie:
            self.log(f"Wpadnięcie: z{z1} jest na trasie/patrolu (punkt osiągalny), dalej normalnie (pietra.py zsynchronizuje trasę).")
            return True
        if self._trasa_na_pietrze(z1):
            self.log(f"Wpadnięcie: z{z1} ma punkty trasy/patrolu, ale żaden nie jest osiągalny z {p[:2]} (kieszeń), szukam wyjścia.")
        self.st = {"z0": z0, "z1": z1, "od": teraz, "p0": p0, "lad": p, "lina": 0, "dojscie": 0, "nast": teraz,
                   "zle": set(), "krok": None, "brak_planu": 0, "alarm": False, "osiag": (teraz, False)}
        return True

    # --- obieg ---

    def aktywne(self):
        return self.st is not None

    def tick(self, poz, teraz):
        """True = obieg zużyty (wpadnięcie w toku), None = nic do roboty."""
        st = self.st
        if st is None:
            return None
        cb = self.cb
        p = (int(poz[0]), int(poz[1]), int(poz[2]))
        if p[2] == st["z0"]:
            return self._powrot(p, teraz)
        if p[2] != st["z1"]:
            self.log(f"Wpadnięcie: kolejna zmiana piętra z{st['z1']} -> z{p[2]} w {p}, liczę od nowa.")
            st.update(z1=p[2], lad=p, lina=int(self._k("WPADNIECIE_LINA_PROB", 3)), krok=None, nast=teraz,
                      osiag=(float("-inf"), False))
        if p[2] != st["z0"] and st["krok"] is None and teraz - st["osiag"][0] >= OSIAG_ODSWIEZ_S:
            st["osiag"] = (teraz, self._trasa_osiagalna(p))        # A* ma limit; w kieszeni kończy się od razu
        if p[2] != st["z0"] and st["osiag"][1]:
            self.log(f"Wpadnięcie: z{p[2]} jest na trasie (punkt osiągalny), koniec wpadnięcia.")
            self.st = None
            return None
        cb.ustaw_stan("WPADNIECIE", f"z{st['z0']} <- z{p[2]} od {teraz - st['od']:.0f} s")
        if st["alarm"]:
            cb.pauza(1.0, 2.0)
            return True
        if teraz - st["od"] > float(self._k("PIETRA_MAX_S", 150.0)):
            return self._alarm(f"limit czasu {self._k('PIETRA_MAX_S', 150.0):.0f} s", p)
        if st["krok"] is not None:
            return self._krok(p, teraz)
        if teraz < st["nast"]:
            cb.pauza(0.2, 0.5)
            return True
        lina_prob = int(self._k("WPADNIECIE_LINA_PROB", 3))
        if self._k("WPADNIECIE_LINA", 1) and p[2] == st["z0"] + 1 and st["lina"] < lina_prob:
            return self._lina(p, teraz)
        if self._k("WPADNIECIE_PLAN", 1):
            r = self._plan(p, teraz)
            if r is not None:
                return r
        return self._alarm("lina i plan po mapie nie działają", p)

    # --- (a) lina ---

    def _ops(self):
        cb = self.cb
        o = getattr(cb, "pietra_ops", None)
        if o is None:
            w = getattr(cb, "wyprawa", None)
            o = getattr(w, "ops", None)
        if o is None:
            try:
                import wypad  # noqa: PLC0415
                o = wypad.OperacjeZywe(log=self.log)
            except Exception:
                o = None
        cb.pietra_ops = o
        return o

    def _uzyj_liny(self, spot, poz):
        ops = self._ops()
        if ops is None:
            raise RuntimeError("brak operacji na ekranie")
        try:
            ops.uzyj_line(spot, poz)
            return
        except bot.Zatrzymano:
            raise
        except Exception as ex:
            if type(ex).__name__ != "BrakEkranu" or getattr(ops, "ekwipunek", None) is None:
                raise
            blad = ex
        self.log(f"Wpadnięcie: liny nie ma w plecaku ({blad}), próbuję ze slotu {SLOT_LINY} ekwipunku.")
        self._lina_z_ekwipunku(ops, spot, poz)

    def _lina_z_ekwipunku(self, ops, spot, poz):
        """Ctrl+klik na linie w slocie ekwipunku (jak pochodnia.uzyj_slot), potem klik na polu `spot` (<= 1 od `poz`)."""
        e = ops.ekwipunek() or {}
        slot = next((s for s, i in e.items() if int(i) == ID_LINA), None)
        if slot is None:
            raise RuntimeError("liny (3003) nie ma ani w plecaku, ani w ekwipunku")
        ez = getattr(ops, "uzyj_z_ekwipunku", None)
        if ez is not None:
            ez(slot, spot, poz)
            return
        import ekran  # noqa: PLC0415
        import loot  # noqa: PLC0415
        import pochodnia  # noqa: PLC0415
        dx, dy = spot[0] - poz[0], spot[1] - poz[1]
        if abs(dx) > 1 or abs(dy) > 1:
            raise RuntimeError(f"pole liny {spot[:2]} za daleko od {tuple(poz)}")
        with ekran.Mysz() as mysz:
            obraz = loot._zrzut(mysz)
            xy = pochodnia.pozycje_ekwipunku(obraz).get(int(slot))
            if xy is None:
                raise RuntimeError("nie widzę panelu Inventory")
            mysz.klik(xy[0], xy[1], 1, "Control_L", drganie=3)
            time.sleep(0.45)
            mysz.klik(*ekran.pole_na_ekran(dx, dy, ekran.aktualny_prostokat(mysz.ekran)), 1, None, drganie=2)

    def _lina(self, p, teraz):
        cb = self.cb
        st = self.st
        spot = (st["lad"][0], st["lad"][1], st["z1"])       # rope spot = pole lądowania pod dziurą
        if _cheb(p, spot) > 1:
            st["dojscie"] += 1
            if st["dojscie"] > 40:
                self.log(f"Wpadnięcie: nie dochodzę do rope spotu {spot[:2]}, rezygnuję z liny.")
                st["lina"] = int(self._k("WPADNIECIE_LINA_PROB", 3))
                return True
            r = cb.podejdz((spot[0], spot[1]), p, objazd=False, dlugosc=0)
            if r is None or r is False:
                cb.nieudane += 1
                cb.pauza(0.2, 0.5)
            return True
        lim = int(self._k("WPADNIECIE_LINA_PROB", 3))
        st["lina"] += 1
        n = st["lina"]
        try:
            cb.zatrzymaj_klik(p)
        except bot.Zatrzymano:
            raise
        except Exception:
            pass
        cb.klik_cel = None
        self.log(f"Wpadnięcie: lina, próba {n}/{lim} na polu {spot[:2]} z {p}")
        self._tele("wpadniecie_lina", proba=n, poz=list(p), pole=list(spot))
        try:
            self._uzyj_liny(spot, p)
        except bot.Zatrzymano:
            raise
        except Exception as ex:
            self.log(f"Wpadnięcie: lina nie wyszła ({ex!r})")
            st["nast"] = cb.zegar() + 1.0
            return True
        for _ in range(5):                                  # czekamy na zmianę piętra (jak pietra._po_przejsciu)
            cb.spij(0.4)
            q = cb.postac.pozycja()
            if q[2] != p[2]:
                self.log(f"Wpadnięcie: lina zadziałała, z{p[2]} -> z{q[2]} w {tuple(q)} (próba {n}).")
                self._tele("wpadniecie_lina_ok", proba=n, poz=list(q))
                return True
        self.log(f"Wpadnięcie: lina bez skutku (próba {n}/{lim}).")
        st["nast"] = cb.zegar() + 1.0
        return True

    # --- (b) plan po mapie ---

    def _wczytaj_przejscia(self):
        """Pewne przejścia z danych: dict(T, L, zrodlo). T = pole na piętrze startu przejścia, L = lądowanie."""
        if self._przejscia is not None:
            return self._przejscia
        wyn, widziane = [], set()

        def dodaj(T, L, zrodlo):
            T, L = tuple(int(v) for v in T[:3]), tuple(int(v) for v in L[:3])
            if (T, L) in widziane or T[2] == L[2]:
                return
            widziane.add((T, L))
            wyn.append({"T": T, "L": L, "pewne": True, "zrodlo": zrodlo})

        try:
            d = json.loads(PLIK_DOSWIADCZENIA.read_text())
            for e in d.get("przejscia", []):
                dodaj(e["pole_gora"], e["ladowanie_w_dol"], "doswiadczenie")
                dodaj(e["pole_dol_R"], e["ladowanie_w_gore"], "doswiadczenie")
        except Exception:
            pass
        try:
            d = json.loads(PLIK_MIEJSC_TROLL.read_text())
            for e in d.get("przejscia", []):
                dodaj(e["pole"], e["wyjscie_dol"], "miejsca_troll")
                dodaj(e["wyjscie_dol"], e["wyjscie_gora"], "miejsca_troll")
        except Exception:
            pass
        try:
            for plik in sorted(KATALOG_TRAS.glob("*.json")):
                try:
                    pts = json.loads(plik.read_text())
                except Exception:
                    continue
                if not isinstance(pts, list) or not pts or not all(
                        isinstance(q, list) and len(q) == 3 and all(isinstance(v, int) for v in q) for q in pts):
                    continue
                for a, b in zip(pts, pts[1:]):
                    if a[2] == b[2]:
                        continue
                    if b[2] > a[2]:                       # w dół: wejście na pole dziury, lądowanie pod nim
                        dodaj((b[0], b[1], a[2]), b, plik.name)
                    else:                                 # w górę: konwencja wypad.py, R = (b.x, b.y-1) piętro niżej
                        dodaj((b[0], b[1] - 1, a[2]), b, plik.name)
        except Exception:
            pass
        self._przejscia = wyn
        return wyn

    def _z_mapy_w_gore(self, poz):
        """Niepewne przejścia w górę z flag mapy: pole R piętra poz.z, nad którym (piętro wyżej) jest flaga 2."""
        m = self.cb.mapa
        z = poz[2]
        if m is None or z <= 0:
            return []
        wyn = []
        for dx in range(-PROMIEN_MAPY, PROMIEN_MAPY + 1):
            for dy in range(-PROMIEN_MAPY, PROMIEN_MAPY + 1):
                x, y = poz[0] + dx, poz[1] + dy
                f = m.flagi(x, y, z)
                if not f & 1 or f & 4:
                    continue
                g = m.flagi(x, y, z - 1)
                if not (g & 1 and g & 2 and not g & 4):
                    continue
                lf = m.flagi(x, y + 1, z - 1)
                if not lf & 1 or lf & 4:
                    continue
                wyn.append({"T": (x, y, z), "L": (x, y + 1, z - 1), "pewne": False, "zrodlo": "mapa_flaga2"})
        wyn += self._z_mapy_schody_tu(poz)
        return wyn

    def _z_mapy_schody_tu(self, poz):
        """15.10 (kieszeń): niepewne przejścia w górę z flagi 2 na WŁASNYM piętrze (drabina/schody w górę stoją na polu
        piętra z, nie pod dziurą piętra z-1). Lądowanie nieznane: pierwsze chodliwe pole obok (x, y+1), (x, y-1), (x+1, y),
        (x-1, y), (x, y) na z-1. Dziury w dół (chodliwe pole pod spodem, nauczone dziury) pomijamy. pietra.py próbuje
        R (Ctrl+klik) i krok, sukces = zmiana piętra."""
        m = self.cb.mapa
        z = poz[2]
        if m is None or z <= 0:
            return []
        wyn = []
        for dx in range(-PROMIEN_MAPY, PROMIEN_MAPY + 1):
            for dy in range(-PROMIEN_MAPY, PROMIEN_MAPY + 1):
                x, y = poz[0] + dx, poz[1] + dy
                f = m.flagi(x, y, z)
                if not (f & 1 and f & 2) or f & 4 or (x, y, z) in self.dziury:
                    continue
                pod = m.flagi(x, y, z + 1)
                if pod & 1 and not pod & 4:
                    continue                          # coś chodliwego pod spodem = górny koniec dziury/schodów (w dół), nie wyjście w górę
                L = None
                for lx, ly in ((x, y + 1), (x, y - 1), (x + 1, y), (x - 1, y), (x, y)):
                    lf = m.flagi(lx, ly, z - 1)
                    if lf & 1 and not lf & 4:
                        L = (lx, ly, z - 1)
                        break
                if L is not None:
                    wyn.append({"T": (x, y, z), "L": L, "pewne": False, "zrodlo": "mapa_flaga2_tu"})
        return wyn

    def _znajdz_plan(self, p, zle):
        """Najtańsza sekwencja przejść z piętra p.z na piętro z0 (lista słowników T, L, pewne) albo None."""
        cb = self.cb
        cel_z = self.st["z0"]
        dane = self._wczytaj_przejscia()
        licznik = 0
        kopiec = [(0, licznik, p, [])]
        odw = set()
        rozwiniete = 0
        while kopiec and rozwiniete < PLAN_MAX_ROZWINIEC:
            koszt, _, poz, sciezka = heapq.heappop(kopiec)
            if poz[2] == cel_z:
                return sciezka
            if poz in odw or len(sciezka) >= PLAN_MAX_PIETER:
                continue
            odw.add(poz)
            rozwiniete += 1
            kand = [t for t in dane if t["T"][2] == poz[2]] + self._z_mapy_w_gore(poz)
            kand = [t for t in kand if t["T"] not in zle and _cheb(t["T"], poz) <= 80]
            kand.sort(key=lambda t: (_cheb(t["T"], poz), not t["pewne"]))
            for t in kand[:PLAN_MAX_KAND]:
                try:
                    d = [] if _cheb(t["T"], poz) <= 1 else cb.droga(poz, (t["T"][0], t["T"][1]), dlugosc=1)
                except Exception:
                    d = None
                if d is None:
                    continue
                c = koszt + len(d) + PRZEJSCIE_KOSZT + (0 if t["pewne"] else NIEPEWNA_KARA)
                licznik += 1
                heapq.heappush(kopiec, (c, licznik, t["L"], sciezka + [t]))
        return None

    def _plan(self, p, teraz):
        """Jeden obieg planu: znajdź plan, ustaw pierwsze przejście w pietra.py. None = brak planu (alarm)."""
        cb = self.cb
        st = self.st
        plan = self._znajdz_plan(p, st["zle"])
        if plan is None:
            st["brak_planu"] += 1
            self.log(f"Wpadnięcie: brak planu po mapie z {p} ({st['brak_planu']}/{PLAN_PROBY}).")
            if st["brak_planu"] >= PLAN_PROBY:
                return None
            st["nast"] = cb.zegar() + 2.0
            return True
        st["brak_planu"] = 0
        opis = " -> ".join(f"{t['T'][:2]}z{t['T'][2]}>z{t['L'][2]}{'' if t['pewne'] else '?'}" for t in plan)
        self.log(f"Wpadnięcie: plan po mapie z {p}: {opis}")
        t = plan[0]
        try:
            import pietra  # noqa: PLC0415
        except Exception as e:
            self.log(f"Wpadnięcie: pietra.py niedostępne ({e!r})")
            return None
        if cb.pietra is None:
            cb.pietra = pietra.Pietra(cb, konf=self.konf, log=self.log)
        cel = tuple(t["L"])
        cb.pietra.st = {"cel": cel, "a": tuple(p), "z0": p[2], "od": teraz,
                        "kand": [{"pole": tuple(t["T"]), "pewne": bool(t["pewne"]), "lad": cel}], "ki": 0,
                        "proby": 0, "nast": teraz, "postep": [teraz, 999], "tryby": None}
        st["krok"] = {"T": tuple(t["T"]), "cel": cel, "z": p[2], "od": teraz}
        self._tele("wpadniecie_plan", poz=list(p), przejscie=[list(t["T"]), list(t["L"])], pewne=bool(t["pewne"]),
                   kroki=len(plan))
        return self._krok(p, teraz)

    def _krok(self, p, teraz):
        """Jeden obieg przejścia pięter z planu (pietra.py). Nieudane przejście = pole do złych i nowy plan."""
        cb = self.cb
        st = self.st
        k = st["krok"]
        pi = cb.pietra
        if p[2] != k["z"]:
            st["krok"] = None
            if pi is not None:
                pi.st = None
            self.log(f"Wpadnięcie: przejście z planu zadziałało, z{k['z']} -> z{p[2]} w {p}.")
            return True
        if pi is None or pi.st is None:
            return self._krok_porazka(k, p, "pietra.py zakończyło próby")
        porazki = getattr(cb, "pietra_porazki", 0)
        cb.__dict__["_pietra_zawroc"] = lambda poz: None       # porażka planu nie odwraca trasy łowiska
        try:
            wynik = pi.tick(p, k["cel"])
        finally:
            cb.__dict__.pop("_pietra_zawroc", None)
            cb.pietra_porazki = porazki
        q = tuple(cb.postac.pozycja())
        if q[2] != k["z"]:
            st["krok"] = None
            if pi.st is not None:
                pi.st = None
            self.log(f"Wpadnięcie: przejście z planu zadziałało, z{k['z']} -> z{q[2]} w {q}.")
            return True
        if wynik is False or pi.st is None:
            return self._krok_porazka(k, p, "przejście nieudane")
        if teraz - k["od"] > float(self._k("PIETRA_MAX_S", 150.0)):
            pi.st = None
            return self._krok_porazka(k, p, "limit czasu przejścia")
        return True

    def _krok_porazka(self, k, p, powod):
        st = self.st
        st["zle"].add(k["T"])
        st["krok"] = None
        if self.cb.pietra is not None:
            self.cb.pietra.st = None
        self.log(f"Wpadnięcie: {powod} przy {k['T'][:2]} (z{k['T'][2]}), szukam innego przejścia.")
        self._tele("wpadniecie_plan_porazka", pole=list(k["T"]), powod=powod)
        st["nast"] = self.cb.zegar() + 0.5
        return True

    # --- (c) alarm ---

    def _alarm(self, powod, p):
        cb = self.cb
        st = self.st
        st["alarm"] = True
        tresc = f"wpadłem z z{st['z0']} na z{p[2]} i nie umiem wrócić ({powod}); jestem w {tuple(p)}"
        self.log(f"Wpadnięcie: ALARM, {tresc}. Zatrzymuję bota (STOP).")
        self._tele("wpadniecie_alarm", powod=powod, poz=list(p), z0=st["z0"], czas_s=round(cb.zegar() - st["od"], 1))
        try:
            import powiadom  # noqa: PLC0415
            powiadom.powiadom("Bot: wpadł i nie wraca", tresc, "critical", "wpadniecie")
        except Exception:
            pass
        al = getattr(cb, "alarm", None)
        if callable(al):
            try:
                al(f"wpadnięcie: {tresc}")
            except Exception:
                pass
        plik = self.plik_stop or (None if os.environ.get("RETRONIC_TESTY") else bot.STOP)
        self.stop_zapisany = False
        if plik is not None:
            try:
                Path(plik).write_text(f"wpadniecie: {tresc}\n")
                self.stop_zapisany = True
                self.log(f"Wpadnięcie: zapisałem {plik} (zatrzymanie bota).")
            except OSError as e:
                self.log(f"Wpadnięcie: nie zapisałem STOP ({e})")
        cb.pauza(1.0, 2.0)
        return True

    # --- powrót ---

    def _powrot(self, p, teraz):
        cb = self.cb
        st = self.st
        self.st = None
        self.log(f"Wpadnięcie: wróciłem na z{st['z0']} w {p} po {teraz - st['od']:.0f} s.")
        self._tele("wpadniecie_wyjscie", poz=list(p), czas_s=round(teraz - st["od"], 1), z0=st["z0"], z1=st["z1"])
        if cb.pietra is not None:
            cb.pietra.st = None
        cb.pietra_porazki = 0
        try:
            if not cb._wypad_wroc_na_trase(p):
                cb._patrol_sync_idx(p)
        except bot.Zatrzymano:
            raise
        except Exception as e:
            self.log(f"Wpadnięcie: powrót na trasę nie wyszedł ({e!r})")
            try:
                cb._patrol_sync_idx(p)
            except Exception:
                pass
        cb.pauza(0.15, 0.35)
        return True
