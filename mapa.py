#!/usr/bin/env python3
"""Pełna mapa serwera z pliku minimapy OTClienta (mapa/map74.otmm): które pola są przechodnie
i najkrótsza droga po nich (A* na kubełkach). Bloki 64x64 rozpakowujemy dopiero przy pierwszym
użyciu (~0,1 ms na blok), więc start to tylko spis bloków (~40 ms), a zapytanie o pole to
koszt ok. 4 pustych wywołań funkcji.

  mapa.py pole <x> <y> <z>                       flagi, kolor i prędkość pola
  mapa.py droga <x1> <y1> <z> <x2> <y2> [dlugosc] droga z pola 1 do pola przy polu 2
  mapa.py podglad <z> <x> <y> <promien> <plik.png> [trasa]   obraz wycinka (z trasą)

Format OTMM: "OTMM", u16 początek danych, u16 wersja, u32 flagi, u16+opis; dalej bloki:
u16 x, u16 y, u8 z, u16 rozmiar, zlib -> 64*64 pól po 3 bajty (flagi, kolor, prędkość);
koniec przy x == 0xFFFF. Flagi pola (sprawdzone na żywo):
  1 = pole widziane (0 = nigdy nie widziane, wtedy nic o nim nie wiemy)
  2 = OTClient nie prowadzi tędy drogi: prawie zawsze schody/dziury/rampy (kolor 210, żółty),
      czasem pole z polem magicznym albo przedmiotem blokującym pathfinding
  4 = nie da się przejść (ściana, woda, kamień)
"""

import struct
import sys
import time
import zlib
from pathlib import Path

sys.dont_write_bytecode = True

PLIK_MAPY = Path(__file__).resolve().parent / "mapa" / "map74.otmm"
KATALOG_TRAS = Path(__file__).resolve().parent / "trasy"
WIDZIANE, BEZ_DROGI, SCIANA = 1, 2, 4
KOLOR_SCHODOW = 210                # żółty na minimapie Tibii = zmiana piętra
DROGA_LIMIT = 20000                # maks. rozwiniętych pól A* (droga 30 pól to zwykle < 1000)
_K = 1 << 17                       # klucz pola w droga(): x*_K + y, jak w cavebot.py
_BRAK = object()


def _klucz_bloku(x, y, z):
    return (z << 20) | ((x >> 6) << 10) | (y >> 6)


class Mapa:
    def __init__(self, plik=PLIK_MAPY):
        dane = Path(plik).read_bytes()
        if dane[:4] != b"OTMM":
            raise ValueError(f"{plik}: to nie jest plik OTMM")
        poczatek, self.wersja = struct.unpack_from("<HH", dane, 4)
        self._dane = dane
        self._spis = {}                # klucz bloku -> (offset, rozmiar) skompresowanych danych
        off = poczatek
        while off + 2 <= len(dane):
            x, = struct.unpack_from("<H", dane, off)
            if x == 0xFFFF:
                break
            y, z, rozmiar = struct.unpack_from("<HBH", dane, off + 2)
            self._spis[_klucz_bloku(x, y, z)] = (off + 7, rozmiar)
            off += 7 + rozmiar
        self._bloki = {}               # klucz bloku -> bytes 64*64*3 albo None (brak bloku)

    def _blok(self, kb):
        """Rozpakowany blok (bytes) albo None, gdy pliku nie ma tego bloku."""
        b = self._bloki.get(kb, _BRAK)
        if b is _BRAK:
            m = self._spis.get(kb)
            b = zlib.decompress(self._dane[m[0]:m[0] + m[1]]) if m else None
            self._bloki[kb] = b
        return b

    @property
    def bloki(self):
        return len(self._spis)

    def pole(self, x, y, z):
        """(flagi, kolor, prędkość) albo None, gdy pole leży poza zapisanymi blokami."""
        b = self._blok(_klucz_bloku(x, y, z))
        if b is None:
            return None
        i = ((y & 63) * 64 + (x & 63)) * 3
        return b[i], b[i + 1], b[i + 2]

    def flagi(self, x, y, z):
        """Same flagi pola (0 = niewidziane albo brak bloku). Najszybsze zapytanie."""
        b = self._bloki.get((z << 20) | ((x >> 6) << 10) | (y >> 6), _BRAK)
        if b is _BRAK:
            b = self._blok(_klucz_bloku(x, y, z))
        return b[((y & 63) * 64 + (x & 63)) * 3] if b is not None else 0

    def przechodnie(self, x, y, z):
        """True = da się wejść, False = ściana/woda, None = pole niewidziane (nic nie wiemy).
        Schody/dziury (flaga 2) są przechodnie - do omijania służy schody_lub_dziura()."""
        f = self.flagi(x, y, z)
        if not f & WIDZIANE:
            return None
        return not f & SCIANA

    def schody_lub_dziura(self, x, y, z):
        """True, gdy wejście na pole może zmienić piętro (flaga 2: OTClient nie prowadzi tędy drogi).
        None dla pola niewidzianego."""
        f = self.flagi(x, y, z)
        if not f & WIDZIANE:
            return None
        return bool(f & BEZ_DROGI)

    def droga(self, start, cel, zajete=(), dlugosc=1, skosy=True, limit=DROGA_LIMIT,
              schody=False, nieznane=False, znane=None, przepusc=None):
        """Najkrótsza droga po mapie piętra start=(x,y,z) do najbliższego pola, z którego do
        cel=(x,y[,z]) jest <= dlugosc (Chebyshev). `przepusc` (zbiór kluczy x*_K+y): pola przechodnie mimo ściany
        w mapie (drzwi, R1c). Krok prosty kosztuje 1, skos 3 (jak w cavebot).
        Pola z `zajete` ((x,y) albo (x,y,z)) omijamy; schody/dziury (flaga 2) tylko gdy schody=True,
        pola niewidziane tylko gdy nieznane=True albo gdy ich klucz x*_K+y jest w `znane` (pola, na
        których stał gracz, a minimapa ich nie ma). Zwraca listę pól (x,y,z) bez startu
        ([] = już przy celu) albo None, gdy drogi nie ma w `limit` rozwiniętych pól."""
        sx, sy, z = start[0], start[1], start[2]
        cx, cy = cel[0], cel[1]
        if max(abs(sx - cx), abs(sy - cy)) <= dlugosc:
            return []
        blok = {p[0] * _K + p[1] for p in zajete if len(p) < 3 or p[2] == z}
        zle = SCIANA | (0 if schody else BEZ_DROGI)
        bloki, blok_mapy = self._bloki, self._blok
        zz = z << 20
        dozwolone = {}                 # klucz pola -> bool (pamięć w obrębie jednego szukania)

        def wolne(k):
            w = dozwolone.get(k)
            if w is None:
                y = (k + _K // 2) % _K - _K // 2
                x = (k - y) // _K
                b = bloki.get(zz | ((x >> 6) << 10) | (y >> 6), _BRAK)
                if b is _BRAK:
                    b = blok_mapy(zz | ((x >> 6) << 10) | (y >> 6))
                f = b[((y & 63) * 64 + (x & 63)) * 3] if b is not None else 0
                w = (bool(f & WIDZIANE) or nieznane or (znane is not None and k in znane)) \
                    and not f & zle and k not in blok
                if not w and przepusc and k in przepusc and k not in blok:
                    w = True
                dozwolone[k] = w
            return w

        def h(k):                      # dolne oszacowanie kosztu do kwadratu celu (spójne)
            y = (k + _K // 2) % _K - _K // 2
            x = (k - y) // _K
            return max(0, abs(x - cx) - dlugosc) + max(0, abs(y - cy) - dlugosc)

        ruchy = ((_K, 1), (-_K, 1), (1, 1), (-1, 1))
        if skosy:
            ruchy += ((_K + 1, 3), (_K - 1, 3), (-_K + 1, 3), (-_K - 1, 3))
        s = sx * _K + sy
        skad, koszt = {s: None}, {s: 0}
        f0 = h(s)
        kubly, i, gotowe = {f0: [s]}, f0, 0
        koniec = f0 + 4 * limit
        while gotowe < limit and i <= koniec:
            kubel = kubly.get(i)
            if not kubel:
                kubly.pop(i, None)
                if not kubly:
                    break
                i += 1
                continue
            k = kubel.pop()               # LIFO: w obrębie kubełka najpierw najświeższe (głębsze)
            g = koszt[k]
            hk = h(k)
            if g + hk != i:
                continue                  # wpis nieaktualny (pole dostało tańszą drogę)
            gotowe += 1
            if hk == 0 and k != s:
                wynik = []
                while k != s:
                    y = (k + _K // 2) % _K - _K // 2
                    wynik.append(((k - y) // _K, y, z))
                    k = skad[k]
                return wynik[::-1]
            for d, c in ruchy:
                n = k + d
                gn = g + c
                if gn < koszt.get(n, 1 << 30) and wolne(n):
                    koszt[n], skad[n] = gn, k
                    fn = gn + h(n)
                    kubly.setdefault(fn, []).append(n)
        return None


_mapa = None


def mapa():
    """Wspólna instancja (wczytana przy pierwszym użyciu); None, gdy pliku mapy nie ma."""
    global _mapa
    if _mapa is None and PLIK_MAPY.is_file():
        _mapa = Mapa(PLIK_MAPY)
    return _mapa


# --- podgląd ---

def _kolor_tibii(c):
    """Kolor minimapy Tibii (paleta 6x6x6) jako RGB; 255 = brak koloru (lita skała)."""
    if c >= 216:
        return (28, 28, 34)
    return (c // 36 % 6 * 51, c // 6 % 6 * 51, c % 6 * 51)


def _zapisz_png(plik, szer, wys, wiersze):
    def kawalek(typ, dane):
        return (struct.pack(">I", len(dane)) + typ + dane
                + struct.pack(">I", zlib.crc32(typ + dane) & 0xFFFFFFFF))
    surowe = b"".join(b"\x00" + bytes(w) for w in wiersze)
    Path(plik).write_bytes(b"\x89PNG\r\n\x1a\n"
                           + kawalek(b"IHDR", struct.pack(">IIBBBBB", szer, wys, 8, 2, 0, 0, 0))
                           + kawalek(b"IDAT", zlib.compress(surowe, 6)) + kawalek(b"IEND", b""))


def podglad(m, z, x0, y0, promien, plik, trasa=(), droga=(), skala=8):
    """PNG wycinka: kolory minimapy, ściany przyciemnione, niewidziane czarne, schody żółte z
    ramką, pola trasy czerwone (kropka), droga niebieska, środek biały."""
    trasa = {(p[0], p[1]) for p in trasa if p[2] == z}
    droga = {(p[0], p[1]) for p in droga}
    bok = 2 * promien + 1
    wiersze = []
    for ty in range(y0 - promien, y0 + promien + 1):
        kafle = []
        for tx in range(x0 - promien, x0 + promien + 1):
            p = m.pole(tx, ty, z)
            if p is None or not p[0] & WIDZIANE:
                rgb, srodek = (0, 0, 0), None
            else:
                rgb = _kolor_tibii(p[1])
                if p[0] & SCIANA:
                    rgb = tuple(v // 3 for v in rgb)
                elif p[0] & BEZ_DROGI:
                    rgb = (255, 220, 0)
                srodek = None
            if (tx, ty) in droga:
                srodek = (40, 120, 255)
            if (tx, ty) in trasa:
                srodek = (230, 30, 30)
            if (tx, ty) == (x0, y0):
                srodek = (255, 255, 255)
            kafle.append((rgb, srodek))
        for py in range(skala):
            w = bytearray()
            for rgb, srodek in kafle:
                for px in range(skala):
                    brzeg = px == 0 or py == 0
                    wnetrze = skala // 4 <= px < skala - skala // 4 and skala // 4 <= py < skala - skala // 4
                    if srodek and wnetrze:
                        w += bytes(srodek)
                    elif brzeg:
                        w += bytes(tuple(v * 3 // 4 for v in rgb))
                    else:
                        w += bytes(rgb)
            wiersze.append(w)
    _zapisz_png(plik, bok * skala, bok * skala, wiersze)


def _trasy(nazwa=None):
    import json
    pliki = [KATALOG_TRAS / f"{nazwa}.json"] if nazwa else sorted(KATALOG_TRAS.glob("*.json"))
    pola = []
    for plik in pliki:
        try:
            pola += [tuple(p) for p in json.loads(plik.read_text())]
        except (OSError, ValueError):
            pass
    return pola


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    t = time.perf_counter()
    m = Mapa()
    t_start = time.perf_counter() - t
    polecenie, a = argv[1], [int(v) for v in argv[2:] if v.lstrip("-").isdigit()]
    if polecenie == "pole" and len(a) == 3:
        p = m.pole(*a)
        print(f"pole {tuple(a)}: {p} przechodnie={m.przechodnie(*a)} "
              f"schody_lub_dziura={m.schody_lub_dziura(*a)}")
    elif polecenie == "droga" and len(a) >= 5:
        x1, y1, z, x2, y2 = a[:5]
        dl = a[5] if len(a) > 5 else 1
        t = time.perf_counter()
        d = m.droga((x1, y1, z), (x2, y2), dlugosc=dl)
        ms = (time.perf_counter() - t) * 1000
        if d is None:
            print(f"brak drogi ({ms:.2f} ms)")
            return 1
        print(f"droga {len(d)} pól ({ms:.2f} ms, start mapy {t_start * 1000:.0f} ms):")
        print(" ".join(f"{x},{y}" for x, y, _ in d))
    elif polecenie == "podglad" and len(a) == 4 and len(argv) >= 7:
        z, x, y, r = a
        plik = next(v for v in argv[2:] if not v.lstrip("-").isdigit())
        nazwa = argv[7] if len(argv) > 7 else None
        podglad(m, z, x, y, r, plik, _trasy(nazwa))
        print(f"zapisano {plik} ({2 * r + 1}x{2 * r + 1} pól)")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
