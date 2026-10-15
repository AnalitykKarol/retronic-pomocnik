"""Wiadomość do gracza, który wraca na nasz spot albo zabiera nam moby (SPEC dane_tibia/SPEC_czat_spot_1015.md).

Czysta logika, bez wejścia/wyjścia: unikanie.py podaje graczy w UNIKANIE_PROMIEN i moby pominięte przez gracza,
mózg pyta o kandydata, wysyła tekst z puli i zgłasza odpowiedzi gracza. Przechodzień (jedno krótkie spotkanie)
nie dostaje nic. Sygnały (per nick):
 - S1 powroty: >= CZAT_SPOT_SPOTKAN osobnych spotkań (każde >= SPOTKANIE_MIN_S) w CZAT_SPOT_OKNO_MIN min;
 - S2 siedzi: ciągła obecność >= CZAT_SPOT_CIAGLE_MIN min;
 - S3 zabiera moby: >= CZAT_SPOT_ZABRANE różnych mobów pominiętych przez niego w ZABRANE_OKNO_S, przy obecności
   łącznie >= S3_OBECNOSC_S (troll goniący przechodnia to nie S3).
Limity: jeden nick raz na CZAT_SPOT_NICK_MIN min, wszyscy razem raz na GLOBALNY_S. Odpowiedź gracza:
prowokacja (bot/makro/polecenie/zgłoszenie) = tylko dymek; inaczej najwyżej CZAT_SPOT_ODPOWIEDZI odpowiedzi modelu.
Stałe czyta z `konf` przy każdym wywołaniu (pokrętła z na_zywo.json działają od razu)."""
import random
import re
import time

SPOTKANIE_MIN_S = 20.0        # krótsze spotkanie = przechodzień, nie liczy się do S1
ZABRANE_OKNO_S = 600.0        # S3: okno liczenia zabranych mobów
S3_OBECNOSC_S = 60.0          # S3: gracz był przy nas łącznie >= tyle s w tym oknie (troll goniący przechodnia to nie S3)
GLOBALNY_S = 600.0            # najwyżej jedna wiadomość na tyle sekund (do wszystkich)
ROZMOWA_S = 600.0             # tyle po naszej wiadomości odpowiedź gracza należy do tej rozmowy
WIDOK_X, WIDOK_Y = 7, 5       # ekran klienta: gracz musi być widoczny w chwili wysyłki

TEKSTY = {
    "S1": ("hey, im hunting here for a while",
           "yo, this spot is taken atm, sorry",
           "hi mate, im on this spot, can u find another one pls"),
    "S3": ("pls dont take my {mob}, im hunting here",
           "hey, pls dont interrupt, im hunting here"),
}
TEKSTY["S2"] = TEKSTY["S1"]

# odpowiedź, na którą bot NIE odpisuje (Karol przejmuje): pytanie o bota/makro/AFK, polecenie, zgłoszenie, GM
PROWOKACJA = re.compile(
    r"\bbot|\bmacro|\bmakro|\bafk\b|\bscript|\bcheat|\bai\b|\bgpt|\bchat ?gpt|\bignore\b|\bforget\b|\bsay\b|\btype\b|"
    r"\bwrite\b|\brepeat\b|\binstruction|\bprompt|\breport|\bgm\b|\bcm\b|\bban\b|\bpolice|\bprove\b|\bproof\b|"
    r"\breal person|\bhuman\b|\brespond\b|\bnapisz|\bpowiedz|\bzglos|\bzgłos",
    re.IGNORECASE)


def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


class CzatSpot:
    def __init__(self, konf, zegar=time.time, losuj=random.choice):
        self.konf, self.zegar, self.losuj = konf, zegar, losuj
        self.spotkania = {}       # nick -> [[od, ost], ...] (ostatnie = bieżące)
        self.zabrane = {}         # nick -> {id moba: czas}
        self.mob = {}             # nick -> nazwa ostatniego zabranego moba
        self.widoczni = set()     # nicki na ekranie (ostatnia obserwacja)
        self.wyslane = {}         # nick -> czas naszej wiadomości
        self.ost_wyslanie = float("-inf")
        self.odpowiedzi = {}      # nick -> ile razy odpisaliśmy na jego odpowiedź

    def _k(self, nazwa, domyslna):
        return getattr(self.konf, nazwa, domyslna)

    def wlaczone(self):
        return bool(self._k("CZAT_SPOT_AKTYWNY", 0))

    # --- obserwacja (z unikanie.py) ---

    def obserwuj(self, gracze, poz, t=None, znikl_s=10.0):
        """gracze: [{"nazwa","x","y","odl"}] w UNIKANIE_MAX (to samo piętro, bez nas). Liczy spotkania w
        UNIKANIE_PROMIEN; przerwa > znikl_s zaczyna nowe spotkanie."""
        t = self.zegar() if t is None else t
        r = self._k("UNIKANIE_PROMIEN", 9)
        self.widoczni = {g["nazwa"] for g in gracze
                         if abs(g["x"] - poz[0]) <= WIDOK_X and abs(g["y"] - poz[1]) <= WIDOK_Y}
        for g in gracze:
            if g["odl"] > r:
                continue
            lista = self.spotkania.setdefault(g["nazwa"], [])
            if lista and t - lista[-1][1] <= znikl_s:
                lista[-1][1] = t
            else:
                lista.append([t, t])
        okno = max(self._k("CZAT_SPOT_OKNO_MIN", 20), self._k("CZAT_SPOT_CIAGLE_MIN", 5)) * 60.0
        for nick in list(self.spotkania):
            self.spotkania[nick] = [s for s in self.spotkania[nick] if t - s[1] <= okno]
            if not self.spotkania[nick]:
                del self.spotkania[nick]

    def zabrany(self, nick, mob_id, nazwa_moba=None, t=None):
        """Mob, którego bot nie bierze, bo stoi tuż przy graczu `nick` (on go bije)."""
        t = self.zegar() if t is None else t
        d = self.zabrane.setdefault(nick, {})
        d[mob_id] = t
        for k in [k for k, v in d.items() if t - v > ZABRANE_OKNO_S]:
            del d[k]
        if nazwa_moba:
            self.mob[nick] = nazwa_moba

    # --- decyzja ---

    def sygnal(self, nick, t=None):
        """"S3" / "S2" / "S1" / None dla jednego gracza (bez limitów wysyłki)."""
        t = self.zegar() if t is None else t
        sp = self.spotkania.get(nick, [])
        zab = [v for v in self.zabrane.get(nick, {}).values() if t - v <= ZABRANE_OKNO_S]
        obecnosc = sum(s[1] - max(s[0], t - ZABRANE_OKNO_S) for s in sp if s[1] >= t - ZABRANE_OKNO_S)
        if len(zab) >= self._k("CZAT_SPOT_ZABRANE", 2) and obecnosc >= S3_OBECNOSC_S:
            return "S3"
        if sp and t - sp[-1][1] <= 1e-9 and sp[-1][1] - sp[-1][0] >= self._k("CZAT_SPOT_CIAGLE_MIN", 5) * 60.0:
            return "S2"
        okno = self._k("CZAT_SPOT_OKNO_MIN", 20) * 60.0
        liczne = [s for s in sp if t - s[1] <= okno and (s[1] - s[0] >= SPOTKANIE_MIN_S)]
        if len(liczne) >= self._k("CZAT_SPOT_SPOTKAN", 3):
            return "S1"
        return None

    def kandydat(self, t=None):
        """(nick, sygnał) gracza, do którego wolno teraz napisać, albo None. Tylko gracz widoczny na ekranie."""
        t = self.zegar() if t is None else t
        if not self.wlaczone() or t - self.ost_wyslanie < GLOBALNY_S:
            return None
        nick_s = self._k("CZAT_SPOT_NICK_MIN", 60) * 60.0
        for nick in sorted(self.widoczni):
            if t - self.wyslane.get(nick, float("-inf")) < nick_s:
                continue
            s = self.sygnal(nick, t)
            if s:
                return nick, s
        return None

    def tekst(self, nick, sygnal):
        mob = (self.mob.get(nick) or "monsters").casefold()
        mob = mob if mob.endswith("s") else mob + "s"
        return self.losuj(TEKSTY[sygnal]).format(mob=mob)

    def wyslano(self, nick, t=None):
        """Wiadomość poszła: limity i nowe liczenie dowodów dla tego gracza."""
        t = self.zegar() if t is None else t
        self.wyslane[nick] = self.ost_wyslanie = t
        self.odpowiedzi[nick] = 0
        self.spotkania.pop(nick, None)
        self.zabrane.pop(nick, None)

    # --- odpowiedź gracza ---

    def w_rozmowie(self, nick, t=None):
        t = self.zegar() if t is None else t
        return t - self.wyslane.get(nick, float("-inf")) <= ROZMOWA_S

    def odpowiedz(self, nick, tekst, t=None):
        """Gracz odpisał po naszej wiadomości. -> "dymek" (prowokacja: nie odpisujemy, Karol przejmuje),
        "model" (jedna odpowiedź modelu, licznik rośnie), "cisza" (limit odpowiedzi) albo None (to nie ta rozmowa)."""
        t = self.zegar() if t is None else t
        if not self.w_rozmowie(nick, t):
            return None
        if PROWOKACJA.search(tekst or ""):
            self.odpowiedzi[nick] = 10 ** 6       # do końca okna już nic do niego
            return "dymek"
        if self.odpowiedzi.get(nick, 0) >= self._k("CZAT_SPOT_ODPOWIEDZI", 1):
            return "cisza"
        self.odpowiedzi[nick] = self.odpowiedzi.get(nick, 0) + 1
        return "model"
