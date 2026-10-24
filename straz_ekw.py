"""Straż ekwipunku (23.10, Karol: lina invincible znikła ze slotu 10, gold wydry wpadał na slot 10).

Dwie rzeczy, obie bez żadnego inputu do gry:
1. `ocen_cel(obraz, cel)` - przed KAŻDYM przeciągnięciem lootu/serwisu: środek celu musi leżeć na slocie okna kontenera
   (znajdz_okna) na ŚWIEŻYM zrzucie i nie na slocie panelu Inventory (pochodnia.pozycje_ekwipunku). Inaczej odmowa.
2. `Straznik` - przed/po przeciągnięciu czyta ekwipunek z pamięci (komenda "kontenery" z "ekwipunek": true) i gdy
   którykolwiek slot się zmienił, loguje `[EKW] ...` i wysyła zwykłe powiadomienie (najwyżej raz na ODSTEP_POWIADOMIEN_S).
   Brak odczytu (tablica ekwipunku niedostępna) = cisza, loot działa jak dotąd; po porażce odczytu nie pytamy ponownie
   przez PO_PORAZCE_S (skan pamięci blokuje rdzeń), tak jak robi to rdzeń.

Nic tu nie przenosi przedmiotów: lina w slocie 10 jest dozwolona i zostaje tam, gdzie leży."""
import time

POLOWA_SLOTU = 17            # BOK_SLOTU / 2
MARGINES_PX = 4              # drganie przeciągnięcia (+-4 px) mieści się w slocie
ODSTEP_POWIADOMIEN_S = 600.0
PO_PORAZCE_S = 300.0
POWIADOM = None              # testy: podmieniają (tytul, tresc, pilnosc, klucz); None = powiadom.powiadom
ZEGAR = time.monotonic

_ostatnie_powiadomienie = {}


def powiadom(tytul, tresc, klucz):
    """Zwykłe powiadomienie, najwyżej raz na ODSTEP_POWIADOMIEN_S na klucz. Nigdy nie rzuca."""
    teraz = ZEGAR()
    if teraz - _ostatnie_powiadomienie.get(klucz, -1e12) < ODSTEP_POWIADOMIEN_S:
        return False
    _ostatnie_powiadomienie[klucz] = teraz
    try:
        if POWIADOM is not None:
            POWIADOM(tytul, tresc, "normal", klucz)
        else:
            import powiadom as modul  # noqa: PLC0415
            modul.powiadom(tytul, tresc, "normal", klucz)
    except Exception:
        return False
    return True


def sloty_ekwipunku(obraz):
    """{numer slotu Tibii: (x, y)} panelu Inventory na zrzucie albo {} (nie widać panelu / błąd)."""
    try:
        import pochodnia  # noqa: PLC0415
        return pochodnia.pozycje_ekwipunku(obraz) or {}
    except Exception:
        return {}


def _na_slocie(cel, xy):
    return abs(cel[0] - xy[0]) <= POLOWA_SLOTU + MARGINES_PX and abs(cel[1] - xy[1]) <= POLOWA_SLOTU + MARGINES_PX


def ocen_cel(obraz, cel):
    """(True, None) gdy `cel` (x, y) jest bezpiecznym miejscem upuszczenia, inaczej (False, powód).
    Bezpieczne = środek slotu któregoś okna kontenera na tym zrzucie i NIE slot ekwipunku."""
    for numer, xy in sorted(sloty_ekwipunku(obraz).items()):
        if _na_slocie(cel, xy):
            return False, f"cel {tuple(cel)} leży na slocie ekwipunku {numer} ({tuple(xy)})"
    try:
        import loot  # noqa: PLC0415
        okna = loot.znajdz_okna(obraz)
    except Exception as ex:
        return True, f"nie umiem sprawdzić okien ({ex!r})"       # nie blokujemy lootu błędem detekcji; [EKW] po fakcie złapie skutek
    for o in okna:
        if any(_na_slocie(cel, s.srodek) for s in o.sloty):
            return True, None
    return False, f"cel {tuple(cel)} leży poza slotami okna kontenera (okien na zrzucie: {len(okna)})"


def ekwipunek_z_pamieci(zapytaj):
    """{slot: (id, ilosc)} albo None, gdy odczytu nie ma. `zapytaj` jak bot.zapytaj / loot._zapytaj."""
    try:
        odp = zapytaj({"cmd": "kontenery", "ekwipunek": True})
    except Exception:
        return None
    if not isinstance(odp, dict) or odp.get("blad"):
        return None
    e = odp.get("ekwipunek")
    if not isinstance(e, dict):
        return None
    wynik = {}
    for s, v in e.items():
        try:
            wynik[int(s)] = (int((v or {}).get("id")), int((v or {}).get("ilosc", 1)))
        except (TypeError, ValueError):
            continue
    return wynik


def _opis(w):
    return "pusty" if w is None else f"ID {w[0]} x{w[1]}"


def zmiany(przed, po):
    """Lista opisów zmienionych slotów ('slot 10: ID 3003 x1 -> pusty'); [] gdy któryś odczyt jest None."""
    if przed is None or po is None:
        return []
    return [f"slot {s}: {_opis(przed.get(s))} -> {_opis(po.get(s))}"
            for s in sorted(set(przed) | set(po)) if przed.get(s) != po.get(s)]


class Straznik:
    """Porównuje ekwipunek między kolejnymi `przed()`/`po()`. Jeden egzemplarz na jedną sesję zbierania."""

    def __init__(self, zapytaj, log=print, etykieta="loot"):
        self.zapytaj, self.log, self.etykieta = zapytaj, log, etykieta
        self.stan = None
        self._porazka = -1e12

    def _odczyt(self):
        if ZEGAR() - self._porazka < PO_PORAZCE_S:
            return None
        e = ekwipunek_z_pamieci(self.zapytaj)
        if e is None:
            self._porazka = ZEGAR()
        return e

    def przed(self):
        """Zapamiętuje ekwipunek tuż przed ruchem (przy braku odczytu stan None = bez porównania)."""
        self.stan = self._odczyt()
        return self.stan

    def po(self, co):
        """Porównuje z `przed()`/poprzednim `po()`. Zwraca listę zmian ([] gdy brak albo brak odczytu)."""
        if self.stan is None:
            self.stan = self._odczyt()
            return []
        teraz = self._odczyt()
        if teraz is None:
            return []
        z = zmiany(self.stan, teraz)
        self.stan = teraz
        if z:
            opis = "; ".join(z)
            self.log(f"[EKW] {self.etykieta}: po ruchu '{co}' zmienił się ekwipunek: {opis}")
            powiadom("Ekwipunek zmienił się po przeciągnięciu", f"{self.etykieta} '{co}': {opis}", "ekw_zmiana")
        return z


def odmowa(log, co, powod, etykieta="loot"):
    """Wspólny log + zwykłe powiadomienie przy odmowie przeciągnięcia."""
    log(f"[EKW] {etykieta}: nie przeciągam '{co}': {powod}")
    powiadom("Nie przeciągnąłem przedmiotu", f"{etykieta} '{co}': {powod}", "ekw_odmowa")
