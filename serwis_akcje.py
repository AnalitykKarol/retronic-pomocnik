"""Akcje serwisu miasta na żywej grze (serwis.py): rozmowa z NPC, depo w dwóch poziomach, układ okien plecaków.

Wszystko, co wysyła input do gry, jest tu; serwis.py (orkiestrator) i testy zależą od interfejsu `AkcjeZywe`.
Zmierzone na żywo 19.10 (Edron, Mastafian): dialogi NPC, dwupoziomowe depo (locker -> depot chest), okno "Move Objects"
(suwak 1..N bez pola tekstowego; strzałka w lewo = -1), układ panelu z minimapą. Szczegóły: dane_tibia/SPEC_edron_serwis_1019.md.
"""
import os
import re
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from serwis_blad import SerwisBlad  # noqa: E402
import widma  # noqa: E402

ID_GOLD, ID_PLATINUM, ID_BLANK, ID_HAM = 3031, 3035, 3147, 3582
SLOT_AMUNICJI = 10          # slot ekwipunku Tibii, w którym lądują monety po wymianie w banku (22.10 wydra)
ID_BAGOW = {2868, 2869, 2854}               # purple / blue / zwykły plecak jako przedmiot w plecaku
ID_UH = 3160
ID_RUNY_BAGU = {ID_BLANK, ID_UH, 3198}      # blank / UH / HMM: to, co leży w worku na runy
NAZWY_GLOWNE = ("backpack", "bag")          # tytuł okna głównego plecaka
NAZWY_DEPO = ("locker", "depot chest")
MIN_HP_PROC = 60                            # start serwisu tylko przy HP >= 60%
ZASIEG_POTWORA = 4                          # potwór bliżej niż tyle pól na starcie = serwis nie startuje
BAG_ILE_RZEDOW = 5                          # okna plecaków rozciągamy do 5 rzędów (20 slotów)
SASIEDZI_SKRZYNI = ((0, -1), (1, 0), (0, 1), (-1, 0))     # skrzynia depo Edron stoi na północ od pola stania (zmierzone)
STRZALKA_LEWA = (-50, 1)                    # środek okna "Move Objects" -> strzałka suwaka w lewo (kalibracja 19.10)
WAGA_HAM_OZ, WAGA_BLANK_OZ, WAGA_BAGU_OZ = 20.0, 1.2, 18.0   # oz; dane_tibia/przedmioty.json, bag z 20 blankami = 42 oz (Karol 21.10)
LIMITY_CENY = {"ham": 12, "blank rune": 12, "backpack": 25}   # gp za sztukę; dwa razy więcej = oferta odrzucona
ODP_OFERTA = re.compile(r"do you want to buy (?:(\d+) |an? )?(.+?) for (\d+) gold", re.I)
ODP_PYTANIE_PLATINUM = re.compile(r"how many platinum", re.I)
ODP_SUKCES = re.compile(r"here you are|here it is|there you are", re.I)
SKUTEK_CZEKAJ_S, SKUTEK_KROK_S = 3.0, 0.4   # 22.10: tyle czekamy, aż pamięć klienta pokaże skutek przeciągnięcia (jeden odczyt po 0,9 s bywał za wcześnie)
SASIAD_PX = 40                              # sloty okna co 37 px: sąsiad (także po przekątnej) leży bliżej niż tyle
ODP_BRAK = re.compile(r"not have enough|cannot carry|too heavy|do not have|don't have|no room|capacity", re.I)


# --- układ panelu bocznego (czyste funkcje na obrazie) ----------------------------------------------

def uklad_panelu(obraz):
    """{"minimapa": "brak"|"zwinieta"|"rozwinieta", "plecak_ekw": (x, y), "prawo": x} z zrzutu ekranu gry.

    Pozycję paska HP (czerwony, kolumny 800..830) zmierzono 19.10: y 58..67 bez minimapy, 78..87 po zwinięciu,
    207..216 rozwinięta. Plecak w ekwipunku stoi 85 px niżej od pierwszego wiersza paska i 81 px od prawej krawędzi panelu."""
    import numpy as np
    a = np.asarray(obraz.convert("RGB")).astype(int)
    szer = a.shape[1]
    kol = a[:, max(0, szer - 140):max(1, szer - 110), :]
    r, g, b = kol[..., 0], kol[..., 1], kol[..., 2]
    czerw = ((r > 170) & (g < 90) & (b < 90)).mean(axis=1)
    ys = [y for y in range(35, min(500, a.shape[0])) if czerw[y] > 0.5]
    if not ys:
        return {"minimapa": None, "plecak_ekw": None, "prawo": szer - 4}
    y0 = ys[0]
    stan = "brak" if y0 <= 70 else ("zwinieta" if y0 <= 110 else "rozwinieta")
    prawo = szer - 4
    return {"minimapa": stan, "plecak_ekw": (prawo - 81, y0 + 85), "prawo": prawo}


def przycisk_zwin_minimape(prawo):
    """Przycisk "-" w nagłówku panelu Minimap (pierwszy panel, y = 42)."""
    return prawo - 27, 42


def wolny_slot(okno, zajete):
    """Indeks pierwszego widocznego slotu okna, którego nie ma w `zajete`, albo None."""
    return next((i for i in range(len(okno.sloty)) if i not in zajete), None)


def slot_w_pelni_widoczny(obraz, slot):
    """False, gdy dół slotu wystaje poza zrzut (okno depot chest na dole panelu: piąty rząd ucięty; `loot.znajdz_okna` zostawia takie
    sloty, a `czy_pusty` widzi w nich cudze piksele i daje „zajęte”). Bez zrzutu albo geometrii slotu: True (nie oceniamy)."""
    rozmiar = getattr(obraz, "size", None)
    y, bok = getattr(slot, "y", None), getattr(slot, "bok", None)
    if rozmiar is None or y is None or bok is None:
        return True
    return y + bok <= rozmiar[1]


def bezpieczny_wolny_slot(okno, kontener, pusty_na_ekranie=None, widoczny=None):
    """Indeks slotu, na który wolno UPUŚCIĆ przedmiot w oknie `kontener`, albo None. 22.10 (dawajkesh, depo Edron): upuszczenie
    na slot z kontenerem wkłada przedmiot do jego środka (licznik w skrzyni się nie zmienia), więc:
    - slot musi być wolny w pamięci ORAZ (gdy podano `pusty_na_ekranie(slot)`) pusty na ekranie; slot zajęty na ekranie,
      a wolny w pamięci, uchodzi za podejrzany (pamięć mogła nie nadążyć) i nie jest celem;
    - wśród wolnych bierzemy pierwszy, który nie sąsiaduje (także po przekątnej) z bagiem/plecakiem ani z podejrzanym slotem
      (zapas na przesunięcie okna o jedno pole); gdy takiego nie ma, pierwszy wolny;
    - sloty, dla których `widoczny(slot)` jest False (ucięte dołem okna/zrzutu), nie są ani celem, ani sygnałem ryzyka."""
    zajete = {q["slot"] for q in kontener.get("przedmioty", [])}
    ryzyko = {q["slot"] for q in kontener.get("przedmioty", []) if q["id"] in ID_BAGOW}
    wolne = []
    for i, s in enumerate(okno.sloty):
        if i in zajete or (widoczny is not None and not widoczny(s)):
            continue
        if pusty_na_ekranie is not None and not pusty_na_ekranie(s):
            ryzyko.add(i)
            continue
        wolne.append(i)

    def blisko(i, j):
        (xi, yi), (xj, yj) = okno.sloty[i].srodek, okno.sloty[j].srodek
        return abs(xi - xj) <= SASIAD_PX and abs(yi - yj) <= SASIAD_PX

    dalekie = [i for i in wolne if not any(blisko(i, j) for j in ryzyko if j < len(okno.sloty))]
    return (dalekie or wolne or [None])[0]


# --- rozmowa z NPC ---------------------------------------------------------------------------------

class Rozmowa:
    """Rozmowa z jednym NPC przez czat: wysłanie z weryfikacją echa, oczekiwanie na odpowiedź tego NPC (nie cudze krzyki)."""

    def __init__(self, czat, wiadomosci, nick, log=print, czas=time.monotonic, spij=time.sleep, powtorz_echo=3,
                 stan_zakladek=None, przelacz=None, pomin_zakladki=False):
        """`stan_zakladek()` -> {"zakladki": [{"nazwa","rect","aktywna"}], "aktywny_bufor": adres|None} (odczyt pamięci klienta);
        `przelacz(x, y)` klika zakładkę. 22.10: bez `stan_zakladek` Rozmowa niczego nie wyśle (`pomin_zakladki=True` tylko w
        testach z atrapą czatu): tekst trafia do AKTYWNEJ zakładki, a bywa nią prywatna rozmowa z graczem."""
        self.czat, self.wiad, self.nick, self.log = czat, wiadomosci, nick, log
        self.czas, self.spij, self.powtorz_echo = czas, spij, powtorz_echo
        self.stan_zakladek, self.przelacz, self.pomin_zakladki = stan_zakladek, przelacz, pomin_zakladki
        self.bufor_default = None              # adres bufora aktywnej zakładki Default w chwili ostatniego wysłania
        self.bufor = []                        # wiadomości odczytane przy oczekiwaniu na echo, jeszcze nieprzetworzone

    def _pobierz(self):
        self.bufor.extend(self.wiad() or [])

    def _nadrob(self):
        """Po długim marszu zaległe wiadomości (spam Trade) mogą wypełnić kilka porcji po 100: czytamy do opróżnienia,
        żeby echo świeżej wiadomości nie utknęło za zaległością."""
        for _ in range(30):
            n = len(self.wiad() or [])
            if n < 50:
                return

    def _zakladka_default(self):
        """Przed KAŻDYM wysłaniem: aktywna ma być zakładka Default, i to jedyna aktywna, a pamięć ma wskazywać jej bufor.
        Inna aktywna (np. prywatna rozmowa z graczem, 22.10 "hi" poszło do Wrexa) = klik w kartę Default (rect z pamięci klienta),
        potem ponowny odczyt. Brak pewności po kliku albo brak odczytu = SerwisBlad, nic nie jest wysyłane."""
        if self.pomin_zakladki:
            return
        if self.stan_zakladek is None:
            raise SerwisBlad("rozmowa", "brak odczytu zakładek czatu, nie wiem, gdzie trafi wiadomość (nie wysyłam)")
        opis = "?"
        for odczyt in range(5):
            try:
                st = self.stan_zakladek() or {}
            except Exception as e:      # noqa: BLE001 - każdy błąd odczytu = brak pewności
                raise SerwisBlad("rozmowa", f"odczyt zakładek czatu nie powiódł się ({e}); nie wysyłam") from e
            zak = st.get("zakladki") or []
            default = [z for z in zak if (z.get("nazwa") or "").casefold() == "default"]
            aktywne = [z for z in zak if z.get("aktywna")]
            opis = f"aktywne: {[z.get('nazwa') for z in aktywne]}, bufor: {st.get('aktywny_bufor')}"
            if len(default) != 1:
                raise SerwisBlad("rozmowa", f"na pasku czatu nie ma jednej zakładki Default ({len(default)}); nie wysyłam")
            if aktywne == default and st.get("aktywny_bufor"):
                self.bufor_default = st["aktywny_bufor"]
                return
            if odczyt == 0 and not aktywne == default:
                # klikamy raz; kolejne odczyty tylko czekają na skutek (klient przełącza z opóźnieniem)
                x1, y1, x2, y2 = default[0]["rect"]
                if self.przelacz is None or not (0 <= x1 < x2 <= 3000 and 400 <= y1 < y2 <= 3000 and 8 <= y2 - y1 <= 60
                                                 and 20 <= x2 - x1 <= 400):
                    raise SerwisBlad("rozmowa", f"aktywna zakładka inna niż Default ({opis}), nie umiem jej przełączyć "
                                                f"(rect Default {default[0].get('rect')}); nie wysyłam")
                self.log(f"rozmowa: aktywna zakładka czatu to nie Default ({opis}), klikam kartę Default")
                self.przelacz((x1 + x2) // 2, (y1 + y2) // 2)
            self.spij(0.5)
        raise SerwisBlad("rozmowa", f"nie potwierdzono aktywnej zakładki Default ({opis}); nie wysyłam")

    def powiedz(self, tekst, czekaj_echo_s=4.0):
        """Wysyła `tekst` i czeka, aż pojawi się własna linia na czacie (bez echa wysyła ponownie, do `powtorz_echo` razy).
        Zakładka inna niż Default = przełączenie albo błąd (nie wysyłamy dalej); echo w innym buforze niż aktywny Default
        w chwili wysłania = natychmiastowe przerwanie (bez kolejnych prób)."""
        wlasne = lambda x: x["autor"] == self.nick and x["tekst"].strip().lower() == tekst.strip().lower()
        for proba in range(1, self.powtorz_echo + 1):
            self._nadrob()
            self._pobierz()
            self.bufor = [x for x in self.bufor if not wlasne(x)]      # stare echo tej samej wiadomości nie potwierdzi nowej
            self._zakladka_default()
            self.czat(tekst)
            t0 = self.czas()
            while self.czas() - t0 < czekaj_echo_s:
                self._pobierz()
                for w in self.bufor:
                    if w["autor"] == self.nick and w["tekst"].strip().lower() == tekst.strip().lower():
                        if w["kanal"].casefold() not in ("default", ""):
                            raise SerwisBlad("rozmowa", f"wiadomość poszła na kanał {w['kanal']!r}, przełącz zakładkę na Default")
                        if not self.pomin_zakladki and self.bufor_default and w.get("bufor") \
                                and str(w["bufor"]).casefold() != str(self.bufor_default).casefold():
                            # 22.10: kanał bywa nieznany (None), ale bufor echa to twardy dowód: to nie Default
                            raise SerwisBlad("rozmowa", f"{tekst!r} trafiło do bufora {w['bufor']} zamiast Default "
                                                        f"({self.bufor_default}); przerywam, nie ponawiam")
                        # spóźnione echa wcześniejszych prób tej samej wiadomości nie mogą potwierdzić kolejnej
                        self.bufor = [x for x in self.bufor if not (x["autor"] == self.nick
                                                                     and x["tekst"].strip().lower() == tekst.strip().lower())]
                        return True
                self.spij(0.4)
            self.log(f"rozmowa: brak echa dla {tekst!r} (próba {proba}/{self.powtorz_echo})")
        raise SerwisBlad("rozmowa", f"wiadomość {tekst!r} nie pojawiła się na czacie")

    def czekaj(self, npc, wzor, s=8.0):
        """Tekst pierwszej wiadomości od `npc` pasującej do `wzor` w ciągu `s` sekund albo None."""
        t0 = self.czas()
        while True:
            self._pobierz()
            for w in list(self.bufor):
                if w["autor"].casefold() == npc.casefold():
                    self.bufor.remove(w)
                    self.log(f"  [{w['autor']}] {w['tekst']}")
                    if wzor is None or wzor.search(w["tekst"]):
                        return w["tekst"]
            if self.czas() - t0 >= s:
                return None
            self.spij(0.5)

    def powitaj(self, npc):
        """hi -> odpowiedź NPC (trzy próby; przy zajętym NPC ("talking to") nie liczymy jako porażkę, czekamy)."""
        for proba in range(3):
            self.powiedz("hi")
            r = self.czekaj(npc, None, 6.0)
            if r is not None:
                if re.search(r"talking to|busy|wait", r, re.I):
                    self.spij(5.0)
                    continue
                return r
            self.spij(1.0)
        raise SerwisBlad("rozmowa", f"{npc} nie odpowiada na hi (nie stoi obok?)")

    def zamow(self, npc, tekst, max_cena_sztuki, ile=None, slepy_yes=False):
        """Zamówienie (np. "5 ham" albo "backpack") -> oferta -> yes -> potwierdzenie. Zwraca (ile_sztuk, cena).
        `slepy_yes`: NPC, którego oferta nie ląduje w logu czatu (Mirabell 19.10): po 5 s ciszy mówimy yes, a skutek
        i tak sprawdza plecak (ilość i cena), więc zła odpowiedź nie przejdzie."""
        self.powiedz(tekst)
        o = self.czekaj(npc, ODP_OFERTA, 8.0 if not slepy_yes else 5.0)
        if o is None and slepy_yes:
            self.log(f"rozmowa: {npc} nie pokazał oferty na {tekst!r}, potwierdzam (skutek sprawdzi plecak)")
            self.powiedz("yes")
            r = self.czekaj(npc, re.compile(ODP_SUKCES.pattern + "|" + ODP_BRAK.pattern, re.I), 8.0)
            if r is None or ODP_BRAK.search(r) and not ODP_SUKCES.search(r):
                raise SerwisBlad("rozmowa", f"{npc}: brak potwierdzenia zakupu ({r!r})")
            return (ile or 1), None
        if o is None:
            raise SerwisBlad("rozmowa", f"{npc}: brak oferty na {tekst!r}")
        m = ODP_OFERTA.search(o)
        sztuk = int(m[1]) if m[1] else 1
        cena = int(m[3])
        if ile is not None and sztuk != ile:
            self.powiedz("no")
            raise SerwisBlad("rozmowa", f"{npc}: oferta na {sztuk} szt., zamawiałem {ile}")
        if cena > max_cena_sztuki * max(1, sztuk):
            self.powiedz("no")
            raise SerwisBlad("rozmowa", f"{npc}: oferta za droga ({cena} gp za {sztuk} szt., limit {max_cena_sztuki} gp/szt.)")
        self.powiedz("yes")
        r = self.czekaj(npc, re.compile(ODP_SUKCES.pattern + "|" + ODP_BRAK.pattern, re.I), 8.0)
        if r is None or ODP_BRAK.search(r) and not ODP_SUKCES.search(r):
            raise SerwisBlad("rozmowa", f"{npc}: brak potwierdzenia zakupu ({r!r})")
        return sztuk, cena

    def zmien_gold(self, npc, platinum):
        """hi -> change gold -> liczba platinum -> yes -> "Here you are." (dialog zmierzony 19.10 u Ebenizera)."""
        self.powitaj(npc)
        self.powiedz("change gold")
        if self.czekaj(npc, ODP_PYTANIE_PLATINUM, 8.0) is None:
            raise SerwisBlad("bank", f"{npc} nie zapytał o liczbę platinum")
        self.powiedz(str(int(platinum)))
        self.czekaj(npc, None, 2.0)           # u Ebenizera po liczbie nie było linii; jeśli jest pytanie, i tak "yes"
        self.powiedz("yes")
        r = self.czekaj(npc, re.compile(ODP_SUKCES.pattern + "|" + ODP_BRAK.pattern, re.I), 8.0)
        if r is None or ODP_BRAK.search(r) and not ODP_SUKCES.search(r):
            raise SerwisBlad("bank", f"{npc}: brak potwierdzenia wymiany ({r!r})")
        return True


# --- akcje na żywej grze ------------------------------------------------------------------------------

def _nazwy_npc():
    """Imiona NPC z bazy serwera (dane_tibia/serwer74/npc_pelne.json); brak pliku = pusty zbiór."""
    import json
    plik = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dane_tibia", "serwer74", "npc_pelne.json")
    try:
        with open(plik, encoding="utf-8") as f:
            return {n["nazwa"].casefold() for n in json.load(f)["npc"]}
    except (OSError, ValueError, KeyError):
        return set()


NPC_NAZWY = _nazwy_npc() | {"ebenizer", "mirabell", "beatrice", "alexander", "bonifacius"}


def _nazwa(k):
    return (k.get("nazwa") or "").casefold()


def _ma_bag(k):
    """Czy w kontenerze leży przedmiot-bag (ID_BAGOW), czyli czy to plecak, w którym schowano worek na runy."""
    return any(q["id"] in ID_BAGOW for q in k.get("przedmioty", []))


def _runowy(k):
    """Czy w kontenerze przeważają runy z bagu na runy (blank/UH/HMM), jak loot._wyglada_na_runy."""
    przedm = k.get("przedmioty", [])
    n_run = sum(1 for q in przedm if q["id"] in ID_RUNY_BAGU)
    return n_run > 0 and n_run * 2 >= len(przedm)


def _rozdziel_plecaki(kon):
    """(plecak główny albo None, [worki na runy o nazwie plecaka]) wśród kontenerów `kon`.

    Jedno okno o nazwie plecaka = plecak główny (jak dotąd). 22.10 (wydra, Thais): worek na runy to zwykły backpack (2854),
    więc dwa okna noszą tę samą nazwę "backpack" (u postaci z Edronu worek to "blue backpack" i nazwa wystarcza). Pamięć kontenerów
    nie podaje rodzica ani slotu ekwipunku (kontenery.py: numer, nazwa, id, pojemność, przedmioty; id obu to 2854), więc
    rozstrzyga zawartość: główny = ten, w którym leży przedmiot-bag (ID_BAGOW); gdy żaden nie ma bagu w środku (worek już
    przeniesiony do depo, a jego okno zostało), główny = jedyny bez przewagi run, a gdy obaj bez run, jedyny niepusty.
    Więcej niż dwa okna albo brak jednoznacznego wyniku = SerwisBlad (nie zgadujemy)."""
    grupa = [k for k in kon if _nazwa(k) in NAZWY_GLOWNE]
    if len(grupa) <= 1:
        return (grupa[0] if grupa else None), []
    glowny = None
    if len(grupa) == 2:
        z_bagiem = [k for k in grupa if _ma_bag(k)]
        if len(z_bagiem) == 1:
            glowny = z_bagiem[0]
        elif not z_bagiem:
            kandydaci = [k for k in grupa if not _runowy(k)]
            if len(kandydaci) > 1:
                kandydaci = [k for k in kandydaci if k.get("przedmioty")]
            if len(kandydaci) == 1:
                glowny = kandydaci[0]
    if glowny is None:
        raise SerwisBlad("okna", f"dwa kontenery o nazwie plecaka ({[k.get('nazwa') for k in grupa]}): nie odróżnię plecaka od baga")
    return glowny, [k for k in grupa if k is not glowny]


def _ten_sam(a, b):
    return a is b or (a.get("numer") is not None and a.get("numer") == b.get("numer"))


def _czy_glowny(k, kon):
    """Czy `k` (element listy `kon`) to główny plecak; rozróżnia też dwa okna o tej samej nazwie (`_rozdziel_plecaki`)."""
    glowny, _ = _rozdziel_plecaki(kon)
    return glowny is not None and _nazwa(k) in NAZWY_GLOWNE and _ten_sam(glowny, k)


def _czy_bag(k, kon):
    """Bag na runy: kontener inny niż główny plecak i depo, o nazwie plecaka/torby (np. "blue backpack", "purple backpack"),
    albo drugie okno o nazwie plecaka, które nie jest głównym (zwykły backpack jako worek, Thais 22.10)."""
    n = _nazwa(k)
    if n in NAZWY_GLOWNE:
        return any(_ten_sam(k, b) for b in _rozdziel_plecaki(kon)[1])
    return n not in NAZWY_DEPO and ("backpack" in n or n.endswith("bag") or "pouch" in n)


def _suma(k, ids):
    return sum(max(1, q.get("ilosc", 1)) for q in k.get("przedmioty", []) if q["id"] in ids)


class AkcjeZywe:
    """Interfejs używany przez serwis.Serwis. Każda metoda weryfikuje skutek w pamięci klienta (kontenery), na obu końcach."""

    def __init__(self, postac, log=print, sprawdz_bota=True):
        import bot
        import mozg
        import wypad
        self.postac, self.log, self.sprawdz_bota = postac, log, sprawdz_bota
        self.nick = postac.nazwa
        self._ops = wypad.OperacjeZywe(log=log, wyslij=lambda t: mozg.wpisz_na_czacie(t))
        self.rozmowa = Rozmowa(self._ops.czat, self._ops.wiadomosci, self.nick, log=log,
                               stan_zakladek=self._ops.stan_zakladek, przelacz=self._kliknij_zakladke)
        self._bot = bot

    def _kliknij_zakladke(self, x, y):
        """Lewy klik w kartę zakładki czatu (pozycja z pamięci klienta, nie stała)."""
        with self._mysz() as m:
            m.klik(x, y, 1, None, drganie=1)

    # --- odczyt ---

    def kontenery(self):
        import loot
        kon, powod = loot.kontenery_z_pamieci()
        if kon is None:
            if powod and "nie widzi otwartych" in powod:
                return []                 # gniazdo działa, tylko nic nie jest otwarte
            raise SerwisBlad("odczyt", f"pamięć kontenerów: {powod}")
        return kon

    def ilosc(self, ids, bez=NAZWY_DEPO):
        """Suma sztuk przedmiotów o ID z `ids` we wszystkich otwartych kontenerach poza depo."""
        return sum(_suma(k, ids) for k in self.kontenery() if _nazwa(k) not in bez)

    def _ekwipunek(self):
        """{slot: {"id", "ilosc"}} slotów ekwipunku postaci albo None przy braku odczytu (jak w uh.py: komenda `kontenery` z
        `ekwipunek`). Brak odczytu nie jest błędem: majątek liczy się wtedy tylko z kontenerów, jak dotąd."""
        try:
            e = self._bot._zapytaj_surowe({"cmd": "kontenery", "ekwipunek": True}).get("ekwipunek")
        except self._bot.Zatrzymano:
            raise
        except Exception:
            return None
        return None if not isinstance(e, dict) else e

    def majatek_w_ekwipunku(self):
        """Gold + 100 * platinum + 10000 * crystal leżące w slocie 10 ekwipunku (amunicja). 22.10 wydra (Thais): bank zamienił
        złoto w tym slocie na 6 platinum, a odczyt samych kontenerów widział 13 gp. Brak odczytu = 0."""
        e = self._ekwipunek() or {}
        q = e.get(str(SLOT_AMUNICJI)) or e.get(SLOT_AMUNICJI) or {}
        wartosc = {ID_GOLD: 1, ID_PLATINUM: 100, 3043: 10000}.get(q.get("id"), 0)
        return wartosc * max(1, q.get("ilosc", 1)) if wartosc else 0

    def ilosc_w_plecaku(self, ids):
        """Suma sztuk o ID z `ids` tylko w głównym plecaku (bez baga na runy, który depo odkłada razem z zawartością)."""
        g = self._glowny()
        return 0 if g is None else _suma(g, ids)

    def majatek(self, tylko_glowny=False):
        """Gold + 100 * platinum + 10000 * crystal w otwartych kontenerach poza depo oraz w slocie 10 ekwipunku (depo go nie rusza);
        `tylko_glowny`: z kontenerów tylko plecak (pieniądze w bagu na runy odejdą z nim do depo)."""
        if tylko_glowny:
            g = self._glowny()
            return self.majatek_w_ekwipunku() + (0 if g is None else
                                                 _suma(g, {ID_GOLD}) + 100 * _suma(g, {ID_PLATINUM}) + 10000 * _suma(g, {3043}))
        return self.majatek_w_ekwipunku() + self.ilosc({ID_GOLD}) + 100 * self.ilosc({ID_PLATINUM}) + 10000 * self.ilosc({3043})

    def wolne_w_bagu(self):
        """Wolne sloty jedynego bagu na runy; 0, gdy bagu brak albo jest więcej niż jeden."""
        kon = self.kontenery()
        bagi = [k for k in kon if _czy_bag(k, kon)]
        if len(bagi) != 1:
            return 0
        return bagi[0].get("pojemnosc", 0) - len(bagi[0].get("przedmioty", []))

    def brakuje(self, co, docelowo):
        """Ile sztuk brakuje do celu (dla backpacka 0 albo 1)."""
        if co == "backpack":
            return 1 if self.potrzeba_baga() else 0
        ids = {"ham": {ID_HAM}, "blank rune": {ID_BLANK}}[co]
        return max(0, docelowo - self.ilosc(ids))

    def cap(self):
        """Wolny udźwig postaci w oz (jak wyprawa._cap: wartość > 5000 to setne części oz). Brak odczytu = błąd, nie zgadujemy."""
        cap = self._gracz().get("cap")
        if cap is None:
            raise SerwisBlad("start", "klient nie podaje capa postaci")
        return float(cap) / 100.0 if cap > 5000 else float(cap)

    def rezerwa_na_blanki(self, blanki):
        """Ile oz capa musi zostać wolne po zakupie jedzenia, żeby zmieścić bag z `blanki` blankami: bag jeszcze niekupiony
        (waży 18 oz) liczymy razem z blankami, bag już w plecaku (jego waga jest w capie) tylko same blanki."""
        brak = self.brakuje("blank rune", blanki)
        return (WAGA_BAGU_OZ if self.potrzeba_baga() else 0.0) + brak * WAGA_BLANK_OZ

    def cel_ham(self, cel, rezerwa_oz):
        """Docelowa liczba ham, tak by po zakupie zostało co najmniej `rezerwa_oz` wolnego capa (NPC i tak sprzedaje tylko tyle,
        ile się mieści, a wtedy kolejny zakup, blanki, kończył się porażką: 21.10 invincible, 4 z 20 blanków)."""
        ma = self.ilosc({ID_HAM})
        wolne = self.cap() - rezerwa_oz
        ile = max(0, min(cel - ma, int(wolne // WAGA_HAM_OZ)))
        self.log(f"cap: wolne {self.cap():.1f} oz, rezerwa {rezerwa_oz:.1f} oz na bag z blankami, ham w plecaku {ma}, kupię {ile} (cel {cel})")
        return ma + ile

    def _glowny(self, kon=None):
        return _rozdziel_plecaki(kon or self.kontenery())[0]

    # --- start ---

    def _gracz(self):
        try:
            return self._bot._zapytaj_surowe({"cmd": "gracz"})["gracz"]
        except Exception as e:
            raise SerwisBlad("start", f"nie odczytam stanu postaci ({e!r})")

    def _stwory(self):
        try:
            lista = self._bot._zapytaj_surowe({"cmd": "stwory"})["stwory"]
        except Exception as e:
            raise SerwisBlad("start", f"nie odczytam stworów ({e!r})")
        if widma.domyslnie_wlaczone():
            # tylko znacznik `widmo` (nic nie znika); zajętość pól pomija oznaczone (pole_zajete, serwis.py), RPC bez zmian
            try:
                widma.loguj(widma.oznacz(lista, self.nick), self.log, time.monotonic(),
                            self.__dict__.setdefault("_widma_log", {}))
            except Exception as e:
                self.log(f"widma: błąd {e!r}")
        return lista

    def sprawdz_start(self):
        """Bot stoi, HP >= MIN_HP_PROC, w pobliżu brak potworów, pamięć kontenerów odpowiada."""
        if self.sprawdz_bota:
            import dopasuj_okno
            if dopasuj_okno.bot_dziala():
                raise SerwisBlad("start", "bot (mozg/cavebot) działa: zatrzymaj go przed serwisem")
        g = self._gracz()
        if g.get("max_hp") and 100 * g["hp"] / g["max_hp"] < MIN_HP_PROC:
            raise SerwisBlad("start", f"HP {g['hp']}/{g['max_hp']} poniżej {MIN_HP_PROC}%")
        poz = tuple(self.postac.pozycja())
        for s in self._stwory():
            if (s.get("nazwa") or "").casefold() in NPC_NAZWY or (s.get("hp") is not None and s["hp"] <= 0):
                continue                         # NPC (stoją tuż przy stanowiskach) i martwe istoty to nie zagrożenie
            if not s.get("gracz") and s.get("z") == poz[2] and s.get("x") is not None \
                    and max(abs(s["x"] - poz[0]), abs(s["y"] - poz[1])) <= ZASIEG_POTWORA:
                raise SerwisBlad("start", f"potwór {s.get('nazwa')} {max(abs(s['x'] - poz[0]), abs(s['y'] - poz[1]))} pól obok")
        self.kontenery()                       # sprawdza, że pamięć kontenerów odpowiada

    def pole_zajete(self, pole):
        """True, gdy na `pole` stoi inny gracz/stwór. Brak odczytu = błąd (nie zakładamy, że wolne)."""
        return any((s.get("x"), s.get("y"), s.get("z")) == tuple(pole) and s.get("nazwa") != self.nick
                   and not s.get("widmo") for s in self._stwory())

    # --- ekran ---

    def _zrzut(self, mysz):
        import loot
        return loot._zrzut(mysz)

    def _mysz(self):
        import ekran
        return ekran.Mysz()

    def _zamknij(self, numer):
        import loot
        return loot.zamknij_kontener(numer, log=self.log)

    def _okna_numery(self, obraz):
        """[(okno, kontener)]: okna od góry w dół, kontenery po numerze rosnąco; liczby muszą się zgadzać, a widoczne sloty
        okna nie mogą przekraczać pojemności kontenera. Dodatkowo każda akcja sprawdza skutek na obu końcach."""
        import loot
        okna = sorted(loot.znajdz_okna(obraz), key=lambda o: o.sloty[0].srodek[1])  # gora bywa None
        kon = sorted(self.kontenery(), key=lambda k: k.get("numer", 0))
        if len(okna) != len(kon):
            raise SerwisBlad("okna", f"okien na ekranie {len(okna)}, kontenerów w pamięci {len(kon)}")
        # numer kontenera nie mówi o położeniu okna (świeżo otwarty locker dostaje numer 0, a leży pod plecakiem):
        # przypisanie po zawartości slotów i tytułach (loot.dopasuj_okna), numer tylko jako rezerwa
        przypisane, powod = loot.dopasuj_okna(obraz, okna, kon)
        if przypisane is not None:
            kon = list(przypisane)
        else:
            kon = self._okna_bez_dopasowania(obraz, okna, kon, powod)
        if all(k.get("numer") is not None for k in kon):
            self._kolejnosc_okien = [k["numer"] for k in kon]        # pamięć układu okien na wypadek niejednoznacznego odczytu
        for o, k in zip(okna, kon):
            if len(o.sloty) > max(k.get("pojemnosc", 0), 1):
                raise SerwisBlad("okna", f"okno ma {len(o.sloty)} slotów, kontener {k.get('nazwa')!r} pojemność {k.get('pojemnosc')}")
        return list(zip(okna, kon))

    def _okna_bez_dopasowania(self, obraz, okna, kon, powod):
        """Kontenery w kolejności okien, gdy `loot.dopasuj_okna` zawiodło. 22.10 (invincible, wydra): przypisanie po numerze
        kontenera zamieniało okna plecaka i baga (numer ≠ położenie), a bot chwytał przedmiot z niewłaściwego okna. Teraz:
        - bez zrzutu (`obraz` None, tylko testy) jedyną rezerwą jest numer;
        - ze zrzutem wolno zostać przy kolejności z ostatniego udanego dopasowania (okna się nie przesuwają, a bag wypełniony
          po brzegi daje okna nie do odróżnienia po zajętości), ale tylko gdy ta kolejność zgadza się z ekranem lepiej niż każda
          inna (albo idealnie, gdy inne też są idealne) i co najwyżej 3 sloty się różnią (pamięć klienta bywa o chwilę za ekranem);
        - inaczej SerwisBlad: przerywamy PRZED pierwszym przeciągnięciem, nie zgadujemy."""
        if obraz is None:
            self.log(f"okna: dopasowanie po zawartości nie wyszło ({powod}), bez zrzutu: przypisuję po numerze kontenera")
            return kon
        import itertools
        import loot
        hist = getattr(self, "_kolejnosc_okien", None)
        po_numerze = {k.get("numer"): k for k in kon}
        if hist and len(hist) == len(okna) and set(hist) == set(po_numerze) and len(kon) <= 6:
            koszt = {(i, j): loot._niezgodnosci(obraz, o, k) for i, o in enumerate(okna) for j, k in enumerate(kon)}
            idx = {k.get("numer"): j for j, k in enumerate(kon)}
            wybrana = tuple(idx[n] for n in hist)

            def suma(perm):
                c = [koszt[i, j] for i, j in enumerate(perm)]
                return None if None in c else sum(c)

            k0 = suma(wybrana)
            inne = [c for perm in itertools.permutations(range(len(kon))) if perm != wybrana and (c := suma(perm)) is not None]
            if k0 is not None and k0 <= 3 and (not inne or k0 < min(inne) or (k0 == 0 and min(inne) == 0)):
                self.log(f"okna: dopasowanie po zawartości nie wyszło ({powod}), zostaję przy kolejności z poprzedniego odczytu "
                         f"(różnic z ekranem: {k0})")
                return [kon[j] for j in wybrana]
        raise SerwisBlad("okna", f"nie przypiszę okien do kontenerów ({powod}); przerywam przed jakimkolwiek ruchem, "
                                 "bo przypisanie po numerze kontenera mogłoby zamienić okna")

    # --- układ okien ---

    def przygotuj_okna(self):
        """Minimapa zwinięta, zostawione depo zamknięte, bag na runy (jeśli jest) i plecak otwarte w osobnych oknach
        (bag wyżej, plecak niżej), oba rozciągnięte do 5 rzędów. Idempotentne."""
        import loot
        self._kolejnosc_okien = None                    # okna będą otwierane i przesuwane: stara kolejność przestaje obowiązywać
        with self._mysz() as m:
            obraz = self._zrzut(m)
            u = uklad_panelu(obraz)
            if u["minimapa"] is None:
                raise SerwisBlad("okna", "nie rozpoznałem układu panelu (brak paska HP na zrzucie)")
            if u["minimapa"] == "rozwinieta":
                self.log("okna: zwijam minimapę (miejsce na plecaki)")
                m.klik(*przycisk_zwin_minimape(u["prawo"]), 1, None, drganie=1)
                time.sleep(1.2)
                u = uklad_panelu(self._zrzut(m))
                if u["minimapa"] == "rozwinieta":
                    raise SerwisBlad("okna", "minimapa nie zwinęła się")
            for k in self.kontenery():          # zostawione depo z poprzedniego razu
                if _nazwa(k) in NAZWY_DEPO:
                    self._zamknij(k.get("numer"))
            if self._glowny() is None:
                self._otworz_plecak_z_ekwipunku(m, u)
            kon = self.kontenery()
            glowny = self._glowny(kon)
            inne = [k for k in kon if k is not glowny]
            bagi = [q for q in (glowny or {}).get("przedmioty", []) if q["id"] in ID_BAGOW]
            if not inne and len(bagi) == 1:
                self.log("okna: otwieram bag w osobnym oknie")
                pary = self._okna_numery(self._zrzut(m))
                o = next(o for o, k in pary if k.get("numer") == glowny.get("numer"))
                if bagi[0]["slot"] >= len(o.sloty):
                    raise SerwisBlad("okna", f"bag w slocie {bagi[0]['slot']}, a okno plecaka pokazuje {len(o.sloty)} slotów")
                m.klik(*o.sloty[bagi[0]["slot"]].srodek, 1, "Control_L", drganie=2)   # bag zastępuje okno plecaka
                time.sleep(1.3)
                self._otworz_plecak_z_ekwipunku(m, u)                                   # plecak wraca w osobnym oknie
            elif len(bagi) > 1 and not inne:
                raise SerwisBlad("okna", f"w plecaku {len(bagi)} bagi, nie wiem, który otworzyć jako bag na runy")
            for _ in range(4):                  # rozciągamy od góry; po każdym rozciągnięciu okna niżej się przesuwają
                obraz = self._zrzut(m)
                okna = sorted(loot.znajdz_okna(obraz), key=lambda o: o.sloty[0].srodek[1])  # gora bywa None
                zrobione = False
                for o in okna:
                    rzedy = len({s.y for s in o.sloty})
                    if o.sloty and rzedy < BAG_ILE_RZEDOW:
                        x = (o.lewo + o.prawo) // 2
                        y = loot.dolna_krawedz(o, obraz)
                        m.przeciagnij(x, y, x, y + (BAG_ILE_RZEDOW - rzedy) * 37, drganie=0)
                        time.sleep(0.8)
                        zrobione = True
                        break
                if not zrobione:
                    break
            okna = loot.znajdz_okna(self._zrzut(m))
            if any(len({s.y for s in o.sloty}) < BAG_ILE_RZEDOW for o in okna if o.sloty):
                raise SerwisBlad("okna", "nie udało się rozciągnąć okien plecaków do 5 rzędów (brak miejsca w panelu?)")
        return True

    def _otworz_plecak_z_ekwipunku(self, m, u):
        """Ctrl+klik na plecaku w ekwipunku (pozycja z układu panelu, nie ze stałej); sprawdza, że przybył kontener plecaka."""
        ile0 = len([k for k in self.kontenery() if _nazwa(k) in NAZWY_GLOWNE])    # po nazwie: worek-backpack też jest takim oknem
        self.log("okna: otwieram plecak z ekwipunku")
        m.klik(*u["plecak_ekw"], 1, "Control_L", drganie=2)
        time.sleep(1.4)
        ile1 = len([k for k in self.kontenery() if _nazwa(k) in NAZWY_GLOWNE])
        if ile1 <= ile0:
            raise SerwisBlad("okna", "plecak z ekwipunku się nie otworzył")

    # --- bank ---

    def bank_zmien(self, npc):
        gold = self.ilosc({ID_GOLD})
        plat0 = self.ilosc({ID_PLATINUM})
        n = gold // 100
        if n <= 0:
            self.log(f"bank: {gold} gold, nic do wymiany")
            return 0
        self.rozmowa.zmien_gold(npc, n)
        time.sleep(1.0)
        plat1, gold1 = self.ilosc({ID_PLATINUM}), self.ilosc({ID_GOLD})
        if plat1 != plat0 + n or gold1 != gold - 100 * n:
            raise SerwisBlad("bank", f"wymiana {n} platinum: platinum {plat0} -> {plat1}, gold {gold} -> {gold1}")
        self.log(f"bank: wymieniono {n * 100} gold na {n} platinum")
        return n

    # --- zakupy ---

    def potrzeba_baga(self):
        """True, gdy nie ma bagu na runy: w plecaku nie leży żaden bag i nie ma otwartego okna z bagiem."""
        kon = self.kontenery()
        glowny = self._glowny(kon)
        w_plecaku = [q for q in (glowny or {}).get("przedmioty", []) if q["id"] in ID_BAGOW]
        return not any(_czy_bag(k, kon) for k in kon) and not w_plecaku

    def kup(self, npc, co, docelowo, prefiks=""):
        """`prefiks`: słowo przed zamówieniem, gdy NPC go wymaga (Thais: Frodo i Xodet odpowiadają na „buy 3 ham”, zmierzone
        13-14.10; Edron: samo „5 ham”). Ilość i cenę i tak sprawdzają oferta NPC oraz plecak po zakupie."""
        ids = {"ham": {ID_HAM}, "blank rune": {ID_BLANK}, "backpack": ID_BAGOW}[co]
        potrzeba = self.brakuje(co, docelowo)
        if potrzeba <= 0:
            self.log(f"kup: {co} nie brakuje (cel {docelowo}), nie kupuję")
            return 0
        ma, majatek0 = self.ilosc(ids), self.majatek()
        self.rozmowa.powitaj(npc)
        tekst = prefiks + (co if co == "backpack" else f"{potrzeba} {co}")
        self.rozmowa.zamow(npc, tekst, LIMITY_CENY[co], ile=None if co == "backpack" else potrzeba,
                           slepy_yes=(co == "ham"))
        time.sleep(1.5)
        po, majatek1 = self.ilosc(ids), self.majatek()
        if po != ma + potrzeba:
            raise SerwisBlad("kup", f"{co}: w plecaku {ma} -> {po}, oczekiwano dokładnie +{potrzeba}")
        wydano = majatek0 - majatek1
        if wydano < 0 or wydano > LIMITY_CENY[co] * potrzeba:
            raise SerwisBlad("kup", f"{co}: wydano {wydano} gp za {potrzeba} szt. (limit {LIMITY_CENY[co]} gp/szt.)")
        self.log(f"kup: {co} {ma} -> {po}, wydano {wydano} gp")
        return potrzeba

    # --- przeciąganie między oknami ---

    def _przeciagnij(self, m, okno_z, i_z, okno_do, i_do):
        m.przeciagnij(*okno_z.sloty[i_z].srodek, *okno_do.sloty[i_do].srodek, drganie=3)
        time.sleep(0.9)

    def _okno_ilosci(self, m, zostaw_w_zrodle, razem):
        """Po przeciągnięciu stosu: strzałką w lewo ustawia ilość `razem - zostaw_w_zrodle` i klika Ok."""
        import loot
        t0 = time.monotonic()
        poz = None
        while time.monotonic() - t0 < 2.0 and poz is None:
            poz = loot.znajdz_okno_ilosci(self._zrzut(m))
            time.sleep(0.15)
        if poz is None:
            return False
        sx, sy = poz[0] + 60, poz[1] + 66
        for _ in range(int(zostaw_w_zrodle)):
            m.klik(sx + STRZALKA_LEWA[0], sy + STRZALKA_LEWA[1], 1, None, drganie=1)
            time.sleep(0.2)
        m.klik(sx + loot.OK_DX, sy + loot.OK_DY, 1, None, drganie=2)
        time.sleep(0.8)
        return True

    # --- depo ---

    def _otworz_depo(self, m):
        """Ctrl+klik na skrzyni obok (północ, potem pozostałe), potem na pozycji "DEPOT" w lockerze: okno staje się "depot chest"."""
        import ekran
        przed = {k.get("numer") for k in self.kontenery()}
        for dx, dy in SASIEDZI_SKRZYNI:
            ekran.otworz(dx, dy)
            time.sleep(1.2)
            nowe = [k for k in self.kontenery() if k.get("numer") not in przed]
            if nowe and _nazwa(nowe[0]) == "locker":
                break
            if nowe:                       # coś innego niż locker: zostawiamy otwarte, nie zgadujemy
                raise SerwisBlad("depo", f"po kliku na ({dx},{dy}) otwarto {nowe[0].get('nazwa')!r}, nie locker")
        else:
            return False
        for _ in range(2):
            obraz = self._zrzut(m)
            pary = self._okna_numery(obraz)
            okno_locker = next((o for o, k in pary if _nazwa(k) == "locker"), None)
            if okno_locker is None:
                break
            m.klik(*okno_locker.sloty[0].srodek, 1, "Control_L", drganie=2)
            time.sleep(1.3)
            if any(_nazwa(k) == "depot chest" for k in self.kontenery()):
                return True
        return False

    def _sprawdz_bag_do_depo(self, kon, glowny):
        """Odkładamy tylko bag z UH, nigdy świeży bag z blankami (idempotencja po awarii w połowie serwisu)."""
        bagi = [q for q in glowny.get("przedmioty", []) if q["id"] in ID_BAGOW]
        if len(bagi) > 1:
            raise SerwisBlad("depo", f"w plecaku {len(bagi)} bagi, nie wiem, który jest bagiem na runy")
        for k in kon:
            if _czy_bag(k, kon) and _suma(k, {ID_BLANK}) > 0 and _suma(k, {ID_UH}) == 0:
                raise SerwisBlad("depo", f"otwarty bag {k.get('nazwa')!r} ma blanki i nie ma UH: to nowy bag, nie odkładam")
        return bagi

    def depo_zloz(self, zostaw_platinum=3, odejdz=None):
        """Otwiera depo (skrzynia obok), odkłada bag z runami z plecaka i platinum ponad `zostaw_platinum`, zamyka depo
        i każde okno poza plecakiem. Zwraca False tylko wtedy, gdy skrzynia się nie otworzyła (nic nie ruszone)."""
        with self._mysz() as m:
            if not self._otworz_depo(m):
                return False
            kon = self.kontenery()
            glowny = self._glowny(kon)
            if glowny is None:
                raise SerwisBlad("depo", "brak okna plecaka")
            bagi = self._sprawdz_bag_do_depo(kon, glowny)
            if bagi:
                self._przenies_do_depo(m, bagi[0]["slot"])
            self._platinum_do_depo(m, zostaw_platinum)
        self._zamknij_poza_plecakiem(odejdz)
        plat = self.ilosc({ID_PLATINUM})
        glowny = self._glowny()
        if glowny is None or any(q["id"] in ID_BAGOW for q in glowny.get("przedmioty", [])):
            raise SerwisBlad("depo", "bag nadal leży w plecaku po składaniu")
        if plat > zostaw_platinum:
            raise SerwisBlad("depo", f"platinum w plecaku {plat}, miało zostać {zostaw_platinum}")
        self.log(f"depo: złożone (platinum w plecaku {plat})")
        return True

    def _zamknij_poza_plecakiem(self, odejdz=None):
        """Zamyka depo i okno przeniesionego baga (klient może je trzymać otwarte); sprawdza w pamięci, że został tylko plecak.
        22.10 (Karol): gdy okna nie dają się zamknąć, `odejdz()` odsuwa postać od skrzyni (serwer sam zamyka depo i okna z niego)."""
        for _ in range(3):
            kon = self.kontenery()
            reszta = [k for k in kon if not _czy_glowny(k, kon)]
            if not reszta:
                return
            for k in reszta:
                try:
                    self._zamknij(k.get("numer"))
                except self._bot.Zatrzymano:
                    raise
                except Exception as e:
                    self.log(f"depo: nie zamknąłem {k.get('nazwa')!r} ({e!r})")
        kon = self.kontenery()
        reszta = [k.get("nazwa") for k in kon if not _czy_glowny(k, kon)]
        if reszta and odejdz is not None:
            self.log(f"depo: okna {reszta} nadal otwarte, odchodzę od skrzyni")
            odejdz()
            time.sleep(1.0)
            kon = self.kontenery()
            reszta = [k.get("nazwa") for k in kon if not _czy_glowny(k, kon)]
        if reszta:
            raise SerwisBlad("depo", f"po składaniu zostały otwarte okna: {reszta}")

    def _depo_i_glowny_z_obrazem(self, m):
        """((okno, kontener) plecaka, (okno, kontener) depot chest, zrzut, z którego okna wzięto)."""
        obraz = self._zrzut(m)
        pary = self._okna_numery(obraz)
        kon = [k for _, k in pary]
        g = next(((o, k) for o, k in pary if _czy_glowny(k, kon)), None)
        d = next(((o, k) for o, k in pary if _nazwa(k) == "depot chest"), None)
        if g is None or d is None:
            raise SerwisBlad("depo", "brak okna plecaka albo depot chest na ekranie")
        return g, d, obraz

    def _depo_i_glowny(self, m):
        g, d, _ = self._depo_i_glowny_z_obrazem(m)
        return g, d

    def _sloty_rozjechane(self, obraz, okno, kontener):
        """Indeksy slotów okna, w których ekran i pamięć kontenera się nie zgadzają (zajęty/pusty). Bez zrzutu: brak oceny.
        Sloty ucięte dołem zrzutu pomijamy (13:13 invincible: sloty 16-19 depot chest na dole panelu dawały fałszywy rozjazd)."""
        if obraz is None:
            return []
        zajete = {q["slot"] for q in kontener.get("przedmioty", [])}
        return [i for i, s in enumerate(okno.sloty)
                if slot_w_pelni_widoczny(obraz, s) and (not self._slot_pusty(obraz, s)) != (i in zajete)]

    def _depo_i_glowny_spojne(self, m, proby=4):
        """Jak `_depo_i_glowny_z_obrazem`, ale okno depot chest musi zgadzać się z pamięcią co do zajętych slotów: bez tego cel
        upuszczenia liczymy z nieświeżych danych i można trafić w bag leżący w depo (22.10). Ponawia odczyt (pamięć klienta bywa
        o chwilę za ekranem); gdy rozjazd trwa, błąd zamiast przeciągania na ślepo."""
        rozjazd = []
        for p in range(proby):
            g, d, obraz = self._depo_i_glowny_z_obrazem(m)
            rozjazd = self._sloty_rozjechane(obraz, d[0], d[1])
            if not rozjazd:
                return g, d, obraz
            self.log(f"depo: ekran i pamięć depot chest różnią się w slotach {rozjazd} (odczyt {p + 1}/{proby}), czekam")
            time.sleep(0.6)
        raise SerwisBlad("depo", f"depot chest: ekran i pamięć klienta rozjeżdżają się w slotach {rozjazd}; nie przeciągam na ślepo "
                                 "(upuszczenie na kontener w depo wkłada przedmiot do jego środka)")

    def _slot_pusty(self, obraz, slot):
        """Czy slot jest pusty NA EKRANIE (obraz None = brak zrzutu, nie oceniamy: True)."""
        if obraz is None:
            return True
        import loot
        return loot.czy_pusty(obraz, slot)

    def _wolny_w_depo(self, obraz, okno, kontener):
        """Slot depot chest, na który wolno upuścić przedmiot (`bezpieczny_wolny_slot`): wolny w pamięci i na ekranie, nie przy bagu."""
        return bezpieczny_wolny_slot(okno, kontener, lambda s: self._slot_pusty(obraz, s),
                                     lambda s: slot_w_pelni_widoczny(obraz, s))

    def _poczekaj_na_skutek(self, num_z, num_d, ident, z_przed, d_przed):
        """(kontener źródła, kontener celu) z pamięci po przeciągnięciu `ident` o jedną sztukę; czeka do SKUTEK_CZEKAJ_S, aż
        źródło ma o 1 mniej, a cel o 1 więcej (pamięć klienta bywa o chwilę za ekranem). Zwraca ostatni odczyt, gdy skutku nie ma."""
        t0 = time.monotonic()
        while True:
            z_po, d_po = self._kontener(num_z), self._kontener(num_d)
            if z_po is not None and d_po is not None and _suma(z_po, {ident}) == z_przed - 1 and _suma(d_po, {ident}) == d_przed + 1:
                return z_po, d_po
            if time.monotonic() - t0 >= SKUTEK_CZEKAJ_S:
                return z_po, d_po
            time.sleep(SKUTEK_KROK_S)

    def _kontener(self, numer):
        return next((k for k in self.kontenery() if k.get("numer") == numer), None)

    def _przenies_do_depo(self, m, slot_zrodlowy):
        """Przeciąga przedmiot ze slotu plecaka na pierwsze wolne widoczne pole depot chest; weryfikacja na obu końcach."""
        (o_z, k_z), (o_d, k_d), obraz = self._depo_i_glowny_spojne(m)
        if slot_zrodlowy >= len(o_z.sloty):
            raise SerwisBlad("depo", f"slot {slot_zrodlowy} poza widocznym oknem plecaka")
        przedmiot = next((q for q in k_z.get("przedmioty", []) if q["slot"] == slot_zrodlowy), None)
        if przedmiot is None:
            raise SerwisBlad("depo", f"slot {slot_zrodlowy} plecaka jest pusty")
        # 22.10: cel nigdy nie jest slotem z kontenerem (upuszczenie na bag/plecak w depo wkłada przedmiot do jego środka)
        wolny = self._wolny_w_depo(obraz, o_d, k_d)
        if wolny is None:
            raise SerwisBlad("depo", "depot chest bez wolnego widocznego pola (wolne w pamięci i puste na ekranie)")
        ident = przedmiot["id"]
        z_przed, d_przed = _suma(k_z, {ident}), _suma(k_d, {ident})
        self._przeciagnij(m, o_z, slot_zrodlowy, o_d, wolny)
        z_po, d_po = self._poczekaj_na_skutek(k_z.get("numer"), k_d.get("numer"), ident, z_przed, d_przed)
        if z_po is not None and d_po is not None and _suma(z_po, {ident}) == z_przed - 1 and _suma(d_po, {ident}) == d_przed + 1:
            return
        raise SerwisBlad("depo", "przeciągnięcie do depo nie dało skutku na obu końcach: "
                         + self._opis_nieudanego_przeciagniecia(ident, z_przed, d_przed, z_po, d_po, wolny))

    @staticmethod
    def _opis_nieudanego_przeciagniecia(ident, z_przed, d_przed, z_po, d_po, slot_celu):
        """Precyzyjny komunikat zamiast zgadywania „spadł na podłogę” (22.10: ten sam symptom daje też wpadnięcie do kontenera w depo)."""
        if z_po is None or d_po is None:
            return "po przeciągnięciu zniknął z pamięci plecak albo depot chest (okno zamknięte?), nie wiadomo, gdzie jest przedmiot"
        z, d = _suma(z_po, {ident}), _suma(d_po, {ident})
        if z == z_przed and d == d_przed:
            return (f"przedmiot {ident} nie ruszył się z plecaka (upuszczenie na slot {slot_celu} nie zadziałało albo pamięć "
                    f"nie pokazała skutku w {SKUTEK_CZEKAJ_S:g} s)")
        if z == z_przed - 1 and d == d_przed:
            w_srodku = sorted(q["slot"] for q in d_po.get("przedmioty", []) if q["id"] in ID_BAGOW)
            return (f"przedmiot {ident} zniknął z plecaka ({z_przed} -> {z}), a w depot chest nie przybył ({d_przed} -> {d}); "
                    f"upuszczony na slot {slot_celu}: najpewniej wpadł do kontenera leżącego w depo (bag/plecak w slotach {w_srodku}) "
                    "albo leży na podłodze; pamięć klienta tego nie rozróżnia — sprawdź ręcznie, nie ponawiaj")
        return f"plecak {z_przed} -> {z}, depot chest {d_przed} -> {d} (przedmiot {ident}, cel slot {slot_celu}): skutek niezgodny z jedną sztuką"

    def _platinum_do_depo(self, m, zostaw):
        """Platinum ponad `zostaw` do depo: stos po stosie (na istniejący stos w depo, jeśli jest miejsce); ostatni, częściowy
        stos przez okno ilości. Każdy ruch weryfikowany na obu końcach."""
        for _ in range(6):
            (o_z, k_z), (o_d, k_d), obraz = self._depo_i_glowny_spojne(m)
            stosy = [q for q in k_z.get("przedmioty", []) if q["id"] == ID_PLATINUM and q["slot"] < len(o_z.sloty)]
            razem = _suma(k_z, {ID_PLATINUM})
            nadmiar = razem - zostaw
            if nadmiar <= 0 or not stosy:
                return
            stos = stosy[0]
            ile = stos.get("ilosc", 1)
            przenosi = min(ile, nadmiar)
            cel = next((q for q in k_d.get("przedmioty", []) if q["id"] == ID_PLATINUM and q.get("ilosc", 1) + przenosi <= 100
                        and q["slot"] < len(o_d.sloty)), None)
            slot_do = cel["slot"] if cel else self._wolny_w_depo(obraz, o_d, k_d)     # 22.10: nie na bag/plecak w depo
            if slot_do is None:
                raise SerwisBlad("depo", "depot chest bez wolnego widocznego pola na platinum")
            d_przed = _suma(k_d, {ID_PLATINUM})
            self._przeciagnij(m, o_z, stos["slot"], o_d, slot_do)
            if ile > 1 and not self._okno_ilosci(m, ile - przenosi, ile):
                raise SerwisBlad("depo", "okno ilości (Move Objects) się nie pojawiło")
            z_po, d_po = self._kontener(k_z.get("numer")), self._kontener(k_d.get("numer"))
            if z_po is None or d_po is None or _suma(z_po, {ID_PLATINUM}) != razem - przenosi \
                    or _suma(d_po, {ID_PLATINUM}) != d_przed + przenosi:
                raise SerwisBlad("depo", f"platinum: oczekiwano plecak {razem - przenosi}, depo {d_przed + przenosi}; "
                                          "przeniesienie nie dało skutku na obu końcach")

    # --- blanki do baga na runy ---

    def przenies_blanki(self):
        """Blanki z plecaka do bagu na runy (jedyny otwarty kontener-bag poza plecakiem); weryfikacja na obu końcach."""
        with self._mysz() as m:
            for _ in range(40):
                pary = self._okna_numery(self._zrzut(m))
                kon = [k for _, k in pary]
                glowny = next(((o, k) for o, k in pary if _czy_glowny(k, kon)), None)
                bagi = [(o, k) for o, k in pary if _czy_bag(k, kon)]
                if glowny is None or len(bagi) != 1:
                    raise SerwisBlad("blanki", f"oczekiwano jednego plecaka i jednego bagu na runy ({len(bagi)} bagów)")
                o_z, k_z = glowny
                o_d, k_d = bagi[0]
                zrodlo = [q for q in k_z.get("przedmioty", []) if q["id"] == ID_BLANK and q["slot"] < len(o_z.sloty)]
                if not zrodlo:
                    break
                wolny = wolny_slot(o_d, {q["slot"] for q in k_d.get("przedmioty", [])})
                if wolny is None:
                    raise SerwisBlad("blanki", "bag na runy pełny albo bez wolnego widocznego pola")
                z_przed, d_przed = _suma(k_z, {ID_BLANK}), _suma(k_d, {ID_BLANK})
                self._przeciagnij(m, o_z, zrodlo[0]["slot"], o_d, wolny)
                z_po, d_po = self._kontener(k_z.get("numer")), self._kontener(k_d.get("numer"))
                if z_po is None or d_po is None or _suma(z_po, {ID_BLANK}) != z_przed - 1 or _suma(d_po, {ID_BLANK}) != d_przed + 1:
                    raise SerwisBlad("blanki", "przeciągnięcie blanku do bagu nie dało skutku na obu końcach")
        glowny = self._glowny()
        if glowny and any(q["id"] == ID_BLANK for q in glowny.get("przedmioty", [])):
            raise SerwisBlad("blanki", "blanki zostały w plecaku")
        return True
