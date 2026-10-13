#!/usr/bin/env python3
"""Obserwator ręcznej pomocy Karola (osobny proces, TYLKO ODCZYT, zero inputu do gry).

  python3 -I obserwator_reczny.py [--okres 0.7] [--postac NAZWA] [--katalog-logi DIR]

Próbkuje gniazdo $XDG_RUNTIME_DIR/retronic-pomocnik.sock (komendy `stwory` i `gracz`) co ~0,7 s i
czyta z dysku telemetrię bota (logi/telemetria-RRRRMMDD.jsonl, tylko ogon), proces mozg/cavebot oraz
pliki STOP / STOP_RECZNY. Działa także, gdy bot jest zatrzymany albo w ogóle nie działa.

Co wykrywa (tryb "bot_aktywny": porównanie zlecenia bota z tym, co się stało):
  zmiana_celu     gra atakuje inny stwór niż cel bota (dłużej niż 1 próbka, bez nowego celu bota)
  ruch_nie_zlecony  postać zmieniła pole, choć bot (stan, cel przy styku, pościg) tego nie zlecił
  stop_reczny     pojawił się plik STOP_RECZNY (Karol przejął)
  ruch_w_pauzie / aktywnosc_przy_zatrzymanym_bocie
Tryby "bot_zatrzymany", "bot_cichy" (proces jest, telemetria milczy), "brak_bota" = gra ręczna.

Zapis: logi/pomoc-karola.jsonl (jeden rekord na epizod), logi/pomoc-karola.md (podsumowanie po
polsku), logi/obserwator-reczny.log. Nie zapisuje treści czatu ani nazw innych graczy ani własnego
nicka (inni gracze to tylko licznik).
"""
import argparse
import json
import os
import re
import signal
import socket
import sys
import time
from collections import deque
from pathlib import Path

sys.dont_write_bytecode = True

KATALOG = Path(__file__).resolve().parent
sys.path.insert(0, str(KATALOG))
import instancja  # noqa: E402

STAN = instancja.S.stan          # STOP / STOP_RECZNY instancji (bez RETRONIC_ID = KATALOG)
LOGI = instancja.S.logi
GNIAZDO = instancja.gniazdo()

OKRES = 0.7
CISZA_BOT = 8.0          # s bez sygnału kończy epizod pomocy przy działającym bocie
CISZA_RECZNA = 15.0      # s bez aktywności kończy segment gry ręcznej
EPIZOD_MAX = 180.0       # s: dłuższy epizod jest dzielony
TELEMETRIA_STARA = 20.0  # s: starsza próbka telemetrii = bot "cichy"
STYK = 1                 # odległość Chebysheva uznawana za "stykający"
UCIEKINIER_HP = 30       # % HP moba uznawany za uciekiniera
ZASIEG_EKRANU = 8
WAGA_OTWARCIA = 2
SKOK_TELEPORT = 2        # skok większy niż tyle pól w jednej próbce = teleport, nie krok

STANY_RUCHU = {"IDZ", "POGON", "LOOT", "UCIECZKA"}      # bot sam chodzi
STANY_PAUZY = {"PAUZA", "PRZERWA"}
# co z "akcja.co" bota wolno przepisać (whitelist: nic z czatu, żadnych nicków)
AKCJA_OK = re.compile(r"^(Nowy cel|Odpuszczam|Pościg|Czekam|Loot|Zjedzono|Rat |Cel |Następne|Zmiana celu)")
AKCJA_ZLE = re.compile(r"Gracz|gracz")
ZDARZENIA_OK = ("nowy_cel", "poscig_start", "poscig_koniec", "odpuszczenie", "zabicie", "utkniecie", "loot")


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def godzina(t):
    return time.strftime("%H:%M:%S", time.localtime(t))


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t))


# ---------------------------------------------------------------------------------------------
# źródła danych
# ---------------------------------------------------------------------------------------------
def zapytaj(zadanie, gniazdo=GNIAZDO, limit=3.0):
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(limit)
        s.connect(str(gniazdo))
        s.sendall((json.dumps(zadanie) + "\n").encode())
        odp = json.loads(s.makefile("rb").readline())
    if not odp.get("ok", True):
        raise RuntimeError(str(odp.get("blad") or odp.get("error") or "błąd rdzenia"))
    return odp


class Gra:
    """Migawka gry z gniazda. Własną postać rozpoznaje po nicku (nick nigdy nie trafia do logów)."""

    def __init__(self, postac=None, katalog_logi=LOGI):
        self.postac = postac
        self.logi = Path(katalog_logi)

    def _nick_z_telemetrii(self):
        try:
            pliki = sorted(self.logi.glob("telemetria-*.jsonl"))
            if not pliki:
                return None
            with open(pliki[-1], "rb") as f:
                f.seek(0, 2)
                f.seek(max(0, f.tell() - 60000))
                for linia in reversed(f.read().decode("utf-8", "replace").splitlines()):
                    if '"probka"' not in linia:
                        continue
                    try:
                        r = json.loads(linia)
                    except ValueError:
                        continue
                    for w in r.get("stwory", []):
                        if w.get("gracz") and w.get("odl") == 0 and w.get("dx") == 0:
                            return w.get("n")
        except OSError:
            pass
        return None

    def migawka(self):
        st = zapytaj({"cmd": "stwory"})["stwory"]
        gr = zapytaj({"cmd": "gracz"})["gracz"]
        hp_proc = round(100.0 * gr["hp"] / gr["max_hp"]) if gr.get("max_hp") else None
        gracze = [s for s in st if s.get("gracz")]
        if not self.postac:
            self.postac = self._nick_z_telemetrii()
        ja = None
        if self.postac:
            ja = next((s for s in gracze if s["nazwa"] == self.postac), None)
        if ja is None and not self.postac:
            if len(gracze) == 1:
                ja = gracze[0]
            else:
                kand = [s for s in gracze if s.get("hp") == hp_proc]
                if len(kand) == 1:
                    ja = kand[0]
        if ja is None:
            raise RuntimeError("nie widzę własnej postaci")
        mobs = [{"id": s["id"], "nazwa": s["nazwa"], "x": s["x"], "y": s["y"], "z": s["z"],
                 "hp": s.get("hp", 100), "atakowany": bool(s.get("atakowany")),
                 "bije_nas": bool(s.get("bije_nas"))}
                for s in st if not s.get("gracz") and s.get("hp", 100) > 0 and s["z"] == ja["z"]]
        return {"poz": (ja["x"], ja["y"], ja["z"]), "hp_proc": hp_proc, "hp": gr["hp"],
                "max_hp": gr["max_hp"], "exp": gr.get("exp"), "cap": gr.get("cap"),
                "mana": gr.get("mana"), "mobs": mobs, "inni_gracze": len(gracze) - 1}


class Bot:
    """Stan bota z dysku: ogon telemetrii, proces, pliki STOP. Czytelnik tylko do odczytu."""

    def __init__(self, katalog=STAN, logi=LOGI, zegar=time.time):
        self.katalog = Path(katalog)
        self.logi = Path(logi)
        self.zegar = zegar
        self.plik = None
        self.offset = 0
        self.reszta = b""
        self.probka = None                 # ostatnia próbka telemetrii (dict)
        self.zdarzenia = deque(maxlen=200)  # {"t","typ",...}
        self.poscig = False
        self.t_poscig_koniec = -1e9
        self.proces = False
        self.t_proces = -1e9

    def _czytaj_telemetrie(self):
        dzien = time.strftime("%Y%m%d", time.localtime(self.zegar()))
        plik = self.logi / f"telemetria-{dzien}.jsonl"
        if not plik.exists():
            return
        try:
            rozm = plik.stat().st_size
            if plik != self.plik:
                self.plik, self.offset, self.reszta = plik, max(0, rozm - 40000), b""
            elif rozm < self.offset:
                self.offset, self.reszta = 0, b""
            if rozm == self.offset:
                return
            with open(plik, "rb") as f:
                f.seek(self.offset)
                dane = f.read(rozm - self.offset)
            self.offset += len(dane)
        except OSError:
            return
        dane = self.reszta + dane
        linie = dane.split(b"\n")
        self.reszta = linie.pop()            # niepełna ostatnia linia czeka na następny obieg
        for l in linie:
            try:
                r = json.loads(l)
            except ValueError:
                continue
            self.dodaj(r)

    def dodaj(self, r):
        """Jeden rekord telemetrii (publiczne: testy karmią tym syntetyczne dane)."""
        typ = r.get("typ")
        if typ == "probka":
            self.probka = r
            return
        if typ in ZDARZENIA_OK:
            self.zdarzenia.append(r)
        if typ == "poscig_start":
            self.poscig = True
        elif typ == "poscig_koniec":
            self.poscig = False
            self.t_poscig_koniec = r.get("t", 0)

    def _proces_bota(self):
        t = self.zegar()
        if t - self.t_proces < 3:
            return self.proces
        self.t_proces = t
        ok = False
        try:
            for p in os.listdir("/proc"):
                if not p.isdigit():
                    continue
                try:
                    with open(f"/proc/{p}/cmdline", "rb") as f:
                        c = f.read().replace(b"\0", b" ").decode("utf-8", "replace")
                except OSError:
                    continue
                if re.search(r"python3?\b.*\b(mozg|cavebot)\.py", c) and instancja.nalezy(int(p)):
                    ok = True
                    break
        except OSError:
            pass
        self.proces = ok
        return ok

    def stan(self, t=None):
        """Słownik opisujący bota w chwili t (obejmuje odczyt dysku)."""
        self._czytaj_telemetrie()
        t = self.zegar() if t is None else t
        p = self.probka
        wiek = (t - p["t"]) if p else None
        stop = (self.katalog / "STOP").exists()
        stop_r = (self.katalog / "STOP_RECZNY").exists()
        proces = self._proces_bota()
        return self.opisz(t, p, wiek, proces, stop, stop_r)

    def opisz(self, t, p, wiek, proces, stop, stop_r):
        if stop or stop_r:
            tryb = "zatrzymany"
        elif not proces:
            tryb = "brak"
        elif wiek is None or wiek > TELEMETRIA_STARA:
            tryb = "cichy"
        else:
            tryb = "aktywny"
        cel = (p or {}).get("cel") if tryb == "aktywny" else None
        akcja = None
        if p and p.get("akcja") and tryb == "aktywny":
            co = p["akcja"].get("co", "")
            if AKCJA_OK.search(co) and not AKCJA_ZLE.search(co):
                akcja = co[:90]
        return {"tryb": tryb, "stan": (p or {}).get("stan") if tryb in ("aktywny", "cichy") else None,
                "cel": cel, "akcja": akcja, "stop": stop, "stop_reczny": stop_r,
                "poscig": self.poscig or (t - self.t_poscig_koniec) < 3.0,
                "wiek_probki": wiek,
                "zdarzenia": [z for z in self.zdarzenia if t - z.get("t", 0) < 15]}


# ---------------------------------------------------------------------------------------------
# logika wykrywania i epizodów (czysta, testowalna na syntetycznych danych)
# ---------------------------------------------------------------------------------------------
def opis_zdarzenia(z):
    typ = z.get("typ")
    if typ == "nowy_cel":
        return f"nowy cel {z.get('n')} (hp {z.get('hp')}%)"
    if typ == "poscig_start":
        return f"pościg za {z.get('cel')} (hp {z.get('hp_celu')}%, odl {z.get('odl')})"
    if typ == "odpuszczenie":
        return f"odpuścił {z.get('n') or z.get('cel') or ''}: {str(z.get('powod', ''))[:50]}".strip()
    if typ == "zabicie":
        return f"zabił {z.get('n')}"
    if typ == "utkniecie":
        return "utknął"
    return typ


class Epizod:
    def __init__(self, t, tryb, migawka, bot, powod):
        self.t0 = t
        self.t_ost = t              # ostatnia aktywność/sygnał
        self.tryb = tryb
        self.powody = []
        self.waga = 0
        self.poz0 = migawka["poz"]
        self.poz = migawka["poz"]
        self.hp0 = self.hp_min = self.hp1 = migawka["hp_proc"]
        self.exp0 = migawka.get("exp")
        self.exp1 = migawka.get("exp")
        self.cap_ost = migawka.get("cap")
        self.moby0 = self.licz(migawka)
        self.moby_max = self.moby0["zywe"]
        self.styk_max = self.moby0["stykaja"]
        self.t_styk3 = 0.0
        self.odl_min = self.moby0["najblizszy"]
        self.cele = []              # kolejność atakowanych celów
        self.kroki = 0
        self.kroki_od = 0
        self.pola_od = 0            # pola oddalenia od skupiska
        self.ucieczka = False
        self.jadl = False
        self.bot0 = {"tryb": bot["tryb"], "stan": bot["stan"], "cel": self._cel(bot),
                     "akcja": bot["akcja"],
                     "zdarzenia": [opis_zdarzenia(z) for z in bot["zdarzenia"][-4:]]}
        self.bot_cel_zmiany = []    # co bot sam wybrał w trakcie
        self.zmiany_celu = []       # {"z","na",...}
        self.sygnaly = {}
        self.t_ost_probka = t
        self.koniec_moby = self.moby0
        self.bot_stan_koniec = bot["stan"]
        if powod:
            self.dodaj_powod(powod, 0)

    @staticmethod
    def _cel(bot):
        c = bot.get("cel")
        if not c:
            return None
        return {"id": c.get("id"), "nazwa": c.get("nazwa"), "hp": c.get("hp"), "odl": c.get("odl")}

    @staticmethod
    def licz(m):
        pz = m["poz"]
        zyw = [s for s in m["mobs"] if cheb(pz, (s["x"], s["y"])) <= ZASIEG_EKRANU]
        odl = [cheb(pz, (s["x"], s["y"])) for s in zyw]
        return {"zywe": len(zyw), "stykaja": sum(1 for o in odl if o <= STYK),
                "najblizszy": min(odl) if odl else None}

    def dodaj_powod(self, p, waga):
        if p not in self.powody:
            self.powody.append(p)
        self.waga += waga


class Obserwator:
    """Karmiony próbkami (t, migawka, stan bota); zwraca zamknięte epizody przez .gotowe."""

    def __init__(self):
        self.ep = None
        self.gotowe = []          # zamknięte epizody (rekord, podsumowanie)
        self.zdarzenia = []       # krótkie zdarzenia (stop_reczny itd.)
        self.prev = None          # poprzednia migawka
        self.prev_t = None
        self.prev_bot = None
        self.niezgodne = 0        # kolejne próbki z innym celem niż bot
        self.niezlecone = deque() # czasy ruchów nie zleconych
        self.t_nowy_cel_bota = -1e9
        self.bot_cel_id = None
        self.t_zmiany_tr = -1e9
        self.hist = deque(maxlen=12)   # (t, migawka, bot) ostatnich próbek, do cofnięcia początku epizodu
        self.t_pierwszy_sygnal = None
        self.sygnal_waga = 0.0

    # --- pomocnicze ---
    def _zrodlo_ruchu(self, poprz, mig, bot):
        """Czy bot mógł zlecić ruch poprz->mig? Zwraca (zlecony, powod_jesli_nie)."""
        tryb, stan = bot["tryb"], bot["stan"]
        if tryb == "zatrzymany" or tryb == "brak":
            return False, "ruch_przy_zatrzymanym_bocie" if tryb == "zatrzymany" else "gra_reczna"
        if tryb == "cichy":
            return False, "ruch_bez_telemetrii_bota"
        if stan in STANY_PAUZY:
            return False, "ruch_w_pauzie"
        if stan in STANY_RUCHU or bot["poscig"]:
            return True, None
        if stan == "WALKA":
            cel = bot.get("cel")
            if cel:
                prev_cel = next((s for s in poprz["mobs"] if s["id"] == cel.get("id")), None)
                if prev_cel is not None:
                    tcel = (prev_cel["x"], prev_cel["y"])
                    d0, d1 = cheb(poprz["poz"], tcel), cheb(mig["poz"], tcel)
                    if d0 <= STYK or d1 > d0:        # krok przy styku albo oddalający się od celu
                        return False, "ruch_nie_zlecony"
                return True, None            # dochodzenie do celu
            return True, None                # brak celu: bot wybiera, nie ma jak ocenić
        return True, None                    # JEDZENIE/GRACZ/MOZG/POCHODNIA: nie oceniamy

    def _otworz(self, t, mig, bot, powod, waga):
        tryb = {"aktywny": "bot_aktywny", "zatrzymany": "bot_zatrzymany",
                "cichy": "bot_cichy", "brak": "brak_bota"}[bot["tryb"]]
        self.ep = Epizod(self.prev_t or t, tryb, self.prev or mig, bot, None)
        self.ep.dodaj_powod(powod, waga)
        self.ep.t_ost = t

    def _zamknij(self, t, powod_konca):
        ep = self.ep
        self.ep = None
        if ep is None:
            return
        dlug = ep.t_ost - ep.t0
        ruszal = cheb(ep.poz0, ep.poz) + ep.kroki
        gra_reczna = ep.tryb != "bot_aktywny"
        if gra_reczna and dlug < 3 and not ep.cele and ruszal < 2:
            return
        if not gra_reczna and ep.waga < WAGA_OTWARCIA:
            return
        rec = zbuduj_rekord(ep, ep.t_ost, powod_konca)
        self.gotowe.append((rec, podsumowanie(rec)))

    # --- główne wejście ---
    def probka(self, t, mig, bot):
        prev, prev_bot = self.prev, self.prev_bot
        tryb_bot = bot["tryb"]
        # zmiana trybu zamyka epizod
        if self.ep and prev_bot and prev_bot["tryb"] != tryb_bot:
            self._zamknij(t, "zmiana_trybu")
        sygnaly = []   # (nazwa, waga)

        # STOP_RECZNY: przejęcie
        if bot["stop_reczny"] and not (prev_bot and prev_bot["stop_reczny"]):
            sygnaly.append(("stop_reczny", 3))
            self.zdarzenia.append({"t": t, "zdarzenie": "stop_reczny_pojawil_sie"})
        if prev_bot and prev_bot["stop_reczny"] and not bot["stop_reczny"]:
            self.zdarzenia.append({"t": t, "zdarzenie": "stop_reczny_zniknal"})

        aktywnosc = False
        atak = next((s for s in mig["mobs"] if s["atakowany"]), None)
        if prev is not None and mig["poz"][2] == prev["poz"][2]:
            d = cheb(mig["poz"], prev["poz"])
            if d > SKOK_TELEPORT:
                d = 0
            if d > 0:
                aktywnosc = True
                zlecony, powod = self._zrodlo_ruchu(prev, mig, bot)
                if not zlecony:
                    if powod == "ruch_nie_zlecony":
                        self.niezlecone.append(t)
                        while self.niezlecone and t - self.niezlecone[0] > 5:
                            self.niezlecone.popleft()
                        sygnaly.append((powod, 2 if len(self.niezlecone) >= 2 else 1))
                    elif powod == "ruch_w_pauzie":
                        sygnaly.append((powod, 2))
                    else:
                        sygnaly.append((powod, 2 if tryb_bot == "zatrzymany" else 0))
        if atak is not None:
            aktywnosc = True
        if prev and mig.get("exp") is not None and prev.get("exp") is not None and mig["exp"] > prev["exp"]:
            aktywnosc = True

        # zmiana celu: gra atakuje inny stwór niż cel bota
        if tryb_bot == "aktywny":
            bid = (bot.get("cel") or {}).get("id")
            if bid != self.bot_cel_id:
                self.t_nowy_cel_bota = t
                self.bot_cel_id = bid
            nowy_cel_bota_swiezo = (t - self.t_nowy_cel_bota) < 2.0
            if atak is not None and bid is not None and atak["id"] != bid and not nowy_cel_bota_swiezo:
                self.niezgodne += 1
                sygnaly.append(("zmiana_celu", 2 if self.niezgodne >= 2 else 1))
            else:
                self.niezgodne = 0
        else:
            self.niezgodne = 0
            self.bot_cel_id = None

        # gra ręczna / bot zatrzymany: aktywność sama jest powodem
        if tryb_bot in ("brak", "cichy", "zatrzymany") and aktywnosc:
            nazwa = {"brak": "gra_reczna", "cichy": "gra_reczna_bot_cichy",
                     "zatrzymany": "aktywnosc_przy_zatrzymanym_bocie"}[tryb_bot]
            sygnaly.append((nazwa, 2))

        waga = sum(w for _, w in sygnaly)
        # otwieranie epizodu
        if self.ep is None:
            if waga > 0 and self.t_pierwszy_sygnal is None:
                self.t_pierwszy_sygnal = t
            elif waga == 0 and self.t_pierwszy_sygnal is not None and t - self.t_pierwszy_sygnal > 5:
                self.t_pierwszy_sygnal = None
            if waga >= WAGA_OTWARCIA:
                t_sig = self.t_pierwszy_sygnal if self.t_pierwszy_sygnal is not None else t
                powtorka = [h for h in self.hist if h[0] >= t_sig]
                przed = [h for h in self.hist if h[0] < t_sig]
                if przed:
                    self.prev_t, self.prev, self.prev_bot = przed[-1]
                else:
                    powtorka = []
                self._otworz(t, mig, bot, sygnaly[0][0] if sygnaly else "?", 0)
                for n, w in sygnaly:
                    self.ep.dodaj_powod(n, w)
                self.t_pierwszy_sygnal = None
                pp, pb = self.prev, self.prev_bot
                for (ht, hm, hb) in powtorka:
                    self._aktualizuj(ht, hm, hb, pp, [], True, 1)
                    pp = hm
        elif self.ep is not None:
            for n, w in sygnaly:
                if w > 0:
                    self.ep.dodaj_powod(n, w)
        if self.ep is not None:
            self._aktualizuj(t, mig, bot, prev, sygnaly, aktywnosc, waga)
            cisza = CISZA_BOT if self.ep.tryb == "bot_aktywny" else CISZA_RECZNA
            if t - self.ep.t_ost > cisza:
                self._zamknij(t, "cisza")
            elif t - self.ep.t0 > EPIZOD_MAX:
                self._zamknij(t, "podzial_dlugi")
        self.prev, self.prev_t, self.prev_bot = mig, t, bot
        self.hist.append((t, mig, bot))

    def _aktualizuj(self, t, mig, bot, prev, sygnaly, aktywnosc, waga):
        ep = self.ep
        if waga > 0 or (aktywnosc and ep.tryb != "bot_aktywny"):
            ep.t_ost = t
        dt = t - ep.t_ost_probka
        ep.t_ost_probka = t
        ep.poz = mig["poz"]
        ep.exp1 = mig.get("exp", ep.exp1)
        if mig["hp_proc"] is not None:
            ep.hp1 = mig["hp_proc"]
            ep.hp_min = mig["hp_proc"] if ep.hp_min is None else min(ep.hp_min, mig["hp_proc"])
        l = Epizod.licz(mig)
        ep.moby_max = max(ep.moby_max, l["zywe"])
        ep.styk_max = max(ep.styk_max, l["stykaja"])
        if l["najblizszy"] is not None:
            ep.odl_min = l["najblizszy"] if ep.odl_min is None else min(ep.odl_min, l["najblizszy"])
        if l["stykaja"] >= 3:
            ep.t_styk3 += dt
        ep.koniec_moby = l
        # kroki i cofanie względem skupiska żywych w promieniu 6
        if prev is not None and mig["poz"] != prev["poz"] and mig["poz"][2] == prev["poz"][2] \
                and cheb(mig["poz"], prev["poz"]) <= SKOK_TELEPORT:
            ep.kroki += 1
            bliskie = [s for s in prev["mobs"] if cheb(prev["poz"], (s["x"], s["y"])) <= 6]
            if bliskie:
                cx = sum(s["x"] for s in bliskie) / len(bliskie)
                cy = sum(s["y"] for s in bliskie) / len(bliskie)
                d0 = max(abs(prev["poz"][0] - cx), abs(prev["poz"][1] - cy))
                d1 = max(abs(mig["poz"][0] - cx), abs(mig["poz"][1] - cy))
                if d1 > d0:
                    ep.kroki_od += 1
                    ep.pola_od += 1
                    if (mig["hp_proc"] is not None and mig["hp_proc"] < 40) or l["stykaja"] >= 3 \
                            or any(s["bije_nas"] for s in bliskie):
                        ep.ucieczka = ep.ucieczka or ep.kroki_od >= 3
        # jedzenie: skok capa w górę przy braku loot (cap rośnie tylko gdy coś znika z plecaka)
        if prev is not None and mig.get("cap") is not None and prev.get("cap") is not None:
            if 0 < mig["cap"] - prev["cap"] <= 20 and bot["stan"] != "LOOT":
                ep.jadl = True
        # atakowany cel
        atak = next((s for s in mig["mobs"] if s["atakowany"]), None)
        if atak is not None:
            if not ep.cele or ep.cele[-1]["id"] != atak["id"]:
                zyw = [s for s in mig["mobs"] if cheb(mig["poz"], (s["x"], s["y"])) <= ZASIEG_EKRANU]
                styk = [s for s in zyw if cheb(mig["poz"], (s["x"], s["y"])) <= STYK]
                odl = cheb(mig["poz"], (atak["x"], atak["y"]))
                slab = min(styk, key=lambda s: s["hp"]) if styk else None
                nowy = {"id": atak["id"], "nazwa": atak["nazwa"], "hp_start": atak["hp"],
                        "hp_koniec": atak["hp"], "odl": odl, "stykajacy": odl <= STYK,
                        "uciekinier": atak["hp"] <= UCIEKINIER_HP and odl > STYK,
                        "najslabszy_stykajacy": bool(slab and slab["id"] == atak["id"]),
                        "stykajacych_wtedy": len(styk), "t": round(t - ep.t0, 1),
                        "bot_cel": (bot.get("cel") or {}).get("id"),
                        "zgodny_z_botem": (bot.get("cel") or {}).get("id") == atak["id"]}
                if ep.cele:
                    nowy["z"] = {"nazwa": ep.cele[-1]["nazwa"], "hp": ep.cele[-1]["hp_koniec"],
                                 "uciekinier": ep.cele[-1]["uciekinier"],
                                 "stykajacy": ep.cele[-1]["stykajacy"]}
                    ep.zmiany_celu.append(nowy)
                ep.cele.append(nowy)
            else:
                ep.cele[-1]["hp_koniec"] = atak["hp"]
        if bot.get("cel") and bot["tryb"] == "aktywny":
            bc = bot["cel"]
            if not ep.bot_cel_zmiany or ep.bot_cel_zmiany[-1].get("id") != bc.get("id"):
                if len(ep.bot_cel_zmiany) < 6:
                    ep.bot_cel_zmiany.append({"id": bc.get("id"), "nazwa": bc.get("nazwa"), "hp": bc.get("hp")})
        ep.bot_stan_koniec = bot["stan"]


def zbuduj_rekord(ep, t_koniec, powod_konca):
    dlug = round(t_koniec - ep.t0, 1)
    exp = None
    if ep.exp0 is not None and ep.exp1 is not None:
        exp = ep.exp1 - ep.exp0
    k = getattr(ep, "koniec_moby", ep.moby0)
    dlug_cel = [{kk: v for kk, v in c.items() if kk not in ("id",)} for c in ep.cele]
    return {
        "start": iso(ep.t0), "koniec": iso(t_koniec), "t_start": round(ep.t0, 1), "t_koniec": round(t_koniec, 1),
        "czas_s": dlug, "tryb": ep.tryb, "powod": ep.powody, "waga": ep.waga,
        "powod_konca": powod_konca,
        "poz_start": list(ep.poz0), "poz_koniec": list(ep.poz),
        "przeszedl_pol": ep.kroki,
        "moby": {"zywe_start": ep.moby0["zywe"], "zywe_max": ep.moby_max, "zywe_koniec": k["zywe"],
                 "najblizszy_start": ep.moby0["najblizszy"], "najblizszy_min": ep.odl_min,
                 "stykajace_start": ep.moby0["stykaja"], "stykajace_max": ep.styk_max,
                 "stykajace_koniec": k["stykaja"], "s_przy_3_stykajacych": round(ep.t_styk3, 1)},
        "hp": {"start": ep.hp0, "min": ep.hp_min, "koniec": ep.hp1},
        "exp_przyrost": exp,
        "cele": dlug_cel,
        "zmian_celu": len(ep.zmiany_celu),
        "cofal_sie": ep.pola_od >= 2, "cofniecie_pol": ep.pola_od, "uciekal": ep.ucieczka,
        "jadl": ep.jadl,
        "bot": {"przed": ep.bot0, "cel_bota_w_trakcie": ep.bot_cel_zmiany,
                "stan_na_koniec": getattr(ep, "bot_stan_koniec", None)},
    }


def opis_moba(c):
    return f"{c['nazwa']} {c['hp_start'] if 'hp_start' in c else c.get('hp')}%"


def podsumowanie(r):
    """Krótkie czytelne zdania po polsku: co Karol zrobił inaczej niż bot."""
    z = []
    tryb = r["tryb"]
    start = r["start"][11:]
    koniec = r["koniec"][11:]
    nag = {"bot_aktywny": "Karol pomaga botowi", "bot_zatrzymany": "Karol gra przy zatrzymanym bocie",
           "bot_cichy": "Karol gra (bot bez telemetrii)", "brak_bota": "Gra ręczna (bota nie ma)"}[tryb]
    hp = r["hp"]
    hp_txt = f"HP {hp['start']}%" + (f" (min {hp['min']}%)" if hp["min"] != hp["start"] else "") + f" -> {hp['koniec']}%"
    m = r["moby"]
    z.append(f"{start}-{koniec} ({r['czas_s']:.0f} s) {nag}; powód: {', '.join(r['powod'])}; {hp_txt}; "
             f"exp {r['exp_przyrost'] if r['exp_przyrost'] is not None else '?'}; "
             f"żywych {m['zywe_start']}->maks {m['zywe_max']}, stykających maks {m['stykajace_max']}.")
    zm = []
    cele = r["cele"]
    for c in cele:
        if "z" not in c:
            continue
        a, b = c["z"], c
        opis = f"zmienił cel z {a['nazwa']} {a['hp']}%{' (uciekinier)' if a.get('uciekinier') else ''} " \
               f"na {b['nazwa']} {b['hp_start']}%"
        det = []
        if b["najslabszy_stykajacy"] and b["stykajacy"]:
            det.append("najsłabszego stykającego")
        elif b["stykajacy"]:
            det.append("stykającego")
        if b.get("uciekinier"):
            det.append("uciekiniera")
        if det:
            opis += " (" + ", ".join(det) + ")"
        if b.get("stykajacych_wtedy", 0) >= 3:
            opis += f", przy {b['stykajacych_wtedy']} stykających"
        if not b.get("zgodny_z_botem") and b.get("bot_cel") is not None:
            opis += ", bot celował w innego"
        zm.append(opis)
    for s in zm[:4]:
        z.append("- " + s + ".")
    if cele and "z" not in cele[0] and tryb == "bot_aktywny" and cele[0].get("bot_cel") not in (None, ) \
            and not cele[0].get("zgodny_z_botem"):
        c = cele[0]
        z.append(f"- zaatakował {c['nazwa']} {c['hp_start']}% zamiast celu bota"
                 f"{' (dobił uciekiniera)' if c.get('uciekinier') else ''}.")
    elif cele and tryb == "bot_aktywny" and cele[0].get("uciekinier") and cele[0].get("bot_cel") is None:
        z.append(f"- dobił uciekiniera ({cele[0]['nazwa']} {cele[0]['hp_start']}%) zamiast ruszyć dalej.")
    if r["cofal_sie"]:
        z.append(f"- {'uciekał' if r['uciekal'] else 'cofnął się'} o {r['cofniecie_pol']} pól od skupiska "
                 f"(bot tego nie robi).")
    if r["jadl"]:
        z.append("- prawdopodobnie jadł (cap wzrósł bez lootu).")
    if "stop_reczny" in r["powod"]:
        z.append("- zatrzymał bota (STOP_RECZNY).")
    if tryb == "bot_aktywny" and "ruch_nie_zlecony" in r["powod"] and r["przeszedl_pol"] and not r["cofal_sie"]:
        z.append(f"- zmienił pozycję o {r['przeszedl_pol']} kroków, choć bot stał przy celu.")
    if tryb != "bot_aktywny" and r["przeszedl_pol"]:
        z.append(f"- przeszedł {r['przeszedl_pol']} pól, zabił ok. {max(0, (r['exp_przyrost'] or 0)) // 5} (wg exp).")
    b = r["bot"]["przed"]
    if b.get("cel") or b.get("stan"):
        c = b.get("cel")
        z.append(f"- bot przed tym: stan {b.get('stan')}"
                 + (f", cel {c['nazwa']} {c['hp']}% (odl {c['odl']})" if c else "")
                 + (f", ostatnio: {b['zdarzenia'][-1]}" if b.get("zdarzenia") else "") + ".")
    return "\n".join(z)


# ---------------------------------------------------------------------------------------------
# zapis i pętla
# ---------------------------------------------------------------------------------------------
class Zapis:
    def __init__(self, logi=LOGI):
        self.logi = Path(logi)
        self.jsonl = self.logi / "pomoc-karola.jsonl"
        self.md = self.logi / "pomoc-karola.md"

    def epizod(self, rec, tekst):
        self.logi.mkdir(exist_ok=True)
        with open(self.jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        nowy = not self.md.exists()
        with open(self.md, "a", encoding="utf-8") as f:
            if nowy:
                f.write("# Pomoc Karola: co zrobił inaczej niż bot\n\n")
            f.write(f"## {rec['start'][:10]} {tekst.splitlines()[0]}\n" + "\n".join(tekst.splitlines()[1:]) + "\n\n")

    def zdarzenie(self, z):
        self.logi.mkdir(exist_ok=True)
        z = {**z, "typ": "zdarzenie", "czas": iso(z["t"])}
        with open(self.jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(z, ensure_ascii=False) + "\n")


def log(tekst):
    print(f"{time.strftime('%H:%M:%S')} {tekst}", flush=True)


def petla(okres=OKRES, postac=None, logi=LOGI, katalog=STAN, ile=None):
    gra = Gra(postac, logi)
    bot = Bot(katalog, logi)
    obs = Obserwator()
    zapis = Zapis(logi)
    stop = {"v": False}
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.__setitem__("v", True))
    log(f"start; gniazdo {GNIAZDO}; okres {okres} s")
    n = 0
    blad_ost = None
    while not stop["v"]:
        t0 = time.time()
        try:
            mig = gra.migawka()
            st = bot.stan(t0)
            obs.probka(t0, mig, st)
            blad_ost = None
        except (OSError, RuntimeError, ValueError, KeyError) as e:
            if obs.ep is not None:
                obs._zamknij(t0, "brak_gry")
            obs.prev = None
            msg = f"{type(e).__name__}: {str(e)[:80]}"
            if msg != blad_ost:
                log(f"brak odczytu: {msg}")
                blad_ost = msg
        while obs.gotowe:
            rec, tekst = obs.gotowe.pop(0)
            zapis.epizod(rec, tekst)
            log("epizod: " + tekst.splitlines()[0])
        while obs.zdarzenia:
            zapis.zdarzenie(obs.zdarzenia.pop(0))
        n += 1
        if ile is not None and n >= ile:
            break
        time.sleep(max(0.05, okres - (time.time() - t0)))
    if obs.ep is not None:
        obs._zamknij(time.time(), "koniec_obserwatora")
        while obs.gotowe:
            rec, tekst = obs.gotowe.pop(0)
            zapis.epizod(rec, tekst)
    log("koniec")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--okres", type=float, default=OKRES)
    ap.add_argument("--postac", default=None, help="nick własnej postaci (domyślnie auto z telemetrii)")
    ap.add_argument("--katalog-logi", default=str(LOGI))
    a = ap.parse_args()
    petla(max(0.3, min(2.0, a.okres)), a.postac, Path(a.katalog_logi))


if __name__ == "__main__":
    main()
