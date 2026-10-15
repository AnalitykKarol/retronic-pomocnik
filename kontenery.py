"""Otwarte kontenery (plecak, zwłoki...) i ich przedmioty z pamięci gry.

Ładowany przez rdzen.py przy poleceniu "kontenery" (przeładowanie, gdy plik się zmieni).
Tylko odczyt.

Układ w pamięci (OTClient 32-bit, MSVC):

  Game::m_containers = std::map<int, ContainerPtr> w sekcji danych exe (rw, tuż za obrazem),
      obiekt mapy {głowa, liczba}; numer kontenera = klucz, wartość 0 = okno zamknięte.
      węzeł drzewa: +0 lewy, +4 rodzic, +8 prawy, +0xC kolor (u8), +0xD isnil (u8),
      +0x10 klucz (i32), +0x14 Container* (głowa: isnil = 1, rodzic = korzeń)
  Container  +0x00 vtable, +0x04 licznik referencji, +0x0C numer (= klucz mapy),
      +0x10 pojemność, +0x14 Item* przedmiotu kontenera (np. bag, zwłoki),
      +0x18 nazwa (std::string: 16 B SSO, +0x10 rozmiar, +0x14 pojemność bufora),
      +0x3C std::deque<ItemPtr> {proxy, mapa, rozmiar mapy, przesunięcie, liczba}
      (4 wskaźniki na blok, element k = przesunięcie + slot, blok = mapa[(k // 4) % rozmiar mapy])
  Item  +0x00 vtable, +0x0C pozycja x (u32, 0xFFFF = w kontenerze), +0x10 y (u32, 0x40 | numer
      kontenera), +0x14 z (u8, = slot), +0x1C 4 floaty 1.0 (kolor), +0x2C ID klienta (u16),
      +0x30 ilość / subtyp (u8)

Szukanie: mapa leży pod stałym adresem w danych exe, więc po pierwszym znalezieniu każdy odczyt
to kilkadziesiąt pread. Gdy adres przestanie pasować (np. nowa wersja klienta), mapa jest
szukana od nowa strukturalnie w sekcji danych exe.
"""

import re
import struct
import time

import numpy as np

KONTENER_NUMER = 0x0C
KONTENER_POJEMNOSC = 0x10
KONTENER_PRZEDMIOT = 0x14
KONTENER_NAZWA = 0x18
KONTENER_DEQUE = 0x3C
ROZMIAR_KONTENERA = 0x50

PRZEDMIOT_X = 0x0C
PRZEDMIOT_Y = 0x10
PRZEDMIOT_Z = 0x14
PRZEDMIOT_KOLOR = 0x1C
PRZEDMIOT_ID = 0x2C
PRZEDMIOT_ILOSC = 0x30
ROZMIAR_PRZEDMIOTU = 0x34
JEDEN = 0x3F800000           # float 1.0

W_BLOKU = 4                  # deque MSVC: 16 B na blok, wskaźnik 4 B
MAKS_KONTENEROW = 64
MAKS_POJEMNOSC = 64
PONOWNE_SZUKANIE = 2.0       # nie szukaj mapy częściej (gdy brak wyniku)

# ID klienta zaobserwowane na Retronic (numeracja nowych klientów, nie 7.4)
NAZWY = {
    3031: "gold coin",
    3003: "rope",
    3607: "cheese",
    3577: "meat",
    2853: "bag",
    3994: "dead rat",
}


def _wsk(v):
    return 0x10000 <= v < 0x7FFF0000 and v % 4 == 0


def _u32(p, adres, ile=1):
    b = p.czytaj(adres, 4 * ile)
    if len(b) < 4 * ile:
        return None
    return struct.unpack(f"<{ile}I", b)


def _obraz_exe(p):
    """Zakres obrazu exe (kod + vtable) i regiony rw jego sekcji danych."""
    obraz, dane = None, []
    with open(f"/proc/{p.pid}/maps") as f:
        linie = [l.split() for l in f]
    for i, cz in enumerate(linie):
        if len(cz) > 5 and cz[5].lower().endswith(".exe"):
            obraz = [int(x, 16) for x in cz[0].split("-")]
            # dalsze sekcje exe i anonimowe tuż za nimi (kod, dane), aż do przerwy
            for nast in linie[i + 1:]:
                s, k = (int(x, 16) for x in nast[0].split("-"))
                inny_plik = len(nast) > 5 and not nast[5].lower().endswith(".exe")
                if s != obraz[1] or inny_plik or nast[1].startswith("---"):
                    break
                obraz[1] = k
                if nast[1].startswith("rw") and len(nast) <= 5:
                    dane.append((s, k))
            break
    if obraz is None:
        return (0x400000, 0x1000000), [r for r in p.regiony() if r[0] < 0x1000000]
    return tuple(obraz), dane


def _napis(p, adres):
    """std::string MSVC pod adresem; None, gdy nie wygląda na napis."""
    b = p.czytaj(adres, 24)
    if len(b) < 24:
        return None
    rozmiar, pojemnosc = struct.unpack_from("<II", b, 16)
    if rozmiar > 64 or pojemnosc < 15 or rozmiar > pojemnosc or pojemnosc > 4096:
        return None
    if pojemnosc == 15:
        tekst = b[:rozmiar]
    else:
        wsk = struct.unpack_from("<I", b, 0)[0]
        if not _wsk(wsk):
            return None
        tekst = p.czytaj(wsk, rozmiar)
    if len(tekst) != rozmiar or any(c < 0x20 for c in tekst):
        return None
    return tekst.decode("latin-1")


def _wezly(p, glowa, liczba):
    """Węzły drzewa mapy w kolejności kluczy: [(klucz, wartość)]; None, gdy drzewo nie pasuje."""
    h = p.czytaj(glowa, 24)
    if len(h) < 24 or h[0xD] != 1:
        return None
    lewy, korzen, prawy = struct.unpack_from("<III", h, 0)
    wynik = []
    stos, wezel = [], korzen
    while stos or wezel != glowa:
        if len(wynik) > liczba or len(stos) > 64:
            return None
        if wezel != glowa:
            if not _wsk(wezel):
                return None
            b = p.czytaj(wezel, 24)
            if len(b) < 24 or b[0xD] != 0 or b[0xC] > 1:
                return None
            stos.append((wezel, b))
            wezel = struct.unpack_from("<I", b, 0)[0]
            continue
        adres, b = stos.pop()
        klucz, wartosc = struct.unpack_from("<iI", b, 0x10)
        wynik.append((klucz, wartosc))
        wezel = struct.unpack_from("<I", b, 8)[0]
    if len(wynik) != liczba:
        return None
    return wynik


def _kontener(p, adres, numer, obraz):
    """Odczyt jednego kontenera; None, gdy obiekt nie pasuje do układu."""
    b = p.czytaj(adres, ROZMIAR_KONTENERA)
    if len(b) < ROZMIAR_KONTENERA:
        return None
    vtable, referencje = struct.unpack_from("<II", b, 0)
    nr, pojemnosc, przedmiot = struct.unpack_from("<iiI", b, KONTENER_NUMER)
    _, mapa, rozmiar_mapy, przes, liczba = struct.unpack_from("<5I", b, KONTENER_DEQUE)
    if not (obraz[0] <= vtable < obraz[1]) or not (0 < referencje < 100000):
        return None
    if nr != numer or not (0 < pojemnosc <= MAKS_POJEMNOSC) or liczba > pojemnosc:
        return None
    nazwa = _napis(p, adres + KONTENER_NAZWA)
    if nazwa is None:
        return None
    id_kontenera = None
    if _wsk(przedmiot):
        pb = p.czytaj(przedmiot + PRZEDMIOT_ID, 2)
        if len(pb) == 2:
            id_kontenera = struct.unpack("<H", pb)[0]
    przedmioty = []
    if liczba:
        if not _wsk(mapa) or not (0 < rozmiar_mapy <= 4096) or rozmiar_mapy & (rozmiar_mapy - 1):
            return None
        bloki = _u32(p, mapa, rozmiar_mapy)
        if bloki is None:
            return None
        wsk_bloku = {}
        for slot in range(liczba):
            k = przes + slot
            nb = (k // W_BLOKU) % rozmiar_mapy
            if nb not in wsk_bloku:
                if not _wsk(bloki[nb]):
                    return None
                wsk_bloku[nb] = _u32(p, bloki[nb], W_BLOKU)
                if wsk_bloku[nb] is None:
                    return None
            ptr = wsk_bloku[nb][k % W_BLOKU]
            if not _wsk(ptr):
                return None
            ib = p.czytaj(ptr, ROZMIAR_PRZEDMIOTU)
            if len(ib) < ROZMIAR_PRZEDMIOTU:
                return None
            iv = struct.unpack_from("<I", ib, 0)[0]
            kolor = struct.unpack_from("<4I", ib, PRZEDMIOT_KOLOR)
            if not (obraz[0] <= iv < obraz[1]) or kolor[3] != JEDEN:
                return None
            ident = struct.unpack_from("<H", ib, PRZEDMIOT_ID)[0]
            if not ident:
                return None
            wpis = {"slot": slot, "id": ident, "ilosc": ib[PRZEDMIOT_ILOSC]}
            if ident in NAZWY:
                wpis["nazwa"] = NAZWY[ident]
            przedmioty.append(wpis)
    return {"numer": numer, "nazwa": nazwa, "id": id_kontenera,
            "pojemnosc": pojemnosc, "przedmioty": przedmioty}


def _odczytaj(p, adres_mapy, obraz):
    """Kontenery z mapy pod adresem; None, gdy adres nie jest mapą kontenerów."""
    mv = _u32(p, adres_mapy, 2)
    if mv is None:
        return None
    glowa, liczba = mv
    if not _wsk(glowa) or not (0 < liczba <= MAKS_KONTENEROW):
        return None
    wezly = _wezly(p, glowa, liczba)
    if wezly is None:
        return None
    wynik = []
    for klucz, wartosc in wezly:
        if not (0 <= klucz < 16):
            return None
        if wartosc == 0:
            continue                 # numer zajęty kiedyś, okno zamknięte
        k = _kontener(p, wartosc, klucz, obraz)
        if k is None:
            # przedmioty mogą się zmieniać w trakcie odczytu: jedna powtórka
            k = _kontener(p, wartosc, klucz, obraz)
            if k is None:
                return None
        wynik.append(k)
    return wynik


def _szukaj_mapy(p, obraz, dane):
    """Kandydaci {głowa, liczba} w sekcji danych exe, sprawdzani przez pełny odczyt.
    Wymaga choć jednego otwartego kontenera (inaczej nie da się odróżnić mapy)."""
    for start, koniec in dane:
        bufor = p.czytaj(start, koniec - start)
        n = len(bufor) // 4
        if n < 2:
            continue
        a = np.frombuffer(bufor, "<u4", count=n)
        g, l = a[:-1], a[1:]
        idx = np.nonzero((l >= 1) & (l <= MAKS_KONTENEROW) & (g >= 0x10000) & (g < 0x7FFF0000)
                         & (g % 4 == 0))[0]
        for i in idx:
            glowa = int(a[i])
            h = p.czytaj(glowa, 16)
            if len(h) < 16 or h[0xD] != 1 or h[0xC] != 1:
                continue
            adres = start + int(i) * 4
            k = _odczytaj(p, adres, obraz)
            if k:
                return adres, k
    return None, None


def _stan(p):
    st = getattr(p, "kontenery_stan", None)
    if st is None or st.get("pid") != p.pid:
        st = {"pid": p.pid, "mapa": None, "obraz": None, "dane": None, "proba": 0.0}
        p.kontenery_stan = st
    return st


def kontenery(p):
    st = _stan(p)
    if st["obraz"] is None:
        st["obraz"], st["dane"] = _obraz_exe(p)
    if st["mapa"] is not None:
        k = _odczytaj(p, st["mapa"], st["obraz"])
        if k is not None:
            return k
        k = _odczytaj(p, st["mapa"], st["obraz"])   # zmiana w trakcie odczytu
        if k is not None:
            return k
        st["mapa"] = None
        st["obraz"], st["dane"] = _obraz_exe(p)
    if time.monotonic() - st["proba"] < PONOWNE_SZUKANIE:
        return []
    st["proba"] = time.monotonic()
    adres, k = _szukaj_mapy(p, st["obraz"], st["dane"])
    if adres is None:
        return []
    st["mapa"] = adres
    return k


# --- ekwipunek (sloty postaci) ------------------------------------------------
#
# LocalPlayer::m_inventoryItems = ItemPtr[11] indeksowane numerem slotu Tibii (1 głowa, 2 naszyjnik,
# 3 plecak, 4 zbroja, 5 prawa ręka, 6 lewa ręka, 7 nogi, 8 buty, 9 pierścień, 10 amunicja);
# 0 = pusty slot. Item ma pozycję x = 0xFFFF, y = numer slotu, z = 0 (przedmiot w kontenerze: y = 0x40|numer).
# Adres tablicy w stercie nie jest stały między sesjami: szukamy przedmiotów o takiej pozycji (żywe mają
# licznik referencji > 0, zwolnione duchy 0), potem wskaźników na nie i tablicy zgodnej z numerami slotów.
SLOTY_EKWIPUNKU = 11
PONOWNE_SZUKANIE_EKW = 20.0
WZORZEC_EKW = rb"\xff\xff\x00\x00[\x01-\x0a]\x00\x00\x00"


def _przedmiot_ekw(p, adres, obraz):
    """(id, ilosc, slot) żywego przedmiotu ekwipunku pod adresem albo None."""
    b = p.czytaj(adres, ROZMIAR_PRZEDMIOTU)
    if len(b) < ROZMIAR_PRZEDMIOTU:
        return None
    vt, ref = struct.unpack_from("<II", b, 0)
    x, y = struct.unpack_from("<II", b, PRZEDMIOT_X)
    kolor = struct.unpack_from("<4I", b, PRZEDMIOT_KOLOR)
    ident = struct.unpack_from("<H", b, PRZEDMIOT_ID)[0]
    if not (obraz[0] <= vt < obraz[1]) or not (0 < ref < 100000) or kolor[3] != JEDEN:
        return None
    if x != 0xFFFF or not (1 <= y < SLOTY_EKWIPUNKU) or not ident:
        return None
    return ident, b[PRZEDMIOT_ILOSC], y


def _tablica_ekw(p, baza, obraz):
    """{slot: (id, ilosc)} gdy pod adresem jest tablica ekwipunku zgodna z numerami slotów, inaczej None."""
    w = _u32(p, baza, SLOTY_EKWIPUNKU)
    if w is None:
        return None
    wynik = {}
    for slot, ptr in enumerate(w):
        if ptr == 0:
            continue
        if not _wsk(ptr):
            return None
        pr = _przedmiot_ekw(p, ptr, obraz)
        if pr is None or pr[2] != slot:
            return None
        wynik[slot] = (pr[0], pr[1])
    return wynik


def _szukaj_tablicy_ekw(p, obraz):
    zywe = {}
    for a in p.szukaj_bajtow(WZORZEC_EKW, 400):
        adres = int(a, 16) - PRZEDMIOT_X
        pr = _przedmiot_ekw(p, adres, obraz)
        if pr:
            zywe[adres] = pr
    if not zywe:
        return None, None
    wzorzec = b"(?:" + b"|".join(re.escape(struct.pack("<I", a)) for a in zywe) + b")"
    lokalizacje = [int(a, 16) for a in p.szukaj_bajtow(wzorzec, 200)]
    najlepsza = None
    for loc in lokalizacje:
        ptr = struct.unpack("<I", p.czytaj(loc, 4))[0]
        if ptr not in zywe:
            continue
        baza = loc - 4 * zywe[ptr][2]
        t = _tablica_ekw(p, baza, obraz)
        if t and len(t) == len(zywe) and (najlepsza is None or baza < najlepsza[0]):
            najlepsza = (baza, t)
    return najlepsza if najlepsza else (None, None)


def ekwipunek(p):
    """{slot: {"id", "ilosc"}} slotów ekwipunku (tylko zajęte) albo None, gdy nie znaleziono tablicy."""
    st = _stan(p)
    if st["obraz"] is None:
        st["obraz"], st["dane"] = _obraz_exe(p)
    baza = st.get("ekw")
    if baza is not None:
        t = _tablica_ekw(p, baza, st["obraz"])
        if t is None:
            t = _tablica_ekw(p, baza, st["obraz"])      # zmiana w trakcie odczytu
        if t is not None:
            return {s: {"id": i, "ilosc": n} for s, (i, n) in t.items()}
        st["ekw"] = None
    if time.monotonic() - st.get("ekw_proba", -1e9) < PONOWNE_SZUKANIE_EKW:
        return None
    st["ekw_proba"] = time.monotonic()
    baza, t = _szukaj_tablicy_ekw(p, st["obraz"])
    if baza is None:
        return None
    st["ekw"] = baza
    return {s: {"id": i, "ilosc": n} for s, (i, n) in t.items()}


def obsluz(p, z):
    t0 = time.monotonic()
    if z.get("ekwipunek"):
        try:
            if z.get("odswiez"):
                # wymuszone ponowne szukanie tablicy (bot po relogu/zmianie tarczy); działa po restarcie gry
                st = _stan(p)
                st["ekw"] = None
                st["ekw_proba"] = -1e9
            e = ekwipunek(p)
        except Exception as ex:
            return {"ekwipunek": None, "blad": f"{type(ex).__name__}: {ex}"}
        return {"ekwipunek": None if e is None else {str(k): v for k, v in e.items()}}
    try:
        wynik = kontenery(p)
    except Exception:
        wynik = []
    odp = {"kontenery": wynik}
    if z.get("diagnostyka"):
        st = _stan(p)
        odp["mapa"] = None if st["mapa"] is None else hex(st["mapa"])
        odp["czas_s"] = round(time.monotonic() - t0, 4)
    return odp
