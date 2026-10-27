"""STÓJ: obcy gracz blisko -> wylogowanie (24.10, Karol 22:08: „wydra niech robi runy tu, gdzie stoi, a jak ktoś do niej podejdzie
z graczy, to niech się wyloguje").

Działa TYLKO przy włączonym STÓJ (stoj.py) i pokrętle `STOJ_GRACZ_WYLOGUJ_ODL` > 0 (pola, Czebyszew, to samo piętro; 0 = wyłączone,
domyślnie 0). Poza STÓJ cavebot tego nie woła, więc zachowanie zwykłych trybów jest bez zmian.

Trzy kroki (cavebot.py: `_stoj_obcy_tick`, wywoływane w `tick` PRZED blokiem „obcy gracz"):
  1. `obcy_gracze` + `Wykrywacz`: kto jest „obcym graczem" i czy to nie jednorazowy błędny odczyt. Obcy = wpis stwora z `gracz`,
     który NIE jest: naszą postacią (nick z profil.json każdej instancji i nick bieżącej), NPC (serwis_akcje.NPC_NAZWY, chyba że ma
     czaszkę/PK), wpisem-widmem (widma.py) ani martwym (hp <= 0). Potwierdzenie: `POTW_ODCZYTY` (2) kolejne odczyty z odstępem
     >= `POTW_ODSTEP_S` (0,5 s: dwa obiegi z jednego cache skanu to jeden odczyt), ten sam nick w obu. Zniknięcie z zasięgu między
     odczytami albo przerwa dłuższa niż `POTW_LUKA_S` (5 s) zeruje licznik. Razem ok. 1 s od pierwszego zobaczenia.
  2. `Epizod`: po potwierdzeniu decyzja jest PODJĘTA (obcy może odejść, ale ktoś nas zobaczył). Bot przestaje robić runy/akcje i
     próbuje wylogować Ctrl+L TĄ SAMĄ ścieżką co `logowanie.py wyloguj`: bramka `logowanie.spokoj` (bez walki: zero potworów w
     odległości <= 2, nikt nas nie bije ani nie jest atakowany, HP nie spada), Ctrl+L co 4 s (pierwszy po 2 s), po każdym
     zrzut `logowanie.stan_ekranu`. Bez spokoju: bot nie naciska klawisza i walczy/leczy jak dotąd (obieg idzie dalej w cavebot).
     PZ-lock (Ctrl+L bez skutku) = ekran nadal „gra", więc ponawiamy. Limit `LIMIT_S` (300 s, jak wyloguj.sh) -> poddanie, log,
     powiadomienie, cisza `CISZA_PO_PODDANIU_S` (60 s) i potem możliwy nowy epizod, jeśli obcy nadal blisko.
  3. Po wylogowaniu (ekran logowania): STOP + STOP_RECZNY w katalogu stanu instancji (to samo, co zostaje po `stoj.sh off` ze startu
     świeżego i po `zatrzymaj.sh`: „Karol gra", nadzorca/relog/zaloguj.sh pomijają postać), znacznik `stoj_gracz_wylogowany.json`
     (diagnoza; NIE `wylogowany.json`, bo ten uruchamia kolejkę relogów), proces bota się kończy (`Cavebot.wylogowany`), a
     odłączony pomocnik `stoj_obcy.py zamknij <pid>` czeka na koniec procesu i woła `logowanie.py wyloguj --reczny-ok`
     (ekran już logowania = tylko `sesja_gry.py zamknij`; autoReconnect klienta bez tego logowałby postać z powrotem w < 60 s).

Nigdy logowanie: żaden kod tu nie klika „Login"/„Ok" ani nie woła zaloguj.sh. Powrót postaci = decyzja Karola (usunięcie STOP_RECZNY /
zwykły start przez okno lub `uruchom.sh`).

Moduł nie importuje bota; wejścia, zegar i porty są wstrzykiwane (testy/test_stoj_obcy.py). CLI (tylko dla pomocnika):
  python3 -I stoj_obcy.py zamknij <pid>
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

KAT = Path(__file__).resolve().parent

POTW_ODCZYTY = 2                 # tyle kolejnych odczytów z obcym potwierdza go
POTW_ODSTEP_S = 0.5              # min. odstęp czasu między dwoma odczytami liczonymi do potwierdzenia
POTW_LUKA_S = 5.0                # dłuższa przerwa między odczytami = licznik od nowa (odczyty muszą być „kolejne")
LIMIT_S = 300.0                  # jak logowanie.LIMIT_WYLOGUJ_S
CTRL_L_PIERWSZY_S = 2.0          # jak logowanie.CTRL_L_PIERWSZY_S
CTRL_L_CO_S = 4.0                # jak logowanie.CTRL_L_CO_S
EKRAN_CO_S = 0.5                 # zrzut ekranu po Ctrl+L najczęściej co tyle (grim kosztuje ok. 0,1-0,3 s)
CISZA_PO_PODDANIU_S = 60.0       # po poddaniu (limit czasu / zgon) tyle bez nowego epizodu
CZEKAJ_NA_KONIEC_BOTA_S = 45.0   # pomocnik: tyle czekamy, aż proces bota się skończy, zanim zamkniemy sesję
ZNACZNIK = "stoj_gracz_wylogowany.json"
EKRANY_LOGOWANIA = ("enter_game", "character_list")


# --- kto jest obcym graczem -------------------------------------------------------------------------------------------

def nicki_naszych(katalog_instancji=None):
    """Zbiór nicków (casefold) z instancje/*/profil.json (`postac`). Błędy plików pomijane."""
    kat = Path(katalog_instancji) if katalog_instancji else KAT / "instancje"
    wynik = set()
    try:
        pliki = list(kat.glob("*/profil.json"))
    except OSError:
        return wynik
    for p in pliki:
        try:
            n = (json.loads(p.read_text(encoding="utf-8")).get("postac") or "").strip()
        except (OSError, ValueError, AttributeError):
            continue
        if n:
            wynik.add(n.casefold())
    return wynik


def _czaszka(s):
    return bool(s.get("czaszka") or s.get("skull") or s.get("pk"))


def obcy_gracze(lista, poz, nick, nasze, npc, odl):
    """-> [(odległość, nazwa)] obcych graczy w odległości Czebyszewa <= odl na piętrze `poz[2]`, od najbliższego.
    odl <= 0 = wyłączone (pusta lista). Pomija: własny nick, `nasze` (zbiór casefold), `npc` (zbiór casefold; gracz z czaszką/PK
    nigdy nie jest NPC), wpisy-widma (`widmo`), martwych (hp <= 0) i wpisy bez współrzędnych."""
    if not odl or odl <= 0:
        return []
    wlasny = (nick or "").casefold()
    wynik = []
    for s in lista or ():
        if not isinstance(s, dict) or not s.get("gracz") or s.get("widmo"):
            continue
        nazwa = str(s.get("nazwa") or "")
        k = nazwa.casefold()
        if not k or k == wlasny or k in nasze:
            continue
        if k in npc and not _czaszka(s):
            continue
        try:
            if int(s["z"]) != int(poz[2]):
                continue
            d = max(abs(int(s["x"]) - int(poz[0])), abs(int(s["y"]) - int(poz[1])))
        except (KeyError, TypeError, ValueError):
            continue
        hp = s.get("hp")
        if isinstance(hp, (int, float)) and not isinstance(hp, bool) and hp <= 0:
            continue
        if d <= odl:
            wynik.append((d, nazwa))
    return sorted(wynik)


class Wykrywacz:
    """Potwierdzenie obcego: `krok(teraz, obcy)` (obcy = wynik `obcy_gracze`) -> (odległość, nazwa) najbliższego POTWIERDZONEGO albo None.
    Potwierdzony = ten sam nick w `potw` kolejnych odczytach, każdy >= `odstep_s` po poprzednim, bez przerwy dłuższej niż `luka_s`
    i bez odczytu „pusto" pomiędzy."""

    def __init__(self, potw=POTW_ODCZYTY, odstep_s=POTW_ODSTEP_S, luka_s=POTW_LUKA_S):
        self.potw, self.odstep_s, self.luka_s = potw, odstep_s, luka_s
        self.reset()

    def reset(self):
        self.licznik = {}        # casefold nazwy -> liczba kolejnych odczytów
        self.t_ost = None        # czas ostatniego liczonego odczytu

    def krok(self, teraz, obcy):
        if not obcy:
            self.reset()
            return None
        if self.t_ost is not None and teraz - self.t_ost > self.luka_s:
            self.reset()
        if self.t_ost is not None and teraz - self.t_ost < self.odstep_s:
            return None              # ten sam skan / za szybko: to nie jest nowy odczyt
        teraz_nazwy = {n.casefold() for _, n in obcy}
        self.licznik = {k: self.licznik.get(k, 0) + 1 for k in teraz_nazwy}
        self.t_ost = teraz
        for d, n in obcy:
            if self.licznik.get(n.casefold(), 0) >= self.potw:
                return d, n
        return None


# --- wylogowanie ---------------------------------------------------------------------------------------------------------

class Epizod:
    """Jedna próba wylogowania po potwierdzonym obcym. Wszystko wstrzykiwane:
      ctrl_l()            naciśnięcie Ctrl+L (logowanie.PortZywy.ctrl_l)
      ekran()             -> "gra" | "enter_game" | "character_list" | "zgon" | "nieznany" (logowanie.stan_ekranu(port)[0])
      spokoj(hp_poprzednie) -> (bool, powód, hp) (logowanie.spokoj nad danymi bota)
    `krok(teraz)` -> "niespokojnie" (bez klawisza: bot walczy/leczy jak dotąd) | "ctrl_l" (naciśnięto) | "czeka" |
                     "wylogowano" | "zgon" | "limit"."""

    def __init__(self, t0, kto, odl, ctrl_l, ekran, spokoj, log=print, limit_s=LIMIT_S):
        self.t0, self.kto, self.odl = t0, kto, odl
        self.ctrl_l, self.ekran, self.spokoj, self.log = ctrl_l, ekran, spokoj, log
        self.limit_s = limit_s
        self.proby = 0
        self.nast = t0                       # najwcześniejszy czas kolejnego Ctrl+L
        self.hp_pop = None
        self.ekran_t = float("-inf")
        self.ekran_ost = None                # wynik ostatniego zrzutu (używany, gdy zrzut był < EKRAN_CO_S temu)
        self.bez_spokoju_od = None
        self.log_t = float("-inf")

    def krok(self, teraz):
        if teraz - self.t0 > self.limit_s:
            self.log(f"STÓJ obcy: limit {self.limit_s:g} s, nie udało się wylogować ({self.proby} prób Ctrl+L); wracam do stania.")
            return "limit"
        ok, powod, hp = self.spokoj(self.hp_pop)
        self.hp_pop = hp
        if not ok:
            if self.bez_spokoju_od is None:
                self.bez_spokoju_od = teraz
            if teraz - self.log_t >= 15.0:
                self.log_t = teraz
                self.log(f"STÓJ obcy: {self.kto} blisko, ale brak spokoju ({powod}): nie wylogowuję w walce, ponawiam "
                         f"(od {teraz - self.bez_spokoju_od:.0f} s).")
            return "niespokojnie"
        self.bez_spokoju_od = None
        if self.proby and teraz - self.ekran_t >= EKRAN_CO_S:
            self.ekran_t = teraz
            e = self.ekran_ost = self.ekran()
            if e in EKRANY_LOGOWANIA:
                self.log(f"STÓJ obcy: wylogowano po {self.proby} Ctrl+L ({e}).")
                return "wylogowano"
            if e == "zgon":
                self.log("STÓJ obcy: zgon w trakcie wylogowania: stop.")
                return "zgon"
        else:
            e = self.ekran_ost if self.proby else None
        if teraz >= self.nast:
            if self.proby == 0:
                e = self.ekran_ost = self.ekran()              # pierwszy raz: tylko gdy ekran = gra (nieznany = czekamy, bez klawiszy)
                self.ekran_t = teraz
                if e in EKRANY_LOGOWANIA:
                    self.log(f"STÓJ obcy: klient już na ekranie {e}, nic do naciśnięcia.")
                    return "wylogowano"
                if e == "zgon":
                    return "zgon"
            if e in (None, "gra"):
                self.ctrl_l()
                self.proby += 1
                self.nast = teraz + (CTRL_L_PIERWSZY_S if self.proby <= 1 else CTRL_L_CO_S)
                if self.proby % 15 == 1:
                    self.log(f"STÓJ obcy: Ctrl+L (próba {self.proby}), obcy {self.kto} w {self.odl} polach.")
                return "ctrl_l"
        return "czeka"


def zapisz_koniec(stan, kto, odl, nick, poz, teraz=None, zrodlo="stoj_obcy"):
    """STOP + STOP_RECZNY w katalogu stanu instancji i znacznik diagnostyczny. Nie rzuca; -> słownik znacznika (klucz `blad` przy błędzie)."""
    teraz = time.time() if teraz is None else teraz
    stan = Path(stan)
    d = {"czas": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(teraz)), "ts": round(teraz, 1), "nick": nick, "obcy": kto,
         "odleglosc": odl, "poz": list(poz[:3]) if poz else None, "pid": os.getpid(), "zrodlo": zrodlo,
         "opis": "obcy gracz blisko w trybie STÓJ: wylogowano; STOP + STOP_RECZNY (Karol gra), bez relogu"}
    bledy = []
    for nazwa in ("STOP", "STOP_RECZNY"):
        try:
            (stan / nazwa).touch()
        except OSError as e:
            bledy.append(f"{nazwa}: {e!r}")
    try:
        tmp = stan / (ZNACZNIK + f".tmp{os.getpid()}")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, stan / ZNACZNIK)
    except OSError as e:
        bledy.append(f"{ZNACZNIK}: {e!r}")
    if bledy:
        d["blad"] = "; ".join(bledy)
    return d


def uruchom_zamkniecie(id_, pid=None, kat=KAT):
    """Odłączony pomocnik: czeka na koniec procesu bota `pid` i zamyka sesję istniejącą ścieżką wylogowania. -> Popen albo None."""
    pid = os.getpid() if pid is None else pid
    env = dict(os.environ)
    env["RETRONIC_ID"] = id_ or ""
    try:
        import instancja  # noqa: PLC0415
        logi = Path(instancja.S.stan) / "logi"
        logi.mkdir(parents=True, exist_ok=True)
        wy = open(logi / "stoj-obcy-zamknij.log", "ab")
    except Exception:                     # noqa: BLE001
        wy = subprocess.DEVNULL
    try:
        return subprocess.Popen([sys.executable, "-I", str(Path(kat) / "stoj_obcy.py"), "zamknij", str(pid)], cwd=str(kat), env=env,
                                stdin=subprocess.DEVNULL, stdout=wy, stderr=subprocess.STDOUT, start_new_session=True)
    except OSError:
        return None


def _proces_zyje(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        stan = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        return stan != "Z"
    except (OSError, IndexError):
        return True


def zamknij(pid, kat=KAT, czekaj_s=CZEKAJ_NA_KONIEC_BOTA_S, zyje=_proces_zyje, uruchom=None, spij=time.sleep, zegar=time.monotonic):
    """Pomocnik: czeka do `czekaj_s` na koniec `pid`, potem `logowanie.py wyloguj --reczny-ok` (z STOP_RECZNY i bez bota; ekran logowania =
    tylko zamknięcie sesji). -> kod wyjścia wyloguj."""
    koniec = zegar() + czekaj_s
    while zyje(pid) and zegar() < koniec:
        spij(0.5)
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} stoj_obcy zamknij: bot {pid} {'zakończony' if not zyje(pid) else 'nadal działa (limit czekania)'}; "
          "wyloguj.sh --reczny-ok", flush=True)
    uruchom = uruchom or (lambda cmd: subprocess.call(cmd, cwd=str(kat), timeout=420))
    try:
        return uruchom([sys.executable, "-I", str(Path(kat) / "logowanie.py"), "wyloguj", "--reczny-ok"])
    except subprocess.TimeoutExpired:
        return 124


def main(argv):
    if len(argv) == 2 and argv[0] == "zamknij" and argv[1].isdigit():
        return zamknij(int(argv[1]))
    print("użycie: stoj_obcy.py zamknij <pid>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
