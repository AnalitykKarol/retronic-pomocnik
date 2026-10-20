"""Marsz klikiem w mapę: wspólne klocki serwisu (serwis.idz_pewnie, 19.10) i marszu wyprawy/„Wróć do miasta”
(wypad.Wypad._marsz_klik, 20.10, pokrętło WYPRAWA_MARSZ_KLIK).

Klient sam prowadzi postać ciągiem do klikniętego pola, kilka razy szybciej niż krok po kroku. Klikamy w NAJDALSZE pole
ścieżki w zasięgu widoku, do którego wszystkie pola są zwykłe (bez schodów, dziur i pól obok nich, bez ognia i zajętych),
potem sprawdzamy ruch. Moduł nie wie nic o grze: mapa, kliknięcie, zegar i przerwanie przychodzą z zewnątrz (atrapy w testach).
Zmiana piętra, brak ruchu i przerwanie (mob, PK, spadek HP) oddają sterowanie dotychczasowej logice wołającego."""
import time

KLIK_MAKS_POL = 5      # ile pól naprzód klikamy naraz (widok mapy ma ±7 x ±5 pól)
ZASIEG_KLIKU = (6, 4)  # |dx|, |dy| klikanego pola: widok ±7 x ±5 z zapasem 1 pola od krawędzi (poza widokiem ekran.klik_pola rzuca ValueError)
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


def dalej_klik(sciezka, koszt, z, maks=KLIK_MAKS_POL):
    """SERWIS (gęsta Dijkstra po polach): indeks najdalszego pola `sciezka` (lista (x, y, ...) od pozycji postaci), w które wolno
    kliknąć: kolejne pola aż do `maks`, każde zwykłe wg `koszt(x, y, z)`. 1 = nie ma co klikać (krok strzałką). Wyprawa używa
    gesta_sciezka + ile_pol_klik (rzadkie punkty nagrania, prostokąt z marginesem)."""
    dalej = 1
    while (dalej < len(sciezka) - 1 and dalej < maks
           and koszt(sciezka[dalej + 1][0], sciezka[dalej + 1][1], z) == ZWYKLE):
        dalej += 1
    return dalej


def gesta_sciezka_idx(poz, punkty, maks=KLIK_MAKS_POL, zasieg=ZASIEG_KLIKU):
    """Jak gesta_sciezka, ale -> lista ((x, y), i): `i` = indeks punktu w `punkty`, DO którego prowadzi odcinek zawierający to pole
    (potrzebny do oceny postępu po planie). Ścieżka kończy się też na pierwszym polu, które cofa się na pole `poz` albo na pole już na niej
    (plan z zawrotem / odbiciem): klik nie może prowadzić z powrotem."""
    z, prev, wynik, byly = poz[2], (poz[0], poz[1]), [], {(poz[0], poz[1])}
    for idx, q in enumerate(punkty):
        if len(q) > 2 and q[2] != z:
            break
        d = max(abs(q[0] - prev[0]), abs(q[1] - prev[1]))
        for i in range(1, d + 1):
            xy = (prev[0] + round(i * (q[0] - prev[0]) / d), prev[1] + round(i * (q[1] - prev[1]) / d))
            if abs(xy[0] - poz[0]) > zasieg[0] or abs(xy[1] - poz[1]) > zasieg[1] or xy in byly:
                return wynik
            wynik.append((xy, idx))
            byly.add(xy)
            if len(wynik) >= maks:
                return wynik
        if d:
            prev = (q[0], q[1])
    return wynik


def gesta_sciezka(poz, punkty, maks=KLIK_MAKS_POL, zasieg=ZASIEG_KLIKU):
    """Pola do przejścia po `punktach` odcinka (lista (x, y, z), zwykle zaczyna się od `poz`) jako ścieżka GĘSTA: kolejne pola są
    sąsiednie (Chebyshev 1), tego samego piętra co `poz`, w zasięgu kliku, bez powrotów na pole `poz` i bez powtórzeń. Rzadkie punkty
    nagrania (co 2+ pola) uzupełniamy linią prostą (każde pole pośrednie i tak sprawdzi `koszt_pola`). -> lista (x, y) BEZ pola `poz`,
    najwyżej `maks` pól; kończy się na pierwszym polu poza zasięgiem, na zawrocie albo na zmianie piętra."""
    return [xy for xy, _ in gesta_sciezka_idx(poz, punkty, maks, zasieg)]


def prostokat_czysty(mp, poz, pola, zakaz=()):
    """Klient wybiera własną drogę do klikniętego pola i przy obejściu przeszkody ma równorzędne objazdy po obu stronach, więc sprawdzamy
    prostokąt obejmujący postać i WSZYSTKIE `pola` ścieżki z marginesem 1 pola: żadnego pola z flagą 2 (schody, dziury, krzesła, nieznane
    przejścia: także koszt 6.0) ani z `zakaz` (zbiory (x, y): ogień, dziury nauczone). To samo pole `poz` jest pomijane."""
    z = poz[2]
    xs = [poz[0]] + [p[0] for p in pola]
    ys = [poz[1]] + [p[1] for p in pola]
    for x in range(min(xs) - 1, max(xs) + 2):
        for y in range(min(ys) - 1, max(ys) + 2):
            if (x, y) == (poz[0], poz[1]):
                continue
            if mp.flagi(x, y, z) & FLAGA_SCHODY or any((x, y) in zb for zb in zakaz):
                return False
    return True


def ile_pol_klik(mp, poz, pola, unik=(), zakaz=()):
    """Ile początkowych pól gęstej ścieżki `pola` wolno przejść jednym klikiem: każde pole zwykłe (koszt 1.0, bez `unik`: zajęte, ogień),
    a prostokąt całej ścieżki z marginesem 1 czysty (prostokat_czysty); skracamy do pierwszego spełnienia. < 2 = nie klikamy."""
    z = poz[2]
    k = 0
    while k < len(pola) and koszt_pola(mp, pola[k][0], pola[k][1], z, None, unik) == ZWYKLE:
        k += 1
    while k >= 2 and not prostokat_czysty(mp, poz, pola[:k], zakaz):
        k -= 1
    return k if k >= 2 else 0


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
