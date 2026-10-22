"""Telemetria bota: 1 rekord/s do logi/telemetria-RRRRMMDD.jsonl + zdarzenia (zabicie, odpuszczenie,
loot, utknięcie), agregaty i wykrywanie anomalii (czysty Python, bez modelu). Tylko stdlib.

Rekordy: {"t": czas epoch, "typ": "probka"|<zdarzenie>, ...}. Tym samym rekordom służy analityk.py."""
import json
import math
import os
import re
import sys
import time
from collections import deque, Counter
from pathlib import Path

import ekonomia
import instancja
import ostatnie

LOGI = instancja.S.logi      # bez RETRONIC_ID: pomocnik/logi
MAX_BAJTOW = 20 * 1024 * 1024      # plik dnia ponad tyle: rotacja do .1 (stary .1 znika)
DNI = 4                            # tyle dni plików zostaje
PAMIEC_S = 3600                    # tyle sekund rekordów trzymamy w pamięci do agregacji
STWORY_MAX = 8                     # maks. potworów w próbce
ASTAR_MAX = 3                      # A* (droga) tylko dla tylu najbliższych potworów (reszta bez drogi)
ASTAR_CO = 2.0                     # s: droga liczona nie częściej; między tym bierzemy ostatnią znaną
BLISKO_LOOT = 5                    # żywy cel tak blisko przy starcie lootu = anomalia
UTKNIECIE_S = 15                   # stoi w IDZ/WALKA bez ruchu tyle sekund = utknięcie
STANY_POSTOJU = ("PRZERWA", "PAUZA", "JEDZENIE", "LOOT", "GRACZ", "UCIECZKA")
RUCH_OKNO_S = 30.0                 # R0b: co tyle sekund rekord ruch_okno
RUCH_LUKA_S = 1.5                  # R0b: odstęp między obiegami tyle lub dłuższy = luka ticka
RUCH_DT_MAX = 30.0                 # R0b: do czasu marszu/stania liczymy najwyżej tyle z jednego odstępu (pauza bota to luka)
RUCH_SKOK_MAX = 8                  # R0b: przesunięcie większe (Czebyszew) = teleport/wypad, nie liczymy pól
NAZWY_TESTOWE = ("Ja",)            # R0a: postać atrapy z testów i skryptów pomocniczych, jej telemetrii nie zapisujemy

RE_CEL = re.compile(r"Nowy cel: (.+?) \((\d+),(\d+)\) HP (\d+)%")
RE_ODP = re.compile(r"Odpuszczam (.+?)(?: poza ekranem)?: (.*)")
RE_ZAB = re.compile(r"Cel (.+?) zabity na")
# 13.10 (P4): tylko prawdziwy wynik lootu (status z loot.py, log(f"Loot: {wynik}") w cavebot._loot_...);
# "Loot: 4 pola puste", "Loot: stoję na zwłokach" itd. to komunikaty pośrednie, nie wynik
RE_LOOT = re.compile(r"^Loot: (ok|brak_okna|okno_niewidoczne|daleko|brak_plecaka|pelny_plecak|przerwany)$")
RE_LOOT_WSTRZYMANY = re.compile(r"^Loot: zwłoki \((-?\d+), (-?\d+)\) bez okna \((\d+)x\)")
RE_STAN = re.compile(r"^\[(\w+)\]")
RE_ZMIANA = re.compile(r"Zmiana celu: (.+?) stoi obok, (.+?) jest")
RE_ZGUB = re.compile(r"Cel (.+?) (?:wyszedł z widoku|zniknął poza ekranem)")
# zdarzenia lootu w walce (cavebot._loot_w_walce): krok (krok, poz, kroki, czas, hp) i przerwanie (powod, poz, kroki, czas)
LOOT_W_WALCE_TYPY = ("loot_w_walce_krok", "loot_w_walce_przerwany")
EP_MAX = 5000                      # tyle epizodów/zdarzeń exp trzymamy w pamięci na sesję
PROG_30 = 30                       # HP% celu, od którego liczymy "dobijanie"
EXP_PRZED_S = 1.5                  # exp sprzed zabicia: ostatni odczyt starszy o tyle (exp bywa przed logiem)
EXP_CZEKAJ_S = 6                   # tyle sekund czekamy na wzrost exp po zabiciu


_BLOKADY = {}                      # katalog -> otwarty deskryptor blokady zapisu (trzymany przez życie procesu)


def _zapis_wlaczony():
    """13.10 (P4): zapis do prawdziwego pliku tylko na żywo: RETRONIC_TELEMETRIA=1 i bez RETRONIC_TESTY.
    14.10 (R0a): dodatkowo tylko proces mozg.py (skrypty pomocnicze i testy uruchamiane jako inny plik nie piszą)."""
    return (os.environ.get("RETRONIC_TELEMETRIA") == "1" and not os.environ.get("RETRONIC_TESTY")
            and _src() == "mozg")


def _src():
    if os.environ.get("RETRONIC_TESTY"):
        return "test"
    nazwa = os.path.basename(sys.argv[0]) if sys.argv and sys.argv[0] else ""
    return "mozg" if nazwa.startswith("mozg") else "cavebot"


class Telemetria:
    def __init__(self, katalog=LOGI, zegar=time.time, max_bajtow=MAX_BAJTOW, zapis=None):
        """zapis=None: decyduje środowisko (_zapis_wlaczony) i blokada pisarza (jeden proces na katalog);
        True/False: jawnie (testy, analityk), bez blokady."""
        self.katalog = Path(katalog)
        self.zegar = zegar
        self.max_bajtow = max_bajtow
        self._blokada = zapis is None          # zapis z domyślnych: wymaga flock na katalog/telemetria.lock
        self.zapis = _zapis_wlaczony() if zapis is None else bool(zapis)
        self.pid = os.getpid()
        self.sesja = round(time.time(), 1)     # czas startu procesu (obiektu): odróżnia pisarzy w jednym pliku
        self.src = _src()
        self.nazwa_postaci = None        # R0a: ustawia Cavebot; nazwa z NAZWY_TESTOWE blokuje zapis na dysk
        self._ruch = None                # R0b: stan okna ruchu (patrz ruch_tick)
        if self.zapis and self._blokada:
            self._zajmij_blokade()
        # F1 Przegląd: ostatnio znane dane postaci (instancje/<id>/ostatnie.json); tylko dla prawdziwego katalogu logi/ i zapisu na żywo
        self.ostatnie = ostatnie.Pisarz(self.katalog.parent) if self.zapis and self.katalog.name == "logi" else None
        self.rek = deque()               # rekordy z ostatniej godziny
        self.ostatnia_probka = float("-inf")
        self.cel_start = None
        self.cel_pierwszy_pogon = None
        self.loot_start = None
        self.ostatni_stan = None
        self.stoi_od = None              # (pozycja, od kiedy)
        self.utknieto = False
        self.akcja = None                # ostatnia akcja: (czas, nazwa, wynik)
        self.pola_loot = {}
        self.astar_ost = float("-inf")   # kiedy ostatnio liczyliśmy drogi
        self.astar_cache = {}            # id stwora -> (osiagalny, droga)
        self.ep = None                   # otwarty epizod celu (patrz _ep_*)
        self.nast_decyzja = None         # 15.10: id decyzji D1 dla najbliższej linii "Nowy cel" (ustawia Cavebot tuż przed logiem)
        self.exp_hist = deque(maxlen=30)  # (t, exp) z próbek
        self.exp_czeka = None            # {"t","exp0","n":[nazwy]} zabicia czekające na przyrost exp
        self.sesja_ep = []               # epizody_celu od startu procesu
        self.sesja_exp = []              # exp_zabicie od startu procesu
        self.puszczenia_sesja = {}       # 11.10: powód puszczenia klawisza w pościgu -> licznik od startu procesu
        self.pierwszy_krok_sesja = deque(maxlen=200)  # 11.10: t_pierwszy_krok z poscig_koniec (do mediany w analizie)
        # dziennik ekonomii (SPEC_ekonomia_lootu_1017): osobny plik, bez rotacji i sprzątania
        self.lup = ekonomia.Lup()
        self.ost_zabicie = None          # (nazwa, czas) ostatniego zabicia: przypisanie lupu do potwora
        self.ekon_tik_ost = float("-inf")
        self.ekon_razem = {"gold": 0, "uh": 0, "zab": 0}
        self.ekon_start = False

    # --- zapis ---
    def _zajmij_blokade(self):
        """flock(LOCK_EX|LOCK_NB) na katalog/telemetria.lock, trzymany do końca procesu. Zajęty przez inny proces:
        zapis=False i jedna linia na stdout (bez log(), żeby nie wchodzić w HAKI_LOGU)."""
        k = str(self.katalog)
        if k in _BLOKADY:
            return                              # ten proces już pisze do tego katalogu (drugi obiekt)
        try:
            import fcntl  # noqa: PLC0415
            self.katalog.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.katalog / "telemetria.lock", os.O_RDWR | os.O_CREAT, 0o644)
        except (OSError, ImportError) as e:
            print(f"telemetria: brak blokady ({e!r}), nie zapisuję", flush=True)
            self.zapis = False
            return
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            try:
                kto = os.read(fd, 32).decode(errors="replace").strip() or "?"
            except OSError:
                kto = "?"
            os.close(fd)
            print(f"telemetria: inny proces pisze (pid {kto}), nie zapisuję", flush=True)
            self.zapis = False
            return
        try:
            os.ftruncate(fd, 0)
            os.write(fd, str(self.pid).encode())
        except OSError:
            pass
        _BLOKADY[k] = fd
        print(f"telemetria: zapis (pid {self.pid}, src {self.src})", flush=True)

    def _plik(self, t):
        return self.katalog / f"telemetria-{time.strftime('%Y%m%d', time.localtime(t))}.jsonl"

    def _plik_ekon(self, t):
        return self.katalog / f"ekonomia-{time.strftime('%Y%m%d', time.localtime(t))}.jsonl"

    def _ekon(self, typ, t=None, **d):
        """Rekord dziennika ekonomii: te same bezpieczniki co telemetria (zapis, blokada, atrapa), ale bez rotacji
        i bez sprzątania starych plików. Błąd zapisu nigdy nie psuje bota."""
        if not self.zapis or self._postac_testowa():
            return
        t = self.zegar() if t is None else t
        try:
            if not self.ekon_start:
                self.ekon_start = True
                self._ekon("start", t=t, v=ekonomia.WERSJA, postac=self.nazwa_postaci)
            r = {"t": round(t, 1), "typ": typ, **d, "pid": self.pid, "sesja": self.sesja, "src": self.src}
            self.katalog.mkdir(parents=True, exist_ok=True)
            with self._plik_ekon(t).open("a") as f:
                f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
        except OSError:
            pass

    def _ekon_zdarzenie(self, typ, d):
        """Kopiuje wybrane zdarzenia telemetrii do dziennika ekonomii (patrz tabela rekordów w SPEC)."""
        if typ == "zabicie":
            self.ekon_razem["zab"] += 1
            self._ekon("zabicie", n=d.get("n"), walka_s=d.get("walka_s"))
        elif typ == "exp_zabicie":
            self._ekon("exp", n=d.get("n"), exp=d.get("exp"), zab=d.get("zab"))
        elif typ == "uh_run":
            if d.get("wynik") == "ok":
                self.ekon_razem["uh"] += d.get("rzuty") or 1
            self._ekon("uh", wynik=d.get("wynik"), rzuty=d.get("rzuty"), czas_s=d.get("czas_s"), powod=d.get("powod"))
        elif typ in ("jedzenie_walka", "jedzenie_mana"):
            self._ekon("jedzenie", rodzaj="walka" if typ == "jedzenie_walka" else "mana")

    def _ekon_lup(self, zrodlo, wynik):
        """Zamyka rekord `lup` z linii zebranych od ostatniego zamknięcia i czyści akumulator."""
        t = self.zegar()
        r = self.lup.rekord(zrodlo, wynik, self.ost_zabicie, t)
        self.lup.reset()
        self.ekon_razem["gold"] += r["gold"] or 0
        self._ekon("lup", **r)

    def _ekon_tik(self, t, r):
        if t - self.ekon_tik_ost < ekonomia.TIK_S:
            return
        self.ekon_tik_ost = t
        self._ekon("tik", t=t, exp=r.get("exp"), mana=r.get("mana"), max_mana=r.get("max_mana"), hp=r.get("hp"),
                   poz=r.get("poz"), stan=r.get("stan"), gold_razem=self.ekon_razem["gold"],
                   uh_razem=self.ekon_razem["uh"], zab_razem=self.ekon_razem["zab"])

    def _postac_testowa(self):
        return self.nazwa_postaci in NAZWY_TESTOWE

    def _zapisz(self, r):
        if self.zapis:
            r["pid"], r["sesja"], r["src"] = self.pid, self.sesja, self.src
        self.rek.append(r)
        if r.get("typ") == "probka":
            try:
                self._ekon_tik(r["t"], r)
            except Exception:
                pass
        while self.rek and r["t"] - self.rek[0]["t"] > PAMIEC_S:
            self.rek.popleft()
        if not self.zapis or self._postac_testowa():     # R0a: atrapa "Ja" nie trafia do pliku
            return
        try:
            self.katalog.mkdir(parents=True, exist_ok=True)
            p = self._plik(r["t"])
            if p.exists() and p.stat().st_size > self.max_bajtow:
                p.replace(p.with_suffix(".jsonl.1"))
            with p.open("a") as f:
                f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
        except OSError:
            pass

    def sprzatnij_stare(self):
        if not self.zapis:
            return
        try:
            pliki = sorted(self.katalog.glob("telemetria-*.jsonl*"))
            for p in pliki[:-2 * DNI] if len(pliki) > 2 * DNI else []:
                p.unlink()
        except OSError:
            pass

    def zdarzenie(self, typ, **d):
        r = {"t": round(self.zegar(), 1), "typ": typ, **d}
        self._zapisz(r)
        if typ == "poscig_pamiec_koniec":
            self._ep_pamiec(d)
        if typ == "poscig_koniec":
            for pow_, n in (d.get("puszczenia") or {}).items():
                self.puszczenia_sesja[pow_] = self.puszczenia_sesja.get(pow_, 0) + int(n)
            if d.get("t_pierwszy_krok") is not None:
                self.pierwszy_krok_sesja.append(d["t_pierwszy_krok"])
        try:
            self._ekon_zdarzenie(typ, d)
        except Exception:
            pass
        if typ in ("epizod_celu", "exp_zabicie"):
            lst = self.sesja_ep if typ == "epizod_celu" else self.sesja_exp
            lst.append(r)
            if len(lst) > EP_MAX:
                del lst[:len(lst) - EP_MAX]
        return r

    def akcja_wykonana(self, nazwa, wynik=""):
        self.akcja = (self.zegar(), nazwa, str(wynik)[:60])

    # --- próbka z cavebota ---
    def probka(self, cb, g, poz, lista, wczesna=None):
        """wczesna: powód wczesnego zakończenia obiegu (R0b); próbka bez liczenia dróg (A*), tylko z cache."""
        t = self.zegar()
        if t - self.ostatnia_probka < 1.0:
            return None
        self.ostatnia_probka = t
        nz = getattr(getattr(cb, "postac", None), "nazwa", None)
        if isinstance(nz, str):
            self.nazwa_postaci = nz
        stwory = []
        dbb = getattr(cb, "droga_bez_blokad", 0)   # nasze zapytania o drogę nie psują licznika bota
        liczyc = t - self.astar_ost >= ASTAR_CO and not wczesna
        if liczyc:
            self.astar_ost = t
            self.astar_cache = {}
        blisko = sorted((s for s in lista if not s.get("gracz") and s["z"] == poz[2] and s.get("hp", 100) > 0
                         and max(abs(s["x"] - poz[0]), abs(s["y"] - poz[1])) <= 8),
                        key=lambda s: max(abs(s["x"] - poz[0]), abs(s["y"] - poz[1])))
        do_drogi = {s["id"] for s in blisko[:ASTAR_MAX]}
        for s in lista:
            if s["z"] != poz[2] or s.get("hp", 100) <= 0:
                continue
            if abs(s["x"] - poz[0]) > 8 or abs(s["y"] - poz[1]) > 6:
                continue
            odl = max(abs(s["x"] - poz[0]), abs(s["y"] - poz[1]))
            w = {"n": s["nazwa"], "dx": s["x"] - poz[0], "dy": s["y"] - poz[1], "odl": odl,
                 "hp": s.get("hp"), "gracz": bool(s.get("gracz"))}
            if cb.cel and cb.cel.get("id") == s["id"]:
                w["cel"] = 1
            if s.get("widmo"):
                w["widmo"] = 1                  # widma.py: wpis zostaje w próbce (diagnostyka), ale nie liczy się do zajętości
            if cb.ignorowane.get(s["id"], 0) > cb.zegar():
                w["ign"] = 1
            if not s.get("gracz") and odl <= 8 and s["id"] in do_drogi:
                if liczyc:
                    try:
                        # te same argumenty co decyzja bota: zajęte jak w podejdz, skosy jak w walcz
                        zaj = cb.zajete_bez_nas(poz) if hasattr(cb, "zajete_bez_nas") else ()
                        d = cb.droga(tuple(poz), (s["x"], s["y"], s["z"]), zaj, 1,
                                     skosy=getattr(cb, "klik", None) is not None)
                        self.astar_cache[s["id"]] = (d is not None, None if d is None else len(d))
                    except Exception:
                        pass
                if s["id"] in self.astar_cache:
                    w["osiagalny"], w["droga"] = self.astar_cache[s["id"]]
            stwory.append(w)
            if w["gracz"] and odl == 0 and w["n"] in NAZWY_TESTOWE:
                self.nazwa_postaci = w["n"]              # R0a: własny wpis atrapy
        stwory.sort(key=lambda w: w["odl"])
        cb.droga_bez_blokad = dbb
        r = {"t": round(t, 1), "typ": "probka", "stan": cb.stan, "poz": list(poz),
             "hp": round(g["proc"]) if g.get("proc") is not None else None,
             "mana": g.get("mana"), "max_mana": g.get("max_mana"), "stwory": stwory[:STWORY_MAX], "dbb": dbb}
        if g.get("exp") is not None:
            r["exp"] = g["exp"]
        if wczesna:
            r["wczesna"] = wczesna
        if cb.cel:
            r["cel"] = {k: cb.cel.get(k) for k in ("id", "nazwa", "poz", "hp", "odl")}
            if any(w.get("cel") and w.get("ign") for w in stwory):
                r["cel"]["ign"] = 1
        diag = getattr(cb, "lww_diag", None)       # ostatnia ocena lootu w walce: flaga ataku i powód odmowy
        tc = cb.zegar() if callable(getattr(cb, "zegar", None)) else t     # zegar bota (diag.t jest w jego skali)
        if isinstance(diag, dict) and tc - diag.get("t", float("-inf")) < 3.0:
            r["lww_powod"] = diag.get("powod")
            if diag.get("atak") is not None:
                r["atak"] = bool(diag["atak"])
        if self.akcja and t - self.akcja[0] < 5:
            r["akcja"] = {"co": self.akcja[1], "wynik": self.akcja[2], "temu": round(t - self.akcja[0], 1)}
        self._zapisz(r)
        self._ostatnie_tik(t, g, poz, cb.stan)
        self._utknięcie(r)
        if wczesna:              # R0b: próbka z wczesnego zakończenia obiegu tylko uzupełnia lukę, nie zasila epizodów
            return r
        try:
            self._ep_probka(r)
            self._exp_probka(r)
        except Exception:        # pomiar nigdy nie psuje bota
            pass
        return r

    def _ostatnie_aktywne(self):
        return self.ostatnie is not None and self.zapis and not self._postac_testowa()

    def _ostatnie_tik(self, t, g, poz, stan):
        """Zapis ostatnie.json co 60 s i przy zmianie levelu (ostatnie.Pisarz.tik). Nigdy nie rzuca do pętli bota."""
        if not self._ostatnie_aktywne():
            return
        try:
            self.ostatnie.tik(t, g, poz, stan if isinstance(stan, str) else None, self.nazwa_postaci,
                              {"start": self.sesja, "zab": self.ekon_razem["zab"], "gold": self.ekon_razem["gold"],
                               "uh": self.ekon_razem["uh"]})
        except Exception as e:      # noqa: BLE001
            print(f"telemetria: ostatnie.tik: {e!r}", flush=True)

    def ostatnie_stop(self, powod=None):
        """Hak mozg.py: bot kończy z powodu STOP / STOP_RECZNY / sygnału (ścieżki Zatrzymano nie przechodzą przez HAKI_LOGU)."""
        if not self._ostatnie_aktywne():
            return False
        try:
            return self.ostatnie.stop(powod)
        except Exception as e:      # noqa: BLE001
            print(f"telemetria: ostatnie.stop: {e!r}", flush=True)
            return False

    # --- R0b: okno ruchu co RUCH_OKNO_S (czas marszu/stania, przyczyny, luki, kroki, kliki) ---
    def ruch_tick(self, t, poz, stan, powod, kliki=0, strzalki=0):
        """Wołane raz na początku obiegu Cavebot.tick (przed wczesnymi return), bez RPC: tylko arytmetyka.
        Odstęp od poprzedniego obiegu liczymy do marszu (pozycja się zmieniła) albo stania (nie), w stanie `stan`
        z początku obiegu (to, co bot robił w tym odstępie). `powod` = przyczyna stania (schody, ogien, utkniecie,
        loot, walka, patrol_postoj, inne). Zwraca rekord ruch_okno, gdy okno się zamknęło."""
        poz = tuple(poz)
        w = self._ruch
        if w is None:
            self._ruch = {"t0": t, "t": t, "poz": poz, "kl": kliki, "st": strzalki, **self._ruch_puste()}
            return None
        dt = t - w["t"]
        if dt > 0:
            dtc = min(dt, RUCH_DT_MAX)
            ruszyl = poz != w["poz"]
            if ruszyl and poz[2] != w["poz"][2]:
                w["zmiany_pietra"] += 1
            elif ruszyl and max(abs(poz[0] - w["poz"][0]), abs(poz[1] - w["poz"][1])) <= RUCH_SKOK_MAX:
                w["kroki"] += max(abs(poz[0] - w["poz"][0]), abs(poz[1] - w["poz"][1]))
            ms = w["stany"].setdefault(str(stan), [0.0, 0.0])
            if ruszyl:
                ms[0] += dtc
            else:
                ms[1] += dtc
                w["powody"][powod] = w["powody"].get(powod, 0.0) + dtc
                if stan == "IDZ":
                    w["powody_idz"][powod] = w["powody_idz"].get(powod, 0.0) + dtc
            w["ticki"] += 1
            if dt >= RUCH_LUKA_S:
                w["luki"] += 1
                w["luki_s"] += dt
                w["luka_max"] = max(w["luka_max"], dt)
        w["t"], w["poz"] = t, poz
        if t - w["t0"] < RUCH_OKNO_S:
            return None
        r = self.zdarzenie(
            "ruch_okno", okno_s=round(t - w["t0"], 1), ticki=w["ticki"],
            stany={k: [round(v[0], 1), round(v[1], 1)] for k, v in w["stany"].items()},
            powody_s={k: round(v, 1) for k, v in w["powody"].items()},
            powody_idz_s={k: round(v, 1) for k, v in w["powody_idz"].items()},
            luki=w["luki"], luki_s=round(w["luki_s"], 1), luka_max=round(w["luka_max"], 1),
            kroki=w["kroki"], zmiany_pietra=w["zmiany_pietra"],
            kliki=max(0, kliki - w["kl"]), strzalki=max(0, strzalki - w["st"]), poz=list(poz))
        self._ruch = {"t0": t, "t": t, "poz": poz, "kl": kliki, "st": strzalki, **self._ruch_puste()}
        return r

    @staticmethod
    def _ruch_puste():
        return {"stany": {}, "powody": {}, "powody_idz": {}, "ticki": 0, "luki": 0, "luki_s": 0.0, "luka_max": 0.0,
                "kroki": 0, "zmiany_pietra": 0}

    # --- epizody celu (dobijanie) ---
    def _ep_pamiec(self, d):
        """Koniec pościgu na pamięć za celem, który zniknął z widoku żywy: odnaleziony = epizod trwa dalej
        (następny "Nowy cel" tego samego mobka go wznawia, bez wpisu zgubionego); inaczej zamykamy go
        jako zgubiony (cel nie wrócił w limicie albo pościg przerwano)."""
        ep = self.ep
        if not ep or (d.get("cel") and ep["n"] != d["cel"]):
            return
        if d.get("wynik") == "odnaleziony":
            ep["odnaleziony"] = ep["wznow"] = True
        else:
            self._ep_zamknij(self.zegar(), "zgubiony", "zniknął z widoku żywy")

    def _ep_nowy(self, n, pos, hp, t, decyzja_id=None):
        if self.ep and self.ep.get("wznow") and self.ep["n"] == n:
            self.ep["wznow"] = False          # ten sam mob odnaleziony po zniknięciu: ciągniemy ten sam epizod
            return
        if self.ep:
            self._ep_zamknij(t, None)
        self.ep = {"n": n, "id": None, "t0": t, "hp0": hp, "hp": hp, "pos": pos, "t_hit": None, "t_30": None,
                   "uciekl": 0, "kroki": 0, "blisko": False, "poz_bota": None, "ucieczka": False, "ign": False,
                   "decyzja_id": decyzja_id}

    def _ep_probka(self, r):
        ep = self.ep
        if not ep:
            return
        if r.get("stan") == "UCIECZKA":
            ep["ucieczka"] = True
        c = r.get("cel")
        if not c or (c.get("nazwa") and c["nazwa"] != ep["n"]):
            return
        ep["id"] = c.get("id")
        hp = c.get("hp")
        if hp is not None:
            ep["hp"] = hp
            if ep["t_hit"] is None and hp < ep["hp0"]:
                ep["t_hit"] = r["t"]
            if ep["t_30"] is None and hp <= PROG_30:
                ep["t_30"] = r["t"]
                if ep["t_hit"] is None:
                    ep["t_hit"] = r["t"]
        if c.get("poz"):
            ep["pos"] = list(c["poz"])[:2]
        ep["ign"] = bool(c.get("ign"))
        odl = c.get("odl")
        poz = tuple(r["poz"])
        if odl is not None:
            if ep["poz_bota"] is not None and poz != ep["poz_bota"] and odl > 1:
                ep["kroki"] += 1
            if odl <= 2:
                ep["blisko"] = True
            elif ep["blisko"] and odl >= 3 and ep["t_hit"] is not None:
                ep["uciekl"] += 1
                ep["blisko"] = False
        ep["poz_bota"] = poz

    def _ep_zamknij(self, t, wynik, powod=None):
        """wynik: 'zabity' | 'porzucony' | 'zgubiony' | None (cichy koniec: z flagi ign albo zgubiony)."""
        ep, self.ep = self.ep, None
        if not ep:
            return None
        if wynik is None:
            wynik, powod = ("porzucony", "ignorowany") if ep["ign"] else ("zgubiony", "zniknął z widoku żywy")
        if wynik != "zabity" and ep["ucieczka"] and powod in (None, "ignorowany", "zniknął z widoku żywy"):
            wynik, powod = "porzucony", "ucieczka bota z walki"
        trafiony = ep["t_hit"] is not None or wynik == "zabity"
        t_hit = ep["t_hit"] if ep["t_hit"] is not None else ep["t0"]
        d = {"n": ep["n"], "id": ep["id"], "wynik": wynik, "powod": powod, "trafiony": trafiony,
             "t0": round(ep["t0"], 1), "t_hit": round(t_hit, 1) if trafiony else None,
             "hp0": ep["hp0"], "hp_porz": None if wynik == "zabity" else ep["hp"],
             "do_zab_s": round(t - t_hit, 1) if wynik == "zabity" else None,
             "od30_s": round(t - ep["t_30"], 1) if wynik == "zabity" and ep["t_30"] is not None else None,
             "uciekl": ep["uciekl"], "kroki": ep["kroki"], "pos": ep["pos"]}
        if ep.get("odnaleziony"):
            d["odnaleziony_po_zniknieciu"] = True
        if ep.get("decyzja_id") is not None:
            d["decyzja_id"] = ep["decyzja_id"]       # 15.10: łączy epizod z rekordem "decyzja" D1
        return self.zdarzenie("epizod_celu", **d)

    def _ep_odpuszczenie(self, n, txt):
        if not self.ep or self.ep["n"] != n:
            return
        low = txt.lower()
        if "za ścian" in low:
            powod = "odpuszczony za ścianą"
        elif "nie zbliżam" in low:
            powod = "nie zbliżam się"
        else:
            powod = txt[:30]
        self._ep_zamknij(self.zegar(), "porzucony", powod)

    # --- exp na zabicie (wzrost exp gracza po zabiciu celu) ---
    def _exp_probka(self, r):
        exp = r.get("exp")
        if exp is None:
            return
        t = r["t"]
        cz = self.exp_czeka
        if cz:
            if exp > cz["exp0"]:
                n = len(cz["n"])
                if len(set(cz["n"])) == 1:
                    self.zdarzenie("exp_zabicie", n=cz["n"][0], exp=round((exp - cz["exp0"]) / n, 1), zab=n)
                self.exp_czeka = None
            elif t - cz["t"] > EXP_CZEKAJ_S:
                self.exp_czeka = None
        self.exp_hist.append((t, exp))

    def _exp_zabicie(self, n, t):
        if self.exp_czeka:
            self.exp_czeka["n"].append(n)
            return
        exp0 = None
        for tt, e in self.exp_hist:
            if tt <= t - EXP_PRZED_S:
                exp0 = e
        if exp0 is None and self.exp_hist:
            exp0 = self.exp_hist[0][1]
        if exp0 is not None:
            self.exp_czeka = {"t": t, "exp0": exp0, "n": [n]}

    def _utknięcie(self, r):
        poz, t, stan = tuple(r["poz"]), r["t"], r["stan"]
        if self.stoi_od is None or self.stoi_od[0] != poz or stan in STANY_POSTOJU:
            self.stoi_od, self.utknieto = (poz, t), False
            return
        if not self.utknieto and t - self.stoi_od[1] >= UTKNIECIE_S:
            # stoimy w walce przy celu w zasięgu ataku to nie utknięcie
            if any(w.get("cel") and w["odl"] <= 1 for w in r["stwory"]):
                return
            self.utknieto = True
            self.zdarzenie("utkniecie", stan=stan, poz=list(poz), s=round(t - self.stoi_od[1]),
                           stwory=[(w["n"], w["odl"]) for w in r["stwory"][:3]])

    # --- zdarzenia z linii logu ---
    def linia(self, txt):
        t = self.zegar()
        if txt.startswith("ALARM") and self._ostatnie_aktywne():     # trwały „ostatni alarm” (panel pokazuje alarm tylko 60 s)
            try:
                self.ostatnie.alarm(txt)
            except Exception as e:      # noqa: BLE001
                print(f"telemetria: ostatnie.alarm: {e!r}", flush=True)
        m = RE_STAN.match(txt)
        if not m and not txt.startswith("debug:"):
            self.akcja_wykonana(txt[:60])
        if m:
            stan = m[1]
            if stan == "LOOT" and self.ostatni_stan != "LOOT":
                self.loot_start = t
                zywe = self._zywe_blisko()
                if zywe:
                    self.zdarzenie("loot_przy_zywym", zywe=zywe)
            self.ostatni_stan = stan
            return
        try:
            if self.lup.linia(txt):                 # zebrano/cenne/zjedzono: składamy rekord `lup`
                return
            if ekonomia.RE_LUP_WALKA.match(txt):    # znacznik końca lootu w walce
                self._ekon_lup("walka", "ok")
                return
        except Exception:                           # dziennik ekonomii nigdy nie psuje bota
            pass
        m = RE_CEL.search(txt)
        if m:
            self.cel_start = t
            did, self.nast_decyzja = self.nast_decyzja, None
            dd = {"decyzja_id": did} if did is not None else {}
            self.zdarzenie("nowy_cel", n=m[1], pos=[int(m[2]), int(m[3])], hp=int(m[4]), **dd)
            self._ep_nowy(m[1], [int(m[2]), int(m[3])], int(m[4]), t, did)
            return
        m = RE_ODP.search(txt)
        if m:
            odl = hp = None
            for r in reversed(self.rek):
                if r["typ"] == "probka":
                    c = r.get("cel")
                    if c:
                        odl, hp = c.get("odl"), c.get("hp")
                    break
            self.zdarzenie("odpuszczenie", n=m[1], powod=m[2][:100], odl=odl, hp=hp)
            self._ep_odpuszczenie(m[1], m[2])
            return
        m = RE_ZMIANA.search(txt)
        if m:
            if self.ep and self.ep["n"] == m[2]:
                self._ep_zamknij(t, "porzucony", "zmiana celu na świeżego")
            return
        m = RE_ZGUB.search(txt)
        if m:
            if self.ep and self.ep["n"] == m[1]:
                self._ep_zamknij(t, "zgubiony", "zniknął z widoku żywy")
            return
        m = RE_ZAB.search(txt)
        if m:
            self.ost_zabicie = (m[1], t)
            self.zdarzenie("zabicie", n=m[1], walka_s=round(t - self.cel_start, 1) if self.cel_start else None)
            self.cel_start = None
            if self.ep and self.ep["n"] == m[1]:
                self._ep_zamknij(t, "zabity")
            self._exp_zabicie(m[1], t)
            return
        m = RE_LOOT_WSTRZYMANY.match(txt)
        if m:
            self.zdarzenie("loot_wstrzymany", zwloki=[int(m[1]), int(m[2])], n=int(m[3]))
            return
        m = RE_LOOT.match(txt)
        if m:
            self.zdarzenie("loot", wynik=m[1], s=round(t - self.loot_start, 1) if self.loot_start else None)
            try:
                self._ekon_lup("zwloki", m[1])
            except Exception:
                pass
            self.loot_start = None
            return
        if txt.startswith(("Przerywam loot", "Loot odłożony", "Czekam na")):
            self.zdarzenie("info", tekst=txt[:100])

    def _zywe_blisko(self):
        for r in reversed(self.rek):
            if r["typ"] == "probka":
                if self.zegar() - r["t"] > 5:
                    return []
                return [(w["n"], w["odl"]) for w in r["stwory"]
                        if not w["gracz"] and w["odl"] <= BLISKO_LOOT]
        return []

    # --- agregaty / anomalie ---
    def okno(self, sekundy):
        od = self.zegar() - sekundy
        return [r for r in self.rek if r["t"] >= od]

    def dobicie(self, sekundy=None):
        """Statystyka dobijania dla okna (None = od startu procesu). Exp referencyjny: mediana z sesji."""
        if sekundy is None:
            rek = self.sesja_ep + self.sesja_exp
        else:
            od = self.zegar() - sekundy
            rek = [r for r in self.sesja_ep + self.sesja_exp if r["t"] >= od]
        return dobicie(rek, ref_exp=exp_ref(self.sesja_exp))


def agreguj(rek, sekundy):
    """Statystyki z listy rekordów obejmujących `sekundy` s. Zwraca dict (JSON-owalny)."""
    min_ = max(sekundy / 60, 1e-9)
    z = Counter(r["typ"] for r in rek)
    stany = Counter(r["stan"] for r in rek if r["typ"] == "probka")
    n_p = sum(stany.values()) or 1
    odp = [r for r in rek if r["typ"] == "odpuszczenie"]
    cele = Counter((r["n"], r.get("hp")) for r in rek if r["typ"] == "nowy_cel")
    loot = Counter(r["wynik"] for r in rek if r["typ"] == "loot")
    walki = [r["walka_s"] for r in rek if r["typ"] == "zabicie" and r.get("walka_s") is not None]
    nieosiagalne = sum(1 for r in rek if r["typ"] == "probka" for w in r["stwory"]
                       if w.get("osiagalny") is False and w["odl"] <= 5)
    return {
        "okno_min": round(sekundy / 60, 1),
        "zabicia_na_min": round(z["zabicie"] / min_, 2),
        "odpuszczenia_na_min": round(len(odp) / min_, 2),
        "powody_odpuszczen": dict(Counter(r["powod"][:40] for r in odp).most_common(4)),
        "powtorzone_cele": sum(1 for v in cele.values() if v >= 3),
        "loot": dict(loot),
        "loot_przy_zywym": z["loot_przy_zywym"],
        "utkniecia": z["utkniecie"],
        "droga_bez_blokad": max([r.get("dbb", 0) for r in rek if r["typ"] == "probka"] or [0])
        - min([r.get("dbb", 0) for r in rek if r["typ"] == "probka"] or [0]),
        "udzial_stanow_proc": {k: round(100 * v / n_p) for k, v in stany.most_common(6)},
        "sr_walka_s": round(sum(walki) / len(walki), 1) if walki else None,
        "sekundy_z_nieosiagalnym_<=5": nieosiagalne,
    }


def loot_w_walce(rek):
    """Podsumowanie lootu w walce z rekordów: {"kroki": n, "ukonczone": n, "przerwane": {powod: n},
    "atak_wylaczony": n} (atak_wylaczony > 0 = klik w zwłoki wyłączył atak: do zbadania na żywo)."""
    w = {"kroki": 0, "ukonczone": 0, "przerwane": {}, "atak_wylaczony": 0}
    for r in rek:
        if r.get("typ") == "loot_w_walce_krok":
            if r.get("krok") == "koniec":
                w["ukonczone"] += 1
            else:
                w["kroki"] += 1
        elif r.get("typ") == "loot_w_walce_przerwany":
            p = r.get("powod", "?")
            w["przerwane"][p] = w["przerwane"].get(p, 0) + 1
            if p == "atak_wylaczony":
                w["atak_wylaczony"] += 1
    return w


def linia_stworow(r):
    """Zwięzła linia do logu bota z próbki: 'Rat 2,1 hp100 cel; Cave Rat 5,-3 hp80 !droga'."""
    return "debug: stwory: " + "; ".join(
        f"{w['n']} {w['dx']},{w['dy']} hp{w['hp']}" + (" cel" if w.get("cel") else "")
        + (" ign" if w.get("ign") else "") + (" !droga" if w.get("osiagalny") is False else "")
        + (" widmo" if w.get("widmo") else "")
        for w in r["stwory"]) if r["stwory"] else "debug: stwory: brak"


def najgorsze(rek, ile=6):
    """Najbardziej podejrzane zdarzenia (do przykładów dla analityka)."""
    waga = {"loot_przy_zywym": 5, "utkniecie": 4, "odpuszczenie": 3}
    kand = [r for r in rek if r["typ"] in waga or (r["typ"] == "loot" and r.get("wynik") != "ok")
            or (r["typ"] == "zabicie" and (r.get("walka_s") or 0) > 40)]
    kand.sort(key=lambda r: (-waga.get(r["typ"], 2), -r["t"]))
    return [{k: v for k, v in r.items()} for r in kand[:ile]]


def anomalie(rek, teraz):
    """Lista opisów anomalii z ostatnich minut (puste = OK)."""
    wynik = []
    ost60 = [r for r in rek if r["t"] >= teraz - 60]
    if sum(1 for r in ost60 if r["typ"] == "odpuszczenie") >= 3:
        wynik.append(">=3 odpuszczenia w 60 s")
    cele = Counter((r["n"], r.get("hp")) for r in ost60 if r["typ"] == "nowy_cel")
    if cele and max(cele.values()) >= 3:
        wynik.append("ten sam cel wzięty >=3 razy w 60 s")
    if any(r["typ"] == "loot_przy_zywym" for r in rek if r["t"] >= teraz - 120):
        wynik.append(f"loot zaczęty przy żywym celu <= {BLISKO_LOOT} pól")
    if any(r["typ"] == "loot" and r["wynik"] == "brak_okna" for r in ost60):
        wynik.append("loot brak_okna")
    if any(r["typ"] == "utkniecie" for r in ost60):
        wynik.append("utknięcie")
    probki = [r for r in rek if r["typ"] == "probka" and r["t"] >= teraz - 180]
    if len(probki) >= 150 and not any(r["typ"] == "zabicie" for r in rek if r["t"] >= teraz - 180) \
            and any(w["odl"] <= 8 and not w["gracz"] for r in probki for w in r["stwory"]):
        wynik.append("brak zabicia 3 min mimo potworów w pobliżu")
    return wynik


# --- statystyka dobijania (z zdarzeń epizod_celu / exp_zabicie) ---
def _mediana(l):
    if not l:
        return None
    l = sorted(l)
    n = len(l)
    return l[n // 2] if n % 2 else round((l[n // 2 - 1] + l[n // 2]) / 2, 1)


def _p90(l):
    if not l:
        return None
    l = sorted(l)
    return l[max(0, math.ceil(0.9 * len(l)) - 1)]


def exp_ref(rek):
    """Mediana exp na zabicie per nazwa gatunku (z zdarzeń exp_zabicie); brak danych = brak klucza."""
    per = {}
    for r in rek:
        if r.get("typ") == "exp_zabicie" and r.get("exp") is not None:
            per.setdefault(r["n"], []).append(r["exp"])
    return {n: _mediana(v) for n, v in per.items() if v}


SCAL_OKNO_S = 45                 # s: porzucony cel zabity w tym oknie (to samo id) nie jest stratą


def scal_epizody(rek, okno=SCAL_OKNO_S):
    """Porzucone/zgubione epizody, których cel (to samo id) został zabity w ciągu `okno` s od ostatniego
    porzucenia (seria zmian celu liczy się jako jedna), znikają z listy,
    a zabicie dostaje adnotację po_zmianie_celu=True (chwilowa zmiana celu na świeżego nie jest zgubionym mobem).
    Zwraca nową listę (rekordy wejściowe nie są modyfikowane)."""
    zab, ost = {}, {}
    for r in rek:
        if r.get("typ") == "epizod_celu" and r.get("id") is not None:
            if r.get("wynik") == "zabity":
                zab.setdefault(r["id"], []).append(r["t"])
            elif r.get("wynik") in ("porzucony", "zgubiony"):
                ost[r["id"]] = max(ost.get(r["id"], 0), r["t"])      # ostatnie porzucenie tego celu
    if not zab:
        return list(rek)
    oznacz, out = set(), []
    for r in rek:
        if r.get("typ") == "epizod_celu" and r.get("wynik") in ("porzucony", "zgubiony") and r.get("id") is not None:
            kt = [t for t in zab.get(r["id"], ()) if r["t"] <= t <= ost[r["id"]] + okno]
            if kt:
                oznacz.add((r["id"], min(kt)))
                continue
        out.append(r)
    return [dict(r, po_zmianie_celu=True) if r.get("typ") == "epizod_celu" and r.get("wynik") == "zabity"
            and (r.get("id"), r["t"]) in oznacz else r for r in out]


def dobicie(rek, ref_exp=None):
    """Agregat dobijania z listy rekordów. Liczą się cele z >=1 trafieniem.
    wskaznik = zabite / (zabite + porzucone + zgubione) w %."""
    rek = scal_epizody(rek)
    ep = [r for r in rek if r.get("typ") == "epizod_celu" and r.get("trafiony")]
    zab = [r for r in ep if r["wynik"] == "zabity"]
    porz = [r for r in ep if r["wynik"] == "porzucony"]
    zgub = [r for r in ep if r["wynik"] == "zgubiony"]
    n = len(ep)
    straty = porz + zgub
    powody = Counter((r.get("powod") or ("zniknął z widoku żywy" if r["wynik"] == "zgubiony" else "?"))
                     for r in straty)
    do_zab = [r["do_zab_s"] for r in zab if r.get("do_zab_s") is not None]
    od30 = [r["od30_s"] for r in zab if r.get("od30_s") is not None]
    ref = ref_exp if ref_exp is not None else exp_ref(rek)
    zdobyty = round(sum(r["exp"] * r.get("zab", 1) for r in rek
                        if r.get("typ") == "exp_zabicie" and r.get("exp") is not None))
    stracony = round(sum(ref[r["n"]] for r in straty if ref.get(r["n"])))
    bez_ref = sum(1 for r in straty if not ref.get(r["n"]))
    pot = zdobyty + stracony
    return {
        "epizody": n, "zabite": len(zab), "porzucone": len(porz), "zgubione": len(zgub),
        "odnalezione": sum(1 for r in ep if r.get("odnaleziony_po_zniknieciu")),
        "wskaznik": round(100 * len(zab) / n) if n else None,
        "med_do_zab_s": _mediana(do_zab), "p90_do_zab_s": _p90(do_zab),
        "med_od30_s": _mediana(od30), "p90_od30_s": _p90(od30),
        "powod_top": powody.most_common(1)[0][0] if powody else None,
        "powody": dict(powody.most_common(5)),
        "exp_zdobyty": zdobyty, "exp_stracony": stracony, "exp_bez_danych": bez_ref,
        "exp_utracony_proc": round(100 * stracony / pot) if pot and stracony else (0 if zdobyty else None),
    }


def _s(x):
    return f"{x:.0f} s" if x is not None else "?"


def linia_dobicia(d, exp=True):
    """'dobicie 92% (11/12), mediana 14 s, stracone ~30 exp = 8% potencjału' albo None bez danych."""
    if not d or not d.get("epizody"):
        return None
    t = f"dobicie {d['wskaznik']}% ({d['zabite']}/{d['epizody']}), mediana {_s(d['med_do_zab_s'])}"
    if exp and d.get("exp_stracony"):
        t += f", stracone ~{d['exp_stracony']} exp = {d['exp_utracony_proc']}% potencjału"
    return t


def wczytaj_rekordy(katalog=LOGI, od_t=None, tail_bajtow=None, wszystko=False):
    """Rekordy epizod_celu / exp_zabicie z plików telemetrii (bez uruchamiania bota).
    tail_bajtow: czytaj tylko koniec najnowszego pliku (szybko, do paska)."""
    wynik = []
    try:
        pliki = sorted(Path(katalog).glob("telemetria-*.jsonl*"))
    except OSError:
        return wynik
    if tail_bajtow and pliki:
        pliki = [p for p in pliki if p.name.endswith(".jsonl")][-1:]
    for p in pliki:
        try:
            with p.open("rb") as f:
                pierwsza = True
                if tail_bajtow:
                    rozm = f.seek(0, 2)
                    if rozm > tail_bajtow:
                        f.seek(rozm - tail_bajtow)
                        f.readline()
                    else:
                        f.seek(0)
                else:
                    f.seek(0)
                for b in f:
                    if not wszystko and b'"epizod_celu"' not in b and b'"exp_zabicie"' not in b:
                        continue
                    try:
                        r = json.loads(b)
                    except ValueError:
                        continue
                    if (wszystko or r.get("typ") in ("epizod_celu", "exp_zabicie")) and (od_t is None or r["t"] >= od_t):
                        wynik.append(r)
        except OSError:
            continue
    wynik.sort(key=lambda r: r["t"])
    return wynik


def odtworz_epizody(rek):
    """Odtwarza epizody z surowych rekordów (probka/nowy_cel/odpuszczenie/zabicie) starszej telemetrii,
    sprzed wprowadzenia zdarzenia epizod_celu. Zmiana celu i zniknięcie bywają tu nierozróżnialne
    (cichy koniec = zgubiony / ignorowany). Zwraca listę rekordów epizod_celu."""
    cur = [0.0]
    tl = Telemetria(zapis=False, zegar=lambda: cur[0])
    for r in sorted(rek, key=lambda r: r["t"]):
        cur[0] = r["t"]
        typ = r.get("typ")
        if typ == "nowy_cel":
            tl._ep_nowy(r["n"], r.get("pos"), r.get("hp", 100), r["t"])
        elif typ == "probka":
            tl._ep_probka(r)
        elif typ == "odpuszczenie":
            tl._ep_odpuszczenie(r["n"], r.get("powod", ""))
        elif typ == "log_zmiana":
            m = RE_ZMIANA.search(r["tekst"])
            if m and tl.ep and tl.ep["n"] == m[2]:
                tl._ep_zamknij(r["t"], "porzucony", "zmiana celu na świeżego")
        elif typ == "log_zgub":
            m = RE_ZGUB.search(r["tekst"])
            if m and tl.ep and tl.ep["n"] == m[1]:
                tl._ep_zamknij(r["t"], "zgubiony", "zniknął z widoku żywy")
        elif typ == "zabicie" and tl.ep and tl.ep["n"] == r["n"]:
            tl._ep_zamknij(r["t"], "zabity")
    return tl.sesja_ep


def zdarzenia_z_logow(katalog=LOGI, od_t=0):
    """Z logów bota (linie 'GG:MM:SS tekst') bierze to, czego nie ma w telemetrii: zmiany celu i zniknięcia
    celu z widoku. Data z mtime pliku. Zwraca rekordy typ log_zmiana / log_zgub."""
    wynik, widziane = [], set()
    try:
        pliki = [p for p in Path(katalog).glob("*.log") if p.name.startswith(("cavebot-", "mozg-stdout-"))
                 and p.stat().st_mtime >= od_t]
    except OSError:
        return wynik
    for p in pliki:
        try:
            dzien = time.strftime("%Y-%m-%d", time.localtime(p.stat().st_mtime))
            for l in p.read_text(errors="replace").splitlines():
                if len(l) < 10 or l[2] != ":" or l[5] != ":":
                    continue
                tekst = l[9:]
                if "Zmiana celu:" in tekst:
                    typ = "log_zmiana"
                elif RE_ZGUB.search(tekst):
                    typ = "log_zgub"
                else:
                    continue
                try:
                    t = time.mktime(time.strptime(f"{dzien} {l[:8]}", "%Y-%m-%d %H:%M:%S"))
                except ValueError:
                    continue
                if t > p.stat().st_mtime + 60:      # log z przed północy
                    t -= 86400
                if (t, tekst) in widziane or t < od_t:
                    continue
                widziane.add((t, tekst))
                wynik.append({"t": t, "typ": typ, "tekst": tekst})
        except OSError:
            continue
    return wynik
