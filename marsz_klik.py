"""Marsz klikiem w mapę: wspólne klocki serwisu (serwis.idz_pewnie, 19.10) i marszu wyprawy/„Wróć do miasta”
(wypad.Wypad._marsz_klik, 20.10, pokrętło WYPRAWA_MARSZ_KLIK).

Klient sam prowadzi postać ciągiem do klikniętego pola, kilka razy szybciej niż krok po kroku. Klikamy w NAJDALSZE pole
ścieżki w zasięgu widoku, do którego wszystkie pola są zwykłe (bez schodów, dziur i pól obok nich, bez ognia i zajętych),
potem sprawdzamy ruch. Moduł nie wie nic o grze: mapa, kliknięcie, zegar i przerwanie przychodzą z zewnątrz (atrapy w testach).
Zmiana piętra, brak ruchu i przerwanie (mob, PK, spadek HP) oddają sterowanie dotychczasowej logice wołającego."""
import time

KLIK_MAKS_POL = 5      # ile pól naprzód klikamy naraz (widok mapy ma ±7 x ±5 pól)
ZWYKLE = 1.0           # koszt zwykłego pola
FLAGA_CHODLIWE, FLAGA_SCHODY, FLAGA_BLOK = 1, 2, 4


class Czas:
    """Zegar i sen z funkcji (cb.zegar / cb.spij) w kształcie modułu `time`, którego oczekuje klik_i_czekaj."""

    def __init__(self, zegar, spij):
        self._zegar, self._spij = zegar, spij

    def monotonic(self):
        return self._zegar()

    def time(self):
        return self._zegar()

    def sleep(self, s):
        self._spij(s)


def koszt_pola(mp, x, y, z, cel=None, unik=()):
    """None = nie wchodzimy; 1.0 = zwykłe pole; 6.0 = pole z flagą 2 bez odpowiednika piętro obok (krzesło, mebel: może być
    szum mapy, może przejście pięter). `cel` = (x, y) pola docelowego (zawsze 1.0), `unik` = zbiór (x, y) do ominięcia."""
    if cel is not None and (x, y) == (cel[0], cel[1]):
        return ZWYKLE
    f = mp.flagi(x, y, z)
    if not (f & FLAGA_CHODLIWE) or (f & FLAGA_BLOK) or (x, y) in unik:
        return None
    if f & FLAGA_SCHODY:
        # schody/dziury mają odpowiednik z flagą 2 na piętrze nad lub pod; krzesła i meble go nie mają (wtedy chodzimy)
        for zz in (z - 1, z + 1):
            for ddx in (-1, 0, 1):
                for ddy in (-1, 0, 1):
                    if mp.flagi(x + ddx, y + ddy, zz) & FLAGA_SCHODY:
                        return None
        return 6.0
    return ZWYKLE


def dalej_klik(sciezka, koszt, z, maks=KLIK_MAKS_POL, pierwsze_zwykle=False):
    """Indeks najdalszego pola `sciezka` (lista (x, y, ...) od pozycji postaci), w które wolno kliknąć: kolejne pola aż do
    `maks`, każde zwykłe wg `koszt(x, y, z)`. 1 = nie ma co klikać (krok strzałką). `pierwsze_zwykle`: także pole nr 1 musi
    być zwykłe (serwis go nie sprawdza, bo plan Dijkstry dopuszcza w nim pole z kosztem 6)."""
    if pierwsze_zwykle and len(sciezka) > 1 and koszt(sciezka[1][0], sciezka[1][1], z) != ZWYKLE:
        return 1
    dalej = 1
    while (dalej < len(sciezka) - 1 and dalej < maks
           and koszt(sciezka[dalej + 1][0], sciezka[dalej + 1][1], z) == ZWYKLE):
        dalej += 1
    return dalej


def klik_i_czekaj(postac, poz, cel_kl, dalej, zegar=time, log=print, przerwij=None, przerwij_co=3, prefiks="marsz klikiem"):
    """Po kliku w `cel_kl` (pole nr `dalej` ścieżki): czeka na ruch do ok. 0,8 + 0,45 s na pole. `przerwij(poz)` (opcjonalne,
    co `przerwij_co`-ty odczyt) zwraca True, gdy trzeba przerwać marsz (mob, PK, spadek HP).
    -> "pietro" (zmiana piętra), "przerwano", "ruch" (postać zmieniła pole) albo "bez_ruchu" (klik nic nie ruszył)."""
    t1, ost, stoi, n = zegar.monotonic(), poz, 0, 0
    while zegar.monotonic() - t1 < 0.8 + 0.45 * dalej:
        zegar.sleep(0.12)
        teraz_poz = tuple(postac.pozycja())
        if teraz_poz[2] != poz[2]:
            log(f"{prefiks}: klik na {cel_kl} zmienił piętro ({poz[2]} -> {teraz_poz[2]})")
            return "pietro"
        if teraz_poz[:2] == cel_kl[:2]:
            break
        stoi = stoi + 1 if teraz_poz == ost else 0
        ost = teraz_poz
        if stoi >= 4 and teraz_poz != poz:
            break
        if stoi >= 6:
            break
        n += 1
        if przerwij is not None and n % przerwij_co == 0 and przerwij(teraz_poz):
            return "przerwano"
    if tuple(postac.pozycja())[:2] != poz[:2]:
        return "ruch"
    return "bez_ruchu"
