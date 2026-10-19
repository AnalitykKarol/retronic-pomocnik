#!/usr/bin/env python3
"""Zbieranie łupu ze zwłok: otwarcie zwłok, wykrycie okien kontenerów w prawym panelu,
rozpoznanie przedmiotów (po ID z pamięci gry, awaryjnie po ikonach) i przeciągnięcie ich do plecaka.

  loot.py sloty [plik.png]               podgląd wykrytych okien i slotów (scratchpad/podglad_slotow.png)
  loot.py rozpoznaj [plik.png]           wypisuje, co leży w slotach każdego okna kontenera
  loot.py ikona <nazwa> <x> <y> [plik]   wycina ikonę ze slotu pod (x, y) do ikony/<nazwa>.png
  loot.py tytul <nazwa> <x> <y> [plik]   wycina tytuł okna ze slotem pod (x, y) do ikony/tytuly/<nazwa>.png
  loot.py test                           testy offline na zrzutach ze scratchpadu

Bez pliku komendy robią świeży zrzut gry. Żadna z nich nie wysyła inputu do gry.
Jedynie zbierz() (używane przez cavebota) klika i przeciąga.

Jak to działa:
 - Co leży w oknach (ID i ilość) czytamy komendą {"cmd":"kontenery"} z gniazda pomocnika. Okna z ekranu
   dopasowujemy do kontenerów z pamięci po układzie pustych/zajętych slotów (i tytule przy remisie);
   slot i kontenera = i-ty widoczny slot okna. Gdy odczyt nie działa albo nie zgadza się z ekranem,
   wracamy do rozpoznawania po ikonach (opis niżej).
 - Okna w panelu mają ramki w kolorze (50,52,48): górną krawędź okna (długi poziomy odcinek)
   i ramki slotów (kwadraty 34 px, krok 37 px). Nie zależy to od rozmiaru ekranu.
 - Okno kontenera = wiersz co najmniej 3 slotów w równym kroku. Ekwipunek ma ich najwyżej 2 w wierszu.
 - Plecak rozpoznajemy po tytule (wzorce ikony/tytuly/<nazwa>.png, nazwy z PLECAKI),
   każdy inny kontener to zwłoki (przy kilku wybieramy najniższe, bo nowe okno dochodzi na dół).
 - Przedmioty: porównanie 32x32 z ikony slotu z biblioteką ikony/<nazwa>.png (średni błąd bezwzględny
   z pominięciem prawego dolnego rogu, gdzie jest licznik stosu). Warianty: ikony/<nazwa>__<cokolwiek>.png
   (np. gold coin ma inny sprite dla 1, 2, 5, 50 monet).
"""
import hashlib
import itertools
import random
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import bot  # noqa: E402
import ekran  # noqa: E402

KATALOG = Path(__file__).resolve().parent
IKONY = KATALOG / "ikony"
TYTULY = IKONY / "tytuly"
SCRATCH = ekran.SCRATCH

PLIK_LISTY = Path(__file__).resolve().parent / "do_zebrania.txt"
NIEZNANE = Path(__file__).resolve().parent / "ikony" / "nieznane"

# ID przedmiotów w kliencie Retronic (numeracja nowych klientów, nie 7.4), zaobserwowane w pamięci
# komendą {"cmd":"kontenery"}. Nowe ID można też dopisać w do_zebrania.txt: "1234 # nazwa".
NAZWA_ID = {
    "gold coin": 3031,
    "cheese": 3607,
    "meat": 3577,
    "rope": 3003,
    "bag": 2853,
    "dead rat": 3994,
}

# Jedzenie: ID z items.xml (numeracja nowych klientów / canary). Na żywo w Retronic potwierdzone są
# tylko cheese 3607 i meat 3577; reszta to lista startowa (sprawdź komendą "kontenery", gdy wypadnie).
# Kolejność = kolejność jedzenia z plecaka: najpierw to, co syci najdłużej.
JEDZENIE_ID = {
    "ham": 3582,
    "dragon ham": 3583,
    "meat": 3577,
    "fish": 3578,
    "salmon": 3579,
    "bread": 3600,
    "brown bread": 3602,
    "cheese": 3607,
    "roll": 3601,
    "melon": 3593,
    "pumpkin": 3594,
    "coconut": 3589,
    "corncob": 3597,
    "carrot": 3595,
    "tomato": 3596,
    "banana": 3587,
    "apple": 3585,
    "orange": 3586,
    "egg": 3606,
    "brown mushroom": 3725,
    "white mushroom": 3723,
    "red mushroom": 3724,
    "grapes": 3592,
    "cookie": 3598,
    "strawberry": 3591,
    "cherry": 3590,
    "blueberry": 3588,
}
KOLEJNOSC_JEDZENIA = tuple(JEDZENIE_ID.values())
for _n, _i in JEDZENIE_ID.items():
    NAZWA_ID.setdefault(_n, _i)
ID_NAZWA = {i: n for n, i in NAZWA_ID.items()}
JEDZ_ZE_ZWLOK = True     # jedzenie w zwłokach: najpierw Use (zjedz), dopiero najedzony -> do plecaka
MAKS_ZJEDZENIA = 6       # ile razy maks. jemy ze zwłok przy jednym zbieraniu


def parsuj_liste(linie):
    """Wpisy z do_zebrania.txt: nazwa (str) albo ID (int). "3031 # gold coin" to ID 3031,
    a komentarz staje się nazwą tego ID w logach (jeśli nie znamy lepszej)."""
    wynik = []
    for linia in linie:
        tresc, _, komentarz = linia.partition("#")
        tresc = tresc.strip().casefold()
        if not tresc:
            continue
        if tresc.isdigit():
            ident = int(tresc)
            komentarz = komentarz.strip().casefold()
            if komentarz and ident not in ID_NAZWA:
                ID_NAZWA[ident] = komentarz
                NAZWA_ID.setdefault(komentarz, ident)
            wynik.append(ident)
        else:
            wynik.append(tresc)
    return tuple(wynik)


def wczytaj_liste():
    """Lista rzeczy do zbierania z do_zebrania.txt (nazwa albo ID w linii, # komentarz)."""
    try:
        linie = PLIK_LISTY.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ("gold coin", "cheese", "meat", "ham")
    return parsuj_liste(linie)


def rozdziel_liste(lista):
    """(zbiór ID, zbiór nazw) z wpisów listy; nazwa i ID tego samego przedmiotu uzupełniają się."""
    idy, nazwy = set(), set()
    for wpis in lista:
        if isinstance(wpis, int) or str(wpis).strip().isdigit():
            ident = int(wpis)
            idy.add(ident)
            if ident in ID_NAZWA:
                nazwy.add(ID_NAZWA[ident])
        else:
            nazwa = str(wpis).strip().casefold()
            nazwy.add(nazwa)
            if nazwa in NAZWA_ID:
                idy.add(NAZWA_ID[nazwa])
    return idy, nazwy


def nazwa_id(ident):
    return ID_NAZWA.get(ident, f"id {ident}")


DO_ZEBRANIA = wczytaj_liste()
STOSOWE = ("gold coin",)   # plan z obrazka: upuszczamy na istniejący stos w plecaku
# Plan z pamięci: każdy przedmiot upuszczamy na stos tego samego ID w plecaku (< 100 szt.), chyba że
# wiemy, że się nie stackuje. NIESTOSOWE_ID uzupełnia się samo, gdy po upuszczeniu na "stos" pamięć
# pokaże osobny przedmiot. Pewne stosy (scalamy też rozbite stosy w plecaku): gold i jedzenie.
STOSOWE_ID = {NAZWA_ID[n] for n in STOSOWE if n in NAZWA_ID} | set(JEDZENIE_ID.values())
NIESTOSOWE_ID = {NAZWA_ID["rope"], NAZWA_ID["bag"]}
PEWNE_STOSY_ID = {NAZWA_ID["gold coin"]}   # nigdy nie uczymy się, że się nie stackuje (np. chybiony drop)
MAKS_STOSU = 100
MAKS_SCALEN = 2                  # ile scaleń rozbitych stosów w plecaku przy jednym zbieraniu
PLECAKI = ("bag", "backpack")    # nazwy wzorców tytułu, które oznaczają plecak gracza
ID_PLECAKOW = {NAZWA_ID["bag"]}  # ID przedmiotu-kontenera, który jest plecakiem gracza
# Pojemnik na runy (np. Purple backpack): drugi kontener obok plecaka, NIE zwłoki i NIE plecak lootu.
ID_MONET_W_POJEMNIKU = {3031, 3035, 3043}   # gold, platinum, crystal coin
ID_RUN_W_POJEMNIKU = {3147, 3198, 3160, 3155, 3191, 3200, 3152}   # blank, HMM, UH, SD, GFB, explosion, IH: kontener tylko z nimi = pojemnik na runy
ID_TARCZ_W_POJEMNIKU = {3409, 3426}      # steel shield, tarcza z UH_STAN_PLIK: dozwolone w pojemniku na runy chwilowo
ID_POJEMNIKOW_RUN = {2868}              # ID przedmiotu-kontenera (Purple backpack)
NAZWY_POJEMNIKOW_RUN = ("purple backpack",)   # prefiks nazwy kontenera (pamięć) i wzorzec tytułu okna

RAMKA = (50, 52, 48)             # kolor ramek okien i slotów
OK_DX, OK_DY = 29, 41               # przycisk Ok względem środka okna ilości (środek = róg wzorca + (60, 66))
BOK_SLOTU = 34                   # bok slotu razem z ramką
MIN_W_WIERSZU = 3                # tyle slotów w równym kroku to kontener (ekwipunek ma 2)
PROG_IKONY = 14.0                # maks. średni błąd (0-255), żeby uznać ikonę za rozpoznaną
PROG_TYTULU = 10.0
MAKS_RUCHOW = 12                 # ile przedmiotów maks. w jednym zbieraniu
PRZERWIJ = None                  # opcjonalne wywołanie() -> True: przerwij zbieranie (cavebot: żywy potwór obok)


# --- wykrywanie okien i slotów ----------------------------------------------

def _przedzialy(maska):
    d = np.diff(np.concatenate([[0], maska.astype(np.int8), [0]]))
    return list(zip(np.where(d == 1)[0].tolist(), np.where(d == -1)[0].tolist()))


def _maska_ramki(a):
    return ((np.abs(a[:, :, 0] - RAMKA[0]) <= 2) & (np.abs(a[:, :, 1] - RAMKA[1]) <= 2)
            & (np.abs(a[:, :, 2] - RAMKA[2]) <= 2))


class Slot:
    def __init__(self, x, y, bok):
        self.x, self.y, self.bok = x, y, bok

    @property
    def srodek(self):
        return self.x + self.bok // 2, self.y + self.bok // 2

    def wnetrze(self):
        """(x0, y0, x1, y1) bez ramki."""
        return self.x + 1, self.y + 1, self.x + self.bok - 1, self.y + self.bok - 1

    def __repr__(self):
        return f"Slot({self.x},{self.y},{self.bok})"


class Okno:
    def __init__(self, gora, lewo, prawo, sloty):
        self.gora, self.lewo, self.prawo = gora, lewo, prawo   # gora: y górnej ramki, None gdy nie znaleziono
        self.sloty = sloty                                    # posortowane: wiersz, kolumna
        self.tytul = None                                     # nazwa dopasowanego wzorca tytułu
        self.rola = "zwloki"                                  # "plecak", "zwloki" albo "runy" (pojemnik na runy)
        self.kontener = None                                  # kontener z pamięci (słownik), gdy dopasowany

    @property
    def przycisk_zamkniecia(self):
        """Środek przycisku X w nagłówku (nagłówek: 7 px pod górną ramką, X ~10 px od prawej)."""
        if self.gora is None:
            return None
        return self.prawo - 11, self.gora + 8

    def __repr__(self):
        return (f"Okno({self.rola}, tytuł={self.tytul}, gora={self.gora}, "
                f"x={self.lewo}..{self.prawo}, slotów={len(self.sloty)})")


def _sloty(maska, szer):
    """Lewe-górne rogi slotów: odcinki ramki o długości = bok slotu, niebędące dolną krawędzią
    innego slotu (dolna krawędź leży bok-1 pod górną). Slot z uciętym dołem też się liczy."""
    odcinki = {}
    for y in np.where(maska[:, szer // 2:].sum(1) >= 20)[0].tolist():
        for s, e in _przedzialy(maska[y]):
            if e - s == BOK_SLOTU and s >= szer // 2:
                odcinki[(s, y)] = e - s
    wynik = []
    for (x, y), bok in sorted(odcinki.items(), key=lambda p: (p[0][1], p[0][0])):
        if (x, y - bok + 1) in odcinki:
            continue   # to dolna krawędź slotu wyżej
        wynik.append(Slot(x, y, bok))
    return wynik


def _gorna_ramka(maska, slot_x, y_pierwszego_wiersza):
    """Najbliższa nad slotami górna krawędź okna: odcinek >= 165 px zaczynający się ~9 px na lewo od slotu."""
    for y in range(y_pierwszego_wiersza - 1, max(0, y_pierwszego_wiersza - 30), -1):
        for s, e in _przedzialy(maska[y, slot_x - 14:slot_x + 200]):
            s += slot_x - 14
            e += slot_x - 14
            if e - s >= 165 and slot_x - 14 <= s <= slot_x - 4:
                return y, s, e
    return None


def znajdz_okna(obraz):
    """Okna kontenerów w prawym panelu zrzutu: lista Okno (kolejność od góry)."""
    a = np.asarray(obraz.convert("RGB")).astype(np.int16)
    maska = _maska_ramki(a)
    szer = obraz.size[0]
    sloty = _sloty(maska, szer)
    # wiersze slotów (ten sam y), z kolumnami w równym kroku 36-38 px
    wiersze = {}
    for s in sloty:
        wiersze.setdefault(s.y, []).append(s)
    okna = []
    ostatni = {}                       # okno -> y ostatniego dodanego wiersza
    for y in sorted(wiersze):
        w = sorted(wiersze[y], key=lambda s: s.x)
        # najdłuższy ciąg w równym kroku
        ciag, najlepszy = [w[0]], []
        for poprzedni, s in zip(w, w[1:]):
            if 36 <= s.x - poprzedni.x <= 38:
                ciag.append(s)
            else:
                najlepszy = max(najlepszy, ciag, key=len)
                ciag = [s]
        najlepszy = max(najlepszy, ciag, key=len)
        if len(najlepszy) < MIN_W_WIERSZU:
            continue
        # kolejny wiersz tego samego okna: ta sama kolumna startowa, 36-38 px niżej
        okno = next((o for o in okna if o.sloty[0].x == najlepszy[0].x and 36 <= y - ostatni[o] <= 38), None)
        if okno is None:
            ramka = _gorna_ramka(maska, najlepszy[0].x, y)
            okno = Okno(ramka[0] if ramka else None,
                        ramka[1] if ramka else najlepszy[0].x - 9,
                        ramka[2] if ramka else najlepszy[-1].x + BOK_SLOTU + 20, [])
            okna.append(okno)
        okno.sloty.extend(najlepszy)
        ostatni[okno] = y
    # Slot uciety od dolu przez dolna ramke okna (okno zmniejszone, pod nim kolejne okno, np. Battle):
    # jego wnetrze to cudze piksele, wiec nie jest ani pusty, ani rozpoznawalny. Gubimy go (jest zawsze
    # na koncu, wiec numeracja slotow sie nie zmienia). Ucieci przez dol zrzutu zostaja jak byly.
    wys = maska.shape[0]
    for o in okna:
        o.sloty = [s for s in o.sloty
                   if s.y + s.bok - 1 >= wys or maska[s.y + s.bok - 1, s.x:s.x + s.bok].sum() >= s.bok // 2]
    # Wiersz z <3 wykrytymi slotami (zaznaczony/podświetlony slot) wypada i rozbija okno na dwa: kolejne
    # okno zaczyna się wtedy dokładnie k*37 px pod ostatnim wierszem (a nie o nagłówek niżej).
    okna = [o for o in okna if o.sloty]
    okna.sort(key=lambda o: min(s.y for s in o.sloty))
    scalone = []
    for o in okna:
        poprz = scalone[-1] if scalone else None
        if poprz is not None and o.sloty and poprz.sloty:
            dol = max(s.y for s in poprz.sloty)
            gora = min(s.y for s in o.sloty)
            krok = 37
            k = round((gora - dol) / krok)
            kol_poprz = {s.x for s in poprz.sloty}
            if (k >= 1 and abs(gora - dol - k * krok) <= 1
                    and {s.x for s in o.sloty} <= kol_poprz):
                poprz.sloty.extend(o.sloty)
                for j in range(1, k):
                    for s0 in {s.x for s in poprz.sloty}:
                        poprz.sloty.append(Slot(s0, dol + j * krok, BOK_SLOTU))
                continue
        scalone.append(o)
    okna = scalone
    # Slot z niestandardową ramką (zaznaczony przez klik, niebieska obwódka) wypada z wykrywania i
    # przesuwa numerację wszystkich kolejnych: uzupełniamy dziury w siatce (wiersz x kolumna okna).
    for o in okna:
        kolumny = sorted({s.x for s in o.sloty})
        bok = o.sloty[0].bok
        mamy = {(s.x, s.y) for s in o.sloty}
        for y in sorted({s.y for s in o.sloty}):
            for x in kolumny:
                if (x, y) not in mamy:
                    o.sloty.append(Slot(x, y, bok))
    okna = [o for o in okna if o.sloty]
    wynik = sorted(okna, key=lambda o: min(s.y for s in o.sloty))
    for o in wynik:
        o.sloty.sort(key=lambda s: (s.y, s.x))
        o.tytul = _nazwa_tytulu(obraz, o)
        o.rola = rola_z_tytulu(o.tytul)
    return wynik


# --- tytuły i ikony (biblioteki wzorców) -------------------------------------

def _wycinek_tytulu(obraz, okno):
    if okno.gora is None:
        return None
    x, y = okno.lewo + 19, okno.gora + 2
    return obraz.crop((x, y, x + 70, y + 13)).convert("RGB")


def _blad(a, b, maska=None):
    r = np.abs(np.asarray(a).astype(np.int16) - np.asarray(b).astype(np.int16)).mean(2)
    return float(r[maska].mean()) if maska is not None else float(r.mean())


_biblioteka = {}


def _wczytaj(katalog):
    """{nazwa: [obrazy]}; plik <nazwa>__<wariant>.png trafia do <nazwa>. Cache po czasie modyfikacji katalogu."""
    klucz = (str(katalog), katalog.stat().st_mtime if katalog.exists() else 0)
    if klucz not in _biblioteka:
        wynik = {}
        for plik in sorted(katalog.glob("*.png")) if katalog.exists() else []:
            nazwa = plik.stem.split("__")[0]
            wynik.setdefault(nazwa, []).append(Image.open(plik).convert("RGB"))
        _biblioteka[klucz] = wynik
    return _biblioteka[klucz]


def _nazwa_tytulu(obraz, okno):
    wycinek = _wycinek_tytulu(obraz, okno)
    if wycinek is None:
        return None
    najlepszy = (PROG_TYTULU, None)
    for nazwa, wzorce in _wczytaj(TYTULY).items():
        for w in wzorce:
            if w.size == wycinek.size:
                najlepszy = min(najlepszy, (_blad(wycinek, w), nazwa), key=lambda p: p[0])
    return najlepszy[1]


def _ikona_slotu(obraz, slot):
    x0, y0, x1, y1 = slot.wnetrze()
    return obraz.crop((x0, y0, x1, y1)).convert("RGB")


def _maska_ikony(rozmiar):
    """True tam, gdzie porównujemy. Prawy dolny róg (licznik stosu) pomijamy."""
    m = np.ones((rozmiar, rozmiar), bool)
    m[int(rozmiar * 0.55):, int(rozmiar * 0.42):] = False
    return m


def czy_pusty(obraz, slot):
    """Pusty slot ma tylko ciemne tło (jasność 15-40): bez czerni obrysu i bez jasnych pikseli."""
    g = np.asarray(_ikona_slotu(obraz, slot).convert("L")).astype(int)
    return int(((g <= 8) | (g >= 64)).sum()) < 6


def rozpoznaj(obraz, slot):
    """(nazwa, błąd). Nazwa None dla pustego slotu, "?" gdy nic nie pasuje do biblioteki."""
    if czy_pusty(obraz, slot):
        return None, 0.0
    ikona = _ikona_slotu(obraz, slot)
    maska = _maska_ikony(ikona.size[0])
    najlepszy = (1e9, "?")
    for nazwa, wzorce in _wczytaj(IKONY).items():
        for w in wzorce:
            if w.size == ikona.size:
                najlepszy = min(najlepszy, (_blad(ikona, w, maska), nazwa), key=lambda p: p[0])
    blad, nazwa = najlepszy
    if blad <= PROG_IKONY:
        return nazwa, blad
    # gold ma osobną grafikę dla 1, 2, 3... monet: rozpoznajemy go po złotym kolorze
    if _udzial_zlota(ikona) > PROG_ZLOTA:
        return "gold coin", blad
    return "?", blad


PROG_ZLOTA = 0.45   # udział złotych pikseli w ikonie (gold 0.66-0.74, inne przedmioty <= 0.2)


def _udzial_zlota(ikona):
    a = np.asarray(ikona.convert("RGB"), dtype=np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    tlo = (abs(r - g) < 12) & (abs(g - b) < 12)
    zloto = (r > 150) & (g > 110) & (b < 90) & (r - b > 90)
    return zloto.sum() / max(1, (~tlo).sum())


def zapisz_nieznany(obraz, slot, ident=None):
    """Zapisuje ikonę nierozpoznanego przedmiotu do ikony/nieznane/, żeby można ją nazwać.
    Przy znanym ID z pamięci plik nazywa się id_<ID>.png (wystarczy dopisać ID do NAZWA_ID)."""
    try:
        NIEZNANE.mkdir(parents=True, exist_ok=True)
        ikona = _ikona_slotu(obraz, slot)
        podpis = f"id_{ident}" if ident is not None else hashlib.md5(ikona.tobytes()).hexdigest()[:10]
        cel = NIEZNANE / f"{podpis}.png"
        if not cel.exists():
            ikona.save(cel)
    except OSError:
        pass


def zawartosc(obraz, okno):
    """Lista (slot, nazwa|None|"?", błąd) dla slotów okna."""
    return [(s, *rozpoznaj(obraz, s)) for s in okno.sloty]


# --- kontenery z pamięci gry ------------------------------------------------------

def _zapytaj(zadanie):
    """Zapytanie do gniazda pomocnika (w testach podmieniane atrapą)."""
    return bot.zapytaj(zadanie)


def kontenery_z_pamieci():
    """(lista kontenerów z komendy "kontenery", None) albo (None, powód), gdy odczyt nie działa."""
    try:
        odp = _zapytaj({"cmd": "kontenery"})
    except Exception as e:  # brak gniazda, timeout, błąd w rdzeniu: zostaje rozpoznawanie obrazkiem
        return None, f"brak odczytu ({type(e).__name__}: {e})"
    if odp.get("blad"):
        return None, f"błąd odczytu ({odp['blad']})"
    kontenery = odp.get("kontenery") or []
    if not kontenery:
        return None, "pamięć nie widzi otwartych kontenerów"
    return kontenery, None


def czy_plecak(kontener):
    return kontener.get("id") in ID_PLECAKOW or (kontener.get("nazwa") or "").casefold() in PLECAKI


def czy_runy(kontener):
    """Pojemnik na runy (ID_POJEMNIKOW_RUN albo nazwa zaczynająca się od NAZWY_POJEMNIKOW_RUN)."""
    if (kontener.get("id") in ID_POJEMNIKOW_RUN
            or (kontener.get("nazwa") or "").casefold().startswith(NAZWY_POJEMNIKOW_RUN)):
        return True
    # zwykły plecak (id 2854) z samymi runami (blank 3147 / gotowe 3198, 3160 ...) to też pojemnik na runy
    ids = {p.get("id") for p in kontener.get("przedmioty", [])}
    # tarcza odłożona na czas runy (uh.py, gdy w głównym plecaku brak widocznego wolnego pola) nie zmienia roli bagu
    # 14.10: monety (gold/platinum/crystal) też nie zmieniają roli: loot wrzucił gold do pustego bagu na runy i bot
    # brał go potem za drugi plecak (UH "kilka okien plecaka", łopata "niejednoznaczne dopasowanie okien")
    przedm = kontener.get("przedmioty", [])
    if ids & ID_RUN_W_POJEMNIKU and not ids <= (ID_RUN_W_POJEMNIKU | ID_TARCZ_W_POJEMNIKU | ID_MONET_W_POJEMNIKU):
        # 15.10: bag z lootem pomieszanym z runami (np. rope/gold obok UH i blanków) nadal jest bagiem na runy,
        # gdy runy to wyraźna większość (inaczej pełny bag na runy brany za główny plecak -> "pełny plecak")
        n_run = sum(1 for p in przedm if p.get("id") in ID_RUN_W_POJEMNIKU)
        return n_run >= 3 and n_run * 4 >= len(przedm) * 3
    if not (ids & ID_RUN_W_POJEMNIKU):
        return False
    monety = sum(1 for p in przedm if p.get("id") in ID_MONET_W_POJEMNIKU)
    return monety < sum(1 for p in przedm if p.get("id") in ID_RUN_W_POJEMNIKU)   # pojedynczy stos złota w bagu na runy


def _wyglada_na_runy(kontener):
    """True, gdy w kontenerze są runy z uh.py (UH/blanki itd.) i to one przeważają: nigdy nie główny plecak."""
    przedm = kontener.get("przedmioty", [])
    n_run = sum(1 for p in przedm if p.get("id") in ID_RUN_W_POJEMNIKU)
    return n_run > 0 and n_run * 2 >= len(przedm)


def rola_z_tytulu(tytul):
    """Rola okna z rozpoznanego tytułu: "runy" | "plecak" | "zwloki"."""
    if tytul is not None and tytul.startswith(NAZWY_POJEMNIKOW_RUN):
        return "runy"
    return "plecak" if tytul in PLECAKI else "zwloki"


def rola_kontenera(kontener):
    return "runy" if czy_runy(kontener) else ("plecak" if czy_plecak(kontener) else "zwloki")


def _niezgodnosci(obraz, okno, kontener):
    """Ile widocznych slotów okna nie zgadza się z kontenerem (pusty/zajęty). None: nie pasuje wcale.
    Okno może pokazywać mniej slotów niż pojemność (reszta schowana pod suwakiem)."""
    if len(okno.sloty) > kontener.get("pojemnosc", 0):
        return None
    zajete = {p["slot"] for p in kontener.get("przedmioty", [])}
    return sum((not czy_pusty(obraz, s)) != (i in zajete) for i, s in enumerate(okno.sloty))


def dopasuj_okna(obraz, okna, kontenery):
    """Przypisanie kontenerów z pamięci do okien z ekranu: (lista kontenerów w kolejności okien, None)
    albo (None, powód). Okna muszą zgadzać się co do slotu (pusty/zajęty) z kontenerem; tytuł
    rozpoznany z obrazka rozstrzyga remisy. Gdy dwa przypisania są równie dobre, nie zgadujemy."""
    if not okna:
        return None, "brak okien na ekranie"
    if len(kontenery) < len(okna):
        return None, f"okien {len(okna)}, kontenerów w pamięci {len(kontenery)}"
    if len(kontenery) > 6:
        return None, f"za dużo kontenerów ({len(kontenery)})"
    koszt = {(i, j): _niezgodnosci(obraz, o, k) for i, o in enumerate(okna) for j, k in enumerate(kontenery)}
    wyniki = []
    for perm in itertools.permutations(range(len(kontenery)), len(okna)):
        koszty = [koszt[i, j] for i, j in enumerate(perm)]
        if None in koszty:
            continue
        zgodne_tytuly = sum(1 for i, j in enumerate(perm)
                            if okna[i].tytul is not None
                            and (okna[i].tytul == (kontenery[j].get("nazwa") or "").casefold()
                                 or ((okna[i].tytul in PLECAKI) == czy_plecak(kontenery[j])
                                     and (rola_z_tytulu(okna[i].tytul) == "runy") == czy_runy(kontenery[j]))))
        wyniki.append(((sum(koszty), -zgodne_tytuly), perm))
    if not wyniki:
        return None, "żaden kontener nie pasuje do okien (liczba slotów)"
    wyniki.sort()
    (niezgodnych, _), perm = wyniki[0]
    if niezgodnych:
        return None, f"niezgodne z ekranem ({niezgodnych} slotów)"
    if len(wyniki) > 1 and wyniki[1][0] == wyniki[0][0]:
        return None, "niejednoznaczne dopasowanie okien"
    return [kontenery[j] for j in perm], None


def suma_id(kontener, ident):
    """Ile sztuk przedmiotu o ID leży w kontenerze (dla niestakowalnych: liczba przedmiotów)."""
    if kontener is None:
        return 0
    return sum(max(1, p.get("ilosc", 1)) for p in kontener.get("przedmioty", []) if p["id"] == ident)


def _plan_z_pamieci(obraz, wynik, kontenery, idy, nazwy):
    """Uzupełnia wynik planu na podstawie kontenerów z pamięci. Zwraca powód, gdy się nie da (None = ok)."""
    okna = wynik["okna"]
    przypisane, powod = dopasuj_okna(obraz, okna, kontenery)
    if przypisane is None:
        return powod
    for o, k in zip(okna, przypisane):
        o.kontener = k
        o.rola = rola_kontenera(k)
    plecaki = [o for o in okna if o.rola == "plecak"]
    # 14.10: kilka okien "plecak" (np. pusty bag na runy po depo): główny to ten z największą liczbą rzeczy, nie pierwszy
    plecaki.sort(key=lambda o: (_wyglada_na_runy((o.kontener or {})), -len((o.kontener or {}).get("przedmioty", []))))
    zwloki = [o for o in okna if o.rola == "zwloki"]
    runy = [o for o in okna if o.rola == "runy"]
    wynik.update(zrodlo="pamiec", plecak=plecaki[0] if plecaki else None,
                 zwloki=zwloki[-1] if zwloki else None, runy=runy[0] if runy else None)
    if not wynik["zwloki"]:
        return None
    okno = wynik["zwloki"]
    wynik["kontener_zwlok"] = okno.kontener
    bez_id = {n for n in nazwy if n not in NAZWA_ID}        # nazwy z listy, których ID jeszcze nie znamy
    kandydaci = []                                          # (slot, nazwa, ID, ilość) do przeniesienia
    jedzenia_w_plecaku = sum(suma_id(k, i) for k in kontenery if czy_plecak(k) for i in KOLEJNOSC_JEDZENIA)
    dosc_jedzenia = bool(JEDZENIE_MAX) and jedzenia_w_plecaku >= JEDZENIE_MAX
    for p in sorted(okno.kontener.get("przedmioty", []), key=lambda p: p["slot"]):
        ident, ilosc = p["id"], p.get("ilosc", 1)
        widoczny = p["slot"] < len(okno.sloty)
        slot = okno.sloty[p["slot"]] if widoczny else None
        chcemy = ident in idy
        if chcemy and POMIN_CIEZKIE and POMINIETE_CIEZKIE.get(ident, 0) > time.monotonic():
            chcemy = False                         # za_ciezki: pomijamy do końca POMIN_CIEZKIE_S
        if chcemy and dosc_jedzenia and ident in KOLEJNOSC_JEDZENIA:
            chcemy = False                         # w plecaku jest już JEDZENIE_MAX sztuk jedzenia
        if not chcemy and ident not in ID_NAZWA:
            # nieznane ID: może obrazek rozpozna przedmiot z listy, wtedy uczymy się jego ID
            nazwa_obrazka = rozpoznaj(obraz, slot)[0] if widoczny else None
            if nazwa_obrazka in bez_id:
                ID_NAZWA[ident] = nazwa_obrazka
                NAZWA_ID[nazwa_obrazka] = ident
                idy.add(ident)
                wynik["nauczone"].append((ident, nazwa_obrazka))
                chcemy = True
            else:
                wynik["nieznane"] += 1
                if widoczny:
                    zapisz_nieznany(obraz, slot, ident)
                continue
        nazwa = nazwa_id(ident)
        if (JEDZ_ZE_ZWLOK and ident in KOLEJNOSC_JEDZENIA and widoczny and wynik["jedzenie"] is None):
            wynik["jedzenie"] = (slot, nazwa, ident)
        if not chcemy:
            wynik["zostalo"].append(nazwa)
        elif not widoczny:
            wynik["ukryte"].append(nazwa)          # slot schowany pod suwakiem okna
        else:
            kandydaci.append((slot, nazwa, ident, ilosc))
    # pierwszy przedmiot, który ma gdzie wejść (pełny plecak: rope czeka, gold idzie na stos);
    # gdy żaden: pierwszy z celem None -> status pelny_plecak
    for slot, nazwa, ident, ilosc in kandydaci:
        cel, cel_stos = _cel_w_plecaku(wynik["plecak"], ident, ilosc) if wynik["plecak"] else (None, None)
        if wynik["przedmiot"] is None or cel is not None:
            wynik.update(przedmiot=(slot, nazwa), przedmiot_id=(ident, ilosc), cel=cel, cel_stos=cel_stos)
        if cel is not None:
            break
    return None


def _cel_w_plecaku(plecak, ident, ilosc):
    """(slot plecaka, na który upuścić przedmiot, ilość na stosie albo None). Stos tego samego ID
    (< 100 szt., najlepiej taki, na który zmieści się całość) dla każdego ID, o którym nie wiemy,
    że się nie stackuje; inaczej pierwszy wolny widoczny slot. (None, None): plecak pełny."""
    k = plecak.kontener
    widoczne = len(plecak.sloty)
    if ident not in NIESTOSOWE_ID:
        stosy = [p for p in k.get("przedmioty", [])
                 if p["id"] == ident and p.get("ilosc", 1) < MAKS_STOSU and p["slot"] < widoczne]
        stosy.sort(key=lambda p: (p.get("ilosc", 1) + ilosc > MAKS_STOSU, p["slot"]))
        if stosy:
            return plecak.sloty[stosy[0]["slot"]], stosy[0].get("ilosc", 1)
    zajete = {p["slot"] for p in k.get("przedmioty", [])}
    if len(zajete) >= k.get("pojemnosc", 0):
        return None, None
    wolny = next((i for i in range(min(widoczne, k.get("pojemnosc", 0))) if i not in zajete), None)
    return (plecak.sloty[wolny] if wolny is not None else None), None


NIEUDANE_SCALENIA = set()        # ID, których scalenie w plecaku nie wyszło (nie próbujemy znowu)

# --- P5 (13.10): klasyfikacja braku miejsca i wagi z danych ----------------------------
JEDZENIE_MAX = 2           # 14.10 (Karol): przy tylu sztukach jedzenia w plecaku nie zbieramy go ze zwłok (0 = bez limitu);
                           # liczone przed każdym przeniesieniem, więc cały stos (np. 3 cheese) może limit przekroczyć
POMIN_CIEZKIE = 0          # 1 = przedmiot `za_ciezki` pomijamy przez POMIN_CIEZKIE_S (cavebot: LOOT_POMIN_CIEZKIE, domyślnie 0)
POMIN_CIEZKIE_S = 300.0
POMINIETE_CIEZKIE = {}     # ID -> zegar (time.monotonic), do kiedy pomijany
PLIK_PRZEDMIOTOW = KATALOG / "dane_tibia" / "przedmioty.json"
WAGI_ZAPASOWE = {          # oz, wg dane_tibia/przedmioty.json; tylko gdy pliku brak
    "ham": 20.0, "dragon ham": 30.0, "bread": 5.0, "cheese": 4.0, "meat": 13.0, "fish": 5.2,
    "gold coin": 0.1, "blank rune": 1.2,
}
_WAGI_ID = None


def _wagi_po_id():
    """{id_klienta: waga oz} z przedmioty.json (raz); przy błędzie pliku z WAGI_ZAPASOWE po nazwie."""
    global _WAGI_ID
    if _WAGI_ID is None:
        wagi = {}
        try:
            import json
            with open(PLIK_PRZEDMIOTOW, encoding="utf-8") as f:
                dane = json.load(f)
            for lista in (dane.get("kategorie") or {}).values():
                for it in lista:
                    i, w = it.get("id_klienta"), it.get("waga_oz")
                    if isinstance(i, int) and isinstance(w, (int, float)):
                        wagi[i] = float(w)
        except Exception:
            wagi = {}
        for nazwa, w in WAGI_ZAPASOWE.items():
            i = NAZWA_ID.get(nazwa)
            if i is not None:
                wagi.setdefault(i, w)
        _WAGI_ID = wagi
    return _WAGI_ID


def waga_id(ident):
    """Waga jednej sztuki (oz) albo None, gdy nieznana."""
    return _wagi_po_id().get(ident)


def klasyfikuj_brak_miejsca(plecak, ident, ilosc, cap):
    """Powód braku miejsca na przedmiot: (powod, szczegoly). powod: "sloty_pelne" (zajęte >= pojemność),
    "slot_ukryty" (są wolne sloty, ale żaden nie jest widoczny: pod suwakiem okna), "za_ciezki"
    (cap = wolne oz < waga * ilość), "nieznany". Tylko odczyt, bez inputu do gry; cap to wolne oz."""
    k = (plecak.kontener if plecak is not None else None) or {}
    zajete = {p["slot"] for p in k.get("przedmioty", [])}
    pojemnosc = k.get("pojemnosc", 0)
    widoczne = len(plecak.sloty) if plecak is not None else 0
    waga = waga_id(ident)
    det = {"zajete": len(zajete), "pojemnosc": pojemnosc, "widoczne": widoczne, "cap": cap,
           "waga": waga, "ilosc": ilosc, "id": ident}
    if pojemnosc and len(zajete) >= pojemnosc:
        return "sloty_pelne", det
    if pojemnosc and not any(i not in zajete for i in range(min(widoczne, pojemnosc))):
        return "slot_ukryty", det
    if waga is not None and cap is not None and cap < waga * ilosc:
        return "za_ciezki", det
    return "nieznany", det


def _cap_gracza():
    """Wolne oz gracza z pamięci (pole cap; max_cap nie jest używany do decyzji) albo None."""
    try:
        g = _zapytaj({"cmd": "gracz"}).get("gracz") or {}
        c = g.get("cap")
        return float(c) if isinstance(c, (int, float)) else None
    except Exception:
        return None


def _powod_braku_miejsca(p, log, kiedy):
    """Klasyfikuje i loguje brak miejsca dla przedmiotu z planu `p`; przy za_ciezki i POMIN_CIEZKIE
    dopisuje ID do POMINIETE_CIEZKIE. Zwraca powód albo None (brak danych)."""
    try:
        if not p.get("przedmiot_id") or not p.get("plecak"):
            return None
        ident, ilosc = p["przedmiot_id"]
        powod, d = klasyfikuj_brak_miejsca(p["plecak"], ident, ilosc, _cap_gracza())
        log(f"loot: {kiedy}: powód {powod} ({nazwa_id(ident)} x{ilosc}; zajęte {d['zajete']}/{d['pojemnosc']}, "
            f"widoczne {d['widoczne']}, cap {d['cap']}, waga {d['waga']})")
        if powod == "za_ciezki" and POMIN_CIEZKIE:
            POMINIETE_CIEZKIE[ident] = time.monotonic() + POMIN_CIEZKIE_S
        return powod
    except Exception:
        return None


def scalenie(plecak):
    """Rozbity stos w plecaku (pewne stosy: gold, jedzenie): (slot z, slot na, ID) albo None.
    Mniejszy stos idzie na większy, gdy razem mieszczą się w 100. Tylko widoczne sloty."""
    if plecak is None or plecak.kontener is None:
        return None
    widoczne = len(plecak.sloty)
    wg_id = {}
    for p in plecak.kontener.get("przedmioty", []):
        if (p["id"] in STOSOWE_ID and p["id"] not in NIESTOSOWE_ID | NIEUDANE_SCALENIA
                and p["slot"] < widoczne):
            wg_id.setdefault(p["id"], []).append(p)
    for ident, stosy in sorted(wg_id.items()):
        stosy.sort(key=lambda p: (p.get("ilosc", 1), -p["slot"]))
        for i, maly in enumerate(stosy):
            for duzy in reversed(stosy[i + 1:]):
                if maly.get("ilosc", 1) + duzy.get("ilosc", 1) <= MAKS_STOSU:
                    return plecak.sloty[maly["slot"]], plecak.sloty[duzy["slot"]], ident
    return None


# --- plan zbierania ----------------------------------------------------------

def _role_luzno_z_pamieci(obraz, okna, kontenery):
    """Plan z obrazka (pamięć nie zgadza się z ekranem): ze znanych kontenerów wyłapujemy tylko okna bagu na runy
    (15.10: pełny bag na runy o tytule "backpack" był brany za plecak lootu). Okno "plecak" staje się "runy",
    gdy zgadza się co do zajętości slotów z bagiem na runy, a z żadnym innym kontenerem nie-na-runy.
    Przy błędzie albo niejednoznaczności role zostają z tytułów."""
    try:
        if not kontenery or not okna:
            return
        runowe = [k for k in kontenery if czy_runy(k)]
        inne = [k for k in kontenery if not czy_runy(k)]
        if len(runowe) != 1:
            return
        for o in okna:
            if o.rola != "plecak":
                continue
            if _niezgodnosci(obraz, o, runowe[0]) != 0:
                continue
            if all(_niezgodnosci(obraz, o, k) not in (0,) for k in inne):
                o.rola = "runy"
    except Exception:
        return


def _plan_z_obrazu(obraz, wynik, nazwy):
    """Dawne rozpoznawanie: role okien po tytule, przedmioty po ikonach."""
    okna = wynik["okna"]
    _role_luzno_z_pamieci(obraz, okna, wynik.get("kontenery"))
    plecaki = [o for o in okna if o.rola == "plecak"]
    zwloki = [o for o in okna if o.rola == "zwloki"]
    runy = [o for o in okna if o.rola == "runy"]
    wynik.update(zrodlo="obraz", plecak=plecaki[0] if plecaki else None,
                 zwloki=zwloki[-1] if zwloki else None, runy=runy[0] if runy else None)
    if not wynik["zwloki"]:
        return
    for slot, nazwa, _ in zawartosc(obraz, wynik["zwloki"]):
        if nazwa is None:
            continue
        if nazwa == "?":
            wynik["nieznane"] += 1
            zapisz_nieznany(obraz, slot)
        else:
            if JEDZ_ZE_ZWLOK and nazwa in JEDZENIE and wynik["jedzenie"] is None:
                wynik["jedzenie"] = (slot, nazwa, NAZWA_ID.get(nazwa))   # bez pamięci: jeden Use (ile ubyło: nie wiadomo)
            if nazwa in nazwy:
                wynik["przedmiot"] = wynik["przedmiot"] or (slot, nazwa)
            else:
                wynik["zostalo"].append(nazwa)
    if wynik["plecak"]:
        nazwa_przedmiotu = wynik["przedmiot"][1] if wynik["przedmiot"] else None
        if nazwa_przedmiotu in STOSOWE:
            # stos szukamy we wszystkich oknach "plecak" (nie w bagu na runy), nie tylko w pierwszym
            for okno in plecaki:
                for slot, nazwa, _ in zawartosc(obraz, okno):
                    if nazwa == nazwa_przedmiotu:
                        wynik["plecak"], wynik["cel"] = okno, slot
                        break
                if wynik["cel"] is not None:
                    break
        if wynik["cel"] is None:
            for okno in plecaki:
                wolny = next((s for s in okno.sloty if czy_pusty(obraz, s)), None)
                if wolny is not None:
                    wynik["plecak"], wynik["cel"] = okno, wolny
                    break


def plan(obraz, lista=DO_ZEBRANIA, pamiec=True):
    """Co zrobić na tym zrzucie. Słownik: zwloki, plecak, przedmiot (slot, nazwa), cel (slot plecaka),
    nieznane (ile przedmiotów nierozpoznanych), zostalo (nazwy bez pozycji do zebrania), oraz:
    zrodlo ("pamiec" | "obraz"), pamiec (powód, gdy pamięć nie zadziałała), kontenery (surowy odczyt),
    przedmiot_id ((ID, ilość) przy planie z pamięci), ukryte (do zebrania, ale pod suwakiem okna).

    Najpierw komenda "kontenery" (ID i ilości z pamięci gry, pozycje slotów z obrazka), a gdy nie działa
    albo nie zgadza się z ekranem, dawne rozpoznawanie ikon."""
    idy, nazwy = rozdziel_liste(lista)
    okna = znajdz_okna(obraz)
    wynik = {"okna": okna, "plecak": None, "zwloki": None, "przedmiot": None, "cel": None,
             "nieznane": 0, "zostalo": [], "zrodlo": None, "pamiec": None, "kontenery": None,
             "kontener_zwlok": None, "przedmiot_id": None, "ukryte": [], "nauczone": [],
             "jedzenie": None, "cel_stos": None, "runy": None}
    if pamiec:
        kontenery, powod = kontenery_z_pamieci()
        wynik["kontenery"] = kontenery
        if kontenery is not None:
            powod = _plan_z_pamieci(obraz, wynik, kontenery, idy, nazwy)
        if powod is None:
            return wynik
        wynik["pamiec"] = powod
        for k in ("przedmiot", "cel", "kontener_zwlok", "przedmiot_id", "jedzenie", "cel_stos"):
            wynik[k] = None
        wynik.update(nieznane=0, zostalo=[], ukryte=[])
        for o in okna:                                   # role wracają do rozpoznania po tytule
            o.kontener = None
            o.rola = rola_z_tytulu(o.tytul)
    _plan_z_obrazu(obraz, wynik, nazwy)
    return wynik


# --- zbieranie (wysyła input) -------------------------------------------------

def _xyz(p):
    if isinstance(p, dict):
        return p["x"], p["y"], p.get("z")
    return (*p[:2], p[2] if len(p) > 2 else None)


def przylega(pozycja_zwlok, gracz_pozycja):
    x1, y1, z1 = _xyz(pozycja_zwlok)
    x2, y2, z2 = _xyz(gracz_pozycja)
    return (z1 is None or z2 is None or z1 == z2) and max(abs(x1 - x2), abs(y1 - y2)) <= 1


def _zmiana_srodka(przed, po):
    """Ułamek zmienionych pikseli w obszarze mapy (wykrywanie okna z pytaniem o ilość)."""
    L, T, R, B = ekran.prostokat_mapy(po)
    a = np.asarray(przed.convert("L").crop((L, T, R, B))).astype(int)
    b = np.asarray(po.convert("L").crop((L, T, R, B))).astype(int)
    return float((np.abs(a - b) > 25).mean())


def _zrzut(mysz):
    """Zrzut w pikselach ekranu X (współrzędne slotów idą wprost do XTEST)."""
    obraz = ekran.zrzut()
    rozmiar = ekran._rozmiar_ekranu(mysz.ekran)
    return obraz if obraz.size == rozmiar else obraz.resize(rozmiar)


def _pauza(a=0.3, b=0.7):
    time.sleep(random.uniform(a, b))


def zamknij_okno(mysz, okno):
    """Klik w X okna kontenera. Zwraca True, gdy znamy położenie przycisku."""
    p = okno.przycisk_zamkniecia
    if not p:
        return False
    mysz.lewy(*p, drganie=2)
    return True


def _sasiednie_pola(dx, dy):
    """Pola przylegające do gracza (bez jego własnego), najpierw najbliższe (dx, dy)."""
    pola = [(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if (x, y) not in ((0, 0), (dx, dy))]
    return sorted(pola, key=lambda q: abs(q[0] - dx) + abs(q[1] - dy))[:3]


def znajdz_okno_ilosci(obraz):
    """Lewy górny róg wzorca tytułu okna "Move Objects" (pytanie o ilość) albo None. Szuka w całym
    obszarze mapy (położenie okna zależy od rozmiaru okna klienta): zgrubnie po kilku wierszach
    i co trzeciej kolumnie wzorca, potem dokładnie wokół najlepszego trafienia."""
    wzorzec = IKONY / "dialog_ilosc.png"
    if not wzorzec.exists():
        return None
    wz = np.asarray(Image.open(wzorzec).convert("L"), np.int16)
    wh, ww = wz.shape
    sz = np.asarray(obraz.convert("L"), np.int16)
    h, w = sz.shape
    L, T, R, B = ekran.prostokat_mapy(obraz)
    x0, x1 = max(0, min(L, w - ww)), max(1, min(R, w) - ww)
    y0, y1 = max(0, T - 20), min(h - wh, B + 20)
    if x1 <= x0 or y1 <= y0:
        return None
    wiersze = (1, 5, 9, 14)
    kol = slice(0, ww, 3)
    suma = None
    for r in wiersze:
        pas = sz[y0 + r:y1 + r, x0:x1 + ww - 1 + 1]
        okna = np.lib.stride_tricks.sliding_window_view(pas, ww, axis=1)[:, :x1 - x0, kol]
        d = np.abs(okna - wz[r, kol]).mean(axis=2)
        suma = d if suma is None else suma + d
    suma /= len(wiersze)
    iy, ix = np.unravel_index(int(suma.argmin()), suma.shape)
    if suma[iy, ix] > 25:
        return None
    najlepszy = (1e9, None)
    for y in range(max(0, y0 + iy - 2), min(h - wh, y0 + iy + 2) + 1):
        for x in range(max(0, x0 + ix - 2), min(w - ww, x0 + ix + 2) + 1):
            d = float(np.abs(sz[y:y + wh, x:x + ww] - wz).mean())
            if d < najlepszy[0]:
                najlepszy = (d, (x, y))
    return najlepszy[1] if najlepszy[0] < 10 else None


def okno_ilosci(obraz):
    """Czy na ekranie jest okno "Move Objects" (pytanie o ilość przy przenoszeniu stosu)."""
    return znajdz_okno_ilosci(obraz) is not None


JEDZENIE = ("ham", "meat", "cheese")   # fallback obrazkowy (są ikony); kolejność: co syci najdłużej


def _jedzenie_z_pamieci(obraz):
    """Jedzenie w plecaku według pamięci: (slot na ekranie, nazwa, ID, numer kontenera) w kolejności
    KOLEJNOSC_JEDZENIA albo None, gdy nie ma. Wyjątek _BezPamieci, gdy pamięć nie działa / nie pasuje."""
    okna = znajdz_okna(obraz)
    kontenery, powod = kontenery_z_pamieci()
    if kontenery is None:
        raise _BezPamieci(powod)
    przypisane, powod = dopasuj_okna(obraz, okna, kontenery)
    if przypisane is None:
        raise _BezPamieci(powod)
    kandydaci = []
    for o, k in zip(okna, przypisane):
        if not czy_plecak(k):
            continue
        for p in k.get("przedmioty", []):
            if p["id"] in KOLEJNOSC_JEDZENIA and p["slot"] < len(o.sloty):
                kandydaci.append((KOLEJNOSC_JEDZENIA.index(p["id"]), p["slot"], o.sloty[p["slot"]],
                                  p["id"], k["numer"]))
    if not any(czy_plecak(k) for k in przypisane):
        raise _BezPamieci("nie widzę plecaka w pamięci")
    if not kandydaci:
        return None
    _, _, slot, ident, numer = min(kandydaci, key=lambda c: c[:2])
    return slot, nazwa_id(ident), ident, numer


class _BezPamieci(Exception):
    pass


def _ile_w_kontenerze(numer, ident):
    """Sztuk ID w kontenerze o numerze według świeżego odczytu pamięci; None: nie wiadomo."""
    kontenery, _ = kontenery_z_pamieci()
    if kontenery is None:
        return None
    k = next((k for k in kontenery if k.get("numer") == numer), None)
    return suma_id(k, ident) if k is not None else None


def blanki_i_miejsce(ids=tuple(sorted(ID_RUN_W_POJEMNIKU))):
    """Z pamięci (bez myszy): (sztuk runy/blanków w głównym plecaku, wolnych pól w pojemniku na runy albo None,
    gdy pojemnik nie jest otwarty). None: odczyt nie działa."""
    kon, _ = kontenery_z_pamieci()
    if kon is None:
        return None
    ile = sum(max(1, q.get("ilosc", 1)) for k in kon if czy_plecak(k) and not czy_runy(k)
              for q in k.get("przedmioty", []) if q["id"] in ids)
    runy = next((k for k in kon if czy_runy(k)), None)
    wolne = None if runy is None else max(0, int(runy.get("pojemnosc", 0)) - len(runy.get("przedmioty", [])))
    return ile, wolne


def przenies_do_runow(ids=tuple(sorted(ID_RUN_W_POJEMNIKU)), maks=30, log=print):
    """Przenosi runy (domyślnie blanki i gotowe runy: ID_RUN_W_POJEMNIKU) z głównego plecaka do pojemnika na runy
    (drugi bag, tylko z runami): drag z slotu na pierwszy wolny widoczny slot. Zwraca liczbę przeniesionych sztuk.
    Bez otwartego pojemnika na runy (albo bez wolnego widocznego slotu) nic nie robi."""
    ruszono = 0
    with ekran.Mysz() as mysz:
        for _ in range(maks):
            bot.sprawdz_stop()
            obraz = _zrzut(mysz)
            p = plan(obraz, [])
            plecak, runy = p.get("plecak"), p.get("runy")
            if plecak is None or plecak.kontener is None or runy is None or runy.kontener is None:
                log("przenoszenie run: nie widzę plecaka albo pojemnika na runy (otwarte oba okna)")
                break
            widoczne = len(plecak.sloty)
            zrodlo = [q for q in plecak.kontener.get("przedmioty", [])
                      if q["id"] in ids and q["slot"] < widoczne]
            if not zrodlo:
                break
            k = runy.kontener
            zajete = {q["slot"] for q in k.get("przedmioty", [])}
            wolny = next((i for i in range(min(len(runy.sloty), k.get("pojemnosc", 0))) if i not in zajete), None)
            if wolny is None:
                log("przenoszenie run: brak wolnego widocznego pola w pojemniku na runy")
                break
            przed = sum(1 for q in k.get("przedmioty", []))
            mysz.przeciagnij(*plecak.sloty[zrodlo[0]["slot"]].srodek, *runy.sloty[wolny].srodek, drganie=4)
            _pauza(0.4, 0.7)
            _okno_ilosci_ok(mysz, "runy", log, obraz)
            po = kontenery_z_pamieci()[0]
            kon = next((c for c in (po or []) if c.get("numer") == k.get("numer")), None)
            if kon is None or len(kon.get("przedmioty", [])) <= przed:
                log("przenoszenie run: przeciągnięcie nie podziałało, przerywam")
                break
            ruszono += 1
            log(f"przenoszenie run: {nazwa_id(zrodlo[0]['id'])} -> pojemnik na runy ({ruszono})")
    return ruszono


def okna_z_kontenerami(obraz):
    """[(okno, kontener)] otwartych okien kontenerów (pamięć + ekran) albo (None, powód)."""
    okna = znajdz_okna(obraz)
    kontenery, powod = kontenery_z_pamieci()
    if kontenery is None:
        return None, f"pamięć: {powod}"
    przypisane, powod = dopasuj_okna(obraz, okna, kontenery)
    if przypisane is None:
        return None, f"okna: {powod}"
    return list(zip(okna, przypisane)), None


def przenies_miedzy(ids, skad, dokad, maks=25, log=print):
    """Przeciąga przedmioty o ID z `ids` z okna kontenera spełniającego `skad(kontener)` na pierwsze wolne widoczne
    pole okna spełniającego `dokad(kontener)`. Po każdym ruchu weryfikuje w pamięci (ubyło w źródle, przybyło w celu).
    Zwraca (przeniesione, powód_stopu albo None)."""
    ruszono = 0
    with ekran.Mysz() as mysz:
        for _ in range(maks):
            bot.sprawdz_stop()
            obraz = _zrzut(mysz)
            pary, powod = okna_z_kontenerami(obraz)
            if pary is None:
                return ruszono, powod
            z = next(((o, k) for o, k in pary if skad(k)), None)
            do = next(((o, k) for o, k in pary if dokad(k)), None)
            if z is None or do is None:
                return ruszono, "brak okna źródła albo celu"
            oz, kz = z
            od, kd = do
            zrodlo = [q for q in kz.get("przedmioty", []) if q["id"] in ids and q["slot"] < len(oz.sloty)]
            if not zrodlo:
                return ruszono, None
            zajete = {q["slot"] for q in kd.get("przedmioty", [])}
            wolny = next((i for i in range(min(len(od.sloty), kd.get("pojemnosc", 0))) if i not in zajete), None)
            if wolny is None:
                return ruszono, "cel pełny albo bez wolnego widocznego pola"
            przed_cel = len(kd.get("przedmioty", []))
            przed_zrodlo = len(kz.get("przedmioty", []))
            mysz.przeciagnij(*oz.sloty[zrodlo[0]["slot"]].srodek, *od.sloty[wolny].srodek, drganie=4)
            _pauza(0.4, 0.7)
            _okno_ilosci_ok(mysz, "przenoszenie", log, obraz)
            kon, _ = kontenery_z_pamieci()
            kz2 = next((c for c in (kon or []) if c.get("numer") == kz.get("numer")), None)
            kd2 = next((c for c in (kon or []) if c.get("numer") == kd.get("numer")), None)
            if kz2 is None or kd2 is None or len(kd2.get("przedmioty", [])) <= przed_cel \
                    or len(kz2.get("przedmioty", [])) >= przed_zrodlo:
                return ruszono, "przeciągnięcie nie zadziałało"
            ruszono += 1
            log(f"przenoszenie: {nazwa_id(zrodlo[0]['id'])} ({ruszono})")
    return ruszono, "limit ruchów"


def zamknij_kontener(numer, log=print):
    """Zamyka okno kontenera o numerze z pamięci (klik w X). True, gdy po chwili już go nie ma."""
    with ekran.Mysz() as mysz:
        pary, _ = okna_z_kontenerami(_zrzut(mysz))
        for o, k in pary or []:
            if k.get("numer") == numer:
                if zamknij_okno(mysz, o):
                    _pauza(0.4, 0.7)
                break
    kon, _ = kontenery_z_pamieci()
    return not any(c.get("numer") == numer for c in (kon or []))


def zjedz(ile=2, log=print):
    """Je jedzenie z plecaka: Ctrl+klik (Use). Z pamięci: jedzenie po ID (KOLEJNOSC_JEDZENIA), slot na
    ekranie z dopasowania okien, po Use sprawdzenie w pamięci, czy ubyło (nie ubyło = najedzony, koniec).
    Gdy pamięć nie działa: dawne rozpoznawanie ikon (JEDZENIE).
    Zwraca listę zjedzonych nazw (pusta, gdy w plecaku nie ma jedzenia albo postać jest najedzona)."""
    zjedzone = []
    with ekran.Mysz() as mysz:
        for _ in range(ile):
            bot.sprawdz_stop()
            obraz = _zrzut(mysz)
            try:
                znalezione = _jedzenie_z_pamieci(obraz)
            except _BezPamieci as e:
                if zjedz.ostatni_powod != str(e):
                    log(f"jedzenie: pamięć: {e}, szukam obrazkiem")
                zjedz.ostatni_powod = str(e)
            else:
                zjedz.ostatni_powod = None
                if znalezione is None:
                    log("jedzenie: brak jedzenia w plecaku")
                    break
                slot, nazwa, ident, numer = znalezione
                przed = _ile_w_kontenerze(numer, ident)
                mysz.lewy(*slot.srodek, modyfikator="Control_L", drganie=3)
                _pauza(0.6, 0.8)
                po = _ile_w_kontenerze(numer, ident)
                if przed is not None and po is not None and po >= przed:
                    log(f"jedzenie: {nazwa} nie ubyło, najedzony")
                    break
                zjedzone.append(nazwa)
                _pauza(0.1, 0.3)
                continue
            # fallback obrazkowy
            plecaki = [o for o in znajdz_okna(obraz) if o.rola == "plecak"]
            if not plecaki:
                log("jedzenie: nie widzę plecaka")
                break
            sloty = {nazwa: slot for slot, nazwa, _ in zawartosc(obraz, plecaki[0]) if nazwa in JEDZENIE}
            nazwa = next((n for n in JEDZENIE if n in sloty), None)
            if nazwa is None:
                log("jedzenie: brak jedzenia w plecaku")
                break
            mysz.lewy(*sloty[nazwa].srodek, modyfikator="Control_L", drganie=3)
            zjedzone.append(nazwa)
            _pauza(0.6, 1.1)
    return zjedzone


zjedz.ostatni_powod = None


LACZNIE = {}      # zebrane od startu procesu: nazwa -> sztuk


def _log_cenne(prefiks, zostalo, log):
    """SPEC_ekonomia_lootu_1017: cenne (NPC >= 100 gp) przedmioty, które zostały w zwłokach (nie zbieramy ich),
    jako jedna linia logu dla telemetrii/dziennika ekonomii. Tylko log, nigdy nie zmienia zbierania."""
    try:
        import ekonomia  # noqa: PLC0415
        opis = ekonomia.cenne_opis(ekonomia.cenne(list(zostalo or [])))
        if opis:
            log(f"{prefiks}: cenne zostały {opis}")
    except Exception:       # dziennik nigdy nie wywraca lootu
        pass


def _plan_teraz(mysz, lista, log):
    """Świeży zrzut i plan. Gdy pamięć nie zgadza się z ekranem (zrzut i odczyt z różnych chwil),
    jeszcze jedna próba po krótkiej pauzie. Powód przejścia na obrazek logujemy przy zmianie."""
    obraz = _zrzut(mysz)
    p = plan(obraz, lista)
    if p["pamiec"] and p["pamiec"].startswith("niezgodne"):
        _pauza(0.15, 0.3)
        obraz = _zrzut(mysz)
        p = plan(obraz, lista)
    if p["pamiec"] != _plan_teraz.ostatni_powod:
        if p["pamiec"]:
            log(f"loot: pamięć: {p['pamiec']}, rozpoznaję obrazkiem")
        elif _plan_teraz.ostatni_powod:
            log("loot: pamięć znowu działa")
        _plan_teraz.ostatni_powod = p["pamiec"]
    for ident, nazwa in p["nauczone"]:
        log(f"loot: {nazwa} ma ID {ident} (z obrazka), dopisz do do_zebrania.txt: {ident} # {nazwa}")
    return obraz, p


_plan_teraz.ostatni_powod = None


def _zebrano_z_pamieci(przed, po, ident=None):
    """Ile sztuk przedmiotu (domyślnie przenoszonego) ubyło ze zwłok, według pamięci. None: nie wiadomo."""
    if ident is None:
        ident = przed["przedmiot_id"][0] if przed["przedmiot_id"] else None
    if przed["zrodlo"] != "pamiec" or ident is None or po["kontenery"] is None:
        return None
    numer = przed["kontener_zwlok"]["numer"]
    teraz = next((k for k in po["kontenery"] if k.get("numer") == numer), None)
    if teraz is None or teraz.get("id") != przed["kontener_zwlok"].get("id"):
        return None
    return suma_id(przed["kontener_zwlok"], ident) - suma_id(teraz, ident)


def _kontener_po_numerze(kontenery, wzor):
    if not kontenery or not wzor:
        return None
    k = next((k for k in kontenery if k.get("numer") == wzor.get("numer")), None)
    return k if k is not None and k.get("id") == wzor.get("id") else None


def _sprawdz_plecak(przed, po, ile, log):
    """Po przeniesieniu: czy w plecaku przybyło tyle, ile ubyło ze zwłok, i czy przedmiot wszedł
    na stos. Gdy upuszczony na stos (zmieściłby się) zrobił osobny slot: ID się nie stackuje
    (NIESTOSOWE_ID). Zwraca opis albo None, gdy nie da się sprawdzić."""
    if przed["plecak"] is None or przed["plecak"].kontener is None or not przed["przedmiot_id"]:
        return None
    k_przed = przed["plecak"].kontener
    k_po = _kontener_po_numerze(po["kontenery"], k_przed)
    if k_po is None:
        return None
    ident = przed["przedmiot_id"][0]
    nazwa = nazwa_id(ident)
    przybylo = suma_id(k_po, ident) - suma_id(k_przed, ident)
    if przybylo != ile:
        log(f"loot: {nazwa}: ze zwłok -{ile}, w plecaku +{przybylo} (niezgodne)")
        return "niezgodne"
    if przed["cel_stos"] is None:
        return "wolny slot"
    wpisy = lambda k: sum(1 for p in k.get("przedmioty", []) if p["id"] == ident)
    if (wpisy(k_po) > wpisy(k_przed) and przed["cel_stos"] + ile <= MAKS_STOSU
            and ident not in PEWNE_STOSY_ID):
        NIESTOSOWE_ID.add(ident)
        log(f"loot: {nazwa} (ID {ident}) nie łączy się w stos, następne na wolny slot")
        return "osobno"
    return "stos"


def _okno_ilosci_ok(mysz, nazwa, log, przed=None, czekaj_s=1.0):
    """Po przeciągnięciu stosu: gdy jest okno "Move Objects", klik "Ok" względem znalezionego okna
    (suwak stoi na całości). Okno pojawia się z opóźnieniem, więc sprawdzamy kilka razy do czekaj_s.
    Bez klawiatury: Enter bez dialogu otwiera czat. Po kliku sprawdza, czy okno zniknęło."""
    koniec = time.monotonic() + czekaj_s
    poz = None
    while True:
        poz = znajdz_okno_ilosci(_zrzut(mysz))
        if poz is not None or time.monotonic() >= koniec:
            break
        time.sleep(0.15)
    if poz is None:
        return False
    for proba in (1, 2):
        log(f"loot: pytanie o ilość ({nazwa}), Ok" + ("" if proba == 1 else " (ponowny klik)"))
        bot.sprawdz_stop()
        mysz.lewy(poz[0] + 60 + OK_DX, poz[1] + 66 + OK_DY, drganie=2)
        _pauza(0.3, 0.5)
        poz = znajdz_okno_ilosci(_zrzut(mysz))
        if poz is None:
            return True
    log(f"loot: okno ilości ({nazwa}) nadal otwarte po dwóch klikach")
    return True


def _sprzatnij_okno_ilosci(mysz, log):
    """Jednorazowe sprawdzenie na koniec zbierania: zostawione okno "Move Objects" zamykamy kliknięciem Ok."""
    _okno_ilosci_ok(mysz, "sprzątanie", log, czekaj_s=0.0)


def _zjedz_ze_zwlok(mysz, p, lista, wynik, log):
    """Use na jedzeniu w zwłokach. Zwraca (nowy plan, czy zjedzono). Nie ubyło = najedzony."""
    slot, nazwa, ident = p["jedzenie"]
    mysz.lewy(*slot.srodek, modyfikator="Control_L", drganie=3)
    _pauza(0.6, 0.7)
    _, nowy = _plan_teraz(mysz, lista, log)
    ile = _zebrano_z_pamieci(p, nowy, ident)
    if ile is not None and ile > 0:
        wynik["zjedzono"].append(nazwa)
        log(f"loot: zjedzono ze zwłok: {nazwa}")
        return nowy, True
    log(f"loot: {nazwa} ze zwłok nie ubyło, najedzony" + ("" if ile is not None else " (pamięć nie wie)"))
    return nowy, False


def _scal_stosy(mysz, p, lista, log):
    """Łączy rozbite stosy w plecaku (np. dwa sery po 1). Zwraca aktualny plan."""
    for _ in range(MAKS_SCALEN):
        bot.sprawdz_stop()
        ruch = scalenie(p["plecak"]) if p["zrodlo"] == "pamiec" else None
        if ruch is None:
            break
        z, na, ident = ruch
        k_przed = p["plecak"].kontener
        przed = _zrzut(mysz)
        mysz.przeciagnij(*z.srodek, *na.srodek, drganie=4)
        _pauza(0.25, 0.5)
        _okno_ilosci_ok(mysz, nazwa_id(ident), log, przed)
        _, nowy = _plan_teraz(mysz, lista, log)
        k_po = _kontener_po_numerze(nowy["kontenery"], k_przed)
        wpisy = lambda k: sum(1 for q in k.get("przedmioty", []) if q["id"] == ident)
        if k_po is None or wpisy(k_po) >= wpisy(k_przed):
            NIEUDANE_SCALENIA.add(ident)
            log(f"loot: scalenie {nazwa_id(ident)} w plecaku nie wyszło, przerywam")
            return nowy
        log(f"loot: scalono stos {nazwa_id(ident)} w plecaku")
        p = nowy
    return p


def _opis_ilosci(ilosci):
    return ", ".join(f"{n} +{i}" for n, i in ilosci.items()) or "nic"


# --- otwieranie zwłok potwierdzane pamięcią ------------------------------------------
# Ctrl+klik na zwłokach, które mają już otwarte okno, ZAMYKA je (przełącznik). Dlatego po każdym
# Ctrl+kliku sprawdzamy w pamięci (komenda "kontenery", < 1 ms), czy pojawił się nowy kontener zwłok,
# i nigdy nie klikamy drugi raz pola, którego zwłoki są otwarte. Klik w trakcie kroku postaci trafia
# w pole obok (kamera w pół kroku), więc przed pierwszym klikiem czekamy na postój.

ODCZYTY_OTWARCIA_DALSZE = 4   # 13.10: odczyty po kolejnym pustym kliku w tym samym otwieraniu (pole zgadywane, ~0,5 s; 1. klik: pełne)
ODCZYTY_OTWARCIA = 8      # odczyty pamięci co ~0,1 s po Ctrl+kliku (razem ~1 s)
ODCZYTY_ZAMKNIECIA = 6    # po zamknięciu okna zwłok: tyle odczytów (~0,6 s) na zniknięcie z pamięci
POSTOJ_ODCZYTOW = 5       # postój = ta sama pozycja w tylu kolejnych odczytach co ~0,13 s (> 0,6 s)
POSTOJ_LIMIT = 16         # maks. odczytów pozycji przy czekaniu na postój (~2 s)


def _klucz(k):
    return k.get("numer"), k.get("id")


def _odczyt_kontenerow():
    """Kontenery z pamięci albo None, gdy odczytowi nie można ufać: błąd gniazda/rdzenia, pusta lista
    (rdzeń zwraca [] także wtedy, gdy zgubił mapę kontenerów) albo brak plecaka (plecak jest zawsze otwarty)."""
    try:
        odp = _zapytaj({"cmd": "kontenery"})
    except Exception:
        return None
    kontenery = odp.get("kontenery")
    if odp.get("blad") or not kontenery or not any(czy_plecak(k) for k in kontenery):
        return None
    return kontenery


def ile_jedzenia():
    """Sztuk jedzenia (KOLEJNOSC_JEDZENIA: meat, ham, cheese, bread...) w otwartych plecakach według
    pamięci gry; None, gdy odczyt nie działa albo plecaka nie widać. Tylko odczyt, bez inputu do gry."""
    kontenery = _odczyt_kontenerow()
    if kontenery is None:
        return None
    return sum(suma_id(k, i) for k in kontenery if czy_plecak(k) for i in KOLEJNOSC_JEDZENIA)


def _zwloki_w(kontenery):
    return {_klucz(k): k for k in kontenery if not czy_plecak(k) and not czy_runy(k)}


def _pozycja_gracza():
    """(x, y, z) z komendy "pozycja" albo None (w testach podmieniane)."""
    try:
        if _pozycja_gracza.nazwa is None:
            _pozycja_gracza.nazwa = bot.nazwa_postaci()
        p = _zapytaj({"cmd": "pozycja", "nazwa": _pozycja_gracza.nazwa})["pozycja"]
        return p["x"], p["y"], p["z"]
    except (Exception, SystemExit):
        return None


_pozycja_gracza.nazwa = None


def _czekaj_na_postoj(gracz):
    """Czeka, aż pozycja gracza będzie stała przez POSTOJ_ODCZYTOW odczytów (dłużej niż krok).
    Zwraca (pozycja, stoi): stoi None, gdy pozycji nie da się odczytać (zostaje `gracz`)."""
    poz = _pozycja_gracza()
    if poz is None:
        return gracz, None
    takich = 1
    for _ in range(POSTOJ_LIMIT):
        if takich >= POSTOJ_ODCZYTOW:
            return poz, True
        _pauza(0.12, 0.14)
        teraz = _pozycja_gracza()
        if teraz is None:
            return poz, None
        takich = takich + 1 if teraz == poz else 1
        poz = teraz
    return poz, takich >= POSTOJ_ODCZYTOW


def _pola_ze_stworami(gracz):
    """Pola (dx, dy) przy graczu, na których stoi żywy stwór (Ctrl+klik dałby "You cannot use this object")."""
    try:
        stwory = _zapytaj({"cmd": "stwory"}).get("stwory") or []
        gx, gy, gz = _xyz(gracz)
        return {(s["x"] - gx, s["y"] - gy) for s in stwory
                if s.get("hp", 100) > 0 and (gz is None or s.get("z", gz) == gz)
                and max(abs(s["x"] - gx), abs(s["y"] - gy)) == 1}
    except Exception:
        return set()


def _pola_proby(dx, dy, powtorz):
    """Kolejność Ctrl+klików: pole zwłok (dwa razy, gdy pierwszy klik mógł paść w trakcie kroku),
    potem pozostałe pola wokół gracza (3x3 bez gracza), najbliższe (dx, dy) najpierw."""
    reszta = [(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if (x, y) not in ((0, 0), (dx, dy))]
    reszta.sort(key=lambda q: (max(abs(q[0] - dx), abs(q[1] - dy)), abs(q[0] - dx) + abs(q[1] - dy)))
    return [(dx, dy)] * (2 if powtorz else 1) + reszta


def _czekaj_na_otwarcie(przed, odczyty=None):
    """Po Ctrl+kliku: (nowy kontener zwłok albo None, zamknięte), gdzie zamknięte = klucze okien zwłok,
    które były otwarte przed klikiem, a zniknęły (klik trafił w już otwarte zwłoki i je zamknął)."""
    zamkniete = set()
    for _ in range(ODCZYTY_OTWARCIA if odczyty is None else odczyty):
        _pauza(0.1, 0.12)
        kontenery = _odczyt_kontenerow()
        if kontenery is None:
            continue
        teraz = _zwloki_w(kontenery)
        nowe = [k for klucz, k in teraz.items() if klucz not in przed]
        if nowe:
            return nowe[-1], set()
        zamkniete = set(przed) - set(teraz)
        if zamkniete:
            return None, zamkniete
    return None, zamkniete


# Pole zwłok pod nogami (12.10): zwłoki bywają pod graczem (cel zginął tam, gdzie potem stanęliśmy) albo o pole
# od zgadniętego. Ctrl+klik na własnym polu (0,0) otwiera zwłoki pod postacią, więc idzie zaraz po polu
# zgadniętym i polach alternatywnych z cavebota, a całe przeszukanie ma budżet MAKS_PROB kliknięć (nie 9-13).
POD_NOGAMI_PIERWSZE = True   # False = dawne zachowanie (3x3 po kolei, bez budżetu, bez pamiętania pustych pól)
MAKS_PROB = 3                # ile różnych pól maks. klikamy przy jednym otwieraniu (przy POD_NOGAMI_PIERWSZE)
DALSZE_PROB = 1              # ile pól o krok dalej maks. (_otworz_dalsze) po wyczerpaniu MAKS_PROB
ALTERNATYWY = []             # ustawia cavebot: inne pola zwłok (x, y) tego samego zabicia, wg prawdopodobieństwa
PROBOWANE = {}               # (x, y) bezwzględne pole -> czas, kiedy było puste (nie klikamy ponownie przy ponowieniu)
NIEDOKONCZONE = False        # ustawia _otworz_z_pamiecia: budżet MAKS_PROB wyczerpany, a zostały nieprzeszukane pola 3x3
                             # (cavebot ponawia wtedy zbierz: pola już puste są pomijane)
PROBOWANE_TTL = 60.0         # s: tyle pamiętamy puste pole (cavebot czyści je przy każdym nowym zabiciu)


def _juz_puste(klucz):
    """Czy pole (klucz = (x, y) bezwzględne albo ("wlasne", x, y)) było niedawno puste
    (pomijamy je przy ponowieniu zbierania)."""
    t = PROBOWANE.get(klucz)
    return t is not None and time.monotonic() - t < PROBOWANE_TTL


def _pola_proby_nogi(dx, dy, gracz, powtorz):
    """Kolejność prób przy POD_NOGAMI_PIERWSZE: zgadnięte pole (dx, dy), pola alternatywne cavebota
    (np. ostatnia widziana pozycja celu, może to pole gracza), własne pole (0, 0), potem sąsiedzi 3x3
    wg bliskości (dx, dy). Zgadnięte pole dwa razy, gdy pierwszy klik mógł paść w trakcie kroku."""
    gx, gy, _ = _xyz(gracz)
    pola = [(dx, dy)]
    for ax, ay in ALTERNATYWY:
        q = (ax - gx, ay - gy)
        if max(abs(q[0]), abs(q[1])) <= 1 and q not in pola:
            pola.append(q)
    if (0, 0) not in pola:
        pola.append((0, 0))
    for q in _pola_proby(dx, dy, False):
        if q not in pola:
            pola.append(q)
    if powtorz:
        pola.insert(0, (dx, dy))
    return pola


def _otworz_z_pamiecia(dx, dy, gracz, przed, powtorz, log):
    """Ctrl+klik kolejnych pól (_pola_proby) aż pamięć pokaże nowy kontener zwłok.
    Zwraca (pole (dx, dy), kontener) albo (None, None). Każdą próbę logujemy (gdy była więcej niż jedna).
    Gdy przed klikiem są już otwarte zwłoki (`przed`), klikamy tylko pole (dx, dy): bez zmiany w pamięci
    zbieramy z okna, które już jest (dawne zachowanie), zamiast klikać po polach z otwartymi zwłokami.
    Przy POD_NOGAMI_PIERWSZE: _pola_proby_nogi, budżet MAKS_PROB różnych pól i pomijanie pól, które
    były puste przy poprzedniej próbie tego zabicia (PROBOWANE)."""
    global NIEDOKONCZONE
    NIEDOKONCZONE = False
    zajete = _pola_ze_stworami(gracz)
    proby = []
    wynik = (None, None)
    nogi = bool(POD_NOGAMI_PIERWSZE)
    gx, gy, _ = _xyz(gracz)
    wlasne = ("wlasne", gx, gy)
    pola = _pola_proby_nogi(dx, dy, gracz, powtorz) if nogi else _pola_proby(dx, dy, powtorz)
    if przed:
        pola = pola[:1]
    klikniec, ostatnie = 0, None
    for sx, sy in pola:
        if (sx, sy) in zajete:
            proby.append(f"({sx},{sy}) stwór")
            continue
        if nogi and not przed:
            if (sx, sy) != ostatnie and ((sx, sy) == (0, 0) and _juz_puste(wlasne)
                                         or (sx, sy) != (0, 0) and _juz_puste((gx + sx, gy + sy))):
                proby.append(f"({sx},{sy}) już puste")
                continue
            if (sx, sy) != ostatnie and MAKS_PROB and klikniec >= MAKS_PROB:
                NIEDOKONCZONE = True
                break
        if (sx, sy) != ostatnie:
            klikniec += 1
        ostatnie = (sx, sy)
        bot.sprawdz_stop()
        ekran.otworz(sx, sy)
        nowy, zamkniete = _czekaj_na_otwarcie(przed, ODCZYTY_OTWARCIA_DALSZE if klikniec > 1 else None)
        if nowy is None and zamkniete:
            # te zwłoki miały już otwarte okno i klik je zamknął: otwieramy jeszcze raz (już na pewno nowe)
            proby.append(f"({sx},{sy}) zamknięte {sorted(zamkniete)}")
            przed = {k: v for k, v in przed.items() if k not in zamkniete}
            bot.sprawdz_stop()
            ekran.otworz(sx, sy)
            nowy, _ = _czekaj_na_otwarcie(przed)
        if nowy is not None:
            proby.append(f"({sx},{sy}) {nowy.get('nazwa')} nr {nowy.get('numer')}")
            wynik = ((sx, sy), nowy)
            break
        proby.append(f"({sx},{sy}) pusto")
        if nogi:
            # własne pole pamiętamy tylko dla pozycji, na której stoimy (po zejściu to zwykłe sąsiednie pole)
            PROBOWANE[wlasne if (sx, sy) == (0, 0) else (gx + sx, gy + sy)] = time.monotonic()
    if wynik[0] is None and not przed and not NIEDOKONCZONE:
        wynik = _otworz_dalsze(dx, dy, gracz, przed, proby, log, maks=(DALSZE_PROB if nogi else None))
    if len(proby) > 1 or (wynik[0] is None and not przed):
        log(f"loot: Ctrl+klik od gracza {_xyz(gracz)[:2]}, zwłoki ({dx},{dy}): {', '.join(proby)}")
    if wynik[0] is not None and wynik[0] != (dx, dy):
        log(f"loot: zwłoki na polu {wynik[0]} zamiast ({dx}, {dy})" + (" (pod nogami)" if wynik[0] == (0, 0) else ""))
    return wynik


def _pola_dalsze(dx, dy):
    """Pola w odległości 2 od gracza, przylegające do przypuszczalnego pola zwłok (dx, dy): uciekający
    potwór zginął o krok dalej, niż ostatnio widzieliśmy. Najbliższe (dx, dy) najpierw."""
    pola = [(x, y) for x in range(-2, 3) for y in range(-2, 3)
            if max(abs(x), abs(y)) == 2 and max(abs(x - dx), abs(y - dy)) <= 1]
    pola.sort(key=lambda q: (abs(q[0] - dx) + abs(q[1] - dy), abs(q[0] - dx) * abs(q[1] - dy)))
    return pola


def _stwory_xy():
    """Pozycje (x, y) żywych stworów (do pomijania pól w _otworz_dalsze)."""
    try:
        return {(s["x"], s["y"]) for s in _zapytaj({"cmd": "stwory"}).get("stwory") or [] if s.get("hp", 100) > 0}
    except Exception:
        return set()


def _otworz_dalsze(dx, dy, gracz, przed, proby, log, maks=None):
    """Gdy pola przy graczu nic nie otworzyły: Ctrl+klik pól o krok dalej (_pola_dalsze). Serwer podprowadza
    postać do zwłok i otwiera je, gdy przy nich stanie, więc pole liczymy od bieżącej pozycji (cel jest
    bezwzględny), a zwrócone pole jest względem pozycji po otwarciu. Zwraca (pole, kontener) albo (None, None)."""
    gx, gy, _ = _xyz(gracz)
    klikniec = 0
    for rx, ry in _pola_dalsze(dx, dy):
        cel = (gx + rx, gy + ry)
        if maks is not None and (klikniec >= maks or _juz_puste(cel)):
            if klikniec >= maks:
                break
            continue
        teraz = _pozycja_gracza() or _xyz(gracz)
        tx, ty = cel[0] - teraz[0], cel[1] - teraz[1]
        if (tx, ty) == (0, 0) or max(abs(tx), abs(ty)) > 5:
            continue
        if cel in _stwory_xy():
            proby.append(f"({rx},{ry}) stwór")
            continue
        bot.sprawdz_stop()
        klikniec += 1
        ekran.otworz(tx, ty)
        nowy, _ = _czekaj_na_otwarcie(przed)
        if nowy is not None:
            po = _pozycja_gracza() or teraz
            proby.append(f"({rx},{ry}) dalej: {nowy.get('nazwa')} nr {nowy.get('numer')}")
            log(f"loot: zwłoki o krok dalej, {(rx, ry)} od pozycji początkowej (zgadywane ({dx}, {dy}))")
            return (cel[0] - po[0], cel[1] - po[1]), nowy
        proby.append(f"({rx},{ry}) dalej pusto")
        if maks is not None:
            PROBOWANE[cel] = time.monotonic()
        po = _pozycja_gracza()
        if po and (po[0], po[1]) == (gx + dx, gy + dy):
            # serwer poprowadził nas na przypuszczalne pole zwłok: na zwłokach nie otworzymy, dalej nie klikamy
            proby.append("stoję na polu zwłok, przerywam (cavebot zejdzie na sąsiednie pole)")
            break
    return None, None


def _plan_z_oknem(mysz, lista, klucz, log):
    """Plan, w którym okno zwłok jest na ekranie (do 4 zrzutów, okno rysuje się z opóźnieniem).
    Przy planie z pamięci okno zwłok musi być oknem kontenera `klucz` (nowo otwartego)."""
    p = None
    for proba in range(4):
        bot.sprawdz_stop()
        _, p = _plan_teraz(mysz, lista, log)
        if p["zwloki"]:
            if klucz is None or p["zrodlo"] != "pamiec" or _klucz(p["zwloki"].kontener) == klucz:
                return p, True
        _pauza(0.3, 0.6)
    return p, False


def _zamknij_zwloki(mysz, p, pole, klucz, log):
    """Zamyka okno zwłok po lootowaniu: X w nagłówku, a gdy go nie widać, a pamięć potwierdza, że
    okno jest otwarte - ponowny Ctrl+klik na polu zwłok (przełącznik). Gdy znamy kontener, sprawdzamy
    w pamięci, że zniknął (inaczej zapychałby prawy panel i następne zwłoki byłyby niewidoczne)."""
    klikniety = False
    if p is not None and p["zwloki"]:
        _pauza(0.2, 0.5)
        klikniety = zamknij_okno(mysz, p["zwloki"])
    if klucz is None:
        return None
    if not klikniety:
        kontenery = _odczyt_kontenerow()
        if kontenery is None or klucz not in _zwloki_w(kontenery):
            return True
        if pole is None:
            log("loot: okno zwłok otwarte, nie znam przycisku X ani pola, zostaje otwarte")
            return False
        bot.sprawdz_stop()
        ekran.otworz(*pole)
    for _ in range(ODCZYTY_ZAMKNIECIA):
        _pauza(0.1, 0.12)
        kontenery = _odczyt_kontenerow()
        if kontenery is not None and klucz not in _zwloki_w(kontenery):
            return True
    log(f"loot: okno zwłok (kontener {klucz[0]}) nadal otwarte według pamięci")
    return False


def _otworz_bez_pamieci(mysz, dx, dy, lista, log):
    """Dawna ścieżka, gdy pamięć nie działa: okno zwłok szukane na zrzutach, potem 3 sąsiednie pola.
    Bez pamięci nie wiemy, czy okno się otworzyło, więc pola (dx, dy) drugi raz nie klikamy (przełącznik)."""
    ekran.otworz(dx, dy)
    _pauza(0.5, 0.9)
    p = None
    for proba in range(4):          # okno zwłok pojawia się z opóźnieniem
        bot.sprawdz_stop()
        _, p = _plan_teraz(mysz, lista, log)
        if p["zwloki"]:
            return p, (dx, dy)
        _pauza(0.3, 0.6)
    # cel mógł zrobić krok tuż przed śmiercią: spróbuj sąsiednich pól przy graczu
    for sx, sy in _sasiednie_pola(dx, dy):
        bot.sprawdz_stop()
        ekran.otworz(sx, sy)
        _pauza(0.6, 0.9)
        _, p = _plan_teraz(mysz, lista, log)
        if p["zwloki"]:
            log(f"loot: zwłoki na polu ({sx}, {sy}) zamiast ({dx}, {dy})")
            return p, (sx, sy)
    return p, None


def zbierz_szczegoly(pozycja_zwlok, gracz_pozycja, lista=DO_ZEBRANIA, log=print):
    """Otwiera zwłoki i przenosi przedmioty z `lista` do plecaka. Zwraca słownik:
    status ("daleko" | "brak_okna" | "okno_niewidoczne" | "brak_plecaka" | "pelny_plecak" | "ok"),
    zebrano (nazwy, po jednej na przeniesienie), ilosci ({nazwa: sztuk}), zostalo, nieznane, ukryte,
    zrodlo (skąd był plan), zjedzono (nazwy zjedzone ze zwłok, JEDZ_ZE_ZWLOK), pole ((dx, dy) zwłok,
    które otworzyliśmy), zamkniete (True/False: okno zwłok zniknęło z pamięci po lootowaniu; None: nie wiadomo).

    "okno_niewidoczne": pamięć potwierdziła otwarcie, ale okna nie ma na ekranie (pełny prawy panel,
    okno ucięte pod dolną krawędzią). Okno zamykamy ponownym Ctrl+klikiem, żeby nie zapychało panelu."""
    wynik = {"status": "ok", "zebrano": [], "ilosci": {}, "zostalo": [], "nieznane": 0, "ukryte": [],
             "zrodlo": None, "zjedzono": [], "pole": None, "zamkniete": None}
    if not przylega(pozycja_zwlok, gracz_pozycja):
        wynik["status"] = "daleko"
        return wynik
    gracz, stoi = _czekaj_na_postoj(gracz_pozycja)
    if stoi is not None and tuple(gracz[:2]) != tuple(_xyz(gracz_pozycja)[:2]):
        log(f"loot: postać przeszła z {_xyz(gracz_pozycja)[:2]} na {gracz[:2]}, liczę pole zwłok od nowa")
        if not przylega(pozycja_zwlok, gracz):
            wynik["status"] = "daleko"
            return wynik
    if stoi is False:
        log("loot: postać nie stanęła, klikam mimo to")
    x1, y1, _ = _xyz(pozycja_zwlok)
    x2, y2, _ = _xyz(gracz)
    dx, dy = x1 - x2, y1 - y2
    przed = _odczyt_kontenerow()
    klucz = None
    with ekran.Mysz() as mysz:
        if przed is None:
            p, pole = _otworz_bez_pamieci(mysz, dx, dy, lista, log)
            if pole is None:
                wynik["status"] = "brak_okna"
                return wynik
        else:
            przed = _zwloki_w(przed)
            if przed:
                log(f"loot: przed otwarciem były już otwarte zwłoki {sorted(przed)}")
            pole, kontener = _otworz_z_pamiecia(dx, dy, gracz, przed, stoi is not True, log)
            if pole is None and not przed:
                wynik["status"] = "brak_okna"
                return wynik
            if pole is None:
                # nic nowego się nie otworzyło, ale zostały okna zwłok sprzed klików: zbieramy z nich
                klucz = None
            else:
                klucz = _klucz(kontener)
            wynik["pole"] = pole
            p, widoczne = _plan_z_oknem(mysz, lista, klucz, log)
            if not widoczne:
                if klucz is None:
                    wynik["status"] = "brak_okna"
                    return wynik
                log(f"loot: okno_niewidoczne: zwłoki {kontener.get('nazwa')!r} (kontener {klucz[0]}) otwarte "
                    "w pamięci, ale nie ma ich okna na ekranie (pełny prawy panel?). Zamykam je ponownym "
                    "Ctrl+klikiem. Zrób miejsce: zminimalizuj Skills/Battle w prawym panelu.")
                wynik["status"] = "okno_niewidoczne"
                wynik["zamkniete"] = _zamknij_zwloki(mysz, None, pole, klucz, log)
                return wynik
            if klucz is None and p["zrodlo"] == "pamiec":
                klucz = _klucz(p["zwloki"].kontener)
        wynik["pole"] = pole
        wynik["zrodlo"] = p["zrodlo"]
        najedzony = not JEDZ_ZE_ZWLOK
        zjedzen = 0
        proba_plecaka = False
        for _ in range(MAKS_RUCHOW + MAKS_ZJEDZENIA):
            bot.sprawdz_stop()
            if PRZERWIJ is not None and PRZERWIJ():
                log("loot: żywy potwór obok, przerywam zbieranie")
                wynik["status"] = "przerwany"
                break
            if p["jedzenie"] and not najedzony and zjedzen < MAKS_ZJEDZENIA:
                zjedzen += 1
                p, zjedzono = _zjedz_ze_zwlok(mysz, p, lista, wynik, log)
                najedzony = not zjedzono
                continue                  # zostało jedzenie: jemy dalej; najedzony: do plecaka
            if not p["przedmiot"] or len(wynik["zebrano"]) >= MAKS_RUCHOW:
                break
            if not p["plecak"]:
                if not proba_plecaka and otworz_plecak(mysz, log):
                    proba_plecaka = True
                    _obraz, p = _plan_teraz(mysz, lista, log)
                    continue
                wynik["status"] = "brak_plecaka"
                break
            if not p["cel"]:
                wynik["status"] = "pelny_plecak"
                wynik["powod"] = _powod_braku_miejsca(p, log, "pełny plecak")
                break
            slot, nazwa = p["przedmiot"]
            przed = _zrzut(mysz)
            mysz.przeciagnij(*slot.srodek, *p["cel"].srodek, drganie=4)
            _pauza(0.25, 0.5)
            _okno_ilosci_ok(mysz, nazwa, log, przed)
            obraz, nowy = _plan_teraz(mysz, lista, log)
            ile = _zebrano_z_pamieci(p, nowy)
            if ile is not None and ile > 0:
                _sprawdz_plecak(p, nowy, ile, log)
            if ile is not None:
                if ile <= 0:
                    log(f"loot: {nazwa} nie przeszedł (slot {slot.srodek}, pamięć bez zmian), przerywam")
                    _powod_braku_miejsca(p, log, "nie przeszedł")
                    p = nowy
                    break
            elif nowy["przedmiot"] and nowy["przedmiot"][0].srodek == slot.srodek and nowy["przedmiot"][1] == nazwa:
                log(f"loot: {nazwa} nie przeszedł (slot {slot.srodek}), przerywam")
                _powod_braku_miejsca(p, log, "nie przeszedł")
                p = nowy
                break
            wynik["zebrano"].append(nazwa)
            if ile is not None:
                wynik["ilosci"][nazwa] = wynik["ilosci"].get(nazwa, 0) + ile
                LACZNIE[nazwa] = LACZNIE.get(nazwa, 0) + ile
                log(f"loot: zebrano {nazwa} +{ile}")
            else:
                log(f"loot: zebrano {nazwa} (ilość nieznana, plan z obrazka)")
            p = nowy
        if p["plecak"] and wynik["status"] == "ok":
            p = _scal_stosy(mysz, p, lista, log)
        wynik["zostalo"] = p["zostalo"]
        wynik["nieznane"] = p["nieznane"]
        wynik["ukryte"] = p["ukryte"]
        _log_cenne("loot", p["zostalo"], log)
        if p["ukryte"]:
            log(f"loot: pod suwakiem okna zostało {', '.join(p['ukryte'])}")
        if wynik["ilosci"]:
            log(f"loot: łup {_opis_ilosci(wynik['ilosci'])} (razem: {_opis_ilosci(LACZNIE)})")
        _sprzatnij_okno_ilosci(mysz, log)
        wynik["zamkniete"] = _zamknij_zwloki(mysz, p, pole, klucz, log)
    return wynik


# --- otwieranie i rozciąganie plecaka (18.10) ---------------------------------

SLOT_PLECAKA_EKWIPUNEK = (1089, 143)  # plecak w slocie ekwipunku, okno gry 1175x910 (18.10): Ctrl+lewy klik = otwórz
ROZCIAGNIECIE_DO_RZEDOW = 5           # okno plecaka rozciągamy do tylu rzędów slotów (krok rzędu 37 px)
ODSTEP_OTWARCIA_S = 20.0              # nie próbujemy otwierać plecaka częściej niż co tyle sekund
_ostatnia_proba_otwarcia = [None]


def plecak_otwarty(obraz):
    """True, gdy w panelu jest okno plecaka (tytuł ze wzorców z PLECAKI)."""
    return any((_nazwa_tytulu(obraz, o) or "").casefold() in PLECAKI for o in znajdz_okna(obraz))


def dolna_krawedz(okno):
    """Y dolnej ramki okna: dolny rząd slotów plus 10 px (kalibracja 18.10)."""
    return max(s.y + s.bok for s in okno.sloty) + 10


def _okno_plecaka(obraz):
    for o in znajdz_okna(obraz):
        if (_nazwa_tytulu(obraz, o) or "").casefold() in PLECAKI and o.sloty:
            return o
    return None


def rozciagnij_plecak(mysz, obraz, log=print):
    """Przeciąga dolną krawędź okna plecaka w dół, aż ma ROZCIAGNIECIE_DO_RZEDOW rzędów slotów.
    Ciągnie za linię ramki (drganie 0): róg z uchwytem w lewym dolnym rogu nie reagował (18.10)."""
    okno = _okno_plecaka(obraz)
    if okno is None:
        return False
    rzedy = len({s.y for s in okno.sloty})
    brak = ROZCIAGNIECIE_DO_RZEDOW - rzedy
    if brak <= 0:
        return False
    x = (okno.lewo + okno.prawo) // 2
    y = dolna_krawedz(okno)
    bot.sprawdz_stop()
    mysz.przeciagnij(x, y, x, y + brak * 37, drganie=0)
    _pauza(0.4, 0.6)
    log(f"plecak: okno rozciągnięte z {rzedy} do {ROZCIAGNIECIE_DO_RZEDOW} rzędów")
    return True


def otworz_plecak(mysz, log=print):
    """Gdy żadne okno plecaka nie jest otwarte: Ctrl+lewy klik na plecaku w ekwipunku, potem rozciągnięcie.
    True tylko wtedy, gdy klik faktycznie otworzył plecak (zweryfikowane zrzutem)."""
    if plecak_otwarty(_zrzut(mysz)):
        return False
    teraz = time.monotonic()
    ostatnia = _ostatnia_proba_otwarcia[0]
    if ostatnia is not None and teraz - ostatnia < ODSTEP_OTWARCIA_S:
        return False
    _ostatnia_proba_otwarcia[0] = teraz
    bot.sprawdz_stop()
    mysz.lewy(*SLOT_PLECAKA_EKWIPUNEK, modyfikator="Control_L", drganie=2)
    _pauza(0.9, 1.3)
    obraz = _zrzut(mysz)
    otwarto = plecak_otwarty(obraz)
    log(f"plecak: Ctrl+klik na ekwipunku, okno plecaka {'otwarte' if otwarto else 'NIE pojawiło się'}")
    if otwarto:
        rozciagnij_plecak(mysz, obraz, log)
    return otwarto


def zbierz(pozycja_zwlok, gracz_pozycja, lista=DO_ZEBRANIA):
    """Zbiera łup ze zwłok. Zwraca "daleko" (cavebot ma podejść), "brak_okna", "brak_plecaka",
    "pelny_plecak" albo "ok"."""
    return zbierz_szczegoly(pozycja_zwlok, gracz_pozycja, lista)["status"]


# --- loot w trakcie walki: atomowe kroki ---------------------------------------------
# Bez wątków (jedno wejście XTEST): cavebot woła krok_w_walce() najwyżej raz na obieg tick(), w przerwie
# między kontrolami ataku (atak trwa sam po ustawieniu celu). Każde wywołanie to JEDEN krótki krok i powrót:
#   None -> "czekaj"  Ctrl+klik na zwłokach (jedno kliknięcie, bez czekania na okno)
#   "czekaj"          odczyt pamięci: czy pojawił się nowy kontener zwłok (bez klików)
#   "plan"            zrzut + plan: okno zwłok widoczne i zgodne z kontenerem (bez klików)
#   "przenies"        jedno przeciągnięcie przedmiotu do plecaka (+ ewentualne "Ok" w oknie ilości)
#   "weryfikuj"       zrzut + sprawdzenie w pamięci, czy przedmiot przeszedł (bez klików)
#   "zamknij"         zamknięcie okna zwłok (X albo przełączający Ctrl+klik)
# Stan między krokami w słowniku `stan` (pusty dict = start). Nigdy Alt+klik; Ctrl+klik tylko w pole zwłok
# przy graczu, na którym nie stoi żywy stwór.

W_WALCE_MAKS_RUCHOW = 6        # ile przedmiotów maks. z jednych zwłok w trakcie walki (resztę zbierze loot po walce)
W_WALCE_OTWARCIE_S = 1.5       # s od Ctrl+kliku, po których brak nowego kontenera = "brak_okna"
W_WALCE_OBCE_PROB = 2          # tyle prób zamknięcia otwartego już okna zwłok przed Ctrl+klikiem (potem "obce_okno")
W_WALCE_PROB_PLANU = 4         # tyle kroków "plan" (okno rysuje się z opóźnieniem), potem okno_niewidoczne
W_WALCE_MAKS_ZJEDZENIA = 3     # ile razy maks. jemy ze zwłok w trakcie walki (kolejne zwłoki: znów od zera)


def krok_w_walce(stan, pozycja_zwlok, gracz_pozycja, lista=DO_ZEBRANIA, log=print, zegar=time.monotonic):
    """Jeden atomowy krok lootu w walce. Zwraca (status, opis):
    "kontynuuj" (opis = nazwa wykonanego kroku z inputem/zrzutem albo None, gdy tylko czekamy),
    "gotowe" (zwłoki obsłużone, okno zamknięte; opis "ok" albo powód wcześniejszego końca) albo
    "przerwane" (opis = powód: daleko, na_zwlokach, brak_pamieci, obce_okno, stwor_na_zwlokach, brak_okna;
    nic nie zostało otwarte przez ten krok, a gdy okno już było otwarte, jest w stan["klucz"])."""
    bot.sprawdz_stop()
    faza = stan.get("faza")
    if faza is None:
        if not przylega(pozycja_zwlok, gracz_pozycja):
            return "przerwane", "daleko"
        x1, y1, _ = _xyz(pozycja_zwlok)
        x2, y2, _ = _xyz(gracz_pozycja)
        dx, dy = x1 - x2, y1 - y2
        if (dx, dy) == (0, 0):
            return "przerwane", "na_zwlokach"
        kontenery = _odczyt_kontenerow()
        if kontenery is None:
            return "przerwane", "brak_pamieci"
        przed = _zwloki_w(kontenery)
        if przed:
            # Ctrl+klik zamknąłby/pomieszał okno zwłok, które już jest otwarte (zwykle nasze, zostawione przez
            # pilne przerwanie): zamykamy je X-em (świeży plan z ekranu) i ponawiamy w następnym kroku
            proby = stan.get("obce_proby", 0)
            if proby >= W_WALCE_OBCE_PROB:
                return "przerwane", "obce_okno"
            stan["obce_proby"] = proby + 1
            bot.sprawdz_stop()
            with ekran.Mysz() as mysz:
                if not _zamknij_okno_z_planu(mysz, lista, log):
                    return "przerwane", "obce_okno"
            return "kontynuuj", "zamkniecie_obcego"
        if (dx, dy) in _pola_ze_stworami(gracz_pozycja):
            return "przerwane", "stwor_na_zwlokach"
        bot.sprawdz_stop()
        ekran.otworz(dx, dy)
        stan.update(faza="czekaj", przed=przed, pole=(dx, dy), t_klik=zegar(), klucz=None, p=None,
                    ruchy=0, proby=0, ilosci={}, koniec_powod=None, zamkniete=None, zjedzen=0, najedzony=False)
        return "kontynuuj", "otwarcie"
    if faza == "czekaj":
        kontenery = _odczyt_kontenerow()
        if kontenery is not None:
            nowe = [k for klucz, k in _zwloki_w(kontenery).items() if klucz not in stan["przed"]]
            if nowe:
                stan.update(klucz=_klucz(nowe[-1]), faza="plan", proby=0)
                return "kontynuuj", None
        if zegar() - stan["t_klik"] > W_WALCE_OTWARCIE_S:
            return "przerwane", "brak_okna"
        return "kontynuuj", None
    with ekran.Mysz() as mysz:
        if faza == "plan":
            _, p = _plan_teraz(mysz, lista, log)
            klucz = stan["klucz"]
            if p["zwloki"] and (p["zrodlo"] != "pamiec" or _klucz(p["zwloki"].kontener) == klucz):
                stan.update(p=p, faza="przenies")
                return "kontynuuj", "plan"
            stan["proby"] += 1
            if stan["proby"] >= W_WALCE_PROB_PLANU:
                stan.update(faza="zamknij", koniec_powod="okno_niewidoczne")
                log("loot w walce: okno zwłok otwarte w pamięci, ale niewidoczne na ekranie, zamykam")
            return "kontynuuj", None
        if faza == "przenies":
            p = stan["p"]
            if (JEDZ_ZE_ZWLOK and p.get("jedzenie") and not stan.get("najedzony")
                    and stan.get("zjedzen", 0) < W_WALCE_MAKS_ZJEDZENIA):
                # jedzenie w zwłokach (jak w zbierz_szczegoly): Use na nim zanim ruszymy resztę; nie ubyło = najedzony
                slot, nazwa, _ = p["jedzenie"]
                bot.sprawdz_stop()
                mysz.lewy(*slot.srodek, modyfikator="Control_L", drganie=3)
                _pauza(0.15, 0.3)
                stan.update(faza="weryfikuj_jedzenie", zjedzen=stan.get("zjedzen", 0) + 1)
                return "kontynuuj", f"jedz {nazwa}"
            if not p["przedmiot"] or stan["ruchy"] >= W_WALCE_MAKS_RUCHOW:
                stan.update(faza="zamknij", koniec_powod=None)
            elif not p["plecak"]:
                stan.update(faza="zamknij", koniec_powod="brak_plecaka")
            elif not p["cel"]:
                _powod_braku_miejsca(p, log, "pełny plecak w walce")
                stan.update(faza="zamknij", koniec_powod="pelny_plecak")
            else:
                slot, nazwa = p["przedmiot"]
                bot.sprawdz_stop()
                przed = _zrzut(mysz)
                mysz.przeciagnij(*slot.srodek, *p["cel"].srodek, drganie=4)
                _pauza(0.15, 0.3)
                _okno_ilosci_ok(mysz, nazwa, log, przed)
                stan["faza"] = "weryfikuj"
                return "kontynuuj", f"przenies {nazwa}"
        if faza == "weryfikuj_jedzenie":
            p = stan["p"]
            _, nazwa, ident = p["jedzenie"]
            _, nowy = _plan_teraz(mysz, lista, log)
            ile = _zebrano_z_pamieci(p, nowy, ident)
            stan["p"] = nowy
            if ile is not None and ile > 0:
                log(f"loot w walce: zjedzono ze zwłok: {nazwa}")
            else:
                stan["najedzony"] = True
                log(f"loot w walce: {nazwa} ze zwłok nie ubyło, najedzony" + ("" if ile is not None else " (pamięć nie wie)"))
            stan["faza"] = "przenies"
            return "kontynuuj", "weryfikacja_jedzenia"
        if faza == "weryfikuj":
            p = stan["p"]
            slot, nazwa = p["przedmiot"]
            _, nowy = _plan_teraz(mysz, lista, log)
            ile = _zebrano_z_pamieci(p, nowy)
            if ile is not None and ile > 0:
                _sprawdz_plecak(p, nowy, ile, log)
            nie_przeszedl = (ile is not None and ile <= 0) or (
                ile is None and nowy["przedmiot"] and nowy["przedmiot"][0].srodek == slot.srodek
                and nowy["przedmiot"][1] == nazwa)
            stan["p"] = nowy
            if nie_przeszedl:
                log(f"loot w walce: {nazwa} nie przeszedł (slot {slot.srodek}), kończę")
                _powod_braku_miejsca(p, log, "nie przeszedł w walce")
                stan.update(faza="zamknij", koniec_powod="nie_przeszedl")
                return "kontynuuj", None
            stan["ruchy"] += 1
            if ile is not None:
                stan["ilosci"][nazwa] = stan["ilosci"].get(nazwa, 0) + ile
                LACZNIE[nazwa] = LACZNIE.get(nazwa, 0) + ile
                log(f"loot w walce: zebrano {nazwa} +{ile}")
            else:
                log(f"loot w walce: zebrano {nazwa} (ilość nieznana, plan z obrazka)")
            stan["faza"] = "przenies"
            return "kontynuuj", "weryfikacja"
        if stan["faza"] == "zamknij":      # także po przejściu z "przenies" w tym samym wywołaniu
            _sprzatnij_okno_ilosci(mysz, log)
            stan["zamkniete"] = _zamknij_zwloki(mysz, stan.get("p"), stan.get("pole"), stan.get("klucz"), log)
            stan["faza"] = "koniec"
            _log_cenne("loot w walce", (stan.get("p") or {}).get("zostalo") or [], log)
            if stan["ilosci"]:
                log(f"loot w walce: łup {_opis_ilosci(stan['ilosci'])} (razem: {_opis_ilosci(LACZNIE)})")
            log("loot w walce: koniec")        # znacznik dla dziennika ekonomii (zamyka rekord `lup`)
            return "gotowe", stan.get("koniec_powod") or "ok"
    return "przerwane", "stan"


def _zamknij_okno_z_planu(mysz, lista, log):
    """Klik w X okna zwłok widocznego na ekranie (świeży plan, pozycja z bieżącego zrzutu). True: kliknięto."""
    try:
        _, p = _plan_teraz(mysz, lista, log)
    except bot.Zatrzymano:
        raise
    except Exception as e:
        log(f"loot w walce: plan okna do zamknięcia nie wyszedł: {e!r}")
        return False
    okno = p.get("zwloki") if p else None
    kont = getattr(okno, "kontener", None)
    if okno is not None and (getattr(okno, "rola", None) == "runy" or (kont is not None and czy_runy(kont))):
        return False                       # pojemnika na runy nigdy nie zamykamy
    return bool(okno is not None and zamknij_okno(mysz, okno))


def zamknij_w_walce(stan, log=print, swiezo=False, lista=DO_ZEBRANIA):
    """Zamyka okno zwłok otwarte przez krok_w_walce (przerwanie lootu w walce).
    True: okno zniknęło z pamięci (albo nie było otwarte); False: nie udało się; None: klik poszedł, ale okna
    jeszcze nie widać w pamięci (faza "czekaj") - wywołujący ponawia później.
    swiezo=True (zamykanie zaległe, postać mogła się ruszyć): okno szukane na świeżym zrzucie, bez Ctrl+kliku
    w pole zapamiętane względem dawnej pozycji."""
    faza = stan.get("faza")
    if faza in (None, "koniec"):
        return True
    if faza == "czekaj" and not stan.get("klucz"):
        kontenery = _odczyt_kontenerow()
        if kontenery is None:
            return None
        nowe = [k for klucz, k in _zwloki_w(kontenery).items() if klucz not in stan.get("przed", {})]
        if not nowe:
            return None            # okno jeszcze się nie narysowało (albo klik nie zadziałał)
        stan["klucz"] = _klucz(nowe[-1])
    klucz = stan.get("klucz")
    if not klucz:
        return True
    if swiezo:
        kontenery = _odczyt_kontenerow()
        if kontenery is not None and klucz not in _zwloki_w(kontenery):
            stan["faza"] = "koniec"
            return True
        with ekran.Mysz() as mysz:
            if not _zamknij_okno_z_planu(mysz, lista, log):
                return False
        for _ in range(ODCZYTY_ZAMKNIECIA):
            _pauza(0.1, 0.12)
            kontenery = _odczyt_kontenerow()
            if kontenery is not None and klucz not in _zwloki_w(kontenery):
                stan["faza"] = "koniec"
                return True
        return False
    with ekran.Mysz() as mysz:
        zamkniete = _zamknij_zwloki(mysz, stan.get("p"), stan.get("pole"), klucz, log)
    stan["faza"] = "koniec"
    return bool(zamkniete)


# --- narzędzia offline --------------------------------------------------------

def _obraz(plik=None):
    return Image.open(plik).convert("RGB") if plik else ekran.zrzut()


def _okno_ze_slotem(obraz, x, y):
    for o in znajdz_okna(obraz):
        for s in o.sloty:
            if s.x <= x < s.x + s.bok and s.y <= y < s.y + s.bok:
                return o, s
    raise SystemExit(f"nie ma slotu kontenera pod ({x}, {y})")


def podglad(obraz, plik):
    kopia = obraz.copy()
    r = ImageDraw.Draw(kopia)
    for o in znajdz_okna(obraz):
        kolor = (0, 255, 0) if o.rola == "plecak" else (255, 0, 255)
        if o.gora is not None:
            r.rectangle([o.lewo, o.gora, o.prawo, o.gora + 15], outline=kolor)
            cx, cy = o.przycisk_zamkniecia
            r.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], outline=(255, 255, 0))
        for slot, nazwa, blad in zawartosc(obraz, o):
            r.rectangle([slot.x, slot.y, slot.x + slot.bok - 1, slot.y + slot.bok - 1], outline=kolor)
            etykieta = "." if nazwa is None else nazwa[:6]
            r.text((slot.x + 2, slot.y + 2), etykieta, fill=(255, 255, 255))
    kopia.save(plik)


def komenda_sloty(plik=None):
    obraz = _obraz(plik)
    okna = znajdz_okna(obraz)
    print(f"ekran {obraz.size[0]}x{obraz.size[1]}, okien kontenerów: {len(okna)}")
    for o in okna:
        print(" ", o)
    wyjscie = SCRATCH / "podglad_slotow.png"
    podglad(obraz, wyjscie)
    print("podgląd:", wyjscie)


def komenda_rozpoznaj(plik=None):
    obraz = _obraz(plik)
    for o in znajdz_okna(obraz):
        print(o)
        print("   ", [(n if n else ".") + (f"({b:.0f})" if n else "") for _, n, b in zawartosc(obraz, o)])
    p = plan(obraz)
    print("plan:", {k: p[k] for k in ("zrodlo", "pamiec", "przedmiot", "przedmiot_id", "cel", "nieznane",
                                      "zostalo", "ukryte")})
    for o in p["okna"]:
        if o.kontener:
            print(f"  {o.rola} = kontener {o.kontener['numer']} {o.kontener['nazwa']!r}:",
                  [(q["slot"], nazwa_id(q["id"]), q.get("ilosc")) for q in o.kontener["przedmioty"]])


def komenda_ikona(nazwa, x, y, plik=None):
    obraz = _obraz(plik)
    _, slot = _okno_ze_slotem(obraz, int(x), int(y))
    IKONY.mkdir(exist_ok=True)
    cel = IKONY / f"{nazwa}.png"
    _ikona_slotu(obraz, slot).save(cel)
    print("zapisano", cel, f"(slot {slot.x},{slot.y})")


def komenda_tytul(nazwa, x, y, plik=None):
    obraz = _obraz(plik)
    okno, _ = _okno_ze_slotem(obraz, int(x), int(y))
    TYTULY.mkdir(parents=True, exist_ok=True)
    cel = TYTULY / f"{nazwa}.png"
    _wycinek_tytulu(obraz, okno).save(cel)
    print("zapisano", cel)


def _test_obrazu(sprawdz):

    oczekiwane = ["gold coin", "torch", "cheese", "meat", None, None, None, None]
    for nazwa, sloty_x in (("z6.png", [563, 600, 637, 674]), ("z3.png", [1365, 1402, 1439, 1476])):
        obraz = Image.open(SCRATCH / nazwa).convert("RGB")
        okna = znajdz_okna(obraz)
        sprawdz(f"{nazwa}: jedno okno kontenera, rola plecak", len(okna) == 1 and okna[0].rola == "plecak")
        if not okna:
            continue
        o = okna[0]
        sprawdz(f"{nazwa}: sloty w kolumnach {sloty_x}", sorted({s.x for s in o.sloty}) == sloty_x)
        nazwy = [n for _, n, _ in zawartosc(obraz, o)]
        sprawdz(f"{nazwa}: zawartość {nazwy}", len(nazwy) == 8 and nazwy == oczekiwane)
    # świeży zrzut (65 monet, bez sera): inny licznik, ten sam sprite
    plik = SCRATCH / "fresh.png"
    if plik.exists():
        obraz = Image.open(plik).convert("RGB")
        o = znajdz_okna(obraz)[0]
        nazwy = [n for _, n, _ in zawartosc(obraz, o)]
        sprawdz(f"fresh.png: zawartość {nazwy}", nazwy[:4] == ["gold coin", "torch", "meat", None])
    # ekwipunek nie jest kontenerem; zrzuty bez okna kontenera
    sprawdz("z2.png (menu kontekstowe nad mapą): tylko plecak", [o.rola for o in znajdz_okna(Image.open(SCRATCH / "z2.png").convert("RGB"))] == ["plecak"])
    # atrapa zwłok: kopia okna Bag poniżej, z wymazanym tytułem i podmienionymi slotami
    obraz = Image.open(SCRATCH / "z6.png").convert("RGB")
    bag = obraz.crop((554, 357, 731, 441))
    atrapa = obraz.copy()
    atrapa.paste(bag, (554, 460))
    r = ImageDraw.Draw(atrapa)
    r.rectangle([554 + 19, 460 + 2, 554 + 19 + 70, 460 + 14], fill=(24, 25, 22))   # tytuł "Dead rat" nieznany
    # zwłoki: slot 1 = ser, slot 2 = nieznany (pochodnia usunięta), wolne reszta
    atrapa.paste(Image.new("RGB", (32, 32), (24, 25, 22)), (600 + 1, 478 + 1 - 3 + 3))
    p = plan(atrapa)
    sprawdz("atrapa: plecak i zwłoki wykryte jako dwa okna", len(p["okna"]) == 2 and p["plecak"] is not None and p["zwloki"] is not None)
    if p["zwloki"] and p["plecak"]:
        sprawdz(f"atrapa: do zebrania gold coin ze slotu zwłok {p['przedmiot'] and p['przedmiot'][0]}",
                p["przedmiot"] and p["przedmiot"][1] == "gold coin" and p["przedmiot"][0].y > 460)
        sprawdz(f"atrapa: cel = pierwszy wolny slot plecaka {p['cel']}", p["cel"] is not None and p["cel"].y < 440 and p["cel"].x == 563)
        sprawdz(f"atrapa: przycisk zamknięcia zwłok {p['zwloki'].przycisk_zamkniecia}",
                p["zwloki"].przycisk_zamkniecia == (730 - 10 + 0, 460 + 8 + 0) or
                abs(p["zwloki"].przycisk_zamkniecia[0] - 719) <= 2)
    atrapa.save(SCRATCH / "atrapa_zwloki.png")
    podglad(atrapa, SCRATCH / "podglad_atrapy.png")
    # przyleganie
    sprawdz("przyleganie: obok", przylega((10, 10, 7), (11, 11, 7)))
    sprawdz("przyleganie: daleko", not przylega((10, 10, 7), (12, 10, 7)))
    sprawdz("przyleganie: inne piętro", not przylega((10, 10, 6), (10, 10, 7)))



def kont(numer, nazwa, ident, pojemnosc, *przedmioty):
    """Atrapa kontenera jak z komendy "kontenery": przedmioty jako (ID, ilość) od slotu 0."""
    return {"numer": numer, "nazwa": nazwa, "id": ident, "pojemnosc": pojemnosc,
            "przedmioty": [{"slot": i, "id": d, "ilosc": n} for i, (d, n) in enumerate(przedmioty)
                           if d is not None]}


def _test_pamieci(sprawdz):
    global _zapytaj
    # zwloki.png (żywy zrzut): Bag [gold 85, rope], Dead rat [gold, cheese, -, -] (pojemność 5, 4 widoczne)
    obraz = Image.open(SCRATCH / "zwloki.png").convert("RGB")
    zwloki = kont(0, "dead rat", 3994, 5, (3031, 3), (3607, 1))
    bag = kont(1, "bag", 2853, 8, (3031, 85), (3003, 1))

    def z_pamiecia(kontenery, lista=("gold coin", "cheese", "meat", "ham")):
        global _zapytaj
        _zapytaj = (lambda z: {"kontenery": kontenery}) if not isinstance(kontenery, Exception) \
            else (lambda z: (_ for _ in ()).throw(kontenery))
        return plan(obraz, lista)

    p = z_pamiecia([zwloki, bag])
    okna = p["okna"]
    sprawdz(f"pamięć: plan z pamięci ({p['zrodlo']}, {p['pamiec']})", p["zrodlo"] == "pamiec")
    sprawdz("pamięć: zwłoki = dolne okno, plecak = górne",
            p["zwloki"] is okna[1] and p["plecak"] is okna[0] and okna[1].kontener["numer"] == 0)
    sprawdz(f"pamięć: zbieram gold coin x3 ze slotu 0 zwłok {p['przedmiot']} {p['przedmiot_id']}",
            p["przedmiot"] == (okna[1].sloty[0], "gold coin") and p["przedmiot_id"] == (3031, 3))
    sprawdz(f"pamięć: gold na istniejący stos (slot 0 plecaka) {p['cel']}", p["cel"] is okna[0].sloty[0])
    # kolejność kontenerów w odpowiedzi nie ma znaczenia
    p = z_pamiecia([bag, zwloki])
    sprawdz("pamięć: odwrotna kolejność kontenerów, to samo dopasowanie",
            p["zrodlo"] == "pamiec" and p["zwloki"].kontener["numer"] == 0 and p["plecak"].kontener["numer"] == 1)
    # pełny stos: gold idzie na wolny slot
    p = z_pamiecia([zwloki, kont(1, "bag", 2853, 8, (3031, 100), (3003, 1))])
    sprawdz(f"pamięć: stos 100 pełny, gold na pierwszy wolny slot (2) {p['cel']}", p["cel"] is p["okna"][0].sloty[2])
    # 98 + 3 > 100: inny stos z miejscem ma pierwszeństwo, nawet dalej w plecaku
    p = z_pamiecia([zwloki, kont(1, "bag", 2853, 8, (3031, 98), (3031, 40))])
    sprawdz(f"pamięć: stos, na który zmieści się całość (slot 1) {p['cel']}", p["cel"] is p["okna"][0].sloty[1])
    # pełny plecak (wszystkie 8 slotów zajęte w pamięci) nie zgadza się z ekranem: fallback
    p = z_pamiecia([zwloki, kont(1, "bag", 2853, 8, *[(3003, 1)] * 8)])
    sprawdz(f"pamięć: niezgodna z ekranem -> obrazek ({p['pamiec']})",
            p["zrodlo"] == "obraz" and p["pamiec"].startswith("niezgodne") and p["przedmiot"][1] == "gold coin")
    # lista po ID: tylko ser
    p = z_pamiecia([zwloki, bag], lista=(3607,))
    sprawdz(f"pamięć: lista po ID (3607) -> cheese ze slotu 1, cel slot 2 {p['przedmiot']} {p['cel']}",
            p["przedmiot"] == (p["okna"][1].sloty[1], "cheese") and p["cel"] is p["okna"][0].sloty[2]
            and p["zostalo"] == ["gold coin"])
    # przedmiot do zebrania pod suwakiem (slot 4 przy 4 widocznych)
    ukryty = kont(0, "dead rat", 3994, 5, (3031, 3), (3577, 1))
    ukryty["przedmioty"].append({"slot": 4, "id": 3607, "ilosc": 1})
    ukryty["przedmioty"][1]["id"] = 3577
    p = z_pamiecia([ukryty, bag], lista=("cheese",))
    sprawdz(f"pamięć: ser pod suwakiem -> ukryte {p['ukryte']}, brak ruchu",
            p["zrodlo"] == "pamiec" and p["przedmiot"] is None and p["ukryte"] == ["cheese"])
    # nieznane ID: obrazek rozpoznaje przedmiot z listy bez ID -> uczymy się ID
    stare = dict(NAZWA_ID), dict(ID_NAZWA)
    del NAZWA_ID["cheese"], ID_NAZWA[3607]
    try:
        p = z_pamiecia([zwloki, bag], lista=("cheese",))
        sprawdz(f"pamięć: nowe ID z obrazka {p['nauczone']}", p["nauczone"] == [(3607, "cheese")]
                and p["przedmiot"] == (p["okna"][1].sloty[1], "cheese"))
    finally:
        NAZWA_ID.clear(); NAZWA_ID.update(stare[0]); ID_NAZWA.clear(); ID_NAZWA.update(stare[1])
    p = z_pamiecia([kont(0, "dead rat", 3994, 5, (3031, 3), (9999, 1)), bag], lista=("gold coin",))
    sprawdz(f"pamięć: nieznane ID 9999 liczone jako nieznane ({p['nieznane']})", p["nieznane"] == 1)
    # awarie odczytu -> obrazek, a plan obrazkowy taki jak dawniej
    for opis, kontenery in (("wyjątek gniazda", ConnectionRefusedError("brak gniazda")), ("pusta lista", []),
                            ("mniej kontenerów niż okien", [bag]),
                            ("za mała pojemność", [kont(0, "dead rat", 3994, 3, (3031, 3), (3607, 1)), bag])):
        p = z_pamiecia(kontenery)
        sprawdz(f"fallback ({opis}): {p['pamiec']}", p["zrodlo"] == "obraz" and p["pamiec"]
                and p["przedmiot"] and p["przedmiot"][1] == "gold coin" and p["cel"] is not None)
    _zapytaj = lambda z: {"kontenery": [], "blad": "SyntaxError: x"}
    p = plan(obraz)
    sprawdz(f"fallback (błąd w rdzeniu): {p['pamiec']}", p["zrodlo"] == "obraz" and "SyntaxError" in p["pamiec"])
    # stosy po ID (nie tylko gold): ser na stos sera w plecaku
    p = z_pamiecia([zwloki, kont(1, "bag", 2853, 8, (3607, 2), (3003, 1))], lista=("cheese",))
    sprawdz(f"stosy: ser na stos sera (slot 0, 2 szt.) {p['cel']} {p['cel_stos']}",
            p["cel"] is p["okna"][0].sloty[0] and p["cel_stos"] == 2)
    p = z_pamiecia([kont(0, "dead rat", 3994, 5, (3003, 1), (3607, 1)), bag], lista=(3003,))
    sprawdz(f"stosy: rope (niestosowe) na wolny slot 2, nie na rope {p['cel']}",
            p["cel"] is p["okna"][0].sloty[2] and p["cel_stos"] is None)
    p = z_pamiecia([kont(0, "dead rat", 3994, 5, (3035, 5), (3607, 1)), kont(1, "bag", 2853, 8, (3035, 10), (3003, 1))],
                   lista=(3035,))
    sprawdz(f"stosy: nieznane ID 3035 też na swój stos {p['cel']}", p["cel"] is p["okna"][0].sloty[0])
    # pełny plecak: rope nie ma gdzie wejść, ale gold idzie na stos (nie kończymy na rope)
    # (pełny plecak w pamięci nie zgodzi się ze zrzutem, więc "pełny" udaje _cel_w_plecaku: brak wolnych slotów)
    global _cel_w_plecaku
    prawdziwy_cel = _cel_w_plecaku
    try:
        _cel_w_plecaku = lambda plecak, ident, ilosc: (prawdziwy_cel(plecak, ident, ilosc)
                                                       if ident != 3003 else (None, None))
        p = z_pamiecia([kont(0, "dead rat", 3994, 5, (3003, 1), (3031, 3)), bag], lista=(3003, 3031))
        sprawdz(f"pełny plecak: rope czeka, gold na stos {p['przedmiot_id']} {p['cel']} ({p['pamiec']})",
                p["przedmiot_id"] == (3031, 3) and p["cel"] is p["okna"][0].sloty[0])
        p = z_pamiecia([kont(0, "dead rat", 3994, 5, (3003, 1), (3031, 3)), bag], lista=(3003,))
        sprawdz(f"pełny plecak: tylko rope -> cel None (pelny_plecak) {p['przedmiot_id']} {p['cel']}",
                p["przedmiot_id"] == (3003, 1) and p["cel"] is None)
    finally:
        _cel_w_plecaku = prawdziwy_cel
    # jedzenie w zwłokach
    p = z_pamiecia([zwloki, bag], lista=("gold coin",))
    sprawdz(f"jedzenie: ser w zwłokach do zjedzenia {p['jedzenie']}",
            p["jedzenie"] == (p["okna"][1].sloty[1], "cheese", 3607))
    global JEDZ_ZE_ZWLOK
    try:
        JEDZ_ZE_ZWLOK = False
        p = z_pamiecia([zwloki, bag], lista=("gold coin",))
        sprawdz("jedzenie: JEDZ_ZE_ZWLOK = False -> nie jemy", p["jedzenie"] is None)
    finally:
        JEDZ_ZE_ZWLOK = True
    sprawdz(f"jedzenie: kolejność ham, dragon ham, meat ... cheese ({KOLEJNOSC_JEDZENIA[:3]})",
            KOLEJNOSC_JEDZENIA[:3] == (3582, 3583, 3577)
            and KOLEJNOSC_JEDZENIA.index(3577) < KOLEJNOSC_JEDZENIA.index(3607) and len(KOLEJNOSC_JEDZENIA) == 27)
    # scalanie rozbitych stosów w plecaku
    p = z_pamiecia([zwloki, kont(1, "bag", 2853, 8, (3607, 1), (3607, 1))], lista=("meat",))
    sprawdz(f"scalenie: dwa sery po 1 -> slot 1 na slot 0 {scalenie(p['plecak'])}",
            scalenie(p["plecak"]) == (p["okna"][0].sloty[1], p["okna"][0].sloty[0], 3607))
    p = z_pamiecia([zwloki, kont(1, "bag", 2853, 8, (3031, 4), (3031, 100))], lista=("meat",))
    sprawdz("scalenie: gold 4 + 100 się nie mieści -> nic", scalenie(p["plecak"]) is None)
    # do_zebrania.txt: nazwa albo ID z komentarzem
    stare = dict(NAZWA_ID), dict(ID_NAZWA)
    try:
        wpisy = parsuj_liste(["# komentarz", "gold coin", "3607 # cheese", "2671 # ham", "  ", "Meat  # jedzenie"])
        sprawdz(f"lista: {wpisy}", wpisy == ("gold coin", 3607, 2671, "meat"))
        sprawdz(f"lista: ID 2671 nazwane z komentarza ({nazwa_id(2671)})", nazwa_id(2671) == "ham")
        idy, nazwy = rozdziel_liste(wpisy)
        sprawdz(f"lista: ID {sorted(idy)}, nazwy {sorted(nazwy)}",
                idy == {3031, 3607, 2671, 3577} and nazwy == {"gold coin", "cheese", "ham", "meat"})
    finally:
        NAZWA_ID.clear(); NAZWA_ID.update(stare[0]); ID_NAZWA.clear(); ID_NAZWA.update(stare[1])


def test():
    """Testy offline: bez gniazda, myszy i klawiatury (odczyt pamięci i zapis ikon to atrapy)."""
    global _zapytaj, zapisz_nieznany
    ok = True

    def sprawdz(opis, warunek):
        nonlocal ok
        print(("OK    " if warunek else "BŁĄD "), opis)
        ok &= bool(warunek)

    oryginaly = _zapytaj, zapisz_nieznany
    zapisz_nieznany = lambda *a, **k: None
    try:
        _zapytaj = lambda z: (_ for _ in ()).throw(ConnectionRefusedError("test offline"))
        _test_obrazu(sprawdz)
        _test_pamieci(sprawdz)
    finally:
        _zapytaj, zapisz_nieznany = oryginaly
    return ok


def main(argv):
    k = argv[1] if len(argv) > 1 else ""
    a = argv[2:]
    if k == "sloty":
        komenda_sloty(*a[:1])
    elif k == "rozpoznaj":
        komenda_rozpoznaj(*a[:1])
    elif k == "ikona" and len(a) >= 3:
        komenda_ikona(*a[:4])
    elif k == "tytul" and len(a) >= 3:
        komenda_tytul(*a[:4])
    elif k == "test":
        return 0 if test() else 1
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
