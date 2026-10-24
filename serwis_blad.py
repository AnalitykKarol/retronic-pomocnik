"""Wspólne drobiazgi serwisu (jeden moduł, żeby SerwisBlad nie istniał w dwóch kopiach przy `python3 serwis.py`)."""


class SerwisBlad(RuntimeError):
    """Krok serwisu nie powiódł się: alarm i STOP, bez ponawiania po cichu."""

    def __init__(self, krok, powod):
        super().__init__(f"{krok}: {powod}")
        self.krok = krok
        self.powod = powod


class BrakOdpowiedziNpc(SerwisBlad):
    """NPC nie odpowiedział na `hi` (23.10): za daleko albo odszedł. Podklasa SerwisBlad (krok „rozmowa”), więc stare łapanie
    SerwisBlad działa bez zmian; serwis rozpoznaje po niej jedyny przypadek, w którym warto podejść do NPC i spróbować jeszcze raz."""


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))
