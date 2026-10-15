"""Powiadomienia na pulpicie (notify-send, app-name "Retronic", Omarchy/mako).

powiadom(tytul, tresc, pilnosc="normal", klucz=None) nigdy nie rzuca wyjątku i nie blokuje bota
(notify-send idzie w osobnym wątku z timeoutem procesu 2 s).
Limity: max 1 powiadomienie na klucz na 60 s, max 20/h łącznie (critical poza limitem godzinowym).
Wyłączniki: RETRONIC_POWIADOMIENIA=0 albo plik pomocnik/cisza. W testach (RETRONIC_TESTY) funkcja
modułowa nic nie wysyła; klasę Powiadamiacz testuje się z atrapą `uruchom`.
Tylko stdlib."""
import os
import re
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

KATALOG = Path(__file__).resolve().parent
CISZA = KATALOG / "cisza"
KLUCZ_S = 60
LIMIT_H = 20
TIMEOUT_S = 2
PODSUMOWANIE_S = 300
OBCY_S = 300
TYTUL_MAX, TRESC_MAX = 80, 400
PILNOSCI = ("low", "normal", "critical")


def _notify_send(arg):
    subprocess.run(["notify-send", *arg], timeout=TIMEOUT_S, capture_output=True)


class Powiadamiacz:
    def __init__(self, uruchom=_notify_send, zegar=time.time, cisza=CISZA, watek=True):
        self.uruchom, self.zegar, self.cisza, self.watek = uruchom, zegar, Path(cisza), watek
        self.po_kluczach = {}          # klucz -> czas ostatniego powiadomienia
        self.godzina = deque()         # czasy powiadomień nie-critical
        self.blokada = threading.Lock()

    def wylaczone(self):
        if os.environ.get("RETRONIC_POWIADOMIENIA", "").strip() == "0":
            return True
        try:
            return self.cisza.exists()
        except OSError:
            return True

    def powiadom(self, tytul, tresc="", pilnosc="normal", klucz=None):
        """-> True, gdy powiadomienie poszło (do wysłania), False gdy odrzucone/wyłączone."""
        try:
            if self.wylaczone():
                return False
            if pilnosc not in PILNOSCI:
                pilnosc = "normal"
            t = self.zegar()
            klucz = klucz or tytul
            with self.blokada:
                if t - self.po_kluczach.get(klucz, float("-inf")) < KLUCZ_S:
                    return False
                while self.godzina and t - self.godzina[0] >= 3600:
                    self.godzina.popleft()
                if pilnosc != "critical":
                    if len(self.godzina) >= LIMIT_H:
                        return False
                    self.godzina.append(t)
                self.po_kluczach[klucz] = t
                if len(self.po_kluczach) > 500:
                    self.po_kluczach = {k: v for k, v in self.po_kluczach.items() if t - v < KLUCZ_S}
            arg = ["-a", "Retronic", "-u", pilnosc, "-t", "20000" if pilnosc == "critical" else "8000",
                   str(tytul)[:TYTUL_MAX], re.sub(r"\s+", " ", str(tresc))[:TRESC_MAX]]
            if self.watek:
                threading.Thread(target=self._wyslij, args=(arg,), daemon=True).start()
            else:
                self._wyslij(arg)
            return True
        except Exception:
            return False

    def _wyslij(self, arg):
        try:
            self.uruchom(arg)
        except Exception:
            pass


_domyslny = Powiadamiacz()

# 14.10 (Karol): dymki tylko, gdy coś jest nie tak, plus start i stop bota. Przechodzą klucze z ZAWSZE
# (start, stop, niskie HP, obcy gracz, gracz pisze, GM, dojście) i wszystko "critical"; reszta (podsumowanie
# co 5 min, brak jedzenia, wnioski analityka, pokrętła) jest cicha. RETRONIC_POWIADOMIENIA=wszystkie: dawne zachowanie.
ZAWSZE = ("start", "stop", "hp", "obcy:", "czat:", "gm", "dojscie")


def istotne(tytul, pilnosc="normal", klucz=None):
    if os.environ.get("RETRONIC_POWIADOMIENIA", "").strip() == "wszystkie":
        return True
    return pilnosc == "critical" or str(klucz or tytul).startswith(ZAWSZE)


def powiadom(tytul, tresc="", pilnosc="normal", klucz=None):
    if os.environ.get("RETRONIC_TESTY"):
        return False
    if not istotne(tytul, pilnosc, klucz):
        return False
    return _domyslny.powiadom(tytul, tresc, pilnosc, klucz)


# --- zdarzenia bota ---------------------------------------------------------------

def start(trasa, potwory=None):
    powiadom("Bot ruszył", f"Trasa: {trasa}, potwory: {', '.join(potwory) if potwory else 'wszystkie'}",
             klucz="start")


def stop(powod):
    powiadom("Bot zatrzymany", powod, "critical", klucz="stop")


_obcy = {}              # nick -> czas ostatniego powiadomienia
_brak_jedzenia = [False]
BRAK_JEDZENIA_S = 3600        # s: powiadomienie "brak jedzenia" najwyżej raz na godzinę (nie jest awarią)
HP_S = 300                    # s: powiadomienie "niskie HP" najwyżej raz na 5 min
_ostatnie = {}                # klucz -> czas ostatniego powiadomienia z z_logu


def _odstep(klucz, s, t):
    """True, gdy od ostatniego powiadomienia o tym kluczu minęło >= s (i zapisuje czas)."""
    if t - _ostatnie.get(klucz, float("-inf")) < s:
        return False
    _ostatnie[klucz] = t
    return True
RE_OBCY = re.compile(r"ALARM: gracz na ekranie: (.+)")
RE_HP = re.compile(r"ALARM: niskie HP (\d+)%")
RE_START = re.compile(r"Start: trasa (\d+) pkt.*potwory=(.*)$")
STOPY = (("Zatrzymano (plik STOP)", "STOP ręczny (plik STOP)"), ("Przerwano", "Przerwano (Ctrl+C / SIGTERM)"),
         ("Koniec.", "Koniec (limit okrążeń/czasu)"), ("Upłynął limit czasu", "Koniec: upłynął limit czasu"),
         ("Wykonano zadaną liczbę okrążeń", "Koniec: wykonano okrążenia"),
         ("Za dużo błędów z rzędu", "Błąd: za dużo błędów z rzędu, bot przerwał"),
         ("Trzy punkty z rzędu nieosiągalne", "Błąd: trzy punkty trasy z rzędu nieosiągalne"))


def z_logu(linia, zegar=time.time):
    """Hak cavebot.HAKI_LOGU: rozpoznaje w liniach logu alarmy, ucieczkę, brak jedzenia, start i stop."""
    try:
        m = RE_OBCY.search(linia)
        if m:
            t = zegar()
            for nick in [n.strip() for n in m[1].split(",") if n.strip()]:
                if t - _obcy.get(nick, float("-inf")) >= OBCY_S:
                    _obcy[nick] = t
                    powiadom("Obcy gracz na ekranie", nick, klucz=f"obcy:{nick}")
            return
        m = RE_HP.search(linia)
        if m:
            if _odstep("hp", HP_S, zegar()):
                powiadom("Niskie HP, ucieczka", f"HP {m[1]}%, postać ucieka", "critical", klucz="hp")
            return
        if "Zjedzono: nic (brak jedzenia)" in linia:
            # jedno powiadomienie na godzinę, zwykłe (nie critical): bot gra dalej, dopóki HP nie spadnie
            _brak_jedzenia[0] = True
            if _odstep("jedzenie", BRAK_JEDZENIA_S, zegar()):
                powiadom("Brak jedzenia", "Postać jest głodna, a w plecaku nie ma jedzenia (bot gra dalej)",
                         "normal", klucz="jedzenie")
            return
        if linia.startswith("Zjedzono:"):
            _brak_jedzenia[0] = False
            return
        m = RE_START.match(linia)
        if m:
            start(f"{m[1]} pkt", None if m[2].startswith("wszystkie") else [m[2].strip("[]'\" ")])
            return
        for poczatek, powod in STOPY:
            if linia.startswith(poczatek):
                stop(powod)
                return
    except Exception:
        pass


def czat(autor, tekst, prywatna):
    powiadom("Gracz pisze do bota" + (" (priv)" if prywatna else ""), f"{autor}: {tekst}", "critical",
             klucz=f"czat:{autor}:{hash(tekst)}")


def czat_obok(autor, tekst):
    """Gracz pisze na Default, ale nie do nas: zwykły dymek, najwyżej raz na minutę od jednego gracza."""
    powiadom("Ktoś pisze obok", f"{autor}: {tekst}", klucz=f"czat:obok:{autor}")


def czat_spot(autor, tekst, odpowiedz=False, pilne=False):
    """czat_spot: bot napisał do gracza na spocie albo gracz mu odpisał (pilne = prowokacja, Karol przejmuje)."""
    tytul = (f"{autor} odpisał" + (" — przejmij" if pilne else "")) if odpowiedz else f"Napisałem do {autor}"
    powiadom(tytul, tekst if odpowiedz else f"(wraca/przeszkadza na spocie) {tekst}", "critical" if pilne else "normal",
             klucz=f"czat:spot:{autor}:{hash(tekst)}")


def alarm_gm(powod):
    powiadom("ALARM GM", powod, "critical", klucz="gm")


# --- podsumowanie co 5 minut (z agregatów telemetrii, bez modelu) -----------------

class Podsumowanie:
    def __init__(self, zegar=time.time, wyslij=None, co=PODSUMOWANIE_S):
        self.zegar, self.co = zegar, co
        self.wyslij = wyslij or (lambda t, c: powiadom(t, c, "low", klucz="podsumowanie"))
        self.start = self.zegar()
        self.nastepne = self.start + co
        self.exp0 = None

    def tick(self, tele, g=None):
        try:
            t = self.zegar()
            if g and self.exp0 is None and g.get("exp") is not None:
                self.exp0 = g["exp"]
            if t < self.nastepne:
                return False
            self.nastepne = t + self.co
            self.wyslij("Retronic: ostatnie 5 min", self.tekst(tele, g, t))
            return True
        except Exception:
            return False

    def tekst(self, tele, g, t):
        import telemetria  # noqa: PLC0415
        rek = tele.okno(self.co)
        ag = telemetria.agreguj(rek, self.co)
        probki = [r for r in rek if r["typ"] == "probka"]
        zab = sum(1 for r in rek if r["typ"] == "zabicie")
        odp = sum(1 for r in rek if r["typ"] == "odpuszczenie")
        hp = [r["hp"] for r in probki if r.get("hp") is not None]
        jedz, poprz = 0, None
        for r in probki:
            if r["stan"] == "JEDZENIE" and poprz != "JEDZENIE":
                jedz += 1
            poprz = r["stan"]
        loot = ag["loot"]
        czesci = [f"zabicia {zab}", f"loot ok {loot.get('ok', 0)}/brak_okna {loot.get('brak_okna', 0)}",
                  f"odpuszczenia {odp}", f"HP min {min(hp) if hp else '?'}%", f"jedzenie {jedz}x"]
        jm = sum(1 for r in rek if r["typ"] == "jedzenie_mana")
        if jm:
            czesci.append(f"jedzenie z braku regeneracji many {jm}x")
        jw = sum(1 for r in rek if r["typ"] == "jedzenie_walka")
        if jw:
            czesci.append(f"jedzenie w walce (HP nie rosło) {jw}x")
        if g and g.get("mana") is not None and g.get("max_mana"):
            czesci.append(f"mana {int(g['mana'])}/{int(g['max_mana'])} ({100 * g['mana'] / g['max_mana']:.0f}%)"
                          + (f", ML {'on' if g.get('ml_aktywny') else 'off'}" if "ml_aktywny" in g else "")
                          + (f" rzuty {g['ml_rzuty']}" if g.get("ml_rzuty") else ""))
        if g and self.exp0 is not None and g.get("exp") is not None and t - self.start >= 300:
            czesci.append(f"exp/h {round((g['exp'] - self.exp0) * 3600 / (t - self.start))}")
        try:
            lin = telemetria.linia_dobicia(tele.dobicie(self.co))
            if lin:
                czesci.append(lin)
        except Exception:
            pass
        return ", ".join(czesci)
