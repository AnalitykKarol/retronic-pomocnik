"""Logika odczytu pamięci gry. Strażnik przeładowuje ten plik po każdej zmianie,
więc poprawki działają bez restartu gry.

Tylko odczyt: /proc/<pid>/mem otwierany jest w trybie "rb".
"""

import errno
import os
import re
import struct
import sys
import time
import threading

import rdzen_skan
import cpu_wdrozenie

import numpy as np

np.seterr(invalid="ignore", over="ignore")
_CPU_KOMPONENTY = cpu_wdrozenie.konfiguracja()
CPU_OPTYMALIZACJE = bool(_CPU_KOMPONENTY)
CPU_SKAN = "scan" in _CPU_KOMPONENTY
CPU_PID = "pid" in _CPU_KOMPONENTY
CPU_CZAT = "chat" in _CPU_KOMPONENTY

LIMIT_ADRESU = int(os.environ.get("POMOCNIK_LIMIT", 1 << 32))  # kod i dane gry (x86) leżą poniżej 4 GB

TYPY = {
    "i32": ("<i4", 4),
    "u32": ("<u4", 4),
    "u16": ("<u2", 2),
    "u8": ("u1", 1),
    "f32": ("<f4", 4),
    "f64": ("<f8", 8),
}

# Statystyki gracza w OTClient (LocalPlayer) leżą obok siebie jako double.
POLA_GRACZA = ["hp", "max_hp", "cap", "max_cap", "exp", "level", "procent", "mana", "max_mana"]
ZYWY_BLOK = 60.0   # s: tyle po ostatniej zmianie blok statystyk gracza uchodzi za żywy (nie widmo po relogu)


def exp_na_level(level):
    """Doświadczenie potrzebne do osiągnięcia danego levelu (wzór Tibii)."""
    return 50 * (level ** 3 - 6 * level ** 2 + 17 * level - 12) / 3


def potomkowie(korzen):
    rodzice = {}
    for wpis in os.listdir("/proc"):
        if not wpis.isdigit():
            continue
        try:
            with open(f"/proc/{wpis}/stat") as f:
                stat = f.read()
            rodzice[int(wpis)] = int(stat.rsplit(")", 1)[1].split()[1])
        except (OSError, IndexError, ValueError):
            pass
    wynik = []
    for pid in rodzice:
        p = pid
        while p in rodzice and p > 1:
            p = rodzice[p]
            if p == korzen:
                wynik.append(pid)
                break
    return wynik


def rss(pid):
    try:
        with open(f"/proc/{pid}/status") as f:
            for linia in f:
                if linia.startswith("VmRSS:"):
                    return int(linia.split()[1])
    except OSError:
        pass
    return 0


def znajdz_gre():
    kandydaci = []
    for pid in potomkowie(os.getpid()):
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().decode(errors="replace").lower()
        except OSError:
            continue
        if "retronic" in cmd and ".exe" in cmd and "straznik" not in cmd:
            kandydaci.append((rss(pid), pid))
    return max(kandydaci)[1] if kandydaci else None


def calkowite(x):
    return np.floor(x) == x


def maska_gracza(v):
    """Dla tablicy double zwraca maskę indeksów, od których zaczyna się blok
    statystyk gracza (POLA_GRACZA)."""
    n = len(v) - len(POLA_GRACZA) + 1
    if n <= 0:
        return np.zeros(0, bool)
    # filtr etapami: każdy warunek liczony tylko dla indeksów, które przeszły poprzednie
    pole = {nazwa: i for i, nazwa in enumerate(POLA_GRACZA)}
    lvl = v[pole["level"]:pole["level"] + n]
    idx = np.nonzero((lvl >= 1) & (lvl <= 5000))[0]

    def zostaw(warunek):
        nonlocal idx
        idx = idx[warunek(lambda nazwa: v[idx + pole[nazwa]])]

    zostaw(lambda w: calkowite(w("level")))
    zostaw(lambda w: (w("procent") >= 0) & (w("procent") <= 100) & calkowite(w("procent")))
    zostaw(lambda w: (w("max_hp") >= 100) & (w("max_hp") <= 200000) & calkowite(w("max_hp")))
    zostaw(lambda w: (w("hp") >= 0) & (w("hp") <= w("max_hp")) & calkowite(w("hp")))
    zostaw(lambda w: (w("max_cap") >= 0) & (w("max_cap") <= 100000) & (w("cap") >= 0) & (w("cap") <= w("max_cap")))
    zostaw(lambda w: (w("max_mana") >= 0) & (w("max_mana") <= 200000) & calkowite(w("max_mana")))
    zostaw(lambda w: (w("mana") >= 0) & (w("mana") <= w("max_mana")) & calkowite(w("mana")))
    # exp musi pasować do levelu
    zostaw(lambda w: calkowite(w("exp")) & (w("exp") >= exp_na_level(w("level")))
           & (w("exp") < exp_na_level(w("level") + 1)))
    wynik = np.zeros(n, bool)
    wynik[idx] = True
    return wynik


# Obiekt stwora w kliencie Retronic: 4 floaty 1.0 (kolor), ID, potem nazwa jako
# std::string MSVC (bufor 16 B, rozmiar, pojemność). Przesunięcia względem nazwy.
ZNACZNIK_STWORA = b"\x00\x00\x80\x3f" * 4   # przed ID, ID przed nazwą
NAZWA_STWORA = re.compile(rb"[\x20-\x7e]{1,15}\x00")
POZYCJA_STWORA = -0x24     # x (u32), y (u32), z (u8)
HP_STWORA = 0x18           # % HP (u8)
KIERUNEK_STWORA = 0x1C     # u32
NIEZNANA_POZYCJA = 0xFFFF
# Ramki OTClienta wokół stwora (Creature): dwa kolory RGBA (4 x f32) i bajty widoczności.
# "Static square" (stała, czerwona) = nasz cel ataku: klient ją zapala po Alt+kliku, gasi po
# zmianie celu / anulowaniu. Kolor bywa przyciemniony (miga), więc o celu decyduje bool.
# "Timed square" (czarna, na ~1 s) = serwer: ten stwór właśnie nas uderzył.
KOLOR_RAMKI_CHWILOWEJ = 0xB0   # 4 x f32, czarna (0, 0, 0, 1)
KOLOR_RAMKI = 0xC0             # 4 x f32, czerwona (1, 0, 0, 1)
RAMKA_CHWILOWA = 0xE0          # u8 (bool m_showTimedSquare)
RAMKA_STWORA = 0xE1            # u8 (bool m_showStaticSquare)


_WIADOMOSCI_ZAMEK = threading.RLock()


def _modul_wiadomosci():
    """Ładuje aktualne źródło raz na (mtime_ns, size), z pominięciem cache .pyc.

    Znacznik na module opisuje kod, który naprawdę wykonaliśmy, także gdy
    Pamiec/rdzen jest przeładowany lub moduł zaimportował wcześniej ktoś inny.
    Błędy wychodzą jak dotąd do osłony RPC; nie udają pustej listy wiadomości.
    """
    import importlib.util
    with _WIADOMOSCI_ZAMEK:
        modul = sys.modules.get("wiadomosci")
        plik = (modul.__file__ if modul is not None
                else os.path.join(os.path.dirname(__file__), "wiadomosci.py"))
        stat = os.stat(plik)
        sygnatura = (stat.st_mtime_ns, stat.st_size)
        if (modul is not None
                and getattr(modul, "_retronic_zrodlo_sygnatura", None) == sygnatura):
            return modul
        with open(plik, "rb") as f:
            przed = os.fstat(f.fileno())
            zrodlo = f.read()
            po = os.fstat(f.fileno())
        # Nie podpisuj kodu sygnaturą zmiany wykonanej w trakcie odczytu.
        if ((przed.st_mtime_ns, przed.st_size) != (po.st_mtime_ns, po.st_size)
                or len(zrodlo) != po.st_size):
            raise RuntimeError("wiadomosci.py zmienił się w trakcie odczytu; ponów żądanie")
        kod = compile(zrodlo, plik, "exec")
        nowy = modul is None
        if nowy:
            spec = importlib.util.spec_from_file_location("wiadomosci", plik)
            modul = importlib.util.module_from_spec(spec)
            sys.modules["wiadomosci"] = modul
        # exec może częściowo zmienić istniejący słownik i dopiero potem rzucić.
        # Stara sygnatura nie może wtedy podpisywać częściowo wykonanego kodu,
        # nawet po przywróceniu starego źródła wraz z jego metadanymi.
        modul.__dict__.pop("_retronic_zrodlo_sygnatura", None)
        try:
            exec(kod, modul.__dict__)
        except BaseException:
            if nowy:
                sys.modules.pop("wiadomosci", None)
            raise
        modul._retronic_zrodlo_sygnatura = (po.st_mtime_ns, po.st_size)
        return modul


class Pamiec:
    def __init__(self):
        self.pid = None
        self.mem = None
        self.kandydaci = None  # np.array adresów
        self.poprzednie = None  # np.array wartości
        self.typ = None
        self.adres_gracza = None
        self.regiony_stworow = None
        self.pelny_skan_stworow = 0.0
        self._bufor_stworow = bytearray()
        # Kopiowany razem ze stanem przy hot-reloadzie; obejmuje C zwalniające GIL.
        self._bufor_stworow_zamek = threading.Lock()

    def _pid_z_cache(self):
        """Tania walidacja znanego PID gry (1 odczyt cmdline) zamiast skanu /proc przy każdym RPC.
        Stan (self.pid, self.mem) żyje w instancji, więc przeżywa hot-reload. Zwraca pid albo None."""
        pid = self.pid
        if pid is None or self.mem is None or getattr(self, "_wymus_skan", False):
            return None
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().decode(errors="replace").lower()
        except OSError:
            return None
        if "retronic" in cmd and ".exe" in cmd and "straznik" not in cmd:
            return pid
        return None

    def podlacz(self):
        pid = self._pid_z_cache()
        if pid is not None:
            return pid
        self._wymus_skan = False
        pid = znajdz_gre()
        if pid is None:
            raise RuntimeError("gra nie działa (brak procesu Retronic wśród potomków)")
        if pid != self.pid:
            if self.mem:
                self.mem.close()
            self.mem = open(f"/proc/{pid}/mem", "rb", buffering=0)
            self.pid = pid
            self.kandydaci = None
            self.adres_gracza = None
            self.regiony_stworow = None
            self._regiony_wiek = None
            self._cache = None
        return pid

    def regiony(self):
        wynik = []
        with open(f"/proc/{self.pid}/maps") as f:
            for linia in f:
                czesci = linia.split()
                zakres, prawa = czesci[0], czesci[1]
                nazwa = czesci[5] if len(czesci) > 5 else ""
                if not prawa.startswith("rw") or nazwa.startswith("[v"):
                    continue
                start, koniec = (int(x, 16) for x in zakres.split("-"))
                if start >= LIMIT_ADRESU:
                    continue
                wynik.append((start, min(koniec, LIMIT_ADRESU)))
        return wynik

    def czytaj(self, adres, dlugosc):
        try:
            return os.pread(self.mem.fileno(), dlugosc, adres)
        except OSError as e:
            if e.errno == errno.ESRCH:   # proces gry zniknął: następny RPC robi pełny skan
                self._wymus_skan = True
            return b""

    def wartosci(self, bufor, przesuniecia, typ):
        dtype, rozmiar = TYPY[typ]
        bajty = np.frombuffer(bufor, np.uint8)
        idx = przesuniecia[:, None] + np.arange(rozmiar)
        return bajty[idx].copy().view(dtype).ravel()

    def szukaj(self, wartosc, typ, do=None):
        """Nowe skanowanie: wartość równa `wartosc` albo, gdy podano `do`,
        z zakresu wartosc..do (włącznie)."""
        dtype, rozmiar = TYPY[typ]
        wyrownanie = min(rozmiar, 4)
        adresy, wart = [], []
        for start, koniec in self.regiony():
            bufor = self.czytaj(start, koniec - start)
            if len(bufor) < rozmiar:
                continue
            for przes in range(0, rozmiar, wyrownanie):
                n = (len(bufor) - przes) // rozmiar
                if n <= 0:
                    continue
                tab = np.frombuffer(bufor, dtype, count=n, offset=przes)
                if do is not None:
                    trafienia = np.nonzero((tab >= wartosc) & (tab <= do))[0]
                elif typ.startswith("f"):
                    trafienia = np.nonzero(np.abs(tab - wartosc) < 1e-3)[0]
                else:
                    trafienia = np.nonzero(tab == int(wartosc))[0]
                if len(trafienia):
                    adresy.append(start + przes + trafienia.astype(np.uint64) * rozmiar)
                    wart.append(tab[trafienia])
        self.typ = typ
        self.kandydaci = np.concatenate(adresy) if adresy else np.array([], np.uint64)
        self.poprzednie = np.concatenate(wart) if wart else np.array([], dtype)
        return len(self.kandydaci)

    def biezace(self, adresy=None, typ=None):
        adresy = self.kandydaci if adresy is None else adresy
        typ = typ or self.typ
        dtype, rozmiar = TYPY[typ]
        wynik = np.zeros(len(adresy), dtype)
        ok = np.zeros(len(adresy), bool)
        for start, koniec in self.regiony():
            maska = (adresy >= start) & (adresy + rozmiar <= koniec)
            if not maska.any():
                continue
            lo, hi = int(adresy[maska].min()), int(adresy[maska].max()) + rozmiar
            bufor = self.czytaj(lo, hi - lo)
            if len(bufor) < hi - lo:
                continue
            wynik[maska] = self.wartosci(bufor, (adresy[maska] - lo).astype(np.int64), typ)
            ok[maska] = True
        return wynik, ok

    def zawez(self, warunek, wartosc=None, do=None):
        if self.kandydaci is None:
            raise RuntimeError("najpierw 'szukaj'")
        teraz, ok = self.biezace()
        if warunek == "rowne":
            if self.typ.startswith("f"):
                maska = np.abs(teraz - wartosc) < 1e-3
            else:
                maska = teraz == int(wartosc)
        elif warunek == "zakres":
            maska = (teraz >= wartosc) & (teraz <= do)
        elif warunek == "zmienione":
            maska = teraz != self.poprzednie
        elif warunek == "niezmienione":
            maska = teraz == self.poprzednie
        elif warunek == "wieksze":
            maska = teraz > self.poprzednie
        elif warunek == "mniejsze":
            maska = teraz < self.poprzednie
        else:
            raise RuntimeError(f"nieznany warunek: {warunek}")
        maska &= ok
        self.kandydaci = self.kandydaci[maska]
        self.poprzednie = teraz[maska]
        return len(self.kandydaci)

    def sledz(self, sekundy, odstep):
        """Próbkuje kandydatów przez `sekundy` i zostawia tych, którzy byli
        zarówno zerem, jak i niezerem (np. cel ataku: ID potwora albo 0)."""
        import time
        if self.kandydaci is None:
            raise RuntimeError("najpierw 'szukaj'")
        zero = np.zeros(len(self.kandydaci), bool)
        niezero = np.zeros(len(self.kandydaci), bool)
        zmiany = np.zeros(len(self.kandydaci), np.int32)
        poprzednie = None
        probki = 0
        koniec = time.monotonic() + sekundy
        while time.monotonic() < koniec:
            teraz, ok = self.biezace()
            zero |= ok & (teraz == 0)
            niezero |= ok & (teraz != 0)
            if poprzednie is not None:
                zmiany += (teraz != poprzednie)
            poprzednie = teraz
            probki += 1
            time.sleep(odstep)
        maska = zero & niezero
        self.kandydaci = self.kandydaci[maska]
        self.poprzednie = poprzednie[maska]
        return {"kandydaci": len(self.kandydaci), "probki": probki,
                "zmiany": np.bincount(np.minimum(zmiany[maska], 10)).tolist()}

    def szukaj_bajtow(self, wzorzec, limit=200):
        """Adresy dopasowań wyrażenia regularnego na surowych bajtach."""
        import re
        wz = re.compile(wzorzec, re.S)
        wynik = []
        for start, koniec in self.regiony():
            bufor = self.czytaj(start, koniec - start)
            for m in wz.finditer(bufor):
                wynik.append(hex(start + m.start()))
                if len(wynik) >= limit:
                    return wynik
        return wynik

    @staticmethod
    def _kandydaci_stworow(bufor):
        """Dokładnie te same przesunięcia; natywny filtr albo zgodny NumPy."""
        if CPU_OPTYMALIZACJE and CPU_SKAN:
            return rdzen_skan.kandydaci(bufor)
        return rdzen_skan.kandydaci_numpy(bufor)

    def _czytaj_region_stworow(self, adres, dlugosc):
        """Odczyt tylko dla skanera, pod _bufor_stworow_zamek.

        Nie przechowywać widoku po dekodowaniu regionu. czytaj() pozostaje bytes
        i punktem rozszerzenia dla atrap/podklas. Krótki odczyt nie odsłania ogona.
        """
        if (not CPU_OPTYMALIZACJE or not CPU_SKAN
                or getattr(self.czytaj, "__func__", None) is not _CZYTAJ_PAMIEC
                or not hasattr(os, "preadv")):
            return self.czytaj(adres, dlugosc)
        bufor = self._bufor_stworow
        if len(bufor) < dlugosc:
            # Nowa alokacja zamiast resize: poprzedni widok może jeszcze istnieć
            # jako lokalna zmienna poprzedniego obiegu.
            bufor = self._bufor_stworow = bytearray(dlugosc)
        try:
            n = os.preadv(self.mem.fileno(), [memoryview(bufor)[:dlugosc]], adres)
        except OSError as e:
            if e.errno in (errno.ENOSYS, errno.ENOTSUP):
                return self.czytaj(adres, dlugosc)
            if e.errno == errno.ESRCH:
                self._wymus_skan = True
            return b""
        return memoryview(bufor)[:n]

    # --- skan stworów: wynik w pamięci podręcznej, odświeżany w wątku w tle ---------------
    REGIONY_STWOROW_MAX = 12      # suma regionów ze stworami (najstarsze wypadają)
    OKRES_PELNEGO_PUSTO = 2.0     # s: bez stworów (poza graczami) pełny skan prawie ciągle
    OKRES_PELNEGO_WALKA = 20.0    # s: gdy są stwory, wystarczą szybkie skany + rzadki pełny
    WIEK_PUSTO = 0.5              # s: najstarszy akceptowany wynik, gdy nie ma stworów (pozycja gracza)
    WIEK_STWORY = 0.5             # s: jw., gdy są stwory (pozycje i HP muszą być świeże)
    CZEKANIE_NA_SKAN = 0.6        # s: tyle zapytanie czeka na trwający skan, zanim weźmie starszy cache
    SKANER_BEZCZYNNY = 20.0       # s bez zapytania o stwory i wątek się usypia
    ZAPAS_SKANU = 0.05            # s: skan w tle startuje, gdy wynik ma (limit wieku - średni czas skanu - zapas); 20.10:
                                  # bot pyta 1,5-2,5 razy/s i bierze wynik do 0,5 s, a skaner robił 7-8 skanów/s (4 z 5 do kosza)
    _czas_skanu = 0.1             # s: średnia krocząca czasu szybkiego skanu
    RYTM_WAZNY_S = 2.0            # 21.10 (SPEC_skan_walka_spokoj_1021): tyle s po zapytaniu z polem "rytm" skaner w tle planuje pod ten wiek
    RYTM_ZAKRES = (0.05, 2.0)     # s: dopuszczalny wiek z pola "rytm" (bez pola = WIEK_* jak dotąd)
    _rytmy = None                 # {wiek_s: t_mono ostatniego zapytania z tym "rytm"}; plan = najmniejszy ważny (RYTM_WAZNY_S)

    def _rytm_teraz(self, teraz):
        """Najmniejszy wiek z pola "rytm" zapytań z ostatnich RYTM_WAZNY_S albo None (= WIEK_* jak dotąd)."""
        r = self._rytmy
        if not r:
            return None
        wazne = [w for w, t in list(r.items()) if teraz - t <= self.RYTM_WAZNY_S]
        return min(wazne) if wazne else None
    LOG_SKANU_MAX = 1 << 20
    _cache = None                 # (lista, t_mono, rodzaj, t_pelnego)
    _regiony_wiek = None
    _zamek = None
    _ostatnie_zapytanie = 0.0
    _agregat = None
    _zapytania = None             # [liczba zapytań o stwory, z nich obsłużone z cache] od ostatniego wpisu logu (pomiar 20.10)

    def _log_skanu(self, tekst, wymus=False):
        """Rotowany log pomiarów skanu (logi/rdzen-skan.log, 1 MB + .1). Nigdy nie rzuca."""
        if os.environ.get("RETRONIC_TESTY"):
            return                                   # testy nie zaśmiecają logu pomiarów
        try:
            katalog = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logi")
            plik = os.path.join(katalog, "rdzen-skan.log")
            if os.path.exists(plik) and os.path.getsize(plik) > self.LOG_SKANU_MAX:
                os.replace(plik, plik + ".1")
            with open(plik, "a") as f:
                f.write(time.strftime("%H:%M:%S ") + tekst + "\n")
        except Exception:
            pass

    def _potrzebny_pelny(self, teraz):
        c = self._cache
        if self.regiony_stworow is None or c is None:
            return True
        ma_stwory = any(not s["gracz"] for s in c[0])
        okres = self.OKRES_PELNEGO_WALKA if ma_stwory else self.OKRES_PELNEGO_PUSTO
        return teraz - c[3] > okres

    def _skanuj_stwory(self, pelny):
        """Jeden właściciel bufora aż do publikacji kompletnego wyniku."""
        with self._bufor_stworow_zamek:
            if not (CPU_OPTYMALIZACJE and CPU_SKAN) and self._bufor_stworow:
                self._bufor_stworow = bytearray()  # rollback nie zachowuje dużej alokacji
            return self._skanuj_stwory_pod_zamkiem(pelny)

    def _skanuj_stwory_pod_zamkiem(self, pelny):
        t0 = time.monotonic()
        regiony = self.regiony() if pelny else (self.regiony_stworow or [])
        znalezione, uzyte, kopie = {}, set(), {}
        for start, koniec in regiony:
            bufor = self._czytaj_region_stworow(start, koniec - start)
            for n in self._kandydaci_stworow(bufor):
                if n + RAMKA_STWORA + 1 > len(bufor) or n + POZYCJA_STWORA < 0:
                    continue
                m = NAZWA_STWORA.match(bufor, n)
                if not m:
                    continue
                nazwa = m.group()[:-1]
                rozmiar, pojemnosc = struct.unpack_from("<II", bufor, n + 0x10)
                if rozmiar != len(nazwa) or pojemnosc != 15:
                    continue
                x, y = struct.unpack_from("<II", bufor, n + POZYCJA_STWORA)
                z = bufor[n + POZYCJA_STWORA + 8]
                if x == NIEZNANA_POZYCJA or not (0 < x < 70000 and 0 < y < 70000 and z < 16):
                    continue
                ident = struct.unpack_from("<I", bufor, n - 4)[0]
                uzyte.add((start, koniec))
                if ident in znalezione:
                    # to samo ID w dwóch miejscach pamięci (zwolniony, nieprzepisany obiekt obok żywego): wygrywa ostatni
                    # skan jak dotąd, ale ślad zostaje w polu `kopie` (diagnostyka widm, 19.10; pole opcjonalne, BEZ konsumentów w kodzie)
                    st = znalezione[ident]
                    kopie.setdefault(ident, []).append([st["x"], st["y"], st["z"], st["adres"]])
                znalezione[ident] = {
                    "id": ident,
                    "nazwa": nazwa.decode("latin-1"),
                    "gracz": ident < 0x40000000,
                    "x": x, "y": y, "z": z,
                    "hp": bufor[n + HP_STWORA],
                    "kierunek": struct.unpack_from("<I", bufor, n + KIERUNEK_STWORA)[0],
                    **self._ramka(bufor, n),
                    "adres": hex(start + n),
                }
        for ident, k in kopie.items():
            znalezione[ident]["kopie"] = k
        lista = sorted(znalezione.values(), key=lambda s: s["id"])
        # suma regionów: nie zastępujemy, tylko dokładamy; najstarsze wypychane
        wiek = dict(self._regiony_wiek or {})
        for r in self.regiony_stworow or []:
            wiek.setdefault(r, 0.0)
        nowych = len([r for r in uzyte if r not in wiek])
        for r in uzyte:
            wiek.pop(r, None)
            wiek[r] = t0
        if pelny:
            # regiony z map zmieniają granice (rośnie sterta): stary zakres (start, koniec) przestaje istnieć, ale
            # zostawał w sumie i był skanowany obok nowego (zagnieżdżone zakresy: 12 slotów = 1,2 GB zamiast
            # ~0,2 GB, szybki skan 3,2 s zamiast 0,3 s). Pełny skan zna bieżące mapy: zostaje tylko to, co w nich jest.
            obecne = set(regiony)
            for r in [r for r in wiek if r not in obecne]:
                del wiek[r]
        if len(wiek) > self.REGIONY_STWOROW_MAX:
            for r in sorted(wiek, key=wiek.get)[:len(wiek) - self.REGIONY_STWOROW_MAX]:
                del wiek[r]
        if wiek or pelny:
            self._regiony_wiek = wiek
            self.regiony_stworow = sorted(wiek) or None
        teraz = time.monotonic()
        t_pelnego = teraz if pelny else (self._cache[3] if self._cache else 0.0)
        if pelny:
            self.pelny_skan_stworow = teraz
        self._cache = (lista, teraz, "pelny" if pelny else "szybki", t_pelnego)
        dt = teraz - t0
        if not pelny:
            self._czas_skanu = 0.8 * self._czas_skanu + 0.2 * dt
        if pelny:
            self._log_skanu(f"pelny {dt:.3f}s regiony={len(regiony)} stwory={len(lista)} "
                            f"(poza graczem {sum(1 for s in lista if not s['gracz'])}) "
                            f"nowe_regiony={nowych} suma_regionow={len(self.regiony_stworow or [])}")
        else:
            ag = self._agregat or [t0, 0, 0.0, 0.0]
            ag[1] += 1
            ag[2] += dt
            ag[3] = max(ag[3], dt)
            if teraz - ag[0] >= 10:
                zq = self._zapytania or [0, 0]
                self._log_skanu(f"[{os.environ.get('RETRONIC_ID', '-')}] szybki x{ag[1]} w {teraz - ag[0]:.0f}s "
                                f"srednio={ag[2] / ag[1]:.3f}s max={ag[3]:.3f}s regiony={len(regiony)} "
                                f"zapytania={zq[0]} z_cache={zq[1]}")
                self._zapytania = None
                ag = None
            self._agregat = ag
        return self._cache

    def stwory_info(self, maks_wiek=None, rytm=None):
        """Stwory z pamięci podręcznej (odświeżanej w tle) albo świeżym skanem.
        `rytm` (s, opcjonalne): bot mówi, jak świeżych danych potrzebuje (walka krócej, spokój dłużej); skaner w tle
        planuje pod ten wiek przez RYTM_WAZNY_S. Zwraca (lista, info) gdzie info: skan, wiek_s, wiek_pelnego_s."""
        import threading
        teraz = time.monotonic()
        self._ostatnie_zapytanie = teraz
        if rytm is not None:
            try:
                w = float(rytm)
                if w == w and w not in (float("inf"), float("-inf")):      # NaN/inf z JSON-a ignorujemy
                    lo, hi = self.RYTM_ZAKRES
                    w = round(min(max(w, lo), hi), 3)
                    r = {k: t for k, t in (self._rytmy or {}).items() if teraz - t <= self.RYTM_WAZNY_S}
                    r[w] = teraz
                    self._rytmy = r                   # nowy słownik: wątek skanera czyta spójną kopię
            except (TypeError, ValueError):
                pass
        self._zapytania = self._zapytania or [0, 0]
        self._zapytania[0] += 1
        if self._zamek is None:
            self._zamek = threading.Lock()
        c = self._cache
        if c is not None:
            ma = any(not s["gracz"] for s in c[0])
            limit = maks_wiek if maks_wiek is not None else (self.WIEK_STWORY if ma else self.WIEK_PUSTO)
            if teraz - c[1] <= limit:
                self._zapytania[1] += 1
                return self._odpowiedz_skanu(c, teraz)
        # wątek akurat skanuje: bierzemy co mamy, jeśli nie jest bardzo stare
        # (serwer strażnika jest jednowątkowy: zapytanie czekające na zamek blokuje WSZYSTKIE inne, więc czekamy
        # krótko; skan trwa ~0,3 s, a po nim cache jest świeży)
        if not self._zamek.acquire(blocking=False):
            if c is not None and not self._zamek.acquire(timeout=self.CZEKANIE_NA_SKAN):
                if teraz - c[1] < 2.0:
                    return self._odpowiedz_skanu(c, teraz)
                self._zamek.acquire()
            elif c is None:
                self._zamek.acquire()
        try:
            c = self._cache
            teraz = time.monotonic()
            if c is None or teraz - c[1] > 0.1 or c[0] is None:
                c = self._skanuj_stwory(self._potrzebny_pelny(teraz))
        finally:
            self._zamek.release()
        return self._odpowiedz_skanu(c, time.monotonic())

    @staticmethod
    def _odpowiedz_skanu(c, teraz):
        return c[0], {"skan": c[2], "wiek_s": round(teraz - c[1], 3),
                      "wiek_pelnego_s": round(teraz - c[3], 3) if c[3] else None}

    def stwory(self):
        """Stwory obecne na mapie: id, nazwa, pozycja, % HP, kierunek.
        Szybki skan tylko po regionach, w których były stwory (suma, do 12); pełny skan
        co ~2 s przy braku stworów i co ~20 s w walce. Wątek w tle trzyma wynik świeży."""
        return self.stwory_info()[0]

    def skaner_krok(self):
        """Jeden obieg wątku w tle: skan, jeśli wynik się zestarzał. Zwraca czas snu."""
        if self.mem is None or time.monotonic() - self._ostatnie_zapytanie > self.SKANER_BEZCZYNNY:
            return 0.5
        # skan tylko wtedy, gdy wynik zbliża się do wieku, który zapytania akceptują (WIEK_*), albo gdy czas na pełny
        teraz = time.monotonic()
        c = self._cache
        if c is not None and not self._potrzebny_pelny(teraz):
            ma = any(not s["gracz"] for s in c[0])
            limit = self.WIEK_STWORY if ma else self.WIEK_PUSTO
            r = self._rytm_teraz(teraz)
            if r is not None:
                limit = r                    # 21.10: najmniejszy rytm zamówiony przez bota w ostatnich 2 s (walka / spokój)
            zostalo = c[1] + limit - min(self._czas_skanu, limit / 2) - self.ZAPAS_SKANU - teraz
            if zostalo > 0:
                return min(zostalo, 0.5)
        import threading
        if self._zamek is None:
            self._zamek = threading.Lock()
        with self._zamek:
            teraz = time.monotonic()
            self._skanuj_stwory(self._potrzebny_pelny(teraz))
        return 0.01

    @staticmethod
    def _ramka(bufor, n):
        """Ramki stwora: atakowany = świeci stała ramka (nasz cel), bije_nas = czarna ramka
        chwilowa (stwór uderzył nas w ostatniej ~sekundzie)."""
        def kolor(przes):
            r, g, b, _ = struct.unpack_from("<4f", bufor, n + przes)
            if r < 0.2 and g < 0.2 and b < 0.2:
                return "czarna"
            if r > g + 0.3 and r > b + 0.3:
                return "czerwona"
            if g > r + 0.3 and g > b + 0.3:
                return "zielona"     # podążanie (follow), nie atak
            return "inna"
        stala, chwilowa = bufor[n + RAMKA_STWORA], bufor[n + RAMKA_CHWILOWA]
        wynik = {"atakowany": False, "ramka": None, "bije_nas": bool(chwilowa)}
        if stala:
            wynik["ramka"] = kolor(KOLOR_RAMKI)
            wynik["atakowany"] = wynik["ramka"] in ("czerwona", "inna")
            if wynik["ramka"] == "inna":
                wynik["kolor_ramki"] = [round(x, 3) for x in struct.unpack_from("<4f", bufor, n + KOLOR_RAMKI)]
        elif chwilowa:
            wynik["ramka"] = kolor(KOLOR_RAMKI_CHWILOWEJ)
        return wynik

    def stwor_szybki(self, adres, ident_oczekiwany=None):
        """Stwór spod znanego adresu nazwy (jeden odczyt): id, x, y, z, hp, atakowany, bije_nas.
        None, gdy pod adresem nie ma już tego stwora."""
        n = int(adres, 16)
        # jeden odczyt: od pozycji do bajtu ramki stałej (flagi "atakowany" / "bije_nas" jak w stwory)
        dl_ramki = -POZYCJA_STWORA + RAMKA_STWORA + 1
        bufor = self.czytaj(n + POZYCJA_STWORA, dl_ramki)
        if len(bufor) < -POZYCJA_STWORA + HP_STWORA + 1:
            return None
        ident = struct.unpack_from("<I", bufor, -POZYCJA_STWORA - 4)[0]
        x, y = struct.unpack_from("<II", bufor, 0)
        if ident != int(ident if ident_oczekiwany is None else ident_oczekiwany) or x == NIEZNANA_POZYCJA:
            return None
        odp = {"id": ident, "x": x, "y": y, "z": bufor[8],
               "hp": bufor[-POZYCJA_STWORA + HP_STWORA]}
        if len(bufor) >= dl_ramki:
            try:   # bufor zaczyna się o -POZYCJA_STWORA bajtów za początkiem obiektu: n = -POZYCJA_STWORA
                r = self._ramka(bufor, -POZYCJA_STWORA)
                odp["atakowany"], odp["bije_nas"] = r["atakowany"], r["bije_nas"]
            except Exception:
                pass
        return odp

    def cel_ataku(self):
        """Stwór z czerwoną ramką (cel ataku gracza) albo None."""
        cele = [s for s in self.stwory() if s["atakowany"]]
        if not cele:
            return {"id": None}
        s = cele[0]
        return {"id": s["id"], "nazwa": s["nazwa"], "x": s["x"], "y": s["y"], "z": s["z"],
                "hp": s["hp"], "adres": s["adres"], "ilu": len(cele)}

    def pozycja(self, nazwa):
        """Pozycja postaci o danej nazwie. Adres obiektu jest zapamiętywany,
        więc kolejne odczyty to jedno pread."""
        adres = getattr(self, "adres_postaci", None)
        if adres is not None:
            bufor = self.czytaj(adres + POZYCJA_STWORA, -POZYCJA_STWORA + len(nazwa) + 1)
            if bufor[-POZYCJA_STWORA:] == nazwa.encode("latin-1") + b"\x00":
                x, y = struct.unpack_from("<II", bufor, 0)
                if x != NIEZNANA_POZYCJA:
                    return {"x": x, "y": y, "z": bufor[8]}
        for s in self.stwory():
            if s["nazwa"] == nazwa:
                self.adres_postaci = int(s["adres"], 16)
                return {"x": s["x"], "y": s["y"], "z": s["z"]}
        self.adres_postaci = None
        raise RuntimeError(f"nie widzę postaci {nazwa} (zalogowana?)")

    def pokaz(self, ile):
        if self.kandydaci is None:
            return []
        teraz, _ = self.biezace(self.kandydaci[:ile])
        return [[hex(int(a)), teraz[i].item()] for i, a in enumerate(self.kandydaci[:ile])]

    def blok_gracza(self, adres):
        bufor = self.czytaj(adres, 8 * len(POLA_GRACZA))
        if len(bufor) < 8 * len(POLA_GRACZA):
            return None
        v = np.frombuffer(bufor, "<f8")
        if not maska_gracza(v)[0]:
            return None
        return {pole: int(v[i]) if calkowite(v[i]) else round(float(v[i]), 2)
                for i, pole in enumerate(POLA_GRACZA)}

    def szukaj_gracza(self):
        trafienia = []
        for start, koniec in self.regiony():
            bufor = self.czytaj(start, koniec - start)
            for przes in (0, 4):
                n = (len(bufor) - przes) // 8
                if n < len(POLA_GRACZA):
                    continue
                v = np.frombuffer(bufor, "<f8", count=n, offset=przes)
                for i in np.nonzero(maska_gracza(v))[0]:
                    trafienia.append(start + przes + int(i) * 8)
        return trafienia

    def _wybierz_blok_gracza(self, trafienia):
        """Spośród trafień wybiera żywy blok statystyk. Widmo po relogu (15.10: 1 h 45 min) to zamrożona
        kopia; żywy jest blok, który zmienił się w ostatnich ZYWY_BLOK s (wygrywa ostatnia zmiana).
        Gdy żaden nie zmienił się w tym oknie (postać stoi, pełne HP): najwyższe exp, potem ostatnia
        zmiana, potem obecny adres. Czas zmiany 0.0 = nie widziano zmiany od pierwszego odczytu."""
        teraz = time.monotonic()
        widziane = self.__dict__.setdefault("_gracz_widziane", {})
        bloki = {}
        for a in trafienia:
            b = self.blok_gracza(a)
            if not b:
                continue
            bloki[a] = b
            wart = tuple(b.values())
            poprz = widziane.get(a)
            if poprz is None:
                widziane[a] = (wart, 0.0)
            elif poprz[0] != wart:
                widziane[a] = (wart, teraz)
        if not bloki:
            return None, None
        def klucz(a):
            zm = widziane[a][1]
            exp = bloki[a].get("exp", 0)
            zywy = zm > 0.0 and teraz - zm <= ZYWY_BLOK
            return (zywy, zm if zywy else exp, exp if zywy else zm, a == self.adres_gracza)
        a = max(bloki, key=klucz)
        return a, bloki[a]

    def gracz(self):
        """Blok z cache; pełny skan (ok. 1-2 s, blokuje strażnika) tylko gdy blok jest nieczytelny
        albo od 20 s się nie zmienia (stara kopia po relogu)."""
        teraz = time.monotonic()
        if self.adres_gracza is not None:
            blok = self.blok_gracza(self.adres_gracza)
            if blok:
                wart = tuple(blok.values())
                zm = self.__dict__.get("_gracz_cache_zm")
                if zm is None or zm[0] != wart or zm[2] != self.adres_gracza:
                    self._gracz_cache_zm = (wart, teraz, self.adres_gracza)
                    zm = self._gracz_cache_zm
                zamrozony = teraz - zm[1] > 20.0
                skan_ok = teraz - self.__dict__.get("_gracz_skan_t", 0.0) > 20.0
                if not (zamrozony and skan_ok):
                    return {**blok, "adres": hex(self.adres_gracza)}
        trafienia = self.szukaj_gracza()
        self._gracz_skan_t = time.monotonic()
        if not trafienia:
            self.adres_gracza = None
            raise RuntimeError("nie znalazłem statystyk gracza (zalogowany?)")
        adres, blok = self._wybierz_blok_gracza(trafienia)
        if blok is None:
            self.adres_gracza = None
            raise RuntimeError("nie znalazłem statystyk gracza (zalogowany?)")
        if adres != self.adres_gracza:
            print(f"[rdzen] statystyki gracza: blok {hex(self.adres_gracza) if self.adres_gracza else '-'} "
                  f"-> {hex(adres)} (hp {blok.get('hp')}, exp {blok.get('exp')}; trafień {len(trafienia)})",
                  file=sys.stderr, flush=True)
        self.adres_gracza = adres
        return {**blok, "adres": hex(adres),
                "inne_trafienia": [hex(a) for a in trafienia if a != adres][:5]}

    def kontenery(self, zadanie):
        """Otwarte kontenery z przedmiotami (logika w kontenery.py, przeładowywana po zmianie
        pliku). Błąd modułu daje pustą listę zamiast wywrócenia bota."""
        try:
            import importlib
            import kontenery
            mtime = os.path.getmtime(kontenery.__file__)
            if getattr(self, "kontenery_mtime", None) != mtime:
                if getattr(self, "kontenery_mtime", None) is not None:
                    kontenery = importlib.reload(kontenery)
                self.kontenery_mtime = mtime
            return kontenery.obsluz(self, zadanie)
        except Exception as e:
            return {"kontenery": [], "blad": f"{type(e).__name__}: {e}"}

    def obsluz(self, zadanie):
        pid = self.podlacz()
        cmd = zadanie.get("cmd")
        if cmd == "status":
            return {"pid": pid, "kandydaci": None if self.kandydaci is None else len(self.kandydaci),
                    "typ": self.typ, "regiony": len(self.regiony())}
        if cmd == "szukaj":
            do = zadanie.get("do")
            return {"kandydaci": self.szukaj(float(zadanie["wartosc"]), zadanie.get("typ", "i32"),
                                             None if do is None else float(do))}
        if cmd == "zawez":
            w = zadanie.get("wartosc")
            d = zadanie.get("do")
            return {"kandydaci": self.zawez(zadanie["warunek"], None if w is None else float(w),
                                            None if d is None else float(d))}
        if cmd == "stwor":
            # szybki odczyt jednego stwora spod znanego adresu nazwy (pościg): pozycja i % HP
            return {"stwor": self.stwor_szybki(zadanie["adres"], zadanie.get("id"))}
        if cmd == "poscig":
            # jedna odpowiedź zamiast dwóch (pościg): pozycja gracza + stwór spod adresu (jak "stwor")
            return {"pozycja": self.pozycja(zadanie["nazwa"]),
                    "stwor": self.stwor_szybki(zadanie["adres"], zadanie.get("id"))}
        if cmd == "pozycja":
            return {"pozycja": self.pozycja(zadanie["nazwa"])}
        if cmd == "stwory":
            if zadanie.get("rytm") is None:          # bez pola "rytm" wywołanie jak przed 21.10
                lista, info = self.stwory_info(maks_wiek=zadanie.get("maks_wiek"))
            else:
                lista, info = self.stwory_info(maks_wiek=zadanie.get("maks_wiek"), rytm=zadanie.get("rytm"))
            return {"stwory": lista, **info}
        if cmd == "cel_ataku":
            return self.cel_ataku()
        if cmd == "profil_stworow":
            t0 = time.monotonic()
            regiony = self.regiony_stworow or self.regiony()
            bajty = trafienia = 0
            t_czyt = t_find = 0.0
            for start, koniec in regiony:
                a = time.monotonic(); bufor = self.czytaj(start, koniec - start); t_czyt += time.monotonic() - a
                bajty += len(bufor)
                a = time.monotonic(); trafienia += bufor.count(ZNACZNIK_STWORA); t_find += time.monotonic() - a
            a = time.monotonic(); n = len(self.stwory()); t_calosc = time.monotonic() - a
            return {"regiony": len(regiony), "MB": bajty >> 20, "trafienia": trafienia, "czytanie_s": round(t_czyt, 3),
                    "szukanie_s": round(t_find, 3), "stwory_s": round(t_calosc, 3), "stwory": n}
        if cmd == "bajty":
            return {"adresy": self.szukaj_bajtow(bytes.fromhex(zadanie["hex"]).decode("latin-1").encode("latin-1")
                                                 if "hex" in zadanie else zadanie["regex"].encode("latin-1"),
                                                 int(zadanie.get("limit", 200)))}
        if cmd == "sledz":
            return self.sledz(float(zadanie.get("sekundy", 30)), float(zadanie.get("odstep", 0.1)))
        if cmd == "pokaz":
            return {"lista": self.pokaz(int(zadanie.get("ile", 20)))}
        if cmd == "czytaj":
            adresy = np.array([int(a, 16) for a in zadanie["adresy"]], np.uint64)
            typ = zadanie.get("typ", "i32")
            teraz, ok = self.biezace(adresy, typ)
            return {"wartosci": [teraz[i].item() if ok[i] else None for i in range(len(adresy))]}
        if cmd == "hexdump":
            adres, dl = int(zadanie["adres"], 16), int(zadanie.get("dlugosc", 64))
            return {"hex": self.czytaj(adres, dl).hex()}
        if cmd == "gracz":
            return {"gracz": self.gracz()}
        if cmd == "wiadomosci":
            if not (CPU_OPTYMALIZACJE and CPU_CZAT):
                import importlib
                import wiadomosci
                # Stary reload nie gwarantuje świeżego source względem .pyc.
                # Może też częściowo wykonać moduł i rzucić: unieważnij PRZED nim.
                # Ponowne włączenie musi jeszcze raz podpisać wykonany kod.
                wiadomosci.__dict__.pop("_retronic_zrodlo_sygnatura", None)
                importlib.reload(wiadomosci)
                return wiadomosci.obsluz(self, zadanie)
            wiadomosci = _modul_wiadomosci()
            self.wiadomosci_sygnatura = wiadomosci._retronic_zrodlo_sygnatura
            return wiadomosci.obsluz(self, zadanie)
        if cmd == "kontenery":
            return self.kontenery(zadanie)
        raise RuntimeError(f"nieznane polecenie: {cmd}")


_CZYTAJ_PAMIEC = Pamiec.czytaj  # nie omijaj czytaj nadpisanego przez podklasę/atrapę

_TOKEN = object()  # nowy przy każdym (prze)ładowaniu modułu; stary wątek skanera sam się kończy


def _petla_skanera(stan, token):
    while stan.get("skaner_token") is token:
        sen = 1.0
        try:
            p = stan.get("pamiec")
            if p is not None and hasattr(p, "skaner_krok"):
                sen = p.skaner_krok()
        except Exception as e:  # błąd skanu nie może zabić wątku ani strażnika
            try:
                Pamiec()._log_skanu(f"BLAD skanera {type(e).__name__}: {e}")
            except Exception:
                pass
            sen = 1.0
        time.sleep(sen)


def _uruchom_skaner(stan):
    if stan.get("skaner_token") is _TOKEN and stan.get("skaner_watek") and stan["skaner_watek"].is_alive():
        return
    import threading
    stan["skaner_token"] = _TOKEN
    w = threading.Thread(target=_petla_skanera, args=(stan, _TOKEN), daemon=True)
    stan["skaner_watek"] = w
    w.start()


def obsluz(stan, zadanie):
    """Wejście ze strażnika. Po przeładowaniu modułu przenosi stan do nowej klasy."""
    try:
        _uruchom_skaner(stan)
    except Exception:
        pass
    stary = stan.get("pamiec")
    if type(stary) is not Pamiec:
        nowy = Pamiec()
        if stary is not None:
            nowy.__dict__.update(stary.__dict__)
        stan["pamiec"] = nowy
    return stan["pamiec"].obsluz(zadanie)
