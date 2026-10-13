"""Automatyczna wymiana pochodni: gdy pochodnia w slocie się wypali (albo slot jest pusty), bot wyrzuca
starą na podłogę, przenosi nową z plecaka do slotu i zapala ją (Use = Ctrl+klik, jak jedzenie).

Wykrywanie (tylko odczyt pamięci, kontenery.py komenda {"cmd":"kontenery","ekwipunek":true}):
  ekwipunek postaci to tablica ItemPtr[11] indeksowana numerem slotu Tibii; pochodnia leży w slocie
  SLOT_POCHODNI (10 = amunicja, prawy dolny róg panelu Inventory). Stan poznajemy po ID klienta:
    NOWA (niezapalona, taka jak w plecaku od NPC): 2920 - zweryfikowane w pamięci (plecak = slot po zakupie)
    ZAPALONA i WYPALONA: ID nie są pewne (na zrzutach pamięci widać zwolnione duchy 2925 i 2926, ale bez
    informacji, który jest który), więc bot UCZY SIĘ ich sam i zapisuje w pochodnia_ids.json:
      - po naszym Use ID w slocie zmienia się z NOWA na X  -> X = ZAPALONA
      - ID w slocie zmienia się z ZAPALONA na Y (nie NOWA, nie pusty) -> Y = WYPALONA
    Dopóki ID nieznane, bot nie rusza slotu z nieznanym ID (nie wyrzuci zapalonej pochodni).
    Slot pusty albo NOWA w slocie (niezapalona) obsługujemy od razu.
  Ręcznie można dopisać ID do pochodnia_ids.json: {"zapalona": [...], "wypalona": [...]}.

Wymiana (max 2 próby, potem 10 min przerwy; brak zapasowej pochodni: log raz):
  a) wypalona: przeciągnięcie ze slotu na pole gracza (podłoga pod postacią), kontrola odczytem, że slot pusty
  b) nowa z plecaka (okno plecaka dopasowane do pamięci jak w loot.zjedz) do slotu, kontrola odczytem
  c) Ctrl+klik na slocie (Use), kontrola odczytem, że ID się zmieniło (zapalona)
"""

import json
import random
import time
from pathlib import Path

KATALOG = Path(__file__).resolve().parent
PLIK_ID = KATALOG / "pochodnia_ids.json"

SLOT_POCHODNI = 10
ID_NOWA = {2920}
INTERWAL_S = 30.0
MAKS_PROB = 2
BLOKADA_S = 600.0
CZEKANIE_S = (0.6, 1.0)          # po przeciągnięciu / Use czekamy na odpowiedź serwera
ODCZYTY = 4                      # tyle razy (co ~0,3 s) czytamy pamięć, czekając na zmianę slotu


class BrakEkranu(Exception):
    """Nie widać na ekranie panelu Inventory albo okna plecaka (nie liczy się jako próba)."""


class Pochodnia:
    """Logika wymiany; operacje na ekranie i pamięci przez `ops` (atrapa w testach).

    ops: ekwipunek() -> {slot: id} albo None; zapas() -> (liczba pochodni w plecaku) albo None;
         przeciagnij_do_podlogi(); przeniesc_zapas_do_slotu(); uzyj_slot()  (mogą rzucić BrakEkranu).
    """

    def __init__(self, ops, zegar=time.monotonic, spij=time.sleep, log=print, plik=PLIK_ID,
                 interwal=INTERWAL_S, nie_lap=()):
        self.ops, self.zegar, self.spij, self.log = ops, zegar, spij, log
        self.plik, self.interwal = plik, interwal
        self.nie_lap = tuple(nie_lap)          # wyjątki (np. bot.Zatrzymano) przepuszczane dalej
        self.zapalona, self.wypalona = set(), set()
        self._wczytaj()
        self.nast = float("-inf")
        self.blokada_do = float("-inf")
        self.proby = 0
        self.ostatni = None                    # ID w slocie przy poprzednim odczycie (None: pusty)
        self.ostatni_znany = False
        self.brak_zapasu_zalogowano = False
        self.brak_odczytu_zalogowano = False
        self.nieznane_zalogowano = None
        self.wymian = 0

    # --- ID uczone w locie ---

    def _wczytaj(self):
        try:
            d = json.loads(Path(self.plik).read_text())
            self.zapalona = {int(i) for i in d.get("zapalona", [])}
            self.wypalona = {int(i) for i in d.get("wypalona", [])}
        except (OSError, ValueError, AttributeError, TypeError):
            pass

    def _zapisz(self):
        try:
            Path(self.plik).write_text(json.dumps(
                {"zapalona": sorted(self.zapalona), "wypalona": sorted(self.wypalona)}, indent=1))
        except OSError as e:
            self.log(f"pochodnia: nie zapisałem ID ({e})")

    def stan(self, ident):
        if ident is None:
            return "pusty"
        if ident in ID_NOWA:
            return "nowa"
        if ident in self.zapalona:
            return "zapalona"
        if ident in self.wypalona:
            return "wypalona"
        return "nieznana"

    def _ucz_sie(self, ident):
        """Przejście ZAPALONA -> inne ID (nie nowa) w slocie bez naszego udziału = pochodnia się wypaliła."""
        pop = self.ostatni
        if (self.ostatni_znany and pop is not None and pop != ident and pop in self.zapalona
                and ident is not None and ident not in ID_NOWA and ident not in self.zapalona
                and ident not in self.wypalona):
            self.wypalona.add(ident)
            self._zapisz()
            self.log(f"pochodnia: wypaliła się, ID {ident} = wypalona (zapisane)")

    # --- odczyt ---

    def _slot(self):
        """(odczyt się udał, ID w slocie albo None)."""
        try:
            e = self.ops.ekwipunek()
        except self.nie_lap:
            raise
        except Exception as ex:
            if not self.brak_odczytu_zalogowano:
                self.log(f"pochodnia: odczyt ekwipunku nie działa ({ex!r})")
                self.brak_odczytu_zalogowano = True
            return False, None
        if e is None:
            if not self.brak_odczytu_zalogowano:
                self.log("pochodnia: nie widzę ekwipunku w pamięci (brak żywych przedmiotów w slotach?)")
                self.brak_odczytu_zalogowano = True
            return False, None
        self.brak_odczytu_zalogowano = False
        return True, e.get(SLOT_POCHODNI, e.get(str(SLOT_POCHODNI)))

    def _czekaj_na_slot(self, ocz, nazwa):
        """Czyta slot po akcji aż spełni ocz(id) (maks. ODCZYTY razy). Zwraca (spelnione, ostatnie ID)."""
        ident = None
        for _ in range(ODCZYTY):
            self.spij(random.uniform(*CZEKANIE_S) / 2)
            ok, ident = self._slot()
            if ok and ocz(ident):
                return True, ident
        return False, ident

    # --- wymiana ---

    def _wymien(self, stan):
        """Jedna próba; True gdy pochodnia zapalona. BrakEkranu przepuszczamy do wywołującego."""
        if stan == "wypalona":
            self.log(f"pochodnia: wyrzucam wypaloną (slot {SLOT_POCHODNI})")
            self.ops.przeciagnij_do_podlogi()
            ok, _ = self._czekaj_na_slot(lambda i: i is None, "pusty")
            if not ok:
                self.log("pochodnia: wypalona nie zniknęła ze slotu")
                return False
            stan = "pusty"
        if stan == "pusty":
            self.log("pochodnia: wkładam nową z plecaka")
            self.ops.przeniesc_zapas_do_slotu()
            ok, _ = self._czekaj_na_slot(lambda i: i in ID_NOWA, "nowa")
            if not ok:
                self.log("pochodnia: nowa nie trafiła do slotu")
                return False
            stan = "nowa"
        # stan == "nowa": zapalamy
        self.ops.uzyj_slot()
        ok, ident = self._czekaj_na_slot(lambda i: i is not None and i not in ID_NOWA, "zapalona")
        if not ok:
            self.log("pochodnia: po Use pochodnia dalej niezapalona")
            return False
        if ident not in self.zapalona and ident not in self.wypalona:
            self.zapalona.add(ident)
            self._zapisz()
            self.log(f"pochodnia: zapalona, ID {ident} = zapalona (zapisane)")
        elif ident in self.wypalona:
            self.log(f"pochodnia: po Use w slocie ID {ident} z listy wypalonych, nie zapaliła się")
            return False
        else:
            self.log("pochodnia: zapalona")
        return True

    def tick(self, teraz=None, bezpiecznie=True):
        """Wołane z pętli bota. True, gdy wykonano akcję na ekranie (bot ma pauzę przed następnym krokiem)."""
        teraz = self.zegar() if teraz is None else teraz
        if not bezpiecznie or teraz < self.nast or teraz < self.blokada_do:
            return False
        self.nast = teraz + self.interwal
        ok, ident = self._slot()
        if not ok:
            return False
        self._ucz_sie(ident)
        self.ostatni, self.ostatni_znany = ident, True
        stan = self.stan(ident)
        if stan == "zapalona":
            self.proby = 0
            return False
        if stan == "nieznana":
            if self.nieznane_zalogowano != ident:
                self.nieznane_zalogowano = ident
                self.log(f"pochodnia: w slocie {SLOT_POCHODNI} nieznane ID {ident}, nie ruszam "
                         "(po pierwszym Use/wypaleniu bot sam się nauczy)")
            return False
        if stan in ("pusty", "wypalona"):
            try:
                zapas = self.ops.zapas()
            except self.nie_lap:
                raise
            except Exception as ex:
                self.log(f"pochodnia: odczyt plecaka nie działa ({ex!r})")
                return False
            if not zapas:
                if not self.brak_zapasu_zalogowano:
                    self.log("pochodnia: brak pochodni" + (" (zapas w plecaku)" if zapas == 0 else
                                                           " (nie widzę plecaka w pamięci)"))
                    self.brak_zapasu_zalogowano = True
                return False
            self.brak_zapasu_zalogowano = False
        try:
            wynik = self._wymien(stan)
        except self.nie_lap:
            raise
        except BrakEkranu as e:
            self.log(f"pochodnia: {e}, spróbuję później")
            return False
        except Exception as e:
            self.log(f"pochodnia: błąd {e!r}")
            wynik = False
        if wynik:
            self.proby = 0
            self.wymian += 1
            ok, ident = self._slot()
            self.ostatni = ident if ok else self.ostatni
            return True
        self.proby += 1
        if self.proby >= MAKS_PROB:
            self.log(f"pochodnia: {MAKS_PROB} nieudane próby, przerwa {BLOKADA_S / 60:.0f} min")
            self.blokada_do = teraz + BLOKADA_S
            self.proby = 0
        return True


# --- operacje na żywo (ekran + pamięć) ---------------------------------------

def pozycje_ekwipunku(obraz):
    """Środki slotów panelu Inventory na zrzucie: {numer slotu Tibii: (x, y)} albo {}.
    Układ 3 kolumny (naszyjnik/lewa ręka/pierścień | głowa/zbroja/nogi/buty | plecak/prawa ręka/amunicja);
    kotwica: slot głowy = slot, który ma sąsiadów +-36/37 px w bok i +13 px w dół (okno kontenera nie ma)."""
    import numpy as np  # noqa: PLC0415

    import loot  # noqa: PLC0415
    a = np.asarray(obraz.convert("RGB")).astype(np.int16)
    sloty = loot._sloty(loot._maska_ramki(a), obraz.size[0])
    pola = {(s.x, s.y) for s in sloty}
    for s in sloty:
        lewy = next((q for q in pola if 35 <= s.x - q[0] <= 38 and 12 <= q[1] - s.y <= 14), None)
        prawy = next((q for q in pola if 35 <= q[0] - s.x <= 38 and 12 <= q[1] - s.y <= 14), None)
        if lewy and prawy:
            bok = s.bok
            xl, xs, xp = lewy[0], s.x, prawy[0]
            y0 = s.y
            yb = lewy[1]                     # wiersz boczny 1 (naszyjnik/plecak)
            krok = 36
            def c(x, y):
                return x + bok // 2, y + bok // 2
            return {1: c(xs, y0), 2: c(xl, yb), 3: c(xp, yb),
                    4: c(xs, y0 + krok), 5: c(xp, yb + krok), 6: c(xl, yb + krok),
                    7: c(xs, y0 + 2 * krok), 8: c(xs, y0 + 3 * krok),
                    9: c(xl, yb + 2 * krok), 10: c(xp, yb + 2 * krok)}
    return {}


class OperacjeZywe:
    """Ekran (XTEST przez ekran.Mysz, zrzut grim) + odczyt pamięci przez gniazdo."""

    def __init__(self, zapytaj=None, log=print):
        import bot  # noqa: PLC0415
        self.zapytaj = zapytaj or bot.zapytaj
        self.log = log

    def ekwipunek(self):
        odp = self.zapytaj({"cmd": "kontenery", "ekwipunek": True})
        if odp.get("blad"):
            raise RuntimeError(odp["blad"])
        e = odp.get("ekwipunek")
        if e is None:
            return None
        return {int(s): v["id"] for s, v in e.items()}

    def _kontenery(self):
        odp = self.zapytaj({"cmd": "kontenery"})
        return odp.get("kontenery") or []

    def zapas(self):
        """Liczba pochodni (ID_NOWA) w plecakach gracza w pamięci; None, gdy brak otwartego plecaka."""
        import loot  # noqa: PLC0415
        plecaki = [k for k in self._kontenery() if loot.czy_plecak(k)]
        if not plecaki:
            return None
        return sum(1 for k in plecaki for p in k.get("przedmioty", []) if p["id"] in ID_NOWA)

    def _mysz(self):
        import ekran  # noqa: PLC0415
        return ekran.Mysz()

    def _zrzut(self, mysz):
        import loot  # noqa: PLC0415
        return loot._zrzut(mysz)

    def _slot_ekw(self, obraz):
        poz = pozycje_ekwipunku(obraz).get(SLOT_POCHODNI)
        if poz is None:
            raise BrakEkranu("nie widzę panelu Inventory")
        return poz

    def _zapas_na_ekranie(self, obraz):
        import loot  # noqa: PLC0415
        okna = loot.znajdz_okna(obraz)
        kontenery, powod = loot.kontenery_z_pamieci()
        if kontenery is None:
            raise BrakEkranu(f"pamięć: {powod}")
        przypisane, powod = loot.dopasuj_okna(obraz, okna, kontenery)
        if przypisane is None:
            raise BrakEkranu(f"okna plecaka: {powod}")
        for o, k in zip(okna, przypisane):
            if not loot.czy_plecak(k):
                continue
            for p in k.get("przedmioty", []):
                if p["id"] in ID_NOWA and p["slot"] < len(o.sloty):
                    return o.sloty[p["slot"]].srodek
        raise BrakEkranu("nie widzę okna plecaka z pochodnią")

    def przeciagnij_do_podlogi(self):
        import ekran  # noqa: PLC0415
        with self._mysz() as mysz:
            obraz = self._zrzut(mysz)
            x, y = self._slot_ekw(obraz)
            cel = ekran.pole_na_ekran(0, 0, ekran.aktualny_prostokat(mysz.ekran))
            mysz.przeciagnij(x, y, *cel, drganie=3)

    def przeniesc_zapas_do_slotu(self):
        with self._mysz() as mysz:
            obraz = self._zrzut(mysz)
            cel = self._slot_ekw(obraz)
            zrodlo = self._zapas_na_ekranie(obraz)
            mysz.przeciagnij(*zrodlo, *cel, drganie=3)

    def uzyj_slot(self):
        with self._mysz() as mysz:
            obraz = self._zrzut(mysz)
            x, y = self._slot_ekw(obraz)
            mysz.klik(x, y, 1, "Control_L", drganie=3)


def zywa(log=print):
    """Pochodnia z operacjami na żywo; wyjątek zatrzymania bota przepuszczany."""
    import bot  # noqa: PLC0415
    return Pochodnia(OperacjeZywe(log=log), log=log, nie_lap=(bot.Zatrzymano,))
