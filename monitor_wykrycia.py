#!/usr/bin/env python3
"""Monitor „czy widać, że to bot” (Karol 22.10): osobny terminal, TYLKO ODCZYT, nic nie wysyła do gry.

Co 15 s dla każdej instancji z działającym botem czyta przyrost logu mozg-stdout i telemetrii, a ze strażnika
(komenda "wiadomosci", bez skanu) nowe wpisy czatu. Liczy w oknie 10 min sygnały, które gracz widzi jako bota:
  zawieszki (D3), kręcenie się / wahadło (S4), stanie w miejscu (S3), bicie w ścianę (krok nie ruszył),
  złe piętro, porażki tras, utknięcia, ucieczki, alarmy, STOP;
  obcy gracz w zasięgu wzroku (z telemetrii) i jak długo patrzy; czat od obcego (zwłaszcza „bot”, „?”, „afk”);
  GM/CM w pobliżu albo w czacie.
Ryzyko: OK / UWAGA / RYZYKO. RYZYKO = obcy patrzy, a bot w tym czasie robi coś „botowego”, albo czat/GM.
Przy RYZYKU dymek `notify-send` (najwyżej raz na 5 min na postać i rodzaj).
23.10: (a) wypowiedzi NPC (rozmowa handlowa/bankowa, odpowiedź NPC na „hi”) NIE są „czatem od obcych” i nie podnoszą RYZYKA:
  gracz widziany w telemetrii nigdy nie jest NPC; potem lista imion NPC serwera (dane_tibia/serwer74/npc_pelne.json + NPC_DODATKOWE);
  potem struktura rozmowy (nadawca, który odpowiedział na >= 2 kolejne własne wypowiedzi postaci w Default, jest NPC przez godzinę);
  (b) sygnał „duch w kliencie”: ten sam cel z „klików bez efektu” >= 3 razy w 5 min = jeden dymek critical na postać na 15 min.

  python3 -I monitor_wykrycia.py            tabela co 15 s (Ctrl+C kończy)
  python3 -I monitor_wykrycia.py --raz      jeden przebieg, wypisz i wyjdź
Lista instancji jest skanowana na nowo w KAŻDYM przebiegu (22.10: nowa instancja albo zmiana id bez restartu monitora), a źródłem
logu i telemetrii jest zawsze najnowszy plik (mozg-stdout-*.log powstaje przy każdym starcie bota). W tabeli jest każda instancja
z działającym botem ALBO z sesją gry (strażnik), nie tylko z botem.
Log zdarzeń: instancje/_wspolne/logi/monitor-wykrycia-RRRRMMDD.log. Cofnięcie: usunąć ten plik i monitor_wykrycia.sh."""
import json
import os
import re
import socket
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

KAT = Path(__file__).resolve().parent
sys.path.insert(0, str(KAT))
import instancja  # noqa: E402

OKNO_S = 600.0                 # okno liczenia sygnałów
ODSWIEZ_S = 15.0
DYMEK_CO_S = 300.0
WLASNE = {"invincible", "dawajkesh", "wydra", "kolanosh", "kutangen", "bober qrwa", "jointoramix", "mastafian"}
NIE_GRACZE = re.compile(r"growth|fungal", re.I)          # wpisy „gracz” z telemetrii, które nie są graczami
GM = re.compile(r"^(gm|cm|god|tutor|gamemaster)\b|gamemaster", re.I)
KANALY_PUBLICZNE = {"server log", "trade", "game-chat", "help", "advertising", "loot channel", "rl-chat",
                    "english chat", "world chat", "npcs"}
NPC_PLIK = Path("dane_tibia") / "serwer74" / "npc_pelne.json"
NPC_DODATKOWE = {"ebenizer", "mirabell", "beatrice", "alexander", "bonifacius", "xodet", "gorn", "suzy", "frodo"}
                                # imiona z trasy/serwis_*.json i logów serwisu 22–23.10; zapas, gdy brak npc_pelne.json
NPC_ODP_MIN = 2                 # tyle własnych wypowiedzi, na które ten sam nadawca odpowiada, uznaje go za NPC
NPC_ODP_RESET_S = 300.0         # przerwa dłuższa niż to zeruje licznik odpowiedzi nadawcy
NPC_NAUCZONY_S = 3600.0         # jak długo nauczony z rozmowy NPC jest uznawany za NPC
DUCH = re.compile(r"\[ATAK\] \d+ klików bez efektu w (.+) id(\S+?), Escape")
DUCH_OKNO_S = 300.0
DUCH_MIN = 3
DUCH_DYMEK_CO_S = 900.0
CZAT_ALARM = re.compile(r"\bbot|makro|macro|afk|cave ?bot|\?|hello|hej|siema|elo|yo\b|hi\b|cze", re.I)

WZORY = [  # (klucz, regex na linii logu, waga „botowości”)
    ("zawieszka", re.compile(r"D3 zawieszka (\d+) s"), 2),
    ("kreci", re.compile(r"S4 kręci się"), 2),
    ("stoi", re.compile(r"S3 stoi w"), 1),
    ("sciana", re.compile(r"debug: krok \w+ z .* nie ruszył"), 0.25),
    ("pietro", re.compile(r"złe piętro"), 1),
    ("trasa", re.compile(r"S1 porażka trasy|NIEUDANE|utknięcie"), 1),
    ("klik", re.compile(r"klik bez skutku"), 1),
    ("ucieczka", re.compile(r"\[UCIECZKA\]"), 0),
    ("alarm", re.compile(r"ALARM"), 0),
    ("stop", re.compile(r"Zatrzymano \(plik STOP\)"), 0),
    ("zabicie", re.compile(r"zabity na"), 0),
]
ETYKIETY = {"zawieszka": "zawiesz", "kreci": "kręci", "stoi": "stoi", "sciana": "ściana", "pietro": "piętro",
            "trasa": "trasa", "klik": "klik", "ucieczka": "ucieczka", "alarm": "alarm", "stop": "STOP"}


def teraz():
    return time.time()


_NPC_CACHE = {}


def imiona_npc(kat=None):
    """Imiona NPC (casefold): baza serwera + NPC_DODATKOWE. Brak albo błędny plik = same NPC_DODATKOWE (monitor nie pada)."""
    plik = (kat or KAT) / NPC_PLIK
    if plik not in _NPC_CACHE:
        nazwy = set(NPC_DODATKOWE)
        try:
            with open(plik, encoding="utf-8") as f:
                nazwy |= {str(n["nazwa"]).casefold() for n in json.load(f)["npc"]}
        except (OSError, ValueError, KeyError, TypeError):
            pass
        _NPC_CACHE[plik] = nazwy
    return _NPC_CACHE[plik]


NICKI_WLASNE = {}               # id instancji -> nick postaci z profil.json (Gebelish gra jako „Geblish”, nie ma go w WLASNE)


def minuta_czasu(czas):
    """„HH:MM” z klienta -> minuta doby albo None."""
    m = re.match(r"\s*(\d{1,2}):(\d{2})", czas or "")
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def _notify(tytul, tresc):
    try:
        subprocess.run(["notify-send", "-u", "critical", "-a", "Monitor botów", tytul, tresc[:300]],
                       timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


class Postac:
    def __init__(self, id_, kat=None):
        self.id = id_
        self.s = instancja.sciezki(id_, instancja.runtime(f"/run/user/{os.getuid()}"), katalog=kat or KAT)
        self.plik_logu = None
        self.off_logu = 0
        self.plik_tele = None
        self.off_tele = 0
        self.zdarz = deque()            # (t, klucz, waga, tekst)
        self.obcy = {}                  # nick -> [pierwszy_t, ostatni_t, min_odl]
        self.czat = deque(maxlen=20)    # (t, autor, tekst)
        self.czat_nr = None
        self.czat_epoka = None
        self.ostatnie = deque(maxlen=6)
        self.dymki = {}
        self.ost_zabicie = None
        self.poz = None
        self.hp = None
        self.bot = False
        self.sesja = False              # działa strażnik (klient gry) tej instancji, bot niekoniecznie
        self.kat = kat or KAT
        self.nick = self._nick()
        if self.nick:
            NICKI_WLASNE[id_] = self.nick.casefold()
        self.czeka_odp = None           # minuta doby własnej wypowiedzi w Default bez odpowiedzi (-1 = czas nieznany)
        self.odpowiedzi = {}            # nadawca (casefold) -> [liczba odpowiedzi na własne wypowiedzi, czas ostatniej]
        self.npc_nauczone = {}          # nadawca (casefold) -> czas nauczenia z rozmowy
        self.duchy = deque()            # (t, nazwa celu, końcówka id) z „klików bez efektu”
        self.duch_dymek = 0.0

    def _nick(self):
        try:
            return (json.loads((Path(self.s.stan) / "profil.json").read_text(encoding="utf-8")).get("postac") or "").strip()
        except (OSError, ValueError, AttributeError):
            return ""

    # --- źródła -------------------------------------------------------------------------------
    def _najnowszy(self, wzor):
        try:
            pliki = sorted(Path(self.s.logi).glob(wzor), key=lambda p: p.stat().st_mtime)
        except OSError:
            return None
        return pliki[-1] if pliki else None

    def _czytaj_od(self, plik, off_attr):
        try:
            with open(plik, "rb") as f:
                f.seek(getattr(self, off_attr))
                dane = f.read()
                setattr(self, off_attr, f.tell())
        except OSError:
            return []
        return dane.decode("utf-8", "replace").splitlines()

    def _przyrost(self, plik, off_attr, plik_attr):
        """Nowe linie z najnowszego pliku. Zmiana pliku (nowy start bota = nowy mozg-stdout-*.log, nowa doba telemetrii):
        najpierw dokończ ogon poprzedniego, potem przejdź na nowy od początku (albo ostatnich ~200 KB)."""
        if plik is None:
            return []
        linie = []
        stary = getattr(self, plik_attr)
        if stary is not None and stary != plik:
            linie += self._czytaj_od(stary, off_attr)
        if stary != plik:
            setattr(self, plik_attr, plik)
            try:
                setattr(self, off_attr, max(0, plik.stat().st_size - 200_000))   # nowy plik: ostatnie ~200 KB
            except OSError:
                return linie
        return linie + self._czytaj_od(plik, off_attr)

    def czytaj_log(self):
        dzien = time.strftime("%Y-%m-%d ")
        for l in self._przyrost(self._najnowszy("mozg-stdout-*.log"), "off_logu", "plik_logu"):
            m = re.match(r"(\d\d:\d\d:\d\d) (.*)", l)
            if not m:
                continue
            try:
                t = time.mktime(time.strptime(dzien + m.group(1), "%Y-%m-%d %H:%M:%S"))
            except ValueError:
                continue
            if t > teraz() + 60:
                t -= 86400
            tekst = m.group(2)
            d = DUCH.search(tekst)
            if d:                                   # nie zamienia wzorców poniżej: to osobny sygnał („duch w kliencie”)
                self.duchy.append((t, d.group(1), d.group(2)))
            for klucz, rx, waga in WZORY:
                r = rx.search(tekst)
                if r:
                    if klucz == "zawieszka":
                        waga = 2 if int(r.group(1)) >= 30 else 1
                    if klucz == "zabicie":
                        self.ost_zabicie = max(self.ost_zabicie or 0, t)
                    self.zdarz.append((t, klucz, waga, tekst[:110]))
                    if klucz != "zabicie" and klucz != "sciana":
                        self.ostatnie.append(f"{m.group(1)} {tekst[:95]}")
                    break

    def czytaj_tele(self):
        for l in self._przyrost(self._najnowszy("telemetria-*.jsonl"), "off_tele", "plik_tele"):
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if r.get("typ") != "probka":
                continue
            t = r.get("t", teraz())
            self.poz, self.hp = r.get("poz"), r.get("hp")
            for s in r.get("stwory", []):
                n = s.get("n", "")
                if not s.get("gracz") or n.lower() in WLASNE or NIE_GRACZE.search(n) or s.get("odl", 0) == 0:
                    continue
                o = self.obcy.setdefault(n, [t, t, s.get("odl", 99)])
                if t - o[1] > 120:                 # wrócił po przerwie: nowe spotkanie
                    o[0] = t
                o[1] = t
                o[2] = min(o[2], s.get("odl", 99)) if t - o[1] < 30 else s.get("odl", 99)

    def czytaj_czat(self):
        z = {"cmd": "wiadomosci", "limit": 30}
        if self.czat_nr is not None:
            z.update(od=self.czat_nr, epoka=self.czat_epoka)
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as so:
                so.settimeout(3)
                so.connect(str(self.s.gniazdo))
                so.sendall((json.dumps(z) + "\n").encode())
                odp = json.loads(so.makefile("rb").readline())
        except (OSError, ValueError):
            return
        if not odp.get("ok"):
            return
        pierwszy = self.czat_nr is None
        self.czat_nr, self.czat_epoka = odp.get("znacznik"), odp.get("epoka")
        if pierwszy:
            return                              # start: tylko znacznik, bez starej historii
        self.przyjmij_czat(odp.get("wiadomosci", []))

    def wlasne_nicki(self):
        return WLASNE | set(NICKI_WLASNE.values())

    def widziany_jako_gracz(self, klucz):
        return any(n.casefold() == klucz for n in self.obcy)

    def jest_npc(self, autor, t=None):
        """Czy nadawca to NPC. Kolejność: (1) gracz widziany w telemetrii (okno OKNO_S) nigdy nie jest NPC — NPC-e nie
        występują w telemetrii (sprawdzone na wszystkich plikach 20–23.10), a gracz obok mówi w Default;
        (2) imię z bazy NPC serwera; (3) nauczony ze struktury rozmowy (`przyjmij_czat`)."""
        k = autor.casefold()
        t = teraz() if t is None else t
        if self.widziany_jako_gracz(k):
            return False
        if k in imiona_npc(self.kat):
            return True
        return t - self.npc_nauczone.get(k, float("-inf")) <= NPC_NAUCZONY_S

    def _ucz_sie_rozmowy(self, lista, wlasne, t):
        """Struktura rozmowy: własna wypowiedź postaci w Default, a zaraz po niej (ta sama lub następna minuta klienta)
        odpowiedź nadawcy w Default albo w zakładce o jego imieniu (NPC odpowiada prywatnie w zakładce nazwanej jego
        imieniem). Nadawca, który odpowiedział na NPC_ODP_MIN kolejnych własnych wypowiedzi, jest NPC. Ogłoszenia Trade
        i inne kanały publiczne rozmowy nie przerywają. Czat gracza obok nie uczy: gracz w telemetrii jest wykluczony."""
        for w in lista:
            autor = (w.get("autor") or w.get("nadawca") or "").strip()
            kanal = (w.get("kanal") or "").lower()
            if not autor or not kanal or kanal in KANALY_PUBLICZNE:
                continue
            minuta = minuta_czasu(w.get("czas"))
            if autor.lower() in wlasne:
                if kanal == "default":
                    self.czeka_odp = -1 if minuta is None else minuta
                continue
            k = autor.casefold()
            if self.czeka_odp is None or not (kanal == "default" or kanal == k):
                continue
            if minuta is not None and self.czeka_odp >= 0 and (minuta - self.czeka_odp) % 1440 > 1:
                self.czeka_odp = None            # odpowiedź po minucie: to nie jest odpowiedź na tę wypowiedź
                continue
            self.czeka_odp = None
            lic, ost = self.odpowiedzi.get(k, [0, t])
            lic = 1 if t - ost > NPC_ODP_RESET_S else lic + 1
            self.odpowiedzi[k] = [lic, t]
            if lic >= NPC_ODP_MIN and not self.widziany_jako_gracz(k):
                self.npc_nauczone[k] = t

    def przyjmij_czat(self, lista, t=None):
        """Wiadomości ze strażnika -> `self.czat` (tylko Default i prywatne zakładki, bez NPC, bez własnych postaci)."""
        t = teraz() if t is None else t
        wlasne = self.wlasne_nicki()
        self._ucz_sie_rozmowy(lista, wlasne, t)            # najpierw cała porcja, żeby pierwsza wypowiedź nowego NPC też odpadła
        for w in lista:
            autor = (w.get("autor") or w.get("nadawca") or "").strip()
            tekst = (w.get("tekst") or "").strip()
            kanal = (w.get("kanal") or "").lower()
            if not autor or autor.lower() in wlasne or not kanal or kanal in KANALY_PUBLICZNE:
                continue                        # tylko Default (gracze obok) i prywatne zakładki; kanał nieznany = pomiń
                                                # (22.10: invincible ma kanały nieprzypisane, Trade wyglądał jak czat obok)
            if self.jest_npc(autor, t):
                continue                        # 23.10: rozmowa z NPC (handel, bank, „hi”) to nie obcy gracz
            self.czat.append((t, autor, tekst))
            self.ostatnie.append(f"{time.strftime('%H:%M:%S')} CZAT {autor}: {tekst[:80]}")

    def duch(self):
        """(nazwa, końcówka id, liczba) celu z >= DUCH_MIN „klików bez efektu” w ostatnich DUCH_OKNO_S s albo None.
        Klient widzi potwora, którego serwer nie ma (23.10 wydra: Troll id..1363, 6x w 4 min): pomaga tylko restart klienta."""
        granica = teraz() - DUCH_OKNO_S
        self.duchy = deque(x for x in self.duchy if x[0] >= granica)
        licz = {}
        for _, nazwa, id_ in self.duchy:
            if id_ != "?":                           # cel bez id: nie wiadomo, czy ten sam
                licz[(nazwa, id_)] = licz.get((nazwa, id_), 0) + 1
        if not licz:
            return None
        (nazwa, id_), n = max(licz.items(), key=lambda x: x[1])
        return (nazwa, id_, n) if n >= DUCH_MIN else None

    def odswiez(self):
        self.bot = bool(instancja.procesy(r"(mozg|cavebot)\.py", id_=self.id))
        self.sesja = self.bot or bool(instancja.procesy(r"(^|[ /])straznik\.py", id_=self.id))
        self.czytaj_log()
        self.czytaj_tele()
        self.czytaj_czat()
        granica = teraz() - OKNO_S
        while self.zdarz and self.zdarz[0][0] < granica:
            self.zdarz.popleft()
        for n in [n for n, o in self.obcy.items() if teraz() - o[1] > OKNO_S]:
            del self.obcy[n]

    # --- ocena --------------------------------------------------------------------------------
    def liczniki(self):
        c = {}
        for _, k, _, _ in self.zdarz:
            c[k] = c.get(k, 0) + 1
        return c

    def ocena(self):
        """(poziom, powody): poziom 0 OK, 1 UWAGA, 2 RYZYKO."""
        c = self.liczniki()
        t0 = teraz()
        botowosc = sum(w for t, k, w, _ in self.zdarz if t0 - t <= 180)
        patrza = {n: o for n, o in self.obcy.items() if t0 - o[1] <= 20}
        dlugo = {n: o for n, o in patrza.items() if o[1] - o[0] >= 60}
        powody, poziom = [], 0
        gm = [n for n in patrza if GM.search(n)] + [a for _, a, _ in self.czat if GM.search(a)]
        if gm:
            return 2, [f"GM/CM: {', '.join(sorted(set(gm)))}"]
        czat5 = [(a, x) for t, a, x in self.czat if t0 - t <= 300]
        if czat5:
            pyt = [(a, x) for a, x in czat5 if CZAT_ALARM.search(x)]
            poziom = 2 if pyt else 1
            a, x = (pyt or czat5)[-1]
            powody.append(f"czat {a}: „{x[:40]}”")
        if patrza and botowosc >= 3:
            poziom = 2
            powody.append(f"{', '.join(patrza)} patrzy, a bot: " + self._co_botowe(180))
        elif dlugo:
            poziom = max(poziom, 1)
            n, o = next(iter(dlugo.items()))
            powody.append(f"{n} obok od {int(o[1] - o[0])} s")
        zle = [(t, x) for t, k, _, x in self.zdarz if k == "pietro" and t0 - t <= 60]
        if zle:
            m = re.search(r"trwa_s=([\d.]+)", zle[-1][1])
            if m and float(m.group(1)) >= 30:
                poziom = 2                      # 22.10: dawajkesh wpadł na z10 i stał tam niezauważony
                powody.insert(0, f"złe piętro od {float(m.group(1)):.0f} s (wpadł?)")
        if c.get("zawieszka", 0) >= 3 or c.get("kreci", 0) >= 3 or c.get("sciana", 0) >= 40:
            poziom = max(poziom, 1)
            powody.append("dużo zacięć: " + self._co_botowe(OKNO_S))
        if self.bot and self.ost_zabicie and t0 - self.ost_zabicie > 900:
            poziom = max(poziom, 1)
            powody.append(f"bez zabicia {int((t0 - self.ost_zabicie) / 60)} min")
        if c.get("stop") and not self.bot:
            poziom = max(poziom, 1)
            powody.append("bot zatrzymany")
        d = self.duch()
        if d:
            poziom = max(poziom, 1)                 # sam dymek „duch” idzie osobną drogą (dymek_duch), bez RYZYKA
            powody.append(f"duch w kliencie: {d[0]} id{d[1]} {d[2]}x")
        return poziom, powody

    def _co_botowe(self, okno):
        t0 = teraz()
        c = {}
        for t, k, w, _ in self.zdarz:
            if t0 - t <= okno and w > 0:
                c[k] = c.get(k, 0) + 1
        return ", ".join(f"{ETYKIETY.get(k, k)} {n}" for k, n in sorted(c.items(), key=lambda x: -x[1])) or "-"


# --- prezentacja -------------------------------------------------------------------------------------
KOLOR = {0: "\033[32m", 1: "\033[33m", 2: "\033[1;31m"}
NAZWA = {0: "OK", 1: "UWAGA", 2: "RYZYKO"}
RESET = "\033[0m"


def dymek(p, poziom, powody):
    if poziom < 2:
        return
    klucz = powody[0].split(":")[0] if powody else "?"
    if teraz() - p.dymki.get(klucz, 0) < DYMEK_CO_S:
        return
    p.dymki[klucz] = teraz()
    _notify(f"Ryzyko: {p.id}", "\n".join(powody))


def dymek_duch(p):
    """Jeden dymek critical (tytuł + 2 linie) „duch w kliencie”, najwyżej raz na DUCH_DYMEK_CO_S na postać. Bez akcji w grze.
    Zwraca treść dymka albo None."""
    d = p.duch()
    if not d or teraz() - p.duch_dymek < DUCH_DYMEK_CO_S:
        return None
    p.duch_dymek = teraz()
    nick = p.nick or p.id
    tresc = (f"{nick}: klient widzi potwora, którego nie da się bić (duch) — restart klienta: zatrzymaj bota, "
             f"sesja_gry zamknij/start, zaloguj\nCel: {d[0]} id{d[1]}, {d[2]}x „klików bez efektu” w 5 min")
    _notify(f"Duch w kliencie: {nick}", tresc)
    dopisz_log(f"{p.id} DUCH {nick}: {d[0]} id{d[1]} {d[2]}x")
    return tresc


def dopisz_log(linia):
    kat = KAT / "instancje" / "_wspolne" / "logi"
    try:
        kat.mkdir(parents=True, exist_ok=True)
        with open(kat / time.strftime("monitor-wykrycia-%Y%m%d.log"), "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {linia}\n")
    except OSError:
        pass


def zapisz(p, poziom, powody, ost):
    if poziom == 0 or (poziom, tuple(powody)) == ost.get(p.id):
        return
    ost[p.id] = (poziom, tuple(powody))
    dopisz_log(f"{p.id} {NAZWA[poziom]} {' | '.join(powody)}")


def tabela(postacie):
    w = [f"\033[2J\033[HMonitor botów (tylko odczyt)  {time.strftime('%H:%M:%S')}   okno {int(OKNO_S / 60)} min, "
         f"odświeżanie {int(ODSWIEZ_S)} s, Ctrl+C kończy\n"]
    w.append(f"{'postać':<11} {'bot':<4} {'ocena':<7} {'zab.':>5} {'zaw':>4} {'kręci':>5} {'stoi':>4} {'ścian':>5} "
             f"{'trasa':>5} {'obcy':>4}  powody")
    for p in postacie:
        poziom, powody = p.ocena()
        c = p.liczniki()
        obcy = sum(1 for o in p.obcy.values() if teraz() - o[1] <= 20)
        zab = f"{int((teraz() - p.ost_zabicie) / 60)}m" if p.ost_zabicie else "-"
        w.append(f"{p.id:<11} {'tak' if p.bot else ('gra' if p.sesja else 'nie'):<4} {KOLOR[poziom]}{NAZWA[poziom]:<7}{RESET} {zab:>5} "
                 f"{c.get('zawieszka', 0):>4} {c.get('kreci', 0):>5} {c.get('stoi', 0):>4} {c.get('sciana', 0):>5} "
                 f"{c.get('trasa', 0) + c.get('pietro', 0):>5} {obcy:>4}  {'; '.join(powody)[:110]}")
    w.append("\nObcy gracze w zasięgu (teraz):")
    for p in postacie:
        for n, o in p.obcy.items():
            if teraz() - o[1] <= 20:
                w.append(f"  {p.id}: {n}, obok {int(o[1] - o[0])} s, najbliżej {o[2]} pól")
    w.append("\nOstatnie zdarzenia:")
    for p in postacie:
        for e in list(p.ostatnie)[-3:]:
            w.append(f"  [{p.id}] {e}")
    return "\n".join(w)


def instancje(kat=None):
    ids = []
    try:
        wpisy = sorted(((kat or KAT) / "instancje").iterdir())
    except OSError:
        return ids
    for d in wpisy:
        if d.is_dir() and not d.name.startswith("_") and (d / "profil.json").exists():
            ids.append(d.name)
    return ids


def synchronizuj(postacie, kat=None):
    """Zgodność słownika postaci z katalogiem instancji (co przebieg): nowa instancja trafia do monitora od razu, zniknięta
    (zmiana id, archiwizacja) odpada. Zwraca (dodane, usuniete)."""
    kat = kat or KAT
    ids = instancje(kat)
    dodane, usuniete = [], []
    for i in ids:
        if i not in postacie:
            try:
                postacie[i] = Postac(i, kat)
            except ValueError:               # id spoza a-z0-9_- : instancja.py i tak by nie wystartowała
                continue
            dodane.append(i)
    for i in [i for i in postacie if i not in ids]:
        del postacie[i]
        usuniete.append(i)
    return dodane, usuniete


def przebieg(postacie, kat=None):
    """Jeden przebieg: synchronizacja listy, odczyt każdej instancji, lista aktywnych (bot, sesja gry albo zdarzenia w oknie)."""
    synchronizuj(postacie, kat)
    aktywne = []
    for p in postacie.values():
        try:
            p.odswiez()
        except Exception as e:  # noqa: BLE001 — monitor nie może paść przez jedną instancję
            p.ostatnie.append(f"{time.strftime('%H:%M:%S')} błąd monitora: {e!r}"[:120])
        if p.bot or p.sesja or p.zdarz:
            aktywne.append(p)
    return aktywne


def main():
    raz = "--raz" in sys.argv
    postacie = {}
    ost = {}
    while True:
        aktywne = przebieg(postacie)
        for p in aktywne:
            poziom, powody = p.ocena()
            dymek(p, poziom, powody)
            dymek_duch(p)
            zapisz(p, poziom, powody, ost)
        print(tabela(aktywne), flush=True)
        if raz:
            return
        time.sleep(ODSWIEZ_S)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
