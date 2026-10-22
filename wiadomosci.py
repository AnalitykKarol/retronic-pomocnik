"""Odczyt wiadomości z konsoli gry (zakładki czatu OTClienta) z pamięci procesu.

Ładowany przez rdzen.py przy każdym poleceniu "wiadomosci" (importlib.reload),
więc zmiany działają bez restartu strażnika. Tylko odczyt.

Układ w pamięci (OTClient 32-bit, std::string i std::deque z MSVC):

  UITabBar "consoleTabBar"  +0x84: deque<UITab*> {mapa, rozmiar mapy, przesunięcie, liczba}
      element deque = surowy wskaźnik 4 B, 4 elementy na blok, indeks k = przesunięcie + i,
      blok = mapa[(k // 4) % rozmiar_mapy], miejsce = k % 4
  UITab "tab"  tekst (nazwa zakładki) +0x2AC; +0x438 wskazuje bufor NASTĘPNEJ zakładki
      (przesunięcie o jeden, patrz _przypisz_kanaly)
  UIScrollablePanel "consoleBuffer" (vtable gry, rodzic +0x64 = "tabPanel")
      +0x84: deque<UIWidget*> dzieci (kolejność = chronologia, najstarsza pierwsza)
  UILabel "consoleLabelN" (jedna wiadomość)
      +0x00 vtable, +0x0C id (std::string SSO), +0x64 rodzic (bufor),
      +0xC0 u32 czas utworzenia w ms zegara klienta (rosnący, wspólny dla zakładek),
      +0xE4 3 floaty RGB koloru tekstu, +0x2AC tekst (std::string: SSO <=15 lub wskaźnik)
  Tekst ma postać "HH:MM Nadawca: treść" albo "HH:MM treść" (komunikaty systemowe).
"""

import re
import struct
import time

BUFOR = re.compile(rb"consoleBuffer\x00", re.S)
PASEK = re.compile(rb"consoleTabBar\x00", re.S)

ID = 0xC               # std::string z id widgetu
RODZIC = 0x64
DZIECI = 0x84          # deque dzieci / zakładek
CZAS_MS = 0xC0
KOLOR = 0xE4
TEKST = 0x2AC
PANEL_ZAKLADKI = 0x438
# 22.10 (zmierzone na żywo, dawajkesh/gebelish/wydra/invincible; tylko odczyt): stan zakładki i widoczność bufora.
STAN_ZAKLADKI = 0xD0   # int: 0 = zakładka aktywna (styl "checked"), 2 = nieaktywna (wszystkie inne tak samo)
RECT_ZAKLADKI = 0x3C   # 4 x int: lewo, góra, prawo, dół w pikselach okna klienta (= piksele zrzutu sesji)
KOLOR_ZAKLADKI = 0xE4  # 3 floaty RGB tekstu: aktywna szara 0.87/0.87/0.87, nieaktywna czerwona 0.97/0.37/0.37
RECT_BUFORA = 0x3C     # ukryty bufor ma rect (2, 0, -2, -1), widoczny prawdziwy (np. 10, 788, 982, 884)
WIDOCZNY_BUFOR = 0x1E8  # int: 1 tylko u widocznego (aktywnego) bufora, 0 u pozostałych
ROZMIAR_WIDGETU = 0x2D0
MAKS_DZIECI = 2000
MAKS_LOG = 3000

OBRAZ_GRY = (0x400000, 0x1000000)   # vtable widgetów leżą w obrazie exe
SKAN_SZYBKI = 30.0     # odświeżenie listy buforów w znanych regionach
SKAN_PELNY = 600.0     # pełny skan całej pamięci (nowe zakładki są wykrywane wcześniej)
LINIA = re.compile(r"^(\d\d):(\d\d) (.*)$", re.S)
NADAWCA = re.compile(r"^([A-Za-z][A-Za-z0-9 '\-.]{0,29}?): (.*)$", re.S)
SYSTEMOWE = ("You ", "Loot of", "Monster loot", "Welcome ", "Your ", "Warning", "Server ")


def _wsk(v):
    return 0x10000 < v < 0x7FFF0000


def _tekst(b):
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp1250", "replace")


def _napis(p, bufor, o):
    """std::string MSVC w buforze widgetu: SSO (<=15) albo wskaźnik na bufor."""
    if o + 0x18 > len(bufor):
        return None
    rozmiar, pojemnosc = struct.unpack_from("<II", bufor, o + 0x10)
    if pojemnosc <= 15:
        return bufor[o:o + rozmiar] if rozmiar <= 15 else None
    if rozmiar > pojemnosc or pojemnosc > 1 << 20:
        return None
    ptr = struct.unpack_from("<I", bufor, o)[0]
    if not _wsk(ptr):
        return None
    dane = p.czytaj(ptr, rozmiar)
    return dane if len(dane) == rozmiar else None


def _id_widgetu(p, adres):
    b = p.czytaj(adres + ID, 0x18)
    return _napis(p, b, 0) if len(b) == 0x18 else None


def _deque(p, widget, przesuniecie=DZIECI):
    """Lista wskaźników z std::deque<T*> leżącego w widgecie."""
    b = p.czytaj(widget + przesuniecie, 16)
    if len(b) < 16:
        return None
    mapa, rozm_mapy, od, liczba = struct.unpack("<IIII", b)
    if not (_wsk(mapa) and 1 <= rozm_mapy <= 4096 and rozm_mapy & (rozm_mapy - 1) == 0
            and liczba <= min(MAKS_DZIECI, rozm_mapy * 4)):
        return None
    bloki = p.czytaj(mapa, 4 * rozm_mapy)
    if len(bloki) < 4 * rozm_mapy:
        return None
    wynik = []
    ostatni_blok, dane = None, b""
    for i in range(liczba):
        k = od + i
        nr = (k // 4) % rozm_mapy
        if nr != ostatni_blok:
            blok = struct.unpack_from("<I", bloki, 4 * nr)[0]
            dane = p.czytaj(blok, 16) if _wsk(blok) else b""
            ostatni_blok = nr
        if len(dane) < 16:
            return None
        wynik.append(struct.unpack_from("<I", dane, 4 * (k % 4))[0])
    return wynik


def _poprawny_bufor(p, adres):
    """consoleBuffer to widget z vtable gry, rodzicem "tabPanel" i poprawną deque dzieci."""
    b = p.czytaj(adres, 0x90)
    if len(b) < 0x90:
        return False
    vt = struct.unpack_from("<I", b, 0)[0]
    if not (OBRAZ_GRY[0] < vt < OBRAZ_GRY[1]):
        return False
    if _id_widgetu(p, adres) != b"consoleBuffer":
        return False
    rodzic = struct.unpack_from("<I", b, RODZIC)[0]
    if not _wsk(rodzic) or _id_widgetu(p, rodzic) != b"tabPanel":
        return False
    return _deque(p, adres) is not None


def _skan(p, regiony=None):
    """Jeden przebieg po pamięci: adresy buforów konsoli i paska zakładek
    oraz regiony, w których coś znaleziono."""
    bufory, paski, uzyte = [], [], set()
    for start, koniec in (regiony or p.regiony()):
        dane = p.czytaj(start, koniec - start)
        for wzorzec, sprawdz, cel in ((BUFOR, _poprawny_bufor, bufory), (PASEK, _poprawny_pasek, paski)):
            for m in wzorzec.finditer(dane):
                o = m.start()
                if o < ID or o + 0x18 > len(dane):
                    continue
                if not OBRAZ_GRY[0] < struct.unpack_from("<I", dane, o - ID)[0] < OBRAZ_GRY[1]:
                    continue
                rozmiar, pojemnosc = struct.unpack_from("<II", dane, o + 0x10)
                if pojemnosc == 15 and rozmiar == len(m.group()) - 1 and sprawdz(p, start + o - ID):
                    cel.append(start + o - ID)
                    uzyte.add((start, koniec))
    return bufory, paski, sorted(uzyte)


def _poprawny_pasek(p, adres):
    b = p.czytaj(adres, 0x90)
    if len(b) < 0x90 or not (OBRAZ_GRY[0] < struct.unpack_from("<I", b, 0)[0] < OBRAZ_GRY[1]):
        return False
    tab = _deque(p, adres)
    return bool(tab) and all(_id_widgetu(p, t) == b"tab" for t in tab)


def _zakladki(p, pasek):
    """[(adres zakładki, nazwa, wskaźnik z +0x438)] w kolejności paska."""
    wynik = []
    for t in _deque(p, pasek) or []:
        b = p.czytaj(t, PANEL_ZAKLADKI + 4)
        if len(b) < PANEL_ZAKLADKI + 4:
            continue
        nazwa = _napis(p, b, TEKST)
        wynik.append((t, _tekst(nazwa) if nazwa is not None else None,
                      struct.unpack_from("<I", b, PANEL_ZAKLADKI)[0]))
    return wynik


def stan_zakladek(p, st):
    """Zakładki paska z położeniem i stanem + aktywny bufor (22.10, serwis nie może pisać na zakładkę prywatną).

    {"zakladki": [{"nazwa", "rect": [x1, y1, x2, y2], "stan", "kolor": [r, g, b], "aktywna"}], "aktywny_bufor": "0x..."|None,
     "pasek": bool}. `aktywna` = stan 0 ORAZ tekst nie czerwony (dwa niezależne objawy tego samego stanu); `aktywny_bufor` =
    jedyny bufor z flagą widoczności i prawdziwym rectem (None, gdy żaden albo kilka). Odczyt tylko; kolejność listy nie
    jest kolejnością na ekranie, pozycję daje rect."""
    wynik = {"zakladki": [], "aktywny_bufor": None, "pasek": False}
    pasek = st["pasek"]
    if not pasek or not _poprawny_pasek(p, pasek):
        _odswiez(p, st, wymus=True)
        pasek = st["pasek"]
        if not pasek or not _poprawny_pasek(p, pasek):
            return wynik
    wynik["pasek"] = True
    for t in _deque(p, pasek) or []:
        b = p.czytaj(t, PANEL_ZAKLADKI + 4)
        if len(b) < PANEL_ZAKLADKI + 4 or _id_widgetu(p, t) != b"tab":
            continue
        nazwa = _napis(p, b, TEKST)
        stan = struct.unpack_from("<i", b, STAN_ZAKLADKI)[0]
        rect = list(struct.unpack_from("<4i", b, RECT_ZAKLADKI))
        kolor = [round(x, 2) for x in struct.unpack_from("<3f", b, KOLOR_ZAKLADKI)]
        wynik["zakladki"].append({"nazwa": _tekst(nazwa) if nazwa is not None else None, "rect": rect, "stan": stan,
                                  "kolor": kolor, "aktywna": stan == 0 and kolor[1] > 0.6})
    widoczne = []
    for bufor in st["bufory"]:
        if not _poprawny_bufor(p, bufor):
            continue
        b = p.czytaj(bufor, WIDOCZNY_BUFOR + 4)
        if len(b) < WIDOCZNY_BUFOR + 4:
            continue
        lewo, gora, prawo, dol = struct.unpack_from("<4i", b, RECT_BUFORA)
        if struct.unpack_from("<i", b, WIDOCZNY_BUFOR)[0] == 1 and prawo > lewo and dol > gora:
            widoczne.append(bufor)
    if len(widoczne) == 1:
        wynik["aktywny_bufor"] = hex(widoczne[0])
    return wynik


def _przypisz_kanaly(p, bufory, zakladki):
    """Nazwa zakładki dla każdego bufora (None, gdy nie da się ustalić).

    1) wskaźnik +0x438 zakładki i wskazuje bufor zakładki i+1 (zaobserwowane na żywo),
    2) pozostałe: nazwa zakładki zawarta w powitaniu kanału "Welcome on the channel 'X'"
       albo w pierwszym komunikacie bufora (np. loot),
    3) jeśli została jedna zakładka i jeden bufor, są sobie przypisane."""
    kanaly = {}
    wolne = [i for i in range(len(zakladki))]
    for i in range(1, len(zakladki)):
        cel = zakladki[i - 1][2]
        if cel in bufory and cel not in kanaly:
            kanaly[cel] = zakladki[i][1]
            wolne.remove(i)
    reszta = [b for b in bufory if b not in kanaly]
    for b in list(reszta):
        pierwszy = _pierwsza_tresc(p, b)
        if not pierwszy:
            continue
        for i in wolne:
            nazwa = (zakladki[i][1] or "").lower()
            if nazwa and nazwa != "default" and nazwa in pierwszy.lower():
                kanaly[b] = zakladki[i][1]
                wolne.remove(i)
                reszta.remove(b)
                break
    if len(wolne) == 1 and len(reszta) == 1:
        kanaly[reszta[0]] = zakladki[wolne[0]][1]
    return kanaly


def _pierwsza_tresc(p, bufor):
    dzieci = _deque(p, bufor) or []
    if not dzieci:
        return None
    b = p.czytaj(dzieci[0], ROZMIAR_WIDGETU)
    t = _napis(p, b, TEKST) if len(b) == ROZMIAR_WIDGETU else None
    return None if t is None else _tekst(t)


def _stan(p):
    st = p.__dict__.setdefault("_wiad", {})
    for k, v in (("bufory", []), ("pasek", None), ("skan", 0.0), ("pelny", 0.0), ("regiony", None),
                 ("kanaly", {}), ("zakladki", [])):
        st.setdefault(k, v)
    if "epoka" not in st:
        st["epoka"] = "%x" % int(time.time() * 1000)
        st.update(log=[], nr=0, ogony={})
    return st


def _odswiez(p, st, wymus=False):
    """Szybki skan (tylko regiony z poprzednich trafień) co SKAN_SZYBKI s, pełny co SKAN_PELNY s,
    gdy brak buforów, któryś przestał być poprawny albo zmieniła się liczba zakładek."""
    teraz = time.monotonic()
    zywe = [a for a in st["bufory"] if _poprawny_bufor(p, a)]
    tab = _deque(p, st["pasek"]) if st["pasek"] else None
    zmiana = len(zywe) != len(st["bufory"]) or (tab is not None and len(tab) != len(st["zakladki"]))
    pelny = wymus or not zywe or zmiana or not st["regiony"] or teraz - st["pelny"] > SKAN_PELNY
    if not pelny and teraz - st["skan"] <= SKAN_SZYBKI:
        return
    bufory, paski, uzyte = _skan(p, None if pelny else st["regiony"])
    if pelny:
        st["pelny"] = teraz
    elif not bufory:
        return
    st["bufory"] = bufory
    st["pasek"] = paski[0] if paski else st["pasek"] if not pelny else None
    st["regiony"] = uzyte if pelny or uzyte else st["regiony"]
    st["skan"] = teraz
    zakl = _zakladki(p, st["pasek"]) if st["pasek"] else []
    st["zakladki"] = [z[1] for z in zakl]
    st["kanaly"] = _przypisz_kanaly(p, bufory, zakl)


def _etykieta(p, widget, bufor):
    """(klucz, surowy tekst, licznik ms klienta, kolor RGB) albo None, gdy to nie etykieta tego bufora."""
    b = p.czytaj(widget, ROZMIAR_WIDGETU)
    if len(b) < ROZMIAR_WIDGETU:
        return None
    if struct.unpack_from("<I", b, RODZIC)[0] != bufor:
        return None
    id_ = _napis(p, b, ID)
    if id_ is None or not id_.startswith(b"consoleLabel"):
        return None
    surowy = _napis(p, b, TEKST)
    if surowy is None:
        return None
    r, g, bl = struct.unpack_from("<fff", b, KOLOR)
    kolor = "".join("%02x" % max(0, min(255, round(x * 255))) for x in (r, g, bl))
    t = struct.unpack_from("<I", b, CZAS_MS)[0]
    return (widget, t, surowy), surowy, t, kolor


def _rozbij(tekst):
    """(minuta doby albo None, "HH:MM", nadawca albo None, treść)."""
    m = LINIA.match(tekst)
    if not m:
        return None, None, None, tekst
    czas, reszta = f"{m.group(1)}:{m.group(2)}", m.group(3)
    minuta = int(m.group(1)) * 60 + int(m.group(2))
    n = NADAWCA.match(reszta)
    if n and not reszta.startswith(SYSTEMOWE):
        return minuta, czas, n.group(1), n.group(2)
    return minuta, czas, None, reszta


def _odczytaj_bufor(p, bufor):
    dzieci = _deque(p, bufor)
    if dzieci is None:
        return None
    wynik = []
    for w in dzieci:
        e = _etykieta(p, w, bufor)
        if e is not None:
            wynik.append(e)
    return wynik


def _synchronizuj(p, st):
    """Dopisuje do dziennika st["log"] wiadomości, których jeszcze nie było (numer rosnący nr)."""
    teraz = time.time()
    swieze = []
    for poz_bufora, bufor in enumerate(st["bufory"]):
        elementy = _odczytaj_bufor(p, bufor)
        if elementy is None:
            st["skan"] = 0.0   # bufor zniknął: odświeżenie listy przy następnym wywołaniu
            continue
        ogon = st["ogony"].get(bufor)
        start = 0
        if ogon is not None:
            for i in range(len(elementy) - 1, -1, -1):
                if elementy[i][0] == ogon:
                    start = i + 1
                    break
        if elementy:
            st["ogony"][bufor] = elementy[-1][0]
        nowe = elementy[start:]
        rozbite = [_rozbij(_tekst(e[1])) for e in nowe]
        epoki, nast, po = [None] * len(nowe), None, None   # po = minuta doby następnej wiadomości
        for i in range(len(nowe) - 1, -1, -1):          # od najnowszej: kotwica to "teraz"
            minuta = rozbite[i][0]
            if minuta is None:
                epoki[i] = nast
                continue
            if nast is None:
                lt = time.localtime(teraz)
                nast = int(teraz // 60) - (lt.tm_hour * 60 + lt.tm_min - minuta) % 1440
            else:
                nast -= (po - minuta) % 1440
            po = minuta
            epoki[i] = nast
        for i, e in enumerate(nowe):
            minuta, czas, nadawca, tresc = rozbite[i]
            swieze.append(((epoki[i] or 0), poz_bufora, i, {
                "ts": None if epoki[i] is None else epoki[i] * 60, "czas": czas, "nadawca": nadawca,
                "tekst": tresc, "kanal": st["kanaly"].get(bufor), "kolor": e[3], "bufor": hex(bufor),
                "t": e[2]}))
    swieze.sort(key=lambda x: x[:3])
    for _, _, _, m in swieze:
        st["nr"] += 1
        m["nr"] = st["nr"]
        st["log"].append(m)
    del st["log"][:-MAKS_LOG]


def wiadomosci(p, od=None, kanal=None, limit=100):
    st = _stan(p)
    _odswiez(p, st)
    _synchronizuj(p, st)
    lista = [m for m in st["log"] if (od is None or m["nr"] > od)
             and (kanal is None or (m["kanal"] or "").lower() == kanal.lower())]
    if limit:
        lista = lista[-int(limit):]
    return {"wiadomosci": lista, "znacznik": st["nr"], "epoka": st["epoka"],
            "kanaly": {hex(b): n for b, n in st["kanaly"].items()}, "zakladki": st["zakladki"]}


def obsluz(p, z):
    """{"cmd":"wiadomosci","od":<nr>,"epoka":<epoka>,"kanal":"Default","limit":100,"skan":true}
    Zwraca wiadomości z numerem nr > od (bez "od": cały dziennik, do limitu)."""
    st = _stan(p)
    if z.get("skan"):
        _odswiez(p, st, wymus=True)
    od = z.get("od")
    if od is not None and z.get("epoka") not in (None, st["epoka"]):
        od = None   # dziennik założony od nowa (restart strażnika): numery z innej epoki nie pasują
    odp = wiadomosci(p, None if od is None else int(od), z.get("kanal"), int(z.get("limit", 100)))
    if z.get("stan_zakladek"):
        odp["stan_zakladek"] = stan_zakladek(p, st)
    return odp
