"""Wspólne drobiazgi serwisu (jeden moduł, żeby SerwisBlad nie istniał w dwóch kopiach przy `python3 serwis.py`)."""


class SerwisBlad(RuntimeError):
    """Krok serwisu nie powiódł się: alarm i STOP, bez ponawiania po cichu."""

    def __init__(self, krok, powod):
        super().__init__(f"{krok}: {powod}")
        self.krok = krok
        self.powod = powod


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))
